# -*- coding: utf-8 -*-
"""LA REFERENCE GLM SUIT LA CIBLE — LA BONNE MESURE DU MAUVAIS MODELE.

A4 et A5 comparent leurs modeles a un << GLM de reference >>. Ils lisaient
`metriques['poisson']` EN DUR, quelle que soit la cible comparee.

MESURE DU 05/09/2026, sur `col_cible='prime_pure'` :

  | ligne << GLM de reference >> | publie              | attendu (Tweedie) |
  |------------------------------|---------------------|-------------------|
  | libelle                      | GLM Poisson         | GLM Tweedie       |
  | Gini                         | 0,1912              | 0,1901            |
  | RMSE                         | **0,7141**          | non mesuree       |
  | ratio train/test             | 0,9702              | 0,5051            |

Le 0,7141 est une RMSE sur l'echelle du COMPTAGE ; les modeles ML de cette
cible ont des RMSE de l'ordre de **1 720**, sur l'echelle de la prime pure.
La ligne se classait #1 avec un chiffre qui ne se compare a rien. Et le
commentaire signe annoncait << Amelioration vs GLM : -5,9 % >> entre un Gini
de prime pure et un Gini de frequence.

  *La bonne mesure du mauvais modele reste une mauvaise reference.*

LA DERIVATION N'INVENTE AUCUNE TABLE. A3 declare lui-meme la cible de
chacune de ses familles (`metriques[f]['cible']` : Poisson sur la frequence,
Gamma sur `cout_moyen`, Tweedie sur `prime_pure`), et c'est deja la chaine
sur laquelle A6 apparie les modeles. Une seconde table divergerait.

Ce que cette sentinelle exige :
  RG-1  la derivation suit ce qu'A3 DECLARE, pas un nom code en dur ;
  RG-2  sans GLM de la cible, la reference est ABSENTE et le DIT, en nommant
        les cibles reellement disponibles ;
  RG-3  A4 sur `prime_pure` publie le TWEEDIE, avec SES chiffres ;
  RG-4  A4 sur `nb_sinistres` publie toujours le POISSON -- le correctif n'a
        pas tout bascule ;
  RG-5  le LIBELLE nomme le modele reellement relaye ;
  RG-6  aucun agent ne lit `metriques['poisson']` en dur ;
  RG-7  la cible du run est REINITIALISEE a chaque appel -- c'est le risque
        introduit par l'etat d'instance, il se surveille.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import ast
import logging
import os
import pathlib
import re
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
    glm_de_reference,
    phrase_reference_glm_absente,
)

_MET_A3 = {
    'poisson': {'cible': 'nb_sinistres', 'gini': 0.1912, 'rmse_test': 0.7141,
                'overfit_ratio': 0.9702},
    'gamma': {'cible': 'cout_moyen', 'gini': -0.0298, 'overfit_ratio': None},
    'tweedie': {'cible': 'prime_pure', 'gini': 0.1901, 'overfit_ratio': 0.5051},
}


class TestDerivation(unittest.TestCase):

    def test_RG1_la_reference_suit_la_cible_declaree_par_A3(self):
        for cible, attendu in (('nb_sinistres', 'poisson'),
                               ('cout_moyen', 'gamma'),
                               ('prime_pure', 'tweedie')):
            with self.subTest(cible=cible):
                nom, met = glm_de_reference(_MET_A3, cible)
                self.assertEqual(nom, attendu)
                self.assertEqual(met['cible'], cible)

    def test_RG1b_elle_ne_code_aucun_nom_en_dur(self):
        """⚠️ Si A3 renommait ses familles, la derivation devrait SUIVRE.
        Un test qui ne verifie que les trois noms connus passerait sur une
        table codee en dur -- celui-ci ne le peut pas."""
        invente = {'quasi_poisson': {'cible': 'nb_sinistres', 'gini': 0.2}}
        nom, met = glm_de_reference(invente, 'nb_sinistres')
        self.assertIsNone(nom, "la derivation ne connait que trois noms : "
                               "elle enumere au lieu de deriver")
        # ... et c'est un choix ASSUME : `MODELES_GLM` fixe les trois familles
        # d'A3. Le jour ou A3 en ajoute une, cette constante doit suivre --
        # ce test le rappellera par son echec.
        self.assertIsNone(met)

    def test_RG2_sans_GLM_de_la_cible_la_reference_est_absente_et_le_DIT(self):
        nom, met = glm_de_reference(_MET_A3, 'charge_ultime')
        self.assertIsNone(nom)
        self.assertIsNone(met)
        phrase = phrase_reference_glm_absente('charge_ultime', _MET_A3)
        self.assertIn('charge_ultime', phrase)
        for attendu in ("poisson ('nb_sinistres')", "gamma ('cout_moyen')",
                        "tweedie ('prime_pure')"):
            self.assertIn(attendu, phrase,
                          'la phrase ne nomme pas les cibles disponibles : '
                          "l'actuaire cherchera une panne la ou il manque un "
                          'ajustement')

    def test_RG2b_une_entree_sans_cible_ne_devient_pas_la_reference(self):
        sans = {'poisson': {'gini': 0.19}}      # aucune cible declaree
        self.assertEqual(glm_de_reference(sans, 'nb_sinistres'), (None, None))
        self.assertEqual(glm_de_reference(None, 'nb_sinistres'), (None, None))
        self.assertEqual(glm_de_reference(_MET_A3, ''), (None, None))


class TestAucunPoissonEnDur(unittest.TestCase):

    AGENTS = ('a4_ml/agent.py', 'a5_deep_learning/agent.py',
              'a6_comparaison/agent.py')

    def test_RG6_aucun_agent_ne_lit_metriques_poisson_en_dur(self):
        """⚠️ Au TEXTE, hors commentaires et hors chaines de documentation :
        un releve par AST ne verrait pas la difference entre une lecture et
        une mention, mais il ne verrait pas non plus une lecture ecrite
        autrement. Les deux se completent -- ici c'est la LECTURE qu'on
        traque, donc on retire les commentaires par AST puis on cherche."""
        motif = re.compile(r"""\[\s*['"]poisson['"]\s*\]"""
                           r"""|\.get\(\s*['"]poisson['"]""")
        fautes = []
        for relatif in self.AGENTS:
            chemin = os.path.join(_ICI, relatif)
            source = pathlib.Path(chemin).read_text(encoding='utf-8')
            arbre = ast.parse(source)
            # les intervalles de lignes occupes par une docstring
            docs = set()
            for n in ast.walk(arbre):
                if (isinstance(n, ast.Expr)
                        and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, str)):
                    docs.update(range(n.lineno, (n.end_lineno or n.lineno) + 1))
            for numero, ligne in enumerate(source.splitlines(), 1):
                if numero in docs or ligne.strip().startswith('#'):
                    continue
                if motif.search(ligne):
                    fautes.append(f'{relatif}:{numero} {ligne.strip()[:70]}')
        self.assertEqual(fautes, [],
                         'la famille de GLM est codee en dur :\n  '
                         + '\n  '.join(fautes))


class TestSurLaChaineReelle(unittest.TestCase):
    """⚠️⚠️ PAR EXECUTION. Le defaut ne se voit pas dans le code d'un site
    isole : il se voit dans ce que le classement PUBLIE."""

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
        donnees = T._portefeuille_auto(1500)
        cls.plan = T._PLAN_AUTO
        base = {'audit_path': '/tmp', 'verbose': False}
        r1 = AgentA1Ingestion(**base).run(branche='non_vie',
                                          sous_branche='auto',
                                          dataframe=donnees)
        qualite = preambule_qualite(r1.get('dataframe'), cls.plan,
                                    qualite_validee_par='Test',
                                    horodatage=None)
        r1 = {**r1, 'dataframe': qualite.dataframe_propre}
        cls.r2 = AgentA2Preprocessing(**base).run(result_a1=r1, plan=cls.plan)
        cls.r3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp').run(
            result_a2=cls.r2, plan=cls.plan,
            col_frequence=cls.plan.cible_frequence,
            col_cout=cls.plan.cible_cout, generer_graphiques=False)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def _a4(self, cible, agent=None):
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        agent = agent or AgentA4ML(models_path='/tmp', audit_path='/tmp')
        return agent, agent.run(
            result_a2=self.r2, result_a3=self.r3, plan=self.plan,
            col_cible=cible, ponderer_par_exposition=True, calcul_shap=False,
            generer_graphiques=False)

    def _ligne_glm(self, resultat):
        lignes = [c for c in (resultat.get('classement') or [])
                  if str(c.get('famille', '')).upper() == 'GLM']
        self.assertEqual(len(lignes), 1,
                         f'une seule ligne de reference attendue : {lignes}')
        return lignes[0]

    def test_RG3_sur_prime_pure_la_reference_est_le_TWEEDIE(self):
        _, r4 = self._a4('prime_pure')
        ligne = self._ligne_glm(r4)
        tweedie = self.r3['metriques']['tweedie']
        self.assertIn('Tweedie', ligne['modele'],
                      f"le libelle publie {ligne['modele']!r}")
        self.assertEqual(ligne['gini_test'], tweedie['gini'])
        self.assertEqual(ligne['overfit_ratio'], tweedie.get('overfit_ratio'))
        # ⚠️ ET SURTOUT : ce n'est PLUS la RMSE du Poisson, qui est sur une
        # autre echelle. Le Tweedie n'en publie pas -- l'absence se relaie.
        self.assertNotEqual(ligne['rmse_test'],
                            self.r3['metriques']['poisson'].get('rmse_test'))

    def test_RG4_sur_nb_sinistres_la_reference_reste_le_POISSON(self):
        """La contre-epreuve : le correctif n'a pas tout bascule."""
        _, r4 = self._a4('nb_sinistres')
        ligne = self._ligne_glm(r4)
        poisson = self.r3['metriques']['poisson']
        self.assertIn('Poisson', ligne['modele'])
        self.assertEqual(ligne['gini_test'], poisson['gini'])
        self.assertEqual(ligne['rmse_test'], poisson.get('rmse_test'))

    def test_RG8_les_graphiques_d_A4_survivent_a_un_ratio_NON_MESURE(self):
        """⚠️⚠️ TROUVE EN PASSANT, ET C'ETAIT UNE PANNE. `_generer_graphiques`
        portait `size = max(8, int(20 / max(overfit, 0.5)))` -- une taille de
        marqueur **jamais lue** (zero lecture, relevee par AST). Depuis que le
        ratio peut valoir `None`, `max(None, 0.5)` LEVE : la figure
        disparaissait des qu'un modele n'a pas de stabilite mesurable,
        c'est-a-dire le cas courant sur cette fixture.

        *Une ligne morte n'est pas inoffensive : elle s'execute.*
        """
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        agent = AgentA4ML.__new__(AgentA4ML)
        agent.shap_vals = {}
        classement = [
            {'modele': 'gbm', 'famille': 'Arbres / Boosting', 'gini_test': 0.13,
             'rmse_test': 0.74, 'overfit_ratio': 3.58, 'gini_train': 0.47,
             'recommandation': 'ok', 'overfit_alerte': True},
            # ⚠️ CELUI-CI porte le cas : ratio NON MESURE (son Gini de test est
            # negatif, `ratio_sur_apprentissage` refuse donc de le calculer).
            {'modele': 'lightgbm', 'famille': 'Arbres / Boosting',
             'gini_test': -0.11, 'rmse_test': 0.75, 'overfit_ratio': None,
             'gini_train': 0.40, 'recommandation': 'ok',
             'overfit_alerte': None},
        ]
        graphiques = agent._generer_graphiques(
            np.array([0.0, 1.0, 0.0, 2.0]), classement, ['age', 'bonus_malus'])
        # ⚠️⚠️ ON NOMME LA FIGURE. `assertTrue(graphiques)` ne surveillait
        # rien : chaque figure est produite dans son propre `try`, donc celle
        # qui plante disparait EN SILENCE et le dictionnaire reste non vide
        # grace aux autres. C'est le motif du constat `services/C13` --
        # *un controle qui atteste sans surveiller*.
        self.assertIn('scatter_gini_rmse', graphiques,
                      'la figure Gini/RMSE a disparu sur un ratio non mesure, '
                      f'en silence. Figures produites : {sorted(graphiques)}')

    def test_RG9_A3_et_le_pipeline_nomment_la_cible_a_L_IDENTIQUE(self):
        """⚠️⚠️ TOUT LE LOT REPOSE SUR CETTE EGALITE DE CHAINES. A3 declare
        `poisson['cible'] = col_frequence`, `gamma['cible'] = 'cout_moyen'`,
        `tweedie['cible'] = 'prime_pure'` ; le pipeline arbitre sur
        `plan.cible_frequence`, `CIBLE_COUT` et `CIBLE_PRIME_PURE`. Une
        divergence d'un seul caractere ferait disparaitre TOUTE reference
        GLM -- en silence, puisque l'absence est un etat legitime.

        *C'est le meme contrat d'appariement que le filtre de cible d'A6 :
        une divergence y ecarterait le Gamma de son propre arbitrage.*
        """
        from direction_non_vie.tarification.pipeline_agents import (
            CIBLE_COUT,
            CIBLE_PRIME_PURE,
        )
        met = self.r3['metriques']
        self.assertEqual(met['poisson']['cible'], self.plan.cible_frequence)
        self.assertEqual(met['gamma']['cible'], CIBLE_COUT)
        self.assertEqual(met['tweedie']['cible'], CIBLE_PRIME_PURE)
        # ... et la derivation retrouve bien les trois.
        for cible in (self.plan.cible_frequence, CIBLE_COUT, CIBLE_PRIME_PURE):
            with self.subTest(cible=cible):
                nom, _ = glm_de_reference(met, cible)
                self.assertIsNotNone(nom, f'aucun GLM pour {cible!r}')

    def test_RG7_la_cible_du_run_est_REINITIALISEE_a_chaque_appel(self):
        """⚠️⚠️ LE RISQUE QUE CE LOT INTRODUIT. La cible est rangee sur
        l'instance pour les methodes qui ne la recoivent pas. Un MEME agent
        relance sur une autre cible doit changer de reference -- sinon il
        comparerait le modele d'une cible a la reference d'une autre, ce qui
        est exactement le defaut corrige."""
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        agent = AgentA4ML(models_path='/tmp', audit_path='/tmp')
        _, premier = self._a4('nb_sinistres', agent)
        _, second = self._a4('prime_pure', agent)
        self.assertIn('Poisson', self._ligne_glm(premier)['modele'])
        self.assertIn('Tweedie', self._ligne_glm(second)['modele'],
                      "le MEME agent relance sur une autre cible garde la "
                      'reference du run precedent')


if __name__ == '__main__':
    unittest.main(verbosity=2)
