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
from direction_non_vie.provisionnement.a7_provisionnement.n3.glm_apc_poisson import (
    glm_apc_poisson, STATSMODELS_OK as _APC_SM_OK,
)
from direction_non_vie.provisionnement.a7_provisionnement.config.lob_config import (
    get_lob_config, list_lobs,
)
from direction_non_vie.provisionnement.a7_provisionnement.agent import AgentA7Provisionnement

try:
    import docx as _docx  # noqa: F401  (python-docx — requis pour T8 export_word)
    _DOCX_OK = True
except Exception:
    _DOCX_OK = False


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

    def test_clark_annee0_developpee(self):
        """L'année 0 est totalement développée -> IBNR ~ tail seul (quelques milliers).

        Vérifie le correctif B3 (clark.py, _calculer_resultats) : le paramètre
        MLE U_i EST déjà l'ultime à l'infini (G->1), donc IBNR_i = U_i - obs_last
        (sans re-multiplier par tail_factor, qui reste calculé pour le diagnostic).
        Avant correctif, l'année 0 recevait ~59 904 EUR d'IBNR (double comptage
        du tail) au lieu de ~7 546 EUR (tail résiduel seul).
        """
        r = clark_ldf(GENINS)
        self.assertLess(r['ibnr_par_annee'][0], 10_000)
        print(f"    OK T5 Clark GenIns : IBNR annee 0 = {r['ibnr_par_annee'][0]:,.0f} EUR")


# =============================================================================
#  BOOTSTRAP ODP — cohérence avec le S.E. de Mack (oracle RAA)
# =============================================================================

class T4_Bootstrap_RAA(unittest.TestCase):
    """Bootstrap ODP sur RAA : la prediction-error doit être cohérente avec Mack."""

    def test_bootstrap_coherence_mack_raa(self):
        """std bootstrap ODP ~ S.E. Mack (England & Verrall 2002 <-> Mack 1993).

        Sur un même triangle, la prediction-error du bootstrap ODP doit être
        proche de l'erreur-type de Mack (26 909 pour RAA). Fenêtre ±30% :
        [18 836 ; 34 982].

        Vérifie le correctif B2 (bootstrap_odp.py) : résidus de Pearson, pseudo-
        triangle et bruit de processus portés sur les INCRÉMENTS (ODP England-
        Verrall) au lieu des cumulés, + recentrage de la distribution sur la
        réserve CL. Avant correctif, std ~103 647 pour RAA (seed=99, +285%).
        """
        rc = chain_ladder(RAA, tail_force=1.0)
        bo = bootstrap_odp(RAA, rc['facteurs'], n_sim=3000, seed=99)
        self.assertTrue(18_836 <= bo['std_bootstrap'] <= 34_982)
        print(f"    OK T6 Bootstrap RAA : std = {bo['std_bootstrap']:,.0f} EUR (Mack 26 909)")


# =============================================================================
#  CONFIG LoB — snapshot des valeurs effectives (anti-régression clés dupliquées)
# =============================================================================

# Valeurs effectives capturées AVANT le nettoyage des clés dupliquées de
# lob_config.py (3 blocs contenaient des clés définies plusieurs fois, Python
# gardant la dernière). Ce snapshot verrouille le comportement : toute édition
# qui change accidentellement une de ces valeurs fait échouer T7.
_LOB_REFERENCE = {
    'accidents_corporels':         {'risque_long': False, 'tail_seuil_stabilisation': 1.02, 'ratio_c0_primes': 0.4},
    'catastrophes_naturelles':     {'risque_long': False, 'tail_seuil_stabilisation': 1.02, 'ratio_c0_primes': 0.45},
    'construction':                {'risque_long': True,  'tail_seuil_stabilisation': 1.1,  'ratio_c0_primes': 0.04},
    'credit_caution':              {'risque_long': True,  'tail_seuil_stabilisation': 1.05, 'ratio_c0_primes': 0.15},
    'dommage_corporel_individuel': {'risque_long': True,  'tail_seuil_stabilisation': 1.05, 'ratio_c0_primes': 0.2},
    'generique':                   {'risque_long': True,  'tail_seuil_stabilisation': 1.02, 'ratio_c0_primes': 0.35},
    'incendie_dommages':           {'risque_long': False, 'tail_seuil_stabilisation': 1.01, 'ratio_c0_primes': None},
    'marine_aviation_transport':   {'risque_long': True,  'tail_seuil_stabilisation': 1.05, 'ratio_c0_primes': 0.25},
    'mrh':                         {'risque_long': False, 'tail_seuil_stabilisation': 1.01, 'ratio_c0_primes': 0.55},
    'protection_juridique':        {'risque_long': False, 'tail_seuil_stabilisation': 1.01, 'ratio_c0_primes': 0.4},
    'rc_auto_corporels':           {'risque_long': True,  'tail_seuil_stabilisation': 1.1,  'ratio_c0_primes': 0.08},
    'rc_auto_materiel':            {'risque_long': False, 'tail_seuil_stabilisation': 1.01, 'ratio_c0_primes': 0.45},
    'rc_generale':                 {'risque_long': True,  'tail_seuil_stabilisation': 1.05, 'ratio_c0_primes': 0.18},
    'rc_medicale':                 {'risque_long': True,  'tail_seuil_stabilisation': 1.1,  'ratio_c0_primes': 0.06},
    'transport':                   {'risque_long': True,  'tail_seuil_stabilisation': 1.05, 'ratio_c0_primes': 0.25},
}


class T7_LobConfig_Snapshot(unittest.TestCase):
    """Verrouille les valeurs effectives des blocs LoB (anti-régression B8)."""

    def test_lob_config_valeurs_effectives(self):
        """get_lob_config() renvoie les valeurs effectives attendues pour toutes les LoB."""
        # L'ensemble des LoB ne doit pas changer sans mise à jour de la référence
        lobs_config = set(list_lobs()) | {'generique'}
        self.assertEqual(
            set(_LOB_REFERENCE), lobs_config,
            "Ensemble des LoB modifié — mettre à jour _LOB_REFERENCE.",
        )
        # Chaque valeur sensible doit correspondre à la valeur effective d'origine
        for lob, attendu in _LOB_REFERENCE.items():
            cfg = get_lob_config(lob)
            for cle, val in attendu.items():
                self.assertEqual(
                    cfg.get(cle), val,
                    f"{lob}.{cle} = {cfg.get(cle)!r}, attendu {val!r} "
                    f"(valeur effective d'avant nettoyage B8).",
                )
        print(f"    OK T7 lob_config : {len(_LOB_REFERENCE)} LoB verrouillées "
              f"(risque_long / tail_seuil_stabilisation / ratio_c0_primes)")


# =============================================================================
#  LIVRABLES — les exports produisent des bytes (anti-régression exports)
# =============================================================================

class T8_Exports(unittest.TestCase):
    """Les livrables produisent des bytes sur le chemin par défaut (sans resultats_precedents).

    Ce test aurait attrapé la régression du Lot 1 (commit e94793d) : cv_nm1/100
    plantait sur None quand resultats_precedents est absent, faisant retomber
    tout export_excel à 0 bytes. Cette régression est restée invisible 2 lots
    pour deux raisons — TOUTES DEUX distinctes de « le code avale les erreurs »
    (le fail-loud logger.error + exc_info existait déjà dans les except des
    exports) :
      (1) aucun test n'exerçait export_excel / export_word — comblé ici ;
      (2) les scripts de vérification faisaient logging.disable(CRITICAL), qui
          masquait le logger.error déjà présent. En run agent réel l'erreur
          était bien loggée à ERROR.
    D'où ce test : il échoue si un export retombe à 0 bytes, quel que soit
    l'état du logging.
    """

    @classmethod
    def setUpClass(cls):
        # Agent réel sur GenIns, SANS resultats_precedents (le chemin par défaut
        # qui avait planté au Lot 1). Sorties réelles réutilisées pour les deux
        # asserts — plus robuste qu'un n3/n4 mocké qui divergerait du réel.
        cls.r = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, lob='generique', n_sim_bootstrap=300,
            generer_word=True, generer_pdf_flag=False, generer_graphiques=False,
        )

    def test_export_excel_produit_bytes(self):
        """export_excel produit > 0 bytes (openpyxl installé) — cf. régression Lot 1."""
        self.assertTrue(self.r.get('success'), self.r.get('erreur'))
        n = len(self.r.get('excel_bytes', b''))
        self.assertGreater(n, 0, "export_excel a produit 0 bytes — régression d'export ?")
        print(f"    OK T8 Excel : {n:,} bytes")

    @unittest.skipUnless(_DOCX_OK, "python-docx non installé")
    def test_export_word_produit_bytes(self):
        """export_word produit > 0 bytes (si python-docx disponible)."""
        n = len(self.r.get('word_bytes', b''))
        self.assertGreater(n, 0, "export_word a produit 0 bytes — régression d'export ?")
        print(f"    OK T8 Word : {n:,} bytes")


# =============================================================================
#  GLM POISSON APC (Renshaw-Verrall) — réserve = CL + test calendaire F quasi-Poisson
#  Remplace l'ancien module mal nommé/mal calibré 'barnett_zehnwirth'.
# =============================================================================

def _genins_transforme(fn):
    """GenIns cumulé après transformation fn(i, j, incrément) des incréments."""
    n = len(_INC_GENINS)
    C = np.zeros((n, n))
    for i, row in enumerate(_INC_GENINS):
        C[i, :len(row)] = np.cumsum([fn(i, j, row[j]) for j in range(len(row))])
    return C


def _triangle_separable():
    """Triangle séparable a_i × b_j — aucun effet calendaire par construction."""
    b = np.array([0.30, 0.25, 0.18, 0.10, 0.06, 0.04, 0.03, 0.02, 0.01, 0.01])
    a = np.array([1000, 1100, 1250, 1300, 1400, 1500, 1600, 1750, 1800, 1900.0])
    n = 10
    C = np.zeros((n, n))
    for i in range(n):
        C[i, :n-i] = np.cumsum([a[i]*b[j]*(1.0 + 0.03*(((i*7 + j*3) % 5) - 2)) for j in range(n-i)])
    return C


@unittest.skipUnless(_APC_SM_OK, "statsmodels non installé")
class T9_GLM_APC(unittest.TestCase):
    """GLM Poisson âge-période-cohorte (Renshaw-Verrall 1998).

    Deux garanties, toutes deux mesurées :
      · RÉSERVE âge-cohorte = chain-ladder (théorème Renshaw-Verrall) ;
      · TEST calendaire F quasi-Poisson : calme sur triangle propre ET sur
        inflation CONSTANTE (non identifiable sur le triangle seul — la
        signaler serait un faux positif) ; significatif sur une COURBURE
        injectée (oscillation, choc de dernière diagonale).
    """

    def test_reserve_apc_egale_cl_genins(self):
        """Réserve GLM âge-cohorte = réserve chain-ladder GenIns (Renshaw-Verrall)."""
        r = glm_apc_poisson(GENINS, annee_debut=2010, annee_base=1)
        self.assertTrue(r.get('success'), r.get('erreur'))
        res = r['reserve_apc']
        self.assertAlmostEqual(res / 18680856.0, 1.0, delta=0.005,
            msg=f"réserve APC = {res:,.0f}, attendu ~18 680 856 (= CL)")
        self.assertFalse(r['reserve_fallback_cl'], "fallback CL non attendu sur GenIns")
        print(f"    OK T9 réserve APC GenIns = {res:,.0f} (= CL)")

    def test_reserve_apc_egale_cl_separable(self):
        """Sur un triangle séparable, réserve APC = réserve chain-ladder."""
        C = _triangle_separable()
        cl = chain_ladder(C, tail_force=1.0)
        cl_res = cl.get('reserve_best_estimate', cl.get('reserve', cl.get('reserve_totale')))
        r = glm_apc_poisson(C, annee_debut=2010, annee_base=1)
        self.assertAlmostEqual(r['reserve_apc'] / cl_res, 1.0, delta=0.005,
            msg=f"APC={r['reserve_apc']:,.0f} vs CL={cl_res:,.0f}")
        print(f"    OK T9 réserve APC séparable = {r['reserve_apc']:,.0f} (= CL {cl_res:,.0f})")

    def test_calendaire_calme_sur_genins_brut(self):
        """GenIns brut (sans choc calendaire connu) : non significatif → VERT."""
        r = glm_apc_poisson(GENINS, annee_debut=2010)
        self.assertFalse(r['cal_significatif'], f"faux positif (p={r['p_calendaire']})")
        self.assertEqual(r['statut'], 'VERT')
        print(f"    OK T9 GenIns brut : VERT (p={r['p_calendaire']})")

    def test_inflation_constante_non_signalee(self):
        """Oracle d'honnêteté : une inflation CONSTANTE (non identifiable sur le
        triangle seul) NE doit PAS être signalée — sinon faux positif."""
        C = _genins_transforme(lambda i, j, x: x * (1.10 ** (i + j)))
        r = glm_apc_poisson(C, annee_debut=2010)
        self.assertFalse(r['cal_significatif'],
            f"inflation constante signalée à tort (p={r['p_calendaire']})")
        self.assertEqual(r['statut'], 'VERT')
        print(f"    OK T9 inflation constante 10%/an : VERT (correct, p={r['p_calendaire']})")

    def test_courbure_oscillation_detectee(self):
        """Oscillation ±30 % par diagonale (courbure pure) : significatif → AMBRE."""
        C = _genins_transforme(lambda i, j, x: x * 1.30 if (i + j) % 2 == 0 else x * 0.70)
        r = glm_apc_poisson(C, annee_debut=2010)
        self.assertTrue(r['cal_significatif'], f"oscillation non détectée (p={r['p_calendaire']})")
        self.assertEqual(r['statut'], 'AMBRE')
        print(f"    OK T9 oscillation ±30% : AMBRE (p={r['p_calendaire']})")

    def test_choc_derniere_diagonale_detecte(self):
        """Choc ×2 sur la dernière diagonale (biais BE direct) : significatif → AMBRE."""
        C = _genins_transforme(lambda i, j, x: x * 2.0 if (i + j) == 9 else x)
        r = glm_apc_poisson(C, annee_debut=2010)
        self.assertTrue(r['cal_significatif'], f"choc non détecté (p={r['p_calendaire']})")
        self.assertEqual(r['statut'], 'AMBRE')
        print(f"    OK T9 choc dernière diagonale ×2 : AMBRE (p={r['p_calendaire']})")


if __name__ == '__main__':
    unittest.main()
