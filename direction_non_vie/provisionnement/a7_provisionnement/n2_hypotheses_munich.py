# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — hypothèses de Munich Chain Ladder (Quarg & Mack 2004)
=============================================================================

 UNE SEULE HYPOTHÈSE GATE, ET C'EST MESURÉ. Les quatre autres sont
 descriptives, chacune pour une raison chiffrée écrite dans son message. Ce
 module n'ajoute pas de gouvernance par symétrie avec CLM, BFCC, BOOT et
 Clark : il publie ce qui doit l'être et gate ce qui le mérite.

 MCL-H1  Indépendance des années de survenance   descriptive  reprise CLM-H1 ×2
 MCL-H2  Linéarité conditionnelle                descriptive  test neuf, faible
 MCL-H3  Structure de variance                   descriptive  reprise CLM-H3 ×2
 MCL-H4  Homogénéité de λ                        MENTION — jamais un verdict
 MCL-H5  Non-circularité du triangle engagé      CRITIQUE     seuils calibrés

 ⚠️ MCL-H1 ET MCL-H3 PORTENT SUR LES DEUX TRIANGLES. Munich est la seule
 méthode d'A7 à exploiter payé ET engagé ; ses hypothèses valent des deux
 côtés. `clm_h1_effet_calendaire` et `clm_h3_structure_variance` sont des
 fonctions PURES d'un triangle — l'agent ne les appelait que sur le payé.
 Le verdict retenu est le PIRE des deux, comme `_pire_statut` de CLM.

 ⚠️ MCL-H4 N'EST PAS UN TEST, ET C'EST UNE DÉCISION MESURÉE. Un test
 d'homogénéité de λ est constructible : il est même parfaitement calibré
 (5,0 % de fausses alarmes au seuil 5 %). Mais sa PUISSANCE vaut 13 à 17 %
 contre un λ variant de 0 à 1,2 — parce que sous λ CONSTANT l'étendue
 médiane des λ_j vaut déjà 1,469. Le bruit d'estimation par colonne dépasse
 le signal cherché : le pooling ne peut pas se tester par les λ par colonne,
 puisque c'est précisément ce qu'il existe pour éviter.
 Or la CONSÉQUENCE, elle, est réelle — pooler un λ qui varie fait passer le
 biais de réserve de 1,15 % à 20,05 % sur vérité connue, et la statistique
 n'y est corrélée qu'à ρ = +0,204 (p = 0,058).
 Une hypothèse dont la violation coûte 20 % et qu'on ne sait pas détecter
 appelle une MENTION PERMANENTE, pas un label vert : un VALIDÉE à 15 % de
 puissance serait un faux confort. C'est l'exact inverse de CLARK-H2 —
 là un test puissant sans conséquence, ici une conséquence sans test.

 ⚠️ SUR UN TRIANGLE 4×4, CE BLOC EST MAJORITAIREMENT MUET, et c'est correct.
 MCL-H2 exige 6 paires (un 4×4 en fournit 5), MCL-H3 n'est pas testable à
 cette taille. NON TESTABLE est un verdict honnête, pas un échec.
=============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np

from .n2_puissance import (
    GRAINE_PUISSANCE, N_SIM_PUISSANCE, arrondir, formuler, lambda_paye,
    regenerer_munich, sans_objet)
from .n2_hypotheses_clm import (
    A_JUSTIFIER, NON_TESTABLE, NON_VALIDEE, SOURCE_JUGEMENT, VALIDEE,
    ResultatHypothese, _pire_statut,
    clm_h1_effet_calendaire, clm_h3_structure_variance)
from .n3.munich_cl import (
    MCL_CV_ALERTE, MCL_CV_BLOQUANT, _statistiques_colonne)

try:
    from scipy import stats as _st
    SCIPY_OK = True
except ImportError:                                        # pragma: no cover
    SCIPY_OK = False

#: Cible de `critique_pour` — un LIVRABLE, jamais un nom de méthode. Munich ne
#: figure pas dans `_CLES_N3` : ses hypothèses ne peuvent pas, structurellement,
#: écarter une méthode du Best Estimate.
RESERVE_MUNICH = 'reserve_munich'

#: MCL-H2 ajuste un terme quadratique en plus de la pente : il lui faut au
#: moins deux degrés de liberté résiduels. Un triangle 4×4 fournit 5 paires,
#: donc le test y est NON TESTABLE — verdict honnête, pas un échec.
MCL_H2_PAIRES_MIN = 6

#: Seuil du test de courbure. Calibration mesurée sur vérité connue linéaire :
#: 1,7 % de rejets pour un nominal de 5 % — le test est CONSERVATEUR, il crie
#: rarement au loup. Sa faiblesse est assumée et verrouillée par test.
MCL_H2_P_REJET = 0.05

LIBELLES = {
    'MCL-H1': "MCL-H1 — Indépendance des années de survenance (payé ET engagé)",
    'MCL-H2': "MCL-H2 — Linéarité conditionnelle de la corrélation",
    'MCL-H3': "MCL-H3 — Structure de variance (payé ET engagé)",
    'MCL-H4': "MCL-H4 — Homogénéité de λ sur le triangle",
    'MCL-H5': "MCL-H5 — Non-circularité du triangle engagé",
}

#: Ordre de présentation, fixe : il suit la numérotation, pas le résultat.
CODES: Tuple[str, ...] = ('MCL-H1', 'MCL-H2', 'MCL-H3', 'MCL-H4', 'MCL-H5')

#: Le texte de MCL-H4, figé. Il porte un chiffre mesuré ; le modifier sans
#: refaire la mesure reviendrait à publier une affirmation sans preuve.
MESSAGE_H4 = (
    "λ est supposé constant sur le triangle (Quarg & Mack 2004). Cette "
    "hypothèse n'est pas vérifiable à cette taille de triangle — puissance "
    "mesurée 13 à 17 % — et sa violation biaiserait la réserve de l'ordre "
    "de 20 %."
)


# =============================================================================
#  MCL-H1 — INDÉPENDANCE DES ANNÉES               (reprise CLM-H1, DEUX côtés)
# =============================================================================

def mcl_h1_independance(
    C_P: Optional[np.ndarray],
    C_E: Optional[np.ndarray],
) -> ResultatHypothese:
    """MCL-H1 — l'indépendance vaut pour les DEUX triangles.

    Munich lit le payé et l'engagé ensemble : un effet calendaire sur l'un
    contamine la corrélation entre les deux. `clm_h1_effet_calendaire` est une
    fonction pure d'un triangle — on l'applique deux fois plutôt que de
    réécrire un test qui existe.

    ⚠️ DESCRIPTIVE. Un effet calendaire biaise le payé et l'engagé DANS LE MÊME
    SENS ; il ne disqualifie pas le rapprochement, il déplace les deux. CLM-H1
    est elle-même descriptive (`critique_pour = ()`), et la gater ici
    sanctionnerait Munich pour un défaut qui n'est pas le sien.
    """
    base = dict(code='MCL-H1',
                libelle="Indépendance des années de survenance (payé et engagé)",
                critere="reprise de CLM-H1, appliquée aux deux triangles",
                source_critere=SOURCE_JUGEMENT,
                critique_pour=())

    verdicts, detail = [], []
    for nom, C in (('payé', C_P), ('engagé', C_E)):
        if C is None:
            continue
        try:
            r = clm_h1_effet_calendaire(np.asarray(C, dtype=float))
        except Exception:                                  # pragma: no cover
            continue
        verdicts.append(r.statut)
        detail.append({'triangle': nom, 'statut': r.statut,
                       'valeur': r.valeur, 'message': r.message})

    if not verdicts:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("MCL-H1 NON TESTABLE — aucun des deux triangles n'a pu "
                     "être évalué."),
            extras={'repris_de': 'CLM-H1'})

    pire = _pire_statut(verdicts)
    resume = " · ".join(f"{d['triangle']} : {d['statut']}" for d in detail)
    return ResultatHypothese(
        **base, statut=pire,
        valeur=next((d['valeur'] for d in detail if d['statut'] == pire), None),
        message=(f"MCL-H1 = CLM-H1 sur les deux triangles ({resume}). "
                 f"Le verdict retenu est le plus sévère des deux : Munich lit "
                 f"le payé et l'engagé ensemble."),
        detail=tuple(detail),
        extras={'repris_de': 'CLM-H1', 'n_triangles': len(detail)})


# =============================================================================
#  MCL-H2 — LINÉARITÉ CONDITIONNELLE                              (test neuf)
# =============================================================================

def _paires_standardisees(C_P: np.ndarray, C_E: np.ndarray) -> np.ndarray:
    """Résidus standardisés (Res(F^P), Res(Q⁻¹)) de tout le triangle.

    Exactement ceux que `_calculer_lambda` régresse — même masque, mêmes
    pondérations. Tester la linéarité sur d'autres résidus que ceux du modèle
    ne prouverait rien sur le modèle.
    """
    _, m = C_P.shape
    paires = []
    for j in range(m - 1):
        st = _statistiques_colonne(C_P, C_E, j)
        if st is None:
            continue
        for i in st['idx']:
            p, p1, e = C_P[i, j], C_P[i, j + 1], C_E[i, j]
            w = float(np.sqrt(p))
            paires.append(((p1 / p - st['f_P']) / st['sig_P']  * w,
                           (e / p - st['q_inv']) / st['rho_Qi'] * w))
    return np.asarray(paires, dtype=float) if paires else np.empty((0, 2))


def mcl_h2_linearite(
    C_P: Optional[np.ndarray],
    C_E: Optional[np.ndarray],
) -> ResultatHypothese:
    """MCL-H2 — la corrélation est-elle LINÉAIRE dans le résidu standardisé ?

    Quarg & Mack posent E[Res(F^P) | Res(Q⁻¹)] = λ · Res(Q⁻¹) : une droite
    passant par l'origine. On ajoute un terme quadratique et on teste s'il
    apporte quelque chose (F de restriction, 1 et n−2 degrés de liberté).

    ⚠️ DESCRIPTIVE, et sa faiblesse est mesurée. Calibration sur vérité connue
    linéaire : 1,7 % de rejets pour un nominal de 5 % — le test est
    CONSERVATEUR. Il ne criera pas au loup, mais un VALIDÉE ne certifie pas la
    linéarité : il constate qu'on ne voit pas de courbure.
    """
    base = dict(code='MCL-H2',
                libelle="Linéarité conditionnelle de la corrélation",
                critere=(f"terme quadratique ajouté à la régression par "
                         f"l'origine ; p < {MCL_H2_P_REJET} → courbure"),
                source_critere=SOURCE_JUGEMENT,
                critique_pour=())

    if C_P is None or C_E is None or not SCIPY_OK:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=("MCL-H2 NON TESTABLE — triangle engagé absent ou scipy "
                     "indisponible."))

    a = _paires_standardisees(np.asarray(C_P, dtype=float),
                              np.asarray(C_E, dtype=float))
    if len(a) < MCL_H2_PAIRES_MIN:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message=(f"MCL-H2 NON TESTABLE — {len(a)} paire(s) exploitable(s) "
                     f"pour un minimum de {MCL_H2_PAIRES_MIN}. Un terme de "
                     f"courbure n'est pas ajustable sur si peu de points ; un "
                     f"triangle 4×4 en fournit 5."),
            extras={'n_paires': int(len(a))})

    y, x = a[:, 0], a[:, 1]
    X1 = x[:, None]
    X2 = np.column_stack([x, x ** 2])
    b1, *_ = np.linalg.lstsq(X1, y, rcond=None)
    b2, *_ = np.linalg.lstsq(X2, y, rcond=None)
    sse1 = float(np.sum((y - X1 @ b1) ** 2))
    sse2 = float(np.sum((y - X2 @ b2) ** 2))
    df2  = len(y) - 2
    if df2 <= 0 or sse2 <= 0:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message="MCL-H2 NON TESTABLE — ajustement quadratique dégénéré.",
            extras={'n_paires': int(len(a))})

    F = max((sse1 - sse2) / (sse2 / df2), 0.0)
    p = float(1.0 - _st.f.cdf(F, 1, df2))
    statut = NON_VALIDEE if p < 0.01 else (A_JUSTIFIER if p < MCL_H2_P_REJET
                                           else VALIDEE)
    suite = ("Aucune courbure décelable : la relation linéaire de Quarg & Mack "
             "tient sur ce triangle." if statut == VALIDEE else
             "Une courbure apparaît : la corrélation entre règlement et charge "
             "dossier n'est pas linéaire dans le résidu, l'ajustement de Munich "
             "en est approximatif.")
    return ResultatHypothese(
        **base, statut=statut, valeur=round(p, 4),
        message=(f"MCL-H2 {statut} — terme quadratique F = {F:.3f}, "
                 f"p = {p:.4f} sur {len(a)} paires. {suite} "
                 f"Test conservateur (1,7 % de fausses alarmes mesurées pour "
                 f"un nominal de 5 %) : un VALIDÉE constate l'absence de "
                 f"courbure visible, il ne certifie pas la linéarité."),
        extras={'n_paires': int(len(a)), 'F': round(F, 4),
                'pente': round(float(b1[0]), 4),
                'quadratique': round(float(b2[1]), 6)})


# =============================================================================
#  MCL-H3 — STRUCTURE DE VARIANCE                 (reprise CLM-H3, DEUX côtés)
# =============================================================================

def mcl_h3_structure_variance(
    C_P: Optional[np.ndarray],
    C_E: Optional[np.ndarray],
) -> ResultatHypothese:
    """MCL-H3 — la dispersion croît-elle comme le volume, des DEUX côtés ?

    Quarg & Mack reprennent la structure de variance de Mack sur chacun des
    deux triangles : Var(F) = σ²_j / C. `clm_h3_structure_variance` la teste
    déjà — appliquée deux fois plutôt que réécrite.

    ⚠️ DESCRIPTIVE ICI. CLM-H3 gate `mack` parce que le σ de Mack en dépend
    directement. Munich ne publie pas de σ : sa réserve est un point. La même
    hypothèse n'a donc pas la même conséquence selon la méthode qui l'emprunte.
    """
    base = dict(code='MCL-H3',
                libelle="Structure de variance (payé et engagé)",
                critere="reprise de CLM-H3, appliquée aux deux triangles",
                source_critere=SOURCE_JUGEMENT,
                critique_pour=())

    verdicts, detail = [], []
    for nom, C in (('payé', C_P), ('engagé', C_E)):
        if C is None:
            continue
        try:
            r = clm_h3_structure_variance(np.asarray(C, dtype=float))
        except Exception:                                  # pragma: no cover
            continue
        verdicts.append(r.statut)
        detail.append({'triangle': nom, 'statut': r.statut,
                       'valeur': r.valeur, 'message': r.message})

    if not verdicts:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message="MCL-H3 NON TESTABLE — aucun des deux triangles évaluable.",
            extras={'repris_de': 'CLM-H3'})

    pire = _pire_statut(verdicts)
    resume = " · ".join(f"{d['triangle']} : {d['statut']}" for d in detail)
    return ResultatHypothese(
        **base, statut=pire,
        valeur=next((d['valeur'] for d in detail if d['statut'] == pire), None),
        message=(f"MCL-H3 = CLM-H3 sur les deux triangles ({resume}). "
                 f"Verdict le plus sévère retenu. Descriptive pour Munich, qui "
                 f"ne publie pas de σ — contrairement à Mack, que CLM-H3 gate."),
        detail=tuple(detail),
        extras={'repris_de': 'CLM-H3', 'n_triangles': len(detail)})


# =============================================================================
#  MCL-H4 — HOMOGÉNÉITÉ DE λ                    MENTION, JAMAIS UN VERDICT
# =============================================================================

def mcl_h4_homogeneite_lambda() -> ResultatHypothese:
    """MCL-H4 — mention permanente. Aucun test, et c'est le résultat mesuré.

    Cf. l'en-tête du module : test calibré (5,0 %) mais puissance 13-17 %,
    conséquence réelle jusqu'à 20 % de biais, corrélation statistique/erreur
    ρ = +0,204. On publie la limite, pas un verdict.

    Le statut est NON TESTABLE — le seul honnête. Ce n'est ni VALIDÉE (on n'a
    rien validé) ni NON VALIDÉE (on n'a rien réfuté) : on ne peut pas savoir.
    """
    return ResultatHypothese(
        code='MCL-H4',
        libelle="Homogénéité de λ sur le triangle",
        statut=NON_TESTABLE,
        valeur=None,
        critere="non testable — puissance mesurée 13 à 17 %, aucun seuil publié",
        source_critere=SOURCE_JUGEMENT,
        critique_pour=(),
        message=MESSAGE_H4,
        extras={'mention_permanente': True,
                'puissance_mesuree': '13 % à 17 %',
                'biais_si_violee': '~20 %',
                'correlation_statistique_erreur': 0.204})


# =============================================================================
#  MCL-H5 — NON-CIRCULARITÉ                                        CRITIQUE
# =============================================================================

def mcl_h5_non_circularite(munich: Optional[Dict]) -> ResultatHypothese:
    """MCL-H5 — le triangle engagé est-il indépendant des provisions ?

    ⚠️ SEULE HYPOTHÈSE CRITIQUE DU BLOC, et la seule dont les seuils soient
    calibrés sur vérité connue. Si les charges engagées sont recalculées depuis
    les provisions actuarielles, Munich ne lit que le reflet du payé : il n'a
    rien à rapprocher, et sa réserve n'a pas de contenu propre.

    Le verdict est LU sur ce que `valider_prerequis` a déjà décidé — le module
    ne recalcule rien. `alerte_prerequis` porte l'avertissement dans les deux
    régimes depuis le lot 2 ; il était auparavant perdu quand la méthode
    restait active.

    ⚠️ OÙ CETTE HYPOTHÈSE APPORTE RÉELLEMENT QUELQUE CHOSE — et c'est une bande
    étroite, qu'il faut connaître pour ne pas la croire redondante. Elle est
    INFORMATIVE : elle ne retire jamais rien, la circularité franche étant déjà
    bloquée en amont. Sa valeur tient tout entière dans l'intervalle

        [MCL_CV_BLOQUANT ; MCL_CV_ALERTE[   =   [0,020 ; 0,025[

    où `valider_prerequis` LAISSE PASSER — Munich est calculé et publié — et où
    MCL-H5 est la SEULE à signaler quoi que ce soit. Hors de cette bande elle ne
    fait que redire ce que la garde a déjà tranché.

    Cette bande n'est pas théorique. La calibration en tête de `munich_cl.py`
    (80 tirages par scénario, vérité connue) mesure qu'un portefeuille
    CIRCULAIRE bruité à 2 % a un CV médian de 0,0199 : **la moitié de ces
    portefeuilles franchissent la garde**, et seul MCL-H5 les voit. C'est
    exactement le cas que le test `test_mh9_la_bande_ou_mcl_h5_parle_seule`
    verrouille, sur un triangle dont le CV vaut 0,0223.
    """
    base = dict(code='MCL-H5',
                libelle="Non-circularité du triangle engagé",
                critere=(f"CV des ratios engagé/payé : < {MCL_CV_BLOQUANT} → "
                         f"rejet ; < {MCL_CV_ALERTE} → à justifier"),
                source_critere=SOURCE_JUGEMENT,
                critique_pour=(RESERVE_MUNICH,))

    if not isinstance(munich, dict) or not munich:
        return ResultatHypothese(
            **base, statut=NON_TESTABLE, valeur=None,
            message="MCL-H5 NON TESTABLE — Munich CL n'a pas été exécuté.")

    alerte = munich.get('alerte_prerequis')
    dispo  = bool(munich.get('disponible'))

    if not dispo:
        circulaire = 'CIRCULARITE' in str(alerte or munich.get('message', ''))
        return ResultatHypothese(
            **base,
            statut=NON_VALIDEE if circulaire else NON_TESTABLE,
            valeur=None,
            message=((f"MCL-H5 NON VALIDÉE — {alerte}" if circulaire else
                      f"MCL-H5 NON TESTABLE — Munich indisponible pour une "
                      f"autre raison : {munich.get('message', '—')}")),
            extras={'lu_de': 'munich_cl.alerte_prerequis'})

    if alerte:
        return ResultatHypothese(
            **base, statut=A_JUSTIFIER, valeur=None,
            message=(f"MCL-H5 À JUSTIFIER — {alerte} Les deux populations se "
                     f"recouvrent dans cette bande (circulaire q95 = 0,0233, "
                     f"légitime q05 = 0,0223) : le seuil est un point de "
                     f"croisement, pas une frontière."),
            extras={'lu_de': 'munich_cl.alerte_prerequis'})

    return ResultatHypothese(
        **base, statut=VALIDEE, valeur=None,
        message=(f"MCL-H5 VALIDÉE — le CV des ratios engagé/payé dépasse "
                 f"{MCL_CV_ALERTE} : les charges dossier portent une "
                 f"information propre, distincte du règlement. C'est ce que "
                 f"Munich CL exploite."),
        extras={'lu_de': 'munich_cl.alerte_prerequis'})


# =============================================================================
#  INTERFACE PUBLIQUE
# =============================================================================

def verifier_hypotheses_munich(
    C_P:    Optional[np.ndarray],
    C_E:    Optional[np.ndarray],
    munich: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Les cinq hypothèses de Munich CL, d'un bloc.

    ⚠️ S'EXÉCUTE APRÈS N3 : MCL-H5 juge ce que `valider_prerequis` a réellement
    décidé, pas ce qu'il aurait pu décider. Même raison que BFCC, BOOT et le
    bloc Clark.

    ⚠️ AUCUN DRAPEAU DE PUBLICATION ICI, ET C'EST DÉMONTRÉ. Ce bloc rendait un
    `reserve_publiable = (MCL-H5 != NON VALIDÉE)`. Il était REDONDANT PAR
    CONSTRUCTION : MCL-H5 est NON VALIDÉE si et seulement si
    `CV < MCL_CV_BLOQUANT`, or c'est exactement la condition sous laquelle
    `valider_prerequis` a DÉJÀ rendu Munich indisponible (`munich_cl.py`, même
    constante, même comparaison). Le drapeau ne pouvait donc valoir False que
    là où il n'y avait aucune réserve à retirer — et personne ne le lisait.

    C'est la différence avec `percentiles_publiables` du Bootstrap, qui lui est
    branché et utile : le Bootstrap PRODUIT ses percentiles quoi qu'il arrive, et
    l'hypothèse décide s'ils sont opposables. MCL-H5, elle, juge en AVAL d'une
    garde qui a déjà tranché.
    """
    h1 = mcl_h1_independance(C_P, C_E)
    h2 = mcl_h2_linearite(C_P, C_E)
    h3 = mcl_h3_structure_variance(C_P, C_E)
    h4 = mcl_h4_homogeneite_lambda()
    h5 = mcl_h5_non_circularite(munich)

    resultats = {'MCL-H1': h1, 'MCL-H2': h2, 'MCL-H3': h3,
                 'MCL-H4': h4, 'MCL-H5': h5}
    return {
        'hypotheses': {c: r.synthese() for c, r in resultats.items()},
        'statuts':    {c: r.statut for c, r in resultats.items()},
        # Ce que MCL-H2 POUVAIT détecter sur cette paire — à lire avec son
        # verdict, jamais à sa place.
        'puissance':  puissance_munich(C_P, C_E),
        'mention_h4': MESSAGE_H4,
        'statut_le_plus_severe': _pire_statut([r.statut for r in resultats.values()]),
        'objets': resultats,
    }


#: Courbure publiée pour MCL-H2 : coefficient du terme en carré du résidu
#: standardisé. 0,50 parce que la mesure le place dans la zone informative —
#: à 0,10 tout portefeuille afficherait le niveau du témoin, et le chiffre ne
#: dirait plus rien de la paix payé / engagé qu'on lui soumet.
MCL_H2_COURBURE_PUBLIEE = 0.50

#: Les quatre autres hypothèses de la famille n'ont pas de puissance propre.
_SANS_PUISSANCE_MCL = {
    'MCL-H1': "elle rejoue CLM-H1 sur les deux triangles, et la puissance de "
              "ce test est publiée là-bas",
    'MCL-H3': "elle rejoue CLM-H3 sur les deux triangles, et la puissance de "
              "ce test est publiée là-bas",
    'MCL-H4': "aucun test n'est disponible pour l'homogénéité de λ — c'est "
              "une limite assumée, pas un résultat",
    'MCL-H5': "elle vérifie une condition de non-circularité, par comparaison "
              "à un seuil",
}


def puissance_munich(
    C_P: Optional[np.ndarray],
    C_E: Optional[np.ndarray],
) -> Dict[str, Dict[str, Any]]:
    """Ce que MCL-H2 pouvait détecter SUR CETTE PAIRE payé / engagé.

    ⚠️ LE λ VIENT DES DONNÉES, JAMAIS D'UNE CONSTANTE, et c'est une leçon
    payée : en construisant ce générateur, coder λ = 0,35 « par défaut » là où
    la paire réelle en portait −0,0 faisait passer le témoin de 7,5 % à
    17,5 %. Le générateur cessait de respecter la nulle de Quarg & Mack, et
    toute puissance qu'il aurait produite aurait été fausse.
    """
    out: Dict[str, Dict[str, Any]] = {
        code: sans_objet(motif) for code, motif in _SANS_PUISSANCE_MCL.items()
    }
    if C_P is None or C_E is None:
        out['MCL-H2'] = sans_objet(
            "le triangle des engagés n'est pas fourni")
        return out

    lam = lambda_paye(C_P, C_E)
    if lam is None:
        out['MCL-H2'] = sans_objet(
            "la paire ne permet pas d'estimer le coefficient de Quarg & Mack")
        return out

    def _mesure(courbure: float) -> Optional[float]:
        rng = np.random.default_rng(GRAINE_PUISSANCE)
        detectes = evalues = 0
        for _ in range(N_SIM_PUISSANCE):
            paire = regenerer_munich(C_P, C_E, lam, rng, quad=courbure)
            if paire is None:
                return None
            try:
                statut = str(mcl_h2_linearite(paire[0], paire[1]).statut)
            except Exception:                              # pragma: no cover
                continue
            evalues += 1
            if statut not in (VALIDEE, NON_TESTABLE):
                detectes += 1
        return (100.0 * detectes / evalues) if evalues else None

    pct = _mesure(MCL_H2_COURBURE_PUBLIEE)
    if pct is None:
        out['MCL-H2'] = sans_objet(
            "la paire ne permet pas de régénérer un jeu de référence")
        return out
    effet = (f"une courbure de {MCL_H2_COURBURE_PUBLIEE:.2f} dans la réponse "
             f"du facteur payé au résidu engagé / payé")
    out['MCL-H2'] = {
        'mesurable':      True,
        'puissance':      arrondir(pct),
        'puissance_brute': round(pct, 1),
        'temoin':         (lambda t: arrondir(t) if t is not None else None)(
            _mesure(0.0)),
        'lambda_estime':  round(lam, 4),
        'effet':          effet,
        'n_simulations':  N_SIM_PUISSANCE,
        'graine':         GRAINE_PUISSANCE,
        'phrase':         formuler(
            pct, effet,
            "la relation entre payé et engagé y est peu marquée, ce qui laisse "
            "peu de prise à un test de courbure"),
    }
    return out


def lignes_hypotheses_munich(n2: Optional[Dict]) -> list:
    """Les cinq verdicts, prêts à afficher — SOURCE UNIQUE des trois formats.

    HTML, Word et Excel lisent cette liste. Une hypothèse non évaluée ressort
    NON TESTABLE, jamais en valeur par défaut : un zéro se lirait « aucun
    problème ».
    """
    hyps = ((n2 or {}).get('munich_hyp') or {}).get('hypotheses', {})
    puis = ((n2 or {}).get('munich_hyp') or {}).get('puissance', {}) or {}
    lignes = []
    for code in CODES:
        h = hyps.get(code, {})
        statut = str(h.get('statut', NON_TESTABLE))
        lignes.append({
            'code':     code,
            'libelle':  LIBELLES[code],
            'statut':   statut,
            'message':  str(h.get('message', "Hypothèse non évaluée.")),
            'critere':  str(h.get('critere', '—')),
            'source':   str(h.get('source_critere', '—')),
            'ok':       statut == VALIDEE,
            'critique': RESERVE_MUNICH in (h.get('critique_pour') or []),
            'puissance':        (puis.get(code) or {}).get('puissance'),
            'puissance_phrase': str((puis.get(code) or {}).get('phrase', '')),
        })
    return lignes
