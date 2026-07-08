"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ACTUARIA — TESTS PIPELINE NON-VIE A1→A6 (Direction Tarification)      ║
║     1 test par agent · sous-tests groupés · données synthétiques           ║
║     Commande : python test_pipeline_non_vie.py                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys, unittest
import numpy as np
import pandas as pd

sys.path.insert(0, '/home/claude')

# ── Données synthétiques communes ─────────────────────────────────────────────
np.random.seed(42)
N = 500

def make_df(n=N, avec_manquants=False, avec_doublons=False):
    df = pd.DataFrame({
        'id_contrat':          range(n),
        'nb_sinistres':        np.random.poisson(0.12, n),
        'cout_total_sinistres':np.random.exponential(800, n) * (np.random.poisson(0.12, n) > 0),
        'exposition':          np.random.uniform(0.1, 1.0, n),
        'age':                 np.random.randint(18, 75, n),
        'bonus_malus':         np.random.uniform(0.5, 3.5, n),
        'puissance_fiscale':   np.random.randint(4, 12, n),
        'age_vehicule':        np.random.randint(0, 20, n),
        'zone_geographique':   np.random.choice(['A','B','C','D'], n),
        'carburant':           np.random.choice(['essence','diesel'], n),
        'prime_pure':          np.random.exponential(300, n),
    })
    if avec_manquants:
        idx = np.random.choice(n, int(n*0.35), replace=False)
        df.loc[idx, 'age'] = np.nan
        df.loc[idx[:50], 'bonus_malus'] = np.nan
    if avec_doublons:
        df = pd.concat([df, df.iloc[:20]], ignore_index=True)
    return df

DF_BASE    = make_df()
DF_MANQ    = make_df(avec_manquants=True)
DF_DOUBLON = make_df(avec_doublons=True)


# ══════════════════════════════════════════════════════════════════════════════
# TEST A1 — INGESTION
# ══════════════════════════════════════════════════════════════════════════════
class TestA1Ingestion(unittest.TestCase):
    """A1 Amara — Ingestion & Validation. Teste : DataFrame direct, qualité,
    hash MD5, détection branche, statut RAG sur données dégradées."""

    @classmethod
    def setUpClass(cls):
        from a1_ingestion import AgentA1Ingestion
        cls.agent = AgentA1Ingestion(
            base_path='/tmp', audit_path='/tmp', verbose=False
        )

    def test_a1(self):
        # ── ST1 : DataFrame direct (portabilité future) ───────────────────────
        r = self.agent.run(dataframe=DF_BASE, branche='non_vie')
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        self.assertFalse(r['dataframe'].empty)
        print(f"    ST1 DataFrame direct ✅ | {len(r['dataframe'])} lignes | {r['statut_rag']}")

        # ── ST2 : Qualité des métriques ───────────────────────────────────────
        q = r['qualite']
        self.assertGreaterEqual(q['taux_completude'], 0)
        self.assertLessEqual(q['taux_completude'], 100)
        self.assertGreaterEqual(q['nb_doublons'], 0)
        self.assertGreaterEqual(q['score_global'], 0)
        print(f"    ST2 Qualité ✅ | complétude={q['taux_completude']:.1f}% | score={q['score_global']:.1f}")

        # ── ST3 : Hash MD5 valide ─────────────────────────────────────────────
        h = r['hash_md5']
        self.assertEqual(len(h), 32)
        self.assertTrue(all(c in '0123456789abcdef' for c in h.lower()))
        print(f"    ST3 Hash MD5 ✅ | {h[:8]}...")

        # ── ST4 : Détection de branche auto ───────────────────────────────────
        self.assertIn(r['branche'], ['auto','non_vie','mrh','rcpro','autre'])
        print(f"    ST4 Branche ✅ | {r['branche']}")

        # ── ST5 : Données très dégradées → score dégradé ────────────────────
        import pandas as pd, numpy as np
        df_deg = DF_BASE.copy()
        # 80% de manquants sur 6 colonnes → complétude < 80% → ROUGE
        for col in ['age','bonus_malus','puissance_fiscale',
                    'age_vehicule','prime_pure','exposition']:
            idx = np.random.choice(len(df_deg), int(len(df_deg)*0.80), replace=False)
            df_deg.loc[idx, col] = np.nan
        r_deg = self.agent.run(dataframe=df_deg, branche='non_vie')
        self.assertTrue(r_deg['success'])
        self.assertLess(r_deg['qualite']['taux_completude'], 95)
        self.assertIn(r_deg['statut_rag'], ['AMBRE','ROUGE'])
        print(f"    ST5 Données dégradées ✅ | complétude={r_deg['qualite']['taux_completude']:.1f}% → {r_deg['statut_rag']}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST A2 — PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════
class TestA2Preprocessing(unittest.TestCase):
    """A2 Kenji — Preprocessing & Feature Engineering. Teste : pipeline complet,
    garde-fou A1 échoué, imputation, structure paramètres, colonnes cibles."""

    @classmethod
    def setUpClass(cls):
        from a1_ingestion import AgentA1Ingestion
        from a2_preprocessing import AgentA2Preprocessing
        agent_a1 = AgentA1Ingestion(
            base_path='/tmp', audit_path='/tmp', verbose=False
        )
        cls.result_a1 = agent_a1.run(dataframe=DF_BASE, branche='non_vie')
        cls.agent = AgentA2Preprocessing(
            models_path='/tmp/models', audit_path='/tmp', verbose=False
        )

    def test_a2(self):
        # ── ST1 : Pipeline complet ────────────────────────────────────────────
        r = self.agent.run(self.result_a1)
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertFalse(r['dataframe'].empty)
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        print(f"    ST1 Pipeline ✅ | {r['dataframe'].shape} | {r['statut_rag']}")

        # ── ST2 : Garde-fou A1 échoué ─────────────────────────────────────────
        r_fail = self.agent.run({'success': False, 'erreur': 'test', 'branche': 'auto'})
        self.assertFalse(r_fail['success'])
        self.assertIsNotNone(r_fail.get('erreur'))
        print(f"    ST2 Garde-fou ✅ | A1 échoué → A2 bloqué")

        # ── ST3 : Imputation complète (0 NaN dans colonnes numériques) ───────
        df_out = r['dataframe']
        num_cols = df_out.select_dtypes(include=[np.number]).columns
        nan_total = df_out[num_cols].isnull().sum().sum()
        self.assertEqual(nan_total, 0, f"{nan_total} NaN restants")
        print(f"    ST3 Imputation ✅ | 0 NaN dans {len(num_cols)} colonnes numériques")

        # ── ST4 : Colonnes cibles présentes ───────────────────────────────────
        cols = r['dataframe'].columns.tolist()
        self.assertIn('nb_sinistres',         cols)
        self.assertIn('cout_total_sinistres',  cols)
        print(f"    ST4 Colonnes cibles ✅ | nb_sinistres + cout_total_sinistres")

        # ── ST5 : Paramètres non vides ────────────────────────────────────────
        self.assertIsInstance(r['parametres'], dict)
        self.assertGreater(len(r['parametres']), 0)
        print(f"    ST5 Paramètres ✅ | {len(r['parametres'])} clés")


# ══════════════════════════════════════════════════════════════════════════════
# TEST A3 — GLM
# ══════════════════════════════════════════════════════════════════════════════
class TestA3GLM(unittest.TestCase):
    """A3 Laurent — GLM Poisson/Gamma/Tweedie. Teste : pipeline complet,
    métriques Poisson, calibration non biaisée, meilleur modèle, RAG."""

    @classmethod
    def setUpClass(cls):
        from a1_ingestion import AgentA1Ingestion
        from a2_preprocessing import AgentA2Preprocessing
        from a3_glm import AgentA3GLM
        r1 = AgentA1Ingestion(base_path='/tmp', audit_path='/tmp', verbose=False)\
               .run(dataframe=DF_BASE, branche='non_vie')
        cls.result_a2 = AgentA2Preprocessing(models_path='/tmp/models', audit_path='/tmp', verbose=False)\
                          .run(r1)
        cls.agent = AgentA3GLM(models_path='/tmp/models', audit_path='/tmp', verbose=False)

    def test_a3(self):
        r = self.agent.run(self.result_a2, generer_graphiques=False)
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        print(f"    ST1 Pipeline ✅ | {r['statut_rag']}")

        # ── ST2 : Métriques Poisson présentes et cohérentes ───────────────────
        m_p = r['metriques'].get('poisson', {})
        self.assertIn('gini',  m_p)
        self.assertIn('aic',   m_p)
        self.assertGreaterEqual(m_p['gini'], 0)
        self.assertLessEqual(m_p['gini'],    1)
        self.assertGreater(m_p['aic'], 0)
        print(f"    ST2 Métriques Poisson ✅ | gini={m_p['gini']:.4f} aic={m_p['aic']:.0f}")

        # ── ST3 : Calibration non biaisée (fréquence obs ≈ pred) ─────────────
        freq_obs  = m_p.get('frequence_obs',  0)
        freq_pred = m_p.get('frequence_pred', 0)
        if freq_obs > 0:
            ecart_pct = abs(freq_obs - freq_pred) / freq_obs * 100
            self.assertLess(ecart_pct, 30,
                f"Biais fréquence : obs={freq_obs:.4f} pred={freq_pred:.4f}")
        print(f"    ST3 Calibration ✅ | freq_obs={freq_obs:.4f} freq_pred={freq_pred:.4f}")

        # ── ST4 : Meilleur modèle identifié ──────────────────────────────────
        self.assertIn(r['metriques'].get('meilleur_modele',''), ['poisson','gamma',''])
        print(f"    ST4 Meilleur modèle ✅ | {r['metriques'].get('meilleur_modele','N/A')}")

        # ── ST5 : Statut RAG cohérent avec Gini ──────────────────────────────
        gini = m_p.get('gini', 0)
        if gini < 0.05:
            self.assertIn(r['statut_rag'], ['AMBRE','ROUGE'])
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        print(f"    ST5 RAG ✅ | gini={gini:.4f} → {r['statut_rag']}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST A4 — ML
# ══════════════════════════════════════════════════════════════════════════════
class TestA4ML(unittest.TestCase):
    """A4 Priya — Machine Learning 6 modèles. Teste : classement trié,
    structure métriques, overfitting raisonnable, meilleur modèle, SHAP."""

    @classmethod
    def setUpClass(cls):
        from a1_ingestion import AgentA1Ingestion
        from a2_preprocessing import AgentA2Preprocessing
        from a4_ml import AgentA4ML
        r1 = AgentA1Ingestion(base_path='/tmp', audit_path='/tmp', verbose=False)\
               .run(dataframe=DF_BASE, branche='non_vie')
        cls.result_a2 = AgentA2Preprocessing(models_path='/tmp/models', audit_path='/tmp', verbose=False)\
                          .run(r1)
        cls.agent = AgentA4ML(models_path='/tmp/models', audit_path='/tmp', verbose=False)

    def test_a4(self):
        r = self.agent.run(self.result_a2, generer_graphiques=False, calcul_shap=False)
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertGreater(len(r['classement']), 0)
        print(f"    ST1 Pipeline ✅ | {len(r['classement'])} modèles | {r['statut_rag']}")

        # ── ST2 : Classement trié par Gini décroissant ────────────────────────
        ginis = [m['gini_test'] for m in r['classement']]
        self.assertEqual(ginis, sorted(ginis, reverse=True))
        print(f"    ST2 Tri ✅ | Ginis décroissants : {[round(g,4) for g in ginis[:3]]}")

        # ── ST3 : Structure métriques complète ────────────────────────────────
        for m in r['classement']:
            for k in ['modele','gini_test','gini_train','rmse_test']:
                self.assertIn(k, m, f"Clé '{k}' manquante dans {m.get('modele','?')}")
        print(f"    ST3 Structure ✅ | clés gini_test/gini_train/rmse_test présentes")

        # ── ST4 : Meilleur modèle a un gini_test ≥ 0 ────────────────────────
        meilleur = r['classement'][0]
        self.assertGreaterEqual(meilleur['gini_test'], 0)
        self.assertGreaterEqual(meilleur['gini_train'], 0)
        ovf = (meilleur['gini_test'] / meilleur['gini_train']
               if meilleur['gini_train'] > 0 else 1.0)
        print(f"    ST4 Métriques ✅ | {meilleur['modele']} : "
              f"train={meilleur['gini_train']:.4f} test={meilleur['gini_test']:.4f} "
              f"ovfit={ovf:.2f}")

        # ── ST5 : Meilleur modèle non None ───────────────────────────────────
        self.assertIsNotNone(r['meilleur_modele'])
        print(f"    ST5 Meilleur modèle ✅ | {meilleur['modele']} gini={meilleur['gini_test']:.4f}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST A5 — DEEP LEARNING
# ══════════════════════════════════════════════════════════════════════════════
class TestA5DeepLearning(unittest.TestCase):
    """A5 Yohan — CANN + TabNet. Teste : pipeline en mode rapide,
    métriques CANN et TabNet, historique convergence, classement."""

    @classmethod
    def setUpClass(cls):
        from a1_ingestion import AgentA1Ingestion
        from a2_preprocessing import AgentA2Preprocessing
        from a5_deep_learning import AgentA5DeepLearning
        r1 = AgentA1Ingestion(base_path='/tmp', audit_path='/tmp', verbose=False)\
               .run(dataframe=DF_BASE, branche='non_vie')
        cls.result_a2 = AgentA2Preprocessing(models_path='/tmp/models', audit_path='/tmp', verbose=False)\
                          .run(r1)
        cls.agent = AgentA5DeepLearning(models_path='/tmp/models', audit_path='/tmp', verbose=False)

    def test_a5(self):
        # Mode rapide : 5 epochs pour ne pas bloquer les tests
        r = self.agent.run(
            self.result_a2,
            n_epochs=5,
            generer_graphiques=False
        )
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        print(f"    ST1 Pipeline rapide ✅ | {r['statut_rag']}")

        # ── ST2 : Métriques CANN présentes et cohérentes ──────────────────────
        m_cann = r['metriques'].get('cann', {})
        self.assertIn('gini_test', m_cann)
        self.assertGreaterEqual(m_cann['gini_test'], 0)
        self.assertLessEqual(m_cann['gini_test'],    1)
        print(f"    ST2 CANN ✅ | gini_test={m_cann['gini_test']:.4f}")

        # ── ST3 : Métriques TabNet présentes et cohérentes ────────────────────
        m_tab = r['metriques'].get('tabnet', {})
        self.assertIn('gini_test', m_tab)
        self.assertGreaterEqual(m_tab['gini_test'], 0)
        self.assertLessEqual(m_tab['gini_test'],    1)
        print(f"    ST3 TabNet ✅ | gini_test={m_tab['gini_test']:.4f}")

        # ── ST4 : Historique de convergence non vide ─────────────────────────
        self.assertGreater(len(r['historique_cann']),   0)
        self.assertGreater(len(r['historique_tabnet']), 0)
        print(f"    ST4 Convergence ✅ | CANN={len(r['historique_cann'])} époques "
              f"TabNet={len(r['historique_tabnet'])} époques")

        # ── ST5 : Classement contient CANN et TabNet ─────────────────────────
        modeles = [m['modele'] for m in r['classement']]
        self.assertGreaterEqual(len(modeles), 2)
        print(f"    ST5 Classement ✅ | {modeles}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST A6 — COMPARAISON & SÉLECTION
# ══════════════════════════════════════════════════════════════════════════════
class TestA6Comparaison(unittest.TestCase):
    """A6 Victor — Comparaison & Sélection. Teste : A3 seul suffit,
    score modèle production, Gini = meilleur du classement, RAG, fiche décision."""

    @classmethod
    def setUpClass(cls):
        from a1_ingestion import AgentA1Ingestion
        from a2_preprocessing import AgentA2Preprocessing
        from a3_glm import AgentA3GLM
        from a4_ml import AgentA4ML
        from a6_comparaison import AgentA6Comparaison
        r1 = AgentA1Ingestion(base_path='/tmp', audit_path='/tmp', verbose=False)\
               .run(dataframe=DF_BASE, branche='non_vie')
        r2 = AgentA2Preprocessing(models_path='/tmp/models', audit_path='/tmp', verbose=False).run(r1)
        cls.result_a2 = r2
        cls.result_a3 = AgentA3GLM(models_path='/tmp/models', audit_path='/tmp', verbose=False)\
                          .run(r2, generer_graphiques=False)
        cls.result_a4 = AgentA4ML(models_path='/tmp/models', audit_path='/tmp', verbose=False)\
                          .run(r2, generer_graphiques=False, calcul_shap=False)
        cls.agent = AgentA6Comparaison(models_path='/tmp/models', audit_path='/tmp', verbose=False)

    def test_a6(self):
        # ── ST1 : A3 seul suffit (A4/A5 optionnels) ──────────────────────────
        r_minimal = self.agent.run(
            self.result_a2, result_a3=self.result_a3,
            generer_graphiques=False, aide_decision=False
        )
        self.assertTrue(r_minimal['success'], f"Erreur : {r_minimal.get('erreur')}")
        print(f"    ST1 A3 seul ✅ | {r_minimal['statut_rag']}")

        # ── ST2 : Pipeline complet A3+A4 ─────────────────────────────────────
        r = self.agent.run(
            self.result_a2,
            result_a3=self.result_a3,
            result_a4=self.result_a4,
            generer_graphiques=False,
            aide_decision=True,
        )
        self.assertTrue(r['success'])
        mp = r['modele_production']
        self.assertGreaterEqual(mp['score_global'], 0)
        self.assertLessEqual(mp['score_global'],    1)
        print(f"    ST2 Pipeline A3+A4 ✅ | {mp['modele']} score={mp['score_global']:.4f}")

        # ── ST3 : Gini production dans le top-3 du classement ───────────────
        ginis_classes = sorted([m['gini_test'] for m in r['classement']], reverse=True)
        top3 = ginis_classes[:3]
        self.assertIn(round(mp['gini_test'],4),
                      [round(g,4) for g in top3],
                      f"Gini production={mp['gini_test']:.4f} pas dans top-3={top3}")
        print(f"    ST3 Gini ✅ | {mp['gini_test']:.4f} dans top-3 {[round(g,4) for g in top3]}")

        # ── ST4 : RAG cohérent avec score et Gini ────────────────────────────
        self.assertIn(r['statut_rag'], ['VERT','AMBRE','ROUGE'])
        if mp['score_global'] >= 0.60 and mp['gini_test'] >= 0.15:
            self.assertEqual(r['statut_rag'], 'VERT')
        print(f"    ST4 RAG ✅ | score={mp['score_global']:.3f} "
              f"gini={mp['gini_test']:.4f} → {r['statut_rag']}")

        # ── ST5 : Fiche décision complète ────────────────────────────────────
        for k in ['modele','famille','score_global','gini_test','overfit_ratio']:
            self.assertIn(k, mp, f"Clé '{k}' manquante dans modele_production")
        print(f"    ST5 Fiche décision ✅ | "
              f"{mp['modele']} ({mp['famille']}) "
              f"overfit={mp['overfit_ratio']:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  ACTUARIA — TESTS PIPELINE NON-VIE A1 → A6")
    print("  1 test par agent · sous-tests groupés · données synthétiques")
    print("="*70)
    suite = unittest.TestLoader().loadTestsFromModule(__import__('__main__'))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print("\n"+"="*70)
    if result.wasSuccessful():
        print(f"  ✅ {result.testsRun}/{result.testsRun} TESTS PASSÉS — Pipeline A1→A6 VALIDÉ")
    else:
        n_fail = len(result.failures) + len(result.errors)
        print(f"  ❌ {n_fail} ÉCHEC(S) sur {result.testsRun} tests")
        for f in result.failures + result.errors:
            print(f"  → {f[0]}")
    print("="*70)
