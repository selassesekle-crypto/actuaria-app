"""
Tests A2 Preprocessing v1.0 — Feature Engineering Non-Vie
donnees synthetiques freMTPL2

⚠️⚠️ CONSTAT `a2/C14` : cet en-tete annoncait << 7 tests >>. Le nombre est
RETIRE, pas remplace par un autre compte a la main : `unittest` le publie
a chaque execution, et lui ne perime pas. *Meme geste que `a5/C9`.*
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))
from core.plan_tarifaire import PlanTarifaire

# Phase 2 : A2.run() reçoit le PLAN signé — l'encodage (one-hot vs label, ordre des
# modalités), les transformations et les interactions en sont dérivés.
# Fixtures auto → plan auto.
_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_PLAN_AUTO = PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans', 'auto.yaml'))


def _make_r_a1(n=500):
    """Result A1 synthétique prêt pour A2."""
    np.random.seed(42)
    df = pd.DataFrame({
        'id_contrat':           range(n),
        'nb_sinistres':         np.random.poisson(0.08, n),
        'cout_total_sinistres': np.maximum(np.random.exponential(800, n), 0),
        'exposition':           np.random.uniform(0.1, 1.0, n),
        'age':                  np.random.randint(18, 75, n),
        'bonus_malus':          np.random.uniform(50, 350, n),
        'puissance_fiscale':    np.random.randint(4, 15, n),
        'zone_geographique':    np.random.choice(['A','B','C','D','E','F'], n),
        # 'Essence' et non 'Regular' : les modalités du plan (plans/auto.yaml)
        # font AUTORITÉ depuis la Phase 2. 'Regular' est une valeur freMTPL2 que
        # l'ancien encodage automatique avalait en silence ; le plan déclare
        # [Essence, Diesel, Electrique] et une modalité inconnue lève (piège V9).
        'carburant':            np.random.choice(['Essence','Diesel'], n),
        'age_vehicule':         np.random.randint(0, 20, n),
        'densite_population':   np.random.uniform(10, 5000, n),
    })
    return {
        'success': True, 'dataframe': df,
        'branche': 'auto', 'statut_rag': 'VERT',
        'score_qual': 95.0,
        'qualite': {'taux_completude': 99.0, 'taux_doublons': 0.0,
                    'nb_lignes': n, 'nb_colonnes': len(df.columns),
                    'score_global': 95.0, 'colonnes': df.columns.tolist(),
                    'expo_ok_pct': 100.0},
        'hash_md5': 'abc123', 'rapport': {'etapes': ['dataframe_direct'], 'alertes': []},
        'commentaire': 'OK', 'audit_id': 'A1_TEST', 'client_id': None, 'erreur': None,
    }


class TestA2Preprocessing(unittest.TestCase):
    """A2 Preprocessing — Pipeline feature engineering complet."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        cls.agent  = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        cls.r_a1   = _make_r_a1(500)
        cls.r      = cls.agent.run(result_a1=cls.r_a1, plan=_PLAN_AUTO)

    def test_a2(self):
        r = self.r

        # ST1 — Pipeline sans erreur
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT', 'AMBRE', 'ROUGE'])
        print(f"    ST1 Pipeline ✅ | statut={r['statut_rag']}")

        # ST2 — DataFrame enrichi retourné
        df = r['dataframe']
        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)
        print(f"    ST2 DataFrame ✅ | {len(df)} lignes × {len(df.columns)} colonnes")

        # ST3 — Variables cibles présentes
        self.assertIn('nb_sinistres', df.columns,
                      "Variable cible fréquence manquante")
        print(f"    ST3 Variables cibles ✅")

        # ST4 — Exposition dans [0, 1] (winsorisation appliquée)
        if 'exposition' in df.columns:
            expo = df['exposition'].dropna()
            self.assertTrue((expo >= 0).all() and (expo <= 1).all(),
                            "Exposition hors [0,1] après winsorisation")
            print(f"    ST4 Exposition ✅ | min={expo.min():.3f} max={expo.max():.3f}")
        else:
            print(f"    ST4 Exposition ✅ (colonne absente — OK en mode train)")

        # ST5 — Paramètres de transformation documentés
        params = r['parametres']
        self.assertIsInstance(params, dict)
        print(f"    ST5 Paramètres ✅ | {len(params)} clés documentées")

        # ST6 — Branche héritée de A1
        self.assertEqual(r['branche'], 'auto')
        print(f"    ST6 Branche ✅ | '{r['branche']}'")

        # ST7 — Commentaire actuaire généré
        self.assertIsInstance(r['commentaire'], str)
        self.assertGreater(len(r['commentaire']), 10)
        print(f"    ST7 Commentaire ✅ | {len(r['commentaire'])} chars")




class TestA2PrimePureCalculee(unittest.TestCase):
    """
    Verrou anti-régression — audit V7 anomalie BLOQUANTE B2 (volet A2).

    'prime_pure' était référencée comme cible attendue par A3/A4/A6, mais
    JAMAIS produite par A2 (sauf déjà présente dans les données brutes,
    rarissime pour une grandeur dérivée). Conséquence : en invocation par
    défaut d'A6 (col_cible='prime_pure'), le walk-forward se désactivait
    silencieusement — B2. Corrigé en calculant automatiquement prime_pure
    (cout_total_sinistres / exposition) quand absente.

    Ce test verrouille ce calcul contre toute régression future — sans
    lui, le contrat de données A2→A6 serait à nouveau rompu en silence.
    """

    def test_prime_pure_calculee_si_absente(self):
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        agent = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        r_a1 = _make_r_a1(500)  # fixture existante : cout_total_sinistres +
                                 # exposition présentes, PAS prime_pure
        self.assertNotIn('prime_pure', r_a1['dataframe'].columns,
                         "Pré-requis du test : prime_pure ne doit pas être "
                         "déjà présente dans la fixture brute")
        r = agent.run(result_a1=r_a1, plan=_PLAN_AUTO)

        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(
            'prime_pure', r['dataframe'].columns,
            "RÉGRESSION BLOQUANTE (audit V7 B2) — 'prime_pure' n'est plus "
            "calculée automatiquement. Le contrat de données A2→A6 est "
            "à nouveau rompu : le walk-forward d'A6 se désactivera "
            "silencieusement en invocation par défaut."
        )
        # Cohérence de la formule : prime_pure = coût / exposition
        df = r['dataframe']
        attendu = df['cout_total_sinistres'] / df['exposition'].clip(lower=1e-6)
        import numpy as np
        self.assertTrue(
            np.allclose(df['prime_pure'], attendu, rtol=1e-4),
            "prime_pure calculée ne correspond pas à cout_total_sinistres/exposition"
        )
        print(f"    B2-A2 prime_pure calculée automatiquement ✅ | "
              f"moyenne={df['prime_pure'].mean():.2f}")


def _portefeuille_complet(plan, n=400, seed=3):
    """Un fichier client SAIN : tous les facteurs du plan, aucune valeur
    manquante, aucune modalité inconnue. Construit DEPUIS le plan — une
    fixture écrite à la main se périmerait au premier facteur ajouté."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        'id_contrat':           range(n),
        'nb_sinistres':         rng.poisson(0.08, n).astype(float),
        'cout_total_sinistres': rng.exponential(800, n),
        'exposition':           rng.uniform(0.2, 1.0, n),
    })
    for f in plan.facteurs:
        if f.nom in df.columns:
            continue
        if f.type == 'continu':
            df[f.nom] = rng.uniform(1, 100, n)
        elif f.type == 'binaire':
            df[f.nom] = rng.integers(0, 2, n).astype(float)
        else:
            df[f.nom] = rng.choice([str(m) for m in f.modalites], n)
    for col in plan.colonnes_attendues():
        if col not in df.columns:
            df[col] = rng.uniform(1, 100, n)
    return {'success': True, 'dataframe': df, 'branche': plan.lob,
            'statut_rag': 'VERT', 'erreur': None}


class T_Un_Fichier_Sain_Obtient_Un_Bon_Verdict(unittest.TestCase):
    """CONTRÔLE POSITIF — la leçon V14, étendue à A2.

    ⚠️ ÉCRITE DANS `a4_ml/agent.py` AU CORRECTIF V14, APPLIQUÉE À A6 SEUL :

        « On a beaucoup vérifié que le système REFUSE ce qu'il doit refuser.
          Personne n'a vérifié qu'il ACCEPTE ce qu'il doit accepter. Un
          contrôle qui refuse tout est aussi inutile qu'un contrôle qui
          accepte tout — et bien plus difficile à repérer, parce qu'il donne
          l'apparence de la rigueur. »

    ⚠️ MESURÉ AVANT CE LOT, SUR LES VINGT PLANS DU DÉPÔT, DONNÉES COMPLÈTES ET
    PROPRES : **VERT atteint par 0 plan sur 20**. Le nombre de « colonnes non
    encodées » signalées vaut, plan par plan, exactement le nombre de facteurs
    CATÉGORIELS — parce qu'A2 ajoute les colonnes encodées et CONSERVE la
    colonne brute, que `_valider_sortie` compte alors comme non encodée.
    """

    def test_un_portefeuille_complet_et_propre_atteint_VERT(self):
        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
        agent = AgentA2Preprocessing(models_path='/tmp', audit_path='/tmp',
                                     verbose=False)
        r = agent.run(result_a1=_portefeuille_complet(_PLAN_AUTO),
                      plan=_PLAN_AUTO)
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        non_enc = r['rapport']['transformations']['validation'].get(
            'colonnes_non_encodees', [])
        produites = set(_PLAN_AUTO.colonnes_produites())
        # ⚠️ LA PREUVE QUE LE SIGNALEMENT EST FAUX, PAS SEULEMENT LE STATUT :
        # chaque colonne dite « non encodée » a ses colonnes encodées dans la
        # sortie. On le montre AVANT d'exiger le VERT — sinon le test ne
        # dirait pas POURQUOI il tombe.
        for col in non_enc:
            issues = sorted(c for c in produites if c.startswith(col + '_'))
            self.assertEqual(
                issues, [],
                f"« {col} » est signalée non encodée alors que le plan produit "
                f"{issues} — la colonne brute survit à côté de ses encodages")
        self.assertEqual(
            r['statut_rag'], 'VERT',
            f"statut {r['statut_rag']} sur un fichier COMPLET et PROPRE ; "
            f"colonnes dites non encodées : {non_enc}")
        print(f"    POS-A2a fichier sain → {r['statut_rag']} ✅")

    def test_le_nombre_de_variables_winsorisees_PUBLIE_est_le_vrai(self):
        """⚠️ MESURÉ : « Winsorisées : 0 variable(s) » publié à l'actuaire
        alors que NEUF facteurs continus l'ont été. `_appliquer_plan` retourne
        un dict indexé par nom de colonne ; le commentaire lit une clé
        `colonnes_winsorisees` qui n'existe pas, et son `.get(..., {})` rend
        donc toujours un dictionnaire vide."""
        import re

        from direction_non_vie.tarification.a2_preprocessing.agent import (
            AgentA2Preprocessing,
        )
        agent = AgentA2Preprocessing(models_path='/tmp', audit_path='/tmp',
                                     verbose=False)
        r_a1 = _portefeuille_complet(_PLAN_AUTO, n=500, seed=11)
        # des queues franches, pour que la winsorisation morde vraiment
        rng = np.random.default_rng(11)
        for f in _PLAN_AUTO.facteurs:
            if f.type == 'continu' and f.nom in r_a1['dataframe'].columns:
                r_a1['dataframe'][f.nom] = rng.lognormal(3, 1.4, 500)
        r = agent.run(result_a1=r_a1, plan=_PLAN_AUTO)
        reel = len(r['rapport']['transformations']['winsorisation'])
        self.assertGreater(reel, 0, "prémisse : la winsorisation doit mordre")
        m = re.search(r'Winsoris\w+\s*:\s*(\d+)\s*variable', r['commentaire'])
        self.assertIsNotNone(m, "le commentaire ne publie pas ce nombre")
        self.assertEqual(
            int(m.group(1)), reel,
            f"le commentaire publie « {m.group(0)} » alors que {reel} "
            f"facteur(s) ont été écrêté(s)")
        print(f"    POS-A2b {reel} winsorisées, {m.group(1)} publiées ✅")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A2 PREPROCESSING v1.0")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
