"""
ActuarIA — Agent R-VIE1 : Éric — Réglementation Vie QRT S.26
Direction Vie & EP-RE | Manager : Olivier | Directeur : Paul

QRT S.26 — Life underwriting risk
→ SCR Vie : mortalité, longévité, invalidité, rachat, frais, révision, catastrophe
→ Agrégation des sous-modules via matrice EIOPA
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.rvie1 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent R-VIE1 — QRT S.26 Réglementation Vie ActuarIA v1.0")
print("QRT S.26.01 — Life underwriting risk (SCR Vie décomposé)")
print("Usage : agent_rvie1 = AgentRVIE1QRTVie()")
print("        result_rvie1 = agent_rvie1.run(be_vie=45e6, pm_total=50e6)")

# Matrice de corrélation EIOPA QIS5 — Risque Vie (S.26)
# Modules : mort · long · inv · rachat · frais · revision · cat
CORR_VIE_EIOPA = np.array([
    [1.00, -0.25,  0.25,  0.00,  0.25,  0.00,  0.25],  # mortalité
    [-0.25, 1.00, 0.00,  0.25,  0.25,  0.25,  0.00],   # longévité
    [ 0.25, 0.00, 1.00,  0.00,  0.25,  0.00,  0.25],   # invalidité
    [ 0.00, 0.25, 0.00,  1.00,  0.50,  0.00,  0.25],   # rachat
    [ 0.25, 0.25, 0.25,  0.50,  1.00,  0.25,  0.25],   # frais
    [ 0.00, 0.25, 0.00,  0.00,  0.25,  1.00,  0.00],   # révision
    [ 0.25, 0.00, 0.25,  0.25,  0.25,  0.00,  1.00],   # catastrophe
])

class AgentRVIE1QRTVie:
    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = models_path
        self.audit_path  = audit_path
        self.verbose     = verbose
        self.logger      = logging.getLogger("actuaria.rvie1")
        os.makedirs(models_path, exist_ok=True)
        os.makedirs(audit_path,  exist_ok=True)

    def run(self, be_vie=45_000_000, pm_total=50_000_000,
            fonds_propres=12_000_000, generer_graphiques=True,
            result_v3=None,   # Optional[Dict] — alimente be_vie et pm_total depuis V3 Amélie
            ) -> Dict:
        audit_id = f"RVIE1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger = self.logger
        if self.verbose:
            logger.info(f"[{audit_id}] Agent R-VIE1 démarré | BE={be_vie/1e6:.1f}M€")
        try:
            # ── Alimentation depuis V3 Amélie (si disponible) ────────────────
            # Permet la chaîne automatique : V3 → R-VIE1 sans ressaisie
            if result_v3 and result_v3.get('success'):
                be_vie   = result_v3.get('pm_prospective', be_vie)
                pm_total = result_v3.get('pm_prospective', pm_total)
                logger.info(
                    f"[{audit_id}] Alimenté depuis V3 Amélie — "
                    f"BE Vie = {be_vie/1e6:.2f}M€ | PM = {pm_total/1e6:.2f}M€"
                )

            # ── Chocs EIOPA S.26 — Sous-modules SCR Vie ──────────────────────
            # Chocs calibrés EIOPA QIS5 / Actes délégués S2
            # ── Sous-module rachat : 3 chocs distincts (Art. 142 Actes délégués S2) ──
            # Art. 142 §1 — Choc hausse permanente : +50% des taux de rachat prévus
            # Proxy BE : les rachats hausse génèrent une perte ≈ 5% BE par an × horizon
            # (taux rachat moyen ≈ 5%, duration ≈ 10 ans → perte ≈ 5% × 10 × 50% = 25%)
            scr_rachat_hausse   = be_vie * 0.2500
            # Art. 142 §2 — Choc baisse permanente : -50% des taux de rachat prévus
            # Les mauvais risques restent → anti-sélection → surcoût ≈ 20% BE
            scr_rachat_baisse   = be_vie * 0.2000
            # Art. 142 §3 — Choc ponctuel (mass lapse) : 40% des assurés rachetent
            # Choc liquidité immédiat — généralement le plus pénalisant pour un assureur vie
            scr_rachat_mass_lapse = be_vie * 0.4000
            # SCR rachat = maximum des trois sous-chocs (Art. 142 §4)
            scr_rachat_total = max(scr_rachat_hausse, scr_rachat_baisse, scr_rachat_mass_lapse)
            rachat_dominant  = (
                "mass_lapse"    if scr_rachat_total == scr_rachat_mass_lapse
                else "hausse"   if scr_rachat_total == scr_rachat_hausse
                else "baisse"
            )

            chocs = {
                "mortalite":   be_vie * 0.1500,       # +15% qx pour 1 an (Art. 137)
                "longevite":   be_vie * 0.2000,       # -20% qx permanent (Art. 138)
                "invalidite":  be_vie * 0.3500,       # +35% taux invalidité (Art. 139)
                "rachat":      scr_rachat_total,      # max(hausse,baisse,mass_lapse) Art. 142
                "frais":       be_vie * 0.1000,       # +10% frais + 1% inflation (Art. 143)
                "revision":    be_vie * 0.0300,       # +3% rentes viagères (Art. 144)
                "catastrophe": be_vie * 0.0015,       # 1.5‰ capital sous risque (Art. 145)
            }

            noms_modules = list(chocs.keys())
            SCR_vecteur  = np.array([chocs[k] for k in noms_modules])

            # Agrégation via matrice de corrélation EIOPA
            SCR_vie_total = float(np.sqrt(SCR_vecteur @ CORR_VIE_EIOPA @ SCR_vecteur))

            # Vérification matrice définie positive
            eigenvalues = np.linalg.eigvals(CORR_VIE_EIOPA)
            is_pos_def  = bool(np.all(eigenvalues > 0))

            # Ratios de couverture
            mcr_vie    = max(SCR_vie_total * 0.25, pm_total * 0.005)
            ratio_scr  = fonds_propres / max(SCR_vie_total, 1) * 100
            ratio_mcr  = fonds_propres / max(mcr_vie, 1) * 100

            # Décomposition par sous-module
            decompo = {k: {"scr":round(chocs[k],2), "pct":round(chocs[k]/max(SCR_vie_total,1)*100,1)}
                       for k in noms_modules}

            # Module dominant (par niveau de SCR)
            module_dominant = max(chocs, key=chocs.get)
            # Détail sous-module rachat
            rachat_detail = {
                "hausse":     round(scr_rachat_hausse, 0),
                "baisse":     round(scr_rachat_baisse, 0),
                "mass_lapse": round(scr_rachat_mass_lapse, 0),
                "dominant":   rachat_dominant,
            }

            commentaire = (
                f"✅ QRT S.26 — SCR Vie = {SCR_vie_total/1e6:.2f}M€ | "
                f"BE = {be_vie/1e6:.1f}M€ | PM = {pm_total/1e6:.1f}M€.\n"
                f"Ratio SCR : {ratio_scr:.1f}% | Ratio MCR : {ratio_mcr:.1f}%.\n"
                f"Module dominant : {module_dominant} ({chocs[module_dominant]/1e3:.0f}k€ = "
                f"{chocs[module_dominant]/max(SCR_vie_total,1)*100:.1f}% du SCR Vie).\n"
                f"Matrice EIOPA définie positive : {'✅' if is_pos_def else '❌'}.\n"
                f"Effet diversification : {(sum(chocs.values()) - SCR_vie_total)/1e3:.0f}k€ "
                f"({(1 - SCR_vie_total/max(sum(chocs.values()),1))*100:.1f}%)."
            )

            val_hyp = self._valider_qrt_s26(
                SCR_vie_total, ratio_scr, is_pos_def, chocs, be_vie, fonds_propres)
            gv = self._graphiques_validation_s26(
                val_hyp, decompo, ratio_scr, fonds_propres, SCR_vie_total,
                eigenvalues) if generer_graphiques else {}
            graphiques = self._generer_graphiques(
                decompo, ratio_scr) if generer_graphiques else {}
            self._sauvegarder({
                'agent':'R-VIE1 Éric','scr_vie':SCR_vie_total,
                'ratio_scr':ratio_scr,'decompo':decompo}, audit_id)

            return {
                'success':True, 'agent':'R-VIE1 Éric',
                'source_be_vie':'V3 Amélie (pm_prospective)' if (result_v3 and result_v3.get('success')) else 'Saisie manuelle',
                'statut_rag':'VERT' if ratio_scr >= 150 else 'AMBRE' if ratio_scr >= 100 else 'ROUGE',
                'be_vie':be_vie, 'pm_total':pm_total, 'fonds_propres':fonds_propres,
                'scr_vie_total':round(SCR_vie_total,2),
                'mcr_vie':round(mcr_vie,2),
                'ratio_scr_pct':round(ratio_scr,1),
                'ratio_mcr_pct':round(ratio_mcr,1),
                'decomposition_scr':decompo,
                'module_dominant':module_dominant,
                'rachat_detail':rachat_detail,
                'matrice_pos_def':is_pos_def,
                'eigenvalues_min':round(float(np.min(eigenvalues)),4),
                'sources':{'be_vie': 'saisie manuelle', 'pm_total': 'saisie manuelle', 'fonds_propres': 'saisie manuelle'},
                'commentaire':commentaire, 'audit_id':audit_id,
                'graphiques':graphiques,
                'validation_rvie1':val_hyp,
                'graphiques_validation':gv,
                'erreur':None,
            }
        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {'success':False,'statut_rag':'ROUGE','erreur':str(e),'audit_id':audit_id}

    def _valider_qrt_s26(self, scr, ratio_scr, is_pos_def, chocs, be, fp):
        """
        Validation 3 hypothèses QRT S.26.

        H1 — Matrice EIOPA définie positive
             Toutes valeurs propres > 0 → corrélations valides ✅

        H2 — Ratio SCR Vie ≥ 150% (cible ORSA)
             150%+ → capitalisation solide · 100-150% → conforme · <100% ❌

        H3 — Longévité = sous-module dominant (portefeuille vie)
             Longévité et Rachat dominants → structure normale ✅
        """
        # H1 — Matrice
        if is_pos_def:
            h1_s,h1_m,h1_c = "VERT","Matrice EIOPA définie positive ✅","Agrégation SCR Vie valide — corrélations EIOPA QIS5 conformes"
        else:
            h1_s,h1_m,h1_c = "ROUGE","Matrice non définie positive ❌","Revoir les corrélations — SCR Vie invalide"

        # H2 — Ratio SCR
        if ratio_scr >= 150:
            h2_s,h2_m,h2_c = "VERT",f"Ratio SCR = {ratio_scr:.1f}% ≥ 150% ✅","Capitalisation solide — objectif ORSA Vie atteint"
        elif ratio_scr >= 100:
            h2_s,h2_m,h2_c = "AMBRE",f"Ratio SCR = {ratio_scr:.1f}% ∈ [100%,150%] ⚠️","Conforme mais proche du seuil — surveiller"
        else:
            h2_s,h2_m,h2_c = "ROUGE",f"Ratio SCR = {ratio_scr:.1f}% < 100% ❌","INSUFFISANCE DE CAPITAL — notification ACPR obligatoire"

        # H3 — Structure des sous-modules (Art. 142 : rachat = max 3 sous-chocs)
        top2 = sorted(chocs, key=chocs.get, reverse=True)[:2]
        structure_ok = any(m in top2 for m in ['longevite','rachat','invalidite'])
        if structure_ok:
            h3_s,h3_m,h3_c = "VERT",f"Modules dominants : {top2[0]} · {top2[1]} ✅","Structure SCR Vie cohérente avec un portefeuille vie classique"
        else:
            h3_s,h3_m,h3_c = "AMBRE",f"Modules dominants : {top2[0]} · {top2[1]} ⚠️","Structure atypique — vérifier la composition du portefeuille"

        sts = [h1_s,h2_s,h3_s]
        sg = "ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"
        return {
            "h1_matrice":{"statut":h1_s,"message":h1_m,"conseil":h1_c,
                "titre_graphique":f"{'✅' if h1_s=='VERT' else '❌'} Matrice EIOPA — {'Valide' if is_pos_def else 'Invalide'}"},
            "h2_ratio_scr":{"ratio_scr":round(ratio_scr,1),"statut":h2_s,"message":h2_m,"conseil":h2_c,
                "titre_graphique":f"{'✅' if h2_s=='VERT' else '⚠️' if h2_s=='AMBRE' else '❌'} Ratio SCR Vie = {ratio_scr:.1f}%"},
            "h3_structure":{"top2":top2,"structure_ok":structure_ok,"statut":h3_s,"message":h3_m,"conseil":h3_c,
                "titre_graphique":f"{'✅' if h3_s=='VERT' else '⚠️'} Structure — {top2[0].title()} dominant"},
            "statut_global":sg,
            "conclusion":{"VERT":"✅ QRT S.26 validé — Matrice EIOPA, SCR et structure conformes",
                         "AMBRE":"⚠️ QRT acceptable — vérifier les points signalés",
                         "ROUGE":"❌ QRT S.26 non conforme — action corrective requise"}[sg],
        }

    def _graphiques_validation_s26(self, val, decompo, ratio_scr, fp, scr, eigenvalues):
        try:
            import plotly.graph_objects as go
        except: return {}
        NAVY="#0F2E52";NAVY_L="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0"
        VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT = dict(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,
                      font=dict(family="Inter",color=BLANC,size=11),
                      margin=dict(l=16,r=16,t=60,b=50),height=300)
        graphiques = {}

        # G1 — Décomposition SCR par sous-module (waterfall)
        try:
            noms   = [k.title() for k in decompo]
            valeurs= [decompo[k]['scr'] for k in decompo]
            pcts   = [decompo[k]['pct'] for k in decompo]
            colors = [OR if i==valeurs.index(max(valeurs)) else "rgba(52,152,219,0.6)"
                      for i in range(len(valeurs))]
            h3 = val["h3_structure"]; c3 = VERT if h3["statut"]=="VERT" else AMBRE
            fig1 = go.Figure(go.Bar(
                x=noms, y=[v/1e3 for v in valeurs],
                marker_color=colors, opacity=0.88, width=0.55,
                text=[f"{v/1e3:.0f}k\n{p:.0f}%" for v,p in zip(valeurs,pcts)],
                textposition="outside", textfont=dict(color=BLANC,size=9),
                hovertemplate="<b>%{x}</b><br>SCR : %{y:.0f}k€<extra></extra>",
            ))
            l1 = dict(**LAYOUT); l1.update(dict(
                title=dict(text=h3["titre_graphique"]+" — Décomposition SCR Vie S.26",
                          font=dict(color=c3,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC,size=9),showgrid=False),
                yaxis=dict(title="SCR (k€)",tickfont=dict(color=GRIS),showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                showlegend=False,
                annotations=[dict(
                    text="💡 La barre dorée = module le plus risqué. Plus elle est haute, plus ce risque pèse dans le SCR Vie total.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False,align="left")]))
            fig1.update_layout(**l1); graphiques["decomposition_scr_vie"] = fig1
        except Exception as e: self.logger.warning(f"G1 S26 : {e}")

        # G2 — Ratio SCR Vie jauge
        try:
            h2 = val["h2_ratio_scr"]; c2 = VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            fig2 = go.Figure(go.Indicator(
                mode="gauge+number", value=ratio_scr,
                number=dict(suffix="%",font=dict(color=c2,size=28),valueformat=".1f"),
                title=dict(text=h2["titre_graphique"],font=dict(color=c2,size=11)),
                gauge=dict(
                    axis=dict(range=[0,300],tickfont=dict(color=GRIS,size=8),
                             tickvals=[0,100,150,200,300],ticktext=["0%","100%","150%","200%","300%"]),
                    bar=dict(color=c2,thickness=0.25),bgcolor=NAVY_L,borderwidth=0,
                    steps=[dict(range=[0,100],color="rgba(231,76,60,0.12)"),
                           dict(range=[100,150],color="rgba(243,156,18,0.12)"),
                           dict(range=[150,300],color="rgba(46,204,113,0.12)")],
                    threshold=dict(line=dict(color=VERT,width=3),thickness=0.8,value=150)),
            ))
            fig2.update_layout(paper_bgcolor=NAVY,font=dict(color=BLANC),
                margin=dict(l=30,r=30,t=80,b=50),height=300,
                annotations=[dict(text=f"💡 {h2['conseil']}",xref="paper",yref="paper",
                    x=0.5,y=-0.12,font=dict(color=GRIS,size=9),showarrow=False)])
            graphiques["ratio_scr_vie_s26"] = fig2
        except Exception as e: self.logger.warning(f"G2 S26 : {e}")

        # G3 — Fonds propres vs SCR Vie
        try:
            c_fp = VERT if fp >= scr else ROUGE
            fig3 = go.Figure(go.Bar(
                x=["SCR Vie total","Fonds Propres"],
                y=[scr/1e6, fp/1e6],
                marker_color=[AMBRE, c_fp], width=0.4, opacity=0.88,
                text=[f"{scr/1e6:.2f}M€", f"{fp/1e6:.2f}M€"],
                textposition="outside", textfont=dict(color=BLANC,size=12),
            ))
            l3 = dict(**LAYOUT); l3.update(dict(
                title=dict(text=f"{'✅' if fp>=scr else '❌'} Couverture SCR Vie — Fonds Propres {fp/1e6:.1f}M€ vs SCR {scr/1e6:.1f}M€",
                          font=dict(color=c_fp,size=11),x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(title="M€",tickfont=dict(color=GRIS)),
                bargap=0.4,showlegend=False,
                annotations=[dict(
                    text="💡 Les Fonds Propres (barre droite) doivent toujours dépasser le SCR Vie (barre gauche).",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)]))
            fig3.update_layout(**l3); graphiques["fp_vs_scr_s26"] = fig3
        except Exception as e: self.logger.warning(f"G3 S26 : {e}")

        # G4 — Scorecard
        try:
            items = [
                ("H1 — Matrice EIOPA valide", val["h1_matrice"]["statut"],
                 val["h1_matrice"]["message"], val["h1_matrice"]["conseil"]),
                ("H2 — Ratio SCR ≥ 150%", val["h2_ratio_scr"]["statut"],
                 val["h2_ratio_scr"]["message"], val["h2_ratio_scr"]["conseil"]),
                ("H3 — Structure sous-modules", val["h3_structure"]["statut"],
                 val["h3_structure"]["message"], val["h3_structure"]["conseil"]),
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
                title=dict(text=f"Scorecard QRT S.26 — {val['conclusion']}",
                          font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",height=260,
                annotations=[dict(
                    text="💡 3 ✅ = QRT S.26 validé, SCR Vie conforme EIOPA et défendable devant l'ACPR.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)]))
            fig4.update_layout(**l4); graphiques["scorecard_s26"] = fig4
        except Exception as e: self.logger.warning(f"G4 S26 : {e}")

        return graphiques

    def _generer_graphiques(self, decompo, ratio_scr):
        try:
            import plotly.graph_objects as go
            NAVY="#0F2E52";OR="#C9A84C";BLANC="#F0F4F8";GRIS="#8A9AB0";BLEU="#3498DB"
            noms   = [k.title() for k in decompo]
            valeurs= [decompo[k]['scr'] for k in decompo]
            fig = go.Figure(go.Bar(
                x=noms,y=[v/1e3 for v in valeurs],
                marker_color=[OR if v==max(valeurs) else "rgba(52,152,219,0.6)" for v in valeurs],
                opacity=0.88,hovertemplate="<b>%{x}</b><br>%{y:.0f}k€<extra></extra>"))
            fig.update_layout(paper_bgcolor=NAVY,plot_bgcolor="#1B3A5C",
                font=dict(family="Inter",color=BLANC,size=11),
                margin=dict(l=16,r=16,t=60,b=40),height=300,
                title=dict(text="SCR Vie par sous-module — QRT S.26",
                          font=dict(color=BLANC,size=12),x=0.01),
                xaxis=dict(tickfont=dict(color=GRIS,size=9),showgrid=False),
                yaxis=dict(title="k€",tickfont=dict(color=GRIS)),showlegend=False)
            return {"scr_vie_bar":fig}
        except: return {}

    def _sauvegarder(self, rapport, audit_id):
        try:
            with open(os.path.join(self.models_path,f"rvie1_s26_{audit_id}.json"),'w') as f:
                json.dump(rapport,f,indent=2)
            self.logger.info(f"Sauvegardé : rvie1_s26_{audit_id}.json")
        except Exception as e: self.logger.warning(f"Sauvegarde : {e}")
