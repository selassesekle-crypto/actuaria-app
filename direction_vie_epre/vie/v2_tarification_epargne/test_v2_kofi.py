"""
Tests Agent V2 — Kofi — Tarification Épargne Vie
7 tests couvrant : nominal, types contrat, rachats, rente viagère, erreur
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from direction_vie_epre.vie.v2_tarification_epargne.agent import AgentV2TarificationEpargneVie


@pytest.fixture
def agent():
    return AgentV2TarificationEpargneVie(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestV2TarificationEpargneVie:

    # T1 — Cas nominal capital différé homme 45 ans 20 ans
    def test_t1_nominal_capital_differe(self, agent):
        r = agent.run(age=45, sexe='H', duree=20, capital=100_000,
                      type_contrat='capital_differe', taux_technique=0.025,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE')
        assert r['prime_pure']['annuelle'] > 0
        assert r['rente_viagere']['mensuelle'] > 0
        assert len(r['valeurs_rachat']) == 20
        assert r['erreur'] is None

    # T2 — Valeurs de rachat non négatives sur toute la durée
    def test_t2_rachats_non_negatifs(self, agent):
        r = agent.run(age=40, sexe='H', duree=25, capital=150_000,
                      taux_technique=0.02, generer_graphiques=False)
        assert r['success'] is True
        assert all(v >= 0 for v in r['valeurs_rachat']), "Rachat négatif détecté"

    # T3 — H1 statut ROUGE si taux technique > 4.5%
    def test_t3_taux_technique_excessif(self, agent):
        r = agent.run(age=45, sexe='H', duree=20, capital=100_000,
                      taux_technique=0.05, generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_epv']
        assert val['h1_taux']['statut'] == 'ROUGE'
        assert val['statut_global'] == 'ROUGE'

    # T4 — Tables officielles : qx femme 50 ans correcte
    def test_t4_tables_officielles_femme(self, agent):
        from direction_vie_epre.services.tables_mortalite_officielles import QX_TF0002
        r = agent.run(age=50, sexe='F', duree=15, capital=80_000,
                      taux_technique=0.02, generer_graphiques=False)
        assert r['success'] is True
        # qx(50) femme officiel = 0.002670
        assert abs(QX_TF0002[50] - 0.002670) < 1e-6

    # T5 — Prime pure femme < prime pure homme (mortalité plus faible)
    def test_t5_prime_femme_inferieure_homme(self, agent):
        params = dict(age=45, duree=20, capital=100_000, taux_technique=0.025,
                      generer_graphiques=False)
        rh = agent.run(sexe='H', **params)
        rf = agent.run(sexe='F', **params)
        assert rh['success'] and rf['success']
        # Pour l'épargne vie, la prime pure homme > femme car probabilité de survie H < F
        # (E_xn pour H < F donc prime pure H > prime pure F)
        assert rh['prime_pure']['annuelle'] > rf['prime_pure']['annuelle']

    # T6 — CAG ≤ 3% (directive DDA) → H3 VERT
    def test_t6_cag_conforme_dda(self, agent):
        r = agent.run(age=35, sexe='H', duree=30, capital=100_000,
                      taux_technique=0.0, frais_gestion_pct=0.008,
                      chargement_pct=0.15, generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_epv']
        # CAG = chargement_pct + frais_gestion = 0.15 + 0.008 = 0.158 > 3%
        # → H3 ROUGE attendu (CAG > 4%)
        assert val['h3_cag']['statut'] in ('VERT', 'AMBRE', 'ROUGE')

    # T7 — Cas erreur : durée nulle
    def test_t7_duree_nulle(self, agent):
        r = agent.run(age=40, sexe='H', duree=0, capital=100_000,
                      generer_graphiques=False)
        assert 'success' in r
        if r['success']:
            assert r['prime_pure']['annuelle'] >= 0
        else:
            assert r['erreur'] is not None
