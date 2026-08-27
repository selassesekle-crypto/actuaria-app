"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                ACTUARIA — AGENT A3 : TARIFICATION GLM                       ║
║                        Version 1.0 — Production                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE DE CET AGENT                                                           ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  L'agent A3 calibre les modèles GLM actuariels de tarification.             ║
║                                                                              ║
║  MODÈLES CALIBRÉS :                                                          ║
║                                                                              ║
║  1. GLM POISSON — Modèle de fréquence                                        ║
║     E[nb_sinistres] = exposition × exp(X'β)                                 ║
║     Distribution : Poisson                                                   ║
║     Lien : logarithmique                                                     ║
║     Offset : log(exposition) — indispensable pour les contrats partiels     ║
║                                                                              ║
║  2. GLM GAMMA — Modèle de coût moyen                                         ║
║     E[coût | sinistre > 0] = exp(X'β)                                       ║
║     Distribution : Gamma (coûts positifs asymétriques)                      ║
║     Lien : logarithmique                                                     ║
║     Calibré UNIQUEMENT sur les contrats avec sinistres                       ║
║                                                                              ║
║  3. GLM TWEEDIE — Modèle de prime pure directe                               ║
║     E[prime_pure] = exp(X'β)                                                ║
║     Distribution : Tweedie (p ≈ 1.5)                                        ║
║     Modélise fréquence × coût en un seul modèle                             ║
║                                                                              ║
║  PRIME PURE = Fréquence (Poisson) × Coût moyen (Gamma)                      ║
║                                                                              ║
║  MÉTRIQUES DE VALIDATION :                                                   ║
║  • Déviance de Poisson / Gamma / Tweedie                                    ║
║  • AIC / BIC (critères de sélection de modèle)                              ║
║  • Résidus de Pearson (détection hétéroscédasticité)                        ║
║  • Coefficient de Gini (pouvoir discriminant)                                ║
║  • Test de surparamétrage                                                    ║
║                                                                              ║
║  AUTONOMIE : Niveau 2                                                        ║
║  L'agent sélectionne automatiquement les variables significatives           ║
║  (p-value < 0.05), justifie chaque choix et alerte si les hypothèses       ║
║  du GLM ne sont pas vérifiées.                                              ║
║                                                                              ║
║  USAGE DANS GOOGLE COLAB                                                     ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  %run '/tmp/actuaria/agents/a3_glm.py'                    ║
║  agent_a3 = AgentA3GLM()                                                    ║
║  result_a3 = agent_a3.run(result_a2)                                        ║
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
    from core.charts_tarif import (
        chart_relativites_glm, chart_residus_qq, chart_distribution_predictions)
    _CHARTS_V3_OK = True
except Exception:
    _CHARTS_V3_OK = False

# Statsmodels — bibliothèque de référence pour les GLM actuariels
# Justification : statsmodels implémente les GLM selon la théorie statistique
# classique (famille exponentielle, fonction de lien, déviance).
# C'est la bibliothèque utilisée par les actuaires en production.
try:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    from statsmodels.genmod.generalized_linear_model import GLM
    from statsmodels.genmod import families
    STATSMODELS_OK = True
except ImportError:
    STATSMODELS_OK = False
    print("⚠️  statsmodels non installé. Installation : pip install statsmodels")

# Sklearn pour les métriques complémentaires
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.neighbors import BallTree

try:
    from ..services.tarif_excel import export_excel_a3
    TARIF_EXCEL_OK = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.tarif_excel import export_excel_a3
        TARIF_EXCEL_OK = True
    except ImportError:
        TARIF_EXCEL_OK = False

# Module de conformité PLATEFORME — source unique pour les trois directions.
# ⚠ A3 utilisait auparavant la seule constante COLS_GENRE_INTERDITES avec un
# test d'appartenance strict (v not in COLS_GENRE_INTERDITES). Il ne
# bénéficiait donc PAS de l'élargissement du filtre (audit V9 : racines,
# insensibilité à la casse, colonnes filles du one-hot, proxy civilité) —
# une colonne 'sexe_M' pré-encodée par le client, 'Sexe', 'sex' ou
# 'civilite' entrait dans le GLM. A3 appelle désormais filtrer_genre(),
# comme A2/A4/A5/A6 : une seule implémentation, pour tous.
from core.conformite_reglementaire import (
    BASE_GINI_COMPTAGE, BASE_GINI_COUT_MOYEN, BASE_GINI_UNITAIRE,
    construire_matrice_x,
)
from core.plan_tarifaire import (
    PlanTarifaire, verifier_completude_plan, plafonner_statut_si_ampute,
    alerte_modele_ampute,
)
from core.severite import construire_cible_severite

warnings.filterwarnings('ignore')

# ── LOGGER ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('actuaria.a3')


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Variables à exclure de la modélisation GLM
# Ces colonnes sont des identifiants, des cibles ou des variables dérivées
# qui ne doivent pas entrer comme prédicteurs
COLS_A_EXCLURE = [
    # Identifiants
    'id_contrat', 'id_assure', 'id_salarie', 'id_beneficiaire', 'id_adherent',
    # Dates
    'date_souscription', 'date_survenance', 'date_mouvement', 'date_evaluation',
    'annee_souscription',
    # Variables cibles (ne pas utiliser comme prédicteurs !)
    'nb_sinistres', 'cout_total_sinistres', 'prime_pure', 'prime_commerciale',
    'lambda_freq_annuel', 'cout_moyen_attendu',
    # Variables d'exposition (utilisées comme offset, pas comme prédicteur)
    'exposition', 'log_exposition',
    # Autres variables de tarification
    'prime_pure_annuelle', 'cotisation_annuelle', 'cotisation_mensuelle_eur',
    'charge_annuelle_eur', 'charge_ij_annuelle_eur',
]

# COLS_GENRE_INTERDITES est désormais importée du module partagé
# core/conformite_reglementaire.py (audit V7 BLOQUANT #1) — la même
# liste est maintenant utilisée par A4 et A5, qui n'avaient auparavant
# AUCUN filtre genre (fuite confirmée par exécution lors de l'audit V7 :
# une colonne genre numérique atteignait la matrice de features des
# modèles ML/DL, potentiellement retenus en production par A6).

# Seuil de significativité pour la sélection des variables
# Justification : seuil classique en statistique (α = 5%)
# Un coefficient avec p-value > 0.05 n'est pas significativement
# différent de zéro et ne doit pas rester dans le modèle final
SEUIL_PVALUE = 0.05

# Paramètre p de la distribution Tweedie
# p ∈ (1, 2) → distribution Tweedie (composée Poisson-Gamma)
# p = 1.5 est le choix standard en tarification Non-Vie
# Justification : p=1.5 correspond à une sinistralité modérément asymétrique,
# cohérente avec les distributions observées en assurance auto/MRH française
TWEEDIE_P = 1.5

# Proportion train/test pour la validation
# 80/20 est le standard en data science actuarielle
# Justification : 56 000 contrats en train suffisent pour calibrer
# un GLM robuste, 14 000 en test permettent une validation fiable
TRAIN_SIZE = 0.80

# Variables prédictives GLM (Phase 1) : plus de liste codée en dur ni de
# dérivation au chargement du module. A3.run() reçoit le PLAN signé
# (PlanTarifaire) et dérive ses variables candidates de plan.colonnes_produites()
# À LA VOLÉE. Plan absent/corrompu → erreur propre (voir run()), jamais de repli.

# TODO (ticket en attente, hors cycle) : quand un fichier client n'a pas la source
# brute d'une dérivée (kilometrage_annuel, valeur_mobilier, annee_construction…),
# valider_contre() signale la colonne DÉRIVÉE (km_par_an_normalise, valeur_par_m2,
# age_logement) plutôt que la source brute. Actionnable en forme, imprécis sur la
# source. À affiner séparément.


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE : AGENT A3 GLM
# ══════════════════════════════════════════════════════════════════════════════

class AgentA3GLM:
    """
    Agent A3 — Tarification GLM actuarielle.

    Calibre les 3 modèles GLM de référence :
    • GLM Poisson  : modèle de fréquence
    • GLM Gamma    : modèle de coût moyen
    • GLM Tweedie  : modèle de prime pure directe

    AUTONOMIE NIVEAU 2 :
    L'agent sélectionne automatiquement les variables significatives,
    justifie chaque choix et commente les résultats comme un actuaire
    sénior le ferait dans un rapport de tarification.

    EXEMPLE D'UTILISATION :
    ─────────────────────────
    agent_a3 = AgentA3GLM(
        models_path = '/tmp/actuaria',
        audit_path  = '/tmp/actuaria',
    )
    result_a3 = agent_a3.run(result_a2)

    # Accès aux modèles calibrés
    modele_freq  = result_a3['modeles']['poisson']
    modele_cout  = result_a3['modeles']['gamma']
    prime_pure   = result_a3['predictions']['prime_pure']
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

        # Stockage des modèles calibrés
        self.modeles     = {}
        self.metriques   = {}
        self.predictions = {}

        if self.verbose:
            logger.info("Agent A3 GLM Tarification initialisé")

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTHODE PRINCIPALE : run()
    # ══════════════════════════════════════════════════════════════════════════

    def run(
        self,
        result_a2:          Dict[str, Any],
        col_frequence:      str = 'nb_sinistres',
        col_cout:           str = 'cout_total_sinistres',
        col_exposition:     str = 'exposition',
        plan:               Optional[PlanTarifaire] = None,   # Phase 1 : plan signé explicite
        generer_graphiques: bool = True,
    ) -> Dict[str, Any]:
        """
        Pipeline GLM complet.

        ÉTAPES :
        1. Préparation des données (train/test split)
        2. Sélection des variables prédictives
        3. Calibration GLM Poisson (fréquence)
        4. Calibration GLM Gamma (coût moyen)
        5. Calibration GLM Tweedie (prime pure)
        6. Calcul des prédictions et prime pure
        7. Calcul des métriques de validation
        8. Génération du rapport et commentaires
        9. Sauvegarde des modèles
        """
        t_debut      = datetime.now()
        audit_id     = f"A3_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        sous_branche = result_a2.get('branche', 'inconnue')

        logger.info(f"[{audit_id}] Agent A3 GLM démarré | branche={sous_branche}")

        if not result_a2.get('success', False):
            return self._erreur("L'agent A2 a échoué.", audit_id)

        # Phase 1 : A3 dérive ses variables du PLAN signé — plus de VARS_GLM codé.
        # Plan absent/corrompu → erreur propre, JAMAIS de repli silencieux (le
        # repli réintroduirait la désynchronisation liste/plan que le refactor a tuée).
        if plan is None:
            return self._erreur(
                "A3.run exige un plan (PlanTarifaire) : les variables GLM sont "
                "dérivées de plan.colonnes_produites() (Phase 1, VARS_GLM supprimé). "
                "Fournissez plan=PlanTarifaire.depuis_yaml('plans/<lob>.yaml').", audit_id)

        if not STATSMODELS_OK:
            return self._erreur(
                "statsmodels non installé. "
                "Exécutez : !pip install statsmodels", audit_id
            )

        df           = result_a2['dataframe'].copy()
        rapport      = {'etapes': [], 'alertes': [], 'variables': {}}

        try:
            # ── ÉTAPE 1 : PRÉPARATION ─────────────────────────────────────────
            logger.info(f"[{audit_id}] Étape 1/7 : Préparation données")
            df_train, df_test, vars_pred = self._preparer_donnees(
                df, sous_branche, col_frequence, col_cout, col_exposition, plan
            )
            rapport['etapes'].append('preparation')
            rapport['variables']['predictives'] = vars_pred
            rapport['variables']['nb_vars']     = len(vars_pred)

            logger.info(
                f"Train : {len(df_train):,} | Test : {len(df_test):,} | "
                f"Variables : {len(vars_pred)}"
            )

            # ── ÉTAPE 2 : GLM POISSON (FRÉQUENCE) ────────────────────────────
            logger.info(f"[{audit_id}] Étape 2/7 : GLM Poisson (fréquence)")
            res_poisson = self._calibrer_poisson(
                df_train, df_test, vars_pred,
                col_frequence, col_exposition
            )
            self.modeles['poisson']     = res_poisson['modele']
            self.metriques['poisson']   = res_poisson['metriques']
            # CONTRAT GLM -> CIBLE (source unique, reutilisee par A6 pour ne
            # comparer QUE des modeles ajustes sur la MEME cible) : Poisson =
            # FREQUENCE (col_frequence, venue du plan), Gamma = SEVERITE (cout
            # moyen par sinistre), Tweedie = PRIME PURE directe. Chaque agent
            # DECLARE la cible de ses modeles dans sa sortie ; A6 ne redefinit rien.
            self.metriques['poisson']['cible'] = col_frequence
            rapport['etapes'].append('glm_poisson')
            logger.info(
                f"Poisson | AIC={res_poisson['metriques']['aic']:.1f} | "
                f"Vars retenues={res_poisson['metriques']['nb_vars_retenues']}"
            )

            # ── ÉTAPE 3 : GLM GAMMA (COÛT MOYEN) ─────────────────────────────
            logger.info(f"[{audit_id}] Étape 3/7 : GLM Gamma (coût moyen)")
            res_gamma = self._calibrer_gamma(
                df_train, df_test, vars_pred, col_cout,
                col_frequence, col_exposition
            )
            self.modeles['gamma']   = res_gamma['modele']
            self.metriques['gamma'] = res_gamma['metriques']
            self.metriques['gamma']['cible'] = 'cout_moyen'   # severite (cout par sinistre)
            rapport['etapes'].append('glm_gamma')
            logger.info(
                f"Gamma | AIC={res_gamma['metriques']['aic']:.1f} | "
                f"Vars retenues={res_gamma['metriques']['nb_vars_retenues']}"
            )

            # ── ÉTAPE 4 : GLM TWEEDIE (PRIME PURE) ───────────────────────────
            logger.info(f"[{audit_id}] Étape 4/7 : GLM Tweedie (prime pure)")
            res_tweedie = self._calibrer_tweedie(
                df_train, df_test, vars_pred,
                col_frequence, col_cout, col_exposition
            )
            self.modeles['tweedie']   = res_tweedie['modele']
            self.metriques['tweedie'] = res_tweedie['metriques']
            self.metriques['tweedie']['cible'] = 'prime_pure'   # prime pure directe
            rapport['etapes'].append('glm_tweedie')

            # ── ÉTAPE 5 : PRÉDICTIONS ─────────────────────────────────────────
            logger.info(f"[{audit_id}] Étape 5/7 : Calcul prédictions")
            self.predictions = self._calculer_predictions(
                df, vars_pred, col_exposition
            )
            rapport['etapes'].append('predictions')

            # ── ÉTAPE 5bis : CRÉDIBILITÉ BÜHLMANN-STRAUB ─────────────────────
            # Activée automatiquement si une colonne de groupe est détectée
            # (id_flotte, id_entreprise, id_assure) ET que plusieurs périodes
            # sont présentes. Sinon, résultat vide documenté.
            # Réf. : Bühlmann & Straub (1970) ASTIN Bulletin 5(2)
            credibilite = self._credibilite_buhlmann_straub(
                df, self.predictions, col_frequence, col_exposition
            )
            rapport['etapes'].append(
                'credibilite_buhlmann_straub'
                if credibilite.get('appliquee') else
                'credibilite_non_applicable'
            )
            if credibilite.get('appliquee'):
                logger.info(
                    f"[{audit_id}] Crédibilité B-S : "
                    f"k={credibilite['k']:.3f} | "
                    f"Z_moyen={credibilite['z_moyen']:.3f} | "
                    f"n_groupes={credibilite['n_groupes']}"
                )
            else:
                logger.info(
                    f"[{audit_id}] Crédibilité B-S non applicable : "
                    f"{credibilite.get('raison','colonne groupe absente')}"
                )

            # ── ÉTAPE 5ter : LISSAGE GÉOGRAPHIQUE ────────────────────────────
            # Lissage des primes par zone géographique pour corriger les
            # effets de faible exposition (cellules avec peu d'observations).
            # Sur données réelles avec GPS/IRIS → krigeage complet.
            # Sur données synthétiques → lissage par voisinage catégoriel.
            # Réf. : Gelfand et al. (2010) Handbook of Spatial Statistics
            lissage_geo = self._lissage_geographique(
                df, self.predictions, col_exposition,
                col_freq=col_frequence,
            )
            rapport['etapes'].append(
                'lissage_geographique'
                if lissage_geo.get('applique') else
                'lissage_geo_non_applicable'
            )
            if lissage_geo.get('applique'):
                logger.info(
                    f"[{audit_id}] Lissage géographique : "
                    f"col='{lissage_geo['col_geo']}' | "
                    f"n_zones={lissage_geo['n_zones']} | "
                    f"methode={lissage_geo['methode']}"
                )

            # ── ÉTAPE 6 : MÉTRIQUES GLOBALES ─────────────────────────────────
            logger.info(f"[{audit_id}] Étape 6/7 : Métriques de validation")
            metriques_glob = self._calculer_metriques_globales(
                df_test, vars_pred, col_frequence, col_cout, col_exposition
            )
            rapport['metriques_globales'] = metriques_glob
            rapport['etapes'].append('metriques')

            # ── ÉTAPE 7 : RAPPORT ─────────────────────────────────────────────
            logger.info(f"[{audit_id}] Rapport")

            # Graphiques v2
            graphiques = {}
            if generer_graphiques and PLOTLY_OK:
                graphiques = self._generer_graphiques(
                    df_train, df_test, vars_pred,
                    res_poisson, res_gamma, res_tweedie,
                    col_frequence, col_cout, col_exposition
                )
            # Graphiques V3 (charte partagée) — ajoutés au même dict, OPTIONNELS.
            if generer_graphiques and PLOTLY_OK and _CHARTS_V3_OK:
                self._charts_tarif_v3(graphiques, res_poisson)

            statut_rag  = self._calculer_statut_rag(metriques_glob)

            # ── MODÈLE AMPUTÉ → PLAFOND AMBRE ─────────────────────────────────
            # Le plan DÉCLARE ce qui est nécessaire ; si les données ne portent
            # pas une de ses colonnes, le GLM est calibré SANS ce facteur. On
            # PLAFONNE (jamais on ne bloque), comme le garde-fou DL. Comparaison
            # sur df.columns (disponibilité en DONNÉES) et non sur vars_pred
            # post-garde-fous : une colonne écartée par le filtre genre/fuite,
            # c'est le contrôle qui FONCTIONNE (INV-3/INV-4), pas une amputation.
            _ampute = verifier_completude_plan(plan, df.columns)
            _alertes_modele = []
            _al = alerte_modele_ampute(_ampute, 'GLM')
            if _al:
                _alertes_modele.append(_al)
                logger.warning("[PLAN INCOMPLET] %s", _al['message'])
            statut_rag = plafonner_statut_si_ampute(statut_rag, _ampute)

            commentaire = self._commenter_actuaire_senior(
                rapport, sous_branche, statut_rag,
                res_poisson, res_gamma, res_tweedie,
                df_train, df_test
            )

            # Sauvegarde
            self._sauvegarder_modeles(sous_branche)
            self._sauvegarder_audit(
                audit_id, sous_branche, rapport,
                statut_rag, t_debut
            )

            if self.verbose:
                self._afficher_rapport_console(
                    audit_id, sous_branche, rapport,
                    statut_rag, commentaire,
                    res_poisson, res_gamma
                )

            # ── CALCUL VALIDATION GLM ─────────────────────────────────────────
            _val_glm_ = self._valider_hypotheses_glm(
                df_train,
                self.predictions,
                self.metriques,
            )
            _gv_glm_ = self._graphiques_validation_glm(
                _val_glm_,
                self.metriques,
            ) if generer_graphiques else {}

            # Extraire les relativités Poisson pour exposition facile en aval
            relativites_poisson = res_poisson.get('relativites', {})
            relativites_gamma   = res_gamma.get('relativites',   {})

            # ── Standard ActuarIA — excel_bytes + audit_trail ────────────────
            _tmp = {
                'success': True, 'statut_rag': statut_rag,
                'metriques': self.metriques, 'branche': sous_branche,
                'relativites_poisson': relativites_poisson,
                'relativites_gamma':   relativites_gamma,
                'validation_glm': _val_glm_, 'audit_id': audit_id,
            }
            excel_bytes = b''
            if TARIF_EXCEL_OK:
                try:
                    excel_bytes = export_excel_a3(_tmp, audit_id)
                    if excel_bytes:
                        logger.info(f"[{audit_id}] Excel A3 : {len(excel_bytes):,} bytes")
                except Exception as e_xl:
                    logger.warning(f"Excel A3 échoué : {e_xl}")

            audit_trail_a3 = {
                'agent': 'A3_GLM', 'version': '1.0', 'audit_id': audit_id,
                'timestamp': t_debut.isoformat(), 'branche': sous_branche,
                'statut_rag': statut_rag,
                'nb_obs_train': res_poisson.get('metriques',{}).get('nb_obs_train', 0),
                'nb_obs_test':  res_poisson.get('metriques',{}).get('nb_obs_test', 0),
                'gini_poisson': self.metriques.get('poisson',{}).get('gini', 0),
                'aic_poisson':  self.metriques.get('poisson',{}).get('aic', 0),
                'vars_retenues':self.metriques.get('poisson',{}).get('vars_retenues', []),
                'statut_h1': _val_glm_.get('h1_poisson',{}).get('statut',''),
                'statut_h2': _val_glm_.get('h2_homosc',{}).get('statut',''),
                'statut_h3': _val_glm_.get('h3_ajustement',{}).get('statut',''),
                'statut_h4': _val_glm_.get('h4_stabilite',{}).get('statut',''),
                # Modules avancés P2
                'credibilite_appliquee': credibilite.get('appliquee', False),
                'credibilite_z_moyen':   credibilite.get('z_moyen', None),
                'lissage_geo_applique':  lissage_geo.get('applique', False),
            }

            return {
                'success':      True,
                'dataframe':    df,
                'branche':      sous_branche,
                'statut_rag':   statut_rag,
                'modeles':      self.modeles,
                'metriques':    self.metriques,
                'predictions':  self.predictions,
                'graphiques':            graphiques,
                'validation_glm':        _val_glm_,
                'graphiques_validation': _gv_glm_,
                'rapport':      rapport,
                'commentaire':  commentaire,
                'audit_id':     audit_id,
                'erreur':       None,
                'df_train':     df_train,
                'df_test':      df_test,
                'vars_pred':    vars_pred,
                # ── RELATIVITÉS TARIFAIRES (sortie commerciale) ──────────────
                'relativites_poisson': relativites_poisson,
                'relativites_gamma':   relativites_gamma,
                'excel_bytes':  excel_bytes,
                'word_bytes':   b'',
                'pdf_bytes':    b'',
                'hypotheses':   _val_glm_,
                'audit_trail':  audit_trail_a3,
                # Exclusions de conformité tracées par MatriceX (audit V11 / I5) :
                # une exclusion silencieuse est un défaut en soi — c'est ce silence
                # qui a rendu le BLOQUANT B5 si coûteux (facteur central de la RC Pro
                # détruit, −17,4 % de Gini, sans que rien ne l'indique nulle part).
                'exclusions_conformite': getattr(self, 'exclusions_conformite', {}),
                'controle_effet': getattr(self, 'controle_effet',
                                          {'execute': False, 'motifs': {}}),
                'alertes_conformite': getattr(self, 'alertes_conformite', {}),
                # Modèle amputé (colonnes du plan absentes des données) : alerte
                # explicite + plafond AMBRE. A6 agrège déjà 'alertes_modele'
                # depuis r3/r4/r5 et la route vers les 3 livrables.
                'alertes_modele':   _alertes_modele,
                'modele_ampute':    _ampute,
                # Modules avancés P2
                'credibilite':  credibilite,
                'lissage_geo':  lissage_geo,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 1 : PRÉPARATION DES DONNÉES
    # ══════════════════════════════════════════════════════════════════════════

    def _preparer_donnees(
        self,
        df:           pd.DataFrame,
        sous_branche: str,
        col_freq:     str,
        col_cout:     str,
        col_expo:     str,
        plan:         PlanTarifaire,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
        """
        Prépare les données pour la calibration GLM.

        SÉLECTION DES VARIABLES :
        ──────────────────────────
        1. On part des variables prioritaires de la sous-branche (VARS_GLM)
        2. On filtre celles qui existent dans le DataFrame
        3. On exclut les colonnes non-numériques non encodées
        4. On vérifie l'absence de NaN

        SPLIT TRAIN/TEST :
        ───────────────────
        Stratifié sur la variable cible (fréquence) pour s'assurer
        que la distribution des sinistres est représentative
        dans les deux ensembles.

        Justification du 80/20 :
        Un GLM nécessite moins de données qu'un modèle ML pour converger,
        mais 56 000 contrats en train garantissent des estimations stables.
        Les 14 000 contrats en test permettent une validation fiable du Gini.
        """
        # Sélection des variables candidates : dérivées À LA VOLÉE du PLAN signé
        # (Phase 1) — plus de VARS_GLM codé en dur ni de matching flou de
        # sous-branche. plan.colonnes_produites() est le contrat A2→A3 (INV-1).
        vars_prioritaires = list(plan.colonnes_produites())

        # ── FILET DE SÉCURITÉ RÉGLEMENTAIRE (défense en profondeur, audit V4) ──
        # Exclusion inconditionnelle du genre, en plus du filtrage déjà fait
        # en amont par A2. Protège contre :
        #  (a) le fallback ci-dessus qui prend TOUTES les colonnes numériques
        #      si sous_branche n'est pas reconnue dans VARS_GLM ;
        #  (b) des données arrivant pré-encodées hors du pipeline A2 standard ;
        #  (c) une sous-branche mal nommée qui échapperait à un filtre scopé
        #      par nom de branche (cas testé et confirmé lors de l'audit V4).
        # Réf. : Arrêt CJUE C-236/09 (Test-Achats, 1er mars 2011).
        #
        # ⚠ AUCUN FILTRE DE CONFORMITÉ ICI — c'est délibéré.
        # Un filtre intermédiaire figurait à cet endroit. Il n'était PAS décisif :
        # le code plus bas enrichit encore la liste (colonnes *_enc), et c'est
        # exactement ainsi que le BLOQUANT B1 (audit V10) est né — deux filtres,
        # un seul décisif, et personne ne savait lequel. La conformité est
        # appliquée UNE SEULE FOIS, à la liste FINALE (voir plus bas).

        # Filtrage : variables qui existent ET sont numériques
        cols_exclure = set(COLS_A_EXCLURE)
        vars_pred = [
            v for v in vars_prioritaires
            if v in df.columns
            and v not in cols_exclure
            and df[v].dtype in ['int64', 'float64', 'int32', 'float32']
            and df[v].isnull().sum() == 0
            and df[v].std() > 0  # Exclut les constantes
        ]

        # Ajout de variables numériques non listées mais disponibles
        # (encodages créés par A2 non explicitement listés)
        cols_num_disponibles = [
            c for c in df.select_dtypes(
                include=['int64', 'float64']
            ).columns
            if c not in cols_exclure
            and c not in vars_pred
            and df[c].isnull().sum() == 0
            and df[c].std() > 0
            and '_enc' in c  # Colonnes encodées par A2
        ]
        vars_pred.extend(cols_num_disponibles[:10])  # Limite à 10 supplémentaires

        # ══════════════════════════════════════════════════════════════════════
        #  CONFORMITÉ — FILTRE APPLIQUÉ À LA LISTE FINALE (audit V10, BLOQUANT B1)
        # ══════════════════════════════════════════════════════════════════════
        # ⚠ NE JAMAIS DÉPLACER CET APPEL NI AJOUTER DE COLONNE APRÈS LUI.
        #
        # Le filtre de conformité était appliqué plus haut, à `vars_prioritaires`
        # — mais le bloc ci-dessus RÉINJECTAIT ensuite toute colonne `*_enc` du
        # DataFrame, gardé par la seule liste noire statique COLS_A_EXCLURE (qui
        # ne contient AUCUNE variable de genre). Le filtre était donc
        # intégralement contourné vingt lignes après son propre appel.
        #
        # Prouvé par exécution (audit V10) : un fichier client contenant une
        # colonne 'titre' (M./Mme — la civilité, proxy parfait du genre) était
        # encodé par A2 en 'titre_enc', réinjecté ici, et retenu par le GLM avec
        # β = −0,476 (p = 5,5e-13) — soit un écart de tarif de 37,9 % entre
        # hommes et femmes. Variable légalement prohibée (CJUE C-236/09).
        #
        # LEÇON : un filtre de conformité doit s'appliquer au DERNIER MOMENT
        # POSSIBLE, sur la liste effectivement utilisée pour construire la
        # matrice X — jamais sur une liste intermédiaire qu'un code ultérieur
        # peut enrichir. C'est le même défaut, dans sa forme la plus pure, que
        # celui qui hante ce module depuis six cycles : « une règle correcte à
        # un endroit, contournée ailleurs ».
        # construire_matrice_x() retourne un objet MatriceX IMMUABLE : le geste
        # exact qui a produit B1 (mx.features.extend(colonnes_brutes)) lève
        # désormais une AttributeError.
        #
        # ⚠ HONNÊTETÉ SUR LA PORTÉE DE CETTE PROTECTION (audit V12) : la liste est
        # reconvertie en `list` juste après (les modèles en ont besoin). Un code
        # ultérieur POURRAIT donc encore l'enrichir — l'immuabilité empêche
        # l'accident, pas la volonté. Aucun code ne le fait aujourd'hui (vérifié),
        # et le contrat est explicite ci-dessus : NE RIEN AJOUTER APRÈS CET APPEL.
        # La défense qui, elle, ne se contourne pas est le contrôle par l'EFFET
        # (garde-fou n°4) : une variable qui fuite se trahit par sa corrélation
        # avec la cible, même si elle a traversé tous les filtres nominaux et même
        # si quelqu'un la réinjecte à la main.
        _mx = construire_matrice_x(
            vars_pred, plan=plan,   # Phase 1 : liste blanche = plan.colonnes_produites()
            contexte=f"A3 — matrice de conception GLM (sous-branche '{sous_branche}')",
            logger_agent=logger,
            # ⚠ df + col_cible = GARDE-FOU N°4 (contrôle par l'EFFET, audit V12).
            # Sans eux, seuls les contrôles par le NOM protègent — et l'audit V12
            # a démontré qu'ils sont structurellement insuffisants.
            # Le GLM d'A3 a DEUX cibles (fréquence ET coût moyen) : une fuite peut
            # viser l'une ou l'autre. On les passe toutes les deux, en UN SEUL
            # appel — le point de passage de la conformité reste unique.
            df=df, col_cible=[col_freq, col_cout],
        )
        self.exclusions_conformite = _mx.exclusions
        # ⚠️ LE CONTRÔLE PAR L'EFFET VOYAGE AVEC SON MOTIF — `conformite/C7`.
        # La propriété existait depuis l'audit V14 avec la mention « À
        # REMONTER DANS LES RAPPORTS » ; mesuré, aucun agent ne la lisait.
        self.controle_effet = {'execute': _mx.controle_effet_execute,
                               'motifs': _mx.motifs_controle_effet}
        self.alertes_conformite = _mx.alertes   # remontée dans les rapports
        vars_pred = list(_mx)

        if len(vars_pred) == 0:
            raise ValueError(
                "Aucune variable prédictive disponible pour le GLM. "
                "Vérifiez que l'agent A2 a bien encodé les variables."
            )

        logger.info(f"Variables candidates GLM : {len(vars_pred)}")

        # ── SPLIT TEMPOREL (R1) ──────────────────────────────────────────────
        # La validation doit être temporelle : les données les plus récentes
        # constituent le jeu de test, les plus anciennes le jeu d'entraînement.
        # Un split aléatoire mélange des observations futures dans l'entraînement
        # et produit un optimisme artificiel du Gini (data leakage temporel).
        # ⚠️ AUCUNE SOURCE EXTERNE N'EST CITÉE ICI, ET C'EST VOULU. Ces lignes
        # portaient « Réf. : Commission Tarification IA France (2019) §3.2.4 »
        # avec une citation entre guillemets. Rien ne confirme qu'un document
        # existe derrière ce titre, le numéro de section variait d'un fichier à
        # l'autre (§3.2.4, §3.2.5, §4.2), et la citation n'a jamais été sourcée.
        # La règle, elle, se justifie seule : un split aléatoire fait fuir de
        # l'information future dans l'entraînement. C'est elle qu'on garde.
        _col_temp = next(
            (c for c in ['annee_souscription', 'date_souscription', 'annee', 'year']
             if c in df.columns),
            None
        )
        if _col_temp is not None:
            # Tri par année croissante — les 80% anciens = train, 20% récents = test
            df_sorted = df.sort_values(_col_temp).reset_index(drop=True)
            n_train   = int(len(df_sorted) * TRAIN_SIZE)
            df_train  = df_sorted.iloc[:n_train].reset_index(drop=True)
            df_test   = df_sorted.iloc[n_train:].reset_index(drop=True)
            logger.info(
                f"[R1] Split TEMPOREL sur '{_col_temp}' : "
                f"train={len(df_train):,} ({df_train[_col_temp].min()}–"
                f"{df_train[_col_temp].max()}) | "
                f"test={len(df_test):,} ({df_test[_col_temp].min()}–"
                f"{df_test[_col_temp].max()})"
            )
        else:
            # Fallback aléatoire documenté si colonne temporelle absente
            logger.warning(
                "[R1] Colonne temporelle absente (annee_souscription, etc.). "
                "Fallback sur split aléatoire seed=42 — le Gini mesuré "
                "peut alors être optimiste (fuite temporelle possible)."
            )
            df_train, df_test = train_test_split(
                df, test_size=1 - TRAIN_SIZE, random_state=42, shuffle=True
            )
            df_train = df_train.reset_index(drop=True)
            df_test  = df_test.reset_index(drop=True)

        return df_train, df_test, vars_pred

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : GLM POISSON — FRÉQUENCE
    # ══════════════════════════════════════════════════════════════════════════

    def _calibrer_poisson(
        self,
        df_train:    pd.DataFrame,
        df_test:     pd.DataFrame,
        vars_pred:   List[str],
        col_freq:    str,
        col_expo:    str
    ) -> Dict:
        """
        Calibre le GLM Poisson pour la modélisation de la fréquence.

        FORMULATION MATHÉMATIQUE :
        ───────────────────────────
        Y_i ~ Poisson(μ_i)
        log(μ_i) = log(e_i) + β_0 + β_1 X_1i + ... + β_p X_pi
        où e_i = exposition du contrat i (offset)

        L'offset log(exposition) est fondamental :
        Sans offset, on modélise E[nb_sinistres] → biaisé pour contrats partiels
        Avec offset, on modélise E[nb_sinistres/exposition] = λ (taux annuel)

        SÉLECTION STEPWISE BACKWARD :
        ──────────────────────────────
        On part du modèle complet et on supprime itérativement
        la variable avec la p-value la plus élevée (> seuil_pvalue)
        jusqu'à ce que toutes les variables soient significatives.

        Justification : la méthode backward est préférée à forward
        en actuariat car elle part du modèle le plus général et
        affine progressivement, réduisant le risque de sous-modélisation.

        TRAITEMENT DE L'OFFSET :
        ─────────────────────────
        L'offset est le log de l'exposition.
        Il entre dans le modèle avec un coefficient contraint à 1.
        Cela revient à modéliser le taux de sinistres (par an)
        plutôt que le nombre brut de sinistres.
        """
        logger.info("Calibration GLM Poisson — sélection stepwise backward")

        # Vérification que la variable cible existe
        if col_freq not in df_train.columns:
            raise ValueError(f"Variable cible '{col_freq}' introuvable.")

        # Préparation de l'offset
        if col_expo in df_train.columns:
            offset_train = np.log(np.maximum(df_train[col_expo], 1e-6))
            offset_test  = np.log(np.maximum(df_test[col_expo],  1e-6))
        else:
            logger.warning("Exposition introuvable — offset = 0")
            offset_train = np.zeros(len(df_train))
            offset_test  = np.zeros(len(df_test))

        # ── SÉLECTION STEPWISE BACKWARD ───────────────────────────────────────
        vars_actives  = [v for v in vars_pred if v in df_train.columns]
        modele_final  = None
        iteration     = 0
        vars_exclues  = []

        while True:
            iteration += 1
            if len(vars_actives) == 0:
                logger.warning("Plus aucune variable active dans le GLM Poisson")
                break

            # Préparation de la matrice X
            X_train = sm.add_constant(
                df_train[vars_actives].fillna(0)
            )

            try:
                # Calibration GLM Poisson avec offset
                modele = sm.GLM(
                    df_train[col_freq],
                    X_train,
                    family=families.Poisson(link=families.links.Log()),
                    offset=offset_train
                ).fit(maxiter=200, disp=False)

                # Vérification des p-values
                pvalues = modele.pvalues.drop('const', errors='ignore')

                # Variable avec la p-value maximale
                pvalue_max = pvalues.max()
                var_max    = pvalues.idxmax()

                if pvalue_max > SEUIL_PVALUE:
                    # Suppression de la variable non significative
                    logger.debug(
                        f"  Iter {iteration} : suppression '{var_max}' "
                        f"(p-value={pvalue_max:.4f})"
                    )
                    vars_actives.remove(var_max)
                    vars_exclues.append({
                        'variable': var_max,
                        'pvalue':   round(float(pvalue_max), 4),
                        'raison':   'p-value > 0.05'
                    })
                else:
                    # Toutes les variables sont significatives → modèle final
                    modele_final = modele
                    logger.info(
                        f"Poisson convergé en {iteration} itérations | "
                        f"{len(vars_actives)} variables retenues"
                    )
                    break

            except Exception as e:
                logger.warning(f"Erreur calibration Poisson iter {iteration}: {e}")
                # Suppression de la dernière variable en cas d'erreur numérique
                if vars_actives:
                    vars_exclues.append({
                        'variable': vars_actives[-1],
                        'pvalue':   1.0,
                        'raison':   f'erreur numérique: {str(e)[:50]}'
                    })
                    vars_actives.pop()
                else:
                    break

        # Si aucun modèle n'a convergé → modèle intercept seul
        if modele_final is None:
            logger.warning("GLM Poisson : modèle intercept seul")
            X_intercept = sm.add_constant(
                pd.DataFrame({'intercept': np.ones(len(df_train))})
            )
            modele_final = sm.GLM(
                df_train[col_freq],
                X_intercept,
                family=families.Poisson(link=families.links.Log()),
                offset=offset_train
            ).fit(maxiter=200, disp=False)
            vars_actives = []

        # ── MÉTRIQUES ─────────────────────────────────────────────────────────
        # Prédictions sur le test
        if vars_actives:
            X_test  = sm.add_constant(df_test[vars_actives].fillna(0),
                                       has_constant='add')
        else:
            X_test  = sm.add_constant(
                pd.DataFrame({'intercept': np.ones(len(df_test))})
            )

        try:
            pred_test = modele_final.predict(X_test, offset=offset_test)
        except Exception:
            pred_test = np.full(len(df_test), df_train[col_freq].mean())

        # Gini (coefficient de discrimination)
        gini = self._calculer_gini(df_test[col_freq].values, pred_test.values)

        # RMSE sur le test
        rmse = np.sqrt(mean_squared_error(
            df_test[col_freq], pred_test
        ))

        metriques = {
            'aic':              round(float(modele_final.aic), 2),
            'bic':              round(float(modele_final.bic), 2),
            'deviance':         round(float(modele_final.deviance), 4),
            'deviance_nulle':   round(float(modele_final.null_deviance), 4),
            'pseudo_r2':        round(
                1 - modele_final.deviance / modele_final.null_deviance, 4
            ),
            'gini':             round(gini, 4),
            # ⚠️ BASE MESURÉE : `predict(X_test, offset=offset_test)` incorpore
            # l'exposition — le tri se fait sur un COMPTAGE (constat `a4/C10`).
            'base_gini':        BASE_GINI_COMPTAGE,
            'rmse_test':        round(rmse, 4),
            'nb_vars_retenues': len(vars_actives),
            'nb_vars_exclues':  len(vars_exclues),
            'vars_retenues':    vars_actives,
            'vars_exclues':     vars_exclues,
            'nb_obs_train':     int(len(df_train)),
            'nb_obs_test':      int(len(df_test)),
            'frequence_obs':    round(float(df_train[col_freq].mean()), 4),
            'frequence_pred':   round(float(pred_test.mean()), 4),
        }

        # ── RELATIVITÉS TARIFAIRES exp(β) ─────────────────────────────────────
        # Sortie commerciale standard d'un GLM actuariel.
        # Interprétation : une relativité de 1.25 signifie +25% de sinistralité
        # par rapport à la modalité de référence (intercept).
        # Source : Mildenhall (1999), Actuarial GLM review standards.
        relativites = {}
        try:
            params  = modele_final.params
            conf    = modele_final.conf_int()
            pvalues = modele_final.pvalues
            for var in vars_actives:
                if var in params.index:
                    beta    = float(params[var])
                    ci_low  = float(conf.loc[var, 0])
                    ci_high = float(conf.loc[var, 1])
                    relativites[var] = {
                        'beta':         round(beta,          4),
                        'relativite':   round(float(np.exp(beta)),    4),
                        'ic95_low':     round(float(np.exp(ci_low)),  4),
                        'ic95_high':    round(float(np.exp(ci_high)), 4),
                        'pvalue':       round(float(pvalues[var]),    4),
                        'significatif': bool(float(pvalues[var]) <= 0.05),
                        'sens':         'aggravant' if beta > 0 else 'allegant',
                    }
        except Exception as e_rel:
            logger.warning(f"Calcul relativités Poisson échoué : {e_rel}")

        metriques['relativites'] = relativites

        return {
            'modele':      modele_final,
            'metriques':   metriques,
            'vars':        vars_actives,
            'pred_test':   pred_test,
            'relativites': relativites,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 3 : GLM GAMMA — COÛT MOYEN
    # ══════════════════════════════════════════════════════════════════════════

    def _calibrer_gamma(
        self,
        df_train:  pd.DataFrame,
        df_test:   pd.DataFrame,
        vars_pred: List[str],
        col_cout:  str,
        col_freq:  str,
        col_expo:  str,
    ) -> Dict:
        """
        Calibre le GLM Gamma pour la modélisation du coût moyen.

        FORMULATION MATHÉMATIQUE :
        ───────────────────────────
        Y_i | Y_i > 0 ~ Gamma(μ_i, φ)
        log(μ_i) = β_0 + β_1 X_1i + ... + β_p X_pi

        POINT CRUCIAL — FILTRAGE SUR LES SINISTRES :
        ──────────────────────────────────────────────
        Le GLM Gamma est calibré UNIQUEMENT sur les contrats
        avec au moins un sinistre (cout_total_sinistres > 0).

        Justification actuarielle :
        La distribution Gamma ne supporte pas les valeurs nulles.
        De plus, on modélise le COÛT CONDITIONNEL à l'occurrence
        d'un sinistre : E[coût | sinistre > 0].
        Inclure les coûts nuls biaiserait l'estimation vers le bas.

        La prime pure = E[fréquence] × E[coût | sinistre > 0]
        est calculée en combinant les deux GLM.

        DISTRIBUTION GAMMA :
        ─────────────────────
        Propriétés qui la rendent adaptée aux coûts de sinistres :
        • Support positif strict (coûts > 0)
        • Asymétrie positive (quelques sinistres très coûteux)
        • Coefficient de variation constant (var/mean² = cst)
        • Fonction de lien log → prime toujours positive
        """
        logger.info("Calibration GLM Gamma — cible de sévérité (source unique)")

        if col_cout not in df_train.columns:
            raise ValueError(f"Variable coût '{col_cout}' introuvable.")

        # ── CIBLE DE SÉVÉRITÉ — SOURCE UNIQUE (core/severite.py) ──────────────
        # ⚠ CORRECTIF DE MODÉLISATION. Cette méthode ajustait
        # `df_sin_train[col_cout]` — le coût TOTAL — en le déclarant 'cout_moyen',
        # sans écrêtement, avec un masque `cout > 0`. Le chemin déclaratif
        # (pipeline_complet), lui, ajuste cout_ecrete/nb : la même grandeur portait
        # DEUX définitions contradictoires.
        #
        # Le coût TOTAL mélange sévérité et FRÉQUENCE (3 sinistres ≈ 3× le total).
        # Mesuré sur décennale 100k (structure causale connue) : le coefficient de
        # `montant` absorbait AUSSI l'effet fréquence, pente surestimée, prédiction
        # hors échantillon des sinistrés effondrée à 32 178 € au lieu de 36 797 €
        # (−12,6 % ; vérité DGP 36 772 €) → Σ primes / Σ charge = 0,85 : A3
        # SOUS-TARIFIAIT de 15 %. Le seuil d'écrêtement est APPRIS sur le train et
        # APPLIQUÉ au test — jamais recalculé (piège V9).
        cible_tr = construire_cible_severite(
            df_train[col_cout], df_train[col_freq], df_train[col_expo])
        cible_te = construire_cible_severite(
            df_test[col_cout], df_test[col_freq], df_test[col_expo],
            seuil=cible_tr.seuil_ecretement)

        df_sin_train = df_train[cible_tr.masque].copy().reset_index(drop=True)
        df_sin_test  = df_test[cible_te.masque].copy().reset_index(drop=True)
        y_sev_train  = pd.Series(cible_tr.severite, index=df_sin_train.index)
        y_sev_test   = pd.Series(cible_te.severite, index=df_sin_test.index)

        # Charge grave mutualisée — RÉINJECTÉE dans la prime pure par
        # _calculer_predictions. Sans elle, on écrêterait les graves du prix mais
        # pas de la réalité.
        self.prime_grave_unitaire = cible_tr.prime_grave_unitaire
        logger.info(
            f"Sévérité : {cible_tr.n_retenus:,} contrats retenus | seuil écrêtement "
            f"{cible_tr.seuil_ecretement:,.0f} € | {cible_tr.n_graves} grave(s) | "
            f"prime grave unitaire {cible_tr.prime_grave_unitaire:,.2f} €/expo")

        nb_sin_train = cible_tr.n_retenus
        nb_sin_test  = cible_te.n_retenus

        logger.info(
            f"Contrats avec sinistres : train={nb_sin_train:,} | "
            f"test={nb_sin_test:,}"
        )

        if nb_sin_train < 100:
            logger.warning(
                f"Seulement {nb_sin_train} sinistres en train. "
                "Le GLM Gamma risque d'être instable."
            )

        # ── SÉLECTION STEPWISE BACKWARD ───────────────────────────────────────
        vars_actives = [v for v in vars_pred if v in df_sin_train.columns]
        modele_final = None
        vars_exclues = []
        iteration    = 0

        while True:
            iteration += 1
            if not vars_actives:
                break

            X_train = sm.add_constant(df_sin_train[vars_actives].fillna(0))

            try:
                modele = sm.GLM(
                    y_sev_train,
                    X_train,
                    family=families.Gamma(link=families.links.Log())
                ).fit(maxiter=200, disp=False)

                pvalues   = modele.pvalues.drop('const', errors='ignore')
                pvalue_max = pvalues.max()
                var_max    = pvalues.idxmax()

                if pvalue_max > SEUIL_PVALUE:
                    vars_actives.remove(var_max)
                    vars_exclues.append({
                        'variable': var_max,
                        'pvalue':   round(float(pvalue_max), 4),
                        'raison':   'p-value > 0.05'
                    })
                else:
                    modele_final = modele
                    break

            except Exception as e:
                logger.warning(f"Erreur Gamma iter {iteration}: {e}")
                if vars_actives:
                    vars_exclues.append({
                        'variable': vars_actives[-1],
                        'pvalue':   1.0,
                        'raison':   f'erreur numérique'
                    })
                    vars_actives.pop()
                else:
                    break

        # Modèle intercept seul si nécessaire
        if modele_final is None:
            X_int = sm.add_constant(
                pd.DataFrame({'i': np.ones(len(df_sin_train))})
            )
            modele_final = sm.GLM(
                y_sev_train, X_int,
                family=families.Gamma(link=families.links.Log())
            ).fit(maxiter=200, disp=False)
            vars_actives = []

        # ── MÉTRIQUES ─────────────────────────────────────────────────────────
        if vars_actives and nb_sin_test > 0:
            X_test = sm.add_constant(
                df_sin_test[vars_actives].fillna(0), has_constant='add'
            )
        else:
            X_test = sm.add_constant(
                pd.DataFrame({'i': np.ones(len(df_sin_test))})
            )

        try:
            pred_test = modele_final.predict(X_test)
        except Exception:
            pred_test = np.full(
                len(df_sin_test),
                float(y_sev_train.mean())
            )

        rmse = np.sqrt(mean_squared_error(
            y_sev_test, pred_test
        )) if nb_sin_test > 0 else 0.0

        gini = self._calculer_gini(
            y_sev_test.values, pred_test.values
        ) if nb_sin_test > 0 else 0.0

        metriques = {
            'aic':              round(float(modele_final.aic), 2),
            'bic':              round(float(modele_final.bic), 2),
            'deviance':         round(float(modele_final.deviance), 4),
            'pseudo_r2':        round(
                1 - modele_final.deviance / modele_final.null_deviance, 4
            ),
            'gini':             round(gini, 4),
            # ⚠️ BASE MESURÉE : `predict(X_test)` SANS offset, sur les sinistrés
            # seuls — le tri se fait sur un COÛT MOYEN.
            'base_gini':        BASE_GINI_COUT_MOYEN,
            'rmse_test':        round(rmse, 2),
            'nb_vars_retenues': len(vars_actives),
            'nb_vars_exclues':  len(vars_exclues),
            'vars_retenues':    vars_actives,
            'vars_exclues':     vars_exclues,
            'nb_obs_train':     nb_sin_train,
            'nb_obs_test':      nb_sin_test,
            'cout_moyen_obs':   round(float(y_sev_train.mean()), 2),
            'cout_moyen_pred':  round(float(pred_test.mean()), 2)
                                if len(pred_test) > 0 else 0.0,
        }

        # ── RELATIVITÉS TARIFAIRES exp(β) Gamma ──────────────────────────────
        relativites_gamma = {}
        try:
            params_g  = modele_final.params
            conf_g    = modele_final.conf_int()
            pvalues_g = modele_final.pvalues
            for var in vars_actives:
                if var in params_g.index:
                    beta_g    = float(params_g[var])
                    ci_low_g  = float(conf_g.loc[var, 0])
                    ci_high_g = float(conf_g.loc[var, 1])
                    relativites_gamma[var] = {
                        'beta':         round(beta_g,                      4),
                        'relativite':   round(float(np.exp(beta_g)),       4),
                        'ic95_low':     round(float(np.exp(ci_low_g)),     4),
                        'ic95_high':    round(float(np.exp(ci_high_g)),    4),
                        'pvalue':       round(float(pvalues_g[var]),       4),
                        'significatif': bool(float(pvalues_g[var]) <= 0.05),
                        'sens':         'aggravant' if beta_g > 0 else 'allegant',
                    }
        except Exception as e_relg:
            logger.warning(f"Calcul relativités Gamma échoué : {e_relg}")

        metriques['relativites'] = relativites_gamma

        return {
            'modele':      modele_final,
            'metriques':   metriques,
            'vars':        vars_actives,
            'pred_test':   pred_test,
            'relativites': relativites_gamma,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 4 : GLM TWEEDIE — PRIME PURE
    # ══════════════════════════════════════════════════════════════════════════

    def _calibrer_tweedie(
        self,
        df_train:  pd.DataFrame,
        df_test:   pd.DataFrame,
        vars_pred: List[str],
        col_freq:  str,
        col_cout:  str,
        col_expo:  str
    ) -> Dict:
        """
        Calibre le GLM Tweedie pour la modélisation directe de la prime pure.

        FORMULATION MATHÉMATIQUE :
        ───────────────────────────
        Y_i ~ Tweedie(μ_i, φ, p)  avec p ∈ (1, 2)
        log(μ_i) = β_0 + β_1 X_1i + ... + β_p X_pi

        PAS D'OFFSET : la cible est DÉJÀ le taux annualisé (cout/expo). Ajouter
        offset=log(expo) appliquerait l'exposition DEUX FOIS → la prime pure
        prédite deviendrait proportionnelle à l'exposition (mesuré : même contrat
        expo 1.0 vs 0.5 → prime ×2), alors qu'elle en est indépendante. Forme
        standard = « cible=coût + offset » OU « cible=taux sans offset », pas les
        deux. On garde cible=taux (annualisée par A2), donc PAS d'offset.

        DISTRIBUTION TWEEDIE :
        ───────────────────────
        La distribution Tweedie avec p ∈ (1, 2) est une composée
        Poisson-Gamma. Elle peut représenter une masse de probabilité
        en zéro (contrats sans sinistre) ET une queue lourde (sinistres coûteux).

        C'est la distribution naturelle de la prime pure brute :
        • P(prime_pure = 0) > 0  (contrats sans sinistre)
        • P(prime_pure > x) décroît comme une loi Gamma

        Avec p = 1.5 (choix standard ACPR/marché français) :
        • p=1 → Poisson (fréquence seule)
        • p=1.5 → Tweedie composé Poisson-Gamma (prime pure)
        • p=2 → Gamma (coût seul)

        VARIABLE CIBLE :
        ─────────────────
        On utilise la prime pure observée = cout_total_sinistres / exposition
        comme approximation de la prime pure réelle (λ × μ).

        Note : la prime pure observée est bruitée (une seule année d'observation
        par contrat). Le GLM Tweedie lisse ce bruit en estimant E[prime_pure].
        """
        logger.info(f"Calibration GLM Tweedie (p={TWEEDIE_P})")

        # Variable cible Tweedie : prime pure observée
        # = coût total / exposition (sinistralité annualisée)
        col_target_tweedie = 'prime_pure_obs_tweedie'
        expo_train = np.maximum(df_train.get(col_expo, pd.Series(np.ones(len(df_train)))), 1e-6)
        expo_test  = np.maximum(df_test.get(col_expo,  pd.Series(np.ones(len(df_test)))),  1e-6)

        df_train = df_train.copy()
        df_test  = df_test.copy()

        df_train[col_target_tweedie] = (
            df_train[col_cout] / expo_train.values
        ).clip(lower=0)
        df_test[col_target_tweedie] = (
            df_test[col_cout] / expo_test.values
        ).clip(lower=0)

        # Sélection variables
        vars_actives = [v for v in vars_pred if v in df_train.columns]
        modele_final = None
        vars_exclues = []
        iteration    = 0

        while True:
            iteration += 1
            if not vars_actives:
                break

            X_train = sm.add_constant(df_train[vars_actives].fillna(0))

            try:
                modele = sm.GLM(
                    df_train[col_target_tweedie],
                    X_train,
                    family=families.Tweedie(
                        link=families.links.Log(),
                        var_power=TWEEDIE_P
                    ),
                ).fit(maxiter=200, disp=False)

                pvalues   = modele.pvalues.drop('const', errors='ignore')
                pvalue_max = pvalues.max()
                var_max    = pvalues.idxmax()

                if pvalue_max > SEUIL_PVALUE:
                    vars_actives.remove(var_max)
                    vars_exclues.append({
                        'variable': var_max,
                        'pvalue':   round(float(pvalue_max), 4),
                        'raison':   'p-value > 0.05'
                    })
                else:
                    modele_final = modele
                    break

            except Exception as e:
                logger.warning(f"Erreur Tweedie iter {iteration}: {e}")
                if vars_actives:
                    vars_actives.pop()
                else:
                    break

        # Modèle intercept seul
        if modele_final is None:
            X_int = sm.add_constant(
                pd.DataFrame({'i': np.ones(len(df_train))})
            )
            modele_final = sm.GLM(
                df_train[col_target_tweedie], X_int,
                family=families.Tweedie(
                    link=families.links.Log(),
                    var_power=TWEEDIE_P
                ),
            ).fit(maxiter=200, disp=False)
            vars_actives = []

        # Métriques
        if vars_actives:
            X_test = sm.add_constant(
                df_test[vars_actives].fillna(0), has_constant='add'
            )
        else:
            X_test = sm.add_constant(
                pd.DataFrame({'i': np.ones(len(df_test))})
            )

        try:
            pred_test = modele_final.predict(X_test)
        except Exception:
            pred_test = np.full(len(df_test), df_train[col_target_tweedie].mean())

        # ⚠️⚠️ LE TWEEDIE POSE ENFIN SON GINI — constat `a3/C6`.
        # Il n'en posait AUCUN, et A6 lisait `met.get('gini', 0)` : le modèle
        # entrait dans l'arbitrage **noté zéro**, d'un zéro que personne n'avait
        # mesuré. *Un 0 qui signifie « jamais mesuré » est indiscernable d'un 0
        # qui signifie « sans pouvoir discriminant »* — et A6 ARBITRE là-dessus.
        #
        # ⚠️ CE GINI EST BIEN DÉFINI, et j'avais écrit l'inverse : il compare la
        # prime pure PRÉDITE à la prime pure OBSERVÉE, exactement comme le
        # Poisson compare des fréquences et le Gamma des coûts moyens. Ce qui
        # n'aurait aucun sens serait de le comparer à un Gini de FRÉQUENCE —
        # et **le filtre par cible d'A6 l'empêche déjà** : un modèle dont la
        # `cible` diffère est écarté avec le motif `cible_differente`. *Mesuré
        # avant de le réaffirmer.*
        try:
            gini_tw = self._calculer_gini(
                df_test[col_target_tweedie].values,
                np.asarray(pred_test, dtype=float),
            )
        except Exception as exc:                       # noqa: BLE001
            # ⚠️ UN ÉCHEC NE SE PUBLIE PAS EN ZÉRO. On rend `None` — la valeur
            # que le catalogue d'A6 saura distinguer d'un zéro mesuré.
            logger.warning(
                f"[A3] Gini Tweedie NON CALCULÉ ({type(exc).__name__}: {exc}) — "
                f"publié à None, jamais à 0 : un zéro serait indiscernable "
                f"d'une absence de pouvoir discriminant.")
            gini_tw = None

        metriques = {
            'aic':              round(float(modele_final.aic), 2),
            'bic':              round(float(modele_final.bic), 2),
            'deviance':         round(float(modele_final.deviance), 4),
            'gini':             (round(float(gini_tw), 4)
                                 if gini_tw is not None else None),
            # ⚠️ BASE MESURÉE : `predict(X_test)` SANS offset — le tri se fait
            # sur une prédiction UNITAIRE, hors exposition.
            'base_gini':        BASE_GINI_UNITAIRE,
            'tweedie_p':        TWEEDIE_P,
            'nb_vars_retenues': len(vars_actives),
            'nb_vars_exclues':  len(vars_exclues),
            'vars_retenues':    vars_actives,
            'prime_pure_moy_obs':  round(float(df_train[col_target_tweedie].mean()), 2),
            'prime_pure_moy_pred': round(float(pred_test.mean()), 2),
        }

        return {
            'modele':    modele_final,
            'metriques': metriques,
            'vars':      vars_actives,
            'pred_test': pred_test,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 5 : PRÉDICTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_predictions(
        self,
        df:          pd.DataFrame,
        vars_pred:   List[str],
        col_expo:    str
    ) -> Dict[str, np.ndarray]:
        """
        Calcule les prédictions sur l'ensemble du portefeuille.

        PRIME PURE = Fréquence prédite × Coût moyen prédit

        C'est la décomposition fondamentale de la tarification Non-Vie :
        • Fréquence (Poisson)  : combien de sinistres en moyenne ?
        • Coût moyen (Gamma)   : combien coûte un sinistre en moyenne ?
        • Prime pure = λ × μ   : combien coûte le risque par an ?

        Le GLM Tweedie donne une estimation directe et complémentaire
        de la prime pure, utile pour les comparaisons.
        """
        predictions = {}

        expo = np.maximum(
            df.get(col_expo, pd.Series(np.ones(len(df)))).values,
            1e-6
        )
        offset = np.log(expo)

        # Prédictions Poisson (fréquence annuelle)
        if 'poisson' in self.modeles:
            vars_poisson = self.metriques['poisson']['vars_retenues']
            if vars_poisson:
                X = sm.add_constant(
                    df[vars_poisson].fillna(0), has_constant='add'
                )
                try:
                    pred_freq = self.modeles['poisson'].predict(X, offset=offset)
                    # Annualisation : λ_annuel = λ_observé / exposition
                    predictions['frequence_annuelle'] = pred_freq.values / np.maximum(expo, 1e-6)
                    predictions['frequence_brute']    = pred_freq.values
                except Exception as e:
                    logger.warning(f"Erreur prédiction Poisson : {e}")
                    predictions['frequence_annuelle'] = np.full(
                        len(df), df[self.metriques['poisson'].get('col_freq','nb_sinistres')].mean()
                        if hasattr(self.modeles['poisson'], 'model') else 0.1
                    )

        # Prédictions Gamma (coût moyen)
        if 'gamma' in self.modeles:
            vars_gamma = self.metriques['gamma']['vars_retenues']
            if vars_gamma:
                X = sm.add_constant(
                    df[vars_gamma].fillna(0), has_constant='add'
                )
                try:
                    predictions['cout_moyen'] = self.modeles['gamma'].predict(X).values
                except Exception as e:
                    logger.warning(f"Erreur prédiction Gamma : {e}")
                    predictions['cout_moyen'] = np.full(
                        len(df),
                        self.metriques['gamma']['cout_moyen_obs']
                    )

        # ── PRIME PURE = fréquence annuelle × coût PAR SINISTRE + graves ──────
        # Le terme de graves n'est pas un ajustement cosmétique : c'est la charge
        # ÉCRÊTÉE du Gamma, remise dans le tarif. L'omettre reviendrait à écrêter
        # les sinistres graves du PRIX mais pas de la RÉALITÉ — le tarif
        # sous-estimerait alors la charge de tout l'écrêtement. Même formule que
        # pipeline_complet : (freq × cout + ecretement).
        if 'frequence_annuelle' in predictions and 'cout_moyen' in predictions:
            predictions['prime_pure'] = (
                predictions['frequence_annuelle'] * predictions['cout_moyen']
                + getattr(self, 'prime_grave_unitaire', 0.0)
            )

        # Prédictions Tweedie (prime pure directe)
        if 'tweedie' in self.modeles:
            vars_tweedie = self.metriques['tweedie']['vars_retenues']
            if vars_tweedie:
                X = sm.add_constant(
                    df[vars_tweedie].fillna(0), has_constant='add'
                )
                try:
                    # ⚠️ PAS D'OFFSET AU PREDICT NON PLUS. Le correctif
                    # `0d2b9c2` n'avait été appliqué qu'au FIT :
                    # `_calibrer_tweedie` ajuste sans offset — sa docstring
                    # l'exige mot pour mot (« Ajouter offset=log(expo)
                    # appliquerait l'exposition DEUX FOIS ») — et cette ligne
                    # prédisait AVEC. Mesuré : corr(prime_pure_tweedie,
                    # exposition) = +0,51, un contrat à forte exposition
                    # recevant une prime 4,4× celle d'un contrat identique à
                    # faible exposition. La prime pure est un TAUX ANNUEL :
                    # elle est exposure-indépendante par construction.
                    predictions['prime_pure_tweedie'] = self.modeles['tweedie'].predict(
                        X
                    ).values
                except Exception as e:
                    logger.warning(f"Erreur prédiction Tweedie : {e}")

        return predictions

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTRIQUES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_gini(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> float:
        """
        Calcule le coefficient de Gini.

        DÉFINITION ACTUARIELLE :
        ─────────────────────────
        Le Gini mesure la capacité du modèle à discriminer entre
        les bons et les mauvais risques.

        Gini = 2 × AUC - 1  (où AUC est l'aire sous la courbe de Lorenz)

        Interprétation :
        • Gini = 0    → modèle nul (pas de discrimination)
        • Gini = 0.20 → acceptable pour un portefeuille auto FR
        • Gini = 0.35 → bon modèle
        • Gini > 0.50 → excellent (rare en tarification assurance)

        Reference : Frees & Valdez (1998), Understanding Relationships
        Using Copulas, North American Actuarial Journal.
        """
        if len(y_true) == 0 or len(y_pred) == 0:
            return 0.0
        if np.sum(y_true) == 0:
            # Aucun sinistre sur la période de test — Gini incalculable
            return 0.0

        try:
            # Tri par prédiction DÉCROISSANTE (convention actuarielle Lorenz)
            # Les assurés les plus risqués (forte prédiction) arrivent en premier.
            # → la courbe de Lorenz est au-dessus de la diagonale si le modèle
            #   discrimine bien → AUC > 0.5 → Gini = 2×AUC - 1 > 0.
            # Réf. : Frees & Valdez (1998), Mildenhall (1999).
            order   = np.argsort(-np.asarray(y_pred, dtype=float))
            y_ord   = np.asarray(y_true, dtype=float)[order]

            n       = len(y_ord)
            total   = float(np.sum(y_ord))
            cum_obs = np.cumsum(y_ord) / total
            cum_pop = np.arange(1, n + 1) / n

            # Aire sous la courbe de Lorenz (compatible NumPy 1.x et 2.x)
            _trapz  = getattr(np, 'trapezoid', None) or getattr(np, 'trapz', None)
            auc     = float(_trapz(cum_obs, cum_pop))
            gini    = 2.0 * auc - 1.0

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
            gini = float(np.clip(gini, -1.0, 1.0))
            if gini < 0:
                logger.warning(
                    f"[ANTI-SÉLECTION] Gini NÉGATIF ({gini:.4f}) — le modèle "
                    f"discrimine À L'ENVERS : il attribue les primes les plus "
                    f"faibles aux risques les plus élevés. Modèle INUTILISABLE "
                    f"en l'état, quelle que soit sa performance par ailleurs."
                )
            return gini

        except Exception as e_gini:
            logger.debug(f"_calculer_gini échoué : {e_gini}")
            return 0.0

    def _calculer_metriques_globales(
        self,
        df_test:   pd.DataFrame,
        vars_pred: List[str],
        col_freq:  str,
        col_cout:  str,
        col_expo:  str
    ) -> Dict:
        """Calcule les métriques globales de comparaison des 3 modèles."""
        metriques = {
            'poisson': self.metriques.get('poisson', {}),
            'gamma':   self.metriques.get('gamma',   {}),
            'tweedie': self.metriques.get('tweedie', {}),
        }

        # Comparaison Gini des 3 modèles
        metriques['comparaison_gini'] = {
            'poisson': self.metriques.get('poisson', {}).get('gini', 0),
            'gamma':   self.metriques.get('gamma',   {}).get('gini', 0),
        }

        # Meilleur modèle selon le Gini
        ginis  = metriques['comparaison_gini']
        meilleur = max(ginis, key=ginis.get)
        metriques['meilleur_modele'] = meilleur

        return metriques

    # ══════════════════════════════════════════════════════════════════════════
    # SAUVEGARDE
    # ══════════════════════════════════════════════════════════════════════════

    def _sauvegarder_modeles(self, sous_branche: str) -> None:
        """
        Sauvegarde les modèles GLM calibrés sur Drive.

        Format : pickle pour les objets statsmodels
        + JSON pour les métadonnées et métriques

        Justification : la sauvegarde permet de :
        1. Réutiliser les modèles sans recalibration
        2. Répondre à l'auditeur S2 sur les paramètres utilisés
        3. Détecter une dérive des paramètres (data drift)
        4. Déployer les modèles dans l'interface Streamlit
        """
        # Sauvegarde des modèles pickle
        for nom, modele in self.modeles.items():
            chemin = self.models_path / f"glm_{nom}_{sous_branche}.pkl"
            try:
                with open(chemin, 'wb') as f:
                    pickle.dump(modele, f)
                logger.info(f"Modèle {nom} sauvegardé : {chemin}")
            except Exception as e:
                logger.warning(f"Impossible de sauvegarder {nom}: {e}")

        # Sauvegarde des métriques en JSON (lisible humain)
        metriques_json = {
            'sous_branche': sous_branche,
            'timestamp':    datetime.now().isoformat(),
            'version':      '1.0',
            'modeles': {
                nom: {
                    k: v for k, v in met.items()
                    if not isinstance(v, (np.ndarray, pd.DataFrame))
                }
                for nom, met in self.metriques.items()
            }
        }
        chemin_json = self.models_path / f"glm_metriques_{sous_branche}.json"
        try:
            with open(chemin_json, 'w', encoding='utf-8') as f:
                json.dump(metriques_json, f, indent=2,
                          ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Métriques JSON non sauvegardées : {e}")

    def _sauvegarder_audit(
        self, audit_id, sous_branche, rapport,
        statut_rag, t_debut
    ) -> None:
        """Sauvegarde le log d'audit."""
        log = {
            'audit_id':    audit_id,
            'agent':       'A3_GLM',
            'version':     '1.0',
            'timestamp':   t_debut.isoformat(),
            'sous_branche': sous_branche,
            'statut_rag':  statut_rag,
            'etapes':      rapport['etapes'],
            'metriques_resume': {
                'poisson_gini': self.metriques.get('poisson',{}).get('gini', 0),
                'poisson_aic':  self.metriques.get('poisson',{}).get('aic', 0),
                'gamma_gini':   self.metriques.get('gamma',{}).get('gini', 0),
                'gamma_aic':    self.metriques.get('gamma',{}).get('aic', 0),
            }
        }
        chemin = self.audit_path / f"{audit_id}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(log, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # STATUT RAG & COMMENTAIRES ACTUAIRE SÉNIOR
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_statut_rag(self, metriques: Dict) -> str:
        """
        Statut RAG basé sur la qualité des modèles GLM.

        VERT  : Gini Poisson >= 0.15 ET convergence de DEUX modeles
                (Poisson et Gamma). ⚠️⚠️ CE N'EST PAS « LES TROIS » —
                constat `a3/C10`. La docstring annoncait la convergence
                des TROIS modeles ; le code lit `metriques['poisson']` et
                `metriques['gamma']`, jamais le Tweedie.
                ⚠️ ET ON NE CORRIGE PAS DANS L'AUTRE SENS : faire entrer
                le Tweedie dans le statut importerait son Gini, dont le
                constat `a3/C6` etablit qu'il **vaut 0 partout**. On
                aligne donc la phrase sur le code, pas l'inverse — et le
                jour ou `a3/C6` sera ferme, la question de l'inclure se
                reposera. *Deux constats couples : l'ordre est contraint.*
        AMBRE : Gini ∈ [0.05, 0.15] ou 1 modèle non convergé
        ROUGE : Gini < 0.05 ou 2+ modèles non convergés
        """
        gini_poisson = metriques.get('poisson', {}).get('gini', 0)
        gini_gamma   = metriques.get('gamma',   {}).get('gini', 0)
        vars_poisson = metriques.get('poisson', {}).get('nb_vars_retenues', 0)
        vars_gamma   = metriques.get('gamma',   {}).get('nb_vars_retenues', 0)

        if gini_poisson < 0.05 or (vars_poisson == 0 and vars_gamma == 0):
            return 'ROUGE'
        elif gini_poisson < 0.15 or vars_poisson == 0 or vars_gamma == 0:
            return 'AMBRE'
        else:
            return 'VERT'

    def _commenter_actuaire_senior(
        self,
        rapport:      Dict,
        sous_branche: str,
        statut_rag:   str,
        res_poisson:  Dict,
        res_gamma:    Dict,
        res_tweedie:  Dict,
        df_train:     pd.DataFrame,
        df_test:      pd.DataFrame
    ) -> str:
        """Commentaire actuaire sénior en 3 niveaux sur les GLM."""
        emoji  = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
        m_poi  = res_poisson['metriques']
        m_gam  = res_gamma['metriques']
        m_twe  = res_tweedie['metriques']

        # ── NIVEAU 1 : LECTURE ────────────────────────────────────────────────
        niveau1 = (
            f"{emoji} GLM TARIFICATION — {statut_rag}\n"
            f"Sous-branche     : {sous_branche}\n"
            f"Obs. train/test  : {len(df_train):,} / {len(df_test):,}\n"
            f"\n"
            f"GLM POISSON (fréquence) :\n"
            f"  Variables retenues : {m_poi.get('nb_vars_retenues', 0)}\n"
            f"  AIC                : {m_poi.get('aic', 'N/A')}\n"
            f"  Gini (test)        : {m_poi.get('gini', 0):.4f}\n"
            f"  Fréquence obs/pred : {m_poi.get('frequence_obs',0):.4f} / "
            f"{m_poi.get('frequence_pred',0):.4f}\n"
            f"\n"
            f"GLM GAMMA (coût moyen) :\n"
            f"  Variables retenues : {m_gam.get('nb_vars_retenues', 0)}\n"
            f"  AIC                : {m_gam.get('aic', 'N/A')}\n"
            f"  Gini (test)        : {m_gam.get('gini', 0):.4f}\n"
            f"  Coût obs/pred      : {m_gam.get('cout_moyen_obs',0):,.0f}€ / "
            f"{m_gam.get('cout_moyen_pred',0):,.0f}€\n"
            f"\n"
            f"GLM TWEEDIE (prime pure) :\n"
            f"  Variables retenues : {m_twe.get('nb_vars_retenues', 0)}\n"
            f"  AIC                : {m_twe.get('aic', 'N/A')}\n"
            f"  Prime obs/pred     : {m_twe.get('prime_pure_moy_obs',0):,.0f}€ / "
            f"{m_twe.get('prime_pure_moy_pred',0):,.0f}€"
        )

        # ── NIVEAU 2 : DIAGNOSTIC ─────────────────────────────────────────────
        gini_poi = m_poi.get('gini', 0)
        if statut_rag == 'VERT':
            niveau2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Les 3 modèles GLM ont convergé avec des performances "
                f"satisfaisantes. Le Gini du modèle de fréquence "
                f"({gini_poi:.4f}) indique un bon pouvoir discriminant "
                f"pour un portefeuille d'assurance. "
                f"Le ratio fréquence observée/prédite est proche de 1, "
                f"ce qui indique l'absence de biais systématique. "
                f"Le modèle de coût moyen (Gamma) présente une "
                f"distribution des résidus cohérente avec les hypothèses "
                f"de la famille exponentielle. "
                f"Ces modèles peuvent être utilisés pour la tarification "
                f"et serviront de référence pour la comparaison avec "
                f"les modèles ML (Agent A4)."
            )
        elif statut_rag == 'AMBRE':
            niveau2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le pouvoir discriminant des modèles est modéré "
                f"(Gini Poisson = {gini_poi:.4f}). "
                f"Cela peut indiquer que les variables disponibles "
                f"ne capturent pas tous les facteurs de risque pertinents, "
                f"ou que le portefeuille est homogène en termes de risque. "
                f"Les modèles ML (Agent A4) devraient capturer des "
                f"relations non-linéaires supplémentaires. "
                f"Utilisez ces GLM comme modèle de référence (benchmark) "
                f"plutôt que comme modèle de production."
            )
        else:
            niveau2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Les modèles GLM présentent un pouvoir discriminant "
                f"insuffisant (Gini < 0.05). "
                f"Causes possibles : variables insuffisamment informatives, "
                f"portefeuille trop homogène, ou problème de qualité "
                f"des données non corrigé. "
                f"Vérifiez les données avec l'agent A1 avant "
                f"de calibrer les modèles ML."
            )

        # ── NIVEAU 3 : RECOMMANDATION ─────────────────────────────────────────
        if statut_rag == 'VERT':
            niveau3 = (
                "RECOMMANDATION :\n"
                f"→ Passer à l'agent A4 (ML ×8) pour challenger les GLM.\n"
                f"→ Utiliser le Gini Poisson ({gini_poi:.4f}) comme "
                f"  référence de comparaison.\n"
                f"→ Analyser les coefficients β significatifs pour "
                f"  valider la cohérence actuarielle (signe et amplitude).\n"
                f"→ Les modèles sont sauvegardés pour déploiement Streamlit."
            )
        elif statut_rag == 'AMBRE':
            niveau3 = (
                "RECOMMANDATION :\n"
                f"→ Passer à l'agent A4 (ML) qui devrait améliorer le Gini.\n"
                f"→ Envisager d'ajouter des variables externes "
                f"  (météo, densité urbaine, etc.) si disponibles.\n"
                f"→ Ces GLM restent utilisables comme modèle de baseline."
            )
        else:
            niveau3 = (
                "RECOMMANDATION :\n"
                f"→ Relancer A1 + A2 avec une revue approfondie des données.\n"
                f"→ Vérifier que les variables clés (BM, âge, garantie) "
                f"  sont bien présentes et correctement encodées.\n"
                f"→ Ne pas utiliser ces GLM pour la tarification."
            )

        return f"{niveau1}\n\n{niveau2}\n\n{niveau3}"

    def _afficher_rapport_console(
        self, audit_id, sous_branche, rapport,
        statut_rag, commentaire, res_poisson, res_gamma
    ) -> None:
        """Affiche le rapport dans la console Colab."""
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
        sep   = "═" * 65

        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT A3 GLM | {audit_id}")
        print(sep)
        print(f"  Sous-branche : {sous_branche}")
        print(f"  {emoji} STATUT : {statut_rag}")

        for nom, met in self.metriques.items():
            print(f"\n  GLM {nom.upper()} :")
            print(f"    Variables retenues : {met.get('nb_vars_retenues', 0)}")
            print(f"    AIC                : {met.get('aic', 'N/A')}")
            if 'gini' in met:
                print(f"    Gini               : {met['gini']:.4f}")

        print(f"\n{sep}")
        print("  COMMENTAIRE ACTUAIRE SÉNIOR")
        print(sep)
        for ligne in commentaire.split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    # ══════════════════════════════════════════════════════════════════════════
    # GRAPHIQUES v2 — Style PowerBI/Bloomberg
    # ══════════════════════════════════════════════════════════════════════════

    def _charts_tarif_v3(self, graphiques: dict, res_poisson: dict) -> None:
        """Ajoute les graphiques V3 (core/charts_tarif) au dict `graphiques`.
        Chaque figure est OPTIONNELLE : données manquantes → chart non produit,
        le run continue (même pattern que synthese_mapping : absence = silence)."""
        # Relativités exp(β) du Poisson (fréquence)
        try:
            rel = (res_poisson or {}).get('relativites')
            if rel:
                graphiques['chart_relativites_glm'] = chart_relativites_glm(
                    rel, titre='Relativités GLM Poisson  exp(β)')
        except Exception as e:
            logger.debug(f"chart_relativites_glm non produit : {e}")
        # QQ-plot des résidus de Pearson du Poisson
        try:
            mp = self.modeles.get('poisson')
            rp = getattr(mp, 'resid_pearson', None) if mp is not None else None
            if rp is not None:
                graphiques['chart_residus_qq'] = chart_residus_qq(
                    np.asarray(rp, dtype=float))
        except Exception as e:
            logger.debug(f"chart_residus_qq non produit : {e}")
        # Distribution des fréquences prédites
        try:
            freq = (self.predictions or {}).get('frequence_annuelle')
            if freq is not None and len(freq):
                graphiques['chart_distribution_predictions'] = \
                    chart_distribution_predictions(
                        freq, unite='',
                        titre='Distribution des fréquences prédites')
        except Exception as e:
            logger.debug(f"chart_distribution_predictions non produit : {e}")

    def _generer_graphiques(
        self,
        df_train:      pd.DataFrame,
        df_test:       pd.DataFrame,
        vars_pred:     list,
        res_poisson:   Dict,
        res_gamma:     Dict,
        res_tweedie:   Dict,
        col_freq:      str,
        col_cout:      str,
        col_expo:      str,
    ) -> Dict:
        """
        Génère 4 graphiques GLM style PowerBI/Bloomberg.

        G1 — Coefficients GLM Poisson avec IC 95%
        G2 — Résidus de déviance (Poisson)
        G3 — Courbe de Lorenz GLM
        G4 — Comparaison AIC des 3 modèles
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

        LAYOUT_BASE = dict(
            paper_bgcolor = NAVY,
            plot_bgcolor  = NAVY_L,
            font          = dict(family="Inter, Arial", color=BLANC, size=11),
            margin        = dict(l=16, r=16, t=52, b=16),
            height        = 320,
            hoverlabel    = dict(bgcolor=NAVY_LL, bordercolor=OR,
                                 font_size=12, font_color=BLANC),
            legend        = dict(
                bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                orientation="h", yanchor="bottom", y=1.02,
            ),
        )

        graphiques = {}

        # ── G1 : COEFFICIENTS GLM POISSON avec IC 95% ────────────────────────
        try:
            modele_p = res_poisson.get('modele')
            if modele_p is not None and hasattr(modele_p, 'params'):
                params = modele_p.params
                conf   = modele_p.conf_int()

                # Exclure l'intercept et trier par valeur absolue
                mask    = params.index != 'const'
                noms    = params.index[mask].tolist()
                vals    = params[mask].values.tolist()
                ci_low  = conf.loc[mask, 0].values.tolist()
                ci_high = conf.loc[mask, 1].values.tolist()

                # Tri par valeur absolue décroissante
                ordre   = sorted(range(len(vals)), key=lambda i: abs(vals[i]), reverse=True)
                noms    = [noms[i]    for i in ordre]
                vals    = [vals[i]    for i in ordre]
                ci_low  = [ci_low[i]  for i in ordre]
                ci_high = [ci_high[i] for i in ordre]

                colors  = [ROUGE if v < 0 else OR for v in vals]
                errors  = [abs(h - v) for v, h in zip(vals, ci_high)]

                fig1 = go.Figure()
                fig1.add_trace(go.Bar(
                    x             = vals,
                    y             = noms,
                    orientation   = 'h',
                    marker_color  = colors,
                    marker_line   = dict(color=NAVY, width=1),
                    width         = 0.6,
                    opacity       = 0.85,
                    error_x       = dict(
                        type      = 'data',
                        array     = errors,
                        color     = BLANC,
                        thickness = 1.5,
                        width     = 5,
                    ),
                    # ⚠️⚠️ LES VRAIES BORNES, PAR `customdata` — constat `a3/C4`.
                    # L'infobulle publiait `IC 95% : [0.0000, 0.0000]` sur CHAQUE
                    # barre : deux zéros codés en dur. Une f-string ne peut porter
                    # qu'un scalaire, jamais une valeur PAR POINT — c'est pour cela
                    # que le zéro était là. `customdata` le permet, et les bornes
                    # existaient déjà : elles servent aux barres d'erreur juste
                    # au-dessus. *Aucun nombre n'est calculé ici, il est AFFICHÉ.*
                    customdata    = list(zip(ci_low, ci_high)),
                    hovertemplate = (
                        "<b>%{y}</b><br>"
                        "Coefficient β : <b>%{x:.4f}</b><br>"
                        "IC 95% : [%{customdata[0]:.4f}, %{customdata[1]:.4f}]"
                        "<extra></extra>"
                    ),
                    text          = [f"{v:.3f}" for v in vals],
                    textposition  = 'outside',
                    textfont      = dict(color=BLANC, size=9),
                ))

                fig1.add_vline(x=0, line_color=GRIS, line_width=1.5, line_dash="dot")

                layout1 = dict(**LAYOUT_BASE)
                layout1.update(dict(
                    title = dict(
                        text = "📊 Coefficients GLM Poisson β avec IC 95%",
                        font = dict(color=BLANC, size=13), x=0.01,
                    ),
                    xaxis = dict(
                        title    = dict(text="Valeur du coefficient β",
                                        font=dict(color=GRIS, size=10)),
                        showgrid = True,
                        gridcolor= "rgba(255,255,255,0.05)",
                        tickfont = dict(color=GRIS, size=10),
                        zeroline = False,
                    ),
                    yaxis = dict(
                        tickfont = dict(color=BLANC, size=9),
                        showgrid = False,
                    ),
                    height = max(280, len(noms) * 28 + 80),
                ))
                fig1.update_layout(**layout1)
                graphiques['coefficients_glm'] = fig1

        except Exception as e:
            logger.warning(f"G1 coefficients échoué : {e}")

        # ── G1b : RELATIVITÉS TARIFAIRES exp(β) — Barres horizontales ─────────
        # Sortie commerciale : visualisation des relativités par variable.
        # La barre représente exp(β) — référence = 1.0 (trait vertical).
        # Rouge = aggravant (relativité > 1), Vert = allégant (< 1).
        try:
            modele_p = res_poisson.get('modele')
            rels_p   = res_poisson.get('relativites', {})
            if modele_p is not None and rels_p:
                vars_r  = [v for v in rels_p]
                rel_v   = [rels_p[v]['relativite']  for v in vars_r]
                ic_low  = [rels_p[v]['ic95_low']    for v in vars_r]
                ic_high = [rels_p[v]['ic95_high']   for v in vars_r]
                colors_r= [ROUGE if r > 1 else VERT for r in rel_v]
                errors_r= [abs(h - r) for r, h in zip(rel_v, ic_high)]

                # Tri par relativité décroissante
                ordre_r = sorted(range(len(rel_v)), key=lambda i: rel_v[i], reverse=True)
                vars_r  = [vars_r[i]   for i in ordre_r]
                rel_v   = [rel_v[i]    for i in ordre_r]
                ic_low  = [ic_low[i]   for i in ordre_r]
                ic_high = [ic_high[i]  for i in ordre_r]
                colors_r= [colors_r[i] for i in ordre_r]
                errors_r= [errors_r[i] for i in ordre_r]

                fig_rel = go.Figure()
                fig_rel.add_trace(go.Bar(
                    x             = rel_v,
                    y             = vars_r,
                    orientation   = 'h',
                    marker_color  = colors_r,
                    marker_line   = dict(color=NAVY, width=1),
                    width         = 0.6,
                    opacity       = 0.88,
                    error_x       = dict(
                        type      = 'data',
                        array     = errors_r,
                        color     = BLANC,
                        thickness = 1.5,
                        width     = 5,
                    ),
                    text          = [f"{r:.3f}" for r in rel_v],
                    textposition  = 'outside',
                    textfont      = dict(color=BLANC, size=9),
                    # ⚠️ Même correctif : l'infobulle publiait « IC 95% : [ »
                    # — un crochet ouvert, rien dedans. `ic_low`/`ic_high` sont
                    # lus vingt lignes plus haut pour les barres d'erreur.
                    customdata    = list(zip(ic_low, ic_high)),
                    hovertemplate = (
                        "<b>%{y}</b><br>"
                        "Relativité exp(β) : <b>%{x:.4f}</b><br>"
                        "IC 95% : [%{customdata[0]:.4f}, %{customdata[1]:.4f}]"
                        "<br>Rouge = aggravant · Vert = allégant"
                        "<extra></extra>"
                    ),
                ))
                fig_rel.add_vline(
                    x=1.0, line_color=OR, line_width=1.5, line_dash='dot',
                    annotation_text='Référence = 1.0',
                    annotation_font=dict(color=OR, size=9),
                )
                layout_rel = dict(**LAYOUT_BASE)
                layout_rel.update(dict(
                    title=dict(
                        text='📊 Relativités tarifaires GLM Poisson — exp(β) avec IC 95%',
                        font=dict(color=BLANC, size=13), x=0.01,
                    ),
                    xaxis=dict(
                        title=dict(text='Relativité exp(β) — référence = 1.0',
                                   font=dict(color=GRIS, size=10)),
                        showgrid=True,
                        gridcolor='rgba(255,255,255,0.05)',
                        tickfont=dict(color=GRIS, size=10),
                    ),
                    yaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                    height=max(280, len(vars_r) * 28 + 100),
                ))
                fig_rel.update_layout(**layout_rel)
                graphiques['relativites_poisson'] = fig_rel

        except Exception as e:
            logger.warning(f"G1b relativités échoué : {e}")

        # ── G2 : RÉSIDUS DE DÉVIANCE — Scatter ───────────────────────────────
        try:
            modele_p = res_poisson.get('modele')
            if modele_p is not None and hasattr(modele_p, 'resid_deviance'):
                residus   = modele_p.resid_deviance
                fitted    = modele_p.fittedvalues
                n_plot    = min(2000, len(residus))

                idx_sample = np.random.choice(len(residus), n_plot, replace=False)
                res_plot   = residus.iloc[idx_sample] if hasattr(residus, 'iloc') else residus[idx_sample]
                fit_plot   = fitted.iloc[idx_sample]  if hasattr(fitted, 'iloc')  else fitted[idx_sample]

                # Couleur selon magnitude du résidu
                colors_res = [
                    ROUGE if abs(r) > 2 else AMBRE if abs(r) > 1 else OR
                    for r in res_plot
                ]

                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x             = fit_plot.tolist(),
                    y             = res_plot.tolist(),
                    mode          = 'markers',
                    name          = 'Résidus',
                    marker        = dict(
                        color   = colors_res,
                        size    = 4,
                        opacity = 0.6,
                        line    = dict(color=NAVY, width=0.5),
                    ),
                    hovertemplate = (
                        "Valeur ajustée : %{x:.4f}<br>"
                        "Résidu déviance : <b>%{y:.4f}</b><extra></extra>"
                    ),
                ))

                # Lignes de référence ±2σ
                fig2.add_hline(y=0,  line_color=BLANC, line_width=1.5, line_dash="dot")
                fig2.add_hline(y=2,  line_color=ROUGE, line_width=1, line_dash="dot",
                               annotation_text="+2σ", annotation_font=dict(color=ROUGE, size=9))
                fig2.add_hline(y=-2, line_color=ROUGE, line_width=1, line_dash="dot",
                               annotation_text="-2σ", annotation_font=dict(color=ROUGE, size=9))

                layout2 = dict(**LAYOUT_BASE)
                layout2.update(dict(
                    title = dict(
                        text = "📈 Résidus de déviance — GLM Poisson",
                        font = dict(color=BLANC, size=13), x=0.01,
                    ),
                    xaxis = dict(
                        title    = dict(text="Valeurs ajustées",
                                        font=dict(color=GRIS, size=10)),
                        showgrid = True, gridcolor="rgba(255,255,255,0.05)",
                        tickfont = dict(color=GRIS, size=10), zeroline=False,
                    ),
                    yaxis = dict(
                        title    = dict(text="Résidu de déviance",
                                        font=dict(color=GRIS, size=10)),
                        showgrid = True, gridcolor="rgba(255,255,255,0.05)",
                        tickfont = dict(color=GRIS, size=10), zeroline=False,
                    ),
                    annotations = [dict(
                        x=0.02, y=0.97, xref='paper', yref='paper',
                        text=f"Or=OK · Ambre=|r|>1 · Rouge=|r|>2 · n={n_plot:,}",
                        showarrow=False, font=dict(color=GRIS, size=9),
                    )],
                ))
                fig2.update_layout(**layout2)
                graphiques['residus_deviance'] = fig2

        except Exception as e:
            logger.warning(f"G2 résidus échoué : {e}")

        # ── G3 : COURBE DE LORENZ GLM ─────────────────────────────────────────
        try:
            metriques_p = res_poisson.get('metriques', {})
            gini_p      = metriques_p.get('gini', 0)
            metriques_g = res_gamma.get('metriques', {})
            gini_g      = metriques_g.get('gini', 0)
            metriques_t = res_tweedie.get('metriques', {})
            gini_t      = metriques_t.get('gini', 0)

            t = np.linspace(0, 1, 200)

            fig3 = go.Figure()

            # Diagonale
            fig3.add_trace(go.Scatter(
                x=t.tolist(), y=t.tolist(),
                mode='lines', name='Aléatoire (Gini=0)',
                line=dict(color=GRIS, width=1.5, dash='dot'),
                hoverinfo='skip',
            ))

            for (label, gini, color, dash, width) in [
                (f'Poisson (Gini={gini_p:.3f})',  gini_p, OR,    'solid', 2.5),
                (f'Gamma (Gini={gini_g:.3f})',    gini_g, VERT,  'dash',  1.8),
                (f'Tweedie (Gini={gini_t:.3f})',  gini_t, AMBRE, 'dot',   1.8),
            ]:
                if gini > 0.001:
                    lorenz = t ** (1 / (1 + gini * 2))
                else:
                    lorenz = t
                fig3.add_trace(go.Scatter(
                    x=t.tolist(), y=lorenz.tolist(),
                    mode='lines', name=label,
                    line=dict(color=color, width=width, dash=dash),
                    hovertemplate=(
                        f"<b>{label}</b><br>"
                        "% contrats : %{x:.1%}<br>"
                        "% sinistres : %{y:.1%}<extra></extra>"
                    ),
                ))

            layout3 = dict(**LAYOUT_BASE)
            layout3.update(dict(
                title = dict(
                    text = "📈 Courbe de Lorenz — GLM Poisson · Gamma · Tweedie",
                    font = dict(color=BLANC, size=13), x=0.01,
                ),
                xaxis = dict(
                    title=dict(text="% contrats", font=dict(color=GRIS, size=10)),
                    tickformat=".0%", showgrid=True,
                    gridcolor="rgba(255,255,255,0.05)", tickfont=dict(color=GRIS, size=10),
                ),
                yaxis = dict(
                    title=dict(text="% sinistres cumulés", font=dict(color=GRIS, size=10)),
                    tickformat=".0%", showgrid=True,
                    gridcolor="rgba(255,255,255,0.05)", tickfont=dict(color=GRIS, size=10),
                ),
            ))
            fig3.update_layout(**layout3)
            graphiques['lorenz_glm'] = fig3

        except Exception as e:
            logger.warning(f"G3 Lorenz GLM échoué : {e}")

        # ── G4 : COMPARAISON AIC DES 3 MODÈLES ───────────────────────────────
        try:
            modeles_aic = ['Poisson', 'Gamma', 'Tweedie']
            aics = [
                res_poisson.get('metriques', {}).get('aic', 0),
                res_gamma.get('metriques', {}).get('aic', 0),
                res_tweedie.get('metriques', {}).get('aic', 0),
            ]
            ginis = [
                res_poisson.get('metriques', {}).get('gini', 0),
                res_gamma.get('metriques', {}).get('gini', 0),
                res_tweedie.get('metriques', {}).get('gini', 0),
            ]
            colors4 = [OR, VERT, AMBRE]

            fig4 = make_subplots(specs=[[{"secondary_y": True}]])

            fig4.add_trace(go.Bar(
                x            = modeles_aic,
                y            = aics,
                name         = "AIC (bas = meilleur)",
                marker_color = colors4,
                marker_line  = dict(color=NAVY, width=1),
                width        = 0.4,
                opacity      = 0.85,
                hovertemplate= "<b>%{x}</b><br>AIC : <b>%{y:,.0f}</b><extra></extra>",
                text         = [f"{a:,.0f}" for a in aics],
                textposition = 'outside',
                textfont     = dict(color=BLANC, size=11),
            ), secondary_y=False)

            fig4.add_trace(go.Scatter(
                x             = modeles_aic,
                y             = ginis,
                mode          = 'lines+markers',
                name          = "Gini (haut = meilleur)",
                line          = dict(color=BLANC, width=2.5, shape='spline', smoothing=0.5),
                marker        = dict(color=colors4, size=10,
                                     line=dict(color=NAVY, width=2)),
                hovertemplate = "<b>%{x}</b><br>Gini : <b>%{y:.4f}</b><extra></extra>",
            ), secondary_y=True)

            fig4.update_layout(
                title         = dict(
                    text = "📊 AIC & Gini — Comparaison des 3 GLM",
                    font = dict(color=BLANC, size=13), x=0.01,
                ),
                paper_bgcolor = NAVY, plot_bgcolor = NAVY_L,
                font          = dict(family="Inter, Arial", color=BLANC),
                margin        = dict(l=16, r=16, t=52, b=16),
                height        = 300,
                hoverlabel    = dict(bgcolor=NAVY_LL, bordercolor=OR,
                                     font_size=12, font_color=BLANC),
                legend        = dict(bgcolor="rgba(0,0,0,0)",
                                     font=dict(color=BLANC, size=10),
                                     orientation="h", yanchor="bottom", y=1.02),
                bargap        = 0.4,
            )
            fig4.update_xaxes(showgrid=False, tickfont=dict(color=GRIS))
            fig4.update_yaxes(
                title_text="AIC", title_font=dict(color=GRIS, size=10),
                showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                tickfont=dict(color=GRIS), secondary_y=False,
            )
            fig4.update_yaxes(
                title_text="Gini", title_font=dict(color=GRIS, size=10),
                showgrid=False, tickfont=dict(color=GRIS), secondary_y=True,
            )
            graphiques['aic_comparaison'] = fig4

        except Exception as e:
            logger.warning(f"G4 AIC échoué : {e}")

        return graphiques


    def _valider_hypotheses_glm(
        self,
        df_train: object,
        predictions: Dict,
        metriques: Dict,
    ) -> Dict:
        """
        Validation complète des hypothèses GLM actuariel — 4 hypothèses.

        H1 — Sur-dispersion Poisson
             Ratio Var(Y)/E(Y) — Poisson suppose Var = E.
             Ratio < 2 → Poisson valide ✅
             Ratio ∈ [2,5] → sur-dispersion modérée → Quasi-Poisson ⚠️
             Ratio > 5 → sur-dispersion forte → NegBin ❌

        H2 — Homoscédasticité des résidus de Pearson
             Les résidus (Y - μ̂) / √μ̂ doivent avoir une VARIANCE
             constante quelle que soit la valeur prédite μ̂.
             Ratio variance max/min entre quintiles de μ̂ < 2.0 → homoscédastique ✅
             Un CV élevé sur les déciles extrêmes signale un modèle
             mal spécifié pour les risques forts ou faibles.
             Réf. : Mildenhall (1999) — GLM for Insurance Ratemaking.

        H3 — Qualité d'ajustement (Gini)
             Gini ≥ 0.15 → bon ajustement ✅
             Gini ∈ [0.08,0.15] → acceptable ⚠️
             Gini < 0.08 → insuffisant ❌

        H4 — Stabilité des relativités (bootstrap)
             On recalibre le GLM Poisson sur 5 sous-échantillons
             bootstrap (80% du train). Pour chaque variable, on
             calcule le CV des relativités exp(β).
             CV < 15% → relativité stable et défendable ACPR ✅
             CV ∈ [15%,30%] → relativité fragile ⚠️
             CV > 30% → relativité non défendable ❌
             Réf. : Goldburd et al. (2016) — GLM for P&C Insurance.
        """
        import numpy as np

        # ── H1 — Sur-dispersion Poisson ───────────────────────────────────────
        try:
            col_freq = next(
                (c for c in ['nb_sinistres', 'frequence', 'freq']
                 if hasattr(df_train, 'columns') and c in df_train.columns),
                None
            )
            if col_freq:
                y = df_train[col_freq].values.astype(float)
                mean_y     = float(np.mean(y))
                var_y      = float(np.var(y))
                ratio_disp = var_y / max(mean_y, 1e-6)
            else:
                mean_y, var_y, ratio_disp = None, None, None
        except Exception:
            mean_y, var_y, ratio_disp = None, None, None

        # ⚠️ UNE HYPOTHÈSE NON MESURÉE NE REND PLUS VERT. Le repli posait
        # `(0.05, 0.065, 1.30)` en dur : sans colonne de fréquence, H1
        # publiait « Var/E = 1.30 < 2 → Distribution Poisson valide ✅ » sur
        # trois chiffres que personne n'avait calculés — et H1 plafonne le
        # statut global. C'est le défaut déjà corrigé dans A4 (« une
        # calibration non testée n'est pas une calibration validée », défaut
        # AMBRE et écart None) et jamais reporté ici. Le sentinel `None`
        # traverse jusqu'à la publication, comme pour H5.
        if ratio_disp is None:
            h1_statut = "AMBRE"
            h1_msg    = ("Sur-dispersion NON mesurée — aucune colonne de "
                         "fréquence exploitable dans df_train ⚠️")
            h1_conseil= ("Fournir df_train avec 'nb_sinistres' (ou 'frequence', "
                         "'freq') : sans elle, l'hypothèse Var=E n'est pas testée")
        elif ratio_disp < 2.0:
            h1_statut = "VERT"
            h1_msg    = f"Var/E = {ratio_disp:.2f} < 2 → Distribution Poisson valide ✅"
            h1_conseil= "GLM Poisson adapté — hypothèse Var=E vérifiée"
        elif ratio_disp < 5.0:
            h1_statut = "AMBRE"
            h1_msg    = f"Var/E = {ratio_disp:.2f} ∈ [2,5] → Sur-dispersion modérée ⚠️"
            h1_conseil= "Envisager GLM Quasi-Poisson (coefficient de dispersion φ libre)"
        else:
            h1_statut = "ROUGE"
            h1_msg    = f"Var/E = {ratio_disp:.2f} > 5 → Sur-dispersion forte ❌"
            h1_conseil= "GLM Poisson inadapté — utiliser Négative Binomiale (NegBin)"

        # ── H2 — Homoscédasticité des résidus de Pearson ─────────────────────
        # Résidus de Pearson (Y−μ̂)/√μ̂ : sous une spécification Poisson CORRECTE
        # ils ont une variance ≈ 1 sur TOUTE la plage de μ̂ (V(μ)=μ pour Poisson →
        # résidu standardisé à variance unitaire). On teste l'HÉTÉROSCÉDASTICITÉ =
        # leur variance VARIE-T-ELLE selon le niveau de risque ? Métrique = ratio
        # var_max/var_min entre 5 quintiles de μ̂ (EFFET DE TAILLE, sans dimension,
        # INSENSIBLE À N — contrairement à un test de significativité type
        # Breusch-Pagan dont la p-valeur → 0 sur les grands portefeuilles
        # actuariels et flaguerait ROUGE tout modèle). Bon modèle : variances
        # ≈ [1,1,1,1,1] → ratio ≈ 1 (mesuré auto sain 1.07) ; sur-dispersion
        # sévère → ~2.9 (AMBRE).
        # ⚠ ANCIENNE métrique max(std_quintile/std_global) < 0.30 : CASSÉE —
        #   valait ≈1.0 pour un modèle HOMOSCÉDASTIQUE (chaque quintile a std ≈
        #   std_global), seuil <0.30 INATTEIGNABLE → ROUGE sur TOUT modèle.
        try:
            modele_p = self.modeles.get('poisson')
            if modele_p is not None and hasattr(modele_p, 'fittedvalues'):
                mu_hat      = np.asarray(modele_p.fittedvalues, dtype=float)
                res_pearson = np.asarray(getattr(modele_p, 'resid_pearson', []),
                                         dtype=float)
                if res_pearson.size != mu_hat.size:
                    # repli : recalcul manuel depuis la cible d'entraînement
                    col_freq2 = next(
                        (c for c in ['nb_sinistres', 'frequence', 'freq']
                         if hasattr(df_train, 'columns') and c in df_train.columns),
                        None)
                    res_pearson = (
                        (df_train[col_freq2].values.astype(float) - mu_hat)
                        / np.sqrt(np.maximum(mu_hat, 1e-6))
                        if col_freq2 and len(mu_hat) == len(df_train)
                        else np.array([]))
                if res_pearson.size >= 50:
                    quintiles = [
                        d for d in np.array_split(res_pearson[np.argsort(mu_hat)], 5)
                        if len(d) > 5]
                    var_par_quintile = [float(np.var(d)) for d in quintiles]
                    ratio_variance = (
                        max(var_par_quintile) / max(min(var_par_quintile), 1e-9)
                        if len(var_par_quintile) >= 2 else 1.0)
                else:
                    ratio_variance, var_par_quintile = None, []
            else:
                ratio_variance, var_par_quintile = None, []
        except Exception:
            ratio_variance, var_par_quintile = None, []

        # ⚠️ MÊME DÉFAUT QUE H1, DANS LA MÊME FONCTION : le repli posait
        # `ratio_variance = 1.0`, c'est-à-dire la valeur d'un modèle
        # PARFAITEMENT homoscédastique. Sans modèle Poisson ajusté, sans
        # résidus, ou sur moins de 50 observations, H2 publiait donc
        # « ratio = 1.00 < 2.0 → Homoscédasticité ✅ » sans avoir regardé un
        # seul résidu.
        if ratio_variance is None:
            h2_statut = "AMBRE"
            h2_msg    = ("Homoscédasticité NON mesurée — résidus de Pearson "
                         "indisponibles ou effectif insuffisant (< 50) ⚠️")
            h2_conseil= ("Le GLM Poisson doit être ajusté et df_train fourni "
                         "pour que la variance résiduelle soit testée")
        elif ratio_variance < 2.0:
            h2_statut = "VERT"
            h2_msg    = f"Ratio variance résidus Pearson (max/min quintiles) = {ratio_variance:.2f} < 2.0 → Homoscédasticité ✅"
            h2_conseil= "Dispersion homogène entre bandes de risque — le GLM est bien spécifié sur toute la plage"
        elif ratio_variance < 3.0:
            h2_statut = "AMBRE"
            h2_msg    = f"Ratio variance résidus Pearson (max/min quintiles) = {ratio_variance:.2f} ∈ [2.0, 3.0) → Hétéroscédasticité légère ⚠️"
            h2_conseil= "La dispersion varie selon le risque — vérifier les bandes extrêmes · interactions · Tweedie"
        else:
            h2_statut = "ROUGE"
            h2_msg    = f"Ratio variance résidus Pearson (max/min quintiles) = {ratio_variance:.2f} ≥ 3.0 → Hétéroscédasticité forte ❌"
            h2_conseil= "Variance résiduelle très inégale entre risques forts et faibles — revoir la spécification / segmentation"

        # ── H3 — Qualité d'ajustement (Gini) ─────────────────────────────────
        gini_poisson = metriques.get('poisson', {}).get('gini', 0)
        gini_gamma   = metriques.get('gamma',   {}).get('gini', 0)
        gini_tweedie = metriques.get('tweedie', {}).get('gini', 0)
        gini_max     = max(gini_poisson, gini_gamma, gini_tweedie)

        # ⚠️ LE SEUIL ANNONCÉ EST DÉSORMAIS LE SEUIL APPLIQUÉ. La docstring
        # ci-dessus décrit TROIS bandes — « Gini ∈ [0.08,0.15] → acceptable
        # ⚠️ » — et le code en appliquait QUATRE, dont une seconde bande VERTE
        # sur [0.10, 0.15]. Mesuré : un Gini de 0,12 sortait VERT là où
        # l'échelle publiée le donne AMBRE. C'est le statut, pas le message,
        # que lit le verrou d'A6 : un ajustement que le module lui-même dit
        # « à enrichir » certifiait la chaîne entière. Les deux messages fins
        # sont conservés — ils distinguent [0.10,0.15] de [0.08,0.10] — mais
        # ils rendent tous deux le statut que l'échelle annonce.
        if gini_max >= 0.15:
            h3_statut = "VERT"
            h3_msg    = f"Gini max = {gini_max:.4f} ≥ 0.15 → Bon ajustement GLM ✅"
            h3_conseil= "Le GLM explique bien la sinistralité — défendable devant l'ACPR"
        elif gini_max >= 0.10:
            h3_statut = "AMBRE"
            h3_msg    = f"Gini max = {gini_max:.4f} ∈ [0.10, 0.15] → Ajustement acceptable ⚠️"
            h3_conseil= "GLM utilisable — enrichir avec plus de variables actuarielles"
        elif gini_max >= 0.08:
            h3_statut = "AMBRE"
            h3_msg    = f"Gini max = {gini_max:.4f} ∈ [0.08, 0.10] → Ajustement limite ⚠️"
            h3_conseil= "Ajouter variables bonus-malus, zone géographique, usage véhicule"
        else:
            h3_statut = "ROUGE"
            h3_msg    = f"Gini max = {gini_max:.4f} < 0.08 → Ajustement insuffisant ❌"
            h3_conseil= "Données insuffisantes ou modèle mal spécifié — revoir la sélection de variables"

        # ── H4 — Stabilité des relativités (bootstrap) ───────────────────────
        # 5 sous-échantillons bootstrap à 80% du train.
        # CV des relativités exp(β) par variable.
        # Réf. : Goldburd et al. (2016) — GLM for P&C Insurance Ratemaking.
        # ⚠️ LE DÉFAUT LE PLUS VISIBLE DES TROIS : le statut par défaut était
        # "VERT" ALORS QUE SON PROPRE MESSAGE DIT « non testée ». Le verdict
        # et le message se contredisaient dans le même dictionnaire, et c'est
        # le VERDICT que lit le verrou d'A6. `rel_cv_max` valait 0.0 — le CV
        # d'une relativité parfaitement stable — pour un bootstrap jamais
        # lancé. Défaut AMBRE et sentinel None, comme H4 dans A4.
        h4_statut    = "AMBRE"
        h4_msg       = "Stabilité relativités NON testée (modèle ou données non disponibles) ⚠️"
        h4_conseil   = "Fournir df_train avec données pour le test bootstrap"
        rel_cv_max   = None
        rel_instables= []
        try:
            import statsmodels.api as sm
            from statsmodels.genmod import families
            modele_p2  = self.modeles.get('poisson')
            vars_ret   = metriques.get('poisson', {}).get('vars_retenues', [])
            col_freq3  = next(
                (c for c in ['nb_sinistres', 'frequence', 'freq']
                 if hasattr(df_train, 'columns') and c in df_train.columns),
                None
            )
            col_expo3  = next(
                (c for c in ['exposition', 'exposure', 'expo']
                 if hasattr(df_train, 'columns') and c in df_train.columns),
                None
            )
            if (modele_p2 is not None and vars_ret and col_freq3
                    and hasattr(df_train, 'sample') and len(df_train) >= 200):
                n_boot = 5
                rel_boot = {v: [] for v in vars_ret}
                np.random.seed(42)
                for _ in range(n_boot):
                    idx   = np.random.choice(len(df_train), int(0.80 * len(df_train)), replace=True)
                    dft   = df_train.iloc[idx]
                    Xb    = sm.add_constant(dft[vars_ret].fillna(0))
                    ob    = (np.log(np.maximum(dft[col_expo3], 1e-6))
                             if col_expo3 else np.zeros(len(dft)))
                    try:
                        mb = sm.GLM(
                            dft[col_freq3], Xb,
                            family=families.Poisson(link=families.links.Log()),
                            offset=ob
                        ).fit(maxiter=100, disp=False)
                        for v in vars_ret:
                            if v in mb.params.index:
                                rel_boot[v].append(float(np.exp(mb.params[v])))
                    except Exception:
                        pass

                cv_par_var = {}
                for v, vals in rel_boot.items():
                    if len(vals) >= 3:
                        cv_v = float(np.std(vals) / max(np.mean(vals), 1e-6))
                        cv_par_var[v] = round(cv_v, 4)

                if cv_par_var:
                    rel_cv_max    = max(cv_par_var.values())
                    rel_instables = [v for v, cv in cv_par_var.items() if cv > 0.15]

                    if rel_cv_max < 0.15:
                        h4_statut = "VERT"
                        h4_msg    = f"CV max relativités = {rel_cv_max:.3f} < 15% → Toutes stables ✅"
                        h4_conseil= "Relativités défendables devant l'ACPR et l'actuaire désigné"
                    elif rel_cv_max < 0.30:
                        h4_statut = "AMBRE"
                        h4_msg    = (f"CV max = {rel_cv_max:.3f} ∈ [15%,30%] — "                                     f"{len(rel_instables)} var(s) fragile(s) : {rel_instables[:3]} ⚠️")
                        h4_conseil= "Documenter les relativités instables · Élargir l'échantillon si possible"
                    else:
                        h4_statut = "ROUGE"
                        h4_msg    = (f"CV max = {rel_cv_max:.3f} > 30% — "                                     f"{len(rel_instables)} var(s) non défendables : {rel_instables[:3]} ❌")
                        h4_conseil= "Relativités trop instables — réduire le nombre de variables ou augmenter les données"
        except Exception as e_boot:
            logger.debug(f"H4 bootstrap échoué : {e_boot}")

        # ── H5 — Déviance résiduelle (ajustement global du GLM Poisson) ───────
        # deviance / df_resid ≈ 1 pour un Poisson bien ajusté ; > 1 signale une
        # sur-dispersion / mauvaise spécification GLOBALE (complément de H1, qui ne
        # regarde que Var/E des données brutes, avant modèle).
        try:
            mp5 = self.modeles.get('poisson')
            ratio_dev = (float(mp5.deviance) / max(float(mp5.df_resid), 1e-6)
                         if (mp5 is not None and hasattr(mp5, 'deviance')
                             and hasattr(mp5, 'df_resid')) else None)
        except Exception:
            ratio_dev = None
        _dev_disp = f"{ratio_dev:.2f}" if ratio_dev is not None else "N/A"
        if ratio_dev is None:
            h5_statut, h5_msg = "AMBRE", "Déviance résiduelle non calculable (GLM Poisson absent) ⚠️"
            h5_conseil = "Vérifier l'ajustement du GLM Poisson"
        elif ratio_dev < 1.5:
            h5_statut, h5_msg = "VERT", f"déviance/df = {_dev_disp} < 1.5 → bon ajustement global ✅"
            h5_conseil = "Ajustement satisfaisant — pas de sur-dispersion résiduelle"
        elif ratio_dev < 2.0:
            h5_statut, h5_msg = "AMBRE", f"déviance/df = {_dev_disp} ∈ [1.5,2.0] → ajustement partiel ⚠️"
            h5_conseil = "Envisager des interactions ou un Quasi-Poisson (φ libre)"
        else:
            h5_statut, h5_msg = "ROUGE", f"déviance/df = {_dev_disp} > 2.0 → mauvais ajustement ❌"
            h5_conseil = "Sur-dispersion forte — NegBin ou variables manquantes"

        statuts = [h1_statut, h2_statut, h3_statut, h4_statut, h5_statut]
        statut_global = "ROUGE" if "ROUGE" in statuts else "AMBRE" if "AMBRE" in statuts else "VERT"
        conclusion = {
            "VERT":  "✅ GLM validé — 5 hypothèses satisfaites (distribution, homoscédasticité, Gini, stabilité, déviance)",
            "AMBRE": "⚠️ GLM utilisable avec précautions — documenter les points signalés",
            "ROUGE": "❌ GLM à revoir — hypothèses non satisfaites",
        }[statut_global]

        return {
            # ⚠️ UNE GRANDEUR NON MESURÉE SE PUBLIE `None`, ET SON TITRE DIT
            # « non mesurée » — il ne montre pas un nombre. C'est le motif que
            # H5 portait déjà seul dans cette fonction.
            "h1_poisson": {
                "ratio_disp": round(ratio_disp, 3) if ratio_disp is not None else None,
                "mean_y":     round(mean_y, 6) if mean_y is not None else None,
                "var_y":      round(var_y, 6) if var_y is not None else None,
                "statut":     h1_statut,
                "message":    h1_msg,
                "conseil":    h1_conseil,
                "titre_graphique": (
                    f"{'✅' if h1_statut=='VERT' else '⚠️' if h1_statut=='AMBRE' else '❌'} "
                    + (f"Distribution Poisson — Var/E = {ratio_disp:.2f}"
                       if ratio_disp is not None
                       else "Distribution Poisson — Var/E non mesurée")),
            },
            "h2_homosc": {
                "ratio_variance":   round(ratio_variance, 4) if ratio_variance is not None else None,
                "var_par_quintile": [round(v, 4) for v in var_par_quintile],
                "statut":        h2_statut,
                "message":       h2_msg,
                "conseil":       h2_conseil,
                "titre_graphique": (
                    f"{'✅' if h2_statut=='VERT' else '⚠️' if h2_statut=='AMBRE' else '❌'} "
                    + (f"Homoscédasticité — ratio variance max/min = {ratio_variance:.2f}"
                       if ratio_variance is not None
                       else "Homoscédasticité — ratio variance non mesuré")),
            },
            "h3_ajustement": {
                "gini_poisson": round(gini_poisson, 4),
                "gini_gamma":   round(gini_gamma, 4),
                "gini_tweedie": round(gini_tweedie, 4),
                "gini_max":     round(gini_max, 4),
                "statut":       h3_statut,
                "message":      h3_msg,
                "conseil":      h3_conseil,
                "titre_graphique": f"{'✅' if h3_statut=='VERT' else '⚠️' if h3_statut=='AMBRE' else '❌'} Gini GLM = {gini_max:.4f}",
            },
            "h4_stabilite": {
                "cv_max":           round(rel_cv_max, 4) if rel_cv_max is not None else None,
                "vars_instables":   rel_instables,
                "n_instables":      len(rel_instables),
                "statut":           h4_statut,
                "message":          h4_msg,
                "conseil":          h4_conseil,
                "titre_graphique":  (
                    f"{'✅' if h4_statut=='VERT' else '⚠️' if h4_statut=='AMBRE' else '❌'} "
                    + (f"Stabilité relativités — CV max = {rel_cv_max:.3f}"
                       if rel_cv_max is not None
                       else "Stabilité relativités — CV non mesuré")),
            },
            "h5_deviance": {
                "ratio_deviance_df": round(ratio_dev, 3) if ratio_dev is not None else None,
                "statut":            h5_statut,
                "message":           h5_msg,
                "conseil":           h5_conseil,
                "titre_graphique":   f"{'✅' if h5_statut=='VERT' else '⚠️' if h5_statut=='AMBRE' else '❌'} Déviance/df = {_dev_disp}",
            },
            "statut_global": statut_global,
            "conclusion":    conclusion,
        }

    def _graphiques_validation_glm(self, val_glm: Dict, metriques: Dict) -> Dict:
        """4 graphiques auto-explicatifs validation GLM."""
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

        # G1 — Comparaison Gini 3 modèles GLM
        try:
            modeles_glm = ["GLM Poisson", "GLM Gamma", "GLM Tweedie"]
            ginis_glm   = [
                val_glm["h3_ajustement"]["gini_poisson"],
                val_glm["h3_ajustement"]["gini_gamma"],
                val_glm["h3_ajustement"]["gini_tweedie"],
            ]
            gini_max = val_glm["h3_ajustement"]["gini_max"]
            colors_glm = [OR if g == gini_max else "rgba(52,152,219,0.6)" for g in ginis_glm]
            statut_h3  = val_glm["h3_ajustement"]["statut"]
            couleur_h3 = VERT if statut_h3=="VERT" else AMBRE if statut_h3=="AMBRE" else ROUGE

            fig1 = go.Figure(go.Bar(
                x=modeles_glm, y=ginis_glm,
                marker_color=colors_glm,
                marker_line=dict(color=NAVY, width=1),
                width=0.45, opacity=0.88,
                text=[f"{g:.4f}" for g in ginis_glm],
                textposition="outside",
                textfont=dict(color=BLANC, size=11),
                hovertemplate="<b>%{x}</b><br>Gini : %{y:.4f}<extra></extra>",
            ))
            fig1.add_hline(y=0.10, line_color=AMBRE, line_width=1.5, line_dash="dot",
                          annotation_text="Seuil acceptable 0.10",
                          annotation_font=dict(color=AMBRE, size=9))
            fig1.add_hline(y=0.15, line_color=VERT, line_width=1.5, line_dash="dot",
                          annotation_text="Seuil bon 0.15",
                          annotation_font=dict(color=VERT, size=9))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(
                    text=val_glm["h3_ajustement"]["titre_graphique"] + " — Barre dorée = meilleur GLM",
                    font=dict(color=couleur_h3, size=11), x=0.01
                ),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(visible=False), bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 Le Gini mesure le pouvoir discriminant du GLM. Au-dessus de 0.10 = le modèle différencie bien les bons et mauvais risques.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig1.update_layout(**l1)
            graphiques["gini_comparaison_glm"] = fig1
        except Exception as e:
            logger.warning(f"G1 Gini GLM : {e}")

        # G2 — Jauge sur-dispersion Poisson
        try:
            ratio = val_glm["h1_poisson"]["ratio_disp"]
            # ⚠️ PAS DE JAUGE SUR UNE GRANDEUR NON MESURÉE : H1 publie
            # désormais `None` quand la sur-dispersion n'a pas été calculée.
            # Une aiguille posée sur une valeur par défaut se lit comme une
            # mesure.
            if ratio is None:
                raise ValueError("sur-dispersion non mesurée — jauge non produite")
            statut_h1  = val_glm["h1_poisson"]["statut"]
            couleur_h1 = VERT if statut_h1=="VERT" else AMBRE if statut_h1=="AMBRE" else ROUGE

            fig2 = go.Figure(go.Indicator(
                mode="gauge+number",
                value=ratio,
                title=dict(
                    text=val_glm["h1_poisson"]["titre_graphique"],
                    font=dict(color=couleur_h1, size=11)
                ),
                number=dict(font=dict(color=couleur_h1, size=28), valueformat=".2f"),
                gauge=dict(
                    axis=dict(range=[0, 8], tickfont=dict(color=GRIS, size=8),
                             tickvals=[0, 1, 2, 5, 8],
                             ticktext=["0", "1 Poisson", "2 Limite", "5 Fort", "8"]),
                    bar=dict(color=couleur_h1, thickness=0.25),
                    bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0, 2],  color="rgba(46,204,113,0.12)"),
                        dict(range=[2, 5],  color="rgba(243,156,18,0.12)"),
                        dict(range=[5, 8],  color="rgba(231,76,60,0.12)"),
                    ],
                    threshold=dict(line=dict(color=VERT, width=3), thickness=0.8, value=2.0),
                ),
            ))
            fig2.update_layout(
                paper_bgcolor=NAVY, font=dict(color=BLANC),
                margin=dict(l=30, r=30, t=80, b=50), height=300,
                annotations=[dict(
                    text=f"💡 {val_glm['h1_poisson']['conseil']}",
                    xref="paper", yref="paper", x=0.5, y=-0.12,
                    font=dict(color=GRIS, size=9), showarrow=False, align="center"
                )],
            )
            graphiques["sur_dispersion_poisson"] = fig2
        except Exception as e:
            logger.warning(f"G2 Poisson : {e}")

        # G3 — Jauge Durbin-Watson
        try:
            dw = val_glm["h2_homosc"]["dw_stat"]
            statut_h2  = val_glm["h2_homosc"]["statut"]
            couleur_h2 = VERT if statut_h2=="VERT" else AMBRE if statut_h2=="AMBRE" else ROUGE

            fig3 = go.Figure(go.Indicator(
                mode="gauge+number",
                value=dw,
                title=dict(
                    text=val_glm["h2_homosc"]["titre_graphique"],
                    font=dict(color=couleur_h2, size=11)
                ),
                number=dict(font=dict(color=couleur_h2, size=28), valueformat=".3f"),
                gauge=dict(
                    axis=dict(range=[0, 4], tickfont=dict(color=GRIS, size=8),
                             tickvals=[0, 1, 1.5, 2, 2.5, 3, 4],
                             ticktext=["0", "1", "1.5", "2 Idéal", "2.5", "3", "4"]),
                    bar=dict(color=couleur_h2, thickness=0.25),
                    bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0, 1.5],   color="rgba(231,76,60,0.12)"),
                        dict(range=[1.5, 2.5],  color="rgba(46,204,113,0.12)"),
                        dict(range=[2.5, 4.0],  color="rgba(231,76,60,0.12)"),
                    ],
                    threshold=dict(line=dict(color=VERT, width=3), thickness=0.8, value=2.0),
                ),
            ))
            fig3.update_layout(
                paper_bgcolor=NAVY, font=dict(color=BLANC),
                margin=dict(l=30, r=30, t=80, b=50), height=300,
                annotations=[dict(
                    text=f"💡 {val_glm['h2_homosc']['conseil']}",
                    xref="paper", yref="paper", x=0.5, y=-0.12,
                    font=dict(color=GRIS, size=9), showarrow=False, align="center"
                )],
            )
            graphiques["durbin_watson"] = fig3
        except Exception as e:
            logger.warning(f"G3 DW : {e}")

        # G4 — Scorecard validation GLM
        try:
            # ⚠️⚠️ LA SCORECARD SE CONSTRUIT DEPUIS CE QUI EST CALCULÉ — constat
            # `a3/C9`. Elle portait une liste ÉCRITE EN DUR de 4 entrées, une
            # légende annonçant « 3 ✅ », et le module calcule **5 hypothèses** :
            # `h5_deviance` — une PLAFONNANTE — n'apparaissait nulle part.
            # Trois comptes différents pour la même chose, dans le même
            # graphique. On les dérive donc tous du dictionnaire de validation.
            #
            # ⚠️ ET CELA SUPPRIME AUSSI UN FAUX VERT : la ligne H4 lisait
            # `.get("h4_stabilite", {}).get("statut", "VERT")` — une hypothèse
            # ABSENTE s'affichait VERTE. En construisant depuis les clés
            # réellement présentes, une hypothèse absente **n'apparaît plus**
            # au lieu d'apparaître verte. *Le constat `a3/C3` reste ouvert sur
            # le calcul lui-même ; ce que ce correctif ferme, c'est la
            # scorecard qui l'affichait.*
            _LIBELLES_H = {
                "h1_poisson":     "H1 — Distribution Poisson",
                "h2_homosc":      "H2 — Homoscédasticité résidus",
                "h3_ajustement":  "H3 — Qualité ajustement Gini",
                "h4_stabilite":   "H4 — Stabilité relativités",
                "h5_deviance":    "H5 — Déviance résiduelle",
            }
            items = [
                (_LIBELLES_H.get(cle, cle), val.get("statut", "AMBRE"),
                 val.get("message", ""), val.get("conseil", ""))
                for cle, val in val_glm.items()
                if isinstance(val, dict) and "statut" in val
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
            statut_g  = val_glm["statut_global"]
            couleur_g = VERT if statut_g=="VERT" else AMBRE if statut_g=="AMBRE" else ROUGE
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(
                    text=f"Scorecard GLM — {val_glm['conclusion']}",
                    font=dict(color=couleur_g, size=10), x=0.01
                ),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text=(f"💡 {len(items)} ✅ = GLM validé, défendable devant "
                          f"l'ACPR et l'actuaire désigné."),
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig4.update_layout(**l4)
            graphiques["scorecard_validation_glm"] = fig4
        except Exception as e:
            logger.warning(f"G4 scorecard GLM : {e}")

        return graphiques

    # ══════════════════════════════════════════════════════════════════════════
    # CRÉDIBILITÉ BÜHLMANN-STRAUB
    # Réf. : Bühlmann & Straub (1970) ASTIN Bulletin 5(2) ;
    #        Mack (1994) "Measuring the Variability of Chain Ladder Reserve Estimates"
    # ══════════════════════════════════════════════════════════════════════════

    def _credibilite_buhlmann_straub(
        self,
        df:             pd.DataFrame,
        predictions:    Dict[str, Any],
        col_freq:       str,
        col_expo:       str,
    ) -> Dict[str, Any]:
        """
        Crédibilité Bühlmann-Straub pour tarification de groupe.

        Principe : pondère la prime observée du groupe avec la prime de marché
        selon un facteur Z ∈ [0,1] qui dépend du volume d'exposition.

        Formule :
            Z_i = n_i / (n_i + k)
            k   = σ²_intra / σ²_entre
            Prime_crédibilisée_i = Z_i × μ_obs_i + (1 - Z_i) × μ_marché

        où :
            μ_obs_i  = taux de sinistralité observé du groupe i
            μ_marché = prime pure GLM (prédiction)
            n_i      = exposition pondérée du groupe i (en véhicules-années)
            σ²_intra = composante de variance de processus (Poisson → μ_marché)
            σ²_entre = variance inter-groupes (estimée par méthode des moments)

        Colonnes requises pour activation :
            - Une colonne de groupe : id_flotte, id_entreprise, id_assure,
              id_client, flotte_id, groupe_id, entreprise_id
            - La colonne d'exposition (col_expo)
            - La colonne de fréquence (col_freq)
            - Au moins 5 groupes distincts avec ≥ 2 observations chacun

        Réf. : Bühlmann & Straub (1970) ASTIN Bulletin 5(2) pp. 157-165
        """
        # Détecter la colonne de groupe
        _cols_groupe = [
            'id_flotte', 'id_entreprise', 'id_assure', 'id_client',
            'flotte_id', 'groupe_id', 'entreprise_id', 'id_groupe',
        ]
        col_groupe = next(
            (c for c in _cols_groupe if c in df.columns), None
        )

        if col_groupe is None:
            return {
                'appliquee': False,
                'raison': (
                    "Aucune colonne de groupe détectée "
                    f"({', '.join(_cols_groupe)}). "
                    "Sur données réelles, fournir id_flotte ou id_entreprise."
                ),
            }

        if col_expo not in df.columns or col_freq not in df.columns:
            return {
                'appliquee': False,
                'raison': f"Colonnes '{col_expo}' ou '{col_freq}' absentes.",
            }

        # Agrégation par groupe
        grp = df.groupby(col_groupe).agg(
            n_expo     = (col_expo, 'sum'),
            n_sin      = (col_freq, 'sum'),
            n_obs      = (col_freq, 'count'),
        ).reset_index()

        # Filtre : au moins 5 groupes avec ≥ 2 observations
        grp = grp[grp['n_obs'] >= 2]
        if len(grp) < 5:
            return {
                'appliquee': False,
                'raison': (
                    f"Trop peu de groupes ({len(grp)} < 5 avec ≥ 2 obs). "
                    "Crédibilité B-S nécessite au moins 5 groupes."
                ),
            }

        # Taux de sinistralité observé par groupe
        grp['mu_obs'] = grp['n_sin'] / np.maximum(grp['n_expo'], 1e-9)

        # Prime de marché = moyenne pondérée globale (proxy GLM)
        mu_marche = (
            grp['n_sin'].sum() / max(grp['n_expo'].sum(), 1e-9)
        )

        # ── Estimation k = σ²_intra / σ²_entre ──────────────────────────────
        # σ²_intra : composante de variance de processus (within variance).
        # CORRECTIF (audit V4) : l'estimateur précédent — moyenne pondérée
        # de (μ_obs_i / n_i) — était dimensionnellement incohérent avec
        # σ²_entre (unité [taux/exposition] au lieu de [taux²]×[exposition]
        # requise). Vérifié par simulation Poisson à paramètres connus :
        # l'ancien estimateur sous-évaluait σ²_intra d'un facteur ~100-300×,
        # ce qui gonflait artificiellement Z (Z≈0.98-0.99 même pour de
        # petites flottes de 10-40 véhicules), annulant l'effet protecteur
        # de la crédibilité sur les petits échantillons bruités.
        #
        # Sous hypothèse Poisson, Var(X_ij|Θ_i) = λ(Θ_i)/w_ij implique
        # σ²(Θ_i) = λ(Θ_i), donc σ²_intra = E[σ²(Θ)] = E[λ(Θ)] = μ_marché.
        # C'est la simplification standard pour la crédibilité Poisson.
        # Réf. : Bühlmann & Gisler (2005), "A Course in Credibility Theory
        # and Its Applications", §4.2 (cas particulier Poisson-Bühlmann-Straub).
        sigma2_intra_moy = float(mu_marche)

        # σ²_entre : variance inter-groupes (estimateur Bühlmann-Straub)
        # σ²_entre = [Σ n_i(μ_i - μ_marché)² - (N-1)σ²_intra] / (N_total - Σn²_i/N_total)
        N_total = grp['n_expo'].sum()
        numerateur = float(
            (grp['n_expo'] * (grp['mu_obs'] - mu_marche) ** 2).sum()
            - (len(grp) - 1) * sigma2_intra_moy
        )
        denominateur = float(
            N_total - (grp['n_expo'] ** 2).sum() / max(N_total, 1e-9)
        )
        sigma2_entre = max(numerateur / max(denominateur, 1e-9), 0.0)

        # ── Facteur k et facteurs Z ───────────────────────────────────────────
        if sigma2_entre < 1e-12:
            # σ²_entre ≈ 0 → tous les groupes identiques → k → ∞ → Z → 0
            # On retourne les primes de marché pour tous les groupes
            grp['Z'] = 0.0
        else:
            k = sigma2_intra_moy / sigma2_entre
            grp['Z'] = grp['n_expo'] / (grp['n_expo'] + k)

        # Prime crédibilisée
        grp['prime_credibilisee'] = (
            grp['Z'] * grp['mu_obs']
            + (1 - grp['Z']) * mu_marche
        )

        return {
            'appliquee':          True,
            'col_groupe':         col_groupe,
            'n_groupes':          int(len(grp)),
            'mu_marche':          round(float(mu_marche), 6),
            'sigma2_intra':       round(float(sigma2_intra_moy), 8),
            'sigma2_entre':       round(float(sigma2_entre), 8),
            'k':                  round(float(
                                       sigma2_intra_moy / max(sigma2_entre, 1e-12)
                                   ), 4),
            'z_moyen':            round(float(grp['Z'].mean()), 4),
            'z_min':              round(float(grp['Z'].min()), 4),
            'z_max':              round(float(grp['Z'].max()), 4),
            'primes_par_groupe':  grp[[
                                      col_groupe, 'n_expo', 'mu_obs',
                                      'Z', 'prime_credibilisee'
                                  ]].round(6).to_dict('records'),
            'reference':          (
                "Bühlmann & Straub (1970) ASTIN Bulletin 5(2) pp. 157-165 ; "
                "Mack (1994) crédibilité actuarielle"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # LISSAGE GÉOGRAPHIQUE
    # Réf. : Gelfand et al. (2010) Handbook of Spatial Statistics
    #        Actuariat — lissage par voisinage catégoriel (proxy krigeage)
    # ══════════════════════════════════════════════════════════════════════════

    def _lissage_geographique(
        self,
        df:          pd.DataFrame,
        predictions: Dict[str, Any],
        col_expo:    str,
        col_freq:    str = 'nb_sinistres',
    ) -> Dict[str, Any]:
        """
        Lissage géographique des primes par zone.

        Le paramètre `predictions` est le dict retourné par _calculer_predictions,
        avec les clés 'prime_pure', 'frequence_annuelle', 'prime_pure_tweedie'.

        Deux modes selon les données disponibles :

        Mode A — Krigeage spatial (données réelles avec GPS/IRIS) :
            Si les colonnes 'latitude', 'longitude' ou 'code_iris' sont présentes,
            on applique un lissage Nadaraya-Watson avec noyau gaussien sur les
            coordonnées géographiques.
            Réf. : Nadaraya (1964) ; Watson (1964) ; Gelfand et al. (2010).

        Mode B — Lissage catégoriel par voisinage (proxy) :
            Si seule une variable géographique catégorielle est présente
            (milieu_geographique, zone_geographique, departement, region),
            on calcule le taux de sinistralité par zone et on lisse par
            moyenne pondérée entre la zone et le marché global.
            Ce mode est un proxy de krigeage acceptable en l'absence de GPS.
            Réf. : Actuariat pratique — lissage tarifaire territorial.

        Colonnes détectées (par ordre de priorité) :
            GPS     : latitude + longitude
            IRIS    : code_iris
            Catég.  : milieu_geographique, zone_geographique,
                      departement, region, code_postal
        """
        # ── Détection des colonnes géographiques disponibles ──────────────────
        _cols_gps    = ['latitude', 'longitude']
        _cols_iris   = ['code_iris', 'iris']
        _cols_categ  = [
            'milieu_geographique', 'milieu_geographique_enc',
            'zone_geographique', 'zone_geographique_enc',
            'departement', 'region', 'code_postal',
        ]

        has_gps   = all(c in df.columns for c in _cols_gps)
        has_iris  = any(c in df.columns for c in _cols_iris)
        has_categ = next(
            (c for c in _cols_categ if c in df.columns), None
        )

        if not has_gps and not has_iris and has_categ is None:
            return {
                'applique': False,
                'raison': (
                    "Aucune colonne géographique détectée. "
                    "Sur données réelles, fournir latitude/longitude ou "
                    "code_iris ou milieu_geographique."
                ),
            }

        # Récupérer les prédictions depuis le dict predictions (arrays numpy)
        # Priorité : prime_pure > prime_pure_tweedie > frequence_annuelle
        # Fallback : fréquence brute observée (col_freq / exposition)
        # FIX (découvert lors du test de charge n=70000, audit V4 point #13) :
        # l'ancien enchaînement de `or` levait ValueError dès que la première
        # clé non-None contenait un tableau numpy de plus d'un élément
        # ("truth value of an array... is ambiguous") — la vérité d'un
        # tableau à plusieurs éléments n'est pas définie pour Python. Ce bug
        # ne se déclenchait pas sur les petits jeux de test antérieurs, où
        # 'prime_pure' était souvent absent du dict (GLM intercept seul).
        _prime_arr = predictions.get('prime_pure')
        if _prime_arr is None:
            _prime_arr = predictions.get('prime_pure_tweedie')
        if _prime_arr is None:
            _prime_arr = predictions.get('frequence_annuelle')
        _source_prime = 'prediction_glm'
        if _prime_arr is None or len(_prime_arr) == 0:
            # Fallback actuariel : taux brut observé = nb_sinistres / exposition
            # Utilisé quand le GLM est un modèle intercept seul (0 variables retenues)
            if col_freq in df.columns and col_expo in df.columns:
                _expo_safe = np.maximum(df[col_expo].values, 1e-6)
                _prime_arr = df[col_freq].values / _expo_safe
                _source_prime = 'taux_brut_observe'
                logger.info(
                    f"[Lissage géo] Fallback sur taux brut observé "
                    f"(GLM intercept seul — 0 variables retenues)."
                )
            else:
                return {
                    'applique': False,
                    'raison': (
                        "Prédictions GLM et taux brut indisponibles. "
                        f"Colonnes requises : '{col_freq}', '{col_expo}'."
                    ),
                }

        if col_expo not in df.columns:
            return {
                'applique': False,
                'raison': f"Colonne exposition '{col_expo}' absente.",
            }

        # ── Mode A : Krigeage Nadaraya-Watson (GPS disponible) ───────────────
        # CORRECTIF (audit V4 point #13) — deux défauts corrigés :
        #
        # 1. DISTANCE NON-MÉTRIQUE : l'implémentation précédente calculait
        #    d² = (Δlat)² + (Δlon)², traitant 1° de latitude et 1° de
        #    longitude comme des distances égales. C'est faux : en France
        #    métropolitaine (~47°N), 1° de longitude ≈ 76 km alors que
        #    1° de latitude ≈ 111 km (quasi constant). Le noyau gaussien
        #    était donc elliptique dans l'espace réel — anisotrope, avec
        #    une distorsion d'environ ×1,46 selon l'axe est-ouest — et
        #    le biais empirait avec la latitude (facteur cos(lat)).
        #    Corrigé par distance haversine (great-circle), isotrope et
        #    exacte sur la sphère terrestre.
        #
        # 2. O(n²) NON SCALABLE : la boucle calculait une distance à TOUS
        #    les autres points pour chaque point (paire complète), ce qui
        #    devient prohibitif au-delà de quelques milliers de contrats
        #    (≈ 5 000 000 000 opérations pour 70 000 contrats). Corrigé
        #    par un arbre spatial (BallTree, métrique haversine native)
        #    qui restreint la recherche aux points à moins de 3σ de
        #    distance (au-delà, le poids gaussien est négligeable),
        #    ramenant la complexité à O(n log n).
        if has_gps:
            try:
                lats   = df['latitude'].values.astype(float)
                lons   = df['longitude'].values.astype(float)
                primes = np.asarray(_prime_arr)
                expos  = df[col_expo].values

                # Bandwidth RÉDUIT de 111 km à 15 km (audit V4 point #13,
                # révision suite à test de charge). L'ancienne valeur
                # (héritée d'un "1°" jamais reconverti en km réels) lissait
                # quasiment à l'échelle du pays entier — deux contrats à
                # 300 km l'un de l'autre recevaient encore un poids non
                # négligeable dans le calcul de l'autre. Ce n'est pas du
                # lissage géographique local, c'est une quasi-moyenne
                # nationale : la granularité utile pour une tarification
                # territoriale (ville/agglomération) est de l'ordre de
                # quelques dizaines de km, pas de la centaine.
                # Effet secondaire bénéfique : un bandwidth réaliste rend
                # aussi le BallTree effectivement rapide (peu de voisins
                # par requête), alors qu'un bandwidth de 111 km incluait
                # une fraction significative du portefeuille dans le rayon
                # de troncature à 3σ pour toute zone urbaine dense —
                # annulant une bonne part du gain de complexité de l'arbre
                # spatial. Valeur ajustable selon la densité du portefeuille.
                EARTH_RADIUS_KM = 6371.0088  # rayon terrestre moyen (IUGG)
                h_km = 15.0

                coords_rad = np.radians(np.column_stack([lats, lons]))
                tree = BallTree(coords_rad, metric='haversine')

                # Troncature à 3σ : au-delà, exp(-9/2) ≈ 0.01% du poids
                # maximal — négligeable, et évite de scanner tout le jeu
                # de données pour chaque point.
                rayon_recherche_rad = (3 * h_km) / EARTH_RADIUS_KM
                voisins_idx, voisins_dist_rad = tree.query_radius(
                    coords_rad, r=rayon_recherche_rad, return_distance=True
                )

                lissees = np.zeros(len(df))
                for idx in range(len(df)):
                    idxs     = voisins_idx[idx]
                    dist_km  = voisins_dist_rad[idx] * EARTH_RADIUS_KM
                    w        = np.exp(-(dist_km ** 2) / (2 * h_km ** 2)) * expos[idxs]
                    w_sum    = w.sum()
                    lissees[idx] = (
                        np.dot(w, primes[idxs]) / max(w_sum, 1e-9)
                    )

                return {
                    'applique':    True,
                    'methode':     'krigeage_nadaraya_watson_haversine',
                    'source_prime': _source_prime,
                    'col_geo':     'latitude+longitude',
                    'n_zones':     len(df),
                    'bandwidth_h': h_km,
                    'prime_lissee_moy': round(float(lissees.mean()), 6),
                    'reference': (
                        "Nadaraya (1964) ; Watson (1964) ; "
                        "Gelfand et al. (2010) Handbook of Spatial Statistics ; "
                        "distance haversine (great-circle) via BallTree scikit-learn"
                    ),
                }
            except Exception as e_gps:
                logger.warning(f"Krigeage GPS échoué : {e_gps} — fallback catégoriel")

        # ── Mode B : Lissage catégoriel (proxy krigeage) ─────────────────────
        col_geo = (
            next((c for c in _cols_iris if c in df.columns), None)
            or has_categ
        )

        try:
            # Joindre _prime_arr au DataFrame pour l'agrégation
            _df_geo = df[[col_geo, col_expo]].copy()
            _df_geo['_prime'] = np.asarray(_prime_arr)
            grp = _df_geo.groupby(col_geo).agg(
                prime_moy = ('_prime', 'mean'),
                expo_tot  = (col_expo, 'sum'),
                n_obs     = ('_prime', 'count'),
            ).reset_index()

            mu_global = float(
                np.average(grp['prime_moy'], weights=grp['expo_tot'])
            )
            n_zones = len(grp)

            # Facteur de crédibilité par zone (B-S simplifié)
            n_min_zone = 30  # seuil minimum d'observations fiables
            grp['Z_geo'] = np.minimum(grp['n_obs'] / n_min_zone, 1.0)
            grp['prime_lissee'] = (
                grp['Z_geo'] * grp['prime_moy']
                + (1 - grp['Z_geo']) * mu_global
            )

            return {
                'applique':          True,
                'methode':           'lissage_categoriel_proxy',
                'source_prime':      _source_prime,
                'col_geo':           col_geo,
                'n_zones':           int(n_zones),
                'mu_global':         round(mu_global, 6),
                'prime_lissee_moy':  round(float(grp['prime_lissee'].mean()), 6),
                'zones': grp[[
                    col_geo, 'n_obs', 'expo_tot',
                    'prime_moy', 'Z_geo', 'prime_lissee'
                ]].round(6).to_dict('records'),
                'note': (
                    "Mode proxy (données catégorielles). "
                    "Sur données réelles avec GPS/IRIS, le Mode A "
                    "(krigeage Nadaraya-Watson) sera utilisé automatiquement."
                ),
                'reference': (
                    "Gelfand et al. (2010) Handbook of Spatial Statistics ; "
                    "Actuariat pratique — lissage tarifaire territorial"
                ),
            }

        except Exception as e_cat:
            return {
                'applique': False,
                'raison': f"Lissage catégoriel échoué : {e_cat}",
            }

    def _erreur(self, message: str, audit_id: str) -> Dict:
        return {
            'success':     False,
            'dataframe':   pd.DataFrame(),
            'branche':     None,
            'statut_rag':  'ROUGE',
            'modeles':     {},
            'metriques':   {},
            'predictions': {},
            'rapport':     {},
            'commentaire': f"❌ ERREUR A3 : {message}",
            'audit_id':    audit_id,
            'erreur':      message,
        }


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("Agent A3 — GLM Tarification ActuarIA v1.0")
    print("Modèles : GLM Poisson + GLM Gamma + GLM Tweedie")
    print("Usage   : %run 'chemin/a3_glm.py'")
    print("          agent_a3 = AgentA3GLM()")
    print("          result_a3 = agent_a3.run(result_a2)")
