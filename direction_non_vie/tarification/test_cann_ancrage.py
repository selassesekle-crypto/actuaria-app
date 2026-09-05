# -*- coding: utf-8 -*-
"""LE CANN S'ANCRAIT SUR LE GLM D'UNE AUTRE CIBLE, ET SON CONTROLE DISAIT OK.

Un CANN (Wuthrich & Merz, 2019) n'est pas un reseau ordinaire : c'est un reseau
qui apprend un RESIDU au-dessus d'un GLM **gele**. Toute sa valeur en decoule --
interpretabilite (`INTERPRETABILITE['cann'] = 0.80`, justifie en toutes lettres
par << composante GLM visible >>), repli sur : si le reseau n'apprend rien, on
retombe exactement sur le GLM.

⚠️⚠️ IL S'ANCRAIT SUR `modeles['tweedie']`, QUELLE QUE SOIT SA CIBLE. Or
`pipeline_agents:482` ne lance le CANN que sur la FREQUENCE -- une cible de
COMPTAGE, avec offset log-exposition -- tandis que le Tweedie d'A3 vise
`prime_pure`, un taux deja annualise dont la docstring d'A3 interdit l'offset
(<< l'appliquer DEUX FOIS >>). Le reseau partait donc des coefficients d'un
modele d'une autre cible, sur une autre echelle.

    Mesure du 05/09/2026, fixture `auto`, 2 500 contrats, cible nb_sinistres :

                                    AVANT       APRES
        CANN -- Gini                0,0615      0,1908
        CANN -- score global        0,4483      0,9329
        CANN -- rang                8e / 9      3e / 9
        variables appariees         5           7
        GLM Poisson (SA cible)      0,1912      0,1912
        ecart CANN / son GLM        68 %        0,2 %

*Un CANN correctement ancre EGALE son GLM a l'epoque 0 et ne peut que s'en
ecarter en s'ameliorant. Trois fois moins de pouvoir discriminant que le GLM
seul etait la signature d'un ancrage faux.*

⚠️⚠️ ET LE CONTROLE DE FIDELITE NE POUVAIT PAS LE VOIR. Il comparait la
prediction du reseau a `exp(X @ w_init + bias_init + offset)` -- une
reconstruction faite avec LES MEMES `w_init`/`bias_init` qu'on venait
d'injecter. Il verifiait donc que `nn.Linear` fait une multiplication
matricielle. Mesure avant correction : `glm_verification_error = 1e-06`,
`glm_gele = True`, 5 variables sur 5, **aucune alerte** -- sur un ancrage faux.

  *Un controle qui se compare a son propre point de depart atteste sans
  surveiller.*

⚠️ LE MODELE DE PRODUCTION NE CHANGE PAS : GLM_POISSON reste premier (0,9725
contre 0,9329). Le motif d'arret prevu par la feuille de route ne s'est pas
declenche -- et il a ete MESURE, pas suppose.

Ce que cette sentinelle exige :
  CN-1  le CANN s'ancre sur le GLM de SA cible, jamais sur une famille codee ;
  CN-2  le nom du GLM ancre et SA cible sont PUBLIES ;
  CN-3  un ancrage hors cible leve une alerte -- test BINAIRE, aucun seuil ;
  CN-4  le Gini du CANN a l'epoque 0 et celui du GLM ancre sont publies
        COTE A COTE, sans seuil : l'actuaire juge ;
  CN-5  l'appariement cible -> famille DERIVE de `glm_de_reference` ;
  CN-6  second sens : ancrage correct -> aucune alerte hors cible ;
  CN-7  ⚠️ LE CONSTAT, DEVENU CONTROLE : le CANN ancre a un Gini du MEME
        ORDRE que son GLM. C'est ce qui etait faux, et c'est mesurable ;
  CN-8  l'alerte existante `cann_glm_non_ancre` continue de mordre.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
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

from core.conformite_reglementaire import glm_de_reference


class TestLAppariementDerive(unittest.TestCase):
    """⚠️ Ces tests ne lancent aucun reseau : ils verifient la REGLE."""

    def test_CN5_l_appariement_vient_de_glm_de_reference(self):
        """⚠️⚠️ *Une seconde table d'appariement divergerait de la premiere.*
        A4, A6 et le classement utilisent deja cette fonction ; le CANN devait
        la rejoindre au lieu de coder `'tweedie'`."""
        metriques = {
            'poisson': {'cible': 'nb_sinistres', 'gini': 0.1912},
            'gamma':   {'cible': 'cout_moyen',   'gini': 0.05},
            'tweedie': {'cible': 'prime_pure',   'gini': 0.1901},
        }
        self.assertEqual(glm_de_reference(metriques, 'nb_sinistres')[0],
                         'poisson')
        self.assertEqual(glm_de_reference(metriques, 'prime_pure')[0],
                         'tweedie')
        self.assertEqual(glm_de_reference(metriques, 'cout_moyen')[0], 'gamma')
        # ⚠️ Et une cible sans GLM ne rend PAS un repli : elle rend l'absence.
        self.assertEqual(glm_de_reference(metriques, 'inconnue'), (None, None))

    def test_CN3_LE_PREMIER_SENS_un_ancrage_hors_cible_LEVE_l_alerte(self):
        """⚠️⚠️ CE TEST EXISTE PARCE QUE LE SCEAU L'A EXIGE. Le plant qui
        DESACTIVAIT l'alerte restait MUET : la sentinelle ne verifiait que le
        cas << aucune alerte quand tout va bien >>, donc supprimer l'alerte ne
        pouvait pas la faire rougir.

        > *Un garde-fou dont on ne teste qu'un sens n'est verifie qu'a moitie.*

        Ici : le CANN modelise `nb_sinistres`, il est ancre sur un GLM dont la
        cible est `prime_pure` -- exactement l'etat du depot avant ce lot.
        """
        from core.conformite_reglementaire import alerte_ancrage_hors_cible
        alerte = alerte_ancrage_hors_cible(
            {'glm_gele': True, 'glm_ancre': 'tweedie',
             'cible_glm_ancre': 'prime_pure'}, 'nb_sinistres')
        self.assertIsNotNone(
            alerte, "un CANN de comptage ancre sur le GLM de la prime pure ne "
                    'leve AUCUNE alerte')
        self.assertEqual(alerte['code'], 'cann_ancre_hors_cible')
        self.assertEqual(alerte['severite'], 'AMBRE')
        for attendu in ('tweedie', 'prime_pure', 'nb_sinistres'):
            self.assertIn(attendu, alerte['message'],
                          f"l'alerte ne nomme pas {attendu!r} : elle ne dit "
                          'pas ce qui est ancre sur quoi')

    def test_CN3b_LE_SECOND_SENS_trois_cas_qui_ne_doivent_RIEN_dire(self):
        """⚠️ Une alerte qui tirerait aussi sur un ancrage correct serait du
        bruit, et l'actuaire cesserait de la lire."""
        from core.conformite_reglementaire import alerte_ancrage_hors_cible
        cas = {
            'cibles concordantes': (
                {'glm_gele': True, 'glm_ancre': 'poisson',
                 'cible_glm_ancre': 'nb_sinistres'}, 'nb_sinistres'),
            # ⚠️ Non ancre : `cann_glm_non_ancre` couvre deja ce cas. Deux
            # alertes pour un fait unique se contrediraient un jour.
            'CANN non ancre': (
                {'glm_gele': False, 'cible_glm_ancre': 'prime_pure'},
                'nb_sinistres'),
            'cible inconnue': (
                {'glm_gele': True, 'cible_glm_ancre': None}, 'nb_sinistres'),
        }
        for nom, (met, cible) in cas.items():
            with self.subTest(cas=nom):
                self.assertIsNone(alerte_ancrage_hors_cible(met, cible))
        self.assertIsNone(alerte_ancrage_hors_cible(None, 'nb_sinistres'))

    def test_CN1_le_code_n_ancre_plus_sur_une_famille_ECRITE(self):
        """⚠️ Assiette : le CODE de `_calibrer_cann`, par AST -- pas la prose
        qui explique le correctif. *Un commentaire qui decrit un correctif
        n'est pas le correctif.*"""
        import ast
        chemin = os.path.join(_ICI, 'a5_deep_learning', 'agent.py')
        with open(chemin, encoding='utf-8') as f:
            arbre = ast.parse(f.read())
        fonction = next(
            (n for n in ast.walk(arbre)
             if isinstance(n, ast.FunctionDef) and n.name == '_calibrer_cann'),
            None)
        self.assertIsNotNone(fonction, '_calibrer_cann a disparu')
        corps = ast.unparse(ast.Module(body=fonction.body, type_ignores=[]))
        for famille in ("'tweedie'", '"tweedie"', "'poisson'", "'gamma'"):
            self.assertNotIn(
                f'.get({famille})', corps,
                f'`_calibrer_cann` ancre sur la famille {famille} ECRITE EN '
                f'DUR : elle doit venir de la cible, par `glm_de_reference`')
        self.assertIn('_reference_glm', corps,
                      "l'ancrage ne passe plus par l'appariement cible -> "
                      'famille')


class TestLeCANNAncreSurSaCible(unittest.TestCase):
    """⚠️⚠️ PAR EXECUTION. Un controle par AST ne verrait pas un ancrage
    construit a l'execution ; celui-ci calibre un vrai CANN et lit ce qu'il
    publie."""

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        try:
            import torch
        except ImportError:                                  # pragma: no cover
            raise unittest.SkipTest('torch absent : le CANN ne tourne pas')
        from core.qualite_donnees import preambule_qualite
        from direction_non_vie.tarification import test_pipeline_agents as T
        from direction_non_vie.tarification.a1_ingestion.agent import (
            AgentA1Ingestion,
        )
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        np.random.seed(7)
        import torch
        torch.manual_seed(7)
        plan = T._PLAN_AUTO
        cls.cible = plan.cible_frequence
        base = {'audit_path': '/tmp', 'verbose': False}
        # ⚠️⚠️ 2 500 CONTRATS, ET CE N'EST PAS UN DETAIL. Le sceau a montre que
        # sur 1 500, un CANN MAL ancre rend encore 0,1286 contre 0,1889 pour
        # son GLM -- 68 % : `CN-7` ne mordait pas. A 2 500, le meme defaut
        # donne 0,0615 contre 0,1912 -- 32 %, et il mord.
        #   *Un controle doit exercer la taille sur laquelle le constat a ete
        #   MESURE ; sur une fixture plus petite il atteste sans surveiller.*
        r1 = AgentA1Ingestion(**base).run(
            branche='non_vie', sous_branche='auto',
            dataframe=T._portefeuille_auto(2500))
        q = preambule_qualite(r1.get('dataframe'), plan,
                              qualite_validee_par='Test', horodatage=None)
        r2 = AgentA2Preprocessing(**base).run(
            result_a1={**r1, 'dataframe': q.dataframe_propre}, plan=plan)
        cls.r3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp').run(
            result_a2=r2, plan=plan, col_frequence=plan.cible_frequence,
            col_cout=plan.cible_cout, generer_graphiques=False)
        r4 = AgentA4ML(models_path='/tmp', audit_path='/tmp').run(
            result_a2=r2, result_a3=cls.r3, plan=plan, col_cible=cls.cible,
            ponderer_par_exposition=True, calcul_shap=False,
            generer_graphiques=False)
        cls.r5 = AgentA5DeepLearning(models_path='/tmp',
                                     audit_path='/tmp').run(
            result_a2=r2, result_a3=cls.r3, result_a4=r4, plan=plan,
            col_cible=cls.cible, modeles=('cann',), generer_graphiques=False)
        cls.met = (cls.r5.get('metriques') or {}).get('cann') or {}

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_CN2_le_GLM_ancre_est_NOMME_avec_sa_cible(self):
        """*Un controle qui atteste sans nommer son objet ne permet a personne
        de le contredire.* `glm_gele` disait SI, jamais SUR QUOI."""
        self.assertTrue(self.met, 'aucune metrique CANN')
        self.assertIn('glm_ancre', self.met)
        self.assertIn('cible_glm_ancre', self.met)
        self.assertEqual(self.met['glm_ancre'], 'poisson',
                         "le CANN de la frequence doit s'ancrer sur le GLM "
                         'Poisson, pas sur une autre famille')
        self.assertEqual(self.met['cible_glm_ancre'], self.cible)

    def test_CN3_CN6_aucune_alerte_hors_cible_quand_l_ancrage_est_JUSTE(self):
        """⚠️ Le second sens de CN-3 : une alerte qui tirerait aussi sur un
        ancrage correct serait du bruit."""
        codes = {a.get('code')
                 for a in (self.r5.get('alertes_modele') or [])}
        self.assertNotIn('cann_ancre_hors_cible', codes)
        self.assertNotIn('cann_glm_non_ancre', codes)

    def test_CN4_les_deux_GINIS_sont_publies_COTE_A_COTE(self):
        """⚠️ Sans seuil : on publie, l'actuaire juge -- meme regle que la
        puissance de selection (`G.4`)."""
        for cle in ('gini_cann_epoch0', 'gini_glm_ancre'):
            self.assertIn(cle, self.met, f'{cle} n est pas publie')
        self.assertIsNotNone(self.met['gini_glm_ancre'],
                             'le Gini du GLM ancre manque')

    def test_CN7_LE_CONSTAT_le_CANN_ancre_vaut_son_GLM(self):
        """⚠️⚠️ LE COEUR DU LOT, DEVENU CONTROLE.

        Un CANN ancre part EXACTEMENT du GLM : a l'epoque 0 leurs predictions
        coincident, donc leurs Ginis aussi. L'entrainement ne peut ensuite que
        s'en ecarter en s'ameliorant.

        Mesure : AVANT le correctif, 0,0615 contre 0,1912 -- **68 % d'ecart**.
        APRES : 0,1908 contre 0,1912 -- **0,2 %**.

        ⚠️ LE SEUIL DE CE TEST N'EST PAS UN SEUIL DE QUALITE : c'est un ordre
        de grandeur, et il a ete VERIFIE aux deux bornes plutot que choisi.

            ancrage JUSTE  (2 500)  ->  0,1908 / 0,1912 =  99,8 %
            ancrage FAUX   (2 500)  ->  0,0615 / 0,1912 =  32,2 %
            ancrage FAUX   (1 500)  ->  0,1286 / 0,1889 =  68,1 %   <- ne mord
                                                                        pas

        La moitie separe donc les deux etats A LA TAILLE OU LE CONSTAT A ETE
        MESURE. *Il separe un ancrage CASSE d'un ancrage qui tient, pas un bon
        modele d'un mauvais.*

        ⚠️⚠️ ET LA REFERENCE EST LE GLM DE LA CIBLE, PAS LE GLM ANCRE. Le
        sceau l'a exige : compare au GLM ANCRE, ce test devient TAUTOLOGIQUE --
        un CANN mal ancre sur le Tweedie serait juge par rapport au Tweedie,
        donc conforme a son propre defaut. *Le CANN modelise `nb_sinistres` :
        c'est au GLM de `nb_sinistres` qu'il doit se mesurer, quel que soit ce
        sur quoi quelqu'un a decide de l'ancrer.*
        """
        gini_cann = self.met.get('gini_test')
        _, met_cible = glm_de_reference(
            (self.r3 or {}).get('metriques'), self.cible)
        gini_glm = (met_cible or {}).get('gini')
        self.assertIsNotNone(gini_cann, 'le CANN ne publie pas de Gini')
        self.assertIsNotNone(
            gini_glm, f"aucun GLM d'A3 ne vise {self.cible} : ce test ne "
                      'mesure plus rien')
        self.assertGreater(
            gini_cann, gini_glm / 2,
            f"le CANN ancre rend un Gini de {gini_cann} la ou le GLM qui "
            f"l'ancre vaut {gini_glm}. Un CANN part de son GLM : un tel ecart "
            f"signifie que les coefficients geles ne sont pas les siens "
            f"-- c'est exactement le defaut du 05/09/2026 (0,0615 vs 0,1912).")

    def test_CN8_l_ancrage_a_bien_eu_lieu_et_toutes_les_vars_matchent(self):
        """⚠️ Sans ancrage, CN-7 serait vert pour la mauvaise raison : un
        reseau libre peut atteindre un bon Gini SANS etre un CANN."""
        self.assertTrue(self.met.get('glm_gele'),
                        "le CANN n'est pas ancre : ce n'est pas un CANN "
                        'Wuthrich, et CN-7 ne prouve alors rien')
        self.assertEqual(self.met.get('n_vars_glm_matchees'),
                         self.met.get('n_vars_glm_total'),
                         'des variables du GLM ne sont pas retrouvees dans '
                         "les features d'A5 : l'ancrage est partiel")
        self.assertGreater(self.met.get('n_vars_glm_total') or 0, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
