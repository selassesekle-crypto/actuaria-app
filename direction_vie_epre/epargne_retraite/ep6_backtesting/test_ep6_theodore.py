"""Tests Agent EP6 — Théodore — Backtesting Hypothèses EP-RE (7 tests)"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
from direction_vie_epre.epargne_retraite.ep6_backtesting.agent import AgentEP6Backtesting

@pytest.fixture
def agent():
    return AgentEP6Backtesting(models_path='/tmp/actuaria/models',
                                audit_path='/tmp/actuaria/audit', verbose=False)

@pytest.fixture
def hyp_std():
    return {'taux_mortalite': 0.005, 'taux_rotation': 0.05,
            'taux_revalorisation': 0.020, 'taux_actu': 0.035,
            'taux_rendement': 0.040}

@pytest.fixture
def obs_proches(hyp_std):
    """Observations proches des hypothèses → VERT"""
    return {k: v * 1.03 for k, v in hyp_std.items()}

class TestEP6Backtesting:

    def test_t1_nominal(self, agent, hyp_std, obs_proches):
        r = agent.run(hypotheses_n1=hyp_std, observations_n=obs_proches,
                      dbo_debut_n=10e6, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert len(r['ecarts']) == 5
        assert r['dbo_debut_n'] == 10_000_000
        assert r.get('erreur') is None

    def test_t2_gain_actuariel_taux_actu(self, agent):
        """Taux actu réel > hypothèse → gain actuariel (DBO baisse)"""
        hyp = {'taux_actu': 0.030, 'taux_mortalite': 0.005,
               'taux_rotation': 0.05, 'taux_revalorisation': 0.02,
               'taux_rendement': 0.04}
        obs = {'taux_actu': 0.040,  # taux réel plus élevé → DBO plus basse
               'taux_mortalite': 0.005, 'taux_rotation': 0.05,
               'taux_revalorisation': 0.02, 'taux_rendement': 0.04}
        r = agent.run(hypotheses_n1=hyp, observations_n=obs,
                      dbo_debut_n=10e6, generer_graphiques=False)
        assert r['success'] is True
        # Écart taux actu : hyp 3% < obs 4% → écart négatif
        # → impact_dbo positif (car sensibilité négative × écart négatif = positif)
        assert r['ecarts']['taux_actu']['nature'] == 'GAIN'
        assert r['gain_actuariel'] > 0

    def test_t3_perte_actuarielle_revalo(self, agent):
        """Revalorisation réelle > hypothèse → perte actuarielle (DBO monte)"""
        hyp = {'taux_revalorisation': 0.020, 'taux_mortalite': 0.005,
               'taux_rotation': 0.05, 'taux_actu': 0.035, 'taux_rendement': 0.04}
        obs = {'taux_revalorisation': 0.035,  # salaires ont plus augmenté
               'taux_mortalite': 0.005, 'taux_rotation': 0.05,
               'taux_actu': 0.035, 'taux_rendement': 0.04}
        r = agent.run(hypotheses_n1=hyp, observations_n=obs,
                      dbo_debut_n=10e6, generer_graphiques=False)
        assert r['success'] is True
        assert r['ecarts']['taux_revalorisation']['nature'] == 'PERTE'
        assert r['perte_actuarielle'] < 0

    def test_t4_impact_dbo_coherent(self, agent, hyp_std, obs_proches):
        r = agent.run(hypotheses_n1=hyp_std, observations_n=obs_proches,
                      dbo_debut_n=10e6, generer_graphiques=False)
        assert r['success'] is True
        # dbo_reestimee = dbo_debut - impact_total
        dbo_attendue = r['dbo_debut_n'] - r['impact_total_dbo']
        assert abs(r['dbo_reestimee'] - dbo_attendue) < 1.0

    def test_t5_statut_rouge_si_grand_ecart(self, agent):
        """Écart > 25% sur plusieurs paramètres → ROUGE"""
        hyp = {'taux_mortalite': 0.005, 'taux_rotation': 0.05,
               'taux_revalorisation': 0.02, 'taux_actu': 0.035,
               'taux_rendement': 0.04}
        obs = {'taux_mortalite': 0.010,   # +100% écart → ROUGE
               'taux_rotation': 0.10,     # +100% écart → ROUGE
               'taux_revalorisation': 0.04, 'taux_actu': 0.020,
               'taux_rendement': 0.025}
        r = agent.run(hypotheses_n1=hyp, observations_n=obs,
                      dbo_debut_n=10e6, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] == 'ROUGE'

    def test_t6_alimentation_depuis_ep1(self, agent, hyp_std, obs_proches):
        result_ep1_mock = {
            'success': True,
            'ias19': {'dbo_total': 8_000_000}
        }
        r = agent.run(hypotheses_n1=hyp_std, observations_n=obs_proches,
                      result_ep1=result_ep1_mock, generer_graphiques=False)
        assert r['success'] is True
        assert r['dbo_debut_n'] == 8_000_000
        assert r['sources'].get('dbo_debut_n') == 'EP1 Henri (ias19.dbo_total)'

    def test_t7_hypotheses_par_defaut(self, agent):
        """Sans hypothèses fournies → utilise les défauts → résultat valide"""
        r = agent.run(dbo_debut_n=5e6, generer_graphiques=False)
        assert r['success'] is True
        assert len(r['ecarts']) == 5
        assert r['dbo_debut_n'] == 5_000_000
