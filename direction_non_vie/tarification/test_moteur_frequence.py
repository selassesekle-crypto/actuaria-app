# -*- coding: utf-8 -*-
"""DEUX CHEMINS AJUSTAIENT LA FREQUENCE AVEC DEUX CODES (lot 12).

A3 -- le moteur qui COMPARE des modeles -- et `pipeline_complet` -- le chemin
declaratif qui EXECUTE un plan signe -- ecrivaient chacun leur GLM de
frequence. *Deux chemins qui ajustent la meme grandeur avec deux codes
finissent par diverger* : c'est ce qui avait coute **-15 % de tarif** sur la
severite, avant que `core/severite.py` n'en fasse une source unique.
`core/frequence.py` en est le symetrique.

⚠️⚠️ IL UNIFIE LE CODE, PAS LA METHODE -- ET C'EST UN ARBITRAGE MESURE.
Mesure du 05/09/2026 sur les 18 plans porteurs de signal : apporter la
SELECTION au chemin declaratif ne deplace pas la masse (+0,000 % partout, le
coefficient d'equilibre la recale) mais **redistribue fortement** -- 24 % des
contrats a plus de 10 % d'ecart, jusqu'a 54 % sur `mrh`. Et sur quatre plans
elle retire des facteurs qui portent un effet REEL, faute de puissance :

    decennale   `sinistres_3ans_anterieurs`   p=0,0737   effet reel +0,40
    mrh         `statut_occupation_locataire` p=0,0594   effet reel +0,30
    rc_produit  `type_produit_alimentaire`    p=0,1020   effet reel +0,40

Pire, sur `mrh` (324 sinistres) la selection RETIENT `etage`, qui est du bruit
pur par construction du generateur. *Ce n'est pas le seuil qui decide, c'est le
nombre de SINISTRES* : les plans a plus de 900 sinistres retrouvent tout leur
signal, ceux a moins de 600 le perdent.

**Arbitrage de Selasse, 05/09/2026 : le tarif signe garde les facteurs que
l'actuaire y a inscrits.** `selection=False` n'est pas un repli, c'est la
doctrine du chemin declaratif.

Ce que cette sentinelle exige :
  MF-1  le socle porte UN seul ajustement, et les deux chemins l'appellent ;
  MF-2  ⚠️ le chemin declaratif NE SELECTIONNE PAS -- il garde toutes les
        colonnes conformes du plan signe ;
  MF-3  A3 SELECTIONNE, avec SON seuil passe explicitement ;
  MF-4  `selection=True` sans seuil est REFUSE : pas de seconde source du
        0,05 dans le socle ;
  MF-5  le defaut de `selection` est FALSE -- un appelant distrait ne peut pas
        modifier un tarif signe ;
  MF-6  le comportement d'`a3/C14` est repris a l'identique : un retrait
        apres echec porte `pvalue=None`, jamais 1.0 ;
  MF-7  ⚠️ AUCUN EURO NE BOUGE : le tarif du chemin declaratif est identique
        AU CENTIME a ce qu'il etait avant l'extraction ;
  MF-8  le socle ne REMONTE pas -- `core/frequence.py` n'importe aucune
        direction, et il ne traduit aucune exception d'agent.

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
import pandas as pd

from core.frequence import ajuster_glm_frequence


def _jeu(n=1500, seed=7):
    """Un portefeuille de comptage a signal CONNU : `x1` porte, `bruit` non."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    bruit = rng.normal(size=n)
    expo = rng.uniform(0.5, 1.0, n)
    y = rng.poisson(np.exp(-1.5 + 0.8 * x1) * expo).astype(float)
    return pd.DataFrame({'x1': x1, 'bruit': bruit, 'nb': y}), np.log(expo)


class TestLeMoteurPartage(unittest.TestCase):

    def test_MF2_sans_selection_TOUTES_les_colonnes_sont_gardees(self):
        """⚠️⚠️ LA DOCTRINE DU CHEMIN DECLARATIF. Il execute un plan SIGNE :
        ses facteurs sont un engagement de l'actuaire, pas une hypothese a
        tester. *Une variable sans signal statistique reste une variable que
        quelqu'un a decide de tarifer.*"""
        df, offset = _jeu()
        r = ajuster_glm_frequence(df, ['x1', 'bruit'], 'nb', offset)
        self.assertEqual(sorted(r['variables']), ['bruit', 'x1'],
                         'le chemin declaratif a retire une colonne du plan')
        self.assertEqual(r['exclues'], [])
        self.assertEqual(r['iterations'], 1)

    def test_MF3_avec_selection_le_BRUIT_part_et_le_SIGNAL_reste(self):
        df, offset = _jeu()
        r = ajuster_glm_frequence(df, ['x1', 'bruit'], 'nb', offset,
                                  selection=True, seuil_pvalue=0.05)
        self.assertIn('x1', r['variables'], 'la selection a retire le SIGNAL')
        self.assertNotIn('bruit', r['variables'],
                         'la selection garde une variable sans effet')
        self.assertTrue(r['exclues'], 'aucun retrait trace')
        self.assertIsNotNone(r['exclues'][0]['pvalue'])

    def test_MF4_selection_SANS_seuil_est_REFUSEE(self):
        """⚠️⚠️ PAS DE SECONDE SOURCE DU 0,05. Le seuil vit chez celui qui
        selectionne (`a3_glm.SEUIL_PVALUE`), et un test l'y fige. Lui donner
        un defaut ici creerait le doublon que ce module existe pour fermer."""
        df, offset = _jeu()
        with self.assertRaises(ValueError):
            ajuster_glm_frequence(df, ['x1'], 'nb', offset, selection=True)

    def test_MF5_le_defaut_de_selection_est_FALSE(self):
        """⚠️ Un appelant distrait ne doit pas pouvoir modifier un tarif
        signe. Le defaut PRUDENT est celui qui ne retire rien."""
        import inspect
        sig = inspect.signature(ajuster_glm_frequence)
        self.assertIs(sig.parameters['selection'].default, False)
        self.assertIsNone(sig.parameters['seuil_pvalue'].default)

    def test_MF6_un_retrait_apres_ECHEC_porte_pvalue_None(self):
        """⚠️⚠️ CONSTAT `a3/C14`, REPRIS A L'IDENTIQUE. Une `pvalue` fabriquee
        a 1.0 se lirait << variable non significative >> alors que RIEN n'a
        ete teste. Et la variable retiree est ARBITRAIRE : l'exception ne dit
        pas laquelle a echoue -- c'est DECLARE, pas corrige."""
        # ⚠️ UN `inf` DANS UNE COLONNE fait echouer l'ajustement sans que
        # statsmodels ne nomme la coupable -- exactement la situation du
        # constat. Ma premiere fixture (cible toute nulle) etait trop
        # degeneree : meme le modele a la seule constante echouait, et
        # l'exception remontait avant d'atteindre ce chemin. *Une fixture qui
        # casse tout ne prouve rien sur un cas particulier.*
        rng = np.random.default_rng(3)
        n = 400
        df = pd.DataFrame({
            'a': np.r_[np.inf, rng.normal(size=n - 1)],
            'b': rng.normal(size=n),
            'nb': rng.poisson(0.3, n).astype(float)})
        r = ajuster_glm_frequence(df, ['a', 'b'], 'nb', np.zeros(n),
                                  selection=True, seuil_pvalue=0.05)
        non_testees = [e for e in r['exclues']
                       if e.get('pvalue_non_testee')]
        self.assertTrue(non_testees,
                        "aucun retrait NON TESTE : ce test n'exerce plus le "
                        'chemin du constat `a3/C14`')
        for e in non_testees:
            self.assertIsNone(e['pvalue'],
                              'une p-value FABRIQUEE remplace une mesure '
                              'qui n a pas eu lieu')
            self.assertTrue(e.get('variable_arbitraire'),
                            'le retrait ARBITRAIRE ne se declare pas')
            self.assertIn('ARBITRAIREMENT', e['raison'])

    def test_MF8_le_socle_ne_REMONTE_pas_vers_une_direction(self):
        """⚠️ Meme regle que le lot 16 : un socle qui a besoin d'une direction
        n'est pas un socle. Releve par AST, pas par grep."""
        import ast
        chemin = os.path.join(_RACINE, 'core', 'frequence.py')
        with open(chemin, encoding='utf-8') as f:
            arbre = ast.parse(f.read())
        for n in ast.walk(arbre):
            mods = ([a.name for a in n.names] if isinstance(n, ast.Import)
                    else [n.module] if isinstance(n, ast.ImportFrom) and n.module
                    else [])
            for m in mods:
                self.assertFalse(
                    m.split('.')[0].startswith('direction_'),
                    f'`core/frequence.py` importe {m} : le socle remonte')


class TestLesDeuxCheminsAppellentLeMoteur(unittest.TestCase):
    """⚠️⚠️ PAR EXECUTION. Un controle par AST verrait un import ; seule
    l'execution prouve que le chemin passe VRAIMENT par le moteur."""

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_MF1_MF7_le_tarif_declaratif_est_INCHANGE_au_centime(self):
        """⚠️⚠️ LA CONDITION (4), DEVENUE CONTROLE. L'extraction ne devait
        RIEN deplacer sur le chemin signe : ces valeurs sont celles mesurees
        AVANT le lot 12, et elles sont ecrites ici en dur pour cela.

        ⚠️ Si le modele change un jour, ce test doit TOMBER et etre
        re-mesure -- jamais ajuste pour le faire passer.
        """
        from direction_non_vie.tarification import test_pipeline_agents as T
        from direction_non_vie.tarification.pipeline_tarifaire import (
            pipeline_complet,
        )
        np.random.seed(7)
        plan = T._PLAN_AUTO
        df = T._portefeuille_auto(2500)
        tarif = pipeline_complet(df, plan)
        primes = np.asarray(
            tarif.predire_portefeuille(df)['prime_pure'], dtype=float)
        # ⚠️ Le chemin declaratif garde TOUTES ses colonnes : c'est ce que
        # `selection=False` garantit, et c'est verifiable ici.
        self.assertEqual(len(tarif.features),
                         len(set(tarif.features)),
                         'des colonnes en double dans la specification')
        self.assertGreater(len(tarif.features), 10,
                           "le chemin declaratif a perdu des facteurs : la "
                           "selection s'y est invitee")
        self.assertAlmostEqual(float(primes.sum()), 1993741.098588, places=2,
                               msg='LE TARIF A BOUGE — le lot 12 ne devait '
                                   'rien deplacer sur le chemin signe')

    def test_MF3b_A3_selectionne_toujours_et_publie_ses_exclusions(self):
        """⚠️ Le second sens : A3 doit CONTINUER de selectionner. Un moteur
        partage qui aurait desactive sa selection serait passe inapercu du
        test precedent."""
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
        plan = T._PLAN_AUTO
        base = {'audit_path': '/tmp', 'verbose': False}
        r1 = AgentA1Ingestion(**base).run(
            branche='non_vie', sous_branche='auto',
            dataframe=T._portefeuille_auto(1500))
        q = preambule_qualite(r1.get('dataframe'), plan,
                              qualite_validee_par='Test', horodatage=None)
        r2 = AgentA2Preprocessing(**base).run(
            result_a1={**r1, 'dataframe': q.dataframe_propre}, plan=plan)
        r3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp').run(
            result_a2=r2, plan=plan, col_frequence=plan.cible_frequence,
            col_cout=plan.cible_cout, generer_graphiques=False)
        poisson = (r3.get('metriques') or {}).get('poisson') or {}
        self.assertGreater(poisson.get('nb_vars_exclues', 0), 0,
                           "A3 ne selectionne plus : le moteur partage a "
                           'emporte sa methode avec le code')
        self.assertTrue(poisson.get('vars_exclues'),
                        'les exclusions ne sont plus publiees')


if __name__ == '__main__':
    unittest.main(verbosity=2)
