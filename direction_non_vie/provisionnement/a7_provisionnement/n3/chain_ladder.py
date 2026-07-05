# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n3/chain_ladder.py  —  Méthode Chain Ladder (4 variantes + tail factor)
# =============================================================================
#
#  Références mathématiques
#  ------------------------
#  Mack (1993) — "Distribution-Free Calculation of the Standard Error
#                 of Chain Ladder Reserve Estimates"
#                 ASTIN Bulletin 23(2), pp. 213-225
#
#  Taylor (1986) — "Claims Reserving in Non-Life Insurance"
#                  North-Holland, Amsterdam
#
#  Formules implémentées
#  ----------------------
#
#  Facteurs de développement
#  ─────────────────────────
#  Zone connue : C[i,j] disponible si i + j < n  (triangle supérieur gauche)
#
#  Standard (volume-weighted, Mack 1993) :
#      f_j = Σ_{i : i+j+1 < n} C[i,j+1]
#            ─────────────────────────────
#            Σ_{i : i+j+1 < n} C[i,j]
#
#  Volume-weighted (pondération √C[i,j]) :
#      f_j = Σ_{i} √C[i,j] × f[i,j]
#            ────────────────────────
#            Σ_{i} √C[i,j]
#      avec f[i,j] = C[i,j+1] / C[i,j]
#
#  Médiane :
#      f_j = médiane { f[i,j] = C[i,j+1]/C[i,j] | i+j+1 < n, C[i,j]>0 }
#
#  Trimmed mean (écrêtée 10%-90%) :
#      f_j = moyenne de { f[i,j] | q10 ≤ f[i,j] ≤ q90 }
#
#  Facteurs cumulés (de la colonne j jusqu'à ultime) :
#      F_j = f_j × f_{j+1} × ... × f_{m-2} × tail
#      F_{m-1} = tail
#
#  Ultimates :
#      U_i = C[i, k_i] × f_{k_i} × f_{k_i+1} × ... × f_{m-2} × tail
#      où k_i = min(n-i-1, m-1) = dernière colonne connue pour l'année i
#
#  IBNR :
#      IBNR_i = max(U_i - C[i, k_i], 0)
#
#  Réserve totale :
#      R = Σ_{i=annee_base}^{n-1} IBNR_i
#      Par défaut annee_base=1 (l'année i=0 est supposée totalement développée)
#      Paramétrable via annee_base_reserve
#
#  Tail factor (régression log-linéaire)
#  ──────────────────────────────────────
#  Sur les k derniers facteurs (k=min(8, n_facteurs)) :
#      log(f_j - 1) = a + b × j    →    régression OLS
#      tail = Π_{j=m-1}^{∞} (1 + exp(a + b×j))  (tronqué à convergence)
#
#  Dimensions du triangle
#  ──────────────────────
#  n×m quelconque avec :
#    · n ≥ 3  (années de survenance)
#    · m ≥ 3  (périodes de développement)
#    · n×m    carré (cas standard) ou rectangulaire (triangle tronqué)
#    · Cas typique marché FR : 10×10 à 15×15
#    · Cas RC Médicale / Construction : 20×25 à 30×30
#    · Max supporté : 60×60 (validation N1)
#
# =============================================================================

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
try:
    from scipy.optimize import curve_fit as _curve_fit
except ImportError:
    _curve_fit = None

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  CALCUL DES FACTEURS DE DÉVELOPPEMENT
# =============================================================================

def calculer_facteurs(
    C:       np.ndarray,
    methode: str = 'standard',
) -> Tuple[np.ndarray, List[List[float]]]:
    """
    Calcule les facteurs de développement CL et les facteurs individuels.

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé. Zone connue : C[i,j] avec i+j < n.
        Zéros utilisés pour les cellules inconnues (hors zone connue).
    methode : str
        'standard'        — volume-weighted (Mack 1993, estimateur optimal)
        'volume_weighted' — pondération par √C[i,j] (distinct de 'standard'
                            qui pondère par C[i,j] au sens de Mack 1993)
        'mediane'         — médiane des facteurs individuels (robuste outliers)
        'trimmed_mean'    — moyenne écrêtée 10%-90% (compromis)

    Returns
    -------
    facteurs : np.ndarray  shape (m-1,)
        Vecteur des facteurs agrégés f_0, ..., f_{m-2}.
        Tous ≥ 1.0 (un triangle cumulé ne peut que croître).
    facteurs_indiv : List[List[float]]
        facteurs_indiv[j] = liste des f[i,j] = C[i,j+1]/C[i,j]
        pour les i tels que i+j+1 < n et C[i,j] > 0.
        Utilisés par Mack (σ²) et Bootstrap ODP (résidus).
    """
    n, m         = C.shape
    facteurs     = np.ones(m - 1)
    facteurs_ind = []   # facteurs_ind[j] = [f[0,j], f[1,j], ...]

    for j in range(m - 1):
        f_ind = []   # facteurs individuels de la colonne j
        c_j   = []   # C[i,j] correspondants (pour pondérations)

        for i in range(n):
            # Zone connue : i+j < n  ET  i+j+1 < n
            if i + j + 1 >= n:
                break
            c_ij  = float(C[i, j])
            c_ij1 = float(C[i, j + 1])
            if c_ij > 0 and c_ij1 > 0:
                f_ind.append(c_ij1 / c_ij)
                c_j.append(c_ij)

        facteurs_ind.append(f_ind)

        if not f_ind:
            # Aucune observation → facteur = 1 (neutre)
            facteurs[j] = 1.0
            logger.warning(f"Colonne j={j} : aucune observation — facteur=1.0")
            continue

        arr = np.array(f_ind,  dtype=float)
        w   = np.array(c_j,    dtype=float)

        if methode == 'standard':
            # ── Standard (Mack 1993) ────────────────────────────────────────
            # f_j = Σ C[i,j+1] / Σ C[i,j]
            # Équivalent à np.average(arr, weights=w) car :
            # Σ w_i f_i / Σ w_i = Σ C[i,j]×(C[i,j+1]/C[i,j]) / Σ C[i,j]
            #                    = Σ C[i,j+1] / Σ C[i,j]
            facteurs[j] = float(np.average(arr, weights=w))

        elif methode == 'volume_weighted':
            # ── Volume-weighted (pondération √C[i,j]) ──────────────────────
            # Donne moins de poids aux très grandes années
            w_sqrt      = np.sqrt(w)
            facteurs[j] = float(np.average(arr, weights=w_sqrt))

        elif methode == 'mediane':
            # ── Médiane ─────────────────────────────────────────────────────
            # Insensible aux outliers. Perd l'information volume.
            facteurs[j] = float(np.median(arr))

        elif methode == 'trimmed_mean':
            # ── Moyenne écrêtée 10%-90% ─────────────────────────────────────
            # Élimine les 10% les plus hauts et les 10% les plus bas.
            # Nécessite au moins 4 observations pour être significative.
            if len(arr) >= 4:
                q10 = np.percentile(arr, 10)
                q90 = np.percentile(arr, 90)
                mask = (arr >= q10) & (arr <= q90)
                facteurs[j] = float(np.mean(arr[mask])) if mask.sum() > 0 \
                               else float(np.mean(arr))
            else:
                # Trop peu d'obs → fallback standard
                facteurs[j] = float(np.average(arr, weights=w))

        else:
            # Fallback sécurisé → standard
            logger.warning(
                f"Méthode '{methode}' inconnue — fallback standard"
            )
            facteurs[j] = float(np.average(arr, weights=w))

        # Contrainte : facteur ≥ 1.0
        # Un triangle cumulé ne peut que croître (ou stagner).
        # Un facteur < 1.0 signifie une inversion dans les données.
        if facteurs[j] < 1.0:
            logger.warning(
                f"Facteur j={j} = {facteurs[j]:.4f} < 1.0 "
                f"— forcé à 1.0 (inversion dans le triangle)"
            )
            facteurs[j] = 1.0

    return facteurs, facteurs_ind


# =============================================================================
#  FACTEURS CUMULÉS
# =============================================================================

def calculer_facteurs_cumules(
    facteurs:    np.ndarray,
    tail_factor: float = 1.0,
) -> np.ndarray:
    """
    Calcule les facteurs de développement cumulés de j à ultime.

    F_j = f_j × f_{j+1} × ... × f_{m-2} × tail

    Parameters
    ----------
    facteurs : np.ndarray  shape (m-1,)
        Facteurs individuels f_0, ..., f_{m-2}.
    tail_factor : float
        Facteur tail (développement au-delà de la dernière colonne).
        1.0 si pas de tail.

    Returns
    -------
    f_cum : np.ndarray  shape (m-1,)
        f_cum[j] = facteur cumulé depuis la colonne j jusqu'à ultime.
        f_cum[-1] = tail_factor (colonne finale).
    """
    m     = len(facteurs)
    f_cum = np.ones(m)

    # Partir de la droite (colonne la plus développée)
    f_cum[m - 1] = tail_factor
    for j in range(m - 2, -1, -1):
        f_cum[j] = facteurs[j] * f_cum[j + 1]

    return f_cum


# =============================================================================
#  TAIL FACTOR (RÉGRESSION LOG-LINÉAIRE)
# =============================================================================

def calculer_tail_factor(
    facteurs:                  np.ndarray,
    lob_tail_max_alerte:       float = 1.05,
    n_facteurs_queue:          int   = 4,
    risque_long:               bool  = True,
    tail_seuil_stabilisation:  float = 1.02,
) -> Dict:
    """
    Estime le tail factor par régression log-linéaire sur les derniers
    facteurs de développement.

    Conditions d'application — Guide de l'Institut des Actuaires (2023)
    --------------------------------------------------------------------
    Le tail factor NE s'applique QUE si les deux conditions suivantes
    sont réunies simultanément :

    1. RISQUE LONG : la branche est classée à développement long
       (RC Médicale, RC Générale, RC Auto Corporels, Construction,
        Transport, CAT NAT). Pour les risques courts (MRH, RC Auto
        Matériel), tail = 1.0.

    2. COEFFICIENTS NON STABILISÉS : le dernier LDF observé dépasse
       le seuil de stabilisation propre à la LoB (tail_seuil_stabilisation).
       Si dernier LDF < seuil → coefficients stabilisés → tail = 1.0.

    Méthode de calcul (si applicable) — Mack 1993 / Taylor 1986
    ------------------------------------------------------------
    Régression log-linéaire sur les n derniers facteurs (défaut n=4) :

        log(f_j - 1) ≈ a + b × j    avec b < 0 (décroissance)

    Extrapolation :
        tail = Π_{j=m}^{∞} (1 + exp(a + b×j))

    Troncature à convergence : f_extrap < 1 + 1e-4 ou 50 itérations max.
    Tail clippé à [1.0, 1.20].

    Parameters
    ----------
    facteurs : np.ndarray
        Vecteur des facteurs f_0, ..., f_{m-2}.
    lob_tail_max_alerte : float
        Seuil d'alerte tail factor depuis lob_config.
    n_facteurs_queue : int
        Nombre de derniers facteurs pour la régression (défaut 4).
    risque_long : bool
        True si la branche est à développement long (depuis lob_config).
    tail_seuil_stabilisation : float
        Dernier LDF minimum pour que le tail soit appliqué (depuis lob_config).

    Returns
    -------
    dict avec tail_factor, methode, statut, message.
    """
    n_f = len(facteurs)

    # ── Condition 1 — Guide IA 2023 : risque court → tail = 1.0 ─────────────
    if not risque_long:
        return {
            'tail_factor': 1.0,
            'methode':     'non applicable (risque court)',
            'statut':      'VERT',
            'message':     (
                "Tail factor = 1.0 — branche à développement court. "
                "Guide IA 2023 : le tail factor ne s'applique qu'aux risques longs."
            ),
        }

    # ── Condition 2 — Guide IA 2023 : coefficients stabilisés → tail = 1.0 ──
    # Pratique professionnelle française :
    # LDF < 1.05 = développement très faible = stabilisé
    # LDF < 1.10 = développement faible = stabilisé
    # LDF < 1.15 = quasi-stabilisé
    dernier_ldf = float(facteurs[-1]) if n_f > 0 else 1.0

    if dernier_ldf < 1.05:
        niveau_stab = "totalement stabilisé (LDF < 1,05)"
    elif dernier_ldf < 1.10:
        niveau_stab = "stabilisé (LDF < 1,10)"
    elif dernier_ldf < 1.15:
        niveau_stab = "quasi-stabilisé (LDF < 1,15)"
    else:
        niveau_stab = "non stabilisé (LDF ≥ 1,15)"

    if dernier_ldf < tail_seuil_stabilisation:
        return {
            'tail_factor': 1.0,
            'methode':     'non applicable (coefficients stabilisés)',
            'statut':      'VERT',
            'message':     (
                f"Tail factor = 1.0 — dernier LDF observé = {dernier_ldf:.4f} "
                f"({niveau_stab}). "
                f"Seuil de stabilisation LoB = {tail_seuil_stabilisation:.2f}. "
                "Guide IA 2023 : tail factor non justifié si coefficients stabilisés."
            ),
        }

    # ── Pas assez de facteurs pour régresser ─────────────────────────────────
    if n_f < 4:
        return {
            'tail_factor': 1.0,
            'methode':     'aucune (trop peu de facteurs)',
            'statut':      'VERT',
            'message':     "Tail factor = 1.0 — triangle trop court pour régresser.",
        }

    # ── Régression log-linéaire (Mack 1993) ──────────────────────────────────
    # Utiliser les k derniers facteurs — Guide IA : facteurs proches de 1.0
    k        = min(n_facteurs_queue, n_f)
    f_queue  = facteurs[n_f - k:]
    x        = np.arange(k, dtype=float)

    # log(f-1) — clip à 1e-8 pour éviter log(0)
    eps = 1e-8
    log_f_m1 = np.log(np.maximum(f_queue - 1.0, eps))

    # Régression OLS : log(f-1) = a + b×x
    try:
        b, a = np.polyfit(x, log_f_m1, 1)

        if b >= 0:
            # ⚠️ Pente positive : LDF croissants avec l'âge = pattern anormal
            # Causes possibles : rupture sinistralité, inflation, données insuffisantes
            # → tail = 1.0 par prudence (pas d'extrapolation)
            logger.warning(
                f"⚠️ Tail factor : pente positive b={b:.4f} — LDF croissants avec l'âge. "
                f"Causes possibles : rupture sinistralité, inflation, données insuffisantes. "
                f"Tail = 1.0 (pas d'extrapolation)."
            )
            tail = 1.0
        else:
            # Extrapoler au-delà du dernier facteur connu
            tail     = 1.0
            max_iter = 50
            for step in range(max_iter):
                j_extrap   = k + step
                f_extrap   = 1.0 + np.exp(a + b * j_extrap)
                if f_extrap < 1.0 + 1e-4:
                    break
                tail *= f_extrap

    except Exception as e:
        logger.warning(f"Tail factor : régression échouée ({e}) → tail=1.0")
        tail = 1.0

    # Clipper à [1.0, tail_max] — tail_max = min(lob_tail_max_alerte × 1.5, 1.50)
    tail_max = min(lob_tail_max_alerte * 1.5, 1.50)
    tail = float(np.clip(tail, 1.0, tail_max))

    # Statut selon seuil LoB
    if tail >= lob_tail_max_alerte:
        statut = 'ROUGE'
    elif tail >= 1.0 + (lob_tail_max_alerte - 1.0) * 0.5:
        statut = 'AMBRE'
    else:
        statut = 'VERT'

    if tail < 1.001:
        msg = (
            f"Tail factor = {tail:.4f} — "
            f"développement considéré complet (tail ≈ 1)."
        )
    else:
        msg = (
            f"Tail factor = {tail:.4f} appliqué — "
            f"dernier LDF = {dernier_ldf:.4f} ≥ seuil {tail_seuil_stabilisation:.2f} "
            f"({niveau_stab}). "
            f"+{(tail - 1)*100:.2f}% de provisions additionnelles "
            f"au-delà de la dernière colonne. "
            f"Guide IA 2023 — régression log-linéaire (Mack 1993)."
        )

    return {
        'tail_factor': round(tail, 6),
        'methode':     'régression exponentielle log-linéaire',
        'statut':      statut,
        'message':     msg,
    }




# =============================================================================
#  TAIL FACTOR MULTI-MÉTHODES AVEC SÉLECTION AIC
#  À insérer dans chain_ladder.py après la fonction calculer_tail_factor
# =============================================================================
#
#  Trois méthodes calibrées par scipy.optimize.curve_fit :
#
#  M1 — Log-linéaire (Mack 1993)  : f(j) = 1 + exp(a + b×j),  b < 0
#  M2 — Inverse power curve       : f(j) = 1 + c × j^(-d),    c,d > 0
#  M3 — Exponential decay         : f(j) = 1 + e × exp(-f×j), e,f > 0
#
#  Sélection par AIC = 2k - 2×log(L) où L est la vraisemblance gaussienne
#  sur les résidus des facteurs observés vs ajustés.
#
#  Référence : Mack (1993), Clark LDF (2003), Taylor (1986)
# =============================================================================


def _aic(residus: np.ndarray, n_params: int) -> float:
    """Calcule l'AIC à partir des résidus et du nombre de paramètres."""
    n = len(residus)
    if n <= n_params:
        return np.inf
    sse = float(np.sum(residus ** 2))
    if sse <= 0:
        return -np.inf
    sigma2 = sse / n
    log_lik = -n / 2 * np.log(2 * np.pi * sigma2) - sse / (2 * sigma2)
    return 2 * n_params - 2 * log_lik


def _extrapoler_tail(f_func, j_start: int, params: tuple,
                     max_iter: int = 100, tol: float = 1e-5) -> float:
    """Produit les facteurs extrapolés jusqu'à convergence."""
    tail = 1.0
    for step in range(max_iter):
        j = j_start + step
        f_j = float(f_func(j, *params))
        increment = f_j - 1.0
        if increment < tol:
            break
        tail *= f_j
    return max(tail, 1.0)


def calculer_tail_factor_multi(
    facteurs:                 np.ndarray,
    lob_tail_max_alerte:      float = 1.05,
    n_facteurs_queue:         int   = 4,
    risque_long:              bool  = True,
    tail_seuil_stabilisation: float = 1.02,
) -> Dict:
    """
    Estime le tail factor par trois méthodes et sélectionne la meilleure
    selon le critère AIC (Akaike Information Criterion).

    Méthodes calibrées :
      M1 — Log-linéaire   : f(j) = 1 + exp(a + b×j)      [2 params]
      M2 — Inverse power  : f(j) = 1 + c × j^(-d)        [2 params]
      M3 — Exponential    : f(j) = 1 + e × exp(-f×j)     [2 params]

    Parameters
    ----------
    facteurs                 : vecteur des LDF observés f_0..f_{m-2}
    lob_tail_max_alerte      : seuil d'alerte tail (depuis lob_config)
    n_facteurs_queue         : nombre de LDF utilisés pour calibration
    risque_long              : True si branche à développement long
    tail_seuil_stabilisation : dernier LDF minimum pour appliquer un tail

    Returns
    -------
    dict : tail_factor, methode, methode_retenue, comparaison_methodes,
           statut, message, aic_retenu
    """
    from scipy.optimize import curve_fit

    n_f = len(facteurs)

    # ── Conditions préalables identiques à calculer_tail_factor ──────────────
    if not risque_long:
        return {
            'tail_factor': 1.0, 'methode': 'non applicable (risque court)',
            'methode_retenue': 'aucune', 'comparaison_methodes': {},
            'statut': 'VERT', 'aic_retenu': None,
            'message': "Tail = 1.0 — risque court (Guide IA 2023).",
        }

    dernier_ldf = float(facteurs[-1]) if n_f > 0 else 1.0

    if dernier_ldf < tail_seuil_stabilisation:
        return {
            'tail_factor': 1.0, 'methode': 'non applicable (LDF stabilisé)',
            'methode_retenue': 'aucune', 'comparaison_methodes': {},
            'statut': 'VERT', 'aic_retenu': None,
            'message': (
                f"Tail = 1.0 — dernier LDF={dernier_ldf:.4f} "
                f"< seuil {tail_seuil_stabilisation:.2f} (coefficients stabilisés)."
            ),
        }

    if n_f < 4:
        return {
            'tail_factor': 1.0, 'methode': 'aucune (trop peu de facteurs)',
            'methode_retenue': 'aucune', 'comparaison_methodes': {},
            'statut': 'VERT', 'aic_retenu': None,
            'message': "Tail = 1.0 — triangle trop court pour calibrer.",
        }

    # ── Préparer les données de calibration ───────────────────────────────────
    k       = min(n_facteurs_queue, n_f)
    f_queue = facteurs[n_f - k:]
    x       = np.arange(k, dtype=float)
    eps     = 1e-8

    # ── Définition des trois courbes ──────────────────────────────────────────
    def f_log_lin(j, a, b):
        """M1 — Log-linéaire : f(j) = 1 + exp(a + b×j)"""
        return 1.0 + np.exp(np.clip(a + b * j, -20, 10))

    def f_inverse_power(j, c, d):
        """M2 — Inverse power : f(j) = 1 + c × j^(-d)"""
        j_safe = np.maximum(j, eps)
        return 1.0 + c * np.power(j_safe + 1, -d)

    def f_exponential(j, e, g):
        """M3 — Exponential decay : f(j) = 1 + e × exp(-g×j)"""
        return 1.0 + e * np.exp(-g * j)

    methodes = {
        'log_lineaire': {
            'func': f_log_lin,
            'p0': (-2.0, -0.5),
            'bounds': ([-10, -5], [5, -1e-6]),
            'label': 'Log-linéaire (Mack 1993)',
            'n_params': 2,
        },
        'inverse_power': {
            'func': f_inverse_power,
            'p0': (0.1, 1.0),
            'bounds': ([1e-6, 1e-6], [10, 10]),
            'label': 'Inverse power curve',
            'n_params': 2,
        },
        'exponential': {
            'func': f_exponential,
            'p0': (0.1, 0.5),
            'bounds': ([1e-6, 1e-6], [10, 10]),
            'label': 'Exponential decay',
            'n_params': 2,
        },
    }

    # ── Calibration + AIC pour chaque méthode ────────────────────────────────
    resultats = {}
    tail_max  = min(lob_tail_max_alerte * 1.5, 1.50)

    for nom, cfg in methodes.items():
        try:
            popt, _ = curve_fit(
                cfg['func'], x, f_queue,
                p0=cfg['p0'], bounds=cfg['bounds'],
                maxfev=2000,
            )

            # Vérifier la décroissance (b < 0 pour log-linéaire)
            if nom == 'log_lineaire' and popt[1] >= 0:
                resultats[nom] = {'tail': 1.0, 'aic': np.inf,
                                  'params': popt, 'label': cfg['label'],
                                  'echec': 'pente positive'}
                continue

            # Résidus et AIC
            f_ajuste = cfg['func'](x, *popt)
            residus  = f_queue - f_ajuste
            aic      = _aic(residus, cfg['n_params'])

            # Extrapolation
            tail_raw = _extrapoler_tail(cfg['func'], k, popt)
            tail     = float(np.clip(tail_raw, 1.0, tail_max))

            resultats[nom] = {
                'tail': tail, 'aic': aic,
                'params': popt, 'label': cfg['label'],
                'residus_mse': float(np.mean(residus ** 2)),
            }

        except Exception as _e:
            resultats[nom] = {'tail': 1.0, 'aic': np.inf,
                              'params': None, 'label': cfg['label'],
                              'echec': str(_e)}

    # ── Sélection par AIC minimum ─────────────────────────────────────────────
    valides = {k: v for k, v in resultats.items() if v['aic'] < np.inf}

    if not valides:
        # Fallback sur log-linéaire classique
        fallback = calculer_tail_factor(
            facteurs, lob_tail_max_alerte, n_facteurs_queue,
            risque_long, tail_seuil_stabilisation
        )
        fallback['methode_retenue'] = 'log_lineaire (fallback)'
        fallback['comparaison_methodes'] = {}
        fallback['aic_retenu'] = None
        return fallback

    meilleure = min(valides, key=lambda k: valides[k]['aic'])
    tail_final = valides[meilleure]['tail']
    aic_final  = valides[meilleure]['aic']

    # ── Statut ────────────────────────────────────────────────────────────────
    if tail_final >= lob_tail_max_alerte:
        statut = 'ROUGE'
    elif tail_final >= 1.0 + (lob_tail_max_alerte - 1.0) * 0.5:
        statut = 'AMBRE'
    else:
        statut = 'VERT'

    # ── Tableau comparatif ────────────────────────────────────────────────────
    comparaison = {}
    for nom, res in resultats.items():
        comparaison[nom] = {
            'label':    res['label'],
            'tail':     round(res['tail'], 6),
            'aic':      round(res['aic'], 2) if res['aic'] < np.inf else None,
            'retenu':   (nom == meilleure),
            'echec':    res.get('echec'),
        }

    # ── Message ───────────────────────────────────────────────────────────────
    label_retenu = resultats[meilleure]['label']
    msg = (
        f"Tail factor = {tail_final:.4f} — méthode retenue : {label_retenu} "
        f"(AIC = {aic_final:.1f}). "
        f"3 méthodes calibrées — sélection par critère AIC. "
        f"+{(tail_final-1)*100:.2f}% de provisions au-delà de la dernière colonne."
    )

    return {
        'tail_factor':          round(tail_final, 6),
        'methode':              label_retenu,
        'methode_retenue':      meilleure,
        'comparaison_methodes': comparaison,
        'statut':               statut,
        'aic_retenu':           round(aic_final, 2),
        'message':              msg,
    }


# =============================================================================
#  % DÉVELOPPÉ PAR ANNÉE
# =============================================================================

def calculer_pct_developpe(
    C:     np.ndarray,
    f_cum: np.ndarray,
) -> np.ndarray:
    """
    Pourcentage développé pour chaque année de survenance.

        pct_dev[i] = 1 / F_{k_i}

    où k_i = min(n-i-1, m-1) est la dernière colonne connue de l'année i,
    et F_{k_i} est le facteur cumulé depuis k_i jusqu'à ultime.

    Interprétation : pct_dev[i] = fraction des sinistres déjà payés.
    L'IBNR BF = primes × LR × (1 - pct_dev[i]).

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
    f_cum : np.ndarray  shape (m-1,)

    Returns
    -------
    pct : np.ndarray  shape (n,)
        Valeurs dans [0, 1]. 1.0 = totalement développé.
    """
    n, m = C.shape
    pct  = np.ones(n)

    for i in range(n):
        k = min(n - i - 1, m - 1)   # dernière colonne connue
        if k < len(f_cum) and f_cum[k] > 0:
            pct[i] = 1.0 / f_cum[k]
        else:
            pct[i] = 1.0

    return np.clip(pct, 0.0, 1.0)


# =============================================================================
#  CHAIN LADDER — PROJECTION
# =============================================================================

def chain_ladder(
    C:                       np.ndarray,
    methode:                 str   = 'standard',
    annee_base_reserve:      int   = 1,
    lob_tail_max_alerte:     float = 1.05,
    n_facteurs_queue:        int   = 4,
    risque_long:             bool  = True,
    tail_seuil_stabilisation: float = 1.02,
    tail_force:              Optional[float] = None,
) -> Dict:
    """
    Chain Ladder complet : facteurs → tail → ultimates → IBNR → réserve.

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé payé. Zéros pour la zone inconnue.
        n : nombre d'années de survenance  (≥ 3)
        m : nombre de périodes de développement  (≥ 3)
        Cas supportés :
          · n = m  (triangle carré, cas standard)
          · n > m  (plus d'années que de colonnes, triangle "court")
          · n < m  (plus de colonnes que d'années, triangle "long", rare)
    methode : str
        Variante CL : 'standard' | 'volume_weighted' | 'mediane' | 'trimmed_mean'
    annee_base_reserve : int
        Index (0-based) de la première année incluse dans la réserve totale.
        Défaut = 1 : exclut i=0 (supposée totalement développée).
        Mettre 0 pour inclure toutes les années.
        Utile pour triangles courts où i=0 n'est pas totalement développée.
    lob_tail_max_alerte : float
        Seuil d'alerte tail (depuis lob_config.tail_factor_max_alerte).
    n_facteurs_queue : int
        Nombre de facteurs utilisés pour la régression tail.

    Returns
    -------
    dict avec :
        facteurs, facteurs_cumules, facteurs_indiv
        tail_factor
        ultimates, ibnr_par_annee, reserve_totale
        pct_developpe, methode, message
    """
    n, m = C.shape

    # ── 1. Facteurs de développement ──────────────────────────────────────────
    facteurs, facteurs_ind = calculer_facteurs(C, methode)

    # ── 2. Tail factor ────────────────────────────────────────────────────────
    if tail_force is not None:
        # Tail pré-calculé par agent.py — pas de recalcul interne
        tail = {
            'tail_factor': tail_force,
            'methode':     'fourni par agent',
            'statut':      'VERT' if tail_force <= lob_tail_max_alerte else 'ROUGE',
            'message':     f"Tail factor = {tail_force:.6f} (fourni par agent).",
        }
    else:
        tail = calculer_tail_factor(
            facteurs,
            lob_tail_max_alerte      = lob_tail_max_alerte,
            n_facteurs_queue         = n_facteurs_queue,
            risque_long              = risque_long,
            tail_seuil_stabilisation = tail_seuil_stabilisation,
        )

    # ── 3. Facteurs cumulés (avec tail) ───────────────────────────────────────
    f_cum = calculer_facteurs_cumules(facteurs, tail['tail_factor'])

    # ── 4. % développé ────────────────────────────────────────────────────────
    pct_dev = calculer_pct_developpe(C, f_cum)

    # ── 5. Ultimates et IBNR ──────────────────────────────────────────────────
    #
    # Pour chaque année i :
    #   k_i = min(n-i-1, m-1)  ← dernière colonne connue
    #   U_i = C[i, k_i] × f_{k_i} × ... × f_{m-2} × tail
    #
    # Implémentation : multiplier C[i, k_i] par les facteurs restants.
    # On utilise les facteurs individuels (pas les cumulés) pour éviter
    # les erreurs d'arrondi sur les très petits/grands triangles.

    ultimates  = np.zeros(n)
    ibnr       = np.zeros(n)
    last_diag  = np.array([
        float(C[i, min(n - i - 1, m - 1)]) for i in range(n)
    ])

    for i in range(n):
        k_i = min(n - i - 1, m - 1)    # dernière colonne connue
        val = float(C[i, k_i])

        # Multiplier par les facteurs restants f_{k_i}, ..., f_{m-2}
        for j in range(k_i, m - 1):
            if j < len(facteurs):
                val *= facteurs[j]

        # Appliquer le tail
        val *= tail['tail_factor']

        ultimates[i] = val
        ibnr[i]      = max(val - last_diag[i], 0.0)

    # ── 6. Réserve totale ─────────────────────────────────────────────────────
    # Par défaut : Σ IBNR_{i=1}^{n-1} (exclure i=0 supposée développée)
    # Paramétrable via annee_base_reserve
    idx_base       = max(0, min(annee_base_reserve, n - 1))
    reserve_totale = float(np.sum(ibnr[idx_base:]))

    # ── 7. Résumé ─────────────────────────────────────────────────────────────
    msg = (
        f"Chain Ladder ({methode}) : "
        f"réserve={reserve_totale:,.0f}€ | "
        f"tail={tail['tail_factor']:.4f} | "
        f"{n}×{m} | base={idx_base}"
    )
    logger.info(msg)

    return {
        # Facteurs
        'facteurs':             [round(float(f), 6) for f in facteurs],
        'facteurs_cumules':     [round(float(f), 6) for f in f_cum],
        'facteurs_indiv':       facteurs_ind,

        # Tail
        'tail_factor':          tail,

        # Résultats
        'ultimates':            [round(float(u), 2) for u in ultimates],
        'ibnr_par_annee':       [round(float(v), 2) for v in ibnr],
        'last_diagonale':       [round(float(d), 2) for d in last_diag],
        'pct_developpe':        [round(float(p), 4) for p in pct_dev],

        # Réserve
        'reserve_totale':       round(reserve_totale, 2),
        'reserve_best_estimate': round(reserve_totale, 2),
        'annee_base_reserve':   idx_base,

        # Métadonnées
        'methode':              f'Chain Ladder ({methode})',
        'n':                    n,
        'm':                    m,
        'message':              msg,
    }
