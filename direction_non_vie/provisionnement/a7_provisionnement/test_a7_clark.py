# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — filet de tests de la méthode de Clark (2003)
=============================================================================

 DEUX NIVEAUX, comme le filet du Bootstrap ODP.

 NIVEAU 1 — VÉRITÉ CONNUE, BLOQUANT. Aucune source externe n'est invoquée,
 et ce n'est pas un choix de confort : LE GUIDE DE L'INSTITUT NE TRAITE PAS
 CLARK. Son sommaire ne couvre, en stochastique, que Mack (§3.b) et le
 Bootstrap (§3.c) ; son introduction borne explicitement son périmètre à
 Chain-Ladder, Loss Ratio et Bornhuetter-Ferguson. Il n'existe donc aucun
 exemple chiffré publié à opposer au code — et après les trois coquilles déjà
 trouvées dans ce guide (Mack, BF, Bootstrap), c'est la meilleure des
 situations : les paramètres sont fixés ici, et le code doit les retrouver.

 NIVEAU 2 — STRUCTUREL. Gouvernance, non-pollution, acquis des lots
 précédents, périmètre.
=============================================================================
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n3.clark import (
    clark_ldf, _increments, _verdict_structure_monotone, CLARK_G_T2_MIN)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA, _TRI_RECOURS)


# =============================================================================
#  LA VÉRITÉ — fixée ici, jamais montrée au code
# =============================================================================

OMEGA_VRAI = 1.60
THETA_VRAI = 3.20
U_VRAIS    = np.array([12000., 13000., 14500., 15000., 16200.,
                       17000., 18500., 19000., 20000., 21500.])
PHI_VRAI   = 30.0
#: Taille des campagnes stochastiques. 8 plutot que 10 : le pouvoir de
#: separation reste large (30 % contre 95 % de couverture) pour un cout de
#: gate divise par pres de trois.
N_CAMP     = 8
Z95        = 1.959964


def _carre(n=10, phi=None, graine=0, courbe='weibull'):
    """Carré COMPLET engendré par la courbe exacte. phi=None → sans bruit."""
    t = np.arange(1.0, n + 1.0)
    p = _increments(t, OMEGA_VRAI, THETA_VRAI, courbe)
    U = U_VRAIS[:n]
    rng = np.random.default_rng(graine)
    Y = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            mu = U[i] * p[j]
            Y[i, j] = mu if phi is None else phi * rng.poisson(mu / phi)
    return Y


def _triangle(n=10, phi=None, graine=0, courbe='weibull'):
    """Le triangle HAUT seul — ce que le code a le droit de voir."""
    Y = _carre(n, phi, graine, courbe)
    C = np.cumsum(Y, axis=1)
    for i in range(n):
        for j in range(n):
            if i + j >= n:
                C[i, j] = 0.0
    return C


#: Un ajustement de Clark coûte plusieurs secondes (48 démarrages multiples).
#: Une dizaine de tests réajustent les mêmes triangles de référence avec les
#: mêmes options : on ne paie l'ajustement qu'une fois.
_CACHE: dict = {}


def _fit(C, **kw):
    """Ajustement mémoïsé sur (identité du triangle, options)."""
    cle = (np.asarray(C, float).tobytes(), tuple(sorted(kw.items())))
    if cle not in _CACHE:
        _CACHE[cle] = clark_ldf(np.asarray(C, float), **kw)
    return _CACHE[cle]


# =============================================================================
#  NIVEAU 1 — VÉRITÉ CONNUE (BLOQUANT)
# =============================================================================

class TestClarkVeriteConnue(unittest.TestCase):
    """Le MLE retrouve-t-il des paramètres qu'on lui a cachés ?"""

    def test_c1_mle_retrouve_les_parametres_sans_bruit(self):
        """Sans bruit, l'ajustement doit rendre EXACTEMENT la courbe posée."""
        r = clark_ldf(_triangle(), courbes=['weibull'], annee_base=0,
                      calculer_ic=False)
        self.assertTrue(r['success'], r.get('erreur'))
        self.assertLess(abs(r['omega'] - OMEGA_VRAI) / OMEGA_VRAI, 0.02,
                        f"omega={r['omega']} vs {OMEGA_VRAI} attendu")
        self.assertLess(abs(r['theta'] - THETA_VRAI) / THETA_VRAI, 0.02,
                        f"theta={r['theta']} vs {THETA_VRAI} attendu")
        err = np.abs(np.array(r['ultimates'], float) - U_VRAIS) / U_VRAIS
        self.assertLess(err.max(), 0.03, f"ecart max sur U_i = {err.max():.3%}")

    def test_c2_mle_non_biaise_sous_bruit_odp(self):
        """Sous bruit ODP, la moyenne des estimations reste sur la vérité."""
        oms, ths = [], []
        for g in range(8):
            r = clark_ldf(_triangle(n=N_CAMP, phi=PHI_VRAI, graine=1000 + g),
                          courbes=['weibull'], annee_base=0, calculer_ic=False)
            if r.get('success'):
                oms.append(r['omega'])
                ths.append(r['theta'])
        self.assertGreaterEqual(len(oms), 6, 'trop d ajustements en echec')
        self.assertLess(abs(np.mean(oms) - OMEGA_VRAI) / OMEGA_VRAI, 0.08,
                        f"biais omega : {np.mean(oms):.4f} vs {OMEGA_VRAI}")
        self.assertLess(abs(np.mean(ths) - THETA_VRAI) / THETA_VRAI, 0.08,
                        f"biais theta : {np.mean(ths):.4f} vs {THETA_VRAI}")

    def test_c3_sigma2_retrouve_la_sur_dispersion_vraie(self):
        """σ² = χ²/df doit retrouver le φ qui a servi à engendrer le bruit.

        C'est le pendant exact du φ du Bootstrap ODP : même modèle Var = σ²·μ.
        """
        est = []
        for g in range(8):
            r = clark_ldf(_triangle(n=N_CAMP, phi=PHI_VRAI, graine=2000 + g),
                          courbes=['weibull'], annee_base=0, calculer_ic=False)
            if r.get('success') and r.get('sigma2'):
                est.append(r['sigma2'])
        self.assertGreaterEqual(len(est), 6)
        moy = float(np.mean(est))
        self.assertGreater(moy, PHI_VRAI * 0.6, f"sigma2 moyen = {moy:.2f}")
        self.assertLess(moy, PHI_VRAI * 1.6, f"sigma2 moyen = {moy:.2f}")

    def test_c4_couverture_ic_parametre(self):
        """L'IC 95 % doit contenir le VRAI U_i ~95 fois sur 100.

        ⚠️ ORACLE HISTORIQUE : avant le correctif σ², la couverture mesurée
        valait 30,8 % sur 400 intervalles — un « intervalle à 95 % » qui
        contenait la vérité moins d'une fois sur trois. La cause était que la
        Hessienne de POISSON était inversée telle quelle, alors que Clark
        écrit ℓ_ODP = ℓ_Poisson/σ² : la covariance vaut σ²·H⁻¹.
        Un seuil à 80 % sépare sans ambiguïté les deux régimes.
        """
        dedans = total = 0
        for g in range(6):
            r = clark_ldf(_triangle(n=N_CAMP, phi=PHI_VRAI, graine=3000 + g),
                          courbes=['weibull'], annee_base=0, calculer_ic=True)
            if not r.get('success') or r['ic_95'][0][0] is None:
                continue
            for i, (lo, hi) in enumerate(r['ic_95']):
                total += 1
                if lo <= U_VRAIS[i] <= hi:
                    dedans += 1
        self.assertGreaterEqual(total, 40, 'campagne trop maigre')
        couv = dedans / total
        self.assertGreater(couv, 0.80,
                           f"couverture = {couv:.1%} — l'IC est trop etroit "
                           f"(regression du facteur sigma^2 ?)")

    def test_c5_ic_decompose_processus_et_parametre(self):
        """Les deux composantes de Clark (2003) sont présentes et se somment."""
        r = clark_ldf(_triangle(n=N_CAMP, phi=PHI_VRAI, graine=42), courbes=['weibull'],
                      annee_base=0, calculer_ic=True)
        self.assertTrue(r['success'])
        self.assertIsNotNone(r['se_reserve_totale'])
        for par, pro, tot in zip(r['se_parametre'], r['se_processus'],
                                 r['se_totale']):
            self.assertIsNotNone(par)
            self.assertIsNotNone(pro)
            self.assertAlmostEqual(tot, float(np.sqrt(par ** 2 + pro ** 2)),
                                   places=1)
        # la variance de processus n'est pas cosmétique : elle doit peser
        self.assertGreater(max(r['se_processus']), 0.0)

    def test_c6_chi2_porte_sur_les_cellules_ajustees(self):
        """Le χ² et le MLE doivent porter sur le MÊME ensemble de cellules.

        ⚠️ ORACLE HISTORIQUE : le χ² incluait les incréments négatifs que le
        masque du MLE excluait. Sur le triangle à recours, il valait 1 602,98
        sur 21 cellules au lieu de 75,14 sur 18 — les 3 cellules exclues
        portaient 95 % du chi-deux. σ² en aurait hérité d'un facteur 21.
        """
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA),
                         ('Recours', _TRI_RECOURS)):
            with self.subTest(triangle=nom):
                r = _fit(tri, annee_base=1, calculer_ic=False)
                if not r.get('success'):
                    continue
                self.assertEqual(r['residus']['n'], r['n_obs'],
                                 f"{nom} : chi2 sur {r['residus']['n']} cellules "
                                 f"mais MLE sur {r['n_obs']}")
                self.assertEqual(r['df'], r['n_obs'] - r['n_params'])

    def test_c7_verdict_structure_sur_verite_connue(self):
        """Le verdict doit se déclencher sur une reprise QUE J'INJECTE."""
        C = _triangle(phi=None)
        v_sain = _verdict_structure_monotone(C)
        self.assertTrue(v_sain['compatible'], 'faux positif sur triangle sain')
        self.assertTrue(v_sain['testable'])

        # J'encaisse un recours à partir de la colonne 3 : le cumulé redescend
        # entre les colonnes 2 et 3. `facteurs[j]` indexant la TRANSITION
        # j → j+1, la violation attendue porte donc l'indice 2.
        C_rec = C.copy()
        n = C.shape[0]
        for i in range(n):
            if i + 3 < n:
                C_rec[i, 3:n - i] -= 0.25 * C[i, 3]
        v_rec = _verdict_structure_monotone(C_rec)
        self.assertFalse(v_rec['compatible'],
                         'la reprise injectee n a pas ete detectee')
        self.assertIn(2, v_rec['colonnes_reprise'])
        self.assertLess(v_rec['facteur_min'], 1.0)
        self.assertIn('2→3', v_rec['message'])

    def test_c8_reserve_retenue_si_structure_incompatible(self):
        """Sur un triangle à recours, Clark ne publie PAS de réserve.

        Elle reste accessible en `reserve_brute` pour l'audit, jamais comme
        un chiffre que rien ne distingue de celui de Chain Ladder.
        """
        r = _fit(_TRI_RECOURS, annee_base=1, calculer_ic=False)
        self.assertTrue(r['success'])
        self.assertFalse(r['structure_monotone']['compatible'])
        self.assertIsNone(r['reserve_totale'])
        self.assertIsNone(r['reserve_be_clark'])
        self.assertIsNotNone(r['reserve_brute'])
        self.assertEqual(r['statut'], 'ROUGE')
        self.assertIn('monotone', r['message'])

    def test_c9_n_sur_developpement_ne_voit_pas_le_recours(self):
        """Verrou de la LIMITE : l'ancien signal reste muet, par construction.

        `n_sur_developpement` compare l'ultime ajusté au cumul observé. Sur un
        triangle à recours il vaut ZÉRO — la courbe croissante place l'ultime
        au-dessus du cumul pour toutes les années. Ce test fige le fait que ce
        compteur ne pouvait pas servir de verdict, et que ce n'est pas lui
        qu'on a « réparé ».
        """
        r = _fit(_TRI_RECOURS, annee_base=1, calculer_ic=False)
        self.assertEqual(r['n_sur_developpement'], 0)
        self.assertTrue(all(v >= 0 for v in r['ibnr_brut_par_annee']))
        self.assertFalse(r['structure_monotone']['compatible'])


# =============================================================================
#  NIVEAU 2 — STRUCTUREL
# =============================================================================

class TestClarkStructurel(unittest.TestCase):

    def test_c10_aucune_pollution_de_np_random(self):
        """Clark ne doit pas réécrire l'état global de np.random.

        ⚠️ ORACLE HISTORIQUE : un `np.random.seed(42)` mort — le module ne
        tire rien — écrasait le flux de l'appelant. Le Bootstrap ODP emploie
        la même API globale et n'était protégé que par son propre reseed.
        """
        np.random.seed(999)
        attendu = [np.random.rand() for _ in range(2)]
        np.random.seed(999)
        np.random.rand()
        clark_ldf(np.asarray(GENINS, float), annee_base=1, calculer_ic=False)
        self.assertAlmostEqual(np.random.rand(), attendu[1], places=12,
                               msg='Clark a reecrit le flux np.random global')

    def test_c11_un_rejet_donne_toujours_son_motif(self):
        """Aberrant ⇒ le message nomme la raison. Jamais de phrase vide.

        ⚠️ ORACLE HISTORIQUE : le critère testait `g_t2_min` (paramétrable)
        et le message testait 0.10 (en dur). Avec g_t2_min=0.60 le résultat
        était : « ⚠️ Clark weibull écarté — . » — une méthode écartée sans
        aucun motif.
        """
        for seuil in (CLARK_G_T2_MIN, 0.60, 0.95):
            with self.subTest(g_t2_min=seuil):
                r = clark_ldf(np.asarray(GENINS, float), annee_base=1,
                              calculer_ic=False, g_t2_min=seuil)
                if not r.get('aberrant'):
                    continue
                self.assertNotIn('— . ', r['message'],
                                 'rejet sans motif')
                self.assertRegex(r['message'], r'(tail factor|G\(t=2\)|convergé)')

    def test_c12_statut_publie_et_coherent(self):
        """Le statut existe et suit le message — l'app le lit pour la couleur."""
        r = _fit(GENINS, annee_base=1, calculer_ic=False)
        self.assertIn(r['statut'], ('VERT', 'AMBRE', 'ROUGE'))
        r_rec = _fit(_TRI_RECOURS, annee_base=1, calculer_ic=False)
        self.assertEqual(r_rec['statut'], 'ROUGE')

    def test_c13_annee_base_est_respectee(self):
        """La réserve dépend de annee_base — sinon le câblage est muet.

        ⚠️ ORACLE HISTORIQUE : `clark_ldf(C)` était appelé en ligne dans le
        dict de retour de l'agent, sans `annee_base`. Clark était la SEULE
        méthode à ne pas le recevoir.
        """
        C = np.asarray(GENINS, float)
        r0 = _fit(GENINS, annee_base=0, calculer_ic=False)
        r1 = _fit(GENINS, annee_base=1, calculer_ic=False)
        self.assertNotEqual(r0['reserve_totale'], r1['reserve_totale'])
        self.assertAlmostEqual(
            r0['reserve_totale'] - r1['reserve_totale'],
            r0['ibnr_brut_par_annee'][0], delta=1.0)

    def test_c14_perimetre_aucune_cle_fantome(self):
        """`elr` était un montant nommé comme un ratio. Il ne revient pas."""
        r = _fit(GENINS, annee_base=1, calculer_ic=False)
        self.assertNotIn('elr', r,
                         "'elr' designe un RATIO chez Clark (methode Cape Cod) ; "
                         "U_i est un MONTANT")

    def test_c15_acquis_double_tail_et_ic_symetrique(self):
        """Les correctifs f37b63b et ecc590e tiennent toujours."""
        C = np.asarray(GENINS, float)
        r = clark_ldf(C, annee_base=1, calculer_ic=True)
        ult = np.array(r['ultimates'], float)
        n, m = C.shape
        dern = np.array([C[i, max(j for j in range(m) if C[i, j] > 0)]
                         for i in range(n)])
        # IBNR = U - dernier cumul, SANS multiplication par le tail
        self.assertLess(
            float(np.max(np.abs(np.array(r['ibnr_brut_par_annee'], float)
                                - (ult - dern)))), 1.5)
        # IC symetrique autour de l'ultime (pas de x tail residuel)
        for u, (lo, hi) in zip(ult, r['ic_95']):
            if lo is None or lo <= 0:
                continue
            self.assertAlmostEqual((hi - u) - (u - lo), 0.0, delta=1.5)

    def test_c16_sigma2_du_meme_ordre_que_le_phi_du_bootstrap(self):
        """Deux estimateurs du MÊME paramètre doivent se recouper.

        Clark et le Bootstrap ODP posent tous deux Var = σ²·μ. Leurs
        ajustements diffèrent — courbe paramétrique contre chain-ladder — donc
        les valeurs diffèrent légitimement. Un écart d'un ORDRE DE GRANDEUR,
        lui, signalerait que l'un des deux ne mesure pas ce qu'il annonce.
        C'est ce recoupement qui manquait quand deux « φ » coexistaient.
        """
        from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import (
            calculer_facteurs)
        from direction_non_vie.provisionnement.a7_provisionnement.n3.bootstrap_odp import (
            bootstrap_odp)
        C = np.asarray(GENINS, float)
        s2 = _fit(GENINS, annee_base=1, calculer_ic=False)['sigma2']
        phi = bootstrap_odp(C, np.asarray(calculer_facteurs(C, 'standard')[0],
                                          float), n_sim=200, seed=42)['phi']
        self.assertIsNotNone(s2)
        self.assertIsNotNone(phi)
        ratio = max(s2, phi) / min(s2, phi)
        self.assertLess(ratio, 10.0,
                        f"sigma2 Clark = {s2:,.0f} vs phi Bootstrap = {phi:,.0f} "
                        f"— rapport x{ratio:.1f}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
