"""Tests Agent EP7 — Camille — Optimisation PB sous Contraintes (7 tests)"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
from direction_vie_epre.epargne_retraite.ep7_optimisation_pb.agent import AgentEP7OptimisationPB

@pytest.fixture
def agent():
    return AgentEP7OptimisationPB(models_path='/tmp/actuaria/models',
                                   audit_path='/tmp/actuaria/audit', verbose=False)

class TestEP7OptimisationPB:

    # T1 — Cas nominal : structure et valeur dans la plage
    def test_t1_nominal(self, agent):
        r = agent.run(pm_total=50e6, rendement_actifs=0.04,
                      taux_technique=0.025, fonds_propres=8e6,
                      scr_vie=5e6, ppb_stock=1e6, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert r.get('erreur') is None
        # Taux optimal dans la plage
        assert r['tx_min'] <= r['tx_optimal'] <= r['tx_max']
        assert r['tx_optimal_pct'] > 0

    # T2 — Le taux optimal respecte toutes les contraintes
    def test_t2_contraintes_respectees(self, agent):
        r = agent.run(pm_total=50e6, rendement_actifs=0.04,
                      taux_technique=0.02, fonds_propres=12e6,
                      scr_vie=5e6, ppb_stock=500_000,
                      scr_cible_pct=150.0, generer_graphiques=False)
        assert r['success'] is True
        eval_opt = r['evaluation_optimale']
        assert eval_opt['toutes_ok'] is True, (
            f"Contraintes violées : L132={eval_opt['c_l132_ok']}, "
            f"PPB={eval_opt['c_ppb_ok']}, SCR={eval_opt['c_scr_ok']}"
        )

    # T3 — L132-29 : PB servie ≥ 85% des produits financiers
    def test_t3_l132_29_respecte(self, agent):
        r = agent.run(pm_total=50e6, rendement_actifs=0.04,
                      taux_technique=0.02, fonds_propres=15e6,
                      scr_vie=3e6, ppb_stock=2e6, generer_graphiques=False)
        assert r['success'] is True
        # PB minimale = 85% × produits financiers
        pb_min = r['pb_legale_min']
        pb_opt  = r['evaluation_optimale']['pb_servie']
        ppb_fin = r['evaluation_optimale']['ppb_finale']
        assert pb_opt + ppb_fin >= pb_min * 0.99, (
            f"L132-29 violée : PB+PPB={pb_opt+ppb_fin:.0f} < PB_min={pb_min:.0f}"
        )

    # T4 — SCR cible respecté post-distribution
    def test_t4_scr_cible_respecte(self, agent):
        r = agent.run(pm_total=50e6, rendement_actifs=0.04,
                      taux_technique=0.025, fonds_propres=10e6,
                      scr_vie=5e6, scr_cible_pct=150.0, generer_graphiques=False)
        assert r['success'] is True
        ratio_scr = r['evaluation_optimale']['ratio_scr']
        assert ratio_scr >= 150.0, (
            f"Ratio SCR = {ratio_scr:.1f}% < cible 150%"
        )

    # T5 — Sensibilité : 4 points de sensibilité calculés
    def test_t5_sensibilite_calculee(self, agent):
        r = agent.run(pm_total=50e6, rendement_actifs=0.04,
                      taux_technique=0.02, fonds_propres=12e6,
                      scr_vie=5e6, generer_graphiques=False)
        assert r['success'] is True
        sensib = r['sensibilite']
        for key in ['-50bp', '-25bp', '+25bp', '+50bp']:
            assert key in sensib, f"Point de sensibilité manquant : {key}"
            assert 'ratio_scr' in sensib[key]
            assert 'toutes_contraintes_ok' in sensib[key]

    # T6 — Alimentation depuis EP3
    def test_t6_alimentation_depuis_ep3(self, agent):
        result_ep3_mock = {
            'success': True,
            'provisions': {
                'pm_encours':   40_000_000,
                'ppb_total':    2_000_000,
            }
        }
        r = agent.run(pm_total=99e6,  # sera écrasé par EP3
                      rendement_actifs=0.04, taux_technique=0.02,
                      fonds_propres=12e6, scr_vie=5e6,
                      result_ep3=result_ep3_mock, generer_graphiques=False)
        assert r['success'] is True
        assert r['pm_total'] == 40_000_000
        assert r['sources'].get('pm_total') == 'EP3 Jin-Ho (provisions.pm_encours)'
        assert r['sources'].get('ppb_stock') == 'EP3 Jin-Ho (provisions.ppb_total)'

    # T7 — Monotonie : taux optimal croît avec les fonds propres
    def test_t7_monotonie_fonds_propres(self, agent):
        """Plus les fonds propres sont élevés, plus le taux servi peut être élevé."""
        params = dict(pm_total=50e6, rendement_actifs=0.04, taux_technique=0.02,
                      scr_vie=5e6, ppb_stock=500_000, scr_cible_pct=150.0,
                      generer_graphiques=False)
        r_bas  = agent.run(fonds_propres=7e6,  **params)
        r_haut = agent.run(fonds_propres=15e6, **params)
        assert r_bas['success'] and r_haut['success']
        assert r_haut['tx_optimal'] >= r_bas['tx_optimal'], (
            f"Avec plus de FP, tx_optimal devrait être ≥ : "
            f"{r_haut['tx_optimal_pct']:.3f}% vs {r_bas['tx_optimal_pct']:.3f}%"
        )
