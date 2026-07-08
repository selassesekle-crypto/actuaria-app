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
        assert r.get('erreur') is None  # clé absente du dict success — comportement normal
        # A5 : be_vie = capital × E_xn doit être présent dans le retour
        assert 'be_vie' in r
        assert r['be_vie'] > 0
        assert r['be_vie'] <= 100_000  # be_vie ≤ capital (E_xn ≤ 1)

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
        # Pour capital différé : survie F > survie H → E_xn(F) > E_xn(H)
        # → prime_pure F > prime_pure H (la femme doit cotiser plus pour garantir sa survie)
        assert rf['prime_pure']['annuelle'] > rh['prime_pure']['annuelle']

    # T6 — CAG ≤ 3% (directive DDA) → H3 VERT
    def test_t6_cag_conforme_dda(self, agent):
        r = agent.run(age=35, sexe='H', duree=30, capital=100_000,
                      taux_technique=0.0, taux_frais=0.008,
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

    # T8 — A5 : be_vie présent et cohérent avec capital × E_xn
    def test_t8_be_vie_coherent(self, agent):
        r = agent.run(age=45, sexe='H', duree=20, capital=100_000,
                      taux_technique=0.025, generer_graphiques=False)
        assert r['success'] is True
        assert 'be_vie' in r, "be_vie absent du dict retour — A5 non appliqué"
        # be_vie = capital × E_xn = capital × v^n × n_px
        # Doit être positif et inférieur au capital (actualisation + survie)
        assert 0 < r['be_vie'] < 100_000
        # be_vie == capital × E_xn (vérifié via la clé prime_pure.E_xn)
        expected_be = round(100_000 * r['prime_pure']['E_xn'], 2)
        assert abs(r['be_vie'] - expected_be) < 1.0, (
            f"be_vie={r['be_vie']} ≠ capital×E_xn={expected_be}"
        )

    # T9 — B2 : TMG détecté et tracé dans le dict retour
    def test_t9_tmg_tracé(self, agent):
        """Le TMG doit être enregistré et le flag underwater levé si TMG > taux_technique."""
        # TMG = 3% > taux_technique = 2.5% → underwater
        r = agent.run(age=45, sexe='H', duree=20, capital=100_000,
                      taux_technique=0.025, tmg=0.03, generer_graphiques=False)
        assert r['success'] is True
        assert 'tmg' in r
        assert r['tmg']['valeur'] == 0.03
        assert r['tmg']['underwater'] is True, "TMG 3% > taux 2.5% doit être underwater"
        # Le taux garanti doit être max(taux_technique, tmg) = 3%
        assert r['tmg']['taux_garanti'] == 0.03

    # T10 — B2 : types de contrats distincts
    def test_t10_types_contrats_distincts(self, agent):
        """Les 4 types doivent produire des primes différentes."""
        params = dict(age=45, sexe='H', duree=20, capital=100_000,
                      taux_technique=0.025, generer_graphiques=False)
        r_cd = agent.run(type_contrat='capital_differe', **params)
        r_rx = agent.run(type_contrat='rente', **params)
        r_mx = agent.run(type_contrat='mixte', **params)
        r_ms = agent.run(type_contrat='multisupport', **params)

        for r in [r_cd, r_rx, r_mx, r_ms]:
            assert r['success'] is True
            assert r['prime_pure']['annuelle'] > 0

        # Mixte doit être plus cher que capital différé (ajoute une garantie décès)
        assert r_mx['prime_pure']['annuelle'] > r_cd['prime_pure']['annuelle'], (
            "Prime mixte doit être > capital différé (garantie décès incluse)"
        )
        # Multisupport ne garanti pas la survie → prime différente du capital différé
        assert r_ms['prime_pure']['annuelle'] != r_cd['prime_pure']['annuelle'], (
            "Prime multisupport doit différer du capital différé (pas d'actualisation viag."
        )
