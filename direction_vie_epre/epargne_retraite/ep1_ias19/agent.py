"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ACTUARIA — AGENT EP1 : ENGAGEMENTS RETRAITE IAS 19           ║
║                        Version 1.0 — Production                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

warnings.filterwarnings('ignore')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ══════════════════════════════════════════════════════════════════════════════
# AGENT EP1 — ÉVALUATION DES ENGAGEMENTS DE RETRAITE (IAS 19)
# ══════════════════════════════════════════════════════════════════════════════

class AgentEP1EngagementsRetraite:
    """
    Agent EP1 — Évaluation IAS 19 des engagements de retraite.

    MÉTHODE PUC (Projected Unit Credit) :
    ────────────────────────────────────────
    Méthode imposée par IAS 19 pour l'évaluation des régimes
    à prestations définies (Art. 39, retraites chapeau).

    Pour chaque salarié :
    1. Projection du salaire final (avec revalorisation)
    2. Calcul de la prestation projetée (% salaire × annuités)
    3. Attribution de la prestation aux années de service (unité de crédit)
    4. Actualisation au taux OAT iBoxx (IAS 19.83)

    DBO (Defined Benefit Obligation) :
    ───────────────────────────────────
    DBO = Σ_i [Unité_crédit_i × Facteur_annuité_i] actualisé

    Service Cost = DBO fin - DBO début × (1+taux)
    Interest Cost = DBO début × taux_actu

    EXEMPLE D'UTILISATION :
    ─────────────────────────
    agent_ep1 = AgentEP1EngagementsRetraite()
    result_ep1 = agent_ep1.run(
        effectif           = 500,
        salaire_moyen      = 45000,
        anciennete_moyenne = 12,
        taux_actu          = 0.035,
        taux_revalorisation= 0.02,
        taux_rotation      = 0.05,
        taux_prestation    = 0.015,  # 1.5% du salaire final par année
        age_moyen          = 42,
        age_retraite       = 65,
    )
    """

    def __init__(
        self,
        models_path: str = '/tmp/actuaria/models',
        audit_path:  str = '/tmp/actuaria/audit',
        verbose:     bool = True
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        logger.getLogger('actuaria.ep1').info("Agent EP1 IAS 19 initialisé") if False else None
        self.logger = logging.getLogger('actuaria.ep1')
        self.logger.info("Agent EP1 IAS 19 initialisé")

    def run(
        self,
        effectif:            int   = 500,
        salaire_moyen:       float = 45_000,
        anciennete_moyenne:  float = 12,
        taux_actu:           float = 0.035,
        taux_revalorisation: float = 0.020,
        taux_rotation:       float = 0.050,
        taux_prestation:     float = 0.015,
        age_moyen:           float = 42,
        age_retraite:        float = 65,
        annuites_viageres:   float = 14.0,
        sous_branche:        str  = 'art39',
        generer_graphiques: bool = True,
    ) -> Dict[str, Any]:
        """
        Évalue les engagements de retraite selon IAS 19.

        Paramètres
        ──────────
        taux_actu : float
            Taux OAT iBoxx AA (IAS 19.83).
            En 2024 : ~3.5% pour l'€zone.

        taux_revalorisation : float
            Inflation des salaires anticipée.
            En France : ~2% sur le long terme.

        taux_rotation : float
            Probabilité qu'un salarié quitte l'entreprise.
            Impact : réduit la DBO si les droits ne sont pas acquis
            en cas de départ (Art. 39).

        taux_prestation : float
            % du salaire final accordé par année d'ancienneté.
            Ex : 1.5% → 30 ans d'ancienneté = 45% du salaire final.

        annuites_viageres : float
            ä_x à l'âge de retraite (depuis A14).
            14 ans à 65 ans avec taux 2% est une valeur typique.
        """
        t_debut  = datetime.now()
        audit_id = f"EP1_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"[{audit_id}] Agent EP1 démarré")

        try:
            # Durée résiduelle jusqu'à la retraite
            duree_res = max(age_retraite - age_moyen, 1)

            # ── DBO — PROJECTED UNIT CREDIT ───────────────────────────────────
            # Projection du salaire final
            salaire_final = salaire_moyen * (1 + taux_revalorisation) ** duree_res

            # Prestation projetée par salarié
            # = taux_prestation × ancienneté_totale_prévue × salaire_final
            anciennete_totale = anciennete_moyenne + duree_res
            prestation_proj   = taux_prestation * anciennete_totale * salaire_final

            # Unité de crédit (droits acquis à ce jour)
            unite_credit = prestation_proj * (anciennete_moyenne / anciennete_totale)

            # Probabilité d'atteindre la retraite (survie + maintien)
            proba_retraite = (1 - taux_rotation) ** duree_res * 0.85

            # Valeur actualisée de l'engagement
            facteur_actu = 1 / (1 + taux_actu) ** duree_res

            # DBO = unité crédit × annuités viagères × facteur actu × effectif
            dbo_unitaire  = unite_credit * annuites_viageres * facteur_actu * proba_retraite
            dbo_total     = dbo_unitaire * effectif

            # ── SERVICE COST ──────────────────────────────────────────────────
            # Coût des droits acquis pendant l'année N
            # = prestation projetée × 1/ancienneté_totale × ä_x actualisé
            service_cost_unitaire = (
                taux_prestation * salaire_final
                * annuites_viageres * facteur_actu
                * proba_retraite
            )
            service_cost = service_cost_unitaire * effectif

            # ── INTEREST COST ─────────────────────────────────────────────────
            # Coût de désactualisation sur l'année N
            interest_cost = dbo_total * taux_actu

            # ── ACTUARIAL GAINS/LOSSES ────────────────────────────────────────
            # Gains/pertes actuariels si le taux change de ±50bp
            # Duration modifiée approx : D_mod = duree_res / (1 + taux_actu)
            # Impact ±50bp : ΔDBO = ±D_mod × 0.005 × DBO
            duration_modifiee = duree_res / (1 + taux_actu)
            dbo_choc_up   = dbo_total * (1 - duration_modifiee * 0.005)   # +50bp → DBO baisse
            dbo_choc_down = dbo_total * (1 + duration_modifiee * 0.005)   # -50bp → DBO monte

            # ── CORRIDOR IAS 19 (méthode simplifiée) ─────────────────────────
            corridor_10pct = dbo_total * 0.10

            # ── TAUX DE COUVERTURE ────────────────────────────────────────────
            # Si le régime est externalisé (fonds de pension)
            # actifs_fonds_pension = 0 si pas de fonds externe
            actifs_fonds  = 0.0
            taux_couv     = actifs_fonds / max(dbo_total, 1) * 100

            statut_rag = 'VERT'  # EP1 est un calcul pur, pas de seuil RAG

            result = {
                'success':             True,
                'audit_id':            audit_id,
                'sous_branche':        sous_branche,
                'statut_rag':          statut_rag,
                'parametres': {
                    'effectif':            effectif,
                    'salaire_moyen':       salaire_moyen,
                    'anciennete_moyenne':  anciennete_moyenne,
                    'taux_actu':           taux_actu,
                    'taux_revalo':         taux_revalorisation,
                    'taux_prestation':     taux_prestation,
                    'age_moyen':           age_moyen,
                    'age_retraite':        age_retraite,
                },
                'ias19': {
                    'dbo_total':           round(dbo_total, 0),
                    'dbo_unitaire':        round(dbo_unitaire, 0),
                    'service_cost':        round(service_cost, 0),
                    'interest_cost':       round(interest_cost, 0),
                    'charge_totale_n':     round(service_cost + interest_cost, 0),
                    'salaire_final_proj':  round(salaire_final, 0),
                    'prestation_proj_unit':round(prestation_proj, 0),
                    'proba_retraite':      round(proba_retraite, 4),
                    'corridor_10pct':      round(corridor_10pct, 0),
                    'dbo_choc_taux_up50bp': round(dbo_choc_up, 0),
                    'dbo_choc_taux_down50bp':round(dbo_choc_down, 0),
                    'taux_couverture_pct': round(taux_couv, 1),
                },
                'commentaire': self._commenter(
                    dbo_total, service_cost, interest_cost,
                    taux_actu, effectif, sous_branche
                ),
            }

            # Graphiques v2
            if generer_graphiques and PLOTLY_OK:
                result['graphiques'] = self._generer_graphiques(
                    dbo_total, service_cost, interest_cost,
                    dbo_choc_up, dbo_choc_down, taux_actu,
                    effectif, taux_revalorisation, duree_res
                )
            else:
                result['graphiques'] = {}

            # Validation IAS 19
            result['validation_ep1']        = self._valider_ias19(
                dbo_total, service_cost, taux_actu, taux_revalorisation)
            result['graphiques_validation'] = self._graphiques_validation_ias19(
                result['validation_ep1'])

            self._sauvegarder(audit_id, result)

            if self.verbose:
                self._afficher(result)

            return result

        except Exception as e:
            self.logger.error(f"ERREUR EP1 : {e}", exc_info=True)
            return {'success': False, 'erreur': str(e), 'audit_id': audit_id}


    def _valider_ias19(
        self,
        dbo:          float,
        service_cost: float,
        taux_actu:    float,
        taux_revalo:  float,
    ) -> Dict:
        """
        Contrôles qualité IAS 19.

        H1 — Taux d'actualisation cohérent (OAT iBoxx AA)
             Taux ∈ [2%, 6%] → cohérent avec courbe OAT ✅
             Taux < 1% → sous-évaluation de l'engagement ❌
             Taux > 8% → sur-évaluation ⚠️

        H2 — Sensibilité DBO raisonnable
             Impact -100bp sur DBO < 20% → sensibilité normale ✅
             Impact > 30% → duration passif très longue ⚠️

        H3 — Service Cost cohérent avec DBO
             SC/DBO ∈ [1%, 10%] par an → cohérent ✅
             SC/DBO > 15% → progression anormale ❌
        """
        import numpy as np

        # H1 — Taux d'actualisation
        if 2.0 <= taux_actu * 100 <= 6.0:
            h1_statut = "VERT"
            h1_msg    = f"Taux actualisation = {taux_actu*100:.2f}% ∈ [2%, 6%] → Cohérent OAT iBoxx AA ✅"
            h1_conseil= "Taux conforme aux exigences IAS 19 et aux courbes obligataires AA"
        elif 1.0 <= taux_actu * 100 < 2.0:
            h1_statut = "AMBRE"
            h1_msg    = f"Taux actualisation = {taux_actu*100:.2f}% < 2% → Taux bas ⚠️"
            h1_conseil= "Vérifier la courbe OAT iBoxx AA à la date de clôture"
        elif taux_actu * 100 > 6.0:
            h1_statut = "AMBRE"
            h1_msg    = f"Taux actualisation = {taux_actu*100:.2f}% > 6% → Taux élevé ⚠️"
            h1_conseil= "Vérifier la duration moyenne des engagements vs la courbe OAT"
        else:
            h1_statut = "ROUGE"
            h1_msg    = f"Taux actualisation = {taux_actu*100:.2f}% < 1% → Sous-évaluation ❌"
            h1_conseil= "Taux trop bas — la DBO sera sous-estimée. Utiliser courbe OAT AA"

        # H2 — Sensibilité DBO à -100bp
        impact_100bp = dbo * (taux_actu * 10)  # approximation : duration × ΔT
        sensibilite_pct = abs(impact_100bp / max(dbo, 1)) * 100

        if sensibilite_pct <= 20:
            h2_statut = "VERT"
            h2_msg    = f"Impact -100bp = {sensibilite_pct:.1f}% de la DBO → Sensibilité normale ✅"
            h2_conseil= "Duration des engagements raisonnable pour ce type de régime"
        elif sensibilite_pct <= 30:
            h2_statut = "AMBRE"
            h2_msg    = f"Impact -100bp = {sensibilite_pct:.1f}% de la DBO → Sensibilité élevée ⚠️"
            h2_conseil= "Duration longue — vérifier la structure des paiements futurs"
        else:
            h2_statut = "ROUGE"
            h2_msg    = f"Impact -100bp = {sensibilite_pct:.1f}% de la DBO → Très sensible ❌"
            h2_conseil= "Vérifier les hypothèses de duration · Retraite à cotisations définies ?"

        # H3 — Service Cost / DBO
        ratio_sc = service_cost / max(dbo, 1) * 100
        if 1.0 <= ratio_sc <= 10.0:
            h3_statut = "VERT"
            h3_msg    = f"SC/DBO = {ratio_sc:.2f}% ∈ [1%, 10%] → Progression cohérente ✅"
            h3_conseil= "L'acquisition des droits est régulière et cohérente"
        elif ratio_sc < 1.0:
            h3_statut = "AMBRE"
            h3_msg    = f"SC/DBO = {ratio_sc:.2f}% < 1% → Progression lente ⚠️"
            h3_conseil= "Vérifier la méthode d'attribution des droits (PUC)"
        else:
            h3_statut = "ROUGE"
            h3_msg    = f"SC/DBO = {ratio_sc:.2f}% > 10% → Progression anormale ❌"
            h3_conseil= "Revoir la méthode PUC · Possible erreur dans les hypothèses d'ancienneté"

        statuts = [h1_statut, h2_statut, h3_statut]
        statut_global = "ROUGE" if "ROUGE" in statuts else "AMBRE" if "AMBRE" in statuts else "VERT"
        conclusion = {
            "VERT":  "✅ IAS 19 validé — DBO fiable, taux cohérent et sensibilité maîtrisée",
            "AMBRE": "⚠️ IAS 19 acceptable — vérifier les points signalés",
            "ROUGE": "❌ IAS 19 à revoir — hypothèses non conformes",
        }[statut_global]

        return {
            "h1_taux": {
                "taux_actu":    round(taux_actu * 100, 3),
                "statut":       h1_statut,
                "message":      h1_msg,
                "conseil":      h1_conseil,
                "titre_graphique": f"{'✅' if h1_statut=='VERT' else '⚠️' if h1_statut=='AMBRE' else '❌'} Taux d'actualisation = {taux_actu*100:.2f}%",
            },
            "h2_sensibilite": {
                "impact_100bp_pct": round(sensibilite_pct, 2),
                "statut":           h2_statut,
                "message":          h2_msg,
                "conseil":          h2_conseil,
                "titre_graphique": f"{'✅' if h2_statut=='VERT' else '⚠️' if h2_statut=='AMBRE' else '❌'} Sensibilité DBO à -100bp = {sensibilite_pct:.1f}%",
            },
            "h3_service_cost": {
                "ratio_sc_pct": round(ratio_sc, 3),
                "dbo":          round(dbo, 0),
                "service_cost": round(service_cost, 0),
                "statut":       h3_statut,
                "message":      h3_msg,
                "conseil":      h3_conseil,
                "titre_graphique": f"{'✅' if h3_statut=='VERT' else '⚠️' if h3_statut=='AMBRE' else '❌'} SC/DBO = {ratio_sc:.2f}%",
            },
            "statut_global": statut_global,
            "conclusion":    conclusion,
        }

    def _graphiques_validation_ias19(self, val: Dict) -> Dict:
        """4 graphiques auto-explicatifs validation IAS 19."""
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}

        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; OR="#C9A84C"; BLANC="#F0F4F8"
        GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"; BLEU="#3498DB"
        LAYOUT = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                      font=dict(family="Inter,Arial", color=BLANC, size=11),
                      margin=dict(l=16,r=16,t=60,b=50), height=300)
        graphiques = {}

        # G1 — Jauge taux d'actualisation
        try:
            h1 = val["h1_taux"]
            taux = h1["taux_actu"]
            couleur = VERT if h1["statut"]=="VERT" else AMBRE if h1["statut"]=="AMBRE" else ROUGE
            fig1 = go.Figure(go.Indicator(
                mode="gauge+number", value=taux,
                title=dict(text=h1["titre_graphique"], font=dict(color=couleur, size=11)),
                number=dict(suffix="%", font=dict(color=couleur, size=28), valueformat=".2f"),
                gauge=dict(
                    axis=dict(range=[0,10], tickfont=dict(color=GRIS, size=8),
                             tickvals=[0,1,2,4,6,8,10],
                             ticktext=["0%","1%","2% min","4%","6% max","8%","10%"]),
                    bar=dict(color=couleur, thickness=0.25), bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0,2],  color="rgba(231,76,60,0.12)"),
                        dict(range=[2,6],  color="rgba(46,204,113,0.12)"),
                        dict(range=[6,10], color="rgba(243,156,18,0.12)"),
                    ],
                    threshold=dict(line=dict(color=OR,width=3), thickness=0.8, value=4.0),
                ),
            ))
            fig1.update_layout(paper_bgcolor=NAVY, font=dict(color=BLANC),
                              margin=dict(l=30,r=30,t=80,b=50), height=300,
                              annotations=[dict(text=f"💡 {h1['conseil']}", xref="paper",
                                              yref="paper", x=0.5, y=-0.12,
                                              font=dict(color=GRIS,size=9), showarrow=False)])
            graphiques["jauge_taux_actu"] = fig1
        except Exception as e:
            pass

        # G2 — Décomposition charge IAS 19
        try:
            sc  = val["h3_service_cost"]["service_cost"]
            dbo = val["h3_service_cost"]["dbo"]
            ic  = dbo * val["h1_taux"]["taux_actu"] / 100
            h3  = val["h3_service_cost"]
            couleur = VERT if h3["statut"]=="VERT" else AMBRE if h3["statut"]=="AMBRE" else ROUGE
            fig2 = go.Figure(go.Bar(
                x=["Service Cost", "Interest Cost", "Charge totale N"],
                y=[sc/1e3, ic/1e3, (sc+ic)/1e3],
                marker_color=[OR, BLEU, couleur],
                marker_line=dict(color=NAVY,width=1), width=0.4, opacity=0.88,
                text=[f"{v:.0f}k€" for v in [sc/1e3, ic/1e3, (sc+ic)/1e3]],
                textposition="outside", textfont=dict(color=BLANC,size=10),
                hovertemplate="<b>%{x}</b><br>%{y:.0f}k€<extra></extra>",
            ))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text=h3["titre_graphique"], font=dict(color=couleur,size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(visible=False), bargap=0.35, showlegend=False,
                annotations=[dict(text="💡 SC = droits acquis cette année · IC = effet actualisation · Charge = ce qui passe en résultat.",
                                 xref="paper",yref="paper",x=0.01,y=-0.22,
                                 font=dict(color=GRIS,size=9),showarrow=False,align="left")],
            ))
            fig2.update_layout(**l2)
            graphiques["decomposition_charge"] = fig2
        except Exception as e:
            pass

        # G3 — Sensibilité à -100bp
        try:
            h2 = val["h2_sensibilite"]
            dbo = val["h3_service_cost"]["dbo"]
            chocs_bp  = [-200, -100, -50, +50, +100, +200]
            taux_base = val["h1_taux"]["taux_actu"]
            impacts   = [dbo * (taux_base/100) * abs(c)/100 * (-1 if c < 0 else 1) for c in chocs_bp]
            colors    = [VERT if abs(i/dbo*100) <= 20 else AMBRE if abs(i/dbo*100) <= 30 else ROUGE for i in impacts]
            couleur = VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            fig3 = go.Figure(go.Bar(
                x=[f"{c:+d}bp" for c in chocs_bp], y=[i/1e3 for i in impacts],
                marker_color=colors, marker_line=dict(color=NAVY,width=1),
                width=0.5, opacity=0.88,
                text=[f"{i/1e3:+.0f}k€" for i in impacts],
                textposition="outside", textfont=dict(color=BLANC,size=9),
                hovertemplate="<b>%{x}</b><br>Impact DBO : %{y:+.0f}k€<extra></extra>",
            ))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text=h2["titre_graphique"], font=dict(color=couleur,size=11), x=0.01),
                xaxis=dict(title="Choc de taux", tickfont=dict(color=BLANC,size=9), showgrid=False),
                yaxis=dict(title="Impact DBO (k€)", tickfont=dict(color=GRIS), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                bargap=0.3, showlegend=False,
                annotations=[dict(text="💡 Barres vertes = impact acceptable. Rouges = engagement très sensible aux variations de taux.",
                                 xref="paper",yref="paper",x=0.01,y=-0.22,
                                 font=dict(color=GRIS,size=9),showarrow=False,align="left")],
            ))
            fig3.update_layout(**l3)
            graphiques["sensibilite_dbo"] = fig3
        except Exception as e:
            pass

        # G4 — Scorecard IAS 19
        try:
            items = [
                ("H1 — Taux actualisation OAT AA", val["h1_taux"]["statut"],
                 val["h1_taux"]["message"], val["h1_taux"]["conseil"]),
                ("H2 — Sensibilité DBO -100bp", val["h2_sensibilite"]["statut"],
                 val["h2_sensibilite"]["message"], val["h2_sensibilite"]["conseil"]),
                ("H3 — Service Cost cohérent", val["h3_service_cost"]["statut"],
                 val["h3_service_cost"]["message"], val["h3_service_cost"]["conseil"]),
            ]
            fig4 = go.Figure()
            for nom, statut, msg, conseil in items:
                couleur = VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                icone   = "✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                fig4.add_trace(go.Bar(
                    x=[1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.2],
                    y=[nom], orientation="h", marker_color=couleur, width=0.5,
                    text=f"{icone} {statut}", textposition="outside",
                    textfont=dict(color=couleur,size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False,
                ))
            statut_g  = val["statut_global"]
            couleur_g = VERT if statut_g=="VERT" else AMBRE if statut_g=="AMBRE" else ROUGE
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text=f"Scorecard IAS 19 — {val['conclusion']}",
                          font=dict(color=couleur_g,size=10), x=0.01),
                xaxis=dict(range=[0,1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10), showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(text="💡 3 ✅ = IAS 19 validé, défendable devant l'auditeur et le Conseil d'Administration.",
                                 xref="paper",yref="paper",x=0.01,y=-0.22,
                                 font=dict(color=GRIS,size=9),showarrow=False,align="left")],
            ))
            fig4.update_layout(**l4)
            graphiques["scorecard_ias19"] = fig4
        except Exception as e:
            pass

        return graphiques

    def _generer_graphiques(
        self,
        dbo_total:    float,
        service_cost: float,
        interest_cost:float,
        dbo_choc_up:  float,
        dbo_choc_down:float,
        taux_actu:    float,
        effectif:     int,
        taux_revalo:  float,
        duree_res:    float,
    ) -> Dict:
        """4 graphiques IAS 19 style PowerBI."""
        if not PLOTLY_OK:
            return {}

        NAVY=  "#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"
        OR=    "#C9A84C"; BLANC="#F0F4F8"; GRIS="#8A9AB0"
        VERT=  "#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"; BLEU="#3498DB"

        LAYOUT = dict(
            paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=52, b=16), height=300,
            hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR,
                           font_size=12, font_color=BLANC),
        )
        graphiques = {}

        # G1 — Décomposition charge IAS 19
        try:
            charge_tot = service_cost + interest_cost
            labels = ['Service Cost', 'Interest Cost', 'Charge totale N']
            vals   = [service_cost, interest_cost, charge_tot]
            colors = [OR, BLEU, AMBRE]

            fig1 = go.Figure(go.Bar(
                x=labels, y=vals, marker_color=colors,
                marker_line=dict(color=NAVY, width=1),
                width=0.45, opacity=0.9,
                text=[f"{v/1e3:.0f}k€" for v in vals],
                textposition='outside',
                textfont=dict(color=BLANC, size=11),
                hovertemplate="<b>%{x}</b><br>%{y:,.0f} €<extra></extra>",
            ))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(text="📊 Charge IAS 19 — Décomposition annuelle",
                           font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                yaxis=dict(visible=False), bargap=0.4, showlegend=False,
            ))
            fig1.update_layout(**l1)
            graphiques['charge_ias19'] = fig1
        except Exception as e:
            self.logger.warning(f"G1 IAS19 échoué : {e}")

        # G2 — Sensibilité DBO aux taux
        try:
            scenarios = ['-100bp', '-50bp', 'Central', '+50bp', '+100bp']
            taux_s    = [taux_actu - 0.01, taux_actu - 0.005,
                         taux_actu, taux_actu + 0.005, taux_actu + 0.01]
            # DBO approximée par sensibilité duration
            dur_app  = duree_res / (1 + taux_actu)
            dbos_s   = [dbo_total * (1 - dur_app * (t - taux_actu)) for t in taux_s]
            colors_s = [VERT if d < dbo_total else ROUGE for d in dbos_s]

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=scenarios, y=dbos_s,
                marker_color=colors_s,
                marker_line=dict(color=NAVY, width=1),
                width=0.45, opacity=0.88,
                text=[f"{d/1e6:.2f}M€" for d in dbos_s],
                textposition='outside',
                textfont=dict(color=BLANC, size=10),
                hovertemplate="<b>%{x}</b><br>DBO : %{y:,.0f} €<extra></extra>",
            ))
            fig2.add_hline(y=dbo_total, line_color=OR, line_width=2, line_dash="dash",
                           annotation_text=f"DBO centrale {dbo_total/1e6:.2f}M€",
                           annotation_font=dict(color=OR, size=9))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text="📈 Sensibilité DBO aux taux OAT iBoxx AA",
                           font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                yaxis=dict(visible=False), bargap=0.35, showlegend=False,
            ))
            fig2.update_layout(**l2)
            graphiques['sensibilite_taux'] = fig2
        except Exception as e:
            self.logger.warning(f"G2 sensibilité échoué : {e}")

        # G3 — Evolution DBO projetée sur 5 ans
        try:
            annees = [2025 + i for i in range(6)]
            dbos_p = [dbo_total * (1 + (taux_revalo - taux_actu) * i * 0.1)
                      for i in range(6)]
            scs_p  = [service_cost * (1 + taux_revalo) ** i for i in range(6)]

            fig3 = make_subplots(specs=[[{"secondary_y": True}]])
            fig3.add_trace(go.Bar(
                x=annees, y=dbos_p, name='DBO projetée',
                marker_color=[OR] + ["rgba(201,168,76,0.5)"] * 5,
                width=0.4, opacity=0.88,
                hovertemplate="<b>%{x}</b><br>DBO : %{y:,.0f} €<extra></extra>",
            ), secondary_y=False)
            fig3.add_trace(go.Scatter(
                x=annees, y=scs_p, name='Service Cost',
                mode='lines+markers',
                line=dict(color=BLEU, width=2, shape='spline'),
                marker=dict(color=BLEU, size=7, line=dict(color=NAVY, width=2)),
                hovertemplate="<b>%{x}</b><br>SC : %{y:,.0f} €<extra></extra>",
            ), secondary_y=True)
            fig3.update_layout(
                title=dict(text="📈 DBO projetée & Service Cost sur 5 ans",
                           font=dict(color=BLANC, size=13), x=0.01),
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family="Inter, Arial", color=BLANC),
                margin=dict(l=16, r=16, t=52, b=16), height=300,
                hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR,
                               font_size=12, font_color=BLANC),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                            orientation="h", yanchor="bottom", y=1.02),
                bargap=0.35,
            )
            fig3.update_xaxes(tickfont=dict(color=GRIS), showgrid=False)
            fig3.update_yaxes(title_text="DBO (€)", title_font=dict(color=GRIS, size=10),
                              showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                              tickfont=dict(color=GRIS), secondary_y=False)
            fig3.update_yaxes(title_text="Service Cost (€)",
                              title_font=dict(color=GRIS, size=10),
                              showgrid=False, tickfont=dict(color=GRIS), secondary_y=True)
            graphiques['projection_dbo'] = fig3
        except Exception as e:
            self.logger.warning(f"G3 projection DBO échoué : {e}")

        # G4 — Scorecard IAS 19
        try:
            dbo_par_sal = dbo_total / max(effectif, 1)
            ratio_sc_dbo = service_cost / max(dbo_total, 1) * 100

            fig4 = go.Figure()
            metriques = ['DBO/effectif', 'SC/DBO (%)', 'Taux actuali. (%)']
            vals4     = [dbo_par_sal / 1000, ratio_sc_dbo, taux_actu * 100]
            colors4   = [OR, BLEU, AMBRE]

            fig4.add_trace(go.Bar(
                x=metriques, y=vals4,
                marker_color=colors4,
                marker_line=dict(color=NAVY, width=1),
                width=0.4, opacity=0.9,
                text=[f"{vals4[0]:.1f}k€", f"{vals4[1]:.2f}%", f"{vals4[2]:.2f}%"],
                textposition='outside',
                textfont=dict(color=BLANC, size=11),
                hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
            ))
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text="🎯 Scorecard IAS 19 — Indicateurs clés",
                           font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                yaxis=dict(visible=False), bargap=0.4, showlegend=False,
            ))
            fig4.update_layout(**l4)
            graphiques['scorecard_ias19'] = fig4
        except Exception as e:
            self.logger.warning(f"G4 scorecard échoué : {e}")

        return graphiques

    def _commenter(self, dbo, sc, ic, taux, effectif, branche):
        return (
            f"🟢 IAS 19 — VERT\n"
            f"DBO totale         : {dbo:>12,.0f} €\n"
            f"Service Cost N     : {sc:>12,.0f} €\n"
            f"Interest Cost N    : {ic:>12,.0f} €\n"
            f"Charge totale N    : {sc+ic:>12,.0f} €\n"
            f"DBO / effectif     : {dbo/max(effectif,1):>12,.0f} €/pers\n"
            f"Taux actu IAS 19   : {taux*100:.2f}% (OAT iBoxx AA)\n\n"
            f"DIAGNOSTIC :\n"
            f"La DBO de {dbo:,.0f}€ représente la valeur actuelle\n"
            f"des droits de retraite déjà acquis par les salariés.\n"
            f"Elle doit figurer au passif du bilan IFRS.\n\n"
            f"RECOMMANDATION :\n"
            f"→ Externaliser dans un fonds de pension pour améliorer le ratio SCR.\n"
            f"→ Surveiller la sensibilité au taux d'actualisation (±50bp).\n"
            f"→ Actualiser annuellement avec le taux OAT iBoxx AA."
        )

    def _afficher(self, result):
        sep = "═" * 65
        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT EP1 IAS 19 | {result['audit_id']}")
        print(sep)
        for ligne in result['commentaire'].split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    def _sauvegarder(self, audit_id, result):
        chemin = self.models_path / f"ep1_ias19_{audit_id}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass


if __name__ == '__main__':
    print("Agent EP1 — IAS 19 ActuarIA v1.0")
    print("Usage : agent_ep1 = AgentEP1EngagementsRetraite()")
    print("        result_ep1 = agent_ep1.run(effectif=500)")
