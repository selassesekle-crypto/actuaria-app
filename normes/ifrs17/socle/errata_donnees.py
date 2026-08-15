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

⚠️⚠️ LE QUATRIÈME TERME EST ÉTABLI DEPUIS, ET IL PENCHE DANS L'AUTRE SENS.
La question posée ici — « `sinistres_attendus` est-il déjà une valeur
actuelle ? » — a reçu sa réponse : NON, au code source du générateur. §32 a)
ii) range l'ajustement pour la valeur temps de l'argent dans les flux
d'exécution, au même rang que l'ajustement pour risque, et AUCUN des trois
premiers paniers ne le porte. D'où le quatrième.

⚠️ ET C'EST CE QUI REND LES QUATRE TERMES NÉCESSAIRES PLUTÔT QU'UN SOLDE.
Les deux premières omissions rendaient le test TROP INDULGENT (249 → 552 →
747) ; l'actualisation le rend TROP SÉVÈRE (747 → 539 à 4 %). Elles NE SE
COMPENSENT PAS : il faudrait un taux sans risque d'environ 11 % pour que le
panier complet retombe à 249. Un solde net cacherait deux erreurs de sens
contraire sous un chiffre presque juste — le motif de ce dépôt, appliqué à
un comptage.

⚠️⚠️ ET LA CONVENTION D'ACTUALISATION EST ELLE-MÊME UNE DÉCISION. Ce n'est
pas seulement la COURBE qui se déclare (§36 b) : c'est aussi CE QU'ON
ACTUALISE. Mesuré à 4 % sur le portefeuille livré, quatre conventions
également défendables donnent 521, 539, 541 et 568 — 47 contrats d'écart
pour un effet de 208, soit 23 % de l'effet qu'elles mesurent. Un comptage
actualisé cité sans sa convention laisse croire à une grandeur objective là
où il y a DEUX décisions superposées.

⚠️⚠️ CE QUE L'ERRATA NE COUVRE PAS, ET UNE AFFIRMATION D'ICI QUI ÉTAIT FAUSSE.
Ce module a d'abord écrit que « l'ajustement pour risque de crédit de 10 bps
doit être RETRAITÉ, car c'est une construction réglementaire ». C'EST FAUX,
ET DANS LE SENS INVERSE. Le CRA RETIRE de la courbe swap le risque de crédit
bancaire résiduel ; il la rapproche du sans-risque au lieu de l'en éloigner.
Or §36 c) impose précisément d'« EXCLURE L'EFFET DES FACTEURS QUI INFLUENT
SUR CES PRIX DE MARCHÉ OBSERVABLES, MAIS PAS SUR LES FLUX DE TRÉSORERIE » des
contrats — et le risque de crédit d'une banque en est un. Le retraitement du
CRA est donc EXIGÉ PAR §36 c), non à défaire : le défaire remettrait ce
risque dans la courbe.

⚠️⚠️ CE QUI MANQUE RÉELLEMENT EST LA PRIME D'ILLIQUIDITÉ, ET ELLE EST D'UN
AUTRE ORDRE. §36 a) exige de refléter « les CARACTÉRISTIQUES DE LIQUIDITÉ des
contrats d'assurance », et B80 décrit l'approche ascendante : ajuster une
courbe sans risque LIQUIDE « pour tenir compte des différences entre les
caractéristiques de liquidité des instruments financiers sous-jacents aux
taux observés sur le marché et celles des contrats d'assurance ». La courbe
EIOPA sans VA ne porte AUCUN ajustement de ce type — le VA est la
transposition Solvabilité II de cette idée, et le code l'écarte déjà pour une
raison qui lui est propre (l'agrément de l'art. 77 quinquies). ⚠️ Le taux
§36 se compose donc de DEUX termes, et un seul est disponible.

⚠️ ET SON SENS PROLONGE CELUI DE L'ACTUALISATION : une prime d'illiquidité
AUGMENTE le taux, donc réduit encore la valeur actuelle des sorties, donc
réduit le comptage AU-DELÀ des 539 mesurés à 4 %. Elle ne compense rien, elle
accentue.

⚠️ LA MESURE SUR LE LAST LIQUID POINT RESTE VRAIE, mais elle prouve autre
chose que ce qui lui était attribué : la durée de règlement la plus longue du
portefeuille est 4,76 ans (DO), très en deçà du LLP de 20 ans, donc
l'EXTRAPOLATION vers l'UFR n'est pas atteinte. Ni le CRA ni l'extrapolation
ne sont donc en cause — reste la seule prime d'illiquidité.

⚠️ ET AUCUN TAUX N'EST POSÉ ICI. La note « Courbe des taux sans risque sous
IFRS 17 » de l'Institut des Actuaires (juillet 2022) donne des allocations
indicatives par nature de passif, mais une indication de place n'est pas une
règle : la prime d'illiquidité SE DÉCLARE, avec sa technique. Son §5 nomme
d'ailleurs comme premier écueil à documenter le fait qu'un taux ne reflète
pas à la fois le sans-risque ET la prime d'illiquidité.

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

#: ⚠️ LE QUATRIÈME PANIER — CELUI QUI N'A PAS DE COMPTAGE. §32 a) ii) range
#: l'ajustement pour la VALEUR TEMPS DE L'ARGENT dans les flux d'exécution, au
#: même rang que l'ajustement pour risque. Aucun des trois autres ne le porte.
PANIER_COMPLET_47_ACTUALISE = 'PANIER_COMPLET_47_ACTUALISE'

#: ⚠️ QUATRE PANIERS, TROIS COMPTAGES. Le quatrième n'a pas de nombre tant
#: que sa courbe ET sa convention ne sont pas déclarées : le ranger ici sans
#: comptage, plutôt que de lui en inventer un, est tout le sujet.
PANIERS = (PANIER_LIVRE, PANIER_AVEC_FRAIS_GESTION, PANIER_COMPLET_47,
           PANIER_COMPLET_47_ACTUALISE)
PANIERS_SANS_COMPTAGE_ETABLI = frozenset({PANIER_COMPLET_47_ACTUALISE})

#: ⚠️ CE PANIER DESCEND D'UNE DÉCLARATION NON SIGNÉE. Le nommer ici évite
#: qu'un agrégat le cite au même rang que les autres.
PANIERS_TRIBUTAIRES_D_UNE_DECLARATION = frozenset({PANIER_COMPLET_47,
                                                   PANIER_COMPLET_47_ACTUALISE})

#: ⚠️⚠️ CE QUE L'ACTUALISATION FAIT AU COMPTAGE — MESURÉ, ET DANS L'AUTRE SENS.
#: Les deux premières omissions rendaient le test TROP INDULGENT (249 → 747) ;
#: celle-ci le rend TROP SÉVÈRE. ⚠️ ELLES NE SE COMPENSENT PAS : il faudrait un
#: taux sans risque d'environ 11 % pour que le panier complet retombe à 249.
#: Mesuré sur les 2 000 contrats livrés, sous la convention nommée ci-dessous.
SENSIBILITE_ACTUALISATION = {0.00: 747, 0.01: 690, 0.02: 640,
                             0.03: 587, 0.04: 539}

#: ⚠️⚠️ LA CONVENTION D'ACTUALISATION EST ELLE-MÊME UNE DÉCISION, ET PAS UNE
#: PETITE. Ce n'est pas seulement la COURBE qui se déclare (§36 b), c'est aussi
#: CE QU'ON ACTUALISE. Mesuré à 4 % sur le portefeuille livré :
#:
#:   · durée moyenne, sinistres + frais de gestion + ajustement risque : 539
#:   · cadence complète au lieu de la durée moyenne                    : 541
#:   · sinistres seuls actualisés                                      : 568
#:   · frais de maintenance actualisés aussi                           : 521
#:
#: Soit 47 contrats d'écart entre conventions, pour un effet d'actualisation
#: de 208 contrats : LA CONVENTION PÈSE 23 % DE L'EFFET QU'ELLE MESURE. Citer
#: un comptage actualisé sans nommer sa convention laisse croire à une
#: grandeur objective là où il y a deux décisions superposées.
CONVENTION_DES_SENSIBILITES = (
    "durée moyenne de règlement par portefeuille appliquée aux sinistres "
    "attendus, frais de gestion des sinistres et ajustement pour risque ; "
    "frais d'acquisition et de maintenance laissés en nominal")
ECART_ENTRE_CONVENTIONS_A_4PCT = 47
EFFET_ACTUALISATION_A_4PCT = 208

#: ⚠️⚠️ TROIS DÉCLARATIONS, ET ELLES SE SÉPARENT — c'est le tout de la leçon
#: du CRA. Fondre la prime d'illiquidité dans « la courbe » la rendrait
#: invisible, et un terme absorbé dans un mot global ne se rouvre pas : il
#: a fallu une source externe pour voir qu'une exigence posée ici sur le CRA
#: était à l'envers. Ce qui est nommé séparément se relit séparément.
DECLARATION_COURBE = 'COURBE_SANS_RISQUE'
DECLARATION_PRIME_ILLIQUIDITE = 'PRIME_ILLIQUIDITE'
DECLARATION_CONVENTION = 'CONVENTION_ACTUALISATION'
DECLARATIONS_DU_TAUX_36 = (DECLARATION_COURBE, DECLARATION_PRIME_ILLIQUIDITE,
                           DECLARATION_CONVENTION)

#: ⚠️ LE PREMIER ÉCUEIL À DOCUMENTER, ET C'EST EXACTEMENT NOTRE SITUATION.
#: La note « Courbe des taux sans risque sous IFRS 17 » de l'Institut des
#: Actuaires (juillet 2022, §5, bonnes pratiques et gouvernance) place en
#: tête des écueils à éviter ET À DOCUMENTER le cas d'un taux d'actualisation
#: qui ne reflète pas à la fois le taux sans risque ET la prime
#: d'illiquidité. L'avoir écrit vaut mieux que le découvrir.
ECUEIL_TAUX_INCOMPLET = (
    "⚠️ ÉCUEIL NOMMÉ, ET C'EST LE PREMIER DE LA LISTE : un taux "
    "d'actualisation qui ne reflète pas À LA FOIS le taux sans risque ET la "
    "prime d'illiquidité. §36 a) exige les « caractéristiques de liquidité "
    "des contrats d'assurance » et B80 décrit l'ajustement correspondant ; "
    "une courbe sans risque seule ne les porte pas. C'est la situation de ce "
    "dépôt, et elle est écrite plutôt que laissée à découvrir.")


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
        'E4', 'contrats_ifrs17_v2.csv / sinistres_attendus',
        'DEFAUT_CONFIRME',
        "Les sinistres attendus sont NOMINAUX — confirmé au code source du "
        "générateur : prime × ratio S/P, aucun facteur d'actualisation. §32 "
        "a) ii) range pourtant l'ajustement pour la valeur temps de l'argent "
        "dans les flux d'exécution, au même rang que l'ajustement pour "
        "risque. Aucun des trois premiers paniers ne le porte.",
        "⚠️ SENS INVERSE DES DEUX AUTRES OMISSIONS : l'actualisation RÉDUIT "
        "le comptage. 747 à taux nul, 690 à 1 %, 640 à 2 %, 587 à 3 %, 539 à "
        "4 %. Elles NE SE COMPENSENT PAS — il faudrait environ 11 % pour "
        "retomber aux 249 du panier livré. ⚠️ Et la CONVENTION pèse 47 "
        "contrats à 4 % pour un effet de 208, soit 23 % de l'effet mesuré.",
        "Employer `PANIER_COMPLET_47_ACTUALISE` dès que la courbe du §36 b) "
        "ET la convention d'actualisation sont déclarées. Jusque-là, le "
        "panier 552 reste le meilleur disponible et porte sa réserve : ne pas "
        "bloquer le §62 b), qui supprimerait une date que la norme exige."),
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
    if panier not in PANIERS:
        raise SourceDesavouee(
            f"panier inconnu : {panier!r}. Les paniers connus sont "
            f"{sorted(PANIERS)}, et en inventer un laisserait citer un "
            f"comptage sans réserve attachée")

    #: ⚠️ « PANIER CONNU SANS COMPTAGE ÉTABLI » N'EST PAS « PANIER INCONNU ».
    #: Les confondre laisserait croire que le quatrième panier n'existe pas,
    #: alors qu'il est le seul complet au sens du §47.
    if panier in PANIERS_SANS_COMPTAGE_ETABLI:
        return (
            f"⚠️ CE PANIER EST LE SEUL COMPLET AU SENS DU §47, ET IL N'A PAS "
            f"DE COMPTAGE. Il exige une COURBE déclarée (§36 b confie à "
            f"l'entité « celle qui concorde avec les prix de marché "
            f"observables ») ET une CONVENTION déclarée — ce qu'on actualise "
            f"n'est pas moins une décision que le taux auquel on actualise. "
            f"Mesuré : à 4 %, la convention seule déplace "
            f"{ECART_ENTRE_CONVENTIONS_A_4PCT} contrats pour un effet de "
            f"{EFFET_ACTUALISATION_A_4PCT}, soit "
            f"{ECART_ENTRE_CONVENTIONS_A_4PCT / EFFET_ACTUALISATION_A_4PCT:.0%} "
            f"de l'effet qu'elle mesure. Sensibilité indicative sous la "
            f"convention « {CONVENTION_DES_SENSIBILITES} » : "
            + ', '.join(f'{t:.0%} → {n}'
                        for t, n in sorted(SENSIBILITE_ACTUALISATION.items()))
            + ".")

    if panier == PANIER_AVEC_FRAIS_GESTION:
        return (
            "⚠️ CE COMPTAGE N'EST PAS ACTUALISÉ, ET L'OMISSION PENCHE DANS "
            "L'AUTRE SENS QUE LES DEUX PRÉCÉDENTES. §32 a) ii) range "
            "l'ajustement pour la valeur temps de l'argent dans les flux "
            "d'exécution, au même rang que l'ajustement pour risque ; ce "
            "panier ne le porte pas. L'actualisation RÉDUIT la valeur "
            "actuelle des sorties, donc RÉDUIT le nombre de déficitaires : ce "
            "comptage les SURESTIME. ⚠️ Les omissions NE SE COMPENSENT PAS — "
            "il faudrait un taux sans risque d'environ 11 % pour que le "
            "panier complet retombe aux 249 du panier livré. Ce panier reste "
            "le meilleur disponible, et c'est à ce titre qu'il est employé.")

    if panier in PANIERS_TRIBUTAIRES_D_UNE_DECLARATION:
        return (
            "⚠️ CE COMPTAGE HÉRITE D'UNE DÉCLARATION NON SIGNÉE. Il descend "
            "de l'ajustement pour risque déclaré en statut A_REMPLACER : il "
            "n'est pas plus solide que cette déclaration, et "
            "`mesure.declaration.est_renseigne` la refuse. Le fondement EN "
            "DROIT est acquis — §32 a) iii) range l'ajustement pour risque "
            "dans les flux d'exécution — mais la VALEUR ne l'est pas. ⚠️ ET "
            "IL N'EST PAS ACTUALISÉ NON PLUS : le §32 a) ii) reste omis, ce "
            "que seul le panier complet actualisé corrige.")
    return ''
