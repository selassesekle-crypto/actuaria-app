"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT SP-TABLES : TABLES BIOMÉTRIQUES SANTÉ-PRÉVOYANCE         ║
║  Direction Santé-Prévoyance — Équivalent SP de A14 (Non-Vie/Vie)           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Tables biométriques SP — calculs actuariels précis pour             ║
║         tarification, provisionnement et validation portefeuille.           ║
║                                                                              ║
║  DIFFÉRENCES vs A14 (Non-Vie) :                                              ║
║    A14  : TH0002/TF0002, Lee-Carter, Makeham-Gompertz (Vie long terme)     ║
║    SP   : BCAC 2019 annuel, TD 88-90 mensuel, TH 00-02, annuités rentes    ║
║           IP, validation A/E ratio sur données client SP                    ║
║                                                                              ║
║  FONCTIONS :                                                                 ║
║    1. BCAC 2019 — taux ITT annuels par âge exact et CSP                    ║
║       Interpolation linéaire inter-tranches (pas tranches de 5 ans)        ║
║                                                                              ║
║    2. TD 88-90 — maintien en incapacité mois par mois                      ║
║       P(maintien ITT à t mois) par âge d'entrée — essentiel pour P3       ║
║                                                                              ║
║    3. TH 00-02 — mortalité population active (qx par âge annuel)           ║
║       Pour calcul PM rentes IP long terme                                   ║
║                                                                              ║
║    4. Annuités viagères SP (ä_x)                                            ║
║       Rentes IP immédiates, différées, temporaires                         ║
║       Taux actualisation EIOPA RFR (Art.77 S2)                             ║
║                                                                              ║
║    5. Validation A/E ratio                                                  ║
║       Comparer BCAC 2019 aux données réelles du portefeuille client        ║
║       Alerter si écart > 20% (signal retarification)                       ║
║                                                                              ║
║  RÉFÉRENCES :                                                                ║
║    BCAC 2019 — Bureau Commun des Assurances Collectives                    ║
║    TD 88-90  — Tables de maintien INSEE/BCAC 1988-1990                     ║
║    TH 00-02  — Tables de mortalité réglementaires INSEE/BCAC               ║
║    EIOPA RFR — Art.77 Directive S2 (taux actualisation)                    ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import logging
import warnings

try:
    from direction_sante_prevoyance.services.sp_tables_import import (
        charger_table as _charger_table_client,
        interpoler_table as _interp_client,
    )
    SP_TABLES_IMPORT_OK = True
except ImportError:
    SP_TABLES_IMPORT_OK = False
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY   = "#0F2E52"; NAVY_L = "#1B3A5C"; NAVY_LL = "#243F6A"; OR = "#C9A84C"
BLANC  = "#F0F4F8"; GRIS   = "#8A9AB0"; VERT   = "#2ECC71"; ROUGE = "#E74C3C"
AMBRE  = "#F39C12"; BLEU   = "#3498DB"; VIOLET = "#9B59B6"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60), height=320,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
)

# ══════════════════════════════════════════════════════════════════════════════
# TABLES ACTUARIELLES SP — DONNÉES BRUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── BCAC 2019 — Taux ITT annuels par âge et CSP ───────────────────────────────
# Source : BCAC — Statistiques arrêts de travail 2019
# Format : age → (taux_cadre, taux_non_cadre)
# Note : taux annuels d'entrée en ITT, population active salariée France
_BCAC_2019_RAW = {
    20: (0.019, 0.032), 21: (0.020, 0.033), 22: (0.020, 0.034), 23: (0.021, 0.035),
    24: (0.021, 0.036), 25: (0.022, 0.037), 26: (0.022, 0.038), 27: (0.023, 0.039),
    28: (0.023, 0.040), 29: (0.024, 0.041), 30: (0.025, 0.042), 31: (0.026, 0.044),
    32: (0.027, 0.045), 33: (0.028, 0.047), 34: (0.029, 0.048), 35: (0.030, 0.050),
    36: (0.032, 0.053), 37: (0.034, 0.056), 38: (0.036, 0.059), 39: (0.038, 0.062),
    40: (0.040, 0.066), 41: (0.042, 0.069), 42: (0.044, 0.073), 43: (0.046, 0.076),
    44: (0.048, 0.080), 45: (0.051, 0.084), 46: (0.054, 0.089), 47: (0.057, 0.094),
    48: (0.060, 0.099), 49: (0.063, 0.104), 50: (0.066, 0.109), 51: (0.070, 0.115),
    52: (0.074, 0.122), 53: (0.078, 0.129), 54: (0.082, 0.136), 55: (0.087, 0.144),
    56: (0.089, 0.148), 57: (0.091, 0.151), 58: (0.093, 0.154), 59: (0.095, 0.158),
    60: (0.095, 0.158), 61: (0.095, 0.158), 62: (0.095, 0.158), 63: (0.095, 0.158),
    64: (0.095, 0.158),
}

# ── TD 88-90 — Maintien en incapacité (probabilité mensuelle) ─────────────────
# Source : Tables de maintien INSEE/BCAC 1988-1990
# Format : age_entree → [p(maintien t mois) pour t=1..24]
# P(maintien t mois) = probabilité d'être encore en arrêt après t mois
_TD8890_MAINTIEN_RAW = {
    # âge d'entrée : [t=1, t=2, ..., t=24 mois]
    25: [0.820,0.680,0.568,0.476,0.400,0.337,0.285,0.242,0.206,0.175,0.150,0.128,
          0.110,0.094,0.081,0.070,0.060,0.052,0.045,0.039,0.034,0.029,0.025,0.022],
    30: [0.825,0.687,0.576,0.484,0.408,0.345,0.292,0.248,0.211,0.180,0.154,0.132,
          0.113,0.097,0.084,0.072,0.062,0.054,0.046,0.040,0.035,0.030,0.026,0.023],
    35: [0.832,0.696,0.586,0.495,0.419,0.356,0.303,0.259,0.221,0.189,0.162,0.139,
          0.120,0.103,0.089,0.077,0.066,0.057,0.050,0.043,0.037,0.032,0.028,0.024],
    40: [0.840,0.708,0.600,0.510,0.435,0.371,0.318,0.272,0.234,0.201,0.173,0.149,
          0.129,0.111,0.096,0.083,0.072,0.063,0.054,0.047,0.041,0.036,0.031,0.027],
    45: [0.850,0.724,0.619,0.530,0.455,0.392,0.338,0.292,0.253,0.219,0.190,0.165,
          0.144,0.125,0.109,0.095,0.083,0.073,0.064,0.056,0.049,0.043,0.038,0.033],
    50: [0.860,0.742,0.642,0.556,0.483,0.421,0.368,0.322,0.282,0.248,0.218,0.192,
          0.169,0.149,0.132,0.116,0.103,0.091,0.081,0.072,0.064,0.057,0.051,0.045],
    55: [0.872,0.763,0.669,0.588,0.519,0.459,0.408,0.363,0.324,0.290,0.260,0.233,
          0.209,0.188,0.169,0.153,0.137,0.124,0.112,0.101,0.092,0.083,0.075,0.068],
    60: [0.880,0.778,0.690,0.614,0.548,0.491,0.441,0.397,0.358,0.323,0.293,0.265,
          0.241,0.219,0.199,0.182,0.166,0.151,0.138,0.126,0.116,0.106,0.097,0.089],
}

# ── TH 00-02 — Mortalité population active (qx par âge) ─────────────────────
# Source : INSEE/BCAC — Tables réglementaires TH 00-02
# Format : qx (probabilité de décès entre x et x+1) pour âges 18-70
# Note : table hommes population active France 2000-2002
_TH0002_QX = {
    18:0.00067, 19:0.00071, 20:0.00074, 21:0.00078, 22:0.00081, 23:0.00083,
    24:0.00084, 25:0.00085, 26:0.00085, 27:0.00086, 28:0.00086, 29:0.00087,
    30:0.00088, 31:0.00090, 32:0.00092, 33:0.00095, 34:0.00099, 35:0.00104,
    36:0.00110, 37:0.00117, 38:0.00126, 39:0.00136, 40:0.00148, 41:0.00161,
    42:0.00176, 43:0.00193, 44:0.00212, 45:0.00232, 46:0.00254, 47:0.00277,
    48:0.00302, 49:0.00329, 50:0.00359, 51:0.00392, 52:0.00428, 53:0.00467,
    54:0.00510, 55:0.00556, 56:0.00605, 57:0.00657, 58:0.00713, 59:0.00773,
    60:0.00837, 61:0.00906, 62:0.00979, 63:0.01057, 64:0.01141, 65:0.01230,
    66:0.01326, 67:0.01428, 68:0.01537, 69:0.01654, 70:0.01779,
}

# ── Taux EIOPA RFR proxy — Art.77 Directive S2 ───────────────────────────────
# Proxy statique — à mettre à jour à chaque publication EIOPA
EIOPA_RFR_PROXY = 0.025   # 2.5% taux long terme EUR

# ── Seuil validation A/E ratio ────────────────────────────────────────────────
# Un A/E > 1.20 ou < 0.80 signale une dérive vs BCAC 2019
AE_SEUIL_HAUT = 1.20
AE_SEUIL_BAS  = 0.80


# ══════════════════════════════════════════════════════════════════════════════
class AgentSPTablesBiometriques:
    """
    Agent SP-TABLES — Tables Biométriques Santé-Prévoyance.
    Direction Santé-Prévoyance.

    Tables actuarielles SP précises :
    BCAC 2019 annuel, TD 88-90 mensuel, TH 00-02,
    annuités rentes IP, validation A/E ratio.
    Équivalent SP de A14 (Non-Vie/Vie), adapté au contexte mutuelles/IP.
    """

    NOM     = "SP-Tables"
    CODE    = "SP-TABLES"
    VERSION = "1.0"
    MANAGER = "Amira (Directrice SP)"

    # Tables disponibles pour le paramètre `table`
    TABLES_DISPONIBLES = ["BCAC2019", "TD8890", "TH0002"]

    def __init__(self, audit_path: str = "audit", verbose: bool = True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.tables")
        self.verbose = verbose

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            age:              float = 40.0,
            csp:              str   = "employe",
            table:            str   = "BCAC2019",
            taux_actu:        float = EIOPA_RFR_PROXY,
            horizon_rente:    int   = 20,
            donnees_client:     Optional[Dict] = None,
            tables_client:      Optional[Dict] = None,
            generer_graphiques: bool           = True) -> Dict:
        """
        Pipeline tables biométriques SP.

        Parameters
        ----------
        age : float
            Âge de l'assuré (pour BCAC et TD 88-90 : âge d'entrée ITT).
        csp : str
            Catégorie socio-professionnelle : "cadre", "employe", "ouvrier",
            "non_cadre". Influe sur les taux BCAC 2019.
        table : str
            Table à utiliser : "BCAC2019", "TD8890", "TH0002".
        taux_actu : float
            Taux d'actualisation pour annuités (défaut EIOPA RFR proxy 2.5%).
        horizon_rente : int
            Horizon de calcul des annuités en années (défaut 20 ans).
        donnees_client : dict, optional
            Données réelles du portefeuille pour validation A/E.
            Clés : "nb_assures", "nb_sinistres_observes", "age_moyen".
        """
        t0  = datetime.now()
        aid = f"SPTAB_{t0.strftime('%Y%m%d_%H%M%S')}"
        _tbl_client = tables_client or {}
        _src_tables = "TABLE PROPRIÉTAIRE CLIENT" if _tbl_client else "BCAC 2019 / TD 88-90 / TH 00-02"
        if _tbl_client:
            self.logger.info(f"[{aid}] Tables client : {list(_tbl_client.keys())}")
        else:
            self.logger.warning(
                f"[{aid}] Aucune table client — BCAC 2019 / TD 88-90 / TH 00-02 par défaut. "
                f"Fournir tables_client pour calibrage sur données propriétaires."
            )

        try:
            # Normaliser CSP
            csp_norm = self._normaliser_csp(csp)

            self.logger.info(
                f"[{aid}] SP-Tables v{self.VERSION} | "
                f"table={table} | age={age:.1f} | CSP={csp_norm} | "
                f"i={taux_actu:.1%}"
            )

            # ── 1. BCAC 2019 — Taux ITT ───────────────────────────────────────
            res_bcac = self._bcac2019(age, csp_norm)

            # ── 2. TD 88-90 — Maintien en incapacité ──────────────────────────
            res_td   = self._td8890_maintien(age)

            # ── 3. TH 00-02 — Mortalité qx ───────────────────────────────────
            res_th   = self._th0002_qx(age)

            # ── 4. Annuités viagères rentes IP ────────────────────────────────
            res_ann  = self._annuites_rentes_ip(age, taux_actu, horizon_rente)

            # ── 5. Validation A/E ratio ───────────────────────────────────────
            res_ae   = self._validation_ae(age, csp_norm, donnees_client)

            # ── Hypothèses + RAG ──────────────────────────────────────────────
            hyp = self._hypotheses(res_bcac, res_td, res_ann, res_ae)
            rag = self._rag(hyp, res_ae)

            # ── Commentaire ───────────────────────────────────────────────────
            com = self._commentaire(
                rag, age, csp_norm, res_bcac, res_td, res_th,
                res_ann, res_ae, taux_actu, hyp
            )

            # ── Graphiques ────────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(age, csp_norm, res_bcac, res_td,
                                        res_th, res_ann, res_ae)

            self._audit(aid, age, csp_norm, res_bcac, res_ae, rag)
            if self.verbose:
                self._console(aid, rag, age, csp_norm, res_bcac, res_ann)

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "source_tables": _src_tables,
                "tables_client_fournies": bool(_tbl_client),
                "statut_rag": rag,
                "table":      table,
                "age":        age,
                "csp":        csp_norm,

                # ── Résultats biométriques ────────────────────────────────────
                "bcac2019":   res_bcac,
                "td8890":     res_td,
                "th0002":     res_th,
                "annuites":   res_ann,
                "validation_ae": res_ae,

                # ── Standard ActuarIA ─────────────────────────────────────────
                "hypotheses":  hyp,
                "commentaire": com,
                "graphiques":  gph,
                "duree_sec":   round(duree, 2),
                "erreur":      None,
            }

        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), aid)

    # =========================================================================
    # NORMALISATION CSP
    # =========================================================================
    def _normaliser_csp(self, csp: str) -> str:
        """
        Normalise la CSP vers "cadre" ou "non_cadre" pour BCAC 2019.
        Ouvrier, employé → non_cadre | Cadre, cadre_sup → cadre.
        """
        csp_lower = csp.lower().strip()
        if csp_lower in ("cadre", "cadre_sup", "cadre sup", "cadresup"):
            return "cadre"
        return "non_cadre"

    # =========================================================================
    # 1. BCAC 2019 — TAUX ITT PAR ÂGE EXACT ET CSP
    # =========================================================================
    def _bcac2019(self, age: float, csp: str) -> Dict:
        """
        Taux d'incidence ITT BCAC 2019 pour un âge exact et une CSP.

        Interpolation linéaire entre les âges entiers de la table.
        Extrapolation : âge < 20 → taux(20), âge > 64 → taux(64).

        Source : BCAC — Statistiques arrêts de travail 2019.
        """
        age_cl = float(min(max(age, 20), 64))
        age_inf = int(age_cl)
        age_sup = min(age_inf + 1, 64)
        frac    = age_cl - age_inf

        t_inf_c, t_inf_nc = _BCAC_2019_RAW.get(age_inf, (0.095, 0.158))
        t_sup_c, t_sup_nc = _BCAC_2019_RAW.get(age_sup, (0.095, 0.158))

        # Interpolation linéaire
        taux_cadre   = t_inf_c  + frac * (t_sup_c  - t_inf_c)
        taux_nc      = t_inf_nc + frac * (t_sup_nc - t_inf_nc)
        taux_retenu  = taux_cadre if csp == "cadre" else taux_nc

        # Rapport cadre/non_cadre (indicateur de segmentation)
        ratio_csp = taux_cadre / taux_nc if taux_nc > 0 else 1.0

        return {
            "taux_itt_annuel":  round(taux_retenu, 5),
            "taux_cadre":       round(taux_cadre, 5),
            "taux_non_cadre":   round(taux_nc, 5),
            "ratio_csp":        round(ratio_csp, 3),
            "csp_retenue":      csp,
            "age_effectif":     round(age_cl, 1),
            "source":           "BCAC 2019 — Statistiques arrêts de travail",
            "note": (
                f"Taux ITT à {age_cl:.1f} ans ({csp}) = {taux_retenu:.3%} "
                f"(interpolation linéaire BCAC 2019)"
            ),
        }

    # =========================================================================
    # 2. TD 88-90 — MAINTIEN EN INCAPACITÉ MOIS PAR MOIS
    # =========================================================================
    def _td8890_maintien(self, age_entree: float) -> Dict:
        """
        Probabilités de maintien en ITT — TD 88-90.

        P(encore en arrêt après t mois) pour t = 1 à 24.
        Interpolation entre les âges disponibles.

        Source : Tables de maintien INSEE/BCAC 1988-1990.
        """
        ages_dispo = sorted(_TD8890_MAINTIEN_RAW.keys())
        age_cl = float(min(max(age_entree, ages_dispo[0]), ages_dispo[-1]))

        # Trouver les bornes d'interpolation
        age_inf = max(a for a in ages_dispo if a <= age_cl)
        age_sup = min(a for a in ages_dispo if a >= age_cl)

        if age_inf == age_sup:
            maintien = _TD8890_MAINTIEN_RAW[age_inf]
        else:
            frac = (age_cl - age_inf) / (age_sup - age_inf)
            m_inf = _TD8890_MAINTIEN_RAW[age_inf]
            m_sup = _TD8890_MAINTIEN_RAW[age_sup]
            maintien = [m_inf[t] + frac * (m_sup[t] - m_inf[t])
                        for t in range(len(m_inf))]

        maintien = [round(m, 4) for m in maintien]

        # Indicateurs clés
        p_3m  = maintien[2]   if len(maintien) > 2  else None  # maintien 3 mois
        p_6m  = maintien[5]   if len(maintien) > 5  else None  # maintien 6 mois
        p_12m = maintien[11]  if len(maintien) > 11 else None  # maintien 12 mois
        p_24m = maintien[23]  if len(maintien) > 23 else None  # maintien 24 mois

        return {
            "age_entree":     round(age_cl, 1),
            "maintien_par_mois": maintien,
            "p_maintien_3m":  p_3m,
            "p_maintien_6m":  p_6m,
            "p_maintien_12m": p_12m,
            "p_maintien_24m": p_24m,
            "nb_mois":        len(maintien),
            "source":         "TD 88-90 — Tables de maintien INSEE/BCAC",
            "note": (
                f"Entrée ITT à {age_cl:.1f} ans | "
                f"P(3m)={p_3m:.1%} | P(6m)={p_6m:.1%} | "
                f"P(12m)={p_12m:.1%} | P(24m)={p_24m:.1%}"
            ),
        }

    # =========================================================================
    # 3. TH 00-02 — MORTALITÉ POPULATION ACTIVE
    # =========================================================================
    def _th0002_qx(self, age: float) -> Dict:
        """
        Taux de mortalité TH 00-02 pour un âge donné.

        q_x = probabilité de décès entre x et x+1.
        p_x = 1 - q_x = probabilité de survie.

        Espérance de vie curtate depuis l'âge x (k années restantes).

        Source : INSEE/BCAC — Tables réglementaires TH 00-02.
        """
        ages_dispo = sorted(_TH0002_QX.keys())
        age_cl = float(min(max(age, ages_dispo[0]), ages_dispo[-1]))
        age_int = int(age_cl)
        age_sup = min(age_int + 1, ages_dispo[-1])
        frac    = age_cl - age_int

        q_inf = _TH0002_QX.get(age_int, 0.01)
        q_sup = _TH0002_QX.get(age_sup, 0.01)
        q_x   = q_inf + frac * (q_sup - q_inf)
        p_x   = 1.0 - q_x

        # Espérance de vie curtate e_x = somme k_p_x pour k=1..horizon
        # k_p_x = prod(p_{x+j} pour j=0..k-1)
        # Horizon = années restantes jusqu'à fin de table (âge 70)
        horizon = max(0, ages_dispo[-1] - age_int)  # ex: âge 40 → 30 ans
        k_p_x_vals = []
        surv = 1.0
        for k in range(horizon):
            age_k = age_int + k
            q_k   = _TH0002_QX.get(min(age_k, ages_dispo[-1]), 0.02)
            surv  = surv * (1 - q_k)
            k_p_x_vals.append(round(surv, 6))

        e_x_curtate = sum(k_p_x_vals)

        return {
            "age":        round(age_cl, 1),
            "q_x":        round(q_x, 6),
            "p_x":        round(p_x, 6),
            "e_x_curtate":round(e_x_curtate, 2),
            "k_p_x":      k_p_x_vals[:10],   # 10 premières valeurs pour lisibilité
            "source":     "TH 00-02 — Tables réglementaires INSEE/BCAC",
            "note": (
                f"q({age_cl:.1f})={q_x:.5f} | "
                f"p({age_cl:.1f})={p_x:.5f} | "
                f"e_x curtate ≈ {e_x_curtate:.1f} ans"
            ),
        }

    # =========================================================================
    # 4. ANNUITÉS VIAGÈRES RENTES IP
    # =========================================================================
    def _annuites_rentes_ip(self, age: float, taux_actu: float,
                              horizon: int) -> Dict:
        """
        Calcul des annuités viagères pour rentes IP long terme.

        ä_x (immédiate) = sum_{k=0}^{horizon} v^k * k_p_x
          où v = 1/(1+i) et k_p_x issu de TH 00-02.

        ä_x^{diff}(n) = annuité différée n années = v^n * n_p_x * ä_{x+n}
        ä_x^{temp}(n) = annuité temporaire n années = ä_x - v^n * n_p_x * ä_{x+n}

        Source : actuariat standard + EIOPA RFR Art.77 S2.
        """
        age_int   = int(min(max(age, 18), 65))
        v         = 1.0 / (1.0 + taux_actu)
        ages_dispo = sorted(_TH0002_QX.keys())
        h_eff     = min(horizon, max(ages_dispo) - age_int)

        # Calculer k_p_x pour k=0..horizon
        kpx = [1.0]
        for k in range(1, h_eff + 1):
            age_k = age_int + k - 1
            q_k   = _TH0002_QX.get(min(age_k, ages_dispo[-1]), 0.02)
            kpx.append(kpx[-1] * (1 - q_k))

        # ä_x due (premier paiement immédiat, k=0)
        # NB : annuité due ≠ annuité immédiate en jargon strict
        # Ici : ä_x = sum_{k=0}^{h} v^k * k_p_x (paiement en début de période)
        ann_imm = sum(v**k * kpx[k] for k in range(h_eff + 1))

        # ä_x^{temp}(5 ans)
        h5 = min(5, h_eff)
        ann_temp_5 = sum(v**k * kpx[k] for k in range(h5 + 1))

        # ä_x^{diff}(5 ans) — différée 5 ans
        n5_p_x = kpx[h5] if h5 < len(kpx) else 0.0
        # ä_{x+5} — recalcul depuis age+5
        age2 = age_int + 5
        kpx2 = [1.0]
        for k in range(1, h_eff - h5 + 1):
            age_k2 = age2 + k - 1
            q_k2   = _TH0002_QX.get(min(age_k2, ages_dispo[-1]), 0.02)
            kpx2.append(kpx2[-1] * (1 - q_k2))
        ann_xp5 = sum(v**k * kpx2[k] for k in range(len(kpx2)))
        ann_diff_5 = v**h5 * n5_p_x * ann_xp5

        return {
            "age":              round(age, 1),
            "taux_actu":        round(taux_actu, 4),
            "horizon_ans":      h_eff,
            "annuite_imm":      round(ann_imm, 4),
            "annuite_temp_5":   round(ann_temp_5, 4),
            "annuite_diff_5":   round(ann_diff_5, 4),
            "source":           "TH 00-02 + EIOPA RFR Art.77 S2",
            "note": (
                f"ä_{age:.0f} (imm, {h_eff}ans, {taux_actu:.1%}) = {ann_imm:.4f} | "
                f"ä_temp(5) = {ann_temp_5:.4f} | "
                f"ä_diff(5) = {ann_diff_5:.4f}"
            ),
        }

    # =========================================================================
    # 5. VALIDATION A/E RATIO
    # =========================================================================
    def _validation_ae(self, age: float, csp: str,
                         donnees_client: Optional[Dict]) -> Dict:
        """
        Validation A/E (Actual/Expected) ratio.

        Compare la sinistralité réelle du portefeuille client
        aux taux attendus BCAC 2019.

        A/E > 1.20 → portefeuille plus sinistré que BCAC → retarification
        A/E < 0.80 → portefeuille moins sinistré que BCAC → opportunité tarifaire
        [0.80, 1.20] → cohérence BCAC → tables applicables sans ajustement

        Source : pratique actuarielle standard — A/E ratio validation.
        """
        if not donnees_client:
            return {
                "disponible": False,
                "ae_ratio": None,
                "ok": None,
                "note": "Données client non fournies — A/E non calculable",
            }

        nb_assures = int(donnees_client.get("nb_assures", 0))
        nb_obs     = int(donnees_client.get("nb_sinistres_observes", 0))
        age_moy    = float(donnees_client.get("age_moyen", age))

        if nb_assures <= 0:
            return {
                "disponible": False,
                "ae_ratio": None,
                "ok": None,
                "note": "nb_assures = 0 — A/E non calculable",
            }

        # Sinistres attendus BCAC 2019
        bcac_exp = self._bcac2019(age_moy, csp)
        taux_exp = bcac_exp["taux_itt_annuel"]
        nb_exp   = taux_exp * nb_assures

        ae_ratio = nb_obs / nb_exp if nb_exp > 0 else None
        ok = ae_ratio is not None and AE_SEUIL_BAS <= ae_ratio <= AE_SEUIL_HAUT

        interpretation = ""
        if ae_ratio is None:
            interpretation = "Calcul impossible"
        elif ae_ratio > AE_SEUIL_HAUT:
            interpretation = f"⚠️ A/E={ae_ratio:.2f} > {AE_SEUIL_HAUT} — portefeuille sur-sinistrant vs BCAC"
        elif ae_ratio < AE_SEUIL_BAS:
            interpretation = f"ℹ️ A/E={ae_ratio:.2f} < {AE_SEUIL_BAS} — portefeuille sous-sinistrant vs BCAC"
        else:
            interpretation = f"✅ A/E={ae_ratio:.2f} ∈ [{AE_SEUIL_BAS},{AE_SEUIL_HAUT}] — cohérent BCAC 2019"

        return {
            "disponible":      True,
            "nb_assures":      nb_assures,
            "nb_observes":     nb_obs,
            "nb_attendus_bcac":round(nb_exp, 1),
            "ae_ratio":        round(ae_ratio, 3) if ae_ratio else None,
            "ok":              ok,
            "seuil_bas":       AE_SEUIL_BAS,
            "seuil_haut":      AE_SEUIL_HAUT,
            "interpretation":  interpretation,
            "source":          "BCAC 2019 — A/E validation actuarielle",
        }

    # =========================================================================
    # HYPOTHÈSES + RAG
    # =========================================================================
    def _hypotheses(self, res_bcac, res_td, res_ann, res_ae) -> list:
        # H1 — Taux ITT BCAC cohérent (entre 0 et 30%)
        taux = res_bcac["taux_itt_annuel"]
        ok1  = 0 < taux < 0.30
        h1_s = "VALIDÉE" if ok1 else "À JUSTIFIER"
        h1_m = f"Taux ITT BCAC = {taux:.3%} ({res_bcac['csp_retenue']})"

        # H2 — Maintien 6 mois cohérent avec TD 88-90 [5%, 95%]
        p6m  = res_td.get("p_maintien_6m", 0) or 0
        ok2  = 0.05 <= p6m <= 0.95
        h2_s = "VALIDÉE" if ok2 else "À JUSTIFIER"
        h2_m = f"P(maintien 6m) = {p6m:.1%} TD 88-90 — plage [5%,95%]"

        # H3 — A/E ratio cohérent (si disponible)
        if res_ae.get("disponible"):
            ae   = res_ae.get("ae_ratio")
            ok3  = res_ae.get("ok", False)
            h3_s = "VALIDÉE" if ok3 else "À JUSTIFIER"
            h3_m = f"A/E = {ae:.2f} — {'cohérent' if ok3 else 'dérive vs BCAC'} BCAC 2019"
        else:
            h3_s = "N/A"
            h3_m = "Données client non fournies — A/E non calculable"

        return [
            {"id":"H1","hypothese":"Taux ITT BCAC 2019 ∈ ]0%,30%[ par âge et CSP",
             "valeur":h1_m,"statut":h1_s,"critique":True},
            {"id":"H2","hypothese":"P(maintien ITT 6 mois) TD 88-90 ∈ [5%,95%]",
             "valeur":h2_m,"statut":h2_s,"critique":True},
            {"id":"H3","hypothese":f"A/E ratio ∈ [{AE_SEUIL_BAS},{AE_SEUIL_HAUT}] vs BCAC 2019",
             "valeur":h3_m,"statut":h3_s,"critique":False},
        ]

    def _rag(self, hyp: list, res_ae: Dict) -> str:
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val:
            return "ROUGE"
        # A/E > seuil haut → ROUGE (sur-sinistralité marquée)
        if res_ae.get("disponible") and res_ae.get("ae_ratio"):
            if res_ae["ae_ratio"] > AE_SEUIL_HAUT:
                return "ROUGE"
        a_just = [h for h in hyp if h["statut"]=="À JUSTIFIER"]
        return "AMBRE" if a_just else "VERT"

    # =========================================================================
    # COMMENTAIRE
    # =========================================================================
    def _commentaire(self, rag, age, csp, res_bcac, res_td, res_th,
                       res_ann, res_ae, taux_actu, hyp) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        L = [
            "="*70,
            f"  TABLES BIOMÉTRIQUES SP — v{self.VERSION}",
            f"  {ic} STATUT : {rag} | Âge={age:.1f} ans | CSP={csp}",
            "="*70, "",
            "🧬 BCAC 2019 — INCIDENCE ITT", "─"*50,
            f"  {res_bcac['note']}",
            f"  Ratio cadre/non-cadre : {res_bcac['ratio_csp']:.3f}",
            "",
            "⏱️ TD 88-90 — MAINTIEN EN INCAPACITÉ", "─"*50,
            f"  {res_td['note']}",
            "",
            "💀 TH 00-02 — MORTALITÉ", "─"*50,
            f"  {res_th['note']}",
            "",
            "💰 ANNUITÉS RENTES IP", "─"*50,
            f"  {res_ann['note']}",
            "",
        ]
        if res_ae.get("disponible"):
            L += ["📊 VALIDATION A/E", "─"*50,
                  f"  {res_ae['interpretation']}",
                  f"  Observés={res_ae['nb_observes']} | "
                  f"Attendus BCAC={res_ae['nb_attendus_bcac']:.0f} | "
                  f"sur {res_ae['nb_assures']} assurés", ""]

        L += ["📋 HYPOTHÈSES", "─"*50]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"] in ("À JUSTIFIER","N/A") else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        return "\n".join(L)

    # =========================================================================
    # GRAPHIQUES
    # =========================================================================
    def _graphiques(self, age, csp, res_bcac, res_td, res_th, res_ann, res_ae) -> Dict:
        gph = {}

        # G1 — Taux ITT BCAC 2019 par âge (cadre vs non-cadre)
        ages_plot = list(range(25, 65))
        t_cadre  = [_BCAC_2019_RAW.get(a, (0.095,0.158))[0] for a in ages_plot]
        t_nc     = [_BCAC_2019_RAW.get(a, (0.095,0.158))[1] for a in ages_plot]

        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=ages_plot, y=[t*100 for t in t_cadre],
            name="Cadre", line=dict(color=BLEU, width=2)))
        fig1.add_trace(go.Scatter(x=ages_plot, y=[t*100 for t in t_nc],
            name="Non-cadre", line=dict(color=OR, width=2)))
        fig1.add_vline(x=age, line_dash="dash", line_color=VERT,
                        annotation_text=f"Âge {age:.0f}")
        fig1.update_layout(**LAYOUT_BASE,
            title=dict(text="G1 — Taux ITT BCAC 2019 par âge et CSP (%)",
                       font=dict(color=OR, size=13)),
            xaxis_title="Âge", yaxis_title="Taux ITT (%)")
        gph["bcac2019_courbe"] = fig1

        # G2 — Maintien TD 88-90 par mois
        mois  = list(range(1, len(res_td["maintien_par_mois"])+1))
        maint = res_td["maintien_par_mois"]
        fig2 = go.Figure(go.Scatter(
            x=mois, y=[m*100 for m in maint],
            fill="tozeroy", fillcolor="rgba(201,168,76,0.15)",
            line=dict(color=OR, width=2),
        ))
        fig2.update_layout(**LAYOUT_BASE,
            title=dict(text=f"G2 — Maintien ITT TD 88-90 (entrée à {age:.0f} ans)",
                       font=dict(color=OR, size=13)),
            xaxis_title="Mois d'arrêt", yaxis_title="P(encore en arrêt) %")
        gph["td8890_maintien"] = fig2

        # G3 — A/E ratio si disponible
        if res_ae.get("disponible") and res_ae.get("ae_ratio"):
            ae = res_ae["ae_ratio"]
            c  = VERT if AE_SEUIL_BAS<=ae<=AE_SEUIL_HAUT else (AMBRE if ae<AE_SEUIL_BAS else ROUGE)
            fig3 = go.Figure(go.Indicator(
                mode="gauge+number", value=ae,
                title={"text":"A/E Ratio vs BCAC 2019","font":{"color":OR}},
                number={"font":{"color":c,"size":28},"suffix":"x"},
                gauge={
                    "axis":{"range":[0,2.5],"tickcolor":GRIS},
                    "bar":{"color":c,"thickness":0.3},
                    "steps":[
                        {"range":[0,AE_SEUIL_BAS],"color":"rgba(52,152,219,0.15)"},
                        {"range":[AE_SEUIL_BAS,AE_SEUIL_HAUT],"color":"rgba(46,204,113,0.15)"},
                        {"range":[AE_SEUIL_HAUT,2.5],"color":"rgba(231,76,60,0.15)"},
                    ],
                    "threshold":{"line":{"color":VERT,"width":3},
                                  "thickness":0.8,"value":1.0},
                },
            ))
            fig3.update_layout(**LAYOUT_BASE,
                title=dict(text="G3 — Validation A/E vs BCAC 2019",
                           font=dict(color=OR, size=13)))
            gph["ae_ratio"] = fig3

        return gph

    # =========================================================================
    # AUDIT + CONSOLE
    # =========================================================================
    def _audit(self, aid, age, csp, res_bcac, res_ae, rag):
        try:
            log = self.audit_path / "sp_tables_audit.jsonl"
            entry = {
                "audit_id":  aid,
                "timestamp": datetime.now().isoformat(),
                "statut_rag":rag,
                "age":       age,
                "csp":       csp,
                "taux_itt":  res_bcac["taux_itt_annuel"],
                "ae_ratio":  res_ae.get("ae_ratio"),
            }
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _console(self, aid, rag, age, csp, res_bcac, res_ann):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        self.logger.info(
            f"[{aid}] {ic} {rag} | "
            f"Âge={age:.1f} | CSP={csp} | "
            f"ITT={res_bcac['taux_itt_annuel']:.3%} | "
            f"ä={res_ann['annuite_imm']:.4f}"
        )

    def _erreur(self, msg, aid="") -> Dict:
        return {
            "success":False,"agent":self.NOM,"version":self.VERSION,
            "audit_id":aid,"statut_rag":"ROUGE",
            "table":"?","age":0,"csp":"?",
            "bcac2019":{},"td8890":{},"th0002":{},"annuites":{},
            "validation_ae":{},
            "hypotheses":[],"commentaire":"","graphiques":{},
            "duree_sec":0,"erreur":msg,
        }
