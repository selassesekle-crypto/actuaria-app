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
    A_JUSTIFIER, NON_TESTABLE, NON_VALIDEE, PERCENTILES_MACK, VALIDEE,
    _esperance_variance_Z, clm_h1_effet_calendaire,
    clm_h2_existence_facteurs, clm_h3_structure_variance,
    clm_h4_incertitude_queue, couvertures_par_annee, facteurs_individuels,
    verifier_hypotheses_clm)
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
        """Un triangle sain doit valider — et c'est une CALIBRATION, pas un cas.

        ⚠️ CE TEST NE PORTE PLUS SUR UN SEUL TIRAGE, ET LA RAISON EST MESURÉE.
        Il employait la graine par défaut (11), sur laquelle le test de scan
        rend p = 0,0199 et conclut « à justifier ». Ce n'est pas un défaut du
        scan : sur 40 graines du même générateur, 5 rejets seulement, avec une
        p-valeur MÉDIANE de 0,307 — la graine 11 est un tirage malheureux, et
        un test bâti sur un seul d'entre eux ne dit rien de la calibration.

        On vérifie donc ce qui a un sens, et sur assez de tirages pour que le
        verrou ne soit pas lui-même à la merci du hasard : quarante triangles
        sains, dont au moins trente doivent valider. Mesuré : 35 sur 40.
        La fausse alarme du scan sur 200 triangles conformes au modèle vaut
        6,0 % pour un nominal de 5 % — contre 10,4 % pour le seul test des
        signes avant ce lot.
        """
        statuts = [clm_h1_effet_calendaire(
            triangle(VOLUMES_VARIES, bruit=0.5, graine=g)).statut
            for g in range(40)]
        n_ok = sum(1 for s in statuts if s == VALIDEE)
        self.assertGreaterEqual(
            n_ok, 30,
            "plus d'un quart des triangles sains sont signalés : la "
            "calibration a dérivé")
        print(f"    OK CLM-H1-b triangles sains : {n_ok}/40 validés "
              f"(la graine 11 tombe à « à justifier » — tirage malheureux, "
              f"médiane des p = 0,307)")

    def test_rupture_de_regime_non_validee(self):
        """Une RUPTURE de régime calendaire doit être détectée.

        ⚠️ L'ASSERTION SUR `valeur` A CHANGÉ DE NATURE, PAS DE FOND. Depuis le
        branchement du test de scan, `valeur` porte une P-VALEUR et non plus la
        statistique t du test des signes : comparer `abs(valeur)` à 1,96 n'a
        donc plus de sens. La statistique du guide reste vérifiée — elle est
        publiée dans `extras`, où ce test va désormais la chercher.
        """
        r = clm_h1_effet_calendaire(rupture_calendaire(0.35, depuis=6))
        self.assertEqual(r.statut, NON_VALIDEE)
        self.assertLess(r.valeur, 0.01)                    # p-valeur du scan
        self.assertGreater(abs(r.extras['guide_statistique']), 1.96)
        self.assertEqual(r.extras['guide_statut'], NON_VALIDEE)
        self.assertIn('année calendaire', r.message)
        print(f"    OK CLM-H1-c rupture de régime : NON VALIDÉE "
              f"(scan p = {r.valeur:.4f} ; guide t = "
              f"{r.extras['guide_statistique']:+.2f} — les deux concordent)")

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

        DÉTECTION RÉELLEMENT PORTÉE PAR LE TEST COMBINÉ, ET ICI C'EST PROUVÉ,
        PAS AFFIRMÉ. Le champ `statut_par_colonne_seul` enregistre le verdict
        qu'auraient rendu les colonnes seules : « à justifier ». Fisher, en
        agrégeant les six périodes (p = 0,0042), le durcit en « non validée ».
        C'est exactement le rôle qu'on attend de lui.

        ⚠️ CE TEST EMPLOYAIT AUPARAVANT UNE AUTRE RÉALISATION (graine 3,
        bruit 1,2) EN AFFIRMANT DÉJÀ CETTE MÊME EXPLICATION — à tort : sur
        celle-là Fisher vaut 0,128 et ne durcit rien. La détection y tenait à
        une colonne isolée comparée au seuil brut. Ce cas est désormais traité
        pour ce qu'il est, dans le test suivant.
        """
        C = triangle([400_000 * (1.55 ** k) for k in range(15)],
                     bruit=3.0, variance_en_volume=True, graine=7)
        r = clm_h3_structure_variance(C)
        self.assertEqual(r.statut, NON_VALIDEE)
        self.assertEqual(r.extras.get('statut_par_colonne_seul'), A_JUSTIFIER)
        self.assertLess(r.extras['p_combine_fisher'], 0.01)
        print(f"    OK CLM-H3-b dispersion ∝ C : colonnes seules "
              f"« {A_JUSTIFIER} », combiné p = "
              f"{r.extras['p_combine_fisher']} → {r.statut}")

    def test_une_violation_marginale_de_variance_n_est_plus_detectee(self):
        """⚠️ CE TEST DOCUMENTE UNE PERTE, IL NE LA MASQUE PAS.

        Cette violation de variance ÉTAIT détectée avant le lot
        « calibration », et ne l'est plus. Elle est réelle : le triangle est
        engendré avec une dispersion croissant comme C au lieu de √C. Voici
        pourquoi elle passe désormais, et à quel prix elle était attrapée.

        Les six p-valeurs de colonne valent
            0,0153  0,0984  0,2345  0,5270  0,8970  0,8984
        L'ancienne règle comparait chacune au seuil brut de 0,05 : la première
        passait dessous, et « le plus sévère l'emporte » suffisait à alerter.
        Mais voir une p-valeur ≤ 0,0153 EN INTERROGEANT SIX COLONNES arrive sur
        1 − (1 − 0,0153)^6 = 8,8 % des triangles parfaitement sains. Ce n'était
        donc pas un rejet au seuil de 5 % : c'en était un au seuil de 8,8 %,
        présenté comme s'il valait 5 %.

        Le test combiné ne rattrape pas non plus : Fisher vaut 0,128.

        LE COÛT EST MESURÉ, PAS SUPPOSÉ. Sur 400 triangles conformes à Mack et
        400 triangles violés, la correction fait passer la fausse alarme de
        CLM-H3 de 35,2 % à 10,5 % (et de 16,0 % à 4,2 % au niveau « non
        validée »), en conservant 94,2 % de la puissance sur une violation
        franche (Var ∝ C^2,4 : 81,5 % → 76,8 %). Ce sont les violations
        MARGINALES, comme celle-ci, qui sont perdues.

        LA BONNE RÉPONSE N'EST PAS DE RENONCER À LA CORRECTION mais d'aller
        chercher de la puissance ailleurs — une statistique qui agrège le
        triangle en UNE mesure plutôt que d'en découper six. Tant que ce n'est
        pas fait, ce test tient la trace de ce qu'on ne voit plus.
        """
        C = triangle([400_000 * (1.55 ** k) for k in range(15)],
                     bruit=1.2, variance_en_volume=True, graine=3)
        r = clm_h3_structure_variance(C)
        self.assertEqual(r.statut, VALIDEE)
        ps = sorted(d['p'] for d in r.detail if d.get('p') is not None)
        self.assertLess(ps[0], 0.05,
                        "la plus petite p-valeur est bien sous le seuil BRUT — "
                        "c'est ce qui suffisait à alerter avant la correction")
        self.assertGreater(r.extras['p_combine_fisher'], 0.05,
                           "et le test combiné ne la rattrape pas")
        print(f"    OK CLM-H3-b2 violation marginale NON détectée : p min = "
              f"{ps[0]:.4f} sur {len(ps)} colonnes (soit 8,8 % de chance sur un "
              f"triangle sain), Fisher = {r.extras['p_combine_fisher']}")

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

    def test_critique_pour_les_percentiles_de_mack_seulement(self):
        """Le point estimate de Chain Ladder ne dépend d'aucune hypothèse de
        variance ; σ, la MSEP et les percentiles en dépendent entièrement.

        ⚠️ L'ASSERTION A CHANGÉ AU LOT « MACK », ET LA DOCSTRING CI-DESSUS
        DISAIT DÉJÀ POURQUOI. Elle épinglait `('mack',)`, faute de mieux :
        `percentiles_mack` n'existait pas encore, et `mack` était le label le
        plus proche disponible. Or l'intention écrite ici est bien « σ, la MSEP
        et les percentiles », c'est-à-dire la MESURE D'INCERTITUDE — pas le
        modèle. La cible exacte est donc `PERCENTILES_MACK`, strictement
        parallèle à `PERCENTILES_BOOT` pour BOOT-H3/H4.

        La distinction n'est pas cosmétique : elle a une conséquence mesurée.
        `mack` est aussi la cible de CLM-H2, qui invalide le MODÈLE. Sans deux
        labels distincts, le porteur `percentiles_mack_publiables` se serait
        déclenché sur CLM-H2 aussi, et DEUX des cinq scénarios de référence
        auraient perdu leurs percentiles Mack sans raison.
        """
        r = clm_h3_structure_variance(triangle(VOLUMES_VARIES))
        self.assertEqual(r.critique_pour, (PERCENTILES_MACK,))
        self.assertNotIn('chain_ladder', r.critique_pour)
        self.assertNotIn('mack', r.critique_pour,
                         "CLM-H3 ne vise pas le modèle, seulement son σ")
        print("    OK CLM-H3-d critique pour les PERCENTILES de Mack "
              "seulement — ni Chain Ladder, ni le modèle de Mack")


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


class T7_Couvertures_Par_Annee(unittest.TestCase):
    """La traduction des verdicts par colonne en deux couvertures par année."""

    def _couvertures(self, C):
        return couvertures_par_annee(C, {
            'CLM-H1': clm_h1_effet_calendaire(C),
            'CLM-H2': clm_h2_existence_facteurs(C),
            'CLM-H3': clm_h3_structure_variance(C),
            'CLM-H4': clm_h4_incertitude_queue(
                C, tail_info={'tail_factor': 1.0, 'comparaison_methodes': {}},
                facteurs=calculer_facteurs(C, 'standard')[0])})

    def test_annee_la_plus_ancienne_ne_traverse_aucune_colonne(self):
        """Un triangle carré : l'année 0 est entièrement développée, plus aucun
        facteur ne la concerne — son motif est validé sans objet."""
        C = np.array(GENINS, dtype=float)
        a0 = self._couvertures(C)['annees'][0]
        self.assertEqual(a0['colonnes_traversees'], [])
        self.assertEqual(a0['couverture_motif'], VALIDEE)
        print("    OK CLM-cov-a année la plus ancienne : aucune colonne traversée")

    def test_annee_la_plus_jeune_traverse_tout(self):
        C = np.array(GENINS, dtype=float)
        n, m = C.shape
        a9 = self._couvertures(C)['annees'][n - 1]
        self.assertEqual(a9['colonnes_traversees'], list(range(0, m - 1)))
        print("    OK CLM-cov-b année la plus jeune : traverse tout le motif")

    def test_une_colonne_non_validee_ne_touche_que_les_annees_exposees(self):
        """ORACLE MESURÉ — une colonne non validée n'atteint que l'année la
        plus jeune, la seule dont le parcours la contient.

        ⚠️ RAA NE PORTE PLUS DE COLONNE NON VALIDÉE, ET C'EST LE LOT
        « CALIBRATION » QUI L'A CHANGÉ. Sa colonne 0 porte p = 0,0020. Face au
        seuil brut de 0,01 elle était « non validée » ; mais six colonnes sont
        interrogées, et le seuil de Holm au premier rang vaut 0,01/6 =
        0,00167. Elle reste sous le seuil souple (0,05/6 = 0,00833), donc le
        verdict descend à « à justifier » — l'alerte n'est pas perdue, elle est
        requalifiée. Aucune année n'est plus sous filet.

        GenIns, lui, garde sa colonne 0 non validée (p = 0,0008 ≤ 0,00167) :
        la propriété que ce test vérifie — la propagation par le PARCOURS de
        chaque année — y reste démontrée de bout en bout.
        """
        attendu = {
            # triangle : (colonnes non validées, colonnes à justifier,
            #             années sous filet)
            'GenIns': ([0], [], [9]),
            'RAA':    ([], [0], []),
        }
        for nom, T in (('GenIns', GENINS), ('RAA', RAA)):
            with self.subTest(triangle=nom):
                C = np.array(T, dtype=float)
                detail = clm_h2_existence_facteurs(C).detail
                ko = [d['colonne'] for d in detail
                      if d.get('statut') == NON_VALIDEE]
                aj = [d['colonne'] for d in detail
                      if d.get('statut') == A_JUSTIFIER]
                filet = self._couvertures(C)['synthese']['annees_sous_filet']
                self.assertEqual((ko, aj, filet), attendu[nom])
        print("    OK CLM-cov-c GenIns : colonne 0 non validée → seule l'année "
              "la plus jeune sous filet ; RAA : colonne 0 requalifiée « à "
              "justifier » par la correction de multiplicité → aucun filet")

    def test_la_queue_touche_toutes_les_annees(self):
        """CLM-H4 est global : une queue non validée dégrade la volatilité de
        TOUTES les années, y compris la plus ancienne."""
        G = np.array(GENINS, dtype=float)
        f, _ = calculer_facteurs(G, 'standard')
        ti = calculer_tail_factor_multi(f, risque_long=True,
                                        tail_seuil_stabilisation=1.0001)
        h4 = clm_h4_incertitude_queue(G, tail_info=ti, facteurs=f)
        self.assertEqual(h4.statut, NON_VALIDEE)
        cov = couvertures_par_annee(G, {
            'CLM-H2': clm_h2_existence_facteurs(G),
            'CLM-H3': clm_h3_structure_variance(G), 'CLM-H4': h4})
        for a in cov['annees']:
            self.assertEqual(a['couverture_volatilite'], NON_VALIDEE)
        print("    OK CLM-cov-d queue non validée : volatilité dégradée sur "
              "TOUTES les années, y compris l'année 0")

    def test_motif_et_volatilite_ne_se_contaminent_pas(self):
        """LE VERROU DE LA DISTINCTION — une queue non validée ne doit RIEN
        faire au motif : elle ne touche pas la réserve, seulement ce que Mack
        publie autour."""
        G = np.array(GENINS, dtype=float)
        f, _ = calculer_facteurs(G, 'standard')
        h2, h3 = clm_h2_existence_facteurs(G), clm_h3_structure_variance(G)
        sans = couvertures_par_annee(G, {
            'CLM-H2': h2, 'CLM-H3': h3,
            'CLM-H4': clm_h4_incertitude_queue(
                G, tail_info={'tail_factor': 1.0, 'comparaison_methodes': {}},
                facteurs=f)})
        avec = couvertures_par_annee(G, {
            'CLM-H2': h2, 'CLM-H3': h3,
            'CLM-H4': clm_h4_incertitude_queue(
                G, tail_info=calculer_tail_factor_multi(
                    f, risque_long=True, tail_seuil_stabilisation=1.0001),
                facteurs=f)})
        motifs_sans = [a['couverture_motif'] for a in sans['annees']]
        motifs_avec = [a['couverture_motif'] for a in avec['annees']]
        self.assertEqual(motifs_sans, motifs_avec)
        self.assertNotEqual([a['couverture_volatilite'] for a in sans['annees']],
                            [a['couverture_volatilite'] for a in avec['annees']])
        print("    OK CLM-cov-e motif intact quand seule la volatilité tombe")

    def test_non_testable_ne_degrade_ni_ne_valide(self):
        """Une colonne sans assez d'observations est une absence d'information,
        pas un échec : elle ne doit pas faire basculer une année sous filet."""
        cov = self._couvertures(np.array(GENINS, dtype=float))
        non_testables = [a for a in cov['annees']
                         if a['couverture_motif'] == NON_TESTABLE]
        self.assertTrue(non_testables)
        for a in non_testables:
            self.assertFalse(a['filet_requis'])
        print(f"    OK CLM-cov-f {len(non_testables)} année(s) NON TESTABLE : "
              f"aucune sous filet")


#: Exposition cohérente avec GenIns — un loss ratio d'environ 70 %.
#: ⚠️ INDISPENSABLE pour verrouiller le filet de sécurité : sans exposition,
#: Bornhuetter-Ferguson et Cape Cod ne tournent pas, l'année sous filet reçoit
#: Chain Ladder seule ET les années nominales aussi. Le filet devient alors
#: numériquement INVISIBLE — il ne subsiste que par le statut. Un test qui
#: prétend vérifier son effet doit placer le système là où il agit.
EXPOSITION_GENINS = np.array(GENINS, dtype=float).max(axis=1) * 1.6 / 0.70


class T8_Cablage_Dans_Le_Pipeline(unittest.TestCase):
    """Lot A — CLM tourne en N2 et n'est consommé par rien."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.provisionnement.a7_provisionnement.agent import (
            AgentA7Provisionnement)
        cls.r = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, n_sim_bootstrap=100, generer_graphiques=False,
            generer_word=False, generer_pdf_flag=False)
        cls.r_expo = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, primes=EXPOSITION_GENINS, n_sim_bootstrap=100,
            generer_graphiques=False, generer_word=False, generer_pdf_flag=False)

    def test_clm_est_calcule_en_n2(self):
        clm = self.r['n2'].get('clm', {})
        self.assertEqual(set(clm.get('hypotheses', {})),
                         {'CLM-H1', 'CLM-H2', 'CLM-H3', 'CLM-H4'})
        self.assertIn('annees', clm.get('couvertures', {}))
        print("    OK CLM-pipe-a CLM-H1..H4 et les couvertures produits en N2")

    def test_expose_dans_les_livrables_en_resume(self):
        """Visible par l'actuaire, sans alourdir l'audit du détail par colonne."""
        n2r = self.r['audit_trail']['n2_resume']
        self.assertEqual(set(n2r['clm_hypotheses']),
                         {'CLM-H1', 'CLM-H2', 'CLM-H3', 'CLM-H4'})
        self.assertIn('annees_sous_filet', n2r['clm_couvertures'])
        import json
        self.assertLess(len(json.dumps(n2r['clm_hypotheses'])), 4000)
        print("    OK CLM-pipe-b exposé en résumé dans l'audit, détail non persisté")

    def test_estimateur_standard_impose(self):
        """CLM teste les hypothèses de Mack : l'estimateur doit être le
        volume-weighted, quelle que soit la variante retenue par N2."""
        import inspect
        from direction_non_vie.provisionnement.a7_provisionnement import agent as mod
        src = inspect.getsource(mod.AgentA7Provisionnement._verifier_clm)
        self.assertIn("'standard'", src)
        self.assertNotIn('methode_cl', src)
        print("    OK CLM-pipe-c estimateur standard imposé, pas de circularité")

    def test_les_couvertures_pilotent_la_selection(self):
        """VERROU DU LOT B — l'inverse exact de celui du lot A.

        Au lot A ce test vérifiait qu'une année sous filet NE changeait PAS le
        Best Estimate, les couvertures étant exposées sans être consommées. Le
        lot B branche le mécanisme : cette assertion devient son contraire, et
        c'est le but même du lot.
        """
        n4 = self.r_expo['n4']
        cov = self.r_expo['n2']['clm']['couvertures']['synthese']
        self.assertEqual(cov['annees_sous_filet'], [9])
        # La couverture décidée en N2 se retrouve telle quelle dans la sélection.
        self.assertEqual(n4['annees_sous_filet'], [9])
        sous_filet = [d for d in n4['selection_par_annee'] if d['sous_filet']]
        self.assertEqual(len(sous_filet), 1)
        self.assertEqual(sous_filet[0]['methodes'], ['chain_ladder'])
        self.assertEqual(sous_filet[0]['motif'], NON_VALIDEE)
        # Les autres années gardent les trois méthodes, à poids égal.
        nominales = [d for d in n4['selection_par_annee'] if not d['sous_filet']]
        for d in nominales:
            self.assertEqual(len(d['methodes']), 3)
            self.assertAlmostEqual(d['poids_unitaire'], 1 / 3, places=6)
        # Et le filet ne peut jamais passer inaperçu.
        self.assertEqual(n4['statut'], 'ROUGE')
        print("    OK CLM-pipe-d l'année sous filet reçoit Chain Ladder seule, "
              "les autres les 3 méthodes à poids égal, statut ROUGE")

    def test_ne_leve_jamais(self):
        """Un échec de vérification ne doit pas empêcher un provisionnement."""
        from unittest.mock import patch
        from direction_non_vie.provisionnement.a7_provisionnement.agent import (
            AgentA7Provisionnement)
        with patch('direction_non_vie.provisionnement.a7_provisionnement.agent'
                   '.verifier_hypotheses_clm', side_effect=RuntimeError('boum')):
            r = AgentA7Provisionnement(verbose=False).run(
                source=GENINS, n_sim_bootstrap=100, generer_graphiques=False,
                generer_word=False, generer_pdf_flag=False)
        self.assertTrue(r['success'])
        self.assertIn('erreur', r['n2']['clm'])
        # Sans couvertures, aucune année n'est sous filet. Et sans exposition,
        # seul Chain Ladder est calculé (lot BF/Cape Cod) : le provisionnement
        # aboutit, simplement sans le raffinement que CLM apporte.
        # CONSTANTE MISE À JOUR — lot BF/Cape Cod : 21 794 332 → 18 680 856.
        self.assertEqual(r['n4']['annees_sous_filet'], [])
        self.assertAlmostEqual(r['n4']['best_estimate'], 18_680_856, delta=2)
        print("    OK CLM-pipe-e échec CLM : signalé, jamais fatal, "
              "provisionnement produit sans filet")


if __name__ == '__main__':
    unittest.main()
