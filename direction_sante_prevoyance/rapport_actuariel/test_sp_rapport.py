"""
Tests unitaires — Agent SP-RAPPORT : Rapport Actuariel Santé-Prévoyance
Direction Santé-Prévoyance
Équivalent SP de A7 Ibrahim (Non-Vie) — Pipeline M1→M5
"""
import pytest
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from direction_sante_prevoyance.rapport_actuariel.agent import AgentSPRapportActuariel


@pytest.fixture(scope="module")
def pipeline_complet():
    """Pipeline complet S1→S3 + P1→P4 + Coord + REG2 + REG3."""
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder
    from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante
    from direction_sante_prevoyance.sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
    from direction_sante_prevoyance.sante.s3_reporting.agent import AgentS3ReportingSante
    from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
    from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
    from direction_sante_prevoyance.prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
    from direction_sante_prevoyance.prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
    from direction_sante_prevoyance.coordination.sp_coord.agent import AgentSPCoord

    np.random.seed(42)
    n = 1000
    df_m = pd.DataFrame({
        "age": np.random.randint(25, 60, n),
        "garanties": np.random.choice(["confort","premium"], n),
        "sinistres_sante": np.random.exponential(600, n),
        "cotisation": np.random.uniform(900, 1800, n),
    })
    df_ip = pd.DataFrame({
        "age": np.random.randint(30, 58, n),
        "salaire_brut": np.random.uniform(30000, 70000, n),
        "csp": np.random.choice(["employe","cadre","ouvrier"], n, p=[0.5,0.3,0.2]),
        "arrets_itt": np.where(np.random.rand(n)<0.08, np.random.uniform(30,180,n), 0),
    })
    r_bm  = SPDataBuilder(verbose=False).construire(df_m)
    r_bip = SPDataBuilder(verbose=False).construire(df_ip)

    r_s1 = AgentS1TarificationSante(verbose=False).run(
        result_a2=r_bm, nb_assures=1000, age_moyen=40,
        contrat="collectif", garantie_niveau="confort", generer_graphiques=False)
    r_s2 = AgentS2ProvissionnementSante(verbose=False).run(
        result_s1=r_s1, generer_graphiques=False)
    r_s3 = AgentS3ReportingSante(verbose=False).run(
        result_s1=r_s1, result_s2=r_s2, fonds_propres=5_000_000, generer_graphiques=False)
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
    r_coord = AgentSPCoord(verbose=False).run(
        result_s3=r_s3, result_p4=r_p4, fonds_propres=15_000_000,
        generer_graphiques=False)

    return r_s1, r_s2, r_s3, r_p1, r_p2, r_p3, r_p4, r_coord


@pytest.fixture(scope="module")
def r_rapport(pipeline_complet):
    r_s1,r_s2,r_s3,r_p1,r_p2,r_p3,r_p4,r_coord = pipeline_complet
    return AgentSPRapportActuariel(verbose=False).run(
        result_s1=r_s1, result_s2=r_s2, result_s3=r_s3,
        result_p1=r_p1, result_p2=r_p2, result_p3=r_p3, result_p4=r_p4,
        result_coord=r_coord,
        entite="Mutuelle Test", date_arrete="31/12/2025",
        fonds_propres=15_000_000, generer_graphiques=False)


# ── T1 : Succès et structure standard ────────────────────────────────────────
def test_rapport_success_et_structure(r_rapport):
    """Pipeline M1→M5 doit réussir et retourner toutes les clés standard."""
    assert r_rapport["success"] is True, "SP-Rapport doit réussir"
    assert r_rapport["erreur"] is None, "Pas d'erreur attendue"
    assert r_rapport["statut_rag"] in ("VERT","AMBRE","ROUGE"), "RAG invalide"
    for cle in ["m1","m2","m3","m4","hypotheses","commentaire",
                "excel_bytes","word_bytes","pdf_bytes","audit_trail","session_hash"]:
        assert cle in r_rapport, f"Clé manquante : {cle}"


# ── T2 : 10 modules chargés (S1-S3, P1-P4, SP-Coord) ────────────────────────
def test_rapport_modules_disponibles(r_rapport):
    """Le rapport doit détecter et utiliser tous les modules du pipeline SP."""
    modules = r_rapport["modules_disponibles"]
    for attendu in ["S1","S2","S3","P1","P2","P3","P4","SP-Coord"]:
        assert attendu in modules, f"Module manquant : {attendu}"


# ── T3 : BE total = BE_santé + BE_prévoyance ─────────────────────────────────
def test_rapport_be_identite(r_rapport):
    """Identité comptable : BE_total = BE_santé + BE_prévoyance."""
    m1  = r_rapport["m1"]
    m4  = r_rapport["m4"]
    be_calc = m1["be_sante"] + m1["be_prev"]
    assert abs(m4["be_total"] - be_calc) < 0.01, (
        f"BE_total ({m4['be_total']:.2f}) ≠ BE_S+BE_P ({be_calc:.2f})"
    )
    assert m4["be_total"] > 0, "BE total doit être positif"


# ── T4 : Livrables M5 produits (Excel + Word + PDF) ──────────────────────────
def test_rapport_livrables_m5(r_rapport):
    """Les 3 livrables M5 doivent être des bytes non vides.
    Équivalent des excel_bytes/word_bytes/pdf_bytes de A7 Ibrahim (Non-Vie).
    """
    assert isinstance(r_rapport["excel_bytes"], bytes), "Excel doit être bytes"
    assert isinstance(r_rapport["word_bytes"], bytes), "Word doit être bytes"
    assert isinstance(r_rapport["pdf_bytes"], bytes), "PDF/HTML doit être bytes"
    # Excel et Word doivent avoir une taille minimale
    assert len(r_rapport["excel_bytes"]) > 1000, (
        f"Excel trop petit : {len(r_rapport['excel_bytes'])} bytes"
    )
    assert len(r_rapport["word_bytes"]) > 1000, (
        f"Word trop petit : {len(r_rapport['word_bytes'])} bytes"
    )


# ── T5 : Hash de session SHA-256 cohérent ────────────────────────────────────
def test_rapport_hash_session(r_rapport):
    """Le hash de session doit être présent et identique dans le retour et l'audit.
    Garantit l'intégrité des résultats (équivalent du hash A13 Non-Vie).
    """
    h = r_rapport["session_hash"]
    assert len(h) == 8, f"Hash attendu 8 chars, obtenu : {len(h)}"
    assert h == r_rapport["audit_trail"]["session_hash"], (
        "Hash retour ≠ hash audit trail"
    )
    assert h.isupper() or h.isalnum(), f"Hash format invalide : {h}"


# ── T6 : Dégradation gracieuse (S3+P4 seulement) ────────────────────────────
def test_rapport_degradation_gracieuse(pipeline_complet):
    """Le rapport doit fonctionner même avec seulement S3 et P4 disponibles.
    Propriété différenciante : pas de plantage si certains agents sont absents.
    """
    _, _, r_s3, _, _, _, r_p4, _ = pipeline_complet
    r = AgentSPRapportActuariel(verbose=False).run(
        result_s3=r_s3, result_p4=r_p4,
        fonds_propres=15_000_000, generer_graphiques=False)
    assert r["success"] is True, "Doit réussir avec S3+P4 seulement"
    assert r["be_total"] > 0, f"BE doit être > 0 avec S3+P4 : {r['be_total']}"
    assert "S3" in r["modules_disponibles"], "S3 doit être détecté"
    assert "P4" in r["modules_disponibles"], "P4 doit être détecté"


# ── T7 : Avis actuariel conforme aux 3 valeurs attendues ─────────────────────
def test_rapport_avis_actuariel(r_rapport):
    """L'avis actuariel doit être FAVORABLE, AVEC RÉSERVES ou DÉFAVORABLE.
    C'est le verdict final du rapport — présenté au CA et à l'ACPR.
    """
    avis = r_rapport["avis_actuariel"]
    assert avis in ("FAVORABLE","AVEC RÉSERVES","DÉFAVORABLE"), (
        f"Avis invalide : {avis}"
    )
    rag = r_rapport["statut_rag"]
    avis_attendu = ("FAVORABLE" if rag=="VERT" else
                    "AVEC RÉSERVES" if rag=="AMBRE" else "DÉFAVORABLE")
    assert avis == avis_attendu, (
        f"Incohérence RAG/Avis : RAG={rag} → attendu {avis_attendu}, obtenu {avis}"
    )
