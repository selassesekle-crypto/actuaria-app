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
#  LES DEUX QUESTIONS D'HYPOTHÈSES QUE CE MODULE LAISSAIT OUVERTES SONT TRANCHÉES
#  — elles ont leurs verdicts dans `n2_hypotheses_bfcc` (BFCC-H1..H5).
#
#  1. LE LOSS RATIO DÉRIVÉ DE CHAIN LADDER N'EST PAS UNE FAUTE, C'EST UNE
#     PROVENANCE. Le guide de l'Institut des Actuaires liste CINQ façons d'obtenir
#     le S/P (§2.b.i p14) : tarification, plan à moyen terme, benchmark de marché,
#     jugement d'expert, ou calcul sur l'historique — et son exemple chiffré
#     (p15, figure 14) dérive précisément les charges ultimes par Chain Ladder.
#     Les quatre premières voies arrivent ici par `lr_manuel` / `ultime_apriori`,
#     la cinquième est calculée. Ce qui manquait n'était pas un garde-fou mais la
#     TRANSPARENCE : la provenance est désormais publiée (`source_lr`), et
#     BFCC-H4 la juge. Ce qu'il faut savoir et qui est écrit dans les livrables :
#     BF corrige l'ALLOCATION de Chain Ladder entre années (il y substitue
#     l'exposition) mais hérite intégralement de son NIVEAU — mesuré sur GenIns,
#     ultimes CL matures +10 % déplacent la réserve BF de +10,0 %.
#
#  2. BF NE PEUT PAS PRODUIRE D'IBNR NÉGATIF, ET C'EST TESTABLE. La condition est
#     l'hypothèse (H2) du guide (§2.c.ii p18-19) : cadence comprise entre 0 et 1,
#     à éléments consécutifs croissants. Une année à recours la viole, et
#     l'écrêtage de `calculer_pct_developpe` l'effaçait en la déclarant « 100 %
#     développée ». BFCC-H2 la mesure sur la cadence BRUTE et exclut ces années,
#     UNE PAR UNE — Chain Ladder les porte seule. Mesuré : 1 année sur 6 sur le
#     triangle à recours, 5 sur 6 sur le tout décroissant, AUCUNE sur GenIns ni
#     RAA. La remarque du guide sur le facteur à l'ultime inférieur à 1 (p22) est
#     strictement plus faible : sur le triangle à recours, le CDF global vaut
#     1,6629 et ne signalerait rien, alors que la cadence est bien rompue.
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

#: Repli défensif : `_loss_ratio_apriori` documente toujours son refus dans les
#: alertes, ce message ne sert que si cette liste arrivait vide.
_MSG_APRIORI_REFUSE = (
    "⚠️ Bornhuetter-Ferguson non calculée : le loss ratio a priori n'a pas pu "
    "être dérivé de l'historique. Fournir un loss ratio ou une charge ultime "
    "a priori activerait cette méthode."
)


#: En deçà, le loss ratio dérivé est REFUSÉ. Avec une seule année, la dispersion
#: vaut zéro PAR CONSTRUCTION : l'estimateur rendrait son verdict le plus
#: favorable là où il a le moins d'information — exactement la pathologie du
#: `cv_inter` mono-méthode, corrigée en N4 pour la même raison.
MIN_ANNEES_APRIORI = 2


def _masque_admissible(cadence_ok, n: int) -> np.ndarray:
    """Masque d'admissibilité de cadence, ramené à `n` années.

    `None` — la cadence n'a pas été évaluée — vaut « tout admissible » : ce module
    ne se substitue pas au diagnostic, il l'applique quand on le lui donne. Un
    masque trop court est complété à True pour la même raison.
    """
    admis = np.ones(n, dtype=bool)
    if cadence_ok is None:
        return admis
    fourni = np.asarray(cadence_ok, dtype=bool).ravel()
    k = min(n, len(fourni))
    admis[:k] = fourni[:k]
    return admis


def _fenetre_apriori(n: int, nb_annees_matures: Optional[int]) -> int:
    """Largeur de la fenêtre d'années servant à dériver le loss ratio.

    ⚠️ COMPTAGE, PAS SEUIL DE MATURITÉ — décision prise APRÈS mesure, contre
    l'intuition de départ. Un seuil du type « α ≥ 0,95 » a été simulé sur vérité
    connue (modèle croisé α_j × β_i, 3 000 tirages) et rejeté sur trois constats :
      · à loss ratio stable, il ne retire AUCUN biais (+0,00 % dans les deux cas)
        et coûte +50 % d'écart-type — la part projetée d'un ultime Chain Ladder
        ajoute de la variance, pas d'erreur systématique ;
      · à loss ratio en dérive (+4 %/an), il AGGRAVE le biais de 3,8 points, les
        années anciennes étant propres mais périmées ;
      · il n'aide que si Chain Ladder est lui-même faux (choc calendaire : biais
        +2,34 % contre +4,74 %) — cas que CLM-H1 détecte déjà dans 80,3 % des
        tirages, contre 12,3 % de fausses alarmes.
    Se prémunir deux fois du même risque en payant variance et péremption est un
    mauvais échange. C'est BFCC-H5 qui traite la dérive, pas la fenêtre.
    """
    nb_mat = nb_annees_matures or (min(5, n // 2) if n >= 6 else min(3, n - 1))
    return max(1, min(nb_mat, n - 1))


def _loss_ratio_apriori(
    exposition:        np.ndarray,
    ultimates_cl:      np.ndarray,
    n:                 int,
    lr_manuel:         Optional[float],
    lr_reference:      Optional[float],
    lr_reference_src:  str,
    nb_annees_matures: Optional[int],
    cadence_ok:        Optional[np.ndarray],
    alertes:           list,
    infos:             list,
) -> Tuple[Optional[float], str, Dict]:
    """Loss ratio a priori de Bornhuetter-Ferguson, sa provenance et son détail.

    Deux sources, par ordre de priorité :
      1. fourni par l'actuaire (`lr_manuel`) — prioritaire, il l'assume ;
      2. calculé sur la fenêtre mature : `moyenne(Ultimate_CL[i] / exposition[i])`.

    FILTRE D'ADMISSIBILITÉ (`cadence_ok`). Une année dont la cadence viole
    l'hypothèse (H2) du guide n'a pas d'ultime interprétable : son cumulé
    redescend, donc `Ultimate_CL[i]` ne décrit plus une charge en cours de
    développement. Elle est retirée de la fenêtre — jamais remplacée par une
    année plus jeune, ce qui reviendrait à aller chercher la contamination qu'on
    vient d'écarter. La fenêtre rétrécit, elle ne se déplace pas.

    Renvoie `(None, 'refuse', detail)` si moins de `MIN_ANNEES_APRIORI` années
    exploitables subsistent : refuser un chiffre vaut mieux que d'en fabriquer un.
    """
    if lr_manuel is not None:
        lr = float(np.clip(lr_manuel, *LR_PLAGE_DURE))
        infos.append(f"LR a priori fourni par l'actuaire : {lr:.1%}")
        return lr, 'manuel', {'annees_retenues': [], 'ratios': [], 'cv': 0.0,
                              'fenetre': 0, 'annees_ecartees': []}

    largeur = _fenetre_apriori(n, nb_annees_matures)
    admis   = _masque_admissible(cadence_ok, n)

    retenues, ratios, ecartees = [], [], []
    for i in range(largeur):
        if not admis[i]:
            ecartees.append(i)
            continue
        if exposition[i] > 0 and ultimates_cl[i] > 0:
            retenues.append(i)
            ratios.append(float(ultimates_cl[i]) / float(exposition[i]))

    detail = {'annees_retenues': retenues, 'ratios': [round(r, 6) for r in ratios],
              'fenetre': largeur, 'annees_ecartees': ecartees, 'cv': 0.0}

    if len(ratios) < MIN_ANNEES_APRIORI:
        alertes.append(
            f"⚠️ BF : le loss ratio a priori ne peut pas être dérivé de "
            f"l'historique — {len(ratios)} année(s) exploitable(s) sur les "
            f"{largeur} de la fenêtre, minimum {MIN_ANNEES_APRIORI}"
            + (f" ({len(ecartees)} écartée(s) pour cadence non admissible)"
               if ecartees else "")
            + ". Fournir un loss ratio (tarification, plan à moyen terme, "
              "benchmark de marché, jugement d'expert — guide IA 2023 §2.b.i "
              "p14) ou une charge ultime a priori.")
        return None, 'refuse', detail

    lr = float(np.mean(ratios))
    cv = float(np.std(ratios) / max(abs(lr), 1e-9)) if len(ratios) > 1 else 0.0
    detail['cv'] = round(cv, 6)
    infos.append(f"LR a priori = {lr:.1%}, moyenne sur {len(ratios)} année(s) "
                 f"(CV = {cv:.1%}) — dérivé des ultimes Chain Ladder.")
    if ecartees:
        infos.append(f"Années {ecartees} écartées du calcul du LR a priori : "
                     f"cadence non admissible (hypothèse H2 du guide).")
    if cv > CV_LR_MAX:
        alertes.append(
            f"⚠️ BF : le LR a priori varie de {cv:.1%} d'une année mature à "
            f"l'autre (> {CV_LR_MAX:.0%}) — ancrage hétérogène.")
    if lr_reference and abs(lr - lr_reference) > ECART_LR_REFERENCE:
        alertes.append(
            f"🟡 BF : LR calculé = {lr:.1%} contre {lr_reference:.1%} en "
            f"référence de marché ({lr_reference_src}) — écart supérieur à "
            f"{ECART_LR_REFERENCE:.0%}, à expliquer.")
    return lr, 'matures', detail


# =============================================================================
#  BORNHUETTER-FERGUSON (1972)
# =============================================================================

def _charge_ultime_attendue(
    n:                 int,
    exposition,
    ultime_apriori,
    ultimates_cl:      np.ndarray,
    lr_manuel:         Optional[float],
    lr_reference:      Optional[float],
    lr_reference_src:  str,
    nb_annees_matures: Optional[int],
    cadence_ok:        Optional[np.ndarray],
    alertes:           list,
    infos:             list,
) -> Tuple[Optional[np.ndarray], str, float, Dict, Optional[Dict]]:
    """La charge ultime attendue μ de Bornhuetter-Ferguson, et sa provenance.

    Deux formes, dans l'ordre où Bornhuetter et Ferguson les présentent :
      1. une CHARGE ULTIME fournie directement — la forme d'origine de 1972,
         où les auteurs parlent d'« expected ultimate loss » ;
      2. une EXPOSITION multipliée par un loss ratio a priori.

    Le cinquième élément du tuple est un résultat de REFUS non nul lorsque la
    méthode ne peut pas être calculée — pas d'ancrage externe, ou loss ratio non
    dérivable. L'appelant le renvoie tel quel ; le séparer ici évite de mêler la
    construction de μ et la mise en forme du refus.
    """
    apriori = _exposition_valide(ultime_apriori, n)
    if apriori is not None:
        infos.append("μ = charge ultime a priori fournie par l'actuaire "
                     "(forme d'origine de Bornhuetter-Ferguson 1972).")
        return apriori, 'ultime_apriori', float('nan'), {}, None

    expo = _exposition_valide(exposition, n)
    if expo is None:
        return None, '', float('nan'), {}, _non_calculee(
            'Bornhuetter-Ferguson (1972)', n,
            _MSG_SANS_ANCRAGE.format(
                methode="Bornhuetter-Ferguson",
                extra=", ni charge ultime a priori",
                activation=" ou une charge ultime a priori"))

    lr, source, detail_lr = _loss_ratio_apriori(
        expo, ultimates_cl, n, lr_manuel, lr_reference, lr_reference_src,
        nb_annees_matures, cadence_ok, alertes, infos)
    if lr is None:
        refus = _non_calculee('Bornhuetter-Ferguson (1972)', n,
                              alertes[-1] if alertes else _MSG_APRIORI_REFUSE)
        refus.update({'alertes': alertes, 'infos': infos,
                      'detail_lr': detail_lr})
        return None, source, float('nan'), detail_lr, refus

    if not (LR_PLAGE_ALERTE[0] <= lr <= LR_PLAGE_ALERTE[1]):
        alertes.append(
            f"⚠️ BF : LR a priori = {lr:.1%}, hors de la plage plausible "
            f"[{LR_PLAGE_ALERTE[0]:.0%} – {LR_PLAGE_ALERTE[1]:.0%}] "
            f"— vérifier la source ({source}).")
    mu = np.array([float(expo[i]) * lr for i in range(n)])
    return mu, source, lr, detail_lr, None

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
    cadence_ok:        Optional[np.ndarray] = None,
) -> Dict:
    """Bornhuetter-Ferguson (1972) — combine un a priori externe et l'observé.

    Parameters
    ----------
    pct_dev : fraction développée par année (1 / facteur cumulé), ÉCRÊTÉE [0,1].
    last_diag : dernière valeur connue `C[i, k_i]`.
    ultimates_cl : ultimes Chain Ladder — servent au LR des années matures.
    exposition : mesure de volume par année (primes, contrats, capitaux…).
    ultime_apriori : charge ultime attendue fournie DIRECTEMENT par l'actuaire.
        C'est la forme d'origine de 1972 ; elle dispense d'exposition et de loss
        ratio, l'actuaire assumant le chiffre.
    lr_manuel : loss ratio a priori imposé, appliqué à l'exposition.
    cadence_ok : masque des années dont la cadence satisfait l'hypothèse (H2) du
        guide — cf. `chain_ladder.cadence_admissible`. Les années écartées ne
        servent pas à dériver le loss ratio. `None` = pas de filtre.

    Sans `exposition` ni `ultime_apriori`, la méthode N'EST PAS CALCULÉE. Sans
    a priori dérivable non plus (fenêtre trop courte), elle ne l'est pas davantage.
    """
    n = C.shape[0]
    alertes: list = []
    infos:   list = []

    # ── 1. Charge ultime attendue μ ───────────────────────────────────────────
    mu, source, lr, detail_lr, refus = _charge_ultime_attendue(
        n, exposition, ultime_apriori, ultimates_cl, lr_manuel, lr_reference,
        lr_reference_src, nb_annees_matures, cadence_ok, alertes, infos)
    if refus is not None:
        return refus

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
        'detail_lr':             detail_lr,
        'mu_par_annee':          [round(float(v), 2) for v in mu],
        'ibnr_par_annee':        [round(float(v), 2) for v in ibnr],
        'ultimates':             [round(float(v), 2) for v in ultimates],
        'decomposition':         _decomposition_credibilite(
                                     pct_dev, last_diag, mu, ultimates, n),
        'reserve_totale':        round(reserve, 2),
        'reserve_best_estimate': round(reserve, 2),
        'alertes':               alertes,
        'infos':                 infos,
        'methode':               'Bornhuetter-Ferguson (1972)',
        'message':               msg,
    }


def _decomposition_credibilite(
    pct_dev:   np.ndarray,
    last_diag: np.ndarray,
    mu:        np.ndarray,
    ultimates: np.ndarray,
    n:         int,
) -> list:
    """Décomposition de l'ultime BF en ses deux apports, année par année.

    LE POIDS DE CRÉDIBILITÉ EST LA CADENCE ELLE-MÊME. Le guide le dit en toutes
    lettres (§2.c p16) : la cadence de développement fait office de facteur de
    crédibilité entre l'espérance de l'ultime prédéfini et le résultat du Chain
    Ladder. Écrit ainsi, l'ultime BF est une moyenne de crédibilité —

        Ultime_BF[i] = α[i] × Ultime_CL[i]  +  (1 − α[i]) × μ[i]
                     = C[i, k_i]            +  (1 − α[i]) × μ[i]

    la première égalité venant de `Ultime_CL[i] = C[i, k_i] / α[i]`. La part
    « Chain Ladder » est donc exactement le montant OBSERVÉ, et le reste vient de
    l'a priori. Ce facteur, qui gouverne tout l'arbitrage de la méthode,
    n'apparaissait dans aucun livrable — l'actuaire ne pouvait pas montrer d'où
    venait son chiffre. Il apparaît désormais.
    """
    lignes = []
    for i in range(n):
        alpha = float(pct_dev[i])
        part_cl      = float(last_diag[i])
        part_apriori = max(1.0 - alpha, 0.0) * float(mu[i])
        lignes.append({
            'annee':             i,
            'poids_credibilite': round(alpha, 6),
            'part_chain_ladder': round(part_cl, 2),
            'part_apriori':      round(part_apriori, 2),
            'ultime':            round(float(ultimates[i]), 2),
        })
    return lignes


# =============================================================================
#  CAPE COD  (Bühlmann & Straub 1983)
# =============================================================================

def _loss_ratio_cape_cod(
    n:                int,
    expo:             np.ndarray,
    pct_dev:          np.ndarray,
    last_diag:        np.ndarray,
    admis:            np.ndarray,
    lr_reference:     Optional[float],
    lr_reference_src: str,
    alertes:          list,
    infos:            list,
) -> Tuple[Optional[float], list, list]:
    """Loss ratio poolé de Cape Cod, et les années qui l'informent.

              Σ_i C[i, k_i]
        LR = ─────────────────────────────    sur les années ADMISSIBLES
              Σ_i exposition[i] × pct_dev[i]

    ⚠️ LA SOMME PORTE SUR TOUTES LES ANNÉES D'ORIGINE ADMISSIBLES, y compris la
    première : elle est entièrement développée et porte donc le rapport
    sinistres/exposition le plus fiable. `annee_base` délimite la RÉSERVE, pas
    l'information.

    Renvoie `(None, …)` si l'exposition développée est nulle.
    """
    retenues = [i for i in range(n)
                if admis[i] and expo[i] > 0 and pct_dev[i] > 0]
    ecartees = [i for i in range(n) if not admis[i]]
    num = sum(float(last_diag[i]) for i in retenues)
    den = sum(float(expo[i]) * float(pct_dev[i]) for i in retenues)

    if den <= 0:
        alertes.append(
            "❌ Cape Cod : exposition développée nulle — loss ratio incalculable.")
        return None, retenues, ecartees
    if ecartees:
        infos.append(f"Années {ecartees} écartées du loss ratio Cape Cod : "
                     f"cadence non admissible (hypothèse H2 du guide).")

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
                 f"{den:,.0f} €, sur {len(retenues)} des {n} années d'origine.")
    return lr_cc, retenues, ecartees

def cape_cod(
    C:                np.ndarray,
    pct_dev:          np.ndarray,
    last_diag:        np.ndarray,
    exposition:       Optional[np.ndarray] = None,
    annee_base:       int                  = 1,
    lr_reference:     Optional[float]      = None,
    lr_reference_src: str                  = '',
    cadence_ok:       Optional[np.ndarray] = None,
) -> Dict:
    """Cape Cod (Bühlmann & Straub 1983) — loss ratio estimé sur les données.

    Ne reçoit PLUS les ultimes Chain Ladder : ils ne servaient qu'à fabriquer
    une exposition de repli, désormais supprimée (cf. en-tête).

    Contrairement à Bornhuetter-Ferguson, le loss ratio n'est pas apporté de
    l'extérieur : il se déduit du rapport entre les sinistres observés et
    l'exposition « vue » à ce jour. Mais une exposition reste indispensable —
    sans elle la méthode dégénère en Chain Ladder (cf. en-tête).

    `cadence_ok` — même filtre que pour Bornhuetter-Ferguson, et pour la même
    raison : une année que BFCC-H2 écarte du résultat ne peut pas continuer
    d'informer le loss ratio qui le produit. La cohérence est ici d'autant plus
    nécessaire que Cape Cod met TOUTES les années en commun : une seule année à
    cumulé décroissant contaminerait le ratio de toutes les autres.

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

    # ── 1. Loss ratio Cape Cod — sur toutes les années d'origine ADMISSIBLES ──
    admis   = _masque_admissible(cadence_ok, n)
    lr_cc, retenues, ecartees = _loss_ratio_cape_cod(
        n, expo, pct_dev, last_diag, admis, lr_reference, lr_reference_src,
        alertes, infos)
    if lr_cc is None:
        return _non_calculee(
            'Cape Cod (Bühlmann & Straub 1983)', n,
            "⚠️ Cape Cod non calculée : l'exposition fournie ne permet pas "
            "d'estimer un loss ratio (exposition développée nulle"
            + (f", {len(ecartees)} année(s) écartée(s) pour cadence non "
               f"admissible" if ecartees else "") + ").")

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
        'annees_loss_ratio':     retenues,
        'annees_ecartees':       ecartees,
        'ibnr_par_annee':        [round(float(v), 2) for v in ibnr],
        'ultimates':             [round(float(v), 2) for v in ultimates],
        'reserve_totale':        round(reserve, 2),
        'reserve_best_estimate': round(reserve, 2),
        'alertes':               alertes,
        'infos':                 infos,
        'methode':               'Cape Cod (Bühlmann & Straub 1983)',
        'message':               msg,
    }
