# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §57-58 : LE TEST DE DÉFICIT ET L'ÉLÉMENT DE PERTE
=============================================================================

§57, verbatim : « Si, à n'importe quel moment au cours de la période de
couverture, LES FAITS ET CIRCONSTANCES INDIQUENT qu'un groupe de contrats
d'assurance est déficitaire, l'entité doit calculer l'écart entre : a) la
valeur comptable du passif au titre de la couverture restante, déterminée
conformément au paragraphe 55 ; et b) les flux de trésorerie d'exécution
afférents à la couverture restante du groupe, évalués conformément aux
paragraphes 33 à 37 et B36 à B92. »

§58 : « Dans la mesure où les flux de trésorerie d'exécution visés au
paragraphe 57 b) EXCÈDENT la valeur comptable visée au paragraphe 57 a),
l'entité doit comptabiliser une perte en résultat net et MAJORER le passif au
titre de la couverture restante. »

⚠️⚠️ « LES FAITS ET CIRCONSTANCES INDIQUENT » EST UN JUGEMENT DE L'ENTITÉ.
La norme n'énumère ni seuil ni indicateur. Ce module ne déclenche donc rien
de lui-même : il REÇOIT la déclaration, signée, et la publie. C'est la
sixième fois dans ce chantier qu'un paragraphe remet la décision à l'entité,
après §54, §59 a), B66 d), §36 b) et §37.

⚠️ ET NE PAS DÉCLENCHER N'EST PAS CONCLURE QUE LE GROUPE VA BIEN. En
l'absence de déclenchement, le résultat dit que la présomption de non-déficit
de la PAA est MAINTENUE, faute d'élément contraire déclaré — jamais que le
groupe a été testé et jugé sain. Confondre les deux ferait passer une absence
d'examen pour un examen concluant.

⚠️ AUCUN ORACLE ICI NON PLUS. Le classeur de la section 7 de la note ICA,
qui chiffre l'élément de perte, est annoncé « under separate cover » et n'est
pas en notre possession. Si un jour il arrive, c'est ce module-ci qu'il
viendra confronter — pas `flux_execution`.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §57, §58, et §59 b) pour la règle de cohérence.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.flux_execution import FluxExecution
from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_SANS_SIGNATURE = 'declenchement_sans_signataire'
MOTIF_SANS_FAITS = 'declenchement_sans_faits_ni_circonstances'
MOTIF_INCOHERENCE_59B = 'dispense_59b_et_actualisation_du_57b'
MOTIF_LRC_NEGATIF = 'lrc_negatif'

#: ⚠️ CE QUE PORTE UN RÉSULTAT NON DÉCLENCHÉ. « Non testé » n'est pas
#: « testé et sain » — même leçon que `PAA_NON_ETABLI` dans le socle.
MOTIF_NON_DECLENCHE = (
    "test de déficit NON DÉCLENCHÉ — la présomption de non-déficit de la "
    "méthode d'affectation des primes est MAINTENUE, faute de faits et "
    "circonstances déclarés en sens contraire. ⚠️ Ce n'est PAS un constat "
    "que le groupe est sain : c'est l'absence d'examen, et le §57 confie "
    "l'appréciation des faits et circonstances à l'entité, pas à ce code.")

#: ⚠️ CE QUI DESCEND D'UN TERME NON ÉTABLI. Si les flux d'exécution portent
#: la réserve du §33 a), l'élément de perte la porte aussi : un chiffre
#: calculé sur une base non établie ne devient pas établi en changeant de
#: ligne.
MOTIF_HERITE = (
    "⚠️ ÉLÉMENT DE PERTE CALCULÉ SUR UNE BASE NON ÉTABLIE — voir la réserve "
    "attachée aux flux d'exécution, reprise ci-dessous. Elle accompagne "
    "obligatoirement tout montant qui en descend.")


class Declenchement(NamedTuple):
    """L'appréciation du §57, telle que l'entité la porte."""
    declenche:              bool
    faits_et_circonstances: str
    arrete:                 str
    actuaire_resp:          str


class TestDeficit(NamedTuple):
    """Le résultat. ⚠️ `element_de_perte` À `None` = test non déclenché."""
    declenche:         bool
    lrc:               float | None
    flux_execution:    float | None
    ecart:             float | None   # §57 b) - §57 a)
    element_de_perte:  float | None   # §58, jamais négatif
    motif:             str


def declarer_declenchement(*, declenche: bool, faits_et_circonstances: str,
                           arrete: str,
                           actuaire_resp: str) -> Declenchement:
    """Reçoit l'appréciation du §57, ou REFUSE.

    ⚠️ DÉCLENCHER SANS DIRE POURQUOI EST REFUSÉ. §57 fait dépendre le test
    de « faits et circonstances » : un déclenchement sans faits nommés ne
    serait pas vérifiable par un tiers, et un élément de perte non
    justifiable n'est pas présentable.
    """
    if not (actuaire_resp or '').strip():
        raise RefusMesure(
            MOTIF_SANS_SIGNATURE,
            "aucun actuaire ne se porte garant de cette appréciation. Le "
            "§57 la confie à l'entité et le §58 en fait une perte en "
            "résultat net : elle engage quelqu'un, nommément")
    if not (arrete or '').strip():
        raise RefusMesure(
            MOTIF_SANS_SIGNATURE,
            "l'appréciation est fournie sans son arrêté. §57 dit « à "
            "n'importe quel moment au cours de la période de couverture » : "
            "sans date, elle ne se rattache à aucun moment")
    if declenche and not (faits_et_circonstances or '').strip():
        raise RefusMesure(
            MOTIF_SANS_FAITS,
            "le test est déclenché sans qu'aucun fait ni aucune "
            "circonstance ne soit nommé. §57 subordonne le test à ce que "
            "« les faits et circonstances INDIQUENT » : un déclenchement "
            "sans eux n'est vérifiable par personne")
    return Declenchement(declenche=declenche,
                         faits_et_circonstances=(
                             faits_et_circonstances or '').strip(),
                         arrete=arrete.strip(),
                         actuaire_resp=actuaire_resp.strip())


def eprouver(declenchement: Declenchement, *, lrc: float | None = None,
             flux: FluxExecution | None = None,
             dispense_59b_sur_le_lic: bool = False) -> TestDeficit:
    """§57 puis §58 — l'écart, et la perte s'il y en a une.

    ⚠️ LA RÈGLE DE COHÉRENCE DU §57 EST APPLIQUÉE ICI, ET ELLE EST FACILE À
    MANQUER. Le §57 ajoute : « Cependant, l'entité qui applique le
    paragraphe 59 b) SANS ajuster le passif au titre des sinistres survenus
    pour refléter la valeur temps de l'argent […] NE DOIT PAS inclure de
    tels ajustements dans les flux de trésorerie d'exécution. » Autrement
    dit : qui n'actualise pas son passif au titre des sinistres survenus ne
    peut pas actualiser les flux du §57 b). Deux conventions différentes
    dans le même test rendraient l'écart faux dans un sens systématique.
    """
    if not declenchement.declenche:
        return TestDeficit(declenche=False, lrc=None, flux_execution=None,
                           ecart=None, element_de_perte=None,
                           motif=MOTIF_NON_DECLENCHE)

    if lrc is None or flux is None:
        raise RefusMesure(
            'termes_du_57_incomplets',
            "le test est déclenché mais l'un des deux termes du §57 manque : "
            "il faut la valeur comptable du passif au titre de la couverture "
            "restante (§57 a) ET les flux d'exécution (§57 b). Un écart "
            "calculé sur un seul terme n'a aucun sens")
    if lrc < 0:
        raise RefusMesure(
            MOTIF_LRC_NEGATIF,
            f"le passif au titre de la couverture restante vaut {lrc}. Ce "
            f"module attend la convention positive du §55 ; un négatif "
            f"signale une créance de prime présentée comme un passif")

    if dispense_59b_sur_le_lic and flux.actualisation_appliquee:
        raise RefusMesure(
            MOTIF_INCOHERENCE_59B,
            "la dispense du §59 b) est déclarée sur le passif au titre des "
            "sinistres survenus, mais les flux du §57 b) ont ÉTÉ actualisés. "
            "Le §57 l'interdit expressément : qui n'ajuste pas son passif de "
            "la valeur temps de l'argent ne doit pas inclure cet ajustement "
            "ici. Deux conventions dans le même test fausseraient l'écart "
            "dans un sens systématique, en faveur de l'entité")

    ecart = flux.total - lrc
    perte = max(0.0, ecart)

    if flux.motif_esperance:
        motif = f'{MOTIF_HERITE} {flux.motif_esperance}'
    elif perte > 0:
        motif = ''
    else:
        motif = ("test déclenché et MENÉ : les flux d'exécution n'excèdent "
                 "pas le passif au titre de la couverture restante. Aucun "
                 "élément de perte. ⚠️ Ce constat-ci, contrairement à un "
                 "test non déclenché, EST un examen concluant.")

    return TestDeficit(declenche=True, lrc=lrc, flux_execution=flux.total,
                       ecart=ecart, element_de_perte=perte, motif=motif)
