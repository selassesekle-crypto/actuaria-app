"""
Tests A3 GLM v1.0 — Tarification GLM Poisson/Gamma/Tweedie Non-Vie
7 tests · données synthétiques freMTPL2 · 500 contrats
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))
from core.plan_tarifaire import PlanTarifaire

# Phase 1 : A3.run() reçoit le PLAN signé et en dérive ses variables candidates
# (plan.colonnes_produites()). Ces fixtures sont toutes de type auto (freMTPL2-like)
# → plan auto. Le plan restreint les candidates aux colonnes qu'il produit : les
# colonnes absentes du plan sont IGNORÉES — exactement comme VARS_GLM['auto'] (qui
# en était dérivé) le faisait avant la Phase 1.
_PLAN_AUTO = PlanTarifaire.depuis_yaml(os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')),
    'plans', 'auto.yaml'))


def _make_r_a2(n=2000):
    """Result A2 synthétique avec données freMTPL2-like pour GLM.
    n=2000 et bonus_malus fortement discriminant pour garantir
    qu'au moins 1 variable est retenue par le stepwise backward.
    """
    np.random.seed(42)
    exposition  = np.random.uniform(0.1, 1.0, n)
    # bonus_malus dans [50, 350] — effet multiplicatif fort sur la fréquence
    bonus_malus = np.random.uniform(50, 350, n)
    # lambda proportionnel au bonus_malus : fort signal actuariel
    lam = 0.04 * exposition * (bonus_malus / 100.0)
    nb_sin     = np.random.poisson(lam, n).astype(float)
    cout       = np.where(nb_sin > 0, np.random.gamma(2, 400, n), 0.0)
    df = pd.DataFrame({
        'nb_sinistres':         nb_sin,
        'cout_total_sinistres': cout,
        'exposition':           exposition,
        'age':                  np.random.randint(18, 75, n).astype(float),
        'bonus_malus':          bonus_malus,
        'puissance_fiscale':    np.random.randint(4, 15, n).astype(float),
        'densite_population':   np.random.uniform(10, 5000, n),
        'log_exposition':       np.log(np.maximum(exposition, 1e-6)),
        'prime_pure':           cout * exposition,
    })
    return {
        'success': True, 'dataframe': df, 'branche': 'auto',
        'statut_rag': 'VERT', 'parametres': {}, 'rapport': {},
        'commentaire': 'OK', 'audit_id': 'A2_TEST', 'erreur': None,
    }


class TestA3GLM(unittest.TestCase):
    """A3 GLM — Calibration Poisson/Gamma/Tweedie, Gini, relativités, H1-H4."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        cls.agent = AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
        cls.r_a2  = _make_r_a2(500)
        cls.r     = cls.agent.run(result_a2=cls.r_a2, plan=_PLAN_AUTO,
                                  generer_graphiques=False)

    def test_a3(self):
        r = self.r

        # ST1 — Pipeline sans erreur
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        self.assertIn(r['statut_rag'], ['VERT', 'AMBRE', 'ROUGE'])
        print(f"    ST1 Pipeline ✅ | statut={r['statut_rag']}")

        # ST2 — Les 3 modèles GLM calibrés
        # Note : Tweedie peut ne pas avoir 'gini' si peu de sinistres en test
        met = r['metriques']
        for modele in ['poisson', 'gamma', 'tweedie']:
            self.assertIn(modele, met, f"Modèle {modele} manquant")
            m = met[modele]
            self.assertIn('aic', m)
            self.assertGreater(m.get('aic', 0), 0)
            # Gini présent uniquement si données test suffisantes
            if 'gini' in m:
                # ⚠ Borne INFÉRIEURE portée de 0,0 à −1,0 (auto-audit 11/07/2026).
                # Cette assertion encodait l'ANCIEN comportement : le Gini était
                # écrêté à [0, 1], ce qui masquait le cas le plus dangereux —
                # un Gini NÉGATIF, c'est-à-dire un modèle ANTI-SÉLECTIF (il fait
                # payer moins les mauvais risques). Le Gini est désormais rapporté
                # à sa valeur vraie ; sur cette fixture synthétique de petite
                # taille, il vaut ≈ −0,05 : du bruit autour de zéro, le GLM n'y
                # ayant quasiment aucun signal à capter. C'est une information
                # honnête, pas une régression — et le gate d'A6 rend désormais un
                # Gini négatif DISQUALIFIANT (ROUGE).
                self.assertGreaterEqual(m['gini'], -1.0)
                self.assertLessEqual(m['gini'], 1.0)
        print(f"    ST2 3 GLM calibrés ✅ | Poisson AIC={met['poisson'].get('aic',0):.0f} "              f"Gini={'oui' if 'gini' in met['poisson'] else 'N/A (peu sinistres)'}")

        # ST3 — Gini Poisson calculé et dans les bornes actuarielles [−1, 1]
        # (borne inférieure portée de 0,0 à −1,0 — voir ST2 : l'écrêtage à zéro
        #  masquait l'anti-sélection, le cas le plus dangereux en tarification)
        gini_p = met['poisson'].get('gini', 0)
        self.assertGreaterEqual(gini_p, -1.0)
        self.assertLessEqual(gini_p, 1.0)
        print(f"    ST3 Gini Poisson ✅ | Gini={gini_p:.4f}")

        # ST4 — Stepwise backward : au moins 1 variable retenue
        # (n=2000 avec bonus_malus fortement discriminant garantit la sélection)
        vars_ret = met['poisson'].get('vars_retenues', [])
        self.assertIsInstance(vars_ret, list)
        self.assertGreater(len(vars_ret), 0,
            "Aucune variable retenue — vérifier la puissance statistique des données")
        print(f"    ST4 Stepwise ✅ | {len(vars_ret)} var(s) retenue(s) : {vars_ret[:3]}")

        # ST5 — Relativités tarifaires exp(β) présentes et cohérentes
        rels = r.get('relativites_poisson', {})
        self.assertIsInstance(rels, dict)
        self.assertGreater(len(rels), 0,
            "Aucune relativité — bonus_malus doit être retenu par le stepwise")
        # Accès sécurisé : guard explicite avant iteration
        rels_list = list(rels.items())
        first_var, first_rel = rels_list[0]
        for key in ['beta', 'relativite', 'ic95_low', 'ic95_high', 'pvalue']:
            self.assertIn(key, first_rel, f"Clé '{key}' manquante dans relativités")
        # exp(β) strictement positif par construction mathématique
        for var, d in rels.items():
            self.assertGreater(d['relativite'], 0.0,
                f"Relativité nulle/négative pour '{var}' : {d['relativite']}")
        # IC 95% cohérent : bas ≤ relativité ≤ haut
        for var, d in rels.items():
            self.assertLessEqual(d['ic95_low'], d['relativite'] + 1e-9,
                f"IC bas > relativité pour '{var}'")
            self.assertGreaterEqual(d['ic95_high'], d['relativite'] - 1e-9,
                f"IC haut < relativité pour '{var}'")
        print(
            f"    ST5 Relativités ✅ | {len(rels)} var(s) | "
            f"ex: {first_var}={first_rel['relativite']:.3f} "
            f"[{first_rel['ic95_low']:.3f}, {first_rel['ic95_high']:.3f}]"
        )

        # ST6 — Standard ActuarIA : clés obligatoires
        for key in ['excel_bytes', 'hypotheses', 'audit_trail']:
            self.assertIn(key, r, f"Clé '{key}' manquante dans le résultat")
        self.assertIsInstance(r['excel_bytes'], bytes)
        self.assertIsInstance(r['audit_trail'], dict)
        hyp = r['hypotheses']
        for hkey in ['h1_poisson', 'h2_homosc', 'h3_ajustement', 'h4_stabilite',
                     'h5_deviance']:
            self.assertIn(hkey, hyp, f"Hypothèse '{hkey}' manquante")
        print(f"    ST6 Standard ActuarIA ✅ | excel={len(r['excel_bytes'])} bytes | "
              f"H1={hyp['h1_poisson']['statut']} H2={hyp['h2_homosc']['statut']} "
              f"H3={hyp['h3_ajustement']['statut']} H4={hyp['h4_stabilite']['statut']} "
              f"H5={hyp['h5_deviance']['statut']}")

        # ST7 — Cohérence AIC : Poisson AIC > 0, déviance nulle > déviance
        m_p = met['poisson']
        self.assertGreater(m_p['deviance_nulle'], m_p.get('deviance', 0),
            "Déviance nulle doit être > déviance du modèle")
        self.assertGreater(m_p.get('pseudo_r2', 0), 0,
            "Pseudo-R² doit être positif")
        print(f"    ST7 Cohérence AIC ✅ | déviance={m_p.get('deviance',0):.2f} < "
              f"nulle={m_p['deviance_nulle']:.2f} | pseudo-R²={m_p.get('pseudo_r2',0):.4f}")




def _make_r_a2_credibilite(n_groupes=30, n_par_groupe=60):
    """
    Result A2 avec structure de groupe (id_flotte) et λ connu par groupe,
    conçu spécifiquement pour valider numériquement la crédibilité
    Bühlmann-Straub — audit V4 point #14 (aucun test dédié n'existait
    avant ce correctif, alors que le point #5 de l'audit avait révélé
    un bug quantifié de ~275× sur l'estimateur σ²_intra).

    λ_i ~ Gamma(shape=4, scale=0.025) — hétérogénéité inter-groupes connue
    et contrôlée par construction (moyenne théorique ≈ 0.10).
    """
    np.random.seed(7)
    lambda_vrai = np.random.gamma(shape=4, scale=0.025, size=n_groupes)
    flottes = [f'F{i:03d}' for i in range(n_groupes)]

    id_flotte_list, expo_list, nb_sin_list = [], [], []
    for f, lam in zip(flottes, lambda_vrai):
        expo_f = np.random.uniform(0.3, 1.0, n_par_groupe)
        nb_sin_f = np.random.poisson(lam * expo_f)
        id_flotte_list.extend([f] * n_par_groupe)
        expo_list.extend(expo_f)
        nb_sin_list.extend(nb_sin_f)

    n = n_groupes * n_par_groupe
    nb_sin = np.array(nb_sin_list, dtype=float)
    expo   = np.array(expo_list, dtype=float)
    cout   = np.where(nb_sin > 0, np.random.gamma(2, 400, n), 0.0)

    df = pd.DataFrame({
        'nb_sinistres':         nb_sin,
        'cout_total_sinistres': cout,
        'exposition':           expo,
        'age':                  np.random.randint(18, 75, n).astype(float),
        'bonus_malus':          np.random.uniform(50, 350, n),
        'prime_pure':           cout * expo,
        'id_flotte':            id_flotte_list,
    })
    return {
        'success': True, 'dataframe': df, 'branche': 'auto',
        'statut_rag': 'VERT', 'parametres': {}, 'rapport': {},
        'commentaire': 'OK', 'audit_id': 'A2_TEST_CRED', 'erreur': None,
    }, lambda_vrai


class TestA3CredibiliteBuhlmannStraub(unittest.TestCase):
    """
    Crédibilité Bühlmann-Straub — validation numérique à paramètres connus.

    Audit V4 point #14 : ce test aurait immédiatement détecté le bug
    corrigé au point #5 (σ²_intra sous-estimé d'un facteur ~275×,
    provoquant Z≈1 même pour des petites flottes — annulant l'effet
    protecteur de la crédibilité). Il protège contre toute régression
    future sur ce mécanisme.

    Réf. : Bühlmann & Gisler (2005), "A Course in Credibility Theory
    and Its Applications", §4.2 (cas particulier Poisson-Bühlmann-Straub).
    """

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        cls.agent = AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
        cls.r_a2, cls.lambda_vrai = _make_r_a2_credibilite(n_groupes=30, n_par_groupe=60)
        cls.r = cls.agent.run(result_a2=cls.r_a2, plan=_PLAN_AUTO,
                              generer_graphiques=False)

    def test_credibilite(self):
        r = self.r
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")

        cred = r.get('credibilite', {})
        self.assertTrue(cred.get('appliquee'), "Crédibilité B-S non appliquée")
        print(f"    CRED1 Appliquée ✅ | n_groupes={cred.get('n_groupes')}")

        # CRED2 — σ²_intra doit être égal à μ_marché (Bühlmann-Gisler §4.2),
        # PAS à une moyenne pondérée de (μ_obs_i/n_i) — c'était le bug V4.
        mu_marche    = cred.get('mu_marche', 0)
        sigma2_intra = cred.get('sigma2_intra', 0)
        self.assertAlmostEqual(
            sigma2_intra, mu_marche, delta=max(mu_marche * 0.01, 1e-6),
            msg=(
                f"σ²_intra ({sigma2_intra}) doit être ≈ μ_marché ({mu_marche}) "
                "sous hypothèse Poisson — régression possible sur le fix V4 point #5."
            )
        )
        print(f"    CRED2 σ²_intra=μ_marché ✅ | {sigma2_intra:.6f} ≈ {mu_marche:.6f}")

        # CRED3 — k doit être strictement positif et d'un ordre de grandeur
        # cohérent avec les paramètres simulés (garde-fou contre un nouveau
        # bug dimensionnel qui donnerait un k proche de 0 ou aberrant).
        k = cred.get('k', 0)
        self.assertGreater(k, 0.1, f"k trop faible ({k}) — sur-crédibilisation suspecte")
        self.assertLess(k, 1000, f"k excessif ({k}) — sous-crédibilisation suspecte")
        print(f"    CRED3 k cohérent ✅ | k={k:.4f}")

        # CRED4 — Z_moyen ne doit PAS être quasi-systématiquement proche de 1.
        # C'était le symptôme concret du bug V4 : même les petites flottes
        # recevaient un facteur de crédibilité ≈1 (aucune protection).
        z_moyen = cred.get('z_moyen', 0)
        self.assertLess(z_moyen, 0.95,
            f"Z_moyen={z_moyen:.4f} trop proche de 1 — la crédibilité ne "
            "ramène plus les groupes vers le marché (régression du bug V4 ?)")
        self.assertGreater(z_moyen, 0.05,
            f"Z_moyen={z_moyen:.4f} trop proche de 0 — sur-lissage suspect")
        print(f"    CRED4 Z_moyen protecteur ✅ | Z_moyen={z_moyen:.4f}")

        # CRED5 — Cohérence de la formule : k = σ²_intra / σ²_entre
        # (la docstring était inversée avant le fix V4 point #5 — ce test
        # vérifie la relation numérique réelle, pas seulement la docstring).
        sigma2_entre = cred.get('sigma2_entre', 0)
        if sigma2_entre > 1e-12:
            k_recalcule = sigma2_intra / sigma2_entre
            self.assertAlmostEqual(k, k_recalcule, delta=max(k * 0.01, 1e-6),
                msg="k renvoyé incohérent avec σ²_intra/σ²_entre")
        print(f"    CRED5 Formule k=σ²_intra/σ²_entre cohérente ✅")


class TestConformiteA3(unittest.TestCase):
    """
    A3 utilisait un test d'appartenance STRICT à COLS_GENRE_INTERDITES
    (6 noms exacts) au lieu de la fonction partagée filtrer_genre(). Il ne
    bénéficiait donc pas de l'élargissement du filtre (racines, casse,
    one-hot, civilité) décidé après l'audit V9 : une colonne 'sexe_M'
    pré-encodée par le client entrait dans le GLM — prouvé par exécution
    (11/07/2026). Par ailleurs, son chemin de repli (toutes les colonnes
    numériques quand la sous-branche n'est pas reconnue) n'était protégé
    contre la fuite de données que par une liste noire de noms exacts.
    Les deux filtres partagés du module plateforme sont désormais appliqués.

    ⚠ MISE À JOUR PHASE 1 — mécanisme RÉELLEMENT exercé par ce test.
    Le « chemin de repli » évoqué ci-dessus N'EXISTE PLUS : A3.run() exige un
    plan signé et dérive ses candidates de plan.colonnes_produites() — plus de
    sous-branche à deviner, plus de repli « toutes colonnes numériques ». Une
    colonne genre BRUTE et pré-encodée absente du plan — 'sexe_M' ici — est donc
    écartée par la LISTE BLANCHE DU PLAN, EN AMONT de filtrer_genre. Ce test
    vérifie désormais cette exclusion par liste blanche ; ses assertions (aucune
    variable genre ni sinistralité dans le GLM) restent exactes et pertinentes.
    L'élargissement de filtrer_genre lui-même — le cas où une colonne prohibée
    PEUT encore devenir candidate — est exercé là où ce risque subsiste : la
    réinjection d'une colonne '*_enc' (test V10-B1 ci-dessous : 'titre_enc' →
    filtrer_genre) et les contrôles non contournables de construire_matrice_x
    (INV-3 / INV-3b / INV-4 dans test_invariants.py).
    """

    def test_genre_preencode_et_sinistralite_brute_exclus_du_glm(self):
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        np.random.seed(4)
        n = 3000
        expo = np.random.uniform(.1, 1, n)
        bm = np.random.uniform(50, 350, n)
        sexe_M = np.random.binomial(1, 0.5, n).astype(float)
        nb = np.random.poisson(.06 * expo * (bm / 100) * (1 + 0.8 * sexe_M), n).astype(float)
        df = pd.DataFrame({
            'id_contrat': range(n), 'nb_sinistres': nb,
            'cout_total_sinistres': np.where(nb > 0, np.random.gamma(2, 500, n), 0.),
            'exposition': expo,
            'age': np.random.randint(18, 80, n).astype(float),
            'bonus_malus': bm,
            'sexe_M': sexe_M,                                    # genre pré-encodé
            'Sexe': np.random.binomial(1, .5, n).astype(float),  # variante de casse
            'montant_sinistres': np.where(nb > 0, np.random.gamma(2, 400, n), 0.),
            'puissance_fiscale': np.random.randint(4, 15, n).astype(float),
            'annee_souscription': np.random.choice([2020, 2021, 2022, 2023], n),
        })
        a1 = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        a2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        a3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
        r3 = a3.run(result_a2=a2.run(result_a1=a1.run(
                        branche='non_vie', sous_branche='auto', dataframe=df),
                        plan=_PLAN_AUTO),
                    plan=_PLAN_AUTO, generer_graphiques=False)
        self.assertTrue(r3['success'])
        vars_glm = r3['metriques']['poisson'].get('vars_retenues', [])
        genre = [v for v in vars_glm if 'sexe' in v.lower() or 'genre' in v.lower()]
        self.assertEqual(genre, [],
            f"FUITE GENRE dans le GLM (CJUE C-236/09) : {genre}")
        fuite = [v for v in vars_glm
                 if 'sinistre' in v.lower() or 'cout_' in v.lower()]
        self.assertEqual(fuite, [],
            f"FUITE DE DONNÉES dans le GLM : {fuite}")
        print(f"    A3-CONF Genre et sinistralité exclus du GLM ✅ | vars={vars_glm}")


class TestAuditV10_B1_ContournementA3(unittest.TestCase):
    """
    AUDIT V10 — BLOQUANT B1. Ce test DOIT échouer sur le code d'avant correctif.

    A3 appelait filtrer_features() sur `vars_prioritaires`, puis un bloc situé
    vingt lignes plus bas RÉINJECTAIT toute colonne `*_enc` du DataFrame, gardé
    par la seule liste noire statique COLS_A_EXCLURE (sans aucune variable de
    genre). Le filtre était donc intégralement contourné.

    Prouvé par le certificateur V10 : un fichier client contenant une colonne
    'titre' (M./Mme — civilité, proxy parfait du genre) était encodé par A2 en
    'titre_enc', réinjecté, et retenu par le GLM avec β = −0,476 (p = 5,5e-13),
    soit 37,9 % d'écart de tarif entre hommes et femmes. CJUE C-236/09.

    ⚠ Le test de conformité A3 précédent n'injectait QUE des colonnes numériques
    sans '_enc' dans le nom : il ne pouvait structurellement pas exercer le
    chemin vulnérable. Un test de non-régression qui ne peut pas échouer sur le
    code bogué ne prouve rien. Celui-ci porte une colonne '_enc' prohibée.
    """

    def test_colonne_enc_prohibee_n_atteint_pas_le_glm(self):
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        rng = np.random.default_rng(42)
        N = 6000
        age = rng.integers(18, 85, N)
        bm = np.clip(rng.normal(0.9, 0.2, N), 0.5, 3.5)
        sexe = rng.choice(['M', 'F'], N)
        # Effet de risque VOLONTAIREMENT injecté dans le genre : le GLM a donc
        # un intérêt statistique à retenir la civilité s'il y a accès.
        lam = 0.10 * np.exp(0.5 * (age < 25) + 0.4 * np.log(bm) + 0.35 * (sexe == 'M'))
        nb = rng.poisson(lam)
        df = pd.DataFrame({
            'id_contrat': [f'C{i:06d}' for i in range(N)],
            'annee_souscription': rng.choice([2021, 2022, 2023, 2024], N),
            'exposition': np.clip(rng.beta(5, 1, N), 0.05, 1.0),
            'age': age, 'bonus_malus': bm,
            'anciennete_permis': np.clip(age - 18, 0, None),
            'puissance_fiscale': rng.integers(4, 15, N),
            'csp': rng.choice(['Cadre', 'Employe', 'Retraite'], N),
            'usage': rng.choice(['Prive', 'Pro'], N),
            'antecedents_sinistres_n1': rng.poisson(0.15, N),
            # ⚠ colonnes prohibées, noms 100 % réalistes en SI d'assureur :
            'titre': np.where(sexe == 'M', 'M.', 'Mme'),        # proxy genre
            'sinistralite_categorie': rng.choice(['Faible', 'Forte'], N),  # fuite
            'nb_sinistres': nb,
            'cout_total_sinistres': np.where(nb > 0, rng.gamma(2, 1200, N), 0.),
        })
        a1 = AgentA1Ingestion(audit_path='/tmp', verbose=False)
        a2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False)
        a3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
        r2 = a2.run(result_a1=a1.run(branche='non_vie', sous_branche='auto',
                                     dataframe=df), plan=_PLAN_AUTO)

        r3 = a3.run(result_a2=r2, plan=_PLAN_AUTO, generer_graphiques=False)
        self.assertTrue(r3['success'], f"A3 a échoué : {r3.get('erreur')}")
        vars_glm = r3['metriques']['poisson'].get('vars_retenues', [])

        genre = [v for v in vars_glm
                 if 'titre' in v.lower() or 'sexe' in v.lower() or 'genre' in v.lower()]
        self.assertEqual(genre, [],
            f"FUITE GENRE dans la matrice de conception du GLM : {genre} "
            f"(CJUE C-236/09 — variable légalement prohibée en tarification)")
        fuite = [v for v in vars_glm if 'sinistral' in v.lower()]
        self.assertEqual(fuite, [],
            f"FUITE DE DONNÉES dans le GLM : {fuite}")
        print(f"    V10-B1 Colonne *_enc prohibée écartée du GLM ✅ | vars={vars_glm}")


class T_Un_Verdict_Ne_Se_Rend_Pas_Sans_Mesure(unittest.TestCase):
    """CONTRÔLE POSITIF — la leçon V14, étendue à A3.

    ⚠️ ELLE N'A ÉTÉ APPLIQUÉE QU'À A6, et A3 porte les deux formes du défaut
    qu'elle nomme : un contrôle qui ACCEPTE sans avoir rien mesuré. Deux des
    cinq hypothèses d'A3 rendent VERT sur une absence — et trois d'entre elles
    plafonnent le statut d'A6.

    ⚠️ LE CORRECTIF EXISTE DÉJÀ, DANS A4 : « une calibration non testée n'est
    pas une calibration validée » — H4 y vaut AMBRE par défaut, et son écart
    sort `None` plutôt que `0.0`. Il n'a jamais été reporté sur A3.
    """

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        cls.agent = AgentA3GLM(models_path='/tmp', audit_path='/tmp',
                               verbose=False)

    def test_H1_sans_donnee_ne_rend_pas_un_verdict_FAVORABLE(self):
        """⚠️ MESURÉ : sans colonne de fréquence, H1 publie « Var/E = 1.30 < 2
        → Distribution Poisson valide ✅ » sur les valeurs `(1.30, 0.05,
        0.065)` codées en dur. Une hypothèse plafonnante rend donc VERT sur des
        chiffres que personne n'a calculés."""
        v = self.agent._valider_hypotheses_glm(
            pd.DataFrame({'sans_cible': [1, 2, 3]}), {}, {})
        h1 = v['h1_poisson']
        self.assertNotEqual(
            h1['statut'], 'VERT',
            f"H1 rend VERT sans donnée, sur ratio={h1['ratio_disp']}, "
            f"moyenne={h1['mean_y']}, variance={h1['var_y']} — trois valeurs "
            f"fabriquées publiées comme une mesure")
        print(f"    POS-A3a H1 sans donnée → {h1['statut']} ✅")

    def test_H4_non_testee_ne_vaut_pas_VALIDEE(self):
        """⚠️ LE DÉFAUT EXACT CORRIGÉ DANS A4 ET NON REPORTÉ ICI. A3 initialise
        `h4_statut = "VERT"` avec le message « Stabilité relativités NON
        testée » : le verdict et le message se contredisent, et c'est le
        verdict que le verrou d'A6 lirait."""
        v = self.agent._valider_hypotheses_glm(
            pd.DataFrame({'x': [1, 2, 3]}), {}, {})
        h4 = v['h4_stabilite']
        self.assertIn('test', h4['message'].lower(),
                      "prémisse : ce cas doit bien être un « non testé »")
        self.assertNotEqual(
            h4['statut'], 'VERT',
            f"H4 vaut VERT avec le message « {h4['message'][:56]} » — une "
            f"stabilité non testée n'est pas une stabilité validée")
        print(f"    POS-A3b H4 non testée → {h4['statut']} ✅")

    def test_le_seuil_H3_annonce_est_le_seuil_APPLIQUE(self):
        """⚠️ LA DOCSTRING ANNONCE TROIS BANDES, LE CODE EN A QUATRE.
        « Gini ∈ [0.08, 0.15] → acceptable ⚠️ » dit la docstring ; mesuré, un
        Gini de 0,12 sort VERT. Une phrase de portée se mesure comme un
        chiffre."""
        bandes = {}
        for g in (0.20, 0.12, 0.09, 0.05):
            v = self.agent._valider_hypotheses_glm(
                pd.DataFrame({'x': [1]}), {}, {'poisson': {'gini': g}})
            bandes[g] = v['h3_ajustement']['statut']
        self.assertEqual(
            bandes[0.12], 'AMBRE',
            f"Gini 0,12 sort {bandes[0.12]} alors que la docstring place "
            f"[0.08 ; 0.15] en « acceptable ⚠️ » : {bandes}")
        print(f"    POS-A3c bandes H3 conformes à l'annonce : {bandes} ✅")

    def test_la_prime_pure_Tweedie_NE_DEPEND_PAS_de_l_exposition(self):
        """⚠️ CORRECTIF `0d2b9c2` APPLIQUÉ AU FIT, PAS AU PREDICT.
        `_calibrer_tweedie` ajuste et prédit SANS offset — sa propre docstring
        l'exige : « Ajouter offset=log(expo) appliquerait l'exposition DEUX
        FOIS → la prime pure prédite deviendrait proportionnelle à
        l'exposition ». Or `_calculer_predictions` la prédit AVEC
        `offset=offset`.

        ⚠️ MESURÉ : corr(prime_pure_tweedie, exposition) = +0,51 ; un contrat
        à forte exposition reçoit une prime 4,4× celle d'un contrat identique
        à faible exposition. La prime pure est un TAUX ANNUEL : elle est
        exposure-indépendante par construction."""
        # ⚠️ UNE FIXTURE OÙ LE TWEEDIE RETIENT QUELQUE CHOSE. `_make_r_a2` tire
        # le coût indépendamment des facteurs : le Tweedie n'y garde aucune
        # variable, `prime_pure_tweedie` n'est pas produite, et le contrôle se
        # sauterait — donc ne prouverait rien. Ici le COÛT dépend du
        # bonus-malus, comme la fréquence.
        rng = np.random.default_rng(17)
        n = 3000
        expo_f = rng.uniform(0.15, 1.0, n)
        bm = rng.uniform(50, 350, n)
        nb = rng.poisson(0.10 * expo_f * (bm / 100.0)).astype(float)
        cout_f = np.where(nb > 0, rng.gamma(2, 200 * (bm / 100.0)), 0.0)
        r_a2 = _make_r_a2(n)
        r_a2['dataframe'] = pd.DataFrame({
            'nb_sinistres': nb, 'cout_total_sinistres': cout_f,
            'exposition': expo_f, 'bonus_malus': bm,
            'age': rng.integers(18, 75, n).astype(float),
            'puissance_fiscale': rng.integers(4, 15, n).astype(float),
            'log_exposition': np.log(np.maximum(expo_f, 1e-6)),
            'prime_pure': cout_f / np.maximum(expo_f, 1e-6),
        })
        r = self.agent.run(result_a2=r_a2, plan=_PLAN_AUTO,
                           generer_graphiques=False)
        self.assertTrue(r['success'], f"Erreur : {r.get('erreur')}")
        pred = r['predictions'].get('prime_pure_tweedie')
        self.assertIsNotNone(
            pred, "prémisse du contrôle : le Tweedie doit avoir retenu au "
                  "moins une variable, sinon rien n'est prédit et le test "
                  "ne prouverait rien")
        expo = r['dataframe']['exposition'].values
        corr = float(np.corrcoef(np.asarray(pred, dtype=float), expo)[0, 1])
        self.assertLess(
            abs(corr), 0.15,
            f"corr(prime_pure_tweedie, exposition) = {corr:+.4f} — la prime "
            f"pure prédite suit l'exposition, ce que le fit interdit "
            f"explicitement (correctif 0d2b9c2)")
        print(f"    POS-A3d corr(prime Tweedie, exposition) = {corr:+.4f} ✅")


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A3 GLM v1.0 — TARIFICATION POISSON/GAMMA/TWEEDIE")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
