# =============================================================================
#  ActuarIA — Direction Non-Vie / Provisionnement A7 Ibrahim
#  n3/glm_apc_poisson.py  —  GLM Poisson Âge-Période-Cohorte (cross-classifié)
#
#  Référence : Renshaw & Verrall (1998) — "The stochastic model underlying the
#  chain-ladder technique", British Actuarial Journal 4(4).
#
#  ⚠️ CE N'EST PAS Barnett-Zehnwirth. Le vrai B&Z (Probabilistic Trend Family,
#     régression log-normale sur incréments) est une méthode SÉPARÉE, à venir.
#     Ce module est un GLM Poisson sur-dispersé cross-classifié (tradition ODP /
#     Renshaw-Verrall). Il remplace l'ancien n3/barnett_zehnwirth.py qui portait
#     ce nom à tort et était mal calibré (cf. audit interne 2026-07).
#
#  CE QUE FAIT CE MODULE — deux livrables distincts :
#
#    1. RÉSERVE — modèle ÂGE-COHORTE Poisson  E[Y_wd] = exp(α_w + β_d)
#       Sur les incréments Y_wd. Résultat : théorème Renshaw-Verrall (1998) —
#       la réserve MLE de ce modèle est EXACTEMENT celle du chain-ladder.
#       On la livre donc comme réserve fiable (= CL), avec CL en filet de
#       sécurité (fallback si le GLM diverge, ex. incréments négatifs).
#       Le calendaire n'entre JAMAIS dans la réserve (décision de conception) :
#       il est signalé, pas projeté.
#
#    2. TEST CALENDAIRE — F quasi-Poisson  (âge-cohorte)  vs  (âge-période-cohorte)
#       H0 : pas d'effet calendaire (γ_t = 0 ∀t).
#       F = [ (D_AC − D_APC) / Δddl ] / φ̂     avec φ̂ = dispersion de Pearson.
#       Le scaling par φ̂ est INDISPENSABLE : sur des montants (≠ comptes),
#       φ̂ ≈ 10^4–10^5, et le test LR brut (qui suppose φ=1) rejette TOUT.
#
#  LIMITES ASSUMÉES (mesurées — cf. note méthodologique) :
#    · Une inflation superposée CONSTANTE (tendance calendaire linéaire) est
#      mathématiquement NON IDENTIFIABLE sur le triangle seul (absorbée par
#      âge+cohorte). Le test en est aveugle par nécessité — VERT ne certifie
#      PAS l'absence d'inflation. La détecter exige primes/exposition (externe).
#    · Le test capte la COURBURE calendaire (chocs de diagonale, changements de
#      régime abrupts, oscillations), pas les tendances lisses modérées.
#    · Statut à 2 niveaux (VERT / AMBRE) : pas de ROUGE. L'attribution d'un
#      effet à UNE diagonale précise est peu fiable (absorption dans les coins,
#      diagonales mono-cellule bruitées) — insuffisant pour un 3e niveau.
#
#  Auteur  : ActuarIA
#  Version : 1.0.0
# =============================================================================

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

try:
    from scipy import stats as sp_stats
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

try:
    import pandas as pd
    import statsmodels.api as sm
    STATSMODELS_OK = True
except ImportError:
    STATSMODELS_OK = False

from .chain_ladder import chain_ladder

logger = logging.getLogger('actuaria.a7.n3.glm_apc')


# =============================================================================
#  CONSTANTES
# =============================================================================

# Seuil de significativité du test calendaire (F quasi-Poisson)
SEUIL_P_CALENDAIRE = 0.05

# Tolérance de validation réserve_apc vs chain-ladder (théorème Renshaw-Verrall).
# Au-delà → on retombe sur CL (filet de sécurité).
TOL_RESERVE_CL = 0.01          # 1 %

# Nombre minimal de cellules sur une diagonale pour la juger (évite le bruit
# des diagonales mono-cellule des coins — t=0, t=1).
MIN_CELLULES_DIAG = 3

# Seuil |z| pour signaler une diagonale individuelle (détail de rapport
# uniquement ; le statut vient du test F global, pas de ces flags).
SEUIL_Z_DIAG = 2.0

# Seuils d'amplitude pour qualifier le niveau d'un effet (rapport)
SEUIL_FORT   = 0.15   # 15 %
SEUIL_MODERE = 0.08   # 8 %

# Plancher pour les incréments (Poisson exige Y > 0)
FLOOR_Y = 0.5


# =============================================================================
#  CONSTRUCTION DES DONNÉES
# =============================================================================

def _to_long(C: np.ndarray) -> Dict[str, list]:
    """
    Triangle cumulé → incréments observés en format long.

    Cellule (i, j) observée ⟺ i + j ≤ n − 1 (triangle supérieur).
      w (cohorte / année de survenance)  = i
      d (développement)                  = j
      t (calendrier / diagonale)         = i + j
      Y (incrément)                      = C[i,j] − C[i,j-1]   (C[i,-1] = 0)

    Renvoie des colonnes parallèles + un drapeau incréments négatifs.
    """
    n, m = C.shape
    Y, w, d, t = [], [], [], []
    neg = False
    for i in range(n):
        for j in range(m):
            if i + j > n - 1:
                continue
            prev = float(C[i, j-1]) if j > 0 else 0.0
            inc  = float(C[i, j]) - prev
            if inc < 0:
                neg = True
            Y.append(max(inc, FLOOR_Y))
            w.append(str(i)); d.append(str(j)); t.append(str(i + j))
    return {'Y': Y, 'w': w, 'd': d, 't': t, 'incr_negatifs': neg}


def _design(cols: Dict[str, list], noms: List[str]) -> 'pd.DataFrame':
    """Matrice de design : indicatrices (drop_first) + constante."""
    df = pd.DataFrame({k: cols[k] for k in noms})
    X  = pd.get_dummies(df, columns=noms, drop_first=True).astype(float)
    return sm.add_constant(X, has_constant='add')


# =============================================================================
#  RÉSERVE — MODÈLE ÂGE-COHORTE (= CHAIN LADDER PAR MLE)
# =============================================================================

def _cl_reserve(C: np.ndarray) -> Optional[float]:
    """Réserve chain-ladder (pondération volume, sans tail) — filet & validation."""
    try:
        r = chain_ladder(C, tail_force=1.0)
        for k in ('reserve_best_estimate', 'reserve', 'reserve_totale'):
            if k in r and r[k] is not None:
                return float(r[k])
    except Exception as e:
        logger.warning(f"GLM APC : chain_ladder de référence indisponible : {e}")
    return None


def _reserve_age_cohorte(
    C: np.ndarray, cols: Dict[str, list], annee_base: int,
) -> Dict:
    """
    Ajuste le GLM Poisson âge-cohorte et projette les cellules futures.

    Théorème Renshaw-Verrall (1998) : la réserve MLE de exp(α_w + β_d) sur les
    incréments = réserve chain-ladder. On valide contre CL et on retombe sur CL
    en cas d'échec/divergence (ex. incréments négatifs).
    """
    n, m   = C.shape
    cl_ref = _cl_reserve(C)
    y      = np.array(cols['Y'], dtype=float)

    try:
        Xac = _design(cols, ['w', 'd'])
        modele = sm.GLM(y, Xac, family=sm.families.Poisson()).fit()

        # Design des cellules futures (i+j > n-1), aligné sur les colonnes de Xac
        fut_w, fut_d, idx = [], [], []
        for i in range(n):
            for j in range(m):
                if i + j > n - 1:
                    fut_w.append(str(i)); fut_d.append(str(j)); idx.append(i)
        comb = {'w': cols['w'] + fut_w, 'd': cols['d'] + fut_d}
        Xcomb = _design(comb, ['w', 'd']).reindex(columns=Xac.columns, fill_value=0.0)
        mu_fut = np.asarray(modele.predict(Xcomb.iloc[len(y):]), dtype=float)

        ibnr = np.zeros(n)
        for k, i in enumerate(idx):
            ibnr[i] += float(mu_fut[k])
        reserve = float(np.sum(ibnr[annee_base:]))

        # Validation vs chain-ladder (le théorème doit tenir)
        if cl_ref and cl_ref > 0 and abs(reserve / cl_ref - 1.0) > TOL_RESERVE_CL:
            logger.warning(
                f"GLM APC : réserve_apc={reserve:,.0f} s'écarte de CL={cl_ref:,.0f} "
                f"de {abs(reserve/cl_ref-1)*100:.1f}% (> {TOL_RESERVE_CL:.0%}) — "
                f"filet CL appliqué (cause probable : incréments négatifs)."
            )
            return {'reserve': cl_ref, 'ultimates': None, 'ibnr': None,
                    'fallback_cl': True, 'modele': modele}

        ultimates = []
        for i in range(n):
            last_j = max((j for j in range(m) if i + j <= n - 1), default=0)
            ultimates.append(round(float(C[i, last_j]) + ibnr[i], 0))
        return {'reserve': round(reserve, 0),
                'ultimates': ultimates,
                'ibnr': [round(v, 0) for v in ibnr],
                'fallback_cl': False, 'modele': modele}

    except Exception as e:
        logger.warning(f"GLM APC âge-cohorte échoué ({e}) — filet CL appliqué.")
        return {'reserve': cl_ref, 'ultimates': None, 'ibnr': None,
                'fallback_cl': True, 'modele': None}


# =============================================================================
#  TEST CALENDAIRE — F QUASI-POISSON
# =============================================================================

def _test_calendaire(cols: Dict[str, list], modele_ac) -> Dict:
    """
    Test F quasi-Poisson : âge-cohorte (H0) vs âge-période-cohorte (H1).

        F = [ (D_AC − D_APC) / Δddl ] / φ̂        φ̂ = X²_APC / (N − p_APC)
        F ~ F(Δddl, N − p_APC)   sous H0

    Δddl = nombre de paramètres calendaires IDENTIFIABLES (invariant à
    l'aliasing APC : la déviance du modèle complet est unique même si les γ_t
    ne le sont pas). On n'utilise jamais les γ_t individuels.
    """
    if not (STATSMODELS_OK and SCIPY_OK) or modele_ac is None:
        return {'disponible': False}
    try:
        y   = np.array(cols['Y'], dtype=float)
        Xapc = _design(cols, ['w', 'd', 't'])
        apc  = sm.GLM(y, Xapc, family=sm.families.Poisson()).fit()

        ddl  = int(round(modele_ac.df_resid - apc.df_resid))
        if ddl < 1:
            return {'disponible': False}
        phi  = float(apc.pearson_chi2 / apc.df_resid)
        d_ac = float(modele_ac.deviance)
        d_ap = float(apc.deviance)
        F    = ((d_ac - d_ap) / ddl) / max(phi, 1e-12)
        p    = float(1.0 - sp_stats.f.cdf(F, ddl, apc.df_resid))
        return {
            'disponible':   True,
            'F':            round(F, 4),
            'p':            round(p, 6),
            'phi':          round(phi, 2),
            'ddl':          ddl,
            'significatif': p < SEUIL_P_CALENDAIRE,
        }
    except Exception as e:
        logger.warning(f"GLM APC : test calendaire échoué : {e}")
        return {'disponible': False}


def _amplitudes_par_diagonale(
    C: np.ndarray, cols: Dict[str, list], modele_ac, annee_debut: int,
    cal_significatif: bool,
) -> List[Dict]:
    """
    Amplitude calendaire par diagonale = excès multiplicatif des incréments
    observés sur le fit âge-cohorte :  amplitude_t = mean(Y/μ̂_ac) − 1.
    Identification-invariant (résidus du modèle âge-cohorte, sans γ_t).

    Le drapeau 'significatif' par diagonale n'est qu'un DÉTAIL de rapport :
    il exige le test global significatif ET |z| > seuil ET assez de cellules.
    Le statut VERT/AMBRE vient du test F global, jamais de ces flags.
    """
    if modele_ac is None or not STATSMODELS_OK:
        return []
    try:
        y   = np.array(cols['Y'], dtype=float)
        Xac = _design(cols, ['w', 'd'])
        mu  = np.asarray(modele_ac.predict(Xac), dtype=float)
        r   = (y - mu) / np.sqrt(np.maximum(mu, 1e-9))     # résidu de Pearson
        ratio = y / np.maximum(mu, 1e-9)
        tarr  = np.array([int(x) for x in cols['t']])

        effets = []
        for tk in sorted(set(tarr.tolist())):
            sel = (tarr == tk)
            n_c = int(sel.sum())
            if n_c < MIN_CELLULES_DIAG:
                continue
            amp = (float(np.mean(ratio[sel])) - 1.0) * 100.0
            rk  = r[sel]
            z   = (float(np.mean(rk)) / (float(np.std(rk, ddof=1)) / np.sqrt(n_c))
                   if n_c >= 2 and np.std(rk, ddof=1) > 1e-9 else 0.0)
            sig = bool(cal_significatif and abs(z) > SEUIL_Z_DIAG)
            a   = abs(amp) / 100.0
            niveau = 'FORT' if a >= SEUIL_FORT else ('MODÉRÉ' if a >= SEUIL_MODERE else 'FAIBLE')
            effets.append({
                'diagonale':     tk,
                'annee_label':   str(annee_debut + tk) if annee_debut else f"Diag. {tk}",
                'amplitude_pct': round(amp, 1),
                'z_score':       round(z, 3),
                'n_points':      n_c,
                'significatif':  sig,
                'sens':          'hausse' if amp > 0 else 'baisse',
                'niveau':        niveau if sig else 'normal',
            })
        return effets
    except Exception as e:
        logger.warning(f"GLM APC : amplitudes par diagonale échouées : {e}")
        return []


# =============================================================================
#  FONCTION PRINCIPALE
# =============================================================================

def glm_apc_poisson(
    C           : np.ndarray,
    annee_debut : Optional[int] = None,
    annee_base  : int           = 1,
) -> Dict:
    """
    GLM Poisson Âge-Période-Cohorte cross-classifié (Renshaw-Verrall 1998).

    Deux livrables : (1) réserve âge-cohorte = chain-ladder par MLE (filet CL) ;
    (2) test calendaire F quasi-Poisson (statut VERT/AMBRE).

    Parameters
    ----------
    C           : triangle des paiements CUMULÉS (n × n), zone future = 0.
    annee_debut : première année calendaire (labels).
    annee_base  : première année de survenance incluse dans la réserve.

    Returns
    -------
    dict — clés principales :
        success, disponible, statut ('VERT'|'AMBRE'), message, erreur
        reserve_apc, reserve_fallback_cl, ultimates_apc, ibnr_par_annee_apc
        glm_disponible, cal_significatif, p_calendaire, F_calendaire,
        phi_dispersion, ddl_calendaire
        effets_calendaire, n_effets_significatifs, diagonales_anormales,
        n_diagonales_evaluees, recommandation, note_apc
    """
    n, m = C.shape
    if annee_debut is None:
        annee_debut = 2000

    if n < 5 or m < 5:
        return {
            'success': False, 'disponible': False,
            'statut': 'VERT',
            'erreur':  f"Triangle trop petit ({n}×{m}) — minimum 5×5",
            'message': "Triangle insuffisant pour le GLM Poisson APC.",
        }

    if not STATSMODELS_OK:
        return {
            'success': False, 'disponible': False, 'statut': 'VERT',
            'glm_disponible': False,
            'erreur':  "statsmodels non disponible",
            'message': "GLM Poisson APC indisponible (statsmodels absent).",
        }

    try:
        cols = _to_long(C)
        if len(cols['Y']) < 8:
            return {
                'success': False, 'disponible': True, 'statut': 'VERT',
                'erreur':  f"Trop peu de cellules ({len(cols['Y'])})",
                'message': "Triangle insuffisant pour l'ajustement.",
            }

        # ── 1. Réserve âge-cohorte (= CL) ────────────────────────────────────
        res = _reserve_age_cohorte(C, cols, annee_base)
        modele_ac = res['modele']

        # ── 2. Test calendaire F quasi-Poisson ───────────────────────────────
        test = _test_calendaire(cols, modele_ac)
        glm_dispo = test.get('disponible', False)
        cal_sig   = bool(test.get('significatif', False)) if glm_dispo else False

        # ── Amplitudes par diagonale (détail de rapport) ─────────────────────
        effets = _amplitudes_par_diagonale(C, cols, modele_ac, annee_debut, cal_sig)
        n_sig  = sum(1 for e in effets if e['significatif'])
        diagonales_anormales = [e['annee_label'] for e in effets if e['significatif']]

        # ── Statut : 2 niveaux (VERT / AMBRE) ────────────────────────────────
        statut = 'AMBRE' if cal_sig else 'VERT'

        # ── Recommandation ───────────────────────────────────────────────────
        if not glm_dispo:
            recommandation = ("Test calendaire indisponible — réserve = chain-ladder "
                              "(âge-cohorte). Vérifier scipy/statsmodels.")
        elif cal_sig:
            recommandation = (
                "Effet calendaire significatif détecté (courbure : choc de diagonale "
                "ou changement de régime). Retraiter en triangles 'as-if' avec une "
                "hypothèse d'inflation documentée (jugement actuariel, Guide IA 2023). "
                "La réserve livrée (= chain-ladder) ne corrige PAS cet effet."
            )
        else:
            recommandation = ("Aucun effet calendaire (courbure) significatif — "
                              "chain-ladder / âge-cohorte approprié.")

        # ── Message + caveat d'honnêteté (limites du test) ───────────────────
        if glm_dispo:
            _p = test['p']
            _p_txt = "p < 0,0001" if _p < 0.0001 else f"p = {_p:.4f}".replace('.', ',')
            base = (f"Test calendaire F quasi-Poisson : "
                    f"{'SIGNIFICATIF' if cal_sig else 'non significatif'} "
                    f"(F = {test['F']:.2f}, {_p_txt}, ddl = {test['ddl']}, "
                    f"φ = {test['phi']:,.0f}).")
        else:
            base = "Test calendaire indisponible."
        caveat = (" VERT ne certifie PAS l'absence d'inflation superposée CONSTANTE "
                  "(non identifiable sur le triangle seul — requiert primes/exposition). "
                  "Le test détecte la courbure calendaire (chocs, changements de régime), "
                  "pas les tendances lisses modérées.")
        reserve_txt = ""
        if res['reserve'] is not None:
            reserve_txt = (f" Réserve âge-cohorte = {res['reserve']:,.0f} € "
                           f"(= chain-ladder par MLE, Renshaw-Verrall 1998"
                           + (" ; filet CL appliqué" if res['fallback_cl'] else "") + ").")
        message = base + reserve_txt + caveat

        return {
            'success':    True,
            'disponible': True,

            # Réserve (= CL)
            'reserve_apc':          res['reserve'],
            'reserve_fallback_cl':  res['fallback_cl'],
            'ultimates_apc':        res['ultimates'],
            'ibnr_par_annee_apc':   res['ibnr'],
            'incr_negatifs':        cols['incr_negatifs'],

            # Test calendaire
            'glm_disponible':       glm_dispo,
            'cal_significatif':     cal_sig,
            'p_calendaire':         test.get('p'),
            'F_calendaire':         test.get('F'),
            'phi_dispersion':       test.get('phi'),
            'ddl_calendaire':       test.get('ddl'),

            # Amplitudes / détail
            'effets_calendaire':        effets,
            'n_effets_significatifs':   n_sig,
            'n_diagonales_evaluees':    len(effets),
            'diagonales_anormales':     diagonales_anormales,

            # Décision / narratif
            'statut':         statut,
            'recommandation': recommandation,
            'message':        message,
            'note_apc': (
                "Réserve par GLM Poisson âge-cohorte cross-classifié "
                "(Renshaw & Verrall 1998) — équivalente au chain-ladder par MLE. "
                "Le calendaire est signalé (test F quasi-Poisson), jamais projeté "
                "dans la réserve. Ce module n'est pas Barnett-Zehnwirth (log-normal)."
            ),
            'erreur': None,
        }

    except Exception as e:
        logger.error(f"GLM Poisson APC échoué : {e}", exc_info=True)
        return {
            'success': False, 'disponible': True, 'statut': 'VERT',
            'erreur':  str(e),
            'message': f"GLM Poisson APC échoué : {e}",
        }
