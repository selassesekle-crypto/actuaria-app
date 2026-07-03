# =============================================================================
#  ActuarIA — Direction Non-Vie / Provisionnement A7 Ibrahim v5.0
#  n3/barnett_zehnwirth.py  —  Détection des Effets Calendaire
#
#  Inspiré de : Barnett & Zehnwirth (1998) — Best Estimates for Reserves
#  Approche : Analyse des facteurs de développement par diagonale
#
#  Principe :
#    Pour chaque diagonale k (= i + j = année calendaire), on calcule
#    le facteur de développement médian observé sur cette diagonale.
#    On compare ce facteur à la médiane globale de tous les facteurs
#    via un score Z robuste (MAD — Median Absolute Deviation).
#
#    Une diagonale est anormale si son facteur s'écarte de plus de
#    SEUIL_MAD déviations MAD de la médiane globale.
#
#  Ce module ne corrige PAS automatiquement les ultimates :
#    La correction des effets calendaire nécessite un jugement actuariel
#    (estimation de l'amplitude du choc, choix de la méthode de correction).
#    ActuarIA détecte et alerte — l'actuaire désigné décide et valide.
#
#  Ce que fait ce module :
#    · Détecte les diagonales anormales avec leur amplitude et direction
#    · Recommande la méthode la plus adaptée (Clark, BF, ou CL corrigé)
#    · Génère un message actuariel avec les années calendaires concernées
#    · Fournit un statut VERT/AMBRE/ROUGE pour le tableau de bord
#
#  Auteur  : ActuarIA v5.0
#  Version : 2.0.0
# =============================================================================

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from scipy import stats as sp_stats
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

try:
    import pandas as pd
    import statsmodels.api as sm
    from scipy import stats as scipy_stats
    STATSMODELS_OK = True
except ImportError:
    STATSMODELS_OK = False

logger = logging.getLogger('actuaria.a7.n3.barnett_zehnwirth')


# =============================================================================
#  CONSTANTES
# =============================================================================

# Seuil MAD pour la détection des anomalies de diagonale
# 2.5 → équivalent à ~2.5σ sous distribution gaussienne (~1.2% faux positifs)
SEUIL_MAD = 2.5

# Nombre minimum de facteurs sur une diagonale pour qu'elle soit évaluable
# · 3 minimum requis pour éviter les faux positifs sur les premières diagonales
#   (qui n'ont naturellement que peu de cellules dans un triangle carré)
MIN_POINTS = 3

# Seuils d'amplitude pour la qualification du niveau d'effet
SEUIL_FORT   = 0.15   # 15% → effet fort
SEUIL_MODERE = 0.08   # 8%  → effet modéré

# Valeur minimale pour éviter log(0)
EPSILON = 1e-10

# Seuil de significativité pour les tests statistiques
# 0.05 = 5% — standard actuariel (Kruskal-Wallis, t-test)
SEUIL_SIGNIFICATIVITE = 0.05


# =============================================================================
#  CALCUL DES FACTEURS PAR DIAGONALE
# =============================================================================

def _facteurs_par_cellule(C: np.ndarray) -> List[Dict]:
    """
    Calcule le facteur de développement f_{i,j} = C[i,j] / C[i,j-1]
    pour chaque cellule du triangle, avec la diagonale k = i+j associée.

    Ces facteurs individuels sont la matière première de l'analyse BZ.
    On travaille en log pour stabiliser la variance :
    log(f) suit une distribution plus symétrique que f.

    Parameters
    ----------
    C : triangle cumulé (n × m)

    Returns
    -------
    List[Dict] : liste de {i, j, k, facteur, log_facteur} par cellule
    """
    n, m = C.shape
    cellules = []

    for i in range(n):
        for j in range(1, m):
            # Cellule valide = dans le triangle + deux valeurs positives
            if C[i, j] > 0 and C[i, j-1] > 0 and (i + j) < n:
                f = float(C[i, j]) / float(C[i, j-1])
                cellules.append({
                    'i':           i,
                    'j':           j,
                    'k':           i + j,   # Diagonale calendaire
                    'facteur':     f,
                    'log_facteur': np.log(max(f, EPSILON)),
                })

    return cellules


# =============================================================================
#  DÉTECTION DES DIAGONALES ANORMALES
# =============================================================================

def _test_kruskal_wallis(cellules: List[Dict]) -> Dict:
    """
    Test de Kruskal-Wallis — test global d'existence des effets calendaire.

    H0 : Les log-facteurs ont la même distribution sur toutes les diagonales
         (= pas d'effets calendaire dans le triangle).
    H1 : Au moins une diagonale a une distribution différente
         (= au moins un effet calendaire existe).

    Ce test PRÉCÈDE les tests individuels par diagonale.
    Si H0 n'est pas rejetée (p > 0.05) → aucun effet calendaire global
    → on ne cherche pas d'anomalies individuelles (évite les faux positifs).

    Référence : Kruskal & Wallis (1952) — non-paramétrique, robuste
    aux petits échantillons et aux distributions non gaussiennes.
    """
    if not SCIPY_OK:
        # Si scipy absent, on autorise les tests individuels par défaut
        return {'significatif': True, 'p_value': None, 'h_stat': None,
                'message': 'scipy absent — test Kruskal-Wallis ignoré'}

    # Regrouper les log-facteurs par diagonale avec assez de points
    par_diag: Dict[int, List[float]] = {}
    for c in cellules:
        k = c['k']
        if k not in par_diag:
            par_diag[k] = []
        par_diag[k].append(c['log_facteur'])

    groupes = [v for v in par_diag.values() if len(v) >= MIN_POINTS]

    if len(groupes) < 2:
        # Pas assez de groupes → supposer pas d'effet calendaire
        return {'significatif': False, 'p_value': 1.0, 'h_stat': 0.0,
                'message': 'Pas assez de diagonales évaluables pour le test global'}

    try:
        h_stat, p_value = sp_stats.kruskal(*groupes)
        significatif = float(p_value) < SEUIL_SIGNIFICATIVITE
        return {
            'h_stat':       round(float(h_stat), 3),
            'p_value':      round(float(p_value), 4),
            'significatif': significatif,
            'n_groupes':    len(groupes),
            'message': (
                f"Kruskal-Wallis : H={h_stat:.2f}, p={p_value:.4f} — "
                f"{'Effets calendaire globaux détectés (H0 rejetée)' if significatif else 'Aucun effet calendaire global (H0 non rejetée)'}"
            ),
        }
    except Exception as e:
        return {'significatif': True, 'p_value': None, 'h_stat': None,
                'message': f'Kruskal-Wallis échoué : {e}'}


def _detecter_anomalies(
    cellules    : List[Dict],
    annee_debut : Optional[int] = None,
) -> List[Dict]:
    """
    Détecte les diagonales anormales via score Z robuste (MAD).

    Pour chaque diagonale k, on calcule le log-facteur médian.
    On compare à la distribution globale des log-facteurs via MAD.

    Interprétation du score Z :
      · |Z| < 2.5 → diagonale normale
      · |Z| ≥ 2.5 → diagonale anormale (effet calendaire probable)
      · Z > 0 → diagonale anormalement haute (hausse des paiements)
      · Z < 0 → diagonale anormalement basse (baisse des paiements)

    Parameters
    ----------
    cellules    : liste des facteurs par cellule
    annee_debut : première année calendaire (pour les labels)

    Returns
    -------
    List[Dict] : résultats par diagonale avec statut et amplitude
    """
    if not cellules:
        return []

    # Regrouper par diagonale k
    par_diag: Dict[int, List[float]] = {}
    for c in cellules:
        k = c['k']
        if k not in par_diag:
            par_diag[k] = []
        par_diag[k].append(c['log_facteur'])

    # Filtrer les diagonales avec assez de points
    par_diag_valide = {k: v for k, v in par_diag.items() if len(v) >= MIN_POINTS}

    if not par_diag_valide:
        return []

    # Médiane des log-facteurs par diagonale
    medianes_diag = {k: float(np.median(v)) for k, v in par_diag_valide.items()}

    # Distribution globale des log-facteurs (toutes diagonales confondues)
    tous_lf   = [lf for lfs in par_diag_valide.values() for lf in lfs]
    med_glob  = float(np.median(tous_lf))
    mad_glob  = float(np.median(np.abs(np.array(tous_lf) - med_glob)))

    # Fallback si MAD = 0 (triangle trop régulier)
    if mad_glob < EPSILON:
        std_glob = float(np.std(tous_lf))
        if std_glob > EPSILON:
            mad_glob = std_glob
        else:
            mad_glob = 1.0
            logger.warning('BZ : MAD=0 et std=0 — triangle deterministe, scores Z non significatifs.')

    # Constante de normalisation : MAD × 1.4826 ≈ σ pour une loi normale
    # Cette constante rend le score Z comparable à un z-score gaussien standard
    scale = mad_glob * 1.4826

    results = []
    for k in sorted(par_diag_valide.keys()):
        med_k    = medianes_diag[k]
        n_pts    = len(par_diag_valide[k])
        z_score  = (med_k - med_glob) / scale if scale > EPSILON else 0.0
        anomalie = abs(z_score) > SEUIL_MAD

        # Amplitude en % : exp(médiane_k - médiane_globale) - 1
        # Représente l'excès de développement sur cette diagonale
        amplitude_pct = (np.exp(med_k - med_glob) - 1.0) * 100

        # Niveau de l'effet
        amp_abs = abs(amplitude_pct) / 100
        if amp_abs >= SEUIL_FORT:
            niveau = 'FORT'
        elif amp_abs >= SEUIL_MODERE:
            niveau = 'MODÉRÉ'
        else:
            niveau = 'FAIBLE'

        # Label de l'année calendaire (si annee_debut fourni)
        # k représente le rang de la diagonale → annee calendaire = annee_debut + k
        annee_label = str(annee_debut + k) if annee_debut else f"Diag. {k}"

        # Test de Student optionnel (si scipy disponible et ≥ 3 points)
        p_value = None
        if SCIPY_OK and n_pts >= 3:
            _, p_val = sp_stats.ttest_1samp(
                par_diag_valide[k], popmean=med_glob
            )
            p_value = round(float(p_val), 4)
            # Renforcer l'anomalie si t-test confirme (p < 0.10)
            if not anomalie and p_value < 0.10:
                anomalie = True  # Confirmation par t-test

        results.append({
            'diagonale':     k,
            'annee_label':   annee_label,
            'mediane_logf':  round(med_k, 4),
            'z_score':       round(float(z_score), 3),
            'amplitude_pct': round(float(amplitude_pct), 1),
            'n_points':      n_pts,
            'significatif':  anomalie,
            'sens':          'hausse' if amplitude_pct > 0 else 'baisse',
            'niveau':        niveau if anomalie else 'normal',
            'p_value':       p_value,
        })

    return results


# =============================================================================
#  RECOMMANDATION MÉTHODE
# =============================================================================

def _recommander_methode(
    effets          : List[Dict],
    n_sig           : int,
    derniere_diag   : int,
) -> str:
    """
    Recommande la méthode actuarielle la plus adaptée selon les effets
    calendaire détectés.

    Logique de recommandation :
      · Aucun effet → CL standard fiable
      · Effets modérés → BF (ancrage externe atténue l'influence des diagonales)
      · Effets forts → Clark (courbe paramétrique lisse les irrégularités)
      · Effet sur la DERNIÈRE diagonale → attention particulière (BE biaisé)

    Parameters
    ----------
    effets        : effets calendaire détectés
    n_sig         : nombre d'effets significatifs
    derniere_diag : indice de la dernière diagonale (la plus récente)

    Returns
    -------
    str : recommandation méthode
    """
    if n_sig == 0:
        return "Chain Ladder standard — aucun effet calendaire détecté."

    effets_sig   = [e for e in effets if e['significatif']]
    effets_forts = [e for e in effets_sig if e['niveau'] == 'FORT']
    effet_dernier = any(e['diagonale'] == derniere_diag for e in effets_sig)

    if effets_forts or effet_dernier:
        reco = "Triangles 'As if' corrigés des effets calendaires recommandés"
        if effet_dernier:
            reco += (
                " — effet sur la dernière diagonale biaise directement le BE. "
                "Retraiter les données avant application de CL ou BF."
            )
        else:
            reco += (
                " — effets forts. Identifier la cause (inflation, changement "
                "législatif) et documenter dans la note méthodologique S2."
            )
    else:
        reco = (
            "Bornhuetter-Ferguson recommandé — effets modérés. "
            "L'ancrage sur a priori externe atténue l'influence des diagonales perturbées."
        )

    return reco


# =============================================================================
#  GLM BARNETT-ZEHNWIRTH — Poisson log-linéaire
# =============================================================================

def _triangle_to_long(
    C:          np.ndarray,
    annee_debut: int = 2000,
) -> 'pd.DataFrame':
    """
    Convertit un triangle cumulé numpy en format long pour le GLM BZ.
    Générique — fonctionne pour n'importe quelle taille de triangle.

    Returns DataFrame avec colonnes :
        cohorte, developpement, calendrier, Y (incréments), Y_cum (cumulés)
    """
    n, m = C.shape
    rows = []
    for i in range(n):
        for j in range(m):
            val_cum = C[i, j]
            if np.isnan(val_cum) or val_cum <= 0:
                continue
            val_prev = C[i, j-1] if j > 0 else 0.0
            if np.isnan(val_prev):
                val_prev = 0.0
            inc = val_cum - val_prev
            rows.append({
                'cohorte':       str(annee_debut + i),
                'developpement': str(j + 1),
                'calendrier':    str(annee_debut + i + j),
                'Y':             float(max(inc, 0.01)),  # Poisson nécessite Y > 0
                'Y_cum':         float(val_cum),
            })
    return pd.DataFrame(rows)


def _glm_bz_fit(
    df_long: 'pd.DataFrame',
) -> Dict:
    """
    Ajuste deux GLM Poisson :
    - Modèle réduit  : Y ~ α_i (cohorte) + β_j (développement)
    - Modèle complet : Y ~ α_i + β_j + γ_k (calendrier)

    Test LR pour significativité des effets calendaires.

    Returns dict avec modèles, prédictions, AIC, LR test, p-value.
    """
    if not STATSMODELS_OK:
        return {'success': False, 'erreur': 'statsmodels non disponible'}

    df = df_long[df_long['Y'] > 0].copy()
    if len(df) < 8:
        return {'success': False, 'erreur': f'Trop peu de données ({len(df)} cellules)'}

    y = df['Y'].values

    try:
        # ── Modèle réduit (sans calendrier) ──────────────────────────────────
        X_red = pd.get_dummies(
            df[['cohorte','developpement']], drop_first=True
        ).astype(float)
        X_red = sm.add_constant(X_red)
        m_red = sm.GLM(y, X_red, family=sm.families.Poisson()).fit(disp=False)

        # ── Modèle complet (avec calendrier) ──────────────────────────────────
        X_ful = pd.get_dummies(
            df[['cohorte','developpement','calendrier']], drop_first=True
        ).astype(float)
        X_ful = sm.add_constant(X_ful)
        m_ful = sm.GLM(y, X_ful, family=sm.families.Poisson()).fit(disp=False)

        # ── LR test H0 : γ_k = 0 ∀k ──────────────────────────────────────────
        lr_stat  = 2.0 * (m_ful.llf - m_red.llf)
        ddl_reel = int(round(m_red.df_resid - m_ful.df_resid))
        n_cal    = max(ddl_reel, 1)
        p_value  = 1.0 - scipy_stats.chi2.cdf(lr_stat, df=n_cal)
        cal_sig  = p_value < 0.05

        # Prédictions modèle complet
        df = df.copy()
        df['Y_hat'] = m_ful.fittedvalues
        df['residu_pearson'] = (df['Y'] - df['Y_hat']) / np.sqrt(np.maximum(df['Y_hat'], 1e-6))

        return {
            'success':         True,
            'df_pred':         df,
            'aic_reduit':      round(m_red.aic, 2),
            'aic_complet':     round(m_ful.aic, 2),
            'll_reduit':       round(m_red.llf, 2),
            'll_complet':      round(m_ful.llf, 2),
            'lr_stat':         round(lr_stat, 2),
            'p_calendrier':    round(p_value, 6),
            'n_cal_ddl':       n_cal,
            'cal_significatif': cal_sig,
            'deviance':        round(m_ful.deviance, 4),
            'model_ful':       m_ful,
            'model_red':       m_red,
        }

    except Exception as e:
        return {'success': False, 'erreur': str(e)}


def _fallback_ratio(df_pred, annee_i, last_j, m, obs_last):
    """Fallback projection BZ par ratio de moyennes (approximation)."""
    df = df_pred.copy()
    df['cohorte_int'] = df['cohorte'].astype(int)
    ibnr_i = 0.0
    for j in range(last_j + 1, m):
        df_dev = df[df['developpement'] == str(j + 1)]
        df_lj  = df[df['developpement'] == str(last_j + 1)]
        if len(df_dev) == 0 or len(df_lj) == 0 or df_lj['Y_hat'].mean() <= 0:
            continue
        ratio    = df_dev['Y_hat'].mean() / df_lj['Y_hat'].mean()
        inc_base = float(df[(df['cohorte_int'] == annee_i) & (df['developpement'] == str(last_j + 1))]['Y_hat'].sum()) or (obs_last * 0.05)
        ibnr_i  += inc_base * ratio
    return ibnr_i


def _extrapoler_ultimates_bz(df_pred, C, annee_debut, model_ful=None, annee_base=1):
    """
    Extrapole les ultimates BZ via m_ful.predict — Barnett & Zehnwirth (1998).
    Hypothese : effet calendaire futur = dernier effet calendaire observe (gel).
    Fallback par ratio de moyennes si predict echoue.
    """
    n, m = C.shape
    derniere_cal = str(annee_debut + n - 1)
    ultimates, ibnr_annees = [], []

    for i in range(n):
        annee_i  = annee_debut + i
        last_j   = m - 1 - i
        obs_last = float(C[i, last_j]) if last_j >= 0 and not np.isnan(C[i, last_j]) else 0.0
        ibnr_i   = 0.0

        if model_ful is not None and last_j < m - 1:
            try:
                rows_fut = [{'cohorte': str(annee_i), 'developpement': str(j + 1), 'calendrier': derniere_cal}
                            for j in range(last_j + 1, m)]
                if rows_fut:
                    df_fut = pd.DataFrame(rows_fut)
                    X_fut  = pd.get_dummies(df_fut[['cohorte','developpement','calendrier']], drop_first=True).astype(float)
                    X_fut  = sm.add_constant(X_fut)
                    for col in model_ful.model.exog_names:
                        if col not in X_fut.columns:
                            X_fut[col] = 0.0
                    X_fut  = X_fut[model_ful.model.exog_names]
                    y_pred = model_ful.predict(X_fut)
                    ibnr_i = float(np.sum(np.maximum(y_pred, 0)))
            except Exception as e_pred:
                logger.debug(f'BZ predict annee {annee_i}: {e_pred} — fallback ratio')
                ibnr_i = _fallback_ratio(df_pred, annee_i, last_j, m, obs_last)
        else:
            ibnr_i = _fallback_ratio(df_pred, annee_i, last_j, m, obs_last)

        ultimates.append(obs_last + ibnr_i)
        ibnr_annees.append(ibnr_i)

    return {
        'ultimates':      [round(u, 0) for u in ultimates],
        'ibnr_par_annee': [round(v, 0) for v in ibnr_annees],
        'reserve_totale': round(sum(ibnr_annees[annee_base:]), 0),
    }





# =============================================================================
#  FONCTION PRINCIPALE
# =============================================================================

def barnett_zehnwirth(
    C           : np.ndarray,
    annee_debut : Optional[int] = None,
    annee_base  : int           = 1,
) -> Dict:
    """
    Analyse Barnett-Zehnwirth complète :

    NIVEAU 1 — Détection des effets calendaires
        · Test Kruskal-Wallis global
        · Détection anomalies par diagonale (MAD)
        · Statut VERT / AMBRE / ROUGE

    NIVEAU 2 — GLM Poisson (Barnett & Zehnwirth 1998)
        · Modèle : μ_{i,j} = exp(α_i + β_j + γ_k)
        · Test LR H0 : γ_k = 0 ∀k (effets calendaires nuls)
        · Ultimates corrigés des effets calendaires détectés
        · AIC comparatif avec/sans effets calendaires

    Note : les ultimates BZ sont produits à titre informatif.
    La correction des effets calendaires nécessite un jugement
    actuariel documenté (Guide IA 2023).

    Limite connue : la projection des incréments futurs dans
    `_extrapoler_ultimates_bz` utilise une approximation par ratio
    de moyennes — pas la projection exacte B&Z 1998 par paramètres β_j.
    Les ultimates BZ sont donc indicatifs, pas certifiés conformes B&Z.

    Parameters
    ----------
    C           : triangle des paiements CUMULÉS (n × n)
    annee_debut : première année calendaire (labels)
    annee_base  : première année incluse dans la réserve

    Returns
    -------
    Dict standard A7 Ibrahim avec :
        success, disponible, statut, message, erreur
        effets_calendaire, n_effets_significatifs, diagonales_anormales
        recommandation, kruskal_wallis
        glm_disponible, p_calendrier, cal_significatif, aic_complet
        reserve_bz, ultimates_corriges, ibnr_par_annee_bz
    """
    n, m = C.shape
    if annee_debut is None:
        annee_debut = 2000

    if n < 5 or m < 5:
        return {
            'success':    False,
            'disponible': False,
            'erreur':     f"Triangle trop petit ({n}×{m}) — minimum 5×5",
            'message':    "Triangle insuffisant pour l'analyse des effets calendaire.",
        }

    try:
        logger.info(f"Analyse BZ — triangle {n}×{m}...")

        # ── NIVEAU 1 : Détection ─────────────────────────────────────────────
        cellules = _facteurs_par_cellule(C)

        if not cellules:
            return {
                'success':    False,
                'disponible': True,
                'erreur':     "Aucun facteur de développement calculable",
                'message':    "Triangle insuffisant pour l'analyse.",
            }

        kw     = _test_kruskal_wallis(cellules)
        effets = _detecter_anomalies(cellules, annee_debut) if kw['significatif'] else []

        n_sig  = sum(1 for e in effets if e['significatif'])
        pct_sig = n_sig / len(effets) * 100 if effets else 0.0
        diagonales_anormales = [e['annee_label'] for e in effets if e['significatif']]

        derniere_diag = max(e['diagonale'] for e in effets) if effets else 0
        recommandation = _recommander_methode(effets, n_sig, derniere_diag)

        effets_forts   = [e for e in effets if e['significatif'] and e['niveau'] == 'FORT']
        effet_dernier  = any(e['diagonale'] == derniere_diag and e['significatif'] for e in effets)

        if len(effets_forts) >= 2 or effet_dernier:
            statut = 'ROUGE'
        elif n_sig >= 1:
            statut = 'AMBRE'
        else:
            statut = 'VERT'

        # ── NIVEAU 2 : GLM BZ ────────────────────────────────────────────────
        glm_result     = {}
        reserve_bz     = None
        ultimates_bz   = None
        ibnr_bz        = None
        glm_disponible = False
        p_cal          = None
        cal_sig        = None
        aic_complet    = None

        if STATSMODELS_OK and n >= 5 and m >= 5:
            try:
                df_long = _triangle_to_long(C, annee_debut)
                glm_result = _glm_bz_fit(df_long)

                if glm_result.get('success'):
                    glm_disponible = True
                    p_cal       = glm_result['p_calendrier']
                    cal_sig     = glm_result['cal_significatif']
                    aic_complet = glm_result['aic_complet']

                    # Ultimates BZ
                    ult_result  = _extrapoler_ultimates_bz(
                        glm_result['df_pred'], C, annee_debut,
                        model_ful=glm_result.get('model_ful'),
                        annee_base=annee_base,
                    )
                    reserve_bz  = ult_result['reserve_totale']
                    ultimates_bz = ult_result['ultimates']
                    ibnr_bz     = ult_result['ibnr_par_annee']

                    logger.info(
                        f"GLM BZ : p_cal={p_cal:.4f}, "
                        f"cal_sig={cal_sig}, "
                        f"réserve_BZ={reserve_bz:,.0f}€"
                    )
            except Exception as e_glm:
                logger.warning(f"GLM BZ échoué : {e_glm}")

        # ── Message actuariel ─────────────────────────────────────────────────
        if n_sig == 0:
            message = (
                f"Aucun effet calendaire significatif détecté sur "
                f"{len(effets)} diagonale(s). "
                f"Triangle conforme à l'hypothèse d'indépendance des diagonales."
            )
        else:
            details = [
                f"{e['annee_label']} : {e['amplitude_pct']:+.1f}% ({e['sens']}, {e['niveau']})"
                for e in effets if e['significatif']
            ]
            message = (
                f"{n_sig} effet(s) calendaire(s) détecté(s) : "
                f"{chr(8212).join(details)}. "
                f"Causes possibles : inflation, changement législatif, pandémie. "
                f"Recommandation : {recommandation}"
            )
            if statut == 'ROUGE':
                message = "⚠️ " + message + (
                    " Effet sur dernière diagonale — biais direct sur le BE."
                    if effet_dernier else
                    " Effets forts — révision des hypothèses recommandée."
                )

        # Enrichir avec GLM si disponible
        if glm_disponible and cal_sig is not None:
            glm_msg = (
                f" GLM BZ (LR test) : effets calendaires "
                f"{'SIGNIFICATIFS (p={:.4f})'.format(p_cal) if cal_sig else 'NON significatifs (p={:.4f})'.format(p_cal)}."
            )
            if reserve_bz is not None:
                glm_msg += f" Réserve BZ corrigée : {reserve_bz:,.0f}€ (informatif)."
            message += glm_msg

        return {
            'success':                   True,
            'disponible':                True,

            # Niveau 1 — Détection
            'effets_calendaire':         effets,
            'n_effets_significatifs':    n_sig,
            'pct_effets_significatifs':  round(pct_sig, 1),
            'diagonales_anormales':      diagonales_anormales,
            'n_diagonales_evaluees':     len(effets),
            'kruskal_wallis':            kw,

            # Niveau 2 — GLM BZ
            'glm_disponible':            glm_disponible,
            'p_calendrier':              p_cal,
            'cal_significatif':          cal_sig,
            'aic_reduit':                glm_result.get('aic_reduit'),
            'aic_complet':               aic_complet,
            'll_reduit':                 glm_result.get('ll_reduit'),
            'll_complet':                glm_result.get('ll_complet'),
            'lr_stat':                   glm_result.get('lr_stat'),
            'n_cal_ddl':                 glm_result.get('n_cal_ddl'),

            # Ultimates BZ (informatif — nécessite jugement actuariel)
            'reserve_bz':                reserve_bz,
            'ultimates_corriges':        ultimates_bz,
            'ibnr_par_annee_bz':         ibnr_bz,
            'note_bz': (
                "Ultimates BZ calculés par GLM Poisson log-linéaire "
                "(Barnett & Zehnwirth 1998). "
                "À titre informatif — la correction des effets calendaires "
                "nécessite un jugement actuariel documenté (Guide IA 2023)."
            ) if reserve_bz is not None else None,

            # Recommandation
            'recommandation':            recommandation,
            'statut':                    statut,
            'message':                   message,
            'erreur':                    None,
        }

    except Exception as e:
        logger.error(f"Barnett-Zehnwirth échoué : {e}", exc_info=True)
        return {
            'success':    False,
            'disponible': True,
            'erreur':     str(e),
            'message':    f"Analyse BZ échouée : {e}",
        }
