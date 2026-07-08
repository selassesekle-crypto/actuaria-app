"""
ActuarIA — Agent V7 : Léa — Analyse Contrats Anciens TMG
Direction Vie & EP-RE | Manager : Sven | Directeur : Paul

Analyse du risque TMG (Taux Minimum Garanti) sur le portefeuille vie :
→ Détection des contrats anciens "underwater" (TMG > rendement actifs)
→ Calcul du coussin de sécurité restant par tranche de TMG
→ Projection du point de rupture (année où le coussin s'épuise)
→ Exigence en capital réglementaire (SCR taux garanti)
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.v7 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent V7 — Analyse Contrats Anciens TMG ActuarIA v1.0")
print("Risque TMG : Underwater · Coussin · Point de rupture · SCR taux")
print("Usage : agent_v7 = AgentV7AnalyseTMG()")
print("        result_v7 = agent_v7.run(tranches_tmg=[{'tmg':0.035,'pm':20e6,'duree':10}])")

# Tables de mortalité officielles — Arrêté du 27 juillet 2006
from direction_vie_epre.services.tables_mortalite_officielles import (
    calculer_annuite_viagere, REFERENCE_REGLEMENTAIRE,
)


class AgentV7AnalyseTMG:
    """
    Agent V7 — Léa : Analyse du risque TMG sur contrats anciens.

    CONTEXTE RÉGLEMENTAIRE :
    ────────────────────────
    Les contrats d'assurance vie souscrits avant 2000 portent souvent
    des TMG (Taux Minimum Garantis) de 3% à 4.5%. Avec la remontée
    des taux depuis 2022, ces contrats redeviennent un enjeu stratégique
    majeur pour la solvabilité des assureurs vie.

    Un contrat est dit "underwater" (sous l'eau) quand :
        TMG > rendement_espéré_actifs

    Dans ce cas, l'assureur perd de l'argent sur chaque euro garanti.

    MÉTHODE :
    ─────────
    Pour chaque tranche de TMG du portefeuille :
    1. Calcul du coussin de sécurité = PM × (rendement_actifs - TMG)
    2. Projection de l'épuisement du coussin (années)
    3. Calcul du SCR taux garanti (stress EIOPA : baisse taux +200bp)
    4. Comparaison avec la PPB disponible comme amortisseur
    """

    def __init__(self, models_path='/tmp/actuaria/models',
                 audit_path='/tmp/actuaria/audit', verbose=True):
        self.models_path = models_path
        self.audit_path  = audit_path
        self.verbose     = verbose
        self.logger      = logging.getLogger('actuaria.v7')
        os.makedirs(models_path, exist_ok=True)
        os.makedirs(audit_path,  exist_ok=True)

    def run(
        self,
        tranches_tmg:       List[Dict]  = None,
        rendement_actifs:   float       = 0.03,
        ppb_disponible:     float       = 2_000_000,
        taux_sans_risque:   float       = 0.03,
        horizon_projection: int         = 10,
        result_v2:          Optional[Dict] = None,
        result_v4:          Optional[Dict] = None,
        generer_graphiques: bool        = True,
    ) -> Dict:
        """
        Analyse le risque TMG du portefeuille.

        Paramètres
        ──────────
        tranches_tmg : list of dict
            Décomposition du portefeuille par tranche de TMG.
            Chaque élément : {
                'tmg'   : float  — taux minimum garanti (ex: 0.035)
                'pm'    : float  — provisions mathématiques de la tranche (€)
                'duree' : int    — durée résiduelle moyenne (années)
                'label' : str    — libellé (optionnel, ex: 'Contrats 1990-2000')
            }

        rendement_actifs : float
            Rendement attendu du portefeuille d'actifs (ex: 0.03 = 3%).

        ppb_disponible : float
            Stock de PPB utilisable comme amortisseur TMG.

        taux_sans_risque : float
            Taux de référence pour le calcul du SCR taux garanti.

        result_v2 : dict, optional
            Résultat V2 — extrait tmg et be_vie si disponible.

        result_v4 : dict, optional
            Résultat V4 — extrait ppb_finale si disponible.
        """
        audit_id = f"V7_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger = self.logger
        if self.verbose:
            logger.info(f"[{audit_id}] Agent V7 démarré | rendement={rendement_actifs*100:.2f}%")

        try:
            # ── Alimentation depuis la chaîne actuarielle ─────────────────────
            sources = {}
            if result_v4 and result_v4.get('success'):
                ppb_disponible = result_v4.get('ppb_finale', ppb_disponible)
                sources['ppb'] = 'V4 Théo (ppb_finale)'
                logger.info(f"[{audit_id}] PPB alimentée depuis V4 : {ppb_disponible/1e3:.0f}k€")

            if result_v2 and result_v2.get('success'):
                tmg_info = result_v2.get('tmg', {})
                if tmg_info.get('valeur', 0) > 0 and not tranches_tmg:
                    tranches_tmg = [{
                        'tmg':   tmg_info['valeur'],
                        'pm':    result_v2.get('be_vie', 50_000_000),
                        'duree': 15,
                        'label': f"Contrats TMG {tmg_info['valeur']*100:.1f}% (depuis V2)",
                    }]
                    sources['tranches'] = 'V2 Kofi (be_vie + tmg)'

            # Tranches par défaut si rien fourni
            if not tranches_tmg:
                tranches_tmg = [
                    {'tmg': 0.045, 'pm': 5_000_000,  'duree': 8,  'label': 'TMG 4.5% (avant 1990)'},
                    {'tmg': 0.035, 'pm': 20_000_000, 'duree': 12, 'label': 'TMG 3.5% (1990-2000)'},
                    {'tmg': 0.025, 'pm': 15_000_000, 'duree': 10, 'label': 'TMG 2.5% (2000-2010)'},
                    {'tmg': 0.005, 'pm': 10_000_000, 'duree': 8,  'label': 'TMG 0.5% (depuis 2023)'},
                ]

            # ── Analyse par tranche TMG ───────────────────────────────────────
            pm_total = sum(t['pm'] for t in tranches_tmg)
            analyses = []
            pm_underwater_total = 0.0
            cout_annuel_total   = 0.0
            scr_taux_total      = 0.0

            for tranche in tranches_tmg:
                tmg   = tranche['tmg']
                pm    = tranche['pm']
                duree = tranche.get('duree', 10)
                label = tranche.get('label', f"TMG {tmg*100:.1f}%")

                # Spread = rendement - TMG
                spread = rendement_actifs - tmg
                underwater = spread < 0

                # Coût annuel du TMG (si underwater)
                cout_annuel = max(0, -spread) * pm  # perte annuelle garantie

                # Coussin de sécurité (PPB allouée proportionnellement)
                ppb_allouee = ppb_disponible * (pm / max(pm_total, 1))

                # Années avant épuisement du coussin
                if cout_annuel > 0 and ppb_allouee > 0:
                    annees_rupture = ppb_allouee / cout_annuel
                else:
                    annees_rupture = float('inf') if not underwater else 0.0

                # Projection du coussin sur l'horizon
                coussin_projection = []
                coussin_courant = ppb_allouee
                for annee in range(1, horizon_projection + 1):
                    coussin_courant = max(0, coussin_courant - cout_annuel)
                    coussin_projection.append(round(coussin_courant, 0))

                # SCR taux garanti (stress EIOPA : baisse taux -200bp)
                # Impact sur la PM quand les taux baissent :
                # ΔSCR = PM × duration × choc_taux
                # duration ≈ duree / (1 + taux_sans_risque)
                duration_mod = duree / max(1 + taux_sans_risque, 0.01)
                choc_taux_eiopa = 0.02  # -200bp (choc standard EIOPA)
                scr_taux = pm * duration_mod * choc_taux_eiopa

                # Statut RAG de la tranche
                if not underwater:
                    rag = 'VERT'
                elif annees_rupture > horizon_projection:
                    rag = 'AMBRE'
                else:
                    rag = 'ROUGE'

                if underwater:
                    pm_underwater_total += pm
                    cout_annuel_total   += cout_annuel
                scr_taux_total += scr_taux

                analyses.append({
                    'label':              label,
                    'tmg_pct':            round(tmg * 100, 2),
                    'pm':                 round(pm, 0),
                    'spread_pct':         round(spread * 100, 2),
                    'underwater':         underwater,
                    'cout_annuel':        round(cout_annuel, 0),
                    'ppb_allouee':        round(ppb_allouee, 0),
                    'annees_rupture':     round(annees_rupture, 1) if annees_rupture != float('inf') else None,
                    'scr_taux':           round(scr_taux, 0),
                    'coussin_projection': coussin_projection,
                    'rag':                rag,
                })

            # ── Indicateurs globaux ───────────────────────────────────────────
            pct_underwater = pm_underwater_total / max(pm_total, 1) * 100
            coussin_total  = ppb_disponible - cout_annuel_total  # résidu N+1

            # Statut global
            nb_rouge = sum(1 for a in analyses if a['rag'] == 'ROUGE')
            nb_ambre = sum(1 for a in analyses if a['rag'] == 'AMBRE')
            if nb_rouge > 0:
                statut_rag = 'ROUGE'
            elif nb_ambre > 0 or pct_underwater > 20:
                statut_rag = 'AMBRE'
            else:
                statut_rag = 'VERT'

            commentaire = (
                f"{'⚠️' if statut_rag != 'VERT' else '✅'} Analyse TMG — "
                f"PM totale : {pm_total/1e6:.1f}M€ | Rendement actifs : {rendement_actifs*100:.2f}%.\n"
                f"Portefeuille underwater : {pm_underwater_total/1e6:.1f}M€ "
                f"({pct_underwater:.1f}% des PM) — Coût annuel : {cout_annuel_total/1e3:.0f}k€.\n"
                f"PPB disponible : {ppb_disponible/1e3:.0f}k€ | "
                f"SCR taux total : {scr_taux_total/1e6:.2f}M€.\n"
                f"Tranches ROUGE : {nb_rouge} | AMBRE : {nb_ambre} | "
                f"VERT : {len(analyses)-nb_rouge-nb_ambre}."
            )

            # ── Validation ────────────────────────────────────────────────────
            val_hyp = self._valider_tmg(
                pct_underwater, ppb_disponible, cout_annuel_total,
                scr_taux_total, pm_total, rendement_actifs
            )

            # ── Graphiques ────────────────────────────────────────────────────
            graphiques = {}
            gv = {}
            if generer_graphiques:
                graphiques = self._generer_graphiques(
                    analyses, rendement_actifs, ppb_disponible,
                    pm_underwater_total, pm_total, horizon_projection
                )
                gv = self._graphiques_validation_tmg(val_hyp, analyses, pm_total)

            self._sauvegarder({
                'agent': 'V7 Léa', 'pm_total': pm_total,
                'pm_underwater': pm_underwater_total,
                'cout_annuel': cout_annuel_total,
                'scr_taux': scr_taux_total,
            }, audit_id)

            return {
                'success':             True,
                'agent':               'V7 Léa',
                'statut_rag':          statut_rag,
                'pm_total':            round(pm_total, 0),
                'pm_underwater':       round(pm_underwater_total, 0),
                'pct_underwater':      round(pct_underwater, 1),
                'cout_annuel_total':   round(cout_annuel_total, 0),
                'ppb_disponible':      round(ppb_disponible, 0),
                'scr_taux_total':      round(scr_taux_total, 0),
                'rendement_actifs':    rendement_actifs,
                'analyses_tranches':   analyses,
                'sources':             sources,
                'commentaire':         commentaire,
                'audit_id':            audit_id,
                'graphiques':          graphiques,
                'validation_tmg':      val_hyp,
                'graphiques_validation': gv,
                'erreur':              None,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR V7 : {e}", exc_info=True)
            return {'success': False, 'statut_rag': 'ROUGE',
                    'erreur': str(e), 'audit_id': audit_id}

    # ─── VALIDATION ──────────────────────────────────────────────────────────
    def _valider_tmg(self, pct_underwater, ppb, cout_annuel,
                     scr_taux, pm_total, rendement) -> Dict:
        """
        H1 — Part du portefeuille underwater ≤ 20% (seuil de vigilance)
        H2 — PPB couvre au moins 3 ans de coût TMG
        H3 — SCR taux ≤ 15% des PM (stress tolérable)
        """
        # H1 — Part underwater
        if pct_underwater <= 10:
            h1_s, h1_m, h1_c = 'VERT', f"Underwater = {pct_underwater:.1f}% ≤ 10% ✅", \
                "Exposition TMG limitée — portefeuille sain"
        elif pct_underwater <= 20:
            h1_s, h1_m, h1_c = 'AMBRE', f"Underwater = {pct_underwater:.1f}% ∈ [10%,20%] ⚠️", \
                "Surveillance TMG renforcée — surveiller l'évolution des taux"
        else:
            h1_s, h1_m, h1_c = 'ROUGE', f"Underwater = {pct_underwater:.1f}% > 20% ❌", \
                "ALERTE TMG — plan d'action requis (revalorisation, rachat incentivé)"

        # H2 — Couverture PPB (années)
        if cout_annuel > 0:
            annees_couverture = ppb / cout_annuel
        else:
            annees_couverture = float('inf')

        if annees_couverture >= 5 or cout_annuel == 0:
            h2_s, h2_m, h2_c = 'VERT', \
                f"PPB couvre {min(annees_couverture, 99):.1f} ans de coût TMG ✅", \
                "PPB suffisante pour absorber le risque TMG à horizon 5 ans"
        elif annees_couverture >= 3:
            h2_s, h2_m, h2_c = 'AMBRE', \
                f"PPB couvre {annees_couverture:.1f} ans ∈ [3,5] ans ⚠️", \
                "Renforcer la PPB ou activer un programme de revalorisation ciblée"
        else:
            h2_s, h2_m, h2_c = 'ROUGE', \
                f"PPB couvre {annees_couverture:.1f} ans < 3 ans ❌", \
                "URGENT — PPB insuffisante, risque de perte nette avant 3 ans"

        # H3 — SCR taux / PM
        ratio_scr = scr_taux / max(pm_total, 1) * 100
        if ratio_scr <= 10:
            h3_s, h3_m, h3_c = 'VERT', f"SCR taux = {ratio_scr:.1f}% PM ≤ 10% ✅", \
                "Exposition taux maîtrisée — sensibilité raisonnable"
        elif ratio_scr <= 15:
            h3_s, h3_m, h3_c = 'AMBRE', f"SCR taux = {ratio_scr:.1f}% PM ∈ [10%,15%] ⚠️", \
                "Sensibilité aux taux élevée — envisager une couverture (swaption)"
        else:
            h3_s, h3_m, h3_c = 'ROUGE', f"SCR taux = {ratio_scr:.1f}% PM > 15% ❌", \
                "SCR taux excessif — mise en place de couvertures obligatoire (ORSA)"

        sts = [h1_s, h2_s, h3_s]
        sg = 'ROUGE' if 'ROUGE' in sts else 'AMBRE' if 'AMBRE' in sts else 'VERT'
        return {
            'h1_underwater': {'pct': round(pct_underwater, 1), 'statut': h1_s,
                              'message': h1_m, 'conseil': h1_c,
                              'titre_graphique': f"{'✅' if h1_s=='VERT' else '⚠️' if h1_s=='AMBRE' else '❌'} Underwater = {pct_underwater:.1f}%"},
            'h2_ppb':        {'annees': round(min(annees_couverture, 99), 1),
                              'statut': h2_s, 'message': h2_m, 'conseil': h2_c,
                              'titre_graphique': f"{'✅' if h2_s=='VERT' else '⚠️' if h2_s=='AMBRE' else '❌'} PPB couvre {min(annees_couverture,99):.1f} ans"},
            'h3_scr':        {'ratio_pct': round(ratio_scr, 1), 'statut': h3_s,
                              'message': h3_m, 'conseil': h3_c,
                              'titre_graphique': f"{'✅' if h3_s=='VERT' else '⚠️' if h3_s=='AMBRE' else '❌'} SCR taux = {ratio_scr:.1f}% PM"},
            'statut_global': sg,
            'conclusion': {
                'VERT':  '✅ Risque TMG maîtrisé — portefeuille, PPB et SCR taux conformes',
                'AMBRE': '⚠️ Risque TMG surveillé — renforcer PPB et suivi trimestriel',
                'ROUGE': '❌ Risque TMG critique — plan d\'action immédiat requis',
            }[sg],
        }

    # ─── GRAPHIQUES ──────────────────────────────────────────────────────────
    def _generer_graphiques(self, analyses, rendement, ppb, pm_uw, pm_tot,
                            horizon) -> Dict:
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

        # G1 — Répartition PM par tranche TMG (underwater vs OK)
        try:
            labels = [a['label'] for a in analyses]
            pms    = [a['pm'] / 1e6 for a in analyses]
            colors = [ROUGE if a['underwater'] else VERT for a in analyses]
            fig1 = go.Figure(go.Bar(
                x=labels, y=pms,
                marker_color=colors, opacity=0.88, width=0.5,
                text=[f"{p:.1f}M€" for p in pms],
                textposition='outside', textfont=dict(color=BLANC, size=9),
                hovertemplate="<b>%{x}</b><br>PM : %{y:.1f}M€<extra></extra>",
            ))
            fig1.add_hline(y=rendement * max(a['pm'] for a in analyses) / 1e6,
                           line_color=OR, line_width=2, line_dash='dash',
                           annotation_text=f"Rendement actifs {rendement*100:.1f}%",
                           annotation_font=dict(color=OR, size=9))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(text=f"PM par tranche TMG — Rouges = underwater (TMG > {rendement*100:.1f}%)",
                           font=dict(color=AMBRE, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title='PM (M€)', tickfont=dict(color=GRIS)),
                showlegend=False,
                annotations=[dict(
                    text="💡 Barres rouges = contrats 'underwater' : le TMG garanti dépasse le rendement actifs.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)],
            ))
            fig1.update_layout(**l1)
            graphiques['repartition_tmg'] = fig1
        except Exception:
            pass

        # G2 — Projection du coussin PPB sur l'horizon
        try:
            annees = list(range(1, horizon + 1))
            fig2 = go.Figure()
            for a in analyses:
                if a['underwater']:
                    c = ROUGE if a['rag'] == 'ROUGE' else AMBRE
                    fig2.add_trace(go.Scatter(
                        x=annees, y=[v / 1e3 for v in a['coussin_projection']],
                        mode='lines+markers',
                        name=a['label'][:25],
                        line=dict(color=c, width=2),
                        marker=dict(size=5),
                        hovertemplate=f"<b>{a['label'][:20]}</b><br>Année %{{x}}<br>Coussin : %{{y:.0f}}k€<extra></extra>",
                    ))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text=f"Projection coussin PPB — Tranches underwater sur {horizon} ans",
                           font=dict(color=AMBRE, size=11), x=0.01),
                xaxis=dict(title='Années', tickfont=dict(color=GRIS), showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(title='Coussin (k€)', tickfont=dict(color=GRIS)),
                legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color=BLANC, size=9),
                            orientation='h', yanchor='bottom', y=1.0),
                annotations=[dict(
                    text="💡 Quand une courbe touche 0, le coussin PPB est épuisé : l'assureur perd de l'argent.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)],
            ))
            fig2.update_layout(**l2)
            graphiques['projection_coussin'] = fig2
        except Exception:
            pass

        # G3 — Spread TMG vs rendement actifs
        try:
            tmgs   = [a['tmg_pct'] for a in analyses]
            spreads = [a['spread_pct'] for a in analyses]
            colors  = [VERT if s >= 0 else ROUGE for s in spreads]
            fig3 = go.Figure(go.Bar(
                x=[a['label'][:20] for a in analyses], y=spreads,
                marker_color=colors, opacity=0.88, width=0.5,
                text=[f"{s:+.2f}%" for s in spreads],
                textposition='outside', textfont=dict(color=BLANC, size=9),
                hovertemplate="<b>%{x}</b><br>Spread : %{y:+.2f}%<extra></extra>",
            ))
            fig3.add_hline(y=0, line_color=OR, line_width=2, line_dash='dash',
                           annotation_text='Seuil 0% (underwater)',
                           annotation_font=dict(color=OR, size=9))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text=f"Spread (rendement {rendement*100:.1f}% - TMG) par tranche",
                           font=dict(color=BLANC, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title='Spread (%)', tickfont=dict(color=GRIS),
                           showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                showlegend=False,
                annotations=[dict(
                    text="💡 Barres vertes = marge positive. Rouges = perte garantie. Plus c'est rouge, plus le risque est élevé.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)],
            ))
            fig3.update_layout(**l3)
            graphiques['spread_tmg'] = fig3
        except Exception:
            pass

        # G4 — Jauge portefeuille underwater
        try:
            pct_uw = pm_uw / max(pm_tot, 1) * 100
            c_uw = VERT if pct_uw <= 10 else AMBRE if pct_uw <= 20 else ROUGE
            fig4 = go.Figure(go.Indicator(
                mode='gauge+number', value=pct_uw,
                number=dict(suffix='% underwater', font=dict(color=c_uw, size=28), valueformat='.1f'),
                title=dict(text=f"Part du portefeuille underwater (TMG > {rendement*100:.1f}%)",
                           font=dict(color=c_uw, size=11)),
                gauge=dict(
                    axis=dict(range=[0, 50], tickfont=dict(color=GRIS, size=8),
                              tickvals=[0, 10, 20, 30, 50],
                              ticktext=['0%', '10%', '20% ⚠️', '30%', '50%']),
                    bar=dict(color=c_uw, thickness=0.25), bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0, 10],  color='rgba(46,204,113,0.12)'),
                        dict(range=[10, 20], color='rgba(243,156,18,0.12)'),
                        dict(range=[20, 50], color='rgba(231,76,60,0.12)'),
                    ],
                    threshold=dict(line=dict(color=AMBRE, width=3), thickness=0.8, value=20),
                ),
            ))
            fig4.update_layout(paper_bgcolor=NAVY, font=dict(color=BLANC),
                               margin=dict(l=30, r=30, t=80, b=50), height=300,
                               annotations=[dict(
                                   text="💡 Seuil de vigilance ACPR : 20% du portefeuille underwater déclenche une surveillance renforcée.",
                                   xref='paper', yref='paper', x=0.5, y=-0.12,
                                   font=dict(color=GRIS, size=9), showarrow=False)])
            graphiques['jauge_underwater'] = fig4
        except Exception:
            pass

        return graphiques

    def _graphiques_validation_tmg(self, val, analyses, pm_total) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; BLANC='#F0F4F8'; GRIS='#8A9AB0'
        VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'
        LAYOUT = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                      font=dict(family='Inter', color=BLANC, size=11),
                      margin=dict(l=16, r=16, t=60, b=50), height=300)
        graphiques = {}
        try:
            items = [
                ('H1 — Part underwater ≤ 20%', val['h1_underwater']['statut'],
                 val['h1_underwater']['message'], val['h1_underwater']['conseil']),
                ('H2 — PPB ≥ 3 ans coût TMG', val['h2_ppb']['statut'],
                 val['h2_ppb']['message'], val['h2_ppb']['conseil']),
                ('H3 — SCR taux ≤ 15% PM', val['h3_scr']['statut'],
                 val['h3_scr']['message'], val['h3_scr']['conseil']),
            ]
            fig = go.Figure()
            for nom, statut, msg, conseil in items:
                c = VERT if statut == 'VERT' else AMBRE if statut == 'AMBRE' else ROUGE
                i = '✅' if statut == 'VERT' else '⚠️' if statut == 'AMBRE' else '❌'
                s = 1.0 if statut == 'VERT' else 0.5 if statut == 'AMBRE' else 0.0
                fig.add_trace(go.Bar(
                    x=[s], y=[nom], orientation='h', marker_color=c, width=0.5,
                    text=f"{i} {statut}", textposition='outside',
                    textfont=dict(color=c, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False,
                ))
            sg = val['statut_global']
            cg = VERT if sg == 'VERT' else AMBRE if sg == 'AMBRE' else ROUGE
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text=f"Scorecard Risque TMG — {val['conclusion']}",
                           font=dict(color=cg, size=10), x=0.01),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode='overlay', height=260,
                annotations=[dict(
                    text="💡 3 ✅ = risque TMG maîtrisé, défendable devant l'ACPR et l'actuaire désigné.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)],
            ))
            fig.update_layout(**l4)
            graphiques['scorecard_tmg'] = fig
        except Exception:
            pass
        return graphiques

    def _sauvegarder(self, rapport, audit_id):
        try:
            fpath = os.path.join(self.models_path, f"v7_tmg_{audit_id}.json")
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sauvegardé : v7_tmg_{audit_id}.json")
        except Exception as e:
            self.logger.warning(f"Sauvegarde V7 : {e}")
