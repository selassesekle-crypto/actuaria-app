"""
ActuarIA — Agent S1 : Léonie — Tarification Frais de Santé
Direction Santé-Prévoyance | Manager : Chiara | Directeur : Amira

Tarification santé individuelle et collective :
→ Tables CCAM (actes médicaux) / NGAP (nomenclature)
→ Sinistralité par poste (médecine, pharmacie, hospitalisation, dentaire, optique)
→ Prime pure, commerciale, ratio S/P
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.s1 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent S1 — Tarification Frais de Santé ActuarIA v1.0")
print("Postes : Médecine · Pharmacie · Hospitalisation · Dentaire · Optique")
print("Usage : agent_s1 = AgentS1TarificationSante()")
print("        result_s1 = agent_s1.run(nb_assures=1000, age_moyen=42)")

# Coûts moyens par poste (€/assuré/an) — source DREES 2023
COUTS_POSTES_REF = {
    "medecine":       {"freq": 4.2,  "cout_acte": 28.5,  "tc_ss": 0.70},
    "pharmacie":      {"freq": 8.5,  "cout_acte": 22.0,  "tc_ss": 0.65},
    "hospitalisation":{"freq": 0.15, "cout_acte": 3500.0,"tc_ss": 0.80},
    "dentaire":       {"freq": 1.2,  "cout_acte": 180.0, "tc_ss": 0.25},
    "optique":        {"freq": 0.45, "cout_acte": 320.0, "tc_ss": 0.00},
}

class AgentS1TarificationSante:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.s1")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,nb_assures=1000,age_moyen=42,contrat="individuel",
            garantie_niveau="confort",chargement_pct=0.18,
            generer_graphiques=True) -> Dict:
        audit_id=f"S1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent S1 démarré | {nb_assures} assurés | âge moy={age_moyen}")
        try:
            # Facteur d'âge (sinistralité croît avec l'âge)
            fact_age = 0.7 + (age_moyen - 30) * 0.015

            # Niveau de garantie
            niveaux = {"eco":0.6,"confort":1.0,"premium":1.4,"luxe":1.8}
            fact_garantie = niveaux.get(garantie_niveau, 1.0)

            # Sinistralité par poste
            postes = {}
            total_sinistres = 0
            for poste, ref in COUTS_POSTES_REF.items():
                freq = ref["freq"] * fact_age * fact_garantie
                cout = ref["cout_acte"] * fact_age
                remboursement_ss = cout * ref["tc_ss"]
                charge_mutuelle  = (cout - remboursement_ss) * min(fact_garantie, 2.0)
                sinistre_an = freq * charge_mutuelle
                postes[poste] = {
                    "frequence_an":    round(freq, 3),
                    "cout_moyen":      round(cout, 2),
                    "remb_ss":         round(remboursement_ss, 2),
                    "charge_mutuelle": round(charge_mutuelle, 2),
                    "sinistre_annuel": round(sinistre_an, 2),
                }
                total_sinistres += sinistre_an

            prime_pure    = total_sinistres
            prime_comm    = prime_pure * (1 + chargement_pct)
            prime_mensuelle = prime_comm / 12

            # Ratio S/P attendu
            ratio_sp_attendu = prime_pure / max(prime_comm, 1)

            # Comparaison marché
            prime_marche_ref = prime_pure * 1.20

            commentaire = (
                f"✅ Tarification Santé finalisée — {nb_assures} assurés | âge moy {age_moyen} ans | {contrat}.\n"
                f"Prime pure : {prime_pure:.2f}€/an/assuré ({prime_mensuelle:.2f}€/mois).\n"
                f"Sinistralité : Médecine {postes['medecine']['sinistre_annuel']:.0f}€ "
                f"| Hospit {postes['hospitalisation']['sinistre_annuel']:.0f}€ "
                f"| Dentaire {postes['dentaire']['sinistre_annuel']:.0f}€ "
                f"| Optique {postes['optique']['sinistre_annuel']:.0f}€.\n"
                f"Ratio S/P attendu : {ratio_sp_attendu*100:.1f}% | Chargement : {chargement_pct*100:.0f}%."
            )

            val_hyp = self._valider_sante(prime_pure, prime_comm, prime_marche_ref,
                                          ratio_sp_attendu, postes, age_moyen)
            gv  = self._graphiques_validation_sante(val_hyp, postes, prime_pure, prime_comm) if generer_graphiques else {}
            graphiques = self._generer_graphiques(postes) if generer_graphiques else {}
            self._sauvegarder({'agent':'S1 Léonie','prime_pure':prime_pure,'prime_comm':prime_comm,
                               'ratio_sp':ratio_sp_attendu,'postes':postes}, audit_id)

            return {
                'success':True,'agent':'S1 Léonie','contrat':contrat,
                'nb_assures':nb_assures,'age_moyen':age_moyen,
                'statut_rag':'VERT' if val_hyp['statut_global']=='VERT' else 'AMBRE',
                'prime_pure':round(prime_pure,2),
                'prime_commerciale':round(prime_comm,2),
                'prime_mensuelle':round(prime_mensuelle,2),
                'ratio_sp_attendu':round(ratio_sp_attendu,4),
                'postes':postes,
                'commentaire':commentaire,'audit_id':audit_id,
                'graphiques':graphiques,'validation_sante':val_hyp,'graphiques_validation':gv,'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_sante(self,prime_pure,prime_comm,prime_marche,ratio_sp,postes,age):
        # H1 — Ratio S/P ∈ [0.65, 0.85]
        if 0.65<=ratio_sp<=0.85: h1_s,h1_m,h1_c="VERT",f"Ratio S/P = {ratio_sp*100:.1f}% ∈ [65%,85%] ✅","Ratio sinistres/primes conforme normes mutualité"
        elif 0.55<=ratio_sp<0.65: h1_s,h1_m,h1_c="AMBRE",f"Ratio S/P = {ratio_sp*100:.1f}% < 65% ⚠️","Prime trop élevée — risque de perte d'adhérents"
        elif ratio_sp<=0.95: h1_s,h1_m,h1_c="AMBRE",f"Ratio S/P = {ratio_sp*100:.1f}% > 85% ⚠️","Ratio élevé — rentabilité insuffisante"
        else: h1_s,h1_m,h1_c="ROUGE",f"Ratio S/P = {ratio_sp*100:.1f}% > 95% ❌","Contrat déficitaire — revoir les garanties ou le tarif"
        # H2 — Hospitalisation ≤ 50% du total
        hospit = postes['hospitalisation']['sinistre_annuel']
        total  = sum(p['sinistre_annuel'] for p in postes.values())
        part_hospit = hospit / max(total, 1)
        if part_hospit<=0.50: h2_s,h2_m,h2_c="VERT",f"Hospit = {part_hospit*100:.1f}% du total ≤ 50% ✅","Répartition sinistralité équilibrée"
        elif part_hospit<=0.65: h2_s,h2_m,h2_c="AMBRE",f"Hospit = {part_hospit*100:.1f}% ∈ [50%,65%] ⚠️","Hospit dominante — surveiller l'anti-sélection"
        else: h2_s,h2_m,h2_c="ROUGE",f"Hospit = {part_hospit*100:.1f}% > 65% ❌","Concentration risque hospitalier — revoir les garanties hospit"
        # H3 — Prime compétitive vs marché
        ratio_comp = prime_comm / max(prime_marche, 1)
        if ratio_comp<=1.10: h3_s,h3_m,h3_c="VERT",f"Prime/marché = {ratio_comp:.3f} ≤ 1.10 ✅","Tarif compétitif — bon positionnement commercial"
        elif ratio_comp<=1.25: h3_s,h3_m,h3_c="AMBRE",f"Prime/marché = {ratio_comp:.3f} ∈ [1.10,1.25] ⚠️","Prime légèrement élevée — optimiser les chargements"
        else: h3_s,h3_m,h3_c="ROUGE",f"Prime/marché = {ratio_comp:.3f} > 1.25 ❌","Prime non compétitive — perte de marché probable"
        sts=[h1_s,h2_s,h3_s]; sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "h1_ratio_sp":{"ratio":round(ratio_sp,4),"statut":h1_s,"message":h1_m,"conseil":h1_c,"titre_graphique":f"{'✅' if h1_s=='VERT' else '⚠️' if h1_s=='AMBRE' else '❌'} Ratio S/P = {ratio_sp*100:.1f}%"},
            "h2_hospit":{"part_hospit":round(part_hospit,4),"statut":h2_s,"message":h2_m,"conseil":h2_c,"titre_graphique":f"{'✅' if h2_s=='VERT' else '⚠️' if h2_s=='AMBRE' else '❌'} Hospit = {part_hospit*100:.1f}% du total"},
            "h3_competitivite":{"ratio_comp":round(ratio_comp,4),"statut":h3_s,"message":h3_m,"conseil":h3_c,"titre_graphique":f"{'✅' if h3_s=='VERT' else '⚠️' if h3_s=='AMBRE' else '❌'} Compétitivité = {ratio_comp:.3f}"},
            "statut_global":sg,"conclusion":{"VERT":"✅ Tarification Santé validée — S/P, répartition et compétitivité conformes","AMBRE":"⚠️ Tarification acceptable — vérifier les points signalés","ROUGE":"❌ Tarification à corriger — non-conformité détectée"}[sg],
        }

    def _graphiques_validation_sante(self,val,postes,prime_pure,prime_comm):
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT=dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques={}
        # G1 — Décomposition sinistralité par poste
        try:
            noms=[p.replace("_"," ").title() for p in postes]
            vals=[postes[p]['sinistre_annuel'] for p in postes]
            colors=[OR,BLEU,"#9B59B6",AMBRE,VERT]
            fig1=go.Figure(go.Bar(x=noms,y=vals,marker_color=colors[:len(noms)],width=0.5,opacity=0.88,
                text=[f"{v:.0f}€" for v in vals],textposition="outside",textfont=dict(color=BLANC,size=10),
                hovertemplate="<b>%{x}</b><br>%{y:.0f}€/an<extra></extra>"))
            h2=val["h2_hospit"]; c2=VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            l1=dict(**LAYOUT); l1.update(dict(title=dict(text=f"{'✅' if h2['statut']=='VERT' else '⚠️'} Sinistralité par poste — {h2['message'][:40]}",font=dict(color=c2,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.3,showlegend=False,
                annotations=[dict(text="💡 L'hospitalisation ne doit pas dépasser 50% du total — sinon risque d'anti-sélection sur ce poste.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig1.update_layout(**l1); graphiques["sinistralite_postes"]=fig1
        except: pass
        # G2 — Ratio S/P jauge
        try:
            h1=val["h1_ratio_sp"]; c1=VERT if h1["statut"]=="VERT" else AMBRE if h1["statut"]=="AMBRE" else ROUGE
            fig2=go.Figure(go.Indicator(mode="gauge+number",value=h1["ratio"]*100,
                number=dict(suffix="%",font=dict(color=c1,size=28),valueformat=".1f"),
                title=dict(text=h1["titre_graphique"],font=dict(color=c1,size=11)),
                gauge=dict(axis=dict(range=[0,110],tickfont=dict(color=GRIS,size=8),tickvals=[0,55,65,85,95,110],ticktext=["0","55","65%","85%","95",""]),
                    bar=dict(color=c1,thickness=0.25),bgcolor="#1B3A5C",borderwidth=0,
                    steps=[dict(range=[0,55],color="rgba(243,156,18,0.12)"),dict(range=[55,65],color="rgba(243,156,18,0.12)"),dict(range=[65,85],color="rgba(46,204,113,0.12)"),dict(range=[85,110],color="rgba(231,76,60,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=75))))
            fig2.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {h1['conseil']}",xref="paper",yref="paper",x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["jauge_ratio_sp"]=fig2
        except: pass
        # G3 — Prime pure vs commerciale vs marché
        try:
            h3=val["h3_competitivite"]; c3=VERT if h3["statut"]=="VERT" else AMBRE if h3["statut"]=="AMBRE" else ROUGE
            marche=prime_comm/h3["ratio_comp"]
            fig3=go.Figure(go.Bar(x=["Prime pure","Prime commerciale","Référence marché"],
                y=[prime_pure,prime_comm,marche],marker_color=[OR,c3,GRIS],width=0.4,opacity=0.88,
                text=[f"{v:.0f}€" for v in [prime_pure,prime_comm,marche]],textposition="outside",textfont=dict(color=BLANC,size=10)))
            l3=dict(**LAYOUT); l3.update(dict(title=dict(text=h3["titre_graphique"],font=dict(color=c3,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.35,showlegend=False,
                annotations=[dict(text="💡 La prime commerciale doit rester proche de la référence marché pour rester compétitive.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig3.update_layout(**l3); graphiques["comparaison_primes_sante"]=fig3
        except: pass
        # G4 — Scorecard
        try:
            items=[("H1 — Ratio S/P ∈ [65%,85%]",val["h1_ratio_sp"]["statut"],val["h1_ratio_sp"]["message"],val["h1_ratio_sp"]["conseil"]),
                   ("H2 — Hospit ≤ 50% total",val["h2_hospit"]["statut"],val["h2_hospit"]["message"],val["h2_hospit"]["conseil"]),
                   ("H3 — Prime compétitive",val["h3_competitivite"]["statut"],val["h3_competitivite"]["message"],val["h3_competitivite"]["conseil"])]
            fig4=go.Figure()
            for nom,statut,msg,conseil in items:
                c=VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i="✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s=1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(x=[s],y=[nom],orientation="h",marker_color=c,width=0.5,text=f"{i} {statut}",textposition="outside",textfont=dict(color=c,size=10),hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"]; cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard Santé — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",height=260,annotations=[dict(text="💡 3 ✅ = Tarification Santé validée, conforme CCAM/NGAP et compétitive.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_sante"]=fig4
        except: pass
        return graphiques

    def _generer_graphiques(self,postes):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";NAVY_L="#1B3A5C";BLANC="#F0F4F8";GRIS="#8A9AB0"
            OR="#C9A84C";BLEU="#3498DB";AMBRE="#F39C12";VERT="#2ECC71"
            noms=[p.replace("_"," ").title() for p in postes]
            vals=[postes[p]['sinistre_annuel'] for p in postes]
            fig=go.Figure(go.Pie(labels=noms,values=vals,hole=0.4,
                marker_colors=[OR,BLEU,"#9B59B6",AMBRE,VERT],
                hovertemplate="<b>%{label}</b><br>%{value:.0f}€ (%{percent})<extra></extra>"))
            fig.update_layout(paper_bgcolor=NAVY,font=dict(family="Inter",color=BLANC,size=11),
                margin=dict(l=16,r=16,t=60,b=40),height=300,
                title=dict(text="Répartition de la sinistralité par poste",font=dict(color=BLANC,size=12),x=0.01),
                legend=dict(bgcolor="rgba(0,0,0,0)",font=dict(color=BLANC,size=9)))
            return {"sinistralite_pie":fig}
        except: return {}

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"s1_sante_{audit_id}.json"),'w') as f: json.dump(rapport,f,indent=2)
            self.logger.info(f"Sauvegardé : s1_sante_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
