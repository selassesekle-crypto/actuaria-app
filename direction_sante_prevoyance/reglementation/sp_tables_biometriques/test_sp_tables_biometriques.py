"""
Tests unitaires — Agent SP-TABLES : Tables Biométriques Santé-Prévoyance
Direction Santé-Prévoyance — Équivalent SP de A14 (Non-Vie/Vie)
BCAC 2019, TD 88-90, TH 00-02, annuités rentes IP, validation A/E
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from direction_sante_prevoyance.reglementation.sp_tables_biometriques.agent import (
    AgentSPTablesBiometriques,
    EIOPA_RFR_PROXY, AE_SEUIL_BAS, AE_SEUIL_HAUT,
    _BCAC_2019_RAW, _TH0002_QX
)


@pytest.fixture(scope="module")
def agent():
    return AgentSPTablesBiometriques(verbose=False)


@pytest.fixture(scope="module")
def r_nominal(agent):
    return agent.run(age=42.0, csp="employe", table="BCAC2019",
                     taux_actu=EIOPA_RFR_PROXY, horizon_rente=20,
                     generer_graphiques=False)


# ── T1 : Succès et structure standard ────────────────────────────────────────
def test_tables_success_et_structure(r_nominal):
    """SP-TABLES doit réussir et retourner les 5 modules biométriques."""
    assert r_nominal["success"] is True, "Doit réussir"
    assert r_nominal["erreur"] is None, "Pas d'erreur"
    assert r_nominal["statut_rag"] in ("VERT","AMBRE","ROUGE"), "RAG invalide"
    for cle in ["bcac2019","td8890","th0002","annuites","validation_ae",
                "hypotheses","commentaire"]:
        assert cle in r_nominal, f"Clé manquante : {cle}"
    assert len(r_nominal["hypotheses"]) == 3, "3 hypothèses attendues"


# ── T2 : BCAC 2019 — cohérence cadre/non-cadre et monotonie ─────────────────
def test_tables_bcac2019_coherence(agent):
    """BCAC 2019 : taux cadre < non-cadre à tout âge (segmentation CSP).
    Monotonie croissante : taux augmente avec l'âge (vieillissement).
    Source : BCAC 2019 — Statistiques arrêts de travail.
    """
    taux_prec = 0.0
    for age in [25, 30, 35, 40, 45, 50, 55, 60]:
        r_c  = agent.run(age=age, csp="cadre", generer_graphiques=False)
        r_nc = agent.run(age=age, csp="employe", generer_graphiques=False)
        # Cadre < non-cadre
        assert r_c["bcac2019"]["taux_cadre"] < r_nc["bcac2019"]["taux_non_cadre"], (
            f"Âge {age} : taux cadre doit être < non-cadre"
        )
        # Monotonie
        taux = r_nc["bcac2019"]["taux_itt_annuel"]
        assert taux > taux_prec, (
            f"Taux ITT doit croître avec l'âge : {taux:.4%} <= {taux_prec:.4%} à {age} ans"
        )
        taux_prec = taux


# ── T3 : TD 88-90 — décroissance stricte du maintien ────────────────────────
def test_tables_td8890_decroissance(r_nominal):
    """TD 88-90 : P(maintien t mois) doit être strictement décroissante.
    Un assuré ne peut pas revenir en arrêt après guérison dans cette table.
    Source : TD 88-90 — Tables de maintien INSEE/BCAC.
    """
    maintien = r_nominal["td8890"]["maintien_par_mois"]
    assert len(maintien) == 24, f"TD 88-90 doit avoir 24 mois, obtenu {len(maintien)}"
    for i in range(1, len(maintien)):
        assert maintien[i] < maintien[i-1], (
            f"Maintien doit décroître : P({i+1}m)={maintien[i]:.4f} >= P({i}m)={maintien[i-1]:.4f}"
        )
    # Bornes : P(1m) < 1 et P(24m) > 0
    assert maintien[0] < 1.0, "P(1m) doit être < 1"
    assert maintien[-1] > 0.0, "P(24m) doit être > 0"


# ── T4 : TH 00-02 — mortalité croissante avec l'âge ─────────────────────────
def test_tables_th0002_monotonie(agent):
    """TH 00-02 : qx doit croître avec l'âge (mortalité population active).
    Source : INSEE/BCAC — Tables réglementaires TH 00-02.
    """
    ages = [25, 30, 35, 40, 45, 50, 55, 60]
    qx_vals = []
    for age in ages:
        r = agent.run(age=age, csp="cadre", generer_graphiques=False)
        qx_vals.append(r["th0002"]["q_x"])
    # Vérifier la monotonie
    for i in range(1, len(qx_vals)):
        assert qx_vals[i] > qx_vals[i-1], (
            f"qx doit croître avec l'âge : qx({ages[i]})={qx_vals[i]:.6f} "
            f"<= qx({ages[i-1]})={qx_vals[i-1]:.6f}"
        )
    # Vérifier les bornes [0, 1]
    for qx in qx_vals:
        assert 0 < qx < 1, f"qx doit être dans ]0,1[ : {qx}"


# ── T5 : Annuités viagères — propriétés mathématiques ────────────────────────
def test_tables_annuites_proprietes(agent):
    """Annuités ä_x : décroissantes avec le taux d'actualisation.
    Annuité différée < annuité immédiate (actualisation sur n années).
    Source : actuariat standard + EIOPA RFR Art.77 S2.
    """
    # Décroissance avec le taux
    r1 = agent.run(age=45.0, csp="cadre", taux_actu=0.01, generer_graphiques=False)
    r2 = agent.run(age=45.0, csp="cadre", taux_actu=0.04, generer_graphiques=False)
    assert r1["annuites"]["annuite_imm"] > r2["annuites"]["annuite_imm"], (
        f"ä(1%)={r1['annuites']['annuite_imm']:.4f} doit être > ä(4%)={r2['annuites']['annuite_imm']:.4f}"
    )
    # Annuité différée < annuité immédiate
    r3 = agent.run(age=40.0, csp="employe", generer_graphiques=False)
    ann = r3["annuites"]
    assert ann["annuite_diff_5"] < ann["annuite_imm"], (
        f"ä_diff(5) = {ann['annuite_diff_5']:.4f} doit être < ä_imm = {ann['annuite_imm']:.4f}"
    )
    # Annuité positive
    assert ann["annuite_imm"] > 0, "Annuité immédiate doit être positive"


# ── T6 : A/E ratio — cohérence et alertes ────────────────────────────────────
def test_tables_ae_ratio(agent):
    """A/E ratio : validation données client vs BCAC 2019.
    A/E ≈ 1.0 pour portefeuille cohérent BCAC.
    A/E > 1.2 → ROUGE (sur-sinistralité), A/E < 0.8 → VERT ou AMBRE.
    """
    # Sans données client → A/E non disponible
    r_sans = agent.run(age=40.0, csp="employe", generer_graphiques=False)
    assert r_sans["validation_ae"]["disponible"] is False, (
        "A/E ne doit pas être disponible sans données client"
    )

    # Portefeuille cohérent (A/E ≈ 1.0)
    taux_exp = 0.066  # non-cadre 40 ans BCAC 2019
    nb_ass   = 1000
    r_ok = agent.run(age=40.0, csp="employe",
                      donnees_client={"nb_assures": nb_ass,
                                      "nb_sinistres_observes": round(taux_exp * nb_ass),
                                      "age_moyen": 40.0},
                      generer_graphiques=False)
    assert r_ok["validation_ae"]["disponible"] is True
    ae = r_ok["validation_ae"]["ae_ratio"]
    assert AE_SEUIL_BAS <= ae <= AE_SEUIL_HAUT, (
        f"A/E cohérent doit être ∈ [{AE_SEUIL_BAS},{AE_SEUIL_HAUT}] : {ae:.3f}"
    )

    # Portefeuille sur-sinistrant → ROUGE
    r_rouge = agent.run(age=40.0, csp="employe",
                         donnees_client={"nb_assures": 500,
                                         "nb_sinistres_observes": 100,
                                         "age_moyen": 40.0},
                         generer_graphiques=False)
    assert r_rouge["statut_rag"] == "ROUGE", (
        f"RAG doit être ROUGE si A/E > {AE_SEUIL_HAUT}"
    )


# ── T7 : Normalisation CSP ───────────────────────────────────────────────────
def test_tables_normalisation_csp(agent):
    """Normalisation CSP : "cadre", "cadre_sup" → cadre ; autres → non_cadre.
    Les deux groupes doivent donner des taux différents (segmentation BCAC).
    """
    for csp_cadre in ["cadre", "cadre_sup"]:
        r = agent.run(age=40.0, csp=csp_cadre, generer_graphiques=False)
        assert r["csp"] == "cadre", (
            f"CSP='{csp_cadre}' doit être normalisée en 'cadre', obtenu '{r['csp']}'"
        )
    for csp_nc in ["employe", "ouvrier", "non_cadre", "technicien"]:
        r = agent.run(age=40.0, csp=csp_nc, generer_graphiques=False)
        assert r["csp"] == "non_cadre", (
            f"CSP='{csp_nc}' doit être normalisée en 'non_cadre', obtenu '{r['csp']}'"
        )
