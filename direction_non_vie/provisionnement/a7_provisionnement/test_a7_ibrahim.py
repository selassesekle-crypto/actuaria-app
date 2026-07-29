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

from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import (
    chain_ladder, calculer_facteurs,
)
from direction_non_vie.provisionnement.a7_provisionnement.n3.mack import mack_1993
from direction_non_vie.provisionnement.a7_provisionnement.n3.clark import clark_ldf
from direction_non_vie.provisionnement.a7_provisionnement.n3.bootstrap_odp import bootstrap_odp
from direction_non_vie.provisionnement.a7_provisionnement.n3.munich_cl import (
    munich_cl, valider_prerequis,
    _calculer_lambda as _mcl_lambda,        # T21 : chaîne λ depuis la source unique
)
from direction_non_vie.services.nv_triangle_projection import projeter_ultimates
from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate import (
    garde_fou_be_negatif, BestEstimateS2,
)
from direction_non_vie.provisionnement.a7_provisionnement.n3.glm_apc_poisson import (
    glm_apc_poisson, STATSMODELS_OK as _APC_SM_OK,
    _to_long as _glm_to_long, FLOOR_Y as _GLM_FLOOR_Y,   # T12 : preuve d'équivalence increments_positifs
)
from direction_non_vie.provisionnement.a7_provisionnement.n3.barnett_zehnwirth_ptf import (
    barnett_zehnwirth_ptf, STATSMODELS_OK as _PTF_SM_OK,
    _to_long_log as _bz_to_long_log,                     # T12 : preuve d'équivalence increments_positifs
)
from direction_non_vie.services.nv_triangle_negatifs import (
    signaler_negatifs, increments_positifs,
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


def _forcer_reserve(bloc: dict, total: float, annee_base: int = 1) -> None:
    """Impose une réserve à un bloc de méthode N3, EN GARDANT LA COHÉRENCE.

    Depuis le lot B, N4 agrège année par année : il lit `ibnr_par_annee`, tandis
    que l'admissibilité d'une méthode se juge encore sur `reserve_totale`. Forcer
    l'un sans l'autre laisserait le test piloter une grandeur qui ne commande
    plus rien — c'est exactement ce qui a fait tomber T17 et les oracles de base
    charges au lot B, sans qu'aucun d'eux ne soit faux pour autant.

    Le montant est porté par la dernière année, les précédentes mises à zéro :
    peu importe la répartition, seule compte la somme, et l'invariant
    `reserve_totale == Σ ibnr_par_annee[annee_base:]` est respecté (T24).
    """
    n = len(bloc.get('ibnr_par_annee') or [0.0])
    valeurs = [0.0] * n
    if n > annee_base:
        valeurs[-1] = float(total)
    bloc['ibnr_par_annee'] = valeurs
    if 'ibnr_brut_par_annee' in bloc:
        bloc['ibnr_brut_par_annee'] = list(valeurs)
    bloc['reserve_totale'] = float(total)


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


# =============================================================================
#  BARNETT-ZEHNWIRTH PTF log-normal — ÉTAPE 2a (détection tendances/ruptures)
#  Triangles synthétiques à tendances CONNUES (seed fixe, reproductibles).
# =============================================================================

def _make_cum_ptf(cal_fn, devfn=None, seed=7):
    """Triangle cumulé log-normal à tendances connues (oracles B&Z PTF).

    Incréments p_wd = exp(niveau_w + dev(d) + calendaire(w+d) + N(0, 0.20)).
    """
    n = 10
    A = 12.0 + 0.05*np.arange(n)
    G = (lambda d: -0.45*d) if devfn is None else devfn
    C = np.zeros((n, n))
    np.random.seed(seed)
    for w in range(n):
        incs = [np.exp(A[w] + G(d) + cal_fn(w+d) + np.random.normal(0, 0.20)) for d in range(n-w)]
        C[w, :n-w] = np.cumsum(incs)
    return C


@unittest.skipUnless(_PTF_SM_OK, "statsmodels non installé")
class T10_BZ_PTF(unittest.TestCase):
    """B&Z PTF log-normal (2a) : détecte les CHANGEMENTS de tendance, pas
    l'inflation constante (mur d'identifiabilité). Tendances injectées connues."""

    R = float(np.log(1.12))    # +12 %/an en log

    def test_clean_pas_de_fausse_rupture(self):
        """Triangle propre + rupture déclarée en année 2010+5=2015 → NON sig (VERT)."""
        r = barnett_zehnwirth_ptf(_make_cum_ptf(lambda t: 0.0), ruptures_calendaires=[2015], annee_debut=2010)
        self.assertTrue(r['disponible'], r.get('message'))
        self.assertFalse(r['calendaire_significatif'], f"faux positif p={r['p_bloc_calendaire']}")
        self.assertEqual(r['statut'], 'VERT')
        print(f"    OK T10 clean : VERT (p={r['p_bloc_calendaire']})")

    def test_inflation_constante_non_identifiable(self):
        """Oracle d'IDENTIFIABILITÉ : inflation CONSTANTE (absorbée par âge+dev)
        → NON détectée. Miroir de l'étape 1 : B&Z n'échappe pas au mur."""
        r = barnett_zehnwirth_ptf(_make_cum_ptf(lambda t: self.R * t), ruptures_calendaires=[2015], annee_debut=2010)
        self.assertFalse(r['calendaire_significatif'],
                         f"inflation constante signalée à tort p={r['p_bloc_calendaire']}")
        self.assertEqual(r['statut'], 'VERT')
        print(f"    OK T10 inflation constante : NON détectée (p={r['p_bloc_calendaire']}) — mur d'identifiabilité")

    def test_rupture_kink_detectee_localisee_pente(self):
        """Rupture calendaire à t0=5, +12 %/an → détectée (AMBRE), pente dans l'IC."""
        r = barnett_zehnwirth_ptf(_make_cum_ptf(lambda t: self.R * max(0, t-5)),
                                  ruptures_calendaires=[2015], annee_debut=2010)
        self.assertTrue(r['calendaire_significatif'], f"rupture manquée p={r['p_bloc_calendaire']}")
        self.assertEqual(r['statut'], 'AMBRE')
        self.assertLess(r['p_bloc_calendaire'], 0.05)
        det = r['ruptures_calendaires_testees'][0]
        self.assertTrue(det['significatif'])
        self.assertEqual(det['rupture_t'], 5)
        self.assertEqual(det['annee'], 2015)          # rapporté en ANNÉE, pas en indice
        # pente injectée (log) +0.1133 dans l'IC 95 % de l'estimé
        self.assertLess(abs(det['delta_log'] - self.R), 1.96 * det['se'] + 1e-3,
                        f"pente injectée hors IC : est={det['delta_log']} se={det['se']}")
        # IC 95 % explicite en %/an : doit contenir le +12 % injecté
        self.assertIsNotNone(det['ic95_pct_par_an'], "ic95_pct_par_an absent")
        _ic_inf, _ic_sup = det['ic95_pct_par_an']
        self.assertLessEqual(_ic_inf, 12.0)
        self.assertGreaterEqual(_ic_sup, 12.0)
        print(f"    OK T10 kink t0=5 : AMBRE p={r['p_bloc_calendaire']}, "
              f"pente {det['delta_pct_par_an']:+.1f}%/an IC95=[{_ic_inf:+.1f} ; {_ic_sup:+.1f}] (injecté +12 %)")

    def test_rupture_developpement_detectee(self):
        """Rupture de tendance DÉVELOPPEMENT à d0=4 (déclarée) → détectée."""
        def dev(d): return (-0.30*d) if d <= 4 else (-0.30*4 - 0.70*(d-4))
        r = barnett_zehnwirth_ptf(_make_cum_ptf(lambda t: 0.0, devfn=dev), ruptures_dev=[4], annee_debut=2010)
        self.assertTrue(r['disponible'])
        det = r['ruptures_dev_testees'][0]
        self.assertTrue(det['significatif'], f"rupture dev manquée p={det['p_value']}")
        print(f"    OK T10 rupture dev d=4 : delta_log={det['delta_log']} (injecté -0.40), p={det['p_value']}")

    def test_genins_pas_de_fausse_rupture(self):
        """Contrôle données réelles (PAS une référence de réserve) : pas de fausse rupture."""
        r = barnett_zehnwirth_ptf(GENINS, ruptures_calendaires=[1993], annee_debut=1988)
        self.assertTrue(r['disponible'])
        self.assertFalse(r['calendaire_significatif'])
        print(f"    OK T10 GenIns : VERT (p={r['p_bloc_calendaire']})")

    def test_raa_negatif_exclu_pas_de_crash(self):
        """RAA (a des incréments négatifs) : négatif exclu + flag, pas de crash, calme."""
        r = barnett_zehnwirth_ptf(RAA, ruptures_calendaires=[1986], annee_debut=1981)
        self.assertTrue(r['disponible'])
        self.assertGreaterEqual(r['n_exclues'], 1)
        self.assertFalse(r['calendaire_significatif'])
        print(f"    OK T10 RAA : {r['n_exclues']} négatif exclu, VERT (pas de crash)")

    def test_trop_de_negatifs_non_fiable(self):
        """> 10 % d'incréments ≤ 0 → disponible=False (log-normal inadapté)."""
        Cbad = GENINS.copy().astype(float)
        for i in range(6):
            Cbad[i, 2] = Cbad[i, 1] - 1.0
        r = barnett_zehnwirth_ptf(Cbad, annee_debut=1988)
        self.assertFalse(r['disponible'])
        print(f"    OK T10 négatifs>10% : disponible=False ({r['n_exclues']}/{r['n_obs']})")


# =============================================================================
#  BE — Mack retiré du point estimate (double-comptage CL) — Lot A
# =============================================================================

def _make_mack_recommande(seed=2, noise=0.01):
    """Triangle propre (H1/H2 forts) où Mack est RECOMMANDÉ par N2 (score ≥ 70).
    Sert à vérifier le remap : le point CL garde le forçage 50 %, Mack non pondéré."""
    np.random.seed(seed)
    n = 10
    expo = np.linspace(1000, 2000, n)
    patt = np.array([0.30, 0.22, 0.16, 0.11, 0.08, 0.05, 0.035, 0.02, 0.015, 0.01])
    C = np.zeros((n, n))
    for i in range(n):
        C[i, :n-i] = np.cumsum([expo[i]*patt[j]*(1 + np.random.normal(0, noise)) for j in range(n-i)])
    return C


class T11_BE_Mack_Retire(unittest.TestCase):
    """Mack retiré de la pondération du BE (son point = celui du CL, double-comptage).
    Traitement 'remap' : quand Mack est recommandé, le point CL est pondéré (forçage
    50 %) ; 'mack' n'apparaît plus comme méthode pondérée séparée."""

    @classmethod
    def setUpClass(cls):
        cls.r = AgentA7Provisionnement(verbose=False).run(
            source=_make_mack_recommande(), lob='generique', n_sim_bootstrap=100,
            generer_word=False, generer_pdf_flag=False, generer_graphiques=False)

    def test_mack_non_pondere_dans_le_be(self):
        """Mack n'entre JAMAIS dans la pondération du Best Estimate.

        Son estimation centrale est celle de Chain Ladder (Mack = CL + σ, il
        consomme les mêmes facteurs) : l'inclure comme méthode pondérée
        double-compterait le Chain Ladder. C'est la protection posée au commit
        6e2e66e, et elle reste entière.

        DEUX ASSERTIONS RETIRÉES AU LOT B, parce que ce qu'elles vérifiaient a
        été supprimé, pas parce qu'elles échouaient :
        · la précondition `methode_recommandee ∈ ('mack','mack_1993')` — la
          recommandation ne renvoie plus « mack », justement parce que son point
          estimate EST celui de Chain Ladder ;
        · le poids de 0,50 sur Chain Ladder — il venait du plancher
          `POIDS_MIN_REC` accordé à la méthode recommandée, mécanisme remplacé
          par des poids égaux entre méthodes admises.
        """
        r = self.r
        self.assertTrue(r.get('success'), r.get('erreur'))
        poids = r['n4'].get('poids', {})
        for interdit in ('mack', 'mack_1993'):
            self.assertNotIn(interdit, poids,
                             f"Mack ne doit jamais être pondéré (poids={poids})")
        self.assertIn('chain_ladder', poids,
                      f"le point de Mack passe par Chain Ladder (poids={poids})")
        print(f"    OK T11 : Mack non pondéré, son point porté par CL (poids={poids})")


# =============================================================================
#  NÉGATIFS — outils partagés signaler_negatifs / increments_positifs (Lot 1)
# =============================================================================

# Triangle synthétique 4×4 à négatifs CONNUS (oracles calculés à la main) :
#   · cumulé négatif   : (2,1) = -20
#   · inversions (>5%) : (0,2) 150→140, (1,1) 100→90, (2,1) 100→-20
#   · incréments ≤ 0   : (0,2)=-10, (1,1)=-10, (2,1)=-120  → 3/10 = 30 %
_TRI_NEG = np.array([[100., 150., 140., 200.],
                     [100.,  90., 120.,   0.],
                     [100., -20.,   0.,   0.],
                     [ 50.,   0.,   0.,   0.]])


def _increments_long(res, C):
    """Incréments du helper en zone connue (i+j<n), ordre i-externe/j-interne
    — même parcours que _to_long / _to_long_log, pour comparer terme à terme."""
    n, m = C.shape
    Y, masque = res['Y'], res['masque']
    return [(float(Y[i, j]), bool(masque[i, j]))
            for i in range(n) for j in range(m) if i + j < n]


class T12_Negatifs_Helpers(unittest.TestCase):
    """Lot 1 — outils partagés de gestion des négatifs. signaler_negatifs détecte
    sans transformer ; increments_positifs reproduit EXACTEMENT B&Z (plancher=None)
    et GLM APC (plancher=FLOOR_Y). Aucune méthode N3 n'est encore branchée dessus."""

    # ── signaler_negatifs ─────────────────────────────────────────────────────
    def test_signaler_synthetique(self):
        r = signaler_negatifs(_TRI_NEG)
        self.assertEqual(r['n_neg'], 1)
        self.assertEqual(r['cellules_neg'], [(2, 1)])
        self.assertAlmostEqual(r['frac_neg'], 0.10, places=6)          # 1 / 10 cellules connues
        self.assertEqual(r['n_inversions'], 3)
        self.assertEqual(r['cellules_inversions'], [(0, 2), (1, 1), (2, 1)])
        self.assertAlmostEqual(r['frac_inversions'], 0.50, places=6)   # 3 / 6 transitions
        print("    OK T12a signaler_negatifs : 1 négatif + 3 inversions détectés")

    def test_signaler_raa_genins_cumule_propre(self):
        # RAA a un incrément négatif (15599→15496) mais AUCUN cumulé négatif, et sa
        # baisse (0,66 %) est sous la tolérance 5 % → rien à signaler ICI. C'est
        # increments_positifs (niveau incrément) qui l'attrape, pas signaler_negatifs.
        for nom, C in (("RAA", RAA), ("GENINS", GENINS)):
            r = signaler_negatifs(C)
            self.assertEqual(r['n_neg'], 0, nom)
            self.assertEqual(r['n_inversions'], 0, nom)
        print("    OK T12b signaler_negatifs : RAA/GenIns cumulé propre (0 négatif, 0 inversion)")

    def test_signaler_ne_modifie_pas_C(self):
        C = _TRI_NEG.copy()
        avant = C.copy()
        signaler_negatifs(C)
        self.assertTrue(np.array_equal(C, avant), "signaler_negatifs a modifié C")
        print("    OK T12c signaler_negatifs : C strictement inchangé")

    # ── increments_positifs : reproduction EXACTE de B&Z et GLM APC ───────────
    def test_increments_none_reproduit_bz(self):
        for nom, C in (("SYNTH", _TRI_NEG), ("RAA", RAA), ("GENINS", GENINS)):
            bz = _bz_to_long_log(C)
            ip = increments_positifs(C, plancher=None)
            self.assertEqual(ip['cellules_exclues'], bz['cellules_exclues'], nom)
            self.assertEqual(ip['n_exclues'], bz['n_exclues'], nom)
            self.assertEqual(ip['n_obs'], bz['n_obs'], nom)
            log_util = [float(np.log(y)) for y, mk in _increments_long(ip, C) if mk]
            self.assertEqual(len(log_util), len(bz['y']), nom)
            self.assertTrue(np.allclose(log_util, bz['y']), nom)
        print("    OK T12d increments_positifs(None) == B&Z _to_long_log (exact)")

    def test_increments_plancher_reproduit_glm(self):
        for nom, C in (("SYNTH", _TRI_NEG), ("RAA", RAA), ("GENINS", GENINS)):
            glm = _glm_to_long(C)
            ip = increments_positifs(C, plancher=_GLM_FLOOR_Y)
            Y_util = [y for y, _ in _increments_long(ip, C)]
            self.assertEqual(len(Y_util), len(glm['Y']), nom)
            self.assertTrue(np.allclose(Y_util, glm['Y']), nom)
        print(f"    OK T12e increments_positifs(FLOOR_Y={_GLM_FLOOR_Y}) == GLM APC _to_long (exact)")

    def test_increments_raa_un_negatif(self):
        ip = increments_positifs(RAA, plancher=None)
        self.assertEqual(ip['n_exclues'], 1)
        self.assertEqual(ip['cellules_exclues'], [(1, 6)])
        print("    OK T12f increments_positifs : RAA = 1 incrément négatif exclu (1,6)")

    def test_increments_gate_disponible(self):
        self.assertFalse(increments_positifs(_TRI_NEG, plancher=None)['disponible'])  # 30 % > 10 %
        self.assertTrue(increments_positifs(RAA, plancher=None)['disponible'])        # 1,8 %
        self.assertTrue(increments_positifs(GENINS, plancher=None)['disponible'])     # 0 %
        print("    OK T12g increments_positifs : gate disponible (30% KO, RAA/GenIns OK)")


# =============================================================================
#  CHAIN LADDER — facteur < 1.0 (recours) conservé et signalé (Lot 2)
# =============================================================================

# Triangle 6×6 avec un RECOURS en développement 2→3 (Σ colonne 3 < Σ colonne 2)
# → facteur de colonne j=2 < 1.0. Les autres colonnes restent > 1.0.
_TRI_RECOURS = np.array([[1000., 1500., 1800., 1700., 1750., 1780.],
                         [1100., 1600., 1900., 1750., 1800.,    0.],
                         [1050., 1550., 1850., 1720.,    0.,    0.],
                         [1200., 1650., 1950.,    0.,    0.,    0.],
                         [1150., 1580.,    0.,    0.,    0.,    0.],
                         [1080.,    0.,    0.,    0.,    0.,    0.]])


class T13_CL_Recours_Facteur_Sous_1(unittest.TestCase):
    """Lot 2 — le plancher facteur<1.0→1.0 est retiré : un recours/subrogation qui
    fait descendre un facteur de colonne sous 1.0 est CONSERVÉ et SIGNALÉ, jamais
    écrasé. Les oracles CL/Mack (facteurs tous >1) restent intacts (T1/T3/T4)."""

    def test_facteur_recours_conserve_et_signale(self):
        r = chain_ladder(_TRI_RECOURS)
        fac = r['facteurs']
        # colonne j=2 : recours → facteur < 1.0, CONSERVÉ (plus forcé à 1.0)
        self.assertLess(fac[2], 1.0, f"facteur col.2 doit être < 1.0 (facteurs={fac})")
        # signalé dans le champ structuré
        fs1 = r['facteurs_sous_1']
        self.assertEqual(len(fs1), 1, f"exactement 1 facteur < 1.0 attendu (fs1={fs1})")
        self.assertEqual(fs1[0][0], 2, "la colonne signalée doit être j=2")
        self.assertLess(fs1[0][1], 1.0)
        self.assertAlmostEqual(fs1[0][1], fac[2], places=6, msg="valeur signalée == facteur conservé")
        # signalé dans le message lisible
        self.assertIn('facteur(s) < 1.0', r['message'])
        print(f"    OK T13a CL recours : facteur col.2 = {fac[2]:.4f} conservé + signalé {fs1}")

    def test_pas_de_faux_signalement_sur_oracles(self):
        # RAA et GenIns n'ont AUCUN facteur de colonne < 1.0 → champ vide, réserve intacte
        self.assertEqual(chain_ladder(RAA, tail_force=1.0)['facteurs_sous_1'], [])
        rg = chain_ladder(GENINS)
        self.assertEqual(rg['facteurs_sous_1'], [])
        self.assertAlmostEqual(rg['reserve_totale'], 18680856, delta=1)  # T1 inchangé
        print("    OK T13b CL : RAA/GenIns aucun facteur < 1.0 (pas de faux signalement, réserve intacte)")


# =============================================================================
#  MUNICH CL — contrôle de cohérence C_engagé ≥ C_payé (Lot 3)
# =============================================================================

# Payé cumulé 4×4 (zone connue i+j ≤ 3).
_MCL_PAYE = np.array([[100., 180., 230., 260.],
                      [120., 200., 250.,   0.],
                      [110., 190.,   0.,   0.],
                      [130.,   0.,   0.,   0.]])
# Engagé SAIN : ≥ payé partout, ratios variés (passe aussi le test de circularité).
_MCL_ENG_SAIN = np.array([[160., 220., 250., 265.],
                          [200., 250., 275.,   0.],
                          [175., 235.,   0.,   0.],
                          [210.,   0.,   0.,   0.]])


class T14_Munich_Coherence_Negatifs(unittest.TestCase):
    """Lot 3 — le contrôle C_engagé ≥ C_payé ne saute plus les cellules où l'une
    des valeurs est ≤ 0 : un engagé négatif (payé positif) est désormais DÉTECTÉ
    comme violation au lieu d'échapper au test (angle mort corrigé)."""

    def test_engage_sain_pas_de_violation(self):
        ok, msg = valider_prerequis(_MCL_PAYE, _MCL_ENG_SAIN)
        self.assertTrue(ok, msg)
        print("    OK T14a Munich sain : prérequis satisfaits (aucune violation)")

    def test_engage_negatif_detecte(self):
        # 2 cellules engagé < 0 avec payé > 0 → 25 % du triangle → désactivé.
        # (Avec l'ancien garde > 0, ces cellules étaient ignorées → 0 violation.)
        eng = _MCL_ENG_SAIN.copy(); eng[1, 1] = -30.; eng[2, 0] = -20.
        ok, msg = valider_prerequis(_MCL_PAYE, eng)
        self.assertFalse(ok, "un engagé négatif (payé positif) doit être détecté")
        self.assertIn('incohérent', msg)
        print("    OK T14b Munich engagé négatif : violation détectée → désactivé")

    def test_cellule_vide_pas_de_faux_positif(self):
        # Cellule (2,1) payé = 0 ET engagé = 0 (non remplie) → aucune violation.
        pay = _MCL_PAYE.copy();     pay[2, 1] = 0.
        eng = _MCL_ENG_SAIN.copy(); eng[2, 1] = 0.
        ok, _ = valider_prerequis(pay, eng)
        self.assertTrue(ok, "une cellule vide (0,0) ne doit pas déclencher de faux positif")
        print("    OK T14c Munich cellule vide : pas de faux positif")

    def test_munich_cl_end_to_end(self):
        # Le fix se propage au consommateur réel munich_cl().
        self.assertTrue(munich_cl(_MCL_PAYE, _MCL_ENG_SAIN).get('disponible'))
        eng = _MCL_ENG_SAIN.copy(); eng[1, 1] = -30.; eng[2, 0] = -20.
        self.assertFalse(munich_cl(_MCL_PAYE, eng).get('disponible'))
        print("    OK T14d Munich end-to-end : sain disponible, engagé négatif désactivé")


# =============================================================================
#  IBNR-A — Helper de projection partagé + garde-fou BE négatif (fondations)
# =============================================================================

# Triangle 3×3 + facteurs avec RECOURS en dev 1→2 (f[1]=0.9 < 1). Oracles calculés
# à la main : année 1 → IBNR brut = 210×0.9 − 210 = −21 (reprise) ; année 2 →
# 120×1.8×0.9 − 120 = +74.4.
_TRI_PROJ = np.array([[100., 200., 180.],
                      [110., 210.,   0.],
                      [120.,   0.,   0.]])
_FAC_PROJ = np.array([1.8, 0.9])


class T15_Projection_Helper(unittest.TestCase):
    """Fondation 1 — projeter_ultimates expose l'IBNR brut (reprises < 0) ET
    plancheré (max(·,0)), sans décider lequel utiliser. Non branché ici."""

    def test_brut_vs_plancher_et_agregats(self):
        p = projeter_ultimates(_TRI_PROJ, _FAC_PROJ, tail_factor=1.0, annee_base=1)
        self.assertAlmostEqual(p['ibnr_brut'][1], -21.0, places=6)      # reprise conservée dans le brut
        self.assertAlmostEqual(p['ibnr_plancher'][1], 0.0, places=6)    # reprise écrasée dans le plancher
        self.assertAlmostEqual(p['ibnr_brut'][2], 74.4, places=6)
        self.assertTrue(np.allclose(p['ibnr_plancher'], np.maximum(p['ibnr_brut'], 0.0)))
        self.assertAlmostEqual(p['reserve_brute'], 53.4, places=6)      # -21 + 74.4
        self.assertAlmostEqual(p['reserve_plancher'], 74.4, places=6)   # 0 + 74.4
        self.assertEqual(p['n_annees_reprise'], 1)
        print("    OK T15a projeter_ultimates : brut (reprise -21) vs plancher (0), agrégats OK")

    def test_tail_factor_applique(self):
        p0 = projeter_ultimates(_TRI_PROJ, _FAC_PROJ, tail_factor=1.0)
        p1 = projeter_ultimates(_TRI_PROJ, _FAC_PROJ, tail_factor=1.10)
        self.assertAlmostEqual(p1['ultimate'][2], p0['ultimate'][2] * 1.10, places=6)
        print("    OK T15b projeter_ultimates : tail_factor appliqué")


class T16_GardeFou_BE_Negatif(unittest.TestCase):
    """Fondation 2 — garde-fou TOTAL : un BE final ≤ 0 rend les agrégats S2 non
    calculables (SCR/RM/PT/percentiles absurdes), signalé ROUGE, jamais plancheré
    en silence. Testé isolément (dormant en production tant que BE > 0)."""

    def test_be_positif_pas_de_garde(self):
        self.assertIsNone(garde_fou_be_negatif(1500.0))
        self.assertIsNone(garde_fou_be_negatif(0.01))
        print("    OK T16a garde_fou_be_negatif : BE > 0 → None (calcul normal)")

    def test_be_negatif_ou_nul_declenche_rouge(self):
        for be in (-100.0, 0.0):
            g = garde_fou_be_negatif(be)
            self.assertIsNotNone(g, f"BE={be} doit déclencher le garde-fou")
            self.assertEqual(g['statut'], 'ROUGE')
            self.assertTrue(g['be_negatif'])
            self.assertIn('non calculables', g['message'])
            for k in ('scr_provisions', 'ratio_scr_be', 'reserve_p75', 'reserve_p90',
                      'reserve_p99_5', 'risk_margin', 'ratio_rm_be', 'provisions_techniques_s2'):
                self.assertIsNone(g[k], f"{k} doit être None (non calculable)")
        print("    OK T16b garde_fou_be_negatif : BE ≤ 0 → ROUGE + agrégats S2 = None")


# =============================================================================
#  IBNR-B — Chain Ladder bascule sur le brut + garde-fou N4 chemin primaire
# =============================================================================

# Triangle 6×6 à reprise (3 facteurs de dév < 1) : réserve encore positive mais
# 3 années en reprise. Oracles calculés par le code (impact analysis).
_TRI_RECOURS_FORT = np.array([[1000., 2000., 2500., 2400., 2350., 2300.],
                              [1100., 2100., 2600., 2450., 2380.,    0.],
                              [1050., 2050., 2550., 2420.,    0.,    0.],
                              [1200., 2200., 2650.,    0.,    0.,    0.],
                              [1150., 2150.,    0.,    0.,    0.,    0.],
                              [1080.,    0.,    0.,    0.,    0.,    0.]])
# Triangle TOUT décroissant → réserve CL brute NÉGATIVE (releases dominants).
_TRI_TOUT_DECROISSANT = np.array([[1000., 900., 850., 820., 810., 805.],
                                  [1100., 990., 940., 910., 895.,   0.],
                                  [1050., 945., 895., 870.,   0.,   0.],
                                  [1200.,1080.,1030.,   0.,   0.,   0.],
                                  [1150.,1035.,   0.,   0.,   0.,   0.],
                                  [1080.,   0.,   0.,   0.,   0.,   0.]])


class T17_N4_GardeFou_CheminPrimaire(unittest.TestCase):
    """Lot IBNR-B Partie 1 — garde-fou BE négatif câblé sur le SCR PRIMAIRE de N4
    (calculer(), chemin SANS grands sinistres) : un BE pondéré < 0 déclenche ROUGE
    + agrégats S2 = None, sans passer par le bloc LLT d'agent.py."""

    def _n2_n3(self):
        r = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, generer_word=False, generer_pdf_flag=False, generer_graphiques=False)
        return r['n2'], r['n3'], np.array(r['triangle'])

    def test_be_negatif_chemin_primaire_declenche_garde_fou(self):
        n2, n3, C = self._n2_n3()
        # CL fortement négatif (reprise nette), BF/CC = 0 (exclus car r==0) → CL seule
        # incluse → be = réserve CL < 0.
        #
        # LEVIER MIS À JOUR — lot B : N4 agrège désormais ANNÉE PAR ANNÉE, donc
        # il lit `ibnr_par_annee` et non plus `reserve_totale`. Forcer le seul
        # total ne commande plus rien. On force les deux, cohérents entre eux —
        # c'est précisément l'invariant que T24 verrouille désormais.
        _forcer_reserve(n3['chain_ladder'], -5_000_000.0)
        _forcer_reserve(n3['bf'],                    0.0)
        _forcer_reserve(n3['cape_cod'],              0.0)
        n4 = BestEstimateS2().calculer(n2, n3, C)
        self.assertLess(n4['best_estimate'], 0)
        self.assertTrue(n4.get('be_negatif'))
        self.assertEqual(n4['statut'], 'ROUGE')
        for k, v in (('scr_provisions', n4['scr']['scr_provisions']), ('scr_prov', n4['scr_prov']),
                     ('risk_margin', n4['risk_margin']), ('pt_s2', n4['provisions_techniques_s2']),
                     ('reserve_p75', n4['reserve_p75']), ('reserve_p90', n4['reserve_p90'])):
            self.assertIsNone(v, f"{k} doit être None (non calculable)")
        self.assertIn('non calculables', n4['message'])
        print("    OK T17a N4 chemin primaire : BE négatif → ROUGE + agrégats S2 None")

    def test_filtre_inclut_reserve_negative_exclut_zero(self):
        n2, n3, C = self._n2_n3()
        n3['chain_ladder']['reserve_totale'] = -1_000_000.0   # reprise
        n3['bf']['reserve_totale']       = 0.0                 # échec (r==0)
        n3['cape_cod']['reserve_totale'] = 0.0
        n4 = BestEstimateS2().calculer(n2, n3, C)
        self.assertIn('chain_ladder', n4['methodes_incluses'])            # r<0 inclus
        self.assertNotIn('bornhuetter_ferguson', n4['methodes_incluses']) # r==0 exclu
        print("    OK T17b filtre N4 : réserve négative incluse, r==0 exclu")


class T18_CL_Bascule_Brut(unittest.TestCase):
    """Lot IBNR-B Partie 2 — Chain Ladder bascule sur l'IBNR BRUT : la réserve
    reflète les reprises (recours), avec signalement honnête. Mack hérite du brut."""

    def test_recours_reserve_brute_et_signalement(self):
        r = chain_ladder(_TRI_RECOURS_FORT, tail_force=1.0)
        self.assertEqual(r['reserve_totale'], r['reserve_brute'])
        self.assertLess(r['reserve_brute'], r['reserve_plancher'])       # honnête < plancher
        self.assertEqual(r['n_annees_reprise'], 3)
        self.assertTrue(any(v < 0 for v in r['ibnr_par_annee']))         # reprises conservées
        self.assertIn('reprise', r['message'])
        self.assertAlmostEqual(r['reserve_plancher'] - r['reserve_brute'], 406.93, places=1)
        print(f"    OK T18a CL recours : brut={r['reserve_brute']:.0f} < plancher={r['reserve_plancher']:.0f} ({r['n_annees_reprise']} reprises)")

    def test_tout_decroissant_reserve_negative(self):
        r = chain_ladder(_TRI_TOUT_DECROISSANT, tail_force=1.0)
        self.assertLess(r['reserve_totale'], 0)                          # honnête, peut être < 0
        self.assertEqual(r['reserve_totale'], r['reserve_brute'])
        print(f"    OK T18b CL tout décroissant : réserve brute = {r['reserve_brute']:.0f} < 0 (honnête)")

    def test_mack_herite_du_brut(self):
        rc = chain_ladder(_TRI_RECOURS_FORT, tail_force=1.0)
        mk = mack_1993(_TRI_RECOURS_FORT, facteurs=rc['facteurs'], facteurs_indiv=rc['facteurs_indiv'],
                       ultimates_cl=np.array(rc['ultimates']), ibnr_cl=np.array(rc['ibnr_par_annee']),
                       annee_base=1)
        self.assertAlmostEqual(mk['reserve_best_estimate'], rc['reserve_brute'], places=1)
        self.assertGreater(mk['sigma_total'], 0)                         # σ (variance) intact
        print(f"    OK T18c Mack hérite du brut : réserve Mack = {mk['reserve_best_estimate']:.0f} = CL brut, σ intact")

    def test_sans_reprise_brut_egale_plancher(self):
        r = chain_ladder(GENINS)
        self.assertEqual(r['n_annees_reprise'], 0)
        self.assertAlmostEqual(r['reserve_brute'], r['reserve_plancher'], places=2)
        self.assertAlmostEqual(r['reserve_totale'], 18_680_856, delta=1)  # T1 intact
        print("    OK T18d CL sans reprise : brut == plancher, réserve GenIns intacte")


class T19_BE_Negatif_Livrables_Et_RM(unittest.TestCase):
    """Lot IBNR-B (correctif) — un BE négatif traverse TOUT le pipeline jusqu'au
    rapport sans crash, en affichant 'non calculable' ; et en cas de RÉCUPÉRATION
    (attritionnel < 0 mais BE final > 0 après grands sinistres) la Risk Margin est
    RECALCULÉE à neuf sur le BE final — un vrai chiffre, jamais 0 par défaut."""

    def _run(self, **kw):
        return AgentA7Provisionnement(verbose=False).run(
            generer_word=False, generer_pdf_flag=False, generer_graphiques=False, **kw)

    def test_be_negatif_rapport_complet_sans_crash(self):
        # mode_declare='cumule' : le triangle décroissant est pris tel quel (sinon N1
        # le détecte comme incrémental et le cumule) → BE pondéré négatif.
        r = self._run(source=_TRI_TOUT_DECROISSANT, mode_declare='cumule')
        self.assertTrue(r['success'], r.get('erreur'))
        n4 = r['n4']
        self.assertLess(n4['best_estimate'], 0)
        self.assertTrue(n4.get('be_negatif'))
        self.assertEqual(n4['statut'], 'ROUGE')
        self.assertIn('NON CALCULABLES', r.get('commentaire') or '')
        print("    OK T19a BE négatif : rapport complet produit, 'non calculable' affiché")

    def test_recuperation_risk_margin_reelle_pas_zero(self):
        r = self._run(source=_TRI_TOUT_DECROISSANT, mode_declare='cumule',
                      reserve_grands_sinistres=5000.0, n_grands_sinistres=3)
        self.assertTrue(r['success'], r.get('erreur'))
        n4 = r['n4']
        self.assertLess(n4['be_attritional'], 0)     # attritionnel négatif
        self.assertGreater(n4['best_estimate'], 0)   # BE final positif (récupération)
        self.assertFalse(n4.get('be_negatif'))       # drapeau levé
        self.assertGreater(n4['risk_margin'], 0)     # RM RÉELLE, pas 0 par défaut
        self.assertGreater(n4['scr']['scr_provisions'], 0)
        self.assertAlmostEqual(n4['provisions_techniques_s2'],
                               n4['best_estimate'] + n4['risk_margin'], delta=1.5)
        print(f"    OK T19b récupération : RM={n4['risk_margin']:.0f} réelle (pas 0), PT = BE + RM")

    def test_llt_normal_rm_inchangee(self):
        # Non-régression : le recalcul à neuf donne EXACTEMENT la même RM que
        # l'ancienne proratisation (la RM est linéaire en SCR, donc en BE).
        #
        # CONSTANTE MISE À JOUR — lot « décalage f_cum » : 2 728 439 → 3 009 051.
        # `calculer_facteurs_cumules` rendait un tableau d'une case trop courte et
        # n'y multipliait jamais le dernier facteur. Le profil d'écoulement de la
        # Risk Margin (pct_res[j] = 1/f_cum[j]) perdait donc une colonne, ce qui
        # raccourcissait la durée d'écoulement et sous-estimait la RM.
        # Décomposition mesurée : +8,29 % (profil corrigé) puis +2,02 % (hausse
        # du BE, la RM étant linéaire en SCR donc en BE).
        # CE QUE CE TEST VÉRIFIE N'A PAS CHANGÉ — la relation recalcul ≡
        # proratisation reste exacte (écart mesuré 0,13 € après correctif) ;
        # seule la valeur épinglée était périmée.
        #
        # CONSTANTE MISE À JOUR À NOUVEAU — lot B : 3 009 051 → 3 012 464. La RM
        # est linéaire en SCR, donc en BE ; le BE GenIns passe de 20 997 282 à
        # 21 023 363 sous l'effet du nouveau mécanisme de sélection (poids égaux
        # +98 841, puis filet sur l'année 9 −770 968). La relation testée est,
        # elle aussi, inchangée.
        r = self._run(source=GENINS, reserve_grands_sinistres=2_000_000.0, n_grands_sinistres=2)
        self.assertTrue(r['success'], r.get('erreur'))
        self.assertAlmostEqual(r['n4']['risk_margin'], 3_012_464, delta=1)
        print("    OK T19c LLT normal : RM = 3 012 464 (recalcul ≡ proratisation)")


# =============================================================================
#  INVARIANT DE COHÉRENCE — total vs décomposition par année
# =============================================================================

class T24_Reserve_Totale_Egale_Somme_Par_Annee(unittest.TestCase):
    """`reserve_totale` doit toujours valoir `Σ ibnr_par_annee[annee_base:]`.

    POURQUOI CE VERROU EXISTE. Depuis le lot B, N4 juge l'ADMISSIBILITÉ d'une
    méthode sur `reserve_totale` (finie, non nulle) mais calcule le MONTANT sur
    `ibnr_par_annee`. Les deux grandeurs sont donc toutes les deux vivantes, pour
    des usages différents. Si elles divergeaient, l'admissibilité serait décidée
    sur un chiffre et le Best Estimate produit sur un autre, sans que rien ne le
    signale.

    Ce n'est pas une crainte théorique : trois tests sont tombés au lot B parce
    qu'ils forçaient `reserve_totale` sans toucher `ibnr_par_annee`, et le
    système a continué sans broncher. Ce test transforme ce piège en garde-fou.
    """

    def test_les_trois_methodes_du_be_reconcilient(self):
        for nom, source in (('GenIns', GENINS), ('RAA', RAA)):
            r = AgentA7Provisionnement(verbose=False).run(
                source=source, n_sim_bootstrap=200, generer_graphiques=False,
                generer_word=False, generer_pdf_flag=False)
            self.assertTrue(r['success'], r.get('erreur'))
            base = int(r['n3']['chain_ladder'].get('annee_base_reserve', 1))
            for cle, libelle in (('chain_ladder', 'Chain Ladder'),
                                 ('bf', 'Bornhuetter-Ferguson'),
                                 ('cape_cod', 'Cape Cod')):
                bloc = r['n3'][cle]
                somme = float(np.sum(bloc['ibnr_par_annee'][base:]))
                self.assertAlmostEqual(
                    somme, float(bloc['reserve_totale']), delta=0.05,
                    msg=(f"{nom} / {libelle} : la décomposition par année "
                         f"({somme:,.2f}) ne réconcilie pas avec le total "
                         f"({bloc['reserve_totale']:,.2f})"))
        print("    OK T24 : reserve_totale == Σ ibnr_par_annee sur CL, BF et "
              "Cape Cod (GenIns et RAA)")


# =============================================================================
#  GRAPHIQUES — réellement produits par run() (bug du paramètre masquant)
# =============================================================================

class T20_Graphiques_Reellement_Produits(unittest.TestCase):
    """Lot graphiques — `run(generer_graphiques=True)` doit produire de VRAIES
    figures, pas seulement « ne pas planter ».

    Le bug : le paramètre `generer_graphiques: bool` de run() masquait la fonction
    importée du même nom → `TypeError: 'bool' object is not callable`, avalé par le
    except → run en succès dégradé avec 0 graphique, indéfiniment. Les tests
    existants passaient tous `generer_graphiques=False` : personne n'exerçait le
    chemin nominal. C'est ce test qui aurait attrapé le bug dès le premier jour.
    """

    @classmethod
    def setUpClass(cls):
        cls.r = AgentA7Provisionnement(verbose=False).run(
            source=GENINS, n_sim_bootstrap=300,
            generer_graphiques=True, generer_word=False, generer_pdf_flag=False)

    def test_graphiques_reellement_produits(self):
        """Le cœur : des figures existent, et ce sont bien des figures Plotly."""
        self.assertTrue(self.r.get('success'), self.r.get('erreur'))
        g = self.r.get('graphiques') or {}
        # 14/14 et non « au moins un » : GenIns alimente les 14 graphiques (aucune
        # garde « pas de données » ne s'y déclenche — vérifié). C'est ce verrou qui
        # empêche un graphique de retomber silencieusement sans test rouge.
        attendus = ['g1_heatmap', 'g2_cadences', 'g3_facteurs_cl', 'g4_ibnr',
                    'g5_convergence', 'g6_bootstrap', 'g7_scr', 'g8_h1', 'g9_h2',
                    'g10_h3', 'g11_ultimates', 'g12_sensibilites', 'g13_paiements',
                    'g14_backtesting']
        self.assertEqual(sorted(g), sorted(attendus),
                         f"manquant(s) : {[k for k in attendus if k not in g]}")
        self.assertTrue(all(hasattr(f, 'to_html') for f in g.values()),
                        "les valeurs doivent être des go.Figure, pas des placeholders")
        print(f"    OK T20a graphiques : {len(g)}/14 réellement produits")

    def test_echec_graphiques_remonte_dans_le_resultat(self):
        """Un échec N5 ne doit plus être un « succès dégradé » invisible."""
        self.assertIsNone(self.r.get('graphiques_erreur'),
                          f"erreur graphiques : {self.r.get('graphiques_erreur')}")
        # Chemin d'échec : le générateur lève → run reste en succès MAIS le
        # résultat porte la trace de l'échec.
        import direction_non_vie.provisionnement.a7_provisionnement.agent as _ag
        _vrai = _ag._generer_graphiques
        try:
            _ag._generer_graphiques = lambda *a, **k: (_ for _ in ()).throw(
                RuntimeError('boom'))
            r = AgentA7Provisionnement(verbose=False).run(
                source=GENINS, n_sim_bootstrap=300,
                generer_graphiques=True, generer_word=False, generer_pdf_flag=False)
        finally:
            _ag._generer_graphiques = _vrai
        self.assertTrue(r['success'])                     # comportement global inchangé
        self.assertEqual(r['graphiques'], {})
        self.assertIn('boom', r['graphiques_erreur'])     # mais l'échec est visible
        print("    OK T20b échec N5 : run en succès, mais graphiques_erreur renseigné")

    def test_g4_ibnr_ne_plante_plus_sur_portefeuille_en_reprise(self):
        """Garde anti-plantage : sur un portefeuille ENTIÈREMENT en reprise, tous
        les IBNR planchés valent 0 → max_v = 0 → division par zéro, et g4_ibnr ne
        se rendait pas. On vérifie seulement qu'il se GÉNÈRE — pas qu'il affiche
        le bon chiffre : il montre encore l'IBNR planché, la refonte est prévue
        au chantier « rapport »."""
        from direction_non_vie.provisionnement.a7_provisionnement.n5_graphiques import (
            g4_ibnr_par_annee)
        cl = chain_ladder(_TRI_TOUT_DECROISSANT, tail_force=1.0)
        # le cas dégénéré est bien exercé : aucun IBNR strictement positif
        self.assertTrue(all(v <= 0 for v in cl['ibnr_par_annee']))
        fig = g4_ibnr_par_annee({'chain_ladder': cl})
        self.assertIsNotNone(fig, "g4_ibnr doit se générer, même planché à zéro")
        self.assertTrue(hasattr(fig, 'to_html'))
        print("    OK T20e g4_ibnr : portefeuille en reprise → figure générée, plus de crash")

    def test_flags_desactivent_toujours(self):
        """Les deux drapeaux (nouveau et alias de compat) coupent bien la génération."""
        for kw in ({'generer_graphiques': False}, {'generer_graphiques_flag': False}):
            r = AgentA7Provisionnement(verbose=False).run(
                source=GENINS, n_sim_bootstrap=300,
                generer_word=False, generer_pdf_flag=False, **kw)
            self.assertEqual(r.get('graphiques'), {}, f"{kw} n'a pas désactivé")
            self.assertIsNone(r.get('graphiques_erreur'), f"{kw} : faux positif d'erreur")
        print("    OK T20c les deux drapeaux désactivent, sans fausse alerte")

    def test_aucun_parametre_ne_masque_une_fonction_du_module(self):
        """Garde-fou GÉNÉRIQUE : aucun paramètre de run() ne doit porter le nom
        d'un callable importé/défini dans agent.py. Attrape toute récidive de
        cette classe de bug, pas seulement l'occurrence corrigée."""
        import inspect
        import direction_non_vie.provisionnement.a7_provisionnement.agent as _ag
        callables_module = {n for n, v in vars(_ag).items()
                            if callable(v) and not n.startswith('__')}
        params = set(inspect.signature(AgentA7Provisionnement.run).parameters)
        collisions = sorted(params & callables_module)
        self.assertEqual(collisions, [],
                         f"paramètre(s) masquant un callable du module : {collisions}")
        # L'API publique reste inchangée : le paramètre historique existe toujours.
        self.assertIn('generer_graphiques', params)
        print("    OK T20d aucun masquage nom-de-paramètre / callable du module")


# =============================================================================
#  MUNICH CL — SOURCE UNIQUE DES FACTEURS (Lot C1)
# =============================================================================

# Paire à RECOURS simple : le payé ET l'engagé décroissent en fin de dév.
_MCL_REC_P = np.array([[100., 180., 230., 205.],
                       [120., 200., 250.,   0.],
                       [110., 190.,   0.,   0.],
                       [130.,   0.,   0.,   0.]])
_MCL_REC_E = np.array([[160., 220., 250., 235.],
                       [200., 250., 275.,   0.],
                       [175., 235.,   0.,   0.],
                       [210.,   0.,   0.,   0.]])

# Paire 7×7 conçue pour exercer la CHAÎNE λ : en colonne 1, une année massivement
# en reprise tire le facteur agrégé sous 1, mais 4 années croissantes survivent au
# filtre des incréments négatifs de _calculer_lambda — donc λ est réellement
# ré-estimé à partir du facteur honnête (et non du facteur écrasé à 1.0).
_MCL_LAM_P = np.array([[6000., 9000., 4000., 4100., 4150., 4200., 4250.],
                       [ 200.,  360.,  470.,  520.,  545.,  560.,    0.],
                       [ 220.,  400.,  530.,  590.,  615.,    0.,    0.],
                       [ 240.,  455.,  600.,  665.,    0.,    0.,    0.],
                       [ 260.,  500.,  660.,    0.,    0.,    0.,    0.],
                       [ 280.,  540.,    0.,    0.,    0.,    0.,    0.],
                       [ 300.,    0.,    0.,    0.,    0.,    0.,    0.]])
_MCL_LAM_E = np.array([[8000.,10500., 5200., 5100., 5050., 5000., 4980.],
                       [ 300.,  470.,  560.,  600.,  615.,  625.,    0.],
                       [ 360.,  540.,  650.,  690.,  705.,    0.,    0.],
                       [ 330.,  580.,  720.,  760.,    0.,    0.,    0.],
                       [ 420.,  660.,  790.,    0.,    0.,    0.,    0.],
                       [ 400.,  700.,    0.,    0.,    0.,    0.,    0.],
                       [ 470.,    0.,    0.,    0.,    0.,    0.,    0.]])


class T21_Munich_Source_Unique_Facteurs(unittest.TestCase):
    """Lot C1 — Munich avait sa PROPRE copie du calcul des facteurs, restée bloquée
    sur le plancher f ≥ 1 retiré de chain_ladder au Lot 2 (mesuré : 0.8913 côté
    partagé contre 1.0000 côté copie). La copie est supprimée : une seule source
    dans A7. Ce lot ne touche NI le plancher f* ≥ 1 (verrou 2) NI le plancher IBNR
    final (verrou 3) — décisions séparées."""

    def test_copie_privee_supprimee(self):
        """Propreté : la copie n'est pas contournée, elle n'existe plus."""
        from direction_non_vie.provisionnement.a7_provisionnement.n3 import munich_cl as _m
        self.assertFalse(hasattr(_m, '_facteurs_cl'),
                         "la copie privée _facteurs_cl doit avoir disparu du module")
        print("    OK T21a source unique : _facteurs_cl supprimée de munich_cl")

    def test_facteurs_exposes_identiques_a_la_source_partagee(self):
        """Sur triangle sain ET à recours, Munich expose exactement les facteurs
        de chain_ladder — plus aucune divergence possible entre les deux."""
        for nom, P, E in (('sain',    _MCL_PAYE,  _MCL_ENG_SAIN),
                          ('recours', _MCL_REC_P, _MCL_REC_E)):
            r = munich_cl(P, E, annee_base=0)
            for lbl, C, cle in (('payé',   P, 'facteurs_cl_paye'),
                                ('engagé', E, 'facteurs_cl_engage')):
                attendu = [round(float(v), 4) for v in calculer_facteurs(C)[0]]
                self.assertEqual(r[cle], attendu, f"{nom}/{lbl} : facteurs divergents")
        print("    OK T21b facteurs Munich == chain_ladder.calculer_facteurs (sain + recours)")

    def test_facteur_sous_1_desormais_conserve(self):
        """Le plancher a bien disparu : un facteur de recours n'est plus écrasé."""
        r = munich_cl(_MCL_REC_P, _MCL_REC_E, annee_base=0)
        self.assertAlmostEqual(r['facteurs_cl_paye'][2],   0.8913, places=4)  # était 1.0
        self.assertAlmostEqual(r['facteurs_cl_engage'][2], 0.9400, places=4)  # était 1.0
        print("    OK T21c recours : f_payé=0.8913 et f_engagé=0.9400 conservés (étaient 1.0)")

    def test_chaine_lambda_estimee_depuis_la_source_honnete(self):
        """CHAÎNE COMPLÈTE — les facteurs entrent dans les résidus de λ
        (munich_cl.py, r_P = C[i,j+1]/C[i,j] − f[j]). On vérifie que λ est estimé
        à partir des facteurs HONNÊTES, et que ce choix est bien discriminant :
        les facteurs planchés donnent un λ différent."""
        P, E = _MCL_LAM_P, _MCL_LAM_E
        f_P, f_E = calculer_facteurs(P)[0], calculer_facteurs(E)[0]
        self.assertLess(min(f_P), 1.0, "la fixture doit exercer un facteur < 1")

        lam_honnete = _mcl_lambda(P, E, f_P, f_E)
        lam_planche = _mcl_lambda(P, E, np.maximum(f_P, 1.0), np.maximum(f_E, 1.0))
        # le cas est bien discriminant (sinon le test ne prouverait rien)
        self.assertFalse(np.allclose(lam_honnete[1], lam_planche[1]),
                         "fixture non discriminante : λ identique dans les deux cas")

        r = munich_cl(P, E, annee_base=0)
        for cle, idx in (('lambda_P', 0), ('lambda_E', 1)):
            obtenu = [float(v) for v in r[cle]]
            np.testing.assert_allclose(obtenu, lam_honnete[idx], atol=1e-4,
                                       err_msg=f"{cle} n'est pas estimé depuis la source unique")
        self.assertFalse(np.allclose([float(v) for v in r['lambda_E']],
                                     lam_planche[1], atol=1e-4),
                         "λ_E correspond encore aux facteurs planchés")
        print(f"    OK T21d chaîne λ : λ_E[1]={r['lambda_E'][1]} (honnête) "
              f"≠ {round(float(lam_planche[1][1]), 4)} (planché)")

    def test_triangle_sain_strictement_inchange(self):
        """Non-régression : sans aucun facteur < 1, la chaîne Munich complète est
        identique à l'avant-lot (valeurs relevées avant modification)."""
        r = munich_cl(_MCL_PAYE, _MCL_ENG_SAIN, annee_base=0)
        self.assertEqual(r['facteurs_cl_paye'],     [1.7273, 1.2632, 1.1304])
        self.assertEqual(r['lambda_P'],             [2.0, 0.0, 0.0])
        self.assertEqual(r['facteurs_munich_paye'], [2.1106, 1.2632, 1.1304])
        self.assertAlmostEqual(r['be_munich_paye'], 375.71, places=2)
        self.assertAlmostEqual(r['be_cl_paye'],     304.55, places=2)
        print("    OK T21e triangle sain : chaîne Munich identique bit à bit")

    def test_verrous_2_et_3_retires_chantier_complet(self):
        """État FINAL du chantier Munich (Lot C3) : les trois verrous IBNR sont
        tous levés. Sur le recours, un f* < 1 est conservé (verrou 2, C2) ET l'IBNR
        d'une année en reprise est < 0 (verrou 3, C3) — plus aucun plancher."""
        r = munich_cl(_MCL_REC_P, _MCL_REC_E, annee_base=0)
        self.assertTrue(any(f < 1.0 for f in r['facteurs_munich_paye']),
                        "verrou 2 retiré : un f* < 1 doit être conservé sur le recours")
        self.assertTrue(any(v < 0.0 for v in r['ibnr_munich_paye']),
                        "verrou 3 retiré : l'IBNR d'une année en reprise doit être < 0")
        print("    OK T21f chantier Munich complet : verrous 1+2+3 tous levés (f*<1 et IBNR<0)")


class T22_Munich_Verrou2_Retire(unittest.TestCase):
    """Lot C2 — le forçage f* ≥ 1.0 est retiré : les facteurs Munich ajustés < 1
    (recours/subrogation) sont CONSERVÉS et signalés (facteurs_munich_sous_1_*),
    avec une garde résiduelle uniquement contre le cas dégénéré f* ≤ 0."""

    def test_sain_no_op(self):
        """(a) Portefeuille sain : aucun f* < 1 → retrait du verrou = no-op exact.
        be_munich inchangé, listes de signalement vides."""
        r = munich_cl(_MCL_PAYE, _MCL_ENG_SAIN, annee_base=1)
        self.assertTrue(all(f >= 1.0 for f in r['facteurs_munich_paye']))
        self.assertTrue(all(f >= 1.0 for f in r['facteurs_munich_engage']))
        self.assertEqual(r['facteurs_munich_sous_1_paye'], [])
        self.assertEqual(r['facteurs_munich_sous_1_engage'], [])
        self.assertEqual(r['facteurs_degeneres_paye'], [])
        self.assertEqual(r['facteurs_degeneres_engage'], [])
        self.assertAlmostEqual(r['be_munich_paye'],   375.71, delta=0.01)
        self.assertAlmostEqual(r['be_munich_engage'], 250.13, delta=0.01)
        print("    OK T22a sain : retrait du verrou = no-op (be_munich 375.71/250.13, rien signalé)")

    def test_recours_f_star_sous_1_conserve_et_signale(self):
        """(b) Recours — le vrai sujet de C2 : un f* < 1 (ajusté) est CONSERVÉ et
        SIGNALÉ, jamais forcé à 1.0. La valeur chiffrée de be_munich relève du Lot
        C3 (verrou 3, plancher IBNR) et est vérifiée par T23 — pas ici."""
        r = munich_cl(_MCL_REC_P, _MCL_REC_E, annee_base=1)
        # colonne 2 : f* payé 0.8913 et engagé 0.94 conservés (étaient forcés à 1.0)
        self.assertEqual(r['facteurs_munich_sous_1_paye'],   [[2, 0.891304]])
        self.assertEqual(r['facteurs_munich_sous_1_engage'], [[2, 0.94]])
        self.assertAlmostEqual(r['facteurs_munich_paye'][2],   0.8913, places=4)
        self.assertAlmostEqual(r['facteurs_munich_engage'][2], 0.94,   places=4)
        self.assertIn('f* < 1.0 conservé', r['message'])
        self.assertEqual(r['facteurs_degeneres_paye'], [])   # pas de dégénérescence
        print("    OK T22b recours : f*<1 (ajusté) conservé et signalé (valeur → T23)")

    def test_garde_f_star_negatif_repli_cl(self):
        """(c) Garde résiduelle f* ≤ 0 : jamais atteinte naturellement (min 0.67 sur
        12 000 paires). Exercée ARTIFICIELLEMENT en forçant λ = 50 (monkeypatch)
        pour saturer l'ajustement → f* ≤ 0 → repli sur le facteur CL (toujours > 0)."""
        from direction_non_vie.provisionnement.a7_provisionnement.n3 import munich_cl as _m
        _orig = _m._calculer_lambda

        def _fake_lambda(C_P, C_E, f_P, f_E, lambda_max=2.0):
            n, mm = C_P.shape
            # λ énorme + Q_moy=0 → le code recalcule le vrai Q volumique (l.356-361)
            return np.full(mm - 1, 50.0), np.full(mm - 1, 50.0), np.zeros(mm - 1)

        _m._calculer_lambda = _fake_lambda
        try:
            r = munich_cl(_MCL_REC_P, _MCL_REC_E, annee_base=1)
        finally:
            _m._calculer_lambda = _orig

        # la garde a sauté (f* aurait été ≤ 0 sur la colonne 2)
        self.assertTrue(r['facteurs_degeneres_paye'] or r['facteurs_degeneres_engage'],
                        "la garde f* ≤ 0 aurait dû se déclencher avec λ = 50")
        self.assertTrue(any(v <= 0 for v, in
                            [(x[1],) for x in r['facteurs_degeneres_paye']]))
        # repli propre : aucun f* projeté ≤ 0
        self.assertTrue(all(f > 0 for f in r['facteurs_munich_paye']))
        self.assertTrue(all(f > 0 for f in r['facteurs_munich_engage']))
        # le repli vaut bien le facteur CL non ajusté sur la cellule dégénérée
        j0 = r['facteurs_degeneres_paye'][0][0]
        self.assertAlmostEqual(r['facteurs_munich_paye'][j0],
                               r['facteurs_cl_paye'][j0], places=4)
        print(f"    OK T22c garde f*≤0 : dégénérescence {r['facteurs_degeneres_paye']} "
              f"→ repli CL, tous f* > 0")


class T23_Munich_Verrou3_Retire_IBNR_Brut(unittest.TestCase):
    """Lot C3 — dernier verrou IBNR de Munich levé : la projection utilise l'IBNR
    BRUT. be_munich reflète PLEINEMENT la reprise (recours), avec le signalement
    ibnr_brut_par_annee / n_annees_reprise / reserve_brute / reserve_plancher
    (même schéma que chain_ladder, Lot B). Ferme le chantier Munich CL."""

    def test_sain_no_op(self):
        """(a) Sain : aucune reprise → brut == plancher → be_munich inchangé."""
        r = munich_cl(_MCL_PAYE, _MCL_ENG_SAIN, annee_base=1)
        self.assertEqual(r['n_annees_reprise_paye'], 0)
        self.assertEqual(r['n_annees_reprise_engage'], 0)
        self.assertEqual(r['reserve_brute_paye'], r['reserve_plancher_paye'])
        self.assertTrue(all(v >= 0 for v in r['ibnr_munich_paye']))
        self.assertAlmostEqual(r['be_munich_paye'],   375.71, delta=0.01)
        self.assertAlmostEqual(r['be_munich_engage'], 250.13, delta=0.01)
        print("    OK T23a sain : pas de reprise, brut == plancher, be_munich inchangé")

    def test_recours_be_munich_reflete_pleinement_la_reprise(self):
        """(b) Recours : be_munich PLEIN (verrou 3 retiré). Avant ce lot :
        202.83 / 156.81 (plancher). Après : 175.66 / 140.31 (brut). L'ancien
        plancher reste exposé pour l'écart."""
        r = munich_cl(_MCL_REC_P, _MCL_REC_E, annee_base=1)
        self.assertAlmostEqual(r['be_munich_paye'],   175.66, delta=0.01)
        self.assertAlmostEqual(r['be_munich_engage'], 140.31, delta=0.01)
        # headline == réserve brute
        self.assertAlmostEqual(r['be_munich_paye'],   r['reserve_brute_paye'],   places=2)
        self.assertAlmostEqual(r['be_munich_engage'], r['reserve_brute_engage'], places=2)
        # l'ancien plancher (== be_munich d'avant C3) est exposé et strictement > brut
        self.assertAlmostEqual(r['reserve_plancher_paye'],   202.83, delta=0.01)
        self.assertAlmostEqual(r['reserve_plancher_engage'], 156.81, delta=0.01)
        self.assertGreater(r['reserve_plancher_paye'], r['reserve_brute_paye'])
        print(f"    OK T23b recours : be_munich_paye {r['be_munich_paye']} plein "
              f"(plancher {r['reserve_plancher_paye']}), be_munich_engage {r['be_munich_engage']}")

    def test_recours_signalement_ibnr_brut(self):
        """(c) Recours : 1 année en reprise par triangle, IBNR brut < 0 exposé et
        cohérent avec ibnr_munich_*, alerte de reprise dans le message."""
        r = munich_cl(_MCL_REC_P, _MCL_REC_E, annee_base=1)
        self.assertEqual(r['n_annees_reprise_paye'], 1)
        self.assertEqual(r['n_annees_reprise_engage'], 1)
        # ibnr_brut_par_annee_* == ibnr_munich_* (source unique, tous deux bruts)
        self.assertEqual(r['ibnr_brut_par_annee_paye'],   r['ibnr_munich_paye'])
        self.assertEqual(r['ibnr_brut_par_annee_engage'], r['ibnr_munich_engage'])
        self.assertTrue(any(v < 0 for v in r['ibnr_brut_par_annee_paye']),
                        "l'année en reprise doit avoir un IBNR brut < 0")
        self.assertIn('en reprise', r['message'])
        print("    OK T23c recours : 1 reprise/triangle, IBNR brut<0 exposé + alerte reprise")


class T24_Bootstrap_Recentrage_Brut(unittest.TestCase):
    """Lot D — Bootstrap ODP. D1 : le recentrage England-Verrall vise désormais la
    réserve CL BRUTE (chiffre honnête post-Lot B) et non l'ancien plancher. D2 : les
    deux mécanismes morts (f* ≥ 1, IBNR ≥ 0/sim) sont retirés — no-op numérique
    prouvé. Les gardes d'incrément (contrainte ODP) restent, intactes."""

    def test_d1_recentrage_sur_le_brut_recours(self):
        """D1 : sur RECOURS_FORT, be_bootstrap reflète le brut (~1076) et non
        l'ancien plancher (~1483). Recentrage exact : be == réserve CL brute."""
        f  = calculer_facteurs(_TRI_RECOURS_FORT, 'standard')[0]
        rc = chain_ladder(_TRI_RECOURS_FORT, tail_force=1.0)
        bo = bootstrap_odp(_TRI_RECOURS_FORT, f, n_sim=3000, seed=42)
        self.assertAlmostEqual(bo['be_bootstrap'], rc['reserve_brute'], delta=0.01)  # recentrage exact
        self.assertAlmostEqual(bo['be_bootstrap'], 1075.80, delta=0.5)                # brut
        self.assertGreater(rc['reserve_plancher'] - bo['be_bootstrap'], 400)          # ~407 sous le plancher
        print(f"    OK T24a D1 recentrage brut : be_bootstrap={bo['be_bootstrap']:.0f} "
              f"(= CL brut {rc['reserve_brute']:.0f}, ancien plancher {rc['reserve_plancher']:.0f})")

    def test_d1_recentrage_est_un_decalage_std_invariant(self):
        """Le recentrage est un décalage pur : changer la cible (brut vs plancher)
        déplace be_bootstrap d'exactement l'écart, σ STRICTEMENT invariant."""
        import direction_non_vie.provisionnement.a7_provisionnement.n3.bootstrap_odp as _bo
        f = calculer_facteurs(_TRI_RECOURS_FORT, 'standard')[0]
        _orig = _bo._reserve_cl_simple
        try:
            _bo._reserve_cl_simple = lambda C, fa, ab=1: 1076.0
            r_brut = bootstrap_odp(_TRI_RECOURS_FORT, f, n_sim=3000, seed=42)
            _bo._reserve_cl_simple = lambda C, fa, ab=1: 1483.0
            r_plan = bootstrap_odp(_TRI_RECOURS_FORT, f, n_sim=3000, seed=42)
        finally:
            _bo._reserve_cl_simple = _orig
        self.assertAlmostEqual(r_brut['be_bootstrap'], 1076.0, delta=0.01)
        self.assertAlmostEqual(r_plan['be_bootstrap'], 1483.0, delta=0.01)
        self.assertEqual(r_brut['std_bootstrap'], r_plan['std_bootstrap'])   # σ invariant au décalage
        print(f"    OK T24b décalage pur : be 1076 vs 1483, σ identique = {r_brut['std_bootstrap']:.2f}")

    def test_d2_retrait_morts_no_op_bit_exact(self):
        """D2 : le retrait des deux mécanismes morts ne change RIEN. Sur GENINS
        (sain, D1 aussi no-op car brut == plancher), la distribution entière est
        identique aux valeurs d'avant le lot (be ET σ, seed/n_sim figés)."""
        f  = calculer_facteurs(GENINS, 'standard')[0]
        bo = bootstrap_odp(GENINS, f, n_sim=3000, seed=42)
        self.assertAlmostEqual(bo['be_bootstrap'],  18_680_855.61, delta=0.5)
        self.assertAlmostEqual(bo['std_bootstrap'],  3_061_803.46, delta=1.0)
        self.assertAlmostEqual(bo['p99_5'],         27_173_015.67, delta=1.0)
        print("    OK T24c D2 no-op : GENINS be/σ/P99.5 identiques à l'avant-lot")


class T25_Clark_IBNR_Brut_Expose(unittest.TestCase):
    """Lot E — Clark expose le signal honnête (ibnr_brut_par_annee,
    n_sur_developpement) jusque-là CALCULÉ mais jamais transmis (docstring
    mensongère), et la réserve bascule sur le brut. DERNIER lot du chantier IBNR."""

    def test_signal_brut_present_et_coherent(self):
        """(a) Les deux clés promises par la docstring sont désormais réellement
        présentes et cohérentes. GENINS et recours : Clark lisse tout (courbe
        monotone), aucun sur-développement → brut == planché année par année."""
        for nom, C in [('GENINS', GENINS), ('RECOURS_FORT', _TRI_RECOURS_FORT)]:
            r = clark_ldf(C, annee_base=1)
            self.assertIn('ibnr_brut_par_annee', r, f"{nom} : clé absente")
            self.assertIn('n_sur_developpement', r, f"{nom} : clé absente")
            self.assertEqual(len(r['ibnr_brut_par_annee']), len(r['ibnr_par_annee']))
            self.assertEqual(r['n_sur_developpement'], 0)
            self.assertEqual(r['ibnr_brut_par_annee'], r['ibnr_par_annee'])  # pas de sur-dev
        print("    OK T25a signal brut exposé et cohérent (GENINS, recours : n_sur_dev=0)")

    def test_sur_developpement_expose_le_negatif(self):
        """(b) RAA année 0 sur-développe (ultime MLE < cumul observé) : le brut
        expose la valeur négative (~ -92) alors que le champ planché reste 0, et
        n_sur_developpement compte l'année."""
        r = clark_ldf(RAA, annee_base=1)
        self.assertEqual(r['ibnr_par_annee'][0], 0.0)                 # planché à 0
        self.assertLess(r['ibnr_brut_par_annee'][0], 0)               # brut < 0 (robuste)
        self.assertAlmostEqual(r['ibnr_brut_par_annee'][0], -92.0, delta=5.0)  # valeur mesurée
        self.assertGreaterEqual(r['n_sur_developpement'], 1)
        print(f"    OK T25b sur-développement : RAA an.0 brut={r['ibnr_brut_par_annee'][0]:.0f} "
              f"(planché {r['ibnr_par_annee'][0]:.0f}), n_sur_dev={r['n_sur_developpement']}")

    def test_reserve_brute_no_op_hors_sur_developpement(self):
        """(c) Là où aucune année de réserve ne sur-développe (cas quasi général),
        reserve_totale (brut) == réserve planchée — bascule sans effet. Ancré GENINS."""
        r = clark_ldf(GENINS, annee_base=1)
        brut = np.array(r['ibnr_brut_par_annee'], dtype=float)
        res_planchee = float(np.sum(np.maximum(brut, 0.0)[1:]))
        self.assertAlmostEqual(r['reserve_totale'], res_planchee, delta=2.0)   # no-op
        self.assertAlmostEqual(r['reserve_totale'], 17_740_889, delta=2.0)     # ancrage
        self.assertEqual(r['reserve_totale'], r['reserve_be_clark'])            # alias
        print(f"    OK T25c réserve brute == planchée hors sur-dev : {r['reserve_totale']:,.0f}")


if __name__ == '__main__':
    unittest.main()
