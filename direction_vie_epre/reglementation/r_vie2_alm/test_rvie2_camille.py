"""
Tests Agent R-VIE2 — Camille — RSR & SFCR Vie
7 tests couvrant : nominal, sections SFCR, stabilité SCR, TP/BE, cas limites
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

import pytest
from direction_vie_epre.reglementation.r_vie2_alm.agent import AgentRVIE2RSRSFCRVie


@pytest.fixture
def agent():
    return AgentRVIE2RSRSFCRVie(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestRVIE2RSRSFCRVie:

    # T1 — Cas nominal
    def test_t1_nominal(self, agent):
        r = agent.run(scr_vie=5_000_000, fonds_propres=12_000_000,
                      be_vie=45_000_000, pm_total=50_000_000,
                      ratio_scr_n1=200.0, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert 'sfcr' in r
        assert 'rsr' in r
        assert r['avis_fa'] in ('FAVORABLE', 'FAVORABLE AVEC RÉSERVE')
        assert r['erreur'] is None

    # T2 — SFCR contient 5 sections A-E
    def test_t2_sfcr_5_sections(self, agent):
        r = agent.run(scr_vie=5e6, fonds_propres=12e6, be_vie=45e6,
                      pm_total=50e6, generer_graphiques=False)
        assert r['success'] is True
        sections = list(r['sfcr'].keys())
        assert len(sections) == 5
        assert 'A_activite' in sections
        assert 'E_gestion_capital' in sections

    # T3 — H1 VERT si toutes sections SFCR VERT
    def test_t3_h1_sections_toutes_vertes(self, agent):
        r = agent.run(scr_vie=5e6, fonds_propres=15e6, be_vie=45e6,
                      pm_total=50e6, ratio_scr_n1=200.0, generer_graphiques=False)
        assert r['success'] is True
        nb_vert = sum(1 for s in r['sfcr'].values() if s['statut'] == 'VERT')
        val = r['validation_rvie2']
        if nb_vert == 5:
            assert val['h1_sections']['statut'] == 'VERT'

    # T4 — H2 VERT si ratio SCR stable ou en hausse vs N-1
    def test_t4_h2_stabilite_scr(self, agent):
        # Ratio N > ratio N-1 → amélioration
        r = agent.run(scr_vie=5e6, fonds_propres=15e6, be_vie=45e6,
                      pm_total=50e6, ratio_scr_n1=200.0, generer_graphiques=False)
        assert r['success'] is True
        ratio_n = r['ratio_scr_pct']
        val = r['validation_rvie2']
        if ratio_n >= 200.0:
            assert val['h2_stabilite']['statut'] == 'VERT'

    # T5 — H2 ROUGE si dégradation > 20pp vs N-1
    def test_t5_h2_degradation_scr(self, agent):
        r = agent.run(scr_vie=5e6, fonds_propres=8e6, be_vie=45e6,
                      pm_total=50e6, ratio_scr_n1=300.0, generer_graphiques=False)
        assert r['success'] is True
        variation = r['ratio_scr_pct'] - 300.0
        if variation < -20:
            val = r['validation_rvie2']
            assert val['h2_stabilite']['statut'] == 'ROUGE'

    # T6 — H3 VERT si TP/BE ∈ [1.0, 1.5]
    def test_t6_h3_tp_be_conforme(self, agent):
        r = agent.run(scr_vie=5e6, fonds_propres=12e6, be_vie=45e6,
                      pm_total=50e6, generer_graphiques=False)
        assert r['success'] is True
        # tp_vie = be_vie * 1.08 → ratio = 1.08 ∈ [1.0, 1.5]
        assert 1.0 <= r['ratio_tp_be'] <= 1.5
        val = r['validation_rvie2']
        assert val['h3_valorisation']['statut'] == 'VERT'

    # T7 — RSR contient les changements documentés
    def test_t7_rsr_changements(self, agent):
        r = agent.run(scr_vie=5e6, fonds_propres=12e6, be_vie=45e6,
                      pm_total=50e6, generer_graphiques=False)
        assert r['success'] is True
        rsr = r['rsr']
        assert 'changements' in rsr
        assert isinstance(rsr['changements'], list)
        assert 'plan_capital' in rsr
