"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ACTUARIA — AGENT A12 AISHA : ALM & LIQUIDITÉ NON-VIE v1.0        ║
║                     Sous NADIA (Direction Non-Vie)                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  DIFFÉRENCIATEURS vs marché :                                               ║
║    ✅ Immunisation Redington 3 conditions explicites                        ║
║    ✅ BV01 par branche (sensibilité 1bp en valeur absolue)                 ║
║    ✅ Stress taux ±200bp décomposé actif/passif/NAV                        ║
║    ✅ Duration Macaulay + duration modifiée actif ET passif                 ║
║    ✅ Gap duration documenté avec recommandation de gestion                 ║
║    ✅ LCR (actifs liquides / sorties 30j)                                  ║
║    ✅ Sorties vers A9 Marcus C4/C5                                         ║
║                                                                              ║
║  ENTRÉES OBLIGATOIRES :                                                     ║
║    result_a10 → Elena S2 (duration passif, BE, taux, allocation actif)    ║
║                                                                              ║
║  ENTRÉES OPTIONNELLES :                                                     ║
║    result_a7    → BE Ibrahim (sigma Mack pour stress)                      ║
║    result_a11   → Thomas IFRS 17 (LIC pour cohérence)                     ║
║    market_data  → Taux BCE                                                  ║
║    portefeuille_actif → Détail par classe d'actif                          ║
║    params_alm   → Paramètres client                                         ║
║                                                                              ║
║  SORTIES VERS A9 MARCUS :                                                   ║
║    duration.passif  → C5                                                    ║
║    duration.actif   → C5                                                    ║
║    gap_duration     → C5                                                    ║
║    lcr              → C5                                                    ║
║    redington.ok     → C5                                                    ║
║                                                                              ║
║  VERSION : 1.0 — 19/06/2026                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"; OR="#C9A84C"
BLANC="#F0F4F8"; GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"
AMBRE="#F39C12"; BLEU="#3498DB"; VIOLET="#9B59B6"; TURQUOISE="#1ABC9C"

LAYOUT_BASE = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=60,r=40,t=70,b=90), height=420,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))

# ── Paramètres ALM ────────────────────────────────────────────────────────────
# Duration actif par classe (années)
DURATION_ACTIF_CLASSE = {
    'obligations':   5.0,
    'actions':       0.0,   # sensibilité taux ≈ 0
    'immo':          0.0,
    'cash':          0.0,
    'oblig_court':   2.0,
    'oblig_long':    8.0,
}

# Seuils de gap duration (années)
GAP_VERT  = 1.0    # gap ≤ 1 an : bien immunisé
GAP_AMBRE = 2.5    # gap 1-2.5 ans : acceptable
# gap > 2.5 ans : ROUGE

# Seuils LCR
LCR_VERT  = 100.0  # LCR ≥ 100% : conforme Basel III
LCR_AMBRE = 75.0   # LCR 75-100% : vigilance

# Chocs de taux
CHOCS_TAUX = [-0.02, -0.01, +0.01, +0.02]  # -200bp, -100bp, +100bp, +200bp
CHOC_LABELS = ['-200bp', '-100bp', '+100bp', '+200bp']

# ══════════════════════════════════════════════════════════════════════════════
class AgentA12ALM:
    """
    Agent A12 Aisha — ALM & Liquidité Non-Vie v1.0.
    Duration Macaulay/modifiée | Gap | BV01 par branche
    Immunisation Redington 3 conditions | Stress ±200bp décomposé
    LCR | Sorties vers A9 Marcus C5
    """
    NOM="Aisha"; CODE="A12"; VERSION="1.0"; RESPONSABLE="NADIA (Réglementation)"

    def __init__(self, audit_path='/tmp/actuaria',
                 verbose=True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger('actuaria.a12.aisha')
        self.verbose = verbose
        if verbose:
            self.logger.info(f"A12 Aisha v{self.VERSION} | {self.RESPONSABLE}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_a10,
            result_a7        = None,
            result_a11       = None,
            market_data      = None,
            portefeuille_actif = None,
            params_alm       = None,
            generer_graphiques = True) -> Dict:

        t0  = datetime.now()
        aid = f"A12_{t0.strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"[{aid}] A12 Aisha v{self.VERSION}")

        try:
            # ── 1. PARAMÈTRES ────────────────────────────────────────────────
            p = self._params(params_alm)

            # ── 2. TAUX ──────────────────────────────────────────────────────
            taux = self._taux(result_a10, market_data)

            # ── 3. PASSIF ────────────────────────────────────────────────────
            passif = self._analyser_passif(result_a10, result_a7, result_a11, taux)

            # ── 4. ACTIF ─────────────────────────────────────────────────────
            actif = self._analyser_actif(result_a10, portefeuille_actif, taux, passif)

            # ── 5. GAP DURATION ──────────────────────────────────────────────
            gap = self._calculer_gap(actif, passif, taux)

            # ── 6. BV01 PAR BRANCHE ──────────────────────────────────────────
            bv01 = self._calculer_bv01(actif, passif, taux)

            # ── 7. IMMUNISATION REDINGTON (3 CONDITIONS) ─────────────────────
            redington = self._verifier_redington(actif, passif, bv01)

            # ── 8. STRESS TAUX ±200bp DÉCOMPOSÉ ─────────────────────────────
            stress = self._stress_taux(actif, passif, taux)

            # ── 9. LCR ───────────────────────────────────────────────────────
            lcr = self._calculer_lcr(actif, passif, p)

            # ── 10. STATUT RAG ────────────────────────────────────────────────
            rag, motif = self._rag(gap, redington, lcr, stress)

            # ── 11. HYPOTHÈSES ────────────────────────────────────────────────
            hyp = self._hypotheses(gap, redington, lcr, stress, taux)

            # ── 12. COMMENTAIRE ───────────────────────────────────────────────
            com = self._commentaire(rag, actif, passif, gap, bv01,
                                    redington, stress, lcr, taux, p, hyp)

            # ── 13. GRAPHIQUES ────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(actif, passif, gap, bv01,
                                       redington, stress, lcr, taux)

            # ── 14. AUDIT ────────────────────────────────────────────────────
            self._audit(aid, gap, redington, lcr, stress, rag)

            if self.verbose:
                self._console(aid, actif, passif, gap, redington, lcr, stress, rag, com)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':True, 'agent':self.NOM, 'version':self.VERSION,
                'audit_id':aid, 'statut_rag':rag, 'motif_rag':motif,

                # ── Duration (→ A9 C5) ───────────────────────────────────────
                'duration': {
                    'actif':              actif['dur_macaulay'],
                    'actif_modifiee':     actif['dur_modifiee'],
                    'passif':             passif['dur_macaulay'],
                    'passif_modifiee':    passif['dur_modifiee'],
                    'gap':                gap['gap_macaulay'],
                    'gap_modifiee':       gap['gap_modifiee'],
                    'statut_gap':         gap['statut'],
                    'par_branche_passif': passif['par_branche'],
                },

                # ── BV01 (→ A9 C5) ───────────────────────────────────────────
                'bv01': {
                    'bv01_actif':   bv01['bv01_actif'],
                    'bv01_passif':  bv01['bv01_passif'],
                    'bv01_net':     bv01['bv01_net'],
                    'impact_100bp': bv01['impact_100bp'],
                    'sens_net':     bv01['sens_net'],
                    'par_branche':  bv01['par_branche'],
                },

                # ── Redington (→ A9 C5) ──────────────────────────────────────
                'redington': {
                    'ok':             redington['ok'],
                    'c1_duration':    redington['c1'],
                    'c2_convexite':   redington['c2'],
                    'c3_va_positive': redington['c3'],
                    'detail':         redington,
                },

                # ── Stress taux ───────────────────────────────────────────────
                'stress': {
                    'chocs':      stress['chocs'],
                    'pire_cas':   stress['pire_cas'],
                    'pire_nav':   stress['pire_nav'],
                    'detail':     stress['detail'],
                },

                # ── LCR (→ A9 C5) ────────────────────────────────────────────
                'lcr': {
                    'lcr':             lcr['lcr'],
                    'actifs_liquides': lcr['actifs_liquides'],
                    'sorties_30j':     lcr['sorties_30j'],
                    'statut':          lcr['statut'],
                },

                # ── Actif/Passif ─────────────────────────────────────────────
                'actif':  actif,
                'passif': passif,
                'taux':   taux,

                # ── Standard ActuarIA ─────────────────────────────────────────
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
    # 1. PARAMÈTRES
    # ══════════════════════════════════════════════════════════════════════════
    def _params(self, p):
        if not p: p = {}
        return {
            'horizon_lcr':      p.get('horizon_lcr',     30),
            'taux_sortie_30j':  p.get('taux_sortie_30j', 0.10),
            'haircut_oblig':    p.get('haircut_oblig',   0.0),
            'haircut_actions':  p.get('haircut_actions', 0.50),
            'haircut_immo':     p.get('haircut_immo',    0.50),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 2. TAUX
    # ══════════════════════════════════════════════════════════════════════════
    def _taux(self, result_a10, market_data):
        t = result_a10.get('taux', {})
        rfr  = float(t.get('rfr_10ans', 0.032))
        r5   = float(t.get('rfr_5ans',  0.031))
        r20  = float(t.get('rfr_20ans', 0.033))
        src  = t.get('source', 'FALLBACK')
        fib  = t.get('fiabilite', 'REFERENCE')
        return {
            'rfr':      rfr,
            'rfr_5ans': r5,
            'rfr_20ans':r20,
            'source':   src,
            'fiabilite':fib,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 3. PASSIF — DURATION PAR BRANCHE
    # ══════════════════════════════════════════════════════════════════════════
    def _analyser_passif(self, result_a10, result_a7, result_a11, taux):
        """
        Duration passif depuis Elena A10 (par branche si disponible).
        Complétée par LIC IFRS 17 si Thomas disponible.
        """
        rfr = taux['rfr']

        # Duration passif globale depuis A10
        dur_p = float(result_a10.get('duration', {}).get('passif', 4.0))
        be_p  = float(result_a10.get('provisions', {}).get('best_estimate', 0.0))
        rm_p  = float(result_a10.get('provisions', {}).get('risk_margin', 0.0))
        tp_s2 = be_p + rm_p

        # Par branche depuis A10 si disponible
        branches_a10 = result_a10.get('duration', {}).get('par_branche', [])

        if branches_a10:
            par_b = []
            for b in branches_a10:
                dur_b   = float(b.get('duration_macaulay', dur_p))
                dur_mod = dur_b / (1 + rfr)
                poids   = float(b.get('poids', 1.0/len(branches_a10)))
                par_b.append({
                    'nom':              b.get('nom', 'n/a'),
                    'be':               be_p * poids,
                    'duration_macaulay':dur_b,
                    'duration_modifiee':round(dur_mod, 4),
                    'poids':            poids,
                    'bv01_branche':     be_p * poids * dur_mod * 0.0001,
                })
        else:
            # Mono-branche
            dur_mod = dur_p / (1 + rfr)
            lob = result_a10.get('detail', {}).get('branches', [{}])
            nom = lob[0].get('nom', 'rc_auto') if lob else 'rc_auto'
            par_b = [{
                'nom':              nom,
                'be':               be_p,
                'duration_macaulay':dur_p,
                'duration_modifiee':round(dur_mod, 4),
                'poids':            1.0,
                'bv01_branche':     be_p * dur_mod * 0.0001,
            }]

        # Duration Macaulay globale pondérée
        dur_mac_glob = sum(
            b['duration_macaulay'] * b['poids'] for b in par_b
        )
        dur_mod_glob = dur_mac_glob / (1 + rfr)

        # LIC IFRS 17 si disponible
        lic_ifrs = 0.0
        if result_a11:
            lic_ifrs = float(result_a11.get('provisions', {}).get('lic', 0.0))

        return {
            'be':            be_p,
            'tp_s2':         tp_s2,
            'lic_ifrs17':    lic_ifrs,
            'dur_macaulay':  round(dur_mac_glob, 4),
            'dur_modifiee':  round(dur_mod_glob, 4),
            'par_branche':   par_b,
            'bv01_passif':   be_p * dur_mod_glob * 0.0001,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 4. ACTIF — DURATION PAR CLASSE
    # ══════════════════════════════════════════════════════════════════════════
    def _analyser_actif(self, result_a10, portefeuille, taux, passif):
        """
        Duration actif depuis allocation Elena A10 ou portefeuille fourni.
        Duration Macaulay + duration modifiée par classe.
        """
        rfr    = taux['rfr']
        be_p   = passif['be']
        actif_total = be_p * 1.35   # hypothèse standard Non-Vie

        # Allocation depuis Elena ou portefeuille fourni
        if portefeuille:
            alloc = portefeuille
        else:
            alloc_a10 = (result_a10.get('detail', {})
                         .get('scr_mkt', {}).get('allocation', {}))
            ob = alloc_a10.get('obligations', 0.70)
            ac = alloc_a10.get('actions',     0.10)
            im = alloc_a10.get('immo',        0.05)
            ca = max(0.0, 1.0 - ob - ac - im)
            total_alloc = ob + ac + im + ca
            if total_alloc > 1.001:
                self.logger.warning(
                    f'ALM : allocation actif somme a {total_alloc:.1%} > 100%'
                    ' — normalisation appliquee.'
                )
                ob /= total_alloc; ac /= total_alloc
                im /= total_alloc; ca /= total_alloc
            alloc = {
                'obligations': ob,
                'actions':     ac,
                'immo':        im,
                'cash':        ca,
            }

        par_classe = []
        dur_mac_pond = 0.0

        for classe, pct in alloc.items():
            if pct <= 0:
                continue
            val       = actif_total * pct
            dur_mac_c = DURATION_ACTIF_CLASSE.get(classe, 0.0)
            dur_mod_c = dur_mac_c / (1 + rfr) if dur_mac_c > 0 else 0.0
            bv01_c    = val * dur_mod_c * 0.0001
            dur_mac_pond += dur_mac_c * pct
            par_classe.append({
                'classe':           classe,
                'pct':              pct,
                'valeur':           val,
                'duration_macaulay':dur_mac_c,
                'duration_modifiee':round(dur_mod_c, 4),
                'bv01':             bv01_c,
            })

        dur_mod_glob = dur_mac_pond / (1 + rfr)

        return {
            'total':        actif_total,
            'allocation':   alloc,
            'dur_macaulay': round(dur_mac_pond, 4),
            'dur_modifiee': round(dur_mod_glob, 4),
            'par_classe':   par_classe,
            'bv01_actif':   actif_total * dur_mod_glob * 0.0001,
            'nav':          actif_total - passif['tp_s2'],
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 5. GAP DURATION
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_gap(self, actif, passif, taux):
        """
        Gap duration = Duration passif − Duration actif.

        Interprétation :
        Gap > 0 : passif plus long que l'actif → risque de hausse des taux
        Gap < 0 : actif plus long que le passif → risque de baisse des taux
        Gap ≈ 0 : portefeuille immunisé

        Non-Vie : gap typique 0-3 ans (passifs courts, actifs obligataires)
        """
        gap_mac = passif['dur_macaulay'] - actif['dur_macaulay']
        gap_mod = passif['dur_modifiee'] - actif['dur_modifiee']

        abs_gap = abs(gap_mac)
        if abs_gap <= GAP_VERT:
            statut = 'VERT'
            recommandation = "Gap faible — portefeuille bien immunisé."
        elif abs_gap <= GAP_AMBRE:
            statut = 'AMBRE'
            recommandation = (
                f"Gap {gap_mac:+.2f} ans — allonger la duration actif "
                "ou raccourcir le passif via réassurance."
            )
        else:
            statut = 'ROUGE'
            recommandation = (
                f"Gap {gap_mac:+.2f} ans — ACTION REQUISE : "
                "acheter des obligations plus longues "
                "ou utiliser des swaps de taux."
            )

        return {
            'gap_macaulay': round(gap_mac, 4),
            'gap_modifiee': round(gap_mod, 4),
            'abs_gap':      round(abs_gap, 4),
            'statut':       statut,
            'recommandation':recommandation,
            'sens':         'passif plus long' if gap_mac > 0 else 'actif plus long',
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 6. BV01 PAR BRANCHE
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_bv01(self, actif, passif, taux):
        """
        BV01 = sensibilité à +1bp (0.01%) des taux d'intérêt.

        BV01_actif  = Valeur actif × Duration modifiée × 0.0001
        BV01_passif = BE × Duration modifiée passif × 0.0001
        BV01_net    = BV01_actif − BV01_passif

        BV01_net > 0 : actif plus sensible → hausse des taux bénéfique (NAV ↑)
        BV01_net < 0 : passif plus sensible → hausse des taux défavorable (NAV ↓)

        Par branche : permet de piloter le risque de taux branche par branche
        (utile pour le desk ALM).
        """
        bv01_a = actif['bv01_actif']
        bv01_p = passif['bv01_passif']
        bv01_n = bv01_a - bv01_p

        # Par branche passif
        par_b = []
        for b in passif['par_branche']:
            par_b.append({
                'nom':              b['nom'],
                'bv01_passif':      b['bv01_branche'],
                'pct_bv01_total':   round(b['bv01_branche'] / max(bv01_p, 1e-10) * 100, 1),
                'duration_modifiee':b['duration_modifiee'],
            })

        return {
            'bv01_actif':  round(bv01_a, 2),
            'bv01_passif': round(bv01_p, 2),
            'bv01_net':    round(bv01_n, 2),
            'sens_net':    'actif > passif' if bv01_n > 0 else 'passif > actif',
            'impact_100bp':round(bv01_n * 100, 0),   # impact d'un choc 100bp
            'par_branche': par_b,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 7. IMMUNISATION REDINGTON — 3 CONDITIONS EXPLICITES
    # ══════════════════════════════════════════════════════════════════════════
    def _verifier_redington(self, actif, passif, bv01):
        """
        Théorème de Redington (1952) — 3 conditions d'immunisation :

        C1 — ÉGALITÉ DES VALEURS ACTUELLES
             VA(actif) = VA(passif)
             → NAV ≥ 0 (actif ≥ passif)

        C2 — ÉGALITÉ DES DURATIONS
             Duration(actif) = Duration(passif)
             → BV01_net ≈ 0 (sensibilité taux équilibrée)

        C3 — CONVEXITÉ ACTIF > CONVEXITÉ PASSIF
             Convexité(actif) > Convexité(passif)
             → Le portefeuille gagne sur les grands mouvements de taux

        Un portefeuille Redington est immunisé contre les petits chocs de taux.
        """
        nav = actif['nav']
        dur_a = actif['dur_modifiee']
        dur_p = passif['dur_modifiee']
        bv01_n = bv01['bv01_net']

        # C1 — VA(actif) ≥ VA(passif)
        c1_ok = nav >= 0
        c1_val = round(nav, 0)
        c1_msg = f"NAV={nav:,.0f}€ {'≥ 0 ✅' if c1_ok else '< 0 ❌'}"

        # C2 — Duration actif ≈ Duration passif (tolérance 10%)
        tol = max(dur_p * 0.10, 0.25)   # tolérance 10% ou 3 mois
        c2_ok  = abs(dur_a - dur_p) <= tol
        c2_ecart = dur_a - dur_p
        c2_val = round(c2_ecart, 4)
        c2_msg = (f"D_actif={dur_a:.3f}a vs D_passif={dur_p:.3f}a "
                  f"écart={c2_ecart:+.3f}a "
                  f"(tol±{tol:.2f}a) {'✅' if c2_ok else '❌'}")

        # C3 — Convexité actif > Convexité passif
        # Approximation : convexité ≈ duration² + duration (pour flux annuels)
        conv_a = dur_a**2 + dur_a
        conv_p = dur_p**2 + dur_p
        c3_ok  = conv_a > conv_p
        c3_val = round(conv_a - conv_p, 4)
        c3_msg = (f"Conv_actif={conv_a:.3f} vs Conv_passif={conv_p:.3f} "
                  f"écart={c3_val:+.3f} {'✅' if c3_ok else '❌'}")

        redington_ok = c1_ok and c2_ok and c3_ok
        nb_ok = sum([c1_ok, c2_ok, c3_ok])

        return {
            'ok':     redington_ok,
            'nb_ok':  nb_ok,
            'c1':     {'ok':c1_ok, 'valeur':c1_val, 'message':c1_msg,
                       'libelle':'VA(actif) ≥ VA(passif)'},
            'c2':     {'ok':c2_ok, 'valeur':c2_val, 'message':c2_msg,
                       'libelle':'Duration actif ≈ Duration passif'},
            'c3':     {'ok':c3_ok, 'valeur':c3_val, 'message':c3_msg,
                       'libelle':'Convexité actif > Convexité passif'},
            'statut': 'VERT' if redington_ok else ('AMBRE' if nb_ok >= 2 else 'ROUGE'),
            'note': (
                "Portefeuille immunisé Redington (3/3 conditions)"
                if redington_ok else
                f"Immunisation partielle ({nb_ok}/3 conditions) — "
                "ajustement allocation actif recommandé"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 8. STRESS TAUX ±200bp DÉCOMPOSÉ
    # ══════════════════════════════════════════════════════════════════════════
    def _stress_taux(self, actif, passif, taux):
        """
        Stress taux décomposé actif / passif / NAV pour ±100bp et ±200bp.

        Impact actif  = −Duration_mod_actif  × Choc × Valeur_actif
        Impact passif = −Duration_mod_passif × Choc × BE_passif
        Impact NAV    = Impact_actif − Impact_passif

        La décomposition est ce que lit le Risk Manager :
        il veut savoir si la perte vient de l'actif ou du passif.
        """
        dur_a = actif['dur_modifiee']
        dur_p = passif['dur_modifiee']
        val_a = actif['total']
        val_p = passif['be']
        nav_0 = actif['nav']

        detail = []
        pire_nav  = 0.0
        pire_choc = CHOCS_TAUX[0]  # valeur de secours

        for choc, label in zip(CHOCS_TAUX, CHOC_LABELS):
            # dur_a est la duration GLOBALE du portefeuille actif (toutes classes)
            # Les classes non sensibles aux taux (actions, cash) ont deja
            # tire dur_a vers le bas — on applique donc sur val_a entier.
            imp_a = -dur_a * choc * val_a

            # Impact passif (BE actualisé)
            imp_p = -dur_p * choc * val_p

            # Impact NAV net
            imp_nav = imp_a - imp_p
            nav_stress = nav_0 + imp_nav
            pct_nav    = imp_nav / max(abs(nav_0), 1) * 100

            # Pire cas = perte maximale (impact negatif le plus fort sur NAV)
            if imp_nav < pire_nav:
                pire_nav  = imp_nav
                pire_choc = choc

            detail.append({
                'choc':      choc,
                'label':     label,
                'imp_actif': round(imp_a, 0),
                'imp_passif':round(imp_p, 0),
                'imp_nav':   round(imp_nav, 0),
                'nav_stress':round(nav_stress, 0),
                'pct_nav':   round(pct_nav, 2),
                'favorable': imp_nav > 0,
            })

        # Fallback : si aucun choc negatif, prendre la variation absolue max
        if pire_nav == 0.0 and detail:
            idx_max = max(range(len(detail)), key=lambda i: abs(detail[i]['imp_nav']))
            pire_nav  = detail[idx_max]['imp_nav']
            pire_choc = detail[idx_max]['choc']
        pire_label = (
            CHOC_LABELS[CHOCS_TAUX.index(pire_choc)]
            if pire_choc in CHOCS_TAUX else 'N/A'
        )
        return {
            'nav_base':  round(nav_0, 0),
            'detail':    detail,
            'pire_cas':  pire_label,
            'pire_nav':  round(pire_nav, 0),
            'chocs':     CHOC_LABELS,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 9. LCR
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_lcr(self, actif, passif, p):
        """
        LCR = Actifs liquides de haute qualité (HQLA) / Sorties nettes 30j.

        Non-Vie : sorties 30j = sinistres payés + frais + réassurance.
        Hypothèse standard : 10% des provisions techniques sur 30j.

        Seuils réglementaires (Basel III adapté assurance) :
        LCR ≥ 100% : conforme
        LCR 75-100%: vigilance
        LCR < 75%  : action requise
        """
        val_a = actif['total']
        alloc = actif['allocation']

        # HQLA Niveau 1 : obligations d'État, cash (haircut 0%)
        hqla_n1 = val_a * (alloc.get('cash', 0.15)
                           + alloc.get('obligations', 0.70) * 0.85)

        # HQLA Niveau 2 : obligations corporate (haircut 15%)
        hqla_n2 = val_a * alloc.get('obligations', 0.70) * 0.15 * 0.85

        # Actions/immo non éligibles HQLA (haircut 50%)
        hqla_n2b = val_a * (alloc.get('actions', 0.10)
                            + alloc.get('immo', 0.05)) * 0.50

        actifs_liquides = hqla_n1 + hqla_n2 + hqla_n2b

        # Sorties 30j = taux_sortie × TP S2
        sorties_30j = passif['tp_s2'] * p['taux_sortie_30j']

        lcr_val = actifs_liquides / max(sorties_30j, 1) * 100

        if lcr_val >= LCR_VERT:
            statut = 'VERT'
        elif lcr_val >= LCR_AMBRE:
            statut = 'AMBRE'
        else:
            statut = 'ROUGE'

        return {
            'lcr':             round(lcr_val, 1),
            'actifs_liquides': round(actifs_liquides, 0),
            'hqla_n1':         round(hqla_n1, 0),
            'hqla_n2':         round(hqla_n2, 0),
            'sorties_30j':     round(sorties_30j, 0),
            'taux_sortie':     p['taux_sortie_30j'],
            'statut':          statut,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 10. STATUT RAG
    # ══════════════════════════════════════════════════════════════════════════
    def _rag(self, gap, redington, lcr, stress):
        # LCR critique
        if lcr['statut'] == 'ROUGE':
            return 'ROUGE', f"LCR={lcr['lcr']:.1f}% < 75% — risque liquidité immédiat"
        # Gap trop élevé
        if gap['statut'] == 'ROUGE':
            return 'ROUGE', (
                f"Gap duration={gap['gap_macaulay']:+.2f}a > 2.5a — "
                f"{gap['recommandation']}"
            )
        # Perte stress > 20% NAV
        pire = abs(stress['pire_nav'])
        nav  = abs(stress['nav_base'])
        if nav > 0 and pire / nav > 0.20:
            return 'ROUGE', (
                f"Stress {stress['pire_cas']} : impact NAV={stress['pire_nav']:,.0f}€ "
                f"({pire/nav:.1%} du NAV) > 20% seuil"
            )
        # Redington partiel
        if not redington['ok']:
            return 'AMBRE', (
                f"Immunisation Redington partielle ({redington['nb_ok']}/3 conditions) — "
                f"{redington['note']}"
            )
        # LCR vigilance
        if lcr['statut'] == 'AMBRE':
            return 'AMBRE', f"LCR={lcr['lcr']:.1f}% entre 75% et 100% — surveiller"
        # Gap modéré
        if gap['statut'] == 'AMBRE':
            return 'AMBRE', (
                f"Gap duration={gap['gap_macaulay']:+.2f}a — "
                f"{gap['recommandation']}"
            )
        return 'VERT', (
            f"ALM conforme | Gap={gap['gap_macaulay']:+.2f}a | "
            f"LCR={lcr['lcr']:.1f}% | Redington {redington['nb_ok']}/3"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 11. HYPOTHÈSES
    # ══════════════════════════════════════════════════════════════════════════
    def _hypotheses(self, gap, redington, lcr, stress, taux):
        h1 = {
            'id':'H1',
            'hypothese':(
                f"Duration passif issue de Elena A10 ({gap['gap_macaulay']+0:.2f}a gap) — "
                f"Taux RFR={taux['rfr']:.3%} pour duration modifiée"
            ),
            'valeur':f"Gap Macaulay={gap['gap_macaulay']:+.4f}a | Statut gap={gap['statut']}",
            'statut':'VALIDÉE' if gap['statut'] in ['VERT','AMBRE'] else 'À JUSTIFIER',
            'critique':True,
        }
        h2 = {
            'id':'H2',
            'hypothese':(
                f"Immunisation Redington {redington['nb_ok']}/3 conditions : "
                f"C1(VA)={'✅' if redington['c1']['ok'] else '❌'} "
                f"C2(Dur)={'✅' if redington['c2']['ok'] else '❌'} "
                f"C3(Conv)={'✅' if redington['c3']['ok'] else '❌'}"
            ),
            'valeur':redington['note'],
            'statut':'VALIDÉE' if redington['ok'] else 'À JUSTIFIER',
            'critique':True,
        }
        h3 = {
            'id':'H3',
            'hypothese':(
                f"LCR={lcr['lcr']:.1f}% (HQLA={lcr['actifs_liquides']:,.0f}€ / "
                f"Sorties30j={lcr['sorties_30j']:,.0f}€) | "
                f"Stress pire cas={stress['pire_cas']} impact NAV={stress['pire_nav']:,.0f}€"
            ),
            'valeur':(
                f"LCR statut={lcr['statut']} | "
                f"Pire stress : {stress['pire_cas']} → NAV {stress['pire_nav']:+,.0f}€"
            ),
            'statut':'VALIDÉE' if lcr['statut']=='VERT' else 'À JUSTIFIER',
            'critique':True,
        }
        return [h1, h2, h3]

    # ══════════════════════════════════════════════════════════════════════════
    # 12. COMMENTAIRE ACTUARIEL
    # ══════════════════════════════════════════════════════════════════════════
    def _commentaire(self, rag, actif, passif, gap, bv01,
                     redington, stress, lcr, taux, p, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        L = [
            "="*70,
            f"  RAPPORT ALM & LIQUIDITÉ — NON-VIE",
            f"  A12 Aisha v{self.VERSION} | {ic} STATUT : {rag}",
            "="*70, "",
            "📊 RÉSUMÉ DIRECTION", "─"*40,
        ]
        if rag=='VERT':
            L.append(f"✅ ALM conforme. Gap={gap['gap_macaulay']:+.2f}a | LCR={lcr['lcr']:.1f}%.")
        elif rag=='AMBRE':
            L.append(f"⚠️ ALM sous surveillance. {gap['recommandation']}")
        else:
            L.append(f"❌ ALERTE ALM. Action requise immédiate.")

        L += [
            "", "📐 DURATION & GAP", "─"*40,
            f"  Duration actif (Macaulay)    : {actif['dur_macaulay']:>10.4f} ans",
            f"  Duration actif (modifiée)    : {actif['dur_modifiee']:>10.4f} ans",
            f"  Duration passif (Macaulay)   : {passif['dur_macaulay']:>10.4f} ans",
            f"  Duration passif (modifiée)   : {passif['dur_modifiee']:>10.4f} ans",
            f"  Gap Macaulay                 : {gap['gap_macaulay']:>+10.4f} ans  [{gap['statut']}]",
            f"  Gap modifiée                 : {gap['gap_modifiee']:>+10.4f} ans",
            f"  → {gap['recommandation']}",
            "", "📏 BV01 (sensibilité 1bp)", "─"*40,
            f"  BV01 Actif                   : {bv01['bv01_actif']:>10.2f}€/bp",
            f"  BV01 Passif                  : {bv01['bv01_passif']:>10.2f}€/bp",
            f"  BV01 Net                     : {bv01['bv01_net']:>+10.2f}€/bp  [{bv01['sens_net']}]",
            f"  Impact choc +100bp           : {bv01['impact_100bp']:>+10,.0f}€",
            "", "🔺 IMMUNISATION REDINGTON", "─"*40,
            f"  C1 — VA(actif) ≥ VA(passif) : {'✅' if redington['c1']['ok'] else '❌'}  {redington['c1']['message']}",
            f"  C2 — Duration équilibrée    : {'✅' if redington['c2']['ok'] else '❌'}  {redington['c2']['message']}",
            f"  C3 — Convexité actif > pass : {'✅' if redington['c3']['ok'] else '❌'}  {redington['c3']['message']}",
            f"  → {redington['note']}",
            "", "⚡ STRESS TAUX (décomposé actif/passif/NAV)", "─"*40,
            f"  NAV de base                  : {stress['nav_base']:>15,.0f}€",
        ]
        for d in stress['detail']:
            L.append(
                f"  {d['label']:>6} : actif={d['imp_actif']:>+10,.0f}€ "
                f"pass={d['imp_passif']:>+10,.0f}€ "
                f"NAV={d['imp_nav']:>+10,.0f}€  ({d['pct_nav']:>+6.1f}%)"
            )
        L += [
            f"  Pire cas : {stress['pire_cas']} → impact NAV = {stress['pire_nav']:+,.0f}€",
            "", "💧 LIQUIDITÉ (LCR)", "─"*40,
            f"  Actifs liquides HQLA         : {lcr['actifs_liquides']:>15,.0f}€",
            f"  Sorties nettes 30j           : {lcr['sorties_30j']:>15,.0f}€",
            f"  LCR                          : {lcr['lcr']:>14.1f}%  [{lcr['statut']}]",
            "", "📋 HYPOTHÈSES", "─"*40,
        ]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else "⚠️"
            L += [f"  {ic_h} [{h['id']}] {h['hypothese'][:65]}",
                  f"       → {h['valeur'][:70]} : {h['statut']}"]
        L += ["", "🎯 AVIS AISHA → NADIA", "─"*40]
        if rag=='VERT':
            L.append("✅ CONFORME — Données transmises à A9 Marcus (C5).")
        elif rag=='AMBRE':
            L.append(f"⚠️ Surveiller le gap. {gap['recommandation']}")
        else:
            L.append("❌ NON CONFORME — Escalade LEILA. Rebalancer le portefeuille actif.")
        L.append("")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════════════════════
    # 13. GRAPHIQUES — 4 AUTO-EXPLICATIFS
    # ══════════════════════════════════════════════════════════════════════════
    def _graphiques(self, actif, passif, gap, bv01, redington, stress, lcr, taux):
        gph = {}

        # G1 — DURATION ACTIF vs PASSIF (barres + gap)
        try:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Actif', x=['Duration Macaulay','Duration Modifiée'],
                y=[actif['dur_macaulay'], actif['dur_modifiee']],
                marker_color=BLEU, opacity=0.85,
                text=[f"{v:.3f}a" for v in [actif['dur_macaulay'],actif['dur_modifiee']]],
                textposition='outside', textfont=dict(color=BLANC,size=11)))
            fig.add_trace(go.Bar(
                name='Passif', x=['Duration Macaulay','Duration Modifiée'],
                y=[passif['dur_macaulay'], passif['dur_modifiee']],
                marker_color=AMBRE, opacity=0.85,
                text=[f"{v:.3f}a" for v in [passif['dur_macaulay'],passif['dur_modifiee']]],
                textposition='outside', textfont=dict(color=BLANC,size=11)))
            l = dict(**LAYOUT_BASE)
            c_gap = VERT if gap['statut']=='VERT' else (AMBRE if gap['statut']=='AMBRE' else ROUGE)
            l.update(dict(
                title=dict(text=f"G1 — Duration Actif vs Passif | Gap={gap['gap_macaulay']:+.3f}a [{gap['statut']}]",
                           font=dict(color=c_gap,size=12),x=0.01),
                barmode='group',
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)'),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)',title='Années'),
                annotations=[dict(
                    text=(f"💡 Gap={gap['gap_macaulay']:+.3f}a. "
                          f"{gap['recommandation']}"),
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['duration_actif_passif'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — STRESS TAUX DÉCOMPOSÉ
        try:
            labels = [d['label'] for d in stress['detail']]
            imp_a  = [d['imp_actif']  for d in stress['detail']]
            imp_p  = [d['imp_passif'] for d in stress['detail']]
            imp_n  = [d['imp_nav']    for d in stress['detail']]

            fig = go.Figure()
            fig.add_trace(go.Bar(name='Impact Actif', x=labels, y=imp_a,
                marker_color=BLEU, opacity=0.80,
                text=[f"{v/1e3:+.0f}k€" for v in imp_a],
                textposition='inside', textfont=dict(color=BLANC,size=9)))
            fig.add_trace(go.Bar(name='Impact Passif', x=labels, y=imp_p,
                marker_color=AMBRE, opacity=0.80,
                text=[f"{v/1e3:+.0f}k€" for v in imp_p],
                textposition='inside', textfont=dict(color=BLANC,size=9)))
            fig.add_trace(go.Scatter(name='Impact NAV Net', x=labels, y=imp_n,
                mode='lines+markers', line=dict(color=OR,width=3),
                marker=dict(size=10,color=OR),
                text=[f"{v/1e3:+.0f}k€" for v in imp_n],
                textposition='top center', textfont=dict(color=OR,size=10)))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text=f"G2 — Stress Taux ±200bp Décomposé | NAV base={stress['nav_base']/1e6:.2f}M€",
                           font=dict(color=OR,size=12),x=0.01),
                barmode='group',
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)',
                            orientation='h',y=-0.18),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
                annotations=[dict(
                    text="💡 La ligne or = impact NET sur la NAV. La décomposition actif/passif montre la source du risque.",
                    xref="paper",yref="paper",x=0.01,y=-0.28,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['stress_taux_decompose'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — REDINGTON 3 CONDITIONS (radar)
        try:
            c1_score = 1.0 if redington['c1']['ok'] else 0.0
            c2_score = 1.0 if redington['c2']['ok'] else max(0, 1 - abs(redington['c2']['valeur'])/2)
            c3_score = 1.0 if redington['c3']['ok'] else max(0, 0.5 + redington['c3']['valeur']/4)

            cats = ['C1 — VA\n(actif≥passif)',
                    'C2 — Duration\n(équilibre)',
                    'C3 — Convexité\n(actif>passif)']
            scores = [c1_score, c2_score, c3_score]

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=scores+[scores[0]], theta=cats+[cats[0]],
                fill='toself', fillcolor='rgba(201,168,76,0.12)',
                line=dict(color=OR,width=2.5),
                marker=dict(size=10, color=[VERT if s>=0.9 else (AMBRE if s>=0.5 else ROUGE) for s in scores+[scores[0]]]),
                name='Redington'))
            fig.add_trace(go.Scatterpolar(
                r=[1,1,1,1], theta=cats+[cats[0]],
                line=dict(color=VERT,width=1,dash='dot'),
                marker=dict(size=4,color=VERT), name='Cible',showlegend=True))

            c_r = VERT if redington['ok'] else (AMBRE if redington['nb_ok']>=2 else ROUGE)
            fig.update_layout(
                polar=dict(bgcolor=NAVY_L,
                    radialaxis=dict(visible=True,range=[0,1],
                        tickvals=[0,0.5,1],ticktext=['❌','~','✅'],
                        tickfont=dict(color=GRIS,size=9)),
                    angularaxis=dict(tickfont=dict(color=BLANC,size=10))),
                paper_bgcolor=NAVY, showlegend=True,
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)'),
                title=dict(text=f"G3 — Immunisation Redington {redington['nb_ok']}/3 conditions",
                           font=dict(color=c_r,size=12),x=0.01),
                margin=dict(l=60,r=60,t=60,b=60), height=340,
                font=dict(color=BLANC),
            )
            gph['redington_3conditions'] = fig
        except Exception as e:
            self.logger.warning(f"G3:{e}")

        # G4 — LCR WATERFALL + JAUGE
        try:
            fig = make_subplots(rows=1, cols=2,
                specs=[[{'type':'bar'},{'type':'indicator'}]],
                subplot_titles=['Composition HQLA','LCR (%)'])
            fig.add_trace(go.Bar(
                x=['HQLA N1\n(cash+oblig Etat)','HQLA N2\n(oblig corp)','Actions/Immo\n(haircut 50%)','Sorties\n30j'],
                y=[lcr['hqla_n1'],lcr['hqla_n2'],
                   lcr['actifs_liquides']-lcr['hqla_n1']-lcr['hqla_n2'],
                   -lcr['sorties_30j']],
                marker_color=[VERT,AMBRE,BLEU,ROUGE], opacity=0.85,
                text=[f"{v/1e6:.1f}M€" for v in [lcr['hqla_n1'],lcr['hqla_n2'],
                    lcr['actifs_liquides']-lcr['hqla_n1']-lcr['hqla_n2'],-lcr['sorties_30j']]],
                textposition='outside', textfont=dict(color=BLANC,size=9),
                showlegend=False), row=1, col=1)

            c_lcr = VERT if lcr['statut']=='VERT' else (AMBRE if lcr['statut']=='AMBRE' else ROUGE)
            fig.add_trace(go.Indicator(
                mode="gauge+number", value=lcr['lcr'],
                number=dict(suffix="%", font=dict(color=c_lcr,size=24)),
                gauge=dict(axis=dict(range=[0,300],tickvals=[0,75,100,150,200,300],
                    tickfont=dict(color=BLANC,size=8)),
                    bar=dict(color=c_lcr,thickness=0.3),bgcolor=NAVY_L,
                    steps=[dict(range=[0,75],color='rgba(231,76,60,0.3)'),
                           dict(range=[75,100],color='rgba(243,156,18,0.3)'),
                           dict(range=[100,300],color='rgba(46,204,113,0.15)')],
                    threshold=dict(line=dict(color=ROUGE,width=2),thickness=0.8,value=100))),
                row=1, col=2)

            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text=f"G4 — LCR={lcr['lcr']:.1f}% | HQLA={lcr['actifs_liquides']/1e6:.1f}M€",
                           font=dict(color=c_lcr,size=12),x=0.01),
                annotations=[dict(
                    text="💡 LCR ≥ 100% = conforme Basel III. HQLA N1 (Etat+cash) = meilleure qualité.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
                xaxis=dict(tickfont=dict(color=BLANC,size=8),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
            ))
            fig.update_layout(**l)
            gph['lcr_composition'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        return gph

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES
    # ══════════════════════════════════════════════════════════════════════════
    def _audit(self, aid, gap, redington, lcr, stress, rag):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'gap_macaulay':gap['gap_macaulay'],'redington_ok':redington['ok'],
                 'lcr':lcr['lcr'],'pire_stress':stress['pire_nav']}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, actif, passif, gap, redington, lcr, stress, rag, com):
        print(f"\n{'─'*70}\n  A12 AISHA v{self.VERSION} | {aid}\n{'─'*70}")
        print(com); print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {
            'success':False,'agent':self.NOM,'version':self.VERSION,'audit_id':aid,
            'statut_rag':'ROUGE',
            'duration':{'actif':0,'passif':0,'gap':0,'statut_gap':'ROUGE'},
            'bv01':{'bv01_actif':0,'bv01_passif':0,'bv01_net':0},
            'redington':{'ok':False,'nb_ok':0},
            'stress':{'pire_cas':'N/A','pire_nav':0},
            'lcr':{'lcr':0,'statut':'ROUGE'},
            'actif':{},'passif':{},'taux':{},
            'hypotheses':[],'commentaire':f"❌ ERREUR A12 Aisha : {msg}",
            'graphiques':{},'duree_sec':0.0,'erreur':msg,
        }


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  A12 AISHA v1.0 — DÉMO ALM & LIQUIDITÉ NON-VIE")
    print("  Duration | BV01 | Redington 3C | Stress ±200bp | LCR")
    print("="*70)

    a10 = {
        'provisions':{'best_estimate':6_195_000.0,'risk_margin':236_000.0,'tp_s2':6_431_000.0},
        'taux':{'rfr_10ans':0.032,'rfr_5ans':0.031,'rfr_20ans':0.033,
                'source':'FALLBACK','fiabilite':'REFERENCE'},
        'duration':{'passif':3.88,'par_branche':[
            {'nom':'rc_auto','duration_macaulay':4.0,'poids':0.68},
            {'nom':'mrh',    'duration_macaulay':2.0,'poids':0.32},
        ]},
        'scr':{'total':3_771_000.0},
        'detail':{'scr_mkt':{'allocation':{'obligations':0.72,'actions':0.08,'immo':0.05}}},
    }

    agent = AgentA12ALM(audit_path='/tmp/a12/audit', verbose=True)
    r = agent.run(
        result_a10=a10,
        params_alm={'taux_sortie_30j':0.10},
        generer_graphiques=False,
    )

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut   : {r['statut_rag']} | {r.get('motif_rag','')}")
    d = r['duration']
    print(f"  Dur actif : {d['actif']:.4f}a (mod={d['actif_modifiee']:.4f}a)")
    print(f"  Dur passif: {d['passif']:.4f}a (mod={d['passif_modifiee']:.4f}a)")
    print(f"  Gap       : {d['gap']:+.4f}a [{d['statut_gap']}]")
    b = r['bv01']
    print(f"  BV01 net  : {r['bv01']['bv01_net']:+.2f}€/bp | impact+100bp={r['bv01']['impact_100bp']:+,.0f}€")
    rd = r['redington']
    print(f"  Redington : {rd['detail']['nb_ok']}/3 conditions | ok={rd['ok']}")
    s = r['stress']
    print(f"  Pire stress: {s['pire_cas']} → {s['pire_nav']:+,.0f}€ NAV")
    print(f"  LCR       : {r['lcr']['lcr']:.1f}% [{r['lcr']['statut']}]")
    print(f"  Durée     : {r['duree_sec']:.2f}s")
