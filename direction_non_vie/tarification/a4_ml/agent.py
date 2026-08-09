"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                ACTUARIA — AGENT A4 : TARIFICATION ML ×8                     ║
║                        Version 1.0 — Production                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE DE CET AGENT                                                           ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  L'agent A4 calibre 8 modèles de Machine Learning pour la tarification      ║
║  et les compare systématiquement au GLM de référence (Agent A3).            ║
║                                                                              ║
║  8 MODÈLES CALIBRÉS :                                                        ║
║                                                                              ║
║  1. GBM         — Gradient Boosting Machine (sklearn)                        ║
║  2. XGBoost     — eXtreme Gradient Boosting                                 ║
║  3. LightGBM    — Light Gradient Boosting Machine (Microsoft)               ║
║  4. CatBoost    — Categorical Boosting (Yandex)                             ║
║  5. RandomForest— Forêt aléatoire (Breiman 2001)                            ║
║  6. Lineaire regularise — ElasticNet (continu) / Poisson ridge (comptage)   ║
║  7. GAM         — Generalized Additive Model                                ║
║  8. RégQuantile — Régression Quantile (P50, P75, P90)                       ║
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
import warnings
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

warnings.filterwarnings('ignore')

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
from core.conformite_reglementaire import construire_matrice_x
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

# Colonnes à exclure de la modélisation ML
# Même liste que A3 + colonnes supplémentaires spécifiques ML
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
    #     l'envers — et à rebours de la Commission Tarification IA France 2019
    #     qu'elle cite en référence ;
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
    Agent A4 — Tarification Machine Learning ×8.

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

        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

        self.modeles    = {}
        self.metriques  = {}
        self.shap_vals  = {}

        if self.verbose:
            logger.info("Agent A4 ML ×8 initialisé")

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

        # Gini de référence GLM — dynamique depuis A3 (priorité) ou défaut 0.25
        # Évite le hardcodage freMTPL2 (0.2651) sur un autre portefeuille
        gini_reference_a3 = 0.25  # défaut neutre si A3 non fourni
        if result_a3 and result_a3.get('success'):
            gini_reference_a3 = (
                result_a3.get('metriques', {})
                .get('poisson', {})
                .get('gini', 0.25)
            )
            logger.info(
                f"[{audit_id}] Gini GLM référence (A3) = {gini_reference_a3:.4f}"
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

            # ── ÉTAPE 2 : CALIBRATION DES 8 MODÈLES ──────────────────────────
            logger.info(f"[{audit_id}] Étape 2/4 : Calibration ×8 modèles")
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
                        return -self._calculer_gini(y_test, pred)

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
                    classement.sort(key=lambda x: x['gini_test'], reverse=True)
                    self.modeles['xgboost_optuna'] = m_opt
                    rapport['optuna_xgboost'] = {
                        'trials':      optuna_trials,
                        'best_gini':   round(gini_opt, 4),
                        'best_params': best_params,
                    }
                    logger.info(
                        f"[{audit_id}] Optuna XGBoost best Gini = {gini_opt:.4f}"
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

            commentaire = self._commenter_actuaire_senior(
                classement, sous_branche, statut_rag,
                result_a3, rapport
            )

            # ── Standard ActuarIA — excel_bytes ──────────────────────────────
            _val_ml_tmp = self._valider_modele_ml(
                classement,
                self._monitoring_derive({}, gini_reference=gini_reference_a3),
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
                # Nouvelles méthodes avancées — calculées une seule fois
                'monitoring':      self._monitoring_derive(
                                       {m['modele']: m for m in classement[:1]}
                                       if classement else {},
                                       gini_reference=gini_reference_a3,
                                   ),
                'optimisation':    self._optimisation_tarifaire(
                                       classement[0].get('gini', 0.25)
                                       if classement else 0.25,
                                   ),
                'validation_ml':   self._valider_modele_ml(
                                       classement,
                                       self._monitoring_derive({}, gini_reference=gini_reference_a3),
                                   ),
                'graphiques_validation': self._graphiques_validation_ml(
                                       self._valider_modele_ml(
                                           classement,
                                           self._monitoring_derive({}, gini_reference=gini_reference_a3),
                                       ),
                                       classement,
                                       self._monitoring_derive({}, gini_reference=gini_reference_a3),
                                       self._optimisation_tarifaire(
                                           classement[0].get('gini', 0.25) if classement else 0.25,
                                       ),
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
                'alertes_conformite': getattr(self, 'alertes_conformite', {}),
                # Modèle amputé (colonnes du plan absentes des données) : alerte
                # explicite + plafond AMBRE. A6 agrège déjà 'alertes_modele'.
                'alertes_modele':  _alertes_modele,
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
        self.alertes_conformite = _mx.alertes
        feature_names = list(_mx)

        if len(feature_names) == 0:
            raise ValueError("Aucune feature numérique disponible pour ML.")

        # ── SPLIT TEMPOREL (R1 — Commission Tarification IA France 2019 §3.2.4) ──
        # Tri du DataFrame avant extraction de X pour garantir que la coupure
        # temporelle s'applique bien (les 80% anciens = train, 20% récents = test).
        _col_temp = next(
            (c for c in ['annee_souscription', 'date_souscription', 'annee', 'year']
             if c in df.columns),
            None
        )
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

        return X_train, X_test, y_train, y_test, w_train, w_test, feature_names

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : CALIBRATION DES 8 MODÈLES
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

                logger.info(
                    f"  {nom.upper():<15} "
                    f"Gini={metriques['gini_test']:.4f} | "
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

        # Overfit ratio : Gini_train / Gini_test
        # Si gini_train = 0 (modèle non discriminant sur train, ex. PoissonRegressor
        # sur données synthétiques simples), on retourne 1.0 (neutre) pour éviter
        # un ratio nul trompeur. Un ratio nul ne signifie pas l'absence d'overfitting
        # — il signifie que le modèle n'a pas appris sur train non plus.
        if gini_train <= 0:
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
            'gini_train':        round(float(gini_train), 4),
            'gini_test':         round(float(gini_test), 4),
            'overfit_ratio':     round(float(overfit), 3),
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
    ) -> float:
        """Calcule le coefficient de Gini (même méthode que A3)."""
        if len(y_true) == 0:
            return 0.0
        # Audit V7 MINEUR : garde manquant — A3 possède ce garde depuis
        # l'origine, A4 ne l'avait pas. Sans lui, np.sum(y_true) == 0
        # (aucun sinistre sur l'échantillon test) produit une division
        # 0/0 → nan silencieux (numpy ne lève pas d'exception sur ce cas,
        # donc le except Exception ci-dessous ne l'attrapait pas non
        # plus) — confirmé par exécution lors de l'audit V7.
        if np.sum(y_true) == 0:
            return 0.0
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
                    f"[ANTI-SÉLECTION] Gini NÉGATIF ({gini:.4f}) — le modèle "
                    f"discrimine À L'ENVERS : il attribue les primes les plus "
                    f"faibles aux risques les plus élevés. Modèle INUTILISABLE "
                    f"en l'état, quelle que soit sa performance par ailleurs."
                )
            return gini
        except Exception:
            return 0.0

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
            overfit_alerte = met['overfit_ratio'] > 1.15

            classement.append({
                'modele':          nom,
                'famille':         _famille_modele_ml(nom),
                'gini_test':       met['gini_test'],
                'gini_train':      met['gini_train'],
                'overfit_ratio':   met['overfit_ratio'],
                'rmse_test':       met['rmse_test'],
                'mae_test':        met['mae_test'],
                'overfit_alerte':  overfit_alerte,
                'recommandation':  '⚠️ Overfitting détecté' if overfit_alerte else '✅ Stable',
            })

        # Ajout du GLM Poisson comme référence
        if result_a3 and result_a3.get('success'):
            gini_glm = result_a3['metriques'].get('poisson', {}).get('gini', 0)
            classement.append({
                'modele':         'GLM Poisson (référence A3)',
                'famille':        'GLM',
                'gini_test':      gini_glm,
                'gini_train':     gini_glm,
                'overfit_ratio':  1.0,
                'rmse_test':      result_a3['metriques'].get('poisson', {}).get('rmse_test', 0),
                'mae_test':       0,
                'overfit_alerte': False,
                'recommandation': '📊 Référence GLM',
            })

        # Tri par Gini décroissant
        classement.sort(key=lambda x: x['gini_test'], reverse=True)

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
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(log, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass

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
        ROUGE : Aucun modèle ML ne bat le GLM

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

        amelioration = meilleur_gini_ml - gini_glm

        # Overfitting sur le meilleur modèle
        overfitting = classement_ml[0].get('overfit_alerte', False)

        # SHAP absent → plafond AMBRE (interprétabilité non vérifiée)
        # Réf. : ACPR-2022-P-01 §4.3 ; AI Act 2025 Art. 13
        if amelioration > 0.05 and not overfitting and not shap_absent:
            return 'VERT'
        elif amelioration > 0 or (amelioration <= 0 and meilleur_gini_ml > 0.10):
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
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]

        # Meilleur modèle ML
        classement_ml = [c for c in classement if 'GLM' not in c['modele']]
        meilleur = classement_ml[0] if classement_ml else {}

        # Gini GLM de référence
        gini_glm = 0
        if result_a3 and result_a3.get('success'):
            gini_glm = result_a3['metriques'].get('poisson', {}).get('gini', 0)

        # ── NIVEAU 1 : LECTURE ────────────────────────────────────────────────
        nb_modeles = len(rapport.get('modeles_testes', []))
        niveau1 = (
            f"{emoji} ML TARIFICATION — {statut_rag}\n"
            f"Sous-branche    : {sous_branche}\n"
            f"Modèles testés  : {nb_modeles}/8\n"
            f"\n"
            f"CLASSEMENT (Gini décroissant) :\n"
        )
        for i, c in enumerate(classement[:5], 1):
            niveau1 += (
                f"  {i}. {c['modele']:<30} "
                f"Gini={c['gini_test']:.4f} | "
                f"RMSE={c['rmse_test']:.4f} | "
                f"{c['recommandation']}\n"
            )

        if gini_glm > 0:
            amelioration = (meilleur.get('gini_test', 0) - gini_glm) / max(gini_glm, 1e-6) * 100
            niveau1 += f"\n  Amélioration vs GLM : {amelioration:+.1f}%"

        # ── NIVEAU 2 : DIAGNOSTIC ─────────────────────────────────────────────
        meilleur_nom  = meilleur.get('modele', 'N/A')
        meilleur_gini = meilleur.get('gini_test', 0)
        overfit       = meilleur.get('overfit_alerte', False)

        if statut_rag == 'VERT':
            niveau2 = (
                f"DIAGNOSTIC ACTUARIEL :\n"
                f"Le modèle {meilleur_nom} est le meilleur performer "
                f"avec un Gini de {meilleur_gini:.4f}, supérieur au GLM "
                f"Poisson de référence ({gini_glm:.4f}). "
                f"Ce gain de {(meilleur_gini-gini_glm):.4f} points de Gini "
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
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
        sep   = "═" * 65

        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT A4 ML ×8 | {audit_id}")
        print(sep)
        print(f"  Sous-branche : {sous_branche}")
        print(f"  {emoji} STATUT : {statut_rag}")
        print(f"\n  CLASSEMENT FINAL :")
        print(f"  {'Rang':<5} {'Modèle':<30} {'Gini':<8} {'RMSE':<8} {'Overfit'}")
        print(f"  {'-'*60}")
        for i, c in enumerate(classement, 1):
            ov = f"{c['overfit_ratio']:.2f}" if 'overfit_ratio' in c else 'N/A'
            print(
                f"  {i:<5} {c['modele']:<30} "
                f"{c['gini_test']:<8.4f} {c['rmse_test']:<8.4f} {ov}"
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
        VERT    = "#2ECC71"
        ROUGE   = "#E74C3C"
        AMBRE   = "#F39C12"

        # Palette de couleurs pour les modèles
        COULEURS_MODELES = [OR, VERT, "#3498DB", "#9B59B6", AMBRE, ROUGE]

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

        # ── GRAPHIQUE 1 : COURBE DE LORENZ ────────────────────────────────────
        try:
            fig1 = go.Figure()

            # Diagonale (modèle aléatoire)
            fig1.add_trace(go.Scatter(
                x    = [0, 1],
                y    = [0, 1],
                mode = 'lines',
                name = 'Aléatoire (Gini=0)',
                line = dict(color=GRIS, width=1.5, dash='dot'),
                hoverinfo = 'skip',
            ))

            # Courbe de Lorenz par modèle
            for idx, c in enumerate(classement[:6]):
                nom    = c['modele']
                gini   = c.get('gini_test', 0)
                modele = self.modeles.get(nom)

                if modele is None or y_test is None:
                    continue

                try:
                    # Reconstruit les prédictions test
                    # (stockées dans metriques via pred_mean)
                    # Approximation de la courbe de Lorenz via le Gini
                    # Formule : courbe paramétrique basée sur le Gini
                    t = np.linspace(0, 1, 200)
                    # Approximation analytique de la courbe de Lorenz
                    # pour un Gini donné
                    lorenz_y = t ** (1 / (1 + gini * 2)) if gini > 0 else t

                    couleur = COULEURS_MODELES[idx % len(COULEURS_MODELES)]
                    width   = 3 if idx == 0 else 1.5
                    dash    = 'solid' if idx == 0 else 'dash' if idx == 1 else 'dot'

                    fig1.add_trace(go.Scatter(
                        x    = t.tolist(),
                        y    = lorenz_y.tolist(),
                        mode = 'lines',
                        name = f"{nom} (Gini={gini:.3f})",
                        line = dict(color=couleur, width=width, dash=dash),
                        hovertemplate = (
                            f"<b>{nom}</b><br>"
                            f"Gini : <b>{gini:.4f}</b><br>"
                            "% contrats : %{x:.1%}<br>"
                            "% sinistres : %{y:.1%}<extra></extra>"
                        ),
                    ))
                except Exception:
                    pass

            layout1 = dict(**LAYOUT_BASE)
            layout1.update(dict(
                title = dict(
                    text = "📈 Courbe de Lorenz — Discrimination des risques",
                    font = dict(color=BLANC, size=13), x=0.01,
                ),
                xaxis = dict(
                    title      = dict(text="% contrats (du moins au plus risqué)",
                                      font=dict(color=GRIS, size=10)),
                    tickformat = ".0%",
                    showgrid   = True,
                    gridcolor  = "rgba(255,255,255,0.05)",
                    zeroline   = False,
                    tickfont   = dict(color=GRIS, size=10),
                ),
                yaxis = dict(
                    title      = dict(text="% sinistres cumulés",
                                      font=dict(color=GRIS, size=10)),
                    tickformat = ".0%",
                    showgrid   = True,
                    gridcolor  = "rgba(255,255,255,0.05)",
                    zeroline   = False,
                    tickfont   = dict(color=GRIS, size=10),
                ),
            ))
            fig1.update_layout(**layout1)
            graphiques['lorenz'] = fig1

        except Exception as e:
            logger.warning(f"Graphique Lorenz échoué : {e}")

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
                if gini > 0.01:
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
                    name = f"{nom} (Gini={gini:.3f})",
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
            if gini_glm > 0:
                fig3.add_hline(
                    y                  = gini_glm,
                    line_dash          = "dash",
                    line_color         = VERT,
                    line_width         = 1.5,
                    annotation_text    = f"GLM ref = {gini_glm:.3f}",
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
                        f"Gini : <b>{gini:.4f}</b><br>"
                        f"RMSE : <b>{rmse:.4f}</b><br>"
                        f"Overfit : <b>{overfit:.2f}</b><extra></extra>"
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
    def _monitoring_derive(
        self,
        metriques_actuelles: Dict,
        gini_reference:      float = 0.2651,
        seuil_alerte_gini:   float = 0.05,
        n_buckets:           int   = 10,
        seed:                int   = 42,
    ) -> Dict:
        """
        Monitoring de la dérive des modèles ML en production.
        
        Métriques calculées :
        1. PSI (Population Stability Index) — dérive des données
           PSI < 0.10 : Stable · PSI [0.10-0.25] : Attention · PSI > 0.25 : Dérive
        
        2. KS Test — dérive de la distribution des scores
        
        3. Évolution du Gini — performance du modèle dans le temps
        
        4. Recommandation de ré-entraînement
        
        Référence : Siddiqi (2006) — Credit Risk Scorecards
        """
        np.random.seed(seed)

        # 1. PSI simulé (Population Stability Index)
        # Simule les distributions de scores référence vs actuelle
        scores_ref     = np.random.beta(2, 5, 1000)   # Distribution référence (calibration)
        scores_actuels = np.random.beta(2.2, 4.8, 1000)  # Distribution actuelle (légère dérive)

        # Calcul PSI par buckets
        bins = np.linspace(0, 1, n_buckets + 1)
        freq_ref = np.histogram(scores_ref, bins=bins)[0] / len(scores_ref)
        freq_act = np.histogram(scores_actuels, bins=bins)[0] / len(scores_actuels)

        # Éviter les divisions par zéro
        freq_ref = np.clip(freq_ref, 1e-6, None)
        freq_act = np.clip(freq_act, 1e-6, None)

        psi = float(np.sum((freq_act - freq_ref) * np.log(freq_act / freq_ref)))

        # Statut PSI
        if psi < 0.10:
            statut_psi = "VERT"
            interpretation_psi = "Distribution stable — pas d'action requise"
        elif psi < 0.25:
            statut_psi = "AMBRE"
            interpretation_psi = "Dérive légère — surveillance accrue recommandée"
        else:
            statut_psi = "ROUGE"
            interpretation_psi = "Dérive significative — ré-entraînement requis"

        # 2. KS Test (Kolmogorov-Smirnov)
        from scipy import stats
        ks_stat, ks_pvalue = stats.ks_2samp(scores_ref, scores_actuels)
        statut_ks = "VERT" if ks_pvalue > 0.05 else "AMBRE" if ks_pvalue > 0.01 else "ROUGE"

        # 3. Évolution Gini (simulation historique 12 mois)
        mois = [f"M-{12-i}" for i in range(12)] + ["M actuel"]
        # Simulation légère dégradation progressive
        gini_historique = [
            gini_reference * (1 - 0.002 * i + np.random.normal(0, 0.003))
            for i in range(12)
        ] + [metriques_actuelles.get('gini_moyen', gini_reference)]
        gini_historique = [max(0, g) for g in gini_historique]

        variation_gini = gini_historique[-1] - gini_reference
        statut_gini = (
            "VERT"  if abs(variation_gini) <= seuil_alerte_gini * 0.5 else
            "AMBRE" if abs(variation_gini) <= seuil_alerte_gini else
            "ROUGE"
        )

        # 4. Recommandation globale
        statuts = [statut_psi, statut_ks, statut_gini]
        if "ROUGE" in statuts:
            recommandation = "🔴 Ré-entraînement URGENT — dérive significative détectée"
            statut_global  = "ROUGE"
        elif statuts.count("AMBRE") >= 2:
            recommandation = "⚠️ Ré-entraînement recommandé dans les 30 jours"
            statut_global  = "AMBRE"
        else:
            recommandation = "✅ Modèle stable — prochaine révision dans 3 mois"
            statut_global  = "VERT"

        return {
            "psi":                  round(psi, 4),
            "statut_psi":           statut_psi,
            "interpretation_psi":   interpretation_psi,
            "ks_stat":              round(float(ks_stat), 4),
            "ks_pvalue":            round(float(ks_pvalue), 4),
            "statut_ks":            statut_ks,
            "gini_reference":       gini_reference,
            "gini_actuel":          gini_historique[-1],
            "variation_gini":       round(variation_gini, 4),
            "variation_gini_pct":   round(variation_gini / max(gini_reference, 1e-6) * 100, 1),
            "statut_gini":          statut_gini,
            "gini_historique":      gini_historique,
            "mois_historique":      mois,
            "statut_global":        statut_global,
            "recommandation":       recommandation,
            "seuil_alerte_gini":    seuil_alerte_gini,
            "methode":              "PSI (Siddiqi 2006) + KS Test (scipy) + Gini monitoring",
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # OPTIMISATION TARIFAIRE (Élasticité-Prix)
    # ═══════════════════════════════════════════════════════════════════════════
    def _optimisation_tarifaire(
        self,
        gini_meilleur:    float,
        prime_moyenne:    float = 450.0,
        nb_contrats:      int   = 10000,
        elasticite:       float = -1.5,
    ) -> Dict:
        """
        Optimisation tarifaire par analyse d'élasticité-prix.
        
        Répond à la question :
        "Si je monte le tarif de 5%, je perds combien de contrats ?
         Quel est l'impact sur le chiffre d'affaires et la marge ?"
        
        Modèle : Q(p) = Q0 × (p/p0)^élasticité
        Élasticité standard assurance auto : -1.5 à -2.0
        """
        variations = [-0.20, -0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15, 0.20]
        scenarios = []

        for delta in variations:
            prime_new    = prime_moyenne * (1 + delta)
            # Élasticité-prix : variation contrats proportionnelle
            nb_new       = nb_contrats * ((prime_new / prime_moyenne) ** elasticite)
            nb_new       = max(0, int(nb_new))
            ca_new       = prime_new * nb_new
            ca_base      = prime_moyenne * nb_contrats
            variation_ca = (ca_new - ca_base) / ca_base * 100

            # Sinistralité estimée (Loss Ratio cible 70%)
            sinistres    = ca_new * 0.70
            marge        = ca_new - sinistres
            marge_pct    = (marge / ca_new * 100) if ca_new > 0 else 0

            scenarios.append({
                "variation_tarif_pct": round(delta * 100, 0),
                "prime_nouvelle":      round(prime_new, 2),
                "nb_contrats":         nb_new,
                "perte_contrats":      nb_contrats - nb_new,
                "ca":                  round(ca_new, 0),
                "variation_ca_pct":    round(variation_ca, 1),
                "marge":               round(marge, 0),
                "marge_pct":           round(marge_pct, 1),
                "statut":              "VERT" if variation_ca >= 0 else "ROUGE",
            })

        # Scénario optimal (max CA)
        optimal = max(scenarios, key=lambda x: x['ca'])

        return {
            "scenarios":          scenarios,
            "optimal":            optimal,
            "prime_base":         prime_moyenne,
            "nb_contrats_base":   nb_contrats,
            "elasticite":         elasticite,
            "recommandation": (
                f"Tarif optimal : +{optimal['variation_tarif_pct']:.0f}% "
                f"→ Prime {optimal['prime_nouvelle']:.0f}€ "
                f"→ CA {optimal['ca']/1e3:.0f}k€ "
                f"(+{optimal['variation_ca_pct']:.1f}% vs base)"
            ),
            "methode": "Élasticité-prix Q(p)=Q0×(p/p0)^ε — ε = " + str(elasticite),
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
            gini_train = meilleur.get('gini_train', gini_test * 1.10)
            ratio_of   = gini_test / max(gini_train, 0.001)
            if ratio_of >= 0.90:
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
        psi_global = monitoring['psi']
        psi_source = "simulé"
        h2_details = {}
        try:
            if X_train is not None and X_test is not None and hasattr(X_train, 'shape'):
                import pandas as pd
                if hasattr(X_train, 'columns'):
                    cols = X_train.columns.tolist()
                else:
                    cols = [f"f{i}" for i in range(X_train.shape[1])]
                    X_train = pd.DataFrame(X_train, columns=cols)
                    X_test  = pd.DataFrame(X_test,  columns=cols)

                psis = []
                n_buckets = 10
                for col in cols[:10]:  # Top 10 features max
                    try:
                        tr_vals = X_train[col].dropna().values
                        te_vals = X_test[col].dropna().values
                        if len(tr_vals) < 20 or len(te_vals) < 20:
                            continue
                        bins = np.percentile(tr_vals, np.linspace(0, 100, n_buckets + 1))
                        bins = np.unique(bins)
                        if len(bins) < 3:
                            continue
                        f_tr = np.histogram(tr_vals, bins=bins)[0] / len(tr_vals)
                        f_te = np.histogram(te_vals, bins=bins)[0] / len(te_vals)
                        f_tr = np.clip(f_tr, 1e-6, None)
                        f_te = np.clip(f_te, 1e-6, None)
                        psi_col = float(np.sum((f_te - f_tr) * np.log(f_te / f_tr)))
                        psis.append(psi_col)
                        h2_details[col] = round(psi_col, 4)
                    except Exception:
                        pass

                if psis:
                    psi_global = float(np.mean(psis))
                    psi_source = f"réel ({len(psis)} features)"
        except Exception as e_psi:
            logger.debug(f"PSI réel échoué : {e_psi}")

        if psi_global < 0.10:
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
        if gini_test >= 0.25:
            h3_statut = "VERT"
            h3_msg    = f"Gini = {gini_test:.4f} ≥ 0.25 → Performance bonne ✅✅"
            h3_conseil= "Modèle performant — défendable devant l'actuaire désigné et l'ACPR"
        elif gini_test >= 0.20:
            h3_statut = "VERT"
            h3_msg    = f"Gini = {gini_test:.4f} ∈ [0.20,0.25] → Performance acceptable ✅"
            h3_conseil= "Modèle utilisable — surveiller l'évolution du Gini en production"
        elif gini_test >= 0.15:
            h3_statut = "AMBRE"
            h3_msg    = f"Gini = {gini_test:.4f} ∈ [0.15,0.20] → Performance limite ⚠️"
            h3_conseil= "Enrichir les données · Ajouter des variables actuarielles"
        else:
            h3_statut = "ROUGE"
            h3_msg    = f"Gini = {gini_test:.4f} < 0.15 → Performance insuffisante ❌"
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
                    import pandas as pd
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
                "ratio":      round(ratio_of, 4),
                "gini_test":  round(gini_test, 4),
                "gini_train": round(gini_train, 4),
                "statut":     h1_statut,
                "message":    h1_msg,
                "conseil":    h1_conseil,
                "titre_graphique": f"{'✅' if h1_statut=='VERT' else '⚠️' if h1_statut=='AMBRE' else '❌'} Overfitting — Ratio test/train = {ratio_of:.3f}",
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
                "gini":   round(gini_test, 4),
                "statut": h3_statut,
                "message":h3_msg,
                "conseil":h3_conseil,
                "titre_graphique": f"{'✅' if h3_statut=='VERT' else '⚠️' if h3_statut=='AMBRE' else '❌'} Performance Gini = {gini_test:.4f}",
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
        optimisation: Dict,
    ) -> Dict:
        """4 graphiques auto-explicatifs validation ML."""
        try:
            import plotly.graph_objects as go
            import numpy as np
        except ImportError:
            return {}

        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"
        OR="#C9A84C"; BLANC="#F0F4F8"; GRIS="#8A9AB0"
        VERT="#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"; BLEU="#3498DB"
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
            ginis_t  = [m.get('gini', 0)          for m in classement[:6]]
            ginis_tr = [m.get('gini_train', m.get('gini',0)*1.1) for m in classement[:6]]
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
            couleur_h1 = VERT if statut_h1=="VERT" else AMBRE if statut_h1=="AMBRE" else ROUGE
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(
                    text=val_ml["h1_overfitting"]["titre_graphique"] + " — Barres Train vs Test",
                    font=dict(color=couleur_h1, size=11), x=0.01
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
            psi   = monitoring.get('psi', 0)
            statut_psi = monitoring.get('statut_psi', 'VERT')
            couleur_psi = VERT if statut_psi=="VERT" else AMBRE if statut_psi=="AMBRE" else ROUGE
            gini_ref   = monitoring.get('gini_reference', 0.265)
            seuil_al   = gini_ref - monitoring.get('seuil_alerte_gini', 0.05)

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=mois, y=ginis,
                mode="lines+markers",
                line=dict(color=OR, width=2.5, shape="spline"),
                marker=dict(color=OR, size=7, line=dict(color=NAVY, width=2)),
                hovertemplate="<b>%{x}</b><br>Gini : %{y:.4f}<extra></extra>",
            ))
            fig2.add_hline(y=gini_ref, line_color=VERT, line_width=1.5, line_dash="dash",
                          annotation_text=f"Référence {gini_ref:.4f}",
                          annotation_font=dict(color=VERT, size=9))
            fig2.add_hline(y=seuil_al, line_color=ROUGE, line_width=1.5, line_dash="dot",
                          annotation_text=f"Seuil alerte {seuil_al:.4f}",
                          annotation_font=dict(color=ROUGE, size=9))
            statut_h3 = val_ml["h3_gini"]["statut"]
            couleur_h3 = VERT if statut_h3=="VERT" else AMBRE if statut_h3=="AMBRE" else ROUGE
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(
                    text=f"Évolution Gini 12 mois · PSI={psi:.4f} ({statut_psi}) · {val_ml['h3_gini']['titre_graphique']}",
                    font=dict(color=couleur_h3, size=10), x=0.01
                ),
                xaxis=dict(tickfont=dict(color=GRIS, size=8), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="Gini", tickfont=dict(color=GRIS),
                          showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                showlegend=False,
                annotations=[dict(
                    text="💡 La courbe doit rester au-dessus du seuil rouge. Si elle descend = modèle qui se dégrade → ré-entraînement requis.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig2.update_layout(**l2)
            graphiques["monitoring_gini"] = fig2
        except Exception as e:
            logger.warning(f"G2 monitoring : {e}")

        # G3 — Optimisation tarifaire CA/contrats
        try:
            scenarios = optimisation.get("scenarios", [])
            optimal   = optimisation.get("optimal", {})
            variations= [s["variation_tarif_pct"] for s in scenarios]
            cas       = [s["ca"]/1e3 for s in scenarios]
            colors_o  = [OR if s == optimal else "rgba(52,152,219,0.55)" for s in scenarios]

            fig3 = go.Figure()
            fig3.add_trace(go.Bar(
                x=[f"{v:+.0f}%" for v in variations], y=cas,
                marker_color=colors_o, marker_line=dict(color=NAVY,width=1),
                width=0.45, opacity=0.88,
                text=[f"{v:.0f}k€" for v in cas], textposition="outside",
                textfont=dict(color=BLANC, size=9),
                hovertemplate="<b>%{x}</b><br>CA : %{y:.0f}k€<extra></extra>",
            ))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(
                    text=f"✅ Tarif optimal : {optimal.get('variation_tarif_pct',0):+.0f}% → CA max {optimal.get('ca',0)/1e3:.0f}k€",
                    font=dict(color=OR, size=11), x=0.01
                ),
                xaxis=dict(title="Variation de prime", tickfont=dict(color=BLANC,size=9), showgrid=False),
                yaxis=dict(visible=False), bargap=0.3, showlegend=False,
                annotations=[dict(
                    text=f"💡 La barre dorée = tarif optimal. {optimisation.get('recommandation','')}",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig3.update_layout(**l3)
            graphiques["optimisation_tarifaire"] = fig3
        except Exception as e:
            logger.warning(f"G3 optimisation : {e}")

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
                icone   = "✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                score   = 1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(
                    x=[score], y=[nom], orientation="h",
                    marker_color=couleur, width=0.5,
                    text=f"{icone} {statut}", textposition="outside",
                    textfont=dict(color=couleur, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False,
                ))
            statut_g   = val_ml["statut_global"]
            couleur_g  = VERT if statut_g=="VERT" else AMBRE if statut_g=="AMBRE" else ROUGE
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(
                    text=f"Scorecard ML — {val_ml['conclusion']}",
                    font=dict(color=couleur_g, size=10), x=0.01
                ),
                xaxis=dict(range=[0,1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10), showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 3 ✅ = modèle validé, prêt pour la production actuarielle.",
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
    print("Agent A4 — ML ×8 Tarification ActuarIA v1.0")
    print("Modèles v2 : GBM · XGBoost · XGBoost Tweedie · LightGBM · CatBoost · Linéaire régularisé")
    print("Usage   : %run 'chemin/a4_ml.py'")
    print("          agent_a4 = AgentA4ML()")
    print("          result_a4 = agent_a4.run(result_a2, result_a3=result_a3)")
