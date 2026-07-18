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


class TestA1MultiFormat(unittest.TestCase):
    """A1 — chargement multi-format par EXTENSION. Le DataFrame lu doit être
    identique quelle que soit la source (csv/txt/xlsx/json/parquet) ; une extension
    inconnue → erreur propre nommant les formats acceptés."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        cls.agent = AgentA1Ingestion(base_path='/tmp', audit_path='/tmp', verbose=False)
        cls.tmp = tempfile.mkdtemp(prefix='a1_fmt_')
        rng = np.random.default_rng(0)
        cls.ref = pd.DataFrame({
            'id_contrat': list(range(10)),
            'age':        rng.integers(18, 75, 10),
            'prime':      rng.uniform(100, 900, 10).round(2),
            'zone':       rng.choice(['A', 'B', 'C'], 10),
        })

    def _lu(self, nom):
        from pathlib import Path
        return self.agent._lire_fichier(Path(os.path.join(self.tmp, nom)))

    def _assert_identique(self, nom, **kw):
        pd.testing.assert_frame_equal(self._lu(nom), self.ref, check_dtype=False, **kw)

    def test_fmt_csv_virgule(self):
        self.ref.to_csv(os.path.join(self.tmp, 'a.csv'), index=False, sep=',')
        self._assert_identique('a.csv')
        print("    A1-FMT csv (,) → identique ✅")

    def test_fmt_csv_pointvirgule(self):       # séparateur DÉTECTÉ (sep=None)
        self.ref.to_csv(os.path.join(self.tmp, 'b.csv'), index=False, sep=';')
        self._assert_identique('b.csv')
        print("    A1-FMT csv (;) détecté → identique ✅")

    def test_fmt_txt_tabulation(self):         # .txt traité comme csv, sép. détecté
        self.ref.to_csv(os.path.join(self.tmp, 'c.txt'), index=False, sep='\t')
        self._assert_identique('c.txt')
        print("    A1-FMT txt (tab) détecté → identique ✅")

    def test_fmt_xlsx(self):
        self.ref.to_excel(os.path.join(self.tmp, 'd.xlsx'), index=False)
        self._assert_identique('d.xlsx')       # corrige l'ancien bug sheet_name=None (dict)
        print("    A1-FMT xlsx → identique (plus de dict) ✅")

    def test_fmt_json(self):
        self.ref.to_json(os.path.join(self.tmp, 'e.json'))          # orient='columns'
        self._assert_identique('e.json', check_like=True)          # ordre colonnes indifférent
        print("    A1-FMT json → identique ✅")

    def test_fmt_xls_route_vers_excel(self):
        """.xls est SUPPORTÉ (routé vers read_excel) ; le lire exige xlrd (absent
        ici). On vérifie qu'il n'est PAS rejeté comme « format non supporté »."""
        with open(os.path.join(self.tmp, 'f.xls'), 'wb') as fh:
            fh.write(b'\xd0\xcf\x11\xe0 fake xls')
        try:
            self._lu('f.xls')
        except ValueError as e:
            self.assertNotIn('format non supporté', str(e).lower(),
                             ".xls ne doit PAS être rejeté comme format non supporté")
        except Exception:
            pass   # read_excel a tenté (xlrd absent / contenu invalide) → routé = supporté
        print("    A1-FMT xls routé vers read_excel (supporté ; exige xlrd) ✅")

    def test_fmt_parquet(self):
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            try:
                import fastparquet  # noqa: F401
            except ImportError:
                self.skipTest("pyarrow/fastparquet absents — round-trip parquet non testable ici")
        self.ref.to_parquet(os.path.join(self.tmp, 'g.parquet'))
        self._assert_identique('g.parquet')
        print("    A1-FMT parquet → identique ✅")

    def test_fmt_inconnu_erreur_propre(self):
        open(os.path.join(self.tmp, 'h.xyz'), 'w').close()
        with self.assertRaises(ValueError) as ctx:
            self._lu('h.xyz')
        msg = str(ctx.exception).lower()
        self.assertIn('.xyz', msg)
        self.assertIn('format non supporté', msg)
        for fmt in ('csv', 'xlsx', 'xls', 'json', 'txt', 'parquet'):
            self.assertIn(fmt, msg)            # la liste des formats acceptés
        print("    A1-FMT inconnu (.xyz) → erreur propre + liste des formats ✅")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A1 INGESTION v1.0")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
