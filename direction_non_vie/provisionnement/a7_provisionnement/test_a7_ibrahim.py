"""
Tests A7 Ibrahim v1.0 — 6 oracles publiés (Chain Ladder / Mack / Clark / Bootstrap ODP)
Commande : python test_a7_ibrahim.py

Première couverture de tests du module A7 Provisionnement (jusqu'ici : zéro test).
Les oracles sont des références EXTERNES vérifiables (aucune valeur auto-générée) :

  · GenIns / Taylor & Ashe (1983)  — réserve Chain Ladder = 18 680 856
  · RAA    / Mack (1993)           — réserve = 52 135 ; erreur-type Mack = 26 909
    (valeurs de référence du package R « ChainLadder », MackChainLadder(RAA)/(GenIns))

Trois tests portent le marqueur @unittest.expectedFailure : ils documentent des bugs
CONFIRMÉS par exécution. Chacun contient l'assertion CORRECTE (post-correctif) et
échoue donc AUJOURD'HUI. Quand le bug sera corrigé, l'assertion passera au vert et
le test deviendra un « unexpected success » — signal que le correctif doit RETIRER
le marqueur @unittest.expectedFailure. Ne jamais affaiblir ces assertions.
"""
import sys, unittest
import os as _os
sys.path.insert(0, _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '../../../../')))

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import chain_ladder
from direction_non_vie.provisionnement.a7_provisionnement.n3.mack import mack_1993
from direction_non_vie.provisionnement.a7_provisionnement.n3.clark import clark_ldf
from direction_non_vie.provisionnement.a7_provisionnement.n3.bootstrap_odp import bootstrap_odp


# =============================================================================
#  TRIANGLES DE RÉFÉRENCE
# =============================================================================

# GenIns / Taylor & Ashe (1983) — paiements INCRÉMENTAUX (on cumule par cumsum)
_INC_GENINS = [
    [357848, 766940, 610542, 482940, 527326, 574398, 146342, 139950, 227229, 67948],
    [352118, 884021, 933894, 1183289, 445745, 320996, 527804, 266172, 425046],
    [290507, 1001799, 926219, 1016654, 750816, 146923, 495992, 280405],
    [310608, 1108250, 776189, 1562400, 272482, 352053, 206286],
    [443160, 693190, 991983, 769488, 504851, 470639],
    [396132, 937085, 847498, 805037, 705960],
    [440832, 847631, 1131398, 1063269],
    [359480, 1061648, 1443370],
    [376686, 986608],
    [344014],
]

# RAA / Mack (1993) — paiements déjà CUMULÉS (ne PAS re-cumuler). Zone inconnue = 0.
_RAA = [
    [5012, 8269, 10907, 11805, 13539, 16181, 18009, 18608, 18662, 18834],
    [106, 4285, 5396, 10666, 13782, 15599, 15496, 16169, 16704],
    [3410, 8992, 13873, 16141, 18735, 22214, 22863, 23466],
    [5655, 11555, 15766, 21266, 23425, 26083, 27067],
    [1092, 9565, 15836, 22169, 25955, 26180],
    [1513, 6445, 11702, 12935, 15852],
    [557, 4020, 10946, 12314],
    [1351, 6947, 13112],
    [3133, 5395],
    [2063],
]


def _triangle_genins():
    """GenIns cumulé (n×n), zone inconnue à 0."""
    n = len(_INC_GENINS)
    C = np.zeros((n, n))
    for i, row in enumerate(_INC_GENINS):
        C[i, :len(row)] = np.cumsum(row)
    return C


def _triangle_raa():
    """RAA cumulé (n×n), zone inconnue à 0."""
    n = len(_RAA)
    C = np.zeros((n, n))
    for i, row in enumerate(_RAA):
        C[i, :len(row)] = row
    return C


GENINS = _triangle_genins()
RAA    = _triangle_raa()


# =============================================================================
#  CHAIN LADDER — oracle GenIns (VERT)
# =============================================================================

class T1_ChainLadder_GenIns(unittest.TestCase):
    """Chain Ladder sur GenIns : réserve et IBNR de l'année totalement développée."""

    def test_chain_ladder_genins_reserve(self):
        """Réserve CL GenIns = 18 680 856 (Taylor & Ashe 1983 / R ChainLadder)."""
        r = chain_ladder(GENINS, tail_force=1.0)
        self.assertAlmostEqual(r['reserve_totale'], 18_680_856, delta=1)
        print(f"    OK T1 CL GenIns : reserve = {r['reserve_totale']:,.0f} EUR")

    def test_chain_ladder_genins_annee0_zero(self):
        """L'année 0 (1ère ligne) est totalement développée -> IBNR = 0."""
        r = chain_ladder(GENINS, tail_force=1.0)
        self.assertAlmostEqual(r['ibnr_par_annee'][0], 0.0, delta=1.0)
        print(f"    OK T2 CL GenIns : IBNR annee 0 = {r['ibnr_par_annee'][0]:,.2f} EUR")


# =============================================================================
#  MACK 1993 — oracle RAA
# =============================================================================

class T2_Mack_RAA(unittest.TestCase):
    """Mack 1993 sur RAA : consomme les sorties de chain_ladder comme le fait l'agent."""

    def _mack_raa(self):
        rc = chain_ladder(RAA, tail_force=1.0)
        return rc, mack_1993(
            RAA,
            rc['facteurs'],
            rc['facteurs_indiv'],
            rc['ultimates'],
            rc['ibnr_par_annee'],
        )

    def test_mack_reserve_raa(self):
        """Réserve best estimate Mack RAA = 52 135 (Mack 1993 / R ChainLadder)."""
        _, mk = self._mack_raa()
        self.assertAlmostEqual(mk['reserve_best_estimate'], 52_135, delta=1)
        print(f"    OK T3 Mack RAA : reserve = {mk['reserve_best_estimate']:,.0f} EUR")

    def test_mack_se_raa(self):
        """Erreur-type Mack RAA = 26 909 (Mack 1993 / R ChainLadder).

        Vérifie le correctif B1 (terme croisé, calculer_variance_totale) : la
        borne d'agrégation du terme de covariance entre années i<l démarre à
        k_i (année ancienne = queue de développement commune), et non k_l
        (année récente). Avant correctif, la plage trop large sur-comptait la
        covariance -> sigma_total ~42 873 (+59% vs la référence 26 909).
        """
        _, mk = self._mack_raa()
        self.assertAlmostEqual(mk['sigma_total'], 26_909, delta=5)
        print(f"    OK T4 Mack RAA : sigma_total = {mk['sigma_total']:,.0f} EUR")


# =============================================================================
#  CLARK 2003 — oracle GenIns (année développée)
# =============================================================================

class T3_Clark_GenIns(unittest.TestCase):
    """Clark 2003 sur GenIns : IBNR de l'année totalement développée."""

    @unittest.expectedFailure
    def test_clark_annee0_developpee(self):
        """L'année 0 est totalement développée -> IBNR ~ tail seul (quelques milliers).

        ÉCHEC ATTENDU — bug B3 (double comptage du tail, clark.py:331-334) :
        l'ultime affiché = U_i × tail alors que le paramètre MLE U_i EST déjà
        l'ultime à l'infini. L'année 0 reçoit ~59 904 EUR d'IBNR au lieu de
        ~7 500 EUR (tail seul). Correctif : IBNR = U_i - obs_last (sans × tail).
        Ce test passera au vert une fois B3 corrigé -> RETIRER alors ce marqueur.
        """
        r = clark_ldf(GENINS)
        self.assertLess(r['ibnr_par_annee'][0], 10_000)


# =============================================================================
#  BOOTSTRAP ODP — cohérence avec le S.E. de Mack (oracle RAA)
# =============================================================================

class T4_Bootstrap_RAA(unittest.TestCase):
    """Bootstrap ODP sur RAA : la prediction-error doit être cohérente avec Mack."""

    @unittest.expectedFailure
    def test_bootstrap_coherence_mack_raa(self):
        """std bootstrap ODP ~ S.E. Mack (England & Verrall 2002 <-> Mack 1993).

        Sur un même triangle, la prediction-error du bootstrap ODP doit être
        proche de l'erreur-type de Mack (26 909 pour RAA). Fenêtre ±30% :
        [18 836 ; 34 982].

        ÉCHEC ATTENDU — bug B2 (bootstrap_odp.py) : résidus de Pearson et facteur
        de sur-dispersion calculés sur les CUMULÉS (au lieu des incréments E&V),
        bruit de processus sur le cumulé, pas de tail. std actuel ~103 647 pour RAA
        (seed=99), largement hors fenêtre.
        Ce test passera au vert une fois B2 corrigé -> RETIRER alors ce marqueur.
        """
        rc = chain_ladder(RAA, tail_force=1.0)
        bo = bootstrap_odp(RAA, rc['facteurs'], n_sim=3000, seed=99)
        self.assertTrue(18_836 <= bo['std_bootstrap'] <= 34_982)


if __name__ == '__main__':
    unittest.main()
