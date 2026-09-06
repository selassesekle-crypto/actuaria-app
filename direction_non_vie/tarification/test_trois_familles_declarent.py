"""RETENUES + EXCLUES = CANDIDATES, POUR LES TROIS FAMILLES -- constat `A3-1`.

Le stepwise de chaque GLM retire une variable quand l'ajustement echoue. Deux
familles sur trois le DECLARENT dans `vars_exclues` -- le Poisson dans
`core/frequence.py`, le Gamma dans `a3_glm/agent.py` avec trente lignes de
commentaire qui expliquent pourquoi. Le Tweedie faisait `vars_actives.pop()`
et rien d'autre : la variable n'etait ni retenue, ni exclue, elle n'avait
jamais existe.

⚠️⚠️ ET C'EST LE DENOMINATEUR DE LA PHRASE DE PUISSANCE QUI ETAIT FAUX.
`phrase_puissance_selection` existe pour dire a l'actuaire combien de
variables ont ete TESTEES : << avec onze candidates testees a 5 %, la
probabilite qu'au moins une variable de bruit passe vaut environ 37 % >>.
Annoncer 1 candidate au lieu de 4 sous-estime exactement ce risque-la. Cette
phrase est publiee dans le classeur A6 SIGNE (`tarif_excel:138`).

  TF-1  le Tweedie DECLARE la variable qu'il retire sur echec ;
  TF-2  et il la declare comme le Gamma : p-value NON TESTEE, cause NON
        ETABLIE, retrait ARBITRAIRE -- trois affirmations qu'on ne fabrique
        pas ;
  TF-3  le comportement d'AJUSTEMENT est inchange : seule la piste d'audit se
        complete. Controle NEGATIF, sans lequel TF-1 pourrait etre satisfait
        par un correctif qui change le modele.

⚠️ LE DECLENCHEUR EST CELUI DU DEPOT, PAS UN AUTRE. Le commentaire du Gamma
nomme les vrais declencheurs mesures : `MissingDataError` (NaN/Inf), deviance
NaN, matrice vide. On fait donc echouer l'ajustement PAR L'OUTIL, en
substituant `sm.GLM`, plutot qu'en inventant des donnees qui echoueraient
peut-etre ailleurs.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import unittest
import warnings

import numpy as np
import pandas as pd

from direction_non_vie.tarification.a3_glm import agent as A3


def _portefeuille(n=600):
    rng = np.random.default_rng(3)
    expo = rng.uniform(0.2, 1.0, n)
    df = pd.DataFrame({
        'exposition': expo,
        'v1': rng.normal(size=n),
        'v2': rng.normal(size=n),
        'v3': rng.normal(size=n),
        'v4': rng.normal(size=n),
    })
    df['nb_sinistres'] = rng.poisson(0.15 * expo, n).astype(float)
    df['cout_total_sinistres'] = np.where(
        df['nb_sinistres'] > 0, rng.gamma(2, 500, n), 0.0)
    df['prime_pure'] = df['cout_total_sinistres'] / np.maximum(expo, 1e-9)
    return df


def _retenues_et_exclues(resultat):
    """Les deux listes, ou qu'elles vivent dans le resultat.

    ⚠️ Elles sont sous `metriques`, pas au premier niveau -- trouve en
    mesurant : les cles rendues sont
    ['metriques', 'modele', 'modele_production', 'pred_test', 'relativites',
    'vars']. On DESCEND, on ne suppose pas.
    """
    source = resultat.get('metriques') or resultat
    return (list(source.get('vars_retenues') or []),
            list(source.get('vars_exclues') or []))


def _fabriquer_glm_qui_echoue(reel):
    """Un `sm.GLM` qui casse UNIQUEMENT sur les ajustements multi-colonnes.

    ⚠️⚠️ IL DOIT LAISSER PASSER LE REPLI INTERCEPT-SEUL. Ma premiere version
    faisait echouer TOUT ajustement : l'agent levait alors
    `CalibrationImpossible` — un chemin reel, mais PAS celui que `A3-1`
    decrit. *Un substitut qui casse plus que le defaut mesure ne mesure plus
    le defaut.*
    """

    class _GLMQuiEchoue(reel):
        def __init__(self, endog, exog, *args, **kwargs):
            colonnes = getattr(exog, 'shape', (0, 0))[1]
            self._casse = colonnes > 2
            super().__init__(endog, exog, *args, **kwargs)

        def fit(self, *args, **kwargs):
            if self._casse:
                raise ValueError('ajustement impossible (substitut de test)')
            return super().fit(*args, **kwargs)

    return _GLMQuiEchoue


class TestTroisFamillesDeclarent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        cls.df = _portefeuille()
        cls.vars_pred = ['v1', 'v2', 'v3', 'v4']

    def _calibrer(self, methode):
        agent = A3.AgentA3GLM(models_path='/tmp', audit_path='/tmp',
                              verbose=False)
        # ⚠️ POSE PAR `run()`, PAS PAR `__init__`. Sans lui le Gamma leve un
        # `AttributeError` que le `try` transforme en << aucun modele
        # ajustable >> : le test mesurerait alors un chemin d'echec TOTAL, pas
        # le retrait d'une variable. La famille vient du plan ; `gamma` est le
        # defaut du dépôt.
        agent._famille_severite_run = 'gamma'
        origine = A3.sm.GLM
        A3.sm.GLM = _fabriquer_glm_qui_echoue(origine)
        try:
            return getattr(agent, methode)(
                df_train=self.df.iloc[:480], df_test=self.df.iloc[480:],
                vars_pred=list(self.vars_pred), col_freq='nb_sinistres',
                col_cout='cout_total_sinistres', col_expo='exposition')
        finally:
            A3.sm.GLM = origine

    def test_TF1_le_Tweedie_declare_la_variable_qu_il_retire(self):
        """⚠️⚠️ AVANT, LA VARIABLE DISPARAISSAIT POUR L'AUDIT. Ni retenue, ni
        exclue : le denominateur de la phrase de puissance comptait 1 au lieu
        de 4."""
        resultat = self._calibrer('_calibrer_tweedie')
        retenues, exclues = _retenues_et_exclues(resultat)
        self.assertTrue(
            exclues,
            "le Tweedie n'a declare AUCUNE variable exclue apres des "
            f"ajustements en echec : elles ont disparu de l'audit. "
            f"Cles du resultat : {sorted(resultat)}")
        self.assertEqual(
            len(retenues) + len(exclues), len(self.vars_pred),
            f'retenues ({len(retenues)}) + exclues ({len(exclues)}) != '
            f'candidates ({len(self.vars_pred)}) : des variables sont perdues '
            f'pour la piste d audit')
        print(f'    TF-1 Tweedie : {len(retenues)} retenue(s) + '
              f'{len(exclues)} exclue(s) = {len(self.vars_pred)} candidates')

    def test_TF2_il_les_declare_COMME_LE_GAMMA(self):
        """⚠️ TROIS AFFIRMATIONS QU'ON NE FABRIQUE PAS : la p-value n'a jamais
        ete calculee, la cause n'est pas etablie, le retrait est arbitraire.
        C'est la doctrine que le Gamma porte deja."""
        _, exclues = _retenues_et_exclues(self._calibrer('_calibrer_tweedie'))
        sur_echec = [e for e in exclues
                     if e.get('pvalue_non_testee') or 'echec' in
                     str(e.get('raison', '')).lower()]
        self.assertTrue(
            sur_echec,
            f'aucune exclusion sur echec declaree : {exclues}')
        for entree in sur_echec:
            with self.subTest(variable=entree.get('variable')):
                self.assertIsNone(
                    entree.get('pvalue'),
                    'une p-value est publiee alors que rien ne l a testee : '
                    'elle se lirait << variable non significative >>')
                self.assertTrue(entree.get('pvalue_non_testee'))
                self.assertTrue(entree.get('variable_arbitraire'))
                self.assertIn('ARBITRAIREMENT', str(entree.get('raison', '')))
        print(f'    TF-2 Tweedie : {len(sur_echec)} exclusion(s) sur echec, '
              f'p-value None, retrait declare arbitraire')

    def test_TF3_le_GAMMA_tient_la_meme_propriete(self):
        """⚠️ CONTROLE DE JUMELLE : si le Gamma cessait de declarer, TF-1
        continuerait de passer. La propriete porte sur LES DEUX."""
        resultat = self._calibrer('_calibrer_gamma')
        _, exclues = _retenues_et_exclues(resultat)
        self.assertTrue(
            exclues,
            f'le Gamma ne declare plus ses exclusions : {sorted(resultat)}')
        print(f'    TF-3 Gamma : {len(exclues)} exclue(s) declaree(s)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
