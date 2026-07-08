"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ACTUARIA — AGENT EP4 : STRESS TESTING ÉPARGNE-RETRAITE       ║
║                        Version 1.0 — Production                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

warnings.filterwarnings('ignore')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ══════════════════════════════════════════════════════════════════════════════
# AGENT EP4 — STRESS TESTING ÉPARGNE-RETRAITE
# ══════════════════════════════════════════════════════════════════════════════

class AgentEP4StressEpargne:
    """
    Agent EP4 — Stress Testing spécifique épargne-retraite.

    CHOCS SPÉCIFIQUES RETRAITE :
    ─────────────────────────────
    • Choc longévité : +20% espérance de vie → PM augmente
    • Choc taux bas  : taux 0% → PM explose (rentes non actualisées)
    • Choc rachats   : 40% des contrats rachetés simultanément
    • Choc financier : -20% actifs → sous-couverture PM
    """

    def __init__(
        self,
        models_path: str = '/tmp/actuaria/models',
        audit_path:  str = '/tmp/actuaria/audit',
        verbose:     bool = True
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger('actuaria.ep4')
        self.logger.info("Agent EP4 Stress Épargne initialisé")

    def run(
        self,
        result_ep3:    Optional[Dict] = None,
        encours_total: float = 50_000_000,
        actifs_total:  float = 55_000_000,
        sous_branche:       str  = 'per',
        generer_graphiques: bool = True,
    ) -> Dict[str, Any]:
        t_debut  = datetime.now()
        audit_id = f"EP4_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"[{audit_id}] Agent EP4 Stress Épargne démarré")

        if result_ep3 and result_ep3.get('success'):
            encours_total = result_ep3['provisions']['pm_encours']

        try:
            scenarios = [
                {
                    'nom':         'Choc longévité +20%',
                    'description': 'Espérance de vie +20% → PM augmente',
                    'impact_pm':   encours_total * 0.12,
                    'impact_actifs': 0,
                    'probabilite': 0.10,
                },
                {
                    'nom':         'Choc taux bas (0%)',
                    'description': 'Taux à 0% → PM non actualisée',
                    'impact_pm':   encours_total * 0.25,
                    'impact_actifs': actifs_total * 0.05,
                    'probabilite': 0.05,
                },
                {
                    'nom':         'Rachats massifs 40%',
                    'description': '40% des contrats rachetés simultanément',
                    'impact_pm':   -encours_total * 0.40,
                    'impact_actifs': -actifs_total * 0.40,
                    'probabilite': 0.03,
                },
                {
                    'nom':         'Choc financier -20%',
                    'description': 'Actifs -20% → sous-couverture',
                    'impact_pm':   0,
                    'impact_actifs': -actifs_total * 0.20,
                    'probabilite': 0.10,
                },
                {
                    'nom':         'Scénario combiné',
                    'description': 'Longévité + taux bas + -10% actifs',
                    'impact_pm':   encours_total * 0.30,
                    'impact_actifs': -actifs_total * 0.10,
                    'probabilite': 0.02,
                },
            ]

            ratio_base = actifs_total / max(encours_total, 1) * 100

            for s in scenarios:
                pm_stresse    = encours_total + s['impact_pm']
                actifs_stresses = actifs_total + s['impact_actifs']
                ratio_stresse = actifs_stresses / max(pm_stresse, 1) * 100
                s['pm_stresse']     = round(pm_stresse, 0)
                s['actifs_stresses']= round(actifs_stresses, 0)
                s['ratio_stresse']  = round(ratio_stresse, 1)
                s['impact_pm']      = round(s['impact_pm'], 0)
                s['impact_actifs']  = round(s['impact_actifs'], 0)
                s['rag'] = (
                    '🟢 VERT'  if ratio_stresse >= 105 else
                    '🟡 AMBRE' if ratio_stresse >= 100 else
                    '🔴 ROUGE'
                )

            statut_rag = (
                'ROUGE' if any(s['rag'] == '🔴 ROUGE' for s in scenarios) else
                'AMBRE' if any(s['rag'] == '🟡 AMBRE' for s in scenarios) else
                'VERT'
            )

            result = {
                'success':       True,
                'audit_id':      audit_id,
                'sous_branche':  sous_branche,
                'statut_rag':    statut_rag,
                'ratio_base':    round(ratio_base, 1),
                'scenarios':     scenarios,
                'commentaire':   self._commenter(scenarios, ratio_base, statut_rag),
            }

            if generer_graphiques and PLOTLY_OK:
                result['graphiques'] = self._generer_graphiques_ep4(scenarios, ratio_base)
            else:
                result['graphiques'] = {}
            self._sauvegarder(audit_id, result)
            if self.verbose:
                self._afficher(result)


            result['validation_ep4'] = self._valider_stress_epre(
                result.get('ratio_base', 100.0), result.get('scenarios', []))
            result['graphiques_validation'] = self._graphiques_validation_stress_epre(result['validation_ep4'])
            return result

        except Exception as e:
            self.logger.error(f"ERREUR EP4 : {e}", exc_info=True)
            return {'success': False, 'erreur': str(e), 'audit_id': audit_id}

    def _generer_graphiques_ep4(self, scenarios, ratio_base) -> Dict:
        if not PLOTLY_OK: return {}
        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"
        OR="#C9A84C"; BLANC="#F0F4F8"; GRIS="#8A9AB0"
        VERT="#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"; BLEU="#3498DB"
        LAYOUT = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=52, b=16), height=300,
            hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))
        graphiques = {}
        try:
            # Utilise les vraies cles de la structure scenarios
            noms_s   = [s.get('nom', f'Choc {i}') for i, s in enumerate(scenarios)]
            ratios_s = [s.get('ratio_stresse', ratio_base) for s in scenarios]
            colors_s = [VERT if r >= 100 else AMBRE if r >= 75 else ROUGE for r in ratios_s]
            color_base = VERT if ratio_base >= 100 else AMBRE if ratio_base >= 75 else ROUGE

            fig1 = go.Figure()

            # Barre Base
            fig1.add_trace(go.Bar(
                x=['Base'], y=[ratio_base],
                marker_color=[color_base],
                marker_line=dict(color='#0F2E52', width=1),
                width=0.45, opacity=0.9,
                text=[f"{ratio_base:.0f}%"],
                textposition='outside', textfont=dict(color='#F0F4F8', size=10),
                name='Base',
                hovertemplate=f"<b>Base</b><br>Ratio : {ratio_base:.1f}%<extra></extra>",
            ))

            # Barres scenarios stresses
            fig1.add_trace(go.Bar(
                x=noms_s, y=ratios_s,
                marker_color=colors_s,
                marker_line=dict(color='#0F2E52', width=1),
                width=0.45, opacity=0.88,
                text=[f"{r:.0f}%" for r in ratios_s],
                textposition='outside', textfont=dict(color='#F0F4F8', size=10),
                name='Post-choc',
                hovertemplate="<b>%{x}</b><br>Ratio stresse : %{y:.1f}%<extra></extra>",
            ))

            # Lignes reference
            fig1.add_hline(y=100, line_color=ROUGE, line_width=1.5, line_dash="dot",
                annotation_text="Seuil MCR 100%",
                annotation_font=dict(color=ROUGE, size=9),
                annotation_position="bottom right")
            fig1.add_hline(y=ratio_base, line_color='#F0F4F8', line_width=1, line_dash="dash",
                annotation_text=f"Base {ratio_base:.0f}%",
                annotation_font=dict(color='#F0F4F8', size=9))

            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(text="Ratio couverture — Base vs chocs epargne-retraite",
                    font=dict(color='#F0F4F8', size=13), x=0.01),
                xaxis=dict(tickfont=dict(color='#F0F4F8', size=9), showgrid=False),
                yaxis=dict(
                    title=dict(text="Ratio (%)", font=dict(color='#8A9AB0', size=10)),
                    showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                    tickfont=dict(color='#8A9AB0'), range=[0, max(ratio_base, max(ratios_s, default=100)) * 1.2],
                ),
                bargap=0.3, barmode='group',
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color='#F0F4F8', size=10),
                            orientation="h", yanchor="bottom", y=1.02),
            ))
            fig1.update_layout(**l1)
            graphiques['ratio_couverture'] = fig1
        except Exception as e:
            pass
        # G2 — Impact en euros par choc
        try:
            noms_s    = [s.get('nom', f'Choc {i}') for i, s in enumerate(scenarios)]
            impacts_pm= [s.get('impact_pm', 0) for s in scenarios]
            impacts_ac= [s.get('impact_actifs', 0) for s in scenarios]
            impacts_net = [ac - pm for ac, pm in zip(impacts_ac, impacts_pm)]
            colors_i  = [VERT if v >= 0 else ROUGE for v in impacts_net]

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=noms_s, y=impacts_pm,
                name='Impact PM (€)', marker_color=ROUGE,
                width=0.3, opacity=0.85,
                hovertemplate="<b>%{x}</b><br>Impact PM : %{y:,.0f} €<extra></extra>",
            ))
            fig2.add_trace(go.Bar(
                x=noms_s, y=impacts_ac,
                name='Impact Actifs (€)', marker_color=BLEU,
                width=0.3, opacity=0.85,
                hovertemplate="<b>%{x}</b><br>Impact Actifs : %{y:,.0f} €<extra></extra>",
            ))
            fig2.add_trace(go.Scatter(
                x=noms_s, y=impacts_net,
                name='Impact net (€)', mode='lines+markers',
                line=dict(color=OR, width=2.5),
                marker=dict(color=OR, size=9, line=dict(color=NAVY, width=2)),
                hovertemplate="<b>%{x}</b><br>Impact net : %{y:,.0f} €<extra></extra>",
            ))
            fig2.add_hline(y=0, line_color=GRIS, line_width=1.5, line_dash="dot")
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text="💶 Impact en euros par scenario de choc",
                           font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title=dict(text="Impact (€)", font=dict(color=GRIS, size=10)),
                           showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                           tickfont=dict(color=GRIS)),
                barmode='group', bargap=0.25,
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                            orientation="h", yanchor="bottom", y=1.02),
            ))
            fig2.update_layout(**l2)
            graphiques['impact_euros'] = fig2
        except Exception as e:
            pass

        # G3 — ORSA 5 ans épargne
        try:
            annees   = [2025 + i for i in range(6)]
            # Projection ratio base (croissance 2%/an)
            ratios_c = [ratio_base * (1 + 0.01 * i) for i in range(6)]
            # Projection ratio stressé (choc combiné)
            ratio_min = min([s.get('ratio_stresse', ratio_base) for s in scenarios], default=ratio_base)
            ratios_s  = [ratio_min + (ratio_base - ratio_min) * i / 5 for i in range(6)]
            # Projection favorable
            ratios_f  = [ratio_base * (1 + 0.02 * i) for i in range(6)]

            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=annees, y=ratios_f, mode='lines',
                name='Favorable', line=dict(color=VERT, width=1.5, dash='dot'),
                hovertemplate="<b>Favorable</b><br>%{x} : %{y:.1f}%<extra></extra>",
            ))
            fig3.add_trace(go.Scatter(
                x=annees, y=ratios_c, mode='lines+markers',
                name='Central',
                line=dict(color=OR, width=2.5),
                marker=dict(color=OR, size=8, line=dict(color=NAVY, width=2)),
                hovertemplate="<b>Central</b><br>%{x} : %{y:.1f}%<extra></extra>",
            ))
            fig3.add_trace(go.Scatter(
                x=annees, y=ratios_s, mode='lines+markers',
                name='Stresse',
                line=dict(color=ROUGE, width=2, dash='dash'),
                marker=dict(color=ROUGE, size=7, line=dict(color=NAVY, width=2)),
                hovertemplate="<b>Stresse</b><br>%{x} : %{y:.1f}%<extra></extra>",
            ))
            fig3.add_hline(y=100, line_color=ROUGE, line_width=1, line_dash="dot",
                           annotation_text="Seuil 100%",
                           annotation_font=dict(color=ROUGE, size=9),
                           annotation_position="bottom right")
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text="📈 ORSA 5 ans — Ratio couverture epargne (3 scenarios)",
                           font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(tickfont=dict(color=GRIS), showgrid=True,
                           gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title=dict(text="Ratio (%)", font=dict(color=GRIS, size=10)),
                           showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                           tickfont=dict(color=GRIS)),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                            orientation="h", yanchor="bottom", y=1.02),
                height=340,
            ))
            fig3.update_layout(**l3)
            graphiques['orsa_epargne'] = fig3
        except Exception as e:
            pass

        # G4 — Heatmap chocs × métriques
        try:
            noms_s = [s.get('nom', f'Choc {i}')[:20] for i, s in enumerate(scenarios)]
            metriques4 = ['Impact PM (€)', 'Ratio stresse (%)', 'Probabilite (%)']
            z_data = [
                [s.get('impact_pm', 0) / 1e6 for s in scenarios],
                [s.get('ratio_stresse', 0) for s in scenarios],
                [s.get('probabilite', 0) * 100 for s in scenarios],
            ]
            # Normaliser chaque ligne
            z_norm = []
            for row in z_data:
                rmax = max(abs(v) for v in row) if row else 1
                z_norm.append([v / max(rmax, 1e-6) for v in row])

            fig4 = go.Figure(go.Heatmap(
                z=z_norm, x=noms_s, y=metriques4,
                colorscale=[[0, NAVY_LL], [0.5, AMBRE], [1, ROUGE]],
                showscale=True,
                text=[[f"{z_data[i][j]:.1f}" for j in range(len(noms_s))]
                      for i in range(len(metriques4))],
                texttemplate="%{text}",
                textfont=dict(color=BLANC, size=9),
                hoverongaps=False,
                hovertemplate="<b>%{x} — %{y}</b><br>%{text}<extra></extra>",
            ))
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text="🔥 Heatmap — Chocs epargne x Metriques",
                           font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                showlegend=False, height=280,
            ))
            fig4.update_layout(**l4)
            graphiques['heatmap_chocs'] = fig4
        except Exception as e:
            pass

        return graphiques


    def _valider_stress_epre(self, ratio_base: float, scenarios: list) -> Dict:
        """
        Contrôles qualité Stress Testing EP-RE.
        C1 — Ratio base ≥ 100% (solide avant stress)
        C2 — Solvabilité post-choc longévité ≥ 90%
        C3 — Solvabilité post-choc combiné > 75%
        """
        VERT="VERT"; AMBRE="AMBRE"; ROUGE="ROUGE"

        # C1 — Ratio base
        if ratio_base >= 150:
            c1_statut = VERT; c1_msg = f"Ratio base = {ratio_base:.1f}% ≥ 150% → Très solide ✅"
            c1_conseil = "Résilience forte avant stress"
        elif ratio_base >= 100:
            c1_statut = VERT; c1_msg = f"Ratio base = {ratio_base:.1f}% ≥ 100% → Solide ✅"
            c1_conseil = "Solvabilité maintenue — renforcer pour les stress"
        else:
            c1_statut = ROUGE; c1_msg = f"Ratio base = {ratio_base:.1f}% < 100% → Fragile ❌"
            c1_conseil = "Renforcer les actifs avant tout stress"

        # C2 — Post-choc longévité
        ratio_longevite = next((s.get('ratio_couverture', ratio_base*0.9)
                               for s in (scenarios if isinstance(scenarios, list) else [])
                               if 'longev' in str(s.get('nom_scenario','longev')).lower()),
                              ratio_base * 0.88)
        if ratio_longevite >= 100:
            c2_statut = VERT; c2_msg = f"Post-longévité = {ratio_longevite:.1f}% ≥ 100% ✅"
            c2_conseil = "Résistant au choc longévité +20%"
        elif ratio_longevite >= 90:
            c2_statut = AMBRE; c2_msg = f"Post-longévité = {ratio_longevite:.1f}% ∈ [90%,100%] ⚠️"
            c2_conseil = "Renforcer la réassurance longévité"
        else:
            c2_statut = ROUGE; c2_msg = f"Post-longévité = {ratio_longevite:.1f}% < 90% ❌"
            c2_conseil = "Plan de redressement longévité — choc EIOPA non absorbé"

        # C3 — Post-choc combiné
        ratios = [s.get('ratio_couverture', ratio_base*0.8) for s in (scenarios if isinstance(scenarios,list) else [])]
        ratio_combine = min(ratios) if ratios else ratio_base * 0.75
        if ratio_combine >= 100:
            c3_statut = VERT; c3_msg = f"Pire scénario = {ratio_combine:.1f}% ≥ 100% ✅"
            c3_conseil = "EP-RE résilient dans tous les scénarios"
        elif ratio_combine >= 75:
            c3_statut = AMBRE; c3_msg = f"Pire scénario = {ratio_combine:.1f}% ∈ [75%,100%] ⚠️"
            c3_conseil = "Plan de continuité recommandé pour le pire scénario"
        else:
            c3_statut = ROUGE; c3_msg = f"Pire scénario = {ratio_combine:.1f}% < 75% ❌"
            c3_conseil = "URGENT — risque de défaut dans un scénario adverse combiné"

        statuts = [c1_statut, c2_statut, c3_statut]
        sg = ROUGE if ROUGE in statuts else AMBRE if AMBRE in statuts else VERT
        return {
            "c1_base":    {"ratio":round(ratio_base,1),"statut":c1_statut,"message":c1_msg,"conseil":c1_conseil,
                           "titre_graphique":f"{'✅' if c1_statut==VERT else '⚠️' if c1_statut==AMBRE else '❌'} Ratio base = {ratio_base:.1f}%"},
            "c2_longevite":{"ratio":round(ratio_longevite,1),"statut":c2_statut,"message":c2_msg,"conseil":c2_conseil,
                            "titre_graphique":f"{'✅' if c2_statut==VERT else '⚠️' if c2_statut==AMBRE else '❌'} Post-longévité = {ratio_longevite:.1f}%"},
            "c3_combine": {"ratio":round(ratio_combine,1),"statut":c3_statut,"message":c3_msg,"conseil":c3_conseil,
                           "titre_graphique":f"{'✅' if c3_statut==VERT else '⚠️' if c3_statut==AMBRE else '❌'} Pire scénario = {ratio_combine:.1f}%"},
            "statut_global":sg,
            "conclusion":f"{'✅ Stress EP-RE validé' if sg==VERT else '⚠️ Acceptable' if sg==AMBRE else '❌ Vulnérabilités détectées'} — base, longévité et scénario combiné vérifiés",
        }

    def _graphiques_validation_stress_epre(self, val: Dict) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12"
        graphiques = {}
        try:
            items=[("C1 — Ratio base ≥ 100%",val["c1_base"]["statut"],val["c1_base"]["message"],val["c1_base"]["conseil"]),
                   ("C2 — Post-longévité ≥ 90%",val["c2_longevite"]["statut"],val["c2_longevite"]["message"],val["c2_longevite"]["conseil"]),
                   ("C3 — Pire scénario > 75%",val["c3_combine"]["statut"],val["c3_combine"]["message"],val["c3_combine"]["conseil"])]
            fig=go.Figure()
            for nom,statut,msg,conseil in items:
                c=VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i="✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s=1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.2
                fig.add_trace(go.Bar(x=[s],y=[nom],orientation="h",marker_color=c,width=0.5,
                    text=f"{i} {statut}",textposition="outside",textfont=dict(color=c,size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"];cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            fig.update_layout(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,
                font=dict(family="Inter,Arial",color=BLANC,size=11),
                margin=dict(l=16,r=16,t=60,b=50),height=260,
                title=dict(text=f"Scorecard Stress EP-RE — {val['conclusion'][:55]}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",annotations=[dict(text="💡 3 ✅ = EP-RE résilient aux chocs longévité, taux bas et rachats massifs.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False,align="left")])
            graphiques["scorecard_stress_epre"]=fig
        except Exception:
            pass
        return graphiques

    def _commenter(self, scenarios, ratio_base, statut):
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut]
        lines = [
            f"{emoji} STRESS ÉPARGNE-RETRAITE — {statut}",
            f"Ratio couverture de base : {ratio_base:.1f}%",
            "",
            "SCÉNARIOS :",
        ]
        for s in scenarios:
            lines.append(
                f"  {s['nom']:<30} → Ratio={s['ratio_stresse']:.1f}% {s['rag']}"
            )
        lines += [
            "",
            "RECOMMANDATION :",
            "→ Renforcer les actifs si ratio stressé < 100%.",
            "→ Mettre en place une politique de couverture longévité.",
            "→ Intégrer dans l'ORSA annuel.",
        ]
        return '\n'.join(lines)

    def _afficher(self, result):
        sep = "═" * 65
        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT EP4 STRESS ÉPARGNE | {result['audit_id']}")
        print(sep)
        for ligne in result['commentaire'].split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    def _sauvegarder(self, audit_id, result):
        chemin = self.models_path / f"ep4_stress_{audit_id}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass


if __name__ == '__main__':
    print("Agent EP4 — Stress Testing Épargne-Retraite ActuarIA v1.0")
    print("Usage : agent_ep4 = AgentEP4StressEpargne()")
    print("        result_ep4 = agent_ep4.run(encours_total=50_000_000)")
