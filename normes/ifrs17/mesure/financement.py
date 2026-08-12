# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §56 : LA COMPOSANTE DE FINANCEMENT DU LRC
=============================================================================

Quand la composante de financement d'un groupe est significative, le §56
impose d'ajuster le LRC de la valeur temps de l'argent, au taux verrouillé
à la comptabilisation initiale (§B72 a).

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
26.9.2023, §56 et B72 a).
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.lrc_paa import (
    RefusMesure,
    lrc_suivant,
    revenue_prorata_temporis,
)

MOTIF_TAUX_SANS_SIGNATURE = 'taux_verrouille_sans_signataire'
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
    """Le taux du §B72 a), avec ce qui le rend opposable.

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
    if not (actuaire_resp or '').strip():
        raise RefusMesure(
            MOTIF_TAUX_SANS_SIGNATURE,
            "aucun actuaire ne se porte garant de ce taux. Le §56 fait "
            "entrer une charge financière dans le résultat : elle engage "
            "quelqu'un, nommément")
    if not (source or '').strip():
        raise RefusMesure(
            MOTIF_TAUX_SANS_SOURCE,
            "le taux est fourni sans sa source. « D'où vient ce taux » est "
            "la première question d'un commissaire aux comptes")
    if not (arrete_verrouillage or '').strip():
        raise RefusMesure(
            MOTIF_TAUX_SANS_ARRETE,
            "le taux est fourni sans sa date de verrouillage. §B72 a) le "
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
    """§56 — la désactualisation de la période, au taux verrouillé."""
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


def roll_forward(*, prime: float, duree_ans: int, taux: TauxVerrouille,
                 eligibilite_declaree: bool = False
                 ) -> tuple[ArreteFinancement, ...]:
    """Le LRC arrêté par arrêté, prime encaissée en totalité à l'origine.

    ⚠️ LE LRC INITIAL VAUT LA PRIME ENTIÈRE ICI, et ce n'est pas une
    hypothèse cachée : les frais d'acquisition valent zéro dans le cas que
    cette fonction sert. Un groupe qui en porterait exigerait le §55 a)
    complet, et l'interaction financement × frais d'acquisition N'EST PAS
    VERROUILLÉE par l'oracle disponible — voir `oracles.ica_222092.LACUNES`.
    """
    lrc = prime
    cumul_charges = cumul_revenu = 0.0
    arretes = []
    for periode in range(1, duree_ans + 1):
        charge = charge_financiere(lrc, taux)
        cumul_charges += charge
        revenu_fin = revenu_de_financement(cumul_charges, cumul_revenu,
                                           duree_ans - periode + 1)
        cumul_revenu += revenu_fin
        revenu_prime = revenue_prorata_temporis(prime, duree_ans)
        cloture = lrc_suivant(
            lrc, revenue_periode=revenu_prime + revenu_fin,
            charge_financiere=charge,
            eligibilite_declaree=eligibilite_declaree,
            financement_significatif=True)
        arretes.append(ArreteFinancement(
            periode=periode, lrc_ouverture=lrc, charge_financiere=charge,
            revenu_financement=revenu_fin, revenu_prime=revenu_prime,
            revenu_total=revenu_prime + revenu_fin, lrc_cloture=cloture))
        lrc = cloture
    return tuple(arretes)
