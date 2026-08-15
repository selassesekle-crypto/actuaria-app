# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §56 : LA COMPOSANTE DE FINANCEMENT DU LRC
=============================================================================

Quand la composante de financement d'un groupe est significative, le §56
impose d'ajuster le LRC de la valeur temps de l'argent, au taux verrouillé
à la comptabilisation initiale (§B72 d).

⚠️⚠️ ET CE MODULE A CITÉ « B72 a) » SIX FOIS, À TORT — une référence qui, lue,
RÉFUTE la règle qu'elle appuyait. B72 énumère les taux par usage :

  · **B72 a)** : « pour évaluer les FLUX DE TRÉSORERIE D'EXÉCUTION — des taux
    d'actualisation COURANTS respectant le paragraphe 36 ». C'est l'exact
    CONTRAIRE d'un taux verrouillé, et c'est ce qui gouverne `flux_execution`.
  · **B72 d)** : « pour ajuster, EN APPLICATION DU PARAGRAPHE 56, la valeur
    comptable du passif au titre de la couverture restante des groupes
    auxquels est appliquée la méthode d'affectation des primes et qui
    comportent une composante financement importante — des taux [...]
    DÉTERMINÉS LORS DE LA COMPTABILISATION INITIALE ». C'est celui-ci.

⚠️ LE COMPORTEMENT ÉTAIT JUSTE, LA JUSTIFICATION ÉTAIT FAUSSE. Le verrouillage
est fondé — par B72 d). Mais dans un dépôt destiné à un commissaire aux
comptes, une référence erronée est un défaut à part entière : c'est la
première chose qu'il vérifiera, et elle l'aurait mené à conclure l'inverse.

⚠️ LE TAUX EST UNE ENTRÉE DÉCLARÉE ET SIGNÉE, PAS UNE VALEUR DEVINÉE. Ce
module ne va chercher aucune courbe : il exige qu'on lui remette un taux,
la date à laquelle il a été verrouillé, la source dont il sort, et le nom de
l'actuaire qui l'atteste. Sans signature, il refuse — même porte que le
scellement du registre dans le socle.

⚠️ CE QUI RESTE HORS PÉRIMÈTRE, ET LA DISTINCTION EST LE FRUIT D'UN LOT
ENTIER (d331a64) : appliquer un taux verrouillé FOURNI est un paramètre ;
constituer un MAGASIN de courbes historiques interrogeable par date est un
ouvrage. Ce module fait le premier. Le second n'est pas bâti, et la raison
du périmètre le dit.

⚠️ §56 S'APPLIQUE AUSSI À DES GROUPES PLURIANNUELS MESURÉS EN PAA. Le §53
ouvre deux portes ; échouer à la voie automatique du §53 b) ne renvoie pas
au modèle général. L'oracle ICA 5.6.1 en est la preuve chiffrée : trois ans,
en PAA, avec financement.

⚠️ CONVENTION DE SIGNE. Ce module rend le revenu POSITIF, comme `lrc_paa` et
comme la section 5.2 de l'oracle. La section 5.6.1 le publie NÉGATIF. Le
retournement est fait au point de comparaison, dans le test, et il y est
écrit — jamais en silence.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §56, B72 d) et B72 a) — ce dernier par CONTRASTE.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import (
    est_renseigne,
    exiger_taux_de_la_cohorte,
)
from normes.ifrs17.mesure.lrc_paa import (
    RefusMesure,
    lrc_initial,
    lrc_suivant,
    revenue_prorata_temporis,
)

#: ⚠️⚠️ L'ARBITRAGE DE L'ASSIETTE — POSÉ ICI PARCE QU'IL NE L'AVAIT JAMAIS
#: ÉTÉ. Sur quoi la charge financière du §56 s'applique-t-elle : le passif
#: AVANT déduction des frais d'acquisition, ou APRÈS ? Deux implémentations
#: concurrentes existent, elles passent TOUTES DEUX les oracles ICA §5.2 et
#: §5.6.1, et elles divergent de 1,17 % du LRC sur un contrat de dix ans.
#: Aucun oracle disponible ne les départage — le terme d'interaction est nul
#: dans chacun des deux exemples.
#:
#: ⚠️ LE TEXTE LES DÉPARTAGE, ET PAR L'ARGUMENT LE PLUS SIMPLE QUI SOIT : les
#: deux paragraphes emploient LA MÊME EXPRESSION.
#:
#:   · §56 : « l'entité doit ajuster LA VALEUR COMPTABLE DU PASSIF AU TITRE
#:     DE LA COUVERTURE RESTANTE pour tenir compte de la valeur temps de
#:     l'argent » ;
#:   · §55 a) : « LA VALEUR COMPTABLE DU PASSIF est égale à : i) les primes
#:     reçues […] ii) MOINS […] le montant […] des flux de trésorerie liés
#:     aux frais d'acquisition ».
#:
#: §56 actualise la valeur comptable du passif ; §55 a) définit cette valeur
#: comme NETTE des frais d'acquisition. L'assiette est donc NETTE. La
#: variante brute actualiserait une grandeur qui n'est pas la valeur
#: comptable du passif.
#:
#: ⚠️ ET POURQUOI CETTE NOTE EXISTE : ce module retenait DÉJÀ l'assiette
#: nette — mais par ACCIDENT, parce qu'elle tombe de `lrc_initial` qui
#: déduit les frais. Le choix n'avait été ni posé, ni écrit, ni testé. Un
#: arbitrage qui se trouve juste sans avoir été pris tient par chance, et la
#: chance ne se relit pas dans six mois.
ASSIETTE = (
    "NETTE des frais d'acquisition — §56 ajuste « la valeur comptable du "
    "passif au titre de la couverture restante », et §55 a) ii) définit "
    "cette valeur comptable comme les primes reçues MOINS les flux de "
    "trésorerie liés aux frais d'acquisition. Les deux paragraphes emploient "
    "la même expression : l'assiette de l'actualisation est le passif NET.")

MOTIF_TAUX_SANS_SIGNATURE = 'taux_verrouille_sans_signataire'
MOTIF_LRC_NON_ETEINT = 'lrc_non_eteint_en_fin_de_couverture'
MOTIF_TAUX_SANS_SOURCE = 'taux_verrouille_sans_source'
MOTIF_TAUX_SANS_ARRETE = 'taux_verrouille_sans_arrete'
MOTIF_TAUX_ABERRANT = 'taux_verrouille_aberrant'

#: ⚠️ BORNES DE VRAISEMBLANCE, PAS DE NORME. Aucun paragraphe d'IFRS 17 ne
#: borne un taux d'actualisation. Ces bornes n'existent que pour attraper une
#: erreur d'unité — 2 saisi pour 2 %, qui multiplierait le LRC par trois en un
#: arrêté. Un taux légitime hors de ces bornes doit faire changer les bornes,
#: pas contourner le contrôle.
TAUX_MIN, TAUX_MAX = -0.10, 0.25


class TauxVerrouille(NamedTuple):
    """Le taux du §B72 d), avec ce qui le rend opposable.

    ⚠️ LES QUATRE CHAMPS SONT OBLIGATOIRES. Un taux sans source ne se
    justifie pas devant un contrôleur ; un taux sans date de verrouillage ne
    se rattache à aucun groupe ; un taux sans signataire n'engage personne.
    """
    taux:                float
    arrete_verrouillage: str    # la date de comptabilisation initiale
    source:              str    # d'où sort la courbe
    actuaire_resp:       str    # qui l'atteste


def verrouiller(taux: float, arrete_verrouillage: str, source: str,
                actuaire_resp: str) -> TauxVerrouille:
    """Constitue un taux verrouillé, ou REFUSE en disant ce qui manque."""
    if not est_renseigne(actuaire_resp):
        raise RefusMesure(
            MOTIF_TAUX_SANS_SIGNATURE,
            "aucun actuaire ne se porte garant de ce taux. Le §56 fait "
            "entrer une charge financière dans le résultat : elle engage "
            "quelqu'un, nommément")
    if not est_renseigne(source):
        raise RefusMesure(
            MOTIF_TAUX_SANS_SOURCE,
            "le taux est fourni sans sa source. « D'où vient ce taux » est "
            "la première question d'un commissaire aux comptes")
    if not est_renseigne(arrete_verrouillage):
        raise RefusMesure(
            MOTIF_TAUX_SANS_ARRETE,
            "le taux est fourni sans sa date de verrouillage. §B72 d) le "
            "fige à la comptabilisation initiale du groupe : sans cette "
            "date, il ne se rattache à aucun groupe")
    if not TAUX_MIN <= taux <= TAUX_MAX:
        raise RefusMesure(
            MOTIF_TAUX_ABERRANT,
            f"le taux vaut {taux}, hors des bornes de vraisemblance "
            f"[{TAUX_MIN}, {TAUX_MAX}]. Ces bornes ne viennent d'aucun "
            f"paragraphe : elles n'existent que pour attraper une erreur "
            f"d'unité — 2 saisi pour 2 %")
    return TauxVerrouille(taux, arrete_verrouillage.strip(), source.strip(),
                          actuaire_resp.strip())


class ArreteFinancement(NamedTuple):
    """Un arrêté du roll-forward §56. Revenu en convention POSITIVE."""
    periode:            int
    lrc_ouverture:      float
    charge_financiere:  float
    revenu_financement: float
    revenu_prime:       float
    revenu_total:       float
    lrc_cloture:        float


def charge_financiere(lrc_ouverture: float,
                      taux: TauxVerrouille) -> float:
    """§56 — la désactualisation de la période, au taux verrouillé.

    ⚠️ CETTE FONCTION NE CONTRÔLE PAS LA PÉREMPTION DU TAUX, et c'est dit
    plutôt que tu : elle est un calcul d'une ligne, appelée depuis
    `roll_forward` qui, lui, confronte l'arrêté de verrouillage au contexte
    évalué. L'appeler directement contourne ce contrôle.
    """
    return lrc_ouverture * taux.taux


def revenu_de_financement(cumul_charges: float, cumul_revenu_anterieur: float,
                          periodes_restantes: int) -> float:
    """La part de la charge financière reconnue en produits sur la période.

    ⚠️ CE N'EST PAS LA CHARGE DE LA PÉRIODE. La charge financière grossit le
    passif ; le produit en reconnaît la part correspondant au service DÉJÀ
    fourni. L'écart entre les deux est ce qui reste à reconnaître, et c'est
    pourquoi la formule regarde des CUMULS et non des flux de période.
    """
    if periodes_restantes <= 0:
        raise RefusMesure(
            'periodes_restantes_invalides',
            f"il reste {periodes_restantes} période(s) : la part du service "
            f"fournie n'est pas calculable")
    return (cumul_charges - cumul_revenu_anterieur) / periodes_restantes


def roll_forward(*, prime: float, nb_periodes: int, taux: TauxVerrouille,
                 contexte, cohorte_du_groupe: str = '',
                 forme_du_taux_verrouille: str = '',
                 intervalle_emission=None,
                 ponderation_declaree: str = '',
                 frais_acquisition: float = 0.0,
                 verdict_53_declare: str = ''
                 ) -> tuple[ArreteFinancement, ...]:
    """Le LRC arrêté par arrêté, prime encaissée en totalité à l'origine.

    ⚠️ LES FRAIS D'ACQUISITION SONT UN PARAMÈTRE, ET ILS NE L'ÉTAIENT PAS.
    Cette fonction supposait des frais nuls, si bien que le cas RÉEL —
    financement ET frais ensemble — n'était pas exprimable et devait être
    composé à la main par l'appelant. C'est exactement là que je me suis
    trompé en confrontant ce module à une implémentation tierce : 550,66 €
    d'écart, en silence.

    ⚠️ L'ASSIETTE DE LA CHARGE EST LE LRC NET — voir `ASSIETTE` en tête de
    module, où l'arbitrage est posé et fondé sur §56 et §55 a) ii). Les deux
    oracles disponibles ne le départagent PAS : le terme d'interaction y est
    nul des deux côtés.

    ⚠️ ET LE LRC DOIT S'ÉTEINDRE. Un roll-forward mené sur toute la durée de
    couverture finit à zéro ; ne pas le vérifier laisserait passer un terme
    perdu, ce qui est précisément l'erreur que j'ai commise.
    """
    #: ⚠️⚠️ ET UNE BORNE « ANTÉRIEUR OU ÉGAL » NE SUFFISAIT PAS : elle
    #: acceptait un taux de 2020 pour une cohorte 2024. B72 d) fige le taux à
    #: la comptabilisation initiale DU GROUPE — la comparaison se fait donc
    #: contre SA cohorte, pas contre une borne lâche.
    exiger_taux_de_la_cohorte(
        arrete_verrouillage=taux.arrete_verrouillage,
        cohorte=cohorte_du_groupe, contexte=contexte, erreur=RefusMesure,
        forme=forme_du_taux_verrouille,
        intervalle_emission=intervalle_emission,
        ponderation_declaree=ponderation_declaree,
        objet="le taux verrouillé (B72 d)")

    lrc = lrc_initial(prime, frais_acquisition,
                      verdict_53_declare=verdict_53_declare)
    amortissement = frais_acquisition / nb_periodes
    cumul_charges = cumul_revenu = 0.0
    arretes = []
    for periode in range(1, nb_periodes + 1):
        # ⚠️ ASSIETTE NETTE : `lrc` porte déjà la déduction du §55 a) ii).
        charge = charge_financiere(lrc, taux)
        cumul_charges += charge
        revenu_fin = revenu_de_financement(cumul_charges, cumul_revenu,
                                           nb_periodes - periode + 1)
        cumul_revenu += revenu_fin
        revenu_prime = revenue_prorata_temporis(prime, nb_periodes)
        cloture = lrc_suivant(
            lrc, amortissement_frais_acquisition=amortissement,
            revenue_periode=revenu_prime + revenu_fin,
            charge_financiere=charge,
            verdict_53_declare=verdict_53_declare,
            financement_significatif=True)
        arretes.append(ArreteFinancement(
            periode=periode, lrc_ouverture=lrc, charge_financiere=charge,
            revenu_financement=revenu_fin, revenu_prime=revenu_prime,
            revenu_total=revenu_prime + revenu_fin, lrc_cloture=cloture))
        lrc = cloture

    if abs(lrc) > 1e-6:
        raise RefusMesure(
            MOTIF_LRC_NON_ETEINT,
            f"le passif au titre de la couverture restante vaut {lrc:.2f} "
            f"après les {nb_periodes} période(s) de couverture, au lieu de "
            f"zéro. Un terme du déroulé a été perdu ou compté deux fois. "
            f"⚠️ Ce contrôle existe parce que l'erreur a été COMMISE : une "
            f"composition à la main omettant de relâcher le revenu de "
            f"financement a laissé 550,66 € de résidu sans que rien ne le "
            f"signale")
    return tuple(arretes)
