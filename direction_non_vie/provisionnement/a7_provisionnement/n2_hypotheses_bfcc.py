# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n2_hypotheses_bfcc.py  —  Les hypothèses propres à Bornhuetter-Ferguson
#                            et à Cape Cod (BFCC-H1 … BFCC-H5)
# =============================================================================
#
#  CE MODULE PRODUIT DES VERDICTS, IL N'EN TIRE AUCUNE CONSÉQUENCE. Aucun score,
#  aucun poids, aucune exclusion : `critique_pour` DÉCRIT ce que la théorie
#  invalide si l'hypothèse tombe, et c'est N4 — le niveau qui possède les
#  réserves — qui décide. Même discipline que `n2_hypotheses_clm`, et vérifiée
#  par le même verrou de périmètre côté tests.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  CE QUE DIT LE GUIDE, ET CE QU'IL NE DIT PAS
#
#  Le guide de l'Institut des Actuaires (février 2023) énonce DEUX hypothèses
#  pour Bornhuetter-Ferguson (§2.c.ii p18-19) :
#    (H1) indépendance des montants incrémentaux par période d'origine —
#         le guide précise qu'elle est IDENTIQUE à celle de Chain Ladder ;
#    (H2) il existe un vecteur `β_i` sur les années d'origine (strictement
#         positif) et un vecteur `α_j` sur les années de développement — compris
#         entre 0 et 1, à éléments consécutifs CROISSANTS, et valant 1 à
#         l'ultime — tels que chaque montant du triangle soit, en espérance,
#         le produit des deux (figure 21).
#
#  ⚠️ LE GUIDE NE TRAITE PAS CAPE COD. Vérifié sur sa table des matières : les
#  méthodes déterministes présentées sont Chain-Ladder (2.a), Loss Ratio (2.b),
#  Bornhuetter-Ferguson (2.c) et Benktander (2.c.iii). Aucune section Cape Cod,
#  aucune ligne dans le tableau de synthèse. Ce qui concerne Cape Cod ici est
#  donc dérivé de Bühlmann & Straub (1983) et porte `SOURCE_JUGEMENT`, jamais
#  `SOURCE_GUIDE` — la distinction n'est pas cosmétique, elle dit à l'actuaire
#  ce qu'il peut opposer à un contrôleur.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  DEUX HYPOTHÈSES SONT REPRISES, PAS RÉIMPLÉMENTÉES
#
#  · BFCC-H1 republie le verdict de CLM-H1. Le guide dit l'hypothèse identique à
#    celle de Chain Ladder ; deux implémentations du même test finiraient par
#    diverger, et c'est l'écart entre elles qu'il faudrait alors expliquer.
#  · BFCC-H3 republie le verdict du GLM Poisson âge-cohorte (`glm_apc`). Son
#    test F calendaire est EXACTEMENT le test de l'hypothèse (H2) : le modèle
#    croisé `α_j × β_i` est celui qu'il ajuste, et un effet calendaire
#    significatif est précisément « quelque chose au-delà du produit des deux
#    vecteurs ». Construire un troisième ajusteur du même modèle serait une
#    faute d'architecture.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  BFCC-H5 PORTE DEUX CRITICITÉS SELON LA MÉTHODE — c'est voulu.
#
#  Pour Bornhuetter-Ferguson, le loss ratio est un a priori PAR ANNÉE : une
#  dérive se corrige (méthode « as-if », guide p15) et n'invalide pas la
#  méthode → informatif.
#  Pour Cape Cod, Bühlmann & Straub imposent UN loss ratio unique mis en commun
#  sur toutes les années d'origine. Une dérive rend la méthode structurellement
#  fausse : le ratio poolé est trop bas pour les années récentes, qui portent
#  l'essentiel de la réserve (mesuré : 24,8 % sur GenIns, 40,0 % sur RAA pour la
#  seule année la plus jeune) → critique.
#
#  ⚠️ CE LOT DÉTECTE LA DÉRIVE, IL NE LA CORRIGE PAS. Appliquer l'ajustement
#  « as-if » exige les tendances de sinistralité et de prime de l'actuaire — le
#  guide les prend en entrée, il ne les devine pas. Les inventer ici reviendrait
#  à fabriquer l'hypothèse qu'on prétend tester.
#
#  ⚠️ ANGLE MORT DE BFCC-H5, MESURÉ AVANT DE LA RETENIR. Sonde de puissance sur
#  10 années, 2 000 tirages, t bilatéral à 5 % :
#         dérive      bruit CV 5 %   CV 10 %   CV 20 %
#         0 %/an          4,9 %       5,2 %     5,6 %   ← niveau nominal tenu
#        +3 %/an         99,8 %      64,6 %    21,3 %
#        +5 %/an        100,0 %      96,7 %    46,9 %
#        +8 %/an        100,0 %     100,0 %    84,8 %
#  Sur un portefeuille volatil, une dérive modérée passe inaperçue : un statut
#  VALIDÉE NE CERTIFIE PAS l'absence de dérive, il constate qu'on ne la voit pas.
#
#  Références
#  ----------
#  Institut des Actuaires (2023). Guide de provisionnement des sinistres en
#    assurance non-vie — §2.b.i p14 (les cinq sources du S/P), p15 (dispersion
#    des S/P historiques et méthode « as-if »), §2.c p16 (la cadence comme
#    facteur de crédibilité), §2.c.ii p18-19 (H1 et H2), §2.d p21-22 (conditions
#    d'application, remarque sur le facteur à l'ultime inférieur à 1).
#  Bühlmann, H. & Straub, E. (1983). Mitteilungen der VSVM.
# =============================================================================

import logging
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .n2_hypotheses_clm import (
    A_JUSTIFIER, NON_TESTABLE, NON_VALIDEE, VALIDEE,
    SOURCE_GUIDE, SOURCE_JUGEMENT,
    ResultatHypothese, SCIPY_OK,
)

try:                                                   # pragma: no cover
    from scipy.stats import t as _loi_t
except ImportError:                                    # pragma: no cover
    _loi_t = None

logger = logging.getLogger('actuaria.a7')


# ── Seuils BFCC-H5 — JUGEMENT, alignés sur ceux de CLM-H3 ────────────────────
H5_P_TENDANCE      = 0.05
H5_P_TENDANCE_FORT = 0.01

#: Sous ce nombre d'années, une pente n'a pas de degré de liberté résiduel
#: exploitable — le test est NON TESTABLE, jamais « validé par défaut ».
H5_MIN_ANNEES = 4

#: Codes des méthodes, tels que N4 les nomme.
BF = 'bornhuetter_ferguson'
CC = 'cape_cod'


# =============================================================================
#  BFCC-H1 — INDÉPENDANCE DES ANNÉES D'ORIGINE  (reprise de CLM-H1)
# =============================================================================

def bfcc_h1_independance(clm_h1: Optional[Dict]) -> ResultatHypothese:
    """BFCC-H1 — reprend le verdict de CLM-H1, sans le recalculer.

    Le guide (§2.c.ii p18) énonce l'hypothèse (H1) de Bornhuetter-Ferguson et
    précise qu'elle est identique à celle de Chain Ladder. Le test correspondant
    — celui des signes par diagonale de l'annexe 9.d — est déjà implémenté et
    validé sur l'exemple chiffré du guide. Le republier sous son propre code
    donne à l'actuaire la liste complète des hypothèses de BF sans lui faire
    croire qu'un second contrôle a eu lieu.

    Prend la SYNTHÈSE publiée par `verifier_hypotheses_clm` — un dict — et non
    l'objet interne : reprendre un verdict ne doit pas obliger le module qui le
    produit à élargir son contrat pour être relu.
    """
    base = dict(code='BFCC-H1',
                libelle="Indépendance des années d'origine",
                critere="reprise du verdict CLM-H1",
                source_critere=SOURCE_GUIDE,
                critique_pour=(BF, CC))
    if not clm_h1:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("BFCC-H1 NON TESTABLE — le verdict CLM-H1 n'est pas "
                     "disponible ; l'hypothèse n'a donc pas été évaluée."),
            extras={'repris_de': 'CLM-H1'})

    base['critere'] = str(clm_h1.get('critere', base['critere']))
    return ResultatHypothese(
        **base,
        statut=str(clm_h1.get('statut', NON_TESTABLE)),
        valeur=clm_h1.get('valeur'),
        message=("BFCC-H1 = CLM-H1, le guide énonçant l'hypothèse identique "
                 "pour les deux méthodes (§2.c.ii p18). "
                 + str(clm_h1.get('message', ''))),
        detail=tuple(dict(d) for d in clm_h1.get('detail', ())),
        extras={'repris_de': 'CLM-H1'},
    )


# =============================================================================
#  BFCC-H2 — CADENCE DE DÉVELOPPEMENT ADMISSIBLE       ⚠️ critique, par année
# =============================================================================

def bfcc_h2_cadence(
    pct_brut:   Sequence[float],
    cadence_ok: Sequence[bool],
) -> ResultatHypothese:
    """BFCC-H2 — la cadence satisfait-elle l'hypothèse (H2) du guide ?

    Le guide impose au vecteur de développement d'être compris entre 0 et 1, à
    éléments consécutifs croissants, et de valoir 1 à l'ultime (§2.c.ii p18-19,
    figure 21). Indexé par année d'origine, « croissant » se lit décroissant en
    indice : l'année 0 est la plus mature.

    ⚠️ ÉVALUÉE SUR LA CADENCE BRUTE. `calculer_pct_developpe` écrête à [0,1] pour
    protéger l'arithmétique aval ; cet écrêtage RAMÈNE À 1 exactement les années
    qui violent l'hypothèse, et les fait donc passer pour totalement développées.
    Juger sur la valeur écrêtée reviendrait à ne jamais voir la violation.

    ⚠️ VERDICT BINAIRE, SANS ZONE GRISE. La condition du guide est une inégalité,
    pas un test statistique : lui inventer un seuil de tolérance ajouterait un
    jugement là où la source n'en laisse aucun. Il n'y a donc pas d'À JUSTIFIER.

    CE QUE LA VIOLATION SIGNIFIE CONCRÈTEMENT. Une année dont la cadence dépasse
    1 est une année dont le cumulé redescend — un recours, une subrogation, une
    reprise de provision. Bornhuetter-Ferguson et Cape Cod y produisent alors
    `μ × max(1 − α, 0) = 0` : jamais le bon signe, jamais le bon ordre de
    grandeur. Mesuré sur le triangle « recours fort » : Chain Ladder rend −50,6,
    −110,1 et −246,2 là où les deux autres rendent zéro, et le total est
    surestimé de 37 à 44 %.
    """
    a  = np.asarray(pct_brut, dtype=float)
    ok = np.asarray(cadence_ok, dtype=bool)
    n  = len(a)

    detail = tuple(
        {'annee': i, 'alpha_brut': round(float(a[i]), 6),
         'statut': VALIDEE if ok[i] else NON_VALIDEE}
        for i in range(n)
    )
    fautives = [i for i in range(n) if not ok[i]]

    if n == 0:
        statut, message = NON_TESTABLE, "BFCC-H2 NON TESTABLE — cadence absente."
    elif not fautives:
        statut = VALIDEE
        message = (f"BFCC-H2 VALIDÉE — la cadence est comprise entre 0 et 1 et "
                   f"croissante sur les {n} années d'origine.")
    else:
        statut = NON_VALIDEE
        message = (
            f"BFCC-H2 NON VALIDÉE sur {len(fautives)} année(s) d'origine "
            f"({fautives}) — leur cumulé redescend, la cadence y dépasse 1 ou "
            f"rompt sa croissance. Bornhuetter-Ferguson et Cape Cod ne peuvent "
            f"structurellement pas y représenter une reprise : ils y rendent "
            f"zéro. CES ANNÉES-LÀ SONT PORTÉES PAR CHAIN LADDER SEULE ; les "
            f"autres gardent les trois méthodes.")

    return ResultatHypothese(
        code='BFCC-H2',
        libelle="Cadence de développement admissible",
        statut=statut,
        valeur=(None if n == 0 else round(float(np.max(a)), 6)),
        critere="α ∈ ]0,1] et décroissante en année d'origine (guide fig. 21)",
        source_critere=SOURCE_GUIDE,
        message=message,
        critique_pour=(BF, CC),
        detail=detail,
        extras={'annees_non_admissibles': fautives,
                'nb_annees': n},
    )


def couverture_cadence_par_annee(h2: Optional[ResultatHypothese]) -> Dict[int, str]:
    """Statut de cadence, année par année — ce que N4 lit pour exclure.

    Troisième couverture, aux côtés de `couverture_motif` et
    `couverture_volatilite` produites par CLM. Elle s'en distingue par sa portée :
    le motif concerne les TROIS méthodes du Best Estimate, qui consomment les
    mêmes facteurs ; la cadence ne disqualifie que celles qui multiplient
    `1 − α` par un a priori, c'est-à-dire Bornhuetter-Ferguson et Cape Cod.
    Chain Ladder, elle, projette le cumulé tel qu'il est et rend la reprise.
    """
    if h2 is None:
        return {}
    return {int(d['annee']): str(d.get('statut', NON_TESTABLE))
            for d in h2.detail if 'annee' in d}


# =============================================================================
#  BFCC-H3 — STRUCTURE MULTIPLICATIVE α_j × β_i   (reprise du GLM Poisson APC)
# =============================================================================

def bfcc_h3_structure(glm_apc: Optional[Dict]) -> ResultatHypothese:
    """BFCC-H3 — le triangle se réduit-il au produit `α_j × β_i` ?

    Reprend le test F calendaire du GLM Poisson âge-cohorte, qui ajuste
    exactement ce modèle croisé. Un effet calendaire significatif est un effet
    « en plus » du produit des deux vecteurs, donc une violation de (H2).

    ⚠️ DESCRIPTIF DANS CE LOT : `critique_pour = ()`. Le GLM APC n'a jusqu'ici
    aucun effet décisionnel dans A7 ; lui en donner un ici mêlerait deux risques —
    celui de l'hypothèse et celui d'un module dont ce serait le premier usage
    gatant. À rouvrir dans un lot dédié, sur mesure d'impact.
    """
    base = dict(code='BFCC-H3',
                libelle="Structure multiplicative sans effet calendaire",
                critere=(f"test F calendaire quasi-Poisson, "
                         f"p ≥ {H5_P_TENDANCE} → validée"),
                source_critere=SOURCE_JUGEMENT,
                critique_pour=())

    if not glm_apc or not glm_apc.get('success') or not glm_apc.get('glm_disponible'):
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("BFCC-H3 NON TESTABLE — le GLM Poisson âge-cohorte n'a pas "
                     "produit de test calendaire exploitable."),
            extras={'repris_de': 'glm_apc'})

    p = glm_apc.get('p_calendaire')
    if p is None:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message="BFCC-H3 NON TESTABLE — p-valeur calendaire indisponible.",
            extras={'repris_de': 'glm_apc'})

    p = float(p)
    if p < H5_P_TENDANCE_FORT:
        statut = NON_VALIDEE
    elif p < H5_P_TENDANCE:
        statut = A_JUSTIFIER
    else:
        statut = VALIDEE

    return ResultatHypothese(
        **base, statut=statut, valeur=round(p, 6),
        message=(
            f"BFCC-H3 {statut} — effet calendaire testé par le GLM Poisson "
            f"âge-cohorte : p = {p:.4f}. "
            + ("Le triangle se réduit au produit cadence × année d'origine, "
               "structure que suppose Bornhuetter-Ferguson."
               if statut == VALIDEE else
               "Un effet propre aux années calendaires subsiste au-delà du "
               "produit cadence × année d'origine — BF hérite du même biais que "
               "Chain Ladder sur les années récentes. Constat DESCRIPTIF : "
               "aucune méthode n'est écartée sur ce seul motif.")),
        extras={'repris_de': 'glm_apc',
                'cal_significatif': bool(glm_apc.get('cal_significatif')),
                'F_calendaire': glm_apc.get('F_calendaire')})


# =============================================================================
#  BFCC-H4 — PROVENANCE ET PLAUSIBILITÉ DU LOSS RATIO A PRIORI
# =============================================================================

#: Les cinq voies du guide (§2.b.i p14), de la plus assumée à la plus dérivée.
#: L'ordre est celui du guide ; il ne classe pas explicitement, mais il place le
#: calcul sur historique en dernier et le fait suivre d'un avertissement sur la
#: dispersion des S/P obtenus.
PROVENANCES = {
    'ultime_apriori': "charge ultime a priori fournie par l'actuaire",
    'manuel':         "loss ratio fourni par l'actuaire (tarification, plan à "
                      "moyen terme, benchmark de marché ou jugement d'expert)",
    'matures':        "calculé sur l'historique — dérivé des ultimes Chain Ladder",
    'refuse':         "non dérivable de l'historique",
}


def _juger_loss_ratio(
    lr:               float,
    cv:               float,
    plage_alerte:     tuple,
    plage_dure:       tuple,
    cv_max:           float,
    ecart_reference:  float,
    lr_reference:     Optional[float],
    lr_reference_src: str,
) -> tuple:
    """Statut d'un loss ratio et les motifs qui l'expliquent.

    Hiérarchie : hors plage DURE, la valeur est invraisemblable et la méthode
    tombe. À l'intérieur, trois motifs peuvent seulement la faire passer À
    JUSTIFIER — plage d'alerte, dispersion, écart à la référence de marché.
    Aucun d'eux ne peut relever un statut déjà tombé.
    """
    if not (plage_dure[0] <= lr <= plage_dure[1]):
        return NON_VALIDEE, [f"loss ratio de {lr:.1%}, hors de la plage dure "
                             f"[{plage_dure[0]:.0%} – {plage_dure[1]:.0%}]"]
    motifs: List[str] = []
    if not (plage_alerte[0] <= lr <= plage_alerte[1]):
        motifs.append(f"loss ratio de {lr:.1%}, hors de la plage plausible "
                      f"[{plage_alerte[0]:.0%} – {plage_alerte[1]:.0%}]")
    if cv > cv_max:
        motifs.append(f"dispersion de {cv:.1%} entre années matures "
                      f"(> {cv_max:.0%})")
    if lr_reference and abs(lr - lr_reference) > ecart_reference:
        motifs.append(f"écart de {abs(lr - lr_reference):.1%} avec la "
                      f"référence de marché {lr_reference:.1%} "
                      f"({lr_reference_src or 'source non précisée'})")
    return (A_JUSTIFIER if motifs else VALIDEE), motifs


def bfcc_h4_apriori(
    bf:                Dict,
    lr_plage_alerte:   tuple,
    lr_plage_dure:     tuple,
    cv_max:            float,
    ecart_reference:   float,
    lr_reference:      Optional[float] = None,
    lr_reference_src:  str = '',
) -> ResultatHypothese:
    """BFCC-H4 — le loss ratio a priori est-il exploitable, et d'où vient-il ?

    ⚠️ PORTE SUR LE LOSS RATIO QUE N3 EMPLOIE RÉELLEMENT. Jusqu'à ce lot, N2
    calculait SON PROPRE loss ratio — sur `C[i, dernière colonne connue]`, donc
    sur le PAYÉ À DATE et non sur l'ultime, contre la figure 14 du guide qui
    divise la charge ultime par la prime acquise. Mesuré : il sous-estimait le
    loss ratio de 9,08 % sur GenIns et de 4,39 % sur RAA, toujours à la baisse,
    et c'est pourtant lui que le rapport affichait. Deux loss ratios concurrents
    dans un même livrable : un seul propriétaire désormais, N3.

    ⚠️ LA PLAGE DE PLAUSIBILITÉ COMPTE VRAIMENT, MAINTENANT. L'ancien score valait
    `100 − CV×200` : il ne regardait QUE la dispersion. Le drapeau de plage était
    calculé puis jamais lu par la sélection. Mesuré sur GenIns : un loss ratio de
    364,7 % obtenait 81/100 et passait la gate, un loss ratio de 4,6 % aussi.

    LES BORNES S'APPLIQUENT AUSSI AU LOSS RATIO FOURNI. L'actuaire assume son
    chiffre, et sa provenance est meilleure ; un loss ratio de 900 % reste un
    loss ratio de 900 %.
    """
    base = dict(code='BFCC-H4',
                libelle="Provenance et plausibilité du loss ratio a priori",
                source_critere=SOURCE_JUGEMENT,
                critique_pour=(BF,))
    critere = (f"plage dure {lr_plage_dure[0]:.0%}–{lr_plage_dure[1]:.0%} → "
               f"non validée ; plage d'alerte {lr_plage_alerte[0]:.0%}–"
               f"{lr_plage_alerte[1]:.0%} et CV ≤ {cv_max:.0%} → validée")

    source  = str(bf.get('source_lr', 'non calculée'))
    detail  = bf.get('detail_lr') or {}
    retenues = list(detail.get('annees_retenues', []))
    ecartees = list(detail.get('annees_ecartees', []))
    cv       = float(detail.get('cv', 0.0) or 0.0)

    extras = {'source': source, 'provenance': PROVENANCES.get(source, source),
              'annees_retenues': retenues, 'annees_ecartees': ecartees,
              'cv': cv, 'fenetre': detail.get('fenetre'),
              'lr_reference': lr_reference}

    # ── Le a priori a été refusé faute d'années exploitables ──────────────────
    if source == 'refuse':
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None, critere=critere,
            message=(
                f"BFCC-H4 NON TESTABLE — le loss ratio a priori n'a pas pu être "
                f"dérivé de l'historique : {len(retenues)} année(s) exploitable(s) "
                f"sur la fenêtre"
                + (f", {len(ecartees)} écartée(s) pour cadence non admissible"
                   if ecartees else "")
                + ". Avec une seule année, la dispersion vaut zéro PAR "
                  "CONSTRUCTION et validerait le résultat là où l'information "
                  "manque. Fournir un loss ratio ou une charge ultime a priori "
                  "(guide §2.b.i p14) active la méthode."),
            extras=extras)

    if not bf.get('disponible', False):
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None, critere=critere,
            message=("BFCC-H4 NON TESTABLE — Bornhuetter-Ferguson n'a pas été "
                     "calculée, il n'y a donc pas de loss ratio a priori à juger."),
            extras=extras)

    # ── Charge ultime a priori directe : pas de loss ratio à borner ───────────
    if source == 'ultime_apriori':
        return ResultatHypothese(
            **base, statut=VALIDEE, valeur=None, critere=critere,
            message=("BFCC-H4 VALIDÉE — la charge ultime a priori est fournie "
                     "directement par l'actuaire, forme d'origine de "
                     "Bornhuetter-Ferguson (1972). Aucun loss ratio n'est "
                     "dérivé du triangle : l'a priori est pleinement exogène."),
            extras=extras)

    lr = bf.get('lr_apriori')
    if lr is None:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None, critere=critere,
            message="BFCC-H4 NON TESTABLE — aucun loss ratio a priori publié.",
            extras=extras)

    lr = float(lr)
    statut, motifs = _juger_loss_ratio(
        lr, cv, lr_plage_alerte, lr_plage_dure, cv_max, ecart_reference,
        lr_reference, lr_reference_src)

    provenance = PROVENANCES.get(source, source)
    if source == 'matures':
        provenance += (" — BF corrige l'ALLOCATION de Chain Ladder entre années "
                       "d'origine, mais en hérite le NIVEAU")

    message = (f"BFCC-H4 {statut} — loss ratio a priori = {lr:.1%}, "
               f"provenance : {provenance}."
               + (f" À justifier : {' ; '.join(motifs)}." if motifs else ""))

    return ResultatHypothese(
        **base, statut=statut, valeur=round(lr, 6), critere=critere,
        message=message, extras=extras)


# =============================================================================
#  BFCC-H5 — STABILITÉ TEMPORELLE DU LOSS RATIO
# =============================================================================

def _pente_et_significativite(x: np.ndarray, y: np.ndarray):
    """Pente OLS, statistique t, p-valeur bilatérale et moyenne de `y`.

    `None` si les abscisses ne se distinguent pas ou si `y` est de moyenne nulle
    — une dérive RELATIVE n'y aurait pas de sens.

    AJUSTEMENT PARFAIT → `p = 1`, la pente ne pouvant pas être déclarée
    significative. Même convention que `_regression_origine` de CLM, et le bon
    verdict actuariel : un loss ratio rigoureusement plat n'est pas une absence
    d'information sur la dérive, c'en est la preuve la plus forte.
    """
    x_moy = float(np.mean(x))
    sxx   = float(np.sum((x - x_moy) ** 2))
    y_moy = float(np.mean(y))
    if sxx <= 0 or y_moy == 0:
        return None
    pente = float(np.sum((x - x_moy) * (y - y_moy)) / sxx)
    resid = y - ((y_moy - pente * x_moy) + pente * x)
    ddl   = len(x) - 2
    sce   = float(resid @ resid)
    if ddl <= 0 or sce <= 0:
        return pente, 0.0, 1.0, y_moy
    se = float(np.sqrt((sce / ddl) / sxx))
    t  = pente / se if se > 0 else 0.0
    return pente, t, 2.0 * float(_loi_t.sf(abs(t), ddl)), y_moy


def bfcc_h5_stabilite_lr(
    ultimates_cl: Optional[Sequence[float]],
    exposition:   Optional[Sequence[float]],
    cadence_ok:   Optional[Sequence[bool]],
) -> ResultatHypothese:
    """BFCC-H5 — le loss ratio dérive-t-il d'une année d'origine à l'autre ?

    Régression du loss ratio à l'ultime `U_CL[i] / exposition[i]` sur l'indice
    d'année, et test de Student sur la pente. Le guide décrit exactement cette
    lecture (p15) : il montre l'actuaire comparant les S/P historiques, écartant
    une année non représentative, et proposant de les recaler au niveau de
    l'année courante par une méthode « as-if ».

    CALCULÉE SUR TOUTES LES ANNÉES ADMISSIBLES, pas sur la seule fenêtre mature :
    plus de points, donc plus de puissance. Le bruit de projection des années
    jeunes gonfle le résidu et rend le test CONSERVATEUR — il rate des dérives,
    il n'en invente pas. C'est le sens acceptable de l'erreur pour un test dont
    la conclusion négative exclut une méthode.
    """
    base = dict(code='BFCC-H5',
                libelle="Stabilité temporelle du loss ratio",
                source_critere=SOURCE_JUGEMENT,
                critere=(f"pente du loss ratio : p ≥ {H5_P_TENDANCE} → validée ; "
                         f"p < {H5_P_TENDANCE_FORT} → non validée"),
                critique_pour=(CC,))

    if ultimates_cl is None or exposition is None:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("BFCC-H5 NON TESTABLE — aucune mesure d'exposition n'a été "
                     "fournie : le loss ratio par année n'est pas calculable."),
            extras={})

    U = np.asarray(ultimates_cl, dtype=float)
    E = np.asarray(exposition, dtype=float)
    n = min(len(U), len(E))
    admis = (np.ones(n, dtype=bool) if cadence_ok is None
             else np.asarray(cadence_ok, dtype=bool)[:n])

    idx = [i for i in range(n)
           if admis[i] and np.isfinite(U[i]) and np.isfinite(E[i]) and E[i] > 0]
    lr = np.array([U[i] / E[i] for i in idx], dtype=float)
    x  = np.array(idx, dtype=float)

    detail = tuple({'annee': i, 'loss_ratio': round(float(U[i] / E[i]), 6)}
                   for i in idx)

    if len(idx) < H5_MIN_ANNEES or not SCIPY_OK or _loi_t is None:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=(f"BFCC-H5 NON TESTABLE — {len(idx)} année(s) exploitable(s), "
                     f"minimum {H5_MIN_ANNEES}" +
                     ("" if SCIPY_OK and _loi_t is not None
                      else " (scipy indisponible)") + "."),
            detail=detail, extras={'n': len(idx)})

    ajust = _pente_et_significativite(x, lr)
    if ajust is None:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message="BFCC-H5 NON TESTABLE — les années ne se distinguent pas.",
            detail=detail, extras={'n': len(idx)})
    pente, t, p, lr_moy = ajust
    derive_rel = pente / abs(lr_moy)

    if p < H5_P_TENDANCE_FORT:
        statut = NON_VALIDEE
    elif p < H5_P_TENDANCE:
        statut = A_JUSTIFIER
    else:
        statut = VALIDEE

    consequence = (
        "Cape Cod met un loss ratio UNIQUE en commun sur toutes les années : "
        "une dérive le rend trop bas pour les années récentes, celles qui "
        "portent l'essentiel de la réserve. Bornhuetter-Ferguson, dont l'a "
        "priori est par année, reste calculable — la dérive s'y corrige par un "
        "recalage « as-if » (guide p15) que ce lot signale sans l'appliquer."
        if statut != VALIDEE else
        "Le loss ratio ne montre pas de dérive détectable : la mise en commun "
        "de Cape Cod est fondée. ⚠️ sur un portefeuille volatil, ce test ne "
        "voit pas une dérive modérée — cf. l'angle mort en en-tête.")

    return ResultatHypothese(
        **base, statut=statut, valeur=round(p, 6),
        message=(f"BFCC-H5 {statut} — dérive du loss ratio de "
                 f"{derive_rel:+.1%} par an sur {len(idx)} années "
                 f"(p = {p:.4f}). " + consequence),
        detail=detail,
        extras={'n': len(idx), 'pente': round(pente, 8),
                'derive_relative_annuelle': round(derive_rel, 6),
                't': round(t, 4), 'lr_moyen': round(lr_moy, 6)})


# =============================================================================
#  POINT D'ENTRÉE
# =============================================================================

def verifier_hypotheses_bfcc(
    pct_brut:     Sequence[float],
    cadence_ok:   Sequence[bool],
    bf:           Dict,
    cape_cod:     Dict,
    clm_h1:       Optional[Dict]            = None,
    glm_apc:      Optional[Dict]            = None,
    ultimates_cl: Optional[Sequence[float]] = None,
    exposition:   Optional[Sequence[float]] = None,
    lr_reference: Optional[float]           = None,
    lr_reference_src: str                   = '',
) -> Dict[str, Any]:
    """Les cinq hypothèses de Bornhuetter-Ferguson et Cape Cod, d'un bloc.

    ⚠️ S'EXÉCUTE APRÈS N3, ET C'EST VOULU. BFCC-H4 juge le loss ratio que N3
    emploie réellement, BFCC-H5 les loss ratios par année qu'il implique : une
    hypothèse qui porte sur un résultat ne peut pas être évaluée avant lui.
    C'est la contrepartie assumée d'avoir donné à N3 la propriété unique du loss
    ratio — l'alternative aurait été d'en recalculer un second en N2, c'est-à-dire
    exactement le défaut que ce lot supprime.
    """
    from .n3.bf_cape_cod import (CV_LR_MAX, ECART_LR_REFERENCE,
                                 LR_PLAGE_ALERTE, LR_PLAGE_DURE)

    h1 = bfcc_h1_independance(clm_h1)
    h2 = bfcc_h2_cadence(pct_brut, cadence_ok)
    h3 = bfcc_h3_structure(glm_apc)
    h4 = bfcc_h4_apriori(bf, LR_PLAGE_ALERTE, LR_PLAGE_DURE, CV_LR_MAX,
                         ECART_LR_REFERENCE, lr_reference, lr_reference_src)
    h5 = bfcc_h5_stabilite_lr(ultimates_cl, exposition, cadence_ok)

    hypotheses = {h.code: h for h in (h1, h2, h3, h4, h5)}
    return {
        'hypotheses':          {c: h.synthese() for c, h in hypotheses.items()},
        'couverture_cadence':  couverture_cadence_par_annee(h2),
        'recoupement_lr':      _recoupement_loss_ratios(bf, cape_cod),
        'statuts':             {c: h.statut for c, h in hypotheses.items()},
        'objets':              hypotheses,
    }


# =============================================================================
#  AFFICHAGE — SOURCE UNIQUE POUR LES LIVRABLES N5
# =============================================================================

#: Ordre de présentation, fixe : il suit la numérotation, pas le résultat.
CODES = ('BFCC-H1', 'BFCC-H2', 'BFCC-H3', 'BFCC-H4', 'BFCC-H5')

LIBELLES = {
    'BFCC-H1': "BFCC-H1 — Indépendance des années d'origine",
    'BFCC-H2': "BFCC-H2 — Cadence de développement admissible",
    'BFCC-H3': "BFCC-H3 — Structure multiplicative sans effet calendaire",
    'BFCC-H4': "BFCC-H4 — Provenance et plausibilité du loss ratio a priori",
    'BFCC-H5': "BFCC-H5 — Stabilité temporelle du loss ratio",
}


def lignes_hypotheses_bfcc(n2: Optional[Dict]) -> List[Dict[str, Any]]:
    """Les cinq verdicts, prêts à afficher — commentaire, Excel, Word, rapport.

    SOURCE UNIQUE. Les quatre livrables affichaient auparavant l'ancienne H3
    chacun à sa façon, en lisant `n2['h3_apriori_bf']` ; cette clé a disparu avec
    elle, et un `.get(…, {})` laissé en place aurait affiché « 0,0 % » — un
    chiffre faux, exactement le silence que ce lot supprime. Une hypothèse non
    évaluée ressort ici NON TESTABLE, jamais en valeur par défaut.
    """
    hyps = (n2 or {}).get('bfcc', {}).get('hypotheses', {})
    lignes = []
    for code in CODES:
        h = hyps.get(code, {})
        lignes.append({
            'code':    code,
            'libelle': LIBELLES[code],
            'statut':  str(h.get('statut', NON_TESTABLE)),
            'message': str(h.get('message', "Hypothèse non évaluée.")),
            'critere': str(h.get('critere', '—')),
            'source':  str(h.get('source_critere', '—')),
            'ok':      str(h.get('statut', NON_TESTABLE)) == VALIDEE,
        })
    return lignes


# =============================================================================
#  RECOUPEMENT INFORMATIF DES DEUX LOSS RATIOS
# =============================================================================

def _recoupement_loss_ratios(bf: Dict, cape_cod: Dict) -> Dict[str, Any]:
    """Compare le loss ratio a priori de BF et le loss ratio poolé de Cape Cod.

    Les deux sortent des mêmes données par deux chemins : moyenne des ratios sur
    la fenêtre mature d'un côté, rapport des sommes sur toutes les années
    admissibles de l'autre. Un écart matériel signale une exposition douteuse.

    ⚠️ CE N'EST PAS UN TEST D'INDÉPENDANCE, ET IL NE FAUT PAS LE LIRE AINSI.
    Vérifié algébriquement puis numériquement : si l'on pondérait la moyenne de
    BF par `exposition × cadence` SUR TOUTES LES ANNÉES, on obtiendrait

        Σ (expoᵢ·αᵢ)·(Uᵢ/expoᵢ) / Σ (expoᵢ·αᵢ) = Σ Cᵢ / Σ (expoᵢ·αᵢ) = LR_Cape_Cod

    puisque `Uᵢ = Cᵢ/αᵢ`, et les deux méthodes partageant la formule d'IBNR
    `LR × expo × (1 − α)`, BORNHUETTER-FERGUSON DEVIENDRAIT CAPE COD À
    L'IDENTIQUE. Mesuré : écart de 4,4·10⁻⁵ sur GenIns et RAA, soit l'arrondi.
    C'est la SÉLECTION d'une fenêtre, et elle seule, qui maintient les deux
    méthodes distinctes. Un écart nul ici serait une alarme, pas une validation.
    """
    lr_bf = bf.get('lr_apriori') if bf.get('disponible') else None
    lr_cc = cape_cod.get('lr_cape_cod') if cape_cod.get('disponible') else None
    if lr_bf is None or lr_cc is None:
        return {'comparable': False, 'lr_bf': lr_bf, 'lr_cape_cod': lr_cc,
                'message': "Recoupement impossible : l'un des deux loss ratios "
                           "n'est pas calculé."}
    ecart = abs(float(lr_bf) - float(lr_cc))
    return {
        'comparable': True,
        'lr_bf': float(lr_bf), 'lr_cape_cod': float(lr_cc),
        'ecart': round(ecart, 6),
        'message': (
            f"Loss ratio a priori BF = {float(lr_bf):.1%} contre "
            f"{float(lr_cc):.1%} pour le loss ratio poolé de Cape Cod, soit "
            f"{ecart:.1%} d'écart. Deux chemins sur les mêmes données : un écart "
            f"marqué invite à vérifier l'exposition fournie. INFORMATIF — ce "
            f"n'est pas un test d'indépendance, les deux ratios partagent leurs "
            f"données d'entrée."),
    }
