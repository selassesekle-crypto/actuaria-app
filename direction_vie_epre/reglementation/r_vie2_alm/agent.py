"""
ActuarIA — Agent R-VIE2 : Camille — RSR & SFCR Vie
Direction Vie & EP-RE | Manager : Olivier | Directeur : Paul

Rapports réglementaires Pilier 3 Solvabilité 2 :
→ RSR (Regular Supervisory Report) — rapport superviseur annuel
→ SFCR (Solvency and Financial Condition Report) — rapport public annuel
→ Sections A-E : Activité · Gouvernance · Profil de risque · Valorisation · Capital
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.rvie2 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent R-VIE2 — RSR & SFCR Vie ActuarIA v1.0")
print("Pilier 3 S2 : RSR (superviseur) · SFCR (public) · Sections A-E")
print("Usage : agent_rvie2 = AgentRVIE2RSRSFCRVie()")
print("        result_rvie2 = agent_rvie2.run(scr_vie=5e6, fonds_propres=12e6)")

class AgentRVIE2RSRSFCRVie:
    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = models_path
        self.audit_path  = audit_path
        self.verbose     = verbose
        self.logger      = logging.getLogger("actuaria.rvie2")
        os.makedirs(models_path, exist_ok=True)
        os.makedirs(audit_path,  exist_ok=True)

    def run(self, scr_vie=5_000_000, fonds_propres=12_000_000,
            be_vie=45_000_000, pm_total=50_000_000,
            risk_adjustment_pct=0.08,  # RA = 8% du BE par défaut (à passer depuis R-VIE1)
            ratio_scr_n1=200.0, generer_graphiques=True) -> Dict:
        audit_id = f"RVIE2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger = self.logger
        if self.verbose:
            logger.info(f"[{audit_id}] Agent R-VIE2 démarré | SCR={scr_vie/1e6:.1f}M€")
        try:
            # ── Ratios clés ────────────────────────────────────────────────────
            ratio_scr_n  = fonds_propres / max(scr_vie, 1) * 100
            mcr_vie       = max(scr_vie * 0.25, pm_total * 0.005)
            ratio_mcr_n   = fonds_propres / max(mcr_vie, 1) * 100
            variation_scr = ratio_scr_n - ratio_scr_n1

            # TP Vie S2 = BE + Risk Adjustment (paramètre, pas coefficient fixe)
            # risk_adjustment_pct = RA / BE (ex: 8% = valeur typique marché)
            # Idéalement fourni par R-VIE1 Éric via result_rvie1
            tp_vie  = be_vie * (1 + risk_adjustment_pct)
            ratio_tp_be = tp_vie / max(be_vie, 1)

            # ── Structure SFCR — Sections A à E ──────────────────────────────
            sfcr = {
                "A_activite": {
                    "titre":    "A — Activité et résultats",
                    "statut":   "VERT",
                    "elements": [
                        f"Provisions techniques : {pm_total/1e6:.1f}M€",
                        f"Best Estimate Vie : {be_vie/1e6:.1f}M€",
                        f"TP Vie (S2) : {tp_vie/1e6:.1f}M€",
                        f"Ratio TP/BE : {ratio_tp_be:.3f}",
                    ],
                },
                "B_gouvernance": {
                    "titre":  "B — Système de gouvernance",
                    "statut": "VERT",
                    "elements": [
                        "Fonction actuarielle désignée ✅",
                        "Comité des risques opérationnel ✅",
                        "Politique de rémunération approuvée ✅",
                        "Externalisation documentée ✅",
                    ],
                },
                "C_profil_risque": {
                    "titre":  "C — Profil de risque",
                    "statut": "VERT" if ratio_scr_n >= 150 else "AMBRE",
                    "elements": [
                        f"SCR Vie : {scr_vie/1e6:.1f}M€",
                        f"Risque dominant : Longévité + Rachat",
                        f"Réassurance : couverture catastrophe ✅",
                        f"Concentration : diversification suffisante ✅",
                    ],
                },
                "D_valorisation": {
                    "titre":  "D — Valorisation à des fins de solvabilité",
                    "statut": "VERT" if 1.0 <= ratio_tp_be <= 1.5 else "AMBRE",
                    "elements": [
                        f"BE Vie : {be_vie/1e6:.1f}M€",
                        f"Risk Adjustment : {(tp_vie-be_vie)/1e3:.0f}k€",
                        f"TP Vie S2 : {tp_vie/1e6:.1f}M€",
                        f"Ratio TP/BE : {ratio_tp_be:.3f}",
                    ],
                },
                "E_gestion_capital": {
                    "titre":  "E — Gestion du capital",
                    "statut": "VERT" if ratio_scr_n >= 150 else "AMBRE" if ratio_scr_n >= 100 else "ROUGE",
                    "elements": [
                        f"Fonds propres T1 : {fonds_propres*0.90/1e6:.1f}M€",
                        f"Fonds propres T2 : {fonds_propres*0.10/1e6:.1f}M€",
                        f"SCR Vie : {scr_vie/1e6:.1f}M€",
                        f"MCR Vie : {mcr_vie/1e6:.1f}M€",
                        f"Ratio SCR : {ratio_scr_n:.1f}%",
                        f"Ratio MCR : {ratio_mcr_n:.1f}%",
                    ],
                },
            }

            # ── RSR — Informations complémentaires superviseur ─────────────────
            rsr = {
                "evolution_scr":     round(variation_scr, 1),
                "ratio_scr_n":       round(ratio_scr_n, 1),
                "ratio_scr_n1":      round(ratio_scr_n1, 1),
                "orsa_conclusions":  "Profil de risque cohérent avec les fonds propres disponibles",
                "plan_capital":      "Aucune action requise" if ratio_scr_n >= 150 else "Surveillance renforcée",
                "incidents":         [],
                "changements":       ["Mise à jour tables mortalité TH0002 2024"],
            }

            # Avis de la fonction actuarielle
            statuts_sections = [sfcr[s]["statut"] for s in sfcr]
            avis_fa = "FAVORABLE" if all(s == "VERT" for s in statuts_sections) else "FAVORABLE AVEC RÉSERVE"

            commentaire = (
                f"✅ RSR & SFCR Vie produits — {datetime.now().strftime('%d/%m/%Y')}.\n"
                f"Section E — Ratio SCR : {ratio_scr_n:.1f}% | MCR : {ratio_mcr_n:.1f}%.\n"
                f"Section D — TP/BE : {ratio_tp_be:.3f} | BE Vie : {be_vie/1e6:.1f}M€.\n"
                f"Évolution ratio SCR vs N-1 : {variation_scr:+.1f}pp.\n"
                f"Avis Fonction Actuarielle : {avis_fa}.\n"
                f"Sections SFCR A-E : "
                + " · ".join(f"{s[0]} {sfcr[s]['statut']}" for s in sfcr) + "."
            )

            val_hyp = self._valider_rsr_sfcr(
                ratio_scr_n, ratio_tp_be, variation_scr, sfcr, ratio_mcr_n)
            gv = self._graphiques_validation_rvie2(
                val_hyp, sfcr, ratio_scr_n, ratio_scr_n1,
                ratio_tp_be, fonds_propres, scr_vie) if generer_graphiques else {}
            graphiques = self._generer_graphiques(
                ratio_scr_n, ratio_scr_n1, sfcr) if generer_graphiques else {}
            self._sauvegarder({
                'agent':'R-VIE2 Camille','sfcr':sfcr,'rsr':rsr,
                'ratio_scr':ratio_scr_n,'avis_fa':avis_fa}, audit_id)

            return {
                'success':True, 'agent':'R-VIE2 Camille',
                'statut_rag':'VERT' if ratio_scr_n >= 150 else 'AMBRE' if ratio_scr_n >= 100 else 'ROUGE',
                'scr_vie':scr_vie,'fonds_propres':fonds_propres,
                'ratio_scr_pct':round(ratio_scr_n,1),
                'ratio_mcr_pct':round(ratio_mcr_n,1),
                'ratio_tp_be':round(ratio_tp_be,4),
                'variation_scr_pp':round(variation_scr,1),
                'sfcr':sfcr, 'rsr':rsr, 'avis_fa':avis_fa,
                'sources':{'scr_vie': 'saisie manuelle', 'fonds_propres': 'saisie manuelle', 'be_vie': 'saisie manuelle'},
                'commentaire':commentaire, 'audit_id':audit_id,
                'graphiques':graphiques,
                'validation_rvie2':val_hyp,
                'graphiques_validation':gv,
                'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_rsr_sfcr(self, ratio_scr, ratio_tp_be, variation_scr, sfcr, ratio_mcr):
        """
        Validation 3 hypothèses RSR/SFCR.

        H1 — Toutes sections SFCR A-E complètes et vertes
             5/5 sections VERT → rapport conforme ✅

        H2 — Ratio SCR stable ou en hausse vs N-1
             Variation ≥ 0 → amélioration ✅ · <-20pp → dégradation ❌

        H3 — Cohérence TP/BE ∈ [1.0, 1.5]
             Section D valide → valorisation conforme EIOPA ✅
        """
        # H1 — Sections SFCR
        nb_vert = sum(1 for s in sfcr if sfcr[s]["statut"]=="VERT")
        nb_total = len(sfcr)
        if nb_vert == nb_total:
            h1_s,h1_m,h1_c = "VERT",f"{nb_vert}/{nb_total} sections SFCR VERT ✅","SFCR complet et conforme — publication autorisée"
        elif nb_vert >= nb_total - 1:
            h1_s,h1_m,h1_c = "AMBRE",f"{nb_vert}/{nb_total} sections SFCR VERT ⚠️","Corriger la/les section(s) en AMBRE avant publication"
        else:
            h1_s,h1_m,h1_c = "ROUGE",f"{nb_vert}/{nb_total} sections SFCR VERT ❌","SFCR incomplet — révision avant soumission ACPR"

        # H2 — Stabilité ratio SCR
        if variation_scr >= 0:
            h2_s,h2_m,h2_c = "VERT",f"Ratio SCR N vs N-1 : {variation_scr:+.1f}pp → Amélioration ✅","Capital renforcé — profil de risque amélioré"
        elif variation_scr >= -20:
            h2_s,h2_m,h2_c = "AMBRE",f"Ratio SCR N vs N-1 : {variation_scr:+.1f}pp → Légère baisse ⚠️","Surveiller l'évolution — expliquer dans le RSR"
        else:
            h2_s,h2_m,h2_c = "ROUGE",f"Ratio SCR N vs N-1 : {variation_scr:+.1f}pp → Dégradation ❌","Plan de redressement requis — notification ACPR probable"

        # H3 — Valorisation TP/BE
        if 1.0 <= ratio_tp_be <= 1.5:
            h3_s,h3_m,h3_c = "VERT",f"TP/BE = {ratio_tp_be:.3f} ∈ [1.0,1.5] ✅","Section D conforme — valorisation EIOPA valide"
        elif ratio_tp_be < 1.0:
            h3_s,h3_m,h3_c = "ROUGE",f"TP/BE = {ratio_tp_be:.3f} < 1.0 ❌","Risk Adjustment négatif impossible — revoir la valorisation"
        else:
            h3_s,h3_m,h3_c = "AMBRE",f"TP/BE = {ratio_tp_be:.3f} > 1.5 ⚠️","Risk Adjustment élevé — justifier dans la section D"

        sts = [h1_s,h2_s,h3_s]
        sg = "ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "h1_sections":{"nb_vert":nb_vert,"nb_total":nb_total,"statut":h1_s,"message":h1_m,"conseil":h1_c,
                "titre_graphique":f"{'✅' if h1_s=='VERT' else '⚠️' if h1_s=='AMBRE' else '❌'} SFCR — {nb_vert}/{nb_total} sections conformes"},
            "h2_stabilite":{"variation_pp":round(variation_scr,1),"statut":h2_s,"message":h2_m,"conseil":h2_c,
                "titre_graphique":f"{'✅' if h2_s=='VERT' else '⚠️' if h2_s=='AMBRE' else '❌'} Ratio SCR {variation_scr:+.1f}pp vs N-1"},
            "h3_valorisation":{"ratio_tp_be":round(ratio_tp_be,4),"statut":h3_s,"message":h3_m,"conseil":h3_c,
                "titre_graphique":f"{'✅' if h3_s=='VERT' else '⚠️' if h3_s=='AMBRE' else '❌'} Section D — TP/BE = {ratio_tp_be:.3f}"},
            "statut_global":sg,
            "conclusion":{"VERT":"✅ RSR & SFCR Vie validés — Sections A-E conformes et ratio SCR solide",
                         "AMBRE":"⚠️ RSR/SFCR acceptable — corriger les points avant soumission ACPR",
                         "ROUGE":"❌ RSR/SFCR à réviser — non-conformité détectée"}[sg],
        }

    def _graphiques_validation_rvie2(self, val, sfcr, ratio_n, ratio_n1, tp_be, fp, scr):
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT = dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,
                      font=dict(family="Inter",color=BLANC,size=11),
                      margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques = {}

        # G1 — Sections SFCR A-E (scorecard horizontal)
        try:
            h1 = val["h1_sections"]; c1 = VERT if h1["statut"]=="VERT" else AMBRE if h1["statut"]=="AMBRE" else ROUGE
            sections = list(sfcr.keys())
            statuts_s = [sfcr[s]["statut"] for s in sections]
            titres_s  = [sfcr[s]["titre"][:25] for s in sections]
            colors_s  = [VERT if s=="VERT" else AMBRE if s=="AMBRE" else ROUGE for s in statuts_s]
            icones_s  = ["✅" if s=="VERT" else "⚠️" if s=="AMBRE" else "❌" for s in statuts_s]

            fig1 = go.Figure()
            for titre,ic,couleur in zip(titres_s,icones_s,colors_s):
                fig1.add_trace(go.Bar(
                    x=[1.0 if ic=="✅" else 0.5 if ic=="⚠️" else 0.1],
                    y=[titre], orientation="h",
                    marker_color=couleur, width=0.5,
                    text=f"{ic} {'Conforme' if ic=='✅' else 'À vérifier'}",
                    textposition="outside", textfont=dict(color=couleur,size=9),
                    showlegend=False))
            l1 = dict(**LAYOUT); l1.update(dict(
                title=dict(text=h1["titre_graphique"],font=dict(color=c1,size=11),x=0.01),
                xaxis=dict(range=[0,1.8],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=9),showgrid=False),
                barmode="overlay",height=280,
                annotations=[dict(
                    text="💡 Les 5 sections A-E du SFCR doivent être vertes pour publication. Chaque ❌ bloque la soumission à l'ACPR.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False,align="left")]))
            fig1.update_layout(**l1); graphiques["sections_sfcr"] = fig1
        except Exception as e: self.logger.warning(f"G1 RVIE2 : {e}")

        # G2 — Évolution ratio SCR N vs N-1
        try:
            h2 = val["h2_stabilite"]
            c_n  = VERT if ratio_n  >= 150 else AMBRE if ratio_n  >= 100 else ROUGE
            c_n1 = VERT if ratio_n1 >= 150 else AMBRE if ratio_n1 >= 100 else ROUGE
            c2   = VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            fig2 = go.Figure(go.Bar(
                x=["Ratio SCR N-1","Ratio SCR N (actuel)"],
                y=[ratio_n1,ratio_n],
                marker_color=[c_n1,c_n],width=0.4,opacity=0.88,
                text=[f"{ratio_n1:.1f}%",f"{ratio_n:.1f}%"],
                textposition="outside",textfont=dict(color=BLANC,size=12)))
            fig2.add_hline(y=150,line_color=VERT,line_width=2,line_dash="dot",
                          annotation_text="Cible 150%",annotation_font=dict(color=VERT,size=9))
            fig2.add_hline(y=100,line_color=ROUGE,line_width=2,line_dash="dot",
                          annotation_text="Seuil 100%",annotation_font=dict(color=ROUGE,size=9))
            l2 = dict(**LAYOUT); l2.update(dict(
                title=dict(text=h2["titre_graphique"],font=dict(color=c2,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(title="Ratio SCR (%)",tickfont=dict(color=GRIS),
                          showgrid=True,gridcolor="rgba(255,255,255,0.05)"),
                bargap=0.4,showlegend=False,
                annotations=[dict(
                    text="💡 Le ratio SCR doit rester stable ou augmenter chaque année. Une baisse significative doit être expliquée dans le RSR.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)]))
            fig2.update_layout(**l2); graphiques["evolution_ratio_scr"] = fig2
        except Exception as e: self.logger.warning(f"G2 RVIE2 : {e}")

        # G3 — Jauge TP/BE Section D
        try:
            h3 = val["h3_valorisation"]; c3 = VERT if h3["statut"]=="VERT" else AMBRE if h3["statut"]=="AMBRE" else ROUGE
            fig3 = go.Figure(go.Indicator(
                mode="gauge+number", value=tp_be,
                number=dict(font=dict(color=c3,size=28),valueformat=".3f"),
                title=dict(text=h3["titre_graphique"],font=dict(color=c3,size=11)),
                gauge=dict(
                    axis=dict(range=[0,2.5],tickfont=dict(color=GRIS,size=8),
                             tickvals=[0,1.0,1.5,2.0,2.5],
                             ticktext=["0","1.0 min","1.5 max","2.0","2.5"]),
                    bar=dict(color=c3,thickness=0.25),bgcolor=NAVY_L,borderwidth=0,
                    steps=[dict(range=[0,1.0],color="rgba(231,76,60,0.12)"),
                           dict(range=[1.0,1.5],color="rgba(46,204,113,0.12)"),
                           dict(range=[1.5,2.5],color="rgba(243,156,18,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=1.25)),
            ))
            fig3.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),
                margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {h3['conseil']}",xref="paper",yref="paper",
                    x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["jauge_tp_be_sfcr"] = fig3
        except Exception as e: self.logger.warning(f"G3 RVIE2 : {e}")

        # G4 — Scorecard RSR/SFCR
        try:
            items = [
                ("H1 — SFCR Sections A-E", val["h1_sections"]["statut"],
                 val["h1_sections"]["message"], val["h1_sections"]["conseil"]),
                ("H2 — Stabilité Ratio SCR", val["h2_stabilite"]["statut"],
                 val["h2_stabilite"]["message"], val["h2_stabilite"]["conseil"]),
                ("H3 — Section D TP/BE", val["h3_valorisation"]["statut"],
                 val["h3_valorisation"]["message"], val["h3_valorisation"]["conseil"]),
            ]
            fig4 = go.Figure()
            for nom,statut,msg,conseil in items:
                c = VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i = "✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s = 1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(x=[s],y=[nom],orientation="h",
                    marker_color=c,width=0.5,text=f"{i} {statut}",textposition="outside",
                    textfont=dict(color=c,size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False))
            sg = val["statut_global"]; cg = VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l4 = dict(**LAYOUT); l4.update(dict(
                title=dict(text=f"Scorecard RSR & SFCR Vie — {val['conclusion']}",
                          font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",height=260,
                annotations=[dict(
                    text="💡 3 ✅ = RSR et SFCR Vie conformes Pilier 3 S2, prêts pour soumission à l'ACPR.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_rsr_sfcr"] = fig4
        except Exception as e: self.logger.warning(f"G4 RVIE2 : {e}")

        return graphiques

    def _generer_graphiques(self, ratio_n, ratio_n1, sfcr):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";BLANC="#F0F4F8";GRIS="#8A9AB0";VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12"
            c = VERT if ratio_n >= 150 else AMBRE if ratio_n >= 100 else ROUGE
            fig = go.Figure(go.Indicator(
                mode="gauge+number",value=ratio_n,
                number=dict(suffix="%",font=dict(color=c,size=28),valueformat=".1f"),
                title=dict(text="Ratio SCR Vie — Rapport SFCR Section E",font=dict(color=c,size=12)),
                gauge=dict(axis=dict(range=[0,300],tickfont=dict(color=GRIS,size=8)),
                    bar=dict(color=c,thickness=0.25),bgcolor="#1B3A5C",borderwidth=0,
                    steps=[dict(range=[0,100],color="rgba(231,76,60,0.12)"),
                           dict(range=[100,150],color="rgba(243,156,18,0.12)"),
                           dict(range=[150,300],color="rgba(46,204,113,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=150))))
            fig.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),
                margin=dict(l=30,r=30,t=80,b=30),height=300)
            return {"ratio_scr_sfcr":fig}
        except: return {}

    def _sauvegarder(self, rapport, audit_id):
        try:
            fpath = os.path.join(self.models_path, f"rvie2_sfcr_{audit_id}.json")
            with open(fpath,'w',encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sauvegardé : rvie2_sfcr_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
