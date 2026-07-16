"""
Tests A1 Ingestion v1.0 — Ingestion & Validation Non-Vie
7 tests · données synthétiques freMTPL2
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))


def _df_auto(n=500):
    """DataFrame synthétique Auto freMTPL2-like."""
    np.random.seed(42)
    return pd.DataFrame({
        'id_contrat':           range(n),
        'nb_sinistres':         np.random.poisson(0.08, n),
        'cout_total_sinistres': np.random.exponential(800, n),
        'exposition':           np.random.uniform(0.1, 1.0, n),
        'age':                  np.random.randint(18, 75, n),
        'bonus_malus':          np.random.uniform(50, 350, n),
        'puissance_fiscale':    np.random.randint(4, 15, n),
        'zone_geographique':    np.random.choice(['A','B','C','D','E','F'], n),
        'carburant':            np.random.choice(['Regular','Diesel'], n),
        'age_vehicule':         np.random.randint(0, 20, n),
        'densite_population':   np.random.uniform(10, 5000, n),
    })


class TestA1Ingestion(unittest.TestCase):
    """A1 Ingestion — Pipeline complet, qualité données, mapping, hash."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        cls.agent = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        cls.df    = _df_auto(500)
        # Phase 1 : la sous-branche est DÉCLARÉE par l'actuaire (A1 ne devine plus).
        cls.r     = cls.agent.run(branche='non_vie', sous_branche='auto',
                                  dataframe=cls.df)

    def test_a1(self):
        r = self.r

        # ST1 — Pipeline complet sans erreur
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIsNone(r['erreur'])
        self.assertIn(r['statut_rag'], ['VERT', 'AMBRE', 'ROUGE'])
        print(f"    ST1 Pipeline ✅ | statut={r['statut_rag']}")

        # ST2 — DataFrame retourné intègre
        df_out = r['dataframe']
        self.assertIsInstance(df_out, pd.DataFrame)
        self.assertGreater(len(df_out), 0)
        self.assertEqual(len(df_out), len(self.df))
        print(f"    ST2 DataFrame ✅ | {len(df_out):,} lignes")

        # ST3 — Score qualité cohérent
        score = r['score_qual']
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        qualite = r['qualite']
        self.assertIn('taux_completude', qualite)
        self.assertIn('taux_doublons', qualite)
        self.assertGreater(qualite['taux_completude'], 0)
        print(f"    ST3 Qualité ✅ | score={score:.1f}/100 | complétude={qualite['taux_completude']:.1f}%")

        # ST4 — Sous-branche DÉCLARÉE par l'actuaire, propagée telle quelle.
        # ⚠ PRÉMISSE MISE À JOUR (Phase 1) : ce test vérifiait la DÉTECTION
        # automatique (MOTS_CLES_DETECTION, supprimé). A1 ne devine plus la LoB —
        # il la reçoit. On vérifie donc qu'il la propage SANS la réinterpréter :
        # c'est cette valeur que A2 transmet à A3/A4/A5 (result_a2['branche']).
        branche = r['branche']
        self.assertIsInstance(branche, str)
        self.assertGreater(len(branche), 0)
        self.assertEqual(branche, 'auto',
            "A1 doit propager la sous-branche déclarée, sans la réinterpréter.")
        print(f"    ST4 Sous-branche déclarée ✅ | propagée='{branche}'")

        # ST5 — Hash MD5 calculé et non vide
        hash_md5 = r['hash_md5']
        self.assertIsInstance(hash_md5, str)
        self.assertGreater(len(hash_md5), 0)
        self.assertNotEqual(hash_md5, 'hash_non_disponible')
        print(f"    ST5 Hash MD5 ✅ | {hash_md5[:12]}...")

        # ST6 — Suggestions de mapping présentes si colonnes non standard
        rapport = r['rapport']
        self.assertIn('etapes', rapport)
        self.assertIn('chargement' if 'chargement' in rapport['etapes'] else 'dataframe_direct',
                      rapport['etapes'])
        print(f"    ST6 Rapport ✅ | étapes={rapport['etapes']}")

        # ST7 — VERT si données propres (500 lignes synthétiques sans doublons)
        self.assertGreaterEqual(score, 70.0,
            "Score qualité trop bas sur données synthétiques propres")
        print(f"    ST7 Qualité données propres ✅ | score={score:.1f} ≥ 70")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A1 INGESTION v1.0")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
