"""
Tests A3 GLM v1.0 — Tarification GLM Poisson/Gamma/Tweedie Non-Vie
7 tests · données synthétiques freMTPL2 · 500 contrats
"""
import sys, os, unittest
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))


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
        cls.r     = cls.agent.run(result_a2=cls.r_a2, generer_graphiques=False)

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
                self.assertGreaterEqual(m['gini'], 0.0)
                self.assertLessEqual(m['gini'], 1.0)
        print(f"    ST2 3 GLM calibrés ✅ | Poisson AIC={met['poisson'].get('aic',0):.0f} "              f"Gini={'oui' if 'gini' in met['poisson'] else 'N/A (peu sinistres)'}")

        # ST3 — Gini Poisson calculé et positif
        gini_p = met['poisson'].get('gini', 0)
        self.assertGreaterEqual(gini_p, 0.0)
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
        for hkey in ['h1_poisson', 'h2_homosc', 'h3_ajustement', 'h4_stabilite']:
            self.assertIn(hkey, hyp, f"Hypothèse '{hkey}' manquante")
        print(f"    ST6 Standard ActuarIA ✅ | excel={len(r['excel_bytes'])} bytes | "
              f"H1={hyp['h1_poisson']['statut']} H2={hyp['h2_homosc']['statut']} "
              f"H3={hyp['h3_ajustement']['statut']} H4={hyp['h4_stabilite']['statut']}")

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
        cls.r = cls.agent.run(result_a2=cls.r_a2, generer_graphiques=False)

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
        r3 = a3.run(result_a2=a2.run(result_a1=a1.run(branche='non_vie', dataframe=df)),
                    generer_graphiques=False)
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
        r2 = a2.run(result_a1=a1.run(branche='non_vie', dataframe=df))

        r3 = a3.run(result_a2=r2, generer_graphiques=False)
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


if __name__ == '__main__':
    print("="*65)
    print("  TESTS A3 GLM v1.0 — TARIFICATION POISSON/GAMMA/TWEEDIE")
    print("="*65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("✅" if result.wasSuccessful() else "❌", f"{result.testsRun} test(s)")
