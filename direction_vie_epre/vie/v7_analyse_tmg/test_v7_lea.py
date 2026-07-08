"""
Tests Agent V7 — Léa — Analyse Contrats Anciens TMG
7 tests couvrant : nominal, underwater, coussin PPB, SCR taux, chaîne, limites
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from direction_vie_epre.vie.v7_analyse_tmg.agent import AgentV7AnalyseTMG


@pytest.fixture
def agent():
    return AgentV7AnalyseTMG(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


@pytest.fixture
def tranches_std():
    return [
        {'tmg': 0.045, 'pm': 5_000_000,  'duree': 8,  'label': 'TMG 4.5%'},
        {'tmg': 0.035, 'pm': 20_000_000, 'duree': 12, 'label': 'TMG 3.5%'},
        {'tmg': 0.005, 'pm': 10_000_000, 'duree': 8,  'label': 'TMG 0.5%'},
    ]


class TestV7AnalyseTMG:

    # T1 — Cas nominal
    def test_t1_nominal(self, agent, tranches_std):
        r = agent.run(tranches_tmg=tranches_std, rendement_actifs=0.03,
                      ppb_disponible=2_000_000, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert r['pm_total'] == 35_000_000
        assert len(r['analyses_tranches']) == 3
        assert r.get('erreur') is None

    # T2 — Détection underwater : TMG > rendement actifs
    def test_t2_detection_underwater(self, agent):
        tranches = [
            {'tmg': 0.04, 'pm': 10_000_000, 'duree': 10, 'label': 'Underwater'},
            {'tmg': 0.02, 'pm': 10_000_000, 'duree': 10, 'label': 'OK'},
        ]
        r = agent.run(tranches_tmg=tranches, rendement_actifs=0.03,
                      generer_graphiques=False)
        assert r['success'] is True
        analyses = {a['label']: a for a in r['analyses_tranches']}
        assert analyses['Underwater']['underwater'] is True
        assert analyses['Underwater']['spread_pct'] < 0
        assert analyses['OK']['underwater'] is False
        assert analyses['OK']['spread_pct'] > 0

    # T3 — pm_underwater_total cohérent avec les tranches underwater
    def test_t3_pm_underwater_total(self, agent):
        tranches = [
            {'tmg': 0.05, 'pm': 8_000_000,  'duree': 5},
            {'tmg': 0.04, 'pm': 12_000_000, 'duree': 8},
            {'tmg': 0.01, 'pm': 5_000_000,  'duree': 6},
        ]
        r = agent.run(tranches_tmg=tranches, rendement_actifs=0.03,
                      generer_graphiques=False)
        assert r['success'] is True
        # Les deux premières tranches sont underwater (TMG > 3%)
        assert r['pm_underwater'] == 20_000_000
        assert abs(r['pct_underwater'] - 20_000_000 / 25_000_000 * 100) < 0.1

    # T4 — H2 ROUGE si PPB couvre < 3 ans
    def test_t4_h2_ppb_insuffisante(self, agent):
        tranches = [{'tmg': 0.05, 'pm': 50_000_000, 'duree': 10}]
        # Coût annuel = (5%-3%) × 50M = 1M€/an → PPB 500k€ couvre 0.5 ans
        r = agent.run(tranches_tmg=tranches, rendement_actifs=0.03,
                      ppb_disponible=500_000, generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_tmg']
        assert val['h2_ppb']['statut'] == 'ROUGE'

    # T5 — Statut VERT si portefeuille sans underwater
    def test_t5_statut_vert_sans_underwater(self, agent):
        tranches = [
            {'tmg': 0.005, 'pm': 30_000_000, 'duree': 10},
            {'tmg': 0.010, 'pm': 20_000_000, 'duree': 8},
        ]
        r = agent.run(tranches_tmg=tranches, rendement_actifs=0.04,
                      ppb_disponible=5_000_000, generer_graphiques=False)
        assert r['success'] is True
        assert r['pm_underwater'] == 0
        assert r['statut_rag'] == 'VERT'
        val = r['validation_tmg']
        assert val['h1_underwater']['statut'] == 'VERT'

    # T6 — Alimentation depuis V4 (ppb_disponible)
    def test_t6_alimentation_depuis_v4(self, agent, tranches_std):
        result_v4_mock = {'success': True, 'ppb_finale': 3_000_000}
        r = agent.run(tranches_tmg=tranches_std, rendement_actifs=0.03,
                      result_v4=result_v4_mock, generer_graphiques=False)
        assert r['success'] is True
        assert r['ppb_disponible'] == 3_000_000
        assert r['sources'].get('ppb') == 'V4 Théo (ppb_finale)'

    # T7 — Tranches par défaut si rien fourni
    def test_t7_tranches_defaut(self, agent):
        r = agent.run(rendement_actifs=0.03, ppb_disponible=2_000_000,
                      generer_graphiques=False)
        assert r['success'] is True
        assert len(r['analyses_tranches']) == 4  # 4 tranches par défaut
        assert r['pm_total'] > 0
