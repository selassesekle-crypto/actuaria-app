# =============================================================================
#  ActuarIA — Direction Non-Vie / Service Data
#  nv_triangle_negatifs.py — Detection et politique des valeurs non positives
#
#  Deux outils PARTAGES, purs (numpy seul), sans dependance externe :
#
#    · signaler_negatifs(C)   — DETECTE et REPORTE les cumules negatifs et les
#      inversions d'un triangle cumule. NE TRANSFORME JAMAIS C. Destine a la
#      couche donnees (rapport du triangle) et aux methodes de RATIO
#      (Chain Ladder, Mack, Munich CL), qui tolerent un cumule qui redescend
#      (recours / subrogation) et doivent le SIGNALER sans l'exclure.
#
#    · increments_positifs(C) — POLITIQUE de positivite des INCREMENTS pour la
#      famille de methodes qui les exigent > 0 (log-normal / Poisson) :
#      Barnett-Zehnwirth, GLM APC Poisson, Clark, Bootstrap ODP. Selon le
#      parametre `plancher`, exclut (None) ou plafonne par le bas (valeur) les
#      increments <= 0.
#
#  Convention de zone connue (identique a n3) : cellule (i, j) observee
#  <=> i + j < n  (n = nombre de lignes / annees de survenance).
#
#  Dependance descendante : importe par les services (construction du triangle)
#  ET par n3 (methodes). AUCUN cablage ici : le branchement effectif des
#  methodes (retrait du plancher CL, angle mort Munich, bascule B&Z / GLM APC
#  sur ce helper) est realise aux lots 2 / 3 / 4.
#
#  AUTEUR : ActuarIA
# =============================================================================
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

# Fraction maximale de cellules non exploitables au-dela de laquelle une methode
# a positivite obligatoire se declare indisponible. Alignee sur le garde-fou
# historique de Barnett-Zehnwirth (barnett_zehnwirth_ptf.FRAC_NEG_MAX = 0.10).
FRAC_NEG_MAX_DEFAUT = 0.10


def signaler_negatifs(C: np.ndarray, *, tol_inversion: float = 0.05) -> Dict:
    """
    Detecte et reporte les cumules negatifs et les inversions. NE MODIFIE PAS C.

    Zone connue : i + j < n. Detection pure (aucune transformation).

    - Cumule negatif : C[i, j] < 0.
    - Inversion      : le cumule redescend depuis une base positive,
                       C[i, j] < C[i, j-1] * (1 - tol_inversion), avec
                       C[i, j-1] > 0 et j >= 1.
      Le garde C[i, j-1] > 0 evite que la tolerance multiplicative se retourne
      sur une base negative ; les cumules negatifs sont comptes a part (n_neg),
      pas comme des inversions. (Meme critere que le validateur historique.)

    Parameters
    ----------
    C : np.ndarray (n, m)  — triangle cumule.
    tol_inversion : float  — tolerance relative avant de qualifier une baisse
                             d'inversion (defaut 5 %).

    Returns
    -------
    dict :
        n_neg               : int
        cellules_neg        : List[Tuple[int, int]]   # (i, j) ou C[i, j] < 0
        n_inversions        : int
        cellules_inversions : List[Tuple[int, int]]   # (i, j) ou le cumule baisse
        frac_neg            : float   # n_neg / nb de cellules connues
        frac_inversions     : float   # n_inversions / nb de transitions connues
    """
    n, m = C.shape
    cellules_neg: List[Tuple[int, int]] = []
    cellules_inv: List[Tuple[int, int]] = []
    n_connues = 0
    n_transitions = 0

    for i in range(n):
        for j in range(m):
            if i + j >= n:                      # hors zone connue
                continue
            n_connues += 1
            if float(C[i, j]) < 0.0:
                cellules_neg.append((i, j))
            if j >= 1:
                n_transitions += 1
                prev = float(C[i, j - 1])
                if prev > 0.0 and float(C[i, j]) < prev * (1.0 - tol_inversion):
                    cellules_inv.append((i, j))

    return {
        'n_neg':               len(cellules_neg),
        'cellules_neg':        cellules_neg,
        'n_inversions':        len(cellules_inv),
        'cellules_inversions': cellules_inv,
        'frac_neg':            len(cellules_neg) / max(n_connues, 1),
        'frac_inversions':     len(cellules_inv) / max(n_transitions, 1),
    }


def increments_positifs(
    C: np.ndarray, *,
    seuil_indisponible: float = FRAC_NEG_MAX_DEFAUT,
    plancher: Optional[float] = None,
) -> Dict:
    """
    Politique de positivite des increments pour les methodes qui l'exigent.

    Increment p[i, j] = C[i, j] - C[i, j-1]  (C[i, -1] = 0), zone connue i+j < n.

    Deux regimes :
      · plancher=None    : les cellules p <= 0 (ou non finies) sont EXCLUES
        (masque=False) et listees dans cellules_exclues ; les autres portent
        l'increment brut. Reproduit Barnett-Zehnwirth (_to_long_log :
        exclusion `p <= 0 or not isfinite`).
      · plancher=valeur  : chaque cellule porte Y = max(p, plancher)
        (masque=True partout). Reproduit GLM APC Poisson (_to_long :
        `max(inc, FLOOR_Y)` sur TOUTES les cellules connues).

    disponible = (frac_exclue <= seuil_indisponible), meme regle que le
    garde-fou B&Z (frac > FRAC_NEG_MAX -> indisponible).

    `cellules_exclues` designe toujours les increments <= 0 (ou non finis) —
    exclus (regime None) ou plafonnes (regime plancher) ; c'est la base de
    frac_exclue / disponible dans les deux regimes.

    Parameters
    ----------
    C : np.ndarray (n, m)  — triangle cumule.
    seuil_indisponible : float  — fraction max d'increments non positifs toleree
                                  avant disponible=False (defaut 0.10).
    plancher : float | None  — None = exclure ; valeur > 0 = plafonner par le bas.

    Returns
    -------
    dict :
        Y                : np.ndarray (n, m)   # increments (regime None) ou plafonnes
        masque           : np.ndarray (n, m) de bool  # True = cellule utilisable
        cellules_exclues : List[Tuple[int, int]]      # increments <= 0 (ou non finis)
        n_exclues        : int
        n_obs            : int    # nb de cellules en zone connue
        frac_exclue      : float
        disponible       : bool
    """
    n, m = C.shape
    Y = np.zeros((n, m), dtype=float)
    masque = np.zeros((n, m), dtype=bool)
    cellules_exclues: List[Tuple[int, int]] = []
    n_obs = 0

    for i in range(n):
        for j in range(m):
            if i + j >= n:
                continue
            n_obs += 1
            prev = float(C[i, j - 1]) if j > 0 else 0.0
            p = float(C[i, j]) - prev
            non_positif = (not np.isfinite(p)) or (p <= 0.0)
            if non_positif:
                cellules_exclues.append((i, j))

            if plancher is None:
                # Regime EXCLUSION (B&Z) : increment brut conserve, masque = p > 0.
                Y[i, j] = p if np.isfinite(p) else 0.0
                masque[i, j] = not non_positif
            else:
                # Regime PLAFOND (GLM APC) : Y = max(p, plancher), toutes utilisables.
                Y[i, j] = plancher if not np.isfinite(p) else max(p, plancher)
                masque[i, j] = True

    n_exclues = len(cellules_exclues)
    frac_exclue = n_exclues / max(n_obs, 1)
    return {
        'Y':                Y,
        'masque':           masque,
        'cellules_exclues': cellules_exclues,
        'n_exclues':        n_exclues,
        'n_obs':            n_obs,
        'frac_exclue':      frac_exclue,
        'disponible':       frac_exclue <= seuil_indisponible,
    }
