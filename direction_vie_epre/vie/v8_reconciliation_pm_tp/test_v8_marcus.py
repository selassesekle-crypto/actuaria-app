"""
Tests Agent V8 — Marcus — Réconciliation PM/TP S2/IFRS 17
7 tests couvrant : nominal, écarts, RA, CSM/LC, chaîne V3/V5, limites
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from direction_vie_epre.vie.v8_reconciliation_pm_tp.agent import AgentV8ReconciliationPMTP


@pytest.fixture
def agent():
    return AgentV8ReconciliationPMTP(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestV8ReconciliationPMTP:

    # T1 — Cas nominal
    def test_t1_nominal(self, agent):
        r = agent.run(
            pm_sociale=50_000_000, be_vie=45_000_000,
            risk_adjustment_s2=2_000_000, csm=3_000_000,
            ra_ifrs17=1_500_000, taux_technique_pm=0.025,
            taux_sans_risque=0.03, generer_graphiques=False
        )
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert r['pm_ref']['valeur'] == 50_000_000
        assert r['tp_s2_ref']['tp_total'] == 47_000_000  # BE + RA
        assert r['ifrs17_ref']['lrc_total'] > 0
        assert r.get('erreur') is None

    # T2 — TP S2 = BE + RA
    def test_t2_tp_s2_calcul(self, agent):
        r = agent.run(
            pm_sociale=50e6, be_vie=40e6, risk_adjustment_s2=3e6,
            csm=2e6, generer_graphiques=False
        )
        assert r['success'] is True
        assert r['tp_s2_ref']['tp_total'] == 43_000_000
        assert r['tp_s2_ref']['be_vie'] == 40_000_000
        assert r['tp_s2_ref']['risk_adjustment'] == 3_000_000

    # T3 — LRC IFRS 17 = FCF + CSM
    def test_t3_lrc_ifrs17_calcul(self, agent):
        r = agent.run(
            pm_sociale=50e6, be_vie=45e6, risk_adjustment_s2=2e6,
            csm=4e6, ra_ifrs17=2e6, lc=0, generer_graphiques=False
        )
        assert r['success'] is True
        fcf_attendu = 45e6 + 2e6  # be + ra_ifrs17
        lrc_attendu = fcf_attendu + 4e6  # FCF + CSM
        assert r['ifrs17_ref']['fcf'] == fcf_attendu
        assert r['ifrs17_ref']['lrc_total'] == lrc_attendu
        assert r['ifrs17_ref']['contrat_profitable'] is True

    # T4 — C2 VERT si ratio TP/BE ∈ [1.0, 1.5]
    def test_t4_ratio_tp_be_conforme(self, agent):
        r = agent.run(
            pm_sociale=50e6, be_vie=45e6, risk_adjustment_s2=2e6,
            csm=3e6, generer_graphiques=False
        )
        assert r['success'] is True
        val = r['validation_recon']
        assert val['c2_ratio_tp_be']['statut'] == 'VERT'
        assert 1.0 <= r['tp_s2_ref']['ratio_tp_be'] <= 1.5

    # T5 — C3 AMBRE si CSM = 0
    def test_t5_csm_nul(self, agent):
        r = agent.run(
            pm_sociale=50e6, be_vie=45e6, risk_adjustment_s2=2e6,
            csm=0, lc=0, generer_graphiques=False
        )
        assert r['success'] is True
        val = r['validation_recon']
        assert val['c3_csm']['statut'] == 'AMBRE'

    # T6 — Alimentation depuis V3 et V5
    def test_t6_alimentation_depuis_v3_v5(self, agent):
        result_v3_mock = {'success': True, 'pm_prospective': 35_000_000}
        result_v5_mock = {
            'success': True,
            'qrt_s12': {'be_vie': 32_000_000, 'risk_adjustment': 1_500_000}
        }
        r = agent.run(
            result_v3=result_v3_mock, result_v5=result_v5_mock,
            csm=3e6, generer_graphiques=False
        )
        assert r['success'] is True
        assert r['pm_ref']['valeur'] == 35_000_000
        assert r['tp_s2_ref']['be_vie'] == 32_000_000
        assert r['tp_s2_ref']['risk_adjustment'] == 1_500_000
        assert r['sources'].get('be_vie') == 'V5 Nia (qrt_s12.be_vie)'
        assert r['sources'].get('pm_sociale') == 'V3 Amélie (pm_prospective)'

    # T7 — Réconciliation delta cohérente
    def test_t7_reconciliation_delta_coherente(self, agent):
        pm = 50_000_000
        be = 45_000_000
        ra = 2_000_000
        csm = 3_000_000
        ra17 = 1_500_000
        r = agent.run(
            pm_sociale=pm, be_vie=be, risk_adjustment_s2=ra,
            csm=csm, ra_ifrs17=ra17, generer_graphiques=False
        )
        assert r['success'] is True
        recon = r['reconciliation']
        # PM + delta_pm_tp = TP
        tp_recalcule = pm + recon['delta_pm_to_tp']['total']
        assert abs(tp_recalcule - recon['tp_s2']) < 1.0
        # TP + delta_tp_lrc = LRC
        lrc_recalcule = recon['tp_s2'] + recon['delta_tp_to_ifrs17']['total']
        assert abs(lrc_recalcule - recon['lrc_ifrs17']) < 1.0
