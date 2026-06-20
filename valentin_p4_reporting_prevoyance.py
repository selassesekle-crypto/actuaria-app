"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ACTUARIA — AGENT P4 VALENTIN : REPORTING PRÉVOYANCE v2.0              ║
║              Sous DIALLO (Équipe Prévoyance) · Direction SP                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PÉRIMÈTRE : Reporting réglementaire prévoyance                             ║
║              QRT S.14.01 · SCR Vie Invalidité EIOPA · MCR · Ratios        ║
║                                                                              ║
║  DIFFÉRENCIATEURS vs marché :                                               ║
║    ✅ BE prévoyance = PM Rentes IP + PSAP ITT (pas 1 ligne fixe)          ║
║    ✅ SCR Invalidité EIOPA : choc morbidité +35% + choc cessation -20%    ║
║    ✅ MCR prévoyance avec bornes 25%/45% SCR et plancher absolu            ║
║    ✅ QRT S.14.01 complet (BE, RA 8%, TP, SCR, MCR, FPP)                 ║
║    ✅ Réconciliation avec P2 (matrices Markov) et P3 (provisions)         ║
║    ✅ Standard ActuarIA : RAG + 3 hypothèses + 4 graphiques + commentaire  ║
║    ✅ Sorties vers Naomie (stress testing SP)                              ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_p1  → Tarification Axel (primes, salaire, taux cotisation)      ║
║    result_p2  → Tables Rayan (matrices Markov, maintien, durées)           ║
║    result_p3  → Provisionnement Élodie (BE, PM rentes, PSAP, PREC)       ║
║    fonds_propres → capital disponible                                      ║
║                                                                              ║
║  SORTIES VERS NAOMIE :                                                      ║
║    be_prevoyance · tp_prevoyance · scr_invalidite · mcr · ratio_scr       ║
║    pm_rentes_ip · psap_total                                               ║
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

# ── Paramètres EIOPA Prévoyance ───────────────────────────────────────────────
# SCR Invalidité (module Vie — Art. 145 Delegated Regulation)
CHOC_MORBIDITE_HAUSSE  = 0.35   # +35% taux incidence ITT/IP
CHOC_CESSATION_BAISSE  = 0.20   # -20% taux de cessation (moins de guérisons)
COC_RA                 = 0.08   # Risk Adjustment prévoyance = 8% BE
MCR_PLANCHER_ABS       = 3_700_000.0   # plancher absolu prévoyance (≠ 2.5M santé)
MCR_ALPHA_PREV         = 0.0338   # coefficient primes prévoyance
MCR_BETA_PREV          = 0.0191   # coefficient provisions prévoyance


# ══════════════════════════════════════════════════════════════════════════════
class AgentP4ReportingPrevoyance:
    """Agent P4 Valentin — Reporting Prévoyance QRT S.14 v2.0."""

    NOM     = "Valentin"
    CODE    = "P4"
    VERSION = "2.0"
    MANAGER = "Diallo (Équipe Prévoyance)"

    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.p4.valentin")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"P4 Valentin v{self.VERSION} | {self.MANAGER}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_p1,
            result_p2,
            result_p3,
            fonds_propres:      float = 0.0,
            generer_graphiques: bool  = True) -> Dict:

        t0  = datetime.now()
        aid = f"P4_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # ── 1. EXTRACTION P1 + P2 + P3 ───────────────────────────────────
            src = self._extraire(result_p1, result_p2, result_p3, fonds_propres)
            self.logger.info(
                f"[{aid}] P4 Valentin | BE={src['be_prevoyance']:,.0f}€ | "
                f"PA={src['primes_acquises']:,.0f}€"
            )

            # ── 2. PROVISIONS TECHNIQUES PRÉVOYANCE ──────────────────────────
            be_prev  = src['be_prevoyance']
            risk_adj = be_prev * COC_RA
            tp_prev  = be_prev + risk_adj

            # ── 3. SCR INVALIDITÉ EIOPA ───────────────────────────────────────
            scr = self._calculer_scr_invalidite(src, be_prev)

            # ── 4. MCR PRÉVOYANCE ─────────────────────────────────────────────
            mcr = self._calculer_mcr(src, scr)

            # ── 5. RATIOS ─────────────────────────────────────────────────────
            fpp = src['fonds_propres']
            ratio_scr = fpp / max(scr['scr_total'], 1) * 100
            ratio_mcr = fpp / max(mcr['mcr'], 1) * 100

            # ── 6. QRT S.14.01 ────────────────────────────────────────────────
            qrt = self._generer_qrt(
                be_prev, risk_adj, tp_prev, scr, mcr,
                ratio_scr, ratio_mcr, fpp, src
            )

            # ── 7. HYPOTHÈSES + RAG ───────────────────────────────────────────
            hyp = self._hypotheses(be_prev, scr, ratio_scr, ratio_mcr, src)
            rag = self._rag(hyp, ratio_scr, ratio_mcr)

            # ── 8. COMMENTAIRE ────────────────────────────────────────────────
            com = self._commentaire(
                rag, be_prev, risk_adj, tp_prev,
                scr, mcr, ratio_scr, ratio_mcr, fpp, src, hyp
            )

            # ── 9. GRAPHIQUES ─────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    be_prev, risk_adj, tp_prev,
                    scr, mcr, fpp, ratio_scr, ratio_mcr, src, hyp
                )

            self._audit(aid, ratio_scr, ratio_mcr, be_prev, rag)
            if self.verbose:
                self._console(aid, rag, be_prev, tp_prev, scr['scr_total'],
                              ratio_scr, ratio_mcr)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':    True,
                'agent':      self.NOM,
                'version':    self.VERSION,
                'audit_id':   aid,
                'statut_rag': rag,

                # ── Provisions ──────────────────────────────────────────────
                'be_prevoyance':    round(be_prev, 2),
                'risk_adjustment':  round(risk_adj, 2),
                'tp_prevoyance':    round(tp_prev, 2),
                'pm_rentes_ip':     src['pm_rentes_ip'],
                'psap_total':       src['psap_total'],
                'prec':             src['prec'],

                # ── SCR / MCR ────────────────────────────────────────────────
                'scr_invalidite':    round(scr['scr_total'], 2),
                'scr_morbidite':     round(scr['scr_morbidite'], 2),
                'scr_cessation':     round(scr['scr_cessation'], 2),
                'scr_longevite':     round(scr['scr_longevite'], 2),
                'mcr':               round(mcr['mcr'], 2),
                'ratio_scr_pct':     round(ratio_scr, 1),
                'ratio_mcr_pct':     round(ratio_mcr, 1),
                'fonds_propres':     round(fpp, 2),

                # ── QRT ──────────────────────────────────────────────────────
                'qrt_s14': qrt,

                # ── Sorties vers Naomie ───────────────────────────────────────
                'sorties_naomie': {
                    'be_prevoyance':    round(be_prev, 2),
                    'tp_prevoyance':    round(tp_prev, 2),
                    'pm_rentes_ip':     src['pm_rentes_ip'],
                    'psap_total':       src['psap_total'],
                    'scr_invalidite':   round(scr['scr_total'], 2),
                    'mcr':              round(mcr['mcr'], 2),
                    'ratio_scr_pct':    round(ratio_scr, 1),
                    'primes_acquises':  src['primes_acquises'],
                    'fonds_propres':    round(fpp, 2),
                    'taux_ip':          src['taux_ip'],
                    'taux_itt':         src['taux_itt'],
                    'nb_assures':       src['nb_assures'],
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
    # 1. EXTRACTION P1 + P2 + P3
    # ══════════════════════════════════════════════════════════════════════════
    def _extraire(self, result_p1, result_p2, result_p3, fonds_propres):
        if not result_p3 or not result_p3.get('success'):
            raise ValueError("result_p3 absent — P4 nécessite P1+P2+P3")

        p4 = result_p3.get('sorties_p4', {})

        be_prev     = float(p4.get('be_prevoyance',    0))
        pm_rentes   = float(p4.get('pm_rentes_ip',     0))
        psap_total  = float(p4.get('psap_total',       0))
        prec        = float(p4.get('prec',             0))
        pa          = float(p4.get('primes_acquises',  0))
        lr          = float(p4.get('loss_ratio',       0.80))
        fpp_est     = float(p4.get('fonds_propres',    0))

        # Taux depuis P2
        p3_src = result_p2.get('sorties_p3', {}) if result_p2 else {}
        taux_ip  = float(p3_src.get('taux_ip',  0.003))
        taux_itt = float(p3_src.get('taux_itt', 0.042))
        dur_ip   = float(p3_src.get('esperance_duree_ip', 20.0))
        nb_ass   = int(p3_src.get('nb_assures', 1))

        # Salaire depuis P1
        p2_src = result_p1.get('sorties_p2', {}) if result_p1 else {}
        sal = float(p2_src.get('salaire_brut', 45_000))

        # Fonds propres
        fpp = float(fonds_propres) if fonds_propres > 0 else max(fpp_est, pa * 2.0)
        if fonds_propres <= 0:
            self.logger.warning(f"fonds_propres non fournis → estimés à {fpp:,.0f}€")

        return {
            'be_prevoyance':  be_prev,
            'pm_rentes_ip':   pm_rentes,
            'psap_total':     psap_total,
            'prec':           prec,
            'primes_acquises':pa,
            'loss_ratio':     lr,
            'fonds_propres':  fpp,
            'taux_ip':        taux_ip,
            'taux_itt':       taux_itt,
            'duree_ip_ans':   dur_ip,
            'salaire_brut':   sal,
            'nb_assures':     nb_ass,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 2. SCR INVALIDITÉ EIOPA
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_scr_invalidite(self, src, be_prev):
        """
        SCR Invalidité — Module Vie EIOPA (Art. 145 Delegated Regulation).

        3 sous-modules agrégés :

        SCR_Morbidité : choc +35% taux incidence ITT/IP
        → Impact = BE × CHOC_MORBIDITE = augmentation des provisions

        SCR_Cessation : choc -20% taux de guérison (maintien en ITT plus long)
        → Impact = PM_rentes × CHOC_CESSATION

        SCR_Longévité : choc -20% mortalité des invalides (rentes plus longues)
        → Impact = PM_rentes × 0.20 × facteur_longévité

        Agrégation : corrélation = 0.25 entre modules (EIOPA Annexe IV)
        """
        pa   = src['primes_acquises']
        pm   = src['pm_rentes_ip']
        psap = src['psap_total']

        # SCR Morbidité : +35% incidence → hausse BE
        # Impact estimé = CHOC × PA × (1 + duree_arret_moyenne)
        scr_morb = be_prev * CHOC_MORBIDITE_HAUSSE

        # SCR Cessation : -20% guérisons → PM rentes augmentent
        # Les invalides restent plus longtemps → provision plus élevée
        scr_cess = max(pm, psap * 0.5) * CHOC_CESSATION_BAISSE

        # SCR Longévité : invalides vivent plus longtemps
        # Choc EIOPA : -20% mortalité sur les rentes IP
        facteur_longevite = src['duree_ip_ans'] / 25.0   # normalisé 25 ans
        scr_long = pm * 0.20 * facteur_longevite

        # Agrégation matricielle (corrélation 0.25 entre modules)
        corr = np.array([
            [1.00, 0.25, 0.25],
            [0.25, 1.00, 0.25],
            [0.25, 0.25, 1.00],
        ])
        v = np.array([scr_morb, scr_cess, scr_long])
        scr_total = float(np.sqrt(max(float(v @ corr @ v), 0.0)))

        # SCR opérationnel prévoyance (3% PA)
        scr_ope = 0.03 * pa

        # SCR total
        scr_final = np.sqrt(scr_total**2 + scr_ope**2)

        return {
            'scr_morbidite':  round(scr_morb, 2),
            'scr_cessation':  round(scr_cess, 2),
            'scr_longevite':  round(scr_long, 2),
            'scr_operationnel': round(scr_ope, 2),
            'scr_invalide':   round(scr_total, 2),
            'scr_total':      round(scr_final, 2),
            'choc_morbidite': CHOC_MORBIDITE_HAUSSE,
            'choc_cessation': CHOC_CESSATION_BAISSE,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 3. MCR PRÉVOYANCE
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_mcr(self, src, scr):
        """
        MCR Prévoyance — coefficients spécifiques branche prévoyance.
        Différents des coefficients Non-Vie (α=0.0418, β=0.0261).
        Plancher absolu prévoyance = 3.7M€ (vs 2.5M€ santé/Non-Vie).
        """
        mcr_lin   = MCR_ALPHA_PREV * src['primes_acquises'] + \
                    MCR_BETA_PREV  * src['be_prevoyance']
        plancher  = max(0.25 * scr['scr_total'], MCR_PLANCHER_ABS)
        plafond   = 0.45 * scr['scr_total']
        mcr       = max(min(mcr_lin, plafond), plancher)

        if mcr_lin < plancher:
            regime = 'PLANCHER_ACTIF'
        elif mcr_lin > plafond:
            regime = 'PLAFOND_ACTIF'
        else:
            regime = 'MCR_LINEAIRE'

        return {
            'mcr':          round(mcr, 2),
            'mcr_lineaire': round(mcr_lin, 2),
            'plancher':     round(plancher, 2),
            'plafond':      round(plafond, 2),
            'regime':       regime,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 4. QRT S.14.01
    # ══════════════════════════════════════════════════════════════════════════
    def _generer_qrt(self, be, ra, tp, scr, mcr,
                     r_scr, r_mcr, fpp, src):
        """
        QRT S.14.01 — Vie & Prévoyance.
        Spécifique prévoyance : PM Rentes IP séparées de PSAP ITT.
        """
        return {
            'code':  'S.14.01',
            'titre': 'Life and Health SLT — Prévoyance Collective',
            'lignes': [
                {'code':'R0010','libelle':'BE Prévoyance (PM Rentes + PSAP ITT)',
                 'C0010': round(be, 0)},
                {'code':'R0011','libelle':'  dont PM Rentes IP (long terme)',
                 'C0010': round(src['pm_rentes_ip'], 0)},
                {'code':'R0012','libelle':'  dont PSAP ITT',
                 'C0010': round(src['psap_total'], 0)},
                {'code':'R0020','libelle':'Risk Adjustment (CoC 8% BE prévoyance)',
                 'C0010': round(ra, 0)},
                {'code':'R0030','libelle':'TP Prévoyance (BE + RA)',
                 'C0010': round(tp, 0)},
                {'code':'R0040','libelle':'SCR Morbidité (choc +35% incidence)',
                 'C0040': round(scr['scr_morbidite'], 0)},
                {'code':'R0041','libelle':'SCR Cessation (choc -20% guérison)',
                 'C0040': round(scr['scr_cessation'], 0)},
                {'code':'R0042','libelle':'SCR Longévité (choc -20% mortalité invalides)',
                 'C0040': round(scr['scr_longevite'], 0)},
                {'code':'R0050','libelle':'SCR Invalidité (agrégé)',
                 'C0040': round(scr['scr_invalide'], 0)},
                {'code':'R0060','libelle':'SCR Opérationnel Prévoyance',
                 'C0040': round(scr['scr_operationnel'], 0)},
                {'code':'R0070','libelle':'SCR Total Prévoyance',
                 'C0040': round(scr['scr_total'], 0)},
                {'code':'R0080','libelle':'MCR Prévoyance',
                 'C0040': round(mcr['mcr'], 0)},
                {'code':'R0090','libelle':'Fonds Propres',
                 'C0050': round(fpp, 0)},
                {'code':'R0100','libelle':'Ratio SCR (%)',
                 'C0060': round(r_scr, 1)},
                {'code':'R0110','libelle':'Ratio MCR (%)',
                 'C0060': round(r_mcr, 1)},
                {'code':'R0120','libelle':'Primes acquises',
                 'C0010': round(src['primes_acquises'], 0)},
                {'code':'R0130','libelle':'Loss Ratio',
                 'C0060': round(src['loss_ratio'], 4)},
            ],
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 5. HYPOTHÈSES
    # ══════════════════════════════════════════════════════════════════════════
    def _hypotheses(self, be, scr, ratio_scr, ratio_mcr, src):
        # H1 — BE/PA ≤ 50% (prévoyance plus chargée que santé)
        ratio_be = be / max(src['primes_acquises'], 1)
        if ratio_be <= 0.50:
            h1_s = 'VALIDÉE'
            h1_m = f"BE/PA = {ratio_be*100:.1f}% ≤ 50% ✅ — provisions cohérentes"
        elif ratio_be <= 0.80:
            h1_s = 'À JUSTIFIER'
            h1_m = f"BE/PA = {ratio_be*100:.1f}% ∈ [50%,80%] — vérifier PM rentes"
        else:
            h1_s = 'NON VALIDÉE'
            h1_m = f"BE/PA = {ratio_be*100:.1f}% > 80% — surprovisionnement"

        # H2 — SCR Morbidité dominant (> 50% SCR total)
        part_morb = scr['scr_morbidite'] / max(scr['scr_invalide'], 1)
        if part_morb >= 0.40:
            h2_s = 'VALIDÉE'
            h2_m = f"SCR Morbidité = {part_morb*100:.1f}% du SCR Invalidité ✅"
        else:
            h2_s = 'À JUSTIFIER'
            h2_m = f"SCR Morbidité = {part_morb*100:.1f}% — déséquilibre modules"

        # H3 — Ratio SCR ≥ 100%
        if ratio_scr >= 130:
            h3_s = 'VALIDÉE'
            h3_m = f"Ratio SCR = {ratio_scr:.1f}% ≥ 130% ✅"
        elif ratio_scr >= 100:
            h3_s = 'À JUSTIFIER'
            h3_m = f"Ratio SCR = {ratio_scr:.1f}% ∈ [100%,130%] — surveiller"
        else:
            h3_s = 'NON VALIDÉE'
            h3_m = f"Ratio SCR = {ratio_scr:.1f}% < 100% — insuffisance capital"

        return [
            {'id':'H1','hypothese':'BE/PA ≤ 50% — provisions prévoyance cohérentes',
             'valeur':h1_m,'statut':h1_s,'critique':True},
            {'id':'H2','hypothese':'SCR Morbidité ≥ 40% SCR Invalidité — module dominant',
             'valeur':h2_m,'statut':h2_s,'critique':True},
            {'id':'H3','hypothese':'Ratio SCR ≥ 130% — capitalisation prévoyance solide',
             'valeur':h3_m,'statut':h3_s,'critique':True},
        ]

    def _rag(self, hyp, ratio_scr, ratio_mcr):
        if ratio_mcr < 100: return 'ROUGE'
        non_val = [h for h in hyp if h['statut']=='NON VALIDÉE']
        if non_val or ratio_scr < 100: return 'ROUGE'
        a_just = [h for h in hyp if h['statut']=='À JUSTIFIER']
        if a_just or ratio_scr < 130:  return 'AMBRE'
        return 'VERT'

    # ══════════════════════════════════════════════════════════════════════════
    # 6. COMMENTAIRE
    # ══════════════════════════════════════════════════════════════════════════
    def _commentaire(self, rag, be, ra, tp, scr, mcr,
                     r_scr, r_mcr, fpp, src, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        L = [
            "="*70,
            f"  RAPPORT REPORTING PRÉVOYANCE — P4 VALENTIN v{self.VERSION}",
            f"  QRT S.14.01 | SCR Invalidité EIOPA | {src['nb_assures']} assuré(s)",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
        ]
        if rag=='VERT':
            L.append(f"✅ QRT S.14.01 conforme. SCR={r_scr:.1f}% | MCR={r_mcr:.1f}%.")
        elif rag=='AMBRE':
            L.append(f"⚠️ Acceptable — vérifier les points signalés.")
        else:
            L.append(f"❌ NON CONFORME — action corrective requise.")

        L += [
            "", "🔢 QRT S.14.01 — PRÉVOYANCE", "─"*40,
            f"  PM Rentes IP (long terme)     : {src['pm_rentes_ip']:>12,.0f}€",
            f"  PSAP ITT                       : {src['psap_total']:>12,.0f}€",
            f"  BE Prévoyance (PM + PSAP)      : {be:>12,.0f}€",
            f"  Risk Adjustment (8% BE)        : {ra:>12,.0f}€",
            f"  TP Prévoyance                  : {tp:>12,.0f}€",
            "  " + "─"*45,
            f"  SCR Morbidité (+35% incidence) : {scr['scr_morbidite']:>12,.0f}€",
            f"  SCR Cessation (-20% guérison)  : {scr['scr_cessation']:>12,.0f}€",
            f"  SCR Longévité (-20% mortalité) : {scr['scr_longevite']:>12,.0f}€",
            f"  SCR Invalidité (agrégé EIOPA)  : {scr['scr_invalide']:>12,.0f}€",
            f"  SCR Opérationnel               : {scr['scr_operationnel']:>12,.0f}€",
            f"  SCR Total Prévoyance           : {scr['scr_total']:>12,.0f}€",
            "  " + "─"*45,
            f"  MCR Prévoyance                 : {mcr['mcr']:>12,.0f}€  [{mcr['regime']}]",
            f"  Fonds Propres                  : {fpp:>12,.0f}€",
            f"  Ratio SCR                      : {r_scr:>11.1f}%",
            f"  Ratio MCR                      : {r_mcr:>11.1f}%",
            "", "📋 HYPOTHÈSES", "─"*40,
        ]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else "⚠️"
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        L += ["", "🎯 AVIS VALENTIN → DIALLO", "─"*40]
        if rag=='VERT':
            L.append("✅ QRT S.14.01 prêt. Données transmises à Naomie (stress testing SP).")
        elif rag=='AMBRE':
            L.append("⚠️ Documenter avant soumission. Transmission Naomie possible.")
        else:
            L.append("❌ NON CONFORME — Escalade Diallo/Amira avant Naomie.")
        L.append("")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════════════════════
    # 7. GRAPHIQUES
    # ══════════════════════════════════════════════════════════════════════════
    def _graphiques(self, be, ra, tp, scr, mcr,
                    fpp, r_scr, r_mcr, src, hyp):
        gph = {}

        # G1 — Décomposition BE prévoyance
        try:
            fig = go.Figure(go.Bar(
                x=["PM Rentes IP\n(long terme)","PSAP ITT\n(court terme)",
                   "Risk Adj. 8%","TP Prévoyance"],
                y=[src['pm_rentes_ip']/1e3, src['psap_total']/1e3,
                   ra/1e3, tp/1e3],
                marker_color=[ROUGE, AMBRE, BLEU, OR],
                width=0.45, opacity=0.88,
                text=[f"{v:.0f}k€" for v in
                      [src['pm_rentes_ip']/1e3, src['psap_total']/1e3,
                       ra/1e3, tp/1e3]],
                textposition="outside", textfont=dict(color=BLANC,size=10),
            ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G1 — BE Prévoyance : PM Rentes IP vs PSAP ITT",
                           font=dict(color=OR,size=12),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC,size=8),showgrid=False),
                yaxis=dict(visible=False),
                annotations=[dict(
                    text="💡 PM Rentes = provisions long terme (actuariat vie). PSAP = dossiers ITT en cours.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['be_decompose_prev'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — SCR Invalidité décomposé
        try:
            fig = go.Figure(go.Bar(
                x=["Morbidité\n(+35% incidence)",
                   "Cessation\n(-20% guérison)",
                   "Longévité\n(-20% mortalité)",
                   "Opérationnel"],
                y=[scr['scr_morbidite']/1e3, scr['scr_cessation']/1e3,
                   scr['scr_longevite']/1e3, scr['scr_operationnel']/1e3],
                marker_color=[ROUGE, AMBRE, VIOLET, BLEU],
                width=0.45, opacity=0.88,
                text=[f"{v:.0f}k€" for v in
                      [scr['scr_morbidite']/1e3, scr['scr_cessation']/1e3,
                       scr['scr_longevite']/1e3, scr['scr_operationnel']/1e3]],
                textposition="outside", textfont=dict(color=BLANC,size=10),
            ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text=f"G2 — SCR Invalidité EIOPA décomposé | Total={scr['scr_total']/1e3:.0f}k€",
                           font=dict(color=OR,size=12),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC,size=8),showgrid=False),
                yaxis=dict(visible=False),
                annotations=[dict(
                    text="💡 Morbidité = choc dominant (+35% incidence ITT/IP). Corrélation 0.25 entre modules EIOPA.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['scr_invalidite_decompose'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — Double jauge SCR/MCR
        try:
            c_scr = VERT if r_scr>=130 else (AMBRE if r_scr>=100 else ROUGE)
            c_mcr = VERT if r_mcr>=100 else ROUGE
            fig = make_subplots(rows=1, cols=2,
                specs=[[{'type':'indicator'},{'type':'indicator'}]],
                subplot_titles=['Ratio SCR Prévoyance','Ratio MCR Prévoyance'])
            for col, val, c in [(1,r_scr,c_scr),(2,r_mcr,c_mcr)]:
                fig.add_trace(go.Indicator(
                    mode="gauge+number", value=val,
                    number=dict(suffix="%",font=dict(color=c,size=24),valueformat=".1f"),
                    gauge=dict(
                        axis=dict(range=[0,300],tickvals=[0,100,130,200,300],
                                  ticktext=["0","100%","130%","200%","300%"],
                                  tickfont=dict(color=GRIS,size=8)),
                        bar=dict(color=c,thickness=0.25),bgcolor=NAVY_L,borderwidth=0,
                        steps=[
                            dict(range=[0,100],   color="rgba(231,76,60,0.2)"),
                            dict(range=[100,130],  color="rgba(243,156,18,0.2)"),
                            dict(range=[130,300],  color="rgba(46,204,113,0.1)"),
                        ],
                        threshold=dict(line=dict(color=ROUGE,width=2),thickness=0.8,value=100),
                    )), row=1, col=col)
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G3 — Ratios Couverture SCR/MCR Prévoyance",
                           font=dict(color=OR,size=12),x=0.01),
                annotations=[dict(
                    text="💡 SCR prévoyance ≥ 130% recommandé. MCR plancher 3.7M€ (vs 2.5M€ santé).",
                    xref="paper",yref="paper",x=0.5,y=-0.12,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['jauges_scr_mcr_prev'] = fig
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
                title=dict(text="G4 — Scorecard QRT Prévoyance S.14.01",
                           font=dict(color=cg,size=12),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=9),showgrid=False),
                barmode="overlay",height=260,
                annotations=[dict(
                    text="💡 3 ✅ = QRT S.14.01 prêt pour Naomie (stress testing SP).",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['scorecard_p4'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        return gph

    # ══════════════════════════════════════════════════════════════════════════
    def _audit(self, aid, r_scr, r_mcr, be, rag):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'ratio_scr':r_scr,'ratio_mcr':r_mcr,'be_prevoyance':be}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, rag, be, tp, scr, r_scr, r_mcr):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        print(f"\n{'─'*70}")
        print(f"  P4 VALENTIN v{self.VERSION} | {aid} | {ic} {rag}")
        print(f"  BE={be:,.0f}€ | TP={tp:,.0f}€ | SCR={scr:,.0f}€ | {r_scr:.1f}%/{r_mcr:.1f}%")
        print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {'success':False,'agent':self.NOM,'version':self.VERSION,
                'audit_id':aid,'statut_rag':'ROUGE',
                'be_prevoyance':0,'tp_prevoyance':0,'scr_invalidite':0,
                'ratio_scr_pct':0,'qrt_s14':{},'sorties_naomie':{},
                'hypotheses':[],'commentaire':f"❌ ERREUR P4:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  P4 VALENTIN v2.0 — DÉMO REPORTING PRÉVOYANCE QRT S.14")
    print("  SCR Invalidité EIOPA | MCR prévoyance | QRT S.14.01")
    print("="*70)

    import sys; sys.path.insert(0,'/home/claude')
    from axel_p1_tarification_prevoyance import AgentP1TarificationPrevoyance
    from rayan_p2_tables_morbidite import AgentP2TablesMorbidite
    from elodie_p3_provisionnement_prevoyance import AgentP3ProvisionnemntPrevoyance

    r1 = AgentP1TarificationPrevoyance(models_path='/tmp',audit_path='/tmp',verbose=False).run(
        age=40, salaire_brut=45_000, categorie='employe',
        franchise_jours=90, taux_rente_ipp=0.60, duree_contrat=20,
        chargement_pct=0.20, generer_graphiques=False)
    r2 = AgentP2TablesMorbidite(models_path='/tmp',audit_path='/tmp',verbose=False).run(
        result_p1=r1, horizon_ans=10, generer_graphiques=False)
    r3 = AgentP3ProvisionnemntPrevoyance(models_path='/tmp',audit_path='/tmp',verbose=False).run(
        result_p1=r1, result_p2=r2, generer_graphiques=False)

    agent = AgentP4ReportingPrevoyance(
        models_path='/tmp/p4/models', audit_path='/tmp/p4/audit', verbose=True
    )
    r = agent.run(result_p1=r1, result_p2=r2, result_p3=r3,
                  fonds_propres=5_000_000, generer_graphiques=False)

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut         : {r['statut_rag']}")
    print(f"  PM Rentes IP   : {r['pm_rentes_ip']:>12,.0f}€")
    print(f"  PSAP ITT       : {r['psap_total']:>12,.0f}€")
    print(f"  BE Prévoyance  : {r['be_prevoyance']:>12,.0f}€")
    print(f"  TP Prévoyance  : {r['tp_prevoyance']:>12,.0f}€")
    print(f"  SCR Morbidité  : {r['scr_morbidite']:>12,.0f}€")
    print(f"  SCR Cessation  : {r['scr_cessation']:>12,.0f}€")
    print(f"  SCR Longévité  : {r['scr_longevite']:>12,.0f}€")
    print(f"  SCR Total      : {r['scr_invalidite']:>12,.0f}€")
    print(f"  MCR            : {r['mcr']:>12,.0f}€")
    print(f"  Ratio SCR      : {r['ratio_scr_pct']:>11.1f}%")
    print(f"  Ratio MCR      : {r['ratio_mcr_pct']:>11.1f}%")
    print(f"  QRT lignes     : {len(r['qrt_s14']['lignes'])}")
    print(f"  Durée          : {r['duree_sec']:.2f}s")
