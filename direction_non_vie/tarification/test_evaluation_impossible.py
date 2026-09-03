# -*- coding: utf-8 -*-
"""
=============================================================================
  QUAND AUCUN MODELE NE PEUT ETRE EVALUE -- on le DIT, on ne choisit pas
=============================================================================

ARBITRAGE DE SELASSE, 03/09/2026, sur les trois agents ensemble. Quand aucun
modele ne peut etre vraiment evalue, le systeme doit :

  1. le DIRE clairement, jamais produire un tarif silencieusement sur une
     selection arbitraire ;
  2. NOMMER les vraies causes probables, derivees des donnees fournies ;
  3. donner un CONSEIL ACTIONNABLE pour corriger le fichier, pas un message
     d'erreur sec.

-----------------------------------------------------------------------------
DEUX IMPOSSIBILITES QUI NE SE CONFONDENT PAS
-----------------------------------------------------------------------------
  AMONT, deja en place -- `CalibrationImpossible` (A3) : le jeu
  d'ENTRAINEMENT ne porte aucun sinistre. Le maximum de vraisemblance de
  l'intercept vaut log(0) : aucun modele n'existe.

  ICI -- `ArbitrageImpossible` : l'entrainement porte des sinistres, les
  modeles sont CALIBRES et utilisables ; c'est le TEST qui n'en porte aucun.
  Ce qui est impossible n'est pas l'ajustement, c'est le CLASSEMENT.

  *On peut ajuster, on ne peut pas departager. Choisir quand meme serait
  tirer au sort le modele qui fixera des primes.*

-----------------------------------------------------------------------------
POURQUOI LE CONTROLE PORTE SUR LE DIAGNOSTIC ET NON SUR LE CATALOGUE
-----------------------------------------------------------------------------
Le refus prealable d'A6 ne tire que si le catalogue est VIDE. Or
`_calculer_gini` rend encore `0.0` sur un jeu non mesurable dans les trois
agents (A3 : 3 branches, A4 : 3, A5 : 2 -- et A5 n'a AUCUNE garde sur la
somme nulle). Les modeles y restent donc, notes zero.

  **Un catalogue plein n'est pas une preuve qu'il y avait quelque chose a
  comparer.**

⚠️ LE `0.0` N'EST PAS CORRIGE ICI, ET C'EST MESURE : le convertir en `None`
casserait 196 lignes de production, dont 111 DANS les trois agents (releve
AST du 03/09/2026), chacune exigeant de decider quoi AFFICHER. Ce qui compte
-- ne jamais SELECTIONNER sur une note fabriquee -- est obtenu sans y
toucher : l'arbitrage s'arrete avant de la lire.
=============================================================================
"""

import ast
import inspect
import pathlib
import re
import textwrap
import unittest

from core.conformite_reglementaire import (
    CAUSE_CIBLE_NON_RENSEIGNEE,
    CAUSE_DECOUPAGE_ALEATOIRE,
    CAUSE_PORTEFEUILLE_PETIT,
    CAUSE_TEST_PERIODE_RECENTE,
    COLONNES_TEMPORELLES,
    SEUIL_REGLE_DE_TROIS,
    ArbitrageImpossible,
    colonne_temporelle,
    conseil_actionnable,
    diagnostiquer_evaluation,
    doit_refuser_arbitrage,
    message_arbitrage_impossible,
    phrase_evaluation_impossible,
)

_BASE = {'cible': 'nb_sinistres', 'n_train': 8000, 'n_test': 2000,
             'sinistres_train': 400.0, 'sinistres_test': 0.0}


def _diag(**surcharges):
    return diagnostiquer_evaluation(**{**_BASE, **surcharges})


class T1_LeDiagnostic(unittest.TestCase):

    def test_ei_1_aucune_alerte_quand_l_evaluation_est_possible(self):
        """EI-1 : le second sens. Un diagnostic qui parle toujours ne dit rien.

        ⚠️ Un sinistre suffit : ce n'est pas un seuil de FIABILITE, c'est le
        seuil de la POSSIBILITE. Les confondre reviendrait a inventer le
        seuil que Selasse a explicitement refuse d'inventer.
        """
        self.assertIsNone(_diag(sinistres_test=1.0))
        self.assertIsNone(_diag(sinistres_test=97.0))
        self.assertIsNotNone(_diag(sinistres_test=0.0))

    def test_ei_14_sans_sinistre_NULLE_PART_c_est_l_AUTRE_refus(self):
        """EI-14 : L'ARTICULATION, APPLIQUEE ET NON SUPPOSEE.

        ⚠️⚠️ TROUVE PAR LE PIPELINE REEL, PAS PAR LA CONCEPTION. J'avais
        ecrit que le cas << aucun sinistre nulle part >> etait << exclu par
        construction >>, le refus amont l'ayant deja arrete.
        **C'etait faux** : `CalibrationImpossible` tire pendant
        l'AJUSTEMENT, donc APRES ce diagnostic. Le message publiait alors
        << le modele est CALIBRE (l'entrainement porte 0 sinistre) >> --
        une phrase que la ligne suivante du journal dementait.

          *Une articulation decrite dans une conception n'est pas une
          articulation tenue : c'est l'ordre d'execution qui decide.*
        """
        self.assertIsNone(
            _diag(sinistres_train=0.0, sinistres_test=0.0),
            "sans sinistre a l'entrainement, il n'y a pas de probleme "
            "d'EVALUATION : il n'y a pas de modele, et c'est "
            "`CalibrationImpossible` qui porte ce message-la")
        # ⚠️ et le cas voisin reste diagnostique : train garni, test vide
        self.assertIsNotNone(_diag(sinistres_train=400.0, sinistres_test=0.0))

    def test_ei_2_les_quatre_causes_sont_discriminees(self):
        """EI-2 : chaque cause a SES signaux, pas un fourre-tout."""
        cas = (
            ({'cible_vide_en_test': True, 'colonne_temporelle': 'annee',
                  'periode_test': (2023, 2023)}, CAUSE_CIBLE_NON_RENSEIGNEE),
            ({'n_train': 200, 'n_test': 50, 'sinistres_train': 5.0,
                  'colonne_temporelle': 'annee'}, CAUSE_PORTEFEUILLE_PETIT),
            ({'colonne_temporelle': 'annee_souscription',
                  'periode_train': (2019, 2022), 'periode_test': (2023, 2023)},
             CAUSE_TEST_PERIODE_RECENTE),
            ({}, CAUSE_DECOUPAGE_ALEATOIRE),
        )
        for surcharges, attendue in cas:
            with self.subTest(cause=attendue):
                self.assertEqual(_diag(**surcharges)['cause'], attendue)

    def test_ei_3_le_petit_portefeuille_PASSE_AVANT_la_periode_recente(self):
        """EI-3 : LA PRIORITE ARBITREE, et elle est actuarielle.

        ⚠️ Sous trois sinistres ATTENDUS, observer zero n'est PAS remarquable
        -- regle de trois. Accuser alors la sous-declaration serait une
        affirmation que la mesure ne porte pas. Au-dessus, zero DEVIENT
        remarquable et la cause temporelle reprend la main.
        """
        petit = _diag(n_train=200, n_test=50, sinistres_train=5.0,
                      colonne_temporelle='annee_souscription',
                      periode_train=(2019, 2022), periode_test=(2023, 2023))
        self.assertLess(petit['sinistres_attendus_test'],
                        SEUIL_REGLE_DE_TROIS)
        self.assertEqual(petit['cause'], CAUSE_PORTEFEUILLE_PETIT)
        # ⚠️ mais la cause temporelle n'est pas PERDUE : elle reste facteur
        self.assertIn(CAUSE_TEST_PERIODE_RECENTE, petit['facteurs'])

        gros = _diag(colonne_temporelle='annee_souscription',
                     periode_train=(2019, 2022), periode_test=(2023, 2023))
        self.assertGreaterEqual(gros['sinistres_attendus_test'],
                                SEUIL_REGLE_DE_TROIS)
        self.assertEqual(gros['cause'], CAUSE_TEST_PERIODE_RECENTE)

    def test_ei_4_le_nombre_attendu_est_PUBLIE_sans_seuil_invente(self):
        """EI-4 : arbitrage (B) -- on publie, on ne juge pas.

        Un Gini sur cinq sinistres est mesurable et ne vaut rien ; ce second
        seuil est un choix actuariel que ce module n'a pas a faire.
        """
        d = _diag(n_train=1000, n_test=250, sinistres_train=40.0)
        self.assertAlmostEqual(d['sinistres_attendus_test'], 10.0, places=6)
        self.assertIn('borne_regle_de_trois', d)
        self.assertAlmostEqual(d['borne_regle_de_trois'], 3 / 250, places=9)


class T2_CeQueLitLActuaire(unittest.TestCase):

    def test_ei_5_la_cause_est_NOMMEE_avec_les_chiffres_du_fichier(self):
        """EI-5 : (2) -- une cause sans chiffres n'est pas un diagnostic."""
        d = _diag(colonne_temporelle='annee_souscription',
                  periode_train=(2019, 2022), periode_test=(2023, 2023))
        msg = message_arbitrage_impossible(d, ['glm_tweedie', 'xgboost'])
        self.assertIn('annee_souscription', msg)
        self.assertIn('2019', msg)
        self.assertIn('2023', msg)
        self.assertIn('SOUS-DÉCLARÉ', msg)

    def test_ei_6_un_conseil_ACTIONNABLE_pour_chaque_cause(self):
        """EI-6 : (3) -- chaque conseil nomme un GESTE, pas une intention.

        ⚠️ Le controle cherche un VERBE D'ACTION. Un message qui dit
        seulement ce qui ne va pas laisse son lecteur devant un fichier
        qu'il ne sait pas corriger.
        """
        gestes = ('Vérifiez', 'Excluez', 'Ajoutez', 'évaluez', 'tarifez',
                  'fournissez', 'Relancez', 'Contrôlez')
        for surcharges in ({'cible_vide_en_test': True},
                           {'n_train': 200, 'n_test': 50, 'sinistres_train': 5.0},
                           {'colonne_temporelle': 'annee_souscription',
                                'periode_test': (2023, 2023)},
                           {}):
            d = _diag(**surcharges)
            conseil = conseil_actionnable(d)
            with self.subTest(cause=d['cause']):
                self.assertTrue(
                    any(g.lower() in conseil.lower() for g in gestes),
                    f"conseil sans geste actionnable : {conseil}")

    def test_ei_7_le_message_dit_que_les_CALIBRATIONS_restent_valides(self):
        """EI-7 : la moitie qu'on oublie.

        ⚠️ Un actuaire qui lit << aucun tarif >> sans cette precision croit
        son travail perdu. Il ne l'est pas : c'est la SELECTION qui est
        refusee, pas la calibration.
        """
        msg = message_arbitrage_impossible(_diag(), ['glm_tweedie'])
        self.assertIn('CALIBRÉS', msg)
        self.assertIn('result_a3', msg)
        self.assertIn('SÉLECTION', msg)
        phrase = phrase_evaluation_impossible(_diag(), 'GLM')
        self.assertIn('CALIBRÉ', phrase)

    def test_ei_8_aucune_virgule_de_prose_n_est_mangee(self):
        """EI-8 : le defaut que la relecture de la sortie a trouve.

        ⚠️ Ma premiere version faisait `.replace(',', ' ')` sur la phrase
        ENTIERE pour transformer les separateurs de milliers : elle mangeait
        aussi les virgules du francais (<< la periode 2023  la plus
        recente >>). *Un remplacement global applique a une phrase corrige un
        chiffre et casse le texte autour.*
        """
        d = _diag(colonne_temporelle='annee_souscription',
                  periode_train=(2019, 2022), periode_test=(2023, 2023))
        msg = message_arbitrage_impossible(d, ['glm_tweedie'])
        self.assertIn('2023, la plus récente', msg)
        # ⚠️ LA SIGNATURE EXACTE DU DEFAUT, pas << des espaces doubles >> :
        # ma premiere version cherchait `'  '` apres avoir remplace les
        # sauts de ligne par des espaces -- elle accusait les paragraphes du
        # message. *Un controle doit viser la trace du defaut, pas une
        # consequence qu'il partage avec du texte parfaitement sain.*
        mange = re.search(r'\d {2,}[a-zà-ÿ]', msg)
        self.assertIsNone(
            mange, f"une virgule de prose a ete mangee : « {mange.group(0)} »"
            if mange else '')


class T3_LeRefus(unittest.TestCase):

    def test_ei_9_on_refuse_SEULEMENT_si_plus_rien_n_est_evaluable(self):
        """EI-9 : TOUS, pas AU MOINS UN.

        Refuser des qu'un agent trebuche interdirait des arbitrages
        parfaitement fondes ; ne jamais refuser laisserait choisir sur des
        notes fabriquees.
        """
        self.assertTrue(doit_refuser_arbitrage([{'c': 1}] * 3, [1, 2, 3]))
        self.assertFalse(doit_refuser_arbitrage([{'c': 1}], [1, 2, 3]))
        self.assertFalse(doit_refuser_arbitrage([], [1, 2, 3]))
        self.assertFalse(doit_refuser_arbitrage([], []),
                         "sans aucune source, ce n'est pas CE refus-ci")

    def test_ei_10_ArbitrageImpossible_est_un_ValueError(self):
        """EI-10 : le contrat de TYPE, comme `CalibrationImpossible`.

        ⚠️ A6 levait deja `ValueError` sur catalogue vide : un appelant qui
        filtre `except ValueError` doit continuer de fonctionner. On
        enrichit le message, on ne deplace pas le type.
        """
        self.assertTrue(issubclass(ArbitrageImpossible, ValueError))

    def test_ei_11_A6_APPELLE_la_decision_et_LEVE(self):
        """EI-11 : L'ASSIETTE -- la decision est-elle CABLEE dans A6 ?

        ⚠️ Les controles ci-dessus eprouvent une fonction pure. Rien ne
        prouverait qu'A6 s'en sert : une decision correcte que personne
        n'appelle est du decor. Mesure par AST sur le corps d'A6.

        ⚠️⚠️ CE CONTROLE A D'ABORD ETE DU DECOR, ET LE SCEAU L'A MONTRE.
        Il cherchait la PRESENCE d'un appel a `doit_refuser_arbitrage` et
        d'un `raise ArbitrageImpossible`. La violation plantee
        `if False and doit_refuser_arbitrage(...)` les laisse tous les deux
        dans le texte : le controle restait VERT alors que le refus ne
        pouvait plus tirer.

          *Une MENTION n'est pas un APPEL -- et un appel dans une condition
          morte n'est pas un usage.*

        Il verifie desormais la STRUCTURE : un `if` dont le test EST
        l'appel, et dont le corps porte le `raise`.
        """
        from direction_non_vie.tarification.a6_comparaison import agent as A6
        source = textwrap.dedent(inspect.getsource(A6.AgentA6Comparaison))
        arbre = ast.parse(source)

        gardes = []
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.If):
                continue
            test = noeud.test
            if not (isinstance(test, ast.Call)
                    and (getattr(test.func, 'id', None)
                         or getattr(test.func, 'attr', None))
                    == 'doit_refuser_arbitrage'):
                continue
            leve = [n for n in ast.walk(noeud)
                    if isinstance(n, ast.Raise) and n.exc is not None
                    and 'ArbitrageImpossible' in ast.unparse(n.exc)]
            if leve:
                gardes.append(noeud.lineno)

        self.assertTrue(
            gardes,
            "A6 ne porte AUCUN `if doit_refuser_arbitrage(...)` dont le corps "
            "leve `ArbitrageImpossible`. Le refus est peut-etre mentionne, il "
            "n'est pas CABLE : un appel enferme dans une condition morte "
            "laisse l'arbitrage se faire sur des notes fabriquees.")


class T4_LaSourceUnique(unittest.TestCase):

    def test_ei_12_les_trois_agents_lisent_LA_MEME_colonne_temporelle(self):
        """EI-12 : la liste vivait TRIPLEE.

        ⚠️ Le diagnostic NOMME la colonne qui a servi au decoupage. S'il en
        devine une quatrieme copie, il nommera la mauvaise le jour ou une
        liste derive. Les trois agents appellent desormais la meme fonction.
        """
        for module in ('a3_glm', 'a4_ml', 'a5_deep_learning'):
            chemin = (pathlib.Path(__file__).resolve().parent / module
                      / 'agent.py')
            source = chemin.read_text(encoding='utf-8')
            with self.subTest(agent=module):
                self.assertIn(
                    'colonne_temporelle(', source,
                    f"{module} ne passe pas par la source unique")
                self.assertNotIn(
                    "'date_souscription', 'annee', 'year'", source,
                    f"{module} porte encore sa copie de la liste")
        self.assertEqual(colonne_temporelle(['x', 'annee', 'year']), 'annee')
        self.assertEqual(
            colonne_temporelle(['year', 'annee_souscription']),
            'annee_souscription', "l'ORDRE de priorite n'est pas respecte")
        self.assertIsNone(colonne_temporelle(['a', 'b']))
        self.assertIsNone(colonne_temporelle(None))
        self.assertEqual(len(COLONNES_TEMPORELLES), 4)

    def test_ei_13_les_trois_agents_PUBLIENT_le_diagnostic(self):
        """EI-13 : publie dans le RESULTAT, pas seulement journalise.

        Un avertissement au journal n'atteint personne -- c'est le defaut
        que cet audit poursuit depuis le premier jour.
        """
        for module in ('a3_glm', 'a4_ml', 'a5_deep_learning'):
            chemin = (pathlib.Path(__file__).resolve().parent / module
                      / 'agent.py')
            source = chemin.read_text(encoding='utf-8')
            with self.subTest(agent=module):
                self.assertIn("'diagnostic_evaluation'", source,
                              f"{module} ne publie pas son diagnostic")


if __name__ == '__main__':
    unittest.main(verbosity=2)
