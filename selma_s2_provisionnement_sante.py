"""
ActuarIA — Agent S2 : Selma — Provisionnement Santé
Direction Santé-Prévoyance | Manager : Chiara | Directeur : Amira

Provisions spécifiques santé :
→ PSAP (Provision Sinistres À Payer) — triangle de développement santé
→ PREC (Provision pour Risques En Cours)
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.s2 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent S2 — Provisionnement Santé ActuarIA v1.0")
print("PSAP (Sinistres À Payer) · PREC (Risques En Cours) · Triangle Santé")
print("Usage : agent_s2 = AgentS2ProvisionnemntSante()")
print("        result_s2 = agent_s2.run(primes_acquises=5e6, sinistres_payes=3.2e6)")

class AgentS2ProvisionnemntSante:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.s2")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,primes_acquises=5_000_000,sinistres_payes=3_200_000,
            nb_sinistres_ouverts=1200,cout_moyen_ouvert=850,
            delai_reglement_mois=3,generer_graphiques=True) -> Dict:
        audit_id=f"S2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent S2 démarré | PA={primes_acquises/1e6:.1f}M€ | SP={sinistres_payes/1e6:.1f}M€")
        try:
            # PSAP — Méthode des dossiers connus
            psap_dossiers = nb_sinistres_ouverts * cout_moyen_ouvert

            # PSAP IBNR (Incurred But Not Reported) — ratio de développement santé
            # En santé, IBNR ≈ 15-25% des sinistres payés (liquidation rapide)
            facteur_ibnr = 0.18
            psap_ibnr = sinistres_payes * facteur_ibnr
            psap_total = psap_dossiers + psap_ibnr

            # PREC — Provision pour Risques En Cours
            # PREC = max(0, PA × (1 - ratio combiné attendu))
            ratio_sp = sinistres_payes / max(primes_acquises, 1)
            ratio_combine_attendu = ratio_sp + 0.15  # chargements
            prec = max(0, primes_acquises * max(0, ratio_combine_attendu - 1))

            # Loss Ratio
            loss_ratio = sinistres_payes / max(primes_acquises, 1)
            provision_totale = psap_total + prec

            # Taux de provisionnement
            taux_prov = provision_totale / max(primes_acquises, 1)

            commentaire = (
                f"✅ Provisionnement Santé — PA={primes_acquises/1e6:.1f}M€ | SP={sinistres_payes/1e6:.1f}M€.\n"
                f"PSAP dossiers : {psap_dossiers/1e3:.0f}k€ ({nb_sinistres_ouverts} sin. × {cout_moyen_ouvert:.0f}€).\n"
                f"PSAP IBNR     : {psap_ibnr/1e3:.0f}k€ ({facteur_ibnr*100:.0f}% des SP).\n"
                f"PSAP totale   : {psap_total/1e3:.0f}k€ | PREC : {prec/1e3:.0f}k€.\n"
                f"Loss Ratio    : {loss_ratio*100:.1f}% | Taux prov. : {taux_prov*100:.1f}%."
            )

            val_hyp = self._valider_provisionnement_sante(
                psap_total, prec, loss_ratio, taux_prov, primes_acquises, psap_ibnr, sinistres_payes)
            gv  = self._graphiques_validation_s2(val_hyp, psap_dossiers, psap_ibnr, prec, primes_acquises, sinistres_payes) if generer_graphiques else {}
            graphiques = self._generer_graphiques(psap_dossiers, psap_ibnr, prec) if generer_graphiques else {}
            self._sauvegarder({'agent':'S2 Selma','psap_total':psap_total,'prec':prec,'loss_ratio':loss_ratio}, audit_id)

            return {
                'success':True,'agent':'S2 Selma',
                'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                'primes_acquises':primes_acquises,'sinistres_payes':sinistres_payes,
                'psap_dossiers':round(psap_dossiers,2),
                'psap_ibnr':round(psap_ibnr,2),
                'psap_total':round(psap_total,2),
                'prec':round(prec,2),
                'provision_totale':round(provision_totale,2),
                'loss_ratio':round(loss_ratio,4),
                'taux_provisionnement':round(taux_prov,4),
                'commentaire':commentaire,'audit_id':audit_id,
                'graphiques':graphiques,'validation_s2':val_hyp,'graphiques_validation':gv,'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_provisionnement_sante(self,psap,prec,lr,taux_prov,pa,ibnr,sp):
        # H1 — PSAP ≥ 10% des primes
        ratio_psap = psap / max(pa, 1)
        if ratio_psap>=0.10: h1_s,h1_m,h1_c="VERT",f"PSAP = {ratio_psap*100:.1f}% PA ≥ 10% ✅","PSAP suffisante — sinistres couverts"
        elif ratio_psap>=0.05: h1_s,h1_m,h1_c="AMBRE",f"PSAP = {ratio_psap*100:.1f}% PA ∈ [5%,10%] ⚠️","PSAP limite — revoir les dossiers ouverts"
        else: h1_s,h1_m,h1_c="ROUGE",f"PSAP = {ratio_psap*100:.1f}% PA < 5% ❌","PSAP insuffisante — sous-provisionnement probable"
        # H2 — IBNR ∈ [10%, 30%] des sinistres payés
        ratio_ibnr = ibnr / max(sp, 1)
        if 0.10<=ratio_ibnr<=0.30: h2_s,h2_m,h2_c="VERT",f"IBNR = {ratio_ibnr*100:.0f}% SP ∈ [10%,30%] ✅","IBNR santé cohérent avec la liquidation rapide"
        elif ratio_ibnr<0.10: h2_s,h2_m,h2_c="AMBRE",f"IBNR = {ratio_ibnr*100:.0f}% SP < 10% ⚠️","IBNR faible — vérifier les délais de déclaration"
        else: h2_s,h2_m,h2_c="AMBRE",f"IBNR = {ratio_ibnr*100:.0f}% SP > 30% ⚠️","IBNR élevé pour la santé — vérifier la méthode"
        # H3 — Loss Ratio ≤ 85%
        if lr<=0.85: h3_s,h3_m,h3_c="VERT",f"Loss Ratio = {lr*100:.1f}% ≤ 85% ✅","Sinistralité maîtrisée — contrat rentable"
        elif lr<=0.95: h3_s,h3_m,h3_c="AMBRE",f"Loss Ratio = {lr*100:.1f}% ∈ [85%,95%] ⚠️","Sinistralité limite — surveiller l'évolution"
        else: h3_s,h3_m,h3_c="ROUGE",f"Loss Ratio = {lr*100:.1f}% > 95% ❌","Contrat déficitaire — révision tarifaire urgente"
        sts=[h1_s,h2_s,h3_s]; sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "h1_psap":{"ratio_psap":round(ratio_psap,4),"statut":h1_s,"message":h1_m,"conseil":h1_c,"titre_graphique":f"{'✅' if h1_s=='VERT' else '⚠️' if h1_s=='AMBRE' else '❌'} PSAP = {ratio_psap*100:.1f}% PA"},
            "h2_ibnr":{"ratio_ibnr":round(ratio_ibnr,4),"statut":h2_s,"message":h2_m,"conseil":h2_c,"titre_graphique":f"{'✅' if h2_s=='VERT' else '⚠️'} IBNR = {ratio_ibnr*100:.0f}% SP"},
            "h3_loss_ratio":{"loss_ratio":round(lr,4),"statut":h3_s,"message":h3_m,"conseil":h3_c,"titre_graphique":f"{'✅' if h3_s=='VERT' else '⚠️' if h3_s=='AMBRE' else '❌'} Loss Ratio = {lr*100:.1f}%"},
            "statut_global":sg,"conclusion":{"VERT":"✅ Provisionnement Santé validé — PSAP, IBNR et sinistralité conformes","AMBRE":"⚠️ Provisionnement acceptable — vérifier les points signalés","ROUGE":"❌ Provisionnement insuffisant — action corrective requise"}[sg],
        }

    def _graphiques_validation_s2(self,val,psap_d,psap_i,prec,pa,sp):
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT=dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques={}
        # G1 — Décomposition provisions
        try:
            h1=val["h1_psap"]; c1=VERT if h1["statut"]=="VERT" else AMBRE if h1["statut"]=="AMBRE" else ROUGE
            fig1=go.Figure(go.Bar(x=["PSAP Dossiers","PSAP IBNR","PREC","Total"],
                y=[psap_d/1e3,psap_i/1e3,prec/1e3,(psap_d+psap_i+prec)/1e3],
                marker_color=[OR,BLEU,AMBRE,c1],width=0.45,opacity=0.88,
                text=[f"{v:.0f}k€" for v in [psap_d/1e3,psap_i/1e3,prec/1e3,(psap_d+psap_i+prec)/1e3]],
                textposition="outside",textfont=dict(color=BLANC,size=10)))
            l1=dict(**LAYOUT); l1.update(dict(title=dict(text=f"{'✅' if h1['statut']=='VERT' else '⚠️'} Décomposition des provisions santé",font=dict(color=c1,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.3,showlegend=False,
                annotations=[dict(text="💡 PSAP=sinistres connus, IBNR=non encore déclarés, PREC=risques futurs.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig1.update_layout(**l1); graphiques["decomposition_provisions"]=fig1
        except: pass
        # G2 — Loss Ratio jauge
        try:
            h3=val["h3_loss_ratio"]; lr=h3["loss_ratio"]; c3=VERT if h3["statut"]=="VERT" else AMBRE if h3["statut"]=="AMBRE" else ROUGE
            fig2=go.Figure(go.Indicator(mode="gauge+number",value=lr*100,
                number=dict(suffix="%",font=dict(color=c3,size=28),valueformat=".1f"),
                title=dict(text=h3["titre_graphique"],font=dict(color=c3,size=11)),
                gauge=dict(axis=dict(range=[0,120],tickfont=dict(color=GRIS,size=8),tickvals=[0,65,85,95,100,120],ticktext=["0","65%","85%","95%","100","120"]),
                    bar=dict(color=c3,thickness=0.25),bgcolor="#1B3A5C",borderwidth=0,
                    steps=[dict(range=[0,85],color="rgba(46,204,113,0.12)"),dict(range=[85,95],color="rgba(243,156,18,0.12)"),dict(range=[95,120],color="rgba(231,76,60,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=85))))
            fig2.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {h3['conseil']}",xref="paper",yref="paper",x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["jauge_loss_ratio"]=fig2
        except: pass
        # G3 — IBNR vs sinistres payés
        try:
            h2=val["h2_ibnr"]; c2=VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            ibnr=sp*h2["ratio_ibnr"]
            fig3=go.Figure(go.Bar(x=["Sinistres payés","IBNR"],y=[sp/1e3,ibnr/1e3],
                marker_color=[OR,c2],width=0.4,opacity=0.88,
                text=[f"{sp/1e3:.0f}k€",f"{ibnr/1e3:.0f}k€"],textposition="outside",textfont=dict(color=BLANC,size=12)))
            l3=dict(**LAYOUT); l3.update(dict(title=dict(text=h2["titre_graphique"]+" — Proportion vs sinistres payés",font=dict(color=c2,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(title="k€",tickfont=dict(color=GRIS)),bargap=0.4,showlegend=False,
                annotations=[dict(text="💡 En santé, l'IBNR est faible (10-30%) car les soins sont déclarés rapidement vs l'IARD (40-60%).",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig3.update_layout(**l3); graphiques["ibnr_vs_sinistres"]=fig3
        except: pass
        # G4 — Scorecard
        try:
            items=[("H1 — PSAP ≥ 10% PA",val["h1_psap"]["statut"],val["h1_psap"]["message"],val["h1_psap"]["conseil"]),
                   ("H2 — IBNR ∈ [10%,30%] SP",val["h2_ibnr"]["statut"],val["h2_ibnr"]["message"],val["h2_ibnr"]["conseil"]),
                   ("H3 — Loss Ratio ≤ 85%",val["h3_loss_ratio"]["statut"],val["h3_loss_ratio"]["message"],val["h3_loss_ratio"]["conseil"])]
            fig4=go.Figure()
            for nom,statut,msg,conseil in items:
                c=VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i="✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s=1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(x=[s],y=[nom],orientation="h",marker_color=c,width=0.5,text=f"{i} {statut}",textposition="outside",textfont=dict(color=c,size=10),hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"]; cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard Provisionnement Santé — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),barmode="overlay",height=260,
                annotations=[dict(text="💡 3 ✅ = provisionnement santé conforme, PSAP et IBNR adéquats.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_s2"]=fig4
        except: pass
        return graphiques

    def _generer_graphiques(self,psap_d,psap_i,prec):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0";BLEU="#3498DB";AMBRE="#F39C12"
            fig=go.Figure(go.Pie(labels=["PSAP Dossiers","PSAP IBNR","PREC"],
                values=[psap_d,psap_i,prec],hole=0.4,marker_colors=[OR,BLEU,AMBRE],
                hovertemplate="<b>%{label}</b><br>%{value:,.0f}€ (%{percent})<extra></extra>"))
            fig.update_layout(paper_bgcolor=NAVY,font=dict(family="Inter",color=BLANC,size=11),
                margin=dict(l=16,r=16,t=60,b=40),height=300,
                title=dict(text="Répartition des provisions santé",font=dict(color=BLANC,size=12),x=0.01))
            return {"provisions_pie":fig}
        except: return {}

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"s2_prov_{audit_id}.json"),'w') as f: json.dump(rapport,f,indent=2)
            self.logger.info(f"Sauvegardé : s2_prov_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
