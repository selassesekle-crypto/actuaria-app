"""
Tests A2 Preprocessing v1.0 — Feature Engineering Non-Vie
7 tests · données synthétiques freMTPL2
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))


def _make_r_a1(n=500):
    """Result A1 synthétique prêt pour A2."""
    np.random.seed(42)
    df = pd.DataFrame({
        'id_contrat':           range(n),
        'nb_sinistres':         np.random.poisson(0.08, n),
        'cout_total_sinistres': np.maximum(np.random.exponential(800, n), 0),
        'exposition':           np.random.uniform(0.1, 1.0, n),
        'age':                  np.random.randint(18, 75, n),
        'bonus_malus':          np.random.uniform(50, 350, n),
        'puissance_fiscale':    np.random.randint(4, 15, n),
        'zone_geographique':    np.random.choice(['A','B','C','D','E','F'], n),
        'carburant':            np.random.choice(['Regular','Diesel'], n),
        'age_vehicule':         np.random.randint(0, 20, n),
        'densite_population':   np.random.uniform(10, 5000, n),
    })
    return {
        'success': True, 'dataframe': df,
        'branche': 'auto', 'statut_rag': 'VERT',
        'score_qual': 95.0,
        'qualite': {'taux_completude': 99.0, 'taux_doublons': 0.0,
                    'nb_lignes': n, 'nb_colonnes': len(df.columns),
                    'score_global': 95.0, 'colonnes': df.columns.tolist(),
                    'expo_ok_pct': 100.0},
        'hash_md5': 'abc123', 'rapport': {'etapes': ['dataframe_direct'], 'alertes': []},
        'commentaire': 'OK', 'audit_id': 'A1_TEST', 'client_id': None, 'erreur': None,
    }


class TestA2Preprocessing(unittest.TestCase):
    """A2 Preprocessing — Pipeline feature engineering complet."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        cls.agent  = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        cls.r_a1   = _make_r_a1(500)
        cls.r      = cls.agent.run(result_a1=cls.r_a1)

    def test_a2(self):
        r = self.r

        # ST1 — Pipeline sans erreur
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT', 'AMBRE', 'ROUGE'])
        print(f"    ST1 Pipeline ✅ | statut={r['statut_rag']}")

        # ST2 — DataFrame enrichi retourné
        df = r['dataframe']
        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)
        print(f"    ST2 DataFrame ✅ | {len(df)} lignes × {len(df.columns)} colonnes")

        # ST3 — Variables cibles présentes
        self.assertIn('nb_sinistres', df.columns,
                      "Variable cible fréquence manquante")
        print(f"    ST3 Variables cibles ✅")

        # ST4 — Exposition dans [0, 1] (winsorisation appliquée)
        if 'exposition' in df.columns:
            expo = df['exposition'].dropna()
            self.assertTrue((expo >= 0).all() and (expo <= 1).all(),
                            "Exposition hors [0,1] après winsorisation")
            print(f"    ST4 Exposition ✅ | min={expo.min():.3f} max={expo.max():.3f}")
        else:
            print(f"    ST4 Exposition ✅ (colonne absente — OK en mode train)")

        # ST5 — Paramètres de transformation documentés
        params = r['parametres']
        self.assertIsInstance(params, dict)
        print(f"    ST5 Paramètres ✅ | {len(params)} clés documentées")

        # ST6 — Branche héritée de A1
        self.assertEqual(r['branche'], 'auto')
        print(f"    ST6 Branche ✅ | '{r['branche']}'")

        # ST7 — Commentaire actuaire généré
        self.assertIsInstance(r['commentaire'], str)
        self.assertGreater(len(r['commentaire']), 10)
        print(f"    ST7 Commentaire ✅ | {len(r['commentaire'])} chars")




class TestA2PrimePureCalculee(unittest.TestCase):
    """
    Verrou anti-régression — audit V7 anomalie BLOQUANTE B2 (volet A2).

    'prime_pure' était référencée comme cible attendue par A3/A4/A6, mais
    JAMAIS produite par A2 (sauf déjà présente dans les données brutes,
    rarissime pour une grandeur dérivée). Conséquence : en invocation par
    défaut d'A6 (col_cible='prime_pure'), le walk-forward se désactivait
    silencieusement — B2. Corrigé en calculant automatiquement prime_pure
    (cout_total_sinistres / exposition) quand absente.

    Ce test verrouille ce calcul contre toute régression future — sans
    lui, le contrat de données A2→A6 serait à nouveau rompu en silence.
    """

    def test_prime_pure_calculee_si_absente(self):
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        agent = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        r_a1 = _make_r_a1(500)  # fixture existante : cout_total_sinistres +
                                 # exposition présentes, PAS prime_pure
        self.assertNotIn('prime_pure', r_a1['dataframe'].columns,
                         "Pré-requis du test : prime_pure ne doit pas être "
                         "déjà présente dans la fixture brute")
        r = agent.run(result_a1=r_a1)

        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(
            'prime_pure', r['dataframe'].columns,
            "RÉGRESSION BLOQUANTE (audit V7 B2) — 'prime_pure' n'est plus "
            "calculée automatiquement. Le contrat de données A2→A6 est "
            "à nouveau rompu : le walk-forward d'A6 se désactivera "
            "silencieusement en invocation par défaut."
        )
        # Cohérence de la formule : prime_pure = coût / exposition
        df = r['dataframe']
        attendu = df['cout_total_sinistres'] / df['exposition'].clip(lower=1e-6)
        import numpy as np
        self.assertTrue(
            np.allclose(df['prime_pure'], attendu, rtol=1e-4),
            "prime_pure calculée ne correspond pas à cout_total_sinistres/exposition"
        )
        print(f"    B2-A2 prime_pure calculée automatiquement ✅ | "
              f"moyenne={df['prime_pure'].mean():.2f}")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A2 PREPROCESSING v1.0")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
