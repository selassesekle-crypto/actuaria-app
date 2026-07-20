# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  clark.py  —  Méthode de Clark (2003) — LDF Curve-Fitting par MLE ODP
#
#  Implémentation fidèle à Clark (2003) :
#  · Modèle : Y_{i,j} ~ ODP avec μ_{i,j} = U_i × p_j(θ, β/ω)
#  · Courbes : log-logistique ET Weibull
#  · Estimation : MLE via scipy (BFGS) avec Hessienne approchée
#  · Sélection : AIC entre les deux courbes
#  · Tail factor : 1 / G(t_last)
#  · IC 95% sur les ultimates via matrice de covariance BFGS
#
#  Interface publique : clark_ldf(C, periodes, annee_base)
#  Retourne le dict standard A7 Ibrahim (compatible n4_best_estimate.py)
#
#  Auteur  : ActuarIA v5.0
#  Version : 2.0.0  (réécriture sur base Clark 2003)
# =============================================================================

from __future__ import annotations
import logging
import numpy as np

logger = logging.getLogger('actuaria.a7.clark')

try:
    from scipy.optimize import minimize
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False
    logger.warning('scipy absent — Clark LDF indisponible')

from typing import Dict, List, Optional, Tuple


# =============================================================================
#  CONSTANTES — SEUILS D'ABERRATION ET PARAMÈTRES
# =============================================================================
#  Regroupés ici pour faciliter la maintenance et l'audit.

# Tail factor au-delà duquel Clark est considéré aberrant
CLARK_TAIL_MAX          = 1.5

# G(t=2) en dessous duquel le MLE est mal conditionné
# (triangle trop peu développé à 2 ans — années récentes extrapolées)
CLARK_G_T2_MIN          = 0.10

# Minimum d'observations pour un MLE fiable : n_obs >= n + CLARK_DF_MIN
CLARK_DF_MIN            = 3

# Hessienne calculée uniquement si convergence propre (res.success)
# → évite un calcul O(n²) coûteux sur des solutions instables
CLARK_HESSIENNE_SI_CONVERGENCE = True



# =============================================================================
#  COURBES DE DÉVELOPPEMENT G(t)
# =============================================================================

def _g_loglogistique(t: np.ndarray, omega: float, theta: float) -> np.ndarray:
    """
    Courbe log-logistique (Clark 2003, eq. 3) :
    G(t) = t^ω / (t^ω + θ^ω)

    Parameters
    ----------
    t     : périodes de développement (positives)
    omega : paramètre de forme (> 0)
    theta : paramètre d'échelle / médiane (> 0)
    """
    t_safe = np.maximum(t, 1e-10)
    return t_safe**omega / (t_safe**omega + theta**omega)


def _g_weibull(t: np.ndarray, omega: float, theta: float) -> np.ndarray:
    """
    Courbe Weibull (Clark 2003, eq. 4) :
    G(t) = 1 - exp(-(t/θ)^ω)

    Parameters
    ----------
    t     : périodes de développement (positives)
    omega : paramètre de forme / β (> 0)
    theta : paramètre d'échelle (> 0)
    """
    t_safe = np.maximum(t, 1e-10)
    return 1.0 - np.exp(-(t_safe / theta) ** omega)


def _g(t: np.ndarray, omega: float, theta: float, courbe: str) -> np.ndarray:
    """Dispatch vers la courbe choisie."""
    if courbe == 'weibull':
        return _g_weibull(t, omega, theta)
    return _g_loglogistique(t, omega, theta)


def _increments(t: np.ndarray, omega: float, theta: float, courbe: str) -> np.ndarray:
    """
    Incréments de développement théoriques :
    p_j = G(t_j) - G(t_{j-1}), avec G(t_0) = 0
    """
    G = _g(t, omega, theta, courbe)
    G_prev = np.concatenate(([0.0], G[:-1]))
    return G - G_prev


# =============================================================================
#  LOG-VRAISEMBLANCE ODP
# =============================================================================

def _neg_loglik_odp(
    params:   np.ndarray,
    Y:        np.ndarray,       # triangle incrémental (n×m), NaN = cellule vide
    t:        np.ndarray,       # périodes de développement (m,)
    courbe:   str,
    mask:     np.ndarray,       # booléen (n×m) : True = cellule observée
) -> float:
    """
    Négatif de la log-vraisemblance ODP (Clark 2003, eq. 2) :

    ℓ = Σ_{i,j observés} [ Y_{i,j} · log(μ_{i,j}) - μ_{i,j} ]

    avec μ_{i,j} = U_i · p_j(ω, θ)

    params = [omega, theta, U_1, ..., U_n]
    """
    omega = params[0]
    theta = params[1]
    U     = params[2:]

    # Contraintes sur les paramètres
    if omega <= 0 or theta <= 0 or np.any(U <= 0):
        return 1e12

    n, m = Y.shape
    if len(U) != n:
        return 1e12

    # Incréments théoriques (communs à toutes les années)
    try:
        p = _increments(t, omega, theta, courbe)  # (m,)
    except Exception:
        return 1e12

    # Vérification : p doit être positif (croissant pour log-logistique,
    # en cloche pour Weibull — on vérifie juste la positivité stricte)
    if np.any(p <= 0):
        return 1e12
    # Vérification forme Weibull : p_j doit croître puis décroître (unimodal)
    # On rejette les solutions dégénérées où p est strictement croissant partout
    if courbe == 'weibull' and len(p) > 3:
        if np.all(np.diff(p) > 0):   # strictement croissant → dégénéré
            return 1e12

    # Construction de μ_{i,j} = U_i × p_j
    mu = np.outer(U, p)  # (n, m)

    # Log-vraisemblance sur les cellules observées
    Y_obs  = Y[mask]
    mu_obs = np.maximum(mu[mask], 1e-12)

    # Cellules avec Y=0 : Y·log(μ) = 0 par convention (limite de Poisson)
    ll = np.sum(np.where(Y_obs > 0, Y_obs * np.log(mu_obs), 0.0) - mu_obs)

    return -ll


# =============================================================================
#  ESTIMATION MLE
# =============================================================================

def _estimer_parametres(
    Y:           np.ndarray,
    t:           np.ndarray,
    mask:        np.ndarray,
    courbe:      str,
    n_multi:     int  = 4,
    calculer_ic: bool = True,
) -> Tuple[Optional[np.ndarray], float, bool, Optional[np.ndarray]]:
    """
    Estimation MLE par BFGS avec plusieurs points de départ.

    Returns
    -------
    params_hat : np.ndarray ou None si échec
    ll_opt     : float — log-vraisemblance optimale
    converge   : bool
    hess_inv   : np.ndarray ou None — matrice de covariance approchée
    """
    n, m = Y.shape

    # ── Initialisations multiples ─────────────────────────────────────────────
    # Stratégie 1 : somme des incréments observés × 1.1
    U_init_s1 = np.zeros(n)
    for i in range(n):
        row_valid = Y[i, mask[i]]
        U_init_s1[i] = max(float(np.sum(row_valid)) * 1.1, 1.0) if len(row_valid) > 0 else 1.0

    # Stratégie 2 : obs_last / G(t_last) — Copilot / Clark (2003) recommandé
    # Calcul de G(t_last_i) avec une courbe "rough" (paramètres médians de la grille)
    def _U_init_from_G(omega_0: float, theta_0: float) -> np.ndarray:
        U = np.zeros(n)
        for i in range(n):
            last_j = max(j for j in range(m) if mask[i, j]) if mask[i].any() else 0
            obs_last = float(np.nansum(Y[i, :last_j+1]))  # cumul reconstruit
            g_last = max(float(_g(t[last_j:last_j+1], omega_0, theta_0, courbe)[0]), 0.05)
            U[i] = max(obs_last / g_last, 1.0)
        return U

    best_ll     = -np.inf
    best_params = None
    best_hinv   = None
    converge    = False

    # Grille de points de départ pour omega et theta
    omega_starts = [0.5, 1.0, 2.0, 3.0][:n_multi]
    theta_starts = [t[m // 2], t[m // 3], t[-2], 2.0]

    bounds = [(1e-4, 10.0), (1e-2, t[-1] * 5.0)] + [(1.0, None)] * n

    for omega_0 in omega_starts:
        for theta_0 in theta_starts[:2]:
            # Tester les deux stratégies d'initialisation
            for U_init_base in [_U_init_from_G(omega_0, theta_0), U_init_s1]:
                # Multi-start sur U_i : ×0.9, ×1.0, ×1.1
                for u_scale in [0.9, 1.0, 1.1]:
                    U_init = np.maximum(U_init_base * u_scale, 1.0)
                    x0 = np.concatenate(([omega_0, theta_0], U_init))

                    try:
                        res = minimize(
                            fun     = _neg_loglik_odp,
                            x0      = x0,
                            args    = (Y, t, courbe, mask),
                            method  = 'L-BFGS-B',
                            bounds  = bounds,
                            options = {'maxiter': 5000, 'ftol': 1e-12, 'gtol': 1e-8},
                        )
                        if res.success or res.fun < 1e11:
                            ll_cur = -float(res.fun)
                            if ll_cur > best_ll:
                                best_ll     = ll_cur
                                best_params = res.x.copy()
                                converge    = res.success
                                # Hessienne numérique — seulement si demandée ET convergence propre
                                # (O(n³) évaluations de LL — coûteux sur 30×30)
                                if calculer_ic and converge:
                                  try:
                                    from scipy.optimize import approx_fprime
                                    p_opt = best_params
                                    n_p   = len(p_opt)
                                    eps_h = 1e-4 * np.maximum(np.abs(p_opt), 1.0)
                                    H_num = np.zeros((n_p, n_p))
                                    for ki in range(n_p):
                                        e_ki = np.zeros(n_p); e_ki[ki] = eps_h[ki]
                                        g_plus  = approx_fprime(p_opt + e_ki, _neg_loglik_odp,
                                                                 eps_h * 1e-2, Y, t, courbe, mask)
                                        g_minus = approx_fprime(p_opt - e_ki, _neg_loglik_odp,
                                                                 eps_h * 1e-2, Y, t, courbe, mask)
                                        H_num[ki] = (g_plus - g_minus) / (2.0 * eps_h[ki])
                                    # Symétriser et inverser
                                    H_sym = 0.5 * (H_num + H_num.T)
                                    # Régularisation si mal conditionné
                                    eigvals = np.linalg.eigvalsh(H_sym)
                                    if np.min(eigvals) <= 0:
                                        H_sym += np.eye(n_p) * max(-np.min(eigvals) + 1e-6, 1e-6)
                                    best_hinv = np.linalg.inv(H_sym)
                                    # Vérifier que les variances sont positives
                                    if np.any(np.diag(best_hinv) < 0):
                                        best_hinv = None
                                  except Exception:
                                    best_hinv = None
                    except Exception as e:
                        logger.debug(f'Clark optim ({courbe}, ω={omega_0:.1f}, θ={theta_0:.1f}) : {e}')
                        continue

    return best_params, best_ll, converge, best_hinv


# =============================================================================
#  CALCUL DES RÉSULTATS ACTUARIELS
# =============================================================================

def _calculer_resultats(
    C:       np.ndarray,    # triangle cumulé original (n×m)
    Y:       np.ndarray,    # triangle incrémental (n×m)
    t:       np.ndarray,    # périodes (m,)
    params:  np.ndarray,    # [omega, theta, U_1..U_n]
    courbe:  str,
    hess_inv: Optional[np.ndarray],
    annee_base: int,
) -> Dict:
    """
    Calcule ultimates, IBNR, tail factor, IC 95% et statistiques.
    """
    n, m = C.shape
    omega = float(params[0])
    theta = float(params[1])
    U     = params[2:]

    # Courbe G(t) aux périodes observées
    G = _g(t, omega, theta, courbe)           # (m,)
    p = _increments(t, omega, theta, courbe)  # (m,)

    # ── Tail factor ───────────────────────────────────────────────────────────
    # G(∞) = 1 pour les deux courbes → tail = 1 / G(t_last)
    tail_factor = float(1.0 / max(G[-1], 1e-10))

    # ── Ultimates et IBNR ─────────────────────────────────────────────────────
    ultimates            = []
    ibnr_par_annee       = []
    ibnr_brut_par_annee  = []  # IBNR avant troncature — signal sur-développement
    pct_developpe        = []

    for i in range(n):
        u_i = float(U[i])

        # Dernier cumul observé pour cette année
        row = C[i]
        last_j = max(j for j in range(m) if not np.isnan(row[j]) and row[j] > 0)
        obs_last = float(row[last_j])

        # % développé = G(t_{last_j}) pour cette année
        pct = float(G[last_j]) * 100.0

        # U_i (paramètre MLE) EST déjà l'ultime à l'infini : à l'optimum,
        # U_i = obs_i / G(t_last_i) et G(∞) = 1. Le développement au-delà de la
        # dernière colonne (le "tail") est donc DÉJÀ contenu dans U_i.
        # IBNR_i = U_i - dernière observation cumulée. NE PAS multiplier par
        # tail_factor (qui reste calculé pour l'affichage/diagnostic) : cela
        # compterait le tail une seconde fois.
        ibnr_i      = u_i - obs_last
        ibnr_brut_i = ibnr_i  # valeur brute avant troncature à 0

        ultimates.append(u_i)
        ibnr_par_annee.append(max(ibnr_i, 0.0))  # tronqué : provision ≥ 0
        ibnr_brut_par_annee.append(round(ibnr_brut_i, 0))  # brut : signal sur-développement
        pct_developpe.append(pct)

    # Sur-développement : années où IBNR brut < 0 → ultimate Clark < cumul observé
    n_sur_dev = sum(1 for v in ibnr_brut_par_annee if v < 0)

    # Réserve totale depuis annee_base — aligné sur CL/Mack/BF/CC (exclut l'année 0)
    reserve_totale = float(np.sum(ibnr_par_annee[annee_base:]))

    # ── Intervalles de confiance 95% sur les ultimates ────────────────────────
    ic_95 = []
    if hess_inv is not None:
        try:
            var_params = np.diag(hess_inv)
            se_U = np.sqrt(np.maximum(var_params[2:], 0.0))
            z95  = 1.96
            for i in range(n):
                se_ult = se_U[i] * tail_factor
                ic_95.append((
                    round(max(ultimates[i] - z95 * se_ult, 0), 0),
                    round(ultimates[i] + z95 * se_ult, 0),
                ))
        except Exception:
            ic_95 = [(None, None)] * n
    else:
        ic_95 = [(None, None)] * n

    # ── Résidus de Pearson (qualité d'ajustement) ─────────────────────────────
    mu = np.outer(U, p)  # (n, m)
    residus_list = []
    for i in range(n):
        for j in range(m):
            if not np.isnan(Y[i, j]) and mu[i, j] > 0:
                r = (Y[i, j] - mu[i, j]) / np.sqrt(mu[i, j])
                residus_list.append(r)

    residus_arr = np.array(residus_list)
    residus_stats = {
        'n':          len(residus_arr),
        'mean':       round(float(np.mean(residus_arr)), 4),
        'std':        round(float(np.std(residus_arr)), 4),
        'min':        round(float(np.min(residus_arr)), 4),
        'max':        round(float(np.max(residus_arr)), 4),
        'chi2_stat':  round(float(np.sum(residus_arr**2)), 4),
    }

    return {
        'omega':           round(omega, 4),
        'theta':           round(theta, 2),
        'U':               [round(float(u), 0) for u in U],
        'ultimates':       [round(u, 0) for u in ultimates],
        'ibnr_par_annee':        [round(v, 0) for v in ibnr_par_annee],
        'ibnr_brut_par_annee':   ibnr_brut_par_annee,  # brut < 0 si sur-développement
        'n_sur_developpement':   n_sur_dev,
        'reserve_totale':  round(reserve_totale, 0),
        'tail_factor':     round(tail_factor, 6),
        'pct_developpe':   [round(p, 1) for p in pct_developpe],
        'ic_95':           ic_95,
        'residus':         residus_stats,
    }


# =============================================================================
#  AIC
# =============================================================================

def _aic(ll: float, n_params: int) -> float:
    """AIC = 2k - 2ℓ (Clark 2003)."""
    return 2.0 * n_params - 2.0 * ll


# =============================================================================
#  INTERFACE PUBLIQUE
# =============================================================================

def clark_ldf(
    C:              np.ndarray,
    periodes:       Optional[List[float]] = None,
    courbes:        List[str]             = ['loglogistique', 'weibull'],
    annee_base:     int                   = 1,
    calculer_ic:    bool                  = True,
    g_t2_min:       Optional[float]       = None,
) -> Dict:
    """
    Paramètres supplémentaires
    --------------------------
    calculer_ic : bool
        Si True (défaut), calcule la Hessienne numérique et les IC 95%
        sur les ultimates. Coûteux sur grands triangles (O(n³)) —
        mettre à False si seule la réserve centrale est nécessaire.
    g_t2_min : float, optional
        Seuil G(t=2) en dessous duquel Clark est déclaré aberrant.
        Par défaut : CLARK_G_T2_MIN (0.10). À ajuster par LoB :
        RC Médicale / Construction → 0.03, RC Générale → 0.05.
    """
    """
    Méthode de Clark (2003) — LDF Curve-Fitting par Maximum de Vraisemblance.

    Parameters
    ----------
    C : np.ndarray
        Triangle des paiements CUMULÉS (n × m), zone connue i+j < n.
        Cas supportés : n=m (carré), n>m (court), n<m (long, rare).
    periodes : list[float], optional
        Périodes de développement en mois. Défaut : [12, 24, 36, ...].
    courbes : list[str]
        Courbes à tester : 'loglogistique' et/ou 'weibull'.
    annee_base : int
        Première année incluse dans la réserve totale.

    Returns
    -------
    Dict standard A7 Ibrahim avec les clés :
        success, disponible, aberrant, courbe_choisie, omega, theta,
        ultimates, ibnr_par_annee, reserve_totale, reserve_be_clark,
        ibnr_brut_par_annee  — IBNR avant troncature à 0 (< 0 = sur-développement)
        n_sur_developpement  — nombre d'années où ultimate Clark < cumul observé
        tail_factor, pct_developpe, ic_95, aic_loglogistique, aic_weibull,
        ll_loglogistique, ll_weibull, residus, converge, message, erreur,
        aic_optimal, g_courbe, periodes_arr
    """
    # ── Vérifications préliminaires ───────────────────────────────────────────
    if not SCIPY_OK:
        return {
            'success': False, 'disponible': False,
            'erreur':  'scipy non disponible',
            'message': 'Méthode de Clark non disponible.',
        }

    if C is None or C.ndim != 2:
        return {
            'success': False, 'disponible': False,
            'erreur':  'Triangle invalide',
            'message': 'Triangle invalide.',
        }

    n, m = C.shape

    # Minimum 4×4 pour avoir des degrés de liberté suffisants
    if n < 4 or m < 4:
        return {
            'success': False, 'disponible': False,
            'erreur':  f'Triangle trop petit ({n}×{m}). Minimum 4×4.',
            'message': 'Triangle insuffisant pour Clark.',
        }

    # ── Périodes de développement ─────────────────────────────────────────────
    if periodes is None:
        # Périodes en années (1, 2, 3, ..., m)
        # Convention Clark : t_j = âge de développement en années
        # θ s'interprète donc en années (ex: θ=5 → médiane à 5 ans)
        t = np.array([(j + 1.0) for j in range(m)], dtype=float)
    else:
        t = np.array(periodes, dtype=float)
        if len(t) != m:
            logger.warning(f'Clark : len(periodes)={len(t)} != m={m} — périodes ignorées, fallback [1..m]')
            t = np.array([(j + 1.0) for j in range(m)], dtype=float)
        elif np.any(np.diff(t) <= 0):
            return {
                'success': False, 'disponible': False,
                'erreur':  'Périodes non strictement croissantes.',
                'message': 'Clark invalide : les périodes t doivent être strictement croissantes.',
            }
        elif np.any(t <= 0):
            return {
                'success': False, 'disponible': False,
                'erreur':  'Périodes négatives ou nulles.',
                'message': 'Clark invalide : les périodes t doivent être strictement positives.',
            }

    # ── Triangle incrémental ──────────────────────────────────────────────────
    C_float = C.astype(float).copy()

    # Mettre NaN là où le triangle est vide (cellules au-delà de la diagonale)
    for i in range(n):
        for j in range(m):
            if j > m - 1 - i:
                C_float[i, j] = np.nan

    # Pas de normalisation — la LL ODP n'est pas invariante à l'échelle
    # (Copilot AI / Clark 2003 : travailler sur les données brutes)
    scale = 1.0  # conservé pour compatibilité rescaling U_i
    C_norm = C_float

    Y_norm = np.full_like(C_norm, np.nan)
    Y_norm[:, 0] = C_norm[:, 0]
    for j in range(1, m):
        Y_norm[:, j] = C_norm[:, j] - C_norm[:, j - 1]

    Y = Y_norm

    # Vérification monotonicité : C[i,j] doit être croissant en j
    # (incréments négatifs = annulations/corrections — Clark invalide)
    _n_neg = int(np.sum(Y_norm[~np.isnan(Y_norm)] < 0))
    if _n_neg > 0:
        logger.warning(
            f'Clark : {_n_neg} incrément(s) négatif(s) détecté(s) — '
            f'triangle non-monotone. Cellules ignorées dans le MLE.'
        )

    # Masque : cellules effectivement observées (non NaN et non négatif)
    # Les incréments négatifs sont exclus — ils violent H1 de Clark (2003)
    mask = ~np.isnan(Y) & ~np.isnan(C_norm) & (Y >= 0)

    n_obs = int(mask.sum())
    if n_obs < (n + CLARK_DF_MIN):  # besoin d'au moins n+CLARK_DF_MIN observations
        return {
            'success': False, 'disponible': False,
            'erreur':  f'Observations insuffisantes ({n_obs}) pour {n} années.',
            'message': 'Données insuffisantes pour Clark.',
        }

    # ── Estimation MLE pour chaque courbe ────────────────────────────────────
    # Seed fixe pour reproductibilité des résultats entre deux appels identiques.
    # Impact : les perturbations aléatoires de U_init (×0.9/1.0/1.1) sont
    # déterministes. Ne pas modifier sans adapter les tests de non-régression.
    np.random.seed(42)

    resultats_courbes = {}
    ll_par_courbe     = {}
    aic_par_courbe    = {}
    n_params          = n + 2  # n ELR + ω + θ

    for courbe in courbes:
        logger.info(f'Clark MLE — courbe={courbe}, n={n}, m={m}')
        try:
            params, ll, conv, hinv = _estimer_parametres(Y, t, mask, courbe, calculer_ic=calculer_ic)
            if params is None or ll == -np.inf:
                logger.warning(f'Clark {courbe} : optimisation échouée')
                ll_par_courbe[courbe]  = None
                aic_par_courbe[courbe] = None
                continue

            aic = _aic(ll, n_params)
            # Rescaler les U_i vers les valeurs originales
            params_rescaled      = params.copy()
            params_rescaled[2:] *= scale
            res = _calculer_resultats(C_float, Y_norm, t, params_rescaled, courbe, hinv, annee_base)
            res['converge'] = conv
            res['ll']       = round(ll, 2)
            res['aic']      = round(aic, 2)

            resultats_courbes[courbe] = res
            ll_par_courbe[courbe]     = ll
            aic_par_courbe[courbe]    = aic
            logger.info(f'Clark {courbe} : LL={ll:.2f}, AIC={aic:.2f}, '
                        f'réserve={res["reserve_totale"]:,.0f}€')

        except Exception as e:
            logger.error(f'Clark {courbe} : erreur — {e}', exc_info=True)
            ll_par_courbe[courbe]  = None
            aic_par_courbe[courbe] = None

    # ── Sélection de la courbe ────────────────────────────────────────────────
    # Clark (2003) recommande Weibull comme courbe de référence sur triangles
    # annuels réguliers. La log-logistique est plus flexible mais extrapole
    # agressivement la queue → résultats aberrants sur triangles longs.
    # Règle : Weibull en priorité si convergé et tail raisonnable (< 1.5)
    #         Log-logistique si Weibull échoue ou tail > 1.5
    courbes_ok = {c: aic for c, aic in aic_par_courbe.items() if aic is not None}

    if not courbes_ok:
        return {
            'success': False, 'disponible': True,
            'erreur':  'Optimisation Clark échouée pour toutes les courbes.',
            'message': 'Clark non convergé — résultats indisponibles.',
        }

    # Priorité à Weibull si tail raisonnable
    wb_ok = ('weibull' in resultats_courbes
             and float(resultats_courbes['weibull'].get('tail_factor', 99)) < 1.5)
    if wb_ok:
        courbe_choisie = 'weibull'
    else:
        # Fallback : meilleur AIC parmi les courbes disponibles
        courbe_choisie = min(courbes_ok, key=courbes_ok.get)
    best = resultats_courbes[courbe_choisie]

    aic_ll = aic_par_courbe.get('loglogistique')
    aic_wb = aic_par_courbe.get('weibull')
    ll_ll  = ll_par_courbe.get('loglogistique')
    ll_wb  = ll_par_courbe.get('weibull')

    reserve_totale = float(best['reserve_totale'])
    tail_factor    = float(best['tail_factor'])

    # ── Validation de cohérence ───────────────────────────────────────────────
    # Calculer la somme des dernières diagonales comme référence
    # (last_diag_sum supprimé — critère 5×diagonale retiré au profit
    #  des critères actuariels : tail, G(t2), convergence)

    # ── Critères d'aberration actuariellement justifiés ──────────────────
    # 1. Tail factor > 1.5 : queue irréaliste quelle que soit la LoB
    # 2. G(t_min) < 3% : triangle trop peu développé à la 1ère période
    #    → MLE mal conditionné, ultimates extrapolés massivement
    # 3. Non-convergence : le MLE n'a pas trouvé de minimum stable
    # NB : AIC absolu non utilisé (dépend de l'échelle des données)
    # NB : ratio Clark/CL non utilisé (circulaire)
    _omega_best  = float(best.get('omega', 1.0))
    _theta_best  = float(best.get('theta', 1.0))
    _g_t2_min    = g_t2_min if g_t2_min is not None else CLARK_G_T2_MIN
    # G(t=1) et G(t=2) pour évaluer le conditionnement du MLE
    # Seuil G(t=2) < 10% plus robuste que G(t=1) < 3% :
    # - G(t=1) < 3% peut être normal sur triangles longs (20×20+)
    # - G(t=2) < 10% signifie que même à 2 ans, le triangle est très peu
    #   développé → MLE mal conditionné sur les années récentes
    G_at_t1 = float(_g(np.array([t[0]]), _omega_best, _theta_best, courbe_choisie)[0])
    G_at_t2 = float(_g(np.array([t[min(1, m-1)]]), _omega_best, _theta_best, courbe_choisie)[0])
    clark_aberrant = (
        tail_factor > CLARK_TAIL_MAX         # queue irréaliste quelle que soit la LoB
        or G_at_t2 < _g_t2_min               # MLE mal conditionné (< _g_t2_min à t=2)
        or not best.get('converge', True)    # MLE non convergé
    )

    # ── Message actuariel ─────────────────────────────────────────────────────
    # ΔAIC entre les deux courbes (comparaison relative — pas en absolu)
    _delta_aic = None
    if aic_ll is not None and aic_wb is not None:
        _delta_aic = round(aic_ll - aic_wb, 1)  # négatif si log-log meilleure

    if clark_aberrant:
        _raison = []
        if tail_factor > CLARK_TAIL_MAX:
            _raison.append(f'tail factor = {tail_factor:.3f} (> {CLARK_TAIL_MAX} — queue irréaliste)')
        if G_at_t2 < 0.10:
            _raison.append(f'G(t=2) = {G_at_t2:.3f} (< {_g_t2_min:.0%} — MLE mal conditionné sur années récentes)')
        if not best.get('converge', True):
            _raison.append('MLE non convergé')
        message = (
            f"⚠️ Clark {courbe_choisie} écarté — "
            f"{' ; '.join(_raison)}. "
            f"Méthode non retenue dans la pondération."
        )
    elif tail_factor > 1.20:
        message = (
            f"Clark {courbe_choisie} sélectionné. "
            f"Queue notable : tail = {tail_factor:.3f}. "
            f"Résultat à titre informatif — vérifier le développement tardif."
        )
    else:
        message = (
            f"Clark {courbe_choisie} sélectionné. "
            f"Tail factor = {tail_factor:.4f}. "
            + (f"\u0394AIC Weibull vs Log-log = {_delta_aic:+.0f}. " if _delta_aic else '')
            + "Ajustement satisfaisant."
        )

    # ── Courbe G(t) pour graphique ────────────────────────────────────────────
    t_dense = np.linspace(0, t[-1] * 1.5, 100)
    g_courbe = _g(t_dense, float(best['omega']), float(best['theta']), courbe_choisie)

    return {
        'success':           True,
        'disponible':        True,
        'aberrant':          clark_aberrant,

        # Modèle sélectionné
        'courbe_choisie':    courbe_choisie,
        'omega':             best['omega'],
        'theta':             best['theta'],
        'elr':               best['U'],  # alias ELR = U_i (ultimates paramétriques)

        # Résultats actuariels
        'ultimates':         best['ultimates'],
        'ibnr_par_annee':    best['ibnr_par_annee'],
        'reserve_totale':    reserve_totale,
        'reserve_be_clark':  reserve_totale,  # alias
        'tail_factor':       tail_factor,
        'pct_developpe':     best['pct_developpe'],
        'ic_95':             best['ic_95'],

        # Comparaison des courbes
        'aic_loglogistique': round(aic_ll, 2) if aic_ll is not None else None,
        'aic_weibull':       round(aic_wb, 2) if aic_wb is not None else None,
        'll_loglogistique':  round(ll_ll, 2)  if ll_ll  is not None else None,
        'll_weibull':        round(ll_wb, 2)  if ll_wb  is not None else None,
        'aic_optimal':       round(courbes_ok[courbe_choisie], 2),
        'll_optimal':        round(best['ll'], 2),

        # Qualité d'ajustement
        'residus':           best['residus'],
        'converge':          best['converge'],

        # Courbe G(t) pour graphique
        'periodes_arr':      t_dense.tolist(),
        'g_courbe':          [round(float(v), 4) for v in g_courbe],

        # Métadonnées
        'n_params':          n_params,
        'n_obs':             n_obs,
        'message':           message,
        'erreur':            None,
    }
