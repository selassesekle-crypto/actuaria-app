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
#  Oracle externe
#  --------------
#  Institut des Actuaires (2023), §3.c p28-30 — exemple Bootstrap ENTIÈREMENT
#  CHIFFRÉ sur le triangle RAA, 10 000 simulations (figure 30) :
#      moyenne 53 428 · médiane 52 091 · écart-type 13 923
#      min 17 705 · max 118 008 · q5 32 945 · q25 43 419
#      q75 61 940 · q95 78 150 · q99 91 898
#  Reproduit par les tests de ce module, au même titre que l'exemple
#  Bornhuetter-Ferguson de la figure 19. Deux affirmations du guide y sont
#  vérifiables : « la médiane est très proche de la réserve Chain Ladder » et
#  « la moyenne n'en est pas très différente AVANT tout retraitement de
#  recentrage » — mesuré +2,48 % sur son propre exemple.
#
#  ⚠️ σ DU GUIDE 13 923 CONTRE σ DE MACK 26 909 SUR LE MÊME TRIANGLE — ce n'est
#  pas une contradiction, et l'hypothèse la plus tentante est FAUSSE. On pourrait
#  croire que le bootstrap du guide mesure l'erreur de PARAMÈTRE seule ; la
#  mesure dit l'inverse. C'est notre σ TOTAL qui approche le sien (14 668, soit
#  +5,4 %), là où notre erreur de paramètre seule vaut 9 896, à −28,9 %. Le
#  bootstrap du guide inclut donc bien le bruit de processus, et son écart à
#  Mack tient à ce que les deux modèles ne sont pas le même — l'un sur-dispersé
#  de Poisson, l'autre sans loi. Les deux composantes sont publiées
#  (`std_parametre`, `std_processus`) pour que cette question se tranche par la
#  mesure et non par l'intuition : sans elles, un σ 2,4 fois trop grand est resté
#  invisible jusqu'à l'audit modèle de ce lot.
#
#  Correction du lot « audit modèle Bootstrap »
#  --------------------------------------------
#  DÉFAUT RACINE CORRIGÉ : les valeurs ajustées étaient calculées VERS L'AVANT,
#  `Ĉ[i,j] = C[i,j−1] × f̂_j`, à partir du cumulé OBSERVÉ en amont. C'est la
#  prédiction à un pas du modèle de MACK — la base de SES résidus — et non
#  l'ajustement croisé sur-dispersé de Poisson d'England & Verrall. Preuve : un
#  ajustement E&V reproduit exactement la diagonale observée, celui-ci s'en
#  écartait de +51 %, −44 %, +32 % sur les premières années de RAA.
#
#  Quatre conséquences, toutes issues de cette seule racine, corrigées avec elle :
#    · la colonne 0 ne pouvait pas entrer dans le vivier (résidu nul par
#      construction) → 18 % des incréments hors du rééchantillonnage ;
#    · N = 45 au lieu de 55 pour p = 19 → df = 26 au lieu de 36, facteur
#      d'ajustement surélevé de 6,4 % ;
#    · φ = 5 722,8 au lieu de 983,6 sur RAA (5,82×) et 103 872 au lieu de
#      52 601 sur GenIns (1,97×) ;
#    · le biais AVANT recentrage atteignait +79,4 % sur RAA — le guide en
#      mesure +2,5 % — parce qu'un φ démesuré faisait mordre les gardes
#      d'incrément sur un tiers des tirages.
#
#  Correction v5.0 vs v4.0 (antérieure)
#  ------------------------------------
#  En v4.0 : perturbation des facteurs individuels par colonne →
#    NON conforme England-Verrall 2002, sous-estime la variance en queue.
#  En v5.0 : résidus de Pearson sur les incréments → conforme.
#
#  Algorithme England-Verrall 2002
#  --------------------------------
#
#  Étape 1 — Triangle ajusté, par RÉCURSION ARRIÈRE
#  ─────────────────────────────────────────────────
#      Ĉ[i, k_i] = C[i, k_i]        (k_i = dernière colonne connue)
#      Ĉ[i, j−1] = Ĉ[i, j] / f̂_j    pour j = k_i … 1
#  puis les incréments ajustés  m̂_ij = Ĉ[i,j] − Ĉ[i,j−1],  m̂_i0 = Ĉ[i,0].
#  Le triangle ajusté reproduit alors EXACTEMENT la diagonale observée.
#
#  Étape 2 — Résidus de Pearson, sur les incréments, colonne 0 comprise
#  ─────────────────────────────────────────────────────────────────────
#      r_ij = (m_ij − m̂_ij) / sqrt(m̂_ij)
#
#  Ajustement des degrés de liberté (England-Verrall 2002, eq. 3.7) :
#      r_ij_adj = r_ij × sqrt(N / (N − p))
#  où  N = nombre d'incréments ajustés strictement positifs (zone connue)
#      p = n + m − 1   (paramètres du modèle croisé α_j × β_i)
#
#  Étape 3 — Facteur de sur-dispersion φ
#  ───────────────────────────────────────
#      φ = Σ r²_ij / (N − p)        sur les résidus BRUTS
#
#  Étape 4 — Simulation Bootstrap (N itérations)
#  ───────────────────────────────────────────────
#  Pour chaque simulation b = 1..N :
#    a. rééchantillonner les résidus ajustés avec remise, UN TIRAGE PAR CELLULE
#       RETENUE ;
#    b. pseudo-triangle par les incréments :
#       m*_ij = m̂_ij + r*_ij × sqrt(m̂_ij),  garde ODP : m*_ij ≥ m̂_ij × 0.01,
#       puis C* = cumul(m*) ;
#    c. refit des facteurs sur le pseudo-triangle : f*_j = Σ C*[i,j+1] / Σ C*[i,j] ;
#    d. projection depuis la diagonale RÉELLE, avec bruit de processus sur
#       l'incrément : Var(inc) = φ × inc,  approximation normale ;
#    e. réserve simulée R*_b, ET la même sans bruit de processus — les deux
#       étant appariées, leur différence isole la part de processus.
#
#  Étape 5 — Distribution, recentrage et percentiles
#  ───────────────────────────────────────────────────
#  Recentrage par TRANSLATION sur la réserve Chain Ladder — la première des deux
#  formes que le guide décrit (§3.c.i p29), celle qui laisse l'écart-type
#  inchangé. Puis :
#    BE_boot  = moyenne(R*_b)  ( = réserve CL, par construction du recentrage)
#    σ_boot   = écart-type(R*_b)
#    P_α      = percentile α de {R*_b}
#
# =============================================================================

import logging
from typing import Dict, Optional

import numpy as np

from direction_non_vie.services.nv_triangle_negatifs import increments_positifs
from direction_non_vie.services.nv_triangle_projection import projeter_ultimates

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  FITTED VALUES ET RÉSIDUS DE PEARSON
# =============================================================================

def ajuster_triangle(C: np.ndarray, facteurs: np.ndarray) -> np.ndarray:
    """Triangle cumulé AJUSTÉ, par récursion ARRIÈRE depuis la dernière diagonale.

        Ĉ[i, k_i] = C[i, k_i]              (k_i = dernière colonne connue)
        Ĉ[i, j−1] = Ĉ[i, j] / f̂_j          pour j = k_i … 1

    ⚠️ LE SENS DE LA RÉCURSION N'EST PAS UN DÉTAIL D'IMPLÉMENTATION. Celle-ci
    descend depuis la diagonale OBSERVÉE. La version précédente remontait vers
    l'avant — `Ĉ[i,j] = C[i,j−1] × f̂_j`, en s'appuyant sur le cumulé OBSERVÉ en
    amont : c'est la prédiction à un pas du modèle de MACK, base de SES résidus,
    et non l'ajustement croisé sur-dispersé de Poisson d'England & Verrall dont
    le Bootstrap ODP a besoin.

    LA PROPRIÉTÉ QUI LES SÉPARE SE VÉRIFIE EN UNE LIGNE : l'ajustement E&V
    reproduit exactement la diagonale observée, donc la somme de ses incréments
    ajustés égale le cumulé observé, ligne par ligne. Mesuré sur RAA, la forme
    avant s'en écartait de +51,2 %, −44,4 %, +11,6 %, +32,4 % et −22,5 % sur les
    cinq premières années — un triangle « ajusté » qui contredit de moitié les
    données qu'il ajuste.
    """
    n, m   = C.shape
    ajuste = np.zeros((n, m))
    for i in range(n):
        k = min(n - i - 1, m - 1)
        ajuste[i, k] = C[i, k]
        for j in range(k, 0, -1):
            f = float(facteurs[j - 1]) if j - 1 < len(facteurs) else 1.0
            ajuste[i, j - 1] = ajuste[i, j] / f if f > 0 else 0.0
    return ajuste


def calculer_fitted_et_residus(
    C:        np.ndarray,
    facteurs: np.ndarray,
) -> tuple:
    """
    Incréments ajustés du modèle ODP et résidus de Pearson (England & Verrall).

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé. Zone connue : i+j < n.
    facteurs : np.ndarray  shape (m-1,)
        Facteurs CL agrégés (volume-weighted standard).

    Returns
    -------
    m_fit : np.ndarray  shape (n, m)
        INCRÉMENTS ajustés — et non plus le cumulé ajusté. C'est la grandeur que
        le pseudo-triangle perturbe ; la rendre directement évite à l'appelant de
        la reconstruire par différence, et lui évite surtout de la reconstruire
        AUTREMENT que le calcul des résidus ne l'a fait.
    residus : np.ndarray  shape (n, m)
        Résidus de Pearson AJUSTÉS des degrés de liberté.
    phi : float
        Sur-dispersion φ = Σ r²_bruts / df.
    residus_list : list
        Vivier plat pour le rééchantillonnage.
    n_obs : int
        Nombre d'incréments retenus — COLONNE 0 COMPRISE.
    n_params : int
        n + m − 1 : paramètres du modèle croisé.

    ⚠️ LA COLONNE 0 EST DANS LE VIVIER, et ce n'est pas un ajout gratuit. Dans le
    modèle ODP, `m_i0 = C[i,0]` est une observation comme les autres. L'ancienne
    version ne POUVAIT pas l'inclure : avec l'ajustement avant, `Ĉ[i,0] = C[i,0]`
    par construction, donc résidu identiquement nul. Dix des cinquante-cinq
    incréments de GenIns comme de RAA — 18 % des données — quittaient ainsi le
    rééchantillonnage, tandis que `n_params = n + m − 1` restait, lui, le compte
    du modèle COMPLET. D'où des degrés de liberté de 26 au lieu de 36, un facteur
    d'ajustement surélevé de 6,4 %, et un φ divisé par le mauvais dénominateur.
    """
    n, m    = C.shape
    ajuste  = ajuster_triangle(C, facteurs)
    m_fit   = np.zeros((n, m))
    residus = np.zeros((n, m))
    bruts   = np.zeros((n, m))

    # ── Incréments ajustés et observés, COLONNE 0 COMPRISE ────────────────────
    cellules = []
    for i in range(n):
        k = min(n - i - 1, m - 1)
        for j in range(0, k + 1):
            m_fit[i, j] = ajuste[i, j] - (ajuste[i, j - 1] if j > 0 else 0.0)
            if m_fit[i, j] <= 0:
                continue          # incrément ajusté ≤ 0 → hors du modèle ODP
            m_obs = C[i, j] - (C[i, j - 1] if j > 0 else 0.0)
            bruts[i, j] = (m_obs - m_fit[i, j]) / np.sqrt(m_fit[i, j])
            cellules.append((i, j))

    n_obs    = len(cellules)
    n_params = n + m - 1
    df       = n_obs - n_params

    # ── φ et ajustement des degrés de liberté (E&V 2002, eq. 3.7) ────────────
    # φ se calcule sur les résidus BRUTS ; l'ajustement ne sert qu'au
    # rééchantillonnage. Les deux jeux coexistent donc, au lieu d'être calculés,
    # écrasés par l'ajustement en place, puis RECALCULÉS pour φ — ce que faisait
    # la version précédente, trois passes pour deux grandeurs.
    somme_carres = float(sum(bruts[i, j] ** 2 for (i, j) in cellules))
    phi = somme_carres / max(df, 1)

    if df > 0:
        adj = float(np.sqrt(n_obs / df))
    else:
        adj = 1.0
        logger.warning(
            f"Bootstrap ODP : degrés de liberté df={df} ≤ 0 "
            f"(n_obs={n_obs}, n_params={n_params}) — ajustement désactivé. "
            f"Triangle trop petit pour un Bootstrap fiable."
        )
    for (i, j) in cellules:
        residus[i, j] = bruts[i, j] * adj

    # ⚠️ AUCUN FILTRE SUR LA VALEUR DU RÉSIDU. Un résidu exactement nul est une
    # observation légitime — l'ajustement y est parfait. Le `!= 0` précédent
    # écartait donc du vivier une observation au motif qu'elle était bien ajustée.
    residus_list = [residus[i, j] for (i, j) in cellules]

    return m_fit, residus, phi, residus_list, n_obs, n_params, tuple(cellules)


# =============================================================================
#  BOOTSTRAP ODP — FONCTION PRINCIPALE
def _simuler(
    C:          np.ndarray,
    m_fit:      np.ndarray,
    cellules:   tuple,
    res_arr:    np.ndarray,
    phi:        float,
    last_diag:  np.ndarray,
    n_sim:      int,
    annee_base: int,
) -> tuple:
    """Les `n_sim` réserves simulées, AVEC et SANS bruit de processus.

    Extraite de `bootstrap_odp` pour la ramener sous la taille que ce module
    s'impose : l'orchestration, la boucle chaude et la mise en forme du résultat
    sont trois choses distinctes, et seule la deuxième est longue.

    Renvoie `(totales, parametre_seul)` — deux vecteurs APPARIÉS : même
    pseudo-triangle, mêmes facteurs refités, la seule différence étant le bruit
    ajouté. C'est cet appariement qui permet de décomposer σ sans lancer une
    seconde campagne, qui n'aurait pas partagé les mêmes tirages.
    """
    n, m  = C.shape
    n_cel = len(cellules)
    reserves_sim = np.zeros(n_sim)   # erreur totale
    reserves_par = np.zeros(n_sim)   # erreur de paramètre seule

    for b in range(n_sim):

        # ── a. Rééchantillonner les résidus avec remise ───────────────────────
        # Un tirage PAR CELLULE RETENUE, et non sur toute la matrice (n, m) :
        # l'ancienne version en tirait 100 pour n'en consommer que 45 sur les
        # triangles de référence — 55 % de tirages jetés à chaque simulation.
        res_boot = res_arr[np.random.randint(0, len(res_arr), size=n_cel)]

        # ── b. Pseudo-triangle par les INCRÉMENTS, puis re-cumul ──────────────
        # E&V 2002 : m* = m̂ + r* × sqrt(m̂). `m_fit` vient DIRECTEMENT de
        # l'ajustement E&V : il n'est plus reconstruit ici par différence, donc
        # l'incrément perturbé est exactement celui dont le résidu a été tiré.
        M_star = np.zeros((n, m))
        for t, (i, j) in enumerate(cellules):
            mf = m_fit[i, j]
            M_star[i, j] = max(
                mf + res_boot[t] * np.sqrt(mf),
                mf * 0.01,                      # garde-fou : incrément > 0
            )
        C_star = np.cumsum(M_star, axis=1)

        # ── c. Facteurs CL sur le pseudo-triangle ─────────────────────────────
        # f*_j = Σ C*[i,j+1] / Σ C*[i,j]  (volume-weighted). Copie inline
        # VOLONTAIRE : la source partagée `calculer_facteurs` coûte +54 % dans
        # cette boucle chaude (elle construit les facteurs individuels) pour un
        # gain nul — mesuré. PAS de plancher f* ≥ 1 : le pseudo-triangle est
        # monotone croissant par construction (incréments planchés > 0 en b),
        # donc num ≥ den. L'ancien `max(…, 1.0)` était mort — 0 sur 24 000
        # simulations — et a été retiré au Lot D2.
        f_star = np.ones(m - 1)
        for j in range(m - 1):
            num = den = 0.0
            for i in range(n):
                if i + j + 1 < n and C_star[i, j] > 0 and C_star[i, j + 1] > 0:
                    num += C_star[i, j + 1]
                    den += C_star[i, j]
            f_star[j] = num / max(den, 1e-10)

        # ── d. Projection depuis la diagonale RÉELLE ──────────────────────────
        # E&V 2002 : l'incrément futur suit ODP(mean, φ) avec
        #   mean = C_proj[i,j−1] × (f*_j − 1)     (l'incrément, pas le cumulé)
        #   Var  = φ × mean                        (approximation normale)
        reserve_b = 0.0    # avec bruit de processus
        reserve_p = 0.0    # sans — erreur de paramètre seule
        for i in range(annee_base, n):
            k_i   = min(n - i - 1, m - 1)
            c_val = float(C[i, k_i])
            c_par = float(C[i, k_i])

            for j in range(k_i, m - 1):
                if j >= len(f_star):
                    continue
                inc_mean = c_val * (f_star[j] - 1.0)
                # ⚠️ GARDE D'INCRÉMENT ODP — À NE JAMAIS RETIRER, ≠ verrou
                # recours. Le bruit Normal(0, √(φ·inc)) peut rendre l'incrément
                # négatif, ce qui est IMPOSSIBLE pour un ODP (loi ≥ 0). Le
                # plancher tronque cette queue gauche pour respecter la
                # non-négativité du MODÈLE. Ce n'est PAS un masque de recours :
                # les cellules à incrément ajusté ≤ 0 sont déjà exclues en amont
                # par `calculer_fitted_et_residus`. Idem au point b.
                if phi > 0 and inc_mean > 0:
                    std_proc = np.sqrt(phi * inc_mean)
                    inc_sim  = max(
                        inc_mean + np.random.normal(0, std_proc),
                        inc_mean * 0.01,
                    )
                else:
                    inc_sim = max(inc_mean, 0.0)
                c_val = c_val + inc_sim
                c_par = c_par * f_star[j]       # même f*, aucun bruit ajouté

            # PAS de plancher IBNR ≥ 0 : la garde d'incrément rend `c_val`
            # monotone croissant, donc c_val ≥ last_diag[i] par construction.
            # L'ancien `max(…, 0.0)` était mort — 0 sur 24 000 simulations —
            # et a été retiré au Lot D2.
            reserve_b += c_val - last_diag[i]
            reserve_p += c_par - last_diag[i]

        reserves_sim[b] = reserve_b
        reserves_par[b] = reserve_p

    return reserves_sim, reserves_par



# =============================================================================

#: LE NOMBRE DE SIMULATIONS PAR DEFAUT — SOURCE UNIQUE.
#:
#: ⚠️ IL Y EN AVAIT TROIS, ET ELLES NE DISAIENT PAS LA MEME CHOSE : 1000 ici,
#: 5000 dans `agent.run`, 5000 dans le menu de l'application. Une seule
#: décision, trois valeurs. Celle-ci était la plus basse ET la plus exposée :
#: un appelant direct de `bootstrap_odp` obtenait 1000 en silence, soit le
#: cinquième du plancher recommandé par EIOPA. Aucun appelant du dépôt ne la
#: subissait — tous fournissent `n_sim` — mais c'est précisément ce qui la
#: rendait invisible.
#:
#: POURQUOI 10 000 ET NON 5 000. Mesuré sur GenIns : le CV est stable dès 200
#: simulations (13,34 % à 200, 13,52 % à 5 000, 13,42 % à 10 000) — c'est un
#: moment central, il converge vite. Le P99.5, lui, bouge encore de 1 % entre
#: 5 000 et 10 000, parce qu'il repose sur les 25 pires tirages à 5 000 contre
#: 50 à 10 000. Or c'est LUI qui sert d'estimation stochastique du capital.
#: Et le coût est faible : 5,6 s contre 7,4 s sur un triangle 10x10, 12,9 s
#: contre 18,8 s sur un 20x20. Le Bootstrap n'est pas le goulot d'A7.
#: 5 000 est le PLANCHER d'une recommandation, pas un optimum.
N_SIM_DEFAUT = 10_000


def bootstrap_odp(
    C:       np.ndarray,
    facteurs: np.ndarray,
    n_sim:   int = N_SIM_DEFAUT,
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

    # ── 1. Incréments ajustés et résidus de Pearson ───────────────────────────
    m_fit, residus, phi, res_list, n_obs, n_params, cellules = \
        calculer_fitted_et_residus(C, facteurs)

    # ⚠️ DEUX CONDITIONS, ET LA SECONDE EST INDISPENSABLE. Le seul critère
    # `len(res_list) < 4` ne suffit pas : il regarde le nombre de résidus, pas
    # le nombre de DEGRÉS DE LIBERTÉ. Un triangle peut fournir six résidus pour
    # onze paramètres — df = −5 — et passer ce filtre. Le modèle est alors
    # sur-paramétré : `adj` retombe à 1, φ est divisé par `max(df, 1)` donc par
    # un dénominateur inventé, et la dispersion simulée s'effondre. Mesuré sur le
    # triangle tout décroissant après le passage à l'ajustement E&V : df = −5,
    # σ ≈ 0, CV = 0 % et un statut VERT — le contraire de ce qu'il faut dire.
    if len(res_list) < 4 or (n_obs - n_params) <= 0:
        logger.warning(
            f"Bootstrap ODP : {len(res_list)} résidu(s) pour "
            f"{n_params} paramètre(s), df={n_obs - n_params}. "
            f"Bootstrap non fiable sur ce triangle."
        )
        reserve_cl = _reserve_cl_simple(C, facteurs, annee_base)
        return _resultat_degrade(reserve_cl, n_sim, C)

    res_arr = np.array(res_list)

    # Dernière diagonale connue
    last_diag = np.array([
        float(C[i, min(n - i - 1, m - 1)]) for i in range(n)
    ])

    # ── 2. Réserve CL de référence ────────────────────────────────────────────
    reserve_ref = _reserve_cl_simple(C, facteurs, annee_base)

    # ── 3. Simulations Bootstrap ──────────────────────────────────────────────
    reserves_sim, reserves_par = _simuler(
        C, m_fit, cellules, res_arr, phi, last_diag, n_sim, annee_base)

    # ── 3e. Recentrage England-Verrall ────────────────────────────────────────
    # Le bootstrap estime la DISPERSION autour de l'estimateur analytique CL
    # (reserve_ref = réserve BRUTE depuis D1), non une moyenne biaisée par les
    # gardes d'incrément (max(…, ·×0.01), 3b/3d) sur triangles très volatils. On
    # décale la distribution pour que sa moyenne = reserve_ref — invariant en σ.
    moyenne_brute = float(np.mean(reserves_sim))
    biais         = moyenne_brute - reserve_ref
    reserves_sim  = reserves_sim - biais

    # ── 4. Distribution et statistiques ──────────────────────────────────────
    be_boot  = float(np.mean(reserves_sim))
    std_boot = float(np.std(reserves_sim, ddof=1))
    cv_boot  = std_boot / max(be_boot, 1e-9)

    # ── 4bis. Décomposition de σ — paramètre / processus ──────────────────────
    # POURQUOI LA PUBLIER. L'exemple du guide (§3.c.ii p30, fig. 30) donne
    # σ = 13 923 sur RAA quand Mack en donne 26 909 sur le MÊME triangle. Sans
    # décomposition, impossible de savoir laquelle des deux composantes explique
    # l'écart — et l'hypothèse la plus naturelle (« le guide serait en paramètre
    # seul ») est démentie par la mesure : c'est notre σ TOTAL qui l'approche.
    # C'est cette opacité qui a laissé un σ 2,4 fois trop grand passer inaperçu.
    std_param = float(np.std(reserves_par, ddof=1))
    var_proc  = max(std_boot ** 2 - std_param ** 2, 0.0)
    std_proc  = float(np.sqrt(var_proc))

    statut = _statut_eiopa(cv_boot)

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

    return _resultat_nominal(
        reserves_sim, be_boot, std_boot, cv_boot, std_param, std_proc,
        moyenne_brute, biais, reserve_ref, phi, n_obs, n_params, n_sim,
        statut, msg, ip_neg)


def _resultat_nominal(
    reserves_sim: np.ndarray,
    be_boot:   float,
    std_boot:  float,
    cv_boot:   float,
    std_param: float,
    std_proc:  float,
    moyenne_brute: float,
    biais:     float,
    reserve_ref: float,
    phi:       float,
    n_obs:     int,
    n_params:  int,
    n_sim:     int,
    statut:    str,
    msg:       str,
    ip_neg:    Dict,
) -> Dict:
    """Contrat de sortie du Bootstrap nominal.

    Séparée de `bootstrap_odp` : construire un dictionnaire de vingt-cinq clés
    est une mise en forme, pas un calcul, et la mêler à l'orchestration rendait
    la fonction principale illisible. Le résultat DÉGRADÉ a son propre
    constructeur, `_resultat_degrade` — les deux contrats sont voisins mais
    distincts, et c'est voulu : l'un publie des grandeurs, l'autre déclare
    qu'il n'en a aucune.
    """
    return {
        'disponible':     True,

        # Statistiques centrales
        'be_bootstrap':   round(be_boot,  2),
        'std_bootstrap':  round(std_boot, 2),
        'cv_bootstrap':   round(cv_boot,  4),

        # Décomposition de l'incertitude — σ² total = σ² paramètre + σ² processus
        'std_parametre':  round(std_param, 2),
        'std_processus':  round(std_proc,  2),

        # Ce que le recentrage a déplacé. Le guide observe « la moyenne n'est pas
        # très différente » de la réserve Chain Ladder AVANT recentrage — +2,5 %
        # sur son propre exemple. Un écart bien plus grand ne serait plus une
        # correction de troncature mais le signe que les gardes d'incrément
        # mordent, donc qu'un paramètre en amont est faux : c'est ainsi qu'un φ
        # 5,8 fois trop grand produisait +79,4 % sur RAA.
        'moyenne_avant_recentrage': round(moyenne_brute, 2),
        'biais_recentrage_pct':     round(biais / max(abs(reserve_ref), 1e-9), 6),

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

def _statut_eiopa(cv: float) -> str:
    """Statut de dispersion selon les Guidelines EIOPA on Technical Provisions.

    CV < 10 % → VERT · 10–20 % → AMBRE · au-delà → ROUGE. Extrait de
    `bootstrap_odp` : un seuil réglementaire se lit mieux isolé qu'enfoui dans
    une fonction de deux cents lignes.
    """
    if cv < 0.10:
        return 'VERT'
    if cv < 0.20:
        return 'AMBRE'
    return 'ROUGE'


def _reserve_cl_simple(
    C:          np.ndarray,
    facteurs:   np.ndarray,
    annee_base: int = 1,
) -> float:
    """Réserve CL simple (sans tail) — cible de recentrage E&V. IBNR BRUT (D1) :
    le recentrage vise l'estimateur CL honnête (recours conservés), cohérent avec
    chain_ladder post-Lot B (1076 et non 1483 sur un triangle à recours fort).
    Ne concerne QUE la cible ; le rééchantillonnage et le pseudo-triangle sont
    indépendants de cette fonction."""
    proj = projeter_ultimates(C, facteurs, tail_factor=1.0)
    return float(np.sum(proj['ibnr_brut'][annee_base:]))


def libelle_incertitude(bloc: Dict, cle: str = 'std_bootstrap') -> str:
    """Grandeur d'incertitude du Bootstrap, formatée pour l'actuaire.

    SOURCE UNIQUE pour les livrables N5. Un Bootstrap NON CALCULÉ n'a pas
    d'écart-type : afficher « 0 » ou « 0,0 % » serait lu comme une incertitude
    nulle, c'est-à-dire l'exact contraire de ce que le cas dégradé signifie.
    Même remède que `libelle_loss_ratio` pour Bornhuetter-Ferguson.
    """
    if not bloc.get('disponible', True):
        return 'non calculé'
    valeur = bloc.get(cle)
    if valeur is None:
        return '—'
    if cle.startswith('cv_'):
        return f"{float(valeur):.1%}"
    # φ n'est pas un montant : il vaut 5,26·10⁴ sur GenIns et 0,33 sur un
    # triangle de faible volume. Un format monétaire l'écrirait « 0 ».
    if cle == 'phi':
        return f"{float(valeur):,.4g}"
    return f"{float(valeur):,.0f}"


def _resultat_degrade(reserve_ref: float, n_sim: int,
                      C: Optional[np.ndarray] = None) -> Dict:
    """Résultat d'un Bootstrap NON CALCULÉ, faute de résidus exploitables.

    ⚠️ AUCUNE GRANDEUR D'INCERTITUDE N'EST FABRIQUÉE. La version précédente
    rendait `std = 0`, `cv = 0` et TOUS les percentiles égaux au point estimate :
    un P99,5 égal au Best Estimate affirme que la réserve ne peut pas être
    dépassée, et un CV de 0 % se lit « aucune incertitude » là où il signifie
    « je n'ai pas pu la mesurer ». C'est la pathologie du `cv_inter` mono-méthode,
    corrigée en N4 au lot Bornhuetter-Ferguson pour exactement la même raison.

    Le point estimate, lui, RESTE publié : la réserve Chain Ladder de référence
    est un chiffre légitime — c'est seulement sa dispersion qui manque.
    """
    ip = (increments_positifs(C, plancher=None) if C is not None else
          {'n_exclues': 0, 'cellules_exclues': [], 'frac_exclue': 0.0,
           'disponible': True})
    return {
        'disponible':    False,
        'be_bootstrap':  round(reserve_ref, 2),
        'std_bootstrap': None,
        'cv_bootstrap':  None,
        'std_parametre': None,
        'std_processus': None,
        'p50': None, 'p75': None, 'p90': None, 'p95': None, 'p99_5': None,
        'ic_95_inf': None, 'ic_95_sup': None,
        'phi': None, 'n_obs': 0, 'n_params': 0, 'df': 0,
        'n_simulations': n_sim,
        'distribution': [],
        'statut': 'ROUGE',
        'methode': 'Bootstrap ODP — England & Verrall (2002)',
        'message': (
            "⚠️ Bootstrap ODP NON CALCULÉ : trop peu d'incréments ajustés "
            "strictement positifs pour un rééchantillonnage fiable. AUCUNE "
            "mesure d'incertitude n'est produite — ni écart-type, ni "
            "percentiles. La réserve Chain Ladder de référence reste publiée."
        ),
        'increments_non_positifs': {
            'n_exclues':        ip['n_exclues'],
            'cellules_exclues': ip['cellules_exclues'],
            'frac_exclue':      ip['frac_exclue'],
            'disponible':       ip['disponible'],
        },
    }
