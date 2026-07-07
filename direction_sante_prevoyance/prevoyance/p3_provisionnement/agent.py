"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT P3 ÉLODIE v3.0 : PROVISIONNEMENT PRÉVOYANCE              ║
║  Direction Santé-Prévoyance · Équipe Prévoyance · Sous DIALLO              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  REFONTE v3.0 — Triangle ITT + Chain Ladder + Mack (1993)                  ║
║                                                                              ║
║  MÉTHODES (calquées sur A7 Ibrahim Non-Vie) :                               ║
║    · Chain Ladder (volume-weighted, Mack 1993)                              ║
║    · Mack 1993 — σ ITT, P75/P90/P99.5 (log-normale QIS5 TP.5.26)         ║
║    · Bornhuetter-Ferguson — LR a priori CTIP 2023                          ║
║    · Bootstrap ODP — England & Verrall (2002), 1000 simulations            ║
║    · Back-testing boni/mali — Guide IA 2023                                 ║
║                                                                              ║
║  HYPOTHÈSES (H1-H4) :                                                        ║
║    · H1 — Indépendance colonnes triangle ITT (Spearman)                    ║
║    · H2 — Stabilité facteurs CL (CV ≤ 20%, dérive ≤ 25%)                  ║
║    · H3 — A priori BF vs LR CTIP 2023                                      ║
║    · H4 — Homoscédasticité Bootstrap ODP                                    ║
║                                                                              ║
║  LOB S2 :                                                                    ║
║    · NSLT sous-cat 2 — Protection du revenu / ITT — σ=10%/11%             ║
║    · SLT Invalidité — PM Rentes IP — module vie                            ║
║                                                                              ║
║  DONNÉES D'ENTRÉE :                                                          ║
║    · result_p1      — Tarification Axel                                     ║
║    · result_p2      — Tables Rayan (Markov, maintien)                       ║
║    · triangle_itt   — optionnel, triangle ITT réel (numpy array n×m)       ║
║    · annees_debut   — optionnel, première année de survenance               ║
║    · primes_par_an  — optionnel, vecteur primes par année (pour BF)        ║
║                                                                              ║
║  RÉFÉRENCES :                                                                ║
║    · Mack (1993) — ASTIN Bulletin 23(2)                                    ║
║    · England & Verrall (2002) — British Actuarial Journal                  ║
║    · CTIP — Statistiques prévoyance collective 2023                        ║
║    · EIOPA — RD 2015/35 Art.145 (SCR morbidité), Art.77 (BE)              ║
║    · QIS5 Technical Specifications TP.5.26 (log-normale)                   ║
║                                                                              ║
║  VERSION : 3.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# =============================================================================
#  IMPORTS
# =============================================================================

import json
import logging
import math
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

try:
    from scipy.stats import spearmanr as _spearmanr
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

# ── Palette ActuarIA ──────────────────────────────────────────────────────────
NAVY   = "#0F2E52"; NAVY_L = "#1B3A5C"; NAVY_LL = "#243F6A"; OR = "#C9A84C"
BLANC  = "#F0F4F8"; GRIS   = "#8A9AB0"; VERT   = "#2ECC71"; ROUGE = "#E74C3C"
AMBRE  = "#F39C12"; BLEU   = "#3498DB"; VIOLET = "#9B59B6"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60), height=320,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
)

# =============================================================================
#  CONSTANTES ACTUARIELLES PRÉVOYANCE
# =============================================================================

# CTIP 2023 — Statistiques prévoyance collective
# Source : CTIP, "La prévoyance collective en 2023"
LR_CTIP_ITT_MARCHE = 0.68   # Loss Ratio ITT médiane marché
LR_CTIP_ITT_MIN    = 0.55   # Seuil bas (portefeuilles jeunes)
LR_CTIP_ITT_MAX    = 0.85   # Seuil haut (portefeuilles matures)

# Facteurs de développement de référence ITT (semestres)
# Source : CTIP/BCAC 2019, pratique marché prévoyance collective
# S0→S1 : 1.55, S1→S2 : 1.28, S2→S3 : 1.12, S3→S4 : 1.04, S4→S5 : 1.015
FACTEURS_REFERENCE_ITT = [1.55, 1.28, 1.12, 1.04, 1.015]

# SCR NSLT sous-catégorie 2 — Protection du revenu / ITT
# Source : Annexe II, Règlement Délégué (UE) 2015/35
SIGMA_NSLT_PRIMES   = 0.10   # σ primes = 10%
SIGMA_NSLT_RESERVES = 0.11   # σ réserves = 11%

# Taux d'actualisation PM Rentes IP (proxy EIOPA RFR)
TAUX_ACT_RFR = 0.025

# Bootstrap
N_SIM_BOOTSTRAP = 1000


# =============================================================================
#  CLASSE PRINCIPALE
# =============================================================================

class AgentP3ProvissionnementPrevoyance:
    """
    Agent P3 Élodie v3.0 — Provisionnement Prévoyance.
    Direction Santé-Prévoyance · Équipe Prévoyance · Sous DIALLO.

    Refonte complète v3.0 avec triangle ITT et méthodes actuarielles standards :
    Chain Ladder + Mack (1993) + BF (LR CTIP) + Bootstrap ODP.
    PM Rentes IP conservées (méthode actuarielle vie, correcte).
    """

    NOM     = "Élodie"
    CODE    = "P3"
    VERSION = "3.0"
    MANAGER = "Diallo (Équipe Prévoyance)"

    def __init__(
        self,
        models_path: str  = "models",
        audit_path:  str  = "audit",
        verbose:     bool = True,
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.p3.elodie")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"P3 Élodie v{self.VERSION} | {self.MANAGER}")

    # =========================================================================
    #  POINT D'ENTRÉE PRINCIPAL
    # =========================================================================

    def run(
        self,
        result_p1,
        result_p2,
        triangle_itt:       Optional[np.ndarray] = None,
        annees_debut:       Optional[int]        = None,
        primes_par_an:      Optional[np.ndarray] = None,
        lr_manuel:          Optional[float]      = None,
        taux_actualisation: float                = TAUX_ACT_RFR,
        n_sim_bootstrap:    int                  = N_SIM_BOOTSTRAP,
        generer_graphiques: bool                 = True,
    ) -> Dict:
        """
        Paramètres
        ----------
        result_p1           : dict — résultat P1 Axel (requis)
        result_p2           : dict — résultat P2 Rayan (requis)
        triangle_itt        : np.ndarray (n×m) — triangle cumulé ITT.
                              Optionnel. Si absent, triangle synthétique généré
                              depuis P1/P2 (cadences CTIP 2023).
        annees_debut        : int — première année de survenance (ex: 2020).
        primes_par_an       : np.ndarray — primes par année pour a priori BF.
        lr_manuel           : float — LR a priori manuel (prioritaire).
        taux_actualisation  : float — taux actuariel PM Rentes IP (proxy EIOPA 2.5%).
        n_sim_bootstrap     : int — simulations Bootstrap ODP.
        generer_graphiques  : bool — produire les graphiques Plotly.
        """
        t0  = datetime.now()
        aid = f"P3_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # N1 — Extraction P1 + P2
            src = self._extraire(result_p1, result_p2, taux_actualisation)
            self.logger.info(
                f"[{aid}] P3 v{self.VERSION} | "
                f"PA={src['primes_acquises']:,.0f}€ | "
                f"{src['nb_assures']} assuré(s)"
            )

            # N2 — Triangle ITT
            C_itt, meta = self._preparer_triangle(triangle_itt, src, annees_debut)
            n_ann, n_per = C_itt.shape
            self.logger.info(
                f"[{aid}] Triangle {n_ann}×{n_per} | mode={meta['mode']} | "
                f"ultime={meta['ultime_observe']:,.0f}€"
            )

            # N3 — Hypothèses H1-H4
            h = self._tester_hypotheses(C_itt, primes_par_an, lr_manuel)

            # N4 — Chain Ladder
            cl = self._chain_ladder(C_itt, h['methode_cl'])

            # N4 — Mack 1993
            mack = self._mack_1993(C_itt, cl['facteurs_arr'], cl['facteurs_indiv'], cl)

            # N4 — Bornhuetter-Ferguson
            bf = self._bornhuetter_ferguson(
                C_itt, cl['pct_dev_arr'], cl['last_diag_arr'],
                cl['ultimates_arr'], primes_par_an, lr_manuel
            )

            # N4 — Bootstrap ODP
            boot = self._bootstrap_odp(C_itt, cl['facteurs_arr'], n_sim_bootstrap)

            # N4 — Back-testing
            bt = self._backtesting(C_itt, annees_debut)

            # N5 — Best Estimate ITT
            be_itt = self._best_estimate_itt(h, cl, mack, bf, boot)

            # N6 — PM Rentes IP (méthode vie — inchangée)
            pm_rentes = self._pm_rentes_ip(src)

            # N6 — PSAP IP
            psap_ip = self._psap_ip(src)

            # N6 — PREC
            prec = self._prec(src, be_itt['be'])

            # Totaux
            be_total = be_itt['be'] + pm_rentes + psap_ip
            scr      = self._scr(be_total)
            risk_adj = self._risk_adjustment(be_total)
            tp_prev  = be_total + risk_adj
            prov_tot = be_total + prec
            lr       = src['sinistres_payes_total'] / max(src['primes_acquises'], 1)
            taux_prov = prov_tot / max(src['primes_acquises'], 1)

            # Hypothèses sortie + RAG
            hyp = self._hypotheses_sortie(h, be_itt, mack, bt, lr)
            rag = self._rag(hyp, lr)

            # Commentaire
            com = self._commentaire(
                rag, src, C_itt, meta, h, cl, mack, bf, boot, bt,
                be_itt, pm_rentes, psap_ip, prec, be_total,
                risk_adj, tp_prev, prov_tot, lr, scr, hyp, aid
            )

            # Graphiques
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    C_itt, meta, cl, mack, bf, boot, bt,
                    be_itt, pm_rentes, psap_ip, prec, prov_tot, lr, h
                )

            self._audit(aid, be_total, pm_rentes, lr, rag, mack, scr)
            if self.verbose:
                self._console(aid, rag, be_itt['be'], pm_rentes, prov_tot, lr, mack)

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # Triangle
                "triangle_meta": meta,
                "n_annees":      n_ann,
                "n_periodes":    n_per,

                # Méthodes
                "chain_ladder": {
                    "reserve_totale":   round(cl['reserve_totale'], 2),
                    "facteurs":         [round(float(f), 6) for f in cl['facteurs_arr']],
                    "facteurs_cumules": [round(float(f), 6) for f in cl['f_cum']],
                    "ultimates":        [round(float(u), 2) for u in cl['ultimates_arr']],
                    "ibnr_par_annee":   [round(float(v), 2) for v in cl['ibnr_arr']],
                    "pct_developpe":    [round(float(p), 4) for p in cl['pct_dev_arr']],
                    "tail_factor":      cl['tail_factor'],
                    "methode":          cl['methode'],
                },
                "mack": {
                    "reserve_best_estimate": round(mack['reserve_best_estimate'], 2),
                    "sigma_total":           round(mack['sigma_total'], 2),
                    "cv_pct":                round(mack['cv_pct'], 2),
                    "reserve_p75":           round(mack['reserve_p75'], 2),
                    "reserve_p90":           round(mack['reserve_p90'], 2),
                    "reserve_p99_5":         round(mack['reserve_p99_5'], 2),
                    "statut":                mack['statut'],
                },
                "bf": {
                    "reserve_totale": round(bf['reserve_totale'], 2),
                    "lr_apriori":     bf['lr_apriori'],
                    "source_lr":      bf['source_lr'],
                },
                "bootstrap": boot,
                "backtesting": bt,

                # BE ITT
                "be_itt":        round(be_itt['be'], 2),
                "be_itt_detail": be_itt,

                # Provisions
                "pm_rentes_ip":  round(pm_rentes, 2),
                "psap_ip":       round(psap_ip, 2),
                "psap_total":    round(psap_ip, 2),  # alias pour compatibilité modules Excel/tests
                "prec":          round(prec, 2),

                # Totaux
                "be_prevoyance":        round(be_total, 2),
                "risk_adjustment":      round(risk_adj, 2),
                "tp_prevoyance":        round(tp_prev, 2),
                "provision_totale":     round(prov_tot, 2),
                "loss_ratio":           round(lr, 4),
                "taux_provisionnement": round(taux_prov, 4),

                # SCR
                "scr": scr,

                # Sorties vers P4
                "sorties_p4": {
                    "be_prevoyance":    round(be_total, 2),
                    "risk_adjustment":  round(risk_adj, 2),
                    "tp_prevoyance":    round(tp_prev, 2),
                    "be_itt":           round(be_itt['be'], 2),
                    "pm_rentes_ip":     round(pm_rentes, 2),
                    "psap_ip":          round(psap_ip, 2),
                    "psap_total":       round(psap_ip, 2),
                    "prec":             round(prec, 2),
                    "provision_totale": round(prov_tot, 2),
                    "loss_ratio":       round(lr, 4),
                    "primes_acquises":  src['primes_acquises'],
                    "scr_invalidite":   scr['scr_provisions'],
                    "sigma_itt":        round(mack['sigma_total'], 2),
                    "p90_itt":          round(mack['reserve_p90'], 2),
                    "p99_5_itt":        round(mack['reserve_p99_5'], 2),
                },

                # Standard ActuarIA
                "hypotheses":  hyp,
                "commentaire": com,
                "graphiques":  gph,
                "duree_sec":   round(duree, 2),
                "erreur":      None,
            }

        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR P3 : {e}", exc_info=True)
            return self._erreur(str(e), aid)

    # =========================================================================
    #  N1 — EXTRACTION P1 + P2
    # =========================================================================

    def _extraire(self, result_p1, result_p2, taux_act: float) -> Dict:
        """Extrait et consolide les données de P1 Axel et P2 Rayan."""
        if not result_p1 or not result_p1.get("success"):
            raise ValueError("result_p1 requis et success=True")
        if not result_p2 or not result_p2.get("success"):
            raise ValueError("result_p2 requis et success=True")

        p3 = result_p2.get("sorties_p3", {})

        pa        = float(result_p1.get("primes_acquises",
                    p3.get("primes_acquises", 500_000)))
        nb        = int(p3.get("nb_assures", result_p1.get("nb_assures", 1)))
        sal       = float(p3.get("salaire_brut", result_p1.get("salaire_brut", 45_000)))
        taux_ip   = float(p3.get("taux_ip", 0.0028))
        taux_rente = float(p3.get("taux_rente_ipp",
                     result_p1.get("taux_rente_ipp", 0.60)))
        dur_ip    = float(p3.get("esperance_duree_ip",
                    p3.get("esperance_duree_ip_ans", 20.0)))
        maint_6m  = float(p3.get("prob_maintien_6m",  0.40))
        maint_12m = float(p3.get("prob_maintien_12m", 0.25))
        maint_24m = float(p3.get("prob_maintien_24m", 0.12))

        taux_cot  = float(result_p1.get("taux_cotisation_pct", 2.0)) / 100
        lr_att    = taux_cot * 0.80
        sin_tot   = pa * lr_att
        sin_itt   = sin_tot * 0.65
        sin_ip    = sin_tot * 0.35

        return {
            "primes_acquises":       pa,
            "nb_assures":            nb,
            "salaire_brut":          sal,
            "taux_ip":               taux_ip,
            "taux_rente_ipp":        taux_rente,
            "duree_ip_ans":          dur_ip,
            "prob_maintien_6m":      maint_6m,
            "prob_maintien_12m":     maint_12m,
            "prob_maintien_24m":     maint_24m,
            "taux_actualisation":    taux_act,
            "sinistres_payes_total": sin_tot,
            "sinistres_payes_itt":   sin_itt,
            "sinistres_payes_ip":    sin_ip,
            "lr_attendu":            lr_att,
        }

    # =========================================================================
    #  N2 — TRIANGLE ITT
    # =========================================================================

    def _preparer_triangle(
        self,
        triangle_fourni: Optional[np.ndarray],
        src: Dict,
        annees_debut: Optional[int],
    ) -> Tuple[np.ndarray, Dict]:
        """
        Prépare le triangle ITT (réel ou synthétique).

        Triangle en SEMESTRES (S1…S5). Zone connue : C[i,j] si i+j < n.
        Si triangle_fourni fourni : validation + utilisation directe.
        Sinon : génération synthétique depuis P1/P2 + cadences CTIP 2023.
        """
        if triangle_fourni is not None:
            C = np.array(triangle_fourni, dtype=float)
            if C.ndim != 2 or C.shape[0] < 3 or C.shape[1] < 3:
                raise ValueError(
                    f"triangle_itt doit être 2D, min 3×3. Reçu : {C.shape}"
                )
            C      = np.maximum(C, 0.0)
            mode   = "réel"
            ultime = float(np.max(C))
            n_v, m_v = C.shape

            # ── Validation zone connue ─────────────────────────────────────────
            # Pour chaque ligne i, la dernière colonne connue est k_i = min(n-i-1, m-1).
            # Si C[i, k_i] == 0, l'ultimate projeté sera 0 → IBNR = 0 → sous-provisionnement.
            # Ce cas arrive quand :
            #   (a) le triangle est n > m et des cellules de la zone connue manquent ;
            #   (b) la ligne i n'a pas encore de sinistres (portefeuille très récent).
            cellules_zero = []
            for i_v in range(n_v):
                k_v = min(n_v - i_v - 1, m_v - 1)
                if C[i_v, k_v] == 0.0:
                    cellules_zero.append(i_v)

            if cellules_zero:
                self.logger.warning(
                    f"Triangle ITT {n_v}×{m_v} : cellules de la zone connue à zéro "
                    f"pour les années i={cellules_zero}. "
                    f"L'ultimate et l'IBNR de ces années seront nuls. "
                    f"Vérifier que le triangle est complet (toutes cellules i+j < n renseignées)."                )

            # ── Avertissement triangle rectangulaire n > m ─────────────────────
            if n_v > m_v:
                self.logger.warning(
                    f"Triangle ITT rectangulaire n={n_v} > m={m_v}. "
                    f"Les années i <= {n_v - m_v} ont une zone connue plus large que m colonnes. "
                    f"Vérifier que toutes les cellules C[i,j] pour i+j < n et j < m sont renseignées."                )

            self.logger.info(
                f"Triangle réel {n_v}×{m_v}, "
                f"ultime max={ultime:,.0f}€"
                + (f", {len(cellules_zero)} ligne(s) à zéro" if cellules_zero else "")
            )
        else:
            C, ultime = self._triangle_synthetique(src)
            mode = "synthétique (CTIP 2023)"
            self.logger.warning(
                "Triangle ITT synthétique — fournir triangle_itt réel pour S2 conforme."
            )

        n, m     = C.shape
        an_debut = annees_debut or (datetime.now().year - n + 1)

        return C, {
            "mode":            mode,
            "n_annees":        n,
            "n_periodes":      m,
            "annee_debut":     an_debut,
            "annee_fin":       an_debut + n - 1,
            "labels_annees":   [str(an_debut + i) for i in range(n)],
            "labels_periodes": [f"S{j+1}" for j in range(m)],
            "ultime_observe":  ultime,
            "dimensions":      f"{n}×{m} (semestres)",
        }

    def _triangle_synthetique(self, src: Dict) -> Tuple[np.ndarray, float]:
        """
        Triangle synthétique 5×5 calibré sur P1/P2 + cadences CTIP.

        Volume global = sinistres_payes_itt.
        Cadences = courbe de maintien P2 ajustée.
        Bruit ±5% (seed=42 pour reproductibilité).
        """
        np.random.seed(42)
        n = 5; m = 5

        vol = src["sinistres_payes_itt"]
        if vol <= 0:
            vol = src["primes_acquises"] * LR_CTIP_ITT_MARCHE * 0.65

        # Répartition par année (+2%/an autour de la moyenne)
        vol_an = np.array([
            vol * (1 + 0.02 * (i - n // 2)) / n for i in range(n)
        ])
        vol_an = np.maximum(vol_an, vol * 0.05)

        # Cadences ajustées sur la courbe de maintien P2
        m6   = src.get("prob_maintien_6m", 0.40)
        fact = 1 + (m6 - 0.40) * 0.3
        cad  = np.array([0.45 / fact, 0.72 / fact, 0.87, 0.95, 1.00])
        cad  = np.clip(cad, 0.05, 1.0)
        cad[-1] = 1.0
        for j in range(1, m):
            cad[j] = max(cad[j], cad[j-1] + 0.01)

        C = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                if i + j < n:
                    bruit   = 1 + np.random.normal(0, 0.05)
                    C[i, j] = max(vol_an[i] * cad[j] * bruit,
                                  vol_an[i] * cad[j] * 0.80)

        # Forcer cumulativité
        for i in range(n):
            for j in range(1, m):
                if i + j < n:
                    C[i, j] = max(C[i, j], C[i, j-1] * 1.001)

        return C, float(np.max(C))

    # =========================================================================
    #  N3 — HYPOTHÈSES H1–H4
    # =========================================================================

    def _tester_hypotheses(
        self,
        C: np.ndarray,
        primes: Optional[np.ndarray],
        lr_manuel: Optional[float],
    ) -> Dict:
        """
        Valide H1-H4 — même logique que A7 Ibrahim N2, adaptée ITT.

        H1 Spearman : seuil 0.50 (idem Non-Vie)
        H2 Stabilité : CV ≤ 20%, dérive ≤ 25% (plus larges que Non-Vie —
                        variabilité morbidité naturellement plus élevée)
        H3 A priori  : référence CTIP 2023 (vs FFA pour Non-Vie)
        H4 Homosc    : idem Non-Vie
        """
        n, m    = C.shape
        alertes = []
        infos   = []

        h1 = self._h1_independance(C, alertes, infos)
        h2 = self._h2_stabilite(C, alertes, infos, seuil_cv=0.20, seuil_derive=0.25)
        h3 = self._h3_apriori(C, primes, lr_manuel, alertes, infos)
        h4 = self._h4_homosc(C, alertes, infos)

        methode_cl  = self._choisir_variante_cl(h1, h2)
        methode_rec, raison_rec = self._recommander_methode(h1, h2, h3, n)

        if not h1['ok'] and not h2['ok']:   statut = "ROUGE"
        elif not h1['ok'] or not h2['ok']:  statut = "AMBRE"
        else:                               statut = "VERT"

        return {
            "h1_independance":      h1,
            "h2_stabilite":         h2,
            "h3_apriori_bf":        h3,
            "h4_homosc_bootstrap":  h4,
            "methode_cl":           methode_cl,
            "methode_recommandee":  methode_rec,
            "raison_recommandation": raison_rec,
            "statut_global":        statut,
            "alertes":              alertes,
            "infos":                infos,
        }

    def _h1_independance(self, C: np.ndarray, alertes: list, infos: list) -> Dict:
        """H1 — Indépendance des colonnes (Spearman)."""
        n, m   = C.shape
        seuil  = 0.50
        corrs  = []
        details = []

        if not SCIPY_OK:
            return {
                "ok": True, "score": 70,
                "corr_moy": 0.0, "corr_max": 0.0,
                "n_colonnes_testees": 0, "n_colonnes_sig": 0,
                "seuil_utilise": seuil,
                "message": "H1 non testable — scipy non disponible.",
                "details": [],
            }

        for j in range(m - 2):
            f_j, f_j1 = [], []
            for i in range(n):
                if i + j + 2 >= n:
                    continue
                cij  = float(C[i, j])
                cij1 = float(C[i, j+1])
                cij2 = float(C[i, j+2])
                if cij > 0 and cij1 > 0 and cij2 > 0:
                    f_j.append(cij1 / cij)
                    f_j1.append(cij2 / cij1)

            if len(f_j) >= 4:
                corr, pval = _spearmanr(f_j, f_j1)
                if not math.isnan(corr):
                    corrs.append(abs(corr))
                    details.append({
                        "colonnes":     f"S{j+1}→S{j+2}",
                        "corr":         round(float(corr), 3),
                        "pval":         round(float(pval), 3),
                        "n_obs":        len(f_j),
                        "significatif": pval < 0.05 and abs(corr) > seuil,
                    })

        if not corrs:
            return {
                "ok": True, "score": 80,
                "corr_moy": 0.0, "corr_max": 0.0,
                "n_colonnes_testees": 0, "n_colonnes_sig": 0,
                "seuil_utilise": seuil,
                "message": "H1 non testable — trop peu de données (< 4 obs/colonne).",
                "details": [],
            }

        corr_moy = float(np.mean(corrs))
        corr_max = float(np.max(corrs))
        n_sig    = sum(1 for d in details if d["significatif"])
        ok       = corr_moy < seuil and n_sig <= 1
        score    = max(0, int((1 - corr_moy) * 100))

        if not ok:
            alertes.append(
                f"⚠️ H1 Indépendance ITT : corr_moy={corr_moy:.2f} (seuil={seuil}), "
                f"{n_sig} paire(s) significative(s). "
                f"Possible effet épidémique ou sinistres sériels. BF CTIP recommandé."
            )
            message = (
                f"H1 NON VALIDÉE — corrélation Spearman moy={corr_moy:.2f}, max={corr_max:.2f}. "
                f"{n_sig} paire(s) significative(s). CL et Mack potentiellement biaisés. "
                f"En ITT : effet épidémique, changement de franchise ou mix contrats possible."
            )
        else:
            infos.append(f"✅ H1 Indépendance ITT validée (corr_moy={corr_moy:.2f})")
            message = (
                f"H1 VALIDÉE — corrélation Spearman moy={corr_moy:.2f} < {seuil}. "
                f"Pas d'effet épidémique ou sinistres sériels détecté. CL approprié."
            )

        return {
            "ok":                 ok,
            "score":              score,
            "corr_moy":           round(corr_moy, 3),
            "corr_max":           round(corr_max, 3),
            "n_colonnes_testees": len(corrs),
            "n_colonnes_sig":     n_sig,
            "seuil_utilise":      seuil,
            "message":            message,
            "details":            details[:5],
        }

    def _h2_stabilite(
        self, C: np.ndarray, alertes: list, infos: list,
        seuil_cv: float = 0.20, seuil_derive: float = 0.25,
    ) -> Dict:
        """H2 — Stabilité facteurs CL. Seuils ITT : CV≤20%, dérive≤25%."""
        n, m      = C.shape
        cv_cols   = []
        der_cols  = []
        details   = []

        for j in range(m - 1):
            facteurs = []
            for i in range(n):
                if i + j + 1 >= n:
                    continue
                cij  = float(C[i, j])
                cij1 = float(C[i, j+1])
                if cij > 0 and cij1 > 0:
                    facteurs.append(cij1 / cij)

            if len(facteurs) >= 3:
                arr    = np.array(facteurs)
                moy    = float(np.mean(arr))
                std    = float(np.std(arr, ddof=1))
                cv     = std / moy if moy > 0 else 0.0
                cv_cols.append(cv)

                derive = 0.0
                mid    = len(facteurs) // 2
                if mid >= 2:
                    m_anc  = float(np.mean(arr[:mid]))
                    m_rec  = float(np.mean(arr[mid:]))
                    derive = abs(m_rec - m_anc) / max(m_anc, 1e-9)
                    der_cols.append(derive)

                ref = FACTEURS_REFERENCE_ITT[j] if j < len(FACTEURS_REFERENCE_ITT) else 1.0
                details.append({
                    "semestre":  f"S{j+1}→S{j+2}",
                    "n_obs":     len(facteurs),
                    "f_moyen":   round(moy, 4),
                    "cv":        round(cv, 3),
                    "derive":    round(derive, 3),
                    "ref_ctip":  round(ref, 3),
                    "ecart_ref": round(abs(moy - ref) / max(ref, 1e-9), 3),
                })

        if not cv_cols:
            return {
                "ok": True, "score": 80,
                "cv_moy": 0.0, "cv_max": 0.0, "derive_moy": 0.0,
                "ok_cv": True, "ok_derive": True,
                "seuil_cv": seuil_cv, "seuil_derive": seuil_derive,
                "message": "H2 non testable — trop peu de données.",
                "details": [],
            }

        cv_moy     = float(np.mean(cv_cols))
        cv_max     = float(np.max(cv_cols))
        derive_moy = float(np.mean(der_cols)) if der_cols else 0.0
        ok_cv      = cv_moy    < seuil_cv
        ok_derive  = derive_moy < seuil_derive
        ok         = ok_cv and ok_derive
        score      = max(0, int((1 - cv_moy / max(seuil_cv * 2, 0.40)) * 100))

        if not ok_cv:
            alertes.append(
                f"⚠️ H2 Stabilité ITT : CV={cv_moy:.1%} > {seuil_cv:.0%}. "
                f"Facteurs instables — variante médiane recommandée."
            )
        if not ok_derive:
            alertes.append(
                f"⚠️ H2 Dérive ITT : {derive_moy:.1%} > {seuil_derive:.0%}. "
                f"Facteurs en évolution — volume_weighted recommandé."
            )
        if ok:
            infos.append(
                f"✅ H2 Stabilité ITT : CV={cv_moy:.1%} < {seuil_cv:.0%}, "
                f"dérive={derive_moy:.1%} < {seuil_derive:.0%}"
            )

        message = (
            f"H2 {'VALIDÉE' if ok else 'NON VALIDÉE'} — "
            f"CV={cv_moy:.1%} (seuil ITT {seuil_cv:.0%}), "
            f"dérive={derive_moy:.1%} (seuil {seuil_derive:.0%}). "
            + (
                "Facteurs ITT stables dans le temps."
                if ok else
                "Instabilité/dérive détectée. Seuils ITT plus larges que Non-Vie "
                "(variabilité naturelle de la morbidité)."
            )
        )

        return {
            "ok":          ok,
            "ok_cv":       ok_cv,
            "ok_derive":   ok_derive,
            "score":       score,
            "cv_moy":      round(cv_moy, 4),
            "cv_max":      round(cv_max, 4),
            "derive_moy":  round(derive_moy, 4),
            "seuil_cv":    seuil_cv,
            "seuil_derive": seuil_derive,
            "message":     message,
            "details":     details,
        }

    def _h3_apriori(
        self,
        C: np.ndarray,
        primes: Optional[np.ndarray],
        lr_manuel: Optional[float],
        alertes: list,
        infos: list,
    ) -> Dict:
        """
        H3 — A priori BF vs LR CTIP 2023.

        Sources (par ordre de priorité) :
        1. LR manuel
        2. LR depuis primes fournies
        3. LR CTIP 2023 directement (proxy marché)
        """
        n, m   = C.shape
        lr_ref = LR_CTIP_ITT_MARCHE
        lr_src = "CTIP 2023 — Prévoyance collective"

        # Cas 0 : LR manuel
        if lr_manuel is not None and lr_manuel > 0:
            ok    = LR_CTIP_ITT_MIN <= lr_manuel <= LR_CTIP_ITT_MAX
            score = 85 if ok else 50
            ecart = abs(lr_manuel - lr_ref)
            if ecart > 0.20:
                alertes.append(
                    f"⚠️ H3 LR manuel={lr_manuel:.1%} vs CTIP={lr_ref:.1%} "
                    f"(écart {ecart:.0%}). Documenter la justification."
                )
            return {
                "ok": ok, "score": score,
                "lr_apriori":    round(lr_manuel, 4),
                "lr_std":        0.0, "cv_lr": 0.0,
                "source":        "manuel",
                "lr_reference":  lr_ref, "lr_reference_src": lr_src,
                "message": (
                    f"H3 A priori ITT : LR manuel={lr_manuel:.1%}. "
                    f"Référence CTIP 2023={lr_ref:.1%}. "
                    f"Plage : [{LR_CTIP_ITT_MIN:.0%}, {LR_CTIP_ITT_MAX:.0%}]. "
                    f"{'Dans plage.' if ok else 'Hors plage — justifier.'}"
                ),
            }

        nb_mat = min(3, n - 1)

        # Cas 1 : primes fournies
        if primes is not None and len(primes) >= nb_mat:
            lr_an = []
            for i in range(nb_mat):
                p    = float(primes[i])
                last = min(n - i - 1, m - 1)
                u    = float(C[i, last])
                if p > 0 and u > 0:
                    lr_an.append(u / p)

            if lr_an:
                lr_moy = float(np.mean(lr_an))
                lr_std = float(np.std(lr_an, ddof=1)) if len(lr_an) > 1 else 0.0
                cv_lr  = lr_std / max(lr_moy, 1e-9)
                ok     = LR_CTIP_ITT_MIN <= lr_moy <= LR_CTIP_ITT_MAX
                score  = max(0, min(100, int(100 - cv_lr * 200)))

                if abs(lr_moy - lr_ref) > 0.15:
                    alertes.append(
                        f"🟡 H3 LR ITT={lr_moy:.1%} vs CTIP={lr_ref:.1%} "
                        f"(écart {abs(lr_moy - lr_ref):.0%})."
                    )

                return {
                    "ok": ok, "score": score,
                    "lr_apriori":    round(lr_moy, 4),
                    "lr_std":        round(lr_std, 4),
                    "cv_lr":         round(cv_lr, 4),
                    "source":        "primes_fournies",
                    "nb_matures":    nb_mat,
                    "lr_reference":  lr_ref, "lr_reference_src": lr_src,
                    "message": (
                        f"H3 {'VALIDÉE' if ok else 'À VÉRIFIER'} — "
                        f"LR ITT={lr_moy:.1%} (CV={cv_lr:.1%}, {nb_mat} années matures). "
                        f"CTIP 2023={lr_ref:.1%}. Plage : [{LR_CTIP_ITT_MIN:.0%}, {LR_CTIP_ITT_MAX:.0%}]."
                    ),
                }

        # Cas 2 : proxy CTIP direct
        alertes.append(
            f"ℹ️ H3 A priori ITT : primes non fournies. "
            f"LR a priori = {lr_ref:.1%} (CTIP 2023 médiane marché). "
            f"Fournir primes_par_an pour BF conforme S2."
        )
        return {
            "ok": True, "score": 60,
            "lr_apriori":    round(lr_ref, 4),
            "lr_std":        0.0, "cv_lr": 0.0,
            "source":        "ctip_2023_reference",
            "lr_reference":  lr_ref, "lr_reference_src": lr_src,
            "message": (
                f"H3 ESTIMÉE — LR a priori = {lr_ref:.1%} (CTIP 2023 médiane). "
                f"Fournir primes_par_an pour un a priori BF personnalisé."
            ),
        }

    def _h4_homosc(self, C: np.ndarray, alertes: list, infos: list) -> Dict:
        """H4 — Homoscédasticité Bootstrap ODP (England & Verrall 2002)."""
        n, m     = C.shape
        var_cols = []

        for j in range(m - 1):
            facteurs, poids = [], []
            for i in range(n):
                if i + j + 1 >= n:
                    continue
                cij  = float(C[i, j])
                cij1 = float(C[i, j+1])
                if cij > 0 and cij1 > 0:
                    facteurs.append(cij1 / cij)
                    poids.append(cij)

            if len(facteurs) >= 3:
                arr = np.array(facteurs)
                w   = np.array(poids)
                moy = float(np.average(arr, weights=w))
                var = float(np.average((arr - moy)**2, weights=w))
                var_cols.append(var)

        if len(var_cols) < 3:
            return {
                "ok": True, "score": 75,
                "phi": 0.0, "cv_var": 0.0,
                "message": "H4 non testable — moins de 3 semestres disponibles.",
            }

        var_arr = np.array(var_cols)
        cv_var  = float(np.std(var_arr) / max(np.mean(var_arr), 1e-12))
        phi     = float(np.mean(var_arr))
        ok      = cv_var < 1.0
        score   = max(0, int((1 - cv_var / 2.0) * 100))

        if not ok:
            alertes.append(
                f"🟡 H4 Homoscédasticité ITT : CV variances={cv_var:.2f} > 1.0. "
                f"Bootstrap ODP moins fiable. Préférer percentiles Mack pour le SCR."
            )
            message = (
                f"H4 HÉTÉROSCÉDASTICITÉ ITT — CV variances={cv_var:.2f}. "
                f"Bootstrap ODP approximatif. Utiliser Mack (log-normale QIS5) pour S2."
            )
        else:
            infos.append(f"✅ H4 Homoscédasticité ITT validée (CV={cv_var:.2f}, φ={phi:.6f})")
            message = f"H4 VALIDÉE — CV variances={cv_var:.2f} < 1.0, φ={phi:.6f}."

        return {
            "ok":     ok,
            "score":  score,
            "phi":    round(phi, 6),
            "cv_var": round(cv_var, 3),
            "message": message,
        }

    def _choisir_variante_cl(self, h1: Dict, h2: Dict) -> str:
        """Variante CL selon H1/H2 — même logique que A7 Ibrahim N2."""
        h1_ok  = h1.get("ok", True)
        h2_ok  = h2.get("ok", True)
        cv     = h2.get("cv_moy", 0.0)
        derive = h2.get("derive_moy", 0.0)

        if h1_ok and h2_ok:           return "standard"
        if not h2_ok and derive > 0.25 and cv <= 0.25: return "volume_weighted"
        if not h2_ok and cv > 0.25:   return "mediane"
        if not h2_ok and cv > 0.20:   return "trimmed_mean"
        if not h1_ok:                 return "volume_weighted"
        return "standard"

    def _recommander_methode(
        self, h1: Dict, h2: Dict, h3: Dict, n: int
    ) -> Tuple[str, str]:
        """Méthode recommandée — même règles que A7 Ibrahim."""
        if n < 4:
            return "bornhuetter_ferguson", f"Triangle petit ({n} années). BF avec LR CTIP."
        if h1["ok"] and h2["ok"]:
            return "mack_1993", "H1+H2 validées. Mack 1993 pour quantification incertitude S2."
        if not h1["ok"] and h3["score"] >= 60:
            return "bornhuetter_ferguson", f"H1 rejetée (corr={h1['corr_moy']:.2f}). BF ancré sur CTIP."
        if not h1["ok"]:
            return "bornhuetter_ferguson", "H1 rejetée + a priori peu fiable. BF conservateur."
        return "bornhuetter_ferguson", "H2 rejetée. BF robuste aux facteurs instables."

    # =========================================================================
    #  N4 — CHAIN LADDER
    # =========================================================================

    def _chain_ladder(self, C: np.ndarray, methode: str = "standard") -> Dict:
        """
        Chain Ladder sur triangle ITT — même implémentation que A7 Ibrahim.

        Facteur ≥ 1.0 (triangle cumulatif). Tail = 1.0 si dernier LDF < 1.05.
        """
        n, m = C.shape

        # ── Facteurs de développement ─────────────────────────────────────────
        f_arr = np.ones(m - 1)
        f_ind = []

        for j in range(m - 1):
            ind_j = []
            c_j   = []
            for i in range(n):
                # Zone connue : i+j+1 < n (triangle carré ou supérieur)
                # break valide car les lignes sont ordonnées : si la condition
                # est vraie pour i, elle l'est pour tous les i suivants
                if i + j + 1 >= n:
                    break
                cij  = float(C[i, j])
                cij1 = float(C[i, j+1])
                if cij > 0 and cij1 > 0:
                    ind_j.append(cij1 / cij)
                    c_j.append(cij)
            f_ind.append(ind_j)

            if not ind_j:
                f_arr[j] = 1.0
                continue

            arr = np.array(ind_j, dtype=float)
            w   = np.array(c_j,   dtype=float)

            if methode == "standard":
                f_arr[j] = float(np.average(arr, weights=w))
            elif methode == "volume_weighted":
                f_arr[j] = float(np.average(arr, weights=np.sqrt(w)))
            elif methode == "mediane":
                f_arr[j] = float(np.median(arr))
            elif methode == "trimmed_mean":
                if len(arr) >= 4:
                    q10 = np.percentile(arr, 10)
                    q90 = np.percentile(arr, 90)
                    mask = (arr >= q10) & (arr <= q90)
                    f_arr[j] = float(np.mean(arr[mask])) if mask.sum() > 0 \
                                else float(np.mean(arr))
                else:
                    f_arr[j] = float(np.average(arr, weights=w))
            else:
                f_arr[j] = float(np.average(arr, weights=w))

            f_arr[j] = max(f_arr[j], 1.0)

        # ── Tail factor ───────────────────────────────────────────────────────
        dernier = float(f_arr[-1]) if len(f_arr) > 0 else 1.0
        if dernier < 1.05:
            tail = 1.0
            tail_msg = (
                f"Tail = 1.0 — dernier LDF ITT={dernier:.4f} < 1.05. "
                f"Développement ITT considéré complet à S{m}."
            )
        else:
            k = min(3, len(f_arr))
            f_q = f_arr[-k:]
            x   = np.arange(k, dtype=float)
            eps = 1e-8
            try:
                b, a = np.polyfit(x, np.log(np.maximum(f_q - 1.0, eps)), 1)
                if b < 0:
                    tail = 1.0
                    for step in range(30):
                        fe = 1.0 + np.exp(a + b * (k + step))
                        if fe < 1.0001:
                            break
                        tail *= fe
                    tail = float(np.clip(tail, 1.0, 1.10))
                else:
                    tail = 1.0
            except Exception:
                tail = 1.0
            tail_msg = (
                f"Tail = {tail:.4f} — dernier LDF ITT={dernier:.4f} ≥ 1.05. "
                f"Extrapolation log-linéaire appliquée."
            )

        # ── Facteurs cumulés ──────────────────────────────────────────────────
        f_cum = np.ones(m)
        f_cum[m-1] = tail
        for j in range(m - 2, -1, -1):
            f_cum[j] = f_arr[j] * f_cum[j+1]

        # ── % développé ───────────────────────────────────────────────────────
        pct = np.ones(n)
        for i in range(n):
            k = min(n - i - 1, m - 1)
            if k < len(f_cum) and f_cum[k] > 0:
                pct[i] = 1.0 / f_cum[k]
        pct = np.clip(pct, 0.0, 1.0)

        # ── Ultimates + IBNR ──────────────────────────────────────────────────
        ultimates  = np.zeros(n)
        ibnr       = np.zeros(n)
        last_diag  = np.array([float(C[i, min(n-i-1, m-1)]) for i in range(n)])

        for i in range(n):
            k_i = min(n - i - 1, m - 1)
            val = float(C[i, k_i])
            for j in range(k_i, m - 1):
                if j < len(f_arr):
                    val *= f_arr[j]
            val *= tail
            ultimates[i] = val
            ibnr[i]      = max(val - last_diag[i], 0.0)

        reserve = float(np.sum(ibnr[1:]))

        return {
            "facteurs_arr":   f_arr,
            "facteurs_indiv": f_ind,
            "f_cum":          f_cum,
            "pct_dev_arr":    pct,
            "ultimates_arr":  ultimates,
            "ibnr_arr":       ibnr,
            "last_diag_arr":  last_diag,
            "tail_factor":    tail,
            "tail_message":   tail_msg,
            "reserve_totale": round(reserve, 2),
            "methode":        f"Chain Ladder ITT ({methode})",
        }

    # =========================================================================
    #  N4 — MACK 1993
    # =========================================================================

    def _mack_1993(
        self,
        C: np.ndarray,
        f_arr: np.ndarray,
        f_ind: list,
        cl: Dict,
    ) -> Dict:
        """
        Mack (1993) ASTIN Bulletin 23(2) — extension stochastique CL.

        Formules 3.4 (σ²_j) et 3.5 (extrapolation).
        Theorem 3 (variance par année + termes croisés).
        Percentiles log-normale QIS5 TP.5.26.
        """
        n, m       = C.shape
        ultimates  = cl['ultimates_arr']
        ibnr       = cl['ibnr_arr']

        # σ²_j (formule 3.4)
        sigma2 = np.zeros(m - 1)
        for j in range(m - 1):
            f_j  = float(f_arr[j])
            ind  = f_ind[j]
            n_j  = len(ind)
            if n_j < 2:
                continue
            c_j = []
            for i in range(n):
                if i + j + 1 < n and C[i, j] > 0 and C[i, j+1] > 0:
                    c_j.append(float(C[i, j]))
                if len(c_j) == n_j:
                    break
            if len(c_j) < 2:
                continue
            num = sum(c_j[k] * (ind[k] - f_j)**2 for k in range(min(n_j, len(c_j))))
            sigma2[j] = num / (n_j - 1)

        # Extrapolation σ² manquants (formule 3.5)
        if m > 2 and sigma2[1] == 0 and sigma2[0] > 0:
            sigma2[1] = sigma2[0]
        for j in range(2, m - 1):
            if sigma2[j] > 0:
                continue
            s1 = sigma2[j-1]; s2 = sigma2[j-2]
            if s1 > 0 and s2 > 0:
                sigma2[j] = min(s1, s2, s1**2 / s2)
            elif s1 > 0:
                sigma2[j] = s1

        # Volumes W[j]
        W = np.zeros(m - 1)
        for j in range(m - 1):
            for i in range(n):
                if i + j + 1 < n and C[i, j] > 0:
                    W[j] += C[i, j]

        # Variance par année (Theorem 3)
        var_r = np.zeros(n)
        for i in range(1, n):
            k_i   = min(n - i - 1, m - 1)
            U_i   = float(ultimates[i])
            if U_i <= 0:
                continue
            c_proj = float(C[i, k_i])
            v      = 0.0
            for j in range(k_i, m - 1):
                if j >= len(f_arr) or j >= len(sigma2):
                    break
                f_j = float(f_arr[j]); s2j = float(sigma2[j]); w_j = float(W[j])
                if f_j <= 0 or s2j <= 0:
                    c_proj *= max(f_j, 1.0)
                    continue
                v      += s2j / (f_j**2) * (1.0 / max(c_proj, 1e-10) + 1.0 / max(w_j, 1e-10))
                c_proj *= f_j
            var_r[i] = (U_i**2) * v

        # Variance totale avec termes croisés
        var_tot = float(np.sum(var_r[1:]))
        for i in range(1, n - 1):
            for l in range(i + 1, n):
                U_i = float(ultimates[i]); U_l = float(ultimates[l])
                if U_i <= 0 or U_l <= 0:
                    continue
                k_l = min(n - l - 1, m - 1)
                s   = 0.0
                for j in range(k_l, m - 1):
                    if j >= len(f_arr) or j >= len(sigma2):
                        break
                    f_j = float(f_arr[j]); s2j = float(sigma2[j]); w_j = float(W[j])
                    if f_j > 0 and s2j > 0 and w_j > 0:
                        s += s2j / (f_j**2 * w_j)
                var_tot += 2.0 * U_i * U_l * s
        var_tot = max(var_tot, 0.0)

        sigma_par_an = np.sqrt(np.maximum(var_r, 0.0))
        sigma_total  = float(math.sqrt(var_tot))
        reserve_be   = float(np.sum(ibnr[1:]))
        cv_pct       = sigma_total / max(reserve_be, 1e-9) * 100.0

        # Percentiles log-normale (QIS5 TP.5.26)
        if reserve_be > 0 and sigma_total > 0:
            cv_ln  = sigma_total / reserve_be
            s2_ln  = math.log(1.0 + cv_ln**2)
            s_ln   = math.sqrt(s2_ln)
            m_ln   = math.log(reserve_be) - s2_ln / 2.0
            p75    = float(math.exp(m_ln + 0.6745 * s_ln))
            p90    = float(math.exp(m_ln + 1.2816 * s_ln))
            p95    = float(math.exp(m_ln + 1.6449 * s_ln))
            p99_5  = float(math.exp(m_ln + 2.5758 * s_ln))
        else:
            p75 = p90 = p95 = p99_5 = reserve_be
            s_ln = m_ln = 0.0

        if cv_pct < 10.0:   statut = "VERT"
        elif cv_pct < 20.0: statut = "AMBRE"
        else:               statut = "ROUGE"

        return {
            "reserve_best_estimate": round(reserve_be,  2),
            "sigma_total":           round(sigma_total, 2),
            "var_totale":            round(var_tot,     4),
            "cv_pct":                round(cv_pct,      2),
            "sigma_par_annee":       [round(float(s), 2) for s in sigma_par_an],
            "sigma2_par_colonne":    [round(float(s), 6) for s in sigma2],
            "reserve_p75":           round(p75,   2),
            "reserve_p90":           round(p90,   2),
            "reserve_p95":           round(p95,   2),
            "reserve_p99_5":         round(p99_5, 2),
            "mu_ln":                 round(m_ln,  6),
            "sigma_ln":              round(s_ln,  6),
            "statut":                statut,
            "methode":               "Mack (1993) ITT — ASTIN 23(2) · Log-normale QIS5 TP.5.26",
            "message": (
                f"Mack (1993) ITT : BE={reserve_be:,.0f}€ · σ={sigma_total:,.0f}€ · "
                f"CV={cv_pct:.1f}% · P90={p90:,.0f}€ · P99.5={p99_5:,.0f}€ · {statut}"
            ),
        }

    # =========================================================================
    #  N4 — BORNHUETTER-FERGUSON
    # =========================================================================

    def _bornhuetter_ferguson(
        self,
        C: np.ndarray,
        pct: np.ndarray,
        diag: np.ndarray,
        ult_cl: np.ndarray,
        primes: Optional[np.ndarray],
        lr_manuel: Optional[float],
    ) -> Dict:
        """
        BF (1972) sur triangle ITT. LR a priori : manuel > primes > CTIP direct.
        """
        n, m    = C.shape
        alertes = []

        nb_mat_bf = min(3, n - 1)   # cohérent avec _h3_apriori
        if lr_manuel is not None and lr_manuel > 0:
            lr = float(np.clip(lr_manuel, 0.01, 3.0)); source = "manuel"
        elif primes is not None and len(primes) >= nb_mat_bf:
            lr_an = []
            for i in range(nb_mat_bf):
                p = float(primes[i]); u = float(ult_cl[i])
                if p > 0 and u > 0:
                    lr_an.append(u / p)
            lr = float(np.mean(lr_an)) if lr_an else LR_CTIP_ITT_MARCHE
            source = "primes_fournies"
        else:
            lr     = LR_CTIP_ITT_MARCHE
            source = "ctip_2023_reference"
            alertes.append(
                f"ℹ️ BF ITT : LR a priori = {lr:.1%} (CTIP 2023 médiane). "
                f"Fournir primes_par_an pour BF conforme S2."
            )

        if abs(lr - LR_CTIP_ITT_MARCHE) > 0.15:
            alertes.append(
                f"🟡 BF ITT : LR={lr:.1%} vs CTIP={LR_CTIP_ITT_MARCHE:.1%}. Vérifier."
            )

        lr = float(np.clip(lr, 0.01, 3.0))
        mu = np.array([float(primes[i]) * lr
                       for i in range(n)]) if primes is not None and len(primes) >= n \
            else ult_cl * lr

        ibnr_bf = np.zeros(n)
        ult_bf  = np.zeros(n)
        for i in range(n):
            frac       = max(1.0 - float(pct[i]), 0.0)
            ibnr_bf[i] = frac * float(mu[i])
            ult_bf[i]  = float(diag[i]) + ibnr_bf[i]

        reserve = float(np.sum(ibnr_bf[1:]))
        return {
            "lr_apriori":            round(lr, 4),
            "source_lr":             source,
            "lr_reference_ctip":     LR_CTIP_ITT_MARCHE,
            "ibnr_par_annee":        [round(float(v), 2) for v in ibnr_bf],
            "ultimates":             [round(float(v), 2) for v in ult_bf],
            "reserve_totale":        round(reserve, 2),
            "reserve_best_estimate": round(reserve, 2),
            "alertes":               alertes,
            "methode":               "Bornhuetter-Ferguson (1972) — LR CTIP 2023",
        }

    # =========================================================================
    #  N4 — BOOTSTRAP ODP
    # =========================================================================

    def _bootstrap_odp(
        self, C: np.ndarray, f_arr: np.ndarray, n_sim: int
    ) -> Dict:
        """Bootstrap ODP (England & Verrall 2002) — même algo que A7 Ibrahim."""
        np.random.seed(42)
        n, m = C.shape

        # Fitted values
        C_fit = np.zeros((n, m))
        for i in range(n):
            C_fit[i, 0] = C[i, 0]
            for j in range(1, m):
                if i + j < n and j - 1 < len(f_arr) and C[i, j-1] > 0:
                    C_fit[i, j] = C[i, j-1] * f_arr[j-1]

        # Résidus de Pearson
        cellules = []
        residus  = np.zeros((n, m))
        for i in range(n):
            for j in range(1, m):
                if i + j < n and C_fit[i, j] > 0 and C[i, j] > 0:
                    residus[i, j] = (C[i, j] - C_fit[i, j]) / math.sqrt(C_fit[i, j])
                    cellules.append((i, j))

        n_obs    = len(cellules)
        n_params = n + (m - 1)
        df       = n_obs - n_params

        if df > 0:
            adj = math.sqrt(n_obs / df)
            for (i, j) in cellules:
                residus[i, j] *= adj

        r_bruts = np.array([
            (C[i, j] - C_fit[i, j]) / math.sqrt(C_fit[i, j])
            for (i, j) in cellules if C_fit[i, j] > 0
        ])
        phi = float(np.sum(r_bruts**2) / max(df, 1)) if len(r_bruts) > 0 else 0.0

        res_list = [residus[i, j] for (i, j) in cellules if residus[i, j] != 0]
        if len(res_list) < 4:
            # Calcul de la réserve CL simple comme référence dégradée
            # (on ne peut pas soustraire C[i,k] à lui-même — bug corrigé)
            reserve_ref = 0.0
            for i in range(1, n):
                k_i  = min(n - i - 1, m - 1)
                val  = float(C[i, k_i])
                for jj in range(k_i, m - 1):
                    if jj < len(f_arr):
                        val *= f_arr[jj]
                reserve_ref += max(val - float(C[i, k_i]), 0.0)
            return self._bootstrap_degrade(reserve_ref, n_sim)

        res_arr   = np.array(res_list)
        last_diag = np.array([float(C[i, min(n-i-1, m-1)]) for i in range(n)])

        # Simulations
        reserves_sim = np.zeros(n_sim)
        for b in range(n_sim):
            idx      = np.random.randint(0, len(res_arr), size=(n, m))
            res_boot = res_arr[idx]
            C_star   = np.zeros((n, m))
            for i in range(n):
                C_star[i, 0] = max(C[i, 0], 1.0)
                for j in range(1, m):
                    if i + j < n and C_fit[i, j] > 0:
                        val = C_fit[i, j] + res_boot[i, j] * math.sqrt(C_fit[i, j])
                        C_star[i, j] = max(val, C_fit[i, j] * 0.01)
                        C_star[i, j] = max(C_star[i, j], C_star[i, j-1])

            f_star = np.ones(m - 1)
            for j in range(m - 1):
                num = den = 0.0
                for i in range(n):
                    if i + j + 1 < n and C_star[i, j] > 0 and C_star[i, j+1] > 0:
                        num += C_star[i, j+1]; den += C_star[i, j]
                f_star[j] = max(num / max(den, 1e-10), 1.0)

            rb = 0.0
            for i in range(1, n):
                k_i   = min(n - i - 1, m - 1)
                c_val = float(C[i, k_i])
                for j in range(k_i, m - 1):
                    if j < len(f_star):
                        mn = c_val * f_star[j]
                        if phi > 0 and mn > 0:
                            c_val = max(mn + np.random.normal(0, math.sqrt(phi * mn)),
                                        mn * 0.01)
                        else:
                            c_val = mn
                rb += max(c_val - last_diag[i], 0.0)
            reserves_sim[b] = rb

        be_boot  = float(np.mean(reserves_sim))
        std_boot = float(np.std(reserves_sim, ddof=1))
        cv_boot  = std_boot / max(be_boot, 1e-9)

        if cv_boot < 0.10:   statut = "VERT"
        elif cv_boot < 0.20: statut = "AMBRE"
        else:                statut = "ROUGE"

        return {
            "be_bootstrap":  round(be_boot,  2),
            "std_bootstrap": round(std_boot, 2),
            "cv_bootstrap":  round(cv_boot,  4),
            "p50":   round(float(np.percentile(reserves_sim, 50)),   2),
            "p75":   round(float(np.percentile(reserves_sim, 75)),   2),
            "p90":   round(float(np.percentile(reserves_sim, 90)),   2),
            "p95":   round(float(np.percentile(reserves_sim, 95)),   2),
            "p99_5": round(float(np.percentile(reserves_sim, 99.5)), 2),
            "ic_95_inf": round(float(np.percentile(reserves_sim, 2.5)),  2),
            "ic_95_sup": round(float(np.percentile(reserves_sim, 97.5)), 2),
            "phi":        round(phi, 6),
            "n_obs":      n_obs,
            "n_params":   n_params,
            "df":         df,
            "n_simulations": n_sim,
            "distribution": reserves_sim.tolist(),
            "statut":     statut,
            "methode":    "Bootstrap ODP — England & Verrall (2002)",
            "message": (
                f"Bootstrap ODP ITT : BE={be_boot:,.0f}€ · σ={std_boot:,.0f}€ · "
                f"CV={cv_boot*100:.1f}% · P90={float(np.percentile(reserves_sim, 90)):,.0f}€ · "
                f"P99.5={float(np.percentile(reserves_sim, 99.5)):,.0f}€ · φ={phi:.4f}"
            ),
        }

    def _bootstrap_degrade(self, ref: float, n_sim: int) -> Dict:
        return {
            "be_bootstrap": round(ref, 2), "std_bootstrap": 0.0, "cv_bootstrap": 0.0,
            "p50": round(ref, 2), "p75": round(ref, 2), "p90": round(ref, 2),
            "p95": round(ref, 2), "p99_5": round(ref, 2),
            "ic_95_inf": round(ref, 2), "ic_95_sup": round(ref, 2),
            "phi": 0.0, "n_obs": 0, "n_params": 0, "df": 0,
            "n_simulations": n_sim, "distribution": [ref] * n_sim,
            "statut": "AMBRE", "methode": "Bootstrap ODP — England & Verrall (2002)",
            "message": "Bootstrap ITT : triangle trop petit — résidus insuffisants.",
        }

    # =========================================================================
    #  N4 — BACK-TESTING
    # =========================================================================

    def _backtesting(self, C: np.ndarray, annees_debut: Optional[int]) -> Dict:
        """Back-testing boni/mali ITT — Guide IA 2023 § 4.3."""
        n, m = C.shape
        if n < 4:
            return {
                "success": False,
                "erreur":  f"Triangle < 4 années ({n}) — back-testing non disponible.",
                "tableau": [], "statut": "AMBRE", "score_qualite": 75,
                "n_rouge_n1": 0, "n_ambre_n1": 0,
                "n_rouge_n2": 0, "n_ambre_n2": 0,
                "n_matures": 0,
                "message": "Back-testing ITT non disponible.",
            }

        SEUIL_ROUGE = 15.0; SEUIL_AMBRE = 8.0; SEUIL_MATUR = 0.75

        def _cl(tri):
            _n, _m = tri.shape
            obs = np.where(np.isnan(tri), 0.0, tri)
            fs  = []
            for j in range(_m - 1):
                mask = (obs[:, j] > 0) & (obs[:, j+1] > 0)
                nd   = float(np.sum(obs[mask, j+1]))
                dd   = float(np.sum(obs[mask, j]))
                fs.append(nd / dd if dd > 0 else 1.0)
            fc = np.ones(_m)
            for j in range(_m - 2, -1, -1):
                fc[j] = fc[j+1] * (fs[j] if j < len(fs) else 1.0)
            ults = np.zeros(_n)
            for i in range(_n):
                lj = 0
                for j in range(_m - 1, -1, -1):
                    if not np.isnan(tri[i, j]) and tri[i, j] > 0:
                        lj = j; break
                ults[i] = tri[i, lj] * fc[lj] if fc[lj] > 0 else tri[i, lj]
            return ults

        def _tronque(k):
            mx = max((i+j for i in range(n) for j in range(m)
                      if not np.isnan(C[i,j]) and C[i,j] > 0), default=n-1)
            sd = mx - k
            if sd < 2: return np.zeros(n)
            Ct = C.copy().astype(float)
            Ct[np.add.outer(np.arange(n), np.arange(m)) > sd] = np.nan
            if int(np.sum(~np.isnan(Ct) & (Ct > 0))) < 6: return np.zeros(n)
            return _cl(Ct)

        ult_n1 = _tronque(1); ult_n2 = _tronque(2)
        ult_f  = _cl(C.copy())
        obs_n  = np.zeros(n); pct = np.zeros(n)
        for i in range(n):
            for j in range(m-1,-1,-1):
                if C[i,j] > 0: obs_n[i] = float(C[i,j]); break
            pct[i] = obs_n[i] / ult_f[i] if ult_f[i] > 0 else 0.0
        pct = np.clip(pct, 0.0, 1.0)

        tableau  = []
        nr1 = na1 = nr2 = na2 = 0
        sc1 = []; sc2 = []
        an  = annees_debut or (datetime.now().year - n + 1)

        for i in range(n):
            obs   = float(obs_n[i])
            u1    = float(ult_n1[i])
            u2    = float(ult_n2[i])
            pi    = float(pct[i])
            mat   = pi >= SEUIL_MATUR
            if obs <= 0: continue

            bm1 = round(u1 - obs, 0) if u1 > 0 else None
            bm2 = round(u2 - obs, 0) if u2 > 0 else None
            ep1 = round(bm1/obs*100,1) if bm1 is not None else None
            ep2 = round(bm2/obs*100,1) if bm2 is not None else None

            def _st(ep):
                if ep is None or not mat: return None
                a = abs(ep)
                return "ROUGE" if a >= SEUIL_ROUGE else "AMBRE" if a >= SEUIL_AMBRE else "VERT"

            s1 = _st(ep1); s2 = _st(ep2)
            if mat:
                if s1=="ROUGE": nr1+=1
                elif s1=="AMBRE": na1+=1
                if ep1 is not None: sc1.append(max(0, 100-abs(ep1)*2))
                if s2=="ROUGE": nr2+=1
                elif s2=="AMBRE": na2+=1
                if ep2 is not None: sc2.append(max(0, 100-abs(ep2)*2))

            tableau.append({
                "annee": i, "annee_label": str(an+i),
                "observe_n": round(obs,0),
                "ultimate_n1": round(u1,0) if u1>0 else None,
                "ultimate_n2": round(u2,0) if u2>0 else None,
                "boni_mali_n1": bm1, "boni_mali_n2": bm2,
                "ecart_pct_n1": ep1, "ecart_pct_n2": ep2,
                "statut_n1": s1, "statut_n2": s2,
                "pct_developpe": round(pi*100,1), "mature": mat,
            })

        sq1 = round(float(np.mean(sc1)),1) if sc1 else 100.0
        sq2 = round(float(np.mean(sc2)),1) if sc2 else 100.0
        sq  = round((sq1+sq2)/2,1)
        nr  = max(nr1, nr2); na = max(na1, na2)

        if nr >= 1:   statut = "ROUGE"
        elif na >= 1: statut = "AMBRE"
        else:         statut = "VERT"

        nm = sum(1 for r in tableau if r["mature"])

        return {
            "success": True, "tableau": tableau, "statut": statut,
            "score_qualite": sq, "score_n1": sq1, "score_n2": sq2,
            "n_rouge_n1": nr1, "n_ambre_n1": na1,
            "n_rouge_n2": nr2, "n_ambre_n2": na2,
            "n_matures": nm,
            "message": (
                f"Back-testing ITT — {nm} années matures. "
                f"N-1 : {nr1} rouge · {na1} ambre — Score {sq1}/100. "
                f"N-2 : {nr2} rouge · {na2} ambre — Score {sq2}/100."
            ),
        }

    # =========================================================================
    #  N5 — BEST ESTIMATE ITT
    # =========================================================================

    def _best_estimate_itt(
        self, h: Dict, cl: Dict, mack: Dict, bf: Dict, boot: Dict
    ) -> Dict:
        """BE ITT = combinaison pondérée par scores H1-H4 — même logique A7 N4."""
        rec = h.get("methode_recommandee", "bornhuetter_ferguson")
        h1s = h["h1_independance"]["score"]
        h2s = h["h2_stabilite"]["score"]
        h3s = h["h3_apriori_bf"]["score"]
        h4s = h["h4_homosc_bootstrap"]["score"]

        reserves = {
            "chain_ladder":         (cl["reserve_totale"],                int(h1s*0.50+h2s*0.50)),
            "mack_1993":            (mack["reserve_best_estimate"],        int(h1s*0.50+h2s*0.30+h4s*0.20)),
            "bornhuetter_ferguson": (bf["reserve_totale"],                 int(h1s*0.20+h2s*0.20+h3s*0.60)),
        }

        SEUIL = 55
        incl = {meth: (r, s) for meth, (r, s) in reserves.items() if s >= SEUIL and r > 0}
        if not incl:
            incl = {
                "mack_1993":            (mack["reserve_best_estimate"], 50),
                "bornhuetter_ferguson": (bf["reserve_totale"],          50),
            }

        _map = {
            "mack_1993": "mack_1993", "mack": "mack_1993",
            "chain_ladder": "chain_ladder",
            "bornhuetter_ferguson": "bornhuetter_ferguson", "bf": "bornhuetter_ferguson",
        }
        rec_n = _map.get(rec.lower().replace(" ", "_").replace("-", "_"), "")

        tot_s  = sum(s for _, s in incl.values())
        pb     = {meth: s / max(tot_s, 1) for meth, (_, s) in incl.items()}

        PMIN = 0.50
        if rec_n and rec_n in incl:
            pr    = max(pb.get(rec_n, 0), PMIN)
            reste = 1.0 - pr
            autr  = {meth: v for meth, v in pb.items() if meth != rec_n}
            ta    = sum(autr.values())
            poids = {rec_n: round(pr, 4)}
            if ta > 0:
                for meth, v in autr.items():
                    poids[meth] = round(v / ta * reste, 4)
            else:
                poids = {rec_n: 1.0}
        else:
            poids = {meth: round(v, 4) for meth, v in pb.items()}

        tp = sum(poids.values())
        if tp > 0:
            poids = {meth: round(v / tp, 4) for meth, v in poids.items()}

        be   = float(sum(poids[meth] * r for meth, (r, _) in incl.items()))
        vals = [r for r, _ in incl.values()]
        cvi  = float(np.std(vals) / max(np.mean(vals), 1e-9) * 100) if len(vals) > 1 else 0.0

        boot_ok = bool(boot.get("be_bootstrap", 0) > 0)
        if boot_ok:
            p75 = float(boot.get("p75",  mack["reserve_p75"]))
            p90 = float(boot.get("p90",  mack["reserve_p90"]))
            p99 = float(boot.get("p99_5", mack["reserve_p99_5"]))
            src = "Bootstrap ODP"
        else:
            p75 = mack["reserve_p75"]
            p90 = mack["reserve_p90"]
            p99 = mack["reserve_p99_5"]
            src = "Mack 1993"

        return {
            "be":                round(be, 2),
            "cv_inter":          round(cvi, 2),
            "methodes_incluses": list(incl.keys()),
            "poids":             poids,
            "methode_rec":       rec_n or rec,
            "p75":               round(p75, 2),
            "p90":               round(p90, 2),
            "p99_5":             round(p99, 2),
            "source_percentiles": src,
        }

    # =========================================================================
    #  N6 — PROVISIONS LONG TERME
    # =========================================================================

    def _pm_rentes_ip(self, src: Dict) -> float:
        """
        PM Rentes IP = provision mathématique actualisée (méthode actuarielle vie).

        PM = nb_invalides × rente_annuelle × annuité_actualisée
        nb_invalides = nb_assures × taux_ip × 0.60
        (60% des invalides en rente viagère, 40% en phase consolidation)
        """
        rente_an  = src["salaire_brut"] * src["taux_rente_ipp"]
        dur_ip    = src["duree_ip_ans"]
        v         = 1.0 / (1 + src["taux_actualisation"])
        annuite   = sum(v**t for t in range(1, int(dur_ip) + 1))
        # v3.0 : formule corrigée — suppression du facteur age/10 (inversé en v2)
        nb_inv    = max(0, int(src["nb_assures"] * src["taux_ip"] * 0.60))
        return nb_inv * rente_an * annuite

    def _psap_ip(self, src: Dict) -> float:
        """PSAP IP = dossiers en constitution d'invalidité (6 mois de rente)."""
        rente_men = src["salaire_brut"] * src["taux_rente_ipp"] / 12
        nb_cons   = max(1, int(src["nb_assures"] * src["taux_ip"] * 2))
        return nb_cons * rente_men * 6

    def _prec(self, src: Dict, be_itt: float) -> float:
        """PREC = max(0, PA × max(0, ratio_combiné - 1))."""
        lr = src["sinistres_payes_total"] / max(src["primes_acquises"], 1)
        rc = lr + 0.20
        return max(0.0, src["primes_acquises"] * max(0.0, rc - 1.0))

    # =========================================================================
    #  N7 — SCR NSLT SOUS-CAT 2
    # =========================================================================

    def _scr(self, be_total: float) -> Dict:
        """
        SCR NSLT sous-catégorie 2 — Protection du revenu.

        σ_réserves = 11% (Annexe II RD 2015/35)
        SCR_prov = 3 × σ × BE (Art. 105 S2)
        """
        scr_prov  = 3.0 * SIGMA_NSLT_RESERVES * be_total
        scr_prime = 3.0 * SIGMA_NSLT_PRIMES   * be_total
        ratio     = scr_prov / max(be_total, 1e-9)
        return {
            "scr_provisions":  round(scr_prov,  0),
            "scr_primes":      round(scr_prime, 0),
            "sigma_reserves":  SIGMA_NSLT_RESERVES,
            "sigma_primes":    SIGMA_NSLT_PRIMES,
            "ratio_scr_be":    round(ratio, 4),
            "lob":             "NSLT sous-cat 2 — Protection du revenu",
            "methode":         "Formule standard Art.105 S2 (Rgt 2015/35)",
            "message": (
                f"SCR_prov = 3 × {SIGMA_NSLT_RESERVES:.0%} × {be_total:,.0f}€ "
                f"= {scr_prov:,.0f}€ (ratio={ratio:.1%}). "
                f"NSLT sous-cat 2 — Annexe II RD 2015/35."
            ),
        }

    # =========================================================================
    #  N8 — RISK ADJUSTMENT IFRS 17
    # =========================================================================

    def _risk_adjustment(self, be_total: float) -> float:
        """
        Risk Adjustment IFRS 17 — méthode CoC 6% (§B91 IFRS 17).

        RA = SCR_morbidité × CoC = 0.35 × BE × 0.06 = 2.1% BE.
        Floor : 3% BE (pratique marché prévoyance long terme).
        """
        ra = 0.35 * be_total * 0.06
        return max(ra, be_total * 0.03)

    # =========================================================================
    #  N9 — HYPOTHÈSES SORTIE + RAG
    # =========================================================================

    def _hypotheses_sortie(
        self, h: Dict, be_itt: Dict, mack: Dict, bt: Dict, lr: float
    ) -> list:
        """Hypothèses H1-H7 pour le rapport — standard ActuarIA."""
        def _st(ok): return "VALIDÉE" if ok else "NON VALIDÉE"

        h1 = h["h1_independance"]; h2 = h["h2_stabilite"]
        h3 = h["h3_apriori_bf"];   h4 = h["h4_homosc_bootstrap"]

        hyp = [
            {"id": "H1", "hypothese": "Indépendance années de survenance ITT (Spearman)",
             "valeur": h1["message"], "statut": _st(h1["ok"]), "score": h1["score"], "critique": True},
            {"id": "H2", "hypothese": "Stabilité facteurs CL (CV≤20%, dérive≤25%)",
             "valeur": h2["message"], "statut": _st(h2["ok"]), "score": h2["score"], "critique": True},
            {"id": "H3", "hypothese": f"A priori BF ∈ [{LR_CTIP_ITT_MIN:.0%}–{LR_CTIP_ITT_MAX:.0%}] (CTIP 2023)",
             "valeur": h3["message"], "statut": _st(h3["ok"]), "score": h3["score"], "critique": False},
            {"id": "H4", "hypothese": "Homoscédasticité Bootstrap ODP (England & Verrall 2002)",
             "valeur": h4["message"], "statut": _st(h4["ok"]), "score": h4["score"], "critique": False},
            {"id": "H5", "hypothese": "Loss Ratio Prévoyance ≤ 90%",
             "valeur": f"LR={lr*100:.1f}% {'≤' if lr<=0.90 else '>'} 90%",
             "statut": "VALIDÉE" if lr<=0.90 else ("À JUSTIFIER" if lr<=1.0 else "NON VALIDÉE"),
             "score": max(0, int((1.2-lr)*100)) if lr<=1.2 else 0, "critique": True},
            {"id": "H6", "hypothese": "Incertitude Mack (CV<20% = VERT EIOPA Guidelines TP)",
             "valeur": f"CV={mack['cv_pct']:.1f}% — {mack['statut']}",
             "statut": "VALIDÉE" if mack["statut"] == "VERT" else "À JUSTIFIER",
             "score": 100 if mack["statut"]=="VERT" else (70 if mack["statut"]=="AMBRE" else 40),
             "critique": False},
        ]

        if bt.get("success"):
            hyp.append({
                "id": "H7", "hypothese": "Back-testing boni/mali (Guide IA 2023)",
                "valeur": bt["message"][:200],
                "statut": "VALIDÉE" if bt["statut"]=="VERT" else "À JUSTIFIER",
                "score": bt["score_qualite"], "critique": False,
            })

        return hyp

    def _rag(self, hyp: list, lr: float) -> str:
        if lr > 1.0:
            return "ROUGE"
        if any(h.get("critique") and h["statut"] == "NON VALIDÉE" for h in hyp):
            return "ROUGE"
        if any(h["statut"] in ("À JUSTIFIER", "NON VALIDÉE") for h in hyp):
            return "AMBRE"
        return "VERT"

    # =========================================================================
    #  N10 — COMMENTAIRE
    # =========================================================================

    def _commentaire(
        self, rag, src, C, meta, h, cl, mack, bf, boot, bt,
        be_itt, pm_rentes, psap_ip, prec, be_total,
        risk_adj, tp_prev, prov_tot, lr, scr, hyp, aid
    ) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        n, m = C.shape

        L = [
            "="*70,
            f"  RAPPORT PROVISIONNEMENT PRÉVOYANCE — P3 ÉLODIE v{self.VERSION}",
            f"  {ic} STATUT : {rag} | Audit : {aid}",
            "="*70, "",

            "📊 TRIANGLE ITT", "─"*50,
            f"  Dimensions    : {meta['dimensions']} | Mode : {meta['mode']}",
            f"  Années        : {meta['annee_debut']} → {meta['annee_fin']}",
            f"  Ultime observé: {meta['ultime_observe']:>12,.0f}€",
            "",

            "🔬 MÉTHODES ACTUARIELLES", "─"*50,
            f"  Chain Ladder ({h['methode_cl']:10s}): {cl['reserve_totale']:>12,.0f}€",
            f"  Mack 1993              : {mack['reserve_best_estimate']:>12,.0f}€"
            f" | σ={mack['sigma_total']:,.0f}€ | CV={mack['cv_pct']:.1f}%",
            f"  Bornhuetter-Ferguson   : {bf['reserve_totale']:>12,.0f}€"
            f" | LR={bf['lr_apriori']:.1%} ({bf['source_lr']})",
            f"  Bootstrap ODP          : {boot.get('be_bootstrap',0):>12,.0f}€"
            f" | φ={boot.get('phi',0):.4f}",
            "",

            "📐 BEST ESTIMATE ITT (Art.77 S2)", "─"*50,
            f"  BE ITT pondéré : {be_itt['be']:>12,.0f}€"
            f" | Méthode : {be_itt['methode_rec']}",
            f"  CV inter-méth  : {be_itt['cv_inter']:.1f}%"
            f" | Source pcts : {be_itt['source_percentiles']}",
            f"  P75 ITT        : {be_itt['p75']:>12,.0f}€",
            f"  P90 ITT        : {be_itt['p90']:>12,.0f}€",
            f"  P99.5 ITT      : {be_itt['p99_5']:>12,.0f}€",
            "",

            "🔢 PROVISIONS TOTALES PRÉVOYANCE", "─"*50,
            f"  BE ITT (triangle CL/Mack)   : {be_itt['be']:>12,.0f}€",
            f"  PM Rentes IP (actuariat vie): {pm_rentes:>12,.0f}€",
            f"  PSAP IP (constitution inv.) : {psap_ip:>12,.0f}€",
            f"  {'─'*42}",
            f"  BE Prévoyance Total         : {be_total:>12,.0f}€",
            f"  Risk Adjustment IFRS 17     : {risk_adj:>12,.0f}€",
            f"  TP Prévoyance               : {tp_prev:>12,.0f}€",
            f"  PREC                        : {prec:>12,.0f}€",
            f"  Provision Totale            : {prov_tot:>12,.0f}€",
            f"  Loss Ratio                  : {lr*100:>11.1f}%",
            "",

            "⚖️ SCR NSLT SOUS-CAT 2 (Art.105 S2)", "─"*50,
            f"  {scr['message']}",
            "",

            "📋 HYPOTHÈSES H1-H7", "─"*50,
        ]

        for hi in hyp:
            ic_h = "✅" if hi["statut"]=="VALIDÉE" else ("⚠️" if hi["statut"]=="À JUSTIFIER" else "❌")
            L.append(
                f"  {ic_h} [{hi['id']}] {hi['hypothese']}"
                f" — Score {hi['score']}/100 — {hi['statut']}"
            )

        L += ["", "🎯 AVIS ÉLODIE → DIALLO", "─"*50]

        if rag == "VERT":
            L.append(
                f"✅ PROVISIONNEMENT VALIDÉ — BE={be_total:,.0f}€ | "
                f"LR={lr*100:.1f}% | P90={be_itt['p90']:,.0f}€. "
                f"Sorties transmises à P4 Valentin."
            )
        elif rag == "AMBRE":
            L.append(
                "⚠️ PROVISIONNEMENT ACCEPTABLE SOUS RÉSERVE — "
                "Vérifier les hypothèses signalées avant transmission à P4."
            )
        else:
            L.append(
                f"❌ PROVISIONNEMENT INSUFFISANT — LR={lr*100:.1f}% ou hypothèse critique rejetée. "
                "Escalade Diallo. Ne pas transmettre à P4 sans validation."
            )

        if meta["mode"] != "réel":
            L += [
                "", "⚠️ TRIANGLE SYNTHÉTIQUE", "─"*50,
                "  Triangle ITT généré depuis P1/P2 (cadences CTIP 2023).",
                "  Fournir triangle_itt réel pour un provisionnement S2 conforme.",
            ]

        return "\n".join(L)

    # =========================================================================
    #  N10 — GRAPHIQUES (5 graphiques)
    # =========================================================================

    def _graphiques(
        self, C, meta, cl, mack, bf, boot, bt,
        be_itt, pm_rentes, psap_ip, prec, prov_tot, lr, h
    ) -> Dict:
        gph = {}
        n, m = C.shape

        # G1 — Heatmap triangle ITT
        try:
            z = []
            for i in range(n):
                row = []
                for j in range(m):
                    row.append(round(float(C[i,j]),0) if i+j < n and C[i,j] > 0 else None)
                z.append(row)
            fig = go.Figure(go.Heatmap(
                z=z, x=meta["labels_periodes"], y=meta["labels_annees"],
                colorscale=[[0,NAVY_L],[0.5,"#2D5F8A"],[1,OR]],
                text=[[f"{v:,.0f}€" if v else "" for v in row] for row in z],
                texttemplate="%{text}", textfont=dict(size=9, color=BLANC),
                hovertemplate="Année %{y} · %{x} : %{z:,.0f}€<extra></extra>",
            ))
            fig.update_layout(
                **LAYOUT_BASE, height=360,
                title=dict(text=f"G1 — Heatmap Triangle ITT ({meta['mode']})",
                           font=dict(color=OR, size=13), x=0.01),
                xaxis_title="Période (semestres)", yaxis_title="Année de survenance",
            )
            gph["heatmap_triangle_itt"] = fig
        except Exception as e:
            self.logger.warning(f"G1 : {e}")

        # G2 — Convergence méthodes
        try:
            noms = ["Chain Ladder", "Mack 1993", "BF (CTIP)", "Bootstrap"]
            vals = [cl["reserve_totale"], mack["reserve_best_estimate"],
                    bf["reserve_totale"], boot.get("be_bootstrap", 0)]
            cols = [BLEU, OR, VERT, VIOLET]
            fig = go.Figure()
            for nm, vl, co in zip(noms, vals, cols):
                if vl > 0:
                    fig.add_trace(go.Bar(
                        x=[nm], y=[vl/1e3], marker_color=co, width=0.5, opacity=0.88,
                        text=[f"{vl/1e3:.0f}k€"], textposition="outside",
                        textfont=dict(color=BLANC, size=10), showlegend=False,
                    ))
            fig.add_hline(y=be_itt["be"]/1e3, line_dash="dash", line_color=OR, line_width=2,
                          annotation_text=f"BE={be_itt['be']/1e3:.0f}k€",
                          annotation_font=dict(color=OR, size=10))
            fig.update_layout(
                **LAYOUT_BASE,
                title=dict(text="G2 — Convergence méthodes ITT — BE S2",
                           font=dict(color=OR, size=13), x=0.01),
                yaxis_title="k€",
            )
            gph["convergence_methodes"] = fig
        except Exception as e:
            self.logger.warning(f"G2 : {e}")

        # G3 — IBNR par année
        try:
            ann = meta["labels_annees"]
            ibnr_cl = [round(float(v),2) for v in cl["ibnr_arr"]]
            ibnr_bf = bf["ibnr_par_annee"]
            fig = make_subplots(rows=1, cols=2,
                                subplot_titles=["IBNR Chain Ladder (k€)", "IBNR CL vs BF (k€)"])
            fig.add_trace(go.Bar(
                x=ann, y=[v/1e3 for v in ibnr_cl], marker_color=OR, width=0.5, opacity=0.88,
                text=[f"{v/1e3:.0f}" for v in ibnr_cl], textposition="outside",
                textfont=dict(color=BLANC, size=9), showlegend=False,
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=ann, y=[v/1e3 for v in ibnr_cl], mode="lines+markers", name="CL",
                line=dict(color=OR, width=2), marker=dict(size=7),
            ), row=1, col=2)
            fig.add_trace(go.Scatter(
                x=ann, y=[v/1e3 for v in ibnr_bf], mode="lines+markers", name="BF",
                line=dict(color=VERT, width=2, dash="dot"), marker=dict(size=7, color=VERT),
            ), row=1, col=2)
            lay = dict(**LAYOUT_BASE)
            lay.update(dict(
                title=dict(text="G3 — IBNR ITT par année de survenance",
                           font=dict(color=OR, size=13), x=0.01),
                legend=dict(x=0.55, y=0.95, bgcolor="rgba(0,0,0,0)",
                            font=dict(color=BLANC, size=9)),
            ))
            fig.update_layout(**lay)
            gph["ibnr_par_annee"] = fig
        except Exception as e:
            self.logger.warning(f"G3 : {e}")

        # G4 — Distribution Bootstrap
        try:
            dist = boot.get("distribution", [])
            if dist and len(dist) > 10:
                da = np.array(dist)
                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=da/1e3, nbinsx=40, marker_color=BLEU, opacity=0.75, name="Dist.",
                ))
                for pn, pv, col in [("BE", be_itt["be"], OR),
                                     ("P90", be_itt["p90"], AMBRE),
                                     ("P99.5", be_itt["p99_5"], ROUGE)]:
                    fig.add_vline(x=pv/1e3, line_color=col, line_width=2, line_dash="dash",
                                  annotation_text=f"{pn}={pv/1e3:.0f}k€",
                                  annotation_font=dict(color=col, size=9))
                fig.update_layout(
                    **LAYOUT_BASE,
                    title=dict(text=f"G4 — Bootstrap ODP ITT ({len(dist)} sim.)",
                               font=dict(color=OR, size=13), x=0.01),
                    xaxis_title="Réserve ITT (k€)", yaxis_title="Fréquence", showlegend=False,
                )
                gph["bootstrap_distribution"] = fig
        except Exception as e:
            self.logger.warning(f"G4 : {e}")

        # G5 — Décomposition provisions
        try:
            comp = ["BE ITT (CL/Mack)", "PM Rentes IP", "PSAP IP", "PREC"]
            vals = [be_itt["be"], pm_rentes, psap_ip, prec]
            cols = [OR, VIOLET, BLEU, GRIS]
            fig  = make_subplots(rows=1, cols=2,
                                 subplot_titles=["Décomposition (k€)", "Répartition (%)"],
                                 specs=[[{"type":"bar"}, {"type":"pie"}]])
            fig.add_trace(go.Bar(
                x=comp, y=[v/1e3 for v in vals], marker_color=cols, width=0.5, opacity=0.88,
                text=[f"{v/1e3:.0f}k€" for v in vals], textposition="outside",
                textfont=dict(color=BLANC, size=9), showlegend=False,
            ), row=1, col=1)
            vp = [v for v in vals if v > 0]
            lp = [c for c, v in zip(comp, vals) if v > 0]
            cp = [c for c, v in zip(cols, vals) if v > 0]
            if vp:
                fig.add_trace(go.Pie(
                    labels=lp, values=vp, marker_colors=cp,
                    textfont=dict(size=9, color=BLANC),
                ), row=1, col=2)
            lay = dict(**LAYOUT_BASE)
            lay.update(dict(title=dict(
                text=f"G5 — Provisions prévoyance = {prov_tot/1e3:.0f}k€ | LR={lr*100:.1f}%",
                font=dict(color=OR if lr<=0.90 else (AMBRE if lr<=1.0 else ROUGE), size=12),
                x=0.01
            )))
            fig.update_layout(**lay)
            gph["decomposition_provisions"] = fig
        except Exception as e:
            self.logger.warning(f"G5 : {e}")

        return gph

    # =========================================================================
    #  AUDIT + CONSOLE + ERREUR
    # =========================================================================

    def _audit(self, aid, be_total, pm_rentes, lr, rag, mack, scr):
        try:
            log = self.audit_path / "p3_audit.jsonl"
            entry = {
                "audit_id": aid, "timestamp": datetime.now().isoformat(),
                "version": self.VERSION, "statut_rag": rag,
                "be_total": round(be_total, 2), "pm_rentes_ip": round(pm_rentes, 2),
                "loss_ratio": round(lr, 4),
                "sigma_itt": round(mack["sigma_total"], 2),
                "cv_pct": round(mack["cv_pct"], 2),
                "scr_prov": scr["scr_provisions"],
            }
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _console(self, aid, rag, be_itt, pm_rentes, prov_tot, lr, mack):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        print(f"\n{'─'*70}")
        print(f"  P3 ÉLODIE v{self.VERSION} | {aid} | {ic} {rag}")
        print(
            f"  BE ITT={be_itt:,.0f}€ | PM Rentes={pm_rentes:,.0f}€ | "
            f"Total={prov_tot:,.0f}€ | LR={lr*100:.1f}%"
        )
        print(
            f"  σ Mack={mack['sigma_total']:,.0f}€ | "
            f"CV={mack['cv_pct']:.1f}% | statut={mack['statut']}"
        )
        print(f"{'─'*70}")

    def _erreur(self, msg: str, aid: str = "") -> Dict:
        return {
            "success": False, "agent": self.NOM, "version": self.VERSION,
            "audit_id": aid, "statut_rag": "ROUGE",
            "triangle_meta": {}, "n_annees": 0, "n_periodes": 0,
            "chain_ladder": {}, "mack": {}, "bf": {}, "bootstrap": {}, "backtesting": {},
            "be_itt": 0.0, "be_itt_detail": {},
            "pm_rentes_ip": 0.0, "psap_ip": 0.0, "prec": 0.0,
            "be_prevoyance": 0.0, "risk_adjustment": 0.0, "tp_prevoyance": 0.0,
            "provision_totale": 0.0, "loss_ratio": 0.0, "taux_provisionnement": 0.0,
            "scr": {}, "sorties_p4": {},
            "hypotheses": [], "commentaire": f"❌ ERREUR P3 v{self.VERSION} : {msg}",
            "graphiques": {}, "duree_sec": 0.0, "erreur": msg,
        }


# =============================================================================
#  DÉMONSTRATION
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  P3 ÉLODIE v3.0 — PROVISIONNEMENT PRÉVOYANCE")
    print("  Triangle ITT | CL | Mack 1993 | BF CTIP | Bootstrap ODP")
    print("=" * 70)

    r_p1 = {
        "success": True, "age": 40.0, "salaire_brut": 45_000,
        "primes_acquises": 679.66 * 500, "nb_assures": 500,
        "taux_cotisation_pct": 1.51, "taux_rente_ipp": 0.60,
    }
    r_p2 = {
        "success": True,
        "sorties_p3": {
            "age": 40.0, "taux_ip": 0.00336, "taux_itt": 0.042,
            "prob_maintien_6m": 0.578, "prob_maintien_12m": 0.345,
            "prob_maintien_24m": 0.145, "esperance_duree_ip": 24.8,
            "salaire_brut": 45_000, "taux_rente_ipp": 0.60,
            "primes_acquises": 679.66 * 500, "nb_assures": 500,
            "franchise_jours": 90,
        },
    }

    agent = AgentP3ProvissionnementPrevoyance(
        models_path="/tmp/p3/models", audit_path="/tmp/p3/audit", verbose=True
    )
    r = agent.run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut       : {r['statut_rag']}")
    print(f"  Triangle     : {r['n_annees']}×{r['n_periodes']} — {r['triangle_meta'].get('mode','?')}")
    print(f"  BE ITT (CL)  : {r['chain_ladder']['reserve_totale']:>12,.0f}€")
    print(f"  BE ITT (Mack): {r['mack']['reserve_best_estimate']:>12,.0f}€ | CV={r['mack']['cv_pct']:.1f}%")
    print(f"  BE ITT (BF)  : {r['bf']['reserve_totale']:>12,.0f}€ | LR={r['bf']['lr_apriori']:.1%}")
    print(f"  Bootstrap BE : {r['bootstrap'].get('be_bootstrap',0):>12,.0f}€")
    print(f"  P90 ITT      : {r['be_itt_detail']['p90']:>12,.0f}€")
    print(f"  P99.5 ITT    : {r['be_itt_detail']['p99_5']:>12,.0f}€")
    print(f"  PM Rentes IP : {r['pm_rentes_ip']:>12,.0f}€")
    print(f"  BE Prévoyance: {r['be_prevoyance']:>12,.0f}€")
    print(f"  SCR NSLT     : {r['scr']['scr_provisions']:>12,.0f}€")
    print(f"  LR           : {r['loss_ratio']*100:>11.1f}%")
    print(f"  Durée        : {r['duree_sec']:.2f}s")
    print("\n  Hypothèses :")
    for hi in r["hypotheses"]:
        ic = "✅" if hi["statut"]=="VALIDÉE" else "⚠️"
        print(f"    {ic} [{hi['id']}] {hi['hypothese']} — {hi['score']}/100")
