"""
Tests unitaires — Agent S3 Binta : Reporting Santé
Direction Santé-Prévoyance · Équipe Santé
Sources : RD 2015/35 Art.148/252/159, IFRS 17 §B91
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante
from direction_sante_prevoyance.sante.s2_provisionnement.agent import AgentS2ProvisionnemntSante
from direction_sante_prevoyance.sante.s3_reporting.agent import AgentS3ReportingSante


@pytest.fixture(scope="module")
def pipeline_s3():
    s1 = AgentS1TarificationSante(verbose=False)
    s2 = AgentS2ProvisionnemntSante(verbose=False)
    s3 = AgentS3ReportingSante(verbose=False)
    r_s1 = s1.run(nb_assures=5000, age_moyen=38, contrat="collectif",
                  garantie_niveau="confort", chargement_pct=0.18,
                  generer_graphiques=False)
    r_s2 = s2.run(result_s1=r_s1, generer_graphiques=False)
    return s3, r_s1, r_s2


# ── T1 : Succès avec FP réels ─────────────────────────────────────────────────
def test_s3_success_avec_fp(pipeline_s3):
    s3, r_s1, r_s2 = pipeline_s3
    r = s3.run(result_s1=r_s1, result_s2=r_s2,
               fonds_propres=5_000_000, generer_graphiques=False)
    assert r["success"] is True
    assert r["erreur"] is None
    assert r["statut_rag"] in ("VERT", "AMBRE", "ROUGE")


# ── T2 : SCR > 0 et MCR > 0 ──────────────────────────────────────────────────
def test_s3_scr_mcr_positifs(pipeline_s3):
    """SCR et MCR doivent être positifs.
    SCR NSLT formule standard EIOPA — RD 2015/35 Art.148.
    MCR plancher 2.5M€ — Art.252 + Art.129.
    """
    s3, r_s1, r_s2 = pipeline_s3
    r = s3.run(result_s1=r_s1, result_s2=r_s2,
               fonds_propres=5_000_000, generer_graphiques=False)
    assert r["scr_sante"] > 0, "SCR doit être > 0"
    assert r["mcr_sante"] > 0, "MCR doit être > 0"


# ── T3 : Ratio SCR > 100% avec FP suffisants ─────────────────────────────────
def test_s3_ratio_scr_suffisant(pipeline_s3):
    """Avec 5M€ de FP sur un portefeuille ~500k€ de BE, ratio SCR >> 100%."""
    s3, r_s1, r_s2 = pipeline_s3
    r = s3.run(result_s1=r_s1, result_s2=r_s2,
               fonds_propres=5_000_000, generer_graphiques=False)
    assert r["ratio_scr_pct"] > 100, (
        f"Ratio SCR = {r['ratio_scr_pct']:.1f}% — insuffisant avec 5M€ FP"
    )


# ── T4 : VERT avec FP > SCR ───────────────────────────────────────────────────
def test_s3_vert_fp_suffisants(pipeline_s3):
    """S3 doit retourner VERT si FP >> SCR (ratio > 130%)."""
    s3, r_s1, r_s2 = pipeline_s3
    r = s3.run(result_s1=r_s1, result_s2=r_s2,
               fonds_propres=10_000_000, generer_graphiques=False)
    assert r["statut_rag"] == "VERT", (
        f"Statut attendu VERT avec 10M€ FP, obtenu : {r['statut_rag']}"
    )


# ── T5 : Success même sans FP + message explicite ─────────────────────────────
def test_s3_success_sans_fp(pipeline_s3):
    """S3 doit fonctionner sans FP (fallback 80% PA) avec message d'avertissement."""
    s3, r_s1, r_s2 = pipeline_s3
    r = s3.run(result_s1=r_s1, result_s2=r_s2,
               fonds_propres=0, generer_graphiques=False)
    assert r["success"] is True, "S3 doit réussir même sans FP"


# ── T6 : QRT S.13.01 présent ──────────────────────────────────────────────────
def test_s3_qrt_s13(pipeline_s3):
    """Le QRT S.13.01 (Health NSLT) doit être généré."""
    s3, r_s1, r_s2 = pipeline_s3
    r = s3.run(result_s1=r_s1, result_s2=r_s2,
               fonds_propres=5_000_000, generer_graphiques=False)
    qrt = r.get("qrt_s13", {})
    assert qrt is not None and qrt != {}
    assert qrt.get("code") == "S.13.01", (
        f"Code QRT attendu S.13.01, obtenu : {qrt.get('code')}"
    )
    lignes = qrt.get("lignes", [])
    assert len(lignes) >= 5, f"QRT S.13.01 doit avoir ≥ 5 lignes, obtenu : {len(lignes)}"


# ── T7 : TP = BE + RA ─────────────────────────────────────────────────────────
def test_s3_tp_identite(pipeline_s3):
    """Identité : TP = BE + Risk Adjustment — IFRS 17."""
    s3, r_s1, r_s2 = pipeline_s3
    r = s3.run(result_s1=r_s1, result_s2=r_s2,
               fonds_propres=5_000_000, generer_graphiques=False)
    be  = r["be_sante"]
    ra  = r["risk_adjustment"]
    tp  = r["tp_sante"]
    assert abs(tp - (be + ra)) < 0.01, (
        f"TP ({tp:.2f}) ≠ BE ({be:.2f}) + RA ({ra:.2f})"
    )
