# =============================================================================
#  Tests — n2_hypotheses_clm.py : les hypothèses PROPRES à Chain Ladder / Mack
#
#  Pour chaque hypothèse : un cas clairement validé, un cas clairement en échec,
#  un cas limite. Plus deux oracles externes :
#    · CLM-H1 : E(Z) et Var(Z) contre le tableau PUBLIÉ du guide (Figure 52,
#      p81) — c'est ce qui prouve que les coquilles du guide sont bien corrigées.
#    · CLM-H4 : le cas GenIns mesuré (tail 1,114 vs 1,500, ΔAIC = 0,44).
# =============================================================================

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_clm import (
    A_JUSTIFIER, NON_TESTABLE, NON_VALIDEE, VALIDEE,
    _esperance_variance_Z, clm_h1_effet_calendaire, clm_h2_existence_facteurs,
    clm_h3_structure_variance, clm_h4_incertitude_queue, facteurs_individuels,
    verifier_hypotheses_clm,
)
from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import (
    calculer_facteurs, calculer_tail_factor_multi,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA,
)

CADENCE = np.array([0.40, 0.25, 0.15, 0.10, 0.05, 0.03, 0.02])


def triangle(volumes, cadence=CADENCE, inflation_calendaire=0.0,
             bruit=0.0, graine=11, terme_additif=0.0, variance_en_volume=False):
    """Fabrique un triangle cumulé à partir d'une cadence connue.

    · `inflation_calendaire` applique (1+g)^(i+j) aux INCRÉMENTS → effet de
      diagonale, c'est-à-dire exactement ce que CLM-H1 doit détecter.
    · `terme_additif` ajoute une constante à chaque incrément après le premier
      → la relation C[i,j+1] ~ C[i,j] cesse de passer par l'origine (CLM-H2).
    · `variance_en_volume` fait croître le bruit comme C (et non comme √C)
      → la mise à l'échelle de Mack n'est plus la bonne (CLM-H3).
    """
    rng = np.random.RandomState(graine)
    n = len(volumes)
    m = min(n, len(cadence))
    inc = np.zeros((n, m))
    for i, v in enumerate(volumes):
        for j in range(m):
            if i + j >= n:
                continue
            val = v * cadence[j] * (1.0 + inflation_calendaire) ** (i + j)
            if j > 0:
                val += terme_additif
            if bruit:
                ampleur = bruit * (val if variance_en_volume else np.sqrt(abs(val)))
                val += rng.normal(0.0, max(ampleur, 1e-9))
            inc[i, j] = max(val, 1.0)
    C = np.cumsum(inc, axis=1)
    for i in range(n):
        for j in range(m):
            if i + j >= n:
                C[i, j] = 0.0
    return C


def rupture_calendaire(ampleur, depuis, n=12):
    """Triangle sain dont les incréments sont majorés à partir d'une diagonale.

    C'est ce que CLM-H1 sait voir : une RUPTURE de régime (choc, changement de
    politique de règlement, rattrapage), et non une tendance régulière.
    """
    cadence = np.array([.35, .25, .18, .12, .06, .03, .01])
    base = triangle([3_000_000] * n, cadence=cadence)
    inc = np.diff(np.hstack([np.zeros((n, 1)), base]), axis=1)
    lignes, cols = base.shape
    for i in range(lignes):
        for j in range(cols):
            if i + j < lignes and i + j >= depuis:
                inc[i, j] *= (1.0 + ampleur)
    C = np.cumsum(inc, axis=1)
    for i in range(lignes):
        for j in range(cols):
            if i + j >= lignes:
                C[i, j] = 0.0
    return C


VOLUMES_VARIES = [1_000_000, 1_450_000, 2_100_000, 2_800_000,
                  3_600_000, 4_500_000, 5_500_000]
VOLUMES_HOMOGENES = [2_000_000, 2_010_000, 1_995_000, 2_005_000,
                     1_998_000, 2_002_000, 2_001_000]


class T1_Source_Unique_Des_Facteurs(unittest.TestCase):
    """`facteurs_individuels` remplace trois boucles identiques."""

    def test_facteurs_conformes_a_la_definition(self):
        C = triangle(VOLUMES_VARIES)
        n, _ = C.shape
        for j, colonne in enumerate(facteurs_individuels(C)):
            for i, f, c in colonne:
                self.assertLess(i + j + 1, n)          # zone connue
                self.assertAlmostEqual(c, C[i, j], places=6)
                self.assertAlmostEqual(f, C[i, j + 1] / C[i, j], places=9)
        print("    OK CLM-src facteurs individuels : position, volume et ratio exacts")

    def test_cellules_non_exploitables_ecartees(self):
        C = triangle(VOLUMES_VARIES)
        C[2, 1] = 0.0                                   # cellule inexploitable
        colonnes = facteurs_individuels(C)
        self.assertNotIn(2, [i for i, _, _ in colonnes[1]])
        self.assertNotIn(2, [i for i, _, _ in colonnes[0]])
        print("    OK CLM-src une cellule nulle retire ses deux facteurs, sans planter")


class T2_CLM_H1_Effet_Calendaire(unittest.TestCase):

    def test_oracle_formule_contre_le_tableau_publie_du_guide(self):
        """LA preuve que les coquilles du guide sont corrigées.

        Le guide publie E(Z_i) et V(Z_i) (Figure 52, p81). Sa formule ÉCRITE
        mélange l'indice i et l'effectif n_i ; la version corrigée (Mack 1994)
        reproduit son propre tableau, la version littérale non.
        """
        for n_d, esp_attendue, var_attendue in ((14, 5.534, 1.350),
                                                (12, 4.646, 1.168),
                                                (11, 4.146, 0.918),
                                                (10, 3.770, 0.986)):
            esp, var = _esperance_variance_Z(n_d)
            self.assertAlmostEqual(esp, esp_attendue, delta=0.001, msg=f"n={n_d}")
            self.assertAlmostEqual(var, var_attendue, delta=0.001, msg=f"n={n_d}")
        print("    OK CLM-H1-a formules corrigées = tableau publié du guide (4 effectifs)")

    def test_triangle_sain_validee(self):
        r = clm_h1_effet_calendaire(triangle(VOLUMES_VARIES, bruit=0.5))
        self.assertEqual(r.statut, VALIDEE)
        self.assertLess(abs(r.valeur), 1.645)
        print(f"    OK CLM-H1-b triangle sain : VALIDÉE (t = {r.valeur:+.2f})")

    def test_rupture_de_regime_non_validee(self):
        """Une RUPTURE de régime calendaire doit être détectée."""
        r = clm_h1_effet_calendaire(rupture_calendaire(0.35, depuis=6))
        self.assertEqual(r.statut, NON_VALIDEE)
        self.assertGreater(abs(r.valeur), 1.96)
        self.assertIn('année calendaire', r.message)
        print(f"    OK CLM-H1-c rupture de régime : NON VALIDÉE (t = {r.valeur:+.2f})")

    def test_inflation_constante_indetectable_par_construction(self):
        """MUR D'IDENTIFIABILITÉ, vérifié et non supposé.

        Une inflation calendaire CONSTANTE se factorise en `base_i × (1+g)^i ×
        A_j` : tous les facteurs d'une colonne deviennent identiques, le triangle
        est parfaitement régulier, et aucun test de signes ne peut rien y lire.
        Elle est absorbée par le niveau de l'année et par la cadence. Un statut
        VALIDÉE ne certifie donc PAS l'absence d'inflation — ce test verrouille
        cette limite pour qu'elle ne soit jamais présentée autrement.
        """
        C = triangle([3_000_000] * 12, cadence=np.array([.35,.25,.18,.12,.06,.03,.01]),
                     inflation_calendaire=0.30)
        for colonne in facteurs_individuels(C)[:4]:
            valeurs = {round(f, 9) for _, f, _ in colonne}
            self.assertEqual(len(valeurs), 1,
                             "l'inflation constante devrait rendre la colonne uniforme")
        self.assertEqual(clm_h1_effet_calendaire(C).statut, VALIDEE)
        print("    OK CLM-H1-f inflation CONSTANTE : indétectable par construction "
              "(mur d'identifiabilité, documenté)")

    def test_triangle_trop_court_non_testable(self):
        r = clm_h1_effet_calendaire(np.array([[100., 150., 170.],
                                              [110., 160.,   0.],
                                              [120.,   0.,   0.]]))
        self.assertEqual(r.statut, NON_TESTABLE)
        print("    OK CLM-H1-d triangle 3×3 : NON TESTABLE, aucun jugement rendu")

    def test_jamais_critique(self):
        """Le guide rejette H1 sur son propre exemple et poursuit."""
        self.assertEqual(clm_h1_effet_calendaire(triangle(VOLUMES_VARIES)).critique_pour, ())
        print("    OK CLM-H1-e non critique — conforme au guide qui rejette et poursuit")


class T3_CLM_H2_Existence_Des_Facteurs(unittest.TestCase):

    def test_triangle_proportionnel_validee(self):
        r = clm_h2_existence_facteurs(triangle(VOLUMES_VARIES, bruit=0.4))
        self.assertEqual(r.statut, VALIDEE)
        print("    OK CLM-H2-a développement proportionnel : VALIDÉE")

    def test_terme_additif_non_validee(self):
        """Un montant fixe qui s'ajoute à chaque période : la droite ne passe
        plus par l'origine, le coefficient multiplicatif n'existe plus."""
        r = clm_h2_existence_facteurs(
            triangle(VOLUMES_VARIES, terme_additif=900_000, bruit=0.2))
        self.assertEqual(r.statut, NON_VALIDEE)
        en_echec = [d for d in r.detail if d.get('statut') == NON_VALIDEE]
        self.assertGreaterEqual(len(en_echec), 1)
        print(f"    OK CLM-H2-b terme additif : NON VALIDÉE "
              f"({len(en_echec)} colonne(s) en échec)")

    def test_volumes_homogenes_non_testable(self):
        """CAS LIMITE — sans étendue de volumes, la régression n'a aucun levier.
        On le dit, plutôt que de rendre un « validé » sans puissance."""
        r = clm_h2_existence_facteurs(triangle(VOLUMES_HOMOGENES, bruit=0.3))
        motifs = [d.get('motif') for d in r.detail]
        self.assertIn('volumes trop homogènes', motifs)
        print("    OK CLM-H2-c volumes homogènes : colonnes déclarées NON TESTABLES")

    def test_le_r2_ne_decide_pas(self):
        """Le R² dépend de l'étendue des volumes, pas de la proportionnalité :
        il est publié mais n'entre pas dans le verdict."""
        r = clm_h2_existence_facteurs(triangle(VOLUMES_VARIES, bruit=0.4))
        testees = [d for d in r.detail if d.get('statut') == VALIDEE]
        self.assertTrue(any(d.get('r2', 1.0) < 0.90 for d in testees) or testees,
                        "au moins une colonne validée doit exister")
        self.assertIn("n'entre pas dans le verdict", r.critere)
        print("    OK CLM-H2-d le R² est publié mais ne décide pas")

    def test_critique_pour_les_deux_methodes(self):
        r = clm_h2_existence_facteurs(triangle(VOLUMES_VARIES))
        self.assertEqual(set(r.critique_pour), {'chain_ladder', 'mack'})
        print("    OK CLM-H2-e critique pour Chain Ladder ET Mack")


class T4_CLM_H3_Structure_De_Variance(unittest.TestCase):

    def test_dispersion_en_racine_du_volume_validee(self):
        r = clm_h3_structure_variance(triangle(VOLUMES_VARIES, bruit=0.6))
        self.assertIn(r.statut, (VALIDEE, A_JUSTIFIER))
        print(f"    OK CLM-H3-a dispersion ∝ √C : {r.statut}")

    def test_dispersion_proportionnelle_au_volume_detectee(self):
        """La dispersion croît comme C, pas comme √C : Mack suppose l'inverse.

        Détection portée par le test COMBINÉ : prise seule, chaque colonne n'a
        que 4 à 9 observations et n'a pratiquement aucune puissance.
        """
        C = triangle([400_000 * (1.55 ** k) for k in range(15)],
                     bruit=1.2, variance_en_volume=True, graine=3)
        r = clm_h3_structure_variance(C)
        self.assertNotEqual(r.statut, VALIDEE)
        self.assertIsNotNone(r.extras.get('p_combine_fisher'))
        print(f"    OK CLM-H3-b dispersion ∝ C : {r.statut} "
              f"(p combiné = {r.extras['p_combine_fisher']})")

    def test_le_combine_ne_peut_qu_alerter_davantage(self):
        """Le test combiné ne doit JAMAIS adoucir un signal déjà vu en colonne."""
        ordre = {NON_TESTABLE: 0, VALIDEE: 1, A_JUSTIFIER: 2, NON_VALIDEE: 3}
        for volumes, bruit in (([400_000 * (1.55 ** k) for k in range(15)], 1.2),
                               (VOLUMES_VARIES, 0.6)):
            C = triangle(volumes, bruit=bruit, variance_en_volume=True, graine=3)
            r = clm_h3_structure_variance(C)
            seul = r.extras.get('statut_par_colonne_seul')
            if seul is not None:
                self.assertGreaterEqual(ordre[r.statut], ordre[seul])
        print("    OK CLM-H3-e le test combiné durcit le verdict, ne l'adoucit jamais")

    def test_triangle_trop_court_non_testable(self):
        r = clm_h3_structure_variance(np.array([[100., 150., 170.],
                                                [110., 160.,   0.],
                                                [120.,   0.,   0.]]))
        self.assertEqual(r.statut, NON_TESTABLE)
        print("    OK CLM-H3-c triangle 3×3 : NON TESTABLE")

    def test_critique_pour_mack_seul(self):
        """Le point estimate de Chain Ladder ne dépend d'aucune hypothèse de
        variance ; σ, la MSEP et les percentiles en dépendent entièrement."""
        r = clm_h3_structure_variance(triangle(VOLUMES_VARIES))
        self.assertEqual(r.critique_pour, ('mack',))
        print("    OK CLM-H3-d critique pour Mack seul, pas pour Chain Ladder")


class T5_CLM_H4_Incertitude_De_Queue(unittest.TestCase):

    def test_sans_queue_validee(self):
        C = triangle(VOLUMES_VARIES, bruit=0.3)
        f, _ = calculer_facteurs(C, 'standard')
        r = clm_h4_incertitude_queue(
            C, tail_info={'tail_factor': 1.0, 'comparaison_methodes': {}}, facteurs=f)
        self.assertEqual(r.statut, VALIDEE)
        print("    OK CLM-H4-a aucune queue appliquée : VALIDÉE")

    def test_oracle_genins_non_validee(self):
        """ORACLE MESURÉ — GenIns, queue réellement calculée : la courbe retenue
        donne 1,114143 et une concurrente à ΔAIC = 0,44 donne 1,500. Réserves
        24 289 555 € contre 43 249 597 €, soit 43,8 % d'écart."""
        G = np.array(GENINS, dtype=float)
        f, _ = calculer_facteurs(G, 'standard')
        ti = calculer_tail_factor_multi(f, risque_long=True,
                                        tail_seuil_stabilisation=1.0001)
        r = clm_h4_incertitude_queue(G, tail_info=ti, facteurs=f)
        self.assertEqual(r.statut, NON_VALIDEE)
        self.assertAlmostEqual(r.extras['tail_retenu'], 1.114143, delta=1e-5)
        rivaux = {d['methode']: d for d in r.detail}
        self.assertIn('inverse_power', rivaux)
        self.assertAlmostEqual(rivaux['inverse_power']['tail'], 1.5, delta=1e-6)
        self.assertLess(rivaux['inverse_power']['delta_aic'], 2.0)
        self.assertAlmostEqual(rivaux['log_lineaire']['reserve'], 24_289_555, delta=2)
        self.assertAlmostEqual(rivaux['inverse_power']['reserve'], 43_249_597, delta=2)
        self.assertGreater(r.valeur, 0.40)
        print(f"    OK CLM-H4-b oracle GenIns : NON VALIDÉE, réserve de "
              f"{rivaux['log_lineaire']['reserve']:,.0f} à "
              f"{rivaux['inverse_power']['reserve']:,.0f} € (écart {r.valeur:.0%})")

    def test_avertissement_accroche_aux_percentiles(self):
        G = np.array(GENINS, dtype=float)
        f, _ = calculer_facteurs(G, 'standard')
        ti = calculer_tail_factor_multi(f, risque_long=True,
                                        tail_seuil_stabilisation=1.0001)
        r = clm_h4_incertitude_queue(G, tail_info=ti, facteurs=f)
        avert = r.extras.get('avertissement_percentiles', '')
        self.assertIn('MINORÉE', avert)
        self.assertIn('queue', avert)
        print("    OK CLM-H4-c avertissement « volatilité MINORÉE » produit")

    def test_candidats_concordants_a_justifier(self):
        """CAS LIMITE — une queue est appliquée mais les courbes concordent :
        jamais VALIDÉE, jamais NON VALIDÉE."""
        C = triangle(VOLUMES_VARIES, bruit=0.2)
        f, _ = calculer_facteurs(C, 'standard')
        ti = {'tail_factor': 1.02, 'comparaison_methodes': {
            'log_lineaire':  {'tail': 1.02,  'aic': -30.0, 'retenu': True,  'echec': None},
            'exponential':   {'tail': 1.021, 'aic': -29.8, 'retenu': False, 'echec': None},
            'inverse_power': {'tail': 1.90,  'aic': -10.0, 'retenu': False, 'echec': None}}}
        r = clm_h4_incertitude_queue(C, tail_info=ti, facteurs=f)
        self.assertEqual(r.statut, A_JUSTIFIER)
        # La courbe à ΔAIC = 20 est écartée : elle est discernable, donc non retenue.
        self.assertNotIn('inverse_power', {d['methode'] for d in r.detail})
        print("    OK CLM-H4-d courbes concordantes : À JUSTIFIER, jamais VALIDÉE")

    def test_jamais_critique(self):
        C = triangle(VOLUMES_VARIES)
        f, _ = calculer_facteurs(C, 'standard')
        r = clm_h4_incertitude_queue(
            C, tail_info={'tail_factor': 1.0, 'comparaison_methodes': {}}, facteurs=f)
        self.assertEqual(r.critique_pour, ())
        print("    OK CLM-H4-e non critique — Mack continue de produire un σ")


class T6_Point_D_Entree(unittest.TestCase):

    def test_rapport_complet_sur_les_triangles_de_reference(self):
        for nom, T in (('GenIns', GENINS), ('RAA', RAA)):
            with self.subTest(triangle=nom):
                r = verifier_hypotheses_clm(np.array(T, dtype=float))
                self.assertEqual(set(r['hypotheses']),
                                 {'CLM-H1', 'CLM-H2', 'CLM-H3', 'CLM-H4'})
                self.assertEqual(r['chain_ladder']['hypotheses'],
                                 ['CLM-H1', 'CLM-H2'])
                self.assertEqual(r['mack']['hypotheses'],
                                 ['CLM-H1', 'CLM-H2', 'CLM-H3', 'CLM-H4'])
                for h in r['hypotheses'].values():
                    self.assertIn(h['statut'], (VALIDEE, A_JUSTIFIER,
                                                NON_VALIDEE, NON_TESTABLE))
                    self.assertTrue(h['message'])
                    self.assertTrue(h['source_critere'])
        print("    OK CLM-entrée rapport complet sur GenIns et RAA")

    def test_provenance_des_seuils_toujours_explicite(self):
        """Un seuil de jugement ne doit JAMAIS pouvoir se lire comme une
        exigence du guide."""
        r = verifier_hypotheses_clm(np.array(GENINS, dtype=float))
        self.assertIn('guide', r['hypotheses']['CLM-H1']['source_critere'])
        for code in ('CLM-H2', 'CLM-H3', 'CLM-H4'):
            src = r['hypotheses'][code]['source_critere']
            self.assertIn('jugement', src.lower())
            self.assertNotIn('guide IA 2023 pour', src)
        print("    OK CLM-entrée provenance des seuils : guide pour H1, jugement pour H2/H3/H4")

    def test_aucune_consequence_tiree(self):
        """VERROU DE PÉRIMÈTRE — ce module PRODUIT des verdicts, il n'en TIRE
        rien. Aucun score, aucun poids, aucune exclusion."""
        import ast, inspect
        import direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_clm as mod
        arbre = ast.parse(inspect.getsource(mod))
        noms = {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name)}
        noms |= {n.attr for n in ast.walk(arbre) if isinstance(n, ast.Attribute)}
        for interdit in ('methodes_incluses', 'scores_confiance', 'poids',
                         'best_estimate', 'seuil_score'):
            self.assertNotIn(interdit, noms,
                             f"'{interdit}' : ce module ne doit tirer aucune conséquence")
        print("    OK CLM-entrée verrou de périmètre : aucune conséquence tirée")


if __name__ == '__main__':
    unittest.main()
