"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT SP-REG2 : CONFORMITÉ IFRS 17 SANTÉ + PRÉVOYANCE         ║
║  Direction Santé-Prévoyance · Équipe Réglementation & Finance              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Rapport IFRS 17 complet pour assureur Santé-Prévoyance.             ║
║                                                                              ║
║  PÉRIMÈTRE IFRS 17 :                                                         ║
║    · BE (Best Estimate) — §33 IFRS 17                                       ║
║    · RA (Risk Adjustment) — §37 IFRS 17 — méthode CoC §B91                 ║
║    · CSM (Contractual Service Margin) — §38 IFRS 17                        ║
║    · LC (Loss Component) — §49 IFRS 17 — contrats onéreux                  ║
║    · Réconciliation BEL d'ouverture → clôture                              ║
║    · Classification PAA vs GMM (§53 — contrats ≤ 1 an)                    ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_s3  → S3 Binta (BE santé, RA, PA)                                ║
║    result_p4  → P4 Valentin (BE prévoyance, RA, PM rentes)                 ║
║    taux_rendement_actif : float (rendement portefeuille actif)               ║
║                                                                              ║
║  RÉFÉRENCES RÉGLEMENTAIRES :                                                 ║
║    IFRS 17 (2017, amendements 2020/2022) — §33/37/38/49/53/B91             ║
║    ACPR — Questions/Réponses IFRS 17 (2023)                                 ║
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

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY = "#0F2E52"; NAVY_L = "#1B3A5C"; NAVY_LL = "#243F6A"; OR = "#C9A84C"
BLANC = "#F0F4F8"; GRIS = "#8A9AB0"; VERT = "#2ECC71"; ROUGE = "#E74C3C"
AMBRE = "#F39C12"; BLEU = "#3498DB"; VIOLET = "#9B59B6"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60), height=300,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
)

# ── Paramètres IFRS 17 ────────────────────────────────────────────────────────
# Source : IFRS 17 §B91 — CoC rate pour le Risk Adjustment
COC_RATE        = 0.06    # 6% — taux EIOPA
# CSM release pattern — amortissement linéaire par défaut (§B119)
CSM_RELEASE_YRS = 5       # durée d'amortissement CSM santé (ans)
# Seuil onérosité : contrat onéreux si CSM < 0 (LC activé)
LC_SEUIL        = 0.0


# ══════════════════════════════════════════════════════════════════════════════
class AgentSPReg2IFRS17:
    """
    Agent SP-REG2 — Conformité IFRS 17 Santé + Prévoyance.
    Direction Santé-Prévoyance · Équipe Réglementation & Finance.

    Produit le rapport IFRS 17 complet : BE, RA, CSM/LC,
    classification PAA vs GMM, réconciliation BEL.
    """

    NOM     = "SP-Reg2-IFRS17"
    CODE    = "SP-REG2"
    VERSION = "1.0"
    MANAGER = "Équipe Réglementation & Finance SP"

    def __init__(self, audit_path="audit", verbose=True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.reg2.ifrs17")
        self.verbose = verbose

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s3,
            result_p4,
            taux_rendement_actif: float = 0.03,
            prime_charged:        float = 0.0,
            generer_graphiques:   bool  = True) -> Dict:
        """
        Paramètres
        ----------
        result_s3 : dict — résultat S3 Binta
        result_p4 : dict — résultat P4 Valentin
        taux_rendement_actif : float — rendement portefeuille actif (IFRS 17 §B72)
        prime_charged : float — primes brutes chargées (PA). Si 0, extraites de S3/P4.
        """
        t0  = datetime.now()
        aid = f"REG2_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            src = self._extraire(result_s3, result_p4, prime_charged)
            self.logger.info(
                f"[{aid}] SP-Reg2 IFRS 17 | BE={src['be_total']:,.0f}€ | "
                f"PA={src['pa_total']:,.0f}€ | r_actif={taux_rendement_actif:.2%}"
            )

            # ── 1. CLASSIFICATION PAA vs GMM ─────────────────────────────────
            # IFRS 17 §53 : PAA autorisé si durée de couverture ≤ 12 mois
            # Santé : généralement PAA (contrats annuels)
            # Prévoyance : GMM obligatoire (rentes, durée > 1 an)
            classif = self._classifier_contrats(src)

            # ── 2. BE (Best Estimate) ─────────────────────────────────────────
            # §33 IFRS 17 : valeur actuelle espérée des flux futurs
            be_sante = src["be_sante"]
            be_prev  = src["be_prev"]
            be_total = be_sante + be_prev

            # ── 3. RA (Risk Adjustment) — méthode CoC §B91 ───────────────────
            ra_sante = src["ra_sante"]
            ra_prev  = src["ra_prev"]
            ra_total = ra_sante + ra_prev

            # ── 4. FULFILLMENT CASH FLOWS (FCF) ──────────────────────────────
            # FCF = BE + RA — §33
            fcf_sante = be_sante + ra_sante
            fcf_prev  = be_prev + ra_prev
            fcf_total = be_total + ra_total

            # ── 5. CSM / LC ───────────────────────────────────────────────────
            # CSM = PA - FCF si PA > FCF (contrat profitable) — §38
            # LC  = FCF - PA si FCF > PA (contrat onéreux) — §49
            pa_sante = src["pa_sante"]
            pa_prev  = src["pa_prev"]

            csm_sante, lc_sante = self._calculer_csm_lc(pa_sante, fcf_sante, "santé")
            csm_prev,  lc_prev  = self._calculer_csm_lc(pa_prev,  fcf_prev,  "prévoyance")

            csm_total = csm_sante + csm_prev
            lc_total  = lc_sante  + lc_prev

            # ── 6. AMORTISSEMENT CSM (release pattern linéaire §B119) ─────────
            csm_release_annuel = csm_total / max(CSM_RELEASE_YRS, 1)

            # ── 7. RÉCONCILIATION BEL (variation nette) ───────────────────────
            recon = self._reconcilier_bel(be_total, ra_total, pa_sante + pa_prev,
                                           taux_rendement_actif)

            # ── 8. HYPOTHÈSES + RAG ───────────────────────────────────────────
            hyp = self._hypotheses(be_total, ra_total, fcf_total,
                                    pa_sante + pa_prev, csm_total, lc_total)
            rag = self._rag(hyp, lc_total, be_total)

            # ── 9. COMMENTAIRE ────────────────────────────────────────────────
            com = self._commentaire(
                rag, classif, be_sante, be_prev, be_total,
                ra_sante, ra_prev, ra_total,
                fcf_sante, fcf_prev, fcf_total,
                csm_sante, csm_prev, csm_total,
                lc_sante, lc_prev, lc_total,
                csm_release_annuel, recon, hyp
            )

            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    be_total, ra_total, fcf_total, csm_total, lc_total,
                    be_sante, be_prev
                )

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── IFRS 17 core ────────────────────────────────────────────
                "be_sante":      round(be_sante, 2),
                "be_prevoyance": round(be_prev, 2),
                "be_total":      round(be_total, 2),
                "ra_sante":      round(ra_sante, 2),
                "ra_prevoyance": round(ra_prev, 2),
                "ra_total":      round(ra_total, 2),
                "fcf_total":     round(fcf_total, 2),
                "csm_total":     round(csm_total, 2),
                "lc_total":      round(lc_total, 2),
                "csm_release_annuel": round(csm_release_annuel, 2),
                "ratio_ra_be":   round(ra_total / max(be_total, 1), 4),

                # ── Classification ────────────────────────────────────────────
                "classification":   classif,

                # ── Réconciliation ────────────────────────────────────────────
                "reconciliation":   recon,

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
    def _extraire(self, result_s3, result_p4, prime_charged):
        if not result_s3 or not result_s3.get("success"):
            raise ValueError("result_s3 requis")
        if not result_p4 or not result_p4.get("success"):
            raise ValueError("result_p4 requis")

        be_sante = float(result_s3.get("be_sante", 0))
        ra_sante = float(result_s3.get("risk_adjustment", 0))
        be_prev  = float(result_p4.get("be_prevoyance", 0))
        ra_prev  = float(result_p4.get("risk_adjustment", 0))

        # PA depuis les sorties disponibles
        qrt = result_s3.get("qrt_s13", {})
        pa_sante = float(result_s3.get("primes_acquises",
                    result_p4.get("sorties_naomie", {}).get("primes_acquises", be_sante * 2)
                    if not qrt else be_sante * 2))
        pa_prev  = float(result_p4.get("sorties_naomie", {}).get("primes_acquises", be_prev * 2))

        if prime_charged > 0:
            # prime_charged override global
            ratio = pa_sante / max(pa_sante + pa_prev, 1)
            pa_sante = prime_charged * ratio
            pa_prev  = prime_charged * (1 - ratio)

        return {
            "be_sante": be_sante, "ra_sante": ra_sante,
            "be_prev":  be_prev,  "ra_prev":  ra_prev,
            "pa_sante": pa_sante, "pa_prev":  pa_prev,
            "be_total": be_sante + be_prev,
        }

    def _classifier_contrats(self, src):
        """
        IFRS 17 §53 : classification PAA vs GMM.
        Santé annuelle → PAA (simplification) | Prévoyance → GMM.
        """
        return {
            "sante": {
                "methode": "PAA",
                "justification": "Contrats santé annuels ≤ 12 mois — IFRS 17 §53",
                "be": round(src["be_sante"], 2),
            },
            "prevoyance": {
                "methode": "GMM",
                "justification": "Rentes IP long terme > 12 mois — IFRS 17 §53",
                "be": round(src["be_prev"], 2),
            },
        }

    def _calculer_csm_lc(self, pa, fcf, label):
        """
        CSM = PA - FCF si contrat profitable (§38)
        LC  = FCF - PA si contrat onéreux (§49)
        """
        diff = pa - fcf
        if diff >= LC_SEUIL:
            csm = diff
            lc  = 0.0
            self.logger.info(
                f"  {label} : CSM={csm:,.0f}€ (contrat profitable)"
            )
        else:
            csm = 0.0
            lc  = abs(diff)
            self.logger.warning(
                f"  {label} : LC={lc:,.0f}€ — CONTRAT ONÉREUX (§49 IFRS 17)"
            )
        return csm, lc

    def _reconcilier_bel(self, be, ra, pa, r_actif):
        """
        Réconciliation simplifiée BEL ouverture → clôture.
        Éléments : sinistres attendus, libération risque, rendement actif.
        Source : IFRS 17 §100-109.
        """
        # Sinistres attendus ≈ 75% du BE (LR typique santé)
        sinistres_att = be * 0.75
        # Libération RA dans l'année ≈ 25% du RA
        ra_liberation = ra * 0.25
        # Rendement actif sur BE (simplification actif/passif IFRS 17 §B72)
        revenu_actif = be * r_actif
        # Variation BE nette
        variation_nette = - sinistres_att - ra_liberation + revenu_actif
        return {
            "be_ouverture":    round(be, 2),
            "sinistres_att":   round(sinistres_att, 2),
            "ra_liberation":   round(ra_liberation, 2),
            "revenu_actif":    round(revenu_actif, 2),
            "variation_nette": round(variation_nette, 2),
            "be_cloture_est":  round(be + variation_nette, 2),
        }

    def _hypotheses(self, be, ra, fcf, pa, csm, lc):
        ratio_ra = ra / max(be, 1)
        lc_pct   = lc / max(pa, 1)

        # H1 — RA ∈ [1%, 20%] BE
        if 0.01 <= ratio_ra <= 0.20:
            h1_s = "VALIDÉE"; h1_m = f"RA/BE = {ratio_ra:.2%} ∈ [1%,20%] ✅"
        else:
            h1_s = "À JUSTIFIER"; h1_m = f"RA/BE = {ratio_ra:.2%} hors plage [1%,20%]"

        # H2 — Pas de LC (contrats non onéreux)
        if lc <= 0:
            h2_s = "VALIDÉE"; h2_m = "Portefeuille non onéreux — CSM positif ✅"
        elif lc_pct < 0.10:
            h2_s = "À JUSTIFIER"
            h2_m = f"LC = {lc:,.0f}€ ({lc_pct:.1%} PA) — onérosité partielle"
        else:
            h2_s = "NON VALIDÉE"
            h2_m = f"LC = {lc:,.0f}€ ({lc_pct:.1%} PA) — portefeuille fortement onéreux"

        # H3 — CSM > 0 (valeur future du contrat)
        if csm > 0:
            h3_s = "VALIDÉE"; h3_m = f"CSM = {csm:,.0f}€ — profit futur reconnu ✅"
        else:
            h3_s = "À JUSTIFIER"; h3_m = "CSM = 0 — pas de profit futur reconnu"

        return [
            {"id":"H1","hypothese":"RA ∈ [1%,20%] BE — cohérence CoC §B91 IFRS 17",
             "valeur":h1_m,"statut":h1_s,"critique":True},
            {"id":"H2","hypothese":"Pas de LC — contrats non onéreux §49 IFRS 17",
             "valeur":h2_m,"statut":h2_s,"critique":True},
            {"id":"H3","hypothese":"CSM > 0 — profit futur §38 IFRS 17",
             "valeur":h3_m,"statut":h3_s,"critique":False},
        ]

    def _rag(self, hyp, lc, be):
        if lc > be * 0.10:
            return "ROUGE"
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val:
            return "ROUGE"
        a_just = [h for h in hyp if h["statut"]=="À JUSTIFIER"]
        return "AMBRE" if a_just else "VERT"

    def _commentaire(self, rag, classif, be_s, be_p, be_tot,
                     ra_s, ra_p, ra_tot, fcf_s, fcf_p, fcf_tot,
                     csm_s, csm_p, csm_tot, lc_s, lc_p, lc_tot,
                     csm_rel, recon, hyp):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        L = [
            "="*70,
            f"  RAPPORT IFRS 17 — SP-REG2 v{self.VERSION}",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
            "📋 CLASSIFICATION DES CONTRATS", "─"*50,
            f"  Santé      : {classif['sante']['methode']} — {classif['sante']['justification']}",
            f"  Prévoyance : {classif['prevoyance']['methode']} — {classif['prevoyance']['justification']}",
            "",
            "🔢 BILAN IFRS 17", "─"*50,
            f"  {'':30s} {'Santé':>12s} {'Prévoyance':>12s} {'Total':>12s}",
            f"  {'BE (Best Estimate)':30s} {be_s:>12,.0f} {be_p:>12,.0f} {be_tot:>12,.0f}",
            f"  {'RA (Risk Adjustment)':30s} {ra_s:>12,.0f} {ra_p:>12,.0f} {ra_tot:>12,.0f}",
            f"  {'FCF (BE + RA)':30s} {fcf_s:>12,.0f} {fcf_p:>12,.0f} {fcf_tot:>12,.0f}",
            f"  {'CSM (profit futur)':30s} {csm_s:>12,.0f} {csm_p:>12,.0f} {csm_tot:>12,.0f}",
            f"  {'LC (perte onérosité)':30s} {lc_s:>12,.0f} {lc_p:>12,.0f} {lc_tot:>12,.0f}",
            "",
            f"  Amortissement CSM annuel : {csm_rel:,.0f}€/an "
            f"(durée {CSM_RELEASE_YRS} ans — §B119 IFRS 17)",
            "",
            "🔄 RÉCONCILIATION BEL", "─"*50,
            f"  BE ouverture      : {recon['be_ouverture']:>12,.0f}€",
            f"  Sinistres attendus: {-recon['sinistres_att']:>12,.0f}€",
            f"  Libération RA     : {-recon['ra_liberation']:>12,.0f}€",
            f"  Revenu actif      : {recon['revenu_actif']:>12,.0f}€",
            f"  Variation nette   : {recon['variation_nette']:>12,.0f}€",
            f"  BE clôture estimé : {recon['be_cloture_est']:>12,.0f}€",
            "",
            "📋 HYPOTHÈSES", "─"*50,
        ]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"]=="À JUSTIFIER" else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]
        return "\n".join(L)

    def _graphiques(self, be, ra, fcf, csm, lc, be_s, be_p):
        gph = {}
        # Waterfall BE → RA → CSM
        fig = go.Figure(go.Bar(
            x=["BE Total","Risk Adj","FCF","CSM","LC"],
            y=[be, ra, fcf, csm, lc],
            marker_color=["#3498DB","#9B59B6","#C9A84C","#2ECC71","#E74C3C"],
        ))
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text="Décomposition IFRS 17 — BE / RA / FCF / CSM / LC",
                       font=dict(color=OR, size=13)),
        )
        gph["decomposition_ifrs17"] = fig

        # Répartition BE santé vs prévoyance
        fig2 = go.Figure(go.Pie(
            labels=["BE Santé","BE Prévoyance"],
            values=[be_s, be_p],
            marker_colors=["#3498DB","#9B59B6"],
            hole=0.5,
        ))
        fig2.update_layout(
            **LAYOUT_BASE,
            title=dict(text="Répartition BE Santé / Prévoyance", font=dict(color=OR, size=13)),
        )
        gph["repartition_be"] = fig2
        return gph

    def _erreur(self, msg, aid=""):
        return {
            "success":False,"agent":self.NOM,"version":self.VERSION,
            "audit_id":aid,"statut_rag":"ROUGE",
            "be_total":0,"ra_total":0,"fcf_total":0,"csm_total":0,"lc_total":0,
            "hypotheses":[],"commentaire":"","graphiques":{},
            "duree_sec":0,"erreur":msg,
        }
