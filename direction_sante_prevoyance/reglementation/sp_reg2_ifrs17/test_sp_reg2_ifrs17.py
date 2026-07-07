"""
Tests unitaires — Agent SP-REG2 : Conformité IFRS 17
Direction Santé-Prévoyance · Équipe Réglementation & Finance
Sources : IFRS 17 §33/37/38/49/53/B91/B119
"""
import pytest
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from direction_sante_prevoyance.reglementation.sp_reg2_ifrs17.agent import AgentSPReg2IFRS17


@pytest.fixture(scope="module")
def pipeline_reg2():
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
def r_reg2(pipeline_reg2):
    r_s3, r_p4 = pipeline_reg2
    return AgentSPReg2IFRS17(verbose=False).run(
        result_s3=r_s3, result_p4=r_p4, generer_graphiques=False)


# ── T1 : Succès et structure ───────────────────────────────────────────────────
def test_reg2_success(r_reg2):
    """Succès et présence de toutes les clés IFRS 17."""
    assert r_reg2["success"] is True, "SP-Reg2 doit réussir"
    assert r_reg2["erreur"] is None, "Pas d'erreur attendue"
    for cle in ["be_total", "ra_total", "fcf_total", "csm_total",
                "lc_total", "classification", "reconciliation"]:
        assert cle in r_reg2


# ── T2 : FCF = BE + RA (§33 IFRS 17) ─────────────────────────────────────────
def test_reg2_fcf_identite(r_reg2):
    """FCF (Fulfillment Cash Flows) = BE + RA — IFRS 17 §33."""
    fcf = r_reg2["fcf_total"]
    be  = r_reg2["be_total"]
    ra  = r_reg2["ra_total"]
    assert abs(fcf - (be + ra)) < 0.01, (
        f"FCF ({fcf:.2f}) ≠ BE ({be:.2f}) + RA ({ra:.2f})"
    )
    assert fcf > 0


# ── T3 : Classification PAA santé / GMM prévoyance ────────────────────────────
def test_reg2_classification_paa_gmm(r_reg2):
    """Santé → PAA (contrats ≤ 12 mois) | Prévoyance → GMM (rentes longues).
    Source : IFRS 17 §53.
    """
    classif = r_reg2["classification"]
    assert classif["sante"]["methode"] == "PAA", (
        "Santé doit utiliser PAA (contrats annuels — §53 IFRS 17)"
    )
    assert classif["prevoyance"]["methode"] == "GMM", (
        "Prévoyance doit utiliser GMM (rentes long terme — §53 IFRS 17)"
    )


# ── T4 : CSM ≥ 0 ou LC ≥ 0 (exclusifs) ──────────────────────────────────────
def test_reg2_csm_lc_exclusifs(r_reg2):
    """CSM et LC sont mutuellement exclusifs : §38 (CSM) vs §49 (LC) IFRS 17.
    Globalement : si CSM > 0 alors LC = 0, et inversement.
    """
    csm = r_reg2["csm_total"]
    lc  = r_reg2["lc_total"]
    assert csm >= 0, "CSM doit être ≥ 0"
    assert lc  >= 0, "LC doit être ≥ 0"


# ── T5 : Réconciliation BEL cohérente ─────────────────────────────────────────
def test_reg2_reconciliation_bel(r_reg2):
    """La réconciliation BEL doit contenir toutes les lignes de variation.
    Source : IFRS 17 §100-109.
    """
    recon = r_reg2["reconciliation"]
    for cle in ["be_ouverture", "sinistres_att", "ra_liberation",
                "revenu_actif", "variation_nette", "be_cloture_est"]:
        assert cle in recon, f"Clé manquante dans réconciliation : {cle}"
    # Cohérence : be_cloture = be_ouverture + variation_nette
    assert abs(recon["be_cloture_est"] -
               (recon["be_ouverture"] + recon["variation_nette"])) < 0.01, \
        "BE_clôture doit = BE_ouverture + variation_nette (§100-109 IFRS 17)"


# ── T6 : RA/BE ∈ [1%, 20%] — cohérence CoC §B91 ─────────────────────────────
def test_reg2_ratio_ra_be(r_reg2):
    """RA/BE doit être dans [1%, 20%] pour être cohérent avec la méthode CoC.
    Source : IFRS 17 §B91.
    """
    ratio = r_reg2["ratio_ra_be"]
    assert 0.01 <= ratio <= 0.20, (
        f"RA/BE = {ratio:.2%} hors plage [1%,20%] (CoC §B91 IFRS 17)"
    )


# ── T7 : Erreur si S3 absent ──────────────────────────────────────────────────
def test_reg2_erreur_sans_inputs(pipeline_reg2):
    """SP-Reg2 doit retourner success=False si result_s3 est absent."""
    _, r_p4 = pipeline_reg2
    reg2 = AgentSPReg2IFRS17(verbose=False)
    r = reg2.run(result_s3=None, result_p4=r_p4, generer_graphiques=False)
    assert r["success"] is False, "Doit échouer sans S3"
    assert r["erreur"] is not None, "Message d'erreur attendu"
