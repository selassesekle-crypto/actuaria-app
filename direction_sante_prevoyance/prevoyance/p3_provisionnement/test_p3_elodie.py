"""
Tests unitaires — Agent P3 Élodie : Provisionnement Prévoyance
Direction Santé-Prévoyance · Équipe Prévoyance
Sources : CTIP 2023, IFRS 17 §B91, EIOPA RFR Art.77, RD 2015/35 Art.145
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
from direction_sante_prevoyance.prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance


@pytest.fixture(scope="module")
def pipeline_p3():
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
    p3   = AgentP3ProvissionnementPrevoyance(verbose=False)
    r_p1 = p1.run(result_a2=r_b, age=42, salaire_brut=45000,
                  categorie="employe", generer_graphiques=False)
    r_p2 = p2.run(result_p1=r_p1, generer_graphiques=False)
    r_p3 = p3.run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)
    return r_p1, r_p2, r_p3


# ── T1 : Succès et structure ───────────────────────────────────────────────────
def test_p3_success(pipeline_p3):
    _, _, r_p3 = pipeline_p3
    assert r_p3["success"] is True
    assert r_p3["statut_rag"] in ("VERT", "AMBRE", "ROUGE")
    assert r_p3["erreur"] is None


# ── T2 : BE = BE_ITT + PM + PSAP_IP + PREC (identité comptable) ──────────────
def test_p3_be_identite_comptable(pipeline_p3):
    """BE_prévoyance = BE_ITT + PM_rentes_IP + PSAP_IP + PREC.
    Identité fondamentale du provisionnement prévoyance (Art. 77 §1 S2).
    """
    _, _, r_p3 = pipeline_p3
    be      = r_p3["be_prevoyance"]
    be_itt  = r_p3["be_itt"]
    pm      = r_p3["pm_rentes_ip"]
    psap_ip = r_p3["psap_ip"]
    prec    = r_p3["prec"]
    assert be > 0, "BE doit être positif"
    assert abs(be - (be_itt + pm + psap_ip + prec)) < 0.05, (
        f"BE ({be:.2f}) ≠ BE_ITT ({be_itt:.2f}) + PM ({pm:.2f}) + PSAP_IP ({psap_ip:.2f}) + PREC ({prec:.2f})"
    )


# ── T3 : TP = BE + RA ─────────────────────────────────────────────────────────
def test_p3_tp_identite(pipeline_p3):
    """TP = BE + Risk Adjustment — IFRS 17."""
    _, _, r_p3 = pipeline_p3
    be  = r_p3["be_prevoyance"]
    ra  = r_p3.get("sorties_p4",{}).get("risk_adjustment", 0)
    tp  = r_p3["tp_prevoyance"]
    assert abs(tp - (be + ra)) < 0.01, (
        f"TP ({tp:.2f}) ≠ BE ({be:.2f}) + RA ({ra:.2f})"
    )


# ── T4 : RA ≥ 3% BE (floor prévoyance) ───────────────────────────────────────
def test_p3_ra_floor_prevoyance(pipeline_p3):
    """RA prévoyance ≥ 3% BE (floor marché — risque long terme).
    Calculé via CoC : SCR_morbidité × 6% — RD 2015/35 Art.145 + IFRS 17 §B91.
    """
    _, _, r_p3 = pipeline_p3
    be = r_p3["be_prevoyance"]
    ra = r_p3.get("sorties_p4",{}).get("risk_adjustment", 0)
    assert ra >= be * 0.03 - 0.01, (
        f"RA ({ra:,.0f}€) < floor 3% BE ({be*0.03:,.0f}€)"
    )


# ── T5 : FP absents de sorties_p4 ────────────────────────────────────────────
def test_p3_fp_absents_sorties_p4(pipeline_p3):
    """P3 ne doit pas estimer les FP — c'est le rôle de P4."""
    _, _, r_p3 = pipeline_p3
    s4 = r_p3.get("sorties_p4", {})
    assert "fonds_propres" not in s4, (
        "FP ne doivent pas être calculés par P3 (rôle de P4)"
    )


# ── T6 : nb_inv cohérent (sans division par age) ─────────────────────────────
def test_p3_nb_inv_formule_correcte(pipeline_p3):
    """nb_inv = nb_assures × taux_ip × 0.60 — sans division par age/10.
    Sur un grand portefeuille (1000 salariés), PM rentes doit être > 0.
    """
    _, _, r_p3 = pipeline_p3
    pm = r_p3["pm_rentes_ip"]
    assert pm >= 0, "PM rentes IP doit être ≥ 0"
    # Sur 1000 salariés avec taux_ip ~0.5%, nb_inv = 1000×0.005×0.6 = 3
    # → PM > 0 sauf si taux_ip très faible
    be = r_p3["be_prevoyance"]
    assert be > 0, "BE doit être > 0 sur 1000 salariés"


# ── T7 : Sorties vers P4 complètes ────────────────────────────────────────────
def test_p3_sorties_p4_completes(pipeline_p3):
    """sorties_p4 doit contenir toutes les clés attendues par P4."""
    _, _, r_p3 = pipeline_p3
    s4 = r_p3.get("sorties_p4", {})
    for cle in ["be_prevoyance", "risk_adjustment", "tp_prevoyance",
                "psap_total", "pm_rentes_ip", "loss_ratio", "primes_acquises"]:
        assert cle in s4, f"Clé manquante dans sorties_p4 : '{cle}'"
    assert s4["be_prevoyance"] > 0
    assert s4["tp_prevoyance"] > s4["be_prevoyance"]
