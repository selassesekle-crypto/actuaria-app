# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : L'ERRATA DES DONNÉES LIVRÉES
=============================================================================

⚠️ POURQUOI CET ERRATA VIT DANS LE DÉPÔT ET PAS DANS UN COURRIEL. Trois
défauts des données livrées ont été trouvés, confirmés par leur producteur,
et deux d'entre eux CHANGENT UN COMPTAGE. Un errata rangé hors du code se
perd exactement quand il servirait : le jour où quelqu'un reprendra
`classe_profitabilite` comme référence du test §47 sans savoir qu'elle est
désavouée. Il est donc ici, structuré, et la gate le lit.

⚠️ ET IL EST OPÉRANT, PAS DÉCORATIF. `refuser_source_test_47()` fait mordre
E1 : la colonne désavouée est refusée par le code, pas seulement déconseillée
par une note. Un errata qui ne peut rien refuser n'est qu'une prose.

⚠️⚠️ LES TROIS PANIERS DU §47 N'ONT PAS LA MÊME SOLIDITÉ, ET LES CONFONDRE
SERAIT LA FAUTE. §47 définit le contrat déficitaire par « la somme des FLUX
DE TRÉSORERIE D'EXÉCUTION affectés au contrat, des flux […] liés aux frais
d'acquisition […] et des flux découlant du contrat ». §32 a) décompose les
flux d'exécution en TROIS : i) l'estimation des flux futurs, ii) un
ajustement pour la valeur temps de l'argent, iii) UN AJUSTEMENT AU TITRE DU
RISQUE NON FINANCIER. L'ajustement pour risque est donc bien dans le panier,
et le comptage à 747 est fondé EN DROIT.

  · 249 — le panier LIVRÉ. Incomplet des deux composantes. À ne pas employer.
  · 552 — panier + frais de gestion des sinistres. ⚠️ NE DÉPEND D'AUCUNE
    DÉCLARATION : les taux employés sont des paramètres de portefeuille, et
    l'avertissement du fichier ne vise qu'`taux_ra_declare`. Vérifié.
  · 747 — panier complet du §47. ⚠️ HÉRITE DU STATUT `A_REMPLACER` de la
    déclaration d'ajustement pour risque qui l'alimente. Il n'est pas plus
    solide que cette déclaration.

⚠️ ET LE 747 N'EST PAS CONSOMMABLE PAR CE DÉPÔT, ce qui se vérifie plutôt
que se promettre : `mesure.declaration.est_renseigne('A_REMPLACER')` rend
False. Le module bâti pour ce défaut refuse exactement ce chiffre-là.

⚠️ CE QUE L'ERRATA NE COUVRE PAS, ET QUI RESTE OUVERT. Aucun des trois
paniers ne porte de terme d'ACTUALISATION, que §32 a) ii) range pourtant
dans les flux d'exécution au même rang que l'ajustement pour risque. Ce
module ne tranche pas : il ne peut pas savoir, depuis les colonnes livrées,
si `sinistres_attendus` est déjà une valeur actuelle. C'est une QUESTION au
producteur, pas un quatrième défaut établi — et la nommer vaut mieux que la
laisser découvrir.

⚠️ ET SOUS PAA, LE TEST N'EST PAS LE §47 MAIS LE §18 : « l'entité doit
SUPPOSER qu'aucun des contrats du portefeuille n'est déficitaire […] À MOINS
QUE les faits et les circonstances n'indiquent le contraire. » Un panier en
sortie nette est un tel fait. Les comptages restent donc opérants, mais leur
STATUT diffère selon le modèle d'évaluation : verdict en modèle général,
renversement d'une présomption en PAA.

SOURCE — errata transmis par le producteur des données, confirmé point par
point par mesure indépendante sur les 2 000 contrats livrés.
=============================================================================
"""

from typing import NamedTuple

#: La colonne que E1 désavoue comme référence du test §47.
COLONNE_DESAVOUEE_TEST_47 = 'classe_profitabilite'

#: Les trois paniers, et ce dont chacun dépend.
PANIER_LIVRE = 'PANIER_LIVRE'
PANIER_AVEC_FRAIS_GESTION = 'PANIER_AVEC_FRAIS_GESTION'
PANIER_COMPLET_47 = 'PANIER_COMPLET_47'

#: ⚠️ Le comptage de chaque panier, MESURÉ ICI, pas repris du producteur.
COMPTAGE_DEFICITAIRES = {
    PANIER_LIVRE: 249,
    PANIER_AVEC_FRAIS_GESTION: 552,
    PANIER_COMPLET_47: 747,
}

#: ⚠️ CE PANIER DESCEND D'UNE DÉCLARATION NON SIGNÉE. Le nommer ici évite
#: qu'un agrégat le cite au même rang que les deux autres.
PANIERS_TRIBUTAIRES_D_UNE_DECLARATION = frozenset({PANIER_COMPLET_47})


class Erratum(NamedTuple):
    """Un défaut de donnée confirmé, avec sa nature, son poids et sa suite."""
    ref:         str
    objet:       str
    nature:      str
    description: str
    impact:      str
    action:      str


ERRATA = (
    Erratum(
        'E1', 'contrats_ifrs17_v2.csv / classe_profitabilite',
        'DEFAUT_CONFIRME',
        "Le panier du test §16/§47 omet DEUX composantes des flux "
        "d'exécution : les frais de gestion des sinistres, ET l'ajustement "
        "au titre du risque non financier que §32 a) iii) y range.",
        "249 déficitaires livrés, 552 avec les frais de gestion, 747 avec "
        "l'ajustement pour risque — un facteur 3 en comptes. En euros, la "
        "perte portée passe de 33 092 à 77 791 puis 115 010, et la marge du "
        "portefeuille de 18,06 % à 10,18 % puis 4,65 % des primes.",
        "Ne PAS employer `classe_profitabilite` comme référence du test "
        "§47 : `refuser_source_test_47()` le refuse. Employer le panier 552 "
        "sans réserve, le 747 sous la réserve de sa déclaration."),
    Erratum(
        'E2', 'panel de génération / part récupérable GAV',
        'ERREUR_DE_PARAMETRE',
        "Part récupérable 0,18 inférieure au taux de quote-part 0,40. ⚠️ "
        "L'incohérence est ARITHMÉTIQUE, pas statistique : une quote-part de "
        "40 % garantit à elle seule 40 % de récupération AVANT tout effet "
        "d'excédent de sinistre, et les cinq autres portefeuilles le "
        "vérifient — leur part récupérable excède leur quote-part, l'écart "
        "mesurant l'apport de l'excédent.",
        "Immatériel : 6,89 € sur 8 460 € de recouvrement, soit 0,08 %, pour "
        "un impact de 8,39 €. Ne justifie pas une régénération.",
        "Valeur corrigée à appliquer à la prochaine génération. Aucun "
        "retraitement des données actuelles."),
    Erratum(
        'E3', 'composante_recouvrement_pertes.csv / avertissement',
        'FORMULATION_INEXACTE',
        "La note affirme le plafond B119F « respecté PAR CONSTRUCTION ». Un "
        "contrôle strict `composante <= perte × part` échoue sur 129 des "
        "235 lignes.",
        "Dépassement maximal 0,005 €, total 0,3242 €, soit 0,0038 % du "
        "recouvrement. Cause unique : l'arrondi au centime des deux "
        "opérandes, et zéro ligne au-delà de cette borne.",
        "Formulation exacte : « respecté À L'ARRONDI DU CENTIME PRÈS ». "
        "`mesure.recouvrement_perte.verifier_plafond_b119f` porte la borne "
        "démontrable de n × 0,005 €."),
)


class SourceDesavouee(Exception):
    """⚠️ Un refus, pas un avertissement. Une source désavouée qui ne fait
    que prévenir sera employée quand même — c'est le propre des notes."""


def refuser_source_test_47(colonne: str) -> None:
    """E1, rendu opérant — la colonne désavouée est REFUSÉE.

    ⚠️ C'EST CE QUI SÉPARE UN ERRATA D'UNE PROSE. Le défaut est connu,
    confirmé et mesuré ; le laisser à l'état de note reviendrait à parier
    que le prochain lecteur l'aura lue.
    """
    if colonne == COLONNE_DESAVOUEE_TEST_47:
        raise SourceDesavouee(
            f"« {COLONNE_DESAVOUEE_TEST_47} » est DÉSAVOUÉE comme référence "
            f"du test §16/§47 (erratum E1, confirmé par le producteur des "
            f"données et vérifié ici sur les 2 000 contrats). Son panier "
            f"omet les frais de gestion des sinistres ET l'ajustement au "
            f"titre du risque non financier, que §32 a) iii) range dans les "
            f"flux d'exécution : elle compte 249 contrats déficitaires là où "
            f"le panier complet du §47 en compte 747.")


def reserve_du_panier(panier: str) -> str:
    """Ce qu'il faut dire en citant un comptage — vide s'il n'y a rien à dire.

    ⚠️ LA RÉSERVE DESCEND AVEC LE CHIFFRE, sinon elle ne descend pas. Un
    comptage cité sans sa réserve devient un fait, et le 747 n'en est pas
    un tant que sa déclaration n'est pas signée.
    """
    if panier not in COMPTAGE_DEFICITAIRES:
        raise SourceDesavouee(
            f"panier inconnu : {panier!r}. Les paniers connus sont "
            f"{sorted(COMPTAGE_DEFICITAIRES)}, et en inventer un laisserait "
            f"citer un comptage sans réserve attachée")
    if panier in PANIERS_TRIBUTAIRES_D_UNE_DECLARATION:
        return (
            "⚠️ CE COMPTAGE HÉRITE D'UNE DÉCLARATION NON SIGNÉE. Il descend "
            "de l'ajustement pour risque déclaré en statut A_REMPLACER : il "
            "n'est pas plus solide que cette déclaration, et "
            "`mesure.declaration.est_renseigne` la refuse. Le fondement EN "
            "DROIT est acquis — §32 a) iii) range l'ajustement pour risque "
            "dans les flux d'exécution — mais la VALEUR ne l'est pas.")
    return ''
