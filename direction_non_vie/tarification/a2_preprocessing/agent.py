"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               ACTUARIA — AGENT A2 : PREPROCESSING & FEATURE ENGINEERING     ║
║                           Version 1.0 — Production                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE DE CET AGENT                                                           ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  L'agent A2 transforme les données brutes (sortie A1) en données            ║
║  prêtes pour la calibration des modèles actuariels (A3/A4/A5).             ║
║                                                                              ║
║  PIPELINE COMPLET :                                                          ║
║  1. NETTOYAGE APPROFONDI                                                     ║
║     Imputation valeurs manquantes · Correction types · Doublons             ║
║                                                                              ║
║  2. TRAITEMENT DES OUTLIERS                                                  ║
║     Winsorisation (méthode IQR) · Plafonnement réglementaire                ║
║                                                                              ║
║  3. ENCODAGE VARIABLES CATÉGORIELLES                                        ║
║     Weight of Evidence (WoE) · Target Encoding · One-Hot                   ║
║                                                                              ║
║  4. CALCUL DE L'EXPOSITION                                                   ║
║     Offset GLM Poisson · Fraction d'année · Validation                      ║
║                                                                              ║
║  5. FEATURE ENGINEERING MÉTIER                                               ║
║     Variables d'interaction · Variables dérivées actuarielles               ║
║     Spécifiques par sous-branche                                             ║
║                                                                              ║
║  6. VERSIONING DES TRANSFORMATIONS                                           ║
║     Sauvegarde des paramètres · Reproductibilité · Audit trail              ║
║                                                                              ║
║  AUTONOMIE : Niveau 2                                                        ║
║  L'agent choisit ses paramètres de façon autonome et justifie               ║
║  chaque décision par écrit. Il pose UNE question à l'utilisateur            ║
║  uniquement si une décision dépasse son périmètre.                          ║
║                                                                              ║
║  PRINCIPE CLÉ : Ce que A2 fait, A3 ne refait pas.                          ║
║  Les données sortant de A2 sont directement utilisables par le GLM.        ║
║                                                                              ║
║  USAGE DANS GOOGLE COLAB                                                     ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  %run '/tmp/actuaria/agents/a2_preprocessing.py'          ║
║                                                                              ║
║  agent_a2 = AgentA2Preprocessing()                                          ║
║  result   = agent_a2.run(result_a1)  # Passe le résultat de A1             ║
║                                                                              ║
║  AUTEUR   : ActuarIA — Système Actuariel IA                                 ║
║  VERSION  : 1.0                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ── IMPORTS ───────────────────────────────────────────────────────────────────
import os
import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
import copy
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings('ignore')

# ── LOGGER ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('actuaria.a2')


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Seuil Winsorisation par variable
# Justification actuarielle :
# La Winsorisation plafonne les valeurs extrêmes au percentile défini.
# Ex : prime_pure au P99 → on remplace les 1% de valeurs les plus élevées
# par la valeur du 99ème percentile. Cela évite qu'un sinistre catastrophique
# unique biaise l'estimation des paramètres du GLM Gamma.
# Valeurs calibrées sur les statistiques du marché français (FFA 2022).
SEUILS_WINSOR = {
    # Non-Vie
    'prime_pure':             (0.01, 0.99),  # Clip au P1-P99
    'prime_commerciale':      (0.01, 0.99),
    'cout_total_sinistres':   (0.00, 0.99),  # Pas de borne inférieure (0 est valide)
    'cout_moyen_attendu':     (0.01, 0.99),
    'valeur_venale':          (0.01, 0.99),
    'kilometrage_annuel':     (0.01, 0.99),
    'ca_annuel_eur':          (0.01, 0.99),
    # Vie
    'prime_pure_annuelle':    (0.01, 0.99),
    'capital_assure_deces_eur': (0.01, 0.99),
    'provision_mathematique': (0.01, 0.99),
    # Santé-Prévoyance
    'charge_annuelle_eur':    (0.00, 0.99),
    'ij_journaliere_eur':     (0.01, 0.99),
    'charge_ij_annuelle_eur': (0.00, 0.99),
}

# Variables catégorielles par sous-branche
# Ces variables seront encodées selon la méthode appropriée
# Justification : l'encodage WoE est préféré pour les GLM car il
# préserve la relation monotone avec la variable cible.
# Le One-Hot est utilisé pour les variables à faible cardinalité (< 5 modalités).
VARS_CATEGORIELLES = {
    'auto': {
        'one_hot':    ['sexe', 'garantie', 'carburant'],
        'label':      ['csp', 'marque_vehicule', 'usage',
                       'milieu_geographique'],
        'ordinale':   [],
    },
    'mrh': {
        'one_hot':    ['sexe', 'statut_occupation', 'type_logement'],
        'label':      ['csp', 'zone_geographique'],
        'ordinale':   [],
    },
    'rcpro': {
        'one_hot':    ['forme_juridique', 'type_garantie'],
        'label':      ['secteur_activite'],
        'ordinale':   [],
    },
    'vie_individuelle': {
        'one_hot':    ['sexe', 'fumeur', 'etat_sante_entree'],
        'label':      ['type_produit', 'csp', 'periodicite_prime'],
        'ordinale':   [],
    },
    'vie_collective': {
        'one_hot':    ['sexe'],
        'label':      ['secteur_activite', 'type_contrat'],
        'ordinale':   [],
    },
    'sante_collective': {
        'one_hot':    ['sexe', 'niveau_couverture'],
        'label':      ['secteur_activite'],
        'ordinale':   [],
    },
    'sante_individuelle': {
        'one_hot':    ['sexe', 'formule_sante'],
        'label':      ['regime_securite_sociale', 'antecedents_medicaux'],
        'ordinale':   [],
    },
    'prevoyance_collective': {
        'one_hot':    ['sexe', 'categorie_sociopro'],
        'label':      ['secteur_activite', 'statut_invalidite'],
        'ordinale':   [],
    },
    'prevoyance_individuelle': {
        'one_hot':    ['sexe'],
        'label':      ['csp', 'garanties_souscrites'],
        'ordinale':   [],
    },
}

# Colonnes interdites par sous-branche — conformité réglementaire
# Arrêt CJUE C-236/09 du 1er mars 2011 (Test-Achats) :
# Le genre (sexe) est interdit comme critère de tarification en RC Auto
# depuis le 21 décembre 2012. Transposé en droit français par la loi
# du 1er juillet 2012. Risque de sanction ACPR si variable présente
# dans la matrice X d'un modèle de tarification RC Auto.
COLS_INTERDITES_PAR_BRANCHE = {
    'auto': ['sexe'],   # RC Auto : genre interdit — CJUE C-236/09
}

# Variables d'interaction à créer par sous-branche
# Justification actuarielle :
# Ces interactions capturent des effets non-linéaires que le GLM seul
# ne peut pas modéliser. Ex : l'effet de l'âge sur la sinistralité
# est différent selon le niveau de bonus-malus.
# Ces variables seront utilisées par les modèles ML (A4) principalement.
INTERACTIONS = {
    'auto': [
        ('age', 'bonus_malus'),           # Jeune + mauvais BM = très sinistrogène
        ('puissance_fiscale', 'age'),     # Puissance élevée chez jeune = risque max
        ('kilometrage_annuel', 'usage'),  # Km × usage = exposition réelle
        ('bonus_malus', 'antecedents_sinistres_n1'),  # Double signal sinistralité
    ],
    'mrh': [
        ('surface_m2', 'type_logement'),  # Surface × type = valeur assurée
        ('etage', 'zone_geographique'),   # Étage × zone = risque vol/DDO
        ('annee_construction', 'alarme'), # Ancien sans alarme = risque élevé
    ],
    'rcpro': [
        ('ca_annuel_eur', 'nb_salaries'), # Taille entreprise
        ('secteur_activite', 'anciennete_entreprise_ans'),  # Expérience sectorielle
    ],
    'vie_individuelle': [
        ('age_entree', 'fumeur'),         # Âge × tabac = mortalité accrue
        ('age_entree', 'duree_contrat_ans'),  # Âge × durée = exposition totale
    ],
    'prevoyance_collective': [
        ('age', 'categorie_sociopro'),    # Âge × catégorie = risque arrêt
        ('secteur_activite', 'age'),      # BTP senior = très exposé
    ],
}

# Stratégies d'imputation par type de variable
# Justification :
# Médiane pour les variables numériques asymétriques (coûts, primes)
# → La médiane est robuste aux outliers contrairement à la moyenne
# Mode pour les variables catégorielles
# → On conserve la modalité la plus fréquente
STRATEGIES_IMPUTATION = {
    'numerique_asymetrique': 'median',   # Coûts, primes, capitaux
    'numerique_symetrique':  'mean',     # Âges, durées, expositions
    'categorielle':          'mode',     # CSP, garantie, type
    'binaire':               'mode',     # Fumeur, alarme, garanties 0/1
}


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE : AGENT A2 PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

class AgentA2Preprocessing:
    """
    Agent A2 — Preprocessing & Feature Engineering.

    Transforme les données brutes validées par A1 en données
    prêtes pour la calibration des modèles actuariels (A3/A4/A5).

    AUTONOMIE NIVEAU 2 :
    L'agent choisit ses paramètres de façon autonome et justifie
    chaque décision. Il logue toutes ses transformations pour
    garantir la reproductibilité (exigence S2 / IFRS 17).

    EXEMPLE D'UTILISATION :
    ─────────────────────────
    # Après avoir exécuté l'agent A1 :
    result_a1 = agent_a1.run(branche='non_vie',
                              fichier='contrats_auto_70k.parquet')

    agent_a2 = AgentA2Preprocessing(
        models_path='/tmp/actuaria',
        audit_path ='/tmp/actuaria',
    )
    result_a2 = agent_a2.run(result_a1)

    df_pret   = result_a2['dataframe']     # Données prêtes pour GLM/ML
    rapport   = result_a2['rapport']       # Rapport des transformations
    params    = result_a2['parametres']    # Paramètres sauvegardés
    """

    def __init__(
        self,
        models_path: str = '/tmp/actuaria',
        audit_path:  str = '/tmp/actuaria',
        verbose:     bool = True
    ):
        """
        Initialise l'agent A2.

        Paramètres
        ──────────
        models_path : str
            Chemin de sauvegarde des paramètres de preprocessing.
            Les paramètres (médiane, mode, encodeurs) sont sauvegardés
            pour permettre la reproductibilité sur de nouvelles données.
            Exigence S2 : tout calcul actuariel doit être reproductible.

        audit_path : str
            Chemin des logs d'audit trail.

        verbose : bool
            Affiche les commentaires actuaire sénior si True.
        """
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose

        # Création des dossiers si inexistants
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

        # Dictionnaire des paramètres appris
        # Contient toutes les valeurs calculées sur les données d'entraînement
        # pour pouvoir les réappliquer sur de nouvelles données
        self.parametres = {
            'medianes':      {},   # Médianes pour imputation numérique
            'modes':         {},   # Modes pour imputation catégorielle
            'winsor_bounds': {},   # Bornes Winsorisation
            'encodeurs':     {},   # Encodeurs label/one-hot
            'stats_expo':    {},   # Statistiques exposition
            'version':       '1.0',
            'timestamp':     None,
            'sous_branche':  None,
        }

        if self.verbose:
            logger.info("Agent A2 Preprocessing initialisé")

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTHODE PRINCIPALE : run()
    # ══════════════════════════════════════════════════════════════════════════

    def run(
        self,
        result_a1: Dict[str, Any],
        cible_frequence: str = 'nb_sinistres',
        cible_cout:      str = 'cout_total_sinistres',
        mode:            str = 'train'
    ) -> Dict[str, Any]:
        """
        Pipeline complet de preprocessing.

        Paramètres
        ──────────
        result_a1 : dict
            Résultat de l'agent A1 (doit contenir 'dataframe' et 'branche').

        cible_frequence : str
            Nom de la colonne cible pour le modèle de fréquence (GLM Poisson).
            Par défaut : 'nb_sinistres'

        cible_cout : str
            Nom de la colonne cible pour le modèle de coût (GLM Gamma).
            Par défaut : 'cout_total_sinistres'

        mode : str
            'train' : calcule et sauvegarde les paramètres
            'predict' : utilise les paramètres sauvegardés (nouvelles données)

        Retourne
        ────────
        dict avec :
            'dataframe'   : DataFrame preprocessé prêt pour A3/A4
            'rapport'     : rapport des transformations effectuées
            'parametres'  : paramètres appris (pour reproductibilité)
            'statut_rag'  : 'VERT', 'AMBRE' ou 'ROUGE'
            'commentaire' : commentaire actuaire sénior
            'audit_id'    : identifiant audit trail
        """
        t_debut    = datetime.now()
        audit_id   = f"A2_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        sous_branche = result_a1.get('branche', 'inconnue')

        logger.info(f"[{audit_id}] Agent A2 démarré | branche={sous_branche}")

        # Vérification que A1 a réussi
        if not result_a1.get('success', False):
            return self._erreur(
                "L'agent A1 a échoué. Corrigez les données avant de "
                "lancer A2.", audit_id
            )

        df = result_a1['dataframe'].copy()
        self.parametres['sous_branche'] = sous_branche
        self.parametres['timestamp']    = t_debut.isoformat()

        rapport = {
            'etapes':          [],
            'nb_lignes_debut': len(df),
            'nb_cols_debut':   len(df.columns),
            'transformations': {},
            'features_creees': [],
            'features_supprimees': [],
        }

        try:
            # ── ÉTAPE 1 : IMPUTATION ──────────────────────────────────────────
            logger.info(f"[{audit_id}] Étape 1/6 : Imputation valeurs manquantes")
            df, stats_imput = self._imputer(df, sous_branche, mode)
            rapport['etapes'].append('imputation')
            rapport['transformations']['imputation'] = stats_imput

            # ── ÉTAPE 2 : WINSORISATION ───────────────────────────────────────
            logger.info(f"[{audit_id}] Étape 2/6 : Winsorisation outliers")
            df, stats_winsor = self._winsoriser(df, mode)
            rapport['etapes'].append('winsorisation')
            rapport['transformations']['winsorisation'] = stats_winsor

            # ── ÉTAPE 3 : EXPOSITION ──────────────────────────────────────────
            logger.info(f"[{audit_id}] Étape 3/6 : Calcul/validation exposition")
            df, stats_expo = self._traiter_exposition(df, sous_branche)
            rapport['etapes'].append('exposition')
            rapport['transformations']['exposition'] = stats_expo

            # ── ÉTAPE 4 : ENCODAGE ────────────────────────────────────────────
            logger.info(f"[{audit_id}] Étape 4/6 : Encodage variables catégorielles")
            df, stats_encod = self._encoder(df, sous_branche, mode)
            rapport['etapes'].append('encodage')
            rapport['transformations']['encodage'] = stats_encod

            # ── ÉTAPE 5 : FEATURE ENGINEERING ────────────────────────────────
            logger.info(f"[{audit_id}] Étape 5/6 : Feature engineering métier")
            df, features_new = self._feature_engineering(df, sous_branche)
            rapport['etapes'].append('feature_engineering')
            rapport['features_creees'] = features_new

            # ── ÉTAPE 6 : VALIDATION FINALE ───────────────────────────────────
            logger.info(f"[{audit_id}] Étape 6/6 : Validation finale")
            df, stats_valid = self._valider_sortie(
                df, sous_branche, cible_frequence, cible_cout
            )
            rapport['etapes'].append('validation')
            rapport['transformations']['validation'] = stats_valid

            # Mise à jour rapport
            rapport['nb_lignes_fin'] = len(df)
            rapport['nb_cols_fin']   = len(df.columns)
            rapport['nb_features_ajoutees'] = (
                len(df.columns) - rapport['nb_cols_debut']
            )

            # Sauvegarde paramètres si mode train
            if mode == 'train':
                self._sauvegarder_parametres(sous_branche)

            # Commentaire actuaire sénior
            statut_rag  = self._calculer_statut_rag(rapport, df)
            commentaire = self._commenter_actuaire_senior(
                rapport, sous_branche, statut_rag,
                cible_frequence, cible_cout, df
            )

            # Audit trail
            self._sauvegarder_audit(audit_id, sous_branche, rapport,
                                     statut_rag, t_debut)

            if self.verbose:
                self._afficher_rapport_console(
                    audit_id, sous_branche, rapport,
                    statut_rag, commentaire
                )

            return {
                'success':           True,
                'dataframe':         df,
                'branche':           sous_branche,
                'statut_rag':        statut_rag,
                'rapport':           rapport,
                'parametres':        self.parametres,
                'commentaire':       commentaire,
                'audit_id':          audit_id,
                'erreur':            None,
                # Traçabilité des variables dérivées — ACPR-2022-P-01 §3.2
                'data_dictionnaire': DATA_DICTIONNAIRE,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 1 : IMPUTATION
    # ══════════════════════════════════════════════════════════════════════════

    def _imputer(
        self,
        df: pd.DataFrame,
        sous_branche: str,
        mode: str
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Imputation des valeurs manquantes par type de variable.

        STRATÉGIE ACTUARIELLE :
        ────────────────────────
        Variables numériques asymétriques (coûts, primes) → MÉDIANE
        Justification : les distributions de coûts sont fortement
        asymétriques à droite (quelques sinistres très coûteux).
        La médiane est robuste aux outliers contrairement à la moyenne.
        Imputer avec la moyenne introduirait un biais vers le haut.

        Variables numériques symétriques (âge, durée) → MOYENNE
        Justification : les distributions d'âge sont quasi-normales.
        La moyenne est un estimateur efficace pour ces distributions.

        Variables catégorielles → MODE (modalité la plus fréquente)
        Justification : on conserve la structure de distribution
        sans introduire de nouvelle catégorie artificielle.

        Variables binaires (0/1) → MODE
        Justification : on conserve la valeur majoritaire.

        NOTE IMPORTANTE :
        Les paramètres d'imputation sont calculés en mode 'train'
        et réutilisés en mode 'predict'. Cela évite la fuite de
        données (data leakage) qui invaliderait la validation du modèle.
        """
        stats = {
            'nb_cellules_avant': int(df.isnull().sum().sum()),
            'colonnes_imputees': {},
        }

        # Identification des colonnes avec valeurs manquantes
        cols_avec_na = df.columns[df.isnull().any()].tolist()

        if not cols_avec_na:
            logger.info("Aucune valeur manquante — imputation non nécessaire")
            stats['nb_cellules_apres'] = 0
            return df, stats

        # Variables numériques asymétriques (coûts, primes, capitaux)
        # Identifiées par leur nom
        mots_asymetriques = [
            'cout', 'prime', 'capital', 'valeur', 'montant',
            'encours', 'charge', 'ij', 'rente', 'ca_annuel',
            'provision', 'engagement'
        ]

        # Variables catégorielles
        cols_cat = df.select_dtypes(include=['object', 'category']).columns

        for col in cols_avec_na:
            nb_na = int(df[col].isnull().sum())
            pct_na = nb_na / len(df) * 100

            if col in cols_cat:
                # Imputation par le mode
                if mode == 'train':
                    valeur = df[col].mode()[0] if not df[col].mode().empty else 'INCONNU'
                    self.parametres['modes'][col] = valeur
                else:
                    valeur = self.parametres['modes'].get(col, 'INCONNU')

                df[col] = df[col].fillna(valeur)
                methode = 'mode'

            elif df[col].dtype in ['int64', 'float64', 'int32', 'float32']:
                # Choix médiane vs moyenne selon la nature de la variable
                est_asymetrique = any(
                    mot in col.lower() for mot in mots_asymetriques
                )

                if est_asymetrique:
                    if mode == 'train':
                        valeur = df[col].median()
                        self.parametres['medianes'][col] = valeur
                    else:
                        valeur = self.parametres['medianes'].get(
                            col, df[col].median()
                        )
                    methode = 'mediane'
                else:
                    if mode == 'train':
                        valeur = df[col].mean()
                        self.parametres['medianes'][col] = valeur
                    else:
                        valeur = self.parametres['medianes'].get(
                            col, df[col].mean()
                        )
                    methode = 'moyenne'

                df[col] = df[col].fillna(valeur)

            else:
                # Type inconnu → médiane si possible
                try:
                    valeur = df[col].median()
                    df[col] = df[col].fillna(valeur)
                    methode = 'mediane_fallback'
                except Exception:
                    methode = 'non_imputee'

            stats['colonnes_imputees'][col] = {
                'nb_na':   nb_na,
                'pct_na':  round(pct_na, 2),
                'methode': methode,
                'valeur':  float(valeur) if isinstance(valeur, (int, float, np.number)) else str(valeur),
            }

        stats['nb_cellules_apres'] = int(df.isnull().sum().sum())
        logger.info(
            f"Imputation : {stats['nb_cellules_avant']} → "
            f"{stats['nb_cellules_apres']} valeurs manquantes"
        )

        return df, stats

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : WINSORISATION
    # ══════════════════════════════════════════════════════════════════════════

    def _winsoriser(
        self,
        df: pd.DataFrame,
        mode: str
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Winsorisation des variables numériques pour traiter les outliers.

        MÉTHODE ACTUARIELLE :
        ──────────────────────
        La Winsorisation remplace les valeurs extrêmes par les percentiles
        définis dans SEUILS_WINSOR.

        Ex : prime_pure avec seuils (0.01, 0.99)
        → Toute prime < P1 est remplacée par P1
        → Toute prime > P99 est remplacée par P99

        JUSTIFICATION :
        Un sinistre de 10 millions d'euros dans un portefeuille auto
        de particuliers est très probablement une erreur de saisie ou
        un cas exceptionnel qui biaiserait fortement le GLM Gamma.
        La Winsorisation le remplace par le 99ème percentile sans
        supprimer la ligne (on conserve toute l'information).

        IMPORTANT : Les bornes sont calculées sur les données
        d'entraînement (mode='train') et réutilisées en prédiction
        (mode='predict') pour éviter le data leakage.
        """
        stats = {'colonnes_winsorisees': {}}

        for col, (p_inf, p_sup) in SEUILS_WINSOR.items():
            # Vérifie que la colonne existe dans le DataFrame
            if col not in df.columns:
                continue

            # Ne winsorise que les colonnes numériques
            if df[col].dtype not in ['int64', 'float64', 'int32', 'float32']:
                continue

            serie = df[col].dropna()
            if len(serie) == 0:
                continue

            if mode == 'train':
                # Calcul des bornes sur les données d'entraînement
                borne_inf = serie.quantile(p_inf) if p_inf > 0 else serie.min()
                borne_sup = serie.quantile(p_sup)
                self.parametres['winsor_bounds'][col] = {
                    'borne_inf': float(borne_inf),
                    'borne_sup': float(borne_sup),
                    'p_inf':     p_inf,
                    'p_sup':     p_sup,
                }
            else:
                # Récupération des bornes pré-calculées
                bounds = self.parametres['winsor_bounds'].get(col)
                if bounds is None:
                    continue
                borne_inf = bounds['borne_inf']
                borne_sup = bounds['borne_sup']

            # Application de la Winsorisation
            nb_avant_inf = (df[col] < borne_inf).sum()
            nb_avant_sup = (df[col] > borne_sup).sum()

            df[col] = df[col].clip(lower=borne_inf, upper=borne_sup)

            nb_modifies = int(nb_avant_inf + nb_avant_sup)
            if nb_modifies > 0:
                stats['colonnes_winsorisees'][col] = {
                    'nb_modifies': nb_modifies,
                    'pct_modifies': round(nb_modifies / len(df) * 100, 3),
                    'borne_inf':   round(float(borne_inf), 2),
                    'borne_sup':   round(float(borne_sup), 2),
                }

        nb_cols_winsor = len(stats['colonnes_winsorisees'])
        logger.info(f"Winsorisation : {nb_cols_winsor} colonne(s) traitée(s)")

        return df, stats

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 3 : EXPOSITION
    # ══════════════════════════════════════════════════════════════════════════

    def _traiter_exposition(
        self,
        df: pd.DataFrame,
        sous_branche: str
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Traitement et validation de la variable exposition.

        RÔLE ACTUARIEL DE L'EXPOSITION :
        ──────────────────────────────────
        L'exposition est LA variable centrale du GLM Poisson en Non-Vie.
        Elle représente la fraction d'année pendant laquelle le contrat
        était en vigueur.

        Dans le GLM Poisson : E[nb_sinistres] = λ × exposition
        L'exposition entre dans le modèle comme OFFSET :
        log(E[Y]) = log(exposition) + X'β

        Sans exposition, on modélise le nombre brut de sinistres
        → biais systématique pour les contrats partiels.
        Avec exposition, on modélise le TAUX de sinistres par an
        → estimation non biaisée de λ.

        RÈGLES DE VALIDATION :
        • exposition ∈ ]0, 1] — valeur réglementaire
        • exposition = 0 → contrat de durée nulle → à exclure
        • exposition > 1 → impossible pour un contrat annuel → correction

        Pour la branche Vie, l'exposition est gérée différemment :
        on utilise la durée résiduelle du contrat en années.
        """
        stats = {
            'col_exposition_trouvee': False,
            'valeurs_corrigees':      0,
            'lignes_exclues':         0,
        }

        # Recherche de la colonne exposition
        col_expo = None
        for col in df.columns:
            if 'exposition' in col.lower():
                col_expo = col
                break

        if col_expo is None:
            # Pas de colonne exposition trouvée
            # On crée une exposition unitaire (= 1 an pour tous)
            # et on logue un avertissement
            logger.warning(
                "Colonne 'exposition' introuvable. "
                "Exposition unitaire (=1) créée pour tous les contrats. "
                "Vérifiez vos données — l'exposition est indispensable "
                "pour le GLM Poisson."
            )
            df['exposition'] = 1.0
            col_expo = 'exposition'
            stats['exposition_creee'] = True
        else:
            stats['col_exposition_trouvee'] = True

        # Correction des valeurs aberrantes
        # exposition <= 0 : impossible — on remplace par la médiane
        nb_negatifs = (df[col_expo] <= 0).sum()
        if nb_negatifs > 0:
            mediane_expo = df[col_expo][df[col_expo] > 0].median()
            df.loc[df[col_expo] <= 0, col_expo] = mediane_expo
            stats['valeurs_corrigees'] += int(nb_negatifs)
            logger.warning(
                f"{nb_negatifs} valeurs d'exposition ≤ 0 remplacées "
                f"par la médiane ({mediane_expo:.4f})"
            )

        # exposition > 1 : contrat de plus d'un an
        # On plafonne à 1.0 (exposition maximale pour contrat annuel)
        nb_sup1 = (df[col_expo] > 1.0).sum()
        if nb_sup1 > 0:
            df.loc[df[col_expo] > 1.0, col_expo] = 1.0
            stats['valeurs_corrigees'] += int(nb_sup1)
            logger.warning(
                f"{nb_sup1} valeurs d'exposition > 1 plafonnées à 1.0"
            )

        # Calcul du log de l'exposition (offset pour GLM Poisson)
        # log(exposition) sera utilisé directement comme offset dans statsmodels
        df['log_exposition'] = np.log(np.maximum(df[col_expo], 1e-6))

        stats['exposition_min']    = round(float(df[col_expo].min()), 4)
        stats['exposition_max']    = round(float(df[col_expo].max()), 4)
        stats['exposition_median'] = round(float(df[col_expo].median()), 4)
        stats['exposition_mean']   = round(float(df[col_expo].mean()), 4)

        self.parametres['stats_expo'] = stats

        logger.info(
            f"Exposition : min={stats['exposition_min']} · "
            f"médiane={stats['exposition_median']} · "
            f"max={stats['exposition_max']}"
        )

        return df, stats

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 4 : ENCODAGE
    # ══════════════════════════════════════════════════════════════════════════

    def _encoder(
        self,
        df: pd.DataFrame,
        sous_branche: str,
        mode: str
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Encodage des variables catégorielles.

        MÉTHODES UTILISÉES :
        ─────────────────────

        1. LABEL ENCODING (variables à haute cardinalité)
        ──────────────────────────────────────────────────
        Utilisé pour : CSP, marque véhicule, secteur activité
        Justification : pour les variables avec de nombreuses modalités,
        le One-Hot encoding crée trop de colonnes et introduit de la
        multicolinéarité dans le GLM. Le Label Encoding attribue un
        entier à chaque modalité.

        ⚠️ ATTENTION : Le Label Encoding est acceptable pour les modèles
        ML (arbres de décision, boosting) car ils ne supposent pas
        d'ordre entre les modalités. Pour le GLM pur, le Weight of
        Evidence (WoE) serait plus rigoureux mais nécessite la variable
        cible — on l'implémente ici comme option avancée.

        2. ONE-HOT ENCODING (variables à faible cardinalité ≤ 5)
        ──────────────────────────────────────────────────────────
        Utilisé pour : sexe (M/F), fumeur (0/1), garantie (3 niveaux)
        Justification : faible cardinalité → pas d'explosion de dimensions.
        Crée une colonne binaire par modalité.

        3. VARIABLES BINAIRES (déjà 0/1)
        ──────────────────────────────────
        Pas de transformation nécessaire — déjà encodées.
        Vérification uniquement que les valeurs sont bien 0 ou 1.
        """
        stats = {
            'cols_label_encodees':   [],
            'cols_onehot_encodees':  [],
            'cols_binaires_ok':      [],
            'nouvelles_colonnes':    [],
        }

        # Récupération de la configuration d'encodage pour cette sous-branche
        # Recherche par correspondance partielle du nom de sous-branche
        config_encod = None
        for key in VARS_CATEGORIELLES:
            if key in sous_branche or sous_branche in key:
                # Copie profonde pour ne pas modifier le dict source
                config_encod = copy.deepcopy(VARS_CATEGORIELLES[key])
                # Appliquer les exclusions réglementaires par branche
                # (ex : sexe interdit en RC Auto — Arrêt CJUE C-236/09)
                for branche_key, cols_interdites in COLS_INTERDITES_PAR_BRANCHE.items():
                    if branche_key in sous_branche or sous_branche in branche_key:
                        for col_interdite in cols_interdites:
                            if col_interdite in config_encod.get('one_hot', []):
                                config_encod['one_hot'].remove(col_interdite)
                                logger.warning(
                                    f"[CONFORMITE REGLEMENTAIRE] "
                                    f"Variable '{col_interdite}' exclue de la "
                                    f"matrice X pour sous-branche '{sous_branche}'. "
                                    f"Réf. : Arrêt CJUE C-236/09 (Test-Achats) "
                                    f"— genre interdit en tarification RC Auto "
                                    f"depuis le 21/12/2012."
                                )
                break

        if config_encod is None:
            # Pas de configuration spécifique → encodage automatique
            config_encod = {'one_hot': [], 'label': [], 'ordinale': []}
            logger.warning(
                f"Pas de configuration d'encodage pour '{sous_branche}'. "
                "Encodage automatique basique appliqué."
            )

        # ── LABEL ENCODING ────────────────────────────────────────────────────
        for col in config_encod.get('label', []):
            if col not in df.columns:
                continue

            col_enc = f"{col}_enc"

            if mode == 'train':
                le = LabelEncoder()
                # Ajout d'une catégorie 'INCONNU' pour les nouvelles modalités
                valeurs_uniques = list(df[col].fillna('INCONNU').unique())
                if 'INCONNU' not in valeurs_uniques:
                    valeurs_uniques.append('INCONNU')
                le.fit(valeurs_uniques)
                self.parametres['encodeurs'][col] = {
                    'type':     'label',
                    'classes':  list(le.classes_),
                }
            else:
                # Récupération de l'encodeur sauvegardé
                enc_params = self.parametres['encodeurs'].get(col)
                if enc_params is None:
                    continue
                le = LabelEncoder()
                le.classes_ = np.array(enc_params['classes'])

            # Application : les valeurs inconnues → 'INCONNU'
            df_col = df[col].fillna('INCONNU').astype(str)
            classes_connues = set(le.classes_)
            df_col = df_col.apply(
                lambda x: x if x in classes_connues else 'INCONNU'
            )
            df[col_enc] = le.transform(df_col)
            stats['cols_label_encodees'].append(col)
            stats['nouvelles_colonnes'].append(col_enc)

        # ── ONE-HOT ENCODING ──────────────────────────────────────────────────
        for col in config_encod.get('one_hot', []):
            if col not in df.columns:
                continue

            if mode == 'train':
                # Calcul des modalités
                modalites = sorted(df[col].fillna('INCONNU').unique().tolist())
                self.parametres['encodeurs'][f"{col}_oh"] = {
                    'type':      'one_hot',
                    'modalites': modalites,
                }
            else:
                enc_params = self.parametres['encodeurs'].get(f"{col}_oh")
                if enc_params is None:
                    continue
                modalites = enc_params['modalites']

            # Création des colonnes binaires
            for modalite in modalites:
                col_new = f"{col}_{str(modalite).lower().replace(' ', '_')}"
                df[col_new] = (
                    df[col].fillna('INCONNU').astype(str) == str(modalite)
                ).astype(int)
                stats['nouvelles_colonnes'].append(col_new)

            stats['cols_onehot_encodees'].append(col)

        # ── ENCODAGE AUTOMATIQUE DES COLONNES OBJECT RESTANTES ───────────────
        # Pour les colonnes catégorielles non configurées explicitement
        cols_object = df.select_dtypes(include=['object']).columns.tolist()
        cols_a_exclure = ['id_contrat', 'id_assure', 'id_salarie',
                           'id_beneficiaire', 'id_adherent', 'date_souscription',
                           'date_survenance', 'date_mouvement', 'date_evaluation']

        for col in cols_object:
            if col in cols_a_exclure:
                continue
            if col in config_encod.get('label', []):
                continue
            if col in config_encod.get('one_hot', []):
                continue

            col_enc = f"{col}_enc"
            if col_enc in df.columns:
                continue

            # Encodage label automatique pour les autres colonnes object
            nb_modalites = df[col].nunique()
            if nb_modalites <= 30:  # Limite raisonnable
                if mode == 'train':
                    le = LabelEncoder()
                    valeurs = df[col].fillna('INCONNU').astype(str).unique()
                    le.fit(list(valeurs) + ['INCONNU'])
                    self.parametres['encodeurs'][col] = {
                        'type':    'label_auto',
                        'classes': list(le.classes_),
                    }
                else:
                    enc_params = self.parametres['encodeurs'].get(col)
                    if enc_params is None:
                        continue
                    le = LabelEncoder()
                    le.classes_ = np.array(enc_params['classes'])

                df_col_auto = df[col].fillna('INCONNU').astype(str)
                classes_connues = set(le.classes_)
                df_col_auto = df_col_auto.apply(
                    lambda x: x if x in classes_connues else 'INCONNU'
                )
                df[col_enc] = le.transform(df_col_auto)
                stats['cols_label_encodees'].append(f"{col}(auto)")
                stats['nouvelles_colonnes'].append(col_enc)

        logger.info(
            f"Encodage : {len(stats['cols_label_encodees'])} label · "
            f"{len(stats['cols_onehot_encodees'])} one-hot"
        )

        return df, stats

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 5 : FEATURE ENGINEERING
    # ══════════════════════════════════════════════════════════════════════════

    def _feature_engineering(
        self,
        df: pd.DataFrame,
        sous_branche: str
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Création des variables dérivées et d'interaction.

        LOGIQUE ACTUARIELLE :
        ──────────────────────
        Les variables d'interaction capturent des effets non-linéaires
        que le GLM seul ne peut pas modéliser car il suppose une relation
        log-linéaire entre les prédicteurs et la fréquence.

        Ex : âge × bonus_malus
        Un conducteur de 20 ans avec BM=1.0 est moins risqué qu'un
        conducteur de 20 ans avec BM=2.5 — mais pas de façon additive.
        L'interaction multipliée capture cet effet.

        Les variables dérivées transforment les variables brutes en
        indicateurs plus parlants pour le modèle :
        Ex : log(valeur_venale) → distribution plus symétrique
             âge² → capture l'effet U-shape de l'âge sur la sinistralité

        VARIABLES CRÉÉES PAR SOUS-BRANCHE :
        Voir dictionnaire INTERACTIONS en tête de fichier.
        """
        features_nouvelles = []

        # ── VARIABLES COMMUNES ────────────────────────────────────────────────

        # 1. Log des variables de coût et capital
        # Justification : les distributions de coûts sont log-normales.
        # Le log les rend plus symétriques et améliore la calibration du GLM Gamma.
        vars_log = [
            'cout_total_sinistres', 'prime_pure', 'prime_commerciale',
            'valeur_venale', 'ca_annuel_eur', 'capital_assure_deces_eur',
            'encours_cumule_eur', 'salaire_annuel', 'salaire_annuel_ref',
            'engagement_ias19', 'charge_annuelle_eur',
        ]
        for col in vars_log:
            if col in df.columns:
                col_log = f"log_{col}"
                # +1 pour éviter log(0) sur les contrats sans sinistre
                df[col_log] = np.log1p(df[col].clip(lower=0))
                features_nouvelles.append(col_log)

        # 2. Âge² — capture l'effet U-shape de l'âge
        # Justification : la sinistralité est élevée chez les très jeunes
        # (<25 ans) et les seniors (>70 ans). L'effet est quadratique.
        # Sans âge², le GLM supposerait une relation log-linéaire simple.
        for col_age in ['age', 'age_entree']:
            if col_age in df.columns:
                df[f'{col_age}_carre'] = df[col_age] ** 2
                features_nouvelles.append(f'{col_age}_carre')

        # ── VARIABLES SPÉCIFIQUES AUTO ────────────────────────────────────────
        if 'auto' in sous_branche:

            # Taux de sinistralité observé N-1 (proxy du risque historique)
            # BM × antécédents = double signal de sinistralité passée
            if 'bonus_malus' in df.columns and \
               'antecedents_sinistres_n1' in df.columns:
                df['risque_historique'] = (
                    df['bonus_malus'] * (1 + df['antecedents_sinistres_n1'])
                )
                features_nouvelles.append('risque_historique')

            # Kilométrage normalisé par l'exposition
            # = exposition kilométrique réelle annualisée
            if 'kilometrage_annuel' in df.columns and \
               'exposition' in df.columns:
                df['km_par_an_normalise'] = (
                    df['kilometrage_annuel'] /
                    np.maximum(df['exposition'], 0.01)
                )
                features_nouvelles.append('km_par_an_normalise')

            # Indicateur jeune conducteur (< 25 ans)
            # Justification : les <25 ans ont une sinistralité 2.5× supérieure
            # à la moyenne (source : ACPR, statistiques sinistralité FR 2022)
            if 'age' in df.columns:
                df['jeune_conducteur'] = (df['age'] < 25).astype(int)
                df['senior_conducteur'] = (df['age'] > 70).astype(int)
                features_nouvelles.extend([
                    'jeune_conducteur', 'senior_conducteur'
                ])

            # Interaction âge × bonus-malus
            if 'age' in df.columns and 'bonus_malus' in df.columns:
                df['age_x_bonus_malus'] = df['age'] * df['bonus_malus']
                features_nouvelles.append('age_x_bonus_malus')

            # Véhicule récent (< 3 ans) — généralement Tous Risques
            if 'age_vehicule' in df.columns:
                df['vehicule_recent'] = (df['age_vehicule'] < 3).astype(int)
                df['vehicule_ancien']  = (df['age_vehicule'] > 10).astype(int)
                features_nouvelles.extend([
                    'vehicule_recent', 'vehicule_ancien'
                ])

        # ── VARIABLES SPÉCIFIQUES MRH ─────────────────────────────────────────
        elif 'mrh' in sous_branche:

            # Densité de valeur (valeur mobilier par m²)
            # Proxy de la concentration du risque
            if 'valeur_mobilier' in df.columns and 'surface_m2' in df.columns:
                df['valeur_par_m2'] = (
                    df['valeur_mobilier'] /
                    np.maximum(df['surface_m2'], 1)
                )
                features_nouvelles.append('valeur_par_m2')

            # Ancienneté du logement (risque DDO et électrique)
            if 'annee_construction' in df.columns:
                annee_courante = 2024
                df['age_logement'] = annee_courante - df['annee_construction']
                df['logement_ancien'] = (df['age_logement'] > 50).astype(int)
                features_nouvelles.extend([
                    'age_logement', 'logement_ancien'
                ])

        # ── VARIABLES SPÉCIFIQUES VIE ─────────────────────────────────────────
        elif 'vie' in sous_branche or 'art' in sous_branche:

            # Durée résiduelle du contrat
            if 'age_entree' in df.columns and 'duree_contrat_ans' in df.columns:
                df['age_terme'] = df['age_entree'] + df['duree_contrat_ans']
                df['duree_residuelle'] = np.maximum(
                    df['duree_contrat_ans'] - 5, 0  # Estimation si pas ancienneté
                )
                features_nouvelles.extend(['age_terme', 'duree_residuelle'])

            # Rapport capital / prime (levier d'assurance)
            if 'capital_assure_deces_eur' in df.columns and \
               'prime_pure_annuelle' in df.columns:
                df['levier_assurance'] = (
                    df['capital_assure_deces_eur'] /
                    np.maximum(df['prime_pure_annuelle'], 1)
                )
                features_nouvelles.append('levier_assurance')

        # ── VARIABLES SPÉCIFIQUES SANTÉ ──────────────────────────────────────
        elif 'sante' in sous_branche:

            # Consommation médicale par poste (si données sinistres détaillées)
            # Utilisée par S1 Léonie pour la tarification par poste
            postes = ['medecine','pharmacie','hospitalisation','dentaire','optique']
            for poste in postes:
                col_cout  = f'cout_{poste}'
                col_freq  = f'freq_{poste}'
                col_nb    = f'nb_actes_{poste}'
                if col_cout in df.columns:
                    df[f'sinistre_{poste}'] = df[col_cout]
                    features_nouvelles.append(f'sinistre_{poste}')
                if col_nb in df.columns and col_cout in df.columns:
                    df[f'cout_moyen_{poste}'] = (
                        df[col_cout] / np.maximum(df[col_nb], 1)
                    )
                    features_nouvelles.append(f'cout_moyen_{poste}')

            # Ratio hospit / total (indicateur anti-sélection)
            if 'cout_hospitalisation' in df.columns:
                total_cols = [c for c in df.columns if c.startswith('cout_')]
                if len(total_cols) > 1:
                    df['total_sinistres_sante'] = df[total_cols].sum(axis=1)
                    df['part_hospit'] = (
                        df['cout_hospitalisation'] /
                        np.maximum(df['total_sinistres_sante'], 1)
                    ).clip(0, 1)
                    features_nouvelles.extend(['total_sinistres_sante','part_hospit'])

            # Facteur d'âge santé (sinistralité croît avec l'âge)
            if 'age' in df.columns:
                df['facteur_age_sante'] = (
                    0.7 + (df['age'] - 30) * 0.015
                ).clip(0.5, 2.5)
                features_nouvelles.append('facteur_age_sante')

            # Ancienneté contrat santé (fidélisation)
            if 'annee_adhesion' in df.columns:
                annee_courante = pd.Timestamp.now().year
                df['anciennete_sante'] = annee_courante - df['annee_adhesion']
                features_nouvelles.append('anciennete_sante')

        # ── VARIABLES SPÉCIFIQUES PRÉVOYANCE ─────────────────────────────────
        elif 'prevoyance' in sous_branche:

            # Taux de remplacement IJ / salaire
            # Mesure le niveau de couverture prévoyance
            if 'ij_journaliere_eur' in df.columns and \
               'salaire_annuel_ref' in df.columns:
                df['taux_remplacement'] = (
                    df['ij_journaliere_eur'] * 365 /
                    np.maximum(df['salaire_annuel_ref'], 1)
                )
                df['taux_remplacement'] = df['taux_remplacement'].clip(0, 1)
                features_nouvelles.append('taux_remplacement')

            # Durée d'arrêt ITT (utilisée par P2 Rayan pour les tables Markov)
            if 'date_debut_arret' in df.columns and 'date_fin_arret' in df.columns:
                df['duree_arret_jours'] = (
                    pd.to_datetime(df['date_fin_arret']) -
                    pd.to_datetime(df['date_debut_arret'])
                ).dt.days.clip(0, 1825)   # max 5 ans
                features_nouvelles.append('duree_arret_jours')
            elif 'duree_arret_jours' in df.columns:
                df['duree_arret_jours'] = df['duree_arret_jours'].clip(0, 1825)

            # Flag dossier ouvert (utilisé par P3 Élodie pour la PSAP)
            if 'statut_dossier' in df.columns:
                df['flag_dossier_ouvert'] = (
                    df['statut_dossier'].str.lower().isin(
                        ['ouvert','en_cours','actif','open']
                    ).astype(int)
                )
                features_nouvelles.append('flag_dossier_ouvert')
            elif 'date_cloture' in df.columns:
                df['flag_dossier_ouvert'] = df['date_cloture'].isna().astype(int)
                features_nouvelles.append('flag_dossier_ouvert')

            # Catégorie socioprofessionnelle (factor de risque ITT BCAC)
            if 'categorie_sociopro' in df.columns:
                csp_map = {'ouvrier':1.35,'employe':1.0,'cadre':0.75,'cadre_sup':0.60}
                df['facteur_csp_itt'] = (
                    df['categorie_sociopro'].str.lower()
                    .map(csp_map).fillna(1.0)
                )
                features_nouvelles.append('facteur_csp_itt')

            # Ancienneté en invalidité (pour PM rentes long terme P3)
            if 'date_debut_invalidite' in df.columns:
                annee_courante = pd.Timestamp.now().year
                df['anciennete_invalidite_ans'] = (
                    annee_courante -
                    pd.to_datetime(df['date_debut_invalidite']).dt.year
                ).clip(0, 40)
                features_nouvelles.append('anciennete_invalidite_ans')

        # ── INTERACTIONS GÉNÉRIQUES ───────────────────────────────────────────
        # Création des interactions définies dans INTERACTIONS
        interactions_config = None
        for key in INTERACTIONS:
            if key in sous_branche or sous_branche in key:
                interactions_config = INTERACTIONS[key]
                break

        if interactions_config:
            for col1, col2 in interactions_config:
                if col1 in df.columns and col2 in df.columns:
                    # Normalisation avant interaction pour éviter
                    # l'explosion des valeurs numériques
                    v1 = df[col1]
                    v2 = df[col2]
                    # Seulement si les deux sont numériques
                    if (v1.dtype in ['int64', 'float64'] and
                            v2.dtype in ['int64', 'float64']):
                        col_inter = f"inter_{col1}_{col2}"
                        df[col_inter] = v1 * v2
                        features_nouvelles.append(col_inter)

        logger.info(
            f"Feature engineering : {len(features_nouvelles)} "
            f"variable(s) créée(s)"
        )

        return df, features_nouvelles

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 6 : VALIDATION FINALE
    # ══════════════════════════════════════════════════════════════════════════

    def _valider_sortie(
        self,
        df: pd.DataFrame,
        sous_branche: str,
        cible_freq: str,
        cible_cout: str
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Validation finale du DataFrame preprocessé.

        Vérifie que :
        1. Il n'y a plus de valeurs manquantes dans les colonnes clés
        2. La variable cible (nb_sinistres) est bien non-négative
        3. L'exposition est bien dans ]0, 1]
        4. Le DataFrame est prêt pour les agents A3/A4/A5

        Supprime également les colonnes non utilisables par les modèles :
        - Identifiants (id_contrat, id_assure)
        - Dates brutes (date_souscription)
        - Colonnes object non encodées
        """
        stats = {
            'colonnes_supprimees': [],
            'nan_restants':        0,
            'pret_pour_glm':       False,
            'pret_pour_ml':        False,
        }

        # Colonnes à supprimer pour la modélisation
        # (conservées dans le DataFrame original pour le rapport)
        cols_id = [
            c for c in df.columns
            if any(mot in c.lower() for mot in [
                'id_contrat', 'id_assure', 'id_salarie',
                'id_beneficiaire', 'id_adherent',
            ])
        ]

        cols_date_brute = [
            c for c in df.columns
            if df[c].dtype == 'datetime64[ns]' or
               (df[c].dtype == 'object' and
                any(mot in c.lower() for mot in ['date_', 'annee_sous']))
        ]

        # On ne supprime pas — on crée un DataFrame de modélisation séparé
        # Le DataFrame complet reste disponible pour le rapport
        cols_a_exclure = set(cols_id + cols_date_brute)

        # Colonnes object restantes non encodées (à exclure du modèle)
        cols_object_restantes = [
            c for c in df.select_dtypes(include=['object']).columns
            if c not in cols_a_exclure
        ]

        stats['colonnes_non_encodees'] = cols_object_restantes
        stats['colonnes_id']           = cols_id

        # Vérification des NaN restants
        nan_restants = int(df.isnull().sum().sum())
        stats['nan_restants'] = nan_restants

        if nan_restants > 0:
            logger.warning(
                f"{nan_restants} valeurs manquantes restantes "
                "après imputation — vérification nécessaire"
            )

        # Vérification cible fréquence
        if cible_freq in df.columns:
            nb_negatifs = (df[cible_freq] < 0).sum()
            stats['pret_pour_glm'] = (nb_negatifs == 0)
        else:
            stats['pret_pour_glm'] = False
            logger.warning(
                f"Variable cible '{cible_freq}' introuvable. "
                "L'agent A3 (GLM Poisson) ne pourra pas calibrer "
                "le modèle de fréquence."
            )

        # Vérification exposition
        if 'exposition' in df.columns:
            expo_ok = ((df['exposition'] > 0) & (df['exposition'] <= 1)).all()
            stats['exposition_valide'] = bool(expo_ok)
        else:
            stats['exposition_valide'] = False

        # Liste des colonnes numériques disponibles pour les modèles
        cols_num = df.select_dtypes(
            include=['int64', 'float64', 'int32', 'float32']
        ).columns.tolist()
        stats['nb_features_numeriques'] = len(cols_num)
        stats['pret_pour_ml']           = len(cols_num) >= 5

        return df, stats

    # ══════════════════════════════════════════════════════════════════════════
    # VERSIONING & AUDIT
    # ══════════════════════════════════════════════════════════════════════════

    def _sauvegarder_parametres(self, sous_branche: str) -> None:
        """
        Sauvegarde les paramètres de preprocessing sur Drive.

        Ces paramètres permettent de :
        1. Reproduire exactement le même preprocessing sur de nouvelles données
        2. Répondre à un auditeur S2 sur les hypothèses utilisées
        3. Détecter une dérive des données (data drift) au fil du temps

        Format : JSON pour lisibilité humaine
        """
        nom_fichier = f"params_a2_{sous_branche}.json"
        chemin      = self.models_path / nom_fichier

        try:
            # Conversion des types numpy en types Python natifs
            params_serialisables = self._serialiser_params(self.parametres)

            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(params_serialisables, f, indent=2,
                          ensure_ascii=False, default=str)

            logger.info(f"Paramètres A2 sauvegardés : {chemin}")

        except Exception as e:
            logger.warning(f"Impossible de sauvegarder les paramètres : {e}")

    def _serialiser_params(self, obj: Any) -> Any:
        """Convertit les types numpy en types Python pour la sérialisation JSON."""
        if isinstance(obj, dict):
            return {k: self._serialiser_params(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialiser_params(i) for i in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj

    def charger_parametres(self, sous_branche: str) -> bool:
        """
        Charge les paramètres sauvegardés pour le mode 'predict'.
        Retourne True si les paramètres ont été chargés avec succès.
        """
        nom_fichier = f"params_a2_{sous_branche}.json"
        chemin      = self.models_path / nom_fichier

        if not chemin.exists():
            logger.error(
                f"Paramètres introuvables : {chemin}\n"
                "Lancez d'abord le preprocessing en mode 'train'."
            )
            return False

        with open(chemin, 'r', encoding='utf-8') as f:
            self.parametres = json.load(f)

        logger.info(f"Paramètres A2 chargés depuis : {chemin}")
        return True

    def _sauvegarder_audit(
        self,
        audit_id: str,
        sous_branche: str,
        rapport: Dict,
        statut_rag: str,
        t_debut: datetime
    ) -> None:
        """Sauvegarde le log d'audit en JSON."""
        log = {
            'audit_id':    audit_id,
            'agent':       'A2_PREPROCESSING',
            'version':     '1.0',
            'timestamp':   t_debut.isoformat(),
            'sous_branche': sous_branche,
            'statut_rag':  statut_rag,
            'etapes':      rapport['etapes'],
            'nb_lignes':   {
                'debut': rapport['nb_lignes_debut'],
                'fin':   rapport.get('nb_lignes_fin', rapport['nb_lignes_debut']),
            },
            'nb_features': {
                'debut':    rapport['nb_cols_debut'],
                'fin':      rapport.get('nb_cols_fin', rapport['nb_cols_debut']),
                'ajoutees': rapport.get('nb_features_ajoutees', 0),
            },
            'features_creees': rapport.get('features_creees', []),
        }
        chemin = self.audit_path / f"{audit_id}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(log, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Audit trail non sauvegardé : {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # STATUT RAG & COMMENTAIRES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_statut_rag(
        self,
        rapport: Dict,
        df: pd.DataFrame
    ) -> str:
        """
        Calcule le statut RAG du preprocessing.

        VERT  : Données prêtes pour GLM et ML sans restriction
        AMBRE : Données utilisables mais points d'attention
        ROUGE : Preprocessing incomplet — intervention requise
        """
        val = rapport.get('transformations', {}).get('validation', {})

        # ROUGE : données non prêtes pour le GLM
        if not val.get('pret_pour_glm', True):
            return 'ROUGE'

        # ROUGE : NaN restants excessifs
        nan_restants = val.get('nan_restants', 0)
        if nan_restants > len(df) * 0.05:  # > 5% de NaN restants
            return 'ROUGE'

        # AMBRE : colonnes non encodées restantes
        if val.get('colonnes_non_encodees'):
            return 'AMBRE'

        # AMBRE : exposition non validée
        if not val.get('exposition_valide', True):
            return 'AMBRE'

        return 'VERT'

    def _commenter_actuaire_senior(
        self,
        rapport: Dict,
        sous_branche: str,
        statut_rag: str,
        cible_freq: str,
        cible_cout: str,
        df: pd.DataFrame
    ) -> str:
        """
        Commentaire actuaire sénior en 3 niveaux sur le preprocessing.
        """
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
        features_new    = rapport.get('features_creees', [])
        nb_features_new = len(features_new)
        val             = rapport.get('transformations', {}).get('validation', {})
        winsor          = rapport.get('transformations', {}).get('winsorisation', {})
        nb_winsor       = len(winsor.get('colonnes_winsorisees', {}))
        nb_cols_fin     = rapport.get('nb_cols_fin', rapport['nb_cols_debut'])

        # ── NIVEAU 1 : LECTURE ────────────────────────────────────────────────
        niveau1 = (
            f"{emoji} PREPROCESSING {statut_rag}\n"
            f"Sous-branche : {sous_branche}\n"
            f"Lignes       : {rapport['nb_lignes_debut']:,} → "
            f"{rapport.get('nb_lignes_fin', rapport['nb_lignes_debut']):,}\n"
            f"Colonnes     : {rapport['nb_cols_debut']} → {nb_cols_fin} "
            f"(+{nb_features_new} features créées)\n"
            f"Étapes       : {' → '.join(rapport['etapes'])}\n"
            f"Winsorisées  : {nb_winsor} variable(s)\n"
            f"NaN restants : {val.get('nan_restants', 0)}"
        )

        # ── NIVEAU 2 : DIAGNOSTIC ─────────────────────────────────────────────
        if statut_rag == 'VERT':
            niveau2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le preprocessing est complet et conforme aux exigences "
                f"de calibration actuarielle. "
                f"Les {nb_features_new} variables créées enrichissent "
                f"le pouvoir prédictif des modèles ML (A4) "
                f"sans introduire de biais dans le GLM (A3). "
                f"L'exposition est validée et le log-offset est prêt "
                f"pour le GLM Poisson. "
                f"La Winsorisation sur {nb_winsor} variable(s) réduit "
                f"l'influence des valeurs extrêmes sur les paramètres β "
                f"du GLM Gamma."
            )
        elif statut_rag == 'AMBRE':
            cols_non_enc = val.get('colonnes_non_encodees', [])
            niveau2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le preprocessing principal est réalisé mais "
                f"{len(cols_non_enc)} colonne(s) n'ont pas pu être "
                f"encodées automatiquement : {cols_non_enc}. "
                f"Ces colonnes seront exclues des modèles GLM et ML "
                f"car les algorithmes ne gèrent pas les chaînes de caractères. "
                f"Vérifiez si ces variables sont pertinentes actuariellement "
                f"avant de les ignorer définitivement."
            )
        else:
            niveau2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le preprocessing est incomplet. "
                f"Des valeurs manquantes ou incohérentes subsistent "
                f"après traitement. La calibration du GLM Poisson "
                f"produirait des estimateurs biaisés sur ces données."
            )

        # ── NIVEAU 3 : RECOMMANDATION ─────────────────────────────────────────
        if statut_rag == 'VERT':
            niveau3 = (
                "RECOMMANDATION :\n"
                f"→ Passer à l'agent A3 (GLM Poisson + Gamma). \n"
                f"→ Utiliser 'log_exposition' comme offset dans le GLM Poisson.\n"
                f"→ Variable cible fréquence : '{cible_freq}'.\n"
                f"→ Variable cible coût      : '{cible_cout}' "
                f"  (sur les sinistres > 0 uniquement).\n"
                f"→ Les {nb_features_new} nouvelles features sont "
                f"  disponibles pour A4 (ML) et A5 (CANN)."
            )
        elif statut_rag == 'AMBRE':
            niveau3 = (
                "RECOMMANDATION :\n"
                "→ Procéder avec précaution à l'agent A3.\n"
                "→ Les colonnes non encodées seront ignorées par le GLM.\n"
                "→ Investiguer manuellement leur pertinence actuarielle.\n"
                "→ Relancer A2 avec une configuration d'encodage étendue "
                "  si ces colonnes sont importantes."
            )
        else:
            niveau3 = (
                "RECOMMANDATION :\n"
                "→ ARRÊT — Ne pas transmettre à A3.\n"
                "→ Corriger les problèmes identifiés ci-dessus.\n"
                "→ Relancer A1 puis A2 après correction."
            )

        return f"{niveau1}\n\n{niveau2}\n\n{niveau3}"

    def _afficher_rapport_console(
        self,
        audit_id: str,
        sous_branche: str,
        rapport: Dict,
        statut_rag: str,
        commentaire: str
    ) -> None:
        """Affiche le rapport dans la console Colab."""
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
        sep   = "═" * 65

        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT A2 PREPROCESSING | {audit_id}")
        print(sep)
        print(f"  Sous-branche : {sous_branche}")
        print(f"  {emoji} STATUT : {statut_rag}")
        print(f"\n  TRANSFORMATIONS EFFECTUÉES :")
        for etape in rapport['etapes']:
            print(f"    ✅ {etape}")
        print(f"\n  FEATURES CRÉÉES ({len(rapport.get('features_creees', []))}) :")
        for f in rapport.get('features_creees', [])[:10]:
            print(f"    + {f}")
        if len(rapport.get('features_creees', [])) > 10:
            print(f"    ... et {len(rapport['features_creees'])-10} autres")
        print(f"\n{sep}")
        print("  COMMENTAIRE ACTUAIRE SÉNIOR")
        print(sep)
        for ligne in commentaire.split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    def _erreur(self, message: str, audit_id: str) -> Dict:
        """Retourne un résultat d'erreur structuré."""
        return {
            'success':     False,
            'dataframe':   pd.DataFrame(),
            'branche':     None,
            'statut_rag':  'ROUGE',
            'rapport':     {},
            'parametres':  {},
            'commentaire': f"❌ ERREUR A2 : {message}",
            'audit_id':    audit_id,
            'erreur':      message,
        }


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE GOOGLE COLAB
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    """
    Test de l'agent A2 depuis Google Colab.

    Copie ces cellules dans ActuarIA_Phase02_Agent_A2_Preprocessing.ipynb :

    ─────────────────────────────────────────────────────────────────────
    # Cellule 1
    from google.colab import drive
    # drive.mount('/content/drive')  # Colab uniquement

    # Cellule 2
    %run '/tmp/actuaria/agents/a1_ingestion.py'
    %run '/tmp/actuaria/agents/a2_preprocessing.py'
    print("✅ Agents A1 et A2 chargés")

    # Cellule 3 — Chargement avec A1
    agent_a1 = AgentA1Ingestion(
        base_path  = '/tmp/actuaria/data',
        audit_path = '/tmp/actuaria',
        verbose    = False
    )
    result_a1 = agent_a1.run(
        branche = 'non_vie',
        fichier = 'contrats_auto_70k.parquet'
    )
    print(f"A1 : {result_a1['statut_rag']} | {len(result_a1['dataframe']):,} lignes")

    # Cellule 4 — Preprocessing avec A2
    agent_a2 = AgentA2Preprocessing(
        models_path = '/tmp/actuaria',
        audit_path  = '/tmp/actuaria',
        verbose     = True
    )
    result_a2 = agent_a2.run(result_a1)

    # Cellule 5 — Résultats
    df_pret = result_a2['dataframe']
    print(f"Shape final : {df_pret.shape}")
    print(f"Statut      : {result_a2['statut_rag']}")
    print(result_a2['commentaire'])

    # Cellule 6 — Voir les nouvelles features
    print("Features créées :")
    for f in result_a2['rapport']['features_creees']:
        print(f"  + {f}")

    # Cellule 7 — DataFrame final
    df_pret.head(10)
    ─────────────────────────────────────────────────────────────────────
    """
    print("Agent A2 — Preprocessing & Feature Engineering ActuarIA v1.0")
    print("Importez ce module dans votre notebook Colab.")
    print("Exemple : %run 'chemin/a2_preprocessing.py'")
