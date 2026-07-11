"""
Test d'EXÉCUTION RÉELLE — ferme les recommandations V6 #1 et #2 de l'audit V5.

Contrairement aux tests existants (qui vérifient structure / plages / statuts),
ce fichier EXÉCUTE réellement les deux chemins que ni le développeur ni l'audit
V5 n'avaient exercés :

  PART A (V6 #2) — Walk-forward avec un vrai modèle ML (XGBoost / LightGBM /
    XGBoost-Tweedie) EN TÊTE du classement, pour confirmer que le chemin
    « recalibration fidèle » se déclenche vraiment (et non le proxy GBM), que
    le modèle est bien réentraîné par fenêtre, et qu'un Gini walk-forward est
    produit. Contrôle négatif : un modèle GLM_* doit, lui, retomber en proxy.

  PART B (V6 #1) — CANN gelé comparé à statsmodels.predict() de façon
    INDÉPENDANTE. Le self-check interne du code (`glm_verification_error`)
    compare la forward du CANN à une formule reconstruite avec LES MÊMES
    coefficients reprojetés — il est tautologique et ne détecterait pas une
    erreur de reprojection d'échelle. Ici on compare la prédiction du CANN
    (époque 0, résiduel nul) à la prédiction du VRAI GLM statsmodels sur les
    features BRUTES. Si la reprojection raw→standardisé est correcte, les deux
    coïncident à la précision flottante près.

Usage : python3 test_v6_execution_reelle.py   (depuis la racine du repo)
"""

import sys
import os
import unittest
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Rendre le package importable quel que soit le cwd
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
from direction_non_vie.tarification.a4_ml.agent import (
    creer_modele_ml_pour_nom, XGBOOST_OK, LIGHTGBM_OK,
)
from direction_non_vie.tarification.a5_deep_learning.agent import (
    AgentA5DeepLearning, TORCH_OK,
)


# ════════════════════════════════════════════════════════════════════════════
# Générateurs de données synthétiques AVEC signal (sinon Gini dégénéré)
# ════════════════════════════════════════════════════════════════════════════

def _donnees_walk_forward(n_par_annee=1500, annees=(2019, 2020, 2021, 2022), seed=7):
    """Portefeuille auto synthétique multi-années, fréquence dépendant des
    features (pour que XGBoost/LightGBM aient quelque chose à apprendre)."""
    rng = np.random.default_rng(seed)
    blocs = []
    for an in annees:
        n = n_par_annee
        age      = rng.integers(18, 80, n).astype(float)
        bonus    = rng.uniform(0.5, 1.6, n)
        puiss    = rng.integers(4, 12, n).astype(float)
        expo     = rng.uniform(0.3, 1.0, n)
        # Fréquence "vraie" : jeunes + mauvais bonus + forte puissance
        lam = (
            0.06
            + 0.004 * np.maximum(30 - age, 0)
            + 0.05 * (bonus - 0.5)
            + 0.006 * (puiss - 4)
        ) * expo
        nb = rng.poisson(np.maximum(lam, 1e-4))
        blocs.append(pd.DataFrame({
            "annee_souscription": an,
            "age": age, "bonus_malus": bonus, "puissance_fiscale": puiss,
            "exposition": expo, "nb_sinistres": nb,
        }))
    return pd.concat(blocs, ignore_index=True)


def _donnees_glm_cann(n=2500, seed=11):
    """Données pour le GLM Tweedie + CANN. Cible = prime pure (Tweedie)."""
    rng = np.random.default_rng(seed)
    age   = rng.integers(18, 80, n).astype(float)
    bonus = rng.uniform(0.5, 1.6, n)
    puiss = rng.integers(4, 12, n).astype(float)
    expo  = rng.uniform(0.3, 1.0, n)
    lam = (0.05 + 0.004 * np.maximum(30 - age, 0) + 0.05 * (bonus - 0.5)) * expo
    nb  = rng.poisson(np.maximum(lam, 1e-4))
    sev = rng.gamma(shape=2.0, scale=1200.0, size=n)
    cout = nb * sev  # prime pure : masse en 0 + continu positif → Tweedie
    X_raw = pd.DataFrame({"age": age, "bonus_malus": bonus, "puissance_fiscale": puiss})
    return X_raw, cout.astype(float), expo.astype(float)


# ════════════════════════════════════════════════════════════════════════════
# PART A — Walk-forward : le chemin FIDÈLE se déclenche-t-il vraiment ?
# ════════════════════════════════════════════════════════════════════════════

class TestWalkForwardFideleReel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.df = _donnees_walk_forward()
        cls.agent = AgentA6Comparaison()

    def _run_wf(self, modele_nom):
        classement = [{
            "modele": modele_nom, "famille": "ML",
            "gini_test": 0.20, "rmse_test": 0.5,
            "overfit_ratio": 1.0, "interpretabilite": 0.6,
            "score_global": 0.7,
        }]
        return self.agent._backtesting_temporel(
            self.df, col_cible="nb_sinistres", col_expo="exposition",
            classement=classement,
        )

    def test_A1_xgboost_en_tete_declenche_fidele(self):
        if not XGBOOST_OK:
            self.skipTest("xgboost non installé")
        bt = self._run_wf("ML_XGBOOST")
        self.assertTrue(bt.get("disponible"), "Walk-forward indisponible")
        self.assertTrue(
            bt.get("modele_recalibre_fidele"),
            f"Chemin fidèle NON déclenché pour ML_XGBOOST — "
            f"modele_recalibre={bt.get('modele_recalibre')!r}",
        )
        self.assertNotIn("proxy", str(bt.get("modele_recalibre", "")).lower())
        self.assertIsNotNone(bt.get("gini_wf_moyen"), "Aucun Gini walk-forward produit")
        # Contrôle de SIGNE sur le code réel : un modèle discriminant (XGBoost
        # sur données à signal) doit produire un Gini POSITIF (bug #2 = signe).
        self.assertGreater(bt["gini_wf_moyen"], 0,
                           f"Gini WF négatif ({bt['gini_wf_moyen']}) pour un "
                           f"modèle discriminant — signe inversé (bug V6 #2 ?)")
        self.assertGreater(len(bt.get("walk_forward", [])), 0)
        print(f"    A1 XGBoost fidèle ✅ | recalibré={bt['modele_recalibre']} "
              f"| Gini_WF={bt['gini_wf_moyen']} | {len(bt['walk_forward'])} fenêtres")

    def test_A2_lightgbm_en_tete_declenche_fidele(self):
        if not LIGHTGBM_OK:
            self.skipTest("lightgbm non installé")
        bt = self._run_wf("ML_LIGHTGBM")
        self.assertTrue(bt.get("modele_recalibre_fidele"),
                        f"Chemin fidèle NON déclenché pour ML_LIGHTGBM "
                        f"({bt.get('modele_recalibre')!r})")
        self.assertIsNotNone(bt.get("gini_wf_moyen"))
        print(f"    A2 LightGBM fidèle ✅ | recalibré={bt['modele_recalibre']} "
              f"| Gini_WF={bt['gini_wf_moyen']}")

    def test_A3_xgboost_tweedie_underscore_apres_prefixe(self):
        """Le cas piège du mandat V5 : nom AVEC underscore après le préfixe."""
        if not XGBOOST_OK:
            self.skipTest("xgboost non installé")
        bt = self._run_wf("ML_XGBOOST_TWEEDIE")
        self.assertTrue(
            bt.get("modele_recalibre_fidele"),
            "Le stripping de préfixe casse sur 'ML_XGBOOST_TWEEDIE' "
            "(underscore après préfixe) — régression du bug V5 #7",
        )
        print(f"    A3 XGBoost-Tweedie (underscore) fidèle ✅ | "
              f"recalibré={bt['modele_recalibre']}")

    def test_A4_le_glm_est_recalibre_fidelement(self):
        """⚠ PRÉMISSE INVERSÉE (audit V14).

        Ce test s'appelait `test_A4_controle_negatif_glm_retombe_en_proxy` et
        vérifiait qu'un GLM_* n'était PAS marqué fidèle — il ASSERTAIT LE BUG
        COMME UNE FONCTIONNALITÉ. À l'époque, c'était cohérent : la fabrique
        sklearn ne couvrait pas les GLM, et le seul comportement honnête était
        d'étiqueter le proxy comme tel.

        Mais personne n'avait tiré la conséquence : puisque le gate d'A6 exige
        `modele_recalibre_fidele` pour accorder un VERT, un GLM ne pouvait
        JAMAIS être certifié. Le modèle de référence de la Non-Vie —
        interprétable, auditable, attendu par l'ACPR — était structurellement
        exclu de la certification, et l'incitation poussait vers la boîte noire.

        La fabrique reconstruit désormais les GLM (statsmodels : même famille,
        même lien, même offset). Le GLM DOIT être recalibré fidèlement.
        """
        bt = self._run_wf("GLM_POISSON")
        self.assertTrue(bt.get("modele_recalibre_fidele"),
                        f"GLM_POISSON n'est PAS recalibré fidèlement "
                        f"({bt.get('modele_recalibre')}) : il ne pourra jamais "
                        f"être certifié VERT, quelle que soit sa qualité.")
        self.assertNotIn("proxy", str(bt.get("modele_recalibre", "")).lower())
        print(f"    A4 GLM recalibré FIDÈLEMENT ✅ | "
              f"recalibré={bt['modele_recalibre']}")

    def test_A5_convention_signe_gini_walk_forward(self):
        """SENTINELLE DE SIGNE (bug #2). Réplique la formule CORRIGÉE de
        a6_comparaison/agent.py:836-843 (`2*∫lorenz - 1`, numpy-2-safe) et
        vérifie la convention : parfait > 0, aléatoire ≈ 0, anti-corrélé < 0.
        Si un jour la formule du code repasse à `1 - 2*∫` (régression), ce test
        et le contrôle de signe de A1 échouent.
        """
        _trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz", None)

        def gini_formule_a6(y_te, pred_te):
            ordre    = np.argsort(-pred_te)
            y_sorted = y_te[ordre]
            lorenz   = np.cumsum(y_sorted) / max(y_te.sum(), 1e-9)
            # ↓↓↓ formule telle que corrigée en A6:841
            return float(2 * _trapz(lorenz, np.linspace(0, 1, len(lorenz))) - 1)

        rng = np.random.default_rng(0)
        y   = rng.poisson(0.3, 2000).astype(float)
        g_parfait = gini_formule_a6(y, y + rng.uniform(0, 1e-6, len(y)))
        g_alea    = gini_formule_a6(y, rng.uniform(size=len(y)))
        g_inverse = gini_formule_a6(y, -y + rng.uniform(0, 1e-6, len(y)))
        print(f"    A5 convention signe | parfait={g_parfait:.3f} (>0) "
              f"aléatoire={g_alea:.3f} (~0) inversé={g_inverse:.3f} (<0)")
        self.assertGreater(g_parfait, 0.5, "Prédicteur parfait doit donner Gini > 0")
        self.assertLess(abs(g_alea), 0.1, "Prédicteur aléatoire doit donner Gini ~ 0")
        self.assertLess(g_inverse, -0.5, "Prédicteur anti-corrélé doit donner Gini < 0")


# ════════════════════════════════════════════════════════════════════════════
# PART B — CANN gelé vs statsmodels.predict() (vérification INDÉPENDANTE)
# ════════════════════════════════════════════════════════════════════════════

class TestCANNGeleVsStatsmodels(unittest.TestCase):

    def test_B1_cann_epoch0_egale_glm_statsmodels(self):
        if not TORCH_OK:
            self.skipTest("torch non installé")
        try:
            import statsmodels.api as sm
        except ImportError:
            self.skipTest("statsmodels non installé")
        import torch
        from sklearn.preprocessing import StandardScaler

        X_raw, y, expo = _donnees_glm_cann()
        feature_names = list(X_raw.columns)  # ['age','bonus_malus','puissance_fiscale']

        # Split simple
        n = len(X_raw); i = int(n * 0.8)
        Xr_tr, Xr_te = X_raw.iloc[:i], X_raw.iloc[i:]
        y_tr,  y_te  = y[:i], y[i:]
        ex_tr, ex_te = expo[:i], expo[i:]

        # ── 1) VRAI GLM Tweedie statsmodels sur features BRUTES + offset ──────
        glm = sm.GLM(
            y_tr, sm.add_constant(Xr_tr),
            family=sm.families.Tweedie(link=sm.families.links.Log(), var_power=1.5),
            offset=np.log(ex_tr),
        ).fit()

        # ── 2) Scaler standard sur les MÊMES features, même ordre ────────────
        scaler = StandardScaler().fit(Xr_tr.values)
        Xstd_tr = scaler.transform(Xr_tr.values).astype(np.float32)
        Xstd_te = scaler.transform(Xr_te.values).astype(np.float32)

        # ── 3) On alimente le VRAI code A5 : agent.scalers + result_a3 ────────
        agent = AgentA5DeepLearning()
        agent.scalers["standard"] = scaler
        result_a3 = {"success": True, "modeles": {"tweedie": glm}}

        # n_epochs=0 → aucun entraînement → résiduel reste nul → CANN ≡ GLM gelé
        res = agent._calibrer_cann(
            X_train=Xstd_tr, X_test=Xstd_te,
            y_train=y_tr.astype(np.float32), y_test=y_te.astype(np.float32),
            feature_names=feature_names,
            device=torch.device("cpu"),
            n_epochs=0, batch_size=256, lr=1e-3,
            result_a3=result_a3, expo_train=ex_tr, expo_test=ex_te,
        )
        modele = res["modele"]
        met    = res["metriques"]

        # Le gel doit avoir eu lieu et toutes les variables être appariées
        self.assertTrue(met.get("glm_gele"), "Le GLM n'a pas été gelé")
        self.assertEqual(met.get("n_vars_glm_matchees"), met.get("n_vars_glm_total"),
                         "Reproduction GLM partielle — apparie toutes les variables")

        # ── 4) Prédiction CANN (époque 0, résiduel nul) ──────────────────────
        offset_te = np.log(np.maximum(ex_te, 1e-6)).astype(np.float32)
        modele.eval()
        with torch.no_grad():
            pred_cann = modele(
                torch.FloatTensor(Xstd_te),
                torch.FloatTensor(offset_te),
            ).cpu().numpy().ravel()

        # ── 5) Prédiction statsmodels INDÉPENDANTE sur features BRUTES ───────
        pred_glm = glm.predict(sm.add_constant(Xr_te), offset=np.log(ex_te)).values

        # ── 6) Comparaison : doivent coïncider (reprojection correcte) ───────
        ecart_rel = np.abs(pred_cann - pred_glm) / np.maximum(np.abs(pred_glm), 1e-9)
        ecart_max = float(np.max(ecart_rel))

        print(f"    B1 CANN vs statsmodels | écart relatif max = {ecart_max:.2e} "
              f"| self-check interne glm_verification_error = "
              f"{met.get('glm_verification_error')}")

        self.assertLess(
            ecart_max, 1e-3,
            f"CANN gelé (époque 0) ≠ GLM Tweedie statsmodels : écart max "
            f"{ecart_max:.4e}. La reprojection d'échelle raw→standardisé est "
            f"INCORRECTE (le self-check tautologique interne ne l'aurait pas vu)."
        )

    def test_B2_reprojection_fausse_serait_detectee(self):
        """Méta-test : on prouve que la comparaison est DISCRIMINANTE — une
        reprojection volontairement fausse produit bien un grand écart, donc
        le test B1 n'est pas trivialement satisfait."""
        if not TORCH_OK:
            self.skipTest("torch non installé")
        try:
            import statsmodels.api as sm
        except ImportError:
            self.skipTest("statsmodels non installé")
        import torch
        from sklearn.preprocessing import StandardScaler
        from direction_non_vie.tarification.a5_deep_learning.agent import CANNModel

        X_raw, y, expo = _donnees_glm_cann()
        i = int(len(X_raw) * 0.8)
        Xr_tr, Xr_te = X_raw.iloc[:i], X_raw.iloc[i:]
        ex_tr, ex_te = expo[:i], expo[i:]
        glm = sm.GLM(
            y[:i], sm.add_constant(Xr_tr),
            family=sm.families.Tweedie(link=sm.families.links.Log(), var_power=1.5),
            offset=np.log(ex_tr),
        ).fit()
        scaler = StandardScaler().fit(Xr_tr.values)
        Xstd_te = scaler.transform(Xr_te.values).astype(np.float32)

        # Reprojection VOLONTAIREMENT FAUSSE : on oublie le facteur sigma
        # (bug classique) → w_std = beta (au lieu de beta*sigma)
        w_faux = np.array([glm.params[v] for v in X_raw.columns], dtype=np.float32)
        bias_faux = float(glm.params["const"])
        modele_faux = CANNModel(n_features=3, hidden_sizes=[8],
                                glm_weight_init=w_faux, glm_bias_init=bias_faux)
        offset_te = np.log(np.maximum(ex_te, 1e-6)).astype(np.float32)
        modele_faux.eval()
        with torch.no_grad():
            pred_faux = modele_faux(torch.FloatTensor(Xstd_te),
                                    torch.FloatTensor(offset_te)).numpy().ravel()
        pred_glm = glm.predict(sm.add_constant(Xr_te), offset=np.log(ex_te)).values
        ecart_max = float(np.max(np.abs(pred_faux - pred_glm) /
                                 np.maximum(np.abs(pred_glm), 1e-9)))
        print(f"    B2 reprojection FAUSSE → écart max = {ecart_max:.2e} "
              f"(doit être grand : le test B1 est bien discriminant)")
        self.assertGreater(ecart_max, 0.05,
                           "Une reprojection fausse passe inaperçue — le test "
                           "B1 ne serait alors pas discriminant.")


if __name__ == "__main__":
    print("=" * 74)
    print(" TEST D'EXÉCUTION RÉELLE — V6 #1 (CANN vs statsmodels) & #2 (WF fidèle)")
    print("=" * 74)
    unittest.main(verbosity=2)
