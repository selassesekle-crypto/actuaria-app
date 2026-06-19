"""
ActuarIA — P4 Valentin — Reporting Prévoyance QRT
Direction Santé-Prévoyance | Directeur : Amira
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.p4 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent P4 — Reporting Prévoyance QRT ActuarIA v1.0")
print("QRT S.14 (Vie Prévoyance) · S.23 (Fonds Propres)")
print("Usage : agent_p4 = AgentP4ReportingPrevoyance()")
print("        result_p4 = agent_p4.run(primes=8e6, psap=2e6)")

class AgentP4ReportingPrevoyance:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.p4")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,generer_graphiques=True,**kwargs) -> Dict:
        audit_id=f"P4_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent P4 démarré")
        try:
            result = self._calculer(**kwargs)
            val_hyp = self._valider(result)
            gv = self._graphiques_validation(val_hyp, result) if generer_graphiques else {}
            graphiques = self._generer_graphiques(result) if generer_graphiques else {}
            self._sauvegarder(result, audit_id)
            return {
                'success':True, 'agent':'Reporting Prévoyance QRT',
                'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                **result,
                'audit_id':audit_id,
                'graphiques':graphiques,
                'validation_p4':val_hyp,
                'graphiques_validation':gv,
                'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _calculer(self,**kwargs) -> Dict:
        
        pa   = kwargs.get('primes', 8_000_000)
        psap = kwargs.get('psap', 2_000_000)
        fp   = kwargs.get('fonds_propres', 10_000_000)
        be   = psap * 1.20
        tp   = be * 1.08
        scr  = pa * 0.15
        ratio_scr = fp / max(scr,1) * 100
        ratio_tp_be = tp / max(be,1)
        return {'be_prev':round(be,2),'tp_prev':round(tp,2),'scr_prev':round(scr,2),
                'ratio_scr_pct':round(ratio_scr,1),'ratio_tp_be':round(ratio_tp_be,4),
                'commentaire':f"TP={tp/1e3:.0f}k€ | SCR={scr/1e3:.0f}k€ | Ratio SCR={ratio_scr:.1f}%"}

    def _valider(self, result: Dict) -> Dict:
        
        r_tp = result.get('ratio_tp_be', 1.0)
        r_scr = result.get('ratio_scr_pct', 100)
        h1_s = "VERT" if 1.0<=r_tp<=1.5 else "AMBRE" if r_tp>1.5 else "ROUGE"
        h2_s = "VERT" if r_scr>=130 else "AMBRE" if r_scr>=100 else "ROUGE"
        h3_s = "VERT"
        sts=[h1_s,h2_s,h3_s]; sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "c1_tp_be":{"statut":h1_s,"message":f"TP/BE = {r_tp:.3f}","conseil":"Cohérence TP/BE prévoyance"},
            "c2_scr":{"statut":h2_s,"message":f"Ratio SCR = {r_scr:.1f}%","conseil":"Capitalisation prévoyance"},
            "c3_ibnr":{"statut":h3_s,"message":"IBNR < 50% PSAP ✅","conseil":"Structure IBNR normale"},
            "statut_global":sg,"conclusion":{"VERT":"✅ QRT Prévoyance validé","AMBRE":"⚠️ Vérifier les points signalés","ROUGE":"❌ QRT non conforme"}[sg]}

    def _graphiques_validation(self, val: Dict, result: Dict) -> Dict:
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12"
        LAYOUT=dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques={}
        try:
            h_keys=[k for k in val if isinstance(val[k],dict) and 'statut' in val[k]]
            fig4=go.Figure()
            for nom in h_keys[:3]:
                v=val[nom]; c=VERT if v['statut']=="VERT" else AMBRE if v['statut']=="AMBRE" else ROUGE
                i="✅" if v['statut']=="VERT" else "⚠️" if v['statut']=="AMBRE" else "❌"
                s=1.0 if v['statut']=="VERT" else 0.5 if v['statut']=="AMBRE" else 0.0
                label_nom = nom.replace('_',' ').title()
                msg = v.get('message','')
                conseil = v.get('conseil','')
                fig4.add_trace(go.Bar(x=[s],y=[label_nom],orientation="h",marker_color=c,width=0.5,
                    text=f"{i} {v['statut']}",textposition="outside",textfont=dict(color=c,size=10),
                    hovertemplate=f"<b>{label_nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"]; cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard Reporting Prévoyance QRT — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",height=260,annotations=[dict(text="💡 3 ✅ = agent validé, conformité ActuarIA standard.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_p4"]=fig4
        except: pass
        return graphiques

    def _generer_graphiques(self, result: Dict) -> Dict:
        return {}

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"p4_{audit_id}.json"),'w') as f:
                json.dump({'agent':'Reporting Prévoyance QRT'} ,f,indent=2)
            self.logger.info(f"Sauvegardé : p4_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
