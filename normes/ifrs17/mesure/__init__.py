# -*- coding: utf-8 -*-
"""Mesure IFRS 17 — la méthode d'affectation des primes (§55-59).

⚠️ FRONTIÈRE AVEC LE SOCLE, TENUE DANS LES DEUX SENS. Le socle
(`normes/ifrs17/socle/`) répond à « quels groupes existent » et ne porte
AUCUN montant — un test l'interdit. Ce paquet-ci répond à « combien
valent-ils ». Il ne prend donc pas de `Groupe` en entrée : il prend des
montants nommés, et l'appariement des deux relève de l'appelant.

⚠️ ET IL NE DÉCIDE PAS DE L'ÉLIGIBILITÉ. §53 s'apprécie à la création du
groupe et le socle le scelle ; mesurer en PAA un groupe qui n'y a pas droit
serait une faute que ce paquet ne peut pas rattraper. Il exige donc que
l'éligibilité lui soit DÉCLARÉE, et refuse à défaut.

⚠️ `PARAGRAPHE_DES_MODULES` — LE REGISTRE, ET SA PORTÉE EXACTE. Tout module
de ce paquet doit y être inscrit ; un oubli fait échouer la gate,
BRUYAMMENT. C'est une liste à tenir, et c'est assumé : le périmètre publié a
vieilli deux fois en une journée faute de relecture, et une liste dont
l'oubli est bruyant n'est pas du même bois qu'une liste dont l'oubli est
silencieux.

⚠️ CE QU'IL NE PROUVE PAS : le registre force à REGARDER la raison du
périmètre, il ne peut pas forcer à y écrire la vérité. C'est un rappel
mécanique, pas une preuve — et un instrument qui ne dit pas sa portée se
fait surévaluer.
"""

#: Le paragraphe d'IFRS 17 que sert chaque module de mesure.
#:
#: ⚠️⚠️ POURQUOI CE REGISTRE EXISTE, ET IL A ÉTÉ PAYÉ DEUX FOIS. Le périmètre
#: publié a vieilli deux fois en une journée, les deux fois parce qu'un lot de
#: construction avait été poussé sans que la raison correspondante soit
#: relue : elle continuait de dire « reste à bâtir » quand le module existait.
#: Sous-affirmer trompe autant que sur-affirmer.
#:
#: ⚠️ OUI, C'EST UNE LISTE À TENIR — et j'ai retiré le motif vulture le même
#: jour EN LUI REPROCHANT D'EN ÊTRE UNE. La différence tient en un mot, et
#: c'est tout le sujet : OUBLIER ICI FAIT ÉCHOUER LA GATE, BRUYAMMENT. Le
#: motif vulture, lui, se taisait quand il ne couvrait pas un nom. Une liste
#: dont l'oubli est bruyant n'est pas du même bois qu'une liste dont l'oubli
#: est silencieux.
#:
#: ⚠️ ET VOICI CE QUE CE VERROU NE FAIT PAS, pour qu'on ne s'y fie pas plus
#: qu'il ne vaut : il force à REGARDER la raison du périmètre, il ne peut pas
#: forcer à y écrire la vérité. C'est un rappel mécanique, pas une preuve.
PARAGRAPHE_DES_MODULES = {
    'attribution':    '§55-59, B125-B126',
    'bilan':          '§78-92',
    'bouclage_b120':  '§55-59, B125-B126',
    # ⚠️ `declaration` ne sert AUCUN paragraphe en propre : il porte le
    # contrôle « non vide n'est pas renseigné », commun aux cinq portes de
    # signature. Il est rattaché au pan des flux d'exécution parce que c'est
    # là que le défaut a été trouvé — une déclaration d'ajustement pour
    # risque signée « A_RENSEIGNER », acceptée sans broncher.
    'declaration':    '§33-37, B36-B92',
    'deficit':        '§55-59, B125-B126',
    'financement':    '§55-59, B125-B126',
    'financier_lic':  '§78-92',
    'flux_execution': '§33-37, B36-B92',
    'lic':            '§55-59, B125-B126',
    'lrc_paa':        '§55-59, B125-B126',
    'reassurance_63': '§60-70A',
    'reassurance_69': '§60-70A',
    'resultat_80':    '§78-92',
    'revenu_b125':    '§55-59, B125-B126',
}
