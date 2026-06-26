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
        mad_glob = float(np.std(tous_lf)) if np.std(tous_lf) > EPSILON else 1.0

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
        reco = "Clark (log-logistique/Weibull) recommandé"
        if effet_dernier:
            reco += " — effet calendaire sur la dernière diagonale biaise le BE"
    else:
        reco = "Bornhuetter-Ferguson recommandé"
        reco += " — l'ancrage sur l'a priori atténue l'influence des diagonales anormales"

    return reco


# =============================================================================
#  FONCTION PRINCIPALE
# =============================================================================

def barnett_zehnwirth(
    C           : np.ndarray,
    annee_debut : Optional[int] = None,
    annee_base  : int           = 1,
) -> Dict:
    """
    Détection des effets calendaire — approche Barnett-Zehnwirth (1998).

    Détecte les diagonales anormales dans le triangle via analyse MAD
    des facteurs de développement. Génère des alertes actuarielles et
    recommande la méthode la plus adaptée.

    NE CORRIGE PAS automatiquement les ultimates — la correction des
    effets calendaire nécessite un jugement actuariel documenté.

    Parameters
    ----------
    C           : triangle des paiements CUMULÉS (n × n)
    annee_debut : première année calendaire du triangle (pour les labels)
    annee_base  : première année incluse dans la réserve

    Returns
    -------
    Dict avec :
        success                : bool
        disponible             : bool
        effets_calendaire      : list[dict] — résultats par diagonale
        n_effets_significatifs : int
        diagonales_anormales   : list[str] — labels des années anormales
        recommandation         : str — méthode recommandée
        statut                 : 'VERT' | 'AMBRE' | 'ROUGE'
        message                : str — alerte actuarielle détaillée
        erreur                 : str ou None
    """
    n, m = C.shape

    # Vérifications préliminaires
    if n < 5 or m < 5:
        return {
            'success':    False,
            'disponible': False,
            'erreur':     f"Triangle trop petit ({n}×{m}) — minimum 5×5",
            'message':    "Triangle insuffisant pour l'analyse des effets calendaire.",
        }

    try:
        logger.info(f"Analyse effets calendaire BZ — triangle {n}×{m}...")

        # ── Calcul des facteurs par cellule ───────────────────────────────────
        cellules = _facteurs_par_cellule(C)

        if not cellules:
            return {
                'success':    False,
                'disponible': True,
                'erreur':     "Aucun facteur de développement calculable",
                'message':    "Triangle insuffisant pour l'analyse.",
            }

        # ── Test global Kruskal-Wallis ───────────────────────────────────────
        # Séquence statistiquement correcte : test global d'abord,
        # puis tests individuels seulement si H0 est rejetée globalement.
        # Cela évite les faux positifs liés aux tests multiples.
        kw = _test_kruskal_wallis(cellules)
        logger.info(kw['message'])

        # ── Détection des anomalies individuelles ─────────────────────────────
        if kw['significatif']:
            # H0 rejetée → au moins une diagonale est anormale
            effets = _detecter_anomalies(cellules, annee_debut)
        else:
            # H0 non rejetée → aucun effet calendaire global → pas de tests individuels
            effets = []

        n_sig = sum(1 for e in effets if e['significatif'])
        pct_sig = n_sig / len(effets) * 100 if effets else 0.0

        # ── Diagonales anormales avec labels ─────────────────────────────────
        diagonales_anormales = [
            e['annee_label'] for e in effets if e['significatif']
        ]

        # ── Recommandation méthode ────────────────────────────────────────────
        derniere_diag = max(e['diagonale'] for e in effets) if effets else 0
        recommandation = _recommander_methode(effets, n_sig, derniere_diag)

        # ── Statut global ─────────────────────────────────────────────────────
        effets_forts = [e for e in effets if e['significatif'] and e['niveau'] == 'FORT']
        effet_dernier = any(e['diagonale'] == derniere_diag and e['significatif'] for e in effets)

        if len(effets_forts) >= 2 or effet_dernier:
            statut = 'ROUGE'
        elif n_sig >= 1:
            statut = 'AMBRE'
        else:
            statut = 'VERT'

        # ── Message actuariel ─────────────────────────────────────────────────
        if n_sig == 0:
            message = (
                f"Aucun effet calendaire significatif détecté sur "
                f"{len(effets)} diagonale(s) analysée(s). "
                f"Le triangle respecte l'hypothèse d'indépendance des diagonales. "
                f"Chain Ladder non biaisé par des chocs externes."
            )
        else:
            # Détailler chaque anomalie détectée
            details = []
            for e in effets:
                if e['significatif']:
                    details.append(
                        f"{e['annee_label']} : {e['amplitude_pct']:+.1f}% "
                        f"({e['sens']}, {e['niveau']})"
                    )

            message = (
                f"{n_sig} effet(s) calendaire(s) détecté(s) : "
                f"{' — '.join(details)}. "
                f"Causes possibles : inflation, changement législatif, "
                f"pandémie ou changement de pratiques de gestion. "
                f"Vérifier avec votre gestionnaire sinistres. "
                f"Recommandation : {recommandation}"
            )

            if statut == 'ROUGE':
                message = "⚠️ " + message + (
                    " L'effet sur la dernière diagonale biaise directement "
                    "le Best Estimate — révision impérative avant bilan S2."
                    if effet_dernier else
                    " Effets forts détectés — révision des hypothèses recommandée."
                )

        return {
            'success':                  True,
            'disponible':               True,

            # Effets calendaire
            'effets_calendaire':        effets,
            'n_effets_significatifs':   n_sig,
            'pct_effets_significatifs': round(pct_sig, 1),
            'diagonales_anormales':     diagonales_anormales,
            'n_diagonales_evaluees':    len(effets),
            'kruskal_wallis':            kw,

            # Recommandation
            'recommandation':           recommandation,

            # Statut et interprétation
            'statut':                   statut,
            'message':                  message,
            'erreur':                   None,

            # Note : pas d'ultimates corrigés automatiquement
            # La correction nécessite un jugement actuariel documenté
            'reserve_bz':               None,
            'ultimates_corriges':       None,
            'facteurs_corriges':        None,
        }

    except Exception as e:
        logger.error(f"Barnett-Zehnwirth échoué : {e}", exc_info=True)
        return {
            'success':    False,
            'disponible': True,
            'erreur':     str(e),
            'message':    f"Analyse effets calendaire échouée : {e}",
        }
