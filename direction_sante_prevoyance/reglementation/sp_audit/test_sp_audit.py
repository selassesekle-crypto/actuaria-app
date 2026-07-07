"""
Tests unitaires — Agent SP-AUDIT : Audit Trail Santé-Prévoyance
Direction Santé-Prévoyance — Équivalent SP de A13 (Non-Vie)
5 modules : logs SP, RGPD Art.30, versioning hypothèses, hash SHA-256, rapport
"""
import pytest
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from direction_sante_prevoyance.reglementation.sp_audit.agent import (
    AgentSPAuditTrail, AGENTS_SP, HYPOTHESES_SP_REF, CATEGORIES_DONNEES_SP
)


@pytest.fixture(scope="module")
def resultats_sp():
    """Pipeline S1-S3 + P1-P4 — inputs complets pour SP-AUDIT."""
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
        "garanties": np.random.choice(["confort", "premium"], n),
        "sinistres_sante": np.random.exponential(600, n),
        "cotisation": np.random.uniform(900, 1800, n),
    })
    df_ip = pd.DataFrame({
        "age": np.random.randint(30, 58, n),
        "salaire_brut": np.random.uniform(30000, 70000, n),
        "csp": np.random.choice(["employe", "cadre", "ouvrier"], n, p=[0.5, 0.3, 0.2]),
        "arrets_itt": np.where(np.random.rand(n) < 0.08, np.random.uniform(30, 180, n), 0),
    })
    r_bm  = SPDataBuilder(verbose=False).construire(df_m)
    r_bip = SPDataBuilder(verbose=False).construire(df_ip)

    r_s1 = AgentS1TarificationSante(verbose=False).run(result_a2=r_bm, nb_assures=1000, age_moyen=40, contrat="collectif", garantie_niveau="confort", generer_graphiques=False)
    r_s2 = AgentS2ProvissionnementSante(verbose=False).run(result_s1=r_s1, generer_graphiques=False)
    r_s3 = AgentS3ReportingSante(verbose=False).run(result_s1=r_s1, result_s2=r_s2, fonds_propres=5_000_000, generer_graphiques=False)
    r_p1 = AgentP1TarificationPrevoyance(verbose=False).run(result_a2=r_bip, age=42, salaire_brut=45000, categorie="employe", generer_graphiques=False)
    r_p2 = AgentP2TablesMorbidite(verbose=False).run(result_p1=r_p1, generer_graphiques=False)
    r_p3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)
    r_p4 = AgentP4ReportingPrevoyance(verbose=False).run(result_p1=r_p1, result_p2=r_p2, result_p3=r_p3, fonds_propres=10_000_000, generer_graphiques=False)

    return {"s1":r_s1,"s2":r_s2,"s3":r_s3,"p1":r_p1,"p2":r_p2,"p3":r_p3,"p4":r_p4}


@pytest.fixture(scope="module")
def r_audit(resultats_sp):
    return AgentSPAuditTrail(verbose=False).run(
        resultats_agents=resultats_sp,
        client_nom="Mutuelle Test",
        actuaire_resp="Jean Dupont, AIA",
        date_arrete="31/12/2025",
        generer_graphiques=False)


# ── T1 : Succès et structure standard ────────────────────────────────────────
def test_audit_success_et_structure(r_audit):
    """SP-AUDIT doit réussir et retourner les 5 modules + standard ActuarIA."""
    assert r_audit["success"] is True, "SP-AUDIT doit réussir"
    assert r_audit["erreur"] is None, "Pas d'erreur attendue"
    assert r_audit["statut_rag"] in ("VERT","AMBRE","ROUGE"), "RAG invalide"
    for cle in ["logs","registre_rgpd","hypotheses","hash_session",
                "rapport_audit","hypotheses_rag","commentaire"]:
        assert cle in r_audit, f"Module manquant : {cle}"


# ── T2 : Module 1 — Collecte logs SP ─────────────────────────────────────────
def test_audit_collecte_logs(r_audit):
    """Les 7 agents fournis (S1-S3, P1-P4) doivent être collectés.
    Agents manquants (SP-Coord, REG, etc.) doivent être listés comme optionnels.
    """
    logs = r_audit["logs"]
    assert logs["nb_agents"] == 7, (
        f"Attendu 7 agents, collecté {logs['nb_agents']}"
    )
    cles_exec = [a["cle"] for a in logs["agents_executes"]]
    for cle in ["s1","s2","s3","p1","p2","p3","p4"]:
        assert cle in cles_exec, f"Agent {cle} non collecté"
    # Agents manquants — tous optionnels dans ce test
    for m in logs["agents_manquants"]:
        assert "critique" not in m or "ℹ️" in m, (
            f"Agent critique signalé manquant alors qu'il devrait être présent : {m}"
        )


# ── T3 : Module 2 — Registre RGPD Art.30 ─────────────────────────────────────
def test_audit_registre_rgpd(r_audit):
    """Le registre RGPD Art.30 doit couvrir les 4 catégories de données SP.
    Données de santé et données d'arrêts ITT doivent être marquées sensibles.
    """
    rgpd = r_audit["registre_rgpd"]
    assert rgpd["conformite"]["rgpd_art30"] == "✅ Registre tenu", (
        "Registre RGPD Art.30 non conforme"
    )
    categories = rgpd["categories_donnees"]
    assert len(categories) == 4, f"Attendu 4 catégories, obtenu {len(categories)}"
    sensibles = [c["categorie"] for c in categories if c["sensible"]]
    assert "Données de santé" in sensibles, "Données de santé doivent être sensibles"
    assert "Données d'arrêts de travail" in sensibles, (
        "Données d'arrêts ITT doivent être sensibles"
    )
    assert len(rgpd["finalites"]) >= 3, "Finalités RGPD insuffisantes"


# ── T4 : Module 3 — Versioning hypothèses SP ─────────────────────────────────
def test_audit_versioning_hypotheses(r_audit):
    """12 hypothèses de référence SP doivent être versionnées et sourcées.
    Couvre BCAC 2019, TD 88-90, TH 00-02, ANI 2013, DREES, EIOPA RFR, SCR.
    """
    hyp = r_audit["hypotheses"]
    assert len(hyp["hypotheses_reference"]) == 12, (
        f"Attendu 12 hypothèses ref, obtenu {len(hyp['hypotheses_reference'])}"
    )
    # Vérifier les versions clés
    assert "BCAC 2019" in hyp["version_bcac"], "Version BCAC 2019 absente"
    assert "DREES 2023" in hyp["version_drees"], "Version DREES 2023 absente"
    assert "ANI 2013" in hyp["version_ani"], "Version ANI 2013 absente"
    # Toutes les hypothèses de référence doivent avoir source
    for h in hyp["hypotheses_reference"]:
        assert h.get("source"), f"Hypothèse sans source : {h.get('id','?')}"


# ── T5 : Module 4 — Hash SHA-256 reproductible ───────────────────────────────
def test_audit_hash_reproductible(resultats_sp):
    """Le hash SHA-256 doit être identique pour les mêmes inputs et date.
    Garantit la reproductibilité et l'intégrité des calculs SP.
    """
    audit = AgentSPAuditTrail(verbose=False)
    r_a = audit.run(resultats_agents=resultats_sp,
                     client_nom="Test", date_arrete="31/12/2025",
                     generer_graphiques=False)
    r_b = audit.run(resultats_agents=resultats_sp,
                     client_nom="Test", date_arrete="31/12/2025",
                     generer_graphiques=False)
    assert r_a["hash_session"] == r_b["hash_session"], (
        f"Hash non reproductible : {r_a['hash_session']} ≠ {r_b['hash_session']}"
    )
    assert len(r_a["hash_session"]) == 16, (
        f"Hash doit faire 16 chars (SHA-256[:16]) : {r_a['hash_session']}"
    )


# ── T6 : Agents critiques manquants → RAG ROUGE ──────────────────────────────
def test_audit_rouge_si_critiques_manquants():
    """Sans aucun agent, H1 (agents critiques absents) → RAG ROUGE.
    Comportement de sécurité : l'audit ne peut pas être VERT sans les agents métier.
    """
    r = AgentSPAuditTrail(verbose=False).run(
        resultats_agents={},
        client_nom="Test vide",
        generer_graphiques=False)
    assert r["success"] is True, "SP-AUDIT doit réussir même sans agents"
    assert r["statut_rag"] == "ROUGE", (
        f"RAG doit être ROUGE sans agents critiques, obtenu : {r['statut_rag']}"
    )
    assert r["logs"]["nb_agents"] == 0, "0 agents doit être collecté"
    h1 = next(h for h in r["hypotheses_rag"] if h["id"]=="H1")
    assert h1["statut"] == "NON VALIDÉE", (
        f"H1 doit être NON VALIDÉE sans agents critiques"
    )


# ── T7 : Module 5 — Rapport d'audit 5 sections ──────────────────────────────
def test_audit_rapport_cinq_sections(r_audit):
    """Le rapport d'audit doit contenir les 5 sections obligatoires.
    Sections : identification, chaîne traitement, hypothèses, alertes, RGPD.
    """
    rapport = r_audit["rapport_audit"]
    assert "sections" in rapport, "sections manquantes dans le rapport"
    assert len(rapport["sections"]) == 5, (
        f"Attendu 5 sections, obtenu {len(rapport['sections'])}"
    )
    numeros = [s["numero"] for s in rapport["sections"]]
    for n in [1, 2, 3, 4, 5]:
        assert n in numeros, f"Section {n} manquante"
    assert rapport["avis"] in ("FAVORABLE","AVEC RÉSERVES","DÉFAVORABLE"), (
        f"Avis invalide : {rapport['avis']}"
    )
    assert rapport["hash_session"] == r_audit["hash_session"], (
        "Hash session incohérent entre retour et rapport"
    )
