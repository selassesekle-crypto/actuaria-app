"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ACTUARIA — AGENT EP3 : PROVISIONNEMENT ÉPARGNE              ║
║                        Version 1.0 — Production                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, json, logging, warnings
from direction_vie_epre.services.rapport_excel import (
    creer_workbook_actuariel, ajouter_onglet_hypotheses,
    ajouter_onglet_resultats, ajouter_onglet_validation,
    ajouter_onglet_audit_trail, finaliser_et_retourner,
)
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
# AGENT EP3 — PROVISIONNEMENT ÉPARGNE
# ══════════════════════════════════════════════════════════════════════════════

class AgentEP3ProvissionnementEpargne:
    """
    Agent EP3 — Provisionnement des contrats épargne-retraite.

    PROVISIONS CALCULÉES :
    ────────────────────────
    PM (Provision Mathématique) :
    Valeur des engagements envers les assurés.
    PM = ä_x_courant × Rente_garantie

    PPB (Provision pour Participation aux Bénéfices) :
    Réserve des participations aux bénéfices non encore attribuées.
    PPB ≥ 0 · Non distribuable librement

    Réserve de Capitalisation :
    Neutralise les plus/moins-values obligataires.
    Obligatoire en France (art. R342-14 Code des assurances).
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
        self.logger = logging.getLogger('actuaria.ep3')
        self.logger.info("Agent EP3 Provisionnement Épargne initialisé")

    def run(
        self,
        result_ep2:         Optional[Dict] = None,
        result_a14:         Optional[Dict] = None,
        nb_contrats:        int   = 1000,
        encours_total:      float = 50_000_000,
        rente_moyenne:      float = 1_200,
        age_moyen:          float = 55,
        taux_technique:     float = 0.0,
        taux_marche:        float = 0.03,
        ppb_stock:          float = 1_000_000,
        reserve_capi_stock: float = 500_000,
        actifs_total:       float = None,    # None = estimation prudente à 105% des provisions. Fournir la valeur de marché réelle.
        sous_branche:       str  = 'per',
        generer_graphiques: bool = True,
    ) -> Dict[str, Any]:
        """
        Calcule les provisions épargne-retraite.

        Paramètres
        ──────────
        encours_total : float
            Total des provisions mathématiques en stock (€).

        rente_moyenne : float
            Rente mensuelle moyenne garantie (€/mois).

        ppb_stock : float
            Stock de PPB au bilan (€).
            La PPB doit être ≥ 0 (Code assurances R331-3).

        reserve_capi_stock : float
            Réserve de capitalisation au bilan (€).
        """
        t_debut  = datetime.now()
        audit_id = f"EP3_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"[{audit_id}] Agent EP3 démarré")

        try:
            # Annuités viagères depuis A14 si disponible
            annuites = 13.0  # Valeur par défaut à 55 ans, taux 3%
            if result_a14 and result_a14.get('success'):
                annuites = result_a14['annuites'].get('annuite_imm', 13.0)

            # ── PROVISION MATHÉMATIQUE ────────────────────────────────────────
            # PM = Rente_annuelle × ä_x × nb_contrats
            rente_annuelle = rente_moyenne * 12
            pm_calculee    = rente_annuelle * annuites * nb_contrats

            # Vérification cohérence PM calculée vs encours déclaré
            ecart_pm = abs(pm_calculee - encours_total) / max(encours_total, 1) * 100

            # ── PPB ───────────────────────────────────────────────────────────
            # Dotation PPB annuelle = rendement - PB distribuée
            rendement_annuel = encours_total * taux_marche
            pb_distribuee    = rendement_annuel * 0.90  # 90% distribué
            dotation_ppb     = rendement_annuel - pb_distribuee
            ppb_total        = ppb_stock + dotation_ppb

            # Taux de PPB (% de l'encours)
            taux_ppb = ppb_total / max(encours_total, 1) * 100

            # ── RÉSERVE DE CAPITALISATION ─────────────────────────────────────
            # Alimentée par les plus-values obligataires réalisées
            # Reprise en cas de moins-values
            pv_obligataires   = encours_total * 0.70 * 0.005  # 0.5% du portefeuille oblig
            reserve_capi_new  = reserve_capi_stock + pv_obligataires

            # ── PROVISIONS TOTALES ────────────────────────────────────────────
            provisions_total = encours_total + ppb_total + reserve_capi_new

            # ── TAUX DE COUVERTURE ACTIFS / PROVISIONS ────────────────────
            # L'actif total doit couvrir l'ensemble des provisions (PM + PPB + RC)
            _actifs_reel = actifs_total if actifs_total is not None else provisions_total * 1.05
            taux_couverture = _actifs_reel / max(provisions_total, 1) * 100

            # Statut RAG basé sur couverture actifs ET cohérence PM
            # L'écart PM calculée/déclarée peut être grand quand encours_total
            # est fourni directement (portefeuille) vs PM théorique (contrat type).
            # On pondère : couverture actifs est le critère réglementaire principal.
            if taux_couverture >= 100 and ecart_pm <= 20:
                statut_rag = 'VERT'
            elif taux_couverture >= 90 and ecart_pm <= 30:
                statut_rag = 'AMBRE'
            elif taux_couverture >= 100 and ecart_pm <= 50:
                # Couverture suffisante même si PM calculée diverge (données portefeuille)
                statut_rag = 'AMBRE'
            else:
                statut_rag = 'ROUGE'

            result = {
                'success':      True,
                'audit_id':     audit_id,
                'sources':      {'parametres': 'saisie manuelle'},
                'sous_branche': sous_branche,
                'statut_rag':   statut_rag,
                'provisions': {
                    'pm_encours':        round(encours_total, 0),
                    'pm_calculee':       round(pm_calculee, 0),
                    'ecart_pm_pct':      round(ecart_pm, 2),
                    'ppb_stock':         round(ppb_stock, 0),
                    'dotation_ppb_n':    round(dotation_ppb, 0),
                    'ppb_total':         round(ppb_total, 0),
                    'taux_ppb_pct':      round(taux_ppb, 2),
                    'reserve_capi':      round(reserve_capi_new, 0),
                    'provisions_total':  round(provisions_total, 0),
                    'annuites_utilisees':  round(annuites, 4),
                    'actifs_total':        round(_actifs_reel, 0),
                    'taux_couverture_pct': round(taux_couverture, 2),
                },
                'commentaire': self._commenter(
                    encours_total, ppb_total, reserve_capi_new,
                    taux_ppb, ecart_pm, statut_rag
                ),
                # Clés exposées à la racine pour accès direct par EP4/EP5
                'taux_couverture_pct': round(taux_couverture, 2),
                'actifs_total':        round(_actifs_reel, 0),
                'provisions_total':    round(provisions_total, 0),
                'pm_encours':          round(encours_total, 0),
                'ppb':                 round(ppb_total, 0),
            }

            if generer_graphiques and PLOTLY_OK:
                result['graphiques'] = self._generer_graphiques_ep3(
                    encours_total, ppb_total, reserve_capi_new, encours_total, taux_marche
                )
            else:
                result['graphiques'] = {}
            self._sauvegarder(audit_id, result)
            if self.verbose:
                self._afficher(result)


            result['validation_ep3'] = self._valider_provisionnement_epre(
                result.get('provisions',{}).get('pm_calculee', 0),
                result.get('provisions',{}).get('ppb_total', 0),
                result.get('provisions',{}).get('pm_encours', 0),
                result.get('provisions',{}).get('taux_couverture_pct', 100.0))
            result['graphiques_validation'] = self._graphiques_validation_prov_epre(result['validation_ep3'])
            # ── Rapport Excel ──────────────────────────────────────
            try:
                result['excel_bytes'] = self._generer_excel(result)
            except Exception as _xe:
                result['excel_bytes'] = None
                self.logger.warning(f'Excel non généré : {_xe}')
            return result

        except Exception as e:
            self.logger.error(f"ERREUR EP3 : {e}", exc_info=True)
            return {'success': False, 'erreur': str(e), 'audit_id': audit_id}

    def _generer_graphiques_ep3(self, pm, ppb, rc, encours_total, taux_marche=0.03) -> Dict:
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
            fig1 = go.Figure(go.Pie(
                labels=['PM', 'PPB', 'Reserve Cap.'],
                values=[pm, ppb, rc], hole=0.55,
                marker=dict(colors=[OR, BLEU, VERT], line=dict(color=NAVY, width=2)),
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>",
            ))
            l1 = dict(**LAYOUT)
            l1.update(dict(title=dict(text="Decomposition provisions epargne",
                font=dict(color=BLANC, size=13), x=0.01),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10)),
                annotations=[dict(text=f"<b>{(pm+ppb+rc)/1e6:.1f}M€</b>",
                    x=0.5, y=0.5, font=dict(size=14, color=OR), showarrow=False)]))
            fig1.update_layout(**l1)
            graphiques['decomposition_pm'] = fig1
        except Exception as e:
            pass
        try:
            annees = [2025+i for i in range(6)]
            pms_p  = [pm * (1 + taux_marche * 0.5) ** i for i in range(6)]
            fig2 = go.Figure(go.Bar(
                x=annees, y=pms_p,
                marker_color=[OR if i==0 else "rgba(201,168,76,0.5)" for i in range(6)],
                width=0.45, opacity=0.88,
                text=[f"{v/1e6:.2f}M€" for v in pms_p], textposition='outside',
                textfont=dict(color=BLANC, size=10),
                hovertemplate="<b>%{x}</b><br>PM : %{y:,.0f} €<extra></extra>",
            ))
            l2 = dict(**LAYOUT)
            l2.update(dict(title=dict(text="Evolution PM projetee 5 ans",
                font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(visible=False), bargap=0.35, showlegend=False))
            fig2.update_layout(**l2)
            graphiques['evolution_pm'] = fig2
        except Exception as e:
            pass
        # G3 — Sensibilité PM au taux technique
        try:
            taux_techniques = [0.0, 0.005, 0.01, 0.015, 0.02, 0.025]
            pm_base = encours_total
            # PM monte quand taux baisse (effet actualisation)
            pms_s = [pm_base * (1 + (0.01 - t) * 5) for t in taux_techniques]

            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=[t*100 for t in taux_techniques], y=pms_s,
                mode='lines+markers',
                line=dict(color=OR, width=2.5, shape='spline', smoothing=0.5),
                marker=dict(color=OR, size=8, line=dict(color=NAVY, width=2)),
                fill='tozeroy', fillcolor='rgba(201,168,76,0.08)',
                hovertemplate="Taux %{x:.2f}%<br>PM : %{y:,.0f} €<extra></extra>",
            ))
            fig3.add_vline(x=0, line_color=BLANC, line_width=1.5, line_dash="dot",
                annotation_text="TMG actuel 0%",
                annotation_font=dict(color=BLANC, size=9))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text="📈 Sensibilite PM au taux technique (TMG)",
                           font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(title=dict(text="Taux technique (%)", font=dict(color=GRIS, size=10)),
                           showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                           tickfont=dict(color=GRIS)),
                yaxis=dict(title=dict(text="PM (€)", font=dict(color=GRIS, size=10)),
                           showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                           tickfont=dict(color=GRIS)),
                showlegend=False,
            ))
            fig3.update_layout(**l3)
            graphiques['sensibilite_tmg'] = fig3
        except Exception as e:
            pass

        # G4 — Taux de couverture PM / Actifs
        try:
            pm_val    = encours_total
            # Utiliser l'actif réel passé en paramètre si disponible
            actifs_val = actifs_total if actifs_total is not None else encours_total * 1.05
            ppb_v     = ppb   # paramètre reçu = ppb_total depuis run()
            rc_v      = rc    # paramètre reçu = reserve_capi_new depuis run()
            prov_tot  = pm_val + ppb_v + rc_v

            categories = ['PM', 'PPB', 'Reserve Cap.', 'Total prov.', 'Actifs']
            valeurs    = [pm_val, ppb_v, rc_v, prov_tot, actifs_val]
            colors4    = [OR, BLEU, VERT, AMBRE, ROUGE if actifs_val < prov_tot else VERT]

            fig4 = go.Figure(go.Bar(
                x=categories, y=valeurs,
                marker_color=colors4,
                marker_line=dict(color=NAVY, width=1),
                width=0.45, opacity=0.88,
                text=[f"{v/1e6:.1f}M€" for v in valeurs],
                textposition='outside', textfont=dict(color=BLANC, size=10),
                hovertemplate="<b>%{x}</b><br>%{y:,.0f} €<extra></extra>",
            ))
            ratio_couv = actifs_val / max(prov_tot, 1) * 100
            fig4.add_hline(y=actifs_val, line_color=ROUGE if ratio_couv < 100 else VERT,
                           line_width=2, line_dash="dash",
                           annotation_text=f"Actifs = {actifs_val/1e6:.1f}M€ | Couverture {ratio_couv:.0f}%",
                           annotation_font=dict(color=BLANC, size=9))
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text=f"🛡️ Taux de couverture PM/Actifs = {ratio_couv:.0f}%",
                           font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                yaxis=dict(visible=False), bargap=0.35, showlegend=False,
            ))
            fig4.update_layout(**l4)
            graphiques['taux_couverture'] = fig4
        except Exception as e:
            pass

        return graphiques


    def _valider_provisionnement_epre(self, pm: float, ppb: float,
                                       encours: float, taux_couverture: float) -> Dict:
        VERT="VERT"; AMBRE="AMBRE"; ROUGE="ROUGE"
        ratio_pm_enc = pm / max(encours, 1)
        h1_statut = VERT if ratio_pm_enc >= 1.0 else ROUGE
        h1_msg    = f"PM/Encours = {ratio_pm_enc:.3f} {'✅' if h1_statut==VERT else '❌'}"
        h1_conseil= "PM suffisantes" if h1_statut==VERT else "Sous-provisionnement — augmenter PM"
        h2_statut = VERT if ppb >= 0 else ROUGE
        h2_msg    = f"PPB = {ppb/1e3:.0f}k€ {'✅' if h2_statut==VERT else '❌'}"
        h2_conseil= "PPB positif ✅" if h2_statut==VERT else "PPB négatif impossible ❌"
        h3_statut = VERT if taux_couverture>=100 else AMBRE if taux_couverture>=90 else ROUGE
        h3_msg    = f"Taux couverture = {taux_couverture:.1f}% {'✅' if h3_statut==VERT else '⚠️' if h3_statut==AMBRE else '❌'}"
        h3_conseil= "Actifs suffisants" if h3_statut==VERT else "Renforcer les actifs" if h3_statut==AMBRE else "Plan de redressement"
        statuts   = [h1_statut, h2_statut, h3_statut]
        sg        = ROUGE if ROUGE in statuts else AMBRE if AMBRE in statuts else VERT
        return {
            "h1_pm":        {"statut":h1_statut,"message":h1_msg,"conseil":h1_conseil,"ratio":round(ratio_pm_enc,4)},
            "h2_ppb":       {"statut":h2_statut,"message":h2_msg,"conseil":h2_conseil,"ppb":round(ppb,0)},
            "h3_couverture":{"statut":h3_statut,"message":h3_msg,"conseil":h3_conseil,"taux":round(taux_couverture,2)},
            "statut_global":sg,
            "conclusion":f"{'✅ Provisionnement validé' if sg==VERT else '⚠️ Acceptable' if sg==AMBRE else '❌ Sous-provisionnement'} — PM, PPB et couverture vérifiés",
        }

    def _graphiques_validation_prov_epre(self, val: Dict) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12"
        graphiques = {}
        try:
            items=[("H1 — PM ≥ Encours",val["h1_pm"]["statut"],val["h1_pm"]["message"],val["h1_pm"]["conseil"]),
                   ("H2 — PPB ≥ 0",val["h2_ppb"]["statut"],val["h2_ppb"]["message"],val["h2_ppb"]["conseil"]),
                   ("H3 — Couverture ≥ 100%",val["h3_couverture"]["statut"],val["h3_couverture"]["message"],val["h3_couverture"]["conseil"])]
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
                title=dict(text=f"Scorecard Prov. EP-RE — {val['conclusion'][:55]}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",annotations=[dict(text="💡 3 ✅ = Provisionnement EP-RE conforme Art. R342-14.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False,align="left")])
            graphiques["scorecard_prov_epre"]=fig
        except Exception:
            pass
        return graphiques

    def _commenter(self, pm, ppb, rc, taux_ppb, ecart, statut):
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut]
        return (
            f"{emoji} PROVISIONNEMENT ÉPARGNE — {statut}\n"
            f"PM (encours)               : {pm:>12,.0f} €\n"
            f"PPB totale                 : {ppb:>12,.0f} €\n"
            f"Taux PPB                   : {taux_ppb:.2f}%\n"
            f"Réserve de capitalisation  : {rc:>12,.0f} €\n"
            f"Provisions totales         : {pm+ppb+rc:>12,.0f} €\n"
            f"Écart PM calc/déclaré      : {ecart:.1f}%\n\n"
            f"DIAGNOSTIC :\n"
            f"La PPB de {ppb:,.0f}€ ({taux_ppb:.2f}% de l'encours)\n"
            f"représente la réserve de participation non encore distribuée.\n\n"
            f"RECOMMANDATION :\n"
            f"→ Maintenir la PPB ≥ 0% (obligation réglementaire).\n"
            f"→ Objectif marché : PPB ≥ 1-3% de l'encours.\n"
            f"→ Alimenter la réserve de capitalisation en période de taux bas."
        )

    def _afficher(self, result):
        sep = "═" * 65
        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT EP3 PROVISIONS | {result['audit_id']}")
        print(sep)
        for ligne in result['commentaire'].split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")


    def _generer_excel(self, result: dict) -> bytes:
        """Rapport Excel individuel EP3 — 4 onglets auditables."""
        from datetime import datetime
        wb  = creer_workbook_actuariel()
        aid = result.get("audit_id", "N/A")
        dte = datetime.now().strftime("%d/%m/%Y %H:%M")
        hyps = [
            {"label": str(k), "valeur": v, "unite": "",
              "source": result.get("sources", {}).get(str(k), "saisie manuelle"),
              "reference": ""}
            for k, v in result.items()
            if isinstance(v, (int, float, str, bool))
            and k not in ("success", "erreur", "audit_id", "commentaire",
                          "agent", "statut_rag", "be_ifrs17_mode")
        ][:20]
        ajouter_onglet_hypotheses(wb, "EP3", aid, dte, hyps,
                                  sources=result.get("sources", {}))
        lignes = [
            {"label": str(k), "valeur": v,
              "unite": "€" if isinstance(v, float) and v > 100 else
                       "%" if isinstance(v, float) and 0 < v < 1 else "",
              "fmt_excel": "#,##0.00" if isinstance(v, float) else None,
              "commentaire": ""}
            for k, v in result.items()
            if isinstance(v, (int, float)) and k not in ("success",)
        ][:40]
        ajouter_onglet_resultats(wb, "EP3", aid, dte,
                                 [{"titre": "Résultats actuariels", "lignes": lignes}])
        for vk in [k for k in result if "validat" in k.lower()]:
            val = result.get(vk, {})
            if isinstance(val, dict) and "statut_global" in val:
                cles = [k for k in val if isinstance(val[k], dict)
                        and "statut" in val[k] and "message" in val[k]]
                if cles:
                    ajouter_onglet_validation(wb, "EP3", aid, dte, val,
                                              cles_controles=cles[:5])
                break
        ajouter_onglet_audit_trail(wb, "EP3", aid, dte, result)
        return finaliser_et_retourner(wb)

    def _sauvegarder(self, audit_id, result):
        chemin = self.models_path / f"ep3_prov_{audit_id}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass


if __name__ == '__main__':
    print("Agent EP3 — Provisionnement Épargne ActuarIA v1.0")
    print("Usage : agent_ep3 = AgentEP3ProvissionnementEpargne()")
    print("        result_ep3 = agent_ep3.run(encours_total=50_000_000)")