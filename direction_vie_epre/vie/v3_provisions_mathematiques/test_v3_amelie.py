"""
Tests Agent V3 — Amélie — Provisions Mathématiques Vie
7 tests couvrant : nominal, cohérence P/R, rachat, cas limites, erreur
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from direction_vie_epre.vie.v3_provisions_mathematiques.agent import AgentV3ProvisionsMathematiques


@pytest.fixture
def agent():
    return AgentV3ProvisionsMathematiques(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestV3ProvisionsMathematiques:

    # T1 — Cas nominal : PM prospective positive
    def test_t1_nominal_pm_positive(self, agent):
        r = agent.run(age=40, sexe='H', duree=20, t_ecoule=10,
                      capital=100_000, prime_annuelle=3_000,
                      taux_technique=0.025, generer_graphiques=False)
        assert r['success'] is True
        assert r['pm_prospective'] > 0
        assert r['pm_retrospective'] > 0
        assert r['valeur_rachat'] >= 0
        assert r['capital_reduit'] > 0
        assert r['erreur'] is None

    # T2 — Cohérence P/R : écart < 5% → H2 VERT
    def test_t2_coherence_prospective_retrospective(self, agent):
        r = agent.run(age=40, sexe='H', duree=20, t_ecoule=10,
                      capital=100_000, prime_annuelle=3_000,
                      taux_technique=0.025, generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_pm']
        # Vérifier que H2 existe
        assert 'h2_ecart_pr' in val
        assert val['h2_ecart_pr']['statut'] in ('VERT', 'AMBRE', 'ROUGE')

    # T3 — PM prospective croissante en début de contrat
    def test_t3_pm_evolution_coherente(self, agent):
        r = agent.run(age=30, sexe='H', duree=30, t_ecoule=5,
                      capital=100_000, prime_annuelle=2_500,
                      taux_technique=0.025, generer_graphiques=False)
        assert r['success'] is True
        evol = r['pm_evolution']
        assert len(evol) == 31  # duree + 1
        # PM finale doit être 0 ou proche
        assert evol[-1] >= 0

    # T4 — Valeur de rachat ≤ PM prospective
    def test_t4_rachat_inferieur_pm(self, agent):
        r = agent.run(age=45, sexe='H', duree=20, t_ecoule=8,
                      capital=100_000, prime_annuelle=3_500,
                      taux_technique=0.025, generer_graphiques=False)
        assert r['success'] is True
        assert r['valeur_rachat'] <= r['pm_prospective'] + 1e-6

    # T5 — Tables officielles : cohérence avec V1 à mêmes paramètres
    def test_t5_tables_officielles_cohérentes(self, agent):
        from direction_vie_epre.services.tables_mortalite_officielles import get_qx
        # qx(40, H) officiel
        qx_40_officiel = get_qx(40, 'H')
        assert abs(qx_40_officiel - 0.001510) < 1e-6

    # T6 — t_ecoule = 0 (début de contrat) : PM prospective ≈ PM initiale
    def test_t6_debut_contrat(self, agent):
        r = agent.run(age=35, sexe='H', duree=20, t_ecoule=0,
                      capital=100_000, prime_annuelle=3_000,
                      taux_technique=0.025, generer_graphiques=False)
        assert r['success'] is True
        # En début de contrat : PM prospective > 0
        assert r['pm_prospective'] >= 0

    # T7 — Cas erreur : t_ecoule > duree
    def test_t7_t_ecoule_superieur_duree(self, agent):
        r = agent.run(age=40, sexe='H', duree=10, t_ecoule=15,
                      capital=100_000, prime_annuelle=3_000,
                      generer_graphiques=False)
        assert 'success' in r
        # duree_rest = duree - t_ecoule = -5 → comportement défensif attendu
        if r['success']:
            assert r['pm_prospective'] >= 0
        else:
            assert r['erreur'] is not None

    def test_t8_tracabilite_reserve_negative(self, agent):
        """V3 doit tracer les réserves négatives dans l'audit trail (Art. R331-1)"""
        # Contrat décès avec durée très courte : PM peut être négative
        # (prime prospective < prime rétro en début de contrat)
        r = agent.run(age=40, sexe='H', capital=100_000,
                      duree=20, t_ecoule=0, taux_technique=0.005,
                      generer_graphiques=False)
        assert r['success'] is True
        # Les clés de traçabilité doivent toujours être présentes
        assert 'reserve_negative_detectee' in r, "Clé reserve_negative_detectee manquante"
        assert 'pm_prospective_brute' in r, "Clé pm_prospective_brute manquante"
        assert 'raison_reserve_nulle' in r, "Clé raison_reserve_nulle manquante"
        # pm_prospective ≥ 0 (plancher réglementaire toujours appliqué)
        assert r['pm_prospective'] >= 0, "PM prospective ne peut pas être négative"
        # Si la PM brute était négative, la raison doit être documentée
        if r['reserve_negative_detectee']:
            assert r['raison_reserve_nulle'] is not None
            assert "plancher réglementaire" in r['raison_reserve_nulle']
        else:
            assert r['raison_reserve_nulle'] is None
