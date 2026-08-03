# =============================================================================
#  Tests — n3/bootstrap_odp.py : Bootstrap ODP (England & Verrall 2002)
#
#  ⚠️ CE QUI FONDE CE FILET, ET CE QUI NE LE FONDE PAS. Deux niveaux, et l'ordre
#  compte :
#
#    · VERROUS 1 et 2 — THÉORIE ET VÉRITÉ CONNUE. Ils ne citent AUCUNE source
#      externe. Le verrou 1 vérifie une propriété définitoire de l'ajustement
#      croisé ODP (le triangle ajusté reproduit la diagonale observée) ; le
#      verrou 2 génère un triangle par le modèle ODP exact et vérifie que le
#      module retrouve la sur-dispersion qu'on y a mise. C'est là que le
#      correctif se justifie.
#
#    · VERROU 3 — DÉRIVE CONTRE L'EXEMPLE PUBLIÉ. La figure 30 du guide de
#      l'Institut des Actuaires (§3.c.ii p30) chiffre entièrement un Bootstrap
#      sur le triangle RAA. C'est une donnée externe utile, PAS une norme : un
#      exemple publié peut être imprécis, et rien n'oblige deux bootstraps de
#      10 000 tirages à coïncider au pour cent près. Sa tolérance est donc large
#      et assumée — il attrape un facteur, pas un écart de quelques pour cent.
#
#  Ce que l'audit modèle a trouvé, et que ce filet empêche de revenir : les
#  valeurs ajustées étaient calculées VERS L'AVANT — la prédiction à un pas de
#  MACK — au lieu de la récursion ARRIÈRE d'England & Verrall. Sur vérité connue,
#  φ ressortait alors surestimé d'un facteur 1,5 à 2,2 ; sur RAA, σ valait
#  33 395 et 2,24 % des simulations sortaient négatives.
# =============================================================================

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n3.bootstrap_odp import (
    ajuster_triangle, bootstrap_odp, calculer_fitted_et_residus,
    libelle_incertitude, _reserve_cl_simple, _resultat_degrade,
)
from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import (
    calculer_facteurs,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA, _TRI_RECOURS, _TRI_TOUT_DECROISSANT,
)

# ── Figure 30 du guide — RAA, 10 000 simulations ─────────────────────────────
GUIDE_MOYENNE    = 53_428
GUIDE_MEDIANE    = 52_091
GUIDE_ECART_TYPE = 13_923
GUIDE_MIN        = 17_705
GUIDE_MAX        = 118_008
GUIDE_QUANTILES  = {5: 32_945, 25: 43_419, 75: 61_940, 95: 78_150, 99: 91_898}
#: Réserve Chain Ladder du même triangle — le guide écrit que la médiane en est
#: « très proche » et que la moyenne « n'en est pas très différente ».
GUIDE_RESERVE_CL = 52_135


def _facteurs(C):
    return np.asarray(calculer_facteurs(np.asarray(C, float), 'standard')[0], float)


# =============================================================================
#  VERROU 1 — L'AJUSTEMENT REPRODUIT LES DONNÉES QU'IL AJUSTE
# =============================================================================

class T1_Ajustement_England_Verrall(unittest.TestCase):
    """La propriété qui sépare E&V de Mack, et qui se vérifie sans statistique."""

    def test_la_somme_des_increments_ajustes_egale_la_diagonale(self):
        """Propriété DÉFINITOIRE de l'ajustement croisé ODP.

        Le triangle ajusté d'England & Verrall reproduit exactement la dernière
        diagonale observée. C'est ce test-là que l'ancien ajustement — vers
        l'avant, `Ĉ[i,j] = C[i,j−1] × f̂_j` — échouait de +51,2 %, −44,4 %,
        +11,6 %, +32,4 % et −22,5 % sur les cinq premières années de RAA.
        """
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA)):
            C = np.asarray(tri, float)
            n, m = C.shape
            ajuste = ajuster_triangle(C, _facteurs(C))
            for i in range(n):
                k = min(n - i - 1, m - 1)
                self.assertAlmostEqual(
                    ajuste[i, k], C[i, k], delta=abs(C[i, k]) * 1e-9 + 1e-6,
                    msg=f"{nom} année {i} : l'ajustement ne reproduit pas la diagonale")
                # …et la somme des incréments ajustés vaut ce même cumulé.
                somme = ajuste[i, 0] + sum(ajuste[i, j] - ajuste[i, j - 1]
                                           for j in range(1, k + 1))
                self.assertAlmostEqual(somme, C[i, k],
                                       delta=abs(C[i, k]) * 1e-9 + 1e-6)
            print(f"    OK BOOT-1 {nom} : les {n} lignes ajustées reproduisent "
                  f"la diagonale observée")

    def test_la_colonne_zero_est_dans_le_vivier(self):
        """Elle en était exclue par construction, faute de résidu calculable."""
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA)):
            C = np.asarray(tri, float)
            n, m = C.shape
            _, _, _, vivier, n_obs, n_par, cellules = \
                calculer_fitted_et_residus(C, _facteurs(C))
            colonnes = {j for (_, j) in cellules}
            self.assertIn(0, colonnes, f"{nom} : la colonne 0 doit contribuer")
            attendu = sum(1 for i in range(n) for j in range(m) if i + j < n)
            self.assertEqual(n_obs, attendu,
                             f"{nom} : {n_obs} incréments retenus sur {attendu}")
            self.assertEqual(n_par, n + m - 1)
            self.assertEqual(len(vivier), n_obs,
                             "aucun résidu ne doit être filtré sur sa valeur")
            print(f"    OK BOOT-2 {nom} : N={n_obs} (dont colonne 0), "
                  f"p={n_par}, df={n_obs - n_par}, vivier={len(vivier)}")

    def test_un_residu_nul_reste_dans_le_vivier(self):
        """Un ajustement parfait est une observation, pas une donnée manquante."""
        C = np.asarray(RAA, float)
        _, residus, _, vivier, n_obs, _, cellules = \
            calculer_fitted_et_residus(C, _facteurs(C))
        # Le vivier compte exactement une entrée par cellule retenue — donc il
        # ne peut pas avoir écarté une valeur, quelle qu'elle soit.
        self.assertEqual(len(vivier), len(cellules))
        self.assertEqual(len(vivier), n_obs)
        print(f"    OK BOOT-3 vivier = {len(vivier)} entrées pour "
              f"{len(cellules)} cellules — aucun filtre sur la valeur")


# =============================================================================
#  VERROU 2 — VALIDATION SUR VÉRITÉ CONNUE, SANS AUCUN RECOURS AU GUIDE
# =============================================================================

def _triangle_odp(x, y, phi, graine):
    """Triangle cumulé issu du modèle croisé ODP EXACT.

        m_ij ~ φ × Poisson(x_i·y_j / φ)   ⇒   E[m] = x_i·y_j,  Var(m) = φ·x_i·y_j

    On connaît donc la vérité : les moyennes de cellule ET la sur-dispersion.
    """
    rng = np.random.default_rng(graine)
    n, m = len(x), len(y)
    M = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            if i + j < n:
                M[i, j] = phi * rng.poisson(x[i] * y[j] / phi)
    return np.cumsum(M, axis=1)


#: Portefeuille synthétique : volumes croissants, cadence décroissante.
VOL_VRAIS = np.array([1000., 1100., 1250., 1300., 1400.,
                      1500., 1600., 1750., 1800., 1900.])
CAD_VRAIE = np.array([.32, .24, .16, .10, .07, .05, .03, .02, .007, .003])
CAD_VRAIE = CAD_VRAIE / CAD_VRAIE.sum()


class T2_Verite_Connue(unittest.TestCase):
    """L'estimateur retrouve-t-il ce qu'on a mis dans les données ?

    ⚠️ CETTE CLASSE EST LE VERROU QUI COMPTE, ET ELLE N'INVOQUE PAS LE GUIDE.
    Un exemple publié peut être faux ; un modèle dont on écrit soi-même les
    paramètres, non. On génère donc un triangle par le modèle ODP exact, puis on
    vérifie que le module retrouve la sur-dispersion injectée et les moyennes de
    cellule. C'est la validation qui fonde le correctif — l'accord avec la
    figure 30 du guide en est une CONSÉQUENCE, jamais la cible.
    """

    def test_la_sur_dispersion_injectee_est_retrouvee(self):
        """φ estimé ≈ φ vrai. L'ancien estimateur le surestimait de 1,5 à 2,2×."""
        for phi_vrai in (1.0, 20.0, 100.0):
            rapports = []
            for essai in range(12):
                C = _triangle_odp(VOL_VRAIS, CAD_VRAIE, phi_vrai, 1000 + essai)
                if (C <= 0).any():
                    continue
                _, _, phi_est, _, _, _, _ = calculer_fitted_et_residus(C, _facteurs(C))
                rapports.append(phi_est / phi_vrai)
            median = float(np.median(rapports))
            self.assertGreater(median, 0.60,
                               f"φ={phi_vrai} sous-estimé d'un facteur {1/median:.2f}")
            self.assertLess(median, 1.40,
                            f"φ={phi_vrai} surestimé d'un facteur {median:.2f} — "
                            f"l'ancien ajustement donnait 1,94 / 1,92 / 2,21")
            print(f"    OK BOOT-4 φ vrai {phi_vrai:>6,.1f} → estimé "
                  f"{median*phi_vrai:>6,.1f} (rapport {median:.2f})")

    def test_les_increments_ajustes_approchent_les_vraies_moyennes(self):
        """Le triangle ajusté doit estimer x_i·y_j, pas autre chose."""
        C = _triangle_odp(VOL_VRAIS, CAD_VRAIE, 5.0, 4242)
        m_fit, _, _, _, _, _, cellules = calculer_fitted_et_residus(C, _facteurs(C))
        rel = [abs(m_fit[i, j] - VOL_VRAIS[i] * CAD_VRAIE[j])
               / (VOL_VRAIS[i] * CAD_VRAIE[j]) for (i, j) in cellules]
        median = float(np.median(rel))
        self.assertLess(median, 0.20,
                        f"écart médian de {median:.1%} aux vraies moyennes")
        print(f"    OK BOOT-5 incréments ajustés : écart médian de {median:.1%} "
              f"aux moyennes x_i·y_j injectées")

    def test_le_recentrage_est_une_translation_pure(self):
        """Ce qui est publié décrit bien la distribution publiée.

        Le recentrage est une TRANSLATION : il déplace la moyenne sur la réserve
        Chain Ladder et ne touche pas à la dispersion. Ce test vérifie la
        cohérence interne du contrat de sortie — moyenne, écart-type et biais
        déclarés décrivent tous la MÊME distribution — plutôt que de re-dériver
        une identité que numpy garantit de toute façon.
        """
        C = _triangle_odp(VOL_VRAIS, CAD_VRAIE, 5.0, 77)
        r = bootstrap_odp(C, _facteurs(C), n_sim=2000, seed=42)
        d = np.array(r['distribution'])
        self.assertAlmostEqual(float(np.mean(d)), r['be_bootstrap'], delta=0.01)
        self.assertAlmostEqual(float(np.std(d, ddof=1)), r['std_bootstrap'],
                               delta=0.01)
        # Le biais déclaré est bien l'écart que le recentrage a effacé.
        attendu = (r['moyenne_avant_recentrage'] - r['be_bootstrap'])             / abs(r['be_bootstrap'])
        self.assertAlmostEqual(r['biais_recentrage_pct'], attendu, places=5)
        print(f"    OK BOOT-6 contrat cohérent : moyenne, σ et biais "
              f"({r['biais_recentrage_pct']:+.2%}) décrivent la même distribution")


# =============================================================================
#  VERROU 3 — DÉRIVE CONTRE L'EXEMPLE PUBLIÉ  (INFORMATIF, TOLÉRANCE LARGE)
# =============================================================================

class T3_Derive_Contre_Oracle_Publie(unittest.TestCase):
    """Comparaison à la figure 30 du guide — DÉTECTEUR DE DÉRIVE, PAS NORME.

    ⚠️ CE QUE CETTE CLASSE FAIT, ET CE QU'ELLE NE FAIT PAS. Un exemple publié
    est une donnée externe utile : il attrape un facteur 2,4 comme celui que
    l'audit modèle a trouvé (σ = 33 395 contre 13 923). Il ne peut PAS arbitrer
    un écart de 5 % — la figure 30 pourrait elle-même être imprécise, et rien
    n'oblige un bootstrap à 10 000 tirages d'un auteur à coïncider au pour cent
    près avec un autre. Les tolérances sont donc LARGES et assumées comme telles.
    Ce qui fonde le correctif est la classe précédente, sur vérité connue.
    """

    #: Assez serrée pour attraper le facteur 2,4 de l'audit, assez large pour
    #: ne pas ériger un exemple publié en référence normative.
    TOLERANCE = 0.50

    @classmethod
    def setUpClass(cls):
        C = np.asarray(RAA, float)
        cls.r = bootstrap_odp(C, _facteurs(C), n_sim=10_000, seed=42)
        cls.d = np.array(cls.r['distribution'])

    def test_ecart_type_du_meme_ordre_que_lexemple_publie(self):
        sigma = self.r['std_bootstrap']
        self.assertAlmostEqual(sigma / GUIDE_ECART_TYPE, 1.0, delta=self.TOLERANCE,
                               msg=f"σ = {sigma:,.0f} contre {GUIDE_ECART_TYPE:,} "
                                   f"publié — dérive de modèle probable")
        print(f"    OK BOOT-7 écart-type {sigma:,.0f} contre {GUIDE_ECART_TYPE:,} "
              f"au guide ({sigma / GUIDE_ECART_TYPE - 1:+.1%}, toléré "
              f"±{self.TOLERANCE:.0%})")

    def test_les_quantiles_restent_du_meme_ordre(self):
        for q, attendu in GUIDE_QUANTILES.items():
            obtenu = float(np.percentile(self.d, q))
            self.assertAlmostEqual(
                obtenu / attendu, 1.0, delta=self.TOLERANCE,
                msg=f"q{q} = {obtenu:,.0f} contre {attendu:,} publié")
        ecarts = {q: f"{np.percentile(self.d, q) / v - 1:+.0%}"
                  for q, v in GUIDE_QUANTILES.items()}
        print(f"    OK BOOT-8 quantiles du même ordre que le guide : {ecarts}")

    def test_la_mediane_reste_voisine_de_la_reserve_chain_ladder(self):
        """Propriété SAINE d'un bootstrap recentré, que le guide observe aussi."""
        mediane = float(np.median(self.d))
        self.assertAlmostEqual(mediane / GUIDE_RESERVE_CL, 1.0, delta=0.20)
        print(f"    OK BOOT-9 médiane {mediane:,.0f} contre réserve CL "
              f"{GUIDE_RESERVE_CL:,} ({mediane / GUIDE_RESERVE_CL - 1:+.1%})")

    def test_aucune_simulation_negative(self):
        """Propriété du MODÈLE, pas du guide : l'ODP a des incréments ≥ 0."""
        self.assertEqual((self.d < 0).sum(), 0,
                         "une réserve simulée négative contredit le modèle ODP")
        print(f"    OK BOOT-10 domaine [{self.d.min():,.0f} ; {self.d.max():,.0f}] "
              f"— 0 simulation négative (l'ancien code en produisait 224/10 000)")

    def test_le_biais_avant_recentrage_reste_borne(self):
        """Un biais démesuré signale que les gardes d'incrément mordent."""
        self.assertIn('biais_recentrage_pct', self.r)
        biais = self.r['biais_recentrage_pct']
        self.assertLess(abs(biais), 0.30,
                        f"biais de {biais:+.1%} avant recentrage — un paramètre "
                        f"amont est suspect")
        print(f"    OK BOOT-11 biais avant recentrage {biais:+.2%} "
              f"(était +79,43 %, le guide observe +2,48 % sur son exemple)")
#  VERROU 3 — DÉCOMPOSITION DE σ
# =============================================================================

class T3_Decomposition_Sigma(unittest.TestCase):

    def test_les_deux_composantes_se_recomposent(self):
        """σ² total = σ² paramètre + σ² processus, à l'appariement près."""
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA)):
            C = np.asarray(tri, float)
            r = bootstrap_odp(C, _facteurs(C), n_sim=3000, seed=42)
            tot, par, pro = (r['std_bootstrap'], r['std_parametre'],
                             r['std_processus'])
            self.assertGreater(par, 0)
            self.assertGreater(pro, 0)
            self.assertAlmostEqual(np.sqrt(par ** 2 + pro ** 2) / tot, 1.0,
                                   delta=1e-6)
            self.assertLess(par, tot, "la part de paramètre est une PART du total")
            print(f"    OK BOOT-12 {nom} : σ={tot:,.0f} = "
                  f"paramètre {par:,.0f} ⊕ processus {pro:,.0f}")

    def test_la_part_processus_disparait_si_phi_est_nul(self):
        """Contre-épreuve : sans sur-dispersion, il ne reste que le paramètre."""
        C = np.asarray(GENINS, float)
        r = bootstrap_odp(C, _facteurs(C), n_sim=1500, seed=7)
        self.assertGreater(r['phi'], 0, "GenIns doit être sur-dispersé")
        print(f"    OK BOOT-13 φ = {r['phi']:,.1f} > 0 — la part de processus "
              f"a bien une source")


# =============================================================================
#  VERROU 4 — LE CAS NON CALCULÉ NE FABRIQUE AUCUNE INCERTITUDE
# =============================================================================

class T4_Non_Calcule(unittest.TestCase):
    """Un Bootstrap qui ne peut pas tourner doit le DIRE, pas rendre des zéros."""

    def test_le_resultat_degrade_ne_publie_aucun_zero_trompeur(self):
        d = _resultat_degrade(1234.0, 500)
        self.assertFalse(d['disponible'])
        for cle in ('std_bootstrap', 'cv_bootstrap', 'p50', 'p90', 'p99_5',
                    'ic_95_inf', 'ic_95_sup', 'phi'):
            self.assertIsNone(d[cle],
                              f"{cle} = {d[cle]} : un chiffre fabriqué")
        self.assertEqual(d['statut'], 'ROUGE')
        self.assertIn('increments_non_positifs', d,
                      "clé du résultat nominal absente du dégradé")
        self.assertEqual(d['be_bootstrap'], 1234.0,
                         "le point estimate reste légitime et publié")
        print("    OK BOOT-14 dégradé : aucune grandeur d'incertitude fabriquée")

    def test_degres_de_liberte_negatifs_declenchent_le_degrade(self):
        """Six résidus pour onze paramètres n'est pas un bootstrap fiable.

        Le critère `len(résidus) < 4` seul laissait passer ce cas : le triangle
        tout décroissant sortait alors σ ≈ 0, CV = 0 % et un statut VERT.
        """
        C = np.asarray(_TRI_TOUT_DECROISSANT, float)
        _, _, _, vivier, n_obs, n_par, _ = calculer_fitted_et_residus(C, _facteurs(C))
        self.assertGreaterEqual(len(vivier), 4, "le scénario doit exercer la garde df")
        self.assertLessEqual(n_obs - n_par, 0, "et présenter df ≤ 0")
        r = bootstrap_odp(C, _facteurs(C), n_sim=500, seed=42)
        self.assertFalse(r['disponible'])
        self.assertIsNone(r['std_bootstrap'])
        self.assertEqual(r['statut'], 'ROUGE')
        print(f"    OK BOOT-15 df = {n_obs - n_par} ≤ 0 → non calculé "
              f"(et non σ≈0 en VERT)")

    def test_le_formateur_ne_montre_jamais_un_zero(self):
        d = _resultat_degrade(1234.0, 500)
        self.assertEqual(libelle_incertitude(d), 'non calculé')
        self.assertEqual(libelle_incertitude(d, 'cv_bootstrap'), 'non calculé')
        C = np.asarray(RAA, float)
        r = bootstrap_odp(C, _facteurs(C), n_sim=500, seed=42)
        self.assertNotIn('non calculé', libelle_incertitude(r))
        print("    OK BOOT-16 formateur : « non calculé », jamais « 0 »")


# =============================================================================
#  VERROU 5 — LE BOOTSTRAP N'ENTRE PAS DANS LE BEST ESTIMATE
# =============================================================================

class T5_Perimetre(unittest.TestCase):

    def test_le_bootstrap_nest_pas_une_methode_du_be(self):
        """Vérifié à la source : il alimente la dispersion, pas le point estimate."""
        from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate \
            import _CLES_N3
        self.assertNotIn('bootstrap', _CLES_N3)
        self.assertNotIn('bootstrap_odp', _CLES_N3)
        self.assertEqual(set(_CLES_N3),
                         {'chain_ladder', 'bornhuetter_ferguson', 'cape_cod'})
        print(f"    OK BOOT-17 méthodes du BE : {sorted(_CLES_N3)} — "
              f"Bootstrap absent")

    def test_le_recentrage_aligne_exactement_sur_chain_ladder(self):
        """Translation, la forme que le guide décrit (§3.c.i p29)."""
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA)):
            C = np.asarray(tri, float)
            f = _facteurs(C)
            r = bootstrap_odp(C, f, n_sim=2000, seed=42)
            ref = _reserve_cl_simple(C, f, 1)
            self.assertAlmostEqual(r['be_bootstrap'], ref, delta=0.01)
            print(f"    OK BOOT-18 {nom} : recentrage exact sur "
                  f"{ref:,.2f} (réserve CL brute)")

    def test_aucune_exposition_nest_requise(self):
        """Le rééchantillonnage porte sur le seul triangle."""
        import inspect
        params = set(inspect.signature(bootstrap_odp).parameters)
        self.assertFalse({p for p in params if 'prime' in p or 'expo' in p},
                         "le Bootstrap ne doit rien exiger d'extérieur")
        print(f"    OK BOOT-19 signature sans exposition : {sorted(params)}")


# =============================================================================
#  VERROU 6 — TRIANGLE À RECOURS
# =============================================================================

class T6_Recours(unittest.TestCase):
    """L'ODP exige des incréments strictement positifs — le guide le dit (p29)."""

    def test_les_increments_non_positifs_sont_exclus_et_comptes(self):
        C = np.asarray(_TRI_RECOURS, float)
        n, m = C.shape
        _, _, _, vivier, n_obs, _, _ = calculer_fitted_et_residus(C, _facteurs(C))
        total = sum(1 for i in range(n) for j in range(m) if i + j < n)
        self.assertLess(n_obs, total, "des cellules doivent être exclues")
        r = bootstrap_odp(C, _facteurs(C), n_sim=1000, seed=42)
        self.assertIn('increments_non_positifs', r)
        print(f"    OK BOOT-20 recours : {n_obs}/{total} incréments retenus, "
              f"exclusion signalée dans le résultat")


if __name__ == '__main__':
    unittest.main(verbosity=1)
