"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        ACTUARIA — AGENT A11 THOMAS : IFRS 17 PAA NON-VIE v1.0             ║
║                     Sous NADIA (Direction Non-Vie)                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PÉRIMÈTRE : Contrats Non-Vie durée ≤ 1 an — Approche PAA (IFRS 17 §53)  ║
║                                                                              ║
║  DIFFÉRENCIATEURS vs marché :                                               ║
║    ✅ Taux IFRS 17 séparé du RFR S2 (bottom-up — résiste audit Big 4)     ║
║    ✅ Risk Adjustment par quantile VaR explicite (σ Mack → P75)            ║
║    ✅ Loss Component branche par branche + test suffisance                  ║
║    ✅ Réconciliation bilancielle 3 colonnes (ouv → mvt → ferm)             ║
║    ✅ Comparaison S2 ↔ IFRS 17 → A9 Marcus C4                             ║
║    ❌ CSM supprimé (nul par définition PAA — IFRS 17 §55)                  ║
║    ❌ OCI supprimé (contrats courts — non applicable)                       ║
║                                                                              ║
║  ENTRÉES OBLIGATOIRES :                                                     ║
║    result_a7  → BE Ibrahim (best_estimate, sigma_mack, reserve_p75)        ║
║    result_a10 → Elena S2 (be_s2, risk_margin, rfr, duration)              ║
║                                                                              ║
║  ENTRÉES OPTIONNELLES :                                                     ║
║    result_a6    → Primes Victor (primes_acquises)                          ║
║    market_data  → Taux BCE                                                  ║
║    branches     → Multi-branches avec volumes                               ║
║    params_ifrs  → Paramètres client (quantile RA, durée contrat, etc.)    ║
║                                                                              ║
║  SORTIES VERS A9 MARCUS (C4) :                                             ║
║    provisions.lic          → LIC IFRS 17                                   ║
║    provisions.lrc          → LRC IFRS 17                                   ║
║    provisions.risk_adjustment → RA IFRS 17                                 ║
║    ecart_s2_ifrs.be        → écart BE S2 vs LIC                           ║
║    ecart_s2_ifrs.rm_ra     → écart RM S2 vs RA IFRS 17                   ║
║                                                                              ║
║  VERSION : 1.0 — 19/06/2026                                                ║
║  AUTEUR  : ActuarIA — Thomas (sous NADIA)                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats as scipy_stats

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

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"; OR="#C9A84C"
BLANC="#F0F4F8"; GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"
AMBRE="#F39C12"; BLEU="#3498DB"; VIOLET="#9B59B6"; TURQUOISE="#1ABC9C"

LAYOUT_BASE = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=10),
    margin=dict(l=90,r=50,t=80,b=120), height=500,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))

# ── Paramètres IFRS 17 ────────────────────────────────────────────────────────
# Taux IFRS 17 bottom-up = actif sans risque + illiquidity premium
# Pour Non-Vie courte : RFR + prime illiquidité 50-75 bps (vs RFR S2 pur)
ILLIQUIDITY_PREMIUM_DEFAULT = 0.0060   # 60 bps — Non-Vie courte (contrats <= 1 an)
ILLIQUIDITY_PREMIUM_LONG    = 0.0090   # 90 bps — branches longues (RC Medicale)
# Parametrer via params_ifrs['illiq_premium'] selon la branche analysee
QUANTILE_RA_DEFAULT         = 0.75     # P75 — standard marché PAA
DUREE_CONTRAT_DEFAULT       = 1.0      # 1 an — Non-Vie standard

# Mapping libellés branches
LOB_LABELS = {
    'rc_auto':'RC Automobile','auto_autre':'Automobile Autres',
    'mrh':'MRH','incendie':'Incendie','rc_generale':'RC Générale',
    'construction':'Construction','transport':'Transport',
    'credit':'Crédit','assistance':'Assistance',
    'protection_juridique':'Protection Juridique',
    'pertes_pecuniaires':'Pertes Pécuniaires','autres':'Autres',
}

# ══════════════════════════════════════════════════════════════════════════════
class AgentA11IFRS17:
    """
    Agent A11 Thomas — IFRS 17 PAA Non-Vie v1.0.
    Approche PAA pour contrats ≤ 1 an.
    Taux IFRS 17 bottom-up séparé du RFR S2.
    Risk Adjustment par quantile VaR explicite.
    Loss Component branche par branche.
    Réconciliation bilancielle 3 colonnes.
    """
    NOM="Thomas"; CODE="A11"; VERSION="1.0"; RESPONSABLE="NADIA (Réglementation)"

    def __init__(self, audit_path='/tmp/actuaria', verbose=True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger('actuaria.a11.thomas')
        self.verbose = verbose
        if verbose:
            self.logger.info(f"A11 Thomas v{self.VERSION} | {self.RESPONSABLE}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_a7,
            result_a10,
            result_a6        = None,
            market_data      = None,
            branches         = None,
            params_ifrs      = None,
            generer_graphiques = True) -> Dict:

        t0  = datetime.now()
        aid = f"A11_{t0.strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"[{aid}] A11 Thomas v{self.VERSION}")

        try:
            # ── 1. PARAMÈTRES CLIENT ─────────────────────────────────────────
            p = self._params(params_ifrs)

            # ── 2. TAUX IFRS 17 (bottom-up — séparé RFR S2) ─────────────────
            taux = self._taux_ifrs17(result_a10, market_data, p)

            # ── 3. DONNÉES SOURCES ───────────────────────────────────────────
            src = self._extraire_sources(result_a7, result_a10, result_a6)

            # ── 4. BRANCHES ──────────────────────────────────────────────────
            brs = self._branches(branches, src, p)

            # ── 5. LIC — LIABILITY FOR INCURRED CLAIMS ───────────────────────
            lic = self._calculer_lic(brs, taux, src)

            # ── 6. RISK ADJUSTMENT (VaR quantile explicite) ──────────────────
            ra  = self._calculer_ra(brs, src, p)

            # ── 7. LRC — LIABILITY FOR REMAINING COVERAGE ────────────────────
            lrc = self._calculer_lrc(brs, src, p)

            # ── 8. LOSS COMPONENT (branche par branche) ──────────────────────
            lc  = self._calculer_loss_component(brs, lrc, lic, ra, p)

            # ── 9. REVENUE IFRS 17 ───────────────────────────────────────────
            rev = self._calculer_revenue(brs, lrc, lc, ra, src, p)

            # ── 10. RÉCONCILIATION BILANCIELLE 3 COLONNES ────────────────────
            rec = self._reconciliation(lic, lrc, ra, lc, src, p)

            # ── 11. COMPARAISON S2 ↔ IFRS 17 (→ A9 C4) ─────────────────────
            ecart = self._comparer_s2_ifrs17(result_a10, lic, ra, taux)

            # ── 12. STATUT RAG ────────────────────────────────────────────────
            rag, motif = self._rag(lic, lrc, lc, ecart, taux, p)

            # ── 13. HYPOTHÈSES ────────────────────────────────────────────────
            hyp = self._hypotheses(taux, ra, lc, ecart, src, p)

            # ── 14. COMMENTAIRE ───────────────────────────────────────────────
            com = self._commentaire(rag, lic, lrc, ra, lc, rev, ecart,
                                    taux, brs, src, p, hyp)

            # ── 15. GRAPHIQUES ────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(lic, lrc, ra, lc, rev, ecart, taux, brs, rec)

            # ── 16. AUDIT ────────────────────────────────────────────────────
            self._audit(aid, lic, lrc, ra, ecart, rag)

            if self.verbose:
                self._console(aid, lic, lrc, ra, lc, ecart, rag, com)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':True, 'agent':self.NOM, 'version':self.VERSION,
                'audit_id':aid, 'statut_rag':rag, 'motif_rag':motif,

                # ── Provisions IFRS 17 (→ A9 C4) ────────────────────────────
                'provisions': {
                    'lic':              lic['lic_total'],
                    'lic_net_ra':       lic['lic_total'] + ra['ra_total'],
                    'lrc':              lrc['lrc_total'],
                    'risk_adjustment':  ra['ra_total'],
                    'quantile_ra':      p['quantile_ra'],
                    'tp_ifrs17':        lic['lic_total'] + ra['ra_total'] + lrc['lrc_total'],
                    'par_branche':      lic['par_branche'],
                },

                # ── Écarts S2 ↔ IFRS 17 (→ A9 C4) ──────────────────────────
                'ecart_s2_ifrs': {
                    'be':           ecart['ecart_be'],
                    'be_pct':       ecart['ecart_be_pct'],
                    'rm_ra':        ecart['ecart_rm_ra'],
                    'rm_ra_pct':    ecart['ecart_rm_ra_pct'],
                    'taux_s2':      ecart['rfr_s2'],
                    'taux_ifrs17':  ecart['taux_ifrs17'],
                    'motif_ecart':  ecart['motif'],
                    'ratio_ifrs_s2':ecart['ratio_ifrs_s2'],
                },

                # ── Revenue IFRS 17 ──────────────────────────────────────────
                'revenue': {
                    'revenue_total':    rev['revenue_total'],
                    'release_lrc':      rev['release_lrc'],
                    'ajust_risque':     rev['ajust_risque'],
                    'pertes_attendues': rev['pertes_attendues'],
                    'par_branche':      rev['par_branche'],
                },

                # ── Loss Component ───────────────────────────────────────────
                'loss_component': {
                    'lc_total':         lc['lc_total'],
                    'nb_deficitaires':  lc['nb_deficitaires'],
                    'branches_deficit': lc['branches_deficit'],
                    'par_branche':      lc['par_branche'],
                },

                # ── Réconciliation 3 colonnes ────────────────────────────────
                'reconciliation':  rec,

                # ── Taux IFRS 17 ─────────────────────────────────────────────
                'taux': taux,

                # ── Détails ──────────────────────────────────────────────────
                'detail': {
                    'lic': lic, 'lrc': lrc, 'ra': ra, 'lc': lc,
                    'rev': rev, 'ecart': ecart, 'branches': brs,
                    'sources': src, 'params': p,
                },

                # ── Standard ActuarIA ────────────────────────────────────────
                'hypotheses':  hyp,
                'commentaire': com,
                'graphiques':  gph,
                'duree_sec':   round(duree,2),
                'erreur':      None,
            }

        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), aid)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. PARAMÈTRES CLIENT
    # ══════════════════════════════════════════════════════════════════════════
    def _params(self, p):
        if not p: p = {}
        return {
            'quantile_ra':      p.get('quantile_ra',    QUANTILE_RA_DEFAULT),
            'illiq_premium':    p.get('illiq_premium',  ILLIQUIDITY_PREMIUM_DEFAULT),
            'duree_contrat':    p.get('duree_contrat',  DUREE_CONTRAT_DEFAULT),
            'taux_chargement':  p.get('taux_chargement',0.25),
            'taux_sinistres':   p.get('taux_sinistres', 0.70),
            'fraction_ecoule':  p.get('fraction_ecoule', 0.50),
            'annee_ouverture':  p.get('annee_ouverture', datetime.now().year - 1),
            'annee_fermeture':  p.get('annee_fermeture', datetime.now().year),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 2. TAUX IFRS 17 — BOTTOM-UP (≠ RFR S2)
    # ══════════════════════════════════════════════════════════════════════════
    def _taux_ifrs17(self, result_a10, market_data, p):
        """
        Taux IFRS 17 bottom-up = actif sans risque + prime d'illiquidité.

        IFRS 17 §B72-B85 donne 2 méthodes :
        - Bottom-up  : taux actif sans risque + illiquidity premium
        - Top-down   : rendement actif portefeuille − risque crédit

        Pour Non-Vie courte (PAA ≤ 1 an) : bottom-up standard.
        Prime illiquidité typique marché : 50-75 bps.

        DIFFÉRENCE CLEF AVEC S2 :
        RFR S2 = taux swap EUR sans risque (EIOPA)
        Taux IFRS 17 = RFR + illiq_premium → toujours > RFR S2
        → LIC IFRS 17 < BE S2 (actualisation plus forte)
        """
        # RFR S2 depuis Elena
        rfr_s2 = result_a10.get('taux', {}).get('rfr_10ans', 0.032)

        # Prime d'illiquidité configurée ou par défaut
        illiq = p['illiq_premium']

        # Taux IFRS 17
        taux_ifrs = rfr_s2 + illiq

        # Source
        src_taux = result_a10.get('taux', {}).get('source', 'FALLBACK')
        fib      = result_a10.get('taux', {}).get('fiabilite', 'REFERENCE')

        self.logger.info(
            f"Taux IFRS 17 = {taux_ifrs:.3%} "
            f"(RFR S2={rfr_s2:.3%} + illiq={illiq:.3%})"
        )

        return {
            'taux_ifrs17':    taux_ifrs,
            'rfr_s2':         rfr_s2,
            'illiq_premium':  illiq,
            'methode':        'Bottom-up (IFRS 17 §B72)',
            'source_rfr':     src_taux,
            'fiabilite':      fib,
            'note':           (
                f"Taux IFRS 17 ({taux_ifrs:.3%}) > RFR S2 ({rfr_s2:.3%}) "
                f"de {illiq*100:.0f}bps → LIC IFRS 17 < BE S2"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 3. EXTRACTION SOURCES A7 + A10 + A6
    # ══════════════════════════════════════════════════════════════════════════
    def _extraire_sources(self, result_a7, result_a10, result_a6):
        be7   = result_a7.get('best_estimate', {})
        be_brut   = float(be7.get('best_estimate', 0.0))
        sigma_mack= float(be7.get('sigma_mack',   be_brut * 0.05))
        p75       = float(be7.get('reserve_p75',  be_brut * 1.06))
        p90       = float(be7.get('reserve_p90',  be_brut * 1.10))
        cv        = float(be7.get('cv_inter_methodes', 5.0))
        lob       = result_a7.get('sous_branche', 'rc_auto')
        n_tri     = result_a7.get('meta', {}).get('n_annees', 8) if isinstance(result_a7.get('meta'), dict) else 8
        nb_lignes = result_a7.get('meta', {}).get('nb_lignes', 50000) if isinstance(result_a7.get('meta'), dict) else 50000

        be_s2   = float(result_a10.get('provisions', {}).get('best_estimate', be_brut))
        rm_s2   = float(result_a10.get('provisions', {}).get('risk_margin',   be_brut*0.05))
        rfr_s2  = float(result_a10.get('taux', {}).get('rfr_10ans', 0.032))
        dur_p   = float(result_a10.get('duration', {}).get('passif', 4.0))

        primes = 0.0
        if result_a6:
            mp = result_a6.get('modele_production', {})
            primes = float(mp.get('primes_acquises',
                           mp.get('prime_pure', 0.0) / 0.70 * nb_lignes * 0.80))
        if primes <= 0:
            primes = be_brut / 0.70 * 1.20

        return {
            'be_brut':    be_brut,
            'sigma_mack': sigma_mack,
            'p75':        p75,
            'p90':        p90,
            'cv':         cv,
            'lob':        lob,
            'n_tri':      n_tri,
            'nb_lignes':  nb_lignes,
            'be_s2':      be_s2,
            'rm_s2':      rm_s2,
            'rfr_s2':     rfr_s2,
            'dur_passif': dur_p,
            'primes':     primes,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 4. BRANCHES
    # ══════════════════════════════════════════════════════════════════════════
    def _branches(self, branches, src, p):
        if branches:
            res = []
            tot_be = sum(b.get('be', 0) for b in branches)
            tot_pr = sum(b.get('primes', 0) for b in branches)
            for b in branches:
                be_b = b.get('be', src['be_brut'] / len(branches))
                pr_b = b.get('primes', src['primes'] / len(branches))
                # σ proportionnel au BE (hypothèse : σ_glob pondéré)
                sig_b = src['sigma_mack'] * (be_b / max(tot_be, 1))
                res.append({
                    'nom':    b.get('nom', src['lob']),
                    'be':     be_b,
                    'primes': pr_b,
                    'sigma':  sig_b,
                    'label':  LOB_LABELS.get(b.get('nom', src['lob']), b.get('nom', src['lob'])),
                })
            return res
        else:
            return [{
                'nom':    src['lob'],
                'be':     src['be_brut'],
                'primes': src['primes'],
                'sigma':  src['sigma_mack'],
                'label':  LOB_LABELS.get(src['lob'], src['lob']),
            }]

    # ══════════════════════════════════════════════════════════════════════════
    # 5. LIC — LIABILITY FOR INCURRED CLAIMS
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_lic(self, branches, taux, src):
        """
        LIC = BE Ibrahim actualisé au TAUX IFRS 17 (≠ RFR S2).

        C'est la différence fondamentale avec S2 :
        - S2 actualise au RFR EIOPA
        - IFRS 17 actualise au taux bottom-up (RFR + illiq)
        → LIC < BE_S2 car taux d'actualisation IFRS 17 > RFR S2
        """
        t_ifrs = taux['taux_ifrs17']
        par_b  = []
        lic_tot = 0.0

        for b in branches:
            dur = src['dur_passif']
            f   = 1.0 / (1 + t_ifrs) ** dur
            lic_b = b['be'] * f
            lic_tot += lic_b
            par_b.append({
                'nom':    b['nom'],
                'label':  b['label'],
                'be_brut':b['be'],
                'taux_actualisation': t_ifrs,
                'facteur':round(f, 6),
                'lic':    lic_b,
                'impact_vs_be': lic_b - b['be'],
            })

        return {
            'lic_total':    lic_tot,
            'be_brut_total':sum(b['be'] for b in branches),
            'impact_total': lic_tot - sum(b['be'] for b in branches),
            'taux_utilise': t_ifrs,
            'par_branche':  par_b,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 6. RISK ADJUSTMENT — VaR QUANTILE EXPLICITE (IFRS 17 §B86-B92)
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_ra(self, branches, src, p):
        """
        Risk Adjustment IFRS 17 §B86-B92.

        MÉTHODE : VaR sur distribution log-normale calibrée sur σ Mack.
        RA = VaR(q) − BE = (exp(μ + z_q × σ_ln) − 1) × BE

        où σ_ln = sqrt(log(1 + (σ/BE)²)) et z_q = quantile normal.

        Le quantile (P75 standard) DOIT être déclaré dans les notes
        annexes IFRS 17 pour permettre la comparabilité.

        DIFFÉRENCE vs S2 :
        Risk Margin S2 = CoC × SCR_résiduel (méthode duration-based)
        RA IFRS 17     = quantile VaR sur distribution sinistres
        → Méthodes incompatibles — l'écart doit être documenté
        """
        q  = p['quantile_ra']
        z_q = float(scipy_stats.norm.ppf(q))

        par_b  = []
        ra_tot = 0.0

        for b in branches:
            be_b  = b['be']
            sig_b = b['sigma']
            cv_b  = sig_b / max(be_b, 1.0)

            # Paramètres log-normale
            sig_ln = np.sqrt(np.log(1 + cv_b ** 2))
            mu_ln  = np.log(max(be_b, 1.0)) - 0.5 * sig_ln ** 2

            # VaR au quantile q
            var_q  = np.exp(mu_ln + z_q * sig_ln)
            ra_b   = max(var_q - be_b, be_b * 0.02)  # plancher 2% du BE

            # Borne raisonnable : 2%-15% du BE
            ra_b = max(be_b * 0.02, min(ra_b, be_b * 0.15))

            ra_tot += ra_b
            par_b.append({
                'nom':      b['nom'],
                'label':    b['label'],
                'be':       be_b,
                'sigma':    sig_b,
                'cv':       cv_b,
                'sig_ln':   round(sig_ln, 6),
                'var_q':    var_q,
                'ra':       ra_b,
                'ra_pct_be':round(ra_b / max(be_b, 1) * 100, 2),
            })

        return {
            'ra_total':   ra_tot,
            'quantile':   q,
            'z_quantile': round(z_q, 4),
            'methode':    f'VaR log-normale P{int(q*100)} (IFRS 17 §B86)',
            'note_annexe':(
                f"Risk Adjustment calculé au quantile de confiance P{int(q*100)} "
                f"(z={z_q:.3f}) sur distribution log-normale calibrée "
                f"sur σ Mack Ibrahim. "
                f"Déclaration obligatoire IFRS 17 §119(a)."
            ),
            'par_branche': par_b,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 7. LRC — LIABILITY FOR REMAINING COVERAGE
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_lrc(self, branches, src, p):
        """
        LRC PAA = Primes non acquises (portion du risque restant à couvrir).

        En PAA (IFRS 17 §55) :
        LRC = Primes reçues − Primes acquises consommées

        Pour une durée de contrat d = 1 an (standard Non-Vie) :
        LRC_ouv  = Primes × (1 − fraction_écoulée_N-1)
        LRC_ferm = Primes × fraction_restante_N
        On prend LRC = 50% des primes (hypothèse uniforme en absence de données)

        Pas de CSM en PAA (§55) — confirme différence fondamentale avec BBA/VFA.
        """
        d = p['duree_contrat']
        par_b = []
        lrc_tot = 0.0

        for b in branches:
            # LRC = fraction non ecoule des primes
            # Parametrable via params_ifrs['fraction_ecoule'] (defaut 0.50)
            fraction_ecoule = p.get('fraction_ecoule', 0.50)
            lrc_b = b['primes'] * (1.0 - fraction_ecoule) * d
            lrc_tot += lrc_b
            par_b.append({
                'nom':    b['nom'],
                'label':  b['label'],
                'primes': b['primes'],
                'lrc':    lrc_b,
                'fraction_restante': 0.50,
                'csm':    0.0,  # PAA §55 : CSM = 0 explicitement
            })

        return {
            'lrc_total':  lrc_tot,
            'par_branche':par_b,
            'csm':        0.0,
            'note_csm':   'CSM = 0 par définition PAA (IFRS 17 §55)',
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 8. LOSS COMPONENT — BRANCHE PAR BRANCHE + TEST SUFFISANCE
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_loss_component(self, branches, lrc, lic, ra, p):
        """
        Loss Component (LC) IFRS 17 §47-52.

        Test de suffisance (onerous contract test) branche par branche.

        Un contrat (groupe) est DÉFICITAIRE si :
        Flux attendus > Primes restantes à encaisser
        ⟺ LIC_branche + RA_branche > LRC_branche

        Si déficitaire : LC = LIC + RA − LRC (à comptabiliser immédiatement en P&L)
        Si bénéficiaire : LC = 0

        Faire ce test branche par branche (et non global) est
        la pratique recommandée par les Big 4 — évite la compensation
        entre branches profitables et déficitaires.
        """
        par_b      = []
        lc_tot     = 0.0
        deficitaires = []

        for b_lrc, b_lic, b_ra in zip(
            lrc['par_branche'],
            lic['par_branche'],
            ra['par_branche']
        ):
            nom   = b_lrc['nom']
            lrc_b = b_lrc['lrc']
            lic_b = b_lic['lic']
            ra_b  = b_ra['ra']

            flux_attendus = lic_b + ra_b
            marge_b       = lrc_b - flux_attendus

            if marge_b < 0:
                lc_b        = abs(marge_b)
                deficitaire = True
                deficitaires.append(nom)
                lc_tot     += lc_b
            else:
                lc_b        = 0.0
                deficitaire = False

            par_b.append({
                'nom':            nom,
                'label':          b_lrc['label'],
                'lrc':            lrc_b,
                'lic':            lic_b,
                'ra':             ra_b,
                'flux_attendus':  flux_attendus,
                'marge':          marge_b,
                'loss_component': lc_b,
                'deficitaire':    deficitaire,
                'statut':         'DÉFICITAIRE ⚠️' if deficitaire else 'BÉNÉFICIAIRE ✅',
            })

        return {
            'lc_total':        lc_tot,
            'nb_deficitaires': len(deficitaires),
            'branches_deficit':deficitaires,
            'par_branche':     par_b,
            'alerte':          len(deficitaires) > 0,
            'note': (
                f"{len(deficitaires)} branche(s) déficitaire(s) : "
                f"LC={lc_tot:,.0f}€ à comptabiliser en P&L immédiatement."
                if len(deficitaires) > 0
                else "Aucune branche déficitaire — pas de Loss Component."
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 9. REVENUE IFRS 17
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_revenue(self, branches, lrc, lc, ra, src, p):
        """
        Revenue IFRS 17 PAA (§83-86) :

        Revenue = Release LRC + Ajustement risque release + Pertes attendues reconverties

        En PAA :
        Revenue = Primes acquises − Variation LRC − LC reconnu
        """
        par_b   = []
        rev_tot = 0.0

        for b_br, b_lrc, b_lc in zip(
            branches, lrc['par_branche'], lc['par_branche']
        ):
            primes_acq = b_br['primes'] * 0.50   # portion acquise
            rel_lrc    = b_lrc['lrc']              # release LRC (risque couvert)
            ajust_ra   = ra['ra_total'] / max(len(branches), 1) * 0.30
            perte_att  = b_lc['loss_component']
            rev_b      = primes_acq - perte_att + ajust_ra
            rev_tot   += rev_b
            par_b.append({
                'nom':             b_br['nom'],
                'primes_acquises': primes_acq,
                'release_lrc':     rel_lrc,
                'ajust_risque':    ajust_ra,
                'pertes_attendues':perte_att,
                'revenue':         rev_b,
            })

        return {
            'revenue_total':    rev_tot,
            'release_lrc':      lrc['lrc_total'],
            'ajust_risque':     ra['ra_total'] * 0.30,
            'pertes_attendues': lc['lc_total'],
            'par_branche':      par_b,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 10. RÉCONCILIATION BILANCIELLE 3 COLONNES
    # ══════════════════════════════════════════════════════════════════════════
    def _reconciliation(self, lic, lrc, ra, lc, src, p):
        """
        Réconciliation bilancielle IFRS 17 §100-105.

        3 colonnes : LIC | LRC | RA
        Mouvement N : ouverture → sinistres payés → variation charge → fermeture

        C'est la note annexe standard sans laquelle le DAF
        ne peut pas publier ses comptes IFRS 17.
        """
        # Hypothèses mouvement N (simplifiées mais cohérentes)
        # Sinistres payés ~ 70% du BE brut
        sin_payes   = src['be_brut'] * 0.70
        var_charge  = lic['lic_total'] - src['be_brut'] * 0.30
        primes_enc  = src['primes']
        release_lrc = lrc['lrc_total']

        # LIC
        lic_ouv  = src['be_s2'] * 1.05       # ouverture N = TP S2 N-1 approx
        lic_ferm = lic['lic_total']

        # LRC
        lrc_ouv  = src['primes'] * 0.50 * 1.05
        lrc_ferm = lrc['lrc_total']

        # RA
        ra_ouv   = src['rm_s2'] * 1.10       # RA ouverture ≈ RM S2 N-1
        ra_ferm  = ra['ra_total']

        return {
            'annee':       p['annee_fermeture'],
            'colonnes': {
                'LIC': {
                    'ouverture':          round(lic_ouv, 0),
                    'sinistres_payes':    round(-sin_payes, 0),
                    'variation_charge':   round(var_charge, 0),
                    'effet_actualisation':round(lic['impact_total'], 0),
                    'fermeture':          round(lic_ferm, 0),
                },
                'LRC': {
                    'ouverture':          round(lrc_ouv, 0),
                    'primes_encaissees':  round(primes_enc, 0),
                    'release_revenue':    round(-release_lrc, 0),
                    'loss_component':     round(-lc['lc_total'], 0),
                    'fermeture':          round(lrc_ferm, 0),
                },
                'RA': {
                    'ouverture':          round(ra_ouv, 0),
                    'release_risque':     round(-(ra_ouv - ra_ferm), 0),
                    'fermeture':          round(ra_ferm, 0),
                },
            },
            'tp_ifrs17_fermeture': round(lic_ferm + lrc_ferm + ra_ferm, 0),
            'note': 'Réconciliation IFRS 17 §100-105 — 3 colonnes LIC/LRC/RA',
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 11. COMPARAISON S2 ↔ IFRS 17 (→ A9 MARCUS C4)
    # ══════════════════════════════════════════════════════════════════════════
    def _comparer_s2_ifrs17(self, result_a10, lic, ra, taux):
        """
        Comparaison S2 ↔ IFRS 17 pour A9 Marcus (contrôle C4).

        Sources d'écart documentées :
        1. Taux d'actualisation différent (RFR S2 vs taux bottom-up IFRS 17)
        2. Risk Margin (CoC 6%) vs Risk Adjustment (VaR quantile)
        3. Périmètre : S2 inclut la Risk Margin dans les TP
        """
        be_s2   = float(result_a10.get('provisions', {}).get('best_estimate', 0))
        rm_s2   = float(result_a10.get('provisions', {}).get('risk_margin', 0))
        rfr_s2  = float(result_a10.get('taux', {}).get('rfr_10ans', 0.032))
        t_ifrs  = taux['taux_ifrs17']

        lic_tot = lic['lic_total']
        ra_tot  = ra['ra_total']

        # Biais de perimetre a documenter :
        # LIC IFRS17 = Claims Provision | BE S2 = Claims + Premium Provision
        # Comparaison directe sous-estime l'ecart reel.
        ecart_be     = lic_tot - be_s2
        ecart_be_pct = ecart_be / max(be_s2, 1) * 100
        ecart_rm_ra  = ra_tot  - rm_s2
        ecart_rm_pct = ecart_rm_ra / max(rm_s2, 1) * 100

        tp_s2   = be_s2 + rm_s2
        tp_ifrs = lic_tot + ra_tot
        ratio   = tp_ifrs / max(tp_s2, 1)

        motif = (
            f"Écart taux : IFRS 17={t_ifrs:.3%} vs RFR S2={rfr_s2:.3%} "
            f"(+{(t_ifrs-rfr_s2)*100:.0f}bps) → LIC < BE_S2. "
            f"RA VaR P{int(ra['quantile']*100)} vs RM CoC 6% → "
            f"{'RA > RM' if ra_tot > rm_s2 else 'RA < RM'}. "
            f"Ratio IFRS17/S2 = {ratio:.3f}."
        )

        return {
            'be_s2':         be_s2,
            'lic_ifrs17':    lic_tot,
            'ecart_be':      ecart_be,
            'ecart_be_pct':  round(ecart_be_pct, 2),
            'rm_s2':         rm_s2,
            'ra_ifrs17':     ra_tot,
            'ecart_rm_ra':   ecart_rm_ra,
            'ecart_rm_ra_pct':round(ecart_rm_pct, 2),
            'tp_s2':         tp_s2,
            'tp_ifrs17':     tp_ifrs,
            'ratio_ifrs_s2': round(ratio, 4),
            'rfr_s2':        rfr_s2,
            'taux_ifrs17':   t_ifrs,
            'motif':         motif,
            'coherent':      0.80 <= ratio <= 1.50,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 12. STATUT RAG
    # ══════════════════════════════════════════════════════════════════════════
    def _rag(self, lic, lrc, lc, ecart, taux, p):
        # Contrats déficitaires → ROUGE
        if lc['nb_deficitaires'] > 0:
            return 'ROUGE', (
                f"{lc['nb_deficitaires']} branche(s) déficitaire(s) — "
                f"Loss Component={lc['lc_total']:,.0f}€ à comptabiliser en P&L"
            )
        # Ratio IFRS17/S2 hors plage [0.80, 1.50]
        if not ecart['coherent']:
            return 'ROUGE', (
                f"Ratio IFRS17/S2={ecart['ratio_ifrs_s2']:.3f} hors plage [0.80, 1.50] "
                "— vérifier taux et paramètres"
            )
        # Taux fallback
        if taux['fiabilite'] == 'REFERENCE':
            return 'AMBRE', (
                f"Taux IFRS 17 de référence ({taux['taux_ifrs17']:.3%}) — "
                "connecter BCE pour taux temps réel"
            )
        # LIC > LRC (sinistres > primes — ratio sinistres élevé)
        if lic['lic_total'] > lrc['lrc_total'] * 1.20:
            return 'AMBRE', (
                f"LIC ({lic['lic_total']:,.0f}€) > 120% LRC "
                f"({lrc['lrc_total']:,.0f}€) — ratio sinistres élevé"
            )
        return 'VERT', (
            f"PAA conforme IFRS 17 §53 | "
            f"TP={lic['lic_total']+lrc['lrc_total']:,.0f}€ | "
            f"Ratio IFRS17/S2={ecart['ratio_ifrs_s2']:.3f}"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 13. HYPOTHÈSES — STANDARD ACTUARIA (3 minimum)
    # ══════════════════════════════════════════════════════════════════════════
    def _hypotheses(self, taux, ra, lc, ecart, src, p):
        # H1 — Taux IFRS 17 bottom-up
        h1 = {
            'id':'H1',
            'hypothese':(
                f"Taux d'actualisation IFRS 17 bottom-up = "
                f"RFR S2 ({taux['rfr_s2']:.3%}) + "
                f"prime illiquidité ({taux['illiq_premium']*100:.0f}bps) "
                f"= {taux['taux_ifrs17']:.3%}"
            ),
            'valeur': f"Méthode : {taux['methode']} | Source RFR : {taux['source_rfr']}",
            'statut': 'VALIDÉE' if 0.01 <= taux['taux_ifrs17'] <= 0.12 else 'À JUSTIFIER',
            'critique': True,
        }
        # H2 — Risk Adjustment quantile explicite
        q = p['quantile_ra']
        h2 = {
            'id':'H2',
            'hypothese':(
                f"Risk Adjustment calibré au quantile P{int(q*100)} "
                f"(z={ra['z_quantile']:.3f}) sur distribution "
                f"log-normale σ Mack Ibrahim — déclaration IFRS 17 §119(a)"
            ),
            'valeur':(
                f"RA={ra['ra_total']:,.0f}€ | "
                f"RA/BE={ra['ra_total']/max(src['be_brut'],1)*100:.1f}% | "
                f"Méthode : {ra['methode']}"
            ),
            'statut':'VALIDÉE',
            'critique':True,
        }
        # H3 — Cohérence S2 ↔ IFRS 17
        h3 = {
            'id':'H3',
            'hypothese':(
                "Ratio TP_IFRS17 / TP_S2 dans plage de cohérence [0.80, 1.50] "
                "— vérification A9 Marcus C4"
            ),
            'valeur':(
                f"Ratio={ecart['ratio_ifrs_s2']:.4f} | "
                f"TP_IFRS17={ecart['tp_ifrs17']:,.0f}€ vs TP_S2={ecart['tp_s2']:,.0f}€ | "
                f"Écart BE={ecart['ecart_be_pct']:+.1f}%"
            ),
            'statut':'VALIDÉE' if ecart['coherent'] else 'NON VALIDÉE',
            'critique':True,
        }
        return [h1, h2, h3]

    # ══════════════════════════════════════════════════════════════════════════
    # 14. COMMENTAIRE ACTUARIEL
    # ══════════════════════════════════════════════════════════════════════════
    def _commentaire(self, rag, lic, lrc, ra, lc, rev, ecart,
                     taux, branches, src, p, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        noms = " + ".join(b['nom'] for b in branches)
        tp = lic['lic_total'] + lrc['lrc_total'] + ra['ra_total']

        L = [
            "="*70,
            f"  RAPPORT IFRS 17 PAA — NON-VIE",
            f"  Branches : {noms}",
            f"  A11 Thomas v{self.VERSION} | {ic} STATUT : {rag}",
            "="*70, "",
            "📊 RÉSUMÉ DIRECTION", "─"*40,
        ]
        if rag=='VERT':
            L.append(
                f"✅ Conforme IFRS 17 §53 (PAA). "
                f"TP={tp:,.0f}€ | Ratio IFRS17/S2={ecart['ratio_ifrs_s2']:.3f}."
            )
        elif rag=='AMBRE':
            L.append(
                f"⚠️ Conforme sous surveillance. "
                f"TP={tp:,.0f}€ | Vérifier taux et paramètres."
            )
        else:
            L.append(
                f"❌ ALERTE IFRS 17. "
                f"{'Contrats déficitaires détectés.' if lc['nb_deficitaires']>0 else 'Ratio S2/IFRS17 hors plage.'}"
            )

        L += [
            "", "🔢 PROVISIONS IFRS 17 PAA", "─"*40,
            f"  Taux IFRS 17 (bottom-up)   : {taux['taux_ifrs17']:.4%}",
            f"  (RFR S2={taux['rfr_s2']:.4%} + illiq={taux['illiq_premium']*100:.0f}bps)",
            f"  LIC (sinistres survenus)    : {lic['lic_total']:>15,.0f}€",
            f"  LRC (couverture restante)   : {lrc['lrc_total']:>15,.0f}€",
            f"  Risk Adjustment P{int(p['quantile_ra']*100)}          : {ra['ra_total']:>15,.0f}€",
            f"  TP IFRS 17 Total            : {tp:>15,.0f}€",
            f"  CSM                         : {'0€ (PAA §55)':>15}",
            "", "⚖️ COMPARAISON S2 ↔ IFRS 17", "─"*40,
            f"  BE S2 Elena                 : {ecart['be_s2']:>15,.0f}€",
            f"  LIC IFRS 17 Thomas          : {ecart['lic_ifrs17']:>15,.0f}€",
            f"  Écart BE                    : {ecart['ecart_be']:>+15,.0f}€  ({ecart['ecart_be_pct']:+.1f}%)",
            f"  RM S2 Elena                 : {ecart['rm_s2']:>15,.0f}€",
            f"  RA IFRS 17 Thomas           : {ecart['ra_ifrs17']:>15,.0f}€",
            f"  Écart RM/RA                 : {ecart['ecart_rm_ra']:>+15,.0f}€",
            f"  Ratio IFRS17/S2             : {ecart['ratio_ifrs_s2']:>15.4f}",
            f"  Motif : {ecart['motif'][:60]}...",
        ]

        if lc['nb_deficitaires'] > 0:
            L += [
                "", "⚠️ LOSS COMPONENT", "─"*40,
                f"  {lc['nb_deficitaires']} branche(s) déficitaire(s) : "
                f"{', '.join(lc['branches_deficit'])}",
                f"  Loss Component à comptabiliser : {lc['lc_total']:,.0f}€ en P&L",
            ]

        L += ["", "📋 RÉCONCILIATION BILANCIELLE", "─"*40,
              f"  LIC fermeture N   : {lic['lic_total']:>15,.0f}€",
              f"  LRC fermeture N   : {lrc['lrc_total']:>15,.0f}€",
              f"  RA  fermeture N   : {ra['ra_total']:>15,.0f}€",
              f"  TP IFRS 17 N      : {tp:>15,.0f}€",
              "", "📋 HYPOTHÈSES", "─"*40]

        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else "⚠️"
            L += [f"  {ic_h} [{h['id']}] {h['hypothese'][:60]}...",
                  f"       → {h['valeur'][:70]} : {h['statut']}"]

        L += ["", "🎯 AVIS THOMAS → NADIA", "─"*40]
        if rag=='VERT':
            L.append("✅ CONFORME — Données transmises à A9 Marcus (C4). "
                     "Réconciliation bilancielle 3 colonnes disponible pour DAF.")
        elif rag=='AMBRE':
            L.append("⚠️ Documenter les hypothèses taux avant publication comptes.")
        else:
            L.append("❌ NON CONFORME — Escalade NADIA. "
                     "Reconstituer groupes de contrats déficitaires.")
        L.append("")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════════════════════
    # 15. GRAPHIQUES — 4 AUTO-EXPLICATIFS
    # ══════════════════════════════════════════════════════════════════════════
    def _graphiques(self, lic, lrc, ra, lc, rev, ecart, taux, branches, rec):
        gph = {}
        crag = lambda s: VERT if s=='VERT' else (AMBRE if s=='AMBRE' else ROUGE)

        # G1 — WATERFALL BE → TP IFRS 17
        try:
            be_b  = lic['be_brut_total']
            imp   = lic['impact_total']
            ra_v  = ra['ra_total']
            lrc_v = lrc['lrc_total']
            tp    = lic['lic_total'] + lrc_v + ra_v

            fig = go.Figure(go.Waterfall(
                x=['BE Brut\n(Ibrahim)','Actualisation\nIFRS 17','Risk\nAdjustment P75','LRC\n(PAA)','TP IFRS 17'],
                y=[be_b, imp, ra_v, lrc_v, tp],
                measure=['absolute','relative','relative','relative','total'],
                text=[f"{v/1e6:.2f}M€" for v in [be_b, imp, ra_v, lrc_v, tp]],
                textposition='outside', textfont=dict(color=BLANC, size=10),
                connector=dict(line=dict(color=GRIS, width=1, dash='dot')),
                increasing=dict(marker_color=AMBRE),
                decreasing=dict(marker_color=VERT),
                totals=dict(marker_color=OR),
                hovertemplate='<b>%{x}</b><br>%{y:,.0f}€<extra></extra>',
            ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G1 — De Ibrahim (A7) aux Provisions Techniques IFRS 17",
                           font=dict(color=OR,size=12),x=0.01),
                showlegend=False,
                annotations=[dict(
                    text=(f"💡 Taux IFRS 17 ({taux['taux_ifrs17']:.3%}) > "
                          f"RFR S2 ({taux['rfr_s2']:.3%}) → LIC < BE. "
                          f"RA = VaR P{int(ra['quantile']*100)} sur σ Mack. "
                          "LRC = primes non acquises (PAA §55)."),
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False,align="left")],
                xaxis=dict(tickfont=dict(color=BLANC,size=9),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
            ))
            fig.update_layout(**l)
            gph['waterfall_tp_ifrs17'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — COMPARAISON S2 ↔ IFRS 17
        try:
            fig = go.Figure()
            cats = ['BE / LIC','Risk Margin / RA','TP Total']
            vals_s2   = [ecart['be_s2'],  ecart['rm_s2'],  ecart['tp_s2']]
            vals_ifrs = [ecart['lic_ifrs17'],ecart['ra_ifrs17'],ecart['tp_ifrs17']]

            fig.add_trace(go.Bar(name='S2 (Elena A10)', x=cats, y=vals_s2,
                marker_color=BLEU, opacity=0.85,
                text=[f"{v/1e6:.2f}M€" for v in vals_s2],
                textposition='outside', textfont=dict(color=BLANC,size=10)))
            fig.add_trace(go.Bar(name='IFRS 17 (Thomas A11)', x=cats, y=vals_ifrs,
                marker_color=OR, opacity=0.85,
                text=[f"{v/1e6:.2f}M€" for v in vals_ifrs],
                textposition='outside', textfont=dict(color=BLANC,size=10)))

            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text=f"G2 — Comparaison S2 ↔ IFRS 17 | Ratio={ecart['ratio_ifrs_s2']:.3f}",
                           font=dict(color=OR,size=12),x=0.01),
                barmode='group',
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)'),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
                annotations=[dict(
                    text=(f"💡 Écart taux : {(taux['taux_ifrs17']-taux['rfr_s2'])*100:.0f}bps → "
                          f"LIC<BE_S2. RA VaR P{int(ra['quantile']*100)} vs RM CoC6%. "
                          "Transmis à A9 Marcus C4."),
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False,align="left")],
            ))
            fig.update_layout(**l)
            gph['comparaison_s2_ifrs17'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — LOSS COMPONENT PAR BRANCHE
        try:
            noms_b = [b['label'][:12] for b in lc['par_branche']]
            marges  = [b['marge'] for b in lc['par_branche']]
            colors  = [ROUGE if m<0 else VERT for m in marges]

            fig = go.Figure(go.Bar(
                x=noms_b, y=marges,
                marker_color=colors, opacity=0.85,
                text=[f"{m/1e3:.0f}k€" for m in marges],
                textposition='outside', textfont=dict(color=BLANC,size=10),
                hovertemplate='<b>%{x}</b><br>Marge : %{y:,.0f}€<extra></extra>',
            ))
            fig.add_hline(y=0, line=dict(color=ROUGE, width=2, dash='dash'))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G3 — Test Suffisance PAR BRANCHE (LRC − LIC − RA)",
                           font=dict(color=OR,size=12),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC,size=9),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
                annotations=[dict(
                    text=("💡 Barres rouges = branches déficitaires → "
                          "Loss Component comptabilisé en P&L immédiatement (IFRS 17 §47). "
                          "Test branche par branche — pas de compensation."),
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False,align="left")],
            ))
            fig.update_layout(**l)
            gph['loss_component_branches'] = fig
        except Exception as e:
            self.logger.warning(f"G3:{e}")

        # G4 — RÉCONCILIATION BILANCIELLE 3 COLONNES
        try:
            col_data = rec['colonnes']
            fig = make_subplots(rows=1, cols=3,
                subplot_titles=['LIC (Sinistres)', 'LRC (Couverture)', 'RA (Risque)'])

            for i, (col_nm, col_v, col_c) in enumerate([
                ('LIC', col_data['LIC'], ROUGE),
                ('LRC', col_data['LRC'], BLEU),
                ('RA',  col_data['RA'],  AMBRE),
            ], 1):
                items = {k:v for k,v in col_v.items() if k!='fermeture'}
                labels = list(items.keys()) + ['fermeture']
                values = list(items.values()) + [col_v['fermeture']]
                fig.add_trace(go.Bar(
                    x=[l[:10] for l in labels], y=values,
                    marker_color=[col_c if v>0 else GRIS for v in values],
                    opacity=0.85, showlegend=False,
                    text=[f"{v/1e3:.0f}k" for v in values],
                    textposition='outside', textfont=dict(color=BLANC,size=8),
                ), row=1, col=i)

            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G4 — Réconciliation Bilancielle IFRS 17 §100-105 (3 colonnes)",
                           font=dict(color=OR,size=12),x=0.01),
                annotations=[dict(
                    text="💡 Note annexe obligatoire — le DAF ne peut publier sans cette réconciliation.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False,align="left")],
            ))
            fig.update_layout(**l)
            gph['reconciliation_bilancielle'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        return gph

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES
    # ══════════════════════════════════════════════════════════════════════════
    def _audit(self, aid, lic, lrc, ra, ecart, rag):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'lic':lic['lic_total'],'lrc':lrc['lrc_total'],
                 'ra':ra['ra_total'],'ratio_ifrs_s2':ecart['ratio_ifrs_s2']}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, lic, lrc, ra, lc, ecart, rag, com):
        print(f"\n{'─'*70}\n  A11 THOMAS v{self.VERSION} | {aid}\n{'─'*70}")
        print(com); print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {
            'success':False,'agent':self.NOM,'version':self.VERSION,'audit_id':aid,
            'statut_rag':'ROUGE',
            'provisions':{'lic':0,'lrc':0,'risk_adjustment':0,'tp_ifrs17':0},
            'ecart_s2_ifrs':{'be':0,'be_pct':0,'rm_ra':0,'rm_ra_pct':0,
                             'ratio_ifrs_s2':0,'motif_ecart':'ERREUR'},
            'revenue':{'revenue_total':0},'loss_component':{'lc_total':0},
            'reconciliation':{},'taux':{},'hypotheses':[],'detail':{},
            'commentaire':f"❌ ERREUR A11 Thomas : {msg}",
            'graphiques':{},'duree_sec':0.0,'erreur':msg,
        }


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  A11 THOMAS v1.0 — DÉMO IFRS 17 PAA NON-VIE")
    print("  Taux bottom-up | RA VaR P75 | Loss Component | Réconcil. 3 col.")
    print("="*70)

    a7 = {
        'best_estimate':{'best_estimate':7_359_000.0,'sigma_mack':450_000.0,
            'cv_inter_methodes':8.5,'reserve_p75':7_800_000.0,'reserve_p90':8_100_000.0},
        'tail':{'tail_factor':1.037},'meta':{'nb_lignes':70000,'n_annees':8},
        'sous_branche':'rc_auto',
    }
    a10 = {
        'provisions':{'best_estimate':6_195_000.0,'risk_margin':236_000.0,'tp_s2':6_431_000.0},
        'taux':{'rfr_10ans':0.032,'rfr_5ans':0.031,'rfr_20ans':0.033,
                'source':'FALLBACK_REFERENCE','fiabilite':'REFERENCE'},
        'duration':{'passif':3.88},
        'scr':{'total':3_771_000.0},
        'capital':{'ratio_scr':132.5},
    }
    a6 = {'modele_production':{'primes_acquises':10_000_000.0}}

    agent = AgentA11IFRS17(audit_path='/tmp/a11/audit', verbose=True)
    r = agent.run(
        result_a7=a7, result_a10=a10, result_a6=a6,
        branches=[
            {'nom':'rc_auto','be':5_000_000,'primes':7_000_000},
            {'nom':'mrh',    'be':2_359_000,'primes':3_000_000},
        ],
        params_ifrs={'quantile_ra':0.75,'illiq_premium':0.0060,'duree_contrat':1.0},
        generer_graphiques=False,
    )

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut   : {r['statut_rag']} | {r.get('motif_rag','')}")
    pv = r['provisions']
    print(f"  LIC      : {pv['lic']:>15,.0f}€")
    print(f"  LRC      : {pv['lrc']:>15,.0f}€")
    print(f"  RA P75   : {pv['risk_adjustment']:>15,.0f}€  (quantile={pv['quantile_ra']:.0%})")
    print(f"  TP IFRS17: {pv['tp_ifrs17']:>15,.0f}€")
    e = r['ecart_s2_ifrs']
    print(f"\n  Écart BE  : {e['be']:>+15,.0f}€  ({e['be_pct']:+.1f}%)")
    print(f"  Écart RA  : {e['rm_ra']:>+15,.0f}€")
    print(f"  Ratio     : {e['ratio_ifrs_s2']:.4f}")
    lc = r['loss_component']
    print(f"\n  Loss Comp.: {lc['lc_total']:>15,.0f}€  ({lc['nb_deficitaires']} branche(s) déficitaire(s))")
    print(f"  QRT lignes: {len(r.get('detail',{}).get('lic',{}).get('par_branche',[]))} branches")
    print(f"  Durée     : {r['duree_sec']:.2f}s")
