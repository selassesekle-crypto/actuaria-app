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
from typing import Dict, Optional, Tuple, Union

import numpy as np
import pandas as pd

# Réutilisation du validateur existant (migration progressive)
from direction_non_vie.services.nv_triangle_validator import TriangleValidator
# Construction des triangles : SOURCE UNIQUE (module 4 du Bloc II). Le builder
# ne pivote ni ne cumule plus lui-même — cf. _separer_triangles.
from direction_non_vie.services.nv_triangle_construction import construire_depuis_long

logger = logging.getLogger('actuaria.direction_non_vie.services.triangle_builder')

# Import diagnostics qualite triangle
try:
    from direction_non_vie.services.nv_triangle_diagnostics import diagnostiquer_triangle as _diagnostiquer
    DIAGNOSTICS_OK = True
except ImportError:
    try:
        from nv_triangle_diagnostics import diagnostiquer_triangle as _diagnostiquer
        DIAGNOSTICS_OK = True
    except ImportError:
        DIAGNOSTICS_OK = False
        def _diagnostiquer(*a, **kw): return {}


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
                mode           = mode_declare,
                schema_mapping = schema_mapping,
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

            # Diagnostic qualite du triangle
            _diag_qualite = {}
            if DIAGNOSTICS_OK and C_total is not None:
                try:
                    _diag_qualite = _diagnostiquer(
                        C_total,
                        annee_debut=annee_debut,
                        lob='generique',  # lob affiné par A7 si nécessaire
                    )
                    for _c in _diag_qualite.get('controles', []):
                        if _c.get('statut') == 'ROUGE':
                            rapport['alertes'].append(
                                f"⚠️ Qualite triangle [{_c['code']}] : {_c['message'][:120]}"
                            )
                except Exception as _ed:
                    self.logger.warning(f'Diagnostic triangle echec : {_ed}')
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
                'diagnostic_qualite':    _diag_qualite,
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
        # La présence d'un axe temporel (paiement / développement) n'entre PAS
        # dans la décision : elle était calculée puis ignorée. Ce qui tranche,
        # c'est survenance + montant — un axe manquant est traité plus loin, à
        # la construction, où l'on sait dire lequel manque.

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
            # DÉLÉGUÉ au module 4 (source unique) avec le REPÈRE D'ANNÉES de la
            # source COMPLÈTE imposé aux deux sous-ensembles.
            #
            # ⚠️ CORRECTION D'UN DÉFAUT DE PRODUCTION. La construction faite ici
            # à la main redérivait `annee_min` du SOUS-ENSEMBLE, si bien que les
            # lignes étaient DÉCALÉES : un grand sinistre survenu en 2021 dans un
            # portefeuille commençant en 2019 atterrissait ligne 0 au lieu de 2.
            # Mesuré : le triangle des grands plaçait TOUJOURS ses sinistres
            # ligne 0, quelle que soit l'année. Conséquence directe —
            # `attritionnel + grands != total`, et la réserve grands sinistres
            # calculée par l'app (≥ 20 grands → A7 sur ce triangle) portait sur
            # des années fausses. Le repère imposé est exactement ce que
            # `construire_depuis_long` documente comme garantissant
            # `C_attritionnel + C_grands = C_total`.
            n_ann, n_dev = C_total.shape
            repere = (int(df['annee_survenance'].min()), n_ann, n_dev)
            triangle_attritional, _ = construire_depuis_long(
                df_attritional, 'montant', rapport, repere)
            triangle_grands, _ = construire_depuis_long(
                df_grands, 'montant', rapport, repere)

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
