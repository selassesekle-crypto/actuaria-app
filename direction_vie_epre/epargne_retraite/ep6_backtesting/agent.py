"""
ActuarIA — Agent EP6 : Théodore — Backtesting Hypothèses EP-RE
Direction Vie & EP-RE | Manager : Olivier | Directeur : Paul

Backtesting des hypothèses actuarielles EP-RE N-1 vs réalité N :
→ Comparaison hypothèses vs observations pour chaque paramètre
→ Calcul des écarts d'expérience (mortalité, rotation, revalorisation, taux)
→ Ajustement actuariel recommandé par paramètre
→ Impact sur la DBO des écarts non anticipés
→ Validation des hypothèses selon les standards IAS 19 / SII
"""

import numpy as np, logging, os, json
from direction_vie_epre.services.rapport_excel import (
    creer_workbook_actuariel, ajouter_onglet_hypotheses,
    ajouter_onglet_resultats, ajouter_onglet_validation,
    ajouter_onglet_audit_trail, finaliser_et_retourner,
)
from datetime import datetime
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | actuaria.ep6 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

print("Agent EP6 — Backtesting Hypothèses EP-RE ActuarIA v1.0")
print("Écarts d'expérience : mortalité · rotation · revalo · taux actu")
print("Usage : agent_ep6 = AgentEP6Backtesting()")
print("        result_ep6 = agent_ep6.run(hypotheses_n1={...}, observations_n={...})")


class AgentEP6Backtesting:
    """
    Agent EP6 — Théodore : Backtesting hypothèses actuarielles EP-RE.

    CONTEXTE IAS 19 / SII :
    ────────────────────────
    IAS 19.145 exige que l'actuaire analyse les gains et pertes
    actuariels de l'exercice. Ces gains/pertes résultent de l'écart
    entre les hypothèses retenues N-1 et les observations réelles de N.

    PARAMÈTRES ANALYSÉS :
    ─────────────────────
    1. Taux de mortalité (qx)
    2. Taux de rotation (turnover)
    3. Taux de revalorisation des salaires
    4. Taux d'actualisation (OAT iBoxx AA)
    5. Taux de rendement des actifs (si régime externalisé)

    ÉCART D'EXPÉRIENCE :
    ────────────────────
    Pour chaque paramètre p :
        Écart_p = Hypothèse_N1 - Observation_N
        Impact_DBO_p ≈ DBO × sensibilité_p × Écart_p

    Si Écart_p > 0 → hypothèse N-1 plus prudente → gain actuariel → DBO baisse
    Si Écart_p < 0 → hypothèse N-1 trop optimiste → perte actuarielle → DBO monte
    """

    def __init__(self, models_path='/tmp/actuaria/models',
                 audit_path='/tmp/actuaria/audit', verbose=True):
        self.models_path = models_path
        self.audit_path  = audit_path
        self.verbose     = verbose
        self.logger      = logging.getLogger('actuaria.ep6')
        os.makedirs(models_path, exist_ok=True)
        os.makedirs(audit_path, exist_ok=True)

    def run(
        self,
        hypotheses_n1: Optional[Dict] = None,
        observations_n: Optional[Dict] = None,
        dbo_debut_n: float = 10_000_000,
        effectifs: Optional[list] = None,
        # Optionnel — liste de participants pour sensibilités IAS 19 individuelles.
        # Chaque élément : {'age': int, 'age_retraite': int, 'poids_dbo': float}
        # poids_dbo = part de la DBO totale portée par ce participant (0 à 1).
        # Si absent : sensibilités fixes par bp (comportement originel).
        result_ep1: Optional[Dict] = None,
        generer_graphiques: bool = True,
    ) -> Dict:
        """
        Compare les hypothèses N-1 aux observations réelles de N.

        Paramètres
        ──────────
        hypotheses_n1 : dict
            Hypothèses retenues en début d'exercice N (= fin N-1).
            Clés : {
                'taux_mortalite'    : float  — taux de mortalité supposé
                'taux_rotation'     : float  — turnover supposé
                'taux_revalorisation': float — revalorisation salaires supposée
                'taux_actu'         : float  — taux actualisation OAT iBoxx AA
                'taux_rendement'    : float  — rendement actifs supposé (si ext.)
            }

        observations_n : dict
            Valeurs réellement observées en fin d'exercice N.
            Mêmes clés que hypotheses_n1.

        dbo_debut_n : float
            DBO en début d'exercice N (pour calculer l'impact des écarts).
            Alimenté depuis result_ep1 si disponible.

        result_ep1 : dict, optional
            Résultat EP1 — alimente dbo_debut_n.
        """
        audit_id = f"EP6_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger = self.logger
        if self.verbose:
            logger.info(f"[{audit_id}] Agent EP6 démarré | DBO début N = {dbo_debut_n/1e6:.1f}M€")

        try:
            # ── Alimentation depuis EP1 ───────────────────────────────────────
            sources = {}
            if result_ep1 and result_ep1.get('success'):
                dbo_debut_n = result_ep1.get('ias19', {}).get('dbo_total', dbo_debut_n)
                sources['dbo_debut_n'] = 'EP1 Henri (ias19.dbo_total)'
                logger.info(f"[{audit_id}] DBO alimentée depuis EP1 : {dbo_debut_n/1e6:.1f}M€")

            # Hypothèses par défaut si non fournies
            if not hypotheses_n1:
                hypotheses_n1 = {
                    'taux_mortalite':     0.005,
                    'taux_rotation':      0.050,
                    'taux_revalorisation':0.020,
                    'taux_actu':          0.035,
                    'taux_rendement':     0.040,
                }
            if not observations_n:
                observations_n = {
                    'taux_mortalite':     0.0055,
                    'taux_rotation':      0.060,
                    'taux_revalorisation':0.025,
                    'taux_actu':          0.030,
                    'taux_rendement':     0.035,
                }

            # ── SENSIBILITÉS PAR PARAMÈTRE ────────────────────────────────────
            # Si effectifs fournis : sensibilité au taux d'actualisation calculée
            # individuellement via la duration modifiée de chaque participant.
            # d_i = (age_retraite_i - age_i) / (1 + taux_actu) [IAS 19 §83]
            # Sensibilité globale = Σ poids_dbo_i × d_i × 10_000 (en bp)
            taux_actu_courant = hypotheses_n1.get('taux_actu', 0.035)
            if effectifs and len(effectifs) > 0:
                sensib_taux_actu = 0.0
                for p in effectifs:
                    age_i         = p.get('age', 45)
                    age_retraite_i= p.get('age_retraite', 65)
                    poids_i       = p.get('poids_dbo', 1.0 / len(effectifs))
                    d_i           = (age_retraite_i - age_i) / max(1 + taux_actu_courant, 0.01)
                    sensib_taux_actu += poids_i * d_i * 10_000  # en bp
                # Signe négatif : hausse taux → DBO baisse
                sensib_taux_actu = -sensib_taux_actu
                source_sensib = 'Durée individuelle IAS 19 (effectifs fournis)'
                logger.info(f"[{audit_id}] Sensibilité taux (individuelle) = {sensib_taux_actu:.1f} bp/bp")
            else:
                sensib_taux_actu = -25.0  # valeur fixe par défaut
                source_sensib = 'Sensibilité fixe par défaut (fournir effectifs pour la version individuelle)'

            # ── Sensibilités mortalité et rotation ───────────────────────
            # Si effectifs fournis : calculées individuellement via durée résiduelle
            # Sensib. mortalité : Δ DBO / Δ qx ≈ -DBO × durée_résiduelle (IAS 19.145)
            # Un décès avant retraite = droits perdus → DBO baisse
            # Sensib. rotation : même logique (départ = droits non acquis pour Art. 39)
            if effectifs and len(effectifs) > 0:
                # Durée résiduelle pondérée = Σ poids_i × (age_retraite_i - age_i)
                duree_res_ponderee = sum(
                    p.get('poids_dbo', 1.0 / len(effectifs))
                    * max(p.get('age_retraite', 65) - p.get('age', 45), 0)
                    for p in effectifs
                )
                # Sensibilité mortalité = -durée_résiduelle_pondérée (en bp/bp)
                # (chaque bp de qx supplémentaire = durée_res bp de DBO en moins)
                sensib_mortalite = -duree_res_ponderee
                # Sensibilité rotation = même approximation
                # (un départ = même perte de droits futurs qu'un décès)
                sensib_rotation  = -duree_res_ponderee * 0.6
                # Facteur 0.6 : la rotation impacte moins que le décès car
                # les droits acquis passés restent dus (vesting partiel Art. 39)

                # Sensibilité revalorisation salariale — calcul individuel
                # IAS 19.145 : la DBO est fonction du salaire FINAL projeté.
                # Chaque bp de revalorisation supplémentaire augmente ce salaire
                # proportionnellement à la durée résiduelle de l'assuré.
                # Sensibilité_i = poids_i × (age_retraite_i - age_i)
                # Sensibilité globale = Σ sensibilité_i (en bp/bp, signe positif)
                # Un portefeuille jeune (duree_res élevée) est plus sensible
                # qu'un portefeuille en run-off (duree_res faible)
                sensib_revalorisation = duree_res_ponderee  # toujours positif
                source_sensib_rev = 'Durée résiduelle individuelle pondérée (effectifs fournis)'
                logger.info(
                    f"[{audit_id}] Sensibilités individuelles — "
                    f"mortalité={sensib_mortalite:.1f}bp/bp | "
                    f"rotation={sensib_rotation:.1f}bp/bp | "
                    f"revalorisation={sensib_revalorisation:.1f}bp/bp | "
                    f"durée résiduelle pondérée={duree_res_ponderee:.1f} ans"
                )
                source_sensib_mr = 'Durée résiduelle individuelle pondérée (effectifs fournis)'
            else:
                sensib_mortalite      = -5.0   # valeur fixe : durée résiduelle ~5 ans implicite
                sensib_rotation       = -8.0   # valeur fixe par défaut
                sensib_revalorisation = 15.0   # valeur fixe : durée résiduelle ~15 ans implicite
                source_sensib_rev     = 'Sensibilité fixe par défaut (fournir effectifs pour calcul individuel)'
                source_sensib_mr      = 'Sensibilités fixes par défaut (fournir effectifs pour calcul individuel)'

            sensibilites = {
                'taux_mortalite':      sensib_mortalite,       # calculée ou fixe
                'taux_rotation':       sensib_rotation,        # calculée ou fixe
                'taux_revalorisation': sensib_revalorisation,  # calculée ou fixe (IAS 19.145)
                'taux_actu':           sensib_taux_actu,       # calculée ou fixe
                'taux_rendement':       0.0,
            }

            labels_param = {
                'taux_mortalite':     'Taux de mortalité',
                'taux_rotation':      'Taux de rotation',
                'taux_revalorisation':'Taux de revalorisation salariale',
                'taux_actu':          "Taux d'actualisation OAT iBoxx AA",
                'taux_rendement':     'Rendement actifs (si externalisé)',
            }

            # ── CALCUL DES ÉCARTS D'EXPÉRIENCE ───────────────────────────────
            ecarts = {}
            impact_total_dbo = 0.0
            gain_actuariel   = 0.0
            perte_actuarielle = 0.0

            for param, hyp in hypotheses_n1.items():
                obs = observations_n.get(param, hyp)
                ecart_abs = hyp - obs               # positif = hyp prudente
                ecart_bps = ecart_abs * 10_000      # en points de base

                sensib = sensibilites.get(param, 0)
                # Impact sur DBO = DBO × sensibilité_par_bp × écart_bps
                impact_dbo = dbo_debut_n * (sensib / 10_000) * ecart_bps

                statut = (
                    'VERT'  if abs(ecart_abs / max(hyp, 0.001)) <= 0.10
                    else 'AMBRE' if abs(ecart_abs / max(hyp, 0.001)) <= 0.25
                    else 'ROUGE'
                )

                nature = 'GAIN' if impact_dbo > 0 else 'PERTE' if impact_dbo < 0 else 'NEUTRE'

                ecarts[param] = {
                    'label':           labels_param.get(param, param),
                    'hypothese_n1':    round(hyp, 6),
                    'observation_n':   round(obs, 6),
                    'ecart_abs':       round(ecart_abs, 6),
                    'ecart_pct':       round(ecart_abs / max(abs(hyp), 0.001) * 100, 2),
                    'impact_dbo':      round(impact_dbo, 0),
                    'nature':          nature,
                    'statut':          statut,
                    'recommandation':  self._recommander(param, hyp, obs, ecart_abs),
                }

                impact_total_dbo += impact_dbo
                if impact_dbo > 0:
                    gain_actuariel    += impact_dbo
                else:
                    perte_actuarielle += impact_dbo

            # ── DBO RÉESTIMÉE ─────────────────────────────────────────────────
            dbo_reestimee = dbo_debut_n - impact_total_dbo
            # Note : l'impact est retranché car un gain actuariel (impact > 0)
            # signifie que la DBO réelle est plus basse que prévue

            # ── STATUT GLOBAL ─────────────────────────────────────────────────
            nb_rouge = sum(1 for e in ecarts.values() if e['statut'] == 'ROUGE')
            nb_ambre = sum(1 for e in ecarts.values() if e['statut'] == 'AMBRE')
            statut_rag = 'ROUGE' if nb_rouge >= 2 else 'AMBRE' if nb_rouge >= 1 or nb_ambre >= 2 else 'VERT'

            impact_pct = impact_total_dbo / max(dbo_debut_n, 1) * 100

            commentaire = (
                f"{'✅' if statut_rag == 'VERT' else '⚠️' if statut_rag == 'AMBRE' else '❌'} "
                f"Backtesting EP-RE — DBO début N : {dbo_debut_n/1e6:.2f}M€.\n"
                f"Gains actuariels : +{gain_actuariel/1e3:.0f}k€ | "
                f"Pertes actuarielles : {perte_actuarielle/1e3:.0f}k€.\n"
                f"Impact net sur DBO : {impact_total_dbo:+,.0f}€ ({impact_pct:+.1f}%).\n"
                f"DBO réestimée fin N : {dbo_reestimee/1e6:.2f}M€.\n"
                f"Paramètres ROUGE : {nb_rouge} | AMBRE : {nb_ambre} | "
                f"VERT : {len(ecarts)-nb_rouge-nb_ambre}."
            )

            val_hyp = self._valider_backtesting(
                ecarts, impact_total_dbo, dbo_debut_n,
                gain_actuariel, perte_actuarielle
            )
            graphiques = {}
            gv = {}
            if generer_graphiques:
                graphiques = self._generer_graphiques(ecarts, dbo_debut_n,
                                                       impact_total_dbo, dbo_reestimee)
                gv = self._graphiques_validation_bt(val_hyp, ecarts)

            self._sauvegarder({
                'agent': 'EP6 Théodore', 'dbo_debut_n': dbo_debut_n,
                'impact_total': impact_total_dbo, 'dbo_reestimee': dbo_reestimee,
            }, audit_id)

            # ── Rapport Excel individuel ─────────────────────────────
            _result_for_excel = {
                'audit_id': audit_id,
                'agent': 'EP6',
                'statut_rag': statut_rag if 'statut_rag' in dir() else 'VERT',
                'commentaire': commentaire if 'commentaire' in dir() else '',
                'sources': {'parametres': 'saisie manuelle'},
            }
            # Enrichir avec les variables numériques disponibles
            for _k, _v in list(locals().items()):
                if isinstance(_v, (int, float)) and not _k.startswith('_'):
                    _result_for_excel[_k] = _v
            _excel_bytes_tmp = None
            try:
                _excel_bytes_tmp = self._generer_excel(_result_for_excel)
            except Exception as _xe:
                pass
            return {
                'success':            True,
                'agent':              'EP6 Théodore',
                'statut_rag':         statut_rag,
                'dbo_debut_n':        round(dbo_debut_n, 0),
                'dbo_reestimee':      round(dbo_reestimee, 0),
                'impact_total_dbo':   round(impact_total_dbo, 0),
                'impact_pct':         round(impact_pct, 2),
                'gain_actuariel':     round(gain_actuariel, 0),
                'perte_actuarielle':  round(perte_actuarielle, 0),
                'ecarts':             ecarts,
                'source_sensibilites':   source_sensib,
                'source_sensibilites_mr':source_sensib_mr,
                'source_sensibilites_rev':source_sensib_rev,
                'sources':            sources,
                'commentaire':        commentaire,
                'audit_id':           audit_id,
                'graphiques':         graphiques,
                'validation_bt':      val_hyp,
                'graphiques_validation': gv,
                'erreur':             None,
                'excel_bytes':        _excel_bytes_tmp,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR EP6 : {e}", exc_info=True)
            return {'success': False, 'statut_rag': 'ROUGE',
                    'erreur': str(e), 'audit_id': audit_id}

    def _recommander(self, param, hyp, obs, ecart) -> str:
        """Recommandation d'ajustement pour chaque paramètre."""
        ratio = ecart / max(abs(hyp), 0.001)
        if abs(ratio) <= 0.10:
            return f"Hypothèse confirmée — maintenir {hyp*100:.2f}% pour N+1"
        direction = "augmenter" if ecart < 0 else "réduire"
        return (
            f"Écart {ecart*100:+.2f}pp — {direction} l'hypothèse vers "
            f"{obs*100:.2f}% pour N+1 (obs réelle)"
        )

    # ─── VALIDATION ──────────────────────────────────────────────────────────
    def _valider_backtesting(self, ecarts, impact_total, dbo, gains, pertes) -> Dict:
        """
        V1 — Aucun paramètre ROUGE (écart > 25%)
        V2 — Impact total sur DBO < 5% (surprises limitées)
        V3 — Gains ≥ pertes (hypothèses globalement prudentes)
        """
        nb_rouge = sum(1 for e in ecarts.values() if e['statut'] == 'ROUGE')
        if nb_rouge == 0:
            v1_s = 'VERT'
            v1_m = "Aucun paramètre en écart > 25% ✅"
            v1_c = "Hypothèses de bonne qualité — processus actuariel fiable"
        elif nb_rouge == 1:
            param_rouge = [e['label'] for e in ecarts.values() if e['statut'] == 'ROUGE'][0]
            v1_s = 'AMBRE'
            v1_m = f"1 paramètre en écart > 25% : {param_rouge[:30]} ⚠️"
            v1_c = "Réviser cet unique paramètre pour N+1"
        else:
            v1_s = 'ROUGE'
            v1_m = f"{nb_rouge} paramètres en écart > 25% ❌"
            v1_c = "Révision globale des hypothèses requise — comité actuariel"

        impact_pct = abs(impact_total) / max(dbo, 1) * 100
        if impact_pct <= 2:
            v2_s = 'VERT'
            v2_m = f"Impact DBO = {impact_pct:.1f}% ≤ 2% ✅"
            v2_c = "Surprises actuarielles limitées — modèle fiable"
        elif impact_pct <= 5:
            v2_s = 'AMBRE'
            v2_m = f"Impact DBO = {impact_pct:.1f}% ∈ [2%,5%] ⚠️"
            v2_c = "Surprises modérées — affiner les hypothèses principales"
        else:
            v2_s = 'ROUGE'
            v2_m = f"Impact DBO = {impact_pct:.1f}% > 5% ❌"
            v2_c = "Surprises significatives — revoir toutes les hypothèses"

        if gains >= abs(pertes) or abs(pertes) == 0:
            v3_s = 'VERT'
            v3_m = f"Gains ({gains/1e3:.0f}k€) ≥ Pertes ({abs(pertes)/1e3:.0f}k€) ✅"
            v3_c = "Hypothèses globalement prudentes — conforme à la doctrine IAS 19"
        else:
            v3_s = 'AMBRE'
            v3_m = f"Pertes ({abs(pertes)/1e3:.0f}k€) > Gains ({gains/1e3:.0f}k€) ⚠️"
            v3_c = "Hypothèses trop optimistes — renforcer la prudence pour N+1"

        sts = [v1_s, v2_s, v3_s]
        sg = 'ROUGE' if 'ROUGE' in sts else 'AMBRE' if 'AMBRE' in sts else 'VERT'
        return {
            'v1_nb_rouge':    {'nb': nb_rouge, 'statut': v1_s, 'message': v1_m, 'conseil': v1_c,
                               'titre_graphique': f"{'✅' if v1_s=='VERT' else '⚠️' if v1_s=='AMBRE' else '❌'} {nb_rouge} paramètre(s) ROUGE"},
            'v2_impact_dbo':  {'impact_pct': round(impact_pct, 2), 'statut': v2_s,
                               'message': v2_m, 'conseil': v2_c,
                               'titre_graphique': f"{'✅' if v2_s=='VERT' else '⚠️' if v2_s=='AMBRE' else '❌'} Impact DBO = {impact_pct:.1f}%"},
            'v3_prudence':    {'gains': round(gains, 0), 'pertes': round(pertes, 0),
                               'statut': v3_s, 'message': v3_m, 'conseil': v3_c,
                               'titre_graphique': f"{'✅' if v3_s=='VERT' else '⚠️'} Gains vs pertes actuariels"},
            'statut_global': sg,
            'conclusion': {
                'VERT':  '✅ Backtesting validé — hypothèses fiables et prudentes',
                'AMBRE': '⚠️ Backtesting acceptable — affiner les paramètres signalés',
                'ROUGE': '❌ Hypothèses insuffisantes — révision actuarielle requise',
            }[sg],
        }

    # ─── GRAPHIQUES ──────────────────────────────────────────────────────────
    def _generer_graphiques(self, ecarts, dbo0, impact_total, dbo_new) -> Dict:
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

        # G1 — Impact DBO par paramètre (gains/pertes)
        try:
            labels  = [e['label'][:22] for e in ecarts.values()]
            impacts = [e['impact_dbo'] / 1e3 for e in ecarts.values()]
            colors  = [VERT if i > 0 else ROUGE if i < 0 else AMBRE for i in impacts]
            fig1 = go.Figure(go.Bar(
                x=labels, y=impacts, marker_color=colors, opacity=0.88, width=0.5,
                text=[f"{i:+.0f}k€" for i in impacts],
                textposition='outside', textfont=dict(color=BLANC, size=9),
                hovertemplate="<b>%{x}</b><br>Impact DBO : %{y:+.0f}k€<extra></extra>",
            ))
            fig1.add_hline(y=0, line_color=BLANC, line_width=1.5, line_dash='dot')
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(text="Impact sur DBO par paramètre (gains/pertes actuariels)",
                           font=dict(color=BLANC, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title='Impact (k€)', tickfont=dict(color=GRIS),
                           showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                showlegend=False,
                annotations=[dict(
                    text="💡 Vert = gain actuariel (DBO moins élevée que prévu). Rouge = perte (DBO plus élevée).",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig1.update_layout(**l1)
            graphiques['impact_dbo_parametres'] = fig1
        except Exception:
            pass

        # G2 — Hypothèses N-1 vs Observations N (en %)
        try:
            params_affichables = [k for k in ecarts if k != 'taux_rendement']
            hyps = [ecarts[k]['hypothese_n1'] * 100 for k in params_affichables]
            obs  = [ecarts[k]['observation_n'] * 100 for k in params_affichables]
            lbls = [ecarts[k]['label'][:18] for k in params_affichables]

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=lbls, y=hyps, name='Hypothèse N-1',
                marker_color=OR, opacity=0.88, width=0.35,
                text=[f"{h:.2f}%" for h in hyps],
                textposition='outside', textfont=dict(color=BLANC, size=8)))
            fig2.add_trace(go.Bar(x=lbls, y=obs, name='Observation N',
                marker_color=BLEU, opacity=0.88, width=0.35,
                text=[f"{o:.2f}%" for o in obs],
                textposition='outside', textfont=dict(color=BLANC, size=8)))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text="Hypothèses N-1 vs Observations réelles N (%)",
                           font=dict(color=BLANC, size=11), x=0.01),
                barmode='group', bargap=0.2, bargroupgap=0.05,
                legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color=BLANC, size=10),
                            orientation='h', yanchor='bottom', y=1.0),
                xaxis=dict(tickfont=dict(color=BLANC, size=9)),
                yaxis=dict(title='%', tickfont=dict(color=GRIS)),
                annotations=[dict(
                    text="💡 Doré = ce qu'on avait supposé. Bleu = ce qui s'est passé. Écarts = gains/pertes actuariels.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig2.update_layout(**l2)
            graphiques['hyp_vs_obs'] = fig2
        except Exception:
            pass

        # G3 — DBO avant et après prise en compte des écarts
        try:
            c3 = VERT if dbo_new < dbo0 else ROUGE
            fig3 = go.Figure(go.Waterfall(
                orientation='v',
                measure=['absolute', 'relative', 'total'],
                x=['DBO début N', 'Écarts\nd\'expérience', 'DBO fin N\n(réestimée)'],
                y=[dbo0 / 1e6, -impact_total / 1e6, 0],
                text=[f'{dbo0/1e6:.2f}M€',
                      f'{-impact_total/1e6:+.2f}M€',
                      f'{dbo_new/1e6:.2f}M€'],
                textposition='outside', textfont=dict(color=BLANC, size=10),
                connector=dict(line=dict(color=GRIS, width=1.5)),
                increasing=dict(marker=dict(color=ROUGE, opacity=0.85)),
                decreasing=dict(marker=dict(color=VERT, opacity=0.85)),
                totals=dict(marker=dict(color=c3, opacity=0.9)),
            ))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text="Réconciliation DBO — Effet des écarts d'expérience",
                           font=dict(color=BLANC, size=11), x=0.01),
                yaxis=dict(title='M€', tickfont=dict(color=GRIS)),
                showlegend=False,
                annotations=[dict(
                    text="💡 Vert = les hypothèses étaient prudentes → DBO réelle plus basse. Rouge = inverse.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig3.update_layout(**l3)
            graphiques['waterfall_dbo'] = fig3
        except Exception:
            pass

        # G4 — Statuts par paramètre (scorecard)
        try:
            items = [(e['label'][:25], e['statut']) for e in ecarts.values()]
            fig4 = go.Figure()
            for label, statut in items:
                c = VERT if statut == 'VERT' else AMBRE if statut == 'AMBRE' else ROUGE
                i = '✅' if statut == 'VERT' else '⚠️' if statut == 'AMBRE' else '❌'
                s = 1.0 if statut == 'VERT' else 0.5 if statut == 'AMBRE' else 0.0
                fig4.add_trace(go.Bar(x=[s], y=[label], orientation='h',
                    marker_color=c, width=0.5, text=f"{i} {statut}",
                    textposition='outside', textfont=dict(color=c, size=9),
                    showlegend=False))
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(text="Statut backtesting par paramètre",
                           font=dict(color=BLANC, size=11), x=0.01),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                barmode='overlay', height=280,
                annotations=[dict(
                    text="💡 Vert = écart ≤ 10% (bonne hypothèse). Orange = 10-25%. Rouge > 25% (à réviser).",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)]))
            fig4.update_layout(**l4)
            graphiques['scorecard_parametres'] = fig4
        except Exception:
            pass

        return graphiques

    def _graphiques_validation_bt(self, val, ecarts) -> Dict:
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}
        NAVY='#0F2E52'; NAVY_L='#1B3A5C'; BLANC='#F0F4F8'; GRIS='#8A9AB0'
        VERT='#2ECC71'; ROUGE='#E74C3C'; AMBRE='#F39C12'
        graphiques = {}
        try:
            items = [
                ('V1 — Paramètres ROUGE ≤ 0', val['v1_nb_rouge']['statut'],
                 val['v1_nb_rouge']['message'], val['v1_nb_rouge']['conseil']),
                ('V2 — Impact DBO ≤ 5%', val['v2_impact_dbo']['statut'],
                 val['v2_impact_dbo']['message'], val['v2_impact_dbo']['conseil']),
                ('V3 — Gains ≥ Pertes', val['v3_prudence']['statut'],
                 val['v3_prudence']['message'], val['v3_prudence']['conseil']),
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
                title=dict(text=f"Scorecard Backtesting — {val['conclusion']}",
                           font=dict(color=cg, size=10), x=0.01),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode='overlay',
                annotations=[dict(
                    text="💡 3 ✅ = backtesting validé, hypothèses défendables devant l'auditeur IAS 19.",
                    xref='paper', yref='paper', x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)])
            graphiques['scorecard_backtesting'] = fig
        except Exception:
            pass
        return graphiques


    def _generer_excel(self, result: dict) -> bytes:
        """Rapport Excel individuel EP6 — 4 onglets auditables."""
        from datetime import datetime
        wb  = creer_workbook_actuariel()
        aid = result.get("audit_id", "N/A")
        dte = datetime.now().strftime("%d/%m/%Y %H:%M")
        hyps = [
            {"label": str(k), "valeur": v, "unite": "",
              "source": result.get("sources", {}).get(str(k), "saisie manuelle"),
              "reference": ""}
            for k, v in result.items()
            if isinstance(v, (int, float, str, bool))
            and k not in ("success", "erreur", "audit_id", "commentaire",
                          "agent", "statut_rag", "be_ifrs17_mode")
        ][:20]
        ajouter_onglet_hypotheses(wb, "EP6", aid, dte, hyps,
                                  sources=result.get("sources", {}))
        lignes = [
            {"label": str(k), "valeur": v,
              "unite": "€" if isinstance(v, float) and v > 100 else "%"
                       if isinstance(v, float) and 0 < v < 1 else "",
              "fmt_excel": "#,##0.00" if isinstance(v, float) else None,
              "commentaire": ""}
            for k, v in result.items()
            if isinstance(v, (int, float))
            and k not in ("success",)
        ][:40]
        ajouter_onglet_resultats(wb, "EP6", aid, dte,
                                 [{"titre": "Résultats actuariels", "lignes": lignes}])
        # Validation : chercher le premier dict de validation dans le result
        for vk in [k for k in result if "validat" in k.lower()]:
            val = result.get(vk, {})
            if isinstance(val, dict) and "statut_global" in val:
                cles = [k for k in val if isinstance(val[k], dict)
                        and "statut" in val[k] and "message" in val[k]]
                if cles:
                    ajouter_onglet_validation(wb, "EP6", aid, dte, val,
                                              cles_controles=cles[:5])
                break
        ajouter_onglet_audit_trail(wb, "EP6", aid, dte, result)
        return finaliser_et_retourner(wb)

    def _sauvegarder(self, rapport, audit_id):
        try:
            fpath = os.path.join(self.models_path, f"ep6_bt_{audit_id}.json")
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sauvegardé : ep6_bt_{audit_id}.json")
        except Exception as e:
            self.logger.warning(f"Sauvegarde EP6 : {e}")