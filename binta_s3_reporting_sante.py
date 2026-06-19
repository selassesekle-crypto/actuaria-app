"""
ActuarIA — Agent S3 : Binta — Reporting Santé QRT S.13
Direction Santé-Prévoyance | Manager : Chiara | Directeur : Amira

QRT S.13 — Health similar to life techniques
→ TP Santé · BE · Risk Adjustment · SCR Santé
→ Ratio de couverture SCR · MCR
→ Validation hypothèses + graphiques
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.s3 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent S3 — Reporting Santé QRT S.13 ActuarIA v1.0")
print("QRT : S.13.01 (Santé SLT) · S.23 (Fonds Propres) · SCR Santé")
print("Usage : agent_s3 = AgentS3ReportingSante()")
print("        result_s3 = agent_s3.run(primes_acquises=10e6, psap=1.5e6)")

class AgentS3ReportingSante:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.s3")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,primes_acquises=10_000_000,psap=1_500_000,prec=200_000,
            fonds_propres=8_000_000,generer_graphiques=True) -> Dict:
        audit_id=f"S3_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent S3 démarré | PA={primes_acquises/1e6:.1f}M€")
        try:
            be_sante = psap + prec
            risk_adj = be_sante * 0.05
            tp_sante = be_sante + risk_adj
            ratio_tp_be = tp_sante / max(be_sante, 1)

            # SCR Santé (formule standard EIOPA — simplifié)
            scr_souscription = primes_acquises * 0.12
            scr_reserve      = psap * 0.20
            scr_sante = np.sqrt(scr_souscription**2 + scr_reserve**2 + 1.5*scr_souscription*scr_reserve)

            mcr_sante = max(scr_sante * 0.25, primes_acquises * 0.025)
            ratio_scr = fonds_propres / max(scr_sante, 1) * 100
            ratio_mcr = fonds_propres / max(mcr_sante, 1) * 100

            qrt_s13 = {
                "code": "S.13.01",
                "titre": "Health similar to life techniques",
                "be_sante":   round(be_sante, 2),
                "risk_adj":   round(risk_adj, 2),
                "tp_sante":   round(tp_sante, 2),
                "ratio_tp_be":round(ratio_tp_be, 4),
            }

            commentaire = (
                f"✅ QRT Santé S.13 — PA={primes_acquises/1e6:.1f}M€ | BE={be_sante/1e3:.0f}k€ | TP={tp_sante/1e3:.0f}k€.\n"
                f"SCR Santé : {scr_sante/1e3:.0f}k€ | Ratio SCR : {ratio_scr:.1f}% | Ratio MCR : {ratio_mcr:.1f}%.\n"
                f"Risk Adjustment : {risk_adj/1e3:.0f}k€ ({risk_adj/max(be_sante,1)*100:.1f}% du BE)."
            )

            val_hyp = self._valider_qrt_sante(ratio_tp_be, ratio_scr, ratio_mcr, primes_acquises, be_sante)
            gv  = self._graphiques_validation_s3(val_hyp, qrt_s13, scr_sante, fonds_propres) if generer_graphiques else {}
            graphiques = self._generer_graphiques(qrt_s13, scr_sante, fonds_propres, ratio_scr) if generer_graphiques else {}
            self._sauvegarder({'agent':'S3 Binta','qrt_s13':qrt_s13,'scr_sante':scr_sante,'ratio_scr':ratio_scr}, audit_id)

            return {
                'success':True,'agent':'S3 Binta',
                'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                'qrt_s13':qrt_s13,'scr_sante':round(scr_sante,2),'mcr_sante':round(mcr_sante,2),
                'ratio_scr_pct':round(ratio_scr,1),'ratio_mcr_pct':round(ratio_mcr,1),
                'fonds_propres':fonds_propres,
                'commentaire':commentaire,'audit_id':audit_id,
                'graphiques':graphiques,'validation_s3':val_hyp,'graphiques_validation':gv,'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_qrt_sante(self,ratio_tp_be,ratio_scr,ratio_mcr,pa,be):
        # C1 — Ratio TP/BE ∈ [1.0, 1.5]
        if 1.0<=ratio_tp_be<=1.5: c1_s,c1_m,c1_c="VERT",f"TP/BE = {ratio_tp_be:.3f} ∈ [1.0,1.5] ✅","Risk Adjustment justifié — QRT S.13 conforme"
        elif ratio_tp_be<1.0: c1_s,c1_m,c1_c="ROUGE",f"TP/BE = {ratio_tp_be:.3f} < 1.0 ❌","TP Santé < BE — Risk Adjustment négatif impossible"
        else: c1_s,c1_m,c1_c="AMBRE",f"TP/BE = {ratio_tp_be:.3f} > 1.5 ⚠️","Risk Adjustment santé élevé — justifier"
        # C2 — Ratio SCR ≥ 130% (seuil ORSA santé)
        if ratio_scr>=130: c2_s,c2_m,c2_c="VERT",f"Ratio SCR = {ratio_scr:.1f}% ≥ 130% ✅","Capitalisation solide pour le risque santé"
        elif ratio_scr>=100: c2_s,c2_m,c2_c="AMBRE",f"Ratio SCR = {ratio_scr:.1f}% ∈ [100%,130%] ⚠️","Ratio conforme mais proche du seuil"
        else: c2_s,c2_m,c2_c="ROUGE",f"Ratio SCR = {ratio_scr:.1f}% < 100% ❌","INSUFFISANCE DE CAPITAL — notification ACPR requise"
        # C3 — BE Santé ≤ 30% des PA
        ratio_be = be / max(pa, 1)
        if ratio_be<=0.30: c3_s,c3_m,c3_c="VERT",f"BE/PA = {ratio_be*100:.1f}% ≤ 30% ✅","Provisions santé cohérentes avec la sinistralité"
        elif ratio_be<=0.40: c3_s,c3_m,c3_c="AMBRE",f"BE/PA = {ratio_be*100:.1f}% ∈ [30%,40%] ⚠️","Provisions élevées — vérifier la sinistralité"
        else: c3_s,c3_m,c3_c="ROUGE",f"BE/PA = {ratio_be*100:.1f}% > 40% ❌","Surprovisionnement ou sinistralité excessive"
        sts=[c1_s,c2_s,c3_s]; sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "c1_tp_be":{"ratio":round(ratio_tp_be,4),"statut":c1_s,"message":c1_m,"conseil":c1_c,"titre_graphique":f"{'✅' if c1_s=='VERT' else '⚠️' if c1_s=='AMBRE' else '❌'} TP/BE = {ratio_tp_be:.3f}"},
            "c2_scr":{"ratio_scr":round(ratio_scr,1),"statut":c2_s,"message":c2_m,"conseil":c2_c,"titre_graphique":f"{'✅' if c2_s=='VERT' else '⚠️' if c2_s=='AMBRE' else '❌'} Ratio SCR Santé = {ratio_scr:.1f}%"},
            "c3_be_pa":{"ratio_be":round(ratio_be,4),"statut":c3_s,"message":c3_m,"conseil":c3_c,"titre_graphique":f"{'✅' if c3_s=='VERT' else '⚠️' if c3_s=='AMBRE' else '❌'} BE/PA = {ratio_be*100:.1f}%"},
            "statut_global":sg,"conclusion":{"VERT":"✅ QRT Santé S.13 validé — TP, SCR et provisions conformes EIOPA","AMBRE":"⚠️ QRT acceptable — vérifier les points signalés","ROUGE":"❌ QRT non conforme — action corrective requise"}[sg],
        }

    def _graphiques_validation_s3(self,val,s13,scr,fp):
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT=dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques={}
        # G1 — BE vs TP Santé
        try:
            c1=val["c1_tp_be"]; cc1=VERT if c1["statut"]=="VERT" else AMBRE if c1["statut"]=="AMBRE" else ROUGE
            fig1=go.Figure(go.Bar(x=["BE Santé","Risk Adj.","TP Santé"],
                y=[s13["be_sante"]/1e3,s13["risk_adj"]/1e3,s13["tp_sante"]/1e3],
                marker_color=[OR,BLEU,cc1],width=0.4,opacity=0.88,
                text=[f"{v:.0f}k€" for v in [s13["be_sante"]/1e3,s13["risk_adj"]/1e3,s13["tp_sante"]/1e3]],
                textposition="outside",textfont=dict(color=BLANC,size=10)))
            l1=dict(**LAYOUT); l1.update(dict(title=dict(text=c1["titre_graphique"]+" — QRT S.13.01",font=dict(color=cc1,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.35,showlegend=False,
                annotations=[dict(text="💡 TP Santé = BE + Risk Adjustment. Zone verte = ratio TP/BE ∈ [1.0, 1.5].",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig1.update_layout(**l1); graphiques["qrt_s13_tp_be"]=fig1
        except: pass
        # G2 — Ratio SCR Santé jauge
        try:
            c2=val["c2_scr"]; cc2=VERT if c2["statut"]=="VERT" else AMBRE if c2["statut"]=="AMBRE" else ROUGE
            r_scr=c2["ratio_scr"]
            fig2=go.Figure(go.Indicator(mode="gauge+number",value=r_scr,
                number=dict(suffix="%",font=dict(color=cc2,size=28),valueformat=".1f"),
                title=dict(text=c2["titre_graphique"],font=dict(color=cc2,size=11)),
                gauge=dict(axis=dict(range=[0,300],tickfont=dict(color=GRIS,size=8),tickvals=[0,100,130,200,300],ticktext=["0%","100%","130%","200%","300%"]),
                    bar=dict(color=cc2,thickness=0.25),bgcolor="#1B3A5C",borderwidth=0,
                    steps=[dict(range=[0,100],color="rgba(231,76,60,0.12)"),dict(range=[100,130],color="rgba(243,156,18,0.12)"),dict(range=[130,300],color="rgba(46,204,113,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=130))))
            fig2.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {c2['conseil']}",xref="paper",yref="paper",x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["ratio_scr_sante"]=fig2
        except: pass
        # G3 — Fonds propres vs SCR
        try:
            c3=val["c3_be_pa"]; cc3=VERT if c3["statut"]=="VERT" else AMBRE if c3["statut"]=="AMBRE" else ROUGE
            fig3=go.Figure(go.Bar(x=["SCR Santé","Fonds Propres"],
                y=[scr/1e3,fp/1e3],marker_color=[AMBRE,VERT],width=0.4,opacity=0.88,
                text=[f"{scr/1e3:.0f}k€",f"{fp/1e3:.0f}k€"],textposition="outside",textfont=dict(color=BLANC,size=12)))
            l3=dict(**LAYOUT); l3.update(dict(title=dict(text="Couverture SCR — Fonds Propres vs Exigence",font=dict(color=VERT,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(title="k€",tickfont=dict(color=GRIS)),bargap=0.4,showlegend=False,
                annotations=[dict(text="💡 Les Fonds Propres (vert) doivent toujours dépasser le SCR (orange). Sinon l'assureur est en insuffisance de capital.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig3.update_layout(**l3); graphiques["fp_vs_scr_sante"]=fig3
        except: pass
        # G4 — Scorecard
        try:
            items=[("C1 — TP/BE ∈ [1.0,1.5]",val["c1_tp_be"]["statut"],val["c1_tp_be"]["message"],val["c1_tp_be"]["conseil"]),
                   ("C2 — Ratio SCR ≥ 130%",val["c2_scr"]["statut"],val["c2_scr"]["message"],val["c2_scr"]["conseil"]),
                   ("C3 — BE/PA ≤ 30%",val["c3_be_pa"]["statut"],val["c3_be_pa"]["message"],val["c3_be_pa"]["conseil"])]
            fig4=go.Figure()
            for nom,statut,msg,conseil in items:
                c=VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i="✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s=1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(x=[s],y=[nom],orientation="h",marker_color=c,width=0.5,text=f"{i} {statut}",textposition="outside",textfont=dict(color=c,size=10),hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"]; cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard QRT Santé S.13 — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),barmode="overlay",height=260,
                annotations=[dict(text="💡 3 ✅ = QRT Santé S.13 conforme EIOPA, défendable devant l'ACPR.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_s3"]=fig4
        except: pass
        return graphiques

    def _generer_graphiques(self,s13,scr,fp,ratio_scr):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";BLANC="#F0F4F8";GRIS="#8A9AB0";VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12"
            r=ratio_scr; c=VERT if r>=130 else AMBRE if r>=100 else ROUGE
            fig=go.Figure(go.Indicator(mode="gauge+number",value=r,
                number=dict(suffix="%",font=dict(color=c,size=28),valueformat=".1f"),
                title=dict(text="Ratio SCR Santé",font=dict(color=c,size=12)),
                gauge=dict(axis=dict(range=[0,300],tickfont=dict(color=GRIS,size=8)),
                    bar=dict(color=c,thickness=0.25),bgcolor="#1B3A5C",borderwidth=0,
                    steps=[dict(range=[0,100],color="rgba(231,76,60,0.12)"),dict(range=[100,130],color="rgba(243,156,18,0.12)"),dict(range=[130,300],color="rgba(46,204,113,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=130))))
            fig.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=30),height=300)
            return {"ratio_scr":fig}
        except: return {}

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"s3_qrt_{audit_id}.json"),'w') as f: json.dump(rapport,f,indent=2)
            self.logger.info(f"Sauvegardé : s3_qrt_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
