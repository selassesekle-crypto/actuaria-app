# -*- coding: utf-8 -*-
"""CONTRÔLES POSITIFS — les 4 « fermés » du sous-bloc vivant qui n'étaient PAS épinglés.

⚠️ La double vérification des 15 « déjà fermés » a établi que ONZE étaient déjà
épinglés par un contrôle nommé, et que QUATRE ne l'étaient pas :
  · `a3/C1` — un FAUX POSITIF de grep me l'avait caché (`a3/C1` matchait
    `a3/C10`, préfixe — même famille que « imprimerie contient prime ») ;
  · `a4/C1` — fermé au lot L0, jamais épinglé ;
  · `a4/C4` — ⚠️ nommé « déjà fermé » dans une docstring de classe SANS aucune
    méthode qui l'asserte : un FAUX ÉPINGLÉ, le troisième état de §④ ;
  · `a5/C2` — fermé, jamais épinglé.

Chaque constat est ici épinglé par DEUX méthodes indépendantes (source +
comportement/exécution) et porte son SECOND SENS.

Les trois natures, déclarées SÉPARÉMENT (jamais fondues dans « aucun euro déplacé ») :
  · `a3/C1` déplace un EURO — la prime pure Tweedie redevenait ∝ exposition
    (corr +0,51, ×2,00 mesurés) parce que le predict portait offset=log(expo) ;
  · `a4/C4` est un STATUT AFFICHÉ — deux validations contradictoires dans le
    même retour ;
  · `a5/C2` est un NOMBRE PUBLIÉ — une convergence H1 déduite du Gini au lieu
    d'être lue de l'historique d'entraînement réel.
"""
import inspect
import os
import sys
import unittest

import numpy as np
import pandas as pd

_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.a3_glm import agent as A3
from direction_non_vie.tarification.a4_ml import agent as A4
from direction_non_vie.tarification.a5_deep_learning import agent as A5

_PLAN_AUTO = PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans', 'auto.yaml'))


def _r3_auto(n=2500, seed=5):
    """A1→A2→A3 sur un portefeuille auto à exposition DISPERSÉE — pour a3/C1."""
    from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
    from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
    rng = np.random.default_rng(seed)
    age = rng.integers(18, 85, n)
    bm = np.clip(rng.normal(.9, .2, n), .5, 3.5)
    expo = np.clip(rng.beta(2, 3, n), .05, 1.)          # dispersée sur [0.05, 1]
    nb = rng.poisson(0.25 * np.exp(0.9 * np.log(bm) + 0.7 * (age < 25)) * expo)
    df = pd.DataFrame({
        'id_contrat': range(n),
        'annee_souscription': rng.choice([2020, 2021, 2022, 2023], n),
        'exposition': expo, 'age': age.astype(float), 'bonus_malus': bm,
        'anciennete_permis': np.clip(age - 18, 0, None).astype(float),
        'puissance_fiscale': rng.integers(4, 15, n).astype(float),
        'age_vehicule': rng.integers(0, 20, n).astype(float),
        'carburant': rng.choice(['Essence', 'Diesel'], n),
        'usage': rng.choice(['Prive', 'Pro'], n),
        'csp': rng.choice(['Cadre', 'Employe', 'Retraite'], n),
        'milieu_geographique': rng.choice(['Urbain', 'Rural'], n),
        'garantie': rng.choice(['Tiers', 'TousRisques'], n),
        'valeur_venale': rng.uniform(5000, 40000, n),
        'kilometrage_annuel': rng.uniform(5000, 30000, n),
        'antecedents_sinistres_n1': rng.poisson(0.15, n).astype(float),
        'nb_sinistres': nb.astype(float),
        'cout_total_sinistres': np.where(nb > 0, rng.gamma(2, 1200, n), 0.)})
    r2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False).run(
        result_a1=AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
            branche='non_vie', sous_branche='auto', dataframe=df),
        plan=_PLAN_AUTO)
    a3 = A3.AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
    r3 = a3.run(result_a2=r2, plan=_PLAN_AUTO, generer_graphiques=False)
    return r2, r3, a3


# ══ a3/C1 — le Tweedie n'ajuste ni ne prédit plus AVEC offset (EURO) ══════════
class POS_a3C1_TweedieSansOffset(unittest.TestCase):
    """a3/C1 — la prime pure Tweedie est un TAUX annuel, exposure-INDÉPENDANTE.
    Le predict portait offset=log(expo) → prime ∝ exposition. Le SEUL des 40 à
    déplacer un euro. Correctif au fit ET au predict."""

    def test_source_le_predict_prime_pure_tweedie_ne_porte_pas_offset(self):
        src = inspect.getsource(A3.AgentA3GLM)
        i = src.index("predictions['prime_pure_tweedie']")
        bloc = src[i:i + 170]
        self.assertNotIn('offset', bloc,
                         "le predict Tweedie porte encore un offset (double expo)")
        # et le fit déclare explicitement l'absence d'offset
        src_fit = inspect.getsource(A3.AgentA3GLM._calibrer_tweedie)
        self.assertIn("PAS D'OFFSET", src_fit,
                      "le fit Tweedie ne documente plus l'absence d'offset")
        print("    POS a3/C1 source : Tweedie sans offset au fit ET au predict ✅")

    def test_comportement_ajouter_l_offset_CHANGERAIT_la_prime_publiee(self):
        """Méthode indépendante — on REPRODUIT le bug. Le modèle Tweedie ajusté,
        prédit AVEC offset=log(expo), donnerait une prime ∝ exposition ; le code
        publie la version SANS. On prouve les deux : (1) la prime publiée EST la
        version sans offset ; (2) l'offset la changerait matériellement — sinon
        le test ne discriminerait rien.

        ⚠️ Pourquoi PAS un simple corr(prime, expo) ≈ 0 : `km_par_an_normalise`
        = km / exposition est un facteur LÉGITIME inversement lié à l'expo. La
        prime y est donc corrélée (mesuré −0,33) SANS aucun offset. Un corr non
        nul ne prouve rien ; la reproduction du bug, si."""
        import statsmodels.api as sm
        _r2, r3, a3 = _r3_auto()
        mdl = a3.modeles['tweedie']
        vars_tw = a3.metriques['tweedie']['vars_retenues']
        df = _r2['dataframe']
        X = sm.add_constant(df[vars_tw].fillna(0), has_constant='add')
        expo = np.maximum(df['exposition'].values.astype(float), 1e-6)
        sans = np.asarray(mdl.predict(X), dtype=float)                     # publié
        avec = np.asarray(mdl.predict(X, offset=np.log(expo)), dtype=float)  # le bug
        publie = np.asarray(r3['predictions']['prime_pure_tweedie'], dtype=float)
        self.assertTrue(np.allclose(publie, sans, rtol=1e-6),
                        "la prime publiée n'est PAS la prédiction sans offset")
        ecart = float(np.mean(np.abs(avec - sans) / np.maximum(sans, 1e-9)))
        self.assertGreater(ecart, 0.10,
                           "ajouter l'offset ne changerait rien : test aveugle")
        print(f"    POS a3/C1 comportement : prime publiée = sans offset ; "
              f"l'offset la changerait de {ecart:.0%} ✅")

    def test_LE_SECOND_SENS_la_frequence_Poisson_GARDE_son_offset(self):
        """La fréquence EST exposure-dépendante : retirer les DEUX offsets serait
        l'erreur inverse. Le Poisson DOIT garder le sien."""
        src = inspect.getsource(A3.AgentA3GLM)
        i = src.index("self.modeles['poisson'].predict")
        self.assertIn('offset', src[i:i + 130],
                      "la fréquence Poisson a perdu son offset — biais inverse")
        print("    POS a3/C1 SECOND SENS : la fréquence garde son offset ✅")


# ══ a4/C1 — l'optimiseur tarifaire codé en dur ne revient pas ═════════════════
class POS_a4C1_LOptimisationTarifaireEstAbsente(unittest.TestCase):
    """a4/C1 — `_optimisation_tarifaire` (un optimiseur retiré au lot L0) ne doit
    pas réapparaître."""

    def test_source_la_methode_est_absente_de_la_classe(self):
        self.assertFalse(hasattr(A4.AgentA4ML, '_optimisation_tarifaire'),
                         "_optimisation_tarifaire est revenu comme méthode d'A4")
        self.assertNotIn('_optimisation_tarifaire',
                         inspect.getsource(A4.AgentA4ML),
                         "_optimisation_tarifaire est mentionné dans le code d'A4")
        print("    POS a4/C1 : _optimisation_tarifaire absent d'A4 ✅")

    def test_LE_SECOND_SENS_la_vraie_calibration_subsiste(self):
        """Retirer l'optimiseur ne doit pas avoir emporté la calibration réelle
        des modèles — sinon A4 ne modéliserait plus rien."""
        self.assertTrue(hasattr(A4.AgentA4ML, '_calibrer_tous_modeles'),
                        "la vraie calibration a disparu avec l'optimiseur")
        print("    POS a4/C1 SECOND SENS : la calibration réelle subsiste ✅")


# ══ a4/C4 — validation_ml et hypotheses sont le MÊME objet (STATUT) ═══════════
class POS_a4C4_ValidationMlEtHypothesesIdentiques(unittest.TestCase):
    """a4/C4 — `validation_ml` et `hypotheses` divergeaient dans le MÊME retour.
    Corrigé : les deux clés portent le même objet `_val_ml_tmp`.
    ⚠️ Ce constat était marqué « fermé » dans une docstring SANS test — un faux
    épinglé. Il l'est enfin ici, par la source ET par un vrai retour A4."""

    def test_source_les_deux_cles_portent_le_meme_objet(self):
        src = inspect.getsource(A4.AgentA4ML.run)
        self.assertRegex(src, r"'validation_ml':\s*_val_ml_tmp",
                         "validation_ml ne porte pas _val_ml_tmp")
        self.assertRegex(src, r"'hypotheses':\s*_val_ml_tmp",
                         "hypotheses ne porte pas _val_ml_tmp")
        print("    POS a4/C4 source : validation_ml et hypotheses = même objet ✅")

    def test_execution_sur_un_vrai_retour_A4_elles_sont_EGALES(self):
        import direction_non_vie.tarification.a4_ml.test_a4_ml as T4
        r4 = A4.AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False).run(
            result_a2=T4._make_r_a2(600), result_a3=T4._make_r_a3(),
            plan=_PLAN_AUTO, calcul_shap=False, generer_graphiques=False)
        vm, hy = r4.get('validation_ml'), r4.get('hypotheses')
        self.assertTrue(vm, "validation_ml vide : rien à comparer (prémisse)")
        self.assertEqual(set(vm), set(hy),
                         "validation_ml et hypotheses n'ont pas les mêmes clés")
        self.assertEqual(vm, hy,
                         "validation_ml et hypotheses divergent sur un vrai retour")
        print(f"    POS a4/C4 exécution : {len(vm)} clés identiques ✅")


# ══ a5/C2 — H1 lit l'historique RÉEL, ne fabrique plus la convergence (NOMBRE) ═
class POS_a5C2_H1LitLHistoriqueReel(unittest.TestCase):
    """a5/C2 — H1 (convergence DL) déduisait sa « loss finale » du Gini : une
    convergence FABRIQUÉE. Corrigé : elle lit l'historique d'entraînement réel
    (`historiques.get(...)`)."""

    def _val(self, historiques):
        a5 = A5.AgentA5DeepLearning(models_path='/tmp', audit_path='/tmp')
        classement = [{'modele': 'cann', 'gini_test': 0.30, 'gini': 0.30}]
        return a5._valider_hypotheses_dl(classement, {}, historiques=historiques)

    def test_source_H1_lit_historiques_et_ne_simule_pas(self):
        src = inspect.getsource(A5.AgentA5DeepLearning._valider_hypotheses_dl)
        self.assertIn('historiques.get', src, "H1 ne lit pas l'historique réel")
        self.assertNotIn('np.random', src, "H1 simule encore (np.random présent)")
        print("    POS a5/C2 source : H1 lit l'historique, ne simule pas ✅")

    def test_comportement_deux_historiques_donnent_deux_statuts(self):
        conv = self._val({'cann': [{'train': 1.0}, {'train': 0.20}]})   # ratio 0.20 → VERT
        pas_ = self._val({'cann': [{'train': 1.0}, {'train': 0.90}]})   # ratio 0.90 → ROUGE
        self.assertEqual(conv['h1_convergence']['statut'], 'VERT',
                         "un historique convergent ne rend pas VERT")
        self.assertEqual(pas_['h1_convergence']['statut'], 'ROUGE',
                         "un historique non convergent ne rend pas ROUGE — H1 "
                         "ne lit donc pas l'historique")
        print("    POS a5/C2 comportement : l'historique DÉCIDE le statut ✅")

    def test_LE_SECOND_SENS_sans_historique_H1_est_ROUGE_non_mesuree_pas_VERT(self):
        """Un historique absent → « convergence NON mesurée » (ROUGE), jamais un
        VERT fabriqué. C'est le cœur du constat : un nombre non mesuré ne se
        déclare pas satisfait."""
        sans = self._val(None)
        self.assertEqual(sans['h1_convergence']['statut'], 'ROUGE')
        self.assertIn('NON mesurée', sans['h1_convergence']['message'])
        print("    POS a5/C2 SECOND SENS : sans historique → ROUGE non mesurée ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
