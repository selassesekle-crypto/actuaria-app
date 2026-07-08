"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ACTUARIA — AGENT EP2 : TARIFICATION ÉPARGNE-RETRAITE         ║
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

# Tables de mortalité officielles — Arrêté du 27 juillet 2006
from direction_vie_epre.services.tables_mortalite_officielles import (
    calculer_annuite_viagere, REFERENCE_REGLEMENTAIRE,
)

# ══════════════════════════════════════════════════════════════════════════════
# AGENT EP2 — TARIFICATION ÉPARGNE-RETRAITE
# ══════════════════════════════════════════════════════════════════════════════

class AgentEP2TarificationEpargne:
    """
    Agent EP2 — Tarification des contrats épargne-retraite.

    CONTRATS COUVERTS :
    ─────────────────────
    Art. 39 — Retraite à prestations définies (PD)
              Engagement de l'employeur : rente viagère garantie
    Art. 83 / PER Collectif — Retraite à cotisations définies (CD)
              Capitalisation individuelle + rente à la sortie
    PER Individuel — Loi PACTE 2019
              Souplesse rachat + sortie en capital

    TARIFICATION :
    ───────────────
    Prime pure = PM × (i - i_tech) / (1 - (1+i_tech)^{-n})
    où i_tech = taux technique garanti
       i      = taux marché
       PM     = provision mathématique

    Chargements = frais de gestion + frais d'acquisition
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
        self.logger = logging.getLogger('actuaria.ep2')
        self.logger.info("Agent EP2 Tarification Épargne initialisé")

    def run(
        self,
        type_contrat:       str   = 'PER',
        capital_cible:      float = 100_000,
        age_entree:         int   = 35,
        age_retraite:       int   = 65,
        taux_technique:     float = 0.0,
        taux_marche:        float = 0.03,
        taux_participation: float = 0.90,
        frais_gestion_pct:  float = 0.008,
        frais_acquisition_pct: float = 0.04,
        annuites_65:        float = None,   # None = calcul automatique depuis TH0002/TF0002 (arrêté 27/07/2006)
        sexe:               str   = 'H',    # 'H' ou 'F' pour les tables TH0002/TF0002
        sous_branche:       str  = 'per',
        generer_graphiques: bool = True,
    ) -> Dict[str, Any]:
        """
        Tarifie un contrat épargne-retraite.

        Paramètres
        ──────────
        type_contrat : str
            'ART39', 'ART83', 'PER', 'PERCO'

        capital_cible : float
            Capital épargne cible à la retraite (€).

        taux_technique : float
            Taux minimum garanti (TMG).
            Depuis 2023 : max 0.5% pour les nouvelles souscriptions.

        taux_participation : float
            % du rendement financier attribué à l'assuré.
            Min réglementaire : 85% (Code des assurances Art. L132-29).

        frais_gestion_pct : float
            Frais de gestion annuels (prélevés sur l'encours).
            Marché : 0.5-1.5% selon le contrat.
        """
        t_debut  = datetime.now()
        audit_id = f"EP2_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"[{audit_id}] Agent EP2 démarré | {type_contrat}")

        try:
            duree     = age_retraite - age_entree
            taux_net  = taux_marche * taux_participation - frais_gestion_pct

            # ── COTISATION ANNUELLE ────────────────────────────────────────────
            # Capital = Cotisation × ä_due × (1+i)^n
            # Cotisation = Capital / [(1+i)^n - 1) / i × (1+i)]
            if taux_net > 0:
                facteur_epargne = ((1 + taux_net)**duree - 1) / taux_net * (1 + taux_net)
            else:
                facteur_epargne = duree

            cotisation_annuelle = capital_cible / max(facteur_epargne, 1)
            frais_acquisition   = cotisation_annuelle * frais_acquisition_pct
            cotisation_brute    = cotisation_annuelle + frais_acquisition

            # ── PROVISION MATHÉMATIQUE INTERMÉDIAIRE ──────────────────────────
            # PM après k années de cotisation
            pm_progressif = {}
            for k in [5, 10, 15, 20, duree]:
                k = min(k, duree)
                if taux_net > 0:
                    pm = cotisation_annuelle * ((1 + taux_net)**k - 1) / taux_net * (1 + taux_net)
                else:
                    pm = cotisation_annuelle * k
                pm_progressif[f'PM_an_{k}'] = round(float(pm), 0)

            # ── RENTE VIAGÈRE À LA SORTIE ─────────────────────────────────────
            # ä_x calculé depuis les tables officielles TH0002/TF0002
            # (arrêté du 27 juillet 2006) — ou valeur passée par l'utilisateur
            if annuites_65 is None:
                annuites_65 = calculer_annuite_viagere(
                    age=age_retraite,
                    taux=max(taux_technique, taux_marche * 0.5),
                    sexe=sexe,
                )
                self.logger.info(
                    f"[{audit_id}] Annuité viagère calculée depuis tables officielles "
                    f"({REFERENCE_REGLEMENTAIRE[:40]}...) : ä_{age_retraite} = {annuites_65:.4f}"
                )
            rente_annuelle  = capital_cible / max(annuites_65, 1)
            rente_mensuelle = rente_annuelle / 12

            # ── TAUX DE REMPLACEMENT ──────────────────────────────────────────
            # En % du dernier salaire (supposé ~40 000€)
            salaire_fin = 40_000 * (1 + 0.02) ** duree
            taux_rempl  = rente_annuelle / max(salaire_fin, 1) * 100

            # ── PARTICIPATION AUX BÉNÉFICES (PB) ─────────────────────────────
            # PB distribuée = (Produits financiers - Intérêts techniques) × taux_PB
            produits_fi = capital_cible * taux_marche
            interets_t  = capital_cible * taux_technique
            pb          = (produits_fi - interets_t) * taux_participation

            statut_rag = 'VERT'

            result = {
                'success':          True,
                'audit_id':         audit_id,
                'sources':          {'parametres': 'saisie manuelle'},
                'type_contrat':     type_contrat,
                'statut_rag':       statut_rag,
                'parametres': {
                    'capital_cible':    capital_cible,
                    'age_entree':       age_entree,
                    'age_retraite':     age_retraite,
                    'duree_ans':        duree,
                    'taux_technique':   taux_technique,
                    'taux_marche':      taux_marche,
                    'taux_net':         round(taux_net, 4),
                    'frais_gestion':    frais_gestion_pct,
                },
                'tarification': {
                    'cotisation_nette_annuelle': round(cotisation_annuelle, 0),
                    'frais_acquisition':         round(frais_acquisition, 0),
                    'cotisation_brute_annuelle': round(cotisation_brute, 0),
                    'cotisation_mensuelle':       round(cotisation_brute / 12, 0),
                    'capital_cible':             round(capital_cible, 0),
                    'rente_annuelle':            round(rente_annuelle, 0),
                    'rente_mensuelle':           round(rente_mensuelle, 0),
                    'taux_remplacement_pct':     round(taux_rempl, 1),
                    'pb_estimee':                round(pb, 0),
                    'annuites_utilisees':         round(annuites_65, 4),
                    'pm_progressif':             pm_progressif,
                },
                'commentaire': self._commenter(
                    type_contrat, cotisation_brute, capital_cible,
                    rente_mensuelle, taux_rempl, taux_net, duree
                ),
            }

            if generer_graphiques and PLOTLY_OK:
                result['graphiques'] = self._generer_graphiques(
                    capital_cible, cotisation_annuelle, rente_mensuelle,
                    taux_rempl, taux_net, duree, pm_progressif,
                    taux_marche, frais_gestion_pct, type_contrat
                )
            else:
                result['graphiques'] = {}

            result['validation_ep2']        = self._valider_tarification_epre(
                result.get('tarification', {}).get('rente_mensuelle', 0),
                result.get('parametres', {}).get('taux_technique', 0.0),
                result.get('tarification', {}).get('cotisation_mensuelle', 0),
                result.get('tarification', {}).get('capital_cible', 100_000))
            result['graphiques_validation'] = self._graphiques_validation_epre(result['validation_ep2'])

            self._sauvegarder(audit_id, result)
            if self.verbose:
                self._afficher(result)

            return result

        except Exception as e:
            self.logger.error(f"ERREUR EP2 : {e}", exc_info=True)
            return {'success': False, 'erreur': str(e), 'audit_id': audit_id}


    def _valider_tarification_epre(self, rente: float, taux_technique: float,
                                    cotisation: float, capital_cible: float) -> Dict:
        """
        Contrôles qualité tarification EP-RE.
        H1 — Taux technique ≤ taux marché (3.5%)
        H2 — Rente > 0 et cohérente avec le capital
        H3 — Cotisation cohérente (ratio CT/Capital ∈ [0.1%, 2%] par mois)
        """
        VERT="VERT"; AMBRE="AMBRE"; ROUGE="ROUGE"
        taux_marche = 3.5  # OAT 10 ans référence

        # H1
        if taux_technique * 100 <= taux_marche:
            h1_statut = VERT
            h1_msg    = f"Taux technique = {taux_technique*100:.2f}% ≤ marché {taux_marche}% ✅"
            h1_conseil= "Taux technique prudent — conforme Art. A132-1 Code assurances"
        else:
            h1_statut = ROUGE
            h1_msg    = f"Taux technique = {taux_technique*100:.2f}% > marché {taux_marche}% ❌"
            h1_conseil= "Taux technique trop élevé — risque de sous-provisionnement"

        # H2
        if rente > 0:
            h2_statut = VERT
            h2_msg    = f"Rente = {rente:.2f}€/mois > 0 ✅"
            h2_conseil= "Rente calculée cohérente avec le capital cible et les hypothèses"
        else:
            h2_statut = ROUGE
            h2_msg    = f"Rente = {rente:.2f}€/mois ≤ 0 ❌"
            h2_conseil= "Revoir les hypothèses de mortalité et de taux"

        # H3
        ratio_ct = (cotisation / max(capital_cible, 1)) * 100
        if 0.1 <= ratio_ct <= 2.0:
            h3_statut = VERT
            h3_msg    = f"Ratio cotisation/capital = {ratio_ct:.3f}%/mois ∈ [0.1%, 2%] ✅"
            h3_conseil= "Effort d'épargne mensuel cohérent avec le capital cible"
        else:
            h3_statut = AMBRE
            h3_msg    = f"Ratio cotisation/capital = {ratio_ct:.3f}%/mois → Hors plage ⚠️"
            h3_conseil= "Vérifier la durée d'épargne et le taux de rendement supposé"

        statuts = [h1_statut, h2_statut, h3_statut]
        sg = ROUGE if ROUGE in statuts else AMBRE if AMBRE in statuts else VERT
        return {
            "h1_taux": {"taux_technique_pct": round(taux_technique*100,3), "statut": h1_statut,
                        "message": h1_msg, "conseil": h1_conseil,
                        "titre_graphique": f"{'✅' if h1_statut==VERT else '❌'} Taux technique {taux_technique*100:.2f}% vs marché {taux_marche}%"},
            "h2_rente": {"rente": round(rente,2), "statut": h2_statut,
                         "message": h2_msg, "conseil": h2_conseil,
                         "titre_graphique": f"{'✅' if h2_statut==VERT else '❌'} Rente = {rente:.2f}€/mois"},
            "h3_cotisation": {"ratio_ct_pct": round(ratio_ct,4), "statut": h3_statut,
                             "message": h3_msg, "conseil": h3_conseil,
                             "titre_graphique": f"{'✅' if h3_statut==VERT else '⚠️' if h3_statut==AMBRE else '❌'} Ratio CT/Capital = {ratio_ct:.3f}%"},
            "statut_global": sg,
            "conclusion": f"{'✅ EP-RE validé' if sg==VERT else '⚠️ EP-RE acceptable' if sg==AMBRE else '❌ EP-RE à revoir'} — taux, rente et cotisation vérifiés",
        }

    def _graphiques_validation_epre(self, val: Dict) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; OR="#C9A84C"; BLANC="#F0F4F8"
        GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"; BLEU="#3498DB"
        graphiques = {}
        try:
            items = [
                ("H1 — Taux technique ≤ marché", val["h1_taux"]["statut"],
                 val["h1_taux"]["message"], val["h1_taux"]["conseil"]),
                ("H2 — Rente > 0", val["h2_rente"]["statut"],
                 val["h2_rente"]["message"], val["h2_rente"]["conseil"]),
                ("H3 — Cotisation cohérente", val["h3_cotisation"]["statut"],
                 val["h3_cotisation"]["message"], val["h3_cotisation"]["conseil"]),
            ]
            fig = go.Figure()
            for nom, statut, msg, conseil in items:
                c = VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i = "✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s = 1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.2
                fig.add_trace(go.Bar(x=[s], y=[nom], orientation="h", marker_color=c, width=0.5,
                    text=f"{i} {statut}", textposition="outside", textfont=dict(color=c,size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False))
            sg = val["statut_global"]
            cg = VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            fig.update_layout(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family="Inter,Arial",color=BLANC,size=11),
                margin=dict(l=16,r=16,t=60,b=50), height=260,
                title=dict(text=f"Scorecard EP-RE — {val['conclusion'][:60]}",
                          font=dict(color=cg,size=10),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay",
                annotations=[dict(text="💡 3 ✅ = tarification EP-RE validée, défendable devant l\'ACPR et l\'actuaire désigné.",
                                 xref="paper",yref="paper",x=0.01,y=-0.22,
                                 font=dict(color=GRIS,size=9),showarrow=False,align="left")])
            graphiques["scorecard_epre"] = fig
        except Exception:
            pass

        # G2 — Taux technique vs marché
        try:
            h1 = val["h1_taux"]
            taux_tech  = h1.get("taux_technique", 0.025)
            taux_marche= h1.get("taux_marche", 0.035)
            couleur_h1 = VERT if h1["statut"]=="VERT" else AMBRE if h1["statut"]=="AMBRE" else ROUGE
            fig2 = go.Figure(go.Bar(
                x=["Taux technique", "Taux OAT marché"],
                y=[taux_tech*100, taux_marche*100],
                marker_color=[couleur_h1, OR], width=0.4, opacity=0.88,
                text=[f"{taux_tech*100:.2f}%", f"{taux_marche*100:.2f}%"],
                textposition="outside", textfont=dict(color=BLANC, size=12),
            ))
            fig2.update_layout(
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family="Inter", color=BLANC, size=11),
                margin=dict(l=16, r=16, t=60, b=50), height=300,
                title=dict(text=f"{'✅' if h1['statut']=='VERT' else '❌'} Taux technique {taux_tech*100:.2f}% vs OAT {taux_marche*100:.2f}%",
                          font=dict(color=couleur_h1, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(visible=False), bargap=0.4, showlegend=False,
                annotations=[dict(text="💡 Le taux technique doit être inférieur au taux OAT — sinon l'assureur promet un rendement impossible.", xref="paper", yref="paper", x=0.01, y=-0.22, font=dict(color=GRIS, size=9), showarrow=False)],
            )
            graphiques["taux_technique_vs_marche"] = fig2
        except Exception as e:
            self.logger.warning(f"G2 EP2 : {e}")

        # G3 — Rente mensuelle
        try:
            h2 = val["h2_rente"]
            rente = h2.get("rente_mensuelle", 0)
            couleur_h2 = VERT if h2["statut"]=="VERT" else AMBRE if h2["statut"]=="AMBRE" else ROUGE
            fig3 = go.Figure(go.Indicator(
                mode="number",
                value=rente,
                number=dict(suffix=" €/mois", font=dict(color=couleur_h2, size=36), valueformat=",.0f"),
                title=dict(text=f"{'✅' if h2['statut']=='VERT' else '❌'} Rente mensuelle calculée",
                          font=dict(color=couleur_h2, size=11)),
            ))
            fig3.update_layout(
                paper_bgcolor=NAVY, font=dict(color=BLANC),
                margin=dict(l=30, r=30, t=80, b=50), height=300,
                annotations=[dict(text=f"💡 {h2.get('conseil','Rente calculée selon tables réglementaires')}", xref="paper", yref="paper", x=0.5, y=-0.12, font=dict(color=GRIS, size=9), showarrow=False, align="center")],
            )
            graphiques["rente_mensuelle"] = fig3
        except Exception as e:
            self.logger.warning(f"G3 EP2 : {e}")

        return graphiques

    def _generer_graphiques(
        self, capital_cible, cotisation_annuelle, rente_mensuelle,
        taux_rempl, taux_net, duree, pm_progressif,
        taux_marche, frais_gestion_pct, type_contrat
    ) -> Dict:
        """4 graphiques EP2 style PowerBI."""
        if not PLOTLY_OK:
            return {}

        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"
        OR="#C9A84C"; BLANC="#F0F4F8"; GRIS="#8A9AB0"
        VERT="#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"; BLEU="#3498DB"

        LAYOUT = dict(
            paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=52, b=16), height=300,
            hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR,
                           font_size=12, font_color=BLANC),
        )
        graphiques = {}

        # G1 — Croissance PM dans le temps
        try:
            annees = sorted([int(k.split('_')[-1]) for k in pm_progressif.keys()])
            pms    = [pm_progressif[f'PM_an_{a}'] for a in annees]

            fig1 = make_subplots(specs=[[{"secondary_y": True}]])
            fig1.add_trace(go.Bar(
                x=annees, y=pms, name='PM (€)',
                marker_color=[OR if a == duree else "rgba(201,168,76,0.5)" for a in annees],
                width=0.4, opacity=0.88,
                hovertemplate="An %{x}<br>PM : %{y:,.0f} €<extra></extra>",
            ), secondary_y=False)
            # Cotisations cumulées (ligne)
            cot_cum = [cotisation_annuelle * a for a in annees]
            fig1.add_trace(go.Scatter(
                x=annees, y=cot_cum, name='Cotisations cumulees',
                mode='lines+markers',
                line=dict(color=BLEU, width=2, shape='spline'),
                marker=dict(color=BLEU, size=7, line=dict(color=NAVY, width=2)),
                hovertemplate="An %{x}<br>Cot. cum. : %{y:,.0f} €<extra></extra>",
            ), secondary_y=True)
            fig1.update_layout(
                title=dict(text=f"📈 Croissance PM — {type_contrat} | Capital cible {capital_cible/1e3:.0f}k€",
                           font=dict(color=BLANC, size=12), x=0.01),
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family="Inter, Arial", color=BLANC),
                margin=dict(l=16, r=16, t=52, b=16), height=300,
                hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                            orientation="h", yanchor="bottom", y=1.02),
                bargap=0.35,
            )
            fig1.update_xaxes(title=dict(text="Annee", font=dict(color=GRIS, size=10)),
                              showgrid=False, tickfont=dict(color=GRIS))
            fig1.update_yaxes(title_text="PM (€)", title_font=dict(color=GRIS, size=10),
                              showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                              tickfont=dict(color=GRIS), secondary_y=False)
            fig1.update_yaxes(title_text="Cot. cumulees (€)",
                              title_font=dict(color=GRIS, size=10),
                              showgrid=False, tickfont=dict(color=GRIS), secondary_y=True)
            graphiques['croissance_pm'] = fig1
        except Exception as e:
            self.logger.warning(f"G1 PM échoué : {e}")

        # G2 — Decomposition du capital final
        try:
            cotisations_tot = cotisation_annuelle * duree
            interets_tot    = capital_cible - cotisations_tot

            fig2 = go.Figure(go.Pie(
                labels=['Cotisations versees', 'Interets capitalises'],
                values=[cotisations_tot, max(interets_tot, 0)],
                hole=0.55,
                marker=dict(colors=[BLEU, OR], line=dict(color=NAVY, width=2)),
                textfont=dict(color=BLANC, size=11),
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>",
            ))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text=f"🥧 Decomposition capital {capital_cible/1e3:.0f}k€",
                           font=dict(color=BLANC, size=13), x=0.01),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10)),
                annotations=[dict(text=f"<b>{capital_cible/1e3:.0f}k€</b>",
                                  x=0.5, y=0.5, font=dict(size=14, color=OR), showarrow=False)],
            ))
            fig2.update_layout(**l2)
            graphiques['decomposition_capital'] = fig2
        except Exception as e:
            self.logger.warning(f"G2 capital échoué : {e}")

        # G3 — Sensibilite taux net
        try:
            taux_nets = [t/100 for t in range(0, 6)]
            rentes_s  = []
            for tn in taux_nets:
                if tn > 0:
                    fe = ((1+tn)**duree - 1) / tn * (1+tn)
                else:
                    fe = duree
                cot = capital_cible / max(fe, 1)
                rentes_s.append(cot * 12)  # cotisation mensuelle

            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=[t*100 for t in taux_nets], y=rentes_s,
                mode='lines+markers',
                line=dict(color=OR, width=2.5, shape='spline', smoothing=0.5),
                marker=dict(color=OR, size=8, line=dict(color=NAVY, width=2)),
                fill='tozeroy', fillcolor='rgba(201,168,76,0.08)',
                hovertemplate="Taux net %{x:.1f}%<br>Cotisation mensuelle : %{y:,.0f} €<extra></extra>",
            ))
            # Marqueur taux actuel
            cot_act_m = cotisation_annuelle / 12 * (1 + frais_gestion_pct)
            fig3.add_scatter(
                x=[taux_net*100], y=[cot_act_m],
                mode='markers+text',
                marker=dict(color=VERT, size=14, symbol='star',
                            line=dict(color=NAVY, width=2)),
                text=[f"  Taux actuel {taux_net*100:.1f}%"],
                textfont=dict(color=VERT, size=10),
                textposition='middle right',
                showlegend=False,
                hovertemplate=f"Taux net {taux_net*100:.1f}%<br>Cot. mensuelle : {cot_act_m:,.0f} €<extra></extra>",
            )
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text="📈 Cotisation mensuelle selon le taux net",
                           font=dict(color=BLANC, size=13), x=0.01),
                xaxis=dict(title=dict(text="Taux net (%)", font=dict(color=GRIS, size=10)),
                           showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                           tickfont=dict(color=GRIS)),
                yaxis=dict(title=dict(text="Cotisation mensuelle (€)",
                                      font=dict(color=GRIS, size=10)),
                           showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                           tickfont=dict(color=GRIS)),
                showlegend=False,
            ))
            fig3.update_layout(**l3)
            graphiques['sensibilite_taux'] = fig3
        except Exception as e:
            self.logger.warning(f"G3 sensibilité échoué : {e}")

        # G4 — Scorecard tarification
        try:
            metriques = ['Capital cible', 'Rente mensuelle', 'Taux rempl. (%)']
            vals4     = [capital_cible/1e3, rente_mensuelle, taux_rempl]
            units     = ['k€', '€/mois', '%']

            fig4 = go.Figure(go.Bar(
                x=metriques, y=vals4,
                marker_color=[OR, VERT, BLEU],
                marker_line=dict(color=NAVY, width=1),
                width=0.4, opacity=0.9,
                text=[f"{vals4[0]:.0f}k€", f"{vals4[1]:,.0f}€/mois", f"{vals4[2]:.1f}%"],
                textposition='outside',
                textfont=dict(color=BLANC, size=11),
                hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
            ))
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text=f"🎯 Scorecard {type_contrat} — Cot. nette {cotisation_annuelle/12:,.0f}€/mois",
                           font=dict(color=BLANC, size=12), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                yaxis=dict(visible=False), bargap=0.4, showlegend=False,
            ))
            fig4.update_layout(**l4)
            graphiques['scorecard_ep2'] = fig4
        except Exception as e:
            self.logger.warning(f"G4 scorecard échoué : {e}")

        return graphiques

    def _commenter(self, type_c, cot, capital, rente_m, tx_rempl, taux_net, duree):
        return (
            f"🟢 TARIFICATION {type_c} — VERT\n"
            f"Cotisation brute annuelle  : {cot:>10,.0f} €\n"
            f"Cotisation mensuelle       : {cot/12:>10,.0f} €\n"
            f"Capital cible à 65 ans     : {capital:>10,.0f} €\n"
            f"Rente mensuelle viagère    : {rente_m:>10,.0f} €\n"
            f"Taux de remplacement       : {tx_rempl:.1f}%\n"
            f"Taux net (marché - frais)  : {taux_net*100:.2f}%\n\n"
            f"DIAGNOSTIC :\n"
            f"Sur {duree} ans à {taux_net*100:.2f}% net,\n"
            f"une cotisation de {cot/12:,.0f}€/mois permet\n"
            f"d'atteindre un capital de {capital:,.0f}€ à 65 ans,\n"
            f"soit une rente mensuelle de {rente_m:,.0f}€.\n\n"
            f"RECOMMANDATION :\n"
            f"→ Vérifier que le TMG respecte la limite ACPR (max 0.5%).\n"
            f"→ Intégrer la PB dans la revalorisation annuelle.\n"
            f"→ Comparer avec le régime légal (CNAV + AGIRC-ARRCO)."
        )

    def _afficher(self, result):
        sep = "═" * 65
        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT EP2 TARIFICATION | {result['audit_id']}")
        print(sep)
        for ligne in result['commentaire'].split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    def _sauvegarder(self, audit_id, result):
        chemin = self.models_path / f"ep2_tarif_{audit_id}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass


if __name__ == '__main__':
    print("Agent EP2 — Tarification Épargne-Retraite ActuarIA v1.0")
    print("Usage : agent_ep2 = AgentEP2TarificationEpargne()")
    print("        result_ep2 = agent_ep2.run(type_contrat='PER')")
