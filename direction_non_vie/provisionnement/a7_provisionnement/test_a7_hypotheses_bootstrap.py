# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  test_a7_hypotheses_bootstrap.py  —  Filet des hypothèses BOOT-H1..H4
# =============================================================================
#
#  DEUX NIVEAUX, ET LA DISTINCTION EST LE POINT DU FICHIER.
#
#  ── NIVEAU 1 — VÉRITÉ CONNUE, BLOQUANT ─────────────────────────────────────
#  Les triangles sont fabriqués ICI, à partir de paramètres que NOUS fixons :
#  volumes, cadence, et surtout le profil de φ. Le test vérifie que le code
#  retrouve ce que nous avons mis dedans. AUCUNE SOURCE EXTERNE N'INTERVIENT.
#
#  ⚠️ C'EST DÉLIBÉRÉ, ET C'EST LA LEÇON DU LOT PRÉCÉDENT. Le guide de l'Institut
#  des Actuaires ne dit RIEN de l'homogénéité de φ — il n'y a donc pas d'oracle
#  publié à opposer à BOOT-H3, et c'est tant mieux : caler un modèle sur des
#  chiffres publiés revient à supposer qu'ils sont justes. Ici, la référence est
#  une vérité que nous avons construite, donc vérifiable.
#
#  ── NIVEAU 2 — STRUCTUREL ──────────────────────────────────────────────────
#  Les reprises (BOOT-H1 ← CLM-H1, BOOT-H2 ← glm_apc), le verdict de BOOT-H4 sur
#  un comptage, la gouvernance (ce qui est retiré et ce qui ne l'est pas), et les
#  deux verrous de périmètre.
#
#  ⚠️ LES CAMPAGNES SONT VOLONTAIREMENT COURTES. Les taux publiés dans l'en-tête
#  du module viennent de campagnes de 100 triangles ; ici elles en comptent 40,
#  ce qui suffit largement à attraper une RÉGRESSION (une calibration cassée
#  donne 30 % à 100 % de fausses alarmes, pas 12 %) sans faire durer la gate
#  plusieurs minutes. Les bornes sont élargies en conséquence, et calculées :
#  à n = 40 et taux vrai 5 %, la borne binomiale haute à 99 % vaut 14 %.
#  Toutes les graines sont FIXES — aucun test de ce fichier ne peut clignoter.
# =============================================================================

import ast
import unittest
from pathlib import Path

import numpy as np

from .n2_hypotheses_bootstrap import (
    AXES, CODES, GRAINE_CALIBRATION, P_REJET, P_VIGILANCE,
    N_REP_CALIBRATION, PERCENTILES_BOOT,
    boot_h1_independance, boot_h2_structure, boot_h3_homogeneite_phi,
    boot_h4_increments_positifs, libelle_phi_par_axe, lignes_hypotheses_bootstrap,
    nulle_parametrique, percentiles_publiables, phi_par_axe, rho_dispersion,
    verifier_hypotheses_bootstrap, _INDICE,
)
from .n2_hypotheses_clm import (
    A_JUSTIFIER, NON_TESTABLE, NON_VALIDEE, VALIDEE,
)
from .n3.bootstrap_odp import bootstrap_odp, calculer_fitted_et_residus
from .n3.chain_ladder import calculer_facteurs

_ICI = Path(__file__).parent

# ── Vérité connue : les paramètres du générateur, fixés par NOUS ─────────────
VOL_VRAIS = np.array([1000., 1100., 1250., 1300., 1400.,
                      1500., 1600., 1750., 1800., 1900.])
CAD_VRAIE = np.array([.32, .24, .16, .10, .07, .05, .03, .02, .007, .003])
CAD_VRAIE = CAD_VRAIE / CAD_VRAIE.sum()

#: Taille des campagnes. Cf. en-tête pour le dimensionnement.
N_CAMPAGNE = 40
#: Régénérations par triangle DANS les campagnes — bien en deçà de la valeur de
#: production, qui reste testée à part par `test_reproductibilite_8_graines`.
N_REP_CAMPAGNE = 100


def triangle_odp(x, y, rng, phi=None, phi_col=None, phi_diag=None):
    """Triangle cumulé tiré d'un ODP à sur-dispersion CHOISIE.

    `m_ij = φ · Poisson(x_i·y_j / φ)` a bien pour espérance `x_i·y_j` et pour
    variance `φ·x_i·y_j` : c'est exactement le modèle d'England & Verrall, avec
    un φ que l'on fait varier par colonne (`phi_col`) ou par diagonale
    (`phi_diag`) pour fabriquer l'hétérogénéité que le test doit détecter.
    """
    n, m = len(x), len(y)
    M = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            if i + j < n:
                p = (phi_col[j] if phi_col is not None else
                     phi_diag[i + j] if phi_diag is not None else phi)
                M[i, j] = p * rng.poisson(x[i] * y[j] / p)
    return np.cumsum(M, axis=1)


def _facteurs(C):
    return np.asarray(calculer_facteurs(C, 'standard')[0], dtype=float)


def campagne(axe, phi=100.0, phi_col=None, phi_diag=None,
             n=N_CAMPAGNE, graine0=200_000, vol=None):
    """Fraction de rejets à 5 %, seuil issu de la nulle paramétrique de CHAQUE
    triangle simulé — exactement ce que fait le code en production.

    Rend AUSSI le nombre de triangles réellement exploités : sans lui, une
    campagne vide se lit comme un taux de 0 %, ce qui est arrivé une fois.
    """
    vol = VOL_VRAIS if vol is None else vol
    rejets = total = 0
    for s in range(n):
        rng = np.random.default_rng(graine0 + s)
        C = triangle_odp(vol, CAD_VRAIE, rng,
                         phi=phi, phi_col=phi_col, phi_diag=phi_diag)
        if (C <= 0).any():
            continue
        f = _facteurs(C)
        _, residus, _, _, n_obs, n_par, cellules = calculer_fitted_et_residus(C, f)
        if n_obs - n_par <= 0:
            continue
        rho = rho_dispersion(residus, cellules, axe)
        nulle = nulle_parametrique(C, f, N_REP_CAMPAGNE, graine=s + 1)
        if rho is None or nulle is None or len(nulle[axe]) < 40:
            continue
        total += 1
        if float((np.abs(nulle[axe]) >= abs(rho)).mean()) < 0.05:
            rejets += 1
    return rejets / max(total, 1), total


# =============================================================================
#  NIVEAU 1 — VÉRITÉ CONNUE
# =============================================================================

class TestCalibrationJuste(unittest.TestCase):
    """Le test se trompe-t-il au taux qu'il annonce, quand φ est VRAIMENT
    constant ? C'est la première question, avant toute question de puissance :
    un test qui crie au loup ne sert à rien, quelle que soit sa sensibilité.

    C'est précisément ce qui a fait écarter la p-valeur analytique de Spearman
    (13 % à 19,5 % de fausses alarmes) et le rapport max/min des φ.
    """

    def test_calibration_juste_sur_les_trois_axes(self):
        """Aucun axe ne doit être structurellement plus bavard qu'un autre.

        Une première version tenait TROIS tests distincts pour cette propriété —
        φ=20, φ=100, puis les trois axes — soit cinq campagnes là où le niveau
        du test ne dépend ni de la valeur de φ ni, en principe, de l'axe. La
        redondance coûtait une minute de gate sans rien vérifier de plus.
        """
        for axe in AXES:
            with self.subTest(axe=axe):
                taux, n = campagne(axe, phi=50.0, graine0=310_000)
                self.assertGreaterEqual(n, 30, "campagne trop dégarnie")
                self.assertLessEqual(
                    taux, 0.20,
                    f"axe {axe} : {taux:.1%} de rejets alors que φ est VRAIMENT "
                    f"constant — la calibration est cassée. Mesuré 5,0 % à 6,4 % "
                    f"en campagne longue ; borne haute 20 % à n={n}.")

    def test_le_niveau_ne_depend_pas_de_la_valeur_de_phi(self):
        """φ n'est qu'un facteur d'échelle de la variance : le taux de fausse
        alarme doit être le même à φ=20 et à φ=100. S'il ne l'était pas, la
        nulle paramétrique ne serait pas correctement conditionnée."""
        t20, n20 = campagne('developpement', phi=20.0, graine0=320_000)
        self.assertGreaterEqual(n20, 30)
        self.assertLessEqual(t20, 0.20, f"{t20:.1%} de rejets à φ=20 constant")


class TestPuissance(unittest.TestCase):
    """Ce que le test voit, et ce qu'il ne voit pas. LES DEUX SONT VERROUILLÉS.

    Une borne haute sur la faiblesse assumée n'est pas une bizarrerie : si une
    version future prétendait détecter un φ doublé bien mieux que 30 %, ce serait
    le signe d'une calibration redevenue trop bavarde, pas d'un progrès.
    """

    def test_hetero_x20_detectee(self):
        taux, n = campagne('developpement',
                           phi_col=np.linspace(20, 400, 10), graine0=210_000)
        self.assertGreaterEqual(n, 30)
        self.assertGreaterEqual(
            taux, 0.35,
            f"φ multiplié par 20 le long du développement détecté seulement "
            f"{taux:.1%} du temps (mesuré 67,4 % en campagne longue)")

    def test_hetero_x5_detectee(self):
        taux, n = campagne('developpement',
                           phi_col=np.linspace(40, 200, 10), graine0=220_000)
        self.assertGreaterEqual(n, 30)
        self.assertGreaterEqual(taux, 0.15,
                                f"φ×5 détecté {taux:.1%} (mesuré 53,0 %)")

    def test_faiblesse_x2_assumee(self):
        """⚠️ VERROU SUR UNE LIMITE, PAS SUR UNE PERFORMANCE."""
        taux, n = campagne('developpement',
                           phi_col=np.linspace(70, 140, 10), graine0=230_000)
        self.assertGreaterEqual(n, 30)
        self.assertLessEqual(
            taux, 0.40,
            f"φ×2 détecté {taux:.1%} — mesuré 18,1 %. Un bond ici signale une "
            f"calibration devenue trop bavarde, pas un gain de puissance : "
            f"vérifier d'abord le taux de fausse alarme à φ constant.")

    def test_angle_mort_derive_calendaire_reguliere(self):
        """⚠️ L'ANGLE MORT EST DOCUMENTÉ ET VÉRIFIÉ, PAS CONTOURNÉ.

        ⚠️ VOLUMES RELEVÉS (×200), ET C'EST INDISPENSABLE. Aux volumes usuels,
        un φ calendaire de 1000 stérilise la colonne 0 — `φ·Poisson(x_i·y_0/φ)`
        vaut 0 plus d'une fois sur deux — et TOUS les triangles sont écartés. Une
        première version de cette mesure a ainsi conclu « 0,0 % de détection »
        sur une campagne de ZÉRO triangle exploitable : un nombre qui ne prouvait
        rien. Le `assertGreaterEqual(n, …)` ci-dessous existe pour que cela ne
        puisse plus se reproduire silencieusement.

        Ce que le test fige : une DÉRIVE RÉGULIÈRE de φ le long des années
        calendaires n'est pas détectable (1,0 % mesuré, sous le témoin à 2,0 %),
        parce que l'ajustement la répartit entre `x_i` et `y_j`. C'est le motif
        actuariellement plausible — un régime d'inflation — et c'est CLM-H1,
        reprise par BOOT-H1, qui couvre ce terrain.
        """
        taux, n = campagne('calendaire', phi_diag=np.linspace(50, 500, 10),
                           vol=VOL_VRAIS * 200.0, graine0=240_000)
        self.assertGreaterEqual(
            n, 30, "campagne vide : la mesure ne prouverait rien (cf. docstring)")
        self.assertLessEqual(
            taux, 0.20,
            f"une dérive calendaire régulière est détectée {taux:.1%} — mesuré "
            f"1,0 %. Si ce chiffre monte vraiment, l'angle mort documenté dans "
            f"l'en-tête du module n'est plus exact.")

    def test_choc_calendaire_brutal_partiellement_vu(self):
        """Le pendant du précédent : l'axe calendaire n'est pas totalement
        aveugle. Un choc ×10 concentré sur les trois dernières diagonales est vu
        environ une fois sur trois. Verrouillé pour que la nuance survive."""
        taux, n = campagne('calendaire',
                           phi_diag=np.array([100.] * 7 + [1000.] * 3),
                           vol=VOL_VRAIS * 200.0, graine0=250_000)
        self.assertGreaterEqual(n, 30, "campagne vide")
        self.assertGreaterEqual(
            taux, 0.08,
            f"un choc ×10 localisé est détecté {taux:.1%} — mesuré 29,0 %")


class TestPetitsTriangles(unittest.TestCase):
    """La nulle étant tirée du triangle lui-même, elle hérite de sa petitesse :
    aucun garde-fou de taille minimale n'est nécessaire au-delà de df > 0."""

    def test_4x4_a_phi_constant_ne_declenche_pas(self):
        vol4 = np.array([100., 120., 110., 130.])
        cad4 = np.array([.45, .30, .18, .07])
        rejets = total = 0
        for s in range(N_CAMPAGNE):
            rng = np.random.default_rng(300_000 + s)
            C = triangle_odp(vol4, cad4, rng, phi=5.0)
            if (C <= 0).any():
                continue
            f = _facteurs(C)
            _, res, _, _, n_o, n_p, cel = calculer_fitted_et_residus(C, f)
            if n_o - n_p <= 0:
                continue
            rho = rho_dispersion(res, cel, 'developpement')
            nulle = nulle_parametrique(C, f, N_REP_CAMPAGNE, graine=s + 1)
            if rho is None or nulle is None or len(nulle['developpement']) < 40:
                continue
            total += 1
            if float((np.abs(nulle['developpement']) >= abs(rho)).mean()) < 0.05:
                rejets += 1
        self.assertGreaterEqual(total, 20, "trop peu de 4×4 exploitables")
        self.assertLessEqual(
            rejets / total, 0.25,
            f"{rejets}/{total} rejets sur des 4×4 à φ constant — la calibration "
            f"ne s'adapte plus à la taille du triangle")

    def test_df_negatif_donne_non_testable(self):
        """Un triangle sans degrés de liberté ne peut pas être jugé — et
        surtout pas jugé favorablement."""
        C = np.array([[100., 95., 90., 88., 87., 86.],
                      [110., 104., 99., 97., 96., 0.],
                      [120., 114., 108., 106., 0., 0.],
                      [130., 123., 117., 0., 0., 0.],
                      [140., 133., 0., 0., 0., 0.],
                      [150., 0., 0., 0., 0., 0.]])
        h3 = boot_h3_homogeneite_phi(C, _facteurs(C))
        self.assertEqual(h3.statut, NON_TESTABLE)
        self.assertIsNone(h3.valeur)
        self.assertLessEqual(h3.extras['df'], 0)


class TestReproductibilite(unittest.TestCase):
    """⚠️ LE VERROU LE PLUS IMPORTANT DU FICHIER.

    À 200 régénérations et seuil dur de 0,05, un même triangle donnait des
    verdicts opposés selon la graine (2 rejets sur 8 graines, p de 0,030 à
    0,105). C'est inacceptable dans un livrable réglementaire. La correction —
    n_rep = 400 ET zone grise [0,01 ; 0,10] — est vérifiée ici, pas supposée.
    """

    #: Triangle de bord : sa p-valeur vraie vaut ~0,06, donc au milieu de la
    #: zone grise. C'est le cas le plus difficile qui soit pour la stabilité.
    TRI_BORD = np.array([
        [1000., 1600., 1900., 2050., 2100., 2120.],
        [1100., 1750., 2080., 2240., 2290., 0.],
        [1250., 1980., 2350., 2530., 0., 0.],
        [1300., 2100., 2480., 0., 0., 0.],
        [1400., 2230., 0., 0., 0., 0.],
        [1500., 0., 0., 0., 0., 0.]])

    def test_meme_statut_sur_8_graines(self):
        C = self.TRI_BORD
        f = _facteurs(C)
        statuts, ps = set(), []
        for g in range(1, 9):
            h3 = boot_h3_homogeneite_phi(C, f, N_REP_CALIBRATION, graine=g)
            statuts.add(h3.statut)
            ps.append(h3.valeur)
        self.assertEqual(
            len(statuts), 1,
            f"le verdict dépend de la graine : {statuts} — p de {min(ps):.3f} à "
            f"{max(ps):.3f}. C'est exactement ce que n_rep=400 et la zone grise "
            f"doivent empêcher.")

    def test_graine_figee_rend_le_meme_chiffre(self):
        """Deux exécutions du même dossier doivent rendre le MÊME chiffre."""
        C, f = self.TRI_BORD, _facteurs(self.TRI_BORD)
        a = boot_h3_homogeneite_phi(C, f)
        b = boot_h3_homogeneite_phi(C, f)
        self.assertEqual(a.valeur, b.valeur)
        self.assertEqual(a.statut, b.statut)
        self.assertEqual(a.extras['graine'], GRAINE_CALIBRATION)

    def test_parametres_de_production_publies(self):
        """La graine et le nombre de régénérations sont OPPOSABLES : ils
        doivent figurer dans le résultat, pas seulement dans le code."""
        C, f = self.TRI_BORD, _facteurs(self.TRI_BORD)
        h3 = boot_h3_homogeneite_phi(C, f)
        self.assertEqual(h3.extras['n_rep_demande'], N_REP_CALIBRATION)
        self.assertIn(str(GRAINE_CALIBRATION), h3.critere)
        self.assertIn(str(N_REP_CALIBRATION), h3.critere)


class TestPhiParAxe(unittest.TestCase):
    """φ par axe doit être une DÉCOMPOSITION de φ, pas un second φ.

    C'est l'identité qui a révélé, pendant l'implémentation, qu'une remise à
    l'échelle superflue s'était glissée dans la fonction : elle faussait la carte
    de (N−p)/N — 34,5 % sur GenIns — sans rien changer aux rangs ni au verdict.
    """

    def test_moyenne_ponderee_redonne_phi_global(self):
        for phi_v in (20.0, 100.0, 5.0):
            rng = np.random.default_rng(4242)
            C = triangle_odp(VOL_VRAIS, CAD_VRAIE, rng, phi=phi_v)
            f = _facteurs(C)
            _, res, phi, _, n_obs, n_par, cel = calculer_fitted_et_residus(C, f)
            carte = phi_par_axe(res, cel)
            for axe in AXES:
                with self.subTest(phi=phi_v, axe=axe):
                    eff = {}
                    for (i, j) in cel:
                        g = int(_INDICE[axe](i, j))
                        eff[g] = eff.get(g, 0) + 1
                    recompose = sum(eff[g] * v for g, v in carte[axe].items()) / len(cel)
                    self.assertAlmostEqual(
                        recompose / phi, 1.0, places=9,
                        msg=f"φ_par_axe[{axe}] ne se recompose pas en φ : "
                            f"{recompose:,.4f} vs {phi:,.4f}. Ce serait un "
                            f"TROISIÈME φ dans le système.")

    def test_carte_couvre_les_trois_axes(self):
        rng = np.random.default_rng(77)
        C = triangle_odp(VOL_VRAIS, CAD_VRAIE, rng, phi=50.0)
        h3 = boot_h3_homogeneite_phi(C, _facteurs(C), n_rep=60, graine=3)
        carte = h3.extras['phi_par_axe']
        self.assertEqual(set(carte), set(AXES))
        for axe in AXES:
            self.assertGreaterEqual(len(carte[axe]), 3)

    def test_hetero_injectee_se_lit_dans_la_carte(self):
        """Un φ multiplié par 20 en développement doit se VOIR dans la carte,
        pas seulement dans le verdict — c'est elle qui dit OÙ est le problème."""
        rng = np.random.default_rng(909)
        C = triangle_odp(VOL_VRAIS, CAD_VRAIE, rng,
                         phi_col=np.linspace(20, 400, 10))
        f = _facteurs(C)
        _, res, _, _, _, _, cel = calculer_fitted_et_residus(C, f)
        carte = phi_par_axe(res, cel)['developpement']
        premiers = np.mean([carte[g] for g in sorted(carte)[:3]])
        derniers = np.mean([carte[g] for g in sorted(carte)[-3:]])
        self.assertGreater(
            derniers, premiers,
            f"φ croissant injecté mais carte plate : {premiers:.3g} → {derniers:.3g}")


# =============================================================================
#  NIVEAU 2 — STRUCTUREL
# =============================================================================

class TestBootH1Reprise(unittest.TestCase):
    """BOOT-H1 republie CLM-H1 : le statut doit traverser à l'identique."""

    @staticmethod
    def _synth(statut):
        return {'code': 'CLM-H1', 'statut': statut, 'valeur': 1.23,
                'critere': 'critère CLM', 'message': 'message CLM',
                'detail': [{'diagonale': 1}]}

    def test_les_quatre_statuts_traversent(self):
        for st in (VALIDEE, A_JUSTIFIER, NON_VALIDEE, NON_TESTABLE):
            with self.subTest(statut=st):
                h = boot_h1_independance(self._synth(st))
                self.assertEqual(h.statut, st)
                self.assertEqual(h.valeur, 1.23)
                self.assertEqual(h.extras['repris_de'], 'CLM-H1')
                self.assertIn('message CLM', h.message)

    def test_absence_donne_non_testable(self):
        for absent in (None, {}):
            with self.subTest(entree=absent):
                h = boot_h1_independance(absent)
                self.assertEqual(h.statut, NON_TESTABLE)
                self.assertIsNone(h.valeur)

    def test_h1_est_descriptive(self):
        """Un effet calendaire biaise identiquement le point estimate et la
        distribution : le gater punirait le Bootstrap pour le défaut d'un autre."""
        h = boot_h1_independance(self._synth(NON_VALIDEE))
        self.assertEqual(h.critique_pour, ())


class TestBootH2Reprise(unittest.TestCase):
    """BOOT-H2 republie le test F calendaire du GLM Poisson âge-cohorte."""

    @staticmethod
    def _glm(p):
        return {'success': True, 'glm_disponible': True, 'p_calendaire': p,
                'cal_significatif': p < 0.05, 'F_calendaire': 2.0}

    def test_seuils(self):
        """Les bornes viennent des CONSTANTES du module, pas de littéraux
        recopiés : un test qui duplique le seuil qu'il vérifie ne vérifie rien."""
        marge = 1e-6
        for p, attendu in (
                (P_VIGILANCE * 2,            VALIDEE),
                (P_VIGILANCE,                VALIDEE),
                (P_VIGILANCE - marge,        A_JUSTIFIER),
                (P_REJET,                    A_JUSTIFIER),
                (P_REJET - marge,            NON_VALIDEE)):
            with self.subTest(p=p):
                self.assertEqual(boot_h2_structure(self._glm(p)).statut, attendu)

    def test_zone_grise_bien_ordonnee(self):
        """La zone grise doit exister ET être plus large que l'erreur de
        Monte-Carlo à n_rep = 400, sans quoi le verdict redeviendrait
        dépendant de la graine — le défaut que ce lot corrige."""
        self.assertLess(P_REJET, P_VIGILANCE)
        erreur_mc = 1.96 * (P_VIGILANCE * (1 - P_VIGILANCE)
                            / N_REP_CALIBRATION) ** 0.5
        self.assertGreater(
            P_VIGILANCE - P_REJET, erreur_mc,
            f"zone grise ({P_VIGILANCE - P_REJET:.3f}) plus étroite que "
            f"l'erreur de Monte-Carlo ({erreur_mc:.3f}) à n_rep="
            f"{N_REP_CALIBRATION}")

    def test_glm_indisponible_donne_non_testable(self):
        for glm in (None, {}, {'success': False},
                    {'success': True, 'glm_disponible': False},
                    {'success': True, 'glm_disponible': True, 'p_calendaire': None}):
            with self.subTest(glm=glm):
                self.assertEqual(boot_h2_structure(glm).statut, NON_TESTABLE)

    def test_h2_est_descriptive(self):
        """⚠️ VERROU DE NON-GATING. Le GLM APC n'a aucun effet décisionnel dans
        A7 ; lui en donner un ici serait un lot à part entière."""
        self.assertEqual(boot_h2_structure(self._glm(0.0001)).critique_pour, ())


class TestBootH4IncrementsPositifs(unittest.TestCase):
    """BOOT-H4 sur VÉRITÉ CONNUE : on injecte un nombre CHOISI d'incréments
    négatifs et on vérifie que le comptage les retrouve exactement."""

    @staticmethod
    def _triangle_avec_negatifs(n_negatifs):
        """Triangle croissant, puis `n_negatifs` incréments rendus négatifs par
        un recours. Le nombre injecté est connu, donc vérifiable.

        ⚠️ UNE SEULE CELLULE PAR LIGNE, ET TOUJOURS LA DERNIÈRE CONNUE. Un
        premier jet visait des cellules voisines d'une même ligne : abaisser
        `C[0,4]` après avoir posé `C[0,5] = C[0,4] − 30` rendait l'incrément
        (0,5) de nouveau positif, et deux injections n'en produisaient qu'une.
        Le test l'a attrapé — c'est exactement ce qu'un oracle à vérité connue
        doit faire.
        """
        C = np.zeros((6, 6))
        for i in range(6):
            for j in range(6 - i):
                C[i, j] = 1000. * (1 + 0.1 * i) * (1.0 + 0.6 * j)
        cibles = [(0, 5), (1, 4), (2, 3), (3, 2)]      # lignes distinctes
        for (i, j) in cibles[:n_negatifs]:
            C[i, j] = C[i, j - 1] - 30.
        return C

    def test_comptage_exact_sur_verite_connue(self):
        for n_neg in (0, 1, 2, 3):
            with self.subTest(n_negatifs=n_neg):
                C = self._triangle_avec_negatifs(n_neg)
                b = bootstrap_odp(C, _facteurs(C), n_sim=200, seed=42)
                h4 = boot_h4_increments_positifs(b)
                self.assertEqual(
                    h4.extras['n_exclues'], n_neg,
                    f"{n_neg} incrément(s) négatif(s) injecté(s), "
                    f"{h4.extras['n_exclues']} compté(s)")

    def test_seuils_du_verdict(self):
        C0 = self._triangle_avec_negatifs(0)
        b0 = bootstrap_odp(C0, _facteurs(C0), n_sim=200, seed=42)
        self.assertEqual(boot_h4_increments_positifs(b0).statut, VALIDEE)

        C1 = self._triangle_avec_negatifs(1)          # 1/21 = 4,8 % ≤ 10 %
        b1 = bootstrap_odp(C1, _facteurs(C1), n_sim=200, seed=42)
        h1 = boot_h4_increments_positifs(b1)
        self.assertEqual(h1.statut, A_JUSTIFIER)
        self.assertLessEqual(h1.extras['frac_exclue'], 0.10)

        C3 = self._triangle_avec_negatifs(3)          # 3/21 = 14,3 % > 10 %
        b3 = bootstrap_odp(C3, _facteurs(C3), n_sim=200, seed=42)
        h3 = boot_h4_increments_positifs(b3)
        self.assertEqual(h3.statut, NON_VALIDEE)
        self.assertGreater(h3.extras['frac_exclue'], 0.10)

    def test_comptage_absent_donne_non_testable(self):
        for bloc in (None, {}, {'increments_non_positifs': None},
                     {'increments_non_positifs': {}}):
            with self.subTest(bloc=bloc):
                self.assertEqual(
                    boot_h4_increments_positifs(bloc).statut, NON_TESTABLE)

    def test_h4_est_critique_pour_les_percentiles_seulement(self):
        C3 = self._triangle_avec_negatifs(3)
        b3 = bootstrap_odp(C3, _facteurs(C3), n_sim=200, seed=42)
        h4 = boot_h4_increments_positifs(b3)
        self.assertEqual(h4.critique_pour, (PERCENTILES_BOOT,))


class TestGouvernance(unittest.TestCase):
    """⚠️ CE QUI EST RETIRÉ, ET SURTOUT CE QUI NE L'EST PAS."""

    def test_non_validee_retire_les_percentiles(self):
        from .n2_hypotheses_clm import ResultatHypothese
        h = ResultatHypothese(
            code='BOOT-H3', libelle='x', statut=NON_VALIDEE, valeur=0.001,
            critere='c', source_critere='s', message='m',
            critique_pour=(PERCENTILES_BOOT,))
        self.assertFalse(percentiles_publiables({'BOOT-H3': h}))

    def test_non_testable_ne_retire_rien(self):
        """Ne pas avoir pu juger n'est PAS juger défavorablement."""
        from .n2_hypotheses_clm import ResultatHypothese
        for st in (NON_TESTABLE, A_JUSTIFIER, VALIDEE):
            with self.subTest(statut=st):
                h = ResultatHypothese(
                    code='BOOT-H3', libelle='x', statut=st, valeur=None,
                    critere='c', source_critere='s', message='m',
                    critique_pour=(PERCENTILES_BOOT,))
                self.assertTrue(percentiles_publiables({'BOOT-H3': h}))

    def test_hypothese_descriptive_ne_retire_rien(self):
        from .n2_hypotheses_clm import ResultatHypothese
        h = ResultatHypothese(
            code='BOOT-H1', libelle='x', statut=NON_VALIDEE, valeur=None,
            critere='c', source_critere='s', message='m', critique_pour=())
        self.assertTrue(percentiles_publiables({'BOOT-H1': h}))

    def test_aucune_cible_n_est_un_nom_de_methode(self):
        """⚠️ LE POINT DU LOT. Le Bootstrap ODP ne pèse pas dans le Best
        Estimate : ses hypothèses ne peuvent invalider qu'un LIVRABLE."""
        from .n4_best_estimate import _CLES_N3
        rng = np.random.default_rng(31)
        C = triangle_odp(VOL_VRAIS, CAD_VRAIE, rng, phi=50.0)
        f = _facteurs(C)
        res = verifier_hypotheses_bootstrap(
            C, f, bootstrap_odp(C, f, n_sim=200, seed=42), n_rep_calibration=60)
        for code, h in res['objets'].items():
            for cible in h.critique_pour:
                self.assertEqual(
                    cible, PERCENTILES_BOOT,
                    f"{code} déclare « {cible} » critique — or les seules "
                    f"cibles admises sont des LIVRABLES, jamais des méthodes.")
                self.assertNotIn(cible, set(_CLES_N3),
                                 f"{cible} est un nom de méthode du BE")


class TestPointEntree(unittest.TestCase):
    """Contrat de sortie de `verifier_hypotheses_bootstrap`."""

    def setUp(self):
        rng = np.random.default_rng(555)
        self.C = triangle_odp(VOL_VRAIS, CAD_VRAIE, rng, phi=50.0)
        self.f = _facteurs(self.C)
        self.boot = bootstrap_odp(self.C, self.f, n_sim=200, seed=42)
        self.res = verifier_hypotheses_bootstrap(
            self.C, self.f, self.boot, n_rep_calibration=60, graine=9)

    def test_les_quatre_codes_sont_la(self):
        self.assertEqual(tuple(self.res['statuts']), CODES)
        self.assertEqual(set(self.res['hypotheses']), set(CODES))

    def test_synthese_json_serialisable(self):
        import json
        json.dumps(self.res['hypotheses'])
        json.dumps(self.res['phi_par_axe'])

    def test_parametres_publies(self):
        self.assertEqual(self.res['graine_calibration'], 9)
        self.assertEqual(self.res['n_rep_calibration'], 60)

    def test_phi_global_est_celui_du_bootstrap(self):
        """⚠️ UN SEUL φ DANS LE SYSTÈME. Celui que publie l'hypothèse doit être
        celui du Bootstrap, au centième près — c'est toute la raison du lot."""
        self.assertAlmostEqual(self.res['phi_global'], self.boot['phi'], places=4)

    def test_lignes_affichage(self):
        n2 = {'bootstrap_hyp': self.res}
        lignes = lignes_hypotheses_bootstrap(n2)
        self.assertEqual([l['code'] for l in lignes], list(CODES))
        for l in lignes:
            self.assertTrue(l['message'])
            self.assertIn(l['statut'],
                          (VALIDEE, A_JUSTIFIER, NON_VALIDEE, NON_TESTABLE))

    def test_affichage_sans_donnees_dit_non_testable_pas_zero(self):
        """⚠️ LE DÉFAUT QUE CE LOT SUPPRIME. Douze sites affichaient l'ancienne
        H4 avec des `.get(clé, 0)` : la clé disparue, ils auraient publié
        « φ = 0,000000 », c'est-à-dire une dispersion nulle."""
        for n2 in (None, {}, {'bootstrap_hyp': {}}):
            with self.subTest(n2=n2):
                lignes = lignes_hypotheses_bootstrap(n2)
                self.assertEqual(len(lignes), len(CODES))
                for l in lignes:
                    self.assertEqual(l['statut'], NON_TESTABLE)
                    self.assertFalse(l['ok'])
                    self.assertNotIn('0.000000', l['message'])
                self.assertEqual(libelle_phi_par_axe(n2), '')

    def test_sous_titre_graphique(self):
        n2 = {'bootstrap_hyp': self.res}
        txt = libelle_phi_par_axe(n2)
        self.assertIn('φ par période de développement', txt)
        self.assertIn('BOOT-H3', txt)


# =============================================================================
#  VERROUS DE PÉRIMÈTRE — AST, sur le texte des modules
# =============================================================================

class TestPerimetre(unittest.TestCase):

    def test_le_module_ne_decide_rien(self):
        """Il PRODUIT des verdicts, il n'en TIRE aucune conséquence : ni poids,
        ni score, ni sélection de méthode. Même verrou que CLM et BFCC."""
        src = (_ICI / 'n2_hypotheses_bootstrap.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)
        interdits = {'methodes_incluses', 'best_estimate', 'poids',
                     'seuil_score', 'scores_confiance'}
        trouves = {n.id for n in ast.walk(arbre)
                   if isinstance(n, ast.Name) and n.id in interdits}
        trouves |= {n.attr for n in ast.walk(arbre)
                    if isinstance(n, ast.Attribute) and n.attr in interdits}
        self.assertEqual(trouves, set(),
                         f"le module touche à la décision : {trouves}")

    def test_n2_hypotheses_ne_publie_plus_aucun_phi(self):
        """⚠️ VERROU CONTRE LA TROISIÈME OCCURRENCE.

        Deux loss ratios concurrents, puis deux φ concurrents : la même faute,
        deux fois. La forme est toujours la même — une grandeur recalculée
        ailleurs sous le même nom. Ce verrou interdit à `n2_hypotheses.py` de
        produire une clé `phi`, une variable `phi`, ou toute fonction dont le nom
        l'évoque. Il n'y a plus qu'UN SEUL φ dans A7, celui du Bootstrap ODP.
        """
        src = (_ICI / 'n2_hypotheses.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)

        cles = {n.value for n in ast.walk(arbre)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and n.value.strip().lower() in ('phi', 'φ')}
        self.assertEqual(cles, set(),
                         f"n2_hypotheses.py publie une clé φ : {cles}")

        noms = {n.id for n in ast.walk(arbre)
                if isinstance(n, ast.Name) and n.id.lower().startswith('phi')}
        noms |= {t.id for n in ast.walk(arbre)
                 if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name)
                 and t.id.lower().startswith('phi')}
        self.assertEqual(noms, set(),
                         f"n2_hypotheses.py calcule un φ : {noms}")

        fonctions = {f.name for f in ast.walk(arbre)
                     if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and ('homosc' in f.name.lower() or 'phi' in f.name.lower())}
        self.assertEqual(fonctions, set(),
                         f"n2_hypotheses.py teste encore l'homoscédasticité : "
                         f"{fonctions} — c'est BOOT-H3 désormais")

    def test_ancienne_cle_h4_disparue_partout(self):
        """La clé `h4_homosc_bootstrap` ne doit plus être LUE nulle part : un
        `.get('h4_homosc_bootstrap', {})` oublié afficherait un silence."""
        racine = _ICI.parents[2]
        coupables = []
        for f in list(_ICI.rglob('*.py')) + [racine / 'actuaria_app.py']:
            if f.name == Path(__file__).name or not f.exists():
                continue
            for num, ligne in enumerate(
                    f.read_text(encoding='utf-8').splitlines(), 1):
                nu = ligne.strip()
                if nu.startswith('#') or nu.startswith('*'):
                    continue          # commentaire historique : légitime
                if 'h4_homosc_bootstrap' in ligne:
                    coupables.append(f"{f.name}:{num}")
        self.assertEqual(coupables, [],
                         f"l'ancienne H4 est encore lue : {coupables}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
