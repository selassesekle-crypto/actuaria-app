# -*- coding: utf-8 -*-
"""ON VALIDE SUR 80/20, ON PUBLIAIT LE MODELE DES 80 % (lot 13).

A3 decoupe son portefeuille en 80 % d'apprentissage et 20 % de holdout
(`TRAIN_SIZE = 0.80`, split TEMPOREL quand une colonne de date existe). Le
holdout sert a MESURER une performance sur des lignes que le modele n'a pas
vues -- c'est sa raison d'etre.

⚠️⚠️ MAIS LE MODELE PUBLIE ETAIT CELUI DES 80 %. Les relativites qu'un
actuaire lit, et qu'A6 compare, etaient estimees **en jetant un cinquieme du
portefeuille**. Mesure du 05/09/2026, fixture `auto` 2 500 contrats :

    jeune_conducteur     2,5125  ->  2,2975   (-8,56 %)
    log_valeur_venale    0,5475  ->  0,4979   (-9,06 %)
    antecedents_n1       0,4771  ->  0,4921   (+3,14 %)

*Le holdout sert a mesurer une performance, pas a amputer le modele qu'on
livre.*

Ce que cette sentinelle exige :
  MP-1  les TROIS moteurs publient un modele de production, sur 100 % de
        LEUR assiette -- frequence et prime pure sur le portefeuille,
        severite sur les seuls sinistres ;
  MP-2  ⚠️ MEME SPECIFICATION, ASSIETTE DIFFERENTE : les memes variables,
        des coefficients re-estimes. La selection n'est PAS refaite -- elle a
        ete validee sur un jeu non vu, et la refaire ici la priverait de cette
        garantie ;
  MP-3  ⚠️⚠️ LES METRIQUES NE SUIVENT PAS. `gini`, `rmse_test` et
        `overfit_ratio` restent ceux du modele de VALIDATION : les recalculer
        sur le modele de production serait les mesurer sur des lignes qu'il a
        vues. *Deux modeles, deux assiettes -- leurs chiffres ne se melangent
        pas* ;
  MP-4  ⚠️ `modele` RESTE celui de validation. Le CANN s'y ancre (lot 7), A6
        s'en sert : le substituer deplacerait des choses qu'aucune decision ne
        couvre. Le modele de production S'AJOUTE ;
  MP-5  les deux assiettes sont PUBLIEES -- sans elles, deux jeux de
        coefficients cote a cote ne se distinguent pas ;
  MP-6  un re-ajustement qui echoue ne casse rien et se DIT : l'absence est
        publiee, jamais une egalite supposee entre les deux assiettes ;
  MP-7  ⚠️ AUCUN EURO NE BOUGE : l'ajout est additif, le tarif est identique.

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

#: Les trois moteurs. ⚠️ Les trois, pas un : ne re-ajuster qu'un seul ferait
#: croire les trois comparables alors qu'ils ne le seraient plus.
_MOTEURS = ('poisson', 'gamma', 'tweedie')


class TestLeModeleDeProduction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        from core.qualite_donnees import preambule_qualite
        from direction_non_vie.tarification import test_pipeline_agents as T
        from direction_non_vie.tarification.a1_ingestion.agent import (
            AgentA1Ingestion,
        )
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        np.random.seed(7)
        cls.plan = T._PLAN_AUTO
        base = {'audit_path': '/tmp', 'verbose': False}
        r1 = AgentA1Ingestion(**base).run(
            branche='non_vie', sous_branche='auto',
            dataframe=T._portefeuille_auto(2500))
        q = preambule_qualite(r1.get('dataframe'), cls.plan,
                              qualite_validee_par='Test', horodatage=None)
        r2 = AgentA2Preprocessing(**base).run(
            result_a1={**r1, 'dataframe': q.dataframe_propre}, plan=cls.plan)
        cls.r3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp').run(
            result_a2=r2, plan=cls.plan,
            col_frequence=cls.plan.cible_frequence,
            col_cout=cls.plan.cible_cout, generer_graphiques=False)
        cls.met = cls.r3.get('metriques') or {}

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_MP1_MP5_les_TROIS_moteurs_publient_les_DEUX_assiettes(self):
        for moteur in _MOTEURS:
            with self.subTest(moteur=moteur):
                m = self.met.get(moteur) or {}
                self.assertTrue(m, f'{moteur} absent')
                for cle in ('relativites_production', 'n_obs_validation',
                            'n_obs_production'):
                    self.assertIn(cle, m, f'{moteur} ne publie pas {cle!r}')
                self.assertGreater(
                    m['n_obs_production'], m['n_obs_validation'],
                    f"{moteur} : l'assiette de production n'est pas plus "
                    f"large que celle de validation -- le re-ajustement n'a "
                    f'pas eu lieu')

    def test_MP2_MEME_specification_coefficients_DIFFERENTS(self):
        """⚠️⚠️ LE COEUR DU LOT. Memes variables (la selection n'est pas
        refaite), coefficients re-estimes sur plus de donnees. *Si les
        coefficients etaient identiques, le re-ajustement n'aurait pas eu
        lieu ; si les variables differaient, la selection aurait ete refaite
        sur un jeu que le modele a vu.*"""
        for moteur in _MOTEURS:
            with self.subTest(moteur=moteur):
                m = self.met.get(moteur) or {}
                validation = m.get('relativites') or {}
                production = m.get('relativites_production') or {}
                # ⚠️⚠️ PAS DE `continue` ICI, ET LE SCEAU L'A EXIGE. Ma
                # premiere version sautait quand `production` etait vide :
                # les plants qui VIDAIENT les relativites de production de
                # Gamma et de Tweedie restaient donc MUETS. *Un controle qui
                # s'abstient sur le cas qu'il devait detecter atteste sans
                # surveiller.*
                #   Un moteur qui n'a retenu AUCUNE variable a legitimement
                #   deux jeux vides ; c'est le seul cas ou l'on passe.
                if not validation:
                    self.assertFalse(
                        production,
                        f'{moteur} : des relativites de PRODUCTION sans '
                        f'relativites de validation')
                    continue
                self.assertTrue(
                    production,
                    f'{moteur} : {len(validation)} relativites de validation '
                    f'mais AUCUNE de production -- le re-ajustement de ce '
                    f'moteur ne se fait pas, alors que les deux autres le '
                    f'font. C est l asymetrie entre voisins.')
                self.assertEqual(
                    sorted(production), sorted(validation),
                    f'{moteur} : la specification a change entre les deux '
                    f'assiettes -- la selection a ete refaite')
                ecarts = [abs(production[v]['relativite']
                              - validation[v]['relativite'])
                          for v in validation if v in production]
                self.assertTrue(
                    any(e > 1e-9 for e in ecarts),
                    f'{moteur} : coefficients IDENTIQUES sur 80 % et 100 % '
                    f'des donnees -- le re-ajustement ne fait rien')

    def test_MP3_les_METRIQUES_restent_celles_de_la_VALIDATION(self):
        """⚠️⚠️ Recalculer le Gini sur le modele de production, ce serait le
        mesurer sur des lignes qu'il a vues. Le holdout n'existe que parce
        que le modele ne l'a PAS vu."""
        for moteur in _MOTEURS:
            with self.subTest(moteur=moteur):
                m = self.met.get(moteur) or {}
                # ⚠️ Le nombre d'observations de TEST doit rester celui du
                # holdout : s'il valait `n_obs_production`, le Gini aurait
                # ete recalcule sur tout.
                if 'nb_obs_test' in m and m.get('n_obs_production'):
                    self.assertLess(
                        m['nb_obs_test'], m['n_obs_production'],
                        f'{moteur} : le jeu de test a la taille de la '
                        f'production -- les metriques ont fuite')

    def test_MP4_le_modele_RENDU_reste_celui_de_validation(self):
        """⚠️ Le CANN s'ancre sur `modeles['poisson']` (lot 7) et A6 s'en
        sert. Le substituer deplacerait des choses qu'aucune decision ne
        couvre : le modele de production S'AJOUTE, il ne remplace pas."""
        modeles = self.r3.get('modeles') or {}
        for moteur in _MOTEURS:
            with self.subTest(moteur=moteur):
                m = self.met.get(moteur) or {}
                modele = modeles.get(moteur)
                if modele is None or not m.get('n_obs_validation'):
                    continue
                n_ajuste = int(getattr(modele, 'nobs', 0) or 0)
                if n_ajuste:
                    self.assertEqual(
                        n_ajuste, m['n_obs_validation'],
                        f'{moteur} : le modele RENDU est ajuste sur '
                        f'{n_ajuste} lignes, soit l assiette de PRODUCTION. '
                        f'Le CANN et A6 recevraient un autre modele que '
                        f'celui sur lequel les metriques ont ete mesurees.')

    def test_MP6_un_reajustement_ABSENT_se_dit(self):
        """⚠️ `n_obs_production` vaut `None` quand le re-ajustement echoue --
        jamais l'assiette de validation, qui laisserait croire a une egalite
        des deux."""
        import inspect

        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        source = inspect.getsource(AgentA3GLM._calibrer_poisson)
        self.assertIn("if modele_production is not None else None", source,
                      "l'absence de re-ajustement ne se declare pas : "
                      "`n_obs_production` porterait un nombre alors que rien "
                      "n'a ete ajuste")

    def test_MP7_AUCUN_EURO_NE_BOUGE(self):
        """⚠️⚠️ LA CONDITION (4), DEVENUE CONTROLE. L'ajout est ADDITIF : le
        tarif du chemin signe est celui d'avant le lot, au centime."""
        from direction_non_vie.tarification import test_pipeline_agents as T
        from direction_non_vie.tarification.pipeline_tarifaire import (
            pipeline_complet,
        )
        np.random.seed(7)
        df = T._portefeuille_auto(2500)
        tarif = pipeline_complet(df, T._PLAN_AUTO)
        primes = np.asarray(
            tarif.predire_portefeuille(df)['prime_pure'], dtype=float)
        self.assertAlmostEqual(
            float(primes.sum()), 1993741.098588, places=2,
            msg='LE TARIF A BOUGE — le lot 13 ne devait rien deplacer : le '
                'chemin declaratif ajustait deja sur 100 %.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
