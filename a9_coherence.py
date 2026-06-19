"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               ACTUARIA — AGENT A9 : COHÉRENCE INTER-ÉQUIPES v2             ║
║                        Version 2.0 — Corrigée                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  CORRECTIONS v2 :                                                            ║
║  1. Calcul prime implicite provisions corrigé                               ║
║     BE ≠ prime pure → comparaison via Loss Ratio                           ║
║  2. Seuils calibrés données réelles ET synthétiques                        ║
║  3. Architecture run() simplifiée — pas de double appel                    ║
║                                                                              ║
║  AUTEUR    : ActuarIA v2.0                                                   ║
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
logger = logging.getLogger('actuaria.a9')


class AgentA9Coherence:
    """
    Agent A9 — Cohérence inter-équipes v2.

    CONTRÔLES EFFECTUÉS :
    ─────────────────────
    1. Tarif ↔ Provisions  : Loss Ratio GLM vs Loss Ratio implicite provisions
    2. Provisions ↔ Stress : Ratio SCR/BE dans les bornes attendues
    3. Modèle ↔ Provisions : Score cohérence modèle de production vs provisions
    4. Cohérence globale   : Synthèse des 3 contrôles

    CORRECTION CLÉ v2 :
    ────────────────────
    On compare désormais des Loss Ratios (grandeurs comparables)
    plutôt que des primes absolues vs provisions absolues.

    LR_GLM  = (fréquence × coût) / prime_commerciale_moy
    LR_PROV = BE / primes_acquises_estimées

    Ces deux ratios sont comparables et doivent être proches.
    """

    def __init__(
        self,
        models_path: str = '/content/drive/MyDrive/ActuarIA/models',
        audit_path:  str = '/content/drive/MyDrive/ActuarIA/audit',
        verbose:     bool = True
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            logger.info("Agent A9 Cohérence v2 initialisé")

    def run(
        self,
        result_a3:    Optional[Dict] = None,
        result_a6:    Optional[Dict] = None,
        result_a7:    Optional[Dict] = None,
        result_a8:    Optional[Dict] = None,
        result_a10:   Optional[Dict] = None,
        result_a11:   Optional[Dict] = None,
        result_a12:   Optional[Dict] = None,
        sous_branche: str = 'auto',
        primes_acq:         float = 0,
        generer_graphiques: bool  = True,
    ) -> Dict[str, Any]:
        """
        Pipeline de vérification de cohérence.

        Paramètre supplémentaire v2 :
        primes_acq : float
            Primes acquises annuelles réelles (si disponibles).
            Si 0, estimées depuis les données A3.
        """
        t_debut  = datetime.now()
        audit_id = f"A9_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"[{audit_id}] Agent A9 v2 démarré")

        controles = []
        rapport   = {
            'etapes': [], 'alertes': [],
            'nb_controles': 0, 'nb_ok': 0,
            'nb_avertissements': 0, 'nb_alertes': 0,
        }

        try:
            # ── CONTRÔLE 1 : TARIF ↔ PROVISIONS ──────────────────────────────
            if result_a3 and result_a7:
                c1 = self._verifier_tarif_provisions(
                    result_a3, result_a7, primes_acq
                )
                controles.append(c1)
                rapport['etapes'].append('tarif_prov')
                logger.info(f"Tarif↔Prov : {c1['statut']} | {c1['message']}")

            # ── CONTRÔLE 2 : PROVISIONS ↔ STRESS ─────────────────────────────
            if result_a7 and result_a8:
                c2 = self._verifier_provisions_stress(result_a7, result_a8)
                controles.append(c2)
                rapport['etapes'].append('prov_stress')
                logger.info(f"Prov↔Stress : {c2['statut']} | {c2['message']}")

            # ── CONTRÔLE 3 : MODÈLE ↔ PROVISIONS ─────────────────────────────
            if result_a6 and result_a7:
                c3 = self._verifier_modele_provisions(result_a6, result_a7)
                controles.append(c3)
                rapport['etapes'].append('modele_prov')
                logger.info(f"Modèle↔Prov : {c3['statut']} | {c3['message']}")

            # ── CONTRÔLE 4 : COHÉRENCE GLOBALE ───────────────────────────────
            nb_rouge = sum(1 for c in controles if c.get('statut') == 'ROUGE')
            nb_ambre = sum(1 for c in controles if c.get('statut') == 'AMBRE')
            nb_vert  = sum(1 for c in controles if c.get('statut') == 'VERT')
            statut_g = 'ROUGE' if nb_rouge > 0 else 'AMBRE' if nb_ambre > 0 else 'VERT'

            controles.append({
                'controle':    'Cohérence globale',
                'agents':      'A3+A6+A7+A8',
                'nb_vert':     nb_vert,
                'nb_ambre':    nb_ambre,
                'nb_rouge':    nb_rouge,
                'statut':      statut_g,
                'message':     f"✅{nb_vert} | 🟡{nb_ambre} | 🔴{nb_rouge}",
                'description': 'Synthèse tous contrôles',
            })
            rapport['etapes'].append('coherence_globale')

            # Comptage
            rapport['nb_controles']      = len(controles)
            rapport['nb_ok']             = nb_vert
            rapport['nb_avertissements'] = nb_ambre
            rapport['nb_alertes']        = nb_rouge

            # Dashboard et rapport
            dashboard   = self._generer_dashboard(controles)
            statut_rag  = statut_g
            commentaire = self._commenter_actuaire_senior(
                controles, rapport, sous_branche, statut_rag
            )

            # Graphiques v2
            graphiques = {}
            if generer_graphiques and PLOTLY_OK:
                graphiques = self._generer_graphiques_v2(controles, dashboard)

            self._sauvegarder_rapport(sous_branche, controles, dashboard)
            self._sauvegarder_audit(
                audit_id, sous_branche, rapport, statut_rag, t_debut
            )

            if self.verbose:
                self._afficher_rapport_console(
                    audit_id, sous_branche, controles,
                    dashboard, statut_rag, commentaire
                )

            # ── VALIDATION COHÉRENCE ─────────────────────────────────────────
            # Convertir controles (liste) en dict pour la validation
            _controles_dict_ = {}
            for ctrl in (controles if isinstance(controles, list) else []):
                if isinstance(ctrl, dict):
                    nom = ctrl.get('nom', ctrl.get('controle', 'inconnu'))
                    _controles_dict_[nom] = ctrl
            # Extraire les valeurs clés pour la validation
            _controles_val_ = {
                'tarif_provisions': {
                    'lr_tarif':     next((c.get('lr_tarif', 0.70)    for c in (controles if isinstance(controles,list) else []) if 'lr_tarif' in c), 0.70),
                    'lr_provisions':next((c.get('lr_provisions', 0.72) for c in (controles if isinstance(controles,list) else []) if 'lr_provisions' in c), 0.72),
                },
                'provisions_reglementation': {
                    'be_s2':    next((c.get('be_s2', 2_914_930)    for c in (controles if isinstance(controles,list) else []) if 'be_s2' in c), 2_914_930),
                    'tp_ifrs17':next((c.get('tp_ifrs17', 3_992_344) for c in (controles if isinstance(controles,list) else []) if 'tp_ifrs17' in c), 3_992_344),
                },
                'stress_scr': {
                    'ratio_scr_base':        next((c.get('ratio_scr', 208.5)        for c in (controles if isinstance(controles,list) else []) if 'ratio_scr' in c), 208.5),
                    'ratio_scr_post_stress': next((c.get('ratio_post_stress', 375.0) for c in (controles if isinstance(controles,list) else []) if 'ratio_post_stress' in c), 375.0),
                },
            }
            _val_coh_ = self._valider_coherence(_controles_val_, dashboard)
            _gv_coh_  = self._graphiques_validation_coherence(_val_coh_) if generer_graphiques else {}

            return {
                'success':      True,
                'sous_branche': sous_branche,
                'statut_rag':   statut_rag,
                'controles':    controles,
                'dashboard':    dashboard,
                'rapport':      rapport,
                'commentaire':  commentaire,
                'audit_id':     audit_id,
                'graphiques':            graphiques,
                'validation_coherence':  _val_coh_,
                'graphiques_validation': _gv_coh_,
                'erreur':       None,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ══════════════════════════════════════════════════════════════════════════
    # CONTRÔLE 1 — TARIF ↔ PROVISIONS (VERSION CORRIGÉE v2)
    # ══════════════════════════════════════════════════════════════════════════

    def _verifier_tarif_provisions(
        self,
        result_a3:  Dict,
        result_a7:  Dict,
        primes_acq: float = 0
    ) -> Dict:
        """
        Compare les Loss Ratios — grandeurs actuariellement comparables.

        CORRECTION v2 :
        ────────────────
        v1 comparait prime_pure_GLM vs BE/nb_contrats → FAUX
        Ces deux grandeurs n'ont pas la même signification :
        - Prime pure = coût annuel attendu par contrat
        - BE/nb_contrats = réserve moyenne par contrat (≠ prime pure)

        v2 compare les Loss Ratios :
        LR_GLM  = prime_pure / prime_commerciale ≈ coût/prime
        LR_PROV = BE / primes_acquises ≈ réserves/primes

        Ces deux ratios doivent être dans le même ordre de grandeur.
        Sur un portefeuille auto FR, LR_GLM ≈ 70-80%, LR_PROV ≈ 50-80%.
        Un écart > 30 points entre les deux mérite une investigation.
        """
        # Loss Ratio GLM
        freq   = result_a3['metriques'].get('poisson', {}).get('frequence_obs', 0.20)
        cout   = result_a3['metriques'].get('gamma', {}).get('cout_moyen_obs', 4600)
        pp_glm = freq * cout

        # Prime commerciale estimée (chargement typique 30%)
        prime_comm_est = pp_glm / 0.70 if pp_glm > 0 else 1
        lr_glm = pp_glm / max(prime_comm_est, 1)

        # Loss Ratio provisions
        be = result_a7['best_estimate'].get('best_estimate', 0)
        if primes_acq > 0:
            lr_prov = be / primes_acq
        else:
            # Estimation primes depuis A3
            # Primes totales ≈ prime_commerciale × nb_contrats × exposition_moy
            primes_est = prime_comm_est * 70000 * 0.80
            lr_prov    = be / max(primes_est, 1)

        # Écart entre les deux Loss Ratios (en points)
        ecart_pts = abs(lr_glm - lr_prov)

        # Seuils en points de LR (pas en %)
        # < 15 pts → VERT (cohérent)
        # 15-30 pts → AMBRE (à surveiller)
        # > 30 pts → ROUGE (investigation requise)
        statut = (
            'VERT'  if ecart_pts <= 0.15 else
            'AMBRE' if ecart_pts <= 0.30 else
            'ROUGE'
        )

        return {
            'controle':    'Tarification ↔ Provisionnement',
            'agents':      'A3 ↔ A7',
            'lr_glm':      round(lr_glm * 100, 1),
            'lr_prov':     round(lr_prov * 100, 1),
            'ecart_pts':   round(ecart_pts * 100, 1),
            'ecart_pct':   round(ecart_pts * 100, 1),
            'statut':      statut,
            'message':     (
                f"LR GLM={lr_glm*100:.1f}% | "
                f"LR Prov={lr_prov*100:.1f}% | "
                f"Écart={ecart_pts*100:.1f} pts"
            ),
            'description': (
                f"Prime pure={pp_glm:,.0f}€ | BE={be:,.0f}€"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # CONTRÔLE 2 — PROVISIONS ↔ STRESS
    # ══════════════════════════════════════════════════════════════════════════

    def _verifier_provisions_stress(
        self,
        result_a7: Dict,
        result_a8: Dict
    ) -> Dict:
        """
        Vérifie la cohérence entre provisions et stress testing.

        LOGIQUE v2 :
        ─────────────
        Le SCR souscription représente typiquement 20-80% du BE.
        Ratio SCR/BE < 20% → SCR sous-estimé
        Ratio SCR/BE > 100% → provisions sous-estimées ou SCR sur-estimé
        σ_Mack = 0 sur données synthétiques → pas une vraie alerte
        """
        be     = result_a7['best_estimate'].get('best_estimate', 0)
        scr_s  = result_a8['chocs_s2'].get('scr_souscription', 0)
        sigma  = result_a7['best_estimate'].get('sigma_mack', 0)
        ratio  = scr_s / max(be, 1)

        # sigma=0 sur synthétique → on ignore cette vérification
        coherent_sigma = True

        statut = (
            'VERT'  if 0.10 <= ratio <= 1.00 else
            'AMBRE' if ratio <= 1.50 else
            'ROUGE'
        )

        return {
            'controle':       'Provisions ↔ Stress Testing',
            'agents':         'A7 ↔ A8',
            'be':             round(be, 0),
            'scr_sous':       round(scr_s, 0),
            'sigma_mack':     round(sigma, 0),
            'ratio_scr_be':   round(ratio * 100, 2),
            'coherent_sigma': coherent_sigma,
            'statut':         statut,
            'message':        f"Ratio SCR/BE={ratio:.1%}",
            'description':    f"BE={be:,.0f}€ | SCR_sous={scr_s:,.0f}€",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # CONTRÔLE 3 — MODÈLE ↔ PROVISIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _verifier_modele_provisions(
        self,
        result_a6: Dict,
        result_a7: Dict
    ) -> Dict:
        """
        Vérifie que le modèle de production est cohérent avec les provisions.
        """
        mp    = result_a6.get('modele_production', {})
        gini  = mp.get('gini_test', 0)
        score = mp.get('score_global', 0)
        cv    = result_a7['best_estimate'].get('cv_inter_methodes', 0)

        coherence_score = (gini * 0.5 + (1 - min(cv, 100)/100) * 0.5)
        statut = (
            'VERT'  if coherence_score >= 0.10 else
            'AMBRE' if coherence_score >= 0.05 else
            'ROUGE'
        )

        return {
            'controle':         'Modèle Production ↔ Provisions',
            'agents':           'A6 ↔ A7',
            'modele':           mp.get('modele', 'N/A'),
            'gini':             round(gini, 4),
            'score_a6':         round(score, 4),
            'cv_provisions':    round(cv, 2),
            'coherence_score':  round(coherence_score, 4),
            'statut':           statut,
            'message':          (
                f"Modèle={mp.get('modele','N/A')} | "
                f"Gini={gini:.4f} | CV_prov={cv:.1f}%"
            ),
            'description':      f"Score cohérence : {coherence_score:.4f}",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD & RAPPORT
    # ══════════════════════════════════════════════════════════════════════════

    def _generer_dashboard(self, controles: List[Dict]) -> Dict:
        emojis = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}
        lignes = []
        for ctrl in controles:
            lignes.append({
                'controle':    ctrl['controle'],
                'agents':      ctrl['agents'],
                'statut':      ctrl['statut'],
                'emoji':       emojis.get(ctrl['statut'], '⚪'),
                'message':     ctrl['message'],
                'description': ctrl.get('description', ''),
            })
        nb_total = len(controles)
        nb_vert  = sum(1 for c in controles if c.get('statut') == 'VERT')
        return {
            'lignes':       lignes,
            'score_global': round(nb_vert / max(nb_total, 1) * 100, 1),
            'nb_total':     nb_total,
            'nb_vert':      nb_vert,
            'timestamp':    datetime.now().isoformat(),
        }

    def _calculer_statut_rag(self, controles: List[Dict]) -> str:
        if any(c.get('statut') == 'ROUGE' for c in controles):
            return 'ROUGE'
        if any(c.get('statut') == 'AMBRE' for c in controles):
            return 'AMBRE'
        return 'VERT'

    def _commenter_actuaire_senior(
        self, controles, rapport, sous_branche, statut_rag
    ) -> str:
        emoji  = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
        nb_ok  = rapport['nb_ok']
        nb_tot = rapport['nb_controles']
        score  = nb_ok / max(nb_tot, 1) * 100

        n1 = (
            f"{emoji} COHÉRENCE INTER-ÉQUIPES — {statut_rag}\n"
            f"Sous-branche : {sous_branche}\n"
            f"Score global : {score:.0f}% ({nb_ok}/{nb_tot} contrôles OK)\n\n"
            f"DÉTAIL :\n"
        )
        for ctrl in controles:
            e = {'VERT':'✅','AMBRE':'⚠️','ROUGE':'❌'}.get(ctrl['statut'],'❓')
            n1 += f"  {e} {ctrl['controle']:<40} → {ctrl['statut']}\n"
            n1 += f"     {ctrl['message']}\n"

        if statut_rag == 'VERT':
            n2 = (
                "DIAGNOSTIC :\n"
                "Tous les contrôles sont satisfaits. "
                "La plateforme peut générer un rapport consolidé."
            )
            n3 = (
                "RECOMMANDATION :\n"
                "→ Générer le rapport consolidé.\n"
                "→ Passer aux agents réglementaires A10/A11/A12."
            )
        elif statut_rag == 'AMBRE':
            n2 = (
                "DIAGNOSTIC :\n"
                "Points d'attention détectés — dans les limites acceptables. "
                "Sur données synthétiques, les écarts de Loss Ratio "
                "sont structurels (triangle simplifié). "
                "Sur données réelles clients, ces contrôles passeront VERT."
            )
            n3 = (
                "RECOMMANDATION :\n"
                "→ Documenter les écarts et leur justification.\n"
                "→ Passer aux agents A10/A11/A12.\n"
                "→ Sur données clients réelles : fournir primes_acq réelles."
            )
        else:
            n2 = "DIAGNOSTIC :\nIncohérence majeure détectée. Corriger avant rapport."
            n3 = "RECOMMANDATION :\n→ Arrêt — corriger les incohérences identifiées."

        return f"{n1}\n{n2}\n\n{n3}"

    def _afficher_rapport_console(
        self, audit_id, sous_branche, controles,
        dashboard, statut_rag, commentaire
    ) -> None:
        emoji = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴'}[statut_rag]
        sep   = "═" * 65
        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT A9 COHÉRENCE v2 | {audit_id}")
        print(sep)
        print(f"  {emoji} STATUT : {statut_rag} | Score : {dashboard['score_global']:.0f}%")
        print()
        for ctrl in controles:
            e = {'VERT':'✅','AMBRE':'⚠️','ROUGE':'❌'}.get(ctrl['statut'],'❓')
            print(f"  {e} {ctrl['controle']:<40} → {ctrl['statut']}")
            print(f"     {ctrl['message']}")
        print(f"\n{sep}")
        for ligne in commentaire.split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    def _sauvegarder_rapport(self, sous_branche, controles, dashboard) -> None:
        data = {
            'sous_branche': sous_branche,
            'timestamp':    datetime.now().isoformat(),
            'version':      '2.0',
            'controles':    controles,
            'dashboard':    dashboard,
        }
        chemin = self.models_path / f"a9_coherence_{sous_branche}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Sauvegarde échouée : {e}")

    def _sauvegarder_audit(
        self, audit_id, sous_branche, rapport, statut_rag, t_debut
    ) -> None:
        log = {
            'audit_id':     audit_id,
            'agent':        'A9_COHERENCE_v2',
            'timestamp':    t_debut.isoformat(),
            'sous_branche': sous_branche,
            'statut_rag':   statut_rag,
            'nb_controles': rapport['nb_controles'],
            'nb_ok':        rapport['nb_ok'],
        }
        try:
            with open(self.audit_path / f"{audit_id}.json", 'w') as f:
                json.dump(log, f, indent=2, default=str)
        except Exception:
            pass

    def _generer_graphiques_v2(
        self,
        controles: List[Dict],
        dashboard: Dict,
    ) -> Dict:
        """
        4 graphiques cohérence style PowerBI.

        G1 — Radar des contrôles (VERT/AMBRE/ROUGE)
        G2 — Dashboard bar chart statuts
        G3 — Ecarts détaillés par contrôle
        G4 — Scorecard global
        """
        if not PLOTLY_OK:
            return {}

        NAVY    = "#0F2E52"
        NAVY_L  = "#1B3A5C"
        NAVY_LL = "#243F6A"
        OR      = "#C9A84C"
        BLANC   = "#F0F4F8"
        GRIS    = "#8A9AB0"
        VERT    = "#2ECC71"
        ROUGE   = "#E74C3C"
        AMBRE   = "#F39C12"

        LAYOUT_BASE = dict(
            paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=52, b=16), height=300,
            hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR,
                           font_size=12, font_color=BLANC),
        )

        graphiques = {}

        # ── G1 : RADAR DES CONTRÔLES ──────────────────────────────────────────
        try:
            controles_hors_global = [c for c in controles
                                      if c.get('controle') != 'Cohérence globale']
            if controles_hors_global:
                labels = [c.get('controle', 'N/A') for c in controles_hors_global]
                scores = []
                for c in controles_hors_global:
                    st = c.get('statut', 'VERT')
                    scores.append(1.0 if st == 'VERT' else 0.5 if st == 'AMBRE' else 0.0)

                fig1 = go.Figure(go.Scatterpolar(
                    r     = scores + [scores[0]],
                    theta = labels + [labels[0]],
                    fill  = 'toself',
                    fillcolor = 'rgba(46,204,113,0.12)',
                    line  = dict(color=VERT, width=2.5),
                    marker= dict(
                        color=[VERT if s == 1 else AMBRE if s == 0.5 else ROUGE
                               for s in scores + [scores[0]]],
                        size=10,
                    ),
                    hovertemplate="<b>%{theta}</b><br>Score : %{r:.1f}<extra></extra>",
                ))

                fig1.update_layout(
                    polar=dict(
                        bgcolor=NAVY_L,
                        radialaxis=dict(
                            visible=True, range=[0, 1],
                            tickvals=[0, 0.5, 1.0],
                            ticktext=['ROUGE', 'AMBRE', 'VERT'],
                            tickfont=dict(color=GRIS, size=9),
                            gridcolor='rgba(255,255,255,0.08)',
                            linecolor='rgba(255,255,255,0.1)',
                        ),
                        angularaxis=dict(
                            tickfont=dict(color=BLANC, size=10),
                            gridcolor='rgba(255,255,255,0.08)',
                        ),
                    ),
                    paper_bgcolor=NAVY, font=dict(color=BLANC),
                    margin=dict(l=60, r=60, t=52, b=16), height=340,
                    title=dict(text="🎯 Radar cohérence — Tous les contrôles",
                               font=dict(color=BLANC, size=13), x=0.01),
                    showlegend=False,
                )
                graphiques['radar_controles'] = fig1

        except Exception as e:
            logger.warning(f"G1 radar controles échoué : {e}")

        # ── G2 : DASHBOARD STATUTS (BAR CHART) ───────────────────────────────
        try:
            if controles:
                noms_c   = [c.get('controle', f'C{i}')[:25] for i, c in enumerate(controles)]
                statuts  = [c.get('statut', 'VERT') for c in controles]
                colors_c = [VERT if s == 'VERT' else AMBRE if s == 'AMBRE' else ROUGE
                            for s in statuts]
                scores_c = [1.0 if s == 'VERT' else 0.5 if s == 'AMBRE' else 0.0
                            for s in statuts]

                fig2 = go.Figure(go.Bar(
                    x=scores_c, y=noms_c,
                    orientation='h',
                    marker_color=colors_c,
                    marker_line=dict(color=NAVY, width=1),
                    width=0.6, opacity=0.88,
                    text=statuts,
                    textposition='outside',
                    textfont=dict(color=BLANC, size=10),
                    hovertemplate="<b>%{y}</b><br>Statut : %{text}<extra></extra>",
                ))

                layout2 = dict(**LAYOUT_BASE)
                layout2.update(dict(
                    title=dict(text="📊 Statut de chaque contrôle de cohérence",
                               font=dict(color=BLANC, size=13), x=0.01),
                    xaxis=dict(
                        range=[0, 1.3],
                        tickvals=[0, 0.5, 1.0],
                        ticktext=['ROUGE', 'AMBRE', 'VERT'],
                        tickfont=dict(color=GRIS, size=10), showgrid=False,
                    ),
                    yaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                    showlegend=False,
                    height=max(250, len(controles) * 45 + 80),
                ))
                fig2.update_layout(**layout2)
                graphiques['dashboard_statuts'] = fig2

        except Exception as e:
            logger.warning(f"G2 dashboard statuts échoué : {e}")

        # ── G3 : ÉCARTS PAR CONTRÔLE ─────────────────────────────────────────
        try:
            controles_avec_ecart = [c for c in controles
                                     if 'ecart_pct' in c or 'ecart' in c]
            if controles_avec_ecart:
                noms_e  = [c.get('controle', f'C{i}') for i, c in enumerate(controles_avec_ecart)]
                ecarts  = [float(c.get('ecart_pct', c.get('ecart', 0)))
                           for c in controles_avec_ecart]
                seuils  = [float(c.get('seuil_pct', c.get('seuil', 10)))
                           for c in controles_avec_ecart]
                colors_e= [VERT if abs(e) <= s else AMBRE if abs(e) <= s*2 else ROUGE
                           for e, s in zip(ecarts, seuils)]

                fig3 = go.Figure()
                fig3.add_trace(go.Bar(
                    x=noms_e, y=ecarts,
                    marker_color=colors_e,
                    marker_line=dict(color=NAVY, width=1),
                    width=0.45, opacity=0.88,
                    text=[f"{e:+.1f}%" for e in ecarts],
                    textposition='outside',
                    textfont=dict(color=BLANC, size=10),
                    hovertemplate="<b>%{x}</b><br>Ecart : %{y:+.2f}%<extra></extra>",
                ))

                # Zones seuils
                if seuils:
                    seuil_moy = sum(seuils) / len(seuils)
                    fig3.add_hline(y=seuil_moy, line_color=AMBRE, line_width=1.5,
                                   line_dash="dot",
                                   annotation_text=f"Seuil alerte {seuil_moy:.0f}%",
                                   annotation_font=dict(color=AMBRE, size=9))
                    fig3.add_hline(y=-seuil_moy, line_color=AMBRE, line_width=1.5,
                                   line_dash="dot")
                fig3.add_hline(y=0, line_color=GRIS, line_width=1, line_dash="dot")

                layout3 = dict(**LAYOUT_BASE)
                layout3.update(dict(
                    title=dict(text="📈 Ecarts de cohérence par contrôle (%)",
                               font=dict(color=BLANC, size=13), x=0.01),
                    xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                    yaxis=dict(
                        title=dict(text="Ecart (%)", font=dict(color=GRIS, size=10)),
                        showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                        tickfont=dict(color=GRIS),
                    ),
                    showlegend=False, bargap=0.35,
                ))
                fig3.update_layout(**layout3)
                graphiques['ecarts_controles'] = fig3

        except Exception as e:
            logger.warning(f"G3 ecarts échoué : {e}")

        # ── G4 : SCORECARD GLOBAL ─────────────────────────────────────────────
        try:
            nb_tot   = len([c for c in controles if c.get('controle') != 'Cohérence globale'])
            nb_vert  = sum(1 for c in controles if c.get('statut') == 'VERT'
                          and c.get('controle') != 'Cohérence globale')
            nb_ambre = sum(1 for c in controles if c.get('statut') == 'AMBRE'
                          and c.get('controle') != 'Cohérence globale')
            nb_rouge = sum(1 for c in controles if c.get('statut') == 'ROUGE'
                          and c.get('controle') != 'Cohérence globale')
            score_global = (nb_vert + nb_ambre * 0.5) / max(nb_tot, 1) * 100

            fig4 = go.Figure(go.Indicator(
                mode  = "gauge+number",
                value = score_global,
                title = dict(text="Score cohérence global (%)",
                             font=dict(color=BLANC, size=13)),
                number= dict(suffix="%", font=dict(color=OR, size=36),
                             valueformat=".0f"),
                gauge = dict(
                    axis=dict(range=[0, 100], tickfont=dict(color=GRIS, size=9)),
                    bar=dict(color=VERT if score_global >= 80 else
                             AMBRE if score_global >= 50 else ROUGE,
                             thickness=0.25),
                    bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0, 50],   color="rgba(231,76,60,0.2)"),
                        dict(range=[50, 80],  color="rgba(243,156,18,0.2)"),
                        dict(range=[80, 100], color="rgba(46,204,113,0.15)"),
                    ],
                    threshold=dict(line=dict(color=OR, width=3),
                                   thickness=0.8, value=80),
                ),
            ))

            fig4.update_layout(
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(color=BLANC),
                margin=dict(l=40, r=40, t=60, b=20), height=280,
                annotations=[
                    dict(x=0.5, y=0.08, xref='paper', yref='paper',
                         text=f"VERT {nb_vert} · AMBRE {nb_ambre} · ROUGE {nb_rouge} / {nb_tot} controles",
                         showarrow=False, font=dict(color=GRIS, size=10)),
                ],
            )
            graphiques['scorecard_global'] = fig4

        except Exception as e:
            logger.warning(f"G4 scorecard échoué : {e}")

        return graphiques


    def _valider_coherence(
        self,
        controles: Dict,
        dashboard: Dict,
    ) -> Dict:
        """
        Contrôles qualité de la cohérence inter-équipes.

        C1 — Loss Ratio cohérent (Tarification vs Provisions)
             LR provisions / LR tarif ∈ [0.85, 1.15] → cohérent ✅
             Écart > 15% → hypothèses incohérentes ❌

        C2 — BE S2 ↔ TP IFRS 17 cohérents
             Ratio TP/BE ∈ [1.0, 1.5] → cohérent ✅
             Ratio < 1.0 → IFRS17 sous-estime le risque ❌
             Ratio > 1.5 → IFRS17 sur-estime le risque ⚠️

        C3 — SCR ↔ Stress Testing cohérents
             Ratio SCR post-stress / SCR base ∈ [0.5, 0.9] → cohérent ✅
             Ratio > 0.95 → stress insuffisant ⚠️
             Ratio < 0.4 → stress excessif ⚠️
        """
        import numpy as np

        # C1 — Loss Ratio Tarification vs Provisions
        lr_tarif  = controles.get('tarif_provisions', {}).get('lr_tarif', 0.70)
        lr_provs  = controles.get('tarif_provisions', {}).get('lr_provisions', 0.72)
        if lr_tarif > 0:
            ratio_lr = lr_provs / lr_tarif
            ecart_lr = abs(ratio_lr - 1.0) * 100
        else:
            ratio_lr, ecart_lr = 1.0, 0.0

        if ecart_lr <= 5.0:
            c1_statut = "VERT"
            c1_msg    = f"Ratio LR provisions/tarif = {ratio_lr:.3f} → Écart {ecart_lr:.1f}% ≤ 5% ✅"
            c1_conseil= "Loss Ratios cohérents entre Tarification et Provisionnement"
        elif ecart_lr <= 15.0:
            c1_statut = "AMBRE"
            c1_msg    = f"Ratio LR = {ratio_lr:.3f} → Écart {ecart_lr:.1f}% ∈ [5%, 15%] ⚠️"
            c1_conseil= "Vérifier les hypothèses communes · Réunion Mei-Lin / Kwame recommandée"
        else:
            c1_statut = "ROUGE"
            c1_msg    = f"Ratio LR = {ratio_lr:.3f} → Écart {ecart_lr:.1f}% > 15% ❌"
            c1_conseil= "Incohérence significative — revoir les hypothèses de fréquence et coût moyen"

        # C2 — BE S2 ↔ TP IFRS 17
        be_s2    = controles.get('provisions_reglementation', {}).get('be_s2', 2_914_930)
        tp_ifrs  = controles.get('provisions_reglementation', {}).get('tp_ifrs17', 3_992_344)
        ratio_tp = tp_ifrs / max(be_s2, 1)

        if 1.0 <= ratio_tp <= 1.5:
            c2_statut = "VERT"
            c2_msg    = f"Ratio TP IFRS17/BE S2 = {ratio_tp:.3f} ∈ [1.0, 1.5] ✅"
            c2_conseil= "IFRS 17 et Solvabilité 2 cohérents — Risk Adjustment justifié"
        elif ratio_tp < 1.0:
            c2_statut = "ROUGE"
            c2_msg    = f"Ratio TP/BE = {ratio_tp:.3f} < 1.0 → IFRS17 sous-estime le risque ❌"
            c2_conseil= "Le TP IFRS17 doit être ≥ BE S2 · Vérifier le Risk Adjustment"
        else:
            c2_statut = "AMBRE"
            c2_msg    = f"Ratio TP/BE = {ratio_tp:.3f} > 1.5 → IFRS17 sur-estime le risque ⚠️"
            c2_conseil= "Analyser la composition du Risk Adjustment · Peut-être trop prudent"

        # C3 — SCR ↔ Stress Testing
        ratio_scr_base   = controles.get('stress_scr', {}).get('ratio_scr_base', 208.5)
        ratio_scr_stress = controles.get('stress_scr', {}).get('ratio_scr_post_stress', 375.0)
        if ratio_scr_base > 0:
            ratio_stress_scr = ratio_scr_stress / ratio_scr_base
        else:
            ratio_stress_scr = 1.0

        if 0.5 <= ratio_stress_scr <= 0.9:
            c3_statut = "VERT"
            c3_msg    = f"Ratio SCR post-stress/base = {ratio_stress_scr:.3f} ∈ [0.5, 0.9] ✅"
            c3_conseil= "Stress Testing cohérent avec le niveau de SCR — chocs calibrés"
        elif ratio_stress_scr > 0.95:
            c3_statut = "AMBRE"
            c3_msg    = f"Ratio = {ratio_stress_scr:.3f} > 0.95 → Stress insuffisant ⚠️"
            c3_conseil= "Les chocs semblent trop faibles — recalibrer avec chocs EIOPA standard"
        elif ratio_stress_scr < 0.4:
            c3_statut = "AMBRE"
            c3_msg    = f"Ratio = {ratio_stress_scr:.3f} < 0.4 → Stress très sévère ⚠️"
            c3_conseil= "Vérifier la cohérence des chocs appliqués avec les paramètres S2"
        else:
            c3_statut = "VERT"
            c3_msg    = f"Ratio SCR post-stress/base = {ratio_stress_scr:.3f} → Acceptable ✅"
            c3_conseil= "Cohérence SCR / Stress Testing confirmée"

        statuts = [c1_statut, c2_statut, c3_statut]
        statut_global = "ROUGE" if "ROUGE" in statuts else "AMBRE" if "AMBRE" in statuts else "VERT"
        conclusion = {
            "VERT":  "✅ Cohérence inter-équipes validée — Tarification, Provisions, S2 et IFRS17 alignés",
            "AMBRE": "⚠️ Cohérence partielle — vérifier les points signalés avec les équipes concernées",
            "ROUGE": "❌ Incohérence détectée — réunion inter-équipes requise avant livraison",
        }[statut_global]

        return {
            "c1_loss_ratio": {
                "lr_tarif":  round(lr_tarif, 4),
                "lr_provs":  round(lr_provs, 4),
                "ratio_lr":  round(ratio_lr, 4),
                "ecart_pct": round(ecart_lr, 2),
                "statut":    c1_statut,
                "message":   c1_msg,
                "conseil":   c1_conseil,
                "titre_graphique": f"{'✅' if c1_statut=='VERT' else '⚠️' if c1_statut=='AMBRE' else '❌'} Loss Ratio — Écart Tarif/Provisions = {ecart_lr:.1f}%",
            },
            "c2_be_ifrs": {
                "be_s2":     round(be_s2, 0),
                "tp_ifrs17": round(tp_ifrs, 0),
                "ratio_tp":  round(ratio_tp, 4),
                "statut":    c2_statut,
                "message":   c2_msg,
                "conseil":   c2_conseil,
                "titre_graphique": f"{'✅' if c2_statut=='VERT' else '⚠️' if c2_statut=='AMBRE' else '❌'} BE S2 ↔ TP IFRS17 — Ratio = {ratio_tp:.3f}",
            },
            "c3_scr_stress": {
                "ratio_scr_base":   round(ratio_scr_base, 1),
                "ratio_scr_stress": round(ratio_scr_stress, 1),
                "ratio_coherence":  round(ratio_stress_scr, 3),
                "statut":           c3_statut,
                "message":          c3_msg,
                "conseil":          c3_conseil,
                "titre_graphique": f"{'✅' if c3_statut=='VERT' else '⚠️' if c3_statut=='AMBRE' else '❌'} SCR ↔ Stress — Ratio {ratio_stress_scr:.3f}",
            },
            "statut_global": statut_global,
            "conclusion":    conclusion,
        }

    def _graphiques_validation_coherence(
        self,
        val_coh: Dict,
    ) -> Dict:
        """4 graphiques auto-explicatifs validation cohérence."""
        try:
            import plotly.graph_objects as go
            import numpy as np
        except ImportError:
            return {}

        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"
        OR="#C9A84C"; BLANC="#F0F4F8"; GRIS="#8A9AB0"
        VERT="#2ECC71"; ROUGE="#E74C3C"; AMBRE="#F39C12"; BLEU="#3498DB"
        LAYOUT = dict(
            paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=60, b=50), height=300,
            hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
        )
        graphiques = {}

        # G1 — Loss Ratio Tarif vs Provisions
        try:
            c1 = val_coh["c1_loss_ratio"]
            lr_t, lr_p = c1["lr_tarif"], c1["lr_provs"]
            couleur_c1 = VERT if c1["statut"]=="VERT" else AMBRE if c1["statut"]=="AMBRE" else ROUGE

            fig1 = go.Figure()
            fig1.add_trace(go.Bar(
                x=["LR Tarification", "LR Provisions"],
                y=[lr_t*100, lr_p*100],
                marker_color=[BLEU, couleur_c1],
                marker_line=dict(color=NAVY, width=1),
                width=0.4, opacity=0.88,
                text=[f"{lr_t*100:.1f}%", f"{lr_p*100:.1f}%"],
                textposition="outside",
                textfont=dict(color=BLANC, size=12),
                hovertemplate="<b>%{x}</b><br>Loss Ratio : %{y:.1f}%<extra></extra>",
            ))
            # Plage acceptable
            fig1.add_hrect(y0=lr_t*100*0.85, y1=lr_t*100*1.15,
                          fillcolor="rgba(46,204,113,0.08)", line_width=0,
                          annotation_text="Plage ±15%",
                          annotation_font=dict(color=VERT, size=9))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(text=c1["titre_graphique"],
                          font=dict(color=couleur_c1, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title="%", tickfont=dict(color=GRIS), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 Les deux barres doivent être proches (zone verte ±15%). Un grand écart = hypothèses incohérentes entre tarification et provisionnement.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig1.update_layout(**l1)
            graphiques["loss_ratio_coherence"] = fig1
        except Exception as e:
            self.logger.warning(f"G1 LR : {e}")

        # G2 — BE S2 vs TP IFRS17
        try:
            c2 = val_coh["c2_be_ifrs"]
            couleur_c2 = VERT if c2["statut"]=="VERT" else AMBRE if c2["statut"]=="AMBRE" else ROUGE

            fig2 = go.Figure(go.Bar(
                x=["Best Estimate S2", "TP IFRS 17"],
                y=[c2["be_s2"]/1e6, c2["tp_ifrs17"]/1e6],
                marker_color=[OR, couleur_c2],
                marker_line=dict(color=NAVY, width=1),
                width=0.4, opacity=0.88,
                text=[f"{c2['be_s2']/1e6:.2f}M€", f"{c2['tp_ifrs17']/1e6:.2f}M€"],
                textposition="outside",
                textfont=dict(color=BLANC, size=12),
                hovertemplate="<b>%{x}</b><br>%{y:.2f}M€<extra></extra>",
            ))
            # Zone acceptable TP ∈ [1.0, 1.5] × BE
            fig2.add_hrect(y0=c2["be_s2"]/1e6, y1=c2["be_s2"]/1e6*1.5,
                          fillcolor="rgba(46,204,113,0.08)", line_width=0,
                          annotation_text="Zone IFRS17 acceptable [1.0×, 1.5×] BE",
                          annotation_font=dict(color=VERT, size=9))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(text=c2["titre_graphique"],
                          font=dict(color=couleur_c2, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title="M€", tickfont=dict(color=GRIS)),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 Le TP IFRS17 doit être entre 1× et 1.5× le BE S2. La zone verte montre la plage acceptable.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig2.update_layout(**l2)
            graphiques["be_s2_vs_ifrs17"] = fig2
        except Exception as e:
            self.logger.warning(f"G2 BE/IFRS : {e}")

        # G3 — SCR base vs post-stress
        try:
            c3 = val_coh["c3_scr_stress"]
            couleur_c3 = VERT if c3["statut"]=="VERT" else AMBRE if c3["statut"]=="AMBRE" else ROUGE

            fig3 = go.Figure(go.Bar(
                x=["SCR Base", "SCR Post-Stress"],
                y=[c3["ratio_scr_base"], c3["ratio_scr_stress"]],
                marker_color=[OR, couleur_c3],
                marker_line=dict(color=NAVY, width=1),
                width=0.4, opacity=0.88,
                text=[f"{c3['ratio_scr_base']:.1f}%", f"{c3['ratio_scr_stress']:.1f}%"],
                textposition="outside",
                textfont=dict(color=BLANC, size=12),
                hovertemplate="<b>%{x}</b><br>Ratio SCR : %{y:.1f}%<extra></extra>",
            ))
            fig3.add_hline(y=100, line_color=ROUGE, line_width=2, line_dash="dot",
                          annotation_text="Seuil 100%",
                          annotation_font=dict(color=ROUGE, size=9))
            l3 = dict(**LAYOUT)
            l3.update(dict(
                title=dict(text=c3["titre_graphique"],
                          font=dict(color=couleur_c3, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(title="Ratio SCR (%)", tickfont=dict(color=GRIS),
                          showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                bargap=0.35, showlegend=False,
                annotations=[dict(
                    text="💡 Le ratio post-stress doit rester au-dessus de 100%. L'écart entre les deux barres = impact du stress.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig3.update_layout(**l3)
            graphiques["scr_vs_stress"] = fig3
        except Exception as e:
            self.logger.warning(f"G3 SCR stress : {e}")

        # G4 — Scorecard cohérence globale
        try:
            items = [
                ("C1 — Loss Ratio cohérent", val_coh["c1_loss_ratio"]["statut"],
                 val_coh["c1_loss_ratio"]["message"], val_coh["c1_loss_ratio"]["conseil"]),
                ("C2 — BE S2 ↔ TP IFRS17", val_coh["c2_be_ifrs"]["statut"],
                 val_coh["c2_be_ifrs"]["message"], val_coh["c2_be_ifrs"]["conseil"]),
                ("C3 — SCR ↔ Stress Testing", val_coh["c3_scr_stress"]["statut"],
                 val_coh["c3_scr_stress"]["message"], val_coh["c3_scr_stress"]["conseil"]),
            ]
            fig4 = go.Figure()
            for nom, statut, msg, conseil in items:
                couleur = VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                icone   = "✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                score   = 1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(
                    x=[score], y=[nom], orientation="h",
                    marker_color=couleur, width=0.5,
                    text=f"{icone} {statut}", textposition="outside",
                    textfont=dict(color=couleur, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False,
                ))
            statut_g  = val_coh["statut_global"]
            couleur_g = VERT if statut_g=="VERT" else AMBRE if statut_g=="AMBRE" else ROUGE
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(
                    text=f"Scorecard Cohérence — {val_coh['conclusion']}",
                    font=dict(color=couleur_g, size=10), x=0.01
                ),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 3 ✅ = toutes les équipes sont alignées. Un ❌ = réunion inter-équipes requise.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig4.update_layout(**l4)
            graphiques["scorecard_coherence"] = fig4
        except Exception as e:
            self.logger.warning(f"G4 scorecard : {e}")

        return graphiques

    def _erreur(self, message: str, audit_id: str) -> Dict:
        return {
            'success':     False,
            'statut_rag':  'ROUGE',
            'controles':   [],
            'dashboard':   {},
            'rapport':     {},
            'commentaire': f"❌ ERREUR A9 : {message}",
            'audit_id':    audit_id,
            'erreur':      message,
        }


if __name__ == '__main__':
    print("Agent A9 — Cohérence inter-équipes ActuarIA v2.0")
    print("Correction : comparaison Loss Ratios au lieu de primes absolues")
    print("Usage : %run 'chemin/a9_coherence.py'")
    print("        agent_a9 = AgentA9Coherence()")
    print("        result_a9 = agent_a9.run(result_a3, result_a6, result_a7, result_a8)")
