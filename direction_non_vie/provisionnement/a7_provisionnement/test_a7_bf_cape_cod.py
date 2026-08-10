# =============================================================================
#  Tests — n3/bf_cape_cod.py : Bornhuetter-Ferguson et Cape Cod
#
#  Ce fichier comble un trou : avant lui, AUCUN test de la gate ne fournissait
#  de mesure d'exposition. Depuis que les deux méthodes refusent de tourner sans
#  exposition, elles n'auraient plus été exercées du tout — on aurait durci la
#  règle d'entrée et affaibli la couverture au même moment.
#
#  Il porte deux oracles EXTERNES :
#    · l'exemple Bornhuetter-Ferguson entièrement chiffré du guide de l'Institut
#      des Actuaires (§2.c, p16-18), reproduit sur ses ONZE années de survenance ;
#    · la formule Cape Cod de Bühlmann & Straub, vérifiée contre une
#      ré-implémentation indépendante.
# =============================================================================

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement,
)
from direction_non_vie.provisionnement.a7_provisionnement.n3.bf_cape_cod import (
    bornhuetter_ferguson, cape_cod, libelle_loss_ratio,
)
from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import (
    calculer_facteurs, calculer_facteurs_cumules, calculer_pct_developpe,
    chain_ladder,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA,
)

# ── Exemple PUBLIÉ par le guide IA 2023, §2.c p16-18 ─────────────────────────
#: Figures 16 et 18 — primes acquises de l'année N-10 à l'année N, S/P = 60 %.
GUIDE_PRIMES = np.array([33.33, 34.00, 34.68, 35.37, 36.08, 36.80,
                         37.54, 38.29, 39.06, 39.84, 40.63])
GUIDE_SP = 0.60
#: Figure 19 — « Cadence de développement » par période de développement. Elle se
#: termine à 100 %, c'est-à-dire UNE ENTRÉE PAR COLONNE, la dernière entièrement
#: développée : la structure même que le correctif f_cum a rétablie.
GUIDE_CADENCE = np.array([.5577, .5962, .6359, .6769, .7192, .7628,
                          .8077, .8538, .9013, .9500, 1.0000])
#: Figure 19, dernière colonne — les ultimes Bornhuetter-Ferguson publiés.
GUIDE_ULTIMES = [20.0, 21.0, 22.1, 23.1, 24.2, 25.2, 26.3, 27.4, 28.5, 29.7, 30.8]
#: La diagonale du triangle de la Figure 19 vaut 20,0 sur toutes les lignes.
GUIDE_DIAGONALE = 20.0


def _contexte(triangle, tail=1.0):
    """Facteurs, cadence, diagonale et ultimes Chain Ladder d'un triangle."""
    C = np.array(triangle, dtype=float)
    cl = chain_ladder(C, annee_base_reserve=1, tail_force=tail)
    facteurs, _ = calculer_facteurs(C, 'standard')
    pct_dev = calculer_pct_developpe(C, calculer_facteurs_cumules(facteurs, tail))
    return (C, pct_dev, np.array(cl['last_diagonale']),
            np.array(cl['ultimates']), cl)


def _exposition(triangle, loss_ratio=0.70):
    """Exposition cohérente avec un triangle, pour un loss ratio visé."""
    C = np.array(triangle, dtype=float)
    return C.max(axis=1) * 1.6 / loss_ratio


class T1_Oracle_Publie_Du_Guide(unittest.TestCase):
    """L'exemple BF du guide, reproduit sur ses onze années de survenance."""

    def test_ultimes_conformes_a_la_figure_19(self):
        n = len(GUIDE_PRIMES)
        # L'année i = 0 est la plus ancienne (N-10) : sa dernière colonne connue
        # est la dernière du triangle, donc sa cadence est celle de la colonne n-1.
        pct_dev = np.array([GUIDE_CADENCE[n - 1 - i] for i in range(n)])
        r = bornhuetter_ferguson(
            C=np.zeros((n, n)), pct_dev=pct_dev,
            last_diag=np.full(n, GUIDE_DIAGONALE), ultimates_cl=np.zeros(n),
            exposition=GUIDE_PRIMES, lr_manuel=GUIDE_SP, annee_base=0)
        for i, attendu in enumerate(GUIDE_ULTIMES):
            self.assertAlmostEqual(
                r['ultimates'][i], attendu, delta=0.06,
                msg=(f"année N-{n - 1 - i} : ultime {r['ultimates'][i]:.2f} "
                     f"contre {attendu} publié en Figure 19"))
        print("    OK BF-a exemple publié du guide (§2.c p16-18) : 11 années "
              "conformes, à l'arrondi près")

    def test_charge_ultime_attendue_conforme_a_la_figure_16(self):
        """μ = S/P × prime acquise, la « Espérance de la charge Ultime » du guide."""
        n = len(GUIDE_PRIMES)
        r = bornhuetter_ferguson(
            C=np.zeros((n, n)), pct_dev=np.full(n, 0.5),
            last_diag=np.zeros(n), ultimates_cl=np.zeros(n),
            exposition=GUIDE_PRIMES, lr_manuel=GUIDE_SP, annee_base=0)
        for i, prime in enumerate(GUIDE_PRIMES):
            self.assertAlmostEqual(r['mu_par_annee'][i], prime * GUIDE_SP, delta=0.01)
        print("    OK BF-b μ = S/P × prime : conforme à la Figure 16 du guide")


class T2_Exposition_Obligatoire(unittest.TestCase):
    """Sans ancrage externe, les deux méthodes refusent de produire un chiffre."""

    def setUp(self):
        self.C, self.pct, self.ld, self.U, _ = _contexte(GENINS)

    def test_bf_sans_exposition_ni_apriori_ne_calcule_pas(self):
        r = bornhuetter_ferguson(self.C, self.pct, self.ld, self.U)
        self.assertFalse(r['disponible'])
        self.assertEqual(r['reserve_totale'], 0.0)
        self.assertIn('ne repose donc que sur Chain Ladder', r['message'])
        self.assertIn('exposition', r['message'])
        print("    OK BF-c sans exposition : non calculée, message en conséquence")

    def test_cape_cod_sans_exposition_ne_calcule_pas(self):
        r = cape_cod(self.C, self.pct, self.ld)
        self.assertFalse(r['disponible'])
        self.assertEqual(r['reserve_totale'], 0.0)
        self.assertIn('ne repose donc que sur Chain Ladder', r['message'])
        print("    OK BF-d Cape Cod sans exposition : non calculée")

    def test_une_exposition_de_zeros_n_est_pas_une_exposition(self):
        n = len(self.ld)
        for methode, appel in (
                ('BF', lambda e: bornhuetter_ferguson(self.C, self.pct, self.ld,
                                                      self.U, exposition=e)),
                ('Cape Cod', lambda e: cape_cod(self.C, self.pct, self.ld,
                                                exposition=e))):
            with self.subTest(methode=methode):
                self.assertFalse(appel(np.zeros(n))['disponible'])
        print("    OK BF-e vecteur de zéros refusé comme les deux méthodes")

    def test_bf_accepte_un_ultime_apriori_sans_exposition(self):
        """La forme d'ORIGINE de 1972 : l'actuaire fournit la charge ultime."""
        n = len(self.ld)
        apriori = np.full(n, 25_000_000.0)
        r = bornhuetter_ferguson(self.C, self.pct, self.ld, self.U,
                                 ultime_apriori=apriori)
        self.assertTrue(r['disponible'])
        self.assertEqual(r['source_lr'], 'ultime_apriori')
        self.assertIsNone(r['lr_apriori'])
        # IBNR = (1 − cadence) × ultime a priori, sans loss ratio intermédiaire
        for i in range(n):
            attendu = max(1.0 - float(self.pct[i]), 0.0) * 25_000_000.0
            self.assertAlmostEqual(r['ibnr_par_annee'][i], attendu, delta=1.0)
        print("    OK BF-f charge ultime a priori : BF tourne sans exposition "
              "(forme d'origine 1972)")

    def test_aucun_loss_ratio_invente_a_l_affichage(self):
        """Une méthode non calculée n'a pas de loss ratio — surtout pas 0 %."""
        r = bornhuetter_ferguson(self.C, self.pct, self.ld, self.U)
        self.assertEqual(libelle_loss_ratio(r), 'non calculée')
        self.assertEqual(
            libelle_loss_ratio(cape_cod(self.C, self.pct, self.ld), 'lr_cape_cod'),
            'non calculée')
        print("    OK BF-g affichage : « non calculée », jamais « 0,0 % »")


class T3_Cape_Cod_Buhlmann_Straub(unittest.TestCase):
    """Le loss ratio Cape Cod, contre la formule de référence."""

    def test_formule_conforme_a_une_reimplementation_independante(self):
        for nom, triangle in (('GenIns', GENINS), ('RAA', RAA)):
            with self.subTest(triangle=nom):
                C, pct, ld, U, _ = _contexte(triangle)
                expo = _exposition(triangle)
                r = cape_cod(C, pct, ld, exposition=expo, annee_base=1)
                # Bühlmann & Straub : κ = Σ C[i,k_i] / Σ (V_i × β_i), sur TOUTES
                # les années d'origine.
                n = C.shape[0]
                attendu = (sum(ld[i] for i in range(n))
                           / sum(expo[i] * pct[i] for i in range(n)))
                self.assertAlmostEqual(r['lr_cape_cod'], attendu, delta=1e-4)
        print("    OK BF-h loss ratio Cape Cod = Σ observé / Σ exposition "
              "développée, sur toutes les années")

    def test_la_premiere_annee_informe_le_loss_ratio(self):
        """VERROU DE LA CORRECTION — la somme partait de `annee_base`, excluant
        l'année la plus ancienne. Or elle est entièrement développée : elle porte
        le rapport sinistres/exposition le plus fiable. Impact mesuré sur
        GenIns : loss ratio −3,5 %."""
        C, pct, ld, U, _ = _contexte(GENINS)
        expo = _exposition(GENINS)
        n = C.shape[0]
        r = cape_cod(C, pct, ld, exposition=expo, annee_base=1)
        sans_annee_0 = (sum(ld[i] for i in range(1, n))
                        / sum(expo[i] * pct[i] for i in range(1, n)))
        self.assertNotAlmostEqual(r['lr_cape_cod'], sans_annee_0, delta=1e-3)
        self.assertLess(r['lr_cape_cod'], sans_annee_0)
        print(f"    OK BF-i l'année 0 informe le LR : {r['lr_cape_cod']:.4f} "
              f"contre {sans_annee_0:.4f} si on l'excluait")

    def test_annee_base_delimite_la_reserve_pas_le_loss_ratio(self):
        """Deux rôles distincts : `annee_base` borne la RÉSERVE, jamais le LR."""
        C, pct, ld, U, _ = _contexte(GENINS)
        expo = _exposition(GENINS)
        r0 = cape_cod(C, pct, ld, exposition=expo, annee_base=0)
        r1 = cape_cod(C, pct, ld, exposition=expo, annee_base=1)
        self.assertAlmostEqual(r0['lr_cape_cod'], r1['lr_cape_cod'], delta=1e-9)
        self.assertGreaterEqual(r0['reserve_totale'], r1['reserve_totale'])
        print("    OK BF-j annee_base ne change que la réserve, pas le loss ratio")

    def test_cape_cod_avec_exposition_n_est_plus_chain_ladder(self):
        """Sans exposition, Cape Cod valait EXACTEMENT Chain Ladder (LR = 1 par
        identité algébrique). Avec une vraie exposition, elle apporte un avis."""
        C, pct, ld, U, cl = _contexte(GENINS)
        r = cape_cod(C, pct, ld, exposition=_exposition(GENINS), annee_base=1)
        self.assertTrue(r['disponible'])
        self.assertNotAlmostEqual(r['lr_cape_cod'], 1.0, delta=0.05)
        self.assertNotAlmostEqual(r['reserve_totale'], cl['reserve_totale'], delta=1.0)
        print(f"    OK BF-k avec exposition, Cape Cod diverge de Chain Ladder "
              f"({r['reserve_totale']:,.0f} contre {cl['reserve_totale']:,.0f})")


class T4_Scenario_De_Reference_Avec_Exposition(unittest.TestCase):
    """LE SCÉNARIO QUI MANQUAIT — un run complet où les trois méthodes du Best
    Estimate sont réellement exercées."""

    @classmethod
    def setUpClass(cls):
        cls.sans = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, n_sim_bootstrap=150, generer_graphiques=False,
            generer_word=False)
        cls.avec = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, primes=_exposition(GENINS), n_sim_bootstrap=150,
            generer_graphiques=False, generer_word=False)

    def test_les_deux_runs_aboutissent(self):
        self.assertTrue(self.sans['success'], self.sans.get('erreur'))
        self.assertTrue(self.avec['success'], self.avec.get('erreur'))

    def test_sans_exposition_le_be_repose_sur_chain_ladder_seul(self):
        n4 = self.sans['n4']
        self.assertEqual(n4['methodes_incluses'], ['chain_ladder'])
        self.assertAlmostEqual(
            n4['best_estimate'],
            self.sans['n3']['chain_ladder']['reserve_totale'], delta=1.0)
        print(f"    OK BF-l sans exposition : BE = réserve Chain Ladder "
              f"({n4['best_estimate']:,.0f})")

    def test_avec_exposition_les_trois_methodes_entrent_dans_le_be(self):
        n4 = self.avec['n4']
        self.assertEqual(set(n4['methodes_incluses']),
                         {'chain_ladder', 'bornhuetter_ferguson', 'cape_cod'})
        for methode in ('bf', 'cape_cod'):
            self.assertTrue(self.avec['n3'][methode]['disponible'])
        print(f"    OK BF-m avec exposition : les 3 méthodes du BE sont exercées "
              f"({n4['best_estimate']:,.0f})")

    def test_un_be_mono_methode_ne_sort_jamais_en_vert(self):
        """GOUVERNANCE — avec une seule méthode, `cv_inter` vaut 0 et validerait
        mécaniquement le résultat, alors qu'il traduit l'inverse : rien ne vient
        le corroborer."""
        self.assertEqual(self.sans['n4']['methodes_incluses'], ['chain_ladder'])
        self.assertNotEqual(self.sans['n4']['statut'], 'VERT')
        print(f"    OK BF-n BE mono-méthode : statut "
              f"{self.sans['n4']['statut']}, jamais VERT")

    def test_les_livrables_tiennent_dans_les_deux_cas(self):
        for libelle, resultat in (('sans exposition', self.sans),
                                  ('avec exposition', self.avec)):
            with self.subTest(cas=libelle):
                self.assertGreater(len(resultat['excel_bytes'] or b''), 0)
                self.assertGreater(len(resultat['commentaire']), 1000)
        # Et le commentaire ne doit jamais annoncer un loss ratio de 0 %.
        self.assertIn('non calculée', self.sans['commentaire'])
        print("    OK BF-o livrables produits dans les deux cas, sans LR inventé")


if __name__ == '__main__':
    unittest.main()
