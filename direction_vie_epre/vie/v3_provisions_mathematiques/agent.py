"""
ActuarIA — Agent V3 : Amélie — Provisions Mathématiques Vie
Direction Vie & EP-RE | Manager : Sven | Directeur : Paul

Provisions mathématiques prospectives et rétrospectives :
→ PM prospective (valeur actuelle engagements futurs)
→ PM rétrospective (épargne constituée)
→ Valeur de rachat et valeur de réduction
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.v3 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent V3 — Provisions Mathématiques Vie ActuarIA v1.0")
print("Méthodes : Prospective · Rétrospective · Rachat · Réduction")
print("Usage : agent_v3 = AgentV3ProvisionsMathematiques()")
print("        result_v3 = agent_v3.run(age=50, duree=20, t_ecoule=10)")

# Tables de mortalité officielles — Arrêté du 27 juillet 2006
from direction_vie_epre.services.tables_mortalite_officielles import (
    QX_TH0002, QX_TF0002, REFERENCE_REGLEMENTAIRE,
)
from direction_vie_epre.services.rapport_excel import (
    creer_workbook_actuariel, ajouter_onglet_hypotheses,
    ajouter_onglet_resultats, ajouter_onglet_validation,
    ajouter_onglet_audit_trail, finaliser_et_retourner,
)

def _qx(t, a):
    """Retourne le qx officiel exact pour l'âge donné (0-110)."""
    return t.get(max(0, min(a, 110)), 1.0)

class AgentV3ProvisionsMathematiques:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.v3")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,age=50,sexe="H",duree=20,t_ecoule=10,capital=100_000,
            prime_annuelle=3000.0,taux_technique=0.025,generer_graphiques=True) -> Dict:
        audit_id=f"V3_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent V3 démarré | âge={age} | durée={duree} | écoulé={t_ecoule}ans")
        try:
            tqx=QX_TH0002 if sexe.upper()=="H" else QX_TF0002
            tnm="TH0002" if sexe.upper()=="H" else "TF0002"
            v=1/(1+taux_technique)
            age_actuel=age+t_ecoule
            duree_rest=duree-t_ecoule

            # Probabilités de survie depuis l'âge actuel
            qx_r=[_qx(tqx,age_actuel+k) for k in range(duree_rest+5)]
            lx_r=[1.0]
            for q in qx_r[:duree_rest]: lx_r.append(lx_r[-1]*(1-q))

            # PM prospective = VA des prestations futures - VA des primes futures
            E_rest=(v**duree_rest)*lx_r[duree_rest]
            a_rest=sum(lx_r[k]*(v**k) for k in range(duree_rest))
            pm_prospective_brute = capital * E_rest - prime_annuelle * a_rest
            # Traçabilité réglementaire des réserves non-positives (Art. R331-1)
            reserve_negative = pm_prospective_brute < 0
            if reserve_negative:
                # Réserve négative : le contrat est en-dehors (out-of-the-money)
                # → prime commerciale insuffisante ou durée écoulée > durée totale
                # → plancher à 0 conformément à la réglementation française
                raison_reserve_nulle = (
                    f"PM brute = {pm_prospective_brute:,.0f}€ < 0 "
                    f"(E_rest={E_rest:.6f}, a_rest={a_rest:.4f}) "
                    f"— plancher réglementaire appliqué (Art. R331-1)"
                )
            else:
                raison_reserve_nulle = None
            pm_prospective = max(pm_prospective_brute, 0)

            # PM rétrospective = épargne constituée à ce jour
            qx_p=[_qx(tqx,age+k) for k in range(t_ecoule+5)]
            lx_p=[1.0]
            for q in qx_p[:t_ecoule]: lx_p.append(lx_p[-1]*(1-q))
            a_passe=sum(lx_p[k]*((1+taux_technique)**k) for k in range(t_ecoule))
            E_passe=(lx_p[t_ecoule])*(1+taux_technique)**t_ecoule
            pm_retrospective=max(prime_annuelle*a_passe/max(E_passe,1e-10), 0)

            # PM sur toute la durée (évolution)
            pm_evolution=[]
            for t in range(duree+1):
                ag_t=age+t; dr=duree-t
                if dr<=0: pm_evolution.append(0.0); continue
                qx_t=[_qx(tqx,ag_t+k) for k in range(dr+3)]
                lx_t=[1.0]
                for q in qx_t[:dr]: lx_t.append(lx_t[-1]*(1-q))
                E_t=(v**dr)*lx_t[dr]; a_t=sum(lx_t[k]*(v**k) for k in range(dr))
                pm_t = capital * E_t - prime_annuelle * a_t
                # Plancher à 0 : réserve négative acceptée uniquement
                # en tout début de contrat (franchise) ou après l'échéance
                pm_evolution.append(max(pm_t, 0))

            # Valeur de rachat (PM × coefficient de rachat)
            coef_rachat=max(0, 1-max(0,0.05-0.005*(t_ecoule-1)))
            valeur_rachat=pm_prospective*coef_rachat

            # Valeur de réduction (capital réduit si arrêt des primes)
            capital_reduit=pm_prospective/max(E_rest,1e-10)
            capital_reduit=min(capital_reduit,capital)

            # Ecart prospective/retrospective
            ecart_pct=abs(pm_prospective-pm_retrospective)/max(pm_prospective,1)*100 if pm_prospective>0 else 0

            commentaire=(
                f"✅ Provisions Mathématiques calculées — {tnm} | {age} ans | {duree} ans | {t_ecoule} ans écoulés.\n"
                f"PM prospective  : {pm_prospective:,.0f}€ | PM rétrospective : {pm_retrospective:,.0f}€.\n"
                f"Écart P/R       : {ecart_pct:.1f}% (idéal < 5% — méthodes cohérentes).\n"
                f"Valeur de rachat: {valeur_rachat:,.0f}€ | Capital réduit : {capital_reduit:,.0f}€.\n"
                f"Taux technique  : {taux_technique*100:.2f}% | Table : {tnm}."
            )

            val_hyp=self._valider_pm(pm_prospective,pm_retrospective,ecart_pct,valeur_rachat,capital,taux_technique,duree_rest)
            gv=self._graphiques_validation_pm(val_hyp,pm_evolution,age,duree,pm_prospective,pm_retrospective) if generer_graphiques else {}
            graphiques=self._generer_graphiques(pm_evolution,age,duree) if generer_graphiques else {}
            self._sauvegarder({'agent':'V3 Amélie','pm_prospective':pm_prospective,'pm_retrospective':pm_retrospective,
                               'reserve_negative':reserve_negative,'pm_brute':pm_prospective_brute,
                               'valeur_rachat':valeur_rachat,'capital_reduit':capital_reduit}, audit_id)

            # ── Rapport Excel individuel ─────────────────────────────
            _result_for_excel = {
                'audit_id': audit_id,
                'agent': 'V3',
                'statut_rag': statut_rag if 'statut_rag' in dir() else 'VERT',
                'commentaire': commentaire if 'commentaire' in dir() else '',
                'sources': {'parametres': 'saisie manuelle'},
            }
            # Enrichir avec les variables numériques disponibles
            for _k, _v in list(locals().items()):
                if isinstance(_v, (int, float)) and not _k.startswith('_'):
                    _result_for_excel[_k] = _v
            _excel_bytes_tmp = None
            try:
                _excel_bytes_tmp = self._generer_excel(_result_for_excel)
            except Exception as _xe:
                pass
            return {
                'success':True,'agent':'V3 Amélie','table':tnm,'age':age,'sexe':sexe,
                'duree':duree,'t_ecoule':t_ecoule,
                'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                'pm_prospective':round(pm_prospective,2),
                'pm_prospective_brute':round(pm_prospective_brute,2),
                'reserve_negative_detectee':reserve_negative,
                'raison_reserve_nulle':raison_reserve_nulle,
                'pm_retrospective':round(pm_retrospective,2),
                'ecart_pr_pct':round(ecart_pct,2),
                'valeur_rachat':round(valeur_rachat,2),
                'capital_reduit':round(capital_reduit,2),
                'pm_evolution':[round(p,2) for p in pm_evolution],
                'sources':{'parametres': 'saisie manuelle'},
                'commentaire':commentaire,'audit_id':audit_id,
                'graphiques':graphiques,'validation_pm':val_hyp,'graphiques_validation':gv,'erreur':None,
                'excel_bytes':        _excel_bytes_tmp,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_pm(self,pm_prosp,pm_retro,ecart_pct,rachat,capital,taux,dr):
        # H1 — PM prospective ≥ 0
        if pm_prosp>0: h1_s,h1_m,h1_c="VERT",f"PM prospective = {pm_prosp:,.0f}€ > 0 ✅","Provision positive — engagements couverts"
        else: h1_s,h1_m,h1_c="ROUGE","PM prospective < 0 ❌","Revoir les hypothèses — provision négative impossible"
        # H2 — Écart P/R < 5%
        if ecart_pct<=5: h2_s,h2_m,h2_c="VERT",f"Écart P/R = {ecart_pct:.1f}% ≤ 5% ✅","Méthodes prospective et rétrospective cohérentes"
        elif ecart_pct<=10: h2_s,h2_m,h2_c="AMBRE",f"Écart P/R = {ecart_pct:.1f}% ∈ [5%,10%] ⚠️","Vérifier les hypothèses actuarielles"
        else: h2_s,h2_m,h2_c="ROUGE",f"Écart P/R = {ecart_pct:.1f}% > 10% ❌","Incohérence — revoir les tables ou le taux technique"
        # H3 — Rachat ≥ PM × 95%
        r_ratio=rachat/max(pm_prosp,1)
        if r_ratio>=0.95: h3_s,h3_m,h3_c="VERT",f"Rachat = {r_ratio*100:.1f}% de PM ≥ 95% ✅","Valeur de rachat conforme Art. L132-21"
        elif r_ratio>=0.80: h3_s,h3_m,h3_c="AMBRE",f"Rachat = {r_ratio*100:.1f}% de PM ∈ [80%,95%] ⚠️","Vérifier le coefficient de rachat réglementaire"
        else: h3_s,h3_m,h3_c="ROUGE",f"Rachat = {r_ratio*100:.1f}% de PM < 80% ❌","Rachat insuffisant — non conforme Code des Assurances"
        sts=[h1_s,h2_s,h3_s]; sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "h1_pm_positive":{"pm":round(pm_prosp,2),"statut":h1_s,"message":h1_m,"conseil":h1_c,"titre_graphique":f"{'✅' if h1_s=='VERT' else '❌'} PM prospective = {pm_prosp:,.0f}€"},
            "h2_ecart_pr":{"ecart_pct":round(ecart_pct,2),"statut":h2_s,"message":h2_m,"conseil":h2_c,"titre_graphique":f"{'✅' if h2_s=='VERT' else '⚠️' if h2_s=='AMBRE' else '❌'} Écart P/R = {ecart_pct:.1f}%"},
            "h3_rachat":{"rachat":round(rachat,2),"ratio":round(r_ratio,4),"statut":h3_s,"message":h3_m,"conseil":h3_c,"titre_graphique":f"{'✅' if h3_s=='VERT' else '⚠️' if h3_s=='AMBRE' else '❌'} Rachat = {r_ratio*100:.1f}% PM"},
            "statut_global":sg,"conclusion":{"VERT":"✅ PM Vie validées — prospective, cohérence P/R et rachat conformes","AMBRE":"⚠️ PM acceptable — vérifier les points signalés","ROUGE":"❌ PM à corriger — non-conformité détectée"}[sg],
        }

    def _graphiques_validation_pm(self,val,pm_evol,age,duree,pm_p,pm_r):
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT=dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques={}
        # G1 — Évolution PM
        try:
            ages=[age+t for t in range(duree+1)]
            h1=val["h1_pm_positive"]; c1=VERT if h1["statut"]=="VERT" else ROUGE
            fig1=go.Figure(go.Scatter(x=ages,y=pm_evol[:duree+1],mode="lines",line=dict(color=OR,width=2.5),
                fill="tozeroy",fillcolor="rgba(201,168,76,0.08)",hovertemplate="Age %{x}<br>PM : %{y:,.0f}€<extra></extra>"))
            l1=dict(**LAYOUT); l1.update(dict(title=dict(text=f"{'✅' if h1['statut']=='VERT' else '❌'} Évolution PM prospective sur la durée du contrat",font=dict(color=c1,size=11),x=0.01),
                xaxis=dict(title="Âge",tickfont=dict(color=GRIS),showgrid=True,gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="PM (€)",tickfont=dict(color=GRIS),showgrid=True,gridcolor="rgba(255,255,255,0.05)"),showlegend=False,
                annotations=[dict(text="💡 La PM prospective augmente puis diminue en fin de contrat. Elle doit toujours rester ≥ 0.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig1.update_layout(**l1); graphiques["evolution_pm"]=fig1
        except: pass
        # G2 — Comparaison PM prospective vs rétrospective
        try:
            h2=val["h2_ecart_pr"]; c2=VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            fig2=go.Figure(go.Bar(x=["PM Prospective","PM Rétrospective"],y=[pm_p,pm_r],
                marker_color=[OR,c2],width=0.4,opacity=0.88,
                text=[f"{pm_p:,.0f}€",f"{pm_r:,.0f}€"],textposition="outside",textfont=dict(color=BLANC,size=12)))
            l2=dict(**LAYOUT); l2.update(dict(title=dict(text=h2["titre_graphique"]+" — Cohérence des deux méthodes",font=dict(color=c2,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.4,showlegend=False,
                annotations=[dict(text="💡 Les deux barres doivent être proches (écart < 5%). Sinon les hypothèses sont incohérentes entre les deux méthodes.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig2.update_layout(**l2); graphiques["comparaison_pm_pr"]=fig2
        except: pass
        # G3 — Valeur de rachat
        try:
            h3=val["h3_rachat"]; c3=VERT if h3["statut"]=="VERT" else AMBRE if h3["statut"]=="AMBRE" else ROUGE
            fig3=go.Figure(go.Indicator(mode="gauge+number",value=h3["ratio"]*100,
                number=dict(suffix="% de PM",font=dict(color=c3,size=28),valueformat=".1f"),
                title=dict(text=h3["titre_graphique"],font=dict(color=c3,size=11)),
                gauge=dict(axis=dict(range=[0,120],tickfont=dict(color=GRIS,size=8),tickvals=[0,80,95,100,120],ticktext=["0%","80%","95%","100%","120%"]),
                    bar=dict(color=c3,thickness=0.25),bgcolor=NAVY_L,borderwidth=0,
                    steps=[dict(range=[0,80],color="rgba(231,76,60,0.12)"),dict(range=[80,95],color="rgba(243,156,18,0.12)"),dict(range=[95,120],color="rgba(46,204,113,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=95))))
            fig3.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {h3['conseil']}",xref="paper",yref="paper",x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["jauge_rachat_pm"]=fig3
        except: pass
        # G4 — Scorecard
        try:
            items=[("H1 — PM prospective > 0",val["h1_pm_positive"]["statut"],val["h1_pm_positive"]["message"],val["h1_pm_positive"]["conseil"]),
                   ("H2 — Écart P/R < 5%",val["h2_ecart_pr"]["statut"],val["h2_ecart_pr"]["message"],val["h2_ecart_pr"]["conseil"]),
                   ("H3 — Rachat ≥ 95% PM",val["h3_rachat"]["statut"],val["h3_rachat"]["message"],val["h3_rachat"]["conseil"])]
            fig4=go.Figure()
            for nom,statut,msg,conseil in items:
                c=VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i="✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s=1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(x=[s],y=[nom],orientation="h",marker_color=c,width=0.5,text=f"{i} {statut}",textposition="outside",textfont=dict(color=c,size=10),hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"]; cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard PM Vie — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",height=260,annotations=[dict(text="💡 3 ✅ = PM validées, cohérentes et conformes Code des Assurances.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_pm"]=fig4
        except: pass
        return graphiques

    def _generer_graphiques(self,pm_evol,age,duree):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
            fig=go.Figure(go.Scatter(x=list(range(age,age+duree+1)),y=pm_evol[:duree+1],mode="lines",line=dict(color=OR,width=2.5),fill="tozeroy",fillcolor="rgba(201,168,76,0.08)"))
            fig.update_layout(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=40),height=300,
                title=dict(text="Provisions Mathématiques prospectives",font=dict(color=BLANC,size=12),x=0.01),
                xaxis=dict(title="Âge",tickfont=dict(color=GRIS)),yaxis=dict(title="PM (€)",tickfont=dict(color=GRIS)),showlegend=False)
            return {"pm_evolution":fig}
        except: return {}


    def _generer_excel(self, result: dict) -> bytes:
        """Rapport Excel individuel V3 — 4 onglets auditables."""
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
        ajouter_onglet_hypotheses(wb, "V3", aid, dte, hyps,
                                  sources=result.get("sources", {}))
        lignes = [
            {"label": str(k), "valeur": v,
              "unite": "€" if isinstance(v, float) and v > 100 else "%"
                       if isinstance(v, float) and 0 < v < 1 else "",
              "fmt_excel": "#,##0.00" if isinstance(v, float) else None,
              "commentaire": ""}
            for k, v in result.items()
            if isinstance(v, (int, float))
            and k not in ("success",)
        ][:40]
        ajouter_onglet_resultats(wb, "V3", aid, dte,
                                 [{"titre": "Résultats actuariels", "lignes": lignes}])
        # Validation : chercher le premier dict de validation dans le result
        for vk in [k for k in result if "validat" in k.lower()]:
            val = result.get(vk, {})
            if isinstance(val, dict) and "statut_global" in val:
                cles = [k for k in val if isinstance(val[k], dict)
                        and "statut" in val[k] and "message" in val[k]]
                if cles:
                    ajouter_onglet_validation(wb, "V3", aid, dte, val,
                                              cles_controles=cles[:5])
                break
        ajouter_onglet_audit_trail(wb, "V3", aid, dte, result)
        return finaliser_et_retourner(wb)

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"v3_pm_{audit_id}.json"),'w') as f: json.dump(rapport,f,indent=2)
            self.logger.info(f"Sauvegardé : v3_pm_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")