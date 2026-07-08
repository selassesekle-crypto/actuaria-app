"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ACTUARIA — AGENT EP5 : REPORTING ÉPARGNE-RETRAITE            ║
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
# AGENT EP5 — REPORTING ÉPARGNE-RETRAITE
# ══════════════════════════════════════════════════════════════════════════════

class AgentEP5ReportingEpargne:
    """
    Agent EP5 — Reporting réglementaire épargne-retraite.

    RAPPORTS PRODUITS :
    ─────────────────────
    • Rapport actuariel Art. 39/83/PER (annuel)
    • Rapport ACPR (annexes QRT spécifiques retraite)
    • Enquête DARES (statistiques emploi-retraite)
    • Note de synthèse pour le Conseil d'Administration
    • Fiche d'information assuré (IPID-like pour retraite)
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
        self.logger = logging.getLogger('actuaria.ep5')
        self.logger.info("Agent EP5 Reporting Épargne initialisé")

    def run(
        self,
        result_ep1:    Optional[Dict] = None,
        result_ep2:    Optional[Dict] = None,
        result_ep3:    Optional[Dict] = None,
        result_ep4:    Optional[Dict] = None,
        client_nom:         str  = 'Client',
        actuaire_resp:      str  = 'Actuaire FIAF',
        generer_graphiques: bool = True,
        date_arrete:   str   = None,
        sous_branche:  str   = 'per',
    ) -> Dict[str, Any]:
        """
        Génère le rapport de synthèse épargne-retraite.
        """
        t_debut  = datetime.now()
        audit_id = f"EP5_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        date_arr = date_arrete or t_debut.strftime('%Y-%m-%d')
        self.logger.info(f"[{audit_id}] Agent EP5 Reporting démarré")

        try:
            # Collecte des KPIs
            kpis = {}
            if result_ep1 and result_ep1.get('success'):
                kpis['DBO_IAS19']     = result_ep1['ias19']['dbo_total']
                kpis['service_cost']  = result_ep1['ias19']['service_cost']
                kpis['interest_cost'] = result_ep1['ias19']['interest_cost']

            if result_ep2 and result_ep2.get('success'):
                kpis['cotisation_annuelle'] = result_ep2['tarification']['cotisation_brute_annuelle']
                kpis['rente_mensuelle']     = result_ep2['tarification']['rente_mensuelle']
                kpis['taux_remplacement']   = result_ep2['tarification']['taux_remplacement_pct']

            if result_ep3 and result_ep3.get('success'):
                kpis['pm_totale']     = result_ep3['provisions']['pm_encours']
                kpis['ppb']           = result_ep3['provisions']['ppb_total']
                kpis['reserve_capi']  = result_ep3['provisions']['reserve_capi']

            if result_ep4 and result_ep4.get('success'):
                kpis['ratio_base']    = result_ep4['ratio_base']
                kpis['nb_scenarios_rouge'] = sum(
                    1 for s in result_ep4['scenarios']
                    if s['rag'] == '🔴 ROUGE'
                )

            # Rapports disponibles
            rapports_disponibles = [
                {
                    'nom':         'Rapport actuariel annuel',
                    'destinataire':'Conseil d\'Administration',
                    'contenu':     ['DBO IAS 19', 'Hypothèses actuarielles', 'Sensibilités'],
                    'reference':   'IAS 19 + Art. R142-4 Code des assurances',
                },
                {
                    'nom':         'QRT retraite ACPR',
                    'destinataire':'ACPR',
                    'contenu':     ['Provisions techniques', 'SCR retraite', 'Actifs couvrants'],
                    'reference':   'EIOPA QRT S.12 + S.26',
                },
                {
                    'nom':         'Fiche information assuré',
                    'destinataire':'Assurés',
                    'contenu':     ['Droits acquis', 'Rente prévisionnelle', 'Frais'],
                    'reference':   'Loi PACTE 2019 + Décret 2019-807',
                },
                {
                    'nom':         'Enquête DARES',
                    'destinataire':'Ministère du Travail',
                    'contenu':     ['Effectifs couverts', 'Cotisations', 'Prestations servies'],
                    'reference':   'Enquête DARES annuelle',
                },
            ]

            # Statut global
            statuts = []
            for r in [result_ep1, result_ep2, result_ep3, result_ep4]:
                if r and r.get('success'):
                    statuts.append(r.get('statut_rag', 'VERT'))

            statut_rag = (
                'ROUGE' if 'ROUGE' in statuts else
                'AMBRE' if 'AMBRE' in statuts else
                'VERT'
            )

            result = {
                'success':            True,
                'audit_id':           audit_id,
                'client_nom':         client_nom,
                'sous_branche':       sous_branche,
                'statut_rag':         statut_rag,
                'date_arrete':        date_arr,
                'actuaire_resp':      actuaire_resp,
                'kpis_cles':          kpis,
                'rapports_disponibles': rapports_disponibles,
                'commentaire': self._commenter(
                    kpis, rapports_disponibles, client_nom,
                    date_arr, actuaire_resp, statut_rag
                ),
            }

            if generer_graphiques and PLOTLY_OK:
                result['graphiques'] = self._generer_graphiques_ep5(
                    result.get('rapports_disponibles', [])
                )
            else:
                result['graphiques'] = {}
            self._sauvegarder(audit_id, result)
            if self.verbose:
                self._afficher(result)

            return result

        except Exception as e:
            self.logger.error(f"ERREUR EP5 : {e}", exc_info=True)
            return {'success': False, 'erreur': str(e), 'audit_id': audit_id}

    def _generer_graphiques_ep5(self, rapports) -> Dict:
        if not PLOTLY_OK: return {}
        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"
        OR="#C9A84C"; BLANC="#F0F4F8"; GRIS="#8A9AB0"
        VERT="#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"
        LAYOUT = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=52, b=16), height=300,
            hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))
        graphiques = {}
        try:
            if isinstance(rapports, list) and rapports:
                noms_r   = [r.get('nom', f'R{i}') for i, r in enumerate(rapports)]
                destin_r = [r.get('destinataire', '') for r in rapports]
                ref_r    = [r.get('reference', '') for r in rapports]
                # Couleur basée sur la présence d'une référence réglementaire
                colors_r = [VERT if r.get('reference') else AMBRE for r in rapports]

                fig1 = go.Figure(go.Bar(
                    x=[1]*len(noms_r), y=noms_r, orientation='h',
                    marker_color=colors_r, width=0.6,
                    text=destin_r, textposition='outside',
                    textfont=dict(color=BLANC, size=10),
                    hovertemplate="<b>%{y}</b><br>Destinataire : %{text}<extra></extra>",
                ))
                l1 = dict(**LAYOUT)
                l1.update(dict(
                    title=dict(text="Statut des rapports reglementaires",
                        font=dict(color=BLANC, size=13), x=0.01),
                    xaxis=dict(range=[0,1.4], tickvals=[0,0.5,1],
                        ticktext=['ROUGE','AMBRE','VERT'],
                        tickfont=dict(color=GRIS), showgrid=False),
                    yaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                    showlegend=False,
                    height=max(280, len(noms_r)*45+80),
                ))
                fig1.update_layout(**l1)
                graphiques['statut_rapports'] = fig1
        except Exception as e:
            pass
        return graphiques

    def _commenter(self, kpis, rapports, client, date_arr, actuaire, statut):
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut]
        lines = [
            f"{emoji} REPORTING ÉPARGNE-RETRAITE — {statut}",
            f"Client    : {client}",
            f"Date      : {date_arr}",
            f"Actuaire  : {actuaire}",
            "",
            "KPIs CLÉS :",
        ]
        for k, v in kpis.items():
            if isinstance(v, float):
                lines.append(f"  {k:<30} : {v:,.0f}")
            else:
                lines.append(f"  {k:<30} : {v}")

        lines += ["", "RAPPORTS DISPONIBLES :"]
        for r in rapports:
            lines.append(f"  ✅ {r['nom']:<35} → {r['destinataire']}")

        lines += [
            "",
            "RECOMMANDATION :",
            "→ Valider les KPIs avec l'actuaire responsable avant signature.",
            "→ Transmettre le QRT ACPR avant la date limite réglementaire.",
            "→ Archiver avec le hash de session (Agent A13).",
        ]
        return '\n'.join(lines)

    def _afficher(self, result):
        sep = "═" * 65
        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT EP5 REPORTING | {result['audit_id']}")
        print(sep)
        for ligne in result['commentaire'].split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    def _sauvegarder(self, audit_id, result):
        chemin = self.models_path / f"ep5_reporting_{audit_id}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass


if __name__ == '__main__':
    print("Agent EP5 — Reporting Épargne-Retraite ActuarIA v1.0")
    print("Usage : agent_ep5 = AgentEP5ReportingEpargne()")
    print("        result_ep5 = agent_ep5.run(client_nom='Client XYZ')")
