"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — SP_TABLES_IMPORT : Import Tables Expérience Client             ║
║  Direction Santé-Prévoyance · Services                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Charger et valider les tables d'expérience propriétaires client    ║
║         (CSV, Excel) pour substituer les tables de marché BCAC/TD88-90.    ║
║                                                                              ║
║  FORMATS SUPPORTÉS :                                                         ║
║    • CSV (séparateur , ou ; auto-détecté)                                  ║
║    • Excel (.xlsx, .xls) — premier onglet ou onglet nommé                  ║
║    • Fichier uploadé Streamlit (BytesIO)                                    ║
║                                                                              ║
║  3 TYPES DE TABLES IMPORTABLES :                                             ║
║                                                                              ║
║  Type 1 — Incidence ITT (Q_AI)                                             ║
║    Colonnes obligatoires : age | csp | taux_incidence                      ║
║    age    : entier 18-65                                                    ║
║    csp    : "cadre" | "non_cadre" | "ouvrier" | "employe" | "cadre_sup"   ║
║    taux_incidence : décimal ]0, 1[ (probabilité annuelle d'entrée en ITT)  ║
║                                                                              ║
║  Type 2 — Maintien ITT (TD)                                                ║
║    Colonnes obligatoires : age_entree | duree_mois | taux_maintien         ║
║    age_entree  : entier 18-65                                               ║
║    duree_mois  : entier 1-36                                                ║
║    taux_maintien : décimal ]0, 1] (P(encore en arrêt après duree_mois))   ║
║                                                                              ║
║  Type 3 — Mortalité / Passage IP (QX)                                      ║
║    Colonnes obligatoires : age | qx_mortalite | taux_passage_ip            ║
║    age           : entier 18-70                                             ║
║    qx_mortalite  : décimal ]0, 1[ (probabilité de décès entre x et x+1)   ║
║    taux_passage_ip : décimal ]0, 1[ (P(ITT → IP) conditionnelle)          ║
║                                                                              ║
║  VALIDATION :                                                                ║
║    • Colonnes obligatoires présentes                                        ║
║    • Valeurs dans les bornes actuarielles                                   ║
║    • Cohérence : taux maintien décroissants avec la durée                  ║
║    • Couverture âges minimale (au moins 5 âges distincts)                  ║
║    • Pas de NaN, pas de valeurs négatives                                   ║
║                                                                              ║
║  TRAÇABILITÉ :                                                               ║
║    • Métadonnées horodatées (source, nb lignes, plage âges)                ║
║    • Statistiques descriptives intégrées au rapport                        ║
║    • Mention explicite "Table propriétaire client" dans tous les rapports  ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import io
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger("actuaria.sp.tables_import")

# ── Colonnes attendues par type ───────────────────────────────────────────────
COLONNES_TYPE1 = {"age", "csp", "taux_incidence"}
COLONNES_TYPE2 = {"age_entree", "duree_mois", "taux_maintien"}
COLONNES_TYPE3 = {"age", "qx_mortalite", "taux_passage_ip"}

# ── Bornes actuarielles ───────────────────────────────────────────────────────
AGE_MIN, AGE_MAX         = 18, 70
DUREE_MAX_MOIS           = 36
TAUX_MIN, TAUX_MAX       = 0.0, 1.0
QX_MAX                   = 0.30     # qx mortalité ne doit pas dépasser 30%
TAUX_INCIDENCE_MAX       = 0.50     # incidence ITT ne doit pas dépasser 50%
NB_AGES_MINIMUM          = 5        # au moins 5 âges distincts pour interpolation

CSP_VALIDES = {"cadre", "non_cadre", "ouvrier", "employe", "cadre_sup"}


# ══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE D'IMPORT
# ══════════════════════════════════════════════════════════════════════════════

def charger_table(
    source: Union[str, bytes, "io.BytesIO"],
    type_table: str,
    nom_onglet: Optional[str] = None,
    separateur: Optional[str] = None,
) -> Dict:
    """
    Charge et valide une table d'expérience client.

    Parameters
    ----------
    source : str | bytes | BytesIO
        Chemin fichier, bytes bruts, ou objet BytesIO (upload Streamlit).
    type_table : str
        "incidence_itt"  → Type 1 (Q_AI par âge et CSP)
        "maintien_itt"   → Type 2 (TD par âge d'entrée et durée)
        "mortalite_ip"   → Type 3 (qx et taux passage IP par âge)
    nom_onglet : str, optional
        Nom de l'onglet Excel. Si None, premier onglet utilisé.
    separateur : str, optional
        Séparateur CSV (",", ";", "\\t"). Si None, auto-détecté.

    Returns
    -------
    dict avec clés :
        success      : bool
        table        : dict  — table convertie au format interne ActuarIA
        meta         : dict  — métadonnées (source, nb_lignes, plage_ages, horodatage)
        rapport      : dict  — statistiques descriptives
        erreur       : str   — message d'erreur si success=False
        avertissements : list — warnings non bloquants
    """
    try:
        df = _lire_source(source, nom_onglet, separateur)
        df = _normaliser_colonnes(df)

        if type_table == "incidence_itt":
            return _valider_type1(df, source)
        elif type_table == "maintien_itt":
            return _valider_type2(df, source)
        elif type_table == "mortalite_ip":
            return _valider_type3(df, source)
        else:
            return _erreur(f"type_table inconnu : \'{type_table}\'. "
                           f"Valeurs valides : incidence_itt, maintien_itt, mortalite_ip")

    except Exception as e:
        logger.error(f"Erreur import table {type_table} : {e}", exc_info=True)
        return _erreur(str(e))


# ══════════════════════════════════════════════════════════════════════════════
# LECTURE SOURCE
# ══════════════════════════════════════════════════════════════════════════════

def _lire_source(source, nom_onglet, separateur):
    """Lit le fichier depuis chemin, bytes ou BytesIO."""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas est requis pour l'import de tables client.")

    # Déterminer le format
    nom = ""
    if isinstance(source, str):
        nom = source.lower()
        data = source
    elif isinstance(source, (bytes, bytearray)):
        data = io.BytesIO(source)
        nom = "upload"
    elif hasattr(source, "read"):
        # BytesIO ou fichier uploadé Streamlit
        data = source
        nom = getattr(source, "name", "upload").lower()
    else:
        raise ValueError(f"Source non reconnue : {type(source)}")

    if nom.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data, sheet_name=nom_onglet)
    elif nom.endswith(".csv") or nom == "upload":
        # Tenter CSV avec auto-détection séparateur
        if isinstance(data, io.BytesIO):
            raw = data.read().decode("utf-8", errors="replace")
            data = io.StringIO(raw)
        if separateur:
            df = pd.read_csv(data, sep=separateur)
        else:
            # Auto-détection : essayer ; puis ,
            content = data.read() if hasattr(data, "read") else open(data).read()
            sep = ";" if content.count(";") > content.count(",") else ","
            df = pd.read_csv(io.StringIO(content), sep=sep)
    else:
        # Tenter Excel en dernier recours
        try:
            df = pd.read_excel(data, sheet_name=nom_onglet)
        except Exception:
            raise ValueError(
                f"Format non reconnu. Formats supportés : CSV (.csv), Excel (.xlsx, .xls). "
                f"Source reçue : {nom}"
            )

    if df.empty:
        raise ValueError("Le fichier est vide.")

    return df


def _normaliser_colonnes(df):
    """Normalise les noms de colonnes : minuscules, espaces → underscore."""
    df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_")
                  for c in df.columns]
    return df


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION TYPE 1 — INCIDENCE ITT
# ══════════════════════════════════════════════════════════════════════════════

def _valider_type1(df, source) -> Dict:
    """Valide et convertit une table d'incidence ITT (Q_AI)."""
    warns = []

    # Vérifier colonnes
    manquantes = COLONNES_TYPE1 - set(df.columns)
    if manquantes:
        return _erreur(
            f"Colonnes manquantes pour table incidence_itt : {sorted(manquantes)}. "
            f"Colonnes trouvées : {sorted(df.columns)}. "
            f"Colonnes attendues : age, csp, taux_incidence."
        )

    # Nettoyer NaN
    df = df.dropna(subset=list(COLONNES_TYPE1))
    if df.empty:
        return _erreur("Table vide après suppression des lignes incomplètes.")

    erreurs = []

    # Valider âges
    ages_invalides = df[~df["age"].between(AGE_MIN, AGE_MAX)]
    if not ages_invalides.empty:
        erreurs.append(
            f"Âges hors bornes [{AGE_MIN}-{AGE_MAX}] : "
            f"{sorted(ages_invalides['age'].unique().tolist())}"
        )

    # Valider CSP
    df["csp"] = df["csp"].str.lower().str.strip()
    csp_invalides = df[~df["csp"].isin(CSP_VALIDES)]["csp"].unique()
    if len(csp_invalides) > 0:
        erreurs.append(
            f"Valeurs CSP non reconnues : {sorted(csp_invalides.tolist())}. "
            f"Valeurs valides : {sorted(CSP_VALIDES)}."
        )

    # Valider taux
    taux_negatifs = df[df["taux_incidence"] < 0]
    if not taux_negatifs.empty:
        erreurs.append(f"{len(taux_negatifs)} taux d'incidence négatifs détectés.")

    taux_trop_eleves = df[df["taux_incidence"] > TAUX_INCIDENCE_MAX]
    if not taux_trop_eleves.empty:
        erreurs.append(
            f"{len(taux_trop_eleves)} taux d'incidence > {TAUX_INCIDENCE_MAX:.0%} "
            f"(vraisemblance actuarielle douteuse — vérifier l'unité : décimal ou %)."
        )

    if erreurs:
        return _erreur("\n".join(erreurs))

    # Avertissements non bloquants
    ages_couverts = sorted(df["age"].unique())
    if len(ages_couverts) < NB_AGES_MINIMUM:
        warns.append(
            f"Seulement {len(ages_couverts)} âge(s) distincts. "
            f"Minimum recommandé : {NB_AGES_MINIMUM} pour interpolation fiable."
        )
    if min(ages_couverts) > 30:
        warns.append(f"Table ne couvre pas les âges < {min(ages_couverts)}. "
                     f"Valeurs BCAC 2019 utilisées en extrapolation.")
    if max(ages_couverts) < 55:
        warns.append(f"Table ne couvre pas les âges > {max(ages_couverts)}. "
                     f"Valeurs BCAC 2019 utilisées en extrapolation.")

    # Conversion au format interne : dict {age: {csp: taux}}
    table_interne = {}
    for _, row in df.iterrows():
        age = int(row["age"])
        csp = str(row["csp"])
        taux = float(row["taux_incidence"])
        if age not in table_interne:
            table_interne[age] = {}
        table_interne[age][csp] = taux

    meta = _construire_meta("incidence_itt", source, df, ages_couverts)
    rapport = {
        "nb_ages":       len(ages_couverts),
        "plage_ages":    f"{min(ages_couverts)}-{max(ages_couverts)} ans",
        "csp_presentes": sorted(df["csp"].unique().tolist()),
        "taux_moyen":    round(float(df["taux_incidence"].mean()), 4),
        "taux_min":      round(float(df["taux_incidence"].min()), 4),
        "taux_max":      round(float(df["taux_incidence"].max()), 4),
        "nb_lignes":     len(df),
    }

    logger.info(
        f"Table incidence_itt chargée : {len(ages_couverts)} âges, "
        f"CSP={sorted(df['csp'].unique().tolist())}, "
        f"taux moyen={rapport['taux_moyen']:.2%}"
    )

    return {
        "success":         True,
        "type_table":      "incidence_itt",
        "table":           table_interne,
        "meta":            meta,
        "rapport":         rapport,
        "avertissements":  warns,
        "erreur":          None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION TYPE 2 — MAINTIEN ITT
# ══════════════════════════════════════════════════════════════════════════════

def _valider_type2(df, source) -> Dict:
    """Valide et convertit une table de maintien ITT (TD)."""
    warns = []

    manquantes = COLONNES_TYPE2 - set(df.columns)
    if manquantes:
        return _erreur(
            f"Colonnes manquantes pour table maintien_itt : {sorted(manquantes)}. "
            f"Colonnes attendues : age_entree, duree_mois, taux_maintien."
        )

    df = df.dropna(subset=list(COLONNES_TYPE2))
    if df.empty:
        return _erreur("Table vide après suppression des lignes incomplètes.")

    erreurs = []

    ages_invalides = df[~df["age_entree"].between(AGE_MIN, AGE_MAX)]
    if not ages_invalides.empty:
        erreurs.append(
            f"Âges hors bornes [{AGE_MIN}-{AGE_MAX}] : "
            f"{sorted(ages_invalides['age_entree'].unique().tolist())}"
        )

    durees_invalides = df[~df["duree_mois"].between(1, DUREE_MAX_MOIS)]
    if not durees_invalides.empty:
        erreurs.append(
            f"Durées hors bornes [1-{DUREE_MAX_MOIS}] mois : "
            f"{sorted(durees_invalides['duree_mois'].unique().tolist())}"
        )

    taux_invalides = df[~df["taux_maintien"].between(TAUX_MIN, TAUX_MAX)]
    if not taux_invalides.empty:
        erreurs.append(
            f"{len(taux_invalides)} taux de maintien hors [0,1] détectés."
        )

    if erreurs:
        return _erreur("\n".join(erreurs))

    # Vérification cohérence : décroissance avec la durée par âge
    for age, grp in df.groupby("age_entree"):
        grp_sorted = grp.sort_values("duree_mois")
        taux = grp_sorted["taux_maintien"].values
        violations = sum(1 for i in range(len(taux)-1) if taux[i] < taux[i+1] - 0.02)
        if violations > 0:
            warns.append(
                f"Âge {age} : {violations} violation(s) de décroissance du taux de maintien. "
                f"Le taux de maintien doit être décroissant avec la durée."
            )

    ages_couverts = sorted(df["age_entree"].unique())
    if len(ages_couverts) < 3:
        warns.append(
            f"Seulement {len(ages_couverts)} âge(s) d'entrée. "
            f"Minimum recommandé : 3 pour interpolation fiable."
        )

    # Conversion format interne : dict {age: [taux_t1, taux_t2, ...]}
    table_interne = {}
    for age, grp in df.groupby("age_entree"):
        grp_sorted = grp.sort_values("duree_mois")
        table_interne[int(age)] = grp_sorted["taux_maintien"].tolist()

    meta = _construire_meta("maintien_itt", source, df, ages_couverts)
    rapport = {
        "nb_ages":        len(ages_couverts),
        "plage_ages":     f"{min(ages_couverts)}-{max(ages_couverts)} ans",
        "durees_max":     int(df["duree_mois"].max()),
        "taux_t1_moyen":  round(float(df[df["duree_mois"]==1]["taux_maintien"].mean()), 4),
        "nb_lignes":      len(df),
    }

    logger.info(
        f"Table maintien_itt chargée : {len(ages_couverts)} âges, "
        f"durée max={int(df['duree_mois'].max())} mois"
    )

    return {
        "success":         True,
        "type_table":      "maintien_itt",
        "table":           table_interne,
        "meta":            meta,
        "rapport":         rapport,
        "avertissements":  warns,
        "erreur":          None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION TYPE 3 — MORTALITÉ / PASSAGE IP
# ══════════════════════════════════════════════════════════════════════════════

def _valider_type3(df, source) -> Dict:
    """Valide et convertit une table de mortalité et passage IP."""
    warns = []

    manquantes = COLONNES_TYPE3 - set(df.columns)
    if manquantes:
        return _erreur(
            f"Colonnes manquantes pour table mortalite_ip : {sorted(manquantes)}. "
            f"Colonnes attendues : age, qx_mortalite, taux_passage_ip."
        )

    df = df.dropna(subset=list(COLONNES_TYPE3))
    if df.empty:
        return _erreur("Table vide après suppression des lignes incomplètes.")

    erreurs = []

    ages_invalides = df[~df["age"].between(AGE_MIN, AGE_MAX)]
    if not ages_invalides.empty:
        erreurs.append(
            f"Âges hors bornes [{AGE_MIN}-{AGE_MAX}] : "
            f"{sorted(ages_invalides['age'].unique().tolist())}"
        )

    qx_negatifs = df[df["qx_mortalite"] < 0]
    if not qx_negatifs.empty:
        erreurs.append(f"{len(qx_negatifs)} qx de mortalité négatifs.")

    qx_trop_eleves = df[df["qx_mortalite"] > QX_MAX]
    if not qx_trop_eleves.empty:
        erreurs.append(
            f"{len(qx_trop_eleves)} qx de mortalité > {QX_MAX:.0%} "
            f"(valeur actuarielle suspecte — vérifier unité)."
        )

    taux_ip_invalides = df[~df["taux_passage_ip"].between(TAUX_MIN, TAUX_MAX)]
    if not taux_ip_invalides.empty:
        erreurs.append(
            f"{len(taux_ip_invalides)} taux de passage IP hors [0,1]."
        )

    if erreurs:
        return _erreur("\n".join(erreurs))

    ages_couverts = sorted(df["age"].unique())
    if len(ages_couverts) < NB_AGES_MINIMUM:
        warns.append(
            f"Seulement {len(ages_couverts)} âge(s) distincts. "
            f"Minimum recommandé : {NB_AGES_MINIMUM}."
        )

    # Vérification cohérence : qx croissant avec l'âge (tendance)
    if len(ages_couverts) >= 3:
        df_sorted = df.sort_values("age")
        qx_vals = df_sorted["qx_mortalite"].values
        ages_vals = df_sorted["age"].values
        n_violations = sum(
            1 for i in range(len(qx_vals)-1)
            if qx_vals[i] > qx_vals[i+1] + 0.001
            and ages_vals[i+1] - ages_vals[i] <= 5
        )
        if n_violations > len(ages_couverts) // 3:
            warns.append(
                f"{n_violations} inversions détectées dans qx_mortalite. "
                f"La mortalité devrait être croissante avec l'âge."
            )

    # Conversion format interne : dict {age: {qx_mortalite, taux_passage_ip}}
    table_interne = {}
    for _, row in df.iterrows():
        age = int(row["age"])
        table_interne[age] = {
            "qx_mortalite":   float(row["qx_mortalite"]),
            "taux_passage_ip": float(row["taux_passage_ip"]),
        }

    meta = _construire_meta("mortalite_ip", source, df, ages_couverts)
    rapport = {
        "nb_ages":         len(ages_couverts),
        "plage_ages":      f"{min(ages_couverts)}-{max(ages_couverts)} ans",
        "qx_moyen":        round(float(df["qx_mortalite"].mean()), 5),
        "qx_max":          round(float(df["qx_mortalite"].max()), 5),
        "taux_ip_moyen":   round(float(df["taux_passage_ip"].mean()), 4),
        "nb_lignes":       len(df),
    }

    logger.info(
        f"Table mortalite_ip chargée : {len(ages_couverts)} âges, "
        f"qx moyen={rapport['qx_moyen']:.4%}, "
        f"taux IP moyen={rapport['taux_ip_moyen']:.2%}"
    )

    return {
        "success":         True,
        "type_table":      "mortalite_ip",
        "table":           table_interne,
        "meta":            meta,
        "rapport":         rapport,
        "avertissements":  warns,
        "erreur":          None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _construire_meta(type_table: str, source, df, ages_couverts: list) -> Dict:
    """Construit les métadonnées de traçabilité."""
    nom_source = (
        source if isinstance(source, str)
        else getattr(source, "name", "fichier_client")
    )
    return {
        "type_table":          type_table,
        "source":              str(nom_source),
        "horodatage_import":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nb_lignes":           len(df),
        "ages_couverts":       ages_couverts,
        "plage_ages":          f"{min(ages_couverts)}-{max(ages_couverts)} ans",
        "origine":             "TABLE PROPRIÉTAIRE CLIENT",
        "mention_rapport":     (
            f"Table d'expérience propriétaire client chargée le "
            f"{datetime.now().strftime('%d/%m/%Y')} depuis \'{nom_source}\'. "
            f"Plage d'âges : {min(ages_couverts)}-{max(ages_couverts)} ans "
            f"({len(ages_couverts)} points). "
            f"Ces tables remplacent les références BCAC 2019 / TD 88-90 par défaut."
        ),
    }


def _erreur(message: str) -> Dict:
    """Retourne un dict d'erreur standardisé."""
    logger.error(f"Import table client : {message}")
    return {
        "success":         False,
        "type_table":      None,
        "table":           None,
        "meta":            None,
        "rapport":         None,
        "avertissements":  [],
        "erreur":          message,
    }


# ══════════════════════════════════════════════════════════════════════════════
# FONCTION UTILITAIRE : INTERPOLATION TABLE CLIENT
# ══════════════════════════════════════════════════════════════════════════════

def interpoler_table(table_dict: dict, age: float, cle: Optional[str] = None) -> float:
    """
    Interpolation linéaire dans une table client.

    Parameters
    ----------
    table_dict : dict
        Table au format interne (clés = âges entiers).
    age : float
        Âge à interpoler.
    cle : str, optional
        Sous-clé si la table contient des dicts (ex: "qx_mortalite").

    Returns
    -------
    float — valeur interpolée
    """
    if not table_dict:
        raise ValueError("Table vide — impossible d'interpoler.")

    ages = sorted(table_dict.keys())

    if age <= ages[0]:
        val = table_dict[ages[0]]
        return float(val[cle] if cle else val)
    if age >= ages[-1]:
        val = table_dict[ages[-1]]
        return float(val[cle] if cle else val)

    # Trouver les âges encadrants
    age_inf = max(a for a in ages if a <= age)
    age_sup = min(a for a in ages if a >= age)

    if age_inf == age_sup:
        val = table_dict[age_inf]
        return float(val[cle] if cle else val)

    v_inf = table_dict[age_inf]
    v_sup = table_dict[age_sup]
    if cle:
        v_inf = v_inf[cle]
        v_sup = v_sup[cle]

    t = (age - age_inf) / (age_sup - age_inf)
    return float(v_inf) + t * (float(v_sup) - float(v_inf))


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATES CSV POUR LA DOCUMENTATION CLIENT
# ══════════════════════════════════════════════════════════════════════════════

TEMPLATE_TYPE1 = """age,csp,taux_incidence
25,cadre,0.022
25,non_cadre,0.037
30,cadre,0.025
30,non_cadre,0.042
35,cadre,0.030
35,non_cadre,0.050
40,cadre,0.040
40,non_cadre,0.066
45,cadre,0.051
45,non_cadre,0.084
50,cadre,0.066
50,non_cadre,0.109
55,cadre,0.087
55,non_cadre,0.144
60,cadre,0.095
60,non_cadre,0.158
"""

TEMPLATE_TYPE2 = """age_entree,duree_mois,taux_maintien
30,1,0.825
30,3,0.576
30,6,0.408
30,12,0.180
30,24,0.040
40,1,0.840
40,3,0.600
40,6,0.435
40,12,0.201
40,24,0.054
50,1,0.860
50,3,0.642
50,6,0.483
50,12,0.248
50,24,0.081
"""

TEMPLATE_TYPE3 = """age,qx_mortalite,taux_passage_ip
25,0.00085,0.04
30,0.00088,0.05
35,0.00104,0.06
40,0.00148,0.08
45,0.00232,0.12
50,0.00359,0.18
55,0.00556,0.25
60,0.00837,0.35
65,0.01230,0.45
"""

TEMPLATES = {
    "incidence_itt": TEMPLATE_TYPE1,
    "maintien_itt":  TEMPLATE_TYPE2,
    "mortalite_ip":  TEMPLATE_TYPE3,
}


def get_template(type_table: str) -> str:
    """Retourne le template CSV pour un type de table."""
    if type_table not in TEMPLATES:
        raise ValueError(
            f"Type inconnu : {type_table}. "
            f"Valides : {list(TEMPLATES.keys())}"
        )
    return TEMPLATES[type_table]
