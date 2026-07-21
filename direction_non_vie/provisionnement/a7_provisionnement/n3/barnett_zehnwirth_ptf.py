# =============================================================================
#  ActuarIA — Direction Non-Vie / Provisionnement A7 Ibrahim
#  n3/barnett_zehnwirth_ptf.py  —  Barnett-Zehnwirth PTF (log-normal) — ÉTAPE 2a
#
#  Référence : Barnett & Zehnwirth (2000) — "Best Estimates for Reserves",
#  Proceedings of the Casualty Actuarial Society. Probabilistic Trend Family.
#
#  ⚠️ PÉRIMÈTRE 2a = DÉTECTION SEULEMENT. Ce module détecte et localise des
#     TENDANCES et des RUPTURES (changements de tendance) dans les trois
#     directions du triangle, en régression log-normale. Il NE produit PAS de
#     réserve et NE projette RIEN vers le futur (2b, séparé, à venir). Le
#     paramètre `produire_reserve` existe pour 2b mais ne fait rien ici.
#
#  MODÈLE (Probabilistic Trend Family, log-normal) :
#     y_wd = log(p_wd) = α_w + D(d) + K(t=w+d) + ε ,  ε ~ N(0, σ²_d)
#       · α_w  : niveau (log) de l'année de survenance w (niveaux libres)
#       · D(d) : courbe de développement.
#                - ruptures_dev=None  → NIVEAUX de développement LIBRES
#                  (piecewise-linéaire maximalement segmenté) : absorbe toute
#                  la forme du développement pour un test calendaire propre.
#                - ruptures_dev fournies → piecewise-linéaire (pente + hinges),
#                  pour TESTER une rupture de tendance développement.
#       · K(t) : effet calendaire PARAMÉTRÉ EN CHANGEMENTS UNIQUEMENT —
#                somme de hinges Δι_r · max(0, t − t_r) sur les ruptures
#                déclarées. La pente calendaire CONSTANTE n'est JAMAIS estimée
#                (confondue par t = w + d : absorbée par α_w + pente de D).
#       · σ²_d : variance par bandes de développement (early/mid/late), IRLS ;
#                repli sur σ² constante si trop peu de points par bande.
#
#  ⚠️ MUR D'IDENTIFIABILITÉ (mathématique, non contournable — prouvé) :
#     une inflation calendaire CONSTANTE reste NON identifiable sur le triangle
#     seul. B&Z détecte les CHANGEMENTS de tendance (ruptures), pas le niveau
#     absolu d'une tendance constante. VERT ne certifie pas l'absence
#     d'inflation. (Détecter le niveau exige primes/exposition — externe.)
#
#  Complémentarité avec n3/glm_apc_poisson.py (étape 1) :
#     · GLM APC = test F omnibus de COURBURE calendaire (écran rapide) + réserve
#       = chain-ladder. B&Z PTF = test CIBLÉ d'une rupture déclarée (plus
#       puissant sur tendances modérées, localise la rupture). Les deux sont
#       cohérents : quand l'APC détecte, B&Z aussi ; B&Z détecte en plus les
#       ruptures modérées que l'APC manque (mesuré). Ils ne se contredisent pas.
#
#  Auteur  : ActuarIA
#  Version : 1.0.0 (2a — détection)
# =============================================================================

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import pandas as pd
    import statsmodels.api as sm
    STATSMODELS_OK = True
except ImportError:
    STATSMODELS_OK = False

logger = logging.getLogger('actuaria.a7.n3.bz_ptf')


# =============================================================================
#  CONSTANTES
# =============================================================================

SEUIL_P = 0.05                 # significativité d'une rupture
FRAC_NEG_MAX = 0.10            # au-delà → B&Z non fiable (log-normal inadapté)
N_BANDES = 3                   # bandes de développement pour σ²_d (early/mid/late)
MIN_POINTS_BANDE = 4           # sinon repli sur σ² constante
N_CANDIDATS_SCAN = 3           # nb de ruptures candidates rapportées (non injectées)
MARGE_RUPTURE = 2              # une rupture t_r doit laisser ≥ MARGE points de part et d'autre


# =============================================================================
#  DONNÉES : triangle → log-incréments observés (exclusion des ≤ 0)
# =============================================================================

def _to_long_log(C: np.ndarray) -> Dict:
    """
    Triangle cumulé → incréments observés en log.

    Cellule (i,j) observée ⟺ i+j ≤ n-1. Incrément p = C[i,j] − C[i,j-1].
    Les incréments ≤ 0 sont EXCLUS (le log ne les tolère pas), listés dans
    'cellules_exclues'. Aucun offset silencieux.
    """
    n, m = C.shape
    w, d, t, y = [], [], [], []
    exclues = []
    n_obs = 0
    for i in range(n):
        for j in range(m):
            if i + j > n - 1:
                continue
            n_obs += 1
            prev = float(C[i, j-1]) if j > 0 else 0.0
            p = float(C[i, j]) - prev
            if p <= 0 or not np.isfinite(p):
                exclues.append((i, j))
                continue
            w.append(i); d.append(j); t.append(i + j); y.append(float(np.log(p)))
    return {
        'w': np.array(w, dtype=int), 'd': np.array(d, dtype=int),
        't': np.array(t, dtype=int), 'y': np.array(y, dtype=float),
        'cellules_exclues': exclues, 'n_exclues': len(exclues), 'n_obs': n_obs,
    }


def _bandes_dev(d: np.ndarray, m: int) -> np.ndarray:
    """Assigne chaque cellule à une bande de développement (0=early..N_BANDES-1=late)."""
    bornes = [m * (b + 1) / N_BANDES for b in range(N_BANDES - 1)]
    bandes = np.zeros(len(d), dtype=int)
    for k, b in enumerate(bornes):
        bandes[d >= b] = k + 1
    return bandes


# =============================================================================
#  DESIGN : α_w (niveaux) + D(d) + K(t) hinges
# =============================================================================

def _design(
    dat: Dict, ruptures_dev: Optional[List[int]], ruptures_cal: Optional[List[int]],
) -> Tuple['pd.DataFrame', List[str], List[str]]:
    """
    Construit la matrice de design nommée. Renvoie (X, colonnes_cal, colonnes_dev_rupt).

    · Accident : niveaux libres (dummies, référence = min w).
    · Développement : niveaux libres si ruptures_dev None, sinon pente + hinges.
    · Calendaire : hinges max(0, t−t_r) UNIQUEMENT (jamais de pente constante).
    """
    w, d, t = dat['w'], dat['d'], dat['t']
    cols: Dict[str, np.ndarray] = {}

    # Accident : niveaux libres
    for wv in sorted(set(w.tolist())):
        if wv == w.min():
            continue
        cols[f'acc_{wv}'] = (w == wv).astype(float)

    # Développement
    dev_rupt_cols: List[str] = []
    if not ruptures_dev:
        for dv in sorted(set(d.tolist())):
            if dv == d.min():
                continue
            cols[f'dev_{dv}'] = (d == dv).astype(float)
    else:
        cols['dev_lin'] = d.astype(float)
        for dr in sorted(ruptures_dev):
            name = f'dev_hinge_{dr}'
            cols[name] = np.maximum(0, d - dr).astype(float)
            dev_rupt_cols.append(name)

    # Calendaire : hinges (changements) uniquement
    cal_cols: List[str] = []
    for tr in sorted(ruptures_cal or []):
        name = f'cal_t{tr}'
        cols[name] = np.maximum(0, t - tr).astype(float)
        cal_cols.append(name)

    X = pd.DataFrame(cols)
    X.insert(0, 'const', 1.0)
    return X, cal_cols, dev_rupt_cols


def _ruptures_valides(ruptures: Optional[List[int]], t: np.ndarray) -> List[int]:
    """Ne garde que les ruptures laissant assez de points de part et d'autre
    (hinge non dégénéré)."""
    if not ruptures:
        return []
    tmin, tmax = int(t.min()), int(t.max())
    ok = []
    for r in ruptures:
        r = int(r)
        n_avant = int(np.sum(t <= r))
        n_apres = int(np.sum(t > r))
        if tmin + MARGE_RUPTURE <= r <= tmax - MARGE_RUPTURE and n_avant >= MARGE_RUPTURE and n_apres >= MARGE_RUPTURE:
            ok.append(r)
        else:
            logger.warning(f"BZ-PTF : rupture t={r} ignorée (trop proche du bord / hinge dégénéré).")
    return sorted(set(ok))


def _annees_vers_index(ruptures: Optional[List[int]], annee_debut: int) -> Optional[List[int]]:
    """
    Convertit des ruptures déclarées en ANNÉES calendaires → indices de diagonale t.

    L'actuaire déclare en années réelles (ex. [2021]) : t = année − annee_debut.
    Rétro-compat : une valeur < annee_debut (petit nombre) est déjà un indice t
    et est laissée telle quelle. Sépare proprement années (≥ annee_debut ~ 2000+)
    et indices (0..n).
    """
    if not ruptures:
        return ruptures
    return [(int(v) - annee_debut if int(v) >= annee_debut else int(v)) for v in ruptures]


# =============================================================================
#  AJUSTEMENT : WLS constant + WLS bandes (IRLS)
# =============================================================================

def _fit_constante(y: np.ndarray, X: 'pd.DataFrame'):
    return sm.WLS(y, X, weights=np.ones(len(y))).fit()


def _fit_bandes(y: np.ndarray, X: 'pd.DataFrame', bandes: np.ndarray, max_iter: int = 6):
    """IRLS pour σ²_d par bande. Renvoie (modele, sigma2_par_bande) ou (None, None)
    si une bande a trop peu de points (→ repli constant géré par l'appelant)."""
    labels = sorted(set(bandes.tolist()))
    for b in labels:
        if int(np.sum(bandes == b)) < MIN_POINTS_BANDE:
            return None, None
    poids = np.ones(len(y))
    sig2_prec = None
    m = None
    for _ in range(max_iter):
        m = sm.WLS(y, X, weights=poids).fit()
        r = np.asarray(m.resid, dtype=float)
        sig2 = {b: max(float(np.mean(r[bandes == b] ** 2)), 1e-12) for b in labels}
        poids = np.array([1.0 / sig2[b] for b in bandes])
        if sig2_prec is not None and all(
            abs(sig2[b] / sig2_prec[b] - 1.0) < 1e-3 for b in labels
        ):
            sig2_prec = sig2
            break
        sig2_prec = sig2
    m = sm.WLS(y, X, weights=poids).fit()
    return m, sig2_prec


# =============================================================================
#  TESTS DE SIGNIFICATIVITÉ
# =============================================================================

def _test_bloc(modele, cols: List[str]) -> Dict:
    """Test F emboîté : toutes les colonnes de `cols` = 0 conjointement."""
    if not cols:
        return {'F': None, 'p': None, 'ddl': 0, 'significatif': False}
    try:
        ft = modele.f_test(' = 0, '.join(cols) + ' = 0')
        return {
            'F': round(float(np.ravel(ft.fvalue)[0]), 4),
            'p': round(float(ft.pvalue), 6),
            'ddl': int(ft.df_num),
            'significatif': float(ft.pvalue) < SEUIL_P,
        }
    except Exception as e:
        logger.warning(f"BZ-PTF : test F bloc échoué : {e}")
        return {'F': None, 'p': None, 'ddl': 0, 'significatif': False}


def _details_ruptures(modele, cols: List[str], annee_debut: int,
                      k_bonferroni: int, est_calendaire: bool = True) -> List[Dict]:
    """
    Détail par rupture : pente (Δ log), %/an, SE, t-stat, p (Bonferroni).
    Calendaire → champ 'annee' (int) + 'annee_label' en ANNÉES ; développement
    → 'annee'=None + label 'd=…' (période de développement, pas une année).
    """
    out = []
    for name in cols:
        idx = int(name.split('t')[-1]) if name.startswith('cal_t') else int(name.split('_')[-1])
        coef = float(modele.params[name])
        p_adj = min(1.0, float(modele.pvalues[name]) * max(k_bonferroni, 1))
        item = {
            'rupture_t':        idx,
            'delta_log':        round(coef, 4),
            'delta_pct_par_an': round((np.exp(coef) - 1.0) * 100, 2),
            'se':               round(float(modele.bse[name]), 4),
            't_stat':           round(float(modele.tvalues[name]), 3),
            'p_value':          round(p_adj, 6),
            'significatif':     p_adj < SEUIL_P,
        }
        if est_calendaire:
            item['annee'] = int(annee_debut + idx)
            item['annee_label'] = str(annee_debut + idx)
        else:
            item['annee'] = None
            item['annee_label'] = f"d={idx}"
        out.append(item)
    return out


def _scan_candidats(dat: Dict, ruptures_dev: Optional[List[int]], annee_debut: int) -> List[Dict]:
    """
    SCAN DIAGNOSTIC NON-SÉLECTIONNANT : pour chaque t_r intérieur candidat, ajuste
    le modèle (sans calendaire) + un hinge en t_r et rapporte le t-stat. RAPPORTE
    les meilleurs candidats — ne les injecte JAMAIS dans le modèle ni le statut.
    """
    y, t = dat['y'], dat['t']
    tmin, tmax = int(t.min()), int(t.max())
    Xbase, _, _ = _design(dat, ruptures_dev, None)
    scores = []
    for tr in range(tmin + MARGE_RUPTURE, tmax - MARGE_RUPTURE + 1):
        if np.sum(t <= tr) < MARGE_RUPTURE or np.sum(t > tr) < MARGE_RUPTURE:
            continue
        Xc = Xbase.copy()
        Xc[f'cal_t{tr}'] = np.maximum(0, t - tr).astype(float)
        try:
            m = sm.WLS(y, Xc, weights=np.ones(len(y))).fit()
            scores.append((tr, abs(float(m.tvalues[f'cal_t{tr}'])), float(m.pvalues[f'cal_t{tr}'])))
        except Exception:
            continue
    scores.sort(key=lambda s: s[1], reverse=True)
    return [{
        'rupture_t': tr,
        'annee': int(annee_debut + tr),
        'annee_label': str(annee_debut + tr),
        't_stat': round(tv, 3),
        'p_value_brute': round(pv, 6),   # BRUTE, non corrigée du test multiple
    } for tr, tv, pv in scores[:N_CANDIDATS_SCAN]]


# =============================================================================
#  FONCTION PRINCIPALE — 2a (DÉTECTION)
# =============================================================================

def barnett_zehnwirth_ptf(
    C                    : np.ndarray,
    ruptures_calendaires : Optional[List[int]] = None,
    ruptures_dev         : Optional[List[int]] = None,
    produire_reserve     : bool = False,
    annee_debut          : Optional[int] = None,
) -> Dict:
    """
    Barnett-Zehnwirth PTF log-normal — ÉTAPE 2a : DÉTECTION de tendances/ruptures.

    Parameters
    ----------
    C : triangle cumulé (n×n), zone future = 0.
    ruptures_calendaires : ANNÉES calendaires où une rupture de tendance
        CALENDAIRE est déclarée par l'actuaire (ex. [2021]). Converties en
        indice de diagonale t via annee_debut. Rétro-compat : une valeur
        < annee_debut est traitée comme un indice t direct. Testées (semi-manuel).
    ruptures_dev : indices de développement d où une rupture de tendance
        DÉVELOPPEMENT est déclarée. Passe D(d) en piecewise-linéaire.
    produire_reserve : réservé à 2b — SANS EFFET en 2a (aucune réserve calculée).
    annee_debut : première année calendaire (labels).

    Returns
    -------
    dict — clés : success, disponible, statut ('VERT'|'AMBRE'), message, erreur,
        calendaire_significatif, F_bloc_calendaire, p_bloc_calendaire (bandes),
        p_bloc_calendaire_constant, detection_divergente,
        ruptures_calendaires_testees[], ruptures_dev_testees[],
        ruptures_candidates_scan[], sigma_constante, sigma_par_bande,
        cellules_exclues, n_exclues, n_obs, note.
    """
    n, m = C.shape
    if annee_debut is None:
        annee_debut = 2000

    if produire_reserve:
        logger.info("BZ-PTF : produire_reserve=True ignoré (réserve = étape 2b, non implémentée).")

    if n < 5 or m < 5:
        return {'success': False, 'disponible': False, 'statut': 'VERT',
                'erreur': f"Triangle trop petit ({n}×{m}) — minimum 5×5",
                'message': "Triangle insuffisant pour le PTF log-normal."}

    if not STATSMODELS_OK:
        return {'success': False, 'disponible': False, 'statut': 'VERT',
                'erreur': "statsmodels non disponible",
                'message': "B&Z PTF indisponible (statsmodels absent)."}

    try:
        dat = _to_long_log(C)

        # ── Garde-fou incréments négatifs (log-normal inadapté) ──────────────
        frac_neg = dat['n_exclues'] / max(dat['n_obs'], 1)
        if frac_neg > FRAC_NEG_MAX:
            return {
                'success': True, 'disponible': False, 'statut': 'VERT',
                'cellules_exclues': dat['cellules_exclues'], 'n_exclues': dat['n_exclues'],
                'n_obs': dat['n_obs'],
                'message': (f"B&Z non fiable : {dat['n_exclues']}/{dat['n_obs']} incréments "
                            f"≤ 0 ({frac_neg:.0%} > {FRAC_NEG_MAX:.0%}) — le log-normal est "
                            f"structurellement inadapté aux triangles à négatifs nombreux."),
                'erreur': None,
            }

        if len(dat['y']) < max(2 * n, 12):
            return {'success': False, 'disponible': True, 'statut': 'VERT',
                    'n_exclues': dat['n_exclues'], 'n_obs': dat['n_obs'],
                    'erreur': f"Trop peu de cellules exploitables ({len(dat['y'])})",
                    'message': "Triangle insuffisant pour un ajustement PTF stable."}

        # ruptures_calendaires déclarées en ANNÉES calendaires → indices de diagonale t
        rc = _ruptures_valides(_annees_vers_index(ruptures_calendaires, annee_debut), dat['t'])
        rd = _ruptures_valides(ruptures_dev, dat['d']) if ruptures_dev else []

        X, cal_cols, dev_rupt_cols = _design(dat, rd or None, rc or None)
        bandes = _bandes_dev(dat['d'], m)

        # ── Ajustements : constant + bandes ──────────────────────────────────
        m_const = _fit_constante(dat['y'], X)
        m_band, sig2_band = _fit_bandes(dat['y'], X, bandes)
        modele = m_band if m_band is not None else m_const     # primaire
        sigma_constante = round(float(np.sqrt(m_const.scale)), 4)
        sigma_par_bande = ({int(b): round(float(np.sqrt(v)), 4) for b, v in sig2_band.items()}
                           if sig2_band else None)

        # ── Test du bloc calendaire (primaire + constant, pour divergence) ───
        bloc_prim  = _test_bloc(modele, cal_cols)
        bloc_const = _test_bloc(m_const, cal_cols)
        cal_sig = bool(bloc_prim['significatif'])
        detection_divergente = (bloc_prim['significatif'] != bloc_const['significatif'])

        # ── Détails par rupture (calendaire + dev) ───────────────────────────
        k_bonf = max(len(cal_cols), 1)
        rc_details = _details_ruptures(modele, cal_cols, annee_debut, k_bonf, est_calendaire=True)
        rd_details = _details_ruptures(modele, dev_rupt_cols, annee_debut, max(len(dev_rupt_cols), 1), est_calendaire=False)
        n_cal_sig = sum(1 for r in rc_details if r['significatif'])

        # ── Scan diagnostic (candidats NON injectés) ─────────────────────────
        scan = _scan_candidats(dat, rd or None, annee_debut)

        # ── Statut (2 niveaux, calendaire uniquement — gouvernance non câblée) ─
        statut = 'AMBRE' if cal_sig else 'VERT'

        # ── Message ──────────────────────────────────────────────────────────
        if not rc:
            base = ("Aucune rupture calendaire déclarée — modèle âge + développement "
                    "ajusté ; voir le scan pour des candidats à examiner.")
        elif cal_sig:
            det = "; ".join(f"{r['annee_label']} {r['delta_pct_par_an']:+.1f}%/an "
                            f"(p={r['p_value']:.4f})" for r in rc_details if r['significatif'])
            base = f"Rupture(s) calendaire(s) SIGNIFICATIVE(s) : {det}."
        else:
            base = (f"Rupture(s) calendaire(s) déclarée(s) NON significative(s) "
                    f"(F bloc p={bloc_prim['p']}).")
        caveat = (" ⚠ B&Z détecte les CHANGEMENTS de tendance, pas une inflation "
                  "CONSTANTE (non identifiable sur le triangle seul — VERT ne la "
                  "certifie pas absente).")
        divergence_txt = (" ⚠ Conclusion différente entre σ² constante et σ²_d par "
                          "bandes — interpréter avec prudence." if detection_divergente else "")
        message = base + caveat + divergence_txt

        return {
            'success': True, 'disponible': True,
            'statut': statut,

            # Signal calendaire (gouvernance-pertinent)
            'calendaire_significatif': cal_sig,
            'F_bloc_calendaire': bloc_prim['F'],
            'p_bloc_calendaire': bloc_prim['p'],
            'p_bloc_calendaire_constant': bloc_const['p'],
            'ddl_bloc_calendaire': bloc_prim['ddl'],
            'detection_divergente': detection_divergente,
            'n_ruptures_cal_significatives': n_cal_sig,

            # Détails ruptures + scan
            'ruptures_calendaires_testees': rc_details,
            'ruptures_dev_testees': rd_details,
            'ruptures_candidates_scan': scan,

            # Variance
            'sigma_constante': sigma_constante,
            'sigma_par_bande': sigma_par_bande,
            'variance_repli_constant': (sig2_band is None),

            # Données / exclusions
            'cellules_exclues': dat['cellules_exclues'],
            'n_exclues': dat['n_exclues'],
            'n_obs': dat['n_obs'],
            'n_utilises': len(dat['y']),

            'message': message,
            'note': (
                "Barnett-Zehnwirth PTF log-normal (2000) — ÉTAPE 2a : détection de "
                "tendances/ruptures uniquement, AUCUNE réserve ni projection. Ruptures "
                "semi-manuelles (déclarées par l'actuaire) ; le scan propose des "
                "candidats sans les sélectionner. Complète le GLM APC (test F omnibus) "
                "sans le remplacer. Mur d'identifiabilité respecté : seuls les "
                "changements de tendance calendaire sont estimés."
            ),
            'erreur': None,
        }

    except Exception as e:
        logger.error(f"Barnett-Zehnwirth PTF échoué : {e}", exc_info=True)
        return {'success': False, 'disponible': True, 'statut': 'VERT',
                'erreur': str(e), 'message': f"B&Z PTF échoué : {e}"}
