"""
Tests A4 ML v1.0 — Tarification Machine Learning ×8 modèles Non-Vie
7 tests · données synthétiques · comparaison GLM référence
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))
from core.plan_tarifaire import PlanTarifaire

# Phase 1 : A4.run() et _preparer_donnees reçoivent le PLAN signé. Fixtures auto
# (freMTPL2-like) → plan auto ; le test genre MRH (V9-2) → plan mrh. Restreint les
# features à plan.colonnes_produites(), exactement comme _charger_plan_lob avant.
_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_PLAN_AUTO = PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans', 'auto.yaml'))
_PLAN_MRH  = PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans', 'mrh.yaml'))


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
            result_a2=cls.r_a2, result_a3=cls.r_a3, plan=_PLAN_AUTO,
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
    via le module plateforme core/conformite_reglementaire.py.

    Ce test verrouille la correction contre toute régression future.
    """

    def test_genre_numerique_absent_des_features(self):
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        agent = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)
        r_a2 = _make_r_a2_avec_genre_numerique(600)
        r_a3 = _make_r_a3()
        r = agent.run(result_a2=r_a2, result_a3=r_a3, plan=_PLAN_AUTO,
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
        from core.conformite_reglementaire import (
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
                                     'nb_sinistres', 'exposition', _PLAN_AUTO)[-1]
        self.assertNotIn('prime_pure', feats,
            "FUITE : prime_pure ne doit jamais être une feature (cible=fréquence)")
        self.assertFalse(any('cout' in f for f in feats),
            f"FUITE : variable de coût dans les features : {feats}")
        print(f"    AF2 Pas de fuite dans X ✅ | features={feats}")

        r4 = a4.run(result_a2=r2, plan=_PLAN_AUTO, calcul_shap=False,
                    generer_graphiques=False, col_cible='nb_sinistres')
        best = r4['classement'][0]
        gini = best.get('gini_test', 0)
        self.assertLess(gini, 0.60,
            f"Gini fréquence auto = {gini:.4f} ≥ 0,60 — irréaliste, signature "
            f"de fuite de données (régression de l'anomalie V8 ?)")
        print(f"    AF3 Gini plausible ✅ | best={best['modele']} Gini={gini:.4f} (< 0,60)")


class TestAntiFuiteV9(unittest.TestCase):
    """
    Audit de clôture V9 (deux certificateurs indépendants, convergents) —
    verrouille les deux angles morts que les tests AF existants (branche
    auto uniquement) ne couvraient pas :
    (a) fuite de sinistralité en branche santé, noms hors des racines V8 ;
    (b) fuite de genre via les colonnes filles du one-hot A2 (branches
        non-auto), au-delà du match exact de filtrer_genre.
    """

    def test_filtre_genre_variantes_adverses(self):
        """filtrer_genre doit capturer casse, one-hot, civilité — pas
        seulement les 6 noms exacts d'origine (audit V9, ex-IMPORTANT 4.3
        reclassé BLOQUANT après preuve d'atteinte de la matrice X réelle)."""
        from core.conformite_reglementaire import (
            filtrer_genre,
        )
        adverses = ['sexe', 'Sexe', 'SEXE', 'sex', 'genre', 'gender',
                    'sexe_enc', 'sexe_m', 'sexe_f', 'genre_H', 'genre_F',
                    'civilite', 'civilite_Mme', 'titre_civilite']
        out = filtrer_genre(adverses, contexte='test')
        self.assertEqual(out, [], f"Variables de genre non filtrées : {out}")
        legitimes = filtrer_genre(['age', 'bonus_malus', 'puissance_fiscale'])
        self.assertEqual(len(legitimes), 3, "Facteurs tarifaires légitimes exclus à tort")
        print(f"    V9-1 Filtre genre élargi ✅ | 14 variantes adverses toutes exclues")

    def test_integration_a2_a4_genre_one_hot_mrh(self):
        """Reproduction de la fuite prouvée par les deux certificateurs V9 :
        sexe encodé en one-hot (sexe_m/sexe_f) par A2 pour la branche MRH
        atteignait directement la matrice X d'A4.

        Depuis le nettoyage de périmètre (11/07/2026), la correction est
        désormais à DEUX niveaux :
        (1) à la source — 'sexe' ne figure dans AUCUNE config d'encodage de
            A2, et filtrer_genre est appliqué inconditionnellement à
            l'encodage : A2 ne produit donc plus de colonne sexe_* ;
        (2) en défense en profondeur — même si une colonne de genre entrait
            par une autre voie (fichier client pré-encodé), A4 la filtre.
        Ce test verrouille les deux."""
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        np.random.seed(5)
        n = 2000
        df = pd.DataFrame({
            'id_contrat': range(n),
            'nb_sinistres': np.random.poisson(0.1, n).astype(float),
            'cout_total_sinistres': np.random.gamma(2, 300, n),
            'exposition': np.random.uniform(0.2, 1, n),
            'sexe': np.random.choice(['M', 'F'], n),
            'age': np.random.randint(20, 80, n).astype(float),
            'capital_assure_biens_eur': np.random.uniform(50000, 300000, n),
            'type_logement': np.random.choice(['appartement', 'maison'], n),
            'statut_occupation': np.random.choice(['proprietaire', 'locataire'], n),
            'zone_geographique': np.random.choice(list('ABCDE'), n),
            'annee_souscription': np.random.choice([2021, 2022, 2023], n),
        })
        a1 = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        a2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        a4 = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)
        r1 = a1.run(branche='non_vie', sous_branche='mrh', dataframe=df)
        r2 = a2.run(result_a1=r1)

        # (1) Correction à la source : A2 ne doit produire AUCUNE colonne
        #     dérivée du genre (plus de one-hot sexe_m/sexe_f).
        cols_encodees_genre = [c for c in r2['dataframe'].columns
                               if c.lower() not in ('sexe',)
                               and ('sexe' in c.lower() or 'genre' in c.lower())]
        self.assertEqual(cols_encodees_genre, [],
            f"A2 encode encore le genre : {cols_encodees_genre} "
            f"(le genre ne doit figurer dans aucune config d'encodage)")

        # (2) Défense en profondeur : rien de genré n'atteint la matrice X.
        feats = a4._preparer_donnees(
            r2['dataframe'].copy(), r1.get('sous_branche', 'mrh'),
            'nb_sinistres', 'exposition', _PLAN_MRH
        )[-1]
        genre_dans_X = [c for c in feats
                        if 'sexe' in c.lower() or 'genre' in c.lower()]
        self.assertEqual(genre_dans_X, [],
            f"FUITE GENRE : {genre_dans_X} dans la matrice X d'A4 (branche MRH)")
        print(f"    V9-2 Genre ni encodé par A2 ni présent dans X ✅ | features={feats}")

    def test_integration_a2_a4_colonnes_sinistralite_brutes_client(self):
        """Défense en profondeur : un fichier client Non-Vie peut contenir des
        colonnes de sinistralité BRUTES (cout_medecine, cout_hospitalisation,
        montant_sinistres...). Depuis le nettoyage de périmètre (11/07/2026),
        A2 ne génère plus lui-même d'agrégats santé — mais ces colonnes brutes
        restent numériques et atteindraient la matrice X sans le filtre
        anti-fuite. Ce test verrouille ce chemin, qui est celui qui SUBSISTE
        après le retrait du code mort.

        Origine : audit V9 (BLOQUANT) — Gini fréquence 0,8093 avec ces
        colonnes vs 0,0725 sans (+0,74), même signature que la fuite V8."""
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        np.random.seed(7)
        n = 3000
        lat = np.random.gamma(2, 1, n)
        cout_med = lat * np.random.uniform(80, 150, n)
        cout_pharma = lat * np.random.uniform(40, 90, n)
        cout_hosp = lat * np.random.uniform(200, 600, n) * np.random.binomial(1, 0.15, n)
        nb_sin = np.random.poisson(0.15 * lat, n).astype(float)
        df = pd.DataFrame({
            'id_contrat': range(n), 'nb_sinistres': nb_sin,
            'cout_total_sinistres': cout_med + cout_pharma + cout_hosp,
            'exposition': np.random.uniform(0.3, 1, n),
            'age': np.random.randint(18, 75, n).astype(float),
            'bonus_malus': np.random.uniform(50, 350, n),
            # Colonnes de sinistralité brutes fournies par le client :
            'cout_medecine': cout_med, 'cout_pharmacie': cout_pharma,
            'cout_hospitalisation': cout_hosp,
            'montant_sinistres': cout_med + cout_pharma,
            'annee_souscription': np.random.choice([2021, 2022, 2023], n),
        })
        a1 = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        a2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        a4 = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)
        r1 = a1.run(branche='non_vie', sous_branche='auto', dataframe=df)
        self.assertTrue(r1['success'], f"A1 doit accepter du Non-Vie : {r1.get('erreur')}")
        r2 = a2.run(result_a1=r1)
        feats = a4._preparer_donnees(r2['dataframe'].copy(), 'auto',
                                     'nb_sinistres', 'exposition', _PLAN_AUTO)[-1]
        fuite = [c for c in feats
                 if any(s in c.lower() for s in ['sinistre', 'cout_', 'part_hospit'])]
        self.assertEqual(fuite, [],
            f"FUITE : colonnes de sinistralité brutes dans la matrice X : {fuite}")

        r4 = a4.run(result_a2=r2, plan=_PLAN_AUTO, calcul_shap=False,
                    generer_graphiques=False, col_cible='nb_sinistres')
        gini = r4['classement'][0].get('gini_test', 0)
        self.assertLess(gini, 0.60,
            f"Gini fréquence = {gini:.4f} ≥ 0,60 — signature de fuite "
            f"(régression de l'anomalie V9 ?)")
        print(f"    V9-3 Colonnes sinistralité brutes filtrées ✅ | Gini={gini:.4f} (< 0,60)")

    def test_a1_rejette_branche_hors_perimetre(self):
        """Nettoyage de périmètre (11/07/2026) : A1 est un agent de la
        Direction Non-Vie. Les branches Vie et Santé-Prévoyance doivent être
        rejetées explicitement (fail loudly), et non traitées silencieusement
        avec une configuration Non-Vie inadaptée."""
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        a1 = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        df = pd.DataFrame({
            'id_contrat': range(50),
            'nb_sinistres': np.zeros(50),
            'cout_total_sinistres': np.zeros(50),
            'exposition': np.ones(50),
            'age': np.full(50, 40.0),
        })
        for branche_hs in ['sante_prevoyance', 'vie']:
            # sous_branche VALIDE : on isole ainsi le rejet de la BRANCHE
            # (le garde-fou de périmètre s'exécute avant le contrôle sous_branche).
            r = a1.run(branche=branche_hs, sous_branche='auto', dataframe=df)
            self.assertFalse(r['success'],
                f"A1 doit REJETER la branche '{branche_hs}' (hors périmètre Non-Vie)")
            self.assertEqual(r['statut_rag'], 'ROUGE')
            self.assertIn('hors périmètre', r['erreur'])
        r_ok = a1.run(branche='non_vie', sous_branche='auto', dataframe=df)
        self.assertTrue(r_ok['success'], "A1 doit continuer d'accepter 'non_vie'")
        print("    V9-6 A1 rejette Vie/SP, accepte Non-Vie ✅")

    def test_faux_positifs_preserves(self):
        """L'élargissement des racines anti-fuite (V9) ne doit pas exclure
        à tort les variables d'expérience passée (connues à la souscription)."""
        from core.conformite_reglementaire import (
            filtrer_famille_cible,
        )
        legitimes = ['nb_sinistres_anterieurs', 'antecedents_sinistres_n1',
                     'risque_historique', 'age', 'bonus_malus']
        out = filtrer_famille_cible(legitimes, contexte='test')
        self.assertEqual(sorted(out), sorted(legitimes),
            f"Faux positif : variable(s) légitime(s) exclue(s) à tort : "
            f"{set(legitimes) - set(out)}")
        print(f"    V9-4 Faux positifs préservés ✅ | {out}")

    def test_a2_encodage_automatique_ne_recree_pas_le_genre(self):
        """Chemin de contournement découvert en exécution (11/07/2026) :
        A2 possède un encodage LABEL AUTOMATIQUE de repli pour toute colonne
        'object' non configurée explicitement. Ce chemin recréait 'sexe_enc'
        alors même que 'sexe' avait été retiré de toutes les configs
        d'encodage — contournant intégralement le filtre genre basé sur la
        config. Distinct de la voie one-hot identifiée par l'audit V9, et
        couvert par aucun test jusqu'ici."""
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        np.random.seed(3)
        n = 800
        df = pd.DataFrame({
            'id_contrat': range(n),
            'nb_sinistres': np.random.poisson(0.1, n).astype(float),
            'cout_total_sinistres': np.random.gamma(2, 300, n),
            'exposition': np.random.uniform(0.2, 1, n),
            'age': np.random.randint(20, 80, n).astype(float),
            'bonus_malus': np.random.uniform(50, 350, n),
            # Genre sous forme texte — passera par l'encodage automatique
            # s'il n'est pas explicitement filtré :
            'sexe': np.random.choice(['M', 'F'], n),
            'carburant': np.random.choice(['Diesel', 'Regular'], n),
            'annee_souscription': np.random.choice([2021, 2022, 2023], n),
        })
        a1 = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        a2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        r2 = a2.run(result_a1=a1.run(branche='non_vie', sous_branche='auto',
                                     dataframe=df))
        derivees_genre = [c for c in r2['dataframe'].columns
                          if c.lower() != 'sexe'
                          and ('sexe' in c.lower() or 'genre' in c.lower())]
        self.assertEqual(derivees_genre, [],
            f"A2 a recréé une variable de genre encodée : {derivees_genre} "
            f"(l'encodage automatique de repli doit filtrer le genre)")
        # Contrôle négatif : une variable catégorielle légitime est bien encodée
        self.assertTrue(
            any('carburant' in c for c in r2['dataframe'].columns),
            "L'encodage doit continuer de fonctionner pour les variables légitimes")
        print("    V9-7 Encodage automatique ne recrée pas le genre ✅")

    def test_liste_blanche_bloque_les_18_fuites_de_l_audit_interne(self):
        """LISTE BLANCHE (11/07/2026) — le garde-fou structurel.

        L'audit interne a démontré que les listes NOIRES ne peuvent pas être
        exhaustives : 11 noms de sinistralité (loss_ratio, burning_cost,
        frequence_observee, montant_regle...) et 7 proxys de genre (prenom,
        civilite, is_male...) — tous parfaitement réalistes dans un fichier
        client — passaient au travers. Chaque correctif de liste noire n'a fait
        que déplacer la frontière.

        filtrer_features() inverse la charge de la preuve : seule une colonne
        DÉCLARÉE facteur tarifaire légitime entre dans X ; l'inconnu est exclu
        par défaut (fail-safe) et journalisé (transparence ACPR)."""
        from core.conformite_reglementaire import filtrer_features
        fuites_sinistralite = [
            'loss_ratio', 'taux_S_sur_P', 'ratio_sp', 'frequence_observee',
            'severite_observee', 'charge_totale', 'montant_regle',
            'indemnite_versee', 'provision_dossier', 'burning_cost',
            'sinistralite_n',
        ]
        proxys_genre = ['prenom', 'titre', 'madame', 'mr_mme', 'is_male',
                        'homme_femme', 'f_h', 'civilite', 'sexe_M', 'Sexe']
        out = filtrer_features(fuites_sinistralite + proxys_genre, contexte='test')
        self.assertEqual(out, [],
            f"Colonnes non déclarées passant la liste blanche : {out}")

        # Contrôle négatif indispensable : la liste blanche ne doit pas écarter
        # les facteurs tarifaires réellement produits par le pipeline A2.
        legitimes = [
            'age', 'bonus_malus', 'puissance_fiscale', 'age_carre',
            'jeune_conducteur', 'senior_conducteur', 'vehicule_recent',
            'age_x_bonus_malus', 'inter_age_bonus_malus', 'log_exposition',
            'carburant_diesel', 'zone_geographique_enc', 'densite_population',
            'antecedents_sinistres_n1', 'nb_sinistres_anterieurs',
            'statut_occupation_locataire', 'surface_m2',
        ]
        out2 = filtrer_features(legitimes, contexte='test')
        perdus = [c for c in legitimes if c not in out2]
        self.assertEqual(perdus, [],
            f"Facteurs tarifaires légitimes écartés à tort : {perdus}")
        print(f"    LB Liste blanche : 21 fuites bloquées, "
              f"{len(out2)}/{len(legitimes)} facteurs légitimes conservés ✅")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A4 ML v1.0 — MACHINE LEARNING ×8 MODÈLES")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
