"""
Tests unitaires — Agent SP-COORD : Coordination Santé + Prévoyance
Direction Santé-Prévoyance · Sous Amira
Sources : Annexe IV RD 2015/35 (ρ=0.25), IFRS 17, CTIP/FNMF
"""
import pytest
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from direction_sante_prevoyance.coordination.sp_coord.agent import AgentSPCoord


@pytest.fixture(scope="module")
def pipeline():
    """Pipeline complet S1→S3 + P1→P4 pour alimenter SP-Coord."""
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder
    from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante
    from direction_sante_prevoyance.sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
    from direction_sante_prevoyance.sante.s3_reporting.agent import AgentS3ReportingSante
    from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
    from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
    from direction_sante_prevoyance.prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
    from direction_sante_prevoyance.prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance

    np.random.seed(42)
    n = 1000
    df_m = pd.DataFrame({
        "age": np.random.randint(25, 60, n),
        "garanties": np.random.choice(["confort","premium"], n),
        "sinistres_sante": np.random.exponential(600, n),
        "arrets_itt": np.where(np.random.rand(n)<0.08,
                                np.random.uniform(30,120,n), 0),
    })
    df_ip = pd.DataFrame({
        "age": np.random.randint(30, 58, n),
        "salaire_brut": np.random.uniform(30000, 70000, n),
        "csp": np.random.choice(["employe","cadre","ouvrier"], n, p=[0.5,0.3,0.2]),
    })
    r_bm  = SPDataBuilder(verbose=False).construire(df_m)
    r_bip = SPDataBuilder(verbose=False).construire(df_ip)

    r_s1 = AgentS1TarificationSante(verbose=False).run(
        result_a2=r_bm, nb_assures=1000, age_moyen=40,
        contrat="collectif", garantie_niveau="confort", generer_graphiques=False)
    r_s2 = AgentS2ProvissionnementSante(verbose=False).run(
        result_s1=r_s1, generer_graphiques=False)
    r_s3 = AgentS3ReportingSante(verbose=False).run(
        result_s1=r_s1, result_s2=r_s2,
        fonds_propres=5_000_000, generer_graphiques=False)

    r_p1 = AgentP1TarificationPrevoyance(verbose=False).run(
        result_a2=r_bip, age=42, salaire_brut=45000,
        categorie="employe", generer_graphiques=False)
    r_p2 = AgentP2TablesMorbidite(verbose=False).run(
        result_p1=r_p1, generer_graphiques=False)
    r_p3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
        result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)
    r_p4 = AgentP4ReportingPrevoyance(verbose=False).run(
        result_p1=r_p1, result_p2=r_p2, result_p3=r_p3,
        fonds_propres=10_000_000, generer_graphiques=False)

    return r_s3, r_p4, r_bm


@pytest.fixture(scope="module")
def r_coord(pipeline):
    r_s3, r_p4, r_bm = pipeline
    return AgentSPCoord(verbose=False).run(
        result_s3=r_s3, result_p4=r_p4, result_builder=r_bm,
        fonds_propres=15_000_000, generer_graphiques=False)


# ── T1 : Succès et structure ───────────────────────────────────────────────────
def test_coord_success(r_coord):
    """Succès et structure du retour — toutes les clés standard présentes."""
    assert r_coord["success"] is True, "SP-Coord doit réussir"
    assert r_coord["erreur"] is None, "Pas d'erreur attendue"
    assert r_coord["statut_rag"] in ("VERT", "AMBRE", "ROUGE"), "RAG invalide"
    for cle in ["be_consolide", "scr_consolide", "ratio_scr_pct",
                "diversification", "rho_eiopa", "hypotheses", "commentaire"]:
        assert cle in r_coord, f"Clé manquante : {cle}"


# ── T2 : BE consolidé = BE_santé + BE_prévoyance ─────────────────────────────
def test_coord_be_identite(r_coord):
    """Identité comptable : BE_consolidé = BE_santé + BE_prévoyance."""
    be_c = r_coord["be_consolide"]
    be_s = r_coord["be_sante"]
    be_p = r_coord["be_prevoyance"]
    assert abs(be_c - (be_s + be_p)) < 0.01, (
        f"BE_consolidé ({be_c:.2f}) ≠ BE_S ({be_s:.2f}) + BE_P ({be_p:.2f})"
    )
    assert be_c > 0, "BE consolidé doit être positif"


# ── T3 : SCR consolidé < SCR_S + SCR_P (bénéfice diversification) ────────────
def test_coord_diversification_eiopa(r_coord):
    """SCR consolidé < SCR_S + SCR_P grâce à ρ=0.25 EIOPA (Annexe IV RD 2015/35).
    Formule : SCR_tot = √(SCR_S² + 2×0.25×SCR_S×SCR_P + SCR_P²).
    """
    scr_c = r_coord["scr_consolide"]
    scr_s = r_coord["scr_sante"]
    scr_p = r_coord["scr_prevoyance"]
    assert scr_c < scr_s + scr_p, (
        f"SCR consolidé ({scr_c:.0f}) doit être < SCR_S+SCR_P ({scr_s+scr_p:.0f})"
    )
    assert r_coord["diversification"] > 0, "Bénéfice diversification doit être > 0"


# ── T4 : ρ EIOPA = 0.25 ───────────────────────────────────────────────────────
def test_coord_rho_eiopa(r_coord):
    """Corrélation EIOPA entre NSLT et SLT = 0.25 (Annexe IV RD 2015/35)."""
    assert r_coord["rho_eiopa"] == 0.25, (
        f"ρ EIOPA = {r_coord['rho_eiopa']}, attendu 0.25"
    )


# ── T5 : Ratio SCR consolidé > 100% ──────────────────────────────────────────
def test_coord_ratio_scr_suffisant(r_coord):
    """Avec 15M€ de FP sur un portefeuille consolidé, ratio SCR > 100%."""
    assert r_coord["ratio_scr_pct"] > 100, (
        f"Ratio SCR = {r_coord['ratio_scr_pct']:.1f}% insuffisant"
    )


# ── T6 : 3 hypothèses présentes ───────────────────────────────────────────────
def test_coord_hypotheses(r_coord):
    """SP-Coord doit produire 3 hypothèses : TP/BE, ratio SCR, poly-sinistralité."""
    hyp = r_coord["hypotheses"]
    assert len(hyp) == 3, f"Attendu 3 hypothèses, obtenu {len(hyp)}"
    ids = [h["id"] for h in hyp]
    assert "H1" in ids and "H2" in ids and "H3" in ids, f"IDs manquants : {ids}"


# ── T7 : Erreur si S3 absent ──────────────────────────────────────────────────
def test_coord_erreur_sans_s3(pipeline):
    """SP-Coord doit retourner success=False si result_s3 est absent."""
    _, r_p4, _ = pipeline
    coord = AgentSPCoord(verbose=False)
    r = coord.run(result_s3=None, result_p4=r_p4, generer_graphiques=False)
    assert r["success"] is False, "Doit échouer sans S3"
    assert r["erreur"] is not None, "Message d'erreur attendu"
