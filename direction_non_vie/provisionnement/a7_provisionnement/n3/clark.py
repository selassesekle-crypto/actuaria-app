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

    # Vérification : p doit être positif
    if np.any(p <= 0):
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
    Y:       np.ndarray,
    t:       np.ndarray,
    mask:    np.ndarray,
    courbe:  str,
    n_multi: int = 4,
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
    # U_i : dernière valeur cumulée observée par année (proxy robust)
    U_init_base = np.zeros(n)
    for i in range(n):
        row_valid = Y[i, mask[i]]
        if len(row_valid) > 0:
            # Pour les ultimates : somme des incréments observés × 1.1
            U_init_base[i] = max(float(np.sum(Y[i, mask[i]])) * 1.1, 1.0)
        else:
            U_init_base[i] = 1.0

    best_ll     = -np.inf
    best_params = None
    best_hinv   = None
    converge    = False

    # Grille de points de départ pour omega et theta
    omega_starts = [0.5, 1.0, 2.0, 3.0][:n_multi]
    theta_starts = [t[m // 2], t[m // 3], t[-2]]  # médiane, 1/3, avant-dernier

    bounds = [(1e-4, 20.0), (1e-2, t[-1] * 3.0)] + [(1.0, None)] * n

    for omega_0 in omega_starts:
        for theta_0 in theta_starts[:2]:
            # Varier légèrement U_init
            U_init = U_init_base * np.random.uniform(0.9, 1.1, n)
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
                        # Hessienne via BFGS (nécessite method='BFGS')
                        try:
                            res2 = minimize(
                                fun    = _neg_loglik_odp,
                                x0     = best_params,
                                args   = (Y, t, courbe, mask),
                                method = 'BFGS',
                                options = {'maxiter': 1000},
                            )
                            if hasattr(res2, 'hess_inv'):
                                best_hinv = np.array(res2.hess_inv)
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
    ultimates      = []
    ibnr_par_annee = []
    pct_developpe  = []

    for i in range(n):
        u_i = float(U[i])

        # Dernier cumul observé pour cette année
        row = C[i]
        last_j = max(j for j in range(m) if not np.isnan(row[j]) and row[j] > 0)
        obs_last = float(row[last_j])

        # % développé = G(t_{last_j}) pour cette année
        pct = float(G[last_j]) * 100.0

        # IBNR = U_i × (1 - G(t_{last_j})) × tail
        # En fait : IBNR = U_i × tail - obs_last
        # Clark : U_i = ultimate sans queue, donc IBNR = U_i / G(t_last) - obs
        # Mais ici U_i est l'ultimate direct (G va vers 1)
        ibnr_i = u_i * tail_factor - obs_last

        ultimates.append(u_i * tail_factor)
        ibnr_par_annee.append(max(ibnr_i, 0.0))
        pct_developpe.append(pct)

    # Réserve totale depuis annee_base
    reserve_totale = float(np.sum(ibnr_par_annee[annee_base - 1:]))

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
        'ibnr_par_annee':  [round(v, 0) for v in ibnr_par_annee],
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
    C:          np.ndarray,
    periodes:   Optional[List[float]] = None,
    courbes:    List[str]             = ['loglogistique', 'weibull'],
    annee_base: int                   = 1,
) -> Dict:
    """
    Méthode de Clark (2003) — LDF Curve-Fitting par Maximum de Vraisemblance.

    Parameters
    ----------
    C : np.ndarray
        Triangle des paiements CUMULÉS (n × n), triangulaire supérieur.
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
        t = np.array([(j + 1) * 12.0 for j in range(m)])
    else:
        t = np.array(periodes, dtype=float)
        if len(t) != m:
            t = np.array([(j + 1) * 12.0 for j in range(m)])

    # ── Triangle incrémental ──────────────────────────────────────────────────
    C_float = C.astype(float).copy()

    # Mettre NaN là où le triangle est vide (cellules au-delà de la diagonale)
    for i in range(n):
        for j in range(m):
            if j > m - 1 - i:
                C_float[i, j] = np.nan

    # Normaliser par la médiane des valeurs positives pour stabiliser la LL ODP
    # (la LL ODP n'est pas invariante à l'échelle des données)
    vals_pos = C_float[~np.isnan(C_float) & (C_float > 0)]
    scale = float(np.median(vals_pos)) if len(vals_pos) > 0 else 1.0
    scale = max(scale, 1.0)
    C_norm = C_float / scale

    Y_norm = np.full_like(C_norm, np.nan)
    Y_norm[:, 0] = C_norm[:, 0]
    for j in range(1, m):
        Y_norm[:, j] = C_norm[:, j] - C_norm[:, j - 1]

    # Alias pour le reste du code (on travaille en normalisé)
    Y = Y_norm

    # Masque : cellules effectivement observées (non NaN et non négatif)
    mask = ~np.isnan(Y) & ~np.isnan(C_norm) & (Y >= 0)

    n_obs = int(mask.sum())
    if n_obs < (n + 3):  # besoin d'au moins n+2 observations (n ELR + ω + θ)
        return {
            'success': False, 'disponible': False,
            'erreur':  f'Observations insuffisantes ({n_obs}) pour {n} années.',
            'message': 'Données insuffisantes pour Clark.',
        }

    # ── Estimation MLE pour chaque courbe ────────────────────────────────────
    np.random.seed(42)  # Reproductibilité

    resultats_courbes = {}
    ll_par_courbe     = {}
    aic_par_courbe    = {}
    n_params          = n + 2  # n ELR + ω + θ

    for courbe in courbes:
        logger.info(f'Clark MLE — courbe={courbe}, n={n}, m={m}')
        try:
            params, ll, conv, hinv = _estimer_parametres(Y, t, mask, courbe)
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

    # ── Sélection par AIC (plus bas = meilleur) ───────────────────────────────
    courbes_ok = {c: aic for c, aic in aic_par_courbe.items() if aic is not None}

    if not courbes_ok:
        return {
            'success': False, 'disponible': True,
            'erreur':  'Optimisation Clark échouée pour toutes les courbes.',
            'message': 'Clark non convergé — résultats indisponibles.',
        }

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
    last_diag = []
    for i in range(n):
        j_last = m - 1 - i
        if j_last >= 0 and not np.isnan(C_float[i, j_last]) and C_float[i, j_last] > 0:
            last_diag.append(float(C_float[i, j_last]))
    last_diag_sum = sum(last_diag) if last_diag else 0.0

    # Aberrant si :
    # - réserve > 5× la diagonale (seuil large pour ne pas exclure à tort)
    # - ou AIC > 1e6 (ajustement complètement dégradé)
    clark_aberrant = (
        (last_diag_sum > 0 and reserve_totale > 5.0 * last_diag_sum) or
        (courbes_ok[courbe_choisie] > 1e6)
    )

    # ── Message actuariel ─────────────────────────────────────────────────────
    if clark_aberrant:
        message = (
            f"⚠️ RÉSULTAT ABERRANT — réserve Clark ({reserve_totale:,.0f}\u202f€) "
            f"incohérente avec les données (seuil : 5× diagonale = "
            f"{5*last_diag_sum:,.0f}\u202f€). "
            f"Méthode écartée de la pondération."
        )
    elif tail_factor > 1.20:
        message = (
            f"Courbe {courbe_choisie} sélectionnée (AIC={courbes_ok[courbe_choisie]:.1f}). "
            f"Queue significative : {tail_factor:.3f}× — attention aux développements tardifs."
        )
    else:
        message = (
            f"Courbe {courbe_choisie} sélectionnée (AIC={courbes_ok[courbe_choisie]:.1f}). "
            f"Tail factor : {tail_factor:.4f}. Ajustement satisfaisant."
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
