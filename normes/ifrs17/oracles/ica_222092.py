# -*- coding: utf-8 -*-
"""Oracle ICA/CIA doc 222092 — deux exemples chiffrés de mesure PAA.

⚠️ SEULES LES VALEURS ET LA CITATION SONT REPRISES. Aucun texte narratif de
la source n'est recopié : le dépôt est public, la source est protégée
(© 2022 Canadian Institute of Actuaries). Des nombres sont des faits ; la
rédaction qui les entoure ne l'est pas. Les libellés ci-dessous sont écrits
ici, ils ne sont pas des traductions de la source.

⚠️ AUTORITÉ — À LIRE AVANT DE S'APPUYER SUR UNE VALEUR. Note ÉDUCATIVE d'un
institut actuariel national, NON CONTRAIGNANTE : la source précise
elle-même qu'elle illustre une pratique acceptée parmi d'autres possibles.
Elle se situe SOUS la norme IFRS 17 et sous les exemples illustratifs de
l'IASB ; elle se situe AU-DESSUS d'un jeu synthétique, parce qu'elle est
externe, publiée, revue par six comités et le personnel de l'AcSB, et
approuvée par l'Actuarial Guidance Council le 08/02/2022.

⚠️ CE QUE CES DEUX EXEMPLES NE VERROUILLENT PAS — voir LACUNES plus bas. Le
trou le plus lourd est le groupe déficitaire : les deux exemples sont non
déficitaires, et le fichier de la section 7 sur l'élément de perte n'est pas
disponible. Aucune de ces valeurs ne dit quoi que ce soit du LIC.
"""

#: La citation, telle qu'elle doit accompagner toute valeur reprise ici.
SOURCE = (
    "ICA/CIA doc 222092, « IFRS 17 - Actuarial Considerations Related to "
    "Liability for Remaining Coverage in P&C Insurance Contracts », juin "
    "2022, © 2022 Canadian Institute of Actuaries")

#: Le niveau d'autorité, en une phrase — à publier avec tout écart constaté.
AUTORITE = (
    "note éducative NON CONTRAIGNANTE d'un institut actuariel national ; "
    "sous la norme IFRS 17 et sous les exemples illustratifs de l'IASB, "
    "au-dessus d'un jeu de données synthétique")

#: Devise abstraite de la source. ⚠️ PAS DES EUROS : ne jamais additionner
#: ces valeurs à des montants d'un portefeuille réel.
DEVISE = 'CU'

#: ⚠️ CE QUE CES DEUX EXEMPLES LAISSENT OUVERT. Une lacune tue, énoncée,
#: vaut un faux verrou : on croirait couvert ce qui ne l'est pas.
LACUNES = (
    ("frais d'acquisition FIXÉS À ZÉRO en 5.6.1 : l'interaction "
     "financement × frais d'acquisition n'est pas verrouillée"),
    ("groupes NON DÉFICITAIRES dans les deux cas : aucun élément de perte, "
     "et le fichier de la section 7 qui le traite n'est pas disponible"),
    "§57, le déclenchement du test du caractère déficitaire : rien",
    ("le passif au titre des sinistres survenus (LIC) : rien, les deux "
     "exemples ne portent que sur le LRC"),
    "un seul arrêté en 5.2 : la mesure ultérieure n'y est pas vérifiable",
    ("l'option §59 a) de passer les frais d'acquisition en charges n'est "
     "pas retenue par la source"),
    ("affectation prorata temporis dans les deux cas : le §55 b) ii, quand "
     "la libération du risque n'est pas uniforme, n'est pas exercé"),
    "granularité de GROUPE, jamais contrat par contrat",
)

# =============================================================================
#  TOLÉRANCES
# =============================================================================

#: ⚠️ 0,5 ET NON 1, ET C'EST MESURÉ. La source conseille « 1 unité sur les
#: soldes ». Sur un solde de 1 040, une unité vaut 0,1 % — assez lâche pour
#: laisser passer un vrai défaut. L'écart réel maximum entre la chaîne non
#: arrondie et les valeurs publiées est de 0,40 (revenu de financement de
#: l'année 2). 0,5 borne l'arrondi de présentation sans rien couvrir d'autre.
TOLERANCE = 0.5

# =============================================================================
#  SECTION 5.2 — LRC SANS ACTUALISATION, AVEC FRAIS D'ACQUISITION
# =============================================================================

#: Les données d'entrée. Prime encaissée en totalité à la comptabilisation
#: initiale, couverture de deux ans.
ENTREE_5_2 = {
    'prime': 1000.0,
    'duree_couverture_ans': 2,
    'frais_acquisition_attribuables': 200.0,
    'frais_maintenance_attribuables_an1': 50.0,
    'frais_acquisition_non_attribuables': 30.0,
    'frais_maintenance_non_attribuables_par_an': 25.0,
}

#: Les hypothèses retenues par la source — elles font partie de l'oracle :
#: une valeur attendue sous d'autres hypothèses ne serait pas la même.
HYPOTHESES_5_2 = {
    'sinistres_annee_1': 0.0,
    'base_affectation': 'prorata temporis',
    'frais_acquisition': 'capitalisés puis amortis sur 2 ans '
                         '(option §59 a) NON retenue)',
    'actualisation': 'aucune',
    'groupe_deficitaire': False,
}

#: Le résultat attendu au premier arrêté.
#:
#: ⚠️ LE POSTE QUI PORTE LA VALEUR DE CET EXEMPLE EST `lrc`. Il vaut 400 et
#: non 500 : les frais d'acquisition non amortis viennent EN DIMINUTION du
#: LRC, ils ne forment pas un actif séparé. Une implémentation qui les
#: logerait dans une ligne d'actif distincte afficherait un LRC de 500 et un
#: bilan qui équilibre quand même. C'est cette erreur-là que l'exemple
#: attrape, et c'est la seule qu'il attrape seul.
ATTENDU_5_2 = {
    'insurance_revenue': 500.0,
    'insurance_service_expenses': 150.0,
    'insurance_service_result': 350.0,
    'autres_charges': 55.0,
    'resultat': 295.0,
    'lrc': 400.0,
}

# =============================================================================
#  SECTION 5.6.1 — LRC AVEC COMPOSANTE DE FINANCEMENT (§56), TROIS ARRÊTÉS
# =============================================================================

#: ⚠️ POURQUOI CET EXEMPLE COMPTE AU-DELÀ DE SES CHIFFRES. Il mesure un
#: contrat de TROIS ANS en PAA. Si dépasser un an suffisait à imposer le
#: modèle général, il n'existerait pas : échouer à la voie automatique du
#: §53 b) n'entraîne pas le modèle général, le test qualitatif du §53 a)
#: reste ouvert. C'est ce cas qui a corrigé le socle (voir groupe.PORTE_53A).
ENTREE_5_6_1 = {
    'prime': 3000.0,
    'duree_couverture_ans': 3,
    'taux_verrouille': 0.02,
    'frais_acquisition': 0.0,
}

HYPOTHESES_5_6_1 = {
    'base_affectation': 'prorata temporis',
    'groupe_deficitaire': False,
    'composante_financement': 'significative — §56 applicable, la prime est '
                              'encaissée plus d\'un an avant le service',
    'charge_financiere': 'LRC d\'ouverture × taux verrouillé',
    'revenu_financement': '(cumul des charges financières − cumul du revenu '
                          'de financement antérieur) × part du service '
                          'fournie sur la période',
}

#: ⚠️ CONVENTION DE SIGNE — ELLE DIFFÈRE DE 5.2, DANS LE MÊME DOCUMENT. La
#: section 5.2 publie le revenu POSITIF (500) ; la section 5.6.1 le publie
#: NÉGATIF (−1 020), en tant que diminution du passif. Tout rapprochement
#: avec la plateforme devra retourner l'un des deux, et ce retournement doit
#: être DÉCLARÉ au point de comparaison, jamais silencieux.
#:
#: ⚠️ VALEURS PUBLIÉES, DONC ARRONDIES À L'UNITÉ. Le bouclage
#: `ouverture + charge + revenu = clôture` tombe juste aux années 1 et 3 et
#: laisse 1 unité à l'année 2. Ce n'est pas une erreur de transcription : la
#: chaîne NON ARRONDIE boucle exactement aux trois arrêtés (charge réelle
#: 40,80 publiée 41 ; revenu de financement réel 40,40 publié 40 ; clôture
#: réelle 1 040,40 publiée 1 040). Voir CHAINE_EXACTE_5_6_1.
ROLL_FORWARD_5_6_1 = (
    {'arrete': 'comptabilisation_initiale', 'lrc_ouverture': None,
     'charge_financiere': None, 'revenu_financement': None,
     'revenu_prime': None, 'revenu_total': None, 'lrc_cloture': 3000.0},
    {'arrete': 'fin_annee_1', 'lrc_ouverture': 3000.0,
     'charge_financiere': 60.0, 'revenu_financement': -20.0,
     'revenu_prime': -1000.0, 'revenu_total': -1020.0,
     'lrc_cloture': 2040.0},
    {'arrete': 'fin_annee_2', 'lrc_ouverture': 2040.0,
     'charge_financiere': 41.0, 'revenu_financement': -40.0,
     'revenu_prime': -1000.0, 'revenu_total': -1040.0,
     'lrc_cloture': 1040.0},
    {'arrete': 'fin_annee_3', 'lrc_ouverture': 1040.0,
     'charge_financiere': 21.0, 'revenu_financement': -61.0,
     'revenu_prime': -1000.0, 'revenu_total': -1061.0,
     'lrc_cloture': 0.0},
)

#: La même chaîne, sans arrondi, recalculée depuis les formules déclarées.
#:
#: ⚠️⚠️ CECI N'EST PAS UN ORACLE, ET NE DOIT JAMAIS ÊTRE PRÉSENTÉ COMME UNE
#: VALIDATION PAR L'ICA. Ce sont MES valeurs, obtenues en appliquant les
#: formules de la source à ses entrées. Les confronter à un calcul de la
#: plateforme qui emploierait les mêmes formules serait une tautologie : on
#: testerait la formule contre elle-même. Elles ne servent qu'à une chose —
#: établir que l'écart d'une unité de l'année 2 vient de l'arrondi de
#: présentation, et rien d'autre.
CHAINE_EXACTE_5_6_1 = (
    {'arrete': 'fin_annee_1', 'lrc_ouverture': 3000.0,
     'charge_financiere': 60.0, 'revenu_financement': 20.0,
     'lrc_cloture': 2040.0},
    {'arrete': 'fin_annee_2', 'lrc_ouverture': 2040.0,
     'charge_financiere': 40.8, 'revenu_financement': 40.4,
     'lrc_cloture': 1040.4},
    {'arrete': 'fin_annee_3', 'lrc_ouverture': 1040.4,
     'charge_financiere': 20.808, 'revenu_financement': 61.208,
     'lrc_cloture': 0.0},
)

#: ⚠️ CE QUE LE ZÉRO DE L'ANNÉE 3 NE PROUVE PAS. Le LRC DOIT s'éteindre en
#: fin de couverture : c'est structurel, pas une observation. Un calcul faux
#: qui n'aurait perdu aucun terme y arriverait aussi. La force probante de
#: cet exemple est dans les années 1 et 2 — et l'année 2 est précisément
#: celle que la source publie arrondie. L'oracle est plus mince qu'il n'en a
#: l'air, et c'est écrit ici pour que personne ne s'y fie plus qu'il ne vaut.
PORTEE_REELLE_5_6_1 = (
    "le zéro de l'année 3 est forcé par la structure ; seuls les arrêtés 1 "
    "et 2 portent une information, et l'arrêté 2 est publié arrondi")
