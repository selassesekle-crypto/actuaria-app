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

from direction_non_vie.services.nv_triangle_projection import projeter_ultimates
# Source UNIQUE des facteurs de développement dans A7 : Munich avait sa propre
# copie, restée bloquée sur l'ancien plancher f ≥ 1 après son retrait du Lot 2.
from .chain_ladder import calculer_facteurs

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  VALIDATION DES PRÉREQUIS
# =============================================================================

def valider_prerequis(
    C_P:          np.ndarray,
    C_E:          np.ndarray,
    tolerance_ep: float = 0.05,
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

    # Vérifier que engagé ≥ payé sur la zone connue (Quarg-Mack : C_E >= C_P).
    # Le contrôle porte sur TOUTES les cellules connues, SANS garde > 0 : un
    # engagé ≤ 0 avec un payé positif est une vraie incohérence et ne doit pas
    # échapper au test. Une cellule non remplie (payé = engagé = 0) ne déclenche
    # rien (0 > 0 est faux).
    n_violations = 0
    for i in range(n):
        for j in range(min(m, n - i)):
            if C_P[i, j] > C_E[i, j] * (1.0 + tolerance_ep):
                n_violations += 1

    pct_violations = n_violations / max(n * m // 2, 1)
    if pct_violations > 0.20:
        return False, (
            f"{n_violations} cellules où payé > engagé×{1.0+tolerance_ep:.0%} "
            f"({pct_violations*100:.0f}% du triangle) — "
            f"triangle engagé incohérent. Munich CL désactivé."
        )

    # ── Détection de circularité (Quarg & Mack 2004) ─────────────────────────
    # Métrique : coefficient de variation (CV) des ratios C_E/C_P.
    # Si engage = payé × constante → CV ≈ 0 → circularité certaine.
    # Un triangle indépendant a des ratios variables (CV > 0.05) car
    # l'IBNR varie selon la cohorte et l'ancienneté des dossiers.
    try:
        # numpy déjà importé comme np en tête de fichier
        _ratios = []
        for _i in range(n):
            for _j in range(min(m, n - _i)):
                if C_P[_i,_j] > 0 and C_E[_i,_j] > 0:
                    _ratios.append(float(C_E[_i,_j] / C_P[_i,_j]))
        if len(_ratios) >= 6:
            _r = np.array(_ratios)
            _cv = float(np.std(_r) / np.mean(_r)) if np.mean(_r) > 0 else 0.0
            if _cv < 0.02:
                return False, (
                    f'CIRCULARITE DETECTEE — CV des ratios engagé/payé = {_cv:.4f} < 0.02. '
                    f'Les charges engagées sont proportionnelles aux paiements (ratio quasi-constant). '
                    f'Elles semblent calculées depuis les provisions actuarielles. '
                    f'Munich CL désactivé (Quarg & Mack 2004). '
                    f'Utilisez des évaluations dossier par dossier indépendantes des provisions.'
                )
            elif _cv < 0.05:
                return True, (
                    f'⚠️ CV faible des ratios engagé/payé = {_cv:.4f} (seuil alerte 0.05). '
                    f'Vérifiez que les charges engagées sont indépendantes des provisions. '
                    f'Munich CL activé sous réserve de validation actuaire.'
                )
    except Exception:
        pass  # Détection circularité non bloquante

    return True, "Prérequis Munich CL satisfaits."


# =============================================================================
#  COEFFICIENTS λ  (Quarg-Mack 2004, eq. 4.2–4.3)
# =============================================================================

def _calculer_lambda(
    C_P:        np.ndarray,
    C_E:        np.ndarray,
    f_P:        np.ndarray,
    f_E:        np.ndarray,
    lambda_max: float = 2.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Estime λ_P[j], λ_E[j] et Q_moy_vec[j] par régression OLS pondérée.
    Q_moy_vec est retourné pour éviter le recalcul dans munich_cl (Gemini §3).

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

    lam_P    = np.zeros(m - 1)
    lam_E    = np.zeros(m - 1)
    Q_moy_vec = np.zeros(m - 1)  # Q_moy volumique par colonne

    for j in range(m - 1):
        r_P_j, r_E_j, r_Q_j = [], [], []

        # ── Q_moy volumique (Quarg & Mack eq. 3.3) ──────────────────────
        # Q̄[j] = Σ C_P[i,j] / Σ C_E[i,j]  (ratio des sommes, pas moyenne arithmétique)
        sum_CP = sum_CE = 0.0
        for i in range(n):
            if i + j + 1 < n:
                cp = C_P[i, j]; ce = C_E[i, j]
                if cp > 0 and ce > 0:
                    sum_CP += cp; sum_CE += ce

        if sum_CE < 1e-10 or sum_CP < 1e-10:
            continue

        Q_moy = sum_CP / sum_CE  # volumique — conforme Quarg & Mack eq. 3.3
        Q_moy_vec[j] = Q_moy      # stocké pour munich_cl (évite recalcul)

        # ── Résidus pondérés (Quarg & Mack eq. 3.1 — Gauss-Markov) ─────
        # Var(F_P[i,j]) = σ²/C_P[i,j] → pondération par sqrt(C_P[i,j])
        # Filtrer les incréments négatifs (biais sur la régression)
        for i in range(n):
            if i + j + 1 < n:
                cp  = C_P[i, j]; cp1 = C_P[i, j+1]
                ce  = C_E[i, j]; ce1 = C_E[i, j+1]
                if cp > 0 and cp1 > 0 and ce > 0 and ce1 > 0:
                    # Filtrer incréments négatifs
                    if cp1 < cp or ce1 < ce:
                        logger.warning(
                            f'MCL _calculer_lambda : incrément négatif ignoré '
                            f'i={i} j={j} (cp={cp:.0f}→{cp1:.0f} ce={ce:.0f}→{ce1:.0f})'
                        )
                        continue
                    # Résidus pondérés par sqrt(charge) — Mack eq. 3.1
                    w_P = float(np.sqrt(cp))
                    w_E = float(np.sqrt(ce))
                    r_P_j.append((cp1/cp - f_P[j]) * w_P)
                    r_E_j.append((ce1/ce - f_E[j]) * w_E)
                    r_Q_j.append((cp/ce  - Q_moy)  * w_P)

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

    return lam_P, lam_E, Q_moy_vec


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
    ok, msg_prereq = valider_prerequis(C_P, C_E, tolerance_ep=tolerance_ep)
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
    # Source unique (chain_ladder) : un facteur < 1 (recours/subrogation) est
    # conservé tel quel. Il se propage aux λ, aux ratios prédits q̂ et aux
    # facteurs ajustés f* — ces derniers restent bornés à 1.0 plus bas (verrou
    # distinct, décision séparée).
    f_P, _ = calculer_facteurs(C_P)
    f_E, _ = calculer_facteurs(C_E)

    # ── 3. Coefficients λ (Quarg-Mack 2004) ──────────────────────────────────
    lam_P, lam_E, Q_moy_vec = _calculer_lambda(C_P, C_E, f_P, f_E, lambda_max=lambda_max)

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
    # f* ≤ 0 rabattu sur le facteur CL (garde défensive, cf. boucle) — jamais
    # observé en pratique (min 0.67 sur 12 000 paires testées).
    facteurs_degeneres_paye:   list = []
    facteurs_degeneres_engage: list = []

    idx = np.arange(n)
    for j in range(m - 1):
        if f_E[j] <= 0 or f_P[j] <= 0:
            continue

        # Q_moy issu de _calculer_lambda — pas de recalcul (Gemini §3)
        Q_moy = Q_moy_vec[j]
        if Q_moy <= 0:
            # Fallback vectorisé si Q_moy non calculé (colonnes courtes)
            masque_j = (C_P[:, j] > 0) & (C_E[:, j] > 0) & (idx + j < n)
            sp = float(np.sum(C_P[masque_j, j]))
            se = float(np.sum(C_E[masque_j, j]))
            Q_moy = sp / max(se, 1e-10)

        # q̂_P[j] = Q_moy × f_P[j] / f_E[j]  (Quarg & Mack eq. 4.4)
        q_hat_P = Q_moy * f_P[j] / max(f_E[j], 1e-10)

        # q̂_E[j] = Q_moy × f_E[j] / f_P[j]  (même Q, ratio prédit CL engagé)
        # NB : Quarg & Mack raisonnent toujours sur Q = P/E, pas sur Q* = E/P
        q_hat_E = Q_moy * f_E[j] / max(f_P[j], 1e-10)

        # Facteurs ajustés — Quarg & Mack eq. 4.4 :
        # f*_P[j] = f_P[j] + λ_P[j] × (q̂_P[j] - Q_moy)
        # f*_E[j] = f_E[j] + λ_E[j] × (Q_moy - q̂_E[j])
        # Signe f*_P : si f_P>f_E → q̂_P>Q_moy → adj_P>0 → f*_P hausse
        # Signe f*_E : si f_E<f_P → q̂_E<Q_moy → adj_E>0 → f*_E hausse
        adj_P = lam_P[j] * (q_hat_P - Q_moy)
        adj_E = lam_E[j] * (Q_moy   - q_hat_E)

        # Facteur ajusté CONSERVÉ tel quel, y compris < 1.0 (recours/subrogation).
        # Le forçage historique max(…, 1.0) est retiré (Lot C2) : sur une colonne
        # en recours λ vaut 0 (les incréments négatifs sont écartés du calcul des
        # λ, l.233), donc f* = f_CL, et max(f_CL, 1.0) ré-appliquait EXACTEMENT le
        # plancher du verrou 1 déjà retiré au Lot C1 — annulant sa correction. Les
        # f* < 1 sont désormais conservés et signalés (facteurs_munich_sous_1_*).
        #
        # Garde résiduelle UNIQUEMENT contre le cas dégénéré f* ≤ 0 (ultime nul ou
        # négatif) : jamais observé en pratique (f* min 0.67 sur 12 000 paires),
        # garde purement défensive. Repli = facteur CL non ajusté (borné > 0 par
        # construction de calculer_facteurs) → l'ajustement Munich est annulé pour
        # cette seule cellule, exactement comme si λ y valait 0.
        f_P_adj = f_P[j] + adj_P
        f_E_adj = f_E[j] + adj_E
        if f_P_adj <= 0.0:
            f_star_P[j] = f_P[j]
            facteurs_degeneres_paye.append([int(j), round(float(f_P_adj), 6)])
        else:
            f_star_P[j] = f_P_adj
        if f_E_adj <= 0.0:
            f_star_E[j] = f_E[j]
            facteurs_degeneres_engage.append([int(j), round(float(f_E_adj), 6)])
        else:
            f_star_E[j] = f_E_adj

    # ── Facteurs f* < 1.0 conservés (recours) — signalés, jamais forcés ────────
    # Même politique que chain_ladder ('facteurs_sous_1', Lot 2).
    facteurs_munich_sous_1_paye = [
        [int(j), round(float(f_star_P[j]), 6)]
        for j in range(len(f_star_P)) if f_star_P[j] < 1.0
    ]
    facteurs_munich_sous_1_engage = [
        [int(j), round(float(f_star_E[j]), 6)]
        for j in range(len(f_star_E)) if f_star_E[j] < 1.0
    ]
    if facteurs_munich_sous_1_paye or facteurs_munich_sous_1_engage:
        logger.warning(
            f"Munich CL : f* < 1.0 conservé(s) (recours/subrogation) — "
            f"payé {facteurs_munich_sous_1_paye}, engagé {facteurs_munich_sous_1_engage}"
        )
    if facteurs_degeneres_paye or facteurs_degeneres_engage:
        logger.warning(
            f"Munich CL : garde f* ≤ 0 déclenchée (cas dégénéré, jamais vu en "
            f"pratique) — repli sur le facteur CL — "
            f"payé {facteurs_degeneres_paye}, engagé {facteurs_degeneres_engage}"
        )

    # ── 5. Projections MCL et CL ──────────────────────────────────────────────
    def projeter(C, facteurs):
        """Projette ultimates et IBNR via le helper de projection partagé
        (tail=1.0). IBNR plancheré — comportement historique inchangé."""
        p = projeter_ultimates(C, facteurs, tail_factor=1.0)
        return p['ultimate'], p['ibnr_plancher'], p['last_diag']

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
    if facteurs_munich_sous_1_paye or facteurs_munich_sous_1_engage:
        msg += (
            f" | ⚠️ f* < 1.0 conservé(s) (recours) — colonnes payé "
            f"{[j for j, _ in facteurs_munich_sous_1_paye]}, engagé "
            f"{[j for j, _ in facteurs_munich_sous_1_engage]}"
        )
    logger.info(msg)

    # Compter les incréments négatifs (P et E) pour audit
    _inc_P = np.diff(np.where(np.isnan(C_P), 0, C_P), axis=1)
    _inc_E = np.diff(np.where(np.isnan(C_E), 0, C_E), axis=1)
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

        # Facteurs f* < 1.0 conservés (recours) : [[colonne, valeur], ...]
        'facteurs_munich_sous_1_paye':   facteurs_munich_sous_1_paye,
        'facteurs_munich_sous_1_engage': facteurs_munich_sous_1_engage,
        # f* ≤ 0 rabattus sur le CL (garde défensive, jamais vu en pratique)
        'facteurs_degeneres_paye':   facteurs_degeneres_paye,
        'facteurs_degeneres_engage': facteurs_degeneres_engage,

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