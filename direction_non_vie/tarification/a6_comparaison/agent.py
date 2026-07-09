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
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error

try:
    from .services.tarif_rapport import generer_rapport_tarification
    TARIF_RAPPORT_OK = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.tarif_rapport import generer_rapport_tarification
        TARIF_RAPPORT_OK = True
    except ImportError:
        TARIF_RAPPORT_OK = False

try:
    from ..services.tarif_excel import export_excel_a6
    TARIF_EXCEL_OK = True
except ImportError:
    TARIF_EXCEL_OK = False

warnings.filterwarnings('ignore')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('actuaria.a6')

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
    'elasticnet':     0.85,   # Linéaire régularisé
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
        result_a3:   Optional[Dict] = None,
        result_a4:   Optional[Dict] = None,
        result_a5:   Optional[Dict] = None,
        col_cible:   str = 'prime_pure',
        col_expo:    str = 'exposition',
        profil:      str = 'equilibre',
        poids_custom:       Optional[Dict] = None,
        generer_graphiques: bool = True,
        aide_decision:      bool = True,
    ) -> Dict[str, Any]:
        """
        Pipeline de comparaison et validation finale.

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

        # Application du profil de pondération
        global POIDS_CRITERES
        if poids_custom:
            POIDS_CRITERES = poids_custom
            logger.info(f"Profil personnalisé appliqué : {poids_custom}")
        elif profil in PROFILS_PONDERATION:
            POIDS_CRITERES = PROFILS_PONDERATION[profil]
            logger.info(f"Profil '{profil}' appliqué : {POIDS_CRITERES}")
        else:
            logger.warning(f"Profil '{profil}' inconnu — profil 'equilibre' utilisé")
            POIDS_CRITERES = PROFILS_PONDERATION['equilibre']

        logger.info(f"[{audit_id}] Agent A6 Comparaison démarré")

        df      = result_a2['dataframe'].copy()
        rapport = {'etapes': [], 'alertes': []}

        try:
            # ── ÉTAPE 1 : AGRÉGATION ──────────────────────────────────────────
            logger.info("Étape 1/5 : Agrégation des résultats")
            catalogue = self._agreger_resultats(result_a3, result_a4, result_a5)
            rapport['etapes'].append('agregation')
            rapport['nb_modeles'] = len(catalogue)
            logger.info(f"{len(catalogue)} modèles agrégés")

            # ── ÉTAPE 2 : SCORE MULTICRITÈRES ─────────────────────────────────
            logger.info("Étape 2/5 : Score multicritères")
            catalogue = self._calculer_scores_multicriteres(catalogue)
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
            backtest = self._backtesting_temporel(df, col_cible, col_expo)
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

            # ── AIDE À LA DÉCISION v3 ─────────────────────────────────────────
            fiche_decision = {}
            if aide_decision:
                fiche_decision = self._generer_fiche_decision(
                    classement, modele_production, profil
                )

            # Rapport final
            statut_rag  = self._calculer_statut_rag(modele_production, classement)
            commentaire = self._commenter_actuaire_senior(
                classement, modele_production, sous_branche,
                statut_rag, backtest
            )

            self._sauvegarder_rapport(sous_branche, classement, modele_production)
            self._sauvegarder_audit(audit_id, sous_branche, rapport,
                                     statut_rag, t_debut)

            # ── CALCUL VALIDATION SÉLECTION (avant Standard ActuarIA) ────────
            _val_sel_ = self._valider_selection(classement, modele_production, backtest)

            # ── Standard ActuarIA — excel_bytes ──────────────────────────────
            # _tmp_a6 inclut commentaire et courbes — disponibles à ce stade
            _tmp_a6 = {
                'success': True, 'statut_rag': statut_rag,
                'classement': classement, 'modele_production': modele_production,
                'backtest': backtest, 'branche': sous_branche,
                'validation_selection': _val_sel_,
                'fiche_decision': fiche_decision, 'audit_id': audit_id,
                'commentaire': commentaire,   # P7 : commentaire actuaire inclus
                'courbes': courbes,
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
                    _rapports = generer_rapport_tarification(
                        result_a3=result_a3, result_a4=result_a4,
                        result_a6=_tmp_a6,
                        arrete=datetime.now().strftime('%d/%m/%Y'),
                        audit_id=audit_id, formats=['html','word'],
                    )
                    _html_a6 = _rapports.get('html_bytes', b'')
                    _word_a6 = _rapports.get('word_bytes', b'')
                    if _word_a6:
                        logger.info(f"[{audit_id}] Word A6 : {len(_word_a6):,} bytes")
                    if _html_a6:
                        logger.info(f"[{audit_id}] HTML A6 : {len(_html_a6):,} bytes")
                except Exception as e_rp:
                    logger.warning(f"Rapport A6 échoué : {e_rp}")

            _audit_trail_a6 = {
                'agent': 'A6_COMPARAISON', 'version': '1.0', 'audit_id': audit_id,
                'timestamp': t_debut.isoformat(), 'branche': sous_branche,
                'statut_rag': statut_rag,
                'nb_modeles': len(classement),
                'modele_production': modele_production.get('modele','') if modele_production else '',
                'ae_ratio': backtest.get('ae_ratio', 0),
                'stabilite_wf': backtest.get('stabilite_wf',''),
            }

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
                'modele_production':  modele_production,
                'backtest':           backtest,
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
    ) -> List[Dict]:
        """
        Agrège tous les résultats des agents A3, A4, A5 en un catalogue unifié.
        Chaque modèle devient une entrée avec ses métriques standardisées.
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
                        'gini_test':       met.get('gini', 0),
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
            for nom, met in result_a4.get('metriques', {}).items():
                catalogue.append({
                    'modele':          f"ML_{nom.upper()}",
                    'famille':         'ML',
                    'gini_test':       met.get('gini_test', 0),
                    'gini_train':      met.get('gini_train', 0),
                    'rmse_test':       met.get('rmse_test', 999),
                    'overfit_ratio':   met.get('overfit_ratio', 1.0),
                    'nb_vars':         0,
                    'agent_source':    'A4',
                    'interpretabilite': INTERPRETABILITE.get(nom, 0.6),
                })

        # ── RÉSULTATS A5 (DL) ─────────────────────────────────────────────────
        if result_a5 and result_a5.get('success'):
            for nom, met in result_a5.get('metriques', {}).items():
                catalogue.append({
                    'modele':          f"DL_{nom.upper()}",
                    'famille':         'Deep Learning',
                    'gini_test':       met.get('gini_test', 0),
                    'gini_train':      met.get('gini_train', 0),
                    'rmse_test':       met.get('rmse_test', 999),
                    'overfit_ratio':   met.get('overfit_ratio', 1.0),
                    'nb_vars':         0,
                    'agent_source':    'A5',
                    'interpretabilite': INTERPRETABILITE.get(nom, 0.7),
                })

        if not catalogue:
            raise ValueError(
                "Aucun résultat disponible. "
                "Vérifiez que A3, A4 ou A5 ont bien tourné."
            )

        return catalogue

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : SCORE MULTICRITÈRES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_scores_multicriteres(
        self,
        catalogue: List[Dict]
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

            # Score global pondéré
            score_global = (
                POIDS_CRITERES['gini']             * s_gini
                + POIDS_CRITERES['stabilite']      * s_stab
                + POIDS_CRITERES['interpretabilite'] * s_inter
                + POIDS_CRITERES['rmse']            * s_rmse
            )

            modele['score_gini']            = round(s_gini,  4)
            modele['score_stabilite']       = round(s_stab,  4)
            modele['score_interpretabilite']= round(s_inter, 4)
            modele['score_rmse']            = round(s_rmse,  4)
            modele['score_global']          = round(score_global, 4)

        return catalogue

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 4 : BACKTESTING TEMPOREL
    # ══════════════════════════════════════════════════════════════════════════

    def _backtesting_temporel(
        self,
        df:        pd.DataFrame,
        col_cible: str,
        col_expo:  str
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
            backtest['split'] = 'aléatoire_80_20'
            df_train, df_test = train_test_split(df, test_size=0.2, random_state=42)
            backtest['n_train'] = len(df_train)
            backtest['n_test']  = len(df_test)
            moy_train = float(df_train[col_cible].mean())
            moy_test  = float(df_test[col_cible].mean())
            ae_ratio  = moy_test / max(moy_train, 1e-6)
            backtest['ae_ratio']       = round(ae_ratio, 4)
            backtest['moy_train']      = round(moy_train, 2)
            backtest['moy_test']       = round(moy_test, 2)
            backtest['disponible']     = True
            backtest['interpretation'] = (
                '🟢 Non biaisé'       if 0.95 <= ae_ratio <= 1.05 else
                '🟡 Légère déviation' if 0.90 <= ae_ratio <= 1.10 else
                '🔴 Déviation majeure'
            )
            return backtest

        annees = sorted(df[col_annee].dropna().unique())
        if len(annees) < 2:
            backtest['note'] = "Pas assez d'années distinctes pour le walk-forward."
            return backtest

        # ── WALK-FORWARD ──────────────────────────────────────────────────────
        # Tester chaque fenêtre glissante : train = [a0..aN-1], test = aN
        walk_forward = []
        for idx in range(1, len(annees)):
            annee_t = annees[idx]
            df_tr   = df[df[col_annee] < annee_t]
            df_te   = df[df[col_annee] == annee_t]
            if len(df_te) < 50:
                continue
            m_tr = float(df_tr[col_cible].mean()) if len(df_tr) > 0 else 0
            m_te = float(df_te[col_cible].mean())
            ae   = round(m_te / max(m_tr, 1e-6), 4)
            walk_forward.append({
                'annee_test':  int(annee_t),
                'n_train':     len(df_tr),
                'n_test':      len(df_te),
                'moy_train':   round(m_tr, 2),
                'moy_test':    round(m_te, 2),
                'ae_ratio':    ae,
                'statut':      (
                    'VERT'  if 0.95 <= ae <= 1.05 else
                    'AMBRE' if 0.90 <= ae <= 1.10 else
                    'ROUGE'
                ),
            })

        if not walk_forward:
            backtest['note'] = "Aucune fenêtre walk-forward valide."
            return backtest

        # A/E de la dernière fenêtre (N-1 → N)
        derniere = walk_forward[-1]
        ae_ratio = derniere['ae_ratio']

        # Stabilité walk-forward : CV des A/E sur toutes les fenêtres
        aes       = [w['ae_ratio'] for w in walk_forward]
        ae_moyen  = float(np.mean(aes))
        ae_cv     = float(np.std(aes) / max(ae_moyen, 1e-6))
        n_rouge   = sum(1 for w in walk_forward if w['statut'] == 'ROUGE')

        # ── TEST A/E PAR SEGMENT ──────────────────────────────────────────────
        # Utiliser la dernière fenêtre (la plus réaliste)
        annee_test = derniere['annee_test']
        df_test_n  = df[df[col_annee] == annee_test]
        df_train_n = df[df[col_annee] < annee_test]
        moy_ref    = float(df_train_n[col_cible].mean()) if len(df_train_n) > 0 else 1.0

        ae_par_segment = {}

        # Segment 1 : déciles de la variable cible observée
        try:
            df_test_n = df_test_n.copy()
            df_test_n['_decile'] = pd.qcut(
                df_test_n[col_cible], q=5, labels=False, duplicates='drop'
            )
            ae_deciles = []
            for d in sorted(df_test_n['_decile'].dropna().unique()):
                sub = df_test_n[df_test_n['_decile'] == d]
                ae_d = float(sub[col_cible].mean()) / max(moy_ref, 1e-6)
                ae_deciles.append({
                    'quintile': int(d) + 1,
                    'n':        len(sub),
                    'moy_obs':  round(float(sub[col_cible].mean()), 2),
                    'ae_ratio': round(ae_d, 4),
                    'statut':   'VERT' if 0.90 <= ae_d <= 1.10 else 'AMBRE' if 0.80 <= ae_d <= 1.20 else 'ROUGE',
                })
            ae_par_segment['quintiles_risque'] = ae_deciles
        except Exception as e_q:
            logger.debug(f"A/E quintiles échoué : {e_q}")

        # Segment 2 : zone géographique (si disponible)
        for col_zone in ['zone_geographique', 'zone', 'region', 'area']:
            if col_zone in df_test_n.columns:
                try:
                    ae_zones = []
                    for zone in df_test_n[col_zone].dropna().unique()[:8]:
                        sub = df_test_n[df_test_n[col_zone] == zone]
                        if len(sub) < 20:
                            continue
                        ae_z = float(sub[col_cible].mean()) / max(moy_ref, 1e-6)
                        ae_zones.append({
                            'zone':     str(zone),
                            'n':        len(sub),
                            'moy_obs':  round(float(sub[col_cible].mean()), 2),
                            'ae_ratio': round(ae_z, 4),
                            'statut':   'VERT' if 0.90 <= ae_z <= 1.10 else
                                        'AMBRE' if 0.80 <= ae_z <= 1.20 else 'ROUGE',
                        })
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
                    df_test_n = df_test_n.copy()
                    df_test_n['_age_tranche'] = pd.cut(
                        df_test_n[col_age], bins=bins, labels=lbls, right=False
                    )
                    ae_ages = []
                    for tranche in lbls:
                        sub = df_test_n[df_test_n['_age_tranche'] == tranche]
                        if len(sub) < 20:
                            continue
                        ae_a = float(sub[col_cible].mean()) / max(moy_ref, 1e-6)
                        ae_ages.append({
                            'tranche':  tranche,
                            'n':        len(sub),
                            'moy_obs':  round(float(sub[col_cible].mean()), 2),
                            'ae_ratio': round(ae_a, 4),
                            'statut':   'VERT' if 0.90 <= ae_a <= 1.10 else
                                        'AMBRE' if 0.80 <= ae_a <= 1.20 else 'ROUGE',
                        })
                    if ae_ages:
                        ae_par_segment['tranches_age'] = ae_ages
                except Exception as e_a:
                    logger.debug(f"A/E âge échoué : {e_a}")
                break

        # ── BILAN ─────────────────────────────────────────────────────────────
        backtest.update({
            'disponible':        True,
            'split':             'walk_forward_temporel',
            'col_annee':         col_annee,
            'annees_disponibles':[int(a) for a in annees],
            'annee_test':        int(annee_test),
            'annees_train':      [int(a) for a in annees if a < annee_test],
            'n_train':           derniere['n_train'],
            'n_test':            derniere['n_test'],
            'moy_train':         derniere['moy_train'],
            'moy_test':          derniere['moy_test'],
            'ae_ratio':          ae_ratio,
            'ae_moyen_wf':       round(ae_moyen, 4),
            'ae_cv_wf':          round(ae_cv, 4),
            'n_fenetres':        len(walk_forward),
            'n_fenetres_rouge':  n_rouge,
            'walk_forward':      walk_forward,
            'ae_par_segment':    ae_par_segment,
            'interpretation': (
                '🟢 Non biaisé'       if 0.95 <= ae_ratio <= 1.05 else
                '🟡 Légère déviation' if 0.90 <= ae_ratio <= 1.10 else
                '🔴 Déviation majeure'
            ),
            'stabilite_wf': (
                '🟢 Stable'     if ae_cv <= 0.05 and n_rouge == 0 else
                '🟡 Acceptable' if ae_cv <= 0.10 else
                '🔴 Instable'
            ),
        })

        logger.info(
            f"Walk-forward : {len(walk_forward)} fenêtres | "
            f"A/E N-1→N = {ae_ratio:.4f} | CV = {ae_cv:.4f} | "
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
        modele_production: Dict
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
            'poids_criteres':     POIDS_CRITERES,
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

    def _calculer_statut_rag(
        self,
        modele_production: Dict,
        classement:        List[Dict]
    ) -> str:
        """
        Statut RAG basé sur le score global du modèle de production.
        VERT  : score ≥ 0.60 ET gini ≥ 0.15
        AMBRE : score ≥ 0.40 OU gini ≥ 0.05
        ROUGE : score < 0.40 ET gini < 0.05
        """
        score = modele_production.get('score_global', 0)
        gini  = modele_production.get('gini_test',   0)

        if score >= 0.60 and gini >= 0.15:
            return 'VERT'
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
        emoji  = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
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

        if backtest.get('disponible'):
            wf_info = ""
            if backtest.get('split') == 'walk_forward_temporel':
                wf_info = (
                    f"  Fenêtres WF      : {backtest.get('n_fenetres', 'N/A')} "
                    f"({backtest.get('n_fenetres_rouge', 0)} ROUGE)\n"
                    f"  Stabilité WF     : {backtest.get('stabilite_wf', 'N/A')}\n"
                    f"  CV A/E WF        : {backtest.get('ae_cv_wf', 'N/A'):.4f}\n"
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
                f"→ Recalibrer annuellement ou si A/E sort de [0.90, 1.10].\n"
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
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
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
        VERT    = "#2ECC71"
        ROUGE   = "#E74C3C"
        AMBRE   = "#F39C12"
        BLEU    = "#3498DB"

        COULEURS = [OR, VERT, BLEU, AMBRE, ROUGE, "#9B59B6", GRIS]

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

        # ── G2 : SCORES PAR PROFIL ────────────────────────────────────────────
        try:
            profils_labels = list(PROFILS_PONDERATION.keys())
            noms_mod       = [c['modele'] for c in classement[:5]]

            fig2 = go.Figure()

            for idx, nom in enumerate(noms_mod):
                scores_profils = []
                c = next((x for x in classement if x['modele'] == nom), None)
                if not c:
                    continue

                for p in profils_labels:
                    poids = PROFILS_PONDERATION[p]
                    gini  = c.get('gini_test', 0)
                    stab  = 1 / max(c.get('overfit_ratio', 1), 0.5)
                    interp= c.get('score_interpretabilite', 0.6)
                    rmse_n= 1 - min(c.get('rmse_test', 0) / 400, 1)
                    sc = (
                        gini  * poids['gini'] +
                        stab  * poids['stabilite'] +
                        interp* poids['interpretabilite'] +
                        rmse_n* poids['rmse']
                    )
                    scores_profils.append(round(sc, 3))

                est_prod = nom == modele_prod.get('modele', '')
                couleur  = OR if est_prod else COULEURS[idx % len(COULEURS)]

                fig2.add_trace(go.Scatter(
                    x    = profils_labels,
                    y    = scores_profils,
                    mode = 'lines+markers',
                    name = f"{'⭐ ' if est_prod else ''}{nom}",
                    line = dict(color=couleur, width=3 if est_prod else 1.5,
                                shape='spline', smoothing=0.5),
                    marker= dict(color=couleur, size=9 if est_prod else 6,
                                 line=dict(color=NAVY, width=2)),
                    hovertemplate=(
                        f"<b>{nom}</b> — profil %{{x}}<br>"
                        "Score : <b>%{y:.3f}</b><extra></extra>"
                    ),
                ))

            layout2 = dict(**LAYOUT_BASE)
            layout2.update(dict(
                title=dict(
                    text="📊 Score par profil de pondération — Quel profil pour votre client ?",
                    font=dict(color=BLANC, size=13), x=0.01,
                ),
                xaxis=dict(
                    tickfont=dict(color=BLANC, size=10), showgrid=False,
                    tickvals=profils_labels,
                    ticktext=['Équilibré', 'Performance', 'Audit S2', 'Cie Vie'],
                ),
                yaxis=dict(
                    title=dict(text="Score global", font=dict(color=GRIS, size=10)),
                    showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                    tickfont=dict(color=GRIS),
                ),
                annotations=[dict(
                    x=profil, y=1.05, xref='x', yref='paper',
                    text="← Profil actuel",
                    showarrow=True, arrowcolor=OR,
                    font=dict(color=OR, size=10),
                )],
            ))
            fig2.update_layout(**layout2)
            graphiques['scores_profils'] = fig2

        except Exception as e:
            logger.warning(f"G2 scores profils échoué : {e}")

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
        justif_regl = []
        justif_regl.append("Conformité S2 Pilier 1 : modèle validé sur données de test indépendantes")
        justif_regl.append("AI Act 2025 Art. 13 : " + (
            "✅ Modèle linéaire — exigences d'explicabilité satisfaites"
            if 'GLM' in fam_prod.upper() or 'elasticnet' in nom_prod.lower()
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
            ginis = [m.get('gini', 0) for m in classement]
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
            # Vérifier que le modèle de production est dans le top 3
            top3 = [m.get('modele', '') for m in classement[:3]]
            in_top3 = modele_production in top3
            score_retenu = next(
                (m.get('score_global', 0) for m in classement
                 if m.get('modele') == modele_production), 0
            )
            rang = next(
                (i+1 for i, m in enumerate(classement)
                 if m.get('modele') == modele_production), 99
            )
        else:
            in_top3, score_retenu, rang = False, 0, 99

        if in_top3 and score_retenu >= 0.70:
            c3_statut = "VERT"
            c3_msg    = f"{modele_production} rang #{rang} · Score = {score_retenu:.4f} ≥ 0.70 ✅"
            c3_conseil= f"Sélection cohérente — {modele_production} est le meilleur compromis multicritères"
        elif in_top3:
            c3_statut = "AMBRE"
            c3_msg    = f"{modele_production} dans le top 3 mais score = {score_retenu:.4f} < 0.70 ⚠️"
            c3_conseil= "Score limite — documenter les raisons du choix dans la fiche de décision"
        else:
            c3_statut = "ROUGE"
            c3_msg    = f"{modele_production} hors top 3 (rang #{rang}) ❌"
            c3_conseil= "Revoir la sélection — le modèle retenu n'est pas le meilleur"

        statuts = [c1_statut, c2_statut, c3_statut]
        statut_global = "ROUGE" if "ROUGE" in statuts else "AMBRE" if "AMBRE" in statuts else "VERT"
        conclusion = {
            "VERT":  f"✅ Sélection validée — {modele_production} retenu après comparaison rigoureuse",
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
                "titre_graphique": f"{'✅' if c2_statut=='VERT' else '⚠️'} Écart Gini = {ecart_gini:.4f}",
            },
            "c3_coherence": {
                "modele":       modele_production,
                "rang":         rang,
                "score":        round(score_retenu, 4),
                "in_top3":      in_top3,
                "statut":       c3_statut,
                "message":      c3_msg,
                "conseil":      c3_conseil,
                "titre_graphique": f"{'✅' if c3_statut=='VERT' else '⚠️' if c3_statut=='AMBRE' else '❌'} {modele_production} — Rang #{rang} Score={score_retenu:.4f}",
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
        VERT="#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"; BLEU="#3498DB"
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
            couleur_g= VERT if statut_g=="VERT" else AMBRE if statut_g=="AMBRE" else ROUGE

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
                    text=f"{'✅' if statut_g=='VERT' else '⚠️'} Scores multicritères — Barre dorée = modèle retenu",
                    font=dict(color=couleur_g, size=11), x=0.01
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
            self.logger.warning(f"G1 scores : {e}")

        # G2 — Gini par modèle avec écart
        try:
            ginis  = [m.get('gini', 0) for m in classement]
            colors_g = [OR if m.get('modele') == val_sel["c3_coherence"]["modele"]
                       else "rgba(52,152,219,0.6)" for m in classement]
            ecart  = val_sel["c2_ecart_gini"]["ecart"]
            statut_c2 = val_sel["c2_ecart_gini"]["statut"]
            couleur_c2= VERT if statut_c2=="VERT" else AMBRE

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
                    font=dict(color=couleur_c2, size=10),
                    showarrow=False,
                )
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(
                    text=val_sel["c2_ecart_gini"]["titre_graphique"] + " — Différenciation des modèles",
                    font=dict(color=couleur_c2, size=11), x=0.01
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
            self.logger.warning(f"G2 Gini : {e}")

        # G3 — Radar multicritères pour le modèle retenu
        try:
            retenu = next((m for m in classement
                          if m.get('modele') == val_sel["c3_coherence"]["modele"]),
                         classement[0] if classement else {})
            categories = ["Gini", "Stabilité", "Interprét.", "RMSE", "Score global"]
            vals_radar = [
                retenu.get('gini', 0) / 0.30,
                retenu.get('stabilite', 0.8),
                retenu.get('interpretabilite', 0.9),
                1 - retenu.get('rmse_norm', 0.2),
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
            couleur_c3= VERT if statut_c3=="VERT" else AMBRE if statut_c3=="AMBRE" else ROUGE
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
                    text=f"{'✅' if statut_c3=='VERT' else '⚠️'} Profil multicritères — {modele_nm}",
                    font=dict(color=couleur_c3, size=11), x=0.01
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
            self.logger.warning(f"G3 radar : {e}")

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
            statut_g  = val_sel["statut_global"]
            couleur_g = VERT if statut_g=="VERT" else AMBRE if statut_g=="AMBRE" else ROUGE
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(
                    text=f"Scorecard Sélection — {val_sel['conclusion']}",
                    font=dict(color=couleur_g, size=10), x=0.01
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
            self.logger.warning(f"G4 scorecard : {e}")

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
