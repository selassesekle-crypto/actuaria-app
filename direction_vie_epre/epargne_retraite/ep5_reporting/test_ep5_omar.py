"""
Tests Agent EP5 — Omar — Reporting Épargne-Retraite
7 tests couvrant : nominal, agrégation KPIs, statut, rapports, cas limites
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

import pytest
from direction_vie_epre.epargne_retraite.ep5_reporting.agent import AgentEP5ReportingEpargne


@pytest.fixture
def agent():
    return AgentEP5ReportingEpargne(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


@pytest.fixture
def result_ep1_mock():
    return {
        'success': True, 'statut_rag': 'VERT',
        'ias19': {'dbo_total': 10_000_000, 'service_cost': 500_000, 'interest_cost': 350_000}
    }


@pytest.fixture
def result_ep2_mock():
    return {
        'success': True, 'statut_rag': 'VERT',
        'tarification': {
            'cotisation_brute_annuelle': 3_600,
            'rente_mensuelle': 620,
            'taux_remplacement_pct': 18.5
        }
    }


@pytest.fixture
def result_ep3_mock():
    return {
        'success': True, 'statut_rag': 'VERT',
        'provisions': {'pm_encours': 50_000_000, 'ppb_total': 1_200_000, 'reserve_capi': 600_000}
    }


@pytest.fixture
def result_ep4_mock():
    return {
        'success': True, 'statut_rag': 'AMBRE',
        'ratio_base': 110.0,
        'scenarios': [{'rag': '🟡 AMBRE'}, {'rag': '🟢 VERT'},
                      {'rag': '🟢 VERT'}, {'rag': '🟡 AMBRE'}, {'rag': '🟢 VERT'}]
    }


class TestEP5ReportingEpargne:

    # T1 — Cas nominal sans résultats amont
    def test_t1_nominal_sans_amont(self, agent):
        r = agent.run(client_nom='Client Test', generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] == 'VERT'  # aucun statut amont → VERT par défaut
        assert len(r['rapports_disponibles']) > 0
        assert r.get('erreur') is None  # clé absente du dict success — comportement normal

    # T2 — KPIs agrégés depuis EP1
    def test_t2_kpis_depuis_ep1(self, agent, result_ep1_mock):
        r = agent.run(result_ep1=result_ep1_mock, generer_graphiques=False)
        assert r['success'] is True
        kpis = r['kpis_cles']
        assert kpis['DBO_IAS19'] == 10_000_000
        assert kpis['service_cost'] == 500_000

    # T3 — KPIs agrégés depuis EP2 et EP3
    def test_t3_kpis_depuis_ep2_ep3(self, agent, result_ep2_mock, result_ep3_mock):
        r = agent.run(result_ep2=result_ep2_mock, result_ep3=result_ep3_mock,
                      generer_graphiques=False)
        assert r['success'] is True
        kpis = r['kpis_cles']
        assert kpis['rente_mensuelle'] == 620
        assert kpis['pm_totale'] == 50_000_000

    # T4 — Statut RAG AMBRE si EP4 AMBRE
    def test_t4_statut_rag_ambre(self, agent, result_ep4_mock):
        r = agent.run(result_ep4=result_ep4_mock, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] == 'AMBRE'

    # T5 — Rapports disponibles contiennent les références réglementaires
    def test_t5_rapports_references_reglementaires(self, agent):
        r = agent.run(generer_graphiques=False)
        assert r['success'] is True
        refs = [rp.get('reference', '') for rp in r['rapports_disponibles']]
        assert any('IAS 19' in ref or 'PACTE' in ref or 'EIOPA' in ref or 'DARES' in ref
                   for ref in refs)

    # T6 — Commentaire contient le nom du client
    def test_t6_commentaire_client(self, agent):
        nom = 'Mutuelle Alpha Prévoyance'
        r = agent.run(client_nom=nom, generer_graphiques=False)
        assert r['success'] is True
        assert nom in r['commentaire']

    # T7 — Chaîne complète EP1→EP2→EP3→EP4→EP5
    def test_t7_chaine_complete(self, agent, result_ep1_mock, result_ep2_mock,
                                 result_ep3_mock, result_ep4_mock):
        r = agent.run(
            result_ep1=result_ep1_mock, result_ep2=result_ep2_mock,
            result_ep3=result_ep3_mock, result_ep4=result_ep4_mock,
            client_nom='Client CAC40', actuaire_resp='M. Dupont IA',
            generer_graphiques=False
        )
        assert r['success'] is True
        kpis = r['kpis_cles']
        assert 'DBO_IAS19' in kpis
        assert 'rente_mensuelle' in kpis
        assert 'pm_totale' in kpis
        assert 'ratio_base' in kpis
        assert r['statut_rag'] == 'AMBRE'  # EP4 AMBRE
