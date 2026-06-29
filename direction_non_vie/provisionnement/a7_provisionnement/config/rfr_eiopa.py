# =============================================================================
#  ActuarIA — Courbe des taux sans risque EIOPA (Risk-Free Rate)
#  rfr_eiopa.py
#
#  Source  : EIOPA Risk-Free Interest Rate Term Structures
#  Devise  : EUR
#  Date    : 31 mars 2025 (Q1 2025)
#  Méthode : Taux spot sans VA (Volatility Adjustment), sans CRA
#  Réf.    : Art. 77 Directive Solvabilité 2 + Règlement Délégué 2015/35
#
#  ⚠️  MISE À JOUR REQUISE : cette courbe doit être mise à jour
#      trimestriellement depuis https://www.eiopa.europa.eu/
#      tools-and-data/risk-free-interest-rate-term-structures_en
#
#  Utilisation :
#      from config.rfr_eiopa import get_taux_rfr, DATE_COURBE
#      taux_t = get_taux_rfr(t)  # taux spot à la maturité t (années)
# =============================================================================

from __future__ import annotations
import numpy as np
from typing import Union

# ── Métadonnées ───────────────────────────────────────────────────────────────
DATE_COURBE    = "2025-03-31"
DEVISE         = "EUR"
SOURCE         = "EIOPA RFR Term Structures — Q1 2025"
AVEC_VA        = False   # Sans Volatility Adjustment (base)
AVEC_CRA       = False   # Sans Credit Risk Adjustment

# ── Courbe EIOPA RFR EUR au 31/03/2025 ───────────────────────────────────────
# Taux spot annuel en % pour les maturités clés (1 à 150 ans)
# Interpolation linéaire pour les maturités intermédiaires
_MATURITES_CLE = [
     1,  2,  3,  4,  5,  6,  7,  8,  9, 10,
    11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    25, 30, 40, 50, 60, 70, 80, 90, 100, 150,
]

_TAUX_PCT = [
    2.626, 2.617, 2.618, 2.630, 2.648, 2.668, 2.689, 2.710, 2.730, 2.749,
    2.767, 2.784, 2.799, 2.813, 2.826, 2.838, 2.849, 2.859, 2.868, 2.876,
    2.907, 2.926, 2.946, 2.954, 2.958, 2.960, 2.961, 2.961, 2.962, 2.962,
]

# Pré-calculer l'interpolation pour maturités 1 à 150 ans
_mats_arr  = np.array(_MATURITES_CLE, dtype=float)
_taux_arr  = np.array(_TAUX_PCT,      dtype=float)


def get_taux_rfr(maturite: Union[int, float]) -> float:
    """
    Retourne le taux sans risque EIOPA EUR pour une maturité donnée.

    Parameters
    ----------
    maturite : int ou float
        Maturité en années (1 à 150).

    Returns
    -------
    float : taux annuel en décimal (ex: 0.02749 pour 2.749%)
    """
    maturite = max(1.0, min(float(maturite), 150.0))
    taux_pct = float(np.interp(maturite, _mats_arr, _taux_arr))
    return taux_pct / 100.0


def get_courbe_rfr(maturites_max: int = 30) -> list[float]:
    """
    Retourne la courbe complète jusqu'à maturites_max ans.

    Returns
    -------
    list[float] : taux en décimal pour t = 1, 2, ..., maturites_max
    """
    return [get_taux_rfr(t) for t in range(1, maturites_max + 1)]


def get_facteur_actualisation(t: int) -> float:
    """
    Facteur d'actualisation à la maturité t : 1 / (1 + r_t)^t

    Parameters
    ----------
    t : int — maturité en années (t ≥ 1)

    Returns
    -------
    float : facteur d'actualisation
    """
    r_t = get_taux_rfr(t)
    return 1.0 / (1.0 + r_t) ** t
