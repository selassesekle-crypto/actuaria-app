"""Tests Agent V9 — Élise — Embedded Value Simplifiée (7 tests)"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
from direction_vie_epre.vie.v9_embedded_value.agent import AgentV9EmbeddedValue

@pytest.fixture
def agent():
    return AgentV9EmbeddedValue(models_path='/tmp/actuaria/models',
                                 audit_path='/tmp/actuaria/audit', verbose=False)

class TestV9EmbeddedValue:

    # T1 — Cas nominal : structure complète du résultat
    def test_t1_nominal(self, agent):
        r = agent.run(actifs_marche=60e6, pm_s2=50e6, risk_adjustment=2e6,
                      scr_vie=5e6, taux_reference=0.03, taux_coc=0.06,
                      marge_sur_services=0.015, duree_moyenne=15,
                      primes_nouvelles=5e6, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert r.get('erreur') is None
        # Clés obligatoires
        for key in ['ane', 'vif', 'ev', 'vnb', 'va_profits', 'va_coc', 'ratios']:
            assert key in r, f"Clé manquante : {key}"

    # T2 — ANE = actifs − TP S2
    def test_t2_ane_calcul(self, agent):
        r = agent.run(actifs_marche=60e6, pm_s2=50e6, risk_adjustment=2e6,
                      generer_graphiques=False)
        assert r['success'] is True
        tp_s2_attendu = 50e6 + 2e6  # BE + RA
        assert r['tp_s2'] == tp_s2_attendu
        assert r['ane'] == round(60e6 - tp_s2_attendu, 0)

    # T3 — EV = ANE + VIF (identité fondamentale)
    def test_t3_ev_ane_plus_vif(self, agent):
        r = agent.run(actifs_marche=60e6, pm_s2=50e6, risk_adjustment=2e6,
                      scr_vie=5e6, generer_graphiques=False)
        assert r['success'] is True
        assert abs(r['ev'] - (r['ane'] + r['vif'])) < 1.0, (
            f"EV={r['ev']} ≠ ANE+VIF={r['ane']+r['vif']}"
        )

    # T4 — ROUGE si ANE négatif (actifs < TP S2)
    def test_t4_rouge_si_ane_negatif(self, agent):
        r = agent.run(actifs_marche=40e6, pm_s2=50e6, risk_adjustment=2e6,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['ane'] < 0
        assert r['statut_rag'] == 'ROUGE'
        assert r['validation_ev']['e1_ane']['statut'] == 'ROUGE'

    # T5 — VIF positif si marge sur services > CoC/PM
    def test_t5_vif_positif_si_marge_suffisante(self, agent):
        r = agent.run(actifs_marche=60e6, pm_s2=50e6, risk_adjustment=2e6,
                      scr_vie=1e6, marge_sur_services=0.03,
                      taux_coc=0.06, taux_reference=0.03, duree_moyenne=15,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['vif'] > 0, f"VIF devrait être positif avec marge 3% et SCR faible (VIF={r['vif']})"

    # T6 — Alimentation depuis V3 et V4
    def test_t6_alimentation_depuis_v3_v4(self, agent):
        result_v3_mock = {'success': True, 'pm_prospective': 45_000_000}
        result_v4_mock = {
            'success': True,
            'pb_reglementaire_min': 900_000,  # 2% de 45M
            'pm_total': 45_000_000,
        }
        r = agent.run(actifs_marche=55e6, risk_adjustment=2e6, scr_vie=5e6,
                      result_v3=result_v3_mock, result_v4=result_v4_mock,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['tp_s2'] == 45_000_000 + 2_000_000
        assert r['sources'].get('pm_s2') == 'V3 Amélie (pm_prospective)'
        assert 'marge_sur_services' in r['sources']

    # T7 — Décomposition ΔEV si ev_n1 fourni
    def test_t7_decomposition_delta_ev(self, agent):
        r = agent.run(actifs_marche=60e6, pm_s2=50e6, risk_adjustment=2e6,
                      scr_vie=5e6, ev_n1=7_000_000, generer_graphiques=False)
        assert r['success'] is True
        assert 'decomposition_delta_ev' in r
        d = r['decomposition_delta_ev']
        assert d['ev_n1'] == 7_000_000
        # ΔEV = EV_N − EV_N-1
        assert d['delta_ev'] == r['ev'] - 7_000_000
        # Cohérence : gain expérience = ΔEV − VNB − Unwinding
        gain_calc = d['delta_ev'] - d['vnb'] - d['unwinding']
        assert abs(d['gain_experience'] - gain_calc) < 1.0
