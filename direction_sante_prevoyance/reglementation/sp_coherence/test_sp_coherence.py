"""
Tests unitaires — Agent SP-COHÉRENCE : Cohérence Globale Santé-Prévoyance
Direction Santé-Prévoyance — Équivalent SP de A9 Marcus (Non-Vie)
6 contrôles C1-C6 + alertes proactives
"""
import pytest
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from direction_sante_prevoyance.reglementation.sp_coherence.agent import AgentSPCoherence


@pytest.fixture(scope="module")
def pipeline_complet():
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder
    from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante
    from direction_sante_prevoyance.sante.s2_provisionnement.agent import AgentS2ProvisionnemntSante
    from direction_sante_prevoyance.sante.s3_reporting.agent import AgentS3ReportingSante
    from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
    from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
    from direction_sante_prevoyance.prevoyance.p3_provisionnement.agent import AgentP3ProvisionnemntPrevoyance
    from direction_sante_prevoyance.prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
    from direction_sante_prevoyance.coordination.sp_coord.agent import AgentSPCoord
    from direction_sante_prevoyance.reglementation.sp_reg2_ifrs17.agent import AgentSPReg2IFRS17
    from direction_sante_prevoyance.reglementation.sp_reg3_ani_100sante.agent import AgentSPReg3ANI100Sante

    np.random.seed(42)
    n = 1000
    df_m  = pd.DataFrame({"age":np.random.randint(25,60,n),"garanties":np.random.choice(["confort","premium"],n),"sinistres_sante":np.random.exponential(600,n),"cotisation":np.random.uniform(900,1800,n)})
    df_ip = pd.DataFrame({"age":np.random.randint(30,58,n),"salaire_brut":np.random.uniform(30000,70000,n),"csp":np.random.choice(["employe","cadre","ouvrier"],n,p=[0.5,0.3,0.2]),"arrets_itt":np.where(np.random.rand(n)<0.08,np.random.uniform(30,180,n),0)})
    r_bm  = SPDataBuilder(verbose=False).construire(df_m)
    r_bip = SPDataBuilder(verbose=False).construire(df_ip)

    r_s1 = AgentS1TarificationSante(verbose=False).run(result_a2=r_bm, nb_assures=1000, age_moyen=40, contrat="collectif", garantie_niveau="confort", generer_graphiques=False)
    r_s2 = AgentS2ProvisionnemntSante(verbose=False).run(result_s1=r_s1, generer_graphiques=False)
    r_s3 = AgentS3ReportingSante(verbose=False).run(result_s1=r_s1, result_s2=r_s2, fonds_propres=5_000_000, generer_graphiques=False)
    r_p1 = AgentP1TarificationPrevoyance(verbose=False).run(result_a2=r_bip, age=42, salaire_brut=45000, categorie="employe", generer_graphiques=False)
    r_p2 = AgentP2TablesMorbidite(verbose=False).run(result_p1=r_p1, generer_graphiques=False)
    r_p3 = AgentP3ProvisionnemntPrevoyance(verbose=False).run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)
    r_p4 = AgentP4ReportingPrevoyance(verbose=False).run(result_p1=r_p1, result_p2=r_p2, result_p3=r_p3, fonds_propres=10_000_000, generer_graphiques=False)
    r_coord = AgentSPCoord(verbose=False).run(result_s3=r_s3, result_p4=r_p4, fonds_propres=15_000_000, generer_graphiques=False)
    r_reg2 = AgentSPReg2IFRS17(verbose=False).run(result_s3=r_s3, result_p4=r_p4, generer_graphiques=False)
    r_reg3 = AgentSPReg3ANI100Sante(verbose=False).run(result_s1=r_s1, contrat="collectif", generer_graphiques=False)
    return r_s1, r_s2, r_s3, r_p4, r_coord, r_reg2, r_reg3


@pytest.fixture(scope="module")
def r_coh(pipeline_complet):
    r_s1,r_s2,r_s3,r_p4,r_coord,r_reg2,r_reg3 = pipeline_complet
    return AgentSPCoherence(verbose=False).run(
        result_s1=r_s1, result_s2=r_s2, result_s3=r_s3, result_p4=r_p4,
        result_coord=r_coord, result_reg2=r_reg2, result_reg3=r_reg3,
        generer_graphiques=False)


# ── T1 : Succès et structure ───────────────────────────────────────────────────
def test_coh_success_et_structure(r_coh):
    """SP-Cohérence doit réussir et retourner la structure standard."""
    assert r_coh["success"] is True, "SP-Cohérence doit réussir"
    assert r_coh["erreur"] is None, "Pas d'erreur attendue"
    assert r_coh["statut_rag"] in ("VERT","AMBRE","ROUGE"), "RAG invalide"
    for cle in ["controles","dashboard","alertes_proactives",
                "agents_analyses","flux_ok","hypotheses","commentaire"]:
        assert cle in r_coh, f"Clé manquante : {cle}"


# ── T2 : 6 contrôles C1-C6 ───────────────────────────────────────────────────
def test_coh_six_controles(r_coh):
    """6 contrôles C1-C6 doivent tous être présents avec un statut valide."""
    controles = r_coh["controles"]
    assert len(controles) == 6, f"Attendu 6 contrôles, obtenu {len(controles)}"
    ids = [c["id"] for c in controles]
    for cid in ["C1","C2","C3","C4","C5","C6"]:
        assert cid in ids, f"Contrôle manquant : {cid}"
    for c in controles:
        assert c["ok"] in (True, False, None), (
            f"{c['id']} : statut ok={c['ok']} invalide"
        )


# ── T3 : C1 — LR cohérent entre S1 et S2 ─────────────────────────────────────
def test_coh_c1_lr_coherent(r_coh):
    """C1 vérifie l'écart LR tarification (S1) ↔ LR provisionnement (S2).
    Seuil : ≤ 15pp — pratique marché FNMF 2023.
    """
    c1 = next(c for c in r_coh["controles"] if c["id"]=="C1")
    assert c1["ok"] in (True, False), f"C1 doit être calculé (pas N/A) avec S1+S2"
    if c1["ok"] is False:
        ecart = c1.get("ecart", 0)
        assert ecart > 0.15, f"C1 KO mais écart={ecart:.1%} ≤ 15pp — incohérence"


# ── T4 : C2 + C3 — Réconciliation BE S2/IFRS17 ────────────────────────────────
def test_coh_c2_c3_be_reconciliation(r_coh):
    """C2 et C3 vérifient la cohérence BE S2 ↔ BE IFRS17 (santé + prévoyance).
    Seuil : ≤ 5% — ACPR Q&A IFRS17 2023.
    """
    c2 = next(c for c in r_coh["controles"] if c["id"]=="C2")
    c3 = next(c for c in r_coh["controles"] if c["id"]=="C3")
    for c in [c2, c3]:
        if c["ok"] is not None:
            if c["ok"] is False:
                ecart = c.get("ecart", 0)
                assert ecart > 0.05, (
                    f"{c['id']} KO mais écart={ecart:.1%} ≤ 5% — incohérence logique"
                )


# ── T5 : C4 — SCR deux chemins identiques ────────────────────────────────────
def test_coh_c4_scr_coherent(r_coh):
    """C4 vérifie que SP-Coord et SP-REG1 calculent le même SCR.
    Seuil : ≤ 2% — même formule EIOPA Annexe IV, doit être quasi-identique.
    """
    c4 = next(c for c in r_coh["controles"] if c["id"]=="C4")
    if c4["ok"] is not None:
        if c4["ok"] is True:
            ecart = c4.get("ecart", 0)
            assert ecart <= 0.02, (
                f"C4 OK mais écart={ecart:.2%} > 2% — incohérence SCR"
            )


# ── T6 : Dégradation gracieuse — C1 calculé avec S1+S2 ──────────────────────
def test_coh_degradation_gracieuse(pipeline_complet):
    """Avec seulement S1+S2, C1 doit être calculé et C2-C5 doivent être N/A."""
    r_s1,r_s2,*_ = pipeline_complet
    r = AgentSPCoherence(verbose=False).run(
        result_s1=r_s1, result_s2=r_s2, generer_graphiques=False)
    assert r["success"] is True, "Doit réussir avec S1+S2 seulement"
    c1 = next(c for c in r["controles"] if c["id"]=="C1")
    assert c1["ok"] in (True, False), "C1 doit être calculé avec S1+S2"
    for cid in ["C2","C3","C4","C5"]:
        cx = next(c for c in r["controles"] if c["id"]==cid)
        assert cx["ok"] is None, f"{cid} doit être N/A sans agents requis"


# ── T7 : Alertes proactives ───────────────────────────────────────────────────
def test_coh_alertes_proactives(r_coh):
    """Les alertes proactives doivent être une liste (vide ou avec des messages).
    Elles doivent détecter des patterns SP-spécifiques (ANI, PSAP, SCR tendu).
    """
    alertes = r_coh["alertes_proactives"]
    assert isinstance(alertes, list), "alertes_proactives doit être une liste"
    # Toutes les alertes doivent être des strings non vides
    for a in alertes:
        assert isinstance(a, str) and len(a) > 0, f"Alerte invalide : {a}"
