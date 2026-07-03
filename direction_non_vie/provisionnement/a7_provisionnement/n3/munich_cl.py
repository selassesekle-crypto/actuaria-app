# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n3/munich_cl.py  —  Munich Chain Ladder (Quarg & Mack 2004)
# =============================================================================
#
#  Référence principale
#  --------------------
#  Quarg, G. & Mack, T. (2004).
#    "Munich Chain Ladder: A Reserving Method that Reduces the Gap between
#     IBNR Projections of Paid and Incurred Losses."
#    Casualty Actuarial Society Forum, Fall 2004, pp. 101–138.
#
#  Contexte et utilité
#  -------------------
#  Le Munich CL (MCL) utilise DEUX triangles simultanément :
#    · Triangle payé   C_P[i,j]  (sinistres réglés)
#    · Triangle engagé C_E[i,j]  (sinistres notifiés = payés + IBNR dossier)
#
#  Observation empirique (Quarg & Mack) : les facteurs payé et engagé sont
#  corrélés via le ratio Q[i,j] = C_P[i,j] / C_E[i,j] (taux de règlement).
#  Le CL standard ignore cette corrélation → divergence systématique entre
#  projections payé et engagé.
#
#  Principe MCL
#  ------------
#  Pour chaque colonne j, les facteurs payé et engagé sont ajustés :
#
#    f*_P[j] = f_P[j] + λ_P[j] × (Q_moy[j] - q̂_P[j])
#    f*_E[j] = f_E[j] + λ_E[j] × (Q_moy[j] - q̂_E[j])
#
#  où  f_P[j], f_E[j] = facteurs CL standard payé/engagé
#      λ_P[j], λ_E[j] = coefficients de régression (corrélation résidus)
#      Q_moy[j]        = ratio payé/engagé moyen à la colonne j
#      q̂_P[j]         = ratio Q prédit par le facteur payé seul
#      q̂_E[j]         = ratio Q prédit par le facteur engagé seul
#
#  Formules exactes Quarg-Mack 2004
#  ----------------------------------
#
#  Facteurs CL standard (volume-weighted) :
#
#      f_P[j] = Σ C_P[i,j+1] / Σ C_P[i,j]
#      f_E[j] = Σ C_E[i,j+1] / Σ C_E[i,j]
#
#  Ratio de règlement :
#      Q[i,j] = C_P[i,j] / C_E[i,j]    (si C_E[i,j] > 0)
#
#  Coefficients λ (Quarg-Mack 2004, eq. 4.2 et 4.3) :
#
#      λ_P[j] = Cov(r_P[i,j], r_Q[i,j]) / Var(r_Q[i,j])
#      λ_E[j] = Cov(r_E[i,j], r_Q[i,j]) / Var(r_Q[i,j])
#
#  où r_P, r_E, r_Q sont les résidus normalisés des régressions respectives.
#
#  Conditions d'activation
#  -----------------------
#  Munich CL nécessite :
#    1. Triangle engagé fourni et de même dimension que le payé
#    2. C_E[i,j] ≥ C_P[i,j] pour tout i,j  (engagé ≥ payé)
#    3. Au moins 4 années de survenance (sinon λ non estimable)
#    4. Q[i,j] ∈ [0,1] pour la majorité des cellules
#
#  Si ces conditions ne sont pas remplies → méthode désactivée avec message.
#
#  Note sur la v4.0
#  ----------------
#  En v4.0, λ était cappé arbitrairement à 0.30 sans justification.
#  En v5.0 : λ estimé par régression conforme Quarg-Mack 2004, sans cap.
#  Un cap de sécurité [0, 2.0] est appliqué uniquement pour éviter les
#  instabilités numériques sur petits triangles.
#
# =============================================================================

import logging
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  VALIDATION DES PRÉREQUIS
# =============================================================================

def valider_prerequis(
    C_P: np.ndarray,
    C_E: np.ndarray,
) -> Tuple[bool, str]:
    """
    Vérifie que les conditions d'activation du Munich CL sont remplies.

    Returns
    -------
    (ok, message) : bool, str
    """
    if C_E is None:
        return False, "Triangle engagé non fourni — Munich CL désactivé."

    if C_P.shape != C_E.shape:
        return False, (
            f"Dimensions incompatibles : payé {C_P.shape} ≠ "
            f"engagé {C_E.shape} — Munich CL désactivé."
        )

    n, m = C_P.shape
    if n < 4:
        return False, (
            f"Triangle trop petit ({n} années) — "
            f"λ non estimable avec < 4 observations. Munich CL désactivé."
        )

    # Vérifier que engagé ≥ payé sur la zone connue
    n_violations = 0
    for i in range(n):
        for j in range(min(m, n - i)):
            if C_P[i, j] > 0 and C_E[i, j] > 0:
                if C_P[i, j] > C_E[i, j] * (1.0 + tolerance_ep):  # Quarg-Mack : C_E >= C_P
                    n_violations += 1

    pct_violations = n_violations / max(n * m // 2, 1)
    if pct_violations > 0.20:
        return False, (
            f"{n_violations} cellules où payé > engagé×1.05 "
            f"({pct_violations*100:.0f}% du triangle) — "
            f"triangle engagé incohérent. Munich CL désactivé."
        )

    return True, "Prérequis Munich CL satisfaits."


# =============================================================================
#  FACTEURS CL STANDARD SUR UN TRIANGLE
# =============================================================================

def _facteurs_cl(C: np.ndarray) -> np.ndarray:
    """
    Facteurs CL volume-weighted standard sur un triangle.
    f_j = Σ C[i,j+1] / Σ C[i,j]  (zone connue)
    """
    n, m     = C.shape
    facteurs = np.ones(m - 1)
    for j in range(m - 1):
        num = den = 0.0
        for i in range(n):
            if i + j + 1 < n and C[i, j] > 0 and C[i, j+1] > 0:
                num += C[i, j+1]
                den += C[i, j]
        facteurs[j] = max(num / max(den, 1e-10), 1.0)
    return facteurs


# =============================================================================
#  COEFFICIENTS λ  (Quarg-Mack 2004, eq. 4.2–4.3)
# =============================================================================

def _calculer_lambda(
    C_P: np.ndarray,
    C_E: np.ndarray,
    f_P: np.ndarray,
    f_E: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Estime les coefficients λ_P[j] et λ_E[j] par régression OLS.

    Pour chaque colonne j :

    Résidus payé   : r_P[i,j] = C_P[i,j+1]/C_P[i,j] - f_P[j]
    Résidus engagé : r_E[i,j] = C_E[i,j+1]/C_E[i,j] - f_E[j]
    Résidus ratio  : r_Q[i,j] = Q[i,j] - Q_moy[j]
                     où Q[i,j] = C_P[i,j]/C_E[i,j]

    λ_P[j] = Cov(r_P[i,j], r_Q[i,j]) / Var(r_Q[i,j])
    λ_E[j] = Cov(r_E[i,j], r_Q[i,j]) / Var(r_Q[i,j])

    Cap de sécurité : λ ∈ [0, 2.0] (stabilité numérique)
    """
    n, m = C_P.shape

    lam_P = np.zeros(m - 1)
    lam_E = np.zeros(m - 1)

    for j in range(m - 1):
        r_P_j, r_E_j, r_Q_j = [], [], []

        Q_obs = []
        for i in range(n):
            if i + j + 1 < n:
                cp  = C_P[i, j]
                cp1 = C_P[i, j+1]
                ce  = C_E[i, j]
                ce1 = C_E[i, j+1]
                if cp > 0 and cp1 > 0 and ce > 0 and ce1 > 0:
                    Q_obs.append(cp / ce)

        if len(Q_obs) < 3:
            # Pas assez d'observations → λ = 0 (CL standard)
            continue

        Q_moy = float(np.mean(Q_obs))

        for i in range(n):
            if i + j + 1 < n:
                cp  = C_P[i, j]
                cp1 = C_P[i, j+1]
                ce  = C_E[i, j]
                ce1 = C_E[i, j+1]
                if cp > 0 and cp1 > 0 and ce > 0 and ce1 > 0:
                    r_P_j.append(cp1/cp  - f_P[j])
                    r_E_j.append(ce1/ce  - f_E[j])
                    r_Q_j.append(cp/ce   - Q_moy)

        if len(r_Q_j) < 3:
            continue

        r_P_arr = np.array(r_P_j)
        r_E_arr = np.array(r_E_j)
        r_Q_arr = np.array(r_Q_j)

        var_Q = float(np.var(r_Q_arr, ddof=1))
        if var_Q < 1e-12:
            # Ratio constant → pas de corrélation exploitable
            logger.warning(
                f'Munich CL : Var(r_Q) ≈ 0 colonne j={j} — '
                f'ratio Q constant, pas de corrélation exploitable. '
                f'λ_P[{j}] = λ_E[{j}] = 0.'
            )
            continue

        cov_P = float(np.cov(r_P_arr, r_Q_arr, ddof=1)[0, 1])
        cov_E = float(np.cov(r_E_arr, r_Q_arr, ddof=1)[0, 1])

        # Cap λ ∈ [0, lambda_max] — Quarg-Mack ne cappe pas mais nécessaire en pratique
        lam_P[j] = float(np.clip(cov_P / var_Q, 0.0, lambda_max))
        lam_E[j] = float(np.clip(cov_E / var_Q, 0.0, lambda_max))

    return lam_P, lam_E


# =============================================================================
#  MUNICH CHAIN LADDER — FONCTION PRINCIPALE
# =============================================================================

def munich_cl(
    C_P:          np.ndarray,
    C_E:          Optional[np.ndarray],
    annee_base:   int   = 1,
    tolerance_ep: float = 0.05,
    lambda_max:   float = 2.0,
) -> Dict:
    """
    Paramètres supplémentaires
    --------------------------
    tolerance_ep : tolérance sur C_E >= C_P (0.0 = strict Quarg-Mack, 0.05 = défaut).
    lambda_max   : cap sur λ_P et λ_E (défaut 2.0 — Quarg-Mack ne cappe pas).
    """
    """
    Munich Chain Ladder (Quarg & Mack 2004).

    Réduit la divergence entre projections payé et engagé en exploitant
    la corrélation entre les deux triangles via les ratios Q[i,j].

    Parameters
    ----------
    C_P : np.ndarray  shape (n, m)
        Triangle cumulé payé.
    C_E : np.ndarray or None  shape (n, m)
        Triangle cumulé engagé (charges sinistres notifiées).
        None → méthode désactivée avec message explicite.
    annee_base : int
        Première année incluse dans la réserve (défaut = 1).

    Returns
    -------
    dict avec :
        disponible      : bool
        be_munich_paye  : réserve payé MCL
        be_munich_engage: réserve engagé MCL
        be_cl_paye      : réserve payé CL standard (référence)
        be_cl_engage    : réserve engagé CL standard (référence)
        ecart_pct       : écart MCL payé vs CL payé en %
        lambda_P, lambda_E : coefficients par colonne
        statut, message
    """
    # ── 1. Validation prérequis ───────────────────────────────────────────────
    ok, msg_prereq = valider_prerequis(C_P, C_E)
    if not ok:
        logger.info(f"Munich CL désactivé : {msg_prereq}")
        return {
            'disponible': False,
            'statut':     'INFO',
            'message':    msg_prereq,
            'methode':    'Munich Chain Ladder (Quarg & Mack 2004)',
        }

    n, m = C_P.shape

    # ── 2. Facteurs CL standard ───────────────────────────────────────────────
    f_P = _facteurs_cl(C_P)
    f_E = _facteurs_cl(C_E)

    # ── 3. Coefficients λ (Quarg-Mack 2004) ──────────────────────────────────
    lam_P, lam_E = _calculer_lambda(C_P, C_E, f_P, f_E)

    # ── 4. Facteurs Munich ajustés ────────────────────────────────────────────
    #
    # f*_P[j] = f_P[j] + λ_P[j] × (Q_moy[j] - q̂_P[j])
    # f*_E[j] = f_E[j] + λ_E[j] × (Q_moy[j] - q̂_E[j])
    #
    # où Q_moy[j] = ratio moyen payé/engagé à la colonne j
    #    q̂_P[j]  = Q_moy[j] × f_P[j] / f_E[j]  (ratio prédit CL payé)
    #    q̂_E[j]  = Q_moy[j] × f_E[j] / f_P[j]  (ratio prédit CL engagé)

    f_star_P = f_P.copy()
    f_star_E = f_E.copy()

    for j in range(m - 1):
        Q_obs = []
        for i in range(n):
            if i + j < n and C_P[i, j] > 0 and C_E[i, j] > 0:
                Q_obs.append(C_P[i, j] / C_E[i, j])

        if not Q_obs or f_E[j] <= 0:
            continue

        Q_moy = float(np.mean(Q_obs))

        # Ratio prédit par CL payé seul
        q_hat_P = Q_moy * f_P[j] / max(f_E[j], 1e-10)

        # Ratio prédit par CL engagé seul
        q_hat_E = Q_moy * f_E[j] / max(f_P[j], 1e-10)

        # Facteurs ajustés
        adj_P = lam_P[j] * (Q_moy - q_hat_P)
        adj_E = lam_E[j] * (Q_moy - q_hat_E)

        f_star_P[j] = max(f_P[j] + adj_P, 1.0)
        f_star_E[j] = max(f_E[j] + adj_E, 1.0)

    # ── 5. Projections MCL et CL ──────────────────────────────────────────────
    def projeter(C, facteurs):
        """Projette les ultimates et IBNR."""
        ult  = np.zeros(n)
        ibnr = np.zeros(n)
        ld   = np.array([
            float(C[i, min(n - i - 1, m - 1)]) for i in range(n)
        ])
        for i in range(n):
            k_i = min(n - i - 1, m - 1)
            val = float(C[i, k_i])
            for j in range(k_i, m - 1):
                if j < len(facteurs):
                    val *= facteurs[j]
            ult[i]  = val
            ibnr[i] = max(val - ld[i], 0.0)
        return ult, ibnr, ld

    ult_mp, ibnr_mp, ld_P = projeter(C_P, f_star_P)
    ult_me, ibnr_me, ld_E = projeter(C_E, f_star_E)
    ult_cp, ibnr_cp, _    = projeter(C_P, f_P)
    ult_ce, ibnr_ce, _    = projeter(C_E, f_E)

    # Réserves
    R_mp = float(np.sum(ibnr_mp[annee_base:]))
    R_me = float(np.sum(ibnr_me[annee_base:]))
    R_cp = float(np.sum(ibnr_cp[annee_base:]))
    R_ce = float(np.sum(ibnr_ce[annee_base:]))

    ecart_P = (R_mp - R_cp) / max(R_cp, 1e-9) * 100.0
    ecart_E = (R_me - R_ce) / max(R_ce, 1e-9) * 100.0

    # Convergence : MCL réduit l'écart payé vs engagé
    ecart_cl  = abs(R_cp - R_ce) / max(R_cp, 1e-9) * 100.0
    ecart_mcl = abs(R_mp - R_me) / max(R_mp, 1e-9) * 100.0
    convergence = ecart_cl - ecart_mcl   # > 0 = MCL réduit l'écart

    # Statut
    if abs(ecart_P) < 5.0:
        statut = 'VERT'
    elif abs(ecart_P) < 15.0:
        statut = 'AMBRE'
    else:
        statut = 'ROUGE'

    msg = (
        f"Munich CL : payé_MCL={R_mp:,.0f}€ "
        f"({'+' if ecart_P >= 0 else ''}{ecart_P:.1f}% vs CL payé) · "
        f"engagé_MCL={R_me:,.0f}€ · "
        f"convergence={convergence:+.1f} pts"
    )
    logger.info(msg)

    # Compter les incréments négatifs (P et E) pour audit
    _inc_P = np.diff(C_P_f, axis=1)
    _inc_E = np.diff(C_E_f, axis=1)
    n_neg_P = int(np.sum(_inc_P[~np.isnan(_inc_P)] < 0))
    n_neg_E = int(np.sum(_inc_E[~np.isnan(_inc_E)] < 0))
    if n_neg_P > 0 or n_neg_E > 0:
        logger.warning(
            f'Munich CL : {n_neg_P} incrément(s) payé négatif(s), '
            f'{n_neg_E} incrément(s) engagé négatif(s) — '
            f'cellules ignorées dans le calcul des λ.'
        )

    return {
        'n_increments_negatifs_paye':   n_neg_P,
        'n_increments_negatifs_engage': n_neg_E,
        'disponible':         True,

        # Réserves MCL
        'be_munich_paye':     round(R_mp, 2),
        'be_munich_engage':   round(R_me, 2),

        # Réserves CL standard (référence)
        'be_cl_paye':         round(R_cp, 2),
        'be_cl_engage':       round(R_ce, 2),

        # Écarts
        'ecart_pct_paye':     round(ecart_P, 2),
        'ecart_pct_engage':   round(ecart_E, 2),
        'ecart_cl_paye_engage': round(ecart_cl,  2),
        'ecart_mcl_paye_engage': round(ecart_mcl, 2),
        'convergence_pts':    round(convergence,  2),

        # Coefficients λ par colonne
        'lambda_P':           [round(float(l), 4) for l in lam_P],
        'lambda_E':           [round(float(l), 4) for l in lam_E],

        # Facteurs
        'facteurs_cl_paye':   [round(float(f), 4) for f in f_P],
        'facteurs_cl_engage': [round(float(f), 4) for f in f_E],
        'facteurs_munich_paye':   [round(float(f), 4) for f in f_star_P],
        'facteurs_munich_engage': [round(float(f), 4) for f in f_star_E],

        # IBNR par année
        'ibnr_munich_paye':   [round(float(v), 2) for v in ibnr_mp],
        'ibnr_munich_engage': [round(float(v), 2) for v in ibnr_me],

        # Métadonnées
        'statut':    statut,
        'methode':   'Munich Chain Ladder (Quarg & Mack 2004)',
        'message':   msg,
        'conseil': (
            "Écart MCL/CL faible — CL suffisant."
            if abs(ecart_P) < 5.0 else
            "Écart MCL/CL significatif — sur/sous-provisionnement dossier possible."
            if abs(ecart_P) < 15.0 else
            "Écart MCL/CL élevé — révision approfondie des dossiers recommandée."
        ),
    }
