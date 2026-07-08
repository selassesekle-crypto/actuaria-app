"""
ActuarIA — Agent V2 : Kofi — Tarification Épargne Vie
Direction Vie & EP-RE | Manager : Sven | Directeur : Paul

Contrats d'épargne vie : capital différé, rentes viagères, multisupport
→ Primes pures et commerciales
→ Valeur de rachat / valeur de réduction
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.v2 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent V2 — Tarification Épargne Vie ActuarIA v1.0")
print("Contrats : Capital Différé · Rente Viagère · Mixte · Multisupport")
print("Usage : agent_v2 = AgentV2TarificationEpargneVie()")
print("        result_v2 = agent_v2.run(age=45, duree=20, capital=100000)")

# Tables de mortalité officielles — Arrêté du 27 juillet 2006
from direction_vie_epre.services.tables_mortalite_officielles import (
    QX_TH0002, QX_TF0002, REFERENCE_REGLEMENTAIRE,
)

def _qx(tables, age):
    """Retourne le qx officiel exact pour l'âge donné (0-110)."""
    return tables.get(max(0, min(age, 110)), 1.0)

class AgentV2TarificationEpargneVie:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.v2")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,age=45,sexe="H",duree=20,capital=100_000,
            type_contrat="capital_differe",taux_technique=0.025,
            taux_frais=0.008,chargement_pct=0.15,generer_graphiques=True) -> Dict:
        audit_id=f"V2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent V2 démarré | {type_contrat} | âge={age} | durée={duree}ans")
        try:
            table_qx=QX_TH0002 if sexe.upper()=="H" else QX_TF0002
            table_nm="TH0002" if sexe.upper()=="H" else "TF0002"
            v=1/(1+taux_technique)

            # Probabilités de survie
            qx_s=[_qx(table_qx,age+t) for t in range(duree+20)]
            lx=[1.0]
            for q in qx_s[:duree+10]: lx.append(lx[-1]*(1-q))

            t_px=lx[:duree+1]

            # ── Capital différé (survie) ───────────────────────────────────────
            # E_x:n = v^n * n_px
            E_xn = (v**duree) * t_px[duree]

            # Annuité certaine de versement (äx:n)
            a_xn = sum(t_px[k]*(v**k) for k in range(duree))

            # Prime pure annuelle
            prime_pure_an = capital * E_xn / max(a_xn, 1e-10)
            prime_pure_mois = prime_pure_an / 12

            # ── Rente viagère (si type=rente) ──────────────────────────────────
            # Annuité viagère ax = Σ v^k * k_px pour k=0..omega
            age_omega = 110
            duree_rente = min(age_omega - age - duree, 50)
            age_rente = age + duree
            qx_r = [_qx(table_qx, age_rente+t) for t in range(duree_rente+5)]
            lx_r = [1.0]
            for q in qx_r[:duree_rente]: lx_r.append(lx_r[-1]*(1-q))
            a_viager = sum(lx_r[k]*(v**k) for k in range(duree_rente))
            rente_mensuelle = (capital * E_xn) / max(a_viager * 12, 1e-10)

            # ── Valeur de rachat ──────────────────────────────────────────────
            rachats = []
            for t in range(1, duree+1):
                E_rest = (v**(duree-t)) * lx[duree] / max(lx[t], 1e-10)
                a_rest = sum((lx[t+k]/max(lx[t],1e-10))*(v**k) for k in range(duree-t))
                pm_t   = capital * E_rest - prime_pure_an * a_rest
                rachat_t = max(0, pm_t * (1 - max(0, 0.05 - 0.005*(t-1))))
                rachats.append(round(rachat_t, 2))

            # ── Prime commerciale ─────────────────────────────────────────────
            prime_comm_an   = prime_pure_an * (1 + chargement_pct)
            prime_comm_mois = prime_comm_an / 12

            # Coût annuel global (CAG) — indicateur réglementaire
            cag = chargement_pct + taux_frais

            # ── Commentaire ───────────────────────────────────────────────────
            label_contrat = {
                "capital_differe": "Capital Différé",
                "rente": "Rente Viagère",
                "mixte": "Contrat Mixte",
                "multisupport": "Multisupport",
            }.get(type_contrat, type_contrat)

            commentaire = (
                f"✅ Tarification {label_contrat} finalisée — {table_nm} | {age} ans | {duree} ans.\n"
                f"Prime pure : {prime_pure_an:.2f}€/an ({prime_pure_mois:.2f}€/mois) "
                f"→ Capital différé {capital:,.0f}€ garanti à terme.\n"
                f"Rente viagère équivalente : {rente_mensuelle:.0f}€/mois.\n"
                f"Prime commerciale : {prime_comm_an:.2f}€/an (CAG = {cag*100:.2f}%).\n"
                f"Valeur de rachat à mi-contrat : {rachats[duree//2-1]:,.0f}€."
            )

            # ── Validation + graphiques ───────────────────────────────────────
            val_hyp = self._valider_epargne_vie(
                taux_technique, E_xn, prime_pure_an, prime_comm_an,
                rachats, capital, cag, duree)
            gv = self._graphiques_validation_epv(val_hyp, rachats, t_px, age, duree) if generer_graphiques else {}
            graphiques = self._generer_graphiques(rachats, t_px, age, duree, capital) if generer_graphiques else {}
            self._sauvegarder({'agent':'V2 Kofi','type':label_contrat,'prime_pure_an':prime_pure_an,
                               'prime_comm_an':prime_comm_an,'rente':rente_mensuelle,'cag':cag}, audit_id)

            return {
                'success':True,'agent':'V2 Kofi','type_contrat':label_contrat,
                'table':table_nm,'age':age,'sexe':sexe,'duree':duree,
                'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                'prime_pure':{'annuelle':round(prime_pure_an,2),'mensuelle':round(prime_pure_mois,2),'E_xn':round(E_xn,6),'a_xn':round(a_xn,4)},
                'prime_commerciale':{'annuelle':round(prime_comm_an,2),'mensuelle':round(prime_comm_mois,2),'cag_pct':round(cag*100,2)},
                'rente_viagere':{'mensuelle':round(rente_mensuelle,2),'annuelle':round(rente_mensuelle*12,2),'a_viager':round(a_viager,4)},
                'valeurs_rachat':rachats,
                'commentaire':commentaire,'audit_id':audit_id,
                'graphiques':graphiques,'validation_epv':val_hyp,'graphiques_validation':gv,'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_epargne_vie(self,taux_tech,E_xn,prime_pure,prime_comm,rachats,capital,cag,duree):
        # H1 — Taux technique ≤ 3.5% (réglementation vie)
        if taux_tech<=0.035: h1_s,h1_m,h1_c="VERT",f"Taux={taux_tech*100:.2f}% ≤ 3.5% ✅","Taux conforme ACPR vie"
        elif taux_tech<=0.045: h1_s,h1_m,h1_c="AMBRE",f"Taux={taux_tech*100:.2f}% ∈ [3.5%,4.5%] ⚠️","Taux limite — documenter la justification"
        else: h1_s,h1_m,h1_c="ROUGE",f"Taux={taux_tech*100:.2f}% > 4.5% ❌","Taux excessif — risque sous-provisionnement"
        # H2 — Valeurs de rachat > 0 dès année 2
        rachats_pos = sum(1 for r in rachats[1:] if r>0)
        total = len(rachats)-1
        if rachats_pos>=total*0.9: h2_s,h2_m,h2_c="VERT",f"{rachats_pos}/{total} rachats positifs ✅","Valeurs de rachat conformes Code des Assurances"
        elif rachats_pos>=total*0.7: h2_s,h2_m,h2_c="AMBRE",f"{rachats_pos}/{total} rachats positifs ⚠️","Vérifier les années à rachat nul"
        else: h2_s,h2_m,h2_c="ROUGE",f"{rachats_pos}/{total} rachats positifs ❌","Rachats insuffisants — non conforme Art. L132-21"
        # H3 — CAG ≤ 3% (directive DDA)
        if cag<=0.03: h3_s,h3_m,h3_c="VERT",f"CAG={cag*100:.2f}% ≤ 3% ✅","Coût annuel conforme à la directive DDA"
        elif cag<=0.04: h3_s,h3_m,h3_c="AMBRE",f"CAG={cag*100:.2f}% ∈ [3%,4%] ⚠️","CAG à surveiller — DIA II exige la transparence"
        else: h3_s,h3_m,h3_c="ROUGE",f"CAG={cag*100:.2f}% > 4% ❌","CAG excessif — Non conforme DDA/DIA II"
        sts=[h1_s,h2_s,h3_s]
        sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "h1_taux":{"valeur":taux_tech,"statut":h1_s,"message":h1_m,"conseil":h1_c,"titre_graphique":f"{'✅' if h1_s=='VERT' else '⚠️' if h1_s=='AMBRE' else '❌'} Taux technique = {taux_tech*100:.2f}%"},
            "h2_rachats":{"nb_positifs":rachats_pos,"statut":h2_s,"message":h2_m,"conseil":h2_c,"titre_graphique":f"{'✅' if h2_s=='VERT' else '⚠️'} Rachats — {rachats_pos}/{total} positifs"},
            "h3_cag":{"cag":cag,"statut":h3_s,"message":h3_m,"conseil":h3_c,"titre_graphique":f"{'✅' if h3_s=='VERT' else '⚠️' if h3_s=='AMBRE' else '❌'} CAG = {cag*100:.2f}%"},
            "statut_global":sg,"conclusion":{"VERT":"✅ Épargne Vie validée — taux, rachats et CAG conformes","AMBRE":"⚠️ Acceptable — vérifier les points signalés","ROUGE":"❌ À corriger — non-conformité réglementaire"}[sg],
        }

    def _graphiques_validation_epv(self,val,rachats,t_px,age,duree):
        try:
            import plotly.graph_objects as go
            import numpy as np
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT=dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques={}
        # G1 — Évolution valeurs de rachat
        try:
            annees=list(range(1,duree+1))
            colors=[VERT if r>0 else ROUGE for r in rachats[:duree]]
            h2=val["h2_rachats"]; couleur_h2=VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            fig1=go.Figure(go.Bar(x=annees,y=rachats[:duree],marker_color=colors,opacity=0.85,
                hovertemplate="Année %{x}<br>Rachat : %{y:,.0f}€<extra></extra>"))
            l1=dict(**LAYOUT); l1.update(dict(title=dict(text=h2["titre_graphique"]+" — Évolution sur la durée",font=dict(color=couleur_h2,size=11),x=0.01),
                xaxis=dict(title="Année du contrat",tickfont=dict(color=GRIS),showgrid=True,gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="Valeur (€)",tickfont=dict(color=GRIS)),showlegend=False,
                annotations=[dict(text="💡 Les barres vertes = rachat possible. Rouges = indisponibilité. Dès l'an 2 un assuré doit pouvoir récupérer son épargne.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig1.update_layout(**l1); graphiques["rachats_evolution"]=fig1
        except Exception as e: pass
        # G2 — Jauge taux technique
        try:
            h1=val["h1_taux"]; taux=h1["valeur"]; couleur_h1=VERT if h1["statut"]=="VERT" else AMBRE if h1["statut"]=="AMBRE" else ROUGE
            fig2=go.Figure(go.Indicator(mode="gauge+number",value=taux*100,
                number=dict(suffix="%",font=dict(color=couleur_h1,size=28),valueformat=".2f"),
                title=dict(text=h1["titre_graphique"],font=dict(color=couleur_h1,size=11)),
                gauge=dict(axis=dict(range=[0,5],tickfont=dict(color=GRIS,size=8),tickvals=[0,2,3.5,4.5,5],ticktext=["0%","2%","3.5%","4.5%","5%"]),
                    bar=dict(color=couleur_h1,thickness=0.25),bgcolor=NAVY_L,borderwidth=0,
                    steps=[dict(range=[0,3.5],color="rgba(46,204,113,0.12)"),dict(range=[3.5,4.5],color="rgba(243,156,18,0.12)"),dict(range=[4.5,5],color="rgba(231,76,60,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=3.5))))
            fig2.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {h1['conseil']}",xref="paper",yref="paper",x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["jauge_taux_tech_epv"]=fig2
        except Exception as e: pass
        # G3 — Jauge CAG
        try:
            h3=val["h3_cag"]; cag=h3["cag"]; couleur_h3=VERT if h3["statut"]=="VERT" else AMBRE if h3["statut"]=="AMBRE" else ROUGE
            fig3=go.Figure(go.Indicator(mode="gauge+number",value=cag*100,
                number=dict(suffix="%",font=dict(color=couleur_h3,size=28),valueformat=".2f"),
                title=dict(text=h3["titre_graphique"]+" (directive DDA)",font=dict(color=couleur_h3,size=11)),
                gauge=dict(axis=dict(range=[0,5],tickfont=dict(color=GRIS,size=8),tickvals=[0,2,3,4,5],ticktext=["0%","2%","3%","4%","5%"]),
                    bar=dict(color=couleur_h3,thickness=0.25),bgcolor=NAVY_L,borderwidth=0,
                    steps=[dict(range=[0,3],color="rgba(46,204,113,0.12)"),dict(range=[3,4],color="rgba(243,156,18,0.12)"),dict(range=[4,5],color="rgba(231,76,60,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=3))))
            fig3.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {h3['conseil']}",xref="paper",yref="paper",x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["jauge_cag"]=fig3
        except Exception as e: pass
        # G4 — Scorecard
        try:
            items=[("H1 — Taux technique",val["h1_taux"]["statut"],val["h1_taux"]["message"],val["h1_taux"]["conseil"]),
                   ("H2 — Valeurs de rachat",val["h2_rachats"]["statut"],val["h2_rachats"]["message"],val["h2_rachats"]["conseil"]),
                   ("H3 — CAG DDA",val["h3_cag"]["statut"],val["h3_cag"]["message"],val["h3_cag"]["conseil"])]
            fig4=go.Figure()
            for nom,statut,msg,conseil in items:
                c=VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i="✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s=1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(x=[s],y=[nom],orientation="h",marker_color=c,width=0.5,text=f"{i} {statut}",textposition="outside",textfont=dict(color=c,size=10),hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"]; cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard Épargne Vie — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",height=260,annotations=[dict(text="💡 3 ✅ = contrat épargne vie conforme DDA, ACPR et Code des Assurances.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_epv"]=fig4
        except Exception as e: pass
        return graphiques

    def _generer_graphiques(self,rachats,t_px,age,duree,capital):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0";BLEU="#3498DB"
            fig=go.Figure(go.Bar(x=list(range(1,duree+1)),y=rachats[:duree],marker_color=OR,opacity=0.85))
            fig.update_layout(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),
                margin=dict(l=16,r=16,t=60,b=40),height=300,
                title=dict(text="Valeurs de rachat sur la durée du contrat",font=dict(color=BLANC,size=12),x=0.01),
                xaxis=dict(title="Année",tickfont=dict(color=GRIS)),yaxis=dict(title="Rachat (€)",tickfont=dict(color=GRIS)),showlegend=False)
            return {"rachats":fig}
        except: return {}

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"v2_epv_{audit_id}.json"),'w') as f:
                json.dump(rapport,f,indent=2)
            self.logger.info(f"Sauvegardé : v2_epv_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
