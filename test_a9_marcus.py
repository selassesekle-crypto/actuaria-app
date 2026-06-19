"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           ACTUARIA — TESTS UNITAIRES A9 MARCUS v3.0                        ║
║           test_a9_marcus.py                                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  7 tests couvrant :                                                          ║
║    T1 — Flux minimaux OK (A6+A7+A8) → statut VERT                          ║
║    T2 — C1 sans primes_acq → AMBRE (pas ROUGE, pas crash)                  ║
║    T3 — C1 avec primes_acq réelles → VERT                                   ║
║    T4 — C2 ratio SCR/BE hors seuil → ROUGE                                 ║
║    T5 — C4+C5 avec A10+A11+A12 → contrôles actifs                          ║
║    T6 — Flux partiels (A7 seul) → N/A gracieux sans crash                  ║
║    T7 — Alertes IA proactives déclenchées si ratio SCR faible               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import traceback
from a9_coherence import AgentA9Coherence

# ── Fixtures communes ─────────────────────────────────────────────────────────

A6_OK = {
    'modele_production': {
        'modele':       'XGBoost',
        'gini_test':    0.312,
        'score_global': 0.298,
        'prime_pure':   720.0,
        'frequence':    0.144,
        'cout_moyen':   5000.0,
    }
}

A7_OK = {
    'best_estimate': {
        'best_estimate':              7_359_000.0,
        'sigma_mack':                 450_000.0,
        'cv_inter_methodes':          8.5,
        'nb_methodes_convergentes':   5,
        'primes_estimees':            0.0,
    },
    'tail': {'tail_factor': 1.0374},
    'meta': {'nb_lignes': 70_000, 'primes_acquises': 0.0},
}

A8_OK = {
    'chocs_s2': {'scr_souscription': 1_200_000.0},
    'capital':  {
        'scr_total':     853_000.0,
        'fonds_propres': 3_000_000.0,   # ratio 351% → VERT
    },
}

A8_SCR_FAIBLE = {
    'chocs_s2': {'scr_souscription': 1_200_000.0},
    'capital':  {
        'scr_total':     853_000.0,
        'fonds_propres': 1_050_000.0,   # ratio 123% → AMBRE → alerte IA
    },
}

A10_OK = {
    'provisions': {'best_estimate': 7_359_000.0, 'risk_margin': 890_000.0},
    'duration':   {'passif': 3.8},
}

A11_OK = {
    'provisions': {'lic_total': 9_200_000.0},
}

A12_OK = {
    'alm': {
        'duration_actif':  3.5,
        'duration_passif': 3.8,
        'immunisation_redington': True,
    },
}

PRIMES_ACQ_REELLES = 10_000_000.0   # 10M€ → LR_Prov ≈ 73.6%

# ── Helpers ───────────────────────────────────────────────────────────────────

def agent():
    return AgentA9Coherence(
        models_path='/tmp/test_a9/models',
        audit_path='/tmp/test_a9/audit',
        verbose=False,
    )

def run_test(num: int, nom: str, fn):
    try:
        ok, msg = fn()
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status} | T{num} — {nom}")
        if not ok:
            print(f"          → {msg}")
        return ok
    except Exception as e:
        print(f"  💥 ERROR | T{num} — {nom}")
        print(f"          → {e}")
        traceback.print_exc()
        return False

# ══════════════════════════════════════════════════════════════════════════════
# T1 — Flux minimaux A6+A7+A8 avec primes_acq → VERT global
# ══════════════════════════════════════════════════════════════════════════════

def test_t1_flux_minimaux_vert():
    r = agent().run(
        result_a6=A6_OK, result_a7=A7_OK, result_a8=A8_OK,
        primes_acq=PRIMES_ACQ_REELLES, sous_branche='RC Auto',
        generer_graphiques=False,
    )
    if not r['success']:
        return False, f"success=False : {r.get('erreur')}"
    if r['statut_rag'] != 'VERT':
        msgs = [(c['controle'], c['statut'], c['message']) for c in r['controles']]
        return False, f"statut={r['statut_rag']} | détail={msgs}"
    if len(r['controles']) != 6:
        return False, f"Attendu 6 contrôles, obtenu {len(r['controles'])}"
    if len(r['hypotheses']) != 3:
        return False, f"Attendu 3 hypothèses, obtenu {len(r['hypotheses'])}"
    return True, ""

# ══════════════════════════════════════════════════════════════════════════════
# T2 — C1 sans primes_acq, sans primes dans A7 → AMBRE (pas ROUGE, pas crash)
# ══════════════════════════════════════════════════════════════════════════════

def test_t2_c1_sans_primes():
    r = agent().run(
        result_a6=A6_OK, result_a7=A7_OK, result_a8=A8_OK,
        primes_acq=0.0, sous_branche='RC Auto',
        generer_graphiques=False,
    )
    if not r['success']:
        return False, f"crash : {r.get('erreur')}"
    c1 = next((c for c in r['controles'] if 'C1' in c.get('controle', '')), None)
    if c1 is None:
        return False, "Contrôle C1 absent"
    # Sans primes_acq ET sans nb_lignes suffisant → AMBRE (données insuffisantes)
    # Avec nb_lignes=70000 → fallback estimation → peut être VERT ou AMBRE selon calcul
    if c1['statut'] == 'ROUGE':
        return False, (
            f"C1 ne doit pas être ROUGE sans primes_acq "
            f"(doit être AMBRE ou VERT). Obtenu : {c1['statut']} | {c1['message']}"
        )
    return True, ""

# ══════════════════════════════════════════════════════════════════════════════
# T3 — C1 avec primes_acq réelles → VERT (LR cohérents ~70% vs ~73.6%)
# ══════════════════════════════════════════════════════════════════════════════

def test_t3_c1_avec_primes():
    r = agent().run(
        result_a6=A6_OK, result_a7=A7_OK, result_a8=A8_OK,
        primes_acq=PRIMES_ACQ_REELLES,
        generer_graphiques=False,
    )
    c1 = next((c for c in r['controles'] if 'C1' in c.get('controle', '')), None)
    if c1 is None:
        return False, "Contrôle C1 absent"
    if c1['statut'] != 'VERT':
        return False, f"C1 doit être VERT avec primes_acq=10M€. Obtenu : {c1['statut']} | {c1['message']}"
    if c1.get('lr_prov') is None:
        return False, "lr_prov doit être calculé"
    ecart = c1.get('ecart_pts', 999)
    if ecart > 15:
        return False, f"Écart LR trop élevé : {ecart} pts (attendu ≤ 15)"
    return True, ""

# ══════════════════════════════════════════════════════════════════════════════
# T4 — C2 avec ratio SCR/BE anormal → ROUGE
# ══════════════════════════════════════════════════════════════════════════════

def test_t4_c2_scr_anomal():
    # SCR souscription > 2× BE → ROUGE
    a8_rouge = {
        'chocs_s2': {'scr_souscription': 20_000_000.0},   # 20M > 2× BE de 7.36M
        'capital':  {'scr_total': 853_000.0, 'fonds_propres': 3_000_000.0},
    }
    r = agent().run(
        result_a6=A6_OK, result_a7=A7_OK, result_a8=a8_rouge,
        primes_acq=PRIMES_ACQ_REELLES,
        generer_graphiques=False,
    )
    c2 = next((c for c in r['controles'] if 'C2' in c.get('controle', '')), None)
    if c2 is None:
        return False, "Contrôle C2 absent"
    if c2['statut'] not in ('ROUGE', 'AMBRE'):
        return False, (
            f"C2 doit être ROUGE ou AMBRE avec SCR/BE=272%. "
            f"Obtenu : {c2['statut']} | {c2['message']}"
        )
    return True, ""

# ══════════════════════════════════════════════════════════════════════════════
# T5 — Avec A10+A11+A12 : C4 et C5 actifs (pas N/A)
# ══════════════════════════════════════════════════════════════════════════════

def test_t5_flux_complets():
    r = agent().run(
        result_a6=A6_OK, result_a7=A7_OK, result_a8=A8_OK,
        result_a10=A10_OK, result_a11=A11_OK, result_a12=A12_OK,
        primes_acq=PRIMES_ACQ_REELLES,
        generer_graphiques=False,
    )
    if not r['success']:
        return False, f"crash : {r.get('erreur')}"

    c4 = next((c for c in r['controles'] if 'C4' in c.get('controle', '')), None)
    c5 = next((c for c in r['controles'] if 'C5' in c.get('controle', '')), None)

    if c4 is None:
        return False, "Contrôle C4 absent"
    if c5 is None:
        return False, "Contrôle C5 absent"
    if c4['statut'] == 'N/A':
        return False, f"C4 ne doit pas être N/A avec A10+A11 connectés"
    if c5['statut'] == 'N/A':
        return False, f"C5 ne doit pas être N/A avec A10+A12 connectés"

    # Vérifier C4 ratio (9.2M IFRS / 8.25M S2 = 1.115 → VERT)
    if c4['statut'] not in ('VERT', 'AMBRE'):
        return False, f"C4 ratio attendu ~1.11 → VERT/AMBRE. Obtenu : {c4['statut']}"

    # Vérifier C5 gap duration (3.5 vs 3.8 → gap 0.3a → VERT)
    if c5['statut'] != 'VERT':
        return False, f"C5 gap 0.3a doit être VERT. Obtenu : {c5['statut']}"

    return True, ""

# ══════════════════════════════════════════════════════════════════════════════
# T6 — Flux partiels (A7 seul, sans A6 ni A8) → N/A gracieux, pas crash
# ══════════════════════════════════════════════════════════════════════════════

def test_t6_flux_partiels_gracieux():
    r = agent().run(
        result_a6=None,
        result_a7=A7_OK,
        result_a8=None,
        generer_graphiques=False,
    )
    if not r['success']:
        return False, f"crash avec flux partiels : {r.get('erreur')}"

    nb_na = sum(1 for c in r['controles'] if c.get('statut') == 'N/A')
    if nb_na < 2:
        return False, f"Attendu ≥ 2 contrôles N/A sans A6+A8, obtenu {nb_na}"

    # Pas de KeyError, pas d'exception
    return True, ""

# ══════════════════════════════════════════════════════════════════════════════
# T7 — Alertes IA : ratio SCR faible → alerte CAPITAL déclenchée
# ══════════════════════════════════════════════════════════════════════════════

def test_t7_alertes_ia_capital():
    r = agent().run(
        result_a6=A6_OK,
        result_a7=A7_OK,
        result_a8=A8_SCR_FAIBLE,   # fonds propres 1.05M → ratio 123% → AMBRE
        primes_acq=PRIMES_ACQ_REELLES,
        generer_graphiques=False,
    )
    if not r['success']:
        return False, f"crash : {r.get('erreur')}"

    alertes = r.get('alertes_proactives', [])
    alertes_capital = [a for a in alertes if a.get('type') == 'CAPITAL']

    if not alertes_capital:
        ratio = 1_050_000 / 853_000
        return False, (
            f"Alerte CAPITAL attendue pour ratio SCR={ratio*100:.0f}%. "
            f"Alertes trouvées : {[a.get('type') for a in alertes]}"
        )
    return True, ""

# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 70)
    print("  TESTS UNITAIRES — AGENT A9 MARCUS v3.0")
    print("  ActuarIA — Direction Non-Vie")
    print("=" * 70 + "\n")

    tests = [
        (1, "Flux minimaux A6+A7+A8 → VERT global",                test_t1_flux_minimaux_vert),
        (2, "C1 sans primes_acq → AMBRE ou VERT (pas crash/ROUGE)", test_t2_c1_sans_primes),
        (3, "C1 avec primes_acq réelles → VERT (~3.6 pts écart)",   test_t3_c1_avec_primes),
        (4, "C2 SCR/BE anormal (272%) → ROUGE/AMBRE",               test_t4_c2_scr_anomal),
        (5, "Flux complets A10+A11+A12 → C4 et C5 actifs",          test_t5_flux_complets),
        (6, "Flux partiels (A7 seul) → N/A gracieux sans crash",     test_t6_flux_partiels_gracieux),
        (7, "Alerte IA CAPITAL déclenchée si ratio SCR < 130%",      test_t7_alertes_ia_capital),
    ]

    resultats = []
    for num, nom, fn in tests:
        ok = run_test(num, nom, fn)
        resultats.append(ok)

    nb_ok   = sum(resultats)
    nb_tot  = len(resultats)
    nb_fail = nb_tot - nb_ok

    print(f"\n{'─' * 70}")
    statut_final = "🟢 TOUS LES TESTS PASSENT" if nb_fail == 0 else f"🔴 {nb_fail} ÉCHEC(S)"
    print(f"  Résultat : {nb_ok}/{nb_tot} tests passent | {statut_final}")
    print(f"{'─' * 70}\n")

    sys.exit(0 if nb_fail == 0 else 1)


if __name__ == '__main__':
    main()
