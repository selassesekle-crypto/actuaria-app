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


# ══════════════════════════════════════════════════════════════════════════════
#  CONTRÔLES POSITIFS — L'IDENTITÉ D'UN CONTRAT SE DÉCLARE
# ══════════════════════════════════════════════════════════════════════════════

def _historique_renouvellement(n_contrats=200, n_echeances=3, seed=4):
    """Le même contrat, observé à plusieurs échéances — la forme exacte d'un
    historique de renouvellement.

    ⚠️ MESURÉ : A1 y voyait 67 % de « doublons » pour un seuil ROUGE à 5 %,
    parce qu'il dédoublonne sur l'identifiant SEUL. Un contrat vu trois fois
    n'est pas un fichier défectueux : c'est un historique.
    """
    rng = np.random.default_rng(seed)
    lignes = []
    for c in range(n_contrats):
        for e in range(n_echeances):
            lignes.append({
                'id_contrat':           c,
                'annee_exercice':       2021 + e,
                'nb_sinistres':         float(rng.poisson(0.08)),
                'cout_total_sinistres': float(rng.exponential(800)),
                'exposition':           float(rng.uniform(0.3, 1.0)),
                'age':                  float(rng.integers(18, 75)),
                'bonus_malus':          float(rng.uniform(50, 350)),
                'zone_geographique':    rng.choice(['A', 'B', 'C', 'D']),
            })
    return pd.DataFrame(lignes)


class T_L_Identite_D_Un_Contrat_Se_Declare(unittest.TestCase):
    """CONTRÔLE POSITIF — l'identité est un RÔLE déclaré, pas une devinette.

    ⚠️ MESURÉ SUR LES VINGT PLANS DU DÉPÔT. A1 prend
    `[c for c in df.columns if 'id' in c.lower() or 'pol' in c.lower()]` puis
    **le premier de la liste**. Quatre facteurs tarifaires sont attrapés par
    cette heuristique — `forme_juridique` et `caution_solidaire` contiennent
    « id », `antecedents_accidents_3ans` aussi. L'ordre des colonnes vient du
    fichier client : l'identité du contrat est devinée par sous-chaîne, et le
    résultat dépend de l'ordre des colonnes. Cela marche par chance.

    ⚠️ ET LE MÉCANISME EXISTE DÉJÀ, ENDORMI. `PlanTarifaire` porte
    `identifiant_contrat` depuis toujours, et `core/qualite_donnees.py` s'en
    sert (règle 1, QD-8). Mais A1 est le SEUL des six agents dont `run()` ne
    reçoit pas le plan — c'est exactement l'agent qui doit deviner.
    """

    @classmethod
    def setUpClass(cls):
        import dataclasses

        from core.plan_tarifaire import PlanTarifaire
        from direction_non_vie.tarification.a1_ingestion.agent import (
            AgentA1Ingestion,
        )
        cls.agent = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        _base = PlanTarifaire.depuis_yaml(os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         '..', '..', '..')),
            'plans', 'auto.yaml'))
        cls.plan_declare = dataclasses.replace(
            _base, identifiant_contrat='id_contrat', echeance='annee_exercice')
        cls.plan_id_seul = dataclasses.replace(
            _base, identifiant_contrat='id_contrat')

    def test_un_historique_de_renouvellement_n_est_pas_un_fichier_de_DOUBLONS(self):
        """⚠️ LE CAS QUI BLOQUE TOUT LE RESTE. Sans cette distinction, la
        donnée nécessaire à une élasticité est refusée à l'entrée."""
        df = _historique_renouvellement(200, 3)
        r = self.agent.run(branche='non_vie', sous_branche='auto',
                           dataframe=df, plan=self.plan_declare)
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        q = r['qualite']
        self.assertEqual(
            q['nb_doublons'], 0,
            f"{q['nb_doublons']} « doublons » ({q['taux_doublons']:.1f} %) sur "
            f"un historique de 200 contrats × 3 échéances — un contrat vu "
            f"trois fois n'est pas une ligne redondante")
        self.assertEqual(q.get('granularite'), 'un contrat par échéance')
        print(f"    POS-A1a historique 200×3 → {q['nb_doublons']} doublon, "
              f"granularité « {q.get('granularite')} » ✅")

    def test_un_VRAI_doublon_reste_signale(self):
        """⚠️⚠️ LE GARDE-FOU DE LA DISTINCTION. Elle exempte l'échéance ; il
        faut donc prouver qu'elle n'exempte pas le doublon réel — même
        contrat, MÊME échéance. Une liste qui exempte ouvre un trou."""
        df = _historique_renouvellement(100, 3)
        df = pd.concat([df, df.iloc[:30]], ignore_index=True)   # 30 vrais doublons
        r = self.agent.run(branche='non_vie', sous_branche='auto',
                           dataframe=df, plan=self.plan_declare)
        q = r['qualite']
        self.assertEqual(
            q['nb_doublons'], 30,
            f"30 lignes (même contrat, MÊME échéance) ont été ajoutées et "
            f"{q['nb_doublons']} sont signalées — la distinction avale un "
            f"vrai doublon")
        print(f"    POS-A1b 30 vrais doublons ajoutés → {q['nb_doublons']} "
              f"signalés ✅")

    def test_l_identifiant_DECLARE_prime_sur_la_devinette(self):
        """⚠️ LE DÉFAUT MESURÉ, DANS SA FORME PURE. Une colonne dont le nom
        contient « id » précède l'identifiant réel dans le fichier : la
        devinette dédoublonne alors sur un FACTEUR TARIFAIRE."""
        df = _historique_renouvellement(150, 2)
        # `forme_juridique` contient « id » — et arrive AVANT `id_contrat`
        df.insert(0, 'forme_juridique',
                  np.random.default_rng(1).choice(['SARL', 'SAS'], len(df)))
        r = self.agent.run(branche='non_vie', sous_branche='auto',
                           dataframe=df, plan=self.plan_id_seul)
        q = r['qualite']
        self.assertEqual(q.get('identifiant_contrat'), 'id_contrat',
                         f"A1 a retenu « {q.get('identifiant_contrat')} » "
                         f"comme identité du contrat")
        self.assertEqual(q.get('source_identifiant'), 'plan')
        # 150 contrats × 2 échéances, dédoublonnés sur l'identifiant SEUL
        self.assertEqual(q['nb_doublons'], 150)
        print(f"    POS-A1c identifiant retenu « {q['identifiant_contrat']} » "
              f"(source : {q['source_identifiant']}) ✅")

    def test_sans_declaration_A1_DIT_qu_il_devine(self):
        """⚠️ LE REPLI RESTE, MAIS IL NE SE TAIT PLUS. Il est légitime — les
        vingt plans du dépôt ne déclarent rien — mais un lecteur doit savoir
        que l'identité n'a pas été déclarée."""
        r = self.agent.run(branche='non_vie', sous_branche='auto',
                           dataframe=_df_auto(300))
        q = r['qualite']
        self.assertEqual(q.get('source_identifiant'), 'devinee',
                         "A1 devine l'identité sans le dire")
        self.assertTrue(
            any('devin' in str(a).lower() or 'non déclar' in str(a).lower()
                for a in (q.get('alertes_aberrants') or []) + [q.get('note_identite', '')]),
            "aucune mention ne signale que l'identité a été devinée")
        print(f"    POS-A1d identité devinée « {q.get('identifiant_contrat')} », "
              f"et A1 le dit ✅")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A1 INGESTION v1.0")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
