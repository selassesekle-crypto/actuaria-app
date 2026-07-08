"""
ActuarIA — Agent V6 : Sven — Projection ALM Dynamique Vie
Direction Vie & EP-RE | Manager : Sven | Directeur : Paul

Projection Asset-Liability Management (ALM) sur 5-10 ans :
→ Projection des PM (passif) sur l'horizon via V3 + V4 en chaîne temporelle
→ Projection des actifs (rendement, duration, stress taux)
→ Ratio de couverture annuel actifs/passifs
→ Gap de duration actif/passif (mismatch)
→ Scénarios de stress EIOPA (hausse/baisse taux)
→ Validation H1/H2/H3 + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.v6 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent V6 — Projection ALM Dynamique Vie ActuarIA v1.0")
print("ALM : PM projetées · Actifs · Duration gap · Stress taux EIOPA")
print("Usage : agent_v6 = AgentV6ALMDynamique()")
print("        result_v6 = agent_v6.run(pm_initiale=50e6, rendement_actifs=0.04)")


class AgentV6ALMDynamique:
    """
    Agent V6 — Sven : Projection ALM dynamique Vie sur 5-10 ans.

    MÉTHODE ALM :
    ─────────────
    L'ALM (Asset-Liability Management) consiste à analyser l'adéquation
    entre les actifs et les passifs d'un assureur vie sur un horizon pluriannuel.

    PASSIF (PM projetées) :
    La PM évolue chaque année selon :
        PM(t+1) = PM(t) × (1 + rendement_pm) - sorties(t)
    où sorties = prestations versées + rachats

    ACTIF (portefeuille obligataire simplifié) :
        Actif(t+1) = Actif(t) × (1 + rendement_actifs) - prestations(t)

    DURATION GAP :
        Gap = Duration_passif - Duration_actif
        Un gap positif → le passif s'allonge plus vite que l'actif (risque de taux)
        Un gap négatif → l'actif est plus sensible que le passif

    SOLVABILITÉ 2 — SCÉNARIOS STRESS :
    Choc +200bp EIOPA : baisse de la valeur des actifs obligataires
    Choc -200bp EIOPA : hausse de la valeur des actifs et augmentation du passif
    """

    def __init__(self, models_path='/tmp/actuaria/models',
                 audit_path='/tmp/actuaria/audit', verbose=True):
        self.models_path = models_path
        self.audit_path  = audit_path
        self.verbose     = verbose
        self.logger      = logging.getLogger('actuaria.v6')
        os.makedirs(models_path, exist_ok=True)
        os.makedirs(audit_path, exist_ok=True)

    def run(
        self,
        pm_initiale:        float = 50_000_000,
        actif_initiale:     float = 55_000_000,
        rendement_actifs:   float = 0.04,
        taux_technique_pm:  float = 0.025,
        duration_actif:     float = 7.0,
        duration_passif:    float = 10.0,
        taux_sorties_annuel:float = 0.05,
        horizon:            int   = 10,
        taux_sans_risque:   float = 0.03,
        result_v3:          Optional[Dict] = None,
        result_v4:          Optional[Dict] = None,
        result_rvie1:       Optional[Dict] = None,
        generer_graphiques: bool  = True,
    ) -> Dict:
        """
        Projette l'ALM sur l'horizon demandé.

        Paramètres
        ──────────
        pm_initiale : float
            PM en début de période (€). Alimenté par V3 si disponible.

        actif_initiale : float
            Valeur de marché des actifs en début de période (€).

        rendement_actifs : float
            Rendement annuel du portefeuille d'actifs (ex: 0.04 = 4%).

        taux_technique_pm : float
            Taux de revalorisation des PM (= taux servi aux assurés).
            Alimenté par V4 (tx_servi_cible) si disponible.

        duration_actif : float
            Duration modifiée du portefeuille d'actifs (années).
            Typique obligataire vie : 5-9 ans.

        duration_passif : float
            Duration modifiée du passif vie (années).
            Typique contrats vie longue durée : 8-15 ans.

        taux_sorties_annuel : float
            Taux annuel de sorties du passif (rachats + prestations).
            Typique : 3-8% des PM.

        result_v3 : dict, optional
            Alimente pm_initiale depuis V3 Amélie.

        result_v4 : dict, optional
            Alimente taux_technique_pm depuis V4 Théo.

        result_rvie1 : dict, optional
            Alimente fonds_propres (via scr_vie_total) depuis R-VIE1.
        """
        audit_id = f"V6_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger = self.logger
        if self.verbose:
            logger.info(f"[{audit_id}] Agent V6 démarré | PM={pm_initiale/1e6:.1f}M€ | horizon={horizon}ans")

        try:
            # ── Alimentation depuis la chaîne actuarielle ─────────────────────
            sources = {}
            if result_v3 and result_v3.get('success'):
                pm_initiale = result_v3.get('pm_prospective', pm_initiale)
                sources['pm_initiale'] = 'V3 Amélie (pm_prospective)'
                logger.info(f"[{audit_id}] PM alimentée depuis V3 : {pm_initiale/1e6:.1f}M€")

            if result_v4 and result_v4.get('success'):
                taux_technique_pm = result_v4.get('tx_servi_cible', taux_technique_pm)
                sources['taux_technique_pm'] = 'V4 Théo (tx_servi_cible)'
                logger.info(f"[{audit_id}] Taux servi alimenté depuis V4 : {taux_technique_pm*100:.2f}%")

            if result_rvie1 and result_rvie1.get('success'):
                scr_vie = result_rvie1.get('scr_vie_total', pm_initiale * 0.10)
                sources['scr_ref'] = 'R-VIE1 Éric (scr_vie_total)'
            else:
                scr_vie = pm_initiale * 0.10  # SCR approximé à 10% PM

            # ── PROJECTION ANNUELLE ACTIFS / PASSIFS ──────────────────────────
            projection = []
            pm_t    = pm_initiale
            actif_t = actif_initiale

            for t in range(1, horizon + 1):
                # Sorties du passif (prestations + rachats)
                sorties_t = pm_t * taux_sorties_annuel

                # PM fin de période = PM début × (1 + taux_technique) - sorties
                pm_t_new = pm_t * (1 + taux_technique_pm) - sorties_t
                pm_t_new = max(pm_t_new, 0)

                # Actif fin de période = Actif × (1 + rendement) - sorties
                actif_t_new = actif_t * (1 + rendement_actifs) - sorties_t
                actif_t_new = max(actif_t_new, 0)

                # Ratio de couverture actifs / PM
                ratio_couv = actif_t_new / max(pm_t_new, 1)

                # Marge (surplus)
                surplus = actif_t_new - pm_t_new

                # Ratio SCR (surplus / SCR de référence)
                ratio_scr_t = surplus / max(scr_vie, 1) * 100

                projection.append({
                    'annee':        t,
                    'pm':           round(pm_t_new, 0),
                    'actif':        round(actif_t_new, 0),
                    'sorties':      round(sorties_t, 0),
                    'ratio_couv':   round(ratio_couv, 4),
                    'surplus':      round(surplus, 0),
                    'ratio_scr':    round(ratio_scr_t, 1),
                    'couv_ok':      ratio_couv >= 1.0,
                })

                pm_t    = pm_t_new
                actif_t = actif_t_new

            # ── DURATION GAP ─────────────────────────────────────────────────
            duration_gap    = duration_passif - duration_actif
            # Impact d'un choc de taux +100bp sur le surplus
            # ΔSurplus = -(D_actif × Actif - D_passif × PM) × Δtaux
            # = -(D_gap × PM - (D_actif - D_passif) × (Actif - PM)) × Δtaux
            sensibilite_surplus_100bp = (
                duration_actif * actif_initiale - duration_passif * pm_initiale
            ) * 0.01  # +100bp
            # Si positif : hausse taux → gain actif > perte passif → favorable

            # ── SCÉNARIOS STRESS TAUX EIOPA ───────────────────────────────────
            # Chocs EIOPA : Δtaux (en valeur absolue, toujours positif)
            delta_taux_hausse = +0.02  # +200bp (hausse taux)
            delta_taux_baisse = +0.02  # -200bp en valeur absolue

            # Impact choc hausse +200bp : actif BAISSE (D × A × Δtaux), PM peu impactée
            impact_actif_hausse = -actif_initiale * duration_actif * delta_taux_hausse
            # PM monte légèrement (actualisation au TMG reste fixe) → approximation nulle
            impact_pm_hausse    = 0
            surplus_stress_hausse = (actif_initiale + impact_actif_hausse) - pm_initiale

            # Impact choc baisse : actif monte, PM monte aussi (actualisation taux bas)
            # Impact choc baisse -200bp : actif MONTE, PM MONTE aussi
            impact_actif_baisse = +actif_initiale * duration_actif * delta_taux_baisse
            impact_pm_baisse    = pm_initiale * duration_passif * delta_taux_baisse
            surplus_stress_baisse = (
                (actif_initiale + impact_actif_baisse) -
                (pm_initiale + impact_pm_baisse)
            )

            stress = {
                'choc_plus_200bp': {
                    'impact_actif':   round(impact_actif_hausse, 0),
                    'impact_pm':      0,
                    'surplus_stresse':round(surplus_stress_hausse, 0),
                    'ratio_couv':     round((actif_initiale + impact_actif_hausse) / max(pm_initiale, 1), 4),
                    'label':          'Hausse taux +200bp (risque actif)',
                },
                'choc_moins_200bp': {
                    'impact_actif':   round(impact_actif_baisse, 0),
                    'impact_pm':      round(impact_pm_baisse, 0),
                    'surplus_stresse':round(surplus_stress_baisse, 0),
                    'ratio_couv':     round(
                        (actif_initiale + impact_actif_baisse) /
                        max(pm_initiale + impact_pm_baisse, 1), 4),
                    'label':          'Baisse taux -200bp (risque passif)',
                },
            }

            # ── INDICATEURS GLOBAUX ───────────────────────────────────────────
            ratio_couv_initial = actif_initiale / max(pm_initiale, 1)
            surplus_initial    = actif_initiale - pm_initiale
            nb_annees_negative = sum(1 for p in projection if not p['couv_ok'])
            ratio_couv_final   = projection[-1]['ratio_couv'] if projection else 0

            statut_rag = (
                'ROUGE' if nb_annees_negative > 0 or ratio_couv_initial < 1.0
                else 'AMBRE' if duration_gap > 5 or ratio_couv_final < 1.05
                else 'VERT'
            )

            commentaire = (
                f"{'✅' if statut_rag == 'VERT' else '⚠️' if statut_rag == 'AMBRE' else '❌'} "
                f"ALM Vie — PM {pm_initiale/1e6:.1f}M€ | Actif {actif_initiale/1e6:.1f}M€.\n"
                f"Ratio couverture initial : {ratio_couv_initial:.3f} "
                f"({'✅' if ratio_couv_initial >= 1.0 else '❌'}) | "
                f"Final an {horizon} : {ratio_couv_final:.3f}.\n"
                f"Duration gap : {duration_gap:+.1f} ans "
                f"({'neutre' if abs(duration_gap) <= 2 else 'risque taux significatif'}).\n"
                f"Stress +200bp → surplus {surplus_stress_hausse/1e3:.0f}k€ | "
                f"Stress -200bp → surplus {surplus_stress_baisse/1e3:.0f}k€."
            )

            val_hyp = self._valider_alm(
                ratio_couv_initial, duration_gap, surplus_stress_hausse,
                surplus_stress_baisse, pm_initiale, nb_annees_negative, horizon
            )
            graphiques = {}
            gv = {}
            if generer_graphiques:
                graphiques = self._generer_graphiques(
                    projection, duration_actif, duration_passif,
                    duration_gap, stress, pm_initiale, actif_initiale
                )
                gv = self._graphiques_validation_alm(val_hyp, projection)

            self._sauvegarder({
                'agent': 'V6 Sven', 'pm_initiale': pm_initiale,
                'actif_initiale': actif_initiale, 'duration_gap': duration_gap,
                'ratio_couv_initial': ratio_couv_initial,
            }, audit_id)

            return {
                'success':              True,
                'agent':                'V6 Sven',
                'statut_rag':           statut_rag,
                'pm_initiale':          round(pm_initiale, 0),
                'actif_initiale':       round(actif_initiale, 0),
                'ratio_couv_initial':   round(ratio_couv_initial, 4),
                'surplus_initial':      round(surplus_initial, 0),
                'duration_actif':       duration_actif,
                'duration_passif':      duration_passif,
                'duration_gap':         round(duration_gap, 2),
                'sensibilite_100bp':    round(sensibilite_surplus_100bp, 0),
                'projection':           projection,
                'stress':               stress,
                'nb_annees_deficit':    nb_annees_negative,
                'ratio_couv_final':     round(ratio_couv_final, 4),
                'sources':              sources,
                'commentaire':          commentaire,
                'audit_id':             audit_id,
                'graphiques':           graphiques,
                'validation_alm':       val_hyp,
                'graphiques_validation':gv,
                'erreur':               None,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR V6 : {e}", exc_info=True)
            return {'success': False, 'statut_rag': 'ROUGE',
                    'erreur': str(e), 'audit_id': audit_id}

    # ─── VALIDATION ──────────────────────────────────────────────────────────
    def _valider_alm(self, ratio_couv, duration_gap, stress_hausse,
                     stress_baisse, pm, nb_deficit, horizon) -> Dict:
        """
        H1 — Ratio couverture initial ≥ 1.0 (actifs ≥ PM)
        H2 — Duration gap ∈ [-3, +3] ans (mismatch tolérable)
        H3 — Surplus positif sous les deux chocs EIOPA ±200bp
        """
        # H1
        if ratio_couv >= 1.10:
            h1_s = 'VERT'
            h1_m = f"Ratio couverture = {ratio_couv:.3f} ≥ 1.10 ✅"
            h1_c = "Actifs largement suffisants — marge de sécurité confortable"
        elif ratio_couv >= 1.0:
            h1_s = 'AMBRE'
            h1_m = f"Ratio couverture = {ratio_couv:.3f} ∈ [1.0, 1.1] ⚠️"
            h1_c = "Actifs suffisants mais marge limitée — surveiller trimestriellement"
        else:
            h1_s = 'ROUGE'
            h1_m = f"Ratio couverture = {ratio_couv:.3f} < 1.0 ❌"
            h1_c = "SOUS-COUVERTURE — action immédiate requise (recapitalisation ou cession actifs)"

        # H2
        if abs(duration_gap) <= 2:
            h2_s = 'VERT'
            h2_m = f"Duration gap = {duration_gap:+.1f} ans ∈ [-2, +2] ✅"
            h2_c = "Mismatch actif/passif maîtrisé — risque de taux limité"
        elif abs(duration_gap) <= 4:
            h2_s = 'AMBRE'
            h2_m = f"Duration gap = {duration_gap:+.1f} ans ∈ [-4, +4] ⚠️"
            h2_c = "Mismatch significatif — envisager des swaps de duration ou obligations longues"
        else:
            h2_s = 'ROUGE'
            h2_m = f"Duration gap = {duration_gap:+.1f} ans > 4 ans ❌"
            h2_c = "Mismatch élevé — risque de taux majeur : couverture obligatoire (swaption)"

        # H3
        worst_stress = min(stress_hausse, stress_baisse)
        if worst_stress >= 0:
            h3_s = 'VERT'
            h3_m = f"Surplus positif sous les deux chocs ±200bp ✅ (pire : {worst_stress/1e3:.0f}k€)"
            h3_c = "Résilience aux stress EIOPA confirmée — SCR taux absorbable"
        elif worst_stress >= -pm * 0.05:
            h3_s = 'AMBRE'
            h3_m = f"Surplus négatif sous stress ({worst_stress/1e3:.0f}k€) ⚠️"
            h3_c = "Perte limitée sous stress — renforcer les fonds propres de 5%"
        else:
            h3_s = 'ROUGE'
            h3_m = f"Perte significative sous stress ({worst_stress/1e3:.0f}k€) ❌"
            h3_c = "Exigence SCR taux non couverte — couverture financière obligatoire (ORSA)"

        sts = [h1_s, h2_s, h3_s]
        sg = 'ROUGE' if 'ROUGE' in sts else 'AMBRE' if 'AMBRE' in sts else 'VERT'
        return {
            'h1_couverture':  {'ratio': round(ratio_couv, 4), 'statut': h1_s,
                               'message': h1_m, 'conseil': h1_c,
                               'titre_graphique': f"{'✅' if h1_s=='VERT' else '⚠️' if h1_s=='AMBRE' else '❌'} Couverture = {ratio_couv:.3f}"},
            'h2_duration_gap':{'gap': round(duration_gap, 2), 'statut': h2_s,
                               'message': h2_m, 'conseil': h2_c,
                               'titre_graphique': f"{'✅' if h2_s=='VERT' else '⚠️' if h2_s=='AMBRE' else '❌'} Duration gap = {duration_gap:+.1f} ans"},
            'h3_stress':      {'worst_stress': round(worst_stress, 0), 'statut': h3_s,
                               'message': h3_m, 'conseil': h3_c,
                               'titre_graphique': f"{'✅' if h3_s=='VERT' else '⚠️' if h3_s=='AMBRE' else '❌'} Stress ±200bp : pire = {worst_stress/1e3:.0f}k€"},
            'statut_global': sg,
            'conclusion': {
                'VERT':  '✅ ALM Vie validée — couverture, duration et stress conformes',
                'AMBRE': '⚠️ ALM à surveiller — ajuster duration ou renforcer actifs',
                'ROUGE': '❌ ALM non conforme — action corrective immédiate',
            }[sg],
        }

    # ─── GRAPHIQUES ──────────────────────────────────────────────────────────
    def _generer_graphiques(self, projection, dur_a, dur_p, gap, stress,
                             pm0, actif0) -> Dict:
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; OR='#C9A84C'; BLANC='#F0F4F8'
        GRIS='#8A9AB0'; VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'; BLEU='#3498DB'
        LAYOUT = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                      font=dict(family='Inter', color=BLANC, size=11),
                      margin=dict(l=16, r=16, t=60, b=50), height=300)
        graphiques = {}

        # G1 — Projection PM vs Actifs sur l'horizon
        try:
            annees = [p['annee'] for p in projection]
            pms    = [p['pm'] / 1e6 for p in projection]
            actifs = [p['actif'] / 1e6 for p in projection]
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=annees, y=actifs, name='Actifs',
                mode='lines+markers', line=dict(color=VERT, width=2.5),
                marker=dict(size=6), fill='tozeroy', fillcolor='rgba(46,204,113,0.07)',
                hovertemplate="An %{x}<br>Actifs : %{y:.2f}M€<extra></extra>"))
            fig1.add_trace(go.Scatter(x=annees, y=pms, name='PM (passif)',
                mode='lines+markers', line=dict(color=ROUGE, width=2.5, dash='dash'),
                marker=dict(size=6),
                hovertemplate="An %{x}<br>PM : %{y:.2f}M€<extra></extra>"))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(text="Projection ALM — Actifs vs PM sur l'horizon",
                           font=dict(color=BLANC, size=12), x=0.01),
                xaxis=dict(title='Années', tickfont=dict(color=GRIS)),
                yaxis=dict(title='M€', tickfont=dict(color=GRIS)),
                legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color=BLANC, size=10),
                            orientation='h', yanchor='bottom', y=1.0),
                annotations=[dict(
                    text="💡 La courbe verte (actifs) doit toujours rester au-dessus de la rouge (PM).",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig1.update_layout(**l1)
            graphiques['projection_alm'] = fig1
        except Exception:
            pass

        # G2 — Ratio de couverture annuel
        try:
            ratios = [p['ratio_couv'] for p in projection]
            colors = [VERT if r >= 1.05 else AMBRE if r >= 1.0 else ROUGE for r in ratios]
            fig2 = go.Figure(go.Bar(
                x=annees, y=ratios, marker_color=colors, opacity=0.88, width=0.6,
                text=[f"{r:.3f}" for r in ratios],
                textposition='outside', textfont=dict(color=BLANC, size=9),
                hovertemplate="An %{x}<br>Ratio : %{y:.3f}<extra></extra>",
            ))
            fig2.add_hline(y=1.0, line_color=OR, line_width=2, line_dash='dash',
                           annotation_text='Seuil 1.0 (couverture minimale)',
                           annotation_font=dict(color=OR, size=9))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text="Ratio de couverture Actifs/PM par année",
                           font=dict(color=BLANC, size=12), x=0.01),
                xaxis=dict(title='Années', tickfont=dict(color=GRIS)),
                yaxis=dict(title='Ratio', tickfont=dict(color=GRIS),
                           range=[min(0.9, min(ratios) - 0.05), max(ratios) + 0.1]),
                showlegend=False,
                annotations=[dict(
                    text="💡 Vert ≥ 1.05, orange ∈ [1.0, 1.05), rouge < 1.0 = sous-couverture.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig2.update_layout(**l2)
            graphiques['ratio_couverture'] = fig2
        except Exception:
            pass

        # G3 — Duration gap (barre + seuils)
        try:
            labels = ['Duration Actif', 'Duration Passif', 'Duration Gap']
            vals   = [dur_a, dur_p, abs(gap)]
            cg = VERT if abs(gap) <= 2 else AMBRE if abs(gap) <= 4 else ROUGE
            fig3 = go.Figure(go.Bar(
                x=labels, y=vals, marker_color=[BLEU, OR, cg],
                width=0.4, opacity=0.88,
                text=[f"{dur_a:.1f} ans", f"{dur_p:.1f} ans", f"{gap:+.1f} ans"],
                textposition='outside', textfont=dict(color=BLANC, size=11),
            ))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text=f"Duration gap = {gap:+.1f} ans ({'✅' if abs(gap)<=2 else '⚠️' if abs(gap)<=4 else '❌'})",
                           font=dict(color=cg, size=12), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title='Années', tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 Gap = D_passif − D_actif. Idéal : gap ≈ 0. Gap > 0 → risque baisse taux (passif s'allonge).",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig3.update_layout(**l3)
            graphiques['duration_gap'] = fig3
        except Exception:
            pass

        # G4 — Impact stress ±200bp sur le surplus
        try:
            st_h = stress['choc_plus_200bp']
            st_b = stress['choc_moins_200bp']
            surplus_base = actif0 - pm0
            labels4 = ['Surplus\ncentral', 'Stress\n+200bp', 'Stress\n-200bp']
            vals4   = [surplus_base, st_h['surplus_stresse'], st_b['surplus_stresse']]
            cols4   = [OR,
                       VERT if st_h['surplus_stresse'] >= 0 else ROUGE,
                       VERT if st_b['surplus_stresse'] >= 0 else ROUGE]
            fig4 = go.Figure(go.Bar(
                x=labels4, y=[v / 1e6 for v in vals4],
                marker_color=cols4, width=0.4, opacity=0.88,
                text=[f"{v/1e6:.2f}M€" for v in vals4],
                textposition='outside', textfont=dict(color=BLANC, size=10),
            ))
            fig4.add_hline(y=0, line_color=BLANC, line_width=1.5,
                           line_dash='dot')
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text="Impact stress EIOPA ±200bp sur le surplus Actif − PM",
                           font=dict(color=BLANC, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title='Surplus (M€)', tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 Toutes les barres doivent rester positives. Une barre rouge = besoin de fonds propres supplémentaires.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig4.update_layout(**l4)
            graphiques['stress_surplus'] = fig4
        except Exception:
            pass

        return graphiques

    def _graphiques_validation_alm(self, val, projection) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; BLANC='#F0F4F8'; GRIS='#8A9AB0'
        VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'
        graphiques = {}
        try:
            items = [
                ('H1 — Couverture initiale ≥ 1.0', val['h1_couverture']['statut'],
                 val['h1_couverture']['message'], val['h1_couverture']['conseil']),
                ('H2 — Duration gap ∈ [-2, +2] ans', val['h2_duration_gap']['statut'],
                 val['h2_duration_gap']['message'], val['h2_duration_gap']['conseil']),
                ('H3 — Surplus ≥ 0 sous stress ±200bp', val['h3_stress']['statut'],
                 val['h3_stress']['message'], val['h3_stress']['conseil']),
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
            fig.update_layout(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family='Inter', color=BLANC, size=11),
                margin=dict(l=16, r=16, t=60, b=50), height=260,
                title=dict(text=f"Scorecard ALM Vie — {val['conclusion']}",
                           font=dict(color=cg, size=10), x=0.01),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode='overlay',
                annotations=[dict(
                    text="💡 3 ✅ = ALM Vie validée, défendable devant l'ACPR et le Comité des Risques.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)])
            graphiques['scorecard_alm'] = fig
        except Exception:
            pass
        return graphiques

    def _sauvegarder(self, rapport, audit_id):
        try:
            fpath = os.path.join(self.models_path, f"v6_alm_{audit_id}.json")
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sauvegardé : v6_alm_{audit_id}.json")
        except Exception as e:
            self.logger.warning(f"Sauvegarde V6 : {e}")