# -*- coding: utf-8 -*-
"""
Tests de core/charts_tarif.py — chaque fonction retourne une go.Figure valide
sur des données jouet, la charte V3 est appliquée, les helpers sont corrects.
"""
import os
import sys
import unittest

import numpy as np

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

import plotly.graph_objects as go  # noqa: E402
from core import charts_tarif as ct  # noqa: E402


class TestChartsTarifHelpers(unittest.TestCase):
    """Helpers privés : gradient, thème, inverse normale."""

    def test_gradient_ordonne_rend_n_couleurs(self):
        for n in (1, 2, 5, 10):
            couls = ct._gradient_ordonne(n)
            self.assertEqual(len(couls), n)
            self.assertTrue(all(c.startswith('rgba(') for c in couls))

    def test_couleur_gradient_bornes(self):
        # bas ≈ bleu (fort en B), haut ≈ orange (fort en R)
        bas = ct._couleur_gradient(0.0)
        haut = ct._couleur_gradient(1.0)
        self.assertIn('30,100,180', bas)
        self.assertIn('240,85,35', haut)
        # clip hors [0,1]
        self.assertEqual(ct._couleur_gradient(-5), ct._couleur_gradient(0.0))
        self.assertEqual(ct._couleur_gradient(9), ct._couleur_gradient(1.0))

    def test_qnorm_valeurs_connues(self):
        v = ct._qnorm(np.array([0.5, 0.975, 0.025]))
        self.assertAlmostEqual(v[0], 0.0, places=4)
        self.assertAlmostEqual(v[1], 1.959964, places=3)
        self.assertAlmostEqual(v[2], -1.959964, places=3)
        # monotonie croissante
        q = ct._qnorm(np.linspace(0.01, 0.99, 50))
        self.assertTrue(np.all(np.diff(q) > 0))

    def test_appliquer_theme_pose_la_charte(self):
        fig = ct._appliquer_theme(go.Figure(), 'Titre X')
        self.assertEqual(fig.layout.paper_bgcolor, ct.COULEURS['papier'])
        self.assertEqual(fig.layout.plot_bgcolor, ct.COULEURS['graphique'])
        self.assertEqual(fig.layout.title.text, 'Titre X')
        self.assertEqual(fig.layout.title.font.color, ct.COULEURS['or_titre'])

    def test_config_plotly_sans_barre_outils(self):
        self.assertFalse(ct.CONFIG_PLOTLY['displayModeBar'])


class TestChartsTarifFigures(unittest.TestCase):
    """Les 7 fonctions retournent une go.Figure valide sur données jouet."""

    def _assert_figure(self, fig, min_traces=1):
        self.assertIsInstance(fig, go.Figure)
        self.assertGreaterEqual(len(fig.data), min_traces)
        # la charte est bien appliquée
        self.assertEqual(fig.layout.paper_bgcolor, ct.COULEURS['papier'])

    def test_1_lift_decile(self):
        deciles = [0.18, 0.19, 0.21, 0.22, 0.24, 0.25, 0.27, 0.29, 0.33, 0.46]
        fig = ct.chart_lift_decile(deciles, lift_ratio=2.55)
        self._assert_figure(fig)
        # badge LIFT présent
        self.assertTrue(any('LIFT' in (a.text or '') for a in fig.layout.annotations))

    def test_2_lorenz_gini(self):
        """⚠️ CE TEST VERROUILLAIT LA MAUVAISE ÉTIQUETTE. Il exigeait « GINI »
        dans le badge — or la courbe est construite en triant par la valeur
        OBSERVÉE : le nombre affiché est le PLAFOND du portefeuille, pas le
        Gini d'un modèle. Sur le rapport mesuré, le badge disait 0,832 quand
        les tableaux disaient 0,178.
        """
        x = np.linspace(0, 1, 50)
        y = x ** 1.8
        fig = ct.chart_lorenz_gini(x.tolist(), y.tolist(), gini_observe=0.832)
        self._assert_figure(fig, min_traces=3)  # aire + diagonale + halo + ligne
        badges = ' '.join(a.text or '' for a in fig.layout.annotations)
        self.assertIn('Concentration observée', badges)
        self.assertIn('0.8320', badges)
        self.assertNotIn('GINI', badges)

    def test_2b_lorenz_les_deux_gini_donnent_le_ratio(self):
        """⚠️ LES DEUX ENSEMBLE VALENT MIEUX QUE L'UN CORRIGÉ : leur rapport
        dit la part du discriminable que le modèle capte — 0,1775 / 0,832 =
        21 % — ce qu'aucun des deux ne dit seul."""
        x = np.linspace(0, 1, 50)
        fig = ct.chart_lorenz_gini(x.tolist(), (x ** 1.8).tolist(),
                                   gini_observe=0.832, gini_modele=0.1775)
        badges = ' '.join(a.text or '' for a in fig.layout.annotations)
        self.assertIn('0.1775', badges)
        self.assertIn('21 %', badges)
        self.assertIn('discriminable', badges)

    def test_2c_sans_gini_modele_aucun_ratio_invente(self):
        """Un ratio ne se produit que si les DEUX nombres existent."""
        x = np.linspace(0, 1, 50)
        fig = ct.chart_lorenz_gini(x.tolist(), (x ** 1.8).tolist(),
                                   gini_observe=0.832)
        badges = ' '.join(a.text or '' for a in fig.layout.annotations)
        self.assertNotIn('discriminable', badges)
        self.assertNotIn('%', badges)
        # et un plafond nul ne produit pas une division
        fig0 = ct.chart_lorenz_gini(x.tolist(), (x ** 1.8).tolist(),
                                    gini_observe=0.0, gini_modele=0.1775)
        self.assertNotIn('discriminable',
                         ' '.join(a.text or '' for a in fig0.layout.annotations))

    def test_3_relativites_glm(self):
        rel = {
            'bonus_malus':  {'relativite': 1.85, 'ic95_low': 1.70, 'ic95_high': 2.01},
            'age_jeune':    {'relativite': 1.42, 'ic95_low': 1.30, 'ic95_high': 1.55},
            'zone_rurale':  {'relativite': 0.78, 'ic95_low': 0.70, 'ic95_high': 0.87},
            'anciennete':   {'relativite': 0.95},          # sans IC → error-bar 0
        }
        fig = ct.chart_relativites_glm(rel, top=10)
        self._assert_figure(fig)
        self.assertEqual(fig.data[0].orientation, 'h')

    def test_4_walkforward_ae(self):
        fen = [
            {'annee_test': 2020, 'ae_ratio': 1.01},
            {'annee_test': 2021, 'ae_ratio': 0.97},
            {'annee_test': 2022, 'ae_ratio': 1.08},
            {'annee_test': 2023, 'ae_ratio': 1.19},   # hors bande → rouge
        ]
        fig = ct.chart_walkforward_ae(fen)
        self._assert_figure(fig)

    def test_5_shap_summary(self):
        imp = {'bonus_malus': 0.42, 'age': 0.31, 'puissance': 0.12,
               'km': 0.08, 'garantie': 0.05}
        fig = ct.chart_shap_summary(imp)
        self._assert_figure(fig)
        self.assertEqual(fig.data[0].orientation, 'h')

    def test_6_distribution_predictions(self):
        rng = np.random.default_rng(0)
        preds = rng.gamma(2.0, 300.0, 5000)
        fig = ct.chart_distribution_predictions(preds, unite='€')
        self._assert_figure(fig)
        self.assertEqual(fig.data[0].type, 'histogram')

    def test_7_residus_qq(self):
        rng = np.random.default_rng(1)
        res = rng.normal(0, 1, 2000)
        fig = ct.chart_residus_qq(res)
        self._assert_figure(fig, min_traces=2)  # ligne y=x + points


class TestChartsTarifCasLimites(unittest.TestCase):
    """Robustesse : données vides / dégénérées ne plantent pas."""

    def test_predictions_vides(self):
        fig = ct.chart_distribution_predictions([])
        self.assertIsInstance(fig, go.Figure)

    def test_residus_insuffisants(self):
        fig = ct.chart_residus_qq([0.3])   # n<2 → figure thémée sans points
        self.assertIsInstance(fig, go.Figure)

    def test_lift_un_seul_decile(self):
        fig = ct.chart_lift_decile([0.25], lift_ratio=None)
        self.assertIsInstance(fig, go.Figure)

    def test_relativites_vides(self):
        fig = ct.chart_relativites_glm({})
        self.assertIsInstance(fig, go.Figure)


if __name__ == '__main__':
    unittest.main(verbosity=2)
