# -*- coding: utf-8 -*-
"""LE PARAMETRE ECRASAIT L'EXPOSITION DU CONTRAT, EN SILENCE (G.17).

`tarifer()` construisait sa ligne par ``{**contrat, plan.exposition:
exposition}`` : le parametre est pose APRES le contrat, donc il l'ECRASE. Et
comme il valait ``1.0`` par defaut, << l'appelant a passe 1,0 >> et
<< l'appelant n'a rien passe >> etaient LE MEME CAS.

Mesure du 05/09/2026, sur la fixture `auto` :

    meme contrat, `exposition` declaree a 0,5
        tarifer(contrat)                 ->  1 649,30 EUR
        tarifer(contrat, exposition=0.5) ->    792,68 EUR
        rapport 2,0807 -- et `success: True` DANS LES DEUX CAS.

⚠️⚠️ CE LOT NE CHANGE AUCUN PRIX, ET C'EST LE POINT. Faire primer l'exposition
du contrat deplacerait le prix d'un facteur 2 sur tout contrat infra-annuel :
**cette decision n'est pas prise**. L'appelant continue de primer ; ce qui
change, c'est que le conflit est DIT et que la duree retenue est PUBLIEE.
*On rend d'abord visible ; on decide ensuite.*

Arbitrage de Selasse, 05/09/2026 : << valeur par defaut d'un an, toujours
declaree explicitement dans le resultat, jamais en silence >>.

Ce que cette sentinelle exige :
  EX-1  le defaut du parametre est `None`, pas `1.0` -- sans quoi les deux
        cas restent indiscernables ;
  EX-2  la duree RETENUE et sa SOURCE sont publiees a chaque tarification ;
  EX-3  deux sources qui DIFFERENT sont declarees, avec le rapport ;
  EX-4  une exposition de contrat IGNOREE par le defaut est declaree ;
  EX-5  aucune source -> un an, DIT ;
  EX-6  quand il n'y a rien a signaler, la phrase est `None` ;
  EX-7  ⚠️ AUCUN PRIX NE BOUGE -- les quatre cas rendent exactement ce que
        le code rendait avant ce lot ;
  EX-8  une exposition ILLISIBLE ne passe pas pour une mesure.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import inspect
import logging
import os
import sys
import unittest
import warnings

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import numpy as np

from core.conformite_reglementaire import (
    EXPO_ANNUELLE,
    EXPO_DE_L_APPELANT,
    EXPO_DU_CONTRAT,
    EXPO_SUPPOSEE,
    source_exposition,
)

#: ⚠️ LES PRIX D'AVANT LE LOT, MESURES SUR HEAD. Ils sont ecrits ici EN DUR
#: parce que c'est leur role : ce sont les temoins de la condition (4). Si le
#: modele change, ce test doit tomber et etre re-mesure -- pas ajuste.
_PRIME_UN_AN = 1649.30
_PRIME_SIX_MOIS = 792.68


class TestLaPrimitive(unittest.TestCase):

    def test_EX3_deux_sources_qui_DIFFERENT_sont_declarees(self):
        valeur, source, phrase = source_exposition(0.5, 1.0)
        self.assertEqual(valeur, 1.0, "ce n'est plus l'appelant qui prime : "
                                      'le prix a bouge')
        self.assertEqual(source, EXPO_DE_L_APPELANT)
        self.assertTrue(phrase)
        self.assertIn('DIFFERENT', phrase)
        self.assertIn('0.5', phrase)
        self.assertIn('2', phrase, 'le rapport des deux primes manque')

    def test_EX4_CAS_A_le_contrat_declare_donc_on_le_PREND(self):
        """⚠️⚠️ LE CONTRAT CHANGE LE 05/09/2026, ET C'EST UN PRIX.

        L'appelant se tait, le contrat declare une duree : le silence veut
        desormais dire << prends celle du contrat >>, jamais << un an >>.
        L'ancien comportement remplacait **une valeur qu'on a** par un
        litteral -- le motif que ce chantier ferme partout ailleurs.

        ⚠️ ET IL N'Y A RIEN A SIGNALER : aucune hypothese n'a ete faite.
        *Une phrase qui s'affiche toujours ne se lit plus.*
        """
        for declaree in (0.5, 0.25, 0.75, 1.0):
            with self.subTest(exposition=declaree):
                valeur, source, phrase = source_exposition(declaree, None)
                self.assertEqual(valeur, declaree)
                self.assertEqual(source, EXPO_DU_CONTRAT)
                self.assertIsNone(
                    phrase,
                    'une exposition PRISE au contrat ne suppose rien : elle '
                    'n a pas a se declarer comme une hypothese')

    def test_EX4b_CAS_A_aucune_ANNEE_n_est_supposee_a_la_place(self):
        """Le second sens, et c'est lui qui prouve le changement : la valeur
        retenue n'est plus jamais `EXPO_ANNUELLE` quand le contrat parle."""
        for declaree in (0.1, 0.5, 0.9, 2.0):
            with self.subTest(exposition=declaree):
                valeur, source, _ = source_exposition(declaree, None)
                self.assertNotEqual(
                    (valeur, source), (EXPO_ANNUELLE, EXPO_SUPPOSEE),
                    f'le contrat declare {declaree} et le systeme suppose '
                    f'quand meme une annee : le cas (a) est rouvert')

    def test_EX4c_CAS_B_une_duree_NULLE_ou_NEGATIVE_n_est_pas_une_duree(self):
        """⚠️⚠️ LE CAS DEGENERE QUE LE CAS (a) A FAIT APPARAITRE. Tant que le
        silence valait << un an >>, un `exposition: 0` declare au contrat
        etait remplace par 1,0 sans consequence visible. Depuis que le contrat
        est PRIS, le meme zero produirait **une prime nulle publiee comme un
        prix**. *Changer qui decide d'une valeur change ce qu'une valeur
        absurde coute.*"""
        for absurde in (0, 0.0, -0.5, -1):
            with self.subTest(exposition=absurde):
                valeur, source, phrase = source_exposition(absurde, None)
                self.assertEqual(valeur, EXPO_ANNUELLE)
                self.assertEqual(source, EXPO_SUPPOSEE)
                self.assertIn('PAS UTILISABLE', phrase)
                self.assertIn('NON FOURNIE', phrase)

    def test_EX5_aucune_source_donne_un_an_ET_LE_DIT(self):
        """⚠️ CAS (b) — la seule hypothese qui reste, et elle est nommee."""
        valeur, source, phrase = source_exposition(None, None)
        self.assertEqual(valeur, EXPO_ANNUELLE)
        self.assertEqual(source, EXPO_SUPPOSEE)
        self.assertIn('NON FOURNIE', phrase)
        self.assertIn('hypothese', phrase.lower())
        # ⚠️ Et elle DIT que l'hypothese ne porte pas que sur la duree : sur un
        # plan qui derive un facteur de l'exposition, le prix ne se corrige
        # pas en le multipliant par la duree reelle.
        self.assertIn('profil de risque', phrase)

    def test_EX6_rien_a_signaler_rend_None(self):
        """*Une phrase qui s'affiche toujours ne se lit plus.*"""
        for contrat, appelant, source_attendue in (
                (1.0, None, EXPO_DU_CONTRAT),      # accord implicite
                (0.5, 0.5, EXPO_DE_L_APPELANT),    # accord explicite
                (None, 0.5, EXPO_DE_L_APPELANT)):  # une seule source
            with self.subTest(contrat=contrat, appelant=appelant):
                _, source, phrase = source_exposition(contrat, appelant)
                self.assertIsNone(phrase)
                self.assertEqual(source, source_attendue)

    def test_EX8_une_exposition_ILLISIBLE_ne_passe_pas_pour_une_mesure(self):
        """⚠️ `True` vaut 1 en Python. Sans le controle de type, un booleen
        serait pris pour une duree d'un an -- et il ne signalerait rien."""
        for illisible in ('un an', True, None, [], {}):
            with self.subTest(valeur=illisible):
                valeur, source, phrase = source_exposition(illisible, None)
                self.assertEqual(valeur, EXPO_ANNUELLE)
                self.assertEqual(source, EXPO_SUPPOSEE)
                self.assertIn('NON FOURNIE', phrase,
                              'une exposition illisible a ete prise pour une '
                              'declaration')


class TestTariferLaPublie(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        from direction_non_vie.tarification import test_pipeline_agents as T
        from direction_non_vie.tarification.pipeline_tarifaire import (
            pipeline_complet,
        )
        np.random.seed(7)
        cls.plan = T._PLAN_AUTO
        cls.col = cls.plan.exposition
        donnees = T._portefeuille_auto(1200)
        cls.tarif = pipeline_complet(donnees, cls.plan)
        cls.contrat = donnees.iloc[0].to_dict()

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_EX1_le_defaut_du_parametre_est_None_pas_1_0(self):
        """⚠️⚠️ SANS CELA, RIEN N'EST MESURABLE. Avec `exposition: float =
        1.0`, << l'appelant a passe 1,0 >> et << l'appelant n'a rien passe >>
        sont le meme appel : aucun code ne peut les distinguer, donc aucune
        declaration ne peut etre juste."""
        signature = inspect.signature(self.tarif.tarifer)
        self.assertIsNone(signature.parameters['exposition'].default,
                          "le defaut est revenu a une valeur : les deux cas "
                          'redeviennent indiscernables')

    def test_EX2_la_duree_retenue_et_sa_SOURCE_sont_publiees(self):
        """*Une prime sans sa duree n'est pas contestable : 1 649,30 EUR pour
        un an et 792,68 pour six mois sont le MEME tarif.*"""
        for kwargs in ({}, {'exposition': 0.5}):
            with self.subTest(**kwargs):
                r = self.tarif.tarifer(dict(self.contrat), **kwargs)
                self.assertTrue(r['success'])
                self.assertIn('exposition_retenue', r)
                self.assertIn('exposition_source', r)
                self.assertIn('exposition_hypothese', r)

    def test_EX7_LE_PRIX_DE_CHAQUE_CAS_EST_CELUI_DE_SA_SOURCE(self):
        """⚠️⚠️ CE TEST A CHANGE DE CONTRAT LE 05/09/2026, ET IL LE DIT.

        Il s'appelait `EX7_AUCUN_PRIX_NE_BOUGE` et figeait le comportement
        d'alors : << contrat 0,5, rien passe >> valait **une annee entiere**.
        Le cas (a) etant arbitre, ce meme appel rend desormais la duree
        DECLAREE -- c'est le changement, pas un accident.

        ⚠️ Ce qui NE bouge pas, et qui est mesure ailleurs : **aucun prix de
        PRODUCTION**. Le seul appelant de `tarifer()` du depot
        (`demos/fremtpl2_demo.py:171`, releve par AST) passe deja
        `exposition=`, donc il est dans le cas (c), inchange. Voir `PA-*`.

        *Un test qui garde son ancien nom apres un changement de contrat fait
        croire que rien n'a change.*
        """
        sans_expo = {k: v for k, v in self.contrat.items() if k != self.col}
        cas = (
            # (a) le contrat declare, l'appelant se tait -> LA DUREE DECLAREE
            ('contrat 0,5 · rien passe', {**self.contrat, self.col: 0.5}, {},
             _PRIME_SIX_MOIS),
            # (c) l'appelant prime, dans les deux sens -- INCHANGE
            ('contrat 0,5 · parametre 1,0', {**self.contrat, self.col: 0.5},
             {'exposition': 1.0}, _PRIME_UN_AN),
            ('contrat 0,5 · parametre 0,5', {**self.contrat, self.col: 0.5},
             {'exposition': 0.5}, _PRIME_SIX_MOIS),
            # (b) personne ne declare -> une annee, et c'est DIT
            ('aucune source', sans_expo, {}, _PRIME_UN_AN),
        )
        for nom, contrat, kwargs, attendu in cas:
            with self.subTest(cas=nom):
                r = self.tarif.tarifer(contrat, **kwargs)
                self.assertAlmostEqual(
                    r['prime_pure'], attendu, places=2,
                    msg=f'{nom} : le prix n est pas celui de sa source.')

    def test_EX7b_le_cas_b_est_le_SEUL_qui_suppose_encore_une_annee(self):
        """⚠️ L'asymetrie qui prouve que (a) et (b) sont bien distincts : le
        MEME contrat, avec et sans sa colonne d'exposition."""
        sans_expo = {k: v for k, v in self.contrat.items() if k != self.col}
        avec = self.tarif.tarifer({**self.contrat, self.col: 0.5})
        sans = self.tarif.tarifer(sans_expo)
        self.assertEqual(avec['exposition_source'], EXPO_DU_CONTRAT)
        self.assertIsNone(avec['exposition_hypothese'])
        self.assertEqual(sans['exposition_source'], EXPO_SUPPOSEE)
        self.assertIsNotNone(
            sans['exposition_hypothese'],
            "le cas (b) suppose une annee SANS le dire : c'est la garantie "
            "que Selasse a explicitement demandee")
        self.assertGreater(sans['prime_pure'], avec['prime_pure'])

    def test_EX3b_le_conflit_atteint_le_RESULTAT_de_tarifer(self):
        r = self.tarif.tarifer({**self.contrat, self.col: 0.5},
                               exposition=1.0)
        self.assertEqual(r['exposition_source'], EXPO_DE_L_APPELANT)
        self.assertIn('DIFFERENT', r['exposition_hypothese'])

    def test_EX4d_CAS_A_la_duree_du_contrat_atteint_le_RESULTAT(self):
        """⚠️ Il verifiait que le cas silencieux publiait << IGNOREE >>. Cette
        branche n'existe plus : le contrat est PRIS."""
        r = self.tarif.tarifer({**self.contrat, self.col: 0.5})
        self.assertEqual(r['exposition_retenue'], 0.5)
        self.assertEqual(r['exposition_source'], EXPO_DU_CONTRAT)
        self.assertIsNone(r['exposition_hypothese'])

    def test_EX4e_CAS_B_une_duree_ABSURDE_ne_produit_pas_un_prix_NUL(self):
        """⚠️⚠️ Le garde-fou apparu avec le cas (a) : sans lui,
        `exposition: 0` publierait une prime de zero euro comme un prix."""
        r = self.tarif.tarifer({**self.contrat, self.col: 0})
        self.assertTrue(r['success'])
        self.assertEqual(r['exposition_retenue'], EXPO_ANNUELLE)
        self.assertEqual(r['exposition_source'], EXPO_SUPPOSEE)
        self.assertIn('PAS UTILISABLE', r['exposition_hypothese'])
        self.assertGreater(r['prime_pure'], 0.0,
                           'une exposition nulle a produit un prix NUL')

    def test_EX6b_un_contrat_annuel_sans_parametre_ne_signale_RIEN(self):
        r = self.tarif.tarifer({**self.contrat, self.col: 1.0})
        self.assertIsNone(r['exposition_hypothese'])
        self.assertEqual(r['exposition_source'], EXPO_DU_CONTRAT)

    def test_EX2b_un_contrat_REFUSE_ne_pretend_pas_avoir_une_duree(self):
        """⚠️ Le chemin d'echec ne doit pas publier une duree retenue : rien
        n'a ete tarife. *Une cle presente sur un refus se lirait comme un
        resultat.*"""
        r = self.tarif.tarifer({**self.contrat, 'age': 'illisible'})
        if not r['success']:
            self.assertNotIn('exposition_retenue', r,
                             'un contrat NON TARIFABLE publie une duree '
                             'retenue : il n y a pourtant aucun prix')


if __name__ == '__main__':
    unittest.main(verbosity=2)
