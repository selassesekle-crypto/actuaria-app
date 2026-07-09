"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ACTUARIA — AGENT EP5 : REPORTING ÉPARGNE-RETRAITE            ║
║                        Version 1.0 — Production                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, json, logging, warnings
from direction_vie_epre.services.rapport_epre import (
    export_html as _rapport_html_epre,
    export_pdf  as _rapport_pdf_epre,
    export_word as _rapport_word_epre,
)
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
        # Métadonnées rapport consolidé
        ref_client:         str  = '',
        arrete:             str  = '',
        actuaire_nom:       str  = '',
        actuaire_numero_ia: str  = '',
        # Agents complémentaires EP-RE
        result_ep6: dict = None,
        result_ep7: dict = None,
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
            # ── Validation formelle du rapport (scorecard EP5) ────────
            result['validation_ep5']        = self._valider_reporting(
                kpis, rapports_disponibles, statut_rag, actuaire_resp
            )
            result['graphiques_validation'] = self._graphiques_validation_ep5(
                result['validation_ep5']
            ) if generer_graphiques and PLOTLY_OK else {}

            self._sauvegarder(audit_id, result)
            if self.verbose:
                self._afficher(result)

            # ── Rapports consolidés niveau A7 ──────────────────────────
            _kw = dict(
                result_ep1=result_ep1, result_ep2=result_ep2,
                result_ep3=result_ep3, result_ep4=result_ep4,
                result_ep6=result_ep6, result_ep7=result_ep7,
                commentaire=result.get('commentaire',''),
                ref_client=ref_client or client_nom,
                arrete=arrete or date_arr,
                audit_id=audit_id,
                graphiques=result.get('graphiques') if generer_graphiques else None,
                actuaire_nom=actuaire_nom or actuaire_resp,
                actuaire_numero_ia=actuaire_numero_ia,
            )
            html_bytes = pdf_bytes = word_bytes = None
            try:
                _h = _rapport_html_epre(**_kw)
                html_bytes = _h.encode('utf-8') if _h else None
            except Exception as _e:
                self.logger.warning(f'[{audit_id}] HTML EP5 : {_e}')
            try:
                pdf_bytes = _rapport_pdf_epre(**_kw)
            except Exception as _e:
                self.logger.warning(f'[{audit_id}] PDF EP5 : {_e}')
            try:
                _kw_w = {k: v for k, v in _kw.items() if k != 'graphiques'}
                word_bytes = _rapport_word_epre(**_kw_w)
            except Exception as _e:
                self.logger.warning(f'[{audit_id}] Word EP5 : {_e}')

            result['html_bytes']  = html_bytes
            result['pdf_bytes']   = pdf_bytes
            result['word_bytes']  = word_bytes

            return result

        except Exception as e:
            self.logger.error(f"ERREUR EP5 : {e}", exc_info=True)
            return {'success': False, 'erreur': str(e), 'audit_id': audit_id}

    # ─── VALIDATION FORMELLE DU RAPPORT ──────────────────────────────────
    def _valider_reporting(
        self,
        kpis:               Dict,
        rapports:           List[Dict],
        statut_rag:         str,
        actuaire_resp:      str,
    ) -> Dict:
        """
        Scorecard de validation du rapport EP5.

        C1 — Complétude des KPIs
             Les 4 KPIs essentiels sont présents : DBO_IAS19, pm_totale,
             cotisation_annuelle, ratio_base. Un rapport signé sans ces
             données est inacceptable devant l'ACPR et le CA.

        C2 — Couverture réglementaire
             Les 4 rapports réglementaires requis sont présents avec
             leur référence juridique. Un rapport sans référence = rouge.

        C3 — Traçabilité actuaire responsable
             Le champ actuaire_resp est renseigné et non générique.
             Un rapport signé 'Actuaire FIAF' sans nom nominatif
             n'est pas défendable devant le Comité d'Audit.
        """
        # C1 — Complétude des KPIs essentiels
        KPI_ESSENTIELS = ['DBO_IAS19', 'pm_totale', 'cotisation_annuelle', 'ratio_base']
        kpis_presents  = [k for k in KPI_ESSENTIELS if k in kpis]
        nb_kpis        = len(kpis_presents)
        if nb_kpis == len(KPI_ESSENTIELS):
            c1_s = 'VERT'
            c1_m = f"4/4 KPIs essentiels présents ✅"
            c1_c = "Rapport complet — tous les indicateurs clés sont disponibles"
        elif nb_kpis >= 2:
            manquants = [k for k in KPI_ESSENTIELS if k not in kpis]
            c1_s = 'AMBRE'
            c1_m = f"{nb_kpis}/{len(KPI_ESSENTIELS)} KPIs présents — manquants : {', '.join(manquants)} ⚠️"
            c1_c = "Alimenter les agents manquants (EP1/EP2/EP3/EP4) avant signature"
        else:
            c1_s = 'ROUGE'
            c1_m = f"{nb_kpis}/{len(KPI_ESSENTIELS)} KPIs présents ❌ — rapport insuffisant"
            c1_c = "Rapport non signable — exécuter la chaîne EP1→EP4 complète"

        # C2 — Couverture réglementaire (tous les rapports ont une référence juridique)
        nb_rapports       = len(rapports)
        rapports_ref      = [r for r in rapports if r.get('reference', '').strip()]
        nb_avec_ref       = len(rapports_ref)
        if nb_rapports >= 4 and nb_avec_ref == nb_rapports:
            c2_s = 'VERT'
            c2_m = f"{nb_rapports} rapports réglementaires — 100% avec référence juridique ✅"
            c2_c = "Couverture réglementaire complète — défendable devant l'ACPR"
        elif nb_avec_ref >= nb_rapports * 0.75:
            sans_ref = [r['nom'] for r in rapports if not r.get('reference', '').strip()]
            c2_s = 'AMBRE'
            c2_m = f"{nb_avec_ref}/{nb_rapports} rapports avec référence juridique ⚠️"
            c2_c = f"Ajouter la référence réglementaire sur : {', '.join(sans_ref[:2])}"
        else:
            c2_s = 'ROUGE'
            c2_m = f"{nb_avec_ref}/{nb_rapports} rapports avec référence juridique ❌"
            c2_c = "Rapport non conforme — chaque rapport doit citer sa base légale"

        # C3 — Traçabilité actuaire responsable
        # Un nom nominatif est requis (pas de valeur générique par défaut)
        VALEURS_GENERIQUES = {'Actuaire FIAF', 'Actuaire', 'N/A', '', 'TBD'}
        if actuaire_resp and actuaire_resp.strip() not in VALEURS_GENERIQUES:
            c3_s = 'VERT'
            c3_m = f"Actuaire responsable identifié : {actuaire_resp} ✅"
            c3_c = "Traçabilité nominative conforme aux exigences du Comité d'Audit"
        elif actuaire_resp and actuaire_resp.strip():
            c3_s = 'AMBRE'
            c3_m = f"Actuaire responsable générique : '{actuaire_resp}' ⚠️"
            c3_c = "Remplacer par le nom nominatif de l'actuaire signataire avant dépôt"
        else:
            c3_s = 'ROUGE'
            c3_m = "Actuaire responsable non renseigné ❌"
            c3_c = "Rapport non signable — renseigner actuaire_resp avec le nom nominatif"

        sts = [c1_s, c2_s, c3_s]
        sg  = 'ROUGE' if 'ROUGE' in sts else 'AMBRE' if 'AMBRE' in sts else 'VERT'
        return {
            'c1_kpis': {
                'nb_presents':   nb_kpis,
                'nb_requis':     len(KPI_ESSENTIELS),
                'kpis_presents': kpis_presents,
                'statut':        c1_s, 'message': c1_m, 'conseil': c1_c,
                'titre_graphique': f"{'✅' if c1_s=='VERT' else '⚠️' if c1_s=='AMBRE' else '❌'} KPIs — {nb_kpis}/{len(KPI_ESSENTIELS)} essentiels présents",
            },
            'c2_reglementaire': {
                'nb_rapports':    nb_rapports,
                'nb_avec_ref':    nb_avec_ref,
                'statut':         c2_s, 'message': c2_m, 'conseil': c2_c,
                'titre_graphique': f"{'✅' if c2_s=='VERT' else '⚠️' if c2_s=='AMBRE' else '❌'} Réglementation — {nb_avec_ref}/{nb_rapports} rapports référencés",
            },
            'c3_tracabilite': {
                'actuaire':  actuaire_resp,
                'statut':    c3_s, 'message': c3_m, 'conseil': c3_c,
                'titre_graphique': f"{'✅' if c3_s=='VERT' else '⚠️' if c3_s=='AMBRE' else '❌'} Traçabilité actuaire — {actuaire_resp or 'Non renseigné'}",
            },
            'statut_global': sg,
            'conclusion': {
                'VERT':  '✅ Rapport EP5 validé — KPIs complets, couverture réglementaire et traçabilité conformes',
                'AMBRE': '⚠️ Rapport EP5 acceptable — compléter les points signalés avant signature',
                'ROUGE': '❌ Rapport EP5 non signable — insuffisances bloquantes à corriger',
            }[sg],
        }

    def _graphiques_validation_ep5(self, val: Dict) -> Dict:
        """Scorecard graphique de validation du rapport EP5."""
        if not PLOTLY_OK:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; BLANC='#F0F4F8'; GRIS='#8A9AB0'
        VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'
        graphiques = {}
        try:
            items = [
                ('C1 — Complétude KPIs essentiels',    val['c1_kpis']['statut'],
                 val['c1_kpis']['message'],            val['c1_kpis']['conseil']),
                ('C2 — Couverture réglementaire',      val['c2_reglementaire']['statut'],
                 val['c2_reglementaire']['message'],   val['c2_reglementaire']['conseil']),
                ('C3 — Traçabilité actuaire nominatif',val['c3_tracabilite']['statut'],
                 val['c3_tracabilite']['message'],     val['c3_tracabilite']['conseil']),
            ]
            fig = go.Figure()
            for nom, statut, msg, conseil in items:
                c = VERT if statut == 'VERT' else AMBRE if statut == 'AMBRE' else ROUGE
                i = '✅' if statut == 'VERT' else '⚠️' if statut == 'AMBRE' else '❌'
                s = 1.0 if statut == 'VERT' else 0.5 if statut == 'AMBRE' else 0.0
                fig.add_trace(go.Bar(
                    x=[s], y=[nom], orientation='h', marker_color=c, width=0.5,
                    text=f"{i} {statut}", textposition='outside',
                    textfont=dict(color=c, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False,
                ))
            sg = val['statut_global']
            cg = VERT if sg == 'VERT' else AMBRE if sg == 'AMBRE' else ROUGE
            fig.update_layout(
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family='Inter', color=BLANC, size=11),
                margin=dict(l=16, r=16, t=60, b=50), height=260,
                title=dict(
                    text=f"Scorecard Rapport EP5 — {val['conclusion']}",
                    font=dict(color=cg, size=10), x=0.01
                ),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode='overlay',
                annotations=[dict(
                    text="💡 3 ✅ = rapport EP5 validé, signable et transmissible à l'ACPR et au CA.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False,
                )],
            )
            graphiques['scorecard_ep5'] = fig
        except Exception as e:
            self.logger.warning(f"Scorecard EP5 : {e}")
        return graphiques

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
