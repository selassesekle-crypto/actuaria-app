# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  n3/backtesting.py  —  Back-testing boni/mali de liquidation
#
#  Conformité : Guide Institut des Actuaires 2023 — Section 4.3
#
#  Principe :
#    Pour chaque année de survenance i :
#    · Ultimate N-2 = projection CL depuis triangle tronqué à (n-2) colonnes
#    · Ultimate N-1 = projection CL depuis triangle tronqué à (n-1) colonnes
#    · Observé N    = dernière diagonale connue (sinistres actuels)
#    · Boni/Mali    = Ultimate projeté - Observé
#      > 0 : Boni (sur-provisionnement → libération de réserve)
#      < 0 : Mali (sous-provisionnement → insuffisance de réserve)
#
#  Seuil d'alerte : |écart| > 15% (guide IA 2023)
#  Seuil vigilance: |écart| > 8%
# =============================================================================

from __future__ import annotations
import logging
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger('actuaria.a7.backtesting')

SEUIL_ROUGE = 15.0
SEUIL_AMBRE = 8.0


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


def calculer_backtesting(
    C              : np.ndarray,
    annee_debut    : Optional[int] = None,
) -> Dict:
    """
    Calcule le tableau consolidé boni/mali N / N-1 / N-2.

    Parameters
    ----------
    C           : triangle cumulé complet (n×n)
    annee_debut : première année calendaire (optionnel, pour les labels)

    Returns
    -------
    Dict avec :
        tableau         : list de dicts par année (colonnes pro)
        totaux          : dict avec sommes et ratios globaux
        alertes         : list d'alertes (années hors seuil)
        statut          : VERT / AMBRE / ROUGE
        score_qualite   : 0-100
        ratio_stabilite : % d'années dans la zone verte
        message         : narration liée aux hypothèses
        success         : bool
    """
    n, m = C.shape

    if n < 4:
        return {
            'success': False,
            'erreur':  f'Triangle trop petit ({n} lignes) — minimum 4 requis',
            'tableau': [], 'totaux': {}, 'alertes': [],
            'statut': 'ROUGE', 'score_qualite': 0,
            'ratio_stabilite': 0, 'message': 'Back-testing impossible.',
        }

    # ── Calcul des ultimates pour k=1 et k=2 ─────────────────────────────────
    def _ult_tronque(k: int) -> np.ndarray:
        """Ultimates depuis triangle tronqué de k colonnes."""
        n_t = n - k
        m_t = m - k
        if n_t < 3 or m_t < 3:
            return np.zeros(n)
        C_t = C[:n_t, :m_t].copy()
        ult = _chain_ladder_simple(C_t)
        # Prolonger avec des zéros pour les années non calculées
        result = np.zeros(n)
        result[:n_t] = ult
        return result

    ult_n1 = _ult_tronque(1)  # Ultimate projeté à N-1
    ult_n2 = _ult_tronque(2)  # Ultimate projeté à N-2

    # Observé N = dernière valeur connue de chaque ligne
    obs_n = np.zeros(n)
    for i in range(n):
        for j in range(m - 1, -1, -1):
            if C[i, j] > 0:
                obs_n[i] = float(C[i, j])
                break

    # ── Construire le tableau consolidé ──────────────────────────────────────
    tableau   = []
    alertes   = []
    scores    = []
    n_vert = n_ambre = n_rouge = 0

    for i in range(n):
        obs  = float(obs_n[i])
        u_n1 = float(ult_n1[i])
        u_n2 = float(ult_n2[i])

        if obs <= 0:
            continue

        # Boni/Mali
        bm_n1 = u_n1 - obs if u_n1 > 0 else None
        bm_n2 = u_n2 - obs if u_n2 > 0 else None

        # Écarts %
        ep_n1 = (bm_n1 / obs * 100) if bm_n1 is not None else None
        ep_n2 = (bm_n2 / obs * 100) if bm_n2 is not None else None

        # Statut basé sur le pire écart disponible
        ecarts_abs = [abs(e) for e in [ep_n1, ep_n2] if e is not None]
        pire = max(ecarts_abs) if ecarts_abs else 0

        if pire >= SEUIL_ROUGE:
            statut_i = 'ROUGE'; n_rouge += 1
        elif pire >= SEUIL_AMBRE:
            statut_i = 'AMBRE'; n_ambre += 1
        else:
            statut_i = 'VERT'; n_vert += 1

        # Score (100 - écart moyen pondéré)
        scores.append(max(0, 100 - pire * 2))

        # Label année
        annee_label = str(annee_debut + i) if annee_debut else f"An. {i}"

        row = {
            'annee':         i,
            'annee_label':   annee_label,
            'observe_n':     round(obs, 0),
            'ultimate_n1':   round(u_n1, 0) if u_n1 > 0 else None,
            'ultimate_n2':   round(u_n2, 0) if u_n2 > 0 else None,
            'boni_mali_n1':  round(bm_n1, 0) if bm_n1 is not None else None,
            'boni_mali_n2':  round(bm_n2, 0) if bm_n2 is not None else None,
            'ecart_pct_n1':  round(ep_n1, 1) if ep_n1 is not None else None,
            'ecart_pct_n2':  round(ep_n2, 1) if ep_n2 is not None else None,
            'statut':        statut_i,
            'type_n1':       ('Boni' if bm_n1 > 0 else 'Mali') if bm_n1 is not None else '—',
            'type_n2':       ('Boni' if bm_n2 > 0 else 'Mali') if bm_n2 is not None else '—',
        }
        tableau.append(row)

        # Alertes
        if statut_i in ('ROUGE', 'AMBRE'):
            detail_n1 = f"N-1 : {ep_n1:+.1f}%" if ep_n1 is not None else ""
            detail_n2 = f"N-2 : {ep_n2:+.1f}%" if ep_n2 is not None else ""
            alertes.append({
                'annee':       i,
                'annee_label': annee_label,
                'statut':      statut_i,
                'ecart_pct_n1': ep_n1,
                'ecart_pct_n2': ep_n2,
                'message': (
                    f"{annee_label} — {detail_n1}  {detail_n2} — "
                    f"{'⚠️ Dépasse le seuil (15%)' if statut_i=='ROUGE' else '🟡 Vigilance (>8%)'}"
                ),
            })

    # ── Totaux ────────────────────────────────────────────────────────────────
    tot_obs  = sum(r['observe_n']   for r in tableau if r['observe_n'])
    tot_u_n1 = sum(r['ultimate_n1'] for r in tableau if r['ultimate_n1'])
    tot_u_n2 = sum(r['ultimate_n2'] for r in tableau if r['ultimate_n2'])
    tot_bm_n1 = tot_u_n1 - tot_obs if tot_u_n1 else None
    tot_bm_n2 = tot_u_n2 - tot_obs if tot_u_n2 else None
    tot_ep_n1 = (tot_bm_n1 / tot_obs * 100) if tot_bm_n1 and tot_obs else None
    tot_ep_n2 = (tot_bm_n2 / tot_obs * 100) if tot_bm_n2 and tot_obs else None

    totaux = {
        'observe_n':    round(tot_obs, 0),
        'ultimate_n1':  round(tot_u_n1, 0) if tot_u_n1 else None,
        'ultimate_n2':  round(tot_u_n2, 0) if tot_u_n2 else None,
        'boni_mali_n1': round(tot_bm_n1, 0) if tot_bm_n1 else None,
        'boni_mali_n2': round(tot_bm_n2, 0) if tot_bm_n2 else None,
        'ecart_pct_n1': round(tot_ep_n1, 1) if tot_ep_n1 else None,
        'ecart_pct_n2': round(tot_ep_n2, 1) if tot_ep_n2 else None,
    }

    # ── Statut global ─────────────────────────────────────────────────────────
    if n_rouge >= 3:     statut_global = 'ROUGE'
    elif n_rouge >= 1 or n_ambre >= 3: statut_global = 'AMBRE'
    else:                statut_global = 'VERT'

    score_global    = round(float(np.mean(scores)), 1) if scores else 0
    ratio_stabilite = round(n_vert / len(tableau) * 100, 1) if tableau else 0

    # ── Message narratif lié aux hypothèses ───────────────────────────────────
    sign_n1 = f"{tot_ep_n1:+.1f}%" if tot_ep_n1 else "—"
    sign_n2 = f"{tot_ep_n2:+.1f}%" if tot_ep_n2 else "—"
    type_gl_n1 = "BONI global" if (tot_bm_n1 or 0) > 0 else "MALI global"
    type_gl_n2 = "BONI global" if (tot_bm_n2 or 0) > 0 else "MALI global"

    msg_lignes = [
        f"BACK-TESTING BONI/MALI — Triangle {n}×{m}\n",
        f"Horizon N-1 : {type_gl_n1} = {sign_n1} "
        f"({n_rouge} alerte(s) rouge, {n_ambre} ambre).",
        f"Horizon N-2 : {type_gl_n2} = {sign_n2}.",
        f"Score qualité provisionnement : {score_global}/100 "
        f"— {ratio_stabilite:.0f}% des années dans la zone verte.",
    ]

    if n_rouge == 0 and n_ambre == 0:
        msg_lignes.append(
            "\nQualité du provisionnement historique BONNE — "
            "les projections passées sont cohérentes avec les observations actuelles."
        )
    elif n_rouge > 0 and (tot_bm_n1 or 0) > 0:
        msg_lignes.append(
            f"\nBONI significatifs sur les années les plus anciennes — "
            f"indique un sur-provisionnement probable sur ces cohortes. "
            f"Vérifier la présence de sinistres CAT NAT ou de grands sinistres "
            f"non isolés qui auraient gonflé les provisions initiales."
        )
    elif n_rouge > 0 and (tot_bm_n1 or 0) < 0:
        msg_lignes.append(
            f"\nMALI significatifs détectés — "
            f"sous-provisionnement sur {n_rouge} année(s). "
            f"Révision des facteurs de développement recommandée. "
            f"Consulter l'actuaire désigné avant inscription au bilan S2."
        )

    return {
        'success':          True,
        'tableau':          tableau,
        'totaux':           totaux,
        'alertes':          alertes,
        'statut':           statut_global,
        'score_qualite':    score_global,
        'ratio_stabilite':  ratio_stabilite,
        'n_vert':           n_vert,
        'n_ambre':          n_ambre,
        'n_rouge':          n_rouge,
        'message':          '\n'.join(msg_lignes),
        'horizons':         ['horizon_1', 'horizon_2'],
        # Compatibilité ancienne API
        'resultats': {
            'horizon_1': {'k': 1, 'annees': [
                {**r, 'ecart_pct': r['ecart_pct_n1'], 'boni_mali': r['boni_mali_n1'],
                 'annee': r['annee'], 'statut': r['statut']}
                for r in tableau if r['ultimate_n1']
            ]},
            'horizon_2': {'k': 2, 'annees': [
                {**r, 'ecart_pct': r['ecart_pct_n2'], 'boni_mali': r['boni_mali_n2'],
                 'annee': r['annee'], 'statut': r['statut']}
                for r in tableau if r['ultimate_n2']
            ]},
        },
    }
