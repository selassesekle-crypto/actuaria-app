# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — LE RÉFÉRENTIEL DES MÉTHODES (lot C3a)
=============================================================================

 ⚠️ POURQUOI CE MODULE EXISTE.

 La même table était recopiée SIX fois : `label_map` et `res_map` dans le
 graphique de convergence, `label_map` dans l'Excel, `label_map` plus DEUX
 dictionnaires en ligne dans le commentaire. Aucune n'était l'autorité, et
 aucune ne savait ce que les autres disaient.

 La dette était même datée : `n4_best_estimate.py` portait, au-dessus de
 `_LIBELLE_METHODE`, la mention « Source unique pour ce module ; la couche N5
 aura la sienne au lot C ». La voici.

 CE N'EST PAS QU'UNE QUESTION DE LIBELLÉS — C'EST CE QUI PRODUISAIT LES
 « 0 € ». Chacune des copies faisait `.get(methode, 0)` : une méthode qu'on
 n'a PAS PU calculer, faute d'exposition, ressortait avec une réserve de zéro
 euro. Le graphique dessinait une barre à 0 €, l'Excel une ligne à 0, le
 commentaire écrivait « 0 € ». `n4_best_estimate.py` avait pourtant la bonne
 garde depuis toujours :

     if not n3.get(_CLES_N3[m], {}).get('disponible', True):
         exclues[m] = (r, 'non calculée')

 D'où `reserve()` ci-dessous, qui rend **None** et non zéro. Le faux zéro
 devient impossible à écrire : un appelant doit traiter l'absence.

 ⚠️ POURQUOI CE MODULE EST NEUTRE, ET NON DANS N4.
 Le référentiel a QUATRE consommateurs — le calcul du Best Estimate et les
 trois générateurs de livrables. Une donnée partagée par quatre modules
 n'appartient à aucun. Mesuré, et contre mon intuition de départ : importer
 N4 depuis N5 ne coûte RIEN (0,000 s, +0 module — l'arbre est déjà chargé).
 L'argument n'est donc pas la performance, c'est la direction de dépendance :
 la présentation n'a pas à passer par le moteur de calcul pour connaître le
 nom d'une méthode. Précédent du dépôt : `reglementation/segments_s2.py`
 (lot B10-b), partagé par A7 et A10.

 ⚠️ CE QUI RESTE DANS N4, ET POURQUOI. `PORTEURS_DE_CIBLE` NE bouge PAS :
 c'est de la gouvernance, écrite tout entière en termes de « cible DANS /
 HORS `_CLES_N3` », et `test_a7_gouvernance` vérifie que les deux tables se
 répondent. Ici, on ne publie que le référentiel : quelles méthodes existent,
 comment on les nomme, où on lit leur réserve, et lesquelles entrent au BE.
=============================================================================
"""

from typing import Dict, Optional

#: LE LITTÉRAL UNIQUE. Pour chaque méthode qu'A7 présente :
#:     (clé dans n3, clé de la réserve dans ce sous-dict, libellé, entre au BE)
#:
#: ⚠️ LA COLONNE « ENTRE AU BE » EST LA FRONTIÈRE, ET ELLE EST GARDÉE PAR UN
#: TEST SYNTAXIQUE (GB-2). Mack 1993 est PRÉSENTÉE et n'entre PAS : son point
#: estimate VAUT Chain Ladder (commit 6e2e66e), la compter deux fois serait un
#: double comptage. Elle reste affichée parce qu'elle porte l'incertitude.
#:
#: Les trois méthodes du BE CONSOMMENT TOUTES LE MÊME MOTIF de développement —
#: prouvé au correctif f_cum, qui a déplacé BF de +2,2 % et Cape Cod de +3,2 %
#: sans toucher Chain Ladder. Une colonne de facteurs invalidée les frappe donc
#: ensemble : c'est pourquoi la couverture du motif est une propriété de
#: l'ANNÉE, pas de la méthode.
_METHODES = {
    'chain_ladder':         ('chain_ladder', 'reserve_totale',
                             'Chain Ladder',         True),
    'mack':                 ('mack',         'reserve_best_estimate',
                             'Mack 1993',            False),
    'bornhuetter_ferguson': ('bf',           'reserve_totale',
                             'Bornhuetter-Ferguson', True),
    'cape_cod':             ('cape_cod',     'reserve_totale',
                             'Cape Cod',             True),
}

#: Les trois méthodes qui construisent le Best Estimate, avec la clé sous
#: laquelle N3 expose leur IBNR par année. DÉRIVÉ du littéral ci-dessus, une
#: ligne plus bas : aucune dérive possible entre les deux.
_CLES_N3: Dict[str, str] = {m: v[0] for m, v in _METHODES.items() if v[3]}

#: Libellé lisible d'une méthode — la trace, les messages et les livrables ne
#: doivent pas publier une clé technique là où l'actuaire attend un nom.
_LIBELLE_METHODE: Dict[str, str] = {m: v[2] for m, v in _METHODES.items()}

#: L'ordre d'affichage, celui dans lequel les livrables énumèrent les méthodes.
ORDRE_AFFICHAGE = tuple(_METHODES)


def libelle(methode: str) -> str:
    """Le nom lisible d'une méthode ; la clé technique à défaut."""
    return _LIBELLE_METHODE.get(methode, methode)


def disponible(n3: Dict, methode: str) -> bool:
    """La méthode a-t-elle pu être calculée ?

    Reprend à l'identique la garde de `n4_best_estimate._admissibilite_globale`
    — même défaut par défaut à True, pour qu'une méthode sans drapeau reste
    affichée plutôt que de disparaître en silence.
    """
    cle = _METHODES.get(methode, (methode,))[0]
    return bool(n3.get(cle, {}).get('disponible', True))


def reserve(n3: Dict, methode: str) -> Optional[float]:
    """La réserve d'une méthode, ou **None** si elle n'a pas pu être calculée.

    ⚠️ NONE ET NON ZÉRO, C'EST TOUT L'INTÉRÊT. « Non calculable faute
    d'exposition » et « réserve de zéro euro » sont deux affirmations
    différentes, et la seconde est fausse. Un appelant qui formate None sans
    y penser produit une erreur visible ; un appelant qui formatait 0 publiait
    un mensonge lisible.
    """
    if methode not in _METHODES or not disponible(n3, methode):
        return None
    cle, cle_reserve = _METHODES[methode][0], _METHODES[methode][1]
    valeur = (n3.get(cle) or {}).get(cle_reserve)
    return None if valeur is None else float(valeur)
