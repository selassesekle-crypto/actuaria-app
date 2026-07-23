# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n3/bootstrap_odp.py  —  Bootstrap ODP (Over-Dispersed Poisson)
# =============================================================================
#
#  Référence principale
#  --------------------
#  England, P.D. & Verrall, R.J. (2002).
#    "Stochastic Claims Reserving in General Insurance."
#    British Actuarial Journal, 8(3), pp. 443–544.
#    DOI: 10.1017/S1357321700003809
#
#  Référence complémentaire
#  ------------------------
#  England, P.D. (2002).
#    "Addendum to 'Analytic and bootstrap estimates of prediction errors
#     in claims reserving'."
#    Insurance: Mathematics and Economics, 31(3), pp. 461–466.
#
#  Mack, T. (1993) — pour la comparaison σ² vs Bootstrap.
#
#  Contexte réglementaire
#  ----------------------
#  EIOPA (2014), Guidelines on valuation of technical provisions.
#  QIS5 Technical Specifications (2010), TP.5.26.
#  Le Bootstrap ODP est l'une des méthodes stochastiques reconnues par
#  l'EIOPA pour la quantification de l'incertitude de réserve S2.
#
#  Correction v5.0 vs v4.0
#  ------------------------
#  En v4.0 : perturbation des facteurs individuels par colonne →
#    NON conforme England-Verrall 2002, sous-estime la variance en queue.
#
#  En v5.0 : résidus de Pearson sur le triangle complet →
#    CONFORME England-Verrall 2002, P99.5 fiables pour SCR.
#
#  Algorithme England-Verrall 2002
#  --------------------------------
#
#  Étape 1 — Fitted values (CL standard)
#  ───────────────────────────────────────
#  Pour chaque cellule (i,j) dans la zone connue (i+j < n) :
#
#      C_fit[i,j] = C[i,j-1] × f̂_j    pour j ≥ 1
#      C_fit[i,0] = C[i,0]              (première colonne = observée)
#
#  où f̂_j = facteur CL agrégé standard (volume-weighted).
#
#  Étape 2 — Résidus de Pearson
#  ─────────────────────────────
#  Les résidus de Pearson sont les résidus standardisés du modèle ODP :
#
#      r_ij = (C_obs[i,j] - C_fit[i,j]) / sqrt(C_fit[i,j])
#
#  Ces résidus ont variance ≈ φ (facteur de sur-dispersion) si H4 validée.
#
#  Ajustement des degrés de liberté (England-Verrall 2002, eq. 3.7) :
#
#      r_ij_adj = r_ij × sqrt(n_obs / (n_obs - n_params))
#
#  où  n_obs    = nombre de cellules dans la zone connue
#      n_params = n + (m-1)  (n interceptes + m-1 facteurs CL)
#
#  Étape 3 — Facteur de sur-dispersion φ
#  ───────────────────────────────────────
#
#      φ = Σ r²_ij / (n_obs - n_params)
#
#  φ > 1 indique une sur-dispersion par rapport au modèle Poisson pur.
#  Utilisé pour calibrer l'amplitude des simulations.
#
#  Étape 4 — Simulation Bootstrap (N itérations)
#  ───────────────────────────────────────────────
#  Pour chaque simulation b = 1..N :
#
#    a. Rééchantillonner les résidus ajustés avec remise :
#       r*_ij ~ Uniforme({r_ij_adj})
#
#    b. Reconstruire un pseudo-triangle :
#       C*[i,j] = C_fit[i,j] + r*_ij × sqrt(C_fit[i,j])
#       (annuler si C* < 0 → remplacer par C_fit)
#
#    c. Recalculer les facteurs CL sur le pseudo-triangle :
#       f*_j = Σ C*[i,j+1] / Σ C*[i,j]
#
#    d. Projeter la réserve avec f*_j + bruit process :
#       Pour chaque cellule future (i+j ≥ n) :
#         C_proj[i,j] ~ ODP(mean=C_proj[i,j-1] × f*_j, φ)
#       où ODP(mean, φ) ≈ Normal(mean, φ × mean)  [approximation]
#
#    e. Réserve simulée b :
#       R*_b = Σ_{i≥1} (C_proj[i,m-1] - C[i,k_i])
#
#  Étape 5 — Distribution et percentiles
#  ───────────────────────────────────────
#  Distribution empirique de {R*_1, ..., R*_N} :
#    BE_boot  = moyenne(R*_b)
#    σ_boot   = écart-type(R*_b)
#    P_α      = percentile α de {R*_b}
#
# =============================================================================

import logging
from typing import Dict, List, Optional

import numpy as np

from direction_non_vie.services.nv_triangle_negatifs import increments_positifs

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  FITTED VALUES ET RÉSIDUS DE PEARSON
# =============================================================================

def calculer_fitted_et_residus(
    C:        np.ndarray,
    facteurs: np.ndarray,
) -> tuple:
    """
    Calcule les fitted values CL et les résidus de Pearson ajustés.

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé. Zone connue : i+j < n.
    facteurs : np.ndarray  shape (m-1,)
        Facteurs CL agrégés (volume-weighted standard).

    Returns
    -------
    C_fit : np.ndarray  shape (n, m)
        Fitted values sur la zone connue. 0 hors zone.
    residus : np.ndarray  shape (n, m)
        Résidus de Pearson ajustés r_ij_adj sur la zone connue.
    phi : float
        Facteur de sur-dispersion φ.
    residus_list : list
        Liste plate des résidus non nuls (pour rééchantillonnage).
    n_obs : int
        Nombre de cellules dans la zone connue (j ≥ 1).
    n_params : int
        Nombre de paramètres du modèle CL.
    """
    n, m     = C.shape
    C_fit    = np.zeros((n, m))
    residus  = np.zeros((n, m))

    # ── Fitted values ─────────────────────────────────────────────────────────
    # C_fit[i,0] = C[i,0] (colonne 0 = paramètre libre, résidu = 0)
    # C_fit[i,j] = C[i,j-1] × f̂_j  pour j ≥ 1, dans la zone connue

    for i in range(n):
        C_fit[i, 0] = C[i, 0]    # colonne initiale = observée
        for j in range(1, m):
            if i + j < n:        # zone connue uniquement
                if j - 1 < len(facteurs) and C[i, j-1] > 0:
                    C_fit[i, j] = C[i, j-1] * facteurs[j-1]

    # ── Résidus de Pearson bruts ───────────────────────────────────────────────
    # r_ij = (C_obs[i,j] - C_fit[i,j]) / sqrt(C_fit[i,j])
    # Calculés pour j ≥ 1 uniquement (colonne 0 = paramètre libre)

    # ODP England-Verrall : résidu de Pearson sur l'INCRÉMENT. Dénominateur =
    # sqrt(m_ij), m_ij = C[i,j-1]×(f_j-1) = C_fit[i,j] - C[i,j-1] (incrément
    # ajusté). Le numérateur (C[i,j]-C_fit[i,j]) vaut déjà inc_obs - inc_fit.
    cellules  = []    # (i, j) des cellules incluses
    for i in range(n):
        for j in range(1, m):
            if i + j < n and C_fit[i, j] > 0 and C[i, j] > 0:
                m_ij = C_fit[i, j] - C[i, j - 1]        # incrément ajusté (fitted)
                if m_ij <= 0:
                    continue                            # incrément ≤ 0 → cellule exclue
                r = (C[i, j] - C_fit[i, j]) / np.sqrt(m_ij)
                residus[i, j] = r
                cellules.append((i, j))

    # ── Ajustement des degrés de liberté (England-Verrall 2002, eq. 3.7) ─────
    # n_obs    = cellules dans zone connue avec j ≥ 1
    # n_params = n (interceptes par année) + (m-1) (facteurs CL)
    # Facteur d'ajustement = sqrt(n_obs / (n_obs - n_params))

    n_obs    = len(cellules)
    n_params = n + (m - 1)
    df       = n_obs - n_params

    if df > 0:
        adj_factor = np.sqrt(n_obs / df)
        for (i, j) in cellules:
            residus[i, j] *= adj_factor
    else:
        adj_factor = 1.0
        logger.warning(
            f"Bootstrap ODP : degrés de liberté df={df} ≤ 0 "
            f"(n_obs={n_obs}, n_params={n_params}) — "
            f"ajustement désactivé. Triangle trop petit pour Bootstrap fiable."
        )

    # ── Facteur de sur-dispersion φ ───────────────────────────────────────────
    # φ = Σ r²_ij_brut / df  (avant ajustement)
    # Représente la sur-dispersion moyenne par cellule.

    # Résidus de Pearson bruts sur l'incrément (même dénominateur que ci-dessus) :
    # r_ij = (C_ij - C_fit_ij) / sqrt(m_ij),  m_ij = C_fit[i,j] - C[i,j-1].
    # φ = Σr²/df (England & Verrall 2002) — sert à scaler le bruit de processus.
    r_bruts = np.array([
        (C[i, j] - C_fit[i, j]) / np.sqrt(C_fit[i, j] - C[i, j - 1])
        for (i, j) in cellules
    ])
    phi = float(np.sum(r_bruts ** 2) / max(df, 1))

    # Liste plate des résidus ajustés pour rééchantillonnage
    residus_list = [
        residus[i, j] for (i, j) in cellules
        if residus[i, j] != 0
    ]

    return C_fit, residus, phi, residus_list, n_obs, n_params


# =============================================================================
#  BOOTSTRAP ODP — FONCTION PRINCIPALE
# =============================================================================

def bootstrap_odp(
    C:       np.ndarray,
    facteurs: np.ndarray,
    n_sim:   int = 1000,
    seed:    int = 42,
    annee_base: int = 1,
) -> Dict:
    """
    Bootstrap ODP conforme England & Verrall (2002).

    Quantifie l'incertitude de réserve par simulation stochastique.
    Inclut l'erreur de paramètre (via pseudo-triangles) ET l'erreur
    de processus (via bruit ODP sur les projections).

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé. n ≥ 3, m ≥ 3.
    facteurs : np.ndarray  shape (m-1,)
        Facteurs CL agrégés standard (volume-weighted).
        ⚠️ Toujours utiliser la variante 'standard' pour le Bootstrap,
        indépendamment de la variante CL retenue pour les ultimates.
    n_sim : int
        Nombre de simulations (défaut 1000, recommandé 5000 pour S2).
    seed : int
        Graine aléatoire pour la reproductibilité.
    annee_base : int
        Première année incluse dans la réserve (défaut = 1).

    Returns
    -------
    dict conforme standard ActuarIA.
    """
    np.random.seed(seed)
    n, m = C.shape

    # ── 1. Fitted values et résidus de Pearson ────────────────────────────────
    C_fit, residus, phi, res_list, n_obs, n_params = \
        calculer_fitted_et_residus(C, facteurs)

    if len(res_list) < 4:
        # Pas assez de résidus → Bootstrap non fiable
        logger.warning(
            f"Bootstrap ODP : seulement {len(res_list)} résidus disponibles. "
            f"Bootstrap non fiable sur ce triangle."
        )
        reserve_cl = _reserve_cl_simple(C, facteurs, annee_base)
        return _resultat_degrade(reserve_cl, n_sim)

    res_arr = np.array(res_list)

    # Dernière diagonale connue
    last_diag = np.array([
        float(C[i, min(n - i - 1, m - 1)]) for i in range(n)
    ])

    # ── 2. Réserve CL de référence ────────────────────────────────────────────
    reserve_ref = _reserve_cl_simple(C, facteurs, annee_base)

    # ── 3. Simulations Bootstrap ──────────────────────────────────────────────
    reserves_sim = np.zeros(n_sim)

    for b in range(n_sim):

        # ── 3a. Rééchantillonner les résidus avec remise ──────────────────────
        idx      = np.random.randint(0, len(res_arr), size=(n, m))
        res_boot = res_arr[idx]

        # ── 3b. Pseudo-triangle C* — perturber les INCRÉMENTS puis re-cumuler ──
        # E&V 2002 : inc* = m_fit + r*_ij × sqrt(m_fit), puis C*[i,j] = C*[i,j-1] + inc*.
        # m_fit = C[i,j-1]×(f_j-1) = C_fit[i,j] - C[i,j-1] (même incrément que les résidus).
        C_star = np.zeros((n, m))
        for i in range(n):
            C_star[i, 0] = max(C[i, 0], 1.0)   # colonne 0 = observée
            for j in range(1, m):
                if i + j < n and C_fit[i, j] > 0:
                    m_fit = C_fit[i, j] - C[i, j - 1]        # incrément ajusté (fitted)
                    if m_fit > 0:
                        inc_star = max(
                            m_fit + res_boot[i, j] * np.sqrt(m_fit),
                            m_fit * 0.01,               # garde-fou : incrément > 0
                        )
                    else:
                        inc_star = 0.0
                    C_star[i, j] = C_star[i, j - 1] + inc_star   # re-cumul

        # ── 3c. Facteurs CL sur le pseudo-triangle ────────────────────────────
        # f*_j = Σ C*[i,j+1] / Σ C*[i,j]  (volume-weighted)
        f_star = np.ones(m - 1)
        for j in range(m - 1):
            num = den = 0.0
            for i in range(n):
                if i + j + 1 < n and C_star[i, j] > 0 and C_star[i, j+1] > 0:
                    num += C_star[i, j+1]
                    den += C_star[i, j]
            f_star[j] = max(num / max(den, 1e-10), 1.0)

        # ── 3d. Projection avec bruit de processus sur l'INCRÉMENT ─────────────
        # E&V 2002 : l'incrément futur suit ODP(mean=inc_mean, φ) avec
        #   inc_mean = C_proj[i,j-1] × (f*_j - 1)   (l'incrément attendu, pas le cumulé)
        #   Var(inc) = φ × inc_mean  (approximation normale)
        #   C_proj[i,j] = C_proj[i,j-1] + inc_sim   (on AJOUTE l'incrément)

        reserve_b = 0.0
        for i in range(annee_base, n):
            k_i   = min(n - i - 1, m - 1)   # dernière colonne connue
            c_val = float(C[i, k_i])

            for j in range(k_i, m - 1):
                if j < len(f_star):
                    inc_mean = c_val * (f_star[j] - 1.0)   # incrément attendu
                    # Bruit de processus ODP sur l'incrément
                    if phi > 0 and inc_mean > 0:
                        std_proc = np.sqrt(phi * inc_mean)
                        inc_sim  = max(
                            inc_mean + np.random.normal(0, std_proc),
                            inc_mean * 0.01,
                        )
                    else:
                        inc_sim = max(inc_mean, 0.0)
                    c_val = c_val + inc_sim   # cumul += incrément simulé

            ibnr_b = max(c_val - last_diag[i], 0.0)
            reserve_b += ibnr_b

        reserves_sim[b] = reserve_b

    # ── 3e. Recentrage England-Verrall ────────────────────────────────────────
    # Le bootstrap estime la DISPERSION autour de l'estimateur analytique CL
    # (reserve_ref), non une moyenne biaisée par les troncatures (max(...,·×0.01)
    # et max(·-last_diag, 0)) sur triangles très volatils. On décale la
    # distribution pour que sa moyenne = reserve_ref — invariant en écart-type.
    biais        = float(np.mean(reserves_sim)) - reserve_ref
    reserves_sim = reserves_sim - biais

    # ── 4. Distribution et statistiques ──────────────────────────────────────
    be_boot  = float(np.mean(reserves_sim))
    std_boot = float(np.std(reserves_sim, ddof=1))
    cv_boot  = std_boot / max(be_boot, 1e-9)

    # Statut EIOPA (Guidelines TP)
    if cv_boot < 0.10:
        statut = 'VERT'    # CV < 10% — incertitude faible
    elif cv_boot < 0.20:
        statut = 'AMBRE'   # CV 10%-20% — incertitude modérée
    else:
        statut = 'ROUGE'   # CV > 20% — incertitude élevée

    msg = (
        f"Bootstrap ODP (E-V 2002) : "
        f"BE={be_boot:,.0f}€ · σ={std_boot:,.0f}€ · "
        f"CV={cv_boot*100:.1f}% · "
        f"P90={float(np.percentile(reserves_sim, 90)):,.0f}€ · "
        f"P99.5={float(np.percentile(reserves_sim, 99.5)):,.0f}€ · "
        f"φ={phi:.4f} · {n_sim} sim."
    )
    logger.info(msg)

    # Reporting partagé des incréments ≤ 0 (increments_positifs) — informationnel :
    # l'exclusion PROPRE de Bootstrap porte sur l'incrément FITTÉ (m_ij ≤ 0,
    # calculer_fitted_et_residus) et n'est PAS modifiée. On expose seulement le
    # comptage sur les incréments OBSERVÉS.
    ip_neg = increments_positifs(C, plancher=None)

    return {
        # Statistiques centrales
        'be_bootstrap':   round(be_boot,  2),
        'std_bootstrap':  round(std_boot, 2),
        'cv_bootstrap':   round(cv_boot,  4),

        # Percentiles (distribution empirique)
        'p50':            round(float(np.percentile(reserves_sim, 50)),   2),
        'p75':            round(float(np.percentile(reserves_sim, 75)),   2),
        'p90':            round(float(np.percentile(reserves_sim, 90)),   2),
        'p95':            round(float(np.percentile(reserves_sim, 95)),   2),
        'p99_5':          round(float(np.percentile(reserves_sim, 99.5)), 2),

        # Intervalle de confiance 95%
        'ic_95_inf':      round(float(np.percentile(reserves_sim, 2.5)),  2),
        'ic_95_sup':      round(float(np.percentile(reserves_sim, 97.5)), 2),

        # Paramètres Bootstrap
        'phi':            round(phi, 6),
        'n_obs':          n_obs,
        'n_params':       n_params,
        'df':             n_obs - n_params,
        'n_simulations':  n_sim,

        # Distribution complète (pour graphiques)
        'distribution':   reserves_sim.tolist(),

        # Métadonnées
        'statut':         statut,
        'methode':        'Bootstrap ODP — England & Verrall (2002)',
        'message':        msg,
        'increments_non_positifs': {
            'n_exclues':        ip_neg['n_exclues'],
            'cellules_exclues': ip_neg['cellules_exclues'],
            'frac_exclue':      ip_neg['frac_exclue'],
            'disponible':       ip_neg['disponible'],
        },
    }


# =============================================================================
#  UTILITAIRES INTERNES
# =============================================================================

def _reserve_cl_simple(
    C:          np.ndarray,
    facteurs:   np.ndarray,
    annee_base: int = 1,
) -> float:
    """Calcule la réserve CL simple (sans tail) pour référence Bootstrap."""
    n, m   = C.shape
    reserve = 0.0
    for i in range(annee_base, n):
        k_i = min(n - i - 1, m - 1)
        val = float(C[i, k_i])
        for j in range(k_i, m - 1):
            if j < len(facteurs):
                val *= facteurs[j]
        reserve += max(val - float(C[i, k_i]), 0.0)
    return reserve


def _resultat_degrade(reserve_ref: float, n_sim: int) -> Dict:
    """Retourne un résultat dégradé quand le Bootstrap n'est pas fiable."""
    return {
        'be_bootstrap':  round(reserve_ref, 2),
        'std_bootstrap': 0.0,
        'cv_bootstrap':  0.0,
        'p50': round(reserve_ref, 2), 'p75': round(reserve_ref, 2),
        'p90': round(reserve_ref, 2), 'p95': round(reserve_ref, 2),
        'p99_5': round(reserve_ref, 2),
        'ic_95_inf': round(reserve_ref, 2),
        'ic_95_sup': round(reserve_ref, 2),
        'phi': 0.0, 'n_obs': 0, 'n_params': 0, 'df': 0,
        'n_simulations': n_sim,
        'distribution': [reserve_ref] * n_sim,
        'statut': 'AMBRE',
        'methode': 'Bootstrap ODP — England & Verrall (2002)',
        'message': (
            "Bootstrap ODP : triangle trop petit — "
            "résidus insuffisants pour rééchantillonnage fiable."
        ),
    }
