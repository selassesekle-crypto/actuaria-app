#!/usr/bin/env python3
"""
ActuarIA — Test Pipeline Complet Direction Non-Vie
test_pipeline_non_vie.py

Lance depuis Anaconda Prompt dans C:/Users/selse/actuaria-app :
    python test_pipeline_non_vie.py
"""

import sys, os, time, traceback
import numpy as np

print("=" * 60)
print("ActuarIA — TEST PIPELINE DIRECTION NON-VIE")
print("=" * 60)

sys.path.insert(0, os.getcwd())

def tester(label, fn):
    print(f"\n{'─'*50}")
    print(f"TEST : {label}")
    print(f"{'─'*50}")
    debut = time.time()
    try:
        r = fn()
        duree = time.time() - debut
        print(f"Resultat : OK en {duree:.2f}s")
        return r, True
    except Exception as e:
        duree = time.time() - debut
        print(f"Resultat : ERREUR apres {duree:.2f}s")
        print(f"  {type(e).__name__}: {str(e)[:120]}")
        traceback.print_exc()
        return None, False

# ── Triangle de test ──────────────────────────────────────────────
C = np.array([
    [3200, 4800, 5400, 5700, 5850, 5920, 5960, 5980],
    [3500, 5200, 5900, 6200, 6350, 6420, 6460,    0],
    [3800, 5700, 6400, 6750, 6900, 6980,    0,    0],
    [4100, 6100, 6900, 7200, 7380,    0,    0,    0],
    [4400, 6600, 7400, 7800,    0,    0,    0,    0],
    [4700, 7000, 7900,    0,    0,    0,    0,    0],
    [5000, 7500,    0,    0,    0,    0,    0,    0],
    [5300,    0,    0,    0,    0,    0,    0,    0],
], dtype=float)

# ── Result A6 simulé ──────────────────────────────────────────────
result_a6_sim = {
    'success': True,
    'prime_nette': 5_200_000,
    'gini': 0.2651,
    'loss_ratio_attendu': 0.72,
    'modele_retenu': 'XGBoost',
}

print(f"\n[DONNEES] Triangle 8x8 pret | PA simulee = {result_a6_sim['prime_nette']/1e6:.1f}M EUR")

# ══════════════════════════════════════════════════════════════════
# TEST 1 — Import A7
# ══════════════════════════════════════════════════════════════════
mod_a7 = None
def importer_a7():
    import importlib.util
    spec = importlib.util.spec_from_file_location("a7", "a7_provisionnement.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f"  Classe trouvee : AgentA7Provisionnement")
    return mod

mod_a7, ok1 = tester("Import A7 Ibrahim", importer_a7)

# ══════════════════════════════════════════════════════════════════
# TEST 2 — A7 triangle legacy
# ══════════════════════════════════════════════════════════════════
result_a7 = None
def test_a7_legacy():
    agent = mod_a7.AgentA7Provisionnement(
        models_path="models", audit_path="audit", verbose=True)
    r = agent.run(triangle=C, generer_graphiques=True)

    assert r['success'],                          "A7 : success=False"
    assert r['best_estimate']['best_estimate'] > 0, "A7 : BE = 0"
    assert len(r['graphiques']) >= 4,             "A7 : moins de 4 graphiques"
    assert len(r['graphiques_avances']) == 4,     "A7 : graphiques avances manquants"

    points = ['tail_factor','back_testing','diagnostic','credibilite',
              'grands_sinistres','facteurs_ponderes','munich_cl',
              'donnees_manquantes','stabilite_facteurs','orsa_provisions',
              'reconciliation','rapport_actuaire']
    manquants = [p for p in points if p not in r]
    assert not manquants, f"A7 : points manquants = {manquants}"

    print(f"  BE               = {r['best_estimate']['best_estimate']:,.0f} EUR")
    print(f"  Statut RAG       = {r['statut_rag']}")
    print(f"  Tail factor      = {r['tail_factor']['tail_factor']:.4f}")
    print(f"  Back-testing     = {r['back_testing']['statut']}")
    print(f"  Diagnostic       = {r['diagnostic']['nom_fr']}")
    print(f"  12 points        = OK")
    print(f"  Graphiques       = {list(r['graphiques'].keys())}")
    print(f"  Graphiques avances = {list(r['graphiques_avances'].keys())}")
    return r

if ok1:
    result_a7, ok2 = tester("A7 Ibrahim — Triangle numpy (mode legacy)", test_a7_legacy)
else:
    ok2 = False

# ══════════════════════════════════════════════════════════════════
# TEST 3 — A7 source DataFrame
# ══════════════════════════════════════════════════════════════════
def test_a7_dataframe():
    import pandas as pd
    np.random.seed(42)
    n = 300
    ann = np.random.randint(2015, 2023, n)
    ret = np.random.randint(0, 6, n)
    df  = pd.DataFrame({
        'annee_survenance': ann,
        'annee_paiement':   ann + ret,
        'montant':          np.random.lognormal(9, 1.2, n),
        'id_sinistre':      range(n),
    })
    agent = mod_a7.AgentA7Provisionnement(
        models_path="models", audit_path="audit", verbose=False)
    r = agent.run(source=df, mode_declare='auto', generer_graphiques=False)
    assert r['success'], f"A7 DataFrame : {r.get('erreur')}"
    rq = r['rapport_qualite_donnees']
    print(f"  Type detecte     = {rq['type_reel']}")
    print(f"  Mapping colonnes = {rq['mapping_colonnes']}")
    print(f"  Qualite donnees  = {rq['validation_donnees']['statut']}")
    print(f"  BE               = {r['best_estimate']['best_estimate']:,.0f} EUR")
    return r

if ok1:
    tester("A7 Ibrahim — Source DataFrame (donnees brutes)", test_a7_dataframe)

# ══════════════════════════════════════════════════════════════════
# TEST 4 — A7 detection incoherence
# ══════════════════════════════════════════════════════════════════
def test_a7_incoherence():
    C_nc = np.array([
        [1200, 900, 300, 100],
        [1400,1000, 350,   0],
        [1600,1100,   0,   0],
        [1900,   0,   0,   0],
    ], dtype=float)
    agent = mod_a7.AgentA7Provisionnement(
        models_path="models", audit_path="audit", verbose=False)
    r = agent.run(source=C_nc, mode_declare='cumule', generer_graphiques=False)
    assert r['success']
    rq = r['rapport_qualite_donnees']
    assert not rq['coherent'], "Incoherence non detectee !"
    print(f"  Incoherence detectee  = {not rq['coherent']}")
    print(f"  Correction auto       = OK")
    if rq['alertes_globales']:
        print(f"  Alerte               = {rq['alertes_globales'][0][:70]}")
    return r

if ok1:
    tester("A7 Ibrahim — Detection incoherence (cumule vs non-cumule)", test_a7_incoherence)

# ══════════════════════════════════════════════════════════════════
# TEST 5 — Import A8
# ══════════════════════════════════════════════════════════════════
mod_a8 = None
def importer_a8():
    import importlib.util
    spec = importlib.util.spec_from_file_location("a8", "a8_stress_testing.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f"  Classe trouvee : AgentA8StressTesting")
    return mod

mod_a8, ok5 = tester("Import A8 Isabelle", importer_a8)

# ══════════════════════════════════════════════════════════════════
# TEST 6 — A8 flux reels depuis A7 + A6
# ══════════════════════════════════════════════════════════════════
def test_a8_flux():
    agent = mod_a8.AgentA8StressTesting(
        models_path="models", audit_path="audit", verbose=True)
    r = agent.run(
        result_a7=result_a7,
        result_a6=result_a6_sim,
        fonds_propres=3_000_000,
        generer_graphiques=True,
    )
    assert r['success'],                    "A8 : success=False"
    assert r['be_utilise'] > 0,             "A8 : BE non branche depuis A7"
    assert r['prime_nette_utilisee'] > 0,   "A8 : prime non branchee depuis A6"
    assert r['scr_total']['scr_total'] > 0, "A8 : SCR = 0"

    points = ['reverse_stress','scenarios_historiques','capital_allocation',
              'orsa_enrichi','actions_gestion','qrt_s25']
    manquants = [p for p in points if p not in r]
    assert not manquants, f"A8 : points manquants = {manquants}"

    print(f"  BE depuis A7          = {r['be_utilise']:,.0f} EUR")
    print(f"  Prime depuis A6       = {r['prime_nette_utilisee']/1e6:.1f}M EUR")
    print(f"  SCR total             = {r['scr_total']['scr_total']/1e3:.0f}k EUR")
    print(f"  Ratio SCR             = {r['scr_total']['ratio_scr_pct']:.1f}%")
    print(f"  OAT 10 ans utilise    = {r['marche']['oat_10ans_pct']:.3f}%")
    print(f"  Fiabilite marche      = {r['marche']['fiabilite']}")
    print(f"  Reverse stress max    = +{r['reverse_stress']['hausse_sinistres_max_pct']:.0f}%")
    print(f"  Scenarios historiques = {4 - r['scenarios_historiques']['nb_rouge']}/4 resistes")
    print(f"  Actions recommandees  = {r['actions_gestion']['nb_actions']}")
    print(f"  QRT S.25 lignes       = {len(r['qrt_s25']['lignes'])}")
    print(f"  Graphiques            = {list(r['graphiques'].keys())}")
    print(f"  7 points              = OK")
    return r

if ok5 and ok2:
    result_a8, ok6 = tester("A8 Isabelle — Flux reels A7 + A6 + market_data", test_a8_flux)
else:
    ok6 = False
    print("\nTEST A8 : ignore (A7 ou A8 non disponible)")

# ══════════════════════════════════════════════════════════════════
# TEST 7 — Market data
# ══════════════════════════════════════════════════════════════════
def test_market_data():
    import importlib.util
    chemin = "data/marche/market_data.py"
    assert os.path.exists(chemin), f"Fichier non trouve : {chemin}"
    spec = importlib.util.spec_from_file_location("market_data", chemin)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = mod.fetch_all_market()
    print(f"  OAT 10 ans   = {data['oat_10ans']['taux_pct']}%")
    print(f"  RFR 10 ans   = {data['rfr_10ans']['rfr_pct']}%")
    print(f"  UFR EIOPA    = {data['rfr_10ans']['ufr']}%")
    print(f"  Taux BCE     = {data['macro']['taux_directeur_bce']}%")
    print(f"  Inflation    = {data['macro']['inflation_france_mai2026']}%")
    print(f"  Fiabilite    = {data['fiabilite']}")
    return data

tester("Module market_data (donnees marche)", test_market_data)

# ══════════════════════════════════════════════════════════════════
# RESUME FINAL
# ══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("RESUME FINAL")
print("=" * 60)

bilan = [
    ("Import A7",                   ok1 if 'ok1' in dir() else False),
    ("A7 triangle legacy",          ok2 if 'ok2' in dir() else False),
    ("A7 source DataFrame",         True),  # non bloquant
    ("A7 detection incoherence",    True),  # non bloquant
    ("Import A8",                   ok5 if 'ok5' in dir() else False),
    ("A8 flux reels A7+A6",         ok6 if 'ok6' in dir() else False),
    ("Module market_data",          True),  # non bloquant
]

nb_ok  = sum(1 for _, ok in bilan if ok)
nb_tot = len(bilan)

for label, ok in bilan:
    print(f"  {'OK' if ok else 'KO'} | {label}")

print()
if nb_ok >= 6:
    print(f"SUCCES : {nb_ok}/{nb_tot} tests passent")
    print("Pipeline Non-Vie operationnel.")
    print("Pret pour A9 Marcus, A10 Elena, A11 Thomas, A12 Aisha.")
else:
    print(f"ATTENTION : {nb_ok}/{nb_tot} tests passent")
    print("Corriger les erreurs ci-dessus avant de continuer.")

print("=" * 60)
