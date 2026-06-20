"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ACTUARIA — AGENT NAOMIE : STRESS TESTING SP v2.0                      ║
║              Transversal Santé + Prévoyance · Direction SP                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PÉRIMÈTRE : Stress testing réglementaire santé-prévoyance                  ║
║              Chocs EIOPA décomposés · ORSA SP · Reverse stress             ║
║                                                                              ║
║  DIFFÉRENCIATEURS vs marché :                                               ║
║    ✅ 5 chocs EIOPA réels décomposés actif/passif/NAV                      ║
║       1. Pandémie (+20% morbidité santé + ITT)                            ║
║       2. Désengagement Sécu (+15% restes à charge)                        ║
║       3. Longévité (+10% durée rentes IP)                                 ║
║       4. Invalidité massive (+35% taux IP)                                ║
║       5. Inflation médicale (+8% coûts par poste)                         ║
║    ✅ Impact décomposé santé vs prévoyance séparément                      ║
║    ✅ ORSA SP : projection 5 ans (favorable/central/adverse)               ║
║    ✅ Reverse stress : marge d'insolvabilité + probabilité de ruine        ║
║    ✅ Standard ActuarIA : RAG + 3 hypothèses + 4 graphiques + commentaire  ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_s3  → Reporting Binta (BE santé, SCR, MCR, ratio)               ║
║    result_p4  → Reporting Valentin (BE prév, SCR invalidité, ratio)       ║
║    fonds_propres → capital consolidé SP                                    ║
║                                                                              ║
║  VERSION : 2.0 — 20/06/2026                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List

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

# ── Chocs EIOPA SP ────────────────────────────────────────────────────────────
CHOCS_SP = [
    {
        'id':     'C1',
        'nom':    'Pandémie',
        'desc':   '+20% morbidité (santé + ITT)',
        'impact_sante':    0.20,   # +20% sur BE santé
        'impact_prev':     0.20,   # +20% sur BE prévoyance
        'impact_pa':      -0.05,   # -5% primes (résiliations)
        'source':          'EIOPA Pandémie Art.135',
    },
    {
        'id':     'C2',
        'nom':    'Désengagement Sécu',
        'desc':   '+15% restes à charge santé',
        'impact_sante':    0.15,   # +15% sur BE santé uniquement
        'impact_prev':     0.00,
        'impact_pa':       0.08,   # +8% primes (opportunité)
        'source':          'Scénario ACPR 2024',
    },
    {
        'id':     'C3',
        'nom':    'Longévité',
        'desc':   '+10% durée rentes IP',
        'impact_sante':    0.02,   # impact marginal santé
        'impact_prev':     0.10,   # +10% sur PM rentes
        'impact_pa':       0.00,
        'source':          'EIOPA Longévité Art.138',
    },
    {
        'id':     'C4',
        'nom':    'Invalidité Massive',
        'desc':   '+35% taux IP (récession)',
        'impact_sante':    0.05,
        'impact_prev':     0.35,   # +35% sur BE prévoyance
        'impact_pa':      -0.03,
        'source':          'Scénario récession ORSA',
    },
    {
        'id':     'C5',
        'nom':    'Inflation Médicale',
        'desc':   '+8% coûts médicaux par poste',
        'impact_sante':    0.08,   # +8% sur BE santé
        'impact_prev':     0.03,   # impact marginal prévoyance
        'impact_pa':       0.04,   # +4% primes
        'source':          'Scénario inflation ACPR 2025',
    },
]


# ══════════════════════════════════════════════════════════════════════════════
class AgentNaomieSpStressTesting:
    """Agent Naomie — Stress Testing SP v2.0. Transversal Santé+Prévoyance."""

    NOM     = "Naomie"
    CODE    = "SP-ST"
    VERSION = "2.0"
    MANAGER = "Amira (Direction SP)"

    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.naomie.sp")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"Naomie SP-ST v{self.VERSION} | {self.MANAGER}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s3,
            result_p4,
            fonds_propres:      float = 0.0,
            generer_graphiques: bool  = True) -> Dict:

        t0  = datetime.now()
        aid = f"NAOMIE_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # ── 1. EXTRACTION S3 + P4 ────────────────────────────────────────
            src = self._extraire(result_s3, result_p4, fonds_propres)
            self.logger.info(
                f"[{aid}] Naomie | BE_S={src['be_sante']:,.0f}€ | "
                f"BE_P={src['be_prev']:,.0f}€ | FPP={src['fonds_propres']:,.0f}€"
            )

            # ── 2. BASE ───────────────────────────────────────────────────────
            be_total = src['be_sante'] + src['be_prev']
            scr_base = src['scr_sante'] + src['scr_prev']
            nav_base = src['fonds_propres'] - scr_base

            # ── 3. STRESS 5 CHOCS DÉCOMPOSÉS ─────────────────────────────────
            chocs = self._stress_chocs(src, be_total, scr_base)

            # ── 4. PIRE CAS ───────────────────────────────────────────────────
            pire = min(chocs, key=lambda c: c['nav_stress'])

            # ── 5. REVERSE STRESS ─────────────────────────────────────────────
            reverse = self._reverse_stress(src, be_total, scr_base)

            # ── 6. ORSA SP ────────────────────────────────────────────────────
            orsa = self._orsa_sp(src, be_total, scr_base)

            # ── 7. HYPOTHÈSES + RAG ───────────────────────────────────────────
            hyp = self._hypotheses(chocs, pire, reverse, src)
            rag = self._rag(hyp, pire, src)

            # ── 8. COMMENTAIRE ────────────────────────────────────────────────
            com = self._commentaire(
                rag, src, be_total, scr_base, nav_base,
                chocs, pire, reverse, orsa, hyp
            )

            # ── 9. GRAPHIQUES ─────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    chocs, pire, reverse, orsa, src, be_total, nav_base
                )

            self._audit(aid, chocs, pire, reverse, rag)
            if self.verbose:
                self._console(aid, rag, src, be_total, scr_base, pire)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':    True,
                'agent':      self.NOM,
                'version':    self.VERSION,
                'audit_id':   aid,
                'statut_rag': rag,

                # ── Base ────────────────────────────────────────────────────
                'be_sante':   src['be_sante'],
                'be_prev':    src['be_prev'],
                'be_total':   round(be_total, 2),
                'scr_total':  round(scr_base, 2),
                'nav_base':   round(nav_base, 2),

                # ── Stress ──────────────────────────────────────────────────
                'chocs':      chocs,
                'pire_cas':   pire,

                # ── Reverse ─────────────────────────────────────────────────
                'reverse_stress': reverse,

                # ── ORSA ────────────────────────────────────────────────────
                'orsa': orsa,

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
    # 1. EXTRACTION
    # ══════════════════════════════════════════════════════════════════════════
    def _extraire(self, result_s3, result_p4, fonds_propres):
        if not result_s3 or not result_s3.get('success'):
            raise ValueError("result_s3 absent — Naomie nécessite S3")
        if not result_p4 or not result_p4.get('success'):
            raise ValueError("result_p4 absent — Naomie nécessite P4")

        be_s  = float(result_s3.get('be_sante',    0))
        scr_s = float(result_s3.get('scr_sante',   0))
        pa_s  = float(result_s3.get('qrt_s13', {}).get('lignes', [{}])[-1].get('C0010', 0))
        # Fallback PA santé
        if pa_s == 0:
            for l in result_s3.get('qrt_s13', {}).get('lignes', []):
                if l.get('code') == 'R0100':
                    pa_s = l.get('C0010', 0)

        be_p  = float(result_p4.get('be_prevoyance', 0))
        scr_p = float(result_p4.get('scr_invalidite', 0))
        pm_r  = float(result_p4.get('pm_rentes_ip', 0))
        pa_p  = float(result_p4.get('sorties_naomie', {}).get('primes_acquises', 0))

        fpp_s = float(result_s3.get('fonds_propres', 0))
        fpp_p = float(result_p4.get('fonds_propres', 0))
        fpp   = float(fonds_propres) if fonds_propres > 0 else max(fpp_s, fpp_p, (be_s+be_p)*0.30)

        return {
            'be_sante':    be_s,
            'be_prev':     be_p,
            'scr_sante':   scr_s,
            'scr_prev':    scr_p,
            'pm_rentes':   pm_r,
            'pa_sante':    pa_s,
            'pa_prev':     pa_p,
            'fonds_propres': fpp,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 2. STRESS 5 CHOCS DÉCOMPOSÉS
    # ══════════════════════════════════════════════════════════════════════════
    def _stress_chocs(self, src, be_total, scr_base):
        """
        5 chocs EIOPA réels décomposés santé / prévoyance / NAV.

        Pour chaque choc :
        - Impact santé  = BE_santé × choc_santé
        - Impact prévo  = BE_prévo × choc_prévo
        - Impact PA     = (PA_S + PA_P) × choc_pa (effet sur primes)
        - Impact NAV    = −(Impact_S + Impact_P) + Impact_PA
        """
        pa_total = src['pa_sante'] + src['pa_prev']
        nav_base = src['fonds_propres'] - scr_base
        result   = []

        for c in CHOCS_SP:
            imp_s  = src['be_sante'] * c['impact_sante']
            imp_p  = src['be_prev']  * c['impact_prev']
            imp_pa = pa_total        * c['impact_pa']
            imp_nav = -(imp_s + imp_p) + imp_pa
            nav_st  = nav_base + imp_nav
            pct_nav = imp_nav / max(abs(nav_base), 1) * 100

            result.append({
                'id':          c['id'],
                'nom':         c['nom'],
                'desc':        c['desc'],
                'source':      c['source'],
                'imp_sante':   round(imp_s, 0),
                'imp_prev':    round(imp_p, 0),
                'imp_pa':      round(imp_pa, 0),
                'imp_nav':     round(imp_nav, 0),
                'nav_stress':  round(nav_st, 0),
                'pct_nav':     round(pct_nav, 1),
                'favorable':   imp_nav > 0,
            })

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 3. REVERSE STRESS
    # ══════════════════════════════════════════════════════════════════════════
    def _reverse_stress(self, src, be_total, scr_base):
        """
        Reverse stress : quelle hausse simultanée de morbidité rend
        l'entité insolvable (FPP < SCR) ?

        FPP − SCR − BE_total × choc = 0
        → choc_max = (FPP − SCR) / BE_total
        """
        fpp  = src['fonds_propres']
        marge = fpp - scr_base

        if be_total > 0:
            choc_max = marge / be_total * 100
        else:
            choc_max = 0.0

        # Probabilité de ruine (approximation log-normale)
        # P(hausse > choc_max) avec σ ≈ 15% (volatilité sinistralité SP)
        sigma = 0.15
        if choc_max > 0:
            z = choc_max / 100 / sigma
            prob_ruine = float(np.exp(-0.5 * z**2) / (z * sigma * np.sqrt(2*np.pi)) * 100)
            prob_ruine = min(prob_ruine, 50.0)
        else:
            prob_ruine = 100.0

        return {
            'marge_euros':              round(marge, 0),
            'hausse_morbidite_max_pct': round(choc_max, 1),
            'prob_ruine_pct':           round(prob_ruine, 4),
            'interpretation': (
                f"L'entité peut absorber une hausse de morbidité de {choc_max:.1f}% "
                f"avant insolvabilité. P(ruine) ≈ {prob_ruine:.3f}%."
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 4. ORSA SP
    # ══════════════════════════════════════════════════════════════════════════
    def _orsa_sp(self, src, be_total, scr_base):
        """
        ORSA SP : projection 5 ans ratio SCR sous 3 scénarios.
        Favorable : -2%/an morbidité, +3%/an primes
        Central   : stable
        Adverse   : +5%/an morbidité, +1%/an primes
        """
        fpp  = src['fonds_propres']
        proj = {'favorable':[], 'central':[], 'adverse':[]}

        for t in range(1, 6):
            for sc, delta_be, delta_pa in [
                ('favorable', -0.02, +0.03),
                ('central',    0.00,  0.00),
                ('adverse',   +0.05, +0.01),
            ]:
                be_t  = be_total * (1 + delta_be)**t
                pa_t  = (src['pa_sante'] + src['pa_prev']) * (1 + delta_pa)**t
                scr_t = scr_base * (1 + delta_be * 0.8)**t
                fpp_t = fpp + pa_t * 0.05 * t   # capitalisation progressive
                ratio = fpp_t / max(scr_t, 1) * 100
                proj[sc].append(round(ratio, 1))

        ratio_adv_min = min(proj['adverse'])
        statut = 'VERT' if ratio_adv_min >= 130 else ('AMBRE' if ratio_adv_min >= 100 else 'ROUGE')

        return {
            'projection':       proj,
            'ratio_adverse_min':round(ratio_adv_min, 1),
            'statut':           statut,
            'horizons':         list(range(1, 6)),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 5. HYPOTHÈSES
    # ══════════════════════════════════════════════════════════════════════════
    def _hypotheses(self, chocs, pire, reverse, src):
        # H1 — Aucun choc ne rend NAV < 0
        chocs_neg = [c for c in chocs if c['nav_stress'] < 0]
        if not chocs_neg:
            h1_s = 'VALIDÉE'
            h1_m = f"NAV positive sous tous les 5 chocs EIOPA ✅ — pire={pire['nav_stress']:,.0f}€"
        else:
            h1_s = 'NON VALIDÉE'
            h1_m = f"{len(chocs_neg)} choc(s) rendent la NAV négative ❌"

        # H2 — Marge reverse stress > 20%
        choc_max = reverse['hausse_morbidite_max_pct']
        if choc_max >= 20:
            h2_s = 'VALIDÉE'
            h2_m = f"Hausse morbidité absorbable = {choc_max:.1f}% ≥ 20% ✅"
        elif choc_max >= 10:
            h2_s = 'À JUSTIFIER'
            h2_m = f"Hausse morbidité absorbable = {choc_max:.1f}% ∈ [10%,20%]"
        else:
            h2_s = 'NON VALIDÉE'
            h2_m = f"Hausse morbidité absorbable = {choc_max:.1f}% < 10% — fragile"

        # H3 — Impact pire choc < 30% NAV
        nav = src['fonds_propres']
        pct = abs(pire['imp_nav']) / max(abs(nav), 1) * 100
        if pct <= 30:
            h3_s = 'VALIDÉE'
            h3_m = f"Pire choc ({pire['nom']}) = {pct:.1f}% NAV ≤ 30% ✅"
        elif pct <= 50:
            h3_s = 'À JUSTIFIER'
            h3_m = f"Pire choc ({pire['nom']}) = {pct:.1f}% NAV ∈ [30%,50%]"
        else:
            h3_s = 'NON VALIDÉE'
            h3_m = f"Pire choc ({pire['nom']}) = {pct:.1f}% NAV > 50% — concentration"

        return [
            {'id':'H1','hypothese':'NAV positive sous tous les 5 chocs EIOPA SP',
             'valeur':h1_m,'statut':h1_s,'critique':True},
            {'id':'H2','hypothese':'Marge reverse stress ≥ 20% — résistance à la morbidité',
             'valeur':h2_m,'statut':h2_s,'critique':True},
            {'id':'H3','hypothese':'Pire choc ≤ 30% NAV — concentration acceptable',
             'valeur':h3_m,'statut':h3_s,'critique':True},
        ]

    def _rag(self, hyp, pire, src):
        non_val = [h for h in hyp if h['statut']=='NON VALIDÉE']
        if non_val: return 'ROUGE'
        if pire['nav_stress'] < 0: return 'ROUGE'
        a_just = [h for h in hyp if h['statut']=='À JUSTIFIER']
        if a_just: return 'AMBRE'
        return 'VERT'

    # ══════════════════════════════════════════════════════════════════════════
    # 6. COMMENTAIRE
    # ══════════════════════════════════════════════════════════════════════════
    def _commentaire(self, rag, src, be_total, scr_base, nav_base,
                     chocs, pire, reverse, orsa, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        L = [
            "="*70,
            f"  RAPPORT STRESS TESTING SP — NAOMIE v{self.VERSION}",
            f"  5 chocs EIOPA | Santé + Prévoyance | ORSA SP 5 ans",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
        ]
        if rag=='VERT':
            L.append(f"✅ Résistance validée. NAV positive sous tous les chocs.")
        elif rag=='AMBRE':
            L.append(f"⚠️ Acceptable — vérifier les points signalés.")
        else:
            L.append(f"❌ ALERTE — action corrective requise.")

        L += [
            "", "📊 BASE DE CALCUL", "─"*40,
            f"  BE Santé                      : {src['be_sante']:>12,.0f}€",
            f"  BE Prévoyance                 : {src['be_prev']:>12,.0f}€",
            f"  BE Total SP                   : {be_total:>12,.0f}€",
            f"  SCR Santé + Prévoyance        : {scr_base:>12,.0f}€",
            f"  Fonds Propres                 : {src['fonds_propres']:>12,.0f}€",
            f"  NAV de base                   : {nav_base:>12,.0f}€",
            "", "⚡ STRESS 5 CHOCS EIOPA SP (décomposés)", "─"*40,
            f"  {'Choc':<25} {'Santé':>10} {'Prévo':>10} {'PA':>10} {'NAV':>12} {'%NAV':>8}",
            "  " + "─"*75,
        ]
        for c in chocs:
            fav = "↑" if c['favorable'] else "↓"
            L.append(
                f"  {c['id']} {c['nom']:<20} {c['imp_sante']:>+9,.0f}€ "
                f"{c['imp_prev']:>+9,.0f}€ {c['imp_pa']:>+9,.0f}€ "
                f"{c['imp_nav']:>+11,.0f}€ {c['pct_nav']:>+7.1f}% {fav}"
            )
        L += [
            "  " + "─"*75,
            f"  PIRE CAS : {pire['nom']} ({pire['desc']})",
            f"  NAV stress : {pire['nav_stress']:,.0f}€ ({pire['pct_nav']:+.1f}%)",
            "", "🔄 REVERSE STRESS", "─"*40,
            f"  {reverse['interpretation']}",
            f"  P(ruine) ≈ {reverse['prob_ruine_pct']:.4f}%",
            "", "📈 ORSA SP 5 ANS", "─"*40,
            f"  Ratio SCR adverse min (5 ans)  : {orsa['ratio_adverse_min']:.1f}% [{orsa['statut']}]",
            f"  {'An':<6}" + "".join(f"  {'An '+str(t):>8}" for t in orsa['horizons']),
            f"  {'Fav.':<6}" + "".join(f"  {v:>8.1f}%" for v in orsa['projection']['favorable']),
            f"  {'Cent.':<6}" + "".join(f"  {v:>8.1f}%" for v in orsa['projection']['central']),
            f"  {'Adv.':<6}" + "".join(f"  {v:>8.1f}%" for v in orsa['projection']['adverse']),
            "", "📋 HYPOTHÈSES", "─"*40,
        ]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else "⚠️"
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        L += ["", "🎯 AVIS NAOMIE → AMIRA", "─"*40]
        if rag=='VERT':
            L.append("✅ CONFORME — Direction SP résistante aux 5 chocs EIOPA.")
        elif rag=='AMBRE':
            L.append("⚠️ Surveiller le pire choc et renforcer le capital SP.")
        else:
            L.append("❌ NON CONFORME — Escalade Amira. Plan de restauration requis.")
        L.append("")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════════════════════
    # 7. GRAPHIQUES
    # ══════════════════════════════════════════════════════════════════════════
    def _graphiques(self, chocs, pire, reverse, orsa, src, be_total, nav_base):
        gph = {}

        # G1 — Stress 5 chocs : impact NAV décomposé santé/prévo
        try:
            noms    = [f"{c['id']}\n{c['nom']}" for c in chocs]
            imp_s   = [c['imp_sante']/1e3   for c in chocs]
            imp_p   = [c['imp_prev']/1e3    for c in chocs]
            imp_nav = [c['imp_nav']/1e3     for c in chocs]

            fig = go.Figure()
            fig.add_trace(go.Bar(name='Impact Santé', x=noms, y=imp_s,
                marker_color=BLEU, opacity=0.80,
                text=[f"{v:+.0f}k€" for v in imp_s],
                textposition='inside', textfont=dict(color=BLANC,size=9)))
            fig.add_trace(go.Bar(name='Impact Prévoyance', x=noms, y=imp_p,
                marker_color=VIOLET, opacity=0.80,
                text=[f"{v:+.0f}k€" for v in imp_p],
                textposition='inside', textfont=dict(color=BLANC,size=9)))
            fig.add_trace(go.Scatter(name='Impact NAV Net', x=noms, y=imp_nav,
                mode='lines+markers', line=dict(color=OR,width=3),
                marker=dict(size=10,color=OR),
                text=[f"{v:+.0f}k€" for v in imp_nav],
                textposition='top center', textfont=dict(color=OR,size=10)))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G1 — Stress 5 Chocs EIOPA SP | Impact NAV décomposé Santé/Prévoyance",
                           font=dict(color=OR,size=11),x=0.01),
                barmode='group',
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)',
                            orientation='h',y=-0.20),
                xaxis=dict(tickfont=dict(color=BLANC,size=8),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
                annotations=[dict(
                    text="💡 La ligne or = impact NET sur la NAV. Bleu=santé, Violet=prévoyance.",
                    xref="paper",yref="paper",x=0.01,y=-0.30,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['stress_5chocs'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — NAV stress vs base
        try:
            navs = [nav_base] + [c['nav_stress'] for c in chocs]
            lbls = ['Base'] + [c['nom'] for c in chocs]
            cols = [VERT] + [VERT if c['nav_stress']>0 else ROUGE for c in chocs]
            fig = go.Figure(go.Bar(
                x=lbls, y=[v/1e3 for v in navs],
                marker_color=cols, opacity=0.85,
                text=[f"{v/1e3:.0f}k€" for v in navs],
                textposition="outside", textfont=dict(color=BLANC,size=10),
            ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G2 — NAV Stressée par choc (vert=positive, rouge=insolvable)",
                           font=dict(color=OR,size=11),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC,size=8),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
                shapes=[dict(type='line', x0=-0.5, x1=len(lbls)-0.5,
                             y0=0, y1=0, line=dict(color=ROUGE,width=2,dash='dash'))],
                annotations=[dict(
                    text="💡 En dessous de 0 = insolvabilité. La ligne rouge = seuil d'alerte.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['nav_par_choc'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — ORSA SP 5 ans
        try:
            horizons = orsa['horizons']
            fig = go.Figure()
            for sc, col, dash in [
                ('favorable', VERT, 'solid'),
                ('central',   OR,   'dot'),
                ('adverse',   ROUGE,'dash'),
            ]:
                fig.add_trace(go.Scatter(
                    x=horizons, y=orsa['projection'][sc],
                    name=sc.capitalize(), mode='lines+markers',
                    line=dict(color=col,width=2,dash=dash),
                    marker=dict(size=8,color=col),
                    hovertemplate=f"<b>{sc}</b> An %{{x}} : %{{y:.1f}}%<extra></extra>",
                ))
            fig.add_hline(y=100, line=dict(color=ROUGE,width=1,dash='dash'))
            fig.add_hline(y=130, line=dict(color=AMBRE,width=1,dash='dot'))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G3 — ORSA SP 5 ans | Ratio SCR favorable/central/adverse",
                           font=dict(color=OR,size=11),x=0.01),
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)'),
                xaxis=dict(title="Années",tickfont=dict(color=GRIS,size=9)),
                yaxis=dict(title="Ratio SCR %",tickfont=dict(color=GRIS,size=9),range=[0,None]),
                annotations=[dict(
                    text="💡 Rouge=100% (seuil légal) · Orange=130% (seuil confort ACPR).",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['orsa_sp'] = fig
        except Exception as e:
            self.logger.warning(f"G3:{e}")

        # G4 — Scorecard
        try:
            hyp_tmp = self._hypotheses(
                [{'nav_stress':nav_base,'favorable':True,'nom':'base','imp_nav':0}],
                {'nom':'base','nav_stress':nav_base,'imp_nav':0},
                reverse, src
            )
            fig = go.Figure()
            for h in hyp_tmp:
                c  = VERT if h['statut']=='VALIDÉE' else (AMBRE if h['statut']=='À JUSTIFIER' else ROUGE)
                ic = "✅" if h['statut']=='VALIDÉE' else ("⚠️" if h['statut']=='À JUSTIFIER' else "❌")
                s  = 1.0 if h['statut']=='VALIDÉE' else (0.5 if h['statut']=='À JUSTIFIER' else 0.0)
                fig.add_trace(go.Bar(
                    x=[s], y=[h['hypothese'][:45]], orientation="h",
                    marker_color=c, width=0.5, opacity=0.85,
                    text=f"{ic} {h['statut']}", textposition="outside",
                    textfont=dict(color=c,size=10), showlegend=False,
                ))
            cg = VERT if all(h['statut']=='VALIDÉE' for h in hyp_tmp) else (ROUGE if any(h['statut']=='NON VALIDÉE' for h in hyp_tmp) else AMBRE)
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G4 — Scorecard Stress Testing SP",
                           font=dict(color=cg,size=12),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=9),showgrid=False),
                barmode="overlay",height=260,
            ))
            fig.update_layout(**l)
            gph['scorecard_naomie'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        return gph

    # ══════════════════════════════════════════════════════════════════════════
    def _audit(self, aid, chocs, pire, reverse, rag):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'pire_choc':pire['nom'],'pire_nav':pire['nav_stress'],
                 'prob_ruine':reverse['prob_ruine_pct']}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, rag, src, be_total, scr_base, pire):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        print(f"\n{'─'*70}")
        print(f"  NAOMIE SP-ST v{self.VERSION} | {aid} | {ic} {rag}")
        print(f"  BE_SP={be_total:,.0f}€ | SCR={scr_base:,.0f}€ | FPP={src['fonds_propres']:,.0f}€")
        print(f"  Pire choc : {pire['nom']} → NAV={pire['nav_stress']:,.0f}€")
        print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {'success':False,'agent':self.NOM,'version':self.VERSION,
                'audit_id':aid,'statut_rag':'ROUGE',
                'be_total':0,'scr_total':0,'nav_base':0,
                'chocs':[],'pire_cas':{},'reverse_stress':{},'orsa':{},
                'hypotheses':[],'commentaire':f"❌ ERREUR Naomie:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  NAOMIE SP-ST v2.0 — DÉMO STRESS TESTING SANTÉ-PRÉVOYANCE")
    print("  5 chocs EIOPA | Pandémie · Sécu · Longévité · Invalidité · Inflation")
    print("="*70)

    # Simuler result_s3
    r_s3 = {
        'success': True, 'statut_rag': 'VERT',
        'be_sante': 613_020.0, 'scr_sante': 540_665.0,
        'fonds_propres': 3_000_000.0,
        'qrt_s13': {'lignes': [
            {'code':'R0010','libelle':'BE Santé','C0010':613_020.0},
            {'code':'R0100','libelle':'Primes','C0010':2_421_438.0},
        ]},
    }

    # Simuler result_p4
    r_p4 = {
        'success': True, 'statut_rag': 'ROUGE',
        'be_prevoyance': 16_502.0, 'scr_invalidite': 6_391.0,
        'fonds_propres': 5_000_000.0, 'pm_rentes_ip': 0.0,
        'sorties_naomie': {'primes_acquises': 680.0, 'fonds_propres': 5_000_000.0},
    }

    agent = AgentNaomieSpStressTesting(
        models_path='/tmp/naomie/models',
        audit_path='/tmp/naomie/audit',
        verbose=True
    )
    r = agent.run(result_s3=r_s3, result_p4=r_p4,
                  fonds_propres=5_000_000, generer_graphiques=False)

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut         : {r['statut_rag']}")
    print(f"  BE Total SP    : {r['be_total']:>12,.0f}€")
    print(f"  SCR Total SP   : {r['scr_total']:>12,.0f}€")
    print(f"  NAV Base       : {r['nav_base']:>12,.0f}€")
    print(f"\n  5 chocs EIOPA :")
    for c in r['chocs']:
        print(f"    {c['id']} {c['nom']:<22}: NAV={c['nav_stress']:>+10,.0f}€ ({c['pct_nav']:>+6.1f}%)")
    print(f"\n  Pire cas       : {r['pire_cas']['nom']} → {r['pire_cas']['nav_stress']:,.0f}€")
    rev = r['reverse_stress']
    print(f"  Marge stress   : {rev['hausse_morbidite_max_pct']:.1f}% | P(ruine)={rev['prob_ruine_pct']:.4f}%")
    print(f"  ORSA adverse   : {r['orsa']['ratio_adverse_min']:.1f}% [{r['orsa']['statut']}]")
    print(f"  Durée          : {r['duree_sec']:.2f}s")
