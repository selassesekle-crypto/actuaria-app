"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                ACTUARIA — AGENT A1 : INGESTION & VALIDATION v2              ║
║                        Version 2.0 — Production                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  NOUVEAUTÉS v2 :                                                             ║
║  • Chargement config centrale (actuaria_config.json)                       ║
║  • Module mapping colonnes client (client_id_mapping.json)                 ║
║  • Suggestions automatiques de colonnes similaires                         ║
║  • Portabilité totale (Drive → AWS → OVHcloud → local)                    ║
║                                                                              ║
║  USAGE STANDARD :                                                            ║
║  agent_a1 = AgentA1Ingestion()                                             ║
║  result_a1 = agent_a1.run(branche='non_vie', fichier='contrats.parquet')  ║
║                                                                              ║
║  USAGE AVEC CLIENT :                                                         ║
║  result_a1 = agent_a1.run(                                                 ║
║      branche   = 'non_vie',                                                ║
║      fichier   = 'contrats_client.xlsx',                                   ║
║      client_id = 'client_xyz',                                             ║
║  )                                                                          ║
║                                                                              ║
║  AUTEUR    : ActuarIA v2.0                                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import hashlib
import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('actuaria.a1')


# ══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT CONFIG CENTRALE
# ══════════════════════════════════════════════════════════════════════════════

def _charger_config(config_path: str = None) -> Dict:
    """
    Charge la configuration centrale depuis actuaria_config.json.
    Si non trouvée, utilise les valeurs par défaut (Drive).
    """
    chemins_possibles = [
        config_path,
        '/tmp/actuaria/config/actuaria_config.json',
        '/tmp/actuaria/actuaria_config.json',
        './actuaria_config.json',
    ]

    for chemin in chemins_possibles:
        if chemin and Path(chemin).exists():
            try:
                with open(chemin) as f:
                    config = json.load(f)
                logger.info(f"Config chargée depuis : {chemin}")
                return config
            except Exception:
                pass

    # Valeurs par défaut
    logger.warning("Config non trouvée — valeurs par défaut utilisées")
    base = '/tmp/actuaria'
    return {
        'base_path':    base,
        'data_path':    f'{base}/data',
        'models_path':  f'{base}/models',
        'audit_path':   f'{base}/audit',
        'config_path':  f'{base}/config',
        'reports_path': f'{base}/reports',
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAPPING DES COLONNES PAR DÉFAUT
# ══════════════════════════════════════════════════════════════════════════════

# Colonnes ActuarIA standard → synonymes courants
# Utilisé pour la détection automatique de colonnes similaires
SYNONYMES_COLONNES = {
    'id_contrat':             ['num_police', 'id_police', 'policy_id', 'num_contrat',
                               'idpol', 'id_pol', 'num_pol', 'contract_id'],
    'nb_sinistres':           ['claimnb', 'nb_claims', 'sinistres', 'claim_count',
                               'nbre_sinistres', 'nb_sin'],
    'exposition':             ['exposure', 'expo', 'duree', 'duration', 'poids'],
    'age':                    ['drimage', 'age_conducteur', 'age_cdt', 'age_driver',
                               'age_assure', 'age_client'],
    'bonus_malus':            ['bonusmalus', 'crm', 'bm', 'bonus_malus_coeff',
                               'coefficient_bm', 'malus'],
    'puissance_fiscale':      ['vehpower', 'puiss', 'puiss_fisc', 'puissance',
                               'cv_fiscaux', 'power'],
    'age_vehicule':           ['vehage', 'age_veh', 'anciennete_vehicule',
                               'vehicle_age', 'age_auto'],
    'cout_total_sinistres':   ['claimamount', 'montant_sinistres', 'cout_sinistres',
                               'claim_amount', 'montant', 'charge'],
    'zone_geographique':      ['area', 'zone', 'region_risque', 'zone_geo'],
    'region':                 ['region', 'departement', 'dept', 'localisation'],
    'carburant':              ['vehgas', 'fuel', 'energie', 'motorisation'],
    'densite_population':     ['density', 'densite', 'population_density'],
}


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION DES BRANCHES
# ══════════════════════════════════════════════════════════════════════════════

MOTS_CLES_DETECTION = {
    'auto': ['auto', 'vehicule', 'voiture', 'conducteur', 'bonus_malus',
             'bonusmalus', 'puissance', 'vehpower', 'drimage', 'vehgas'],
    'mrh':  ['mrh', 'habitation', 'logement', 'surface', 'locataire'],
    'rcpro':['rcpro', 'rc_pro', 'responsabilite', 'professionnel'],
    'vie':  ['vie', 'deces', 'capital', 'prime_unique', 'taux_technique'],
    'sante':['sante', 'maladie', 'ij', 'hospitalisation', 'optique'],
    'prevoyance': ['prevoyance', 'invalidite', 'incapacite', 'iaptd'],
    'epargne': ['epargne', 'retraite', 'per', 'art39', 'art83', 'encours'],
}

FORMATS_SUPPORTES = ['.csv', '.xlsx', '.xls', '.parquet', '.json', '.txt']

SEUILS_QUALITE = {
    'completude_rouge': 80.0,
    'completude_ambre': 95.0,
    'doublons_rouge':    5.0,
    'doublons_ambre':    1.0,
}


class AgentA1Ingestion:
    """
    Agent A1 — Ingestion & Validation v2.

    NOUVEAUTÉS v2 :
    ────────────────
    • Config centrale — portabilité totale
    • Mapping colonnes client — JSON par client
    • Détection automatique des colonnes similaires

    EXEMPLE D'UTILISATION :
    ─────────────────────────
    # Usage standard
    agent_a1 = AgentA1Ingestion()
    result_a1 = agent_a1.run(branche='non_vie', fichier='contrats.parquet')

    # Usage avec client réel
    agent_a1 = AgentA1Ingestion()
    result_a1 = agent_a1.run(
        branche   = 'non_vie',
        fichier   = 'contrats_client.xlsx',
        client_id = 'assurance_xyz',
    )
    """

    def __init__(
        self,
        base_path:   str = None,
        audit_path:  str = None,
        config_path: str = None,
        verbose:     bool = True,
    ):
        # Chargement config centrale
        self.config = _charger_config(config_path)

        # Les chemins passés en paramètre écrasent la config
        self.base_path  = Path(base_path  or self.config['data_path'])
        self.audit_path = Path(audit_path or self.config['audit_path'])
        self.config_path_dir = Path(self.config.get('config_path',
            str(self.base_path.parent / 'config')))
        self.verbose    = verbose

        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.config_path_dir.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            logger.info(f"Agent A1 Ingestion v2 initialisé | base={self.base_path}")

    def run(
        self,
        branche:   str = 'non_vie',
        fichier:   str = 'contrats_auto_70k.parquet',
        client_id: str = None,
        dataframe  = None,
    ) -> Dict[str, Any]:
        """
        Pipeline d'ingestion complet.

        Paramètres
        ──────────
        branche : str
            'non_vie' | 'vie' | 'sante_prevoyance'

        fichier : str
            Nom du fichier de données (avec extension).
            Formats : .csv · .xlsx · .xls · .parquet · .json · .txt

        client_id : str, optionnel
            Identifiant unique du client.
            Ex : 'assurance_xyz', 'cabinet_abc'
            Si fourni → charge le mapping depuis
            config/client_id_mapping.json
        """
        t_debut  = datetime.now()
        audit_id = f"A1_{t_debut.strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"[{audit_id}] Agent A1 v2 démarré | {fichier} | client={client_id}")

        rapport = {'etapes': [], 'alertes': [], 'mapping_applique': False}

        try:
            # ── ÉTAPE 1 : CHARGEMENT ──────────────────────────────────────────
            # Si un DataFrame est fourni directement → on saute le chargement
            # fichier. Permet l'utilisation depuis Streamlit, FastAPI, etc.
            if dataframe is not None:
                import pandas as pd
                if not isinstance(dataframe, pd.DataFrame):
                    raise ValueError("Le paramètre 'dataframe' doit être un pd.DataFrame.")
                df = dataframe.copy()
                sous_branche = self._detecter_sous_branche(df, branche)
                rapport['etapes'].append('dataframe_direct')
                logger.info(f"DataFrame direct : {df.shape} | sous-branche : {sous_branche}")
            else:
                df, sous_branche = self._charger_fichier(fichier, branche)
                rapport['etapes'].append('chargement')
                logger.info(f"Chargé : {df.shape} | sous-branche détectée : {sous_branche}")

            # ── ÉTAPE 2 : MAPPING COLONNES CLIENT ────────────────────────────
            if client_id:
                df, mapping_info = self._appliquer_mapping_client(
                    df, client_id
                )
                rapport['mapping_applique'] = mapping_info['applique']
                rapport['mapping_info']     = mapping_info
                if mapping_info['applique']:
                    logger.info(
                        f"Mapping client '{client_id}' appliqué : "
                        f"{mapping_info['nb_colonnes_renommees']} colonnes renommées"
                    )
            else:
                # Détection automatique des colonnes similaires
                suggestions = self._suggerer_mapping(df)
                if suggestions:
                    rapport['alertes'].append(
                        f"Colonnes non standard détectées. "
                        f"Suggestions : {suggestions}. "
                        f"Créez un mapping client pour automatiser."
                    )
                    logger.info(f"Suggestions mapping : {suggestions}")

            # ── ÉTAPE 3 : VALIDATION QUALITÉ ─────────────────────────────────
            qualite = self._valider_qualite(df)
            rapport['etapes'].append('validation_qualite')

            # ── ÉTAPE 4 : HASH MD5 ────────────────────────────────────────────
            hash_md5 = self._calculer_hash(df)
            rapport['etapes'].append('hash')

            # ── ÉTAPE 5 : STATUT RAG ──────────────────────────────────────────
            statut_rag  = self._calculer_statut_rag(qualite)
            score_qual  = qualite['score_global']
            commentaire = self._commenter_actuaire_senior(
                qualite, sous_branche, statut_rag, df, client_id
            )

            self._sauvegarder_audit(
                audit_id, sous_branche, rapport,
                qualite, statut_rag, hash_md5, t_debut, client_id
            )

            if self.verbose:
                self._afficher_rapport_console(
                    audit_id, sous_branche, qualite,
                    statut_rag, score_qual, commentaire, client_id
                )

            return {
                'success':      True,
                'dataframe':    df,
                'branche':      sous_branche,
                'statut_rag':   statut_rag,
                'score_qual':   score_qual,
                'qualite':      qualite,
                'hash_md5':     hash_md5,
                'rapport':      rapport,
                'commentaire':  commentaire,
                'audit_id':     audit_id,
                'client_id':    client_id,
                'erreur':       None,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {
                'success':    False,
                'dataframe':  pd.DataFrame(),
                'branche':    branche,
                'statut_rag': 'ROUGE',
                'score_qual': 0,
                'audit_id':   audit_id,
                'erreur':     str(e),
                'commentaire':f"❌ ERREUR A1 : {e}",
            }

    # ══════════════════════════════════════════════════════════════════════════
    # CHARGEMENT FICHIER
    # ══════════════════════════════════════════════════════════════════════════

    def _charger_fichier(
        self,
        fichier:  str,
        branche:  str
    ):
        """Charge le fichier de données depuis le bon sous-dossier."""
        # Cherche dans toutes les branches
        branches_ordre = [branche] + [
            b for b in ['non_vie', 'vie', 'sante_prevoyance']
            if b != branche
        ]

        df = None
        for br in branches_ordre:
            chemin = self.base_path / br / fichier
            if chemin.exists():
                df = self._lire_fichier(chemin)
                break

        # Cherche directement dans base_path
        if df is None:
            chemin = self.base_path / fichier
            if chemin.exists():
                df = self._lire_fichier(chemin)

        if df is None:
            raise FileNotFoundError(
                f"Fichier '{fichier}' non trouvé dans {self.base_path}. "
                f"Branches cherchées : {branches_ordre}"
            )

        # Détection sous-branche
        sous_branche = self._detecter_sous_branche(df, branche)
        return df, sous_branche

    def _lire_fichier(self, chemin: Path) -> pd.DataFrame:
        """Lit un fichier selon son extension."""
        ext = chemin.suffix.lower()
        if ext == '.parquet':
            return pd.read_parquet(chemin)
        elif ext in ['.xlsx', '.xls']:
            return pd.read_excel(chemin, engine='openpyxl')
        elif ext == '.csv':
            # Détection automatique du séparateur
            for sep in [',', ';', '\t', '|']:
                try:
                    df = pd.read_csv(chemin, sep=sep, nrows=5)
                    if df.shape[1] > 1:
                        return pd.read_csv(chemin, sep=sep)
                except Exception:
                    continue
            return pd.read_csv(chemin)
        elif ext == '.json':
            return pd.read_json(chemin)
        elif ext == '.txt':
            return pd.read_csv(chemin, sep='\t')
        else:
            raise ValueError(f"Format non supporté : {ext}")

    def _detecter_sous_branche(
        self,
        df:      pd.DataFrame,
        branche: str
    ) -> str:
        """Détecte automatiquement la sous-branche."""
        cols_lower = [c.lower() for c in df.columns]
        scores     = {k: 0 for k in MOTS_CLES_DETECTION}

        for sous_br, mots in MOTS_CLES_DETECTION.items():
            for mot in mots:
                if any(mot in col for col in cols_lower):
                    scores[sous_br] += 1

        meilleur = max(scores, key=scores.get)
        if scores[meilleur] > 0:
            return meilleur
        return branche.split('_')[0] if '_' in branche else branche

    # ══════════════════════════════════════════════════════════════════════════
    # MAPPING COLONNES CLIENT
    # ══════════════════════════════════════════════════════════════════════════

    def _appliquer_mapping_client(
        self,
        df:        pd.DataFrame,
        client_id: str
    ) -> tuple:
        """
        Applique le mapping de colonnes pour un client donné.

        Charge le fichier : config/{client_id}_mapping.json
        Si non trouvé → crée un mapping suggéré automatiquement

        FORMAT DU FICHIER MAPPING :
        ────────────────────────────
        {
          "NUM_POL":   "id_contrat",
          "AGE_CDT":   "age",
          "CRM":       "bonus_malus",
          "PUISS":     "puissance_fiscale"
        }
        """
        mapping_info = {
            'applique':             False,
            'nb_colonnes_renommees':0,
            'colonnes_renommees':   {},
            'mapping_source':       None,
        }

        # Cherche le fichier mapping
        chemin_mapping = self.config_path_dir / f"{client_id}_mapping.json"

        if chemin_mapping.exists():
            try:
                with open(chemin_mapping) as f:
                    mapping = json.load(f)

                # Applique uniquement les colonnes présentes dans le DataFrame
                mapping_applicable = {
                    k: v for k, v in mapping.items()
                    if k in df.columns
                }

                if mapping_applicable:
                    df = df.rename(columns=mapping_applicable)
                    mapping_info['applique']              = True
                    mapping_info['nb_colonnes_renommees'] = len(mapping_applicable)
                    mapping_info['colonnes_renommees']    = mapping_applicable
                    mapping_info['mapping_source']        = str(chemin_mapping)

            except Exception as e:
                logger.warning(f"Erreur chargement mapping client : {e}")
        else:
            # Mapping non trouvé → détection automatique + création suggestion
            mapping_suggere = self._suggerer_mapping(df)
            if mapping_suggere:
                # Sauvegarde le mapping suggéré pour validation
                chemin_suggere = self.config_path_dir / f"{client_id}_mapping_SUGGERE.json"
                try:
                    with open(chemin_suggere, 'w') as f:
                        json.dump(mapping_suggere, f, indent=2, ensure_ascii=False)
                    logger.info(
                        f"Mapping suggéré sauvegardé : {chemin_suggere}\n"
                        f"→ Renommer en '{client_id}_mapping.json' après validation"
                    )
                    mapping_info['mapping_source'] = f"SUGGÉRÉ (à valider) : {chemin_suggere}"
                except Exception:
                    pass

        return df, mapping_info

    def _suggerer_mapping(self, df: pd.DataFrame) -> Dict:
        """
        Suggère automatiquement un mapping basé sur les synonymes connus.

        Ex : si le DataFrame a une colonne 'CRM' →
        suggère {'CRM': 'bonus_malus'}
        """
        suggestions = {}
        cols_df = {c.lower(): c for c in df.columns}

        for col_standard, synonymes in SYNONYMES_COLONNES.items():
            # Vérifie si la colonne standard existe déjà
            if col_standard in df.columns:
                continue
            # Cherche un synonyme dans les colonnes du DataFrame
            for syn in synonymes:
                if syn.lower() in cols_df:
                    col_originale = cols_df[syn.lower()]
                    suggestions[col_originale] = col_standard
                    break

        return suggestions

    # ══════════════════════════════════════════════════════════════════════════
    # VALIDATION QUALITÉ
    # ══════════════════════════════════════════════════════════════════════════

    def _valider_qualite(self, df: pd.DataFrame) -> Dict:
        """Calcule les métriques de qualité du DataFrame."""
        n = len(df)

        # Complétude
        taux_complet = (1 - df.isnull().mean()).mean() * 100

        # Doublons
        cols_id = [c for c in df.columns if 'id' in c.lower() or 'pol' in c.lower()]
        if cols_id:
            nb_doublons = df.duplicated(subset=[cols_id[0]]).sum()
        else:
            nb_doublons = df.duplicated().sum()
        taux_doublons = nb_doublons / max(n, 1) * 100

        # Exposition
        if 'exposition' in df.columns:
            expo_ok = (df['exposition'].between(0, 1)).mean() * 100
        else:
            expo_ok = 100.0

        # Score global
        score = min(
            taux_complet * 0.50
            + (100 - taux_doublons) * 0.30
            + expo_ok * 0.20,
            100.0
        )

        return {
            'nb_lignes':        n,
            'nb_colonnes':      len(df.columns),
            'taux_completude':  round(taux_complet, 2),
            'nb_doublons':      int(nb_doublons),
            'taux_doublons':    round(taux_doublons, 2),
            'expo_ok_pct':      round(expo_ok, 2),
            'score_global':     round(score, 2),
            'colonnes':         df.columns.tolist(),
        }

    def _calculer_hash(self, df: pd.DataFrame) -> str:
        """Calcule le hash MD5 du DataFrame pour l'audit trail."""
        try:
            return hashlib.md5(
                pd.util.hash_pandas_object(df, index=True).values.tobytes()
            ).hexdigest()
        except Exception:
            return 'hash_non_disponible'

    # ══════════════════════════════════════════════════════════════════════════
    # STATUT RAG & COMMENTAIRES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_statut_rag(self, qualite: Dict) -> str:
        c = qualite['taux_completude']
        d = qualite['taux_doublons']
        if c < SEUILS_QUALITE['completude_rouge'] or d > SEUILS_QUALITE['doublons_rouge']:
            return 'ROUGE'
        elif c < SEUILS_QUALITE['completude_ambre'] or d > SEUILS_QUALITE['doublons_ambre']:
            return 'AMBRE'
        return 'VERT'

    def _commenter_actuaire_senior(
        self,
        qualite:      Dict,
        sous_branche: str,
        statut_rag:   str,
        df:           pd.DataFrame,
        client_id:    Optional[str]
    ) -> str:
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]

        n1 = (
            f"{emoji} INGESTION — {statut_rag}\n"
            f"Sous-branche  : {sous_branche}\n"
            f"Client        : {client_id or 'Standard'}\n"
            f"Lignes        : {qualite['nb_lignes']:,}\n"
            f"Colonnes      : {qualite['nb_colonnes']}\n"
            f"Complétude    : {qualite['taux_completude']:.1f}%\n"
            f"Doublons      : {qualite['nb_doublons']:,} ({qualite['taux_doublons']:.2f}%)\n"
            f"Score qualité : {qualite['score_global']:.1f}/100"
        )

        if statut_rag == 'VERT':
            n2 = (
                "DIAGNOSTIC :\n"
                "Les données sont de bonne qualité et prêtes "
                "pour le pipeline de modélisation."
            )
            n3 = "RECOMMANDATION :\n→ Passer à l'Agent A2 (Preprocessing)."
        elif statut_rag == 'AMBRE':
            n2 = (
                "DIAGNOSTIC :\n"
                "Quelques points d'attention détectés. "
                "Le pipeline peut continuer mais surveiller les résultats."
            )
            n3 = (
                "RECOMMANDATION :\n"
                "→ Vérifier les valeurs manquantes avant A2.\n"
                "→ Contrôler les doublons si taux > 1%."
            )
        else:
            n2 = (
                "DIAGNOSTIC :\n"
                "Qualité insuffisante pour la modélisation. "
                "Corriger les données avant de continuer."
            )
            n3 = (
                "RECOMMANDATION :\n"
                "→ Corriger les données sources.\n"
                "→ Relancer A1 après correction."
            )

        return f"{n1}\n\n{n2}\n\n{n3}"

    def _afficher_rapport_console(
        self, audit_id, sous_branche, qualite,
        statut_rag, score_qual, commentaire, client_id
    ) -> None:
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
        sep   = "═" * 65
        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT A1 INGESTION v2 | {audit_id}")
        print(sep)
        print(f"  {emoji} STATUT : {statut_rag} | Score : {score_qual:.1f}/100")
        if client_id:
            print(f"  Client  : {client_id}")
        print(f"\n{sep}")
        for ligne in commentaire.split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    def _sauvegarder_audit(
        self, audit_id, sous_branche, rapport,
        qualite, statut_rag, hash_md5, t_debut, client_id
    ) -> None:
        log = {
            'audit_id':     audit_id,
            'agent':        'A1_INGESTION_v2',
            'version':      '2.0',
            'timestamp':    t_debut.isoformat(),
            'sous_branche': sous_branche,
            'client_id':    client_id,
            'statut_rag':   statut_rag,
            'score_qual':   qualite['score_global'],
            'nb_lignes':    qualite['nb_lignes'],
            'hash_md5':     hash_md5,
            'mapping_applique': rapport.get('mapping_applique', False),
        }
        try:
            with open(self.audit_path / f"{audit_id}.json", 'w') as f:
                json.dump(log, f, indent=2, default=str)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# FONCTION UTILITAIRE — CRÉER UN MAPPING CLIENT
# ══════════════════════════════════════════════════════════════════════════════

def creer_mapping_client(
    client_id:    str,
    mapping:      Dict[str, str],
    config_path:  str = None,
) -> str:
    """
    Crée ou met à jour le fichier de mapping pour un client.

    USAGE :
    ────────
    creer_mapping_client(
        client_id = 'assurance_xyz',
        mapping   = {
            'NUM_POL':  'id_contrat',
            'AGE_CDT':  'age',
            'CRM':      'bonus_malus',
            'PUISS':    'puissance_fiscale',
        }
    )

    Paramètres
    ──────────
    client_id : str
        Identifiant unique du client.

    mapping : dict
        {colonne_client: colonne_actuaria}

    config_path : str, optionnel
        Chemin du dossier config.
        Par défaut : config centrale.

    Retourne
    ────────
    Chemin du fichier créé.
    """
    config  = _charger_config()
    dossier = Path(config_path or config.get('config_path',
        '/tmp/actuaria/config'))
    dossier.mkdir(parents=True, exist_ok=True)

    chemin = dossier / f"{client_id}_mapping.json"
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    print(f"✅ Mapping client '{client_id}' créé : {chemin}")
    print(f"   {len(mapping)} colonnes mappées :")
    for orig, cible in mapping.items():
        print(f"   {orig:<30} → {cible}")

    return str(chemin)


def verifier_tous_fichiers(base_path: str = None) -> None:
    """Vérifie la présence de tous les fichiers de données."""
    config = _charger_config()
    bp     = Path(base_path or config['data_path'])

    fichiers_attendus = {
        'non_vie': [
            'contrats_auto_70k.parquet', 'sinistres_auto.parquet',
            'contrats_mrh_70k.parquet',  'sinistres_mrh.parquet',
            'contrats_rcpro_70k.parquet','sinistres_rcpro.parquet',
        ],
        'vie': [
            'contrats_vie_indiv_70k.parquet', 'contrats_vie_coll_70k.parquet',
            'mouvements_vie.parquet', 'contrats_art39_70k.parquet',
            'contrats_art83_per_70k.parquet',
        ],
        'sante_prevoyance': [
            'contrats_sante_coll_70k.parquet', 'contrats_sante_indiv_70k.parquet',
            'contrats_prev_coll_70k.parquet',   'contrats_prev_indiv_70k.parquet',
            'sinistres_sante_prev.parquet',
        ],
    }

    print("VÉRIFICATION DES FICHIERS DE DONNÉES")
    print("=" * 50)
    total_ok = 0
    total    = 0

    for branche, fichiers in fichiers_attendus.items():
        print(f"\n  [{branche.upper()}]")
        for fichier in fichiers:
            chemin = bp / branche / fichier
            existe = chemin.exists()
            total += 1
            if existe:
                total_ok += 1
                taille = chemin.stat().st_size // 1024
                print(f"  ✅ {fichier:<45} ({taille:,} Ko)")
            else:
                print(f"  ❌ {fichier:<45} MANQUANT")

    print(f"\n  Score : {total_ok}/{total} fichiers présents")
    print("=" * 50)


if __name__ == '__main__':
    print("Agent A1 — Ingestion ActuarIA v2.0")
    print("Nouveautés : config centrale · mapping client · portabilité")
    print()
    print("Usage standard :")
    print("  agent_a1 = AgentA1Ingestion()")
    print("  result_a1 = agent_a1.run(branche='non_vie', fichier='contrats.parquet')")
    print()
    print("Usage avec client réel :")
    print("  creer_mapping_client('client_xyz', {'NUM_POL': 'id_contrat', ...})")
    print("  result_a1 = agent_a1.run(branche='non_vie', fichier='data.xlsx', client_id='client_xyz')")
