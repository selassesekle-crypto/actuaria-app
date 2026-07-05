"""
sp_tables_actuarielles.py — Tables actuarielles centralisées Direction SP

Tables disponibles :
  BCAC 2019  : taux d'incidence ITT par âge et catégorie socio-professionnelle
  TD 88-90   : probabilités d'invalidité permanente par âge (INSEE)
  TH 00-02   : tables de mortalité toutes causes (hommes + femmes)
  DREES 2023 : consommation médicale par poste et âge (frais de santé)

Principe : centralisées ici pour éviter la duplication entre P1, P2, P3.
           Importées par les agents via : from ...services.sp_tables_actuarielles import ...

NB : Autonomie de la direction respectée — ces tables ne sont pas partagées
     avec les autres directions.
"""

import numpy as np
from typing import Dict, Optional


# =============================================================================
# BCAC 2019 — Taux d'incidence ITT par âge et CSP
# Source : BCAC 2019 (Bureau Commun des Assurances Collectives)
# Unité : taux annuel d'entrée en ITT
# =============================================================================
BCAC_2019_TAUX_ITT = {
    # (age_min, age_max) : (cadre, non_cadre)
    (20, 24): (0.020, 0.035),
    (25, 29): (0.022, 0.038),
    (30, 34): (0.025, 0.042),
    (35, 39): (0.030, 0.050),
    (40, 44): (0.038, 0.063),
    (45, 49): (0.048, 0.080),
    (50, 54): (0.062, 0.103),
    (55, 59): (0.082, 0.136),
    (60, 64): (0.095, 0.158),
}

def get_taux_itt_bcac(age: float, csp: str = "non_cadre") -> float:
    """
    Retourne le taux d'incidence ITT BCAC 2019 pour un âge et une CSP.

    Parameters
    ----------
    age : float — âge de l'assuré
    csp : str   — 'cadre' | 'non_cadre'

    Returns
    -------
    float : taux annuel d'entrée en ITT
    """
    age = int(min(max(age, 20), 64))
    for (a_min, a_max), (t_cadre, t_nc) in BCAC_2019_TAUX_ITT.items():
        if a_min <= age <= a_max:
            return t_cadre if csp == "cadre" else t_nc
    return 0.08  # fallback âge hors table


# =============================================================================
# TD 88-90 — Probabilités de passage ITT → Invalidité Permanente
# Source : Tables de maintien en incapacité INSEE / BCAC
# Unité : probabilité de passage à l'IP après maintien en ITT
# =============================================================================
TD_8890_TAUX_IP = {
    # age : probabilité de passage ITT → IP (après franchise)
    25: 0.0015, 30: 0.0020, 35: 0.0028, 40: 0.0038,
    45: 0.0052, 50: 0.0072, 55: 0.0098, 60: 0.0125,
}

def get_taux_ip_td8890(age: float) -> float:
    """
    Interpolation linéaire du taux IP depuis TD 88-90.
    """
    age = float(min(max(age, 25), 60))
    ages = sorted(TD_8890_TAUX_IP.keys())
    if age in TD_8890_TAUX_IP:
        return TD_8890_TAUX_IP[age]
    # Interpolation linéaire
    for i in range(len(ages) - 1):
        if ages[i] <= age <= ages[i+1]:
            a0, a1 = ages[i], ages[i+1]
            t0, t1 = TD_8890_TAUX_IP[a0], TD_8890_TAUX_IP[a1]
            return t0 + (t1 - t0) * (age - a0) / (a1 - a0)
    return 0.012


# =============================================================================
# TH 00-02 — Tables de mortalité (hommes + femmes)
# Source : INSEE TH 00-02 (base tables réglementaires françaises)
# Unité : taux annuel de décès q_x
# =============================================================================
TH0002_QX = {
    # age : (q_x_hommes, q_x_femmes)
    20: (0.00077, 0.00033), 25: (0.00092, 0.00040),
    30: (0.00103, 0.00050), 35: (0.00134, 0.00068),
    40: (0.00191, 0.00105), 45: (0.00295, 0.00165),
    50: (0.00472, 0.00260), 55: (0.00738, 0.00395),
    60: (0.01115, 0.00600), 65: (0.01700, 0.00940),
    70: (0.02650, 0.01530), 75: (0.04200, 0.02570),
}

def get_qx_th0002(age: float, sexe: str = "M") -> float:
    """
    Taux de décès TH 00-02 avec interpolation linéaire.

    Parameters
    ----------
    age  : float — âge de l'assuré
    sexe : str   — 'M' (hommes) | 'F' (femmes)
    """
    age = float(min(max(age, 20), 75))
    ages = sorted(TH0002_QX.keys())
    idx = 0 if sexe == "M" else 1

    for i in range(len(ages) - 1):
        if ages[i] <= age <= ages[i+1]:
            a0, a1 = ages[i], ages[i+1]
            q0 = TH0002_QX[a0][idx]
            q1 = TH0002_QX[a1][idx]
            return q0 + (q1 - q0) * (age - a0) / (a1 - a0)
    return TH0002_QX[ages[-1]][idx]


# =============================================================================
# DREES 2023 — Consommation médicale par poste et âge
# Source : DREES — Enquête santé et protection sociale 2023
# Unité : consommation annuelle moyenne en € par assuré
# =============================================================================
DREES_2023_CONSO = {
    # poste : {tranche_age : conso_annuelle_€}
    "medecine": {
        (0,  17): 380,  (18, 34): 290,  (35, 49): 420,
        (50, 64): 680,  (65, 79): 980,  (80, 99): 1250,
    },
    "hospitalisation": {
        (0,  17): 210,  (18, 34): 310,  (35, 49): 490,
        (50, 64): 890,  (65, 79): 1650, (80, 99): 2800,
    },
    "dentaire": {
        (0,  17): 95,   (18, 34): 180,  (35, 49): 290,
        (50, 64): 380,  (65, 79): 410,  (80, 99): 350,
    },
    "optique": {
        (0,  17): 85,   (18, 34): 120,  (35, 49): 175,
        (50, 64): 210,  (65, 79): 195,  (80, 99): 160,
    },
    "pharmacie": {
        (0,  17): 145,  (18, 34): 115,  (35, 49): 195,
        (50, 64): 380,  (65, 79): 620,  (80, 99): 780,
    },
    "autres": {
        (0,  17): 55,   (18, 34): 75,   (35, 49): 110,
        (50, 64): 180,  (65, 79): 290,  (80, 99): 380,
    },
}

def get_conso_drees(poste: str, age: float) -> float:
    """
    Consommation médicale annuelle DREES 2023 par poste et âge.

    Parameters
    ----------
    poste : str   — 'medecine' | 'hospitalisation' | 'dentaire' |
                    'optique' | 'pharmacie' | 'autres'
    age   : float — âge de l'assuré

    Returns
    -------
    float : consommation annuelle en €
    """
    age = float(max(age, 0))
    table = DREES_2023_CONSO.get(poste, {})
    for (a_min, a_max), conso in table.items():
        if a_min <= age <= a_max:
            return float(conso)
    return 200.0  # fallback

def get_conso_totale_drees(age: float) -> Dict[str, float]:
    """Retourne la consommation par poste pour un âge donné."""
    postes = ["medecine", "hospitalisation", "dentaire", "optique", "pharmacie", "autres"]
    return {p: get_conso_drees(p, age) for p in postes}


# =============================================================================
# COURBES DE MAINTIEN MARKOV — Probabilités de maintien en ITT
# Source : calibration BCAC / pratique marché français
# =============================================================================
MAINTIEN_ITT_MOIS = {
    # Probabilité de rester en ITT après N mois (toutes CSP confondues)
    1: 0.85, 2: 0.72, 3: 0.61, 6: 0.42, 9: 0.31,
    12: 0.24, 18: 0.16, 24: 0.11, 36: 0.06,
}

def get_prob_maintien_itt(duree_mois: float) -> float:
    """
    Probabilité de maintien en ITT après duree_mois mois.
    Interpolation linéaire entre les points de la courbe.
    """
    duree_mois = float(max(duree_mois, 0))
    mois_ref = sorted(MAINTIEN_ITT_MOIS.keys())
    if duree_mois <= mois_ref[0]:
        return MAINTIEN_ITT_MOIS[mois_ref[0]]
    if duree_mois >= mois_ref[-1]:
        return MAINTIEN_ITT_MOIS[mois_ref[-1]] * np.exp(-0.05 * (duree_mois - mois_ref[-1]))
    for i in range(len(mois_ref) - 1):
        m0, m1 = mois_ref[i], mois_ref[i+1]
        if m0 <= duree_mois <= m1:
            p0, p1 = MAINTIEN_ITT_MOIS[m0], MAINTIEN_ITT_MOIS[m1]
            return p0 + (p1 - p0) * (duree_mois - m0) / (m1 - m0)
    return 0.01
