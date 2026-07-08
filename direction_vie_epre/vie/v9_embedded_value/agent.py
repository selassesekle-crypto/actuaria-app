"""
ActuarIA — Agent V9 : Élise — Embedded Value Simplifiée
Direction Vie & EP-RE | Manager : Sven | Directeur : Paul

Calcul de l'Embedded Value (EV) simplifiée du portefeuille vie :
→ Actif Net Réévalué (ANE) = actifs de marché − PM S2
→ Valeur des Affaires en Portefeuille (VIF) = VA des profits futurs
→ Value of New Business (VNB) = EV sur les affaires nouvelles
→ EV = ANE + VIF
→ Décomposition par source de création de valeur
→ Alimentation depuis V1 (décès), V2 (épargne), V3 (PM), V4 (PB)
"""

import numpy as np, logging, os, json
from datetime import datetime
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.v9 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent V9 — Embedded Value Simplifiée ActuarIA v1.0")
print("EV = ANE + VIF | VNB | Décomposition par source de valeur")
print("Usage : agent_v9 = AgentV9EmbeddedValue()")
print("        result_v9 = agent_v9.run(actifs_marche=60e6, pm_s2=50e6)")


class AgentV9EmbeddedValue:
    """
    Agent V9 — Élise : Embedded Value (EV) simplifiée vie.

    DÉFINITIONS (CEA Guidelines / MCEV Principles) :
    ─────────────────────────────────────────────────
    Embedded Value (EV) = ANE + VIF

    ANE (Actif Net Réévalué) :
        ANE = Actifs de marché − TP Solvabilité 2 (PM + RA)
        Représente la valeur intrinsèque du bilan à date.

    VIF (Value In-Force) :
        VIF = VA des profits futurs non encore reconnus dans l'ANE
        = Σ_t [ (Primes_t − Prestations_t − Frais_t − Coût_capital_t)
                × v^t × t_px ]
        Approximé par : VIF ≈ PM × marge_sur_services × ä_residuelle

    VNB (Value of New Business) :
        VNB = valeur créée par les nouvelles souscriptions de l'année
        = Primes_nouvelles_nettes × taux_marge_VNB
        où taux_marge_VNB ≈ (prime_commerciale − prime_pure) / prime_pure × E_xn

    DÉCOMPOSITION DE L'ÉVOLUTION EV (MCEV §9) :
        ΔEV = VNB + Unwinding + Changements hypothèses + Gains expérience + Autres
        where Unwinding = EV_N-1 × taux_ref (coût de capital du temps)

    COÛT DU CAPITAL (CoC) :
        Charge annuelle sur le SCR pour refléter le risque résiduel
        CoC = SCR × (taux_coc − taux_rf)
        où taux_coc = 6% (EIOPA, IFRS 17 §B91)
    """

    def __init__(self, models_path='/tmp/actuaria/models',
                 audit_path='/tmp/actuaria/audit', verbose=True):
        self.models_path = models_path
        self.audit_path  = audit_path
        self.verbose     = verbose
        self.logger      = logging.getLogger('actuaria.v9')
        os.makedirs(models_path, exist_ok=True)
        os.makedirs(audit_path, exist_ok=True)

    def run(
        self,
        actifs_marche:      float = 60_000_000,
        pm_s2:              float = 50_000_000,
        risk_adjustment:    float =  2_000_000,
        scr_vie:            float =  5_000_000,
        fonds_propres_req:  float =  6_000_000,
        taux_reference:     float =       0.03,
        taux_coc:           float =       0.06,
        marge_sur_services: float =      0.015,
        duree_moyenne:      int   =         15,
        primes_nouvelles:   float =  5_000_000,
        taux_chargement:    float =       0.15,
        frais_acquisition_pct: float =    0.05,   # Frais d'acquisition sur primes nouvelles (ex: 5%)
        frais_gestion_pct:  float =       0.008,  # Frais de gestion annuels sur encours (ex: 0.8%)
        ev_n1:              float =          0,
        result_v1:          Optional[Dict] = None,
        result_v2:          Optional[Dict] = None,
        result_v3:          Optional[Dict] = None,
        result_v4:          Optional[Dict] = None,
        generer_graphiques: bool  =       True,
    ) -> Dict:
        """
        Calcule l'Embedded Value et sa décomposition.

        Paramètres
        ──────────
        actifs_marche : float
            Valeur de marché totale des actifs couvrant les PM (€).

        pm_s2 : float
            Best Estimate Solvabilité 2 (€). Alimenté par V3 si disponible.

        risk_adjustment : float
            Risk Adjustment S2 — composante TP non-BE (€).

        scr_vie : float
            SCR Vie calculé par R-VIE1 (pour le coût du capital).

        fonds_propres_req : float
            Fonds propres requis (= SCR × ratio cible, ex : 150%).

        taux_reference : float
            Taux de référence sans risque (OAT 10 ans, ex: 3%).

        taux_coc : float
            Taux de coût du capital EIOPA : 6% (IFRS 17 §B91).

        marge_sur_services : float
            Marge nette annuelle sur l'encours (ex: 1.5% = chargements − frais).

        duree_moyenne : int
            Duration moyenne résiduelle du portefeuille (années).

        primes_nouvelles : float
            Volume de primes nouvelles de l'année (pour VNB).

        taux_chargement : float
            Taux de chargement commercial (prime commerciale / prime pure − 1).

        frais_acquisition_pct : float
            Frais d'acquisition en % des primes nouvelles (commission réseau, ex: 5%).

        frais_gestion_pct : float
            Frais de gestion annuels sur encours (ex: 0.8% conforme marché vie).
            Inclut les frais administratifs et informatiques alloués.

        ev_n1 : float
            Embedded Value de l'exercice précédent (pour calcul ΔEV).

        result_v1/v2/v3/v4 : dict, optional
            Résultats des agents amont pour alimentation automatique.
        """
        audit_id = f"V9_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger = self.logger
        if self.verbose:
            logger.info(f"[{audit_id}] Agent V9 démarré | Actifs={actifs_marche/1e6:.1f}M€ | PM S2={pm_s2/1e6:.1f}M€")

        try:
            # ── Alimentation depuis la chaîne actuarielle ─────────────────────
            sources = {}
            if result_v3 and result_v3.get('success'):
                pm_s2 = result_v3.get('pm_prospective', pm_s2)
                sources['pm_s2'] = 'V3 Amélie (pm_prospective)'
                logger.info(f"[{audit_id}] PM S2 alimenté depuis V3 : {pm_s2/1e6:.1f}M€")

            if result_v4 and result_v4.get('success'):
                marge_sur_services_v4 = (
                    result_v4.get('pb_reglementaire_min', 0) /
                    max(result_v4.get('pm_total', pm_s2), 1)
                )
                if marge_sur_services_v4 > 0:
                    marge_sur_services = marge_sur_services_v4
                    sources['marge_sur_services'] = 'V4 Théo (pb_reglementaire_min / pm_total)'
                    logger.info(f"[{audit_id}] Marge V4 = {marge_sur_services*100:.2f}%")

            if result_v2 and result_v2.get('success'):
                be = result_v2.get('be_vie', 0)
                if be > 0:
                    actifs_marche = max(actifs_marche, be * 1.10)
                    sources['actifs_marche_min'] = 'V2 Kofi (be_vie × 1.10 minimum)'

            if result_v1 and result_v1.get('success'):
                ev_residuelle = result_v1.get('indicateurs', {}).get('ev_residuelle', 0)
                if ev_residuelle > 0:
                    sources['ev_residuelle_v1'] = f"V1 Nour : {ev_residuelle/1e3:.0f}k€"
                    logger.info(f"[{audit_id}] EV résiduelle V1 (décès) : {ev_residuelle:.0f}€")

            # ── ANE — ACTIF NET RÉÉVALUÉ ───────────────────────────────────────
            # TP S2 = BE + RA
            tp_s2 = pm_s2 + risk_adjustment
            # ANE = Actifs de marché − TP S2 − Fonds propres requis hors bilan
            ane = actifs_marche - tp_s2

            # ── COÛT DU CAPITAL ────────────────────────────────────────────────
            # CoC annuel = SCR × (taux_coc − taux_rf)
            # Projeté sur duree_moyenne années
            cout_capital_annuel = scr_vie * (taux_coc - taux_reference)
            # VA du CoC sur l'horizon (rente à taux_reference)
            if taux_reference > 0:
                va_coc = cout_capital_annuel * (1 - (1 + taux_reference)**(-duree_moyenne)) / taux_reference
            else:
                va_coc = cout_capital_annuel * duree_moyenne

            # ── VIF — VALUE IN-FORCE ───────────────────────────────────────────
            # VIF = VA des profits futurs − VA du CoC
            # Profits futurs annuels ≈ pm_s2 × marge_sur_services
            profits_annuels = pm_s2 * marge_sur_services
            # VA des profits (rente à taux_reference sur duree_moyenne)
            if taux_reference > 0:
                va_profits = profits_annuels * (1 - (1 + taux_reference)**(-duree_moyenne)) / taux_reference
            else:
                va_profits = profits_annuels * duree_moyenne

            vif = max(0, va_profits - va_coc)

            # ── EV — EMBEDDED VALUE ────────────────────────────────────────────
            ev = ane + vif

            # ── VNB — VALUE OF NEW BUSINESS (méthode MCEV §18) ───────────────
            # VNB = VA des profits nets générés par les nouvelles souscriptions
            #
            # Décomposition de la marge nette sur prime commerciale :
            #   Chargement brut          = primes × taux_chargement
            #   Frais d'acquisition      = primes × frais_acquisition_pct
            #   Frais de gestion (VA)    = pm_nouvelles × frais_gestion_pct × ä_moy
            #   Marge nette              = Chargement - Acq. - Gestion
            #
            # Référence : CEA EV Principles §4.3 / AXA MCEV disclosure methodology

            # Annuité actuarielle moyenne pour les nouvelles affaires
            # (horizon moyen = duree_moyenne / 2 car souscriptions étalées)
            if taux_reference > 0:
                a_moy_vnb = (1 - (1 + taux_reference)**(-duree_moyenne)) / taux_reference
            else:
                a_moy_vnb = float(duree_moyenne)

            # PM moyenne des nouvelles affaires ≈ prime_pure × ä_moy
            # Prime pure ≈ prime_commerciale / (1 + taux_chargement)
            prime_commerciale_tot = primes_nouvelles
            prime_pure_tot = prime_commerciale_tot / max(1 + taux_chargement, 1.01)
            pm_nouvelles   = prime_pure_tot * a_moy_vnb  # PM générée par nouvelles affaires

            # Chargement brut sur nouvelles affaires
            chargement_brut = prime_commerciale_tot * taux_chargement / (1 + taux_chargement)

            # Frais d'acquisition (coût de distribution)
            frais_acq = prime_commerciale_tot * frais_acquisition_pct

            # VA des frais de gestion futurs sur la PM des nouvelles affaires
            frais_gest_va = pm_nouvelles * frais_gestion_pct

            # VNB brut = chargement - frais acquisition - VA frais gestion
            vnb_brut = chargement_brut - frais_acq - frais_gest_va

            # Actualisation : les profits sont réalisés sur la durée du contrat
            # → discountés au taux de référence
            if taux_reference > 0:
                facteur_actu_vnb = (1 - (1 + taux_reference)**(-duree_moyenne / 2)) / taux_reference
            else:
                facteur_actu_vnb = float(duree_moyenne) / 2

            vnb = vnb_brut * facteur_actu_vnb / max(a_moy_vnb, 1)
            # Borne de cohérence : VNB ∈ [0, 20% des primes nouvelles]
            # Un VNB > 20% est économiquement improbable (benchmark marché : 5-15%)
            vnb = min(max(vnb, 0), prime_commerciale_tot * 0.20)

            # ── DÉCOMPOSITION ΔEV (si ev_n1 fourni) ──────────────────────────
            delta_ev = ev - ev_n1 if ev_n1 > 0 else None
            unwinding = ev_n1 * taux_reference if ev_n1 > 0 else 0
            # Gain d'expérience = ΔEV − VNB − Unwinding (résiduel)
            gain_experience = (delta_ev - vnb - unwinding) if delta_ev is not None else None

            # ── RATIOS CLÉS ───────────────────────────────────────────────────
            ratio_vnb_primes = vnb / max(primes_nouvelles, 1) * 100
            ratio_vif_pm     = vif / max(pm_s2, 1) * 100
            ratio_ev_actifs  = ev / max(actifs_marche, 1) * 100
            levier_coc       = va_coc / max(vif + va_coc, 1) * 100

            # ── STATUT RAG ────────────────────────────────────────────────────
            if ane >= 0 and vif > 0 and ratio_vnb_primes >= 5:
                statut_rag = 'VERT'
            elif ane >= 0 and vif >= 0:
                statut_rag = 'AMBRE'
            else:
                statut_rag = 'ROUGE'

            commentaire = (
                f"{'✅' if statut_rag=='VERT' else '⚠️' if statut_rag=='AMBRE' else '❌'} "
                f"Embedded Value — Actifs {actifs_marche/1e6:.1f}M€ | PM S2 {pm_s2/1e6:.1f}M€.\n"
                f"ANE : {ane/1e6:.2f}M€ | VIF : {vif/1e6:.2f}M€ | EV : {ev/1e6:.2f}M€.\n"
                f"VNB : {vnb/1e3:.0f}k€ ({ratio_vnb_primes:.1f}% des primes nouvelles).\n"
                f"VA profits futurs : {va_profits/1e6:.2f}M€ | VA CoC : {va_coc/1e6:.2f}M€."
            )

            val_hyp = self._valider_ev(ane, vif, ev, vnb, ratio_vnb_primes,
                                        va_coc, va_profits, levier_coc)
            graphiques = {}
            gv = {}
            if generer_graphiques:
                graphiques = self._generer_graphiques(
                    ane, vif, ev, vnb, va_profits, va_coc,
                    actifs_marche, tp_s2, primes_nouvelles
                )
                gv = self._graphiques_validation_ev(val_hyp)

            self._sauvegarder({
                'agent': 'V9 Élise', 'ev': ev, 'ane': ane, 'vif': vif, 'vnb': vnb,
            }, audit_id)

            result = {
                'success':            True,
                'agent':              'V9 Élise',
                'statut_rag':         statut_rag,
                'ane':                round(ane, 0),
                'vif':                round(vif, 0),
                'ev':                 round(ev, 0),
                'vnb':                round(vnb, 0),
                'tp_s2':              round(tp_s2, 0),
                'va_profits':         round(va_profits, 0),
                'va_coc':             round(va_coc, 0),
                'cout_capital_annuel':round(cout_capital_annuel, 0),
                'ratios': {
                    'ratio_vnb_primes_pct': round(ratio_vnb_primes, 2),
                    'ratio_vif_pm_pct':     round(ratio_vif_pm, 2),
                    'ratio_ev_actifs_pct':  round(ratio_ev_actifs, 2),
                    'levier_coc_pct':       round(levier_coc, 2),
                },
                'sources':            sources,
                'commentaire':        commentaire,
                'audit_id':           audit_id,
                'graphiques':         graphiques,
                'validation_ev':      val_hyp,
                'graphiques_validation': gv,
                'erreur':             None,
            }
            if delta_ev is not None:
                result['decomposition_delta_ev'] = {
                    'ev_n1':           round(ev_n1, 0),
                    'ev_n':            round(ev, 0),
                    'delta_ev':        round(delta_ev, 0),
                    'vnb':             round(vnb, 0),
                    'unwinding':       round(unwinding, 0),
                    'gain_experience': round(gain_experience, 0),
                }
            return result

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR V9 : {e}", exc_info=True)
            return {'success': False, 'statut_rag': 'ROUGE',
                    'erreur': str(e), 'audit_id': audit_id}

    # ─── VALIDATION ──────────────────────────────────────────────────────────
    def _valider_ev(self, ane, vif, ev, vnb, ratio_vnb,
                    va_coc, va_profits, levier_coc) -> Dict:
        """
        E1 — ANE ≥ 0 (bilan solvable à valeur de marché)
        E2 — VIF > 0 (portefeuille créateur de valeur)
        E3 — VNB / Primes nouvelles ≥ 5% (rentabilité des affaires nouvelles)
        """
        # E1 — ANE
        fonds_propres_req_ref = max(va_coc, 0)
        if ane >= fonds_propres_req_ref:
            e1_s = 'VERT'
            e1_m = f"ANE = {ane/1e6:.2f}M€ ≥ VA CoC ({fonds_propres_req_ref/1e6:.2f}M€) ✅"
            e1_c = "Bilan solvable — actifs couvrent provisions + coût du capital"
        elif ane >= 0:
            e1_s = 'AMBRE'
            e1_m = f"ANE = {ane/1e6:.2f}M€ ≥ 0 mais < VA CoC ({fonds_propres_req_ref/1e6:.2f}M€) ⚠️"
            e1_c = "Solvable mais CoC non couvert — renforcer les actifs ou réduire le SCR"
        else:
            e1_s = 'ROUGE'
            e1_m = f"ANE = {ane/1e6:.2f}M€ < 0 ❌"
            e1_c = "INSOLVABILITÉ ÉCONOMIQUE — recapitalisation immédiate requise"

        # E2 — VIF
        if vif > va_coc * 0.5:
            e2_s = 'VERT'
            e2_m = f"VIF = {vif/1e6:.2f}M€ > 50% CoC ✅"
            e2_c = "Portefeuille profitable après coût du capital"
        elif vif > 0:
            e2_s = 'AMBRE'
            e2_m = f"VIF = {vif/1e6:.2f}M€ > 0 mais < CoC ⚠️"
            e2_c = "VIF positif mais marge limitée — optimiser les frais ou chargements"
        else:
            e2_s = 'ROUGE'
            e2_m = f"VIF = {vif/1e6:.2f}M€ ≤ 0 ❌"
            e2_c = "Portefeuille destructeur de valeur — revoir le modèle de tarification"

        # E3 — VNB / Primes
        if ratio_vnb >= 10:
            e3_s = 'VERT'
            e3_m = f"VNB/Primes = {ratio_vnb:.1f}% ≥ 10% ✅"
            e3_c = "Nouvelles affaires très rentables — maintenir le rythme de croissance"
        elif ratio_vnb >= 5:
            e3_s = 'AMBRE'
            e3_m = f"VNB/Primes = {ratio_vnb:.1f}% ∈ [5%,10%] ⚠️"
            e3_c = "Rentabilité des affaires nouvelles correcte — optimiser les frais d'acquisition"
        else:
            e3_s = 'ROUGE'
            e3_m = f"VNB/Primes = {ratio_vnb:.1f}% < 5% ❌"
            e3_c = "Affaires nouvelles peu rentables — revoir la politique tarifaire et de distribution"

        sts = [e1_s, e2_s, e3_s]
        sg = 'ROUGE' if 'ROUGE' in sts else 'AMBRE' if 'AMBRE' in sts else 'VERT'
        return {
            'e1_ane': {'ane': round(ane, 0), 'statut': e1_s, 'message': e1_m, 'conseil': e1_c,
                       'titre_graphique': f"{'✅' if e1_s=='VERT' else '⚠️' if e1_s=='AMBRE' else '❌'} ANE = {ane/1e6:.2f}M€"},
            'e2_vif': {'vif': round(vif, 0), 'statut': e2_s, 'message': e2_m, 'conseil': e2_c,
                       'titre_graphique': f"{'✅' if e2_s=='VERT' else '⚠️' if e2_s=='AMBRE' else '❌'} VIF = {vif/1e6:.2f}M€"},
            'e3_vnb': {'ratio_pct': round(ratio_vnb, 2), 'statut': e3_s, 'message': e3_m, 'conseil': e3_c,
                       'titre_graphique': f"{'✅' if e3_s=='VERT' else '⚠️' if e3_s=='AMBRE' else '❌'} VNB/Primes = {ratio_vnb:.1f}%"},
            'statut_global': sg,
            'conclusion': {
                'VERT':  '✅ EV validée — ANE positif, VIF créateur de valeur et VNB rentable',
                'AMBRE': '⚠️ EV acceptable — renforcer la rentabilité ou la solvabilité',
                'ROUGE': '❌ EV dégradée — action corrective urgente sur solvabilité ou tarification',
            }[sg],
        }

    # ─── GRAPHIQUES ──────────────────────────────────────────────────────────
    def _generer_graphiques(self, ane, vif, ev, vnb, va_profits, va_coc,
                             actifs, tp_s2, primes) -> Dict:
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

        # G1 — Décomposition EV (waterfall)
        try:
            fig1 = go.Figure(go.Waterfall(
                orientation='v',
                measure=['absolute', 'relative', 'total', 'relative', 'total'],
                x=['TP S2\n(passif)', 'ANE\n(bilan)', 'Sous-total', 'VIF\n(profits futurs)', 'EV totale'],
                y=[tp_s2 / 1e6, ane / 1e6, 0, vif / 1e6, 0],
                text=[f'{tp_s2/1e6:.1f}M€', f'{ane/1e6:.1f}M€',
                      f'{(tp_s2+ane)/1e6:.1f}M€', f'{vif/1e6:.1f}M€',
                      f'{ev/1e6:.1f}M€'],
                textposition='outside', textfont=dict(color=BLANC, size=10),
                connector=dict(line=dict(color=GRIS, width=1.5)),
                increasing=dict(marker=dict(color=VERT, opacity=0.85)),
                decreasing=dict(marker=dict(color=ROUGE, opacity=0.85)),
                totals=dict(marker=dict(color=OR, opacity=0.9)),
            ))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(text='Décomposition Embedded Value — ANE + VIF',
                           font=dict(color=BLANC, size=12), x=0.01),
                yaxis=dict(title='M€', tickfont=dict(color=GRIS)),
                showlegend=False,
                annotations=[dict(
                    text="💡 EV = ANE (bilan actuel) + VIF (profits futurs). L'ANE reflète la solvabilité, le VIF la rentabilité.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig1.update_layout(**l1)
            graphiques['waterfall_ev'] = fig1
        except Exception:
            pass

        # G2 — VIF : profits futurs vs coût du capital
        try:
            c_vif = VERT if vif > va_coc else AMBRE if vif > 0 else ROUGE
            fig2 = go.Figure(go.Bar(
                x=['VA Profits futurs', 'VA Coût du capital', 'VIF net'],
                y=[va_profits / 1e6, -va_coc / 1e6, vif / 1e6],
                marker_color=[VERT, ROUGE, c_vif],
                width=0.4, opacity=0.88,
                text=[f'{va_profits/1e6:.2f}M€', f'-{va_coc/1e6:.2f}M€', f'{vif/1e6:.2f}M€'],
                textposition='outside', textfont=dict(color=BLANC, size=10),
            ))
            fig2.add_hline(y=0, line_color=BLANC, line_width=1.5, line_dash='dot')
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text='VIF = Profits futurs − Coût du capital (6% EIOPA)',
                           font=dict(color=c_vif, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title='M€', tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 Le CoC (6% × SCR) est la charge annuelle pour rémunérer les actionnaires. VIF = profits nets de cette charge.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig2.update_layout(**l2)
            graphiques['vif_decomposition'] = fig2
        except Exception:
            pass

        # G3 — Bilan économique (Actifs vs TP S2 vs EV)
        try:
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(
                x=['Actifs de marché'], y=[actifs / 1e6],
                marker_color=VERT, width=0.3, opacity=0.88,
                text=[f'{actifs/1e6:.1f}M€'], textposition='outside',
                textfont=dict(color=BLANC, size=10), name='Actifs'))
            fig3.add_trace(go.Bar(
                x=['TP S2 (BE+RA)'], y=[tp_s2 / 1e6],
                marker_color=ROUGE, width=0.3, opacity=0.88,
                text=[f'{tp_s2/1e6:.1f}M€'], textposition='outside',
                textfont=dict(color=BLANC, size=10), name='TP S2'))
            fig3.add_trace(go.Bar(
                x=['EV (ANE+VIF)'], y=[ev / 1e6],
                marker_color=OR, width=0.3, opacity=0.9,
                text=[f'{ev/1e6:.1f}M€'], textposition='outside',
                textfont=dict(color=BLANC, size=10), name='EV'))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text='Bilan économique — Actifs · TP S2 · EV',
                           font=dict(color=BLANC, size=12), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title='M€', tickfont=dict(color=GRIS)),
                bargap=0.4, showlegend=False,
                annotations=[dict(
                    text="💡 EV < Actifs − TP S2 → une partie de la valeur est 'consommée' par le CoC.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig3.update_layout(**l3)
            graphiques['bilan_economique'] = fig3
        except Exception:
            pass

        # G4 — VNB vs Primes nouvelles
        try:
            c_vnb = VERT if vnb / max(primes, 1) >= 0.10 else AMBRE if vnb / max(primes, 1) >= 0.05 else ROUGE
            fig4 = go.Figure(go.Bar(
                x=['Primes nouvelles', 'VNB', 'Ratio VNB/Primes'],
                y=[primes / 1e6, vnb / 1e6, vnb / max(primes, 1) * 100],
                marker_color=[BLEU, c_vnb, AMBRE],
                width=0.4, opacity=0.88,
                text=[f'{primes/1e6:.1f}M€', f'{vnb/1e3:.0f}k€', f'{vnb/max(primes,1)*100:.1f}%'],
                textposition='outside', textfont=dict(color=BLANC, size=10),
            ))
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text=f"VNB = {vnb/1e3:.0f}k€ ({vnb/max(primes,1)*100:.1f}% des primes nouvelles)",
                           font=dict(color=c_vnb, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title='M€ / %', tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 VNB ≥ 5% des primes = affaires nouvelles rentables. Benchmark marché vie : 8-15%.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig4.update_layout(**l4)
            graphiques['vnb_vs_primes'] = fig4
        except Exception:
            pass

        return graphiques

    def _graphiques_validation_ev(self, val) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; BLANC='#F0F4F8'; GRIS='#8A9AB0'
        VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'
        graphiques = {}
        try:
            items = [
                ('E1 — ANE ≥ 0 (solvabilité)', val['e1_ane']['statut'],
                 val['e1_ane']['message'], val['e1_ane']['conseil']),
                ('E2 — VIF > 0 (valeur)', val['e2_vif']['statut'],
                 val['e2_vif']['message'], val['e2_vif']['conseil']),
                ('E3 — VNB ≥ 5% primes', val['e3_vnb']['statut'],
                 val['e3_vnb']['message'], val['e3_vnb']['conseil']),
            ]
            fig = go.Figure()
            for nom, statut, msg, conseil in items:
                c = VERT if statut == 'VERT' else AMBRE if statut == 'AMBRE' else ROUGE
                i = '✅' if statut == 'VERT' else '⚠️' if statut == 'AMBRE' else '❌'
                s = 1.0 if statut == 'VERT' else 0.5 if statut == 'AMBRE' else 0.0
                fig.add_trace(go.Bar(x=[s], y=[nom], orientation='h', marker_color=c,
                    width=0.5, text=f"{i} {statut}", textposition='outside',
                    textfont=dict(color=c, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False))
            sg = val['statut_global']
            cg = VERT if sg == 'VERT' else AMBRE if sg == 'AMBRE' else ROUGE
            fig.update_layout(
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family='Inter', color=BLANC, size=11),
                margin=dict(l=16, r=16, t=60, b=50), height=260,
                title=dict(text=f"Scorecard EV — {val['conclusion']}",
                           font=dict(color=cg, size=10), x=0.01),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode='overlay',
                annotations=[dict(
                    text="💡 3 ✅ = EV validée, défendable devant investisseurs et analyste sell-side.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)])
            graphiques['scorecard_ev'] = fig
        except Exception:
            pass
        return graphiques

    def _sauvegarder(self, rapport, audit_id):
        try:
            fpath = os.path.join(self.models_path, f"v9_ev_{audit_id}.json")
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sauvegardé : v9_ev_{audit_id}.json")
        except Exception as e:
            self.logger.warning(f"Sauvegarde V9 : {e}")