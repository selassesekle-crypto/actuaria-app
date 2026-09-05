# -*- coding: utf-8 -*-
"""
ActuarIA — Tarification · LE CONTRAT DE SORTIE D'UN AGENT
=========================================================

À quoi il sert : rendre inutile le ``.get(clé, littéral)``. C'est le même
défaut que le lot précédent, pris à sa racine — un lecteur ne pose un
littéral que parce qu'il n'a AUCUNE garantie que la clé sera là.

⚠️⚠️ LE CONTRAT NE SE DÉCLARE PAS, IL SE DÉRIVE : **un agent rend TOUJOURS
LES MÊMES CLÉS, en échec comme en succès.** Aucune liste tenue à la main ne
peut donc diverger — le contrôle compare l'agent à lui-même, sur deux
exécutions réelles.

  *Mesuré le 05/09/2026 : `A1.run` a QUATRE sorties. Une complète, à seize
  clés, et trois chemins d'échec à huit — il y manque `qualite`, `rapport`,
  `hash_md5`, `client_id`, `audit_trail` et les trois clés de livrable. Les
  lecteurs de ces clés (`tarif_excel`, `rapport_equipe_tarif`) reçoivent
  donc leur littéral dès qu'A1 échoue, sans qu'aucun d'eux le sache.*

⚠️ CE MODULE VIT DANS LA TARIFICATION, PAS DANS `core`. Le contrat est celui
d'une direction, et il fait partie de ce qui se vend avec elle : le placer
dans `core` créerait une dépendance de plus à défaire le jour de la licence.
`core/base_agent.py` porte un `RETOUR_VIDE` voisin — quinze clés dont
``triangle``, une notion de PROVISIONNEMENT — et **zéro héritier dans tout le
dépôt, mesuré par AST**. Ce n'est donc pas une source à réutiliser : c'est un
contrat que personne n'a jamais signé.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

#: Ce qu'un agent rend quand il n'a rien produit. ⚠️ Ce ne sont PAS des
#: valeurs par défaut au sens du lot précédent : ce sont les formes VIDES
#: d'objets qui n'existent pas encore — un classeur non produit pèse zéro
#: octet, ce n'est pas une mesure fabriquée. La distinction tient à ceci :
#: `b''` se lit « aucun document », alors que `0` se lisait « mesure nulle ».
FORMES_VIDES: dict[str, Any] = {
    'excel_bytes': b'',
    'word_bytes': b'',
    'pdf_bytes': b'',
    'audit_trail': {},
    'graphiques': {},
    'commentaire': '',
}


def sortie_completee(gabarit: dict[str, Any],
                     **valeurs: Any) -> dict[str, Any]:
    """Une sortie qui porte TOUTES les clés de ``gabarit``.

    ``gabarit`` est le jeu de clés que l'agent rend sur son chemin complet,
    avec leurs formes vides. Les ``valeurs`` fournies l'emportent.

    ⚠️ Une clé fournie qui n'est PAS au gabarit lève : c'est le seul moyen
    que le gabarit reste la référence. Sans cela, un chemin d'échec pourrait
    publier une clé de plus que le chemin normal — et le contrôle « mêmes
    clés partout » serait rouge sans que personne comprenne pourquoi.
    """
    inconnues = sorted(set(valeurs) - set(gabarit))
    if inconnues:
        raise KeyError(
            f"clé(s) hors gabarit de sortie : {inconnues}. Le gabarit porte "
            f"{sorted(gabarit)}. Ajoutez-la au gabarit si elle appartient "
            f"vraiment au contrat de cet agent.")
    # ⚠️⚠️ COPIE PROFONDE, ET CE N'EST PAS UNE PRÉCAUTION. `{**gabarit, ...}`
    # est une copie DE SURFACE : les `{}` du gabarit seraient LE MÊME objet
    # dans toutes les sorties **et dans le gabarit de module**. Un lecteur qui
    # écrit une seule fois dans `qualite` contaminerait alors tous les appels
    # suivants du processus — y compris ceux d'un autre portefeuille.
    # Trouvé par la sentinelle CS-2b, pas par la relecture.
    return {**deepcopy(gabarit), **valeurs}
