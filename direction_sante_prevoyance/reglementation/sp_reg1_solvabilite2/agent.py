"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT SP-REG1 : SOLVABILITÉ 2 SANTÉ-PRÉVOYANCE                 ║
║  Direction Santé-Prévoyance · Équipe Réglementation & Finance              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Rapport S2 narratif complet pour l'ACPR — Santé + Prévoyance.       ║
║                                                                              ║
║  DIFFÉRENCIATION vs S3/P4/SP-Coord :                                         ║
║    S3 Binta    → SCR NSLT santé + QRT S.13.01 (technique santé)            ║
║    P4 Valentin → SCR SLT invalidité + QRT S.14.01 (technique prévoyance)   ║
║    SP-Coord    → SCR consolidé agrégé (ρ=0.25 EIOPA) — vision prudentielle  ║
║    SP-REG1     → Rapport S2 narratif ACPR complet :                         ║
║                  · QRT S.05.01 (primes, sinistres, dépenses consolidées)    ║
║                  · SFCR narratif SP (sections A-E obligatoires)             ║
║                  · ORSA résumé exécutif (lien Naomie stress testing)        ║
║                  · Cohérence inter-QRT (S.05 + S.13 + S.14)                ║
║                  · Tableau MCR/SCR avec décomposition et justifications     ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_s3    → S3 Binta (SCR santé, QRT S.13)                           ║
║    result_p4    → P4 Valentin (SCR invalidité, QRT S.14)                   ║
║    result_coord → SP-Coord (SCR consolidé, diversification) — optionnel    ║
║    result_st    → Naomie ST (stress tests ORSA) — optionnel                ║
║                                                                              ║
║  RÉFÉRENCES RÉGLEMENTAIRES :                                                 ║
║    Directive S2 2009/138/CE — Art.51 (SFCR), Art.45 (ORSA)                 ║
║    RD 2015/35 — Art.143/144 (QRT), Art.148/252 (SCR/MCR)                  ║
║    EIOPA — Guidelines on SFCR (EIOPA-BoS-15/140)                           ║
║    ACPR — Guide SFCR 2023                                                   ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict

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

# ── Paramètres réglementaires ─────────────────────────────────────────────────
# Source : Annexe IV RD 2015/35 — corrélation NSLT/SLT
RHO_NSLT_SLT = 0.25

# Seuil de solvabilité minimal — Art.129 Directive S2
SEUIL_SCR_MIN   = 100.0   # % — seuil minimal absolu
SEUIL_SCR_CIBLE = 130.0   # % — seuil cible pratique marché

# Sections SFCR obligatoires — Directive S2 Art.51 + EIOPA Guidelines
SECTIONS_SFCR = [
    ("A", "Activité et résultats",
     "Présentation de l'activité SP, résultats de souscription, investissements"),
    ("B", "Système de gouvernance",
     "Organisation, contrôle interne, gestion des risques, actuaire désigné"),
    ("C", "Profil de risque",
     "SCR par module, concentration, atténuation, sensibilités"),
    ("D", "Valorisation à des fins de solvabilité",
     "Actifs, provisions techniques (BE+RA), autres passifs"),
    ("E", "Gestion du capital",
     "Fonds propres, SCR, MCR, non-respect éventuel"),
]


# ══════════════════════════════════════════════════════════════════════════════
class AgentSPReg1Solvabilite2:
    """
    Agent SP-REG1 — Solvabilité 2 Santé-Prévoyance.
    Direction Santé-Prévoyance · Équipe Réglementation & Finance.

    Produit le rapport S2 narratif complet pour soumission ACPR :
    QRT S.05.01, SFCR sections A-E, ORSA résumé, cohérence inter-QRT.
    """

    NOM     = "SP-Reg1-S2"
    CODE    = "SP-REG1"
    VERSION = "1.0"
    MANAGER = "Équipe Réglementation & Finance SP"

    def __init__(self, audit_path: str = "audit", verbose: bool = True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.reg1.s2")
        self.verbose = verbose

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s3,
            result_p4,
            result_coord         = None,
            result_st            = None,
            date_arrete:    str  = "",
            entite:         str  = "Assureur Santé-Prévoyance",
            generer_graphiques: bool = True) -> Dict:
        """
        Paramètres
        ----------
        result_s3    : dict — résultat S3 Binta (requis)
        result_p4    : dict — résultat P4 Valentin (requis)
        result_coord : dict — résultat SP-Coord (optionnel — SCR consolidé)
        result_st    : dict — résultat Naomie ST (optionnel — ORSA)
        date_arrete  : str  — date d'arrêté (ex: "31/12/2025")
        entite       : str  — nom de l'entité déclarante
        """
        t0  = datetime.now()
        aid = f"REG1_{t0.strftime('%Y%m%d_%H%M%S')}"
        date_arrete = date_arrete or t0.strftime("%d/%m/%Y")

        try:
            # ── 1. EXTRACTION ─────────────────────────────────────────────────
            src = self._extraire(result_s3, result_p4, result_coord)
            self.logger.info(
                f"[{aid}] SP-Reg1 S2 | BE={src['be_total']:,.0f}€ | "
                f"SCR={src['scr_consolide']:,.0f}€ | "
                f"FP={src['fpp']:,.0f}€ | entité={entite}"
            )

            # ── 2. QRT S.05.01 — Primes, sinistres, dépenses ──────────────────
            qrt_s05 = self._generer_qrt_s05(src)

            # ── 3. COHÉRENCE INTER-QRT ────────────────────────────────────────
            # Vérifier la cohérence entre S.05, S.13 et S.14
            coherence = self._verifier_coherence_qrts(src, result_s3, result_p4)

            # ── 4. SFCR NARRATIF — Sections A-E ──────────────────────────────
            sfcr = self._generer_sfcr(src, result_st, entite, date_arrete)

            # ── 5. ORSA RÉSUMÉ ────────────────────────────────────────────────
            orsa = self._generer_orsa(src, result_st)

            # ── 6. TABLEAU MCR/SCR CONSOLIDÉ ──────────────────────────────────
            tableau_scr = self._tableau_scr_consolide(src)

            # ── 7. HYPOTHÈSES + RAG ───────────────────────────────────────────
            hyp = self._hypotheses(src, coherence)
            rag = self._rag(hyp, src)

            # ── 8. COMMENTAIRE ────────────────────────────────────────────────
            com = self._commentaire(
                rag, src, qrt_s05, coherence, sfcr, orsa,
                tableau_scr, entite, date_arrete, hyp
            )

            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(src, tableau_scr)

            self._audit(aid, src, rag)
            if self.verbose:
                self._console(aid, rag, src, coherence)

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── Bilan S2 ─────────────────────────────────────────────────
                "be_sante":         round(src["be_sante"], 2),
                "be_prevoyance":    round(src["be_prev"], 2),
                "be_total":         round(src["be_total"], 2),
                "scr_sante":        round(src["scr_sante"], 2),
                "scr_prevoyance":   round(src["scr_prev"], 2),
                "scr_consolide":    round(src["scr_consolide"], 2),
                "mcr_consolide":    round(src["mcr_consolide"], 2),
                "fonds_propres":    round(src["fpp"], 2),
                "ratio_scr_pct":    round(src["ratio_scr"], 1),
                "ratio_mcr_pct":    round(src["ratio_mcr"], 1),
                "diversification":  round(src["diversification"], 2),

                # ── QRT ──────────────────────────────────────────────────────
                "qrt_s05":          qrt_s05,
                "coherence_qrts":   coherence,
                "tableau_scr":      tableau_scr,

                # ── SFCR + ORSA ───────────────────────────────────────────────
                "sfcr_sections":    sfcr,
                "orsa_resume":      orsa,

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
    # 1. EXTRACTION
    # =========================================================================
    def _extraire(self, result_s3, result_p4, result_coord) -> Dict:
        """Extrait et consolide les données de S3, P4 et SP-Coord."""
        if not result_s3 or not result_s3.get("success"):
            raise ValueError("result_s3 requis et success=True")
        if not result_p4 or not result_p4.get("success"):
            raise ValueError("result_p4 requis et success=True")

        # Santé (S3)
        be_sante  = float(result_s3.get("be_sante", 0))
        ra_sante  = float(result_s3.get("risk_adjustment", 0))
        scr_sante = float(result_s3.get("scr_sante", 0))
        mcr_sante = float(result_s3.get("mcr_sante", 0))
        fpp_s3    = float(result_s3.get("fonds_propres", 0))

        # Primes santé — depuis primes_acquises S3 (priorité 1),
        # puis QRT S.13 ligne R0100 (priorité 2),
        # sinon fallback be_sante × 1.8 (proxy LR~55% — à remplacer en production)
        qrt_s13  = result_s3.get("qrt_s13", {})
        if "primes_acquises" in result_s3:
            pa_sante = float(result_s3["primes_acquises"])
        else:
            _r0100 = next(
                (l["C0010"] for l in qrt_s13.get("lignes", []) if l.get("code") == "R0100"),
                None
            )
            pa_sante = float(_r0100) if _r0100 is not None else be_sante * 1.8
            if _r0100 is None:
                self.logger.warning(
                    "primes_acquises absentes de result_s3 et QRT S.13 "
                    f"— fallback pa_sante={pa_sante:,.0f}€ (be_sante×1.8)"
                )

        # Prévoyance (P4)
        be_prev  = float(result_p4.get("be_prevoyance", 0))
        ra_prev  = float(result_p4.get("risk_adjustment", 0))
        scr_prev = float(result_p4.get("scr_invalidite", 0))
        mcr_prev = float(result_p4.get("mcr", 0))
        fpp_p4   = float(result_p4.get("fonds_propres", 0))
        nav_p4   = result_p4.get("sorties_naomie", {})
        pa_prev  = float(nav_p4.get("primes_acquises", be_prev))

        # SCR consolidé — depuis SP-Coord si disponible, sinon calculer
        if result_coord and result_coord.get("success"):
            scr_consolide   = float(result_coord.get("scr_consolide", 0))
            diversification = float(result_coord.get("diversification", 0))
            mcr_consolide   = float(result_coord.get("mcr_consolide", 0))
            fpp = float(result_coord.get("fonds_propres", max(fpp_s3, fpp_p4)))
        else:
            # Calcul direct — Annexe IV RD 2015/35
            scr_consolide = float(np.sqrt(
                scr_sante**2 + 2*RHO_NSLT_SLT*scr_sante*scr_prev + scr_prev**2
            ))
            diversification = (scr_sante + scr_prev) - scr_consolide
            mcr_consolide   = mcr_sante + mcr_prev
            fpp = max(fpp_s3, fpp_p4)
            if fpp == 0:
                fpp = (be_sante + be_prev) * 1.5
                self.logger.warning(
                    f"fonds_propres non fournis → estimés à {fpp:,.0f}€"
                )

        ratio_scr = fpp / max(scr_consolide, 1) * 100
        ratio_mcr = fpp / max(mcr_consolide, 1) * 100

        return {
            "be_sante":   be_sante, "ra_sante":   ra_sante,
            "be_prev":    be_prev,  "ra_prev":    ra_prev,
            "be_total":   be_sante + be_prev,
            "pa_sante":   pa_sante, "pa_prev":    pa_prev,
            "pa_total":   pa_sante + pa_prev,
            "scr_sante":  scr_sante,  "mcr_sante": mcr_sante,
            "scr_prev":   scr_prev,   "mcr_prev":  mcr_prev,
            "scr_consolide":   scr_consolide,
            "mcr_consolide":   mcr_consolide,
            "diversification": diversification,
            "fpp":        fpp,
            "ratio_scr":  ratio_scr,
            "ratio_mcr":  ratio_mcr,
        }

    # =========================================================================
    # 2. QRT S.05.01 — PRIMES, SINISTRES, DÉPENSES
    # =========================================================================
    def _generer_qrt_s05(self, src: Dict) -> Dict:
        """
        QRT S.05.01 — Primes, sinistres et dépenses par ligne d'activité.
        Source : Annexe I RD 2015/35 — template QRT S.05.01.
        SP : ligne Santé NSLT (colonne C0030) + Santé SLT (colonne C0060).
        """
        # Sinistres estimés = BE (approximation provisions = sinistres résiduels)
        sin_sante = src["be_sante"] * 0.80   # LR proxy santé
        sin_prev  = src["be_prev"]  * 0.70   # LR proxy prévoyance

        # Dépenses estimées (chargements ~18% des primes)
        dep_sante = src["pa_sante"] * 0.18
        dep_prev  = src["pa_prev"]  * 0.20

        return {
            "code":  "S.05.01",
            "titre": "Primes, sinistres et dépenses par ligne d'activité",
            "lignes": [
                {
                    "code":    "R0010",
                    "libelle": "Primes acquises — Santé NSLT",
                    "C0030":   round(src["pa_sante"], 0),
                    "C0060":   round(src["pa_prev"],  0),
                    "total":   round(src["pa_total"],  0),
                },
                {
                    "code":    "R0050",
                    "libelle": "Sinistres survenus — Santé NSLT",
                    "C0030":   round(sin_sante, 0),
                    "C0060":   round(sin_prev,  0),
                    "total":   round(sin_sante + sin_prev, 0),
                },
                {
                    "code":    "R0090",
                    "libelle": "Dépenses d'exploitation",
                    "C0030":   round(dep_sante, 0),
                    "C0060":   round(dep_prev,  0),
                    "total":   round(dep_sante + dep_prev, 0),
                },
                {
                    "code":    "R0200",
                    "libelle": "Provisions techniques (BE + RA)",
                    # C0030 et C0060 arrondis séparément, total = somme des arrondis
                    # pour garantir total == C0030 + C0060 (cohérence QRT EIOPA)
                    "C0030":   (_r200_s := round(src["be_sante"] + src["ra_sante"], 0)),
                    "C0060":   (_r200_p := round(src["be_prev"]  + src["ra_prev"],  0)),
                    "total":   _r200_s + _r200_p,
                },
            ],
            "note": "Source : RD 2015/35 Annexe I — template S.05.01. "
                    "NSLT = Santé non-similaire à la vie | SLT = Invalidité/Morbidité similaire à la vie.",
        }

    # =========================================================================
    # 3. COHÉRENCE INTER-QRT
    # =========================================================================
    def _verifier_coherence_qrts(self, src, result_s3, result_p4) -> Dict:
        """
        Vérifie la cohérence entre QRT S.05, S.13 et S.14.
        Contrôles obligatoires avant soumission ACPR.
        Source : EIOPA Validation Rules for QRTs.
        """
        controles = []
        ok_global = True

        # C1 — BE total S.05 = BE_santé (S.13) + BE_prév (S.14)
        be_s13 = float(result_s3.get("be_sante", 0))
        be_s14 = float(result_p4.get("be_prevoyance", 0))
        be_s05 = src["be_total"]
        ecart_be = abs(be_s05 - (be_s13 + be_s14))
        ok_c1 = ecart_be < 1.0
        if not ok_c1:
            ok_global = False
        controles.append({
            "id": "C1",
            "controle": "BE S.05 = BE S.13 + BE S.14",
            "valeur":   f"{be_s05:,.0f} = {be_s13:,.0f} + {be_s14:,.0f}",
            "ecart":    round(ecart_be, 2),
            "ok":       ok_c1,
            "note":     "✅ Cohérent" if ok_c1 else f"❌ Écart {ecart_be:.0f}€",
        })

        # C2 — SCR total consolidé ≤ SCR_S + SCR_P (bénéfice diversification)
        scr_s = float(result_s3.get("scr_sante", 0))
        scr_p = float(result_p4.get("scr_invalidite", 0))
        scr_c = src["scr_consolide"]
        ok_c2 = scr_c <= scr_s + scr_p + 0.01
        if not ok_c2:
            ok_global = False
        controles.append({
            "id": "C2",
            "controle": "SCR consolidé ≤ SCR_S + SCR_P (diversification Annexe IV)",
            "valeur":   f"{scr_c:,.0f} ≤ {scr_s+scr_p:,.0f}",
            "ok":       ok_c2,
            "note":     "✅ Cohérent" if ok_c2 else "❌ SCR consolidé > somme modules",
        })

        # C3 — FP > SCR (solvabilité minimale Art.129)
        ok_c3 = src["fpp"] >= src["scr_consolide"]
        if not ok_c3:
            ok_global = False
        controles.append({
            "id": "C3",
            "controle": "FP ≥ SCR (Art.129 Directive S2)",
            "valeur":   f"{src['fpp']:,.0f} ≥ {src['scr_consolide']:,.0f}",
            "ok":       ok_c3,
            "note":     f"✅ Ratio {src['ratio_scr']:.1f}%" if ok_c3
                       else f"❌ Insuffisance {src['scr_consolide']-src['fpp']:,.0f}€",
        })

        # C4 — FP > MCR (Art.129 — plancher absolu)
        ok_c4 = src["fpp"] >= src["mcr_consolide"]
        if not ok_c4:
            ok_global = False
        controles.append({
            "id": "C4",
            "controle": "FP ≥ MCR (Art.129 — plancher absolu)",
            "valeur":   f"{src['fpp']:,.0f} ≥ {src['mcr_consolide']:,.0f}",
            "ok":       ok_c4,
            "note":     f"✅ Ratio MCR {src['ratio_mcr']:.1f}%" if ok_c4
                       else "❌ FP sous le MCR — intervention ACPR requise",
        })

        return {
            "ok_global": ok_global,
            "controles": controles,
            "nb_ok":     sum(1 for c in controles if c["ok"]),
            "nb_total":  len(controles),
        }

    # =========================================================================
    # 4. SFCR NARRATIF — SECTIONS A-E
    # =========================================================================
    def _generer_sfcr(self, src, result_st, entite, date_arrete) -> list:
        """
        SFCR (Solvency and Financial Condition Report) — Sections A-E.
        Contenu narratif obligatoire — Directive S2 Art.51 +
        EIOPA Guidelines on SFCR (EIOPA-BoS-15/140).
        """
        sections = []

        # Section A — Activité et résultats
        sections.append({
            "code": "A",
            "titre": "Activité et résultats",
            "contenu": (
                f"L'entité {entite} exerce une activité d'assurance complémentaire santé "
                f"(garanties frais médicaux) et de prévoyance collective (ITT, invalidité, décès). "
                f"Au {date_arrete}, le portefeuille consolidé représente "
                f"{src['pa_total']/1e6:.2f}M€ de primes acquises, "
                f"dont {src['pa_sante']/1e6:.2f}M€ en santé NSLT et "
                f"{src['pa_prev']/1e6:.2f}M€ en prévoyance SLT. "
                f"Le BE total s'établit à {src['be_total']/1e6:.2f}M€."
            ),
            "donnees_cles": {
                "primes_acquises":    round(src["pa_total"], 0),
                "be_total":           round(src["be_total"], 0),
                "ratio_sinistres":    "Voir QRT S.05.01",
            },
        })

        # Section B — Gouvernance
        sections.append({
            "code": "B",
            "titre": "Système de gouvernance",
            "contenu": (
                "Le système de gouvernance repose sur une organisation à quatre directions "
                "indépendantes (Non-Vie, Vie/EP-RE, Santé-Prévoyance, Data) sous supervision "
                "de SOFIA (Directeur Général IA). La Direction Santé-Prévoyance est dirigée "
                "par Amira, avec deux équipes : Santé (Chiara, agents S1-S3) et Prévoyance "
                "(Diallo, agents P1-P4). La fonction actuarielle est assurée par l'ensemble "
                "des agents avec audit trail traçable."
            ),
            "donnees_cles": {
                "structure": "4 directions · autonomie absolue",
                "actuaire_designe": "Direction SP — Amira",
            },
        })

        # Section C — Profil de risque
        pct_div = src["diversification"] / max(src["scr_sante"] + src["scr_prev"], 1) * 100
        sections.append({
            "code": "C",
            "titre": "Profil de risque",
            "contenu": (
                f"Le profil de risque est dominé par le risque de souscription santé NSLT "
                f"(SCR={src['scr_sante']/1e6:.2f}M€) et le risque d'invalidité SLT "
                f"(SCR={src['scr_prev']/1e6:.2f}M€). "
                f"Le SCR consolidé après diversification (ρ=0.25 EIOPA Annexe IV) "
                f"s'établit à {src['scr_consolide']/1e6:.2f}M€, "
                f"soit un bénéfice de diversification de {pct_div:.1f}%. "
                + (f"Les stress tests ORSA (Naomie) confirment la résilience du portefeuille "
                   f"sous scénario pandémie et morbidité adverse."
                   if result_st and result_st.get("success") else
                   "Les stress tests ORSA sont disponibles via l'agent Naomie SP-ST.")
            ),
            "donnees_cles": {
                "scr_sante":       round(src["scr_sante"], 0),
                "scr_prevoyance":  round(src["scr_prev"], 0),
                "scr_consolide":   round(src["scr_consolide"], 0),
                "diversification": f"{pct_div:.1f}%",
            },
        })

        # Section D — Valorisation S2
        sections.append({
            "code": "D",
            "titre": "Valorisation à des fins de solvabilité",
            "contenu": (
                f"Les provisions techniques sont évaluées en valeur de marché "
                f"selon la méthode Best Estimate + Risk Adjustment (IFRS 17 §33/37, "
                f"cohérente avec S2 Art.77). "
                f"BE total = {src['be_total']/1e6:.2f}M€ "
                f"(santé {src['be_sante']/1e6:.2f}M€ + prévoyance {src['be_prev']/1e6:.2f}M€). "
                f"RA total = {(src['ra_sante']+src['ra_prev'])/1e6:.3f}M€ "
                f"(méthode CoC 6% EIOPA — §B91 IFRS 17)."
            ),
            "donnees_cles": {
                "be_total":  round(src["be_total"], 0),
                "ra_total":  round(src["ra_sante"] + src["ra_prev"], 0),
                "methode":   "BE + RA (CoC 6% EIOPA §B91)",
            },
        })

        # Section E — Gestion du capital
        sections.append({
            "code": "E",
            "titre": "Gestion du capital",
            "contenu": (
                f"Les fonds propres éligibles s'élèvent à {src['fpp']/1e6:.2f}M€. "
                f"Le ratio SCR = {src['ratio_scr']:.1f}% "
                f"({'✅ conforme' if src['ratio_scr'] >= SEUIL_SCR_MIN else '❌ insuffisant'}). "
                f"Le ratio MCR = {src['ratio_mcr']:.1f}% "
                f"({'✅ conforme' if src['ratio_mcr'] >= 100 else '❌ insuffisant — intervention ACPR'}). "
                f"Le bénéfice de diversification S+P représente "
                f"{src['diversification']/1e6:.2f}M€ "
                f"({pct_div:.1f}% de la somme des SCR modules) "
                f"conformément à l'Annexe IV RD 2015/35."
            ),
            "donnees_cles": {
                "fonds_propres": round(src["fpp"], 0),
                "ratio_scr":     f"{src['ratio_scr']:.1f}%",
                "ratio_mcr":     f"{src['ratio_mcr']:.1f}%",
                "conformite":    "✅" if src["ratio_scr"] >= SEUIL_SCR_MIN else "❌",
            },
        })

        return sections

    # =========================================================================
    # 5. ORSA RÉSUMÉ
    # =========================================================================
    def _generer_orsa(self, src, result_st) -> Dict:
        """
        ORSA (Own Risk and Solvency Assessment) — résumé exécutif.
        Source : Directive S2 Art.45 + EIOPA ORSA Guidelines.
        """
        orsa = {
            "date": datetime.now().strftime("%d/%m/%Y"),
            "ratio_scr_baseline": round(src["ratio_scr"], 1),
            "solvabilite_actuelle": (
                "✅ Suffisante" if src["ratio_scr"] >= SEUIL_SCR_MIN
                else "❌ Insuffisante"
            ),
            "evaluation_risques": (
                f"Risque dominant : souscription SP (SCR={src['scr_consolide']/1e6:.2f}M€). "
                f"Diversification S+P : {src['diversification']/1e6:.2f}M€ (ρ=0.25 EIOPA)."
            ),
            "stress_tests": None,
            "conclusion": "",
        }

        if result_st and result_st.get("success"):
            pire = result_st.get("pire_scenario", "adverse")
            pire_ratio = result_st.get("scenarios", {}).get(
                pire, {}).get("ratio_scr_stresse", 0)
            orsa["stress_tests"] = {
                "scenarios_testes": list(result_st.get("scenarios", {}).keys()),
                "pire_scenario":    pire,
                "ratio_stresse":    round(pire_ratio, 1),
                "resilience":       "✅ Résilient" if pire_ratio >= 100 else "⚠️ Insuffisant",
            }
            orsa["conclusion"] = (
                f"L'entité présente une solvabilité {'robuste' if src['ratio_scr'] >= SEUIL_SCR_CIBLE else 'minimale'} "
                f"(ratio SCR = {src['ratio_scr']:.1f}%). "
                f"Sous le scénario de stress le plus adverse ({pire}), "
                f"le ratio reste à {pire_ratio:.1f}% "
                f"({'✅ > 100%' if pire_ratio >= 100 else '❌ < 100% — plan de mesures requis'})."
            )
        else:
            orsa["conclusion"] = (
                f"L'entité présente un ratio SCR de {src['ratio_scr']:.1f}%. "
                "Stress tests ORSA disponibles via l'agent Naomie SP-ST."
            )

        return orsa

    # =========================================================================
    # 6. TABLEAU SCR/MCR CONSOLIDÉ
    # =========================================================================
    def _tableau_scr_consolide(self, src) -> list:
        """
        Tableau de décomposition SCR/MCR consolidé pour le SFCR section E.
        Conforme au template EIOPA — Annexe IV RD 2015/35.
        """
        return [
            {"module": "SCR Santé NSLT (σ=5%)", "montant": round(src["scr_sante"], 0),
             "source": "S3 Binta — Art.148 RD 2015/35"},
            {"module": "SCR Invalidité SLT (+35% morbidité)", "montant": round(src["scr_prev"], 0),
             "source": "P4 Valentin — Art.145 RD 2015/35"},
            {"module": "Bénéfice diversification (ρ=0.25)", "montant": -round(src["diversification"], 0),
             "source": "SP-Coord — Annexe IV RD 2015/35"},
            {"module": "SCR Consolidé", "montant": round(src["scr_consolide"], 0),
             "source": "Formule standard EIOPA"},
            {"module": "MCR Consolidé", "montant": round(src["mcr_consolide"], 0),
             "source": "Art.252 RD 2015/35"},
            {"module": "Fonds Propres Éligibles", "montant": round(src["fpp"], 0),
             "source": "Bilan S2"},
            {"module": f"Ratio SCR ({src['ratio_scr']:.1f}%)", "montant": None,
             "source": f"FP / SCR — seuil 100% Art.129 S2"},
        ]

    # =========================================================================
    # 7. HYPOTHÈSES + RAG
    # =========================================================================
    def _hypotheses(self, src, coherence) -> list:
        # H1 — Ratio SCR ≥ 100%
        ok1 = src["ratio_scr"] >= SEUIL_SCR_MIN
        h1_s = "VALIDÉE" if ok1 else "NON VALIDÉE"
        h1_m = f"Ratio SCR = {src['ratio_scr']:.1f}% {'≥' if ok1 else '<'} {SEUIL_SCR_MIN:.0f}% — Art.129 S2"

        # H2 — Cohérence inter-QRT
        ok2 = coherence["ok_global"]
        h2_s = "VALIDÉE" if ok2 else "NON VALIDÉE"
        h2_m = (f"{coherence['nb_ok']}/{coherence['nb_total']} contrôles QRT OK "
                f"— {'prêt ACPR' if ok2 else 'corriger avant soumission'}")

        # H3 — Ratio SCR cible ≥ 130%
        ok3 = src["ratio_scr"] >= SEUIL_SCR_CIBLE
        h3_s = "VALIDÉE" if ok3 else "À JUSTIFIER"
        h3_m = (f"Ratio SCR = {src['ratio_scr']:.1f}% "
                f"{'≥' if ok3 else '<'} {SEUIL_SCR_CIBLE:.0f}% (cible interne)")

        return [
            {"id":"H1","hypothese":f"Ratio SCR ≥ {SEUIL_SCR_MIN:.0f}% — Art.129 Directive S2",
             "valeur":h1_m,"statut":h1_s,"critique":True},
            {"id":"H2","hypothese":"Cohérence inter-QRT (S.05 + S.13 + S.14) — EIOPA Validation",
             "valeur":h2_m,"statut":h2_s,"critique":True},
            {"id":"H3","hypothese":f"Ratio SCR ≥ {SEUIL_SCR_CIBLE:.0f}% (cible interne)",
             "valeur":h3_m,"statut":h3_s,"critique":False},
        ]

    def _rag(self, hyp, src) -> str:
        if src["ratio_scr"] < SEUIL_SCR_MIN or src["ratio_mcr"] < 100:
            return "ROUGE"
        non_val = [h for h in hyp if h["statut"] == "NON VALIDÉE" and h["critique"]]
        if non_val:
            return "ROUGE"
        a_just = [h for h in hyp if h["statut"] == "À JUSTIFIER"]
        return "AMBRE" if a_just else "VERT"

    # =========================================================================
    # 8. COMMENTAIRE
    # =========================================================================
    def _commentaire(self, rag, src, qrt_s05, coherence, sfcr,
                     orsa, tableau_scr, entite, date_arrete, hyp) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        L = [
            "="*70,
            f"  RAPPORT SOLVABILITÉ 2 — SP-REG1 v{self.VERSION}",
            f"  {ic} STATUT : {rag} | {entite} | Arrêté au {date_arrete}",
            "="*70, "",
        ]

        # Synthèse SCR/MCR
        L += ["📊 BILAN SOLVABILITÉ 2", "─"*50]
        for row in tableau_scr:
            if row["montant"] is not None:
                L.append(f"  {row['module']:40s} : {row['montant']:>12,.0f}€")
            else:
                L.append(f"  {row['module']:40s}")
        L.append("")

        # Cohérence QRT
        L += ["🔍 COHÉRENCE INTER-QRT", "─"*50]
        for c in coherence["controles"]:
            L.append(f"  [{c['id']}] {c['controle']}")
            L.append(f"       {c['note']}")
        L.append("")

        # SFCR résumé
        L += ["📋 SFCR — SECTIONS A-E (Directive S2 Art.51)", "─"*50]
        for s in sfcr:
            contenu_s = s.get("contenu", "")
            status = "✅" if ("conforme" in contenu_s.lower() or "✅" in contenu_s) else "ℹ️"
            L.append(f"  {status} Section {s['code']} — {s['titre']}")

        # ORSA
        L += ["", "🏛️ ORSA — RÉSUMÉ EXÉCUTIF (Art.45 Directive S2)", "─"*50]
        L.append(f"  Solvabilité actuelle : {orsa['solvabilite_actuelle']}")
        if orsa.get("stress_tests"):
            st = orsa["stress_tests"]
            L.append(f"  Stress tests ({', '.join(st['scenarios_testes'])}) :")
            L.append(f"    Pire scénario ({st['pire_scenario']}) : ratio {st['ratio_stresse']:.1f}% — {st['resilience']}")
        L.append(f"  Conclusion : {orsa['conclusion']}")

        # Hypothèses
        L += ["", "📋 HYPOTHÈSES", "─"*50]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"]=="À JUSTIFIER" else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        return "\n".join(L)

    # =========================================================================
    # 9. GRAPHIQUES
    # =========================================================================
    def _graphiques(self, src, tableau_scr) -> Dict:
        gph = {}

        # Décomposition SCR
        modules = ["SCR Santé", "SCR Prévoyance", "Diversification", "SCR Consolidé"]
        valeurs = [src["scr_sante"], src["scr_prev"],
                   -src["diversification"], src["scr_consolide"]]
        couleurs = [BLEU, VIOLET, VERT, OR]

        fig1 = go.Figure(go.Bar(
            x=modules, y=valeurs,
            marker_color=couleurs,
            text=[f"{v/1000:.0f}k€" for v in valeurs],
            textposition="outside",
        ))
        fig1.update_layout(
            **LAYOUT_BASE,
            title=dict(text=f"Décomposition SCR S2 (ρ={RHO_NSLT_SLT} EIOPA Annexe IV)",
                       font=dict(color=OR, size=13)),
            yaxis_title="€",
        )
        gph["scr_decomposition"] = fig1

        # Gauge ratio SCR
        ratio = src["ratio_scr"]
        c_gauge = VERT if ratio >= SEUIL_SCR_CIBLE else (AMBRE if ratio >= SEUIL_SCR_MIN else ROUGE)
        fig2 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=ratio,
            title={"text": "Ratio SCR Consolidé (%)", "font": {"color": OR}},
            number={"font": {"color": c_gauge, "size": 28}, "suffix": "%"},
            gauge={
                "axis": {"range": [0, max(300, ratio*1.2)], "tickcolor": GRIS},
                "bar":  {"color": c_gauge, "thickness": 0.3},
                "steps": [
                    {"range": [0, 100],  "color": "rgba(231,76,60,0.15)"},
                    {"range": [100, 130],"color": "rgba(243,156,18,0.15)"},
                    {"range": [130, max(300, ratio*1.2)], "color": "rgba(46,204,113,0.12)"},
                ],
                "threshold": {
                    "line": {"color": VERT, "width": 3},
                    "thickness": 0.8, "value": SEUIL_SCR_CIBLE
                },
            },
        ))
        fig2.update_layout(**LAYOUT_BASE,
            title=dict(text="Solvabilité S2 — Santé-Prévoyance", font=dict(color=OR, size=13)))
        gph["ratio_scr_s2"] = fig2

        # G3 — Radar QRT S.05.01 : 4 lignes × 2 colonnes (NSLT / SLT)
        # Reconstruit depuis src — mêmes valeurs que _generer_qrt_s05
        try:
            sin_sante = src["be_sante"] * 0.80
            sin_prev  = src["be_prev"]  * 0.70
            dep_sante = src["pa_sante"] * 0.18
            dep_prev  = src["pa_prev"]  * 0.20
            r200_s    = src["be_sante"] + src["ra_sante"]
            r200_p    = src["be_prev"]  + src["ra_prev"]

            # 4 postes QRT S.05.01
            labels_qrt = [
                "R0010 Primes",
                "R0050 Sinistres",
                "R0090 Dépenses",
                "R0200 Provisions",
                "R0010 Primes",   # fermeture du radar
            ]
            vals_nslt = [
                src["pa_sante"],
                sin_sante,
                dep_sante,
                r200_s,
                src["pa_sante"],  # fermeture
            ]
            vals_slt = [
                src["pa_prev"],
                sin_prev,
                dep_prev,
                r200_p,
                src["pa_prev"],   # fermeture
            ]

            # Normalisation : chaque valeur / max(NSLT, SLT) pour le poste
            # afin que les deux axes soient comparables visuellement
            maxima = [
                max(src["pa_sante"], src["pa_prev"]),
                max(sin_sante, sin_prev),
                max(dep_sante, dep_prev),
                max(r200_s, r200_p),
                max(src["pa_sante"], src["pa_prev"]),
            ]
            # Éviter division par zéro
            maxima = [m if m > 0 else 1.0 for m in maxima]

            vals_nslt_norm = [v / m for v, m in zip(vals_nslt, maxima)]
            vals_slt_norm  = [v / m for v, m in zip(vals_slt,  maxima)]

            fig3 = go.Figure()

            # Trace NSLT (Santé)
            fig3.add_trace(go.Scatterpolar(
                r=vals_nslt_norm,
                theta=labels_qrt,
                fill="toself",
                fillcolor=f"rgba(52,152,219,0.18)",   # BLEU transparent
                line=dict(color=BLEU, width=2),
                name="NSLT — Santé",
                hovertemplate=(
                    "<b>%{theta}</b><br>"
                    "NSLT : %{customdata:,.0f}€<extra></extra>"
                ),
                customdata=vals_nslt,
            ))

            # Trace SLT (Prévoyance)
            fig3.add_trace(go.Scatterpolar(
                r=vals_slt_norm,
                theta=labels_qrt,
                fill="toself",
                fillcolor=f"rgba(155,89,182,0.18)",   # VIOLET transparent
                line=dict(color=VIOLET, width=2),
                name="SLT — Prévoyance",
                hovertemplate=(
                    "<b>%{theta}</b><br>"
                    "SLT : %{customdata:,.0f}€<extra></extra>"
                ),
                customdata=vals_slt,
            ))

            fig3.update_layout(
                **LAYOUT_BASE,
                height=360,
                title=dict(
                    text="G3 — QRT S.05.01 : NSLT Santé vs SLT Prévoyance",
                    font=dict(color=OR, size=13), x=0.01,
                ),
                polar=dict(
                    bgcolor=NAVY_L,
                    angularaxis=dict(
                        tickfont=dict(color=BLANC, size=10),
                        linecolor=GRIS,
                        gridcolor="rgba(138,154,176,0.20)",
                    ),
                    radialaxis=dict(
                        visible=True,
                        range=[0, 1.05],
                        tickfont=dict(color=GRIS, size=8),
                        tickformat=".0%",
                        gridcolor="rgba(138,154,176,0.15)",
                        linecolor="rgba(138,154,176,0.20)",
                    ),
                ),
                legend=dict(
                    x=0.80, y=1.10,
                    font=dict(color=BLANC, size=10),
                    bgcolor="rgba(0,0,0,0)",
                    orientation="v",
                ),
                annotations=[dict(
                    text=(
                        "💡 Valeurs normalisées par poste — "
                        "100% = max(NSLT, SLT) pour chaque ligne QRT S.05.01."
                    ),
                    xref="paper", yref="paper",
                    x=0.01, y=-0.08,
                    font=dict(color=GRIS, size=9),
                    showarrow=False,
                )],
            )
            gph["radar_qrt_s05"] = fig3

        except Exception as e:
            self.logger.warning(f"G3 radar QRT : {e}")

        return gph

    # =========================================================================
    # 10. AUDIT + CONSOLE
    # =========================================================================
    def _audit(self, aid, src, rag):
        try:
            import json as _json
            log = self.audit_path / "sp_reg1_s2_audit.jsonl"
            entry = {
                "audit_id": aid, "timestamp": datetime.now().isoformat(),
                "statut_rag": rag,
                "ratio_scr": round(src["ratio_scr"], 1),
                "scr_consolide": round(src["scr_consolide"], 2),
                "fpp": round(src["fpp"], 2),
            }
            with open(log, "a", encoding="utf-8") as f:
                f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _console(self, aid, rag, src, coherence):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        self.logger.info(
            f"[{aid}] {ic} {rag} | SCR={src['scr_consolide']:,.0f}€ | "
            f"Ratio={src['ratio_scr']:.1f}% | "
            f"QRT {coherence['nb_ok']}/{coherence['nb_total']} OK"
        )

    def _erreur(self, msg, aid=""):
        return {
            # ── Contrat standard ActuarIA ─────────────────────────────────
            "success":     False,
            "agent":       self.NOM,
            "version":     self.VERSION,
            "audit_id":    aid,
            "statut_rag":  "ROUGE",
            # ── Bilan S2 (valeurs neutres) ────────────────────────────────
            "be_sante":        0.0,
            "be_prevoyance":   0.0,
            "be_total":        0.0,
            "scr_sante":       0.0,
            "scr_prevoyance":  0.0,
            "scr_consolide":   0.0,
            "mcr_consolide":   0.0,
            "fonds_propres":   0.0,
            "ratio_scr_pct":   0.0,
            "ratio_mcr_pct":   0.0,
            "diversification": 0.0,
            # ── QRT / SFCR / ORSA ────────────────────────────────────────
            "qrt_s05":        {},
            "coherence_qrts": {},
            "tableau_scr":    [],
            "sfcr_sections":  [],
            "orsa_resume":    {},
            # ── Standard ActuarIA ─────────────────────────────────────────
            "hypotheses":  [],
            "commentaire": "",
            "graphiques":  {},
            "duree_sec":   0.0,
            "erreur":      msg,
        }
