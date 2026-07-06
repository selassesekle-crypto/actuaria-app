"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT SP-RAPPORT : RAPPORT ACTUARIEL SANTÉ-PRÉVOYANCE          ║
║  Direction Santé-Prévoyance · Équivalent SP de A7 Ibrahim (Non-Vie)        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Rapport actuariel consolidé SP — livrable professionnel             ║
║         pour CA, ACPR, commissaire aux comptes, actuaire désigné.           ║
║                                                                              ║
║  PIPELINE M1 → M5 (analogie N1→N5 de A7 Ibrahim) :                         ║
║                                                                              ║
║  M1 — Ingestion & validation                                                ║
║       Agrège les résultats de S1-S3, P1-P4, SP-Coord, SP-Reg1/2/3         ║
║       Vérifie la cohérence et la complétude des données                    ║
║                                                                              ║
║  M2 — Hypothèses actuarielles SP                                            ║
║       BCAC 2019, DREES 2023, ANI 2013, EIOPA RFR, FNMF 2023               ║
║       Versioning et traçabilité complète                                    ║
║                                                                              ║
║  M3 — Calculs actuariels SP                                                 ║
║       LR par poste santé, morbidité ITT/IP, LR prévoyance                  ║
║       SCR consolidé, cohérence inter-modules                                ║
║                                                                              ║
║  M4 — Best Estimate SP consolidé                                            ║
║       BE santé + BE prévoyance + RA + TP                                   ║
║       Ratio SCR/MCR + conformité réglementaire                              ║
║                                                                              ║
║  M5 — Livrables professionnels                                              ║
║       · Rapport Word (.docx) 8 sections                                     ║
║       · Rapport PDF (WeasyPrint / HTML fallback)                            ║
║       · Classeur Excel 8 onglets Navy/Gold                                  ║
║       · Graphiques Plotly interactifs                                        ║
║       · Commentaire actuariel narratif                                       ║
║                                                                              ║
║  DIFFÉRENCES vs A7 Ibrahim (Non-Vie) :                                      ║
║    Non-Vie : Chain Ladder, Munich, Mack, Bootstrap, triangles IARD          ║
║    SP      : Sinistralité par poste DREES, morbidité BCAC, Markov ITT/IP   ║
║              PM rentes IP, tarification santé ANI, SCR NSLT+SLT            ║
║                                                                              ║
║  ENTRÉES (toutes optionnelles — dégradation gracieuse) :                   ║
║    result_s1   → S1 Léonie (tarification santé)                            ║
║    result_s2   → S2 Selma  (provisionnement santé)                         ║
║    result_s3   → S3 Binta  (reporting santé)                               ║
║    result_p1   → P1 Axel   (tarification prévoyance)                       ║
║    result_p2   → P2 Rayan  (tables morbidité)                              ║
║    result_p3   → P3 Élodie (provisionnement prévoyance)                    ║
║    result_p4   → P4 Valentin (reporting prévoyance)                        ║
║    result_coord → SP-Coord (consolidation S+P)                             ║
║    result_reg1 → SP-REG1  (S2 narratif)                                    ║
║    result_reg2 → SP-REG2  (IFRS 17)                                        ║
║    result_reg3 → SP-REG3  (ANI + 100%S)                                    ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import hashlib
import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

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

from .m5_excel_sp  import export_excel_sp
from .m5_rapport_sp import export_word_sp, export_pdf_sp

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
class AgentSPRapportActuariel:
    """
    Agent SP-RAPPORT — Rapport Actuariel Santé-Prévoyance.
    Direction Santé-Prévoyance.

    Pipeline M1→M5 produisant Word + PDF + Excel 8 onglets
    à partir des résultats des agents S1-S3, P1-P4 et SP-*.
    Équivalent SP de A7 Ibrahim (Non-Vie).
    """

    NOM     = "SP-Rapport"
    CODE    = "SP-RAPPORT"
    VERSION = "1.0"
    MANAGER = "Amira (Directrice SP)"

    def __init__(self, models_path: str = "models",
                 audit_path: str = "audit", verbose: bool = True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.rapport")
        self.verbose = verbose

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s1   = None,
            result_s2   = None,
            result_s3   = None,
            result_p1   = None,
            result_p2   = None,
            result_p3   = None,
            result_p4   = None,
            result_coord = None,
            result_reg1  = None,
            result_reg2  = None,
            result_reg3  = None,
            entite:          str   = "Assureur Santé-Prévoyance",
            date_arrete:     str   = "",
            actuaire_resp:   str   = "Actuaire qualifié",
            fonds_propres:   float = 0.0,
            generer_graphiques: bool = True) -> Dict:
        """
        Pipeline M1→M5 complet.

        Toutes les entrées sont optionnelles — l'agent produit
        un rapport avec les données disponibles (dégradation gracieuse).
        """
        t0  = datetime.now()
        aid = f"RAPPORT_{t0.strftime('%Y%m%d_%H%M%S')}"
        date_arrete = date_arrete or t0.strftime("%d/%m/%Y")

        try:
            # ── M1 : Ingestion & validation ───────────────────────────────────
            m1 = self._m1_ingestion(
                result_s1, result_s2, result_s3,
                result_p1, result_p2, result_p3, result_p4,
                result_coord, result_reg1, result_reg2, result_reg3,
                fonds_propres
            )
            _be_log = m1['be_sante'] + m1['be_prev']
            self.logger.info(
                f"[{aid}] SP-Rapport v{self.VERSION} | "
                f"BE={_be_log:,.0f}€ | "
                f"PA={m1['pa_total']:,.0f}€ | "
                f"modules={m1['modules_disponibles']}"
            )

            # ── M2 : Hypothèses actuarielles SP ───────────────────────────────
            m2 = self._m2_hypotheses(m1)

            # ── M3 : Calculs actuariels SP ────────────────────────────────────
            m3 = self._m3_calculs(m1, m2)

            # ── M4 : Best Estimate consolidé ──────────────────────────────────
            m4 = self._m4_best_estimate(m1, m3)

            # ── Hypothèses RAG ────────────────────────────────────────────────
            hyp = self._hypotheses(m1, m3, m4)
            rag = self._rag(hyp, m4)
            avis = ("FAVORABLE" if rag == "VERT" else
                    "AVEC RÉSERVES" if rag == "AMBRE" else "DÉFAVORABLE")

            # ── Commentaire ───────────────────────────────────────────────────
            com = self._commentaire(rag, avis, entite, date_arrete,
                                     m1, m3, m4, hyp)

            # ── Hash de session (intégrité) ───────────────────────────────────
            session_hash = hashlib.sha256(
                json.dumps({
                    "be_total":  m4["be_total"],
                    "scr":       m4["scr_consolide"],
                    "ratio_scr": m4["ratio_scr"],
                    "date":      date_arrete,
                }, sort_keys=True).encode()
            ).hexdigest()[:8].upper()

            # ── M5 : Livrables ────────────────────────────────────────────────
            data_m5 = self._preparer_data_m5(
                m1, m2, m3, m4, hyp, rag,
                entite, date_arrete, actuaire_resp
            )

            excel_bytes = export_excel_sp(data_m5)
            word_bytes  = export_word_sp(data_m5)
            pdf_bytes   = export_pdf_sp(data_m5)

            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._m5_graphiques(m1, m3, m4)

            # ── Audit trail ───────────────────────────────────────────────────
            audit = self._audit(aid, m1, m4, rag, session_hash,
                                 entite, date_arrete, actuaire_resp)

            if self.verbose:
                self._console(aid, rag, avis, m4, session_hash)

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── Données M1-M4 ────────────────────────────────────────────
                "m1": m1,
                "m2": m2,
                "m3": m3,
                "m4": m4,

                # ── Résultats clés ────────────────────────────────────────────
                "be_sante":       round(m1["be_sante"], 2),
                "be_prevoyance":  round(m1["be_prev"], 2),
                "be_total":       round(m4["be_total"], 2),
                "scr_consolide":  round(m4["scr_consolide"], 2),
                "ratio_scr_pct":  round(m4["ratio_scr"], 1),
                "avis_actuariel": avis,
                "session_hash":   session_hash,
                "modules_disponibles": m1["modules_disponibles"],

                # ── Livrables M5 ─────────────────────────────────────────────
                "graphiques":  gph,
                "commentaire": com,
                "excel_bytes": excel_bytes,
                "word_bytes":  word_bytes,
                "pdf_bytes":   pdf_bytes,
                "audit_trail": audit,

                # ── Standard ActuarIA ─────────────────────────────────────────
                "hypotheses":  hyp,
                "duree_sec":   round(duree, 2),
                "erreur":      None,
            }

        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), aid)

    # =========================================================================
    # M1 — INGESTION
    # =========================================================================
    def _m1_ingestion(self, r_s1, r_s2, r_s3, r_p1, r_p2, r_p3, r_p4,
                       r_coord, r_reg1, r_reg2, r_reg3, fonds_propres) -> Dict:
        """
        Agrège les résultats de tous les agents SP disponibles.
        Dégradation gracieuse : produit un rapport avec ce qui est disponible.
        """
        modules = []
        warns   = []

        # ── Santé ─────────────────────────────────────────────────────────────
        be_sante = ra_sante = scr_sante = mcr_sante = pa_sante = 0
        lr_sante = psap_sante = ibnr_sante = 0
        postes = {}
        nb_assures_sante = 0
        age_moyen_sante  = 0

        if r_s1 and r_s1.get("success"):
            modules.append("S1")
            pa_sante         = float(r_s1.get("primes_acquises", r_s1.get("sorties_s2",{}).get("primes_acquises",0)))
            nb_assures_sante = int(r_s1.get("nb_assures", 0))
            age_moyen_sante  = float(r_s1.get("age_moyen", 0))
            postes           = r_s1.get("postes", {})
            lr_sante         = float(r_s1.get("ratio_sp_attendu", 0))

        if r_s2 and r_s2.get("success"):
            modules.append("S2")
            psap_sante = float(r_s2.get("psap_total", 0))
            ibnr_sante = float(r_s2.get("psap_ibnr", 0))
            if pa_sante == 0:
                s3_out = r_s2.get("sorties_s3",{})
                pa_sante = float(s3_out.get("primes_acquises", 0))

        if r_s3 and r_s3.get("success"):
            modules.append("S3")
            be_sante  = float(r_s3.get("be_sante", 0))
            ra_sante  = float(r_s3.get("risk_adjustment", 0))
            scr_sante = float(r_s3.get("scr_sante", 0))
            mcr_sante = float(r_s3.get("mcr_sante", 0))
            if pa_sante == 0:
                pa_sante = float(r_s3.get("primes_acquises", be_sante * 2))

        # ── Prévoyance ────────────────────────────────────────────────────────
        be_prev = ra_prev = scr_prev = mcr_prev = pa_prev = 0
        lr_prev = psap_prev = pm_rentes = ibnr_prev = 0
        taux_itt = taux_ip = 0
        nb_assures_prev = 0
        age_moyen_prev  = 0
        maintien = {}
        tarif_p1 = {}

        if r_p1 and r_p1.get("success"):
            modules.append("P1")
            pa_prev         = float(r_p1.get("sorties_p2",{}).get("primes_acquises",
                               r_p1.get("primes_acquises", 0)))
            nb_assures_prev = int(r_p1.get("nb_assures", 0))
            age_moyen_prev  = float(r_p1.get("age_moyen", 0))
            tarif_p1        = r_p1.get("primes_pures", {})

        if r_p2 and r_p2.get("success"):
            modules.append("P2")
            s3_p2 = r_p2.get("sorties_p3", {})
            taux_itt = float(s3_p2.get("taux_itt", 0))
            taux_ip  = float(s3_p2.get("taux_ip", 0))
            maintien = r_p2.get("prob_maintien", {})

        if r_p3 and r_p3.get("success"):
            modules.append("P3")
            psap_prev  = float(r_p3.get("psap_total", 0))
            pm_rentes  = float(r_p3.get("pm_rentes_ip", 0))
            ibnr_prev  = float(r_p3.get("psap_total", 0)) * 0.30
            s4_p3      = r_p3.get("sorties_p4", {})
            ra_prev    = float(s4_p3.get("risk_adjustment", 0))
            be_prev    = float(s4_p3.get("be_prevoyance", 0))

        if r_p4 and r_p4.get("success"):
            modules.append("P4")
            be_prev   = float(r_p4.get("be_prevoyance", be_prev))
            ra_prev   = float(r_p4.get("risk_adjustment", ra_prev))
            scr_prev  = float(r_p4.get("scr_invalidite", 0))
            mcr_prev  = float(r_p4.get("mcr", 0))
            nav_p4    = r_p4.get("sorties_naomie", {})
            if pa_prev == 0:
                pa_prev = float(nav_p4.get("primes_acquises", 0))
            lr_prev = float(r_p4.get("loss_ratio", 0))

        # ── Coord + Reg ───────────────────────────────────────────────────────
        scr_consolide = diversification = mcr_consolide = 0
        fpp = fonds_propres

        if r_coord and r_coord.get("success"):
            modules.append("SP-Coord")
            scr_consolide   = float(r_coord.get("scr_consolide", 0))
            diversification = float(r_coord.get("diversification", 0))
            mcr_consolide   = float(r_coord.get("mcr_consolide", 0))
            if fpp == 0:
                fpp = float(r_coord.get("fonds_propres", 0))
        else:
            # Calcul direct
            rho = 0.25
            scr_consolide = float(np.sqrt(
                scr_sante**2 + 2*rho*scr_sante*scr_prev + scr_prev**2
            )) if scr_sante or scr_prev else 0
            diversification = (scr_sante + scr_prev) - scr_consolide
            mcr_consolide   = mcr_sante + mcr_prev

        if fpp == 0:
            fpp = (be_sante + be_prev) * 1.5
            warns.append("fonds_propres non fournis — estimés à 150% BE")

        ifrs17 = {}
        if r_reg2 and r_reg2.get("success"):
            modules.append("SP-REG2")
            ifrs17 = {
                "be_sante":   float(r_reg2.get("be_sante",0)),
                "be_prev":    float(r_reg2.get("be_prevoyance",0)),
                "be_total":   float(r_reg2.get("be_total",0)),
                "ra_sante":   float(r_reg2.get("ra_sante",0)),
                "ra_prev":    float(r_reg2.get("ra_prevoyance",0)),
                "ra_total":   float(r_reg2.get("ra_total",0)),
                "fcf_sante":  float(r_reg2.get("be_sante",0))+float(r_reg2.get("ra_sante",0)),
                "fcf_prev":   float(r_reg2.get("be_prevoyance",0))+float(r_reg2.get("ra_prevoyance",0)),
                "fcf_total":  float(r_reg2.get("fcf_total",0)),
                "csm_sante":  0,
                "csm_prev":   float(r_reg2.get("csm_total",0)),
                "csm_total":  float(r_reg2.get("csm_total",0)),
                "lc_sante":   0,
                "lc_prev":    float(r_reg2.get("lc_total",0)),
                "lc_total":   float(r_reg2.get("lc_total",0)),
                "csm_release":float(r_reg2.get("csm_release_annuel",0)),
            }

        reglementation = {}
        if r_reg3 and r_reg3.get("success"):
            modules.append("SP-REG3")
            reglementation = {
                "ani_conforme":     r_reg3.get("ani_conforme"),
                "sante_100_note":   r_reg3.get("sante_100_detail",{}).get("note_globale",""),
                "contrat_resp_note":r_reg3.get("contrat_resp",{}).get("note",""),
            }

        if not modules:
            warns.append("Aucun agent SP disponible — rapport minimal")

        return {
            # Santé
            "be_sante":    be_sante, "ra_sante":    ra_sante,
            "scr_sante":   scr_sante, "mcr_sante":  mcr_sante,
            "pa_sante":    pa_sante,  "lr_sante":    lr_sante,
            "psap_sante":  psap_sante, "ibnr_sante": ibnr_sante,
            "nb_assures_sante": nb_assures_sante,
            "age_moyen_sante":  age_moyen_sante,
            "sinistralite_par_poste": postes,
            # Prévoyance
            "be_prev":    be_prev, "ra_prev":     ra_prev,
            "scr_prev":   scr_prev, "mcr_prev":   mcr_prev,
            "pa_prev":    pa_prev,  "lr_prev":     lr_prev,
            "psap_prev":  psap_prev, "pm_rentes_ip": pm_rentes,
            "ibnr_prev":  ibnr_prev,
            "nb_assures_prev": nb_assures_prev,
            "age_moyen_prev":  age_moyen_prev,
            "taux_itt":   taux_itt, "taux_ip": taux_ip,
            "maintien":   maintien, "tarif_p1": tarif_p1,
            # Consolidé
            "pa_total":       pa_sante + pa_prev,
            "scr_consolide":  scr_consolide,
            "diversification":diversification,
            "mcr_consolide":  mcr_consolide,
            "fonds_propres":  fpp,
            # Réglementation
            "ifrs17":         ifrs17,
            "reglementation": reglementation,
            # Méta
            "modules_disponibles": modules,
            "avertissements":      warns,
        }

    # =========================================================================
    # M2 — HYPOTHÈSES
    # =========================================================================
    def _m2_hypotheses(self, m1: Dict) -> Dict:
        """
        Hypothèses actuarielles SP — versionnées et sourcées.
        H1-H4 standard + hypothèses SP-spécifiques.
        """
        hyps = [
            # H1 — Sinistralité santé
            {
                "id": "H1",
                "hypothese": "Fréquences et coûts santé — DREES 2023",
                "valeur":    f"PA santé = {m1['pa_sante']:,.0f}€ | LR = {m1['lr_sante']:.1%}",
                # LR=0 signifie absence de données S1 — statut N/A, pas À JUSTIFIER
                "statut":    ("VALIDÉE" if 0.55 <= m1["lr_sante"] <= 0.90
                              else "N/A" if m1["lr_sante"] == 0
                              else "À JUSTIFIER"),
                "source":    "DREES — Comptes de la Santé 2023",
                "critique":  True,
            },
            # H2 — Morbidité prévoyance
            {
                "id": "H2",
                "hypothese": "Tables de morbidité — BCAC 2019 + TD 88-90",
                "valeur":    (f"Taux ITT = {m1['taux_itt']:.2%} | Taux IP = {m1['taux_ip']:.3%}"
                              if m1["taux_itt"] else "Tables non chargées"),
                "statut":    "VALIDÉE" if m1["taux_itt"] > 0 else "À JUSTIFIER",
                "source":    "BCAC 2019 (Bureau Commun Assurances Collectives)",
                "critique":  True,
            },
            # H3 — Taux d'actualisation
            {
                "id": "H3",
                "hypothese": "Taux d'actualisation EIOPA RFR — Art.77 S2",
                "valeur":    "2.5% proxy EIOPA RFR EUR (long terme)",
                "statut":    "VALIDÉE",
                "source":    "EIOPA Risk-Free Rate curve EUR — Art.77 Directive S2",
                "critique":  False,
            },
            # H4 — Solvabilité
            {
                "id": "H4",
                "hypothese": "Solvabilité S2 — SCR NSLT (σ=5%) + SLT (+35%)",
                "valeur":    (f"SCR consolidé = {m1['scr_consolide']:,.0f}€ (ρ=0.25 EIOPA)"
                              if m1["scr_consolide"] else "SCR non calculé"),
                "statut":    "VALIDÉE" if m1["scr_consolide"] > 0 else "À JUSTIFIER",
                "source":    "RD 2015/35 Art.145/148 + Annexe IV",
                "critique":  True,
            },
        ]

        return {
            "hypotheses": hyps,
            "version_bcac":  "BCAC 2019",
            "version_drees":  "DREES 2023",
            "version_eiopa_rfr": "EIOPA EUR Q4 2025",
            "version_ani":    "ANI 2013 — Art.L911-7 CSS",
            "date_arrete_hyp": datetime.now().strftime("%d/%m/%Y"),
        }

    # =========================================================================
    # M3 — CALCULS ACTUARIELS SP
    # =========================================================================
    def _m3_calculs(self, m1: Dict, m2: Dict) -> Dict:
        """
        Calculs actuariels SP spécifiques.
        LR santé par poste, LR prévoyance, indicateurs BCAC/CTIP.
        """
        # LR global santé
        lr_sante_obs = (m1["psap_sante"] / max(m1["pa_sante"], 1)
                         if m1["pa_sante"] else 0)
        lr_prev_obs  = (m1["psap_prev"] / max(m1["pa_prev"], 1)
                        if m1["pa_prev"] else 0)

        # Part ITT vs IP dans le BE prévoyance
        be_prev = m1["be_prev"]
        part_psap_itt = (m1["psap_prev"] - m1["pm_rentes_ip"]) / max(be_prev, 1)
        part_pm_rentes = m1["pm_rentes_ip"] / max(be_prev, 1)

        # Bénéfice diversification S+P en %
        pct_div = (m1["diversification"] /
                   max(m1["scr_sante"] + m1["scr_prev"], 1) * 100)

        # Vérification cohérence LR tarification vs provisionnement
        lr_tarif_s = m1["lr_sante"]
        lr_cohérent = abs(lr_tarif_s - lr_sante_obs) < 0.20 if (lr_tarif_s and lr_sante_obs) else True

        return {
            "lr_sante_observe":   round(lr_sante_obs, 4),
            "lr_prev_observe":    round(lr_prev_obs, 4),
            "part_psap_itt_pct":  round(part_psap_itt * 100, 1),
            "part_pm_rentes_pct": round(part_pm_rentes * 100, 1),
            "pct_diversification":round(pct_div, 1),
            "lr_coherent":        lr_cohérent,
            # Indicateurs BCAC/CTIP
            "taux_maintien_6m":   m1["maintien"].get("mois_6", 0),
            "taux_maintien_12m":  m1["maintien"].get("mois_12", 0),
        }

    # =========================================================================
    # M4 — BEST ESTIMATE CONSOLIDÉ
    # =========================================================================
    def _m4_best_estimate(self, m1: Dict, m3: Dict) -> Dict:
        """
        BE SP consolidé + ratios S2 + statuts réglementaires.
        """
        be_total  = m1["be_sante"] + m1["be_prev"]
        ra_total  = m1["ra_sante"] + m1["ra_prev"]
        tp_total  = be_total + ra_total
        fpp       = m1["fonds_propres"]
        scr       = m1["scr_consolide"]
        mcr       = m1["mcr_consolide"]

        ratio_scr = fpp / max(scr, 1) * 100 if scr else 0
        ratio_mcr = fpp / max(mcr, 1) * 100 if mcr else 0

        return {
            "be_total":        round(be_total, 2),
            "ra_total":        round(ra_total, 2),
            "tp_total":        round(tp_total, 2),
            "scr_consolide":   round(scr, 2),
            "mcr_consolide":   round(mcr, 2),
            "fonds_propres":   round(fpp, 2),
            "ratio_scr":       round(ratio_scr, 1),
            "ratio_mcr":       round(ratio_mcr, 1),
            "conforme_scr":    ratio_scr >= 100,
            "conforme_mcr":    ratio_mcr >= 100,
        }

    # =========================================================================
    # HYPOTHÈSES RAG
    # =========================================================================
    def _hypotheses(self, m1: Dict, m3: Dict, m4: Dict) -> list:
        h_m2 = [
            {"id":"H1","hypothese":"LR santé ∈ [55%,90%] — marché mutuelles (FNMF 2023)",
             "valeur":f"LR observe = {m3['lr_sante_observe']:.1%}",
             "statut":"VALIDÉE" if 0.55<=m3["lr_sante_observe"]<=0.90 or m3["lr_sante_observe"]==0 else "À JUSTIFIER",
             "source":"FNMF 2023","critique":True},
            {"id":"H2","hypothese":"Ratio SCR SP ≥ 100% — Art.129 Directive S2",
             "valeur":f"Ratio SCR = {m4['ratio_scr']:.1f}%",
             "statut":"VALIDÉE" if m4["conforme_scr"] or m4["scr_consolide"]==0 else "NON VALIDÉE",
             "source":"Art.129 S2","critique":True},
            {"id":"H3","hypothese":"Cohérence LR tarification ↔ provisionnement",
             "valeur":f"LR tarif={m1['lr_sante']:.1%} vs prov={m3['lr_sante_observe']:.1%}",
             "statut":"VALIDÉE" if m3["lr_coherent"] else "À JUSTIFIER",
             "source":"Contrôle interne SP","critique":False},
        ]
        return h_m2

    def _rag(self, hyp: list, m4: Dict) -> str:
        if not m4["conforme_mcr"] and m4["mcr_consolide"] > 0:
            return "ROUGE"
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val:
            return "ROUGE"
        a_just = [h for h in hyp if h["statut"]=="À JUSTIFIER"]
        return "AMBRE" if a_just else "VERT"

    # =========================================================================
    # COMMENTAIRE
    # =========================================================================
    def _commentaire(self, rag, avis, entite, date_arrete,
                      m1, m3, m4, hyp) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        modules = ", ".join(m1["modules_disponibles"]) or "Aucun"
        L = [
            "="*70,
            f"  RAPPORT ACTUARIEL SANTÉ-PRÉVOYANCE — v{self.VERSION}",
            f"  {ic} AVIS : {avis} | {entite} | Arrêté au {date_arrete}",
            f"  Modules : {modules}",
            "="*70, "",
            "🔢 BILAN CONSOLIDÉ", "─"*50,
            f"  {'':30s} {'Santé':>12s} {'Prévoyance':>12s} {'Total':>12s}",
            f"  {'Primes acquises':30s} {m1['pa_sante']:>12,.0f} {m1['pa_prev']:>12,.0f} {m1['pa_total']:>12,.0f}",
            f"  {'Best Estimate':30s} {m1['be_sante']:>12,.0f} {m1['be_prev']:>12,.0f} {m4['be_total']:>12,.0f}",
            f"  {'Risk Adjustment':30s} {m1['ra_sante']:>12,.0f} {m1['ra_prev']:>12,.0f} {m4['ra_total']:>12,.0f}",
            f"  {'TP (BE+RA)':30s} {'':>12s} {'':>12s} {m4['tp_total']:>12,.0f}",
            "",
            "📊 SOLVABILITÉ S2", "─"*50,
            f"  SCR consolidé (ρ=0.25 EIOPA) : {m4['scr_consolide']:>12,.0f}€",
            f"  Bénéfice diversification      : {m1['diversification']:>12,.0f}€  ({m3['pct_diversification']:.1f}%)",
            f"  Fonds Propres                 : {m4['fonds_propres']:>12,.0f}€",
            f"  Ratio SCR                     : {m4['ratio_scr']:>11.1f}%  "
            f"({'✅' if m4['conforme_scr'] else '❌'} seuil 100%)",
            "",
            "🩺 MORBIDITÉ PRÉVOYANCE", "─"*50,
            f"  Taux ITT                      : {m1['taux_itt']:.2%}",
            f"  Taux IP                       : {m1['taux_ip']:.3%}",
            f"  Maintien arrêt 6 mois         : {m3['taux_maintien_6m']:.3f}",
            f"  PSAP / PM rentes IP           : {m3['part_psap_itt_pct']:.1f}% / {m3['part_pm_rentes_pct']:.1f}% du BE",
            "",
            "📋 HYPOTHÈSES", "─"*50,
        ]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"]=="À JUSTIFIER" else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]
        return "\n".join(L)

    # =========================================================================
    # DATA POUR M5
    # =========================================================================
    def _preparer_data_m5(self, m1, m2, m3, m4, hyp, rag,
                            entite, date_arrete, actuaire_resp) -> Dict:
        """Prépare le dict de données pour les exports Excel/Word/PDF."""
        return {
            **m1, **m3, **m4,
            "entite":         entite,
            "date_arrete":    date_arrete,
            "actuaire_resp":  actuaire_resp,
            "statut_rag":     rag,
            "hypotheses_m2":  m2["hypotheses"],
            "hypotheses_rapport": hyp,
            "commentaire_resume": (
                f"Portefeuille SP consolidé | BE={m4['be_total']/1e6:.2f}M€ | "
                f"Ratio SCR={m4['ratio_scr']:.1f}% | Avis: "
                f"{'FAVORABLE' if rag=='VERT' else 'AVEC RÉSERVES' if rag=='AMBRE' else 'DÉFAVORABLE'}"
            ),
            "tarification": {
                "prime_eco":       m1["tarif_p1"].get("itt", 0),
                "prime_confort":   m1["tarif_p1"].get("itt", 0),
                "prime_premium":   m1["tarif_p1"].get("deces", 0),
                "chargement_pct":  0.18,
                **{f"itt_{csp}": m1["tarif_p1"].get("itt", 0)
                   for csp in ["ouvrier","employe","cadre","cadre_sup"]},
            },
            "morbidite": {
                "ages":           [25,30,35,40,45,50,55,60],
                "taux_itt":       m1["taux_itt"],
                "taux_ip":        m1["taux_ip"],
                "maintien":       m1["maintien"],
                "maintien_6m":    m1["maintien"].get("mois_6", 0),
                "maintien_12m":   m1["maintien"].get("mois_12", 0),
            },
            "ratio_scr_sante": (m1["fonds_propres"] / max(m1["scr_sante"],1)*100
                                 if m1["scr_sante"] else 0),
            "ratio_scr_prev":  (m1["fonds_propres"] / max(m1["scr_prev"],1)*100
                                 if m1["scr_prev"] else 0),
        }

    # =========================================================================
    # M5 — GRAPHIQUES
    # =========================================================================
    def _m5_graphiques(self, m1, m3, m4) -> Dict:
        gph = {}

        # G1 — BE consolidé
        fig1 = go.Figure(go.Bar(
            x=["BE Santé","BE Prévoyance","BE Consolidé"],
            y=[m1["be_sante"], m1["be_prev"], m4["be_total"]],
            marker_color=[BLEU, VIOLET, OR],
            text=[f"{v/1000:.0f}k€" for v in [m1["be_sante"],m1["be_prev"],m4["be_total"]]],
            textposition="outside",
        ))
        fig1.update_layout(**LAYOUT_BASE,
            title=dict(text="G1 — Best Estimate Santé + Prévoyance",
                       font=dict(color=OR, size=13)))
        gph["g1_be_consolide"] = fig1

        # G2 — SCR décomposé
        fig2 = go.Figure(go.Bar(
            x=["SCR Santé","SCR Prévoyance","Diversification","SCR Consolidé"],
            y=[m1["scr_sante"], m1["scr_prev"],
               -m1["diversification"], m4["scr_consolide"]],
            marker_color=[BLEU, VIOLET, VERT, OR],
        ))
        fig2.update_layout(**LAYOUT_BASE,
            title=dict(text="G2 — SCR Consolidé SP (ρ=0.25 EIOPA Annexe IV)",
                       font=dict(color=OR, size=13)))
        gph["g2_scr_consolide"] = fig2

        # G3 — Ratio SCR gauge
        ratio = m4["ratio_scr"]
        c = VERT if ratio>=130 else (AMBRE if ratio>=100 else ROUGE)
        fig3 = go.Figure(go.Indicator(
            mode="gauge+number", value=ratio,
            title={"text":"Ratio SCR SP (%)","font":{"color":OR}},
            number={"font":{"color":c,"size":28},"suffix":"%"},
            gauge={
                "axis":{"range":[0,max(300,ratio*1.2)],"tickcolor":GRIS},
                "bar":{"color":c,"thickness":0.3},
                "steps":[
                    {"range":[0,100],"color":"rgba(231,76,60,0.15)"},
                    {"range":[100,130],"color":"rgba(243,156,18,0.15)"},
                    {"range":[130,max(300,ratio*1.2)],"color":"rgba(46,204,113,0.12)"},
                ],
                "threshold":{"line":{"color":VERT,"width":3},"thickness":0.8,"value":130},
            },
        ))
        fig3.update_layout(**LAYOUT_BASE,
            title=dict(text="G3 — Solvabilité S2 Santé-Prévoyance",
                       font=dict(color=OR, size=13)))
        gph["g3_ratio_scr"] = fig3

        # G4 — Répartition provisions
        fig4 = go.Figure(go.Pie(
            labels=["PSAP Santé","PSAP Prévoyance","PM Rentes IP"],
            values=[m1["psap_sante"], m1["psap_prev"]-m1["pm_rentes_ip"], m1["pm_rentes_ip"]],
            marker_colors=[BLEU, VIOLET, OR],
            hole=0.5,
        ))
        fig4.update_layout(**LAYOUT_BASE,
            title=dict(text="G4 — Décomposition Provisions SP",
                       font=dict(color=OR, size=13)))
        gph["g4_provisions"] = fig4

        return gph

    # =========================================================================
    # AUDIT
    # =========================================================================
    def _audit(self, aid, m1, m4, rag, session_hash,
                entite, date_arrete, actuaire_resp) -> Dict:
        entry = {
            "audit_id":     aid,
            "timestamp":    datetime.now().isoformat(),
            "entite":       entite,
            "date_arrete":  date_arrete,
            "actuaire":     actuaire_resp,
            "statut_rag":   rag,
            "session_hash": session_hash,
            "be_total":     round(m4["be_total"], 2),
            "scr_consolide":round(m4["scr_consolide"], 2),
            "ratio_scr":    round(m4["ratio_scr"], 1),
            "modules":      m1["modules_disponibles"],
        }
        try:
            log = self.audit_path / "sp_rapport_audit.jsonl"
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return entry

    def _console(self, aid, rag, avis, m4, session_hash):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        self.logger.info(
            f"[{aid}] {ic} {avis} | "
            f"BE={m4['be_total']:,.0f}€ | "
            f"SCR={m4['scr_consolide']:,.0f}€ | "
            f"Ratio={m4['ratio_scr']:.1f}% | "
            f"Hash={session_hash}"
        )

    def _erreur(self, msg, aid="") -> Dict:
        return {
            "success":False,"agent":self.NOM,"version":self.VERSION,
            "audit_id":aid,"statut_rag":"ROUGE",
            "m1":{},"m2":{},"m3":{},"m4":{},
            "be_total":0,"scr_consolide":0,"ratio_scr_pct":0,
            "avis_actuariel":"DÉFAVORABLE","session_hash":"",
            "graphiques":{},"commentaire":"","excel_bytes":b"",
            "word_bytes":b"","pdf_bytes":b"","audit_trail":{},
            "hypotheses":[],"duree_sec":0,"erreur":msg,
        }
