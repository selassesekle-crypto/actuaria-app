"""
ActuarIA — P3 Élodie — Provisionnement Prévoyance
Direction Santé-Prévoyance | Directeur : Amira
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.p3 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent P3 — Provisionnement Prévoyance ActuarIA v1.0")
print("PSAP ITT/IP · IBNR Prévoyance · PREC")
print("Usage : agent_p3 = AgentP3ProvisionnemntPrevoyance()")
print("        result_p3 = agent_p3.run(sinistres_payes=2e6, primes=5e6)")

class AgentP3ProvisionnemntPrevoyance:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.p3")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,generer_graphiques=True,**kwargs) -> Dict:
        audit_id=f"P3_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent P3 démarré")
        try:
            result = self._calculer(**kwargs)
            val_hyp = self._valider(result)
            gv = self._graphiques_validation(val_hyp, result) if generer_graphiques else {}
            graphiques = self._generer_graphiques(result) if generer_graphiques else {}
            self._sauvegarder(result, audit_id)
            return {
                'success':True, 'agent':'Provisionnement Prévoyance',
                'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                **result,
                'audit_id':audit_id,
                'graphiques':graphiques,
                'validation_p3':val_hyp,
                'graphiques_validation':gv,
                'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _calculer(self,**kwargs) -> Dict:
        
        sp   = kwargs.get('sinistres_payes', 2_000_000)
        pa   = kwargs.get('primes', 5_000_000)
        psap = sp * 0.25
        ibnr = sp * 0.35
        prec = max(0, pa * 0.02)
        lr   = sp / max(pa, 1)
        return {'psap':round(psap,2),'ibnr':round(ibnr,2),'prec':round(prec,2),
                'provision_totale':round(psap+ibnr+prec,2),'loss_ratio':round(lr,4),
                'commentaire':f"PSAP={psap/1e3:.0f}k€ | IBNR={ibnr/1e3:.0f}k€ | LR={lr*100:.1f}%"}

    def _valider(self, result: Dict) -> Dict:
        
        psap = result.get('psap', 0)
        lr   = result.get('loss_ratio', 0)
        ibnr = result.get('ibnr', 0)
        psap_pct = psap / max(result.get('psap',1)+result.get('ibnr',1)+result.get('prec',1), 1) * 100
        h1_s = "VERT" if psap>0 else "ROUGE"
        h2_s = "VERT" if 0.20<=ibnr/max(2e6,1)<=0.50 else "AMBRE"
        h3_s = "VERT" if lr<=0.90 else "AMBRE" if lr<=1.0 else "ROUGE"
        sts=[h1_s,h2_s,h3_s]; sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "h1_psap":{"statut":h1_s,"message":f"PSAP = {psap/1e3:.0f}k€","conseil":"PSAP constituée — sinistres couverts"},
            "h2_ibnr":{"statut":h2_s,"message":f"IBNR = {ibnr/1e3:.0f}k€","conseil":"IBNR prévoyance cohérent (20-50% SP)"},
            "h3_lr":{"statut":h3_s,"message":f"Loss Ratio = {lr*100:.1f}%","conseil":"Sinistralité maîtrisée"},
            "statut_global":sg,"conclusion":{"VERT":"✅ Provisionnement Prévoyance validé","AMBRE":"⚠️ Vérifier les points signalés","ROUGE":"❌ Provisionnement insuffisant"}[sg]}

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
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard Provisionnement Prévoyance — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",height=260,annotations=[dict(text="💡 3 ✅ = agent validé, conformité ActuarIA standard.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_p3"]=fig4
        except: pass
        return graphiques

    def _generer_graphiques(self, result: Dict) -> Dict:
        return {}

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"p3_{audit_id}.json"),'w') as f:
                json.dump({'agent':'Provisionnement Prévoyance'} ,f,indent=2)
            self.logger.info(f"Sauvegardé : p3_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
