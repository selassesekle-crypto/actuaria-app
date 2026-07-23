# =============================================================================
#  ActuarIA — Direction Non-Vie / Service Data
#  nv_triangle_projection.py — Projection déterministe des ultimates (Chain-Ladder)
#
#  SOURCE UNIQUE du motif « projeter l'ultime depuis la dernière diagonale via
#  les facteurs restants, puis IBNR = ultime − dernière diagonale ». Remplace
#  les copies déterministes de Chain Ladder, Munich CL et de la référence
#  Bootstrap (_reserve_cl_simple).
#
#  Le helper NE DÉCIDE PAS quel chiffre utiliser en production : il expose à la
#  fois l'IBNR BRUT (peut être < 0 : recours / sur-développement) et l'IBNR
#  PLANCHERÉ (max(·, 0), comportement historique). Le choix brut vs plancher
#  appartient aux méthodes appelantes (branchement dans les lots suivants).
#
#  HORS PÉRIMÈTRE : le plancher du Bootstrap PAR SIMULATION (accumulation
#  stochastique avec bruit de processus + plancher d'incrément) est un motif
#  DIFFÉRENT — non couvert ici, traité séparément dans le lot Bootstrap.
#
#  Dépendance : numpy seul. Importé par n3 (méthodes). Aucun cablage de décision.
#
#  AUTEUR : ActuarIA
# =============================================================================
from __future__ import annotations

from typing import Dict

import numpy as np


def projeter_ultimates(
    C:        np.ndarray,
    facteurs: np.ndarray,
    *,
    tail_factor: float = 1.0,
    annee_base:  int   = 1,
) -> Dict:
    """
    Projette l'ultime et l'IBNR par année de survenance (Chain-Ladder déterministe).

    Pour chaque année i :
        k_i     = min(n-i-1, m-1)              dernière colonne connue
        ultime  = C[i, k_i] × Π_{j=k_i}^{m-2} facteurs[j] × tail_factor
        IBNR    = ultime − C[i, k_i]

    Reproduit EXACTEMENT la boucle historique de Chain Ladder (avec tail),
    Munich CL (tail=1.0) et Bootstrap _reserve_cl_simple (tail=1.0).

    Parameters
    ----------
    C : np.ndarray (n, m)  — triangle cumulé.
    facteurs : np.ndarray (m-1,)  — facteurs de développement.
    tail_factor : float  — facteur de queue (1.0 = pas de tail).
    annee_base : int  — première année incluse dans les agrégats (défaut 1).

    Returns
    -------
    dict :
        ultimate         : np.ndarray (n,)
        last_diag        : np.ndarray (n,)   — dernière diagonale connue par année
        ibnr_brut        : np.ndarray (n,)   — ultime − last_diag, SANS plancher (peut être < 0)
        ibnr_plancher    : np.ndarray (n,)   — max(ibnr_brut, 0)   (comportement historique)
        reserve_brute    : float             — Σ ibnr_brut[annee_base:]     (recours nets compris)
        reserve_plancher : float             — Σ ibnr_plancher[annee_base:] (historique)
        n_annees_reprise : int               — nb d'années à ibnr_brut < 0  (sur annee_base:)
    """
    n, m = C.shape
    facteurs = np.asarray(facteurs, dtype=float)

    ultimate      = np.zeros(n)
    last_diag     = np.zeros(n)
    ibnr_brut     = np.zeros(n)
    ibnr_plancher = np.zeros(n)

    for i in range(n):
        k_i = min(n - i - 1, m - 1)
        ld  = float(C[i, k_i])
        val = ld
        for j in range(k_i, m - 1):
            if j < len(facteurs):
                val *= float(facteurs[j])
        val *= tail_factor

        last_diag[i]     = ld
        ultimate[i]      = val
        ibnr_brut[i]     = val - ld
        ibnr_plancher[i] = max(val - ld, 0.0)

    idx = max(0, min(int(annee_base), n - 1))
    return {
        'ultimate':         ultimate,
        'last_diag':        last_diag,
        'ibnr_brut':        ibnr_brut,
        'ibnr_plancher':    ibnr_plancher,
        'reserve_brute':    float(np.sum(ibnr_brut[idx:])),
        'reserve_plancher': float(np.sum(ibnr_plancher[idx:])),
        'n_annees_reprise': int(np.sum(ibnr_brut[idx:] < 0)),
    }
