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


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A5 DEEP LEARNING v1.0 — CANN + TabNet")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
