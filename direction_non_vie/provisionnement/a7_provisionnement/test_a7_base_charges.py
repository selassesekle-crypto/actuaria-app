# =============================================================================
#  Tests — BASE CHARGES : réintégration des provisions dossier (lot 8b)
#
#  LA DETTE IMPÉRATIVE, portée depuis le module 2 du Bloc II. Les méthodes N3
#  calculent toutes `ultime − dernière diagonale DU TRIANGLE REÇU`. Sur un
#  triangle de CHARGES, cette diagonale est la charge à date : chaque réserve —
#  et donc le BE — vaut l'IBNR PUR. Il manque les provisions dossier, déjà
#  comprises dans les charges mais pas encore payées. Or le BE S2 (Art. 77) est
#  l'ensemble des flux FUTURS, soit `ultime − PAYÉ à date`.
#
#      ultime − payé  =  (ultime − charges)  +  (charges − payé)
#      réserve totale =      IBNR pur        + provisions dossier
#
#  L'exemple de référence, reproduit tel quel ci-dessous :
#      ultime 300, charge 270, payé 50
#      sans correction : 300 − 270 =  30   ← le bug (BE sous-estimé)
#      avec correction :  30 + 220 = 250   ← correct (220 = 270 − 50)
# =============================================================================

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement, _provisions_dossier,
)
from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate import (
    BestEstimateS2,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, _forcer_reserve,
)
from direction_non_vie.services.nv_triangle import preparer_triangles

# Triangles où l'ANNÉE 1 porte exactement l'exemple : payé 50, charge 270.
PAIEMENTS = np.array([[100., 180., 200.],
                      [ 40.,  50.,   0.],
                      [ 30.,   0.,   0.]])
CHARGES   = np.array([[260., 290., 300.],
                      [250., 270.,   0.],
                      [240.,   0.,   0.]])


class T1_Exemple_De_Reference(unittest.TestCase):
    """L'exemple connu, prouvé au niveau où le calcul se fait (N4)."""

    @classmethod
    def setUpClass(cls):
        """n2/n3 réels, dont on force la réserve à l'IBNR PUR de l'exemple (30)."""
        r = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, n_sim_bootstrap=100,
            generer_graphiques=False, generer_word=False, generer_pdf_flag=False)
        cls.n2, cls.C = r['n2'], np.array(r['triangle'])
        cls.n3 = r['n3']
        # Une seule méthode incluse, à 30 : le BE vaut donc exactement 30.
        #
        # LEVIER MIS À JOUR — lot B : N4 agrège ANNÉE PAR ANNÉE et lit désormais
        # `ibnr_par_annee`, l'admissibilité restant jugée sur `reserve_totale`.
        # Forcer le seul total ne commanderait plus le résultat. `_forcer_reserve`
        # impose les deux, cohérents entre eux — l'invariant que verrouille T24.
        _forcer_reserve(cls.n3['chain_ladder'], 30.0)
        _forcer_reserve(cls.n3['bf'],            0.0)   # r == 0 → exclue
        _forcer_reserve(cls.n3['cape_cod'],      0.0)

    def test_sans_correction_be_vaut_l_ibnr_pur(self):
        """LE BUG : en base charges sans correction, le BE reste l'IBNR pur."""
        n4 = BestEstimateS2().calculer(self.n2, self.n3, self.C)
        self.assertAlmostEqual(n4['best_estimate'], 30.0, delta=0.5)
        self.assertAlmostEqual(n4['provisions_dossier'], 0.0, delta=0.5)
        print("    OK 8b-a sans correction : BE = 30 (IBNR pur — le bug)")

    def test_avec_correction_be_vaut_la_reserve_totale(self):
        """LE CORRECTIF : + provisions dossier (270 − 50 = 220) → 250."""
        n4 = BestEstimateS2().calculer(self.n2, self.n3, self.C,
                                       provisions_dossier=220.0)
        self.assertAlmostEqual(n4['best_estimate'], 250.0, delta=0.5)
        self.assertAlmostEqual(n4['be_ibnr_pur'], 30.0, delta=0.5)
        self.assertAlmostEqual(n4['provisions_dossier'], 220.0, delta=0.5)
        print("    OK 8b-b avec correction : BE = 30 + 220 = 250 (correct)")

    def test_decomposition_exposee_sans_confusion(self):
        """Aucune confusion silencieuse : l'IBNR pur et les provisions restent
        lisibles à côté du BE total."""
        n4 = BestEstimateS2().calculer(self.n2, self.n3, self.C,
                                       provisions_dossier=220.0)
        self.assertAlmostEqual(
            n4['be_ibnr_pur'] + n4['provisions_dossier'], n4['best_estimate'],
            delta=1.0)
        print("    OK 8b-c décomposition exposée : be_ibnr_pur + provisions = BE")

    def test_aval_derive_du_be_corrige(self):
        """Tout ce qui dérive du BE (SCR, percentiles) part du chiffre CORRIGÉ."""
        sans = BestEstimateS2().calculer(self.n2, self.n3, self.C)
        avec = BestEstimateS2().calculer(self.n2, self.n3, self.C,
                                         provisions_dossier=220.0)
        self.assertGreater(avec['scr']['scr_provisions'], sans['scr']['scr_provisions'])
        self.assertGreater(avec['reserve_p90'], sans['reserve_p90'])
        print("    OK 8b-d SCR et percentiles dérivent du BE corrigé")


class T2_Calcul_Des_Provisions(unittest.TestCase):
    """`_provisions_dossier` lit ce que la façade a construit, sans recalculer."""

    def _prep(self, **kw):
        return preparer_triangles(PAIEMENTS, source_charges=CHARGES,
                                  mode_paiements='cumule', mode_charges='cumule',
                                  **kw)

    def test_ecart_par_annee_conforme_a_l_exemple(self):
        p = self._prep(triangle_reference='charges')
        t = p.triangles
        n, m = t.charges.shape
        diag_ch = np.array([t.charges[i, min(n - i - 1, m - 1)] for i in range(n)])
        # année 1 : charge 270 − payé 50 = 220, exactement l'exemple
        self.assertAlmostEqual(diag_ch[1], 270.0, delta=0.5)
        self.assertAlmostEqual(t.diagonale_paiements[1], 50.0, delta=0.5)
        self.assertAlmostEqual(diag_ch[1] - t.diagonale_paiements[1], 220.0, delta=0.5)
        print("    OK 8b-e écart année 1 : charge 270 − payé 50 = 220")

    def test_base_paiements_ne_declenche_rien(self):
        """Rétro-compatibilité : en base paiements, aucune réintégration."""
        p = self._prep(triangle_reference='paiements')
        n1 = {'alertes': [], 'infos': []}
        self.assertIsNone(_provisions_dossier(
            {'preparation': p}, 'paiements', 1, n1))
        self.assertEqual(n1['infos'], [])
        print("    OK 8b-f base paiements : provisions_dossier = None (rien ne change)")

    def test_base_charges_calcule_et_trace(self):
        p = self._prep(triangle_reference='charges')
        n1 = {'alertes': [], 'infos': []}
        prov = _provisions_dossier({'preparation': p}, 'charges', 1, n1)
        # années 1 et 2 : (270−50) + (240−30) = 220 + 210 = 430
        self.assertAlmostEqual(prov, 430.0, delta=0.5)
        self.assertTrue(any('provisions dossier réintégrées' in i for i in n1['infos']))
        print(f"    OK 8b-g base charges : provisions = {prov:.0f} (220 + 210), tracées")

    def test_charges_absentes_alerte_et_ne_devine_pas(self):
        """Sans triangle de paiements, on ALERTE que le BE reste l'IBNR pur —
        un chiffre inventé serait pire que rien."""
        p = preparer_triangles(CHARGES, mode_paiements='cumule')
        n1 = {'alertes': [], 'infos': []}
        prov = _provisions_dossier({'preparation': p}, 'charges', 1, n1)
        self.assertIsNone(prov)
        self.assertTrue(any('IBNR PUR' in a for a in n1['alertes']))
        print("    OK 8b-h paiements absents : None + alerte « BE reste l'IBNR pur »")


class T3_Non_Regression(unittest.TestCase):
    """Le cas par défaut (base paiements) ne doit RIEN changer."""

    def test_run_complet_base_paiements_inchange(self):
        """Un run standard : provisions_dossier absent, be_ibnr_pur == BE."""
        r = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, n_sim_bootstrap=100,
            generer_graphiques=False, generer_word=False, generer_pdf_flag=False)
        n4 = r['n4']
        self.assertAlmostEqual(n4['provisions_dossier'], 0.0, delta=0.5)
        self.assertAlmostEqual(n4['be_ibnr_pur'], n4['best_estimate'], delta=1.0)
        # CONSTANTE MISE À JOUR — lot « décalage f_cum » : 20 580 806 → 20 997 282.
        # Le BE est la moyenne pondérée CL / BF / Cape Cod. CL est inchangé, mais
        # BF et Cape Cod consomment `pct_developpe`, lui-même dérivé des facteurs
        # cumulés qui omettaient le dernier facteur : leurs réserves étaient
        # sous-estimées de 3 à 5 %, d'où +2,02 % sur le BE. L'invariant testé ici
        # (base paiements ⇒ provisions_dossier = 0 et be_ibnr_pur == BE) est
        # intact ; seule la valeur épinglée était périmée.
        #
        # CONSTANTE MISE À JOUR À NOUVEAU — lot B : 20 997 282 → 21 023 363. Le
        # mécanisme de sélection repose désormais sur la couverture du motif,
        # année par année, avec des poids égaux entre méthodes admises. Effets
        # isolés sur GenIns : poids égaux +98 841, puis filet sur l'année 9
        # (motif NON VALIDÉE) −770 968.
        self.assertAlmostEqual(n4['best_estimate'], 21_023_363, delta=2)  # oracle
        print(f"    OK 8b-i run base paiements : BE = {n4['best_estimate']:,.0f} inchangé")

    def test_triangle_reference_expose_dans_run(self):
        """Le paramètre existe et vaut 'paiements' par défaut."""
        import inspect
        params = inspect.signature(AgentA7Provisionnement.run).parameters
        self.assertIn('triangle_reference', params)
        self.assertEqual(params['triangle_reference'].default, 'paiements')
        print("    OK 8b-j triangle_reference exposé dans run(), défaut 'paiements'")


class T4_Bout_En_Bout(unittest.TestCase):
    """Le câblage complet `run(triangle_reference='charges')`, sur un cas où la
    bonne réponse est connue INDÉPENDAMMENT du code testé.

    Construction : charge à date = mi-chemin entre payé à date et ultime. C'est
    économiquement ce qu'est une estimation dossier, c'est monotone (moyenne
    d'un cumulé croissant et d'une constante), et surtout les ultimes sont les
    MÊMES qu'en base paiements — donc la réserve totale doit l'être aussi.
    """

    @classmethod
    def setUpClass(cls):
        G = np.array(GENINS, dtype=float)
        n, m = G.shape
        f = [float(np.sum(G[:n - j - 1, j + 1]) / np.sum(G[:n - j - 1, j]))
             for j in range(m - 1)]
        cls.U = np.array([G[i, n - i - 1] * float(np.prod(f[n - i - 1:]))
                          for i in range(n)])
        cls.diag_paye = np.array([G[i, n - i - 1] for i in range(n)])
        charges = np.zeros_like(G)
        for i in range(n):
            for j in range(n - i):
                charges[i, j] = 0.5 * G[i, j] + 0.5 * cls.U[i]
        kw = dict(n_sim_bootstrap=200, generer_graphiques=False,
                  generer_word=False, generer_pdf_flag=False, mode_declare='cumule')
        a = AgentA7Provisionnement(verbose=False)
        cls.r_paie = a.run(source=GENINS, triangle_engage=charges,
                           triangle_reference='paiements', **kw)
        cls.r_chrg = a.run(source=GENINS, triangle_engage=charges,
                           triangle_reference='charges', **kw)

    def test_les_deux_runs_aboutissent(self):
        self.assertTrue(self.r_paie['success'])
        self.assertTrue(self.r_chrg['success'])

    def test_provisions_egales_au_calcul_a_la_main(self):
        """Σ(charge − payé) = 0,5 × Σ(ultime − payé), par construction."""
        attendu = float(np.sum(0.5 * (self.U[1:] - self.diag_paye[1:])))
        self.assertAlmostEqual(
            self.r_chrg['n4']['provisions_dossier'], attendu, delta=1.0)
        print(f"    OK 8b-k provisions bout-en-bout = {attendu:,.0f} "
              f"(= calcul independant, a l'euro)")

    def test_chain_ladder_retrouve_la_reserve_s2(self):
        """L'INVARIANT FORT : mêmes ultimes ⇒ même réserve totale. Sur le
        chain ladder — la seule méthode sans a priori exogène — l'IBNR pur des
        charges PLUS les provisions dossier doit retomber sur la réserve
        calculée en base paiements."""
        cl_paie = self.r_paie['n3']['chain_ladder']['reserve_totale']
        cl_chrg = self.r_chrg['n3']['chain_ladder']['reserve_totale']
        prov    = self.r_chrg['n4']['provisions_dossier']
        self.assertAlmostEqual((cl_chrg + prov) / cl_paie, 1.0, delta=0.01)
        # et sans la correction, on serait à ~la moitié : le bug est bien réel
        self.assertLess(cl_chrg / cl_paie, 0.60)
        print(f"    OK 8b-l CL : {cl_chrg:,.0f} + {prov:,.0f} = {cl_chrg + prov:,.0f} "
              f"vs {cl_paie:,.0f} en base paiements ({100*((cl_chrg+prov)/cl_paie-1):+.2f}%)")

    def test_le_be_total_remonte_bien_apres_correction(self):
        """Le BE pondéré ne peut pas égaler celui de la base paiements — BF et
        Cape Cod, qui pèsent la moitié, s'appuient sur un a priori exogène qui
        se comporte autrement sur des charges. Ce qui doit être vrai, c'est que
        la correction rapproche fortement le BE de la bonne grandeur."""
        be_paie = self.r_paie['n4']['best_estimate']
        pur     = self.r_chrg['n4']['be_ibnr_pur']
        corrige = self.r_chrg['n4']['best_estimate']
        self.assertLess(abs(corrige - be_paie), abs(pur - be_paie))
        self.assertGreater(corrige, pur)
        print(f"    OK 8b-m BE : {pur:,.0f} (pur) → {corrige:,.0f} (corrige) "
              f"vers {be_paie:,.0f} (base paiements)")

    def test_decomposition_reste_lisible_avec_grands_sinistres(self):
        """Interaction avec la réintégration LLT, qui ÉCRASE `best_estimate` en
        aval de N4 : la décomposition se compare alors à `be_attritional`, et
        l'addition des grands sinistres part bien du BE corrigé."""
        G = np.array(GENINS, dtype=float)
        n, m = G.shape
        charges = np.zeros_like(G)
        for i in range(n):
            for j in range(n - i):
                charges[i, j] = 0.5 * G[i, j] + 0.5 * self.U[i]
        r = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, triangle_engage=charges, triangle_reference='charges',
            reserve_grands_sinistres=1_000_000.0, n_grands_sinistres=3,
            n_sim_bootstrap=200, generer_graphiques=False, generer_word=False,
            generer_pdf_flag=False, mode_declare='cumule')
        n4 = r['n4']
        self.assertTrue(n4['llt_applique'])
        self.assertAlmostEqual(
            n4['be_ibnr_pur'] + n4['provisions_dossier'], n4['be_attritional'],
            delta=1.0)
        self.assertAlmostEqual(
            n4['be_attritional'] + n4['reserve_grands_sinistres'],
            n4['best_estimate'], delta=1.0)
        self.assertAlmostEqual(
            n4['be_attritional'], self.r_chrg['n4']['best_estimate'], delta=1.0)
        print("    OK 8b-o LLT : decomposition pivote sur be_attritional, "
              "grands sinistres ajoutes au BE corrige")

    def test_base_paiements_identique_a_un_run_sans_charges(self):
        """Fournir un triangle de charges sans le désigner comme référence ne
        change RIEN au résultat : la correction est bien conditionnée."""
        # CONSTANTE MISE À JOUR DEUX FOIS — lot « décalage f_cum » (20 580 806 →
        # 20 997 282, BF et Cape Cod redressés) puis lot B (→ 21 023 363, nouveau
        # mécanisme de sélection). Ce que ce test vérifie — qu'un triangle de
        # charges NON désigné comme référence ne change rien — n'a jamais dépendu
        # de la valeur elle-même.
        self.assertAlmostEqual(
            self.r_paie['n4']['best_estimate'], 21_023_363, delta=2)
        self.assertAlmostEqual(self.r_paie['n4']['provisions_dossier'], 0.0, delta=0.5)
        print("    OK 8b-n charges fournies mais base paiements : BE inchange")


if __name__ == '__main__':
    unittest.main()
