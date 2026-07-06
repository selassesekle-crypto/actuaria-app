"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ACTUARIA — SP DATA BUILDER v1.0                                     ║
║         Constructeur de données Santé-Prévoyance                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Équivalent de NVTriangleBuilder pour la Direction SP.               ║
║  Charge, normalise et valide les données clients avant de les passer        ║
║  aux agents S1/S2/P1/P2/P3 et sp_coord.                                    ║
║                                                                              ║
║  FORMATS ACCEPTÉS :                                                          ║
║    Format M  — Fichier adhérents (mutuelle santé individuelle/collective)   ║
║    Format IP — Fichier salariés (institution de prévoyance collective)      ║
║    Format A  — Données agrégées (triangles par poste — comme Non-Vie)      ║
║    Format MX — Mixte (mutuelle + prévoyance dans le même fichier)          ║
║                                                                              ║
║  SORTIE : DataFrame normalisé unique + méta-données + diagnostics          ║
║  Colonnes normalisées : age, sexe, salaire_brut, categorie,                ║
║                          garanties, sinistres_sante, arrets_itt, etc.      ║
║                                                                              ║
║  COMPATIBILITÉ :                                                             ║
║    S1 Léonie  → consomme result_a2.get("dataframe") avec col. age/csp     ║
║    P1 Axel    → consomme result_a2.get("dataframe") avec col. age/salaire  ║
║    sp_coord   → consomme sante{} + prevoyance{} + profil_risque{}         ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False


# =============================================================================
#  SYNONYMES DE COLONNES — accepte les formats de n'importe quel client
# =============================================================================
SYNONYMES = {
    # Identifiant
    "id_adherent": [
        "id_adherent", "id_assure", "id_salarie", "adherent_id",
        "assure_id", "member_id", "employee_id", "id", "numero_adherent",
    ],
    # Données démographiques
    "age": [
        "age", "age_assure", "age_client", "age_adherent", "age_salarie",
        "annee_naissance",   # → calculé : année_courante - annee_naissance
    ],
    "sexe": [
        "sexe", "genre", "gender", "sex", "civilite",
    ],
    # Données financières
    "salaire_brut": [
        "salaire_brut", "salaire_annuel_ref", "salaire", "salaire_annuel",
        "remuneration_annuelle", "annual_salary", "brut_annuel",
        "salaire_reference", "sal_brut",
    ],
    "cotisation": [
        "cotisation", "prime", "cotisation_annuelle", "prime_annuelle",
        "cotisation_mensuelle",   # → × 12
    ],
    # Catégorie socioprofessionnelle
    "categorie": [
        "categorie_sociopro", "csp", "statut_professionnel", "categorie",
        "profession", "job_category", "sociopro", "statut",
    ],
    # Garanties souscrites
    "garanties": [
        "garanties", "garantie", "niveau_garantie", "formule",
        "offre", "pack", "contrat_type",
    ],
    # Sinistres santé
    "sinistres_sante": [
        "sinistres_sante", "remboursements_sante", "consommation_sante",
        "frais_sante", "sinistres_frais", "total_remboursements",
    ],
    "sinistres_medecine": [
        "sinistres_medecine", "frais_medecine", "remb_medecine",
        "consultations",
    ],
    "sinistres_hospitalisation": [
        "sinistres_hospitalisation", "frais_hospit", "remb_hospit",
        "hospitalisation",
    ],
    "sinistres_dentaire": [
        "sinistres_dentaire", "frais_dentaire", "remb_dentaire", "dentaire",
    ],
    "sinistres_optique": [
        "sinistres_optique", "frais_optique", "remb_optique", "optique",
    ],
    "sinistres_pharmacie": [
        "sinistres_pharmacie", "frais_pharmacie", "remb_pharmacie",
        "pharmacie",
    ],
    # Arrêts de travail
    "arrets_itt": [
        "arrets_itt", "jours_arret", "duree_arret_jours", "nb_jours_itt",
        "sick_days", "jours_maladie", "arret_travail",
    ],
    "nb_arrets": [
        "nb_arrets", "nb_arrets_itt", "nombre_arrets", "frequence_arrets",
    ],
    # Invalidité permanente
    "invalidites_ip": [
        "invalidites_ip", "taux_invalidite", "taux_ip", "invalidite",
        "incapacite_permanente", "ip_taux",
    ],
    # Décès
    "deces": [
        "deces", "capital_deces", "deces_flag", "is_deceased",
    ],
    # Données temporelles
    "annee": [
        "annee", "year", "annee_observation", "exercice",
    ],
}

# Valeurs valides pour la catégorie CSP
CSP_VALIDES = {
    "ouvrier":   ["ouvrier", "ouvriers", "worker", "blue_collar", "O"],
    "employe":   ["employe", "employes", "employee", "E", "employe_de_bureau"],
    "cadre":     ["cadre", "cadres", "manager", "C", "cadre_moyen"],
    "cadre_sup": ["cadre_sup", "cadre_superieur", "executive", "CS",
                  "cadre_dirigeant", "dirigeant"],
}

# Valeurs valides pour le sexe
SEXE_VALIDES = {
    "M": ["m", "h", "homme", "masculin", "male", "1"],
    "F": ["f", "femme", "feminin", "female", "2"],
}

# Niveaux de garantie santé reconnus
GARANTIE_VALIDES = {
    "eco":     ["eco", "economique", "base", "essentiel", "1"],
    "confort": ["confort", "standard", "classique", "2", "moyen"],
    "premium": ["premium", "superieur", "haut", "3"],
    "luxe":    ["luxe", "prestige", "excellence", "4"],
}

# Score minimum VERT pour les diagnostics
SCORE_VERT  = 85
SCORE_AMBRE = 70

# Âge minimum/maximum accepté
AGE_MIN, AGE_MAX = 16, 75

# Salaire minimum/maximum accepté (€ brut annuel)
SALAIRE_MIN, SALAIRE_MAX = 12_000, 500_000


# =============================================================================
#  CLASSE PRINCIPALE
# =============================================================================
class SPDataBuilder:
    """
    Constructeur de données Santé-Prévoyance.

    Charge, normalise, valide et enrichit les données clients avant
    de les transmettre aux agents S1, P1 et sp_coord.

    Gère 4 formats d'entrée :
      · Format M  — fichier adhérents mutuelle santé
      · Format IP — fichier salariés institution de prévoyance
      · Format A  — données agrégées (triangles par poste)
      · Format MX — mixte (santé + prévoyance dans le même fichier)

    Compatibilité garantie avec :
      · S1 Léonie  → consomme dataframe avec colonnes age/csp/garanties
      · P1 Axel    → consomme dataframe avec colonnes age/salaire/categorie
      · S2 Selma   → consomme sinistralite_par_poste
      · P3 Élodie  → consomme taux_ip, duree_ip, taux_rente
      · sp_coord   → consomme sante + prevoyance + profil_risque
    """

    VERSION = "1.0"

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger  = logging.getLogger("actuaria.sp.data_builder")
        if verbose:
            self.logger.info(f"SPDataBuilder v{self.VERSION} initialisé")

    # =========================================================================
    #  MÉTHODE PRINCIPALE
    # =========================================================================
    def construire(
        self,
        source          : Union["pd.DataFrame", str, Path],
        format_declare  : str = "auto",   # "auto" | "M" | "IP" | "A" | "MX"
        schema_mapping  : Optional[Dict]  = None,
        annee_reference : int = 2024,
        profil_force    : Optional[str]   = None,  # forcer le type client
        **kwargs,
    ) -> Dict:
        """
        Point d'entrée principal — construit les données SP depuis
        n'importe quelle source.

        Parameters
        ----------
        source : DataFrame, str ou Path
            Données source. Formats acceptés :
            · pd.DataFrame — données déjà chargées
            · str / Path   — chemin vers CSV ou Excel
        format_declare : str
            Format forcé : "auto" | "M" | "IP" | "A" | "MX"
            "auto" : détection automatique (recommandé)
        schema_mapping : dict, optional
            Mapping explicite colonnes client → noms standard.
            Ex : {"salaire_annuel_brut": "salaire_brut", "age_en_annees": "age"}
            Si None → détection automatique via synonymes.
        annee_reference : int
            Année de référence pour calcul âge depuis année de naissance.
        profil_force : str, optional
            Forcer le profil client :
            "mutuelle_individuelle" | "mutuelle_collective" |
            "ip_collective" | "assureur_mixte"

        Returns
        -------
        Dict avec les clés :
            success          bool
            format_detecte   str    "M" | "IP" | "A" | "MX"
            profil_client    str    type de client détecté
            dataframe        pd.DataFrame — données normalisées (pour S1/P1)
            sante            dict   — méta-données équipe santé
            prevoyance       dict   — méta-données équipe prévoyance
            triangles        dict   — triangles agrégés si Format A
            profil_risque    dict   — indicateurs croisés S+P pour sp_coord
            diagnostics      dict   — score qualité + alertes
            rapport          dict   — alertes et infos
            erreur           str|None
        """
        rapport = {"alertes": [], "infos": []}

        if not PANDAS_OK:
            return self._erreur("pandas non disponible — pip install pandas")

        try:
            import pandas as pd

            # ── Étape 1 : Charger la source ───────────────────────────────────
            df_raw, rapport = self._charger_source(source, rapport)
            self.logger.info(
                f"Source chargée : {len(df_raw)} lignes × {len(df_raw.columns)} colonnes"
            )

            # ── Étape 2 : Normaliser les colonnes ─────────────────────────────
            df_norm, colonnes_trouvees, rapport = self._normaliser_colonnes(
                df_raw, schema_mapping, annee_reference, rapport
            )
            self.logger.info(f"Colonnes normalisées : {sorted(colonnes_trouvees)}")

            # ── Étape 3 : Détecter le format ──────────────────────────────────
            if format_declare == "auto":
                format_detecte = self._detecter_format(df_norm, colonnes_trouvees)
            else:
                format_detecte = format_declare.upper()
            rapport["infos"].append(f"Format détecté : {format_detecte}")
            self.logger.info(f"Format : {format_detecte}")

            # ── Étape 4 : Valider et nettoyer ─────────────────────────────────
            df_clean, rapport = self._valider_nettoyer(df_norm, format_detecte, rapport)

            # ── Étape 5 : Détecter le profil client ───────────────────────────
            profil = profil_force or self._detecter_profil(df_clean, format_detecte)
            rapport["infos"].append(f"Profil client : {profil}")

            # ── Étape 6 : Construire les méta-données par direction ───────────
            meta_sante      = self._construire_meta_sante(df_clean, colonnes_trouvees)
            meta_prevoyance = self._construire_meta_prevoyance(df_clean, colonnes_trouvees)

            # ── Étape 7 : Construire les triangles si Format A ────────────────
            triangles = {}
            if format_detecte == "A":
                triangles = self._construire_triangles_agrege(df_clean, rapport)

            # ── Étape 8 : Profil de risque croisé S+P ────────────────────────
            profil_risque = self._calculer_profil_risque(
                meta_sante, meta_prevoyance, df_clean, colonnes_trouvees
            )

            # ── Étape 9 : Diagnostics qualité ─────────────────────────────────
            diagnostics = self._diagnostiquer(
                df_clean, colonnes_trouvees, format_detecte, rapport
            )

            # ── Étape 10 : DataFrame normalisé pour S1/P1 ─────────────────────
            # S1 et P1 consomment result_a2.get("dataframe") directement
            df_pour_agents = self._preparer_dataframe_agents(df_clean, format_detecte)

            n_lignes = len(df_clean)
            self.logger.info(
                f"SPDataBuilder OK | {n_lignes} assurés | format={format_detecte} | "
                f"profil={profil} | score={diagnostics['score']}/100"
            )

            return {
                "success":         True,
                "version":         self.VERSION,
                "format_detecte":  format_detecte,
                "profil_client":   profil,
                "n_lignes":        n_lignes,

                # ── DataFrame normalisé — consommé directement par S1 et P1 ──
                "dataframe":       df_pour_agents,

                # ── Méta-données par direction ─────────────────────────────────
                "sante":           meta_sante,
                "prevoyance":      meta_prevoyance,

                # ── Triangles agrégés (Format A uniquement) ──────────────────
                "triangles":       triangles,

                # ── Vision croisée S+P pour sp_coord ─────────────────────────
                "profil_risque":   profil_risque,

                # ── Diagnostics et rapport ────────────────────────────────────
                "diagnostics":     diagnostics,
                "rapport":         rapport,
                "colonnes":        sorted(colonnes_trouvees),
                "erreur":          None,
            }

        except Exception as e:
            self.logger.error(f"SPDataBuilder ERREUR : {e}", exc_info=True)
            return self._erreur(str(e))

    # =========================================================================
    #  ÉTAPE 1 : CHARGEMENT
    # =========================================================================
    def _charger_source(self, source, rapport: Dict) -> Tuple:
        """Charge la source depuis DataFrame, chemin CSV ou Excel."""
        import pandas as pd

        if isinstance(source, pd.DataFrame):
            rapport["infos"].append("Source : DataFrame fourni directement")
            return source.copy(), rapport

        path = Path(str(source))
        if not path.exists():
            raise FileNotFoundError(f"Fichier non trouvé : {path}")

        ext = path.suffix.lower()
        if ext == ".csv":
            # Essayer différents séparateurs
            for sep in [",", ";", "\t", "|"]:
                try:
                    df = pd.read_csv(path, sep=sep, encoding="utf-8")
                    if len(df.columns) >= 2:
                        rapport["infos"].append(f"CSV chargé (sep='{sep}') : {len(df)} lignes")
                        return df, rapport
                except Exception:
                    continue
            raise ValueError(f"Impossible de lire le CSV : {path}")

        elif ext in (".xlsx", ".xls"):
            # Chercher le bon onglet
            xl = pd.ExcelFile(path)
            onglet = self._choisir_onglet(xl.sheet_names, rapport)
            df = pd.read_excel(path, sheet_name=onglet)
            rapport["infos"].append(
                f"Excel chargé (onglet='{onglet}') : {len(df)} lignes"
            )
            return df, rapport

        else:
            raise ValueError(f"Format non supporté : {ext}. Utilisez CSV ou Excel.")

    def _choisir_onglet(self, sheet_names: List[str], rapport: Dict) -> str:
        """Choisit l'onglet le plus pertinent dans un fichier Excel."""
        # Priorité aux onglets avec des noms liés aux données SP
        priorite = [
            "adherents", "salaries", "donnees", "data", "portefeuille",
            "assures", "membres", "effectifs", "sinistres", "contrats",
        ]
        for p in priorite:
            for s in sheet_names:
                if p in s.lower():
                    rapport["infos"].append(f"Onglet sélectionné : '{s}'")
                    return s
        # Fallback : premier onglet
        rapport["alertes"].append(
            f"Onglet auto-sélectionné : '{sheet_names[0]}'. "
            f"Onglets disponibles : {sheet_names}. "
            f"Utilisez schema_mapping si nécessaire."
        )
        return sheet_names[0]

    # =========================================================================
    #  ÉTAPE 2 : NORMALISATION DES COLONNES
    # =========================================================================
    def _normaliser_colonnes(
        self,
        df: "pd.DataFrame",
        schema_mapping: Optional[Dict],
        annee_reference: int,
        rapport: Dict,
    ) -> Tuple:
        """
        Normalise les colonnes vers les noms standard ActuarIA.
        Priorité : schema_mapping explicite > détection auto via synonymes.
        """
        import pandas as pd

        df_out = df.copy()
        colonnes_norm = df.columns.str.lower().str.strip().str.replace(" ", "_")
        df_out.columns = colonnes_norm
        colonnes_trouvees = set()

        # Appliquer le mapping explicite en premier
        if schema_mapping:
            for col_client, col_std in schema_mapping.items():
                col_client_norm = col_client.lower().strip().replace(" ", "_")
                if col_client_norm in df_out.columns:
                    df_out = df_out.rename(columns={col_client_norm: col_std})
                    colonnes_trouvees.add(col_std)
                    rapport["infos"].append(
                        f"Mapping explicite : '{col_client}' → '{col_std}'"
                    )

        # Détection automatique via synonymes
        for col_std, synonymes in SYNONYMES.items():
            if col_std in df_out.columns:
                colonnes_trouvees.add(col_std)
                continue
            for syn in synonymes:
                syn_norm = syn.lower().strip().replace(" ", "_")
                if syn_norm in df_out.columns:
                    df_out = df_out.rename(columns={syn_norm: col_std})
                    colonnes_trouvees.add(col_std)
                    if self.verbose:
                        rapport["infos"].append(
                            f"Auto-détecté : '{syn}' → '{col_std}'"
                        )
                    break

        # Cas spécial : calculer l'âge depuis l'année de naissance
        if "age" not in colonnes_trouvees and "annee_naissance" in df_out.columns:
            df_out["age"] = annee_reference - pd.to_numeric(
                df_out["annee_naissance"], errors="coerce"
            )
            colonnes_trouvees.add("age")
            rapport["infos"].append(
                f"Âge calculé depuis annee_naissance (référence {annee_reference})"
            )

        # Cas spécial : cotisation mensuelle → annuelle
        if "cotisation" in df_out.columns:
            cot = pd.to_numeric(df_out["cotisation"], errors="coerce")
            if cot.median() < 500:   # probablement mensuelle si < 500€
                df_out["cotisation"] = cot * 12
                rapport["infos"].append(
                    "Cotisation convertie en annuelle (médiane < 500€ → ×12)"
                )

        return df_out, colonnes_trouvees, rapport

    # =========================================================================
    #  ÉTAPE 3 : DÉTECTION FORMAT
    # =========================================================================
    def _detecter_format(self, df: "pd.DataFrame", colonnes: set) -> str:
        """
        Détecte automatiquement le format des données.

        Logique :
          Format M  → a des données santé (sinistres_sante, garanties)
                       mais PAS de données salariales
          Format IP → a des données salariales (salaire_brut, arrets_itt)
                       mais PAS de données santé spécifiques
          Format MX → a les deux
          Format A  → structure triangulaire (peu de lignes, colonnes numériques)
        """
        a_sante     = bool(colonnes & {"sinistres_sante", "garanties",
                                        "sinistres_medecine", "sinistres_hospitalisation"})
        a_prevoyance = bool(colonnes & {"salaire_brut", "arrets_itt",
                                         "invalidites_ip", "deces"})

        # Détecter structure triangulaire : peu de lignes (années),
        # colonnes numériques en majorité
        import pandas as pd
        n_lignes = len(df)
        n_cols_num = sum(1 for c in df.columns
                         if pd.api.types.is_numeric_dtype(df[c]))
        est_triangle = (n_lignes <= 30 and n_cols_num >= 5
                        and n_cols_num / max(len(df.columns), 1) > 0.7)

        if est_triangle and not a_sante and not a_prevoyance:
            return "A"
        if a_sante and a_prevoyance:
            return "MX"
        if a_sante:
            return "M"
        if a_prevoyance:
            return "IP"

        # Fallback : si colonne age présente → Format M (plus courant)
        if "age" in colonnes:
            return "M"
        return "A"

    # =========================================================================
    #  ÉTAPE 4 : VALIDATION ET NETTOYAGE
    # =========================================================================
    def _valider_nettoyer(
        self, df: "pd.DataFrame", format_detecte: str, rapport: Dict
    ) -> Tuple:
        """Valide et nettoie les données — supprime les lignes invalides."""
        import pandas as pd

        n_avant = len(df)
        masque_valide = pd.Series([True] * len(df), index=df.index)

        # Valider l'âge
        if "age" in df.columns:
            df["age"] = pd.to_numeric(df["age"], errors="coerce")
            # 1. Remplir les NaN par la médiane AVANT le masque
            age_valides = df["age"].dropna()
            age_median = float(age_valides.median()) if len(age_valides) > 0 else 40.0
            n_nan = int(df["age"].isna().sum())
            if n_nan > 0:
                df.loc[df["age"].isna(), "age"] = age_median
                rapport["infos"].append(
                    f"{n_nan} âge(s) manquant(s) remplacé(s) par la médiane ({age_median:.0f} ans)"
                )
            # 2. Masque sur les valeurs hors plage
            masque_age = df["age"].between(AGE_MIN, AGE_MAX)
            n_age_invalide = int((~masque_age).sum())
            if n_age_invalide > 0:
                rapport["alertes"].append(
                    f"⚠️ {n_age_invalide} ligne(s) avec âge hors [{AGE_MIN},{AGE_MAX}] — supprimées"
                )
            masque_valide &= masque_age

        # Valider le salaire
        if "salaire_brut" in df.columns:
            df["salaire_brut"] = pd.to_numeric(df["salaire_brut"], errors="coerce")
            masque_sal = (df["salaire_brut"] >= SALAIRE_MIN) | df["salaire_brut"].isna()
            n_sal_invalide = (~masque_sal).sum()
            if n_sal_invalide > 0:
                rapport["alertes"].append(
                    f"⚠️ {n_sal_invalide} salaire(s) < {SALAIRE_MIN}€ — remplacés par {SALAIRE_MIN}€"
                )
                df.loc[~masque_sal & df["salaire_brut"].notna(), "salaire_brut"] = SALAIRE_MIN

        # Normaliser le sexe
        if "sexe" in df.columns:
            df["sexe"] = df["sexe"].astype(str).str.lower().str.strip()
            for std, variantes in SEXE_VALIDES.items():
                df.loc[df["sexe"].isin(variantes), "sexe"] = std
            df.loc[~df["sexe"].isin(["M", "F"]), "sexe"] = "M"  # fallback

        # Normaliser la catégorie CSP — map inversé pour éviter les écrasements
        if "categorie" in df.columns:
            df["categorie"] = df["categorie"].astype(str).str.lower().str.strip()
            _csp_map = {v: k for k, vs in CSP_VALIDES.items() for v in vs}
            df["categorie"] = df["categorie"].map(
                lambda x: _csp_map.get(x, x if x in CSP_VALIDES else "employe")
            )

        # Normaliser le niveau de garantie
        if "garanties" in df.columns:
            df["garanties"] = df["garanties"].astype(str).str.lower().str.strip()
            for std, variantes in GARANTIE_VALIDES.items():
                df.loc[df["garanties"].isin(variantes), "garanties"] = std
            df.loc[~df["garanties"].isin(GARANTIE_VALIDES.keys()), "garanties"] = "confort"

        # Appliquer le masque de validité
        df_clean = df[masque_valide].copy().reset_index(drop=True)
        n_apres = len(df_clean)

        if n_apres < n_avant:
            rapport["alertes"].append(
                f"⚠️ {n_avant - n_apres} ligne(s) invalide(s) supprimées "
                f"({n_apres}/{n_avant} conservées)"
            )

        if n_apres == 0:
            raise ValueError(
                "Aucune ligne valide après nettoyage. "
                "Vérifiez le format de votre fichier."
            )

        return df_clean, rapport

    # =========================================================================
    #  ÉTAPE 5 : DÉTECTION PROFIL CLIENT
    # =========================================================================
    def _detecter_profil(self, df: "pd.DataFrame", format_detecte: str) -> str:
        """
        Détecte le profil du client selon le format et les données disponibles.
        """
        if format_detecte == "MX":
            return "assureur_mixte"
        if format_detecte == "IP":
            return "ip_collective"

        # Format M : distinguer individuel vs collectif
        # Collectif → colonne 'contrat' avec valeur 'collectif'
        #           → ou grande taille (>= 500 adhérents) avec garanties uniformes
        if "contrat" in df.columns:
            if any(v in str(df["contrat"].iloc[0]).lower()
                   for v in ["collectif", "collective", "group", "entreprise"]):
                return "mutuelle_collective"
            return "mutuelle_individuelle"
        # Heuristique volume + uniformité garanties
        if "garanties" in df.columns and len(df) >= 500:
            import pandas as pd
            pct_dominant = df["garanties"].value_counts(normalize=True).iloc[0]
            if pct_dominant >= 0.80:  # 80%+ sur un seul niveau → collectif
                return "mutuelle_collective"
        return "mutuelle_individuelle"

    # =========================================================================
    #  ÉTAPE 6 : MÉTA-DONNÉES PAR DIRECTION
    # =========================================================================
    def _construire_meta_sante(
        self, df: "pd.DataFrame", colonnes: set
    ) -> Dict:
        """Construit les méta-données pour l'équipe Santé (S1, S2)."""
        import pandas as pd

        meta = {
            "disponible":      bool(colonnes & {"age", "garanties", "sinistres_sante",
                                                  "sinistres_medecine"}),
            "nb_adherents":    len(df),
            "age_moyen":       float(df["age"].mean()) if "age" in df.columns else None,
            "age_median":      float(df["age"].median()) if "age" in df.columns else None,
            "ratio_h_f":       None,
            "garantie_dominante": None,
            "cotisation_moyenne": None,
            "sinistralite_par_poste": {},
            "pyramide_ages":   {},
        }

        # Ratio H/F
        if "sexe" in df.columns:
            vh = (df["sexe"] == "M").sum()
            vf = (df["sexe"] == "F").sum()
            meta["ratio_h_f"] = round(float(vh) / max(float(vf), 1), 2)

        # Garantie dominante
        if "garanties" in df.columns:
            meta["garantie_dominante"] = str(df["garanties"].mode().iloc[0])

        # Cotisation moyenne
        if "cotisation" in df.columns:
            meta["cotisation_moyenne"] = float(
                pd.to_numeric(df["cotisation"], errors="coerce").mean()
            )

        # Sinistralité par poste
        for poste in ["medecine", "hospitalisation", "dentaire", "optique", "pharmacie"]:
            col = f"sinistres_{poste}"
            if col in df.columns:
                vals = pd.to_numeric(df[col], errors="coerce")
                meta["sinistralite_par_poste"][poste] = {
                    "moyenne":   round(float(vals.mean()), 2),
                    "mediane":   round(float(vals.median()), 2),
                    "total":     round(float(vals.sum()), 2),
                    "n_sinistres": int(vals.notna().sum()),
                }

        # Sinistralité totale si disponible
        if "sinistres_sante" in df.columns:
            vals = pd.to_numeric(df["sinistres_sante"], errors="coerce")
            meta["sinistres_totaux"] = round(float(vals.sum()), 2)
            meta["sinistres_moyens"] = round(float(vals.mean()), 2)

        # Pyramide des âges par tranche
        if "age" in df.columns:
            tranches = [(0,17),(18,25),(26,35),(36,45),(46,55),(56,65),(66,99)]
            for a, b in tranches:
                n = int(df["age"].between(a, b).sum())
                if n > 0:
                    meta["pyramide_ages"][f"{a}-{b}"] = n

        return meta

    def _construire_meta_prevoyance(
        self, df: "pd.DataFrame", colonnes: set
    ) -> Dict:
        """Construit les méta-données pour l'équipe Prévoyance (P1, P2, P3)."""
        import pandas as pd

        meta = {
            "disponible":      bool(colonnes & {"salaire_brut", "arrets_itt",
                                                  "invalidites_ip", "categorie"}),
            "nb_salaries":     len(df),
            "age_moyen":       float(df["age"].mean()) if "age" in df.columns else None,
            "salaire_moyen":   None,
            "salaire_median":  None,
            "repartition_csp": {},
            "taux_arret":      None,
            "taux_ip":         None,
            "taux_deces":      None,
            "nb_arrets":       None,
            "duree_arret_moyenne_jours": None,
        }

        # Salaires
        if "salaire_brut" in df.columns:
            sal = pd.to_numeric(df["salaire_brut"], errors="coerce")
            meta["salaire_moyen"]  = round(float(sal.mean()), 2)
            meta["salaire_median"] = round(float(sal.median()), 2)

        # Répartition CSP
        if "categorie" in df.columns:
            csp_counts = df["categorie"].value_counts()
            total = len(df)
            meta["repartition_csp"] = {
                k: {"n": int(v), "pct": round(v/total*100, 1)}
                for k, v in csp_counts.items()
            }

        # Taux d'arrêt ITT
        if "arrets_itt" in df.columns:
            arrets = pd.to_numeric(df["arrets_itt"], errors="coerce")
            n_arrets = int((arrets > 0).sum())
            meta["nb_arrets"]   = n_arrets
            meta["taux_arret"]  = round(n_arrets / max(len(df), 1), 4)
            meta["duree_arret_moyenne_jours"] = round(
                float(arrets[arrets > 0].mean()), 1
            ) if n_arrets > 0 else 0.0

        # Taux d'invalidité
        if "invalidites_ip" in df.columns:
            ip = pd.to_numeric(df["invalidites_ip"], errors="coerce")
            n_ip = int((ip > 0).sum())
            meta["taux_ip"] = round(n_ip / max(len(df), 1), 4)

        # Taux de décès
        if "deces" in df.columns:
            dec = pd.to_numeric(df["deces"], errors="coerce")
            n_dec = int((dec > 0).sum())
            meta["taux_deces"] = round(n_dec / max(len(df), 1), 4)

        return meta

    # =========================================================================
    #  ÉTAPE 7 : TRIANGLES AGRÉGÉS (FORMAT A)
    # =========================================================================
    def _construire_triangles_agrege(self, df: "pd.DataFrame", rapport: Dict) -> Dict:
        """
        Construit les triangles de développement depuis des données agrégées.
        Format A : lignes = années de survenance, colonnes = périodes.
        """
        import pandas as pd

        triangles = {}
        try:
            # Identifier les colonnes numériques (périodes de développement)
            cols_num = [c for c in df.columns
                        if pd.api.types.is_numeric_dtype(df[c])]

            if len(cols_num) >= 3:
                # Construire un triangle numpy
                tri = df[cols_num].values.astype(float)
                # Remplacer les NaN/0 par 0 dans le triangle
                tri = np.nan_to_num(tri, nan=0.0)
                triangles["principal"] = tri
                rapport["infos"].append(
                    f"Triangle agrégé construit : {tri.shape[0]}×{tri.shape[1]}"
                )
            else:
                rapport["alertes"].append(
                    "Format A détecté mais moins de 3 colonnes numériques — "
                    "triangle non construit. Vérifiez le format."
                )

        except Exception as e:
            rapport["alertes"].append(f"Erreur construction triangle : {e}")

        return triangles

    # =========================================================================
    #  ÉTAPE 8 : PROFIL DE RISQUE CROISÉ S+P
    # =========================================================================
    def _calculer_profil_risque(
        self,
        meta_sante: Dict,
        meta_prevoyance: Dict,
        df: "pd.DataFrame",
        colonnes: set,
    ) -> Dict:
        """
        Calcule les indicateurs de risque croisé santé + prévoyance.
        Utilisé par sp_coord pour la vision consolidée.
        """
        profil = {
            "age_moyen":          None,
            "ratio_h_f":          meta_sante.get("ratio_h_f"),
            "correlation_sp":     None,   # corrélation sinistres S et arrêts P
            "poly_sinistralite":  None,   # % adhérents sinistrés en S ET P
            "risque_age":         None,   # "faible" | "moyen" | "élevé"
            "risque_csp":         None,
            "indicateurs":        [],
        }

        # Âge moyen consolidé
        ages = []
        if meta_sante.get("age_moyen") is not None:    ages.append(meta_sante["age_moyen"])
        if meta_prevoyance.get("age_moyen") is not None: ages.append(meta_prevoyance["age_moyen"])
        if ages:
            profil["age_moyen"] = round(float(np.mean(ages)), 1)

        # Risque lié à l'âge
        age_m = profil["age_moyen"]
        if age_m:
            if age_m < 35:
                profil["risque_age"] = "faible"
            elif age_m < 48:
                profil["risque_age"] = "moyen"
            else:
                profil["risque_age"] = "élevé"

        # Risque CSP
        csp = meta_prevoyance.get("repartition_csp", {})
        pct_ouvrier = csp.get("ouvrier", {}).get("pct", 0)
        if pct_ouvrier > 40:
            profil["risque_csp"] = "élevé"
            profil["indicateurs"].append(
                f"⚠️ {pct_ouvrier:.0f}% ouvriers — sinistralité ITT élevée attendue"
            )
        elif pct_ouvrier > 20:
            profil["risque_csp"] = "moyen"
        else:
            profil["risque_csp"] = "faible"

        # Poly-sinistralité (si données individuelles avec S et P)
        import pandas as pd
        if "sinistres_sante" in df.columns and "arrets_itt" in df.columns:
            sin_s = pd.to_numeric(df["sinistres_sante"], errors="coerce") > 0
            arr_p = pd.to_numeric(df["arrets_itt"], errors="coerce") > 0
            poly = (sin_s & arr_p).sum()
            pct_poly = round(float(poly) / max(len(df), 1) * 100, 1)
            profil["poly_sinistralite"] = pct_poly
            if pct_poly > 5:
                profil["indicateurs"].append(
                    f"🔴 {pct_poly:.1f}% d'adhérents sinistrés en santé ET en prévoyance "
                    f"— risque de basculement ITT → IP"
                )
            elif pct_poly > 2:
                profil["indicateurs"].append(
                    f"⚠️ {pct_poly:.1f}% adhérents en poly-sinistralité — surveiller"
                )

        return profil

    # =========================================================================
    #  ÉTAPE 9 : DIAGNOSTICS QUALITÉ
    # =========================================================================
    def _diagnostiquer(
        self,
        df: "pd.DataFrame",
        colonnes: set,
        format_detecte: str,
        rapport: Dict,
    ) -> Dict:
        """
        Évalue la qualité des données sur 7 contrôles (100 points).

        C1 — Colonnes essentielles présentes       (20 pts)
        C2 — Complétude (taux de valeurs manquantes) (20 pts)
        C3 — Âge valide et cohérent               (15 pts)
        C4 — Salaire valide (Format IP)            (15 pts)
        C5 — Volume suffisant                      (10 pts)
        C6 — Cohérence interne                     (10 pts)
        C7 — Richesse des données SP               (10 pts)
        """
        import pandas as pd

        controles = []
        score = 0

        # C1 — Colonnes essentielles
        if format_detecte in ("M", "MX"):
            cols_ess = {"age"}
            cols_opt = {"sexe", "garanties", "cotisation"}
        elif format_detecte == "IP":
            cols_ess = {"age", "salaire_brut"}
            cols_opt = {"categorie", "arrets_itt"}
        else:
            cols_ess = set()
            cols_opt = set()

        manquantes_ess = cols_ess - colonnes
        manquantes_opt = cols_opt - colonnes
        if not manquantes_ess:
            c1_pts = 20; c1_st = "VERT"
            c1_msg = f"Colonnes essentielles présentes ✅"
            if manquantes_opt:
                c1_msg += f" (optionnelles manquantes : {manquantes_opt})"
        elif len(manquantes_ess) == 1:
            c1_pts = 10; c1_st = "AMBRE"
            c1_msg = f"Colonne manquante : {manquantes_ess} — fonctionnement dégradé"
        else:
            c1_pts = 0; c1_st = "ROUGE"
            c1_msg = f"Colonnes essentielles manquantes : {manquantes_ess}"
        controles.append({"code":"C1","libelle":"Colonnes essentielles","points":c1_pts,
                           "statut":c1_st,"message":c1_msg,"max":20})
        score += c1_pts

        # C2 — Complétude
        if len(df) > 0 and len(colonnes) > 0:
            taux_na = df[list(colonnes & set(df.columns))].isna().mean().mean()
            if taux_na <= 0.05:
                c2_pts = 20; c2_st = "VERT"
                c2_msg = f"Complétude : {(1-taux_na)*100:.1f}% ✅"
            elif taux_na <= 0.15:
                c2_pts = 12; c2_st = "AMBRE"
                c2_msg = f"Complétude : {(1-taux_na)*100:.1f}% — données partielles"
            else:
                c2_pts = 4; c2_st = "ROUGE"
                c2_msg = f"Complétude : {(1-taux_na)*100:.1f}% — trop de valeurs manquantes"
        else:
            c2_pts = 0; c2_st = "ROUGE"; c2_msg = "Aucune donnée"
        controles.append({"code":"C2","libelle":"Complétude données","points":c2_pts,
                           "statut":c2_st,"message":c2_msg,"max":20})
        score += c2_pts

        # C3 — Âge
        if "age" in df.columns:
            ages = pd.to_numeric(df["age"], errors="coerce").dropna()
            pct_valide = (ages.between(AGE_MIN, AGE_MAX)).mean()
            if pct_valide >= 0.95:
                c3_pts = 15; c3_st = "VERT"
                c3_msg = f"Âge ∈ [{AGE_MIN},{AGE_MAX}] : {pct_valide*100:.1f}% ✅ | moy={ages.mean():.1f} ans"
            elif pct_valide >= 0.80:
                c3_pts = 8; c3_st = "AMBRE"
                c3_msg = f"Âge : {pct_valide*100:.1f}% valide — quelques valeurs aberrantes"
            else:
                c3_pts = 0; c3_st = "ROUGE"
                c3_msg = f"Âge : {pct_valide*100:.1f}% valide — données âge problématiques"
        else:
            c3_pts = 5; c3_st = "AMBRE"; c3_msg = "Âge absent — utilisation de l'âge moyen par défaut"
        controles.append({"code":"C3","libelle":"Cohérence âge","points":c3_pts,
                           "statut":c3_st,"message":c3_msg,"max":15})
        score += c3_pts

        # C4 — Salaire (Format IP)
        if format_detecte in ("IP", "MX") and "salaire_brut" in df.columns:
            sal = pd.to_numeric(df["salaire_brut"], errors="coerce").dropna()
            pct_valide = (sal.between(SALAIRE_MIN, SALAIRE_MAX)).mean()
            if pct_valide >= 0.95:
                c4_pts = 15; c4_st = "VERT"
                c4_msg = f"Salaires ∈ [{SALAIRE_MIN/1000:.0f}k,{SALAIRE_MAX/1000:.0f}k€] : {pct_valide*100:.1f}% ✅ | moy={sal.mean()/1000:.1f}k€"
            elif pct_valide >= 0.80:
                c4_pts = 8; c4_st = "AMBRE"
                c4_msg = f"Salaires : {pct_valide*100:.1f}% valide"
            else:
                c4_pts = 0; c4_st = "ROUGE"
                c4_msg = "Salaires : trop de valeurs hors plage — vérifier l'unité (€ annuel attendu)"
        elif format_detecte in ("IP", "MX"):
            c4_pts = 0; c4_st = "ROUGE"
            c4_msg = "Salaire manquant — obligatoire pour Format IP"
        else:
            c4_pts = 15; c4_st = "VERT"
            c4_msg = "N/A (format santé uniquement)"
        controles.append({"code":"C4","libelle":"Cohérence salaires","points":c4_pts,
                           "statut":c4_st,"message":c4_msg,"max":15})
        score += c4_pts

        # C5 — Volume
        n = len(df)
        if n >= 1000:
            c5_pts = 10; c5_st = "VERT"
            c5_msg = f"{n:,} lignes ✅ — volume statistiquement significatif"
        elif n >= 100:
            c5_pts = 6; c5_st = "AMBRE"
            c5_msg = f"{n:,} lignes — volume limité, résultats indicatifs"
        elif n >= 10:
            c5_pts = 3; c5_st = "AMBRE"
            c5_msg = f"{n:,} lignes — très faible volume, à utiliser avec précaution"
        else:
            c5_pts = 0; c5_st = "ROUGE"
            c5_msg = f"{n:,} lignes — volume insuffisant pour une analyse actuarielle"
        controles.append({"code":"C5","libelle":"Volume suffisant","points":c5_pts,
                           "statut":c5_st,"message":c5_msg,"max":10})
        score += c5_pts

        # C6 — Cohérence interne
        alertes_coherence = []
        if "arrets_itt" in df.columns and "age" in df.columns:
            arrets = pd.to_numeric(df["arrets_itt"], errors="coerce")
            ages   = pd.to_numeric(df["age"], errors="coerce")
            # Un arrêt ne peut pas dépasser 365 × (65 - age) jours
            arrets_impossibles = (arrets > 365 * (65 - ages)).sum()
            if arrets_impossibles > 0:
                alertes_coherence.append(f"{arrets_impossibles} arrêt(s) d'une durée impossible")
        if "sinistres_sante" in df.columns and "cotisation" in df.columns:
            sin = pd.to_numeric(df["sinistres_sante"], errors="coerce")
            cot = pd.to_numeric(df["cotisation"], errors="coerce")
            # S/P > 5 est anormal individuellement
            sp_excessif = ((sin / cot.replace(0, np.nan)) > 5).sum()
            if sp_excessif > 0:
                alertes_coherence.append(f"{sp_excessif} S/P > 5 (sinistres >> cotisation)")

        if not alertes_coherence:
            c6_pts = 10; c6_st = "VERT"; c6_msg = "Cohérence interne vérifiée ✅"
        elif len(alertes_coherence) == 1:
            c6_pts = 6; c6_st = "AMBRE"; c6_msg = f"⚠️ {alertes_coherence[0]}"
        else:
            c6_pts = 2; c6_st = "ROUGE"; c6_msg = f"❌ {len(alertes_coherence)} incohérences"
        controles.append({"code":"C6","libelle":"Cohérence interne","points":c6_pts,
                           "statut":c6_st,"message":c6_msg,"max":10})
        score += c6_pts

        # C7 — Richesse des données SP
        cols_sp_riches = {
            "sinistres_medecine","sinistres_hospitalisation","sinistres_dentaire",
            "sinistres_optique","sinistres_pharmacie","arrets_itt","invalidites_ip",
            "deces","nb_arrets","garanties",
        }
        n_riches = len(colonnes & cols_sp_riches)
        if n_riches >= 5:
            c7_pts = 10; c7_st = "VERT"
            c7_msg = f"{n_riches}/10 colonnes SP riches ✅ — modélisation fine possible"
        elif n_riches >= 3:
            c7_pts = 6; c7_st = "AMBRE"
            c7_msg = f"{n_riches}/10 colonnes SP — modélisation partielle"
        else:
            c7_pts = 2; c7_st = "AMBRE"
            c7_msg = f"{n_riches}/10 colonnes SP — modélisation par tables de référence"
        controles.append({"code":"C7","libelle":"Richesse données SP","points":c7_pts,
                           "statut":c7_st,"message":c7_msg,"max":10})
        score += c7_pts

        # Statut global
        statut = "VERT" if score >= SCORE_VERT else ("AMBRE" if score >= SCORE_AMBRE else "ROUGE")

        return {
            "score":     score,
            "statut":    statut,
            "controles": controles,
            "alertes":   [c["message"] for c in controles if c["statut"] in ("AMBRE","ROUGE")],
        }

    # =========================================================================
    #  ÉTAPE 10 : DATAFRAME POUR AGENTS S1 ET P1
    # =========================================================================
    def _preparer_dataframe_agents(
        self, df: "pd.DataFrame", format_detecte: str
    ) -> "pd.DataFrame":
        """
        Prépare le DataFrame normalisé dans le format exact attendu par S1 et P1.

        S1 cherche : age, age_assure, age_client, categorie_sociopro, csp
        P1 cherche : age, salaire_annuel_ref, salaire_brut, salaire,
                     categorie_sociopro, csp, statut_professionnel
        """
        import pandas as pd

        df_out = df.copy()

        # Ajouter les alias de colonnes attendus par S1 et P1
        if "age" in df_out.columns:
            df_out["age_assure"] = df_out["age"]
            df_out["age_client"] = df_out["age"]

        if "categorie" in df_out.columns:
            df_out["categorie_sociopro"]    = df_out["categorie"]
            df_out["csp"]                   = df_out["categorie"]
            df_out["statut_professionnel"]  = df_out["categorie"]

        if "salaire_brut" in df_out.columns:
            df_out["salaire"]             = df_out["salaire_brut"]
            df_out["salaire_annuel_ref"]  = df_out["salaire_brut"]

        return df_out

    # =========================================================================
    #  UTILITAIRES
    # =========================================================================
    def _erreur(self, msg: str) -> Dict:
        self.logger.error(f"SPDataBuilder ERREUR : {msg}")
        return {
            "success":        False,
            "format_detecte": None,
            "profil_client":  None,
            "dataframe":      None,
            "sante":          {},
            "prevoyance":     {},
            "triangles":      {},
            "profil_risque":  {},
            "diagnostics":    {"score":0,"statut":"ROUGE","controles":[],"alertes":[msg]},
            "rapport":        {"alertes":[msg],"infos":[]},
            "colonnes":       [],
            "erreur":         msg,
        }
