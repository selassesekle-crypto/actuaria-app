# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  n3/backtesting.py  —  Back-testing boni/mali de liquidation
#
#  Conformité : Guide Institut des Actuaires 2023 — Section 4.3
#
#  Principe :
#    Pour chaque horizon de recul k (k=1, k=2) :
#    1. Tronquer le triangle à la colonne (n - k) → triangle "passé"
#    2. Appliquer Chain Ladder sur ce triangle tronqué
#    3. Comparer les ultimates projetés avec la diagonale actuelle
#    4. Calculer boni/mali = ultimate_projeté - sinistres_observés
#
#  Interprétation :
#    · Boni (positif)  : sur-provisionnement → libération de réserve
#    · Mali (négatif)  : sous-provisionnement → insuffisance de réserve
#    · Seuil alerte    : |écart| > 15% (guide IA 2023)
#
# =============================================================================

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger('actuaria.a7.backtesting')

# Seuil d'alerte guide IA 2023
SEUIL_ALERTE_PCT = 15.0
SEUIL_AMBRE_PCT  = 8.0


def _chain_ladder_simple(C: np.ndarray, methode: str = 'volume_weighted') -> np.ndarray:
    """
    Chain Ladder simplifié sur un triangle tronqué.
    Retourne les ultimates projetés (array de longueur n).
    """
    n, m = C.shape

    # Facteurs volume_weighted
    facteurs = []
    for j in range(m - 1):
        num = sum(C[i, j+1] for i in range(n - j - 1) if C[i, j] > 0)
        den = sum(C[i, j]   for i in range(n - j - 1) if C[i, j] > 0)
        facteurs.append(num / den if den > 0 else 1.0)

    # Tail factor = 1.0 (triangle supposé complet à la dernière colonne)
    tail = 1.0

    # Facteurs cumulés (de droite à gauche)
    f_cum = np.ones(m)
    f_cum[-1] = tail
    for j in range(m - 2, -1, -1):
        f_cum[j] = f_cum[j+1] * (facteurs[j] if j < len(facteurs) else 1.0)

    # Ultimates
    ultimates = np.zeros(n)
    for i in range(n):
        # Dernière valeur non nulle de la ligne i
        last_j = 0
        for j in range(m - 1, -1, -1):
            if C[i, j] > 0:
                last_j = j
                break
        if f_cum[last_j] > 0:
            ultimates[i] = C[i, last_j] * f_cum[last_j]
        else:
            ultimates[i] = C[i, last_j]

    return ultimates


def calculer_backtesting(
    C          : np.ndarray,
    horizons   : List[int] = [1, 2],
    methode_cl : str       = 'volume_weighted',
    seuil_alerte: float    = SEUIL_ALERTE_PCT,
) -> Dict:
    """
    Calcule les boni/mali de liquidation sur les horizons demandés.

    Parameters
    ----------
    C           : triangle cumulé complet (n×n)
    horizons    : liste des horizons de recul en périodes (défaut [1, 2])
    methode_cl  : variante Chain Ladder pour le triangle tronqué
    seuil_alerte: seuil % au-delà duquel une alerte est générée (guide IA 2023 : 15%)

    Returns
    -------
    Dict avec :
        resultats       : liste de dicts par horizon × année de survenance
        synthese        : boni/mali total par horizon
        alertes         : années avec écart > seuil
        statut          : VERT / AMBRE / ROUGE
        score_qualite   : 0-100 (qualité du provisionnement historique)
        message         : narration
    """
    n, m = C.shape

    if n < 4:
        return {
            'success': False,
            'erreur':  f'Triangle trop petit ({n} années) — minimum 4 requis pour le back-testing',
            'resultats': [], 'synthese': {}, 'alertes': [], 'statut': 'ROUGE',
            'score_qualite': 0, 'message': 'Back-testing impossible — triangle insuffisant.',
        }

    resultats_par_horizon = {}
    toutes_alertes        = []
    scores_horizon        = []

    for k in horizons:
        if k >= n - 2:
            logger.warning(f"Horizon {k} ignoré — triangle trop petit")
            continue

        # ── Triangle tronqué : on enlève les k dernières colonnes ────────────
        # Simuler ce qu'on aurait calculé k périodes en arrière :
        # · On prend les n-k premières lignes et m-k premières colonnes
        # · La "diagonale passée" = colonne (m-k-1)
        n_tronc = n - k
        m_tronc = m - k
        C_tronc = C[:n_tronc, :m_tronc].copy()

        # ── Ultimates projetés depuis le triangle tronqué ────────────────────
        ult_projetes = _chain_ladder_simple(C_tronc, methode=methode_cl)

        # ── Diagonale actuelle (sinistres observés k périodes plus tard) ─────
        # Pour chaque année i < n_tronc, la valeur observée aujourd'hui
        # est sur la diagonale de C (colonne min(i + k, m-1))
        diag_actuelle = np.zeros(n_tronc)
        for i in range(n_tronc):
            j_obs = min(i + k, m - 1)  # colonne k périodes plus tard
            diag_actuelle[i] = float(C[i, j_obs])

        # ── Boni/Mali ─────────────────────────────────────────────────────────
        resultats_annees = []
        n_alertes_rouge  = 0
        n_alertes_ambre  = 0
        ecarts_pct_abs   = []

        for i in range(n_tronc):
            ult_p  = float(ult_projetes[i])
            obs    = float(diag_actuelle[i])

            if obs <= 0 or ult_p <= 0:
                continue

            boni_mali     = ult_p - obs          # positif = boni, négatif = mali
            ecart_pct     = (boni_mali / obs) * 100
            ecart_abs_pct = abs(ecart_pct)
            ecarts_pct_abs.append(ecart_abs_pct)

            statut_annee = (
                'ROUGE' if ecart_abs_pct > seuil_alerte else
                'AMBRE' if ecart_abs_pct > SEUIL_AMBRE_PCT else
                'VERT'
            )

            if statut_annee == 'ROUGE': n_alertes_rouge += 1
            if statut_annee == 'AMBRE': n_alertes_ambre += 1

            annee_result = {
                'annee':          i,
                'horizon':        k,
                'ultimate_projete': round(ult_p, 2),
                'observe':          round(obs, 2),
                'boni_mali':        round(boni_mali, 2),
                'ecart_pct':        round(ecart_pct, 2),
                'statut':           statut_annee,
                'type':             'Boni' if boni_mali > 0 else 'Mali',
            }
            resultats_annees.append(annee_result)

            if statut_annee in ('ROUGE', 'AMBRE'):
                toutes_alertes.append({
                    'annee':    i,
                    'horizon':  k,
                    'ecart_pct': round(ecart_pct, 2),
                    'statut':   statut_annee,
                    'message': (
                        f"Année {i} — horizon {k} : écart {ecart_pct:+.1f}% "
                        f"({'BONI' if boni_mali > 0 else 'MALI'}) — "
                        f"{'⚠️ dépasse le seuil IA 2023 (15%)' if statut_annee=='ROUGE' else '🟡 vigilance'}"
                    ),
                })

        # ── Synthèse horizon k ────────────────────────────────────────────────
        total_ult = sum(r['ultimate_projete'] for r in resultats_annees)
        total_obs = sum(r['observe']          for r in resultats_annees)
        total_bm  = total_ult - total_obs
        ecart_global_pct = (total_bm / total_obs * 100) if total_obs > 0 else 0

        # Score qualité horizon (100 - moyenne des écarts abs pondérée)
        if ecarts_pct_abs:
            score_h = max(0, 100 - np.mean(ecarts_pct_abs) * 2)
        else:
            score_h = 100

        scores_horizon.append(score_h)

        resultats_par_horizon[f'horizon_{k}'] = {
            'k':               k,
            'annees':          resultats_annees,
            'total_ult':       round(total_ult, 2),
            'total_obs':       round(total_obs, 2),
            'total_boni_mali': round(total_bm, 2),
            'ecart_global_pct': round(ecart_global_pct, 2),
            'n_alertes_rouge': n_alertes_rouge,
            'n_alertes_ambre': n_alertes_ambre,
            'score_qualite':   round(score_h, 1),
            'type_global':     'Boni' if total_bm > 0 else 'Mali',
        }

    # ── Statut global ─────────────────────────────────────────────────────────
    n_rouge_total = sum(
        h['n_alertes_rouge'] for h in resultats_par_horizon.values()
    )
    n_ambre_total = sum(
        h['n_alertes_ambre'] for h in resultats_par_horizon.values()
    )

    if n_rouge_total >= 3:
        statut_global = 'ROUGE'
    elif n_rouge_total >= 1 or n_ambre_total >= 3:
        statut_global = 'AMBRE'
    else:
        statut_global = 'VERT'

    score_global = round(np.mean(scores_horizon), 1) if scores_horizon else 0

    # ── Message narratif ──────────────────────────────────────────────────────
    lignes_msg = [
        f"BACK-TESTING BONI/MALI — {len(horizons)} horizon(s) analysé(s)\n"
    ]
    for k_str, h in resultats_par_horizon.items():
        k = h['k']
        sign  = '+' if h['total_boni_mali'] >= 0 else ''
        type_ = 'BONI' if h['total_boni_mali'] >= 0 else 'MALI'
        lignes_msg.append(
            f"Horizon N-{k} : {type_} global = {sign}{h['total_boni_mali']:,.0f} € "
            f"({sign}{h['ecart_global_pct']:.1f}%) — "
            f"{h['n_alertes_rouge']} alerte(s) rouge, {h['n_alertes_ambre']} ambre. "
            f"Score qualité : {h['score_qualite']}/100."
        )

    if n_rouge_total == 0 and n_ambre_total == 0:
        lignes_msg.append(
            "\nQualité du provisionnement historique BONNE — "
            "les projections passées sont cohérentes avec les observations actuelles. "
            "Aucun écart significatif détecté (seuil guide IA 2023 : 15%)."
        )
    elif n_rouge_total > 0:
        lignes_msg.append(
            f"\nATTENTION : {n_rouge_total} année(s) dépassent le seuil d'alerte de {seuil_alerte:.0f}% "
            "du guide Institut des Actuaires 2023. "
            "Une révision des hypothèses de développement est recommandée."
        )
    else:
        lignes_msg.append(
            f"\nVIGILANCE : {n_ambre_total} année(s) présentent des écarts modérés "
            f"(>{SEUIL_AMBRE_PCT:.0f}%). Suivi recommandé au prochain arrêté."
        )

    return {
        'success':          True,
        'resultats':        resultats_par_horizon,
        'alertes':          toutes_alertes,
        'statut':           statut_global,
        'score_qualite':    score_global,
        'n_rouge':          n_rouge_total,
        'n_ambre':          n_ambre_total,
        'message':          '\n'.join(lignes_msg),
        'seuil_alerte_pct': seuil_alerte,
        'methode_cl':       methode_cl,
        'horizons':         horizons,
    }


def tableau_boni_mali(bt_result: Dict, horizon: int = 2) -> List[Dict]:
    """
    Extrait un tableau boni/mali pour un horizon donné.
    Format adapté pour affichage Streamlit et rapport Word.

    Returns
    -------
    List de dicts avec clés : annee, ultimate_projete, observe, boni_mali, ecart_pct, statut
    """
    h_key = f'horizon_{horizon}'
    if not bt_result.get('success') or h_key not in bt_result.get('resultats', {}):
        return []
    return bt_result['resultats'][h_key].get('annees', [])
