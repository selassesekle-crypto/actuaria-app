"""
Tests A11 Thomas v1.0 — 9 tests couvrant tous les modules IFRS 17 PAA
Commande : python test_a11_thomas.py
"""
import math, sys, unittest
from statistics import NormalDist
import os as _os
sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '../../../../')))
from core.courbe_rfr import actualiser, courbe_embarquee
from direction_non_vie.reglementation.a11_ifrs17.agent import AgentA11IFRS17

# ── Données de base ──────────────────────────────────────────────────────────
A7 = {
    'best_estimate':{'best_estimate':7_000_000.0,'sigma_mack':350_000.0,
        'cv_inter_methodes':8.0,'reserve_p75':7_420_000.0,'reserve_p90':7_700_000.0},
    'tail':{'tail_factor':1.035},'meta':{'nb_lignes':60000,'n_annees':8},
    'sous_branche':'rc_auto',
}
# ⚠️ CETTE FIXTURE SIMULAIT UN A10 QUI N'EXISTE PLUS (lot R4c). Elle portait
# 0,032 / 0,031 / 0,033 -- les taux d'A10 d'avant le chantier RFR. Elle restait
# VERTE en le simulant, parce que les assertions de ce fichier sont
# relationnelles : elle ne cassait pas, elle mentait. Elle prend desormais les
# taux du referentiel, comme A10 les produit reellement.
A10 = {
    'provisions':{'best_estimate':6_100_000.0,'risk_margin':220_000.0,'tp_s2':6_320_000.0},
    'taux':{'rfr_10ans':actualiser(courbe_embarquee(), 10),
            'rfr_5ans': actualiser(courbe_embarquee(), 5),
            'rfr_20ans':actualiser(courbe_embarquee(), 20),
            'source':'FALLBACK','fiabilite':'REFERENCE'},
    'duration':{'passif':3.5},
    'scr':{'total':3_500_000.0},
    'capital':{'ratio_scr':150.0},
}
A6 = {'modele_production':{'primes_acquises':12_000_000.0}}

# Données avec primes très élevées → pas de déficit
A10_OK = dict(A10)

def agent():
    return AgentA11IFRS17(audit_path='/tmp/test_a11', verbose=False)

def run_ok():
    """Run avec primes suffisantes pour éviter déficit."""
    return agent().run(
        result_a7=A7, result_a10=A10_OK, result_a6=A6,
        branches=[{'nom':'rc_auto','be':5_000_000,'primes':20_000_000},
                  {'nom':'mrh',    'be':2_000_000,'primes':8_000_000}],
        params_ifrs={'quantile_ra':0.75,'illiq_premium':0.006,'duree_contrat':1.0},
        generer_graphiques=False,
    )

def run_cv(cv):
    """Même run, avec une dispersion imposée : sigma_mack / BE = cv."""
    be = A7['best_estimate']['best_estimate']
    a7 = {**A7, 'best_estimate': {**A7['best_estimate'], 'sigma_mack': be * cv}}
    return agent().run(
        result_a7=a7, result_a10=A10_OK, result_a6=A6,
        branches=[{'nom':'rc_auto','be':5_000_000,'primes':20_000_000},
                  {'nom':'mrh',    'be':2_000_000,'primes':8_000_000}],
        params_ifrs={'quantile_ra':0.75,'illiq_premium':0.006,'duree_contrat':1.0},
        generer_graphiques=False,
    )

class T1_FluxMinimal(unittest.TestCase):
    """T1 — Flux minimal : result_a7 + result_a10 uniquement"""
    def test_run(self):
        r = agent().run(result_a7=A7, result_a10=A10, generer_graphiques=False)
        self.assertTrue(r['success'], r.get('erreur'))
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertGreater(r['provisions']['lic'], 0)
        self.assertGreater(r['provisions']['lrc'], 0)
        self.assertGreater(r['provisions']['risk_adjustment'], 0)
        self.assertGreater(r['provisions']['tp_ifrs17'], 0)
        self.assertEqual(len(r['hypotheses']), 3)
        print(f"    ✅ T1 minimal : LIC={r['provisions']['lic']:,.0f}€  RA={r['provisions']['risk_adjustment']:,.0f}€")

class T2_TauxIFRS17_SepaeDuRFR(unittest.TestCase):
    """T2 — Taux IFRS 17 bottom-up séparé et > RFR S2"""
    def test_taux_superieur_rfr(self):
        r = agent().run(result_a7=A7, result_a10=A10, generer_graphiques=False)
        t = r['taux']
        rfr_s2  = A10['taux']['rfr_10ans']
        illiq   = 0.006   # défaut
        self.assertAlmostEqual(t['rfr_s2'], rfr_s2, places=5)
        self.assertGreater(t['taux_ifrs17'], t['rfr_s2'])
        self.assertAlmostEqual(t['taux_ifrs17'], rfr_s2 + illiq, places=5)
        # Sixieme site du meme facteur cent : des points de base demandent
        # x10 000, pas x100. Les cinq autres etaient dans l'agent.
        print(f"    ✅ T2 taux : RFR_S2={t['rfr_s2']:.3%}  illiq={t['illiq_premium']*10000:.0f} bps  IFRS17={t['taux_ifrs17']:.3%}")

class T3_RiskAdjustment_VaR(unittest.TestCase):
    """T3 — RA par VaR log-normale au quantile P75.

    ⚠️ Les bornes 2 %-15 % du BE qui figuraient ici n'étaient pas une
    propriété du modèle : c'étaient les bornes de l'écrêtage, recopiées
    dans le test. Sur cette fixture (CV 5 %) l'écrêtage ne mord pas, donc
    elles passaient qu'il soit là ou non — elles ne vérifiaient rien.
    Remplacées par les deux propriétés que la norme exige réellement.
    """

    @staticmethod
    def _quantile_atteint(be, sigma, ra):
        """Le quantile auquel correspond RÉELLEMENT le RA publié.

        Calculé en bibliothèque standard, pas avec le scipy de l'agent :
        un témoin doit être indépendant de ce qu'il vérifie.
        """
        s = math.sqrt(math.log(1 + (sigma / be) ** 2))
        return NormalDist().cdf((math.log(1 + ra / be) + 0.5 * s ** 2) / s)

    def test_ra_au_quantile_declare(self):
        """IFRS 17 §119 : le niveau publié doit être le niveau UTILISÉ.

        Testé à CV 40 % en plus de la fixture : c'est là que l'écrêtage
        mordait, et il y livrait P71,1 en annonçant P75.
        L'identité est exacte — résidu mesuré 1e-15 — donc places=6
        laisse encore neuf ordres de grandeur de marge.
        """
        be = A7['best_estimate']['best_estimate']
        for cv in (0.05, 0.40):
            r  = run_cv(cv)
            ra = r['provisions']['risk_adjustment']
            self.assertGreater(ra, 0)
            self.assertEqual(r['provisions']['quantile_ra'], 0.75)
            atteint = self._quantile_atteint(be, be * cv, ra)
            self.assertAlmostEqual(
                atteint, 0.75, places=6,
                msg=f"CV {cv:.0%} : P{atteint*100:.1f} livré pour P75 déclaré")
            print(f"    ✅ T3 §119 CV {cv:.0%} : RA={ra:,.0f}€ "
                  f"({ra/be*100:.1f}% du BE) | P75 déclaré = P{atteint*100:.1f} atteint")

    def test_ra_croit_avec_la_dispersion(self):
        """IFRS 17 §B91(c) : montant plus élevé si la distribution est large.

        L'écrêtage à 15 % du BE rendait ces deux portefeuilles IDENTIQUES
        (1 050 000 € l'un et l'autre).
        """
        etroit = run_cv(0.30)['provisions']['risk_adjustment']
        large  = run_cv(0.60)['provisions']['risk_adjustment']
        self.assertGreater(large, etroit)
        print(f"    ✅ T3 §B91(c) : CV 30% → {etroit:,.0f}€ "
              f"< CV 60% → {large:,.0f}€")

class T4_CSM_Nulle(unittest.TestCase):
    """T4 — CSM = 0 en PAA (IFRS 17 §55)"""
    def test_csm_nulle(self):
        r = run_ok()
        # Dans les branches LRC
        for b in r['detail']['lrc']['par_branche']:
            self.assertEqual(b['csm'], 0.0,
                f"CSM non nulle pour {b['nom']} : {b['csm']}")
        print(f"    ✅ T4 CSM=0 pour toutes les branches (PAA §55 confirmé)")

class T5_LossComponent_Detection(unittest.TestCase):
    """T5 — Loss Component détecte bien les branches déficitaires"""
    def test_deficit_detecte(self):
        # Primes très faibles → déficit certain
        r = agent().run(
            result_a7=A7, result_a10=A10,
            result_a6={'modele_production':{'primes_acquises':500_000.0}},
            branches=[{'nom':'rc_auto','be':5_000_000,'primes':300_000}],
            generer_graphiques=False,
        )
        lc = r['loss_component']
        self.assertGreater(lc['lc_total'], 0)
        self.assertGreater(lc['nb_deficitaires'], 0)
        self.assertIn('rc_auto', lc['branches_deficit'])
        self.assertEqual(r['statut_rag'], 'ROUGE')
        print(f"    ✅ T5 déficit détecté : LC={lc['lc_total']:,.0f}€  [{lc['nb_deficitaires']} branche(s)]")

    def test_pas_de_deficit(self):
        r = run_ok()
        lc = r['loss_component']
        self.assertEqual(lc['lc_total'], 0.0)
        self.assertEqual(lc['nb_deficitaires'], 0)
        print(f"    ✅ T5b pas de déficit : LC=0€ avec primes suffisantes")

class T6_Reconciliation_3Colonnes(unittest.TestCase):
    """T6 — Réconciliation bilancielle 3 colonnes présente et cohérente"""
    def test_colonnes_presentes(self):
        r = run_ok()
        rec = r['reconciliation']
        self.assertIn('colonnes', rec)
        self.assertIn('LIC', rec['colonnes'])
        self.assertIn('LRC', rec['colonnes'])
        self.assertIn('RA',  rec['colonnes'])
        # Fermeture LIC cohérente avec provisions
        self.assertAlmostEqual(
            rec['colonnes']['LIC']['fermeture'],
            r['provisions']['lic'], delta=1.0
        )
        self.assertGreater(rec['tp_ifrs17_fermeture'], 0)
        print(f"    ✅ T6 réconciliation : LIC_ferm={rec['colonnes']['LIC']['fermeture']:,.0f}€  "
              f"LRC_ferm={rec['colonnes']['LRC']['fermeture']:,.0f}€  "
              f"RA_ferm={rec['colonnes']['RA']['fermeture']:,.0f}€")

class T7_ComparaisonS2_IFRS17(unittest.TestCase):
    """T7 — Comparaison S2 ↔ IFRS 17 cohérente → sorties A9 C4"""
    def test_ecarts_documentes(self):
        r = run_ok()
        e = r['ecart_s2_ifrs']
        # Toutes les clés attendues par A9 Marcus C4
        self.assertIn('be', e)
        self.assertIn('rm_ra', e)
        self.assertIn('ratio_ifrs_s2', e)
        self.assertIn('motif_ecart', e)
        self.assertIn('taux_s2', e)
        self.assertIn('taux_ifrs17', e)
        # Ratio dans plage raisonnable
        self.assertGreater(e['ratio_ifrs_s2'], 0.5)
        self.assertLess(e['ratio_ifrs_s2'], 2.0)
        # Taux IFRS 17 > taux S2
        self.assertGreater(e['taux_ifrs17'], e['taux_s2'])
        print(f"    ✅ T7 comparaison S2↔IFRS17 : ratio={e['ratio_ifrs_s2']:.4f}  "
              f"écart_BE={e['be']:+,.0f}€ ({e['be_pct']:+.1f}%)")

class T8_SortiesVersA9(unittest.TestCase):
    """T8 — Toutes les sorties attendues par A9 Marcus C4 présentes"""
    def test_sorties_a9(self):
        r = run_ok()
        pv = r['provisions']
        self.assertGreater(pv['lic'], 0)
        self.assertGreater(pv['lrc'], 0)
        self.assertGreater(pv['risk_adjustment'], 0)
        self.assertGreater(pv['tp_ifrs17'], 0)
        self.assertIn('quantile_ra', pv)
        e = r['ecart_s2_ifrs']
        self.assertIn('be', e)
        self.assertIn('rm_ra', e)
        self.assertIn('motif_ecart', e)
        print(f"    ✅ T8 sorties A9 C4 : LIC={pv['lic']:,.0f}€  LRC={pv['lrc']:,.0f}€  "
              f"RA={pv['risk_adjustment']:,.0f}€  ratio={e['ratio_ifrs_s2']:.4f}")

class T9_MultiBranches(unittest.TestCase):
    """T9 — Multi-branches : test suffisance branche par branche"""
    def test_branche_par_branche(self):
        r = agent().run(
            result_a7=A7, result_a10=A10,
            branches=[
                {'nom':'rc_auto','be':5_000_000,'primes':20_000_000},  # ok
                {'nom':'mrh',    'be':2_000_000,'primes':500_000},     # déficitaire
            ],
            generer_graphiques=False,
        )
        lc = r['loss_component']
        # mrh déficitaire, rc_auto ok
        brs = {b['nom']:b for b in lc['par_branche']}
        self.assertFalse(brs['rc_auto']['deficitaire'],
            "rc_auto ne doit pas être déficitaire")
        self.assertTrue(brs['mrh']['deficitaire'],
            "mrh doit être déficitaire")
        # Loss Component = uniquement mrh (pas de compensation)
        self.assertAlmostEqual(
            lc['lc_total'], brs['mrh']['loss_component'], delta=1.0
        )
        print(f"    ✅ T9 multi-branches : rc_auto=✅ bénéf.  mrh=⚠️ déficit  "
              f"LC={lc['lc_total']:,.0f}€ (pas de compensation)")


if __name__ == '__main__':
    print("="*70)
    print("  TESTS A11 THOMAS v1.0 — IFRS 17 PAA NON-VIE")
    print("  Taux bottom-up | RA VaR P75 | LC branche/branche | Réconcil.")
    print("="*70)
    suite = unittest.TestLoader().loadTestsFromModule(__import__('__main__'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n"+"="*70)
    if result.wasSuccessful():
        print(f"  ✅ {result.testsRun}/{result.testsRun} TESTS PASSÉS — A11 Thomas v1.0 VALIDÉ")
    else:
        print(f"  ❌ {len(result.failures)+len(result.errors)} ÉCHEC(S) sur {result.testsRun} tests")
    print("="*70)
