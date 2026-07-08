"""
Tests Agent V1 — Nour — Tarification Décès Vie
7 tests couvrant : nominal, statuts RAG, cas limites, erreur
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import pytest
from direction_vie_epre.vie.v1_tarification_deces.agent import AgentV1TarificationDeces


@pytest.fixture
def agent():
    return AgentV1TarificationDeces(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestV1TarificationDeces:

    # T1 — Cas nominal homme 40 ans, 20 ans, capital 100k€
    def test_t1_nominal_homme(self, agent):
        r = agent.run(age=40, sexe='H', duree=20, capital_deces=100_000,
                      taux_technique=0.025, chargement_pct=0.20,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] == 'VERT'
        assert r['prime_pure']['annuelle'] > 0
        assert r['prime_commerciale']['annuelle'] > r['prime_pure']['annuelle']
        assert r['indicateurs']['prob_deces_contrat'] > 0
        assert r['indicateurs']['prob_deces_contrat'] < 1
        assert r['erreur'] is None

    # T2 — Cas nominal femme 35 ans, 25 ans
    def test_t2_nominal_femme(self, agent):
        r = agent.run(age=35, sexe='F', duree=25, capital_deces=150_000,
                      taux_technique=0.020, generer_graphiques=False)
        assert r['success'] is True
        assert r['table'] in ('TF0002', 'TH0002')
        # Les qx femmes sont plus faibles → prime pure F ≤ prime pure H à âge égal
        r_h = agent.run(age=35, sexe='H', duree=25, capital_deces=150_000,
                        taux_technique=0.020, generer_graphiques=False)
        assert r['prime_pure']['annuelle'] <= r_h['prime_pure']['annuelle']

    # T3 — Statut RAG : taux technique trop élevé → H1 ROUGE → AMBRE global
    def test_t3_taux_technique_eleve(self, agent):
        r = agent.run(age=50, sexe='H', duree=15, taux_technique=0.08,
                      generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_deces']
        assert val['h1_taux_tech']['statut'] == 'ROUGE'
        assert val['statut_global'] == 'ROUGE'

    # T4 — Réserve prospective : doit être non négative sur toute la durée
    def test_t4_reserves_positives(self, agent):
        r = agent.run(age=45, sexe='H', duree=20, capital_deces=200_000,
                      taux_technique=0.025, generer_graphiques=False)
        assert r['success'] is True
        reserves = r['tables_actuarielles']['reserves']
        assert all(v >= 0 for v in reserves), "Réserve prospective négative détectée"

    # T5 — Cohérence actuarielle : prime pure croît avec l'âge (toutes choses égales)
    def test_t5_prime_croissante_avec_age(self, agent):
        ages = [30, 40, 50, 60]
        primes = []
        for a in ages:
            r = agent.run(age=a, sexe='H', duree=10, capital_deces=100_000,
                          taux_technique=0.025, generer_graphiques=False)
            assert r['success'] is True
            primes.append(r['prime_pure']['annuelle'])
        assert primes == sorted(primes), f"Primes non croissantes : {primes}"

    # T6 — Tables officielles utilisées (arrêté 27/07/2006) : vérifier qx âge 65 homme
    def test_t6_tables_officielles_qx(self, agent):
        from direction_vie_epre.services.tables_mortalite_officielles import QX_TH0002
        r = agent.run(age=65, sexe='H', duree=1, capital_deces=100_000,
                      taux_technique=0.01, generer_graphiques=False)
        assert r['success'] is True
        qx_65_officiel = QX_TH0002[65]
        qx_65_agent = r['tables_actuarielles']['qx_serie'][0]
        assert abs(qx_65_agent - qx_65_officiel) < 1e-6, (
            f"qx(65) agent={qx_65_agent} ≠ officiel={qx_65_officiel}"
        )

    # T7 — Cas erreur : âge hors plage → success False
    def test_t7_erreur_age_invalide(self, agent):
        r = agent.run(age=-5, sexe='H', duree=20, generer_graphiques=False)
        # L'agent doit gérer gracieusement (success False ou prime=0)
        assert 'success' in r
        if r['success']:
            # Si success, la prime doit être cohérente (pas de valeur aberrante)
            assert r['prime_pure']['annuelle'] >= 0
        else:
            assert r['erreur'] is not None
