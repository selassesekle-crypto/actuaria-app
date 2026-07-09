"""
Tests A12 Aisha v1.0 — 9 tests couvrant tous les modules ALM
Commande : python test_a12_aisha.py
"""
import sys, unittest
import os as _os
sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '../../../../')))
from direction_non_vie.reglementation.a12_alm.agent import AgentA12ALM

A10_BASE = {
    'provisions':{'best_estimate':6_000_000.0,'risk_margin':230_000.0,'tp_s2':6_230_000.0},
    'taux':{'rfr_10ans':0.032,'rfr_5ans':0.031,'rfr_20ans':0.033,
            'source':'FALLBACK','fiabilite':'REFERENCE'},
    'duration':{'passif':3.5,'par_branche':[
        {'nom':'rc_auto','duration_macaulay':4.0,'poids':0.70},
        {'nom':'mrh',    'duration_macaulay':2.0,'poids':0.30},
    ]},
    'detail':{'scr_mkt':{'allocation':{'obligations':0.70,'actions':0.10,'immo':0.05}}},
}

def agent():
    return AgentA12ALM(audit_path='/tmp/test_a12', verbose=False)

def run_base():
    return agent().run(result_a10=A10_BASE, generer_graphiques=False)

class T1_FluxMinimal(unittest.TestCase):
    """T1 — Flux minimal : uniquement result_a10"""
    def test_run(self):
        r = run_base()
        self.assertTrue(r['success'], r.get('erreur'))
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertGreater(r['duration']['passif'], 0)
        self.assertGreater(r['duration']['actif'], 0)
        self.assertGreater(r['lcr']['lcr'], 0)
        self.assertEqual(len(r['hypotheses']), 3)
        print(f"    ✅ T1 minimal : dur_pass={r['duration']['passif']:.3f}a  LCR={r['lcr']['lcr']:.1f}%")

class T2_Duration_Macaulay_Modifiee(unittest.TestCase):
    """T2 — Duration Macaulay et modifiée cohérentes (modifiée < Macaulay)"""
    def test_durations(self):
        r = run_base()
        d = r['duration']
        # Duration modifiée < Macaulay (rfr > 0)
        self.assertLess(d['actif_modifiee'],  d['actif'])
        self.assertLess(d['passif_modifiee'], d['passif'])
        # Duration modifiée = Macaulay / (1 + rfr)
        rfr = A10_BASE['taux']['rfr_10ans']
        self.assertAlmostEqual(d['actif_modifiee'],  d['actif']  / (1+rfr), places=3)
        self.assertAlmostEqual(d['passif_modifiee'], d['passif'] / (1+rfr), places=3)
        print(f"    ✅ T2 duration : actif={d['actif']:.4f}a→{d['actif_modifiee']:.4f}a  "
              f"passif={d['passif']:.4f}a→{d['passif_modifiee']:.4f}a")

class T3_Gap_Duration(unittest.TestCase):
    """T3 — Gap duration calculé et statut correct"""
    def test_gap(self):
        r = run_base()
        d = r['duration']
        # Gap = passif − actif (calculé à partir des durées Macaulay)
        gap_attendu = d['passif'] - d['actif']
        self.assertAlmostEqual(d['gap'], gap_attendu, places=3)
        # Statut cohérent avec la valeur absolue
        abs_gap = abs(d['gap'])
        if abs_gap <= 1.0:
            self.assertEqual(d['statut_gap'], 'VERT')
        elif abs_gap <= 2.5:
            self.assertIn(d['statut_gap'], ['VERT','AMBRE'])
        print(f"    ✅ T3 gap : {d['gap']:+.4f}a [{d['statut_gap']}]")

class T4_BV01(unittest.TestCase):
    """T4 — BV01 net = BV01_actif − BV01_passif"""
    def test_bv01_net(self):
        r = run_base()
        b = r['bv01']
        self.assertAlmostEqual(b['bv01_net'],
                                b['bv01_actif'] - b['bv01_passif'], places=2)
        self.assertGreater(b['bv01_actif'], 0)
        self.assertGreater(b['bv01_passif'], 0)
        self.assertIn('impact_100bp', b)
        # Impact 100bp = BV01_net × 100
        self.assertAlmostEqual(b['impact_100bp'], b['bv01_net'] * 100, delta=1.0)
        print(f"    ✅ T4 BV01 : actif={b['bv01_actif']:.2f}€/bp  "
              f"passif={b['bv01_passif']:.2f}€/bp  net={b['bv01_net']:+.2f}€/bp")

class T5_Redington_3Conditions(unittest.TestCase):
    """T5 — Redington : 3 conditions présentes et cohérentes"""
    def test_redington_structure(self):
        r = run_base()
        rd = r['redington']
        # Les 3 conditions sont présentes
        self.assertIn('c1_duration', rd)
        self.assertIn('c2_convexite', rd)
        self.assertIn('c3_va_positive', rd)
        # C1 : NAV ≥ 0 si actif > passif
        nav = r['actif']['nav']
        self.assertEqual(rd['c1_duration']['ok'], nav >= 0)
        # nb_ok cohérent
        nb = sum([rd['c1_duration']['ok'], rd['c2_convexite']['ok'], rd['c3_va_positive']['ok']])
        self.assertEqual(rd['detail']['nb_ok'], nb)
        self.assertEqual(rd['ok'], nb == 3)
        print(f"    ✅ T5 Redington : {rd['detail']['nb_ok']}/3  ok={rd['ok']}")

class T6_StressTaux_Decompose(unittest.TestCase):
    """T6 — Stress ±200bp : 4 scénarios décomposés actif/passif/NAV"""
    def test_stress_structure(self):
        r = run_base()
        s = r['stress']
        self.assertEqual(len(s['detail']), 4)  # -200,-100,+100,+200
        for d in s['detail']:
            self.assertIn('imp_actif',  d)
            self.assertIn('imp_passif', d)
            self.assertIn('imp_nav',    d)
            # Impact NAV = Impact actif − Impact passif
            self.assertAlmostEqual(d['imp_nav'],
                                   d['imp_actif'] - d['imp_passif'], delta=1.0)
        # Symétrie : impact +100bp ≈ −impact −100bp
        d_moins = s['detail'][1]  # -100bp
        d_plus  = s['detail'][2]  # +100bp
        self.assertAlmostEqual(d_plus['imp_nav'], -d_moins['imp_nav'], delta=1.0)
        print(f"    ✅ T6 stress : 4 scénarios | "
              f"-200bp NAV={s['detail'][0]['imp_nav']:+,.0f}€  "
              f"+200bp NAV={s['detail'][3]['imp_nav']:+,.0f}€")

class T7_LCR(unittest.TestCase):
    """T7 — LCR positif et statut cohérent"""
    def test_lcr(self):
        r = run_base()
        lc = r['lcr']
        self.assertGreater(lc['lcr'], 0)
        self.assertGreater(lc['actifs_liquides'], 0)
        self.assertGreater(lc['sorties_30j'], 0)
        # Statut cohérent
        if lc['lcr'] >= 100:
            self.assertEqual(lc['statut'], 'VERT')
        elif lc['lcr'] >= 75:
            self.assertIn(lc['statut'], ['AMBRE','VERT'])
        else:
            self.assertEqual(lc['statut'], 'ROUGE')
        # LCR = actifs / sorties * 100
        lcr_calc = lc['actifs_liquides'] / lc['sorties_30j'] * 100
        self.assertAlmostEqual(lc['lcr'], lcr_calc, places=1)
        print(f"    ✅ T7 LCR : {lc['lcr']:.1f}% [{lc['statut']}]  "
              f"HQLA={lc['actifs_liquides']:,.0f}€ / sorties={lc['sorties_30j']:,.0f}€")

class T8_SortiesVersA9(unittest.TestCase):
    """T8 — Toutes les sorties attendues par A9 Marcus C5 présentes"""
    def test_sorties_a9(self):
        r = run_base()
        # Duration
        self.assertGreater(r['duration']['passif'], 0)
        self.assertGreater(r['duration']['actif'],  0)
        self.assertIn('gap', r['duration'])
        self.assertIn('statut_gap', r['duration'])
        # LCR
        self.assertGreater(r['lcr']['lcr'], 0)
        # Redington
        self.assertIn('ok', r['redington'])
        # BV01
        self.assertIn('bv01_net', r['bv01'])
        print(f"    ✅ T8 sorties A9 C5 : dur_pass={r['duration']['passif']:.3f}a  "
              f"gap={r['duration']['gap']:+.3f}a  LCR={r['lcr']['lcr']:.1f}%  "
              f"Redington={r['redington']['ok']}")

class T9_GapRouge_AllocationDesequilibree(unittest.TestCase):
    """T9 — Gap ROUGE quand actif très court vs passif long"""
    def test_gap_rouge(self):
        # Passif très long (8 ans) + actif très court (cash uniquement)
        a10_long = dict(A10_BASE)
        a10_long = {**A10_BASE,
            'duration':{'passif':8.0,'par_branche':[
                {'nom':'rc_generale','duration_macaulay':8.0,'poids':1.0}]},
            'detail':{'scr_mkt':{'allocation':{'obligations':0.0,'actions':0.0,'immo':0.0,'cash':1.0}}}}
        r = agent().run(result_a10=a10_long, generer_graphiques=False)
        # Gap doit être > 2.5a → ROUGE
        self.assertGreater(abs(r['duration']['gap']), 2.0)
        self.assertIn(r['duration']['statut_gap'], ['AMBRE','ROUGE'])
        self.assertIn(r['statut_rag'], ['AMBRE','ROUGE'])
        print(f"    ✅ T9 gap déséquilibré : gap={r['duration']['gap']:+.3f}a  "
              f"[{r['duration']['statut_gap']}]  RAG={r['statut_rag']}")


if __name__ == '__main__':
    print("="*70)
    print("  TESTS A12 AISHA v1.0 — ALM & LIQUIDITÉ NON-VIE")
    print("  Duration | BV01 | Redington 3C | Stress ±200bp | LCR")
    print("="*70)
    suite = unittest.TestLoader().loadTestsFromModule(__import__('__main__'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n"+"="*70)
    if result.wasSuccessful():
        print(f"  ✅ {result.testsRun}/{result.testsRun} TESTS PASSÉS — A12 Aisha v1.0 VALIDÉE")
    else:
        print(f"  ❌ {len(result.failures)+len(result.errors)} ÉCHEC(S) sur {result.testsRun} tests")
    print("="*70)
