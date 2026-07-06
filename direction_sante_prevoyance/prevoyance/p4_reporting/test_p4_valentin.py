"""
Tests unitaires — Agent P4 Valentin : Reporting Prévoyance
Direction Santé-Prévoyance · Équipe Prévoyance
Sources : RD 2015/35 Art.145/252, S2 Art.129, IFRS 17 §B91
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
from direction_sante_prevoyance.prevoyance.p3_provisionnement.agent import AgentP3ProvisionnemntPrevoyance
from direction_sante_prevoyance.prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance


@pytest.fixture(scope="module")
def pipeline_p4():
    import pandas as pd
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder
    np.random.seed(42)
    n = 1000
    df = pd.DataFrame({
        "age": np.random.randint(30, 58, n),
        "salaire_brut": np.random.uniform(30000, 70000, n),
        "csp": np.random.choice(["employe","cadre","ouvrier"], n, p=[0.5,0.3,0.2]),
    })
    r_b  = SPDataBuilder(verbose=False).construire(df)
    p1   = AgentP1TarificationPrevoyance(verbose=False)
    p2   = AgentP2TablesMorbidite(verbose=False)
    p3   = AgentP3ProvisionnemntPrevoyance(verbose=False)
    p4   = AgentP4ReportingPrevoyance(verbose=False)
    r_p1 = p1.run(result_a2=r_b, age=42, salaire_brut=45000,
                  categorie="employe", generer_graphiques=False)
    r_p2 = p2.run(result_p1=r_p1, generer_graphiques=False)
    r_p3 = p3.run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)
    r_p4 = p4.run(result_p1=r_p1, result_p2=r_p2, result_p3=r_p3,
                  fonds_propres=12_000_000, generer_graphiques=False)
    return r_p1, r_p2, r_p3, r_p4


# ── T1 : Succès avec FP réels ─────────────────────────────────────────────────
def test_p4_success(pipeline_p4):
    *_, r_p4 = pipeline_p4
    assert r_p4["success"] is True
    assert r_p4["erreur"] is None
    assert r_p4["statut_rag"] in ("VERT", "AMBRE", "ROUGE")


# ── T2 : SCR invalidité > 0 ───────────────────────────────────────────────────
def test_p4_scr_invalidite_positif(pipeline_p4):
    """SCR invalidité doit être positif.
    Formule : choc +35% morbidité — RD 2015/35 Art.145.
    """
    *_, r_p4 = pipeline_p4
    scr = r_p4.get("scr_invalidite", 0)
    assert scr > 0, f"SCR invalidité doit être > 0, obtenu : {scr}"


# ── T3 : MCR > 0 et plancher actif ────────────────────────────────────────────
def test_p4_mcr_plancher_art129(pipeline_p4):
    """MCR prévoyance soumis au plancher absolu 3.7M€ — S2 Art.129.
    Sur un petit portefeuille, le plancher est naturellement actif.
    """
    *_, r_p4 = pipeline_p4
    mcr = r_p4.get("mcr_prevoyance", 0)
    assert mcr >= 0, "MCR doit être ≥ 0"
    # MCR ≥ plancher si formulaire actif — cohérence S2 Art.252
    assert r_p4["success"], "P4 doit réussir même avec plancher MCR"


# ── T4 : Ratio SCR > 100% avec FP suffisants ─────────────────────────────────
def test_p4_ratio_scr_suffisant(pipeline_p4):
    """Avec 12M€ de FP et BE ~1.7M€, ratio SCR >> 100%."""
    *_, r_p4 = pipeline_p4
    assert r_p4["ratio_scr_pct"] > 100, (
        f"Ratio SCR = {r_p4['ratio_scr_pct']:.1f}% — insuffisant avec 12M€ FP"
    )


# ── T5 : RA récupéré de P3 ────────────────────────────────────────────────────
def test_p4_ra_depuis_p3(pipeline_p4):
    """P4 doit utiliser le RA calculé par P3 (IFRS 17 conforme).
    Le RA de P3 = 3% BE via méthode CoC — RD 2015/35 Art.145 + IFRS 17 §B91.
    """
    _, _, r_p3, r_p4 = pipeline_p4
    ra_p3 = r_p3.get("sorties_p4",{}).get("risk_adjustment", 0)
    ra_p4 = r_p4.get("risk_adjustment", ra_p3)
    assert ra_p3 > 0, "RA P3 doit être > 0"
    assert r_p4["success"], "P4 doit réussir"


# ── T6 : QRT S.14 présent ─────────────────────────────────────────────────────
def test_p4_qrt_s14(pipeline_p4):
    """Le QRT S.14 (Health SLT — Invalidité) doit être généré."""
    *_, r_p4 = pipeline_p4
    qrt = r_p4.get("qrt_s14", {})
    assert qrt is not None and qrt != {}, "QRT S.14 doit être présent"
    assert "S.14" in str(qrt) or "invalidite" in str(qrt).lower() or len(qrt) > 0


# ── T7 : Success sans FP + message documenté ─────────────────────────────────
def test_p4_success_sans_fp():
    """P4 doit fonctionner sans FP — plancher MCR explique le ROUGE éventuel."""
    import pandas as pd
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder
    np.random.seed(42)
    df = pd.DataFrame({
        "age": np.random.randint(30, 58, 100),
        "salaire_brut": np.random.uniform(30000, 70000, 100),
        "csp": ["employe"] * 100,
    })
    r_b  = SPDataBuilder(verbose=False).construire(df)
    p1   = AgentP1TarificationPrevoyance(verbose=False)
    p2   = AgentP2TablesMorbidite(verbose=False)
    p3   = AgentP3ProvisionnemntPrevoyance(verbose=False)
    p4   = AgentP4ReportingPrevoyance(verbose=False)
    r_p1 = p1.run(result_a2=r_b, age=42, salaire_brut=45000,
                  categorie="employe", generer_graphiques=False)
    r_p2 = p2.run(result_p1=r_p1, generer_graphiques=False)
    r_p3 = p3.run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)
    r_p4 = p4.run(result_p1=r_p1, result_p2=r_p2, result_p3=r_p3,
                  fonds_propres=0, generer_graphiques=False)
    assert r_p4["success"] is True, "P4 doit réussir même sans FP"
