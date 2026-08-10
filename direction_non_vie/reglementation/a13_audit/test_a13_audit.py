"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              ACTUARIA — TEST A13 : AUDIT TRAIL                              ║
║              Agent : AgentA13AuditTrail                                     ║
║              7 tests — Production                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys, os
import unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from agent import AgentA13AuditTrail
except ImportError:
    from a13_audit import AgentA13AuditTrail

# ── FIXTURES ──────────────────────────────────────────────────────────────────

def _agent_vert(key):
    """Simule un résultat agent VERT minimal."""
    return {
        "success": True,
        "statut_rag": "VERT",
        "audit_id": f"{key.upper()}_20260101_120000",
        "rapport": {"alertes": []},
        "best_estimate": {"best_estimate": 5_000_000, "cv_inter_methodes": 3.2, "reserve_p90": 5_500_000},
        "scr": {"total": 1_200_000},
        "mcr": {"mcr": 300_000},
        "capital": {"ratio_scr": 185.0},
        "ratio_scr": 185.0,
        "provisions": {"tp_ifrs17": 4_800_000, "taux_actu": 2.5, "conf_ra": "90%"},
        "ecart_s2_ifrs": {"ratio_ifrs_s2": 0.96},
        "reconciliation_s2": {"ratio_ifrs17_s2": 0.96},
        "approche": "PAA",
        "gap_alm": {"gap_duration": 0.3},
        "duration_actifs": {"duration_macaulay": 5.2},
        "duration_passifs": {"duration_macaulay": 4.9},
        "liquidite": {"lcr": 142.0},
        "metriques": {"poisson": {"nb_vars_retenues": 8}},
    }

def _resultats_complets():
    return {f"a{i}": _agent_vert(f"a{i}") for i in range(1, 13)}

def _make_agent():
    return AgentA13AuditTrail(audit_path="/tmp/actuaria", models_path="/tmp/actuaria", verbose=False)

# ── TESTS ─────────────────────────────────────────────────────────────────────

def test_t1_nominal_tous_agents_vert():
    """T1 — Tous agents VERT → succès, statut VERT, hash valide."""
    agent = _make_agent()
    res = agent.run(
        resultats_agents=_resultats_complets(),
        client_nom="Assurance XYZ",
        sous_branche="rc_auto",
        generer_graphiques=False,
    )
    assert res["success"] is True, f"success attendu True, obtenu {res['success']}"
    assert res["statut_rag"] == "VERT", f"statut_rag attendu VERT, obtenu {res['statut_rag']}"
    h = res["hash_session"]
    assert isinstance(h, dict), "hash_session doit être un dict"
    assert len(h.get("hash_sha256", "")) == 64, "hash_sha256 doit faire 64 caractères"
    assert len(h.get("hash_court", "")) == 8, "hash_court doit faire 8 caractères"
    print("T1 ✅ — Nominal tous agents VERT")

def test_t2_agents_manquants_ambre():
    """T2 — Plusieurs agents manquants → statut AMBRE."""
    agent = _make_agent()
    # Garder seulement a7, a10, a11 → 9 agents manquants → AMBRE (> 3 manquants)
    resultats = {
        "a7":  _agent_vert("a7"),
        "a10": _agent_vert("a10"),
        "a11": _agent_vert("a11"),
    }
    res = agent.run(
        resultats_agents=resultats,
        client_nom="Test SA",
        sous_branche="mrh",
        generer_graphiques=False,
    )
    assert res["success"] is True
    assert res["statut_rag"] in ("AMBRE", "ROUGE"),         f"statut attendu AMBRE ou ROUGE avec 9 agents manquants, obtenu {res['statut_rag']}"
    print(f"T2 ✅ — Agents manquants → {res['statut_rag']}")

def test_t3_agent_rouge_statut_rouge():
    """T3 — Un agent en ROUGE → statut global ROUGE."""
    agent = _make_agent()
    resultats = _resultats_complets()
    resultats["a10"]["statut_rag"] = "ROUGE"
    res = agent.run(
        resultats_agents=resultats,
        client_nom="Test SA",
        sous_branche="construction",
        generer_graphiques=False,
    )
    assert res["success"] is True
    assert res["statut_rag"] == "ROUGE",         f"statut attendu ROUGE car a10=ROUGE, obtenu {res['statut_rag']}"
    print("T3 ✅ — Agent ROUGE → statut global ROUGE")

def test_t4_registre_rgpd_structure():
    """T4 — Registre RGPD contient les champs obligatoires."""
    agent = _make_agent()
    res = agent.run(
        resultats_agents=_resultats_complets(),
        client_nom="Mutuelle Sud",
        sous_branche="sante",
        generer_graphiques=False,
    )
    assert res["success"] is True
    rgpd = res["registre_rgpd"]
    for champ in ("responsable_traitement", "client", "traitements", "dpo_contact", "ref_legale"):
        assert champ in rgpd, f"Champ RGPD manquant : {champ}"
    assert len(rgpd["traitements"]) >= 1, "Au moins 1 traitement RGPD attendu"
    assert rgpd["client"] == "Mutuelle Sud"
    print("T4 ✅ — Registre RGPD structuré correctement")

def test_t5_versioning_hypotheses():
    """T5 — Versioning hypothèses contient les modules A7, A10, A11, A12."""
    agent = _make_agent()
    res = agent.run(
        resultats_agents=_resultats_complets(),
        client_nom="Test SA",
        sous_branche="rc_auto",
        generer_graphiques=False,
    )
    assert res["success"] is True
    hyp = res["hypotheses"]
    assert "modules" in hyp, "hypotheses doit contenir 'modules'"
    modules = hyp["modules"]
    assert "provisionnement" in modules, "Module provisionnement manquant"
    assert "solvabilite_2" in modules, "Module solvabilite_2 manquant"
    assert "ifrs_17" in modules, "Module ifrs_17 manquant"
    assert "alm" in modules, "Module alm manquant"
    print("T5 ✅ — Versioning hypothèses complet (A7/A10/A11/A12)")

def test_t6_validation_audit_c1_c2_c3():
    """T6 — Validation audit retourne C1, C2, C3 avec statuts."""
    agent = _make_agent()
    res = agent.run(
        resultats_agents=_resultats_complets(),
        client_nom="Test SA",
        sous_branche="rc_auto",
        generer_graphiques=False,
    )
    assert res["success"] is True
    val = res["validation_audit"]
    for ctrl in ("c1_hash", "c2_rgpd", "c3_versioning"):
        assert ctrl in val, f"Contrôle manquant : {ctrl}"
        assert "statut" in val[ctrl], f"statut manquant dans {ctrl}"
        assert val[ctrl]["statut"] in ("VERT", "AMBRE", "ROUGE")
    assert "statut_global" in val
    print(f"T6 ✅ — Validation audit C1={val['c1_hash']['statut']} C2={val['c2_rgpd']['statut']} C3={val['c3_versioning']['statut']}")

def test_t7_dict_retour_complet():
    """T7 — Dictionnaire de retour contient toutes les clés standard."""
    agent = _make_agent()
    res = agent.run(
        resultats_agents=_resultats_complets(),
        client_nom="Test SA",
        sous_branche="rc_auto",
        generer_graphiques=False,
    )
    cles_attendues = [
        "success", "statut_rag", "logs", "registre_rgpd",
        "hypotheses", "hash_session", "rapport_audit",
        "commentaire", "audit_id", "graphiques",
        "validation_audit", "erreur",
    ]
    for cle in cles_attendues:
        assert cle in res, f"Clé manquante dans le retour : {cle}"
    assert res["erreur"] is None
    assert res["audit_id"].startswith("A13_")
    print("T7 ✅ — Dictionnaire de retour complet")

# ── CE QUE LA GATE VOIT ───────────────────────────────────────────────────────
# ⚠️ LES SEPT FONCTIONS CI-DESSUS ÉTAIENT INVISIBLES À LA GATE. `unittest
# discover` ne collecte que les méthodes des sous-classes de `TestCase` ; sur
# ce fichier il rendait « Ran 0 tests — NO TESTS RAN » et sortait en 0. Sept
# tests réels ne tournaient pas, et la gate déclarait le succès : le silence
# ressemblait au succès.
#
# ⚠️ CETTE CLASSE N'AJOUTE AUCUNE VÉRIFICATION. Chaque méthode appelle sa
# fonction, rien de plus — ce que les tests contrôlent est inchangé, seule leur
# visibilité l'est. `core/test_couverture_gate.py` empêche le trou de se
# rouvrir en silence.

class T13_GateA13Audit(unittest.TestCase):
    """Expose à `unittest discover` les sept tests ci-dessus."""

    def test_t1_nominal_tous_agents_vert(self):
        test_t1_nominal_tous_agents_vert()

    def test_t2_agents_manquants_ambre(self):
        test_t2_agents_manquants_ambre()

    def test_t3_agent_rouge_statut_rouge(self):
        test_t3_agent_rouge_statut_rouge()

    def test_t4_registre_rgpd_structure(self):
        test_t4_registre_rgpd_structure()

    def test_t5_versioning_hypotheses(self):
        test_t5_versioning_hypotheses()

    def test_t6_validation_audit_c1_c2_c3(self):
        test_t6_validation_audit_c1_c2_c3()

    def test_t7_dict_retour_complet(self):
        test_t7_dict_retour_complet()


# ── RUNNER ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_t1_nominal_tous_agents_vert,
        test_t2_agents_manquants_ambre,
        test_t3_agent_rouge_statut_rouge,
        test_t4_registre_rgpd_structure,
        test_t5_versioning_hypotheses,
        test_t6_validation_audit_c1_c2_c3,
        test_t7_dict_retour_complet,
    ]
    passed = 0
    failed = 0
    print("\n" + "="*65)
    print("  ACTUARIA — TEST SUITE A13 : AUDIT TRAIL")
    print("="*65)
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ❌ {t.__name__} ÉCHEC : {e}")
            failed += 1
    print("="*65)
    print(f"  RÉSULTAT : {passed}/{len(tests)} tests passés")
    if failed == 0:
        print("  🟢 TOUS LES TESTS PASSENT")
    else:
        print(f"  🔴 {failed} test(s) en échec")
    print("="*65)
