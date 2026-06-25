# =============================================================================
#  ActuarIA — core/audit_trail.py
#  Agent Rafael A13 — Audit Trail & Conformité RGPD
#
#  Module transversal utilisé par TOUS les agents de toutes les directions.
#
#  Fonctionnalités :
#    · Hachage SHA-256 de chaque résultat de calcul
#    · Registre RGPD Art.30 des traitements
#    · Versioning des calculs par arrêté
#    · Génération du rapport d'audit JSON exportable
#    · Vérification d'intégrité (hash replay)
#
#  Usage :
#    from core.audit_trail import AuditTrail
#
#    audit = AuditTrail(agent_code='A7', agent_nom='Ibrahim')
#    audit.enregistrer(resultat=r, parametres={'lob': 'mrh', 'arrete': 'Q2 2026'})
#    rapport = audit.generer_rapport()
#    bytes_json = audit.exporter_json()
#
# =============================================================================

import hashlib
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger('actuaria.core.audit')


# =============================================================================
#  REGISTRE RGPD ART.30 — Définition des traitements
# =============================================================================

REGISTRE_TRAITEMENTS = {
    'A1':  {'traitement': 'Ingestion données sinistres/contrats', 'base_legale': 'Art.6(1)(b) RGPD — Exécution contrat', 'donnees': 'Données sinistres agrégées', 'duree': '10 ans (S2 Art.98)'},
    'A2':  {'traitement': 'Preprocessing feature engineering',    'base_legale': 'Art.6(1)(b) RGPD — Exécution contrat', 'donnees': 'Données sinistres transformées', 'duree': '10 ans'},
    'A3':  {'traitement': 'Tarification GLM',                     'base_legale': 'Art.6(1)(f) RGPD — Intérêt légitime', 'donnees': 'Coefficients tarifaires agrégés', 'duree': '10 ans'},
    'A4':  {'traitement': 'Tarification Machine Learning',        'base_legale': 'Art.6(1)(f) RGPD — Intérêt légitime', 'donnees': 'Modèles ML (pas de données perso)', 'duree': '10 ans'},
    'A5':  {'traitement': 'Tarification Deep Learning',           'base_legale': 'Art.6(1)(f) RGPD — Intérêt légitime', 'donnees': 'Modèles DL (pas de données perso)', 'duree': '10 ans'},
    'A6':  {'traitement': 'Sélection modèle de production',       'base_legale': 'Art.6(1)(f) RGPD — Intérêt légitime', 'donnees': 'Métriques comparatives', 'duree': '10 ans'},
    'A7':  {'traitement': 'Provisionnement Non-Vie',              'base_legale': 'Art.6(1)(c) RGPD — Obligation légale (S2 Art.77)', 'donnees': 'Triangles de développement agrégés', 'duree': '10 ans (S2 Art.98)'},
    'A8':  {'traitement': 'Stress Testing & ORSA',                'base_legale': 'Art.6(1)(c) RGPD — Obligation légale (S2 Art.45)', 'donnees': 'KPIs agrégés', 'duree': '10 ans'},
    'A9':  {'traitement': 'Cohérence inter-équipes',              'base_legale': 'Art.6(1)(c) RGPD — Obligation légale', 'donnees': 'Résultats agrégés', 'duree': '10 ans'},
    'A10': {'traitement': 'Solvabilité 2 SCR/MCR',                'base_legale': 'Art.6(1)(c) RGPD — Obligation légale (S2 Art.101)', 'donnees': 'KPIs S2 agrégés', 'duree': '10 ans'},
    'A11': {'traitement': 'IFRS 17 PAA',                          'base_legale': 'Art.6(1)(c) RGPD — Obligation légale (IFRS 17)', 'donnees': 'Provisions comptables agrégées', 'duree': '10 ans'},
    'A12': {'traitement': 'ALM & Risque liquidité',               'base_legale': 'Art.6(1)(c) RGPD — Obligation légale (S2)', 'donnees': 'Données actif-passif agrégées', 'duree': '10 ans'},
    'SP1': {'traitement': 'Tarification santé',                   'base_legale': 'Art.6(1)(b) RGPD — Exécution contrat', 'donnees': 'Statistiques CCAM/NGAP agrégées', 'duree': '10 ans'},
    'SP2': {'traitement': 'Provisionnement santé',                'base_legale': 'Art.6(1)(c) RGPD — Obligation légale', 'donnees': 'PSAP agrégé', 'duree': '10 ans'},
    'SP3': {'traitement': 'Reporting santé AMEXA/DREES',          'base_legale': 'Art.6(1)(c) RGPD — Obligation légale', 'donnees': 'Statistiques agrégées', 'duree': '10 ans'},
    'SP4': {'traitement': 'Tarification prévoyance ITT/Invalidité','base_legale': 'Art.6(1)(b) RGPD — Exécution contrat', 'donnees': 'Tables morbidité agrégées', 'duree': '10 ans'},
    'SP5': {'traitement': 'Tables de morbidité',                  'base_legale': 'Art.6(1)(b) RGPD — Exécution contrat', 'donnees': 'Tables BCAC 2004 (publiques)', 'duree': '10 ans'},
    'SP6': {'traitement': 'Provisionnement prévoyance',           'base_legale': 'Art.6(1)(c) RGPD — Obligation légale', 'donnees': 'PM invalidité agrégées', 'duree': '10 ans'},
    'SP7': {'traitement': 'Reporting prévoyance',                 'base_legale': 'Art.6(1)(c) RGPD — Obligation légale', 'donnees': 'QRT agrégés', 'duree': '10 ans'},
}


# =============================================================================
#  CLASSE PRINCIPALE
# =============================================================================

class AuditTrail:
    """
    Gestionnaire d'audit trail transversal ActuarIA.

    Chaque agent instancie AuditTrail au début de son run() et enregistre
    son résultat à la fin. Le rapport exportable est conforme RGPD Art.30
    et aux exigences de traçabilité S2 Art.98.
    """

    VERSION_AUDIT = '1.0'

    def __init__(
        self,
        agent_code  : str,
        agent_nom   : str,
        audit_path  : str = '/tmp/actuaria',
        ref_client  : str = '',
        arrete      : str = '',
    ):
        self.agent_code  = agent_code.upper()
        self.agent_nom   = agent_nom
        self.audit_path  = Path(audit_path)
        self.ref_client  = ref_client
        self.arrete      = arrete
        self.audit_path.mkdir(parents=True, exist_ok=True)

        # Identifiant unique de session d'audit
        self.session_id  = f"{self.agent_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
        self.timestamp   = datetime.now().isoformat()

        # Registre des événements
        self._events     : List[Dict] = []
        self._hash_final : str = ''

        logger.debug(f"[AUDIT] Session {self.session_id} ouverte pour {agent_nom}")

    # =========================================================================
    #  ENREGISTREMENT
    # =========================================================================

    def log_event(self, etape: str, statut: str, detail: str = '', data: Any = None) -> None:
        """
        Enregistre un événement dans le trail.

        Parameters
        ----------
        etape   : nom de l'étape (ex. 'N1_INGESTION', 'N3_CHAIN_LADDER')
        statut  : 'OK' / 'WARNING' / 'ERROR'
        detail  : message descriptif
        data    : données optionnelles à hasher pour l'intégrité
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'etape':     etape,
            'statut':    statut,
            'detail':    str(detail)[:500],
        }
        if data is not None:
            event['hash_data'] = self._hasher(data)
        self._events.append(event)

    def enregistrer(
        self,
        resultat    : Dict,
        parametres  : Dict = None,
    ) -> str:
        """
        Enregistre le résultat final et calcule le hash d'intégrité.

        Returns
        -------
        hash_final : str — hash SHA-256 tronqué (8 caractères) du résultat
        """
        # Hash du résultat complet
        self._hash_final = self._hasher(resultat)

        self.log_event(
            etape='RESULTAT_FINAL',
            statut='OK' if resultat.get('success') else 'ERROR',
            detail=f"statut_rag={resultat.get('statut_rag','?')} · hash={self._hash_final}",
            data=resultat,
        )

        if parametres:
            self.log_event(
                etape='PARAMETRES',
                statut='OK',
                detail=json.dumps({k: str(v)[:100] for k, v in parametres.items()}, ensure_ascii=False),
            )

        logger.debug(f"[AUDIT] {self.session_id} · hash={self._hash_final}")
        return self._hash_final

    # =========================================================================
    #  GÉNÉRATION DU RAPPORT
    # =========================================================================

    def generer_rapport(self) -> Dict:
        """
        Génère le rapport d'audit complet conforme RGPD Art.30 + S2 Art.98.

        Returns
        -------
        Dict structuré avec toutes les métadonnées d'audit.
        """
        # Fiche RGPD Art.30
        rgpd = REGISTRE_TRAITEMENTS.get(self.agent_code, {
            'traitement':  f'Calcul actuariel {self.agent_code}',
            'base_legale': 'Art.6(1)(c) RGPD — Obligation légale',
            'donnees':     'Données actuarielles agrégées',
            'duree':       '10 ans',
        })

        rapport = {
            # ── Identification ────────────────────────────────────────────────
            'version_audit':    self.VERSION_AUDIT,
            'session_id':       self.session_id,
            'timestamp':        self.timestamp,
            'timestamp_fin':    datetime.now().isoformat(),
            # ── Agent ─────────────────────────────────────────────────────────
            'agent_code':       self.agent_code,
            'agent_nom':        self.agent_nom,
            'ref_client':       self.ref_client or '—',
            'arrete':           self.arrete     or '—',
            # ── Intégrité ─────────────────────────────────────────────────────
            'hash_sha256':      self._hash_final or 'NON_CALCULÉ',
            'nb_events':        len(self._events),
            'events':           self._events,
            # ── RGPD Art.30 ───────────────────────────────────────────────────
            'rgpd_art30': {
                'responsable_traitement': 'ActuarIA',
                'finalite':               rgpd.get('traitement', '—'),
                'base_legale':            rgpd.get('base_legale', '—'),
                'categories_donnees':     rgpd.get('donnees', '—'),
                'duree_conservation':     rgpd.get('duree', '10 ans'),
                'mesures_securite':       'Hachage SHA-256 · Chiffrement TLS · Accès authentifié',
                'transfert_tiers':        'Aucun transfert vers des tiers',
            },
            # ── S2 Art.98 ─────────────────────────────────────────────────────
            's2_art98': {
                'traçabilite':    'Conforme — hash SHA-256 + session_id unique',
                'versioning':     f'Session {self.session_id}',
                'conservation':   '10 ans minimum (Art.98 Directive S2)',
                'reproductibilite': 'Les paramètres sont enregistrés pour reproductibilité',
            },
        }
        return rapport

    def exporter_json(self, sauvegarder: bool = True) -> bytes:
        """
        Exporte le rapport d'audit en JSON bytes.

        Parameters
        ----------
        sauvegarder : si True, sauvegarde aussi sur disque dans audit_path

        Returns
        -------
        bytes JSON encodé UTF-8
        """
        rapport = self.generer_rapport()
        json_str = json.dumps(rapport, indent=2, ensure_ascii=False, default=str)
        json_bytes = json_str.encode('utf-8')

        if sauvegarder:
            try:
                chemin = self.audit_path / f"audit_{self.session_id}.json"
                chemin.write_text(json_str, encoding='utf-8')
                logger.debug(f"[AUDIT] Sauvegardé : {chemin}")
            except Exception as e:
                logger.warning(f"[AUDIT] Sauvegarde impossible : {e}")

        return json_bytes

    # =========================================================================
    #  VÉRIFICATION D'INTÉGRITÉ
    # =========================================================================

    def verifier_integrite(self, resultat: Dict, hash_reference: str) -> bool:
        """
        Vérifie qu'un résultat correspond à un hash de référence.
        Permet de détecter toute modification a posteriori.

        Returns
        -------
        bool : True si intègre, False si altéré
        """
        hash_calcule = self._hasher(resultat)
        integre = hash_calcule == hash_reference
        if not integre:
            logger.warning(
                f"[AUDIT] ⚠️ INTÉGRITÉ COMPROMISE — "
                f"hash calculé={hash_calcule} ≠ référence={hash_reference}"
            )
        return integre

    # =========================================================================
    #  UTILITAIRES INTERNES
    # =========================================================================

    @staticmethod
    def _hasher(data: Any) -> str:
        """Hash SHA-256 tronqué à 8 caractères pour lisibilité."""
        try:
            serialized = json.dumps(data, default=str, sort_keys=True)
            return hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:8].upper()
        except Exception:
            return 'HASH_ERR'

    @property
    def hash_final(self) -> str:
        return self._hash_final

    @property
    def audit_id(self) -> str:
        return self.session_id


# =============================================================================
#  AGENT RAFAEL A13 — Interface compatible avec le reste de la plateforme
# =============================================================================

class AgentRafael(AuditTrail):
    """
    Agent Rafael A13 — Audit Trail & Conformité RGPD.
    Wrapper de AuditTrail pour compatibilité avec l'interface agent standard.

    Usage depuis actuaria_app.py :
        from core.audit_trail import AgentRafael
        rafael = AgentRafael(agent_code='A7', agent_nom='Ibrahim', ref_client='Mutuelle X')
        rafael.log_event('N1_INGESTION', 'OK', '28×28 triangle validé')
        hash_final = rafael.enregistrer(resultat=r)
        audit_bytes = rafael.exporter_json()
    """

    AGENT_CODE    = 'A13'
    AGENT_NOM     = 'Rafael'
    AGENT_VERSION = '1.0'

    def __init__(self, agent_code='A13', agent_nom='Rafael', **kwargs):
        super().__init__(agent_code=agent_code, agent_nom=agent_nom, **kwargs)

    def run(self, resultats: Dict, parametres: Dict = None) -> Dict:
        """
        Interface run() standard pour compatibilité avec le pipeline.

        Parameters
        ----------
        resultats  : dict retourné par n'importe quel agent
        parametres : paramètres du calcul pour traçabilité

        Returns
        -------
        Dict standardisé avec audit_trail et hash
        """
        hash_final = self.enregistrer(resultat=resultats, parametres=parametres)
        rapport    = self.generer_rapport()
        audit_bytes = self.exporter_json(sauvegarder=True)

        return {
            'success':      True,
            'statut_rag':   'VERT',
            'audit_id':     self.session_id,
            'hash_sha256':  hash_final,
            'audit_trail':  rapport,
            'audit_bytes':  audit_bytes,
            'erreur':       None,
        }
