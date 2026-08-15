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
#: ⚠️⚠️ LE QUATRIÈME ÉTAT, ET C'EST CE DOCUMENT QUI L'A EXIGÉ. Sa propre
#: en-tête plaidait « TROIS ÉTATS, ET NON DEUX » — confondre « hors
#: périmètre » et « pas encore construit » trompe dans les deux sens. Le même
#: raisonnement en imposait un de plus, et la mesure l'a montré :
#:
#:   `NON_CONSTRUIT` disait à la fois « RIEN N'EXISTE » (§93-132) et
#:   « 20 modules, 5 182 lignes, 378 tests, avec des manques nommés »
#:   (§33-37, §55-59, §60-70A, §78-92).
#:
#: ⚠️ UN CLIENT NE POUVAIT PAS LES DISTINGUER — et le préambule du même
#: document revendiquait ces quatre pans. Sur-affirmation en tête,
#: sous-affirmation dans le corps, dans un seul texte.
#:
#: `BATI` dit : le mécanisme existe et il est testé. Ce qui lui manque À
#: L'INTÉRIEUR vit dans sa `raison`, qui l'a toujours dit avec précision.
BATI = 'BATI'
#: Décision assumée : la plateforme ne le fera pas, et dit pourquoi.
HORS_PERIMETRE = 'HORS_PERIMETRE'
#: Prévu, RIEN n'existe encore. ⚠️ N'est PAS une exclusion, et n'est PAS
#: « BATI avec des manques » — c'est exactement la confusion que le
#: quatrième état a défaite.
NON_CONSTRUIT = 'NON_CONSTRUIT'

ETATS = (COUVERT, BATI, HORS_PERIMETRE, NON_CONSTRUIT)

#: ⚠️⚠️ L'OPPOSABILITÉ EST UNE PROPRIÉTÉ DE LA DONNÉE, PAS DU PAN — et c'est
#: pourquoi elle est un CHAMP et non un cinquième état. Le jour où le client
#: remet un triangle de liquidation signé, quatre pans deviennent opposables
#: SANS QU'UNE LIGNE DE CODE CHANGE. En faire un état obligerait à réécrire
#: le périmètre pour un fait qui ne le concerne pas.
#:
#: ⚠️ ET LA DISTINCTION N'EST PAS THÉORIQUE : c'est aujourd'hui la seule qui
#: sépare « la plateforme sait le calculer » de « ce montant peut être signé ».
#: Le triangle disponible porte la mention « cadences INVENTÉES » ; les cinq
#: déclarations de taux portent `DEMONSTRATION_NON_SIGNEE` et `qualite=TIERS`.
OPPOSABLE = 'OPPOSABLE'
SOUS_RESERVE = 'SOUS_RESERVE'
OPPOSABILITE_SANS_OBJET = 'SANS_OBJET'

OPPOSABILITES = (OPPOSABLE, SOUS_RESERVE, OPPOSABILITE_SANS_OBJET)

#: ⚠️ LA PHRASE QUI PORTE TOUT CE DOCUMENT, et elle descend dans le texte
#: publié parce que c'est là qu'elle sert.
BATI_N_EST_PAS_OPPOSABLE = (
    "⚠️ BÂTI N'EST PAS OPPOSABLE, ET LA DIFFÉRENCE EST LE TOUT DE CE "
    "DOCUMENT. Un pan BÂTI a son mécanisme écrit et testé ; cela ne dit rien "
    "de la valeur des montants qui en sortent, laquelle dépend de la donnée "
    "remise et de sa signature.")


class Element(NamedTuple):
    """Un pan de la norme, et ce que la plateforme en fait.

    `raison` est obligatoire hors du cas COUVERT : une exclusion sans motif
    est une omission déguisée.

    ⚠️ `opposabilite` ET `reserve` FORMENT LE MÊME COUPLE QUE `etat` ET
    `raison` — un verdict clos, et son motif obligatoire dès qu'il réserve.
    Leur défaut est la chaîne VIDE et non `SANS_OBJET` : un défaut qui vaut
    une réponse valide ferait passer un champ non renseigné pour une décision.
    C'est la faute que ce dépôt a déjà payée avec « non vide n'est pas
    renseigné ».
    """
    reference:    str
    etat:         str
    libelle:      str
    raison:       str = ''
    opposabilite: str = ''
    reserve:      str = ''


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
            "TROIS N'ONT PAS LA MÊME SOLIDITÉ : le 747 hérite du statut "
            "A_REMPLACER de la déclaration qui l'alimente — que "
            "`mesure.declaration.est_renseigne` refuse. "
            "⚠️⚠️ ET UN QUATRIÈME PANIER EXISTE DEPUIS, SANS COMPTAGE. Les "
            "sinistres attendus sont NOMINAUX — confirmé au code source du "
            "générateur — alors que §32 a) ii) range l'ajustement pour la "
            "VALEUR TEMPS DE L'ARGENT dans les flux d'exécution, au même "
            "rang que l'ajustement pour risque. Aucun des trois premiers ne "
            "le porte. ⚠️ ET IL PENCHE DANS L'AUTRE SENS : l'actualisation "
            "RÉDUIT le comptage — 747 à taux nul, 690 à 1 %, 640 à 2 %, 587 "
            "à 3 %, 539 à 4 %. LES OMISSIONS NE SE COMPENSENT PAS : il "
            "faudrait environ 11 % pour retomber à 249, et un solde net "
            "cacherait deux erreurs de sens contraire sous un chiffre "
            "presque juste. "
            "⚠️⚠️ LA CONVENTION D'ACTUALISATION EST ELLE-MÊME UNE DÉCISION : "
            "ce n'est pas seulement la COURBE qui se déclare (§36 b), c'est "
            "aussi CE QU'ON ACTUALISE. Mesuré à 4 %, quatre conventions "
            "également défendables donnent 521, 539, 541 et 568 — 47 "
            "contrats d'écart pour un effet de 208, soit 23 % DE L'EFFET "
            "QU'ELLES MESURENT. "
            "⚠️ DEUX SÉRIES SONT DONC PORTÉES CÔTE À CÔTE, ET AUCUNE NE "
            "REMPLACE L'AUTRE. La convention A — durée moyenne, maintenance "
            "en nominal — a produit les comptages publiés : 747/690/640/587/"
            "539. La convention E — chaque flux à sa propre échéance, les "
            "frais de maintenance à 0,5 an parce qu'ils sont encourus sur la "
            "période de COUVERTURE et non de règlement — donne 747/688/637/"
            "579/532. Les deux sont reproduites ici à l'unité près sur les "
            "2 000 contrats. ⚠️ ET E N'EST PAS SIGNÉE : elle vient d'un "
            "fichier de démonstration dont chaque ligne porte « le producteur "
            "n'est PAS l'entité au sens du §36 ». Remplacer A par E ferait "
            "passer pour retenue une convention qui ne l'est pas. ⚠️ L'écart "
            "de SEPT contrats à 4 % est faible, mais c'est une propriété de "
            "CE portefeuille — les frais de maintenance y sont petits devant "
            "les sinistres — et non un résultat général. "
            "⚠️ LE 552 RESTE ADMIS POUR DATER LE §62 b), SOUS RÉSERVE : le "
            "refuser supprimerait une date que la norme exige, et un refus "
            "qui supprime une obligation est pire que le défaut qu'il évite. "
            "Sa réserve descend avec la date — ce comptage SURESTIME les "
            "déficitaires, donc §62 b) se déclenche trop souvent. "
            "⚠️⚠️ ET CETTE RAISON A DIT UNE CHOSE FAUSSE SUR LA COURBE, "
            "corrigée ici. Elle affirmait que l'ajustement pour risque de "
            "crédit de 10 points de base « doit être retraité, car c'est une "
            "construction réglementaire ». C'EST L'INVERSE : le CRA RETIRE de "
            "la courbe swap le risque de crédit bancaire résiduel, et §36 c) "
            "impose précisément d'« exclure l'effet des facteurs qui influent "
            "sur ces prix de marché observables, mais pas sur les flux de "
            "trésorerie » des contrats. Le retraitement du CRA est donc EXIGÉ "
            "par §36 c), non à défaire. "
            "⚠️ CE QUI MANQUE RÉELLEMENT EST LA PRIME D'ILLIQUIDITÉ. §36 a) "
            "exige de refléter « les caractéristiques de liquidité des "
            "contrats d'assurance », et B80 décrit l'approche ascendante : "
            "ajuster une courbe sans risque LIQUIDE pour tenir compte de "
            "l'écart de liquidité entre les instruments observés et les "
            "contrats. La courbe EIOPA sans VA n'en porte aucun — le VA en "
            "est la transposition Solvabilité II, que le code écarte déjà "
            "pour une raison qui lui est propre (agrément de l'art. 77 "
            "quinquies). Le taux §36 a donc DEUX termes, et un seul est "
            "disponible. ⚠️ Son sens PROLONGE celui de l'actualisation : une "
            "prime d'illiquidité augmente le taux, donc réduit le comptage "
            "AU-DELÀ des 539 mesurés à 4 %. "
            "⚠️ LA MESURE SUR LE LLP RESTE VRAIE MAIS PROUVE AUTRE CHOSE : la "
            "durée de règlement la plus longue est 4,76 ans (DO), très en "
            "deçà du LAST LIQUID POINT de 20 ans — l'EXTRAPOLATION vers l'UFR "
            "n'est pas atteinte. Ni le CRA ni l'extrapolation ne sont donc en "
            "cause ; reste la seule prime d'illiquidité. "
            "⚠️⚠️ ET LE VOLATILITY ADJUSTMENT NE PEUT PAS EN TENIR LIEU — CE "
            "N'EST PAS UN DÉFAUT DE CALIBRAGE, C'EST UN DÉFAUT D'OBJET. Des "
            "six critiques que la place adresse au VA, celle qui pèse ici est "
            "« la non prise en compte des caractéristiques des passifs "
            "d'assurance » : le VA se calcule sur un PORTEFEUILLE D'ACTIFS "
            "représentatif, quand §36 a) porte sur les CARACTÉRISTIQUES DE "
            "LIQUIDITÉ DES CONTRATS. Il répond à une autre question. ⚠️ Le "
            "refus du VA par `core/courbe_rfr.actualiser` était posé pour une "
            "raison SOLVABILITÉ II — l'agrément de l'art. 77 quinquies ; il "
            "en existe désormais une IFRS 17, et elle est PLUS FORTE : le VA "
            "n'est pas seulement soumis à agrément, il ne mesure pas la bonne "
            "chose. "
            "⚠️ LA PRIME SE DÉCLARE SOUS TROIS FORMES — technique, néant "
            "MOTIVÉ, ou refus — et JAMAIS en néant nu : un « néant » qui ne "
            "dit pas pourquoi affirme une conclusion sans l'établir, comme un "
            "montant sans sa méthode à B119E. Un néant motivé EST une "
            "déclaration, pas une absence, et il ne bloque pas la datation. "
            "⚠️⚠️ ET CETTE RAISON A PRÊTÉ À UNE SOURCE UNE AUTORITÉ QU'ELLE "
            "N'A PAS, corrigé ici. Elle exigeait que la déclaration tranche "
            "entre deux lectures de la plage CEIOPS de 24 à 48 ans — ce qui "
            "présuppose que la source gouverne quelque chose. Elle ne "
            "gouverne rien : NI §36 a) NI B80 NE POSENT DE SEUIL DE MATURITÉ, "
            "vérifié sur les blocs entiers du règlement. C'est le motif de "
            "l'étiquette qui affirme trop, appliqué à une CITATION. "
            "⚠️ ET L'ARGUMENT D'AUTO-ANNULATION QUI FIGURAIT ICI EST RETIRÉ, "
            "PAS NUANCÉ. Il opposait [24 ; 48] au Last Liquid Point de 20 ans "
            "pour conclure à une intersection vide. Or le LLP à 20 ans est le "
            "cadre EIOPA posé à la mise en œuvre de Solvabilité II, quand la "
            "phrase vient du « Task Force Report on the Liquidity Premium » "
            "du CEIOPS, DATÉ DE 2010 par la bibliographie de la note "
            "elle-même — et le CEIOPS a cessé d'exister le 1er janvier 2011. "
            "L'argument importait un paramètre POSTÉRIEUR DE CINQ ANS à la "
            "phrase qu'il commentait. Le garder affaibli aurait été pire que "
            "l'effacer. "
            "⚠️ « HORS PLAGE CEIOPS » N'EST DONC PAS UN MOTIF OPPOSABLE — "
            "trois degrés de distance : résumé français 2022 → rapport CEIOPS "
            "2010 → exercice quantitatif Solvabilité II. CE QUI EST "
            "OPPOSABLE, à la place : un écart de liquidité ténu à des "
            "maturités de 0,81 à 4,76 ans. La différence est tout le sujet — "
            "un motif tiré d'un seuil se discute sur la grammaire d'une "
            "source, un motif tiré de l'économie des passifs SE MESURE ET SE "
            "CONTESTE. "
            "⚠️ ET LE MÉCANISME NE JUGE PAS LA QUALITÉ DU MOTIF, seulement sa "
            "PRÉSENCE : « hors plage CEIOPS » porte un motif, donc passe, "
            "alors qu'il n'est pas opposable. Les deux contrôles sont "
            "distincts, et le second n'existe pas. "
            "⚠️ STATUT DE LA SOURCE CONSULTÉE : note de place professionnelle "
            "française, NON CONTRAIGNANTE — même régime que la note ICA "
            "222092. Elle a servi à ORIENTER trois vérifications, dont deux "
            "ont été tranchées ailleurs : le §36 c) au texte du règlement, la "
            "lecture CEIOPS par cohérence interne. AUCUNE de ses valeurs "
            "n'entre dans le code. Elle éclaire, elle ne signe pas."),
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
    Element('§33-37, B36-B92', BATI,
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
            "formes fictives, zéro rejet à tort.",
            SOUS_RESERVE,
            "Aucune donnée de sinistres n'a été remise : ni triangle de "
            "liquidation, ni échéancier de règlement. Le module ne peut être "
            "alimenté que par des montants saisis, et il n'est adossé à "
            "AUCUNE source externe — ses garanties sont des invariants "
            "internes, pas une concordance publiée."),
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
    Element('§55-59, B125-B126', BATI,
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
            "règle.",
            SOUS_RESERVE,
            "Le triangle de liquidation disponible porte la mention "
            "« synthétique, CADENCES INVENTÉES » : aucun montant qui en "
            "descend n'est opposable tant que la source n'est pas attestée "
            "par l'actuaire signataire. La réserve accompagne toute sortie."),
    Element('§60-70A', BATI,
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
            "⚠️⚠️ L'AIGUILLE DU §70A EST LE MODÈLE ÉLU, ET CETTE RAISON "
            "DISAIT « LE §69 », À TORT. §70A pose sa condition sur « SI "
            "l'entité ÉVALUE un groupe […] selon la méthode d'affectation des "
            "primes », quand §69 dit seulement que l'entité « PEUT » "
            "l'appliquer : une option ouverte n'est pas une option levée, et "
            "router sur l'éligibilité supposait une élection que personne n'a "
            "déclarée. Le module reçoit désormais le modèle ÉLU et refuse à "
            "défaut. L'ajustement va à l'ACTIF au titre de la couverture "
            "restante si le groupe est ÉVALUÉ en PAA, à la MARGE SUR SERVICES "
            "CONTRACTUELS sinon. "
            "⚠️ ET L'INDÉTERMINATION VISE LES TREIZE TRAITÉS, PAS SIX. AUCUN "
            "ne porte l'élection du modèle d'évaluation. Les six quote-parts "
            "restent particulières pour trois raisons mesurées — §62A les "
            "reporte, §69 b) ne les établit pas, elles portent le "
            "recouvrement — mais l'aiguillage n'en est pas une quatrième, et "
            "le dire aurait plié la mesure à l'hypothèse. "
            "⚠️ LA TENSION ENTRE ÉLECTION ET ÉLIGIBILITÉ SE PUBLIE SANS SE "
            "TRANCHER : une entité qui déclare évaluer en PAA un groupe non "
            "établi au §69 déclenche bien le §70A, mais elle affirme du même "
            "coup le §69 a), que le code n'a pas vérifié. Le motif le porte. "
            "⚠️ ET UNE ASYMÉTRIE QU'UN COMMISSAIRE SONDERA : §68 pose que la "
            "réassurance détenue NE PEUT PAS être déficitaire et écarte les "
            "§47-52. La marge sur services contractuels d'un groupe CÉDÉ est "
            "donc SIGNÉE — un coût net, sans plancher ni composante de perte "
            "— là où celle d'un groupe ÉMIS est bloquée à zéro. Le même mot "
            "désigne deux objets qui n'ont pas les mêmes bornes. "
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
            "§64 À §68, LA SUITE DE LA MESURE CÉDÉE : BÂTIS — et c'est le "
            "PREMIER BLOC DE CE CHANTIER OÙ LA NORME CALCULE VRAIMENT. Sur "
            "les paragraphes précédents, la réponse à « que permet-il de "
            "calculer ? » était le plus souvent « rien, c'est une décision "
            "d'entité ». Ici §65 est une SOMME de quatre termes, §66 un "
            "DÉROULÉ de six postes, §67 une CONTRAINTE négative et §68 un "
            "INVARIANT — quatre grandeurs vérifiables. "
            "⚠️ §68 N'EST PAS UNE REMARQUE, IL CHANGE LE TYPE DU RÉSULTAT : "
            "en écartant les §47-52, il rend la marge cédée SIGNÉE — un coût "
            "net sans plancher à zéro et sans composante de perte — là où "
            "celle d'un groupe ÉMIS est bloquée à zéro. Le même mot désigne "
            "deux objets qui n'ont pas les mêmes bornes, et un commissaire "
            "aux comptes le sondera. "
            "⚠️ §67 DIT QUOI NE PAS METTRE, ET C'EST CE QUI LE REND "
            "VÉRIFIABLE : la variation due au risque de non-exécution est "
            "EXCLUE du déroulé, le module l'exclut lui-même et PUBLIE le "
            "montant exclu plutôt que de croire l'appelant sur parole. "
            "⚠️ ET §64 EST LE SEUL DES CINQ QUI NE CALCULE RIEN : il remplace "
            "une règle sans méthode (§37) par une autre règle sans méthode, "
            "en changeant seulement ce que la grandeur signifie — le risque "
            "TRANSFÉRÉ, non le risque supporté. UNE SEULE chose y est "
            "vérifiable, et le module ne prétend à rien d'autre : on ne "
            "transfère pas plus de risque qu'il n'en existe. ⚠️ Cette borne "
            "ÉCARTE L'IMPOSSIBLE, ELLE NE VALIDE PAS LE PLAUSIBLE — un "
            "ajustement cédé nul la respecterait et serait absurde sur une "
            "quote-part. "
            "⚠️ TROIS OMISSIONS DIFFÉRENTES, UN MÊME SENS : les litiges au "
            "§63, la décomptabilisation supposée nulle au §65 b) et un "
            "ajustement cédé surestimé au §64 gonflent tous l'actif de "
            "réassurance, EN FAVEUR DE L'ENTITÉ. C'est ce qui rend ces "
            "contrôles utiles plutôt que formels. "
            "⚠️ CE QUI RESTE REMIS À L'ENTITÉ ICI : la méthode du §64, les "
            "unités de couverture de B119 pour le poste §66 e), la "
            "qualification « événements antérieurs » du §65A, le montant "
            "décomptabilisé du §65 b), et le modèle d'évaluation du groupe "
            "SOUS-JACENT pour l'exclusion du §66 c) ii) — distinct de celui "
            "du groupe cédé.",
            SOUS_RESERVE,
            "Quatre décisions restent remises à l'entité et aucune n'est "
            "signée à ce jour : la méthode du §64, les unités de couverture "
            "de B119 pour le poste §66 e), la qualification « événements "
            "antérieurs » du §65A et le montant décomptabilisé du §65 b). "
            "S'y ajoute la réserve des sinistres survenus, dont dépend la "
            "part cédée."),
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
    Element('§78-92', BATI,
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
            "les écarts de change ne sont ni §80 a) ni §80 b).",
            SOUS_RESERVE,
            "Deux lignes du §78 manquent — c) et d), les portefeuilles de "
            "réassurance détenue — et §87 b), l'effet du risque financier, "
            "n'est pas construit. S'y ajoute la réserve des sinistres "
            "survenus : le mouvement financier du LIC décompose trois "
            "valorisations reçues, il ne les produit pas."),
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
    # ⚠️⚠️ CE PAN ÉTAIT UN SEUL ÉLÉMENT « §93-132 », ET IL NE POUVAIT PAS
    # PORTER UN ÉTAT VRAI. Les trois tiers du bloc n'auront JAMAIS le même :
    # les rapprochements sont un OUVRAGE à bâtir, les risques et jugements
    # sont majoritairement de la PROSE que seule l'entité écrit. Une étiquette
    # unique aurait donc été fausse pour au moins une moitié.
    #
    # ⚠️ C'EST LE DÉFAUT DU §92 AVALÉ PAR LA PLAGE §78-92, corrigé une fois
    # déjà : une plage dont ni le libellé ni la raison ne mentionnaient les
    # écarts de change, introuvable pour qui les cherchait. La scission
    # l'ANTICIPE au lieu de le subir.
    #
    # ⚠️ ET LA COUPURE NE LAISSE AUCUN TROU : §106 à §109 sont exclus en PAA
    # par §97, mais ils doivent rester DANS un élément — sinon ils
    # n'appartiendraient à rien, et « exclu » deviendrait indistinguable
    # d'« oublié ». Ils vivent donc dans le pan des rapprochements, qui dit
    # lui-même lesquels de ses paragraphes ne s'appliquent pas.
    Element('§93-97', NON_CONSTRUIT,
            "Objectif des informations à fournir, niveau de regroupement, et "
            "les trois informations propres à la méthode d'affectation des "
            "primes",
            "⚠️ §97 EST L'INDEX DU BLOC, ET IL SE LIT AVANT TOUT LE RESTE : "
            "« Parmi les obligations d'information énoncées aux paragraphes "
            "98 à 109A, SEULES celles des paragraphes 98 à 100, 102, 103, "
            "105 à 105B et 109A s'appliquent aux contrats évalués selon la "
            "méthode d'affectation des primes. » ⚠️ Sa portée s'arrête à "
            "§109A : il ne dit RIEN de §110 à §132, qui portent leurs propres "
            "restrictions. "
            "⚠️ ET §97 IMPOSE EN OUTRE TROIS INFORMATIONS PROPRES À LA PAA, "
            "dont la plateforme tient déjà la matière : a) laquelle des "
            "conditions des §53 et §69 est remplie — le socle scelle ce "
            "verdict ; b) si un ajustement a été apporté pour la valeur temps "
            "de l'argent (§56, §57 b), §59 b)) — `mesure.financement` le "
            "porte ; c) la méthode retenue pour les flux liés aux frais "
            "d'acquisition (§59 a)) — DÉCISION DE L'ENTITÉ, et elle n'est pas "
            "bâtie. ⚠️ Aucune n'est PRODUITE aujourd'hui : la matière existe, "
            "la restitution non. "
            "⚠️ §96 laisse le NIVEAU DE REGROUPEMENT à l'entité — IAS 1 §29-31, "
            "et « il pourrait par exemple être approprié » par type de "
            "contrat, zone géographique ou secteur IFRS 8. Rien n'est "
            "prescrit : la plateforme stocke à la maille FINE du groupe, "
            "l'agrégation est un choix de restitution."),
    Element('§98-109A', NON_CONSTRUIT,
            "Rapprochements des soldes d'ouverture et de clôture, et leurs "
            "causes de mouvement",
            "⚠️ LA MATIÈRE EST BÂTIE, LA RESTITUTION NE L'EST PAS, et "
            "confondre les deux serait la sur-affirmation que ce document "
            "vient de corriger ailleurs. `socle.cloture` porte les QUATRE "
            "soldes du §100 — le passif net de couverture restante hors "
            "élément de perte, l'élément de perte, et le passif des sinistres "
            "survenus VENTILÉ entre flux futurs et ajustement pour risque, "
            "cette ventilation ne portant que sur le poste c) — ainsi que les "
            "ONZE postes de mouvement de §103 et §105 et le résidu du "
            "§105 d). ⚠️ MAIS AUCUN TABLEAU N'EST PRODUIT : §99 a) exige les "
            "rapprochements « sous forme de tableau », et rien ne les "
            "assemble. "
            "⚠️ CE QUI NE S'APPLIQUE PAS EN PAA, PAR §97 : §101 et §104 "
            "(ils visent les contrats « qui NE SONT PAS évalués » selon la "
            "PAA et apporteraient la marge sur services contractuels, qui "
            "n'existe pas ici), §106, §107, §108 et §109. ⚠️ §109 ET §109A "
            "SONT DEUX PARAGRAPHES DIFFÉRENTS : le premier est exclu, le "
            "second s'applique. "
            "⚠️⚠️ TROIS PARAGRAPHES SONT BLOQUÉS PAR UNE SEULE ET MÊME CAUSE, "
            "ET CE N'EST PAS TROIS OUBLIS : §105A (rapprochement séparé de "
            "l'actif au titre des flux liés aux frais d'acquisition), §105B "
            "(pertes de valeur et reprises de cet actif) et §109A (calendrier "
            "ATTENDU de sa décomptabilisation) reposent tous sur le mécanisme "
            "des §28B, §28C, §28E et §28F, QUI N'EST PAS BÂTI. Le §28B est "
            "traité au bilan (§79, incorporation au portefeuille) ; son "
            "déroulé, sa dépréciation et sa décomptabilisation ne le sont "
            "pas. Un seul ouvrage manquant, trois informations absentes. "
            "⚠️ §102 est une clause d'OBJECTIF : il n'y a rien à en calculer."),
    Element('§110-132', NON_CONSTRUIT,
            "Produits et charges financiers, jugements importants, et nature "
            "et ampleur des risques",
            "⚠️ CE PAN EST MAJORITAIREMENT DE LA PROSE QUE SEULE L'ENTITÉ "
            "ÉCRIT, et le dire est plus utile que de promettre un ouvrage. "
            "§117 (jugements, données d'entrée, hypothèses), §121 à §127 "
            "(expositions, objectifs, politiques, concentrations) et §132 a) "
            "(gestion du risque de liquidité) ne se calculent pas. §125 a) "
            "s'appuie même explicitement sur les informations « communiquées "
            "EN INTERNE aux principaux dirigeants », que la plateforme ne "
            "voit pas. "
            "⚠️ DEUX EXIGENCES SORTENT STRUCTURELLEMENT DU PÉRIMÈTRE, ET PAS "
            "FAUTE DE TRAVAIL : §110 demande d'expliquer le lien entre les "
            "charges financières d'assurance et LE RENDEMENT DES ACTIFS de "
            "l'entité, et §128 a) ii) de relier la sensibilité des contrats à "
            "celle des ACTIFS FINANCIERS DÉTENUS. La plateforme mesure des "
            "passifs d'assurance ; elle ne voit aucun actif. "
            "⚠️ CE QUI EST RESTITUABLE, ET SEULEMENT RESTITUABLE : §119, le "
            "niveau de confiance de l'ajustement pour risque — déjà tenu hors "
            "de ce socle, dans l'agent A11, et `mesure.flux_execution` porte "
            "le champ ; §120, la courbe d'actualisation employée. ⚠️ ET §120 "
            "PORTE UN PIÈGE DÉJÀ PAYÉ : il admet une présentation « sous "
            "forme de MOYENNES PONDÉRÉES ou de fourchettes ». Une moyenne "
            "pondérée de courbe est une DÉCISION, exactement comme la "
            "pondération de B73 — trois pondérations défendables donnent "
            "trois courbes. Elle se REÇOIT déclarée, elle ne se calcule pas. "
            "La fourchette, elle, se déduit des taux remis. "
            "⚠️ §130 — LE DÉVELOPPEMENT DES SINISTRES, avec ses deux bornes "
            "et son « cependant ». Il n'est pas obligatoire de remonter "
            "au-delà de DIX ANS, ni de couvrir les sinistres dont "
            "l'incertitude « est habituellement levée dans un délai d'un "
            "an » ; mais l'entité doit CEPENDANT rapprocher le développement "
            "communiqué de la valeur comptable totale présentée en "
            "application du §100 c). ⚠️ Ce rapprochement, lui, est calculable "
            "— c'est exactement ce que `socle.cloture` porte. "
            "⚠️ §132 — LE PASSIF AU TITRE DE LA COUVERTURE RESTANTE EN PAA "
            "EST EXCLU DE L'ANALYSE D'ÉCHÉANCES, le texte le dit : « l'entité "
            "n'est pas tenue d'inclure dans ces analyses le passif au titre "
            "de la couverture restante évalué selon les paragraphes 55 à 59 "
            "et les paragraphes 69 à 70A ». Il ne reste donc que le passif "
            "des sinistres survenus — et AUCUN ÉCHÉANCIER DE RÈGLEMENT n'a "
            "été remis à ce jour. "
            "⚠️ §131 est partiellement atteignable : l'exposition maximale au "
            "risque de crédit se calcule sur la part cédée, et le chantier de "
            "réassurance vérifie déjà le taux de défaut contre "
            "« défaut × (1 − collatéral) » ligne à ligne ; en revanche la "
            "QUALITÉ DU CRÉDIT des réassureurs — une notation — n'est dans "
            "aucune donnée remise."),
    # ⚠️⚠️ CETTE EXCLUSION N'A AUCUN APPUI NORMATIF, ET C'EST SA RAISON
    # D'ÊTRE. Aucun paragraphe d'IFRS 17 ne dit comment le document est
    # RÉDIGÉ : la norme prescrit ce qui doit y figurer, pas la plume. Ce
    # qu'aucun texte n'interdit, aucun texte n'arrête — la ligne existe donc
    # ici, où un actuaire qui signe et un CAC qui lit la rencontreront.
    #
    # ⚠️ ET LE RISQUE EST MESURÉ, PAS CRAINT. `core.frontiere_llm` déclare
    # TREIZE sites d'appel, dont NEUF sont des narrations de rapport —
    # provisionnement, tarification, vie, santé, prévoyance. **AUCUN n'est
    # dans `normes/`** : IFRS 17 est aujourd'hui le seul domaine du dépôt
    # sans site LLM, et rien ne le disait. Le jour où le rendu des états
    # sera bâti, la chaîne A7 sera le modèle évident à reprendre — elle
    # porte `_narration_claude_api`, et la reprendre par réflexe de
    # réutilisation est le chemin le plus court.
    #
    # ⚠️ LE VERROU TIENT EN DEUX PIÈCES, ET AUCUNE NE SUFFIT SEULE :
    #   · `test_frontiere_llm` interdit d'appeler l'API hors de la frontière,
    #     dans TOUT le dépôt — un quatorzième site doit donc l'importer ;
    #   · `test_perimetre` interdit qu'un fichier de `normes/` l'importe.
    # Ensemble, elles rendent la déclaration vérifiable et non seulement
    # écrite. Une exclusion que personne ne contrôle est une intention.
    Element('aucun paragraphe — production du livrable', HORS_PERIMETRE,
            "Rédaction par modèle de langage de tout ou partie des états "
            "financiers (§78-92) et de leurs annexes (§93-132)",
            "Les états financiers et leurs annexes ne comportent AUCUN texte "
            "produit par un modèle de langage. La norme prescrit des MONTANTS "
            "et des rapprochements dont la forme est imposée (§99-109) : un "
            "rapport actuariel argumente, une annexe énonce. Une phrase "
            "générée dans un document signé affirmerait plus que la mesure ne "
            "porte, et aucun contrôle ne peut la confronter au texte comme il "
            "confronte un montant. ⚠️ AUCUN PARAGRAPHE D'IFRS 17 NE L'INTERDIT "
            "— la norme ne dit pas qui tient la plume — et c'est précisément "
            "pourquoi cette exclusion est écrite : ce qu'aucun texte "
            "n'interdit, aucun texte n'arrête. ⚠️ ELLE PORTE SUR LE CONTENU DU "
            "LIVRABLE, NON SUR LA PLATEFORME : un modèle de langage peut "
            "servir en amont — reconnaissance de colonnes, assistance à la "
            "saisie — sans qu'aucune de ses sorties n'entre dans les états. La "
            "frontière technique unique par laquelle une donnée sort reste "
            "inchangée : cette ligne déclare un PÉRIMÈTRE, pas un mécanisme."),
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
    #: ⚠️⚠️ CE PRÉAMBULE A ÉTÉ FAUX DANS LES DEUX SENS À LA FOIS, et la
    #: mesure l'a établi. Il disait « la plateforme COUVRE l'évaluation, la
    #: présentation et la clôture » — sur-affirmation : §93-132 n'est pas
    #: bâti, et « conserve les clôtures successives » ne l'a jamais été, la
    #: persistance des soldes restant à construire. Et le corps du MÊME
    #: document déclarait `NON_CONSTRUIT` les quatre pans que le préambule
    #: revendiquait — sous-affirmation sur 20 modules et 378 tests.
    #:
    #: ⚠️ La correction ne consiste pas à choisir un des deux sens : elle
    #: consiste à dire ce qui est BÂTI, et à ne plus confondre bâti et
    #: opposable. Le décompte ci-dessous se lit sur `PERIMETRE`, il n'est
    #: donc pas une affirmation de plus à tenir à jour à la main.
    lignes = [
        "PÉRIMÈTRE IFRS 17 — ASSURANCE NON-VIE",
        "",
        "La plateforme constitue l'unité de compte réglementaire (§14-25) à",
        "partir d'un inventaire de contrats fourni par l'entité, et",
        "enregistre les groupes d'un arrêté à l'autre.",
        "",
        f"Le MÉCANISME est bâti et testé sur {len(elements(BATI))} pans de",
        "la norme, énumérés ci-dessous : évaluation en méthode d'affectation",
        "des primes, réassurance détenue, flux d'exécution et présentation",
        "aux états primaires.",
        "",
        BATI_N_EST_PAS_OPPOSABLE,
        "",
    ]
    for etat, titre in (
            (COUVERT, "CE QUI EST COUVERT"),
            (BATI, ("BÂTI ET TESTÉ — avec, pour chacun, ce qui lui manque à "
                    "l'intérieur et ce qui réserve son opposabilité")),
            (NON_CONSTRUIT, "DANS LE PÉRIMÈTRE, RIEN N'EXISTE ENCORE"),
            (HORS_PERIMETRE, "HORS PÉRIMÈTRE — DÉCISIONS ASSUMÉES")):
        groupe = elements(etat)
        lignes.append(f"{titre} ({len(groupe)})")
        for e in groupe:
            lignes.append(f"  {e.reference} — {e.libelle}")
            if e.raison:
                lignes.append(f"      {e.raison}")
            if e.opposabilite == SOUS_RESERVE:
                lignes.append(f"      ⚠️ OPPOSABILITÉ RÉSERVÉE : {e.reserve}")
            elif e.opposabilite == OPPOSABLE:
                lignes.append("      OPPOSABLE — aucune réserve de donnée.")
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
