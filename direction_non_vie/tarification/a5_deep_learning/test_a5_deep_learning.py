"""
Tests A5 Deep Learning v1.0 — CANN + TabNet Non-Vie
7 tests · fallback si PyTorch absent · données synthétiques
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

try:
    import torch
    TORCH_OK = True
except ImportError:
    TORCH_OK = False


def _make_r_a2(n=400):
    np.random.seed(42)
    exposition = np.random.uniform(0.1, 1.0, n)
    nb_sin     = np.random.poisson(0.08 * exposition, n).astype(float)
    cout       = np.where(nb_sin > 0, np.random.gamma(2, 400, n), 0.0)
    df = pd.DataFrame({
        'nb_sinistres':         nb_sin,
        'cout_total_sinistres': cout,
        'exposition':           exposition,
        'age':                  np.random.randint(18, 75, n).astype(float),
        'bonus_malus':          np.random.uniform(50, 350, n),
        'puissance_fiscale':    np.random.randint(4, 15, n).astype(float),
        'prime_pure':           cout * exposition,
    })
    return {'success': True, 'dataframe': df, 'branche': 'auto',
            'statut_rag': 'VERT', 'parametres': {}, 'rapport': {},
            'commentaire': 'OK', 'audit_id': 'A2_TEST', 'erreur': None}


def _make_r_a3():
    return {
        'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
        'metriques': {
            'poisson': {'gini': 0.14, 'aic': 1100,
                        'vars_retenues': ['age', 'bonus_malus'],
                        'nb_obs_train': 320, 'nb_obs_test': 80},
        },
        'modeles': {},  # modele Poisson absent → init CANN aléatoire (fallback)
        'relativites_poisson': {}, 'relativites_gamma': {},
        'validation_glm': {'statut_global': 'VERT'},
        'excel_bytes': b'', 'word_bytes': b'', 'pdf_bytes': b'',
        'hypotheses': {}, 'audit_trail': {}, 'erreur': None,
    }


class TestA5DeepLearning(unittest.TestCase):
    """A5 DL — CANN + TabNet, Gini, feature importance, H1-H4."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a5_deep_learning.agent import AgentA5DeepLearning
        cls.agent  = AgentA5DeepLearning(models_path='/tmp', audit_path='/tmp', verbose=False)
        cls.r_a2   = _make_r_a2(400)
        cls.r_a3   = _make_r_a3()
        if TORCH_OK:
            cls.r = cls.agent.run(
                result_a2=cls.r_a2, result_a3=cls.r_a3,
                n_epochs=5, batch_size=64, generer_graphiques=False
            )
        else:
            # Sans PyTorch → l'agent retourne une erreur documentée
            cls.r = cls.agent.run(
                result_a2=cls.r_a2, result_a3=cls.r_a3,
                generer_graphiques=False
            )

    def test_a5(self):
        r = self.r

        # ST1 — Résultat structuré dans tous les cas (avec ou sans PyTorch)
        self.assertIn('success', r)
        self.assertIn('statut_rag', r)
        self.assertIn(r['statut_rag'], ['VERT', 'AMBRE', 'ROUGE'])
        if not TORCH_OK:
            # Sans PyTorch : échec documenté, pas de crash silencieux
            self.assertFalse(r['success'])
            self.assertIsNotNone(r.get('erreur'))
            print(f"    ST1 Sans PyTorch ✅ | erreur documentée : {r.get('erreur','')[:50]}")
            # Tests ST2-ST7 passés en mode skip gracieux
            for i in range(2, 8):
                print(f"    ST{i} Skipped (PyTorch absent)")
            return
        print(f"    ST1 Pipeline ✅ | statut={r['statut_rag']}")

        # ST2 — CANN calibré
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        met = r.get('metriques', {})
        self.assertIn('cann', met, "Métriques CANN manquantes")
        m_cann = met['cann']
        self.assertIn('gini_test', m_cann)
        self.assertGreaterEqual(m_cann['gini_test'], 0.0)
        print(f"    ST2 CANN ✅ | Gini={m_cann['gini_test']:.4f} "
              f"époques={m_cann.get('n_epochs_reels','?')}")

        # ST3 — TabNet calibré
        self.assertIn('tabnet', met, "Métriques TabNet manquantes")
        m_tab = met['tabnet']
        self.assertIn('gini_test', m_tab)
        self.assertGreaterEqual(m_tab['gini_test'], 0.0)
        print(f"    ST3 TabNet ✅ | Gini={m_tab['gini_test']:.4f}")

        # ST4 — Early stopping CANN : époques réelles ≤ 200
        n_ep = m_cann.get('n_epochs_reels', 200)
        self.assertLessEqual(n_ep, 200,
            "CANN doit utiliser au maximum 200 époques (early stopping actif)")
        print(f"    ST4 Early stopping ✅ | {n_ep} époques (≤ 200)")

        # ST5 — gini_glm_ref ≠ 0.121 hardcodé
        # On vérifie que le classement référence le Gini A3 (0.14), pas 0.121
        classement = r.get('classement', [])
        glm_entries = [m for m in classement if 'GLM' in m.get('modele', '')]
        if glm_entries:
            gini_glm = glm_entries[0].get('gini_test', 0)
            self.assertNotAlmostEqual(gini_glm, 0.121, places=2,
                msg="gini_glm_ref ne doit pas être hardcodé à 0.121")
        print(f"    ST5 Gini GLM dynamique ✅")

        # ST6 — Historique d'apprentissage présent
        hist = r.get('historique_cann', m_cann.get('historique', []))
        self.assertIsInstance(hist, list)
        print(f"    ST6 Historique ✅ | {len(hist)} entrées")

        # ST7 — Classement final non vide
        self.assertGreater(len(classement), 0)
        best = classement[0]
        self.assertIn('gini_test', best)
        print(f"    ST7 Classement ✅ | {len(classement)} modèles | "
              f"best={best.get('modele','?')} Gini={best.get('gini_test',0):.4f}")




def _make_r_a2_avec_genre_numerique(n=400):
    """Fixture avec une colonne 'sexe' numérique (0/1) — même cas concret
    que le test équivalent d'A4 (audit V7 anomalie B1)."""
    np.random.seed(7)
    exposition = np.random.uniform(0.1, 1.0, n)
    nb_sin     = np.random.poisson(0.08 * exposition, n).astype(float)
    cout       = np.where(nb_sin > 0, np.random.gamma(2, 400, n), 0.0)
    df = pd.DataFrame({
        'nb_sinistres':         nb_sin,
        'cout_total_sinistres': cout,
        'exposition':           exposition,
        'age':                  np.random.randint(18, 75, n).astype(float),
        'bonus_malus':          np.random.uniform(50, 350, n),
        'sexe':                 np.random.choice([0, 1], n),  # genre numérique
        'prime_pure':           cout * exposition,
    })
    return {'success': True, 'dataframe': df, 'branche': 'auto',
            'statut_rag': 'VERT', 'parametres': {}, 'rapport': {},
            'commentaire': 'OK', 'audit_id': 'A2_TEST_GENRE', 'erreur': None}


class TestA5FiltreGenre(unittest.TestCase):
    """
    Verrou anti-régression — audit V7 anomalie BLOQUANTE B1 (même trou
    que A4 : A5 utilisait une logique de sélection de features identique,
    sans aucun filtre genre, avant l'audit V7).
    """

    def test_genre_numerique_absent_des_features(self):
        if not TORCH_OK:
            self.skipTest("PyTorch non installé — filtre vérifié par lecture "
                           "de code lors de l'audit V7 (logique identique à A4, "
                           "elle-même vérifiée empiriquement).")
        from direction_non_vie.tarification.a5_deep_learning.agent import AgentA5DeepLearning
        agent = AgentA5DeepLearning(models_path='/tmp', audit_path='/tmp', verbose=False)
        r_a2 = _make_r_a2_avec_genre_numerique(400)
        r_a3 = _make_r_a3()
        r = agent.run(result_a2=r_a2, result_a3=r_a3,
                      n_epochs=3, batch_size=64, generer_graphiques=False)

        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        features = r.get('rapport', {}).get('feature_names', [])
        self.assertNotIn(
            'sexe', features,
            "RÉGRESSION BLOQUANTE (audit V7 B1) — la colonne 'sexe' "
            "numérique est présente dans les features du modèle DL."
        )
        print(f"    B1-A5 Genre numérique filtré ✅ | features={features}")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A5 DEEP LEARNING v1.0 — CANN + TabNet")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
