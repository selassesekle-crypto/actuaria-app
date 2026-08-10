# -*- coding: utf-8 -*-
"""C5a — le fait mesuré : le logiciel comporte une assistance IA qui sort.

⚠️ CE MODULE NE QUALIFIE RIEN EN DROIT, ET C'EST DÉLIBÉRÉ. Un registre des
activités de traitement (art. 30 RGPD) est un document que le responsable de
traitement produit ; sa finalité, sa base légale, sa durée de conservation et
la qualification d'un transfert relèvent de lui et de son DPO. Ce que le code
peut faire honnêtement, c'est rendre CE QU'IL FAIT — mesuré, à une source
unique — pour que personne n'ait à l'inventer.

⚠️ POURQUOI IL EXISTE. Les deux registres du dépôt (A13 en Non-Vie, SP audit
en Santé-Prévoyance) nomment leurs destinataires — actuaires, commissaire aux
comptes, ACPR — et n'ont jamais nommé le fournisseur du service d'assistance
IA, alors que les agents qu'ils documentent (A1 à A12) comptent les trois qui
l'appellent. Le registre décrivait donc des exécutions pendant lesquelles des
données sortaient, sans le dire.

⚠️ CE QUE LA MESURE A ÉTABLI, ET QUI TEMPÈRE LE CONSTAT. Après C1, C2 et C3,
ce qui sort n'est PAS constitué de données personnelles : des agrégats de
portefeuille (un Best Estimate, un sigma, un Gini), des noms de colonnes, et
la FORME des valeurs — jamais les valeurs. Les deux réserves ci-dessous sont
donc les seules qui subsistent, et elles sont nommées plutôt que tues.
"""
from typing import Any

from core import frontiere_llm

#: Ce qui sort réellement, relevé canal par canal aux treize sites (C1),
#: après le caviardage de C2 et l'anonymisation de C3.
CATEGORIES_TRANSMISES = (
    ('Agrégats de portefeuille (Best Estimate, sigma, SCR, Gini, '
     'effectifs) — aucune valeur individuelle'),
    ('Structure des fichiers : noms de colonnes et FORME des valeurs '
     '(cf. core.apercu_caviarde) — jamais les valeurs'),
    ("Contexte de l'arrêté : date d'arrêté, branche, type de contrat"),
    ("Texte libre saisi par l'utilisateur dans l'assistant conversationnel"),
)

#: ⚠️ LES DEUX SEULES RÉSERVES MESURÉES. Les taire rendrait le reste suspect.
RESERVES = (
    ("En-tête décalé : lorsque la ligne d'en-tête d'un fichier client est "
     'décalée, les « noms de colonnes » sont en réalité des valeurs et '
     'sortent telles quelles. Cas mesuré en C2, rare, et celui où '
     "l'assistance IA n'apporte rien — le lecteur déterministe le résout."),
    ('Assistant conversationnel : rien dans le code ne contraint le texte '
     "que l'utilisateur saisit. Le contenu de ce canal dépend de lui."),
)

#: La phrase qui marque la frontière entre ce que le code sait et ce qu'il
#: n'a pas à trancher. ⚠️ Elle n'est pas décorative : sans elle, un lecteur
#: prendrait le bloc factuel pour une qualification juridique.
QUALIFICATION = (
    'À DÉTERMINER PAR LE RESPONSABLE DE TRAITEMENT ET SON DPO. Ce bloc est '
    'un constat technique produit par le logiciel, non une qualification '
    "juridique : ni la nature du transfert, ni la base légale, ni la durée "
    "de conservation applicables au service tiers n'y sont établies."
)


def constat_assistance_ia() -> dict[str, Any]:
    """Le constat technique, prêt à être porté par un registre art. 30.

    ⚠️ Les chiffres viennent de `core.frontiere_llm`, seule source du dépôt
    qui connaisse les sites sortants — jamais d'une liste recopiée ici. Un
    site ajouté demain se compte tout seul.
    """
    chemins = frontiere_llm.chemins_appelants()
    return {
        'fournisseur': frontiere_llm.FOURNISSEUR,
        'service': frontiere_llm.SERVICE,
        'nb_sites_appelants': len(chemins),
        'modeles_appeles': list(frontiere_llm.MODELES_CONNUS),
        'categories_transmises': list(CATEGORIES_TRANSMISES),
        # ⚠️ PAS DE BOOLÉEN « données personnelles : oui/non » ICI. J'en avais
        # écrit un — c'eût été le défaut même que ce lot corrige. Un booléen
        # aplatit la seule nuance qui compte : trois canaux sur quatre sont
        # clos par construction, le quatrième dépend de ce que l'utilisateur
        # saisit. Les catégories et les réserves le disent exactement.
        'reserves': list(RESERVES),
        'qualification_juridique': QUALIFICATION,
    }
