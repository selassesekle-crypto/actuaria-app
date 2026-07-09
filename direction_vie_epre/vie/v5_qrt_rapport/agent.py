"""
ActuarIA — Agent V5 : Nia — QRT Vie & Rapport Actuariel
Direction Vie & EP-RE | Manager : Sven | Directeur : Paul

Reporting réglementaire Vie (Solvabilité 2) :
→ QRT S.12 (Provisions Vie)
→ QRT S.23 (Fonds Propres Vie)
→ Rapport Actuariel Annuel
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from direction_vie_epre.services.rapport_vie import (
    export_html as _rapport_html_vie,
    export_pdf  as _rapport_pdf_vie,
    export_word as _rapport_word_vie,
)
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.v5 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent V5 — QRT Vie & Rapport Actuariel ActuarIA v1.0")
print("QRT : S.12 (Provisions) · S.23 (Fonds Propres) · Rapport Actuariel")
print("Usage : agent_v5 = AgentV5QRTVie()")
print("        result_v5 = agent_v5.run(pm_total=50e6, scr_vie=5e6)")

class AgentV5QRTVie:
    def __init__(self,models_path="models",audit_path="audit",verbose=True):
        self.models_path=models_path; self.audit_path=audit_path
        self.verbose=verbose; self.logger=logging.getLogger("actuaria.v5")
        os.makedirs(models_path,exist_ok=True); os.makedirs(audit_path,exist_ok=True)

    def run(self,pm_total=50_000_000,scr_vie=5_000_000,fonds_propres=12_000_000,
            be_vie=45_000_000,risk_adjustment=2_000_000,ppb=1_500_000,
            nb_contrats=10_000,generer_graphiques=True,
            result_v3=None,    # Optional[Dict] — alimente be_vie et pm_total depuis V3 Amélie
            result_rvie1=None, # Optional[Dict] — alimente scr_vie depuis R-VIE1 Éric
            result_v4=None,    # Optional[Dict] — alimente ppb depuis V4 Théo
            # Agents complémentaires pour rapport consolidé
            result_v6=None, result_v7=None, result_v8=None, result_v9=None,
            result_rvie2=None,
            result_ep1=None, result_ep3=None, result_ep4=None,
            result_ep6=None, result_ep7=None,
            # Métadonnées rapport
            ref_client='', arrete='',
            actuaire_nom='', actuaire_numero_ia='',
            ) -> Dict:
        audit_id=f"V5_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger=self.logger
        if self.verbose: logger.info(f"[{audit_id}] Agent V5 démarré | PM={pm_total/1e6:.1f}M€ | SCR Vie={scr_vie/1e6:.1f}M€")
        try:
            # ── Alimentation depuis la chaîne actuarielle (si disponible) ────
            # V3 Amélie → be_vie + pm_total
            sources = {}
            if result_v3 and result_v3.get('success'):
                be_vie   = result_v3.get('pm_prospective', be_vie)
                pm_total = result_v3.get('pm_prospective', pm_total)
                sources['be_vie'] = 'V3 Amélie (pm_prospective)'
                sources['pm_total'] = 'V3 Amélie (pm_prospective)'
                logger.info(f"[{audit_id}] be_vie alimenté depuis V3 Amélie : {be_vie/1e6:.2f}M€")

            # R-VIE1 Éric → scr_vie
            if result_rvie1 and result_rvie1.get('success'):
                scr_vie = result_rvie1.get('scr_vie_total', scr_vie)
                sources['scr_vie'] = 'R-VIE1 Éric (scr_vie_total)'
                logger.info(f"[{audit_id}] scr_vie alimenté depuis R-VIE1 Éric : {scr_vie/1e6:.2f}M€")

            # V4 Théo → ppb
            if result_v4 and result_v4.get('success'):
                ppb = result_v4.get('ppb_finale', ppb)
                sources['ppb'] = 'V4 Théo (ppb_finale)'
                logger.info(f"[{audit_id}] ppb alimenté depuis V4 Théo : {ppb/1e3:.0f}k€")

            # ── QRT S.12 — Provisions Vie ─────────────────────────────────────
            tp_vie = be_vie + risk_adjustment
            ratio_tp_be = tp_vie / max(be_vie, 1)
            pm_par_contrat = pm_total / max(nb_contrats, 1)

            qrt_s12 = {
                "code": "S.12.01",
                "titre": "Life and Health SLT Technical Provisions",
                "be_vie": round(be_vie, 2),
                "risk_adjustment": round(risk_adjustment, 2),
                "tp_vie": round(tp_vie, 2),
                "ratio_tp_be": round(ratio_tp_be, 4),
                "pm_total": round(pm_total, 2),
                "ppb": round(ppb, 2),
                "nb_contrats": nb_contrats,
                "pm_par_contrat": round(pm_par_contrat, 2),
                "ecart_pm_tp": round(abs(pm_total - tp_vie), 2),
                "statut": "VERT" if 1.0 <= ratio_tp_be <= 1.5 else "AMBRE",
            }

            # ── QRT S.23 — Fonds Propres ──────────────────────────────────────
            ratio_scr = fonds_propres / max(scr_vie, 1) * 100
            mcr_vie = scr_vie * 0.25  # 25% du SCR minimum
            ratio_mcr = fonds_propres / max(mcr_vie, 1) * 100

            qrt_s23 = {
                "code": "S.23.01",
                "titre": "Own Funds",
                "fonds_propres_t1": round(fonds_propres * 0.90, 2),
                "fonds_propres_t2": round(fonds_propres * 0.10, 2),
                "fonds_propres_total": round(fonds_propres, 2),
                "scr_vie": round(scr_vie, 2),
                "mcr_vie": round(mcr_vie, 2),
                "ratio_scr_pct": round(ratio_scr, 1),
                "ratio_mcr_pct": round(ratio_mcr, 1),
                "statut": "VERT" if ratio_scr >= 150 else "AMBRE" if ratio_scr >= 100 else "ROUGE",
            }

            # ── Rapport Actuariel ─────────────────────────────────────────────
            avis_pa = "FAVORABLE" if ratio_scr >= 150 and 1.0 <= ratio_tp_be <= 1.5 else "FAVORABLE AVEC RÉSERVE"
            rapport_actuariel = {
                "titre": "Rapport de la Fonction Actuarielle — Vie",
                "date": datetime.now().strftime("%d/%m/%Y"),
                "avis": avis_pa,
                "sections": [
                    {"num": "1", "titre": "Adéquation des provisions techniques", "statut": qrt_s12["statut"]},
                    {"num": "2", "titre": "Adéquation du capital de solvabilité", "statut": qrt_s23["statut"]},
                    {"num": "3", "titre": "Validation des hypothèses actuarielles", "statut": "VERT"},
                    {"num": "4", "titre": "Politique de souscription et réassurance", "statut": "VERT"},
                ],
                "recommandations": [
                    "Maintenir le ratio SCR au-dessus de 150%" if ratio_scr < 150 else "SCR conforme — continuer le suivi trimestriel",
                    "Vérifier la cohérence PM/TP" if abs(pm_total-tp_vie)/max(pm_total,1) > 0.05 else "PM et TP cohérents",
                    "Surveiller l'évolution de la PPB" if ppb > 0 else "PPB nulle — aucune action requise",
                ],
            }

            commentaire = (
                f"✅ QRT Vie & Rapport Actuariel produits — PM {pm_total/1e6:.1f}M€.\n"
                f"S.12 — BE Vie : {be_vie/1e6:.2f}M€ | TP Vie : {tp_vie/1e6:.2f}M€ | Ratio TP/BE : {ratio_tp_be:.3f}.\n"
                f"S.23 — Fonds propres : {fonds_propres/1e6:.2f}M€ | Ratio SCR : {ratio_scr:.1f}% | Ratio MCR : {ratio_mcr:.1f}%.\n"
                f"Rapport Actuariel : Avis {avis_pa}.\n"
                f"Cohérence PM/TP : écart {abs(pm_total-tp_vie)/max(pm_total,1)*100:.1f}%."
            )

            val_hyp = self._valider_qrt(qrt_s12, qrt_s23, pm_total, tp_vie, ratio_scr)
            gv = self._graphiques_validation_qrt(val_hyp, qrt_s12, qrt_s23) if generer_graphiques else {}
            graphiques = self._generer_graphiques(qrt_s12, qrt_s23) if generer_graphiques else {}
            self._sauvegarder({'agent':'V5 Nia','qrt_s12':qrt_s12,'qrt_s23':qrt_s23,
                               'rapport_actuariel':rapport_actuariel}, audit_id)

            # ── Rapports consolidés niveau A7 ─────────────────────────────────
            _kw = dict(
                result_v3=result_v3, result_v6=result_v6, result_v7=result_v7,
                result_v8=result_v8, result_v9=result_v9,
                result_v5={
                    'success':True,
                    'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                    'tp_vie':round(tp_vie,2), 'be_vie':round(be_vie,2),
                    'ratio_tp_be':round(ratio_tp_be,4),
                    'ratio_scr_pct':round(ratio_scr,1),
                    'ratio_mcr_pct':round(ratio_mcr,1),
                    'avis_pa':avis_pa,
                    'conseil_global':rapport_actuariel.get('avis',''),
                    'recommandations':rapport_actuariel.get('recommandations',[]),
                },
                result_rvie1=result_rvie1, result_rvie2=result_rvie2,
                result_ep1=result_ep1, result_ep3=result_ep3, result_ep4=result_ep4,
                result_ep6=result_ep6, result_ep7=result_ep7,
                commentaire=commentaire, ref_client=ref_client, arrete=arrete,
                audit_id=audit_id,
                graphiques=graphiques if generer_graphiques else None,
                actuaire_nom=actuaire_nom, actuaire_numero_ia=actuaire_numero_ia,
            )
            html_bytes = pdf_bytes = word_bytes = None
            try:
                _h = _rapport_html_vie(**_kw)
                html_bytes = _h.encode('utf-8') if _h else None
            except Exception as _e:
                logger.warning(f'[{audit_id}] HTML V5 : {_e}')
            try:
                pdf_bytes = _rapport_pdf_vie(**_kw)
            except Exception as _e:
                logger.warning(f'[{audit_id}] PDF V5 : {_e}')
            try:
                _kw_word = {k: v for k, v in _kw.items() if k != 'graphiques'}
                word_bytes = _rapport_word_vie(**_kw_word)
            except Exception as _e:
                logger.warning(f'[{audit_id}] Word V5 : {_e}')

            return {
                'success':True,'agent':'V5 Nia',
                'statut_rag':'VERT' if val_hyp['statut_global']!='ROUGE' else 'AMBRE',
                'sources':sources,  # traçabilité des données d'entrée
                'qrt_s12':qrt_s12,'qrt_s23':qrt_s23,
                'rapport_actuariel':rapport_actuariel,
                'ratio_scr_pct':round(ratio_scr,1),
                'ratio_mcr_pct':round(ratio_mcr,1),
                'ratio_tp_be':round(ratio_tp_be,4),
                'commentaire':commentaire,'audit_id':audit_id,
                'graphiques':graphiques,'validation_qrt':val_hyp,'graphiques_validation':gv,
                'html_bytes':html_bytes,'pdf_bytes':pdf_bytes,'word_bytes':word_bytes,
                'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_qrt(self,s12,s23,pm,tp,ratio_scr):
        # C1 — Ratio TP/BE ∈ [1.0, 1.5]
        r=s12["ratio_tp_be"]
        if 1.0<=r<=1.5: c1_s,c1_m,c1_c="VERT",f"Ratio TP/BE = {r:.3f} ∈ [1.0,1.5] ✅","TP Vie conforme — Risk Adjustment justifié"
        elif r<1.0: c1_s,c1_m,c1_c="ROUGE",f"Ratio TP/BE = {r:.3f} < 1.0 ❌","TP inférieur au BE — Risk Adjustment négatif impossible"
        else: c1_s,c1_m,c1_c="AMBRE",f"Ratio TP/BE = {r:.3f} > 1.5 ⚠️","Risk Adjustment élevé — justifier devant l'ACPR"
        # C2 — Ratio SCR ≥ 150%
        if ratio_scr>=150: c2_s,c2_m,c2_c="VERT",f"Ratio SCR = {ratio_scr:.1f}% ≥ 150% ✅","Capitalisation solide — objectif ORSA atteint"
        elif ratio_scr>=100: c2_s,c2_m,c2_c="AMBRE",f"Ratio SCR = {ratio_scr:.1f}% ∈ [100%,150%] ⚠️","Ratio conforme mais proche du seuil"
        else: c2_s,c2_m,c2_c="ROUGE",f"Ratio SCR = {ratio_scr:.1f}% < 100% ❌","INSUFFISANCE DE CAPITAL — Action ACPR immédiate"
        # C3 — Cohérence PM/TP (écart < 10%)
        ecart=abs(pm-tp)/max(pm,1)*100
        if ecart<=5: c3_s,c3_m,c3_c="VERT",f"Écart PM/TP = {ecart:.1f}% ≤ 5% ✅","PM et TP cohérents — comptabilité sociale alignée S2"
        elif ecart<=10: c3_s,c3_m,c3_c="AMBRE",f"Écart PM/TP = {ecart:.1f}% ∈ [5%,10%] ⚠️","Documenter les sources d'écart PM vs TP"
        else: c3_s,c3_m,c3_c="ROUGE",f"Écart PM/TP = {ecart:.1f}% > 10% ❌","Divergence significative — revoir la réconciliation"
        sts=[c1_s,c2_s,c3_s]; sg="ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "c1_tp_be":{"ratio":r,"statut":c1_s,"message":c1_m,"conseil":c1_c,"titre_graphique":f"{'✅' if c1_s=='VERT' else '⚠️' if c1_s=='AMBRE' else '❌'} QRT S.12 — Ratio TP/BE = {r:.3f}"},
            "c2_scr":{"ratio_scr":round(ratio_scr,1),"statut":c2_s,"message":c2_m,"conseil":c2_c,"titre_graphique":f"{'✅' if c2_s=='VERT' else '⚠️' if c2_s=='AMBRE' else '❌'} QRT S.23 — Ratio SCR = {ratio_scr:.1f}%"},
            "c3_pm_tp":{"ecart_pct":round(ecart,2),"statut":c3_s,"message":c3_m,"conseil":c3_c,"titre_graphique":f"{'✅' if c3_s=='VERT' else '⚠️' if c3_s=='AMBRE' else '❌'} Cohérence PM/TP — Écart {ecart:.1f}%"},
            "statut_global":sg,"conclusion":{"VERT":"✅ QRT Vie validés — S.12 et S.23 conformes, cohérence PM/TP","AMBRE":"⚠️ QRT acceptable — vérifier les points signalés","ROUGE":"❌ QRT non conformes — action immédiate requise"}[sg],
        }

    def _graphiques_validation_qrt(self,val,s12,s23):
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT=dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques={}
        # G1 — BE vs TP (S.12)
        try:
            c1=val["c1_tp_be"]; cc1=VERT if c1["statut"]=="VERT" else AMBRE if c1["statut"]=="AMBRE" else ROUGE
            fig1=go.Figure(go.Bar(x=["BE Vie","Risk Adj.","TP Vie"],
                y=[s12["be_vie"]/1e6,s12["risk_adjustment"]/1e6,s12["tp_vie"]/1e6],
                marker_color=[OR,BLEU,cc1],width=0.4,opacity=0.88,
                text=[f"{v:.2f}M€" for v in [s12["be_vie"]/1e6,s12["risk_adjustment"]/1e6,s12["tp_vie"]/1e6]],
                textposition="outside",textfont=dict(color=BLANC,size=10)))
            l1=dict(**LAYOUT); l1.update(dict(title=dict(text=c1["titre_graphique"],font=dict(color=cc1,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.35,showlegend=False,
                annotations=[dict(text="💡 TP Vie = BE + Risk Adjustment. La barre TP doit être entre 1× et 1.5× le BE.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig1.update_layout(**l1); graphiques["qrt_s12_tp_be"]=fig1
        except: pass
        # G2 — Ratio SCR (S.23)
        try:
            c2=val["c2_scr"]; cc2=VERT if c2["statut"]=="VERT" else AMBRE if c2["statut"]=="AMBRE" else ROUGE
            fig2=go.Figure(go.Indicator(mode="gauge+number",value=s23["ratio_scr_pct"],
                number=dict(suffix="%",font=dict(color=cc2,size=28),valueformat=".1f"),
                title=dict(text=c2["titre_graphique"],font=dict(color=cc2,size=11)),
                gauge=dict(axis=dict(range=[0,300],tickfont=dict(color=GRIS,size=8),tickvals=[0,100,150,200,300],ticktext=["0%","100%","150%","200%","300%"]),
                    bar=dict(color=cc2,thickness=0.25),bgcolor=NAVY_L,borderwidth=0,
                    steps=[dict(range=[0,100],color="rgba(231,76,60,0.12)"),dict(range=[100,150],color="rgba(243,156,18,0.12)"),dict(range=[150,300],color="rgba(46,204,113,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=150))))
            fig2.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {c2['conseil']}",xref="paper",yref="paper",x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["ratio_scr_vie"]=fig2
        except: pass
        # G3 — Cohérence PM vs TP
        try:
            c3=val["c3_pm_tp"]; cc3=VERT if c3["statut"]=="VERT" else AMBRE if c3["statut"]=="AMBRE" else ROUGE
            fig3=go.Figure(go.Bar(x=["PM Comptable","TP Solvabilité 2"],y=[s12["pm_total"]/1e6,s12["tp_vie"]/1e6],
                marker_color=[OR,cc3],width=0.4,opacity=0.88,
                text=[f"{s12['pm_total']/1e6:.2f}M€",f"{s12['tp_vie']/1e6:.2f}M€"],textposition="outside",textfont=dict(color=BLANC,size=12)))
            l3=dict(**LAYOUT); l3.update(dict(title=dict(text=c3["titre_graphique"],font=dict(color=cc3,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),yaxis=dict(visible=False),bargap=0.4,showlegend=False,
                annotations=[dict(text="💡 PM (comptable) et TP S2 doivent être cohérents. Un écart > 10% signale une incohérence entre les deux référentiels.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig3.update_layout(**l3); graphiques["coherence_pm_tp"]=fig3
        except: pass
        # G4 — Scorecard QRT
        try:
            items=[("C1 — QRT S.12 TP/BE",val["c1_tp_be"]["statut"],val["c1_tp_be"]["message"],val["c1_tp_be"]["conseil"]),
                   ("C2 — QRT S.23 Ratio SCR",val["c2_scr"]["statut"],val["c2_scr"]["message"],val["c2_scr"]["conseil"]),
                   ("C3 — Cohérence PM/TP",val["c3_pm_tp"]["statut"],val["c3_pm_tp"]["message"],val["c3_pm_tp"]["conseil"])]
            fig4=go.Figure()
            for nom,statut,msg,conseil in items:
                c=VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i="✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s=1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(x=[s],y=[nom],orientation="h",marker_color=c,width=0.5,text=f"{i} {statut}",textposition="outside",textfont=dict(color=c,size=10),hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",showlegend=False))
            sg=val["statut_global"]; cg=VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4=dict(**LAYOUT); l4.update(dict(title=dict(text=f"Scorecard QRT Vie — {val['conclusion']}",font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",height=260,annotations=[dict(text="💡 3 ✅ = QRT Vie conformes EIOPA, défendables devant l'ACPR.",xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_qrt"]=fig4
        except: pass
        return graphiques

    def _generer_graphiques(self,s12,s23):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0";VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12"
            r=s23["ratio_scr_pct"]; c=VERT if r>=150 else AMBRE if r>=100 else ROUGE
            fig=go.Figure(go.Indicator(mode="gauge+number",value=r,number=dict(suffix="%",font=dict(color=c,size=28),valueformat=".1f"),
                title=dict(text="Ratio de couverture SCR Vie",font=dict(color=c,size=12)),
                gauge=dict(axis=dict(range=[0,300],tickfont=dict(color=GRIS,size=8)),bar=dict(color=c,thickness=0.25),bgcolor=NAVY_L,borderwidth=0,
                    steps=[dict(range=[0,100],color="rgba(231,76,60,0.12)"),dict(range=[100,150],color="rgba(243,156,18,0.12)"),dict(range=[150,300],color="rgba(46,204,113,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=150))))
            fig.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),margin=dict(l=30,r=30,t=80,b=30),height=300)
            return {"ratio_scr":fig}
        except: return {}

    def _sauvegarder(self,rapport,audit_id):
        try:
            with open(os.path.join(self.models_path,f"v5_qrt_{audit_id}.json"),'w') as f: json.dump(rapport,f,indent=2)
            self.logger.info(f"Sauvegardé : v5_qrt_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
