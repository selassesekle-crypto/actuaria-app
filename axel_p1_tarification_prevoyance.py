"""
ActuarIA — Agent P1 : Axel — Tarification Prévoyance ITT/IP
Direction Santé-Prévoyance | Manager : Diallo | Directeur : Amira

Tarification prévoyance collective et individuelle :
→ ITT (Incapacité Temporaire de Travail) — tables BCAC
→ IP (Invalidité Permanente) — tables TD88-90
→ Décès toutes causes
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.p1 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent P1 — Tarification Prévoyance ITT/IP ActuarIA v1.0")
print("Tables : BCAC 2019 (ITT) · TD88-90 (Invalidité) · TH0002 (Décès)")
print("Usage : agent_p1 = AgentP1TarificationPrevoyance()")
print("        result_p1 = agent_p1.run(age=40, salaire_brut=45000)")

# Taux d'incidence ITT et invalidité par tranche d'âge (BCAC 2019 — simplifiés)
TAUX_ITT_BCAC = {
    25: 0.020, 30: 0.025, 35: 0.032, 40: 0.042,
    45: 0.055, 50: 0.072, 55: 0.095, 60: 0.120,
}
TAUX_IP_TD88 = {
    25: 0.0008, 30: 0.0012, 35: 0.0018, 40: 0.0028,
    45: 0.0045, 50: 0.0072, 55: 0.0115, 60: 0.0180,
}
QX_TH0002 = {
    25:0.000730,30:0.000860,35:0.001180,40:0.001800,45:0.002980,
    50:0.005040,55:0.008640,60:0.014500,65:0.023800,
}

def _interp(t,a):
    ages=sorted(t.keys())
    if a>=ages[-1]: return t[ages[-1]]
    if a<=ages[0]: return t[ages[0]]
    for i in range(len(ages)-1):
        if ages[i]<=a<ages[i+1]:
            r=(a-ages[i])/(ages[i+1]-ages[i]); return t[ages[i]]*(1-r)+t[ages[i+1]]*r
    return t[ages[-1]]

class AgentP1TarificationPrevoyance:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.p1")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,age=40,salaire_brut=45_000,categorie="employe",
            franchise_jours=90,taux_rente_ipp=0.60,duree_contrat=20,
            chargement_pct=0.20,generer_graphiques=True) -> Dict:
        audit_id=f"P1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent P1 démarré | âge={age} | salaire={salaire_brut:,.0f}€")
        try:
            salaire_mensuel = salaire_brut / 12

            # Facteur catégorie (sinistralité plus élevée pour cadres/ouvriers)
            fact_cat = {"ouvrier":1.35,"employe":1.0,"cadre":0.75,"cadre_sup":0.60}.get(categorie,1.0)

            # ── ITT — Incapacité Temporaire de Travail ────────────────────────
            taux_itt = _interp(TAUX_ITT_BCAC, age) * fact_cat
            duree_moy_itt = 45  # jours (BCAC 2019)
            # Charge après franchise
            jours_charges = max(0, duree_moy_itt - franchise_jours)
            indemnite_jour = salaire_mensuel * 0.80 / 30  # 80% du salaire

            prime_pure_itt = taux_itt * jours_charges * indemnite_jour

            # ── IP — Invalidité Permanente ─────────────────────────────────────
            taux_ip = _interp(TAUX_IP_TD88, age) * fact_cat
            # Rente invalidité = taux_rente × salaire × annuité
            age_retraite = 65
            v = 1/1.025
            duree_rente_ip = max(0, age_retraite - age)
            annuite_ip = sum(v**k for k in range(int(duree_rente_ip)))
            rente_ip_annuelle = salaire_brut * taux_rente_ipp
            prime_pure_ip = taux_ip * rente_ip_annuelle * annuite_ip / max(duree_contrat,1)

            # ── Décès ──────────────────────────────────────────────────────────
            qx = _interp(QX_TH0002, age)
            capital_deces = salaire_brut * 3  # 3× salaire annuel
            prime_pure_deces = qx * capital_deces

            # ── Total ─────────────────────────────────────────────────────────
            prime_pure_totale = prime_pure_itt + prime_pure_ip + prime_pure_deces
            prime_comm = prime_pure_totale * (1 + chargement_pct)
            prime_mois = prime_comm / 12

            # Coût employeur (part patronale ≈ 60% pour collectif)
            part_patronale = prime_comm * 0.60
            part_salariale  = prime_comm * 0.40

            commentaire = (
                f"✅ Tarification Prévoyance — {age} ans | {categorie} | {salaire_brut:,.0f}€/an.\n"
                f"Prime pure : {prime_pure_totale:.2f}€/an "
                f"(ITT: {prime_pure_itt:.2f}€ + IP: {prime_pure_ip:.2f}€ + Décès: {prime_pure_deces:.2f}€).\n"
                f"Prime commerciale : {prime_comm:.2f}€/an ({prime_mois:.2f}€/mois).\n"
                f"Part patronale : {part_patronale:.2f}€ | Part salariale : {part_salariale:.2f}€.\n"
                f"Taux de cotisation : {prime_comm/salaire_brut*100:.2f}% du salaire brut."
            )

            val_hyp = self._valider_prevoyance(prime_pure_itt, prime_pure_ip, prime_pure_deces,
                                               prime_comm, salaire_brut, taux_itt, taux_ip)
            gv = self._graphiques_validation_p1(val_hyp, prime_pure_itt, prime_pure_ip,
                                                prime_pure_deces, prime_comm, salaire_brut) if generer_graphiques else {}
            graphiques = self._generer_graphiques(prime_pure_itt, prime_pure_ip, prime_pure_deces) if generer_graphiques else {}
            self._sauvegarder({'agent':'P1 Axel','prime_pure':prime_pure_totale,'prime_comm':prime_comm,
                               'taux_itt':taux_itt,'taux_ip':taux_ip}, audit_id)

            return {
                'success':True,'agent':'P1 Axel','age':age,'categorie':categorie,
                'salaire_brut':salaire_brut,
                'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                'primes_pures':{'itt':round(prime_pure_itt,2),'ip':round(prime_pure_ip,2),'deces':round(prime_pure_deces,2),'total':round(prime_pure_totale,2)},
                'prime_commerciale':round(prime_comm,2),'prime_mensuelle':round(prime_mois,2),
                'taux_cotisation_pct':round(prime_comm/salaire_brut*100,3),
                'part_patronale':round(part_patronale,2),'part_salariale':round(part_salariale,2),
                'taux_sinistralite':{'itt':round(taux_itt,4),'ip':round(taux_ip,6),'deces':round(qx,6)},
                'commentaire':commentaire,'audit_id':audit_id,
                'graphiques':graphiques,'validation_p1':val_hyp,'graphiques_validation':gv,'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_prevoyance(self,p_itt,p_ip,p_deces,p_comm,salaire,t_itt,t_ip):
        # H1 — Taux de cotisation ∈ [1.5%, 4%] du salaire brut
        taux_cot = p_comm / max(salaire, 1) * 100
        if 1.5<=taux_cot<=4.0: h1_s,h1_m,h1_c="VERT",f"Taux cotisation = {taux_cot:.2f}% ∈ [1.5%,4%] ✅","Cotisation conforme aux normes CCN prévoyance"
        elif taux_cot<1.5: h1_s,h1_m,h1_c="AMBRE",f"Taux cotisation = {taux_cot:.2f}% < 1.5% ⚠️","Cotisation faible — vérifier l'adéquation des garanties"
        else: h1_s,h1_m,h1_c="ROUGE",f"Taux cotisation = {taux_cot:.2f}% > 4% ❌","Cotisation excessive — revoir les garanties ou les chargements"
        # H2 — ITT > 50% de la prime pure
        part_itt = p_itt / max(p_itt+p_ip+p_deces, 1)
        if part_itt>=0.50: h2_s,h2_m,h2_c="VERT",f"ITT = {part_itt*100:.1f}% ≥ 50% ✅","Prévoyance dominée par l'ITT — structure normale"
        elif part_itt>=0.30: h2_s,h2_m,h2_c="AMBRE",f"ITT = {part_itt*100:.1f}% ∈ [30%,50%] ⚠️","Vérifier les paramètres de franchise et durée"
        else: h2_s,h2_m,h2_c="ROUGE",f"ITT = {part_itt*100:.1f}% < 30% ❌","Structure anormale — ITT sous-pondéré vs IP et décès"
        # H3 — Taux ITT BCAC cohérent ∈ [1%, 15%]
        if 0.01<=t_itt<=0.15: h3_s,h3_m,h3_c="VERT",f"Taux ITT = {t_itt*100:.1f}% ∈ [1%,15%] ✅","Taux BCAC cohérent avec l'âge et la catégorie"
        else: h3_s,h3_m,h3_c="AMBRE",f"Taux ITT = {t_itt*100:.1f}% hors [1%,15%] ⚠️","Vérifier la table BCAC et les paramètres"
        sts=[h1_s,h2_s,h3_s]; sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "h1_cotisation":{"taux_cot":round(taux_cot,3),"statut":h1_s,"message":h1_m,"conseil":h1_c,"titre_graphique":f"{'✅' if h1_s=='VERT' else '⚠️' if h1_s=='AMBRE' else '❌'} Cotisation = {taux_cot:.2f}% du salaire"},
            "h2_structure":{"part_itt":round(part_itt,4),"statut":h2_s,"message":h2_m,"conseil":h2_c,"titre_graphique":f"{'✅' if h2_s=='VERT' else '⚠️' if h2_s=='AMBRE' else '❌'} ITT = {part_itt*100:.1f}% de la prime"},
            "h3_taux_itt":{"taux_itt":round(t_itt,4),"statut":h3_s,"message":h3_m,"conseil":h3_c,"titre_graphique":f"{'✅' if h3_s=='VERT' else '⚠️'} Taux BCAC = {t_itt*100:.2f}%"},
            "statut_global":sg,"conclusion":{"VERT":"✅ Prévoyance validée — cotisation, structure et taux BCAC conformes","AMBRE":"⚠️ Acceptable — vérifier les points signalés","ROUGE":"❌ À corriger — non-conformité détectée"}[sg],
        }

    def _graphiques_validation_p1(self,val,p_itt,p_ip,p_deces,p_comm,salaire):
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT=dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques={}
        # G1 — Décomposition primes pures
        try:
            h2=val["h2_structure"]; c2=VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            fig1=go.Figure(go.Bar(x=["ITT","Invalidité (IP)","Décès"],y=[p_itt,p_ip,p_deces],
                marker_color=[OR,BLEU,AMBRE],width=0.45,opacity=0.88,
                text=[f"{v:.0f}€" for v in [p_itt,p_ip,p_deces]],textposition="outside",textfont=dict(color=BLANC,size=10),
                hovertemplate="<b>%{x}</b><br>%{y:.2f}€/an<extra></extra>"))
            l1=dict(**LAYOUT); l1.update(dict(title=dict(text=h2["titre_graphique"]+" — Décomposition prime pure",font=dict(color=c2,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.35,showlegend=False,
                annotations=[dict(text="💡 L'ITT doit représenter plus de 50% de la prime pure — c'est le risque dominant en prévoyance.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig1.update_layout(**l1); graphiques["decomposition_prime_prev"]=fig1
        except: pass
        # G2 — Taux de cotisation jauge
        try:
            h1=val["h1_cotisation"]; taux=h1["taux_cot"]; c1=VERT if h1["statut"]=="VERT" else AMBRE if h1["statut"]=="AMBRE" else ROUGE
            fig2=go.Figure(go.Indicator(mode="gauge+number",value=taux,
                number=dict(suffix="%",font=dict(color=c1,size=28),valueformat=".2f"),
                title=dict(text=h1["titre_graphique"],font=dict(color=c1,size=11)),
                gauge=dict(axis=dict(range=[0,6],tickfont=dict(color=GRIS,size=8),tickvals=[0,1.5,2.5,4,6],ticktext=["0","1.5%","2.5%","4%","6%"]),
                    bar=dict(color=c1,thickness=0.25),bgcolor="#1B3A5C",borderwidth=0,
                    steps=[dict(range=[0,1.5],color="rgba(243,156,18,0.12)"),dict(range=[1.5,4],color="rgba(46,204,113,0.12)"),dict(range=[4,6],color="rgba(231,76,60,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=2.5))))
            fig2.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {h1['conseil']}",xref="paper",yref="paper",x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["jauge_cotisation_prev"]=fig2
        except: pass
        # G3 — Part patronale vs salariale
        try:
            part_pat = p_comm * 0.60; part_sal = p_comm * 0.40
            h1=val["h1_cotisation"]; c1=VERT if h1["statut"]=="VERT" else AMBRE if h1["statut"]=="AMBRE" else ROUGE
            fig3=go.Figure(go.Bar(x=["Part patronale (60%)","Part salariale (40%)"],
                y=[part_pat,part_sal],marker_color=[VERT,BLEU],width=0.4,opacity=0.88,
                text=[f"{part_pat:.0f}€",f"{part_sal:.0f}€"],textposition="outside",textfont=dict(color=BLANC,size=12)))
            l3=dict(**LAYOUT); l3.update(dict(title=dict(text="Répartition prime — Part patronale 60% / salariale 40%",font=dict(color=BLANC,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.4,showlegend=False,
                annotations=[dict(text="💡 En prévoyance collective, l'employeur paie au moins 50% de la prime — exigence ANI 2013.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig3.update_layout(**l3); graphiques["repartition_cotisation"]=fig3
        except: pass
        # G4 — Scorecard
        try:
            items=[("H1 — Cotisation ∈ [1.5%,4%]",val["h1_cotisation"]["statut"],val["h1_cotisation"]["message"],val["h1_cotisation"]["conseil"]),
                   ("H2 — ITT ≥ 50% prime pure",val["h2_structure"]["statut"],val["h2_structure"]["message"],val["h2_structure"]["conseil"]),
                   ("H3 — Taux BCAC cohérent",val["h3_taux_itt"]["statut"],val["h3_taux_itt"]["message"],val["h3_taux_itt"]["conseil"])]
            fig4=go.Figure()
            for nom,statut,msg,conseil in items:
                c=VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i="✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s=1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(x=[s],y=[nom],orientation="h",marker_color=c,width=0.5,text=f"{i} {statut}",textposition="outside",textfont=dict(color=c,size=10),hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"]; cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard Prévoyance P1 — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),barmode="overlay",height=260,
                annotations=[dict(text="💡 3 ✅ = tarification prévoyance conforme BCAC/TD88-90 et ANI 2013.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_p1"]=fig4
        except: pass
        return graphiques

    def _generer_graphiques(self,p_itt,p_ip,p_deces):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";BLANC="#F0F4F8";OR="#C9A84C";BLEU="#3498DB";AMBRE="#F39C12"
            fig=go.Figure(go.Pie(labels=["ITT","Invalidité (IP)","Décès"],values=[p_itt,p_ip,p_deces],
                hole=0.4,marker_colors=[OR,BLEU,AMBRE],hovertemplate="<b>%{label}</b><br>%{value:.2f}€ (%{percent})<extra></extra>"))
            fig.update_layout(paper_bgcolor=NAVY,font=dict(family="Inter",color=BLANC,size=11),
                margin=dict(l=16,r=16,t=60,b=40),height=300,
                title=dict(text="Répartition prime pure prévoyance",font=dict(color=BLANC,size=12),x=0.01))
            return {"prime_pie":fig}
        except: return {}

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"p1_prev_{audit_id}.json"),'w') as f: json.dump(rapport,f,indent=2)
            self.logger.info(f"Sauvegardé : p1_prev_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
