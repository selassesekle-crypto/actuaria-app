# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n3/bf_cape_cod.py  —  Bornhuetter-Ferguson (1972) & Cape Cod
# =============================================================================
#
#  Références
#  ----------
#  Bornhuetter, R.L. & Ferguson, R.E. (1972).
#    "The Actuary and IBNR."
#    Proceedings of the CAS, Vol. LIX, pp. 181–195.
#
#  Bühlmann, H. & Straub, E. (1983).
#    "Estimation of IBNR reserves by the methods of chain ladder,
#     Cape Cod and BF."
#    Mitteilungen der Vereinigung schweizerischer Versicherungsmathematiker.
#
#  Mack, T. (1994).
#    "Measuring the Variability of Chain Ladder Reserve Estimates."
#    CAS Forum, Spring 1994.
#
#  Venter, G. (1998).
#    "Testing the Assumptions of Age-to-Age Factors."
#    PCAS LXXXV, pp. 807–847.
#
#  Formules implémentées
#  ---------------------
#
#  Bornhuetter-Ferguson (1972)
#  ───────────────────────────
#  Pour chaque année de survenance i :
#
#      IBNR_BF[i]    = (1 - pct_dev[i]) × μ[i]
#      Ultimate_BF[i] = C[i, k_i] + IBNR_BF[i]
#
#  où  pct_dev[i]  = 1 / F_{k_i}   : fraction déjà développée
#                   (F_{k_i} = facteur cumulé depuis colonne k_i)
#      k_i         = min(n-i-1, m-1) : dernière colonne connue
#      μ[i]        = prime[i] × LR_apriori  : sinistres attendus a priori
#
#  Si primes non disponibles :
#      μ[i] = Ultimate_CL[i] × LR_apriori
#      ⚠️ CIRCULARITÉ : μ dépend de CL → BF n'est plus indépendant de CL.
#         Documenté explicitement dans les alertes.
#
#  Loss Ratio a priori
#  ───────────────────
#  Source 1 — Fourni manuellement par l'actuaire
#  Source 2 — Calculé depuis les années les plus matures :
#      LR = moyenne(Ultimate_CL[i] / prime[i])  pour i = 0..nb_matures-1
#  Source 3 — Proxy sans primes (⚠️ approximation) :
#      LR_proxy = moyenne(Ultimate_CL[i] / (C[i,0] / 0.35))
#      Hypothèse : sinistres initiaux ≈ 35% des primes (FFA Non-Vie)
#
#  Cape Cod (Bühlmann & Straub)
#  ─────────────────────────────
#  Le LR Cape Cod est estimé directement depuis les données :
#
#      LR_CC = Σ_{i≥1} C[i, k_i]                   ← sinistres observés
#              ─────────────────────────────────────
#              Σ_{i≥1} prime[i] × pct_dev[i]        ← exposition pondérée
#
#  Puis :
#      IBNR_CC[i]    = LR_CC × prime[i] × (1 - pct_dev[i])
#      Ultimate_CC[i] = C[i, k_i] + IBNR_CC[i]
#
#  Avantages vs BF :
#  · Pas d'a priori externe — LR estimé depuis les données
#  · Plus robuste si le LR marché n'est pas disponible
#  · Convergence vers CL quand pct_dev → 1 (années matures)
#
#  Circularité Cape Cod sans primes
#  ──────────────────────────────────
#  Sans primes, exposition = Ultimate_CL → LR_CC = sinistres/ultimes CL.
#  Cette circularité est documentée et signalée — résultat à interpréter
#  avec précaution.
#
# =============================================================================

import logging
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  BORNHUETTER-FERGUSON (1972)
# =============================================================================

def bornhuetter_ferguson(
    C:                np.ndarray,
    pct_dev:          np.ndarray,
    last_diag:        np.ndarray,
    ultimates_cl:     np.ndarray,
    primes:           Optional[np.ndarray] = None,
    lr_manuel:        Optional[float]      = None,
    annee_base:       int                  = 1,
    lr_reference:     Optional[float]      = None,
    lr_reference_src: str                  = '',
) -> Dict:
    """
    Méthode de Bornhuetter-Ferguson (1972).

    Combine l'a priori (sinistres attendus) avec les observations.
    Idéale quand H1 est rejetée ou les années récentes sont peu développées.

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé.
    pct_dev : np.ndarray  shape (n,)
        Fraction développée par année (depuis chain_ladder.calculer_pct_developpe).
    last_diag : np.ndarray  shape (n,)
        Dernière valeur connue par année C[i, k_i].
    ultimates_cl : np.ndarray  shape (n,)
        Ultimates Chain Ladder (utilisés si primes absentes).
    primes : np.ndarray, optional
        Primes acquises par année de survenance.
    lr_manuel : float, optional
        Loss Ratio a priori fourni manuellement par l'actuaire.
        Prioritaire sur tout calcul automatique.
    annee_base : int
        Première année incluse dans la réserve (défaut = 1).
    lr_reference : float, optional
        LR de référence marché (depuis lob_config) pour validation.
    lr_reference_src : str
        Source du LR de référence marché.

    Returns
    -------
    dict conforme standard ActuarIA.
    """
    n, m     = C.shape
    alertes  = []
    infos    = []

    # ── 1. Déterminer le Loss Ratio a priori ──────────────────────────────────

    if lr_manuel is not None:
        # Source 1 : LR fourni manuellement
        lr       = float(np.clip(lr_manuel, 0.01, 5.0))
        source   = 'manuel'
        infos.append(f"LR a priori fourni manuellement : {lr:.1%}")

    elif primes is not None and len(primes) >= n:
        # Source 2 : LR calculé depuis les années matures avec primes
        nb_mat    = min(5, n // 2) if n >= 6 else min(3, n - 1)
        lr_annees = []
        for i in range(nb_mat):
            p = float(primes[i])
            u = float(ultimates_cl[i])
            if p > 0 and u > 0:
                lr_annees.append(u / p)

        if lr_annees:
            lr     = float(np.mean(lr_annees))
            source = 'primes_fournies'
            cv_lr  = float(np.std(lr_annees) / max(lr, 1e-9)) if len(lr_annees) > 1 else 0.0
            infos.append(
                f"LR a priori = {lr:.1%} calculé sur {nb_mat} années matures "
                f"(CV={cv_lr:.1%})"
            )
            if cv_lr > 0.25:
                alertes.append(
                    f"⚠️ BF : CV du LR a priori = {cv_lr:.1%} > 25% "
                    f"— LR hétérogène entre années matures."
                )
            # Comparer avec référence marché
            if lr_reference and abs(lr - lr_reference) > 0.20:
                alertes.append(
                    f"🟡 BF : LR calculé = {lr:.1%} vs référence marché "
                    f"= {lr_reference:.1%} ({lr_reference_src}). "
                    f"Écart > 20 pts — vérifier la cohérence."
                )
        else:
            lr     = 0.75
            source = 'defaut'
            alertes.append("⚠️ BF : impossible de calculer le LR depuis les années matures.")

    else:
        # Source 3 : proxy sans primes
        # ⚠️ CIRCULARITÉ : μ = Ultimate_CL × LR → BF dépend de CL
        nb_mat    = min(5, n // 2) if n >= 6 else min(3, n - 1)
        lr_proxy  = []
        for i in range(nb_mat):
            c0 = float(C[i, 0])
            u  = float(ultimates_cl[i])
            if c0 > 0 and u > 0:
                # Hypothèse : sinistres initiaux ≈ 35% des primes (FFA Non-Vie)
                prime_proxy = c0 / 0.35
                lr_proxy.append(u / prime_proxy)

        lr     = float(np.clip(np.mean(lr_proxy), 0.35, 1.50)) if lr_proxy else 0.75
        source = 'proxy_sans_primes'
        alertes.append(
            f"⚠️ BF — primes non fournies : LR proxy = {lr:.1%} "
            f"(hypothèse sinistres initiaux = 35% des primes, FFA Non-Vie). "
            f"⚠️ CIRCULARITÉ : μ dépend de CL — résultat à valider avec l'actuaire."
        )

    # Garde-fou LR
    if lr < 0.20 or lr > 2.0:
        alertes.append(
            f"⚠️ BF : LR a priori = {lr:.1%} hors plage raisonnable [20%-200%]. "
            f"Vérifier la source ({source})."
        )
    lr = float(np.clip(lr, 0.01, 5.0))

    # ── 2. Sinistres attendus a priori μ[i] ───────────────────────────────────
    #
    # μ[i] = prime[i] × LR    si primes disponibles
    # μ[i] = Ultimate_CL[i] × LR   sinon (circularité documentée)

    if primes is not None and len(primes) >= n:
        mu = np.array([float(primes[i]) * lr for i in range(n)])
    else:
        mu = np.array([float(ultimates_cl[i]) * lr for i in range(n)])
        infos.append(
            "μ[i] = Ultimate_CL[i] × LR (sans primes — voir alerte circularité)"
        )

    # ── 3. IBNR BF ────────────────────────────────────────────────────────────
    #
    # IBNR_BF[i]     = (1 - pct_dev[i]) × μ[i]
    # Ultimate_BF[i] = C[i, k_i] + IBNR_BF[i]
    #
    # Interprétation :
    # · pct_dev[i] = fraction déjà réalisée → pct observé
    # · (1 - pct_dev[i]) = fraction encore à venir → pct IBNR
    # · μ[i] = montant total attendu a priori (exposition × LR)

    ibnr_bf    = np.zeros(n)
    ultimates_bf = np.zeros(n)

    for i in range(n):
        frac_ibnr     = max(1.0 - float(pct_dev[i]), 0.0)
        ibnr_bf[i]    = frac_ibnr * float(mu[i])
        ultimates_bf[i] = float(last_diag[i]) + ibnr_bf[i]

    reserve_totale = float(np.sum(ibnr_bf[annee_base:]))

    msg = (
        f"Bornhuetter-Ferguson (1972) : réserve={reserve_totale:,.0f}€ · "
        f"LR={lr:.1%} ({source})"
    )
    logger.info(msg)

    return {
        'lr_apriori':            round(lr, 4),
        'source_lr':             source,
        'mu_par_annee':          [round(float(v), 2) for v in mu],
        'ibnr_par_annee':        [round(float(v), 2) for v in ibnr_bf],
        'ultimates':             [round(float(v), 2) for v in ultimates_bf],
        'reserve_totale':        round(reserve_totale, 2),
        'reserve_best_estimate': round(reserve_totale, 2),
        'alertes':               alertes,
        'infos':                 infos,
        'methode':               'Bornhuetter-Ferguson (1972)',
        'message':               msg,
    }


# =============================================================================
#  CAPE COD  (Bühlmann & Straub)
# =============================================================================

def cape_cod(
    C:            np.ndarray,
    pct_dev:      np.ndarray,
    last_diag:    np.ndarray,
    ultimates_cl: np.ndarray,
    primes:       Optional[np.ndarray] = None,
    annee_base:   int                  = 1,
    lr_reference: Optional[float]      = None,
    lr_reference_src: str              = '',
) -> Dict:
    """
    Méthode Cape Cod (Bühlmann & Straub 1983).

    Estime le LR directement depuis les données observées, sans a priori
    externe. Plus robuste que BF quand les primes ne sont pas disponibles
    ou quand l'a priori est incertain.

    LR_CC = Σ sinistres observés (zone connue)
            ────────────────────────────────────
            Σ exposition pondérée par pct_dev[i]

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé.
    pct_dev : np.ndarray  shape (n,)
        Fraction développée par année.
    last_diag : np.ndarray  shape (n,)
        Dernière valeur connue par année.
    ultimates_cl : np.ndarray  shape (n,)
        Ultimates Chain Ladder (exposition si primes absentes).
    primes : np.ndarray, optional
        Primes acquises par année.
    annee_base : int
        Première année incluse dans la réserve (défaut = 1).
    lr_reference : float, optional
        LR marché de référence pour validation.

    Returns
    -------
    dict conforme standard ActuarIA.
    """
    n, m    = C.shape
    alertes = []
    infos   = []

    # ── 1. Exposition par année ───────────────────────────────────────────────

    if primes is not None and len(primes) >= n:
        expo   = np.array([float(primes[i]) for i in range(n)])
        source = 'primes_fournies'
        infos.append("Cape Cod : exposition = primes acquises fournies")
    else:
        # Sans primes → exposition = Ultimate_CL
        # ⚠️ CIRCULARITÉ : LR_CC = sinistres / (Ultimate_CL × pct_dev)
        expo   = np.array([float(ultimates_cl[i]) for i in range(n)])
        source = 'proxy_ultimates_cl'
        alertes.append(
            "⚠️ Cape Cod — primes non fournies : exposition = Ultimate_CL. "
            "⚠️ CIRCULARITÉ : LR_CC estimé depuis CL — résultat biaisé "
            "si CL est biaisé. Fournir les primes pour un Cape Cod fiable."
        )

    # ── 2. LR Cape Cod ────────────────────────────────────────────────────────
    #
    #          Σ_{i≥annee_base} C[i, k_i]
    # LR_CC = ────────────────────────────────────────────────
    #          Σ_{i≥annee_base} expo[i] × pct_dev[i]
    #
    # Interprétation :
    # · Numérateur   = sinistres déjà observés (zone connue)
    # · Dénominateur = exposition "vue" jusqu'à aujourd'hui
    #                  expo[i] × pct_dev[i] = primes × fraction développée
    # → LR_CC est un estimateur sans biais du LR ultime si les expositions
    #   sont correctes.

    num = 0.0
    den = 0.0
    for i in range(annee_base, n):
        pd = float(pct_dev[i])
        ex = float(expo[i])
        if ex > 0 and pd > 0:
            num += float(last_diag[i])
            den += ex * pd

    if den <= 0:
        alertes.append("❌ Cape Cod : dénominateur nul — impossible de calculer LR_CC.")
        lr_cc = 0.75
    else:
        lr_cc = num / den

    # Garde-fou
    if lr_cc < 0.10 or lr_cc > 3.0:
        alertes.append(
            f"⚠️ Cape Cod : LR_CC = {lr_cc:.1%} hors plage [10%-300%]. "
            f"Vérifier l'exposition ({source})."
        )
    lr_cc = float(np.clip(lr_cc, 0.10, 3.0))

    # Comparaison avec référence marché
    if lr_reference and abs(lr_cc - lr_reference) > 0.20:
        alertes.append(
            f"🟡 Cape Cod : LR_CC = {lr_cc:.1%} vs référence marché "
            f"= {lr_reference:.1%} ({lr_reference_src}). "
            f"Écart > 20 pts."
        )

    infos.append(
        f"LR Cape Cod = {lr_cc:.1%} "
        f"(numérateur={num:,.0f}€, dénominateur={den:,.0f}€)"
    )

    # ── 3. IBNR Cape Cod ──────────────────────────────────────────────────────
    #
    # IBNR_CC[i]    = LR_CC × expo[i] × (1 - pct_dev[i])
    # Ultimate_CC[i] = C[i, k_i] + IBNR_CC[i]

    ibnr_cc      = np.zeros(n)
    ultimates_cc = np.zeros(n)

    for i in range(n):
        frac          = max(1.0 - float(pct_dev[i]), 0.0)
        ibnr_cc[i]    = lr_cc * float(expo[i]) * frac
        ultimates_cc[i] = float(last_diag[i]) + ibnr_cc[i]

    reserve_totale = float(np.sum(ibnr_cc[annee_base:]))

    msg = (
        f"Cape Cod : réserve={reserve_totale:,.0f}€ · "
        f"LR_CC={lr_cc:.1%} ({source})"
    )
    logger.info(msg)

    return {
        'lr_cape_cod':           round(lr_cc, 4),
        'source_exposition':     source,
        'ibnr_par_annee':        [round(float(v), 2) for v in ibnr_cc],
        'ultimates':             [round(float(v), 2) for v in ultimates_cc],
        'reserve_totale':        round(reserve_totale, 2),
        'reserve_best_estimate': round(reserve_totale, 2),
        'alertes':               alertes,
        'infos':                 infos,
        'methode':               'Cape Cod (Bühlmann & Straub 1983)',
        'message':               msg,
    }
