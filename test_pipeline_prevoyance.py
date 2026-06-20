"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ACTUARIA — TESTS PIPELINE PRÉVOYANCE P1→P2→P3→P4→NAOMIE              ║
║     1 test par agent · sous-tests groupés · données synthétiques           ║
║     Commande : python test_pipeline_prevoyance.py                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys, unittest
import numpy as np
sys.path.insert(0, '/home/claude')

# ── Paramètres communs ────────────────────────────────────────────────────────
PARAMS_P1 = dict(
    age=40, salaire_brut=45_000, categorie='employe',
    franchise_jours=90, taux_rente_ipp=0.60,
    duree_contrat=20, chargement_pct=0.20,
)
FONDS_PROPRES = 5_000_000.0

# ── Result S3 synthétique pour Naomie ────────────────────────────────────────
R_S3_SYNTH = {
    'success': True, 'be_sante': 613_020.0, 'scr_sante': 540_665.0,
    'fonds_propres': 3_000_000.0,
    'qrt_s13': {'lignes': [
        {'code':'R0100','libelle':'Primes acquises','C0010': 2_421_438.0},
    ]},
}


# ══════════════════════════════════════════════════════════════════════════════
# TEST P1 — TARIFICATION PRÉVOYANCE
# ══════════════════════════════════════════════════════════════════════════════
class TestP1TarificationPrevoyance(unittest.TestCase):
    """P1 Axel — Tarification ITT/IP/Décès. Teste : pipeline, taux cotisation,
    décomposition primes pures, sorties P2, fallback sans A2."""

    @classmethod
    def setUpClass(cls):
        from axel_p1_tarification_prevoyance import AgentP1TarificationPrevoyance
        cls.agent = AgentP1TarificationPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        )
        cls.r = cls.agent.run(**PARAMS_P1, generer_graphiques=False)

    def test_p1(self):
        r = self.r

        # ── ST1 : Pipeline ────────────────────────────────────────────────────
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertGreater(r['prime_commerciale'], r['primes_pures']['total'])
        self.assertGreater(r['primes_pures']['total'], 0)
        print(f"    ST1 Pipeline ✅ | prime_pure={r['primes_pures']['total']:.2f}€ "
              f"comm={r['prime_commerciale']:.2f}€ | {r['statut_rag']}")

        # ── ST2 : Taux cotisation cohérent ────────────────────────────────────
        tc = r['taux_cotisation_pct']
        self.assertGreater(tc, 0.5)
        self.assertLess(tc, 10.0)
        # Prime commerciale = taux × salaire
        tc_calc = r['prime_commerciale'] / PARAMS_P1['salaire_brut'] * 100
        prime_pure = r['primes_pures']['total']
        self.assertAlmostEqual(tc, tc_calc, places=2)
        print(f"    ST2 Taux cot. ✅ | {tc:.2f}% du salaire brut")

        # ── ST3 : Décomposition ITT + IP + Décès cohérente ───────────────────
        pp = r['primes_pures']
        self.assertGreater(pp['itt'],   0)
        self.assertGreater(pp['ip'],    0)
        self.assertGreater(pp['deces'], 0)
        self.assertAlmostEqual(pp['total'], pp['itt']+pp['ip']+pp['deces'], delta=0.01)
        self.assertAlmostEqual(pp['total'], r['primes_pures']['total'], delta=0.01)
        print(f"    ST3 Décomposition ✅ | ITT={pp['itt']:.2f}€ "
              f"IP={pp['ip']:.2f}€ Décès={pp['deces']:.2f}€")

        # ── ST4 : Sorties P2 complètes ────────────────────────────────────────
        s2 = r['sorties_p2']
        for k in ['age','categorie','taux_itt','taux_ip','qx',
                  'franchise_jours','salaire_brut','nb_assures']:
            self.assertIn(k, s2)
        self.assertAlmostEqual(s2['age'], PARAMS_P1['age'], delta=0.1)
        self.assertGreater(s2['taux_itt'], 0)
        self.assertGreater(s2['taux_ip'],  0)
        print(f"    ST4 Sorties P2 ✅ | âge={s2['age']} "
              f"taux_ITT={s2['taux_itt']*100:.1f}% taux_IP={s2['taux_ip']*100:.3f}%")

        # ── ST5 : Fallback sans A2 (result_a2=None) ───────────────────────────
        r_no_a2 = self.agent.run(
            result_a2=None, **PARAMS_P1, generer_graphiques=False
        )
        self.assertTrue(r_no_a2['success'])
        self.assertEqual(r_no_a2['source_donnees'], 'parametres_manuels')
        print(f"    ST5 Fallback ✅ | source={r_no_a2['source_donnees']}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST P2 — TABLES MORBIDITÉ (MARKOV)
# ══════════════════════════════════════════════════════════════════════════════
class TestP2TablesMorbidite(unittest.TestCase):
    """P2 Rayan — Chaîne de Markov 4 états. Teste : matrice valide,
    cohérence BCAC, maintien décroissant, projection cohérente, sorties P3."""

    @classmethod
    def setUpClass(cls):
        from axel_p1_tarification_prevoyance import AgentP1TarificationPrevoyance
        from rayan_p2_tables_morbidite import AgentP2TablesMorbidite
        r1 = AgentP1TarificationPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(**PARAMS_P1, generer_graphiques=False)
        cls.result_p1 = r1
        cls.agent = AgentP2TablesMorbidite(
            models_path='/tmp', audit_path='/tmp', verbose=False
        )
        cls.r = cls.agent.run(result_p1=r1, horizon_ans=10, generer_graphiques=False)

    def test_p2(self):
        r = self.r

        # ── ST1 : Matrice Markov 4×4 valide ──────────────────────────────────
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        P = np.array(r['matrice_P'])
        self.assertEqual(P.shape, (4, 4))
        # Chaque ligne somme à 1
        for i in range(4):
            self.assertAlmostEqual(P[i].sum(), 1.0, places=4,
                msg=f"Ligne {i} ne somme pas à 1 : {P[i].sum()}")
        # Toutes les valeurs ≥ 0
        self.assertTrue((P >= 0).all())
        print(f"    ST1 Matrice Markov ✅ | 4×4 | lignes somment à 1 | {r['statut_rag']}")

        # ── ST2 : P(IP) < P(ITT) — cohérence BCAC ────────────────────────────
        t = r['transitions']
        self.assertLess(t['q_IP_annuel'], t['q_AI'])
        self.assertGreater(t['q_AI'], 0)
        self.assertGreater(t['q_IP_annuel'], 0)
        print(f"    ST2 Cohérence BCAC ✅ | q_ITT={t['q_AI']*100:.2f}% "
              f"> q_IP={t['q_IP_annuel']*100:.3f}%")

        # ── ST3 : Maintien décroissant (6m > 12m > 24m) ──────────────────────
        m = r['prob_maintien']
        self.assertGreater(m['mois_6'],  m['mois_12'])
        self.assertGreater(m['mois_12'], m['mois_24'])
        self.assertGreaterEqual(m['mois_6'],  0)
        self.assertLessEqual(m['mois_6'],    1)
        print(f"    ST3 Maintien ✅ | 6m={m['mois_6']*100:.1f}% "
              f"> 12m={m['mois_12']*100:.1f}% > 24m={m['mois_24']*100:.1f}%")

        # ── ST4 : Projection — distribution somme à 1 ────────────────────────
        proj = r['projection']
        ef = proj['etat_final']
        total = sum(ef.values())
        self.assertAlmostEqual(total, 1.0, places=3)
        # Actif dominant à 10 ans
        self.assertGreater(ef['Actif'], ef['ITT'])
        self.assertGreater(ef['Actif'], ef['IP'])
        print(f"    ST4 Projection 10 ans ✅ | "
              f"Actif={ef['Actif']*100:.1f}% ITT={ef['ITT']*100:.2f}% "
              f"IP={ef['IP']*100:.2f}% Décès={ef['Décès']*100:.2f}%")

        # ── ST5 : Sorties P3 complètes ────────────────────────────────────────
        s3 = r['sorties_p3']
        for k in ['age','categorie','taux_ip','taux_itt',
                  'prob_maintien_6m','prob_maintien_12m',
                  'esperance_duree_ip','salaire_brut']:
            self.assertIn(k, s3)
        self.assertGreater(s3['taux_ip'],  0)
        self.assertGreater(s3['taux_itt'], 0)
        print(f"    ST5 Sorties P3 ✅ | taux_IP={s3['taux_ip']*100:.3f}% "
              f"durée_IP={s3['esperance_duree_ip']:.1f} ans")


# ══════════════════════════════════════════════════════════════════════════════
# TEST P3 — PROVISIONNEMENT PRÉVOYANCE
# ══════════════════════════════════════════════════════════════════════════════
class TestP3ProvisionnemntPrevoyance(unittest.TestCase):
    """P3 Élodie — Provisions ITT/IP. Teste : pipeline P1+P2→P3,
    garde-fous, IBNR cadence prévoyance, triangle, sorties P4."""

    @classmethod
    def setUpClass(cls):
        from axel_p1_tarification_prevoyance import AgentP1TarificationPrevoyance
        from rayan_p2_tables_morbidite import AgentP2TablesMorbidite
        from elodie_p3_provisionnement_prevoyance import AgentP3ProvisionnemntPrevoyance
        r1 = AgentP1TarificationPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(**PARAMS_P1, generer_graphiques=False)
        r2 = AgentP2TablesMorbidite(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(result_p1=r1, horizon_ans=10, generer_graphiques=False)
        cls.result_p1 = r1
        cls.result_p2 = r2
        cls.agent = AgentP3ProvisionnemntPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        )
        cls.r = cls.agent.run(result_p1=r1, result_p2=r2, generer_graphiques=False)

    def test_p3(self):
        r = self.r

        # ── ST1 : Pipeline P1+P2→P3 ───────────────────────────────────────────
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertGreater(r['be_prevoyance'], 0)
        self.assertGreater(r['psap_total'],    0)
        print(f"    ST1 Pipeline P1+P2→P3 ✅ | BE={r['be_prevoyance']:,.0f}€ "
              f"PSAP={r['psap_total']:,.0f}€ | {r['statut_rag']}")

        # ── ST2 : Garde-fous P1/P2 absents ───────────────────────────────────
        r_fail = self.agent.run(
            result_p1={'success':False}, result_p2={'success':False},
            generer_graphiques=False
        )
        self.assertFalse(r_fail['success'])
        print(f"    ST2 Garde-fou ✅ | P1+P2 échoués → P3 bloqué")

        # ── ST3 : IBNR ITT ∈ [20%, 50%] des sinistres ────────────────────────
        from elodie_p3_provisionnement_prevoyance import IBNR_ITT_PCT
        self.assertGreaterEqual(IBNR_ITT_PCT, 0.20)
        self.assertLessEqual(IBNR_ITT_PCT,    0.50)
        self.assertGreater(r['ibnr_itt'], 0)
        self.assertGreater(r['ibnr_ip'],  0)
        print(f"    ST3 IBNR ✅ | ITT={r['ibnr_itt']:,.0f}€ ({IBNR_ITT_PCT*100:.0f}%) "
              f"IP={r['ibnr_ip']:,.0f}€")

        # ── ST4 : Triangle prévoyance cohérent ───────────────────────────────
        tri = r['triangle']
        self.assertIn('ITT', tri)
        self.assertIn('IP',  tri)
        # Développement croissant jusqu'à l'ultime
        self.assertLessEqual(tri['ITT']['mois_6'],  tri['ITT']['mois_12'])
        self.assertLessEqual(tri['ITT']['mois_12'], tri['ITT']['mois_36'])
        self.assertLessEqual(tri['ITT']['mois_36'], tri['ITT']['ultime'])
        self.assertLessEqual(tri['IP']['an_1'],     tri['IP']['an_5'])
        self.assertLessEqual(tri['IP']['an_5'],     tri['IP']['ultime'])
        print(f"    ST4 Triangle ✅ | ITT 36m={tri['ITT']['mois_36']:,.0f}€ "
              f"< ultime={tri['ITT']['ultime']:,.0f}€ | "
              f"IP 5a={tri['IP']['an_5']:,.0f}€ < ultime={tri['IP']['ultime']:,.0f}€")

        # ── ST5 : Sorties P4 complètes ────────────────────────────────────────
        s4 = r['sorties_p4']
        for k in ['be_prevoyance','risk_adjustment','tp_prevoyance',
                  'psap_total','pm_rentes_ip','prec','provision_totale',
                  'loss_ratio','primes_acquises']:
            self.assertIn(k, s4)
        self.assertAlmostEqual(
            s4['tp_prevoyance'],
            s4['be_prevoyance'] + s4['risk_adjustment'],
            delta=1
        )
        print(f"    ST5 Sorties P4 ✅ | BE={s4['be_prevoyance']:,.0f}€ "
              f"RA={s4['risk_adjustment']:,.0f}€ TP={s4['tp_prevoyance']:,.0f}€")


# ══════════════════════════════════════════════════════════════════════════════
# TEST P4 — REPORTING PRÉVOYANCE
# ══════════════════════════════════════════════════════════════════════════════
class TestP4ReportingPrevoyance(unittest.TestCase):
    """P4 Valentin — QRT S.14.01. Teste : pipeline complet, TP cohérent,
    diversification SCR, QRT 17 lignes, sorties Naomie."""

    @classmethod
    def setUpClass(cls):
        from axel_p1_tarification_prevoyance import AgentP1TarificationPrevoyance
        from rayan_p2_tables_morbidite import AgentP2TablesMorbidite
        from elodie_p3_provisionnement_prevoyance import AgentP3ProvisionnemntPrevoyance
        from valentin_p4_reporting_prevoyance import AgentP4ReportingPrevoyance
        r1 = AgentP1TarificationPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(**PARAMS_P1, generer_graphiques=False)
        r2 = AgentP2TablesMorbidite(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(result_p1=r1, horizon_ans=10, generer_graphiques=False)
        r3 = AgentP3ProvisionnemntPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(result_p1=r1, result_p2=r2, generer_graphiques=False)
        cls.result_p3 = r3
        cls.agent = AgentP4ReportingPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        )
        cls.r = cls.agent.run(
            result_p1=r1, result_p2=r2, result_p3=r3,
            fonds_propres=FONDS_PROPRES, generer_graphiques=False
        )

    def test_p4(self):
        r = self.r

        # ── ST1 : Pipeline P1+P2+P3→P4 ───────────────────────────────────────
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertGreater(r['scr_invalidite'], 0)
        self.assertGreater(r['mcr'], 0)
        print(f"    ST1 Pipeline ✅ | SCR={r['scr_invalidite']:,.0f}€ "
              f"MCR={r['mcr']:,.0f}€ | {r['statut_rag']}")

        # ── ST2 : TP = BE + RA (8%) ───────────────────────────────────────────
        be = r['be_prevoyance']
        ra = r['risk_adjustment']
        tp = r['tp_prevoyance']
        self.assertAlmostEqual(tp, be + ra, delta=1)
        self.assertAlmostEqual(ra, be * 0.08, delta=1)
        self.assertAlmostEqual(be, self.result_p3['be_prevoyance'], delta=1)
        print(f"    ST2 TP ✅ | BE={be:,.0f}€ + RA={ra:,.0f}€ = TP={tp:,.0f}€")

        # ── ST3 : SCR agrégé < somme des sous-modules (diversification) ───────
        somme = r['scr_morbidite'] + r['scr_cessation'] + r['scr_longevite']
        self.assertLess(r['scr_invalidite'], somme)
        self.assertGreater(r['scr_morbidite'], 0)
        self.assertGreater(r['scr_cessation'], 0)
        print(f"    ST3 Diversification ✅ | SCR_inv={r['scr_invalidite']:,.0f}€ "
              f"< somme={somme:,.0f}€ | morb={r['scr_morbidite']:,.0f}€")

        # ── ST4 : QRT S.14.01 complet ─────────────────────────────────────────
        qrt = r['qrt_s14']
        self.assertEqual(qrt['code'], 'S.14.01')
        codes = [l['code'] for l in qrt['lignes']]
        for code in ['R0010','R0020','R0030','R0050','R0070','R0080','R0090','R0100']:
            self.assertIn(code, codes, f"Ligne {code} manquante")
        self.assertEqual(len(qrt['lignes']), 17)
        # BE dans QRT = BE calculé
        r0010 = next(l['C0010'] for l in qrt['lignes'] if l['code']=='R0010')
        self.assertAlmostEqual(r0010, be, delta=1)
        print(f"    ST4 QRT S.14.01 ✅ | {len(qrt['lignes'])} lignes | "
              f"BE={r0010:,.0f}€")

        # ── ST5 : Sorties Naomie complètes ────────────────────────────────────
        sn = r['sorties_naomie']
        for k in ['be_prevoyance','tp_prevoyance','scr_invalidite',
                  'mcr','ratio_scr_pct','primes_acquises','fonds_propres']:
            self.assertIn(k, sn)
        self.assertAlmostEqual(sn['be_prevoyance'], be, delta=1)
        print(f"    ST5 Sorties Naomie ✅ | BE={sn['be_prevoyance']:,.0f}€ "
              f"SCR={sn['scr_invalidite']:,.0f}€ ratio={sn['ratio_scr_pct']:.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# TEST NAOMIE — STRESS TESTING SP
# ══════════════════════════════════════════════════════════════════════════════
class TestNaomieSpStressTesting(unittest.TestCase):
    """Naomie — Stress Testing SP. Teste : 5 chocs EIOPA, décomposition NAV,
    ORSA 3 scénarios, reverse stress, garde-fous."""

    @classmethod
    def setUpClass(cls):
        from axel_p1_tarification_prevoyance import AgentP1TarificationPrevoyance
        from rayan_p2_tables_morbidite import AgentP2TablesMorbidite
        from elodie_p3_provisionnement_prevoyance import AgentP3ProvisionnemntPrevoyance
        from valentin_p4_reporting_prevoyance import AgentP4ReportingPrevoyance
        from naomie_sp_stress_testing import AgentNaomieSpStressTesting
        r1 = AgentP1TarificationPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(**PARAMS_P1, generer_graphiques=False)
        r2 = AgentP2TablesMorbidite(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(result_p1=r1, horizon_ans=10, generer_graphiques=False)
        r3 = AgentP3ProvisionnemntPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(result_p1=r1, result_p2=r2, generer_graphiques=False)
        cls.result_p4 = AgentP4ReportingPrevoyance(
            models_path='/tmp', audit_path='/tmp', verbose=False
        ).run(result_p1=r1, result_p2=r2, result_p3=r3,
              fonds_propres=FONDS_PROPRES, generer_graphiques=False)
        cls.agent = AgentNaomieSpStressTesting(
            models_path='/tmp', audit_path='/tmp', verbose=False
        )
        cls.r = cls.agent.run(
            result_s3=R_S3_SYNTH, result_p4=cls.result_p4,
            fonds_propres=FONDS_PROPRES, generer_graphiques=False
        )

    def test_naomie(self):
        r = self.r

        # ── ST1 : Pipeline S3+P4→Naomie, 5 chocs présents ───────────────────
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertEqual(len(r['chocs']), 5)
        for c in r['chocs']:
            for k in ['id','nom','imp_sante','imp_prev','imp_nav','nav_stress']:
                self.assertIn(k, c)
        print(f"    ST1 Pipeline ✅ | 5 chocs | NAV_base={r['nav_base']:,.0f}€ | {r['statut_rag']}")

        # ── ST2 : Impact NAV = -(S+P) + PA ────────────────────────────────────
        for c in r['chocs']:
            imp_calc = -(c['imp_sante'] + c['imp_prev']) + c['imp_pa']
            self.assertAlmostEqual(c['imp_nav'], imp_calc, delta=1)
        print(f"    ST2 Décomposition ✅ | imp_NAV = -(santé+prévo) + PA vérifié")

        # ── ST3 : ORSA — favorable > central > adverse ────────────────────────
        proj = r['orsa']['projection']
        for t in range(5):
            self.assertGreaterEqual(proj['favorable'][t], proj['central'][t])
            self.assertGreaterEqual(proj['central'][t],   proj['adverse'][t])
        print(f"    ST3 ORSA ✅ | fav={proj['favorable'][-1]:.1f}% "
              f"> cent={proj['central'][-1]:.1f}% "
              f"> adv={proj['adverse'][-1]:.1f}% (an 5)")

        # ── ST4 : Reverse stress — marge > 0 si FPP > SCR ────────────────────
        rev = r['reverse_stress']
        self.assertIn('marge_euros', rev)
        self.assertIn('hausse_morbidite_max_pct', rev)
        self.assertIn('prob_ruine_pct', rev)
        # Si FPP > SCR → marge positive → hausse absorbable > 0
        if r['nav_base'] > 0:
            self.assertGreater(rev['hausse_morbidite_max_pct'], 0)
        self.assertGreaterEqual(rev['prob_ruine_pct'], 0)
        self.assertLessEqual(rev['prob_ruine_pct'], 100)
        print(f"    ST4 Reverse stress ✅ | marge={rev['marge_euros']:,.0f}€ "
              f"hausse_max={rev['hausse_morbidite_max_pct']:.1f}% "
              f"P(ruine)={rev['prob_ruine_pct']:.4f}%")

        # ── ST5 : Garde-fous S3 ou P4 absents ────────────────────────────────
        r_fail_s3 = self.agent.run(
            result_s3={'success':False}, result_p4=self.result_p4,
            generer_graphiques=False
        )
        self.assertFalse(r_fail_s3['success'])
        r_fail_p4 = self.agent.run(
            result_s3=R_S3_SYNTH, result_p4={'success':False},
            generer_graphiques=False
        )
        self.assertFalse(r_fail_p4['success'])
        print(f"    ST5 Garde-fous ✅ | S3 absent → bloqué | P4 absent → bloqué")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  ACTUARIA — TESTS PIPELINE PRÉVOYANCE P1→P2→P3→P4→NAOMIE")
    print("  Tarification · Markov · Provisionnement · QRT S.14 · Stress SP")
    print("="*70)
    suite = unittest.TestLoader().loadTestsFromModule(__import__('__main__'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n"+"="*70)
    if result.wasSuccessful():
        print(f"  ✅ {result.testsRun}/{result.testsRun} TESTS PASSÉS — Pipeline Prévoyance VALIDÉ")
    else:
        n = len(result.failures) + len(result.errors)
        print(f"  ❌ {n} ÉCHEC(S) sur {result.testsRun} tests")
    print("="*70)
