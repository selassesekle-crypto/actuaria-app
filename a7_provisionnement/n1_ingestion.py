# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n1_ingestion.py  —  Niveau 1 : Ingestion & Validation du triangle
# =============================================================================
#
#  Nouveautés v5.0 vs v4.0 :
#    · Contrôle qualité données brutes (doublons, incohérences temporelles,
#      outliers IQR, montants aberrants, années hors plage)
#    · schema_mapping explicite prioritaire sur synonymes internes
#    · Journalisation détaillée dans rapport['infos']
#
# =============================================================================

import re
import logging
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger('actuaria.a7')


class TriangleValidator:
    """
    Reçoit n'importe quelle donnée et retourne un triangle numpy valide
    avec son rapport de qualité complet.

    Entrées acceptées
    -----------------
    - numpy array  (carré ou rectangulaire, cumulé ou non)
    - pandas DataFrame
    - fichier CSV / Excel (chemin str ou Path)
    - objet fichier upload Streamlit
    - dict résultat A2 (clé 'dataframe', 'df' ou 'data')
    - liste de listes

    Sorties garanties
    -----------------
    C        : np.ndarray  (n_années × n_développements), cumulé, sans NaN
    C_engage : np.ndarray ou None   — triangle engagé pour Munich CL
    primes   : np.ndarray ou None   — vecteur primes par année
    rapport  : dict complet qualité + metadata
    """

    # ── Synonymes de colonnes pour sinistres bruts ────────────────────────────
    SYNONYMES: Dict[str, List[str]] = {
        'annee_survenance':    ['id_year', 'year', 'annee', 'loss_year', 'acc_year',
                                'underwriting_year', 'ay', 'accident_year'],
        'annee_paiement':      ['payment_year', 'annee_reglement', 'dev_year',
                                'development_year', 'py', 'dy'],
        'annee_developpement': ['dev', 'developpement', 'lag', 'retard', 'development'],
        'montant':             ['cout_total_sinistres', 'claim_amount', 'charge',
                                'cout_sinistre', 'paid', 'incurred', 'cumulative',
                                'amount'],
        'id_sinistre':         ['claim_id', 'sinistre_id', 'id', 'claimid',
                                'numero_sinistre', 'sin_id'],
        'nb_sinistres':        ['claim_nb', 'claimnb', 'nb_claims',
                                'claim_count', 'freq'],
    }

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # =========================================================================
    #  POINT D'ENTRÉE UNIQUE
    # =========================================================================

    def charger(
        self,
        source,
        mode:                          str  = 'auto',
        triangle_engage                     = None,
        primes                              = None,
        schema_mapping: Optional[Dict[str, str]] = None,
    ) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], Dict]:
        """
        Point d'entrée universel.

        Parameters
        ----------
        source : any
            Données source (tous formats acceptés).
        mode : str
            'auto' | 'cumule' | 'non_cumule' | 'brutes'
        triangle_engage : any, optional
            Triangle des engagements pour Munich CL.
        primes : array-like, optional
            Vecteur des primes acquises par année de survenance.
        schema_mapping : dict, optional
            Mapping explicite {nom_standard: nom_dans_fichier}.
            Exemple : {'montant': 'cout_total', 'annee_survenance': 'ay'}
            Prioritaire sur la détection automatique par synonymes.

        Returns
        -------
        C : np.ndarray
        C_engage : np.ndarray or None
        primes : np.ndarray or None
        rapport : dict
        """
        rapport: Dict[str, Any] = {
            'alertes':      [],
            'infos':        [],
            'statut':       'VERT',
            'taille':       None,
            'mode_detecte': mode,
            'n_annees':     None,
            'n_dev':        None,
        }

        try:
            # Étape 1 : lire la source
            raw = self._lire_source(source, rapport)

            # Étape 1b : appliquer schema_mapping si fourni
            if schema_mapping and isinstance(raw, pd.DataFrame):
                raw = self._appliquer_schema_mapping(raw, schema_mapping, rapport)

            # Étape 2 : détecter le mode
            mode_final = self._detecter_mode(raw, mode, rapport)

            # Étape 3 : construire le triangle
            if mode_final == 'brutes':
                if isinstance(raw, pd.DataFrame):
                    raw = self._controler_qualite_brutes(raw, rapport)
                C = self._construire_depuis_brutes(raw, rapport)
            else:
                C = self._construire_depuis_triangle(raw, mode_final, rapport)

            # Étape 4 : valider et nettoyer
            C = self._valider_et_nettoyer(C, rapport)

            # Étape 5 : triangle engagé
            C_eng = None
            if triangle_engage is not None:
                try:
                    _rp_eng = {'alertes': [], 'infos': []}
                    raw_eng = self._lire_source(triangle_engage, _rp_eng)
                    C_eng   = self._construire_depuis_triangle(raw_eng, 'cumule', _rp_eng)
                    C_eng   = self._valider_et_nettoyer(C_eng, _rp_eng)
                    if C_eng.shape[0] != C.shape[0]:
                        rapport['alertes'].append(
                            "⚠️ Triangle engagé de taille différente — Munich CL désactivé"
                        )
                        C_eng = None
                    else:
                        rapport['infos'].append(
                            f"✅ Triangle engagé chargé ({C_eng.shape[0]}×{C_eng.shape[1]})"
                        )
                except Exception as e:
                    rapport['alertes'].append(f"⚠️ Triangle engagé non chargé : {e}")

            # Étape 6 : primes
            primes_out = self._normaliser_primes(primes, C.shape[0], rapport)

            # Résumé
            n, m = C.shape
            rapport.update({
                'taille':       f"{n}×{m}",
                'n_annees':     n,
                'n_dev':        m,
                'mode_detecte': mode_final,
            })
            rapport['infos'].append(f"✅ Triangle {n}×{m} prêt ({mode_final})")

            # Statut final
            n_rouge = sum(1 for a in rapport['alertes'] if '❌' in a)
            if n_rouge > 0:
                rapport['statut'] = 'ROUGE'
            elif rapport['alertes']:
                rapport['statut'] = 'AMBRE'
            else:
                rapport['statut'] = 'VERT'

            if self.verbose:
                logger.info(
                    f"Triangle {n}×{m} chargé | mode={mode_final} | "
                    f"statut={rapport['statut']} | "
                    f"{len(rapport['alertes'])} alerte(s)"
                )

            return C, C_eng, primes_out, rapport

        except Exception as e:
            rapport['statut'] = 'ROUGE'
            rapport['alertes'].append(f"❌ Erreur chargement : {str(e)}")
            logger.error(f"Erreur chargement triangle : {e}", exc_info=True)
            raise ValueError(f"Impossible de charger le triangle : {e}") from e

    # =========================================================================
    #  ÉTAPE 1 : LIRE LA SOURCE
    # =========================================================================

    def _lire_source(self, source, rapport: Dict) -> Union[np.ndarray, pd.DataFrame]:
        """Convertit n'importe quelle source en DataFrame ou ndarray."""

        if isinstance(source, np.ndarray):
            return source.astype(float)

        if isinstance(source, list):
            return np.array(source, dtype=float)

        if isinstance(source, pd.DataFrame):
            return source

        if isinstance(source, dict):
            for key in ('dataframe', 'df', 'data'):
                if key in source:
                    return source[key]
            raise ValueError(
                "Dict fourni mais clé 'dataframe', 'df' ou 'data' introuvable. "
                "Vérifiez le format du résultat A2."
            )

        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"Fichier introuvable : {path}")
            if path.suffix.lower() in ('.xlsx', '.xls', '.xlsm'):
                return pd.read_excel(path)
            if path.suffix.lower() in ('.csv', '.txt'):
                for sep in (',', ';', '\t', '|'):
                    try:
                        df = pd.read_csv(path, sep=sep)
                        if df.shape[1] > 1:
                            return df
                    except Exception:
                        continue
                return pd.read_csv(path)
            raise ValueError(f"Format de fichier non supporté : {path.suffix}")

        # Objet fichier (upload Streamlit)
        try:
            name = getattr(source, 'name', '')
            if name.lower().endswith(('.xlsx', '.xls')):
                return pd.read_excel(source)
            source.seek(0)
            return pd.read_csv(source)
        except Exception as e:
            raise ValueError(f"Impossible de lire la source : {type(source)} — {e}")

    # =========================================================================
    #  ÉTAPE 1b : SCHEMA_MAPPING EXPLICITE
    # =========================================================================

    def _appliquer_schema_mapping(
        self, df: pd.DataFrame, mapping: Dict[str, str], rapport: Dict
    ) -> pd.DataFrame:
        """
        Renomme les colonnes selon le mapping explicite fourni.
        Prioritaire sur la détection automatique par synonymes.

        Parameters
        ----------
        mapping : {nom_standard: nom_dans_fichier}
        """
        rename = {}
        for std_name, file_name in mapping.items():
            if file_name in df.columns:
                rename[file_name] = std_name
                rapport['infos'].append(
                    f"schema_mapping : '{file_name}' → '{std_name}'"
                )
            else:
                rapport['alertes'].append(
                    f"⚠️ schema_mapping : colonne '{file_name}' introuvable "
                    f"— colonnes disponibles : {list(df.columns)}"
                )
        if rename:
            df = df.rename(columns=rename)
        return df

    # =========================================================================
    #  ÉTAPE 1c : CONTRÔLE QUALITÉ DONNÉES BRUTES
    # =========================================================================

    def _controler_qualite_brutes(
        self, df: pd.DataFrame, rapport: Dict
    ) -> pd.DataFrame:
        """
        Contrôle qualité complet sur les sinistres bruts.

        Vérifie (sans corriger silencieusement) :
        1. Doublons exacts sur (id_sinistre, annee_survenance, annee_paiement)
        2. Incohérences temporelles : annee_paiement < annee_survenance
        3. Montants outliers extrêmes : > Q3 + 3×IQR
        4. Montants nuls ou négatifs
        5. Années de survenance hors plage [1980, année courante]

        L'actuaire décide de l'action corrective — l'agent signale et documente.
        """
        from datetime import datetime
        annee_courante = datetime.now().year
        df = df.copy()

        col_id   = self._trouver_colonne(df, 'id_sinistre',       {})
        col_surv = self._trouver_colonne(df, 'annee_survenance',   {})
        col_paie = self._trouver_colonne(df, 'annee_paiement',     {})
        col_mont = self._trouver_colonne(df, 'montant',            {})

        # 1. Doublons
        cles = [c for c in [col_id, col_surv, col_paie] if c is not None]
        if len(cles) >= 2:
            n_dup = df.duplicated(subset=cles).sum()
            if n_dup > 0:
                rapport['alertes'].append(
                    f"⚠️ {n_dup} ligne(s) dupliquée(s) sur "
                    f"({', '.join(cles)}) — vérifier la source."
                )

        # 2. Incohérences temporelles
        if col_surv and col_paie:
            s = pd.to_numeric(df[col_surv], errors='coerce')
            p = pd.to_numeric(df[col_paie], errors='coerce')
            n_incoh = (p < s).sum()
            if n_incoh > 0:
                rapport['alertes'].append(
                    f"❌ {n_incoh} sinistre(s) avec annee_paiement < "
                    f"annee_survenance — incohérence temporelle grave."
                )

        # 3. Outliers extrêmes (IQR)
        if col_mont:
            montants = pd.to_numeric(df[col_mont], errors='coerce').dropna()
            pos = montants[montants > 0]
            if len(pos) >= 10:
                q1, q3 = pos.quantile(0.25), pos.quantile(0.75)
                iqr    = q3 - q1
                seuil  = q3 + 3 * iqr
                n_out  = (pos > seuil).sum()
                if n_out > 0:
                    rapport['alertes'].append(
                        f"⚠️ {n_out} sinistre(s) outlier(s) extrême(s) "
                        f"(montant > Q3+3×IQR = {seuil:,.0f} €, soit "
                        f"{n_out/len(pos)*100:.1f}% du portefeuille). "
                        f"Envisager un Large Loss Threshold."
                    )
                rapport['infos'].append(
                    f"Montants : Q1={q1:,.0f}€  Q3={q3:,.0f}€  "
                    f"seuil outlier={seuil:,.0f}€"
                )

            # 4. Nuls et négatifs
            n_nuls = (montants == 0).sum()
            n_negs = (montants < 0).sum()
            if n_nuls > 0:
                rapport['alertes'].append(
                    f"⚠️ {n_nuls} montant(s) nul(s) — "
                    f"sinistres sans coût ou erreurs de saisie."
                )
            if n_negs > 0:
                rapport['alertes'].append(
                    f"⚠️ {n_negs} montant(s) négatif(s) — "
                    f"recours/remboursements identifiés, convertis en valeur absolue."
                )

        # 5. Années hors plage
        if col_surv:
            annees = pd.to_numeric(df[col_surv], errors='coerce').dropna()
            n_hors = ((annees < 1980) | (annees > annee_courante)).sum()
            if n_hors > 0:
                rapport['alertes'].append(
                    f"⚠️ {n_hors} année(s) de survenance hors plage "
                    f"[1980, {annee_courante}] — à vérifier."
                )

        rapport['infos'].append(
            f"Contrôle qualité données brutes : {len(df)} lignes analysées"
        )
        return df

    # =========================================================================
    #  ÉTAPE 2 : DÉTECTER LE MODE
    # =========================================================================

    def _detecter_mode(
        self,
        raw:    Union[np.ndarray, pd.DataFrame],
        mode:   str,
        rapport: Dict
    ) -> str:
        """Détecte automatiquement si les données sont brutes ou un triangle."""

        if mode != 'auto':
            return mode

        if isinstance(raw, np.ndarray):
            detected = 'cumule' if self._est_cumule(raw) else 'non_cumule'
            rapport['infos'].append(f"Format détecté : triangle numpy → {detected}")
            return detected

        if isinstance(raw, pd.DataFrame):
            cols = [str(c).lower() for c in raw.columns]
            has_surv  = any(s in cols for s in
                            self.SYNONYMES['annee_survenance'] + ['annee_survenance'])
            has_mont  = any(s in cols for s in
                            self.SYNONYMES['montant'] + ['montant'])

            if has_surv and has_mont:
                rapport['infos'].append(
                    "Format détecté : sinistres bruts (une ligne par sinistre)"
                )
                return 'brutes'

            rapport['infos'].append(
                "Format détecté : triangle en tableau "
                "(lignes = années, colonnes = développements)"
            )
            num = raw.select_dtypes(include=[np.number])
            if num.shape[0] >= 2 and num.shape[1] >= 2:
                for i in range(min(3, num.shape[0])):
                    row = num.iloc[i].dropna().values
                    if len(row) >= 2 and all(row > 0):
                        detected = (
                            'cumule' if self._est_cumule(row.reshape(1, -1))
                            else 'non_cumule'
                        )
                        rapport['infos'].append(f"Cumulativité détectée : {detected}")
                        return detected
            return 'cumule'

        return 'cumule'

    def _est_cumule(self, arr: np.ndarray) -> bool:
        """
        Teste si un triangle est cumulé.
        Critère : au moins 70% des lignes sont croissantes (tolérance 1%).
        """
        if arr.ndim == 1:
            vals = arr[arr > 0]
            return len(vals) < 2 or bool(np.all(np.diff(vals) >= -vals[:-1] * 0.01))

        n_croissantes = n_valides = 0
        for i in range(min(arr.shape[0], 5)):
            row = arr[i, arr[i] > 0]
            if len(row) >= 2:
                n_valides += 1
                if np.all(np.diff(row) >= -row[:-1] * 0.01):
                    n_croissantes += 1
        return True if n_valides == 0 else n_croissantes / n_valides >= 0.7

    # =========================================================================
    #  ÉTAPE 3A : DEPUIS TRIANGLE TABLEAU
    # =========================================================================

    def _construire_depuis_triangle(
        self,
        raw:    Union[np.ndarray, pd.DataFrame],
        mode:   str,
        rapport: Dict
    ) -> np.ndarray:
        """Construit un triangle numpy depuis un tableau (DataFrame ou array)."""

        if isinstance(raw, pd.DataFrame):
            num = raw.select_dtypes(include=[np.number])
            num = num.dropna(how='all')
            num = num.loc[:, num.notna().any(axis=0)]

            # Retirer en-têtes numériques (années > 1900)
            if num.shape[0] > 1 and num.shape[1] > 1:
                first_val = num.iloc[0, 0]
                if not np.isnan(first_val) and first_val > 1900:
                    num = num.iloc[1:, 1:]
                    rapport['infos'].append(
                        "En-têtes numériques (années) retirés automatiquement"
                    )

            num = num[(num > 0).any(axis=1)]
            num = num.loc[:, (num > 0).any(axis=0)]
            C   = num.fillna(0).values.astype(float)
        else:
            C = raw.copy()

        C = np.nan_to_num(C, nan=0.0, posinf=0.0, neginf=0.0)

        if mode == 'non_cumule':
            C_cum = np.zeros_like(C)
            for i in range(C.shape[0]):
                for j in range(C.shape[1]):
                    C_cum[i, j] = (C_cum[i, j-1] + C[i, j]) if j > 0 else C[i, j]
            C = C_cum
            rapport['infos'].append("Triangle non cumulé → cumulé automatiquement")

        return C

    # =========================================================================
    #  ÉTAPE 3B : DEPUIS SINISTRES BRUTS
    # =========================================================================

    def _construire_depuis_brutes(
        self, df: pd.DataFrame, rapport: Dict
    ) -> np.ndarray:
        """
        Construit un triangle cumulé depuis des sinistres bruts.
        Une ligne = un sinistre ou un agrégat
        (annee_survenance, annee_paiement, montant).
        """
        df = df.copy()
        df.columns = [str(c).lower().strip().replace(' ', '_') for c in df.columns]

        col_surv = self._trouver_colonne(df, 'annee_survenance', rapport)
        col_mont = self._trouver_colonne(df, 'montant',          rapport)

        if col_surv is None or col_mont is None:
            raise ValueError(
                f"Colonnes introuvables. Disponibles : {list(df.columns)}. "
                f"Attendu : annee_survenance + montant (ou synonymes). "
                f"Utilisez schema_mapping pour forcer le mapping."
            )

        col_dev  = self._trouver_colonne(df, 'annee_developpement', rapport)
        col_paie = self._trouver_colonne(df, 'annee_paiement',      rapport)

        df[col_surv] = self._normaliser_annee(df[col_surv])
        df[col_mont] = pd.to_numeric(df[col_mont], errors='coerce').fillna(0)

        n_neg = (df[col_mont] < 0).sum()
        if n_neg > 0:
            df[col_mont] = df[col_mont].abs()

        annees_surv = sorted(df[col_surv].dropna().unique())
        annee_min   = int(min(annees_surv))
        annee_max   = int(max(annees_surv))
        n_annees    = annee_max - annee_min + 1

        if col_dev is not None:
            df[col_dev] = pd.to_numeric(df[col_dev], errors='coerce').fillna(0).astype(int)
            n_dev  = int(df[col_dev].max()) + 1
            pivot  = df.groupby([col_surv, col_dev])[col_mont].sum().reset_index()
            C_inc  = np.zeros((n_annees, n_dev))
            for _, row in pivot.iterrows():
                i = int(row[col_surv]) - annee_min
                j = int(row[col_dev])
                if 0 <= i < n_annees and 0 <= j < n_dev:
                    C_inc[i, j] = row[col_mont]

        elif col_paie is not None:
            df[col_paie] = self._normaliser_annee(df[col_paie])
            df['_dev_']  = df[col_paie] - df[col_surv]
            df = df[df['_dev_'] >= 0]
            n_dev  = int(df['_dev_'].max()) + 1 if len(df) > 0 else n_annees
            pivot  = df.groupby([col_surv, '_dev_'])[col_mont].sum().reset_index()
            C_inc  = np.zeros((n_annees, max(n_dev, n_annees)))
            for _, row in pivot.iterrows():
                i = int(row[col_surv]) - annee_min
                j = int(row['_dev_'])
                if 0 <= i < n_annees and 0 <= j < C_inc.shape[1]:
                    C_inc[i, j] += row[col_mont]

        else:
            rapport['alertes'].append(
                "⚠️ Colonne 'annee_paiement' introuvable — "
                "hypothèse : tout payé dans l'année de survenance"
            )
            C_inc = np.zeros((n_annees, 1))
            for ann in annees_surv:
                i = int(ann) - annee_min
                C_inc[i, 0] = df[df[col_surv] == ann][col_mont].sum()

        C_cum = np.cumsum(C_inc, axis=1)
        rapport['infos'].append(
            f"Triangle construit : {n_annees} années "
            f"({annee_min}→{annee_max}), "
            f"{C_cum.shape[1]} périodes"
        )
        return C_cum

    # =========================================================================
    #  ÉTAPE 4 : VALIDER ET NETTOYER
    # =========================================================================

    def _valider_et_nettoyer(self, C: np.ndarray, rapport: Dict) -> np.ndarray:
        """
        Valide et nettoie le triangle.
        Fonctionne pour n×m quelconque (pas forcément carré).
        """
        if C.ndim != 2:
            raise ValueError(f"Matrice 2D attendue, {C.ndim}D reçue")

        n, m = C.shape

        if n < 3:
            raise ValueError(f"Triangle trop petit ({n} lignes). Minimum : 3.")
        if m < 3:
            raise ValueError(f"Triangle trop peu développé ({m} col.). Minimum : 3.")

        if n > 60:
            rapport['alertes'].append(f"⚠️ Grand triangle ({n}×{m})")

        C = np.nan_to_num(C, nan=0.0, posinf=0.0, neginf=0.0)

        n_neg = (C < 0).sum()
        if n_neg > 0:
            C = np.maximum(C, 0)
            rapport['alertes'].append(f"⚠️ {n_neg} valeur(s) négative(s) remises à zéro")

        # Inversions dans zone cumulée (tolérance 5%)
        n_inv = sum(
            1 for i in range(n) for j in range(1, m)
            if C[i, j] > 0 and C[i, j-1] > 0 and C[i, j] < C[i, j-1] * 0.95
        )
        if n_inv > 0:
            rapport['alertes'].append(
                f"⚠️ {n_inv} inversion(s) dans le triangle cumulé "
                f"(C[i,j] < C[i,j-1]×0.95) — vérifier la cumulativité"
            )

        # Zéros dans zone connue
        n_zeros = sum(
            1 for i in range(n) for j in range(1, min(m, n - i))
            if C[i, j] == 0 and C[i, j-1] > 0
        )
        if n_zeros > 0:
            rapport['alertes'].append(
                f"ℹ️ {n_zeros} zéro(s) dans la zone connue"
            )

        # Diagonale principale
        diag_vides = sum(1 for i in range(n) if C[i, min(n-i-1, m-1)] == 0)
        if diag_vides > n // 3:
            rapport['alertes'].append(
                f"⚠️ {diag_vides}/{n} valeurs vides sur la diagonale principale"
            )

        rapport['infos'].append(
            f"Validation OK : {n}×{m} | "
            f"{n_inv} inversion(s) | {n_zeros} zéro(s) zone connue"
        )
        return C

    # =========================================================================
    #  UTILITAIRES
    # =========================================================================

    def _trouver_colonne(
        self, df: pd.DataFrame, type_col: str, rapport: Dict
    ) -> Optional[str]:
        """Trouve une colonne par son type via synonymes. Retourne None si absent."""
        cols_lower = {c.lower(): c for c in df.columns}
        for syn in [type_col] + self.SYNONYMES.get(type_col, []):
            if syn.lower() in cols_lower:
                return cols_lower[syn.lower()]
        # Recherche partielle
        for syn in [type_col] + self.SYNONYMES.get(type_col, []):
            for col_low, col_orig in cols_lower.items():
                if syn.lower() in col_low or col_low in syn.lower():
                    return col_orig
        return None

    def _normaliser_annee(self, serie: pd.Series) -> pd.Series:
        """
        Normalise une colonne d'années.
        Gère : 2017 (int), 'Year 0' (texte), '2017-01-01' (date).
        """
        def _parser(val):
            if pd.isna(val):
                return np.nan
            s = str(val).strip()
            try:
                f = float(s)
                if 1900 < f < 2100:
                    return int(f)
                if 0 <= f <= 100:
                    return 2000 + int(f)
            except ValueError:
                pass
            m = re.search(r'(\d+)', s)
            if m:
                num = int(m.group(1))
                if 1900 < num < 2100:
                    return num
                if 0 <= num <= 100:
                    return 2000 + num
            return np.nan
        return serie.apply(_parser)

    def _normaliser_primes(
        self, primes, n_annees: int, rapport: Dict
    ) -> Optional[np.ndarray]:
        """Normalise le vecteur de primes en array numpy."""
        if primes is None:
            return None
        if isinstance(primes, pd.Series):
            primes = primes.values
        if isinstance(primes, (list, np.ndarray)):
            p = np.array(primes, dtype=float)
            if len(p) >= n_annees:
                return p[:n_annees]
            if len(p) > 0:
                rapport['alertes'].append(
                    f"⚠️ Vecteur primes ({len(p)}) plus court que le triangle "
                    f"({n_annees} années) — extrapolation par la dernière valeur"
                )
                return np.pad(p, (0, n_annees - len(p)), mode='edge')
        rapport['alertes'].append("⚠️ Format primes non reconnu — ignoré")
        return None
