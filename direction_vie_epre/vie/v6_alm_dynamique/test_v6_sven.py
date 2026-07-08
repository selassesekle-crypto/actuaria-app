"""Tests Agent V6 — Sven — Projection ALM Dynamique (7 tests)"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
from direction_vie_epre.vie.v6_alm_dynamique.agent import AgentV6ALMDynamique

@pytest.fixture
def agent():
    return AgentV6ALMDynamique(models_path='/tmp/actuaria/models',
                                audit_path='/tmp/actuaria/audit', verbose=False)

class TestV6ALMDynamique:

    def test_t1_nominal(self, agent):
        r = agent.run(pm_initiale=50e6, actif_initiale=55e6, rendement_actifs=0.04,
                      taux_technique_pm=0.025, horizon=10, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert len(r['projection']) == 10
        assert r['pm_initiale'] == 50_000_000
        assert r['actif_initiale'] == 55_000_000
        assert r.get('erreur') is None

    def test_t2_ratio_couverture_initial(self, agent):
        r = agent.run(pm_initiale=50e6, actif_initiale=55e6,
                      horizon=5, generer_graphiques=False)
        assert r['success'] is True
        assert abs(r['ratio_couv_initial'] - 55e6 / 50e6) < 0.0001
        assert r['surplus_initial'] == 5_000_000

    def test_t3_sous_couverture_rouge(self, agent):
        """Actif < PM dès le départ → ROUGE"""
        r = agent.run(pm_initiale=50e6, actif_initiale=45e6,
                      horizon=5, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] == 'ROUGE'
        val = r['validation_alm']
        assert val['h1_couverture']['statut'] == 'ROUGE'

    def test_t4_duration_gap_calcul(self, agent):
        r = agent.run(pm_initiale=50e6, actif_initiale=55e6,
                      duration_actif=7.0, duration_passif=12.0,
                      horizon=5, generer_graphiques=False)
        assert r['success'] is True
        assert abs(r['duration_gap'] - 5.0) < 0.01
        # Gap > 4 ans → H2 ROUGE
        assert r['validation_alm']['h2_duration_gap']['statut'] == 'ROUGE'

    def test_t5_projection_decroissante(self, agent):
        """Les PM doivent décroître avec des sorties > revalorisation"""
        r = agent.run(pm_initiale=50e6, actif_initiale=55e6,
                      taux_technique_pm=0.02,
                      taux_prestations=0.03, taux_rachats=0.05,
                      horizon=10, generer_graphiques=False)
        # Sorties totales = 8% (prestations 3% + rachats 5%) > revalorisation 2%
        assert r['success'] is True
        pms = [p['pm'] for p in r['projection']]
        assert pms[-1] < pms[0], "PM doit décroître si sorties > revalorisation"

    def test_t6_alimentation_depuis_v3_v4(self, agent):
        result_v3_mock = {'success': True, 'pm_prospective': 35_000_000}
        result_v4_mock = {'success': True, 'tx_servi_cible': 0.030}
        r = agent.run(result_v3=result_v3_mock, result_v4=result_v4_mock,
                      actif_initiale=40e6, horizon=5, generer_graphiques=False)
        assert r['success'] is True
        assert r['pm_initiale'] == 35_000_000
        assert r['sources'].get('pm_initiale') == 'V3 Amélie (pm_prospective)'
        assert r['sources'].get('taux_technique_pm') == 'V4 Théo (tx_servi_cible)'

    def test_t7_stress_taux_coherent(self, agent):
        r = agent.run(pm_initiale=50e6, actif_initiale=55e6,
                      duration_actif=7.0, duration_passif=10.0,
                      taux_sans_risque=0.03, horizon=5, generer_graphiques=False)
        assert r['success'] is True
        stress = r['stress']
        # +200bp : actif baisse (duration_actif × actif × choc)
        assert stress['choc_plus_200bp']['impact_actif'] < 0  # hausse taux → actif baisse
        # Les ratios de couverture stress sont calculés
        assert 'ratio_couv' in stress['choc_plus_200bp']
        assert 'ratio_couv' in stress['choc_moins_200bp']
