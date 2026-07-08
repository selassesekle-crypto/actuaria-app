"""
Tests Agent EP2 — Salomé — Tarification Épargne-Retraite
7 tests couvrant : nominal, cotisation, rente, taux, cas limites, validation
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

import pytest
from direction_vie_epre.epargne_retraite.ep2_tarification_epargne.agent import AgentEP2TarificationEpargne


@pytest.fixture
def agent():
    return AgentEP2TarificationEpargne(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestEP2TarificationEpargne:

    # T1 — Cas nominal PER
    def test_t1_nominal_per(self, agent):
        r = agent.run(type_contrat='PER', capital_cible=100_000,
                      age_entree=35, age_retraite=65,
                      taux_technique=0.0, taux_marche=0.03,
                      generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] in ('VERT', 'AMBRE')
        assert r['tarification']['cotisation_brute_annuelle'] > 0
        assert r['tarification']['rente_mensuelle'] > 0
        assert r.get('erreur') is None  # clé absente du dict success — comportement normal

    # T2 — Cotisation décroît quand le taux net augmente
    def test_t2_cotisation_decroit_avec_taux(self, agent):
        params = dict(type_contrat='PER', capital_cible=100_000,
                      age_entree=35, age_retraite=65,
                      taux_technique=0.0, generer_graphiques=False)
        r1 = agent.run(taux_marche=0.01, **params)
        r2 = agent.run(taux_marche=0.04, **params)
        assert r1['success'] and r2['success']
        assert r1['tarification']['cotisation_nette_annuelle'] > \
               r2['tarification']['cotisation_nette_annuelle'], \
            "La cotisation doit décroître quand le taux de marché augmente"

    # T3 — H1 VERT si taux technique ≤ 3.5%
    def test_t3_taux_technique_conforme(self, agent):
        r = agent.run(type_contrat='PER', capital_cible=100_000,
                      taux_technique=0.0, taux_marche=0.03,
                      generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_ep2']
        assert val['h1_taux']['statut'] == 'VERT'

    # T4 — H1 ROUGE si taux technique > marché
    def test_t4_taux_technique_excessif(self, agent):
        r = agent.run(type_contrat='PER', capital_cible=100_000,
                      taux_technique=0.05, taux_marche=0.03,
                      generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_ep2']
        assert val['h1_taux']['statut'] == 'ROUGE'

    # T5 — Validation clés imbriquées correctement lues (bug corrigé)
    def test_t5_validation_cles_imbriquees(self, agent):
        r = agent.run(type_contrat='PER', capital_cible=100_000,
                      age_entree=35, age_retraite=65,
                      taux_technique=0.0, taux_marche=0.03,
                      generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_ep2']
        # H2 rente doit lire la vraie rente mensuelle (> 0)
        assert val['h2_rente']['statut'] == 'VERT', \
            f"H2 rente ROUGE — clé rente_mensuelle non lue correctement"
        assert val['h2_rente']['rente'] > 0

    # T6 — PM progressif cohérent : PM croît avec les années
    def test_t6_pm_progressif_croissant(self, agent):
        r = agent.run(type_contrat='PER', capital_cible=100_000,
                      age_entree=35, age_retraite=65,
                      taux_technique=0.0, taux_marche=0.03,
                      generer_graphiques=False)
        assert r['success'] is True
        pm = r['tarification']['pm_progressif']
        valeurs = list(pm.values())
        assert valeurs == sorted(valeurs), "PM progressif doit croître"

    # T7 — Cas limite : durée minimale (1 an)
    def test_t7_duree_minimale(self, agent):
        r = agent.run(type_contrat='PER', capital_cible=10_000,
                      age_entree=64, age_retraite=65,
                      taux_technique=0.0, taux_marche=0.03,
                      generer_graphiques=False)
        assert 'success' in r
        if r['success']:
            assert r['tarification']['cotisation_brute_annuelle'] > 0
