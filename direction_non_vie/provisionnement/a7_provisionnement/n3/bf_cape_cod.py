# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n3/bf_cape_cod.py  —  Bornhuetter-Ferguson (1972) & Cape Cod
# =============================================================================
#
#  Références
#  ----------
#  Bornhuetter, R.L. & Ferguson, R.E. (1972).
#    "The Actuary and IBNR." Proceedings of the CAS, Vol. LIX, pp. 181–195.
#
#  Bühlmann, H. & Straub, E. (1983).
#    "Estimation of IBNR reserves by the methods of chain ladder, Cape Cod
#     and BF." Mitteilungen der Vereinigung schweizerischer Versicherungs-
#     mathematiker.
#
#  Institut des Actuaires (2023). Guide de provisionnement des sinistres en
#    assurance non-vie, §2.c p16-18 — exemple BF entièrement chiffré, reproduit
#    par les tests de ce module sur ses onze années de survenance.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  RÈGLE D'ENTRÉE : UNE EXPOSITION EST OBLIGATOIRE
#
#  Les deux méthodes ancrent leur estimation sur une grandeur EXTÉRIEURE au
#  triangle. Sans elle, elles n'ont rien à apporter :
#
#  · Bornhuetter-Ferguson a besoin d'une charge ultime attendue `μ`. Elle peut
#    venir d'une EXPOSITION × loss ratio, ou être fournie DIRECTEMENT par
#    l'actuaire — c'est la forme d'origine de 1972, où Bornhuetter et Ferguson
#    parlent d'« expected ultimate loss » issue de la tarification, du budget ou
#    d'un benchmark de marché.
#  · Cape Cod a besoin d'une exposition pour estimer son loss ratio.
#
#  EXPOSITION ≠ PRIMES. Bühlmann et Straub parlent de MESURE DE VOLUME : primes
#  acquises, nombre de contrats, capitaux assurés, années-véhicule conviennent.
#  Exiger spécifiquement des primes bloquerait un assureur qui dispose d'une
#  exposition mais pas d'une allocation de primes par année de survenance.
#
#  AUCUN PROXY N'EST INVENTÉ. Les deux replis qui existaient jusqu'ici sont
#  supprimés, mesures à l'appui :
#
#  · BF déduisait des primes fictives de `C[i,0] / 0.35` — une hypothèse de
#    cadence de première période appliquée uniformément, sans fondement pour une
#    branche donnée.
#  · Cape Cod prenait l'ultime Chain Ladder comme exposition. Ce n'était pas une
#    approximation biaisée mais une IDENTITÉ : puisque `C[i,k_i] = U_CL[i] ×
#    pct_dev[i]` par définition de pct_dev = 1/CDF, le numérateur et le
#    dénominateur du loss ratio deviennent égaux, `LR_CC = 1` EXACTEMENT, et
#    l'IBNR reproduit celui de Chain Ladder au centime. Vérifié sur GenIns et
#    RAA : écart maximal par année de 0,0000. Le Best Estimate moyennait donc
#    Chain Ladder avec Chain Ladder sous deux noms.
#
#  Sans exposition ni ultime a priori, chaque méthode renvoie un résultat
#  explicitement NON CALCULÉ (`disponible = False`), que N4 écarte du Best
#  Estimate. Le message dit la CONSÉQUENCE, pas le manque.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  ⚠️ CE QUE CE MODULE NE PRÉTEND PAS RÉSOUDRE — deux questions d'hypothèses,
#  identifiées et laissées au lot d'audit de BF/Cape Cod :
#
#  1. Le loss ratio dit « a priori » est calculé sur les ULTIMES CHAIN LADDER des
#     années matures (cf. `_loss_ratio_apriori`, source « matures »). BF n'est
#     donc PAS indépendant de Chain Ladder, contrairement à ce que l'en-tête de
#     ce fichier affirmait avant ce lot — mesuré sur GenIns : Chain Ladder mature
#     +10 % déplace la réserve BF de +10,0 %, et jusqu'à 20 % des ultimes servant
#     au calcul ne sont pas observés. Dériver l'a priori de l'expérience mature
#     est une pratique reconnue ; l'ancrer sur des ultimes PROJETÉS est le point
#     à trancher.
#  2. BF ne peut structurellement pas produire un IBNR négatif : `μ × (1 − β)`
#     avec β écrêté à 1 vaut 0 au minimum. Sur un triangle à recours, Chain
#     Ladder rend une reprise et BF rend zéro. Ce n'est pas un plancher ajouté,
#     c'est la forme de la méthode — mais moyenner les deux demande un arbitrage.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  Formules implémentées
#  ---------------------
#  Bornhuetter-Ferguson (1972)
#      IBNR_BF[i]     = (1 − pct_dev[i]) × μ[i]
#      Ultimate_BF[i] = C[i, k_i] + IBNR_BF[i]
#  avec pct_dev[i] = 1 / F_{k_i} la fraction déjà développée et μ[i] la charge
#  ultime attendue. Le guide écrit la même chose (p17) :
#      Ultime_BF = Charge + (S/P) × Primes acquises × (1 − 1/CDF)
#
#  Cape Cod (Bühlmann & Straub 1983)
#                Σ_i C[i, k_i]
#      LR_CC = ─────────────────────────────
#                Σ_i exposition[i] × pct_dev[i]
#      IBNR_CC[i]     = LR_CC × exposition[i] × (1 − pct_dev[i])
#      Ultimate_CC[i] = C[i, k_i] + IBNR_CC[i]
#
#  ⚠️ LA SOMME PORTE SUR TOUTES LES ANNÉES D'ORIGINE, y compris la première.
#  Elle s'arrêtait auparavant à `annee_base`, ce qui confondait deux choses :
#  quelles années reçoivent une RÉSERVE, et quelles années INFORMENT le loss
#  ratio. L'année la plus ancienne, entièrement développée, porte le rapport
#  sinistres/exposition le plus fiable — l'exclure jetait la meilleure donnée.
#  Impact mesuré sur GenIns : loss ratio +4,4 %, réserve +4,2 %.
#  `annee_base` continue de délimiter la RÉSERVE, comme pour les autres méthodes.
# =============================================================================

import logging
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger('actuaria.a7')

#: Bornes de vraisemblance d'un loss ratio. La première déclenche une alerte, la
#: seconde borne le calcul pour qu'une valeur aberrante ne se propage pas.
LR_PLAGE_ALERTE = (0.20, 2.00)
LR_PLAGE_DURE   = (0.01, 5.00)
#: Idem pour le loss ratio Cape Cod, estimé sur les données donc plus contraint.
LR_CC_PLAGE_ALERTE = (0.10, 3.00)

#: Au-delà, le loss ratio des années matures est jugé trop hétérogène pour servir
#: d'a priori sans commentaire.
CV_LR_MAX = 0.25
#: Écart au-delà duquel on signale une divergence avec la référence de marché.
ECART_LR_REFERENCE = 0.20


def libelle_loss_ratio(bloc: Dict, cle: str = 'lr_apriori') -> str:
    """Loss ratio d'un bloc BF/Cape Cod, formaté pour l'actuaire.

    SOURCE UNIQUE pour les livrables N5. Une méthode non calculée n'a PAS de
    loss ratio : afficher « 0,0 % » serait un chiffre faux, et c'est exactement
    le genre de silence que ce lot supprime. Elle affiche « non calculée ».
    """
    if not bloc.get('disponible', True):
        return 'non calculée'
    valeur = bloc.get(cle)
    return '—' if valeur is None else f"{float(valeur):.1%}"


def _exposition_valide(exposition, n: int) -> Optional[np.ndarray]:
    """Rend l'exposition si elle est exploitable, `None` sinon.

    Exploitable = un vecteur d'au moins `n` valeurs dont au moins une est
    strictement positive. Un vecteur de zéros n'est pas une exposition.
    """
    if exposition is None:
        return None
    try:
        vecteur = np.asarray(exposition, dtype=float)
    except (TypeError, ValueError):
        return None
    if vecteur.ndim != 1 or len(vecteur) < n:
        return None
    if not np.any(np.isfinite(vecteur) & (vecteur > 0)):
        return None
    return vecteur[:n]


def _non_calculee(methode: str, n: int, message: str) -> Dict:
    """Résultat d'une méthode qui n'a PAS été calculée, faute d'ancrage externe.

    Même forme que le résultat nominal — les niveaux N4 et N5 lisent les mêmes
    clés — mais `disponible = False`, que N4 utilise pour l'écarter du Best
    Estimate. La réserve à zéro n'est PAS le signal : une réserve nulle peut
    être un résultat légitime.
    """
    return {
        'disponible':            False,
        'lr_apriori':            None,
        'lr_cape_cod':           None,
        'source_lr':             'non calculée',
        'source_exposition':     'non calculée',
        'mu_par_annee':          [0.0] * n,
        'ibnr_par_annee':        [0.0] * n,
        'ultimates':             [0.0] * n,
        'reserve_totale':        0.0,
        'reserve_best_estimate': 0.0,
        'alertes':               [message],
        'infos':                 [],
        'methode':               methode,
        'message':               message,
    }


#: Formulé en CONSÉQUENCE et non en manque : ce qui compte pour l'actuaire n'est
#: pas qu'une donnée soit absente, c'est ce que son absence retire au résultat.
_MSG_SANS_ANCRAGE = (
    "⚠️ {methode} non calculée : aucune mesure d'exposition n'a été fournie{extra}. "
    "Le Best Estimate ne repose donc que sur Chain Ladder — aucun avis "
    "indépendant ne vient le corroborer. Fournir une exposition (primes "
    "acquises, nombre de contrats, capitaux assurés…){activation} activerait "
    "cette méthode."
)


def _loss_ratio_apriori(
    exposition:        np.ndarray,
    ultimates_cl:      np.ndarray,
    n:                 int,
    lr_manuel:         Optional[float],
    lr_reference:      Optional[float],
    lr_reference_src:  str,
    nb_annees_matures: Optional[int],
    alertes:           list,
    infos:             list,
) -> Tuple[float, str]:
    """Loss ratio a priori de Bornhuetter-Ferguson, et sa provenance.

    Deux sources, par ordre de priorité :
      1. fourni par l'actuaire (`lr_manuel`) — prioritaire, il l'assume ;
      2. calculé sur les années matures : `moyenne(Ultimate_CL[i] / exposition[i])`.

    ⚠️ La source 2 ancre BF sur Chain Ladder — voir l'avertissement en en-tête.
    """
    if lr_manuel is not None:
        lr = float(np.clip(lr_manuel, *LR_PLAGE_DURE))
        infos.append(f"LR a priori fourni par l'actuaire : {lr:.1%}")
        return lr, 'manuel'

    nb_mat = nb_annees_matures or (min(5, n // 2) if n >= 6 else min(3, n - 1))
    nb_mat = max(1, min(nb_mat, n - 1))
    ratios = [float(ultimates_cl[i]) / float(exposition[i])
              for i in range(nb_mat)
              if exposition[i] > 0 and ultimates_cl[i] > 0]

    if not ratios:
        alertes.append(
            "⚠️ BF : aucune année mature exploitable pour estimer le LR a priori "
            "— fournir un LR ou une charge ultime a priori.")
        return 0.75, 'defaut'

    lr = float(np.mean(ratios))
    cv = float(np.std(ratios) / max(lr, 1e-9)) if len(ratios) > 1 else 0.0
    infos.append(f"LR a priori = {lr:.1%}, moyenne sur {nb_mat} années matures "
                 f"(CV = {cv:.1%}) — dérivé des ultimes Chain Ladder.")
    if cv > CV_LR_MAX:
        alertes.append(
            f"⚠️ BF : le LR a priori varie de {cv:.1%} d'une année mature à "
            f"l'autre (> {CV_LR_MAX:.0%}) — ancrage hétérogène.")
    if lr_reference and abs(lr - lr_reference) > ECART_LR_REFERENCE:
        alertes.append(
            f"🟡 BF : LR calculé = {lr:.1%} contre {lr_reference:.1%} en "
            f"référence de marché ({lr_reference_src}) — écart supérieur à "
            f"{ECART_LR_REFERENCE:.0%}, à expliquer.")
    return lr, 'matures'


# =============================================================================
#  BORNHUETTER-FERGUSON (1972)
# =============================================================================

def bornhuetter_ferguson(
    C:                 np.ndarray,
    pct_dev:           np.ndarray,
    last_diag:         np.ndarray,
    ultimates_cl:      np.ndarray,
    exposition:        Optional[np.ndarray] = None,
    ultime_apriori:    Optional[np.ndarray] = None,
    lr_manuel:         Optional[float]      = None,
    annee_base:        int                  = 1,
    lr_reference:      Optional[float]      = None,
    lr_reference_src:  str                  = '',
    nb_annees_matures: Optional[int]        = None,
) -> Dict:
    """Bornhuetter-Ferguson (1972) — combine un a priori externe et l'observé.

    Parameters
    ----------
    pct_dev : fraction développée par année (1 / facteur cumulé).
    last_diag : dernière valeur connue `C[i, k_i]`.
    ultimates_cl : ultimes Chain Ladder — servent au LR des années matures.
    exposition : mesure de volume par année (primes, contrats, capitaux…).
    ultime_apriori : charge ultime attendue fournie DIRECTEMENT par l'actuaire.
        C'est la forme d'origine de 1972 ; elle dispense d'exposition et de loss
        ratio, l'actuaire assumant le chiffre.
    lr_manuel : loss ratio a priori imposé, appliqué à l'exposition.

    Sans `exposition` ni `ultime_apriori`, la méthode N'EST PAS CALCULÉE.
    """
    n = C.shape[0]
    alertes: list = []
    infos:   list = []

    # ── 1. Charge ultime attendue μ ───────────────────────────────────────────
    apriori = _exposition_valide(ultime_apriori, n)
    if apriori is not None:
        mu, source = apriori, 'ultime_apriori'
        lr = float('nan')
        infos.append("μ = charge ultime a priori fournie par l'actuaire "
                     "(forme d'origine de Bornhuetter-Ferguson 1972).")
    else:
        expo = _exposition_valide(exposition, n)
        if expo is None:
            return _non_calculee('Bornhuetter-Ferguson (1972)', n,
                                 _MSG_SANS_ANCRAGE.format(
                                     methode="Bornhuetter-Ferguson",
                                     extra=", ni charge ultime a priori",
                                     activation=" ou une charge ultime a priori"))
        lr, source = _loss_ratio_apriori(
            expo, ultimates_cl, n, lr_manuel, lr_reference, lr_reference_src,
            nb_annees_matures, alertes, infos)
        if not (LR_PLAGE_ALERTE[0] <= lr <= LR_PLAGE_ALERTE[1]):
            alertes.append(
                f"⚠️ BF : LR a priori = {lr:.1%}, hors de la plage plausible "
                f"[{LR_PLAGE_ALERTE[0]:.0%} – {LR_PLAGE_ALERTE[1]:.0%}] "
                f"— vérifier la source ({source}).")
        mu = np.array([float(expo[i]) * lr for i in range(n)])

    # ── 2. IBNR et ultimes ────────────────────────────────────────────────────
    frac_a_venir = np.array([max(1.0 - float(pct_dev[i]), 0.0) for i in range(n)])
    ibnr = frac_a_venir * mu
    ultimates = np.array([float(last_diag[i]) + ibnr[i] for i in range(n)])
    reserve = float(np.sum(ibnr[annee_base:]))

    # ── 3. Contrôle de vraisemblance contre Chain Ladder ──────────────────────
    # Sur une année déjà bien développée, un IBNR BF très supérieur à celui de
    # Chain Ladder trahit un a priori trop élevé. L'IBNR de référence est pris
    # BRUT : un plancher à zéro masquerait les reprises que le chantier IBNR a
    # justement rendues visibles ailleurs.
    for i in range(annee_base, n):
        ibnr_cl = float(ultimates_cl[i]) - float(last_diag[i])
        if float(pct_dev[i]) > 0.80 and ibnr_cl > 0 and ibnr[i] / ibnr_cl > 2.0:
            alertes.append(
                f"⚠️ BF année {i} : IBNR = {ibnr[i]:,.0f} €, soit "
                f"{ibnr[i] / ibnr_cl:.1f}× celui de Chain Ladder alors que "
                f"l'année est développée à {pct_dev[i]:.0%} — a priori surestimé ?")

    lr_affiche = None if np.isnan(lr) else round(lr, 4)
    msg = (f"Bornhuetter-Ferguson (1972) : réserve = {reserve:,.0f} € · "
           + (f"a priori fourni ({source})" if lr_affiche is None
              else f"LR = {lr:.1%} ({source})"))
    logger.info(msg)

    return {
        'disponible':            True,
        'lr_apriori':            lr_affiche,
        'source_lr':             source,
        'mu_par_annee':          [round(float(v), 2) for v in mu],
        'ibnr_par_annee':        [round(float(v), 2) for v in ibnr],
        'ultimates':             [round(float(v), 2) for v in ultimates],
        'reserve_totale':        round(reserve, 2),
        'reserve_best_estimate': round(reserve, 2),
        'alertes':               alertes,
        'infos':                 infos,
        'methode':               'Bornhuetter-Ferguson (1972)',
        'message':               msg,
    }


# =============================================================================
#  CAPE COD  (Bühlmann & Straub 1983)
# =============================================================================

def cape_cod(
    C:                np.ndarray,
    pct_dev:          np.ndarray,
    last_diag:        np.ndarray,
    exposition:       Optional[np.ndarray] = None,
    annee_base:       int                  = 1,
    lr_reference:     Optional[float]      = None,
    lr_reference_src: str                  = '',
) -> Dict:
    """Cape Cod (Bühlmann & Straub 1983) — loss ratio estimé sur les données.

    Ne reçoit PLUS les ultimes Chain Ladder : ils ne servaient qu'à fabriquer
    une exposition de repli, désormais supprimée (cf. en-tête).

    Contrairement à Bornhuetter-Ferguson, le loss ratio n'est pas apporté de
    l'extérieur : il se déduit du rapport entre les sinistres observés et
    l'exposition « vue » à ce jour. Mais une exposition reste indispensable —
    sans elle la méthode dégénère en Chain Ladder (cf. en-tête).

    Sans `exposition`, la méthode N'EST PAS CALCULÉE.
    """
    n = C.shape[0]
    alertes: list = []
    infos:   list = []

    expo = _exposition_valide(exposition, n)
    if expo is None:
        return _non_calculee('Cape Cod (Bühlmann & Straub 1983)', n,
                             _MSG_SANS_ANCRAGE.format(
                                 methode="Cape Cod", extra="", activation=""))

    # ── 1. Loss ratio Cape Cod — sur TOUTES les années d'origine ──────────────
    num = sum(float(last_diag[i]) for i in range(n)
              if expo[i] > 0 and pct_dev[i] > 0)
    den = sum(float(expo[i]) * float(pct_dev[i]) for i in range(n)
              if expo[i] > 0 and pct_dev[i] > 0)

    if den <= 0:
        alertes.append(
            "❌ Cape Cod : exposition développée nulle — loss ratio incalculable.")
        return _non_calculee(
            'Cape Cod (Bühlmann & Straub 1983)', n,
            "⚠️ Cape Cod non calculée : l'exposition fournie ne permet pas "
            "d'estimer un loss ratio (exposition développée nulle).")

    lr_cc = num / den
    if not (LR_CC_PLAGE_ALERTE[0] <= lr_cc <= LR_CC_PLAGE_ALERTE[1]):
        alertes.append(
            f"⚠️ Cape Cod : LR = {lr_cc:.1%}, hors de la plage plausible "
            f"[{LR_CC_PLAGE_ALERTE[0]:.0%} – {LR_CC_PLAGE_ALERTE[1]:.0%}] "
            f"— vérifier l'exposition fournie.")
    lr_cc = float(np.clip(lr_cc, *LR_CC_PLAGE_ALERTE))

    if lr_reference and abs(lr_cc - lr_reference) > ECART_LR_REFERENCE:
        alertes.append(
            f"🟡 Cape Cod : LR = {lr_cc:.1%} contre {lr_reference:.1%} en "
            f"référence de marché ({lr_reference_src}) — écart supérieur à "
            f"{ECART_LR_REFERENCE:.0%}, à expliquer.")
    infos.append(f"LR Cape Cod = {lr_cc:.1%} — sinistres observés "
                 f"{num:,.0f} € rapportés à l'exposition développée "
                 f"{den:,.0f} €, sur les {n} années d'origine.")

    # ── 2. IBNR et ultimes ────────────────────────────────────────────────────
    frac_a_venir = np.array([max(1.0 - float(pct_dev[i]), 0.0) for i in range(n)])
    ibnr = lr_cc * expo * frac_a_venir
    ultimates = np.array([float(last_diag[i]) + ibnr[i] for i in range(n)])
    reserve = float(np.sum(ibnr[annee_base:]))

    msg = (f"Cape Cod : réserve = {reserve:,.0f} € · LR = {lr_cc:.1%} "
           f"(exposition fournie)")
    logger.info(msg)

    return {
        'disponible':            True,
        'lr_cape_cod':           round(lr_cc, 4),
        'source_exposition':     'exposition_fournie',
        'ibnr_par_annee':        [round(float(v), 2) for v in ibnr],
        'ultimates':             [round(float(v), 2) for v in ultimates],
        'reserve_totale':        round(reserve, 2),
        'reserve_best_estimate': round(reserve, 2),
        'alertes':               alertes,
        'infos':                 infos,
        'methode':               'Cape Cod (Bühlmann & Straub 1983)',
        'message':               msg,
    }
