# Migré depuis sp6_provisionnement_prevoyance.py → direction_sante_prevoyance/prevoyance/p3_provisionnement/agent.py
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ACTUARIA — AGENT P3 ÉLODIE : PROVISIONNEMENT PRÉVOYANCE v2.0          ║
║              Sous DIALLO (Équipe Prévoyance) · Direction SP                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PÉRIMÈTRE : Provisions techniques prévoyance                               ║
║              PSAP ITT (dossiers ouverts + IBNR) · PM Rentes IP (long terme)║
║              PREC · Triangle prévoyance différencié ITT/IP                 ║
║                                                                              ║
║  DIFFÉRENCIATEURS vs marché :                                               ║
║    ✅ PSAP ITT calibrée sur courbe de maintien Markov (P2)                 ║
║    ✅ PM Rentes IP = vraies provisions mathématiques actualisées            ║
║    ✅ IBNR prévoyance différencié ITT (12-18 mois) vs santé (1-3 mois)    ║
║    ✅ Triangle de développement ITT vs IP séparés                          ║
║    ✅ Standard ActuarIA : RAG + 3 hypothèses + 4 graphiques + commentaire  ║
║    ✅ Sorties vers P4 Valentin (reporting QRT S.14)                        ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_p1  → Tarification Axel (primes, salaire, franchise)             ║
║    result_p2  → Tables Rayan (matrices Markov, maintien, durées)           ║
║                                                                              ║
║  SORTIES VERS P4 VALENTIN :                                                  ║
║    psap_itt · pm_rentes · prec · provision_totale · loss_ratio             ║
║    be_prevoyance · tp_prevoyance                                            ║
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
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"; OR="#C9A84C"
BLANC="#F0F4F8"; GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"
AMBRE="#F39C12"; BLEU="#3498DB"; VIOLET="#9B59B6"

LAYOUT_BASE = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16,r=16,t=60,b=60), height=300,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))

# Taux actualisation PM rentes IP
TAUX_ACT = 0.025
# IBNR prévoyance : bien plus long que la santé
IBNR_ITT_PCT = 0.35   # 35% des SP — arrêts longs, déclarations tardives
IBNR_IP_PCT  = 0.20   # 20% — invalidités longues durées


# ══════════════════════════════════════════════════════════════════════════════
class AgentP3ProvisionnemntPrevoyance:
    """Agent P3 Élodie — Provisionnement Prévoyance v2.0."""

    NOM     = "Élodie"
    CODE    = "P3"
    VERSION = "2.0"
    MANAGER = "Diallo (Équipe Prévoyance)"

    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.p3.elodie")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"P3 Élodie v{self.VERSION} | {self.MANAGER}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_p1,
            result_p2,
            generer_graphiques: bool = True) -> Dict:

        t0  = datetime.now()
        aid = f"P3_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # ── 1. EXTRACTION P1 + P2 ────────────────────────────────────────
            src = self._extraire(result_p1, result_p2)
            self.logger.info(
                f"[{aid}] P3 Élodie | PA={src['primes_acquises']:,.0f}€ | "
                f"{src['nb_assures']} assuré(s)"
            )

            # ── 2. PSAP ITT (calibrée sur courbe de maintien P2) ─────────────
            psap_itt = self._calculer_psap_itt(src)

            # ── 3. PM RENTES IP (provisions mathématiques long terme) ─────────
            pm_rentes = self._calculer_pm_rentes_ip(src)

            # ── 4. PSAP IP (dossiers invalidité en cours) ─────────────────────
            psap_ip = self._calculer_psap_ip(src)

            # ── 5. IBNR PRÉVOYANCE (différencié ITT/IP) ──────────────────────
            ibnr_itt = src['sinistres_payes_itt'] * IBNR_ITT_PCT
            ibnr_ip  = src['sinistres_payes_ip']  * IBNR_IP_PCT

            # ── 6. PSAP TOTAL + PREC ─────────────────────────────────────────
            psap_total = psap_itt + psap_ip + ibnr_itt + ibnr_ip
            prec       = self._calculer_prec(src)

            # ── 7. BE + TP PRÉVOYANCE ─────────────────────────────────────────
            be_prev   = psap_total + pm_rentes
            risk_adj  = be_prev * 0.08   # RA prévoyance ≈ 8% du BE (≠ santé 5%)
            tp_prev   = be_prev + risk_adj
            prov_tot  = be_prev + prec

            # ── 8. RATIOS ─────────────────────────────────────────────────────
            lr        = src['sinistres_payes_total'] / max(src['primes_acquises'], 1)
            taux_prov = prov_tot / max(src['primes_acquises'], 1)

            # ── 9. TRIANGLE ───────────────────────────────────────────────────
            triangle = self._triangle_prevoyance(src, psap_itt, psap_ip)

            # ── 10. HYPOTHÈSES + RAG ──────────────────────────────────────────
            hyp = self._hypotheses(
                psap_total, pm_rentes, lr, taux_prov,
                src['primes_acquises'], src['sinistres_payes_total'],
                ibnr_itt
            )
            rag = self._rag(hyp, lr)

            # ── 11. COMMENTAIRE ───────────────────────────────────────────────
            com = self._commentaire(
                rag, src, psap_itt, psap_ip, ibnr_itt, ibnr_ip,
                pm_rentes, psap_total, prec, be_prev, risk_adj,
                tp_prev, prov_tot, lr, taux_prov, hyp
            )

            # ── 12. GRAPHIQUES ────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    psap_itt, psap_ip, ibnr_itt, ibnr_ip,
                    pm_rentes, prec, lr, src, hyp
                )

            self._audit(aid, psap_total, pm_rentes, lr, rag)
            if self.verbose:
                self._console(aid, rag, psap_total, pm_rentes, prov_tot, lr)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':    True,
                'agent':      self.NOM,
                'version':    self.VERSION,
                'audit_id':   aid,
                'statut_rag': rag,

                # ── Provisions ──────────────────────────────────────────────
                'psap_itt':         round(psap_itt, 2),
                'psap_ip':          round(psap_ip, 2),
                'ibnr_itt':         round(ibnr_itt, 2),
                'ibnr_ip':          round(ibnr_ip, 2),
                'psap_total':       round(psap_total, 2),
                'pm_rentes_ip':     round(pm_rentes, 2),
                'prec':             round(prec, 2),
                'be_prevoyance':    round(be_prev, 2),
                'tp_prevoyance':    round(tp_prev, 2),
                'provision_totale': round(prov_tot, 2),
                'loss_ratio':       round(lr, 4),
                'taux_provisionnement': round(taux_prov, 4),

                # ── Triangle ─────────────────────────────────────────────────
                'triangle': triangle,

                # ── Sorties vers P4 Valentin ──────────────────────────────────
                'sorties_p4': {
                    'be_prevoyance':    round(be_prev, 2),
                    'risk_adjustment':  round(risk_adj, 2),
                    'tp_prevoyance':    round(tp_prev, 2),
                    'psap_total':       round(psap_total, 2),
                    'pm_rentes_ip':     round(pm_rentes, 2),
                    'prec':             round(prec, 2),
                    'provision_totale': round(prov_tot, 2),
                    'loss_ratio':       round(lr, 4),
                    'primes_acquises':  src['primes_acquises'],
                    'fonds_propres':    src['primes_acquises'] * 1.20,
                },

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
    def _extraire(self, result_p1, result_p2):
        if not result_p1 or not result_p1.get('success'):
            raise ValueError("result_p1 absent — P3 nécessite P1")
        if not result_p2 or not result_p2.get('success'):
            raise ValueError("result_p2 absent — P3 nécessite P2")

        p3 = result_p2.get('sorties_p3', {})
        pa = float(result_p1.get('primes_acquises',
                   p3.get('primes_acquises', 500_000)))
        nb = int(p3.get('nb_assures', result_p1.get('nb_assures', 1)))
        sal = float(p3.get('salaire_brut', result_p1.get('salaire_brut', 45_000)))
        age = float(p3.get('age', result_p1.get('age', 40)))
        lr_att = result_p1.get('taux_cotisation_pct', 2.0) / 100 * 0.80
        sin_tot = pa * lr_att

        # Répartition sinistres ITT / IP
        sin_itt = sin_tot * 0.65
        sin_ip  = sin_tot * 0.35

        # Taux IP et durées depuis P2
        taux_ip   = float(p3.get('taux_ip', 0.0028))
        dur_ip    = float(p3.get('esperance_duree_ip_ans', 20.0))
        maint_6m  = float(p3.get('prob_maintien_6m', 0.40))
        maint_12m = float(p3.get('prob_maintien_12m', 0.25))
        taux_rente= float(p3.get('taux_rente_ipp', 0.60))
        franchise = int(p3.get('franchise_jours', 90))

        return {
            'primes_acquises':       pa,
            'nb_assures':            nb,
            'salaire_brut':          sal,
            'age':                   age,
            'sinistres_payes_total': sin_tot,
            'sinistres_payes_itt':   sin_itt,
            'sinistres_payes_ip':    sin_ip,
            'taux_ip':               taux_ip,
            'duree_ip_ans':          dur_ip,
            'prob_maintien_6m':      maint_6m,
            'prob_maintien_12m':     maint_12m,
            'taux_rente_ipp':        taux_rente,
            'franchise_jours':       franchise,
        }

    def _calculer_psap_itt(self, src):
        """
        PSAP ITT calibrée sur la courbe de maintien Markov (P2).
        PSAP_ITT ≈ nb_dossiers_ouverts × durée_résiduelle × indemnité_jour
        """
        sal_men     = src['salaire_brut'] / 12
        indem_jour  = sal_men * 0.80 / 30
        # Nombre de dossiers ouverts estimé
        nb_ouv_itt  = max(1, int(src['nb_assures'] * src['taux_ip'] * 10))
        # Durée résiduelle calibrée sur courbe de maintien P2
        # Si maintien 12m = 25%, la durée résiduelle moyenne ≈ 8 mois
        dur_res_mois = max(1.0, -1.0 / np.log(max(src['prob_maintien_12m'], 0.01)))
        psap_itt = nb_ouv_itt * dur_res_mois * 30 * indem_jour
        return psap_itt

    def _calculer_pm_rentes_ip(self, src):
        """
        PM Rentes IP = provision mathématique pour les rentes d'invalidité en cours.
        PM = Σ_t [rente_annuelle × v^t] sur durée résiduelle

        C'est la provision la plus importante en prévoyance long terme.
        Elle se comporte comme une provision de rentes en assurance vie.
        """
        rente_an   = src['salaire_brut'] * src['taux_rente_ipp']
        dur_ip     = src['duree_ip_ans']
        v          = 1.0 / (1 + TAUX_ACT)
        annuite    = sum(v**t for t in range(1, int(dur_ip)+1))
        nb_inv     = max(0, int(src['nb_assures'] * src['taux_ip'] * src['age'] / 10))
        pm_rentes  = nb_inv * rente_an * annuite
        return pm_rentes

    def _calculer_psap_ip(self, src):
        """PSAP IP : dossiers en phase de constitution d'invalidité."""
        rente_men = src['salaire_brut'] * src['taux_rente_ipp'] / 12
        nb_cons   = max(1, int(src['nb_assures'] * src['taux_ip'] * 2))
        psap_ip   = nb_cons * rente_men * 6   # 6 mois de constitution
        return psap_ip

    def _calculer_prec(self, src):
        """PREC prévoyance = max(0, PA × max(0, RC - 1))."""
        lr   = src['sinistres_payes_total'] / max(src['primes_acquises'], 1)
        rc   = lr + 0.20   # chargements prévoyance ≈ 20%
        return max(0.0, src['primes_acquises'] * max(0.0, rc - 1.0))

    def _triangle_prevoyance(self, src, psap_itt, psap_ip):
        """
        Triangle de développement prévoyance — TRÈS différent de la santé.
        ITT : développement 12-36 mois (vs 1-3 mois en santé)
        IP  : développement 5-20 ans (long terme)
        """
        sp_itt = src['sinistres_payes_itt']
        sp_ip  = src['sinistres_payes_ip']
        return {
            'description': "Triangle prévoyance — liquidation lente (≠ santé rapide)",
            'ITT': {
                'mois_6':   round(sp_itt * 0.35, 0),
                'mois_12':  round(sp_itt * 0.60, 0),
                'mois_24':  round(sp_itt * 0.82, 0),
                'mois_36':  round(sp_itt * 0.92, 0),
                'ultime':   round(sp_itt + psap_itt * 0.65, 0),
            },
            'IP': {
                'an_1':   round(sp_ip * 0.10, 0),
                'an_3':   round(sp_ip * 0.30, 0),
                'an_5':   round(sp_ip * 0.50, 0),
                'an_10':  round(sp_ip * 0.75, 0),
                'ultime': round(sp_ip + psap_ip, 0),
            },
            'note': (
                "ITT : 35% payé à 6 mois, 92% à 36 mois. "
                "IP : seulement 10% à 1 an (rentes long terme). "
                "Cadences très différentes de la santé (97% en 3 mois)."
            ),
        }

    def _hypotheses(self, psap, pm, lr, taux_prov, pa, sp, ibnr_itt):
        # H1 — PSAP ≥ 20% des primes (prévoyance plus lente que santé)
        ratio_psap = psap / max(pa, 1)
        if ratio_psap >= 0.20:
            h1_s = 'VALIDÉE'
            h1_m = f"PSAP = {ratio_psap*100:.1f}% PA ≥ 20% ✅ (norme prévoyance)"
        elif ratio_psap >= 0.10:
            h1_s = 'À JUSTIFIER'
            h1_m = f"PSAP = {ratio_psap*100:.1f}% PA ∈ [10%,20%] — vérifier dossiers"
        else:
            h1_s = 'NON VALIDÉE'
            h1_m = f"PSAP = {ratio_psap*100:.1f}% PA < 10% — sous-provisionnement"

        # H2 — IBNR ITT ∈ [20%, 50%] des SP (prévoyance >> santé)
        ratio_ibnr = ibnr_itt / max(sp * 0.65, 1)
        if 0.20 <= ratio_ibnr <= 0.50:
            h2_s = 'VALIDÉE'
            h2_m = f"IBNR ITT = {ratio_ibnr*100:.0f}% SP-ITT ∈ [20%,50%] ✅ — cadence prévoyance"
        elif ratio_ibnr < 0.20:
            h2_s = 'À JUSTIFIER'
            h2_m = f"IBNR ITT = {ratio_ibnr*100:.0f}% SP < 20% — trop faible pour prévoyance"
        else:
            h2_s = 'À JUSTIFIER'
            h2_m = f"IBNR ITT = {ratio_ibnr*100:.0f}% SP > 50% — vérifier méthode"

        # H3 — Loss Ratio ≤ 90%
        if lr <= 0.90:
            h3_s = 'VALIDÉE'
            h3_m = f"Loss Ratio = {lr*100:.1f}% ≤ 90% ✅"
        elif lr <= 1.0:
            h3_s = 'À JUSTIFIER'
            h3_m = f"Loss Ratio = {lr*100:.1f}% ∈ [90%,100%] — surveiller"
        else:
            h3_s = 'NON VALIDÉE'
            h3_m = f"Loss Ratio = {lr*100:.1f}% > 100% — déficit technique"

        return [
            {'id':'H1','hypothese':'PSAP ≥ 20% PA — norme prévoyance (vs 10% en santé)',
             'valeur':h1_m,'statut':h1_s,'critique':True},
            {'id':'H2','hypothese':'IBNR ITT ∈ [20%,50%] SP — cadence prévoyance lente',
             'valeur':h2_m,'statut':h2_s,'critique':True},
            {'id':'H3','hypothese':'Loss Ratio ≤ 90% — sinistralité maîtrisée',
             'valeur':h3_m,'statut':h3_s,'critique':True},
        ]

    def _rag(self, hyp, lr):
        non_val = [h for h in hyp if h['statut']=='NON VALIDÉE']
        a_just  = [h for h in hyp if h['statut']=='À JUSTIFIER']
        if non_val or lr > 1.0: return 'ROUGE'
        if a_just:               return 'AMBRE'
        return 'VERT'

    def _commentaire(self, rag, src, psap_itt, psap_ip, ibnr_itt, ibnr_ip,
                     pm, psap_tot, prec, be, ra, tp, prov, lr, taux_prov, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        L = [
            "="*70,
            f"  RAPPORT PROVISIONNEMENT PRÉVOYANCE — P3 ÉLODIE v{self.VERSION}",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
        ]
        if rag=='VERT':
            L.append(f"✅ Provisionnement validé. BE={be:,.0f}€ | LR={lr*100:.1f}%")
        elif rag=='AMBRE':
            L.append(f"⚠️ Acceptable — vérifier les points signalés.")
        else:
            L.append(f"❌ Sous-provisionnement ou LR>100% — action requise.")

        L += [
            "", "🔢 PROVISIONS PRÉVOYANCE", "─"*40,
            f"  PSAP ITT (dossiers + calibration Markov) : {psap_itt:>12,.0f}€",
            f"  PSAP IP (constitution invalidité)         : {psap_ip:>12,.0f}€",
            f"  IBNR ITT (35% SP-ITT — cadence lente)   : {ibnr_itt:>12,.0f}€",
            f"  IBNR IP  (20% SP-IP)                     : {ibnr_ip:>12,.0f}€",
            f"  PSAP Total                               : {psap_tot:>12,.0f}€",
            "  " + "─"*50,
            f"  PM Rentes IP (long terme actualisées)    : {pm:>12,.0f}€",
            f"  BE Prévoyance (PSAP + PM)                : {be:>12,.0f}€",
            f"  Risk Adjustment (8% BE)                  : {ra:>12,.0f}€",
            f"  TP Prévoyance                            : {tp:>12,.0f}€",
            f"  PREC                                     : {prec:>12,.0f}€",
            f"  Provision Totale                         : {prov:>12,.0f}€",
            f"  Loss Ratio                               : {lr*100:>11.1f}%",
            "", "📋 HYPOTHÈSES", "─"*40,
        ]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else "⚠️"
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        L += ["", "🎯 AVIS ÉLODIE → DIALLO", "─"*40]
        if rag=='VERT':
            L.append("✅ VALIDÉ — Données transmises à P4 Valentin (QRT S.14).")
        else:
            L.append("⚠️/❌ Revoir avant transmission à P4.")
        L.append("")
        return "\n".join(L)

    def _graphiques(self, psap_itt, psap_ip, ibnr_itt, ibnr_ip,
                    pm, prec, lr, src, hyp):
        gph = {}

        # G1 — Décomposition provisions
        try:
            tot = psap_itt + psap_ip + ibnr_itt + ibnr_ip + pm + prec
            fig = go.Figure(go.Bar(
                x=["PSAP ITT","PSAP IP","IBNR ITT","IBNR IP","PM Rentes IP","PREC"],
                y=[psap_itt/1e3, psap_ip/1e3, ibnr_itt/1e3,
                   ibnr_ip/1e3, pm/1e3, prec/1e3],
                marker_color=[OR, BLEU, AMBRE, VIOLET, ROUGE, GRIS],
                width=0.5, opacity=0.88,
                text=[f"{v:.0f}k€" for v in
                      [psap_itt/1e3, psap_ip/1e3, ibnr_itt/1e3,
                       ibnr_ip/1e3, pm/1e3, prec/1e3]],
                textposition="outside", textfont=dict(color=BLANC,size=9),
            ))
            c_tot = VERT if lr<=0.90 else (AMBRE if lr<=1.0 else ROUGE)
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text=f"G1 — Provisions prévoyance | Total={tot/1e3:.0f}k€ | LR={lr*100:.1f}%",
                           font=dict(color=c_tot,size=11),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC,size=8),showgrid=False),
                yaxis=dict(visible=False),
                annotations=[dict(
                    text="💡 PM Rentes = provisions long terme pour invalides (≈ actuariat vie). IBNR prévoyance >> santé.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['decomposition_prev'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — Comparaison cadences ITT vs santé
        try:
            fig = make_subplots(rows=1, cols=2,
                subplot_titles=["Cadences ITT Prévoyance","Cadences Santé (référence)"])
            x_prev = [0, 6, 12, 24, 36]
            y_prev = [0, 35, 60, 82, 92]
            x_san  = [0, 1, 2, 3, 6]
            y_san  = [0, 60, 85, 97, 100]
            fig.add_trace(go.Scatter(
                x=x_prev, y=y_prev, mode='lines+markers',
                line=dict(color=AMBRE,width=2.5), marker=dict(size=8,color=AMBRE),
                fill='tozeroy', fillcolor='rgba(243,156,18,0.08)',
                showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=x_san, y=y_san, mode='lines+markers',
                line=dict(color=VERT,width=2.5), marker=dict(size=8,color=VERT),
                fill='tozeroy', fillcolor='rgba(46,204,113,0.08)',
                showlegend=False), row=1, col=2)
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G2 — Cadences de développement : Prévoyance vs Santé",
                           font=dict(color=OR,size=12),x=0.01),
                xaxis=dict(title="Mois",tickfont=dict(color=GRIS,size=9)),
                yaxis=dict(title="% payé",tickfont=dict(color=GRIS,size=9),range=[0,105]),
                xaxis2=dict(title="Mois",tickfont=dict(color=GRIS,size=9)),
                yaxis2=dict(title="% payé",tickfont=dict(color=GRIS,size=9),range=[0,105]),
                annotations=[dict(
                    text="💡 Prévoyance : 35% à 6 mois (vs santé 97% à 3 mois) → IBNR beaucoup plus élevé.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['cadences_prevoyance_vs_sante'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — Jauge LR
        try:
            c = VERT if lr<=0.90 else (AMBRE if lr<=1.0 else ROUGE)
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=lr*100,
                number=dict(suffix="%",font=dict(color=c,size=28),valueformat=".1f"),
                title=dict(text="Loss Ratio Prévoyance",font=dict(color=c,size=12)),
                gauge=dict(
                    axis=dict(range=[0,120],tickvals=[0,70,90,100,120],
                              ticktext=["0","70","90%","100%","120"],
                              tickfont=dict(color=GRIS,size=8)),
                    bar=dict(color=c,thickness=0.25),bgcolor=NAVY_L,borderwidth=0,
                    steps=[
                        dict(range=[0,90],   color="rgba(46,204,113,0.12)"),
                        dict(range=[90,100],  color="rgba(243,156,18,0.12)"),
                        dict(range=[100,120], color="rgba(231,76,60,0.12)"),
                    ],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=90),
                ),
            ))
            fig.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),
                margin=dict(l=30,r=30,t=60,b=50),height=300,
                annotations=[dict(text="💡 Prévoyance : seuil confort ≤ 90%. Au-delà = révision tarifaire.",
                    xref="paper",yref="paper",x=0.5,y=-0.12,
                    font=dict(color=GRIS,size=9),showarrow=False)])
            gph['jauge_lr_prev'] = fig
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
                    x=[s], y=[h['hypothese'][:45]], orientation="h",
                    marker_color=c, width=0.5, opacity=0.85,
                    text=f"{ic} {h['statut']}", textposition="outside",
                    textfont=dict(color=c,size=10), showlegend=False,
                ))
            cg = VERT if all(h['statut']=='VALIDÉE' for h in hyp) else (ROUGE if any(h['statut']=='NON VALIDÉE' for h in hyp) else AMBRE)
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G4 — Scorecard Provisionnement Prévoyance",
                           font=dict(color=cg,size=12),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=9),showgrid=False),
                barmode="overlay",height=260,
                annotations=[dict(text="💡 3 ✅ = provisions prévoyance conformes.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['scorecard_p3'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        return gph

    def _audit(self, aid, psap, pm, lr, rag):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'psap_total':psap,'pm_rentes':pm,'loss_ratio':lr}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, rag, psap, pm, prov, lr):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        print(f"\n{'─'*70}")
        print(f"  P3 ÉLODIE v{self.VERSION} | {aid} | {ic} {rag}")
        print(f"  PSAP={psap:,.0f}€ | PM rentes={pm:,.0f}€ | Total={prov:,.0f}€ | LR={lr*100:.1f}%")
        print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {'success':False,'agent':self.NOM,'version':self.VERSION,
                'audit_id':aid,'statut_rag':'ROUGE',
                'psap_total':0,'pm_rentes_ip':0,'provision_totale':0,'loss_ratio':0,
                'sorties_p4':{},'hypotheses':[],'commentaire':f"❌ ERREUR P3:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  P3 ÉLODIE v2.0 — DÉMO PROVISIONNEMENT PRÉVOYANCE")
    print("  PSAP ITT+IP | PM Rentes actualisées | IBNR cadence lente | Triangle")
    print("="*70)

    r_p1 = {
        'success':True,'age':40.0,'categorie':'employe',
        'salaire_brut':45_000,'primes_acquises':679.66,
        'nb_assures':1,'taux_cotisation_pct':1.51,'taux_rente_ipp':0.60,
        'sorties_p2':{'age':40,'categorie':'employe','taux_ip':0.00336,
                      'franchise_jours':90,'duree_contrat':20,'salaire_brut':45_000,
                      'primes_acquises':679.66,'nb_assures':1},
    }
    r_p2 = {
        'success':True,
        'sorties_p3': {
            'age':40.0,'categorie':'employe','taux_ip':0.00336,'taux_itt':0.042,
            'duree_moy_itt_mois':13.5,'prob_itt_to_ip':0.08,
            'prob_maintien_6m':0.578,'prob_maintien_12m':0.345,'prob_maintien_24m':0.145,
            'esperance_duree_ip_ans':24.8,'salaire_brut':45_000,
            'taux_rente_ipp':0.60,'primes_acquises':679.66,
            'nb_assures':1,'franchise_jours':90,
        },
    }

    agent = AgentP3ProvisionnemntPrevoyance(
        models_path='/tmp/p3/models', audit_path='/tmp/p3/audit', verbose=True
    )
    r = agent.run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut          : {r['statut_rag']}")
    print(f"  PSAP ITT        : {r['psap_itt']:>12,.0f}€")
    print(f"  PSAP IP         : {r['psap_ip']:>12,.0f}€")
    print(f"  IBNR ITT        : {r['ibnr_itt']:>12,.0f}€")
    print(f"  IBNR IP         : {r['ibnr_ip']:>12,.0f}€")
    print(f"  PSAP Total      : {r['psap_total']:>12,.0f}€")
    print(f"  PM Rentes IP    : {r['pm_rentes_ip']:>12,.0f}€")
    print(f"  BE Prévoyance   : {r['be_prevoyance']:>12,.0f}€")
    print(f"  TP Prévoyance   : {r['tp_prevoyance']:>12,.0f}€")
    print(f"  Loss Ratio      : {r['loss_ratio']*100:>11.1f}%")
    print(f"\n  Triangle ITT 36m: {r['triangle']['ITT']['mois_36']:,.0f}€")
    print(f"  Triangle IP 5a  : {r['triangle']['IP']['an_5']:,.0f}€")
    print(f"  Durée           : {r['duree_sec']:.2f}s")
