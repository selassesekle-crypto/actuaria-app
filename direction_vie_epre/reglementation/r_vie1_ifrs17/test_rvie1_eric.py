"""
Tests Agent R-VIE1 — Éric — QRT S.26 Vie
7 tests couvrant : nominal, SCR, matrice EIOPA, décomposition, cas limites
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

import pytest
import numpy as np
from direction_vie_epre.reglementation.r_vie1_ifrs17.agent import AgentRVIE1QRTVie


@pytest.fixture
def agent():
    return AgentRVIE1QRTVie(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestRVIE1QRTVie:

    # T1 — Cas nominal
    def test_t1_nominal(self, agent):
        r = agent.run(be_vie=45_000_000, pm_total=50_000_000,
                      fonds_propres=12_000_000, generer_graphiques=False)
        assert r['success'] is True
        assert r['scr_vie_total'] > 0
        assert r['ratio_scr_pct'] > 0
        assert r['matrice_pos_def'] is True
        assert r['erreur'] is None

    # T2 — Matrice EIOPA définie positive → H1 VERT
    def test_t2_matrice_definie_positive(self, agent):
        r = agent.run(be_vie=45_000_000, pm_total=50_000_000,
                      fonds_propres=12_000_000, generer_graphiques=False)
        assert r['success'] is True
        assert r['matrice_pos_def'] is True
        val = r['validation_rvie1']
        assert val['h1_matrice']['statut'] == 'VERT'

    # T3 — SCR vie < somme des sous-modules (effet diversification)
    def test_t3_effet_diversification(self, agent):
        r = agent.run(be_vie=45_000_000, pm_total=50_000_000,
                      fonds_propres=12_000_000, generer_graphiques=False)
        assert r['success'] is True
        somme_brute = sum(r['decomposition_scr'][k]['scr']
                          for k in r['decomposition_scr'])
        assert r['scr_vie_total'] < somme_brute, \
            "Pas d'effet diversification — vérifier la matrice de corrélation"

    # T4 — Ratio SCR ≥ 150% avec fonds propres suffisants → H2 VERT
    def test_t4_ratio_scr_solide(self, agent):
        r = agent.run(be_vie=10_000_000, pm_total=12_000_000,
                      fonds_propres=15_000_000, generer_graphiques=False)
        assert r['success'] is True
        assert r['ratio_scr_pct'] >= 150
        val = r['validation_rvie1']
        assert val['h2_ratio_scr']['statut'] == 'VERT'

    # T5 — Ratio SCR < 100% → H2 ROUGE
    def test_t5_ratio_scr_insuffisant(self, agent):
        r = agent.run(be_vie=100_000_000, pm_total=110_000_000,
                      fonds_propres=5_000_000, generer_graphiques=False)
        assert r['success'] is True
        if r['ratio_scr_pct'] < 100:
            val = r['validation_rvie1']
            assert val['h2_ratio_scr']['statut'] == 'ROUGE'

    # T6 — Décomposition SCR : 7 sous-modules présents
    def test_t6_decomposition_7_modules(self, agent):
        r = agent.run(be_vie=45_000_000, pm_total=50_000_000,
                      fonds_propres=12_000_000, generer_graphiques=False)
        assert r['success'] is True
        modules = list(r['decomposition_scr'].keys())
        assert len(modules) == 7
        assert 'mortalite' in modules
        assert 'longevite' in modules
        assert 'rachat' in modules

    # T7 — SCR proportionnel au BE (toutes choses égales)
    def test_t7_scr_proportionnel_be(self, agent):
        r1 = agent.run(be_vie=45_000_000, pm_total=50_000_000,
                       fonds_propres=12_000_000, generer_graphiques=False)
        r2 = agent.run(be_vie=90_000_000, pm_total=100_000_000,
                       fonds_propres=24_000_000, generer_graphiques=False)
        assert r1['success'] and r2['success']
        ratio = r2['scr_vie_total'] / max(r1['scr_vie_total'], 1)
        assert abs(ratio - 2.0) < 0.01, \
            f"SCR non proportionnel au BE : ratio={ratio:.3f} (attendu ≈ 2.0)"

    # T8 — A6 : alimentation automatique depuis result_v3
    def test_t8_alimentation_depuis_v3(self, agent):
        result_v3_mock = {
            'success': True,
            'pm_prospective': 30_000_000,  # BE = PM prospective V3
        }
        r = agent.run(
            fonds_propres=12_000_000,
            result_v3=result_v3_mock,
            generer_graphiques=False
        )
        assert r['success'] is True
        # be_vie doit être alimenté depuis result_v3
        assert r['be_vie'] == 30_000_000, (
            f"be_vie={r['be_vie']} ≠ 30_000_000 — alimentation V3 non appliquée"
        )
        assert r['pm_total'] == 30_000_000
        # SCR doit être recalculé sur la base du BE issu de V3
        assert r['scr_vie_total'] > 0
        assert r.get('source_be_vie') == 'V3 Amélie (pm_prospective)'

    def test_t9_rachat_trois_sous_chocs(self, agent):
        """Art. 142 S2 : le SCR rachat = max(hausse, baisse, mass_lapse)"""
        r = agent.run(be_vie=45e6, pm_total=50e6, fonds_propres=12e6,
                      generer_graphiques=False)
        assert r['success'] is True
        assert 'rachat_detail' in r
        rd = r['rachat_detail']
        # Les trois sous-chocs doivent être présents
        for key in ['hausse', 'baisse', 'mass_lapse', 'dominant']:
            assert key in rd, f"Clé manquante dans rachat_detail : {key}"
        # Le SCR rachat déclaré = max des trois sous-chocs
        scr_rachat = r['decomposition_scr']['rachat']['scr']
        assert scr_rachat == max(rd['hausse'], rd['baisse'], rd['mass_lapse']), \
            "SCR rachat doit être le maximum des trois sous-chocs (Art. 142 §4)"
        # Pour un portefeuille vie classique, le mass lapse est dominant
        assert rd['dominant'] == 'mass_lapse', \
            "Le mass lapse doit être dominant pour un portefeuille vie standard"

    def test_t10_mass_lapse_superieur_sous_chocs(self, agent):
        """Le choc mass_lapse (40%) > hausse (25%) > baisse (20%) — cohérence Art. 142"""
        r = agent.run(be_vie=100e6, pm_total=110e6, fonds_propres=20e6,
                      generer_graphiques=False)
        assert r['success'] is True
        rd = r['rachat_detail']
        assert rd['mass_lapse'] > rd['hausse'] > rd['baisse'], \
            "Ordre des sous-chocs incorrect : mass_lapse > hausse > baisse attendu"
        assert rd['mass_lapse'] == 40_000_000, "mass_lapse doit être 40% × BE = 40M€"
        assert rd['hausse']     == 25_000_000, "hausse doit être 25% × BE = 25M€"
        assert rd['baisse']     == 20_000_000, "baisse doit être 20% × BE = 20M€"
