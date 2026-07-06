"""
Tests unitaires — Agent SP-REG3 : Conformité ANI 2013 + 100% Santé
Direction Santé-Prévoyance · Équipe Réglementation & Finance
Sources : ANI 11/01/2013, Art. L911-7 CSS, Décrets 2019-21, Art. L871-1 CSS
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from direction_sante_prevoyance.reglementation.sp_reg3_ani_100sante.agent import AgentSPReg3ANI100Sante


@pytest.fixture(scope="module")
def r_s1_collectif():
    from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante
    return AgentS1TarificationSante(verbose=False).run(
        nb_assures=1000, age_moyen=40, contrat="collectif",
        garantie_niveau="premium", chargement_pct=0.18,
        generer_graphiques=False)


@pytest.fixture(scope="module")
def r_s1_individuel():
    from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante
    return AgentS1TarificationSante(verbose=False).run(
        nb_assures=200, age_moyen=35, contrat="individuel",
        garantie_niveau="confort", chargement_pct=0.20,
        generer_graphiques=False)


# ── T1 : Succès collectif et individuel ───────────────────────────────────────
def test_reg3_success(r_s1_collectif, r_s1_individuel):
    reg3 = AgentSPReg3ANI100Sante(verbose=False)
    r_c = reg3.run(result_s1=r_s1_collectif, contrat="collectif",
                   generer_graphiques=False)
    r_i = reg3.run(result_s1=r_s1_individuel, contrat="individuel",
                   generer_graphiques=False)
    assert r_c["success"] is True and r_c["erreur"] is None
    assert r_i["success"] is True and r_i["erreur"] is None


# ── T2 : ANI individuel → conforme automatiquement ────────────────────────────
def test_reg3_ani_individuel_conforme(r_s1_individuel):
    """ANI 2013 ne s'applique qu'aux collectifs (Art. L911-7 CSS).
    Un contrat individuel doit toujours être conforme ANI.
    """
    reg3 = AgentSPReg3ANI100Sante(verbose=False)
    r = reg3.run(result_s1=r_s1_individuel, contrat="individuel",
                 generer_graphiques=False)
    assert r["ani_conforme"] is True, (
        "Contrat individuel → ANI conforme auto (Art. L911-7 CSS)"
    )
    notes = [v.get("note", "") for v in r["ani_detail"].values()]
    assert any("N/A" in n for n in notes), (
        "Notes ANI individuel doivent contenir N/A"
    )


# ── T3 : ANI collectif vérifié poste par poste ────────────────────────────────
def test_reg3_ani_collectif_postes(r_s1_collectif):
    """Pour un contrat collectif, chaque poste ANI doit être vérifié."""
    reg3 = AgentSPReg3ANI100Sante(verbose=False)
    r = reg3.run(result_s1=r_s1_collectif, contrat="collectif",
                 generer_graphiques=False)
    detail = r["ani_detail"]
    assert isinstance(r["ani_conforme"], bool)
    # Vérifier que les postes obligatoires sont présents
    for poste in ["medecine", "hospitalisation", "dentaire", "optique"]:
        assert poste in detail, f"Poste ANI manquant : {poste}"


# ── T4 : 100% Santé vérifié ───────────────────────────────────────────────────
def test_reg3_100_sante_verifie(r_s1_collectif):
    """La vérification 100% Santé (RAC 0) doit couvrir optique et dentaire.
    Source : Décrets 2019-21.
    """
    reg3 = AgentSPReg3ANI100Sante(verbose=False)
    r = reg3.run(result_s1=r_s1_collectif, contrat="collectif",
                 inclure_100pct_sante=True, generer_graphiques=False)
    s100 = r["sante_100_detail"]
    assert s100 != {}, "100% Santé doit être vérifié"
    # sante_100_detail contient un sous-dict 'detail' avec les postes
    detail = s100.get("detail", s100)
    assert "optique_rac0" in detail, "Optique RAC 0 doit être dans detail"
    assert "dentaire_rac0" in detail, "Dentaire RAC 0 doit être dans detail"
    assert r["sante_100_conforme"] is not None


# ── T5 : Contrat responsable vérifié ─────────────────────────────────────────
def test_reg3_contrat_responsable(r_s1_collectif):
    """Le contrat responsable doit être vérifié (Art. L871-1 CSS)."""
    reg3 = AgentSPReg3ANI100Sante(verbose=False)
    r = reg3.run(result_s1=r_s1_collectif, contrat="collectif",
                 inclure_contrat_resp=True, generer_graphiques=False)
    cr = r["contrat_resp"]
    assert cr != {}, "Contrat responsable doit être vérifié"
    assert "conforme" in cr
    assert "detail" in cr


# ── T6 : 3 hypothèses présentes ───────────────────────────────────────────────
def test_reg3_hypotheses(r_s1_collectif):
    """SP-Reg3 doit produire 3 hypothèses : ANI, 100%S, contrat responsable."""
    reg3 = AgentSPReg3ANI100Sante(verbose=False)
    r = reg3.run(result_s1=r_s1_collectif, contrat="collectif",
                 generer_graphiques=False)
    assert len(r["hypotheses"]) == 3
    ids = [h["id"] for h in r["hypotheses"]]
    assert "H1" in ids and "H2" in ids and "H3" in ids


# ── T7 : Erreur si S1 absent ──────────────────────────────────────────────────
def test_reg3_erreur_sans_s1():
    reg3 = AgentSPReg3ANI100Sante(verbose=False)
    r = reg3.run(result_s1=None, contrat="collectif", generer_graphiques=False)
    assert r["success"] is False
    assert r["erreur"] is not None
