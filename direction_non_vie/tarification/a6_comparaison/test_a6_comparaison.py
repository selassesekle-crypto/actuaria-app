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




class TestA6GouvernancePlafond(unittest.TestCase):
    """
    Plafond de gouvernance du profil de pondération — ACPR-2022-P-01 §4.3.

    Audit V4 point #14 : ce test aurait immédiatement détecté le bug
    corrigé au point #10 (défaut environnement='developpement' rendait
    le contrôle silencieusement contournable par simple omission du
    paramètre, sans action malveillante). Il protège contre toute
    régression future sur ce mécanisme fail-safe.

    Réf. : Saltzer & Schroeder (1975), fail-safe defaults.
    """

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        cls.agent = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp', verbose=False)
        cls.r_a2  = _make_r_a2_avec_annee(800)
        cls.r_a3  = _make_r_a3()
        cls.r_a4  = _make_r_a4()

    def test_gouvernance_omission_totale_plafonne(self):
        """GOUV1 — Aucun paramètre de gouvernance précisé (le scénario
        exact dénoncé par l'audit V4) → le statut ne doit JAMAIS être VERT,
        et environnement doit valoir 'production' par défaut (fail-safe)."""
        r = self.agent.run(
            result_a2=self.r_a2, result_a3=self.r_a3, result_a4=self.r_a4,
            result_a5=None, generer_graphiques=False,
            generer_rapport_equipe=False,
            # Ni environnement=, ni profil_valide_par= volontairement omis
        )
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        at = r.get('audit_trail', {})
        self.assertEqual(at.get('environnement'), 'production',
            "Défaut fail-safe rompu : environnement doit être 'production' "
            "par défaut, pas 'developpement' (régression du fix V4 point #10 ?)")
        self.assertFalse(at.get('gouvernance_ok'),
            "gouvernance_ok=True sans validateur en 'production' — "
            "le plafond de gouvernance est contournable (régression !)")
        self.assertNotEqual(r['statut_rag'], 'VERT',
            "Statut VERT obtenu malgré l'absence totale de validation "
            "de gouvernance — le contrôle est contourné par omission.")
        print(f"    GOUV1 Omission plafonnée ✅ | statut={r['statut_rag']} | "
              f"environnement={at.get('environnement')} | "
              f"gouvernance_ok={at.get('gouvernance_ok')}")

    def test_gouvernance_developpement_non_bloquant(self):
        """GOUV2 — environnement='developpement' explicite → le contrôle
        ne doit PAS être bloquant (usage de développement/test légitime)."""
        r = self.agent.run(
            result_a2=self.r_a2, result_a3=self.r_a3, result_a4=self.r_a4,
            result_a5=None, generer_graphiques=False,
            generer_rapport_equipe=False,
            environnement='developpement',
        )
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        at = r.get('audit_trail', {})
        self.assertTrue(at.get('gouvernance_ok'),
            "gouvernance_ok=False en environnement='developpement' explicite "
            "— le contrôle ne devrait pas être bloquant hors production")
        print(f"    GOUV2 Dev non bloquant ✅ | gouvernance_ok={at.get('gouvernance_ok')}")

    def test_gouvernance_production_avec_validateur(self):
        """GOUV3 — Production + profil_valide_par renseigné → gouvernance
        conforme, VERT redevient atteignable (si les autres critères le sont)."""
        r = self.agent.run(
            result_a2=self.r_a2, result_a3=self.r_a3, result_a4=self.r_a4,
            result_a5=None, generer_graphiques=False,
            generer_rapport_equipe=False,
            environnement='production', profil_valide_par='Actuaire Test',
        )
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        at = r.get('audit_trail', {})
        self.assertTrue(at.get('gouvernance_ok'),
            "gouvernance_ok=False malgré profil_valide_par renseigné en production")
        self.assertEqual(at.get('profil_valide_par'), 'Actuaire Test')
        print(f"    GOUV3 Production validée ✅ | "
              f"validé_par={at.get('profil_valide_par')} | statut={r['statut_rag']}")




class TestA6GiniWalkForwardSentinelles(unittest.TestCase):
    """
    Sentinelles anti-régression — Gini walk-forward (audit V6).

    Deux bugs réels ont été découverts par exécution effective du walk-forward
    avec un modèle ML réel en tête de classement (jamais fait avant l'audit
    V5→V6, car les tests précédents ne poussaient jamais ce chemin jusqu'au
    bout) :
      (a) np.trapz supprimé sous numpy ≥ 2.0 → AttributeError absorbée
          silencieusement par le except Exception englobant → gini_wf_moyen
          restait toujours None, sans aucune alerte visible dans les rapports.
      (b) Le signe de la formule était inversé (1-2·AUC au lieu de 2·AUC-1) :
          un prédicteur PARFAIT obtenait un Gini fortement NÉGATIF, et un
          prédicteur ANTI-CORRÉLÉ un Gini fortement POSITIF — l'exact inverse
          de la convention actuarielle standard.

    Ces deux bugs étaient dans une formule inline (a6_comparaison/agent.py,
    bloc de calcul du Gini walk-forward) jamais exercée bout-en-bout avant
    l'exécution réelle d'un walk-forward avec XGBoost/LightGBM en tête —
    exactement le type de défaut « marche sur le chemin testé, échoue en
    silence sur le chemin voisin » que les cycles d'audit successifs (V4,
    V5) demandaient explicitement de traquer.

    Ce test reproduit isolément la formule pour verrouiller son comportement,
    indépendamment de la disponibilité de XGBoost/LightGBM dans l'environnement
    d'exécution des tests (qui peuvent ne pas être installés en CI).
    """

    @staticmethod
    def _gini_walk_forward(y_te, pred_te):
        """Reproduction exacte de la formule corrigée (a6_comparaison/agent.py)."""
        if y_te.sum() > 0 and pred_te.std() > 0:
            _trapz_fn = np.trapezoid if hasattr(np, 'trapezoid') else np.trapz
            ordre = np.argsort(-pred_te)
            y_sorted = y_te[ordre]
            lorenz = np.cumsum(y_sorted) / max(y_te.sum(), 1e-9)
            return round(float(2 * _trapz_fn(lorenz, np.linspace(0, 1, len(lorenz))) - 1), 4)
        return None

    def test_sentinelle_numpy_2x_pas_de_none(self):
        """SENT1 — Sous numpy actuel (2.x dans cet environnement si applicable),
        le Gini walk-forward ne doit JAMAIS être None pour des données valides
        (régression du bug np.trapz supprimé)."""
        np.random.seed(0)
        y_te = np.random.exponential(100, 300)
        pred_te = np.random.exponential(100, 300)
        gini = self._gini_walk_forward(y_te, pred_te)
        self.assertIsNotNone(
            gini,
            "Gini walk-forward est None — régression possible du bug "
            "np.trapz (supprimé sous numpy ≥ 2.0, audit V6 bug #1)."
        )
        print(f"    SENT1 Pas de None sous numpy {np.__version__} ✅ | Gini={gini}")

    def test_sentinelle_signe_predicteur_parfait(self):
        """SENT2 — Un prédicteur PARFAIT (mêmes valeurs que l'observé, même
        ordre) doit produire un Gini walk-forward FORTEMENT POSITIF —
        régression du bug de signe (audit V6 bug #2) sinon."""
        np.random.seed(1)
        y_te = np.random.exponential(100, 300)
        gini_parfait = self._gini_walk_forward(y_te, y_te.copy())
        self.assertGreater(
            gini_parfait, 0.5,
            f"Prédicteur parfait donne Gini={gini_parfait} — devrait être "
            f"fortement positif. Régression du bug de signe (audit V6 #2) ?"
        )
        print(f"    SENT2 Prédicteur parfait → Gini fortement positif ✅ | {gini_parfait}")

    def test_sentinelle_signe_predicteur_anticorrele(self):
        """SENT3 — Un prédicteur ANTI-CORRÉLÉ (ordre inversé) doit produire
        un Gini walk-forward FORTEMENT NÉGATIF."""
        np.random.seed(2)
        y_te = np.random.exponential(100, 300)
        pred_anti = -y_te
        gini_anti = self._gini_walk_forward(y_te, pred_anti)
        # Seuil -0.4 (pas -0.5) : marge de sécurité contre la variance
        # d'échantillonnage — l'essentiel du test est le SIGNE (négatif),
        # pas une valeur absolue précise sur un tirage aléatoire donné.
        self.assertLess(
            gini_anti, -0.4,
            f"Prédicteur anti-corrélé donne Gini={gini_anti} — devrait être "
            f"fortement négatif. Régression du bug de signe (audit V6 #2) ?"
        )
        print(f"    SENT3 Prédicteur anti-corrélé → Gini fortement négatif ✅ | {gini_anti}")

    def test_sentinelle_predicteur_aleatoire_proche_zero(self):
        """SENT4 — Un prédicteur indépendant de l'observé doit produire un
        Gini walk-forward proche de zéro (garde-fou complémentaire de calibrage)."""
        np.random.seed(3)
        y_te = np.random.exponential(100, 500)
        pred_alea = np.random.exponential(100, 500)
        gini_alea = self._gini_walk_forward(y_te, pred_alea)
        self.assertLess(
            abs(gini_alea), 0.2,
            f"Prédicteur aléatoire donne Gini={gini_alea} — devrait être proche de 0."
        )
        print(f"    SENT4 Prédicteur aléatoire → Gini proche de 0 ✅ | {gini_alea}")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A6 COMPARAISON v1.0 — SÉLECTION FINALE")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
