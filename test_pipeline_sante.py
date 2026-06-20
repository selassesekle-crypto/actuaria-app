"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        ACTUARIA — TESTS PIPELINE SANTÉ S1→S2→S3                           ║
║        1 test par agent · sous-tests groupés · données synthétiques        ║
║        Commande : python test_pipeline_sante.py                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys, unittest
import numpy as np
sys.path.insert(0, '/home/claude')

# ── Données synthétiques communes ─────────────────────────────────────────────
PARAMS_BASE = {
    'nb_assures':      5000,
    'age_moyen':       43.0,
    'contrat':         'collectif',
    'garantie_niveau': 'confort',
    'chargement_pct':  0.18,
    'csp':             'employe',
}
FONDS_PROPRES = 3_000_000.0


# ══════════════════════════════════════════════════════════════════════════════
# TEST S1 — TARIFICATION SANTÉ
# ══════════════════════════════════════════════════════════════════════════════
class TestS1TarificationSante(unittest.TestCase):
    """S1 Léonie — Tarification Santé. Teste : pipeline paramètres manuels,
    ratio S/P, sinistralité par poste, ANI 2013, sorties vers S2."""

    @classmethod
    def setUpClass(cls):
        from leonie_s1_tarification_sante import AgentS1TarificationSante
        cls.agent = AgentS1TarificationSante(
            models_path='/tmp', audit_path='/tmp', verbose=False
        )
        cls.r = cls.agent.run(**PARAMS_BASE, generer_graphiques=False)

    def test_s1(self):
        r = self.r
        # ── ST1 : Pipeline ────────────────────────────────────────────────────
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertGreater(r['prime_commerciale'], 0)
        self.assertGreater(r['primes_acquises'],   0)
        print(f"    ST1 Pipeline ✅ | prime={r['prime_commerciale']:.2f}€ "
              f"PA={r['primes_acquises']:,.0f}€ | {r['statut_rag']}")

        # ── ST2 : Ratio S/P cohérent ──────────────────────────────────────────
        lr = r['ratio_sp_attendu']
        self.assertGreater(lr, 0.30)
        self.assertLess(lr, 1.10)
        # Prime commerciale > prime pure (chargement)
        self.assertGreater(r['prime_commerciale'], r['prime_pure'])
        print(f"    ST2 Ratio S/P ✅ | {lr*100:.1f}% | "
              f"pure={r['prime_pure']:.2f}€ comm={r['prime_commerciale']:.2f}€")

        # ── ST3 : Sinistralité par poste complète ─────────────────────────────
        postes_attendus = ['medecine','pharmacie','hospitalisation','dentaire','optique']
        for p in postes_attendus:
            self.assertIn(p, r['postes'])
            self.assertGreater(r['postes'][p]['sinistre_annuel'], 0)
        # Total postes ≈ prime pure
        total_postes = sum(v['sinistre_annuel'] for v in r['postes'].values())
        self.assertAlmostEqual(total_postes, r['prime_pure'], delta=r['prime_pure']*0.01)
        print(f"    ST3 Postes ✅ | 5 postes | total={total_postes:.2f}€ ≈ prime_pure")

        # ── ST4 : ANI 2013 présent ────────────────────────────────────────────
        self.assertIn('ani_conforme', r)
        self.assertIn('ani_detail',   r)
        self.assertIsInstance(r['ani_conforme'], bool)
        print(f"    ST4 ANI 2013 ✅ | conforme={r['ani_conforme']}")

        # ── ST5 : Sorties vers S2 complètes ──────────────────────────────────
        s2 = r['sorties_s2']
        for k in ['primes_acquises','sinistres_attendus','loss_ratio_attendu',
                  'sinistralite_par_poste','nb_assures']:
            self.assertIn(k, s2)
        self.assertAlmostEqual(s2['primes_acquises'], r['primes_acquises'], delta=1)
        self.assertGreater(s2['sinistres_attendus'], 0)
        print(f"    ST5 Sorties S2 ✅ | PA={s2['primes_acquises']:,.0f}€ "
              f"sin={s2['sinistres_attendus']:,.0f}€ LR={s2['loss_ratio_attendu']*100:.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# TEST S2 — PROVISIONNEMENT SANTÉ
# ══════════════════════════════════════════════════════════════════════════════
class TestS2ProvisionnemntSante(unittest.TestCase):
    """S2 Selma — Provisionnement Santé. Teste : branchement S1, PSAP par poste,
    IBNR cadences santé, PREC, sorties vers S3."""

    @classmethod
    def setUpClass(cls):
        from leonie_s1_tarification_sante import AgentS1TarificationSante
        from selma_s2_provisionnement_sante import AgentS2ProvisionnemntSante
        r1 = AgentS1TarificationSante(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(**PARAMS_BASE, generer_graphiques=False)
        cls.result_s1 = r1
        cls.agent = AgentS2ProvisionnemntSante(
            models_path='/tmp', audit_path='/tmp', verbose=False
        )
        cls.r = cls.agent.run(result_s1=r1, generer_graphiques=False)

    def test_s2(self):
        r = self.r

        # ── ST1 : Pipeline branchement S1 ─────────────────────────────────────
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertGreater(r['psap_total'], 0)
        print(f"    ST1 Pipeline S1→S2 ✅ | PSAP={r['psap_total']:,.0f}€ "
              f"LR={r['loss_ratio']*100:.1f}% | {r['statut_rag']}")

        # ── ST2 : Garde-fou S1 échoué ─────────────────────────────────────────
        r_fail = self.agent.run(
            {'success': False, 'erreur': 'test'}, generer_graphiques=False
        )
        self.assertFalse(r_fail['success'])
        self.assertIsNotNone(r_fail.get('erreur'))
        print(f"    ST2 Garde-fou ✅ | S1 échoué → S2 bloqué")

        # ── ST3 : PSAP décomposé (dossiers + IBNR) ───────────────────────────
        self.assertGreater(r['psap_dossiers'], 0)
        self.assertGreater(r['psap_ibnr'],     0)
        self.assertAlmostEqual(
            r['psap_total'],
            r['psap_dossiers'] + r['psap_ibnr'],
            delta=1
        )
        # IBNR santé ∈ [5%, 30%] des sinistres payés
        sp = self.result_s1['sorties_s2']['sinistres_attendus'] * 0.85
        ratio_ibnr = r['psap_ibnr'] / max(sp, 1)
        self.assertGreater(ratio_ibnr, 0.03)
        self.assertLess(ratio_ibnr,    0.35)
        print(f"    ST3 PSAP ✅ | dossiers={r['psap_dossiers']:,.0f}€ "
              f"IBNR={r['psap_ibnr']:,.0f}€ ratio={ratio_ibnr*100:.1f}%")

        # ── ST4 : PSAP par poste présent ──────────────────────────────────────
        self.assertIn('psap_par_poste', r)
        self.assertIn('ibnr_par_poste', r)
        for p in ['medecine','pharmacie','hospitalisation','dentaire','optique']:
            self.assertIn(p, r['psap_par_poste'])
            self.assertIn(p, r['ibnr_par_poste'])
        print(f"    ST4 Par poste ✅ | 5 postes PSAP + 5 postes IBNR")

        # ── ST5 : Sorties vers S3 complètes ──────────────────────────────────
        s3 = r['sorties_s3']
        for k in ['be_sante','risk_adjustment','tp_sante',
                  'psap_total','prec','provision_totale','loss_ratio']:
            self.assertIn(k, s3)
        self.assertGreater(s3['tp_sante'], s3['be_sante'])
        self.assertAlmostEqual(
            s3['tp_sante'],
            s3['be_sante'] + s3['risk_adjustment'],
            delta=1
        )
        print(f"    ST5 Sorties S3 ✅ | BE={s3['be_sante']:,.0f}€ "
              f"RA={s3['risk_adjustment']:,.0f}€ TP={s3['tp_sante']:,.0f}€")


# ══════════════════════════════════════════════════════════════════════════════
# TEST S3 — REPORTING SANTÉ QRT S.13
# ══════════════════════════════════════════════════════════════════════════════
class TestS3ReportingSante(unittest.TestCase):
    """S3 Binta — Reporting Santé. Teste : pipeline S1+S2→S3, SCR NSLT EIOPA,
    MCR plancher, ratio couverture, QRT S.13.01."""

    @classmethod
    def setUpClass(cls):
        from leonie_s1_tarification_sante import AgentS1TarificationSante
        from selma_s2_provisionnement_sante import AgentS2ProvisionnemntSante
        from binta_s3_reporting_sante import AgentS3ReportingSante
        r1 = AgentS1TarificationSante(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(**PARAMS_BASE, generer_graphiques=False)
        r2 = AgentS2ProvisionnemntSante(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(result_s1=r1, generer_graphiques=False)
        cls.result_s1 = r1
        cls.result_s2 = r2
        cls.agent = AgentS3ReportingSante(
            models_path='/tmp', audit_path='/tmp', verbose=False
        )
        cls.r = cls.agent.run(
            result_s1=r1, result_s2=r2,
            fonds_propres=FONDS_PROPRES,
            generer_graphiques=False
        )

    def test_s3(self):
        r = self.r

        # ── ST1 : Pipeline S1+S2→S3 ───────────────────────────────────────────
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertGreater(r['scr_sante'], 0)
        self.assertGreater(r['mcr_sante'], 0)
        print(f"    ST1 Pipeline S1+S2→S3 ✅ | SCR={r['scr_sante']:,.0f}€ "
              f"MCR={r['mcr_sante']:,.0f}€ | {r['statut_rag']}")

        # ── ST2 : TP Santé cohérent avec S2 ───────────────────────────────────
        be = r['be_sante']
        ra = r['risk_adjustment']
        tp = r['tp_sante']
        self.assertAlmostEqual(tp, be + ra, delta=1)
        self.assertAlmostEqual(ra, be * 0.05, delta=1)
        self.assertAlmostEqual(be, self.result_s2['psap_total'], delta=1)
        print(f"    ST2 TP Santé ✅ | BE={be:,.0f}€ + RA={ra:,.0f}€ = TP={tp:,.0f}€")

        # ── ST3 : SCR NSLT décomposé ──────────────────────────────────────────
        self.assertGreater(r['scr_prem'], 0)
        self.assertGreater(r['scr_res'],  0)
        self.assertGreater(r['scr_cat'],  0)
        # SCR total > chaque composante
        self.assertGreater(r['scr_sante'], r['scr_prem'])
        self.assertGreater(r['scr_sante'], r['scr_res'])
        print(f"    ST3 SCR NSLT ✅ | prem={r['scr_prem']:,.0f}€ "
              f"res={r['scr_res']:,.0f}€ cat={r['scr_cat']:,.0f}€")

        # ── ST4 : MCR plancher absolu ─────────────────────────────────────────
        MCR_PLANCHER = 2_500_000.0
        self.assertGreaterEqual(r['mcr_sante'], MCR_PLANCHER)
        # Ratio MCR cohérent
        ratio_mcr = FONDS_PROPRES / r['mcr_sante'] * 100
        self.assertAlmostEqual(r['ratio_mcr_pct'], ratio_mcr, delta=0.1)
        print(f"    ST4 MCR ✅ | MCR={r['mcr_sante']:,.0f}€ ≥ plancher {MCR_PLANCHER:,.0f}€ "
              f"ratio={r['ratio_mcr_pct']:.1f}%")

        # ── ST5 : QRT S.13.01 complet ─────────────────────────────────────────
        qrt = r['qrt_s13']
        self.assertEqual(qrt['code'], 'S.13.01')
        codes = [l['code'] for l in qrt['lignes']]
        for code in ['R0010','R0020','R0030','R0050','R0060','R0070','R0080']:
            self.assertIn(code, codes, f"Ligne {code} manquante dans QRT")
        # BE dans QRT = BE calculé
        r0010 = next((l.get('C0010') or l.get('C0040') or l.get('C0050') or 0)
                       for l in qrt['lignes'] if l['code']=='R0010')
        self.assertAlmostEqual(r0010, be, delta=1)
        print(f"    ST5 QRT S.13.01 ✅ | {len(qrt['lignes'])} lignes | "
              f"BE={r0010:,.0f}€ SCR={r['scr_sante']:,.0f}€ ratio={r['ratio_scr_pct']:.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  ACTUARIA — TESTS PIPELINE SANTÉ S1→S2→S3")
    print("  Tarification · Provisionnement · Reporting QRT S.13")
    print("="*70)
    suite = unittest.TestLoader().loadTestsFromModule(__import__('__main__'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n"+"="*70)
    if result.wasSuccessful():
        print(f"  ✅ {result.testsRun}/{result.testsRun} TESTS PASSÉS — Pipeline Santé VALIDÉ")
    else:
        n = len(result.failures) + len(result.errors)
        print(f"  ❌ {n} ÉCHEC(S) sur {result.testsRun} tests")
    print("="*70)
