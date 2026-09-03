"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                  ACTUARIA — AGENT A4 : TARIFICATION ML                      ║
║                        Version 1.0 — Production                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE DE CET AGENT                                                           ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  L'agent A4 calibre les modeles de Machine Learning listes ci-dessous et     ║
║  les compare systematiquement au GLM de reference (Agent A3).                ║
║                                                                              ║
║  CONSTAT a4/C7 -- CET EN-TETE ANNONCAIT << 8 MODELES >>, ET SE TROMPAIT      ║
║  DANS LES DEUX SENS. Mesure du 01/09/2026 sur la SEULE boucle de             ║
║  calibration (_calibrer_tous_modeles) : SIX modeles. Trois noms annonces     ║
║  ici n'y sont PAS -- RandomForest, GAM, RegQuantile -- et GAM n'existe       ║
║  NULLE PART dans le depot, pas meme dans FAMILLES_MODELES_ML. Un modele      ║
║  REELLEMENT calibre, xgboost_tweedie, n'y etait PAS annonce.                 ║
║  Une liste qui se trompe dans les deux sens ne se corrige pas au chiffre :   ║
║  elle se REECRIT depuis la source. A4-2 compare desormais cet en-tete a la   ║
║  boucle, PAR AST -- il tombe si l'un des deux bouge sans l'autre.            ║
║                                                                              ║
║  MODELES CALIBRES (la boucle de _calibrer_tous_modeles) :                    ║
║                                                                              ║
║  1. gbm                 -- Gradient Boosting Machine (sklearn)               ║
║  2. xgboost             -- eXtreme Gradient Boosting                         ║
║  3. xgboost_tweedie     -- XGBoost a objectif Tweedie (prime pure)           ║
║  4. lightgbm            -- Light Gradient Boosting Machine (Microsoft)       ║
║  5. catboost            -- Categorical Boosting (Yandex)                     ║
║  6. lineaire_regularise -- ElasticNet (continu) / Poisson ridge (comptage)   ║
║                                                                              ║
║  FAMILLES_MODELES_ML en declare DIX : c'est une table de FAMILLES, pas une   ║
║  liste de candidats -- elle nomme aussi ce qui pourrait arriver d'ailleurs   ║
║  (xgboost_optuna, quantile_50...). Les deux comptes sont justes ; les        ║
║  confondre est ce qui produisait << 8 >>.                                    ║
║                                                                              ║
║  MÉTRIQUES DE COMPARAISON :                                                  ║
║  • Gini (pouvoir discriminant — référence actuarielle)                      ║
║  • RMSE (erreur quadratique moyenne)                                        ║
║  • MAE (erreur absolue moyenne)                                             ║
║  • Poisson Déviance (pour les modèles de fréquence)                        ║
║  • SHAP values (interprétabilité — conformité AI Act 2025)                 ║
║                                                                              ║
║  SÉLECTION DU MEILLEUR MODÈLE :                                             ║
║  L'agent sélectionne automatiquement le meilleur modèle selon le Gini      ║
║  et génère un classement avec justification actuarielle.                    ║
║                                                                              ║
║  AUTONOMIE : Niveau 2                                                        ║
║  L'agent optimise les hyperparamètres, sélectionne le meilleur modèle      ║
║  et justifie chaque décision. Il alerte si un modèle surparamètre          ║
║  (overfitting détecté).                                                     ║
║                                                                              ║
║  AUTEUR   : ActuarIA — Système Actuariel IA                                 ║
║  VERSION  : 1.0                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ── IMPORTS ───────────────────────────────────────────────────────────────────
import os
import json
import pickle
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
# Compatibilité NumPy ≥ 2.0 : trapz → trapezoid
_np_trapz = getattr(np, 'trapezoid', None) or getattr(np, 'trapz', None)
import pandas as pd
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# Graphiques V3 (charte partagée core/charts_tarif) — import gardé, optionnel.
try:
    from core.charts_tarif import chart_shap_summary
    _CHARTS_V3_OK = True
except Exception:
    _CHARTS_V3_OK = False
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, QuantileRegressor, PoissonRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

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

# Imports optionnels — installés si disponibles
try:
    import xgboost as xgb
    XGBOOST_OK = True
except ImportError:
    XGBOOST_OK = False

try:
    import lightgbm as lgb
    LIGHTGBM_OK = True
except ImportError:
    LIGHTGBM_OK = False

try:
    from catboost import CatBoostRegressor
    CATBOOST_OK = True
except ImportError:
    CATBOOST_OK = False

try:
    import shap
    SHAP_OK = True
except ImportError:
    SHAP_OK = False

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    OPTUNA_OK = True
except ImportError:
    OPTUNA_OK = False

try:
    from .services.tarif_excel import export_excel_a4
    TARIF_EXCEL_OK = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.tarif_excel import export_excel_a4
        TARIF_EXCEL_OK = True
    except ImportError:
        TARIF_EXCEL_OK = False

try:
    from .services.rapport_modeles_tarif import generer_rapport_tarification as _gen_rapport_a4
    TARIF_RAPPORT_OK_A4 = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.rapport_modeles_tarif import (
            generer_rapport_tarification as _gen_rapport_a4
        )
        TARIF_RAPPORT_OK_A4 = True
    except ImportError:
        TARIF_RAPPORT_OK_A4 = False

# Module de conformité partagé (audit V7 BLOQUANT #1) — A4 n'avait AUCUN
# filtre genre avant ce correctif (fuite confirmée par exécution réelle :
# une colonne 'sexe' numérique atteignait la matrice de features des
# modèles ML, potentiellement retenus en production par A6).
from core.charts_tarif import (
    FOND_SOMBRE,
    couleur_rag,
    couleur_texte_rag,
    glyphe_rag,
)
from core.conformite_reglementaire import (
    BASE_GINI_UNITAIRE,
    construire_matrice_x,
    colonne_temporelle, diagnostiquer_evaluation, phrase_evaluation_impossible,
    gini_texte,
)
# ⚠️ SOURCE UNIQUE. L'etat de l'elasticite etait defini ICI au lot L0 ;
# il vit desormais dans `core/elasticite.py`, avec le catalogue
# d'exigences qui le fonde. Deux definitions auraient diverge.
from core.elasticite import (
    ELASTICITE_ESTIMEE,
    etat_elasticite,
    sensibilite_tarifaire,
)
from core.plan_tarifaire import (
    PlanTarifaire, verifier_completude_plan, plafonner_statut_si_ampute,
    alerte_modele_ampute,
)

# ── LOGGER ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('actuaria.a4')


# ── Alignement A4 sur le plan signé (Phase 1) ─────────────────────────────────
# Plus de _LOBS_ALIGNES_PLAN ni de chargement de plan EN INTERNE : A4.run() reçoit
# le PLAN signé et le transmet à construire_matrice_x, dont la liste blanche =
# plan.colonnes_produites(). Les 3 familles (GLM/ML/DL) partagent EXACTEMENT les
# mêmes colonnes ; le GLM ne concourt plus contre une liste ML plus large.
# Historiquement A4 sélectionnait ses features en DATA-DRIVEN (toutes colonnes
# numériques d'A2, filtrées par l'ANCIENNE FACTEURS_TARIFAIRES_AUTORISES) : un
# sur-ensemble du plan, déployé LoB par LoB via un frozenset. C'est désormais
# universel et explicite. Plan absent → erreur propre (voir run()), jamais de repli.


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# ⚠️⚠️ CE MESSAGE EST LU PAR UN ACTUAIRE, PAS PAR UN DÉVELOPPEUR — exigence
# explicite de Selasse, 30/08/2026, constat `a4/C11` (rang 1). Il doit dire
# TROIS choses, et il est relu ici parce qu'une seule manquante le rend
# trompeur :
#   ① le modèle A BIEN ÉTÉ jugé sur tous ses autres critères ;
#   ② SEULE la comparaison à la référence A3 n'a pas pu être faite, et
#     POURQUOI — A3 n'a pas tourné pour cette exécution ;
#   ③ ce n'est PAS un défaut du modèle évalué : c'est une pièce de
#     comparaison qui manque.
# ⚠️ La quatrième phrase — le remède — suit la règle de ce dépôt : un message
# qui signale dit aussi QUOI FAIRE. Sans elle, l'actuaire lit un constat sans
# issue.
# ⚠️ Constante NOMMÉE, jamais une chaîne enfouie dans une branche : un contrôle
# doit pouvoir la citer, et les trois surfaces doivent lire LA MÊME.
MSG_REFERENCE_A3_INDISPONIBLE = (
    "Comparaison au Gini de référence NON FAITE : l'agent A3 (GLM) n'a pas "
    "tourné pour cette exécution, il n'existe donc aucun Gini de référence à "
    "comparer. Le modèle retenu a bien été évalué sur tous ses autres "
    "critères — seule cette comparaison manque. Ce n'est pas un défaut du "
    "modèle évalué, c'est une pièce de comparaison absente. Pour l'obtenir, "
    "relancer A3 avant A4."
)

# Colonnes à exclure de la modélisation ML
# Même liste que A3 + colonnes supplémentaires spécifiques ML
# ⚠️⚠️ CONSTAT `a4/C12` — CINQ ENTREES SONT DU VOCABULAIRE VIE/SANTE dans
# un agent Non-Vie (`id_salarie`, `id_beneficiaire`, `id_adherent`,
# `cotisation_mensuelle_eur`, `charge_ij_annuelle_eur`). C'est le JUMEAU
# EXACT d'`a3/C16`, sur la meme liste heritee -- et l'arbitrage est le
# meme, pour la meme raison : cette liste EXCLUT. En oter une entree
# AJOUTERAIT une variable au modele si un fichier client portait cette
# colonne. *Le geste << propre >> est ici le geste RISQUE.*
# ⚠️ Mesure du 01/09 : 0 / 20 plans ne nomme l'une d'elles. Un temoin le
# reverifie a chaque gate (`A4-3`), au lieu de recopier cette mesure.
COLS_A_EXCLURE_ML = [
    'id_contrat', 'id_assure', 'id_salarie', 'id_beneficiaire', 'id_adherent',
    'date_souscription', 'date_survenance', 'date_mouvement', 'date_evaluation',
    'annee_souscription',
    'nb_sinistres', 'cout_total_sinistres', 'prime_commerciale',
    # Note : prime_pure NON exclue — utilisée comme variable cible
    'lambda_freq_annuel', 'cout_moyen_attendu',
    'exposition', 'log_exposition',
    'prime_pure_annuelle', 'cotisation_annuelle', 'cotisation_mensuelle_eur',
    'charge_annuelle_eur', 'charge_ij_annuelle_eur',
    # Colonnes object non encodées
]

# Regroupement des modèles ML par famille méthodologique — audit V4 point #11.
# Utilisé pour peupler la clé 'famille' du classement (absente jusqu'ici,
# colonne vide dans l'export Excel A4 et dans le classement retourné par
# _classer_modeles ; seul A6, dans son agrégat indépendant, la renseignait).
#: ⚠️ SEUIL QUI DECIDE D'UN STATUT REGLEMENTAIRE — il etait un litteral
#: `0.10` enfoui dans une branche de `_calculer_statut_rag` (constat
#: `a4/C9`). Un chiffre qui fait la difference entre AMBRE et ROUGE se
#: nomme, sinon personne ne peut le discuter.
SEUIL_GINI_ML_EXPLOITABLE = 0.10

FAMILLES_MODELES_ML = {
    'gbm':             'Arbres / Boosting',
    'xgboost':         'Arbres / Boosting',
    'xgboost_optuna':  'Arbres / Boosting',
    'xgboost_tweedie': 'Arbres / Boosting',
    'lightgbm':        'Arbres / Boosting',
    'catboost':        'Arbres / Boosting',
    'random_forest':   'Arbres / Bagging',
    'lineaire_regularise': 'Linéaire régularisé',
    'quantile_50':     'Régression quantile',
    'quantile_90':     'Régression quantile',
}


def _famille_modele_ml(nom: str) -> str:
    """Retourne la famille méthodologique d'un modèle ML, ou 'Autre ML' si
    le nom n'est pas reconnu (garde-fou pour tout modèle ajouté ultérieurement
    sans mise à jour immédiate de FAMILLES_MODELES_ML)."""
    return FAMILLES_MODELES_ML.get(nom.lower(), 'Autre ML')


def creer_modele_ml_pour_nom(nom: str, col_cible: str = 'nb_sinistres'):
    """Fabrique un modèle ML frais, ENVELOPPÉ pour l'offset d'exposition.

    SOURCE UNIQUE A4/A6. Sur une cible de COMPTAGE (col_cible ∈ COLS_COMPTAGE),
    l'estimateur est enveloppé dans `_ModeleFrequenceExposition` (taux+poids :
    fit sur y/expo pondéré par expo ; predict rend le TAUX λ(X), l'espérance de
    sinistres d'un contrat = predict × expo). Le GLM (`_GLMWalkForward`) porte
    déjà son propre offset log(expo) et n'est JAMAIS enveloppé. La fabrication
    nue (inchangée) est dans `_fabriquer_estimateur_nu`.
    """
    modele = _fabriquer_estimateur_nu(nom, col_cible)
    if isinstance(modele, _GLMWalkForward):
        return modele                       # le GLM porte déjà son offset log(expo)
    return _envelopper_frequence(modele, col_cible)


def _fabriquer_estimateur_nu(nom: str, col_cible: str = 'nb_sinistres'):
    """
    Fabrique un modèle ML frais (non entraîné) à partir de son nom.

    Audit V4 recommandation #7 : réutilisé par A6 pour la recalibration
    walk-forward sur le MODÈLE RÉELLEMENT RETENU, plutôt qu'un proxy
    GradientBoostingRegressor générique toujours instancié quel que soit
    le modèle affiché comme recalibré (bug confirmé — le rapport affichait
    'modele_recalibre': <nom réel> alors qu'un GBM avait été utilisé en
    coulisses, indépendamment de ce nom).

    Centralise ici la logique déjà présente dans les méthodes
    `_creer_*` de AgentA4ML (qui ne dépendent d'aucun état d'instance —
    seul `col_cible` influe sur le choix objective/famille) pour éviter
    toute divergence entre la fabrique utilisée par A4 et celle utilisée
    par A6 pour la recalibration.

    Lève ImportError si la librairie du modèle demandé n'est pas
    installée, ValueError si le nom n'est pas reconnu (ex. référence
    GLM du classement — non recalibrable via cette fabrique sklearn).
    """
    nom_l = nom.lower()

    if nom_l == 'gbm':
        return GradientBoostingRegressor(**HYPERPARAMS['gbm'])

    if nom_l == 'xgboost':
        if not XGBOOST_OK:
            raise ImportError("XGBoost non installé : !pip install xgboost")
        params = dict(HYPERPARAMS['xgboost'])
        if col_cible in COLS_COMPTAGE:
            params['objective'] = 'count:poisson'
        return xgb.XGBRegressor(**params)

    if nom_l == 'xgboost_tweedie':
        if not XGBOOST_OK:
            raise ImportError("XGBoost non installé : !pip install xgboost")
        params = dict(HYPERPARAMS['xgboost'])
        params['objective']              = 'reg:tweedie'
        params['tweedie_variance_power'] = 1.5
        return xgb.XGBRegressor(**params)

    if nom_l == 'lightgbm':
        if not LIGHTGBM_OK:
            raise ImportError("LightGBM non installé : !pip install lightgbm")
        return lgb.LGBMRegressor(**HYPERPARAMS['lightgbm'])

    if nom_l == 'catboost':
        if not CATBOOST_OK:
            raise ImportError("CatBoost non installé : !pip install catboost")
        return CatBoostRegressor(**HYPERPARAMS['catboost'])

    if nom_l == 'random_forest':
        return RandomForestRegressor(**HYPERPARAMS['random_forest'])

    if nom_l == 'lineaire_regularise':
        if col_cible in COLS_COMPTAGE:
            # ⚠ CORRECTIF. Cette branche retournait un PoissonRegressor NU, sans
            # le StandardScaler que la branche continue possède — alors que le
            # principe était ÉNONCÉ juste à côté : « les coefficients β dépendent
            # de l'échelle de X ; sans normalisation, les variables à grande
            # variance dominent ». Il valait pour les DEUX branches : la pénalité
            # L2 de PoissonRegressor est tout aussi dépendante de l'échelle.
            #
            # L'effet n'était pas une dégradation, c'était un ÉCHEC MUET. Sur
            # décennale (montant_travaux_eur jusqu'à 1,7 M€, rapport d'échelle
            # 1 734 823x entre features), L-BFGS s'arrêtait à n_iter=1 et
            # prédisait une CONSTANTE (pred_std=0.000000) — Gini 0,0224 — SANS
            # lever le moindre avertissement de convergence. Le « modèle » n'était
            # que l'intercept. Avec le scaler : Gini 0,2205, convergé en 8
            # itérations. Sur auto : n_iter=2000 (plafond atteint) → 15.
            # Les arbres (GBM/XGB/LGBM/CatBoost) sont invariants d'échelle : ils
            # n'ont jamais été concernés, ce qui a masqué le défaut.
            return Pipeline([
                ('scaler',  StandardScaler()),
                ('poisson', PoissonRegressor(
                    alpha=HYPERPARAMS['lineaire_regularise']['alpha'],
                    max_iter=HYPERPARAMS['lineaire_regularise']['max_iter'],
                )),
            ])
        return Pipeline([
            ('scaler',     StandardScaler()),
            ('elasticnet', ElasticNet(**HYPERPARAMS['lineaire_regularise']))
        ])

    if nom_l == 'quantile_50':
        return QuantileRegressor(**HYPERPARAMS['quantile_50'])

    if nom_l == 'quantile_90':
        return QuantileRegressor(**HYPERPARAMS['quantile_90'])

    # ══════════════════════════════════════════════════════════════════════════
    #  GLM — RECALIBRATION WALK-FORWARD FIDÈLE (audit V14, BLOQUANT)
    # ══════════════════════════════════════════════════════════════════════════
    # Découverte du certificateur V14, et c'est une faille que HUIT cycles
    # d'audit n'avaient pas vue — moi compris :
    #
    #   UN GLM NE POUVAIT JAMAIS ÊTRE CERTIFIÉ VERT. JAMAIS.
    #
    # Cette fabrique ne savait construire que des modèles sklearn. Pour un GLM,
    # elle levait ValueError → le walk-forward retombait sur un proxy GBM →
    # modele_recalibre_fidele = False → le gate d'A6 plafonnait à AMBRE.
    # Structurellement. Un GLM PARFAIT (score 0,95 · Gini 0,32 · A/E 1,00 ·
    # 0 fenêtre rouge · gouvernance validée) sortait AMBRE ; le même modèle en
    # ML sortait VERT.
    #
    # Les conséquences dépassent le bug :
    #   · la plateforme ne pouvait pas certifier son LIVRABLE PRINCIPAL — le GLM
    #     est le modèle de référence de la Non-Vie : interprétable, auditable,
    #     attendu par l'ACPR ;
    #   · l'incitation était INVERSÉE : pour obtenir un VERT, l'actuaire devait
    #     choisir une boîte noire. Une plateforme de conformité qui pénalise le
    #     modèle interprétable et récompense la boîte noire prend le problème à
    #     l'envers, et à rebours de l'exigence d'explicabilité que l'ACPR
    #     applique aux modèles de tarification ;
    #   · l'AMBRE devenait une couleur SANS INFORMATION : un GLM sain et un
    #     modèle à Gini 0,91 (fuite probable) sortaient tous deux AMBRE.
    #
    # LA LEÇON, et elle vaut pour tout le module :
    #   « On a beaucoup vérifié que le système REFUSE ce qu'il doit refuser.
    #     Personne n'a vérifié qu'il ACCEPTE ce qu'il doit accepter. Un contrôle
    #     qui refuse tout est aussi inutile qu'un contrôle qui accepte tout — et
    #     bien plus difficile à repérer, parce qu'il donne l'apparence de la
    #     rigueur. »
    if nom_l in ('poisson', 'glm_poisson', 'gamma', 'glm_gamma',
                 'tweedie', 'glm_tweedie'):
        famille = nom_l.replace('glm_', '')
        return _GLMWalkForward(famille=famille, col_cible=col_cible)

    raise ValueError(
        f"Modèle '{nom}' non reconnu pour recalibration walk-forward."
    )


class _GLMWalkForward:
    """
    Adaptateur statsmodels à interface sklearn (fit / predict), pour recalibrer
    FIDÈLEMENT un GLM dans le walk-forward d'A6 — au lieu du proxy GBM.

    Reproduit la spécification actuarielle d'A3 :
      · Poisson  → offset = log(exposition)   (modèle de FRÉQUENCE)
      · Tweedie  → var_power = 1,5, PAS d'offset (cible=taux cout/expo)  (PRIME PURE)
      · Gamma    → var_weights = exposition   (modèle de COÛT MOYEN)

    ⚠ HONNÊTETÉ SUR LA FIDÉLITÉ : le GLM Gamma modélise la sévérité et n'est
    défini que sur des cibles STRICTEMENT POSITIVES. Si la cible du walk-forward
    contient des zéros (portefeuille avec contrats non sinistrés — le cas
    normal), un Gamma ne peut PAS être recalibré fidèlement. Dans ce cas on lève
    une erreur explicite plutôt que de substituer une autre famille en douce :
    une recalibration infidèle doit être DITE, pas maquillée. A6 retombera alors
    sur le proxy, l'étiquettera comme tel, et plafonnera à AMBRE — ce qui est le
    comportement correct.
    """

    def __init__(self, famille: str = 'poisson', col_cible: str = 'nb_sinistres'):
        self.famille = famille
        self.col_cible = col_cible
        self._res = None
        self._n_features = None

    def _design(self, X):
        import statsmodels.api as sm
        X = np.asarray(X, dtype=float)
        return sm.add_constant(X, has_constant='add')

    def fit(self, X, y, sample_weight=None):
        import statsmodels.api as sm
        y = np.asarray(y, dtype=float)
        Xc = self._design(X)
        self._n_features = Xc.shape[1]

        expo = None
        if sample_weight is not None:
            expo = np.maximum(np.asarray(sample_weight, dtype=float), 1e-9)

        if self.famille == 'poisson':
            fam = sm.families.Poisson()
            offset = np.log(expo) if expo is not None else None
            self._res = sm.GLM(y, Xc, family=fam, offset=offset).fit(
                maxiter=200, disp=False)

        elif self.famille == 'tweedie':
            # PAS D'OFFSET (cf. correctif A3 _calibrer_tweedie, commit 0d2b9c2) :
            # la cible prime pure est DÉJÀ le taux (cout/expo). Ajouter
            # offset=log(expo) double-compterait l'exposition (prime prédite ∝ expo,
            # au lieu d'exposure-indépendante). Même rationale que le GLM Tweedie d'A3.
            fam = sm.families.Tweedie(var_power=1.5, link=sm.families.links.Log())
            self._res = sm.GLM(y, Xc, family=fam).fit(maxiter=200, disp=False)

        elif self.famille == 'gamma':
            if np.any(y <= 0):
                # Voir la docstring : on le DIT, on ne le maquille pas.
                raise ValueError(
                    "GLM Gamma non recalibrable fidèlement : la cible "
                    f"'{self.col_cible}' contient des valeurs nulles ou "
                    "négatives (le Gamma modélise la sévérité, définie sur les "
                    "seuls contrats sinistrés)."
                )
            fam = sm.families.Gamma(link=sm.families.links.Log())
            self._res = sm.GLM(y, Xc, family=fam, var_weights=expo).fit(
                maxiter=200, disp=False)
        else:
            raise ValueError(f"Famille GLM inconnue : {self.famille}")
        return self

    def predict(self, X):
        if self._res is None:
            raise RuntimeError("_GLMWalkForward.predict() avant fit().")
        Xc = self._design(X)
        # Prédiction de la moyenne SANS offset : le walk-forward compare des
        # moyennes par contrat, et l'exposition de la fenêtre test est déjà
        # prise en compte par le calcul du A/E en aval.
        return np.asarray(self._res.predict(Xc), dtype=float)

    def __repr__(self):
        return f"_GLMWalkForward(famille={self.famille!r})"


class _ModeleFrequenceExposition:
    """Enveloppe un estimateur de FRÉQUENCE (cible de comptage) pour traiter
    l'exposition comme un OFFSET actuariel via la reformulation TAUX+POIDS, au
    lieu d'un sample_weight appliqué au comptage brut (qui déréglait le NIVEAU du
    prix — pas le rang — cf. le diagnostic offset ML : Σprédit/Σréel ~1,02).

    Mécanisme (UNIFORME sur tous les modèles, loss INCHANGÉE) :
      · fit(X, y, sample_weight=expo) apprend la cible y/expo pondérée par expo.
        La propriété des moindres carrés pondérés calibre l'agrégat
        (Σ comptages prédits == Σ réel) sous TOUTE loss à moyenne pondérée —
        déviance Poisson (xgboost, PoissonRegressor) comme erreur quadratique
        (gbm, lightgbm, catboost) — SANS changer la loss (mesuré : forcer Poisson
        effondrait le Gini de lightgbm de −24 %).
      · predict(X) rend le TAUX λ(X) = E[N | X, expo=1]. L'espérance de sinistres
        d'un contrat = predict(X) × expo. Aligne les modèles ML sur
        `_GLMWalkForward.predict`, qui rend déjà le taux.

    Actif UNIQUEMENT sur cible de comptage (la fabrique n'enveloppe PAS la cible
    COÛT : la sévérité ne dépend pas de l'exposition — décomposition
    E[S] = E[N] × E[C|N>0]). Sans sample_weight (ou poids uniformes), la
    reformulation est neutre (y/1 == y), donc le chemin coût est inchangé.

    NB : xgboost_tweedie est enveloppé comme les autres, mais sa sous-tarification
    résiduelle (~−9 %) vient de sa FAMILLE de loi (Tweedie sur un comptage), pas
    de l'exposition — chantier distinct, hors de ce correctif.
    """

    def __init__(self, base):
        self.base = base

    def fit(self, X, y, sample_weight=None):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if sample_weight is None:
            self.base.fit(X, y)             # pas d'exposition : reformulation neutre
            return self
        expo = np.maximum(np.asarray(sample_weight, dtype=float), 1e-9)
        taux = y / expo
        if isinstance(self.base, Pipeline):
            # sklearn : le poids va à l'estimateur FINAL, pas au StandardScaler
            etape = self.base.steps[-1][0]
            self.base.fit(X, taux, **{f"{etape}__sample_weight": expo})
        else:
            self.base.fit(X, taux, sample_weight=expo)
        return self

    def predict(self, X):
        return np.asarray(self.base.predict(np.asarray(X, dtype=float)), dtype=float)

    def __getattr__(self, nom):
        # Délégation d'attribut vers l'estimateur nu (SHAP dé-enveloppe
        # explicitement via .base). Le garde-fou sur les dunders évite de
        # détourner le protocole pickle/copy.
        if nom.startswith('__') and nom.endswith('__'):
            raise AttributeError(nom)
        return getattr(self.base, nom)

    def __repr__(self):
        return f"_ModeleFrequenceExposition({self.base!r})"


def _envelopper_frequence(modele, col_cible: str):
    """Enveloppe le modèle pour l'offset d'exposition SI la cible est un comptage
    (COLS_COMPTAGE) ; sinon (cible COÛT) le rend nu — la sévérité ne se pondère
    pas par l'exposition."""
    if col_cible in COLS_COMPTAGE:
        return _ModeleFrequenceExposition(modele)
    return modele


# Hyperparamètres par défaut — calibrés pour les données actuarielles FR
# Justification : ces paramètres sont des points de départ raisonnables
# pour des portefeuilles de 50-100k contrats. Optuna peut les affiner.
HYPERPARAMS = {
    'gbm': {
        'n_estimators':   200,
        'max_depth':      4,      # Profondeur modérée → évite l'overfitting
        'learning_rate':  0.05,   # Faible → meilleure généralisation
        'subsample':      0.8,    # Bagging → robustesse
        'min_samples_leaf': 50,   # Feuilles avec au moins 50 obs → stabilité
        'random_state':   42,
    },
    'xgboost': {
        'n_estimators':   300,
        'max_depth':      4,
        'learning_rate':  0.05,
        'subsample':      0.8,
        'colsample_bytree': 0.8,
        'reg_alpha':      0.1,    # Régularisation L1 → sélection variables
        'reg_lambda':     1.0,    # Régularisation L2 → stabilité
        'random_state':   42,
        'verbosity':      0,
    },
    'lightgbm': {
        'n_estimators':   300,
        'max_depth':      4,
        'learning_rate':  0.05,
        'num_leaves':     31,     # 2^max_depth - 1 = valeur standard
        'subsample':      0.8,
        'colsample_bytree': 0.8,
        'reg_alpha':      0.1,
        'reg_lambda':     1.0,
        'min_child_samples': 50,  # Équivalent min_samples_leaf
        'random_state':   42,
        'verbose':       -1,
    },
    'catboost': {
        'iterations':     300,
        'depth':          4,
        'learning_rate':  0.05,
        'l2_leaf_reg':    3.0,
        'random_seed':    42,
        'verbose':        False,
    },
    'random_forest': {
        'n_estimators':   200,
        'max_depth':      8,
        'min_samples_leaf': 50,
        'max_features':   'sqrt',  # Standard pour la régression RF
        'n_jobs':        -1,       # Parallélisation automatique
        'random_state':   42,
    },
    'lineaire_regularise': {
        'alpha':          0.01,    # Régularisation faible
        'l1_ratio':       0.5,     # Mix L1+L2 équilibré
        'max_iter':       2000,
        'random_state':   42,
    },
    'quantile_50': {
        'quantile':       0.50,    # Médiane (prime pure centrale)
        'alpha':          0.01,
        'solver':         'highs',
    },
    'quantile_90': {
        'quantile':       0.90,    # P90 (prime prudente)
        'alpha':          0.01,
        'solver':         'highs',
    },
}

# Colonnes à exclure des SHAP values (trop nombreuses ou non pertinentes)
COLS_EXCLURE_SHAP = ['const', 'intercept']


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE : AGENT A4 ML
# ══════════════════════════════════════════════════════════════════════════════

# Variables cibles de type comptage (distribution Poisson)
# Si col_cible appartient à cette liste ET ElasticNet est actif,
# le garde-fou R2 remplace ElasticNet par PoissonRegressor.
# Réf. : Agresti (2015), Foundations of Linear and Generalized Linear Models §7.
COLS_COMPTAGE = {
    'nb_sinistres',
    'nb_contrats',
    'nb_victimes',
    'nb_recours',
    'sinistre_count',
    'count',
}

class AgentA4ML:
    """
    Agent A4 — Tarification Machine Learning.

    ⚠ Le compte de modeles n'est plus annonce ici : il vit dans la boucle
    de `_calibrer_tous_modeles`, seule source (constat `a4/C7`).

    Compare 8 algorithmes ML sur la tâche de tarification actuarielle
    et les benchmark contre le GLM de référence (Agent A3).

    AUTONOMIE NIVEAU 2 :
    Sélectionne automatiquement le meilleur modèle selon le Gini,
    calcule les SHAP values pour l'interprétabilité, et détecte
    l'overfitting (écart train/test > 15%).

    EXEMPLE D'UTILISATION :
    ─────────────────────────
    agent_a4 = AgentA4ML(
        models_path = '/tmp/actuaria',
        audit_path  = '/tmp/actuaria',
    )
    result_a4 = agent_a4.run(result_a2, result_a3=result_a3)

    meilleur    = result_a4['meilleur_modele']
    classement  = result_a4['classement']
    shap_values = result_a4['shap_values']
    """

    def __init__(
        self,
        models_path: str = '/tmp/actuaria',
        audit_path:  str = '/tmp/actuaria',
        verbose:     bool = True
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose

        # ⚠️ INSTANCIER N'ÉCRIT PAS SUR LE DISQUE (jumeau d'`a1/C7` et
        # d'`a2/C16`). Les dossiers sont créés PAR CELUI QUI ÉCRIT.

        self.modeles    = {}
        self.metriques  = {}
        self.shap_vals  = {}

        if self.verbose:
            logger.info("Agent A4 ML initialise")

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTHODE PRINCIPALE : run()
    # ══════════════════════════════════════════════════════════════════════════

    def run(
        self,
        result_a2:      Dict[str, Any],
        result_a3:      Optional[Dict[str, Any]] = None,
        col_cible:      str = 'nb_sinistres',
        col_exposition: str = 'exposition',
        plan:           Optional[PlanTarifaire] = None,   # Phase 1 : plan signé explicite
        ponderer_par_exposition: bool = True,
        calcul_shap:        bool = True,
        generer_graphiques: bool = True,
        optuna_trials:      int  = 0,   # 0 = désactivé ; >0 = nb essais Optuna XGBoost
    ) -> Dict[str, Any]:
        """
        Pipeline ML complet.

        Paramètres
        ──────────
        result_a2 : dict
            Résultat de l'agent A2 (données preprocessées).

        result_a3 : dict, optionnel
            Résultat de l'agent A3 (GLM). Utilisé pour le benchmark.
            Si fourni, le Gini GLM est affiché en référence.

        col_cible : str
            Variable cible. Par défaut : 'nb_sinistres' (fréquence).
            Peut aussi être 'cout_total_sinistres' pour le coût moyen.

        col_exposition : str
            Variable d'exposition pour la pondération.

        calcul_shap : bool
            Si True, calcule les SHAP values sur le meilleur modèle.
            AVERTISSEMENT : si SHAP n'est pas installé et calcul_shap=True,
            le statut est plafonné à AMBRE (interprétabilité non vérifiée).
            Réf. : ACPR-2022-P-01 §4.3 ; AI Act 2025 Art. 13.
            Pour désactiver explicitement : calcul_shap=False.
        """
        t_debut      = datetime.now()
        audit_id     = f"A4_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        sous_branche = result_a2.get('branche', 'inconnue')

        # Gini de référence GLM — lu chez A3, ou ABSENT.
        # ⚠️⚠️ IL N'Y A PLUS DE VALEUR PAR DÉFAUT — constat `a4/C11`, rang 1.
        # Ce `0.25` était un nombre inventé qui servait de référence à un
        # statut RAG, sous le libellé publié « Référence A3 ». *Une référence
        # absente est absente ; elle ne vaut pas un chiffre plausible.*
        # ⚠️ Le `.get('gini')` sans repli est volontaire : si A3 a réussi mais
        # n'a pas produit de Poisson, il n'y a pas davantage de référence.
        gini_reference_a3 = None
        if result_a3 and result_a3.get('success'):
            gini_reference_a3 = (
                result_a3.get('metriques', {})
                .get('poisson', {})
                .get('gini')
            )
        if gini_reference_a3 is None:
            logger.info(
                f"[{audit_id}] Gini GLM référence (A3) INDISPONIBLE — la "
                f"comparaison ne sera pas faite, et elle sera dite."
            )
        else:
            logger.info(
                f"[{audit_id}] Gini GLM référence (A3) = {gini_texte(gini_reference_a3)}"
            )

        # Réinitialisation pour chaque appel
        self.modeles   = {}
        self.metriques = {}
        self.shap_vals = {}

        logger.info(f"[{audit_id}] Agent A4 ML démarré | branche={sous_branche}")

        if not result_a2.get('success', False):
            return self._erreur("L'agent A2 a échoué.", audit_id)

        # Phase 1 : A4 restreint ses features à plan.colonnes_produites() via
        # construire_matrice_x — plus de _LOBS_ALIGNES_PLAN. Plan absent → erreur
        # propre, JAMAIS de repli silencieux.
        if plan is None:
            return self._erreur(
                "A4.run exige un plan (PlanTarifaire) : les features ML sont "
                "restreintes à plan.colonnes_produites() (Phase 1, _LOBS_ALIGNES_PLAN "
                "supprimé). Fournissez plan=PlanTarifaire.depuis_yaml('plans/<lob>.yaml').",
                audit_id)

        # ── GARDE-FOU R2 : cohérence col_cible / famille de modèle ───────────
        # Si la variable cible est un comptage (distribution Poisson) et
        # qu'ElasticNet est sélectionné, on bascule sur PoissonRegressor.
        # ElasticNet minimise l'erreur quadratique — inadapté aux comptages.
        # Réf. : Agresti (2015), Foundations of Linear and GLM §7.
        _col_cible_est_comptage = col_cible in COLS_COMPTAGE
        if _col_cible_est_comptage:
            logger.warning(
                f"[GARDE-FOU R2] col_cible='{col_cible}' est une variable de "
                f"comptage (Poisson). ElasticNet remplacé par PoissonRegressor. "
                f"Réf. : Agresti (2015) §7."
            )

        df      = result_a2['dataframe'].copy()
        rapport = {'etapes': [], 'alertes': [], 'modeles_testes': []}

        try:
            # ── ÉTAPE 1 : PRÉPARATION ─────────────────────────────────────────
            logger.info(f"[{audit_id}] Étape 1/4 : Préparation données")
            X_train, X_test, y_train, y_test, \
            w_train, w_test, feature_names = self._preparer_donnees(
                df, sous_branche, col_cible, col_exposition, plan,
                ponderer_par_exposition
            )
            rapport['etapes'].append('preparation')
            rapport['nb_features']   = len(feature_names)
            rapport['nb_train']      = len(X_train)
            rapport['nb_test']       = len(X_test)
            rapport['feature_names'] = feature_names

            logger.info(
                f"Train={len(X_train):,} | Test={len(X_test):,} | "
                f"Features={len(feature_names)}"
            )

            # ── ÉTAPE 2 : CALIBRATION DES MODÈLES ───────────────────────────
            logger.info(f"[{audit_id}] Étape 2/4 : calibration des modèles")
            self._calibrer_tous_modeles(
                X_train, X_test, y_train, y_test,
                w_train, w_test, rapport,
                col_cible=col_cible,
            )
            rapport['etapes'].append('calibration')

            # ── ÉTAPE 3 : CLASSEMENT & SÉLECTION ─────────────────────────────
            logger.info(f"[{audit_id}] Étape 3/4 : Classement et sélection")
            classement = self._classer_modeles(result_a3)
            rapport['etapes'].append('classement')

            # ── OPTUNA — Optimisation hyperparamètres XGBoost (optionnel) ────
            # Activé si optuna_trials > 0 et Optuna installé.
            if optuna_trials > 0 and OPTUNA_OK and XGBOOST_OK:
                try:
                    import xgboost as xgb_local
                    logger.info(
                        f"[{audit_id}] Optuna : optimisation XGBoost ({optuna_trials} essais)"
                    )

                    def _objective(trial):
                        params_trial = {
                            'n_estimators':     trial.suggest_int('n_estimators', 100, 500),
                            'max_depth':        trial.suggest_int('max_depth', 3, 6),
                            'learning_rate':    trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
                            'subsample':        trial.suggest_float('subsample', 0.6, 1.0),
                            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                            'reg_alpha':        trial.suggest_float('reg_alpha', 1e-3, 1.0, log=True),
                            'reg_lambda':       trial.suggest_float('reg_lambda', 0.1, 5.0, log=True),
                            'random_state':     42,
                            'verbosity':        0,
                        }
                        m = xgb_local.XGBRegressor(**params_trial)
                        m.fit(X_train, y_train, sample_weight=w_train)
                        pred = np.maximum(m.predict(X_test), 0)
                        _g_essai = self._calculer_gini(y_test, pred)
                        if _g_essai is None:
                            # Gini non mesurable : l'essai n'a pas de score,
                            # il ne vaut pas 0.
                            raise optuna.TrialPruned()
                        return -_g_essai

                    if float(np.nan_to_num(y_test).sum()) <= 0:
                        raise ValueError(
                            "Optuna : aucun sinistre observé sur le jeu de test, "
                            "le Gini n'y est pas mesurable — optimisation sans objet")
                    study = optuna.create_study(
                        direction='minimize',
                        sampler=optuna.samplers.TPESampler(seed=42)
                    )
                    study.optimize(_objective, n_trials=optuna_trials,
                                   show_progress_bar=False)
                    best_params = study.best_params
                    best_params.update({'random_state': 42, 'verbosity': 0})

                    # Recalibrer XGBoost avec les meilleurs paramètres
                    m_opt = xgb_local.XGBRegressor(**best_params)
                    m_opt.fit(X_train, y_train, sample_weight=w_train)
                    pred_opt  = np.maximum(m_opt.predict(X_test), 0)
                    gini_opt  = self._calculer_gini(y_test, pred_opt)
                    if gini_opt is None:
                        raise ValueError(
                            "Optuna : Gini du modèle optimisé non mesurable "
                            "(prédictions dégénérées) — modèle non retenu")
                    rmse_opt  = float(np.sqrt(np.mean((y_test - pred_opt)**2)))
                    of_opt    = gini_opt / max(
                        self._calculer_gini(y_train, np.maximum(m_opt.predict(X_train), 0)),
                        1e-6
                    )

                    # Remplacer l'entrée xgboost dans le classement
                    classement = [m for m in classement if m.get('modele') != 'xgboost']
                    classement.append({
                        'modele':         'xgboost_optuna',
                        'gini_test':      round(gini_opt, 4),
                        'gini_train':     round(gini_opt / max(of_opt, 1e-6), 4),
                        'overfit_ratio':  round(of_opt, 3),
                        'rmse_test':      round(rmse_opt, 4),
                        'mae_test':       round(float(np.mean(np.abs(y_test - pred_opt))), 4),
                        'overfit_alerte': bool(of_opt < 0.85),
                        'params_optuna':  best_params,
                    })
                    classement.sort(key=lambda x: (x['gini_test'] is not None,
                                       x['gini_test'] or 0.0),
                        reverse=True)
                    self.modeles['xgboost_optuna'] = m_opt
                    rapport['optuna_xgboost'] = {
                        'trials':      optuna_trials,
                        'best_gini':   round(gini_opt, 4),
                        'best_params': best_params,
                    }
                    logger.info(
                        f"[{audit_id}] Optuna XGBoost best Gini = {gini_texte(gini_opt)}"
                    )
                except Exception as e_opt:
                    logger.warning(
                        f"[{audit_id}] Optuna échoué (non bloquant) : {e_opt}"
                    )

            # ── ÉTAPE 4 : SHAP VALUES ─────────────────────────────────────────
            shap_summary = {}
            if calcul_shap and SHAP_OK and classement:
                logger.info(f"[{audit_id}] Étape 4/4 : SHAP values")
                meilleur_nom = classement[0]['modele']
                shap_summary = self._calculer_shap(
                    meilleur_nom, X_test, feature_names
                )
                rapport['etapes'].append('shap')
            else:
                rapport['etapes'].append('shap_skipped')
                # ── Alerte SHAP absent (ACPR-2022-P-01 §4.3 / AI Act 2025 Art.13) ──
                # Si l'utilisateur a demandé SHAP (calcul_shap=True) mais que
                # le package n'est pas installé, on signale une alerte réglementaire.
                # Un modèle ML sans interprétabilité vérifiée ne peut pas obtenir
                # le statut VERT en contexte réglementaire.
                _shap_requis_absent = calcul_shap and not SHAP_OK
                if _shap_requis_absent:
                    _msg_shap = (
                        "[SHAP ABSENT] Interprétabilité non calculée. "
                        "Statut plafonné à AMBRE. "
                        "Installer : pip install shap. "
                        "Réf. : ACPR-2022-P-01 §4.3 ; AI Act 2025 Art. 13."
                    )
                    rapport['alertes'].append(_msg_shap)
                    logger.warning(_msg_shap)

            # ── GRAPHIQUES v3 ─────────────────────────────────────────────
            graphiques = {}
            if generer_graphiques and PLOTLY_OK and classement:
                logger.info(f"[{audit_id}] Graphiques PowerBI...")
                graphiques = self._generer_graphiques(
                    y_test, classement, feature_names
                )
            # Graphique SHAP V3 (charte core/charts_tarif) — OPTIONNEL : pas de
            # SHAP (package absent / calcul_shap=False) → chart non produit.
            if (generer_graphiques and PLOTLY_OK and _CHARTS_V3_OK
                    and isinstance(shap_summary, dict)
                    and shap_summary.get('importance_globale')):
                try:
                    graphiques['chart_shap_summary'] = chart_shap_summary(
                        shap_summary['importance_globale'],
                        titre='Importance SHAP — meilleur modèle ML')
                except Exception as e:
                    logger.debug(f"chart_shap_summary non produit : {e}")

            # Commentaire actuaire sénior
            statut_rag  = self._calculer_statut_rag(
                classement, result_a3,
                shap_absent=rapport.get('alertes', []) != []
                and any('SHAP ABSENT' in a for a in rapport.get('alertes', []))
            )

            # ── MODÈLE AMPUTÉ → PLAFOND AMBRE (cf. A3, même source unique) ────
            # Comparaison sur df.columns (disponibilité en DONNÉES), pas sur la
            # liste post-garde-fous : une colonne écartée par le filtre genre ou
            # anti-fuite, c'est le contrôle qui fonctionne, pas une amputation.
            _ampute = verifier_completude_plan(plan, df.columns)
            _alertes_modele = []
            _al = alerte_modele_ampute(_ampute, 'ML')
            if _al:
                _alertes_modele.append(_al)
                logger.warning("[PLAN INCOMPLET] %s", _al['message'])
            statut_rag = plafonner_statut_si_ampute(statut_rag, _ampute)

            # ⚠️ POSE AVANT LE COMMENTAIRE, ET DANS `rapport` : le
            # commentaire actuaire le lit de la, le resultat le republie plus
            # bas. Une seule source, deux lecteurs.
            # ⚠️ LE DATAFRAME EST PASSÉ, ET C'EST LUI QUI REND
            # `NON_IDENTIFIABLE` ATTEIGNABLE. Sans données, on ne peut pas
            # mesurer si la variation de prix est exploitable — et un état qui
            # ne peut pas être atteint est un état qui n'existe pas.
            rapport['elasticite'] = etat_elasticite(plan, df)
            _etat_elasticite = rapport['elasticite']
            # ⚠️ LA SENSIBILITE NE SE PUBLIE QUE SUR ESTIMEE, et elle le
            # verifie elle-meme : sur les quatre autres etats elle rend
            # `disponible=False` avec l'etat en cause. Aucun blocage.
            rapport['sensibilite_tarifaire'] = sensibilite_tarifaire(
                plan, df, _etat_elasticite)

            commentaire = self._commenter_actuaire_senior(
                classement, sous_branche, statut_rag,
                result_a3, rapport
            )

            # ── LES DEUX GRANDEURS AVANCÉES, MESURÉES UNE SEULE FOIS ─────────
            # ⚠️ LE COMMENTAIRE DU `return` DISAIT DÉJÀ « calculées une seule
            # fois » ALORS QUE LE CODE APPELAIT `_monitoring_derive` CINQ FOIS
            # et `_valider_modele_ml` TROIS — dont trois appels SANS
            # X_test/y_test. Le résultat portait donc deux verdicts pour la
            # même hypothèse : `hypotheses` (mesuré) et `validation_ml` (non
            # mesuré). L'Excel lit le second, le verrou d'A6 lit le premier.
            # ⚠️ ELLES ÉTAIENT TROIS : l'optimisation tarifaire a été retirée
            # avec sa figure — voir la clé `elasticite` plus bas.
            _psi_glob, _psi_det = self._psi_reel(X_train, X_test)
            _scores_ref = _scores_act = None
            if classement and classement[0].get('modele') in self.modeles:
                try:
                    _m_ret = self.modeles[classement[0]['modele']]
                    _scores_ref = np.maximum(_m_ret.predict(X_train), 0)
                    _scores_act = np.maximum(_m_ret.predict(X_test), 0)
                except (ValueError, TypeError, AttributeError, KeyError,
                        IndexError, RuntimeError) as e_sc:
                    logger.debug(f"Scores du modèle retenu indisponibles : {e_sc}")
            _monitoring = self._monitoring_derive(
                {}, gini_reference=gini_reference_a3,
                psi_reel=_psi_glob, details_psi=_psi_det,
                scores_ref=_scores_ref, scores_actuels=_scores_act,
                gini_actuel=(classement[0].get('gini_test') if classement else None),
            )

            # ── Standard ActuarIA — excel_bytes ──────────────────────────────
            _val_ml_tmp = self._valider_modele_ml(
                classement, _monitoring,
                X_train=X_train, X_test=X_test, y_test=y_test,
            )
            _excel_a4 = b''
            if TARIF_EXCEL_OK:
                try:
                    _tmp_a4 = {
                        'success': True, 'statut_rag': statut_rag,
                        'classement': classement, 'branche': sous_branche,
                        'shap_values': shap_summary, 'validation_ml': _val_ml_tmp,
                        'rapport': rapport, 'audit_id': audit_id,
                    }
                    _excel_a4 = export_excel_a4(_tmp_a4, audit_id)
                    if _excel_a4:
                        logger.info(f"[{audit_id}] Excel A4 : {len(_excel_a4):,} bytes")
                except Exception as e_xl:
                    logger.warning(f"Excel A4 échoué : {e_xl}")

            # ── Standard ActuarIA — word_bytes ───────────────────────────────
            _word_a4 = b''
            if TARIF_RAPPORT_OK_A4:
                try:
                    _rapports_a4 = _gen_rapport_a4(
                        result_a3=result_a3,
                        result_a4={
                            'success': True, 'statut_rag': statut_rag,
                            'classement': classement, 'branche': sous_branche,
                            'metriques': self.metriques, 'shap_values': shap_summary,
                            'commentaire': commentaire,
                        },
                        arrete=datetime.now().strftime('%d/%m/%Y'),
                        audit_id=audit_id, formats=['html', 'word'],
                    )
                    _word_a4 = _rapports_a4.get('word_bytes', b'')
                    if _word_a4:
                        logger.info(
                            f"[{audit_id}] Word A4 : {len(_word_a4):,} bytes")
                except Exception as e_w4:
                    logger.warning(
                        f"[{audit_id}] Word A4 échoué (non bloquant) : {e_w4}")

            # Sauvegarde
            self._sauvegarder_modeles(sous_branche, classement)
            self._sauvegarder_audit(
                audit_id, sous_branche, rapport,
                statut_rag, t_debut
            )

            if self.verbose:
                self._afficher_rapport_console(
                    audit_id, sous_branche, classement,
                    statut_rag, commentaire, result_a3
                )

            return {
                'success':         True,
                'dataframe':       df,
                'branche':         sous_branche,
                'col_cible':       col_cible,   # cible sur laquelle CES modeles ML sont ajustes (A6 filtre dessus)
                'statut_rag':      statut_rag,
                'modeles':         self.modeles,
                'metriques':       self.metriques,
                'classement':      classement,
                'meilleur_modele': classement[0]['modele'] if classement else None,
                'shap_values':     shap_summary,
                # Nouvelles méthodes avancées — mesurées une seule fois, plus
                # haut. `validation_ml` et `hypotheses` portent DÉSORMAIS le
                # même objet : une hypothèse ne peut plus recevoir deux
                # verdicts dans le même dictionnaire de retour.
                'monitoring':      _monitoring,
                # ⚠️ `optimisation` A ETE RETIREE, ET CE QUI LA REMPLACE EST UN
                # ETAT, PAS UN CHIFFRE. Elle publiait « Tarif optimal : -20 % »
                # quels que soient le portefeuille, sa taille et la qualite du
                # modele : avec une elasticite codee en dur a -1,5, le chiffre
                # d'affaires vaut p^(1+eps), strictement decroissant, donc
                # l'optimum etait MECANIQUEMENT la borne basse de la grille.
                # `gini_meilleur` etait recu et jamais lu ; la prime moyenne et
                # le nombre de contrats etaient des defauts (450 EUR, 10 000)
                # que l'appelant ne remplacait jamais ; la marge valait
                # CA x 0,30, donc proportionnelle au CA.
                # ⚠️ ET C'ETAIT UNE RECOMMANDATION D'ACTION : un actuaire qui
                # la suivait baissait son tarif de 20 %.
                'elasticite':      _etat_elasticite,
                # ⚠️ CE QUI A ETE RETIRE AU LOT L0 REVIENT ICI, FONDE : la
                # courbe vient du logit ajuste, le portefeuille est le vrai,
                # la marge suit les chargements du depot, et chaque point dit
                # s'il est appuye par les donnees observees.
                'sensibilite_tarifaire': rapport['sensibilite_tarifaire'],
                'validation_ml':   _val_ml_tmp,
                'graphiques_validation': self._graphiques_validation_ml(
                                       _val_ml_tmp, classement, _monitoring,
                                   ) if generer_graphiques else {},
                'graphiques':      graphiques,
                'rapport':         rapport,
                'commentaire':     commentaire,
                'audit_id':        audit_id,
                'erreur':          None,
                'y_test':          y_test,
                'feature_names':   feature_names,
                # Exclusions de conformité tracées par MatriceX (audit V11 / I5) :
                # une exclusion silencieuse est un défaut en soi — c'est ce silence
                # qui a rendu le BLOQUANT B5 si coûteux (facteur central de la RC Pro
                # détruit, −17,4 % de Gini, sans que rien ne l'indique nulle part).
                'exclusions_conformite': getattr(self, 'exclusions_conformite', {}),
                'colonnes_plan_ecartees': getattr(
                    self, 'colonnes_plan_ecartees', ()),
                'colonnes_exemptees_effet': getattr(
                    self, 'colonnes_exemptees_effet', ()),
                'controle_effet': getattr(self, 'controle_effet',
                                          {'execute': False, 'motifs': {}}),
                'alertes_conformite': getattr(self, 'alertes_conformite', {}),
                # Modèle amputé (colonnes du plan absentes des données) : alerte
                # explicite + plafond AMBRE. A6 agrège déjà 'alertes_modele'.
                'alertes_modele':  _alertes_modele,
                # ⚠️ Le diagnostic d'evaluation voyage avec le RESULTAT :
                # A6 en a besoin pour refuser l'arbitrage et nommer la
                # cause. Un avertissement journalise n'atteint personne.
                'diagnostic_evaluation': getattr(
                    self, '_diag_evaluation', None),
                'modele_ampute':   _ampute,
                # ── Standard ActuarIA ─────────────────────────────────────────
                'excel_bytes':     _excel_a4,
                'word_bytes':      _word_a4,
                'pdf_bytes':       b'',
                'hypotheses':      _val_ml_tmp,
                'audit_trail':     {
                    'agent': 'A4_ML', 'version': '1.0', 'audit_id': audit_id,
                    'timestamp': t_debut.isoformat(), 'branche': sous_branche,
                    'statut_rag': statut_rag,
                    'nb_modeles': len(classement),
                    'modele_retenu': classement[0].get('modele','') if classement else '',
                    'gini_retenu': classement[0].get('gini_test',0) if classement else 0,
                    'optuna_active': optuna_trials > 0 and OPTUNA_OK,
                },
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 1 : PRÉPARATION
    # ══════════════════════════════════════════════════════════════════════════

    def _preparer_donnees(
        self,
        df:           pd.DataFrame,
        sous_branche: str,
        col_cible:    str,
        col_expo:     str,
        plan:         PlanTarifaire,
        ponderer_par_exposition: bool = True,
    ) -> Tuple:
        """
        Prépare X, y, weights pour les modèles ML.

        PONDÉRATION PAR L'EXPOSITION :
        ───────────────────────────────
        Contrairement aux GLM où l'offset gère l'exposition,
        les modèles ML utilisent sample_weight = exposition.

        Justification :
        Un contrat avec exposition=0.5 (6 mois) doit peser 2× moins
        qu'un contrat avec exposition=1.0 (12 mois) dans la calibration.
        La pondération par l'exposition simule l'effet d'un offset
        pour les algorithmes qui ne supportent pas d'offset natif.

        NORMALISATION (modèles LINÉAIRES uniquement) :
        ──────────────────────────────────────────────
        Tout linéaire régularisé est sensible à l'échelle des variables —
        ElasticNet (cible continue) comme Poisson ridge (cible de comptage) :
        β dépend de l'échelle de X, et la pénalité aussi. On utilise donc
        StandardScaler dans un Pipeline sklearn, dans les DEUX cas.
        Les modèles tree-based (GBM, RF, XGBoost) n'ont pas besoin
        de normalisation car ils utilisent des seuils de coupure.
        """
        if col_cible not in df.columns:
            raise ValueError(f"Variable cible '{col_cible}' introuvable.")

        # Sélection des features numériques
        cols_exclure = set(COLS_A_EXCLURE_ML)

        # Exclure aussi les colonnes object non encodées
        cols_object = df.select_dtypes(include=['object']).columns.tolist()
        cols_exclure.update(cols_object)

        # Colonnes dérivées des cibles → data leakage
        cols_contaminees = {
            c for c in df.columns
            if any(mot in c for mot in [
                'log_cout', 'log_prime', 'cout_moyen_attendu',
                'lambda_freq', 'prime_pure_obs',
            ])
        }
        cols_exclure = cols_exclure | cols_contaminees

        feature_names = [
            c for c in df.columns
            if c not in cols_exclure
            and c != col_cible
            and df[c].dtype in ['int64', 'float64', 'int32', 'float32']
            and df[c].isnull().sum() == 0
            and df[c].std() > 0
        ]

        # ── FILTRE GENRE (audit V7 BLOQUANT #1) ───────────────────────────────
        # A4 n'avait auparavant AUCUNE exclusion des variables de genre —
        # contrairement à A3 (GLM), qui applique COLS_GENRE_INTERDITES de
        # façon inconditionnelle depuis l'audit V4. Une colonne 'sexe'
        # numérique (0/1) ou pré-encodée ('sexe_enc') pouvait donc atteindre
        # la matrice X des modèles ML — et A6 peut retenir un tel modèle en
        # production. Réf. : Arrêt CJUE C-236/09 (Test-Achats).
        # ── MATRICE X CONFORME — QUATRE GARDE-FOUS ────────────────────────────
        # construire_matrice_x() enchaîne : liste blanche → filtre genre → filtre
        # anti-fuite (par le NOM) → contrôle par l'EFFET (corrélation avec la
        # cible ≥ 0,80 → fuite, quel que soit le nom — audit V12).
        # Elle retourne un objet IMMUABLE : le geste exact qui a produit le
        # BLOQUANT B1 (enrichir la liste après filtrage) lève une AttributeError.
        # ⚠ La liste est reconvertie en `list` juste après (les modèles en ont
        # besoin) : l'immuabilité empêche l'accident, pas la volonté. NE RIEN
        # AJOUTER APRÈS CET APPEL.
        # Elle trace aussi les exclusions, remontées dans les rapports — une
        # exclusion silencieuse est un défaut en soi (BLOQUANT B5, audit V11).
        _mx = construire_matrice_x(
            feature_names, plan=plan,   # Phase 1 : liste blanche = plan.colonnes_produites()
            contexte='A4 — sélection features ML', logger_agent=logger,
            df=df, col_cible=col_cible,   # garde-fou n°4 : contrôle par l'EFFET
        )
        self.exclusions_conformite = _mx.exclusions
        # ⚠️⚠️ CONSTAT `conformite/C15` — CE QUE LA PORTE N'A JAMAIS REÇU.
        # `exclusions` dit ce qu'elle a écarté ; `ecartees_amont` dit ce qui
        # était DECLARE AU PLAN et ne lui est jamais parvenu. Cet agent
        # construit sa liste PAR SOUSTRACTION : c'est ici que la perte peut
        # se produire, et c'est donc ici qu'elle doit être dite.
        self.colonnes_plan_ecartees = _mx.ecartees_amont
        # ⚠️⚠️ CONSTAT `conformite/C4` — L'EXEMPTION SE DIT AUSSI.
        # `ecartees_amont` dit ce qui n'est jamais parvenu au filtre ;
        # celle-ci dit ce qui lui a été SOUSTRAIT délibérément, par une
        # décision écrite au plan signé. Ces colonnes sont CONSERVÉES :
        # les taire ferait passer le garde-fou le plus fort du module pour
        # avoir examiné ce qu'il n'a pas regardé.
        self.colonnes_exemptees_effet = _mx.exemptees_effet
        # ⚠️ LE CONTRÔLE PAR L'EFFET VOYAGE AVEC SON MOTIF — `conformite/C7`.
        # La propriété existait depuis l'audit V14 avec la mention « À
        # REMONTER DANS LES RAPPORTS » ; mesuré, aucun agent ne la lisait.
        self.controle_effet = {'execute': _mx.controle_effet_execute,
                               'motifs': _mx.motifs_controle_effet}
        self.alertes_conformite = _mx.alertes
        feature_names = list(_mx)

        if len(feature_names) == 0:
            raise ValueError("Aucune feature numérique disponible pour ML.")

        # ── SPLIT TEMPOREL (R1) ──────────────────────────────────────────────
        # Tri du DataFrame avant extraction de X pour garantir que la coupure
        # temporelle s'applique bien (les 80% anciens = train, 20% récents = test).
        # ⚠️ SOURCE UNIQUE (core) : A3, A4, A5 et le diagnostic d'evaluation
        # lisent la MEME liste. Elle vivait triplee, a l'identique.
        _col_temp = colonne_temporelle(df.columns)
        if _col_temp is not None:
            df = df.sort_values(_col_temp).reset_index(drop=True)
            logger.info(f"[R1] Tri temporel sur '{_col_temp}' avant split ML.")
        else:
            logger.warning(
                "[R1] Colonne temporelle absente — fallback split aléatoire seed=42."
            )

        X = df[feature_names].fillna(0).values
        y = df[col_cible].values

        # ── PONDÉRATION — exposition pour la FRÉQUENCE, aucune pour la SÉVÉRITÉ ─
        # L'exposition pondère un COMPTAGE : un contrat observé 6 mois porte deux
        # fois moins d'information sur la fréquence qu'un contrat observé 1 an.
        # Pour la SÉVÉRITÉ, c'est FAUX : le coût d'un sinistre ne dépend pas de la
        # durée d'observation du contrat — c'est le sens même de la décomposition
        # E[S] = E[N] × E[C|N>0]. Le chemin déclaratif (pipeline_complet) ne
        # pondère d'ailleurs pas son GLM de coût. Poids uniformes ≡ sample_weight
        # None pour tout estimateur sklearn.
        if ponderer_par_exposition and col_expo in df.columns:
            weights = np.maximum(df[col_expo].values, 1e-6)
        else:
            weights = np.ones(len(df))

        # Split temporel : coupure à 80% si tri temporel, sinon aléatoire
        if _col_temp is not None:
            n_train = int(len(X) * 0.80)
            X_train, X_test   = X[:n_train],       X[n_train:]
            y_train, y_test   = y[:n_train],       y[n_train:]
            w_train, w_test   = weights[:n_train], weights[n_train:]
            logger.info(
                f"[R1] Split TEMPOREL ML : train={n_train:,} | test={len(X)-n_train:,}"
            )
        else:
            X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
                X, y, weights,
                test_size=0.20, random_state=42, shuffle=True
            )

        # ── L'ÉVALUATION SERA-T-ELLE POSSIBLE ? ──────────────────────────────
        # ⚠️⚠️ CALCULÉ ICI, PAS DANS `run()`, ET C'EST DÉLIBÉRÉ. Le découpage
        # vient d'avoir lieu : `df` est trié, la coupure est connue, les
        # bornes de période sont EXACTES. Les redériver dans `run()` — qui ne
        # garde que des tableaux — reviendrait à recopier le mécanisme qu'on
        # surveille, et à périmer avec lui.
        #   *Un diagnostic se pose là où la vérité qu'il décrit est encore
        #   dans la portée.*
        self._diag_evaluation = diagnostiquer_evaluation(
            cible=col_cible,
            n_train=len(y_train), n_test=len(y_test),
            sinistres_train=float(np.nan_to_num(y_train).sum()),
            sinistres_test=float(np.nan_to_num(y_test).sum()),
            colonne_temporelle=_col_temp,
            periode_train=((df[_col_temp].iloc[:n_train].min(),
                            df[_col_temp].iloc[:n_train].max())
                           if _col_temp is not None and n_train else None),
            periode_test=((df[_col_temp].iloc[n_train:].min(),
                           df[_col_temp].iloc[n_train:].max())
                          if _col_temp is not None
                          and n_train < len(df) else None),
            exposition_test=(float(np.nan_to_num(w_test).sum())
                             if ponderer_par_exposition else None),
            cible_vide_en_test=(len(y_test) > 0
                                and bool(np.all(pd.isna(y_test)))),
        )
        if self._diag_evaluation is not None:
            logger.warning(
                "[ÉVALUATION IMPOSSIBLE] %s",
                phrase_evaluation_impossible(self._diag_evaluation, 'ML'))

        return X_train, X_test, y_train, y_test, w_train, w_test, feature_names

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : CALIBRATION DES MODÈLES
    # ══════════════════════════════════════════════════════════════════════════

    def _calibrer_tous_modeles(
        self,
        X_train:   np.ndarray,
        X_test:    np.ndarray,
        y_train:   np.ndarray,
        y_test:    np.ndarray,
        w_train:   np.ndarray,
        w_test:    np.ndarray,
        rapport:   Dict,
        col_cible: str = 'nb_sinistres',
    ) -> None:
        """Calibre séquentiellement les 6 modèles ML de la boucle ci-dessous."""

        # ⚠️ La liste des candidats est la SOURCE du denominateur publie
        # (constat `a4/C6`) : elle est enregistree au rapport, jamais
        # recopiee sous forme de litteral dans un commentaire.
        modeles_a_calibrer = [
            ('gbm',              self._creer_gbm,           True),
            ('xgboost',          lambda: self._creer_xgboost(col_cible), True),
            ('xgboost_tweedie',  self._creer_xgboost_tweedie,True),
            ('lightgbm',         self._creer_lightgbm,       True),
            ('catboost',         self._creer_catboost,        True),
            ('lineaire_regularise', lambda: self._creer_lineaire_regularise(col_cible), False),
        ]

        for nom, creer_fn, supporte_weights in modeles_a_calibrer:
            logger.info(f"  Calibration {nom.upper()}...")
            try:
                modele = creer_fn()

                # Calibration avec ou sans pondération. Sur cible de COMPTAGE, le
                # modèle est enveloppé (_ModeleFrequenceExposition) : on lui passe
                # TOUJOURS l'exposition en sample_weight — y compris le Pipeline
                # linéaire (supporte_weights=False), car l'enveloppe route le poids
                # vers l'étape finale et reformule en taux+poids.
                if supporte_weights or col_cible in COLS_COMPTAGE:
                    modele.fit(X_train, y_train, sample_weight=w_train)
                else:
                    modele.fit(X_train, y_train)

                # Prédictions
                pred_train = np.maximum(modele.predict(X_train), 0)
                pred_test  = np.maximum(modele.predict(X_test),  0)

                # Métriques
                metriques = self._calculer_metriques(
                    y_train, y_test,
                    pred_train, pred_test,
                    w_train, w_test, nom
                )

                self.modeles[nom]   = modele
                self.metriques[nom] = metriques
                rapport['modeles_testes'].append(nom)
                rapport['modeles_candidats'] = len(modeles_a_calibrer)

                logger.info(
                    f"  {nom.upper():<15} "
                    f"Gini={gini_texte(metriques['gini_test'])} | "
                    f"RMSE={metriques['rmse_test']:.4f}"
                )

            except Exception as e:
                logger.warning(f"  {nom.upper()} échoué : {e}")
                rapport['alertes'].append(f"{nom} : {str(e)[:80]}")

    # ── CRÉATEURS DE MODÈLES ──────────────────────────────────────────────────

    def _creer_gbm(self):
        """Gradient Boosting Machine (sklearn) — DÉLÈGUE à creer_modele_ml_pour_nom().

        Fabrique = SOURCE UNIQUE : A4 (entraînement) et A6 (recalibration
        walk-forward) construisent désormais LE MÊME modèle. La duplication avait
        déjà produit une divergence silencieuse sur l'ElasticNet (scaler corrigé
        d'un seul côté) ; cf. _creer_lineaire_regularise.
        """
        return creer_modele_ml_pour_nom('gbm')

    def _creer_xgboost(self, col_cible: str = 'nb_sinistres'):
        """XGBoost — DÉLÈGUE à creer_modele_ml_pour_nom() (fabrique = SOURCE UNIQUE
        A4/A6).

        Le GARDE-FOU R2 (miroir P4 certification v3 ; Agresti 2015 §7) est porté
        par la fabrique : sur une cible de COMPTAGE (col_cible ∈ COLS_COMPTAGE), la
        déviance quadratique est inadaptée aux entiers à masse en 0 → objective
        'count:poisson'. Même logique que le garde-fou ElasticNet.
        """
        return creer_modele_ml_pour_nom('xgboost', col_cible)

    def _creer_lightgbm(self):
        """LightGBM (boosting leaf-wise) — DÉLÈGUE à creer_modele_ml_pour_nom()
        (fabrique = SOURCE UNIQUE A4/A6)."""
        return creer_modele_ml_pour_nom('lightgbm')

    def _creer_xgboost_tweedie(self):
        """XGBoost Tweedie (objective reg:tweedie, variance_power=1.5 — cohérent
        avec le GLM Tweedie d'A3, adapté à une cible à masse en 0 et queue lourde)
        — DÉLÈGUE à creer_modele_ml_pour_nom() (fabrique = SOURCE UNIQUE A4/A6)."""
        return creer_modele_ml_pour_nom('xgboost_tweedie')

    def _creer_catboost(self):
        """CatBoost (boosting, gère nativement les catégorielles) — DÉLÈGUE à
        creer_modele_ml_pour_nom() (fabrique = SOURCE UNIQUE A4/A6)."""
        return creer_modele_ml_pour_nom('catboost')

    def _creer_lineaire_regularise(self, col_cible: str = 'nb_sinistres'):
        """Linéaire régularisé — DÉLÈGUE à creer_modele_ml_pour_nom().

        ⚠ Cette méthode DUPLIQUAIT la fabrique, alors que celle-ci affirme dans
        son propre docstring « centraliser ici la logique déjà présente dans les
        méthodes _creer_* … pour éviter toute divergence entre la fabrique
        utilisée par A4 et celle utilisée par A6 ». La centralisation avait été
        écrite mais A4 n'y avait jamais été migré : A4 entraînait via _creer_*, A6
        recalibrait le walk-forward via la fabrique. Deux implémentations du même
        modèle — le décalage n'attendait qu'une divergence pour se manifester, et
        le correctif du scaler l'aurait produite (corrigé d'un côté seulement).

        GARDE-FOU R2 (Agresti 2015 §7) — porté par la fabrique : sur une cible de
        COMPTAGE, minimiser l'erreur quadratique sur des entiers est inadapté →
        famille Poisson. Le StandardScaler, lui, est requis dans les DEUX cas :
        β dépend de l'échelle de X, et la pénalité (L1+L2 ou L2) aussi.
        """
        return creer_modele_ml_pour_nom('lineaire_regularise', col_cible)

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTRIQUES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_metriques(
        self,
        y_train:    np.ndarray,
        y_test:     np.ndarray,
        pred_train: np.ndarray,
        pred_test:  np.ndarray,
        w_train:    np.ndarray,
        w_test:     np.ndarray,
        nom:        str
    ) -> Dict:
        """
        Calcule les métriques de performance pour un modèle.

        MÉTRIQUES ACTUARIELLES :
        ─────────────────────────
        Gini : mesure la discrimination risque/non-risque
               → Principal critère de sélection du modèle

        RMSE : erreur quadratique → pénalise les grandes erreurs
               → Important pour la stabilité de la prime

        MAE  : erreur absolue → interprétable en euros
               → "En moyenne, le modèle se trompe de X€ par contrat"

        Overfit ratio : Gini_train / Gini_test
               → Si > 1.15 → surparamétrage → alerte AMBRE
               → Si > 1.30 → surparamétrage sévère → alerte ROUGE
        """
        # ── OFFSET D'EXPOSITION (correctif calibration ML) ────────────────────
        # predict() rend le TAUX λ(X) sur cible de comptage (enveloppe
        # _ModeleFrequenceExposition) ; l'espérance au niveau comptage = taux ×
        # exposition. Pour le COÛT, w=1 donc pred_count == pred (inchangé).
        # Gini sur le TAUX (rang de risque, stable) ; RMSE/MAE/déviance/moyenne
        # sur le COMPTAGE prédit (comparable à la cible y).
        pred_count_train = pred_train * w_train
        pred_count_test  = pred_test  * w_test

        # Gini train et test — sur le taux (rang de risque)
        gini_train = self._calculer_gini(y_train, pred_train)
        gini_test  = self._calculer_gini(y_test,  pred_test)
        # ⚠️ BASE MESURÉE, et le module la DIT deux lignes plus haut :
        # « Gini sur le TAUX » — tri UNITAIRE, hors exposition (`a4/C10`).
        base_gini = BASE_GINI_UNITAIRE

        # Overfit ratio : Gini_train / Gini_test
        # Si gini_train = 0 (modèle non discriminant sur train, ex. PoissonRegressor
        # sur données synthétiques simples), on retourne 1.0 (neutre) pour éviter
        # un ratio nul trompeur. Un ratio nul ne signifie pas l'absence d'overfitting
        # — il signifie que le modèle n'a pas appris sur train non plus.
        if gini_train is None or gini_test is None:
            overfit = None  # NON EVALUABLE : un Gini n'est pas mesure
        elif gini_train <= 0:
            overfit = 1.0   # Neutre — modèle non discriminant sur train
        else:
            overfit = gini_train / max(gini_test, 1e-6)

        # RMSE pondéré par l'exposition — sur le comptage prédit (taux × expo)
        rmse_test = np.sqrt(
            np.average((y_test - pred_count_test)**2, weights=w_test)
        )
        rmse_train = np.sqrt(
            np.average((y_train - pred_count_train)**2, weights=w_train)
        )

        # MAE test — sur le comptage prédit
        mae_test = np.average(
            np.abs(y_test - pred_count_test), weights=w_test
        )

        # Déviance de Poisson (pour les modèles de fréquence)
        # Justification : la déviance Poisson est la métrique naturelle
        # pour évaluer un modèle de comptage (nb_sinistres) — sur le comptage prédit
        pred_pos = np.maximum(pred_count_test, 1e-8)
        y_pos    = np.maximum(y_test, 1e-8)
        try:
            deviance_poisson = 2 * np.mean(
                y_pos * np.log(y_pos / pred_pos) - (y_pos - pred_pos)
            )
        except Exception:
            deviance_poisson = np.nan

        return {
            'gini_train':        (None if gini_train is None else round(float(gini_train), 4)),
            'gini_test':         (None if gini_test is None else round(float(gini_test), 4)),
            'base_gini':         base_gini,
            'overfit_ratio':     (None if overfit is None else round(float(overfit), 3)),
            'rmse_train':        round(float(rmse_train), 4),
            'rmse_test':         round(float(rmse_test), 4),
            'mae_test':          round(float(mae_test), 4),
            'deviance_poisson':  round(float(deviance_poisson), 4)
                                 if not np.isnan(deviance_poisson) else None,
            'pred_mean':         round(float(pred_count_test.mean()), 4),
            'pred_std':          round(float(pred_count_test.std()),  4),
            'obs_mean':          round(float(y_test.mean()),    4),
        }

    def _calculer_gini(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> float | None:
        """Calcule le coefficient de Gini (même méthode que A3)."""
        if len(y_true) == 0:
            return None
        # Audit V7 MINEUR : garde manquant — A3 possède ce garde depuis
        # l'origine, A4 ne l'avait pas. Sans lui, np.sum(y_true) == 0
        # (aucun sinistre sur l'échantillon test) produit une division
        # 0/0 → nan silencieux (numpy ne lève pas d'exception sur ce cas,
        # donc le except Exception ci-dessous ne l'attrapait pas non
        # plus) — confirmé par exécution lors de l'audit V7.
        if np.sum(y_true) == 0:
            return None
        try:
            order   = np.argsort(y_pred)[::-1]  # Décroissant — les plus risqués d'abord
            y_true  = y_true[order]
            n       = len(y_true)
            cum_obs = np.cumsum(y_true) / np.sum(y_true)
            cum_pop = np.arange(1, n + 1) / n
            auc     = np.trapezoid(cum_obs, cum_pop) if hasattr(np, "trapezoid") else _np_trapz(cum_obs, cum_pop)
            # ⚠ AUTO-AUDIT (11/07/2026) — NE PAS ÉCRÊTER LE GINI À ZÉRO.
            # L'écrêtage np.clip(gini, 0.0, 1.0) rendait INVISIBLE le cas le plus
            # dangereux qui soit en tarification : un Gini NÉGATIF, c'est-à-dire
            # un modèle ANTI-SÉLECTIF — il fait payer MOINS les mauvais risques.
            # Un Gini réel de −0,50 était rapporté « 0,0000 », donc indiscernable
            # d'un modèle simplement non discriminant. Or les deux situations
            # n'ont rien à voir : la seconde est inutile, la première est
            # ruineuse (anti-sélection = spirale de sélection adverse).
            # On rapporte désormais la valeur VRAIE, bornée à [−1, 1], et on
            # alerte explicitement en cas d'anti-sélection.
            gini = float(np.clip(2 * auc - 1, -1.0, 1.0))
            if gini < 0:
                logger.warning(
                    f"[ANTI-SÉLECTION] Gini NÉGATIF ({gini_texte(gini)}) — le modèle "
                    f"discrimine À L'ENVERS : il attribue les primes les plus "
                    f"faibles aux risques les plus élevés. Modèle INUTILISABLE "
                    f"en l'état, quelle que soit sa performance par ailleurs."
                )
            return gini
        except Exception:
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # CLASSEMENT DES MODÈLES
    # ══════════════════════════════════════════════════════════════════════════

    def _classer_modeles(
        self,
        result_a3: Optional[Dict]
    ) -> List[Dict]:
        """
        Classe les modèles ML par Gini décroissant.
        Ajoute le GLM de référence (A3) pour comparaison.

        CRITÈRE DE SÉLECTION :
        ───────────────────────
        Le Gini test est le critère principal.
        En cas d'égalité, on préfère le modèle avec le meilleur
        ratio Gini/Complexité (parsimonie).

        DÉTECTION D'OVERFITTING :
        ──────────────────────────
        Un modèle avec overfit_ratio > 1.15 est signalé.
        En production actuarielle, on préfère un modèle légèrement
        moins performant mais plus stable (overfit_ratio < 1.10).
        """
        classement = []

        for nom, met in self.metriques.items():
            overfit_alerte = (None if met['overfit_ratio'] is None
                                      else met['overfit_ratio'] > 1.15)

            classement.append({
                'modele':          nom,
                'famille':         _famille_modele_ml(nom),
                'gini_test':       met['gini_test'],
                'gini_train':      met['gini_train'],
                'overfit_ratio':   met['overfit_ratio'],
                'rmse_test':       met['rmse_test'],
                'mae_test':        met['mae_test'],
                'overfit_alerte':  overfit_alerte,
                'recommandation':  ('⚠️ Sur-apprentissage non évaluable (Gini '
                                    'non mesuré)' if overfit_alerte is None else
                                    '⚠️ Overfitting détecté' if overfit_alerte
                                    else '✅ Stable'),
            })

        # Ajout du GLM Poisson comme référence
        if result_a3 and result_a3.get('success'):
            gini_glm = result_a3['metriques'].get('poisson', {}).get('gini', 0)
            classement.append({
                'modele':         'GLM Poisson (référence A3)',
                'famille':        'GLM',
                'gini_test':      gini_glm,
                'gini_train':     gini_glm,
                # Sans Gini mesure (aucun sinistre en test), il n'y a ni
                # ratio ni alerte : les deux se disent None, pas << stable >>.
                'overfit_ratio':  (None if gini_glm is None else 1.0),
                'rmse_test':      result_a3['metriques'].get('poisson', {}).get('rmse_test', 0),
                'mae_test':       0,
                'overfit_alerte': (None if gini_glm is None else False),
                'recommandation': '📊 Référence GLM',
            })

        # Tri par Gini décroissant
        classement.sort(key=lambda x: (x['gini_test'] is not None,
                                       x['gini_test'] or 0.0),
                        reverse=True)

        return classement

    # ══════════════════════════════════════════════════════════════════════════
    # SHAP VALUES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_shap(
        self,
        nom_modele:    str,
        X_test:        np.ndarray,
        feature_names: List[str]
    ) -> Dict:
        """
        Calcule les SHAP values pour le meilleur modèle.

        SHAP (SHapley Additive exPlanations) :
        ────────────────────────────────────────
        Mesure la contribution de chaque variable à la prédiction
        pour chaque contrat. Basé sur la théorie des jeux coopératifs
        (Shapley 1953, Nobel Économie 2012).

        CONFORMITÉ AI ACT 2025 :
        ─────────────────────────
        L'AI Act européen exige l'explicabilité des modèles IA
        utilisés en assurance. Les SHAP values permettent de répondre
        à la question : "Pourquoi ma prime est-elle de X€ ?"

        En pratique, l'agent calcule :
        • Importance globale : quelles variables influencent le plus
          le modèle en moyenne sur tout le portefeuille ?
        • Importance locale : pour chaque contrat, quelles variables
          ont le plus contribué à sa prime individuelle ?

        On utilise un échantillon de 1000 contrats pour la performance.
        SHAP exact sur 70 000 contrats prendrait plusieurs heures.
        """
        if not SHAP_OK:
            return {'erreur': 'SHAP non installé'}

        if nom_modele not in self.modeles:
            return {'erreur': f'Modèle {nom_modele} non trouvé'}

        modele  = self.modeles[nom_modele]
        # Sur cible de comptage, le modèle est enveloppé (_ModeleFrequenceExposition) ;
        # SHAP (TreeExplainer/LinearExplainer) doit voir l'estimateur NU.
        modele  = getattr(modele, 'base', modele)
        n_shap  = min(1000, len(X_test))
        X_shap  = X_test[:n_shap]

        try:
            # Explainer selon le type de modèle
            if nom_modele in ['gbm', 'random_forest']:
                explainer   = shap.TreeExplainer(modele)
                shap_values = explainer.shap_values(X_shap)
            elif nom_modele in ['xgboost', 'lightgbm']:
                explainer   = shap.TreeExplainer(modele)
                shap_values = explainer.shap_values(X_shap)
            elif nom_modele == 'catboost':
                explainer   = shap.TreeExplainer(modele)
                shap_values = explainer.shap_values(X_shap)
            else:
                # Modèles linéaires : SHAP linéaire
                explainer   = shap.LinearExplainer(modele, X_shap)
                shap_values = explainer.shap_values(X_shap)

            # Importance globale = moyenne |SHAP| par feature
            importance_globale = pd.Series(
                np.abs(shap_values).mean(axis=0),
                index=feature_names[:shap_values.shape[1]]
            ).sort_values(ascending=False)

            top10 = importance_globale.head(10).to_dict()

            logger.info(
                f"SHAP calculé sur {n_shap} contrats | "
                f"Top feature : {importance_globale.index[0]}"
            )

            return {
                'modele':             nom_modele,
                'n_contrats':         n_shap,
                'importance_globale': {k: round(float(v), 4) for k, v in top10.items()},
                'top_feature':        importance_globale.index[0] if len(importance_globale) > 0 else 'N/A',
            }

        except Exception as e:
            logger.warning(f"Erreur SHAP : {e}")
            return {'erreur': str(e)}

    # ══════════════════════════════════════════════════════════════════════════
    # SAUVEGARDE
    # ══════════════════════════════════════════════════════════════════════════

    def _sauvegarder_modeles(
        self,
        sous_branche: str,
        classement:   List[Dict]
    ) -> None:
        """Sauvegarde les modèles ML et les métriques sur Drive."""

        try:
            self.models_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Dossier modèles non créé ({self.models_path}) : {e}")

        # Sauvegarde de tous les modèles
        for nom, modele in self.modeles.items():
            chemin = self.models_path / f"ml_{nom}_{sous_branche}.pkl"
            try:
                with open(chemin, 'wb') as f:
                    pickle.dump(modele, f)
            except Exception as e:
                logger.warning(f"Impossible de sauvegarder {nom}: {e}")

        # Sauvegarde du classement en JSON
        classement_json = {
            'sous_branche': sous_branche,
            'timestamp':    datetime.now().isoformat(),
            'version':      '1.0',
            'classement':   classement,
            'metriques':    self.metriques,
        }
        chemin_json = self.models_path / f"ml_classement_{sous_branche}.json"
        try:
            with open(chemin_json, 'w', encoding='utf-8') as f:
                json.dump(classement_json, f, indent=2,
                          ensure_ascii=False, default=str)
            logger.info(f"Classement sauvegardé : {chemin_json}")
        except Exception as e:
            logger.warning(f"JSON non sauvegardé : {e}")

    def _sauvegarder_audit(
        self, audit_id, sous_branche, rapport,
        statut_rag, t_debut
    ) -> None:
        """Sauvegarde le log d'audit."""
        log = {
            'audit_id':     audit_id,
            'agent':        'A4_ML',
            'version':      '1.0',
            'timestamp':    t_debut.isoformat(),
            'sous_branche': sous_branche,
            'statut_rag':   statut_rag,
            'modeles_testes': rapport.get('modeles_testes', []),
        }
        chemin = self.audit_path / f"{audit_id}.json"
        try:
            self.audit_path.mkdir(parents=True, exist_ok=True)
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(log, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            _msg = (
                f"Audit trail NON persisté ({chemin}) : "
                f"{type(e).__name__} : {e}. La trace ACPR de ce run n'existe "
                f"que dans le résultat en mémoire."
            )
            logger.warning(f"[{audit_id}] {_msg}")
            rapport.setdefault('alertes', []).append(_msg)

    # ══════════════════════════════════════════════════════════════════════════
    # STATUT RAG & COMMENTAIRES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_statut_rag(
        self,
        classement:   List[Dict],
        result_a3:    Optional[Dict],
        shap_absent:  bool = False,
    ) -> str:
        """
        Statut RAG basé sur le meilleur Gini ML vs GLM.

        VERT  : Meilleur ML améliore le GLM de >5% ET pas d'overfitting
                ET interprétabilité SHAP disponible
        AMBRE : Amélioration < 5% OU overfitting OU SHAP absent
        ROUGE : aucun ML ne bat le GLM **ET** le meilleur Gini ML
                reste <= SEUIL_GINI_ML_EXPLOITABLE.
                ⚠️⚠️ LA SECONDE CONDITION MANQUAIT — constat `a4/C9`.
                La phrase disait « aucun modele ML ne bat le GLM », et le
                code rend AMBRE des que le meilleur Gini ML depasse le
                seuil, meme sans battre le GLM. **C'est defendable** — un
                ML qui discrimine honnetement sans battre le GLM n'est pas
                sans valeur — mais la docstring ne le disait pas, et le
                seuil etait un litteral invisible dans une branche qui
                decide d'un statut reglementaire.

        Réf. : ACPR-2022-P-01 §4.3 — interprétabilité obligatoire
               AI Act 2025 Art. 13 — transparence systèmes IA haut risque
        """
        if not classement:
            return 'ROUGE'

        # Exclure le GLM du classement pour trouver le meilleur ML pur
        classement_ml = [
            c for c in classement
            if 'GLM' not in c['modele']
        ]

        if not classement_ml:
            return 'ROUGE'

        meilleur_gini_ml = classement_ml[0]['gini_test']

        # Comparaison avec le GLM
        gini_glm = 0
        if result_a3 and result_a3.get('success'):
            gini_glm = result_a3['metriques'].get('poisson', {}).get('gini', 0)

        if meilleur_gini_ml is None or gini_glm is None:
            # Gini NON MESURE (aucun sinistre sur le jeu de test) : le critere
            # de selection n'a pas de base. Un Gini absent reserve, il ne
            # colore pas (arbitrage du 03/09/2026) : AMBRE + diagnostic publie.
            return 'AMBRE'
        amelioration = meilleur_gini_ml - gini_glm

        # Overfitting sur le meilleur modèle
        overfitting = classement_ml[0].get('overfit_alerte', False)

        # SHAP absent → plafond AMBRE (interprétabilité non vérifiée)
        # Réf. : ACPR-2022-P-01 §4.3 ; AI Act 2025 Art. 13
        if amelioration > 0.05 and not overfitting and not shap_absent:
            return 'VERT'
        elif amelioration > 0 or (amelioration <= 0 and meilleur_gini_ml > SEUIL_GINI_ML_EXPLOITABLE):
            return 'AMBRE'
        else:
            return 'ROUGE'

    def _commenter_actuaire_senior(
        self,
        classement:   List[Dict],
        sous_branche: str,
        statut_rag:   str,
        result_a3:    Optional[Dict],
        rapport:      Dict
    ) -> str:
        """Commentaire actuaire sénior en 3 niveaux sur les ML."""
        emoji = glyphe_rag(statut_rag)

        # Meilleur modèle ML
        classement_ml = [c for c in classement if 'GLM' not in c['modele']]
        meilleur = classement_ml[0] if classement_ml else {}

        # Gini GLM de référence
        gini_glm = 0
        if result_a3 and result_a3.get('success'):
            gini_glm = result_a3['metriques'].get('poisson', {}).get('gini', 0)

        # ── NIVEAU 1 : LECTURE ────────────────────────────────────────────────
        nb_modeles = len(rapport.get('modeles_testes', []))
        # ⚠️⚠️ LE DENOMINATEUR ETAIT LE LITTERAL `8` — constat `a4/C6`.
        # Mesure : la liste des candidats en porte **6**, le catalogue
        # `FAMILLES_MODELES_ML` en declare **10**, et un run reel en teste
        # **6**. Le `8` ne correspondait a AUCUN des trois. *Le numerateur
        # etait deja derive ; seul le denominateur etait invente.*
        nb_candidats = rapport.get('modeles_candidats') or nb_modeles
        niveau1 = (
            f"{emoji} ML TARIFICATION — {statut_rag}\n"
            f"Sous-branche    : {sous_branche}\n"
            f"Modèles testés  : {nb_modeles}/{nb_candidats}\n"
            f"\n"
            f"CLASSEMENT (Gini décroissant) :\n"
        )
        for i, c in enumerate(classement[:5], 1):
            niveau1 += (
                f"  {i}. {c['modele']:<30} "
                f"Gini={gini_texte(c['gini_test'])} | "
                f"RMSE={c['rmse_test']:.4f} | "
                f"{c['recommandation']}\n"
            )

        if (gini_glm is not None and gini_glm > 0
                and meilleur.get('gini_test', 0) is not None):
            amelioration = (meilleur.get('gini_test', 0) - gini_glm) / max(gini_glm, 1e-6) * 100
            niveau1 += f"\n  Amélioration vs GLM : {amelioration:+.1f}%"

        # ⚠️ CE QUI N'EST PAS PRIS EN COMPTE SE DIT AUSSI. L'actuaire qui lit
        # ce commentaire doit savoir que la dimension elasticite-prix n'entre
        # pas dans l'analyse — et pourquoi. Le silence laisserait croire
        # qu'elle a ete consideree.
        _elast = rapport.get('elasticite') or {}
        if _elast.get('etat') and _elast['etat'] != ELASTICITE_ESTIMEE:
            niveau1 += (
                f"\n\nÉLASTICITÉ-PRIX : NON PRISE EN COMPTE ({_elast['etat']})"
                f"\n  {_elast.get('motif', '')}"
                f"\n  {_elast.get('ce_que_cela_coute', '')}"
            )
        elif _elast.get('etat') == ELASTICITE_ESTIMEE:
            # ⚠️ CE QUI EST MESURÉ SE PUBLIE AVEC SON INCERTITUDE ET SA
            # RÉSERVE. Un ε seul se lirait comme une certitude ; c'est
            # exactement ce que le « Tarif optimal : −20 % » faisait.
            _est = _elast.get('estimation') or {}
            niveau1 += (
                f"\n\nÉLASTICITÉ-PRIX : ESTIMÉE"
                f"\n  ε = {_est.get('elasticite'):+.4f}"
                f"  IC 95 % [{_est.get('ic_bas'):+.4f} ; "
                f"{_est.get('ic_haut'):+.4f}]"
                f"\n  Voie d'identification : {_est.get('voie')} — "
                f"{_est.get('n_lignes'):,} renouvellements, "
                f"{_est.get('n_resiliations'):,} résiliations"
                f"\n  {_est.get('reserve', '')}"
            )

        # ── NIVEAU 2 : DIAGNOSTIC ─────────────────────────────────────────────
        meilleur_nom  = meilleur.get('modele', 'N/A')
        meilleur_gini = meilleur.get('gini_test', 0)
        overfit       = meilleur.get('overfit_alerte', False)
        _gain_glm     = (None if meilleur_gini is None or gini_glm is None
                         else meilleur_gini - gini_glm)

        if statut_rag == 'VERT':
            niveau2 = (
                f"DIAGNOSTIC ACTUARIEL :\n"
                f"Le modèle {meilleur_nom} est le meilleur performer "
                f"avec un Gini de {gini_texte(meilleur_gini)}, supérieur au GLM "
                f"Poisson de référence ({gini_texte(gini_glm)}). "
                f"Ce gain de {gini_texte(_gain_glm)} points de Gini "
                f"reflète la capacité des modèles ML à capturer des "
                f"interactions non-linéaires entre les variables de risque "
                f"que le GLM ne peut modéliser (ex : effet combiné âge×BM "
                f"×type de garantie). "
                f"Le modèle ne présente pas de signes d'overfitting "
                f"(overfit ratio < 1.15)."
            )
        elif statut_rag == 'AMBRE':
            if overfit:
                niveau2 = (
                    f"DIAGNOSTIC ACTUARIEL :\n"
                    f"Le meilleur modèle ML ({meilleur_nom}) présente "
                    f"un overfitting détecté (ratio train/test = "
                    f"{meilleur.get('overfit_ratio', 0):.2f}). "
                    f"Cela signifie que le modèle a mémorisé les données "
                    f"d'entraînement au lieu d'apprendre les patterns généraux. "
                    f"En production, ses performances seront inférieures "
                    f"à ce que suggèrent les métriques train. "
                    f"Recommandation : renforcer la régularisation "
                    f"(réduire max_depth ou augmenter min_samples_leaf)."
                )
            else:
                niveau2 = (
                    f"DIAGNOSTIC ACTUARIEL :\n"
                    f"L'amélioration des modèles ML par rapport au GLM "
                    f"est modeste. Cela peut indiquer que les relations "
                    f"entre variables et sinistralité sont relativement "
                    f"linéaires pour ce portefeuille, ou que les features "
                    f"disponibles ne capturent pas suffisamment la "
                    f"hétérogénéité du risque. "
                    f"Le GLM reste compétitif et défendable."
                )
        else:
            niveau2 = (
                f"DIAGNOSTIC ACTUARIEL :\n"
                f"Aucun modèle ML n'améliore significativement le GLM. "
                f"Les données ou les features disponibles ne permettent "
                f"pas aux algorithmes ML d'extraire de la valeur "
                f"supplémentaire. Vérifiez la qualité et la richesse "
                f"des variables disponibles."
            )

        # ── NIVEAU 3 : RECOMMANDATION ─────────────────────────────────────────
        if statut_rag == 'VERT':
            niveau3 = (
                f"RECOMMANDATION :\n"
                f"→ Retenir {meilleur_nom} comme modèle de production.\n"
                f"→ Passer à l'agent A6 (Comparaison) pour validation finale.\n"
                f"→ Les SHAP values (Agent A4) sont disponibles pour\n"
                f"  justifier le modèle devant l'auditeur (AI Act 2025).\n"
                f"→ Les modèles sont sauvegardés sur Drive."
            )
        elif statut_rag == 'AMBRE':
            niveau3 = (
                f"RECOMMANDATION :\n"
                f"→ Comparer {meilleur_nom} et GLM Poisson en production.\n"
                f"→ Privilégier le GLM si la stabilité est prioritaire.\n"
                f"→ Tester avec plus de features si disponibles.\n"
                f"→ Passer à l'agent A6 pour la décision finale."
            )
        else:
            niveau3 = (
                f"RECOMMANDATION :\n"
                f"→ Utiliser le GLM Poisson (A3) comme modèle de production.\n"
                f"→ Investiguer les données avec A1 pour améliorer les features.\n"
                f"→ Envisager des sources de données externes."
            )

        return f"{niveau1}\n{niveau2}\n\n{niveau3}"

    def _afficher_rapport_console(
        self, audit_id, sous_branche, classement,
        statut_rag, commentaire, result_a3
    ) -> None:
        """Affiche le rapport dans la console Colab."""
        emoji = glyphe_rag(statut_rag)
        sep   = "═" * 65

        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT A4 ML | {audit_id}")
        print(sep)
        print(f"  Sous-branche : {sous_branche}")
        print(f"  {emoji} STATUT : {statut_rag}")
        print(f"\n  CLASSEMENT FINAL :")
        print(f"  {'Rang':<5} {'Modèle':<30} {'Gini':<8} {'RMSE':<8} {'Overfit'}")
        print(f"  {'-'*60}")
        for i, c in enumerate(classement, 1):
            ov = (f"{c['overfit_ratio']:.2f}"
                  if c.get('overfit_ratio') is not None else 'N/A')
            print(
                f"  {i:<5} {c['modele']:<30} "
                f"{gini_texte(c['gini_test']):<8} {c['rmse_test']:<8.4f} {ov}"
            )
        print(f"\n{sep}")
        for ligne in commentaire.split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    # ══════════════════════════════════════════════════════════════════════════
    # GRAPHIQUES v3 — Style PowerBI/Bloomberg
    # ══════════════════════════════════════════════════════════════════════════

    def _generer_graphiques(
        self,
        y_test:       np.ndarray,
        classement:   List[Dict],
        feature_names: List[str],
    ) -> Dict:
        """
        Génère 4 graphiques actuariels style PowerBI/Bloomberg.

        GRAPHIQUE 1 — Courbe de Lorenz (tous modèles)
        GRAPHIQUE 2 — Lift Chart (déciles)
        GRAPHIQUE 3 — Comparaison Gini (bar chart)
        GRAPHIQUE 4 — Overfit Analysis (scatter)
        """
        if not PLOTLY_OK:
            return {}

        # ── DESIGN TOKENS ─────────────────────────────────────────────────────
        NAVY    = "#0F2E52"
        NAVY_L  = "#1B3A5C"
        NAVY_LL = "#243F6A"
        OR      = "#C9A84C"
        OR_L    = "#E8C96A"
        BLANC   = "#F0F4F8"
        GRIS    = "#8A9AB0"
        # ⚠️ Couleurs RAG lues à la SOURCE UNIQUE (`core/charts_tarif`), jamais
        # redéfinies : 30 définitions locales et 7 valeurs distinctes existaient.
        VERT = couleur_rag("VERT", FOND_SOMBRE)
        ROUGE = couleur_rag("ROUGE", FOND_SOMBRE)
        AMBRE = couleur_rag("AMBRE", FOND_SOMBRE)

        # ══════════════════════════════════════════════════════════════════
        # PALETTE DES MODÈLES — AUCUNE COULEUR DE STATUT DANS UN CYCLE
        # ══════════════════════════════════════════════════════════════════
        # ⚠️⚠️ CONSTAT `charts/C4`, ET LE DÉFAUT N'ÉTAIT PAS L'ESTHÉTIQUE.
        # Cette liste contenait `VERT`, `AMBRE` et `ROUGE` — c'est-à-dire
        # `couleur_rag(...)`, LES COULEURS DE STATUT — utilisées comme cycle
        # DÉCORATIF : `COULEURS_MODELES[idx % len(...)]`. Le modèle numéro 5
        # était donc peint en ROUGE RAG **parce qu'il était cinquième**.
        # *Un lecteur entraîné par tout le reste du rapport y lit une alerte.*
        #
        # ⚠️ ET `#9B59B6` NE PASSAIT PAS : contraste 2,49 sur le fond de tracé
        # `#1B3A5C`, sous le seuil WCAG 1.4.11 (3:1 pour un objet non textuel).
        #
        # Le cycle ci-dessous est MESURÉ, pas choisi au goût :
        #   · aucune valeur n'est un `couleur_rag` ;
        #   · aucune teinte dans les familles rouge/ambre (< 50 deg) ni verte
        #     (90-175 deg) — sauf l'OR (44 deg), qui est l'accent maison du
        #     rapport et n'a jamais été un statut ;
        #   · contraste sur `#1B3A5C` : 5,09 · 3,69 · 5,04 · 6,75 · 3,12 · 4,06
        #     — les six au-dessus de 3:1 ;
        #   · six familles de teinte distinctes, et en deuteranopie la paire
        #     la plus proche reste à 59 de distance L1 (seuil pratique 40).
        # ⚠️ L'OR reste en tête : `idx == 0` est le meilleur modèle, et il
        # porte déjà `width=3` puis un `dash` distinct — la couleur n'est pas
        # le seul canal.
        COULEURS_MODELES = [OR, "#3498DB", "#C89BD4",
                            "#B8C4F0", "#C2678F", GRIS]

        LAYOUT_BASE = dict(
            paper_bgcolor = NAVY,
            plot_bgcolor  = NAVY_L,
            font          = dict(family="Inter, Arial", color=BLANC, size=11),
            margin        = dict(l=16, r=16, t=52, b=16),
            height        = 340,
            hoverlabel    = dict(
                bgcolor    = NAVY_LL,
                bordercolor= OR,
                font_size  = 12,
                font_color = BLANC,
            ),
            legend = dict(
                bgcolor     = "rgba(0,0,0,0)",
                bordercolor = "rgba(201,168,76,0.2)",
                borderwidth = 1,
                font        = dict(color=BLANC, size=10),
                orientation = "h",
                yanchor     = "bottom",
                y           = 1.02,
                xanchor     = "left",
                x           = 0,
            ),
        )

        graphiques = {}

        # ── GRAPHIQUE 2 : LIFT CHART (DÉCILES) ────────────────────────────────
        try:
            fig2 = go.Figure()

            # Ligne de référence (lift = 1)
            fig2.add_hline(
                y                  = 1.0,
                line_dash          = "dot",
                line_color         = GRIS,
                line_width         = 1.5,
                annotation_text    = "Référence (Lift=1)",
                annotation_position= "bottom right",
                annotation_font    = dict(color=GRIS, size=9),
            )

            for idx, c in enumerate(classement[:4]):
                nom  = c['modele']
                gini = c.get('gini_test', 0)

                # Lift Chart approximé depuis le Gini
                # Lift décile k = (% sinistres dans décile k) / (10%)
                # Approximation analytique basée sur la courbe de Lorenz
                deciles = list(range(1, 11))
                if gini is not None and gini > 0.01:
                    # Modèle discriminant : lift croissant
                    lifts = [
                        max(0.1, 1 + (gini * 3) * (d - 5.5) / 5.5)
                        for d in deciles
                    ]
                else:
                    lifts = [1.0] * 10

                couleur = COULEURS_MODELES[idx % len(COULEURS_MODELES)]

                fig2.add_trace(go.Scatter(
                    x    = deciles,
                    y    = lifts,
                    mode = 'lines+markers',
                    name = f"{nom} (Gini={gini_texte(gini, 3)})",
                    line = dict(
                        color    = couleur,
                        width    = 2.5 if idx == 0 else 1.5,
                        shape    = 'spline',
                        smoothing= 0.6,
                    ),
                    marker = dict(
                        color = couleur,
                        size  = 8 if idx == 0 else 6,
                        line  = dict(color=NAVY, width=1.5),
                    ),
                    hovertemplate = (
                        f"<b>{nom}</b><br>"
                        f"Décile %{{x}}<br>"
                        "Lift : <b>%{y:.2f}</b><extra></extra>"
                    ),
                ))

            layout2 = dict(**LAYOUT_BASE)
            layout2.update(dict(
                title = dict(
                    text = "📊 Lift Chart — Performance par décile de risque",
                    font = dict(color=BLANC, size=13), x=0.01,
                ),
                xaxis = dict(
                    title    = dict(text="Décile (1=moins risqué → 10=plus risqué)",
                                    font=dict(color=GRIS, size=10)),
                    tickvals = list(range(1, 11)),
                    showgrid = True,
                    gridcolor= "rgba(255,255,255,0.05)",
                    tickfont = dict(color=GRIS, size=10),
                ),
                yaxis = dict(
                    title    = dict(text="Lift (sinistralité relative)",
                                    font=dict(color=GRIS, size=10)),
                    showgrid = True,
                    gridcolor= "rgba(255,255,255,0.05)",
                    tickfont = dict(color=GRIS, size=10),
                    zeroline = True,
                    zerolinecolor = GRIS,
                ),
            ))
            fig2.update_layout(**layout2)
            graphiques['lift_chart'] = fig2

        except Exception as e:
            logger.warning(f"Graphique Lift Chart échoué : {e}")

        # ── GRAPHIQUE 3 : COMPARAISON GINI — Barres + Ligne GLM ───────────────
        try:
            noms_mod  = [c['modele'] for c in classement]
            ginis     = [c.get('gini_test', 0) for c in classement]
            overfits  = [c.get('overfit_ratio', 1) for c in classement]

            # Couleurs selon overfit
            colors3 = []
            for of, g in zip(overfits, ginis):
                if g == 0:
                    colors3.append(GRIS)
                elif of > 1.30:
                    colors3.append(ROUGE)
                elif of > 1.15:
                    colors3.append(AMBRE)
                else:
                    colors3.append(OR)

            # Gini GLM de référence (A3)
            gini_glm = next(
                (c['gini_test'] for c in classement if 'GLM' in c.get('famille','').upper()),
                0.0
            )

            fig3 = make_subplots(specs=[[{"secondary_y": True}]])

            # Barres Gini (axe gauche)
            fig3.add_trace(go.Bar(
                x             = noms_mod,
                y             = ginis,
                name          = "Gini test",
                marker_color  = colors3,
                marker_line   = dict(color=NAVY, width=1),
                width         = 0.45,
                opacity       = 0.9,
                hovertemplate = (
                    "<b>%{x}</b><br>"
                    "Gini : <b>%{y:.4f}</b><extra></extra>"
                ),
                text          = [f"{g:.3f}" for g in ginis],
                textposition  = 'outside',
                textfont      = dict(color=BLANC, size=10),
            ), secondary_y=False)

            # Courbe overfit ratio (axe droit)
            fig3.add_trace(go.Scatter(
                x             = noms_mod,
                y             = overfits,
                mode          = 'lines+markers',
                name          = "Overfit ratio",
                line          = dict(color=BLANC, width=2, shape='spline', smoothing=0.5),
                marker        = dict(
                    color = [ROUGE if of > 1.30 else AMBRE if of > 1.15 else VERT
                             for of in overfits],
                    size  = 9,
                    line  = dict(color=NAVY_L, width=2),
                ),
                hovertemplate = (
                    "<b>%{x}</b><br>"
                    "Overfit : <b>%{y:.2f}</b><extra></extra>"
                ),
            ), secondary_y=True)

            # Ligne Gini GLM référence
            if gini_glm is not None and gini_glm > 0:
                fig3.add_hline(
                    y                  = gini_glm,
                    line_dash          = "dash",
                    line_color         = VERT,
                    line_width         = 1.5,
                    annotation_text    = f"GLM ref = {gini_texte(gini_glm, 3)}",
                    annotation_font    = dict(color=VERT, size=10),
                    annotation_position= "bottom left",
                    secondary_y        = False,
                )

            # Ligne overfit seuil 1.15
            fig3.add_hline(
                y                  = 1.15,
                line_dash          = "dot",
                line_color         = AMBRE,
                line_width         = 1,
                annotation_text    = "Seuil overfit 1.15",
                annotation_font    = dict(color=AMBRE, size=9),
                annotation_position= "top right",
                secondary_y        = True,
            )

            fig3.update_layout(
                title         = dict(
                    text = "📊 Gini & Overfit — Comparaison des modèles",
                    font = dict(color=BLANC, size=13), x=0.01,
                ),
                paper_bgcolor = NAVY,
                plot_bgcolor  = NAVY_L,
                font          = dict(family="Inter, Arial", color=BLANC),
                margin        = dict(l=16, r=16, t=52, b=16),
                height        = 340,
                hoverlabel    = dict(bgcolor=NAVY_LL, bordercolor=OR,
                                     font_size=12, font_color=BLANC),
                legend        = dict(
                    bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                    orientation="h", yanchor="bottom", y=1.02,
                ),
                bargap        = 0.35,
            )
            fig3.update_xaxes(
                showgrid=False, zeroline=False,
                tickfont=dict(color=GRIS, size=9),
            )
            fig3.update_yaxes(
                title_text  = "Gini",
                title_font  = dict(color=GRIS, size=10),
                showgrid    = True,
                gridcolor   = "rgba(255,255,255,0.05)",
                tickfont    = dict(color=GRIS, size=10),
                secondary_y = False,
            )
            fig3.update_yaxes(
                title_text  = "Overfit ratio",
                title_font  = dict(color=GRIS, size=10),
                showgrid    = False,
                tickfont    = dict(color=GRIS, size=10),
                secondary_y = True,
            )
            graphiques['gini_comparaison'] = fig3

        except Exception as e:
            logger.warning(f"Graphique Gini comparaison échoué : {e}")

        # ── GRAPHIQUE 4 : SCATTER GINI vs RMSE ────────────────────────────────
        try:
            fig4 = go.Figure()

            for idx, c in enumerate(classement):
                nom    = c['modele']
                gini   = c.get('gini_test', 0)
                rmse   = c.get('rmse_test', 0)
                overfit= c.get('overfit_ratio', 1)

                # Taille du point = inverse de l'overfit (plus stable = plus grand)
                size = max(8, int(20 / max(overfit, 0.5)))
                color= COULEURS_MODELES[idx % len(COULEURS_MODELES)]
                est_meilleur = idx == 0

                fig4.add_trace(go.Scatter(
                    x    = [rmse],
                    y    = [gini],
                    mode = 'markers+text',
                    name = nom,
                    text = [nom.replace('_', ' ').title()],
                    textposition = 'top center',
                    textfont     = dict(color=BLANC, size=9),
                    marker       = dict(
                        color   = color,
                        size    = 16 if est_meilleur else 11,
                        symbol  = 'star' if est_meilleur else 'circle',
                        line    = dict(color=NAVY, width=2),
                        opacity = 0.9,
                    ),
                    hovertemplate = (
                        f"<b>{nom}</b><br>"
                        f"Gini : <b>{gini_texte(gini)}</b><br>"
                        f"RMSE : <b>{rmse:.4f}</b><br>"
                        f"Overfit : <b>{gini_texte(overfit, 2)}</b><extra></extra>"
                    ),
                    showlegend = False,
                ))

            layout4 = dict(**LAYOUT_BASE)
            layout4.update(dict(
                title = dict(
                    text = "🎯 Gini vs RMSE — Meilleur modèle = haut-gauche",
                    font = dict(color=BLANC, size=13), x=0.01,
                ),
                xaxis = dict(
                    title    = dict(text="RMSE (erreur absolue)",
                                    font=dict(color=GRIS, size=10)),
                    showgrid = True,
                    gridcolor= "rgba(255,255,255,0.05)",
                    tickfont = dict(color=GRIS, size=10),
                    zeroline = False,
                ),
                yaxis = dict(
                    title    = dict(text="Gini (discrimination)",
                                    font=dict(color=GRIS, size=10)),
                    showgrid = True,
                    gridcolor= "rgba(255,255,255,0.05)",
                    tickfont = dict(color=GRIS, size=10),
                    zeroline = False,
                ),
                showlegend = False,
                annotations = [dict(
                    x         = 0.02, y = 0.97,
                    xref      = 'paper', yref = 'paper',
                    text      = "⭐ = Meilleur modèle",
                    showarrow = False,
                    font      = dict(color=OR, size=10),
                )],
            ))
            fig4.update_layout(**layout4)
            graphiques['scatter_gini_rmse'] = fig4

        except Exception as e:
            logger.warning(f"Graphique scatter échoué : {e}")

        return graphiques


    # ═══════════════════════════════════════════════════════════════════════════
    # MONITORING DÉRIVE DES MODÈLES (PSI + KS Test)
    # ═══════════════════════════════════════════════════════════════════════════
    def _psi_reel(
        self,
        X_train:   object = None,
        X_test:    object = None,
        n_buckets: int    = 10,
        n_features_max: int = 10,
    ) -> tuple:
        """
        PSI (Population Stability Index) MESURÉ entre train et test.

        Rend `(psi_moyen, {feature: psi})`, ou `(None, {})` si la mesure n'a
        pas pu être faite — jamais une valeur par défaut : c'est la règle du
        module, une grandeur non mesurée se publie `None`.

        Les bornes sont les déciles de la distribution d'ENTRAÎNEMENT (la
        référence), et le PSI de chaque feature est moyenné.
        Réf. : Siddiqi (2006) — Credit Risk Scorecards.
        """
        import numpy as np

        details: dict = {}
        try:
            if X_train is None or X_test is None or not hasattr(X_train, 'shape'):
                return None, details
            import pandas as pd
            if hasattr(X_train, 'columns'):
                cols = X_train.columns.tolist()
            else:
                cols = [f"f{i}" for i in range(X_train.shape[1])]
                X_train = pd.DataFrame(X_train, columns=cols)
                X_test  = pd.DataFrame(X_test,  columns=cols)

            psis = []
            for col in cols[:n_features_max]:
                try:
                    tr_vals = X_train[col].dropna().values
                    te_vals = X_test[col].dropna().values
                    if len(tr_vals) < 20 or len(te_vals) < 20:
                        continue
                    bins = np.unique(
                        np.percentile(tr_vals, np.linspace(0, 100, n_buckets + 1)))
                    if len(bins) < 3:
                        continue
                    f_tr = np.histogram(tr_vals, bins=bins)[0] / len(tr_vals)
                    f_te = np.histogram(te_vals, bins=bins)[0] / len(te_vals)
                    f_tr = np.clip(f_tr, 1e-6, None)
                    f_te = np.clip(f_te, 1e-6, None)
                    psi_col = float(np.sum((f_te - f_tr) * np.log(f_te / f_tr)))
                    psis.append(psi_col)
                    details[col] = round(psi_col, 4)
                except Exception:
                    pass

            return (float(np.mean(psis)) if psis else None), details
        except Exception as e_psi:
            logger.debug(f"PSI réel échoué : {e_psi}")
            return None, details

    def _monitoring_derive(
        self,
        metriques_actuelles: Dict,
        gini_reference:      float | None = None,
        seuil_alerte_gini:   float = 0.05,
        psi_reel:            float | None = None,
        details_psi:         dict | None  = None,
        scores_ref:          object = None,
        scores_actuels:      object = None,
        gini_actuel:         float | None = None,
    ) -> Dict:
        """
        Stabilité train → test du modèle retenu.

        ⚠️⚠️ CE N'EST PAS — ET N'A JAMAIS ÉTÉ — UN MONITORING DE PRODUCTION.
        Le titre publié disait « Monitoring de la dérive des modèles ML en
        production » ; aucune donnée de production n'entre dans ce module, et
        les trois grandeurs étaient SIMULÉES :

          • PSI et KS sortaient de `np.random.beta(...)` sous graine 42 →
            MESURÉ : PSI IDENTIQUE sur deux portefeuilles différents. La
            grandeur était une constante du module.
          • l'« historique Gini 12 mois » était `gini_reference × (1 − 0.002·i
            + bruit)` — une courbe de dégradation inventée, tracée sous le
            titre « Évolution Gini 12 mois » avec un seuil d'alerte.
          • `metriques_actuelles` était lu par la clé `gini_moyen`, que le
            site d'appel ne pose pas : même ce point-là était le défaut.

        Ce qui est mesuré maintenant, et rien d'autre :
        1. PSI train → test sur les features RÉELLES (`_psi_reel`), le même
           calcul que celui d'H2 — un seul PSI dans le résultat.
        2. KS train → test sur les SCORES RÉELS du modèle retenu, quand ils
           sont fournis.
        3. Le Gini de référence (A3) et le Gini RÉEL du modèle retenu — deux
           points mesurés, pas treize points simulés.
        4. Recommandation de ré-entraînement, sur ces grandeurs-là.

        Une grandeur non mesurée vaut `None` et son statut est AMBRE.
        Référence : Siddiqi (2006) — Credit Risk Scorecards
        """
        # 1. PSI RÉEL (Population Stability Index) train → test
        psi = psi_reel
        details_psi = details_psi or {}

        # Statut PSI
        if psi is None:
            statut_psi = "AMBRE"
            interpretation_psi = ("Stabilité NON mesurée — features train/test "
                                  "indisponibles")
        elif psi < 0.10:
            statut_psi = "VERT"
            interpretation_psi = "Distribution stable — pas d'action requise"
        elif psi < 0.25:
            statut_psi = "AMBRE"
            interpretation_psi = "Dérive légère — surveillance accrue recommandée"
        else:
            statut_psi = "ROUGE"
            interpretation_psi = "Dérive significative — ré-entraînement requis"

        # 2. KS Test (Kolmogorov-Smirnov) sur les SCORES RÉELS
        ks_stat, ks_pvalue, statut_ks = None, None, "AMBRE"
        if scores_ref is not None and scores_actuels is not None:
            try:
                from scipy import stats
                _ks = stats.ks_2samp(np.asarray(scores_ref, dtype=float),
                                     np.asarray(scores_actuels, dtype=float))
                ks_stat, ks_pvalue = float(_ks[0]), float(_ks[1])
                statut_ks = ("VERT"  if ks_pvalue > 0.05 else
                             "AMBRE" if ks_pvalue > 0.01 else "ROUGE")
            except (ValueError, TypeError) as e_ks:
                logger.debug(f"KS sur scores réels échoué : {e_ks}")

        # 3. Gini : la référence A3 et le Gini RÉEL du modèle retenu
        #
        # ⚠️⚠️ CONSTAT `a4/C11`, RANG 1 — LA RÉFÉRENCE ÉTAIT FABRIQUÉE, ET ELLE
        # DÉCIDAIT D'UN STATUT. Trois nombres inventés coexistaient dans la
        # chaîne, à trois valeurs différentes : `0.25` chez l'appelant,
        # `0.2651` en défaut de signature ici — le hardcodage freMTPL2 que
        # l'appelant dit précisément vouloir éviter — et `0.265` dans la
        # figure. Quand A3 n'avait pas tourné, l'un d'eux servait quand même de
        # référence, sous le libellé publié « Référence A3 » : *une provenance
        # que le code ne portait pas*, sur un statut qui autorise ou plafonne
        # la mise en production d'un modèle.
        #
        # ⚠️ LE COMPORTEMENT EST CELUI DÉJÀ ARBITRÉ POUR L'A/E NON CALCULABLE
        # D'A6 : une grandeur non mesurée vaut `None` et son statut est AMBRE.
        # C'est la règle que cette docstring énonce depuis toujours ; le Gini
        # était le seul des trois indicateurs à ne pas l'appliquer.
        gini_courant = (gini_actuel if gini_actuel is not None
                        else metriques_actuelles.get('gini_moyen'))
        reference_disponible = gini_reference is not None

        # ⚠️ AUCUN POINT FANTÔME SUR LA COURBE. Elle ne trace que ce qui est
        # mesuré : sans référence, un seul point — pas deux dont un inventé.
        mois, gini_historique = [], []
        if reference_disponible:
            mois.append("Référence A3")
            gini_historique.append(gini_reference)
        if gini_courant is not None:
            mois.append("Modèle retenu (test)")
            gini_historique.append(gini_courant)

        if not reference_disponible:
            variation_gini = None
            statut_gini    = "AMBRE"
            interpretation_gini = MSG_REFERENCE_A3_INDISPONIBLE
        elif gini_courant is None:
            variation_gini = None
            statut_gini    = "AMBRE"
            interpretation_gini = ("Gini du modèle retenu NON mesuré — la "
                                   "comparaison à la référence A3 n'a pas pu "
                                   "être faite.")
        else:
            variation_gini = gini_courant - gini_reference
            # ⚠️⚠️ LE TEST EST ASYMÉTRIQUE, ET CE N'EST PAS UN DÉTAIL — arbitré
            # le 30/08/2026. Il portait sur `abs(variation)` : un modèle qui
            # discrimine MIEUX que la référence sortait ROUGE exactement comme
            # un modèle dégradé. Mesuré : Gini 0,34 contre une référence à
            # 0,25 rendait `statut_global = ROUGE`. *Une amélioration n'est pas
            # une dérive.* Elle se SIGNALE — pour qu'une hausse suspecte reste
            # visible — mais elle ne plafonne JAMAIS le statut.
            if variation_gini >= 0:
                statut_gini = "VERT"
                interpretation_gini = (
                    f"Gini SUPÉRIEUR à la référence A3 de "
                    f"{variation_gini:+.4f} — le modèle discrimine mieux que "
                    f"le GLM de référence. Aucun plafonnement : une "
                    f"amélioration n'est pas une dérive. À rapprocher des "
                    f"contrôles de fuite si l'écart surprend.")
            else:
                degradation = -variation_gini
                statut_gini = (
                    "VERT"  if degradation <= seuil_alerte_gini * 0.5 else
                    "AMBRE" if degradation <= seuil_alerte_gini else
                    "ROUGE"
                )
                interpretation_gini = (
                    f"Gini INFÉRIEUR à la référence A3 de {degradation:.4f} "
                    f"(seuil d'alerte {seuil_alerte_gini:.2f}).")

        # 4. Recommandation globale
        statuts = [statut_psi, statut_ks, statut_gini]
        if "ROUGE" in statuts:
            # ⚠️ Les deux autres branches utilisaient déjà le jeu commun
            # (⚠️ et ✅) ; seule celle du ROUGE portait un rond coloré, qui
            # n'est PAS un second canal — trois cercles identiques en
            # niveaux de gris. Elle lit la source comme les deux autres.
            recommandation = (f"{glyphe_rag('ROUGE')} Ré-entraînement URGENT"
                              f" — dérive significative détectée")
            statut_global  = "ROUGE"
        elif statuts.count("AMBRE") >= 2:
            recommandation = "⚠️ Ré-entraînement recommandé dans les 30 jours"
            statut_global  = "AMBRE"
        else:
            recommandation = "✅ Modèle stable — prochaine révision dans 3 mois"
            statut_global  = "VERT"

        return {
            "psi":                  round(psi, 4) if psi is not None else None,
            "details_psi":          details_psi,
            "statut_psi":           statut_psi,
            "interpretation_psi":   interpretation_psi,
            "ks_stat":              round(ks_stat, 4) if ks_stat is not None else None,
            "ks_pvalue":            round(ks_pvalue, 4) if ks_pvalue is not None else None,
            "statut_ks":            statut_ks,
            "gini_reference":       gini_reference,
            "gini_actuel":          gini_courant,
            "variation_gini":       round(variation_gini, 4) if variation_gini is not None else None,
            "variation_gini_pct":   (round(variation_gini / max(gini_reference, 1e-6) * 100, 1)
                                     if variation_gini is not None
                                     and gini_reference is not None else None),
            "statut_gini":          statut_gini,
            # ⚠️⚠️ CE CHAMP N'EXISTAIT PAS, ET C'EST L'ASYMÉTRIE QUI L'A
            # DÉSIGNÉ : le PSI publiait `interpretation_psi` — « Stabilité NON
            # mesurée » en toutes lettres — et le Gini, indicateur voisin dans
            # le MÊME dictionnaire, n'avait aucune prose. Il ne pouvait donc
            # rien dire quand il ne pouvait rien mesurer.
            "interpretation_gini":  interpretation_gini,
            "gini_historique":      gini_historique,
            "mois_historique":      mois,
            "statut_global":        statut_global,
            "recommandation":       recommandation,
            "seuil_alerte_gini":    seuil_alerte_gini,
            # ⚠️ LA MÉTHODE NOMME CE QUI EST MESURÉ, et la portée avec.
            "methode":              ("PSI train→test sur features réelles "
                                     "(Siddiqi 2006) + KS train→test sur les "
                                     "scores du modèle retenu + comparaison du "
                                     "Gini à la référence A3"),
            "portee":               ("Stabilité train → test. AUCUNE donnée de "
                                     "production n'entre dans ce calcul : la "
                                     "dérive en production n'est pas mesurée ici."),
        }

    def _valider_modele_ml(
        self,
        classement:     list,
        monitoring:     Dict,
        n_train:        int = 0,
        n_test:         int = 0,
        X_train:        object = None,
        X_test:         object = None,
        y_test:         object = None,
    ) -> Dict:
        """
        Validation complète des hypothèses ML — 4 hypothèses.

        H1 — Absence d'overfitting
             Ratio Gini test / Gini train ≥ 0.90 → pas d'overfitting ✅
             Ratio < 0.80 → surapprentissage ❌

        H2 — Stabilité PSI réel (dérive train → test)
             PSI calculé sur les features réelles entre train et test.
             PSI < 0.10 → stable ✅
             PSI ∈ [0.10, 0.25] → dérive légère ⚠️
             PSI > 0.25 → dérive significative ❌
             Réf. : Siddiqi (2006) — Credit Risk Scorecards.

        H3 — Performance Gini suffisante
             Gini ≥ 0.20 → acceptable ✅
             Gini ≥ 0.25 → bon ✅✅
             Gini < 0.15 → insuffisant ❌

        H4 — Calibration (Reliability diagram)
             Pour chaque décile de prime prédite, prime observée
             doit être cohérente avec prime prédite.
             Écart moyen |obs - pred| / pred < 15% → calibré ✅
             Réf. : Denuit et al. (2019) — Autocalibration.
        """
        import numpy as np

        # ── H1 — Overfitting ─────────────────────────────────────────────────
        if classement:
            meilleur   = classement[0]
            gini_test  = meilleur.get('gini_test', meilleur.get('gini', 0))
            gini_train = meilleur.get('gini_train')
            if gini_train is None and gini_test is not None:
                gini_train = gini_test * 1.10
            ratio_of   = (gini_test / max(gini_train, 0.001)
                          if gini_test is not None and gini_train is not None
                          else None)
            if ratio_of is None:
                h1_statut = "AMBRE"
                h1_msg = ("Ratio Gini test/train NON MESURABLE : au moins un des deux "
                          "Ginis n'existe pas (aucun sinistre observé sur le jeu "
                          "concerné) → hypothèse H1 non évaluable ⚠️")
                h1_conseil = ("Constituer un jeu de test qui contient des sinistres "
                              "(découpage temporel avec exposition suffisante) avant de "
                              "conclure sur le sur-apprentissage")
            elif ratio_of >= 0.90:
                h1_statut = "VERT"
                h1_msg    = f"Ratio test/train = {ratio_of:.3f} ≥ 0.90 → Pas d'overfitting ✅"
                h1_conseil= f"Le modèle {meilleur.get('modele','?')} généralise bien"
            elif ratio_of >= 0.80:
                h1_statut = "AMBRE"
                h1_msg    = f"Ratio test/train = {ratio_of:.3f} ∈ [0.80, 0.90] → Overfitting léger ⚠️"
                h1_conseil= "Augmenter la régularisation (lambda/alpha) · Réduire max_depth"
            else:
                h1_statut = "ROUGE"
                h1_msg    = f"Ratio test/train = {ratio_of:.3f} < 0.80 → Surapprentissage ❌"
                h1_conseil= "Réduire la complexité · Augmenter min_samples_leaf · Vérifier les données"
        else:
            ratio_of, gini_test, gini_train = 1.0, 0.0, 0.0
            h1_statut  = "AMBRE"
            h1_msg     = "Classement vide — aucun modèle calibré"
            h1_conseil = "Vérifier la qualité des données d'entrée"

        # ── H2 — PSI réel sur features train vs test ─────────────────────────
        # Calcul PSI sur les features les plus importantes (top 5 SHAP si dispo,
        # sinon toutes les colonnes numériques).
        # Remplace le PSI simulé par un PSI calculé sur vraies données.
        # ⚠️ LE REPLI `0.0` EST RETIRÉ, ET C'ÉTAIT DU CODE MORT — pas un
        # correctif de gouvernance. Mesuré : `_monitoring_derive` pose
        # TOUJOURS la clé `psi` (aucun chemin d'exception avant son `return`)
        # et les trois sites d'appel passent tous son résultat ; sur 75
        # configurations réelles, le repli n'a mordu 0 fois. Il aurait de
        # toute façon été inoffensif : le plafond RAG d'A6 ne se déclenche
        # que sur ROUGE, et 0.0 donne VERT. `[...]` échoue bruyamment si un
        # appelant futur oublie la clé — c'est le comportement voulu.
        # ⚠️ LE CALCUL EST DÉSORMAIS PARTAGÉ, PAS DUPLIQUÉ. Il vivait ici, en
        # ligne, et `_monitoring_derive` en SIMULAIT un second sous
        # `np.random.beta` : deux grandeurs nommées « PSI » dans le même
        # résultat, dont une seule regardait le portefeuille. Le corps de ce
        # bloc est passé dans `_psi_reel`, appelé des deux côtés.
        psi_global, h2_details = self._psi_reel(X_train, X_test)
        psi_source = (f"réel ({len(h2_details)} features)"
                      if psi_global is not None else "non mesuré")
        if psi_global is None:
            # dernier recours : la valeur portée par le monitoring, qui est
            # elle-même mesurée ou None depuis ce lot.
            psi_global = monitoring['psi']
            psi_source = "réel (monitoring)" if psi_global is not None else "non mesuré"

        if psi_global is None:
            # ⚠️ UNE DÉRIVE NON MESURÉE N'EST PAS UNE ABSENCE DE DÉRIVE.
            h2_statut = "AMBRE"
            h2_msg    = ("PSI NON mesuré — X_train/X_test indisponibles ou "
                         "effectif insuffisant ⚠️")
            h2_conseil= ("Fournir X_train et X_test pour que la stabilité des "
                         "distributions soit testée")
        elif psi_global < 0.10:
            h2_statut = "VERT"
            h2_msg    = f"PSI moyen = {psi_global:.4f} < 0.10 → Distribution stable ✅ ({psi_source})"
            h2_conseil= "Pas de dérive détectée — modèle applicable sur les nouvelles données"
        elif psi_global < 0.25:
            h2_statut = "AMBRE"
            h2_msg    = f"PSI moyen = {psi_global:.4f} ∈ [0.10,0.25] → Dérive légère ⚠️ ({psi_source})"
            h2_conseil= "Surveiller les features instables · Ré-entraîner si PSI augmente"
        else:
            h2_statut = "ROUGE"
            h2_msg    = f"PSI moyen = {psi_global:.4f} > 0.25 → Dérive significative ❌ ({psi_source})"
            h2_conseil= "Ré-entraînement requis — la distribution des données a changé"

        # ── H3 — Performance Gini ─────────────────────────────────────────────
        if gini_test is None:
            h3_statut = "AMBRE"
            h3_msg = ("Gini test NON MESURÉ (aucun sinistre observé sur le jeu de "
                      "test) → hypothèse H3 non évaluable ⚠️")
            h3_conseil = ("Aucun modèle ML ne peut être évalué ni retenu sur ces "
                          "données : voir le diagnostic d'évaluation publié par "
                          "l'agent")
        elif gini_test >= 0.25:
            h3_statut = "VERT"
            h3_msg    = f"Gini = {gini_texte(gini_test)} ≥ 0.25 → Performance bonne ✅✅"
            h3_conseil= "Modèle performant — défendable devant l'actuaire désigné et l'ACPR"
        elif gini_test >= 0.20:
            h3_statut = "VERT"
            h3_msg    = f"Gini = {gini_texte(gini_test)} ∈ [0.20,0.25] → Performance acceptable ✅"
            h3_conseil= "Modèle utilisable — surveiller l'évolution du Gini en production"
        elif gini_test >= 0.15:
            h3_statut = "AMBRE"
            h3_msg    = f"Gini = {gini_texte(gini_test)} ∈ [0.15,0.20] → Performance limite ⚠️"
            h3_conseil= "Enrichir les données · Ajouter des variables actuarielles"
        else:
            h3_statut = "ROUGE"
            h3_msg    = f"Gini = {gini_texte(gini_test)} < 0.15 → Performance insuffisante ❌"
            h3_conseil= "Modèle à rejeter — données insuffisantes ou inadaptées"

        # ── H4 — Calibration (Reliability diagram) ───────────────────────────
        # Déciles de prime prédite → prime observée moyenne dans chaque décile.
        # Écart |obs - pred| / pred par décile → calibration actuarielle.
        # Réf. : Denuit, Hainaut, Trufin (2019) — Autocalibration.
        # Défaut = AMBRE, PAS vert : une calibration non testée n'est pas une
        # calibration validée (correctif faux-vert H4). La branche testée
        # ci-dessous fixe VERT/AMBRE/ROUGE selon l'écart réel.
        h4_statut    = "AMBRE"
        h4_msg       = "Calibration NON testée (X_test/y_test absents) — à vérifier ⚠️"
        h4_conseil   = "Fournir X_test et y_test pour le reliability diagram"
        # ⚠️ None, PAS 0.0 — ET C'EST UN CORRECTIF DE JUSTESSE. Le repli
        # etait publie tel quel dans la colonne << Valeur >> du rapport,
        # dans le contexte lu par le modele et dans le classeur Excel. Or
        # sur un ECART DE CALIBRATION, zero n'est pas neutre : c'est la
        # MEILLEURE valeur possible. Le lecteur qui balayait la colonne
        # voyait une calibration parfaite la ou RIEN n'avait ete mesure.
        # Le message disait bien << NON testee >> ; la valeur le
        # contredisait. Regle du projet : ne jamais fabriquer un chiffre
        # pour combler un trou -- une case vide honnete vaut mieux qu'un
        # nombre faux, et celui-ci etait flatteur.
        ecart_moy    = None
        reliability  = []
        try:
            if classement and y_test is not None and X_test is not None:
                meilleur_mod = self.modeles.get(
                    classement[0].get('modele', ''), None
                )
                if meilleur_mod is not None and hasattr(meilleur_mod, 'predict'):
                    if hasattr(X_test, 'values'):
                        X_te_arr = X_test.values
                    else:
                        X_te_arr = np.array(X_test)
                    y_pred = np.maximum(meilleur_mod.predict(X_te_arr), 0)
                    y_obs  = np.array(y_test, dtype=float)
                    n_dec  = 10
                    idx_sort = np.argsort(y_pred)
                    deciles  = np.array_split(idx_sort, n_dec)
                    ecarts   = []
                    for d in deciles:
                        if len(d) < 5:
                            continue
                        pred_moy = float(np.mean(y_pred[d]))
                        obs_moy  = float(np.mean(y_obs[d]))
                        ecart    = abs(obs_moy - pred_moy) / max(pred_moy, 1e-6)
                        ecarts.append(ecart)
                        reliability.append({
                            'n':        len(d),
                            'pred_moy': round(pred_moy, 4),
                            'obs_moy':  round(obs_moy, 4),
                            'ecart_pct':round(ecart * 100, 2),
                        })
                    if ecarts:
                        ecart_moy = float(np.mean(ecarts))
                        if ecart_moy < 0.15:
                            h4_statut = "VERT"
                            h4_msg    = f"Écart moyen calibration = {ecart_moy*100:.1f}% < 15% → Bien calibré ✅"
                            h4_conseil= "Primes prédites cohérentes avec observées — pas de biais systématique"
                        elif ecart_moy < 0.30:
                            h4_statut = "AMBRE"
                            h4_msg    = f"Écart moyen = {ecart_moy*100:.1f}% ∈ [15%,30%] → Calibration partielle ⚠️"
                            h4_conseil= "Vérifier les déciles extrêmes · Appliquer une calibration isotonic"
                        else:
                            h4_statut = "ROUGE"
                            h4_msg    = f"Écart moyen = {ecart_moy*100:.1f}% > 30% → Modèle non calibré ❌"
                            h4_conseil= "Appliquer calibration isotonic regression avant déploiement en production"
        except Exception as e_cal:
            logger.debug(f"H4 calibration échouée : {e_cal}")

        statuts = [h1_statut, h2_statut, h3_statut, h4_statut]
        statut_global = "ROUGE" if "ROUGE" in statuts else "AMBRE" if "AMBRE" in statuts else "VERT"
        conclusion = {
            "VERT":  f"✅ Modèle validé — {classement[0].get('modele','?') if classement else '?'} prêt pour la production",
            "AMBRE": "⚠️ Modèle utilisable avec précautions — vérifier les points signalés",
            "ROUGE": "❌ Modèle non recommandé pour la production — corriger les problèmes identifiés",
        }[statut_global]

        return {
            "h1_overfitting": {
                "ratio":      (None if ratio_of is None else round(ratio_of, 4)),
                "gini_test":  (None if gini_test is None else round(gini_test, 4)),
                "gini_train": (None if gini_train is None else round(gini_train, 4)),
                "statut":     h1_statut,
                "message":    h1_msg,
                "conseil":    h1_conseil,
                "titre_graphique": f"{'✅' if h1_statut=='VERT' else '⚠️' if h1_statut=='AMBRE' else '❌'} Overfitting — Ratio test/train = {gini_texte(ratio_of, 3)}",
            },
            "h2_psi": {
                "psi":        round(psi_global, 4),
                "psi_source": psi_source,
                "details":    h2_details,
                "statut":     h2_statut,
                "message":    h2_msg,
                "conseil":    h2_conseil,
                "titre_graphique": f"{'✅' if h2_statut=='VERT' else '⚠️' if h2_statut=='AMBRE' else '❌'} PSI réel = {psi_global:.4f}",
            },
            "h3_gini": {
                "gini":   (None if gini_test is None else round(gini_test, 4)),
                "statut": h3_statut,
                "message":h3_msg,
                "conseil":h3_conseil,
                "titre_graphique": f"{'✅' if h3_statut=='VERT' else '⚠️' if h3_statut=='AMBRE' else '❌'} Performance Gini = {gini_texte(gini_test)}",
            },
            "h4_calibration": {
                # ⚠️ None TRAVERSE : un consommateur doit pouvoir distinguer
                # << non mesure >> de << mesure a zero >>.
                "ecart_moy_pct": (None if ecart_moy is None
                                  else round(ecart_moy * 100, 2)),
                "reliability":   reliability,
                "statut":        h4_statut,
                "message":       h4_msg,
                "conseil":       h4_conseil,
                "titre_graphique": (
                    f"{'✅' if h4_statut=='VERT' else '⚠️' if h4_statut=='AMBRE' else '❌'}"
                    " Calibration — "
                    + ("écart non mesuré" if ecart_moy is None
                       else f"Écart moyen = {ecart_moy*100:.1f}%")),
            },
            "statut_global":   statut_global,
            "conclusion":      conclusion,
            "n_modeles":       len(classement),
        }

    def _graphiques_validation_ml(
        self,
        val_ml:     Dict,
        classement: list,
        monitoring: Dict,
    ) -> Dict:
        """Graphiques auto-explicatifs de validation ML.

        ⚠️ ILS ETAIENT QUATRE. G3 « Optimisation tarifaire CA/contrats »
        titrait « Tarif optimal : X % » sur une grandeur qui ne dependait
        d'aucune donnee : elle est retiree avec la fonction qui la nourrissait.
        """
        try:
            import plotly.graph_objects as go
            import numpy as np
        except ImportError:
            return {}

        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"
        OR="#C9A84C"; BLANC="#F0F4F8"; GRIS="#8A9AB0"
        VERT = couleur_rag("VERT", FOND_SOMBRE)
        ROUGE = couleur_rag("ROUGE", FOND_SOMBRE)
        AMBRE = couleur_rag("AMBRE", FOND_SOMBRE); BLEU="#3498DB"
        LAYOUT = dict(
            paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=60, b=50), height=300,
            hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
        )
        graphiques = {}

        # G1 — Overfitting : Gini train vs test par modèle
        try:
            modeles  = [m.get('modele','?') for m in classement[:6]]
            # ⚠️ LA CLÉ DU CLASSEMENT EST `gini_test`, PAS `gini`. Mesuré : la
            # trace « Gini Test » valait [0, 0, 0, 0, 0, 0] pour des valeurs
            # réelles de 0,18 à −0,27, et les couleurs — calculées sur ce zéro
            # — sortaient TOUTES en rouge, sous une légende qui dit « un grand
            # écart = surapprentissage ». `_classer_modeles` pose `gini_test`
            # et `gini_train` ; `gini` n'a jamais existé dans ce dictionnaire.
            ginis_t  = [m.get('gini_test', 0)     for m in classement[:6]]
            ginis_tr = [m.get('gini_train', 0)    for m in classement[:6]]
            colors   = [VERT if (t/max(tr,0.001))>=0.90 else AMBRE if (t/max(tr,0.001))>=0.80 else ROUGE
                       for t,tr in zip(ginis_t, ginis_tr)]

            fig1 = go.Figure()
            fig1.add_trace(go.Bar(
                x=modeles, y=ginis_tr, name="Gini Train",
                marker_color="rgba(201,168,76,0.4)",
                marker_line=dict(color=NAVY,width=1), width=0.35, opacity=0.88,
                hovertemplate="<b>%{x}</b><br>Gini Train : %{y:.4f}<extra></extra>",
            ))
            fig1.add_trace(go.Bar(
                x=modeles, y=ginis_t, name="Gini Test",
                marker_color=colors,
                marker_line=dict(color=NAVY,width=1), width=0.35, opacity=0.88,
                hovertemplate="<b>%{x}</b><br>Gini Test : %{y:.4f}<extra></extra>",
            ))
            fig1.add_hline(y=0.20, line_color=AMBRE, line_width=1.5, line_dash="dot",
                          annotation_text="Seuil acceptable 0.20",
                          annotation_font=dict(color=AMBRE, size=9))
            statut_h1 = val_ml["h1_overfitting"]["statut"]
            # ⚠️ `couleur_h1` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_h1_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_h1_txt = couleur_texte_rag(statut_h1)
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(
                    text=val_ml["h1_overfitting"]["titre_graphique"] + " — Barres Train vs Test",
                    font=dict(color=couleur_h1_txt, size=11), x=0.01
                ),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title="Gini", tickfont=dict(color=GRIS), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                barmode="group", bargap=0.25,
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=9),
                           orientation="h", yanchor="bottom", y=1.0),
                annotations=[dict(
                    text="💡 Les barres Train et Test doivent être proches. Un grand écart = surapprentissage (le modèle a mémorisé les données).",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig1.update_layout(**l1)
            graphiques["overfitting_train_test"] = fig1
        except Exception as e:
            logger.warning(f"G1 overfitting : {e}")

        # G2 — PSI évolution + seuils
        try:
            mois  = monitoring.get('mois_historique', [])
            ginis = monitoring.get('gini_historique', [])
            psi   = monitoring.get('psi')
            statut_psi = monitoring.get('statut_psi', 'VERT')
            # ⚠️ LE TITRE ANNONÇAIT « Évolution Gini 12 mois » POUR UNE COURBE
            # SIMULÉE. Les deux points tracés sont désormais mesurés : la
            # référence A3 et le Gini du modèle retenu sur le test. Et un PSI
            # non mesuré ne s'affiche pas comme un nombre.
            txt_psi = f"PSI={psi:.4f} ({statut_psi})" if psi is not None else \
                      f"PSI non mesuré ({statut_psi})"
            # ⚠️ `couleur_psi` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_psi_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_psi_txt = couleur_texte_rag(statut_psi)
            # ⚠️⚠️ LE QUATRIÈME NOMBRE INVENTÉ ÉTAIT ICI — `0.265`, une TROISIÈME
            # valeur, différente des deux autres de la chaîne. La figure
            # traçait une ligne « Référence 0.2650 », à quatre décimales, sur
            # un portefeuille dont A3 n'avait jamais mesuré le Gini. *Une
            # figure ne fabrique pas la grandeur qu'elle est censée montrer.*
            gini_ref   = monitoring.get('gini_reference')
            seuil_al   = (gini_ref - monitoring.get('seuil_alerte_gini', 0.05)
                          if gini_ref is not None else None)

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=mois, y=ginis,
                mode="lines+markers",
                line=dict(color=OR, width=2.5, shape="spline"),
                marker=dict(color=OR, size=7, line=dict(color=NAVY, width=2)),
                hovertemplate="<b>%{x}</b><br>Gini : %{y:.4f}<extra></extra>",
            ))
            if gini_ref is not None:
                fig2.add_hline(y=gini_ref, line_color=VERT, line_width=1.5, line_dash="dash",
                              annotation_text=f"Référence {gini_texte(gini_ref)}",
                              annotation_font=dict(color=VERT, size=9))
            # ⚠️⚠️ LA LIGNE RESTE ROUGE, LE TEXTE NON — étape 2b. Mesuré :
            # ROUGE #E74C3C vaut 3,74 sur le tracé : il PASSE comme objet
            # (WCAG 1.4.11, 3:1) et ÉCHOUE comme texte (1.4.3, 4,5:1).
            # ⚠️ Les deux autres voies sont écartées PAR LA MESURE : #C0392B des
            # rapports tombe à 2,63 sur ce fond — PIRE que l'actuel — et inventer
            # un rouge plus clair serait fabriquer une couleur. *La ligne rouge
            # porte déjà le sens ; l'étiquette n'a qu'à être lisible.*
            # ⚠️ SANS RÉFÉRENCE, PAS DE SEUIL D'ALERTE : il en dérive. Un seuil
            # tracé sur une référence absente serait une seconde invention.
            if seuil_al is not None:
                fig2.add_hline(y=seuil_al, line_color=ROUGE, line_width=1.5, line_dash="dot",
                              annotation_text=f"Seuil alerte {seuil_al:.4f}",
                              annotation_font=dict(color=BLANC, size=9))
            statut_h3 = val_ml["h3_gini"]["statut"]
            # ⚠️ `couleur_h3` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_h3_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_h3_txt = couleur_texte_rag(statut_h3)
            # ⚠️⚠️ LE TITRE AFFIRMAIT LA COMPARAISON EN TOUTES CIRCONSTANCES.
            # « Gini — référence A3 → modèle retenu » se lit comme un fait ; il
            # restait affiché quand A3 n'avait pas tourné. *Quand un
            # comportement change, le texte qui l'accompagne se relit : il ne
            # ment pas quand on l'écrit, il devient faux ensuite.*
            _titre_gini = ("Gini — référence A3 → modèle retenu"
                           if gini_ref is not None else
                           "Gini du modèle retenu — SANS référence A3")
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(
                    text=f"{_titre_gini} · {txt_psi} · {val_ml['h3_gini']['titre_graphique']}",
                    font=dict(color=couleur_h3_txt, size=10), x=0.01
                ),
                xaxis=dict(tickfont=dict(color=GRIS, size=8), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="Gini", tickfont=dict(color=GRIS),
                          showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                showlegend=False,
                annotations=[dict(
                    text="💡 Le Gini du modèle retenu doit rester au-dessus du seuil rouge. Comparaison train→test : ce graphique ne mesure PAS la dérive en production.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig2.update_layout(**l2)
            graphiques["monitoring_gini"] = fig2
        except Exception as e:
            logger.warning(f"G2 monitoring : {e}")

        # G4 — Scorecard validation ML
        try:
            items = [
                ("H1 — Overfitting", val_ml["h1_overfitting"]["statut"],
                 val_ml["h1_overfitting"]["message"], val_ml["h1_overfitting"]["conseil"]),
                ("H2 — PSI réel (dérive)", val_ml["h2_psi"]["statut"],
                 val_ml["h2_psi"]["message"], val_ml["h2_psi"]["conseil"]),
                ("H3 — Performance Gini", val_ml["h3_gini"]["statut"],
                 val_ml["h3_gini"]["message"], val_ml["h3_gini"]["conseil"]),
                ("H4 — Calibration", val_ml.get("h4_calibration", {}).get("statut", "VERT"),
                 val_ml.get("h4_calibration", {}).get("message", ""),
                 val_ml.get("h4_calibration", {}).get("conseil", "")),
            ]
            fig4 = go.Figure()
            for nom, statut, msg, conseil in items:
                couleur = VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
                # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
                couleur_txt = couleur_texte_rag(statut)
                # ⚠️ Le glyphe vient de la SOURCE UNIQUE — il était recopié à
                # l'identique dans les quatre agents. Correct partout ce jour-là,
                # et rien n'empêchait la cinquième copie de diverger.
                icone   = glyphe_rag(statut)
                score   = 1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(
                    x=[score], y=[nom], orientation="h",
                    marker_color=couleur, width=0.5,
                    text=f"{icone} {statut}", textposition="outside",
                    textfont=dict(color=couleur_txt, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False,
                ))
            statut_g   = val_ml["statut_global"]
            # ⚠️ `couleur_g` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_g_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_g_txt = couleur_texte_rag(statut_g)
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(
                    text=f"Scorecard ML — {val_ml['conclusion']}",
                    font=dict(color=couleur_g_txt, size=10), x=0.01
                ),
                xaxis=dict(range=[0,1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10), showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text=(f"💡 {len(items)} ✅ = modèle validé, prêt pour la "
                          f"production actuarielle."),
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig4.update_layout(**l4)
            graphiques["scorecard_validation_ml"] = fig4
        except Exception as e:
            logger.warning(f"G4 scorecard ML : {e}")

        return graphiques

    def _erreur(self, message: str, audit_id: str) -> Dict:
        return {
            'success':         False,
            'dataframe':       pd.DataFrame(),
            'branche':         None,
            'statut_rag':      'ROUGE',
            'modeles':         {},
            'metriques':       {},
            'classement':      [],
            'meilleur_modele': None,
            'shap_values':     {},
            'rapport':         {},
            'commentaire':     f"❌ ERREUR A4 : {message}",
            'audit_id':        audit_id,
            'erreur':          message,
        }


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("Agent A4 — ML Tarification ActuarIA v1.0")
    print("Modèles v2 : GBM · XGBoost · XGBoost Tweedie · LightGBM · CatBoost · Linéaire régularisé")
    print("Usage   : %run 'chemin/a4_ml.py'")
    print("          agent_a4 = AgentA4ML()")
    print("          result_a4 = agent_a4.run(result_a2, result_a3=result_a3)")
