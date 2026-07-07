"""
Tests unitaires — Agent SP-ST Naomie : Stress Testing Santé-Prévoyance
Direction Santé-Prévoyance
Sources : RD 2015/35 Art.145/159, EIOPA ORSA Guidelines 2016
"""
import pytest
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from direction_sante_prevoyance.reglementation.sp_st_stress_testing.agent import (
    AgentSPStressTestingNaomie, SCENARIOS
)


@pytest.fixture(scope="module")
def pipeline_st():
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
    return r_s3, r_p4


@pytest.fixture(scope="module")
def r_st(pipeline_st):
    r_s3, r_p4 = pipeline_st
    return AgentSPStressTestingNaomie(verbose=False).run(
        result_s3=r_s3, result_p4=r_p4,
        fonds_propres=15_000_000, generer_graphiques=False)


# ── T1 : Succès et 4 scénarios ────────────────────────────────────────────────
def test_st_success_et_scenarios(r_st):
    """4 scénarios calculés : pandémie, morbidité, cessation, adverse."""
    assert r_st["success"] is True, "Naomie doit réussir"
    assert r_st["erreur"] is None, "Pas d'erreur attendue"
    assert r_st["statut_rag"] in ("VERT", "AMBRE", "ROUGE"), "RAG invalide"
    assert len(r_st["scenarios"]) == 4, f"Attendu 4 scénarios, obtenu {len(r_st['scenarios'])}"
    for nom in ["pandemie", "morbidite", "cessation", "adverse"]:
        assert nom in r_st["scenarios"], f"Scénario manquant : {nom}"


# ── T2 : Ratio stressé toujours ≤ ratio baseline ─────────────────────────────
def test_st_ratios_stresses_inferieurs(r_st):
    """Un stress test doit toujours dégrader le ratio SCR.
    Ratio stressé ≤ ratio baseline pour tous les scénarios.
    """
    baseline = r_st["ratio_scr_baseline"]
    for nom, r in r_st["scenarios"].items():
        assert r["ratio_scr_stresse"] <= baseline + 0.01, (
            f"Scénario {nom} : ratio stressé ({r['ratio_scr_stresse']:.1f}%) "
            f"> baseline ({baseline:.1f}%) — stress ne peut pas améliorer"
        )


# ── T3 : Perte positive pour chaque scénario ─────────────────────────────────
def test_st_pertes_positives(r_st):
    """Chaque scénario de stress doit générer une perte (delta BE > 0).
    Aucun stress ne peut améliorer le bilan.
    """
    for nom, r in r_st["scenarios"].items():
        assert r["perte_totale"] > 0, (
            f"Scénario {nom} : perte ({r['perte_totale']:.0f}€) doit être > 0"
        )


# ── T4 : Scénario adverse = perte max ─────────────────────────────────────────
def test_st_adverse_pire_scenario(r_st):
    """Le scénario adverse (combiné) doit être le pire de tous.
    Il cumule pandémie + morbidité + cessation + mortalité.
    Source : EIOPA ORSA Guidelines 2016.
    """
    pertes = {nom: r["perte_totale"] for nom, r in r_st["scenarios"].items()}
    assert pertes["adverse"] >= pertes["pandemie"], (
        f"Adverse ({pertes['adverse']:.0f}€) doit être ≥ pandémie ({pertes['pandemie']:.0f}€)"
    )
    assert pertes["adverse"] >= pertes["morbidite"], (
        f"Adverse ({pertes['adverse']:.0f}€) doit être ≥ morbidité ({pertes['morbidite']:.0f}€)"
    )


# ── T5 : Choc morbidité EIOPA ≥ choc cessation ────────────────────────────────
def test_st_morbidite_superieur_cessation(r_st):
    """Le choc morbidité (+35%) doit générer plus de pertes que la cessation (-20%).
    Source : RD 2015/35 Art.145 — choc morbidité > choc cessation.
    """
    p_morb = r_st["scenarios"]["morbidite"]["perte_totale"]
    p_cess = r_st["scenarios"]["cessation"]["perte_totale"]
    assert p_morb >= p_cess, (
        f"Morbidité ({p_morb:.0f}€) doit être ≥ cessation ({p_cess:.0f}€)"
    )


# ── T6 : 3 hypothèses ORSA ────────────────────────────────────────────────────
def test_st_hypotheses_orsa(r_st):
    """3 hypothèses ORSA : baseline, pandémie, pire scénario."""
    hyp = r_st["hypotheses"]
    assert len(hyp) == 3
    ids = [h["id"] for h in hyp]
    assert "H1" in ids and "H2" in ids and "H3" in ids, f"IDs ORSA manquants : {ids}"


# ── T7 : Erreur si S3 absent ──────────────────────────────────────────────────
def test_st_erreur_sans_inputs(pipeline_st):
    """Naomie doit retourner success=False si result_s3 est absent."""
    _, r_p4 = pipeline_st
    naomie = AgentSPStressTestingNaomie(verbose=False)
    r = naomie.run(result_s3=None, result_p4=r_p4, generer_graphiques=False)
    assert r["success"] is False, "Doit échouer sans S3"
    assert r["erreur"] is not None, "Message d'erreur attendu"
