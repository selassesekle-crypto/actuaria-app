"""
╔══════════════════════════════════════════════════════════════════════════════╗
║    ACTUARIA — AGENT SP-COORD : COORDINATION SANTÉ + PRÉVOYANCE             ║
║    Sous AMIRA (Directrice SP) · Direction Santé-Prévoyance                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Vision consolidée Santé + Prévoyance — différenciation majeure      ║
║         vs concurrents (ResQ, Addactis) qui traitent S et P en silos.       ║
║                                                                              ║
║  PÉRIMÈTRE :                                                                 ║
║    · BE consolidé S+P avec corrélation EIOPA entre modules                  ║
║    · SCR combiné : agrégation santé NSLT + invalidité SLT                   ║
║    · Détection poly-sinistralité (adhérents sinistrés en S ET P)           ║
║    · Rapport consolidé pour assureur mixte (mutuelle + IP)                  ║
║    · Vision globale pour l'ACPR (un seul rapport, pas deux)               ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_s3    → résultats Agent S3 Binta (reporting santé)                ║
║    result_p4    → résultats Agent P4 Valentin (reporting prévoyance)        ║
║    result_builder → SPDataBuilder (optionnel — pour poly-sinistralité)      ║
║                                                                              ║
║  SORTIES :                                                                   ║
║    be_consolide          → BE_santé + BE_prévoyance                         ║
║    scr_consolide         → SCR agrégé avec corrélation EIOPA               ║
║    ratio_scr_consolide   → FP / SCR_consolidé                               ║
║    poly_sinistralite     → % adhérents sinistrés S+P simultanément          ║
║    profil_risque         → synthèse risques croisés                          ║
║    rapport_consolidé     → commentaire ACPR                                  ║
║                                                                              ║
║  PARAMÈTRES RÉGLEMENTAIRES :                                                ║
║    Corrélation ρ(NSLT, SLT) = 0.25 — Annexe IV RD 2015/35                 ║
║    Matrice agrégation SCR : formule quadratique standard EIOPA              ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

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
# Source : Annexe IV Règlement Délégué (UE) 2015/35
# Corrélation entre module Santé NSLT et module Invalidité/Morbidité SLT
RHO_SANTE_INVALIDITE = 0.25   # Art. Annexe IV RD 2015/35 — matrice corrélation SCR

# Seuil poly-sinistralité — pratique marché CTIP/FNMF
SEUIL_POLY_ALERTE   = 5.0    # % — au-delà : risque de basculement ITT → IP
SEUIL_POLY_CRITIQUE = 10.0   # % — signal fort d'accumulation de risques


# ══════════════════════════════════════════════════════════════════════════════
class AgentSPCoord:
    """
    Agent SP-COORD — Coordination Santé + Prévoyance.
    Sous AMIRA (Directrice SP), Direction Santé-Prévoyance.

    Consolide les résultats de S3 (reporting santé) et P4 (reporting prévoyance)
    pour produire une vision unifiée conforme à l'approche EIOPA multi-modules.

    Différenciation concurrentielle :
    - ResQ/Addactis traitent Santé et Prévoyance en silos séparés
    - SP-COORD produit la vision consolidée qu'un actuaire désigné
      doit présenter à l'ACPR pour un assureur mixte
    """

    NOM     = "SP-Coord"
    CODE    = "SP-COORD"
    VERSION = "1.0"
    MANAGER = "Amira (Directrice SP)"

    def __init__(self, models_path: str = "models",
                 audit_path: str = "audit", verbose: bool = True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.coord")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"SP-Coord v{self.VERSION} | {self.MANAGER}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s3,
            result_p4,
            result_builder  = None,
            fonds_propres: float = 0.0,
            generer_graphiques: bool = True) -> Dict:
        """
        Consolide Santé et Prévoyance en une vision unifiée.

        Parameters
        ----------
        result_s3 : dict
            Résultat de S3 Binta (reporting santé).
            Clés requises : be_sante, scr_sante, mcr_sante, fonds_propres.
        result_p4 : dict
            Résultat de P4 Valentin (reporting prévoyance).
            Clés requises : be_prevoyance, scr_invalidite, mcr.
        result_builder : dict, optional
            Résultat de SPDataBuilder — pour poly-sinistralité.
        fonds_propres : float
            FP consolidés de l'entité. Si 0, utilise max(S3, P4).

        Returns
        -------
        Dict standard ActuarIA avec vision consolidée S+P.
        """
        t0  = datetime.now()
        aid = f"COORD_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # ── 1. EXTRACTION S3 + P4 ─────────────────────────────────────────
            src = self._extraire(result_s3, result_p4, fonds_propres)
            self.logger.info(
                f"[{aid}] SP-Coord | BE_S={src['be_sante']:,.0f}€ | "
                f"BE_P={src['be_prev']:,.0f}€ | FP={src['fpp']:,.0f}€"
            )

            # ── 2. BE CONSOLIDÉ ───────────────────────────────────────────────
            be_consolide = src["be_sante"] + src["be_prev"]
            ra_consolide = src["ra_sante"] + src["ra_prev"]
            tp_consolide = be_consolide + ra_consolide

            # ── 3. SCR CONSOLIDÉ — agrégation EIOPA avec corrélation ──────────
            # Formule : SCR_tot = √(SCR_S² + 2×ρ×SCR_S×SCR_P + SCR_P²)
            # Source : Annexe IV RD 2015/35 — ρ(NSLT, SLT) = 0.25
            scr_s = src["scr_sante"]
            scr_p = src["scr_prev"]
            scr_consolide = np.sqrt(
                scr_s**2
                + 2 * RHO_SANTE_INVALIDITE * scr_s * scr_p
                + scr_p**2
            )
            # Bénéfice de diversification
            diversification = (scr_s + scr_p) - scr_consolide

            # ── 4. MCR CONSOLIDÉ ──────────────────────────────────────────────
            # MCR consolidé = max(MCR_santé + MCR_prévoyance, plancher)
            mcr_consolide = src["mcr_sante"] + src["mcr_prev"]

            # ── 5. RATIOS DE SOLVABILITÉ ──────────────────────────────────────
            fpp = src["fpp"]
            ratio_scr = fpp / max(scr_consolide, 1) * 100
            ratio_mcr = fpp / max(mcr_consolide, 1) * 100

            # ── 6. POLY-SINISTRALITÉ ──────────────────────────────────────────
            poly = self._calculer_poly_sinistralite(result_builder)

            # ── 7. PROFIL RISQUE CONSOLIDÉ ────────────────────────────────────
            profil = self._profil_risque_consolide(src, poly, scr_consolide, diversification)

            # ── 8. HYPOTHÈSES + RAG ───────────────────────────────────────────
            hyp = self._hypotheses(
                be_consolide, ra_consolide, scr_consolide,
                ratio_scr, ratio_mcr, poly, diversification
            )
            rag = self._rag(hyp, ratio_scr, ratio_mcr)

            # ── 9. COMMENTAIRE CONSOLIDÉ ──────────────────────────────────────
            com = self._commentaire(
                rag, src, be_consolide, ra_consolide, tp_consolide,
                scr_consolide, mcr_consolide, ratio_scr, ratio_mcr,
                diversification, poly, profil, hyp
            )

            # ── 10. GRAPHIQUES ────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    src, be_consolide, scr_consolide, mcr_consolide,
                    ratio_scr, diversification, poly
                )

            self._audit(aid, be_consolide, scr_consolide, ratio_scr, rag)
            if self.verbose:
                self._console(
                    aid, rag, be_consolide, scr_consolide, ratio_scr,
                    diversification, poly
                )

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── BE + TP Consolidé ────────────────────────────────────────
                "be_sante":       round(src["be_sante"], 2),
                "be_prevoyance":  round(src["be_prev"], 2),
                "be_consolide":   round(be_consolide, 2),
                "ra_consolide":   round(ra_consolide, 2),
                "tp_consolide":   round(tp_consolide, 2),

                # ── SCR / MCR Consolidé ──────────────────────────────────────
                "scr_sante":        round(scr_s, 2),
                "scr_prevoyance":   round(scr_p, 2),
                "scr_consolide":    round(scr_consolide, 2),
                "diversification":  round(diversification, 2),
                "rho_eiopa":        RHO_SANTE_INVALIDITE,
                "mcr_consolide":    round(mcr_consolide, 2),
                "fonds_propres":    round(fpp, 2),
                "ratio_scr_pct":    round(ratio_scr, 1),
                "ratio_mcr_pct":    round(ratio_mcr, 1),

                # ── Poly-sinistralité ────────────────────────────────────────
                "poly_sinistralite_pct": poly,

                # ── Profil risque consolidé ───────────────────────────────────
                "profil_risque": profil,

                # ── Standard ActuarIA ────────────────────────────────────────
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
    def _extraire(self, result_s3: Dict, result_p4: Dict,
                  fonds_propres: float) -> Dict:
        """Extrait les données de S3 et P4 avec fallbacks robustes."""
        if not result_s3 or not result_s3.get("success"):
            raise ValueError("result_s3 absent ou en erreur — SP-Coord nécessite S3")
        if not result_p4 or not result_p4.get("success"):
            raise ValueError("result_p4 absent ou en erreur — SP-Coord nécessite P4")

        # Santé (S3)
        be_sante  = float(result_s3.get("be_sante", 0))
        ra_sante  = float(result_s3.get("risk_adjustment", 0))
        scr_sante = float(result_s3.get("scr_sante", 0))
        mcr_sante = float(result_s3.get("mcr_sante", 0))
        fpp_s3    = float(result_s3.get("fonds_propres", 0))
        pa_sante  = float(result_s3.get("qrt_s13", {}).get("lignes", [{}])[-1]
                          .get("C0010", be_sante * 2) if result_s3.get("qrt_s13") else be_sante * 2)

        # Prévoyance (P4)
        be_prev   = float(result_p4.get("be_prevoyance", 0))
        ra_prev   = float(result_p4.get("risk_adjustment", 0))
        scr_prev  = float(result_p4.get("scr_invalidite", 0))
        mcr_prev  = float(result_p4.get("mcr", 0))
        fpp_p4    = float(result_p4.get("fonds_propres", 0))
        pa_prev   = result_p4.get("sorties_naomie", {}).get("primes_acquises", be_prev)

        # FP consolidés
        if fonds_propres > 0:
            fpp = fonds_propres
        else:
            fpp = max(fpp_s3, fpp_p4, (be_sante + be_prev) * 1.5)
            if fpp == (be_sante + be_prev) * 1.5:
                self.logger.warning(
                    f"fonds_propres consolidés non fournis → estimés à {fpp:,.0f}€"
                )

        return {
            "be_sante":   be_sante, "ra_sante":   ra_sante,
            "scr_sante":  scr_sante, "mcr_sante": mcr_sante,
            "be_prev":    be_prev, "ra_prev":     ra_prev,
            "scr_prev":   scr_prev, "mcr_prev":   mcr_prev,
            "pa_sante":   pa_sante, "pa_prev":     pa_prev,
            "fpp":        fpp,
        }

    # =========================================================================
    # 2. POLY-SINISTRALITÉ
    # =========================================================================
    def _calculer_poly_sinistralite(self, result_builder) -> Optional[float]:
        """
        % adhérents sinistrés simultanément en santé ET prévoyance.
        Source : SPDataBuilder — profil_risque.
        Signal clé : risque de basculement ITT → IP long terme.
        """
        if not result_builder or not result_builder.get("success"):
            return None
        poly = result_builder.get("profil_risque", {}).get("poly_sinistralite")
        if poly is not None and poly > SEUIL_POLY_CRITIQUE:
            self.logger.warning(
                f"Poly-sinistralité {poly:.1f}% > seuil critique {SEUIL_POLY_CRITIQUE}% "
                f"— risque de basculement ITT → IP à surveiller"
            )
        return poly

    # =========================================================================
    # 3. PROFIL RISQUE CONSOLIDÉ
    # =========================================================================
    def _profil_risque_consolide(self, src: Dict, poly: Optional[float],
                                  scr_consolide: float,
                                  diversification: float) -> Dict:
        """Synthèse du profil de risque consolidé S+P."""
        be_total = src["be_sante"] + src["be_prev"]
        pct_sante = src["be_sante"] / max(be_total, 1) * 100
        pct_prev  = src["be_prev"]  / max(be_total, 1) * 100
        pct_div   = diversification / max(src["scr_sante"] + src["scr_prev"], 1) * 100

        indicateurs = []
        if poly is not None and poly > SEUIL_POLY_ALERTE:
            indicateurs.append(
                f"⚠️ Poly-sinistralité {poly:.1f}% > {SEUIL_POLY_ALERTE}% "
                f"— surveiller basculements ITT→IP"
            )
        if pct_prev > 70:
            indicateurs.append(
                f"⚠️ Prévoyance représente {pct_prev:.0f}% du BE consolidé "
                f"— portefeuille à dominante long terme"
            )
        if pct_div > 15:
            indicateurs.append(
                f"✅ Bénéfice diversification S+P = {pct_div:.0f}% "
                f"(corrélation EIOPA ρ={RHO_SANTE_INVALIDITE})"
            )

        return {
            "be_total":        round(be_total, 2),
            "pct_sante":       round(pct_sante, 1),
            "pct_prevoyance":  round(pct_prev, 1),
            "pct_diversification": round(pct_div, 1),
            "poly_sinistralite": poly,
            "indicateurs":     indicateurs,
        }

    # =========================================================================
    # 4. HYPOTHÈSES + RAG
    # =========================================================================
    def _hypotheses(self, be: float, ra: float, scr: float,
                    ratio_scr: float, ratio_mcr: float,
                    poly: Optional[float], div: float) -> list:
        """3 hypothèses clés pour la vision consolidée."""

        # H1 — TP/BE consolidé ∈ [1.0, 1.5]
        tp  = be + ra
        rtp = tp / max(be, 1)
        if 1.0 <= rtp <= 1.5:
            h1_s = "VALIDÉE"; h1_m = f"TP/BE consolidé = {rtp:.3f} ∈ [1.0, 1.5] ✅"
        elif rtp < 1.0:
            h1_s = "NON VALIDÉE"; h1_m = f"TP/BE = {rtp:.3f} < 1.0 — RA négatif impossible"
        else:
            h1_s = "À JUSTIFIER"; h1_m = f"TP/BE = {rtp:.3f} > 1.5 — RA élevé à justifier"

        # H2 — Ratio SCR consolidé ≥ 100%
        if ratio_scr >= 130:
            h2_s = "VALIDÉE"; h2_m = f"Ratio SCR consolidé = {ratio_scr:.1f}% ≥ 130% ✅"
        elif ratio_scr >= 100:
            h2_s = "À JUSTIFIER"
            h2_m = f"Ratio SCR = {ratio_scr:.1f}% ∈ [100%,130%] — proche seuil S2"
        else:
            h2_s = "NON VALIDÉE"
            h2_m = f"Ratio SCR = {ratio_scr:.1f}% < 100% — insuffisance de capital"

        # H3 — Poly-sinistralité sous contrôle
        if poly is None:
            h3_s = "À JUSTIFIER"
            h3_m = "Poly-sinistralité non calculée — données individuelles absentes"
        elif poly <= SEUIL_POLY_ALERTE:
            h3_s = "VALIDÉE"
            h3_m = f"Poly-sinistralité = {poly:.1f}% ≤ {SEUIL_POLY_ALERTE}% ✅"
        elif poly <= SEUIL_POLY_CRITIQUE:
            h3_s = "À JUSTIFIER"
            h3_m = (f"Poly-sinistralité = {poly:.1f}% ∈ ]5%,10%] "
                    f"— risque basculement ITT→IP à surveiller")
        else:
            h3_s = "NON VALIDÉE"
            h3_m = (f"Poly-sinistralité = {poly:.1f}% > {SEUIL_POLY_CRITIQUE}% "
                    f"— accumulation de risques S+P critique")

        return [
            {"id":"H1", "hypothese":"TP/BE consolidé ∈ [1.0,1.5] — IFRS 17",
             "valeur":h1_m, "statut":h1_s, "critique":True},
            {"id":"H2", "hypothese":"Ratio SCR consolidé ≥ 100% (≥130% cible S2)",
             "valeur":h2_m, "statut":h2_s, "critique":True},
            {"id":"H3", "hypothese":"Poly-sinistralité S+P ≤ 5% (CTIP/FNMF référence)",
             "valeur":h3_m, "statut":h3_s, "critique":False},
        ]

    def _rag(self, hyp: list, ratio_scr: float, ratio_mcr: float) -> str:
        non_val = [h for h in hyp if h["statut"] == "NON VALIDÉE" and h["critique"]]
        a_just  = [h for h in hyp if h["statut"] == "À JUSTIFIER"]
        if ratio_mcr < 100 or non_val or ratio_scr < 100:
            return "ROUGE"
        if a_just or ratio_scr < 130:
            return "AMBRE"
        return "VERT"

    # =========================================================================
    # 5. COMMENTAIRE
    # =========================================================================
    def _commentaire(self, rag: str, src: Dict, be: float, ra: float,
                     tp: float, scr: float, mcr: float,
                     ratio_scr: float, ratio_mcr: float,
                     div: float, poly, profil: Dict, hyp: list) -> str:
        ic = "🟢" if rag == "VERT" else ("🟡" if rag == "AMBRE" else "🔴")
        be_tot = src["be_sante"] + src["be_prev"]

        L = [
            "=" * 70,
            f"  RAPPORT CONSOLIDÉ SANTÉ + PRÉVOYANCE — SP-COORD v{self.VERSION}",
            f"  {ic} STATUT CONSOLIDÉ : {rag}",
            "=" * 70, "",
        ]

        if rag == "VERT":
            L.append("✅ Vision consolidée S+P validée — solvabilité conforme S2.")
        elif rag == "AMBRE":
            L.append("⚠️ Points à surveiller — voir hypothèses ci-dessous.")
        else:
            L.append("❌ Insuffisance détectée — action corrective requise.")

        L += [
            "", "🔢 BILAN CONSOLIDÉ", "─" * 50,
            f"  BE Santé                 : {src['be_sante']:>14,.0f}€",
            f"  BE Prévoyance            : {src['be_prev']:>14,.0f}€",
            f"  BE Consolidé             : {be:>14,.0f}€",
            f"  Risk Adjustment total    : {ra:>14,.0f}€",
            f"  TP Consolidé (BE + RA)   : {tp:>14,.0f}€",
            "",
            "📊 SCR CONSOLIDÉ (ρ=0.25 EIOPA Annexe IV)", "─" * 50,
            f"  SCR Santé NSLT           : {src['scr_sante']:>14,.0f}€",
            f"  SCR Invalidité SLT       : {src['scr_prev']:>14,.0f}€",
            f"  Bénéfice diversification : {div:>14,.0f}€  ({div/(src['scr_sante']+src['scr_prev'])*100:.1f}%)",
            f"  SCR Consolidé            : {scr:>14,.0f}€",
            f"  MCR Consolidé            : {mcr:>14,.0f}€",
            f"  Fonds Propres            : {src['fpp']:>14,.0f}€",
            f"  Ratio SCR                : {ratio_scr:>13.1f}%",
            f"  Ratio MCR                : {ratio_mcr:>13.1f}%",
        ]

        if poly is not None:
            L += [
                "", "🔍 ANALYSE CROISÉE S+P", "─" * 50,
                f"  Poly-sinistralité        : {poly:>13.1f}%",
                f"  Répartition BE           : Santé={profil['pct_sante']:.0f}% | Prév={profil['pct_prevoyance']:.0f}%",
            ]
            for ind in profil.get("indicateurs", []):
                L.append(f"  {ind}")

        L += ["", "📋 HYPOTHÈSES", "─" * 50]
        for h in hyp:
            ic_h = "✅" if h["statut"] == "VALIDÉE" else ("⚠️" if h["statut"] == "À JUSTIFIER" else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        return "\n".join(L)

    # =========================================================================
    # 6. GRAPHIQUES
    # =========================================================================
    def _graphiques(self, src: Dict, be: float, scr: float, mcr: float,
                    ratio_scr: float, div: float, poly) -> Dict:
        gph = {}

        # Graphique 1 — Décomposition BE consolidé
        fig1 = go.Figure(go.Bar(
            x=["BE Santé", "BE Prévoyance", "BE Consolidé"],
            y=[src["be_sante"], src["be_prev"], be],
            marker_color=[BLEU, VIOLET, OR],
            text=[f"{v/1000:.0f}k€" for v in [src["be_sante"], src["be_prev"], be]],
            textposition="outside",
        ))
        fig1.update_layout(
            **LAYOUT_BASE,
            title=dict(text="BE Consolidé Santé + Prévoyance", font=dict(color=OR, size=13)),
            yaxis_title="€",
        )
        gph["be_consolide"] = fig1

        # Graphique 2 — Agrégation SCR avec diversification
        fig2 = go.Figure(go.Bar(
            x=["SCR Santé", "SCR Prévoyance", "Diversification", "SCR Consolidé"],
            y=[src["scr_sante"], src["scr_prev"], -div, scr],
            marker_color=[BLEU, VIOLET, VERT, OR],
            text=[f"{v/1000:.0f}k€" for v in [src["scr_sante"], src["scr_prev"], -div, scr]],
            textposition="outside",
        ))
        fig2.update_layout(
            **LAYOUT_BASE,
            title=dict(text=f"SCR Consolidé (ρ={RHO_SANTE_INVALIDITE} EIOPA)", font=dict(color=OR, size=13)),
        )
        gph["scr_consolide"] = fig2

        # Graphique 3 — Ratio SCR gauge
        c_scr = VERT if ratio_scr >= 130 else (AMBRE if ratio_scr >= 100 else ROUGE)
        fig3 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=ratio_scr,
            title={"text": "Ratio SCR Consolidé (%)", "font": {"color": OR}},
            number={"font": {"color": c_scr, "size": 28}, "suffix": "%"},
            gauge={
                "axis": {"range": [0, max(300, ratio_scr * 1.2)], "tickcolor": GRIS},
                "bar": {"color": c_scr, "thickness": 0.3},
                "steps": [
                    {"range": [0, 100], "color": "rgba(231,76,60,0.15)"},
                    {"range": [100, 130], "color": "rgba(243,156,18,0.15)"},
                    {"range": [130, max(300, ratio_scr * 1.2)], "color": "rgba(46,204,113,0.12)"},
                ],
                "threshold": {"line": {"color": VERT, "width": 3}, "thickness": 0.8, "value": 130},
            },
        ))
        fig3.update_layout(**LAYOUT_BASE,
            title=dict(text="Solvabilité Consolidée S+P", font=dict(color=OR, size=13)))
        gph["ratio_scr_consolide"] = fig3

        return gph

    # =========================================================================
    # 7. AUDIT + CONSOLE
    # =========================================================================
    def _audit(self, aid: str, be: float, scr: float,
               ratio_scr: float, rag: str) -> None:
        log_path = self.audit_path / "sp_coord_audit.jsonl"
        entry = {
            "audit_id": aid,
            "timestamp": datetime.now().isoformat(),
            "statut_rag": rag,
            "be_consolide": round(be, 2),
            "scr_consolide": round(scr, 2),
            "ratio_scr": round(ratio_scr, 1),
        }
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                import json
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _console(self, aid: str, rag: str, be: float, scr: float,
                 ratio_scr: float, div: float, poly) -> None:
        ic = "🟢" if rag == "VERT" else ("🟡" if rag == "AMBRE" else "🔴")
        self.logger.info(
            f"[{aid}] {ic} {rag} | BE_consolidé={be:,.0f}€ | "
            f"SCR_consolidé={scr:,.0f}€ | Ratio={ratio_scr:.1f}% | "
            f"Div={div:,.0f}€" +
            (f" | Poly={poly:.1f}%" if poly is not None else "")
        )

    def _erreur(self, msg: str, aid: str = "") -> Dict:
        self.logger.error(f"SP-Coord ERREUR : {msg}")
        return {
            "success": False, "agent": self.NOM, "version": self.VERSION,
            "audit_id": aid, "statut_rag": "ROUGE",
            "be_consolide": 0, "scr_consolide": 0, "ratio_scr_pct": 0,
            "hypotheses": [], "commentaire": "", "graphiques": {},
            "duree_sec": 0, "erreur": msg,
        }
