# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n3/mack.py  —  Méthode de Mack (1993) — extension stochastique du CL
# =============================================================================
#
#  Référence principale
#  --------------------
#  Mack, T. (1993). "Distribution-Free Calculation of the Standard Error
#  of Chain Ladder Reserve Estimates."
#  ASTIN Bulletin, 23(2), pp. 213–225.
#
#  Référence réglementaire
#  -----------------------
#  Solvabilité II, Art. 77 — Best Estimate des provisions techniques
#  EIOPA (2014), Guidelines on valuation of technical provisions
#  QIS5 Technical Specifications (2010), TP.5.26 — log-normale pour IBNR
#
#  Formules implémentées
#  ---------------------
#
#  1. Variance par colonne σ²_j  (Mack 1993, formule 3.4)
#  ────────────────────────────────────────────────────────
#
#      σ²_j = 1/(n_j - 1) × Σ_{i : i+j+1 < n} C[i,j] × (f[i,j] - f̂_j)²
#
#      avec  f[i,j] = C[i,j+1] / C[i,j]   (facteur individuel)
#            f̂_j   = facteur CL agrégé de la colonne j
#            n_j    = nombre d'observations disponibles pour la colonne j
#
#  2. Cas n_j = 1 (dernière colonne)  (Mack 1993, formule 3.5)
#  ─────────────────────────────────────────────────────────────
#
#      Quand une seule observation est disponible, σ² est extrapolée :
#
#      σ²_{m-2} = min(σ²_{m-3}, σ²_{m-4}, σ⁴_{m-3} / σ²_{m-4})
#
#      Cette formule garantit que σ² décroît vers 0 en fin de développement.
#      (Implémentation v4.0 incorrecte : utilisait une extrapolation
#       quadratique non conforme à Mack 1993.)
#
#  3. Variance de réserve par année i  (Mack 1993, Theorem 3)
#  ─────────────────────────────────────────────────────────────
#
#      Var(R̂_i) = Û²_{i,n} × Σ_{j=k_i}^{m-2}  σ²_j / f̂²_j
#                             × (1/C[i,j_proj] + 1/Σ_l C[l,j])
#
#      où  k_i        = min(n-i-1, m-1)  : dernière colonne connue de l'année i
#          Û_{i,n}    : ultimate projeté de l'année i
#          C[i,j_proj]: valeur projetée de C[i,j] (en cours de projection)
#          Σ_l C[l,j] : somme des volumes sur la colonne j (toutes années)
#
#  4. Variance totale  (Mack 1993, Theorem 3 — termes croisés)
#  ─────────────────────────────────────────────────────────────
#
#      Var(R̂) = Σ_i Var(R̂_i)
#              + 2 × Σ_{i<l} Û_{i,n} × Û_{l,n}
#                    × Σ_{j=k_l}^{m-2} σ²_j / (f̂²_j × Σ_q C[q,j])
#
#      Les termes croisés capturent la corrélation entre années de survenance
#      via les facteurs CL communs — souvent omis dans les implémentations
#      simplifiées, mais obligatoires pour le calcul S2.
#
#  5. Distribution log-normale  (QIS5 TP.5.26, S2 Art. 77)
#  ─────────────────────────────────────────────────────────
#
#      La loi log-normale est retenue pour les provisions IBNR en S2.
#      Paramètres ajustés sur (BE, σ) :
#
#      σ_LN = √(ln(1 + (σ/BE)²))
#      μ_LN = ln(BE) - σ²_LN / 2
#
#      Percentiles : P_α = exp(μ_LN + z_α × σ_LN)
#
#      Quantiles z_α (loi normale standard) :
#        P75  : z = 0.6745
#        P90  : z = 1.2816   ← stress test S2 courant
#        P95  : z = 1.6449
#        P99.5: z = 2.5758   ← SCR provisions (VaR 99.5% horizon 1 an)
#
#      Critères EIOPA (Guidelines TP) :
#        CV = σ/BE < 10%  → VERT  (incertitude faible)
#        CV = 10%–20%     → AMBRE (incertitude modérée)
#        CV > 20%         → ROUGE (incertitude élevée, vigilance S2)
#
# =============================================================================

import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  VARIANCE PAR COLONNE σ²_j
# =============================================================================

def calculer_sigma2(
    C:              np.ndarray,
    facteurs:       np.ndarray,
    facteurs_indiv: List[List[float]],
) -> np.ndarray:
    """
    Calcule les variances σ²_j par colonne selon Mack (1993), formules 3.4–3.5.

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé.
    facteurs : np.ndarray  shape (m-1,)
        Facteurs CL agrégés f̂_0, ..., f̂_{m-2}.
    facteurs_indiv : List[List[float]]
        facteurs_indiv[j] = liste des f[i,j] = C[i,j+1]/C[i,j].

    Returns
    -------
    sigma2 : np.ndarray  shape (m-1,)
        σ²_j pour j = 0, ..., m-2.
        Valeurs ≥ 0. La dernière colonne est extrapolée via formule 3.5
        quand n_j ≤ 1.
    """
    n, m   = C.shape
    sigma2 = np.zeros(m - 1)

    for j in range(m - 1):
        f_ind = facteurs_indiv[j]
        f_j   = float(facteurs[j])
        n_j   = len(f_ind)

        if n_j < 2:
            # Cas n_j ≤ 1 : extrapolation via formule Mack 3.5 (voir ci-dessous)
            continue

        # Récupérer C[i,j] correspondants aux facteurs disponibles
        c_j = []
        for i in range(n):
            if i + j + 1 < n and C[i, j] > 0 and C[i, j+1] > 0:
                c_j.append(float(C[i, j]))
            if len(c_j) == n_j:
                break

        if len(c_j) < 2:
            continue

        # σ²_j = 1/(n_j - 1) × Σ C[i,j] × (f[i,j] - f̂_j)²
        num = sum(
            c_j[k] * (f_ind[k] - f_j) ** 2
            for k in range(min(n_j, len(c_j)))
        )
        sigma2[j] = num / (n_j - 1)

    # ── Extrapolation des σ²_j manquants (Mack 1993, formule 3.5) ──────────
    #
    # Mack 1993 formule 3.5 — pour toute colonne j où n_j ≤ 1 :
    #   σ²_j = min(σ²_{j-1}, σ²_{j-2}, σ⁴_{j-1} / σ²_{j-2})
    #
    # Propriété : garantit la décroissance σ²_{j} ≤ σ²_{j-1} ≤ σ²_{j-2}.
    # Le 3ème terme est la progression géométrique de la décroissance.
    #
    # Implémentation : passage unique de gauche à droite.
    # Les valeurs déjà extrapolées au tour j-1 sont utilisées au tour j
    # — ce qui est correct car on cherche à propager la décroissance.
    # Si plusieurs colonnes consécutives sont à 0, chaque extrapolation
    # s'appuie sur la précédente (déjà extrapolée), garantissant une
    # décroissance continue sans plateau artificiel.
    #
    # Note triangles rectangulaires (m >> n) :
    # Sur des triangles avec beaucoup plus de colonnes que d'années,
    # la majorité des σ²_j sera extrapolée. La qualité de l'extrapolation
    # dépend des 2-3 premières valeurs observées — à interpréter avec
    # précaution. Dans ActuarIA, les triangles typiques sont n×m avec
    # n ≈ m (10×10 à 30×30), ce cas reste donc marginal.

    # j=1 : cas spécial — un seul précédent disponible
    if m > 2 and sigma2[1] == 0 and sigma2[0] > 0:
        sigma2[1] = sigma2[0]

    # j ≥ 2 : formule Mack 3.5 ou fallback décroissant
    for j in range(2, m - 1):
        if sigma2[j] > 0:
            continue  # valeur observée — pas d'extrapolation

        s_prev1 = sigma2[j - 1]   # σ²_{j-1} (peut être extrapolé)
        s_prev2 = sigma2[j - 2]   # σ²_{j-2} (peut être extrapolé)

        if s_prev1 > 0 and s_prev2 > 0:
            # Formule Mack 3.5 exacte
            sigma2[j] = min(
                s_prev1,
                s_prev2,
                s_prev1 ** 2 / s_prev2,   # progression géométrique
            )
        elif s_prev1 > 0:
            # Un seul précédent — plateau conservateur
            sigma2[j] = s_prev1
        # else : laisser à 0 (aucune info disponible)

    return sigma2


# =============================================================================
#  SOMMES DES VOLUMES PAR COLONNE
# =============================================================================

def _sommes_volumes(C: np.ndarray) -> np.ndarray:
    """
    Calcule Σ_i C[i,j] pour chaque colonne j (zone connue uniquement).

    Utilisé dans la formule de variance Mack Theorem 3 :
        1 / Σ_i C[i,j]  →  terme correctif "collectif"

    Returns
    -------
    W : np.ndarray  shape (m-1,)
        W[j] = Σ_{i : i+j+1 < n, C[i,j]>0} C[i,j]
    """
    n, m = C.shape
    W    = np.zeros(m - 1)
    for j in range(m - 1):
        for i in range(n):
            if i + j + 1 < n and C[i, j] > 0:
                W[j] += C[i, j]
    return W


# =============================================================================
#  VARIANCE DE RÉSERVE PAR ANNÉE  (Mack 1993, Theorem 3)
# =============================================================================

def calculer_variance_reserve(
    C:          np.ndarray,
    facteurs:   np.ndarray,
    sigma2:     np.ndarray,
    ultimates:  np.ndarray,
) -> np.ndarray:
    """
    Variance de réserve par année de survenance (Mack 1993, Theorem 3).

    Pour chaque année i (i ≥ 1) :

        Var(R̂_i) = Û²_{i,n} × Σ_{j=k_i}^{m-2}
                    σ²_j / f̂²_j × (1/C_proj[i,j] + 1/W_j)

    où  k_i       = dernière colonne connue de l'année i
        C_proj    = valeur projetée intermédiaire de C[i,j]
        W_j       = Σ_l C[l,j]  (volume total colonne j, zone connue)
        Û_{i,n}   = ultimate projeté

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
    facteurs : np.ndarray  shape (m-1,)
    sigma2 : np.ndarray  shape (m-1,)
    ultimates : np.ndarray  shape (n,)

    Returns
    -------
    var_r : np.ndarray  shape (n,)
        Variance de réserve par année. var_r[0] = 0 par convention.
    """
    n, m  = C.shape
    W     = _sommes_volumes(C)
    var_r = np.zeros(n)

    for i in range(1, n):
        k_i    = min(n - i - 1, m - 1)   # dernière colonne connue
        U_i    = float(ultimates[i])
        if U_i <= 0:
            continue

        # Projeter C[i,j] de k_i vers m-1 pour avoir C_proj à chaque j
        c_proj = float(C[i, k_i])
        v      = 0.0

        for j in range(k_i, m - 1):
            if j >= len(facteurs) or j >= len(sigma2):
                break
            f_j = float(facteurs[j])
            s2j = float(sigma2[j])
            w_j = float(W[j])

            if f_j <= 0 or s2j <= 0:
                c_proj *= max(f_j, 1.0)
                continue

            # Terme individuel : 1/C_proj[i,j]
            terme_ind = 1.0 / max(c_proj, 1e-10)

            # Terme collectif : 1/W_j
            terme_col = 1.0 / max(w_j, 1e-10)

            # Contribution à la variance
            v += s2j / (f_j ** 2) * (terme_ind + terme_col)

            # Avancer la projection
            c_proj *= f_j

        # Var(R̂_i) = Û²_{i,n} × v
        var_r[i] = (U_i ** 2) * v

    return var_r


# =============================================================================
#  VARIANCE TOTALE AVEC TERMES CROISÉS  (Mack 1993, Theorem 3)
# =============================================================================

def calculer_variance_totale(
    C:          np.ndarray,
    facteurs:   np.ndarray,
    sigma2:     np.ndarray,
    ultimates:  np.ndarray,
    var_r:      np.ndarray,
    annee_base: int = 1,
) -> float:
    """
    Variance totale de la réserve incluant les termes croisés entre années.

    Var(R̂) = Σ_i Var(R̂_i)
            + 2 × Σ_{i<l} Û_{i,n} × Û_{l,n}
                  × Σ_{j=k_l}^{m-2} σ²_j / (f̂²_j × W_j)

    Les termes croisés capturent la corrélation entre années via les
    facteurs communs. Ils sont souvent oubliés mais obligatoires pour
    une variance conforme Mack 1993.

    Parameters
    ----------
    annee_base : int
        Première année incluse dans la réserve totale (défaut = 1).

    Returns
    -------
    float : variance totale.
    """
    n, m = C.shape
    W    = _sommes_volumes(C)

    # Somme des variances individuelles
    var_tot = float(np.sum(var_r[annee_base:]))

    # Termes croisés Σ_{i < l} ...
    for i in range(annee_base, n - 1):
        for l in range(i + 1, n):
            U_i = float(ultimates[i])
            U_l = float(ultimates[l])
            if U_i <= 0 or U_l <= 0:
                continue

            k_i = min(n - i - 1, m - 1)   # dernière colonne connue de l'année ANCIENNE i (queue commune)

            # Σ_{j=k_i}^{m-2} σ²_j / (f̂²_j × W_j)
            s = 0.0
            for j in range(k_i, m - 1):
                if j >= len(facteurs) or j >= len(sigma2):
                    break
                f_j = float(facteurs[j])
                s2j = float(sigma2[j])
                w_j = float(W[j])
                if f_j > 0 and s2j > 0 and w_j > 0:
                    s += s2j / (f_j ** 2 * w_j)

            var_tot += 2.0 * U_i * U_l * s

    return max(var_tot, 0.0)


# =============================================================================
#  PERCENTILES LOG-NORMALE  (QIS5 TP.5.26, S2 Art. 77)
# =============================================================================

def percentiles_log_normale(
    be:    float,
    sigma: float,
) -> Dict[str, float]:
    """
    Calcule les percentiles de la distribution log-normale calibrée
    sur (BE, σ) selon QIS5 Technical Specifications TP.5.26.

    La loi log-normale est le standard S2 pour les provisions IBNR.
    Elle est positive, asymétrique à droite, et compatible avec
    l'hypothèse de positivité des réserves.

    Paramètres de la loi
    --------------------
    σ_LN = √(ln(1 + (σ/BE)²))
    μ_LN = ln(BE) - σ²_LN / 2

    Vérification : E[X] = exp(μ_LN + σ²_LN/2) = BE  ✓

    Percentiles
    -----------
    P_α = exp(μ_LN + z_α × σ_LN)

    Quantiles z_α (loi normale standard) :
      P50  : z = 0.0000  (médiane)
      P75  : z = 0.6745  (provision de risque courante)
      P90  : z = 1.2816  (stress test S2)
      P95  : z = 1.6449
      P99.5: z = 2.5758  (SCR provisions, VaR 99.5% horizon 1 an)

    Parameters
    ----------
    be    : float  Best Estimate (espérance de la distribution).
    sigma : float  Écart-type total de Mack.

    Returns
    -------
    dict avec p50, p75, p90, p95, p99_5, mu_ln, sigma_ln.
    """
    if be <= 0 or sigma <= 0:
        return {
            'p50': be, 'p75': be, 'p90': be,
            'p95': be, 'p99_5': be,
            'mu_ln': 0.0, 'sigma_ln': 0.0,
        }

    cv    = sigma / be
    s2_ln = np.log(1.0 + cv ** 2)      # σ²_LN
    s_ln  = np.sqrt(s2_ln)             # σ_LN
    m_ln  = np.log(be) - s2_ln / 2.0   # μ_LN

    # Quantiles z_α de la loi normale standard
    z = {
        'p50':   0.0000,
        'p75':   0.6745,
        'p90':   1.2816,
        'p95':   1.6449,
        'p99_5': 2.5758,
    }

    return {
        key: round(float(np.exp(m_ln + z_val * s_ln)), 2)
        for key, z_val in z.items()
    } | {'mu_ln': round(m_ln, 6), 'sigma_ln': round(s_ln, 6)}


# =============================================================================
#  MACK 1993 — FONCTION PRINCIPALE
# =============================================================================

def mack_1993(
    C:              np.ndarray,
    facteurs:       np.ndarray,
    facteurs_indiv: List[List[float]],
    ultimates_cl:   np.ndarray,
    ibnr_cl:        np.ndarray,
    annee_base:     int = 1,
) -> Dict:
    """
    Méthode de Mack (1993) — extension stochastique du Chain Ladder.

    Quantifie l'incertitude de réserve sans hypothèse de distribution
    sur les facteurs de développement ("distribution-free").

    La distribution log-normale est ajoutée en post-traitement pour
    les percentiles S2 (QIS5 TP.5.26).

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé.
    facteurs : np.ndarray  shape (m-1,)
        Facteurs CL agrégés (depuis chain_ladder.py).
    facteurs_indiv : List[List[float]]
        Facteurs individuels par colonne (depuis chain_ladder.py).
    ultimates_cl : np.ndarray  shape (n,)
        Ultimates projetés par Chain Ladder.
    ibnr_cl : np.ndarray  shape (n,)
        IBNR par année (depuis chain_ladder.py).
    annee_base : int
        Première année incluse dans la réserve (défaut = 1).

    Returns
    -------
    dict conforme au standard ActuarIA avec :
        reserve_best_estimate, sigma_total, cv_pct
        reserve_p75, reserve_p90, reserve_p99_5
        sigma2_par_colonne, sigma_par_annee
        var_totale_avec_croisements
        statut ('VERT'|'AMBRE'|'ROUGE')
        methode, message
    """
    n, m       = C.shape
    ultimates  = np.array(ultimates_cl, dtype=float)
    ibnr       = np.array(ibnr_cl,      dtype=float)

    # ── 1. Variances σ²_j par colonne (formules 3.4–3.5) ────────────────────
    sigma2 = calculer_sigma2(C, facteurs, facteurs_indiv)

    # ── 2. Variance par année (Theorem 3) ────────────────────────────────────
    var_r = calculer_variance_reserve(C, facteurs, sigma2, ultimates)

    # ── 3. Variance totale avec termes croisés (Theorem 3) ───────────────────
    var_tot = calculer_variance_totale(
        C, facteurs, sigma2, ultimates, var_r, annee_base
    )

    sigma_par_annee = np.sqrt(np.maximum(var_r, 0.0))
    sigma_total     = float(np.sqrt(var_tot))
    reserve_be      = float(np.sum(ibnr[annee_base:]))
    cv_pct          = sigma_total / max(reserve_be, 1e-9) * 100.0

    # ── 4. Percentiles log-normale (QIS5 TP.5.26) ────────────────────────────
    pcts = percentiles_log_normale(reserve_be, sigma_total)

    # ── 5. Statut EIOPA (Guidelines TP) ──────────────────────────────────────
    if cv_pct < 10.0:
        statut = 'VERT'    # incertitude faible
    elif cv_pct < 20.0:
        statut = 'AMBRE'   # incertitude modérée
    else:
        statut = 'ROUGE'   # incertitude élevée — vigilance S2

    msg = (
        f"Mack (1993) : BE={reserve_be:,.0f}€ · "
        f"σ={sigma_total:,.0f}€ · CV={cv_pct:.1f}% · "
        f"P90={pcts['p90']:,.0f}€ · P99.5={pcts['p99_5']:,.0f}€ · "
        f"statut={statut}"
    )
    logger.info(msg)

    return {
        # Best Estimate
        'reserve_best_estimate':  round(reserve_be,    2),

        # Incertitude Mack
        'sigma_total':            round(sigma_total,   2),
        'var_totale':             round(var_tot,       4),
        'cv_pct':                 round(cv_pct,        2),

        # Détail par année
        'sigma_par_annee':        [round(float(s), 2) for s in sigma_par_annee],
        'var_par_annee':          [round(float(v), 4) for v in var_r],

        # Détail par colonne
        'sigma2_par_colonne':     [round(float(s), 6) for s in sigma2],

        # Percentiles log-normale (S2)
        'reserve_p50':            pcts['p50'],
        'reserve_p75':            pcts['p75'],
        'reserve_p90':            pcts['p90'],
        'reserve_p95':            pcts['p95'],
        'reserve_p99_5':          pcts['p99_5'],
        'mu_ln':                  pcts['mu_ln'],
        'sigma_ln':               pcts['sigma_ln'],

        # Métadonnées
        'statut':                 statut,
        'methode': (
            'Mack (1993) — ASTIN Bulletin 23(2) · '
            'Log-normale QIS5 TP.5.26'
        ),
        'message':                msg,
    }
