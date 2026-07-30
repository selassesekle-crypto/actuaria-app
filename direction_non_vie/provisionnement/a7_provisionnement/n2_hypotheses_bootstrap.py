# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n2_hypotheses_bootstrap.py  —  Les hypothèses propres au Bootstrap ODP
#                                 (BOOT-H1 … BOOT-H4)
# =============================================================================
#
#  CE MODULE PRODUIT DES VERDICTS, IL N'EN TIRE AUCUNE CONSÉQUENCE. Même
#  discipline que `n2_hypotheses_clm` et `n2_hypotheses_bfcc`, et vérifiée par le
#  même verrou de périmètre côté tests : aucun score, aucun poids, aucune
#  exclusion de méthode n'est décidée ici.
#
#  ⚠️ CES HYPOTHÈSES NE PEUVENT PAS ÉCARTER UNE MÉTHODE DU BEST ESTIMATE, ET
#  C'EST STRUCTUREL. Le Bootstrap ODP ne figure pas parmi les méthodes pondérées
#  du BE (`_CLES_N3` en N4 : Chain Ladder, Bornhuetter-Ferguson, Cape Cod) — il
#  produit une DISPERSION, pas un point estimate concurrent. Ce que ces
#  hypothèses peuvent invalider est donc un LIVRABLE, les percentiles
#  `reserve_p*_boot`, et rien d'autre. D'où `critique_pour =
#  ('percentiles_bootstrap',)` : une cible de livrable, jamais un nom de méthode.
#  Le Best Estimate ne bouge pas d'un centime quand BOOT-H3 ou BOOT-H4 tombe.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  CE QUE DIT LE GUIDE, CE QU'IL DIT MAL, ET CE QU'IL NE DIT PAS
#
#  · §3.c.i p28 — le guide pose que les résidus de Pearson doivent être
#    indépendants et identiquement distribués. C'est BOOT-H1.
#
#    ⚠️ COQUILLE DU GUIDE, RELEVÉE ET NON REPRISE. Le texte décrit les résidus
#    normalisés comme étant « d'espérance 1 et d'écart-type 0 ». Les deux
#    grandeurs sont interverties : un écart-type nul rendrait tous les résidus
#    identiques et le rééchantillonnage sans objet. La définition employée ici
#    est celle d'England & Verrall — espérance 0, écart-type 1.
#
#  · §3.c.ii p29 — le guide exige des incréments strictement positifs pour
#    l'ODP, et signale que le Bootstrap de Mack, lui, n'a pas cette contrainte.
#    C'est BOOT-H4.
#
#    ⚠️ CONTRADICTION INTERNE AU GUIDE, TRANCHÉE EN FAVEUR DE p29. Le §3.d.ii
#    p32 affirme que le Bootstrap ne demande « pas d'hypothèses supplémentaires
#    à celles du Chain-Ladder ». C'est faux pour l'ODP et le guide se contredit
#    lui-même treize pages plus loin : Chain Ladder accepte parfaitement des
#    incréments négatifs (recours, subrogation), l'ODP non — le modèle de
#    Poisson sur-dispersé n'est pas défini pour une espérance négative. La
#    version retenue ici est celle de p29, qui est aussi celle de la théorie.
#
#  · SUR L'HOMOGÉNÉITÉ DE φ, LE GUIDE NE DIT RIEN. Pas une ligne. Le modèle
#    croisé d'England & Verrall (2002) suppose pourtant `Var(m_ij) = φ·E(m_ij)`
#    avec UN SEUL φ pour tout le triangle : c'est ce φ unique qui calibre les
#    résidus rééchantillonnés, donc toute la largeur de la distribution. BOOT-H3
#    est donc intégralement NOTRE JUGEMENT, signalé comme tel.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  DEUX HYPOTHÈSES SONT REPRISES, PAS RÉIMPLÉMENTÉES
#
#  · BOOT-H1 republie le verdict de CLM-H1. L'indépendance que l'ODP demande est
#    celle des incréments par période d'origine — la même que Chain Ladder, déjà
#    testée par les signes par diagonale de l'annexe 9.d et validée sur
#    l'exemple chiffré du guide.
#  · BOOT-H2 republie le verdict du GLM Poisson âge-cohorte (`glm_apc`). Le
#    modèle croisé `x_i·y_j` de l'ODP est EXACTEMENT celui que ce GLM ajuste ;
#    son test F calendaire est donc le test de la structure multiplicative.
#    Construire un troisième ajusteur du même modèle serait une faute
#    d'architecture — c'est déjà l'argument de BFCC-H3.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  BOOT-H3 — POURQUOI CETTE STATISTIQUE, ET PAS UNE AUTRE
#
#  Deux candidates ont été essayées puis ÉCARTÉES SUR MESURE, pas sur intuition :
#
#  · Rapport max/min des φ par groupe. Sa loi sous l'hypothèse nulle est énorme
#    (médiane 4,6 · q95 17,9 · q99 57,3 sur des triangles à φ CONSTANT), et sa
#    puissance nulle : un φ doublé en développement est détecté 1,6 % du temps,
#    soit MOINS que le taux de fausse alarme. Une statistique qui détecte moins
#    souvent qu'elle ne se trompe n'est pas un test.
#  · p-valeur analytique de Spearman. Elle donne 13,0 % à 19,5 % de fausses
#    alarmes pour un seuil nominal de 5 %. La cause est structurelle : les
#    résidus de Pearson NE SONT PAS indépendants — l'ajustement d'England &
#    Verrall reproduit exactement la diagonale observée, ce qui contraint leurs
#    sommes par ligne et par colonne. Spearman suppose l'inverse.
#
#  Ce qui est retenu : la corrélation de rang ρ entre |résidu| et l'indice de
#  l'axe — statistique DIRIGÉE, parce que l'alternative qui compte en pratique
#  n'est pas « φ diffère arbitrairement » mais « φ croît avec le développement »
#  (les queues sont plus volatiles) — CALIBRÉE PAR NULLE PARAMÉTRIQUE : le seuil
#  est tiré du triangle lui-même, en régénérant des triangles depuis SON PROPRE
#  ajustement avec un φ constant. Le test hérite ainsi de sa taille, de ses
#  volumes et de sa corrélation résiduelle.
#
#  ⚠️ PUISSANCE MESURÉE — UN « VALIDÉE » NE CERTIFIE PAS L'HOMOGÉNÉITÉ DE φ.
#  Campagnes de 100 triangles à vérité connue, nulle de 120 régénérations. Le
#  nombre de triangles RÉELLEMENT exploités est donné : une campagne trop
#  dégarnie ne mesure rien, et c'est un piège dans lequel ce lot est tombé une
#  fois (cf. l'axe calendaire ci-dessous).
#
#        profil de φ (axe développement)   détecté à 5 %   triangles exploités
#        constant φ=20   (témoin)               5,0 %            100/100
#        constant φ=100  (témoin)               6,4 %             78/100
#        ×2   (70 → 140)                       18,1 %             94/100
#        ×5   (40 → 200)                       53,0 %            100/100
#        ×20  (20 → 400)                       67,4 %             92/100
#
#  Les deux témoins encadrent le niveau nominal de 5 % : la calibration est
#  juste. Mais une hétérogénéité modérée passe inaperçue quatre fois sur cinq.
#  Le statut VALIDÉE dit qu'on ne voit pas d'hétérogénéité, pas qu'il n'y en a
#  pas.
#
#  ⚠️⚠️ AXE CALENDAIRE — FAIBLE, ET AVEUGLE À CE QUI COMPTE LE PLUS.
#
#        profil de φ (axe calendaire)      détecté à 5 %   triangles exploités
#        constant (témoin)                      2,0 %            100/100
#        choc ×4  sur les 3 dernières diag      7,0 %            100/100
#        choc ×10 sur les 3 dernières diag     29,0 %            100/100
#        choc ×10 sur les 5 dernières diag      8,0 %            100/100
#        DÉRIVE RÉGULIÈRE 50 → 500              1,0 %            100/100
#
#  Lecture, et elle est contre-intuitive. Un choc BRUTAL ET LOCALISÉ sur les
#  toutes dernières diagonales est vu une fois sur trois. Étalez le même choc sur
#  cinq diagonales et la détection s'effondre à 8 % ; faites-en une dérive
#  RÉGULIÈRE et elle tombe à 1 %, SOUS le témoin — c'est-à-dire aucune puissance.
#
#  La cause est l'ajustement lui-même : une dérive régulière le long des années
#  calendaires est absorbée par les paramètres `x_i` et `y_j`, qui la répartissent
#  entre origine et développement. Il n'en reste rien dans les résidus.
#  ⚠️ ET C'EST LE MOTIF QUI COMPTE EN PRATIQUE — un régime d'inflation de
#  sinistralité produit une dérive régulière, pas un choc sur trois diagonales.
#
#  Aucun contournement n'est proposé : il n'y a pas d'information résiduelle à
#  exploiter. → Ce que BOOT-H3 ne peut pas voir, CLM-H1 le voit : son test des
#  signes par diagonale porte sur les MONTANTS et non sur leur dispersion, et il
#  n'est pas aveuglé par l'absorption dans le fit. Les deux hypothèses sont
#  complémentaires, et BOOT-H1 republie justement CLM-H1 — c'est elle qu'il faut
#  lire pour l'effet calendaire, pas celle-ci.
#
#  ⚠️ POURQUOI 400 RÉGÉNÉRATIONS ET UNE ZONE GRISE LARGE — MESURÉ.
#  À 200 régénérations, la p-valeur d'un même triangle varie de 0,030 à 0,105
#  selon la graine (RECOURS, axe développement, p vrai ≈ 0,06) : un seuil dur à
#  0,05 rendrait le verdict DÉPENDANT DE LA GRAINE dans un livrable réglementaire
#  — 2 graines sur 8 rejetaient, 6 validaient. Deux corrections, ensemble :
#    · `N_REP_CALIBRATION = 400` réduit l'étendue de 0,075 à 0,040 ;
#    · la zone grise [0,01 ; 0,10] absorbe le reste — l'erreur de Monte-Carlo
#      vaut ±0,029 à p = 0,10 et ±0,010 à p = 0,01 pour n_rep = 400, soit moins
#      que la largeur de la zone. Vérifié : les 8 graines donnent le MÊME statut.
#  La graine est FIXE et publiée : un livrable réglementaire doit être
#  reproductible à l'identique, chiffre pour chiffre.
#
#  Références
#  ----------
#  · England, P.D. & Verrall, R.J. (2002). "Stochastic Claims Reserving in
#    General Insurance", British Actuarial Journal 8(3), pp. 443-518.
#    Modèle croisé sur-dispersé : E(m_ij) = x_i·y_j, Var(m_ij) = φ·x_i·y_j.
#  · Institut des Actuaires (2023). Guide de provisionnement des sinistres en
#    assurance non-vie — §3.c.i p28 (résidus i.i.d.), §3.c.ii p29 (incréments
#    strictement positifs), §3.d.ii p32 (l'affirmation contradictoire).
# =============================================================================

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from direction_non_vie.services.nv_triangle_negatifs import FRAC_NEG_MAX_DEFAUT

from .n2_hypotheses_clm import (
    A_JUSTIFIER, NON_TESTABLE, NON_VALIDEE, VALIDEE,
    SOURCE_GUIDE, SOURCE_JUGEMENT,
    ResultatHypothese, SCIPY_OK,
)
from .n3.bootstrap_odp import calculer_fitted_et_residus
from .n3.chain_ladder import calculer_facteurs

try:                                                   # pragma: no cover
    from scipy.stats import spearmanr as _spearmanr
except ImportError:                                    # pragma: no cover
    _spearmanr = None

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  CIBLE DE CRITICITÉ — UN LIVRABLE, PAS UNE MÉTHODE
# =============================================================================

#: Ce que BOOT-H3 et BOOT-H4 peuvent invalider. Ce n'est PAS un nom de méthode,
#: et la distinction est le cœur de ce lot : le Bootstrap ODP ne pèse pas dans le
#: Best Estimate, il en mesure la dispersion. Rejeter ses hypothèses retire les
#: percentiles `reserve_p*_boot` du livrable — le BE, le SCR calculé sur σ_EIOPA
#: et la Risk Margin restent inchangés.
PERCENTILES_BOOT = 'percentiles_bootstrap'


# =============================================================================
#  BOOT-H3 — PARAMÈTRES DE CALIBRATION, FIGÉS ET PUBLIÉS
# =============================================================================

AXES: Tuple[str, ...] = ('developpement', 'origine', 'calendaire')

#: L'indice porté par chaque axe, pour une cellule (i, j) du triangle.
_INDICE = {
    'developpement': lambda i, j: j,
    'origine':       lambda i, j: i,
    'calendaire':    lambda i, j: i + j,
}

#: Nombre de triangles régénérés sous l'hypothèse nulle. 400 et non 200 :
#: à 200, le verdict d'un même triangle dépendait de la graine (cf. en-tête).
N_REP_CALIBRATION = 400

#: Graine FIXE. Sa valeur est arbitraire ; ce qui ne l'est pas, c'est qu'elle
#: soit gelée et publiée dans le résultat — deux exécutions du même dossier
#: doivent rendre le même chiffre, sans quoi le livrable n'est pas opposable.
GRAINE_CALIBRATION = 2023

#: Bornes du verdict. La zone grise est LARGE PAR MESURE, pas par prudence
#: vague : elle vaut plus que l'erreur de Monte-Carlo à n_rep = 400.
P_REJET     = 0.01
P_VIGILANCE = 0.10

#: Un axe qui compte moins de groupes distincts ne porte pas de tendance.
H3_MIN_GROUPES = 3

#: Une nulle trop dégarnie (régénérations rejetées faute de triangle cumulé
#: strictement positif) ne calibre plus rien.
H3_MIN_NULLE = 50

LIBELLES = {
    'BOOT-H1': "BOOT-H1 — Indépendance des incréments",
    'BOOT-H2': "BOOT-H2 — Structure multiplicative x_i · y_j",
    'BOOT-H3': "BOOT-H3 — Homogénéité de la sur-dispersion φ",
    'BOOT-H4': "BOOT-H4 — Positivité des incréments ajustés",
}

#: Ordre de présentation, fixe : il suit la numérotation, pas le résultat.
CODES: Tuple[str, ...] = ('BOOT-H1', 'BOOT-H2', 'BOOT-H3', 'BOOT-H4')


# =============================================================================
#  BOOT-H1 — INDÉPENDANCE DES INCRÉMENTS                        (reprise CLM-H1)
# =============================================================================

def boot_h1_independance(clm_h1: Optional[Dict]) -> ResultatHypothese:
    """BOOT-H1 — reprend le verdict de CLM-H1, sans le recalculer.

    Le guide (§3.c.i p28) demande des résidus indépendants ; l'indépendance
    sous-jacente est celle des incréments par période d'origine, c'est-à-dire
    exactement l'hypothèse de Chain Ladder, déjà testée par les signes par
    diagonale de l'annexe 9.d et validée sur l'exemple chiffré du guide.

    Prend la SYNTHÈSE publiée par `verifier_hypotheses_clm` — un dict — et non
    l'objet interne : reprendre un verdict ne doit pas obliger le module qui le
    produit à élargir son contrat pour être relu.

    ⚠️ DESCRIPTIF : `critique_pour = ()`. Un effet calendaire ne disqualifie pas
    le rééchantillonnage, il biaise identiquement le point estimate Chain Ladder
    et la distribution qui l'entoure. Le gater ici reviendrait à sanctionner le
    Bootstrap pour un défaut qui n'est pas le sien.
    """
    base = dict(code='BOOT-H1',
                libelle="Indépendance des incréments",
                critere="reprise du verdict CLM-H1",
                source_critere=SOURCE_GUIDE,
                critique_pour=())
    if not clm_h1:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("BOOT-H1 NON TESTABLE — le verdict CLM-H1 n'est pas "
                     "disponible ; l'hypothèse n'a donc pas été évaluée."),
            extras={'repris_de': 'CLM-H1'})

    base['critere'] = str(clm_h1.get('critere', base['critere']))
    return ResultatHypothese(
        **base,
        statut=str(clm_h1.get('statut', NON_TESTABLE)),
        valeur=clm_h1.get('valeur'),
        message=("BOOT-H1 = CLM-H1 : l'indépendance que demande le modèle ODP "
                 "(guide §3.c.i p28) est celle des incréments par période "
                 "d'origine, déjà testée pour Chain Ladder. "
                 + str(clm_h1.get('message', ''))),
        detail=tuple(dict(d) for d in clm_h1.get('detail', ())),
        extras={'repris_de': 'CLM-H1'},
    )


# =============================================================================
#  BOOT-H2 — STRUCTURE MULTIPLICATIVE                          (reprise glm_apc)
# =============================================================================

def boot_h2_structure(glm_apc: Optional[Dict]) -> ResultatHypothese:
    """BOOT-H2 — le triangle se réduit-il au produit `x_i · y_j` ?

    C'est le modèle croisé d'England & Verrall lui-même : `E(m_ij) = x_i·y_j`.
    Le GLM Poisson âge-cohorte ajuste EXACTEMENT ce modèle ; son test F
    calendaire est donc le test de cette hypothèse — un effet calendaire
    significatif est un effet « en plus » du produit des deux vecteurs.

    ⚠️ DESCRIPTIF : `critique_pour = ()`, pour la même raison que BFCC-H3. Le
    GLM APC n'a aucun effet décisionnel dans A7 ; lui en donner un ici mêlerait
    le risque de l'hypothèse à celui d'un module dont ce serait le premier usage
    gatant.
    """
    base = dict(code='BOOT-H2',
                libelle="Structure multiplicative x_i · y_j",
                critere=f"test F calendaire quasi-Poisson, p ≥ {P_VIGILANCE} → validée",
                source_critere=SOURCE_JUGEMENT,
                critique_pour=())

    if not glm_apc or not glm_apc.get('success') or not glm_apc.get('glm_disponible'):
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("BOOT-H2 NON TESTABLE — le GLM Poisson âge-cohorte n'a pas "
                     "produit de test calendaire exploitable."),
            extras={'repris_de': 'glm_apc'})

    p = glm_apc.get('p_calendaire')
    if p is None:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message="BOOT-H2 NON TESTABLE — p-valeur calendaire indisponible.",
            extras={'repris_de': 'glm_apc'})

    p = float(p)
    if p < P_REJET:
        statut = NON_VALIDEE
    elif p < P_VIGILANCE:
        statut = A_JUSTIFIER
    else:
        statut = VALIDEE

    return ResultatHypothese(
        **base, statut=statut, valeur=round(p, 6),
        message=(
            f"BOOT-H2 {statut} — structure multiplicative testée par le GLM "
            f"Poisson âge-cohorte : p = {p:.4f}. "
            + ("Le triangle se réduit au produit année d'origine × cadence, "
               "modèle croisé que suppose l'ODP d'England & Verrall."
               if statut == VALIDEE else
               "Un effet propre aux années calendaires subsiste au-delà du "
               "produit x_i · y_j : les incréments ajustés dont on tire les "
               "résidus sont alors mal centrés. Constat DESCRIPTIF — aucun "
               "livrable n'est retiré sur ce seul motif.")),
        extras={'repris_de': 'glm_apc',
                'cal_significatif': bool(glm_apc.get('cal_significatif')),
                'F_calendaire': glm_apc.get('F_calendaire')})


# =============================================================================
#  BOOT-H3 — HOMOGÉNÉITÉ DE φ                        ⚠️ critique (percentiles)
# =============================================================================

def rho_dispersion(
    residus:  np.ndarray,
    cellules: Sequence[Tuple[int, int]],
    axe:      str,
) -> Optional[float]:
    """Corrélation de rang entre |résidu| et l'indice de l'axe.

    Rend ρ SEUL, jamais la p-valeur analytique de Spearman : celle-ci suppose des
    observations indépendantes, ce que les résidus de Pearson ne sont pas
    (l'ajustement contraint leurs sommes par ligne et par colonne), et donne
    13 % à 19,5 % de fausses alarmes pour un seuil nominal de 5 %. Le seuil vient
    de `nulle_parametrique`.

    `residus` sont ceux que `calculer_fitted_et_residus` publie, DÉJÀ AJUSTÉS des
    degrés de liberté. Aucune remise à l'échelle n'est appliquée ici, et pas
    seulement par économie : les rangs sont invariants par constante positive,
    donc un facteur d'ajustement n'aurait AUCUN effet sur ρ. Le porter en
    paramètre laisserait croire qu'il en a un.

    `None` quand l'axe porte moins de `H3_MIN_GROUPES` groupes distincts — une
    tendance a besoin de plus de deux points pour exister.
    """
    if _spearmanr is None or not len(cellules):
        return None
    cle = _INDICE[axe]
    xs = np.array([cle(i, j) for (i, j) in cellules], dtype=float)
    if len(np.unique(xs)) < H3_MIN_GROUPES:
        return None
    ys = np.array([abs(residus[i, j]) for (i, j) in cellules], dtype=float)
    if len(np.unique(ys)) < 2:
        return None
    rho = _spearmanr(xs, ys)[0]
    return None if rho is None or not np.isfinite(rho) else float(rho)


def phi_par_axe(
    residus:  np.ndarray,
    cellules: Sequence[Tuple[int, int]],
) -> Dict[str, Dict[int, float]]:
    """La sur-dispersion observée groupe par groupe, sur les trois axes.

    C'est la CARTE que le verdict résume en un mot. Un « NON VALIDÉE » dit qu'il
    y a de l'hétérogénéité ; seul ce tableau dit OÙ elle est — et c'est lui qui a
    montré, en conception, que le problème se tient sur l'axe développement et
    nulle part ailleurs.

    φ_g = moyenne des carrés des résidus du groupe, résidus pris tels que
    `calculer_fitted_et_residus` les publie, c'est-à-dire DÉJÀ AJUSTÉS des degrés
    de liberté. Ce choix n'est pas cosmétique : la moyenne des φ_g pondérée par
    les effectifs redonne EXACTEMENT le φ global du Bootstrap, puisque
        Σ_g (n_g/N)·φ_g = (1/N)·Σ r²_bruts·(N/(N−p)) = Σ r²_bruts/(N−p) = φ.
    Une décomposition qui ne se recompose pas serait un TROISIÈME φ dans le
    système — la pathologie même que ce lot supprime. L'identité est verrouillée
    par test, et c'est elle qui a révélé qu'une remise à l'échelle superflue
    s'était glissée ici : elle faussait la carte de (N−p)/N, soit 34,5 % sur
    GenIns, sans rien changer aux rangs ni donc au verdict.
    """
    out: Dict[str, Dict[int, float]] = {}
    for axe in AXES:
        cle = _INDICE[axe]
        groupes: Dict[int, List[float]] = {}
        for (i, j) in cellules:
            groupes.setdefault(int(cle(i, j)), []).append(
                float(residus[i, j] ** 2))
        out[axe] = {g: float(np.mean(v)) for g, v in sorted(groupes.items())}
    return out


def nulle_parametrique(
    C:        np.ndarray,
    facteurs: np.ndarray,
    n_rep:    int = N_REP_CALIBRATION,
    graine:   int = GRAINE_CALIBRATION,
) -> Optional[Dict[str, np.ndarray]]:
    """Distribution de ρ SOUS LE MODÈLE AJUSTÉ SUR CE TRIANGLE-LÀ.

    On ajuste l'ODP au triangle réel, on régénère `n_rep` triangles depuis CET
    ajustement avec un φ CONSTANT — c'est l'hypothèse nulle de BOOT-H3 — et on
    recalcule ρ sur chacun, en refaisant tout le chemin (facteurs, ajustement,
    résidus) comme le ferait le code en production. Le seuil qui en sort est
    propre au triangle : à sa taille, à ses volumes, et à la corrélation que
    l'ajustement induit mécaniquement entre les résidus.

    LES TROIS AXES PARTAGENT LES MÊMES RÉGÉNÉRATIONS. C'est ce qui rend le test
    abordable : une seule campagne au lieu de trois, pour un coût mesuré de
    0,28 s à 0,59 s à n_rep = 200 contre 2,14 s à 2,24 s pour le Bootstrap
    lui-même à 5 000 simulations.

    Rend `None` si le triangle n'a pas de degrés de liberté — auquel cas il n'y a
    pas d'ajustement, donc pas de nulle à tirer.
    """
    C = np.asarray(C, dtype=float)
    m_fit, _, phi, _, n_obs, n_params, cellules = calculer_fitted_et_residus(
        C, np.asarray(facteurs, dtype=float))
    if n_obs - n_params <= 0 or phi <= 0 or not cellules:
        return None

    rng = np.random.default_rng(graine)
    n, m = C.shape
    nulle: Dict[str, List[float]] = {a: [] for a in AXES}

    for _ in range(int(n_rep)):
        M = np.zeros((n, m), dtype=float)
        for (i, j) in cellules:
            M[i, j] = phi * rng.poisson(max(m_fit[i, j], 1e-9) / phi)
        C_sim = np.cumsum(M, axis=1)
        # Un triangle régénéré non strictement positif n'est pas ajustable :
        # on le laisse tomber plutôt que de le rafistoler, ce qui déformerait
        # la nulle. Le compte des régénérations retenues est publié.
        if (C_sim <= 0).any():
            continue
        try:
            f_sim = np.asarray(calculer_facteurs(C_sim, 'standard')[0], dtype=float)
            _, res_sim, _, _, n_o, n_p, cel_sim = calculer_fitted_et_residus(
                C_sim, f_sim)
        except Exception:                              # pragma: no cover
            continue
        if n_o - n_p <= 0:
            continue
        for axe in AXES:
            r = rho_dispersion(res_sim, cel_sim, axe)
            if r is not None:
                nulle[axe].append(r)

    return {a: np.asarray(v, dtype=float) for a, v in nulle.items()}


def boot_h3_homogeneite_phi(
    C:        np.ndarray,
    facteurs: Sequence[float],
    n_rep:    int = N_REP_CALIBRATION,
    graine:   int = GRAINE_CALIBRATION,
) -> ResultatHypothese:
    """BOOT-H3 — un seul φ suffit-il pour tout le triangle ?

    L'hypothèse que le guide ne mentionne pas, et qui décide pourtant de toute
    la largeur de la distribution Bootstrap : le modèle croisé sur-dispersé pose
    `Var(m_ij) = φ · E(m_ij)` avec UN φ unique, et c'est ce φ qui calibre les
    résidus rééchantillonnés. S'il varie le long du développement, les
    percentiles sont trop étroits là où ça compte et trop larges ailleurs.

    ⚠️ CRITIQUE POUR LES PERCENTILES SEULEMENT. Le point estimate `be_bootstrap`
    n'en dépend pas — il vaut la réserve Chain Ladder par construction — et le
    Best Estimate ne le lit pas.
    """
    base = dict(code='BOOT-H3',
                libelle="Homogénéité de la sur-dispersion φ",
                critere=(f"ρ de rang |résidu| vs indice, nulle paramétrique "
                         f"({n_rep} régénérations, graine {graine}) ; "
                         f"p < {P_REJET} → rejet, "
                         f"p < {P_VIGILANCE} → à justifier"),
                source_critere=SOURCE_JUGEMENT,
                critique_pour=(PERCENTILES_BOOT,))

    if not SCIPY_OK or _spearmanr is None:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("BOOT-H3 NON TESTABLE — scipy indisponible, la corrélation "
                     "de rang ne peut pas être calculée."),
            extras={'graine': graine, 'n_rep_demande': n_rep})

    C = np.asarray(C, dtype=float)
    try:
        f = np.asarray(facteurs, dtype=float)
        _, residus, phi, _, n_obs, n_params, cellules = calculer_fitted_et_residus(C, f)
    except Exception as e:                             # pragma: no cover
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=f"BOOT-H3 NON TESTABLE — ajustement ODP impossible : {e}",
            extras={'graine': graine, 'n_rep_demande': n_rep})

    df = n_obs - n_params
    if df <= 0 or phi <= 0 or not cellules:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=(
                f"BOOT-H3 NON TESTABLE — le triangle n'a pas de degrés de "
                f"liberté (n_obs={n_obs}, n_params={n_params}, df={df}). "
                f"Sans ajustement il n'y a ni résidus ni φ à examiner ; le "
                f"Bootstrap lui-même est désactivé sur ce triangle."),
            extras={'n_obs': n_obs, 'n_params': n_params, 'df': df,
                    'graine': graine, 'n_rep_demande': n_rep})

    rho_obs = {a: rho_dispersion(residus, cellules, a) for a in AXES}
    carte = phi_par_axe(residus, cellules)

    nulle = nulle_parametrique(C, f, n_rep, graine)
    # Taux de rétention de la nulle. Une régénération dont le triangle cumulé
    # n'est pas strictement positif est écartée : c'est la même condition que
    # remplit le triangle OBSERVÉ, donc un conditionnement légitime — mais un
    # taux bas signale que l'ajustement produit des triangles très différents de
    # celui-ci, et l'actuaire doit pouvoir le lire (mesuré : 389/400 sur GenIns
    # contre 143/400 sur RAA, qui porte un incrément négatif).
    n_retenues = 0 if nulle is None else int(max(
        (len(v) for v in nulle.values()), default=0))
    extras: Dict[str, Any] = {
        'phi_global': round(float(phi), 6),
        'phi_par_axe': carte,
        'n_obs': n_obs, 'n_params': n_params, 'df': df,
        'graine': graine, 'n_rep_demande': n_rep,
        'n_rep_retenues': n_retenues,
        'taux_retention_nulle': round(n_retenues / max(n_rep, 1), 4),
        'angle_mort': (
            "L'axe calendaire est FAIBLE, et aveugle à une DÉRIVE RÉGULIÈRE : "
            "1,0 % de détection mesurée pour un φ passant de 50 à 500 le long "
            "des années calendaires, soit moins que le témoin à 2,0 %. Une "
            "dérive régulière est absorbée par les paramètres x_i et y_j de "
            "l'ajustement, qui la répartissent entre origine et développement — "
            "il n'en reste rien dans les résidus. Seul un choc brutal et "
            "localisé sur les toutes dernières diagonales est partiellement vu "
            "(29,0 % à ×10 sur trois diagonales). C'est CLM-H1, reprise par "
            "BOOT-H1, qui couvre l'effet calendaire : son test des signes porte "
            "sur les montants, pas sur leur dispersion."),
    }

    detail: List[Dict[str, Any]] = []
    p_valeurs: Dict[str, float] = {}
    for axe in AXES:
        r = rho_obs[axe]
        tirages = None if nulle is None else nulle.get(axe)
        n_nulle = 0 if tirages is None else int(len(tirages))
        if r is None or n_nulle < H3_MIN_NULLE:
            detail.append({'axe': axe, 'rho': r, 'p': None, 'n_nulle': n_nulle,
                           'statut': NON_TESTABLE,
                           'n_groupes': len(carte.get(axe, {}))})
            continue
        p = float((np.abs(tirages) >= abs(r)).mean())
        p_valeurs[axe] = p
        detail.append({
            'axe': axe, 'rho': round(r, 6), 'p': round(p, 6), 'n_nulle': n_nulle,
            'statut': (NON_VALIDEE if p < P_REJET else
                       A_JUSTIFIER if p < P_VIGILANCE else VALIDEE),
            'n_groupes': len(carte.get(axe, {})),
        })

    if not p_valeurs:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("BOOT-H3 NON TESTABLE — aucun axe n'a réuni assez de "
                     "groupes distincts ou de régénérations exploitables pour "
                     "calibrer la corrélation de rang."),
            detail=tuple(detail), extras=extras)

    # Le PIRE des axes fait le verdict : une hétérogénéité sur un seul suffit à
    # invalider l'hypothèse d'un φ unique.
    axe_pire = min(p_valeurs, key=lambda a: p_valeurs[a])
    p_pire = p_valeurs[axe_pire]
    if p_pire < P_REJET:
        statut = NON_VALIDEE
    elif p_pire < P_VIGILANCE:
        statut = A_JUSTIFIER
    else:
        statut = VALIDEE

    extras['axe_le_plus_defavorable'] = axe_pire
    extras['p_par_axe'] = {a: round(p, 6) for a, p in p_valeurs.items()}

    if statut == VALIDEE:
        suite = ("Aucune tendance de dispersion détectable sur les axes testés — "
                 "un φ unique reste défendable. ⚠️ Ce constat ne CERTIFIE pas "
                 "l'homogénéité : une hétérogénéité d'un facteur 2 en "
                 "développement n'est détectée que 18,1 % du temps, et une "
                 "dérive calendaire régulière ne l'est pas du tout.")
    else:
        etendue = carte.get(axe_pire, {})
        borne = ""
        if len(etendue) >= 2:
            vals = [v for v in etendue.values() if v > 0]
            if len(vals) >= 2:
                borne = (f" La dispersion va de {min(vals):,.4g} à "
                         f"{max(vals):,.4g} le long de cet axe.")
        suite = (
            f"La dispersion des résidus suit l'axe « {axe_pire} » : le φ unique "
            f"du modèle ODP est trop grossier.{borne} Les percentiles Bootstrap "
            f"sont trop étroits là où φ est fort et trop larges ailleurs — ils "
            f"ne sont PAS publiés. Le Best Estimate, lui, est inchangé : le "
            f"Bootstrap ne pèse pas dans sa pondération.")

    return ResultatHypothese(
        **base, statut=statut, valeur=round(p_pire, 6),
        message=(f"BOOT-H3 {statut} — φ = {phi:,.4g} sur {n_obs} résidus "
                 f"({n_params} paramètres, df = {df}). Axe le plus défavorable : "
                 f"« {axe_pire} », ρ = {rho_obs[axe_pire]:+.3f}, p = {p_pire:.3f} "
                 f"contre une nulle paramétrique de {len(nulle[axe_pire])} "
                 f"régénérations. {suite}"),
        detail=tuple(detail), extras=extras)


# =============================================================================
#  BOOT-H4 — POSITIVITÉ DES INCRÉMENTS               ⚠️ critique (percentiles)
# =============================================================================

def boot_h4_increments_positifs(bootstrap: Optional[Dict]) -> ResultatHypothese:
    """BOOT-H4 — le modèle ODP exige des incréments strictement positifs.

    Guide §3.c.ii p29, et c'est de la théorie avant d'être du guide : le Poisson
    sur-dispersé n'est pas défini pour une espérance négative. Chain Ladder, lui,
    accepte parfaitement des incréments négatifs — recours, subrogation — ce qui
    rend cette hypothèse PROPRE au Bootstrap ODP, contrairement à ce qu'affirme
    le §3.d.ii p32 (cf. en-tête).

    LE COMPTAGE N'EST PAS REFAIT ICI. `bootstrap_odp` publie déjà
    `increments_non_positifs`, produit par `increments_positifs` — source unique
    partagée avec Clark et Barnett-Zehnwirth. Ce qui manquait, c'est le VERDICT.
    """
    base = dict(code='BOOT-H4',
                libelle="Positivité des incréments ajustés",
                critere=(f"aucun incrément ≤ 0 → validée ; "
                         f"jusqu'à {FRAC_NEG_MAX_DEFAUT:.0%} → à justifier ; "
                         f"au-delà → rejet"),
                source_critere=SOURCE_GUIDE,
                critique_pour=(PERCENTILES_BOOT,))

    ip = (bootstrap or {}).get('increments_non_positifs')
    if not isinstance(ip, dict) or 'n_exclues' not in ip:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("BOOT-H4 NON TESTABLE — le Bootstrap n'a pas publié le "
                     "comptage des incréments non positifs."),
            extras={'repris_de': 'bootstrap.increments_non_positifs'})

    n_exclues = int(ip.get('n_exclues', 0))
    frac = float(ip.get('frac_exclue', 0.0) or 0.0)
    cellules = list(ip.get('cellules_exclues', []) or [])

    if n_exclues == 0:
        statut = VALIDEE
    elif frac <= FRAC_NEG_MAX_DEFAUT:
        statut = A_JUSTIFIER
    else:
        statut = NON_VALIDEE

    if statut == VALIDEE:
        suite = ("Tous les incréments observés sont strictement positifs : le "
                 "modèle de Poisson sur-dispersé est applicable tel quel.")
    else:
        apercu = ", ".join(f"({int(i)},{int(j)})" for i, j in cellules[:6])
        if len(cellules) > 6:
            apercu += f", … (+{len(cellules) - 6})"
        suite = (
            f"Cellules concernées : {apercu}. Le modèle ODP n'est pas défini "
            f"pour une espérance négative ; ces incréments sortent du calcul des "
            f"résidus, ce qui appauvrit le rééchantillonnage et resserre "
            f"artificiellement la distribution. "
            + ("Écart limité, à documenter dans la note méthodologique."
               if statut == A_JUSTIFIER else
               "Écart matériel : les percentiles Bootstrap ne sont PAS publiés. "
               "Le Bootstrap de Mack, lui, n'a pas cette contrainte (guide "
               "§3.c.ii p29) et reste une alternative recevable."))

    return ResultatHypothese(
        **base, statut=statut, valeur=round(frac, 6),
        message=(f"BOOT-H4 {statut} — {n_exclues} incrément(s) non positif(s) "
                 f"sur le triangle observé, soit {frac:.1%}. {suite}"),
        detail=tuple({'i': int(i), 'j': int(j)} for i, j in cellules),
        extras={'repris_de': 'bootstrap.increments_non_positifs',
                'n_exclues': n_exclues, 'frac_exclue': round(frac, 6),
                'seuil_rejet': FRAC_NEG_MAX_DEFAUT},
    )


# =============================================================================
#  POINT D'ENTRÉE
# =============================================================================

def verifier_hypotheses_bootstrap(
    C:         np.ndarray,
    facteurs:  Sequence[float],
    bootstrap: Dict,
    clm_h1:    Optional[Dict] = None,
    glm_apc:   Optional[Dict] = None,
    n_rep_calibration: int = N_REP_CALIBRATION,
    graine:    int = GRAINE_CALIBRATION,
) -> Dict[str, Any]:
    """Les quatre hypothèses du Bootstrap ODP, d'un bloc.

    ⚠️ S'EXÉCUTE APRÈS N3, ET C'EST VOULU. BOOT-H4 juge ce que le Bootstrap a
    RÉELLEMENT exclu, pas ce qu'il aurait pu exclure — une hypothèse qui porte
    sur un résultat ne peut pas être évaluée avant lui. Même raison que pour
    BFCC.

    `facteurs` doit être le tableau que le Bootstrap a lui-même employé — les
    facteurs STANDARD, indépendants de la variante Chain Ladder retenue. N3 les
    publie sous `facteurs_bootstrap` pour que ce lien soit explicite plutôt que
    supposé : tester un autre ajustement que celui qui a produit les percentiles
    n'aurait aucun sens.

    Rend aussi `percentiles_publiables` — la conséquence, calculée ici parce
    qu'elle se lit sur les statuts, mais APPLIQUÉE par N4, qui possède les
    réserves. Le module ne retire rien lui-même.
    """
    h1 = boot_h1_independance(clm_h1)
    h2 = boot_h2_structure(glm_apc)
    h3 = boot_h3_homogeneite_phi(C, facteurs, n_rep_calibration, graine)
    h4 = boot_h4_increments_positifs(bootstrap)

    hypotheses = {h.code: h for h in (h1, h2, h3, h4)}
    return {
        'hypotheses':   {c: h.synthese() for c, h in hypotheses.items()},
        'statuts':      {c: h.statut for c, h in hypotheses.items()},
        'phi_par_axe':  dict(h3.extras.get('phi_par_axe', {})),
        'phi_global':   h3.extras.get('phi_global'),
        'percentiles_publiables': percentiles_publiables(hypotheses),
        'graine_calibration': graine,
        'n_rep_calibration':   n_rep_calibration,
        'objets':       hypotheses,
    }


def percentiles_publiables(hypotheses: Dict[str, ResultatHypothese]) -> bool:
    """Les percentiles Bootstrap sont-ils opposables ?

    NON dès qu'une hypothèse portant `PERCENTILES_BOOT` est NON VALIDÉE. Une
    hypothèse NON TESTABLE ne retire rien : ne pas avoir pu juger n'est pas
    juger défavorablement — c'est la même convention que partout ailleurs dans
    A7, et elle vaut ici aussi.
    """
    return not any(
        h.statut == NON_VALIDEE and PERCENTILES_BOOT in h.critique_pour
        for h in hypotheses.values()
    )


# =============================================================================
#  AFFICHAGE — SOURCE UNIQUE POUR LES LIVRABLES N5
# =============================================================================

def lignes_hypotheses_bootstrap(n2: Optional[Dict]) -> List[Dict[str, Any]]:
    """Les quatre verdicts, prêts à afficher — commentaire, Excel, Word, rapport.

    SOURCE UNIQUE, et c'est le point du lot. L'ancienne H4 était affichée par
    DOUZE sites qui la mettaient en forme chacun à sa façon, dont plusieurs avec
    un `.get(…, 0)` : la clé disparue, ils auraient publié « φ = 0,000000 » et
    « CV = 0,00 », c'est-à-dire une dispersion nulle et une hypothèse validée. Un
    zéro par défaut se lit « aucun problème ». Ici, une hypothèse non évaluée
    ressort NON TESTABLE, jamais en valeur par défaut.
    """
    hyps = (n2 or {}).get('bootstrap_hyp', {}).get('hypotheses', {})
    lignes = []
    for code in CODES:
        h = hyps.get(code, {})
        statut = str(h.get('statut', NON_TESTABLE))
        lignes.append({
            'code':    code,
            'libelle': LIBELLES[code],
            'statut':  statut,
            'message': str(h.get('message', "Hypothèse non évaluée.")),
            'critere': str(h.get('critere', '—')),
            'source':  str(h.get('source_critere', '—')),
            'ok':      statut == VALIDEE,
            'critique': PERCENTILES_BOOT in (h.get('critique_pour') or []),
        })
    return lignes


def libelle_phi_par_axe(n2: Optional[Dict], axe: str = 'developpement') -> str:
    """Étendue de φ le long d'un axe, en une ligne — sous-titre de graphique.

    Rend une chaîne vide quand la carte n'existe pas : un sous-titre absent vaut
    mieux qu'un « φ : 0,0000 → 0,0000 » qui affirmerait l'homogénéité parfaite.
    """
    carte = (n2 or {}).get('bootstrap_hyp', {}).get('phi_par_axe', {}).get(axe, {})
    vals = [v for v in (carte or {}).values() if v and v > 0]
    if len(vals) < 2:
        return ''
    lo, hi = min(vals), max(vals)
    statut = (n2 or {}).get('bootstrap_hyp', {}).get('statuts', {}).get('BOOT-H3', '')
    rapport = hi / lo if lo > 0 else float('inf')
    return (f"φ par période de développement : {lo:,.4g} → {hi:,.4g} "
            f"(×{rapport:,.1f}) · BOOT-H3 {statut or NON_TESTABLE}")
