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


# ── REGISTRE DES TABLES ────────────────────────────────────────────────────
# ⛔ ARBITRAGE A1 — ET CE QUE LA MESURE A CHANGE A MA RECOMMANDATION.
#
# J avais recommande « une seule source, supprimer les copies ». En mesurant
# les trois tables dites « TH 00-02 » aux ages qu elles ont en commun :
#
#     age   services   sp_tables_bio   p1        ecart max
#      25   0,00092      0,00085      0,00073     26,0 %
#      45   0,00295      0,00232      0,00298     28,4 %
#      65   0,01700      0,01230      0,02380     93,5 %
#
# L ecart CROIT avec l age et `sp_tables_biometriques` est SYSTEMATIQUEMENT
# la plus basse -- exactement ce qu on attend d une table de POPULATION
# ACTIVE, ce qu elle dit etre dans son propre commentaire. Ce ne sont donc
# pas trois VERSIONS d une meme table : ce sont trois OBJETS DIFFERENTS.
#
# ⛔ LES FUSIONNER SERAIT FABRIQUER DE L ACTUARIAT. Et choisir la « bonne »
# exige les publications certifiees, que je n ai pas. Ce que je peux faire,
# et qui ferme le defaut reel :
#
#   ① chaque table DECLARE la population qu elle decrit et l etat de sa
#      verification -- une table sans millesime ne se fait plus passer pour
#      une reference ;
#   ② les replis locaux de P1 et P2, qui donnaient des valeurs DIFFERENTES
#      en silence, sont supprimes : mieux vaut une panne franche qu un tarif
#      calcule sur une table qu on croyait etre une autre ;
#   ③ un sceau interdit qu une nouvelle copie apparaisse.
#
# Ce qui reste a faire, et qui n est pas de mon ressort : commander les
# tables BCAC 2019 et TH 00-02 CERTIFIEES, avec leur millesime. Une ligne a
# un actuaire-conseil, et A1 se ferme pour de bon.

#: Ce que chaque table DECRIT, et ce qu on sait de sa provenance.
#: `verifie` reste False tant que la publication certifiee n a pas ete
#: rapprochee : c est une DETTE DECLAREE, pas un detail.
REGISTRE_TABLES = {
    "BCAC_2019_TAUX_ITT": {
        "libelle": "Taux d'incidence ITT, BCAC 2019",
        "population": "population assuree, contrats collectifs de prevoyance",
        "differenciation": "cadre / non-cadre",
        "source_declaree": "BCAC 2019 (CTIP)",
        "millesime": None,
        "verifie": False,
        "dette": ("millesime et page de publication non renseignes ; a "
                  "rapprocher de la publication BCAC 2019 certifiee"),
    },
    "TD_8890_TAUX_IP": {
        "libelle": "Taux de passage en invalidite, TD 88-90",
        "population": "population generale France 1988-1990",
        "differenciation": "aucune",
        "source_declaree": "TD 88-90",
        "millesime": None,
        "verifie": False,
        "dette": "millesime et page de publication non renseignes",
    },
    "TH0002_QX": {
        "libelle": "Quotients de mortalite, TH/TF 00-02",
        "population": "population generale France 2000-2002",
        "differenciation": "hommes / femmes",
        "source_declaree": "TH 00-02 et TF 00-02 (INSEE)",
        "millesime": None,
        "verifie": False,
        "dette": ("⚠️ TROIS tables du perimetre portaient ce nom en decrivant "
                  "des populations DIFFERENTES (generale, active, assuree), "
                  "avec jusqu'a 93,5 %% d'ecart a 65 ans. Celle-ci decrit la "
                  "population GENERALE. A rapprocher de la publication INSEE."),
    },
    "Q_IA_BCAC": {
        "libelle": "Probabilites de retour a l etat actif depuis l ITT",
        "population": "population assuree, contrats collectifs",
        "differenciation": "aucune",
        "source_declaree": "BCAC 2019",
        "millesime": None,
        "verifie": False,
        "dette": ("table UNIQUE au perimetre -- portee par p2_tables_morbidite "
                  "et par aucun autre module. Millesime non renseigne."),
    },
    "Q_IP_COND_BCAC": {
        "libelle": "Probabilites de passage ITT -> IP, conditionnelles",
        "population": "population assuree en arret de travail",
        "differenciation": "aucune",
        "source_declaree": "BCAC 2019",
        "millesime": None,
        "verifie": False,
        "dette": ("table UNIQUE au perimetre. ⚠️ CONDITIONNELLE a l etat ITT : "
                  "ne pas la confondre avec un taux d incidence brut."),
    },
    "MAINTIEN_ITT_MOIS": {
        "libelle": "Probabilites de maintien en ITT, par mois",
        "population": "population assuree, contrats collectifs",
        "differenciation": "aucune",
        "source_declaree": "BCAC 2019",
        "millesime": None,
        "verifie": False,
        "dette": "millesime et page de publication non renseignes",
    },
}


def fiche_table(nom):
    """Rend la fiche d'une table — et refuse un nom qu'elle ne connaît pas.

    ⛔ Pas de fiche par défaut : une table servie sans fiche est exactement
    ce que cet arbitrage supprime. Un nom inconnu doit faire lever.
    """
    if nom not in REGISTRE_TABLES:
        raise KeyError(
            "Table inconnue du registre : %r. Tables declarees : %s. "
            "Une table servie sans fiche ne peut pas dire quelle population "
            "elle decrit." % (nom, ", ".join(sorted(REGISTRE_TABLES))))
    return dict(REGISTRE_TABLES[nom])


def mention_table(nom):
    """La phrase a porter DANS le document, à côté du taux servi."""
    f = fiche_table(nom)
    etat = ("millesime %s, verifie" % f["millesime"] if f["verifie"]
            else "MILLESIME NON VERIFIE")
    return ("%s — %s ; population : %s ; differenciation : %s ; %s."
            % (f["libelle"], f["source_declaree"], f["population"],
               f["differenciation"], etat))


def tables_non_verifiees():
    """Les tables dont la provenance reste une dette déclarée."""
    return sorted(n for n, f in REGISTRE_TABLES.items() if not f["verifie"])
