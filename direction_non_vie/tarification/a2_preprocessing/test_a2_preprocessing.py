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


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A2 PREPROCESSING v1.0")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
