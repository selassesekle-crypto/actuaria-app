# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §97 a) b) c), §119, §120 : CE QUI SE RESTITUE
=============================================================================

⚠️⚠️ CE MODULE NE CALCULE RIEN, ET C'EST SA DÉFINITION. Les cinq
informations qu'il porte sont des DÉCISIONS ou des DÉCLARATIONS déjà prises
ailleurs ; les recalculer ici en produirait une seconde version, qui
divergerait. Il les rassemble, il en vérifie la PRÉSENCE, et il refuse quand
elles manquent.

⚠️ UNE SEULE EXCEPTION, ET ELLE EST EXACTE : la FOURCHETTE de la courbe du
§120 — son minimum et son maximum — se lit sur les taux remis, sans
convention ni pondération. Elle ne suppose rien.

LES CINQ INFORMATIONS :

  · §97 a) — laquelle des conditions des §53 et §69 est remplie. Le socle la
    SCELLE à la naissance du groupe ; ce module la restitue, il ne la
    réévalue pas.
  · §97 b) — si un ajustement a été apporté pour la valeur temps de l'argent
    (§56, §57 b), §59 b)).
  · §97 c) — la méthode retenue pour les flux liés aux frais d'acquisition
    (§59 a)). ⚠️ DÉCISION DE L'ENTITÉ, et §59 a) n'est pas bâti : elle se
    déclare, faute de quoi ce module refuse.
  · §119 — le niveau de confiance de l'ajustement au titre du risque non
    financier, ou la technique employée et le niveau auquel elle correspond.
  · §120 — la courbe d'actualisation employée en application du §36.

⚠️⚠️ LE PIÈGE DU §120, ET IL A DÉJÀ ÉTÉ PAYÉ AILLEURS. §120 admet une
présentation « sous forme de MOYENNES PONDÉRÉES ou de fourchettes ». Une
moyenne pondérée de courbe est une DÉCISION — par quoi pondère-t-on : les
flux, les primes, la duration ? Trois pondérations défendables donnent trois
courbes. C'est exactement B73, où la pondération d'une date d'émission valait
de 3 à 9 jours d'écart. ⚠️ ELLE SE REÇOIT DÉCLARÉE, AVEC SA PONDÉRATION ;
CE MODULE NE LA CALCULE PAS. La fourchette, elle, est exacte.

⚠️ CE QUE CE MODULE N'ÉTABLIT PAS : que ces déclarations soient VRAIES. Il
constate leur présence et leur forme. L'opposabilité relève de
`declaration.exiger_declaration_opposable`, qui juge le statut, la qualité du
déclarant et le périmètre — et qui refuse aujourd'hui les cinq déclarations
de démonstration reçues.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §36, §53, §56, §57 b), §59, §69, §97, §119, §120.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import est_renseigne, exiger
from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_NOTE_MANQUANTE = 'information_a_fournir_non_declaree'
MOTIF_COURBE_SANS_TAUX = 'courbe_du_120_sans_taux'
MOTIF_MOYENNE_SANS_PONDERATION = 'moyenne_du_120_sans_ponderation'

#: ⚠️ LES DEUX FORMES QUE §120 ADMET, ET ELLES NE SE VALENT PAS ICI.
FORME_FOURCHETTE = 'FOURCHETTE'
FORME_MOYENNE_PONDEREE = 'MOYENNE_PONDEREE'
FORMES_DU_120 = (FORME_FOURCHETTE, FORME_MOYENNE_PONDEREE)

#: ⚠️⚠️ LA LEÇON DE B73, TRANSPOSÉE — et elle descend avec chaque résultat.
PONDERATION_EST_UNE_DECISION = (
    "⚠️ UNE MOYENNE PONDÉRÉE DE COURBE EST UNE DÉCISION, PAS UN CALCUL. §120 "
    "admet « des moyennes pondérées ou des fourchettes » sans dire par quoi "
    "pondérer : les flux d'exécution, les primes, la duration ? Trois "
    "pondérations défendables donnent trois courbes. C'est le piège de B73, "
    "où la pondération d'une date d'émission valait de 3 à 9 jours d'écart. "
    "Ce module REÇOIT la moyenne et sa pondération ; il ne les fabrique pas. "
    "La FOURCHETTE, elle, se lit sur les taux remis et ne suppose rien.")

#: ⚠️ CE QUE LA PRÉSENCE N'ÉTABLIT PAS.
PRESENCE_N_EST_PAS_OPPOSABILITE = (
    "⚠️ CE RELEVÉ CONSTATE LA PRÉSENCE ET LA FORME DE CES DÉCLARATIONS, "
    "JAMAIS LEUR VALEUR. Qu'elles soient signées, par l'entité, et pour le "
    "bon périmètre relève de `declaration.exiger_declaration_opposable` — "
    "qui refuse aujourd'hui les cinq déclarations de démonstration reçues.")


class NotesDeclarees(NamedTuple):
    """Les cinq informations, telles qu'elles se restituent."""
    condition_53_69:      str     # §97 a)
    ajustement_valeur_temps: str  # §97 b)
    methode_frais_acquisition: str  # §97 c) — décision d'entité
    niveau_confiance:     str     # §119
    forme_du_120:         str     # l'une de FORMES_DU_120
    courbe:               tuple   # ((maturite, taux), ...)
    ponderation_du_120:   str     # obligatoire si MOYENNE_PONDEREE
    motif:                str


def fourchette(courbe) -> tuple[float, float]:
    """§120 — le minimum et le maximum des taux remis.

    ⚠️ LA SEULE CHOSE QUE CE MODULE CALCULE, ET ELLE NE SUPPOSE RIEN : une
    fourchette ne pondère pas. Elle se lit.
    """
    taux = [t for _, t in courbe]
    if not taux:
        raise RefusMesure(
            MOTIF_COURBE_SANS_TAUX,
            "la courbe du §120 ne porte aucun taux. Une fourchette calculée "
            "sur un ensemble vide le serait trivialement — c'est la faute de "
            "la gate rendant « Ran 0 tests » en sortant 0.")
    return (min(taux), max(taux))


def relever(*, condition_53_69: str, ajustement_valeur_temps: str,
            methode_frais_acquisition: str, niveau_confiance: str,
            courbe, forme_du_120: str = FORME_FOURCHETTE,
            moyenne_ponderee_declaree: str = '',
            ponderation_du_120: str = '') -> NotesDeclarees:
    """Les cinq informations, ou un REFUS qui dit laquelle manque.

    ⚠️ CHAQUE CHAMP EST EXIGÉ PAR `declaration.exiger`, qui refuse « vide »
    ET « A_RENSEIGNER » : « non vide » n'est pas « renseigné ».
    """
    condition = exiger(
        condition_53_69, '§97 a) — la condition remplie',
        "§97 impose d'indiquer LAQUELLE des conditions des §53 et §69 est "
        "remplie. Le socle la scelle à la naissance du groupe : elle se "
        "restitue, elle ne se réévalue pas.", RefusMesure)
    valeur_temps = exiger(
        ajustement_valeur_temps, '§97 b) — l\'ajustement de valeur temps',
        "§97 impose de dire SI un ajustement a été apporté pour la valeur "
        "temps de l'argent et l'effet du risque financier (§56, §57 b), "
        "§59 b)). « Aucun » est une réponse ; le silence n'en est pas une.",
        RefusMesure)
    frais = exiger(
        methode_frais_acquisition, '§97 c) — la méthode des frais d\'acq.',
        "§97 impose d'indiquer la méthode retenue pour les flux liés aux "
        "frais d'acquisition (§59 a)). ⚠️ C'EST UNE DÉCISION DE L'ENTITÉ que "
        "cette plateforme ne construit pas : elle se déclare.", RefusMesure)
    confiance = exiger(
        niveau_confiance, '§119 — le niveau de confiance',
        "§119 impose d'indiquer le niveau de confiance de l'ajustement au "
        "titre du risque non financier — ou, si une autre technique a été "
        "employée, cette technique ET le niveau de confiance auquel son "
        "résultat correspond.", RefusMesure)

    if forme_du_120 not in FORMES_DU_120:
        raise RefusMesure(
            MOTIF_NOTE_MANQUANTE,
            f"la forme de présentation du §120 n'est pas déclarée (reçu "
            f"{forme_du_120!r}, attendu l'une de {list(FORMES_DU_120)}). "
            f"§120 admet « des moyennes pondérées ou des fourchettes » : les "
            f"deux ne disent pas la même chose. " + PONDERATION_EST_UNE_DECISION)

    lot = tuple(courbe)
    bas, haut = fourchette(lot)

    if forme_du_120 == FORME_MOYENNE_PONDEREE:
        if not est_renseigne(moyenne_ponderee_declaree):
            raise RefusMesure(
                MOTIF_NOTE_MANQUANTE,
                "la forme MOYENNE_PONDEREE est déclarée pour le §120 sans la "
                "moyenne elle-même. " + PONDERATION_EST_UNE_DECISION)
        if not est_renseigne(ponderation_du_120):
            raise RefusMesure(
                MOTIF_MOYENNE_SANS_PONDERATION,
                "la moyenne pondérée du §120 est fournie SANS SA "
                "PONDÉRATION. " + PONDERATION_EST_UNE_DECISION)

    motif = (
        f"§97 a) « {condition} » · §97 b) « {valeur_temps} » · §97 c) "
        f"« {frais} » · §119 « {confiance} » · §120 forme {forme_du_120}, "
        f"{len(lot)} maturité(s), fourchette [{bas:.4%} ; {haut:.4%}]. "
        + PONDERATION_EST_UNE_DECISION + ' ' + PRESENCE_N_EST_PAS_OPPOSABILITE)

    return NotesDeclarees(
        condition_53_69=condition, ajustement_valeur_temps=valeur_temps,
        methode_frais_acquisition=frais, niveau_confiance=confiance,
        forme_du_120=forme_du_120, courbe=lot,
        ponderation_du_120=str(ponderation_du_120 or '').strip(), motif=motif)
