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


# =============================================================================
#  FONCTIONS DE SUBSTITUTION — courbe manuelle ou fichier Excel
# =============================================================================

def get_courbe_taux_plat(taux_pct: float) -> dict:
    """
    Retourne une courbe de taux plat (même taux pour toutes les maturités).

    Parameters
    ----------
    taux_pct : float — taux annuel en % (ex: 3.2 pour 3.2%)

    Returns
    -------
    dict avec 'type', 'taux_pct', 'source', 'date'
    """
    taux_decimal = taux_pct / 100.0
    return {
        'type':        'taux_plat',
        'taux_pct':    taux_pct,
        'taux_fn':     lambda t: taux_decimal,
        'source':      f'Taux manuel saisi par l\u2019actuaire : {taux_pct:.3f}%',
        'date':        'Arrêté courant',
        'label':       f'Taux manuel {taux_pct:.3f}%',
    }


def get_courbe_depuis_excel(fichier_bytes: bytes) -> dict:
    """
    Charge une courbe EIOPA depuis un fichier Excel uploadé.

    Format attendu : deux colonnes dans la première feuille
        - Colonne 1 : maturite (entier, années 1 à 150)
        - Colonne 2 : taux_pct (float, ex: 2.85 pour 2.85%)

    Parameters
    ----------
    fichier_bytes : bytes — contenu du fichier Excel

    Returns
    -------
    dict avec 'type', 'taux_fn', 'source', 'date', 'maturites', 'taux'
    """
    import io
    import numpy as np
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(fichier_bytes))
        # Renommer les colonnes
        df.columns = [str(c).lower().strip() for c in df.columns]
        # Chercher colonnes maturite et taux
        col_mat  = next((c for c in df.columns if 'matur' in c or 'mat' in c or c in ['t', 'annee', 'year']), df.columns[0])
        col_taux = next((c for c in df.columns if 'taux' in c or 'rate' in c or 'rfr' in c or c in ['r', 'pct']), df.columns[1])

        mats = df[col_mat].dropna().astype(float).tolist()
        taux = df[col_taux].dropna().astype(float).tolist()

        if len(mats) < 2 or len(taux) < 2:
            raise ValueError("Fichier invalide — moins de 2 maturités")

        mats_arr = np.array(mats)
        taux_arr = np.array(taux)

        def taux_fn(t):
            return float(np.interp(float(t), mats_arr, taux_arr)) / 100.0

        return {
            'type':      'fichier_excel',
            'taux_fn':   taux_fn,
            'source':    'Fichier Excel importé par l\u2019actuaire',
            'date':      f'Courbe personnalisée ({len(mats)} maturités)',
            'label':     f'Fichier Excel ({len(mats)} maturités)',
            'maturites': mats,
            'taux':      taux,
            'erreur':    None,
        }
    except Exception as e:
        return {
            'type':    'erreur',
            'taux_fn': lambda t: get_taux_rfr(t),
            'source':  f'Erreur chargement fichier : {e} — courbe embarquée utilisée',
            'date':    DATE_COURBE,
            'label':   f'Courbe embarquée (erreur fichier)',
            'erreur':  str(e),
        }


def get_courbe_embarquee() -> dict:
    """Retourne la courbe EIOPA embarquée (Q1 2025) comme dict standard."""
    return {
        'type':    'embarquee',
        'taux_fn': get_taux_rfr,
        'source':  SOURCE,
        'date':    DATE_COURBE,
        'label':   f'Courbe EIOPA embarquée ({DATE_COURBE})',
        'erreur':  None,
    }
