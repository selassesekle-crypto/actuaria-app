"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT P3 ÉLODIE v3.0 : PROVISIONNEMENT PRÉVOYANCE              ║
║  Direction Santé-Prévoyance · Équipe Prévoyance · Sous DIALLO              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  REFONTE v3.0 — Triangle ITT + Chain Ladder + Mack (1993)                  ║
║                                                                              ║
║  PÉRIMÈTRE :                                                                 ║
║    · IBNR ITT        — Chain Ladder + Mack sur triangle semestriel         ║
║    · PSAP ITT        — calibrée sur facteurs CL (vs forfaitaire v2)        ║
║    · PM Rentes IP    — provisions mathématiques actualisées (inchangées)   ║
║    · PSAP IP         — dossiers en phase de constitution invalidité         ║
║    · PREC            — provision pour risques en cours                      ║
║                                                                              ║
║  MÉTHODES (calquées sur A7 Ibrahim Non-Vie) :                               ║
║    · Chain Ladder (volume-weighted, Mack 1993)                              ║
║    · Mack 1993 — σ ITT, P75/P90/P99.5 (log-normale QIS5 TP.5.26)         ║
║    · Bornhuetter-Ferguson — LR a priori CTIP 2023                          ║
║    · Bootstrap ODP — England & Verrall (2002), 1000 simulations            ║
║    · Back-testing boni/mali — Guide IA 2023                                 ║
║                                                                              ║
║  HYPOTHÈSES (H1-H4, scores /100, messages contextualisés) :                 ║
║    · H1 — Indépendance colonnes triangle ITT (Spearman)                    ║
║    · H2 — Stabilité facteurs CL (CV + dérive temporelle)                   ║
║    · H3 — A priori BF vs LR CTIP 2023 (benchmark externe)                 ║
║    · H4 — Homoscédasticité Bootstrap ODP (England & Verrall 2002)          ║
║                                                                              ║
║  LOB S2 :                                                                    ║
║    · NSLT sous-cat 2 — Protection du revenu / ITT — σ=10% primes, 11% rés ║
║    · SLT Invalidité — PM Rentes IP — module vie (annuités actualisées)     ║
║                                                                              ║
║  DONNÉES D'ENTRÉE :                                                          ║
║    · result_p1      — Tarification Axel (primes, salaire, franchise)        ║
║    · result_p2      — Tables Rayan (Markov, maintien, durées)               ║
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
from typing import Dict, List, Optional, Tuple

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
AMBRE  = "#F39C12"; BLEU   = "#3498DB"; VIOLET = "#9B59B6"; CYAN  = "#1ABC9C"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60), height=320,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
)

# =============================================================================
#  CONSTANTES ACTUARIELLES PRÉVOYANCE
# =============================================================================

# ── CTIP 2023 — Statistiques prévoyance collective ────────────────────────────
# Source : CTIP, "La prévoyance collective en 2023", publication annuelle
# LR ITT marché (frais de gestion inclus) : 60-75% selon branche professionnelle
LR_CTIP_ITT_MARCHE = 0.68   # Loss Ratio ITT marché CTIP 2023 (médiane)
LR_CTIP_ITT_MIN    = 0.55   # Seuil bas — portefeuilles jeunes/bonne sélection
LR_CTIP_ITT_MAX    = 0.85   # Seuil haut — portefeuilles matures/sinistralité élevée

# ── Cadences de développement ITT (CTIP, BCAC 2019, pratique marché) ─────────
# Triangle ITT en SEMESTRES (périodes de 6 mois)
# S0→S1 : ~1.45-1.65 (déclarations tardives 1er arrêt)
# S1→S2 : ~1.20-1.35 (régularisation dossiers prolongés)
# S2→S3 : ~1.08-1.15 (consolidation arrêts longs)
# S3→S4 : ~1.03-1.06 (résiduel passage IP)
# S4→S5 : ~1.01-1.02 (queue de développement)
FACTEURS_REFERENCE_ITT = [1.55, 1.28, 1.12, 1.04, 1.015]

# ── SCR NSLT Protection du revenu ─────────────────────────────────────────────
# Source : Annexe II, Règlement Délégué (UE) 2015/35
# Sous-catégorie 2 NSLT : Protection du revenu / ITT
SIGMA_NSLT_PRIMES    = 0.10   # σ primes = 10%
SIGMA_NSLT_RESERVES  = 0.11   # σ réserves = 11%

# ── Taux d'actualisation PM Rentes IP ─────────────────────────────────────────
# Source : courbe EIOPA RFR EUR (Art. 77 Directive S2)
# Proxy 2.5% = taux long terme (duration rentes IP ~12-18 ans)
TAUX_ACT_RFR = 0.025

# ── Bootstrap ────────────────────────────────────────────────────────────────
N_SIM_BOOTSTRAP = 1000   # 5000 recommandé en production


# =============================================================================
#  CLASSE PRINCIPALE
# =============================================================================

class AgentP3ProvisionnemntPrevoyance:
    """
    Agent P3 Élodie v3.0 — Provisionnement Prévoyance.
    Direction Santé-Prévoyance · Équipe Prévoyance · Sous DIALLO.

    Refonte complète avec triangle ITT et méthodes actuarielles standards :
    Chain Ladder + Mack (1993) + BF (LR CTIP) + Bootstrap ODP.
    PM Rentes IP conservées (méthode actuarielle vie, correcte).
    """

    NOM     = "Élodie"
    CODE    = "P3"
    VERSION = "3.0"
    MANAGER = "Diallo (Équipe Prévoyance)"

    def __init__(
        self,
        models_path: str = "models",
        audit_path:  str = "audit",
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
        annees_debut:       Optional[int]         = None,
        primes_par_an:      Optional[np.ndarray]  = None,
        lr_manuel:          Optional[float]        = None,
        taux_actualisation: float                  = TAUX_ACT_RFR,
        n_sim_bootstrap:    int                    = N_SIM_BOOTSTRAP,
        generer_graphiques: bool                   = True,
    ) -> Dict:
        """
        Paramètres
        ----------
        result_p1         : dict — résultat P1 Axel (requis)
        result_p2         : dict — résultat P2 Rayan (requis)
        triangle_itt      : np.ndarray shape (n, m) — triangle cumulé ITT
                            optionnel. Si absent, triangle synthétique généré
                            depuis les données P1/P2 (cadences CTIP).
        annees_debut      : int — première année de survenance (ex: 2020)
        primes_par_an     : np.ndarray — primes par année (pour BF conforme S2)
        lr_manuel         : float — LR a priori manuel (prioritaire)
        taux_actualisation: float — taux PM Rentes IP (défaut : RFR 2.5%)
        n_sim_bootstrap   : int — simulations Bootstrap ODP
        generer_graphiques: bool
        """
        t0  = datetime.now()
        aid = f"P3_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # ── 1. EXTRACTION P1 + P2 ────────────────────────────────────────
            src = self._extraire(result_p1, result_p2, taux_actualisation)
            self.logger.info(
                f"[{aid}] P3 v{self.VERSION} | "
                f"PA={src['primes_acquises']:,.0f}€ | "
                f"{src['nb_assures']} assuré(s) | "
                f"taux_ip={src['taux_ip']:.4f}"
            )

            # ── 2. TRIANGLE ITT ───────────────────────────────────────────────
            C_itt, meta = self._preparer_triangle_itt(triangle_itt, src, annees_debut)
            n_ann, n_per = C_itt.shape
            self.logger.info(
                f"[{aid}] Triangle ITT {n_ann}x{n_per} | "
                f"mode={meta['mode']} | "
                f"ultime={meta['ultime_observe']:,.0f}E"
            )

            # ── 3. HYPOTHÈSES H1-H4 ──────────────────────────────────────────
            h = self._tester_hypotheses(C_itt, primes_par_an, lr_manuel)

            # ── 4. CHAIN LADDER ───────────────────────────────────────────────
            cl = self._chain_ladder(C_itt, h['methode_cl'])

            # ── 5. MACK 1993 ─────────────────────────────────────────────────
            mack = self._mack_1993(C_itt, cl['facteurs'], cl['facteurs_indiv'], cl)

            # ── 6. BORNHUETTER-FERGUSON ───────────────────────────────────────
            bf = self._bornhuetter_ferguson(
                C_itt, cl['pct_developpe'], cl['last_diagonale'],
                cl['ultimates'], primes_par_an, lr_manuel
            )

            # ── 7. BOOTSTRAP ODP ──────────────────────────────────────────────
            boot = self._bootstrap_odp(C_itt, cl['facteurs'], n_sim_bootstrap)

            # ── 8. BACK-TESTING ───────────────────────────────────────────────
            bt = self._backtesting(C_itt, annees_debut)

            # ── 9. BEST ESTIMATE ITT ─────────────────────────────────────────
            be_itt = self._best_estimate_itt(h, cl, mack, bf, boot)

            # ── 10. PM RENTES IP ─────────────────────────────────────────────
            pm_rentes = self._calculer_pm_rentes_ip(src)

            # ── 11. PSAP IP ───────────────────────────────────────────────────
            psap_ip = self._calculer_psap_ip(src)

            # ── 12. PREC ─────────────────────────────────────────────────────
            prec = self._calculer_prec(src, be_itt['be'])

            # ── 13. TOTAUX ────────────────────────────────────────────────────
            be_total = be_itt['be'] + pm_rentes + psap_ip
            scr      = self._calculer_scr(be_total, be_itt['be'])
            risk_adj = self._calculer_risk_adjustment(be_total)
            tp_prev  = be_total + risk_adj
            prov_tot = be_total + prec
            lr       = src['sinistres_payes_total'] / max(src['primes_acquises'], 1)
            taux_prov = prov_tot / max(src['primes_acquises'], 1)

            # ── 14. HYPOTHÈSES FINALES + RAG ─────────────────────────────────
            hyp = self._construire_hypotheses_sortie(h, be_itt, mack, bt, lr)
            rag = self._rag(hyp, be_itt, lr)

            # ── 15. COMMENTAIRE ───────────────────────────────────────────────
            com = self._commentaire(
                rag, src, C_itt, meta, h, cl, mack, bf, boot, bt,
                be_itt, pm_rentes, psap_ip, prec, be_total, risk_adj,
                tp_prev, prov_tot, lr, taux_prov, scr, hyp, aid
            )

            # ── 16. GRAPHIQUES ────────────────────────────────────────────────
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

                # Triangle ITT
                "triangle_meta":  meta,
                "n_annees":       n_ann,
                "n_periodes":     n_per,

                # Méthodes actuarielles
                "chain_ladder": {
                    "reserve_totale":   round(cl['reserve_totale'], 2),
                    "facteurs":         cl['facteurs'],
                    "facteurs_cumules": cl['facteurs_cumules'],
                    "ultimates":        cl['ultimates'],
                    "ibnr_par_annee":   cl['ibnr_par_annee'],
                    "pct_developpe":    cl['pct_developpe'],
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
                    "reserve_totale":  round(bf['reserve_totale'], 2),
                    "lr_apriori":      bf['lr_apriori'],
                    "source_lr":       bf['source_lr'],
                },
                "bootstrap":  boot,
                "backtesting": bt,

                # Best Estimate ITT
                "be_itt":         round(be_itt['be'], 2),
                "be_itt_detail":  be_itt,

                # Provisions long terme
                "pm_rentes_ip":   round(pm_rentes, 2),
                "psap_ip":        round(psap_ip, 2),
                "prec":           round(prec, 2),

                # Totaux
                "be_prevoyance":     round(be_total, 2),
                "risk_adjustment":   round(risk_adj, 2),
                "tp_prevoyance":     round(tp_prev, 2),
                "provision_totale":  round(prov_tot, 2),
                "loss_ratio":        round(lr, 4),
                "taux_provisionnement": round(taux_prov, 4),

                # SCR NSLT sous-cat 2
                "scr": scr,

                # Sorties vers P4 Valentin
                "sorties_p4": {
                    "be_prevoyance":    round(be_total, 2),
                    "risk_adjustment":  round(risk_adj, 2),
                    "tp_prevoyance":    round(tp_prev, 2),
                    "be_itt":           round(be_itt['be'], 2),
                    "pm_rentes_ip":     round(pm_rentes, 2),
                    "psap_ip":          round(psap_ip, 2),
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
    #  1. EXTRACTION P1 + P2
    # =========================================================================

    def _extraire(self, result_p1, result_p2, taux_act: float) -> Dict:
        """Extrait et consolide les données de P1 et P2."""
        if not result_p1 or not result_p1.get("success"):
            raise ValueError("result_p1 requis et success=True")
        if not result_p2 or not result_p2.get("success"):
            raise ValueError("result_p2 requis et success=True")

        p3_data = result_p2.get("sorties_p3", {})

        pa        = float(result_p1.get("primes_acquises",
                   p3_data.get("primes_acquises", 500_000)))
        nb        = int(p3_data.get("nb_assures", result_p1.get("nb_assures", 1)))
        sal       = float(p3_data.get("salaire_brut", result_p1.get("salaire_brut", 45_000)))
        age       = float(p3_data.get("age", result_p1.get("age", 40)))
        taux_ip   = float(p3_data.get("taux_ip", 0.0028))
        taux_itt  = float(p3_data.get("taux_itt", 0.042))
        franchise = int(p3_data.get("franchise_jours", 90))
        taux_rente = float(p3_data.get("taux_rente_ipp",
                    result_p1.get("taux_rente_ipp", 0.60)))
        dur_ip    = float(p3_data.get("esperance_duree_ip",
                   p3_data.get("esperance_duree_ip_ans", 20.0)))
        maint_6m  = float(p3_data.get("prob_maintien_6m", 0.40))
        maint_12m = float(p3_data.get("prob_maintien_12m", 0.25))
        maint_24m = float(p3_data.get("prob_maintien_24m", 0.12))

        taux_cot = float(result_p1.get("taux_cotisation_pct", 2.0)) / 100
        lr_att   = taux_cot * 0.80   # portion sinistres ~80% de la cotisation
        sin_tot  = pa * lr_att
        sin_itt  = sin_tot * 0.65    # ITT ~65% de la sinistralité prévoyance
        sin_ip   = sin_tot * 0.35    # IP ~35%

        return {
            "primes_acquises":       pa,
            "nb_assures":            nb,
            "salaire_brut":          sal,
            "age":                   age,
            "taux_ip":               taux_ip,
            "taux_itt":              taux_itt,
            "franchise_jours":       franchise,
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
    #  2. TRIANGLE ITT
    # =========================================================================

    def _preparer_triangle_itt(
        self,
        triangle_fourni: Optional[np.ndarray],
        src: Dict,
        annees_debut: Optional[int],
    ) -> Tuple[np.ndarray, Dict]:
        """
        Prépare le triangle ITT.

        Si un triangle réel est fourni (cumulatif n×m), il est utilisé directement.
        Sinon, génère un triangle synthétique calibré sur P1/P2 + cadences CTIP.

        Note : le triangle synthétique permet de démontrer la mécanique CL/Mack
        mais doit être remplacé par des données réelles pour un provisionnement
        S2 conforme.
        """
        if triangle_fourni is not None:
            C = np.array(triangle_fourni, dtype=float)
            if C.ndim != 2 or C.shape[0] < 3 or C.shape[1] < 3:
                raise ValueError(
                    f"triangle_itt doit être un tableau 2D de dimensions >= 3x3. "
                    f"Recu : {C.shape}"
                )
            C      = np.maximum(C, 0.0)
            n, m   = C.shape
            ultime = float(np.max(C))
            mode   = "reel"
        else:
            C, ultime = self._generer_triangle_synthetique(src)
            n, m      = C.shape
            mode      = "synthetique (CTIP 2023)"
            self.logger.warning(
                "Triangle ITT synthetique genere depuis P1/P2. "
                "Fournir un triangle reel pour un provisionnement S2 conforme."
            )

        an_debut   = annees_debut or (datetime.now().year - n + 1)
        labels     = [str(an_debut + i) for i in range(n)]
        per_labels = [f"S{j+1}" for j in range(m)]

        meta = {
            "mode":            mode,
            "n_annees":        n,
            "n_periodes":      m,
            "annee_debut":     an_debut,
            "annee_fin":       an_debut + n - 1,
            "labels_annees":   labels,
            "labels_periodes": per_labels,
            "ultime_observe":  ultime,
            "dimensions":      f"{n}x{m} (semestres)",
            "note": (
                "Triangle ITT en semestres. "
                "Zone connue : C[i,j] disponible si i+j < n."
            ),
        }

        return C, meta

    def _generer_triangle_synthetique(self, src: Dict) -> Tuple[np.ndarray, float]:
        """
        Génère un triangle ITT synthétique 5x5 calibré sur P1/P2 + CTIP 2023.

        Structure triangulaire stricte : C[i,j] = 0 pour i+j >= n.
        Bruit aléatoire contrôlé (seed=42 pour reproductibilité).
        """
        np.random.seed(42)
        n = 5; m = 5

        vol_total = src["sinistres_payes_itt"]
        if vol_total <= 0:
            vol_total = src["primes_acquises"] * LR_CTIP_ITT_MARCHE * 0.65

        # Volume par année (croissance 2%/an)
        vol_par_an = np.array([
            vol_total * (1 + 0.02 * (i - n // 2)) / n for i in range(n)
        ])
        vol_par_an = np.maximum(vol_par_an, vol_total * 0.05)

        # Cadences calibrées sur la courbe de maintien P2 + CTIP
        m6  = src.get("prob_maintien_6m", 0.40)
        fac = 1 + (m6 - 0.40) * 0.3
        cadences = np.array([0.45 / fac, 0.72 / fac, 0.87, 0.95, 1.00])
        cadences = np.clip(cadences, 0.05, 1.0)
        cadences[-1] = 1.0
        for j in range(1, m):
            cadences[j] = max(cadences[j], cadences[j-1] + 0.01)

        # Construction du triangle cumulatif
        C = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                if i + j < n:
                    th   = vol_par_an[i] * cadences[j]
                    bruit = 1 + np.random.normal(0, 0.05)
                    C[i, j] = max(th * bruit, th * 0.80)

        # Forcer la cumulativité
        for i in range(n):
            for j in range(1, m):
                if i + j < n:
                    C[i, j] = max(C[i, j], C[i, j-1] * 1.001)

        return C, float(np.max(C))

    # =========================================================================
    #  3. HYPOTHÈSES H1-H4
    # =========================================================================

    def _tester_hypotheses(
        self,
        C: np.ndarray,
        primes: Optional[np.ndarray],
        lr_manuel: Optional[float],
    ) -> Dict:
        """
        Valide les 4 hypothèses actuarielles du triangle ITT.

        H1 — Indépendance (Spearman) — seuil=0.50 (identique A7)
        H2 — Stabilité facteurs CL — CV<=20%, dérive<=25% (seuils ITT élargis)
        H3 — A priori BF vs LR CTIP 2023 — plage [55%, 85%]
        H4 — Homoscédasticité Bootstrap ODP (England & Verrall 2002)
        """
        n, m    = C.shape
        alertes = []
        infos   = []

        h1 = self._tester_h1(C, alertes, infos)
        h2 = self._tester_h2(C, alertes, infos, seuil_cv=0.20, seuil_derive=0.25)
        h3 = self._tester_h3(C, primes, lr_manuel, alertes, infos)
        h4 = self._tester_h4(C, alertes, infos)

        methode_cl               = self._choisir_variante_cl(h1, h2)
        methode_rec, raison_rec  = self._recommander_methode(h1, h2, h3, n)

        if not h1["ok"] and not h2["ok"]:
            statut = "ROUGE"
        elif not h1["ok"] or not h2["ok"]:
            statut = "AMBRE"
        else:
            statut = "VERT"

        return {
            "h1_independance":       h1,
            "h2_stabilite":          h2,
            "h3_apriori_bf":         h3,
            "h4_homosc_bootstrap":   h4,
            "methode_cl":            methode_cl,
            "methode_recommandee":   methode_rec,
            "raison_recommandation": raison_rec,
            "statut_global":         statut,
            "alertes":               alertes,
            "infos":                 infos,
        }

    def _tester_h1(self, C: np.ndarray, alertes: list, infos: list) -> Dict:
        """H1 — Indépendance des colonnes ITT (test de Spearman)."""
        n, m  = C.shape
        seuil = 0.50
        corrs = []
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
                        "colonnes":     f"S{j+1}->S{j+2}",
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
                "message": "H1 non testable — trop peu de donnees (< 4 obs par colonne).",
                "details": [],
            }

        corr_moy = float(np.mean(corrs))
        corr_max = float(np.max(corrs))
        n_sig    = sum(1 for d in details if d["significatif"])
        ok       = corr_moy < seuil and n_sig <= 1
        score    = max(0, int((1 - corr_moy) * 100))

        if not ok:
            alertes.append(
                f"H1 Independance ITT : correlation Spearman moy={corr_moy:.2f} "
                f"(seuil={seuil:.2f}), {n_sig} paire(s) significative(s). "
                f"Effet epidemique ou sinistres seriels possible. BF recommande."
            )
            message = (
                f"H1 REJETEE — correlation Spearman moy={corr_moy:.2f}, "
                f"max={corr_max:.2f}. {n_sig} paire(s) de semestres montrent "
                f"une dependance significative. "
                f"En prevoyance ITT, cela peut refleter : (1) effet epidemique "
                f"(COVID, grippe) touchant plusieurs cohortes ; "
                f"(2) changement de franchise ou de remboursement SS ; "
                f"(3) evolution du mix contrats. "
                f"CL et Mack biaises — BF avec LR CTIP 2023 recommande."
            )
        else:
            infos.append(f"H1 Independance ITT validee (corr_moy={corr_moy:.2f})")
            message = (
                f"H1 VALIDEE — correlation Spearman moy={corr_moy:.2f} < {seuil:.2f}. "
                f"Les annees de survenance ITT sont independantes. "
                f"Pas d'effet epidemique ou de sinistres seriels detecte. "
                f"Chain Ladder approprie pour ce triangle."
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

    def _tester_h2(
        self,
        C: np.ndarray,
        alertes: list,
        infos: list,
        seuil_cv: float = 0.20,
        seuil_derive: float = 0.25,
    ) -> Dict:
        """H2 — Stabilite des facteurs de developpement ITT."""
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
                    "semestre":  f"S{j+1}->S{j+2}",
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
                "message": "H2 non testable — trop peu de donnees.",
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
                f"H2 Stabilite ITT : CV moyen = {cv_moy:.1%} "
                f"(seuil prevoyance = {seuil_cv:.0%}). Variante mediane recommandee."
            )
        if not ok_derive:
            alertes.append(
                f"H2 Derive ITT : derive temporelle = {derive_moy:.1%} "
                f"(seuil = {seuil_derive:.0%}). Variante volume_weighted recommandee."
            )
        if ok:
            infos.append(
                f"H2 Stabilite ITT validee — CV={cv_moy:.1%} < {seuil_cv:.0%}, "
                f"derive={derive_moy:.1%} < {seuil_derive:.0%}"
            )

        message = (
            f"H2 {'VALIDEE' if ok else 'REJETEE'} — "
            f"CV moy={cv_moy:.1%} (seuil ITT {seuil_cv:.0%}), "
            f"derive={derive_moy:.1%} (seuil {seuil_derive:.0%}). "
            + (
                "Les facteurs de developpement ITT sont stables dans le temps."
                if ok else
                "Les facteurs ITT montrent une instabilite ou une derive. "
                "Seuils prevoyance (CV<=20%, derive<=25%) plus larges que Non-Vie."
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

    def _tester_h3(
        self,
        C: np.ndarray,
        primes: Optional[np.ndarray],
        lr_manuel: Optional[float],
        alertes: list,
        infos: list,
    ) -> Dict:
        """
        H3 — A priori BF : LR a priori vs benchmark CTIP 2023.

        Trois sources (par ordre de priorite) :
        1. LR fourni manuellement (lr_manuel)
        2. LR calcule depuis les primes fournies (primes_par_an)
        3. LR estime par proxy (S1 ≈ 30% des primes, CTIP reference)

        Reference externe : LR_CTIP_ITT_MARCHE = 68%
        Plage acceptable : [55%, 85%]
        """
        n, m      = C.shape
        lr_ref    = LR_CTIP_ITT_MARCHE
        lr_src    = "CTIP 2023 — Prevoyance collective"
        nb_matures = min(3, n - 1)

        # Cas 0 : LR manuel prioritaire
        if lr_manuel is not None and lr_manuel > 0:
            ok    = LR_CTIP_ITT_MIN <= lr_manuel <= LR_CTIP_ITT_MAX
            score = 85 if ok else 50
            ecart = abs(lr_manuel - lr_ref)
            if ecart > 0.20:
                alertes.append(
                    f"H3 LR manuel = {lr_manuel:.1%} vs CTIP = {lr_ref:.1%} "
                    f"(ecart {ecart:.0%}). Documenter la justification."
                )
            return {
                "ok": ok, "score": score,
                "lr_apriori":       round(lr_manuel, 4),
                "lr_std":           0.0, "cv_lr": 0.0,
                "source":           "manuel",
                "lr_reference":     lr_ref, "lr_reference_src": lr_src,
                "message": (
                    f"H3 A priori ITT : LR manuel = {lr_manuel:.1%}. "
                    f"Reference CTIP 2023 = {lr_ref:.1%}. "
                    f"Plage [{LR_CTIP_ITT_MIN:.0%}, {LR_CTIP_ITT_MAX:.0%}]. "
                    f"LR {'dans' if ok else 'hors'} plage CTIP."
                ),
            }

        # Cas 1 : primes fournies
        if primes is not None and len(primes) >= nb_matures:
            lr_an = []
            for i in range(nb_matures):
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
                        f"H3 LR ITT = {lr_moy:.1%} vs CTIP marche = {lr_ref:.1%}. "
                        f"Ecart {abs(lr_moy - lr_ref):.0%}."
                    )

                return {
                    "ok": ok, "score": score,
                    "lr_apriori":       round(lr_moy, 4),
                    "lr_std":           round(lr_std, 4),
                    "cv_lr":            round(cv_lr, 4),
                    "source":           "primes_fournies",
                    "nb_matures":       nb_matures,
                    "lr_reference":     lr_ref,
                    "lr_reference_src": lr_src,
                    "message": (
                        f"H3 {'VALIDEE' if ok else 'A VERIFIER'} — "
                        f"LR ITT = {lr_moy:.1%} (CV={cv_lr:.1%}, {nb_matures} annees matures). "
                        f"Reference CTIP 2023 = {lr_ref:.1%}. "
                        f"Plage [{LR_CTIP_ITT_MIN:.0%}, {LR_CTIP_ITT_MAX:.0%}]."
                    ),
                }

        # Cas 2 : proxy sans primes (S1 ≈ 30% des primes, hypothèse CTIP)
        lr_proxy_vals = []
        for i in range(nb_matures):
            c0   = float(C[i, 0])
            last = min(n - i - 1, m - 1)
            cu   = float(C[i, last])
            if c0 > 0 and cu > 0:
                prime_proxy = c0 / 0.30
                lr_proxy_vals.append(cu / prime_proxy)

        lr_proxy = float(np.mean(lr_proxy_vals)) if lr_proxy_vals else lr_ref
        ok       = LR_CTIP_ITT_MIN <= lr_proxy <= LR_CTIP_ITT_MAX
        score    = 55

        alertes.append(
            f"H3 A priori ITT proxy : primes non fournies. "
            f"LR estime = {lr_proxy:.1%} (hypothese : S1 ≈ 30% des primes). "
            f"Reference CTIP 2023 = {lr_ref:.1%}. "
            f"Fournir primes_par_an pour un BF conforme S2."
        )

        return {
            "ok": ok, "score": score,
            "lr_apriori":       round(lr_proxy, 4),
            "lr_std":           0.0, "cv_lr": 0.0,
            "source":           "proxy_sans_primes",
            "lr_reference":     lr_ref,
            "lr_reference_src": lr_src,
            "message": (
                f"H3 ESTIMEE (proxy sans primes) — "
                f"LR ITT proxy = {lr_proxy:.1%} (hypothese S1 ≈ 30% des primes). "
                f"Reference CTIP 2023 = {lr_ref:.1%}. "
                f"Approximation — fournir primes_par_an pour BF conforme S2."
            ),
        }

    def _tester_h4(self, C: np.ndarray, alertes: list, infos: list) -> Dict:
        """H4 — Homocedasticite Bootstrap ODP (England & Verrall 2002)."""
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
                arr  = np.array(facteurs)
                w    = np.array(poids)
                moy  = float(np.average(arr, weights=w))
                var  = float(np.average((arr - moy) ** 2, weights=w))
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
                f"H4 Homocedasticite ITT : CV variances = {cv_var:.2f} > 1.0. "
                f"Bootstrap ODP moins fiable. Preferer percentiles Mack pour le SCR S2."
            )
            message = (
                f"H4 HETEROCEDASTICITE ITT detectee — CV variances = {cv_var:.2f}. "
                f"Bootstrap ODP fournit des intervalles approximatifs. "
                f"Utiliser percentiles Mack (log-normale QIS5) pour le SCR S2."
            )
        else:
            infos.append(f"H4 Homocedasticite ITT validee (CV var={cv_var:.2f}, phi={phi:.6f})")
            message = (
                f"H4 VALIDEE — CV variances = {cv_var:.2f} < 1.0, phi={phi:.6f}. "
                f"Bootstrap ODP fiable pour ce triangle ITT."
            )

        return {
            "ok":     ok,
            "score":  score,
            "phi":    round(phi, 6),
            "cv_var": round(cv_var, 3),
            "message": message,
        }

    def _choisir_variante_cl(self, h1: Dict, h2: Dict) -> str:
        """Choix variante CL selon H1/H2 — meme logique que A7 Ibrahim."""
        h1_ok  = h1.get("ok", True)
        h2_ok  = h2.get("ok", True)
        cv     = h2.get("cv_moy", 0.0)
        derive = h2.get("derive_moy", 0.0)
        if h1_ok and h2_ok:
            return "standard"
        if not h2_ok and derive > 0.25 and cv <= 0.25:
            return "volume_weighted"
        if not h2_ok and cv > 0.25:
            return "mediane"
        if not h2_ok and cv > 0.20:
            return "trimmed_mean"
        if not h1_ok:
            return "volume_weighted"
        return "standard"

    def _recommander_methode(self, h1: Dict, h2: Dict, h3: Dict, n: int) -> Tuple[str, str]:
        """Recommande la methode principale avec justification."""
        if n < 4:
            return "bornhuetter_ferguson", (
                f"Triangle trop petit ({n} annees). BF avec LR CTIP 2023 recommande."
            )
        if h1["ok"] and h2["ok"]:
            return "mack_1993", (
                "H1 et H2 validees. Mack 1993 retenu pour la quantification de l'incertitude S2."
            )
        if not h1["ok"] and h3["score"] >= 60:
            return "bornhuetter_ferguson", (
                f"H1 REJETEE (corr={h1['corr_moy']:.2f}). "
                f"BF recommande : ancrage sur LR CTIP independant des correlations du triangle ITT."
            )
        return "bornhuetter_ferguson", (
            "H1 ou H2 rejetee. BF avec LR CTIP 2023 recommande."
        )

    # =========================================================================
    #  4. CHAIN LADDER
    # =========================================================================

    def _chain_ladder(self, C: np.ndarray, methode: str = "standard") -> Dict:
        """
        Chain Ladder sur triangle ITT — meme implementation que A7 Ibrahim.

        Tail factor : 1.0 si dernier LDF < 1.05 (developpement complete a S5).
        Sinon extrapolation log-lineaire (Mack 1993).
        """
        n, m = C.shape

        # Facteurs de developpement
        facteurs     = np.ones(m - 1)
        facteurs_ind = []

        for j in range(m - 1):
            f_ind = []; c_j = []
            for i in range(n):
                if i + j + 1 >= n:
                    break
                cij  = float(C[i, j]); cij1 = float(C[i, j+1])
                if cij > 0 and cij1 > 0:
                    f_ind.append(cij1 / cij); c_j.append(cij)

            facteurs_ind.append(f_ind)

            if not f_ind:
                facteurs[j] = 1.0; continue

            arr = np.array(f_ind, dtype=float)
            w   = np.array(c_j,   dtype=float)

            if methode == "standard":
                facteurs[j] = float(np.average(arr, weights=w))
            elif methode == "volume_weighted":
                facteurs[j] = float(np.average(arr, weights=np.sqrt(w)))
            elif methode == "mediane":
                facteurs[j] = float(np.median(arr))
            elif methode == "trimmed_mean":
                if len(arr) >= 4:
                    q10 = np.percentile(arr, 10); q90 = np.percentile(arr, 90)
                    mask = (arr >= q10) & (arr <= q90)
                    facteurs[j] = float(np.mean(arr[mask])) if mask.sum() > 0 else float(np.mean(arr))
                else:
                    facteurs[j] = float(np.average(arr, weights=w))
            else:
                facteurs[j] = float(np.average(arr, weights=w))

            facteurs[j] = max(facteurs[j], 1.0)

        # Tail factor
        dernier_ldf = float(facteurs[-1]) if len(facteurs) > 0 else 1.0
        if dernier_ldf < 1.05:
            tail = 1.0
            tail_msg = (
                f"Tail factor = 1.0 — dernier LDF ITT = {dernier_ldf:.4f} < 1.05. "
                f"Developpement considere complet a la derniere periode semestrielle."
            )
        else:
            k = min(3, len(facteurs)); f_queue = facteurs[-k:]
            x = np.arange(k, dtype=float); eps = 1e-8
            log_f = np.log(np.maximum(f_queue - 1.0, eps))
            try:
                b, a = np.polyfit(x, log_f, 1)
                if b < 0:
                    tail = 1.0
                    for step in range(30):
                        f_ext = 1.0 + np.exp(a + b * (k + step))
                        if f_ext < 1.0 + 1e-4: break
                        tail *= f_ext
                    tail = float(np.clip(tail, 1.0, 1.10))
                else:
                    tail = 1.0
            except Exception:
                tail = 1.0
            tail_msg = f"Tail factor = {tail:.4f} applique — dernier LDF ITT = {dernier_ldf:.4f} >= 1.05."

        # Facteurs cumules
        f_cum = np.ones(m)
        f_cum[m-1] = tail
        for j in range(m - 2, -1, -1):
            f_cum[j] = facteurs[j] * f_cum[j+1]

        # % developpe
        pct_dev = np.ones(n)
        for i in range(n):
            k = min(n - i - 1, m - 1)
            if k < len(f_cum) and f_cum[k] > 0:
                pct_dev[i] = 1.0 / f_cum[k]
        pct_dev = np.clip(pct_dev, 0.0, 1.0)

        # Ultimates et IBNR
        ultimates = np.zeros(n); ibnr = np.zeros(n)
        last_diag = np.array([float(C[i, min(n-i-1, m-1)]) for i in range(n)])

        for i in range(n):
            k_i = min(n-i-1, m-1); val = float(C[i, k_i])
            for j in range(k_i, m-1):
                if j < len(facteurs): val *= facteurs[j]
            val *= tail
            ultimates[i] = val
            ibnr[i]      = max(val - last_diag[i], 0.0)

        reserve_totale = float(np.sum(ibnr[1:]))

        return {
            "facteurs":         [round(float(f), 6) for f in facteurs],
            "facteurs_cumules": [round(float(f), 6) for f in f_cum],
            "facteurs_indiv":   facteurs_ind,
            "tail_factor":      tail,
            "tail_message":     tail_msg,
            "ultimates":        [round(float(u), 2) for u in ultimates],
            "ibnr_par_annee":   [round(float(v), 2) for v in ibnr],
            "last_diagonale":   [round(float(d), 2) for d in last_diag],
            "pct_developpe":    [round(float(p), 4) for p in pct_dev],
            "reserve_totale":   round(reserve_totale, 2),
            "reserve_best_estimate": round(reserve_totale, 2),
            "methode":          f"Chain Ladder ITT ({methode})",
        }

    # =========================================================================
    #  5. MACK 1993
    # =========================================================================

    def _mack_1993(
        self, C: np.ndarray, facteurs: list,
        facteurs_indiv: list, cl: Dict,
    ) -> Dict:
        """
        Mack (1993) sur triangle ITT — extension stochastique du CL.

        Conforme a Mack (1993) ASTIN Bulletin 23(2), formules 3.4 et 3.5.
        Termes croises de variance inclus (Theorem 3).
        Percentiles log-normale QIS5 TP.5.26.
        """
        n, m      = C.shape
        f_arr     = np.array(facteurs, dtype=float)
        ultimates = np.array(cl["ultimates"], dtype=float)
        ibnr      = np.array(cl["ibnr_par_annee"], dtype=float)

        # sigma2_j par colonne (Mack 3.4)
        sigma2 = np.zeros(m - 1)
        for j in range(m - 1):
            f_ind = facteurs_indiv[j]; f_j = float(f_arr[j]); n_j = len(f_ind)
            if n_j < 2: continue
            c_j = []
            for i in range(n):
                if i + j + 1 < n and C[i, j] > 0 and C[i, j+1] > 0:
                    c_j.append(float(C[i, j]))
                if len(c_j) == n_j: break
            if len(c_j) < 2: continue
            num = sum(c_j[k] * (f_ind[k] - f_j)**2 for k in range(min(n_j, len(c_j))))
            sigma2[j] = num / (n_j - 1)

        # Extrapolation sigma2 manquants (Mack 3.5)
        if m > 2 and sigma2[1] == 0 and sigma2[0] > 0:
            sigma2[1] = sigma2[0]
        for j in range(2, m - 1):
            if sigma2[j] > 0: continue
            s1 = sigma2[j-1]; s2 = sigma2[j-2]
            if s1 > 0 and s2 > 0:
                sigma2[j] = min(s1, s2, s1**2 / s2)
            elif s1 > 0:
                sigma2[j] = s1

        # Volumes par colonne
        W = np.zeros(m - 1)
        for j in range(m - 1):
            for i in range(n):
                if i + j + 1 < n and C[i, j] > 0:
                    W[j] += C[i, j]

        # Variance par annee (Theorem 3)
        var_r = np.zeros(n)
        for i in range(1, n):
            k_i  = min(n-i-1, m-1); U_i = float(ultimates[i])
            if U_i <= 0: continue
            c_proj = float(C[i, k_i]); v = 0.0
            for j in range(k_i, m-1):
                if j >= len(f_arr) or j >= len(sigma2): break
                f_j = float(f_arr[j]); s2j = float(sigma2[j]); w_j = float(W[j])
                if f_j <= 0 or s2j <= 0:
                    c_proj *= max(f_j, 1.0); continue
                v   += s2j / (f_j**2) * (1.0/max(c_proj, 1e-10) + 1.0/max(w_j, 1e-10))
                c_proj *= f_j
            var_r[i] = (U_i**2) * v

        # Variance totale avec termes croises (Theorem 3)
        var_tot = float(np.sum(var_r[1:]))
        for i in range(1, n-1):
            for l in range(i+1, n):
                U_i = float(ultimates[i]); U_l = float(ultimates[l])
                if U_i <= 0 or U_l <= 0: continue
                k_l = min(n-l-1, m-1); s = 0.0
                for j in range(k_l, m-1):
                    if j >= len(f_arr) or j >= len(sigma2): break
                    f_j = float(f_arr[j]); s2j = float(sigma2[j]); w_j = float(W[j])
                    if f_j > 0 and s2j > 0 and w_j > 0:
                        s += s2j / (f_j**2 * w_j)
                var_tot += 2.0 * U_i * U_l * s
        var_tot = max(var_tot, 0.0)

        sigma_par_an = np.sqrt(np.maximum(var_r, 0.0))
        sigma_total  = float(np.sqrt(var_tot))
        reserve_be   = float(np.sum(ibnr[1:]))
        cv_pct       = sigma_total / max(reserve_be, 1e-9) * 100.0

        # Percentiles log-normale (QIS5 TP.5.26)
        if reserve_be > 0 and sigma_total > 0:
            cv_ln = sigma_total / reserve_be
            s2_ln = math.log(1.0 + cv_ln**2)
            s_ln  = math.sqrt(s2_ln)
            m_ln  = math.log(reserve_be) - s2_ln / 2.0
            p75   = float(np.exp(m_ln + 0.6745 * s_ln))
            p90   = float(np.exp(m_ln + 1.2816 * s_ln))
            p95   = float(np.exp(m_ln + 1.6449 * s_ln))
            p99_5 = float(np.exp(m_ln + 2.5758 * s_ln))
        else:
            p75 = p90 = p95 = p99_5 = reserve_be
            s_ln = m_ln = 0.0

        if cv_pct < 10.0:   statut = "VERT"
        elif cv_pct < 20.0: statut = "AMBRE"
        else:               statut = "ROUGE"

        msg = (
            f"Mack (1993) ITT : BE={reserve_be:,.0f}E | "
            f"sigma={sigma_total:,.0f}E | CV={cv_pct:.1f}% | "
            f"P90={p90:,.0f}E | P99.5={p99_5:,.0f}E | statut={statut}"
        )

        return {
            "reserve_best_estimate":  round(reserve_be,  2),
            "sigma_total":            round(sigma_total, 2),
            "var_totale":             round(var_tot,     4),
            "cv_pct":                 round(cv_pct,      2),
            "sigma_par_annee":        [round(float(s), 2) for s in sigma_par_an],
            "var_par_annee":          [round(float(v), 4) for v in var_r],
            "sigma2_par_colonne":     [round(float(s), 6) for s in sigma2],
            "reserve_p75":            round(p75,   2),
            "reserve_p90":            round(p90,   2),
            "reserve_p95":            round(p95,   2),
            "reserve_p99_5":          round(p99_5, 2),
            "mu_ln":                  round(m_ln,  6),
            "sigma_ln":               round(s_ln,  6),
            "statut":                 statut,
            "methode":                "Mack (1993) ITT — ASTIN Bulletin 23(2) · Log-normale QIS5 TP.5.26",
            "message":                msg,
        }

    # =========================================================================
    #  6. BORNHUETTER-FERGUSON
    # =========================================================================

    def _bornhuetter_ferguson(
        self, C: np.ndarray, pct_dev: list, last_diag: list,
        ultimates_cl: list, primes: Optional[np.ndarray],
        lr_manuel: Optional[float],
    ) -> Dict:
        """
        Bornhuetter-Ferguson (1972) sur triangle ITT.

        LR a priori : priorite lr_manuel > primes > CTIP reference.
        Reference externe : LR_CTIP_ITT_MARCHE = 68%.
        """
        n, m   = C.shape
        pct    = np.array(pct_dev, dtype=float)
        diag   = np.array(last_diag, dtype=float)
        ult_cl = np.array(ultimates_cl, dtype=float)
        alertes = []

        # Determiner le LR a priori
        if lr_manuel is not None and lr_manuel > 0:
            lr = float(np.clip(lr_manuel, 0.01, 3.0)); source = "manuel"
        elif primes is not None and len(primes) >= 2:
            lr_an = []
            for i in range(min(3, n-1)):
                p = float(primes[i]); u = float(ult_cl[i])
                if p > 0 and u > 0: lr_an.append(u / p)
            lr     = float(np.mean(lr_an)) if lr_an else LR_CTIP_ITT_MARCHE
            source = "primes_fournies"
        else:
            lr = LR_CTIP_ITT_MARCHE; source = "ctip_2023_reference"
            alertes.append(
                f"BF ITT : primes non fournies — LR a priori = {lr:.1%} (CTIP 2023 mediane)."
            )

        if abs(lr - LR_CTIP_ITT_MARCHE) > 0.15:
            alertes.append(
                f"BF ITT : LR = {lr:.1%} vs CTIP 2023 = {LR_CTIP_ITT_MARCHE:.1%}. "
                f"Ecart {abs(lr - LR_CTIP_ITT_MARCHE):.0%} — justifier dans la note."
            )

        lr = float(np.clip(lr, 0.01, 3.0))

        # mu[i] : sinistres attendus a priori
        if primes is not None and len(primes) >= n:
            mu = np.array([float(primes[i]) * lr for i in range(n)])
        else:
            mu = ult_cl * lr

        # IBNR BF
        ibnr_bf      = np.zeros(n)
        ultimates_bf = np.zeros(n)
        for i in range(n):
            frac            = max(1.0 - float(pct[i]), 0.0)
            ibnr_bf[i]      = frac * float(mu[i])
            ultimates_bf[i] = float(diag[i]) + ibnr_bf[i]

        reserve_totale = float(np.sum(ibnr_bf[1:]))

        return {
            "lr_apriori":            round(lr, 4),
            "source_lr":             source,
            "lr_reference_ctip":     LR_CTIP_ITT_MARCHE,
            "mu_par_annee":          [round(float(v), 2) for v in mu],
            "ibnr_par_annee":        [round(float(v), 2) for v in ibnr_bf],
            "ultimates":             [round(float(v), 2) for v in ultimates_bf],
            "reserve_totale":        round(reserve_totale, 2),
            "reserve_best_estimate": round(reserve_totale, 2),
            "alertes":               alertes,
            "methode":               "Bornhuetter-Ferguson (1972) — LR a priori CTIP 2023",
        }

    # =========================================================================
    #  7. BOOTSTRAP ODP
    # =========================================================================

    def _bootstrap_odp(
        self, C: np.ndarray, facteurs: list, n_sim: int = N_SIM_BOOTSTRAP,
    ) -> Dict:
        """
        Bootstrap ODP (England & Verrall 2002) sur triangle ITT.

        Algorithme identique a A7 Ibrahim :
        - Residus de Pearson sur zone connue
        - Ajustement degres de liberte
        - Simulation avec bruit de processus ODP
        """
        np.random.seed(42)
        n, m  = C.shape
        f_arr = np.array(facteurs, dtype=float)

        # Fitted values
        C_fit = np.zeros((n, m))
        for i in range(n):
            C_fit[i, 0] = C[i, 0]
            for j in range(1, m):
                if i + j < n and j-1 < len(f_arr) and C[i, j-1] > 0:
                    C_fit[i, j] = C[i, j-1] * f_arr[j-1]

        # Residus de Pearson
        cellules = []; residus = np.zeros((n, m))
        for i in range(n):
            for j in range(1, m):
                if i + j < n and C_fit[i, j] > 0 and C[i, j] > 0:
                    r = (C[i, j] - C_fit[i, j]) / np.sqrt(C_fit[i, j])
                    residus[i, j] = r; cellules.append((i, j))

        n_obs = len(cellules); n_params = n + (m-1); df = n_obs - n_params
        if df > 0:
            adj = np.sqrt(n_obs / df)
            for (i, j) in cellules: residus[i, j] *= adj

        # phi (sur-dispersion)
        r_bruts = np.array([
            (C[i, j] - C_fit[i, j]) / np.sqrt(C_fit[i, j])
            for (i, j) in cellules if C_fit[i, j] > 0
        ])
        phi = float(np.sum(r_bruts**2) / max(df, 1)) if len(r_bruts) > 0 else 0.0

        res_list = [residus[i, j] for (i, j) in cellules if residus[i, j] != 0]
        if len(res_list) < 4:
            reserve_cl = float(sum(
                max(float(C[i, min(n-i-1, m-1)]) * float(np.prod(f_arr[min(n-i-1, m-1):]))
                    - float(C[i, min(n-i-1, m-1)]), 0.0)
                for i in range(1, n)
            ))
            return self._bootstrap_degrade(reserve_cl, n_sim)

        res_arr   = np.array(res_list)
        last_diag = np.array([float(C[i, min(n-i-1, m-1)]) for i in range(n)])

        # Simulations
        reserves_sim = np.zeros(n_sim)
        for b in range(n_sim):
            idx = np.random.randint(0, len(res_arr), size=(n, m))
            res_boot = res_arr[idx]
            C_star = np.zeros((n, m))
            for i in range(n):
                C_star[i, 0] = max(C[i, 0], 1.0)
                for j in range(1, m):
                    if i + j < n and C_fit[i, j] > 0:
                        val = C_fit[i, j] + res_boot[i, j] * np.sqrt(C_fit[i, j])
                        C_star[i, j] = max(val, C_fit[i, j] * 0.01)
                        C_star[i, j] = max(C_star[i, j], C_star[i, j-1])

            f_star = np.ones(m-1)
            for j in range(m-1):
                num = den = 0.0
                for i in range(n):
                    if i + j + 1 < n and C_star[i, j] > 0 and C_star[i, j+1] > 0:
                        num += C_star[i, j+1]; den += C_star[i, j]
                f_star[j] = max(num / max(den, 1e-10), 1.0)

            reserve_b = 0.0
            for i in range(1, n):
                k_i = min(n-i-1, m-1); c_val = float(C[i, k_i])
                for j in range(k_i, m-1):
                    if j < len(f_star):
                        mean_next = c_val * f_star[j]
                        if phi > 0 and mean_next > 0:
                            std_proc = np.sqrt(phi * mean_next)
                            c_val = max(mean_next + np.random.normal(0, std_proc), mean_next * 0.01)
                        else:
                            c_val = mean_next
                reserve_b += max(c_val - last_diag[i], 0.0)
            reserves_sim[b] = reserve_b

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
            "p50":  round(float(np.percentile(reserves_sim, 50)),   2),
            "p75":  round(float(np.percentile(reserves_sim, 75)),   2),
            "p90":  round(float(np.percentile(reserves_sim, 90)),   2),
            "p95":  round(float(np.percentile(reserves_sim, 95)),   2),
            "p99_5": round(float(np.percentile(reserves_sim, 99.5)), 2),
            "ic_95_inf": round(float(np.percentile(reserves_sim, 2.5)),  2),
            "ic_95_sup": round(float(np.percentile(reserves_sim, 97.5)), 2),
            "phi": round(phi, 6), "n_obs": n_obs, "n_params": n_params,
            "df": df, "n_simulations": n_sim,
            "distribution": reserves_sim.tolist(),
            "statut": statut,
            "methode": "Bootstrap ODP — England & Verrall (2002)",
            "message": (
                f"Bootstrap ODP ITT : BE={be_boot:,.0f}E | sigma={std_boot:,.0f}E | "
                f"CV={cv_boot*100:.1f}% | P90={float(np.percentile(reserves_sim, 90)):,.0f}E | "
                f"phi={phi:.4f} | {n_sim} sim."
            ),
        }

    def _bootstrap_degrade(self, reserve_ref: float, n_sim: int) -> Dict:
        """Resultat degrade quand Bootstrap non fiable (triangle trop petit)."""
        return {
            "be_bootstrap":  round(reserve_ref, 2), "std_bootstrap": 0.0, "cv_bootstrap": 0.0,
            "p50": round(reserve_ref, 2), "p75": round(reserve_ref, 2),
            "p90": round(reserve_ref, 2), "p95": round(reserve_ref, 2),
            "p99_5": round(reserve_ref, 2),
            "ic_95_inf": round(reserve_ref, 2), "ic_95_sup": round(reserve_ref, 2),
            "phi": 0.0, "n_obs": 0, "n_params": 0, "df": 0,
            "n_simulations": n_sim, "distribution": [reserve_ref] * n_sim,
            "statut": "AMBRE", "methode": "Bootstrap ODP — England & Verrall (2002)",
            "message": "Bootstrap ODP ITT : triangle trop petit — residus insuffisants.",
        }

    # =========================================================================
    #  8. BACK-TESTING
    # =========================================================================

    def _backtesting(self, C: np.ndarray, annees_debut: Optional[int]) -> Dict:
        """
        Back-testing boni/mali sur triangle ITT (Guide IA 2023).

        Meme principe qu'A7 Ibrahim : ultimates projetees N-1 et N-2 vs observe.
        """
        n, m = C.shape
        if n < 4:
            return {
                "success": False,
                "erreur":  f"Triangle trop petit ({n} annees) — minimum 4 requis.",
                "tableau": [], "statut": "AMBRE", "score_qualite": 75,
                "n_rouge_n1": 0, "n_ambre_n1": 0,
                "n_rouge_n2": 0, "n_ambre_n2": 0,
                "message": "Back-testing ITT non disponible — triangle < 4 annees.",
            }

        SEUIL_ROUGE = 15.0; SEUIL_AMBRE = 8.0; SEUIL_MATURITE = 0.75

        def _cl_simple(tri):
            _n, _m = tri.shape
            obs    = np.where(np.isnan(tri), 0.0, tri)
            facts  = []
            for j in range(_m - 1):
                mask = (obs[:, j] > 0) & (obs[:, j+1] > 0)
                num  = float(np.sum(obs[mask, j+1])); den = float(np.sum(obs[mask, j]))
                facts.append(num / den if den > 0 else 1.0)
            f_cum = np.ones(_m)
            for j in range(_m-2, -1, -1):
                f_cum[j] = f_cum[j+1] * (facts[j] if j < len(facts) else 1.0)
            ults = np.zeros(_n)
            for i in range(_n):
                last_j = 0
                for j in range(_m-1, -1, -1):
                    if tri[i, j] > 0 and not np.isnan(tri[i, j]):
                        last_j = j; break
                ults[i] = tri[i, last_j] * f_cum[last_j] if f_cum[last_j] > 0 else tri[i, last_j]
            return ults

        def _ult_tronque(k):
            max_diag = max(
                (i + j for i in range(n) for j in range(m)
                 if not np.isnan(C[i, j]) and C[i, j] > 0), default=n-1
            )
            seuil_diag = max_diag - k
            if seuil_diag < 2: return np.zeros(n)
            C_t = C.copy().astype(float)
            C_t[np.add.outer(np.arange(n), np.arange(m)) > seuil_diag] = np.nan
            if int(np.sum(~np.isnan(C_t) & (C_t > 0))) < 6: return np.zeros(n)
            return _cl_simple(C_t)

        ult_n1 = _ult_tronque(1); ult_n2 = _ult_tronque(2)
        ult_full = _cl_simple(C.copy())
        obs_n = np.zeros(n); pct_dev = np.zeros(n)
        for i in range(n):
            for j in range(m-1, -1, -1):
                if C[i, j] > 0: obs_n[i] = float(C[i, j]); break
            pct_dev[i] = obs_n[i] / ult_full[i] if ult_full[i] > 0 else 0.0
        pct_dev = np.clip(pct_dev, 0.0, 1.0)

        tableau = []
        n_rouge_n1 = n_ambre_n1 = n_rouge_n2 = n_ambre_n2 = 0
        scores_n1 = []; scores_n2 = []
        an_debut = annees_debut or (datetime.now().year - n + 1)

        for i in range(n):
            obs   = float(obs_n[i]); u_n1 = float(ult_n1[i]); u_n2 = float(ult_n2[i])
            pct_i = float(pct_dev[i]); mature = pct_i >= SEUIL_MATURITE
            if obs <= 0: continue

            bm_n1 = round(u_n1 - obs, 0) if u_n1 > 0 else None
            bm_n2 = round(u_n2 - obs, 0) if u_n2 > 0 else None
            ep_n1 = round(bm_n1 / obs * 100, 1) if bm_n1 is not None else None
            ep_n2 = round(bm_n2 / obs * 100, 1) if bm_n2 is not None else None

            def _stat(ep):
                if ep is None or not mature: return None
                a = abs(ep)
                return "ROUGE" if a >= SEUIL_ROUGE else "AMBRE" if a >= SEUIL_AMBRE else "VERT"

            s1 = _stat(ep_n1); s2 = _stat(ep_n2)
            if mature:
                if s1 == "ROUGE": n_rouge_n1 += 1
                elif s1 == "AMBRE": n_ambre_n1 += 1
                if ep_n1 is not None: scores_n1.append(max(0, 100 - abs(ep_n1) * 2))
                if s2 == "ROUGE": n_rouge_n2 += 1
                elif s2 == "AMBRE": n_ambre_n2 += 1
                if ep_n2 is not None: scores_n2.append(max(0, 100 - abs(ep_n2) * 2))

            tableau.append({
                "annee": i, "annee_label": str(an_debut + i),
                "observe_n": round(obs, 0),
                "ultimate_n1": round(u_n1, 0) if u_n1 > 0 else None,
                "ultimate_n2": round(u_n2, 0) if u_n2 > 0 else None,
                "boni_mali_n1": bm_n1, "boni_mali_n2": bm_n2,
                "ecart_pct_n1": ep_n1, "ecart_pct_n2": ep_n2,
                "statut_n1": s1, "statut_n2": s2,
                "pct_developpe": round(pct_i * 100, 1), "mature": mature,
            })

        score_n1 = round(float(np.mean(scores_n1)), 1) if scores_n1 else 100.0
        score_n2 = round(float(np.mean(scores_n2)), 1) if scores_n2 else 100.0
        score    = round((score_n1 + score_n2) / 2, 1)
        n_rouge  = max(n_rouge_n1, n_rouge_n2); n_ambre = max(n_ambre_n1, n_ambre_n2)

        if n_rouge >= 1:   statut = "ROUGE"
        elif n_ambre >= 1: statut = "AMBRE"
        else:              statut = "VERT"

        n_matures = sum(1 for r in tableau if r["mature"])
        msg = (
            f"Back-testing ITT — {n_matures} annees matures sur {n}. "
            f"N-1 : {n_rouge_n1} rouge | {n_ambre_n1} ambre — Score {score_n1}/100. "
            f"N-2 : {n_rouge_n2} rouge | {n_ambre_n2} ambre — Score {score_n2}/100."
        )

        return {
            "success": True, "tableau": tableau, "statut": statut,
            "score_qualite": score, "score_n1": score_n1, "score_n2": score_n2,
            "n_rouge_n1": n_rouge_n1, "n_ambre_n1": n_ambre_n1,
            "n_rouge_n2": n_rouge_n2, "n_ambre_n2": n_ambre_n2,
            "n_matures": n_matures, "message": msg,
        }

    # =========================================================================
    #  9. BEST ESTIMATE ITT
    # =========================================================================

    def _best_estimate_itt(
        self, h: Dict, cl: Dict, mack: Dict, bf: Dict, boot: Dict
    ) -> Dict:
        """
        Best Estimate ITT = moyenne ponderee des methodes.

        Poids selon scores H1-H4 (comme A7 Ibrahim N4).
        Methode recommandee : poids minimum 50%.
        Percentiles : Bootstrap si disponible, sinon Mack.
        """
        rec = h.get("methode_recommandee", "bornhuetter_ferguson")
        h1s = h["h1_independance"]["score"]
        h2s = h["h2_stabilite"]["score"]
        h3s = h["h3_apriori_bf"]["score"]
        h4s = h["h4_homosc_bootstrap"]["score"]

        score_cl   = int(h1s * 0.50 + h2s * 0.50)
        score_mack = int(h1s * 0.50 + h2s * 0.30 + h4s * 0.20)
        score_bf   = int(h1s * 0.20 + h2s * 0.20 + h3s * 0.60)

        reserves = {
            "chain_ladder":         (cl["reserve_totale"],         score_cl),
            "mack_1993":            (mack["reserve_best_estimate"], score_mack),
            "bornhuetter_ferguson": (bf["reserve_totale"],          score_bf),
        }

        SEUIL_SCORE = 55
        incluses = {m: (r, s) for m, (r, s) in reserves.items() if s >= SEUIL_SCORE and r > 0}
        if not incluses:
            incluses = {
                "mack_1993":            (mack["reserve_best_estimate"], 50),
                "bornhuetter_ferguson": (bf["reserve_totale"],          50),
            }

        _rec_map = {
            "mack_1993": "mack_1993", "mack": "mack_1993",
            "chain_ladder": "chain_ladder",
            "bornhuetter_ferguson": "bornhuetter_ferguson", "bf": "bornhuetter_ferguson",
        }
        rec_norm = _rec_map.get(rec.lower().replace(" ", "_").replace("-", "_"), "")

        tot_s       = sum(s for _, s in incluses.values())
        poids_bruts = {m: s / max(tot_s, 1) for m, (_, s) in incluses.items()}

        if rec_norm and rec_norm in incluses:
            POIDS_MIN  = 0.50
            poids_rec  = max(poids_bruts.get(rec_norm, 0), POIDS_MIN)
            reste      = 1.0 - poids_rec
            autres     = {m: v for m, v in poids_bruts.items() if m != rec_norm}
            tot_autres = sum(autres.values())
            poids      = {rec_norm: round(poids_rec, 4)}
            if tot_autres > 0:
                for m, v in autres.items(): poids[m] = round(v / tot_autres * reste, 4)
            else:
                poids = {rec_norm: 1.0}
        else:
            poids = {m: round(v, 4) for m, v in poids_bruts.items()}

        tot_poids = sum(poids.values())
        if tot_poids > 0:
            poids = {m: round(v / tot_poids, 4) for m, v in poids.items()}

        be    = float(sum(poids[m] * r for m, (r, _) in incluses.items()))
        vals  = [r for r, _ in incluses.values()]
        cv_im = float(np.std(vals) / max(np.mean(vals), 1e-9) * 100) if len(vals) > 1 else 0.0

        boot_ok = bool(boot.get("be_bootstrap", 0) > 0)
        if boot_ok:
            p75 = float(boot.get("p75",   mack["reserve_p75"]))
            p90 = float(boot.get("p90",   mack["reserve_p90"]))
            p99 = float(boot.get("p99_5", mack["reserve_p99_5"]))
            src_pcts = "Bootstrap ODP"
        else:
            p75 = mack["reserve_p75"]; p90 = mack["reserve_p90"]
            p99 = mack["reserve_p99_5"]; src_pcts = "Mack 1993"

        return {
            "be":               round(be, 2),
            "cv_inter":         round(cv_im, 2),
            "methodes_incluses": list(incluses.keys()),
            "poids":            poids,
            "methode_rec":      rec_norm or rec,
            "p75":              round(p75, 2),
            "p90":              round(p90, 2),
            "p99_5":            round(p99, 2),
            "source_percentiles": src_pcts,
        }

    # =========================================================================
    #  10. PM RENTES IP (inchangee — methode actuarielle vie)
    # =========================================================================

    def _calculer_pm_rentes_ip(self, src: Dict) -> float:
        """
        PM Rentes IP = provision mathematique actualisee.

        Methode vie correcte (inchangee vs v2) :
        PM = nb_invalides x rente_annuelle x annuite_actualisee

        Correction v3.0 : suppression du facteur age/10 inverse (bug P3 v2).
        nb_inv = nb_assures x taux_ip x 0.60 (60% en rente viagere)
        """
        rente_an = src["salaire_brut"] * src["taux_rente_ipp"]
        dur_ip   = src["duree_ip_ans"]
        taux_act = src["taux_actualisation"]
        v        = 1.0 / (1 + taux_act)
        annuite  = sum(v**t for t in range(1, int(dur_ip) + 1))
        # Formule corrigee v3.0 : age/10 supprime (direction inversee en v2)
        nb_inv   = max(0, int(src["nb_assures"] * src["taux_ip"] * 0.60))
        return nb_inv * rente_an * annuite

    # =========================================================================
    #  11. PSAP IP
    # =========================================================================

    def _calculer_psap_ip(self, src: Dict) -> float:
        """PSAP IP = dossiers en phase de constitution d'invalidite."""
        rente_men = src["salaire_brut"] * src["taux_rente_ipp"] / 12
        nb_cons   = max(1, int(src["nb_assures"] * src["taux_ip"] * 2))
        return nb_cons * rente_men * 6

    # =========================================================================
    #  12. PREC
    # =========================================================================

    def _calculer_prec(self, src: Dict, be_itt: float) -> float:
        """PREC prevoyance = max(0, PA x max(0, ratio_combine - 1))."""
        lr = src["sinistres_payes_total"] / max(src["primes_acquises"], 1)
        rc = lr + 0.20   # chargements prevoyance ~20%
        return max(0.0, src["primes_acquises"] * max(0.0, rc - 1.0))

    # =========================================================================
    #  13. SCR NSLT SOUS-CAT 2
    # =========================================================================

    def _calculer_scr(self, be_total: float, be_itt: float) -> Dict:
        """
        SCR NSLT sous-categorie 2 — Protection du revenu / ITT.

        Source : Annexe II, Reglement Delegue (UE) 2015/35
        sigma_reserves = 11% (NSLT sous-cat 2)
        SCR_prov = 3 x sigma x BE (formule standard Art.105 S2)
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
                f"SCR_prov = 3 x {SIGMA_NSLT_RESERVES:.0%} x {be_total:,.0f}E "
                f"= {scr_prov:,.0f}E (ratio SCR/BE = {ratio:.1%}). "
                f"LoB : NSLT sous-cat 2 Protection du revenu — Annexe II RD 2015/35."
            ),
        }

    # =========================================================================
    #  14. RISK ADJUSTMENT IFRS 17
    # =========================================================================

    def _calculer_risk_adjustment(self, be_total: float) -> float:
        """
        Risk Adjustment IFRS 17 — methode CoC (cout du capital).

        RA = SCR_morbidite x CoC_rate
        SCR_morbidite ≈ 35% x BE (choc EIOPA Art.145)
        CoC_rate = 6% (EIOPA)
        Floor : RA >= 3% du BE (pratique marche prevoyance long terme)
        """
        scr_morb = 0.35 * be_total
        ra       = scr_morb * 0.06
        return max(ra, be_total * 0.03)

    # =========================================================================
    #  15. HYPOTHESES FINALES
    # =========================================================================

    def _construire_hypotheses_sortie(
        self, h: Dict, be_itt: Dict, mack: Dict, bt: Dict, lr: float
    ) -> list:
        """Construit le tableau des hypotheses pour le rapport (standard ActuarIA)."""
        h1 = h["h1_independance"]; h2 = h["h2_stabilite"]
        h3 = h["h3_apriori_bf"];   h4 = h["h4_homosc_bootstrap"]

        def _s(ok): return "VALIDEE" if ok else "REJETEE"

        mack_score = (100 if mack["statut"] == "VERT" else
                      70  if mack["statut"] == "AMBRE" else 40)

        hyp = [
            {"id": "H1", "hypothese": "Independance annees survenance ITT (Spearman)",
             "valeur": h1["message"], "statut": _s(h1["ok"]), "score": h1["score"], "critique": True},
            {"id": "H2", "hypothese": "Stabilite facteurs CL ITT (CV<=20%, derive<=25%)",
             "valeur": h2["message"], "statut": _s(h2["ok"]), "score": h2["score"], "critique": True},
            {"id": "H3", "hypothese": f"A priori BF vs CTIP 2023 [{LR_CTIP_ITT_MIN:.0%}-{LR_CTIP_ITT_MAX:.0%}]",
             "valeur": h3["message"], "statut": _s(h3["ok"]), "score": h3["score"], "critique": False},
            {"id": "H4", "hypothese": "Homocedasticite Bootstrap ODP (England & Verrall 2002)",
             "valeur": h4["message"], "statut": _s(h4["ok"]), "score": h4["score"], "critique": False},
            {"id": "H5", "hypothese": "Loss Ratio Prevoyance <= 90%",
             "valeur": f"LR = {lr*100:.1f}% {'<=' if lr <= 0.90 else '>'} 90%",
             "statut": "VALIDEE" if lr <= 0.90 else ("A JUSTIFIER" if lr <= 1.0 else "REJETEE"),
             "score": max(0, int((1.2 - lr) * 100)) if lr <= 1.2 else 0, "critique": True},
            {"id": "H6", "hypothese": "Incertitude Mack (CV < 20% = VERT EIOPA)",
             "valeur": f"CV Mack = {mack['cv_pct']:.1f}% — statut {mack['statut']}",
             "statut": "VALIDEE" if mack["statut"] == "VERT" else "A JUSTIFIER",
             "score": mack_score, "critique": False},
        ]

        if bt.get("success"):
            hyp.append({
                "id": "H7", "hypothese": "Back-testing boni/mali (Guide IA 2023)",
                "valeur": bt["message"][:200],
                "statut": "VALIDEE" if bt["statut"] == "VERT" else "A JUSTIFIER",
                "score": bt["score_qualite"], "critique": False,
            })

        return hyp

    def _rag(self, hyp: list, be_itt: Dict, lr: float) -> str:
        """RAG global — rouge si hypothese critique rejetee ou LR > 100%."""
        if lr > 1.0: return "ROUGE"
        if any(h.get("critique") and h["statut"] == "REJETEE" for h in hyp):
            return "ROUGE"
        if any(h["statut"] in ("A JUSTIFIER", "REJETEE") for h in hyp):
            return "AMBRE"
        return "VERT"

    # =========================================================================
    #  16. COMMENTAIRE
    # =========================================================================

    def _commentaire(
        self, rag, src, C, meta, h, cl, mack, bf, boot, bt,
        be_itt, pm_rentes, psap_ip, prec, be_total,
        risk_adj, tp_prev, prov_tot, lr, taux_prov, scr, hyp, aid
    ) -> str:
        ic = "VERT" if rag == "VERT" else ("AMBRE" if rag == "AMBRE" else "ROUGE")

        L = [
            "=" * 70,
            f"  RAPPORT PROVISIONNEMENT PREVOYANCE — P3 ELODIE v{self.VERSION}",
            f"  STATUT : {rag} | Audit : {aid}",
            "=" * 70, "",
            "TRIANGLE ITT", "-" * 50,
            f"  Dimensions  : {meta['dimensions']}",
            f"  Mode        : {meta['mode']}",
            f"  Annees      : {meta['annee_debut']} -> {meta['annee_fin']}",
            f"  Ultime obs  : {meta['ultime_observe']:>12,.0f}E",
            "",
            "METHODES ACTUARIELLES", "-" * 50,
            f"  Chain Ladder ({h['methode_cl']:10s}) : {cl['reserve_totale']:>12,.0f}E",
            f"  Mack 1993              : {mack['reserve_best_estimate']:>12,.0f}E | sigma={mack['sigma_total']:,.0f}E | CV={mack['cv_pct']:.1f}%",
            f"  Bornhuetter-Ferguson   : {bf['reserve_totale']:>12,.0f}E | LR={bf['lr_apriori']:.1%} ({bf['source_lr']})",
            f"  Bootstrap ODP          : {boot.get('be_bootstrap', 0):>12,.0f}E | phi={boot.get('phi', 0):.4f}",
            "",
            "BEST ESTIMATE ITT (Art. 77 S2)", "-" * 50,
            f"  BE ITT (pondere)   : {be_itt['be']:>12,.0f}E",
            f"  Methode principale : {be_itt['methode_rec']}",
            f"  CV inter-methodes  : {be_itt['cv_inter']:.1f}%",
            f"  P75 ITT            : {be_itt['p75']:>12,.0f}E",
            f"  P90 ITT            : {be_itt['p90']:>12,.0f}E",
            f"  P99.5 ITT          : {be_itt['p99_5']:>12,.0f}E",
            f"  Source percentiles : {be_itt['source_percentiles']}",
            "",
            "PROVISIONS TOTALES", "-" * 50,
            f"  BE ITT (triangle)                : {be_itt['be']:>12,.0f}E",
            f"  PM Rentes IP (actuariat vie)     : {pm_rentes:>12,.0f}E",
            f"  PSAP IP (constitution invalidite): {psap_ip:>12,.0f}E",
            f"  " + "-"*40,
            f"  BE Prevoyance Total              : {be_total:>12,.0f}E",
            f"  Risk Adjustment IFRS 17          : {risk_adj:>12,.0f}E",
            f"  TP Prevoyance                    : {tp_prev:>12,.0f}E",
            f"  PREC                             : {prec:>12,.0f}E",
            f"  Provision Totale                 : {prov_tot:>12,.0f}E",
            f"  Loss Ratio                       : {lr*100:>11.1f}%",
            "",
            "SCR NSLT SOUS-CAT 2 (Art. 105 S2)", "-" * 50,
            f"  {scr['message']}",
            "",
            "HYPOTHESES H1-H7", "-" * 50,
        ]

        for h_item in hyp:
            ic_h = "OK" if h_item["statut"] == "VALIDEE" else (
                "ATTENTION" if h_item["statut"] == "A JUSTIFIER" else "ECHEC"
            )
            L.append(
                f"  [{ic_h}] [{h_item['id']}] {h_item['hypothese']} "
                f"— Score {h_item['score']}/100 — {h_item['statut']}"
            )

        L += ["", "AVIS ELODIE -> DIALLO", "-" * 50]

        if rag == "VERT":
            L.append(
                f"PROVISIONNEMENT VALIDE — "
                f"BE={be_total:,.0f}E | LR={lr*100:.1f}% | "
                f"P90 ITT={be_itt['p90']:,.0f}E. Donnees transmises a P4 Valentin."
            )
        elif rag == "AMBRE":
            L.append(
                f"PROVISIONNEMENT ACCEPTABLE AVEC RESERVES — "
                f"Verifier les hypotheses signalee avant transmission a P4."
            )
        else:
            L.append(
                f"PROVISIONNEMENT INSUFFISANT — "
                f"LR={lr*100:.1f}% ou hypothese critique rejetee. "
                f"Escalade Diallo. Ne pas transmettre a P4 sans validation."
            )

        if meta["mode"] != "reel":
            L += [
                "",
                "NOTE IMPORTANTE — TRIANGLE SYNTHETIQUE",
                "-" * 50,
                "  Ce calcul repose sur un triangle ITT synthetique genere",
                "  depuis les donnees P1/P2 (cadences CTIP 2023).",
                "  Pour un provisionnement S2 conforme, fournir un triangle",
                "  ITT reel (parametre triangle_itt) avec les donnees historiques",
                "  du portefeuille (3 a 5 annees de survenance minimum).",
            ]

        L.append("")
        return "\n".join(L)

    # =========================================================================
    #  17. GRAPHIQUES (5 graphiques)
    # =========================================================================

    def _graphiques(
        self, C, meta, cl, mack, bf, boot, bt,
        be_itt, pm_rentes, psap_ip, prec, prov_tot, lr, h
    ) -> Dict:
        gph = {}
        n_ann, n_per = C.shape

        # G1 — Heatmap triangle ITT
        try:
            labels_y = meta["labels_annees"]
            labels_x = meta["labels_periodes"]
            z_vals   = []
            for i in range(n_ann):
                row = []
                for j in range(n_per):
                    if i + j < n_ann and C[i, j] > 0:
                        row.append(round(float(C[i, j]), 0))
                    else:
                        row.append(None)
                z_vals.append(row)

            fig = go.Figure(go.Heatmap(
                z=z_vals, x=labels_x, y=labels_y,
                colorscale=[[0, NAVY_L], [0.5, "#2D5F8A"], [1, OR]],
                text=[[f"{v:,.0f}E" if v else "" for v in row] for row in z_vals],
                texttemplate="%{text}",
                textfont=dict(size=9, color=BLANC),
                hovertemplate="Annee %{y} · %{x} : %{z:,.0f}E<extra></extra>",
                showscale=True,
            ))
            fig.update_layout(
                **LAYOUT_BASE, height=360,
                title=dict(
                    text=f"G1 — Heatmap Triangle ITT ({meta['mode']})",
                    font=dict(color=OR, size=13), x=0.01
                ),
                xaxis=dict(title="Periode (semestres)", tickfont=dict(color=BLANC)),
                yaxis=dict(title="Annee survenance", tickfont=dict(color=BLANC)),
            )
            gph["heatmap_triangle_itt"] = fig
        except Exception as e:
            self.logger.warning(f"G1 heatmap : {e}")

        # G2 — Convergence methodes
        try:
            methodes = ["Chain Ladder", "Mack 1993", "BF (CTIP)", "Bootstrap"]
            reserves = [
                cl["reserve_totale"], mack["reserve_best_estimate"],
                bf["reserve_totale"], boot.get("be_bootstrap", 0),
            ]
            couleurs = [BLEU, OR, VERT, VIOLET]

            fig = go.Figure()
            for m_nom, r, col in zip(methodes, reserves, couleurs):
                if r > 0:
                    fig.add_trace(go.Bar(
                        x=[m_nom], y=[r / 1e3],
                        marker_color=col, width=0.5, opacity=0.88,
                        text=[f"{r/1e3:.0f}kE"], textposition="outside",
                        textfont=dict(color=BLANC, size=10),
                        showlegend=False,
                    ))

            fig.add_hline(
                y=be_itt["be"] / 1e3,
                line_dash="dash", line_color=OR, line_width=2,
                annotation_text=f"BE ITT = {be_itt['be']/1e3:.0f}kE",
                annotation_font=dict(color=OR, size=10),
                annotation_position="right",
            )

            fig.update_layout(
                **LAYOUT_BASE,
                title=dict(
                    text="G2 — Convergence des methodes ITT — BE S2",
                    font=dict(color=OR, size=13), x=0.01
                ),
                yaxis_title="kE",
                xaxis=dict(tickfont=dict(color=BLANC)),
            )
            gph["convergence_methodes"] = fig
        except Exception as e:
            self.logger.warning(f"G2 convergence : {e}")

        # G3 — IBNR par annee de survenance
        try:
            annees = meta["labels_annees"]
            ibnr_cl = cl["ibnr_par_annee"]
            ibnr_bf_vals = bf["ibnr_par_annee"]

            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=["IBNR Chain Ladder (kE)", "IBNR BF vs CL (kE)"]
            )

            fig.add_trace(go.Bar(
                x=annees, y=[v / 1e3 for v in ibnr_cl],
                marker_color=[OR if v > 0 else GRIS for v in ibnr_cl],
                text=[f"{v/1e3:.0f}" for v in ibnr_cl],
                textposition="outside", textfont=dict(color=BLANC, size=9),
                showlegend=False,
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=annees, y=[v / 1e3 for v in ibnr_cl],
                mode="lines+markers", name="CL",
                line=dict(color=OR, width=2), marker=dict(size=7, color=OR),
            ), row=1, col=2)
            fig.add_trace(go.Scatter(
                x=annees, y=[v / 1e3 for v in ibnr_bf_vals],
                mode="lines+markers", name="BF",
                line=dict(color=VERT, width=2, dash="dot"),
                marker=dict(size=7, color=VERT),
            ), row=1, col=2)

            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(
                    text="G3 — IBNR ITT par annee de survenance (CL vs BF)",
                    font=dict(color=OR, size=13), x=0.01
                ),
                legend=dict(x=0.55, y=0.95, bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=9)),
            ))
            fig.update_layout(**l)
            gph["ibnr_par_annee"] = fig
        except Exception as e:
            self.logger.warning(f"G3 IBNR : {e}")

        # G4 — Distribution Bootstrap ODP
        try:
            dist = boot.get("distribution", [])
            if dist and len(dist) > 10:
                dist_arr = np.array(dist)
                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=dist_arr / 1e3, nbinsx=40,
                    marker_color=BLEU, opacity=0.75, name="Distribution",
                ))
                for pct_name, pct_val, col in [
                    ("BE", be_itt["be"], OR),
                    ("P90", be_itt["p90"], AMBRE),
                    ("P99.5", be_itt["p99_5"], ROUGE),
                ]:
                    fig.add_vline(
                        x=pct_val / 1e3,
                        line_color=col, line_width=2, line_dash="dash",
                        annotation_text=f"{pct_name}={pct_val/1e3:.0f}kE",
                        annotation_font=dict(color=col, size=9),
                    )
                fig.update_layout(
                    **LAYOUT_BASE,
                    title=dict(
                        text=f"G4 — Distribution Bootstrap ODP ITT ({len(dist)} simulations)",
                        font=dict(color=OR, size=13), x=0.01
                    ),
                    xaxis_title="Reserve ITT (kE)", yaxis_title="Frequence",
                    showlegend=False,
                )
                gph["bootstrap_distribution"] = fig
        except Exception as e:
            self.logger.warning(f"G4 Bootstrap : {e}")

        # G5 — Decomposition provisions
        try:
            composantes = ["BE ITT (CL/Mack)", "PM Rentes IP", "PSAP IP", "PREC"]
            valeurs     = [be_itt["be"], pm_rentes, psap_ip, prec]
            couleurs_g5 = [OR, VIOLET, BLEU, GRIS]

            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=["Decomposition (kE)", "Repartition (%)"],
                specs=[[{"type": "bar"}, {"type": "pie"}]],
            )
            fig.add_trace(go.Bar(
                x=composantes, y=[v / 1e3 for v in valeurs],
                marker_color=couleurs_g5, width=0.5, opacity=0.88,
                text=[f"{v/1e3:.0f}kE" for v in valeurs],
                textposition="outside", textfont=dict(color=BLANC, size=9),
                showlegend=False,
            ), row=1, col=1)

            vals_pos = [v for v in valeurs if v > 0]
            labs_pos = [c for c, v in zip(composantes, valeurs) if v > 0]
            cols_pos = [c for c, v in zip(couleurs_g5, valeurs) if v > 0]
            if vals_pos:
                fig.add_trace(go.Pie(
                    labels=labs_pos, values=vals_pos,
                    marker_colors=cols_pos,
                    textfont=dict(size=9, color=BLANC),
                ), row=1, col=2)

            l = dict(**LAYOUT_BASE)
            l.update(dict(title=dict(
                text=f"G5 — Provisions prevoyance totales = {prov_tot/1e3:.0f}kE | LR={lr*100:.1f}%",
                font=dict(color=OR if lr <= 0.90 else (AMBRE if lr <= 1.0 else ROUGE), size=12),
                x=0.01
            )))
            fig.update_layout(**l)
            gph["decomposition_provisions"] = fig
        except Exception as e:
            self.logger.warning(f"G5 decomposition : {e}")

        return gph

    # =========================================================================
    #  18. AUDIT + CONSOLE
    # =========================================================================

    def _audit(self, aid, be_total, pm_rentes, lr, rag, mack, scr):
        try:
            log   = self.audit_path / "p3_audit.jsonl"
            entry = {
                "audit_id":     aid, "timestamp": datetime.now().isoformat(),
                "version":      self.VERSION, "statut_rag": rag,
                "be_total":     round(be_total, 2), "pm_rentes_ip": round(pm_rentes, 2),
                "loss_ratio":   round(lr, 4), "sigma_itt": round(mack["sigma_total"], 2),
                "cv_pct":       round(mack["cv_pct"], 2), "scr_prov": scr["scr_provisions"],
            }
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _console(self, aid, rag, be_itt, pm_rentes, prov_tot, lr, mack):
        print(f"\n{'─'*70}")
        print(f"  P3 ELODIE v{self.VERSION} | {aid} | {rag}")
        print(
            f"  BE ITT={be_itt:,.0f}E | PM Rentes={pm_rentes:,.0f}E | "
            f"Total={prov_tot:,.0f}E | LR={lr*100:.1f}%"
        )
        print(f"  sigma Mack={mack['sigma_total']:,.0f}E | CV={mack['cv_pct']:.1f}% | statut={mack['statut']}")
        print(f"{'─'*70}")

    # =========================================================================
    #  19. ERREUR
    # =========================================================================

    def _erreur(self, msg: str, aid: str = "") -> Dict:
        return {
            "success":      False, "agent": self.NOM, "version": self.VERSION,
            "audit_id":     aid, "statut_rag": "ROUGE",
            "triangle_meta": {}, "n_annees": 0, "n_periodes": 0,
            "chain_ladder": {}, "mack": {}, "bf": {}, "bootstrap": {}, "backtesting": {},
            "be_itt": 0.0, "be_itt_detail": {},
            "pm_rentes_ip": 0.0, "psap_ip": 0.0, "prec": 0.0,
            "be_prevoyance": 0.0, "risk_adjustment": 0.0, "tp_prevoyance": 0.0,
            "provision_totale": 0.0, "loss_ratio": 0.0, "taux_provisionnement": 0.0,
            "scr": {}, "sorties_p4": {},
            "hypotheses": [], "commentaire": f"ERREUR P3 v{self.VERSION} : {msg}",
            "graphiques": {}, "duree_sec": 0.0, "erreur": msg,
        }


# =============================================================================
#  DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  P3 ELODIE v3.0 — PROVISIONNEMENT PREVOYANCE")
    print("  Triangle ITT | Chain Ladder | Mack 1993 | BF CTIP | Bootstrap ODP")
    print("=" * 70)

    r_p1 = {
        "success": True, "age": 40.0, "categorie": "employe",
        "salaire_brut": 45_000, "primes_acquises": 679.66 * 500,
        "nb_assures": 500, "taux_cotisation_pct": 1.51, "taux_rente_ipp": 0.60,
        "sorties_p2": {"age": 40, "categorie": "employe", "taux_ip": 0.00336,
                       "franchise_jours": 90, "primes_acquises": 679.66*500, "nb_assures": 500},
    }

    r_p2 = {
        "success": True,
        "sorties_p3": {
            "age": 40.0, "categorie": "employe",
            "taux_ip": 0.00336, "taux_itt": 0.042,
            "duree_moy_itt_mois": 13.5, "prob_itt_to_ip": 0.08,
            "prob_maintien_6m": 0.578, "prob_maintien_12m": 0.345,
            "prob_maintien_24m": 0.145, "esperance_duree_ip": 24.8,
            "salaire_brut": 45_000, "taux_rente_ipp": 0.60,
            "primes_acquises": 679.66 * 500, "nb_assures": 500,
            "franchise_jours": 90,
        },
    }

    agent = AgentP3ProvisionnemntPrevoyance(
        models_path="/tmp/p3/models",
        audit_path="/tmp/p3/audit",
        verbose=True,
    )

    r = agent.run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)

    print(f"\n{'='*70}\n  RESULTATS P3 v3.0\n{'='*70}")
    print(f"  Statut         : {r['statut_rag']}")
    print(f"  Triangle       : {r['n_annees']}x{r['n_periodes']} — {r['triangle_meta']['mode']}")
    print(f"  BE ITT (CL)    : {r['chain_ladder']['reserve_totale']:>12,.0f}E")
    print(f"  BE ITT (Mack)  : {r['mack']['reserve_best_estimate']:>12,.0f}E | CV={r['mack']['cv_pct']:.1f}%")
    print(f"  BE ITT (BF)    : {r['bf']['reserve_totale']:>12,.0f}E | LR={r['bf']['lr_apriori']:.1%}")
    print(f"  Bootstrap BE   : {r['bootstrap'].get('be_bootstrap', 0):>12,.0f}E")
    print(f"  P90 ITT        : {r['be_itt_detail']['p90']:>12,.0f}E")
    print(f"  PM Rentes IP   : {r['pm_rentes_ip']:>12,.0f}E")
    print(f"  BE Prevoyance  : {r['be_prevoyance']:>12,.0f}E")
    print(f"  SCR NSLT       : {r['scr']['scr_provisions']:>12,.0f}E")
    print(f"  Loss Ratio     : {r['loss_ratio']*100:>11.1f}%")
    print()
    print("  Hypotheses :")
    for h_item in r["hypotheses"]:
        print(f"    [{h_item['statut']}] [{h_item['id']}] {h_item['hypothese']} — {h_item['score']}/100")
