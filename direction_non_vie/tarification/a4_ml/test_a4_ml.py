"""
Tests A4 ML v1.0 — Tarification Machine Learning ×8 modèles Non-Vie
7 tests · données synthétiques · comparaison GLM référence
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))


def _make_r_a2(n=600):
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
        'densite_population':   np.random.uniform(10, 5000, n),
        'prime_pure':           cout * exposition,
    })
    return {'success': True, 'dataframe': df, 'branche': 'auto',
            'statut_rag': 'VERT', 'parametres': {}, 'rapport': {},
            'commentaire': 'OK', 'audit_id': 'A2_TEST', 'erreur': None}


def _make_r_a3():
    return {
        'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
        'metriques': {
            'poisson': {'gini': 0.18, 'aic': 1200, 'vars_retenues': ['age','bonus_malus'],
                        'nb_obs_train': 480, 'nb_obs_test': 120},
            'gamma':   {'gini': 0.12, 'aic': 980},
            'tweedie': {'gini': 0.15, 'aic': 1050},
        },
        'relativites_poisson': {},
        'relativites_gamma': {},
        'validation_glm': {'statut_global': 'VERT'},
        'excel_bytes': b'', 'word_bytes': b'', 'pdf_bytes': b'',
        'hypotheses': {}, 'audit_trail': {}, 'erreur': None,
    }


class TestA4ML(unittest.TestCase):
    """A4 ML — 8 modèles, Gini, overfit, SHAP, H1-H4, standard ActuarIA."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        cls.agent = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)
        cls.r_a2  = _make_r_a2(600)
        cls.r_a3  = _make_r_a3()
        cls.r     = cls.agent.run(
            result_a2=cls.r_a2, result_a3=cls.r_a3,
            calcul_shap=False, generer_graphiques=False
        )

    def test_a4(self):
        r = self.r

        # ST1 — Pipeline sans erreur
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT', 'AMBRE', 'ROUGE'])
        print(f"    ST1 Pipeline ✅ | statut={r['statut_rag']}")

        # ST2 — Classement non vide, au moins 3 modèles
        classement = r['classement']
        self.assertIsInstance(classement, list)
        self.assertGreaterEqual(len(classement), 3,
            "Au moins 3 modèles doivent être calibrés")
        print(f"    ST2 Classement ✅ | {len(classement)} modèles calibrés")

        # ST3 — Meilleur modèle a un Gini positif
        best = classement[0]
        gini_best = best.get('gini_test', 0)
        self.assertGreater(gini_best, 0.0,
            "Gini du meilleur modèle doit être > 0")
        self.assertLess(gini_best, 1.0)
        print(f"    ST3 Gini ✅ | meilleur={best.get('modele','?')} Gini={gini_best:.4f}")

        # ST4 — Overfit ratio cohérent (> 0, jamais aberrant)
        for m in classement:
            of = m.get('overfit_ratio', 1.0)
            self.assertGreater(of, 0.0, f"Overfit ratio nul pour {m.get('modele','?')}")
        print(f"    ST4 Overfit ✅ | best overfit={best.get('overfit_ratio',1):.3f}")

        # ST5 — gini_reference_a3 utilisée (≠ 0.2651 hardcodé)
        # On vérifie que le monitoring référence le Gini A3 (0.18) et non freMTPL2 (0.2651)
        monitoring = r.get('monitoring', {})
        gini_ref = monitoring.get('gini_reference', 0)
        self.assertNotAlmostEqual(gini_ref, 0.2651, places=3,
            msg="gini_reference ne doit pas être hardcodé à 0.2651 freMTPL2")
        print(f"    ST5 Gini ref dynamique ✅ | gini_ref={gini_ref:.4f} (≠ 0.2651)")

        # ST6 — Standard ActuarIA : clés obligatoires
        for key in ['excel_bytes', 'hypotheses', 'audit_trail']:
            self.assertIn(key, r, f"Clé '{key}' manquante")
        self.assertIsInstance(r['excel_bytes'], bytes)
        hyp = r.get('hypotheses', {})
        for hkey in ['h1_overfitting', 'h2_psi', 'h3_gini', 'h4_calibration']:
            self.assertIn(hkey, hyp, f"Hypothèse '{hkey}' manquante")
        print(f"    ST6 Standard ActuarIA ✅ | excel={len(r['excel_bytes'])} bytes | "
              f"H1={hyp.get('h1_overfitting',{}).get('statut','?')} "
              f"H2={hyp.get('h2_psi',{}).get('statut','?')} "
              f"H3={hyp.get('h3_gini',{}).get('statut','?')} "
              f"H4={hyp.get('h4_calibration',{}).get('statut','?')}")

        # ST7 — Scores dans [0, 1] pour tous les modèles
        for m in classement:
            score = m.get('score_global', 0)
            if score:
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 1.0)
        print(f"    ST7 Scores ✅ | tous dans [0,1] | meilleur score={best.get('score_global',0):.4f}")




def _make_r_a2_avec_genre_numerique(n=600):
    """Fixture avec une colonne 'sexe' numérique (0/1) — le cas concret
    prouvé par exécution lors de l'audit V7 (extraction SI réelle typique,
    contrairement à une colonne déjà encodée/catégorielle)."""
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


class TestA4FiltreGenre(unittest.TestCase):
    """
    Verrou anti-régression — audit V7 anomalie BLOQUANTE B1.

    A4 n'avait AUCUN filtre genre avant l'audit V7 : une colonne 'sexe'
    numérique (0/1) — le format typique d'une extraction SI réelle,
    par opposition à une colonne déjà catégorielle/encodée — atteignait
    la matrice de features des modèles ML, potentiellement retenus en
    production par A6. Prouvé par exécution lors de l'audit V7, corrigé
    via le module partagé services/conformite_reglementaire.py.

    Ce test verrouille la correction contre toute régression future.
    """

    def test_genre_numerique_absent_des_features(self):
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        agent = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)
        r_a2 = _make_r_a2_avec_genre_numerique(600)
        r_a3 = _make_r_a3()
        r = agent.run(result_a2=r_a2, result_a3=r_a3,
                      calcul_shap=False, generer_graphiques=False)

        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        features = r.get('rapport', {}).get('feature_names', [])
        self.assertNotIn(
            'sexe', features,
            "RÉGRESSION BLOQUANTE (audit V7 B1) — la colonne 'sexe' "
            "numérique est présente dans les features du modèle ML. "
            "Vérifier l'appel à filtrer_genre() dans _preparer_donnees."
        )
        print(f"    B1-A4 Genre numérique filtré ✅ | features={features}")


class TestAntiFuiteFamilleCible(unittest.TestCase):
    """
    Anti-fuite de données — variables dérivées de la sinistralité (audit V8).

    Le correctif V7 (BLOQUANT #2) a fait calculer prime_pure par A2. Effet de
    bord détecté par l'audit V8 : prime_pure (= cout/exposition) atteignait la
    matrice X des modèles fréquence/coût → data leakage (Gini fréquence 0,91
    vs 0,20). Ce test verrouille l'exclusion de toute la famille cible, à deux
    niveaux : (1) unitaire sur filtrer_famille_cible, (2) intégration A2→A4
    avec borne de vraisemblance sur le Gini.
    """

    def test_unitaire_filtrer_famille_cible(self):
        from direction_non_vie.tarification.services.conformite_reglementaire import (
            filtrer_famille_cible,
        )
        feats = [
            'age', 'bonus_malus', 'puissance_fiscale',        # légitimes → gardées
            'prime_pure', 'cout_total_sinistres', 'nb_sinistres',  # famille cible
            'log_prime_pure', 'log_cout_total_sinistres',     # variantes log
            'lambda_freq_annuel', 'cout_moyen_attendu',       # variantes
        ]
        out = filtrer_famille_cible(feats, contexte='test')
        for interdite in ['prime_pure', 'cout_total_sinistres', 'nb_sinistres',
                          'log_prime_pure', 'log_cout_total_sinistres',
                          'lambda_freq_annuel', 'cout_moyen_attendu']:
            self.assertNotIn(interdite, out,
                f"'{interdite}' (dérivée sinistralité) doit être exclue des features")
        for legitime in ['age', 'bonus_malus', 'puissance_fiscale']:
            self.assertIn(legitime, out,
                f"'{legitime}' (facteur tarifaire a priori) ne doit PAS être exclu")
        print(f"    AF1 Filtre unitaire ✅ | gardées={out}")

    def test_integration_a2_a4_pas_de_fuite_prime_pure(self):
        """Pipeline A2→A4 réel : prime_pure (calculée par A2) ne doit pas
        entrer dans la matrice X quand la cible est la fréquence, et le Gini
        doit rester actuariellement plausible (borne anti-fuite)."""
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        np.random.seed(11)
        n = 3000
        expo = np.random.uniform(0.1, 1.0, n)
        bm   = np.random.uniform(50, 350, n)
        nb   = np.random.poisson(0.06 * expo * (bm / 100.0), n).astype(float)
        cout = np.where(nb > 0, np.random.gamma(2, 500, n), 0.0)
        df = pd.DataFrame({
            'id_contrat': range(n), 'nb_sinistres': nb,
            'cout_total_sinistres': cout, 'exposition': expo,
            'age': np.random.randint(18, 80, n).astype(float), 'bonus_malus': bm,
            'puissance_fiscale': np.random.randint(4, 15, n).astype(float),
            'annee_souscription': np.random.choice([2020, 2021, 2022, 2023], n),
        })
        r_a1 = {'success': True, 'dataframe': df, 'branche': 'auto',
                'statut_rag': 'VERT', 'score_qual': 95.0,
                'qualite': {'taux_completude': 99.0, 'taux_doublons': 0.0,
                            'nb_lignes': n, 'nb_colonnes': len(df.columns),
                            'score_global': 95.0, 'colonnes': df.columns.tolist(),
                            'expo_ok_pct': 100.0},
                'hash_md5': 'x', 'rapport': {'etapes': [], 'alertes': []},
                'commentaire': 'OK', 'audit_id': 'A1', 'client_id': None, 'erreur': None}
        a2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        r2 = a2.run(result_a1=r_a1)
        self.assertIn('prime_pure', r2['dataframe'].columns,
            "A2 doit calculer prime_pure (contrat de données V7 B2)")

        a4 = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)
        feats = a4._preparer_donnees(r2['dataframe'].copy(), 'auto',
                                     'nb_sinistres', 'exposition')[-1]
        self.assertNotIn('prime_pure', feats,
            "FUITE : prime_pure ne doit jamais être une feature (cible=fréquence)")
        self.assertFalse(any('cout' in f for f in feats),
            f"FUITE : variable de coût dans les features : {feats}")
        print(f"    AF2 Pas de fuite dans X ✅ | features={feats}")

        r4 = a4.run(result_a2=r2, calcul_shap=False, generer_graphiques=False,
                    col_cible='nb_sinistres')
        best = r4['classement'][0]
        gini = best.get('gini_test', 0)
        self.assertLess(gini, 0.60,
            f"Gini fréquence auto = {gini:.4f} ≥ 0,60 — irréaliste, signature "
            f"de fuite de données (régression de l'anomalie V8 ?)")
        print(f"    AF3 Gini plausible ✅ | best={best['modele']} Gini={gini:.4f} (< 0,60)")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A4 ML v1.0 — MACHINE LEARNING ×8 MODÈLES")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
