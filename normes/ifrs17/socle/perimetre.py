# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : LE PÉRIMÈTRE PUBLIÉ, ET SURTOUT CE QU'IL EXCLUT
=============================================================================

CE QU'UN ACTUAIRE QUI SIGNE ET UN COMMISSAIRE QUI LIT REGARDENT EN PREMIER,
c'est ce que la plateforme NE fait pas. Un périmètre écrit et assumé est
défendable ; une liste d'exigences ouvertes ne l'est pas.

⚠️ TROIS ÉTATS, ET NON DEUX. Confondre « hors périmètre » et « pas encore
construit » tromperait dans les deux sens : présenter un chantier en cours
comme une exclusion délibérée, ou laisser croire qu'une exclusion assumée
sera comblée. Chacun porte sa RAISON, et elle est obligatoire.

⚠️ LES ÉLÉMENTS « COUVERT » SONT VÉRIFIÉS CONTRE `contrat.EXIGENCES`. Le
périmètre ne peut pas revendiquer plus que le socle ne nomme : un test
l'interdit. Sans ce verrou, la promesse commerciale dériverait du code —
et c'est le sens même de ce module d'empêcher cela.

⚠️ CE QUE LA PLATEFORME NE VÉRIFIE PAS, ET QUI N'ÉTAIT PAS DANS MA LISTE.
Relevé sur le texte : IFRS 17 porte QUATRE choix obligatoires (§7, §8A, §88,
§89) et SEPT options (§8, §21, §59 a), §69, B6, B115, B137). La plateforme en
tranche plusieurs implicitement, et le plus lourd est en amont de tout :
elle ne teste JAMAIS si ce qu'on lui remet entre dans le champ d'IFRS 17
(§3, §7, §8, §8A, appendice A, B2-B30). Elle prend l'inventaire pour ce
qu'il dit être. C'est défendable — un assureur connaît ses contrats — mais
cela se DÉCLARE, parce qu'un contrôleur le demandera.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023. Chaque paragraphe cité ci-dessous a été relu dans ce texte.
=============================================================================
"""

from collections.abc import Iterable, Mapping
from typing import NamedTuple

#: Le socle le fait, et `contrat.EXIGENCES` le nomme.
COUVERT = 'COUVERT'
#: Décision assumée : la plateforme ne le fera pas, et dit pourquoi.
HORS_PERIMETRE = 'HORS_PERIMETRE'
#: Prévu, pas encore fait. ⚠️ N'est PAS une exclusion.
NON_CONSTRUIT = 'NON_CONSTRUIT'

ETATS = (COUVERT, HORS_PERIMETRE, NON_CONSTRUIT)


class Element(NamedTuple):
    """Un pan de la norme, et ce que la plateforme en fait.

    `raison` est obligatoire hors du cas COUVERT : une exclusion sans motif
    est une omission déguisée.
    """
    reference: str
    etat:      str
    libelle:   str
    raison:    str = ''


PERIMETRE: tuple[Element, ...] = (

    # ── Ce que le socle fait ────────────────────────────────────────────────
    Element('§14, §16, §22, §25', COUVERT,
            "Unité de compte : portefeuilles, classes de profitabilité, "
            "cohortes annuelles, date de comptabilisation initiale. "
            "⚠️ LA CLASSE DE PROFITABILITÉ LIVRÉE EST DÉSAVOUÉE COMME "
            "RÉFÉRENCE DU TEST §16/§47, et le code la REFUSE — voir "
            "`socle.errata_donnees`, erratum E1. Son panier omet deux "
            "composantes des flux d'exécution : les frais de gestion des "
            "sinistres et l'ajustement au titre du risque non financier, que "
            "§32 a) iii) y range. Mesuré sur les 2 000 contrats livrés : "
            "249 déficitaires avec le panier livré, 552 en ajoutant les "
            "frais de gestion, 747 avec l'ajustement pour risque. ⚠️ ET LES "
            "TROIS N'ONT PAS LA MÊME SOLIDITÉ : le 552 ne dépend d'aucune "
            "déclaration, le 747 hérite du statut A_REMPLACER de celle qui "
            "l'alimente — que `mesure.declaration.est_renseigne` refuse."),
    Element('§17', COUVERT,
            "Évaluation d'un ensemble de contrats plutôt que contrat "
            "par contrat"),
    Element('§18', COUVERT,
            "Présomption de non-déficit en PAA, faute de critère déclaré"),
    Element('§53', COUVERT,
            "Test d'éligibilité à la méthode d'affectation des primes"),
    Element('§36 a), B79', COUVERT,
            "Courbe d'actualisation dans la monnaie des flux"),
    Element('§78', COUVERT,
            "Un jeu d'états par entité juridique"),

    # ── Hors périmètre, par décision assumée ────────────────────────────────
    Element('§3, §7, §8, §8A, appendice A, B2-B30', HORS_PERIMETRE,
            "Test du champ d'application : la plateforme ne vérifie pas "
            "qu'un contrat qu'on lui remet EST un contrat d'assurance",
            "Le §7 exclut lui-même garanties de biens, avantages du "
            "personnel et droits d'usage ; le §8A impose de choisir entre "
            "IFRS 17 et IFRS 9 pour certains contrats. Ces qualifications "
            "relèvent de l'entité, qui connaît ses contrats. La plateforme "
            "prend l'inventaire pour ce qu'il déclare être, et le dit."),
    Element('§8, B6', HORS_PERIMETRE,
            "Option d'appliquer IFRS 15 aux contrats de services à tarif "
            "forfaitaire",
            "Choix contractuel de l'entité, exercé en amont de toute "
            "évaluation. Un contrat remis à la plateforme est traité selon "
            "IFRS 17."),
    Element('§32, §38-52', HORS_PERIMETRE,
            "Modèle général (BBA) et marge sur services contractuels",
            "La plateforme mesure en PAA. Un groupe dont la voie automatique "
            "du §53 b) est fermée n'est PAS pour autant renvoyé au modèle "
            "général : la porte §53 a) reste ouverte et relève du jugement "
            "de l'entité (§54). Ces groupes sont SIGNALÉS, jamais mesurés "
            "d'office sous une méthode qui ne leur a pas été choisie."),
    # ⚠️ §33-37 ET B36-B92 NE SONT PAS DANS LA LIGNE CI-DESSUS, ET C'EST
    # MESURÉ. §59 b) écrit que l'entité en PAA « DOIT évaluer le passif au
    # titre des sinistres survenus [...] conformément aux paragraphes 33 à 37
    # et B36 à B92 ». Ils ne sont donc pas exclus par le choix de la PAA : ils
    # lui sont IMPOSÉS. Les laisser dans un « §32-52 hors périmètre » les
    # faisait passer pour écartés quand ils sont dus — l'exacte confusion que
    # ce module existe pour empêcher.
    Element('§33-37, B36-B92', NON_CONSTRUIT,
            "Flux de trésorerie d'exécution : estimation, actualisation, "
            "ajustement au titre du risque",
            "Imposés en PAA par §59 b) pour le passif au titre des sinistres "
            "survenus (LIC). §59 b) dispense d'actualiser lorsque le "
            "règlement est attendu dans l'année suivant le sinistre — c'est "
            "une dispense, pas une exclusion. "
            "ÉTAT : le SQUELETTE est bâti — l'espérance du §33 a) sur "
            "scénarios déclarés, l'actualisation du §36 par courbe déclarée "
            "et signée, l'ajustement du §37 déclaré et signé avec son niveau "
            "de confiance (§119), et la dispense du §59 b) exercée sur "
            "déclaration. ⚠️ CE QUI RESTE : le raccordement à des flux "
            "RÉELS. Aucune donnée de sinistres n'a été remise à ce jour — ni "
            "triangle de liquidation, ni échéancier de règlement — et le "
            "module ne peut donc être alimenté que par des montants saisis. "
            "⚠️ Et il n'est adossé à AUCUNE source externe : ses garanties "
            "sont des invariants internes, pas une concordance publiée. "
            "⚠️⚠️ LES DÉCLARATIONS SIGNÉES SONT CONTRÔLÉES CONTRE LE "
            "REMPLISSAGE FICTIF, et cela n'allait pas de soi : les portes de "
            "signature vérifiaient qu'un champ n'était pas VIDE, si bien "
            "qu'une déclaration d'ajustement pour risque dont le signataire "
            "s'appelait « A_RENSEIGNER » a été ACCEPTÉE. « Non vide » n'est "
            "pas « renseigné ». Les cinq portes du chantier refusent "
            "désormais aussi `A_RENSEIGNER`, `TBD`, `N/A`, `TODO` et leurs "
            "variantes — contrôle calibré sur 21 valeurs légitimes et 21 "
            "formes fictives, zéro rejet à tort."),
    Element('§45, §71, B101-B118', HORS_PERIMETRE,
            "Contrats avec éléments de participation directe (VFA) et "
            "contrats d'investissement avec participation discrétionnaire",
            "Le §71 pose qu'un contrat d'investissement avec participation "
            "discrétionnaire « n'a pas pour effet de transférer un risque "
            "d'assurance important » : ces contrats relèvent de la vie, non "
            "du périmètre non-vie de cette version. L'option de "
            "l'atténuation du risque (B115-B116) tombe avec eux."),
    Element('§72-77', HORS_PERIMETRE,
            "Modification et décomptabilisation de contrats",
            "Événements de gestion de contrat, non calculs de clôture : "
            "leur place est le système de gestion de l'entité."),
    Element('§88-89', HORS_PERIMETRE,
            "Option de ventiler les produits et charges financiers entre "
            "résultat net et autres éléments du résultat global (OCI)",
            "Le §88 impose de CHOISIR l'une des deux méthodes. La "
            "plateforme retient la première : l'intégralité en résultat "
            "net. ⚠️ C'est une MÉTHODE COMPTABLE et elle se déclare en "
            "annexe aux états financiers, non seulement ici."),
    # ⚠️ CE QUE CETTE RAISON DISAIT AVANT, ET POURQUOI C'ÉTAIT FAUX. Elle
    # concluait : « les cas pluriannuels qui le déclencheraient échouent au
    # §53 b) », donc aucun cas §56 ne survient, donc pas de magasin. La
    # prémisse est réfutée — §53 b) fermé ne renvoie pas au modèle général,
    # la porte §53 a) reste ouverte (voir groupe.PORTE_53A) — et l'oracle ICA
    # 5.6.1 exhibe le cas exact que la phrase déclarait impossible.
    #
    # ⚠️ LA CONCLUSION SURVIT, LE RAISONNEMENT NON, ET LA DISTINCTION QUI
    # MANQUAIT EST CELLE-CI : appliquer un taux verrouillé FOURNI est un
    # paramètre ; constituer un magasin de courbes interrogeable par date est
    # un ouvrage. La raison confondait les deux, et écartait le premier avec
    # le second. Cette narration reste ICI, dans le code : la raison publiée
    # part chez le client par `texte()`, et un livrable n'est pas un journal
    # de corrections — y répéter l'affirmation fausse la ferait relire.
    Element('B72 b) à e), B73', HORS_PERIMETRE,
            "Révision du taux d'actualisation initial d'un groupe quand des "
            "contrats y entrent, et magasin de courbes indexé par date",
            "Mesuré : le B72 énumère cinq usages du taux verrouillé. Deux "
            "visent la marge sur services contractuels, ABSENTE en PAA ; un "
            "vise l'option OCI, exclue ci-dessus ; un vise les taux "
            "COURANTS, donc sans objet. Reste le §56 seul — qui s'exempte "
            "lui-même quand le délai entre service et échéance de prime "
            "n'excède pas un an, c'est-à-dire le contrat annuel. Un groupe "
            "pluriannuel mesuré en PAA par la porte §53 a) déclenche bien "
            "le §56, et ce cas existe : l'exemple 5.6.1 de l'ICA (doc "
            "222092, juin 2022) mesure un contrat de trois ans en PAA avec "
            "composante de financement, sur un taux verrouillé à la "
            "comptabilisation initiale. "
            "CE QUI RESTE HORS PÉRIMÈTRE EST LE MAGASIN, PAS LE TAUX : "
            "appliquer un taux verrouillé FOURNI est un paramètre, et la "
            "mesure §56 le prendra en entrée déclarée et signée ; "
            "constituer un magasin de courbes historiques interrogeable par "
            "date est un ouvrage distinct, non bâti, à rouvrir quand un "
            "portefeuille pluriannuel réel se présentera."),
    Element('annexe C', HORS_PERIMETRE,
            "Dispositions transitoires (rétrospective, rétrospective "
            "modifiée, juste valeur)",
            "IFRS 17 s'applique depuis le 1er janvier 2023 : la plateforme "
            "s'adresse à des entités ayant achevé leur transition. Réserve "
            "assumée — un premier adoptant, entité nouvelle ou passant aux "
            "IFRS aujourd'hui, sort de ce périmètre."),

    # ── Signalé par contrôle, non évalué ────────────────────────────────────
    Element('§10-13', HORS_PERIMETRE,
            "Séparation des composantes d'un contrat d'assurance",
            "Rare en non-vie. Non évaluée, mais SIGNALÉE par contrôle "
            "lorsque l'inventaire la déclare — voir `signaler`."),
    # ⚠️ §85 PORTE DEUX INTERDICTIONS, ET LA RAISON N'EN COUVRAIT QU'UNE.
    # Sa première phrase exclut les composantes d'investissement ; sa SECONDE
    # interdit de présenter des primes en résultat net lorsqu'elles ne sont
    # pas conformes au §83 — cela n'a rien à voir avec les composantes
    # d'investissement, et cela disparaissait sous un motif qui ne parlait
    # que d'elles. Une étiquette qui ne couvre pas ce qu'elle annonce.
    Element('§85', HORS_PERIMETRE,
            "Deux interdictions : exclure les composantes d'investissement "
            "des produits et charges d'assurance, et ne pas présenter en "
            "résultat net des primes non conformes au §83",
            "PREMIÈRE PHRASE — les composantes d'investissement sont rares "
            "en non-vie. Non évaluées, mais SIGNALÉES par contrôle lorsque "
            "l'inventaire les déclare — voir `signaler`. "
            "⚠️ SECONDE PHRASE — l'interdiction de présenter des primes non "
            "conformes au §83 est une contrainte de PRÉSENTATION, distincte "
            "de la première et NON CONSTRUITE : la plateforme ne produit "
            "encore aucun état de performance financière, elle ne peut donc "
            "ni l'enfreindre ni la tenir. Elle deviendra exigible le jour où "
            "le §80 sera bâti."),

    # ── Prévu, pas encore construit ─────────────────────────────────────────
    Element('§55-59, B125-B126', NON_CONSTRUIT,
            "Évaluation PAA : LRC, élément de perte, revenu, charges",
            "Le socle constitue les groupes et les scelle. LA MESURE EST "
            "PARTIELLEMENT BÂTIE, et le détail compte plus que le mot : "
            "§55 a) et b) le LRC initial et ultérieur — BÂTIS et adossés à "
            "l'oracle ICA 5.2 ; §56 la composante de financement — BÂTIE et "
            "adossée au déroulé ICA 5.6.1 sur trois arrêtés ; §57 et §58 le "
            "test du caractère déficitaire et l'élément de perte — BÂTIS "
            "sur déclaration signée, SANS oracle ; B125-B126 le produit des "
            "activités d'assurance — BÂTIS, avec le bouclage de B120. "
            "§59 b), le passif au titre des sinistres survenus — BÂTI. Il "
            "lit un triangle de liquidation pour ce qui est OBSERVÉ (charge "
            "cumulée, paiements, provision dossier) et REÇOIT la charge "
            "ultime déclarée et signée, avec sa méthode nommée : le choix "
            "entre Chain Ladder, Mack, Bornhuetter-Ferguson, Cape Cod et "
            "Bootstrap est un jugement actuariel, pas une lecture de la "
            "norme, et l'IBNR n'est que la différence — il hérite donc "
            "entièrement de l'incertitude du déclaré. "
            "⚠️⚠️ MAIS AUCUN MONTANT QUI EN DESCEND N'EST OPPOSABLE À CE "
            "JOUR : le triangle disponible porte la mention « synthétique, "
            "CADENCES INVENTÉES ». Une projection dessus rend UN NOMBRE, PAS "
            "UNE RÉSERVE — elle éprouve la plomberie, jamais l'exactitude. "
            "La réserve accompagne toute sortie tant que la source n'est pas "
            "attestée par l'actuaire signataire. "
            "⚠️ RESTE NON BÂTI : §59 a), l'option de passer les frais "
            "d'acquisition en charges — c'est un choix de l'entité, pas une "
            "règle."),
    Element('§60-70A', NON_CONSTRUIT,
            "Réassurance détenue",
            "⚠️ CE N'EST PAS UN « RÉGIME PROPRE », ET LA RAISON LE DISAIT À "
            "TORT. §61 impose de diviser les portefeuilles « CONFORMÉMENT "
            "AUX PARAGRAPHES 14 À 24 », avec UNE substitution : les "
            "références aux contrats déficitaires deviennent des références "
            "aux contrats donnant lieu à un PROFIT NET. Même agrégation, un "
            "critère inversé — et §61 admet explicitement un groupe d'un "
            "seul contrat. "
            "§69, L'ÉLIGIBILITÉ À LA PAA : BÂTIE. C'est le §53 à "
            "l'identique — deux portes disjonctives, §70 étant le miroir mot "
            "pour mot du §54 — et les trois verdicts portent les mêmes noms "
            "honnêtes : AUCUN ne dit « inéligible ». ⚠️ LA PARENTHÈSE DU "
            "§69 b) COMMANDE TOUT : la période inclut « la couverture "
            "d'assurance découlant de toutes les primes comprises dans le "
            "périmètre », donc elle DÉPEND DE LA BASE — en risques "
            "attachants la couverture des polices déborde, en sinistres "
            "survenus non. Mesuré sur les treize traités livrés : SEPT "
            "portes ouvertes, SIX fermées, la quote-part décennale couvrant "
            "onze ans au sens du §69 b). "
            "§63, LA MESURE : BÂTIE, et elle porte DEUX exigences de nature "
            "différente. La CONCORDANCE des hypothèses avec le sous-jacent "
            "est une contrainte qui se vérifie entre deux jeux fournis, elle "
            "ne se calcule pas — deux jeux évalués séparément peuvent chacun "
            "être défendable et se contredire entre eux, et rien d'autre ne "
            "l'attraperait. Le RISQUE DE NON-EXÉCUTION, lui, se calcule et se "
            "vérifie : le taux déclaré n'est pas repris mais contrôlé contre "
            "défaut × (1 − collatéral), ligne à ligne. "
            "⚠️ CE QUE §63 EXIGE EN TROIS TERMES, ET CE QUE LES DONNÉES "
            "PORTENT — « y compris l'effet des GARANTIES et des PERTES "
            "DÉCOULANT DE LITIGES ». Le défaut de crédit est présent ; les "
            "GARANTIES aussi, et la relation se vérifie exactement ; les "
            "LITIGES sont ABSENTS, mesuré à zéro occurrence sur les 2 251 "
            "lignes des quatre fichiers de réassurance livrés, toutes "
            "colonnes. L'omission n'est pas neutre : elle sous-estime le "
            "risque, donc surestime les récupérations et l'actif de "
            "réassurance — en faveur de l'entité. Tout montant qui descend du "
            "taux publie ce qu'il ne couvre pas. "
            "LA RÉCONCILIATION TRAITÉ ↔ CONTRAT : BÂTIE, et elle n'implémente "
            "AUCUN paragraphe — c'est un contrôle d'intégrité qui SERT le "
            "§63, lequel mesure des flux cédés ventilés par contrat. ⚠️ IL SE "
            "FAIT CELLULE PAR CELLULE, ET LA MESURE L'A IMPOSÉ : sur le "
            "portefeuille livré, un contrôle global rendrait « écart 0,14 € » "
            "alors que 0,86 € de mouvement existe, 0,72 € s'annulant entre "
            "portefeuilles. Un total qui boucle ne prouve pas que ses "
            "composantes bouclent. ⚠️ ET LA BORNE N'EST PAS UN SEUIL ACCORDÉ "
            "mais une borne DÉMONTRABLE : n contrats arrondis au centime "
            "portent au plus n × 0,005 € d'erreur. Mesuré : de 8 à 60 fois "
            "l'écart observé, et au plus 0,25 % d'une prime de traité. "
            "⚠️ CE QUI N'EST PAS VENTILÉ EST DÉCLARÉ, JAMAIS DEVINÉ : "
            "reconnaître la chaîne « XS_CATASTROPHE » ferait dépendre un "
            "verdict d'une convention de nommage, et un reliquat non déclaré "
            "est un REFUS, pas une tolérance. Mesuré sur les treize traités : "
            "douze mailles rapprochées, 7 277,31 € de prime catastrophe mise "
            "de côté — non réconciliée, et dite telle. "
            "§66A, §66B, §70A ET B119D-F, LE RECOUVREMENT DE PERTE : BÂTIS. "
            "⚠️ LE §70A EST UN AIGUILLAGE DONT L'AIGUILLE EST LE §69 : "
            "l'ajustement va à l'ACTIF au titre de la couverture restante si "
            "le groupe cédé est en PAA, à la MARGE SUR SERVICES CONTRACTUELS "
            "sinon. Or six des treize verdicts §69 sont NON_ETABLI — et ce "
            "sont les QUOTE-PARTS, c'est-à-dire exactement les traités qui "
            "portent la part de sinistres récupérable dont descend le "
            "recouvrement. Le module REFUSE alors de router plutôt que de "
            "retenir une destination par défaut. "
            "⚠️ B119E EST UNE MÉTHODE DE L'ENTITÉ, PAS UN CALCUL : « une "
            "méthode d'affectation SYSTÉMATIQUE ET RATIONNELLE » sans qu'une "
            "seule soit prescrite. Reçue déclarée avec sa méthode, refusée à "
            "défaut — et un montant sans sa méthode est refusé aussi, car "
            "c'est la méthode que B119E qualifie. "
            "⚠️⚠️ CE QUE LE CONTRÔLE B119F PROUVE, ET IL FAUT LE LIRE AVANT DE "
            "LE CITER : RIEN quant à la conformité. La composante étant "
            "calculée par B119D (perte × part), le plafond de B119F vaut "
            "cette même valeur — il est atteint PAR CONSTRUCTION. Sa seule "
            "valeur est celle d'un FILET DE NON-RÉGRESSION, qui mordra le "
            "jour où le calcul changera. L'étiquette descend avec chaque "
            "résultat, et la classe de tests la porte dans son nom. "
            "⚠️ ET « RESPECTÉ PAR CONSTRUCTION » EST LITTÉRALEMENT FAUX, "
            "mesuré : un contrôle strict échoue sur 129 des 235 lignes "
            "livrées. La cause est bénigne — l'arrondi au centime, maximum "
            "0,005 €, total 0,32 € soit 0,0038 % du recouvrement, zéro ligne "
            "au-delà. La formule exacte est « respecté à l'arrondi du centime "
            "près », et la borne employée est celle, démontrable, de "
            "n × 0,005 € — vérifié : le plafond agrégé est REFUSÉ sans elle. "
            "§61, §62 ET §62A, LE GROUPEMENT ET LA DATATION : BÂTIS. "
            "⚠️ ET CETTE RAISON DISAIT UNE CHOSE FAUSSE, corrigée ici : elle "
            "affirmait que « leur classement ET leur date reposent sur le "
            "caractère déficitaire du sous-jacent ». C'est vrai de la DATE, "
            "FAUX du CLASSEMENT. §61 classe sur le PROFIT NET DU CONTRAT "
            "CÉDÉ — sa position propre, critère du §16 a) retourné par la "
            "substitution du §61 ; §62 b) date sur le DÉFICIT DU "
            "SOUS-JACENT, une tout autre grandeur. Le panier des "
            "déficitaires n'entre donc QUE par le §62 b). "
            "⚠️ ET LE PANIER COMPLET DU §47 Y EST REFUSÉ : il descend d'une "
            "déclaration en statut A_REMPLACER, et l'admettre ferait hériter "
            "la date d'une déclaration non signée PAR UNE PORTE DÉROBÉE — le "
            "statut n'apparaîtrait nulle part dans le résultat. Seul le "
            "panier 552 est admis. Le panier livré à 249 est refusé aussi. "
            "⚠️ §62A DIT « NONOBSTANT LE §62 a) » : il ne concourt pas avec "
            "lui, il l'ÉCARTE. Une couverture PROPORTIONNELLE est reportée à "
            "la comptabilisation initiale d'un sous-jacent quand elle lui est "
            "postérieure. Mesuré : SIX quote-parts reportées, sept excédents "
            "datés directement — les mêmes six qui sont NON_ETABLI au §69 et "
            "qui portent le recouvrement. "
            "⚠️ ET SOUS PAA, UN PANIER EN SORTIE NETTE RENVERSE UNE "
            "PRÉSOMPTION (§18), IL NE REND PAS UN VERDICT. La date est la "
            "même, le STATUT diffère, et la réserve descend avec le motif. "
            "⚠️ CE QUE LE MODULE NE CALCULE PAS : la position nette du §61, "
            "qui se prononce sur des FLUX D'EXÉCUTION — actualisés et "
            "ajustés du risque par §32 a). Une comparaison brute des "
            "recouvrements aux primes cédées est un INDICATEUR, et le module "
            "exige qu'on lui nomme le panier employé. Sur le jeu livré, cet "
            "indicateur donne 55 cessions à profit net, toutes en RC_PRO. "
            "⚠️ RESTE NON BÂTI : §64-68, la suite de la mesure."),
    # ⚠️ CETTE RAISON SOUS-AFFIRMAIT, ET C'EST LA FAUTE INVERSE DE CELLE
    # CORRIGÉE EN C2-0. Elle disait « aucun n'est encore produit » : faux
    # depuis que la mesure existe. `mesure.lrc_paa.Periode` porte le résultat
    # des activités d'assurance, `mesure.financement.ArreteFinancement` porte
    # la charge financière. Les DEUX postes du §80 sont calculés — ce qui
    # manque est leur ASSEMBLAGE et leur présentation.
    #
    # ⚠️ Sous-affirmer trompe autant que sur-affirmer : un lecteur croirait
    # devoir refaire un travail déjà fait, ou jugerait la plateforme plus
    # loin de l'objectif qu'elle ne l'est.
    Element('§78-92', NON_CONSTRUIT,
            "Présentation au bilan et au compte de résultat",
            "§78-79, LA PRÉSENTATION AU BILAN : BÂTIE. Les portefeuilles y "
            "sont séparés par côté — actifs d'un côté, passifs de l'autre — "
            "et JAMAIS compensés entre eux, ce que §78 impose par le mot "
            "« séparément ». ⚠️ Deux lignes manquent et l'état le DIT : "
            "§78 c) et d), les portefeuilles de réassurance détenue, qui "
            "dépendent du §60-70A non construit. "
            "§80, LE COMPTE DE RÉSULTAT : BÂTI. Les deux postes sont "
            "assemblés — le résultat des activités d'assurance issu de la "
            "mesure PAA (§55-59), les produits et charges financiers issus "
            "de la composante de financement (§56) — et le §85 est vérifié : "
            "une composante d'investissement déclarée est REFUSÉE, faute de "
            "ligne où la mettre. ⚠️ CE QUI EN FAIT LA VALEUR N'EST PAS "
            "L'ADDITION mais la vérification CROISÉE avec le déroulé du "
            "passif (§100) : deux états produits séparément peuvent chacun "
            "boucler sur eux-mêmes et se contredire entre eux. "
            "⚠️ CETTE RÈGLE D'ARTICULATION A ÉTÉ LUE dans l'exemple 20 des "
            "Illustrative Examples accompagnant IFRS 17 (IFRS Foundation), "
            "mais AUCUNE VALEUR DE CETTE SOURCE N'EST REPRISE dans le dépôt : "
            "ses conditions de réutilisation sont restrictives et ce dépôt "
            "est public. L'exemple a enseigné l'invariant, il ne le vérifie "
            "pas. "
            "§87, LES PRODUITS ET CHARGES FINANCIERS : PARTIELLEMENT BÂTIS, "
            "et le détail compte. §87 vise « la variation de la valeur "
            "comptable DU GROUPE résultant de a) l'effet de la valeur temps "
            "de l'argent ET DE SES VARIATIONS ; b) l'effet du RISQUE "
            "FINANCIER ». La plateforme produit le déroulement du LRC au "
            "taux VERROUILLÉ (§56). LA DÉSACTUALISATION DU PASSIF AU TITRE DES "
            "SINISTRES SURVENUS ET L'EFFET DES VARIATIONS DE TAUX SONT "
            "DÉSORMAIS BÂTIS : le mouvement financier du LIC se décompose "
            "entre effet du temps et effet de courbe. ⚠️ Seul le TOTAL est "
            "exigé par §87 — la ventilation est une information de gestion, "
            "et elle est UNIQUE faute d'une quatrième valorisation qui "
            "permettrait un partage alternatif. ⚠️ MANQUE ENCORE : §87 b), "
            "l'effet du RISQUE FINANCIER, distinct de la valeur temps de "
            "l'argent et NON construit. ⚠️ Et le mouvement financier du LIC, "
            "lui, n'est bâti que dans sa MÉCANIQUE : il décompose trois "
            "valorisations reçues, il ne les produit pas, et les sinistres "
            "survenus dont il dépend portent la réserve des « cadences "
            "inventées » — aucun montant qui en descend n'est opposable à ce "
            "jour. "
            "§88-89 sont arbitrés et déclarés ci-dessus ; §90 et §91 sont "
            "SANS OBJET par construction, étant conditionnés à des options "
            "que la plateforme n'exerce pas. ⚠️ §92 a son PROPRE élément — "
            "les écarts de change ne sont ni §80 a) ni §80 b)."),
    # ⚠️ §92 A SON PROPRE ÉLÉMENT, ET C'EST UN ARBITRAGE. Il était AVALÉ par
    # l'intitulé de plage « §78-92 », dont ni le libellé ni la raison ne
    # mentionnaient les écarts de change, IAS 21 ni §30 — introuvable pour
    # qui le cherchait. C'est exactement la faute corrigée en C4-0, où la
    # seconde interdiction du §85 disparaissait sous une raison qui ne
    # parlait que de la première.
    #
    # ⚠️ ET C'EST UNE TROISIÈME NATURE. Les écarts de change ne relèvent NI
    # de la présentation du résultat d'assurance (§80 a), NI des produits et
    # charges financiers d'assurance (§80 b) : ils viennent d'IAS 21 par le
    # renvoi du §30. Une phrase ajoutée à la plage les laisserait dépendre
    # de la bonne volonté du lecteur.
    Element('§92, §30, IAS 21', NON_CONSTRUIT,
            "Écarts de change sur la valeur comptable des groupes de "
            "contrats d'assurance, présentés en résultat net",
            "§30 impose de traiter un contrat d'assurance comme un ÉLÉMENT "
            "MONÉTAIRE au sens d'IAS 21 ; §92 impose de présenter en "
            "résultat net les écarts de change sur la valeur comptable des "
            "groupes. ⚠️ CE N'EST NI §80 a) NI §80 b) : c'est un troisième "
            "poste, et le seul de §87-92 qui soit calculable aujourd'hui. "
            "NON BÂTI. ⚠️ Il ne peut pas se produire sur les inventaires "
            "remis à ce jour — toutes les lignes sont en EUR, le "
            "multidevise n'est pas exercé — mais cela tient à la DONNÉE, "
            "pas au périmètre. "
            "⚠️⚠️ ET UN DÉFAUT LATENT S'Y RATTACHE, SIGNALÉ ET NON TRAITÉ "
            "PARCE QU'IL VIT HORS DE CE CHANTIER : `actualiser` "
            "(`core/courbe_rfr.py`) NE LIT JAMAIS LA DEVISE. La courbe "
            "embarquée est en EUR seule, et `CourbeRFR.devise` n'est lue "
            "qu'à deux endroits — un en-tête d'affichage et une assertion "
            "de test. Un contrat en dollars serait donc actualisé sur la "
            "courbe euro EN SILENCE, contre B79 qui exige « la courbe des "
            "taux dans la monnaie appropriée ». Le mécanisme de garde "
            "existe juste à côté : `actualiser` REFUSE déjà une courbe "
            "sans agrément. Lot à ouvrir dans `core/`."),
    Element('§93-132', NON_CONSTRUIT,
            "Informations à fournir, dont le développement des sinistres "
            "(§130) et l'analyse de sensibilité (§128-129)",
            "Le §119, niveau de confiance de l'ajustement pour risque, est "
            "le seul déjà tenu — hors de ce socle, dans l'agent A11."),
    Element('§21', NON_CONSTRUIT,
            "Subdivision des groupes au-delà de §16",
            "Le champ `groupe_declare` de l'inventaire la permet ; elle "
            "n'est pas encore exploitée par la dérivation."),
    Element('§28, B73', NON_CONSTRUIT,
            "Entrée de contrats dans un groupe existant",
            "L'appartenance est construite ; la révision du taux qu'elle "
            "entraîne est hors périmètre — voir B72 ci-dessus."),
)


# =============================================================================
#  LES CONTRÔLES DE NON-APPLICABILITÉ
# =============================================================================

#: Champ de l'inventaire → (référence, ce que le contrôle dit).
#: ⚠️ Ces drapeaux ont été posés en D1 pour ce moment précis : reconnaître ce
#: qu'on ne traite pas plutôt que de le mesurer en silence.
CONTROLES: dict[str, tuple[str, str]] = {
    'participation_directe': (
        '§45, B101-B118',
        ("contrat(s) déclaré(s) avec éléments de participation directe : "
         "la méthode de la commission variable est HORS PÉRIMÈTRE. Ces "
         "contrats ne doivent pas être mesurés par cette plateforme.")),
    'composante_investissement': (
        '§85',
        ("contrat(s) déclaré(s) avec une composante d'investissement : elle "
         "doit être exclue des produits des activités d'assurance, ce que "
         "cette plateforme ne fait pas. Traiter ces contrats à part.")),
}


class Alerte(NamedTuple):
    """Un cas hors périmètre rencontré dans un inventaire réel."""
    champ:     str
    reference: str
    nb_lignes: int
    message:   str


def signaler(lignes: Iterable[Mapping]) -> tuple[Alerte, ...]:
    """Les cas hors périmètre présents dans un inventaire.

    ⚠️ SIGNALE, NE REFUSE PAS. Un inventaire peut légitimement contenir des
    contrats que cette plateforme ne mesure pas ; ce qui serait fautif, c'est
    de les mesurer quand même. L'alerte nomme le paragraphe et dit quoi faire.
    """
    compte: dict[str, int] = {}
    for ligne in lignes:
        for champ in CONTROLES:
            if _est_vrai(ligne.get(champ)):
                compte[champ] = compte.get(champ, 0) + 1
    return tuple(
        Alerte(champ, CONTROLES[champ][0], n,
               f"{n} {CONTROLES[champ][1]}")
        for champ, n in sorted(compte.items()))


def _est_vrai(valeur) -> bool:
    """Un drapeau posé, quelle que soit la façon dont le client l'écrit."""
    if valeur is None:
        return False
    if isinstance(valeur, bool):
        return valeur
    return str(valeur).strip().lower() in (
        'oui', 'o', 'yes', 'y', 'true', 'vrai', '1', 'x')


# =============================================================================
#  LE PÉRIMÈTRE PUBLIÉ
# =============================================================================

def elements(etat: str) -> tuple[Element, ...]:
    """Les éléments d'un état donné. Lève sur un état inconnu."""
    if etat not in ETATS:
        raise KeyError(
            f"État inconnu : « {etat} ». Les états sont {', '.join(ETATS)}.")
    return tuple(e for e in PERIMETRE if e.etat == etat)


def mention_directions(directions: Iterable[str]) -> str:
    """La mention à porter sur des états produits pour un abonnement partiel.

    ⚠️ UN JEU PARTIEL PRIS POUR UN JEU COMPLET EST CE QU'UN COMMISSAIRE
    RELÈVE. L'accès filtré au bord est une décision produit légitime ; la
    taire sur le livrable ne le serait pas.
    """
    d = sorted(set(directions))
    if not d:
        raise ValueError(
            "Aucune direction : des états financiers portent toujours sur "
            "un périmètre, fût-il unique.")
    if len(d) == 1:
        return (f"États financiers IFRS 17 limités aux groupes de la "
                f"direction {d[0]} — périmètre partiel.")
    return (f"États financiers IFRS 17 portant sur les directions "
            f"{', '.join(d)} — périmètre partiel.")


def texte() -> str:
    """Le périmètre publié, tel qu'il se remet à un actuaire ou à un CAC."""
    lignes = [
        "PÉRIMÈTRE IFRS 17 — ASSURANCE NON-VIE",
        "",
        "La plateforme couvre l'évaluation, la présentation et la clôture",
        "IFRS 17 en non-vie selon la MÉTHODE D'AFFECTATION DES PRIMES",
        "(§53-59), pour les contrats d'assurance émis et les contrats de",
        "réassurance détenus (§60-70A). Elle constitue l'unité de compte",
        "réglementaire à partir d'un inventaire de contrats fourni par",
        "l'entité, et conserve les clôtures successives.",
        "",
    ]
    for etat, titre in (
            (COUVERT, "CE QUI EST COUVERT"),
            (NON_CONSTRUIT, "DANS LE PÉRIMÈTRE, PAS ENCORE CONSTRUIT"),
            (HORS_PERIMETRE, "HORS PÉRIMÈTRE — DÉCISIONS ASSUMÉES")):
        groupe = elements(etat)
        lignes.append(f"{titre} ({len(groupe)})")
        for e in groupe:
            lignes.append(f"  {e.reference} — {e.libelle}")
            if e.raison:
                lignes.append(f"      {e.raison}")
        lignes.append("")
    # ⚠️ CE QUE CETTE PHRASE DISAIT AVANT, ET POURQUOI C'ÉTAIT FAUX. Elle
    # affirmait « ils ne sont jamais mesurés à tort ». Or `signaler()` REND
    # DES ALERTES ET NE LÈVE JAMAIS : il ne bloque rien. Une alerte que
    # personne ne lit laisse le contrat être mesuré. Promettre un blocage
    # qu'on ne fait pas est plus dangereux que ne rien promettre — le lecteur
    # cesse de surveiller. Le test `test_signaler_ne_refuse_jamais` disait
    # déjà la vérité ; c'est le texte publié qui la contredisait.
    lignes.append(
        "Les contrats relevant d'un pan hors périmètre sont SIGNALÉS par")
    lignes.append(
        "contrôle lorsque l'inventaire les déclare. ⚠️ LE SIGNALEMENT NE")
    lignes.append(
        "BLOQUE PAS LA MESURE : il revient à l'actuaire signataire de")
    lignes.append("décider du sort de ces contrats.")
    return '\n'.join(lignes)
