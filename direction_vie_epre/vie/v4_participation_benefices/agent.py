"""
ActuarIA — Agent V4 : Théo — Participation aux Bénéfices Vie
Direction Vie & EP-RE | Manager : Sven | Directeur : Paul

Participation aux bénéfices (PB) réglementaire Art. L132-29 :
→ PB réglementaire minimale (85% financier, 90% technique)
→ Provision pour Participation aux Bénéfices (PPB)
→ Réserve de capitalisation
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.v4 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent V4 — Participation aux Bénéfices Vie ActuarIA v1.0")
print("Réglementation : Art. L132-29 · C2023-10 · ACPR")
print("Usage : agent_v4 = AgentV4ParticipationBenefices()")
print("        result_v4 = agent_v4.run(pm_total=50e6, rendement_actifs=0.04)")

class AgentV4ParticipationBenefices:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.v4")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,pm_total=50_000_000,rendement_actifs=0.04,taux_technique=0.025,
            ppb_initiale=0,reserve_capi=0,tx_servi_cible=0.03,
            chargements=0.008,generer_graphiques=True) -> Dict:
        audit_id=f"V4_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent V4 démarré | PM={pm_total/1e6:.1f}M€ | Rend={rendement_actifs*100:.2f}%")
        try:
            # ── Produits financiers ───────────────────────────────────────────
            produits_financiers=pm_total*rendement_actifs

            # ── Bénéfice technique ────────────────────────────────────────────
            charges_techniques=pm_total*taux_technique
            benefice_technique=produits_financiers-charges_techniques

            # ── PB réglementaire minimale (Art. L132-29) ─────────────────────
            # 85% des produits financiers nets + 90% du bénéfice technique
            pb_fin_min=max(0, produits_financiers * 0.85)
            pb_tech_min=max(0, benefice_technique * 0.90)
            pb_reglementaire_min=pb_fin_min + pb_tech_min

            # ── PB servie ─────────────────────────────────────────────────────
            # Taux servi = tx_servi_cible (décision de gestion)
            pb_servie=pm_total * tx_servi_cible
            pb_portee_ppb=max(0, pb_reglementaire_min - pb_servie)

            # ── PPB — Provision pour Participation aux Bénéfices ──────────────
            # PPB = PB réglementaire non encore distribuée
            ppb_finale=ppb_initiale + pb_portee_ppb
            # La PPB doit être reprise dans les 8 ans (C2023-10)
            ppb_max_reglementaire=pm_total * 0.10  # 10% des PM
            ppb_ok=ppb_finale <= ppb_max_reglementaire

            # ── Réserve de capitalisation ──────────────────────────────────────
            rc_dotation=max(0, produits_financiers * 0.05)
            rc_finale=reserve_capi + rc_dotation

            # ── Taux servi aux assurés ─────────────────────────────────────────
            tx_net_charge=tx_servi_cible - chargements
            spread=tx_servi_cible - taux_technique

            # ── Bénéfice global ───────────────────────────────────────────────
            benefice_global=produits_financiers - pb_servie - rc_dotation

            # Évolution PPB sur 8 ans (reprises linéaires)
            ppb_evol=[ppb_finale * max(0, 1-t/8) for t in range(9)]
            taux_servi_evol=[tx_servi_cible+pb_portee_ppb/pm_total*(t/8) for t in range(9)]

            commentaire=(
                f"✅ Participation aux Bénéfices calculée — PM {pm_total/1e6:.1f}M€ | Rendement {rendement_actifs*100:.2f}%.\n"
                f"PB réglementaire min : {pb_reglementaire_min/1e3:.0f}k€ "
                f"(85% fin={pb_fin_min/1e3:.0f}k€ + 90% tech={pb_tech_min/1e3:.0f}k€).\n"
                f"PB servie : {pb_servie/1e3:.0f}k€ ({tx_servi_cible*100:.2f}% des PM) "
                f"→ PPB dotation : {pb_portee_ppb/1e3:.0f}k€.\n"
                f"PPB finale : {ppb_finale/1e3:.0f}k€ ({'✅ < 10% PM' if ppb_ok else '❌ > 10% PM'}) "
                f"| Réserve capi : {rc_finale/1e3:.0f}k€.\n"
                f"Taux net de chargements : {tx_net_charge*100:.2f}% | Spread vs technique : +{spread*100:.2f}%."
            )

            val_hyp=self._valider_pb(pb_reglementaire_min,pb_servie,ppb_finale,ppb_max_reglementaire,
                                     tx_servi_cible,taux_technique,pm_total)
            gv=self._graphiques_validation_pb(val_hyp,ppb_evol,taux_servi_evol,
                                              pb_reglementaire_min,pb_servie) if generer_graphiques else {}
            graphiques=self._generer_graphiques(ppb_evol,taux_servi_evol) if generer_graphiques else {}
            self._sauvegarder({'agent':'V4 Théo','pb_regl_min':pb_reglementaire_min,
                               'pb_servie':pb_servie,'ppb_finale':ppb_finale,'tx_servi':tx_servi_cible}, audit_id)

            return {
                'success':True,'agent':'V4 Théo',
                'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                'pm_total':pm_total,'rendement_actifs':rendement_actifs,
                'produits_financiers':round(produits_financiers,2),
                'pb_reglementaire_min':round(pb_reglementaire_min,2),
                'pb_servie':round(pb_servie,2),
                'pb_portee_ppb':round(pb_portee_ppb,2),
                'ppb_initiale':round(ppb_initiale,2),
                'ppb_finale':round(ppb_finale,2),
                'ppb_ok':ppb_ok,
                'rc_dotation':round(rc_dotation,2),
                'rc_finale':round(rc_finale,2),
                'tx_servi_cible':tx_servi_cible,
                'tx_net_charge':round(tx_net_charge,4),
                'spread':round(spread,4),
                'ppb_evol':[round(p,2) for p in ppb_evol],
                'taux_servi_evol':[round(t,4) for t in taux_servi_evol],
                'commentaire':commentaire,'audit_id':audit_id,
                'graphiques':graphiques,'validation_pb':val_hyp,'graphiques_validation':gv,'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_pb(self,pb_min,pb_servie,ppb,ppb_max,tx_servi,taux_tech,pm):
        # H1 — PB servie ≥ PB réglementaire min
        if pb_servie+ppb >= pb_min*0.99:
            h1_s,h1_m,h1_c="VERT",f"PB servie+PPB={( pb_servie+ppb)/1e3:.0f}k€ ≥ PB min={pb_min/1e3:.0f}k€ ✅","Art. L132-29 respecté"
        else:
            h1_s,h1_m,h1_c="ROUGE",f"PB servie+PPB={( pb_servie+ppb)/1e3:.0f}k€ < PB min={pb_min/1e3:.0f}k€ ❌","Art. L132-29 violé — PB insuffisante"
        # H2 — PPB ≤ 10% des PM
        ratio_ppb=ppb/max(pm,1)
        if ratio_ppb<=0.10: h2_s,h2_m,h2_c="VERT",f"PPB = {ratio_ppb*100:.1f}% PM ≤ 10% ✅","PPB conforme C2023-10 ACPR"
        elif ratio_ppb<=0.15: h2_s,h2_m,h2_c="AMBRE",f"PPB = {ratio_ppb*100:.1f}% PM ∈ [10%,15%] ⚠️","PPB élevée — prévoir un plan de reprise"
        else: h2_s,h2_m,h2_c="ROUGE",f"PPB = {ratio_ppb*100:.1f}% PM > 15% ❌","PPB excessive — intervention ACPR possible"
        # H3 — Taux servi > taux technique
        spread=tx_servi-taux_tech
        if spread>=0.005: h3_s,h3_m,h3_c="VERT",f"Spread = +{spread*100:.2f}% → Taux servi attractif ✅","Taux servi compétitif vs taux technique"
        elif spread>=0: h3_s,h3_m,h3_c="AMBRE",f"Spread = +{spread*100:.2f}% → Attractivité limitée ⚠️","Augmenter le taux servi pour fidéliser les assurés"
        else: h3_s,h3_m,h3_c="ROUGE",f"Spread = {spread*100:.2f}% → Taux servi < technique ❌","Taux servi inférieur au taux technique — risque commercial"
        sts=[h1_s,h2_s,h3_s]; sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "h1_pb_regl":{"pb_min":round(pb_min,2),"pb_servie":round(pb_servie,2),"statut":h1_s,"message":h1_m,"conseil":h1_c,"titre_graphique":f"{'✅' if h1_s=='VERT' else '❌'} PB Art.L132-29"},
            "h2_ppb":{"ppb":round(ppb,2),"ratio_ppb":round(ratio_ppb,4),"statut":h2_s,"message":h2_m,"conseil":h2_c,"titre_graphique":f"{'✅' if h2_s=='VERT' else '⚠️' if h2_s=='AMBRE' else '❌'} PPB = {ratio_ppb*100:.1f}% PM"},
            "h3_spread":{"spread":round(spread,4),"tx_servi":tx_servi,"taux_tech":taux_tech,"statut":h3_s,"message":h3_m,"conseil":h3_c,"titre_graphique":f"{'✅' if h3_s=='VERT' else '⚠️' if h3_s=='AMBRE' else '❌'} Spread = +{spread*100:.2f}%"},
            "statut_global":sg,"conclusion":{"VERT":"✅ PB validée — Art.L132-29 respecté, PPB conforme et spread positif","AMBRE":"⚠️ PB acceptable — vérifier les points signalés","ROUGE":"❌ PB non conforme — action corrective requise"}[sg],
        }

    def _graphiques_validation_pb(self,val,ppb_evol,tx_evol,pb_min,pb_servie):
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT=dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques={}
        # G1 — PB réglementaire vs servie
        try:
            h1=val["h1_pb_regl"]; c1=VERT if h1["statut"]=="VERT" else ROUGE
            fig1=go.Figure(go.Bar(x=["PB Min. Réglementaire","PB Servie"],y=[pb_min/1e3,pb_servie/1e3],
                marker_color=[GRIS,c1],width=0.4,opacity=0.88,
                text=[f"{pb_min/1e3:.0f}k€",f"{pb_servie/1e3:.0f}k€"],textposition="outside",textfont=dict(color=BLANC,size=12)))
            l1=dict(**LAYOUT); l1.update(dict(title=dict(text=f"{'✅' if h1['statut']=='VERT' else '❌'} PB servie vs PB réglementaire Art.L132-29",font=dict(color=c1,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(title="k€",tickfont=dict(color=GRIS)),bargap=0.4,showlegend=False,
                annotations=[dict(text="💡 La barre colorée (PB servie) doit être ≥ la barre grise (minimum légal Art.L132-29).",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig1.update_layout(**l1); graphiques["pb_regl_vs_servie"]=fig1
        except: pass
        # G2 — Évolution PPB sur 8 ans
        try:
            h2=val["h2_ppb"]; c2=VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            fig2=go.Figure(go.Scatter(x=list(range(9)),y=[p/1e3 for p in ppb_evol],mode="lines+markers",
                line=dict(color=OR,width=2.5),marker=dict(color=OR,size=7),fill="tozeroy",fillcolor="rgba(201,168,76,0.08)",
                hovertemplate="Année %{x}<br>PPB : %{y:.0f}k€<extra></extra>"))
            l2=dict(**LAYOUT); l2.update(dict(title=dict(text=h2["titre_graphique"]+" — Reprise sur 8 ans (C2023-10)",font=dict(color=c2,size=11),x=0.01),
                xaxis=dict(title="Années",tickfont=dict(color=GRIS),showgrid=True,gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="PPB (k€)",tickfont=dict(color=GRIS)),showlegend=False,
                annotations=[dict(text="💡 La PPB doit être entièrement reprise dans les 8 ans (C2023-10 ACPR). La courbe doit atteindre 0.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig2.update_layout(**l2); graphiques["evolution_ppb"]=fig2
        except: pass
        # G3 — Spread taux servi vs technique
        try:
            h3=val["h3_spread"]; c3=VERT if h3["statut"]=="VERT" else AMBRE if h3["statut"]=="AMBRE" else ROUGE
            fig3=go.Figure(go.Bar(x=["Taux Technique","Taux Servi"],y=[h3["taux_tech"]*100,h3["tx_servi"]*100],
                marker_color=[GRIS,c3],width=0.4,opacity=0.88,
                text=[f"{h3['taux_tech']*100:.2f}%",f"{h3['tx_servi']*100:.2f}%"],textposition="outside",textfont=dict(color=BLANC,size=12)))
            l3=dict(**LAYOUT); l3.update(dict(title=dict(text=h3["titre_graphique"]+" — Taux servi vs technique",font=dict(color=c3,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.4,showlegend=False,
                annotations=[dict(text="💡 Le taux servi (coloré) doit être supérieur au taux technique (gris). L'écart (spread) = attractivité du produit.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig3.update_layout(**l3); graphiques["spread_taux"]=fig3
        except: pass
        # G4 — Scorecard
        try:
            items=[("H1 — PB Art.L132-29",val["h1_pb_regl"]["statut"],val["h1_pb_regl"]["message"],val["h1_pb_regl"]["conseil"]),
                   ("H2 — PPB ≤ 10% PM",val["h2_ppb"]["statut"],val["h2_ppb"]["message"],val["h2_ppb"]["conseil"]),
                   ("H3 — Spread positif",val["h3_spread"]["statut"],val["h3_spread"]["message"],val["h3_spread"]["conseil"])]
            fig4=go.Figure()
            for nom,statut,msg,conseil in items:
                c=VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i="✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s=1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(x=[s],y=[nom],orientation="h",marker_color=c,width=0.5,text=f"{i} {statut}",textposition="outside",textfont=dict(color=c,size=10),hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"]; cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard PB Vie — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",height=260,annotations=[dict(text="💡 3 ✅ = PB conforme Art.L132-29, PPB maîtrisée et spread attractif.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_pb"]=fig4
        except: pass
        return graphiques

    def _generer_graphiques(self,ppb_evol,tx_evol):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
            fig=go.Figure(go.Scatter(x=list(range(9)),y=[p/1e3 for p in ppb_evol],mode="lines+markers",
                line=dict(color=OR,width=2.5),fill="tozeroy",fillcolor="rgba(201,168,76,0.08)"))
            fig.update_layout(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),
                margin=dict(l=16,r=16,t=60,b=40),height=300,
                title=dict(text="Évolution PPB — Reprise sur 8 ans",font=dict(color=BLANC,size=12),x=0.01),
                xaxis=dict(title="Années",tickfont=dict(color=GRIS)),yaxis=dict(title="PPB (k€)",tickfont=dict(color=GRIS)),showlegend=False)
            return {"ppb_evolution":fig}
        except: return {}

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"v4_pb_{audit_id}.json"),'w') as f: json.dump(rapport,f,indent=2)
            self.logger.info(f"Sauvegardé : v4_pb_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
