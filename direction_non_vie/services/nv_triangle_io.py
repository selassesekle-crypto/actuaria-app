# =============================================================================
#  ActuarIA — Bloc II, module 1 : LECTURE UNIVERSELLE DE SOURCES
#  nv_triangle_io.py
# =============================================================================
#
#  RESPONSABILITÉ UNIQUE — lire une source (fichier ou objet en mémoire) et
#  identifier son format. L'actuaire dépose n'importe quoi, ce module le
#  convertit en un pivot unique (DataFrame ou ndarray) pour l'aval.
#
#  CE MODULE NE FAIT PAS (une seule responsabilité) :
#    · mapper les colonnes             → module mapping (lot suivant)
#    · construire le triangle          → module construction
#    · détecter cumulé / incrémental   → module construction
#    · diagnostiquer la qualité        → nv_triangle_diagnostics (existant)
#
#  Agnostique de l'interface : aucun import Streamlit, testable isolément.
#
#  Le format est déduit de l'EXTENSION (fichiers) ou du TYPE Python (mémoire),
#  jamais du contenu — même politique que a1_ingestion._lire_fichier. Une
#  extension inconnue lève une erreur nommant les formats acceptés, jamais un
#  crash pandas cryptique.
# =============================================================================

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger('actuaria.nv.io')

# Extensions reconnues → format normalisé
EXTENSIONS: Dict[str, str] = {
    '.xlsx': 'excel', '.xls': 'excel', '.xlsm': 'excel',
    '.csv':  'csv',   '.txt': 'csv',
    '.json': 'json',
    '.parquet': 'parquet',
}
EXTENSIONS_EXCEL = tuple(e for e, f in EXTENSIONS.items() if f == 'excel')

# Clés acceptées pour un dict en mémoire (résultat d'un autre agent, ex. A2)
CLES_DICT = ('dataframe', 'df', 'data')


def _lire_json(chemin: Path) -> Union[pd.DataFrame, np.ndarray]:
    """
    Lit un JSON de triangle. TROIS formes acceptées, et seulement trois — un
    JSON peut représenter un triangle de dix façons, on en fige un contrat
    explicite plutôt que de deviner :

      1. MATRICE  — liste de listes, une ligne par année de survenance :
         [[100, 180, 230], [120, 200, null], [110, null, null]]
         → np.ndarray (null / None → NaN). Forme naturelle d'un triangle déjà
           agrégé ; c'est elle qui justifie que ce module puisse rendre autre
           chose qu'un DataFrame.

      2. ENREGISTREMENTS — liste d'objets, une entrée par ligne :
         [{"annee": 2015, "dev_0": 100, "dev_1": 180}, ...]
         → pd.DataFrame. Couvre aussi le format long
           ({"annee":…, "dev":…, "montant":…}) : le module ne tranche pas la
           géométrie, c'est le rôle du module de construction.

      3. COLONNES — objet de listes de même longueur :
         {"annee": [2015, 2016], "dev_0": [100, 120]}
         → pd.DataFrame.

    Tout le reste (scalaire, objet imbriqué non tabulaire, listes de longueurs
    inégales) est refusé avec un message nommant les trois formes.
    """
    with open(chemin, 'r', encoding='utf-8') as f:
        contenu = json.load(f)

    if isinstance(contenu, list) and contenu:
        if all(isinstance(ligne, list) for ligne in contenu):        # forme 1
            return pd.DataFrame(contenu).to_numpy(dtype=float)
        if all(isinstance(ligne, dict) for ligne in contenu):        # forme 2
            return pd.DataFrame(contenu)

    if isinstance(contenu, dict) and contenu:                        # forme 3
        if all(isinstance(v, list) for v in contenu.values()):
            longueurs = {len(v) for v in contenu.values()}
            if len(longueurs) == 1:
                return pd.DataFrame(contenu)
            raise ValueError(
                f"JSON 'colonnes' invalide : longueurs inégales {sorted(longueurs)}.")

    raise ValueError(
        "Structure JSON non reconnue. Formes acceptées : (1) matrice "
        "[[...], [...]], (2) enregistrements [{...}, {...}], "
        "(3) colonnes {\"col\": [...], ...}.")


def _lire_chemin(
    chemin:     Path,
    nom_onglet: Optional[str],
    rapport:    Dict[str, Any],
) -> Tuple[Union[pd.DataFrame, np.ndarray], str]:
    """Lit un fichier d'après son extension. Renvoie (brut, format)."""
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")

    fmt = EXTENSIONS.get(chemin.suffix.lower())
    if fmt is None:
        raise ValueError(
            f"Format de fichier non supporté : '{chemin.suffix}' — extensions "
            f"acceptées : {', '.join(sorted(EXTENSIONS))}.")

    if fmt == 'excel':
        # sheet_name=None rendrait un DICT de toutes les feuilles, pas un
        # DataFrame : on retombe explicitement sur la PREMIÈRE feuille (0).
        # C'est le piège qui fait planter TriangleValidator.charger() sur un
        # classeur multi-onglets sans nom_onglet.
        feuille = nom_onglet if nom_onglet is not None else 0
        brut = pd.read_excel(chemin, sheet_name=feuille)
        rapport['infos'].append(
            f"Onglet lu : '{nom_onglet}'" if nom_onglet else "Onglet lu : premier (défaut)")
    elif fmt == 'csv':
        # sep=None + engine='python' : pandas détecte le séparateur (, ; \t |)
        brut = pd.read_csv(chemin, sep=None, engine='python')
    elif fmt == 'json':
        brut = _lire_json(chemin)
    else:                                                            # parquet
        try:
            brut = pd.read_parquet(chemin)
        except ImportError as e:
            raise ImportError(
                f"Lecture parquet impossible — moteur absent (pyarrow ou "
                f"fastparquet) : {e}") from e

    return brut, fmt


def lire_source(
    source:     Any,
    *,
    nom_onglet: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Lit une source quelconque et identifie son format.

    Parameters
    ----------
    source : chemin (str | Path), pd.DataFrame, np.ndarray, list, dict,
             ou objet fichier (upload).
    nom_onglet : nom de feuille Excel. None → première feuille.

    Returns
    -------
    dict — 'brut' (pd.DataFrame | np.ndarray), 'format_fichier'
    ('excel'|'csv'|'json'|'parquet'|'array'|'dataframe'|'dict'|'upload'),
    'nom_onglet', 'rapport' ({'infos': [...], 'avertissements': [...]}).

    Raises
    ------
    FileNotFoundError, ValueError, ImportError — messages nommant les formats
    acceptés ; jamais de crash pandas brut.
    """
    rapport: Dict[str, Any] = {'infos': [], 'avertissements': []}

    if source is None:
        raise ValueError("Aucune source fournie (source=None).")

    # ── Objets en mémoire — format déduit du TYPE ────────────────────────────
    if isinstance(source, np.ndarray):
        brut, fmt = source.astype(float), 'array'
    elif isinstance(source, pd.DataFrame):
        brut, fmt = source, 'dataframe'
    elif isinstance(source, list):
        brut, fmt = np.array(source, dtype=float), 'array'
    elif isinstance(source, dict):
        cle = next((k for k in CLES_DICT if k in source), None)
        if cle is None:
            raise ValueError(
                f"Dict fourni sans clé de données : attendu l'une de "
                f"{CLES_DICT}, reçu {sorted(source)[:5]}.")
        brut, fmt = source[cle], 'dict'
        rapport['infos'].append(f"Dict : données lues sous la clé '{cle}'")

    # ── Fichiers — format déduit de l'EXTENSION ──────────────────────────────
    elif isinstance(source, (str, Path)):
        brut, fmt = _lire_chemin(Path(source), nom_onglet, rapport)

    # ── Objet fichier (upload) — extension déduite du nom porté ──────────────
    elif hasattr(source, 'read'):
        nom = str(getattr(source, 'name', '') or '')
        fmt = 'upload'
        if nom.lower().endswith(EXTENSIONS_EXCEL):
            feuille = nom_onglet if nom_onglet is not None else 0
            brut = pd.read_excel(source, sheet_name=feuille)
            rapport['infos'].append(f"Upload Excel '{nom or '?'}'")
        else:
            if hasattr(source, 'seek'):
                source.seek(0)
            brut = pd.read_csv(source, sep=None, engine='python')
            rapport['infos'].append(f"Upload CSV '{nom or '?'}'")
    else:
        raise ValueError(
            f"Type de source non supporté : {type(source).__name__}. Attendu : "
            f"chemin, DataFrame, ndarray, list, dict ou objet fichier.")

    if isinstance(brut, (pd.DataFrame, np.ndarray)):
        rapport['infos'].append(f"Dimensions lues : {brut.shape[0]}×{brut.shape[1]}")
    else:
        raise ValueError(
            f"Source lue mais non tabulaire : {type(brut).__name__}. "
            f"Attendu un DataFrame ou un tableau.")

    logger.info(f"Source lue — format={fmt}, dimensions={brut.shape}")
    return {
        'brut':           brut,
        'format_fichier': fmt,
        'nom_onglet':     nom_onglet,
        'rapport':        rapport,
    }


def lister_onglets(chemin: Union[str, Path]) -> List[str]:
    """
    Noms des feuilles d'un classeur Excel, dans l'ordre du fichier.

    Ne lit AUCUNE donnée (pd.ExcelFile n'ouvre que le manifeste) et ne devine
    pas le contenu des onglets : le typage « probable » de l'ancien
    detecter_onglets était un aperçu d'interface sans valeur actuarielle.
    """
    chemin = Path(chemin)
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")
    if chemin.suffix.lower() not in EXTENSIONS_EXCEL:
        raise ValueError(
            f"Les onglets n'existent que sur un classeur Excel — reçu "
            f"'{chemin.suffix}' (attendu {', '.join(EXTENSIONS_EXCEL)}).")
    with pd.ExcelFile(chemin) as classeur:
        return list(classeur.sheet_names)
