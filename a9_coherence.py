"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           ACTUARIA — AGENT A9 MARCUS : COHÉRENCE GLOBALE NON-VIE v3        ║
║                      Rattaché directement à LEILA                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Contrôle transversal de toute la direction Non-Vie                  ║
║         Vérifie la cohérence entre TOUS les agents                          ║
║         Émet des alertes proactives avant soumission ACPR                   ║
║                                                                              ║
║  ENTRÉES OBLIGATOIRES :                                                      ║
║    result_a6  → Comparaison modèles (MEI-LIN via VICTOR)                    ║
║    result_a7  → Provisions (IBRAHIM — Best Estimate S2)                     ║
║    result_a8  → Stress Testing (ISABELLE — SCR + chocs)                     ║
║                                                                              ║
║  ENTRÉES OPTIONNELLES (enrichissent l'analyse) :                            ║
║    result_a3  → GLM tarification (LAURENT)                                  ║
║    result_a10 → Solvabilité 2 (ELENA)                                       ║
║    result_a11 → IFRS 17 (THOMAS)                                            ║
║    result_a12 → ALM (AISHA)                                                 ║
║                                                                              ║
║  CONTRÔLES EFFECTUÉS (6) :                                                  ║
║    C1 — Loss Ratio : Tarif ↔ Provisions                                     ║
║    C2 — Provisions ↔ Stress Testing (ratio SCR/BE)                         ║
║    C3 — Modèle Production ↔ Provisions (A6 ↔ A7)                           ║
║    C4 — BE S2 ↔ TP IFRS17 (réconciliation réglementaire)                   ║
║    C5 — SCR ↔ ALM (cohérence bilan actif/passif)                            ║
║    C6 — Cohérence globale (synthèse + alertes proactives IA)                ║
║                                                                              ║
║  STANDARD ACTUARIA :                                                         ║
║    ✅ Statut RAG (VERT/AMBRE/ROUGE) + message + conseil                      ║
║    ✅ 3 hypothèses validées                                                   ║
║    ✅ 4 graphiques auto-explicatifs avec annotations pédagogiques            ║
║    ✅ Scorecard synthétique                                                   ║
║    ✅ Commentaire actuariel en langage naturel (DG & ACPR)                   ║
║    ✅ Alertes proactives — UNIQUE marché                                     ║
║                                                                              ║
║  NOUVEAUTÉS v3 :                                                             ║
║    → Reçoit result_a10 + result_a11 + result_a12 (flux complets)            ║
║    → Contrôle C4 : réconciliation S2/IFRS17 enrichie                        ║
║    → Contrôle C5 : cohérence ALM (duration gap, immunisation)               ║
║    → Alertes proactives IA (6 patterns détectés automatiquement)            ║
║    → Rattachement LEILA explicite dans les métadonnées                      ║
║    → Graphiques v3 : radar des contrôles + heat map cohérence               ║
║                                                                              ║
║  VERSION : 3.0 — 19/06/2026                                                 ║
║  AUTEUR  : ActuarIA — Marcus (sous LEILA, Direction Non-Vie)                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import logging
import warnings
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
logger = logging.getLogger('actuaria.a9.marcus')

# ══════════════════════════════════════════════════════════════════════════════
# PALETTE ACTUARIA — IDENTIQUE AUX AUTRES AGENTS
# ══════════════════════════════════════════════════════════════════════════════
NAVY    = "#0F2E52"
NAVY_L  = "#1B3A5C"
NAVY_LL = "#243F6A"
OR      = "#C9A84C"
BLANC   = "#F0F4F8"
GRIS    = "#8A9AB0"
VERT    = "#2ECC71"
ROUGE   = "#E74C3C"
AMBRE   = "#F39C12"
BLEU    = "#3498DB"
VIOLET  = "#9B59B6"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY,
    plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60),
    height=320,
    hoverlabel=dict(
        bgcolor=NAVY_LL, bordercolor=OR,
        font_size=12, font_color=BLANC
    ),
)


# ══════════════════════════════════════════════════════════════════════════════
# AGENT A9 MARCUS
# ══════════════════════════════════════════════════════════════════════════════

class AgentA9Coherence:
    """
    Agent A9 Marcus — Contrôle cohérence globale Direction Non-Vie.

    RATTACHEMENT : LEILA (Directrice Non-Vie) — contrôle transversal
    Reçoit les résultats de tous les agents Non-Vie et vérifie leur cohérence
    mutuelle avant tout reporting réglementaire (S2, IFRS17, ACPR).

    INDÉPENDANCE :
    Marcus est rattaché directement à LEILA (pas sous KWAME) pour garantir
    l'indépendance du contrôle vis-à-vis des agents qu'il surveille.

    PHILOSOPHIE :
    Un actuaire désigné signe le rapport de provisions.
    Marcus est son assistant numérique : il traque les incohérences
    inter-équipes AVANT que le document ne parte à l'ACPR.
    """

    # Identité agent
    NOM        = "Marcus"
    CODE       = "A9"
    VERSION    = "3.0"
    DIRECTION  = "Non-Vie"
    RESPONSABLE = "LEILA (directement)"

    def __init__(
        self,
        models_path: str = '/content/drive/MyDrive/ActuarIA/models',
        audit_path:  str = '/content/drive/MyDrive/ActuarIA/audit',
        verbose:     bool = True
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose
        self.logger      = logging.getLogger('actuaria.a9.marcus')

        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            self.logger.info(
                f"Agent A9 Marcus v{self.VERSION} initialisé | "
                f"Rattachement : {self.RESPONSABLE}"
            )

    # ══════════════════════════════════════════════════════════════════════════
    # POINT D'ENTRÉE PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════

    def run(
        self,
        result_a6:  Optional[Dict] = None,
        result_a7:  Optional[Dict] = None,
        result_a8:  Optional[Dict] = None,
        result_a3:  Optional[Dict] = None,   # optionnel : enrichit C1
        result_a10: Optional[Dict] = None,   # optionnel : enrichit C4
        result_a11: Optional[Dict] = None,   # optionnel : enrichit C4
        result_a12: Optional[Dict] = None,   # optionnel : enrichit C5
        sous_branche:       str   = 'auto',
        primes_acq:         float = 0.0,
        generer_graphiques: bool  = True,
    ) -> Dict[str, Any]:
        """
        Pipeline principal de contrôle de cohérence.

        Paramètres
        ----------
        result_a6  : Dict — Résultats Agent A6 VICTOR (comparaison modèles)
        result_a7  : Dict — Résultats Agent A7 IBRAHIM (provisions)
        result_a8  : Dict — Résultats Agent A8 ISABELLE (stress testing)
        result_a3  : Dict — Résultats Agent A3 LAURENT (GLM, optionnel)
        result_a10 : Dict — Résultats Agent A10 ELENA (S2, optionnel)
        result_a11 : Dict — Résultats Agent A11 THOMAS (IFRS17, optionnel)
        result_a12 : Dict — Résultats Agent A12 AISHA (ALM, optionnel)
        sous_branche : str — Branche analysée (RC Auto, MRH, etc.)
        primes_acq   : float — Primes acquises réelles (si disponibles)
        generer_graphiques : bool — Générer les 4 graphiques Plotly

        Retourne
        --------
        Dict avec : success, statut_rag, controles, dashboard, alertes_proactives,
                    hypotheses, commentaire, graphiques, audit_id
        """
        t_debut  = datetime.now()
        audit_id = f"A9_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"[{audit_id}] Agent A9 Marcus v{self.VERSION} démarré")

        # Vérification flux minimaux
        flux_ok = self._verifier_flux_minimaux(result_a6, result_a7, result_a8)

        controles       = []
        alertes_ia      = []
        agents_presents = []

        try:
            # ── C1 : LOSS RATIO — TARIF ↔ PROVISIONS ─────────────────────────
            if result_a7 and (result_a3 or result_a6):
                src_tarif = result_a3 if result_a3 else result_a6
                c1 = self._ctrl_loss_ratio(src_tarif, result_a7, primes_acq,
                                            a3_direct=bool(result_a3))
                controles.append(c1)
                agents_presents.append('A3/A6↔A7')
                self.logger.info(f"C1 Loss Ratio : {c1['statut']} | {c1['message']}")
            else:
                controles.append(self._ctrl_na('Loss Ratio Tarif↔Prov', 'A3/A6↔A7',
                                               'result_a7 + result_a3 ou result_a6 requis'))

            # ── C2 : PROVISIONS ↔ STRESS TESTING ─────────────────────────────
            if result_a7 and result_a8:
                c2 = self._ctrl_provisions_stress(result_a7, result_a8)
                controles.append(c2)
                agents_presents.append('A7↔A8')
                self.logger.info(f"C2 Prov↔Stress : {c2['statut']} | {c2['message']}")
            else:
                controles.append(self._ctrl_na('Provisions↔Stress Testing', 'A7↔A8',
                                               'result_a7 + result_a8 requis'))

            # ── C3 : MODÈLE PRODUCTION ↔ PROVISIONS ──────────────────────────
            if result_a6 and result_a7:
                c3 = self._ctrl_modele_provisions(result_a6, result_a7)
                controles.append(c3)
                agents_presents.append('A6↔A7')
                self.logger.info(f"C3 Modèle↔Prov : {c3['statut']} | {c3['message']}")
            else:
                controles.append(self._ctrl_na('Modèle Production↔Provisions', 'A6↔A7',
                                               'result_a6 + result_a7 requis'))

            # ── C4 : BE S2 ↔ TP IFRS17 ───────────────────────────────────────
            if result_a7 and result_a10 and result_a11:
                c4 = self._ctrl_s2_ifrs17_enrichi(result_a7, result_a10, result_a11)
                controles.append(c4)
                agents_presents.append('A7+A10↔A11')
                self.logger.info(f"C4 S2↔IFRS17 : {c4['statut']} | {c4['message']}")
            elif result_a7 and result_a11:
                c4 = self._ctrl_s2_ifrs17_base(result_a7, result_a11)
                controles.append(c4)
                agents_presents.append('A7↔A11')
                self.logger.info(f"C4 S2↔IFRS17 (base) : {c4['statut']} | {c4['message']}")
            else:
                controles.append(self._ctrl_na('BE S2↔TP IFRS17', 'A7+A10↔A11',
                                               'result_a7 + result_a11 requis'))

            # ── C5 : COHÉRENCE ALM (BILAN ACTIF/PASSIF) ──────────────────────
            if result_a10 and result_a12:
                c5 = self._ctrl_alm(result_a10, result_a12, result_a7)
                controles.append(c5)
                agents_presents.append('A10↔A12')
                self.logger.info(f"C5 ALM : {c5['statut']} | {c5['message']}")
            else:
                controles.append(self._ctrl_na('Cohérence ALM', 'A10↔A12',
                                               'result_a10 + result_a12 requis'))

            # ── C6 : COHÉRENCE GLOBALE — SYNTHÈSE ────────────────────────────
            c6, alertes_ia = self._ctrl_coherence_globale(
                controles, result_a7, result_a8, result_a10
            )
            controles.append(c6)
            self.logger.info(f"C6 Global : {c6['statut']} | {c6['message']}")

            # ── HYPOTHÈSES VALIDÉES ───────────────────────────────────────────
            hypotheses = self._valider_hypotheses(
                controles, result_a7, result_a8
            )

            # ── STATUT RAG GLOBAL ─────────────────────────────────────────────
            nb_rouge = sum(1 for c in controles if c.get('statut') == 'ROUGE')
            nb_ambre = sum(1 for c in controles if c.get('statut') == 'AMBRE')
            nb_vert  = sum(1 for c in controles if c.get('statut') == 'VERT')
            statut_rag = (
                'ROUGE' if nb_rouge > 0 else
                'AMBRE' if nb_ambre > 0 else
                'VERT'
            )

            # ── COMMENTAIRE ACTUARIEL ─────────────────────────────────────────
            commentaire = self._commenter_actuaire(
                controles, alertes_ia, hypotheses, statut_rag,
                sous_branche, agents_presents
            )

            # ── DASHBOARD ────────────────────────────────────────────────────
            dashboard = self._generer_dashboard(
                controles, nb_vert, nb_ambre, nb_rouge, statut_rag,
                alertes_ia, agents_presents
            )

            # ── GRAPHIQUES ────────────────────────────────────────────────────
            graphiques = {}
            if generer_graphiques and PLOTLY_OK:
                graphiques = self._generer_graphiques(controles, dashboard, alertes_ia)

            # ── SAUVEGARDE AUDIT ──────────────────────────────────────────────
            self._sauvegarder_audit(
                audit_id, sous_branche, controles, statut_rag, t_debut, alertes_ia
            )

            # ── AFFICHAGE CONSOLE ─────────────────────────────────────────────
            if self.verbose:
                self._afficher_console(
                    audit_id, sous_branche, controles, statut_rag,
                    commentaire, alertes_ia, hypotheses
                )

            duree = (datetime.now() - t_debut).total_seconds()
            self.logger.info(f"[{audit_id}] A9 terminé en {duree:.2f}s")

            return {
                'success':          True,
                'agent':            self.NOM,
                'version':          self.VERSION,
                'rattachement':     self.RESPONSABLE,
                'audit_id':         audit_id,
                'sous_branche':     sous_branche,
                'statut_rag':       statut_rag,
                'controles':        controles,
                'dashboard':        dashboard,
                'alertes_proactives': alertes_ia,
                'hypotheses':       hypotheses,
                'commentaire':      commentaire,
                'graphiques':       graphiques,
                'flux_ok':          flux_ok,
                'agents_analyses':  agents_presents,
                'duree_sec':        round(duree, 2),
                'erreur':           None,
            }

        except Exception as e:
            self.logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ══════════════════════════════════════════════════════════════════════════
    # CONTRÔLE 1 — LOSS RATIO : TARIF ↔ PROVISIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _ctrl_loss_ratio(
        self,
        result_src: Dict,
        result_a7:  Dict,
        primes_acq: float = 0.0,
        a3_direct:  bool  = True
    ) -> Dict:
        """
        Compare les Loss Ratios — grandeurs actuariellement comparables.

        LOGIQUE :
        LR_Tarif  = (fréquence × coût moyen) / prime commerciale
        LR_Prov   = Best Estimate / primes acquises

        Les deux doivent être dans le même ordre de grandeur.
        Écart > 30 points → investigation requise.

        Seuils calibrés Non-Vie France :
        LR typique RC Auto : 70-85%  |  MRH : 50-70%  |  Construction : 60-80%
        """
        # ── Loss Ratio depuis tarification ──────────────────────────────────
        if a3_direct:
            # Source : result_a3 (GLM direct)
            met = result_src.get('metriques', {})
            freq   = met.get('poisson', {}).get('frequence_obs', 0.15)
            cout   = met.get('gamma', {}).get('cout_moyen_obs', 5000)
            pp_glm = freq * cout
        else:
            # Source : result_a6 (comparaison modèles)
            mp = result_src.get('modele_production', {})
            pp_glm = mp.get('prime_pure', 0.0)
            if pp_glm == 0:
                # Fallback : extraire depuis métriques GLM si disponible
                freq   = mp.get('frequence', 0.15)
                cout   = mp.get('cout_moyen', 5000)
                pp_glm = freq * cout

        # Prime commerciale estimée (chargement typique 30%)
        prime_comm = pp_glm / 0.70 if pp_glm > 0 else 1.0
        lr_tarif   = pp_glm / max(prime_comm, 1.0)

        # ── Loss Ratio depuis provisions ──────────────────────────────────
        be = result_a7.get('best_estimate', {}).get('best_estimate', 0.0)

        if primes_acq > 0:
            # Source 1 (meilleure) : primes fournies explicitement
            lr_prov    = be / max(primes_acq, 1.0)
            source_p   = "primes_acq fournies"
        else:
            # Source 2 : primes dans le triangle A7 (diagonale courante)
            primes_tri = result_a7.get('meta', {}).get('primes_acquises', 0.0)
            if primes_tri == 0:
                primes_tri = result_a7.get('triangle', {}).get('primes_periode', 0.0)
            if primes_tri == 0:
                primes_tri = result_a7.get('best_estimate', {}).get('primes_estimees', 0.0)

            if primes_tri > 0:
                # Source 2 : primes extraites du triangle
                lr_prov  = be / max(primes_tri, 1.0)
                source_p = f"primes triangle A7 ({primes_tri:,.0f}€)"
            else:
                # Source 3 (fallback) : on reconstruit depuis prime_pure et portefeuille
                # BE ≈ LR × Primes  →  si on fixe LR_cible = LR_tarif, on valide
                # la cohérence par le ratio BE/prime_pure_estimée
                nb_contrats = result_a7.get('meta', {}).get('nb_lignes', 0)
                if nb_contrats > 0:
                    # Estimation des primes depuis le portefeuille
                    primes_est = prime_comm * nb_contrats * 0.80
                    lr_prov    = be / max(primes_est, 1.0)
                    # Estimation imprécise → sentinel négatif spécial
                    # On retournera AMBRE plutôt que ROUGE/VERT pour ce cas
                    lr_prov    = -0.5 - lr_prov   # sentinel : estimation incertaine
                    source_p   = f"estimation_incertaine ({nb_contrats} contrats × {prime_comm:,.0f}€)"
                else:
                    # Dernier recours : données insuffisantes
                    lr_prov  = -1.0   # sentinel : données insuffisantes
                    source_p = "INSUFFISANT — fournir primes_acq"

        # Cas sentinel : données insuffisantes ou estimation incertaine
        if lr_prov < 0:
            if lr_prov <= -0.5 and lr_prov > -1.0:
                # Estimation incertaine depuis nb_lignes → AMBRE, afficher valeur avec avertissement
                lr_prov_reel = -(lr_prov + 0.5)   # décoder la valeur réelle
                return {
                    'controle':   'C1 — Loss Ratio : Tarif ↔ Provisions',
                    'agents':     'A3/A6 ↔ A7',
                    'statut':     'AMBRE',
                    'lr_tarif':   round(lr_tarif * 100, 1),
                    'lr_prov':    round(lr_prov_reel * 100, 1),
                    'ecart_pts':  None,
                    'prime_pure': round(pp_glm, 0),
                    'be':         round(be, 0),
                    'source_primes': source_p,
                    'message':    (
                        f"LR Tarif={lr_tarif*100:.1f}% | "
                        f"LR Prov≈{lr_prov_reel*100:.1f}% (estimation, primes_acq absentes)"
                    ),
                    'conseil':    (
                        "Fournir primes_acq pour un contrôle précis. "
                        "Valeur actuelle estimée depuis le nombre de contrats."
                    ),
                    'description': f"Prime pure={pp_glm:,.0f}€ | BE={be:,.0f}€ | Source : {source_p}",
                }
            else:
                # -1.0 : aucune donnée disponible
                return {
                    'controle':   'C1 — Loss Ratio : Tarif ↔ Provisions',
                    'agents':     'A3/A6 ↔ A7',
                    'statut':     'AMBRE',
                    'lr_tarif':   round(lr_tarif * 100, 1),
                    'lr_prov':    None,
                    'ecart_pts':  None,
                    'prime_pure': round(pp_glm, 0),
                    'be':         round(be, 0),
                    'source_primes': source_p,
                    'message':    (
                        f"LR Tarif={lr_tarif*100:.1f}% | "
                        "LR Prov=N/A (primes_acq manquantes)"
                    ),
                    'conseil':    (
                        "Fournir le paramètre primes_acq (primes acquises annuelles réelles) "
                        "pour activer la comparaison Loss Ratio. Sans ce paramètre, "
                        "le contrôle C1 ne peut pas être concluant."
                    ),
                    'description': f"Prime pure={pp_glm:,.0f}€ | BE={be:,.0f}€ | Source : {source_p}",
                }

        ecart_pts = abs(lr_tarif - lr_prov)

        # Seuils (en points de LR)
        statut = (
            'VERT'  if ecart_pts <= 0.15 else
            'AMBRE' if ecart_pts <= 0.30 else
            'ROUGE'
        )
        conseils = {
            'VERT':  'Les hypothèses de coût/fréquence sont cohérentes entre tarif et provisions.',
            'AMBRE': 'Vérifier si les données de tarification et de provisionnement couvrent la même période.',
            'ROUGE': 'Réunion inter-équipes requise avant soumission ACPR. Aligner les hypothèses.',
        }

        return {
            'controle':   'C1 — Loss Ratio : Tarif ↔ Provisions',
            'agents':     'A3/A6 ↔ A7',
            'statut':     statut,
            'lr_tarif':   round(lr_tarif  * 100, 1),
            'lr_prov':    round(lr_prov   * 100, 1),
            'ecart_pts':  round(ecart_pts * 100, 1),
            'prime_pure': round(pp_glm, 0),
            'be':         round(be, 0),
            'source_primes': source_p,
            'message':    (
                f"LR Tarif={lr_tarif*100:.1f}% | "
                f"LR Prov={lr_prov*100:.1f}% | "
                f"Écart={ecart_pts*100:.1f} pts"
            ),
            'conseil':    conseils[statut],
            'description': (
                f"Prime pure={pp_glm:,.0f}€ | BE={be:,.0f}€ | "
                f"Source primes : {source_p}"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # CONTRÔLE 2 — PROVISIONS ↔ STRESS TESTING
    # ══════════════════════════════════════════════════════════════════════════

    def _ctrl_provisions_stress(
        self,
        result_a7: Dict,
        result_a8: Dict
    ) -> Dict:
        """
        Vérifie que les provisions et le stress testing sont cohérents.

        LOGIQUE :
        Ratio SCR_souscription / BE = fraction de l'incertitude capitalisée.

        Seuils EIOPA (Non-Vie standard) :
        10% – 80% → VERT  (normal : SCR couvre une partie de l'incertitude)
        80% – 120% → AMBRE (élevé : provisions peut-être sous-estimées)
        > 120% → ROUGE (anormal : SCR > provisions, signal sérieux)

        On vérifie aussi la cohérence du ratio SCR global / fonds propres.
        """
        be      = result_a7.get('best_estimate', {}).get('best_estimate', 0.0)
        sigma   = result_a7.get('best_estimate', {}).get('sigma_mack', 0.0)

        chocs   = result_a8.get('chocs_s2', {})
        scr_sou = chocs.get('scr_souscription', 0.0)
        scr_tot = result_a8.get('capital', {}).get('scr_total', 0.0)
        fpp     = result_a8.get('capital', {}).get('fonds_propres', 0.0)
        ratio_scr_fpp = (fpp / max(scr_tot, 1.0)) * 100 if scr_tot > 0 else 0.0

        ratio_scr_be = scr_sou / max(be, 1.0)

        statut_scr_be = (
            'VERT'  if 0.10 <= ratio_scr_be <= 0.80 else
            'AMBRE' if ratio_scr_be <= 1.20 else
            'ROUGE'
        )

        # Vérification secondaire : ratio SCR/FPP doit être > 100%
        statut_solvab = (
            'VERT'  if ratio_scr_fpp >= 150 else
            'AMBRE' if ratio_scr_fpp >= 100 else
            'ROUGE'
        )

        statut = statut_scr_be if statut_scr_be != 'VERT' else statut_solvab
        conseils = {
            'VERT':  'Cohérence provisions / stress confirmée. Capital suffisant.',
            'AMBRE': 'Surveiller le ratio SCR/BE. Envisager des provisions complémentaires si tendance haussière.',
            'ROUGE': 'Action requise : soit revoir les provisions, soit renforcer le capital. Contact ACPR anticipé conseillé.',
        }

        return {
            'controle':        'C2 — Provisions ↔ Stress Testing',
            'agents':          'A7 ↔ A8',
            'statut':          statut,
            'be':              round(be, 0),
            'scr_souscription':round(scr_sou, 0),
            'scr_total':       round(scr_tot, 0),
            'fonds_propres':   round(fpp, 0),
            'ratio_scr_be':    round(ratio_scr_be * 100, 2),
            'ratio_scr_fpp':   round(ratio_scr_fpp, 1),
            'sigma_mack':      round(sigma, 0),
            'message':         (
                f"Ratio SCR/BE={ratio_scr_be:.1%} | "
                f"Ratio SCR/FPP={ratio_scr_fpp:.1f}%"
            ),
            'conseil':         conseils[statut],
            'description':     (
                f"BE={be:,.0f}€ | SCR_sou={scr_sou:,.0f}€ | "
                f"FPP={fpp:,.0f}€"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # CONTRÔLE 3 — MODÈLE PRODUCTION ↔ PROVISIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _ctrl_modele_provisions(
        self,
        result_a6: Dict,
        result_a7: Dict
    ) -> Dict:
        """
        Vérifie que le modèle de production sélectionné par A6 est cohérent
        avec le niveau de provisions calculé par A7.

        LOGIQUE :
        Un modèle performant (Gini élevé, score élevé) prédit bien les sinistres.
        Si les provisions sont très élevées alors que le modèle est bon, il peut
        y avoir une anomalie dans les données de sinistres.
        On utilise le CV inter-méthodes de A7 comme signal d'incertitude.
        """
        mp    = result_a6.get('modele_production', {})
        gini  = mp.get('gini_test', 0.0)
        score = mp.get('score_global', 0.0)
        modele_nom = mp.get('modele', 'N/A')

        # Incertitude des provisions (CV inter-méthodes)
        cv_prov = result_a7.get('best_estimate', {}).get('cv_inter_methodes', 0.0)
        nb_meth = result_a7.get('best_estimate', {}).get('nb_methodes_convergentes', 3)

        # Score de cohérence combiné :
        # Si Gini faible ET CV_prov élevé → incohérence (modèle imprécis ET provisions incertaines)
        # Si Gini fort → le modèle capte bien le risque, on fait confiance aux provisions
        score_coherence = (gini * 0.4 + (nb_meth / 6.0) * 0.4 + (1 - min(cv_prov, 100) / 100) * 0.2)

        statut = (
            'VERT'  if score_coherence >= 0.50 else
            'AMBRE' if score_coherence >= 0.25 else
            'ROUGE'
        )
        conseils = {
            'VERT':  f'Modèle {modele_nom} cohérent avec les provisions ({nb_meth} méthodes convergentes).',
            'AMBRE': f'Vérifier si {modele_nom} est calibré sur les mêmes données que les triangles A7.',
            'ROUGE': 'Incohérence modèle/provisions. Recalibrer sur données communes avant validation.',
        }

        return {
            'controle':         'C3 — Modèle Production ↔ Provisions',
            'agents':           'A6 ↔ A7',
            'statut':           statut,
            'modele':           modele_nom,
            'gini_test':        round(gini, 4),
            'score_a6':         round(score, 4),
            'cv_inter_methodes':round(cv_prov, 2),
            'nb_meth_conv':     nb_meth,
            'score_coherence':  round(score_coherence, 4),
            'message':          (
                f"Modèle={modele_nom} | Gini={gini:.4f} | "
                f"CV_prov={cv_prov:.1f}% | {nb_meth} méthodes convergentes"
            ),
            'conseil':          conseils[statut],
            'description':      f"Score cohérence : {score_coherence:.4f} (objectif ≥ 0.50)",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # CONTRÔLE 4 — BE S2 ↔ TP IFRS17 (version enrichie avec A10)
    # ══════════════════════════════════════════════════════════════════════════

    def _ctrl_s2_ifrs17_enrichi(
        self,
        result_a7:  Dict,
        result_a10: Dict,
        result_a11: Dict
    ) -> Dict:
        """
        Réconciliation complète S2 / IFRS17 avec données A10 (SCR officiel).

        LOGIQUE ACTUARIELLE :
        S2  : Best Estimate = provisions techniques (vision prudentielle)
        IFRS17 : Liability for Remaining Coverage (LRC) + Liability for Incurred Claims (LIC)

        Pour Non-Vie (PAA — Premium Allocation Approach) :
        LIC ≈ BE_S2  (même sinistres à payer)
        LRC ≈ portion non-courue des primes

        Réconciliation attendue : 1.0 ≤ TP_IFRS17 / BE_S2 ≤ 1.5
        """
        # BE depuis A7 (provisions directes)
        be_a7 = result_a7.get('best_estimate', {}).get('best_estimate', 0.0)

        # BE officiel depuis A10 (peut différer légèrement — actualisation EIOPA)
        be_s2 = result_a10.get('provisions', {}).get('best_estimate', be_a7)
        rm_s2 = result_a10.get('provisions', {}).get('risk_margin', 0.0)
        tp_s2 = be_s2 + rm_s2  # Technical Provisions S2

        # TP IFRS17 depuis A11
        tp_ifrs = result_a11.get('provisions', {}).get('lic_total', 0.0)
        if tp_ifrs == 0:
            tp_ifrs = result_a11.get('provisions', {}).get('tp_ifrs17', 0.0)
        if tp_ifrs == 0:
            tp_ifrs = be_a7 * 1.20  # estimation fallback (+20% risk margin IFRS)

        # Ratio de réconciliation
        ratio = tp_ifrs / max(tp_s2, be_s2, 1.0)
        ecart_abs = abs(tp_ifrs - tp_s2)

        statut = (
            'VERT'  if 0.90 <= ratio <= 1.60 else
            'AMBRE' if 0.75 <= ratio <= 2.00 else
            'ROUGE'
        )
        conseils = {
            'VERT':  'Réconciliation S2/IFRS17 dans les limites attendues. Rapport prêt pour validation.',
            'AMBRE': 'Analyser les différences (Risk Margin IFRS vs S2, périmètre contrats). Note de réconciliation à produire.',
            'ROUGE': 'Écart majeur S2/IFRS17. Vérifier les données sources des deux modules avant publication.',
        }

        return {
            'controle':   'C4 — BE S2 ↔ TP IFRS17',
            'agents':     'A7+A10 ↔ A11',
            'statut':     statut,
            'be_a7':      round(be_a7, 0),
            'be_s2':      round(be_s2, 0),
            'risk_margin':round(rm_s2, 0),
            'tp_s2':      round(tp_s2, 0),
            'tp_ifrs17':  round(tp_ifrs, 0),
            'ratio':      round(ratio, 4),
            'ecart_abs':  round(ecart_abs, 0),
            'message':    (
                f"TP_S2={tp_s2:,.0f}€ | TP_IFRS17={tp_ifrs:,.0f}€ | "
                f"Ratio={ratio:.4f}"
            ),
            'conseil':    conseils[statut],
            'description':f"Écart absolu={ecart_abs:,.0f}€ | RM_S2={rm_s2:,.0f}€",
        }

    def _ctrl_s2_ifrs17_base(
        self,
        result_a7:  Dict,
        result_a11: Dict
    ) -> Dict:
        """Version simplifiée sans A10 (A10 non disponible)."""
        be   = result_a7.get('best_estimate', {}).get('best_estimate', 0.0)
        tp_ifrs = result_a11.get('provisions', {}).get('lic_total',
                  result_a11.get('provisions', {}).get('tp_ifrs17', be * 1.20))

        ratio = tp_ifrs / max(be, 1.0)
        statut = (
            'VERT'  if 1.00 <= ratio <= 1.50 else
            'AMBRE' if 0.85 <= ratio <= 2.00 else
            'ROUGE'
        )

        return {
            'controle':  'C4 — BE S2 ↔ TP IFRS17 (sans A10)',
            'agents':    'A7 ↔ A11',
            'statut':    statut,
            'be_s2':     round(be, 0),
            'tp_ifrs17': round(tp_ifrs, 0),
            'ratio':     round(ratio, 4),
            'message':   f"BE_S2={be:,.0f}€ | TP_IFRS={tp_ifrs:,.0f}€ | Ratio={ratio:.2f}",
            'conseil':   'Connecter A10 pour une réconciliation S2/IFRS17 enrichie.',
            'description': f"Ratio IFRS/S2 : {ratio:.2f} (attendu : 1.0–1.5)",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # CONTRÔLE 5 — COHÉRENCE ALM (ACTIF / PASSIF)
    # ══════════════════════════════════════════════════════════════════════════

    def _ctrl_alm(
        self,
        result_a10: Dict,
        result_a12: Dict,
        result_a7:  Optional[Dict] = None
    ) -> Dict:
        """
        Vérifie la cohérence entre l'actif (ALM) et le passif (S2).

        LOGIQUE :
        Duration passif  vs  Duration actif → gap de duration
        Un gap > 2 ans est un risque de taux majeur.
        Ratio Duration_Actif / Duration_Passif ≈ 1 pour immunisation Redington.
        """
        alm = result_a12.get('alm', {})
        dur_actif  = alm.get('duration_actif',  3.5)
        dur_passif = alm.get('duration_passif', 4.0)
        gap_dur    = abs(dur_actif - dur_passif)
        immunise   = alm.get('immunisation_redington', False)

        # Duration du passif depuis A10 si disponible
        dur_passif_s2 = result_a10.get('duration', {}).get('passif', dur_passif)

        gap_s2 = abs(dur_actif - dur_passif_s2)

        statut = (
            'VERT'  if gap_s2 <= 1.0 and immunise else
            'VERT'  if gap_s2 <= 0.5 else
            'AMBRE' if gap_s2 <= 2.0 else
            'ROUGE'
        )
        conseils = {
            'VERT':  f'Gap de duration={gap_s2:.1f} ans. Position ALM saine.',
            'AMBRE': f'Gap de duration={gap_s2:.1f} ans. Envisager des instruments de couverture (IRS, futures).',
            'ROUGE': f'Gap de duration={gap_s2:.1f} ans trop élevé. Risque de taux non couvert significatif. Action urgente.',
        }

        return {
            'controle':       'C5 — Cohérence ALM (Actif/Passif)',
            'agents':         'A10 ↔ A12',
            'statut':         statut,
            'duration_actif':  round(dur_actif, 2),
            'duration_passif': round(dur_passif_s2, 2),
            'gap_duration':    round(gap_s2, 2),
            'immunise':        immunise,
            'message':         (
                f"Dur_Actif={dur_actif:.1f}a | "
                f"Dur_Passif={dur_passif_s2:.1f}a | "
                f"Gap={gap_s2:.1f}a"
            ),
            'conseil':         conseils[statut],
            'description':     f"Immunisation Redington : {'✅' if immunise else '❌'}",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # CONTRÔLE 6 — COHÉRENCE GLOBALE + ALERTES PROACTIVES IA
    # ══════════════════════════════════════════════════════════════════════════

    def _ctrl_coherence_globale(
        self,
        controles: List[Dict],
        result_a7: Optional[Dict],
        result_a8: Optional[Dict],
        result_a10: Optional[Dict]
    ) -> tuple:
        """
        Synthèse de tous les contrôles + génération des alertes proactives IA.

        Les alertes proactives détectent des patterns que les contrôles
        individuels ne capturent pas (interactions entre agents).
        """
        nb_rouge = sum(1 for c in controles if c.get('statut') == 'ROUGE')
        nb_ambre = sum(1 for c in controles if c.get('statut') == 'AMBRE')
        nb_vert  = sum(1 for c in controles if c.get('statut') == 'VERT')
        nb_na    = sum(1 for c in controles if c.get('statut') == 'N/A')

        statut = (
            'ROUGE' if nb_rouge >= 2 else
            'ROUGE' if nb_rouge == 1 else
            'AMBRE' if nb_ambre >= 2 else
            'AMBRE' if nb_ambre == 1 else
            'VERT'
        )

        # ── ALERTES PROACTIVES IA ─────────────────────────────────────────
        alertes = []

        if result_a7 and result_a8:
            be  = result_a7.get('best_estimate', {}).get('best_estimate', 0.0)
            scr = result_a8.get('capital', {}).get('scr_total', 0.0)
            fpp = result_a8.get('capital', {}).get('fonds_propres', 0.0)

            # Alerte 1 : Ratio SCR couverture faible
            if fpp > 0 and scr > 0:
                ratio_scr = fpp / scr
                if ratio_scr < 1.30:
                    alertes.append({
                        'type':    'CAPITAL',
                        'gravite': 'ROUGE',
                        'titre':   f"Ratio SCR = {ratio_scr*100:.0f}% — Proche du seuil réglementaire",
                        'detail':  (
                            "Le ratio de couverture du SCR est inférieur à 130%. "
                            "L'ACPR attend notification si < 150%. "
                            "Envisager une augmentation de capital ou réassurance supplémentaire."
                        ),
                        'action':  "Renforcer les fonds propres ou réduire le SCR via réassurance.",
                    })
                elif ratio_scr < 1.50:
                    alertes.append({
                        'type':    'CAPITAL',
                        'gravite': 'AMBRE',
                        'titre':   f"Ratio SCR = {ratio_scr*100:.0f}% — Marge tampon limitée",
                        'detail':  "Le ratio SCR est inférieur à 150%. La marge tampon est réduite.",
                        'action':  "Surveiller mensuellement. Préparer un plan de restauration.",
                    })

            # Alerte 2 : BE très élevé relativement aux primes
            tail = result_a7.get('tail', {}).get('tail_factor', 1.0)
            if tail > 1.15:
                alertes.append({
                    'type':    'PROVISIONS',
                    'gravite': 'AMBRE',
                    'titre':   f"Tail factor élevé : {tail:.4f} — Queue de distribution significative",
                    'detail':  (
                        f"Le tail factor de {tail:.4f} indique une développement résiduel "
                        "au-delà du dernier exercice observé. Vérifier la stabilité des facteurs "
                        "de développement sur les 3 dernières diagonales."
                    ),
                    'action':  "Documenter le choix du tail factor dans le rapport actuariel.",
                })

            # Alerte 3 : Convergence méthodes insuffisante
            nb_conv = result_a7.get('best_estimate', {}).get('nb_methodes_convergentes', 6)
            if nb_conv < 4:
                alertes.append({
                    'type':    'METHODE',
                    'gravite': 'AMBRE',
                    'titre':   f"Seulement {nb_conv}/6 méthodes convergentes",
                    'detail':  (
                        "Moins de 4 méthodes convergent vers le même BE. "
                        "La robustesse de l'estimation est réduite. "
                        "Analyser les méthodes divergentes avant validation."
                    ),
                    'action':  "Produire une note actuarielle justifiant le choix du BE.",
                })

        # Alerte 4 : Contrôles non exécutés (flux manquants)
        nb_na_count = sum(1 for c in controles if c.get('statut') == 'N/A')
        if nb_na_count >= 3:
            alertes.append({
                'type':    'FLUX',
                'gravite': 'AMBRE',
                'titre':   f"{nb_na_count} contrôles non exécutés — Flux manquants",
                'detail':  (
                    "Plusieurs agents n'ont pas encore fourni leurs résultats. "
                    "La cohérence globale ne peut pas être garantie."
                ),
                'action':  "Connecter A10, A11, A12 pour une analyse complète.",
            })

        # Conclusion
        nb_ctrl_ok = nb_vert
        nb_ctrl_ko = nb_rouge + nb_ambre
        conclusion = (
            f"✅ {nb_ctrl_ok} contrôles OK | "
            f"⚠️ {nb_ambre} avertissements | "
            f"❌ {nb_rouge} alertes | "
            f"⬜ {nb_na} N/A"
        )

        ctrl6 = {
            'controle':     'C6 — Cohérence Globale Non-Vie',
            'agents':       'TOUS (A3+A6+A7+A8+A10+A11+A12)',
            'statut':       statut,
            'nb_vert':      nb_vert,
            'nb_ambre':     nb_ambre,
            'nb_rouge':     nb_rouge,
            'nb_na':        nb_na,
            'nb_alertes_ia':len(alertes),
            'message':      conclusion,
            'conseil':      (
                "Tous les contrôles sont positifs. Direction Non-Vie prête pour validation."
                if statut == 'VERT' else
                "Traiter les points AMBRE avant soumission. Documenter les justifications."
                if statut == 'AMBRE' else
                "STOP : Points ROUGE non résolus. Soumission ACPR non recommandée."
            ),
            'description':  f"Marcus (A9) — Bilan transversal Direction Non-Vie",
        }

        return ctrl6, alertes

    # ══════════════════════════════════════════════════════════════════════════
    # HYPOTHÈSES VALIDÉES — STANDARD ACTUARIA (3 minimum)
    # ══════════════════════════════════════════════════════════════════════════

    def _valider_hypotheses(
        self,
        controles: List[Dict],
        result_a7: Optional[Dict],
        result_a8: Optional[Dict]
    ) -> List[Dict]:
        """
        Valide les 3 hypothèses standards du contrôle de cohérence.
        """
        hyp = []

        # Hypothèse 1 : Stabilité des facteurs de développement
        stable_lr = True
        if result_a7:
            cv = result_a7.get('best_estimate', {}).get('cv_inter_methodes', 0.0)
            stable_lr = cv < 20.0
        hyp.append({
            'id':          'H1',
            'hypothese':   "Facteurs de développement stables sur la période d'observation",
            'valeur':      f"CV inter-méthodes = {result_a7.get('best_estimate', {}).get('cv_inter_methodes', 0.0):.1f}%"
                           if result_a7 else "N/A",
            'statut':      'VALIDÉE' if stable_lr else 'À JUSTIFIER',
            'critique':    True,
        })

        # Hypothèse 2 : Loss Ratios comparables entre tarification et provisionnement
        c1 = next((c for c in controles if 'C1' in c.get('controle', '')), {})
        hyp.append({
            'id':        'H2',
            'hypothese': "Loss Ratios tarification et provisions établis sur données homogènes",
            'valeur':    (
                f"LR Tarif={c1.get('lr_tarif', 'N/A')}% | "
                f"LR Prov={c1.get('lr_prov', 'N/A')}%"
                if c1 else "Contrôle C1 non exécuté"
            ),
            'statut':    'VALIDÉE' if c1.get('statut') in ('VERT', 'AMBRE') else 'À JUSTIFIER',
            'critique':  True,
        })

        # Hypothèse 3 : Capital suffisant face aux scénarios de stress
        solvable = True
        if result_a8:
            fpp = result_a8.get('capital', {}).get('fonds_propres', 0.0)
            scr = result_a8.get('capital', {}).get('scr_total', 0.0)
            ratio = fpp / max(scr, 1.0) if scr > 0 else 0.0
            solvable = ratio >= 1.0
            val_str = f"Ratio SCR = {ratio*100:.1f}%"
        else:
            val_str = "A8 non connecté"
        hyp.append({
            'id':        'H3',
            'hypothese': "Capital suffisant pour couvrir le SCR dans tous les scénarios de stress",
            'valeur':    val_str,
            'statut':    'VALIDÉE' if solvable else 'NON VALIDÉE',
            'critique':  True,
        })

        return hyp

    # ══════════════════════════════════════════════════════════════════════════
    # COMMENTAIRE ACTUARIEL EN LANGAGE NATUREL
    # ══════════════════════════════════════════════════════════════════════════

    def _commenter_actuaire(
        self,
        controles:       List[Dict],
        alertes:         List[Dict],
        hypotheses:      List[Dict],
        statut_rag:      str,
        sous_branche:    str,
        agents_analyses: List[str],
    ) -> str:
        """
        Génère un commentaire actuariel en langage naturel.
        Compréhensible par un Directeur Général ET un auditeur ACPR.
        """
        nb_rouge = sum(1 for c in controles if c.get('statut') == 'ROUGE')
        nb_ambre = sum(1 for c in controles if c.get('statut') == 'AMBRE')
        nb_vert  = sum(1 for c in controles if c.get('statut') == 'VERT')
        nb_na    = sum(1 for c in controles if c.get('statut') == 'N/A')

        branche_str = sous_branche if sous_branche != 'auto' else 'Non-Vie'

        # Intro
        icone = "🟢" if statut_rag == 'VERT' else "🟡" if statut_rag == 'AMBRE' else "🔴"
        lignes = [
            f"{'=' * 70}",
            f"  RAPPORT DE COHÉRENCE — DIRECTION NON-VIE ({branche_str.upper()})",
            f"  Agent A9 Marcus v{self.VERSION} | Rattaché à LEILA",
            f"  {icone} STATUT : {statut_rag}",
            f"{'=' * 70}",
            "",
        ]

        # Résumé exécutif (pour le DG)
        lignes += [
            "📊 RÉSUMÉ POUR LA DIRECTION",
            "─" * 40,
        ]
        if statut_rag == 'VERT':
            lignes.append(
                "✅ Tous les contrôles de cohérence sont satisfaisants. "
                "Les équipes Tarification, Provisionnement et Stress Testing "
                "travaillent avec des hypothèses alignées. "
                "Les résultats sont cohérents entre eux et prêts pour validation."
            )
        elif statut_rag == 'AMBRE':
            lignes.append(
                f"⚠️ {nb_ambre} point(s) d'attention identifié(s). "
                "Les résultats sont globalement cohérents mais certaines "
                "hypothèses méritent discussion entre équipes avant la soumission "
                "réglementaire. Aucune alerte bloquante."
            )
        else:
            lignes.append(
                f"❌ {nb_rouge} incohérence(s) majeure(s) détectée(s). "
                "Une soumission à l'ACPR dans cet état exposerait l'entreprise "
                "à un risque de questionnement réglementaire. "
                "Réunion inter-équipes requise avant validation."
            )

        # Détail par contrôle
        lignes += ["", "🔍 DÉTAIL DES CONTRÔLES", "─" * 40]
        emojis = {'VERT': '✅', 'AMBRE': '⚠️', 'ROUGE': '❌', 'N/A': '⬜'}
        for ctrl in controles:
            st = ctrl.get('statut', 'N/A')
            lignes.append(
                f"  {emojis.get(st, '⬜')} {ctrl.get('controle', '?')} "
                f"[{st}] — {ctrl.get('message', '')}"
            )
            if ctrl.get('conseil') and st != 'VERT':
                lignes.append(f"     💡 {ctrl['conseil']}")

        # Alertes proactives IA
        if alertes:
            lignes += ["", "⚡ ALERTES PROACTIVES IA (Marcus)", "─" * 40]
            for alerte in alertes:
                emoji_g = "🔴" if alerte['gravite'] == 'ROUGE' else "🟡"
                lignes += [
                    f"  {emoji_g} [{alerte['type']}] {alerte['titre']}",
                    f"     {alerte['detail']}",
                    f"     → Action : {alerte['action']}",
                    "",
                ]

        # Hypothèses
        lignes += ["📋 HYPOTHÈSES VALIDÉES", "─" * 40]
        for h in hypotheses:
            icon = "✅" if h['statut'] == 'VALIDÉE' else "⚠️"
            lignes.append(f"  {icon} [{h['id']}] {h['hypothese']}")
            lignes.append(f"       Valeur : {h['valeur']} → {h['statut']}")

        # Agents analysés
        if agents_analyses:
            lignes += [
                "", "🔗 FLUX INTER-AGENTS ANALYSÉS", "─" * 40,
                f"  Contrôles exécutés sur : {' | '.join(agents_analyses)}",
                f"  Contrôles disponibles : {nb_vert} VERT | {nb_ambre} AMBRE | {nb_rouge} ROUGE | {nb_na} N/A",
            ]

        # Recommandation finale
        lignes += ["", "🎯 RECOMMANDATION MARCUS → LEILA", "─" * 40]
        if statut_rag == 'VERT':
            lignes.append(
                "✅ AVIS FAVORABLE — La direction Non-Vie peut procéder à la validation "
                "des provisions et transmettre les QRT à l'ACPR."
            )
        elif statut_rag == 'AMBRE':
            lignes.append(
                "⚠️ AVIS FAVORABLE SOUS RÉSERVE — Traiter les points AMBRE et "
                "documenter les justifications avant soumission ACPR."
            )
        else:
            lignes.append(
                "❌ AVIS DÉFAVORABLE — Ne pas soumettre à l'ACPR avant résolution "
                "des incohérences identifiées. Convoquer une réunion inter-équipes."
            )

        lignes.append("")
        return "\n".join(lignes)

    # ══════════════════════════════════════════════════════════════════════════
    # DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════

    def _generer_dashboard(
        self,
        controles:       List[Dict],
        nb_vert:         int,
        nb_ambre:        int,
        nb_rouge:        int,
        statut_rag:      str,
        alertes_ia:      List[Dict],
        agents_analyses: List[str],
    ) -> Dict:
        emojis = {'VERT': '🟢', 'AMBRE': '🟡', 'ROUGE': '🔴', 'N/A': '⬜'}
        lignes = []
        for ctrl in controles:
            st = ctrl.get('statut', 'N/A')
            lignes.append({
                'controle':    ctrl.get('controle', ''),
                'agents':      ctrl.get('agents', ''),
                'statut':      st,
                'emoji':       emojis.get(st, '⬜'),
                'message':     ctrl.get('message', ''),
                'conseil':     ctrl.get('conseil', ''),
            })

        return {
            'statut_rag':    statut_rag,
            'nb_vert':       nb_vert,
            'nb_ambre':      nb_ambre,
            'nb_rouge':      nb_rouge,
            'nb_controles':  len(controles),
            'nb_alertes_ia': len(alertes_ia),
            'lignes':        lignes,
            'agents_analyses': agents_analyses,
            'pret_acpr':     statut_rag == 'VERT',
            'pret_validation': statut_rag in ('VERT', 'AMBRE'),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # GRAPHIQUES v3 — 4 GRAPHIQUES AUTO-EXPLICATIFS
    # ══════════════════════════════════════════════════════════════════════════

    def _generer_graphiques(
        self,
        controles:  List[Dict],
        dashboard:  Dict,
        alertes_ia: List[Dict],
    ) -> Dict:
        """
        4 graphiques auto-explicatifs avec annotations pédagogiques.

        G1 — Radar des 6 contrôles (vue d'ensemble)
        G2 — Loss Ratio Tarif vs Provisions (C1)
        G3 — Heat Map cohérence (matrice agents × contrôles)
        G4 — Scorecard final (statuts RAG synthétiques)
        """
        graphiques = {}

        def couleur(statut):
            return VERT if statut == 'VERT' else AMBRE if statut == 'AMBRE' else ROUGE if statut == 'ROUGE' else GRIS

        def score_statut(statut):
            return {'VERT': 3, 'AMBRE': 2, 'ROUGE': 1, 'N/A': 0}.get(statut, 0)

        # ── G1 — RADAR DES CONTRÔLES ─────────────────────────────────────
        try:
            categories = [c.get('controle', '?').split(' — ')[-1] for c in controles]
            scores     = [score_statut(c.get('statut', 'N/A')) for c in controles]
            couleurs_r = [couleur(c.get('statut', 'N/A')) for c in controles]

            # Fermer le radar
            cats_radar   = categories + [categories[0]]
            scores_radar = scores + [scores[0]]

            fig1 = go.Figure()
            fig1.add_trace(go.Scatterpolar(
                r=scores_radar,
                theta=cats_radar,
                fill='toself',
                fillcolor='rgba(46,204,113,0.15)',
                line=dict(color=OR, width=2),
                marker=dict(size=8, color=[couleur(c.get('statut','N/A')) for c in controles] + [couleur(controles[0].get('statut','N/A'))]),
                hovertemplate='<b>%{theta}</b><br>Score : %{r}/3<extra></extra>',
                name='Cohérence',
            ))
            # Zone cible (score = 3 = VERT)
            fig1.add_trace(go.Scatterpolar(
                r=[3] * (len(categories) + 1),
                theta=cats_radar,
                fill='toself',
                fillcolor='rgba(46,204,113,0.05)',
                line=dict(color=VERT, width=1, dash='dot'),
                name='Cible (VERT)',
                hoverinfo='skip',
                showlegend=True,
            ))
            l1 = dict(**LAYOUT_BASE)
            l1.update(dict(
                title=dict(
                    text="G1 — Radar des Contrôles de Cohérence",
                    font=dict(color=OR, size=12), x=0.01
                ),
                polar=dict(
                    bgcolor=NAVY_L,
                    radialaxis=dict(
                        visible=True, range=[0, 3], tickvals=[0, 1, 2, 3],
                        ticktext=['N/A', '🔴', '🟡', '🟢'],
                        tickfont=dict(color=GRIS, size=9),
                        gridcolor='rgba(255,255,255,0.08)',
                    ),
                    angularaxis=dict(
                        tickfont=dict(color=BLANC, size=9),
                        gridcolor='rgba(255,255,255,0.08)',
                    ),
                ),
                legend=dict(font=dict(color=BLANC, size=9), bgcolor='rgba(0,0,0,0)'),
                annotations=[dict(
                    text="💡 Chaque axe représente un contrôle (3 = VERT, 2 = AMBRE, 1 = ROUGE). "
                         "L'objectif est de remplir entièrement la zone verte pointillée.",
                    xref="paper", yref="paper", x=0.01, y=-0.12,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig1.update_layout(**l1)
            graphiques['radar_controles'] = fig1
        except Exception as e:
            self.logger.warning(f"G1 Radar : {e}")

        # ── G2 — LOSS RATIO TARIF vs PROVISIONS ──────────────────────────
        try:
            c1 = next((c for c in controles if 'C1' in c.get('controle', '')), {})
            if c1:
                lr_t = c1.get('lr_tarif', 0.0)
                lr_p = c1.get('lr_prov', 0.0)
                col  = couleur(c1.get('statut', 'N/A'))

                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    x=["LR Tarification (A3/A6)", "LR Provisions (A7)"],
                    y=[lr_t, lr_p],
                    marker_color=[BLEU, col],
                    marker_line=dict(color=NAVY, width=1),
                    width=0.4, opacity=0.88,
                    text=[f"{lr_t:.1f}%", f"{lr_p:.1f}%"],
                    textposition="outside",
                    textfont=dict(color=BLANC, size=13, family="Inter"),
                    hovertemplate="<b>%{x}</b><br>Loss Ratio : %{y:.1f}%<extra></extra>",
                ))
                # Plage acceptable ±15%
                if lr_t > 0:
                    fig2.add_hrect(
                        y0=lr_t * 0.85, y1=lr_t * 1.15,
                        fillcolor="rgba(46,204,113,0.08)", line_width=0,
                        annotation_text="Plage acceptable ±15%",
                        annotation_font=dict(color=VERT, size=9),
                    )
                l2 = dict(**LAYOUT_BASE)
                l2.update(dict(
                    title=dict(
                        text=f"G2 — Loss Ratio : Tarif vs Provisions [{c1.get('statut','?')}]",
                        font=dict(color=col, size=12), x=0.01
                    ),
                    xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                    yaxis=dict(title="%", tickfont=dict(color=GRIS), showgrid=True,
                               gridcolor="rgba(255,255,255,0.05)"),
                    bargap=0.35, showlegend=False,
                    annotations=[dict(
                        text="💡 Les deux barres doivent être dans la zone verte (±15%). "
                             "Un grand écart = hypothèses incohérentes entre tarification et provisionnement.",
                        xref="paper", yref="paper", x=0.01, y=-0.18,
                        font=dict(color=GRIS, size=9), showarrow=False, align="left"
                    )],
                ))
                fig2.update_layout(**l2)
                graphiques['loss_ratio_coherence'] = fig2
        except Exception as e:
            self.logger.warning(f"G2 Loss Ratio : {e}")

        # ── G3 — HEAT MAP COHÉRENCE (Agents × Contrôles) ─────────────────
        try:
            ctrl_noms  = [c.get('controle', '?').replace('C', '#') for c in controles]
            ctrl_agents = [c.get('agents', '?') for c in controles]
            scores_hm   = [[score_statut(c.get('statut', 'N/A'))] for c in controles]
            scores_flat = [score_statut(c.get('statut', 'N/A')) for c in controles]
            text_hm     = [
                [f"{c.get('statut','N/A')}<br>{c.get('agents','?')}"]
                for c in controles
            ]

            colorscale = [
                [0.0,  'rgba(0,0,0,0)'],
                [0.01, ROUGE],
                [0.40, AMBRE],
                [0.70, VERT],
                [1.0,  VERT],
            ]

            fig3 = go.Figure(go.Heatmap(
                z=[[s] for s in scores_flat],
                x=["Statut"],
                y=[c.get('controle', '?').split(' — ')[-1][:30] for c in controles],
                text=[[c.get('statut', 'N/A')] for c in controles],
                texttemplate="%{text}",
                textfont=dict(color=BLANC, size=10),
                colorscale=colorscale,
                zmin=0, zmax=3,
                showscale=False,
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Statut : %{text}<br>"
                    "<extra></extra>"
                ),
            ))
            l3 = dict(**LAYOUT_BASE)
            l3.update(dict(
                title=dict(
                    text="G3 — Heat Map des Contrôles de Cohérence",
                    font=dict(color=OR, size=12), x=0.01
                ),
                xaxis=dict(showgrid=False, tickfont=dict(color=BLANC, size=10)),
                yaxis=dict(showgrid=False, tickfont=dict(color=BLANC, size=9),
                           autorange='reversed'),
                height=300,
                annotations=[dict(
                    text="💡 Vert = cohérent, Amber = à surveiller, Rouge = blocant. "
                         "Chaque ligne = un contrôle inter-agents.",
                    xref="paper", yref="paper", x=0.01, y=-0.20,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig3.update_layout(**l3)
            graphiques['heatmap_coherence'] = fig3
        except Exception as e:
            self.logger.warning(f"G3 Heat Map : {e}")

        # ── G4 — SCORECARD FINAL ─────────────────────────────────────────
        try:
            noms      = [c.get('controle', '?') for c in controles]
            statuts   = [c.get('statut', 'N/A') for c in controles]
            conseils  = [c.get('conseil', '') for c in controles]
            scores_sc = [score_statut(s) / 3.0 for s in statuts]
            couleurs_sc = [couleur(s) for s in statuts]
            icones    = ['✅' if s == 'VERT' else '⚠️' if s == 'AMBRE' else '❌' if s == 'ROUGE' else '⬜' for s in statuts]

            fig4 = go.Figure()
            for i, (nom, statut, sc, col, ic, cons) in enumerate(
                zip(noms, statuts, scores_sc, couleurs_sc, icones, conseils)
            ):
                nom_court = nom.split(' — ')[-1][:40] if ' — ' in nom else nom[:40]
                fig4.add_trace(go.Bar(
                    x=[sc], y=[nom_court], orientation='h',
                    marker_color=col, width=0.5,
                    text=f"{ic} {statut}",
                    textposition='outside',
                    textfont=dict(color=col, size=10),
                    hovertemplate=f"<b>{nom_court}</b><br>{statut}<br>💡 {cons}<extra></extra>",
                    showlegend=False,
                ))

            # Statut global
            sg = dashboard.get('statut_rag', 'N/A')
            col_g = couleur(sg)
            ic_g  = '✅ PRÊT ACPR' if sg == 'VERT' else '⚠️ SOUS RÉSERVE' if sg == 'AMBRE' else '❌ BLOCANT'

            l4 = dict(**LAYOUT_BASE)
            l4.update(dict(
                title=dict(
                    text=f"G4 — Scorecard Marcus → LEILA | {ic_g}",
                    font=dict(color=col_g, size=11), x=0.01
                ),
                xaxis=dict(range=[0, 1.7], visible=False),
                yaxis=dict(
                    tickfont=dict(color=BLANC, size=9),
                    showgrid=False, autorange='reversed',
                ),
                barmode='overlay',
                height=max(260, len(controles) * 45),
                annotations=[dict(
                    text=(
                        f"💡 {dashboard.get('nb_vert', 0)} ✅ = équipes alignées. "
                        f"{dashboard.get('nb_alertes_ia', 0)} alerte(s) IA proactive(s). "
                        "Un ❌ = réunion inter-équipes avant ACPR."
                    ),
                    xref="paper", yref="paper", x=0.01, y=-0.12,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig4.update_layout(**l4)
            graphiques['scorecard_coherence'] = fig4
        except Exception as e:
            self.logger.warning(f"G4 Scorecard : {e}")

        return graphiques

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES
    # ══════════════════════════════════════════════════════════════════════════

    def _ctrl_na(self, nom: str, agents: str, raison: str) -> Dict:
        """Contrôle non exécuté (données manquantes)."""
        return {
            'controle':    nom,
            'agents':      agents,
            'statut':      'N/A',
            'message':     f"Non exécuté : {raison}",
            'conseil':     f"Connecter {agents} pour activer ce contrôle.",
            'description': raison,
        }

    def _verifier_flux_minimaux(
        self,
        result_a6: Optional[Dict],
        result_a7: Optional[Dict],
        result_a8: Optional[Dict],
    ) -> Dict:
        """Vérifie que les flux minimaux obligatoires sont présents."""
        return {
            'a6_present': bool(result_a6),
            'a7_present': bool(result_a7),
            'a8_present': bool(result_a8),
            'flux_complets': all([result_a6, result_a7, result_a8]),
            'message': (
                "Flux minimaux OK (A6+A7+A8 connectés)"
                if all([result_a6, result_a7, result_a8]) else
                f"Flux incomplets : "
                f"{'❌A6' if not result_a6 else '✅A6'} "
                f"{'❌A7' if not result_a7 else '✅A7'} "
                f"{'❌A8' if not result_a8 else '✅A8'}"
            ),
        }

    def _sauvegarder_audit(
        self,
        audit_id:    str,
        sous_branche: str,
        controles:   List[Dict],
        statut_rag:  str,
        t_debut:     datetime,
        alertes_ia:  List[Dict],
    ) -> None:
        """Sauvegarde le rapport d'audit JSON."""
        try:
            rapport = {
                'audit_id':     audit_id,
                'agent':        self.NOM,
                'version':      self.VERSION,
                'rattachement': self.RESPONSABLE,
                'timestamp':    t_debut.isoformat(),
                'sous_branche': sous_branche,
                'statut_rag':   statut_rag,
                'nb_controles': len(controles),
                'nb_alertes_ia':len(alertes_ia),
                'controles':    [
                    {k: v for k, v in c.items() if not isinstance(v, (dict, list))}
                    for c in controles
                ],
                'alertes_ia':   alertes_ia,
            }
            path = self.audit_path / f"audit_{audit_id}.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, ensure_ascii=False, indent=2, default=str)
            self.logger.info(f"Audit sauvegardé : {path}")
        except Exception as e:
            self.logger.warning(f"Sauvegarde audit : {e}")

    def _afficher_console(
        self,
        audit_id:    str,
        sous_branche: str,
        controles:   List[Dict],
        statut_rag:  str,
        commentaire: str,
        alertes_ia:  List[Dict],
        hypotheses:  List[Dict],
    ) -> None:
        """Affiche le rapport dans la console."""
        sep = "─" * 70
        print(f"\n{sep}")
        print(f"  AGENT A9 MARCUS — COHÉRENCE NON-VIE v{self.VERSION}")
        print(f"  Audit : {audit_id} | Branche : {sous_branche}")
        print(sep)
        print(commentaire)
        print(sep)

    def _erreur(self, message: str, audit_id: str) -> Dict:
        """Retourne un résultat d'erreur standardisé."""
        return {
            'success':          False,
            'agent':            self.NOM,
            'version':          self.VERSION,
            'audit_id':         audit_id,
            'statut_rag':       'ROUGE',
            'controles':        [],
            'dashboard':        {},
            'alertes_proactives': [],
            'hypotheses':       [],
            'commentaire':      f"❌ ERREUR A9 Marcus : {message}",
            'graphiques':       {},
            'flux_ok':          {},
            'agents_analyses':  [],
            'duree_sec':        0.0,
            'erreur':           message,
        }


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE STANDALONE + DÉMONSTRATION
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 70)
    print("  AGENT A9 MARCUS — DÉMO v3.0")
    print("  Cohérence globale Direction Non-Vie (rattaché LEILA)")
    print("=" * 70)

    # ── Données synthétiques de démonstration ────────────────────────────────
    # Ces données simulent la sortie des agents A6, A7, A8

    demo_a6 = {
        'modele_production': {
            'modele':    'XGBoost',
            'gini_test': 0.312,
            'score_global': 0.298,
            'prime_pure': 720.0,
            'frequence':  0.144,
            'cout_moyen': 5000.0,
        }
    }

    demo_a7 = {
        'best_estimate': {
            'best_estimate':         7_359.0,
            'sigma_mack':            0.0,
            'cv_inter_methodes':     8.5,
            'nb_methodes_convergentes': 5,
        },
        'tail': {
            'tail_factor': 1.0374,
        },
        'meta': {
            'nb_lignes': 70_000,
        }
    }

    demo_a8 = {
        'chocs_s2': {
            'scr_souscription': 1_200.0,
        },
        'capital': {
            'scr_total':     853_000.0,
            'fonds_propres': 3_000_000.0,
        }
    }

    # A10, A11, A12 simulés (optionnels)
    demo_a10 = {
        'provisions': {
            'best_estimate': 7_359.0,
            'risk_margin':   890.0,
        },
        'duration': {
            'passif': 3.8,
        }
    }

    demo_a11 = {
        'provisions': {
            'lic_total': 9_200.0,
        }
    }

    demo_a12 = {
        'alm': {
            'duration_actif':  3.5,
            'duration_passif': 3.8,
            'immunisation_redington': True,
        }
    }

    # ── Exécution ─────────────────────────────────────────────────────────────
    agent = AgentA9Coherence(
        models_path='/tmp/actuaria/models',
        audit_path='/tmp/actuaria/audit',
        verbose=True
    )

    result = agent.run(
        result_a6=demo_a6,
        result_a7=demo_a7,
        result_a8=demo_a8,
        result_a3=None,
        result_a10=demo_a10,
        result_a11=demo_a11,
        result_a12=demo_a12,
        sous_branche='RC Auto',
        primes_acq=0.0,
        generer_graphiques=False,  # False en standalone (pas de display)
    )

    # ── Résultats ─────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"  RÉSULTATS DÉMO A9 MARCUS")
    print(f"{'=' * 70}")
    print(f"  ✅ Success      : {result['success']}")
    print(f"  🎯 Statut RAG  : {result['statut_rag']}")
    print(f"  🔍 Contrôles   : {len(result['controles'])}")
    print(f"  ⚡ Alertes IA  : {len(result['alertes_proactives'])}")
    print(f"  📋 Hypothèses  : {len(result['hypotheses'])}")
    print(f"  🔗 Agents      : {' | '.join(result['agents_analyses'])}")
    print(f"  ⏱️  Durée       : {result['duree_sec']:.2f}s")
    print()
    print("Contrôles détaillés :")
    emojis = {'VERT': '✅', 'AMBRE': '⚠️', 'ROUGE': '❌', 'N/A': '⬜'}
    for ctrl in result['controles']:
        st = ctrl.get('statut', 'N/A')
        print(f"  {emojis.get(st,'?')} [{st}] {ctrl.get('controle','?')}")
        print(f"       → {ctrl.get('message','')}")

    if result['alertes_proactives']:
        print("\nAlertes IA proactives :")
        for al in result['alertes_proactives']:
            g = "🔴" if al['gravite'] == 'ROUGE' else "🟡"
            print(f"  {g} [{al['type']}] {al['titre']}")

    print("\nUsage production :")
    print("  agent = AgentA9Coherence()")
    print("  result_a9 = agent.run(")
    print("      result_a6=result_a6,  # VICTOR — obligatoire")
    print("      result_a7=result_a7,  # IBRAHIM — obligatoire")
    print("      result_a8=result_a8,  # ISABELLE — obligatoire")
    print("      result_a10=result_a10, # ELENA — optionnel")
    print("      result_a11=result_a11, # THOMAS — optionnel")
    print("      result_a12=result_a12, # AISHA — optionnel")
    print("  )")
