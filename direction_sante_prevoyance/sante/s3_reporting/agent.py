# Migré depuis sp3_reporting_sante.py → direction_sante_prevoyance/sante/s3_reporting/agent.py
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       ACTUARIA — AGENT S3 BINTA : REPORTING SANTÉ v2.0                    ║
║                Sous CHIARA (Équipe Santé) · Direction SP                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PÉRIMÈTRE : Reporting réglementaire santé                                  ║
║              QRT S.13.01 · AMEXA · SCR Santé · Ratio SCR/MCR              ║
║                                                                              ║
║  NOUVEAUTÉS v2 :                                                             ║
║    ✅ Reçoit result_s1 + result_s2 — données réelles du pipeline           ║
║    ✅ QRT S.13.01 complet (BE, RA, TP, SCR, MCR)                          ║
║    ✅ SCR Santé formule standard EIOPA (souscription + réserves)           ║
║    ✅ MCR Santé avec bornes 25%/45% SCR                                    ║
║    ✅ Ratio couverture SCR et MCR                                           ║
║    ✅ Standard ActuarIA : RAG + 3 hypothèses + 4 graphiques + commentaire  ║
║                                                                              ║
║  VERSION : 2.0 — 20/06/2026                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"; OR="#C9A84C"
BLANC="#F0F4F8"; GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"
AMBRE="#F39C12"; BLEU="#3498DB"

LAYOUT_BASE = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16,r=16,t=60,b=60), height=300,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))

# Paramètres SCR Santé EIOPA (module NSLT — Non-Similar to Life Techniques)
# ── Paramètres SCR Santé NSLT ────────────────────────────────────────────
# Source : Règlement Délégué (UE) 2015/35, Annexe II — Santé Non-SLT
SCR_SANTE_SIGMA_PREM = 0.05   # σ primes santé NSLT — Art.148 RD 2015/35
SCR_SANTE_SIGMA_RES  = 0.14   # σ réserves santé NSLT — Art.148 RD 2015/35

# ── MCR Santé — Règlement Délégué Art.252 ────────────────────────────────
# Source : Art.252 RD 2015/35 | Plancher minimum absolu S2 Art.129 §1(d)
MCR_PLANCHER_ABS     = 2_500_000.0  # 2.5M€ — plancher absolu santé Art.129
MCR_COEFF_PREM       = 0.0453       # coefficient primes MCR santé
MCR_COEFF_RES        = 0.0351       # coefficient provisions MCR santé

# ── Risk Adjustment IFRS 17 ───────────────────────────────────────────────
# Méthode : CoC (coût du capital) — IFRS 17 §B91
# RA est calculé dans run() via méthode CoC, pas un coefficient fixe
# SCR_proxy × CoC_rate × duration — voir run() pour le calcul


# ══════════════════════════════════════════════════════════════════════════════
class AgentS3ReportingSante:
    """Agent S3 Binta — Reporting Santé QRT S.13 v2.0."""

    NOM     = "Binta"
    CODE    = "S3"
    VERSION = "2.0"
    MANAGER = "Chiara (Équipe Santé)"

    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.s3.binta")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"S3 Binta v{self.VERSION} | {self.MANAGER}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s1,
            result_s2,
            fonds_propres:    float = 0.0,
            generer_graphiques: bool = True) -> Dict:

        t0  = datetime.now()
        aid = f"S3_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # ── 1. EXTRACTION S1 + S2 ────────────────────────────────────────
            src = self._extraire(result_s1, result_s2, fonds_propres)
            self.logger.info(
                f"[{aid}] S3 Binta | BE={src['be_sante']:,.0f}€ | "
                f"PA={src['primes_acquises']:,.0f}€"
            )

            # ── 2. PROVISIONS TECHNIQUES SANTÉ ───────────────────────────────
            be_sante = src['be_sante']
            # Risk Adjustment IFRS 17 — méthode CoC (cohérence avec S2)
            # RA = SCR_proxy × CoC_rate × duration_santé
            # SCR_proxy santé = σ_prem × PA × 3 (formule std EIOPA)
            # CoC = 6% EIOPA | duration santé = 0.5 an
            _scr_s3  = SCR_SANTE_SIGMA_PREM * src['primes_acquises'] * 3
            _coc_s3  = 0.06   # EIOPA CoC rate — IFRS 17 §B91
            _dur_s3  = 0.5    # duration santé (règlement rapide)
            risk_adj = _scr_s3 * _coc_s3 * _dur_s3
            # Floor : RA ≥ 1% BE — pratique marché
            risk_adj = max(risk_adj, be_sante * 0.01)
            tp_sante = be_sante + risk_adj
            ratio_tp_be = tp_sante / max(be_sante, 1)

            # ── 3. SCR SANTÉ (NSLT — formule standard EIOPA) ─────────────────
            scr_prem  = 3.0 * SCR_SANTE_SIGMA_PREM * src['primes_acquises']
            scr_res   = 3.0 * SCR_SANTE_SIGMA_RES  * be_sante
            # Agrégation (corrélation primes/réserves = 0.5)
            scr_sous  = np.sqrt(
                scr_prem**2 + 2*0.5*scr_prem*scr_res + scr_res**2
            )
            # SCR catastrophe santé (pandémie) = 1% des assurés × coût moyen
            # SCR catastrophe santé (pandémie/épidémie) — Art.159 RD 2015/35
            # Proxy simplifié : 1% × PA (formule standard EIOPA module CAT santé)
            scr_cat   = src['primes_acquises'] * 0.01
            # SCR Santé total
            scr_sante = np.sqrt(scr_sous**2 + scr_cat**2)

            # ── 4. MCR SANTÉ ─────────────────────────────────────────────────
            # MCR santé — Art.252 RD 2015/35
            # MCR_lin = 0.0418 × PA + 0.0261 × BE (coefficients réglementaires)
            # Plancher = max(25% SCR, 2.5M€) | Plafond = 45% SCR
            mcr_lin   = MCR_COEFF_PREM * src['primes_acquises'] + MCR_COEFF_RES * be_sante
            plancher  = max(0.25 * scr_sante, MCR_PLANCHER_ABS)
            plafond   = 0.45 * scr_sante
            mcr_sante = max(min(mcr_lin, plafond), plancher)

            # ── 5. RATIOS ─────────────────────────────────────────────────────
            fpp = src['fonds_propres']
            ratio_scr = fpp / max(scr_sante, 1) * 100
            ratio_mcr = fpp / max(mcr_sante, 1) * 100

            # ── 6. QRT S.13.01 ────────────────────────────────────────────────
            qrt = self._generer_qrt(
                be_sante, risk_adj, tp_sante, ratio_tp_be,
                scr_sante, mcr_sante, ratio_scr, ratio_mcr,
                fpp, src
            )

            # ── 7. HYPOTHÈSES + RAG ───────────────────────────────────────────
            hyp = self._hypotheses(
                ratio_tp_be, ratio_scr, ratio_mcr,
                src['primes_acquises'], be_sante
            )
            rag = self._rag(hyp, ratio_scr, ratio_mcr)

            # ── 8. COMMENTAIRE ────────────────────────────────────────────────
            com = self._commentaire(
                rag, be_sante, risk_adj, tp_sante,
                scr_sante, mcr_sante, ratio_scr, ratio_mcr,
                fpp, src, hyp
            )

            # ── 9. GRAPHIQUES ─────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    be_sante, risk_adj, tp_sante,
                    scr_sante, mcr_sante, fpp,
                    ratio_scr, ratio_mcr, src, hyp
                )

            self._audit(aid, ratio_scr, ratio_mcr, be_sante, rag)
            if self.verbose:
                self._console(aid, rag, be_sante, tp_sante, scr_sante,
                              ratio_scr, ratio_mcr)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':    True,
                'agent':      self.NOM,
                'version':    self.VERSION,
                'audit_id':   aid,
                'statut_rag': rag,

                # ── TP Santé ─────────────────────────────────────────────────
                'be_sante':       round(be_sante, 2),
                'risk_adjustment':round(risk_adj, 2),
                'tp_sante':       round(tp_sante, 2),
                'ratio_tp_be':    round(ratio_tp_be, 4),

                # ── SCR / MCR ────────────────────────────────────────────────
                'scr_sante':     round(scr_sante, 2),
                'scr_prem':      round(scr_prem, 2),
                'scr_res':       round(scr_res, 2),
                'scr_cat':       round(scr_cat, 2),
                'mcr_sante':     round(mcr_sante, 2),
                'ratio_scr_pct': round(ratio_scr, 1),
                'ratio_mcr_pct': round(ratio_mcr, 1),
                'fonds_propres': round(fpp, 2),

                # ── QRT ──────────────────────────────────────────────────────
                'qrt_s13': qrt,

                # ── Standard ActuarIA ────────────────────────────────────────
                'hypotheses':  hyp,
                'commentaire': com,
                'graphiques':  gph,
                'duree_sec':   round(duree, 2),
                'erreur':      None,
            }

        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), aid)

    # ══════════════════════════════════════════════════════════════════════════
    def _extraire(self, result_s1, result_s2, fonds_propres):
        if not result_s2 or not result_s2.get('success'):
            raise ValueError("result_s2 absent — S3 nécessite S2")
        s3 = result_s2.get('sorties_s3', {})
        pa = float(s3.get('primes_acquises',
                   result_s1.get('primes_acquises', 5_000_000) if result_s1 else 5_000_000))
        be = float(s3.get('be_sante', result_s2.get('psap_total', 0)))
        fpp_fournis = float(fonds_propres) > 0
        fpp = float(fonds_propres) if fpp_fournis else pa * 0.80
        if not fpp_fournis:
            self.logger.warning(
                f"fonds_propres non fournis → estimés à {fpp:,.0f}€ (80% PA). "
                f"Le ROUGE éventuel reflète cette estimation, pas nécessairement "
                f"une insuffisance de capital réelle. Fournissez fonds_propres= pour "
                f"un résultat fiable."
            )
        return {
            'primes_acquises': pa,
            'be_sante':        be,
            'fonds_propres':   fpp,
            'loss_ratio':      float(s3.get('loss_ratio', 0.72)),
        }

    def _generer_qrt(self, be, ra, tp, ratio_tp_be, scr, mcr,
                     r_scr, r_mcr, fpp, src):
        return {
            'code':   'S.13.01',
            'titre':  'Health Non-Similar to Life Techniques (NSLT)',
            'lignes': [
                {'code':'R0010','libelle':'BE Santé NSLT','C0010':round(be,0)},
                {'code':'R0020','libelle':'Risk Adjustment (CoC 6% — EIOPA IFRS 17 §B91)','C0010':round(ra,0)},
                {'code':'R0030','libelle':'TP Santé (BE + RA)','C0010':round(tp,0)},
                {'code':'R0040','libelle':'Ratio TP/BE','C0060':round(ratio_tp_be,4)},
                {'code':'R0050','libelle':'SCR Souscription Santé','C0040':round(scr,0)},
                {'code':'R0060','libelle':'MCR Santé','C0040':round(mcr,0)},
                {'code':'R0070','libelle':'Fonds Propres éligibles','C0050':round(fpp,0)},
                {'code':'R0080','libelle':'Ratio SCR (%)','C0060':round(r_scr,1)},
                {'code':'R0090','libelle':'Ratio MCR (%)','C0060':round(r_mcr,1)},
                {'code':'R0100','libelle':'Primes acquises','C0010':round(src['primes_acquises'],0)},
            ],
        }

    def _hypotheses(self, ratio_tp_be, ratio_scr, ratio_mcr, pa, be):
        # H1 — TP/BE ∈ [1.0, 1.5]
        if 1.0 <= ratio_tp_be <= 1.5:
            h1_s = 'VALIDÉE'
            h1_m = f"TP/BE = {ratio_tp_be:.3f} ∈ [1.0, 1.5] ✅"
        elif ratio_tp_be < 1.0:
            h1_s = 'NON VALIDÉE'
            h1_m = f"TP/BE = {ratio_tp_be:.3f} < 1.0 — RA négatif impossible"
        else:
            h1_s = 'À JUSTIFIER'
            h1_m = f"TP/BE = {ratio_tp_be:.3f} > 1.5 — RA élevé à justifier"

        # H2 — Ratio SCR ≥ 130%
        if ratio_scr >= 130:
            h2_s = 'VALIDÉE'
            h2_m = f"Ratio SCR = {ratio_scr:.1f}% ≥ 130% ✅"
        elif ratio_scr >= 100:
            h2_s = 'À JUSTIFIER'
            h2_m = f"Ratio SCR = {ratio_scr:.1f}% ∈ [100%,130%] — proche du seuil"
        else:
            h2_s = 'NON VALIDÉE'
            h2_m = f"Ratio SCR = {ratio_scr:.1f}% < 100% — insuffisance capital"

        # H3 — BE/PA ≤ 30%
        ratio_be = be / max(pa, 1)
        if ratio_be <= 0.30:
            h3_s = 'VALIDÉE'
            h3_m = f"BE/PA = {ratio_be*100:.1f}% ≤ 30% — provisions cohérentes ✅"
        elif ratio_be <= 0.40:
            h3_s = 'À JUSTIFIER'
            h3_m = f"BE/PA = {ratio_be*100:.1f}% ∈ [30%,40%] — provisions élevées"
        else:
            h3_s = 'NON VALIDÉE'
            h3_m = f"BE/PA = {ratio_be*100:.1f}% > 40% — surprovisionnement"

        return [
            {'id':'H1','hypothese':'Ratio TP/BE ∈ [1.0, 1.5] — Risk Adjustment justifié',
             'valeur':h1_m,'statut':h1_s,'critique':True},
            {'id':'H2','hypothese':'Ratio SCR ≥ 130% — capitalisation solide (ORSA santé)',
             'valeur':h2_m,'statut':h2_s,'critique':True},
            {'id':'H3','hypothese':'BE/PA ≤ 30% — provisions cohérentes avec sinistralité',
             'valeur':h3_m,'statut':h3_s,'critique':True},
        ]

    def _rag(self, hyp, ratio_scr, ratio_mcr):
        if ratio_mcr < 100:
            return 'ROUGE'
        non_val = [h for h in hyp if h['statut']=='NON VALIDÉE']
        if non_val or ratio_scr < 100:
            return 'ROUGE'
        a_just = [h for h in hyp if h['statut']=='À JUSTIFIER']
        if a_just or ratio_scr < 130:
            return 'AMBRE'
        return 'VERT'

    def _commentaire(self, rag, be, ra, tp, scr, mcr,
                     r_scr, r_mcr, fpp, src, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        L = [
            "="*70,
            f"  RAPPORT REPORTING SANTÉ QRT S.13 — S3 BINTA v{self.VERSION}",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
            "📊 RÉSUMÉ DIRECTION", "─"*40,
        ]
        if rag=='VERT':
            L.append(f"✅ QRT S.13.01 conforme. SCR={r_scr:.1f}% | MCR={r_mcr:.1f}%.")
        elif rag=='AMBRE':
            L.append(f"⚠️ QRT acceptable — vérifier les points signalés.")
        else:
            L.append(f"❌ QRT non conforme — action corrective requise.")

        L += [
            "", "🔢 QRT S.13.01 — SANTÉ NSLT", "─"*40,
            f"  BE Santé                   : {be:>15,.0f}€",
            f"  Risk Adjustment (CoC 6% EIOPA): {ra:>15,.0f}€",
            f"  TP Santé (BE + RA)         : {tp:>15,.0f}€",
            f"  Ratio TP/BE                : {tp/max(be,1):>15.4f}",
            "  " + "─"*45,
            f"  SCR Santé NSLT             : {scr:>15,.0f}€",
            f"  MCR Santé                  : {mcr:>15,.0f}€",
            f"  Fonds Propres              : {fpp:>15,.0f}€",
            f"  Ratio SCR                  : {r_scr:>14.1f}%",
            f"  Ratio MCR                  : {r_mcr:>14.1f}%",
            "", "📋 HYPOTHÈSES", "─"*40,
        ]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else ("❌" if h['statut']=='NON VALIDÉE' else "⚠️")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        L += ["", "🎯 AVIS BINTA → CHIARA", "─"*40]
        if rag=='VERT':
            L.append("✅ QRT S.13.01 prêt pour soumission ACPR.")
        elif rag=='AMBRE':
            L.append("⚠️ Documenter avant soumission QRT.")
        else:
            L.append("❌ NON CONFORME — Escalade Chiara/Amira.")
        L.append("")
        return "\n".join(L)

    def _graphiques(self, be, ra, tp, scr, mcr, fpp, r_scr, r_mcr, src, hyp):
        gph = {}

        # G1 — BE → TP Santé
        try:
            fig = go.Figure(go.Bar(
                x=["BE Santé","Risk Adj.","TP Santé"],
                y=[be/1e3, ra/1e3, tp/1e3],
                marker_color=[OR, BLEU,
                              VERT if 1.0<=(tp/max(be,1))<=1.5 else AMBRE],
                width=0.4, opacity=0.88,
                text=[f"{v:.0f}k€" for v in [be/1e3,ra/1e3,tp/1e3]],
                textposition="outside", textfont=dict(color=BLANC,size=11),
            ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G1 — De la PSAP aux Provisions Techniques Santé QRT S.13",
                           font=dict(color=OR,size=12),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(visible=False), bargap=0.35,
                annotations=[dict(
                    text="💡 TP Santé = BE (PSAP) + Risk Adjustment (CoC 6% EIOPA §B91). Ratio TP/BE ∈ [1.0,1.5].",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['qrt_s13_tp_be'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — Jauge Ratio SCR
        try:
            c = VERT if r_scr>=130 else (AMBRE if r_scr>=100 else ROUGE)
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=r_scr,
                number=dict(suffix="%", font=dict(color=c,size=28), valueformat=".1f"),
                title=dict(text="Ratio SCR Santé", font=dict(color=c,size=12)),
                gauge=dict(
                    axis=dict(range=[0,300], tickvals=[0,100,130,200,300],
                              ticktext=["0","100%","130%","200%","300%"],
                              tickfont=dict(color=GRIS,size=8)),
                    bar=dict(color=c, thickness=0.25),
                    bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0,100],   color="rgba(231,76,60,0.2)"),
                        dict(range=[100,130],  color="rgba(243,156,18,0.2)"),
                        dict(range=[130,300],  color="rgba(46,204,113,0.1)"),
                    ],
                    threshold=dict(line=dict(color=VERT,width=3), thickness=0.8, value=130),
                ),
            ))
            fig.update_layout(
                paper_bgcolor=NAVY, font=dict(color=BLANC),
                margin=dict(l=30,r=30,t=60,b=50), height=300,
                annotations=[dict(
                    text="💡 Seuil confort ≥ 130%. MCR < 100% = retrait d'agrément ACPR.",
                    xref="paper",yref="paper",x=0.5,y=-0.12,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            )
            gph['ratio_scr_sante'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — FPP vs SCR vs MCR
        try:
            fig = go.Figure()
            for nm, val, col in [
                ('Fonds Propres', fpp, VERT),
                ('SCR Santé',     scr, AMBRE),
                ('MCR Santé',     mcr, BLEU),
            ]:
                fig.add_trace(go.Bar(
                    name=nm, x=[nm], y=[val/1e3],
                    marker_color=col, opacity=0.85,
                    text=f"{val/1e3:.0f}k€", textposition="outside",
                    textfont=dict(color=BLANC,size=11),
                ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text=f"G3 — Capital vs Exigences | SCR={r_scr:.1f}% | MCR={r_mcr:.1f}%",
                           font=dict(color=VERT if r_scr>=130 else AMBRE,size=11),x=0.01),
                barmode='group',
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)'),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
                annotations=[dict(
                    text="💡 Les fonds propres (vert) doivent dépasser SCR et MCR.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['fpp_vs_scr_sante'] = fig
        except Exception as e:
            self.logger.warning(f"G3:{e}")

        # G4 — Scorecard
        try:
            fig = go.Figure()
            for h in hyp:
                c  = VERT if h['statut']=='VALIDÉE' else (AMBRE if h['statut']=='À JUSTIFIER' else ROUGE)
                ic = "✅" if h['statut']=='VALIDÉE' else ("⚠️" if h['statut']=='À JUSTIFIER' else "❌")
                s  = 1.0 if h['statut']=='VALIDÉE' else (0.5 if h['statut']=='À JUSTIFIER' else 0.0)
                fig.add_trace(go.Bar(
                    x=[s], y=[h['hypothese'][:40]], orientation="h",
                    marker_color=c, width=0.5, opacity=0.85,
                    text=f"{ic} {h['statut']}", textposition="outside",
                    textfont=dict(color=c,size=10), showlegend=False,
                ))
            cg = VERT if all(h['statut']=='VALIDÉE' for h in hyp) else (ROUGE if any(h['statut']=='NON VALIDÉE' for h in hyp) else AMBRE)
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G4 — Scorecard QRT Santé S.13.01",
                           font=dict(color=cg,size=12),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 3 ✅ = QRT S.13.01 conforme EIOPA, défendable devant l'ACPR.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['scorecard_s3'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        return gph

    def _audit(self, aid, r_scr, r_mcr, be, rag):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'ratio_scr':r_scr,'ratio_mcr':r_mcr,'be_sante':be}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, rag, be, tp, scr, r_scr, r_mcr):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        print(f"\n{'─'*70}")
        print(f"  S3 BINTA v{self.VERSION} | {aid} | {ic} {rag}")
        print(f"  BE={be:,.0f}€ | TP={tp:,.0f}€ | SCR={scr:,.0f}€ | Ratio={r_scr:.1f}%/{r_mcr:.1f}%")
        print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {'success':False,'agent':self.NOM,'version':self.VERSION,
                'audit_id':aid,'statut_rag':'ROUGE',
                'be_sante':0,'tp_sante':0,'scr_sante':0,'ratio_scr_pct':0,
                'qrt_s13':{},'hypotheses':[],'commentaire':f"❌ ERREUR S3:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  S3 BINTA v2.0 — DÉMO REPORTING SANTÉ QRT S.13")
    print("  SCR NSLT EIOPA | MCR | Ratio SCR/MCR | QRT S.13.01")
    print("="*70)

    r_s1 = {'success':True,'primes_acquises':2_421_438.0,'ratio_sp_attendu':0.848,'nb_assures':5000}
    r_s2 = {
        'success':True,'psap_total':614_116.0,'prec':0.0,
        'provision_totale':614_116.0,'loss_ratio':0.720,
        'sorties_s3': {
            'be_sante':614_116.0,'risk_adjustment':30_706.0,'tp_sante':644_822.0,
            'psap_total':614_116.0,'prec':0.0,'provision_totale':614_116.0,
            'loss_ratio':0.720,'primes_acquises':2_421_438.0,'fonds_propres':1_937_150.0,
        },
    }

    agent = AgentS3ReportingSante(
        models_path='/tmp/s3/models', audit_path='/tmp/s3/audit', verbose=True
    )
    r = agent.run(result_s1=r_s1, result_s2=r_s2,
                  fonds_propres=2_000_000.0, generer_graphiques=False)

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut     : {r['statut_rag']}")
    print(f"  BE Santé   : {r['be_sante']:>12,.0f}€")
    print(f"  TP Santé   : {r['tp_sante']:>12,.0f}€")
    print(f"  SCR Santé  : {r['scr_sante']:>12,.0f}€")
    print(f"  MCR Santé  : {r['mcr_sante']:>12,.0f}€")
    print(f"  Ratio SCR  : {r['ratio_scr_pct']:>11.1f}%")
    print(f"  Ratio MCR  : {r['ratio_mcr_pct']:>11.1f}%")
    print(f"  QRT lignes : {len(r['qrt_s13']['lignes'])}")
    print(f"  Durée      : {r['duree_sec']:.2f}s")
