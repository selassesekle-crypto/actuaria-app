"""Controles positifs — constat `a3/C14` : la p-value fabriquee a 1,0.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
Sur echec d'ajustement, le stepwise d'A3 publiait TROIS affirmations fausses :

  ① `pvalue: 1.0` -- JAMAIS calculee. Un actuaire lit « variable non
    significative » la ou rien n'a ete teste ;
  ② `raison: 'erreur numerique'` -- une cause NON ETABLIE ;
  ③ la variable retiree est `vars_actives[-1]`, la DERNIERE, pas celle qui a
    echoue. L'exception ne dit pas laquelle.

CE QUI A ETE MESURE AVANT DE CORRIGER (demande de Selasse)
  · frequence sur donnees propres : 0 sur 36 exclusions du portefeuille du
    banc -- le chemin n'est PAS atteint quand les donnees sont saines ;
  · atteignabilite : statsmodels ne leve NI sur colinearite parfaite, NI sur
    colonne constante, NI sur separation totale. Les seuls declencheurs
    trouves sont des defauts de DONNEES -- MissingDataError (NaN/Inf),
    deviance NaN, matrice vide ;
  · et le `try` couvre ~30 lignes avec un `except Exception` NU : il attrape
    aussi bien un KeyError de `.drop`. « Erreur numerique » etiquetait donc
    une cause que rien n'etablissait.

⚠️⚠️ CE LOT NE CHANGE PAS QUELLE VARIABLE EST RETIREE. En changer modifierait
le modele ajuste, donc un prix -- et il faudrait savoir laquelle a echoue, ce
que l'exception ne dit pas. *Deviner mieux resterait deviner.* On DECLARE.
"""

from __future__ import annotations

import unittest
import warnings

import numpy as np
import pandas as pd

import direction_non_vie.tarification.a3_glm.agent as mod_a3
from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM


def _donnees(n: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(2)
    d = pd.DataFrame({'x1': rng.normal(0, 1, n),
                      'x2': rng.normal(0, 1, n),
                      'x3': rng.normal(0, 1, n)})
    d['expo'] = 1.0
    d['nb'] = rng.poisson(0.3, n)
    return d


def _calibrer_avec_echecs(n_echecs: int, message: str = 'exog contains inf or nans'):
    """Force l'exception que le handler existe pour attraper, `n_echecs` fois.

    ⚠️ On ne FABRIQUE pas la publication : on declenche la vraie exception, et
    on lit ce que le vrai handler publie. Intermittent, pour que la methode
    aboutisse -- le repli « intercept seul » est HORS du `try` et leverait.
    """
    d = _donnees()
    vrai = mod_a3.sm.GLM
    etat = {'n': 0}

    def faux(*a, **k):
        etat['n'] += 1
        if etat['n'] <= n_echecs:
            raise ValueError(message)
        return vrai(*a, **k)

    mod_a3.sm.GLM = faux
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            agent = AgentA3GLM(models_path='/tmp', audit_path='/tmp',
                               verbose=False)
            res = agent._calibrer_poisson(d, d.copy(), ['x1', 'x2', 'x3'],
                                          'nb', 'expo')
    finally:
        mod_a3.sm.GLM = vrai
    return res['metriques'].get('vars_exclues') or []


class TestPValueNonFabriquee(unittest.TestCase):
    """Une p-value non calculee vaut None, et le retrait se dit arbitraire."""

    def test_aucune_pvalue_fabriquee_a_1_0(self):
        """⚠️ La forme exacte du defaut, epinglee — par EXECUTION."""
        exclusions = _calibrer_avec_echecs(2)
        fabriquees = [e for e in exclusions if e.get('pvalue') == 1.0]
        self.assertEqual(
            fabriquees, [],
            "Une p-value de 1,0 est republiée sur un échec d'ajustement : "
            "elle se lit « variable non significative » alors que rien n'a "
            "été testé.")

    def test_la_pvalue_non_testee_vaut_None_et_le_DIT(self):
        """`None` seul serait ambigu — le drapeau le rend explicite."""
        exclusions = _calibrer_avec_echecs(2)
        echecs = [e for e in exclusions if e.get('pvalue_non_testee')]
        self.assertEqual(
            len(echecs), 2,
            f"2 échecs forcés, {len(echecs)} exclusion(s) déclarée(s) non "
            f"testée(s).")
        for e in echecs:
            self.assertIsNone(e.get('pvalue'))
            self.assertTrue(e.get('variable_arbitraire'))

    def test_la_raison_nomme_le_TYPE_reel_et_pas_une_cause_supposee(self):
        """⚠️⚠️ « erreur numérique » affirmait une cause non établie.

        Mesuré : statsmodels ne lève ni sur colinéarité, ni sur colonne
        constante, ni sur séparation. Le `try` attrape aussi un KeyError. On
        nomme donc le TYPE, on ne conclut pas sur la cause.
        """
        exclusions = _calibrer_avec_echecs(1, message='colonne introuvable')
        echecs = [e for e in exclusions if e.get('pvalue_non_testee')]
        self.assertTrue(echecs)
        raison = echecs[0]['raison']
        self.assertIn('ValueError', raison)
        self.assertIn('colonne introuvable', raison)
        self.assertNotIn('erreur numerique', raison.lower())
        self.assertNotIn('erreur numérique', raison.lower())

    def test_le_retrait_arbitraire_est_DECLARE_comme_tel(self):
        """⚠️ Le comportement est INCHANGÉ — c'est son aveu qui est nouveau.

        Sans cette phrase, un actuaire lirait le retrait comme un diagnostic :
        « cette variable posait problème ». Elle est seulement la dernière.
        """
        exclusions = _calibrer_avec_echecs(1)
        echecs = [e for e in exclusions if e.get('pvalue_non_testee')]
        self.assertIn('ARBITRAIREMENT', echecs[0]['raison'])
        self.assertIn("n'est pas etablie", echecs[0]['raison'])

    def test_la_voie_NORMALE_garde_sa_vraie_pvalue(self):
        """⚠️ SECOND SENS — le plus important du fichier.

        Une exclusion pour p-value élevée doit garder son NOMBRE MESURÉ et
        n'être marquée ni « non testée » ni « arbitraire ». Sans cette
        assertion, on aurait pu effacer toutes les p-values et croire le
        constat fermé.
        """
        exclusions = _calibrer_avec_echecs(0)   # aucun échec : voie normale
        normales = [e for e in exclusions if not e.get('pvalue_non_testee')]
        self.assertTrue(
            normales,
            "Aucune exclusion par p-value : le test ne prouve plus rien sur "
            "la voie normale.")
        for e in normales:
            self.assertIsInstance(e.get('pvalue'), float)
            self.assertNotEqual(e.get('pvalue'), 1.0)
            self.assertIsNone(e.get('variable_arbitraire'))
            self.assertIn('p-value', e.get('raison', ''))


if __name__ == '__main__':
    unittest.main()
