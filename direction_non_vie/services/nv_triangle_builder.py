# =============================================================================
#  ActuarIA — Direction Non-Vie / Service Data
#  nv_triangle_builder.py  —  Construction et séparation des triangles Non-Vie
#
#  Rôle :
#    Point d'entrée unique pour la construction des triangles de développement
#    à partir de n'importe quel format de données (triangle cumulé, incrémental,
#    données agrégées ou sinistres individuels).
#
#    Fonctionnalité clé : séparation automatique Attritional / Grands sinistres
#    via le Large Loss Threshold (LLT), conformément au Guide Institut des
#    Actuaires 2023 (Section 3.2 — Homogénéité des données).
#
#  Formats acceptés en entrée :
#    1. Triangle cumulé    (matrice n×m, Excel ou CSV)
#    2. Triangle incrémental (paiements annuels, à cumuler)
#    3. Données agrégées   (une ligne par cellule du triangle)
#    4. Sinistres individuels (une ligne par sinistre/paiement)
#
#  Sorties :
#    · triangle_total      : np.ndarray — tous sinistres confondus
#    · triangle_attritional: np.ndarray — sinistres < LLT (si LLT fourni)
#    · triangle_grands     : np.ndarray — sinistres ≥ LLT (si LLT fourni)
#    · grands_sinistres    : pd.DataFrame — liste des grands sinistres identifiés
#    · statistiques        : dict — métriques de qualité et LLT suggéré
#
#  Usage :
#    from direction_non_vie.services.nv_triangle_builder import NVTriangleBuilder
#
#    builder = NVTriangleBuilder()
#    result  = builder.construire(source=df, llt=500_000, schema_mapping={...})
#
#    triangle_total       = result['triangle_total']
#    triangle_attritional = result['triangle_attritional']
#    grands_sinistres     = result['grands_sinistres']
#
#  Références :
#    · Guide Institut des Actuaires 2023 — Bonnes pratiques provisionnement NV
#    · EIOPA Guidelines on Non-Life Technical Provisions — Art. 17
#    · Mack (1993) — Conditions d'homogénéité des triangles CL
#
#  Auteur  : ActuarIA v5.0
#  Version : 1.0.0
# =============================================================================

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# Réutilisation du validateur existant (migration progressive)
from direction_non_vie.services.nv_triangle_validator import TriangleValidator

logger = logging.getLogger('actuaria.direction_non_vie.services.triangle_builder')


# =============================================================================
#  CONSTANTES
# =============================================================================

# Percentile utilisé pour le calcul automatique du LLT suggéré
# Référence : pratique marché française (FFA, FFSA)
LLT_PERCENTILE_SUGGESTION = 0.95

# Nombre minimum de grands sinistres pour un traitement statistique fiable
# En dessous : traitement dossier par dossier recommandé
SEUIL_MIN_GRANDS_SINISTRES_STATISTIQUE = 20

# Synonymes de colonnes acceptés pour les données individuelles
# Permet d'accepter les formats de n'importe quel client sans configuration
SYNONYMES_COLONNES = {
    'sinistre_id': [
        'claim_id', 'id_sinistre', 'num_sinistre', 'sinistre_id',
        'id_claim', 'claimid', 'claim_number', 'numero_sinistre',
    ],
    'annee_survenance': [
        'annee_survenance', 'ay', 'accident_year', 'annee_sinistre',
        'year_of_loss', 'survenance', 'annee', 'year', 'origin_year',
    ],
    'annee_paiement': [
        'annee_paiement', 'dy', 'development_year', 'annee_dev',
        'payment_year', 'calendar_year', 'annee_calendaire',
    ],
    'annee_developpement': [
        'annee_developpement', 'dev', 'development', 'periode',
        'lag', 'dev_year', 'periode_dev', 'development_period',
    ],
    'montant': [
        'montant', 'montant_cumule', 'paid', 'incurred', 'charge',
        'cout', 'amount', 'claim_amount', 'montant_sinistre',
        'cout_sinistre', 'charge_sinistre', 'cumulative_paid',
        'paid_losses', 'incurred_losses', 'montant_paye',
    ],
}


# =============================================================================
#  CLASSE PRINCIPALE
# =============================================================================

class NVTriangleBuilder:
    """
    Constructeur de triangles de développement pour la Direction Non-Vie.

    Encapsule TriangleValidator (validation et construction de base) et y ajoute :
      · Détection et suggestion automatique du Large Loss Threshold (LLT)
      · Séparation attritional / grands sinistres sur données individuelles
      · Construction simultanée de 3 triangles (total, attritional, grands)
      · Statistiques détaillées sur la composition du portefeuille

    Conformité : Guide IA 2023 Section 3.2 — Homogénéité des triangles.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialise le builder.

        Parameters
        ----------
        verbose : bool
            Si True, affiche les logs détaillés de construction.
        """
        # Réutilisation du validateur existant — pas de duplication de code
        self._validator = TriangleValidator(verbose=verbose)
        self.verbose    = verbose
        self.logger     = logging.getLogger(
            'actuaria.direction_non_vie.services.triangle_builder'
        )

    # =========================================================================
    #  MÉTHODE PRINCIPALE
    # =========================================================================

    def construire(
        self,
        source          : Union[pd.DataFrame, np.ndarray, str],
        llt             : Optional[float]  = None,
        schema_mapping  : Optional[Dict]   = None,
        mode_declare    : str              = 'auto',
        annee_debut     : Optional[int]    = None,
        nom_onglet      : Optional[str]    = None,
    ) -> Dict:
        """
        Point d'entrée principal — construit les triangles depuis n'importe
        quelle source de données.

        Parameters
        ----------
        source : DataFrame, ndarray ou str
            Données source. Formats acceptés :
            · pd.DataFrame avec colonnes sinistres individuels ou agrégés
            · np.ndarray  triangle déjà construit (cumulé ou incrémental)
            · str          chemin vers un fichier CSV ou Excel
        llt : float, optional
            Large Loss Threshold en euros. Sinistres ≥ LLT sont traités
            séparément. Si None, le LLT est suggéré automatiquement via
            le percentile P95 des montants individuels.
            Ignoré si la source est un triangle (pas de données individuelles).
        schema_mapping : dict, optional
            Mapping explicite des colonnes client → noms standard.
            Exemple : {'montant': 'charge_brute', 'annee_survenance': 'ay'}
            Si None, détection automatique via synonymes.
        mode_declare : str
            Mode de lecture forcé : 'auto' | 'cumule' | 'non_cumule' | 'brutes'
            'auto' : détection automatique (recommandé)
        annee_debut : int, optional
            Première année calendaire du triangle (pour les labels).
            Si None, utilise les indices 0, 1, 2...

        Returns
        -------
        Dict avec les clés suivantes :
            success              : bool
            triangle_total       : np.ndarray — triangle complet
            triangle_attritional : np.ndarray ou None — sinistres < LLT
            triangle_grands      : np.ndarray ou None — sinistres ≥ LLT
            grands_sinistres     : pd.DataFrame — liste des grands sinistres
            llt_utilise          : float ou None — LLT effectivement appliqué
            llt_suggere          : float ou None — LLT suggéré automatiquement
            statistiques         : dict — métriques portefeuille
            rapport              : dict — alertes et informations qualité
            mode_separation      : str — 'aucun' | 'attritional_grands'
            recommandation_grands: str — méthode recommandée pour grands sin.
            erreur               : str ou None
        """
        rapport = {'alertes': [], 'infos': []}

        try:
            # ── Étape 1 : Détecter si on a des données individuelles ──────────
            # La séparation LLT n'est possible que sur données individuelles
            # (triangle cumulé = données agrégées, impossible de séparer)
            est_donnees_individuelles = self._est_source_individuelle(
                source, mode_declare
            )

            if self.verbose:
                self.logger.info(
                    f"Source : {'données individuelles' if est_donnees_individuelles else 'triangle agrégé'}"
                )

            # ── Étape 2 : Construction du triangle total via TriangleValidator ─
            # On délègue la validation et construction de base au module existant
            rapport['infos'].append("Construction du triangle total...")
            C_total, C_engage, primes_norm, rapport_n1 = self._validator.charger(
                source         = source,
                mode_declare   = mode_declare,
                schema_mapping = schema_mapping,
                rapport        = rapport,
                nom_onglet     = nom_onglet,
            )
            rapport['alertes'].extend(rapport_n1.get('alertes', []))
            rapport['infos'].extend(rapport_n1.get('infos', []))

            # ── Étape 3 : Statistiques de base du triangle ────────────────────
            statistiques = self._calculer_statistiques_triangle(C_total, annee_debut)

            # ── Étape 4 : Séparation LLT (uniquement sur données individuelles) ─
            triangle_attritional = None
            triangle_grands      = None
            grands_sinistres_df  = pd.DataFrame()
            llt_suggere          = None
            llt_utilise          = None
            mode_separation      = 'aucun'
            recommandation_grands = 'non_applicable'

            if est_donnees_individuelles:
                # Charger le DataFrame source pour la séparation
                df_source = self._lire_source_df(source, schema_mapping)

                if df_source is not None and len(df_source) > 0:
                    # Calculer le LLT suggéré automatiquement
                    llt_suggere = self._calculer_llt_suggere(df_source)

                    if llt_suggere:
                        rapport['infos'].append(
                            f"LLT suggéré automatiquement (P{LLT_PERCENTILE_SUGGESTION*100:.0f}) : "
                            f"{llt_suggere:,.0f} €"
                        )

                    # Appliquer le LLT si fourni par l'utilisateur
                    if llt is not None and llt > 0:
                        llt_utilise = llt
                        (
                            triangle_attritional,
                            triangle_grands,
                            grands_sinistres_df,
                            stats_separation,
                        ) = self._separer_triangles(
                            df_source  = df_source,
                            llt        = llt,
                            C_total    = C_total,
                            rapport    = rapport,
                        )
                        statistiques.update(stats_separation)
                        mode_separation = 'attritional_grands'

                        # Recommandation méthode selon volume grands sinistres
                        n_grands = len(grands_sinistres_df)
                        recommandation_grands = self._recommander_methode_grands(
                            n_grands, rapport
                        )

                    else:
                        # LLT non fourni — signaler l'opportunité
                        if llt_suggere:
                            rapport['alertes'].append(
                                f"ℹ️ Aucun LLT fourni — séparation grands sinistres non effectuée. "
                                f"LLT suggéré : {llt_suggere:,.0f} € (P95 des montants). "
                                f"Fournissez llt= pour activer la séparation (Guide IA 2023 §3.2)."
                            )

            else:
                # Source = triangle agrégé — séparation LLT impossible
                if llt is not None:
                    rapport['alertes'].append(
                        "⚠️ LLT fourni mais source = triangle agrégé. "
                        "La séparation grands sinistres nécessite des données individuelles "
                        "(une ligne par sinistre). Le triangle total sera utilisé sans séparation."
                    )

            return {
                'success':               True,
                'triangle_total':        C_total,
                'triangle_attritional':  triangle_attritional,
                'triangle_grands':       triangle_grands,
                'grands_sinistres':      grands_sinistres_df,
                'llt_utilise':           llt_utilise,
                'llt_suggere':           llt_suggere,
                'statistiques':          statistiques,
                'rapport':               rapport,
                'mode_separation':       mode_separation,
                'recommandation_grands': recommandation_grands,
                'annee_debut':           annee_debut,
                'erreur':                None,
            }

        except Exception as e:
            self.logger.error(f"NVTriangleBuilder.construire() échoué : {e}", exc_info=True)
            return {
                'success':               False,
                'triangle_total':        None,
                'triangle_attritional':  None,
                'triangle_grands':       None,
                'grands_sinistres':      pd.DataFrame(),
                'llt_utilise':           None,
                'llt_suggere':           None,
                'statistiques':          {},
                'rapport':               rapport,
                'mode_separation':       'aucun',
                'recommandation_grands': 'non_applicable',
                'annee_debut':           annee_debut,
                'erreur':                str(e),
            }

    # =========================================================================
    #  MÉTHODES PRIVÉES — DÉTECTION ET LECTURE
    # =========================================================================

    def _est_source_individuelle(
        self,
        source       : Union[pd.DataFrame, np.ndarray, str],
        mode_declare : str,
    ) -> bool:
        """
        Détermine si la source contient des données individuelles (sinistres)
        ou un triangle déjà agrégé.

        Règles de détection :
          · ndarray             → toujours triangle agrégé
          · mode_declare='brutes' → toujours données individuelles
          · DataFrame avec colonne 'sinistre_id' → données individuelles
          · DataFrame avec plusieurs colonnes numériques → triangle agrégé
          · str (fichier)       → lecture partielle pour détection

        Parameters
        ----------
        source       : source de données
        mode_declare : mode forcé par l'utilisateur

        Returns
        -------
        bool : True si données individuelles, False si triangle agrégé
        """
        # Numpy array → toujours triangle
        if isinstance(source, np.ndarray):
            return False

        # Mode forcé par l'utilisateur
        if mode_declare == 'brutes':
            return True
        if mode_declare in ('cumule', 'non_cumule'):
            return False

        # DataFrame → analyser la structure
        if isinstance(source, pd.DataFrame):
            return self._analyser_structure_df(source)

        # Fichier → lire les premières lignes
        if isinstance(source, str):
            try:
                if source.endswith('.csv'):
                    df_sample = pd.read_csv(source, nrows=5)
                else:
                    df_sample = pd.read_excel(source, nrows=5)
                return self._analyser_structure_df(df_sample)
            except Exception:
                return False

        return False

    def _analyser_structure_df(self, df: pd.DataFrame) -> bool:
        """
        Analyse la structure d'un DataFrame pour détecter si c'est
        des données individuelles ou un triangle agrégé.

        Un DataFrame est considéré comme données individuelles si :
          · Il contient une colonne 'annee_survenance' (ou synonyme) ET
          · Il contient une colonne 'montant' (ou synonyme) ET
          · Il contient une colonne temporelle de paiement/développement

        Sinon c'est un triangle agrégé (lignes = années, colonnes = périodes).

        Parameters
        ----------
        df : pd.DataFrame à analyser

        Returns
        -------
        bool : True si données individuelles
        """
        cols_lower = [str(c).lower().strip() for c in df.columns]

        # Chercher les colonnes caractéristiques des données individuelles
        a_survenance = any(
            c in cols_lower
            for c in SYNONYMES_COLONNES['annee_survenance']
        )
        a_montant = any(
            c in cols_lower
            for c in SYNONYMES_COLONNES['montant']
        )
        a_paiement = any(
            c in cols_lower
            for syn_list in [
                SYNONYMES_COLONNES['annee_paiement'],
                SYNONYMES_COLONNES['annee_developpement'],
            ]
            for c in syn_list
        )

        # Données individuelles = colonnes métier claires
        if a_survenance and a_montant:
            return True

        # Si peu de colonnes numériques → probablement triangle
        n_numeric = df.select_dtypes(include=[np.number]).shape[1]
        if n_numeric > 3 and not a_survenance:
            return False

        return a_survenance and a_montant

    def _lire_source_df(
        self,
        source         : Union[pd.DataFrame, np.ndarray, str],
        schema_mapping : Optional[Dict],
    ) -> Optional[pd.DataFrame]:
        """
        Lit la source et retourne un DataFrame avec colonnes standardisées.
        Applique le schema_mapping si fourni, sinon détection automatique.

        Parameters
        ----------
        source         : source de données
        schema_mapping : mapping colonnes client → noms standard

        Returns
        -------
        pd.DataFrame avec colonnes standardisées, ou None si échec
        """
        try:
            # Lecture selon le type de source
            if isinstance(source, pd.DataFrame):
                df = source.copy()
            elif isinstance(source, str):
                if source.endswith('.csv'):
                    df = pd.read_csv(source)
                else:
                    df = pd.read_excel(source)
            else:
                # numpy array → pas de données individuelles
                return None

            # Normaliser les noms de colonnes
            df.columns = [str(c).lower().strip().replace(' ', '_') for c in df.columns]

            # Appliquer le schema_mapping si fourni
            if schema_mapping:
                df = df.rename(columns={
                    v.lower(): k for k, v in schema_mapping.items()
                })

            # Détection automatique des colonnes via synonymes
            for col_standard, synonymes in SYNONYMES_COLONNES.items():
                if col_standard not in df.columns:
                    for syn in synonymes:
                        if syn in df.columns:
                            df = df.rename(columns={syn: col_standard})
                            break

            return df

        except Exception as e:
            self.logger.warning(f"Lecture source DataFrame échouée : {e}")
            return None

    # =========================================================================
    #  MÉTHODES PRIVÉES — LLT ET SÉPARATION
    # =========================================================================

    def _calculer_llt_suggere(self, df: pd.DataFrame) -> Optional[float]:
        """
        Calcule automatiquement un Large Loss Threshold suggéré basé sur
        le percentile P95 des montants de sinistres.

        Référence : pratique marché française — FFA / FFSA recommandent
        un LLT entre P90 et P99 selon la branche.
        P95 est un compromis équilibré pour la détection automatique.

        Parameters
        ----------
        df : DataFrame avec colonne 'montant'

        Returns
        -------
        float : LLT suggéré, ou None si calcul impossible
        """
        if 'montant' not in df.columns:
            return None

        try:
            montants = pd.to_numeric(df['montant'], errors='coerce').dropna()
            montants_positifs = montants[montants > 0]

            if len(montants_positifs) < 10:
                # Pas assez de données pour un percentile fiable
                return None

            llt = float(montants_positifs.quantile(LLT_PERCENTILE_SUGGESTION))

            # Arrondir au millier le plus proche pour un seuil "propre"
            llt_arrondi = round(llt / 1000) * 1000

            return llt_arrondi if llt_arrondi > 0 else None

        except Exception as e:
            self.logger.warning(f"Calcul LLT suggéré échoué : {e}")
            return None

    def _separer_triangles(
        self,
        df_source : pd.DataFrame,
        llt       : float,
        C_total   : np.ndarray,
        rapport   : Dict,
    ) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, Dict]:
        """
        Sépare les données individuelles en deux triangles distincts :
          · Triangle attritional : sinistres dont le montant total < LLT
          · Triangle grands sinistres : sinistres dont le montant total ≥ LLT

        Méthode :
          1. Agréger les paiements par sinistre_id → montant total par sinistre
          2. Classifier chaque sinistre : attritional ou grand sinistre
          3. Reconstruire deux triangles séparément

        Note importante : cette méthode classe les sinistres sur leur montant
        TOTAL (somme de tous les paiements), pas sur le paiement individuel.
        Un sinistre qui dépasse le LLT sur l'ensemble de son développement
        est entièrement classé en "grand sinistre".

        Parameters
        ----------
        df_source : DataFrame avec données individuelles standardisées
        llt       : Large Loss Threshold en euros
        C_total   : triangle total déjà construit (pour référence dimensions)
        rapport   : dict pour logging des alertes

        Returns
        -------
        Tuple :
            triangle_attritional : np.ndarray
            triangle_grands      : np.ndarray
            grands_sinistres_df  : pd.DataFrame (liste des grands sinistres)
            stats_separation     : dict (statistiques de séparation)
        """
        try:
            df = df_source.copy()

            # Vérifier les colonnes nécessaires
            if 'montant' not in df.columns or 'annee_survenance' not in df.columns:
                rapport['alertes'].append(
                    "⚠️ Colonnes manquantes pour la séparation LLT — "
                    "triangle total utilisé sans séparation."
                )
                return C_total.copy(), np.zeros_like(C_total), pd.DataFrame(), {}

            df['montant'] = pd.to_numeric(df['montant'], errors='coerce').fillna(0)
            df['annee_survenance'] = pd.to_numeric(
                df['annee_survenance'], errors='coerce'
            ).dropna().astype(int)

            # ── Classification des sinistres ──────────────────────────────────
            # Agréger par sinistre pour obtenir le montant total
            if 'sinistre_id' in df.columns:
                # Montant total par sinistre (somme de tous les paiements)
                montant_par_sinistre = df.groupby('sinistre_id')['montant'].sum()
                grands_ids = set(
                    montant_par_sinistre[montant_par_sinistre >= llt].index
                )
                df['est_grand'] = df['sinistre_id'].isin(grands_ids)
            else:
                # Pas d'id sinistre → classification par ligne
                rapport['alertes'].append(
                    "⚠️ Colonne 'sinistre_id' absente — classification LLT "
                    "sur montant par ligne (moins précis que par sinistre total)."
                )
                df['est_grand'] = df['montant'] >= llt
                grands_ids = set()

            # ── Séparer les DataFrames ────────────────────────────────────────
            df_attritional = df[~df['est_grand']].copy()
            df_grands      = df[df['est_grand']].copy()

            n_attritional = len(df_attritional)
            n_grands      = len(df_grands)

            rapport['infos'].append(
                f"Séparation LLT = {llt:,.0f} € : "
                f"{n_attritional} paiements attritionnels, "
                f"{n_grands} paiements grands sinistres"
            )

            # ── Construire les deux triangles ─────────────────────────────────
            def _construire_triangle(df_sub: pd.DataFrame) -> np.ndarray:
                """Construit un triangle cumulé depuis un subset de données."""
                if len(df_sub) == 0:
                    return np.zeros_like(C_total)

                # Déterminer la colonne de développement
                col_dev = None
                for syn in SYNONYMES_COLONNES['annee_developpement']:
                    if syn in df_sub.columns:
                        col_dev = syn
                        break
                if col_dev is None:
                    for syn in SYNONYMES_COLONNES['annee_paiement']:
                        if syn in df_sub.columns:
                            # Calculer la période de développement
                            df_sub = df_sub.copy()
                            df_sub[syn] = pd.to_numeric(df_sub[syn], errors='coerce')
                            df_sub['_dev_'] = df_sub[syn] - df_sub['annee_survenance']
                            df_sub = df_sub[df_sub['_dev_'] >= 0]
                            col_dev = '_dev_'
                            break

                if col_dev is None:
                    return np.zeros_like(C_total)

                # Dimensions du triangle total (référence)
                n_ann, n_dev = C_total.shape
                annee_min = int(df_sub['annee_survenance'].min())

                # Agréger et pivoter
                pivot = df_sub.groupby(
                    ['annee_survenance', col_dev]
                )['montant'].sum().reset_index()

                C_inc = np.zeros((n_ann, n_dev))
                for _, row in pivot.iterrows():
                    i = int(row['annee_survenance']) - annee_min
                    j = int(row[col_dev])
                    if 0 <= i < n_ann and 0 <= j < n_dev:
                        C_inc[i, j] += float(row['montant'])

                # Cumuler
                return np.cumsum(C_inc, axis=1)

            triangle_attritional = _construire_triangle(df_attritional)
            triangle_grands      = _construire_triangle(df_grands)

            # ── DataFrame des grands sinistres ────────────────────────────────
            # Pour le traitement individuel et le rapport
            if 'sinistre_id' in df.columns:
                grands_sinistres_df = (
                    df[df['est_grand']]
                    .groupby(['sinistre_id', 'annee_survenance'])
                    .agg(
                        montant_total=('montant', 'sum'),
                        nb_paiements=('montant', 'count'),
                    )
                    .reset_index()
                    .sort_values('montant_total', ascending=False)
                )
            else:
                grands_sinistres_df = df[df['est_grand']][
                    ['annee_survenance', 'montant']
                ].copy()
                grands_sinistres_df.columns = ['annee_survenance', 'montant_total']

            # ── Statistiques de séparation ────────────────────────────────────
            montant_total_global = float(df['montant'].sum())
            montant_grands       = float(df_grands['montant'].sum())
            pct_grands           = (
                montant_grands / montant_total_global * 100
                if montant_total_global > 0 else 0
            )

            stats_separation = {
                'n_grands_sinistres':      len(grands_sinistres_df),
                'montant_grands_sinistres': round(montant_grands, 0),
                'pct_grands_sinistres':    round(pct_grands, 1),
                'llt_applique':            llt,
                'montant_moyen_grand':     round(
                    montant_grands / len(grands_sinistres_df), 0
                ) if len(grands_sinistres_df) > 0 else 0,
            }

            # Alertes qualité sur la séparation
            if pct_grands > 30:
                rapport['alertes'].append(
                    f"⚠️ Les grands sinistres représentent {pct_grands:.1f}% du total "
                    f"— LLT peut-être trop bas. Envisager un seuil plus élevé."
                )
            if pct_grands < 1:
                rapport['alertes'].append(
                    f"ℹ️ Les grands sinistres représentent seulement {pct_grands:.1f}% "
                    f"du total — LLT peut-être trop élevé ou peu de grands sinistres "
                    f"dans ce portefeuille."
                )

            return (
                triangle_attritional,
                triangle_grands,
                grands_sinistres_df,
                stats_separation,
            )

        except Exception as e:
            self.logger.error(f"Séparation LLT échouée : {e}", exc_info=True)
            rapport['alertes'].append(f"❌ Séparation LLT échouée : {e}")
            return C_total.copy(), np.zeros_like(C_total), pd.DataFrame(), {}

    # =========================================================================
    #  MÉTHODES PRIVÉES — STATISTIQUES ET RECOMMANDATIONS
    # =========================================================================

    def _calculer_statistiques_triangle(
        self,
        C           : np.ndarray,
        annee_debut : Optional[int],
    ) -> Dict:
        """
        Calcule les statistiques descriptives du triangle total.

        Ces statistiques sont affichées dans l'UI et le rapport pour
        donner à l'actuaire une vue rapide de la qualité des données.

        Parameters
        ----------
        C           : triangle cumulé (n×n)
        annee_debut : première année calendaire (pour les labels)

        Returns
        -------
        dict : statistiques du triangle
        """
        n, m = C.shape

        # Dernière diagonale (sinistres les plus récents observés)
        diagonale = np.array([
            float(C[i, n - 1 - i]) if (n - 1 - i) < m and C[i, n - 1 - i] > 0
            else 0.0
            for i in range(n)
        ])

        # Montant total de la diagonale (proxy réserve observée)
        total_diagonale = float(np.sum(diagonale))

        # Première colonne (sinistres à 12M ou 1ère période)
        premiere_col = float(np.sum(C[:, 0]))

        # Ratio de développement global (dernière diagonale / première colonne)
        ratio_dev = total_diagonale / premiere_col if premiere_col > 0 else 0

        # Cellules non nulles dans le triangle
        n_cellules_total = n * m
        n_cellules_remplies = int(np.sum(C > 0))
        pct_remplissage = n_cellules_remplies / n_cellules_total * 100

        # Années de survenance
        if annee_debut:
            annees = [annee_debut + i for i in range(n)]
            label_periode = f"{annee_debut}–{annee_debut + n - 1}"
        else:
            annees = list(range(n))
            label_periode = f"An.0–An.{n-1}"

        return {
            'dimensions':        f"{n}×{m}",
            'n_annees':          n,
            'n_periodes':        m,
            'total_diagonale':   round(total_diagonale, 0),
            'ratio_developpement': round(ratio_dev, 3),
            'pct_remplissage':   round(pct_remplissage, 1),
            'annees':            annees,
            'label_periode':     label_periode,
        }

    def _recommander_methode_grands(
        self,
        n_grands : int,
        rapport  : Dict,
    ) -> str:
        """
        Recommande la méthode de traitement des grands sinistres selon
        leur volume, conformément aux bonnes pratiques actuarielles.

        Référence : Guide IA 2023 §3.2 + pratique marché.

        Seuils :
          · ≥ 50  : Chain Ladder sur triangle séparé (volume statistique suffisant)
          · 20-49 : Bornhuetter-Ferguson avec LR marché externe
          · < 20  : Développement individuel dossier par dossier

        Parameters
        ----------
        n_grands : nombre de grands sinistres identifiés
        rapport  : dict pour logging

        Returns
        -------
        str : code méthode recommandée
        """
        if n_grands >= 50:
            methode = 'chain_ladder_separe'
            msg = (
                f"✅ {n_grands} grands sinistres — volume suffisant pour "
                f"Chain Ladder sur triangle séparé."
            )
        elif n_grands >= SEUIL_MIN_GRANDS_SINISTRES_STATISTIQUE:
            methode = 'bornhuetter_ferguson_marche'
            msg = (
                f"ℹ️ {n_grands} grands sinistres — Bornhuetter-Ferguson "
                f"avec LR marché externe recommandé (volume insuffisant pour CL)."
            )
        else:
            methode = 'developpement_individuel'
            msg = (
                f"⚠️ {n_grands} grands sinistre(s) — développement individuel "
                f"dossier par dossier recommandé. "
                f"Saisie manuelle des ultimates estimés par l'actuaire désigné."
            )

        rapport['infos'].append(msg)
        return methode


# =============================================================================
#  EXTENSION — GESTION MULTI-ONGLETS ET TRIANGLE DES CHARGES ENGAGÉES
# =============================================================================

    def detecter_onglets(
        self,
        chemin_fichier : str,
    ) -> Dict:
        """
        Détecte les onglets d'un fichier Excel et retourne leurs noms
        et un aperçu de leur structure pour aider l'utilisateur à les mapper.

        Utilisé dans l'UI pour proposer à l'utilisateur de choisir quel
        onglet correspond aux paiements, aux charges, aux primes, etc.

        Parameters
        ----------
        chemin_fichier : str
            Chemin vers le fichier Excel (.xlsx, .xls)

        Returns
        -------
        Dict avec :
            success  : bool
            onglets  : list[dict] — nom, nb_lignes, nb_colonnes, apercu_colonnes
            erreur   : str ou None
        """
        try:
            # Lire la liste des onglets sans charger tout le fichier
            xl = pd.ExcelFile(chemin_fichier)
            onglets = []

            for nom_onglet in xl.sheet_names:
                # Lecture unique via xl.parse — plus performant que deux read_excel
                df_full   = xl.parse(nom_onglet)
                df_sample = df_full.head(3)
                type_probable = self._deviner_type_onglet(df_sample, nom_onglet)

                onglets.append({
                    'nom':           nom_onglet,
                    'nb_lignes':     len(df_full),
                    'nb_colonnes':   len(df_full.columns),
                    'colonnes':      list(df_full.columns[:5]),
                    'type_probable': type_probable,
                })

            self.logger.info(f"{len(onglets)} onglet(s) détecté(s) : {[o['nom'] for o in onglets]}")

            return {
                'success':  True,
                'onglets':  onglets,
                'erreur':   None,
            }

        except Exception as e:
            self.logger.error(f"Détection onglets échouée : {e}")
            return {
                'success':  False,
                'onglets':  [],
                'erreur':   str(e),
            }

    def _deviner_type_onglet(self, df_sample: pd.DataFrame, nom: str) -> str:
        """
        Devine le type probable d'un onglet Excel en analysant son nom
        et la structure de ses premières lignes.

        Heuristiques utilisées :
          · Nom contient "paiement", "paid", "pay" → paiements
          · Nom contient "charge", "incurred", "engage" → charges engagées
          · Nom contient "prime", "premium" → primes acquises
          · Structure numérique carrée → triangle agrégé
          · Colonnes métier (annee_survenance, montant) → données individuelles

        Parameters
        ----------
        df_sample : premières lignes du DataFrame
        nom       : nom de l'onglet

        Returns
        -------
        str : type probable ('paiements' | 'charges' | 'primes' | 'sinistres' | 'inconnu')
        """
        nom_lower = nom.lower()

        # Détection par nom d'onglet
        if any(k in nom_lower for k in ['paiement', 'paid', 'pay', 'reglement', 'payment']):
            return 'paiements'
        if any(k in nom_lower for k in ['charge', 'incurred', 'engage', 'provision', 'encours']):
            return 'charges'
        if any(k in nom_lower for k in ['prime', 'premium', 'primes', 'acquired']):
            return 'primes'
        if any(k in nom_lower for k in ['sinistre', 'claim', 'individuel', 'detail']):
            return 'sinistres'

        # Détection par structure
        cols_lower = [str(c).lower() for c in df_sample.columns]
        n_numeric  = df_sample.select_dtypes(include=[np.number]).shape[1]

        if any(c in cols_lower for c in ['annee_survenance', 'ay', 'accident_year']):
            if n_numeric >= 2:
                return 'sinistres'
        if n_numeric >= 5 and len(df_sample.columns) >= 5:
            return 'triangle_agregé'

        return 'inconnu'

    def construire_triangle_engage(
        self,
        source_charges  : Union[pd.DataFrame, np.ndarray, str],
        C_paiements     : np.ndarray,
        schema_mapping  : Optional[Dict] = None,
        mode_declare    : str            = 'auto',
        nom_onglet      : Optional[str]  = None,
    ) -> Dict:
        """
        Construit le triangle des charges engagées pour Munich Chain Ladder.

        Accepte 3 formats pour les charges :
          1. Triangle cumulé agrégé (matrice n×m)
          2. Triangle incrémental (à cumuler)
          3. Données individuelles dossier par dossier
             → une ligne par dossier avec évaluation courante
             → Charge[i,j] = Σ paiements jusqu'à j + Σ évaluations dossiers ouverts

        Le triangle des charges doit être fourni par le client depuis son
        système de gestion (évaluations dossier par dossier indépendantes).
        Il NE DOIT PAS être calculé depuis les provisions IBNR actuarielles
        car cela introduirait une circularité dans Munich CL.
        Référence : Quarg & Mack (2004) — Munich Chain Ladder.

        Parameters
        ----------
        source_charges : source des données de charges
        C_paiements    : triangle des paiements déjà construit (np.ndarray)
                         Utilisé comme référence pour les dimensions et
                         pour le cas 3 (données individuelles)
        schema_mapping : mapping colonnes client → noms standard
        mode_declare   : 'auto' | 'cumule' | 'non_cumule' | 'individuel'
        nom_onglet     : nom de l'onglet si fichier multi-onglets

        Returns
        -------
        Dict avec :
            success          : bool
            triangle_engage  : np.ndarray — triangle charges engagées (n×m)
            format_detecte   : str — format utilisé
            rapport          : dict — alertes et informations
            erreur           : str ou None
        """
        rapport = {'alertes': [], 'infos': []}

        try:
            n_ref, m_ref = C_paiements.shape

            # ── Lire la source selon le type ──────────────────────────────────
            if isinstance(source_charges, np.ndarray):
                # Numpy array → triangle déjà construit
                C_engage = self._normaliser_dimensions(
                    source_charges, n_ref, m_ref, rapport
                )
                format_detecte = 'triangle_numpy'

            elif isinstance(source_charges, (str, pd.DataFrame)):
                # Lire le DataFrame
                if isinstance(source_charges, str):
                    if nom_onglet:
                        # Fichier multi-onglets
                        df_charges = pd.read_excel(
                            source_charges,
                            sheet_name=nom_onglet,
                        )
                        rapport['infos'].append(
                            f"Onglet '{nom_onglet}' chargé pour les charges engagées."
                        )
                    elif source_charges.endswith('.csv'):
                        df_charges = pd.read_csv(source_charges)
                    else:
                        df_charges = pd.read_excel(source_charges)
                else:
                    df_charges = source_charges.copy()

                # Normaliser les colonnes
                df_charges.columns = [
                    str(c).lower().strip().replace(' ', '_')
                    for c in df_charges.columns
                ]
                if schema_mapping:
                    df_charges = df_charges.rename(columns={
                        v.lower(): k for k, v in schema_mapping.items()
                    })

                # Détecter le format
                est_individuel = self._est_source_individuelle(
                    df_charges, mode_declare
                )

                if est_individuel or mode_declare == 'individuel':
                    # ── Format 3 : données individuelles dossier par dossier ──
                    # Charge[i,j] = paiements cumulés + évaluations dossiers ouverts
                    C_engage = self._construire_engage_depuis_individuels(
                        df_charges  = df_charges,
                        C_paiements = C_paiements,
                        rapport     = rapport,
                    )
                    format_detecte = 'donnees_individuelles'
                    rapport['infos'].append(
                        "Triangle des charges construit depuis évaluations individuelles "
                        "(paiements cumulés + provisions dossier par dossier)."
                    )
                else:
                    # ── Format 1 ou 2 : triangle agrégé ──────────────────────
                    # Déléguer au TriangleValidator existant
                    C_raw, _, _, rapport_val = self._validator.charger(
                        source       = df_charges,
                        mode_declare = mode_declare,
                        rapport      = rapport,
                    )
                    rapport['alertes'].extend(rapport_val.get('alertes', []))
                    C_engage = self._normaliser_dimensions(C_raw, n_ref, m_ref, rapport)
                    format_detecte = 'triangle_agrege'

            else:
                raise ValueError(f"Type de source non supporté : {type(source_charges)}")

            # ── Validation cohérence paiements / charges ──────────────────────
            # Les charges engagées doivent être ≥ paiements cumulés
            # (on ne peut pas avoir payé plus qu'on n'a engagé)
            n_incoherences = int(np.sum(
                (C_engage > 0) & (C_paiements > 0) & (C_engage < C_paiements)
            ))
            if n_incoherences > 0:
                rapport['alertes'].append(
                    f"⚠️ {n_incoherences} cellule(s) où charges < paiements — "
                    f"incohérence dans le triangle des charges engagées. "
                    f"Vérifier la source des données."
                )

            rapport['infos'].append(
                f"Triangle engagé construit ({C_engage.shape[0]}×{C_engage.shape[1]}) "
                f"— format : {format_detecte}"
            )

            return {
                'success':         True,
                'triangle_engage': C_engage,
                'format_detecte':  format_detecte,
                'rapport':         rapport,
                'erreur':          None,
            }

        except Exception as e:
            self.logger.error(f"construire_triangle_engage() échoué : {e}", exc_info=True)
            return {
                'success':         False,
                'triangle_engage': None,
                'format_detecte':  'erreur',
                'rapport':         rapport,
                'erreur':          str(e),
            }

    def _construire_engage_depuis_individuels(
        self,
        df_charges  : pd.DataFrame,
        C_paiements : np.ndarray,
        rapport     : Dict,
    ) -> np.ndarray:
        """
        Construit le triangle des charges engagées depuis des données
        individuelles dossier par dossier.

        Formule appliquée pour chaque cellule (i=année survenance, j=période) :
          · Si j < dernière période connue de l'année i :
            C_engage[i,j] = C_paiements[i,j]  (déjà entièrement développé)
          · Si j = dernière période connue (diagonale) :
            C_engage[i,j] = C_paiements[i,j] + Σ(évaluations dossiers ouverts de l'année i)

        Cette approche garantit que les charges engagées sont égales aux
        paiements sur les périodes passées et incluent les provisions
        des dossiers encore ouverts sur la diagonale.

        Parameters
        ----------
        df_charges  : DataFrame avec colonnes (annee_survenance, evaluation_courante)
                      et optionnellement (sinistre_id, statut)
        C_paiements : triangle des paiements cumulés (référence dimensions)
        rapport     : dict pour logging

        Returns
        -------
        np.ndarray : triangle des charges engagées (mêmes dimensions que C_paiements)
        """
        n, m = C_paiements.shape

        # Chercher les colonnes nécessaires
        col_surv = None
        col_eval = None
        cols = list(df_charges.columns)

        for c in cols:
            if c in SYNONYMES_COLONNES['annee_survenance']:
                col_surv = c
            if c in ['evaluation_courante', 'evaluation', 'reserve', 'provision',
                     'case_reserve', 'outstanding', 'encours', 'provision_dossier',
                     'montant_reserve', 'charge_courante']:
                col_eval = c
            # Fallback sur 'montant' si pas de colonne évaluation
            if col_eval is None and c in SYNONYMES_COLONNES['montant']:
                col_eval = c

        if col_surv is None or col_eval is None:
            rapport['alertes'].append(
                "⚠️ Colonnes 'annee_survenance' et/ou 'evaluation_courante' "
                "non trouvées dans les données de charges individuelles. "
                f"Colonnes disponibles : {cols}"
            )
            return C_paiements.copy()

        # Agréger les évaluations par année de survenance
        df_charges[col_surv] = pd.to_numeric(df_charges[col_surv], errors='coerce')
        df_charges[col_eval] = pd.to_numeric(df_charges[col_eval], errors='coerce').fillna(0)

        eval_par_annee = df_charges.groupby(col_surv)[col_eval].sum().to_dict()

        annee_min = int(df_charges[col_surv].min())

        # Construire le triangle des charges
        # Base = triangle des paiements (copie)
        C_engage = C_paiements.copy()

        for i in range(n):
            annee_i = annee_min + i
            provision_i = float(eval_par_annee.get(annee_i, 0.0))

            if provision_i <= 0:
                continue

            # Trouver la dernière colonne non nulle de cette ligne (diagonale)
            last_j = -1
            for j in range(m - 1, -1, -1):
                if C_paiements[i, j] > 0:
                    last_j = j
                    break

            if last_j >= 0:
                # Ajouter la provision à la dernière valeur connue
                C_engage[i, last_j] = C_paiements[i, last_j] + provision_i

        rapport['infos'].append(
            f"Provisions individuelles intégrées pour "
            f"{len(eval_par_annee)} année(s) de survenance."
        )

        return C_engage

    def _normaliser_dimensions(
        self,
        C       : np.ndarray,
        n_ref   : int,
        m_ref   : int,
        rapport : Dict,
    ) -> np.ndarray:
        """
        Normalise les dimensions d'un triangle pour qu'il corresponde
        aux dimensions du triangle de référence (paiements).

        Si le triangle fourni est plus petit → compléter avec des zéros.
        Si le triangle fourni est plus grand → tronquer.

        Cette normalisation est nécessaire pour que Munich CL puisse
        comparer cellule par cellule les deux triangles.

        Parameters
        ----------
        C     : triangle à normaliser
        n_ref : nombre de lignes de référence (années de survenance)
        m_ref : nombre de colonnes de référence (périodes de développement)
        rapport : dict pour logging

        Returns
        -------
        np.ndarray : triangle normalisé (n_ref × m_ref)
        """
        n, m = C.shape

        if n == n_ref and m == m_ref:
            return C  # Dimensions identiques — rien à faire

        # Créer un tableau aux bonnes dimensions
        C_norm = np.zeros((n_ref, m_ref))

        # Copier les données disponibles
        n_copy = min(n, n_ref)
        m_copy = min(m, m_ref)
        C_norm[:n_copy, :m_copy] = C[:n_copy, :m_copy]

        if n != n_ref or m != m_ref:
            rapport['alertes'].append(
                f"⚠️ Triangle des charges ({n}×{m}) redimensionné vers "
                f"({n_ref}×{m_ref}) pour correspondre au triangle des paiements."
            )

        return C_norm
