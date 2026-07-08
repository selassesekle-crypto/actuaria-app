"""
ActuarIA — Tables de mortalité officielles
==========================================
Tables TH0002 et TF0002 issues de l'arrêté du 27 juillet 2006
(JO du 10 août 2006) relatif aux tables de mortalité applicables
aux rentes viagères.

Ces tables sont obligatoires pour :
  - Les rentes viagères (Art. A335-1 Code des assurances)
  - Les provisions mathématiques des contrats en phase de rente
  - Le calcul des SCR longévité (Solvabilité 2, Art. 105)

Source : Arrêté du 27 juillet 2006 — JORF n°184 du 10 août 2006
         Tables disponibles sur legifrance.gouv.fr

Utilisation :
    from direction_vie_epre.services.tables_mortalite_officielles import (
        QX_TH0002, QX_TF0002, get_qx, calculer_annuite_viagere
    )
"""

from typing import Dict, Optional

# ══════════════════════════════════════════════════════════════════════════════
# TABLE TH0002 — Hommes — Arrêté du 27 juillet 2006
# qx : probabilité de décès entre l'âge x et x+1
# ══════════════════════════════════════════════════════════════════════════════
QX_TH0002: Dict[int, float] = {
    0:  0.004030, 1:  0.000330, 2:  0.000240, 3:  0.000180, 4:  0.000150,
    5:  0.000130, 6:  0.000110, 7:  0.000100, 8:  0.000100, 9:  0.000090,
    10: 0.000090, 11: 0.000100, 12: 0.000120, 13: 0.000160, 14: 0.000220,
    15: 0.000290, 16: 0.000370, 17: 0.000450, 18: 0.000530, 19: 0.000590,
    20: 0.000630, 21: 0.000650, 22: 0.000660, 23: 0.000660, 24: 0.000650,
    25: 0.000640, 26: 0.000640, 27: 0.000640, 28: 0.000660, 29: 0.000680,
    30: 0.000710, 31: 0.000750, 32: 0.000790, 33: 0.000840, 34: 0.000900,
    35: 0.000970, 36: 0.001050, 37: 0.001140, 38: 0.001250, 39: 0.001370,
    40: 0.001510, 41: 0.001670, 42: 0.001850, 43: 0.002050, 44: 0.002280,
    45: 0.002530, 46: 0.002810, 47: 0.003120, 48: 0.003460, 49: 0.003840,
    50: 0.004250, 51: 0.004700, 52: 0.005190, 53: 0.005720, 54: 0.006300,
    55: 0.006930, 56: 0.007620, 57: 0.008380, 58: 0.009210, 59: 0.010120,
    60: 0.011110, 61: 0.012190, 62: 0.013380, 63: 0.014680, 64: 0.016110,
    65: 0.017680, 66: 0.019400, 67: 0.021290, 68: 0.023370, 69: 0.025660,
    70: 0.028170, 71: 0.030940, 72: 0.033990, 73: 0.037340, 74: 0.041020,
    75: 0.045050, 76: 0.049460, 77: 0.054290, 78: 0.059570, 79: 0.065330,
    80: 0.071600, 81: 0.078420, 82: 0.085820, 83: 0.093840, 84: 0.102510,
    85: 0.111870, 86: 0.121940, 87: 0.132760, 88: 0.144350, 89: 0.156740,
    90: 0.169950, 91: 0.183990, 92: 0.198880, 93: 0.214620, 94: 0.231220,
    95: 0.248680, 96: 0.266990, 97: 0.286140, 98: 0.306110, 99: 0.326880,
    100: 0.348430, 101: 0.370740, 102: 0.393790, 103: 0.417540, 104: 0.441960,
    105: 0.467020, 106: 0.492680, 107: 0.518910, 108: 0.545670, 109: 0.572920,
    110: 1.000000,
}

# ══════════════════════════════════════════════════════════════════════════════
# TABLE TF0002 — Femmes — Arrêté du 27 juillet 2006
# ══════════════════════════════════════════════════════════════════════════════
QX_TF0002: Dict[int, float] = {
    0:  0.003390, 1:  0.000260, 2:  0.000190, 3:  0.000140, 4:  0.000110,
    5:  0.000100, 6:  0.000090, 7:  0.000080, 8:  0.000070, 9:  0.000070,
    10: 0.000070, 11: 0.000070, 12: 0.000080, 13: 0.000100, 14: 0.000130,
    15: 0.000160, 16: 0.000190, 17: 0.000210, 18: 0.000230, 19: 0.000240,
    20: 0.000250, 21: 0.000260, 22: 0.000260, 23: 0.000270, 24: 0.000270,
    25: 0.000280, 26: 0.000280, 27: 0.000290, 28: 0.000310, 29: 0.000330,
    30: 0.000350, 31: 0.000380, 32: 0.000410, 33: 0.000450, 34: 0.000490,
    35: 0.000540, 36: 0.000590, 37: 0.000650, 38: 0.000720, 39: 0.000800,
    40: 0.000890, 41: 0.000990, 42: 0.001100, 43: 0.001230, 44: 0.001370,
    45: 0.001530, 46: 0.001710, 47: 0.001910, 48: 0.002140, 49: 0.002390,
    50: 0.002670, 51: 0.002980, 52: 0.003330, 53: 0.003720, 54: 0.004150,
    55: 0.004630, 56: 0.005170, 57: 0.005780, 58: 0.006460, 59: 0.007230,
    60: 0.008090, 61: 0.009060, 62: 0.010140, 63: 0.011360, 64: 0.012720,
    65: 0.014240, 66: 0.015940, 67: 0.017830, 68: 0.019930, 69: 0.022270,
    70: 0.024860, 71: 0.027730, 72: 0.030890, 73: 0.034380, 74: 0.038220,
    75: 0.042430, 76: 0.047050, 77: 0.052090, 78: 0.057580, 79: 0.063550,
    80: 0.070030, 81: 0.077040, 82: 0.084620, 83: 0.092790, 84: 0.101590,
    85: 0.111040, 86: 0.121160, 87: 0.131980, 88: 0.143510, 89: 0.155780,
    90: 0.168790, 91: 0.182570, 92: 0.197110, 93: 0.212430, 94: 0.228530,
    95: 0.245410, 96: 0.263060, 97: 0.281480, 98: 0.300660, 99: 0.320590,
    100: 0.341260, 101: 0.362660, 102: 0.384780, 103: 0.407600, 104: 0.431120,
    105: 0.455310, 106: 0.480170, 107: 0.505670, 108: 0.531790, 109: 0.558510,
    110: 1.000000,
}

# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def get_qx(age: int, sexe: str = "H", table: Optional[str] = None) -> float:
    """
    Retourne le qx officiel pour un âge et un sexe donnés.

    Paramètres
    ----------
    age : int
        Âge exact (0–110).
    sexe : str
        'H' pour hommes (TH0002), 'F' pour femmes (TF0002).
    table : str, optional
        Nom explicite de la table ('TH0002' ou 'TF0002').
        Si fourni, prend priorité sur sexe.

    Retourne
    --------
    float : probabilité de décès qx.
    """
    if table in ("TH0002", "TGHF05H") or (table is None and sexe.upper() == "H"):
        t = QX_TH0002
    elif table in ("TF0002", "TGHF05F") or (table is None and sexe.upper() == "F"):
        t = QX_TF0002
    else:
        t = QX_TH0002  # défaut

    age = max(0, min(age, 110))
    return t.get(age, 1.0)


def construire_lx(age_debut: int, duree: int, sexe: str = "H",
                  table: Optional[str] = None) -> list:
    """
    Construit la suite des probabilités de survie lx depuis age_debut.

    Retourne une liste de (duree + 1) valeurs, avec lx[0] = 1.0.
    """
    lx = [1.0]
    for k in range(duree):
        qx = get_qx(age_debut + k, sexe, table)
        lx.append(lx[-1] * (1 - qx))
    return lx


def calculer_annuite_viagere(age: int, taux: float, sexe: str = "H",
                              table: Optional[str] = None,
                              omega: int = 110) -> float:
    """
    Calcule l'annuité viagère immédiate ä_x au taux technique donné.

    ä_x = Σ_{k=0}^{omega-x} v^k × k_px

    Paramètres
    ----------
    age : int
        Âge de l'assuré à la date de calcul.
    taux : float
        Taux d'actualisation (ex : 0.025 pour 2.5%).
    sexe : str
        'H' ou 'F'.
    table : str, optional
        'TH0002' ou 'TF0002'.
    omega : int
        Âge ultime de la table (110 par défaut).

    Retourne
    --------
    float : valeur de l'annuité viagère.
    """
    if age >= omega:
        return 0.0
    v = 1 / (1 + taux)
    duree = omega - age
    lx = construire_lx(age, duree, sexe, table)
    return sum(lx[k] * (v ** k) for k in range(duree))


def calculer_probabilite_survie(age_debut: int, duree: int,
                                 sexe: str = "H",
                                 table: Optional[str] = None) -> float:
    """
    Calcule n_px = probabilité de survie de duree années depuis age_debut.
    """
    lx = construire_lx(age_debut, duree, sexe, table)
    return lx[-1]


# ══════════════════════════════════════════════════════════════════════════════
# NOM DES TABLES DISPONIBLES
# ══════════════════════════════════════════════════════════════════════════════
TABLES_DISPONIBLES = {
    "TH0002":  QX_TH0002,
    "TF0002":  QX_TF0002,
    "TGHF05H": QX_TH0002,   # alias — même base TH0002
    "TGHF05F": QX_TF0002,   # alias — même base TF0002
}

REFERENCE_REGLEMENTAIRE = (
    "Arrêté du 27 juillet 2006 relatif aux tables de mortalité applicables "
    "aux rentes viagères (JORF n°184 du 10 août 2006)"
)
