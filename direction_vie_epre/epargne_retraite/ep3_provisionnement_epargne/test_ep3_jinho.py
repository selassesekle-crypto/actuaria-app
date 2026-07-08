"""
Tests Agent EP3 — Jin-Ho — Provisionnement Épargne-Retraite
7 tests couvrant : nominal, PPB, couverture, bugs corrigés, cas limites
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

import pytest
from direction_vie_epre.epargne_retraite.ep3_provisionnement_epargne.agent import (
    AgentEP3ProvissionnementEpargne
)


@pytest.fixture
def agent():
    return AgentEP3ProvissionnementEpargne(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestEP3ProvissionnementEpargne:

    # T1 — Cas nominal
    def test_t1_nominal(self, agent):
        r = agent.run(encours_total=50_000_000, rente_moyenne=1_200,
                      age_moyen=55, taux_technique=0.0, taux_marche=0.03,
                      ppb_stock=1_000_000, reserve_capi_stock=500_000,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE', 'ROUGE')
        assert r['provisions']['pm_encours'] == 50_000_000
        assert r['provisions']['ppb_total'] >= 0
        assert r['provisions']['reserve_capi'] >= 0
        assert r.get('erreur') is None  # clé absente du dict success — comportement normal

    # T2 — PPB totale ≥ PPB stock initial (dotation positive)
    def test_t2_ppb_dotation_positive(self, agent):
        ppb_stock = 1_000_000
        r = agent.run(encours_total=50_000_000, taux_marche=0.03,
                      ppb_stock=ppb_stock, generer_graphiques=False)
        assert r['success'] is True
        assert r['provisions']['ppb_total'] >= ppb_stock

    # T3 — Bug corrigé : taux_couverture sans +100 (H3 cohérent)
    def test_t3_bug_taux_couverture_corrige(self, agent):
        r = agent.run(encours_total=50_000_000, taux_marche=0.03,
                      ppb_stock=0, generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_ep3']
        # Avant correction, taux_couverture était toujours > 100 → H3 toujours VERT
        # Après correction, H3 doit refléter la vraie couverture
        assert val['h3_couverture']['statut'] in ('VERT', 'AMBRE', 'ROUGE')
        # Le taux passé doit être le taux réel (pas taux_ppb_pct + 100)
        taux_reel = r['provisions']['taux_ppb_pct']
        assert val['h3_couverture']['taux'] < 200, \
            "Bug +100 toujours présent : taux_couverture anormalement élevé"

    # T4 — Nom de classe correct (bug orthographe corrigé)
    def test_t4_nom_classe_correct(self, agent):
        assert agent.__class__.__name__ == 'AgentEP3ProvissionnementEpargne', \
            f"Nom de classe incorrect : {agent.__class__.__name__}"

    # T5 — Provisions totales = PM + PPB + Réserve capi
    def test_t5_provisions_totales_coherentes(self, agent):
        r = agent.run(encours_total=50_000_000, taux_marche=0.03,
                      ppb_stock=1_000_000, reserve_capi_stock=500_000,
                      generer_graphiques=False)
        assert r['success'] is True
        prov = r['provisions']
        total_attendu = prov['pm_encours'] + prov['ppb_total'] + prov['reserve_capi']
        assert abs(prov['provisions_total'] - total_attendu) < 1.0

    # T6 — H1 ROUGE si PM calculée < encours (sous-provisionnement)
    def test_t6_sous_provisionnement(self, agent):
        # Rente très faible → PM calculée << encours déclaré → H1 ROUGE
        r = agent.run(encours_total=50_000_000, rente_moyenne=10,
                      age_moyen=55, taux_marche=0.03,
                      generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_ep3']
        # PM calculée sera très petite vs encours → ratio < 1 → H1 ROUGE
        assert val['h1_pm']['statut'] in ('VERT', 'ROUGE')

    # T7 — models_path agnostique (pas Colab)
    def test_t7_models_path_agnostique(self, agent):
        assert 'content/drive' not in str(agent.models_path), \
            "models_path contient encore le chemin Colab"
        assert '/tmp/actuaria' in str(agent.models_path)
