# -*- coding: utf-8 -*-
"""
=============================================================================
  Le cas qui exhibe un angle mort qu'aucun oracle publié ne discrimine
=============================================================================

⚠️ PROVENANCE — ET C'EST ELLE QUI FAIT LA VALEUR DE CE FICHIER. Ce cas n'est
PAS une source publiée et n'a aucune autorité normative. C'est une
CONSTRUCTION D'UN TIERS : un collègue de l'actuaire signataire l'a bâtie
pour montrer que deux assemblages concurrents passent l'un et l'autre les
deux oracles ICA disponibles, tout en divergeant sur un cas réel. Livrée le
13/08/2026 dans `assemblage_paa_cas_degeneres.csv`.

⚠️ POURQUOI LE CONSERVER PLUTÔT QUE DE LE JETER. Les deux oracles ICA
n'annulent chacun qu'UNE composante — §5.2 met le taux à zéro, §5.6.1 met
les frais d'acquisition à zéro. Le TERME D'INTERACTION est donc nul dans les
deux, et aucun ne peut départager une assiette brute d'une assiette nette.
Ce cas-ci porte les DEUX effets ensemble : il ne prouve rien, mais il MONTRE
ce que les oracles laissent passer. Un angle mort nommé vaut mieux qu'un
angle mort ignoré.

⚠️ CE QU'IL N'EST PAS : un oracle. Personne n'a publié la bonne réponse pour
ce cas. Les valeurs ci-dessous sont celles de la construction tierce, et
elles ne servent qu'à VÉRIFIER QUE L'ÉCART EXISTE — jamais à valider un
résultat. L'arbitrage, lui, a été tranché sur le TEXTE : voir
`mesure.financement.ASSIETTE`, fondé sur §56 et §55 a) ii).

=============================================================================
"""

PROVENANCE = (
    "construction d'un tiers — collègue de l'actuaire signataire, livrée le "
    "13/08/2026 dans `assemblage_paa_cas_degeneres.csv`. AUCUNE autorité "
    "normative : ce n'est pas une source publiée, et personne n'a publié la "
    "bonne réponse pour ce cas. Conservé parce qu'il MONTRE un angle mort "
    "que les deux oracles ICA ne discriminent pas.")

#: Le cas : un contrat type dommages-ouvrage, dix ans, frais ET taux non nuls.
ENTREE = {
    'prime': 4800.0,
    'duree_ans': 10,
    'frais_acquisition': 360.0,
    'taux': 0.02,
}

#: Le LRC des deux variantes concurrentes, aux périodes que la construction
#: tierce publie. ⚠️ `nette` est celle que le TEXTE impose (§56 + §55 a) ii) ;
#: `brute` est conservée pour que le test puisse montrer qu'elle DIFFÈRE.
LRC_PAR_ASSIETTE = {
    #  période : (assiette brute, assiette nette)
    1:  (4082.40, 4075.92),
    3:  (3313.66, 3298.23),
    5:  (2469.79, 2451.06),
    8:  (1052.79, 1040.43),
    10: (0.0,     0.0),
}

#: ⚠️ CE QUE L'ANGLE MORT COÛTE, chiffré par la construction tierce.
ECART_MAXIMAL_PAR_CONTRAT = 18.73      # à la période 5
ECART_MAXIMAL_EN_PART_DU_LRC = 0.0117  # 1,17 %, à la période 8

#: ⚠️ ET LE FAIT QUI JUSTIFIE TOUT CE FICHIER : les deux variantes passent
#: les DEUX oracles. Le vert n'a donc pas départagé, et ne pouvait pas.
LES_DEUX_PASSENT_LES_ORACLES = True
