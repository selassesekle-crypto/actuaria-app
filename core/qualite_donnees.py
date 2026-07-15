"""
core/qualite_donnees.py — Couche de qualité de données GÉNÉRIQUE, pilotée par le
PLAN, pour le chemin déclaratif (Phase 0 du roadmap qualité).

PRINCIPE DIRECTEUR : jamais de correction ou d'exclusion SILENCIEUSE.

QUATRE RÈGLES (toutes pilotées par les RÔLES du plan — exposition,
cible_frequence, cible_cout, identifiant_contrat — jamais par un nom de colonne
codé en dur ; un plan futur jamais vu en bénéficie automatiquement) :

  1. IMPOSSIBLE MATHÉMATIQUEMENT (fréquence < 0, coût < 0, exposition ≤ 0,
     doublon sur l'identifiant de contrat déclaré) → exclut la LIGNE. Comptée
     et listée dans le rapport.
  2. IMPLAUSIBLE MAIS PAS IMPOSSIBLE, règle établie (exposition > 1) → corrige
     automatiquement (plafond 1.0) et signale la correction.
  3. AMBIGU (coût > 0 sans sinistre, ou l'inverse ; fréquence non entière ;
     doublon de ligne entière SANS identifiant pour trancher) → NE DÉCIDE RIEN :
     compte, affiche, laisse tel quel.
  4. ESCALADE PAR PROPORTION : si UN type d'anomalie (règles 1-3) touche ≥ 5 %
     des lignes ET qu'aucune confirmation actuarielle nominative n'est fournie
     (qualite_validee_par), le traitement est BLOQUÉ (QualiteBloquante). Le champ
     nominatif absent par défaut est l'unique échappatoire, et il est TRACÉ (qui,
     quand). MÊME PATTERN que valide_par_actuaire_dl (garde-fou DL).

Réutilise la logique de détection déjà pensée dans A1 (`_evaluer_qualite`), mais
SANS son défaut : ici la détection DÉCLENCHE une action (exclure / corriger /
bloquer), là où A1 se contentait de scorer (flag-only). Les détecteurs sont purs
et paramétrés par colonne — A1 pourra les réutiliser (convergence future).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple, TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:                       # évite un import cyclique à l'exécution
    from core.plan_tarifaire import PlanTarifaire

# Seuil d'escalade : au-delà, une confirmation actuarielle nominative est requise.
SEUIL_ESCALADE = 0.05


class QualiteBloquante(Exception):
    """Levée par pipeline_complet quand une anomalie ≥ seuil n'est PAS validée par
    un actuaire nommé. Porte le RapportQualite — ce que l'actuaire doit voir pour
    décider. L'échappatoire n'est PAS un try/except mais le champ
    qualite_validee_par (re-run nominatif), afin qu'aucun blocage ne soit
    contournable en silence."""

    def __init__(self, rapport: "RapportQualite"):
        self.rapport = rapport
        codes = ", ".join(rapport.anomalies_au_dela_seuil) or "?"
        super().__init__(
            f"Controle qualite BLOQUE : anomalie(s) [{codes}] touchant >= "
            f"{rapport.seuil:.0%} des lignes. Confirmation actuarielle nominative "
            f"requise (qualite_validee_par) pour poursuivre."
        )


# ══════════════════════════════════════════════════════════════════════════════
#  STRUCTURES DU RAPPORT (jamais silencieux)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Anomalie:
    """Une anomalie détectée, avec sa règle, le rôle/colonne concerné, le volume
    et les index — pour une traçabilité complète dans le rapport."""
    code: str            # 'frequence_negative' | 'cout_negatif' | ...
    regle: int           # 1 (exclure) | 2 (corriger) | 3 (signaler)
    role: str            # 'cible_frequence'|'cible_cout'|'exposition'|'identifiant_contrat'|'ligne'
    colonne: Optional[str]
    nb_lignes: int
    proportion: float
    index: Tuple[int, ...]           # positions (0-based) des lignes concernées
    description: str
    correction: Optional[str] = None  # règle 2 : la règle appliquée


@dataclass
class RapportQualite:
    lignes_initiales: int
    lignes_retenues: int
    exclusions: List[Anomalie]        # règle 1
    corrections: List[Anomalie]       # règle 2
    signalements: List[Anomalie]      # règle 3
    escalade_declenchee: bool
    anomalies_au_dela_seuil: List[str]
    seuil: float
    validee_par: Optional[str]        # nom de l'actuaire, ou None
    horodatage: Optional[str]         # FOURNI par l'appelant — jamais généré ici
    bloque: bool
    dataframe_propre: Optional[pd.DataFrame]   # None si bloqué

    def resume(self) -> dict:
        """Dict sérialisable (sans les index bruts) pour audit_trail / rapports."""
        def _a(a: Anomalie) -> dict:
            return {'code': a.code, 'regle': a.regle, 'role': a.role,
                    'colonne': a.colonne, 'nb_lignes': a.nb_lignes,
                    'proportion': round(a.proportion, 4),
                    'description': a.description, 'correction': a.correction}
        return {
            'lignes_initiales': self.lignes_initiales,
            'lignes_retenues':  self.lignes_retenues,
            'exclusions':   [_a(a) for a in self.exclusions],
            'corrections':  [_a(a) for a in self.corrections],
            'signalements': [_a(a) for a in self.signalements],
            'escalade_declenchee':    self.escalade_declenchee,
            'anomalies_au_dela_seuil': list(self.anomalies_au_dela_seuil),
            'seuil':       self.seuil,
            'validee_par': self.validee_par,
            'horodatage':  self.horodatage,
            'bloque':      self.bloque,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  DÉTECTEURS PURS — source unique, paramétrés par COLONNE (issue d'un rôle)
#  Retournent un masque booléen np.ndarray aligné sur les lignes de df.
# ══════════════════════════════════════════════════════════════════════════════
def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def detecter_negatifs(df: pd.DataFrame, col: str) -> np.ndarray:
    """Lignes où df[col] < 0 (NaN non compté)."""
    return (_num(df, col) < 0).to_numpy()


def detecter_non_positif(df: pd.DataFrame, col: str) -> np.ndarray:
    """Lignes où df[col] <= 0 (exposition = 0 casse l'offset log — impossible)."""
    return (_num(df, col) <= 0).to_numpy()


def detecter_sup(df: pd.DataFrame, col: str, hi: float) -> np.ndarray:
    """Lignes où df[col] > hi (ex. exposition > 1)."""
    return (_num(df, col) > hi).to_numpy()


def detecter_non_entier(df: pd.DataFrame, col: str) -> np.ndarray:
    """Lignes où df[col] n'est pas entière (comptage attendu — ambigu)."""
    s = _num(df, col)
    return (s.notna() & ((s - np.round(s)).abs() > 1e-9)).to_numpy()


def detecter_incoherence(df: pd.DataFrame, col_freq: str,
                         col_cout: str) -> Tuple[np.ndarray, np.ndarray]:
    """(coût > 0 & fréquence = 0, fréquence > 0 & coût = 0) — les deux sens."""
    f = _num(df, col_freq)
    c = _num(df, col_cout)
    cout_sans_sin = ((c > 0) & (f == 0)).to_numpy()
    sin_sans_cout = ((f > 0) & (c == 0)).to_numpy()
    return cout_sans_sin, sin_sans_cout


def detecter_doublons_id(df: pd.DataFrame, col_id: str) -> np.ndarray:
    """Lignes en doublon sur l'identifiant déclaré (garde la 1re occurrence)."""
    return df.duplicated(subset=[col_id], keep='first').to_numpy()


def detecter_doublons_ligne(df: pd.DataFrame) -> np.ndarray:
    """Lignes strictement identiques à une précédente (garde la 1re)."""
    return df.duplicated(keep='first').to_numpy()


# ══════════════════════════════════════════════════════════════════════════════
#  RÈGLE 2 — registre des corrections ÉTABLIES (extensible). Phase 0 : 1 entrée.
#  Chaque entrée : (rôle, code, seuil, valeur_plafond, description).
# ══════════════════════════════════════════════════════════════════════════════
# (Gardé explicite plutôt que data-driven pour rester lisible en Phase 0 ;
#  l'unique correction établie est le plafond d'exposition, déjà présent côté
#  legacy dans A2._traiter_exposition.)


# ══════════════════════════════════════════════════════════════════════════════
#  ORCHESTRATEUR
# ══════════════════════════════════════════════════════════════════════════════
def controler_qualite(
    df: pd.DataFrame,
    plan: "PlanTarifaire",
    qualite_validee_par: Optional[str] = None,
    horodatage: Optional[str] = None,
    seuil_escalade: float = SEUIL_ESCALADE,
) -> RapportQualite:
    """
    Applique les 4 règles, pilotées par les RÔLES du plan. Ne mute jamais `df`
    en place ; retourne un RapportQualite (avec `dataframe_propre` si non bloqué).
    Ne génère aucun horodatage — réutilise celui fourni par l'appelant.

    Ordre : détecter tout (1-3) → gate d'escalade (avant toute mutation) →
    appliquer (exclure 1, corriger 2, laisser 3) → rapport.
    """
    n0 = len(df)
    col_freq = plan.cible_frequence
    col_cout = plan.cible_cout
    col_expo = plan.exposition
    col_id = getattr(plan, "identifiant_contrat", None)

    anomalies: List[Anomalie] = []

    def _ajouter(code, regle, role, colonne, mask, description, correction=None):
        idx = np.flatnonzero(np.asarray(mask, dtype=bool))
        if idx.size == 0:
            return
        anomalies.append(Anomalie(
            code=code, regle=regle, role=role, colonne=colonne,
            nb_lignes=int(idx.size), proportion=idx.size / max(n0, 1),
            index=tuple(int(i) for i in idx),
            description=description, correction=correction))

    # ── RÈGLE 1 : IMPOSSIBLE → exclure ───────────────────────────────────────
    if col_freq in df.columns:
        _ajouter('frequence_negative', 1, 'cible_frequence', col_freq,
                 detecter_negatifs(df, col_freq),
                 f"cible_frequence ('{col_freq}') < 0 — nombre de sinistres negatif, impossible.")
    if col_cout in df.columns:
        _ajouter('cout_negatif', 1, 'cible_cout', col_cout,
                 detecter_negatifs(df, col_cout),
                 f"cible_cout ('{col_cout}') < 0 — cout negatif, impossible.")
    if col_expo in df.columns:
        _ajouter('exposition_non_positive', 1, 'exposition', col_expo,
                 detecter_non_positif(df, col_expo),
                 f"exposition ('{col_expo}') <= 0 — duree nulle/negative, casse l'offset log, impossible.")
    if col_id and col_id in df.columns:
        _ajouter('doublon_identifiant', 1, 'identifiant_contrat', col_id,
                 detecter_doublons_id(df, col_id),
                 f"doublon sur l'identifiant de contrat ('{col_id}') — ligne redondante.")

    # ── RÈGLE 2 : IMPLAUSIBLE établi → corriger (plafond exposition) ──────────
    mask_corr_expo = None
    if col_expo in df.columns:
        mask_corr_expo = detecter_sup(df, col_expo, 1.0)
        _ajouter('exposition_sup_1', 2, 'exposition', col_expo, mask_corr_expo,
                 f"exposition ('{col_expo}') > 1 — implausible pour un contrat annuel.",
                 correction="plafond a 1.0")

    # ── RÈGLE 3 : AMBIGU → signaler, laisser tel quel ────────────────────────
    if col_freq in df.columns and col_cout in df.columns:
        cout_sans_sin, sin_sans_cout = detecter_incoherence(df, col_freq, col_cout)
        _ajouter('incoherence_cout_sans_sin', 3, 'cible_cout', col_cout, cout_sans_sin,
                 "cout > 0 avec frequence = 0 — ambigu (ni exclu ni corrige).")
        _ajouter('incoherence_sin_sans_cout', 3, 'cible_frequence', col_freq, sin_sans_cout,
                 "frequence > 0 avec cout = 0 — ambigu (ni exclu ni corrige).")
    if col_freq in df.columns:
        _ajouter('frequence_non_entiere', 3, 'cible_frequence', col_freq,
                 detecter_non_entier(df, col_freq),
                 f"cible_frequence ('{col_freq}') non entiere — ambigu (comptage attendu).")
    if not (col_id and col_id in df.columns):
        # Pas d'identifiant de contrat déclaré → un doublon de ligne entière est
        # AMBIGU (deux contrats identiques peuvent être réels) : règle 3.
        _ajouter('doublon_ligne', 3, 'ligne', None, detecter_doublons_ligne(df),
                 "ligne strictement identique a une autre — ambigu sans identifiant pour trancher.")

    # ── RÈGLE 4 : ESCALADE PAR PROPORTION (avant toute mutation) ─────────────
    au_dela = [a.code for a in anomalies if a.proportion >= seuil_escalade]
    escalade = len(au_dela) > 0
    exclusions = [a for a in anomalies if a.regle == 1]
    corrections = [a for a in anomalies if a.regle == 2]
    signalements = [a for a in anomalies if a.regle == 3]

    if escalade and not qualite_validee_par:
        # BLOQUÉ : on ne mute rien, on ne tarife rien. dataframe_propre = None.
        return RapportQualite(
            lignes_initiales=n0, lignes_retenues=n0,
            exclusions=exclusions, corrections=corrections, signalements=signalements,
            escalade_declenchee=True, anomalies_au_dela_seuil=au_dela,
            seuil=seuil_escalade, validee_par=None, horodatage=horodatage,
            bloque=True, dataframe_propre=None)

    # ── APPLICATION : règle 1 exclut, règle 2 corrige, règle 3 ne touche rien ─
    dfp = df.copy()
    # Règle 2 d'abord (les lignes exclues ensuite seront de toute façon retirées).
    if mask_corr_expo is not None and mask_corr_expo.any():
        dfp.loc[mask_corr_expo, col_expo] = 1.0
    # Règle 1 : union des masques d'exclusion.
    excl = np.zeros(n0, dtype=bool)
    for a in exclusions:
        m = np.zeros(n0, dtype=bool)
        m[list(a.index)] = True
        excl |= m
    if excl.any():
        dfp = dfp.loc[~excl].reset_index(drop=True)   # index propre seulement si on retire

    return RapportQualite(
        lignes_initiales=n0, lignes_retenues=len(dfp),
        exclusions=exclusions, corrections=corrections, signalements=signalements,
        escalade_declenchee=escalade, anomalies_au_dela_seuil=au_dela,
        seuil=seuil_escalade,
        validee_par=(qualite_validee_par if escalade else None),
        horodatage=horodatage, bloque=False, dataframe_propre=dfp)


# ══════════════════════════════════════════════════════════════════════════════
#  SURFAÇAGE — source unique pour Excel / Word / HTML (comme synthese_exclusions)
# ══════════════════════════════════════════════════════════════════════════════
def _date_lisible(ts: Optional[str]) -> Optional[str]:
    """Reformate un horodatage ISO existant en JJ/MM/AAAA. Ne génère rien."""
    if not ts:
        return None
    jour = str(ts).split('T')[0]
    p = jour.split('-')
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else jour


def synthese_qualite_donnees(rapport: Optional["RapportQualite"]) -> Optional[str]:
    """Texte à afficher dans TOUT livrable quand la couche qualité a agi. None si
    rien à signaler. Un traitement silencieux est un défaut en soi : l'actuaire
    doit voir ce qui a été exclu, corrigé, signalé, et qui a validé une poursuite."""
    if rapport is None:
        return None
    if rapport.bloque:
        return (f"⚠ CONTROLE QUALITE BLOQUE — anomalie(s) "
                f"[{', '.join(rapport.anomalies_au_dela_seuil)}] touchant >= "
                f"{rapport.seuil:.0%} des lignes. Confirmation actuarielle nominative "
                f"requise (qualite_validee_par) pour poursuivre.")
    lignes: List[str] = []
    if rapport.exclusions:
        tot = sum(a.nb_lignes for a in rapport.exclusions)
        det = " ; ".join(f"{a.nb_lignes}x {a.code}" for a in rapport.exclusions)
        lignes.append(f"✔ {tot} ligne(s) EXCLUE(S) (impossible) : {det}.")
    if rapport.corrections:
        tot = sum(a.nb_lignes for a in rapport.corrections)
        det = " ; ".join(f"{a.nb_lignes}x {a.code} ({a.correction})" for a in rapport.corrections)
        lignes.append(f"✔ {tot} ligne(s) CORRIGEE(S) : {det}.")
    if rapport.signalements:
        tot = sum(a.nb_lignes for a in rapport.signalements)
        det = " ; ".join(f"{a.nb_lignes}x {a.code}" for a in rapport.signalements)
        lignes.append(f"⚠ {tot} ligne(s) SIGNALEE(S) (ambigu, laissees telles quelles) : {det}.")
    if rapport.escalade_declenchee and rapport.validee_par:
        d = _date_lisible(rapport.horodatage)
        lignes.append(
            f"✔ Poursuite malgre anomalie(s) >= {rapport.seuil:.0%} VALIDEE par "
            f"« {rapport.validee_par} »" + (f" le {d}" if d else "") + ".")
    return "\n".join(lignes) if lignes else None
