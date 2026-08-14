# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 B125-B126 : LE PRODUIT DES ACTIVITÉS D'ASSURANCE
=============================================================================

⚠️⚠️ LA QUESTION QUE CE MODULE TRANCHE, ET ELLE VALAIT 62 097,66 € SUR UN
DOSSIER RÉEL : faut-il AJOUTER au produit des activités d'assurance la part
des primes qui recouvre les frais d'acquisition ? NON. Ce serait un DOUBLE
COMPTE. Mesuré en lisant les deux paragraphes.

B126, verbatim : « le montant des produits des activités d'assurance de la
période doit être LE MÊME QUE celui des encaissements de primes attendus
affectés à la période (exception faite des composantes investissement et
ajusté, en application du paragraphe 56, pour tenir compte de la valeur
temps de l'argent…) ».

⚠️ LES EXCEPTIONS DE B126 SONT LIMITATIVES — il y en a DEUX : les
composantes d'investissement, et l'ajustement du §56. Le recouvrement des
frais d'acquisition n'y figure pas. Le produit en PAA est donc la TOTALITÉ
de la prime affectée à la période, laquelle contient DÉJÀ le chargement
d'acquisition. Y ajouter ce chargement le compterait deux fois.

⚠️ CE QUE B125 DEMANDE N'EST PAS UNE ADDITION, C'EST UNE IDENTIFICATION.
« L'entité doit déterminer les produits […] afférents aux flux de trésorerie
liés aux frais d'acquisition en AFFECTANT LA PART DES PRIMES IMPUTÉE au
recouvrement de ces flux […] d'une manière systématique qui reflète
l'écoulement du temps. Elle doit comptabiliser LE MÊME MONTANT à titre de
charges. » On désigne une part À L'INTÉRIEUR du produit, et on lui fait
correspondre une charge égale. Le total ne bouge pas.

⚠️⚠️ CE QUE L'ORACLE NE VÉRIFIE PAS ICI, ET IL FAUT LE DIRE. L'exemple ICA
5.2 publie un produit de 500 et des charges de 150 ; il NE PUBLIE PAS la
ventilation « dont 100 au titre du recouvrement ». La règle du non-double-
compte EST confrontable à l'oracle — le produit doit rester 500 — mais la
VENTILATION elle-même ne l'est pas. Elle est une lecture de B125, pas une
valeur attestée par une source externe.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, B125 à B127.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_CHARGE_DISCORDANTE = 'charge_b125_differente_du_produit'

#: ⚠️ CE QUE B125 EXIGE ET QUE CE MODULE NE PEUT PAS DEVINER. B125 impose
#: une affectation « systématique qui reflète l'écoulement du temps ». Le
#: prorata linéaire en est une, et c'est celle que l'exemple ICA emploie —
#: mais une entité peut en retenir une autre, tout aussi systématique. Le
#: module applique le linéaire et le DIT, il ne prétend pas que c'est la
#: seule.
BASE_AFFECTATION = ("prorata temporis linéaire — une manière systématique "
                    "reflétant l'écoulement du temps au sens de B125, pas "
                    "la seule possible")


class VentilationB125(NamedTuple):
    """Le produit de la période, et la part qui recouvre l'acquisition.

    ⚠️ `total` N'EST PAS `service + recouvrement` PAR CONSTRUCTION SEULEMENT
    — c'est le point même de ce module. Le total vient de B126 (la prime
    affectée) ; la ventilation vient de B125. Si la somme s'écartait du
    total, c'est que quelqu'un aurait ajouté au lieu d'identifier.
    """
    total:          float   # B126 — la prime affectée à la période
    recouvrement:   float   # B125 — la part imputée aux frais d'acquisition
    service:        float   # le reste
    charge_egale:   float   # B125 — « le même montant » en charges
    base:           str


def ventiler(*, revenu_periode: float, frais_acquisition: float,
             duree_couverture: int) -> VentilationB125:
    """B125 dans B126 : identifier, jamais ajouter.

    ⚠️ `revenu_periode` ENTRE ET RESSORT INCHANGÉ. Ce module ne fabrique pas
    de produit : il en désigne une part. C'est la garantie contre le double
    compte, et elle est vérifiable d'un coup d'œil sur le corps.
    """
    if duree_couverture <= 0:
        raise RefusMesure(
            'duree_de_couverture_invalide',
            f"la durée vaut {duree_couverture} ; l'affectation systématique de "
            f"B125 exige une durée strictement positive")
    if frais_acquisition < 0 or revenu_periode < 0:
        raise RefusMesure(
            'montant_negatif',
            "B125 s'applique à des montants en valeur absolue ; ce module "
            "pose les signes lui-même")

    recouvrement = frais_acquisition / duree_couverture
    if recouvrement > revenu_periode:
        raise RefusMesure(
            MOTIF_CHARGE_DISCORDANTE,
            f"la part de recouvrement ({recouvrement}) dépasse le produit "
            f"de la période ({revenu_periode}). B125 identifie une part À "
            f"L'INTÉRIEUR du produit : une part plus grande que le tout "
            f"signale des frais d'acquisition sans rapport avec la prime")

    return VentilationB125(
        total=revenu_periode,
        recouvrement=recouvrement,
        service=revenu_periode - recouvrement,
        charge_egale=recouvrement,      # B125 : « le même montant »
        base=BASE_AFFECTATION)
