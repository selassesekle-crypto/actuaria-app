"""
Tests A5 Deep Learning v1.0 — CANN + TabNet Non-Vie
7 tests · fallback si PyTorch absent · données synthétiques
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))
from core.plan_tarifaire import PlanTarifaire

# Phase 1 : A5.run() reçoit le PLAN signé (features restreintes à
# plan.colonnes_produites()). Fixtures auto → plan auto.
_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_PLAN_AUTO = PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans', 'auto.yaml'))

try:
    import torch
    TORCH_OK = True
except ImportError:
    TORCH_OK = False


def _make_r_a2(n=4000):
    # Portefeuille synthetique REPRODUCTIBLE (seed numpy) et ASSEZ GRAND pour que
    # le Gini du DL soit mesure sur assez de sinistres (~128 au pli test a n=4000).
    # L'ancienne version (n=400, ~34 sin. au test, SANS signal) mesurait du bruit
    # -> test_a5 instable (TabNet negatif ~2 fois sur 4). Diagnostic etape 3 :
    # la taille fixe la stabilite, le signal fixe le sens de la mesure.
    np.random.seed(42)
    exposition  = np.random.uniform(0.1, 1.0, n)
    age         = np.random.randint(18, 75, n).astype(float)
    bonus_malus = np.random.uniform(50, 350, n)
    puissance   = np.random.randint(4, 15, n).astype(float)
    # SIGNAL reel : sans lui la frequence ne depend d'AUCUNE feature (l'ancien
    # 0.08*exposition) et le vrai Gini vaut ~0 -> l'assertion testerait du bruit.
    # Jeune + malus eleve -> plus de sinistres (structure actuarielle standard).
    lam         = 0.18 * np.exp(0.6 * (age < 25) + 0.004 * (bonus_malus - 100))
    nb_sin      = np.random.poisson(lam * exposition).astype(float)
    cout        = np.where(nb_sin > 0, np.random.gamma(2, 400, n), 0.0)
    df = pd.DataFrame({
        'nb_sinistres':         nb_sin,
        'cout_total_sinistres': cout,
        'exposition':           exposition,
        'age':                  age,
        'bonus_malus':          bonus_malus,
        'puissance_fiscale':    puissance,
        'prime_pure':           cout / np.maximum(exposition, 0.01),
    })
    return {'success': True, 'dataframe': df, 'branche': 'auto',
            'statut_rag': 'VERT', 'parametres': {}, 'rapport': {},
            'commentaire': 'OK', 'audit_id': 'A2_TEST', 'erreur': None}


def _make_r_a3(df=None):
    # ANCRAGE GLM (Wuthrich) : si df fourni, on fitte un vrai GLM Tweedie de
    # FREQUENCE (nb_sinistres ~ features, offset=log expo) place dans
    # modeles['tweedie']. A5 GELE alors la couche GLM du CANN (glm_gele=True) ->
    # CANN tourne dans son MODE REEL, pas le fallback degenere (couche GLM
    # librement entrainable) qui donnait un Gini instable/negatif. On modelise la
    # FREQUENCE car l'archi CANN (exp + offset log-expo) est un modele de
    # comptage : l'offset n'est coherent que pour cette cible (une ancre sur
    # prime_pure, exposure-independante, degrade au contraire le CANN).
    modeles = {}
    if df is not None:
        import statsmodels.api as sm
        feats = ['age', 'bonus_malus', 'puissance_fiscale']
        modeles['tweedie'] = sm.GLM(
            df['nb_sinistres'], sm.add_constant(df[feats]),
            family=sm.families.Tweedie(var_power=1.5, link=sm.families.links.Log()),
            offset=np.log(np.maximum(df['exposition'].to_numpy(), 1e-6)),
        ).fit(maxiter=100)
    return {
        'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
        'metriques': {
            'poisson': {'gini': 0.14, 'aic': 1100,
                        'vars_retenues': ['age', 'bonus_malus'],
                        'nb_obs_train': 320, 'nb_obs_test': 80},
        },
        'modeles': modeles,
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
        cls.r_a2   = _make_r_a2(4000)
        cls.r_a3   = _make_r_a3(cls.r_a2['dataframe'])   # avec ANCRAGE GLM (mode reel du CANN)
        if TORCH_OK:
            # ⚠️ CE COMMENTAIRE DISAIT « A5 n'en fixe AUCUN » — CE N'EST PLUS
            # VRAI depuis le lot 1.1 : A5.run pose lui-meme `torch.manual_seed`
            # et `np.random.seed` a partir de son parametre `seed` (defaut 42),
            # et l'inscrit dans son rapport. Le determinisme ne vient plus de
            # l'exterieur ; ces deux lignes sont conservees pour le TIRAGE DU
            # PORTEFEUILLE, qui, lui, est fait ici.
            np.random.seed(1)
            torch.manual_seed(1)
            cls.r = cls.agent.run(
                result_a2=cls.r_a2, result_a3=cls.r_a3, plan=_PLAN_AUTO,
                col_cible='nb_sinistres',   # FREQUENCE : offset log-expo coherent (cf. _make_r_a3)
                n_epochs=30, batch_size=128, generer_graphiques=False
            )
        else:
            # Sans PyTorch → l'agent retourne une erreur documentée. col_cible est
            # fourni quand même : le contrôle torch s'exécute AVANT celui de la
            # cible, mais faire reposer un test sur l'ORDRE des garde-fous serait
            # un piège — on déclare, comme partout ailleurs.
            cls.r = cls.agent.run(
                result_a2=cls.r_a2, result_a3=cls.r_a3, plan=_PLAN_AUTO,
                col_cible='nb_sinistres', generer_graphiques=False
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

    def test_cann_non_ancre_surface_une_alerte(self):
        """Mode DÉGRADÉ : si A3 ne fournit pas de GLM Tweedie (r_a3 modeles={}),
        le CANN tourne sans ancrage (glm_gele=False) — ce n'est pas un vrai CANN
        Wüthrich. A5 doit le SURFACER dans son resultat (alertes_modele), pas
        seulement en log — c'est ce qui permet a A6 de plafonner le gate."""
        if not TORCH_OK:
            self.skipTest("PyTorch absent")
        from direction_non_vie.tarification.a5_deep_learning.agent import AgentA5DeepLearning
        agent = AgentA5DeepLearning(models_path='/tmp', audit_path='/tmp', verbose=False)
        r_a2 = _make_r_a2(4000)
        r_a3 = _make_r_a3()               # SANS df -> modeles={} -> AUCUN ancrage
        np.random.seed(1); torch.manual_seed(1)
        r = agent.run(result_a2=r_a2, result_a3=r_a3, plan=_PLAN_AUTO, col_cible='nb_sinistres',
                      n_epochs=5, batch_size=128, generer_graphiques=False)
        self.assertFalse(r['metriques']['cann'].get('glm_gele', True),
            "CANN sans GLM d'ancrage doit avoir glm_gele=False (mode degrade).")
        alertes = r.get('alertes_modele', [])
        self.assertTrue(
            any(a.get('code') == 'cann_glm_non_ancre' for a in alertes),
            "A5 doit surfacer l'alerte CANN non ancre dans alertes_modele "
            "(pas seulement un WARNING en log que personne ne lit).")
        print(f"    B2-A5 Mode dégradé surfacé → {len(alertes)} alerte(s) modèle ✅")




def _make_r_a2_avec_genre_numerique(n=400):
    """Fixture avec une colonne 'sexe' numérique (0/1) — même cas concret
    que le test équivalent d'A4 (audit V7 anomalie B1)."""
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


class TestA5FiltreGenre(unittest.TestCase):
    """
    Verrou anti-régression — audit V7 anomalie BLOQUANTE B1 (même trou
    que A4 : A5 utilisait une logique de sélection de features identique,
    sans aucun filtre genre, avant l'audit V7).
    """

    def test_genre_numerique_absent_des_features(self):
        if not TORCH_OK:
            self.skipTest("PyTorch non installé — filtre vérifié par lecture "
                           "de code lors de l'audit V7 (logique identique à A4, "
                           "elle-même vérifiée empiriquement).")
        from direction_non_vie.tarification.a5_deep_learning.agent import AgentA5DeepLearning
        agent = AgentA5DeepLearning(models_path='/tmp', audit_path='/tmp', verbose=False)
        r_a2 = _make_r_a2_avec_genre_numerique(400)
        r_a3 = _make_r_a3()
        # col_cible EXPLICITE : ce test héritait du défaut 'prime_pure' — il
        # exerçait donc le CANN sur une cible incohérente avec son offset
        # log(exposition). Le défaut a été supprimé (piège), la cible est déclarée.
        r = agent.run(result_a2=r_a2, result_a3=r_a3, plan=_PLAN_AUTO,
                      col_cible='nb_sinistres',
                      n_epochs=3, batch_size=64, generer_graphiques=False)

        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        features = r.get('rapport', {}).get('feature_names', [])
        self.assertNotIn(
            'sexe', features,
            "RÉGRESSION BLOQUANTE (audit V7 B1) — la colonne 'sexe' "
            "numérique est présente dans les features du modèle DL."
        )
        print(f"    B1-A5 Genre numérique filtré ✅ | features={features}")


class T_Un_Bon_Modele_Obtient_Un_Bon_Verdict(unittest.TestCase):
    """CONTRÔLE POSITIF — la leçon V14, étendue à A5.

    ⚠️ ELLE EST DÉJÀ DANS LE DÉPÔT, ET ELLE N'A ÉTÉ APPLIQUÉE QU'À A6. Écrite
    au correctif V14, dans `a4_ml/agent.py` :

        « On a beaucoup vérifié que le système REFUSE ce qu'il doit refuser.
          Personne n'a vérifié qu'il ACCEPTE ce qu'il doit accepter. Un
          contrôle qui refuse tout est aussi inutile qu'un contrôle qui
          accepte tout — et bien plus difficile à repérer, parce qu'il donne
          l'apparence de la rigueur. »

    ⚠️ ET IL NE PORTE PAS SUR LE STATUT, MAIS SUR LA GRANDEUR. Un contrôle qui
    exigerait « H1 doit être VERT » serait satisfait par une perte SIMULÉE :
    `_valider_hypotheses_dl` fabrique `loss_init = 0.50` et
    `loss_final = 1 - 2·gini` pendant que l'historique RÉEL est disponible et
    inutilisé. Le contrôle exige donc que la grandeur publiée vienne de la
    mesure — c'est la seule forme qui ne puisse pas être satisfaite à faux.
    """

    @classmethod
    def setUpClass(cls):
        if not TORCH_OK:
            return
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        r_a2 = _make_r_a2(4000)
        r_a3 = _make_r_a3(r_a2['dataframe'])      # ancrage GLM : mode RÉEL
        np.random.seed(1)
        torch.manual_seed(1)
        cls.r = AgentA5DeepLearning(
            models_path='/tmp', audit_path='/tmp', verbose=False).run(
            result_a2=r_a2, result_a3=r_a3, plan=_PLAN_AUTO,
            col_cible='nb_sinistres', n_epochs=30, batch_size=128,
            generer_graphiques=True)

    def setUp(self):
        if not TORCH_OK:
            self.skipTest("PyTorch absent")

    def test_le_verdict_DL_suit_le_Gini_REEL_du_modele(self):
        """⚠️ MESURÉ : un CANN ancré à Gini 0,478 était déclaré « ❌ Deep
        Learning non recommandé », ses TROIS hypothèses en ROUGE. Cause unique :
        `_valider_hypotheses_dl` lit `.get('gini', 0)` quand la clé réelle est
        `gini_test`. Le verdict ne partait donc jamais de la performance."""
        met = self.r['metriques']
        gini_dl = max(met[m]['gini_test'] for m in met)
        gini_glm = self.r['validation_dl']['h3_apport_dl']['gini_glm']
        self.assertGreater(gini_dl, gini_glm,
            "prémisse du test : le DL doit ici battre le GLM de référence")
        h3 = self.r['validation_dl']['h3_apport_dl']
        self.assertAlmostEqual(
            h3['gini_dl'], gini_dl, places=4,
            msg=(f"H3 publie gini_dl={h3['gini_dl']} alors que le meilleur DL "
                 f"vaut {gini_dl:.4f} — la clé lue n'est pas celle qui existe"))
        self.assertNotEqual(
            h3['statut'], 'ROUGE',
            f"un DL à Gini {gini_dl:.4f} contre un GLM à {gini_glm:.4f} ne peut "
            f"pas être déclaré « moins performant »")
        print(f"    POS-A5a Gini DL réel {gini_dl:.4f} > GLM {gini_glm:.4f} "
              f"→ H3 {h3['statut']} ✅")

    def test_H1_convergence_lit_l_historique_REEL(self):
        """⚠️ LA GRANDEUR, PAS LE STATUT. L'historique d'entraînement existe
        (`historique_cann`, une entrée par époque avec ses pertes réelles) et
        H1 ne le reçoit même pas : `_valider_hypotheses_dl` ne prend que le
        classement et les métriques. Elle fabrique alors `loss_init = 0.50`,
        constante, et `loss_final = 1 - 2·gini` — une fonction algébrique du
        Gini publiée sous le titre « Convergence de l'entraînement »."""
        hist = self.r['historique_cann']
        self.assertGreater(len(hist), 1, "prémisse : l'historique doit exister")
        h1 = self.r['validation_dl']['h1_convergence']
        self.assertAlmostEqual(
            h1['loss_init'], hist[0]['train'], places=3,
            msg=(f"H1 publie loss_init={h1['loss_init']} ; la PREMIÈRE perte "
                 f"réellement mesurée vaut {hist[0]['train']:.4f}"))
        self.assertAlmostEqual(
            h1['loss_final'], hist[-1]['train'], places=3,
            msg=(f"H1 publie loss_final={h1['loss_final']} ; la DERNIÈRE perte "
                 f"réellement mesurée vaut {hist[-1]['train']:.4f}"))
        print(f"    POS-A5b H1 lit l'historique réel "
              f"({hist[0]['train']:.4f} → {hist[-1]['train']:.4f}) ✅")

    def test_les_courbes_d_apprentissage_portent_les_pertes_REELLES(self):
        """⚠️ TROIS TRACÉS À ZÉRO. L'historique pose `train` et `val` ; le
        graphique lit `loss_train`, `loss_val` et `gini_val` — trois clés qui
        n'existent pas. Le rapport affiche donc « Courbes d'apprentissage »
        avec trois lignes plates, et une « Best époque » calculée dessus."""
        fig = self.r.get('graphiques', {}).get('apprentissage_cann')
        self.assertIsNotNone(fig, "la figure d'apprentissage n'est pas produite")
        traces = {t.name: [v for v in t.y] for t in fig.data if t.name}
        self.assertIn('Loss Train', traces)
        self.assertTrue(
            any(v != 0 for v in traces['Loss Train']),
            "la courbe « Loss Train » est intégralement à zéro — elle lit une "
            "clé absente de l'historique")
        print(f"    POS-A5c courbes non nulles : "
              f"{ {k: round(v[0], 4) for k, v in traces.items() if v} } ✅")


def _tenseur_de_l_arret_anticipe(source):
    """Le tenseur que chaque boucle d'entraînement lit pour choisir
    `best_state`. Relevé PAR AST, sur la ligne `pred_val = modele(...)`."""
    import ast as _ast
    trouves = {}
    arbre = _ast.parse(source)
    for fn in _ast.walk(arbre):
        if not isinstance(fn, _ast.FunctionDef):
            continue
        if fn.name not in ('_calibrer_cann', '_calibrer_tabnet'):
            continue
        for n in _ast.walk(fn):
            if (isinstance(n, _ast.Assign) and len(n.targets) == 1
                    and isinstance(n.targets[0], _ast.Name)
                    and n.targets[0].id == 'pred_val'
                    and isinstance(n.value, _ast.Call)):
                trouves[fn.name] = [_ast.unparse(a) for a in n.value.args]
    return trouves


class POS_A5e_LArretAnticipeNeLitPasLeTest(unittest.TestCase):
    """⚠️ CONTRÔLE POSITIF DU LOT 1.1 — constat `a5/C6`.

    AVANT LE CORRECTIF : il n'existait que TRAIN et TEST. `val_loss` était
    calculée sur `X_test_t`, et `best_state` retenu dessus. Le Gini test
    publié était donc le MAXIMUM sur les époques — une valeur SÉLECTIONNÉE sur
    le jeu qu'elle prétend estimer, pas une performance hors échantillon. Le
    module citait pourtant Kaufman et al. (2012) sur la fuite, et l'évitait
    correctement pour le scaler.

    ⚠️⚠️ L'OPTIMISME, MESURÉ à seed constant (donc imputable au seul C6) :

        CANN     0,3019 -> 0,2998    -0,0021   (-0,7 %)
        TabNet   0,2269 -> 0,1970    -0,0299   (-13,2 %)

    Le CANN bougeait peu, il est ancré sur un GLM gelé. **TabNet publiait un
    Gini 13 % trop haut.**
    """

    CHEMIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent.py')

    def _source(self):
        with open(self.CHEMIN, encoding='utf-8') as f:
            return f.read()

    def test_les_deux_boucles_valident_sur_X_val(self):
        t = _tenseur_de_l_arret_anticipe(self._source())
        self.assertEqual(set(t), {'_calibrer_cann', '_calibrer_tabnet'},
                         f"boucle(s) d'arret anticipe introuvable(s) : {set(t)}")
        for nom, args in t.items():
            self.assertNotIn(
                'X_test_t', args,
                f"{nom} regle son arret anticipe sur le TEST ({args}) — le "
                f"Gini publie redevient une valeur SELECTIONNEE sur le jeu "
                f"qu'elle pretend estimer")
            self.assertIn('X_val_t', args,
                          f"{nom} ne valide pas sur X_val ({args})")
        print(f"    POS-A5e arret anticipe sur la VALIDATION : {t} ✅")

    def test_le_controle_ATTRAPE_un_retour_au_test(self):
        """⚠️ LE SECOND SENS. Sans lui, ce contrôle pourrait devenir aveugle si
        quelqu'un recâblait la boucle — c'est le motif que cet audit poursuit."""
        plante = self._source().replace('pred_val = modele(X_val_t)',
                                        'pred_val = modele(X_test_t)')
        self.assertNotEqual(plante, self._source(), 'la violation n a pas ete plantee')
        t = _tenseur_de_l_arret_anticipe(plante)
        self.assertIn('X_test_t', t['_calibrer_tabnet'],
                      'le releve ne voit pas le retour au test')
        print('    POS-A5e violation plantee (retour au test) : ATTRAPEE ✅')

    def test_les_trois_jeux_existent_et_sont_disjoints(self):
        if not TORCH_OK:
            self.skipTest("PyTorch absent")
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        np.random.seed(5)
        r_a2 = _make_r_a2(2000)
        r = AgentA5DeepLearning(models_path='/tmp', audit_path='/tmp',
                                verbose=False).run(
            result_a2=r_a2, result_a3=_make_r_a3(r_a2['dataframe']),
            plan=_PLAN_AUTO, col_cible='nb_sinistres', n_epochs=3,
            batch_size=128, generer_graphiques=False)
        rap = r.get('rapport', {})
        n_tr, n_va, n_te = rap.get('n_train'), rap.get('n_val'), rap.get('n_test')
        for nom, v in (('n_train', n_tr), ('n_val', n_va), ('n_test', n_te)):
            self.assertIsNotNone(v, f"{nom} n'est pas trace dans le rapport")
            self.assertGreater(v, 0, f"{nom} est vide")
        total = n_tr + n_va + n_te
        self.assertAlmostEqual(n_te / total, 0.20, delta=0.02,
                               msg=f"test = {n_te}/{total}, attendu ~20 %")
        self.assertAlmostEqual(n_va / total, 0.12, delta=0.02,
                               msg=f"validation = {n_va}/{total}, attendu ~12 %")
        print(f"    POS-A5e trois jeux : train {n_tr} · val {n_va} · "
              f"test {n_te}  ({n_tr/total:.0%}/{n_va/total:.0%}/{n_te/total:.0%}) ✅")


class POS_A5d_LeCalibrageEstReproductible(unittest.TestCase):
    """⚠️ CONTRÔLE POSITIF DU LOT 1.1 — constat `a5/C7`.

    MESURÉ AVANT LE CORRECTIF, trois exécutions strictement identiques :

        CANN    0,3027 · 0,3018 · 0,3033   étendue 0,0015  (0,5 %)
        TabNet  0,2158 · 0,2379 · 0,2420   étendue 0,0262  (11 % DE LA MOYENNE)

    Le CANN bougeait peu — il est ancré sur un GLM gelé. **TabNet variait de
    11 %**, et c'est sur ce Gini qu'A6 ARBITRE : deux exécutions du même
    portefeuille pouvaient retenir deux modèles différents. Le dépôt écrit
    pourtant ailleurs « Exigence S2 : tout calcul actuariel doit être
    reproductible ».

    ⚠️ CE TEST SE MESURE DANS LES DEUX SENS. Même seed → identique ; seed
    différent → différent. Sans le second sens, un `seed` qui ne serait jamais
    lu passerait le premier.
    """

    @classmethod
    def setUpClass(cls):
        if not TORCH_OK:
            return
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        np.random.seed(3)
        cls.r_a2 = _make_r_a2(1500)
        cls.r_a3 = _make_r_a3(cls.r_a2['dataframe'])

        def _run(seed):
            return AgentA5DeepLearning(
                models_path='/tmp', audit_path='/tmp', verbose=False).run(
                result_a2=cls.r_a2, result_a3=cls.r_a3, plan=_PLAN_AUTO,
                col_cible='nb_sinistres', n_epochs=8, batch_size=128,
                generer_graphiques=False, seed=seed)

        cls.a = _run(7)
        cls.b = _run(7)
        cls.c = _run(8)

    def setUp(self):
        if not TORCH_OK:
            self.skipTest("PyTorch absent")

    @staticmethod
    def _ginis(r):
        return {m: v.get('gini_test') for m, v in r.get('metriques', {}).items()}

    def test_meme_seed_meme_calibrage(self):
        ga, gb = self._ginis(self.a), self._ginis(self.b)
        self.assertEqual(
            ga, gb,
            f"deux executions au MEME seed divergent : {ga} vs {gb} — le "
            f"calibrage n'est pas reproductible")
        print(f"    POS-A5d meme seed → identique : {ga} ✅")

    def test_seed_DIFFERENT_donne_un_calibrage_DIFFERENT(self):
        """⚠️ LE SECOND SENS : sans lui, un `seed` jamais lu passerait le
        premier test — deux exécutions seraient identiques par hasard de
        l'implémentation, pas par déclaration."""
        ga, gc = self._ginis(self.a), self._ginis(self.c)
        self.assertNotEqual(
            ga, gc,
            f"changer le seed ne change RIEN ({ga}) — le parametre n'est pas lu")
        print(f"    POS-A5d seed 7 vs 8 → different : {ga} vs {gc} ✅")

    def test_le_seed_est_INSCRIT_dans_le_rapport(self):
        """Un actuaire qui rejoue un tarif doit pouvoir retrouver le seed :
        ce qui n'est que dans le code n'existe pas pour lui."""
        self.assertEqual(self.a.get('rapport', {}).get('seed'), 7,
                         "le seed n'est pas trace dans le rapport")
        print("    POS-A5d le seed est inscrit au rapport ✅")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A5 DEEP LEARNING v1.0 — CANN + TabNet")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
