"""
Tests A10 Elena v2.0 DÉFINITIVE — 9 tests couvrant tous les modules v2
Commande : python test_a10_elena.py
"""
import sys, unittest
sys.path.insert(0, '/home/claude')
from a10_solvabilite2 import AgentA10Solvabilite2, MCR_PLANCHER_ABS

A7_BASE = {
    'best_estimate':{'best_estimate':7_000_000.0,'sigma_mack':400_000.0,'cv_inter_methodes':8.0,'nb_methodes_convergentes':5},
    'tail':{'tail_factor':1.035},'meta':{'nb_lignes':60000,'n_annees':8}
}
A6_BASE = {'modele_production':{'modele':'XGB','gini_test':0.30,'prime_pure':700.0,'primes_acquises':9_500_000.0}}

def agent():
    return AgentA10Solvabilite2(audit_path='/tmp/test_a10', verbose=False)

class T1_FluxMinimal(unittest.TestCase):
    """T1 — Flux minimal : uniquement result_a7, tous les défauts"""
    def test_run(self):
        r = agent().run(result_a7=A7_BASE)
        self.assertTrue(r['success'], r.get('erreur'))
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertGreater(r['provisions']['best_estimate'], 0)
        self.assertGreater(r['scr']['total'], 0)
        self.assertGreater(r['mcr']['mcr'], 0)
        self.assertEqual(len(r['qrt_s25']), 20)
        self.assertEqual(len(r['hypotheses']), 3)
        print(f"    ✅ T1 minimal : SCR={r['scr']['total']:,.0f}€  MCR={r['mcr']['mcr']:,.0f}€")

class T2_FallbackTaux(unittest.TestCase):
    """T2 — Courbe de taux fallback : valeurs de référence 19/06/2026"""
    def test_courbe_defaut(self):
        r = agent().run(result_a7=A7_BASE)
        t = r['taux']
        self.assertAlmostEqual(t['rfr_5ans'],  0.031, places=4)
        self.assertAlmostEqual(t['rfr_10ans'], 0.032, places=4)
        self.assertAlmostEqual(t['rfr_20ans'], 0.033, places=4)
        self.assertEqual(t['fiabilite'], 'REFERENCE')
        self.assertLess(r['provisions']['best_estimate'], r['provisions']['be_brut'])
        print(f"    ✅ T2 taux : RFR={t['rfr_10ans']:.3%}  BE_S2={r['provisions']['best_estimate']:,.0f}€ < BE_brut={r['provisions']['be_brut']:,.0f}€")

class T3_ActualisationBE(unittest.TestCase):
    """T3 — Actualisation BE : impact négatif attendu, borne raisonnable"""
    def test_impact_taux(self):
        r = agent().run(result_a7=A7_BASE)
        imp     = r['provisions']['impact_taux']
        be_brut = r['provisions']['be_brut']
        self.assertLess(imp, 0)
        self.assertGreater(imp, -be_brut * 0.25)
        print(f"    ✅ T3 actualisation : impact={imp:,.0f}€  ({imp/be_brut:.2%} du BE brut)")

class T4_MCR_Bornes(unittest.TestCase):
    """T4 — MCR dans bornes [plancher, plafond], plancher ≥ 2.5M€"""
    def test_bornes_mcr(self):
        r = agent().run(result_a7=A7_BASE, fonds_propres=5_000_000.0)
        mcr = r['mcr']
        scr = r['scr']['total']
        plan = max(0.25 * scr, MCR_PLANCHER_ABS)
        plaf = 0.45 * scr
        # MCR final doit respecter ses propres bornes calculées
        self.assertGreaterEqual(mcr['mcr'], plan - 1.0,
            f"MCR={mcr['mcr']:,.0f} < plancher={plan:,.0f}")
        self.assertGreaterEqual(mcr['plancher'], MCR_PLANCHER_ABS - 1.0,
            "plancher < plancher absolu 2.5M€")
        # Si plancher > plafond (SCR faible), le MCR doit être ≥ plancher
        if plan > plaf:
            self.assertAlmostEqual(mcr['mcr'], plan, delta=1.0,
                msg="Plancher > plafond : MCR doit = plancher")
        else:
            self.assertLessEqual(mcr['mcr'], plaf + 1.0,
                f"MCR={mcr['mcr']:,.0f} > plafond={plaf:,.0f}")
        print(f"    ✅ T4 MCR : lin={mcr['mcr_lineaire']:,.0f}€  final={mcr['mcr']:,.0f}€  [{mcr['regime']}]  plancher={mcr['plancher']:,.0f}€")

class T5_Reassurance_ReduitSCR(unittest.TestCase):
    """T5 — Réassurance XL réduit le SCR souscription net d'au moins 10%"""
    def test_xl_reduit_scr(self):
        sans = agent().run(result_a7=A7_BASE)
        avec = agent().run(result_a7=A7_BASE, reassurance={
            'type':'xl','priorite':300_000,'portee':2_000_000,
            'taux_cession':0.70,'rating_reassureur':'A'
        })
        scr_sans = sans['scr']['souscription_net']
        scr_avec = avec['scr']['souscription_net']
        self.assertLess(scr_avec, scr_sans)
        reduction = (scr_sans - scr_avec) / scr_sans
        self.assertGreater(reduction, 0.10)
        print(f"    ✅ T5 réassurance XL : {scr_sans:,.0f}€ → {scr_avec:,.0f}€  (-{reduction:.1%})")

class T6_Ratio_RAG(unittest.TestCase):
    """T6 — Ratio VERT (FPP élevés) / ROUGE (FPP insuffisants)"""
    def test_vert(self):
        r = agent().run(result_a7=A7_BASE, fonds_propres=15_000_000.0)
        self.assertIn(r['capital']['statut_ratio'], ['VERT','AMBRE'])
        print(f"    ✅ T6a VERT : FPP=15M€ → ratio={r['capital']['ratio_scr']:.1f}%  [{r['capital']['statut_ratio']}]")
    def test_rouge(self):
        r = agent().run(result_a7=A7_BASE, fonds_propres=100.0)
        self.assertEqual(r['capital']['statut_ratio'], 'ROUGE')
        print(f"    ✅ T6b ROUGE : FPP=100€ → ratio={r['capital']['ratio_scr']:.1f}%  [{r['capital']['statut_ratio']}]")

class T7_SortiesVersA9(unittest.TestCase):
    """T7 — Toutes les clés attendues par A9 Marcus sont présentes"""
    def test_sorties_a9(self):
        r = agent().run(result_a7=A7_BASE, fonds_propres=5_000_000.0)
        # → C4
        self.assertGreater(r['provisions']['best_estimate'], 0)
        self.assertGreater(r['provisions']['risk_margin'],   0)
        # → C5
        self.assertGreater(r['duration']['passif'], 0)
        # → C2
        self.assertGreater(r['capital']['scr_total'], 0)
        self.assertGreater(r['capital']['mcr'],       0)
        self.assertGreater(r['capital']['fonds_propres'], 0)
        print(f"    ✅ T7 sorties A9 : BE={r['provisions']['best_estimate']:,.0f}€  RM={r['provisions']['risk_margin']:,.0f}€  "
              f"dur={r['duration']['passif']:.2f}a  SCR={r['capital']['scr_total']:,.0f}€  MCR={r['capital']['mcr']:,.0f}€")

class T8_TiersFPP(unittest.TestCase):
    """T8 — Fonds propres par tier + éligibilité MCR (Tier 3 exclu)"""
    def test_tiers_eligibilite(self):
        r = agent().run(result_a7=A7_BASE, fonds_propres=5_000_000.0,
            tiers_fpp={'tier1':4_000_000,'tier2':800_000,'tier3':200_000})
        c = r['capital']
        self.assertAlmostEqual(c['tier1'], 4_000_000, delta=1)
        self.assertAlmostEqual(c['tier2'],   800_000, delta=1)
        self.assertAlmostEqual(c['tier3'],   200_000, delta=1)
        # FPP MCR = T1 + min(T2, 25%×T1) = 4M + min(800k, 1M) = 4.8M
        self.assertAlmostEqual(c['fpp_eligible_mcr'], 4_800_000, delta=100)
        # Tier 3 non éligible MCR → fpp_mcr < fpp_scr
        self.assertLess(c['fpp_eligible_mcr'], c['fpp_eligible_scr'])
        print(f"    ✅ T8 tiers FPP : T1={c['tier1']:,.0f}€  T2={c['tier2']:,.0f}€  T3={c['tier3']:,.0f}€  "
              f"élig.MCR={c['fpp_eligible_mcr']:,.0f}€  élig.SCR={c['fpp_eligible_scr']:,.0f}€")

class T9_MultiBranchesSCR(unittest.TestCase):
    """T9 — Multi-branches : effet de diversification inter-LoB EIOPA"""
    def test_diversification(self):
        def mk_a7(be, nb):
            return {'best_estimate':{'best_estimate':float(be),'sigma_mack':be*0.06,
                'cv_inter_methodes':8,'nb_methodes_convergentes':5},
                'tail':{'tail_factor':1.03},'meta':{'nb_lignes':nb,'n_annees':8}}
        r1     = agent().run(result_a7=mk_a7(5_000_000,50000),
                             result_a6={'modele_production':{'primes_acquises':7_000_000.0}},
                             sous_branche='rc_auto')
        r2     = agent().run(result_a7=mk_a7(2_000_000,30000),
                             result_a6={'modele_production':{'primes_acquises':3_000_000.0}},
                             sous_branche='mrh')
        r_multi= agent().run(result_a7=A7_BASE, result_a6=A6_BASE,
                     branches=[{'nom':'rc_auto','be':5_000_000,'primes':7_000_000},
                                {'nom':'mrh',    'be':2_000_000,'primes':3_000_000}])
        scr1=r1['scr']['souscription']; scr2=r2['scr']['souscription']; scrm=r_multi['scr']['souscription']
        # Diversification : multi < somme des individuels
        self.assertLessEqual(scrm, scr1 + scr2 + 1.0)
        print(f"    ✅ T9 multi-branches : rc={scr1:,.0f}€  mrh={scr2:,.0f}€  multi={scrm:,.0f}€  "
              f"(gain diversif.={(scr1+scr2-scrm)/(scr1+scr2):.1%})")

if __name__ == '__main__':
    print("="*70)
    print("  TESTS A10 ELENA v2.0 DÉFINITIVE")
    print("  MCR | Courbe 3 pts | 3 modes SCR | Multi-branches | Réassurance | Tiers FPP")
    print("="*70)
    suite = unittest.TestLoader().loadTestsFromModule(__import__('__main__'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n"+"="*70)
    if result.wasSuccessful():
        print(f"  ✅ {result.testsRun}/{result.testsRun} TESTS PASSÉS — A10 Elena v2.0 VALIDÉE")
    else:
        print(f"  ❌ {len(result.failures)+len(result.errors)} ÉCHEC(S) sur {result.testsRun} tests")
    print("="*70)
