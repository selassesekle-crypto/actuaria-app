"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              ACTUARIA — TEST A14 : TABLES DE MORTALITÉ                     ║
║              Agent : AgentA14Mortalite                                      ║
║              7 tests — Production                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

import numpy as np
try:
    from agent import AgentA14Mortalite, TABLES_DISPONIBLES
except ImportError:
    from a14_mortalite import AgentA14Mortalite, TABLES_DISPONIBLES

# ── FIXTURES ──────────────────────────────────────────────────────────────────

def _make_agent():
    return AgentA14Mortalite(models_path="/tmp/actuaria", audit_path="/tmp/actuaria", verbose=False)

# ── TESTS ─────────────────────────────────────────────────────────────────────

def test_t1_nominal_th0002_homme_65():
    """T1 — Nominal TH0002 homme 65 ans → succès, résultats cohérents."""
    agent = _make_agent()
    res = agent.run(age=65, sexe="H", table="TH0002", taux_actu=0.02,
                    projeter_lee_carter=True, generer_graphiques=False)
    assert res["success"] is True, f"success attendu True, obtenu {res['success']}"
    assert res["statut_rag"] == "VERT"
    assert res["table"] == "TH0002"
    # Espérance de vie à 65 ans : doit être entre 15 et 30 ans
    ev = res["esperance_vie"]["e_x_complete"]
    assert 15 <= ev <= 30, f"Espérance de vie à 65 ans hors plage [15,30] : {ev}"
    # Annuité immédiate : doit être entre 8 et 20
    ann = res["annuites"]["annuite_imm"]
    assert 8 <= ann <= 20, f"Annuité immédiate hors plage [8,20] : {ann}"
    print(f"T1 ✅ — TH0002 H65 | e_65={ev:.2f} ans | ä_65={ann:.4f}")

def test_t2_nominal_tf0002_femme_45():
    """T2 — Nominal TF0002 femme 45 ans → espérance de vie > homme même âge."""
    agent = _make_agent()
    res_f = agent.run(age=45, sexe="F", table="TF0002", taux_actu=0.02,
                      projeter_lee_carter=False, generer_graphiques=False)
    res_h = agent.run(age=45, sexe="H", table="TH0002", taux_actu=0.02,
                      projeter_lee_carter=False, generer_graphiques=False)
    assert res_f["success"] is True
    assert res_h["success"] is True
    ev_f = res_f["esperance_vie"]["e_x_complete"]
    ev_h = res_h["esperance_vie"]["e_x_complete"]
    assert ev_f > ev_h, f"Espérance vie femme ({ev_f}) doit dépasser homme ({ev_h})"
    print(f"T2 ✅ — TF0002 F45 e={ev_f:.2f} > TH0002 H45 e={ev_h:.2f}")

def test_t3_qx_contrainte_01():
    """T3 — H3 : qx ∈ [0,1] pour toutes les tables disponibles."""
    for nom_table, qx in TABLES_DISPONIBLES.items():
        arr = np.array(qx)
        assert np.all(arr >= 0), f"{nom_table} : qx < 0 détecté"
        assert np.all(arr <= 1), f"{nom_table} : qx > 1 détecté"
    print(f"T3 ✅ — qx ∈ [0,1] validé pour {list(TABLES_DISPONIBLES.keys())}")

def test_t4_capitaux_deces_relation_fondamentale():
    """T4 — Relation fondamentale : ä_x ≈ (1 - A_x) / d."""
    agent = _make_agent()
    taux = 0.03
    res = agent.run(age=60, sexe="H", table="TH0002", taux_actu=taux,
                    projeter_lee_carter=False, generer_graphiques=False)
    assert res["success"] is True
    ann_imm = res["annuites"]["annuite_imm"]
    relation_check = res["capitaux_deces"]["relation_check"]
    # Les deux doivent être proches (tolérance 5%)
    ecart = abs(ann_imm - relation_check) / max(ann_imm, 1e-6)
    assert ecart < 0.05, f"Relation ä_x=(1-A_x)/d écart {ecart:.2%} > 5%"
    print(f"T4 ✅ — Relation fondamentale : ä_60={ann_imm:.4f} ≈ check={relation_check:.4f} (écart {ecart:.2%})")

def test_t5_lee_carter_reduction_mortalite():
    """T5 — Projection Lee-Carter : qx projeté < qx actuel (amélioration)."""
    agent = _make_agent()
    res = agent.run(age=70, sexe="H", table="TH0002", taux_actu=0.02,
                    projeter_lee_carter=True, horizon_proj=20, generer_graphiques=False)
    assert res["success"] is True
    lc = res["lee_carter"]
    qx_actuel = lc["q_x_actuel"]
    qx_20ans = lc["q_x_projete"].get("q_70_dans_20ans", None)
    assert qx_20ans is not None, "q_70_dans_20ans manquant dans lee_carter"
    assert qx_20ans < qx_actuel,         f"Lee-Carter : qx projeté ({qx_20ans}) doit être < qx actuel ({qx_actuel})"
    derive = lc["derive_annuelle"]
    assert derive < 0, f"Dérive annuelle doit être négative (amélioration) : {derive}"
    print(f"T5 ✅ — Lee-Carter : qx_70 {qx_actuel:.6f} → {qx_20ans:.6f} dans 20 ans (dérive {derive:.2f}%/an)")

def test_t6_validation_ae_table_identique():
    """T6 — Ratio A/E = 1.0 si table_client identique à table référence."""
    agent = _make_agent()
    from direction_non_vie.reglementation.a14_mortalite.agent import TH0002
    res = agent.run(age=50, sexe="H", table="TH0002", taux_actu=0.02,
                    table_client=TH0002,
                    projeter_lee_carter=False, generer_graphiques=False)
    assert res["success"] is True
    ae = res["validation_ae"]["ae_ratio"]
    assert abs(ae - 1.0) < 0.01, f"Ratio A/E attendu ≈ 1.0 avec tables identiques, obtenu {ae}"
    print(f"T6 ✅ — Ratio A/E = {ae:.4f} ≈ 1.0 (tables identiques)")

def test_t7_dict_retour_complet():
    """T7 — Dictionnaire de retour contient toutes les clés standard."""
    agent = _make_agent()
    res = agent.run(age=65, sexe="H", table="TH0002", taux_actu=0.02,
                    projeter_lee_carter=True, generer_graphiques=False)
    cles_attendues = [
        "success", "table", "age", "sexe", "statut_rag",
        "probabilites", "esperance_vie", "annuites", "capitaux_deces",
        "validation_ae", "lee_carter", "makeham_gompertz",
        "rapport", "commentaire", "audit_id", "graphiques",
        "validation_mortalite", "erreur",
    ]
    for cle in cles_attendues:
        assert cle in res, f"Clé manquante dans le retour : {cle}"
    assert res["erreur"] is None
    assert res["audit_id"].startswith("A14_")
    # Validation mortalité H1/H2/H3
    val = res["validation_mortalite"]
    for h in ("h1_lee_carter", "h2_coherence", "h3_qx_valide"):
        assert h in val, f"Hypothèse manquante : {h}"
        assert val[h]["statut"] in ("VERT", "AMBRE", "ROUGE")
    print(f"T7 ✅ — Dict retour complet | H1={val['h1_lee_carter']['statut']} H2={val['h2_coherence']['statut']} H3={val['h3_qx_valide']['statut']}")

# ── RUNNER ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_t1_nominal_th0002_homme_65,
        test_t2_nominal_tf0002_femme_45,
        test_t3_qx_contrainte_01,
        test_t4_capitaux_deces_relation_fondamentale,
        test_t5_lee_carter_reduction_mortalite,
        test_t6_validation_ae_table_identique,
        test_t7_dict_retour_complet,
    ]
    passed = 0
    failed = 0
    print("\n" + "="*65)
    print("  ACTUARIA — TEST SUITE A14 : TABLES DE MORTALITÉ")
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
