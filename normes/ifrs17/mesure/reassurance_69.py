# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §69 : LA PAA POUR LA RÉASSURANCE DÉTENUE
=============================================================================

§69, verbatim : « l'entité PEUT appliquer la méthode d'affectation des primes
[…] si l'une ou l'autre des conditions ci-dessous est remplie à la date de
création du groupe : a) l'entité s'attend raisonnablement à ce que
l'évaluation obtenue par cette méthode ne diffère pas de manière
significative de celle qui serait obtenue en appliquant les §63 à 68 ; OU
b) la période de couverture de chacun des contrats du groupe (CE QUI INCLUT
LA COUVERTURE D'ASSURANCE DÉCOULANT DE TOUTES LES PRIMES COMPRISES DANS LE
PÉRIMÈTRE DU CONTRAT à cette date selon le §34) n'excède pas un an. »

⚠️⚠️ C'EST LE §53 À L'IDENTIQUE, ET LA MÊME LEÇON S'APPLIQUE. Deux portes
DISJONCTIVES : l'automatique (b), mesurable, et la qualitative (a), qui
appartient à l'entité. §70 est le miroir mot pour mot du §54 — « s'attend à
une variabilité importante », facteurs ILLUSTRATIFS, aucun seuil.

⚠️ ÉCHOUER À (b) N'ÉTABLIT RIEN SUR (a), ET AUCUN VERDICT NE DIT
« INÉLIGIBLE ». Le socle a payé cette leçon : un verdict nommé
`NON_ELIGIBLE` affirmait une conclusion que le code ne peut pas atteindre,
et c'est le NOM que consomment les agrégats, pas la phrase du motif. Les
trois verdicts d'ici portent donc les mêmes noms honnêtes.

⚠️⚠️ LA PARENTHÈSE DU §69 b) EST LE CŒUR DU MODULE, ET ELLE DÉPEND DE LA
BASE DU TRAITÉ. « Ce qui inclut la couverture d'assurance découlant de toutes
les primes comprises dans le périmètre » :

  · en RISQUES ATTACHANTS, le traité prend les polices souscrites pendant sa
    période ; leur couverture DÉBORDE la sienne, et c'est elle qui compte ;
  · en SINISTRES SURVENUS, le traité couvre les sinistres survenus pendant
    sa période, quelle que soit la date des polices : la couverture NE
    déborde PAS.

⚠️ ET CETTE DISTINCTION A ÉTÉ PAYÉE. Un premier calcul appliquait l'extension
à TOUS les traités et rendait 13 fermés sur 13. Mesuré correctement, le
portefeuille se partage en 7 ouvertes et 6 fermées — les six quote-parts en
risques attachants, dont celle de la décennale à 10,99 ans.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §69, §70, §34, §63 à §68.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import est_renseigne
from normes.ifrs17.mesure.lrc_paa import RefusMesure

#: Les deux bases d'attachement, et elles ne se devinent pas.
BASE_RISQUES_ATTACHANTS = 'RISQUES_ATTACHANTS'
BASE_SINISTRES_SURVENUS = 'SINISTRES_SURVENUS'
BASES = (BASE_RISQUES_ATTACHANTS, BASE_SINISTRES_SURVENUS)

#: ⚠️ AUCUN DES TROIS NE DIT « INÉLIGIBLE » — même règle qu'au §53.
PAA_RA_ELIGIBLE = 'ELIGIBLE'
PAA_RA_69A_NON_EVALUEE = '69A_NON_EVALUEE'
PAA_RA_NON_ETABLI = 'NON_ETABLI'
VERDICTS = (PAA_RA_ELIGIBLE, PAA_RA_69A_NON_EVALUEE, PAA_RA_NON_ETABLI)

MOTIF_BASE_NON_DECLAREE = 'base_d_attachement_non_declaree'
MOTIF_DATES_INVALIDES = 'dates_du_traite_invalides'

#: ⚠️ POURQUOI LE CODE NE FERME PAS LA PORTE §69 a) — ET §70 EST LU, PAS
#: SUPPOSÉ. §70 dit quand (a) n'est PAS rempli, et il ne fournit aucune règle
#: calculable : sa clause opératoire est « l'entité S'ATTEND à une
#: variabilité importante », un jugement ; et ses facteurs sont introduits
#: par « PAR EXEMPLE », donc illustratifs et sans seuil. Exactement le §54.
PORTE_69A = (
    "La porte §69 a) reste ouverte en droit et le code ne la ferme pas : "
    "§70 subordonne sa fermeture à une ATTENTE de l'entité quant à la "
    "variabilité des flux, et il énumère ses facteurs par « par exemple », "
    "sans aucun seuil. Groupe signalé, non évalué.")


class Traite(NamedTuple):
    """Un traité de réassurance détenue, tel qu'il se déclare."""
    identifiant:     str
    base:            str     # RISQUES_ATTACHANTS ou SINISTRES_SURVENUS
    debut_couverture: object  # date
    fin_couverture:   object  # date


def duree_couverture_69b(traite: Traite, fins_sous_jacentes=()) -> float:
    """La période de couverture au sens du §69 b), EN ANNÉES.

    ⚠️ `fins_sous_jacentes` N'EST LU QU'EN RISQUES ATTACHANTS, et c'est le
    point. En sinistres survenus, la couverture du traité ne déborde pas :
    lui appliquer l'extension rendrait tout traité annuel non éligible, ce
    qui est faux — et c'est l'erreur qui a été commise puis corrigée.
    """
    if traite.base not in BASES:
        raise RefusMesure(
            MOTIF_BASE_NON_DECLAREE,
            f"la base d'attachement du traité « {traite.identifiant} » n'est "
            f"pas déclarée (reçu {traite.base!r}, attendu l'une de {BASES}). "
            f"Elle CHANGE la période de couverture du §69 b) : en risques "
            f"attachants la couverture des polices sous-jacentes compte, en "
            f"sinistres survenus elle ne compte pas. La deviner ferait "
            f"basculer un verdict")
    if traite.fin_couverture <= traite.debut_couverture:
        raise RefusMesure(
            MOTIF_DATES_INVALIDES,
            f"le traité « {traite.identifiant} » finit le "
            f"{traite.fin_couverture} et commence le "
            f"{traite.debut_couverture} : une période de couverture nulle ou "
            f"négative n'est pas une période")

    fin = traite.fin_couverture
    if traite.base == BASE_RISQUES_ATTACHANTS and fins_sous_jacentes:
        fin = max([fin, *fins_sous_jacentes])
    return (fin - traite.debut_couverture).days / 365.25


def eligibilite_69(traite: Traite, *, fins_sous_jacentes=(),
                   attente_69a_declaree: str = '') -> tuple:
    """Le verdict §69 d'un groupe de réassurance détenue, et son motif.

    ⚠️ TROIS VERDICTS, ET AUCUN NE DIT « INÉLIGIBLE ». La porte (b) se
    mesure ; la porte (a) appartient à l'entité et n'est évaluée que si
    elle est DÉCLARÉE. Sans déclaration et avec (b) fermée, le verdict est
    `69A_NON_EVALUEE` — un constat, pas un refus.

    ⚠️ ET EN RISQUES ATTACHANTS SANS COUVERTURES SOUS-JACENTES, LE VERDICT
    EST `NON_ETABLI`. Prendre la seule durée du traité donnerait « éligible »
    à tort sur un traité annuel dont les polices débordent — c'est
    précisément le cas des six quote-parts mesurées.
    """
    duree = duree_couverture_69b(traite, fins_sous_jacentes)

    if (traite.base == BASE_RISQUES_ATTACHANTS and not fins_sous_jacentes):
        return PAA_RA_NON_ETABLI, (
            f"base RISQUES ATTACHANTS et aucune fin de couverture "
            f"sous-jacente fournie. §69 b) inclut « la couverture "
            f"d'assurance découlant de toutes les primes comprises dans le "
            f"périmètre du contrat » : sans elles, la période n'est pas "
            f"calculable. La durée du traité seule ({duree:.3f} an) donnerait "
            f"un « éligible » à tort. §69 b) est DÉCLARÉ, non établi.")

    if duree <= 1.0:
        return PAA_RA_ELIGIBLE, (
            f"la période de couverture au sens du §69 b) vaut {duree:.3f} an, "
            f"au plus un an — la voie automatique est VÉRIFIÉE, et non "
            f"déclarée. Base retenue : {traite.base}.")

    if est_renseigne(attente_69a_declaree):
        return PAA_RA_ELIGIBLE, (
            f"la période de couverture vaut {duree:.3f} an et §69 b) est donc "
            f"fermé, mais la porte §69 a) est DÉCLARÉE et signée : "
            f"« {attente_69a_declaree} ». ⚠️ Cette attente engage l'entité, "
            f"pas ce code — §70 en confie l'appréciation à elle seule.")

    return PAA_RA_69A_NON_EVALUEE, (
        f"la période de couverture au sens du §69 b) vaut {duree:.3f} an, "
        f"soit plus d'un an : §69 b) est fermé. {PORTE_69A}")


def comptes_69(verdicts) -> dict:
    """Combien de traités par verdict — les trois, y compris à zéro.

    ⚠️ LES TROIS CLÉS SONT TOUJOURS PRÉSENTES. Un comptage qui omettrait un
    verdict absent laisserait « 0 non établi » indiscernable de « je n'ai
    pas regardé » — même leçon que le registre du socle.
    """
    comptes = {v: 0 for v in VERDICTS}
    for v in verdicts:
        comptes[v] = comptes.get(v, 0) + 1
    return comptes
