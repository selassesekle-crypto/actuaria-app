"""
Tests SP-REG1 — AgentSPReg1Solvabilite2
7 tests couvrant : QRT S.05.01, SFCR A-E, ORSA, cohérence inter-QRT,
SCR/MCR consolidé, RAG, cas d'insuffisance de solvabilité.
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from direction_sante_prevoyance.reglementation.sp_reg1_solvabilite2.agent import (
    AgentSPReg1Solvabilite2,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _result_s3(
    be_sante=500_000.0,
    scr_sante=75_000.0,
    mcr_sante=25_000.0,
    fonds_propres=300_000.0,
    primes_acquises=1_000_000.0,
    risk_adjustment=5_000.0,
):
    """Simule un résultat S3 Binta conforme."""
    return {
        "success":         True,
        "agent":           "Binta",
        "be_sante":        be_sante,
        "risk_adjustment": risk_adjustment,
        "tp_sante":        be_sante + risk_adjustment,
        "scr_sante":       scr_sante,
        "mcr_sante":       mcr_sante,
        "fonds_propres":   fonds_propres,
        "primes_acquises": primes_acquises,
        "ratio_scr_pct":   fonds_propres / scr_sante * 100,
        "ratio_mcr_pct":   fonds_propres / mcr_sante * 100,
        "qrt_s13": {
            "code": "S.13.01",
            "lignes": [
                {"code": "R0100", "C0010": primes_acquises},
            ],
        },
        "hypotheses":  [],
        "commentaire": "S3 test",
        "graphiques":  {},
        "statut_rag":  "VERT",
        "erreur":      None,
    }


def _result_p4(
    be_prevoyance=300_000.0,
    scr_invalidite=60_000.0,
    mcr=20_000.0,
    fonds_propres=300_000.0,
    primes_acquises=600_000.0,
    risk_adjustment=9_000.0,
):
    """Simule un résultat P4 Valentin conforme."""
    return {
        "success":          True,
        "agent":            "Valentin",
        "be_prevoyance":    be_prevoyance,
        "risk_adjustment":  risk_adjustment,
        "tp_prevoyance":    be_prevoyance + risk_adjustment,
        "scr_invalidite":   scr_invalidite,
        "mcr":              mcr,
        "fonds_propres":    fonds_propres,
        "ratio_scr_pct":    fonds_propres / scr_invalidite * 100,
        "ratio_mcr_pct":    fonds_propres / mcr * 100,
        "pm_rentes_ip":     100_000.0,
        "psap_total":       80_000.0,
        "prec":             10_000.0,
        "sorties_naomie": {
            "be_prevoyance":  be_prevoyance,
            "tp_prevoyance":  be_prevoyance + risk_adjustment,
            "scr_invalidite": scr_invalidite,
            "mcr":            mcr,
            "primes_acquises": primes_acquises,
            "fonds_propres":  fonds_propres,
        },
        "qrt_s14": {"code": "S.14.01", "lignes": []},
        "hypotheses":  [],
        "commentaire": "P4 test",
        "graphiques":  {},
        "statut_rag":  "VERT",
        "erreur":      None,
    }


def _agent():
    return AgentSPReg1Solvabilite2(audit_path="/tmp/sp_reg1_tests", verbose=False)


# ── TEST 1 — Structure de base et contrat de sortie ───────────────────────────

def test_t1_contrat_sortie_complet():
    """
    T1 — Le dict de retour contient toutes les clés du contrat standard ActuarIA
    plus les clés spécifiques SP-REG1 (bilan S2, QRT, SFCR, ORSA).
    """
    agent = _agent()
    r = agent.run(
        result_s3=_result_s3(),
        result_p4=_result_p4(),
        date_arrete="31/12/2025",
        entite="Mutuelle Test SP",
        generer_graphiques=False,
    )

    # Contrat standard ActuarIA
    assert r["success"] is True, "success doit être True"
    assert r["agent"] == "SP-Reg1-S2"
    assert r["statut_rag"] in ("VERT", "AMBRE", "ROUGE")
    assert isinstance(r["audit_id"], str) and r["audit_id"].startswith("REG1_")
    assert isinstance(r["hypotheses"], list)
    assert isinstance(r["commentaire"], str) and len(r["commentaire"]) > 50
    assert isinstance(r["graphiques"], dict)
    assert r["erreur"] is None

    # Bilan S2
    for k in ("be_sante", "be_prevoyance", "be_total",
               "scr_sante", "scr_prevoyance", "scr_consolide",
               "mcr_consolide", "fonds_propres",
               "ratio_scr_pct", "ratio_mcr_pct", "diversification"):
        assert k in r, f"Clé manquante : {k}"
        assert isinstance(r[k], (int, float)), f"{k} doit être numérique"

    # QRT / SFCR / ORSA
    assert "qrt_s05" in r and isinstance(r["qrt_s05"], dict)
    assert "coherence_qrts" in r and isinstance(r["coherence_qrts"], dict)
    assert "sfcr_sections" in r and isinstance(r["sfcr_sections"], list)
    assert "orsa_resume" in r and isinstance(r["orsa_resume"], dict)

    print("  ✅ T1 PASSÉ — contrat de sortie complet")


# ── TEST 2 — QRT S.05.01 structure correcte ──────────────────────────────────

def test_t2_qrt_s05_structure():
    """
    T2 — Le QRT S.05.01 contient les 4 lignes réglementaires obligatoires
    (R0010 primes, R0050 sinistres, R0090 dépenses, R0200 provisions)
    avec des colonnes C0030 (NSLT) et C0060 (SLT) positives.
    """
    agent = _agent()
    r = agent.run(
        result_s3=_result_s3(be_sante=500_000, primes_acquises=1_000_000),
        result_p4=_result_p4(be_prevoyance=300_000, primes_acquises=600_000),
        generer_graphiques=False,
    )

    qrt = r["qrt_s05"]
    assert qrt["code"] == "S.05.01", "Code QRT incorrect"

    codes_attendus = {"R0010", "R0050", "R0090", "R0200"}
    codes_obtenus = {l["code"] for l in qrt["lignes"]}
    assert codes_attendus == codes_obtenus, (
        f"Lignes QRT manquantes : {codes_attendus - codes_obtenus}"
    )

    for ligne in qrt["lignes"]:
        assert ligne["C0030"] >= 0, f"C0030 négatif : {ligne['code']}"
        assert ligne["C0060"] >= 0, f"C0060 négatif : {ligne['code']}"
        assert ligne["total"] == ligne["C0030"] + ligne["C0060"], (
            f"Total incohérent ligne {ligne['code']}"
        )

    # R0010 primes : C0030=pa_sante=1_000_000 + C0060=pa_prev=600_000 = 1_600_000
    r0010 = next(l for l in qrt["lignes"] if l["code"] == "R0010")
    assert r0010["C0030"] == 1_000_000, (
        f"C0030 (santé) attendu 1_000_000, obtenu {r0010['C0030']}"
    )
    assert r0010["C0060"] == 600_000, (
        f"C0060 (prévoyance) attendu 600_000, obtenu {r0010['C0060']}"
    )
    assert r0010["total"] == 1_600_000, (
        f"Total primes attendu 1_600_000, obtenu {r0010['total']}"
    )

    print("  ✅ T2 PASSÉ — QRT S.05.01 structure conforme")


# ── TEST 3 — SFCR 5 sections A-E présentes ───────────────────────────────────

def test_t3_sfcr_cinq_sections():
    """
    T3 — Le SFCR contient exactement 5 sections (A, B, C, D, E) chacune
    avec un titre, un contenu non vide et des données_cles.
    """
    agent = _agent()
    r = agent.run(
        result_s3=_result_s3(),
        result_p4=_result_p4(),
        entite="Mutuelle Test SP",
        generer_graphiques=False,
    )

    sfcr = r["sfcr_sections"]
    assert len(sfcr) == 5, f"SFCR doit avoir 5 sections, obtenu {len(sfcr)}"

    codes_attendus = ["A", "B", "C", "D", "E"]
    codes_obtenus  = [s["code"] for s in sfcr]
    assert codes_obtenus == codes_attendus, (
        f"Codes SFCR incorrects : {codes_obtenus}"
    )

    for s in sfcr:
        assert "titre" in s and len(s["titre"]) > 3, (
            f"Titre manquant section {s['code']}"
        )
        assert "contenu" in s and len(s["contenu"]) > 20, (
            f"Contenu vide section {s['code']}"
        )
        assert "donnees_cles" in s and isinstance(s["donnees_cles"], dict), (
            f"donnees_cles manquant section {s['code']}"
        )

    # Section A doit mentionner les primes
    sect_a = next(s for s in sfcr if s["code"] == "A")
    assert "primes" in sect_a["contenu"].lower() or "M€" in sect_a["contenu"], (
        "Section A doit mentionner les primes acquises"
    )

    # Section E doit mentionner le ratio SCR
    sect_e = next(s for s in sfcr if s["code"] == "E")
    assert "scr" in sect_e["contenu"].lower() or "%" in sect_e["contenu"], (
        "Section E doit mentionner le ratio SCR"
    )

    print("  ✅ T3 PASSÉ — SFCR 5 sections A-E conformes")


# ── TEST 4 — Cohérence inter-QRT (4 contrôles C1-C4) ────────────────────────

def test_t4_coherence_inter_qrt():
    """
    T4 — Les 4 contrôles de cohérence inter-QRT sont présents (C1-C4).
    Avec des données cohérentes, tous doivent passer (ok=True).
    """
    agent = _agent()
    r = agent.run(
        result_s3=_result_s3(
            be_sante=500_000,
            scr_sante=75_000,
            mcr_sante=25_000,
            fonds_propres=400_000,
        ),
        result_p4=_result_p4(
            be_prevoyance=300_000,
            scr_invalidite=60_000,
            mcr=20_000,
            fonds_propres=400_000,
        ),
        generer_graphiques=False,
    )

    coh = r["coherence_qrts"]
    assert "ok_global" in coh
    assert "controles" in coh
    assert "nb_ok" in coh
    assert "nb_total" in coh
    assert coh["nb_total"] == 4, (
        f"4 contrôles attendus, obtenu {coh['nb_total']}"
    )

    ids_attendus = {"C1", "C2", "C3", "C4"}
    ids_obtenus  = {c["id"] for c in coh["controles"]}
    assert ids_attendus == ids_obtenus, (
        f"Contrôles manquants : {ids_attendus - ids_obtenus}"
    )

    for c in coh["controles"]:
        assert "controle" in c and len(c["controle"]) > 5
        assert "ok" in c and isinstance(c["ok"], bool)
        assert "note" in c

    # C1 — BE cohérent (be_total = be_sante + be_prevoyance)
    c1 = next(c for c in coh["controles"] if c["id"] == "C1")
    assert c1["ok"] is True, f"C1 échoue : {c1['note']}"

    # C2 — SCR consolidé ≤ somme modules (diversification)
    c2 = next(c for c in coh["controles"] if c["id"] == "C2")
    assert c2["ok"] is True, f"C2 échoue : {c2['note']}"

    # C3 — FP ≥ SCR (400k > ~95k consolidé)
    c3 = next(c for c in coh["controles"] if c["id"] == "C3")
    assert c3["ok"] is True, f"C3 échoue : {c3['note']}"

    # C4 — FP ≥ MCR
    c4 = next(c for c in coh["controles"] if c["id"] == "C4")
    assert c4["ok"] is True, f"C4 échoue : {c4['note']}"

    print("  ✅ T4 PASSÉ — 4 contrôles inter-QRT C1-C4 conformes")


# ── TEST 5 — SCR consolidé et diversification (formule EIOPA Annexe IV) ──────

def test_t5_scr_consolide_formule_eiopa():
    """
    T5 — Le SCR consolidé suit la formule EIOPA Annexe IV :
    SCR = sqrt(SCR_S² + 2×ρ×SCR_S×SCR_P + SCR_P²) avec ρ=0.25.
    Le bénéfice de diversification = SCR_S + SCR_P - SCR_consolidé > 0.
    """
    agent = _agent()
    scr_s = 100_000.0
    scr_p = 80_000.0
    rho   = 0.25

    r = agent.run(
        result_s3=_result_s3(scr_sante=scr_s, fonds_propres=500_000),
        result_p4=_result_p4(scr_invalidite=scr_p, fonds_propres=500_000),
        generer_graphiques=False,
    )

    scr_attendu = math.sqrt(scr_s**2 + 2*rho*scr_s*scr_p + scr_p**2)
    div_attendue = scr_s + scr_p - scr_attendu

    scr_obtenu = r["scr_consolide"]
    div_obtenu = r["diversification"]

    assert abs(scr_obtenu - scr_attendu) < 1.0, (
        f"SCR consolidé incorrect : attendu {scr_attendu:.2f}, obtenu {scr_obtenu:.2f}"
    )
    assert abs(div_obtenu - div_attendue) < 1.0, (
        f"Diversification incorrecte : attendu {div_attendue:.2f}, obtenu {div_obtenu:.2f}"
    )
    assert div_obtenu > 0, "Le bénéfice de diversification doit être positif"

    # Ratio SCR = FP / SCR_consolidé × 100
    ratio_attendu = 500_000 / scr_attendu * 100
    assert abs(r["ratio_scr_pct"] - ratio_attendu) < 0.1, (
        f"Ratio SCR incorrect : attendu {ratio_attendu:.1f}%, obtenu {r['ratio_scr_pct']:.1f}%"
    )

    print(f"  ✅ T5 PASSÉ — SCR consolidé={scr_obtenu:,.0f}€ "
          f"(ρ=0.25) | Diversification={div_obtenu:,.0f}€")


# ── TEST 6 — ORSA résumé exécutif ────────────────────────────────────────────

def test_t6_orsa_resume():
    """
    T6 — L'ORSA résumé contient les champs obligatoires Art.45 S2 :
    ratio_scr_baseline, solvabilite_actuelle, evaluation_risques, conclusion.
    Avec result_st, les stress tests sont intégrés.
    """
    agent = _agent()

    # Sans stress tests
    r_base = agent.run(
        result_s3=_result_s3(),
        result_p4=_result_p4(),
        generer_graphiques=False,
    )
    orsa = r_base["orsa_resume"]

    champs_obligatoires = [
        "date", "ratio_scr_baseline", "solvabilite_actuelle",
        "evaluation_risques", "conclusion"
    ]
    for champ in champs_obligatoires:
        assert champ in orsa, f"Champ ORSA manquant : {champ}"

    assert isinstance(orsa["ratio_scr_baseline"], float)
    assert len(orsa["conclusion"]) > 10

    # Avec stress tests (Naomie)
    result_st_mock = {
        "success": True,
        "pire_scenario": "pandemie",
        "scenarios": {
            "pandemie":  {"ratio_scr_stresse": 115.0},
            "morbidite": {"ratio_scr_stresse": 128.0},
        },
    }
    r_stress = agent.run(
        result_s3=_result_s3(),
        result_p4=_result_p4(),
        result_st=result_st_mock,
        generer_graphiques=False,
    )
    orsa_st = r_stress["orsa_resume"]
    assert orsa_st["stress_tests"] is not None, "stress_tests absent avec result_st"
    assert "pire_scenario" in orsa_st["stress_tests"]
    assert orsa_st["stress_tests"]["pire_scenario"] == "pandemie"
    assert orsa_st["stress_tests"]["ratio_stresse"] == 115.0
    assert "pandemie" in orsa_st["conclusion"].lower()

    print("  ✅ T6 PASSÉ — ORSA résumé conforme Art.45 S2 (avec et sans stress tests)")


# ── TEST 7 — RAG ROUGE si ratio SCR < 100% ───────────────────────────────────

def test_t7_rag_rouge_insuffisance_solvabilite():
    """
    T7 — Si les fonds propres sont inférieurs au SCR consolidé,
    le statut RAG doit être ROUGE, H1 NON VALIDÉE,
    et le contrôle C3 doit échouer.
    """
    agent = _agent()

    # FP = 50k, SCR_S = 75k, SCR_P = 60k → SCR_consolidé ≈ 107k > FP
    # (formule EIOPA ρ=0.25 : sqrt(75k²+2×0.25×75k×60k+60k²) ≈ 107 121)
    r = agent.run(
        result_s3=_result_s3(scr_sante=75_000, mcr_sante=25_000, fonds_propres=50_000),
        result_p4=_result_p4(scr_invalidite=60_000, mcr=20_000, fonds_propres=50_000),
        generer_graphiques=False,
    )

    assert r["statut_rag"] == "ROUGE", (
        f"RAG doit être ROUGE en cas d'insuffisance SCR, obtenu : {r['statut_rag']}"
    )

    # H1 (ratio SCR ≥ 100%) doit être NON VALIDÉE
    h1 = next(h for h in r["hypotheses"] if h["id"] == "H1")
    assert h1["statut"] == "NON VALIDÉE", (
        f"H1 doit être NON VALIDÉE, obtenu : {h1['statut']}"
    )

    # Ratio SCR < 100%
    assert r["ratio_scr_pct"] < 100.0, (
        f"Ratio SCR doit être < 100%, obtenu {r['ratio_scr_pct']:.1f}%"
    )

    # C3 (FP ≥ SCR) doit échouer
    c3 = next(c for c in r["coherence_qrts"]["controles"] if c["id"] == "C3")
    assert c3["ok"] is False, "C3 doit être False quand FP < SCR"

    # ok_global cohérence doit être False
    assert r["coherence_qrts"]["ok_global"] is False

    print(f"  ✅ T7 PASSÉ — RAG=ROUGE | Ratio SCR={r['ratio_scr_pct']:.1f}% | "
          f"FP={r['fonds_propres']:,.0f}€ < SCR={r['scr_consolide']:,.0f}€")


# ── RUNNER ────────────────────────────────────────────────────────────────────

def pytest_approx(val, rel=0.01):
    """Helper minimal pour tests sans pytest."""
    return val  # utilisé uniquement dans les assertions relatives


if __name__ == "__main__":
    tests = [
        test_t1_contrat_sortie_complet,
        test_t2_qrt_s05_structure,
        test_t3_sfcr_cinq_sections,
        test_t4_coherence_inter_qrt,
        test_t5_scr_consolide_formule_eiopa,
        test_t6_orsa_resume,
        test_t7_rag_rouge_insuffisance_solvabilite,
    ]

    print("=" * 65)
    print("  TESTS SP-REG1 — AgentSPReg1Solvabilite2")
    print("  QRT S.05 | SFCR A-E | ORSA | Cohérence inter-QRT | SCR/MCR")
    print("=" * 65)

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ {test.__name__} ÉCHOUÉ : {e}")
            failed += 1

    print("=" * 65)
    print(f"  Résultat : {passed}/{len(tests)} tests passés")
    if failed == 0:
        print("  ✅ TOUS LES TESTS SP-REG1 PASSENT")
    else:
        print(f"  ❌ {failed} test(s) en échec")
    print("=" * 65)
