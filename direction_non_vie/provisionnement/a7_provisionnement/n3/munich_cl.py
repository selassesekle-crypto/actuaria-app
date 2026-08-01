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
#  Principe MCL — L'AJUSTEMENT EST PAR CELLULE, PAS PAR COLONNE
#  ------------------------------------------------------------
#  Chaque année de survenance reçoit son PROPRE facteur, selon SA position de
#  règlement. Une année qui a moins payé que la moyenne, relativement à ce qui
#  lui est reproché, doit rattraper : son facteur payé futur est révisé à la
#  hausse. C'est tout le mécanisme, et il ne peut pas s'exprimer par un facteur
#  unique appliqué à toutes les années.
#
#      P[i,j+1] = P[i,j] · [ f^P_j + λ_P · (σ^P_j / ρ^Q⁻¹_j) · (I[i,j]/P[i,j] − q⁻¹_j) ]
#      I[i,j+1] = I[i,j] · [ f^I_j + λ_I · (σ^I_j / ρ^Q_j)   · (P[i,j]/I[i,j] − q_j)   ]
#
#  ⚠️ LE CÔTÉ PAYÉ EST CONDITIONNÉ SUR Q⁻¹ = I/P, PAS SUR Q = P/I. Ce n'est pas
#  un détail de notation : le signe de la corrélation en dépend. Une année qui
#  paie lentement a Q bas et des facteurs payés futurs hauts — corrélation
#  NÉGATIVE en Q, POSITIVE en Q⁻¹. Mesuré sur vérité connue : −1,000 contre
#  +0,997. L'implémentation antérieure régressait sur Q puis bornait λ à [0, 2],
#  ce qui ramenait systématiquement λ_P à zéro : Munich rendait Chain Ladder à
#  la virgule près (réserve 1 775 contre 1 775, convergence +0,00 pt, sur un
#  triangle construit pour qu'il ait tout à corriger).
#
#  Formules exactes Quarg-Mack 2004
#  ----------------------------------
#
#  Facteurs et écarts-types résiduels (Mack), pour les DEUX triangles :
#
#      f^P_j     = Σ P[i,j+1] / Σ P[i,j]
#      (σ^P_j)²  = 1/(k−1) · Σ P[i,j] · (P[i,j+1]/P[i,j] − f^P_j)²
#
#  Ratios moyens et leurs écarts-types résiduels. Les pondérations ne sont pas
#  symétriques et c'est voulu : Q = P/I a une variance conditionnelle en 1/I —
#  on pondère par I ; Q⁻¹ = I/P varie en 1/P — on pondère par P.
#
#      q_j        = Σ P[i,j] / Σ I[i,j]
#      q⁻¹_j      = Σ I[i,j] / Σ P[i,j]
#      (ρ^Q_j)²   = 1/(k−1) · Σ I[i,j] · (P[i,j]/I[i,j] − q_j)²
#      (ρ^Q⁻¹_j)² = 1/(k−1) · Σ P[i,j] · (I[i,j]/P[i,j] − q⁻¹_j)²
#
#  Résidus STANDARDISÉS — sans dimension, ce qui autorise le pooling :
#
#      Res(F^P[i,j]) = (P[i,j+1]/P[i,j] − f^P_j) / σ^P_j   · √P[i,j]
#      Res(Q⁻¹[i,j]) = (I[i,j]/P[i,j]   − q⁻¹_j) / ρ^Q⁻¹_j · √P[i,j]
#
#  λ SCALAIRE, régression par l'origine sur TOUTES les paires du triangle :
#
#      λ_P = Σ Res(F^P)·Res(Q⁻¹) / Σ Res(Q⁻¹)²
#      λ_I = Σ Res(F^I)·Res(Q)   / Σ Res(Q)²
#
#  Un λ par côté, pas un par colonne : une colonne fournit 3 à 7 observations,
#  le triangle entier en fournit n(n−1)/2.
#
#  AUCUN ÉCRÊTAGE DE λ
#  -------------------
#  La standardisation lui donne une échelle : λ est une grandeur de type
#  corrélation. Mesuré sur sept jeux (vérité connue de 0 % à 20 % de bruit,
#  plus les triangles de référence) : λ ∈ [−0,856 ; +0,999], et λ ≈ corr dans
#  chaque cas. Le cap [0, 2] de l'implémentation antérieure portait sur une
#  pente BRUTE sans échelle — d'où un λ de 3,26 mesuré, écrêté à 2,0. Un λ
#  négatif est une information, pas une anomalie à taire.
#  Le seul garde-fou survivant porte sur le RÉSULTAT : si le crochet devient
#  ≤ 0 sur une cellule, cette cellule seule retombe sur f^P_j non ajusté.
#
#  Conditions d'activation
#  -----------------------
#    1. Triangle engagé fourni et de même dimension que le payé
#    2. C_E[i,j] ≥ C_P[i,j] sur la majorité des cellules (⇔ Q ≤ 1)
#    3. Assez de PAIRES exploitables pour estimer λ (cf. MCL_PAIRES_MIN)
#
#  ⚠️ La condition « au moins 4 années » a disparu, et sa disparition est une
#  conséquence directe du λ scalaire : elle se justifiait par « λ non estimable
#  avec < 4 observations », ce qui valait quand λ s'estimait COLONNE PAR
#  COLONNE. Un λ poolé s'estime sur les paires du triangle entier ; le seuil
#  porte donc désormais sur ce qui est réellement nécessaire — le nombre de
#  paires — et il est vérifié sur les données, pas déduit de la forme.
#
# =============================================================================

import logging
from typing import Dict, Optional, Tuple

import numpy as np

from direction_non_vie.services.nv_triangle_projection import (
    comptabiliser, projeter_ultimates)
# Source UNIQUE des facteurs de développement dans A7 : Munich avait sa propre
# copie, restée bloquée sur l'ancien plancher f ≥ 1 après son retrait du Lot 2.
from .chain_ladder import calculer_facteurs

logger = logging.getLogger('actuaria.a7')

#: Nombre minimal de PAIRES (i,j) exploitables pour estimer λ. Une régression
#: par l'origine sur moins de cinq points est gouvernée par n'importe laquelle
#: d'entre elles. Cinq est aussi ce que fournit exactement un triangle 4×4
#: (colonnes 0 et 1 : 3 + 2 paires), donc ce seuil préserve le comportement
#: historique sur les carrés de 4 tout en rejetant un 3×3 — qui n'en fournit
#: que 2 — pour la BONNE raison, mesurée sur les données et non déduite de n.
MCL_PAIRES_MIN = 5

#: Nombre minimal d'observations dans une colonne pour que σ_j et ρ_j soient
#: définis (variance à ddof=1).
MCL_OBS_COLONNE_MIN = 2


# =============================================================================
#  VALIDATION DES PRÉREQUIS
# =============================================================================

#: Message rendu quand tout va bien. Nommé pour que `munich_cl` distingue « rien
#: à signaler » d'une ALERTE non bloquante, sans comparer une chaîne au jugé.
MSG_PREREQUIS_OK = "Prérequis Munich CL satisfaits."


def lignes_munich_rapport(n3: Optional[Dict]) -> list:
    """Munich CL prêt à afficher — SOURCE UNIQUE des trois formats.

    HTML, Word et Excel lisent cette liste, pas le dict brut. C'est la leçon du
    lot Clark : un calcul juste qui n'atteint qu'un format n'est réparé qu'au
    tiers. Munich n'apparaissait d'ailleurs dans AUCUN des trois — ni
    `n5_rapport.py`, ni `n5_excel.py` ne le mentionnaient.

    Rend une liste de (libellé, valeur, commentaire). Valeurs déjà formatées :
    aucun consommateur n'a à décider quoi faire d'un None, et une méthode
    indisponible dit POURQUOI au lieu d'afficher zéro.
    """
    m = (n3 or {}).get('munich_cl') or {}
    if not m:
        return []
    if not m.get('disponible'):
        return [('Munich Chain Ladder', 'Non disponible',
                 str(m.get('message', 'Méthode non exécutée.')))]

    def _e(v):
        return '—' if v is None else f'{float(v):,.0f}'.replace(',', ' ') + ' €'

    def _p(v, dec=2):
        return '—' if v is None else f'{float(v):+.{dec}f}'

    lignes = [
        ('Réserve Munich — payé',    _e(m.get('be_munich_paye')),
         f"Chain Ladder payé : {_e(m.get('be_cl_paye'))}"),
        ('Réserve Munich — engagé',  _e(m.get('be_munich_engage')),
         f"Chain Ladder engagé : {_e(m.get('be_cl_engage'))}"),
        ('λ payé (Quarg & Mack)',    _p(m.get('lambda_P'), 4),
         f"estimé sur {(m.get('diagnostic_lambda') or {}).get('n_paires', '—')} "
         f"paires du triangle, non écrêté"),
        ('λ engagé',                 _p(m.get('lambda_E'), 4),
         'régression par l’origine sur résidus standardisés'),
        ('Écart des ultimes — Chain Ladder',
         '—' if m.get('ecart_cl_ultimes') is None else f"{m['ecart_cl_ultimes']:.2f} %",
         'moyenne |ultime payé − ultime engagé| / ultime engagé'),
        ('Écart des ultimes — Munich',
         '—' if m.get('ecart_mcl_ultimes') is None else f"{m['ecart_mcl_ultimes']:.2f} %",
         'ce que la méthode promet de réduire'),
        ('Convergence',              _p(m.get('convergence_pts')) + ' pts',
         'sur les ULTIMES — deux réserves ne convergent pas, '
         'elles ne partent pas de la même base'),
    ]
    if m.get('alerte_prerequis'):
        lignes.append(('⚠️ Alerte prérequis', 'Circularité suspectée',
                       str(m['alerte_prerequis'])))
    n_neg = (m.get('n_increments_negatifs_paye') or 0) + \
            (m.get('n_increments_negatifs_engage') or 0)
    if n_neg:
        lignes.append(('Incréments négatifs (zone connue)', str(n_neg),
                       'écartés de l’estimation de λ, conservés dans la projection'))
    return lignes


def _compter_increments_negatifs(C: np.ndarray) -> int:
    """Incréments négatifs de la ZONE CONNUE seulement (i + j < n).

    La zone inconnue vaut 0 : la diff entre la dernière valeur observée et ce
    zéro n'est pas un incrément, c'est le bord du triangle.
    """
    C = np.asarray(C, dtype=float)
    n, m = C.shape
    return int(sum(
        1
        for i in range(n)
        for j in range(1, min(m, n - i))
        if np.isfinite(C[i, j]) and np.isfinite(C[i, j - 1])
        and C[i, j] - C[i, j - 1] < 0
    ))


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
    # ⚠️ Le seuil « au moins 4 années » a disparu. Il se justifiait par « λ non
    # estimable avec < 4 observations », ce qui valait quand λ s'estimait
    # COLONNE PAR COLONNE. Avec un λ scalaire poolé, ce qui compte est le
    # nombre de PAIRES du triangle entier — vérifié sur les données par
    # `_calculer_lambda` (MCL_PAIRES_MIN), pas déduit de la forme ici. Ne reste
    # que la borne structurelle : sous 3 années, aucune colonne ne fournit les
    # deux observations dont σ_j et ρ_j ont besoin.
    if n < 3:
        return False, (
            f"Triangle trop petit ({n} années) — aucune colonne ne fournit "
            f"{MCL_OBS_COLONNE_MIN} observations. Munich CL désactivé."
        )

    # Vérifier que engagé ≥ payé sur la zone connue (Quarg-Mack : C_E >= C_P).
    # Le contrôle porte sur TOUTES les cellules connues, SANS garde > 0 : un
    # engagé ≤ 0 avec un payé positif est une vraie incohérence et ne doit pas
    # échapper au test. Une cellule non remplie (payé = engagé = 0) ne déclenche
    # rien (0 > 0 est faux).
    n_violations = 0
    n_connues    = 0
    for i in range(n):
        for j in range(min(m, n - i)):
            n_connues += 1
            if C_P[i, j] > C_E[i, j] * (1.0 + tolerance_ep):
                n_violations += 1

    # ⚠️ Le dénominateur est le nombre de cellules RÉELLEMENT PARCOURUES, pas
    # une approximation. L'ancien `n*m//2` sous-estimait la zone connue d'un
    # triangle carré (n²/2 au lieu de n(n+1)/2) et pouvait donc afficher plus
    # de 100 % — mesuré : « 112 % du triangle » sur un 4×4 (9 violations
    # rapportées à 8 cellules supposées, quand il y en a 10).
    pct_violations = n_violations / max(n_connues, 1)
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

    return True, MSG_PREREQUIS_OK


# =============================================================================
#  COEFFICIENTS λ  (Quarg-Mack 2004, eq. 4.2–4.3)
# =============================================================================

def _statistiques_colonne(
    C_P: np.ndarray,
    C_E: np.ndarray,
    j:   int,
) -> Optional[Dict]:
    """Facteurs, ratios et écarts-types résiduels de la colonne j.

    Tout est calculé sur l'INTERSECTION des cellules exploitables des deux
    triangles : les résidus doivent être centrés sur le facteur estimé sur les
    mêmes cellules, sinon la régression par l'origine hérite d'un biais.

    Les incréments négatifs sont écartés : la vraisemblance de Quarg & Mack
    suppose des développements croissants, et un facteur < 1 fausse à la fois
    σ_j et la corrélation. Le triangle les conserve par ailleurs — c'est
    l'estimation de λ qui les exclut, pas la projection.
    """
    n, _ = C_P.shape
    idx = [
        i for i in range(n)
        if i + j + 1 < n
        and C_P[i, j] > 0 and C_P[i, j + 1] > 0
        and C_E[i, j] > 0 and C_E[i, j + 1] > 0
        and C_P[i, j + 1] >= C_P[i, j] and C_E[i, j + 1] >= C_E[i, j]
    ]
    k = len(idx)
    if k < MCL_OBS_COLONNE_MIN:
        return None

    SP  = sum(C_P[i, j]     for i in idx)
    SP1 = sum(C_P[i, j + 1] for i in idx)
    SE  = sum(C_E[i, j]     for i in idx)
    SE1 = sum(C_E[i, j + 1] for i in idx)
    if min(SP, SP1, SE, SE1) <= 0:
        return None

    f_P = SP1 / SP
    f_E = SE1 / SE
    q     = SP / SE      # Q   = payé / engagé
    q_inv = SE / SP      # Q⁻¹ = engagé / payé

    # σ_j : dispersion résiduelle des facteurs, pondérée par le volume (Mack).
    s2_P = sum(C_P[i, j] * (C_P[i, j+1]/C_P[i, j] - f_P) ** 2 for i in idx) / (k - 1)
    s2_E = sum(C_E[i, j] * (C_E[i, j+1]/C_E[i, j] - f_E) ** 2 for i in idx) / (k - 1)
    # ρ_j : dispersion résiduelle des ratios. Pondérations ASYMÉTRIQUES —
    # Var(Q) ∝ 1/I donc poids I ; Var(Q⁻¹) ∝ 1/P donc poids P.
    r2_Q  = sum(C_E[i, j] * (C_P[i, j]/C_E[i, j] - q)     ** 2 for i in idx) / (k - 1)
    r2_Qi = sum(C_P[i, j] * (C_E[i, j]/C_P[i, j] - q_inv) ** 2 for i in idx) / (k - 1)

    if min(s2_P, s2_E, r2_Q, r2_Qi) <= 0:
        return None      # colonne dégénérée : aucun signal exploitable

    return {
        'j': j, 'idx': idx, 'k': k,
        'f_P': f_P, 'f_E': f_E, 'q': q, 'q_inv': q_inv,
        'sig_P': float(np.sqrt(s2_P)), 'sig_E': float(np.sqrt(s2_E)),
        'rho_Q': float(np.sqrt(r2_Q)), 'rho_Qi': float(np.sqrt(r2_Qi)),
    }


def _calculer_lambda(
    C_P: np.ndarray,
    C_E: np.ndarray,
) -> Tuple[Optional[float], Optional[float], Dict[int, Dict], Dict]:
    """λ_P et λ_I — SCALAIRES, poolés sur toutes les paires du triangle.

    Régression par l'origine sur résidus standardisés (Quarg & Mack 2004) :

        λ_P = Σ Res(F^P)·Res(Q⁻¹) / Σ Res(Q⁻¹)²
        λ_I = Σ Res(F^I)·Res(Q)   / Σ Res(Q)²

    ⚠️ LE CÔTÉ PAYÉ RÉGRESSE SUR Q⁻¹ = I/P. Sur Q = P/I la corrélation change
    de signe (mesuré : −1,000 contre +0,997 sur vérité connue), et un λ borné
    par le bas à zéro devient alors identiquement nul.

    AUCUN ÉCRÊTAGE : la standardisation donne à λ une échelle de corrélation
    (mesuré λ ≈ corr sur sept jeux, |λ| ≤ 0,999).

    Returns
    -------
    (lam_P, lam_E, stats_par_colonne, diagnostic)
    lam_* valent None si les paires exploitables sont trop peu nombreuses.
    """
    _, m = C_P.shape
    stats: Dict[int, Dict] = {}
    res_P: list = []      # (Res(F^P), Res(Q⁻¹))
    res_E: list = []      # (Res(F^I), Res(Q))

    for j in range(m - 1):
        st = _statistiques_colonne(C_P, C_E, j)
        if st is None:
            continue
        stats[j] = st
        for i in st['idx']:
            p, p1 = C_P[i, j], C_P[i, j + 1]
            e, e1 = C_E[i, j], C_E[i, j + 1]
            w_P, w_E = float(np.sqrt(p)), float(np.sqrt(e))
            res_P.append((
                (p1 / p - st['f_P']) / st['sig_P']  * w_P,
                (e / p - st['q_inv']) / st['rho_Qi'] * w_P,
            ))
            res_E.append((
                (e1 / e - st['f_E']) / st['sig_E'] * w_E,
                (p / e - st['q'])    / st['rho_Q'] * w_E,
            ))

    n_paires = len(res_P)
    diag = {'n_paires': n_paires, 'colonnes_exploitees': sorted(stats)}
    if n_paires < MCL_PAIRES_MIN:
        return None, None, stats, diag

    def _pente(paires):
        a = np.asarray(paires, dtype=float)
        y, x = a[:, 0], a[:, 1]
        sxx = float(np.sum(x * x))
        if sxx <= 0:
            return None, None
        pente = float(np.sum(x * y) / sxx)
        corr = (float(np.corrcoef(x, y)[0, 1])
                if np.std(x) > 0 and np.std(y) > 0 else None)
        return pente, corr

    lam_P, corr_P = _pente(res_P)
    lam_E, corr_E = _pente(res_E)
    diag['correlation_P'] = corr_P
    diag['correlation_E'] = corr_E

    # λ n'est PAS écrêté. Un |λ| > 1 signalerait un défaut de standardisation,
    # pas un triangle atypique : on le dit, on ne le corrige pas en silence.
    for nom, lam in (('λ_P', lam_P), ('λ_I', lam_E)):
        if lam is not None and abs(lam) > 1.0:
            logger.warning(
                f'Munich CL : {nom} = {lam:.4f}, |{nom}| > 1 sur résidus '
                f'standardisés — vérifier la standardisation.'
            )
    return lam_P, lam_E, stats, diag


def _projeter_conjointement(
    C_P:   np.ndarray,
    C_E:   np.ndarray,
    f_P:   np.ndarray,
    f_E:   np.ndarray,
    stats: Dict[int, Dict],
    lam_P: float,
    lam_E: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list, list]:
    """Complète les DEUX carrés, chaque triangle nourrissant l'autre.

    C'est ici que Munich CL cesse d'être Chain Ladder : le facteur appliqué
    dépend de (i,j), via le ratio OBSERVÉ de l'année i à la colonne j. Les deux
    triangles avancent ensemble parce que le pas payé a besoin de l'engagé à la
    même cellule, et réciproquement.

    `projeter_ultimates` reste intouché : il prend un VECTEUR de facteurs et
    sert Chain Ladder, Clark et le Bootstrap, qui n'ont pas ce besoin. La
    comptabilité, elle, est partagée (`comptabiliser`).
    """
    n, m = C_P.shape
    P = np.array(C_P, dtype=float, copy=True)
    E = np.array(C_E, dtype=float, copy=True)
    fc_P = np.full((n, m - 1), np.nan)
    fc_E = np.full((n, m - 1), np.nan)
    deg_P: list = []
    deg_E: list = []

    for i in range(n):
        for j in range(n - i - 1, m - 1):
            p, e = P[i, j], E[i, j]
            base_P = float(f_P[j]) if j < len(f_P) else 1.0
            base_E = float(f_E[j]) if j < len(f_E) else 1.0
            st = stats.get(j)

            if st is None or p <= 0 or e <= 0:
                # colonne sans statistique exploitable : Munich se tait et
                # laisse le facteur Chain Ladder, pour cette cellule.
                a_P, a_E = base_P, base_E
            else:
                a_P = st['f_P'] + lam_P * (st['sig_P'] / st['rho_Qi']) * (e / p - st['q_inv'])
                a_E = st['f_E'] + lam_E * (st['sig_E'] / st['rho_Q'])  * (p / e - st['q'])

            if a_P <= 0.0:
                deg_P.append([int(i), int(j), round(float(a_P), 6)])
                a_P = base_P
            if a_E <= 0.0:
                deg_E.append([int(i), int(j), round(float(a_E), 6)])
                a_E = base_E

            fc_P[i, j] = a_P
            fc_E[i, j] = a_E
            P[i, j + 1] = p * a_P
            E[i, j + 1] = e * a_E

    return P, E, fc_P, fc_E, deg_P, deg_E


# =============================================================================
#  MUNICH CHAIN LADDER — FONCTION PRINCIPALE
# =============================================================================

def munich_cl(
    C_P:          np.ndarray,
    C_E:          Optional[np.ndarray],
    annee_base:   int   = 1,
    tolerance_ep: float = 0.05,
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
            'alerte_prerequis': msg_prereq,
            'methode':    'Munich Chain Ladder (Quarg & Mack 2004)',
        }

    # ⚠️ L'ALERTE NON BLOQUANTE ÉTAIT PERDUE. Entre CV 0,02 et 0,05, la
    # détection de circularité rend `(True, message d'alerte)` — un doute
    # sérieux sur l'indépendance des charges dossier vis-à-vis des provisions.
    # `msg_prereq` n'était ensuite jamais relu quand ok=True : l'avertissement
    # ne figurait NULLE PART dans la sortie. Mesuré à CV = 0,0275 / 0,0366 /
    # 0,0458 : trois fois muet. Il est désormais publié et joint au message.
    alerte_prerequis = None if msg_prereq == MSG_PREREQUIS_OK else msg_prereq
    if alerte_prerequis:
        logger.warning(f"Munich CL — alerte prérequis : {alerte_prerequis}")

    n, m = C_P.shape

    # ── 2. Facteurs CL standard ───────────────────────────────────────────────
    # Source unique (chain_ladder, Lot C1) : un facteur < 1 (recours/subrogation)
    # est conservé tel quel. Il se propage aux λ, aux ratios prédits q̂, aux
    # facteurs ajustés f* (verrou 1.0 retiré au Lot C2) et jusqu'à l'IBNR brut
    # (plancher retiré au Lot C3) — plus aucun plancher n'écrase les reprises.
    f_P, _ = calculer_facteurs(C_P)
    f_E, _ = calculer_facteurs(C_E)

    # ── 3. Coefficients λ — SCALAIRES, poolés (Quarg-Mack 2004) ──────────────
    lam_P, lam_E, stats_col, diag_lam = _calculer_lambda(C_P, C_E)
    if lam_P is None or lam_E is None:
        msg = (
            f"λ non estimable — {diag_lam['n_paires']} paire(s) exploitable(s) "
            f"pour un minimum de {MCL_PAIRES_MIN}. Munich CL désactivé."
        )
        logger.info(f"Munich CL désactivé : {msg}")
        return {
            'disponible': False,
            'statut':     'INFO',
            'message':    msg,
            'methode':    'Munich Chain Ladder (Quarg & Mack 2004)',
            'diagnostic_lambda': diag_lam,
        }

    # ── 4. Projection CONJOINTE, facteur par cellule ─────────────────────────
    P_proj, E_proj, fc_P, fc_E, facteurs_degeneres_paye, facteurs_degeneres_engage = (
        _projeter_conjointement(C_P, C_E, f_P, f_E, stats_col, lam_P, lam_E))

    # Facteur de colonne IMPLICITE, reconstruit depuis le carré projeté :
    # Σ_i P*[i,j+1] / Σ_i P*[i,j]. C'est la seule lecture « par colonne » qui
    # ait un sens quand l'ajustement est par cellule — et elle reste comparable
    # au facteur Chain Ladder affiché à côté.
    f_star_P = np.array([
        (float(np.sum(P_proj[:, j + 1])) / float(np.sum(P_proj[:, j])))
        if float(np.sum(P_proj[:, j])) > 0 else float(f_P[j])
        for j in range(m - 1)
    ])
    f_star_E = np.array([
        (float(np.sum(E_proj[:, j + 1])) / float(np.sum(E_proj[:, j])))
        if float(np.sum(E_proj[:, j])) > 0 else float(f_E[j])
        for j in range(m - 1)
    ])

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

    # ── 5. Projections MCL et CL — IBNR BRUT (Lot C3 : dernier plancher retiré) ─
    # Les trois verrous IBNR de Munich sont désormais tous levés : facteurs libres
    # (verrou 1, Lot C1) → f* libre (verrou 2, Lot C2) → IBNR brut (verrou 3, ce
    # lot). La chaîne reflète pleinement les reprises (recours/subrogation) ; les
    # années en reprise ne sont plus écrasées à 0. Le helper calcule aussi l'IBNR
    # plancheré, conservé pour mesurer l'écart vs l'ancien comportement.
    # Munich : ultimes issus de la projection CONJOINTE, comptabilisés par le
    # helper partagé — une seule définition de « réserve » dans A7.
    _last = np.array([float(C_P[i, min(n - i - 1, m - 1)]) for i in range(n)])
    _lastE = np.array([float(C_E[i, min(n - i - 1, m - 1)]) for i in range(n)])
    p_mp = comptabiliser(P_proj[:, m - 1], _last,  annee_base=annee_base)
    p_me = comptabiliser(E_proj[:, m - 1], _lastE, annee_base=annee_base)
    # Chain Ladder de référence : projection classique par vecteur de facteurs.
    p_cp = projeter_ultimates(C_P, f_P,      tail_factor=1.0, annee_base=annee_base)
    p_ce = projeter_ultimates(C_E, f_E,      tail_factor=1.0, annee_base=annee_base)

    ibnr_mp = p_mp['ibnr_brut']
    ibnr_me = p_me['ibnr_brut']

    # Réserves BRUTES (recours nets compris) — chiffre de référence honnête.
    # CL de référence (R_cp, R_ce) aussi en brut : l'écart % compare brut vs brut.
    R_mp = p_mp['reserve_brute']
    R_me = p_me['reserve_brute']
    R_cp = p_cp['reserve_brute']
    R_ce = p_ce['reserve_brute']

    # Signalement des reprises — même schéma que chain_ladder (Lot B).
    n_reprise_P      = p_mp['n_annees_reprise']
    n_reprise_E      = p_me['n_annees_reprise']
    reserve_planch_P = p_mp['reserve_plancher']
    reserve_planch_E = p_me['reserve_plancher']
    ecart_planch_P   = reserve_planch_P - R_mp   # ≥ 0 : ce que le plancher masquait
    ecart_planch_E   = reserve_planch_E - R_me

    ecart_P = (R_mp - R_cp) / max(R_cp, 1e-9) * 100.0
    ecart_E = (R_me - R_ce) / max(R_ce, 1e-9) * 100.0

    # ── Convergence — SUR LES ULTIMES, pas sur les réserves ───────────────────
    # ⚠️ Deux réserves ne peuvent PAS converger : celle du payé se mesure depuis
    # le payé-à-date, celle de l'engagé depuis l'engagé-à-date. Ce sont deux
    # bases différentes, l'écart entre elles subsiste même quand les ultimes
    # coïncident parfaitement. Ce que Quarg & Mack rapprochent, ce sont les
    # ULTIMES — deux estimations de la MÊME quantité.
    # Mesuré sur vérité connue : l'écart des ultimes tombe de 9,29 % à 1,98 %
    # (convergence +7,31 pts) là où l'ancienne métrique sur réserves annonçait
    # −9,67 pts, soit le signe opposé à la réalité.
    def _ecart_ultimes(u_p: np.ndarray, u_e: np.ndarray) -> float:
        idx = max(0, min(int(annee_base), n - 1))
        a, b = np.asarray(u_p)[idx:], np.asarray(u_e)[idx:]
        ok_i = np.abs(b) > 1e-9
        if not ok_i.any():
            return 0.0
        return float(np.mean(np.abs(a[ok_i] - b[ok_i]) / np.abs(b[ok_i]))) * 100.0

    ecart_cl_ult  = _ecart_ultimes(p_cp['ultimate'], p_ce['ultimate'])
    ecart_mcl_ult = _ecart_ultimes(p_mp['ultimate'], p_me['ultimate'])
    convergence   = ecart_cl_ult - ecart_mcl_ult   # > 0 = MCL rapproche

    # Écarts de RÉSERVES, conservés à titre descriptif — bases différentes,
    # à ne pas lire comme une convergence.
    ecart_cl  = abs(R_cp - R_ce) / max(abs(R_cp), 1e-9) * 100.0
    ecart_mcl = abs(R_mp - R_me) / max(abs(R_mp), 1e-9) * 100.0

    # ── Statut : la méthode tient-elle SA PROPRE promesse ? ───────────────────
    # L'ancien statut jugeait l'écart Munich/Chain-Ladder : plus Munich
    # s'écartait de CL, plus il était rouge. C'est l'inverse du sens — s'écarter
    # de CL est sa raison d'être. Sur vérité connue, Munich 3,6 fois plus juste
    # que CL ressortait ROUGE. Le statut porte désormais sur la convergence des
    # ultimes, c'est-à-dire sur ce que Quarg & Mack promettent.
    if convergence > 1.0:
        statut = 'VERT'
    elif convergence >= -1.0:
        statut = 'AMBRE'
    else:
        statut = 'ROUGE'

    msg = (
        f"Munich CL : payé_MCL={R_mp:,.0f}€ "
        f"({'+' if ecart_P >= 0 else ''}{ecart_P:.1f}% vs CL payé) · "
        f"engagé_MCL={R_me:,.0f}€ · "
        f"λ_P={lam_P:+.3f} λ_I={lam_E:+.3f} sur {diag_lam['n_paires']} paires · "
        f"écart des ultimes {ecart_cl_ult:.1f}% → {ecart_mcl_ult:.1f}% "
        f"(convergence {convergence:+.1f} pts)"
    )
    if facteurs_munich_sous_1_paye or facteurs_munich_sous_1_engage:
        msg += (
            f" | ⚠️ f* < 1.0 conservé(s) (recours) — colonnes payé "
            f"{[j for j, _ in facteurs_munich_sous_1_paye]}, engagé "
            f"{[j for j, _ in facteurs_munich_sous_1_engage]}"
        )
    if n_reprise_P or n_reprise_E:
        msg += (
            f" | ⚠️ payé {n_reprise_P} année(s) en reprise (écart "
            f"{ecart_planch_P:,.0f}€ vs plancher), engagé {n_reprise_E} "
            f"année(s) (écart {ecart_planch_E:,.0f}€)"
        )
    if alerte_prerequis:
        msg += f" | {alerte_prerequis}"
    logger.info(msg)

    # Compter les incréments négatifs (P et E) pour audit — SUR LA ZONE CONNUE.
    # ⚠️ L'ancien comptage faisait `np.diff` sur TOUT le tableau : le passage de
    # la dernière valeur connue au zéro de la zone inconnue fabriquait un
    # « incrément négatif » par ligne. Mesuré : 3 fictifs sur les triangles 4×4
    # de référence, 6 sur le 7×7, soit un compte gonflé de moitié à 100 %.
    n_neg_P = _compter_increments_negatifs(C_P)
    n_neg_E = _compter_increments_negatifs(C_E)
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
        # Écarts de RÉSERVES — descriptifs. Bases différentes (payé-à-date vs
        # engagé-à-date) : ne PAS les lire comme une convergence.
        'ecart_cl_paye_engage': round(ecart_cl,  2),
        'ecart_mcl_paye_engage': round(ecart_mcl, 2),
        # Écarts d'ULTIMES — deux estimations de la MÊME quantité. C'est là que
        # la convergence se mesure, et ce que `convergence_pts` rapporte.
        'ecart_cl_ultimes':   round(ecart_cl_ult,  2),
        'ecart_mcl_ultimes':  round(ecart_mcl_ult, 2),
        'convergence_pts':    round(convergence,  2),

        # Coefficients λ — SCALAIRES depuis la reconstruction (un par côté,
        # poolé sur toutes les paires), plus jamais un vecteur par colonne.
        'lambda_P':           round(float(lam_P), 4),
        'lambda_E':           round(float(lam_E), 4),
        'diagnostic_lambda':  diag_lam,

        # Facteur appliqué à CHAQUE cellule (n, m-1) — le cœur de Munich CL.
        # NaN sur la zone déjà connue, qui n'est pas projetée.
        'facteurs_munich_paye_cellule':   [
            [None if np.isnan(v) else round(float(v), 6) for v in ligne]
            for ligne in fc_P],
        'facteurs_munich_engage_cellule': [
            [None if np.isnan(v) else round(float(v), 6) for v in ligne]
            for ligne in fc_E],

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

        # IBNR par année (BRUT depuis le Lot C3 — recours conservés, peut être < 0)
        'ibnr_munich_paye':   [round(float(v), 2) for v in ibnr_mp],
        'ibnr_munich_engage': [round(float(v), 2) for v in ibnr_me],

        # Reprises (recours/subrogation) — schéma chain_ladder (Lot B)
        'ibnr_brut_par_annee_paye':   [round(float(v), 2) for v in p_mp['ibnr_brut']],
        'ibnr_brut_par_annee_engage': [round(float(v), 2) for v in p_me['ibnr_brut']],
        'n_annees_reprise_paye':   n_reprise_P,
        'n_annees_reprise_engage': n_reprise_E,
        'reserve_brute_paye':      round(R_mp, 2),
        'reserve_brute_engage':    round(R_me, 2),
        'reserve_plancher_paye':   round(reserve_planch_P, 2),
        'reserve_plancher_engage': round(reserve_planch_E, 2),

        # Métadonnées
        'statut':    statut,
        # Alerte de prérequis NON BLOQUANTE (circularité suspectée) — None quand
        # tout va bien. Autrefois calculée puis jetée.
        'alerte_prerequis': alerte_prerequis,
        'methode':   'Munich Chain Ladder (Quarg & Mack 2004)',
        'message':   msg,
        'conseil': (
            "Munich rapproche nettement les ultimes payé et engagé : la "
            "corrélation entre règlement et charge dossier porte de "
            "l'information que Chain Ladder ignore."
            if convergence > 1.0 else
            "Munich ne déplace presque pas les ultimes : payé et engagé se "
            "développent déjà de façon cohérente, Chain Ladder suffit."
            if convergence >= -1.0 else
            "Munich ÉLOIGNE les ultimes payé et engagé — vérifier la cohérence "
            "du triangle engagé avant d'exploiter ce résultat."
        ),
    }