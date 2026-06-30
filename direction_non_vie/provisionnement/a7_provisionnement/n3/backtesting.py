# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  n3/backtesting.py  —  Back-testing boni/mali de liquidation
#
#  Conformité : Guide Institut des Actuaires 2023 — Section 4.3
#
#  Principe :
#    · Seules les années avec pct_développé >= seuil_maturite sont évaluées
#    · Ultimate N-1 = projection CL depuis triangle tronqué à (n-1) colonnes
#    · Ultimate N-2 = projection CL depuis triangle tronqué à (n-2) colonnes
#    · Observé N    = dernière diagonale connue
#    · Boni/Mali    = Ultimate projeté - Observé
#
#  Comptage alertes : séparé N-1 et N-2 (pas le pire des deux)
#  Statut global    : ROUGE si rouge N-1 OU rouge N-2 sur années matures
#  Score            : moyenne (score N-1 + score N-2) sur années matures
# =============================================================================

from __future__ import annotations
import logging
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger('actuaria.a7.backtesting')

SEUIL_ROUGE    = 15.0   # guide IA 2023
SEUIL_AMBRE    = 8.0
SEUIL_MATURITE = 0.75   # % développement minimum pour être évalué


def _chain_ladder_simple(C: np.ndarray) -> np.ndarray:
    """Chain Ladder volume_weighted sur triangle tronqué. Retourne les ultimates."""
    n, m = C.shape
    facteurs = []
    for j in range(m - 1):
        num = sum(C[i, j+1] for i in range(n - j - 1) if C[i, j] > 0)
        den = sum(C[i, j]   for i in range(n - j - 1) if C[i, j] > 0)
        facteurs.append(num / den if den > 0 else 1.0)

    f_cum = np.ones(m)
    for j in range(m - 2, -1, -1):
        f_cum[j] = f_cum[j+1] * (facteurs[j] if j < len(facteurs) else 1.0)

    ultimates = np.zeros(n)
    for i in range(n):
        last_j = 0
        for j in range(m - 1, -1, -1):
            if C[i, j] > 0:
                last_j = j
                break
        ultimates[i] = C[i, last_j] * f_cum[last_j] if f_cum[last_j] > 0 else C[i, last_j]
    return ultimates


def _pct_developpe(C: np.ndarray) -> np.ndarray:
    """Calcule le % développé pour chaque ligne (ligne / max de la colonne finale)."""
    n, m = C.shape
    pct = np.zeros(n)
    # Ultimate estimé = dernière valeur × facteur cumulé restant
    ult = _chain_ladder_simple(C)
    for i in range(n):
        if ult[i] > 0:
            # Dernière colonne observée
            last_j = 0
            last_val = 0.0
            for j in range(m - 1, -1, -1):
                if C[i, j] > 0:
                    last_j   = j
                    last_val = float(C[i, j])
                    break

            # Règle Guide IA : si seulement 1 ou 2 colonnes observées
            # → toujours immature quel que soit le pct calculé
            # (LDF proche de 1.0 peut donner pct ≈ 100% à tort)
            if last_j == 0:
                pct[i] = 0.0  # 1 seule colonne → immature
            elif last_j == 1 and n >= 10:
                pct[i] = 0.0  # 2 colonnes sur grand triangle → immature
            else:
                pct[i] = last_val / ult[i] if ult[i] > 0 else 0.0
    return np.clip(pct, 0.0, 1.0)


def calculer_backtesting(
    C              : np.ndarray,
    annee_debut    : Optional[int] = None,
    seuil_maturite : float = SEUIL_MATURITE,
) -> Dict:
    """
    Calcule le tableau consolidé boni/mali N / N-1 / N-2.

    Parameters
    ----------
    C               : triangle cumulé complet (n×n)
    annee_debut     : première année calendaire (optionnel)
    seuil_maturite  : % développement minimum pour évaluation (défaut 75%)

    Returns
    -------
    Dict structuré avec tableau, totaux, alertes, statut, scores
    """
    n, m = C.shape

    if n < 4:
        return {
            'success': False,
            'erreur':  f'Triangle trop petit ({n} lignes) — minimum 4 requis',
            'tableau': [], 'totaux': {}, 'alertes': [],
            'statut': 'ROUGE', 'score_qualite': 0,
            'ratio_stabilite': 0, 'message': 'Back-testing impossible.',
            'n_rouge_n1': 0, 'n_rouge_n2': 0,
            'n_ambre_n1': 0, 'n_ambre_n2': 0,
            'n_rouge': 0, 'n_ambre': 0, 'n_vert': 0,
        }

    # ── % développé par ligne ─────────────────────────────────────────────────
    pct_dev = _pct_developpe(C)

    # ── Ultimates tronqués ────────────────────────────────────────────────────
    def _ult_tronque(k: int) -> np.ndarray:
        n_t = n - k; m_t = m - k
        if n_t < 3 or m_t < 3: return np.zeros(n)
        C_t = C[:n_t, :m_t].copy()
        ult = _chain_ladder_simple(C_t)
        result = np.zeros(n)
        result[:n_t] = ult
        return result

    ult_n1 = _ult_tronque(1)
    ult_n2 = _ult_tronque(2)

    # Observé N = dernière valeur connue de chaque ligne
    obs_n = np.zeros(n)
    for i in range(n):
        for j in range(m - 1, -1, -1):
            if C[i, j] > 0:
                obs_n[i] = float(C[i, j])
                break

    # ── Construire le tableau ─────────────────────────────────────────────────
    tableau = []

    # Compteurs séparés N-1 et N-2 — sur années matures uniquement
    n_rouge_n1 = n_ambre_n1 = n_vert_n1 = 0
    n_rouge_n2 = n_ambre_n2 = n_vert_n2 = 0
    scores_n1 = []; scores_n2 = []
    alertes = []

    for i in range(n):
        obs    = float(obs_n[i])
        u_n1   = float(ult_n1[i])
        u_n2   = float(ult_n2[i])
        pct_i  = float(pct_dev[i])
        mature = pct_i >= seuil_maturite

        if obs <= 0: continue

        # Boni/Mali
        bm_n1 = round(u_n1 - obs, 0) if u_n1 > 0 else None
        bm_n2 = round(u_n2 - obs, 0) if u_n2 > 0 else None
        ep_n1 = round(bm_n1 / obs * 100, 1) if bm_n1 is not None else None
        ep_n2 = round(bm_n2 / obs * 100, 1) if bm_n2 is not None else None

        # Statut par horizon — uniquement si année mature
        def _statut_h(ep):
            if ep is None or not mature: return None
            a = abs(ep)
            return 'ROUGE' if a >= SEUIL_ROUGE else 'AMBRE' if a >= SEUIL_AMBRE else 'VERT'

        stat_n1 = _statut_h(ep_n1)
        stat_n2 = _statut_h(ep_n2)

        # Compter sur années matures
        if mature:
            if stat_n1 == 'ROUGE': n_rouge_n1 += 1
            elif stat_n1 == 'AMBRE': n_ambre_n1 += 1
            elif stat_n1 == 'VERT': n_vert_n1 += 1
            if ep_n1 is not None: scores_n1.append(max(0, 100 - abs(ep_n1) * 2))

            if stat_n2 == 'ROUGE': n_rouge_n2 += 1
            elif stat_n2 == 'AMBRE': n_ambre_n2 += 1
            elif stat_n2 == 'VERT': n_vert_n2 += 1
            if ep_n2 is not None: scores_n2.append(max(0, 100 - abs(ep_n2) * 2))

        # Statut global de la ligne (affichage tableau)
        pires = [s for s in [stat_n1, stat_n2] if s]
        if 'ROUGE' in pires: statut_ligne = 'ROUGE'
        elif 'AMBRE' in pires: statut_ligne = 'AMBRE'
        elif 'VERT' in pires: statut_ligne = 'VERT'
        else: statut_ligne = 'NON_ÉVALUÉ'

        annee_label = str(annee_debut + i) if annee_debut else f"An. {i}"

        tableau.append({
            'annee':         i,
            'annee_label':   annee_label,
            'observe_n':     round(obs, 0),
            'ultimate_n1':   round(u_n1, 0) if u_n1 > 0 else None,
            'ultimate_n2':   round(u_n2, 0) if u_n2 > 0 else None,
            'boni_mali_n1':  bm_n1,
            'boni_mali_n2':  bm_n2,
            'ecart_pct_n1':  ep_n1,
            'ecart_pct_n2':  ep_n2,
            'statut_n1':     stat_n1,
            'statut_n2':     stat_n2,
            'statut':        statut_ligne,
            'pct_developpe': round(pct_i * 100, 1),
            'mature':        mature,
            'type_n1':       ('Boni' if bm_n1 > 0 else 'Mali') if bm_n1 is not None else '—',
            'type_n2':       ('Boni' if bm_n2 > 0 else 'Mali') if bm_n2 is not None else '—',
        })

        # Alertes (années matures uniquement)
        if mature and statut_ligne in ('ROUGE', 'AMBRE'):
            alertes.append({
                'annee': i, 'annee_label': annee_label,
                'statut': statut_ligne,
                'ecart_pct_n1': ep_n1, 'ecart_pct_n2': ep_n2,
                'pct_developpe': round(pct_i * 100, 1),
            })

    # ── Totaux ────────────────────────────────────────────────────────────────
    tot_obs  = sum(r['observe_n']   for r in tableau if r['observe_n'])
    tot_u_n1 = sum(r['ultimate_n1'] for r in tableau if r['ultimate_n1'])
    tot_u_n2 = sum(r['ultimate_n2'] for r in tableau if r['ultimate_n2'])
    tot_bm_n1 = round(tot_u_n1 - tot_obs, 0) if tot_u_n1 else None
    tot_bm_n2 = round(tot_u_n2 - tot_obs, 0) if tot_u_n2 else None
    tot_ep_n1 = round(tot_bm_n1 / tot_obs * 100, 1) if tot_bm_n1 and tot_obs else None
    tot_ep_n2 = round(tot_bm_n2 / tot_obs * 100, 1) if tot_bm_n2 and tot_obs else None

    totaux = {
        'observe_n':    round(tot_obs, 0),
        'ultimate_n1':  round(tot_u_n1, 0) if tot_u_n1 else None,
        'ultimate_n2':  round(tot_u_n2, 0) if tot_u_n2 else None,
        'boni_mali_n1': tot_bm_n1,
        'boni_mali_n2': tot_bm_n2,
        'ecart_pct_n1': tot_ep_n1,
        'ecart_pct_n2': tot_ep_n2,
    }

    # ── Scores séparés ────────────────────────────────────────────────────────
    score_n1 = round(float(np.mean(scores_n1)), 1) if scores_n1 else 100.0
    score_n2 = round(float(np.mean(scores_n2)), 1) if scores_n2 else 100.0
    score_global = round((score_n1 + score_n2) / 2, 1) if (scores_n1 or scores_n2) else 100.0

    # ── Statut global ─────────────────────────────────────────────────────────
    n_rouge = max(n_rouge_n1, n_rouge_n2)
    n_ambre = max(n_ambre_n1, n_ambre_n2)
    n_vert  = min(n_vert_n1, n_vert_n2) if (n_vert_n1 and n_vert_n2) else max(n_vert_n1, n_vert_n2)

    if n_rouge >= 1:   statut_global = 'ROUGE'
    elif n_ambre >= 1: statut_global = 'AMBRE'
    else:              statut_global = 'VERT'

    n_matures = sum(1 for r in tableau if r['mature'])
    ratio_stabilite = round(
        sum(1 for r in tableau if r['mature'] and r['statut'] == 'VERT') / n_matures * 100, 1
    ) if n_matures else 100.0

    # ── Message narratif ──────────────────────────────────────────────────────
    msg = (
        f"Analyse sur {n_matures} années matures (≥{seuil_maturite*100:.0f}% développées) "
        f"sur {n} au total.\n"
        f"Horizon N-1 : {n_rouge_n1} alerte(s) rouge · {n_ambre_n1} ambre · "
        f"{n_vert_n1} OK — Score {score_n1}/100\n"
        f"Horizon N-2 : {n_rouge_n2} alerte(s) rouge · {n_ambre_n2} ambre · "
        f"{n_vert_n2} OK — Score {score_n2}/100"
    )

    if statut_global == 'VERT':
        msg += (
            "\n\nQualité du provisionnement historique BONNE — "
            "aucun écart significatif sur les années matures."
        )
    elif (tot_bm_n1 or 0) > 0:
        msg += (
            "\n\nBoni significatifs détectés — sur-provisionnement probable "
            "sur certaines cohortes. Vérifier la présence de sinistres CAT NAT "
            "ou de grands sinistres non isolés dans le triangle."
        )
    else:
        msg += (
            "\n\nMali détectés — sous-provisionnement sur certaines années matures. "
            "Révision des hypothèses de développement recommandée avant inscription au bilan S2."
        )

    return {
        'success':          True,
        'tableau':          tableau,
        'totaux':           totaux,
        'alertes':          alertes,
        'statut':           statut_global,
        'score_qualite':    score_global,
        'score_n1':         score_n1,
        'score_n2':         score_n2,
        'ratio_stabilite':  ratio_stabilite,
        'n_rouge':          n_rouge,
        'n_ambre':          n_ambre,
        'n_vert':           n_vert,
        'n_rouge_n1':       n_rouge_n1,
        'n_rouge_n2':       n_rouge_n2,
        'n_ambre_n1':       n_ambre_n1,
        'n_ambre_n2':       n_ambre_n2,
        'n_vert_n1':        n_vert_n1,
        'n_vert_n2':        n_vert_n2,
        'n_matures':        n_matures,
        'seuil_maturite':   seuil_maturite,
        'message':          msg,
        'horizons':         ['horizon_1', 'horizon_2'],
        # Compatibilité ancienne API
        'resultats': {
            'horizon_1': {'k': 1, 'annees': [
                {**r, 'ecart_pct': r['ecart_pct_n1'], 'boni_mali': r['boni_mali_n1']}
                for r in tableau if r['ultimate_n1']
            ]},
            'horizon_2': {'k': 2, 'annees': [
                {**r, 'ecart_pct': r['ecart_pct_n2'], 'boni_mali': r['boni_mali_n2']}
                for r in tableau if r['ultimate_n2']
            ]},
        },
    }
