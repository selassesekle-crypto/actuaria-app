"""
Tests unitaires — Agent SP-ALM : ALM & Liquidité Santé-Prévoyance
Direction Santé-Prévoyance — Équivalent SP de A12 Aisha (Non-Vie)
Duration SP, gap, BV01, LCR Art.L212-7 CSS
"""
import pytest
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from direction_sante_prevoyance.reglementation.sp_alm.agent import (
    AgentSPAlm, GAP_CIBLE_MAX, LCR_MIN, EIOPA_RFR_PROXY,
    DURATION_RENTES_IP_MIN, DURATION_RENTES_IP_MAX
)


@pytest.fixture(scope="module")
def r_p3():
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder
    from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
    from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
    from direction_sante_prevoyance.prevoyance.p3_provisionnement.agent import AgentP3ProvisionnemntPrevoyance

    np.random.seed(42)
    n = 1000
    df_ip = pd.DataFrame({
        "age": np.random.randint(30, 58, n),
        "salaire_brut": np.random.uniform(30000, 70000, n),
        "csp": np.random.choice(["employe","cadre","ouvrier"], n, p=[0.5,0.3,0.2]),
        "arrets_itt": np.where(np.random.rand(n)<0.08, np.random.uniform(30,180,n), 0),
    })
    r_bip = SPDataBuilder(verbose=False).construire(df_ip)
    rp1 = AgentP1TarificationPrevoyance(verbose=False).run(
        result_a2=r_bip, age=42, salaire_brut=45000,
        categorie="employe", generer_graphiques=False)
    rp2 = AgentP2TablesMorbidite(verbose=False).run(result_p1=rp1, generer_graphiques=False)
    return AgentP3ProvisionnemntPrevoyance(verbose=False).run(
        result_p1=rp1, result_p2=rp2, generer_graphiques=False)


@pytest.fixture(scope="module")
def r_alm(r_p3):
    return AgentSPAlm(verbose=False).run(
        result_p3=r_p3, fonds_propres=15_000_000,
        generer_graphiques=False)


# ── T1 : Succès et structure ───────────────────────────────────────────────────
def test_alm_success_et_structure(r_alm):
    """SP-ALM doit réussir et retourner duration, BV01, LCR."""
    assert r_alm["success"] is True, "Doit réussir"
    assert r_alm["erreur"] is None, "Pas d'erreur"
    assert r_alm["statut_rag"] in ("VERT","AMBRE","ROUGE"), "RAG invalide"
    for cle in ["duration","bv01","lcr","passif","actif","gap",
                "hypotheses","commentaire"]:
        assert cle in r_alm, f"Clé manquante : {cle}"
    assert len(r_alm["hypotheses"]) == 4, "4 hypothèses attendues (H1-H4 avec Redington)"


# ── T2 : Duration passif SP — rentes IP longues, santé courte ────────────────
def test_alm_duration_passif_hierarchie(r_alm):
    """Duration rentes IP > Duration PSAP prév > Duration PSAP santé.
    Les PM rentes IP ont une duration 10-18 ans (long terme).
    Le PSAP santé a une duration < 1 an (remboursements rapides).
    """
    passif = r_alm["passif"]
    dur_rentes = passif["duration_rentes_ip"]
    dur_psap_p = passif["duration_psap_prev"]
    dur_psap_s = passif["duration_psap_sante"]

    assert DURATION_RENTES_IP_MIN <= dur_rentes <= DURATION_RENTES_IP_MAX, (
        f"D_rentes_IP={dur_rentes:.2f}a doit être ∈ [{DURATION_RENTES_IP_MIN},{DURATION_RENTES_IP_MAX}]a"
    )
    assert dur_psap_s < 1.0, (
        f"D_PSAP_santé={dur_psap_s:.2f}a doit être < 1a (remboursements rapides)"
    )
    # Duration consolidée bornée par les extrêmes
    dur_consol = passif["duration_consolidee"]
    assert dur_psap_s <= dur_consol <= dur_rentes, (
        f"D_consol={dur_consol:.2f}a doit être ∈ [D_psap_santé, D_rentes_IP]"
    )


# ── T3 : BV01 — identité BV01_net = BV01_actif - BV01_passif ─────────────────
def test_alm_bv01_identite(r_alm):
    """BV01_net = BV01_actif - BV01_passif (identité comptable).
    Convention : hausse taux → valeur obligation baisse → BV01 négatif.
    Source : actuariat ALM standard + EIOPA Art.105 S2.
    """
    bv = r_alm["bv01"]
    diff = abs(bv["bv01_net"] - (bv["bv01_actif"] - bv["bv01_passif"]))
    assert diff < 2.0, (  # tolérance 2€ pour arrondis
        f"BV01_net={bv['bv01_net']:.2f} ≠ BV01_actif-BV01_passif="
        f"{bv['bv01_actif']-bv['bv01_passif']:.2f} (écart={diff:.2f})"
    )
    # Impact 200bp = 2 × impact 100bp
    ratio = abs(bv["impact_200bp"] / bv["impact_100bp"]) if bv["impact_100bp"] != 0 else 1
    assert abs(ratio - 2.0) < 0.01, (
        f"Impact 200bp doit être 2× impact 100bp, ratio={ratio:.4f}"
    )


# ── T4 : LCR ≥ seuil → VERT/AMBRE ; LCR < seuil → ROUGE ────────────────────
def test_alm_lcr_conformite(r_alm, r_p3):
    """LCR ≥ 100% (Art. L212-7 CSS) → conforme.
    LCR < 100% → ROUGE (exigence réglementaire).
    """
    lcr = r_alm["lcr"]
    assert lcr["actifs_liquides"] > 0, "Actifs liquides doivent être positifs"
    assert lcr["sorties_nettes_30j"] > 0, "Sorties 30j doivent être positives"
    assert lcr["lcr_ratio"] == round(lcr["actifs_liquides"] / lcr["sorties_nettes_30j"], 2), (
        "LCR = actifs_liquides / sorties_nettes_30j"
    )

    # LCR insuffisant → ROUGE
    r_rouge = AgentSPAlm(verbose=False).run(
        result_p3=r_p3,
        allocation_actif={"obligations_corp": 1.0},
        valeur_actif_total=50_000,
        fonds_propres=0,
        generer_graphiques=False)
    assert r_rouge["statut_rag"] == "ROUGE", (
        f"RAG doit être ROUGE si LCR < {LCR_MIN:.0%}"
    )


# ── T5 : Gap duration = D_actif - D_passif ───────────────────────────────────
def test_alm_gap_coherence(r_alm):
    """Gap = D_actif - D_passif.
    Signe et valeur absolue doivent être cohérents.
    """
    dur = r_alm["duration"]
    gap_calcule = dur["actif"] - dur["passif"]
    assert abs(r_alm["gap"]["gap_duration"] - gap_calcule) < 0.01, (
        f"Gap={r_alm['gap']['gap_duration']:.2f} ≠ D_actif-D_passif={gap_calcule:.2f}"
    )


# ── T6 : Sans P3 → erreur ─────────────────────────────────────────────────────
def test_alm_erreur_sans_p3():
    """P3 est requis. Sans lui, l'agent doit retourner success=False."""
    r = AgentSPAlm(verbose=False).run(result_p3=None, generer_graphiques=False)
    assert r["success"] is False, "Doit échouer sans P3"
    assert r["erreur"] is not None, "Erreur doit être documentée"
    assert r["statut_rag"] == "ROUGE", "RAG doit être ROUGE en cas d'erreur"


# ── T7 : Allocation actif personnalisée ───────────────────────────────────────
def test_alm_allocation_personnalisee(r_p3):
    """Une allocation personnalisée doit modifier la duration actif.
    Allocation 100% OAT (duration 7.5a) vs 100% monétaire (duration 0.25a).
    """
    r_oat = AgentSPAlm(verbose=False).run(
        result_p3=r_p3,
        allocation_actif={"oat_souverain": 1.0},
        fonds_propres=10_000_000, generer_graphiques=False)
    r_mon = AgentSPAlm(verbose=False).run(
        result_p3=r_p3,
        allocation_actif={"monetaire": 1.0},
        fonds_propres=10_000_000, generer_graphiques=False)

    assert r_oat["duration"]["actif"] > r_mon["duration"]["actif"], (
        f"Duration OAT ({r_oat['duration']['actif']:.2f}a) "
        f"doit être > Duration monétaire ({r_mon['duration']['actif']:.2f}a)"
    )
    # LCR 100% OAT doit être bon (OAT = actifs liquides)
    assert r_oat["lcr"]["lcr_ratio"] > LCR_MIN, (
        f"LCR 100% OAT doit être ≥ {LCR_MIN:.0%}"
    )
    # LCR 100% monétaire doit aussi être bon
    assert r_mon["lcr"]["lcr_ratio"] > LCR_MIN, (
        f"LCR 100% monétaire doit être ≥ {LCR_MIN:.0%}"
    )
