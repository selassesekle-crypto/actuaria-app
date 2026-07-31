# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  clark.py  —  Méthode de Clark (2003) — LDF Curve-Fitting par MLE ODP
#
#  Implémentation fidèle à Clark (2003) :
#  · Modèle : Y_{i,j} ~ ODP avec μ_{i,j} = U_i × p_j(ω, θ)
#  · Courbes : log-logistique ET Weibull
#  · Estimation : MLE via scipy (L-BFGS-B) avec Hessienne numérique
#  · Sélection : Weibull PRIORITAIRE si sa queue est raisonnable, AIC en repli
#  · Tail factor : 1 / G(t_last)
#  · IC 95% : variance de PARAMÈTRE (σ²·H⁻¹) + variance de PROCESSUS (σ²·R)
#
#  ⚠️ LA SÉLECTION N'EST PAS FAITE PAR L'AIC, malgré ce que l'AIC laisse
#  attendre. La log-logistique gagne presque toujours en vraisemblance (elle a
#  une queue plus lourde, donc plus de liberté pour absorber les derniers
#  points), mais elle extrapole agressivement au-delà de la dernière colonne
#  observée — précisément là où l'on n'a aucune donnée pour la contredire.
#  Weibull est donc retenue par défaut, l'AIC ne servant que de repli quand
#  Weibull échoue ou produit une queue > CLARK_TAIL_MAX. Les deux AIC restent
#  publiés pour que l'écart soit visible et contestable.
#
#  ⚠️ CLARK NE SAIT PAS REPRÉSENTER UN RECOURS. G(t) est monotone croissante
#  par construction : aucun jeu de paramètres ne peut faire redescendre le
#  cumulé. Sur un triangle où les encaissements de recours font passer un
#  facteur de développement sous 1, l'ajustement produit une réserve gonflée
#  sans le signaler. Ce module DÉCLARE donc cette incompatibilité et retient
#  sa réserve (cf. `structure_monotone`) plutôt que de publier un chiffre que
#  rien dans la sortie ne permettrait de mettre en doute.
#
#  Interface publique : clark_ldf(C, periodes, annee_base)
#  Retourne le dict standard A7 Ibrahim (compatible n4_best_estimate.py)
#
#  Auteur  : ActuarIA v5.0
#  Version : 2.1.0  (IC complet + verdict de structure)
# =============================================================================

from __future__ import annotations
import logging
import numpy as np

from direction_non_vie.services.nv_triangle_negatifs import increments_positifs
from .chain_ladder import calculer_facteurs

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

# Tail factor au-delà duquel la queue est signalée sans écarter la méthode
CLARK_TAIL_ALERTE       = 1.20

# Quantile normal bilatéral à 95 %
Z95                     = 1.959964

# Un facteur de développement agrégé strictement sous ce seuil signe une
# REPRISE (recours, subrogation, annulation) que la courbe monotone croissante
# de Clark ne peut pas représenter. Seuil à 1.0 exactement : ce n'est pas une
# tolérance statistique mais une impossibilité de forme.
CLARK_FACTEUR_REPRISE   = 1.0


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

    if len(U) != Y.shape[0]:
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

def _hessienne_inverse(
    params: np.ndarray,
    Y:      np.ndarray,
    t:      np.ndarray,
    courbe: str,
    mask:   np.ndarray,
) -> Optional[np.ndarray]:
    """
    Inverse de la Hessienne numérique de la log-vraisemblance de POISSON.

    ⚠️ Ce n'est PAS encore la matrice de covariance des paramètres. Clark
    (2003) écrit la vraisemblance ODP comme ℓ_ODP = ℓ_Poisson / σ² ; sa
    Hessienne vaut donc H_Poisson / σ², et la covariance σ² · H_Poisson⁻¹.
    Le facteur σ² est appliqué par `_calculer_resultats`, pas ici.
    """
    try:
        from scipy.optimize import approx_fprime
        n_p   = len(params)
        eps_h = 1e-4 * np.maximum(np.abs(params), 1.0)
        H_num = np.zeros((n_p, n_p))
        for ki in range(n_p):
            e_ki = np.zeros(n_p)
            e_ki[ki] = eps_h[ki]
            g_plus  = approx_fprime(params + e_ki, _neg_loglik_odp,
                                    eps_h * 1e-2, Y, t, courbe, mask)
            g_minus = approx_fprime(params - e_ki, _neg_loglik_odp,
                                    eps_h * 1e-2, Y, t, courbe, mask)
            H_num[ki] = (g_plus - g_minus) / (2.0 * eps_h[ki])

        H_sym   = 0.5 * (H_num + H_num.T)
        eigvals = np.linalg.eigvalsh(H_sym)
        if np.min(eigvals) <= 0:                       # régularisation
            H_sym += np.eye(n_p) * max(-np.min(eigvals) + 1e-6, 1e-6)
        h_inv = np.linalg.inv(H_sym)
        return None if np.any(np.diag(h_inv) < 0) else h_inv
    except Exception as e:
        logger.debug(f'Clark ({courbe}) : Hessienne non calculable — {e}')
        return None


def _estimer_parametres(
    Y:           np.ndarray,
    t:           np.ndarray,
    mask:        np.ndarray,
    courbe:      str,
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

    # Stratégie 2 : obs_last / G(t_last) — l'initialisation recommandée par
    # Clark (2003), qui part de l'ultime implicite de chaque année.
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
    converge    = False

    # Grille de points de départ pour omega et theta
    omega_starts = [0.5, 1.0, 2.0, 3.0]
    theta_starts = [t[m // 2], t[m // 3]]

    bounds = [(1e-4, 10.0), (1e-2, t[-1] * 5.0)] + [(1.0, None)] * n

    for omega_0 in omega_starts:
        for theta_0 in theta_starts:
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
                    except Exception as e:
                        logger.debug(f'Clark optim ({courbe}, ω={omega_0:.1f}, θ={theta_0:.1f}) : {e}')
                        continue

    # Hessienne UNE SEULE FOIS, sur l'optimum retenu — et seulement si la
    # convergence est propre : l'inverse d'une Hessienne prise sur une solution
    # instable ne mesure rien. Elle était auparavant recalculée à chaque
    # amélioration du multi-départ, soit jusqu'à 48 fois pour un seul résultat.
    best_hinv = None
    if calculer_ic and converge and best_params is not None:
        best_hinv = _hessienne_inverse(best_params, Y, t, courbe, mask)

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
    mask:    np.ndarray,    # cellules effectivement ajustées par le MLE
    n_params: int,
) -> Dict:
    """
    Calcule ultimates, IBNR, tail factor, σ², IC 95% et statistiques.
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
    ibnr_par_annee       = []   # PLANCHÉ à 0 (provision ≥ 0) — affichage historique
    ibnr_brut_raw        = []   # brut float (peut être < 0) — base de la réserve
    ibnr_brut_par_annee  = []   # brut arrondi — signal sur-développement exposé
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
        ibnr_i = u_i - obs_last

        ultimates.append(u_i)
        ibnr_par_annee.append(max(ibnr_i, 0.0))    # planché : provision ≥ 0
        ibnr_brut_raw.append(ibnr_i)               # brut : sur-développement conservé
        ibnr_brut_par_annee.append(round(ibnr_i, 0))
        pct_developpe.append(pct)

    # Sur-développement : années où IBNR brut < 0 → ultimate Clark < cumul observé
    n_sur_dev = sum(1 for v in ibnr_brut_raw if v < 0)

    # Réserve totale depuis annee_base — sur l'IBNR BRUT (sur-développement conservé),
    # cohérent avec CL/Munich/Bootstrap post-chantier IBNR. Quasi-no-op en pratique :
    # Clark ajuste une courbe monotone croissante, donc l'ultime fitté dépasse le
    # cumul observé sauf sur des années quasi-mûres (souvent l'année 0, exclue de la
    # réserve). L'IBNR PLANCHÉ reste exposé séparément via ibnr_par_annee.
    reserve_totale = float(np.sum(ibnr_brut_raw[annee_base:]))

    # ── Résidus de Pearson — SUR LES CELLULES RÉELLEMENT AJUSTÉES ────────────
    # Le masque du MLE exclut les incréments négatifs ; le χ² doit porter sur
    # exactement le même ensemble, sinon σ² = χ²/df diviserait une somme sur un
    # ensemble par un degré de liberté compté sur un autre.
    mu = np.outer(U, p)  # (n, m)
    residus_list = [
        (Y[i, j] - mu[i, j]) / np.sqrt(mu[i, j])
        for i in range(n) for j in range(m)
        if mask[i, j] and mu[i, j] > 0
    ]

    residus_arr = np.array(residus_list) if residus_list else np.array([0.0])
    chi2 = float(np.sum(residus_arr ** 2))
    n_obs_fit = int(len(residus_list))
    df = n_obs_fit - n_params

    residus_stats = {
        'n':          n_obs_fit,
        'mean':       round(float(np.mean(residus_arr)), 4),
        'std':        round(float(np.std(residus_arr)), 4),
        'min':        round(float(np.min(residus_arr)), 4),
        'max':        round(float(np.max(residus_arr)), 4),
        'chi2_stat':  round(chi2, 4),
    }

    # ── σ² : sur-dispersion ODP (Clark 2003, χ² de Pearson mis à l'échelle) ───
    # C'est le pendant exact du φ du Bootstrap ODP : même modèle Var = σ²·μ,
    # deux estimateurs indépendants. Ils doivent différer — les ajustements
    # diffèrent — mais pas d'un ordre de grandeur ; l'écart est un diagnostic.
    sigma2 = float(chi2 / df) if df > 0 else None

    # ── Intervalles de prédiction 95% sur les ultimates ───────────────────────
    # Clark (2003) : Var(R) = variance de PROCESSUS + variance de PARAMÈTRE.
    #   · processus : Var = σ²·R_i          (modèle ODP, Var = σ²·μ)
    #   · paramètre : σ²·H⁻¹                (ℓ_ODP = ℓ_Poisson/σ² ⇒ la Hessienne
    #                                        de Poisson doit être remise à
    #                                        l'échelle par σ²)
    # L'ultime observé = payé à date (connu) + réserve, donc l'intervalle sur
    # l'ultime EST l'intervalle sur la réserve, translaté d'une constante.
    ic_95:      List[Tuple] = []
    se_param:   List        = []
    se_process: List        = []
    se_totale:  List        = []
    se_reserve_totale = None
    cv_reserve        = None

    if hess_inv is not None and sigma2 is not None and sigma2 > 0:
        try:
            h_uu   = np.asarray(hess_inv)[2:, 2:]          # bloc des U_i
            var_par = sigma2 * np.maximum(np.diag(h_uu), 0.0)
            for i in range(n):
                v_par = float(var_par[i])
                v_pro = float(sigma2 * max(ibnr_brut_raw[i], 0.0))
                v_tot = v_par + v_pro
                se_i  = float(np.sqrt(v_tot))
                se_param.append(round(float(np.sqrt(v_par)), 2))
                se_process.append(round(float(np.sqrt(v_pro)), 2))
                se_totale.append(round(se_i, 2))
                ic_95.append((
                    round(max(ultimates[i] - Z95 * se_i, 0), 0),
                    round(ultimates[i] + Z95 * se_i, 0),
                ))

            # Total : la variance de paramètre de Σ U_i fait intervenir les
            # COVARIANCES, pas seulement la diagonale — les ultimates partagent
            # ω et θ, donc leurs erreurs sont corrélées. La variance de
            # processus, elle, s'additionne (incréments indépendants).
            sl        = slice(annee_base, n)
            var_p_tot = sigma2 * float(np.sum(h_uu[sl, sl]))
            var_q_tot = sigma2 * float(sum(max(v, 0.0) for v in ibnr_brut_raw[annee_base:]))
            v_tot     = max(var_p_tot, 0.0) + max(var_q_tot, 0.0)
            se_reserve_totale = round(float(np.sqrt(v_tot)), 2)
            if reserve_totale > 0:
                cv_reserve = round(se_reserve_totale / reserve_totale * 100.0, 2)
        except Exception as e:                              # pragma: no cover
            logger.debug(f'Clark : IC non calculable — {e}')
            ic_95 = [(None, None)] * n
            se_param = se_process = se_totale = [None] * n
            se_reserve_totale = cv_reserve = None
    else:
        ic_95      = [(None, None)] * n
        se_param   = [None] * n
        se_process = [None] * n
        se_totale  = [None] * n

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
        'se_parametre':    se_param,
        'se_processus':    se_process,
        'se_totale':       se_totale,
        'se_reserve_totale': se_reserve_totale,
        'cv_reserve':      cv_reserve,
        'sigma2':          round(sigma2, 4) if sigma2 is not None else None,
        'df':              df,
        'residus':         residus_stats,
    }


# =============================================================================
#  AIC
# =============================================================================

def _aic(ll: float, n_params: int) -> float:
    """AIC = 2k - 2ℓ (Clark 2003)."""
    return 2.0 * n_params - 2.0 * ll


# =============================================================================
#  VERDICT DE STRUCTURE — Clark peut-il représenter CE triangle ?
# =============================================================================

def _verdict_structure_monotone(C: np.ndarray) -> Dict:
    """
    Verdict de STRUCTURE, à ne pas confondre avec la qualité de l'ajustement.

    G(t) est monotone croissante pour les deux courbes de Clark (2003) :
    log-logistique et Weibull valent 0 en 0 et 1 à l'infini, sans jamais
    redescendre. Le cumulé ajusté U_i·G(t_j) ne peut donc PAS décroître en j.

    Un facteur de développement agrégé strictement sous 1 décrit exactement
    l'inverse : un triangle qui redescend, parce que des recours ou des
    subrogations sont encaissés. Aucun couple (ω, θ) ne peut reproduire cela —
    ce n'est pas un mauvais ajustement, c'est une impossibilité de forme.
    L'optimiseur ne le signale pas : il rend le moins mauvais ajustement
    croissant, donc une réserve mécaniquement gonflée.

    ⚠️ CE N'EST PAS `n_sur_developpement`. Ce compteur-là compare l'ultime
    ajusté au dernier cumul observé ; sur un triangle à recours il reste à
    ZÉRO, puisque la courbe croissante place précisément l'ultime au-dessus du
    cumul pour toutes les années. Il constate une conséquence quand elle est
    visible ; il ne voit pas la cause.

    Returns
    -------
    Dict : compatible, testable, colonnes_reprise, facteurs_reprise,
           facteur_min, message
    """
    vide = {
        'compatible':       True,
        'testable':         False,
        'colonnes_reprise': [],
        'facteurs_reprise': [],
        'facteur_min':      None,
        'message':          'Structure non testable — facteurs de développement '
                            'indisponibles.',
    }
    try:
        facteurs = np.asarray(calculer_facteurs(C, 'standard')[0], dtype=float)
    except Exception as e:                                   # pragma: no cover
        logger.debug(f'Clark : verdict de structure non calculable — {e}')
        return vide

    if facteurs.size == 0 or not np.all(np.isfinite(facteurs)):
        return vide

    idx = [int(j) for j in np.where(facteurs < CLARK_FACTEUR_REPRISE)[0]]
    val = [round(float(facteurs[j]), 4) for j in idx]

    if not idx:
        return {
            'compatible':       True,
            'testable':         True,
            'colonnes_reprise': [],
            'facteurs_reprise': [],
            'facteur_min':      round(float(np.min(facteurs)), 4),
            'message':          'Structure compatible — aucun facteur de '
                                'développement sous 1.',
        }

    detail = ' ; '.join(f'colonne {j}→{j + 1} : {f:.4f}' for j, f in zip(idx, val))
    return {
        'compatible':       False,
        'testable':         True,
        'colonnes_reprise': idx,
        'facteurs_reprise': val,
        'facteur_min':      round(float(np.min(facteurs)), 4),
        'message': (
            f"⚠️ Clark inapplicable — {len(idx)} facteur(s) de développement "
            f"sous 1 ({detail}). Le triangle redescend (recours ou "
            f"subrogation) ; les courbes de Clark sont monotones croissantes "
            f"et ne peuvent pas représenter une reprise. Réserve NON PUBLIÉE : "
            f"l'ajustement serait mécaniquement gonflé, sans qu'aucun autre "
            f"indicateur de la méthode ne le signale. Utiliser Chain Ladder, "
            f"qui accepte les facteurs sous 1."
        ),
    }


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
    Méthode de Clark (2003) — LDF Curve-Fitting par Maximum de Vraisemblance.

    Parameters
    ----------
    C : np.ndarray
        Triangle des paiements CUMULÉS (n × m), zone connue i+j < n.
        Cas supportés : n=m (carré), n>m (court), n<m (long, rare).
    periodes : list[float], optional
        Âges de développement, strictement croissants. Défaut : [1, 2, ..., m],
        soit des ANNÉES — θ s'interprète alors en années. Les deux courbes ne
        dépendent que du rapport t/θ : changer d'unité (mois plutôt qu'années)
        ne change pas l'ajustement, seulement la lecture de θ.
    courbes : list[str]
        Courbes à tester : 'loglogistique' et/ou 'weibull'.
    annee_base : int
        Première année incluse dans la réserve totale.
    calculer_ic : bool
        Si True (défaut), calcule la Hessienne numérique et les IC 95%
        sur les ultimates. Coûteux sur grands triangles (O(n³)) —
        mettre à False si seule la réserve centrale est nécessaire.
    g_t2_min : float, optional
        Seuil G(t=2) en dessous duquel Clark est déclaré aberrant.
        Par défaut : CLARK_G_T2_MIN (0.10). Les branches à développement très
        long (RC Médicale, Construction) justifieraient un seuil plus bas,
        mais AUCUNE configuration de LoB ne le fixe aujourd'hui : ce paramètre
        existe et fonctionne, il n'est simplement jamais renseigné en amont.

    Returns
    -------
    Dict standard A7 Ibrahim. Clés effectivement présentes :
        success, disponible, aberrant, statut, erreur, message
        courbe_choisie, omega, theta, converge
        ultimates, pct_developpe, tail_factor
        structure_monotone   — verdict de FORME : la courbe croissante de Clark
                               peut-elle représenter ce triangle ? (cf.
                               `_verdict_structure_monotone`)
        ibnr_par_annee       — IBNR par année, PLANCHÉ à 0 (provision ≥ 0)
        ibnr_brut_par_annee  — IBNR brut, < 0 si sur-développement (ultime < cumul)
        n_sur_developpement  — nombre d'années où l'IBNR brut est < 0
        reserve_totale       — Σ IBNR BRUT depuis annee_base, ou None si la
                               structure est incompatible (recours)
        reserve_be_clark     — alias de reserve_totale
        reserve_brute        — la même somme, TOUJOURS renseignée, pour l'audit
        sigma2               — sur-dispersion ODP σ² = χ²/df, pendant du φ du
                               Bootstrap ODP : deux estimateurs indépendants du
                               même paramètre, à confronter
        df                   — degrés de liberté du χ² (cellules ajustées − k)
        ic_95                — intervalle de PRÉDICTION 95 % sur les ultimates
        se_parametre, se_processus, se_totale   — décomposition par année
        se_reserve_totale    — se de la réserve agrégée, COVARIANCES comprises
        cv_reserve           — se_reserve_totale / réserve, en %
        aic_loglogistique, aic_weibull, ll_loglogistique, ll_weibull,
        aic_optimal, ll_optimal, residus, n_params, n_obs,
        increments_non_positifs, periodes_arr, g_courbe
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

    # Pas de normalisation : la log-vraisemblance ODP n'est pas invariante à
    # l'échelle (Clark 2003 travaille sur les montants bruts).
    Y = np.full_like(C_float, np.nan)
    Y[:, 0] = C_float[:, 0]
    for j in range(1, m):
        Y[:, j] = C_float[:, j] - C_float[:, j - 1]

    # Vérification monotonicité : C[i,j] doit être croissant en j
    # (incréments négatifs = annulations/corrections — Clark invalide)
    _n_neg = int(np.sum(Y[~np.isnan(Y)] < 0))
    if _n_neg > 0:
        logger.warning(
            f'Clark : {_n_neg} incrément(s) négatif(s) détecté(s) — '
            f'triangle non-monotone. Cellules ignorées dans le MLE.'
        )

    # Masque : cellules effectivement observées (non NaN et non négatif)
    # Les incréments négatifs sont exclus — ils violent H1 de Clark (2003)
    mask = ~np.isnan(Y) & ~np.isnan(C_float) & (Y >= 0)

    n_obs = int(mask.sum())
    if n_obs < (n + CLARK_DF_MIN):  # besoin d'au moins n+CLARK_DF_MIN observations
        return {
            'success': False, 'disponible': False,
            'erreur':  f'Observations insuffisantes ({n_obs}) pour {n} années.',
            'message': 'Données insuffisantes pour Clark.',
        }

    # ── Estimation MLE pour chaque courbe ────────────────────────────────────
    # Aucun tirage aléatoire ici : le multi-départ balaie une grille FIXE
    # (ω × θ × stratégie d'initialisation × facteur d'échelle). Il n'y a donc
    # aucune graine à poser — celle qui figurait ici ne gouvernait rien et
    # réécrivait l'état global de np.random pour tout l'appelant.
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
            res = _calculer_resultats(C_float, Y, t, params, courbe, hinv,
                                      annee_base, mask, n_params)
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
    # ⚠️ CE N'EST PAS L'AIC QUI TRANCHE (cf. en-tête du module). La
    # log-logistique gagne presque toujours en vraisemblance mais extrapole sa
    # queue là où aucune donnée ne peut la contredire ; Weibull est donc
    # prioritaire tant que sa queue reste sous CLARK_TAIL_MAX. L'AIC ne sert
    # qu'en repli, et les deux valeurs restent publiées pour être contestables.
    courbes_ok = {c: aic for c, aic in aic_par_courbe.items() if aic is not None}

    if not courbes_ok:
        return {
            'success': False, 'disponible': True,
            'erreur':  'Optimisation Clark échouée pour toutes les courbes.',
            'message': 'Clark non convergé — résultats indisponibles.',
        }

    # Priorité à Weibull si tail raisonnable
    wb_ok = ('weibull' in resultats_courbes
             and float(resultats_courbes['weibull'].get('tail_factor', 99))
             < CLARK_TAIL_MAX)
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

    # ── Critères d'aberration actuariellement justifiés ──────────────────
    # Les motifs SONT le critère : `clark_aberrant` se déduit de la liste, il
    # n'est plus calculé en parallèle. Une méthode ne peut donc plus être
    # écartée sans que la phrase qui l'explique soit produite — c'est
    # exactement ce qui arrivait quand le seuil affiché (0.10 en dur) et le
    # seuil testé (g_t2_min, paramétrable) divergeaient.
    # NB : AIC absolu non utilisé (dépend de l'échelle des données)
    # NB : ratio Clark/CL non utilisé (circulaire)
    _omega_best  = float(best.get('omega', 1.0))
    _theta_best  = float(best.get('theta', 1.0))
    _g_t2_min    = g_t2_min if g_t2_min is not None else CLARK_G_T2_MIN
    # Seuil sur G(t=2) plutôt que sur G(t=1) : G(t=1) faible peut être normal
    # sur un triangle long (20×20+), alors qu'un développement encore
    # négligeable à 2 ans signe un MLE mal conditionné sur les années récentes.
    G_at_t2 = float(_g(np.array([t[min(1, m - 1)]]), _omega_best, _theta_best,
                       courbe_choisie)[0])

    _raison: List[str] = []
    if tail_factor > CLARK_TAIL_MAX:
        _raison.append(f'tail factor = {tail_factor:.3f} '
                       f'(> {CLARK_TAIL_MAX} — queue irréaliste)')
    if G_at_t2 < _g_t2_min:
        _raison.append(f'G(t=2) = {G_at_t2:.3f} (< {_g_t2_min:.0%} — '
                       f'MLE mal conditionné sur années récentes)')
    if not best.get('converge', True):
        _raison.append('MLE non convergé')
    clark_aberrant = bool(_raison)

    # ── Verdict de STRUCTURE : Clark peut-il seulement représenter ce triangle ?
    structure = _verdict_structure_monotone(C)

    # ── Message actuariel ─────────────────────────────────────────────────────
    # ΔAIC entre les deux courbes (comparaison relative — pas en absolu)
    _delta_aic = None
    if aic_ll is not None and aic_wb is not None:
        _delta_aic = round(aic_ll - aic_wb, 1)  # négatif si log-log meilleure

    if not structure['compatible']:
        statut  = 'ROUGE'
        message = structure['message']
    elif clark_aberrant:
        statut  = 'ROUGE'
        message = (
            f"⚠️ Clark {courbe_choisie} écarté — "
            f"{' ; '.join(_raison)}. "
            f"Méthode non retenue dans la pondération."
        )
    elif tail_factor > CLARK_TAIL_ALERTE:
        statut  = 'AMBRE'
        message = (
            f"Clark {courbe_choisie} sélectionné. "
            f"Queue notable : tail = {tail_factor:.3f}. "
            f"Résultat à titre informatif — vérifier le développement tardif."
        )
    else:
        statut  = 'VERT'
        message = (
            f"Clark {courbe_choisie} sélectionné. "
            f"Tail factor = {tail_factor:.4f}. "
            + (f"\u0394AIC Weibull vs Log-log = {_delta_aic:+.0f}. " if _delta_aic else '')
            + "Ajustement satisfaisant."
        )

    # La réserve n'est PAS publiée quand la courbe ne peut pas représenter le
    # triangle : un nombre sans avertissement se compare à Chain Ladder, et rien
    # dans la sortie ne permettrait de le mettre en doute. Même traitement que
    # les percentiles du Bootstrap quand BOOT-H3 ou BOOT-H4 sont rejetées.
    reserve_publiee = None if not structure['compatible'] else reserve_totale

    # ── Courbe G(t) pour graphique ────────────────────────────────────────────
    t_dense = np.linspace(0, t[-1] * 1.5, 100)
    g_courbe = _g(t_dense, float(best['omega']), float(best['theta']), courbe_choisie)

    # Reporting partagé des incréments ≤ 0 (increments_positifs) — informationnel :
    # l'estimateur MLE de Clark n'est PAS modifié (il gère les incréments dans sa
    # vraisemblance). On ne fait qu'exposer le comptage / la liste / la disponibilité.
    ip_neg = increments_positifs(C, plancher=None)

    return {
        'success':           True,
        'disponible':        True,
        'aberrant':          clark_aberrant,
        'increments_non_positifs': {
            'n_exclues':        ip_neg['n_exclues'],
            'cellules_exclues': ip_neg['cellules_exclues'],
            'frac_exclue':      ip_neg['frac_exclue'],
            'disponible':       ip_neg['disponible'],
        },

        'statut':            statut,
        'structure_monotone': structure,

        # Modèle sélectionné
        'courbe_choisie':    courbe_choisie,
        'omega':             best['omega'],
        'theta':             best['theta'],

        # Résultats actuariels
        'ultimates':           best['ultimates'],
        'ibnr_par_annee':      best['ibnr_par_annee'],        # PLANCHÉ à 0
        'ibnr_brut_par_annee': best['ibnr_brut_par_annee'],   # brut < 0 = sur-développement
        'n_sur_developpement': best['n_sur_developpement'],   # nb années ultime < cumul
        'reserve_totale':    reserve_publiee,   # None si structure incompatible
        'reserve_be_clark':  reserve_publiee,   # alias
        'reserve_brute':     reserve_totale,    # toujours renseignée, pour l'audit
        'tail_factor':       tail_factor,
        'pct_developpe':     best['pct_developpe'],

        # Incertitude — Clark (2003) : processus + paramètre, mis à l'échelle σ²
        'ic_95':             best['ic_95'],
        'se_parametre':      best['se_parametre'],
        'se_processus':      best['se_processus'],
        'se_totale':         best['se_totale'],
        'se_reserve_totale': best['se_reserve_totale'],
        'cv_reserve':        best['cv_reserve'],
        'sigma2':            best['sigma2'],
        'df':                best['df'],

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
