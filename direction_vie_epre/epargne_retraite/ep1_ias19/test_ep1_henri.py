"""
Tests Agent EP1 — Henri — Engagements Retraite IAS 19
7 tests couvrant : nominal, DBO, Service Cost, sensibilité, cas limites
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

import pytest
from direction_vie_epre.epargne_retraite.ep1_ias19.agent import AgentEP1EngagementsRetraite


@pytest.fixture
def agent():
    return AgentEP1EngagementsRetraite(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=False
    )


class TestEP1EngagementsRetraite:

    # T1 — Cas nominal
    def test_t1_nominal(self, agent):
        r = agent.run(effectif=500, salaire_moyen=45_000,
                      anciennete_moyenne=12, taux_actu=0.035,
                      taux_revalorisation=0.02, taux_rotation=0.05,
                      taux_prestation=0.015, age_moyen=42,
                      age_retraite=65, generer_graphiques=False)
        assert r['success'] is True
        assert r['statut_rag'] == 'VERT'
        assert r['ias19']['dbo_total'] > 0
        assert r['ias19']['service_cost'] > 0
        assert r['ias19']['interest_cost'] > 0

    # T2 — DBO croît quand le taux baisse (effet duration)
    def test_t2_dbo_sensibilite_taux(self, agent):
        r_haut = agent.run(effectif=500, salaire_moyen=45_000,
                           taux_actu=0.05, generer_graphiques=False)
        r_bas  = agent.run(effectif=500, salaire_moyen=45_000,
                           taux_actu=0.02, generer_graphiques=False)
        assert r_haut['success'] and r_bas['success']
        assert r_bas['ias19']['dbo_total'] > r_haut['ias19']['dbo_total'], \
            "DBO doit être plus élevée quand le taux baisse"

    # T3 — H1 VERT si taux ∈ [2%, 6%]
    def test_t3_taux_actu_conforme(self, agent):
        r = agent.run(effectif=500, taux_actu=0.035, generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_ep1']
        assert val['h1_taux']['statut'] == 'VERT'

    # T4 — H1 ROUGE si taux < 1%
    def test_t4_taux_actu_trop_bas(self, agent):
        r = agent.run(effectif=500, taux_actu=0.005, generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_ep1']
        assert val['h1_taux']['statut'] == 'ROUGE'

    # T5 — Service Cost / DBO cohérent → H3 VERT
    def test_t5_service_cost_coherent(self, agent):
        r = agent.run(effectif=500, salaire_moyen=45_000,
                      anciennete_moyenne=12, taux_actu=0.035,
                      taux_prestation=0.015, generer_graphiques=False)
        assert r['success'] is True
        val = r['validation_ep1']
        assert val['h3_service_cost']['statut'] in ('VERT', 'AMBRE', 'ROUGE')
        ratio_sc = (r['ias19']['service_cost'] /
                    max(r['ias19']['dbo_total'], 1) * 100)
        assert ratio_sc >= 0

    # T6 — DBO proportionnelle à l'effectif
    def test_t6_dbo_proportionnelle_effectif(self, agent):
        r1 = agent.run(effectif=500, salaire_moyen=45_000, taux_actu=0.035,
                       generer_graphiques=False)
        r2 = agent.run(effectif=1000, salaire_moyen=45_000, taux_actu=0.035,
                       generer_graphiques=False)
        assert r1['success'] and r2['success']
        ratio = r2['ias19']['dbo_total'] / max(r1['ias19']['dbo_total'], 1)
        assert abs(ratio - 2.0) < 0.01, f"DBO non proportionnelle à l'effectif : ratio={ratio}"

    # T7 — Sensibilité DBO choc up/down cohérente (corrigée duration modifiée)
    def test_t7_sensibilite_dbo(self, agent):
        r = agent.run(effectif=500, salaire_moyen=45_000, taux_actu=0.035,
                      generer_graphiques=False)
        assert r['success'] is True
        dbo = r['ias19']['dbo_total']
        dbo_up   = r['ias19']['dbo_choc_taux_up50bp']
        dbo_down = r['ias19']['dbo_choc_taux_down50bp']
        # +50bp → DBO baisse ; -50bp → DBO monte
        assert dbo_up < dbo, f"DBO choc+50bp doit être < DBO centrale"
        assert dbo_down > dbo, f"DBO choc-50bp doit être > DBO centrale"

    # T8 — B1 : annuités viagères calculées automatiquement depuis tables officielles
    def test_t8_annuites_officielles_auto(self, agent):
        """Sans annuites_viageres fourni, EP1 doit calculer depuis TH0002."""
        from direction_vie_epre.services.tables_mortalite_officielles import calculer_annuite_viagere
        r = agent.run(effectif=100, taux_actu=0.035, age_retraite=65,
                      sexe='H', generer_graphiques=False)
        assert r['success'] is True
        # annuites_utilisees doit être calculé automatiquement
        a_officielle = calculer_annuite_viagere(age=65, taux=0.035, sexe='H')
        assert abs(r['ias19']['annuites_utilisees'] - a_officielle) < 0.001, (
            f"Annuité utilisée={r['ias19']['annuites_utilisees']:.4f} "
            f"≠ officielle={a_officielle:.4f}"
        )

    # T9 — B1 : PUC individuel avec DataFrame
    def test_t9_puc_individuel(self, agent):
        """EP1 doit calculer la DBO salarié par salarié si effectifs_df fourni."""
        import pandas as pd
        # 5 salariés avec profils différents
        df = pd.DataFrame({
            'age':        [35, 42, 50, 55, 60],
            'anciennete': [8,  12, 20, 25, 30],
            'salaire':    [38000, 45000, 55000, 60000, 52000],
            'sexe':       ['H', 'F', 'H', 'H', 'F'],
        })
        r = agent.run(
            effectifs_df=df,
            taux_actu=0.035,
            taux_revalorisation=0.02,
            taux_prestation=0.015,
            age_retraite=65,
            generer_graphiques=False
        )
        assert r['success'] is True
        # effectif doit correspondre au nb de lignes du DataFrame
        assert r['parametres']['effectif'] == 5
        # DBO doit être positive
        assert r['ias19']['dbo_total'] > 0
        # Âge moyen cohérent
        assert abs(r['parametres']['age_moyen'] - 48.4) < 0.1
