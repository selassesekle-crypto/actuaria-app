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
║  USAGE STANDARD (sous_branche DÉCLARÉE — A1 ne la devine plus) :            ║
║  agent_a1 = AgentA1Ingestion()                                             ║
║  result_a1 = agent_a1.run(branche='non_vie', sous_branche='auto',         ║
║                           fichier='contrats.parquet')                      ║
║                                                                              ║
║  USAGE AVEC CLIENT :                                                         ║
║  result_a1 = agent_a1.run(                                                 ║
║      branche      = 'non_vie',                                             ║
║      sous_branche = 'auto',                                                ║
║      fichier      = 'contrats_client.xlsx',                                ║
║      client_id    = 'client_xyz',                                          ║
║  )                                                                          ║
║                                                                              ║
║  AUTEUR    : ActuarIA v2.0                                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import numpy as np
import pandas as pd
from core.charts_tarif import glyphe_rag
from core.qualite_donnees import exiger_canal_sans_objet

try:
    from ..services.tarif_excel import export_excel_a1
    TARIF_EXCEL_OK_A1 = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.tarif_excel import export_excel_a1
        TARIF_EXCEL_OK_A1 = True
    except ImportError:
        TARIF_EXCEL_OK_A1 = False

# ⚠️⚠️ CONSTAT `a2/C15` — LE FILTRE GLOBAL D'AVERTISSEMENTS EST RETIRÉ.
# `warnings.filterwarnings('ignore')` posé ICI, au niveau module, s'appliquait
# au PROCESSUS ENTIER dès l'import : tout appelant de cet agent perdait les
# avertissements de TOUS ses modules, y compris ceux qu'il n'a jamais importés.
# *Une bibliothèque ne change pas l'état global du processus à l'import.*
#
# ⚠️ CE QU'IL CACHAIT, MESURÉ SUR UN RUN RÉEL (pipeline complet, 1 200 lignes) :
#     7x Pandas4Warning   `select_dtypes` — NOTRE code, rupture pandas 4
#     6x UserWarning       sklearn : « X does not have valid feature names »
#     3x FutureWarning     statsmodels : le calcul du BIC change apres 0.13
# ⚠️ Le 3e porte sur `bic`, PUBLIÉ dans les métriques d'A3 (trois sites) et au
# chapitre 1 du rapport signé. *Un nombre publié dont la définition change.*
#
# ⚠️ ET JE CORRIGE MON PROPRE SOUPÇON : je pensais y trouver des avertissements
# de NON-CONVERGENCE. Il n'y en a aucun sur ce portefeuille. Le mécanisme est
# réel, la trouvaille est ailleurs — *une hypothèse mesurée vaut mieux qu'une
# hypothèse plausible.*
#
# ⚠️ RIEN DE NOTRE CODE N'APPELLE `warnings.warn` : relevé sur tarification et
# core, zéro site. Ce qui remonte est donc TIERS, et peu volumineux.
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
                               'idpol', 'id_pol', 'num_pol', 'contract_id',
                               'id_client', 'client_id', 'id_assuré'],
    'id_sinistre':            ['id_claim', 'claim_id', 'num_sinistre', 'sinistre_id',
                               'id_sin', 'num_sin'],
    'nb_sinistres':           ['claimnb', 'nb_claims', 'sinistres', 'claim_count',
                               'nbre_sinistres', 'nb_sin', 'claim_nb',
                               'nombre_sinistres', 'freq', 'count_claims', 'sinistre_nb'],
    'cout_total_sinistres':   ['claimamount', 'montant_sinistres', 'cout_sinistres',
                               'claim_amount', 'montant', 'charge', 'cout_sinistre',
                               'claim_cost', 'montant_sinistre', 'charge_sinistre',
                               'indemnite', 'prestation'],
    'exposition':             ['exposure', 'expo', 'duree', 'duration', 'poids',
                               'annee_exposition', 'duree_contrat', 'years_exposed'],
    'annee_survenance':       ['annee', 'year', 'id_year', 'annee_sinistre',
                               'year_occ', 'occurrence_year', 'loss_year'],
    # ⚠️⚠️ `date_echeance` N'EST PAS `annee_survenance`, ET LES CONFONDRE
    # SERAIT GRAVE. L'une est la PERIODE DE COUVERTURE du contrat, l'autre
    # l'annee ou le sinistre est SURVENU. Le role `echeance` du plan sert a
    # distinguer un doublon d'un HISTORIQUE de renouvellement ; le rattacher a
    # l'annee de survenance dedoublonnerait sur la mauvaise grandeur.
    # ⚠️ LA VALEUR EST UN DISCRIMINANT OPAQUE : jamais parsee, jamais comparee,
    # jamais soustraite. Une annee (2024), une date (2024-03-01) ou un libelle
    # de periode conviennent egalement -- on ne fait qu'y distinguer des
    # groupes. *Cela evite d'introduire un contrat de date la ou une simple
    # cle de partition suffit.*
    # ⚠️ Aucun de ces 12 synonymes n'est revendique par une autre entree :
    # verifie contre les 114 synonymes existants avant ajout.
    'date_echeance':          ['echeance', 'date_renouvellement', 'date_effet',
                               'date_debut_couverture', 'exercice',
                               'annee_exercice', 'annee_souscription',
                               'millesime', 'periode', 'renewal_date',
                               'effective_date', 'policy_year'],
    'age':                    ['drimage', 'age_conducteur', 'age_cdt', 'age_driver',
                               'age_assure', 'age_client', 'age_assuré', 'driver_age'],
    'bonus_malus':            ['bonusmalus', 'crm', 'bm', 'bonus_malus_coeff',
                               'coefficient_bm', 'malus', 'coeff_bm'],
    'puissance_fiscale':      ['vehpower', 'puiss', 'puiss_fisc', 'puissance',
                               'cv_fiscaux', 'power', 'puissance_veh', 'veh_power'],
    'age_vehicule':           ['vehage', 'age_veh', 'anciennete_vehicule',
                               'vehicle_age', 'age_auto', 'veh_age', 'age_vehc'],
    'zone_geographique':      ['area', 'zone', 'region_risque', 'zone_geo',
                               'area_code', 'zone_code'],
    'region':                 ['region', 'departement', 'dept', 'localisation',
                               'commune', 'cp', 'code_postal'],
    'carburant':              ['vehgas', 'fuel', 'energie', 'motorisation',
                               'type_energie', 'veh_fuel'],
    'densite_population':     ['density', 'densite', 'population_density',
                               'pop_density', 'dens_pop'],
    'id_vehicule':            ['id_vehicle', 'vehicle_id', 'num_vehicule',
                               'veh_id', 'immatriculation'],
}


# ── Sous-branche : DÉCLARÉE, plus détectée (Phase 1) ──────────────────────────
# MOTS_CLES_DETECTION et _detecter_sous_branche SUPPRIMÉS. A1 ne devine plus la
# LoB : l'actuaire la déclare (run(sous_branche=...)), et le plan signé fait
# autorité en aval (A3/A4/A5). L'ancien repli étiquetait 'auto' par défaut quand
# aucun mot-clé ne matchait — silencieux pour l'aval — et il était de toute façon
# structurellement incapable de reconnaître une LoB neuve (décennale,
# marchandises transportées) : c'était le BLOQUANT B4 de l'audit V11 (RC Pro
# jamais détectée, sa spécialisation étant du code mort). A1 accepte désormais
# TOUTE sous-branche déclarée : c'est le plan qui la valide, pas un dict codé.
#
# Le périmètre Non-Vie reste gardé par BRANCHES_SUPPORTEES ci-dessous : les
# sous-branches Vie/Santé/Prévoyance/Épargne avaient été retirées le 11/07/2026
# (A1/A2 ne sont plus un « service data » mutualisé — les directions Vie/EP-RE et
# Santé-Prévoyance sont autonomes et ont leur propre traitement de données).

# Branches acceptées par cet agent — toute autre valeur est rejetée
# explicitement (fail loudly) plutôt que traitée silencieusement avec une
# configuration inadaptée. Empêche qu'un portefeuille Vie ou Santé soit
# ingéré par erreur dans le pipeline de tarification Non-Vie.
BRANCHES_SUPPORTEES = ('non_vie',)

FORMATS_SUPPORTES = ['.csv', '.xlsx', '.xls', '.parquet', '.json', '.txt']

SEUILS_QUALITE = {
    'completude_rouge': 80.0,
    'completude_ambre': 95.0,
    'doublons_rouge':    5.0,
    'doublons_ambre':    1.0,
    # Audit V4 point #9 — avant ce correctif, les aberrants actuariels
    # (§4.2) pénalisaient le score_global (jusqu'à -3 pts) mais n'avaient
    # AUCUN impact sur le statut RAG affiché, qui ne dépendait que de la
    # complétude et des doublons. Un fichier avec sinistres négatifs, âges
    # impossibles ou exposition nulle pouvait obtenir VERT.
    'aberrants_taux_rouge': 5.0,  # % de lignes affectées par 1 type → ROUGE
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
    # Usage standard — sous_branche DÉCLARÉE par l'actuaire (A1 ne devine plus)
    agent_a1 = AgentA1Ingestion()
    result_a1 = agent_a1.run(branche='non_vie', sous_branche='auto',
                             fichier='contrats.parquet')

    # Usage avec client réel
    agent_a1 = AgentA1Ingestion()
    result_a1 = agent_a1.run(
        branche      = 'non_vie',
        sous_branche = 'auto',
        fichier      = 'contrats_client.xlsx',
        client_id    = 'assurance_xyz',
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

        # ⚠️ INSTANCIER N'ÉCRIT PAS SUR LE DISQUE. Ces deux dossiers étaient
        # créés ici : importer puis construire A1 suffisait à faire naître
        # /tmp/actuaria/{audit,config}, y compris quand aucun run n'avait
        # lieu. Ils sont désormais créés PAR CELUI QUI ÉCRIT, juste avant
        # d'écrire (_sauvegarder_audit, mapping suggéré) — même effet pour
        # qui produit un fichier, aucun effet pour qui ne fait que construire.

        if self.verbose:
            logger.info(f"Agent A1 Ingestion v2 initialisé | base={self.base_path}")

    def run(
        self,
        branche:   str = 'non_vie',
        sous_branche: str = None,   # Phase 1 : déclarée par l'actuaire, plus devinée
        fichier:   str = 'contrats_auto_70k.parquet',
        client_id: str = None,
        dataframe  = None,
        plan       = None,   # PlanTarifaire signé — l'identité du contrat s'y déclare
        #: ⚠️⚠️ LE CANAL DE SIGNATURE QUALITE — etape 3 du chantier 1-B.
        #: Meme nom, meme sens que sur le chemin declaratif. Il n'a PAS ENCORE
        #: d'objet ici : A1 SCORE la qualite (statut RAG) mais n'exclut rien,
        #: et la couche `controler_qualite` n'est pas branchee (`qualite/C4`).
        #: Il LEVE plutot que d'avaler un nom en silence.
        qualite_validee_par = None,
    ) -> Dict[str, Any]:
        """
        Pipeline d'ingestion complet.

        ⚠️⚠️ `qualite_validee_par` : LE CANAL EXISTE, IL N'A PAS ENCORE D'OBJET.
        A1 mesure la qualité et publie un statut RAG, mais **il n'exclut aucune
        ligne** — mesuré le 01/09 : 600 fréquences négatives sur 10 000 le font
        virer au ROUGE, et les 10 000 lignes ressortent. Il n'y a donc aucun
        blocage à lever, et une signature ne validerait rien. Elle LÈVE
        `SignatureSansObjet` plutôt que d'avaler un nom en silence.
        **L'étape qui lui donnera un objet est 1-B**, le branchement de la
        couche qualité au chemin agent — et elle déplace un prix. Pour tarifer
        AVEC la couche aujourd'hui : `pipeline_tarifaire.pipeline_complet`.

        Paramètres
        ──────────
        branche : str
            'non_vie' — seule valeur acceptée (Direction Non-Vie :
            auto · MRH · RC Pro). Toute autre branche est rejetée :
            les directions Vie/EP-RE et Santé-Prévoyance sont autonomes
            et disposent de leur propre traitement de données.

        sous_branche : str
            Sous-branche DÉCLARÉE par l'actuaire : 'auto', 'mrh', 'rcpro',
            'decennale', 'marchandises_transportees'… A1 ne la DEVINE plus
            (Phase 1 : MOTS_CLES_DETECTION supprimé). Obligatoire — absente,
            l'agent échoue proprement plutôt que d'étiqueter par défaut.
            Propagée telle quelle dans result['branche'], que A2 transmet à
            A3/A4/A5 ; le plan signé fait autorité en aval.

        fichier : str
            Nom du fichier de données (avec extension).
            Formats : .csv · .xlsx · .xls · .parquet · .json · .txt

        client_id : str, optionnel
            Identifiant unique du client.
            Ex : 'assurance_xyz', 'cabinet_abc'
            Si fourni → charge le mapping depuis
            config/client_id_mapping.json
        """
        # ⚠️ LE CANAL REFUSE AVANT TOUT, MEME AVANT L'HORODATAGE. Un refus
        # tardif aurait laissé une trace d'audit d'un run qui n'a pas eu lieu.
        exiger_canal_sans_objet(qualite_validee_par, 'A1.run')

        t_debut  = datetime.now()
        audit_id = f"A1_{t_debut.strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"[{audit_id}] Agent A1 v2 démarré | {fichier} | client={client_id}")

        rapport = {'etapes': [], 'alertes': [], 'mapping_applique': False}

        # ── GARDE-FOU DE PÉRIMÈTRE (11/07/2026) ───────────────────────────────
        # A1 est un agent de la Direction Non-Vie. Les directions Vie/EP-RE et
        # Santé-Prévoyance sont autonomes et disposent de leur propre service
        # de données : elles ne doivent plus passer par A1/A2. On échoue
        # explicitement plutôt que de traiter silencieusement un portefeuille
        # hors périmètre avec une configuration Non-Vie inadaptée.
        if branche not in BRANCHES_SUPPORTEES:
            _msg = (
                f"Branche '{branche}' hors périmètre. A1 est un agent de la "
                f"Direction NON-VIE et n'accepte que {list(BRANCHES_SUPPORTEES)}. "
                f"Les directions Vie/EP-RE et Santé-Prévoyance disposent de leur "
                f"propre traitement de données depuis leur passage en autonomie."
            )
            logger.error(f"[{audit_id}] {_msg}")
            return {
                'success':    False,
                'dataframe':  pd.DataFrame(),
                'branche':    branche,
                'statut_rag': 'ROUGE',
                'score_qual': 0,
                'audit_id':   audit_id,
                'erreur':     _msg,
                'commentaire': f"❌ ERREUR A1 : {_msg}",
            }

        # ── PHASE 1 : LA SOUS-BRANCHE EST DÉCLARÉE, PLUS DEVINÉE ──────────────
        # A1 ne détecte plus (MOTS_CLES_DETECTION supprimé) : l'actuaire déclare
        # sa LoB. Absente → erreur propre, JAMAIS de repli : l'ancien repli
        # étiquetait 'auto' par défaut, en silence pour tout l'aval.
        if not sous_branche:
            _msg = (
                "A1.run exige sous_branche (ex. 'auto', 'mrh', 'rcpro', "
                "'decennale') : A1 ne détecte plus la sous-branche (Phase 1, "
                "MOTS_CLES_DETECTION supprimé). L'actuaire la déclare explicitement."
            )
            logger.error(f"[{audit_id}] {_msg}")
            return {
                'success':    False,
                'dataframe':  pd.DataFrame(),
                'branche':    branche,
                'statut_rag': 'ROUGE',
                'score_qual': 0,
                'audit_id':   audit_id,
                'erreur':     _msg,
                'commentaire': f"❌ ERREUR A1 : {_msg}",
            }

        try:
            # ── ÉTAPE 1 : CHARGEMENT ──────────────────────────────────────────
            # Si un DataFrame est fourni directement → on saute le chargement
            # fichier. Permet l'utilisation depuis Streamlit, FastAPI, etc.
            if dataframe is not None:
                # NOTE (11/07/2026) : un 'import pandas as pd' LOCAL figurait
                # ici. Python le traitait comme une liaison locale valable pour
                # TOUTE la fonction run() — masquant le pd importé au niveau du
                # module (l.38). Conséquence : toute référence à pd située
                # avant cette ligne, ou exécutée en mode fichier (dataframe=None,
                # l'import local n'ayant alors jamais lieu), levait un
                # UnboundLocalError — y compris le bloc except final qui
                # construit pd.DataFrame() pour son dict d'erreur. L'import
                # local, redondant, est supprimé.
                if not isinstance(dataframe, pd.DataFrame):
                    raise ValueError("Le paramètre 'dataframe' doit être un pd.DataFrame.")
                df = dataframe.copy()
                rapport['etapes'].append('dataframe_direct')
                logger.info(f"DataFrame direct : {df.shape} | sous-branche déclarée : {sous_branche}")
            else:
                df = self._charger_fichier(fichier, branche)
                rapport['etapes'].append('chargement')
                logger.info(f"Chargé : {df.shape} | sous-branche déclarée : {sous_branche}")

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

            # ── ÉTAPE 2bis : COERCITION DE TYPES ─────────────────────────────
            # Force les colonnes numériques/date attendues à leur type correct.
            # Sans cette étape, une colonne 'age' lue comme chaîne depuis un
            # CSV mal formaté passerait silencieusement en aval.
            # errors='coerce' transforme les valeurs non convertibles en NaN
            # (détectées ensuite par le contrôle de complétude).
            df, rapport_coercition = self._forcer_types(df)
            rapport['etapes'].append('coercition_types')
            rapport['coercition_types'] = rapport_coercition
            if rapport_coercition.get('alertes'):
                rapport['alertes'].extend(rapport_coercition['alertes'])

            # ── ÉTAPE 3 : VALIDATION QUALITÉ ─────────────────────────────────
            qualite = self._valider_qualite(df, plan)
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

            # ── Audit trail — traçabilité ACPR ────────────────────────────────
            _audit_trail_a1 = {
                'agent': 'A1_INGESTION', 'version': '2.0', 'audit_id': audit_id,
                'timestamp': t_debut.isoformat(), 'branche': sous_branche,
                'statut_rag': statut_rag,
                'score_qualite': score_qual,
                'nb_types_aberrants': qualite.get('nb_types_aberrants', 0),
                'colonnes_forcees': rapport.get('coercition_types', {}).get('colonnes_forcees', []),
                'hash_md5': hash_md5,
            }

            _tmp_a1 = {
                'success': True, 'statut_rag': statut_rag, 'branche': sous_branche,
                'qualite': qualite, 'rapport': rapport, 'audit_id': audit_id,
                'hash_md5': hash_md5, 'commentaire': commentaire,
            }
            _excel_a1 = b''
            if TARIF_EXCEL_OK_A1:
                try:
                    _excel_a1 = export_excel_a1(_tmp_a1, audit_id)
                    if _excel_a1:
                        logger.info(f"[{audit_id}] Excel A1 : {len(_excel_a1):,} bytes")
                except Exception as e_xl:
                    logger.warning(f"Excel A1 échoué : {e_xl}")

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
                'excel_bytes':  _excel_a1,
                'word_bytes':   b'',
                'pdf_bytes':    b'',
                'audit_trail':  _audit_trail_a1,
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
        # ── PÉRIMÈTRE — C'EST ICI QUE L'INGESTION A LIEU ──────────────────────
        # Le garde-fou de run() ne voit que l'ARGUMENT `branche`. Tant que ce
        # chargeur énumérait 'vie' et 'sante_prevoyance' en repli, un fichier
        # posé dans data/vie/ était chargé sous branche='non_vie' : la garde
        # portait sur une chaîne, l'acte portait sur un chemin. La liste des
        # dossiers explorés DÉRIVE désormais de BRANCHES_SUPPORTEES.
        if branche not in BRANCHES_SUPPORTEES:
            raise ValueError(
                f"Branche '{branche}' hors périmètre : A1 ne lit que "
                f"{list(BRANCHES_SUPPORTEES)}."
            )
        branches_ordre = [branche] + [
            b for b in BRANCHES_SUPPORTEES if b != branche
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
            # « Absent » et « présent hors périmètre » ne sont pas la même
            # chose. Dire le second évite de faire chercher un fichier qui
            # est là, dans un dossier que l'on REFUSE de lire.
            hors = sorted(
                d.name for d in self.base_path.glob('*')
                if d.is_dir() and d.name not in branches_ordre
                and (d / fichier).exists()
            ) if self.base_path.exists() else []
            if hors:
                raise FileNotFoundError(
                    f"Fichier '{fichier}' TROUVÉ dans {hors} — HORS PÉRIMÈTRE, "
                    f"donc NON chargé. A1 est un agent de la Direction Non-Vie "
                    f"et ne lit que {list(BRANCHES_SUPPORTEES)} ; les "
                    f"directions Vie/EP-RE et Santé-Prévoyance disposent de "
                    f"leur propre traitement de données depuis le 11/07/2026."
                )
            raise FileNotFoundError(
                f"Fichier '{fichier}' non trouvé dans {self.base_path}. "
                f"Branches cherchées : {branches_ordre}"
            )

        # Phase 1 : plus de détection ici — la sous-branche est déclarée par
        # l'actuaire et portée par run(). _charger_fichier ne fait que charger.
        return df

    def _lire_fichier(self, chemin: Path, nom_onglet: str = None) -> pd.DataFrame:
        """Lit un fichier selon son EXTENSION (jamais son contenu). Une extension
        inconnue lève une erreur PROPRE nommant les formats acceptés — jamais un
        crash pandas cryptique. Formats : voir FORMATS_SUPPORTES."""
        ext = chemin.suffix.lower()
        if ext == '.parquet':
            return pd.read_parquet(chemin)                     # exige pyarrow/fastparquet
        if ext in ('.xlsx', '.xls'):
            # sheet_name : la PREMIÈRE feuille par défaut (0). ⚠ sheet_name=None
            # rendrait un DICT de toutes les feuilles, pas un DataFrame (ancien
            # bug). Le moteur est laissé à pandas : openpyxl pour .xlsx, xlrd pour
            # .xls (forcer 'openpyxl' cassait .xls).
            return pd.read_excel(
                chemin, sheet_name=(nom_onglet if nom_onglet is not None else 0))
        if ext in ('.csv', '.txt'):
            # sep=None + engine='python' : pandas DÉTECTE le séparateur (, ; \t)
            # via csv.Sniffer. .txt est traité comme un CSV (détection identique).
            return pd.read_csv(chemin, sep=None, engine='python')
        if ext == '.json':
            return pd.read_json(chemin)
        raise ValueError(
            f"format non supporté : {ext} — formats acceptés : "
            f"{', '.join(e.lstrip('.') for e in FORMATS_SUPPORTES)}.")

    # (_detecter_sous_branche SUPPRIMÉE en Phase 1 : A1 ne devine plus la LoB.
    #  Elle scorait les colonnes contre MOTS_CLES_DETECTION et, à défaut de tout
    #  mot-clé, repliait sur 'auto' avec un WARNING — un étiquetage par défaut
    #  invisible pour l'aval, et incapable par construction de reconnaître une LoB
    #  neuve. La sous-branche est désormais DÉCLARÉE : run(sous_branche=...).)

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
                    self.config_path_dir.mkdir(parents=True, exist_ok=True)
                    # ⚠️ `ensure_ascii=False` SANS encoding écrivait selon la
                    # locale : un nom de colonne accentué (« id_assuré ») fait
                    # lever cp1252 sous Windows, et l'échec partait dans le
                    # `pass` ci-dessous. Le format est UTF-8, il est déclaré.
                    with open(chemin_suggere, 'w', encoding='utf-8') as f:
                        json.dump(mapping_suggere, f, indent=2, ensure_ascii=False)
                    logger.info(
                        f"Mapping suggéré sauvegardé : {chemin_suggere}\n"
                        f"→ Renommer en '{client_id}_mapping.json' après validation"
                    )
                    mapping_info['mapping_source'] = f"SUGGÉRÉ (à valider) : {chemin_suggere}"
                except Exception as e:
                    logger.warning(
                        f"Mapping suggéré NON écrit ({chemin_suggere}) : "
                        f"{type(e).__name__} : {e}"
                    )
                    mapping_info['mapping_source'] = (
                        f"SUGGÉRÉ mais NON ÉCRIT ({type(e).__name__}) — "
                        f"la suggestion n'existe que dans ce résultat"
                    )

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

    def _forcer_types(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """
        Coercition explicite des types de données.

        Force les colonnes numériques et date attendues à leur type correct,
        avec errors='coerce' : les valeurs non convertibles deviennent NaN
        (détectées ensuite par le contrôle de complétude de _valider_qualite).

        Sans cette étape, une colonne 'age' lue comme chaîne de caractères
        depuis un CSV mal formaté (ex. "trente-cinq" au lieu de 35) passerait
        silencieusement en aval, faussant tout contrôle de plage numérique.

        Réf. : Recommandation P3 — Certification actuarielle v3 (10/07/2026).
        """
        rapport = {'colonnes_forcees': [], 'nb_valeurs_perdues': {}, 'alertes': []}

        # Colonnes numériques attendues (fréquence, coût, exposition, âge...)
        cols_numeriques = [
            'age', 'age_conducteur', 'age_entree', 'bonus_malus',
            'nb_sinistres', 'nb_sinistres_rc', 'nb_sinistres_dommages',
            'cout_total_sinistres', 'cout_moyen_attendu',
            'prime_pure', 'prime_commerciale', 'exposition',
            'kilometrage_annuel', 'valeur_venale', 'ca_annuel_eur',
            'puissance_fiscale', 'surface_m2',
        ]
        for col in cols_numeriques:
            if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                n_avant = df[col].notna().sum()
                df[col] = pd.to_numeric(df[col], errors='coerce')
                n_apres = df[col].notna().sum()
                n_perdu = n_avant - n_apres
                rapport['colonnes_forcees'].append(col)
                if n_perdu > 0:
                    rapport['nb_valeurs_perdues'][col] = int(n_perdu)
                    rapport['alertes'].append(
                        f"Coercition '{col}' → numérique : {n_perdu} valeur(s) "
                        f"non convertible(s) transformée(s) en NaN."
                    )
                    logger.warning(
                        f"[Coercition types] '{col}' : {n_perdu} valeurs "
                        f"perdues lors de la conversion numérique."
                    )

        # Colonnes date attendues
        cols_date = [
            'date_souscription', 'date_survenance',
            'date_mouvement', 'date_evaluation',
        ]
        for col in cols_date:
            if col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[col]):
                n_avant = df[col].notna().sum()
                df[col] = pd.to_datetime(df[col], errors='coerce')
                n_apres = df[col].notna().sum()
                n_perdu = n_avant - n_apres
                rapport['colonnes_forcees'].append(col)
                if n_perdu > 0:
                    rapport['nb_valeurs_perdues'][col] = int(n_perdu)
                    rapport['alertes'].append(
                        f"Coercition '{col}' → date : {n_perdu} valeur(s) "
                        f"non convertible(s) transformée(s) en NaT."
                    )
                    logger.warning(
                        f"[Coercition types] '{col}' : {n_perdu} valeurs "
                        f"perdues lors de la conversion date."
                    )

        if rapport['colonnes_forcees']:
            logger.info(
                f"[Coercition types] {len(rapport['colonnes_forcees'])} "
                f"colonne(s) forcée(s) : {rapport['colonnes_forcees']}"
            )

        return df, rapport

    def _valider_qualite(self, df: pd.DataFrame, plan=None) -> Dict:
        """
        Calcule les métriques de qualité du DataFrame.

        Contrôles effectués :
        1. Complétude (valeurs manquantes)
        2. Doublons
        3. Exposition ∈ [0, 1]
        4. Valeurs aberrantes actuarielles (contrôles du module)
           - Sinistres : nb_sinistres ≥ 0, cout_total_sinistres ≥ 0
           - Âge conducteur : 16 ≤ age ≤ 99 (borne basse : art. R. 221-5
             du code de la route ; borne haute : convention du module)
           - Exposition : 0 < exposition ≤ 1 (fraction d'année)
           - Montants : prime_pure > 0 si disponible
        """
        n = len(df)

        # ── 1. Complétude ──────────────────────────────────────────────────────
        taux_complet = (1 - df.isnull().mean()).mean() * 100

        # ── 2. Doublons ────────────────────────────────────────────────────────
        # ⚠️⚠️ L'IDENTITÉ D'UN CONTRAT SE DÉCLARE, ELLE NE SE DEVINE PAS.
        # Cette ligne prenait `[c for c in df.columns if 'id' in c.lower() or
        # 'pol' in c.lower()]` puis LE PREMIER de la liste. Mesuré sur les
        # vingt plans du dépôt : QUATRE FACTEURS TARIFAIRES sont attrapés par
        # cette heuristique — `forme_juridique` et `caution_solidaire`
        # contiennent « id », `antecedents_accidents_3ans` aussi. L'ordre des
        # colonnes vient du fichier client : le dédoublonnage pouvait donc se
        # faire sur une forme juridique. Cela marchait par chance, parce que
        # l'identifiant est d'ordinaire la première colonne.
        # ⚠️ ET LE MÉCANISME EXISTAIT DÉJÀ, ENDORMI : `PlanTarifaire` porte
        # `identifiant_contrat` depuis toujours et `core/qualite_donnees.py`
        # s'en sert (règle 1). A1 était le SEUL des six agents dont `run()` ne
        # recevait pas le plan — c'est-à-dire exactement l'agent qui devinait.
        col_id  = getattr(plan, 'identifiant_contrat', None) if plan else None
        col_ech = getattr(plan, 'echeance', None) if plan else None
        source_identifiant = 'plan'
        if not (col_id and col_id in df.columns):
            col_id = next((c for c in df.columns
                           if 'id' in c.lower() or 'pol' in c.lower()), None)
            source_identifiant = 'devinee' if col_id else 'aucune'
        if not (col_ech and col_ech in df.columns):
            col_ech = None

        # ⚠️ UN DOUBLON N'EST PAS UNE ÉCHÉANCE. Le même contrat observé sur
        # trois exercices donne trois lignes de même identifiant : ce n'est pas
        # une redondance, c'est un historique. Mesuré : un historique de
        # renouvellement sur 3 ans porte ~67 % de « doublons » pour un seuil
        # ROUGE à 5 % — le fichier était refusé avant d'être lu, et c'est
        # exactement la donnée qu'exige l'estimation d'une élasticité.
        if col_id and col_ech:
            nb_doublons = df.duplicated(subset=[col_id, col_ech]).sum()
            granularite = 'un contrat par échéance'
        elif col_id:
            nb_doublons = df.duplicated(subset=[col_id]).sum()
            granularite = 'un contrat'
        else:
            nb_doublons = df.duplicated().sum()
            granularite = 'indéterminée — aucun identifiant'
        taux_doublons = nb_doublons / max(n, 1) * 100

        # ⚠️ LE REPLI RESTE LÉGITIME — aucun des vingt plans ne déclare
        # d'identifiant — MAIS IL NE SE TAIT PLUS. Un lecteur doit savoir que
        # l'identité du contrat n'a pas été déclarée, donc que le compte de
        # doublons repose sur un nom de colonne deviné.
        note_identite = {
            'plan': (f"Identité du contrat DÉCLARÉE au plan : « {col_id} »"
                     + (f", échéance « {col_ech} »." if col_ech else
                        ". Aucune échéance déclarée : deux lignes de même "
                        "identifiant restent comptées comme un doublon.")),
            'devinee': (f"⚠ Identité du contrat DEVINÉE : « {col_id} » (nom "
                        f"contenant « id » ou « pol »). Non déclarée au plan "
                        f"— déclarer `identifiant_contrat` la rend opposable."),
            'aucune': ("⚠ Aucun identifiant de contrat : le dédoublonnage "
                       "porte sur la ligne entière."),
        }[source_identifiant]

        # ── 3. Exposition ∈ ]0, 1] ────────────────────────────────────────────
        # ⚠️⚠️ CORRECTIF — constat `a1/C4`. `between(0, 1)` est INCLUSIF des
        # deux bornes : une exposition NULLE comptait comme saine, et
        # `expo_ok_pct` valait 100,0 sur un portefeuille où le contrôle 4d
        # signalait au même instant `exposition_nulle_ou_negative`.
        # **Deux verdicts contradictoires dans la même fonction** — le score
        # disait sain, l'alerte disait aberrant, et rien ne les réconciliait.
        # La docstring, elle, était juste depuis le début : « Exposition :
        # 0 < exposition ≤ 1 ». **C'est le code qui contredisait le contrat.**
        if 'exposition' in df.columns:
            expo_ok = (df['exposition'].between(0, 1, inclusive='right')).mean() * 100
        else:
            expo_ok = 100.0

        # ── 4. Valeurs aberrantes actuarielles ────────────────────────────────
        # ⚠️ AUCUNE NORME EXTERNE N'EST INVOQUÉE ICI. Ces lignes citaient
        # « IA France (2019) §4.2 » — la forme courte du même document non
        # sourcé que la purge de ce lot retire ailleurs. Ce sont des contrôles
        # de plausibilité propres au module.
        aberrants = {}
        alertes_aberrants = []

        # 4a. Sinistres négatifs — impossible physiquement
        for col_sin in ['nb_sinistres', 'nb_sinistres_rc', 'nb_sinistres_dommages']:
            if col_sin in df.columns:
                n_neg = int((df[col_sin] < 0).sum())
                if n_neg > 0:
                    aberrants[col_sin + '_negatifs'] = n_neg
                    alertes_aberrants.append(
                        f"{col_sin} : {n_neg} valeur(s) négative(s) — impossible."
                    )

        # 4b. Coûts négatifs
        # ⚠️⚠️ CORRECTIF — constat `a1/C3`. La docstring déclare « Montants :
        # **prime_pure > 0** si disponible », et le code testait `< 0` : une
        # prime pure NULLE traversait le contrôle sans un mot (mesuré : 100
        # lignes à `prime_pure = 0` → `aberrants = aucun`).
        # ⚠️ ET LES QUATRE COLONNES NE PARTAGENT PAS LE MÊME CONTRAT :
        # `cout_total_sinistres = 0` est NORMAL — un contrat sans sinistre —
        # tandis qu'une prime pure nulle signifie un coût espéré nul, ce que
        # la docstring exclut. Les traiter en bloc, c'était appliquer à l'une
        # le contrat de l'autre.
        for col_cout in ['cout_total_sinistres', 'cout_moyen_attendu',
                         'prime_commerciale']:
            if col_cout in df.columns:
                n_neg = int((df[col_cout] < 0).sum())
                if n_neg > 0:
                    aberrants[col_cout + '_negatifs'] = n_neg
                    alertes_aberrants.append(
                        f"{col_cout} : {n_neg} valeur(s) négative(s)."
                    )
        # `prime_pure` : le contrat DÉCLARÉ est « > 0 », on le teste tel quel.
        if 'prime_pure' in df.columns:
            n_np = int((df['prime_pure'] <= 0).sum())
            if n_np > 0:
                aberrants['prime_pure_non_positive'] = n_np
                alertes_aberrants.append(
                    f"prime_pure : {n_np} valeur(s) ≤ 0 — une prime pure nulle "
                    f"signifie un coût espéré nul, ce que le contrôle déclare "
                    f"impossible (« prime_pure > 0 »)."
                )

        # 4c. Âge hors plage [16, 99] — UNE BORNE RÉGLEMENTAIRE, UNE CONVENTION
        # ⚠️ L'ARTICLE CITÉ ÉTAIT LE MAUVAIS, ET LA PARENTHÈSE ÉTAIT FAUSSE.
        # Vérifié au texte (Légifrance) : l'art. R. 221-1 ne porte AUCUNE
        # condition d'âge — il énumère les catégories de permis. Les âges sont
        # à l'art. R. 221-5 : 16 ans pour les catégories A1 et B1, 17 ans pour
        # la catégorie B elle-même (et non pour la seule conduite
        # accompagnée, comme le disait la parenthèse), 18, 21 et 24 ans pour
        # les autres catégories.
        # ⚠️⚠️ ET AUCUN TEXTE NE FIXE D'ÂGE MAXIMAL. Le 99 n'est PAS
        # réglementaire : c'est une borne de plausibilité choisie par le
        # module. La citer comme du droit lui donnait une autorité qu'elle
        # n'a pas — c'est exactement ce que cet audit traque. La borne basse
        # de 16 ans reste, elle, celle des catégories A1/B1.
        for col_age in ['age', 'age_conducteur']:
            if col_age in df.columns:
                n_age = int((~df[col_age].between(16, 99)).sum())
                if n_age > 0:
                    aberrants[col_age + '_hors_plage'] = n_age
                    alertes_aberrants.append(
                        f"{col_age} : {n_age} valeur(s) hors [16, 99] "
                        f"(16 = âge du permis A1/B1, art. R. 221-5 du code de "
                        f"la route ; 99 = borne de plausibilité du module, "
                        f"aucun âge maximal n'est fixé par un texte). "
                        f"Min={df[col_age].min():.0f} Max={df[col_age].max():.0f}."
                    )

        # 4d. Exposition strictement positive
        if 'exposition' in df.columns:
            n_expo_nul = int((df['exposition'] <= 0).sum())
            if n_expo_nul > 0:
                aberrants['exposition_nulle_ou_negative'] = n_expo_nul
                alertes_aberrants.append(
                    f"exposition : {n_expo_nul} valeur(s) ≤ 0 — "
                    "biais GLM Poisson via l'offset log(exposition)."
                )

        # 4e. Incohérence nb_sinistres > 0 ET cout = 0
        if 'nb_sinistres' in df.columns and 'cout_total_sinistres' in df.columns:
            n_incoh = int(
                ((df['nb_sinistres'] > 0) & (df['cout_total_sinistres'] == 0)).sum()
            )
            if n_incoh > 0:
                aberrants['incoh_sin_sans_cout'] = n_incoh
                alertes_aberrants.append(
                    f"{n_incoh} contrat(s) avec sinistres mais coût = 0 "
                    "— biais GLM Gamma."
                )

        # ── Score global — intègre la qualité actuarielle ─────────────────────
        # Pénalité aberrants : -5 points par type d'anomalie, max -20
        penalite_aberrants = min(len(aberrants) * 5.0, 20.0)
        score = min(
            taux_complet * 0.45
            + (100 - taux_doublons) * 0.25
            + expo_ok * 0.15
            + (100 - penalite_aberrants) * 0.15,
            100.0
        )

        return {
            'nb_lignes':           n,
            'nb_colonnes':         len(df.columns),
            'taux_completude':     round(taux_complet, 2),
            'nb_doublons':         int(nb_doublons),
            'taux_doublons':       round(taux_doublons, 2),
            # ⚠️ SUR QUOI LE COMPTE A ÉTÉ FAIT — publié avec le compte. Un
            # taux de doublons ne se lit pas sans savoir ce qui identifie une
            # ligne, ni si cette identité a été déclarée ou devinée.
            'identifiant_contrat': col_id,
            'source_identifiant':  source_identifiant,
            'echeance':            col_ech,
            'granularite':         granularite,
            'note_identite':       note_identite,
            'expo_ok_pct':         round(expo_ok, 2),
            'score_global':        round(score, 2),
            'colonnes':            df.columns.tolist(),
            # Valeurs aberrantes actuarielles — contrôles du module
            'aberrants':           aberrants,
            'nb_types_aberrants':  len(aberrants),
            'alertes_aberrants':   alertes_aberrants,
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
        """
        Statut RAG basé sur complétude, doublons ET aberrants actuariels.

        AVANT (audit V4 point #9) : seuls la complétude et les doublons
        déterminaient le statut. Les aberrants actuariels détectés en
        §4 (sinistres négatifs, âges impossibles, exposition nulle,
        incohérences sinistre/coût) ne pesaient que sur score_global
        (max -3 pts sur 100) sans jamais empêcher un statut VERT.

        APRÈS : la présence d'au moins un type d'anomalie plafonne le
        statut à AMBRE. Si un type d'anomalie affecte plus de
        `aberrants_taux_rouge` % des lignes, le statut passe à ROUGE —
        une proportion significative de données actuariellement
        impossibles ne peut pas être couverte par un simple avertissement.
        """
        c = qualite['taux_completude']
        d = qualite['taux_doublons']
        n = max(qualite.get('nb_lignes', 1), 1)
        aberrants = qualite.get('aberrants', {})
        n_types_aberrants = qualite.get('nb_types_aberrants', 0)
        # Taux du type d'anomalie le plus fréquent (évite le double-comptage
        # d'une même ligne affectée par plusieurs contrôles simultanément)
        taux_aberrant_max = (
            max(aberrants.values()) / n * 100 if aberrants else 0.0
        )

        if (c < SEUILS_QUALITE['completude_rouge']
                or d > SEUILS_QUALITE['doublons_rouge']
                or taux_aberrant_max > SEUILS_QUALITE['aberrants_taux_rouge']):
            return 'ROUGE'
        elif (c < SEUILS_QUALITE['completude_ambre']
                or d > SEUILS_QUALITE['doublons_ambre']
                or n_types_aberrants > 0):
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
        emoji = glyphe_rag(statut_rag)

        n1 = (
            f"{emoji} INGESTION — {statut_rag}\n"
            f"Sous-branche  : {sous_branche}\n"
            f"Client        : {client_id or 'Standard'}\n"
            f"Lignes        : {qualite['nb_lignes']:,}\n"
            f"Colonnes      : {qualite['nb_colonnes']}\n"
            f"Complétude    : {qualite['taux_completude']:.1f}%\n"
            f"Doublons      : {qualite['nb_doublons']:,} ({qualite['taux_doublons']:.2f}%)\n"
            # ⚠️ UN TAUX DE DOUBLONS NE SE LIT PAS SANS SON ASSIETTE. Sur quoi
            # deux lignes sont-elles jugées identiques, et cette identité
            # a-t-elle été déclarée au plan ou devinée d'un nom de colonne ?
            # Le compte seul laissait croire à une mesure, sans dire de quoi.
            f"Granularité   : {qualite.get('granularite', '?')}\n"
            f"{qualite.get('note_identite', '')}\n"
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
        emoji = glyphe_rag(statut_rag)
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
        chemin = self.audit_path / f"{audit_id}.json"
        try:
            self.audit_path.mkdir(parents=True, exist_ok=True)
            with open(chemin, 'w') as f:
                json.dump(log, f, indent=2, default=str)
        except Exception as e:
            _msg = (
                f"Audit trail NON persisté ({chemin}) : "
                f"{type(e).__name__} : {e}. La trace ACPR de ce run n'existe "
                f"que dans le résultat en mémoire."
            )
            logger.warning(f"[{audit_id}] {_msg}")
            rapport.setdefault('alertes', []).append(_msg)


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


# ── verifier_tous_fichiers SUPPRIMÉE (01/09/2026) ─────────────────────────────
# 1 définition, 0 appel dans tout le dépôt (AST) -- et elle imprimait la
# présence de 10 fichiers Vie et Santé-Prévoyance, hors du périmètre de A1
# depuis le 11/07/2026. Un inventaire mort qui annonce ce que cet agent
# REFUSE de lire ne rend pas un service : il décrit un autre logiciel.


if __name__ == '__main__':
    print("Agent A1 — Ingestion ActuarIA v2.0")
    print("Nouveautés : config centrale · mapping client · portabilité")
    print()
    print("Usage standard :")
    print("  agent_a1 = AgentA1Ingestion()")
    print("  result_a1 = agent_a1.run(branche='non_vie', sous_branche='auto',")
    print("                           fichier='contrats.parquet')")
    print()
    print("Usage avec client réel :")
    print("  creer_mapping_client('client_xyz', {'NUM_POL': 'id_contrat', ...})")
    print("  result_a1 = agent_a1.run(branche='non_vie', sous_branche='auto',")
    print("                           fichier='data.xlsx', client_id='client_xyz')")
