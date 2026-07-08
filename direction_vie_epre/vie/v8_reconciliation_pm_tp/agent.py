"""
ActuarIA — Agent V8 : Marcus — Réconciliation PM/TP S2/IFRS 17
Direction Vie & EP-RE | Manager : Sven | Directeur : Paul

Tableau de réconciliation tricolonne automatique :
→ PM comptables (référentiel social français)
→ TP Solvabilité 2 (Best Estimate + Risk Adjustment)
→ CSM/LC/RA IFRS 17 (Contractual Service Margin + Loss Component)
→ Analyse des écarts et réconciliation ligne à ligne
→ Validation hypothèses + graphiques auto-explicatifs
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.v8 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent V8 — Réconciliation PM/TP S2/IFRS 17 ActuarIA v1.0")
print("Tricolonne : PM sociale · TP Solvabilité 2 · IFRS 17 (CSM/LC/RA)")
print("Usage : agent_v8 = AgentV8ReconciliationPMTP()")
print("        result_v8 = agent_v8.run(pm_sociale=50e6, be_vie=45e6)")


class AgentV8ReconciliationPMTP:
    """
    Agent V8 — Marcus : Réconciliation PM/TP S2/IFRS 17.

    CONTEXTE :
    ──────────
    Les équipes actuarielles des assureurs vie doivent aujourd'hui
    maintenir trois référentiels simultanément :

    1. PM SOCIALE (comptabilité française, PCG)
       Calculée selon le taux technique contractuel (TMG)
       Référence : Code des assurances Art. R331-1

    2. TP SOLVABILITÉ 2 (valorisation économique)
       TP = Best Estimate (BE) + Risk Adjustment (RA)
       BE = valeur actuelle flux futurs au taux sans risque EIOPA
       Référence : Directive 2009/138/CE, Art. 76-86

    3. IFRS 17 (comptabilité internationale)
       Liability for Remaining Coverage (LRC) :
         LRC = Fulfillment Cashflows (FCF) + CSM
       FCF = BE_IFRS17 + RA_IFRS17
       CSM = Contractual Service Margin (profit futur non encore gagné)
       Si FCF > 0 : contrat déficitaire → Loss Component (LC) à la place du CSM

    RÉCONCILIATION :
    ────────────────
    Écart PM/TP = Δ taux d'actualisation + Δ hypothèses mortalité + Δ frais
    Écart TP/IFRS17 ≈ CSM (représente la valeur du service futur)

    Cette réconciliation est exigée par les auditeurs et l'ACPR depuis 2023.
    """

    def __init__(self, models_path='/tmp/actuaria/models',
                 audit_path='/tmp/actuaria/audit', verbose=True):
        self.models_path = models_path
        self.audit_path  = audit_path
        self.verbose     = verbose
        self.logger      = logging.getLogger('actuaria.v8')
        os.makedirs(models_path, exist_ok=True)
        os.makedirs(audit_path,  exist_ok=True)

    def run(
        self,
        pm_sociale:         float = 50_000_000,
        be_vie:             float = 45_000_000,
        risk_adjustment_s2: float =  2_000_000,
        csm:                float =  3_000_000,
        ra_ifrs17:          float =  1_500_000,
        lc:                 float =          0,
        taux_technique_pm:  float =      0.025,
        taux_sans_risque:   float =      0.030,
        taux_marche:        float =      0.040,
        duree_moyenne:      int   =         15,
        nb_contrats:        int   =     10_000,
        result_v3:          Optional[Dict] = None,
        result_v5:          Optional[Dict] = None,
        generer_graphiques: bool  =       True,
    ) -> Dict:
        """
        Calcule et réconcilie les trois référentiels PM/TP/IFRS 17.

        Paramètres
        ──────────
        pm_sociale : float
            Provisions mathématiques en comptabilité sociale (PCG).
            Actualisées au taux technique contractuel.

        be_vie : float
            Best Estimate Solvabilité 2 (taux sans risque EIOPA).

        risk_adjustment_s2 : float
            Risk Adjustment S2 = RA = marge de risque non-financier.
            Typiquement 3-8% du BE selon la volatilité du portefeuille.

        csm : float
            Contractual Service Margin IFRS 17 = profit futur non gagné.
            Positif si le contrat est profitable (CSM > 0 → bloc de service).
            Si nul avec LC > 0 : contrat déficitaire dès la souscription.

        ra_ifrs17 : float
            Risk Adjustment IFRS 17 ≈ RA S2 mais calculé différemment
            (méthode de la « confidence level » sous IFRS 17 §B91).

        lc : float
            Loss Component = perte initiale si FCF > 0 à la souscription.
            Incompatible avec CSM > 0.

        result_v3 : dict, optional
            Alimente pm_sociale et be_vie depuis V3 Amélie.

        result_v5 : dict, optional
            Alimente be_vie depuis V5 Nia (qrt_s12).
        """
        audit_id = f"V8_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger = self.logger
        if self.verbose:
            logger.info(f"[{audit_id}] Agent V8 démarré | PM={pm_sociale/1e6:.1f}M€")

        try:
            # ── Alimentation depuis la chaîne actuarielle ─────────────────────
            sources = {}
            if result_v3 and result_v3.get('success'):
                pm_sociale = result_v3.get('pm_prospective', pm_sociale)
                be_vie     = result_v3.get('pm_prospective', be_vie)
                sources['pm_sociale'] = 'V3 Amélie (pm_prospective)'
                sources['be_vie']     = 'V3 Amélie (pm_prospective)'
                logger.info(f"[{audit_id}] PM alimentée depuis V3 : {pm_sociale/1e6:.1f}M€")

            if result_v5 and result_v5.get('success'):
                s12 = result_v5.get('qrt_s12', {})
                be_vie = s12.get('be_vie', be_vie)
                risk_adjustment_s2 = s12.get('risk_adjustment', risk_adjustment_s2)
                sources['be_vie']             = 'V5 Nia (qrt_s12.be_vie)'
                sources['risk_adjustment_s2'] = 'V5 Nia (qrt_s12.risk_adjustment)'
                logger.info(f"[{audit_id}] BE alimenté depuis V5 : {be_vie/1e6:.1f}M€")

            # ── RÉFÉRENTIEL 1 : PM SOCIALE ─────────────────────────────────────
            # Actualisée au taux technique (taux_technique_pm)
            # Représente la valeur des engagements selon le tarif d'origine
            pm_ref = {
                'valeur':          round(pm_sociale, 0),
                'taux_actu':       taux_technique_pm,
                'referentiel':     'Comptabilité sociale (PCG)',
                'base_reglementaire': 'Art. R331-1 Code des assurances',
            }

            # ── RÉFÉRENTIEL 2 : TP SOLVABILITÉ 2 ──────────────────────────────
            # TP = BE + RA
            # BE actualisé au taux sans risque EIOPA (courbe RFR)
            tp_s2 = be_vie + risk_adjustment_s2
            ratio_tp_be = tp_s2 / max(be_vie, 1)

            # Effet taux : écart PM vs BE dû à la différence de taux
            # ΔPM = PM × (1 - v_rfr^n) / (1 - v_tech^n) - PM
            # Approximation : ΔPM ≈ PM × (taux_tech - taux_rfr) × D_mod
            d_mod = duree_moyenne / (1 + taux_technique_pm)
            delta_taux_pm_be = pm_sociale * (taux_technique_pm - taux_sans_risque) * d_mod

            tp_ref = {
                'be_vie':              round(be_vie, 0),
                'risk_adjustment':     round(risk_adjustment_s2, 0),
                'tp_total':            round(tp_s2, 0),
                'ratio_tp_be':         round(ratio_tp_be, 4),
                'taux_actu':           taux_sans_risque,
                'referentiel':         'Solvabilité 2',
                'base_reglementaire':  'Dir. 2009/138/CE Art. 76-86 + RFR EIOPA',
                'delta_vs_pm':         round(tp_s2 - pm_sociale, 0),
                'delta_taux_pm_be':    round(delta_taux_pm_be, 0),
            }

            # ── RÉFÉRENTIEL 3 : IFRS 17 ───────────────────────────────────────
            # LRC = FCF + CSM (si contrat profitable)
            #     = FCF + LC  (si contrat déficitaire)
            # FCF = BE_IFRS17 + RA_IFRS17
            # BE IFRS 17 ≈ BE S2 (même principe, légères différences de périmètre)
            be_ifrs17 = be_vie  # approximation : même BE pour simplification
            fcf = be_ifrs17 + ra_ifrs17

            # CSM et LC sont mutuellement exclusifs
            if csm > 0 and lc > 0:
                logger.warning(f"[{audit_id}] CSM et LC tous deux > 0 — incohérence IFRS 17")
                lc = 0  # priorité au CSM

            lrc = fcf + csm + lc  # LRC totale

            # Résultat IFRS 17 vs TP S2 : l'écart est essentiellement le CSM
            delta_ifrs17_s2 = lrc - tp_s2

            ifrs17_ref = {
                'be_ifrs17':           round(be_ifrs17, 0),
                'ra_ifrs17':           round(ra_ifrs17, 0),
                'fcf':                 round(fcf, 0),
                'csm':                 round(csm, 0),
                'lc':                  round(lc, 0),
                'lrc_total':           round(lrc, 0),
                'contrat_profitable':  csm > 0,
                'taux_actu':           taux_sans_risque,
                'referentiel':         'IFRS 17',
                'base_reglementaire':  'IFRS 17 §32-46 (LRC) + §B91 (RA)',
                'delta_vs_tp_s2':      round(delta_ifrs17_s2, 0),
            }

            # ── TABLEAU DE RÉCONCILIATION TRICOLONNE ──────────────────────────
            reconciliation = {
                'pm_sociale':   round(pm_sociale, 0),
                'tp_s2':        round(tp_s2, 0),
                'lrc_ifrs17':   round(lrc, 0),

                # Passage PM → TP S2
                'delta_pm_to_tp': {
                    'total':           round(tp_s2 - pm_sociale, 0),
                    'effet_taux':      round(delta_taux_pm_be, 0),
                    'effet_ra':        round(risk_adjustment_s2, 0),
                    'effet_autres':    round(tp_s2 - pm_sociale - delta_taux_pm_be - risk_adjustment_s2, 0),
                    'pct':             round((tp_s2 - pm_sociale) / max(pm_sociale, 1) * 100, 1),
                },
                # Passage TP S2 → IFRS 17
                'delta_tp_to_ifrs17': {
                    'total':           round(delta_ifrs17_s2, 0),
                    'csm':             round(csm, 0),
                    'lc':              round(lc, 0),
                    'delta_ra':        round(ra_ifrs17 - risk_adjustment_s2, 0),
                    'pct':             round(delta_ifrs17_s2 / max(tp_s2, 1) * 100, 1),
                },
                # Passage PM → IFRS 17 (global)
                'delta_pm_to_ifrs17': {
                    'total':           round(lrc - pm_sociale, 0),
                    'pct':             round((lrc - pm_sociale) / max(pm_sociale, 1) * 100, 1),
                },
            }

            # ── INDICATEURS PAR CONTRAT ───────────────────────────────────────
            pm_par_contrat    = pm_sociale / max(nb_contrats, 1)
            be_par_contrat    = be_vie     / max(nb_contrats, 1)
            lrc_par_contrat   = lrc        / max(nb_contrats, 1)

            # ── STATUT RAG ────────────────────────────────────────────────────
            ecart_pm_tp_pct = abs(tp_s2 - pm_sociale) / max(pm_sociale, 1) * 100
            statut_rag = 'VERT' if ecart_pm_tp_pct <= 15 else \
                         'AMBRE' if ecart_pm_tp_pct <= 30 else 'ROUGE'

            commentaire = (
                f"✅ Réconciliation PM/TP S2/IFRS 17 — {nb_contrats:,} contrats.\n"
                f"PM sociale    : {pm_sociale/1e6:.2f}M€ (taux tech {taux_technique_pm*100:.2f}%)\n"
                f"TP S2         : {tp_s2/1e6:.2f}M€ (BE {be_vie/1e6:.2f}M€ + RA {risk_adjustment_s2/1e3:.0f}k€)\n"
                f"IFRS 17 (LRC) : {lrc/1e6:.2f}M€ (FCF {fcf/1e6:.2f}M€ + CSM {csm/1e3:.0f}k€)\n"
                f"Écart PM/TP   : {tp_s2-pm_sociale:+,.0f}€ ({(tp_s2-pm_sociale)/max(pm_sociale,1)*100:+.1f}%)\n"
                f"Écart TP/IFRS : {delta_ifrs17_s2:+,.0f}€ (essentiellement la CSM = {csm/1e3:.0f}k€)"
            )

            val_hyp = self._valider_reconciliation(
                pm_sociale, tp_s2, lrc, be_vie, risk_adjustment_s2,
                csm, ratio_tp_be, ecart_pm_tp_pct
            )
            graphiques = {}
            gv = {}
            if generer_graphiques:
                graphiques = self._generer_graphiques(
                    pm_ref, tp_ref, ifrs17_ref, reconciliation, nb_contrats
                )
                gv = self._graphiques_validation_recon(val_hyp, reconciliation)

            self._sauvegarder({
                'agent': 'V8 Marcus',
                'pm_sociale': pm_sociale, 'tp_s2': tp_s2, 'lrc': lrc,
            }, audit_id)

            return {
                'success':            True,
                'agent':              'V8 Marcus',
                'statut_rag':         statut_rag,
                'pm_ref':             pm_ref,
                'tp_s2_ref':          tp_ref,
                'ifrs17_ref':         ifrs17_ref,
                'reconciliation':     reconciliation,
                'nb_contrats':        nb_contrats,
                'pm_par_contrat':     round(pm_par_contrat, 0),
                'be_par_contrat':     round(be_par_contrat, 0),
                'lrc_par_contrat':    round(lrc_par_contrat, 0),
                'sources':            sources,
                'commentaire':        commentaire,
                'audit_id':           audit_id,
                'graphiques':         graphiques,
                'validation_recon':   val_hyp,
                'graphiques_validation': gv,
                'erreur':             None,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR V8 : {e}", exc_info=True)
            return {'success': False, 'statut_rag': 'ROUGE',
                    'erreur': str(e), 'audit_id': audit_id}

    # ─── VALIDATION ──────────────────────────────────────────────────────────
    def _valider_reconciliation(self, pm, tp, lrc, be, ra, csm,
                                 ratio_tp_be, ecart_pm_tp_pct) -> Dict:
        """
        C1 — Écart PM/TP ≤ 30% (cohérence inter-référentiels)
        C2 — Ratio TP/BE ∈ [1.0, 1.5] (RA justifié)
        C3 — CSM ≥ 0 (contrat profitable ou neutre)
        """
        # C1 — Écart PM/TP
        if ecart_pm_tp_pct <= 15:
            c1_s, c1_m, c1_c = 'VERT', f"Écart PM/TP = {ecart_pm_tp_pct:.1f}% ≤ 15% ✅", \
                "PM et TP cohérentes — différentiel de taux maîtrisé"
        elif ecart_pm_tp_pct <= 30:
            c1_s, c1_m, c1_c = 'AMBRE', f"Écart PM/TP = {ecart_pm_tp_pct:.1f}% ∈ [15%,30%] ⚠️", \
                "Écart significatif — documenter les sources (taux, hypothèses)"
        else:
            c1_s, c1_m, c1_c = 'ROUGE', f"Écart PM/TP = {ecart_pm_tp_pct:.1f}% > 30% ❌", \
                "Divergence excessive — revoir les hypothèses ou le taux RFR EIOPA"

        # C2 — Ratio TP/BE
        if 1.0 <= ratio_tp_be <= 1.5:
            c2_s, c2_m, c2_c = 'VERT', f"Ratio TP/BE = {ratio_tp_be:.3f} ∈ [1.0,1.5] ✅", \
                "RA justifié — Risk Adjustment proportionnel au BE"
        elif ratio_tp_be < 1.0:
            c2_s, c2_m, c2_c = 'ROUGE', f"Ratio TP/BE = {ratio_tp_be:.3f} < 1.0 ❌", \
                "RA négatif impossible — revoir le calcul du Risk Adjustment"
        else:
            c2_s, c2_m, c2_c = 'AMBRE', f"Ratio TP/BE = {ratio_tp_be:.3f} > 1.5 ⚠️", \
                "RA élevé — justifier la méthode de calcul devant l'ACPR"

        # C3 — CSM
        if csm > 0:
            c3_s, c3_m, c3_c = 'VERT', f"CSM = {csm/1e3:.0f}k€ > 0 ✅", \
                "Portefeuille profitable — service futur valorisé positivement"
        elif csm == 0:
            c3_s, c3_m, c3_c = 'AMBRE', "CSM = 0 ⚠️", \
                "Pas de CSM — vérifier si Loss Component ou portefeuille break-even"
        else:
            c3_s, c3_m, c3_c = 'ROUGE', f"CSM = {csm/1e3:.0f}k€ < 0 ❌", \
                "CSM négatif impossible — utiliser le Loss Component (LC) à la place"

        sts = [c1_s, c2_s, c3_s]
        sg = 'ROUGE' if 'ROUGE' in sts else 'AMBRE' if 'AMBRE' in sts else 'VERT'
        return {
            'c1_ecart_pm_tp': {'ecart_pct': round(ecart_pm_tp_pct, 1), 'statut': c1_s,
                                'message': c1_m, 'conseil': c1_c,
                                'titre_graphique': f"{'✅' if c1_s=='VERT' else '⚠️' if c1_s=='AMBRE' else '❌'} Écart PM/TP = {ecart_pm_tp_pct:.1f}%"},
            'c2_ratio_tp_be': {'ratio': round(ratio_tp_be, 4), 'statut': c2_s,
                                'message': c2_m, 'conseil': c2_c,
                                'titre_graphique': f"{'✅' if c2_s=='VERT' else '⚠️' if c2_s=='AMBRE' else '❌'} Ratio TP/BE = {ratio_tp_be:.3f}"},
            'c3_csm':          {'csm': round(csm, 0), 'statut': c3_s,
                                'message': c3_m, 'conseil': c3_c,
                                'titre_graphique': f"{'✅' if c3_s=='VERT' else '⚠️' if c3_s=='AMBRE' else '❌'} CSM = {csm/1e3:.0f}k€"},
            'statut_global': sg,
            'conclusion': {
                'VERT':  '✅ Réconciliation PM/TP S2/IFRS 17 validée — trois référentiels cohérents',
                'AMBRE': '⚠️ Réconciliation acceptable — documenter les écarts avant audit',
                'ROUGE': '❌ Incohérence détectée — action correctrice avant clôture',
            }[sg],
        }

    # ─── GRAPHIQUES ──────────────────────────────────────────────────────────
    def _generer_graphiques(self, pm_ref, tp_ref, ifrs17_ref,
                             reconciliation, nb_contrats) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; OR='#C9A84C'; BLANC='#F0F4F8'
        GRIS='#8A9AB0'; VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'; BLEU='#3498DB'
        LAYOUT = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                      font=dict(family='Inter', color=BLANC, size=11),
                      margin=dict(l=16, r=16, t=60, b=50), height=300)
        graphiques = {}

        # G1 — Tableau tricolonne (waterfall PM → TP → IFRS 17)
        try:
            pm   = pm_ref['valeur'] / 1e6
            tp   = tp_ref['tp_total'] / 1e6
            lrc  = ifrs17_ref['lrc_total'] / 1e6
            d_pm_tp   = reconciliation['delta_pm_to_tp']['total'] / 1e6
            d_tp_lrc  = reconciliation['delta_tp_to_ifrs17']['total'] / 1e6

            fig1 = go.Figure(go.Waterfall(
                orientation='v',
                measure=['absolute', 'relative', 'total', 'relative', 'total'],
                x=['PM Sociale', 'Δ PM→TP', 'TP S2', 'Δ TP→IFRS17', 'IFRS 17 (LRC)'],
                y=[pm, d_pm_tp, 0, d_tp_lrc, 0],
                text=[f'{pm:.2f}M€', f'{d_pm_tp:+.2f}M€', f'{tp:.2f}M€',
                      f'{d_tp_lrc:+.2f}M€', f'{lrc:.2f}M€'],
                textposition='outside',
                textfont=dict(color=BLANC, size=10),
                connector=dict(line=dict(color=GRIS, width=1.5)),
                increasing=dict(marker=dict(color=ROUGE, opacity=0.85)),
                decreasing=dict(marker=dict(color=VERT, opacity=0.85)),
                totals=dict(marker=dict(color=OR, opacity=0.9)),
            ))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(text='Réconciliation tricolonne PM / TP S2 / IFRS 17',
                           font=dict(color=BLANC, size=12), x=0.01),
                showlegend=False,
                yaxis=dict(title='M€', tickfont=dict(color=GRIS)),
                xaxis=dict(tickfont=dict(color=BLANC, size=9)),
                annotations=[dict(
                    text="💡 Orange = valeur absolue (PM, TP, LRC). Rouge = hausse des passifs. Vert = baisse.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)],
            ))
            fig1.update_layout(**l1)
            graphiques['waterfall_tricolonne'] = fig1
        except Exception:
            pass

        # G2 — Décomposition TP S2 (BE + RA)
        try:
            be  = tp_ref['be_vie'] / 1e6
            ra  = tp_ref['risk_adjustment'] / 1e6
            c2  = VERT if tp_ref['ratio_tp_be'] <= 1.3 else AMBRE
            fig2 = go.Figure(go.Bar(
                x=['Best Estimate (BE)', 'Risk Adjustment (RA)', 'TP S2 Total'],
                y=[be, ra, be + ra],
                marker_color=[OR, BLEU, c2], width=0.4, opacity=0.88,
                text=[f'{be:.2f}M€', f'{ra:.2f}M€', f'{be+ra:.2f}M€'],
                textposition='outside', textfont=dict(color=BLANC, size=11),
            ))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text=f"Décomposition TP S2 — Ratio TP/BE = {tp_ref['ratio_tp_be']:.3f}",
                           font=dict(color=c2, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title='M€', tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 TP = BE + RA. Le RA doit rester entre 0 et 50% du BE pour être justifiable devant l'ACPR.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)],
            ))
            fig2.update_layout(**l2)
            graphiques['decomposition_tp_s2'] = fig2
        except Exception:
            pass

        # G3 — Décomposition IFRS 17 (FCF + CSM/LC)
        try:
            fcf = ifrs17_ref['fcf'] / 1e6
            csm = ifrs17_ref['csm'] / 1e6
            lc  = ifrs17_ref['lc'] / 1e6
            lrc = ifrs17_ref['lrc_total'] / 1e6
            labels = ['FCF (BE+RA)', 'CSM', 'LRC Total'] if csm > 0 else ['FCF (BE+RA)', 'Loss Component', 'LRC Total']
            vals   = [fcf, csm if csm > 0 else lc, lrc]
            colors = [OR, VERT if csm > 0 else ROUGE, BLEU]
            fig3 = go.Figure(go.Bar(
                x=labels, y=vals, marker_color=colors, width=0.4, opacity=0.88,
                text=[f'{v:.2f}M€' for v in vals],
                textposition='outside', textfont=dict(color=BLANC, size=11),
            ))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(
                    text=f"Décomposition IFRS 17 — {'CSM > 0 : contrat profitable ✅' if csm > 0 else '⚠️ Contrat déficitaire (LC)'}",
                    font=dict(color=VERT if csm > 0 else ROUGE, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title='M€', tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 LRC = FCF + CSM (si profitable) ou FCF + LC (si déficitaire). La CSM est amortie sur la durée du service.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)],
            ))
            fig3.update_layout(**l3)
            graphiques['decomposition_ifrs17'] = fig3
        except Exception:
            pass

        # G4 — Comparaison par contrat (PM / TP / LRC)
        try:
            pm_c   = pm_ref['valeur'] / max(nb_contrats, 1) / 1e3
            tp_c   = tp_ref['tp_total'] / max(nb_contrats, 1) / 1e3
            lrc_c  = ifrs17_ref['lrc_total'] / max(nb_contrats, 1) / 1e3
            fig4 = go.Figure(go.Bar(
                x=['PM Sociale / contrat', 'TP S2 / contrat', 'IFRS 17 LRC / contrat'],
                y=[pm_c, tp_c, lrc_c],
                marker_color=[OR, BLEU, AMBRE], width=0.4, opacity=0.88,
                text=[f'{v:.1f}k€' for v in [pm_c, tp_c, lrc_c]],
                textposition='outside', textfont=dict(color=BLANC, size=11),
            ))
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text=f"Passifs par contrat — {nb_contrats:,} contrats",
                           font=dict(color=BLANC, size=12), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title='k€/contrat', tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 Les trois référentiels donnent des passifs différents par contrat. L'écart TP-PM est lié au taux RFR EIOPA.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)],
            ))
            fig4.update_layout(**l4)
            graphiques['passifs_par_contrat'] = fig4
        except Exception:
            pass

        return graphiques

    def _graphiques_validation_recon(self, val, reconciliation) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; BLANC='#F0F4F8'; GRIS='#8A9AB0'
        VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'
        LAYOUT = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                      font=dict(family='Inter', color=BLANC, size=11),
                      margin=dict(l=16, r=16, t=60, b=50), height=260)
        graphiques = {}
        try:
            items = [
                ('C1 — Écart PM/TP ≤ 30%', val['c1_ecart_pm_tp']['statut'],
                 val['c1_ecart_pm_tp']['message'], val['c1_ecart_pm_tp']['conseil']),
                ('C2 — Ratio TP/BE ∈ [1.0,1.5]', val['c2_ratio_tp_be']['statut'],
                 val['c2_ratio_tp_be']['message'], val['c2_ratio_tp_be']['conseil']),
                ('C3 — CSM ≥ 0 (profitable)', val['c3_csm']['statut'],
                 val['c3_csm']['message'], val['c3_csm']['conseil']),
            ]
            fig = go.Figure()
            for nom, statut, msg, conseil in items:
                c = VERT if statut == 'VERT' else AMBRE if statut == 'AMBRE' else ROUGE
                i = '✅' if statut == 'VERT' else '⚠️' if statut == 'AMBRE' else '❌'
                s = 1.0 if statut == 'VERT' else 0.5 if statut == 'AMBRE' else 0.0
                fig.add_trace(go.Bar(x=[s], y=[nom], orientation='h', marker_color=c, width=0.5,
                                     text=f"{i} {statut}", textposition='outside',
                                     textfont=dict(color=c, size=10),
                                     hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                                     showlegend=False))
            sg = val['statut_global']
            cg = VERT if sg == 'VERT' else AMBRE if sg == 'AMBRE' else ROUGE
            fig.update_layout(**LAYOUT,
                title=dict(text=f"Scorecard Réconciliation — {val['conclusion']}",
                           font=dict(color=cg, size=10), x=0.01),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode='overlay',
                annotations=[dict(
                    text="💡 3 ✅ = tricolonne PM/TP/IFRS 17 validée, défendable devant auditeurs et ACPR.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)])
            graphiques['scorecard_recon'] = fig
        except Exception:
            pass
        return graphiques

    def _sauvegarder(self, rapport, audit_id):
        try:
            fpath = os.path.join(self.models_path, f"v8_recon_{audit_id}.json")
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sauvegardé : v8_recon_{audit_id}.json")
        except Exception as e:
            self.logger.warning(f"Sauvegarde V8 : {e}")
