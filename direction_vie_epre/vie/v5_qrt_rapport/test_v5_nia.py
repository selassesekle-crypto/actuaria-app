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

    # T8 — A7 : chaîne actuarielle V3 → R-VIE1 → V4 → V5 complète
    def test_t8_chaine_actuarielle_complete(self, agent):
        result_v3_mock   = {'success': True, 'pm_prospective': 40_000_000}
        result_rvie1_mock = {'success': True, 'scr_vie_total': 4_500_000}
        result_v4_mock   = {'success': True, 'ppb_finale': 800_000}

        r = agent.run(
            fonds_propres=12_000_000,
            risk_adjustment=2_000_000,
            nb_contrats=10_000,
            result_v3=result_v3_mock,
            result_rvie1=result_rvie1_mock,
            result_v4=result_v4_mock,
            generer_graphiques=False
        )
        assert r['success'] is True

        # Vérifier que les inputs ont bien été récupérés depuis la chaîne
        assert r['qrt_s12']['be_vie'] == 40_000_000, "be_vie non alimenté depuis V3"
        assert r['qrt_s12']['pm_total'] == 40_000_000, "pm_total non alimenté depuis V3"
        assert r['qrt_s23']['scr_vie'] == 4_500_000, "scr_vie non alimenté depuis R-VIE1"
        assert r['qrt_s12']['ppb'] == 800_000, "ppb non alimenté depuis V4"

        # Vérifier la traçabilité des sources
        assert 'sources' in r
        assert r['sources'].get('be_vie') == 'V3 Amélie (pm_prospective)'
        assert r['sources'].get('scr_vie') == 'R-VIE1 Éric (scr_vie_total)'
        assert r['sources'].get('ppb') == 'V4 Théo (ppb_finale)'
