"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           ACTUARIA — AGENT A7 : PROVISIONNEMENT v4.0                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Architecture en 5 niveaux                                                  ║
║                                                                              ║
║  N1 — Ingestion & Validation du triangle                                    ║
║  N2 — Validation des hypothèses H1/H2/H3/H4                                ║
║  N3 — 4 méthodes actuarielles + Bootstrap + Munich CL                      ║
║  N4 — Best Estimate S2 dynamique + sensibilités                            ║
║  N5 — Graphiques + Commentaire + Rapport + Excel + PDF + Audit             ║
║                                                                              ║
║  Classe principale : AgentA7Provisionnement                                 ║
║  Point d'entrée   : .run(source, ...)                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, io, json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

try:
    from scipy.stats import spearmanr
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

warnings.filterwarnings('ignore')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | actuaria.a7 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('actuaria.a7')

# Palette ActuarIA
NAVY   = "#0F2E52"
NAVY_L = "#1B3A5C"
OR     = "#C9A84C"
BLANC  = "#F0F4F8"
GRIS   = "#8A9AB0"
VERT   = "#2ECC71"
AMBRE  = "#F39C12"
ROUGE  = "#E74C3C"
BLEU   = "#3498DB"


class TriangleValidator:
    """
    Responsabilité unique : recevoir n'importe quelle donnée et retourner
    un triangle numpy valide avec son rapport de qualité.

    Entrées acceptées :
    - numpy array (carré ou rectangulaire, cumulé ou non)
    - pandas DataFrame
    - fichier CSV / Excel
    - dict résultat A2 (sinistres bruts)
    - liste de listes

    Sortie garantie :
    - C : np.ndarray (n_années × n_développements), cumulé, sans NaN
    - rapport : dict avec statut, alertes, metadata
    """

    # Synonymes de colonnes pour sinistres bruts
    SYNONYMES = {
        'annee_survenance':      ['id_year','year','annee','loss_year','acc_year',
                                   'underwriting_year','ay','accident_year'],
        'annee_paiement':        ['payment_year','annee_reglement','dev_year',
                                   'development_year','py','dy'],
        'annee_developpement':   ['dev','developpement','lag','retard','development'],
        'montant':               ['cout_total_sinistres','claim_amount','montant',
                                   'charge','cout_sinistre','paid','incurred',
                                   'cumulative','amount'],
        'nb_sinistres':          ['claim_nb','claimnb','nb_claims','claim_count','freq'],
    }

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # ── POINT D'ENTRÉE UNIQUE ─────────────────────────────────────────────────

    def charger(
        self,
        source,
        mode:         str = 'auto',   # 'cumule' | 'non_cumule' | 'brutes' | 'auto'
        triangle_engage = None,        # optionnel — pour Munich CL
        primes       = None,           # optionnel — vecteur primes par année
    ) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], Dict]:
        """
        Point d'entrée universel.

        Retourne :
            C        : triangle cumulé payé (n × m), n ≥ m
            C_engage : triangle engagé si fourni, sinon None
            primes   : vecteur primes si fourni, sinon None
            rapport  : dict complet qualité + metadata
        """
        rapport = {
            'alertes':  [],
            'infos':    [],
            'statut':   'VERT',
            'taille':   None,
            'mode_detecte': mode,
        }

        try:
            # ── Étape 1 : convertir source → DataFrame ou ndarray ────────────
            raw = self._lire_source(source, rapport)

            # ── Étape 2 : détecter le format ─────────────────────────────────
            mode_final = self._detecter_mode(raw, mode, rapport)

            # ── Étape 3 : construire le triangle selon le mode ───────────────
            if mode_final == 'brutes':
                C = self._construire_depuis_brutes(raw, rapport)
            else:
                C = self._construire_depuis_triangle(raw, mode_final, rapport)

            # ── Étape 4 : valider le triangle ────────────────────────────────
            C = self._valider_et_nettoyer(C, rapport)

            # ── Étape 5 : triangle engagé si fourni ──────────────────────────
            C_eng = None
            if triangle_engage is not None:
                try:
                    raw_eng = self._lire_source(triangle_engage, {})
                    C_eng   = self._construire_depuis_triangle(raw_eng, 'cumule', {})
                    C_eng   = self._valider_et_nettoyer(C_eng, {})
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

            # ── Étape 6 : primes ─────────────────────────────────────────────
            primes_out = self._normaliser_primes(primes, C.shape[0], rapport)

            # ── Résumé ───────────────────────────────────────────────────────
            n, m = C.shape
            rapport['taille']       = f"{n}×{m}"
            rapport['n_annees']     = n
            rapport['n_dev']        = m
            rapport['mode_detecte'] = mode_final
            rapport['infos'].append(f"✅ Triangle {n}×{m} prêt ({mode_final})")

            if rapport['alertes']:
                rapport['statut'] = 'AMBRE'
            else:
                rapport['statut'] = 'VERT'

            if self.verbose:
                logger.info(f"Triangle {n}×{m} chargé | mode={mode_final} | "
                            f"statut={rapport['statut']}")

            return C, C_eng, primes_out, rapport

        except Exception as e:
            rapport['statut'] = 'ROUGE'
            rapport['alertes'].append(f"❌ Erreur chargement : {str(e)}")
            logger.error(f"Erreur chargement triangle : {e}", exc_info=True)
            raise ValueError(f"Impossible de charger le triangle : {e}") from e

    # ── ÉTAPE 1 : LIRE LA SOURCE ──────────────────────────────────────────────

    def _lire_source(self, source, rapport: Dict) -> Union[np.ndarray, pd.DataFrame]:
        """Convertit n'importe quelle source en DataFrame ou ndarray."""

        # numpy array → garder tel quel
        if isinstance(source, np.ndarray):
            return source.astype(float)

        # liste de listes → numpy
        if isinstance(source, list):
            return np.array(source, dtype=float)

        # DataFrame → garder
        if isinstance(source, pd.DataFrame):
            return source

        # dict A2 → extraire le DataFrame
        if isinstance(source, dict):
            if 'dataframe' in source:
                return source['dataframe']
            if 'df' in source:
                return source['df']
            # Essayer de reconstruire depuis les clés connues
            raise ValueError(
                "Dict fourni mais clé 'dataframe' ou 'df' introuvable. "
                "Vérifiez le format du résultat A2."
            )

        # Fichier Excel ou CSV
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"Fichier introuvable : {path}")
            if path.suffix.lower() in ['.xlsx', '.xls', '.xlsm']:
                return pd.read_excel(path)
            if path.suffix.lower() in ['.csv', '.txt']:
                # Essayer plusieurs séparateurs
                for sep in [',', ';', '\t', '|']:
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
            if name.endswith(('.xlsx', '.xls')):
                return pd.read_excel(source)
            else:
                source.seek(0)
                return pd.read_csv(source)
        except Exception as e:
            raise ValueError(f"Impossible de lire la source : {type(source)} — {e}")

    # ── ÉTAPE 2 : DÉTECTER LE MODE ────────────────────────────────────────────

    def _detecter_mode(
        self,
        raw: Union[np.ndarray, pd.DataFrame],
        mode: str,
        rapport: Dict
    ) -> str:
        """Détecte automatiquement si les données sont brutes ou un triangle."""

        if mode != 'auto':
            return mode

        if isinstance(raw, np.ndarray):
            # Array → forcément un triangle (brutes = DataFrame)
            return 'cumule' if self._est_cumule(raw) else 'non_cumule'

        if isinstance(raw, pd.DataFrame):
            cols = [str(c).lower() for c in raw.columns]

            # Présence de colonnes de sinistres bruts
            has_survenance = any(
                syn in cols
                for syn in self.SYNONYMES['annee_survenance'] + ['annee_survenance']
            )
            has_montant = any(
                syn in cols
                for syn in self.SYNONYMES['montant'] + ['montant']
            )

            if has_survenance and has_montant:
                rapport['infos'].append(
                    "Format détecté : sinistres bruts (une ligne par sinistre)"
                )
                return 'brutes'

            # Sinon c'est un triangle en tableau
            rapport['infos'].append(
                "Format détecté : triangle en tableau (lignes=années, colonnes=développements)"
            )
            # Vérifier si cumulé
            num_df = raw.select_dtypes(include=[np.number])
            if num_df.shape[0] >= 2 and num_df.shape[1] >= 2:
                # Prendre la première ligne complète
                for i in range(min(3, num_df.shape[0])):
                    row = num_df.iloc[i].dropna().values
                    if len(row) >= 2 and all(row > 0):
                        if self._est_cumule(row.reshape(1, -1)):
                            return 'cumule'
                        else:
                            return 'non_cumule'
            return 'cumule'

        return 'cumule'

    def _est_cumule(self, arr: np.ndarray) -> bool:
        """Teste si un triangle est cumulé (croissant par ligne)."""
        if arr.ndim == 1:
            vals = arr[arr > 0]
            return len(vals) < 2 or bool(np.all(np.diff(vals) >= -vals[:-1] * 0.01))

        n_lignes_croissantes = 0
        n_lignes_valides     = 0
        for i in range(min(arr.shape[0], 5)):
            row = arr[i, arr[i] > 0]
            if len(row) >= 2:
                n_lignes_valides += 1
                if np.all(np.diff(row) >= -row[:-1] * 0.01):
                    n_lignes_croissantes += 1
        if n_lignes_valides == 0:
            return True
        return n_lignes_croissantes / n_lignes_valides >= 0.7

    # ── ÉTAPE 3A : CONSTRUIRE DEPUIS TRIANGLE TABLEAU ─────────────────────────

    def _construire_depuis_triangle(
        self,
        raw: Union[np.ndarray, pd.DataFrame],
        mode: str,
        rapport: Dict
    ) -> np.ndarray:
        """Construit un triangle numpy depuis un tableau (DataFrame ou array)."""

        # Convertir DataFrame → array numérique
        if isinstance(raw, pd.DataFrame):
            # Retirer colonnes/lignes purement texte (labels d'années)
            num = raw.select_dtypes(include=[np.number])

            # Retirer lignes entièrement nulles
            num = num.dropna(how='all')
            num = num.loc[:, num.notna().any(axis=0)]

            # Si la première colonne ressemble à des années (> 1900)
            # ou la première ligne, les retirer
            if num.shape[0] > 1 and num.shape[1] > 1:
                first_val = num.iloc[0, 0]
                if not np.isnan(first_val) and first_val > 1900:
                    num = num.iloc[1:, 1:]
                    rapport['infos'].append(
                        "Ligne/colonne d'en-têtes (années) retirée automatiquement"
                    )

            # Retirer lignes sans aucune valeur positive
            mask_lignes = (num > 0).any(axis=1)
            num = num[mask_lignes]
            num = num.loc[:, (num > 0).any(axis=0)]

            C = num.fillna(0).values.astype(float)
        else:
            C = raw.copy()

        # Remettre à zéro les NaN
        C = np.nan_to_num(C, nan=0.0)

        # Si non cumulé → cumuler
        if mode == 'non_cumule':
            C_cum = np.zeros_like(C)
            for i in range(C.shape[0]):
                for j in range(C.shape[1]):
                    C_cum[i, j] = C_cum[i, j-1] + C[i, j] if j > 0 else C[i, j]
            C = C_cum
            rapport['infos'].append("Triangle non cumulé → cumulé automatiquement")

        return C

    # ── ÉTAPE 3B : CONSTRUIRE DEPUIS SINISTRES BRUTS ─────────────────────────

    def _construire_depuis_brutes(
        self,
        df: pd.DataFrame,
        rapport: Dict
    ) -> np.ndarray:
        """
        Construit un triangle cumulé depuis des sinistres bruts.
        Une ligne = un sinistre ou un agrégat (annee_survenance, annee_paiement, montant).
        """
        # Normaliser les noms de colonnes
        df = df.copy()
        df.columns = [str(c).lower().strip().replace(' ', '_') for c in df.columns]

        # Trouver les colonnes
        col_surv = self._trouver_colonne(df, 'annee_survenance', rapport)
        col_mont = self._trouver_colonne(df, 'montant', rapport)

        if col_surv is None or col_mont is None:
            raise ValueError(
                f"Colonnes introuvables. Colonnes disponibles : {list(df.columns)}. "
                f"Attendu : annee_survenance + montant (ou synonymes)."
            )

        # Chercher colonne de développement ou paiement
        col_dev  = self._trouver_colonne(df, 'annee_developpement', rapport)
        col_paie = self._trouver_colonne(df, 'annee_paiement', rapport)

        # Convertir les années en entiers
        df[col_surv] = self._normaliser_annee(df[col_surv])
        df[col_mont] = pd.to_numeric(df[col_mont], errors='coerce').fillna(0)

        # Valeur absolue des montants négatifs (recours)
        n_neg = (df[col_mont] < 0).sum()
        if n_neg > 0:
            df[col_mont] = df[col_mont].abs()
            rapport['alertes'].append(
                f"⚠️ {n_neg} montants négatifs convertis en valeur absolue (recours/remboursements)"
            )

        annees_surv = sorted(df[col_surv].dropna().unique())
        annee_min   = int(min(annees_surv))
        annee_max   = int(max(annees_surv))
        n_annees    = annee_max - annee_min + 1

        if col_dev is not None:
            # Colonne développement explicite (lag = 0, 1, 2, ...)
            df[col_dev] = pd.to_numeric(df[col_dev], errors='coerce').fillna(0).astype(int)
            n_dev = int(df[col_dev].max()) + 1

            pivot = df.groupby([col_surv, col_dev])[col_mont].sum().reset_index()
            C_inc = np.zeros((n_annees, n_dev))
            for _, row in pivot.iterrows():
                i = int(row[col_surv]) - annee_min
                j = int(row[col_dev])
                if 0 <= i < n_annees and 0 <= j < n_dev:
                    C_inc[i, j] = row[col_mont]

        elif col_paie is not None:
            # Colonne année de paiement → calculer le développement
            df[col_paie] = self._normaliser_annee(df[col_paie])
            df['dev'] = df[col_paie] - df[col_surv]
            df = df[df['dev'] >= 0]  # retirer incohérences
            n_dev = int(df['dev'].max()) + 1 if len(df) > 0 else n_annees

            pivot = df.groupby([col_surv, 'dev'])[col_mont].sum().reset_index()
            C_inc = np.zeros((n_annees, max(n_dev, n_annees)))
            for _, row in pivot.iterrows():
                i = int(row[col_surv]) - annee_min
                j = int(row['dev'])
                if 0 <= i < n_annees and 0 <= j < C_inc.shape[1]:
                    C_inc[i, j] += row[col_mont]

        else:
            # Pas d'année de paiement → hypothèse paiement dans l'année de survenance
            rapport['alertes'].append(
                "⚠️ Colonne 'annee_paiement' introuvable — "
                "hypothèse : tout payé dans l'année de survenance (triangle diagonal)"
            )
            C_inc = np.zeros((n_annees, 1))
            for ann in annees_surv:
                i = int(ann) - annee_min
                montant = df[df[col_surv] == ann][col_mont].sum()
                C_inc[i, 0] = montant

        # Cumuler le triangle
        C_cum = np.cumsum(C_inc, axis=1)

        rapport['infos'].append(
            f"Triangle construit depuis sinistres bruts : "
            f"{n_annees} années ({annee_min}→{annee_max}), "
            f"{C_cum.shape[1]} périodes de développement"
        )

        return C_cum

    # ── ÉTAPE 4 : VALIDER ET NETTOYER ────────────────────────────────────────

    def _valider_et_nettoyer(self, C: np.ndarray, rapport: Dict) -> np.ndarray:
        """
        Valide et nettoie le triangle.
        Fonctionne pour n'importe quelle taille n×m (pas forcément carré).
        """
        if C.ndim != 2:
            raise ValueError(f"Le triangle doit être une matrice 2D, pas {C.ndim}D")

        n, m = C.shape

        if n < 3:
            raise ValueError(
                f"Triangle trop petit ({n} lignes). Minimum 3 années de survenance."
            )
        if m < 3:
            raise ValueError(
                f"Triangle trop peu développé ({m} colonnes). Minimum 3 périodes."
            )

        # Alertes taille
        if n > 60:
            rapport['alertes'].append(
                f"⚠️ Grand triangle ({n}×{m}) — calculs plus longs (~{n*m//100}s)"
            )

        # Remplacer NaN et inf
        C = np.nan_to_num(C, nan=0.0, posinf=0.0, neginf=0.0)

        # Valeurs négatives → zéro (après gestion des recours en amont)
        n_neg = (C < 0).sum()
        if n_neg > 0:
            C = np.maximum(C, 0)
            rapport['alertes'].append(f"⚠️ {n_neg} valeurs négatives remises à zéro")

        # Détecter les inversions (décroissance dans le triangle cumulé)
        n_inversions = 0
        for i in range(n):
            for j in range(1, m):
                if C[i, j] > 0 and C[i, j-1] > 0 and C[i, j] < C[i, j-1] * 0.95:
                    n_inversions += 1
        if n_inversions > 0:
            rapport['alertes'].append(
                f"⚠️ {n_inversions} inversion(s) détectée(s) dans le triangle cumulé "
                f"(C[i,j] < C[i,j-1]×0.95) — vérifier la cumulativité"
            )

        # Détecter les zéros dans la zone connue
        n_zeros_zone = 0
        for i in range(n):
            for j in range(m - i):
                if j > 0 and C[i, j] == 0 and C[i, j-1] > 0:
                    n_zeros_zone += 1
        if n_zeros_zone > 0:
            rapport['alertes'].append(
                f"ℹ️ {n_zeros_zone} zéro(s) dans la zone connue du triangle "
                f"— interpolation automatique si nécessaire"
            )

        # Masque de la zone connue (diagonale supérieure gauche)
        # Pour un triangle de développement : zone connue = C[i,j] avec i+j < n
        # IMPORTANT : on ne force PAS la matrice carrée
        # On identifie juste la zone connue vs inconnue
        masque_connu = np.zeros((n, m), dtype=bool)
        for i in range(n):
            for j in range(min(m, n - i)):
                masque_connu[i, j] = True

        # Vérifier que la diagonale principale a des valeurs
        diag_valeurs = [C[i, min(n-i-1, m-1)] for i in range(n)]
        n_diag_vides = sum(1 for v in diag_valeurs if v == 0)
        if n_diag_vides > n // 3:
            rapport['alertes'].append(
                f"⚠️ {n_diag_vides} valeurs vides sur la diagonale principale — "
                f"données récentes manquantes"
            )

        rapport['infos'].append(
            f"Validation OK : triangle {n}×{m}, "
            f"{n_inversions} inversions, {n_zeros_zone} zéros zone connue"
        )

        return C

    # ── UTILITAIRES ───────────────────────────────────────────────────────────

    def _trouver_colonne(
        self, df: pd.DataFrame, type_col: str, rapport: Dict
    ) -> Optional[str]:
        """Trouve une colonne par son type en cherchant dans les synonymes."""
        cols_lower = {c.lower(): c for c in df.columns}
        synonymes  = [type_col] + self.SYNONYMES.get(type_col, [])

        for syn in synonymes:
            if syn.lower() in cols_lower:
                return cols_lower[syn.lower()]

        # Recherche partielle
        for syn in synonymes:
            for col_low, col_orig in cols_lower.items():
                if syn.lower() in col_low or col_low in syn.lower():
                    return col_orig

        return None

    def _normaliser_annee(self, serie: pd.Series) -> pd.Series:
        """
        Normalise une colonne d'années.
        Gère : 2017 (int), 'Year 0' (texte), '2017-01-01' (date).
        """
        import re

        def parser_annee(val):
            if pd.isna(val):
                return np.nan
            s = str(val).strip()
            # Entier ou float direct
            try:
                f = float(s)
                if 1900 < f < 2100:
                    return int(f)
                # Pourrait être un index (Year 0, Year 1...)
                if 0 <= f <= 100:
                    return 2000 + int(f)  # convention : base 2000
            except ValueError:
                pass
            # Format "Year N" ou "An N"
            m = re.search(r'(\d+)', s)
            if m:
                num = int(m.group(1))
                if 1900 < num < 2100:
                    return num
                if 0 <= num <= 100:
                    return 2000 + num
            return np.nan

        return serie.apply(parser_annee)

    def _normaliser_primes(
        self,
        primes,
        n_annees: int,
        rapport: Dict
    ) -> Optional[np.ndarray]:
        """Normalise le vecteur de primes."""
        if primes is None:
            return None

        if isinstance(primes, (list, np.ndarray)):
            p = np.array(primes, dtype=float)
            if len(p) >= n_annees:
                return p[:n_annees]
            elif len(p) > 0:
                # Extrapoler si trop court
                rapport['alertes'].append(
                    f"⚠️ Vecteur primes ({len(p)} valeurs) plus court que le triangle "
                    f"({n_annees} années) — extrapolation par la dernière valeur"
                )
                return np.pad(p, (0, n_annees - len(p)), mode='edge')

        if isinstance(primes, pd.Series):
            return self._normaliser_primes(primes.values, n_annees, rapport)

        rapport['alertes'].append("⚠️ Format primes non reconnu — ignoré")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# NIVEAU 2 — VALIDATION DES HYPOTHÈSES H1 / H2 / H3
# ══════════════════════════════════════════════════════════════════════════════

class HypothesesValidator:
    """
    Valide les hypothèses actuarielles AVANT tout calcul.

    H1 — Indépendance des années de survenance
         Test de Mack (1993) : les facteurs f[i,j] et f[i,j+1]
         ne doivent pas être corrélés entre colonnes consécutives.
         Test sur les FACTEURS (pas les valeurs cumulées).

    H2 — Stabilité des facteurs dans le temps
         CV des facteurs individuels par colonne < seuil.
         Teste aussi la dérive temporelle (facteurs récents vs anciens).

    H3 — Qualité de l'a priori BF
         Vérifie que le Loss Ratio a priori est cohérent
         avec les années les plus matures du triangle.

    H4 — Homoscédasticité (Bootstrap ODP)
         Variance des résidus de Pearson homogène sur toutes les colonnes.
         Condition nécessaire pour que le Bootstrap soit valide.
    """

    def __init__(self):
        pass

    def valider(
        self,
        C:      np.ndarray,
        primes: Optional[np.ndarray] = None,
    ) -> Dict:
        """
        Lance tous les tests et retourne un rapport structuré.

        Retourne :
            h1, h2, h3, h4 : résultats par hypothèse
            scores          : score de confiance 0-100 par méthode
            methode_recommandee : str
            statut_global   : VERT / AMBRE / ROUGE
            alertes         : list[str]
        """
        n, m = C.shape
        alertes = []
        infos   = []

        # ── H1 : INDÉPENDANCE ────────────────────────────────────────────────
        h1 = self._tester_h1_independance(C, alertes, infos)

        # ── H2 : STABILITÉ ───────────────────────────────────────────────────
        h2 = self._tester_h2_stabilite(C, alertes, infos)

        # ── H3 : A PRIORI BF ─────────────────────────────────────────────────
        h3 = self._tester_h3_apriori(C, primes, alertes, infos)

        # ── H4 : HOMOSCÉDASTICITÉ ────────────────────────────────────────────
        h4 = self._tester_h4_homosc(C, alertes, infos)

        # ── SCORES DE CONFIANCE PAR MÉTHODE ──────────────────────────────────
        scores = self._calculer_scores(h1, h2, h3, h4, n)

        # ── MÉTHODE RECOMMANDÉE ───────────────────────────────────────────────
        methode_rec, raison_rec = self._recommander_methode(
            scores, h1, h2, h3, n
        )

        # ── STATUT GLOBAL ────────────────────────────────────────────────────
        if not h1['ok'] and not h2['ok']:
            statut = 'ROUGE'
        elif not h1['ok'] or not h2['ok']:
            statut = 'AMBRE'
        else:
            statut = 'VERT'

        return {
            'h1_independance':       h1,
            'h2_stabilite':          h2,
            'h3_apriori_bf':         h3,
            'h4_homosc_bootstrap':   h4,
            'scores_confiance':      scores,
            'methode_recommandee':   methode_rec,
            'raison_recommandation': raison_rec,
            'statut_global':         statut,
            'alertes':               alertes,
            'infos':                 infos,
        }

    # ── H1 : INDÉPENDANCE ────────────────────────────────────────────────────

    def _tester_h1_independance(
        self, C: np.ndarray, alertes: List, infos: List
    ) -> Dict:
        """
        Test de Mack (1993) — indépendance des années de survenance.

        Méthode : pour chaque paire de colonnes consécutives (j, j+1),
        calculer la corrélation de Spearman entre les facteurs individuels.
        Si |corr| > 0.5 sur plusieurs colonnes → H1 rejetée.

        On utilise Spearman (rang) car les facteurs peuvent être asymétriques.
        """
        n, m = C.shape
        correlations = []
        details      = []

        for j in range(m - 2):
            fact_j  = []
            fact_j1 = []
            for i in range(n - j - 2):
                c_ij  = C[i, j]
                c_ij1 = C[i, j+1]
                c_ij2 = C[i, j+2]
                if c_ij > 0 and c_ij1 > 0 and c_ij2 > 0:
                    fact_j.append(c_ij1 / c_ij)
                    fact_j1.append(c_ij2 / c_ij1)

            if len(fact_j) >= 4:
                # Corrélation de Spearman (plus robuste que Pearson)
                from scipy.stats import spearmanr
                corr, pval = spearmanr(fact_j, fact_j1)
                if not np.isnan(corr):
                    correlations.append(abs(corr))
                    details.append({
                        'colonnes':  f"j={j}→j+1={j+1}",
                        'corr':      round(float(corr), 3),
                        'pval':      round(float(pval), 3),
                        'n_obs':     len(fact_j),
                        'significatif': pval < 0.05 and abs(corr) > 0.5,
                    })

        if not correlations:
            return {
                'ok':      True,
                'score':   80,
                'corr_max': 0,
                'corr_moy': 0,
                'message': "H1 non testable — trop peu de données",
                'details': [],
            }

        corr_max = float(np.max(correlations))
        corr_moy = float(np.mean(correlations))
        n_sig    = sum(1 for d in details if d['significatif'])

        # H1 OK si : corrélation moyenne < 0.5 ET pas plus de 2 colonnes sig.
        ok = corr_moy < 0.50 and n_sig <= 2

        score = max(0, int((1 - corr_moy) * 100))

        if not ok:
            alertes.append(
                f"⚠️ H1 Indépendance : corrélation moyenne des facteurs = {corr_moy:.2f} "
                f"({n_sig} colonnes significatives) → années de survenance dépendantes. "
                f"BF ou Cape Cod recommandés."
            )
            message = (
                f"H1 REJETÉE — corrélation moy={corr_moy:.2f}, max={corr_max:.2f}. "
                f"{n_sig} paires de colonnes montrent une dépendance significative. "
                f"CL et Mack peuvent être biaisés."
            )
        else:
            if corr_moy > 0.30:
                alertes.append(
                    f"🟡 H1 Indépendance : corrélation moy={corr_moy:.2f} — limite acceptable"
                )
            infos.append(f"✅ H1 Indépendance validée (corr_moy={corr_moy:.2f})")
            message = (
                f"H1 VALIDÉE — corrélation moy={corr_moy:.2f} < 0.50. "
                f"Les années de survenance sont indépendantes. CL est approprié."
            )

        return {
            'ok':       ok,
            'score':    score,
            'corr_max': round(corr_max, 3),
            'corr_moy': round(corr_moy, 3),
            'n_colonnes_testees': len(correlations),
            'n_colonnes_sig':     n_sig,
            'message':  message,
            'details':  details[:5],  # max 5 détails
        }

    # ── H2 : STABILITÉ ───────────────────────────────────────────────────────

    def _tester_h2_stabilite(
        self, C: np.ndarray, alertes: List, infos: List
    ) -> Dict:
        """
        Stabilité des facteurs dans le temps.

        Test 1 : CV des facteurs individuels par colonne (< 15% = stable)
        Test 2 : Dérive temporelle — facteurs récents vs anciens
                 (différence > 20% = dérive détectée)
        """
        n, m = C.shape
        cv_par_colonne   = []
        derive_par_col   = []
        details          = []

        for j in range(m - 1):
            facteurs = []
            for i in range(n - j - 1):
                if C[i, j] > 0 and C[i, j+1] > 0:
                    facteurs.append(C[i, j+1] / C[i, j])

            if len(facteurs) >= 3:
                arr  = np.array(facteurs)
                moy  = float(np.mean(arr))
                std  = float(np.std(arr))
                cv   = std / moy if moy > 0 else 0
                cv_par_colonne.append(cv)

                # Dérive : comparer 1ère moitié vs 2ème moitié
                mid = len(facteurs) // 2
                if mid >= 2:
                    moy_anc = float(np.mean(arr[:mid]))
                    moy_rec = float(np.mean(arr[mid:]))
                    derive  = abs(moy_rec - moy_anc) / max(moy_anc, 1e-6)
                    derive_par_col.append(derive)
                else:
                    derive = 0

                details.append({
                    'colonne': j,
                    'n_obs':   len(facteurs),
                    'f_moyen': round(moy, 4),
                    'cv':      round(cv, 3),
                    'derive':  round(derive, 3),
                })

        if not cv_par_colonne:
            return {
                'ok': True, 'score': 80,
                'cv_moy': 0, 'cv_max': 0, 'derive_moy': 0,
                'message': "H2 non testable — trop peu de données",
                'details': [],
            }

        cv_moy    = float(np.mean(cv_par_colonne))
        cv_max    = float(np.max(cv_par_colonne))
        derive_moy = float(np.mean(derive_par_col)) if derive_par_col else 0

        # H2 OK si CV moyen < 15% ET dérive moyenne < 20%
        ok_cv    = cv_moy < 0.15
        ok_derive = derive_moy < 0.20
        ok       = ok_cv and ok_derive

        score = max(0, int((1 - cv_moy / 0.30) * 100))

        if not ok:
            if not ok_cv:
                alertes.append(
                    f"⚠️ H2 Stabilité : CV moyen des facteurs = {cv_moy:.1%} > 15% "
                    f"→ facteurs instables. Méthode robuste (médiane) recommandée."
                )
            if not ok_derive:
                alertes.append(
                    f"⚠️ H2 Dérive temporelle : {derive_moy:.1%} entre facteurs "
                    f"anciens et récents → triangle en évolution. "
                    f"Pondérer les facteurs récents davantage."
                )
            message = (
                f"H2 {'REJETÉE' if not ok_cv else 'DÉRIVE DÉTECTÉE'} — "
                f"CV moy={cv_moy:.1%}, dérive={derive_moy:.1%}. "
                f"Les facteurs ne sont pas homogènes dans le temps."
            )
        else:
            infos.append(
                f"✅ H2 Stabilité validée (CV moy={cv_moy:.1%}, "
                f"dérive={derive_moy:.1%})"
            )
            message = (
                f"H2 VALIDÉE — CV moy={cv_moy:.1%} < 15%, "
                f"dérive={derive_moy:.1%} < 20%. "
                f"Les facteurs sont stables dans le temps."
            )

        return {
            'ok':        ok,
            'ok_cv':     ok_cv,
            'ok_derive': ok_derive,
            'score':     score,
            'cv_moy':    round(cv_moy, 4),
            'cv_max':    round(cv_max, 4),
            'derive_moy': round(derive_moy, 4),
            'message':   message,
            'details':   details,
        }

    # ── H3 : A PRIORI BF ─────────────────────────────────────────────────────

    def _tester_h3_apriori(
        self,
        C:      np.ndarray,
        primes: Optional[np.ndarray],
        alertes: List,
        infos:   List,
    ) -> Dict:
        """
        Qualité de l'a priori Bornhuetter-Ferguson.

        Si primes fournies :
            LR estimé = sinistres ultimes / primes (années matures)
            Vérifier cohérence avec le marché (0.4 < LR < 1.2)

        Si pas de primes :
            Estimer le LR depuis les années les plus développées
            (colonnes les plus à droite = années les plus matures)
        """
        n, m   = C.shape
        score  = 75  # score par défaut

        # Identifier les années les plus matures (celles dont la dernière
        # colonne connue est la plus à droite = plus développées)
        nb_matures = min(5, n // 2) if n >= 6 else min(3, n - 1)

        # Pour les années matures (i=0 à nb_matures-1), dernière colonne = m-1
        # "% développé" = C[i, n-i-1] / C[i, m-1] si C[i, m-1] > 0
        pct_dev = []
        for i in range(nb_matures):
            last_known = n - i - 1  # dernière colonne connue pour l'année i
            if last_known >= m - 1 and C[i, m-1] > 0:
                pct_dev.append(1.0)  # totalement développé
            elif last_known > 0 and C[i, last_known] > 0:
                # Estimer le % développé depuis le facteur cumulé
                pct_dev.append(min(C[i, last_known] / max(C[i, 0], 1e-6) / 2.5, 1.0))

        pct_dev_moy = float(np.mean(pct_dev)) if pct_dev else 0.8

        if primes is not None and len(primes) >= nb_matures:
            # LR sur les années matures
            lr_annees = []
            for i in range(nb_matures):
                p = float(primes[i])
                # Ultimate = dernière valeur connue (années matures = bien développées)
                last_j = n - i - 1
                u = float(C[i, min(last_j, m-1)])
                if p > 0 and u > 0:
                    lr_annees.append(u / p)

            if lr_annees:
                lr_moy = float(np.mean(lr_annees))
                lr_std = float(np.std(lr_annees))
                cv_lr  = lr_std / max(lr_moy, 1e-6)

                ok_lr   = 0.30 < lr_moy < 1.50
                ok_cv   = cv_lr < 0.25
                ok      = ok_lr and ok_cv
                score   = max(0, min(100, int(100 - cv_lr * 200)))

                if not ok_lr:
                    alertes.append(
                        f"⚠️ H3 A priori BF : LR = {lr_moy:.1%} hors plage [30%-150%] "
                        f"— vérifier les primes"
                    )
                if not ok_cv:
                    alertes.append(
                        f"🟡 H3 A priori BF : CV du LR = {cv_lr:.1%} > 25% "
                        f"— a priori peu homogène entre années"
                    )

                message = (
                    f"H3 {'VALIDÉE' if ok else 'À VÉRIFIER'} — "
                    f"LR a priori = {lr_moy:.1%} (CV={cv_lr:.1%}) "
                    f"sur {nb_matures} années matures."
                )

                return {
                    'ok':          ok,
                    'score':       score,
                    'lr_apriori':  round(lr_moy, 4),
                    'lr_std':      round(lr_std, 4),
                    'cv_lr':       round(cv_lr, 4),
                    'nb_matures':  nb_matures,
                    'source':      'primes_fournies',
                    'message':     message,
                }

        # Pas de primes → estimer le LR depuis les colonnes finales
        # Ratio sinistres fin de développement / début = proxy LR
        lr_estime = []
        for i in range(nb_matures):
            last_j = min(n - i - 1, m - 1)
            if C[i, 0] > 0 and C[i, last_j] > 0:
                # LR proxy = ultimate / prime estimée (prime ≈ C[i,0] / 0.3)
                lr_estime.append(C[i, last_j] / (C[i, 0] / 0.30))

        lr_proxy = float(np.mean(lr_estime)) if lr_estime else 0.75
        ok       = 0.20 < lr_proxy < 2.0

        if not ok:
            alertes.append(
                f"🟡 H3 A priori BF : LR estimé = {lr_proxy:.1%} (sans primes). "
                f"Fournir les primes acquises pour un a priori fiable."
            )
        infos.append(
            f"ℹ️ H3 : LR estimé = {lr_proxy:.1%} (proxy sans primes — "
            f"fournir les primes pour plus de précision)"
        )

        return {
            'ok':         ok,
            'score':      score,
            'lr_apriori': round(lr_proxy, 4),
            'lr_std':     0,
            'cv_lr':      0,
            'nb_matures': nb_matures,
            'source':     'estime_sans_primes',
            'message': (
                f"H3 ESTIMÉE (sans primes) — LR proxy = {lr_proxy:.1%}. "
                f"Fournir les primes acquises pour valider précisément."
            ),
        }

    # ── H4 : HOMOSCÉDASTICITÉ ────────────────────────────────────────────────

    def _tester_h4_homosc(
        self, C: np.ndarray, alertes: List, infos: List
    ) -> Dict:
        """
        Homoscédasticité des résidus — condition du Bootstrap ODP.

        Teste si la variance des facteurs individuels est stable
        d'une colonne à l'autre (condition Mack-ODP).
        """
        n, m   = C.shape
        var_par_colonne = []

        for j in range(m - 1):
            facteurs = []
            poids    = []
            for i in range(n - j - 1):
                if C[i, j] > 0 and C[i, j+1] > 0:
                    facteurs.append(C[i, j+1] / C[i, j])
                    poids.append(C[i, j])

            if len(facteurs) >= 3:
                arr  = np.array(facteurs)
                w    = np.array(poids)
                moy  = np.average(arr, weights=w)
                # Variance pondérée
                var  = np.average((arr - moy)**2, weights=w)
                var_par_colonne.append(float(var))

        if len(var_par_colonne) < 3:
            return {
                'ok': True, 'score': 75, 'phi': 0,
                'cv_var': 0,
                'message': "H4 non testable — trop peu de colonnes",
            }

        # Test : CV des variances par colonne
        var_arr = np.array(var_par_colonne)
        cv_var  = float(np.std(var_arr) / max(np.mean(var_arr), 1e-10))
        phi     = float(np.mean(var_arr))  # facteur de sur-dispersion moyen

        ok    = cv_var < 1.0  # tolérance large pour l'homoscédasticité
        score = max(0, int((1 - cv_var / 2) * 100))

        if not ok:
            alertes.append(
                f"🟡 H4 Homoscédasticité : CV des variances = {cv_var:.2f} > 1.0 "
                f"→ Bootstrap ODP moins fiable. Interpréter les percentiles avec prudence."
            )
            message = (
                f"H4 HÉTÉROSCÉDASTICITÉ détectée — CV variances = {cv_var:.2f}. "
                f"La variance n'est pas stable entre colonnes. "
                f"Bootstrap ODP donne des intervalles approximatifs."
            )
        else:
            infos.append(f"✅ H4 Homoscédasticité validée (CV var={cv_var:.2f})")
            message = (
                f"H4 VALIDÉE — CV variances = {cv_var:.2f} < 1.0. "
                f"Bootstrap ODP fiable."
            )

        return {
            'ok':     ok,
            'score':  score,
            'phi':    round(phi, 6),
            'cv_var': round(cv_var, 3),
            'message': message,
        }

    # ── SCORES ET RECOMMANDATION ──────────────────────────────────────────────

    def _calculer_scores(
        self,
        h1: Dict, h2: Dict, h3: Dict, h4: Dict, n: int
    ) -> Dict:
        """
        Calcule le score de confiance 0-100 pour chaque méthode.
        Basé sur les hypothèses qui la concernent directement.
        """
        s_h1 = h1['score']
        s_h2 = h2['score']
        s_h3 = h3['score']
        s_h4 = h4['score']

        # Bonus taille
        bonus_taille = min(10, (n - 5) * 0.5) if n > 5 else 0

        return {
            'chain_ladder': int(min(100, s_h1 * 0.5 + s_h2 * 0.5 + bonus_taille)),
            'mack_1993':    int(min(100, s_h1 * 0.5 + s_h2 * 0.3 + s_h4 * 0.2 + bonus_taille)),
            'bornhuetter_ferguson': int(min(100, s_h1 * 0.2 + s_h2 * 0.2 + s_h3 * 0.6)),
            'cape_cod':     int(min(100, s_h1 * 0.3 + s_h2 * 0.3 + s_h3 * 0.4)),
            'bootstrap_odp': int(min(100, s_h1 * 0.3 + s_h2 * 0.3 + s_h4 * 0.4)),
        }

    def _recommander_methode(
        self,
        scores: Dict, h1: Dict, h2: Dict, h3: Dict, n: int
    ) -> Tuple[str, str]:
        """Recommande la méthode principale avec justification."""

        raisons = []

        # Règle 1 : Triangle très petit → Cape Cod
        if n < 5:
            return 'cape_cod', (
                f"Triangle de petite taille ({n} années) — Cape Cod plus fiable "
                f"car il exploite un a priori externe quand les données sont rares."
            )

        # Règle 2 : H1 et H2 validées → CL/Mack fiables
        if h1['ok'] and h2['ok']:
            if scores['mack_1993'] >= 70:
                return 'mack_1993', (
                    f"H1 et H2 validées → Chain Ladder approprié. "
                    f"Mack 1993 recommandé pour l'incertitude S2 "
                    f"(score confiance = {scores['mack_1993']})."
                )

        # Règle 3 : H1 non validée → BF ou Cape Cod
        if not h1['ok']:
            raisons.append(
                f"H1 rejetée (corrélation inter-années = {h1['corr_moy']:.2f})"
            )
            if h3['score'] >= 60:
                return 'bornhuetter_ferguson', (
                    "H1 rejetée → CL biaisé. "
                    "Bornhuetter-Ferguson recommandé car il ancre sur un a priori "
                    "indépendant des corrélations du triangle. " + " / ".join(raisons)
                )
            else:
                return 'cape_cod', (
                    "H1 rejetée et a priori BF peu fiable → Cape Cod recommandé. "
                    "Il estime le LR directement depuis les données sans a priori externe."
                )

        # Règle 4 : H2 non validée → méthode robuste CL + BF
        if not h2['ok']:
            raisons.append(
                f"H2 rejetée (CV facteurs = {h2['cv_moy']:.1%}, "
                f"dérive = {h2.get('derive_moy',0):.1%})"
            )
            return 'bornhuetter_ferguson', (
                "H2 rejetée → facteurs instables. "
                "Bornhuetter-Ferguson recommandé pour sa robustesse "
                "face à l'instabilité des facteurs. " + " / ".join(raisons)
            )

        # Par défaut : méthode avec le meilleur score
        best = max(scores, key=scores.get)
        return best, (
            f"Méthode sélectionnée sur score de confiance maximum "
            f"({best} = {scores[best]}/100)."
        )


# ══════════════════════════════════════════════════════════════════════════════
# NIVEAU 3 — MÉTHODES ACTUARIELLES
# ══════════════════════════════════════════════════════════════════════════════

class MethodesActuarielles:
    """
    Calcule les 4 méthodes actuarielles + Bootstrap ODP.

    Principes :
    - Fonctionne sur n'importe quelle taille n×m (pas forcément carré)
    - Zone connue = C[i,j] avec i+j < n (triangle supérieur gauche)
    - Zone inconnue = ce qu'on projette
    - Aucune dépendance externe au Niveau 1 ou 2
    """

    def __init__(self):
        pass

    def calculer_tout(
        self,
        C:              np.ndarray,
        methode_cl:     str = 'standard',
        taux_bf_manuel: Optional[float] = None,
        primes:         Optional[np.ndarray] = None,
        n_sim_boot:     int = 1000,
        seed:           int = 42,
    ) -> Dict:
        """
        Lance toutes les méthodes et retourne les résultats.

        Paramètres
        ──────────
        C              : triangle cumulé n×m
        methode_cl     : 'standard' | 'mediane' | 'volume_weighted' | 'trimmed_mean'
        taux_bf_manuel : Loss Ratio a priori (optionnel)
        primes         : vecteur primes par année (optionnel)
        n_sim_boot     : nombre de simulations Bootstrap
        seed           : graine aléatoire

        Retourne
        ────────
        dict avec cl, mack, bf, cc, bootstrap
        """
        n, m = C.shape

        # Facteurs de développement (communs à toutes les méthodes)
        facteurs, facteurs_indiv = self._calculer_facteurs(C, methode_cl)
        facteurs_cum = self._facteurs_cumules(facteurs)
        tail         = self._tail_factor(facteurs)

        # Appliquer le tail au dernier facteur cumulé
        facteurs_cum_avec_tail = facteurs_cum.copy()
        if tail['tail_factor'] > 1.0:
            facteurs_cum_avec_tail[-1] *= tail['tail_factor']

        # Last diagonal (valeurs sur la dernière diagonale connue)
        last_diag = np.array([
            C[i, min(n - i - 1, m - 1)] for i in range(n)
        ])

        # % développé par année = 1 / facteur cumulé depuis dernière colonne
        pct_dev = self._pct_developpe(C, facteurs_cum_avec_tail, n, m)

        # ── 4 méthodes ────────────────────────────────────────────────────────
        cl   = self._chain_ladder(C, facteurs, facteurs_cum_avec_tail,
                                   last_diag, pct_dev, methode_cl, tail)
        mack = self._mack_1993(C, facteurs, facteurs_indiv, cl)
        bf   = self._bornhuetter_ferguson(C, cl, pcts_dev=pct_dev,
                                           last_diag=last_diag,
                                           primes=primes,
                                           taux_manuel=taux_bf_manuel)
        cc   = self._cape_cod(C, cl, pcts_dev=pct_dev,
                               last_diag=last_diag, primes=primes)
        boot = self._bootstrap_odp(C, facteurs_indiv, n_sim_boot, seed)

        return {
            'facteurs':          [round(f, 6) for f in facteurs],
            'facteurs_cumules':  [round(f, 6) for f in facteurs_cum_avec_tail],
            'facteurs_indiv':    facteurs_indiv,
            'tail_factor':       tail,
            'chain_ladder':      cl,
            'mack':              mack,
            'bf':                bf,
            'cape_cod':          cc,
            'bootstrap':         boot,
            'methode_cl':        methode_cl,
        }

    # ── FACTEURS DE DÉVELOPPEMENT ─────────────────────────────────────────────

    def _calculer_facteurs(
        self, C: np.ndarray, methode: str
    ) -> Tuple[np.ndarray, List[List[float]]]:
        """
        Calcule les facteurs de développement et les facteurs individuels.

        Méthodes :
        - standard       : f_j = ΣC[i,j+1] / ΣC[i,j]  (volume-weighted CL)
        - volume_weighted: pondération par √C[i,j]
        - mediane        : médiane des f[i,j] = C[i,j+1]/C[i,j]
        - trimmed_mean   : moyenne écrêtée (10% haut et bas)

        Retourne :
        - facteurs      : vecteur des facteurs CL agrégés
        - facteurs_indiv: liste de listes (facteurs individuels par colonne)
        """
        n, m = C.shape
        facteurs      = np.ones(m - 1)
        facteurs_indiv = []  # facteurs_indiv[j] = liste des f[i,j]

        for j in range(m - 1):
            f_ind = []
            c_j   = []  # C[i,j] pour la pondération
            for i in range(n - j - 1):
                if i + j + 1 >= n:
                    break
                cij  = C[i, j]
                cij1 = C[i, j+1]
                if cij > 0 and cij1 > 0:
                    f_ind.append(cij1 / cij)
                    c_j.append(cij)

            facteurs_indiv.append(f_ind)

            if len(f_ind) == 0:
                facteurs[j] = 1.0
                continue

            arr = np.array(f_ind)
            w   = np.array(c_j)

            if methode == 'standard':
                # Volume-weighted CL standard
                facteurs[j] = sum(f * w_ for f, w_ in zip(f_ind, c_j)) / max(sum(c_j), 1e-9)

            elif methode == 'volume_weighted':
                # Pondération par racine carrée du volume
                w_sqrt = np.sqrt(w)
                facteurs[j] = float(np.average(arr, weights=w_sqrt))

            elif methode == 'mediane':
                facteurs[j] = float(np.median(arr))

            elif methode == 'trimmed_mean':
                if len(arr) >= 4:
                    q10 = np.percentile(arr, 10)
                    q90 = np.percentile(arr, 90)
                    mask = (arr >= q10) & (arr <= q90)
                    facteurs[j] = float(np.mean(arr[mask])) if mask.sum() > 0 else float(np.mean(arr))
                else:
                    facteurs[j] = float(np.mean(arr))

            else:
                # Fallback : standard
                facteurs[j] = sum(f * w_ for f, w_ in zip(f_ind, c_j)) / max(sum(c_j), 1e-9)

            # Facteur minimum = 1.0 (un triangle cumulé ne peut que croître)
            facteurs[j] = max(facteurs[j], 1.0)

        return facteurs, facteurs_indiv

    def _facteurs_cumules(self, facteurs: np.ndarray) -> np.ndarray:
        """Calcule les facteurs cumulés (tail → j0)."""
        m = len(facteurs)
        f_cum = np.ones(m)
        f_cum[-1] = facteurs[-1]
        for j in range(m - 2, -1, -1):
            f_cum[j] = facteurs[j] * f_cum[j+1]
        return f_cum

    def _tail_factor(self, facteurs: np.ndarray) -> Dict:
        """
        Estime le tail factor par régression exponentielle.
        tail = facteur de développement au-delà de la dernière colonne.
        """
        n_f = len(facteurs)
        if n_f < 4:
            return {'tail_factor': 1.0, 'methode': 'aucune', 'statut': 'VERT',
                    'message': 'Tail factor = 1.0 (trop peu de facteurs)'}

        # Utiliser les 8 derniers facteurs (les plus proches de 1)
        f_queue = facteurs[max(0, n_f-8):]
        x = np.arange(len(f_queue), dtype=float)

        # Régression exponentielle : log(f-1) = a + b*x
        y = np.log(np.maximum(f_queue - 1, 1e-8))
        try:
            b, a = np.polyfit(x, y, 1)
            # Extrapoler au-delà
            tail = 1.0
            for k in range(len(f_queue), len(f_queue) + 20):
                f_extrap = 1 + np.exp(a + b * k)
                if f_extrap < 1.0001:
                    break
                tail *= f_extrap
            tail = float(np.clip(tail, 1.0, 1.15))
        except Exception:
            tail = 1.0

        statut = 'VERT' if tail < 1.02 else 'AMBRE' if tail < 1.05 else 'ROUGE'
        return {
            'tail_factor': round(tail, 6),
            'methode':     'exponentielle',
            'statut':      statut,
            'message': (
                f"Tail factor = {tail:.4f} — "
                f"{'développement considéré complet' if tail < 1.001 else f'+{(tail-1)*100:.2f}% de provisions additionnelles'}"
            ),
        }

    def _pct_developpe(
        self, C: np.ndarray, f_cum: np.ndarray, n: int, m: int
    ) -> np.ndarray:
        """
        % développé pour chaque année de survenance.
        pct_dev[i] = 1 / f_cum[k] où k = dernière colonne connue pour l'année i.
        """
        pct = np.ones(n)
        for i in range(n):
            k = min(n - i - 1, m - 1)  # dernière colonne connue
            if k < len(f_cum) and f_cum[k] > 0:
                pct[i] = 1.0 / f_cum[k]
            else:
                pct[i] = 1.0
        return np.clip(pct, 0.0, 1.0)

    # ── MÉTHODE 1 : CHAIN LADDER ──────────────────────────────────────────────

    def _chain_ladder(
        self,
        C:        np.ndarray,
        facteurs: np.ndarray,
        f_cum:    np.ndarray,
        last_diag: np.ndarray,
        pct_dev:   np.ndarray,
        methode:   str,
        tail:      Dict,
    ) -> Dict:
        """
        Chain Ladder : projette le triangle avec les facteurs CL.
        Retourne ultimates, IBNR, réserve totale.
        """
        n, m = C.shape
        ultimates = np.zeros(n)
        ibnr      = np.zeros(n)

        for i in range(n):
            k = min(n - i - 1, m - 1)
            val = float(C[i, k])
            # Projeter jusqu'à la fin du développement
            for j in range(k, m - 1):
                if j < len(facteurs):
                    val *= facteurs[j]
            # Appliquer le tail
            val *= tail['tail_factor']
            ultimates[i] = val
            ibnr[i]      = max(val - last_diag[i], 0)

        reserve_totale = float(np.sum(ibnr[1:]))  # exclure année 0 (totalement développée)

        return {
            'ultimates':       [round(u, 2) for u in ultimates],
            'ibnr_par_annee':  [round(v, 2) for v in ibnr],
            'reserve_totale':  round(reserve_totale, 2),
            'reserve_best_estimate': round(reserve_totale, 2),
            'methode':         f'Chain Ladder ({methode})',
            'pct_developpe':   [round(p, 4) for p in pct_dev],
        }

    # ── MÉTHODE 2 : MACK 1993 ─────────────────────────────────────────────────

    def _mack_1993(
        self,
        C:             np.ndarray,
        facteurs:      np.ndarray,
        facteurs_indiv: List[List[float]],
        res_cl:        Dict,
    ) -> Dict:
        """
        Mack (1993) — extension stochastique du Chain Ladder.
        Calcule σ² par colonne → variance de réserve → IC 95%.

        Formule variance Mack :
        Var(R_i) = Σ_{j=k}^{n-2} C_i_j * sigma²_j / f_j²
        σ²_j = Σ C[i,j] * (f[i,j] - f_j)² / (n_j - 1)
        """
        n, m = C.shape

        # ── Variances par colonne σ²_j ────────────────────────────────────────
        sigma2 = np.zeros(m - 1)
        for j in range(m - 1):
            f_ind = facteurs_indiv[j]
            f_j   = facteurs[j]
            c_j   = []
            for i in range(n - j - 1):
                if i + j < n and C[i, j] > 0:
                    c_j.append(C[i, j])
                if len(c_j) > len(f_ind):
                    c_j = c_j[:len(f_ind)]

            n_j = len(f_ind)
            if n_j < 2 or len(c_j) < 2:
                # Extrapoler σ²_{n-2} depuis les colonnes précédentes
                if j > 0 and sigma2[j-1] > 0:
                    sigma2[j] = sigma2[j-1] * (facteurs[j] / max(facteurs[j-1], 1e-9))**2
                continue

            num = sum(c_j[k] * (f_ind[k] - f_j)**2 for k in range(min(n_j, len(c_j))))
            sigma2[j] = num / (n_j - 1)

        # ── Variance de réserve par année ─────────────────────────────────────
        ultimates = np.array(res_cl['ultimates'])
        ibnr      = np.array(res_cl['ibnr_par_annee'])
        var_r     = np.zeros(n)

        for i in range(1, n):
            k = min(n - i - 1, m - 1)
            v = 0.0
            c_ik = float(C[i, k])
            # Projections intermédiaires
            c_proj = c_ik
            for j in range(k, m - 1):
                if j < len(facteurs) and facteurs[j] > 0 and j < len(sigma2):
                    v += c_proj * sigma2[j] / max(facteurs[j]**2, 1e-12)
                    c_proj *= facteurs[j]
            var_r[i] = v

        sigma_par_annee = np.sqrt(np.maximum(var_r, 0))
        sigma_total     = float(np.sqrt(np.sum(var_r[1:])))
        reserve_be      = float(np.sum(ibnr[1:]))
        cv_mack         = sigma_total / max(reserve_be, 1e-6) * 100

        # Percentiles (approximation log-normale)
        if sigma_total > 0 and reserve_be > 0:
            mu_ln  = np.log(max(reserve_be, 1)) - 0.5 * np.log(1 + (sigma_total/reserve_be)**2)
            sig_ln = np.sqrt(np.log(1 + (sigma_total/reserve_be)**2))
            p75  = float(np.exp(mu_ln + 0.674 * sig_ln))
            p90  = float(np.exp(mu_ln + 1.282 * sig_ln))
            p995 = float(np.exp(mu_ln + 2.576 * sig_ln))
        else:
            p75 = p90 = p995 = reserve_be

        statut = 'VERT' if cv_mack < 5 else 'AMBRE' if cv_mack < 10 else 'ROUGE'

        return {
            'reserve_best_estimate': round(reserve_be, 2),
            'sigma_total':           round(sigma_total, 2),
            'sigma_par_annee':       [round(s, 2) for s in sigma_par_annee],
            'cv_pct':                round(cv_mack, 2),
            'reserve_p75':           round(p75, 2),
            'reserve_p90':           round(p90, 2),
            'reserve_p995':          round(p995, 2),
            'sigma2_par_colonne':    [round(s, 6) for s in sigma2],
            'statut':                statut,
            'methode':               'Mack (1993) — ASTIN Bulletin 23(2)',
            'message': (
                f"Mack : BE={reserve_be:,.0f}€ · σ={sigma_total:,.0f}€ · "
                f"CV={cv_mack:.1f}% · P90={p90:,.0f}€"
            ),
        }

    # ── MÉTHODE 3 : BORNHUETTER-FERGUSON ─────────────────────────────────────

    def _bornhuetter_ferguson(
        self,
        C:          np.ndarray,
        res_cl:     Dict,
        pcts_dev:   np.ndarray,
        last_diag:  np.ndarray,
        primes:     Optional[np.ndarray] = None,
        taux_manuel: Optional[float]     = None,
    ) -> Dict:
        """
        Bornhuetter-Ferguson (1972).

        Ultimate_BF[i] = C[i,last] + (1 - pct_dev[i]) × μ[i]

        où μ[i] = prime[i] × LR_apriori (a priori sinistres attendus)
        et pct_dev[i] = % déjà développé pour l'année i.

        LR a priori estimé sur les années les plus matures si pas fourni.
        """
        n, m       = C.shape
        ultimates_cl = np.array(res_cl['ultimates'])

        # ── Estimer le LR a priori ────────────────────────────────────────────
        if taux_manuel is not None:
            lr = float(taux_manuel)
            source_lr = 'manuel'
        elif primes is not None and len(primes) >= 3:
            # LR sur les 5 années les plus matures (les plus développées)
            nb = min(5, n // 2) if n >= 6 else min(3, n - 1)
            lr_annees = []
            for i in range(nb):
                p = float(primes[i])
                u = float(ultimates_cl[i])
                if p > 0 and u > 0:
                    lr_annees.append(u / p)
            lr = float(np.mean(lr_annees)) if lr_annees else 0.75
            source_lr = 'primes_fournies'
        else:
            # Estimer LR depuis les années matures du triangle
            # Méthode : LR proxy = (sinistres observés) / (exposition estimée)
            # Exposition ≈ premier sinistre × facteur de développement global
            nb = min(5, n // 2) if n >= 6 else min(3, n - 1)
            lr_annees = []
            for i in range(nb):
                c_ini  = float(C[i, 0]) if C[i, 0] > 0 else 1
                u      = float(ultimates_cl[i])
                # LR = ultime / (volume initial × ratio marché estimé à 0.70)
                # On estime la prime ≈ ultime / LR_marché_cible
                # Approche : LR basé sur le ratio développement
                if u > 0 and c_ini > 0:
                    # Facteur de développement total observé
                    fd_total = u / c_ini
                    # LR proxy : suppose que c_ini = prime × taux_sinistres_initial
                    # et fd_total = 1 / (% sinistres payés à la souscription)
                    lr_annees.append(min(fd_total * 0.35, 1.20))
            lr = float(np.mean(lr_annees)) if lr_annees else 0.75
            # Clamp à une plage raisonnable
            lr = float(np.clip(lr, 0.35, 1.20))
            source_lr = 'estime_triangle'

        # ── A priori μ[i] par année ───────────────────────────────────────────
        if primes is not None and len(primes) >= n:
            mu = np.array([float(primes[i]) * lr for i in range(n)])
        else:
            # Sans primes : μ = ultimate CL × lr / 1 (LR appliqué à l'exposure proxy)
            # Meilleure approche : μ proportionnel à la première diagonale
            exposure = np.array([float(C[i, 0]) if C[i, 0] > 0 else float(ultimates_cl[i]) * 0.3
                                  for i in range(n)])
            # Normaliser par le ratio ultime/première diagonale des années matures
            nb_mat = min(3, n - 1)
            ratio  = float(np.mean([
                ultimates_cl[i] / max(exposure[i], 1e-6) for i in range(nb_mat)
            ]))
            mu = exposure * ratio * lr

        # ── IBNR BF ───────────────────────────────────────────────────────────
        ibnr_bf    = np.zeros(n)
        ultimates_bf = np.zeros(n)
        for i in range(n):
            frac_ibnr    = max(1.0 - pcts_dev[i], 0.0)
            ibnr_bf[i]   = frac_ibnr * mu[i]
            ultimates_bf[i] = last_diag[i] + ibnr_bf[i]

        reserve_totale = float(np.sum(ibnr_bf[1:]))

        return {
            'lr_apriori':      round(lr, 4),
            'source_lr':       source_lr,
            'mu_par_annee':    [round(v, 2) for v in mu],
            'ibnr_par_annee':  [round(v, 2) for v in ibnr_bf],
            'ultimates':       [round(v, 2) for v in ultimates_bf],
            'reserve_totale':  round(reserve_totale, 2),
            'reserve_best_estimate': round(reserve_totale, 2),
            'methode':         'Bornhuetter-Ferguson (1972)',
            'message': (
                f"BF : réserve={reserve_totale:,.0f}€ · "
                f"LR={lr:.1%} ({source_lr})"
            ),
        }

    # ── MÉTHODE 4 : CAPE COD ──────────────────────────────────────────────────

    def _cape_cod(
        self,
        C:         np.ndarray,
        res_cl:    Dict,
        pcts_dev:  np.ndarray,
        last_diag: np.ndarray,
        primes:    Optional[np.ndarray] = None,
    ) -> Dict:
        """
        Cape Cod (Bühlmann & Straub) — LR homogène estimé depuis les données.

        LR_CC = Σ_i C[i,last_i] / Σ_i (prime[i] × pct_dev[i])

        Plus robuste que BF quand l'a priori est incertain.
        """
        n, m = C.shape

        # Exposition (primes ou proxy)
        if primes is not None and len(primes) >= n:
            expo = np.array([float(primes[i]) for i in range(n)])
        else:
            # Proxy : exposition = ultimate CL (approximation conservatrice)
            expo = np.array([float(res_cl['ultimates'][i]) for i in range(n)])

        # LR Cape Cod
        num = sum(float(last_diag[i]) for i in range(1, n))
        den = sum(float(expo[i]) * float(pcts_dev[i]) for i in range(1, n)
                  if expo[i] > 0 and pcts_dev[i] > 0)
        lr_cc = num / max(den, 1e-9)
        lr_cc = float(np.clip(lr_cc, 0.20, 2.0))  # sanity check

        # IBNR Cape Cod
        ibnr_cc    = np.zeros(n)
        ultimates_cc = np.zeros(n)
        for i in range(n):
            frac = max(1.0 - pcts_dev[i], 0.0)
            ibnr_cc[i]    = lr_cc * expo[i] * frac
            ultimates_cc[i] = last_diag[i] + ibnr_cc[i]

        reserve_totale = float(np.sum(ibnr_cc[1:]))

        return {
            'lr_cape_cod':     round(lr_cc, 4),
            'ibnr_par_annee':  [round(v, 2) for v in ibnr_cc],
            'ultimates':       [round(v, 2) for v in ultimates_cc],
            'reserve_totale':  round(reserve_totale, 2),
            'reserve_best_estimate': round(reserve_totale, 2),
            'methode':         'Cape Cod (Bühlmann & Straub)',
            'message': (
                f"Cape Cod : réserve={reserve_totale:,.0f}€ · "
                f"LR CC={lr_cc:.1%}"
            ),
        }

    # ── MÉTHODE 5 : BOOTSTRAP ODP ─────────────────────────────────────────────

    def _bootstrap_odp(
        self,
        C:             np.ndarray,
        facteurs_indiv: List[List[float]],
        n_sim:         int = 1000,
        seed:          int = 42,
    ) -> Dict:
        """
        Bootstrap ODP (England & Verrall 2002).

        Principe correct :
        1. Calculer les résidus des facteurs individuels par colonne
           r[i,j] = (f[i,j] - f_CL[j]) / sigma_j
        2. Simuler 1000 jeux de facteurs en rééchantillonnant ces résidus
        3. Pour chaque simulation → projeter le triangle → calculer la réserve
        4. Distribution empirique des 1000 réserves → P50/P75/P90/P99.5
        """
        np.random.seed(seed)
        n, m = C.shape

        # Facteurs CL standard (toujours standard pour Bootstrap)
        facteurs_cl = np.ones(m - 1)
        for j in range(m - 1):
            fi = facteurs_indiv[j] if j < len(facteurs_indiv) else []
            c_j = []
            for i in range(n - j - 1):
                if C[i, j] > 0 and C[i, j+1] > 0:
                    c_j.append(C[i, j])
            if c_j and fi:
                facteurs_cl[j] = max(
                    sum(f * w for f, w in zip(fi, c_j)) / max(sum(c_j), 1e-9),
                    1.0
                )

        # Résidus des facteurs individuels par colonne
        residus_all = []
        for j, fi in enumerate(facteurs_indiv):
            if len(fi) < 2:
                continue
            arr = np.array(fi)
            moy = facteurs_cl[j]
            std = float(np.std(arr))
            if std < 1e-8:
                # Triangle très régulier → estimer std depuis CV historique
                cv_estime = 0.05  # 5% de CV par défaut
                std = moy * cv_estime
            # Résidus normalisés
            residus_col = (arr - moy) / std
            residus_all.extend(residus_col.tolist())

        residus_all = np.array(residus_all) if residus_all else np.array([0.0])

        # Réserve CL de référence
        reserve_cl = 0.0
        for i in range(1, n):
            k = min(n - i - 1, m - 1)
            val = float(C[i, k])
            for j in range(k, m - 1):
                val *= facteurs_cl[j]
            reserve_cl += max(val - C[i, k], 0)

        # ── Simulations ────────────────────────────────────────────────────────
        reserves_sim = []
        for _ in range(n_sim):
            # Simuler des facteurs perturbés par colonne
            f_sim = facteurs_cl.copy()
            for j, fi in enumerate(facteurs_indiv):
                if len(fi) < 2 or j >= len(facteurs_cl):
                    continue
                arr = np.array(fi)
                std_j = float(np.std(arr))
                if std_j < 1e-8:
                    std_j = facteurs_cl[j] * 0.05
                # Tirer un résidu aléatoire
                res = np.random.choice(residus_all) if len(residus_all) > 1 else np.random.normal(0, 1)
                f_sim[j] = max(facteurs_cl[j] + res * std_j, 1.0)

            # Projeter avec ces facteurs simulés
            reserve_sim = 0.0
            for i in range(1, n):
                k = min(n - i - 1, m - 1)
                val = float(C[i, k])
                for j in range(k, m - 1):
                    if j < len(f_sim):
                        val *= f_sim[j]
                reserve_sim += max(val - C[i, k], 0)

            reserves_sim.append(reserve_sim)

        reserves_sim = np.array(reserves_sim)
        be_boot  = float(np.mean(reserves_sim))
        std_boot = float(np.std(reserves_sim))

        statut = 'VERT' if std_boot/max(be_boot,1) < 0.10 else 'AMBRE' if std_boot/max(be_boot,1) < 0.20 else 'ROUGE'

        return {
            'be_bootstrap':  round(be_boot, 2),
            'std_bootstrap': round(std_boot, 2),
            'cv_bootstrap':  round(std_boot / max(be_boot, 1e-6), 4),
            'p50':           round(float(np.percentile(reserves_sim, 50)), 2),
            'p75':           round(float(np.percentile(reserves_sim, 75)), 2),
            'p90':           round(float(np.percentile(reserves_sim, 90)), 2),
            'p95':           round(float(np.percentile(reserves_sim, 95)), 2),
            'p99_5':         round(float(np.percentile(reserves_sim, 99.5)), 2),
            'ic_95_inf':     round(float(np.percentile(reserves_sim, 2.5)), 2),
            'ic_95_sup':     round(float(np.percentile(reserves_sim, 97.5)), 2),
            'n_simulations': n_sim,
            'distribution':  reserves_sim.tolist(),
            'statut':        statut,
            'methode':       'Bootstrap ODP — England & Verrall (2002)',
            'message': (
                f"Bootstrap : BE={be_boot:,.0f}€ · "
                f"σ={std_boot:,.0f}€ · CV={std_boot/max(be_boot,1)*100:.1f}% · "
                f"P90={float(np.percentile(reserves_sim,90)):,.0f}€"
            ),
        }

    def _munich_cl(
        self,
        C_paye:   np.ndarray,
        C_engage: np.ndarray,
    ) -> Dict:
        """
        Munich Chain Ladder (Quarg & Mack 2004).
        Nécessite triangle payé ET triangle engagé (charges).
        """
        if C_engage is None or C_engage.shape != C_paye.shape:
            return {
                'disponible': False, 'statut': 'INFO',
                'message':    "Munich CL : triangle engagé requis.",
            }
        n = C_paye.shape[0]

        def fcl(C):
            f = np.ones(n - 1)
            for j in range(n - 1):
                num = sum(C[i, j+1] for i in range(n-j-1) if C[i,j] > 0 and C[i,j+1] > 0)
                den = sum(C[i, j]   for i in range(n-j-1) if C[i,j] > 0)
                f[j] = max(num/max(den,1e-9), 1.0)
            return f

        f_p = fcl(C_paye)
        f_e = fcl(C_engage)

        # Ratios Q = payé/engagé
        Q = np.zeros((n, n))
        for i in range(n):
            for j in range(min(n-i, n)):
                if C_engage[i,j] > 0:
                    Q[i,j] = C_paye[i,j] / C_engage[i,j]

        # Facteurs Munich ajustés
        f_m = f_p.copy()
        for j in range(n-1):
            qs = [Q[i,j] for i in range(n-j-1) if Q[i,j] > 0]
            if len(qs) >= 2 and f_e[j] > 0:
                q_moy = float(np.mean(qs))
                q_cl  = f_p[j] / f_e[j]
                lam   = min(abs(q_moy - q_cl) / max(q_cl, 1e-6), 0.3)
                f_m[j] = max(f_p[j] * (1 + lam * (q_moy/max(q_cl,1e-6) - 1)), 1.0)

        # Réserves
        r_m = r_s = 0.0
        for i in range(1, n):
            k = n - i - 1
            vm = vs = float(C_paye[i, k])
            for j in range(k, n-1):
                vm *= f_m[j]; vs *= f_p[j]
            r_m += max(vm - C_paye[i,k], 0)
            r_s += max(vs - C_paye[i,k], 0)

        ecart = (r_m - r_s) / max(r_s, 1e-6) * 100
        return {
            'disponible':         True,
            'be_munich':          round(r_m, 0),
            'be_standard':        round(r_s, 0),
            'ecart_munich_vs_cl': round(ecart, 1),
            'statut':  'VERT' if abs(ecart) < 10 else 'AMBRE' if abs(ecart) < 25 else 'ROUGE',
            'message': f"Munich CL : {r_m:,.0f}€ ({'+' if ecart>=0 else ''}{ecart:.1f}% vs CL)",
            'conseil': "Écart faible → CL fiable." if abs(ecart) < 10 else "Écart significatif → sur/sous-provisionnement dossier.",
            'methode': 'Munich Chain Ladder (Quarg & Mack 2004)',
        }



# ══════════════════════════════════════════════════════════════════════════════
# NIVEAU 4 — BEST ESTIMATE S2
# ══════════════════════════════════════════════════════════════════════════════

class BestEstimateS2:
    """
    Calcule le Best Estimate S2 avec :
    - Sélection des méthodes validées (score > 60)
    - Poids dynamiques selon scores N2
    - Documentation du jugement actuariel
    - Sensibilités
    """

    def calculer(
        self,
        n2: Dict,
        n3: Dict,
        C:  np.ndarray,
    ) -> Dict:
        """
        Entrée  : résultats N2 (scores) + N3 (réserves)
        Sortie  : BE, poids, sensibilités, jugement
        """
        scores  = n2.get('scores_confiance', {})
        cl_res  = n3['chain_ladder']['reserve_totale']
        mack_res= n3['mack']['reserve_best_estimate']
        bf_res  = n3['bf']['reserve_totale']
        cc_res  = n3['cape_cod']['reserve_totale']
        sigma   = n3['mack']['sigma_total']
        p90_mack= n3['mack']['reserve_p90']
        boot    = n3['bootstrap']

        # ── Sélection des méthodes validées ──────────────────────────────────
        seuil_score = 60
        methodes_dispo = {
            'chain_ladder': cl_res,
            'mack':         mack_res,
            'bf':           bf_res,
            'cape_cod':     cc_res,
        }

        methodes_incluses = {}
        methodes_exclues  = {}
        for m, r in methodes_dispo.items():
            s = scores.get(m, scores.get('mack_1993' if m == 'mack' else m, 70))
            if s >= seuil_score and r > 0:
                methodes_incluses[m] = (r, s)
            else:
                methodes_exclues[m]  = (r, s)

        # Si tout exclu → garder Mack et BF par défaut
        if not methodes_incluses:
            methodes_incluses = {
                'mack': (mack_res, 50),
                'bf':   (bf_res,   50),
            }

        # ── Poids dynamiques ─────────────────────────────────────────────────
        # Poids proportionnels aux scores de confiance
        total_scores = sum(s for _, s in methodes_incluses.values())
        poids = {
            m: round(s / max(total_scores, 1), 4)
            for m, (_, s) in methodes_incluses.items()
        }

        # ── Best Estimate ─────────────────────────────────────────────────────
        be = sum(
            poids[m] * r
            for m, (r, _) in methodes_incluses.items()
        )

        # ── Percentiles (log-normale Mack) ───────────────────────────────────
        if sigma > 0 and be > 0:
            mu_ln  = np.log(max(be, 1)) - 0.5 * np.log(1 + (sigma/be)**2)
            sig_ln = np.sqrt(np.log(1 + (sigma/be)**2))
            p75  = float(np.exp(mu_ln + 0.674 * sig_ln))
            p90  = float(np.exp(mu_ln + 1.282 * sig_ln))
            p995 = float(np.exp(mu_ln + 2.576 * sig_ln))
        else:
            p75 = p90 = p995 = be

        # ── CV inter-méthodes ─────────────────────────────────────────────────
        reserves_val = [r for r, _ in methodes_incluses.values()]
        cv_inter = float(np.std(reserves_val) / max(np.mean(reserves_val), 1e-6) * 100) if len(reserves_val) > 1 else 0

        # ── Sensibilités ─────────────────────────────────────────────────────
        sensibilites = {}
        for m_exclu in methodes_incluses:
            autres = {k: v for k, v in methodes_incluses.items() if k != m_exclu}
            if autres:
                tot = sum(s for _, s in autres.values())
                p_autres = {k: s/max(tot,1) for k, (_, s) in autres.items()}
                be_sans = sum(p_autres[k] * methodes_incluses[k][0] for k in autres)
                sensibilites[f'sans_{m_exclu}'] = round(be_sans, 0)

        # Fourchette Bootstrap
        if boot.get('p50', 0) > 0:
            sensibilites['boot_p10'] = round(boot.get('ic_95_inf', be * 0.85), 0)
            sensibilites['boot_p90'] = round(boot.get('p90', be * 1.15), 0)

        # ── Statut ───────────────────────────────────────────────────────────
        statut = 'VERT' if cv_inter < 5 else 'AMBRE' if cv_inter < 15 else 'ROUGE'

        # ── Jugement actuariel documenté ─────────────────────────────────────
        jugement = self._documenter_jugement(
            methodes_incluses, methodes_exclues, poids, be, cv_inter,
            n2, n3, statut
        )

        return {
            'best_estimate':       round(be, 0),
            'reserve_p75':         round(p75, 0),
            'reserve_p90':         round(p90, 0),
            'reserve_p99_5':       round(p995, 0),
            'sigma_mack':          round(sigma, 0),
            'cv_inter_methodes':   round(cv_inter, 2),
            'methodes_incluses':   list(methodes_incluses.keys()),
            'methodes_exclues':    list(methodes_exclues.keys()),
            'poids':               poids,
            'sensibilites':        sensibilites,
            'jugement':            jugement,
            'statut':              statut,
            'message': (
                f"BE S2 = {be:,.0f}€ · P90 = {p90:,.0f}€ · "
                f"CV = {cv_inter:.1f}% · σ = {sigma:,.0f}€"
            ),
        }

    def _documenter_jugement(
        self,
        incluses: Dict, exclues: Dict, poids: Dict,
        be: float, cv: float, n2: Dict, n3: Dict, statut: str
    ) -> str:
        """Génère le texte de jugement actuariel documenté."""

        methode_rec = n2.get('methode_recommandee', 'mack')
        raison_rec  = n2.get('raison_recommandation', '')
        h1_ok = n2.get('h1_independance', {}).get('ok', True)
        h2_ok = n2.get('h2_stabilite', {}).get('ok', True)

        lignes = [
            f"JUGEMENT ACTUARIEL — {datetime.now().strftime('%d/%m/%Y')}",
            "─" * 50,
            "",
            "1. MÉTHODES RETENUES",
        ]
        for m, (r, s) in incluses.items():
            lignes.append(
                f"   ✅ {m.replace('_',' ').title()} : "
                f"{r:,.0f}€ · poids={poids.get(m,0):.0%} · score={s}/100"
            )
        for m, (r, s) in exclues.items():
            lignes.append(
                f"   ❌ {m.replace('_',' ').title()} : "
                f"exclu (score={s}/100 < 60)"
            )

        lignes += [
            "",
            "2. VALIDATION DES HYPOTHÈSES",
            f"   H1 Indépendance : {'✅ validée' if h1_ok else '⚠️ rejetée'}",
            f"   H2 Stabilité    : {'✅ validée' if h2_ok else '⚠️ rejetée'}",
            f"   Méthode recommandée : {methode_rec}",
            f"   Raison : {raison_rec[:100]}",
            "",
            "3. BEST ESTIMATE S2",
            f"   BE retenu   : {be:,.0f} €",
            f"   CV méthodes : {cv:.1f}% "
            f"({'acceptable' if cv < 5 else 'à surveiller' if cv < 15 else 'élevé'})",
            "",
            "4. DÉCISION",
        ]

        if statut == 'VERT':
            lignes.append(
                "   Les méthodes convergent. BE retenu pour inscription au bilan S2."
            )
        elif statut == 'AMBRE':
            lignes.append(
                "   Divergence modérée entre méthodes. "
                "BE retenu sous réserve de validation par l'actuaire désigné."
            )
        else:
            lignes.append(
                "   Divergence importante. "
                "BE à valider impérativement par l'actuaire désigné avant signature."
            )

        return "\n".join(lignes)


# ══════════════════════════════════════════════════════════════════════════════
# NIVEAU 5 — LIVRABLES
# ══════════════════════════════════════════════════════════════════════════════

class LivrablesA7:
    """
    Produit tous les livrables :
    G1-G9 : graphiques Plotly style Power BI
    Commentaire actuariel structuré
    Rapport actuaire désigné
    Export Excel multi-onglets
    Audit trail JSON
    """

    LAYOUT_BASE = dict(
        paper_bgcolor=NAVY,
        plot_bgcolor=NAVY_L,
        font=dict(family="Inter, Arial", color=BLANC, size=11),
        margin=dict(l=50, r=30, t=60, b=50),
        height=380,
        hoverlabel=dict(bgcolor=NAVY_L, bordercolor=OR, font_size=12, font_color=BLANC),
    )

    # ── GRAPHIQUES ────────────────────────────────────────────────────────────

    def graphiques(self, C: np.ndarray, n2: Dict, n3: Dict, n4: Dict) -> Dict:
        """Génère les 9 graphiques si Plotly disponible."""
        if not PLOTLY_OK:
            return {}
        g = {}
        try: g['g1_heatmap']       = self._g1_heatmap(C)
        except Exception as e: logger.warning(f"G1 échoué : {e}")
        try: g['g2_facteurs_cl']   = self._g2_facteurs_cl(n3)
        except Exception as e: logger.warning(f"G2 échoué : {e}")
        try: g['g3_ibnr']          = self._g3_ibnr(n3)
        except Exception as e: logger.warning(f"G3 échoué : {e}")
        try: g['g4_convergence']   = self._g4_convergence(n3, n4)
        except Exception as e: logger.warning(f"G4 échoué : {e}")
        try: g['g5_bootstrap']     = self._g5_bootstrap(n3)
        except Exception as e: logger.warning(f"G5 échoué : {e}")
        try: g['g6_h1']            = self._g6_h1(n2)
        except Exception as e: logger.warning(f"G6 échoué : {e}")
        try: g['g7_h2']            = self._g7_h2(C, n3)
        except Exception as e: logger.warning(f"G7 échoué : {e}")
        try: g['g8_h3']            = self._g8_h3(n2)
        except Exception as e: logger.warning(f"G8 échoué : {e}")
        return g

    def _g1_heatmap(self, C: np.ndarray) -> 'go.Figure':
        """G1 — Heatmap triangle de développement."""
        n, m = C.shape
        z_show = []
        for i in range(n):
            row = []
            for j in range(m):
                if j <= n - i - 1 and C[i, j] > 0:
                    row.append(C[i, j])
                else:
                    row.append(None)
            z_show.append(row)

        labels_ann = [f"An. {i}" for i in range(n)]
        labels_dev = [f"Dév. {j}" for j in range(m)]

        fig = go.Figure(go.Heatmap(
            z=z_show,
            x=labels_dev,
            y=labels_ann,
            colorscale=[[0,'#1B3A5C'],[0.5,'#C9A84C'],[1,'#E74C3C']],
            showscale=True,
            hovertemplate="<b>%{y}</b> · %{x}<br>Montant : <b>%{z:,.0f} €</b><extra></extra>",
            colorbar=dict(tickfont=dict(color=BLANC, size=9)),
        ))
        fig.update_layout(
            **self.LAYOUT_BASE,
            title=dict(text="Triangle de développement — Zone connue", font=dict(color=BLANC, size=13), x=0.01),
            xaxis=dict(tickfont=dict(color=GRIS, size=9), showgrid=False),
            yaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False, autorange='reversed'),
        )
        return fig

    def _g2_facteurs_cl(self, n3: Dict) -> 'go.Figure':
        """G2 — Facteurs de développement avec bande ±2σ."""
        facteurs = n3.get('facteurs', [])
        if not facteurs:
            return None

        x = list(range(1, len(facteurs) + 1))
        f_arr = np.array(facteurs)
        moy   = float(np.mean(f_arr))
        std   = float(np.std(f_arr))

        colors = [
            ROUGE if abs(f - moy) > 2 * std else
            AMBRE if abs(f - moy) > std else
            OR
            for f in facteurs
        ]

        fig = go.Figure()
        # Bande ±2σ
        fig.add_trace(go.Scatter(
            x=x + x[::-1],
            y=[moy + 2*std]*len(x) + [moy - 2*std]*len(x),
            fill='toself',
            fillcolor='rgba(201,168,76,0.1)',
            line=dict(color='rgba(0,0,0,0)'),
            name='±2σ',
            showlegend=True,
        ))
        # Ligne médiane
        fig.add_hline(y=moy, line_color=OR, line_dash='dash', line_width=1,
                      annotation_text=f"Moy={moy:.3f}", annotation_font=dict(color=OR, size=10))
        # Barres
        fig.add_trace(go.Bar(
            x=x, y=facteurs,
            marker_color=colors,
            marker_line=dict(color=NAVY, width=1),
            width=0.5,
            name='Facteurs',
            hovertemplate="<b>Période %{x}</b><br>Facteur : <b>%{y:.4f}</b><extra></extra>",
        ))
        fig.update_layout(
            **self.LAYOUT_BASE,
            title=dict(text="Facteurs de développement Chain Ladder ±2σ", font=dict(color=BLANC, size=13), x=0.01),
            xaxis=dict(title="Période de développement", tickfont=dict(color=GRIS, size=10), showgrid=False),
            yaxis=dict(title="Facteur", tickfont=dict(color=GRIS, size=10), showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
            barmode='overlay',
            showlegend=True,
            legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color=BLANC, size=10)),
        )
        return fig

    def _g3_ibnr(self, n3: Dict) -> 'go.Figure':
        """G3 — IBNR par année (barplot horizontal, années sur Y, IBNR sur X)."""
        ibnr = n3['chain_ladder'].get('ibnr_par_annee', [])
        if not ibnr:
            return None

        n = len(ibnr)
        labels = [f"An. {i}" for i in range(n)]
        vals   = [max(v, 0) for v in ibnr]
        max_v  = max(vals) if vals else 1

        colors = [
            f'rgba({int(226*(v/max_v))},{int(204*(1-v/max_v))},{int(76*(1-v/max_v))},0.85)'
            for v in vals
        ]

        fig = go.Figure(go.Bar(
            y=labels,
            x=vals,
            orientation='h',
            marker_color=colors,
            marker_line=dict(color=NAVY, width=0.5),
            text=[f"{v:,.0f} €" if v > 0 else "" for v in vals],
            textposition='outside',
            textfont=dict(color=BLANC, size=9),
            hovertemplate="<b>%{y}</b><br>IBNR : <b>%{x:,.0f} €</b><extra></extra>",
        ))
        fig.update_layout(
            **self.LAYOUT_BASE,
            height=max(350, n * 22),
            title=dict(text="IBNR par année de survenance", font=dict(color=BLANC, size=13), x=0.01),
            xaxis=dict(title="IBNR (€)", tickfont=dict(color=GRIS, size=9), showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False, autorange='reversed'),
        )
        return fig

    def _g4_convergence(self, n3: Dict, n4: Dict) -> 'go.Figure':
        """G4 — Convergence des méthodes avec BE S2 et IC Mack."""
        labels = ['Chain Ladder', 'Mack 1993', 'BF', 'Cape Cod', 'BE S2']
        values = [
            n3['chain_ladder']['reserve_totale'],
            n3['mack']['reserve_best_estimate'],
            n3['bf']['reserve_totale'],
            n3['cape_cod']['reserve_totale'],
            n4['best_estimate'],
        ]
        colors = [OR, BLEU, VERT, GRIS, '#E74C3C']

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=values,
            marker_color=colors,
            marker_line=dict(color=NAVY, width=1),
            width=0.5,
            text=[f"{v:,.0f}€" for v in values],
            textposition='outside',
            textfont=dict(color=BLANC, size=10),
            hovertemplate="<b>%{x}</b><br>Réserve : <b>%{y:,.0f} €</b><extra></extra>",
        ))
        # IC Mack
        be_mack = n3['mack']['reserve_best_estimate']
        p90     = n3['mack']['reserve_p90']
        sigma   = n3['mack']['sigma_total']
        fig.add_trace(go.Scatter(
            x=['Mack 1993', 'Mack 1993'],
            y=[be_mack - sigma, p90],
            mode='lines+markers',
            line=dict(color=BLANC, width=2, dash='dot'),
            marker=dict(size=8, color=BLANC),
            name='IC Mack 95%',
        ))
        # Ligne BE
        fig.add_hline(y=n4['best_estimate'], line_color='#E74C3C',
                      line_dash='dash', line_width=2,
                      annotation_text=f"BE S2 = {n4['best_estimate']:,.0f}€",
                      annotation_font=dict(color='#E74C3C', size=11))
        fig.update_layout(
            **self.LAYOUT_BASE,
            title=dict(text="Convergence des 4 méthodes actuarielles", font=dict(color=BLANC, size=13), x=0.01),
            xaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
            yaxis=dict(title="Réserve (€)", tickfont=dict(color=GRIS, size=10), showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
            showlegend=True,
            legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color=BLANC, size=10)),
        )
        return fig

    def _g5_bootstrap(self, n3: Dict) -> 'go.Figure':
        """G5 — Distribution Bootstrap avec P50/P75/P90/P99.5."""
        boot = n3.get('bootstrap', {})
        dist = boot.get('distribution', [])
        if not dist or len(set([round(v) for v in dist])) < 10:
            return None

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=dist, nbinsx=50,
            marker_color=f'rgba(201,168,76,0.7)',
            marker_line=dict(color=NAVY, width=0.5),
            name='Simulations',
        ))
        for p, lbl, clr in [
            (boot.get('p50',0),   'P50',   VERT),
            (boot.get('p75',0),   'P75',   AMBRE),
            (boot.get('p90',0),   'P90',   '#F39C12'),
            (boot.get('p99_5',0), 'P99.5', ROUGE),
        ]:
            if p > 0:
                fig.add_vline(x=p, line_color=clr, line_width=2, line_dash='dash',
                              annotation_text=f"{lbl}={p:,.0f}€",
                              annotation_font=dict(color=clr, size=10))
        fig.update_layout(
            **self.LAYOUT_BASE,
            title=dict(text="Bootstrap ODP — Distribution des réserves (1 000 simulations)", font=dict(color=BLANC, size=13), x=0.01),
            xaxis=dict(title="Réserve IBNR (€)", tickfont=dict(color=GRIS, size=10), showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(title="Fréquence", tickfont=dict(color=GRIS, size=10), showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
            showlegend=False,
        )
        return fig

    def _g6_h1(self, n2: Dict) -> 'go.Figure':
        """G6 — H1 Indépendance : scatter f[j] vs f[j+1]."""
        details = n2.get('h1_independance', {}).get('details', [])
        if not details:
            return None

        corr_moy = n2['h1_independance'].get('corr_moy', 0)
        ok       = n2['h1_independance'].get('ok', True)
        color_pt = VERT if ok else ROUGE

        x_vals = [d.get('corr', 0) for d in details]
        labels = [d.get('colonnes', '') for d in details]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=[abs(c) for c in x_vals],
            marker_color=[ROUGE if abs(c) > 0.5 else AMBRE if abs(c) > 0.3 else VERT for c in x_vals],
            marker_line=dict(color=NAVY, width=1),
            hovertemplate="<b>%{x}</b><br>|Corr| = <b>%{y:.3f}</b><extra></extra>",
        ))
        fig.add_hline(y=0.5, line_color=ROUGE, line_dash='dash', line_width=1,
                      annotation_text="Seuil H1 (0.50)",
                      annotation_font=dict(color=ROUGE, size=10))
        fig.update_layout(
            **self.LAYOUT_BASE,
            title=dict(
                text=f"H1 Indépendance : {'✅ VALIDÉE' if ok else '⚠️ REJETÉE'} — Corrélation moy={corr_moy:.3f}",
                font=dict(color=VERT if ok else ROUGE, size=13), x=0.01
            ),
            xaxis=dict(tickfont=dict(color=GRIS, size=9), showgrid=False),
            yaxis=dict(title="|Corrélation Spearman|", tickfont=dict(color=GRIS, size=10),
                       showgrid=True, gridcolor='rgba(255,255,255,0.05)', range=[0, 1]),
        )
        return fig

    def _g7_h2(self, C: np.ndarray, n3: Dict) -> 'go.Figure':
        """G7 — H2 Stabilité : heatmap des facteurs individuels."""
        n, m = C.shape
        facteurs_indiv = n3.get('facteurs_indiv', [])
        facteurs_cl    = n3.get('facteurs', [])
        if not facteurs_indiv:
            return None

        # Matrice des écarts : (f_ind - f_CL) / f_CL
        max_j = min(len(facteurs_indiv), m-1, 15)
        max_i = min(n, 15)
        z = []
        for i in range(max_i):
            row = []
            for j in range(max_j):
                fi = facteurs_indiv[j] if j < len(facteurs_indiv) else []
                fcl = facteurs_cl[j] if j < len(facteurs_cl) else 1
                if i < len(fi) and fcl > 0:
                    ecart = (fi[i] - fcl) / fcl * 100
                    row.append(round(ecart, 2))
                else:
                    row.append(None)
            z.append(row)

        fig = go.Figure(go.Heatmap(
            z=z,
            x=[f"j={j}" for j in range(max_j)],
            y=[f"i={i}" for i in range(max_i)],
            colorscale=[[0, ROUGE], [0.35, AMBRE], [0.5, NAVY_L], [0.65, AMBRE], [1, VERT]],
            zmid=0,
            colorbar=dict(title="Écart %", tickfont=dict(color=BLANC, size=9)),
            hovertemplate="<b>Année %{y}, Col %{x}</b><br>Écart vs CL : <b>%{z:.1f}%</b><extra></extra>",
        ))
        fig.update_layout(
            **self.LAYOUT_BASE,
            title=dict(text="H2 Stabilité — Écart des facteurs individuels vs CL (%)", font=dict(color=BLANC, size=13), x=0.01),
            xaxis=dict(tickfont=dict(color=GRIS, size=9)),
            yaxis=dict(tickfont=dict(color=BLANC, size=9), autorange='reversed'),
        )
        return fig

    def _g8_h3(self, n2: Dict) -> 'go.Figure':
        """G8 — H3 LR a priori BF."""
        h3  = n2.get('h3_apriori_bf', {})
        lr  = h3.get('lr_apriori', 0)
        ok  = h3.get('ok', True)
        src = h3.get('source', '')

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=['LR A Priori BF'],
            y=[lr * 100],
            marker_color=VERT if ok else AMBRE,
            marker_line=dict(color=NAVY, width=1),
            width=0.3,
            text=[f"{lr:.1%}"],
            textposition='outside',
            textfont=dict(color=BLANC, size=12),
        ))
        for seuil, lbl, clr in [(30, "Min (30%)", ROUGE), (75, "Marché (75%)", VERT), (150, "Max (150%)", ROUGE)]:
            fig.add_hline(y=seuil, line_color=clr, line_dash='dot', line_width=1,
                          annotation_text=lbl, annotation_font=dict(color=clr, size=10))
        fig.update_layout(
            **self.LAYOUT_BASE,
            height=300,
            title=dict(
                text=f"H3 LR A Priori BF = {lr:.1%} ({src}) — {'✅' if ok else '⚠️'}",
                font=dict(color=VERT if ok else AMBRE, size=13), x=0.01
            ),
            xaxis=dict(showticklabels=False),
            yaxis=dict(title="Loss Ratio (%)", tickfont=dict(color=GRIS, size=10),
                       showgrid=True, gridcolor='rgba(255,255,255,0.05)', range=[0, 200]),
        )
        return fig

    # ── COMMENTAIRE ACTUARIEL ─────────────────────────────────────────────────

    def commentaire(self, n1: Dict, n2: Dict, n3: Dict, n4: Dict) -> str:
        """Commentaire actuariel structuré en 5 sections."""
        be    = n4['best_estimate']
        cv    = n4['cv_inter_methodes']
        p90   = n4['reserve_p90']
        sigma = n4['sigma_mack']
        cl    = n3['chain_ladder']['reserve_totale']
        mack  = n3['mack']['reserve_best_estimate']
        bf    = n3['bf']['reserve_totale']
        cc    = n3['cape_cod']['reserve_totale']
        lr_bf = n3['bf']['lr_apriori']
        lr_cc = n3['cape_cod']['lr_cape_cod']
        meth  = n3['methode_cl']
        h1_ok = n2['h1_independance']['ok']
        h2_ok = n2['h2_stabilite']['ok']
        taille= n1['taille']
        statut= n4['statut']
        emoji = '🟢' if statut == 'VERT' else '🟡' if statut == 'AMBRE' else '🔴'

        sections = [
            f"{emoji} RAPPORT DE PROVISIONNEMENT — {datetime.now().strftime('%d/%m/%Y')}",
            f"Triangle : {taille} | Méthode CL : {meth}",
            "═" * 60,
            "",
            "■ 1. RÉSULTATS",
            f"   Best Estimate S2 (Art. 77)  : {be:>15,.0f} €",
            f"   Provision prudentielle P75   : {n4['reserve_p75']:>15,.0f} €",
            f"   Provision stress test P90    : {p90:>15,.0f} €",
            f"   Provision extrême P99.5      : {n4['reserve_p99_5']:>15,.0f} €",
            f"   Incertitude Mack (σ)         : {sigma:>15,.0f} €",
            f"   CV inter-méthodes            : {cv:>14.1f} %",
            "",
            "■ 2. DÉTAIL PAR MÉTHODE",
            f"   Chain Ladder ({meth})  : {cl:>12,.0f} €",
            f"   Mack 1993 (stochastique)     : {mack:>12,.0f} €",
            f"   Bornhuetter-Ferguson (LR={lr_bf:.0%}): {bf:>9,.0f} €",
            f"   Cape Cod (LR CC={lr_cc:.0%})       : {cc:>11,.0f} €",
            f"   Bootstrap P50 / P90          : {n3['bootstrap'].get('p50',0):>6,.0f} € / {n3['bootstrap'].get('p90',0):>6,.0f} €",
            "",
            "■ 3. VALIDATION DES HYPOTHÈSES",
        ]

        if h1_ok and h2_ok:
            sections.append(
                "   H1 et H2 validées — Chain Ladder approprié. "
                "Les méthodes CL et Mack sont fiables sur ce triangle."
            )
        elif not h1_ok:
            sections.append(
                f"   H1 rejetée (corrélation={n2['h1_independance']['corr_moy']:.2f}) — "
                "années de survenance dépendantes. "
                "Bornhuetter-Ferguson retenu comme méthode principale."
            )
        elif not h2_ok:
            sections.append(
                f"   H2 rejetée (CV={n2['h2_stabilite']['cv_moy']:.1%}) — "
                "facteurs instables dans le temps. "
                f"Méthode robuste ({meth}) appliquée automatiquement."
            )

        sections += [
            "",
            "■ 4. ANALYSE",
        ]

        ecart_cl_bf = abs(cl - bf) / max(cl, 1e-6) * 100
        if ecart_cl_bf < 5:
            sections.append(
                f"   Excellente convergence CL/BF ({ecart_cl_bf:.1f}%) — "
                "triangle long et bien développé. Provisionnement fiable."
            )
        elif ecart_cl_bf < 15:
            sections.append(
                f"   Convergence acceptable CL/BF ({ecart_cl_bf:.1f}%). "
                "Écart dans les normes du marché."
            )
        else:
            sections.append(
                f"   Divergence CL/BF = {ecart_cl_bf:.1f}% — "
                "à analyser. Les années récentes ont peu de développement "
                "→ BF plus fiable sur ces années."
            )

        # Tail factor
        tail = n3['tail_factor']['tail_factor']
        if tail > 1.01:
            sections.append(
                f"   Tail factor = {tail:.4f} (+{(tail-1)*100:.2f}%) — "
                "provisions additionnelles pour développement résiduel."
            )
        else:
            sections.append("   Tail factor ≈ 1.000 — développement considéré complet.")

        sections += [
            "",
            "■ 5. RECOMMANDATIONS",
        ]

        if statut == 'VERT':
            sections += [
                f"   → Inscrire {be:,.0f}€ au bilan S2 (Art. 77 DAS).",
                f"   → Utiliser {p90:,.0f}€ pour le calcul du SCR provisions.",
                "   → Documenter la méthodologie dans le rapport actuaire désigné.",
                "   → Revue trimestrielle recommandée.",
            ]
        elif statut == 'AMBRE':
            sections += [
                f"   → BE de {be:,.0f}€ utilisable sous réserve de validation.",
                "   → Faire valider par l'actuaire désigné avant signature du bilan.",
                "   → Constituer une provision de risque complémentaire si CV > 10%.",
                "   → Documenter les points d'attention dans le dossier actuariel.",
            ]
        else:
            sections += [
                "   → NE PAS utiliser ce BE sans correction actuarielle.",
                "   → Consulter l'actuaire désigné impérativement.",
                "   → Vérifier la qualité des données source (triangle / sinistres bruts).",
            ]

        return "\n".join(sections)

    # ── EXPORT EXCEL ──────────────────────────────────────────────────────────

    def export_excel(
        self, C: np.ndarray, n2: Dict, n3: Dict, n4: Dict, ref_client: str = ""
    ) -> bytes:
        """Génère un fichier Excel multi-onglets en mémoire."""
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:

                # Onglet 1 : Triangle brut
                n, m = C.shape
                df_tri = pd.DataFrame(
                    C,
                    index=[f"An.{i}" for i in range(n)],
                    columns=[f"Dév.{j}" for j in range(m)]
                )
                df_tri.to_excel(writer, sheet_name='Triangle brut')

                # Onglet 2 : Facteurs CL
                facteurs = n3.get('facteurs', [])
                df_f = pd.DataFrame({
                    'Période':        list(range(1, len(facteurs)+1)),
                    'Facteur CL':     facteurs,
                    'Facteur cumulé': n3.get('facteurs_cumules', [])[:len(facteurs)],
                })
                df_f.to_excel(writer, sheet_name='Facteurs CL', index=False)

                # Onglet 3 : Résultats 4 méthodes
                df_res = pd.DataFrame([
                    {'Méthode': 'Chain Ladder',   'Réserve (€)': n3['chain_ladder']['reserve_totale'],   'Poids BE': n4['poids'].get('chain_ladder', 0)},
                    {'Méthode': 'Mack 1993',       'Réserve (€)': n3['mack']['reserve_best_estimate'],     'Poids BE': n4['poids'].get('mack', 0)},
                    {'Méthode': 'BF',              'Réserve (€)': n3['bf']['reserve_totale'],              'Poids BE': n4['poids'].get('bf', 0)},
                    {'Méthode': 'Cape Cod',        'Réserve (€)': n3['cape_cod']['reserve_totale'],        'Poids BE': n4['poids'].get('cape_cod', 0)},
                    {'Méthode': 'BEST ESTIMATE S2','Réserve (€)': n4['best_estimate'],                     'Poids BE': 1.0},
                ])
                df_res.to_excel(writer, sheet_name='Résultats méthodes', index=False)

                # Onglet 4 : IBNR par année
                ibnr = n3['chain_ladder'].get('ibnr_par_annee', [])
                ult  = n3['chain_ladder'].get('ultimates', [])
                df_ibnr = pd.DataFrame({
                    'Année': [f"An.{i}" for i in range(len(ibnr))],
                    'IBNR CL (€)': ibnr,
                    'Ultimate CL (€)': ult,
                    'IBNR BF (€)': n3['bf'].get('ibnr_par_annee', [])[:len(ibnr)],
                })
                df_ibnr.to_excel(writer, sheet_name='IBNR par année', index=False)

                # Onglet 5 : Validation hypothèses
                h1 = n2['h1_independance']
                h2 = n2['h2_stabilite']
                h3 = n2['h3_apriori_bf']
                h4 = n2['h4_homosc_bootstrap']
                df_hyp = pd.DataFrame([
                    {'Hypothèse': 'H1 Indépendance', 'Validée': h1['ok'], 'Score': h1['score'], 'Détail': h1['message']},
                    {'Hypothèse': 'H2 Stabilité',    'Validée': h2['ok'], 'Score': h2['score'], 'Détail': h2['message']},
                    {'Hypothèse': 'H3 A priori BF',  'Validée': h3['ok'], 'Score': h3['score'], 'Détail': h3['message']},
                    {'Hypothèse': 'H4 Homoscédast.', 'Validée': h4['ok'], 'Score': h4['score'], 'Détail': h4['message']},
                ])
                df_hyp.to_excel(writer, sheet_name='Validation hypothèses', index=False)

                # Onglet 6 : Bootstrap
                boot = n3.get('bootstrap', {})
                df_boot = pd.DataFrame([
                    {'Percentile': 'P50',   'Réserve (€)': boot.get('p50', 0)},
                    {'Percentile': 'P75',   'Réserve (€)': boot.get('p75', 0)},
                    {'Percentile': 'P90',   'Réserve (€)': boot.get('p90', 0)},
                    {'Percentile': 'P99.5', 'Réserve (€)': boot.get('p99_5', 0)},
                    {'Percentile': 'Moyenne', 'Réserve (€)': boot.get('be_bootstrap', 0)},
                    {'Percentile': 'Écart-type', 'Réserve (€)': boot.get('std_bootstrap', 0)},
                ])
                df_boot.to_excel(writer, sheet_name='Bootstrap ODP', index=False)

                # Onglet 7 : Rapport synthèse
                df_synth = pd.DataFrame([
                    {'Indicateur': 'Best Estimate S2',    'Valeur': n4['best_estimate']},
                    {'Indicateur': 'Provision P75',       'Valeur': n4['reserve_p75']},
                    {'Indicateur': 'Provision P90',       'Valeur': n4['reserve_p90']},
                    {'Indicateur': 'Provision P99.5',     'Valeur': n4['reserve_p99_5']},
                    {'Indicateur': 'Sigma Mack',          'Valeur': n4['sigma_mack']},
                    {'Indicateur': 'CV inter-méthodes %', 'Valeur': n4['cv_inter_methodes']},
                    {'Indicateur': 'Méthode CL',          'Valeur': n3['methode_cl']},
                    {'Indicateur': 'Tail Factor',         'Valeur': n3['tail_factor']['tail_factor']},
                    {'Indicateur': 'Référence client',    'Valeur': ref_client},
                    {'Indicateur': 'Date',                'Valeur': datetime.now().strftime('%d/%m/%Y %H:%M')},
                ])
                df_synth.to_excel(writer, sheet_name='Rapport synthèse', index=False)

            return output.getvalue()

        except Exception as e:
            logger.warning(f"Export Excel échoué : {e}")
            return b''

    # ── AUDIT TRAIL JSON ──────────────────────────────────────────────────────

    def audit_trail(
        self,
        audit_id: str,
        n1: Dict, n2: Dict, n3: Dict, n4: Dict,
        statut: str,
        t_debut: datetime,
        ref_client: str = "",
    ) -> Dict:
        """Génère l'audit trail complet."""
        return {
            'audit_id':    audit_id,
            'ref_client':  ref_client,
            'date':        datetime.now().isoformat(),
            'duree_sec':   (datetime.now() - t_debut).total_seconds(),
            'statut':      statut,
            'n1_resume': {
                'taille':  n1.get('taille'),
                'mode':    n1.get('mode'),
                'alertes': n1.get('alertes', []),
            },
            'n2_resume': {
                'h1_ok':    n2['h1_independance']['ok'],
                'h2_ok':    n2['h2_stabilite']['ok'],
                'methode_cl': n2.get('methode_cl_retenue'),
                'methode_recommandee': n2.get('methode_recommandee'),
            },
            'n3_resume': {
                'cl':    n3['chain_ladder']['reserve_totale'],
                'mack':  n3['mack']['reserve_best_estimate'],
                'bf':    n3['bf']['reserve_totale'],
                'cc':    n3['cape_cod']['reserve_totale'],
                'boot_p90': n3['bootstrap'].get('p90', 0),
            },
            'n4_resume': {
                'best_estimate': n4['best_estimate'],
                'p90':           n4['reserve_p90'],
                'cv':            n4['cv_inter_methodes'],
                'poids':         n4['poids'],
                'methodes_incluses': n4['methodes_incluses'],
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE — AgentA7Provisionnement
# ══════════════════════════════════════════════════════════════════════════════

class AgentA7Provisionnement:
    """
    Agent A7 — Provisionnement actuariel Non-Vie.

    Usage :
        a7 = AgentA7Provisionnement(audit_path='/tmp', models_path='/tmp')
        result = a7.run(source=mon_triangle)
        result = a7.run(source=df_sinistres_bruts, primes=vecteur_primes)
        result = a7.run(source=fichier.xlsx, triangle_engage=engage.xlsx)
    """

    def __init__(
        self,
        models_path: str = '/tmp/actuaria',
        audit_path:  str = '/tmp/actuaria',
        verbose:     bool = True,
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

        # Sous-modules
        self._tv  = TriangleValidator(verbose=verbose)
        self._hv  = HypothesesValidator()
        self._ma  = MethodesActuarielles()
        self._be  = BestEstimateS2()
        self._liv = LivrablesA7()

    def run(
        self,
        # ── Entrée données ────────────────────────────────────────────────────
        source                = None,
        triangle_engage       = None,
        primes                = None,
        # ── Paramètres client ────────────────────────────────────────────────
        methode_cl:     str   = 'auto',
        taux_bf_manuel: Optional[float] = None,
        annees_a_exclure: Optional[List[int]] = None,
        ref_client:     str   = '',
        # ── Options ──────────────────────────────────────────────────────────
        n_sim_bootstrap: int  = 1000,
        generer_graphiques: bool = True,
        seed:           int   = 42,
        # ── Compatibilité ancienne API ────────────────────────────────────────
        triangle        = None,
        result_a2       = None,
        mode_declare:   str   = 'auto',
        **kwargs,
    ) -> Dict:
        """
        Pipeline complet N1 → N2 → N3 → N4 → N5.

        Paramètres client acceptés :
        - methode_cl     : 'auto' laisse A7 choisir selon hypothèses
        - taux_bf_manuel : Loss Ratio a priori BF (ex: 0.72 = 72%)
        - annees_a_exclure : liste d'indices d'années à exclure manuellement
        - ref_client     : référence dossier (pour le rapport)
        - n_sim_bootstrap: nb simulations (défaut 1000, min 200)
        """
        t_debut  = datetime.now()
        audit_id = f"A7_{t_debut.strftime('%Y%m%d_%H%M%S')}"

        if self.verbose:
            logger.info(f"[{audit_id}] Agent A7 Provisionnement v4.0 démarré")

        try:
            # ── Compatibilité ancienne API ────────────────────────────────────
            if source is None:
                if triangle is not None:
                    source = triangle
                elif result_a2 is not None:
                    source = result_a2
                else:
                    raise ValueError(
                        "Aucune donnée fournie. "
                        "Passez source=votre_triangle ou source=df_sinistres."
                    )

            # ════════════════════════════════════════════════════════════════
            # NIVEAU 1 — INGESTION
            # ════════════════════════════════════════════════════════════════
            if self.verbose:
                logger.info("N1 — Ingestion & validation du triangle")

            C, C_engage, primes_norm, n1_rapport = self._tv.charger(
                source         = source,
                mode           = mode_declare,
                triangle_engage= triangle_engage,
                primes         = primes,
            )

            n, m = C.shape
            n1 = {
                **n1_rapport,
                'C':     C,
                'C_engage': C_engage,
                'primes':   primes_norm,
            }

            # Appliquer exclusions manuelles si demandées
            if annees_a_exclure:
                C_calc = np.delete(C, annees_a_exclure, axis=0)
                n1['infos'].append(
                    f"ℹ️ {len(annees_a_exclure)} année(s) exclue(s) manuellement"
                )
            else:
                C_calc = C

            if self.verbose:
                logger.info(f"N1 OK — Triangle {n}×{m} | statut={n1['statut']}")

            # ════════════════════════════════════════════════════════════════
            # NIVEAU 2 — HYPOTHÈSES
            # ════════════════════════════════════════════════════════════════
            if self.verbose:
                logger.info("N2 — Validation des hypothèses H1/H2/H3/H4")

            n2 = self._hv.valider(C_calc, primes_norm)

            # Déterminer la méthode CL à utiliser
            if methode_cl == 'auto':
                methode_cl_retenue = n2['methode_cl_retenue'] if 'methode_cl_retenue' in n2 else self._choisir_methode_cl(n2)
            else:
                methode_cl_retenue = methode_cl

            n2['methode_cl_retenue'] = methode_cl_retenue

            # Avertissement si hypothèses ROUGE
            if n2['statut_global'] == 'ROUGE':
                n2['alertes'].insert(0,
                    "🔴 HYPOTHÈSES NON VALIDÉES — Résultats à interpréter avec "
                    "prudence. Validation actuaire désigné requise avant tout usage."
                )

            if self.verbose:
                logger.info(
                    f"N2 OK — H1={'✅' if n2['h1_independance']['ok'] else '❌'} "
                    f"H2={'✅' if n2['h2_stabilite']['ok'] else '❌'} "
                    f"méthode={methode_cl_retenue}"
                )

            # ════════════════════════════════════════════════════════════════
            # NIVEAU 3 — MÉTHODES
            # ════════════════════════════════════════════════════════════════
            if self.verbose:
                logger.info(f"N3 — Calcul des méthodes ({methode_cl_retenue})")

            n3 = self._ma.calculer_tout(
                C              = C_calc,
                methode_cl     = methode_cl_retenue,
                taux_bf_manuel = taux_bf_manuel,
                primes         = primes_norm,
                n_sim_boot     = max(200, n_sim_bootstrap),
                seed           = seed,
            )

            # Munich CL si triangle engagé disponible
            if C_engage is not None:
                n3['munich_cl'] = self._ma._munich_cl(C_calc, C_engage)
            else:
                n3['munich_cl'] = {
                    'disponible': False,
                    'statut':     'INFO',
                    'message':    "Munich CL non calculé — triangle engagé (charges) non fourni.",
                    'conseil':    "Fournissez le paramètre triangle_engage= pour activer Munich CL.",
                }

            if self.verbose:
                logger.info(
                    f"N3 OK — CL={n3['chain_ladder']['reserve_totale']:,.0f}€ "
                    f"Mack={n3['mack']['reserve_best_estimate']:,.0f}€ "
                    f"BF={n3['bf']['reserve_totale']:,.0f}€"
                )

            # ════════════════════════════════════════════════════════════════
            # NIVEAU 4 — BEST ESTIMATE
            # ════════════════════════════════════════════════════════════════
            if self.verbose:
                logger.info("N4 — Best Estimate S2")

            n4 = self._be.calculer(n2, n3, C_calc)

            if self.verbose:
                logger.info(
                    f"N4 OK — BE={n4['best_estimate']:,.0f}€ "
                    f"P90={n4['reserve_p90']:,.0f}€ "
                    f"CV={n4['cv_inter_methodes']:.1f}%"
                )

            # ════════════════════════════════════════════════════════════════
            # NIVEAU 5 — LIVRABLES
            # ════════════════════════════════════════════════════════════════
            if self.verbose:
                logger.info("N5 — Génération des livrables")

            # Graphiques
            graphiques = {}
            if generer_graphiques and PLOTLY_OK:
                graphiques = self._liv.graphiques(C_calc, n2, n3, n4)

            # Commentaire
            commentaire = self._liv.commentaire(n1, n2, n3, n4)

            # Excel
            excel_bytes = self._liv.export_excel(C_calc, n2, n3, n4, ref_client)

            # Audit trail
            audit = self._liv.audit_trail(
                audit_id, n1, n2, n3, n4,
                n4['statut'], t_debut, ref_client
            )

            # Sauvegarder audit
            self._sauvegarder_audit(audit_id, audit)

            # Statut final
            statut_rag = n4['statut']
            if n1['statut'] == 'ROUGE' or n2['statut_global'] == 'ROUGE':
                statut_rag = 'ROUGE'
            elif n1['statut'] == 'AMBRE' or n2['statut_global'] == 'AMBRE':
                if statut_rag == 'VERT':
                    statut_rag = 'AMBRE'

            if self.verbose:
                logger.info(
                    f"[{audit_id}] A7 terminé | "
                    f"statut={statut_rag} | "
                    f"durée={audit['duree_sec']:.1f}s"
                )

            # ── RÉSULTAT FINAL ────────────────────────────────────────────
            return {
                'success':      True,
                'statut_rag':   statut_rag,
                'audit_id':     audit_id,
                # Données
                'triangle':     C_calc,
                'sous_branche': n1.get('mode', 'auto'),
                # Niveaux
                'n1':           {k: v for k, v in n1.items() if k != 'C'},
                'n2':           {k: v for k, v in n2.items() if 'graphique' not in str(k)},
                'n3':           {k: v for k, v in n3.items() if k != 'facteurs_indiv'},
                'n4':           n4,
                # Livrables
                'graphiques':   graphiques,
                'commentaire':  commentaire,
                'excel_bytes':  excel_bytes,
                'audit_trail':  audit,
                # Compatibilité ancienne API
                'chain_ladder': n3['chain_ladder'],
                'mack':         n3['mack'],
                'bf':           n3['bf'],
                'cape_cod':     n3['cape_cod'],
                'bootstrap':    n3['bootstrap'],
                'munich_cl':    n3['munich_cl'],
                'best_estimate': n4,
                'validation':   n2,
                'atypiques':    {'alertes': n2.get('alertes', [])},
                'tail_factor':  n3['tail_factor'],
                'back_testing': {'statut': 'INFO', 'message': 'Voir audit trail'},
                'rapport_actuaire': {
                    'avis':     f"AVIS {'FAVORABLE' if statut_rag == 'VERT' else 'AVEC RÉSERVES' if statut_rag == 'AMBRE' else 'DÉFAVORABLE'}",
                    'sections': [{'numero': 1, 'titre': 'Résultats', 'contenu': commentaire}],
                },
                'erreur':       None,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return {
                'success':    False,
                'statut_rag': 'ROUGE',
                'audit_id':   audit_id,
                'erreur':     str(e),
                'commentaire': f"❌ ERREUR A7 : {str(e)}",
            }

    def _choisir_methode_cl(self, n2: Dict) -> str:
        """Choisit la méthode CL selon les résultats N2."""
        h1_ok = n2['h1_independance']['ok']
        h2_ok = n2['h2_stabilite']['ok']
        cv    = n2['h2_stabilite'].get('cv_moy', 0)

        if h1_ok and h2_ok:
            return 'standard'
        elif cv > 0.20:
            return 'mediane'
        elif cv > 0.10:
            return 'trimmed_mean'
        else:
            return 'volume_weighted'

    def _sauvegarder_audit(self, audit_id: str, audit: Dict):
        """Sauvegarde l'audit trail en JSON."""
        try:
            path = self.audit_path / f"{audit_id}.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(audit, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Audit non sauvegardé : {e}")
