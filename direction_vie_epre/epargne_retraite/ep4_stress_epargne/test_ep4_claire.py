"""
Tests Agent EP4 — Claire — Stress Testing Épargne-Retraite
7 tests couvrant : nominal, scénarios, ratios, ORSA, cas limites
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

import pytest
from direction_vie_epre.epargne_retraite.ep4_stress_epargne.agent import AgentEP4StressEpargne


@pytest.fixture
def agent():
    return AgentEP4StressEpargne(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestEP4StressEpargne:

    # T1 — Cas nominal
    def test_t1_nominal(self, agent):
        r = agent.run(encours_total=50_000_000, actifs_total=55_000_000,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert r['ratio_base'] > 0
        assert len(r['scenarios']) == 5
        assert r.get('erreur') is None  # clé absente du dict success — comportement normal

    # T2 — Ratio base = actifs / encours × 100
    def test_t2_ratio_base_calcul(self, agent):
        encours = 50_000_000
        actifs  = 55_000_000
        r = agent.run(encours_total=encours, actifs_total=actifs,
                      generer_graphiques=False)
        assert r['success'] is True
        ratio_attendu = actifs / encours * 100
        assert abs(r['ratio_base'] - ratio_attendu) < 0.01

    # T3 — Scénario rachats massifs : actifs stressés = actifs - 40%
    def test_t3_scenario_rachats_massifs(self, agent):
        encours = 50_000_000
        actifs  = 55_000_000
        r = agent.run(encours_total=encours, actifs_total=actifs,
                      generer_graphiques=False)
        assert r['success'] is True
        s_rachat = next((s for s in r['scenarios'] if 'achat' in s['nom'].lower()), None)
        assert s_rachat is not None
        assert s_rachat['actifs_stresses'] == round(actifs - actifs * 0.40, 0)

    # T4 — C1 VERT si ratio_base ≥ 100%
    def test_t4_c1_ratio_base_solide(self, agent):
        r = agent.run(encours_total=50_000_000, actifs_total=60_000_000,
                      generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_ep4']
        assert val['c1_base']['statut'] == 'VERT'

    # T5 — C1 ROUGE si ratio_base < 100%
    def test_t5_c1_ratio_base_insuffisant(self, agent):
        r = agent.run(encours_total=60_000_000, actifs_total=50_000_000,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['ratio_base'] < 100
        val = r['validation_ep4']
        assert val['c1_base']['statut'] == 'ROUGE'

    # T6 — Statut RAG ROUGE si au moins un scénario ROUGE
    def test_t6_statut_rouge_si_scenario_rouge(self, agent):
        # Actifs très faibles → plusieurs scénarios ROUGE
        r = agent.run(encours_total=50_000_000, actifs_total=45_000_000,
                      generer_graphiques=False)
        assert r['success'] is True
        nb_rouge = sum(1 for s in r['scenarios'] if s['rag'] == '🔴 ROUGE')
        if nb_rouge > 0:
            assert r['statut_rag'] == 'ROUGE'

    # T7 — result_ep3 alimenté : encours récupéré depuis EP3
    def test_t7_alimentation_depuis_ep3(self, agent):
        result_ep3_mock = {
            'success': True,
            'provisions': {'pm_encours': 40_000_000}
        }
        r = agent.run(result_ep3=result_ep3_mock, actifs_total=55_000_000,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['ratio_base'] == round(55_000_000 / 40_000_000 * 100, 1)
