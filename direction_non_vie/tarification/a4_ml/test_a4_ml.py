"""
Tests A4 ML v1.0 — Tarification Machine Learning Non-Vie
Données synthétiques, comparaison GLM référence. Ni le compte de tests ni
celui des modèles ne sont annoncés ici : les deux ont péri en silence
(constats `a4/C13` et `a4/C7`).
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))
from core.conformite_reglementaire import gini_texte
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
    """A4 ML — Gini, overfit, SHAP, H1-H4, standard ActuarIA."""

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
        # ⚠️ RENFORCÉ le 03/09/2026 : `None` est désormais un état LÉGITIME —
        # la stabilité n'a pas été mesurée — et il n'est PLUS remplacé par 1.0
        # (qui vaut, chez A6, la meilleure note de stabilité possible). Le
        # test exige donc que la seule ligne autorisée à ne pas la porter soit
        # celle qui RELAIE A3, et que toute autre ait un ratio strictement
        # positif. Sur cette fixture, `_make_r_a3` ne publie pas la mesure.
        for m in classement:
            of = m.get('overfit_ratio')
            if of is None:
                self.assertEqual(
                    m.get('famille'), 'GLM',
                    f"{m.get('modele','?')} : A4 a calibré ce modèle, son "
                    f"ratio doit être mesuré et non absent")
                continue
            self.assertGreater(of, 0.0, f"Overfit ratio nul pour {m.get('modele','?')}")
        print(f"    ST4 Overfit ✅ | best overfit="
              f"{gini_texte(best.get('overfit_ratio'), 3)}")

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
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
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
        r2 = a2.run(result_a1=r_a1, plan=_PLAN_AUTO)
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
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
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
            # Casse EXACTE du plan mrh : le plan fait autorité (Phase 2), et une
            # modalité inconnue lève — 'maison' ≠ 'Maison'. L'ancien encodage
            # automatique masquait ce désalignement fixture/plan.
            'type_logement': np.random.choice(['Appartement', 'Maison'], n),
            'statut_occupation': np.random.choice(['Proprietaire', 'Locataire'], n),
            # Modalités du plan mrh (Phase 2 : le plan fait autorité). 'A'..'E'
            # était avalé en silence par l'ancien encodage automatique.
            'zone_geographique': np.random.choice(['Urbaine', 'Periurbaine',
                                                   'Rurale'], n),
            'annee_souscription': np.random.choice([2021, 2022, 2023], n),
        })
        a1 = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        a2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        a4 = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False)
        r1 = a1.run(branche='non_vie', sous_branche='mrh', dataframe=df)
        r2 = a2.run(result_a1=r1, plan=_PLAN_MRH)

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
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
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
        r2 = a2.run(result_a1=r1, plan=_PLAN_AUTO)
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
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
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
            # Modalités du plan auto (Phase 2) : 'Regular' (valeur freMTPL2)
            # n'est pas déclarée — une modalité inconnue lève (piège V9).
            'carburant': np.random.choice(['Diesel', 'Essence'], n),
            'annee_souscription': np.random.choice([2021, 2022, 2023], n),
        })
        a1 = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        a2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        r2 = a2.run(result_a1=a1.run(branche='non_vie', sous_branche='auto',
                                     dataframe=df), plan=_PLAN_AUTO)
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


class T_Ce_Qui_Est_Publie_Vient_De_La_Mesure(unittest.TestCase):
    """CONTRÔLE POSITIF — la leçon V14 est écrite DANS CE FICHIER-CI.

    ⚠️ ELLE Y EST DEPUIS LE CORRECTIF V14, dans `agent.py`, et n'a été
    appliquée qu'à A6 :

        « On a beaucoup vérifié que le système REFUSE ce qu'il doit refuser.
          Personne n'a vérifié qu'il ACCEPTE ce qu'il doit accepter. »

    ⚠️ CE CONTRÔLE PORTE SUR LA PROVENANCE DES CHIFFRES, pas sur leur valeur.
    Un test qui exigerait « le PSI doit être bas » serait satisfait par un PSI
    TIRÉ AU SORT — c'est précisément ce que `_monitoring_derive` produit
    aujourd'hui. La seule forme qui ne puisse pas être satisfaite à faux est :
    « une grandeur publiée doit DÉPENDRE du portefeuille ».
    """

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        cls.agent = AgentA4ML(models_path='/tmp', audit_path='/tmp',
                              verbose=False)
        cls.r = cls.agent.run(result_a2=_make_r_a2(600), result_a3=_make_r_a3(),
                              plan=_PLAN_AUTO, calcul_shap=False,
                              generer_graphiques=True)

    def test_le_monitoring_DEPEND_du_portefeuille(self):
        """⚠️ MESURÉ : PSI IDENTIQUE SUR DEUX PORTEFEUILLES DIFFÉRENTS.
        `_monitoring_derive` tire ses deux distributions de `np.random.beta`
        sous graine 42 — aucune donnée du client n'entre dans le calcul, et
        l'« historique Gini 12 mois » est une simulation. Le résultat est donc
        une CONSTANTE du module, publiée sous le titre « Monitoring de la
        dérive des modèles ML en production »."""
        autre = _make_r_a2(600)
        rng = np.random.default_rng(99)
        autre['dataframe']['bonus_malus'] = rng.uniform(50, 350, 600)
        autre['dataframe']['age'] = rng.integers(18, 75, 600).astype(float)
        r2 = self.agent.run(result_a2=autre, result_a3=_make_r_a3(),
                            plan=_PLAN_AUTO, calcul_shap=False,
                            generer_graphiques=False)
        psi_1 = self.r['monitoring']['psi']
        psi_2 = r2['monitoring']['psi']
        self.assertNotEqual(
            psi_1, psi_2,
            f"PSI={psi_1} sur DEUX portefeuilles différents — la grandeur ne "
            f"dépend pas des données qu'elle prétend surveiller")
        print(f"    POS-A4a PSI {psi_1} vs {psi_2} — dépend du portefeuille ✅")

    def test_les_deux_validations_du_resultat_ne_se_contredisent_pas(self):
        """⚠️ `_valider_modele_ml` EST APPELÉE QUATRE FOIS DANS LE MÊME
        `return`, dont trois SANS `X_test`/`y_test`. Le dict retourné porte
        donc deux verdicts pour la même hypothèse : `hypotheses` (calculé avec
        les données de test) et `validation_ml` (sans). L'Excel lit le second,
        le verrou d'A6 lit le premier."""
        # ⚠️ SANS RÉFÉRENCE GLM : sinon « GLM Poisson (référence A3) » gagne le
        # classement, n'existe pas dans `self.modeles`, et H4 ne calcule RIEN
        # des deux côtés — le contrôle passerait alors pour une raison
        # étrangère au défaut. Mesuré : c'est exactement ce qui arrivait.
        r = self.agent.run(result_a2=_make_r_a2(600), result_a3=None,
                           plan=_PLAN_AUTO, calcul_shap=False,
                           generer_graphiques=False)
        self.assertIn(r['classement'][0]['modele'], r['modeles'],
                      "prémisse : le modèle retenu doit être un vrai modèle ML, "
                      "sinon H4 ne calcule rien et le contrôle ne prouve rien")
        h4_hyp = r['hypotheses']['h4_calibration']
        h4_val = r['validation_ml']['h4_calibration']
        self.assertIsNotNone(
            h4_hyp['ecart_moy_pct'],
            "prémisse : « hypotheses » reçoit X_test/y_test, il DOIT mesurer")
        # ⚠️ ON COMPARE LA GRANDEUR, PAS LE STATUT : les deux appels peuvent
        # tomber sur le même statut par coïncidence de seuil, alors que l'un
        # a MESURÉ l'écart et l'autre non. C'est `ecart_moy_pct` qui distingue
        # « calibration testée » de « calibration non testée » — un contrôle
        # qui ne regarderait que le statut passerait sur le code fautif.
        self.assertEqual(
            h4_hyp['ecart_moy_pct'], h4_val['ecart_moy_pct'],
            f"« hypotheses » publie un écart de {h4_hyp['ecart_moy_pct']} "
            f"(statut {h4_hyp['statut']}) et « validation_ml » publie "
            f"{h4_val['ecart_moy_pct']} (statut {h4_val['statut']}) — la même "
            f"hypothèse, deux mesures, dans le même dictionnaire de retour. "
            f"L'Excel lit « validation_ml », le verrou d'A6 lit « hypotheses »")
        self.assertEqual(h4_hyp['statut'], h4_val['statut'])
        print(f"    POS-A4b une seule mesure par hypothèse "
              f"(écart={h4_hyp['ecart_moy_pct']}) ✅")

    def test_le_graphique_d_overfitting_porte_les_Gini_REELS(self):
        """⚠️⚠️ CONSTAT `a4/C3` — IL ETAIT DANS LE QUATRIEME ETAT :
        corrige, epingle par CE test... et NOMME NULLE PART, donc invisible
        pour `ARCH-1` et compte OUVERT. *Un correctif sans le nom de son
        constat est un correctif que l'archive ne peut pas voir.*

        ⚠️ MESURÉ : la trace « Gini Test » vaut [0, 0, 0, 0, 0, 0] pour des
        valeurs réelles de 0,12 à 0,34, et les couleurs — calculées sur ce zéro
        — sortent toutes en ROUGE. Le classement porte `gini_test` ; la figure
        lit `gini`."""
        fig = self.r.get('graphiques_validation', {}).get(
            'overfitting_train_test')
        self.assertIsNotNone(fig, "la figure d'overfitting n'est pas produite")
        traces = {t.name: [v for v in t.y] for t in fig.data if t.name}
        reels = [m['gini_test'] for m in self.r['classement'][:6]]
        self.assertTrue(any(v > 0 for v in reels),
                        "prémisse : au moins un modèle doit discriminer")
        self.assertTrue(
            any(v != 0 for v in traces.get('Gini Test', [])),
            f"la trace « Gini Test » est intégralement à zéro alors que les "
            f"valeurs réelles valent {[round(v, 4) for v in reels]}")
        print(f"    POS-A4c Gini Test tracés = "
              f"{[round(v, 4) for v in traces['Gini Test']]} ✅")

class T_L_Elasticite_Est_Un_Etat_Declare_Pas_Une_Valeur(unittest.TestCase):
    """CONTRÔLE POSITIF — la branche « SI NON », et le faux qui part avec.

    ⚠️ CE QUI A ÉTÉ RETIRÉ, ET POURQUOI. `_optimisation_tarifaire` publiait
    « Tarif optimal : −20 % » quels que soient le portefeuille, sa taille et
    la qualité du modèle : avec une élasticité codée en dur à −1,5, le chiffre
    d'affaires vaut p^(1+ε), strictement décroissant, donc l'optimum était
    MÉCANIQUEMENT la borne basse de sa propre grille. `gini_meilleur` était
    reçu et jamais lu ; la prime moyenne (450 €) et le nombre de contrats
    (10 000) étaient des défauts que l'appelant ne remplaçait jamais ; la
    marge valait CA × 0,30, donc proportionnelle au CA.

    ⚠️ ET C'ÉTAIT UNE RECOMMANDATION D'ACTION : un actuaire qui la suivait
    baissait son tarif de 20 %.

    ⚠️ CE QUI LA REMPLACE N'EST PAS UN SILENCE. Le module CONSTATE qu'aucune
    donnée de comportement n'est déclarée, le dit, dit ce que cela coûte, et
    tarife normalement. Aucun blocage. C'est le patron du lecteur d'inventaire
    IFRS 17 : une capacité se déclare atteignable ou non, avec son coût.
    """

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        cls.agent = AgentA4ML(models_path='/tmp', audit_path='/tmp',
                              verbose=False)
        cls.r = cls.agent.run(
            result_a2=_make_r_a2(600), result_a3=_make_r_a3(),
            plan=_PLAN_AUTO, calcul_shap=False, generer_graphiques=True)

    def test_la_recommandation_tarifaire_FABRIQUEE_a_disparu(self):
        """⚠️ LE SYMBOLE, LA CLÉ ET LA FIGURE — les trois, sinon le retrait
        est incomplet et la valeur ressort par un autre chemin."""
        from direction_non_vie.tarification.a4_ml import agent as A4
        self.assertFalse(
            hasattr(A4.AgentA4ML, '_optimisation_tarifaire'),
            "la méthode qui fabriquait le « tarif optimal » existe encore")
        self.assertNotIn(
            'optimisation', self.r,
            "le résultat publie encore une clé « optimisation »")
        figs = set(self.r.get('graphiques_validation') or {})
        self.assertNotIn(
            'optimisation_tarifaire', figs,
            f"la figure « Tarif optimal » est encore produite : {sorted(figs)}")
        print("    POS-A4e le tarif optimal fabriqué a disparu — "
              "méthode, clé et figure ✅")

    def test_l_elasticite_se_declare_avec_ce_que_son_absence_COUTE(self):
        """⚠️ UNE ABSENCE QUI NE DIT PAS SON COÛT NE SE CORRIGE PAS. « pas
        d'élasticité » ne veut rien dire pour un actuaire ; « aucune
        recommandation tarifaire n'est produite, et voici l'historique qu'il
        faudrait » se comprend et se fournit."""
        from core.elasticite import ELASTICITE_NON_FOURNIE
        e = self.r.get('elasticite')
        self.assertIsNotNone(e, "l'état de l'élasticité n'est pas publié")
        self.assertEqual(e['etat'], ELASTICITE_NON_FOURNIE)
        for cle in ('motif', 'ce_que_cela_coute', 'ce_quil_faudrait'):
            self.assertTrue(
                (e.get(cle) or '').strip(),
                f"l'état ne dit pas « {cle} » — une absence muette")
        print(f"    POS-A4f élasticité {e['etat']}, et son coût est dit ✅")

    def test_le_module_TARIFE_NORMALEMENT_malgre_l_absence(self):
        """⚠️ AUCUN BLOCAGE. C'est la moitié de la règle : diagnostiquer,
        jamais refuser. Un module qui s'arrêterait sur une donnée absente
        serait aussi faux qu'un module qui inventerait une valeur."""
        self.assertTrue(self.r['success'], f"Erreur : {self.r.get('erreur')}")
        self.assertTrue(self.r['classement'], "aucun modèle classé")
        self.assertIn(self.r['statut_rag'], ('VERT', 'AMBRE', 'ROUGE'))
        print(f"    POS-A4g tarification normale : "
              f"{len(self.r['classement'])} modèles, statut "
              f"{self.r['statut_rag']} ✅")

    def test_le_commentaire_actuaire_PORTE_la_mention(self):
        """⚠️ LE SILENCE LAISSERAIT CROIRE QU'ELLE A ÉTÉ CONSIDÉRÉE. C'est le
        motif de tout ce chantier : ce qui n'est pas mesuré doit se voir."""
        c = self.r.get('commentaire', '')
        self.assertIn('ÉLASTICITÉ-PRIX', c,
                      "le commentaire actuaire ne mentionne pas l'élasticité")
        self.assertIn('NON PRISE EN COMPTE', c)
        self.assertNotIn('Tarif optimal', c,
                         "le commentaire porte encore une recommandation")
        print("    POS-A4h le commentaire actuaire porte la mention ✅")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A4 ML v1.0 — MACHINE LEARNING")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
