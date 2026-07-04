"""
Tests A8 Isabelle v2.0 — Stress Testing & ORSA Non-Vie
1 test · 5 sous-tests · données synthétiques
Commande : python test_a8_isabelle.py
"""
import sys, unittest
sys.path.insert(0, '/home/claude')

# Données A7 synthétiques (structure exacte de AgentA7)
A7_SYNTH = {
    'success': True,
    'best_estimate': {
        'best_estimate': 2_914_930.0,
        'sigma_mack':      45_000.0,
        'cv_inter_methodes': 0.6,
        'reserve_p75':   3_098_000.0,
        'reserve_p90':   3_200_000.0,
    },
    'bootstrap': {
        'p99_5':  3_640_000.0,   # minuscule — clé exacte A7
        'p90':    3_200_000.0,
        'p75':    3_098_000.0,
        'p50':    2_900_000.0,
    },
    'tail_factor': {
        'tail_factor': 1.037,    # double imbrication — clé exacte A7
        'methode_retenue': 'Clark',
    },
    'orsa_provisions': {'horizon_5ans': [3.0e6, 3.1e6, 3.2e6, 3.3e6, 3.4e6]},
    'sous_branche': 'auto',
    'chain_ladder': {'facteurs': [2.5, 1.8, 1.3, 1.1, 1.05]},
    'meta': {'nb_lignes': 70000, 'n_annees': 8},
}

# Données A6 synthétiques (structure exacte de AgentA6)
A6_SYNTH = {
    'success': True,
    'modele_production': {
        'modele':       'ML_ELASTICNET',
        'famille':      'ML',
        'gini_test':    0.2651,
        'gini_train':   0.2700,
        'score_global': 0.8373,
        'overfit_ratio':1.02,
        'prime_pure':   720.0,    # prime pure unitaire
    },
    'backtest': {'moy_train': 5_000_000.0},
    'loss_ratio_attendu': 0.72,
}


class TestA8StressTesting(unittest.TestCase):
    """A8 Isabelle — Stress Testing & ORSA. Teste : pipeline complet,
    SCR agrégé, reverse stress, ORSA 3 scénarios, QRT S.25.01."""

    @classmethod
    def setUpClass(cls):
        from a8_stress_testing import AgentA8StressTesting
        cls.agent = AgentA8StressTesting(
            models_path='/tmp', audit_path='/tmp', verbose=False
        )
        # Run avec les vraies données synthétiques A7+A6
        cls.r = cls.agent.run(
            result_a7=A7_SYNTH,
            result_a6=A6_SYNTH,
            fonds_propres=7_650_000.0,
            generer_graphiques=False,
        )

    def test_a8(self):
        r = self.r

        # ── ST1 : Pipeline complet A7+A6 branchés ────────────────────────────
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        # Vérifier que A7 est bien branché (BE = valeur A7, pas fallback)
        self.assertAlmostEqual(r['be_utilise'], 2_914_930.0, delta=1.0)
        # Vérifier que p99_5 vient bien du bootstrap A7 (pas be*1.25)
        self.assertAlmostEqual(r['p99_5_utilise'], 3_640_000.0, delta=1.0)
        # Vérifier que Gini vient de A6 modele_production (pas 0.25 défaut)
        self.assertAlmostEqual(r['gini_a6'], 0.2651, places=3)
        print(f"    ST1 Branchement A7+A6 ✅ | BE={r['be_utilise']:,.0f}€ "
              f"P99.5={r['p99_5_utilise']:,.0f}€ Gini={r['gini_a6']:.4f} "
              f"| {r['statut_rag']}")

        # ── ST2 : SCR agrégé cohérent ─────────────────────────────────────────
        scr = r['scr_total']
        self.assertGreater(scr['scr_total'], 0)
        self.assertGreater(scr['ratio_scr_pct'], 0)
        self.assertGreater(scr['mcr'], 0)
        # SCR total < somme des modules (effet diversification)
        somme_modules = sum(r['chocs_s2'][k] for k in
            ['scr_souscription','scr_catastrophe','scr_taux','scr_actions','scr_operationnel'])
        self.assertLess(scr['scr_total'], somme_modules)
        self.assertGreater(scr['diversification'], 0)
        print(f"    ST2 SCR ✅ | total={scr['scr_total']/1e3:.0f}k€ "
              f"ratio={scr['ratio_scr_pct']:.1f}% "
              f"diversif={scr['diversification_pct']:.1f}%")

        # ── ST3 : Reverse stress testing ──────────────────────────────────────
        rev = r['reverse_stress']
        self.assertIn('marge_euros', rev)
        self.assertIn('hausse_sinistres_max_pct', rev)
        self.assertIn('prob_insolvabilite_pct', rev)
        self.assertGreaterEqual(rev['hausse_sinistres_max_pct'], 0)
        self.assertGreaterEqual(rev['prob_insolvabilite_pct'], 0)
        self.assertLessEqual(rev['prob_insolvabilite_pct'], 100)
        print(f"    ST3 Reverse stress ✅ | marge={rev['marge_euros']/1e3:+.0f}k€ "
              f"hausse_max={rev['hausse_sinistres_max_pct']:.0f}% "
              f"P(insol)={rev['prob_insolvabilite_pct']:.4f}%")

        # ── ST4 : ORSA 3 scénarios sur 5 ans ─────────────────────────────────
        orsa = r['orsa_enrichi']
        self.assertIn('projection', orsa)
        proj = orsa['projection']
        self.assertIn('favorable', proj)
        self.assertIn('central',   proj)
        self.assertIn('adverse',   proj)
        # Chaque scénario a 5 valeurs (horizons 1-5)
        self.assertEqual(len(proj['favorable']), 5)
        self.assertEqual(len(proj['adverse']),   5)
        # Scénario favorable ≥ scénario adverse sur chaque horizon
        for f_val, a_val in zip(proj['favorable'], proj['adverse']):
            self.assertGreaterEqual(f_val, a_val)
        print(f"    ST4 ORSA ✅ | {orsa['statut']} | "
              f"adverse_min={orsa['ratio_adverse_min']:.1f}% "
              f"favorable_max={proj['favorable'][-1]:.1f}%")

        # ── ST5 : QRT S.25.01 complet ─────────────────────────────────────────
        qrt = r['qrt_s25']
        self.assertEqual(qrt['code'], 'S.25.01')
        codes = [l['code'] for l in qrt['lignes']]
        for code in ['R0010','R0020','R0070','R0100','R0200']:
            self.assertIn(code, codes, f"Ligne {code} manquante dans QRT")
        # SCR dans QRT = SCR calculé
        r0010 = next(l['valeur'] for l in qrt['lignes'] if l['code']=='R0010')
        self.assertAlmostEqual(r0010, scr['scr_total'], delta=1.0)
        print(f"    ST5 QRT S.25.01 ✅ | {len(qrt['lignes'])} lignes | "
              f"SCR={r0010/1e3:.0f}k€ ratio={scr['ratio_scr_pct']:.1f}%")


if __name__ == '__main__':
    print("="*70)
    print("  TESTS A8 ISABELLE v2.0 — STRESS TESTING & ORSA NON-VIE")
    print("  Branchement A7+A6 | SCR | Reverse stress | ORSA | QRT S.25.01")
    print("="*70)
    suite = unittest.TestLoader().loadTestsFromModule(__import__('__main__'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n"+"="*70)
    if result.wasSuccessful():
        print(f"  ✅ {result.testsRun}/{result.testsRun} TESTS PASSÉS — A8 Isabelle VALIDÉE")
    else:
        print(f"  ❌ {len(result.failures)+len(result.errors)} ÉCHEC(S) sur {result.testsRun} tests")
    print("="*70)
