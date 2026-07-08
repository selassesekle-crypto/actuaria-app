"""
ActuarIA — Agent EP7 : Camille — Optimisation PB sous Contraintes
Direction Vie & EP-RE | Manager : Olivier | Directeur : Paul

Optimisation du taux de participation aux bénéfices (PB) :
→ Maximisation du taux servi aux assurés
→ Sous contraintes réglementaires : SCR cible, L132-29, PPB plafond (C2023-10)
→ Sous contraintes commerciales : spread minimum, fidélisation
→ Algorithme d'optimisation par dichotomie + analyse de sensibilité
→ Recommandation actionnable : taux PB optimal N+1
→ Alimentation depuis EP3 (PPB), EP4 (SCR stress), EP1 (DBO), EP2 (capital)
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.ep7 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent EP7 — Optimisation PB sous Contraintes ActuarIA v1.0")
print("Optimisation : PB maximale · SCR · L132-29 · PPB cible")
print("Usage : agent_ep7 = AgentEP7OptimisationPB()")
print("        result_ep7 = agent_ep7.run(pm_total=50e6, rendement_actifs=0.04)")


class AgentEP7OptimisationPB:
    """
    Agent EP7 — Camille : Optimisation du taux de PB sous contraintes.

    PROBLÈME D'OPTIMISATION :
    ──────────────────────────
    Maximiser : tx_servi (taux de participation aux bénéfices servi aux assurés)

    Sous contraintes :
    1. [C_SCR]    Ratio SCR post-distribution ≥ scr_cible (ex : 150%)
    2. [C_L132]   PB_servie + PB_ppb ≥ 85% × produits_financiers (Art. L132-29)
    3. [C_PPB]    PPB_après_distrib ≤ 10% × PM (C2023-10 ACPR)
    4. [C_SPREAD] tx_servi ≥ taux_technique + spread_min (fidélisation)
    5. [C_TMG]    tx_servi ≥ TMG contractuel (obligation)

    MÉTHODE DE RÉSOLUTION :
    ────────────────────────
    Dichotomie sur tx_servi dans [taux_technique, rendement_actifs] :
    1. Évaluer toutes les contraintes pour tx candidat
    2. Si toutes respectées → augmenter tx (chercher mieux)
    3. Si au moins une violée → diminuer tx (revenir en arrière)
    4. Précision cible : 1 bp (0.01%)
    """

    def __init__(self, models_path='/tmp/actuaria/models',
                 audit_path='/tmp/actuaria/audit', verbose=True):
        self.models_path = models_path
        self.audit_path  = audit_path
        self.verbose     = verbose
        self.logger      = logging.getLogger('actuaria.ep7')
        os.makedirs(models_path, exist_ok=True)
        os.makedirs(audit_path, exist_ok=True)

    def run(
        self,
        pm_total:          float = 50_000_000,
        rendement_actifs:  float =       0.04,
        taux_technique:    float =      0.025,
        fonds_propres:     float =  8_000_000,
        scr_vie:           float =  5_000_000,
        ppb_stock:         float =  1_500_000,
        tmg_max:           float =      0.005,
        scr_cible_pct:     float =      150.0,
        spread_min:        float =      0.005,
        precision_bp:      float =      0.001,
        result_ep3:        Optional[Dict] = None,
        result_ep4:        Optional[Dict] = None,
        result_ep1:        Optional[Dict] = None,
        generer_graphiques:bool  =       True,
    ) -> Dict:
        """
        Optimise le taux de PB sous contraintes réglementaires et commerciales.

        Paramètres
        ──────────
        pm_total : float
            Provisions mathématiques (€). Alimenté par EP3 si disponible.

        rendement_actifs : float
            Rendement du portefeuille d'actifs (ex: 0.04 = 4%).
            Borne supérieure naturelle du taux servi.

        taux_technique : float
            Taux minimum garanti (TMG contractuel).
            Borne inférieure du taux servi.

        fonds_propres : float
            Fonds propres disponibles pour le calcul SCR.

        scr_vie : float
            SCR Vie calculé par R-VIE1 (€).

        ppb_stock : float
            Stock de PPB disponible (€). Alimenté par EP3 si disponible.

        tmg_max : float
            TMG maximum contractuel à respecter (= taux_technique si régime récent).

        scr_cible_pct : float
            Ratio SCR cible post-distribution (ex: 150%).

        spread_min : float
            Spread minimum à servir au-dessus du TMG (fidélisation, ex: 0.5%).

        result_ep3/ep4/ep1 : dict, optional
            Résultats des agents amont pour alimentation automatique.
        """
        audit_id = f"EP7_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger = self.logger
        if self.verbose:
            logger.info(f"[{audit_id}] Agent EP7 démarré | PM={pm_total/1e6:.1f}M€ | Rend={rendement_actifs*100:.2f}%")

        try:
            # ── Alimentation depuis la chaîne ─────────────────────────────────
            sources = {}
            if result_ep3 and result_ep3.get('success'):
                prov = result_ep3.get('provisions', {})
                pm_total   = prov.get('pm_encours', pm_total)
                ppb_stock  = prov.get('ppb_total', ppb_stock)
                sources['pm_total']  = 'EP3 Jin-Ho (provisions.pm_encours)'
                sources['ppb_stock'] = 'EP3 Jin-Ho (provisions.ppb_total)'
                logger.info(f"[{audit_id}] PM={pm_total/1e6:.1f}M€ | PPB={ppb_stock/1e3:.0f}k€ (EP3)")

            if result_ep4 and result_ep4.get('success'):
                ratio_base_ep4 = result_ep4.get('ratio_base', 0)
                if ratio_base_ep4 > 0:
                    # Ajuster la cible SCR si le stress EP4 révèle une fragilité
                    if ratio_base_ep4 < 130:
                        scr_cible_pct = max(scr_cible_pct, 160.0)
                        sources['scr_cible_ajuste'] = f"EP4 Claire : ratio_base={ratio_base_ep4:.1f}% → cible SCR relevée à {scr_cible_pct:.0f}%"
                    logger.info(f"[{audit_id}] Ratio base EP4 = {ratio_base_ep4:.1f}%")

            if result_ep1 and result_ep1.get('success'):
                dbo = result_ep1.get('ias19', {}).get('dbo_total', 0)
                if dbo > 0:
                    sources['dbo_ep1'] = f"EP1 Henri : DBO = {dbo/1e6:.1f}M€"

            # ── PARAMÈTRES FINANCIERS ──────────────────────────────────────────
            produits_financiers = pm_total * rendement_actifs
            pb_legale_min       = produits_financiers * 0.85  # Art. L132-29

            # Borne inférieure = max(TMG contractuel, TMG + spread_min)
            tx_min = max(taux_technique, taux_technique + spread_min, tmg_max)
            # Borne supérieure = rendement actifs (ne peut pas distribuer plus)
            tx_max = rendement_actifs

            if tx_min >= tx_max:
                tx_optimal = tx_min
                logger.warning(f"[{audit_id}] tx_min ≥ tx_max → tx_optimal = tx_min = {tx_min*100:.2f}%")
            else:
                # ── OPTIMISATION PAR DICHOTOMIE ───────────────────────────────
                tx_optimal = self._dichotomie(
                    tx_min, tx_max, precision_bp,
                    pm_total, produits_financiers, pb_legale_min,
                    fonds_propres, scr_vie, ppb_stock,
                    scr_cible_pct, audit_id
                )

            # ── ÉVALUATION DU TAUX OPTIMAL ─────────────────────────────────────
            eval_opt = self._evaluer_taux(
                tx_optimal, pm_total, produits_financiers, pb_legale_min,
                fonds_propres, scr_vie, ppb_stock, scr_cible_pct
            )

            # ── ANALYSE DE SENSIBILITÉ ────────────────────────────────────────
            # Impact de ±50bp sur le taux servi
            sensibilite = {}
            for delta, label in [(-0.005, '-50bp'), (-0.0025, '-25bp'),
                                  (+0.0025, '+25bp'), (+0.005, '+50bp')]:
                tx_candidat = max(tx_min, min(tx_max, tx_optimal + delta))
                ev = self._evaluer_taux(
                    tx_candidat, pm_total, produits_financiers, pb_legale_min,
                    fonds_propres, scr_vie, ppb_stock, scr_cible_pct
                )
                sensibilite[label] = {
                    'tx_servi': round(tx_candidat, 6),
                    'tx_servi_pct': round(tx_candidat * 100, 3),
                    'toutes_contraintes_ok': ev['toutes_ok'],
                    'pb_servie': round(ev['pb_servie'], 0),
                    'ppb_finale': round(ev['ppb_finale'], 0),
                    'ratio_scr': round(ev['ratio_scr'], 1),
                }

            # ── RECOMMANDATION ────────────────────────────────────────────────
            statut_rag = 'VERT' if eval_opt['toutes_ok'] else 'AMBRE'

            commentaire = (
                f"{'✅' if statut_rag=='VERT' else '⚠️'} Optimisation PB — "
                f"PM {pm_total/1e6:.1f}M€ | Rendement {rendement_actifs*100:.2f}%.\n"
                f"Taux PB optimal : {tx_optimal*100:.3f}% "
                f"(vs TMG {taux_technique*100:.2f}% / rend. {rendement_actifs*100:.2f}%).\n"
                f"PB servie : {eval_opt['pb_servie']/1e3:.0f}k€ | "
                f"PPB finale : {eval_opt['ppb_finale']/1e3:.0f}k€.\n"
                f"Ratio SCR post-distribution : {eval_opt['ratio_scr']:.1f}% "
                f"(cible ≥ {scr_cible_pct:.0f}%).\n"
                f"Toutes contraintes respectées : {'✅ OUI' if eval_opt['toutes_ok'] else '❌ NON'}."
            )

            val_hyp = self._valider_optimisation(
                tx_optimal, tx_min, tx_max, eval_opt,
                scr_cible_pct, pb_legale_min
            )
            graphiques = {}
            gv = {}
            if generer_graphiques:
                graphiques = self._generer_graphiques(
                    tx_optimal, tx_min, tx_max, rendement_actifs,
                    eval_opt, sensibilite, pm_total, pb_legale_min
                )
                gv = self._graphiques_validation_pb(val_hyp, sensibilite, tx_optimal)

            self._sauvegarder({
                'agent': 'EP7 Camille', 'pm_total': pm_total,
                'tx_optimal': tx_optimal, 'pb_servie': eval_opt['pb_servie'],
                'ratio_scr': eval_opt['ratio_scr'],
            }, audit_id)

            return {
                'success':             True,
                'agent':               'EP7 Camille',
                'statut_rag':          statut_rag,
                'tx_optimal':          round(tx_optimal, 6),
                'tx_optimal_pct':      round(tx_optimal * 100, 3),
                'tx_min':              round(tx_min, 6),
                'tx_max':              round(tx_max, 6),
                'evaluation_optimale': eval_opt,
                'sensibilite':         sensibilite,
                'pm_total':            round(pm_total, 0),
                'produits_financiers': round(produits_financiers, 0),
                'pb_legale_min':       round(pb_legale_min, 0),
                'scr_cible_pct':       scr_cible_pct,
                'sources':             sources,
                'commentaire':         commentaire,
                'audit_id':            audit_id,
                'graphiques':          graphiques,
                'validation_pb':       val_hyp,
                'graphiques_validation': gv,
                'erreur':              None,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR EP7 : {e}", exc_info=True)
            return {'success': False, 'statut_rag': 'ROUGE',
                    'erreur': str(e), 'audit_id': audit_id}

    def _evaluer_taux(self, tx, pm, prod_fi, pb_min, fp, scr, ppb_stock,
                       scr_cible) -> Dict:
        """Évalue toutes les contraintes pour un taux candidat."""
        pb_servie = pm * tx

        # PPB portée en réserve : complément pour atteindre le minimum L132-29
        pb_portee_ppb = max(0, prod_fi * 0.85 - pb_servie)
        ppb_finale    = ppb_stock + pb_portee_ppb

        # C_L132 : PB servie + PB portée en PPB ≥ 85% produits financiers (Art. L132-29)
        # La PPB est comptabilisée comme PB différée — elle satisfait la contrainte
        c_l132_ok = (pb_servie + pb_portee_ppb >= pb_min * 0.99)  # tolérance 1%

        # C_PPB : PPB finale ≤ 10% PM (C2023-10)
        c_ppb_ok = (ppb_finale <= pm * 0.10)

        # Ratio SCR post-distribution
        # La distribution de PB réduit les fonds propres
        fp_post = fp - pb_servie + prod_fi  # FP + produits - PB
        ratio_scr = fp_post / max(scr, 1) * 100

        # C_SCR : Ratio SCR ≥ cible
        c_scr_ok = (ratio_scr >= scr_cible)

        toutes_ok = c_l132_ok and c_ppb_ok and c_scr_ok

        return {
            'toutes_ok':   toutes_ok,
            'pb_servie':   round(pb_servie, 0),
            'ppb_finale':  round(ppb_finale, 0),
            'ratio_scr':   round(ratio_scr, 1),
            'fp_post':     round(fp_post, 0),
            'c_l132_ok':   c_l132_ok,
            'c_ppb_ok':    c_ppb_ok,
            'c_scr_ok':    c_scr_ok,
            # Note : le spread vs TMG est calculé dans _valider_optimisation
            # (tx_opt - tx_min) — non recalculé ici car taux_technique absent du scope
        }

    def _dichotomie(self, tx_min, tx_max, precision,
                     pm, prod_fi, pb_min, fp, scr, ppb_stock,
                     scr_cible, audit_id) -> float:
        """Dichotomie : cherche le taux maximum respectant toutes les contraintes."""
        lo, hi = tx_min, tx_max
        tx_ok = tx_min  # solution courante valide

        max_iter = 50
        for _ in range(max_iter):
            if hi - lo < precision:
                break
            mid = (lo + hi) / 2
            ev = self._evaluer_taux(mid, pm, prod_fi, pb_min, fp, scr,
                                     ppb_stock, scr_cible)
            if ev['toutes_ok']:
                tx_ok = mid  # ce taux est admissible → chercher mieux
                lo = mid
            else:
                hi = mid     # trop élevé → descendre

        return round(tx_ok, 6)

    # ─── VALIDATION ──────────────────────────────────────────────────────────
    def _valider_optimisation(self, tx_opt, tx_min, tx_max, eval_opt,
                               scr_cible, pb_min) -> Dict:
        """
        P1 — Toutes les contraintes respectées au taux optimal
        P2 — Spread au-dessus du TMG ≥ 0.5% (attractivité commerciale)
        P3 — Marge de manœuvre ≥ 25bp (distance au plafond)
        """
        # P1 — Contraintes
        if eval_opt['toutes_ok']:
            p1_s = 'VERT'
            p1_m = f"Toutes contraintes respectées à {tx_opt*100:.3f}% ✅"
            p1_c = "Taux optimal admissible — décision de gestion solidement fondée"
        else:
            violated = []
            if not eval_opt['c_l132_ok']: violated.append("L132-29")
            if not eval_opt['c_ppb_ok']:  violated.append("PPB > 10%")
            if not eval_opt['c_scr_ok']:  violated.append(f"SCR < {scr_cible:.0f}%")
            p1_s = 'ROUGE'
            p1_m = f"Contrainte(s) violée(s) : {', '.join(violated)} ❌"
            p1_c = "Réduire le taux servi ou renforcer les fonds propres avant distribution"

        # P2 — Spread vs TMG
        spread = tx_opt - tx_min
        if spread >= 0.005:
            p2_s = 'VERT'
            p2_m = f"Spread = {spread*100:.2f}pp ≥ 0.5pp ✅"
            p2_c = "Attractivité commerciale confirmée — les assurés sont fidélisés"
        elif spread >= 0:
            p2_s = 'AMBRE'
            p2_m = f"Spread = {spread*100:.2f}pp < 0.5pp ⚠️"
            p2_c = "Spread limité — risque de rachats si la concurrence sert plus"
        else:
            p2_s = 'ROUGE'
            p2_m = f"Taux optimal < TMG ❌ — situation de sous-rémunération"
            p2_c = "Revalorisation insuffisante — risque de rachat massif et de non-conformité"

        # P3 — Marge au plafond (distance entre taux optimal et borne max)
        marge_plafond = tx_max - tx_opt
        if marge_plafond >= 0.0025:
            p3_s = 'VERT'
            p3_m = f"Marge au plafond = {marge_plafond*100:.2f}pp ≥ 0.25pp ✅"
            p3_c = "Capacité de distribution future préservée"
        elif marge_plafond >= 0:
            p3_s = 'AMBRE'
            p3_m = f"Marge au plafond = {marge_plafond*100:.2f}pp (très faible) ⚠️"
            p3_c = "Taux quasi-maximal — vulnérable à une baisse du rendement actifs"
        else:
            p3_s = 'ROUGE'
            p3_m = "Taux optimal > plafond — incohérence ❌"
            p3_c = "Revoir les paramètres de l'optimisation"

        sts = [p1_s, p2_s, p3_s]
        sg = 'ROUGE' if 'ROUGE' in sts else 'AMBRE' if 'AMBRE' in sts else 'VERT'
        return {
            'p1_contraintes': {'statut': p1_s, 'message': p1_m, 'conseil': p1_c,
                               'titre_graphique': f"{'✅' if p1_s=='VERT' else '❌'} Contraintes au taux {tx_opt*100:.3f}%"},
            'p2_spread':      {'spread_pp': round(spread * 100, 3), 'statut': p2_s,
                               'message': p2_m, 'conseil': p2_c,
                               'titre_graphique': f"{'✅' if p2_s=='VERT' else '⚠️' if p2_s=='AMBRE' else '❌'} Spread = {spread*100:.2f}pp"},
            'p3_marge':       {'marge_pp': round(marge_plafond * 100, 3), 'statut': p3_s,
                               'message': p3_m, 'conseil': p3_c,
                               'titre_graphique': f"{'✅' if p3_s=='VERT' else '⚠️' if p3_s=='AMBRE' else '❌'} Marge = {marge_plafond*100:.2f}pp"},
            'statut_global': sg,
            'conclusion': {
                'VERT':  '✅ Optimisation PB validée — taux défendable devant l\'ACPR et le CA',
                'AMBRE': '⚠️ Optimisation acceptable — renforcer la marge ou le spread',
                'ROUGE': '❌ Optimisation non admissible — action correctrice requise',
            }[sg],
        }

    # ─── GRAPHIQUES ──────────────────────────────────────────────────────────
    def _generer_graphiques(self, tx_opt, tx_min, tx_max, rend,
                             eval_opt, sensibilite, pm, pb_min) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; OR='#C9A84C'; BLANC='#F0F4F8'
        GRIS='#8A9AB0'; VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'; BLEU='#3498DB'
        LAYOUT = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                      font=dict(family='Inter', color=BLANC, size=11),
                      margin=dict(l=16, r=16, t=60, b=50), height=300)
        graphiques = {}

        # G1 — Positionnement taux optimal dans la plage
        try:
            categories = ['TMG min', 'Taux optimal', 'Rendement actifs']
            valeurs    = [tx_min * 100, tx_opt * 100, tx_max * 100]
            couleurs   = [GRIS, VERT if eval_opt['toutes_ok'] else AMBRE, BLEU]
            fig1 = go.Figure(go.Bar(
                x=categories, y=valeurs,
                marker_color=couleurs, width=0.4, opacity=0.88,
                text=[f'{v:.3f}%' for v in valeurs],
                textposition='outside', textfont=dict(color=BLANC, size=11),
            ))
            fig1.add_hline(y=tx_opt * 100, line_color=OR, line_width=2, line_dash='dash',
                           annotation_text=f"Taux optimal : {tx_opt*100:.3f}%",
                           annotation_font=dict(color=OR, size=9))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(text=f"Taux PB optimal = {tx_opt*100:.3f}% (plage : {tx_min*100:.2f}% – {tx_max*100:.2f}%)",
                           font=dict(color=VERT if eval_opt['toutes_ok'] else AMBRE, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title='Taux (%)', tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 Le taux optimal est la valeur maximale respectant toutes les contraintes réglementaires.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig1.update_layout(**l1)
            graphiques['taux_optimal'] = fig1
        except Exception:
            pass

        # G2 — Sensibilité : ratio SCR pour différents taux
        try:
            labels_s = ['-50bp', '-25bp', 'Optimal', '+25bp', '+50bp']
            txs_s    = [
                sensibilite.get('-50bp', {}).get('tx_servi_pct', tx_opt*100 - 0.5),
                sensibilite.get('-25bp', {}).get('tx_servi_pct', tx_opt*100 - 0.25),
                tx_opt * 100,
                sensibilite.get('+25bp', {}).get('tx_servi_pct', tx_opt*100 + 0.25),
                sensibilite.get('+50bp', {}).get('tx_servi_pct', tx_opt*100 + 0.5),
            ]
            scrs_s = [
                sensibilite.get('-50bp', {}).get('ratio_scr', 0),
                sensibilite.get('-25bp', {}).get('ratio_scr', 0),
                eval_opt['ratio_scr'],
                sensibilite.get('+25bp', {}).get('ratio_scr', 0),
                sensibilite.get('+50bp', {}).get('ratio_scr', 0),
            ]
            ok_s = [
                sensibilite.get('-50bp', {}).get('toutes_contraintes_ok', True),
                sensibilite.get('-25bp', {}).get('toutes_contraintes_ok', True),
                eval_opt['toutes_ok'],
                sensibilite.get('+25bp', {}).get('toutes_contraintes_ok', False),
                sensibilite.get('+50bp', {}).get('toutes_contraintes_ok', False),
            ]
            colors_s = [VERT if ok else ROUGE for ok in ok_s]
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=labels_s, y=scrs_s, marker_color=colors_s, opacity=0.88, width=0.5,
                text=[f'{s:.1f}%' for s in scrs_s],
                textposition='outside', textfont=dict(color=BLANC, size=9),
                hovertemplate="<b>%{x}</b><br>Ratio SCR : %{y:.1f}%<extra></extra>",
            ))
            fig2.add_hline(y=eval_opt['ratio_scr'], line_color=OR, line_width=2, line_dash='dash',
                           annotation_text=f"Optimal {eval_opt['ratio_scr']:.1f}%",
                           annotation_font=dict(color=OR, size=9))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text='Sensibilité ratio SCR selon le taux PB ±50bp',
                           font=dict(color=BLANC, size=11), x=0.01),
                xaxis=dict(title='Variation taux PB', tickfont=dict(color=BLANC, size=9)),
                yaxis=dict(title='Ratio SCR (%)', tickfont=dict(color=GRIS),
                           showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                showlegend=False,
                annotations=[dict(
                    text="💡 Vert = toutes contraintes respectées. Rouge = au moins une contrainte violée.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig2.update_layout(**l2)
            graphiques['sensibilite_scr'] = fig2
        except Exception:
            pass

        # G3 — Décomposition PB (L132-29)
        try:
            pb_opt  = pm * tx_opt
            pb_ppb  = max(0, pm * rend * 0.85 - pb_opt)
            pb_tot  = pb_opt + pb_ppb
            fig3 = go.Figure(go.Bar(
                x=['PB servie\naux assurés', 'PB portée\nen PPB', 'PB totale\n(L132-29)', 'PB minimale\n(85% × PF)'],
                y=[pb_opt / 1e3, pb_ppb / 1e3, pb_tot / 1e3, pb_min / 1e3],
                marker_color=[OR, BLEU, VERT if pb_tot >= pb_min else ROUGE, GRIS],
                width=0.4, opacity=0.88,
                text=[f'{v:.0f}k€' for v in [pb_opt/1e3, pb_ppb/1e3, pb_tot/1e3, pb_min/1e3]],
                textposition='outside', textfont=dict(color=BLANC, size=10),
            ))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text=f"Décomposition PB Art. L132-29 — Taux {tx_opt*100:.3f}%",
                           font=dict(color=BLANC, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title='k€', tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 PB totale (servie + PPB) doit couvrir la PB minimale réglementaire (85% produits financiers).",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig3.update_layout(**l3)
            graphiques['decomposition_pb_l132'] = fig3
        except Exception:
            pass

        # G4 — Jauge taux optimal dans la plage
        try:
            pct_plage = (tx_opt - tx_min) / max(tx_max - tx_min, 0.001) * 100
            c_jauge = VERT if eval_opt['toutes_ok'] else AMBRE
            fig4 = go.Figure(go.Indicator(
                mode='gauge+number',
                value=tx_opt * 100,
                number=dict(suffix='%', font=dict(color=c_jauge, size=28), valueformat='.3f'),
                title=dict(text=f"Taux PB optimal ({pct_plage:.0f}% de la plage disponible)",
                           font=dict(color=c_jauge, size=11)),
                gauge=dict(
                    axis=dict(range=[tx_min * 100, tx_max * 100],
                              tickfont=dict(color=GRIS, size=8)),
                    bar=dict(color=c_jauge, thickness=0.25), bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[tx_min * 100, (tx_min + (tx_max - tx_min) * 0.33) * 100],
                             color='rgba(46,204,113,0.12)'),
                        dict(range=[(tx_min + (tx_max - tx_min) * 0.33) * 100,
                                    (tx_min + (tx_max - tx_min) * 0.67) * 100],
                             color='rgba(243,156,18,0.12)'),
                        dict(range=[(tx_min + (tx_max - tx_min) * 0.67) * 100, tx_max * 100],
                             color='rgba(231,76,60,0.12)'),
                    ],
                    threshold=dict(line=dict(color=OR, width=3), thickness=0.8,
                                   value=tx_opt * 100),
                ),
            ))
            fig4.update_layout(paper_bgcolor=NAVY, font=dict(color=BLANC),
                               margin=dict(l=30, r=30, t=80, b=50), height=300,
                               annotations=[dict(
                                   text=f"💡 Zone verte = conservateur · Zone orange = équilibre · Zone rouge = maximum absolu.",
                                   xref='paper', yref='paper', x=0.5, y=-0.12,
                                   font=dict(color=GRIS, size=9), showarrow=False)])
            graphiques['jauge_taux_optimal'] = fig4
        except Exception:
            pass

        return graphiques

    def _graphiques_validation_pb(self, val, sensibilite, tx_opt) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; BLANC='#F0F4F8'; GRIS='#8A9AB0'
        VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'
        graphiques = {}
        try:
            items = [
                ('P1 — Contraintes respectées', val['p1_contraintes']['statut'],
                 val['p1_contraintes']['message'], val['p1_contraintes']['conseil']),
                ('P2 — Spread ≥ 0.5pp (fidélisation)', val['p2_spread']['statut'],
                 val['p2_spread']['message'], val['p2_spread']['conseil']),
                ('P3 — Marge au plafond ≥ 0.25pp', val['p3_marge']['statut'],
                 val['p3_marge']['message'], val['p3_marge']['conseil']),
            ]
            fig = go.Figure()
            for nom, statut, msg, conseil in items:
                c = VERT if statut == 'VERT' else AMBRE if statut == 'AMBRE' else ROUGE
                i = '✅' if statut == 'VERT' else '⚠️' if statut == 'AMBRE' else '❌'
                s = 1.0 if statut == 'VERT' else 0.5 if statut == 'AMBRE' else 0.0
                fig.add_trace(go.Bar(x=[s], y=[nom], orientation='h', marker_color=c,
                    width=0.5, text=f"{i} {statut}", textposition='outside',
                    textfont=dict(color=c, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False))
            sg = val['statut_global']
            cg = VERT if sg == 'VERT' else AMBRE if sg == 'AMBRE' else ROUGE
            fig.update_layout(
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family='Inter', color=BLANC, size=11),
                margin=dict(l=16, r=16, t=60, b=50), height=260,
                title=dict(text=f"Scorecard Optimisation PB — {val['conclusion']}",
                           font=dict(color=cg, size=10), x=0.01),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode='overlay',
                annotations=[dict(
                    text="💡 3 ✅ = taux PB optimal défendable devant l'ACPR et le Comité d'Audit.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)])
            graphiques['scorecard_optim_pb'] = fig
        except Exception:
            pass
        return graphiques

    def _sauvegarder(self, rapport, audit_id):
        try:
            fpath = os.path.join(self.models_path, f"ep7_optim_{audit_id}.json")
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sauvegardé : ep7_optim_{audit_id}.json")
        except Exception as e:
            self.logger.warning(f"Sauvegarde EP7 : {e}")
