# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 B120 : LE BOUCLAGE DU PRODUIT SUR LA VIE DU GROUPE
=============================================================================

B120, verbatim : « Le total des produits des activités d'assurance pour un
groupe de contrats d'assurance correspond à la contrepartie des contrats,
c'est-à-dire le montant des primes payées à l'entité : a) ajusté pour tenir
compte de l'effet du financement ; et b) exception faite des composantes
investissement. »

⚠️ CE QUE CE MODULE VÉRIFIE, ET QU'AUCUN CONTRÔLE DE PÉRIODE NE PEUT VOIR.
B120 est une identité sur la VIE ENTIÈRE du groupe : la somme des produits
de toutes les périodes doit égaler les primes, ajustées du financement et
diminuées des composantes d'investissement. Trois arrêtés justes un par un
peuvent ne pas boucler ensemble — un terme reconnu deux fois, une période
manquante, un ajustement de financement compté au mauvais endroit.

⚠️ ET SA VRAIE VALEUR EST D'ÊTRE VÉRIFIABLE SANS ORACLE. Cette identité
tient sur n'importe quel portefeuille, sans exemple publié pour la
confirmer. L'oracle ICA 5.6.1 ne fait que confirmer ma lecture de B120 ; il
n'en est pas la source. C'est le seul contrôle de C4 qui ne dépend de
personne.

⚠️ CE MODULE NE CORRIGE RIEN ET NE DEVINE RIEN. Il rend un constat : ça
boucle, ou ça ne boucle pas, et de combien. Un bouclage qui échoue n'est pas
forcément une erreur de calcul — ce peut être une composante
d'investissement non déclarée. Le motif le dit plutôt que d'accuser.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, B120.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_AUCUNE_PERIODE = 'aucune_periode_fournie'

#: Écart en deçà duquel on considère que l'identité tient. ⚠️ CE N'EST PAS
#: UNE TOLÉRANCE MÉTIER : l'identité de B120 est EXACTE en arithmétique. Ce
#: seuil ne couvre que l'accumulation d'erreurs de virgule flottante sur une
#: somme de quelques dizaines de termes. Le relâcher masquerait un vrai
#: défaut ; la mesure du dépôt boucle à 1e-9 près sur l'exemple à trois
#: arrêtés.
EPSILON = 1e-6


class Bouclage(NamedTuple):
    """Le constat, jamais un verdict de faute.

    ⚠️ `boucle` FAUX N'ACCUSE PAS LE CALCUL. Une composante d'investissement
    non déclarée produit le même symptôme. `motif` distingue les deux
    lectures au lieu d'en imposer une.
    """
    total_revenu:  float
    attendu:       float
    ecart:         float
    boucle:        bool
    nb_periodes:   int
    motif:         str


def verifier(*, revenus_periode, primes_encaissees: float,
             charges_financieres: float = 0.0,
             composantes_investissement: float = 0.0,
             epsilon: float = EPSILON) -> Bouclage:
    """B120 — la somme des produits contre la contrepartie du groupe.

    ⚠️ LES SIGNES SONT CEUX DE CE DÉPÔT : produits POSITIFS. La section
    5.6.1 de l'oracle ICA les publie négatifs ; le retournement appartient
    à l'appelant, et il doit être déclaré là où il se fait.
    """
    revenus = list(revenus_periode)
    if not revenus:
        raise RefusMesure(
            MOTIF_AUCUNE_PERIODE,
            "aucune période fournie. Un bouclage sur zéro période ne vaut "
            "pas « ça boucle » — il ne vaut rien, et rendre True ici serait "
            "la même faute qu'une gate rendant « Ran 0 tests » en sortant 0")
    for i, r in enumerate(revenus):
        if r < 0:
            raise RefusMesure(
                'montant_negatif',
                f"le produit de la période {i + 1} vaut {r}. Ce module "
                f"attend la convention POSITIVE ; un négatif signale un "
                f"retournement de signe non fait par l'appelant")

    total = sum(revenus)
    attendu = primes_encaissees + charges_financieres - composantes_investissement
    ecart = total - attendu
    boucle = abs(ecart) <= epsilon

    if boucle:
        motif = ''
    else:
        motif = (
            f"B120 ne boucle pas : {len(revenus)} période(s) totalisent "
            f"{total:.2f} de produits, contre {attendu:.2f} attendus "
            f"({primes_encaissees:.2f} de primes + {charges_financieres:.2f} "
            f"de charges financières - {composantes_investissement:.2f} de "
            f"composantes d'investissement). Écart {ecart:+.2f}. "
            f"⚠️ DEUX LECTURES POSSIBLES, ce module n'en impose aucune : un "
            f"défaut d'affectation entre périodes, OU une composante "
            f"d'investissement présente et non déclarée.")

    return Bouclage(total_revenu=total, attendu=attendu, ecart=ecart,
                    boucle=boucle, nb_periodes=len(revenus), motif=motif)
