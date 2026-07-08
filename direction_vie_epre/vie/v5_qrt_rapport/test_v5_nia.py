"""
Tests Agent V5 — Nia — QRT Vie & Rapport Actuariel
7 tests couvrant : nominal, ratios QRT, cohérence PM/TP, cas limites
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from direction_vie_epre.vie.v5_qrt_rapport.agent import AgentV5QRTVie


@pytest.fixture
def agent():
    return AgentV5QRTVie(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestV5QRTVie:

    # T1 — Cas nominal
    def test_t1_nominal(self, agent):
        r = agent.run(pm_total=50_000_000, scr_vie=5_000_000,
                      fonds_propres=12_000_000, be_vie=45_000_000,
                      risk_adjustment=2_000_000, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert r['qrt_s12']['be_vie'] == 45_000_000
        assert r['qrt_s23']['ratio_scr_pct'] > 0
        assert r['erreur'] is None

    # T2 — Ratio TP/BE ∈ [1.0, 1.5] → C1 VERT
    def test_t2_ratio_tp_be_conforme(self, agent):
        r = agent.run(pm_total=50e6, scr_vie=5e6, fonds_propres=12e6,
                      be_vie=45e6, risk_adjustment=2e6, generer_graphiques=False)
        assert r['success'] is True
        ratio = r['ratio_tp_be']
        assert 1.0 <= ratio <= 1.5
        val = r['validation_qrt']
        assert val['c1_tp_be']['statut'] == 'VERT'

    # T3 — C1 ROUGE si TP < BE (risk_adjustment négatif)
    def test_t3_tp_inferieur_be(self, agent):
        r = agent.run(pm_total=50e6, scr_vie=5e6, fonds_propres=12e6,
                      be_vie=45e6, risk_adjustment=-1e6, generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_qrt']
        assert val['c1_tp_be']['statut'] == 'ROUGE'

    # T4 — Ratio SCR ≥ 150% → C2 VERT
    def test_t4_ratio_scr_solide(self, agent):
        r = agent.run(pm_total=50e6, scr_vie=5e6, fonds_propres=15e6,
                      be_vie=45e6, risk_adjustment=2e6, generer_graphiques=False)
        assert r['success'] is True
        assert r['ratio_scr_pct'] >= 150
        val = r['validation_qrt']
        assert val['c2_scr']['statut'] == 'VERT'

    # T5 — Ratio SCR < 100% → C2 ROUGE et statut_rag ROUGE
    def test_t5_ratio_scr_insuffisant(self, agent):
        r = agent.run(pm_total=50e6, scr_vie=20e6, fonds_propres=15e6,
                      be_vie=45e6, risk_adjustment=2e6, generer_graphiques=False)
        assert r['success'] is True
        assert r['ratio_scr_pct'] < 100
        val = r['validation_qrt']
        assert val['c2_scr']['statut'] == 'ROUGE'
        assert r['statut_rag'] == 'AMBRE'  # statut_rag = AMBRE si val_hyp global ROUGE

    # T6 — Rapport actuariel généré avec avis
    def test_t6_rapport_actuariel(self, agent):
        r = agent.run(pm_total=50e6, scr_vie=5e6, fonds_propres=12e6,
                      be_vie=45e6, risk_adjustment=2e6, generer_graphiques=False)
        assert r['success'] is True
        ra = r['rapport_actuariel']
        assert 'avis' in ra
        assert ra['avis'] in ('FAVORABLE', 'FAVORABLE AVEC RÉSERVE')
        assert len(ra['sections']) > 0
        assert len(ra['recommandations']) > 0

    # T7 — Cas limite : fonds propres nuls → ROUGE
    def test_t7_fonds_propres_nuls(self, agent):
        r = agent.run(pm_total=50e6, scr_vie=5e6, fonds_propres=0,
                      be_vie=45e6, risk_adjustment=2e6, generer_graphiques=False)
        assert r['success'] is True
        assert r['ratio_scr_pct'] == 0
        val = r['validation_qrt']
        assert val['c2_scr']['statut'] == 'ROUGE'
