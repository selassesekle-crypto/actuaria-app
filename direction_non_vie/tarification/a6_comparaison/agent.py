"""
╔══════════════════════════════════════════════════════════════════════════════╗
║            ACTUARIA — AGENT A6 : COMPARAISON & VALIDATION FINALE            ║
║                        Version 1.0 — Production                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE DE CET AGENT                                                           ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  L'agent A6 agrège les résultats de A3 (GLM), A4 (ML) et A5 (DL)          ║
║  et produit la sélection finale du modèle de production.                   ║
║                                                                              ║
║  MÉTRIQUES DE COMPARAISON :                                                  ║
║  • Gini (pouvoir discriminant — critère principal)                          ║
║  • RMSE / MAE (précision des prédictions)                                   ║
║  • Overfit ratio (stabilité train/test)                                     ║
║  • Backtesting temporel N-2/N-1 → N                                        ║
║  • Test A/E (Actual vs Expected)                                            ║
║  • Lift curve et double-lift curve                                          ║
║  • Courbe de Lorenz                                                         ║
║                                                                              ║
║  SÉLECTION DU MODÈLE DE PRODUCTION :                                        ║
║  L'agent applique une grille multicritères actuarielle :                    ║
║  Gini (40%) + Stabilité (30%) + Interprétabilité (20%) + RMSE (10%)       ║
║                                                                              ║
║  AUTONOMIE : Niveau 2                                                        ║
║  AUTEUR    : ActuarIA v1.0                                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, json, pickle, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# Graphiques V3 (charte partagée core/charts_tarif) — import gardé, optionnel.
try:
    from core.charts_tarif import (
        chart_lift_decile, chart_lorenz_gini, chart_walkforward_ae)
    _CHARTS_V3_OK = True
except Exception:
    _CHARTS_V3_OK = False
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error

try:
    from .services.rapport_modeles_tarif import generer_rapport_tarification
    TARIF_RAPPORT_OK = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.rapport_modeles_tarif import generer_rapport_tarification
        TARIF_RAPPORT_OK = True
    except ImportError:
        TARIF_RAPPORT_OK = False

# Fabrique de modèles ML (audit V4 reco #7) — permet de recalibrer le
# MODÈLE RÉELLEMENT RETENU dans le walk-forward, au lieu d'un proxy
# GradientBoostingRegressor générique quel que soit le modèle affiché.
try:
    from ..a4_ml.agent import creer_modele_ml_pour_nom
    CREER_MODELE_ML_OK = True
except ImportError:
    try:
        from direction_non_vie.tarification.a4_ml.agent import creer_modele_ml_pour_nom
        CREER_MODELE_ML_OK = True
    except ImportError:
        CREER_MODELE_ML_OK = False

try:
    from .services.rapport_equipe_tarif import generer_rapport_equipe_tarification
    RAPPORT_EQUIPE_OK = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.rapport_equipe_tarif import (
            generer_rapport_equipe_tarification
        )
        RAPPORT_EQUIPE_OK = True
    except ImportError:
        RAPPORT_EQUIPE_OK = False

try:
    from .services.archive_livrable import archiver_livrable
    ARCHIVE_OK = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.archive_livrable import archiver_livrable
        ARCHIVE_OK = True
    except ImportError:
        ARCHIVE_OK = False

try:
    from ..services.tarif_excel import export_excel_a6
    TARIF_EXCEL_OK = True
except ImportError:
    TARIF_EXCEL_OK = False

# Filtres anti-fuite / conformité partagés (audit V8 + V9) — même source
# que A3/A4/A5. Historique : le walk-forward n'appliquait que
# filtrer_famille_cible ; l'audit V9 (BLOQUANT) a prouvé qu'une colonne
# genre pré-encodée (scénario V7) traversait donc intacte jusqu'à la
# recalibration walk-forward.
from core.charts_tarif import FOND_SOMBRE, couleur_rag, couleur_texte_rag, glyphe_rag
from core.conformite_reglementaire import (
    agreger_controle_effet, avertissement_walk_forward,
    construire_matrice_x, verdict_vraisemblance_gini,
    reserve_bases_gini_melangees,
    meilleur_par_base, reserve_arbitrage_contestable,
    VRAISEMBLANCE_IMPLAUSIBLE, VRAISEMBLANCE_NON_CALIBRE,
    reserve_vraisemblance_non_calibree,
    GINI_PLAUSIBLE_MAX_FREQUENCE,
    AE_FENETRE_ACCEPTABLE, AE_FENETRE_STRICTE,
)

#: ⚠️⚠️ LE VOCABULAIRE DES SPLITS, NOMMÉ — constat `a6/C6`.
#: Trois sites comparaient `backtest['split']` au littéral
#: `'walk_forward_temporel'`, alors que le code n'écrit JAMAIS cette chaîne :
#: il écrit `'aléatoire_80_20'` ou `'walk_forward_temporel_avec_recalibration'`.
#: Les trois branches étaient donc MORTES — deux assertions de test qui ne
#: s'exécutaient jamais, et, dans l'agent, le bloc qui publie les fenêtres du
#: walk-forward. *Une chaîne recopiée à la main dans quatre fichiers finit par
#: diverger ; une constante ne le peut pas.*
#: ⚠️⚠️ LE SEUIL DE STABILITÉ, NOMMÉ — site 9 de l'inventaire des ronds.
#: `stabilite_wf` est un LIBELLÉ D'AFFICHAGE (« 🔴 Instable »), et le verrou du
#: statut RAG décidait en cherchant `'🔴' in _stab` : **une décision
#: réglementaire suspendue à la présence d'un emoji dans une chaîne**. Qu'on
#: réécrive « Instable ❌ » et le garde-fou cesse de bloquer, EN SILENCE —
#: exactement le défaut `a6/C6`. Le seuil est nommé ici pour que le libellé et
#: la décision lisent LE MÊME nombre et ne puissent plus diverger.
SEUIL_CV_INSTABLE = 0.10

SPLIT_ALEATOIRE = 'aléatoire_80_20'
SPLIT_WALK_FORWARD = 'walk_forward_temporel_avec_recalibration'


warnings.filterwarnings('ignore')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('actuaria.a6')


# ── GOUVERNANCE : QUI ASSUME LA DÉCISION ──────────────────────────────────────
#
#  ⚠️ CE PRÉDICAT VIVAIT EN DEUX EXEMPLAIRES — dans `_calculer_statut_rag` et
#  dans l'audit trail — tenus d'accord par rien. Deux copies de la même règle
#  finissent par diverger, et celle-ci aurait divergé au premier durcissement :
#  l'audit trail aurait annoncé « gouvernance validée » sur un rapport
#  plafonné pour défaut de gouvernance. C'est le motif que ce dépôt a fermé
#  sur les σ, sur les paramètres de la formule standard et sur les courbes de
#  taux. Une seule copie, deux appelants.
#
#  ⚠️ ET IL TESTAIT `is None` : une chaîne VIDE le satisfaisait. Un champ
#  « validé par » qui accepte du vide ne valide rien — c'est la même famille
#  que le mot « Actuaire » passé par la démo, une valeur qui contente le
#  contrôle sans nommer personne.
def gouvernance_validee(profil_valide_par, environnement='production') -> bool:
    """La décision de modèle est-elle assumée par quelqu'un de nommé ?

    Hors production, la question ne se pose pas : le contrôle ne s'applique
    qu'aux décisions destinées à produire un tarif.
    """
    if str(environnement or 'production') != 'production':
        return True
    return bool(str(profil_valide_par or '').strip())


# ── GRILLE MULTICRITÈRES ──────────────────────────────────────────────────────
# Profils de pondération prédéfinis
# Le profil est sélectionnable par client dans l'interface Streamlit

PROFILS_PONDERATION = {
    'equilibre': {
        # Profil par défaut — bon équilibre performance/stabilité/interprétabilité
        'gini': 0.40, 'stabilite': 0.30, 'interpretabilite': 0.20, 'rmse': 0.10,
    },
    'performance': {
        # Profil performance — privilégie le Gini (discrimination maximale)
        # Usage : portefeuilles avec forte hétérogénéité des risques
        'gini': 0.60, 'stabilite': 0.20, 'interpretabilite': 0.10, 'rmse': 0.10,
    },
    'auditabilite_s2': {
        # Profil auditabilité — privilégie l'interprétabilité et la stabilité
        # Usage : compagnies soumises à audit S2 strict (ACPR)
        'gini': 0.25, 'stabilite': 0.35, 'interpretabilite': 0.30, 'rmse': 0.10,
    },
    'compagnie_vie': {
        # Profil Vie/Prévoyance — stabilité prioritaire (engagements longs)
        'gini': 0.30, 'stabilite': 0.40, 'interpretabilite': 0.20, 'rmse': 0.10,
    },
}

# Profil actif par défaut
POIDS_CRITERES = PROFILS_PONDERATION['equilibre']

# Score d'interprétabilité par famille de modèle
# Justification : le GLM est le plus interprétable (coefficients β lisibles)
# Les modèles ML sont partiellement interprétables via SHAP
# Le Deep Learning pur est moins interprétable (boîte noire)
INTERPRETABILITE = {
    'poisson':        1.00,   # GLM — coefficients directement lisibles
    'gamma':          1.00,
    'tweedie':        1.00,
    'cann':           0.80,   # CANN — composante GLM visible
    'tabnet':         0.75,   # TabNet — attention weights
    'gbm':            0.60,   # ML avec SHAP
    'xgboost':        0.60,
    'lightgbm':       0.60,
    'catboost':        0.60,
    'random_forest':  0.55,
    'lineaire_regularise': 0.85,   # Poisson ridge (comptage) ou ElasticNet (continu)
    'quantile_50':    0.80,
    'quantile_90':    0.80,
}


class AgentA6Comparaison:
    """
    Agent A6 — Comparaison & Validation finale des modèles.

    Agrège A3 + A4 + A5 et sélectionne le modèle de production
    via une grille multicritères actuarielle.

    EXEMPLE D'UTILISATION :
    ─────────────────────────
    agent_a6 = AgentA6Comparaison(
        models_path = '/tmp/actuaria',
        audit_path  = '/tmp/actuaria',
    )
    result_a6 = agent_a6.run(result_a2, result_a3, result_a4, result_a5)
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

        if self.verbose:
            logger.info("Agent A6 Comparaison initialisé")

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTHODE PRINCIPALE
    # ══════════════════════════════════════════════════════════════════════════

    def run(
        self,
        result_a2:   Dict[str, Any],
        result_a1:   Optional[Dict] = None,
        result_a3:   Optional[Dict] = None,
        result_a4:   Optional[Dict] = None,
        result_a5:   Optional[Dict] = None,
        # Plan signé = autorité des features. Passé, le walk-forward recalibre sur
        # plan.colonnes_produites() (comme A3/A4/A5) au lieu de « toutes les colonnes
        # numériques » → le modèle recalibré a la MÊME spécification que la production
        # (correctif V15 #2). None → repli sur l'ancien comportement (rétro-compat).
        plan:        Optional[Any] = None,
        col_cible:   str = 'prime_pure',
        col_expo:    str = 'exposition',
        profil:      str = 'equilibre',
        poids_custom:        Optional[Dict] = None,
        generer_graphiques:  bool = True,
        aide_decision:       bool = True,
        profil_valide_par:   Optional[str] = None,
        environnement:       str = 'production',
        valide_par_actuaire_dl: Optional[str] = None,
        # ⚠️ LA RELECTURE ACTUARIELLE DU RAPPORT — À NE PAS CONFONDRE AVEC
        # `profil_valide_par`, JUSTE AU-DESSUS. Celui-là valide une DÉCISION
        # DE MODÉLISATION (la pondération des critères) et plafonne le statut
        # RAG, parce qu'il change ce que le classement vaut. Celui-ci
        # enregistre qu'un actuaire a RELU LE DOCUMENT : il n'entre dans aucun
        # plafond, il se publie. A6 ne l'utilise pas, il le fait transiter —
        # même mécanisme que `rapport_qualite` et le champ DL.
        actuaire_nom:        Optional[str] = None,
        actuaire_numero_ia:  Optional[str] = None,
        # RapportQualite (core/qualite_donnees.py) du chemin déclaratif
        # (pipeline_complet). A6 ne l'UTILISE pas — il le fait TRANSITER vers les
        # 3 rapports (synthese_qualite_donnees), même mécanisme que le champ DL.
        rapport_qualite:     Optional[Any] = None,
        # RapportMapping (core/mapping_client.py) produit AVANT A1 par le mapping
        # du fichier client. A6 ne l'UTILISE pas non plus — il le TRANSITE vers les
        # 3 rapports (synthese_mapping), exactement comme rapport_qualite. None sur
        # la quasi-totalité des appels (pas de mapping) → rien affiché.
        rapport_mapping:     Optional[Any] = None,
        generer_rapport_equipe: bool = True,
        formats_equipe:      Optional[List[str]] = None,
        # ⚠️ Archivage vérifiable du livrable signé (dossier + empreintes),
        # DORMANT par défaut — comme l'arrête de C1, aucun appelant de
        # production ne l'active encore. Voir services/archive_livrable.
        archiver:            bool = False,
    ) -> Dict[str, Any]:
        """
        Pipeline de comparaison et validation finale.

        result_a1 : dict, optionnel
            Résultat de l'agent A1 (qualité des données). Utilisé uniquement
            pour enrichir le rapport consolidé équipe (§2 — Qualité données).

        profil_valide_par : str, optionnel
            Nom/identifiant de l'actuaire ayant validé le profil de
            pondération. Si None ET environnement='production', le statut
            est plafonné à AMBRE (gouvernance ACPR-2022-P-01 §4.3).
            Réf. : Recommandation P5 — Certification actuarielle v3.

        generer_rapport_equipe : bool
            Si True (défaut), génère le rapport consolidé équipe A1→A6
            (dashboard de gouvernance). Réutilise le commentaire actuariel
            déjà produit par A6 — n'effectue AUCUN nouvel appel Claude API.

        formats_equipe : list, optionnel
            Formats du rapport équipe : sous-liste de ['excel','html','word','pdf'].
            Défaut : tous les 4 formats.

        environnement : str
            'production' (DÉFAUT — fail-safe, audit V4 point #10) ou
            'developpement'. Détermine si le contrôle profil_valide_par
            est bloquant (plafond AMBRE si non validé).

            Le défaut est volontairement 'production', pas 'developpement' :
            un appelant qui OUBLIE de préciser l'environnement doit tomber
            sur le comportement le plus restrictif, jamais l'inverse.
            Réf. : Saltzer & Schroeder (1975), "The Protection of
            Information in Computer Systems", principe des fail-safe
            defaults. Pour un usage de développement/test sans le
            plafonnement de gouvernance, préciser explicitement
            environnement='developpement'.

        ÉTAPES :
        1. Agrégation de tous les résultats A3/A4/A5
        2. Calcul du score multicritères pour chaque modèle
        3. Classement final et sélection du modèle de production
        4. Backtesting temporel (validation sur données historiques)
        5. Courbe de Lorenz + lift curve
        6. Rapport et commentaire actuaire sénior
        """
        t_debut      = datetime.now()
        audit_id     = f"A6_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        sous_branche = result_a2.get('branche', 'inconnue')
        # Écart plan → données, relevé par A2 : lu À LA SOURCE (A6 reçoit déjà
        # result_a2) et relayé aux 3 livrables, comme rapport_qualite. Un fichier
        # client incomplet ampute le modèle : ce qui n'est que dans les logs
        # n'existe pas.
        _cols_plan_manquantes = (result_a2 or {}).get('colonnes_plan_manquantes')

        # ── Application du profil de pondération — VARIABLE LOCALE ──────────
        # FIX (audit V4) : l'ancienne implémentation mutait une variable
        # globale de module (`global POIDS_CRITERES`), créant un risque de
        # race condition dès lors que plusieurs requêtes s'exécutent en
        # parallèle (ex. déploiement FastAPI concurrent) — deux appels avec
        # des profils différents pouvaient se marcher dessus et l'un des
        # deux calculerait son score avec les poids de l'autre. La
        # pondération est désormais strictement locale à cet appel et
        # transmise explicitement en paramètre aux méthodes qui en ont besoin.
        if poids_custom:
            poids_actifs = poids_custom
            logger.info(f"Profil personnalisé appliqué : {poids_custom}")
        elif profil in PROFILS_PONDERATION:
            poids_actifs = PROFILS_PONDERATION[profil]
            logger.info(f"Profil '{profil}' appliqué : {poids_actifs}")
        else:
            logger.warning(f"Profil '{profil}' inconnu — profil 'equilibre' utilisé")
            poids_actifs = PROFILS_PONDERATION['equilibre']

        logger.info(f"[{audit_id}] Agent A6 Comparaison démarré")

        df      = result_a2['dataframe'].copy()
        rapport = {'etapes': [], 'alertes': []}

        try:
            # ── ÉTAPE 1 : AGRÉGATION (filtrée sur la cible d'A6) ──────────────
            logger.info("Étape 1/5 : Agrégation des résultats")
            catalogue, exclusions_cible, exclusions_metrique = (
                self._agreger_resultats(
                    result_a3, result_a4, result_a5, col_cible=col_cible
                )
            )
            rapport['etapes'].append('agregation')
            rapport['nb_modeles'] = len(catalogue)
            rapport['exclusions_cible'] = exclusions_cible
            rapport['exclusions_metrique'] = exclusions_metrique
            if exclusions_metrique:
                logger.warning(
                    f"{len(exclusions_metrique)} modèle(s) écarté(s) — Gini non "
                    f"mesuré : "
                    + ", ".join(x['modele'] for x in exclusions_metrique))
            # ⚠️⚠️ UN ARBITRAGE ENTRE UN SEUL CANDIDAT N'EST PAS UN ARBITRAGE.
            # Mesuré : sur la cible par DÉFAUT (`prime_pure`), le seul modèle
            # d'A3 est le Tweedie — le Poisson vise la fréquence, le Gamma le
            # coût moyen, et le filtre par cible les écarte. A6 « sélectionnait »
            # donc parmi UN, et rien ne le disait. **Ce n'est ni un refus, ni un
            # silence : c'est une réserve, et elle se publie** — même geste que
            # le contrôle par l'effet qui déclare sa couverture partielle.
            reserve_arbitrage = None
            if len(catalogue) == 1:
                reserve_arbitrage = (
                    f"⚠ ARBITRAGE À UN SEUL CANDIDAT — un seul modèle est "
                    f"ajusté sur la cible '{col_cible}' : "
                    f"{catalogue[0]['modele']}. Il est donc « retenu » sans "
                    f"avoir été comparé à quoi que ce soit. "
                    f"{len(exclusions_cible)} modèle(s) écarté(s) pour cible "
                    f"non conforme, {len(exclusions_metrique)} pour Gini non "
                    f"mesuré. *Une sélection sans alternative n'est pas une "
                    f"sélection.*")
            # ⚠️ PAS de branche « catalogue vide » ici : `_agreger_resultats`
            # LÈVE déjà dans ce cas, donc elle serait inatteignable — et une
            # branche qui ne peut pas s'exécuter affirme un traitement que le
            # code ne rend jamais. Le refus est en amont, il y reste.
            rapport['reserve_arbitrage'] = reserve_arbitrage
            if reserve_arbitrage:
                logger.warning(reserve_arbitrage)
            logger.info(f"{len(catalogue)} modèles agrégés (cible='{col_cible}')")
            if exclusions_cible:
                # Surfacé, jamais silencieux : on trace chaque modèle écarté pour
                # cible non conforme (même exigence que exclusions_conformite).
                logger.warning(
                    f"{len(exclusions_cible)} modèle(s) écarté(s) de la comparaison "
                    f"— cible ≠ '{col_cible}' : "
                    + ", ".join(
                        f"{x['modele']}(cible={x['cible_modele']})"
                        for x in exclusions_cible
                    )
                )

            # ── ÉTAPE 2 : SCORE MULTICRITÈRES ─────────────────────────────────
            logger.info("Étape 2/5 : Score multicritères")
            catalogue = self._calculer_scores_multicriteres(catalogue, poids_actifs)
            rapport['etapes'].append('score_multicriteres')

            # ── ÉTAPE 3 : CLASSEMENT FINAL ────────────────────────────────────
            logger.info("Étape 3/5 : Classement final")
            classement = sorted(
                catalogue, key=lambda x: x['score_global'], reverse=True
            )
            modele_production = classement[0]
            rapport['etapes'].append('classement')

            # ── ÉTAPE 4 : BACKTESTING TEMPOREL ───────────────────────────────
            logger.info("Étape 4/5 : Backtesting temporel")
            backtest = self._backtesting_temporel(df, col_cible, col_expo, classement=classement, plan=plan)
            rapport['etapes'].append('backtesting')
            rapport['backtest'] = backtest

            # ── ÉTAPE 5 : COURBES DE VALIDATION ──────────────────────────────
            logger.info("Étape 5/5 : Courbes de validation")
            courbes = self._calculer_courbes(df, col_cible, classement[:3])
            rapport['etapes'].append('courbes')

            # ── GRAPHIQUES v3 ─────────────────────────────────────────────
            graphiques = {}
            if generer_graphiques and PLOTLY_OK:
                logger.info("Graphiques aide à la décision...")
                graphiques = self._generer_graphiques(
                    classement, modele_production, profil
                )
            # Graphiques V3 (charte partagée) — ajoutés au même dict, OPTIONNELS.
            if generer_graphiques and PLOTLY_OK and _CHARTS_V3_OK:
                self._charts_tarif_v3(graphiques, backtest, courbes,
                                      modele_production)

            # Rapport final
            # Amputation du plan : relevée à l'identique par A3/A4/A5 (chacun
            # vérifie SON plan contre SES données). On prend la première info
            # disponible — si les trois divergent, c'est que les agents n'ont pas
            # reçu le même plan, et chaque alerte est de toute façon remontée
            # individuellement dans _alertes_modele.
            _modele_ampute = next(
                (r.get('modele_ampute') for r in (result_a3, result_a4, result_a5)
                 if isinstance(r, dict) and r.get('modele_ampute')), None)

            # ⚠️⚠️ LA CIBLE EST MESURÉE, PAS SUPPOSÉE — constat `a6/C8`.
            # `plan.cible_frequence` est la seule autorité sur ce qu'est une
            # cible de fréquence ; comparer à un littéral la re-fabriquerait.
            _cible_freq_plan = getattr(plan, 'cible_frequence', None)
            _cible_est_freq = bool(
                _cible_freq_plan is not None and col_cible == _cible_freq_plan)
            _reserve_vrais = (
                reserve_vraisemblance_non_calibree(
                    col_cible, (modele_production or {}).get('gini_test'))
                if not _cible_est_freq else None)
            rapport['reserve_vraisemblance'] = _reserve_vrais
            # ⚠️⚠️ LE MÉLANGE DE BASES SE DÉCLARE — constat `a4/C10`. Il ne
            # bloque rien et ne change aucun nombre : il rend VISIBLE que deux
            # colonnes du même tableau ne sont pas sur le même pied.
            _reserve_bases = reserve_bases_gini_melangees(classement)
            rapport['reserve_bases_gini'] = _reserve_bases
            if _reserve_bases:
                logger.warning(_reserve_bases)

            # ⚠️⚠️ LE MEILLEUR DE CHAQUE BASE, ET LE CHOIX QUI SE DÉCLARE
            # CONTESTABLE — constat `a4/C10`, suite. Le tri global reste seul
            # à décider ; ce bloc n'y touche pas. Il AJOUTE une vue par base,
            # SANS seuil de proximité : on présente toujours le meilleur de
            # chaque base, comme `alternatives` présente toujours les trois
            # suivants. *L'actuaire juge la proximité, le code ne l'invente
            # pas.*
            _meilleurs = meilleur_par_base(classement, modele_production)
            rapport['meilleur_par_base'] = _meilleurs
            _contestable = reserve_arbitrage_contestable(
                _meilleurs, modele_production)
            rapport['arbitrage_contestable'] = _contestable
            if _contestable:
                logger.warning(_contestable)
            if _reserve_vrais:
                logger.warning(_reserve_vrais)

            statut_rag  = self._calculer_statut_rag(
                modele_production, classement,
                profil_valide_par=profil_valide_par,
                environnement=environnement,
                cible_est_frequence=_cible_est_freq,
                backtest=backtest,
                valide_par_actuaire_dl=valide_par_actuaire_dl,
                modele_ampute=_modele_ampute,
                hypotheses_glm=(result_a3 or {}).get('hypotheses'),
                hypotheses_ml=(result_a4 or {}).get('hypotheses'),
            )
            # ── AIDE À LA DÉCISION v3 ─────────────────────────────────────────
            # ⚠️⚠️ DÉPLACÉE ICI, APRÈS `statut_rag` — constat `a6/C5`. Elle
            # était construite AVANT que le statut soit calculé : elle ne
            # pouvait donc pas en tenir compte, et affirmait la conformité S2
            # même sur un modèle plafonné. Rien entre les deux points n'utilise
            # `fiche_decision` ; le déplacement est sans autre effet.
            fiche_decision = {}
            if aide_decision:
                fiche_decision = self._generer_fiche_decision(
                    classement, modele_production, profil,
                    backtest=backtest, statut_rag=statut_rag,
                )

            commentaire = self._commenter_actuaire_senior(
                classement, modele_production, sous_branche,
                statut_rag, backtest
            )

            self._sauvegarder_rapport(sous_branche, classement, modele_production, poids_actifs)
            self._sauvegarder_audit(audit_id, sous_branche, rapport,
                                     statut_rag, t_debut)

            # ── CALCUL VALIDATION SÉLECTION (avant Standard ActuarIA) ────────
            _val_sel_ = self._valider_selection(classement, modele_production, backtest)

            # ── Audit trail — construit AVANT _tmp_a6 pour être exposé dans ──
            # les exports Excel/Word/HTML (gouvernance, profil, score composite).
            # Réf. : ACPR-2022-P-01 §4.3 — les critères de sélection du modèle
            # doivent être documentés et justifiés dans l'audit trail.
            _nom_profil_retenu = next(
                (k for k, v in PROFILS_PONDERATION.items() if v == poids_actifs),
                'personnalise'
            )
            _audit_trail_a6 = {
                'agent': 'A6_COMPARAISON', 'version': '1.0', 'audit_id': audit_id,
                'timestamp': t_debut.isoformat(), 'branche': sous_branche,
                'statut_rag': statut_rag,
                'nb_modeles': len(classement),
                'modele_production': modele_production.get('modele','') if modele_production else '',
                'ae_ratio': backtest.get('ae_ratio', 0),
                'stabilite_wf': backtest.get('stabilite_wf',''),
                # R5 — Traçabilité du profil de pondération (ACPR-2022-P-01 §4.3)
                'profil_ponderation': _nom_profil_retenu,
                'profil_valide_par':  profil_valide_par,
                'environnement':      environnement,
                # Validation humaine d'un modèle Deep Learning en production
                # (garde-fou délibéré) : nom de l'actuaire validateur, ou None.
                # Tracé ici ET rendu dans les 3 rapports via synthese_modele_dl.
                'valide_par_actuaire_dl': valide_par_actuaire_dl,
                'gouvernance_ok':     gouvernance_validee(profil_valide_par,
                                                          environnement),
                # ⚠️ LA CAUSE, PAS SEULEMENT L'EFFET. Un rapport plafonné ne
                # disait PAS pourquoi : la raison n'existait que dans un
                # `logger.warning`, invisible au lecteur du document. Six mois
                # plus tard, personne ne savait pourquoi tel rapport était
                # AMBRE — et l'actuaire cherchait un défaut technique là où le
                # motif était administratif.
                'raisons_plafond': list(getattr(self, '_raisons_plafond', [])),
                'poids_criteres': {
                    'gini':            poids_actifs['gini'],
                    'stabilite':       poids_actifs['stabilite'],
                    'interpretabilite': poids_actifs['interpretabilite'],
                    'rmse':            poids_actifs['rmse'],
                },
                'note_score_global': (
                    "Score composite [0,1] = combinaison pondérée de 4 dimensions "
                    "normalisées (Gini, Stabilité, Interprétabilité, RMSE). "
                    "N'est PAS un R² ni un Gini absolu. "
                    "Profil retenu : " + _nom_profil_retenu + ". "
                    "Réf. : ACPR-2022-P-01 §4.3."
                ),
            }

            # ── Standard ActuarIA — excel_bytes ──────────────────────────────
            # ── EXCLUSIONS DE CONFORMITÉ (audit V11 / constat I5) ────────────
            # Agrégat des colonnes écartées par MatriceX chez A3/A4/A5, avec le
            # motif réglementaire de chacune. DOIT être calculé AVANT _tmp_a6 :
            # c'est ce dict-là qui alimente les TROIS exports (Excel, Word, HTML).
            # Une exclusion silencieuse est un défaut en soi — c'est ce silence
            # qui a rendu le BLOQUANT B5 si coûteux (le facteur central de la RC
            # Pro détruit, −17,4 % de Gini, sans que rien ne l'indique).
            _exclusions_conformite = {}
            _alertes_conformite = {}
            _alertes_modele = []
            # ⚠️ L'AGRÉGATION DU CONTRÔLE PAR L'EFFET EST UNE SOURCE UNIQUE
            # (`agreger_controle_effet`) : par le PIRE, et clés par
            # (AGENT, CIBLE). Elle vivait ici en ligne, et deux agents en
            # échec sur la MÊME cible s'écrasaient l'un l'autre — un motif
            # sur deux disparaissait.
            for _r_src in (result_a3, result_a4, result_a5):
                if isinstance(_r_src, dict):
                    _exclusions_conformite.update(
                        _r_src.get('exclusions_conformite') or {})
                    _alertes_conformite.update(
                        _r_src.get('alertes_conformite') or {})
                    _alertes_modele.extend(_r_src.get('alertes_modele') or [])
            _controle_effet = agreger_controle_effet({
                'A3': (result_a3 or {}).get('controle_effet'),
                'A4': (result_a4 or {}).get('controle_effet'),
                'A5': (result_a5 or {}).get('controle_effet'),
            })

            # ── ALERTE A6 : modèle Deep Learning retenu en production ─────────
            # Garde-fou DÉLIBÉRÉ (point 1), distinct du plafond wf-fidélité
            # incident. Logique isolée dans _alerte_dl_production() pour être
            # testable sans rejouer tout un run. L'alerte « requise » se tait une
            # fois valide_par_actuaire_dl renseigné (l'action est faite) ; la
            # validation reste tracée dans audit_trail ET rendue dans les 3
            # rapports (synthese_modele_dl).
            _alerte_dl = self._alerte_dl_production(
                modele_production, valide_par_actuaire_dl)
            if _alerte_dl:
                _alertes_modele.append(_alerte_dl)

            # _tmp_a6 inclut commentaire, courbes ET audit_trail — disponibles ici
            _tmp_a6 = {
                'success': True, 'statut_rag': statut_rag,
                'classement': classement, 'modele_production': modele_production,
                'backtest': backtest, 'branche': sous_branche,
                'validation_selection': _val_sel_,
                'fiche_decision': fiche_decision, 'audit_id': audit_id,
                'commentaire': commentaire,   # P7 : commentaire actuaire inclus
                'courbes': courbes,
                'graphiques': graphiques,     # figures V3 (ÉTAPE 2) → rapport HTML

                'audit_trail': _audit_trail_a6,  # Gouvernance exposée aux exports
                'exclusions_conformite': _exclusions_conformite,
                'controle_effet': _controle_effet,
                # ⚠️ La reserve d'arbitrage VOYAGE : une reserve que
                # personne ne lit serait `conformite/C7` recommence.
                'reserve_arbitrage': rapport.get('reserve_arbitrage'),
                'reserve_vraisemblance': rapport.get('reserve_vraisemblance'),
                'reserve_bases_gini': rapport.get('reserve_bases_gini'),
                'meilleur_par_base': rapport.get('meilleur_par_base'),
                'arbitrage_contestable': rapport.get('arbitrage_contestable'),
                'alertes_conformite': _alertes_conformite,
                'alertes_modele': _alertes_modele,
                'exclusions_cible': exclusions_cible,
                'valide_par_actuaire_dl': valide_par_actuaire_dl,
                'rapport_qualite': rapport_qualite,
                'rapport_mapping': rapport_mapping,
                'colonnes_plan_manquantes': _cols_plan_manquantes,
            }
            _excel_a6 = b''
            _word_a6  = b''
            _html_a6  = b''
            _pdf_a6   = b''
            if TARIF_EXCEL_OK:
                try:
                    _excel_a6 = export_excel_a6(_tmp_a6, audit_id)
                    if _excel_a6:
                        logger.info(f"[{audit_id}] Excel A6 : {len(_excel_a6):,} bytes")
                except Exception as e_xl:
                    logger.warning(f"Excel A6 échoué : {e_xl}")
            if TARIF_RAPPORT_OK:
                try:
                    # ⚠️ LA RELECTURE ACTUARIELLE TRANSITE ICI. A6 ne s'en sert
                    # pas — il la fait passer, comme il fait déjà passer
                    # `rapport_qualite` et `valide_par_actuaire_dl`. Elle
                    # n'entre PAS dans le statut RAG : les plafonds portent sur
                    # ce qui change la valeur du résultat, la relecture d'un
                    # document n'en est pas.
                    _rapports = generer_rapport_tarification(
                        result_a3=result_a3, result_a4=result_a4,
                        # ⚠️⚠️ SANS CETTE LIGNE, TOUT LE RESTE DU CÂBLAGE EST
                        # INERTE. Le catalogue peut nommer les figures d'A5 et
                        # le plan les attendre : si `result_a5` n'arrive pas
                        # jusqu'ici, `figures_disponibles` ne les trouve pas et
                        # le rapport en publie deux de moins, en silence.
                        # *Le correctif doit atteindre la surface, pas la
                        # frôler.*
                        result_a5=result_a5,
                        result_a6=_tmp_a6,
                        arrete=datetime.now().strftime('%d/%m/%Y'),
                        audit_id=audit_id, formats=['html','word'],
                        actuaire_nom=actuaire_nom or '',
                        actuaire_numero_ia=actuaire_numero_ia or '',
                    )
                    _html_a6 = _rapports.get('html_bytes', b'')
                    _word_a6 = _rapports.get('word_bytes', b'')
                    if _word_a6:
                        logger.info(f"[{audit_id}] Word A6 : {len(_word_a6):,} bytes")
                    if _html_a6:
                        logger.info(f"[{audit_id}] HTML A6 : {len(_html_a6):,} bytes")
                except Exception as e_rp:
                    logger.warning(f"Rapport A6 échoué : {e_rp}")

            # ── Rapport consolidé équipe (dashboard A1 → A6) ──────────────────
            # Réutilise le commentaire actuariel déjà généré par A6 ci-dessus
            # (_tmp_a6['commentaire']) — AUCUN nouvel appel Claude API.
            # Réf. : décision session — séparation rapport technique (narration
            # IA) / rapport équipe (dashboard factuel, sans narration dupliquée).
            _rapport_equipe = {
                'excel_bytes': b'', 'html_bytes': b'',
                'word_bytes':  b'', 'pdf_bytes':  b'',
            }
            if generer_rapport_equipe and RAPPORT_EQUIPE_OK:
                try:
                    _results_equipe = {
                        'a1': result_a1, 'a2': result_a2, 'a3': result_a3,
                        'a4': result_a4, 'a5': result_a5,
                        'a6': _tmp_a6,  # inclut commentaire, audit_trail, backtest
                    }
                    _rapport_equipe = generer_rapport_equipe_tarification(
                        _results_equipe,
                        branche=sous_branche,
                        arrete=datetime.now().strftime('%d/%m/%Y'),
                        audit_id=audit_id,
                        formats=formats_equipe or ['excel', 'html', 'word', 'pdf'],
                    )
                    logger.info(
                        f"[{audit_id}] Rapport équipe : "
                        f"Excel={len(_rapport_equipe.get('excel_bytes',b'')):,}b "
                        f"HTML={len(_rapport_equipe.get('html_bytes',b'')):,}b "
                        f"Word={len(_rapport_equipe.get('word_bytes',b'')):,}b "
                        f"PDF={len(_rapport_equipe.get('pdf_bytes',b'')):,}b"
                    )
                except Exception as e_eq:
                    logger.warning(f"Rapport équipe échoué : {e_eq}")

            # ── Archive vérifiable du livrable signé (voie B, modèle A7) ──────
            # ⚠️ APRÈS les rapports (les octets existent) ; le manifeste
            # {audit_id}.archive.json est SÉPARÉ du dossier {audit_id}/. On NE
            # réordonne PAS _sauvegarder_audit (voie B, arbitrée). L'échec
            # REMONTE dans le résultat (`archive_erreur`), il n'est pas avalé.
            _archive, _archive_erreur = ({}, None)
            if archiver and ARCHIVE_OK:
                _archive, _archive_erreur = archiver_livrable(
                    self.audit_path, audit_id, _rapport_equipe)
                if _archive_erreur:
                    logger.warning(f"[{audit_id}] Archivage échoué : {_archive_erreur}")



            if self.verbose:
                self._afficher_rapport_console(
                    audit_id, sous_branche, classement,
                    modele_production, statut_rag, commentaire
                )

            # _val_sel_ déjà calculé avant le bloc Standard ActuarIA
            _gv_sel_  = self._graphiques_validation_selection(
                _val_sel_, classement) if generer_graphiques else {}


            return {
                'success':            True,
                'dataframe':          df,
                'branche':            sous_branche,
                'statut_rag':         statut_rag,
                'classement':         classement,
                # ⚠️⚠️ SANS CETTE LIGNE, LA TABLE N'ATTEINT RIEN. Leçon du lot
                # 4.7 : le catalogue peut nommer, le rendu peut être écrit —
                # si la donnée ne monte pas dans le résultat, le rapport en
                # publie une de moins, EN SILENCE.
                'sensibilite_profils': self._sensibilite_profils(
                    classement, _nom_profil_retenu),
                'modele_production':  modele_production,
                'backtest':           backtest,
                'lift_ratio':         backtest.get('lift_ratio'),
                'lift_statut':        backtest.get('lift_statut'),
                # ── EXCLUSIONS DE CONFORMITÉ (audit V11 / constat I5) ─────────
                # Agrégat des colonnes écartées par MatriceX chez A3, A4 et A5,
                # avec le motif réglementaire de chaque exclusion. Remontées dans
                # les livrables : une exclusion silencieuse est un défaut en soi.
                # C'est ce silence qui a rendu le BLOQUANT B5 si coûteux —
                # 'antecedents_sinistres_3ans', LE facteur de la RC Pro, était
                # détruit (−17,4 % de Gini) sans qu'aucun rapport ne l'indique.
                'exclusions_conformite': _exclusions_conformite,
                'controle_effet': _controle_effet,
                # ⚠️ La reserve d'arbitrage VOYAGE : une reserve que
                # personne ne lit serait `conformite/C7` recommence.
                'reserve_arbitrage': rapport.get('reserve_arbitrage'),
                'reserve_vraisemblance': rapport.get('reserve_vraisemblance'),
                'reserve_bases_gini': rapport.get('reserve_bases_gini'),
                'meilleur_par_base': rapport.get('meilleur_par_base'),
                'arbitrage_contestable': rapport.get('arbitrage_contestable'),
                'alertes_conformite': _alertes_conformite,
                'alertes_modele':     _alertes_modele,
                # Modèles écartés de la comparaison pour cible non conforme
                # (fréquence vs coût vs prime pure). Surfacé comme les exclusions
                # de conformité : un écart silencieux est un défaut en soi.
                'exclusions_cible':   exclusions_cible,
                'valide_par_actuaire_dl': valide_par_actuaire_dl,
                'rapport_qualite':    rapport_qualite,
                # RapportMapping du renommage client (avant A1) — transité comme
                # rapport_qualite (produit par aucun agent). None = pas de mapping.
                'rapport_mapping':    rapport_mapping,
                # Colonnes DÉCLARÉES au plan que A2 n'a pas pu produire (fichier
                # client incomplet) → modèle amputé. Lu à la SOURCE dans
                # result_a2 : contrairement à rapport_qualite (produit par aucun
                # agent, donc transitant par un paramètre), A6 reçoit déjà A2.
                'colonnes_plan_manquantes': _cols_plan_manquantes,
                'courbes':            courbes,
                'graphiques':            graphiques,
                'validation_selection':  _val_sel_,
                'graphiques_validation': _gv_sel_,
                'fiche_decision':     fiche_decision,
                'rapport':            rapport,
                'commentaire':        commentaire,
                'audit_id':           audit_id,
                'erreur':             None,
                'excel_bytes':        _excel_a6,
                'html_bytes':         _html_a6,
                'word_bytes':         _word_a6,
                'pdf_bytes':          _pdf_a6,
                'hypotheses':         _val_sel_,
                'audit_trail':        _audit_trail_a6,
                # Rapport consolidé équipe A1→A6 (dashboard, sans narration IA dupliquée)
                'rapport_equipe':     _rapport_equipe,
                # Archive vérifiable du livrable signé (dossier + empreintes) ;
                # {} si archiver=False (défaut dormant). archive_erreur REMONTE.
                'archive':            _archive,
                'archive_erreur':     _archive_erreur,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 1 : AGRÉGATION
    # ══════════════════════════════════════════════════════════════════════════

    def _agreger_resultats(
        self,
        result_a3: Optional[Dict],
        result_a4: Optional[Dict],
        result_a5: Optional[Dict],
        col_cible: Optional[str] = None,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Agrège tous les résultats des agents A3, A4, A5 en un catalogue unifié.
        Chaque modèle devient une entrée avec ses métriques standardisées ET la
        CIBLE sur laquelle il a été ajusté — cible DÉCLARÉE par l'agent producteur
        (A3 : metriques[nom]['cible'] ; A4/A5 : result['col_cible']). A6 ne
        redéfinit AUCUNE cible : il lit ce que chaque agent déclare.

        Si ``col_cible`` est fourni, le catalogue est FILTRÉ : on ne garde que les
        modèles ajustés sur CETTE cible. Comparer un Gini de fréquence à un Gini de
        prime pure n'a aucun sens — c'était le bug de mélange de cibles (un
        GLM_POISSON de fréquence pouvait « gagner » un classement coût). Les
        modèles écartés ne sont JAMAIS supprimés en silence : ils sont renvoyés à
        part (exclusions_cible) et surfacés dans le résultat, même principe que
        exclusions_conformite.

        Retour : (catalogue_retenu, exclusions_cible).
        """
        catalogue = []

        # ── RÉSULTATS A3 (GLM) ────────────────────────────────────────────────
        if result_a3 and result_a3.get('success'):
            for nom in ['poisson', 'gamma', 'tweedie']:
                met = result_a3['metriques'].get(nom, {})
                if met:
                    # Récupérer les relativités tarifaires si disponibles (ajout A3)
                    relativites = met.get('relativites', {})
                    catalogue.append({
                        'modele':          f"GLM_{nom.upper()}",
                        'famille':         'GLM',
                        'cible':           met.get('cible'),   # déclarée par A3 (poisson=freq, gamma=cout_moyen, tweedie=prime_pure)
                        'gini_test':       met.get('gini', 0),
                        'base_gini':       met.get('base_gini'),
                        'gini_train':      met.get('gini', 0),
                        'relativites':     relativites,  # exp(β) par variable
                        'rmse_test':       met.get('rmse_test', 999),
                        'overfit_ratio':   1.0,
                        'nb_vars':         met.get('nb_vars_retenues', 0),
                        'agent_source':    'A3',
                        'interpretabilite': INTERPRETABILITE.get(nom, 0.5),
                    })

        # ── RÉSULTATS A4 (ML) ─────────────────────────────────────────────────
        if result_a4 and result_a4.get('success'):
            _cible_a4 = result_a4.get('col_cible')   # cible commune à tous les modèles A4
            for nom, met in result_a4.get('metriques', {}).items():
                catalogue.append({
                    'modele':          f"ML_{nom.upper()}",
                    'famille':         'ML',
                    'cible':           _cible_a4,
                    'gini_test':       met.get('gini_test', 0),
                    'base_gini':       met.get('base_gini'),
                    'gini_train':      met.get('gini_train', 0),
                    'rmse_test':       met.get('rmse_test', 999),
                    'overfit_ratio':   met.get('overfit_ratio', 1.0),
                    'nb_vars':         0,
                    'agent_source':    'A4',
                    'interpretabilite': INTERPRETABILITE.get(nom, 0.6),
                })

        # ── RÉSULTATS A5 (DL) ─────────────────────────────────────────────────
        if result_a5 and result_a5.get('success'):
            _cible_a5 = result_a5.get('col_cible')   # cible commune à tous les modèles A5
            for nom, met in result_a5.get('metriques', {}).items():
                catalogue.append({
                    'modele':          f"DL_{nom.upper()}",
                    'famille':         'Deep Learning',
                    'cible':           _cible_a5,
                    'gini_test':       met.get('gini_test', 0),
                    'base_gini':       met.get('base_gini'),
                    'gini_train':      met.get('gini_train', 0),
                    'rmse_test':       met.get('rmse_test', 999),
                    'overfit_ratio':   met.get('overfit_ratio', 1.0),
                    'nb_vars':         0,
                    'agent_source':    'A5',
                    'interpretabilite': INTERPRETABILITE.get(nom, 0.7),
                    'glm_gele':        met.get('glm_gele'),   # CANN : True/False ; TabNet : None
                })

        if not catalogue:
            raise ValueError(
                "Aucun résultat disponible. "
                "Vérifiez que A3, A4 ou A5 ont bien tourné."
            )

        # ── FILTRE PAR CIBLE : ne comparer QUE des modèles sur la MÊME cible ──
        # Sans filtre, un GLM_POISSON (fréquence) pouvait être classé dans une
        # comparaison de coût — son Gini de fréquence face à des Gini de prime
        # pure : mélange de cibles, comparaison invalide. On garde les modèles
        # dont la cible == col_cible ; les autres sont ÉCARTÉS et SURFACÉS
        # (jamais supprimés en silence). Si col_cible est None (appel legacy sans
        # cible), on ne filtre pas — rétro-compatible.
        exclusions_cible: List[Dict] = []
        if col_cible is not None:
            retenus = []
            for e in catalogue:
                c = e.get('cible')
                if c == col_cible:
                    retenus.append(e)
                else:
                    exclusions_cible.append({
                        'modele':         e['modele'],
                        'famille':        e['famille'],
                        'agent_source':   e['agent_source'],
                        'cible_modele':   c,          # cible réelle du modèle (None = indéterminée)
                        'cible_attendue': col_cible,
                        'raison': ('cible_indeterminee' if c is None
                                   else 'cible_differente'),
                    })
            catalogue = retenus

        # ⚠️⚠️ UN GINI NON MESURÉ NE SE NOTE PAS ZÉRO — il s'écarte, déclaré.
        # Depuis `a3/C6`, un agent qui n'a PAS pu calculer son Gini publie
        # `None`, jamais `0` : un zéro est indiscernable d'un pouvoir
        # discriminant nul, et le modèle entrait alors dans l'arbitrage avec
        # une note fabriquée. **Le filtre est ici, en UN point, et non recopié
        # sur les trois sites d'ajout** : A3, A4 et A5 sont traités pareil.
        # Il protège aussi `_calculer_scores_multicriteres`, qui divise par
        # `max(ginis)` et lèverait un TypeError sur un `None`.
        exclusions_metrique = [
            {'modele':         m['modele'],
             'famille':        m['famille'],
             'metrique':       'gini_test',
             'raison':         "Gini non mesuré (publié à None par l'agent "
                               "source) : un modèle non noté ne peut pas être "
                               "classé, et le noter zéro serait une note "
                               "fabriquée."}
            for m in catalogue if m.get('gini_test') is None
        ]
        if exclusions_metrique:
            catalogue = [m for m in catalogue if m.get('gini_test') is not None]

        if not catalogue:
            raise ValueError(
                f"Aucun modèle ajusté sur la cible '{col_cible}'. "
                f"{len(exclusions_cible)} modèle(s) écarté(s) pour cible non conforme. "
                f"{len(exclusions_metrique)} écarté(s) pour Gini non mesuré. "
                "Vérifiez qu'A3/A4/A5 ont été lancés sur la même cible qu'A6."
            )

        return catalogue, exclusions_cible, exclusions_metrique

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : SCORE MULTICRITÈRES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_scores_multicriteres(
        self,
        catalogue: List[Dict],
        poids:     Dict[str, float],
    ) -> List[Dict]:
        """
        Calcule le score global multicritères pour chaque modèle.

        FORMULE :
        ──────────
        Score = w_gini × S_gini
              + w_stabilite × S_stabilite
              + w_interpretabilite × S_interpretabilite
              + w_rmse × S_rmse

        Où chaque S_x est normalisé entre 0 et 1 par rapport
        au meilleur modèle dans cette dimension.

        JUSTIFICATION ACTUARIELLE :
        ────────────────────────────
        Un modèle avec Gini=0.25 mais overfit_ratio=1.5
        est moins bon en production qu'un modèle avec
        Gini=0.22 et overfit_ratio=1.02.
        La stabilité est le 2ème critère le plus important
        car un modèle instable produit des primes erratiques
        d'une année sur l'autre.
        """
        # Extraction des valeurs pour normalisation
        ginis    = [m['gini_test']     for m in catalogue]
        rmses    = [m['rmse_test']     for m in catalogue]
        overfits = [m['overfit_ratio'] for m in catalogue]

        max_gini = max(ginis) if max(ginis) > 0 else 1
        min_rmse = min(rmses) if min(rmses) > 0 else 1
        min_of   = min(overfits)
        max_of   = max(overfits)

        for modele in catalogue:
            # Score Gini normalisé [0,1]
            s_gini = modele['gini_test'] / max_gini

            # Score stabilité [0,1] — inversé (moins d'overfit = mieux)
            if max_of > min_of:
                s_stab = 1 - (modele['overfit_ratio'] - min_of) / (max_of - min_of)
            else:
                s_stab = 1.0
            # Pénalité si overfit_ratio > 1.15
            if modele['overfit_ratio'] > 1.15:
                s_stab *= 0.7
            if modele['overfit_ratio'] > 1.30:
                s_stab *= 0.5

            # Score interprétabilité (déjà normalisé)
            s_inter = modele['interpretabilite']

            # Score RMSE normalisé [0,1] — inversé (moins = mieux)
            s_rmse = min_rmse / max(modele['rmse_test'], 1e-6)
            s_rmse = min(s_rmse, 1.0)

            # Score global composite — ATTENTION : ce score n'est PAS un R² ni un Gini.
            # C'est une combinaison pondérée de 4 dimensions normalisées [0,1] :
            #   · Gini       (discrimination)      : poids = 40%
            #   · Stabilité  (walk-forward)        : poids = 30%
            #   · Interpré.  (SHAP / lisibilité)   : poids = 20%
            #   · RMSE       (précision absolue)   : poids = 10%
            # Les poids dépendent du profil sélectionné (voir PROFILS_PONDERATION).
            # Un score de 0.96 signifie 96% du score maximum possible dans ce profil,
            # pas une performance absolue de 96%.
            # Réf. : ACPR-2022-P-01 §4.3 — documentation des critères de sélection.
            score_global = (
                poids['gini']             * s_gini
                + poids['stabilite']      * s_stab
                + poids['interpretabilite'] * s_inter
                + poids['rmse']            * s_rmse
            )

            modele['score_gini']            = round(s_gini,  4)
            modele['score_stabilite']       = round(s_stab,  4)
            modele['score_interpretabilite']= round(s_inter, 4)
            modele['score_rmse']            = round(s_rmse,  4)
            modele['score_global']          = round(score_global, 4)

        return catalogue

    # ══════════════════════════════════════════════════════════════════════════
    # SENSIBILITÉ DU CLASSEMENT AU PROFIL DE PONDÉRATION
    # ══════════════════════════════════════════════════════════════════════════

    def _sensibilite_profils(self, classement: list[dict],
                             profil_actif: str) -> list[dict]:
        """Le modèle retenu sous CHACUN des profils de pondération.

        ⚠️⚠️ POURQUOI CETTE TABLE EXISTE — MESURÉ LE 29/08/2026. Le profil est
        choisi par un humain, et son nom est tracé (`profil_valide_par`). Mais
        `gouvernance_validee` ne vérifie qu'**un nom non vide** : elle
        enregistre QUI a assumé le choix, jamais CE QUE le choix a changé.
        Mesuré sur quatre portefeuilles, en recalculant avec la formule qui
        décide : **le vainqueur bascule dans 3 cas sur 4 sur la cible coût**,
        et les marges #1-#2 tombent à 0,008 · 0,016 · 0,021 selon le profil.
        *Le profil est un levier sur le prix ; rien ne le montrait.*

        ⚠️ CE N'EST PAS UNE FIGURE, ET C'EST DÉLIBÉRÉ. Quatre profils, quatre
        lignes : un graphique à quatre points serait un **tableau déguisé** —
        le motif même par lequel cet audit a écarté les quatre scorecards.

        ⚠️⚠️ ET ON RECALCULE AVEC `_calculer_scores_multicriteres`, LA FORMULE
        QUI DÉCIDE. C'est ce qui manquait à l'ancienne figure `scores_profils`
        (constat `a6/C3`, supprimée) : elle en inventait une autre — Gini brut
        au lieu de normalisé, `1/overfit`, `1 - rmse/400` — et publiait 0,56
        là où le score réel valait 0,9001.

        ⚠️⚠️ LA COPIE PROFONDE N'EST PAS UNE PRÉCAUTION, C'EST UNE NÉCESSITÉ :
        `_calculer_scores_multicriteres` écrit `score_global` **dans les
        dictionnaires reçus**. Sans copie, quatre appels écraseraient le
        classement publié avec les scores du dernier profil — *un prix
        déplacé.* Un test l'épingle.
        """
        import copy as _copy
        if not classement or len(classement) < 2:
            return []
        table = []
        for nom, poids in PROFILS_PONDERATION.items():
            note = self._calculer_scores_multicriteres(
                _copy.deepcopy(classement), poids)
            note = sorted(note, key=lambda m: m.get('score_global', 0),
                          reverse=True)
            table.append({
                'profil':  nom,
                'modele':  note[0].get('modele', ''),
                'score':   round(float(note[0].get('score_global', 0)), 4),
                # ⚠️ LA MARGE EST LA MOITIÉ DE L'INFORMATION. « Même vainqueur »
                # à 0,008 d'écart et à 0,381 ne se lisent pas pareil.
                'marge':   round(float(note[0].get('score_global', 0))
                                 - float(note[1].get('score_global', 0)), 4),
                'actif':   nom == profil_actif,
            })
        return table

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 4 : BACKTESTING TEMPOREL
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _gini_lorenz(y_true: np.ndarray, y_pred: np.ndarray,
                     expo: Optional[np.ndarray] = None) -> Optional[float]:
        """
        Gini walk-forward — formule canonique unique (audit V7 MINEUR #3).

        Extrait de la boucle _backtesting_temporel pour être appelée à la
        fois par le code de production ET par les tests (TestA6GiniWalk
        ForwardSentinelles) — élimine le risque qu'une correction de bug
        (ex. audit V6 : np.trapz supprimé sous numpy≥2.0, signe inversé)
        soit appliquée à la formule réelle sans être répercutée sur la
        copie testée par les sentinelles, ou inversement.

        Convention : tri décroissant par prédiction (les plus risqués
        d'abord), Gini = 2·AUC(Lorenz) − 1. Un modèle parfaitement
        discriminant donne un Gini proche de 1 (positif) ; un modèle
        anti-corrélé donne un Gini proche de -1 (négatif).

        Retourne None si le calcul n'est pas possible (pas de sinistre
        dans l'échantillon, ou prédiction constante).

        expo (correctif V15 #3) : si fournie, l'observation accumulée est le TAUX
        observé y_true/expo — homogène au taux prédit y_pred — au lieu du comptage
        brut (sinon un contrat à forte exposition biaise la courbe de Lorenz).
        None → comptage brut (rétro-compat). À ne fournir QUE pour une cible de
        COMPTAGE (fréquence) : pour une sévérité ou une prime pure (déjà un taux),
        y_true est déjà homogène à y_pred.
        """
        if y_true.sum() <= 0 or y_pred.std() <= 0:
            return None
        obs = (y_true if expo is None
               else y_true / np.maximum(np.asarray(expo, dtype=float), 1e-9))
        _trapz_fn = np.trapezoid if hasattr(np, 'trapezoid') else np.trapz
        ordre     = np.argsort(-y_pred)
        obs_sorted = obs[ordre]
        lorenz    = np.cumsum(obs_sorted) / max(obs.sum(), 1e-9)
        return round(
            float(2 * _trapz_fn(lorenz, np.linspace(0, 1, len(lorenz))) - 1),
            4
        )

    def _backtesting_temporel(
        self,
        df:         pd.DataFrame,
        col_cible:  str,
        col_expo:   str,
        classement: list = None,
        plan:       Optional[Any] = None,
    ) -> Dict:
        """
        Backtesting temporel Walk-Forward + Test A/E global et par segment.

        WALK-FORWARD :
        ─────────────
        Pour chaque fenêtre glissante d'années disponibles :
          - Train = toutes les années sauf la dernière
          - Test  = dernière année
        Mesure la stabilité du A/E dans le temps (pas seulement N-1 → N).

        TEST A/E PAR SEGMENT :
        ──────────────────────
        A/E = Observé / Attendu, calculé par :
          - Tranche de prime (déciles)
          - Zone géographique (si disponible)
          - Tranche d'âge (si disponible)
        Un A/E ∈ [0.90, 1.10] par segment = modèle non biaisé sur ce segment.
        """
        backtest = {
            'methode':    'Walk-Forward temporel + A/E par segment',
            'disponible': False,
        }

        if col_cible not in df.columns:
            backtest['note'] = f"Colonne cible '{col_cible}' introuvable."
            return backtest

        # ── Détection colonne année ────────────────────────────────────────────
        col_annee = None
        for candidate in ['annee_souscription', 'annee_survenance', 'annee']:
            if candidate in df.columns:
                col_annee = candidate
                break

        if col_annee is None:
            # Fallback aléatoire — documenté clairement
            backtest['note'] = (
                "Aucune colonne temporelle détectée. "
                "Backtesting remplacé par split aléatoire 80/20. "
                "Pour un backtesting temporel réel, ajouter une colonne "
                "'annee_souscription' ou 'annee_survenance'."
            )
            backtest['split'] = SPLIT_ALEATOIRE
            df_train, df_test = train_test_split(df, test_size=0.2, random_state=42)
            backtest['n_train'] = len(df_train)
            backtest['n_test']  = len(df_test)
            moy_train = float(df_train[col_cible].mean())
            moy_test  = float(df_test[col_cible].mean())
            # ⚠️ CE CHEMIN NE RECALIBRE AUCUN MODÈLE : sans colonne
            # temporelle, il n'y a qu'un découpage aléatoire, donc aucune
            # prédiction. Il publiait pourtant `moy_test / moy_train` sous le
            # nom `ae_ratio`, avec l'interprétation « 🟢 Non biaisé » — un
            # rapport de deux moyennes OBSERVÉES nommé Actual/Expected. Le
            # rapport de stationnarité reste publié SOUS SON PROPRE NOM ; l'A/E
            # vaut None, parce qu'il n'a pas été calculé.
            backtest['ae_ratio']            = None
            backtest['somme_observee']      = round(float(df_test[col_cible].sum()), 2)
            backtest['somme_attendue']      = None
            backtest['ratio_stationnarite'] = round(moy_test / max(moy_train, 1e-6), 4)
            backtest['moy_train']      = round(moy_train, 2)
            backtest['moy_test']       = round(moy_test, 2)
            backtest['disponible']     = True
            backtest['interpretation'] = (
                "⚠️ A/E NON calculé — aucune colonne temporelle, donc aucun "
                "modèle recalibré et aucune prédiction hors échantillon. Le "
                "ratio de stationnarité publié ne mesure PAS la calibration."
            )
            return backtest

        annees = sorted(df[col_annee].dropna().unique())
        if len(annees) < 2:
            backtest['note'] = "Pas assez d'années distinctes pour le walk-forward."
            return backtest

        # ── WALK-FORWARD AVEC RECALIBRATION DU MODÈLE ────────────────────────
        # Pour chaque fenêtre : recalibrer le meilleur modèle sur train,
        # prédire sur test, calculer Gini et A/E sur les prédictions.
        # C'est un vrai backtesting de modèle — pas un test de stationnarité.
        # ⚠️ LA CITATION QUI ÉTAIT ICI EST RETIRÉE. Elle donnait, ENTRE
        # GUILLEMETS, une phrase attribuée à « Commission Tarification IA
        # France (2019) §3.2.5 » — un texte que rien ne permet de retrouver.
        # Une phrase entre guillemets engage plus qu'une référence : elle
        # affirme que quelqu'un l'a écrite. La règle qu'elle habillait tient
        # sans elle, et elle est énoncée ci-dessus.
        walk_forward = []
        # année de test → prédictions du modèle recalibré, indexées sur les
        # lignes de la fenêtre (voir l'A/E par segment, plus bas).
        preds_par_annee: dict = {}

        # ── Recalibration sur le MODÈLE RÉELLEMENT RETENU (audit V4 reco #7) ──
        # AVANT : un GradientBoostingRegressor générique était TOUJOURS
        # instancié, quel que soit le modèle affiché dans 'modele_recalibre'
        # — le rapport pouvait donc afficher "elasticnet" alors qu'un GBM
        # avait réellement tourné en coulisses. Trompeur pour l'actuaire
        # lecteur, qui croit valider la stabilité du modèle sélectionné.
        #
        # APRÈS : on tente de recalibrer le VRAI type de modèle retenu via
        # creer_modele_ml_pour_nom (fabrique partagée avec A4 — mêmes
        # hyperparamètres). Si ce n'est pas possible (référence GLM non
        # couverte par cette fabrique sklearn, librairie manquante...),
        # on retombe sur un proxy GBM, mais le nom affiché le dit
        # explicitement — plus de nom trompeur.
        # ── Extraction du nom réel de modèle (audit V4 reco #7 — bug résiduel) ──
        # A6 préfixe systématiquement les noms dans son propre agrégat
        # (_agreger_resultats) : 'gbm' devient 'ML_GBM', 'poisson' devient
        # 'GLM_POISSON', etc. La fabrique creer_modele_ml_pour_nom attend le
        # nom BRUT d'A4 ('gbm', pas 'ML_GBM') — sans cette extraction, le
        # chemin de recalibration fidèle ne se déclenche JAMAIS en pratique
        # (toujours un repli silencieux sur le proxy, malgré le correctif),
        # ce qui a été détecté lors d'une relecture de contrôle post-fix.
        # ⚠ MISE À JOUR (audit V14) : les 'GLM_*' sont désormais RECALIBRABLES
        # FIDÈLEMENT (fabrique statsmodels — voir _GLMWalkForward dans A4). Ils ne
        # tombent plus en proxy, et un GLM peut donc enfin être certifié VERT.
        # Auparavant, le GLM — modèle de référence de la Non-Vie, interprétable et
        # attendu par l'ACPR — ne pouvait STRUCTURELLEMENT jamais l'être : la
        # fabrique levait ValueError, le proxy prenait le relais, et le gate
        # plafonnait à AMBRE. L'incitation était inversée : pour obtenir un VERT,
        # il fallait choisir une boîte noire.
        # Les 'DL_*' restent en proxy (réseaux de neurones : pas de fabrique).
        classement = classement or []
        _meilleur = (classement[0] if classement else {})
        _modele_nom_brut = _meilleur.get('modele', 'ML_GBM')
        if _modele_nom_brut.upper().startswith('ML_'):
            _modele_nom = _modele_nom_brut[3:].lower()  # 'ML_GBM' → 'gbm'
        else:
            _modele_nom = _modele_nom_brut  # GLM_*/DL_* — non couvert, proxy direct
        _modele_reel_recalibre = None  # nom effectivement utilisé, jamais menteur
        # FAMILLE (correctif V15 #4) : « construit par nom » EST le contrôle de
        # famille — un nom buildable donne la MÊME famille que la production
        # (GLM_POISSON→_GLMWalkForward(poisson), ML_GBM→GBM) ; un nom NON buildable
        # (DL_*, lib manquante) retombe en proxy GBM = famille DIFFÉRENTE. Ce flag
        # pilote build-vs-proxy ; la fidélité RAPPORTÉE le complète par le contrôle
        # de FEATURES (dans la boucle ci-dessous).
        _modele_construit_par_nom = False

        if CREER_MODELE_ML_OK:
            try:
                _test_modele = creer_modele_ml_pour_nom(_modele_nom, col_cible)
                _modele_reel_recalibre  = _modele_nom_brut
                _modele_construit_par_nom = True
            except (ImportError, ValueError) as e_fabrique:
                logger.warning(
                    f"[Walk-forward] Impossible de recalibrer '{_modele_nom_brut}' "
                    f"({e_fabrique}) — repli sur proxy GBM générique, "
                    f"étiqueté explicitement comme tel dans le rapport."
                )
                _modele_reel_recalibre = f"{_modele_nom_brut} → proxy GBM ({e_fabrique})"
        else:
            _modele_reel_recalibre = f"{_modele_nom_brut} → proxy GBM (fabrique A4 indisponible)"

        # Fidélité RAPPORTÉE (correctif V15 #4) = famille (construit par nom) ET
        # spec de FEATURES. Initialisée à la fidélité de famille ; DÉGRADÉE dans la
        # boucle si le WF recalibre sur des features hors production.
        _recalibration_est_fidele = _modele_construit_par_nom

        # ── LIFT / SEGMENTATION PAR DÉCILE (ajout D) ──────────────────────────
        # Piggyback WF : accumuler (prédiction, obs) hors-échantillon sur toutes
        # les fenêtres, puis (après la boucle) trier par prédiction et déciler.
        # Normalisation par exposition comme le Gini (V15 #3) : fréquence →
        # obs = comptage/exposition (taux) ; coût & prime pure → obs = y.
        _est_freq_cible = plan is not None and col_cible == plan.cible_frequence
        _lift_pred = []
        _lift_obs  = []

        for idx in range(1, len(annees)):
            annee_t = annees[idx]
            df_tr   = df[df[col_annee] < annee_t].copy()
            df_te   = df[df[col_annee] == annee_t].copy()
            if len(df_te) < 50 or len(df_tr) < 100:
                continue

            m_tr = float(df_tr[col_cible].mean()) if len(df_tr) > 0 else 0
            m_te = float(df_te[col_cible].mean())

            # ⚠️⚠️ A/E VEUT DIRE ACTUAL / EXPECTED, ET « EXPECTED » EST UNE
            # PRÉDICTION. Cette ligne valait `round(m_te / m_tr, 4)` : le
            # rapport de deux moyennes OBSERVÉES, c'est-à-dire un test de
            # STATIONNARITÉ du portefeuille. Le commentaire d'en-tête de ce
            # bloc l'annonçait pourtant en toutes lettres — « calculer Gini et
            # A/E SUR LES PRÉDICTIONS. C'est un vrai backtesting de modèle —
            # PAS un test de stationnarité » — et la prédiction naissait
            # 91 lignes plus bas sans jamais y entrer.
            # ⚠️ CE QUE ÇA PRODUISAIT, MESURÉ : sur une dernière année peuplée
            # exclusivement de conducteurs de moins de 25 ans portant 3× le
            # risque, mais dont la charge observée reste au niveau
            # d'apprentissage, l'instrument publiait « A/E = 1,0000 🟢 Non
            # biaisé ». Le modèle sur-tarifait massivement et la seule
            # grandeur qu'un contrôleur lit disait que tout allait bien.
            # ⚠️ Un A/E qui ne peut pas être calculé vaut None — il ne retombe
            # PAS sur la stationnarité, qui donnerait l'apparence d'une mesure.
            ae         = None
            somme_obs  = float(df_te[col_cible].sum())
            somme_att  = None
            pred_serie = None

            # ── Recalibration + Gini sur cette fenêtre ────────────────────────
            gini_wf = None
            try:
                # Une instance FRAÎCHE à chaque fenêtre — jamais réentraînée
                # sur l'état d'une fenêtre précédente.
                if _modele_construit_par_nom:
                    modele_wf = creer_modele_ml_pour_nom(_modele_nom, col_cible)
                else:
                    from sklearn.ensemble import GradientBoostingRegressor
                    modele_wf = GradientBoostingRegressor(
                        n_estimators=100, max_depth=3,
                        learning_rate=0.05, random_state=42,
                    )
                # Préparer features numériques (même logique que _preparer_donnees)
                _cols_num = [
                    c for c in df_tr.columns
                    if df_tr[c].dtype in ['int64', 'float64', 'int32', 'float32']
                    and c != col_cible
                    and df_tr[c].isnull().sum() == 0
                    and df_tr[c].std() > 0
                ]
                # ── FILTRES ANTI-FUITE / CONFORMITÉ (audit V8 BLOQUANT + V9 BLOQUANT) ──
                # V8 : sans filtrer_famille_cible, _cols_num retenait TOUTE colonne
                # numérique sauf la cible — data leakage (gini_wf ≈ 0,96 avec
                # cible=prime_pure, cout_total_sinistres en feature).
                # V9 : filtrer_genre manquait ici — une colonne sexe pré-encodée
                # traversait A2 intacte et entrait dans la recalibration walk-forward
                # (variable prohibée CJUE C-236/09, et incohérence de features avec
                # le modèle réellement entraîné par A4/A5 sans genre).
                # La cible reste lue via df_tr[col_cible], indépendamment de _cols_num.
                _cols_num = list(construire_matrice_x(
                    _cols_num, plan=plan,   # correctif V15 #2 : plan = autorité des features du WF
                    contexte='A6 — walk-forward', logger_agent=logger,
                    # ⚠ CRUCIAL : sans le contrôle par l'effet ici, le
                    # walk-forward est contaminé par la MÊME fuite que le modèle
                    # et la CONFIRME au lieu de la détecter (audit V12 : Gini_WF
                    # 0,92 · A/E 0,99 · 0 fenêtre rouge sur un modèle fuité).
                    df=df_tr, col_cible=col_cible,
                ))
                # correctif V15 #4 — FIDÉLITÉ DE SPÉCIFICATION (features) : le WF
                # recalibre-t-il sur les MÊMES features que la production ?
                # Production = plan.colonnes_produites(). Features EN TROP (hors
                # plan) = spec différente → recalibration NON fidèle (rapportée),
                # même si construite par nom. On ne dégrade que sur preuve POSITIVE :
                # sans plan (non vérifiable) ou sur un SOUS-ensemble (facteur constant
                # sur la fenêtre, écarté légitimement) → PAS de dégradation.
                if plan is not None and _recalibration_est_fidele:
                    _en_trop = set(_cols_num) - set(plan.colonnes_produites())
                    if _en_trop:
                        _recalibration_est_fidele = False
                        logger.warning(
                            f"[FIDÉLITÉ WF] Recalibration NON fidèle : features hors "
                            f"production {sorted(_en_trop)} — spec différente de "
                            f"plan.colonnes_produites(). Statut plafonné à AMBRE.")
                if _cols_num and col_cible in df_tr.columns:
                    X_tr = df_tr[_cols_num].fillna(0).values
                    y_tr = df_tr[col_cible].values
                    X_te = df_te[_cols_num].fillna(0).values
                    y_te = df_te[col_cible].values
                    w_tr = (
                        df_tr[col_expo].values
                        if col_expo in df_tr.columns
                        else None
                    )
                    w_te = (
                        df_te[col_expo].values
                        if col_expo in df_te.columns
                        else None
                    )
                    # Recalibrer sur la fenêtre train
                    #
                    # Bug découvert lors des tests V7 (session de suivi de
                    # l'audit) : un Pipeline sklearn (ex. ElasticNet, qui
                    # est enveloppé dans Pipeline([StandardScaler, ElasticNet])
                    # par la fabrique creer_modele_ml_pour_nom) lève ValueError
                    # — PAS TypeError — quand sample_weight est passé
                    # directement à Pipeline.fit() sans le préfixe
                    # 'stepname__'. L'except TypeError seul laissait donc
                    # cette ValueError remonter jusqu'au handler englobant,
                    # qui annulait TOUTE la fenêtre (Gini inclus) au lieu de
                    # simplement refaire un fit sans pondération.
                    if w_tr is not None:
                        try:
                            modele_wf.fit(X_tr, y_tr, sample_weight=w_tr)
                        except (TypeError, ValueError):
                            modele_wf.fit(X_tr, y_tr)
                    else:
                        modele_wf.fit(X_tr, y_tr)
                    # Prédire sur la fenêtre test
                    pred_te = np.maximum(modele_wf.predict(X_te), 0)
                    # ⚠️ INDEXÉE SUR `df_te` : l'A/E par segment, plus bas,
                    # découpe le MÊME dataframe. Sans index partagé, un
                    # alignement par position casserait au premier filtre.
                    pred_serie = pd.Series(pred_te, index=df_te.index)
                    # Gini walk-forward — audit V6 #2, puis audit V7 MINEUR #3.
                    # V6 avait corrigé deux bugs (np.trapz supprimé sous
                    # numpy≥2.0, signe inversé) directement dans cette formule
                    # inline. L'audit V7 a relevé que le test-sentinelle qui
                    # protège ces deux bugs testait une COPIE de la formule,
                    # pas ce chemin de code réel — risque de divergence future
                    # si l'un des deux était modifié sans l'autre. Corrigé en
                    # extrayant le calcul dans _gini_lorenz(), désormais
                    # appelée ICI ET par le test — une seule formule, jamais
                    # deux versions qui peuvent diverger.
                    # correctif V15 #3 : normaliser par l'exposition UNIQUEMENT
                    # pour la fréquence (y=comptage, pred=taux). Coût (sévérité) et
                    # prime pure (déjà un taux) : y déjà homogène à pred → pas d'expo.
                    _est_freq = plan is not None and col_cible == plan.cible_frequence
                    gini_wf = self._gini_lorenz(
                        y_te, pred_te, expo=w_te if _est_freq else None)
                    # Accumulation lift (ajout D) — mêmes unités que le Gini.
                    _obs_lift = np.asarray(y_te, dtype=float)
                    if _est_freq_cible and w_te is not None:
                        _obs_lift = _obs_lift / np.maximum(
                            np.asarray(w_te, dtype=float), 1e-9)
                    _lift_pred.append(np.asarray(pred_te, dtype=float))
                    _lift_obs.append(_obs_lift)
            except Exception as e_wf:
                # Passé de logger.debug à logger.warning (audit V6) : une
                # exception dans la recalibration WF est une erreur de code
                # potentielle (comme le bug np.trapz ci-dessus l'a montré),
                # pas un cas limite anodin de données — elle ne doit plus
                # pouvoir disparaître silencieusement en niveau debug.
                logger.warning(f"Recalibration WF {annee_t} échouée : {e_wf}")

            # ── A/E = charge OBSERVÉE / charge ATTENDUE par le modèle ────────
            # ⚠️ L'UNITÉ EST MESURÉE, PAS SUPPOSÉE. Pour une cible de
            # FRÉQUENCE, `predict` rend un TAUX ANNUEL et non un comptage :
            # `_GLMWalkForward` ajuste avec `offset=log(expo)` et prédit SANS
            # offset. Mesuré sur données de vérité connue :
            # Σy / Σ(pred × expo) = 1,0000 alors que Σy / Σpred = 0,5533.
            # L'attendu est donc `pred × exposition` — exactement la
            # construction que le chemin déclaratif emploie déjà
            # (`pipeline_tarifaire.py:229` : attendu = frequence_annuelle ×
            # exposition). Pour une cible de coût ou de prime pure, `y` et
            # `pred` sont déjà homogènes : pas d'exposition.
            if pred_serie is not None:
                _att = pred_serie.to_numpy(dtype=float)
                if _est_freq_cible and col_expo in df_te.columns:
                    _att = _att * df_te[col_expo].to_numpy(dtype=float)
                somme_att = float(_att.sum())
                if somme_att > 1e-9:
                    ae = round(somme_obs / somme_att, 4)

            walk_forward.append({
                'annee_test':         int(annee_t),
                'n_train':            len(df_tr),
                'n_test':             len(df_te),
                'moy_train':          round(m_tr, 2),
                'moy_test':           round(m_te, 2),
                'somme_observee':     round(somme_obs, 2),
                'somme_attendue':     (round(somme_att, 2)
                                       if somme_att is not None else None),
                'n_sinistres_test':   int((df_te[col_cible] > 0).sum()),
                'ae_ratio':           ae,
                'gini_recalibre':     gini_wf,
                'modele_recalibre':   _modele_reel_recalibre,
                'modele_recalibre_fidele': _recalibration_est_fidele,
                'statut':             (
                    'AMBRE' if ae is None else
                    'VERT'  if AE_FENETRE_STRICTE[0] <= ae
                               <= AE_FENETRE_STRICTE[1] else
                    'AMBRE' if AE_FENETRE_ACCEPTABLE[0] <= ae
                               <= AE_FENETRE_ACCEPTABLE[1] else
                    'ROUGE'
                ),
            })
            # ⚠️ La prédiction de la fenêtre est CONSERVÉE : l'A/E par segment,
            # plus bas, la redemande pour la dernière fenêtre. Elle était
            # jusqu'ici jetée à chaque tour de boucle — c'est pourquoi les
            # segments se rabattaient sur une moyenne observée.
            if pred_serie is not None:
                preds_par_annee[int(annee_t)] = pred_serie

        if not walk_forward:
            backtest['note'] = "Aucune fenêtre walk-forward valide."
            return backtest

        # A/E de la dernière fenêtre (N-1 → N)
        derniere = walk_forward[-1]
        ae_ratio = derniere['ae_ratio']

        # Stabilité walk-forward : CV des A/E sur toutes les fenêtres
        # ⚠️ UNE FENÊTRE SANS A/E MESURÉ N'ENTRE PAS DANS LA STABILITÉ. Elle ne
        # vaut pas 1 : elle ne vaut rien, et la moyenner à 1 dirait « stable ».
        aes       = [w['ae_ratio'] for w in walk_forward if w['ae_ratio'] is not None]
        ae_moyen  = float(np.mean(aes)) if aes else None
        ae_cv     = (float(np.std(aes) / max(ae_moyen, 1e-6))
                     if aes and ae_moyen else None)
        n_rouge   = sum(1 for w in walk_forward if w['statut'] == 'ROUGE')

        # ── TEST A/E PAR SEGMENT ──────────────────────────────────────────────
        # Utiliser la dernière fenêtre (la plus réaliste)
        annee_test = derniere['annee_test']
        df_test_n  = df[df[col_annee] == annee_test].copy()
        pred_n     = preds_par_annee.get(int(annee_test))

        # ⚠️⚠️ LE DÉNOMINATEUR ÉTAIT `moy_ref`, LA MOYENNE OBSERVÉE DU TRAIN —
        # LA MÊME POUR LES TROIS SEGMENTATIONS. Un segment réellement plus
        # risqué sortait donc ROUGE même parfaitement tarifé : la grandeur
        # mesurait l'HÉTÉROGÉNÉITÉ du portefeuille, jamais la CALIBRATION du
        # modèle. Mesuré sur la fixture du dépôt : 8 segments ROUGE sur 11.
        # Chaque segment se compare désormais à ce que LE MODÈLE prédit POUR
        # LUI — c'est la définition d'un contrôle de calibration.
        if pred_n is not None:
            _att_n = pred_n.reindex(df_test_n.index).to_numpy(dtype=float)
            if _est_freq_cible and col_expo in df_test_n.columns:
                _att_n = _att_n * df_test_n[col_expo].to_numpy(dtype=float)
            df_test_n['_attendu'] = _att_n

        ae_par_segment = {}
        _N_MINI_SEG = 20

        # ⚠️⚠️ UN A/E DE SEGMENT EXIGE ASSEZ DE SINISTRES POUR VOULOIR DIRE
        # QUELQUE CHOSE, ET L'EFFECTIF NE SUFFIT PAS À LE DIRE. Mesuré en
        # écrivant ce correctif, sur la fixture du dépôt (cible à 95,8 % de
        # zéros, CV 5,4) : le quintile de risque le plus bas sortait
        # « A/E = 287,92 » — 77 contrats, quelques euros attendus, un sinistre
        # survenu — et trois segments sortaient « A/E = 0,00 ». Aucun n'est un
        # défaut de tarification : c'est un rapport dont le DÉNOMINATEUR n'a
        # pas de signal.
        # ⚠️ LE PLANCHER PORTE SUR LE NOMBRE DE SINISTRES, PAS SUR L'EFFECTIF :
        # trente contrats sans sinistre ne disent rien d'un tarif. C'est un
        # seuil de PUBLICATION, pas une norme de crédibilité — en dessous, le
        # chiffre est montré avec sa mention « non crédible » et ne peut plus
        # rendre ni VERT ni ROUGE. On publie ce qu'on ne peut pas juger ; on
        # ne le juge pas.
        _N_MINI_SINISTRES = 10

        def _ligne_ae(sub, cle_nom, cle_val):
            """A/E d'un sous-ensemble : charge OBSERVÉE / charge ATTENDUE."""
            obs   = float(sub[col_cible].sum())
            att   = float(sub['_attendu'].sum()) if '_attendu' in sub.columns else None
            n_sin = int((sub[col_cible] > 0).sum())
            r     = round(obs / att, 4) if att and att > 1e-9 else None
            credible = r is not None and n_sin >= _N_MINI_SINISTRES
            return {
                cle_nom:      cle_val,
                'n':          len(sub),
                'n_sinistres': n_sin,
                'moy_obs':    round(float(sub[col_cible].mean()), 2),
                'moy_pred':   (round(float(sub['_attendu'].mean()), 2)
                               if '_attendu' in sub.columns else None),
                'ae_ratio':   r,
                'credible':   credible,
                'statut':     ('AMBRE' if not credible else
                               'VERT'  if 0.90 <= r <= 1.10 else
                               'AMBRE' if 0.80 <= r <= 1.20 else 'ROUGE'),
                'note':       (None if credible else
                               f"A/E non crédible : {n_sin} sinistre(s) dans ce "
                               f"segment, seuil de publication {_N_MINI_SINISTRES}"),
            }

        # Segment 1 : quintiles de RISQUE PRÉDIT
        # ⚠️ ILS ÉTAIENT DÉCOUPÉS SUR LA CIBLE OBSERVÉE, et c'est un piège
        # statistique classique : trier par l'observé puis comparer l'observé
        # à une référence garantit que le quintile haut sort au-dessus et le
        # quintile bas en dessous — même pour un modèle PARFAIT (régression
        # vers la moyenne). Le découpage se fait sur le risque PRÉDIT : c'est
        # le diagramme de fiabilité standard, et lui seul montre si le modèle
        # se trompe DE NIVEAU sur une bande de risque donnée.
        try:
            if '_attendu' not in df_test_n.columns:
                raise ValueError("aucune prédiction : quintiles non calculables")
            df_test_n['_quintile'] = pd.qcut(
                df_test_n['_attendu'], q=5, labels=False, duplicates='drop'
            )
            ae_quintiles = []
            for d in sorted(df_test_n['_quintile'].dropna().unique()):
                sub = df_test_n[df_test_n['_quintile'] == d]
                ae_quintiles.append(_ligne_ae(sub, 'quintile', int(d) + 1))
            if ae_quintiles:
                ae_par_segment['quintiles_risque'] = ae_quintiles
        except Exception as e_q:
            logger.debug(f"A/E quintiles échoué : {e_q}")

        # Segment 2 : zone géographique (si disponible)
        for col_zone in ['zone_geographique', 'zone', 'region', 'area']:
            if col_zone in df_test_n.columns:
                try:
                    ae_zones = []
                    for zone in df_test_n[col_zone].dropna().unique()[:8]:
                        sub = df_test_n[df_test_n[col_zone] == zone]
                        if len(sub) < _N_MINI_SEG:
                            continue
                        ae_zones.append(_ligne_ae(sub, 'zone', str(zone)))
                    if ae_zones:
                        ae_par_segment['zones'] = ae_zones
                except Exception as e_z:
                    logger.debug(f"A/E zones échoué : {e_z}")
                break

        # Segment 3 : tranche d'âge (si disponible)
        for col_age in ['age', 'age_conducteur', 'drimage']:
            if col_age in df_test_n.columns:
                try:
                    bins  = [0, 25, 35, 45, 55, 65, 200]
                    lbls  = ['<25', '25-34', '35-44', '45-54', '55-64', '65+']
                    df_test_n['_age_tranche'] = pd.cut(
                        df_test_n[col_age], bins=bins, labels=lbls, right=False
                    )
                    ae_ages = []
                    for tranche in lbls:
                        sub = df_test_n[df_test_n['_age_tranche'] == tranche]
                        if len(sub) < _N_MINI_SEG:
                            continue
                        ae_ages.append(_ligne_ae(sub, 'tranche', tranche))
                    if ae_ages:
                        ae_par_segment['tranches_age'] = ae_ages
                except Exception as e_a:
                    logger.debug(f"A/E âge échoué : {e_a}")
                break

        # ── BILAN ─────────────────────────────────────────────────────────────
        # Gini moyen walk-forward (sur les fenêtres avec recalibration)
        _ginis_wf = [w['gini_recalibre'] for w in walk_forward
                     if w.get('gini_recalibre') is not None]
        gini_wf_moyen = round(float(np.mean(_ginis_wf)), 4) if _ginis_wf else None

        # ── LIFT RATIO (ajout D) — décile haut-risque / décile bas-risque ─────
        # Poolé sur toutes les fenêtres AVANT décilage (≫ points/décile → bien
        # plus stable qu'un lift par fenêtre : mesuré par-fenêtre 1.94–3.24,
        # poolé 2.55 sur le même portefeuille auto sain). Aléatoire → ~1 ;
        # modèle sain de fréquence → ~2.5. Complément « à l'endroit » du Gini.
        lift_ratio  = None
        lift_statut = None
        lift_deciles_wf = None   # phase graphiques : 10 déciles obs. pour chart_lift_decile
        if _lift_pred:
            _p_all = np.concatenate(_lift_pred)
            _o_all = np.concatenate(_lift_obs)
            _fini  = np.isfinite(_p_all) & np.isfinite(_o_all)
            _p_all, _o_all = _p_all[_fini], _o_all[_fini]
            # 10 déciles exigent assez de points ET une prédiction non dégénérée.
            if len(_p_all) >= 100 and float(np.std(_p_all)) > 1e-12:
                _o_tri   = _o_all[np.argsort(_p_all)]
                _deciles = [d for d in np.array_split(_o_tri, 10) if len(d) > 0]
                if len(_deciles) >= 2:
                    _d_bas  = float(np.mean(_deciles[0]))   # prédiction la + basse
                    _d_haut = float(np.mean(_deciles[-1]))  # prédiction la + haute
                    lift_ratio  = round(_d_haut / max(_d_bas, 1e-6), 4)
                    lift_statut = ('VERT'  if lift_ratio >= 3.0 else
                                   'AMBRE' if lift_ratio >= 2.0 else
                                   'ROUGE')
                    # phase graphiques : moyenne observée par décile (bas→haut
                    # risque prédit) — alimente chart_lift_decile (vrai lift WF).
                    lift_deciles_wf = [round(float(np.mean(d)), 6) for d in _deciles]

        backtest.update({
            'disponible':        True,
            'split':             SPLIT_WALK_FORWARD,
            'col_annee':         col_annee,
            'annees_disponibles':[int(a) for a in annees],
            'annee_test':        int(annee_test),
            'annees_train':      [int(a) for a in annees if a < annee_test],
            'n_train':           derniere['n_train'],
            'n_test':            derniere['n_test'],
            'moy_train':         derniere['moy_train'],
            'moy_test':          derniere['moy_test'],
            'ae_ratio':          ae_ratio,
            # ⚠️ LES DEUX TERMES DU RAPPORT SONT PUBLIÉS. Un A/E qui ne donne
            # pas sa charge observée et sa charge attendue n'est pas
            # vérifiable : un commissaire doit pouvoir refaire la division.
            'somme_observee':    derniere.get('somme_observee'),
            'somme_attendue':    derniere.get('somme_attendue'),
            # ⚠️ LE NOMBRE DE SINISTRES DE LA FENÊTRE EST PUBLIÉ AVEC L'A/E.
            # Un A/E porté par trois sinistres et un porté par mille se lisent
            # pareil et ne valent pas pareil ; sans ce compte, rien à l'écran
            # ne distingue les deux.
            'n_sinistres_test':  derniere.get('n_sinistres_test'),
            # ⚠️ LA BASE DU CALCUL EST PUBLIÉE AVEC LE RÉSULTAT. Un A/E ne se
            # lit pas sans savoir ce qui a été divisé — et sur une cible de
            # fréquence l'attendu vaut `prédiction × exposition` parce que le
            # modèle rend un TAUX ANNUEL.
            # ⚠️⚠️ LIMITE MESURÉE, ET ELLE EST DU CÔTÉ SÛR. La convention
            # « prédiction = taux » est EXACTE pour un GLM recalibré
            # (Σy / Σ(pred×expo) = 1,0000 sur données de vérité connue) mais
            # FAUSSE pour un modèle ML réajusté sur le comptage brut avec
            # `sample_weight=exposition` : il rend une troisième grandeur, ni
            # taux ni comptage. L'attendu est alors SOUS-estimé, donc l'A/E
            # sort TROP HAUT, donc ROUGE — une fausse alerte, jamais une
            # fausse mise hors de cause. Le correctif (ajuster le ML sur le
            # taux) a été mesuré et ne referme pas l'écart : 1,72 → 1,10, pas
            # 1,00. Il demande son propre chantier.
            'base_attendu':      ('prédiction × exposition' if _est_freq_cible
                                  else 'prédiction'),
            'ae_moyen_wf':       round(ae_moyen, 4) if ae_moyen is not None else None,
            'ae_cv_wf':          round(ae_cv, 4) if ae_cv is not None else None,
            'n_fenetres':        len(walk_forward),
            'n_fenetres_rouge':  n_rouge,
            'gini_wf_moyen':     gini_wf_moyen,
            'lift_ratio':          lift_ratio,
            'lift_statut':         lift_statut,
            'lift_deciles_wf':     lift_deciles_wf,
            'lift_cible_frequence': _est_freq_cible,
            'modele_recalibre':  _modele_reel_recalibre,
            'modele_recalibre_fidele': _recalibration_est_fidele,
            'walk_forward':      walk_forward,
            'ae_par_segment':    ae_par_segment,
            'interpretation': (
                '⚠️ A/E NON calculé — aucune prédiction hors échantillon '
                'disponible sur la dernière fenêtre' if ae_ratio is None else
                '🟢 Non biaisé'       if AE_FENETRE_STRICTE[0] <= ae_ratio
                                      <= AE_FENETRE_STRICTE[1] else
                '🟡 Légère déviation' if AE_FENETRE_ACCEPTABLE[0] <= ae_ratio
                                      <= AE_FENETRE_ACCEPTABLE[1] else
                '🔴 Déviation majeure'
            ),
            'stabilite_wf': (
                '⚠️ Stabilité NON mesurée — aucune fenêtre avec A/E'
                if ae_cv is None else
                '🟢 Stable'     if ae_cv <= 0.05 and n_rouge == 0 else
                '🟡 Acceptable' if ae_cv <= SEUIL_CV_INSTABLE else
                '🔴 Instable'
            ),
        })

        logger.info(
            f"Walk-forward : {len(walk_forward)} fenêtres | "
            f"A/E N-1→N = {'non calculé' if ae_ratio is None else f'{ae_ratio:.4f}'} "
            f"({derniere.get('somme_observee')} observé / "
            f"{derniere.get('somme_attendue')} attendu) | "
            f"CV = {'n/a' if ae_cv is None else f'{ae_cv:.4f}'} | "
            f"Fenêtres ROUGE = {n_rouge}"
        )

        return backtest

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 5 : COURBES DE VALIDATION
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_courbes(
        self,
        df:         pd.DataFrame,
        col_cible:  str,
        top_modeles: List[Dict]
    ) -> Dict:
        """
        Calcule les courbes de Lorenz et de lift pour les 3 meilleurs modèles.

        COURBE DE LORENZ :
        ───────────────────
        Représente la concentration des sinistres/primes.
        Axe X : % cumulé de contrats (du moins risqué au plus risqué)
        Axe Y : % cumulé des primes/sinistres
        Plus la courbe est convexe, plus le modèle discrimine bien.

        LIFT CURVE :
        ─────────────
        Pour chaque décile de risque prédit, compare la prime moyenne
        observée vs la prime moyenne du portefeuille.
        Un bon modèle a un lift élevé sur le 1er décile (vrais risques élevés).
        """
        courbes = {}

        if col_cible not in df.columns:
            return {'disponible': False}

        y = df[col_cible].values

        # Courbe de Lorenz sur les valeurs observées
        order   = np.argsort(y)[::-1]
        y_sort  = y[order]
        n       = len(y_sort)
        lorenz_x = np.linspace(0, 1, n)
        lorenz_y = np.cumsum(y_sort) / np.sum(y_sort)

        # Courbe diagonale (modèle nul)
        diagonal = np.linspace(0, 1, n)

        # Gini observé (concentration naturelle du portefeuille)
        fn = np.trapezoid if hasattr(np, 'trapezoid') else np.trapz
        auc_obs  = fn(lorenz_y, lorenz_x)
        gini_obs = round(float(2 * auc_obs - 1), 4)

        # Lift par décile (sur valeurs observées)
        n_deciles = 10
        deciles   = np.array_split(y_sort, n_deciles)
        lift_data = []
        moy_glob  = float(np.mean(y))
        for i, dec in enumerate(deciles):
            lift_data.append({
                'decile':       i + 1,
                'prime_moy':    round(float(np.mean(dec)), 2),
                'lift':         round(float(np.mean(dec)) / max(moy_glob, 1e-6), 3),
            })

        courbes = {
            'disponible':   True,
            'gini_observe': gini_obs,
            'lorenz': {
                'x': lorenz_x[::max(1, n//100)].tolist(),  # Sous-échantillonnage pour JSON
                'y': lorenz_y[::max(1, n//100)].tolist(),
            },
            'lift_deciles': lift_data,
            'prime_moy_globale': round(moy_glob, 2),
        }

        logger.info(f"Courbes calculées | Gini observé = {gini_obs:.4f}")
        return courbes

    # ══════════════════════════════════════════════════════════════════════════
    # SAUVEGARDE
    # ══════════════════════════════════════════════════════════════════════════

    def _sauvegarder_rapport(
        self,
        sous_branche:     str,
        classement:       List[Dict],
        modele_production: Dict,
        poids_actifs:     Dict[str, float] = None,
    ) -> None:
        """Sauvegarde le rapport de comparaison en JSON."""
        rapport_json = {
            'sous_branche':       sous_branche,
            'timestamp':          datetime.now().isoformat(),
            'version':            '1.0',
            'modele_production':  modele_production['modele'],
            'score_production':   modele_production['score_global'],
            'classement_complet': [
                {k: v for k, v in m.items()
                 if not isinstance(v, (np.ndarray, pd.DataFrame))}
                for m in classement
            ],
            'poids_criteres':     poids_actifs or {},
        }
        chemin = self.models_path / f"a6_comparaison_{sous_branche}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(rapport_json, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Rapport A6 sauvegardé : {chemin}")
        except Exception as e:
            logger.warning(f"Sauvegarde échouée : {e}")

    def _sauvegarder_audit(
        self, audit_id, sous_branche, rapport, statut_rag, t_debut
    ) -> None:
        log = {
            'audit_id':     audit_id,
            'agent':        'A6_COMPARAISON',
            'timestamp':    t_debut.isoformat(),
            'sous_branche': sous_branche,
            'statut_rag':   statut_rag,
            'etapes':       rapport['etapes'],
            'nb_modeles':   rapport.get('nb_modeles', 0),
        }
        try:
            with open(self.audit_path / f"{audit_id}.json", 'w') as f:
                json.dump(log, f, indent=2, default=str)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # STATUT RAG & COMMENTAIRES
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _alerte_dl_production(
        modele_production:      Optional[Dict],
        valide_par_actuaire_dl: Optional[str],
    ) -> Optional[Dict]:
        """
        Garde-fou DÉLIBÉRÉ (point 1) : dès qu'un modèle de la famille Deep
        Learning est retenu en production SANS validation actuarielle humaine
        explicite, renvoie l'alerte à surfacer dans ALERTES_MODELE — sinon None.
        L'alerte « requise » se tait une fois valide_par_actuaire_dl renseigné
        (l'action est faite) ; la validation reste, elle, tracée dans audit_trail
        et rendue dans les rapports (synthese_modele_dl). Isolé pour testabilité.
        """
        mp = modele_production or {}
        if str(mp.get('famille', '')) != 'Deep Learning' or valide_par_actuaire_dl:
            return None
        return {
            'modele': mp.get('modele', 'DL'),
            'severite': 'AMBRE',
            'code': 'dl_validation_humaine_requise',
            'message': "Modele Deep Learning retenu en production - validation "
                       "actuarielle humaine requise avant deploiement, quel que "
                       "soit le statut RAG.",
        }

    def _calculer_statut_rag(
        self,
        modele_production:  Dict,
        classement:         List[Dict],
        profil_valide_par:  Optional[str] = None,
        environnement:      str = 'production',
        backtest:           Optional[Dict] = None,
        valide_par_actuaire_dl: Optional[str] = None,
        modele_ampute:      Optional[Dict] = None,
        hypotheses_glm:     Optional[Dict] = None,   # r3['hypotheses'] (A3 GLM)
        hypotheses_ml:      Optional[Dict] = None,   # r4['hypotheses'] (A4 ML)
        cible_est_frequence: bool = True,
    ) -> str:
        """
        Statut RAG basé sur le score global du modèle de production.
        VERT  : score ≥ 0.60 ET gini ≥ 0.15 ET gouvernance validée
                ET validation temporelle disponible
        AMBRE : score ≥ 0.40 OU gini ≥ 0.05 OU gouvernance non validée
                OU validation temporelle indisponible
        ROUGE : score < 0.40 ET gini < 0.05

        GOUVERNANCE (ACPR-2022-P-01 §4.3 — Recommandation P5 v3) :
        En environnement='production', le choix du profil de pondération
        (Gini/Stabilité/Interprétabilité/RMSE) doit être validé par un
        actuaire nommément identifié avant déploiement. Sans validation
        (profil_valide_par=None), le statut est plafonné à AMBRE.

        DÉFAUT FAIL-SAFE (audit V4 point #10) : `environnement='production'`
        par défaut — PAS 'developpement'.

        VALIDATION TEMPORELLE OBLIGATOIRE (audit V7 BLOQUANT #2) : avant ce
        correctif, cette méthode ne recevait même pas `backtest` en
        paramètre — elle ne pouvait donc PHYSIQUEMENT PAS savoir si le
        walk-forward avait tourné. Conséquence concrète : la cible par
        défaut d'A6 (prime_pure) n'étant jamais produite par A2, le
        backtest se désactivait silencieusement
        (backtest['disponible']=False), et un modèle pouvait être certifié
        VERT sans qu'aucune validation temporelle n'ait été effectuée —
        exactement le type de certification que ce standard est censé
        empêcher. Même logique fail-safe que la gouvernance : en
        environnement='production', l'absence de backtest disponible
        plafonne désormais le statut à AMBRE.
        """
        score = modele_production.get('score_global', 0)
        gini  = modele_production.get('gini_test',   0)

        # Gouvernance : blocage VERT si profil non validé en production
        _gouvernance_ok = gouvernance_validee(profil_valide_par, environnement)
        if not _gouvernance_ok:
            logger.warning(
                "[GOUVERNANCE] profil_valide_par=None en environnement "
                "'production'. Statut plafonné à AMBRE. "
                "Réf. : ACPR-2022-P-01 §4.3."
            )

        # Validation temporelle : blocage VERT si backtest indisponible
        # en production (audit V7 BLOQUANT #2).
        _backtest_ok = not (
            environnement == 'production'
            and not (backtest or {}).get('disponible', False)
        )
        if not _backtest_ok:
            logger.warning(
                "[VALIDATION TEMPORELLE] backtest['disponible']=False en "
                "environnement 'production' — aucun walk-forward n'a "
                "effectivement tourné. Statut plafonné à AMBRE. "
                f"Raison : {(backtest or {}).get('note', 'non renseignée')}."
            )

        # ── FIDÉLITÉ DE LA RECALIBRATION WALK-FORWARD (audit interne 11/07/2026) ──
        # Le walk-forward ne sait recalibrer que les modèles ML (fabrique sklearn
        # creer_modele_ml_pour_nom). Quand le modèle retenu en production est un
        # GLM_* ou un DL_*, il retombe sur un PROXY GBM — honnêtement étiqueté
        # dans le rapport (correctif V4), mais cela signifie que la validation
        # temporelle a porté sur un modèle DIFFÉRENT de celui qui part en
        # production. Or le GLM est très fréquemment le modèle retenu.
        # Le flag 'modele_recalibre_fidele' existait déjà dans le dict backtest,
        # mais le gate ne le vérifiait pas : A6 pouvait donc certifier VERT sur
        # la foi d'une validation temporelle portant sur un autre modèle — même
        # classe de défaut que le BLOQUANT B2 de l'audit V7 (contrôle correct,
        # mais non câblé dans la décision).
        # On ne peut pas certifier un modèle de production sur la stabilité
        # temporelle d'un autre modèle : plafond AMBRE.
        _wf_fidele_ok = not (
            environnement == 'production'
            and (backtest or {}).get('disponible', False)
            and not (backtest or {}).get('modele_recalibre_fidele', False)
        )
        if not _wf_fidele_ok:
            logger.warning(
                "[VALIDATION TEMPORELLE] La recalibration walk-forward n'a PAS "
                "porté sur le modèle de production "
                f"({(backtest or {}).get('modele_recalibre', 'proxy')}) : la "
                "stabilité temporelle mesurée est celle d'un modèle différent. "
                "Statut plafonné à AMBRE en environnement 'production'."
            )

        # ── POUVOIR DISCRIMINANT — LIFT PAR DÉCILE (ajout D) ──────────────────
        # Le WF a poolé le lift décile-10/décile-1 du modèle de production
        # hors-échantillon. Un lift ROUGE (< 2.0) sur la FRÉQUENCE signale un
        # tarif qui ne suit pas le risque — la prime ne sépare pas les profils,
        # même si le Gini global paraît acceptable. Plafond AMBRE en production.
        #
        # LIMITÉ À LA FRÉQUENCE (lift_cible_frequence) — décision étayée par la
        # mesure : le seuil 2.0 est calé sur la fréquence (auto sain → lift poolé
        # ~2.5, plancher aléatoire ~1.1). La SÉVÉRITÉ (coût) et la prime pure ont
        # un lift atteignable structurellement plus bas (coût par sinistre bien
        # plus bruité → ~1.3 même pour un bon Gamma). Appliquer 2.0 au coût
        # plafonnerait à tort des modèles de sévérité sains. Le lift coût/prime
        # pure reste CALCULÉ et EXPOSÉ (informatif), mais ne plafonne pas le VERT
        # — même prudence que A3-H2 : pas de seuil hors domaine de calibration.
        # À caler séparément sur données réelles de coût.
        _lift_statut = (backtest or {}).get('lift_statut')
        _lift_ok = not (
            environnement == 'production'
            and (backtest or {}).get('lift_cible_frequence', False)
            and _lift_statut == 'ROUGE'
        )
        if not _lift_ok:
            logger.warning(
                f"[POUVOIR DISCRIMINANT] Lift walk-forward de FRÉQUENCE ROUGE "
                f"(ratio={(backtest or {}).get('lift_ratio')}, décile-10/décile-1 "
                f"< 2.0) : le modèle de production ne sépare pas les risques. "
                f"Statut plafonné à AMBRE en environnement 'production'.")

        # ── ANCRAGE DU CANN (Wüthrich) — audit 2026-07 ────────────────────────
        # Un CANN dont la couche GLM n'est PAS gelée (glm_gele=False) n'est pas un
        # vrai CANN : c'est un réseau libre, NON interprétable (audit S2 / ACPR).
        # Il survient quand A3 ne fournit pas de GLM Tweedie et qu'A5 tourne quand
        # même — A5 le signalait en log + métrique, mais le gate ne le lisait pas.
        # Livrer ce CANN dégradé en production, présenté comme un CANN
        # interprétable, est un défaut de gouvernance de MÊME CLASSE que la
        # recalibration infidèle : on ne certifie pas un modèle non interprétable.
        # Plafond AMBRE si le modèle de PRODUCTION est ce CANN non ancré.
        _cann_ancre_ok = not (
            environnement == 'production'
            and str(modele_production.get('modele', '')).upper().endswith('CANN')
            and modele_production.get('glm_gele') is False
        )
        if not _cann_ancre_ok:
            logger.warning(
                "[INTERPRÉTABILITÉ] Le modèle de production est un CANN NON ancré "
                "(glm_gele=False) : couche GLM librement entraînable, ce n'est pas "
                "un CANN Wüthrich et il n'est pas interprétable (audit S2). Cause "
                "probable : GLM Tweedie (A3) indisponible. Statut plafonné à AMBRE."
            )

        # ── CONFIRMATION HUMAINE D'UN MODÈLE DEEP LEARNING (garde-fou délibéré) ─
        # Indépendant, PAR CONCEPTION, du plafond wf-fidélité (_wf_fidele_ok) : même
        # si demain le walk-forward sait recalibrer fidèlement un DL
        # (modele_recalibre_fidele=True), un modèle de la famille Deep Learning
        # retenu en production reste une boîte noire dont le déploiement exige une
        # validation actuarielle humaine explicite. Fail-safe comme profil_valide_par :
        # valide_par_actuaire_dl=None par défaut → plafond AMBRE tant qu'un actuaire
        # n'a pas nommément confirmé.
        # DISTINCT de _cann_ancre_ok : celui-ci vise un CANN DÉGRADÉ (non
        # interprétable) ; ici le DL peut être parfaitement sain (CANN bien ancré,
        # TabNet) — le motif est l'exigence de confirmation humaine, pas un défaut du
        # modèle. Les deux plafonds se déclenchent indépendamment (cf. le cas d'un
        # CANN dégradé MAIS confirmé : _dl_confirme_ok repasse True, _cann_ancre_ok
        # reste False — la confirmation humaine ne blanchit pas la non-interprétabilité).
        _dl_confirme_ok = not (
            environnement == 'production'
            and str(modele_production.get('famille', '')) == 'Deep Learning'
            and not valide_par_actuaire_dl
        )
        if not _dl_confirme_ok:
            logger.warning(
                "[CONFIRMATION DL] Le modèle de production est un modèle Deep "
                f"Learning ({modele_production.get('modele', 'DL')}) : validation "
                "actuarielle humaine explicite requise (valide_par_actuaire_dl) "
                "avant tout VERT, indépendamment de la fidélité de recalibration "
                "walk-forward. Statut plafonné à AMBRE."
            )

        # ── MODÈLE AMPUTÉ (colonnes du plan absentes des données) ─────────────
        # Le plan signé DÉCLARE ce qui est nécessaire. Si les données ne portent
        # pas une de ses colonnes, les modèles sont calibrés SANS ce facteur : on
        # ne certifie pas VERT un modèle amputé, quelle que soit la qualité du
        # Gini ou du walk-forward. Plafond AMBRE, jamais bloquant — même logique
        # que les garde-fous DL ci-dessus. AUCUN SEUIL : une seule colonne suffit
        # (BLOQUANT B5 : un facteur détruit = −17,4 % de Gini).
        # ⚠ DÉFAUT NON PLAFONNANT : si l'information est absente (modele_ampute
        # None — appel direct du gate, agents antérieurs), on NE plafonne PAS. On
        # ne dégrade que sur une information POSITIVE d'amputation ; inventer une
        # amputation faute de donnée serait un faux signal.
        _plan_complet_ok = not (modele_ampute or {}).get('ampute', False)
        if not _plan_complet_ok:
            logger.warning(
                "[PLAN INCOMPLET] Modele de production AMPUTE : "
                f"{len((modele_ampute or {}).get('colonnes_manquantes', []))} "
                f"colonne(s) declaree(s) au plan "
                f"'{(modele_ampute or {}).get('plan', '?')}' absente(s) des "
                "donnees. Statut plafonne a AMBRE."
            )

        # ── RÉSULTAT DU WALK-FORWARD (audit V10, BLOQUANT B2) ─────────────────
        # Le gate vérifiait que le walk-forward avait EU LIEU (`disponible`) et
        # qu'il portait sur le bon modèle (`modele_recalibre_fidele`) — mais
        # JAMAIS qu'il avait RÉUSSI. Il ignorait intégralement gini_wf_moyen,
        # ae_ratio, ae_cv_wf, n_fenetres_rouge et stabilite_wf.
        # Prouvé par exécution : un modèle avec A/E = 0,45 (sous-tarification de
        # 55 %), toutes les fenêtres en ROUGE, stabilité « 🔴 Instable » et même
        # gini_wf_moyen = None (aucune métrique produite) était certifié VERT.
        # Un contrôle dont on ne lit pas le résultat n'est pas un contrôle.
        #
        # Seuils : ceux qu'A6 s'applique déjà à lui-même dans son interprétation
        # du backtest (l.754-756) — 0,95-1,05 « non biaisé », 0,90-1,10 « légère
        # déviation ». On exige donc, pour un VERT en production, que le A/E
        # reste au moins dans la bande de légère déviation, qu'une métrique de
        # discrimination ait bien été produite, et que la stabilité inter-fenêtres
        # ne soit pas rouge.
        _bt = backtest or {}
        _wf_resultat_ok = True
        _wf_motif = ''
        if environnement == 'production' and _bt.get('disponible', False):
            _gini_wf = _bt.get('gini_wf_moyen')
            _ae      = _bt.get('ae_ratio')          # ⚠ DERNIÈRE fenêtre seulement
            _ae_moy  = _bt.get('ae_moyen_wf')       # moyenne sur TOUTES les fenêtres
            _n_rouge = _bt.get('n_fenetres_rouge', 0) or 0
            _stab    = str(_bt.get('stabilite_wf', ''))
            _cv      = _bt.get('ae_cv_wf')   # ⚠️ le CHAMP, pas son libellé
            if _gini_wf is None:
                _wf_resultat_ok = False
                _wf_motif = ("aucune métrique de discrimination produite "
                             "(gini_wf_moyen=None) — le walk-forward n'a rien validé")
            elif _ae is None or not (AE_FENETRE_ACCEPTABLE[0] <= float(_ae)
                                 <= AE_FENETRE_ACCEPTABLE[1]):
                _wf_resultat_ok = False
                _wf_motif = (f"A/E walk-forward (dernière fenêtre) = {_ae} hors bande "
                             f"acceptable [0,90 ; 1,10] — biais de tarification "
                             f"systématique")
            # ── ANGLE MORT RÉSIDUEL DU GATE (audit V11) ───────────────────────
            # 'ae_ratio' ne porte que sur la DERNIÈRE fenêtre (a6:938-939). Un
            # modèle pouvait donc avoir 3 fenêtres ROUGE sur 4 et rester VERT,
            # au seul motif que la dernière année était bonne. Or A6 calcule
            # déjà 'ae_moyen_wf' et 'n_fenetres_rouge' — il ne les lisait
            # simplement pas. Même maladie que B2, un cran plus fin : le
            # contrôle existe, son résultat n'est pas exploité.
            # Un VERT de production atteste la stabilité du modèle DANS LE
            # TEMPS : une seule fenêtre en échec la contredit.
            elif _n_rouge > 0:
                _wf_resultat_ok = False
                _wf_motif = (f"{_n_rouge} fenêtre(s) walk-forward en ROUGE : le "
                             f"modèle a échoué la validation temporelle sur au "
                             f"moins un exercice, même si la dernière année est "
                             f"bonne")
            elif _ae_moy is not None and not (
                AE_FENETRE_ACCEPTABLE[0] <= float(_ae_moy)
                <= AE_FENETRE_ACCEPTABLE[1]):
                _wf_resultat_ok = False
                _wf_motif = (f"A/E MOYEN sur toutes les fenêtres = {_ae_moy}, hors "
                             f"bande acceptable [0,90 ; 1,10] — biais persistant")
            # ⚠️⚠️ ON LIT LE CHAMP, PLUS L'EMOJI. Avant : `'🔴' in _stab` —
            # une décision qui bloque le VERT dépendait de la présence d'un
            # symbole dans un LIBELLÉ D'AFFICHAGE. Le libellé est fait pour
            # être lu par un humain, pas interrogé par un verrou.
            # ⚠️ `_cv` peut valoir None (CV non mesurable) : on ne dégrade
            # alors PAS — une absence de mesure n'est pas une instabilité.
            elif _cv is not None and float(_cv) > SEUIL_CV_INSTABLE:
                _wf_resultat_ok = False
                _wf_motif = (f"stabilité inter-fenêtres dégradée — CV A/E = "
                             f"{float(_cv):.4f} > {SEUIL_CV_INSTABLE} "
                             f"({_stab})")
        if not _wf_resultat_ok:
            logger.warning(
                f"[VALIDATION TEMPORELLE] Le walk-forward a tourné mais son "
                f"RÉSULTAT est insuffisant : {_wf_motif}. "
                f"Statut plafonné à AMBRE en environnement 'production'."
            )

        # ── PLAFOND DE VRAISEMBLANCE DU GINI (audit V12) ──────────────────────
        # Un Gini de fréquence > 0,60 sur un portefeuille Non-Vie n'est pas un
        # exploit : c'est une ALERTE. La littérature situe les GLM de fréquence
        # auto entre 0,15 et 0,35 ; 0,50 est déjà exceptionnel. Les DEUX fuites
        # bloquantes de l'histoire de ce module affichaient 0,91 (V8, prime_pure)
        # et 0,92 (V12, garantie_montant_regle) — contre 0,20 et 0,07 une fois
        # corrigées.
        # Ce garde-fou est le pendant, au niveau du RÉSULTAT, du contrôle par
        # l'effet appliqué au niveau des FEATURES : même une fuite qui aurait
        # traversé tous les filtres se trahit par une performance impossible.
        # Il ne dépend d'aucun nom de colonne — donc il attrapera aussi les
        # fuites que personne n'a encore imaginées.
        # ⚠️⚠️ LA CIBLE N'EST PLUS SUPPOSÉE — constat `a6/C8`. Elle arrive du
        # site d'appel, qui seul sait ce qu'A6 compare. Le défaut par défaut
        # reste `True` : les invariants de fuite (test_invariants) appellent
        # cette méthode SANS la cible, et ils doivent continuer à prouver
        # EXACTEMENT ce qu'ils prouvaient. `run()`, lui, passe la valeur
        # MESURÉE — un contrôle positif l'épingle.
        _verdict = verdict_vraisemblance_gini(
            gini, cible_est_frequence=cible_est_frequence)
        if _verdict == VRAISEMBLANCE_NON_CALIBRE:
            logger.warning(
                f"[VRAISEMBLANCE] Gini = {gini:.4f} sur une cible NON de "
                f"fréquence : le plafond {GINI_PLAUSIBLE_MAX_FREQUENCE} ne "
                f"s'y applique pas et aucune borne publiée ne le remplace. "
                f"Le contrôle anti-fuite par la performance N'A PAS ÉTÉ "
                f"EXERCÉ — il reste à faire sur les variables. Le VERT est "
                f"donc BLOQUÉ à ce titre, et le statut plafonne à AMBRE : "
                f"une absence de contrôle n'est pas un contrôle satisfait. "
                f"Ce n'est pas un défaut établi — c'est une vérification qui "
                f"n'a pas eu lieu, et elle se dit.")
        # ⚠️⚠️ UN CONTRÔLE QUI N'A PAS PU S'EXERCER NE VAUT PAS UN CONTRÔLE
        # SATISFAIT. Le VERT affirme que TOUT a été vérifié ; si le plafond ne
        # sait pas juger cette cible, il bloque le VERT **en le disant** —
        # exactement comme le fait déjà `_backtest_ok` quand la validation
        # temporelle est indisponible. Ce n'est PAS une mise hors service :
        # le statut plafonne à AMBRE, jamais à ROUGE.
        _cible_modele = modele_production.get('cible') or 'inconnue'
        _vraisemblance_ok = _verdict not in (
            VRAISEMBLANCE_IMPLAUSIBLE, VRAISEMBLANCE_NON_CALIBRE)
        if _verdict == VRAISEMBLANCE_IMPLAUSIBLE:
            logger.warning(
                f"[VRAISEMBLANCE] Gini = {gini:.4f} > {GINI_PLAUSIBLE_MAX_FREQUENCE} "
                f"— performance actuariellement IMPLAUSIBLE pour un modèle de "
                f"fréquence Non-Vie. L'hypothèse la plus probable n'est pas "
                f"« excellent modèle » mais FUITE DE DONNÉES : une variable "
                f"connaissant déjà la sinistralité s'est glissée dans la matrice X. "
                f"Statut plafonné à AMBRE — vérifier les features avant tout "
                f"déploiement."
            )

        # ── PLAFOND HYPOTHÈSES DE MODÉLISATION (A3 GLM + A4 ML) ────────────────
        # Les hypothèses de validation étaient CALCULÉES et rapportées mais jamais
        # LUES par la décision — même classe de défaut que B2 (contrôle correct,
        # non câblé). Une hypothèse plafonnante en ROUGE plafonne à AMBRE.
        # NE SONT PAS plafonnantes :
        #  · A3-H3 / A4-H3 (Gini) : déjà couvertes par le gate (pas de doublon) ;
        #  · A3-H4 (stabilité bootstrap) : informative seulement.
        # A3-H2 (homoscédasticité) : RÉINTÉGRÉE aux plafonnantes — sa métrique
        # était CASSÉE (ancien std_quintile/std_global < 0.30 inatteignable → ROUGE
        # sur TOUT modèle sain, mesuré 1.03) ; réparée en ratio de variance max/min
        # entre quintiles de μ̂ (VERT<2.0), qui vaut ~1.07 sur un GLM sain (mesuré)
        # et ne monte qu'en cas d'hétéroscédasticité réelle. Réparée → elle rejoint
        # les plafonnantes comme prévu (contrôle de spécification du GLM).
        _HYP_PLAFONNANTES = [
            (hypotheses_glm, 'h1_poisson'),
            (hypotheses_glm, 'h2_homosc'),     # réintégrée (métrique réparée : ratio de variance)
            (hypotheses_glm, 'h5_deviance'),   # ajout C — déviance résiduelle / df
            (hypotheses_ml,  'h1_overfitting'),
            (hypotheses_ml,  'h2_psi'),
            (hypotheses_ml,  'h4_calibration'),
        ]
        _hyp_rouges = [k for (d, k) in _HYP_PLAFONNANTES
                       if (d or {}).get(k, {}).get('statut') == 'ROUGE']
        _hypotheses_ok = not (environnement == 'production' and _hyp_rouges)
        if not _hypotheses_ok:
            logger.warning(
                f"[HYPOTHÈSES] Hypothèse(s) de modélisation en ROUGE {_hyp_rouges} "
                f"— statut plafonné à AMBRE en environnement 'production'.")

        # ⚠️ CE QUI EMPÊCHE LE VERT SE NOMME, ET DANS LE MÊME GESTE QUE LA
        # DÉCISION — une liste construite ailleurs divergerait du test qui
        # suit. Chaque phrase est écrite pour un lecteur du rapport, pas pour
        # un développeur : elle dit la cause, pas le nom de la variable.
        self._raisons_plafond = [phrase for satisfait, phrase in (
            (score >= 0.60,
             (f"Score composite = {score:.4f} < 0.60 — le modèle retenu "
              f"n'atteint pas le seuil de la grille multicritères.")),
            (gini >= 0.15,
             f"Gini = {gini:.4f} < 0.15 — pouvoir discriminant insuffisant."),
            (_gouvernance_ok,
             ("Décision de modèle non validée par un actuaire identifié en "
              "environnement de production (ACPR-2022-P-01 §4.3).")),
            (_backtest_ok,
             ("Backtesting indisponible en production — la validation "
              "temporelle n'a pas pu être conduite.")),
            (_wf_fidele_ok,
             "La validation temporelle ne porte pas sur le modèle retenu."),
            (_wf_resultat_ok,
             ("Le backtesting walk-forward a été conduit et son résultat "
              "n'est pas satisfaisant.")),
            (_vraisemblance_ok,
             ("Gini hors des bornes plausibles pour la branche."
              if _verdict == VRAISEMBLANCE_IMPLAUSIBLE else
              f"Plafond de vraisemblance NON CALIBRÉ pour la cible "
              f"'{_cible_modele}' — le contrôle anti-fuite par la "
              f"performance n'a pas pu être exercé.")),
            (_cann_ancre_ok,
             "Modèle CANN non ancré sur un GLM vérifié."),
            (_dl_confirme_ok,
             "Modèle de deep learning non confirmé par un actuaire."),
            (_plan_complet_ok,
             ("Le plan tarifaire est amputé — des variables déclarées n'ont "
              "pas été utilisées.")),
            (_hypotheses_ok,
             "Hypothèse(s) de modélisation en ROUGE : "
             + ', '.join(_hyp_rouges) + "."),
            (_lift_ok,
             "Le lift par décile ne confirme pas la hiérarchie des risques."),
        ) if not satisfait]

        if (score >= 0.60 and gini >= 0.15 and _gouvernance_ok
                and _backtest_ok and _wf_fidele_ok and _wf_resultat_ok
                and _vraisemblance_ok and _cann_ancre_ok and _dl_confirme_ok
                and _plan_complet_ok and _hypotheses_ok and _lift_ok):
            return 'VERT'
        # ── ANTI-SÉLECTION : DISQUALIFIANT (auto-audit 11/07/2026) ────────────
        # Un Gini NÉGATIF signifie que le modèle discrimine À L'ENVERS : il
        # attribue les primes les plus faibles aux risques les plus élevés.
        # C'est le pire résultat possible en tarification — pire qu'un modèle
        # nul, car il organise activement l'anti-sélection. Il ne peut donc pas
        # ressortir en AMBRE au motif que son « score composite » est correct :
        # le score est relatif au meilleur modèle du profil, et si TOUS les
        # modèles sont anti-sélectifs, le meilleur d'entre eux vaut quand même
        # ≈ 1,0. Un tel modèle est ROUGE, sans discussion.
        if gini < 0:
            logger.warning(
                f"[ANTI-SÉLECTION] Gini du modèle de production = {gini:.4f} < 0 : "
                f"le modèle discrimine à l'envers. Statut forcé à ROUGE."
            )
            return 'ROUGE'
        elif score >= 0.40 or gini >= 0.05:
            return 'AMBRE'
        return 'ROUGE'

    def _commenter_actuaire_senior(
        self,
        classement:        List[Dict],
        modele_production: Dict,
        sous_branche:      str,
        statut_rag:        str,
        backtest:          Dict
    ) -> str:
        emoji  = glyphe_rag(statut_rag)
        mp     = modele_production

        # ── NIVEAU 1 : LECTURE ────────────────────────────────────────────────
        n1 = (
            f"{emoji} COMPARAISON FINALE — {statut_rag}\n"
            f"Sous-branche    : {sous_branche}\n"
            f"Modèles comparés: {len(classement)}\n\n"
            f"MODÈLE SÉLECTIONNÉ POUR LA PRODUCTION :\n"
            f"  Nom              : {mp['modele']}\n"
            f"  Famille          : {mp['famille']}\n"
            f"  Score global     : {mp['score_global']:.4f}/1.0\n"
            f"  Gini test        : {mp['gini_test']:.4f}\n"
            f"  RMSE test        : {mp['rmse_test']:.2f}\n"
            f"  Interprétabilité : {mp['interpretabilite']:.2f}/1.0\n"
            f"  Overfit ratio    : {mp['overfit_ratio']:.2f}\n"
        )

        def _fmt4(v):
            """Un nombre absent se DIT — il ne lève pas et ne s'invente pas."""
            return (f"{float(v):.4f}" if isinstance(v, (int, float))
                    else "non mesuré")

        if backtest.get('disponible'):
            wf_info = ""
            if backtest.get('split') == SPLIT_WALK_FORWARD:
                wf_info = (
                    f"  Fenêtres WF      : {backtest.get('n_fenetres', 'N/A')} "
                    f"({backtest.get('n_fenetres_rouge', 0)} ROUGE)\n"
                    f"  Stabilité WF     : {backtest.get('stabilite_wf', 'N/A')}\n"
                    # ⚠️⚠️ `get(cle, 'N/A')` NE PROTÈGE PAS ICI : la clé EXISTE
                    # et vaut `None` quand le CV n'a pas pu être calculé.
                    # Un `:.4f` sur `None` LÈVE. Troisième fois que
                    # « présent mais VIDE » revient dans cet audit.
                    f"  CV A/E WF        : {_fmt4(backtest.get('ae_cv_wf'))}\n"
                )
            n_seg = len(backtest.get('ae_par_segment', {}))
            n1 += (
                f"\nBACKTESTING TEMPOREL ({backtest.get('split', 'N/A')}) :\n"
                f"  A/E ratio        : {backtest.get('ae_ratio', 'N/A')}\n"
                f"  Interprétation   : {backtest.get('interpretation', 'N/A')}\n"
                f"{wf_info}"
                f"  A/E par segment  : {n_seg} segment(s) analysé(s)"
            )

        # ── NIVEAU 2 : DIAGNOSTIC ─────────────────────────────────────────────
        if statut_rag == 'VERT':
            n2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le modèle {mp['modele']} est sélectionné comme modèle "
                f"de production selon la grille multicritères actuarielle "
                f"(Gini 40% + Stabilité 30% + Interprétabilité 20% + RMSE 10%). "
                f"Son score global de {mp['score_global']:.4f}/1.0 reflète "
                f"un bon équilibre entre performance discriminante, "
                f"stabilité train/test et interprétabilité réglementaire. "
                f"Ce modèle est défendable devant un auditeur S2 "
                f"et conforme aux exigences de l'AI Act 2025."
            )
        elif statut_rag == 'AMBRE':
            n2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le modèle {mp['modele']} est sélectionné mais présente "
                f"des points d'attention. Le score global de "
                f"{mp['score_global']:.4f}/1.0 est acceptable mais "
                f"pourrait être amélioré avec davantage de données "
                f"ou des features supplémentaires. "
                f"Surveillance renforcée recommandée en production."
            )
        else:
            n2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                "Aucun modèle ne présente des performances suffisantes "
                "pour la production actuarielle. Vérifiez la qualité "
                "des données (Agent A1) et la richesse des features (Agent A2)."
            )

        # ── NIVEAU 3 : RECOMMANDATION ─────────────────────────────────────────
        if statut_rag in ['VERT', 'AMBRE']:
            n3 = (
                "RECOMMANDATION :\n"
                f"→ Déployer {mp['modele']} comme modèle de tarification.\n"
                f"→ Passer à l'Agent A7 (Provisionnement).\n"
                f"→ Surveiller le ratio A/E trimestriellement.\n"
                # ⚠️ LE LIBELLÉ ET LA DÉCISION LISENT LE MÊME NOMBRE. Recopié,
                # ce texte deviendrait faux au premier ajustement de la bande
                # sans que rien ne tombe — même geste que `SEUIL_CV_INSTABLE`.
                f"→ Recalibrer annuellement ou si A/E sort de "
                f"[{AE_FENETRE_ACCEPTABLE[0]:.2f}, "
                f"{AE_FENETRE_ACCEPTABLE[1]:.2f}].\n"
                f"→ Conserver les modèles GLM comme benchmark réglementaire."
            )
        else:
            n3 = (
                "RECOMMANDATION :\n"
                "→ Arrêt — ne pas déployer en production.\n"
                "→ Relancer A1 avec revue qualité des données.\n"
                "→ Enrichir les features avec sources externes."
            )

        return f"{n1}\n\n{n2}\n\n{n3}"

    def _afficher_rapport_console(
        self, audit_id, sous_branche, classement,
        modele_production, statut_rag, commentaire
    ) -> None:
        emoji = glyphe_rag(statut_rag)
        sep   = "═" * 65
        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT A6 COMPARAISON | {audit_id}")
        print(sep)
        print(f"  {emoji} STATUT : {statut_rag}")
        print(f"\n  {'#':<4}{'Modèle':<30}{'Score':<8}{'Gini':<8}{'Famille'}")
        print(f"  {'-'*60}")
        for i, m in enumerate(classement[:10], 1):
            print(
                f"  {i:<4}{m['modele']:<30}"
                f"{m['score_global']:<8.4f}"
                f"{m['gini_test']:<8.4f}"
                f"{m['famille']}"
            )
        print(f"\n  ⭐ MODÈLE PRODUCTION : {modele_production['modele']}")
        print(f"\n{sep}")
        for ligne in commentaire.split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    # ══════════════════════════════════════════════════════════════════════════
    # GRAPHIQUES v3 + AIDE À LA DÉCISION
    # ══════════════════════════════════════════════════════════════════════════

    def _charts_tarif_v3(self, graphiques: dict, backtest: dict, courbes: dict,
                         modele_production: dict = None) -> None:
        """Ajoute les graphiques V3 (core/charts_tarif) au dict `graphiques`.
        Chaque figure est OPTIONNELLE : données manquantes (pas de backtest, pas
        de lift fréquence…) → chart non produit, le run continue (pattern
        synthese_mapping : absence = silence)."""
        bt = backtest or {}
        cb = courbes or {}
        # Lift par décile (vrai lift walk-forward de D)
        try:
            dec = bt.get('lift_deciles_wf')
            if dec:
                graphiques['chart_lift_decile'] = chart_lift_decile(
                    dec, bt.get('lift_ratio'))
        except Exception as e:
            logger.debug(f"chart_lift_decile non produit : {e}")
        # Courbe de Lorenz + aire de Gini
        try:
            lz = cb.get('lorenz') or {}
            if lz.get('x') and lz.get('y'):
                # ⚠️ LES DEUX GINI, PAS UN SEUL. `gini_observe` est le
                # PLAFOND (tri par la valeur observée = tri d'un oracle) ;
                # le Gini du modèle est son pouvoir discriminant réel. Leur
                # rapport dit ce qu'aucun des deux ne dit seul.
                graphiques['chart_lorenz_gini'] = chart_lorenz_gini(
                    lz['x'], lz['y'], cb.get('gini_observe'),
                    gini_modele=(modele_production or {}).get('gini_test'))
        except Exception as e:
            logger.debug(f"chart_lorenz_gini non produit : {e}")
        # Backtesting walk-forward A/E par fenêtre
        try:
            wf = bt.get('walk_forward')
            if wf:
                # ⚠️ LA FIGURE NE POSSÈDE PLUS DE SEUIL : elle reçoit celui
                # de la règle. Constat `charts/C2` -- son rectangle vert
                # promettait 0,85-1,15 là où le verrou refuse hors 0,90-1,10.
                graphiques['chart_walkforward_ae'] = chart_walkforward_ae(
                    wf, bande_acceptable=AE_FENETRE_ACCEPTABLE,
                    bande_stricte=AE_FENETRE_STRICTE)
        except Exception as e:
            logger.debug(f"chart_walkforward_ae non produit : {e}")

    def _generer_graphiques(
        self,
        classement:       List[Dict],
        modele_prod:      Dict,
        profil:           str,
    ) -> Dict:
        """
        Génère 4 graphiques d'aide à la décision style PowerBI.

        G1 — Radar multicritères (vision 360° de chaque modèle)
        G2 — Scores par profil de pondération
        G3 — Scatter Gini vs Stabilité (quadrant idéal)
        G4 — Bar chart scores finaux avec modèle recommandé
        """
        if not PLOTLY_OK:
            return {}

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
        AMBRE = couleur_rag("AMBRE", FOND_SOMBRE)
        BLEU    = "#3498DB"
        # ⚠️ `ROUGE` n'est plus défini ici : il ne servait QUE dans le cycle
        # décoratif ci-dessous. Une couleur de statut qu'on retire d'un cycle
        # ne se garde pas « au cas où » — elle deviendrait une locale morte,
        # et la prochaine main la remettrait dans la liste.

        # ⚠️⚠️ CONSTAT `charts/C4` — MÊME DÉFAUT QU'EN A4, MÊME CORRECTIF.
        # `VERT`, `AMBRE` et `ROUGE` (soit `couleur_rag(...)`) servaient de
        # cycle DÉCORATIF : `COULEURS[idx % len(COULEURS)]`. Un modèle était
        # peint en rouge de statut à cause de son RANG DANS UNE LISTE.
        # ⚠️ `#9B59B6` ne passait pas non plus : 2,49 sur `#1B3A5C`, sous 3:1.
        # Le cycle est identique à celui d'A4 plus le BLANC — mesuré de la
        # même façon (aucun `couleur_rag`, aucune teinte de statut hors l'OR
        # maison, les sept au-dessus de 3:1, min L1 deuteranope 59).
        # ⚠️ L'OR garde son sens ICI : `OR if est_prod else COULEURS[...]` —
        # il marque le modèle de PRODUCTION, ce qui est une information, pas
        # une décoration. Il reste donc aussi en tête du cycle.
        COULEURS = [OR, BLEU, "#C89BD4", "#B8C4F0",
                    "#C2678F", GRIS, BLANC]

        LAYOUT_BASE = dict(
            paper_bgcolor = NAVY,
            plot_bgcolor  = NAVY_L,
            font          = dict(family="Inter, Arial", color=BLANC, size=11),
            margin        = dict(l=16, r=16, t=52, b=16),
            height        = 340,
            hoverlabel    = dict(bgcolor=NAVY_LL, bordercolor=OR,
                                 font_size=12, font_color=BLANC),
            legend        = dict(
                bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                orientation="h", yanchor="bottom", y=1.02,
            ),
        )

        graphiques = {}

        # ── G1 : RADAR MULTICRITÈRES ──────────────────────────────────────────
        try:
            categories = ['Gini', 'Stabilité', 'Interprétabilité', 'RMSE normalisé']

            fig1 = go.Figure()

            # Référence max pour normalisation RMSE
            rmses = [c.get('rmse_test', 1) for c in classement if c.get('rmse_test', 0) > 0]
            rmse_max = max(rmses) if rmses else 1

            for idx, c in enumerate(classement[:5]):
                nom   = c['modele']
                gini  = min(c.get('gini_test', 0) / 0.35, 1.0)
                stab  = min(1 / max(c.get('overfit_ratio', 1), 0.5), 1.0)
                interp= c.get('score_interpretabilite', 0.6)
                rmse  = 1 - (c.get('rmse_test', 0) / rmse_max)

                vals = [gini, stab, interp, rmse]
                est_prod = nom == modele_prod.get('modele', '')
                couleur  = OR if est_prod else COULEURS[idx % len(COULEURS)]
                width    = 3 if est_prod else 1.5

                fig1.add_trace(go.Scatterpolar(
                    r    = vals + [vals[0]],
                    theta= categories + [categories[0]],
                    fill = 'toself' if est_prod else 'none',
                    fillcolor = f'rgba(201,168,76,0.12)' if est_prod else 'rgba(0,0,0,0)',
                    name = f"{'⭐ ' if est_prod else ''}{nom}",
                    line = dict(color=couleur, width=width),
                    marker= dict(color=couleur, size=6 if est_prod else 4),
                    hovertemplate=(
                        f"<b>{'⭐ ' if est_prod else ''}{nom}</b><br>"
                        f"Gini : {c.get('gini_test',0):.3f}<br>"
                        f"Stabilité : {stab:.2f}<br>"
                        f"Interprét. : {interp:.2f}<br>"
                        f"RMSE norm. : {rmse:.2f}"
                        "<extra></extra>"
                    ),
                ))

            fig1.update_layout(
                polar=dict(
                    bgcolor=NAVY_L,
                    radialaxis=dict(
                        visible=True, range=[0, 1],
                        tickfont=dict(color=GRIS, size=9),
                        gridcolor='rgba(255,255,255,0.08)',
                        linecolor='rgba(255,255,255,0.1)',
                    ),
                    angularaxis=dict(
                        tickfont=dict(color=BLANC, size=11),
                        gridcolor='rgba(255,255,255,0.08)',
                        linecolor='rgba(255,255,255,0.1)',
                    ),
                ),
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family="Inter, Arial", color=BLANC),
                margin=dict(l=60, r=60, t=52, b=16),
                height=380,
                title=dict(
                    text="🎯 Radar multicritères — Vision 360° des modèles",
                    font=dict(color=BLANC, size=13), x=0.01,
                ),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                            orientation="h", yanchor="bottom", y=-0.15),
                showlegend=True,
            )
            graphiques['radar_multicriteres'] = fig1

        except Exception as e:
            logger.warning(f"G1 radar échoué : {e}")

        # ── G3 : SCATTER GINI vs STABILITÉ ───────────────────────────────────
        try:
            fig3 = go.Figure()

            # Zones de qualité
            fig3.add_shape(type="rect", x0=0.5, x1=1.0, y0=0.20, y1=0.40,
                           fillcolor="rgba(46,204,113,0.08)",
                           line=dict(color=VERT, width=1, dash="dot"))
            fig3.add_annotation(x=0.75, y=0.39, text="Zone idéale",
                                 font=dict(color=VERT, size=9), showarrow=False)

            for idx, c in enumerate(classement):
                nom    = c['modele']
                gini   = c.get('gini_test', 0)
                stab   = 1 / max(c.get('overfit_ratio', 1.0), 0.5)
                est_prod = nom == modele_prod.get('modele', '')
                couleur  = OR if est_prod else COULEURS[idx % len(COULEURS)]

                fig3.add_trace(go.Scatter(
                    x    = [stab],
                    y    = [gini],
                    mode = 'markers+text',
                    name = nom,
                    text = [f"{'⭐' if est_prod else ''}{nom.replace('ML_','').replace('GLM_','').replace('DL_','')}"],
                    textposition='top center',
                    textfont=dict(color=BLANC, size=9),
                    marker=dict(
                        color=couleur, size=18 if est_prod else 12,
                        symbol='star' if est_prod else 'circle',
                        line=dict(color=NAVY, width=2), opacity=0.9,
                    ),
                    hovertemplate=(
                        f"<b>{nom}</b><br>"
                        f"Gini : <b>{gini:.4f}</b><br>"
                        f"Stabilité : <b>{stab:.2f}</b><br>"
                        f"Overfit : {c.get('overfit_ratio',1):.2f}"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                ))

            layout3 = dict(**LAYOUT_BASE)
            layout3.update(dict(
                title=dict(
                    text="🎯 Gini vs Stabilité — Zone idéale = haut-droite",
                    font=dict(color=BLANC, size=13), x=0.01,
                ),
                xaxis=dict(
                    title=dict(text="Stabilité (1/Overfit)",
                               font=dict(color=GRIS, size=10)),
                    showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                    tickfont=dict(color=GRIS), range=[0, 1.1],
                ),
                yaxis=dict(
                    title=dict(text="Gini test",
                               font=dict(color=GRIS, size=10)),
                    showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                    tickfont=dict(color=GRIS),
                ),
                annotations=layout3.get('annotations', []) + [dict(
                    x=0.02, y=0.97, xref='paper', yref='paper',
                    text="⭐ = Modèle de production recommandé",
                    showarrow=False, font=dict(color=OR, size=10),
                )],
            ))
            fig3.update_layout(**layout3)
            graphiques['scatter_gini_stabilite'] = fig3

        except Exception as e:
            logger.warning(f"G3 scatter échoué : {e}")

        # ── G4 : BAR CHART SCORES FINAUX ─────────────────────────────────────
        try:
            noms_f   = [c['modele'] for c in classement]
            scores_f = [c.get('score_global', 0) for c in classement]
            familles = [c.get('famille', '') for c in classement]

            colors_bar = []
            for c in classement:
                nom = c['modele']
                if nom == modele_prod.get('modele', ''):
                    colors_bar.append(OR)
                elif 'GLM' in c.get('famille', '').upper():
                    colors_bar.append(GRIS)
                elif 'Deep' in c.get('famille', ''):
                    colors_bar.append(BLEU)
                else:
                    colors_bar.append("rgba(201,168,76,0.5)")

            fig4 = go.Figure(go.Bar(
                x             = noms_f,
                y             = scores_f,
                marker_color  = colors_bar,
                marker_line   = dict(color=NAVY, width=1),
                width         = 0.5,
                opacity       = 0.9,
                text          = [f"{s:.3f}" for s in scores_f],
                textposition  = 'outside',
                textfont      = dict(color=BLANC, size=10),
                hovertemplate = (
                    "<b>%{x}</b><br>"
                    "Score global : <b>%{y:.4f}</b><extra></extra>"
                ),
            ))

            # Ligne seuil recommandation
            seuil = scores_f[0] * 0.90
            fig4.add_hline(
                y=seuil, line_dash="dot", line_color=AMBRE, line_width=1.5,
                annotation_text=f"Seuil -10% = {seuil:.3f}",
                annotation_font=dict(color=AMBRE, size=9),
                annotation_position="bottom right",
            )

            layout4 = dict(**LAYOUT_BASE)
            layout4.update(dict(
                title=dict(
                    text=f"🏆 Scores finaux — Profil '{profil}' · ⭐ = {modele_prod.get('modele','')}",
                    font=dict(color=BLANC, size=13), x=0.01,
                ),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(visible=False),
                bargap=0.35,
                annotations=layout4.get('annotations', []) + [dict(
                    x=0.02, y=0.97, xref='paper', yref='paper',
                    text="🟡 ML · 🔵 DL · ⬜ GLM",
                    showarrow=False, font=dict(color=GRIS, size=9),
                )],
            ))
            fig4.update_layout(**layout4)
            graphiques['scores_finaux'] = fig4

        except Exception as e:
            logger.warning(f"G4 scores finaux échoué : {e}")

        return graphiques

    def _generer_fiche_decision(
        self,
        classement:  List[Dict],
        modele_prod: Dict,
        profil:      str,
        *,
        backtest:   dict | None,
        statut_rag: str | None,
    ) -> Dict:
        """
        Génère la fiche d'aide à la décision pour l'actuaire.

        CONTENU :
        ──────────
        → Analyse des forces et faiblesses du modèle recommandé
        → Risques identifiés
        → Alternatives si le modèle recommandé ne convient pas
        → Questions à poser avant signature
        → Justification réglementaire (S2, AI Act 2025)

        ⚠️⚠️ `backtest` ET `statut_rag` SONT EXIGÉS, SANS DÉFAUT — constat
        `a6/C5`. Cette fiche portait « Conformité S2 Pilier 1 : modèle validé
        sur données de test indépendantes » **inconditionnellement**, parce
        qu'elle ne recevait ni l'un ni l'autre : elle l'écrivait même quand le
        walk-forward avait échoué et que le statut était plafonné.
        Un défaut à `None` rouvrirait la porte en silence ; on impose donc de
        les déclarer. `backtest=None` reste licite et SIGNIFIANT — c'est
        « aucune validation temporelle », et `avertissement_walk_forward` le
        dit. Ce qui n'est plus possible, c'est de ne rien dire du tout.
        """
        nom_prod  = modele_prod.get('modele', 'N/A')
        gini_prod = modele_prod.get('gini_test', 0)
        of_prod   = modele_prod.get('overfit_ratio', 1)
        sc_prod   = modele_prod.get('score_global', 0)
        fam_prod  = modele_prod.get('famille', '')

        # ── FORCES & FAIBLESSES ───────────────────────────────────────────────
        forces, faiblesses, risques = [], [], []

        if gini_prod > 0.25:
            forces.append(f"Excellent pouvoir discriminant (Gini={gini_prod:.3f})")
        elif gini_prod > 0.15:
            forces.append(f"Bon pouvoir discriminant (Gini={gini_prod:.3f})")
        else:
            faiblesses.append(f"Pouvoir discriminant faible (Gini={gini_prod:.3f})")

        if of_prod <= 1.10:
            forces.append(f"Très stable — risque d'overfitting minimal (ratio={of_prod:.2f})")
        elif of_prod <= 1.20:
            forces.append(f"Stablement acceptable (overfit ratio={of_prod:.2f})")
        else:
            faiblesses.append(f"Overfit détecté (ratio={of_prod:.2f}) — surveiller en production")
            risques.append("Dégradation possible des performances sur nouveaux contrats")

        if 'GLM' in fam_prod.upper():
            forces.append("Modèle linéaire — interprétable et défendable devant l'ACPR")
        elif 'Deep' in fam_prod:
            faiblesses.append("Modèle boîte noire — justification AI Act 2025 requise")
            risques.append("Auditeur S2 peut demander des explications supplémentaires")

        # ── ALTERNATIVES ──────────────────────────────────────────────────────
        alternatives = []
        for c in classement[1:4]:
            sc_diff = (sc_prod - c.get('score_global', 0)) / max(sc_prod, 0.001) * 100
            alternatives.append({
                'modele':     c['modele'],
                'score':      round(c.get('score_global', 0), 4),
                'gini':       round(c.get('gini_test', 0), 4),
                'ecart_score': round(sc_diff, 1),
                'conseil': (
                    f"Écart de {sc_diff:.1f}% — à considérer si "
                    f"{'stabilité prioritaire' if c.get('overfit_ratio',1) < of_prod else 'performance prioritaire'}"
                ),
            })

        # ── QUESTIONS AVANT SIGNATURE ─────────────────────────────────────────
        questions = [
            "Le portefeuille a-t-il connu des changements structurels récents (nouvelles garanties, tarif révisé) ?",
            f"Un auditeur S2 ou ACPR est-il prévu cette année ? (si oui → préférer un modèle interprétable)",
            f"Le Gini de {gini_prod:.3f} est-il suffisant pour la stratégie tarifaire ?",
            "Les données d'entraînement couvrent-elles au moins 3 ans d'historique ?",
            f"L'overfit ratio de {of_prod:.2f} est-il acceptable au regard du volume de données ?",
        ]

        if of_prod > 1.20:
            questions.append(
                "Avez-vous envisagé d'augmenter la régularisation (learning_rate=0.01, n_estimators=1000) ?"
            )

        # ── JUSTIFICATION RÉGLEMENTAIRE ───────────────────────────────────────
        # ⚠️⚠️ LA CONFORMITÉ S2 EST CONDITIONNELLE — constat `a6/C5`.
        # Cette ligne était écrite TOUJOURS. Elle affirme que le modèle a été
        # « validé sur données de test indépendantes » : c'est précisément ce
        # que le walk-forward établit ou infirme. On la conditionne donc à la
        # SOURCE UNIQUE du dépôt, `avertissement_walk_forward`, déjà utilisée
        # par les trois services de rapport — la fiche était le seul livrable
        # à ne pas la consulter.
        #
        # ⚠️ ET L'ABSENCE D'AFFIRMATION NE DOIT JAMAIS ÊTRE SILENCIEUSE : on ne
        # retire pas la ligne, on écrit qu'elle N'EST PAS ÉTABLIE et pourquoi.
        # Une ligne manquante se lit comme un oubli ; une ligne qui se dénonce
        # se lit comme un fait. C'est le BLOQUANT B3 sous une autre forme —
        # l'Excel y estampillait « ✓ Conforme » sur une recalibration sur proxy.
        justif_regl = []
        _avert_wf = avertissement_walk_forward(backtest)
        if _avert_wf is None and (statut_rag or '').upper() == 'VERT':
            justif_regl.append(
                "Conformité S2 Pilier 1 : modèle validé sur données de test "
                "indépendantes (validation temporelle walk-forward réussie, "
                f"statut {statut_rag})")
        else:
            _motifs = []
            if _avert_wf is not None:
                _motifs.append(_avert_wf)
            if (statut_rag or '').upper() != 'VERT':
                _motifs.append(
                    f"statut du modèle = {statut_rag or 'NON CALCULÉ'} "
                    f"(un modèle non VERT n'est pas certifié)")
            justif_regl.append(
                "⚠ CONFORMITÉ S2 PILIER 1 : NON ÉTABLIE À CE STADE — "
                + " · ".join(_motifs)
                + ". Cette fiche NE PEUT PAS attester que le modèle a été "
                  "validé sur données de test indépendantes.")
        justif_regl.append("AI Act 2025 Art. 13 : " + (
            "✅ Modèle linéaire — exigences d'explicabilité satisfaites"
            if 'GLM' in fam_prod.upper() or 'lineaire_regularise' in nom_prod.lower()
            else "⚠️ Modèle ML/DL — prévoir une note d'explicabilité (SHAP values)"
        ))
        justif_regl.append(f"IFRS 17 : prime pure utilisée pour Best Estimate — cohérence avec A7 à vérifier")

        return {
            'modele_recommande':    nom_prod,
            'profil_utilise':       profil,
            'score_final':          round(sc_prod, 4),
            'gini':                 round(gini_prod, 4),
            'overfit_ratio':        round(of_prod, 2),
            'forces':               forces,
            'faiblesses':           faiblesses,
            'risques':              risques,
            'alternatives':         alternatives,
            'questions_actuaire':   questions,
            'justification_regl':   justif_regl,
            'decision_finale':      "À VALIDER PAR L'ACTUAIRE RESPONSABLE",
        }


    def _valider_selection(
        self,
        classement:        list,
        modele_production: str,
        backtest:          Dict,
    ) -> Dict:
        """
        Validation des contrôles qualité de la sélection multicritères.

        C1 — Nombre de modèles comparés (min 3)
             Au moins 3 modèles évalués → sélection robuste ✅
             Moins de 3 → comparaison insuffisante ❌

        C2 — Écart Gini significatif entre modèles
             Écart max-min > 1% → différenciation réelle ✅
             Écart < 1% → tous les modèles équivalents ⚠️

        C3 — Cohérence du modèle retenu avec le profil
             Le modèle retenu doit être dans le top 3 du classement
             et son score > 0.70 → sélection cohérente ✅
        """
        import numpy as np

        # C1 — Nombre de modèles
        n_modeles = len(classement)
        if n_modeles >= 3:
            c1_statut = "VERT"
            c1_msg    = f"{n_modeles} modèles comparés ≥ 3 → Comparaison robuste ✅"
            c1_conseil= "Sélection basée sur une comparaison suffisante"
        elif n_modeles == 2:
            c1_statut = "AMBRE"
            c1_msg    = f"{n_modeles} modèles comparés — Comparaison limitée ⚠️"
            c1_conseil= "Ajouter au moins 1 modèle supplémentaire pour renforcer la sélection"
        else:
            c1_statut = "ROUGE"
            c1_msg    = f"{n_modeles} modèle(s) — Comparaison impossible ❌"
            c1_conseil= "Calibrer au moins 3 modèles avant la sélection"

        # C2 — Écart Gini entre modèles
        if classement and len(classement) >= 2:
            # Clé correcte : 'gini_test' (pas 'gini')
            ginis = [m.get('gini_test', m.get('gini', 0)) for m in classement]
            ecart_gini = max(ginis) - min(ginis)
            gini_max   = max(ginis)
            gini_min   = min(ginis)
        else:
            ecart_gini, gini_max, gini_min = 0, 0, 0

        if ecart_gini >= 0.02:
            c2_statut = "VERT"
            c2_msg    = f"Écart Gini = {ecart_gini:.4f} ≥ 2% → Modèles bien différenciés ✅"
            c2_conseil= "Le modèle retenu se distingue clairement des alternatives"
        elif ecart_gini >= 0.01:
            c2_statut = "VERT"
            c2_msg    = f"Écart Gini = {ecart_gini:.4f} ∈ [1%, 2%] → Différenciation acceptable ✅"
            c2_conseil= "Différence significative — critères de stabilité et interprétabilité décisifs"
        elif ecart_gini >= 0.005:
            c2_statut = "AMBRE"
            c2_msg    = f"Écart Gini = {ecart_gini:.4f} ∈ [0.5%, 1%] → Modèles proches ⚠️"
            c2_conseil= "Favoriser le modèle le plus stable et interprétable (ElasticNet, GLM)"
        else:
            c2_statut = "AMBRE"
            c2_msg    = f"Écart Gini = {ecart_gini:.4f} < 0.5% → Modèles quasi-équivalents"
            c2_conseil= "Utiliser le modèle le plus simple (ElasticNet ou GLM Tweedie)"

        # C3 — Cohérence modèle retenu
        if classement and modele_production:
            # modele_production peut être un dict ou une string
            if isinstance(modele_production, dict):
                nom_prod = modele_production.get('modele', '')
            else:
                nom_prod = str(modele_production)
            top3    = [m.get('modele', '') for m in classement[:3]]
            in_top3 = nom_prod in top3
            score_retenu = next(
                (m.get('score_global', 0) for m in classement
                 if m.get('modele') == nom_prod), 0
            )
            rang = next(
                (i+1 for i, m in enumerate(classement)
                 if m.get('modele') == nom_prod), 99
            )
        else:
            in_top3, score_retenu, rang = False, 0, 99

        if in_top3 and score_retenu >= 0.70:
            c3_statut = "VERT"
            c3_msg    = f"{nom_prod} rang #{rang} · Score = {score_retenu:.4f} ≥ 0.70 ✅"
            c3_conseil= f"Sélection cohérente — {nom_prod} est le meilleur compromis multicritères"
        elif in_top3:
            c3_statut = "AMBRE"
            c3_msg    = f"{nom_prod} dans le top 3 mais score = {score_retenu:.4f} < 0.70 ⚠️"
            c3_conseil= "Score limite — documenter les raisons du choix dans la fiche de décision"
        else:
            c3_statut = "ROUGE"
            c3_msg    = f"{nom_prod} hors top 3 (rang #{rang}) ❌"
            c3_conseil= "Revoir la sélection — le modèle retenu n'est pas le meilleur"

        statuts = [c1_statut, c2_statut, c3_statut]
        statut_global = "ROUGE" if "ROUGE" in statuts else "AMBRE" if "AMBRE" in statuts else "VERT"
        conclusion = {
            # ⚠️ `nom_prod`, PAS `modele_production` : le second est le DICT du
            # modèle (`classement[0]`), et l'interpoler publiait sa
            # représentation Python entière dans une phrase de conclusion.
            "VERT":  f"✅ Sélection validée — {nom_prod} retenu après comparaison rigoureuse",
            "AMBRE": f"⚠️ Sélection acceptable — documenter les précautions dans la fiche de décision",
            "ROUGE": f"❌ Sélection à revoir — contrôles non satisfaits",
        }[statut_global]

        return {
            "c1_nb_modeles": {
                "n_modeles": n_modeles,
                "statut":    c1_statut,
                "message":   c1_msg,
                "conseil":   c1_conseil,
                "titre_graphique": f"{'✅' if c1_statut=='VERT' else '⚠️' if c1_statut=='AMBRE' else '❌'} {n_modeles} modèles comparés",
            },
            "c2_ecart_gini": {
                "ecart":   round(ecart_gini, 4),
                "gini_max":round(gini_max, 4),
                "gini_min":round(gini_min, 4),
                "statut":  c2_statut,
                "message": c2_msg,
                "conseil": c2_conseil,
                # ⚠️⚠️ GLYPHE À TROIS ÉTATS, pris à la SOURCE UNIQUE — étape 2a de
                # l'arbitrage 2. L'expression était BINAIRE : `'✅' if VERT else '⚠️'`.
                # Un statut ROUGE affichait donc le glyphe de l'AMBRE, sur une figure
                # du plan du rapport SIGNÉ. *Le second canal existait, et il mentait.*
                "titre_graphique": (f"{glyphe_rag(c2_statut)} Écart Gini = "
                                    f"{ecart_gini:.4f}"),
            },
            "c3_coherence": {
                # ⚠️ LE NOM, PAS LE DICT — ET C'EST LA CAUSE DES TROIS AUTRES
                # DEFAUTS. Ce champ etait le dict entier de `classement[0]`,
                # alors que ses QUATRE lecteurs (tous dans le code des
                # figures) le comparent a une CHAINE : les comparaisons
                # etaient donc toujours fausses, et la barre doree du
                # graphique des scores — annoncee par son propre titre,
                # << Barre doree = modele retenu >> — n'apparaissait jamais.
                "modele":       nom_prod,
                "rang":         rang,
                "score":        round(score_retenu, 4),
                "in_top3":      in_top3,
                "statut":       c3_statut,
                "message":      c3_msg,
                "conseil":      c3_conseil,
                "titre_graphique": f"{'✅' if c3_statut=='VERT' else '⚠️' if c3_statut=='AMBRE' else '❌'} {nom_prod} — Rang #{rang} Score={score_retenu:.4f}",
            },
            "statut_global": statut_global,
            "conclusion":    conclusion,
        }

    def _graphiques_validation_selection(
        self,
        val_sel:    Dict,
        classement: list,
    ) -> Dict:
        """4 graphiques auto-explicatifs validation sélection multicritères."""
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

        # G1 — Scores multicritères par modèle
        try:
            modeles  = [m.get('modele', f'M{i}') for i, m in enumerate(classement)]
            scores   = [m.get('score_global', 0) for m in classement]
            modele_p = val_sel["c3_coherence"]["modele"]
            colors_s = [OR if m == modele_p else "rgba(52,152,219,0.6)" for m in modeles]
            statut_g = val_sel["statut_global"]
            # ⚠️ `couleur_g` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_g_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_g_txt = couleur_texte_rag(statut_g)

            fig1 = go.Figure(go.Bar(
                x=modeles, y=scores,
                marker_color=colors_s,
                marker_line=dict(color=NAVY, width=1),
                width=0.45, opacity=0.88,
                text=[f"{s:.4f}" for s in scores],
                textposition="outside",
                textfont=dict(color=BLANC, size=10),
                hovertemplate="<b>%{x}</b><br>Score : %{y:.4f}<extra></extra>",
            ))
            fig1.add_hline(y=0.70, line_color=AMBRE, line_width=1.5, line_dash="dot",
                          annotation_text="Seuil acceptable 0.70",
                          annotation_font=dict(color=AMBRE, size=9))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(
                    text=f"{glyphe_rag(statut_g)} Scores multicritères — Barre dorée = modèle retenu",
                    font=dict(color=couleur_g_txt, size=11), x=0.01
                ),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(visible=False), bargap=0.3, showlegend=False,
                annotations=[dict(
                    text="💡 Le score combine Gini, stabilité, interprétabilité et RMSE. Barre dorée = meilleur compromis.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig1.update_layout(**l1)
            graphiques["scores_multicriteres"] = fig1
        except Exception as e:
            logger.warning(f"G1 scores : {e}")

        # G2 — Gini par modèle avec écart
        try:
            ginis  = [m.get('gini_test', 0) for m in classement]
            colors_g = [OR if m.get('modele') == val_sel["c3_coherence"]["modele"]
                       else "rgba(52,152,219,0.6)" for m in classement]
            ecart  = val_sel["c2_ecart_gini"]["ecart"]
            statut_c2 = val_sel["c2_ecart_gini"]["statut"]
            # ⚠️ `couleur_c2` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_c2_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_c2_txt = couleur_texte_rag(statut_c2)

            fig2 = go.Figure(go.Bar(
                x=modeles, y=ginis,
                marker_color=colors_g,
                marker_line=dict(color=NAVY, width=1),
                width=0.45, opacity=0.88,
                text=[f"{g:.4f}" for g in ginis],
                textposition="outside",
                textfont=dict(color=BLANC, size=10),
                hovertemplate="<b>%{x}</b><br>Gini : %{y:.4f}<extra></extra>",
            ))
            # Annoter l'écart
            if ginis:
                fig2.add_annotation(
                    x=len(ginis)//2, y=max(ginis)*1.05,
                    text=f"Écart max-min = {ecart:.4f}",
                    font=dict(color=couleur_c2_txt, size=10),
                    showarrow=False,
                )
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(
                    text=val_sel["c2_ecart_gini"]["titre_graphique"] + " — Différenciation des modèles",
                    font=dict(color=couleur_c2_txt, size=11), x=0.01
                ),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(visible=False), bargap=0.3, showlegend=False,
                annotations=[dict(
                    text="💡 Un écart > 2% entre les modèles confirme que la sélection est pertinente.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig2.update_layout(**l2)
            graphiques["gini_comparaison"] = fig2
        except Exception as e:
            logger.warning(f"G2 Gini : {e}")

        # G3 — Radar multicritères pour le modèle retenu
        try:
            retenu = next((m for m in classement
                          if m.get('modele') == val_sel["c3_coherence"]["modele"]),
                         classement[0] if classement else {})
            categories = ["Gini", "Stabilité", "Interprét.", "RMSE", "Score global"]
            # ⚠️ TROIS AXES SUR CINQ LISAIENT UNE CLÉ ABSENTE, et affichaient
            # donc leur VALEUR PAR DÉFAUT : `gini` (le catalogue porte
            # `gini_test`) sortait 0, `stabilite` sortait 0,8 et `rmse_norm`
            # sortait 0,2 — deux constantes. Le radar « Profil du modèle
            # retenu » décrivait ainsi un modèle qui n'était pas celui-là.
            # `_calculer_scores_multicriteres` produit les cinq composantes
            # DÉJÀ normalisées dans [0,1] : ce sont elles que la grille
            # pondère, et donc elles que ce profil doit montrer.
            vals_radar = [
                retenu.get('score_gini', 0),
                retenu.get('score_stabilite', 0),
                retenu.get('score_interpretabilite', 0),
                retenu.get('score_rmse', 0),
                retenu.get('score_global', 0),
            ]
            vals_radar = [min(max(v, 0), 1) for v in vals_radar]

            fig3 = go.Figure(go.Scatterpolar(
                r=vals_radar + [vals_radar[0]],
                theta=categories + [categories[0]],
                fill="toself",
                fillcolor="rgba(201,168,76,0.12)",
                line=dict(color=OR, width=2.5),
                marker=dict(color=OR, size=7),
                hovertemplate="<b>%{theta}</b><br>Score : %{r:.3f}<extra></extra>",
            ))
            modele_nm = val_sel["c3_coherence"]["modele"]
            statut_c3 = val_sel["c3_coherence"]["statut"]
            # ⚠️ `couleur_c3` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_c3_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_c3_txt = couleur_texte_rag(statut_c3)
            fig3.update_layout(
                polar=dict(
                    bgcolor=NAVY_L,
                    radialaxis=dict(visible=True, range=[0,1],
                                  tickfont=dict(color=GRIS, size=8),
                                  gridcolor="rgba(255,255,255,0.07)"),
                    angularaxis=dict(tickfont=dict(color=BLANC, size=10),
                                    gridcolor="rgba(255,255,255,0.07)"),
                ),
                paper_bgcolor=NAVY, showlegend=False,
                title=dict(
                    text=f"{glyphe_rag(statut_c3)} Profil multicritères — {modele_nm}",
                    font=dict(color=couleur_c3_txt, size=11), x=0.01
                ),
                margin=dict(l=40, r=40, t=60, b=50), height=300,
                annotations=[dict(
                    text=f"💡 {val_sel['c3_coherence']['conseil']}",
                    xref="paper", yref="paper", x=0.5, y=-0.12,
                    font=dict(color=GRIS, size=9), showarrow=False, align="center"
                )],
            )
            graphiques["radar_modele_retenu"] = fig3
        except Exception as e:
            logger.warning(f"G3 radar : {e}")

        # G4 — Scorecard validation sélection
        try:
            items = [
                ("C1 — Nb modèles comparés", val_sel["c1_nb_modeles"]["statut"],
                 val_sel["c1_nb_modeles"]["message"], val_sel["c1_nb_modeles"]["conseil"]),
                ("C2 — Écart Gini significatif", val_sel["c2_ecart_gini"]["statut"],
                 val_sel["c2_ecart_gini"]["message"], val_sel["c2_ecart_gini"]["conseil"]),
                ("C3 — Cohérence sélection", val_sel["c3_coherence"]["statut"],
                 val_sel["c3_coherence"]["message"], val_sel["c3_coherence"]["conseil"]),
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
            statut_g  = val_sel["statut_global"]
            # ⚠️ `couleur_g` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_g_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_g_txt = couleur_texte_rag(statut_g)
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(
                    text=f"Scorecard Sélection — {val_sel['conclusion']}",
                    font=dict(color=couleur_g_txt, size=10), x=0.01
                ),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 3 ✅ = sélection validée, défendable devant l'actuaire désigné et l'ACPR.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig4.update_layout(**l4)
            graphiques["scorecard_selection"] = fig4
        except Exception as e:
            logger.warning(f"G4 scorecard : {e}")

        return graphiques

    def _erreur(self, message: str, audit_id: str) -> Dict:
        return {
            'success':           False,
            'dataframe':         pd.DataFrame(),
            'branche':           None,
            'statut_rag':        'ROUGE',
            'classement':        [],
            'modele_production': {},
            'backtest':          {},
            'courbes':           {},
            'rapport':           {},
            'commentaire':       f"❌ ERREUR A6 : {message}",
            'audit_id':          audit_id,
            'erreur':            message,
        }


if __name__ == '__main__':
    print("Agent A6 — Comparaison & Validation ActuarIA v1.0")
    print("Usage : %run 'chemin/a6_comparaison.py'")
    print("        agent_a6 = AgentA6Comparaison()")
    print("        result_a6 = agent_a6.run(result_a2, result_a3, result_a4, result_a5)")
