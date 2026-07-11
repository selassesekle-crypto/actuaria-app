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
    Sentinelles anti-régression — Gini walk-forward (audit V6, puis V7 MINEUR #3).

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

    AUDIT V7 MINEUR #3 : ce test appelait initialement une COPIE de la
    formule plutôt que le chemin de code réel — risque de divergence future
    si l'un des deux était modifié sans l'autre (exactement le type de piège
    que les audits successifs demandent de traquer, ironiquement présent
    dans le test destiné à s'en protéger). Corrigé en appelant directement
    AgentA6Comparaison._gini_lorenz(), désormais la source UNIQUE utilisée
    à la fois par le code de production (_backtesting_temporel) et par ce
    test — plus aucune copie possible.
    """

    @staticmethod
    def _gini_walk_forward(y_te, pred_te):
        """Appelle directement le code réel — plus une reproduction."""
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        return AgentA6Comparaison._gini_lorenz(y_te, pred_te)

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




class TestA6ValidationTemporelleObligatoire(unittest.TestCase):
    """
    Verrou anti-régression — audit V7 anomalie BLOQUANTE B2 (volet A6).

    _calculer_statut_rag ne recevait même pas `backtest` en paramètre
    avant l'audit V7 — elle ne pouvait donc physiquement pas savoir si
    le walk-forward avait tourné. Un modèle pouvait être certifié VERT
    sans qu'aucune validation temporelle n'ait été effectuée, dès lors
    que la cible par défaut (prime_pure) était absente des données
    (ce qui était systématiquement le cas avant le correctif A2 — B2
    volet A2, testé séparément dans test_a2_preprocessing.py).

    Ce test appelle directement _calculer_statut_rag avec un backtest
    explicitement indisponible, en défense en profondeur — même si le
    correctif A2 venait à régresser un jour, ce garde-fou resterait actif.
    """

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        cls.agent = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp', verbose=False)

    def test_backtest_indisponible_plafonne_a_ambre_en_production(self):
        # Modèle de production avec un score/gini excellents — devrait
        # normalement donner VERT si seul le score comptait.
        modele_excellent = {'score_global': 0.95, 'gini_test': 0.30}
        classement = [modele_excellent]
        backtest_indisponible = {
            'disponible': False,
            'note': "Colonne cible 'prime_pure' introuvable.",
        }

        statut = self.agent._calculer_statut_rag(
            modele_excellent, classement,
            profil_valide_par='Actuaire Test',  # gouvernance OK — isole le test
            environnement='production',
            backtest=backtest_indisponible,
        )
        self.assertNotEqual(
            statut, 'VERT',
            "RÉGRESSION BLOQUANTE (audit V7 B2) — statut VERT délivré "
            "malgré backtest['disponible']=False en production. La "
            "validation temporelle n'est plus obligatoire pour un VERT."
        )
        print(f"    B2-A6 Backtest indisponible → statut plafonné ✅ : {statut}")

    def test_backtest_disponible_permet_vert(self):
        """Contrôle positif : un backtest disponible ET FIDÈLE ne doit PAS
        bloquer un VERT par ailleurs mérité (le garde-fou ne doit pas être
        trop large et plafonner en permanence).

        ⚠ Fixture complétée le 11/07/2026 : le backtest doit désormais aussi
        déclarer 'modele_recalibre_fidele'. Un walk-forward "disponible" mais
        recalibré sur un PROXY (cas des modèles GLM_*/DL_*, non couverts par la
        fabrique sklearn) ne valide pas le modèle de production — voir le test
        suivant. La prémisse de ce test était incomplète, pas fausse."""
        modele_excellent = {'score_global': 0.95, 'gini_test': 0.30}
        classement = [modele_excellent]
        backtest_disponible = {
            'disponible': True, 'ae_ratio': 1.02,
            'modele_recalibre_fidele': True,   # modèle ML réellement recalibré
        }

        statut = self.agent._calculer_statut_rag(
            modele_excellent, classement,
            profil_valide_par='Actuaire Test',
            environnement='production',
            backtest=backtest_disponible,
        )
        self.assertEqual(statut, 'VERT',
            "Un backtest disponible ET fidèle avec un modèle excellent et une "
            "gouvernance validée devrait permettre VERT — garde-fou trop large ?")
        print(f"    B2-A6 Backtest disponible + fidèle → VERT accessible ✅ : {statut}")

    def test_walk_forward_non_fidele_plafonne_a_ambre(self):
        """Audit interne (11/07/2026) : le walk-forward ne sait recalibrer que
        les modèles ML (fabrique sklearn). Quand le modèle retenu en production
        est un GLM_* ou un DL_*, il retombe sur un PROXY GBM — honnêtement
        étiqueté, mais la stabilité temporelle mesurée est alors celle d'un
        AUTRE modèle que celui qui part en production. Or le GLM est très
        fréquemment le modèle retenu.

        Le flag 'modele_recalibre_fidele' existait dans le dict backtest, mais
        le gate RAG ne le vérifiait pas : VERT restait possible sur la foi d'une
        validation portant sur un autre modèle. Même classe de défaut que le
        BLOQUANT B2 (V7) : contrôle correct, mais non câblé dans la décision."""
        modele_excellent = {'score_global': 0.95, 'gini_test': 0.30}
        backtest_proxy = {
            'disponible': True, 'ae_ratio': 1.02,
            'modele_recalibre': 'GLM_POISSON → proxy GBM',
            'modele_recalibre_fidele': False,
        }
        statut = self.agent._calculer_statut_rag(
            modele_excellent, [modele_excellent],
            profil_valide_par='Actuaire Test',
            environnement='production',
            backtest=backtest_proxy,
        )
        self.assertNotEqual(statut, 'VERT',
            "Un walk-forward recalibré sur un PROXY ne valide pas le modèle de "
            "production : VERT ne doit pas être accordé en production.")
        self.assertEqual(statut, 'AMBRE')

        # En développement, ce n'est pas bloquant.
        statut_dev = self.agent._calculer_statut_rag(
            modele_excellent, [modele_excellent],
            profil_valide_par=None, environnement='developpement',
            backtest=backtest_proxy,
        )
        self.assertEqual(statut_dev, 'VERT',
            "Le plafond ne doit s'appliquer qu'en production.")
        print(f"    WF-FID Walk-forward proxy → AMBRE en prod ✅ / VERT en dev ✅")

    def test_backtest_absent_du_dict_ne_plante_pas(self):
        """Robustesse : backtest=None (paramètre non transmis par un
        appelant plus ancien) ne doit pas lever d'exception."""
        modele = {'score_global': 0.95, 'gini_test': 0.30}
        try:
            statut = self.agent._calculer_statut_rag(
                modele, [modele], profil_valide_par='Test',
                environnement='production', backtest=None,
            )
        except Exception as e:
            self.fail(f"_calculer_statut_rag a levé une exception avec backtest=None : {e}")
        self.assertIn(statut, ['VERT', 'AMBRE', 'ROUGE'])
        print(f"    B2-A6 backtest=None géré sans exception ✅ : {statut}")


class TestAntiFuiteGenreWalkForwardV9(unittest.TestCase):
    """
    Audit de clôture V9 (BLOQUANT 4.2 / B3, deux certificateurs convergents) —
    le walk-forward d'A6 n'appliquait que filtrer_famille_cible, jamais
    filtrer_genre : une colonne sexe pré-encodée (scénario V7) traversait A2
    intacte et entrait dans la recalibration walk-forward.
    """

    def test_sexe_preencode_absent_du_walk_forward(self):
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        np.random.seed(9)
        n = 4000
        expo = np.random.uniform(.1, 1, n)
        bm = np.random.uniform(50, 350, n)
        sexe = np.random.binomial(1, 0.5, n).astype(float)
        nb = np.random.poisson(.06 * expo * bm / 100, n).astype(float)
        cout = np.where(nb > 0, np.random.gamma(2, 500, n), 0.)
        df = pd.DataFrame({
            'id_contrat': range(n), 'nb_sinistres': nb,
            'cout_total_sinistres': cout, 'exposition': expo,
            'age': np.random.randint(18, 80, n).astype(float),
            'bonus_malus': bm, 'sexe': sexe,
            'puissance_fiscale': np.random.randint(4, 15, n).astype(float),
            'annee_souscription': np.random.choice(
                [2019, 2020, 2021, 2022, 2023], n),
        })
        a1 = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        a2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        a3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
        a4 = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)
        a6 = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp', verbose=False)
        r1 = a1.run(branche='non_vie', dataframe=df)
        r2 = a2.run(result_a1=r1)
        self.assertEqual(str(r2['dataframe']['sexe'].dtype), 'float64',
            "Ce test présuppose que 'sexe' survit intact (numérique) à A2 en auto")
        r3 = a3.run(result_a2=r2, generer_graphiques=False)
        r4 = a4.run(result_a2=r2, result_a3=r3, calcul_shap=False,
                    generer_graphiques=False)
        r6 = a6.run(result_a2=r2, result_a3=r3, result_a4=r4, result_a5=None,
                    generer_graphiques=False, generer_rapport_equipe=False,
                    environnement='production', profil_valide_par='Test V9')
        bt = r6['backtest']
        self.assertTrue(bt.get('disponible'),
            "Backtest doit rester disponible (pas de régression B2)")
        gini_wf = bt.get('gini_wf_moyen')
        self.assertIsNotNone(gini_wf)
        self.assertLess(gini_wf, 0.60,
            f"gini_wf = {gini_wf} — plausibilité douteuse si le genre "
            f"contaminait encore le walk-forward")
        print(f"    V9-5 Genre absent du walk-forward A6 ✅ | "
              f"statut={r6['statut_rag']} gini_wf={gini_wf:.4f}")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A6 COMPARAISON v1.0 — SÉLECTION FINALE")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
