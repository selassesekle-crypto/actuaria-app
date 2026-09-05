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

from collections.abc import Mapping
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


#: Ce que la tarification NE PRODUIT PAS, et POURQUOI.
#: ⚠️⚠️ CES TROIS GRANDEURS SONT LUES PAR LA RÉGLEMENTATION, ET FABRIQUÉES.
#: Mesuré le 05/09/2026 : `a8_stress_testing` fait
#: ``result_a6.get('loss_ratio_attendu', 0.72)`` — une clé qu'A6 ne publie
#: JAMAIS, donc le 0,72 se pose à chaque run, et `a8:1084` s'en sert pour
#: décider s'il faut « resserrer les critères de souscription ».
#:
#:   *Déclarer ce qu'on ne produit pas vaut mieux que laisser un
#:   consommateur l'inventer.*
NON_PRODUIT_PAR_LA_TARIFICATION: dict[str, str] = {
    'primes_acquises':
        "La prime ACQUISE est une grandeur comptable : elle vient du système "
        "de gestion des contrats, pas d'un modèle de tarification. La "
        "tarification produit une prime PURE (espérance de charge), pas une "
        "prime encaissée.",
    'loss_ratio_attendu':
        "Le ratio S/P attendu rapporte une charge à une prime COMMERCIALE, "
        "laquelle dépend des chargements, de la politique commerciale et des "
        "remises accordées — aucune de ces trois n'est une sortie de la "
        "tarification technique.",
    'primes_emises':
        "Comme la prime acquise : une grandeur du système de gestion.",
}


def publication_reglementaire(result_a6: Mapping[str, Any] | None,
                              result_a3: Mapping[str, Any] | None = None,
                              plan: Any = None) -> dict[str, Any]:
    """Ce que la tarification publie à l'usage de la réglementation.

    ⚠️⚠️ ELLE PUBLIE, ELLE NE CÂBLE PAS. La publication vit sous SA PROPRE
    CLÉ (`publication_reglementaire`), jamais au premier niveau du résultat
    d'A6 — et c'est délibéré. `a8_stress_testing` lit
    ``result_a6.get('gini', 0.25)`` et ``.get('modele_retenu', 'N/A')`` :
    publier `gini` et `modele_retenu` EN HAUT ferait trouver ces clés et
    câblerait A8 par la bande. **Mesuré : le câblage de la frontière déplace
    +36,2 % de SCR, soit 1 435 571 EUR.** Cette décision n'est pas prise ;
    la porte s'ouvre, on ne la franchit pas.

    ⚠️ CHAQUE VALEUR PORTE SA PROVENANCE. Un chiffre réglementaire sans
    l'endroit d'où il vient n'est pas contestable — c'est la même exigence
    que la `source` d'un seuil de sinistre grave.

    ⚠️ ET ELLE PUBLIE CE QU'ELLE POSSÈDE, PAS CE QU'ON LUI DEMANDE. Une
    grandeur qu'A6 n'a pas est déclarée absente AVEC SON MOTIF, jamais
    remplie d'un repli.
    """
    result_a6 = result_a6 or {}
    production = result_a6.get('modele_production') or {}
    metriques_a3 = (result_a3 or {}).get('metriques') or {}
    tweedie = metriques_a3.get('tweedie') if isinstance(metriques_a3, dict) else None

    def _entree(valeur, provenance):
        return {'valeur': valeur, 'provenance': provenance}

    possede = {
        'modele_retenu': _entree(production.get('modele'),
                                 'A6.modele_production.modele'),
        'gini_test': _entree(production.get('gini_test'),
                             'A6.modele_production.gini_test'),
        'score_global': _entree(production.get('score_global'),
                                'A6.modele_production.score_global'),
        'cible': _entree(production.get('cible'),
                         'A6.modele_production.cible'),
        'statut_rag': _entree(result_a6.get('statut_rag'), 'A6.statut_rag'),
        'branche': _entree(result_a6.get('branche'), 'A6.branche'),
        'audit_id': _entree(result_a6.get('audit_id'), 'A6.audit_id'),
    }
    # ⚠️ L'empreinte du plan SCELLE ce qui a été tarifé : sans elle, un
    # consommateur réglementaire ne peut pas dire SOUS QUEL PLAN le chiffre
    # a été produit. Elle n'est publiée que si le plan est là — jamais
    # reconstruite.
    if plan is not None and hasattr(plan, 'empreinte'):
        possede['empreinte_plan'] = _entree(plan.empreinte(),
                                            'PlanTarifaire.empreinte()')
    # ⚠️ La prime pure moyenne n'existe que si A3 a ajusté un Tweedie : elle
    # se RELAIE, elle ne se recalcule pas ici.
    if isinstance(tweedie, dict) and tweedie.get('prime_pure_moy_pred') is not None:
        possede['prime_pure_moyenne'] = _entree(
            tweedie['prime_pure_moy_pred'],
            'A3.metriques.tweedie.prime_pure_moy_pred')

    return {
        'possede': possede,
        'non_produit': dict(NON_PRODUIT_PAR_LA_TARIFICATION),
        'avertissement': (
            "Cette publication est DESCRIPTIVE : aucun agent de la "
            "reglementation n'y est cable. Un consommateur qui a besoin "
            "d'une grandeur declaree NON PRODUITE doit la tirer de son "
            "propre systeme, jamais d'un repli."
        ),
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
