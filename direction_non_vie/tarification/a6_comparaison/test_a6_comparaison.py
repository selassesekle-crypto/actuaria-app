"""
Tests A6 Comparaison v1.0 — Sélection finale modèle production Non-Vie
7 tests · walk-forward A/E · grille multicritères · standard ActuarIA
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))


def _make_r_a2_avec_annee(n=800):
    np.random.seed(42)
    exposition = np.random.uniform(0.1, 1.0, n)
    nb_sin     = np.random.poisson(0.08 * exposition, n).astype(float)
    cout       = np.where(nb_sin > 0, np.random.gamma(2, 400, n), 0.0)
    annees     = np.random.choice([2020, 2021, 2022, 2023], n,
                                   p=[0.25, 0.25, 0.25, 0.25])
    df = pd.DataFrame({
        'nb_sinistres':         nb_sin,
        'cout_total_sinistres': cout,
        'exposition':           exposition,
        'prime_pure':           cout * exposition,
        'annee_souscription':   annees,
        'age':                  np.random.randint(18, 75, n).astype(float),
        'zone_geographique':    np.random.choice(['A','B','C','D'], n),
        'bonus_malus':          np.random.uniform(50, 350, n),
    })
    return {'success': True, 'dataframe': df, 'branche': 'auto',
            'statut_rag': 'VERT', 'parametres': {}, 'rapport': {},
            'commentaire': 'OK', 'audit_id': 'A2_TEST', 'erreur': None}


def _make_r_a3():
    return {
        'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
        'metriques': {
            'poisson':  {'gini': 0.18, 'aic': 1200, 'vars_retenues': ['age','bonus_malus'],
                         'nb_obs_train': 640, 'nb_obs_test': 160,
                         'relativites': {'age': {'relativite': 1.05, 'beta': 0.05,
                                                  'ic95_low': 1.01, 'ic95_high': 1.09,
                                                  'pvalue': 0.02, 'significatif': True, 'sens': 'aggravant'}}},
            'gamma':    {'gini': 0.12, 'aic': 980},
            'tweedie':  {'gini': 0.15, 'aic': 1050},
        },
        'relativites_poisson': {'age': {'relativite': 1.05, 'beta': 0.05,
                                         'ic95_low': 1.01, 'ic95_high': 1.09,
                                         'pvalue': 0.02, 'significatif': True, 'sens': 'aggravant'}},
        'relativites_gamma': {},
        'validation_glm': {'statut_global': 'VERT'},
        'excel_bytes': b'', 'word_bytes': b'', 'pdf_bytes': b'',
        'hypotheses': {}, 'audit_trail': {}, 'erreur': None,
    }


def _make_r_a4():
    return {
        'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
        'classement': [
            {'modele': 'xgboost', 'famille': 'ML', 'gini_test': 0.22, 'gini_train': 0.24,
             'overfit_ratio': 0.92, 'rmse_test': 0.12, 'mae_test': 0.08,
             'overfit_alerte': False, 'score_global': 0.78, 'interpretabilite': 0.60},
            {'modele': 'lightgbm', 'famille': 'ML', 'gini_test': 0.21, 'gini_train': 0.23,
             'overfit_ratio': 0.91, 'rmse_test': 0.13, 'mae_test': 0.09,
             'overfit_alerte': False, 'score_global': 0.75, 'interpretabilite': 0.60},
            {'modele': 'elasticnet', 'famille': 'ML', 'gini_test': 0.16, 'gini_train': 0.17,
             'overfit_ratio': 0.94, 'rmse_test': 0.15, 'mae_test': 0.11,
             'overfit_alerte': False, 'score_global': 0.70, 'interpretabilite': 0.85},
            {'modele': 'GLM_POISSON', 'famille': 'GLM', 'gini_test': 0.18, 'gini_train': 0.18,
             'overfit_ratio': 1.00, 'rmse_test': 0.14, 'mae_test': 0.10,
             'overfit_alerte': False, 'score_global': 0.72, 'interpretabilite': 1.00},
        ],
        'metriques': {}, 'shap_values': {}, 'monitoring': {}, 'modele_production': {},
        'validation_ml': {}, 'excel_bytes': b'', 'hypotheses': {}, 'audit_trail': {},
        'erreur': None,
    }


class TestA6Comparaison(unittest.TestCase):
    """A6 Comparaison — Multicritères, walk-forward A/E, segments, standard."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        cls.agent = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp', verbose=False)
        cls.r_a2  = _make_r_a2_avec_annee(800)
        cls.r_a3  = _make_r_a3()
        cls.r_a4  = _make_r_a4()
        cls.r     = cls.agent.run(
            result_a2=cls.r_a2, result_a3=cls.r_a3,
            result_a4=cls.r_a4, result_a5=None,
            col_cible='prime_pure', col_expo='exposition',
            generer_graphiques=False, aide_decision=True
        )

    def test_a6(self):
        r = self.r

        # ST1 — Pipeline sans erreur
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT', 'AMBRE', 'ROUGE'])
        print(f"    ST1 Pipeline ✅ | statut={r['statut_rag']}")

        # ST2 — Classement non vide
        classement = r['classement']
        self.assertGreater(len(classement), 0)
        prod = r['modele_production']
        self.assertIn('modele', prod)
        self.assertIn('score_global', prod)
        print(f"    ST2 Classement ✅ | {len(classement)} modèles | "
              f"production='{prod.get('modele','')}' score={prod.get('score_global',0):.4f}")

        # ST3 — Scores multicritères dans [0, 1]
        for m in classement:
            s = m.get('score_global', 0)
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)
        print(f"    ST3 Scores ✅ | tous dans [0,1]")

        # ST4 — Walk-forward backtesting réel (colonne annee_souscription présente)
        bt = r['backtest']
        self.assertTrue(bt.get('disponible'), "Backtesting non disponible")
        self.assertIn('ae_ratio', bt)
        ae = bt['ae_ratio']
        self.assertGreater(ae, 0)
        # Walk-forward si colonne annee disponible
        if bt.get('split') == 'walk_forward_temporel':
            wf = bt.get('walk_forward', [])
            self.assertGreater(len(wf), 0)
            print(f"    ST4 Walk-forward ✅ | {len(wf)} fenêtres | "
                  f"A/E final={ae:.4f} | stabilité={bt.get('stabilite_wf','?')}")
        else:
            print(f"    ST4 Backtesting ✅ | A/E={ae:.4f} (split={bt.get('split','?')})")

        # ST5 — A/E par segment calculé
        # Les données synthétiques ont annee_souscription + zone_geographique :
        # en walk-forward, au moins 'quintiles_risque' doit être produit.
        segs = bt.get('ae_par_segment', {})
        self.assertIsInstance(segs, dict)
        if bt.get('split') == 'walk_forward_temporel' and bt.get('disponible'):
            self.assertGreater(len(segs), 0,
                "Au moins 1 segment A/E attendu avec annee_souscription dans les données")
        print(f"    ST5 A/E segments ✅ | {len(segs)} segment(s) : {list(segs.keys())}")

        # ST6 — Validation sélection C1/C2/C3
        val = r['validation_selection']
        for ckey in ['c1_nb_modeles', 'c2_ecart_gini', 'c3_coherence']:
            self.assertIn(ckey, val, f"Contrôle '{ckey}' manquant")
            c = val[ckey]
            self.assertIn(c.get('statut'), ['VERT', 'AMBRE', 'ROUGE'])
        print(f"    ST6 Validation ✅ | "
              f"C1={val['c1_nb_modeles']['statut']} "
              f"C2={val['c2_ecart_gini']['statut']} "
              f"C3={val['c3_coherence']['statut']}")

        # ST7 — Standard ActuarIA : toutes les clés de rapport vérifiées
        for key in ['excel_bytes', 'word_bytes', 'html_bytes', 'hypotheses', 'audit_trail']:
            self.assertIn(key, r, f"Clé '{key}' manquante")
        self.assertIsInstance(r['excel_bytes'], bytes)
        self.assertIsInstance(r['word_bytes'],  bytes)
        self.assertIsInstance(r['html_bytes'],  bytes)
        self.assertIsInstance(r['audit_trail'], dict)
        try:
            from docx import Document  # noqa
            DOCX_OK = True
        except ImportError:
            DOCX_OK = False
        if DOCX_OK:
            self.assertGreater(len(r['word_bytes']), 0,
                "word_bytes vide — rapport Word non généré malgré python-docx")
        self.assertGreater(len(r['html_bytes']), 500,
            "html_bytes trop court — rapport HTML non généré")
        print(
            f"    ST7 Standard ActuarIA ✅ | "
            f"excel={len(r['excel_bytes'])} b | "
            f"word={len(r['word_bytes'])} b | "
            f"html={len(r['html_bytes'])} b | "
            f"audit={len(r['audit_trail'])} clés"
        )


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A6 COMPARAISON v1.0 — SÉLECTION FINALE")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
