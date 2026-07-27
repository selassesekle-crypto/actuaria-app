# =============================================================================
#  ActuarIA — Bloc II, module 4 : CONSTRUCTION DES TRIANGLES
#  nv_triangle_construction.py
# =============================================================================
#
#  RESPONSABILITÉ — transformer ce que les modules 1-3 ont lu et mappé en
#  TRIANGLES CUMULÉS prêts pour N3. Trois cas d'entrée (cumulé fourni /
#  incrémental fourni / tableau long à agréger) × deux bases (paiements /
#  charges), la formule différant selon la base pour le cas long.
#
#  UNE SEULE SOURCE DE VÉRITÉ : le CUMULÉ. L'incrémental se dérive à la volée,
#  jamais l'inverse — c'est déjà le contrat des 9 méthodes N3.
#
#  ⚠️ DETTE IMPÉRATIVE, MÉCANISME CONCRET ICI. Si une méthode tourne sur les
#  CHARGES, le Best Estimate doit valoir `ultime_charges − payé_à_date` et NON
#  `− charges_à_date` : sinon on obtient l'IBNR PUR, amputé des provisions
#  dossier, et le BE / SCR / Risk Margin sont sous-estimés EN SILENCE. C'est
#  pourquoi ce module expose `diagonale_paiements` DANS TOUS LES CAS, y compris
#  quand base_reference='charges' — N4 dispose ainsi toujours du payé à date.
#  Si la base est 'charges' et que les paiements n'ont pas pu être construits,
#  une alerte le dit explicitement : le BE ne sera pas calculable correctement.
#
#  LA COUCHE DONNÉES NE TRANSFORME JAMAIS UN NÉGATIF (décision Bloc I). Ni
#  `.abs()` sur les montants, ni `max(C, 0)` sur les cumulés : un recours
#  (subrogation) est une donnée VALIDE, elle traverse et elle est signalée.
#
#  Agnostique de l'interface : aucun import Streamlit ni agent. Testable seul.
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger('actuaria.nv.construction')

__all__ = [
    'METHODES_REQUERANT_PRIMES', 'STATUTS_FERMES', 'STATUTS_OUVERTS',
    'TrianglesConstruits', 'ConstructionImpossible',
    'construire_triangles', 'detecter_cumulativite', 'primes_requises',
    'construire_depuis_long', 'deriver_charges_depuis_provisions',
]

# ── Méthodes qui EXIGENT les primes ──────────────────────────────────────────
#  SEULE source de cette règle : aucune condition `if methode == 'bf' ...` ne
#  doit exister ailleurs. Vérifié dans le code : seul bf_cape_cod.py consomme
#  réellement les primes ; les 6 autres méthodes N3 n'en ont jamais besoin.
#  POINT D'EXTENSION — ajouter Benktander (mélange CL/BF par crédibilité, prévu
#  à l'étape 2 du plan) = UNE ligne ici, rien d'autre à rouvrir.
METHODES_REQUERANT_PRIMES: frozenset = frozenset({
    'bornhuetter_ferguson',
    'cape_cod',
    # 'benktander',   ← étape 2 : une ligne, ici et nulle part ailleurs.
})

# ── Statuts de dossier reconnus (cas long → charges dérivées) ────────────────
#  Tout ce qui n'est dans NI l'un NI l'autre est « non reconnu » : CONSERVÉ
#  (jamais d'exclusion silencieuse) mais signalé.
STATUTS_FERMES: frozenset = frozenset({
    'clos', 'close', 'closed', 'ferme', 'fermé', 'fermee', 'fermée',
    'termine', 'terminé', 'settled', 'regle', 'réglé', 'reglee', 'réglée',
})
STATUTS_OUVERTS: frozenset = frozenset({
    'ouvert', 'ouverte', 'open', 'en_cours', 'encours', 'en cours',
    'actif', 'active', 'pending', 'rouvert', 'reouvert', 'réouvert',
})
_COLONNES_STATUT: Tuple[str, ...] = ('statut', 'status', 'etat', 'état', 'state')

# Décroissance relative en deçà de laquelle on considère du bruit d'arrondi.
_TOL_DECROISSANCE = 0.01


class ConstructionImpossible(ValueError):
    """La construction ne peut pas aboutir PROPREMENT : cumulativité ambiguë non
    déclarée, champs indispensables absents, ou entrée inexploitable. Jamais un
    résultat faux en silence."""


# =============================================================================
#  RÉSULTAT
# =============================================================================
@dataclass(frozen=True)
class TrianglesConstruits:
    paiements:           Optional[np.ndarray]   # cumulé
    charges:             Optional[np.ndarray]   # cumulé
    diagonale_paiements: Optional[np.ndarray]   # ⚠️ DETTE : payé à date par année
    annee_min:           Optional[int]
    n_annees:            int
    n_dev:               int
    primes:              Optional[np.ndarray]
    base_reference:      str                    # 'paiements' | 'charges'
    primes_requises:     bool
    primes_disponibles:  bool
    methodes_bloquees:   Tuple[str, ...]        # demandées, non exécutables sans primes
    rapport:             Dict[str, Any] = field(default_factory=dict)

    @property
    def reference(self) -> Optional[np.ndarray]:
        """Le triangle qui sert de base à la projection (selon base_reference)."""
        return self.charges if self.base_reference == 'charges' else self.paiements

    def synthese(self) -> Dict[str, Any]:
        """Vue json-sérialisable (types natifs) — livrables / audit."""
        return {
            'paiements_construits': self.paiements is not None,
            'charges_construites':  self.charges is not None,
            'diagonale_paiements_disponible': self.diagonale_paiements is not None,
            'annee_min': self.annee_min,
            'n_annees':  int(self.n_annees),
            'n_dev':     int(self.n_dev),
            'base_reference':     self.base_reference,
            'primes_requises':    bool(self.primes_requises),
            'primes_disponibles': bool(self.primes_disponibles),
            'methodes_bloquees':  list(self.methodes_bloquees),
            'alertes': list(self.rapport.get('alertes', [])),
            'infos':   list(self.rapport.get('infos', [])),
        }


# =============================================================================
#  1. CUMULATIVITÉ — trois états, on ne devine pas sur l'ambigu
# =============================================================================
def detecter_cumulativite(M: np.ndarray) -> str:
    """Un triangle est-il déjà cumulé ? → 'cumule' | 'incremental' | 'ambigu'.

    L'ancienne détection (validator._est_cumule) ne tolérait que 1 % de
    décroissance et classait donc « incrémental » un CUMULÉ à recours — le
    pipeline le cumsommait alors, produisant un triangle faux en silence
    (mesuré : 1000, 2000, 2500, 2400 → 1000, 3000, 5500, 7900).

    D'où trois états :
      · 'cumule'      : aucune ligne ne décroît au-delà du bruit d'arrondi.
      · 'incremental' : les décroissances sont fortes ET la première colonne
                        domine — signature d'incréments (le gros est payé tôt).
      · 'ambigu'      : décroissances modérées ou partielles — indiscernable
                        d'un cumulé à recours. On NE DEVINE PAS : l'appelant
                        doit déclarer le mode.
    """
    A = np.asarray(M, dtype=float)
    if A.ndim != 2 or A.shape[0] == 0:
        return 'ambigu'

    n_lignes = n_decroissantes = 0
    ratio_max_decr = 0.0
    premiere_domine = 0
    for i in range(A.shape[0]):
        ligne = A[i][A[i] > 0]
        if len(ligne) < 2:
            continue
        n_lignes += 1
        chutes = np.diff(ligne) / np.maximum(ligne[:-1], 1e-12)
        pire = float(-np.min(chutes)) if np.min(chutes) < 0 else 0.0
        if pire > _TOL_DECROISSANCE:
            n_decroissantes += 1
            ratio_max_decr = max(ratio_max_decr, pire)
        # première valeur >= la moitié du total : typique d'incréments
        if ligne[0] >= 0.5 * float(np.sum(ligne)):
            premiere_domine += 1

    if n_lignes == 0:
        return 'ambigu'
    if n_decroissantes == 0:
        return 'cumule'

    frac_decr = n_decroissantes / n_lignes
    frac_dom  = premiere_domine / n_lignes
    # Incrémental net : ça décroît partout ET fortement ET la 1re colonne domine.
    if frac_decr >= 0.8 and ratio_max_decr >= 0.30 and frac_dom >= 0.5:
        return 'incremental'
    return 'ambigu'


def _cumuler_et_masquer(M: np.ndarray) -> np.ndarray:
    """Incrémental → cumulé, puis remise à zéro de la ZONE FUTURE.

    np.cumsum propage les zéros vers la droite : sans ce masquage, les cellules
    (i, j) avec i + j >= n porteraient la dernière valeur connue au lieu d'être
    vides (bug déjà corrigé côté validator, repris ici).
    """
    C = np.cumsum(np.asarray(M, dtype=float), axis=1)
    n = C.shape[0]
    for i in range(n):
        for j in range(C.shape[1]):
            if i + j >= n:
                C[i, j] = 0.0
    return C


# =============================================================================
#  2. TABLEAU LONG → TRIANGLE
# =============================================================================
def _axe_developpement(df: pd.DataFrame) -> pd.Series:
    """Âge de développement : 'annee_developpement' si présent, sinon dérivé de
    'annee_paiement' − 'annee_survenance'. Les dev < 0 sont écartés."""
    if 'annee_developpement' in df.columns:
        return pd.to_numeric(df['annee_developpement'], errors='coerce')
    if 'annee_paiement' in df.columns:
        return (pd.to_numeric(df['annee_paiement'], errors='coerce')
                - pd.to_numeric(df['annee_survenance'], errors='coerce'))
    raise ConstructionImpossible(
        "Aucun axe de developpement : ni 'annee_developpement' ni "
        "'annee_paiement' dans le tableau. Impossible de developper un triangle.")


def _pivot_long(df: pd.DataFrame, mesure: str, rapport: Dict,
                annees_reference: Optional[Tuple[int, int, int]] = None
                ) -> Tuple[np.ndarray, int]:
    """Tableau long → matrice INCRÉMENTALE (survenance × développement).

    Les montants NÉGATIFS traversent tels quels et sont signalés : un recours est
    une donnée valide (décision Bloc I). Aucun .abs(), aucun plancher.

    `annees_reference = (annee_min, n_annees, n_dev)` IMPOSE le repère au lieu de
    le déduire des seules lignes reçues — cf. construire_depuis_long.
    """
    if 'annee_survenance' not in df.columns:
        raise ConstructionImpossible(
            "'annee_survenance' absente — aucun triangle constructible.")
    if mesure not in df.columns:
        raise ConstructionImpossible(f"mesure '{mesure}' absente du tableau.")

    travail = pd.DataFrame({
        'surv': pd.to_numeric(df['annee_survenance'], errors='coerce'),
        'dev':  _axe_developpement(df),
        'val':  pd.to_numeric(df[mesure], errors='coerce'),
    }).dropna(subset=['surv', 'dev'])
    travail['val'] = travail['val'].fillna(0.0)
    travail = travail[travail['dev'] >= 0]

    if travail.empty and annees_reference is None:
        raise ConstructionImpossible(
            f"aucune ligne exploitable pour la mesure '{mesure}' "
            "(annee de survenance ou developpement manquants).")

    n_neg = int((travail['val'] < 0).sum())
    if n_neg > 0:
        rapport['alertes'].append(
            f"⚠️ {n_neg} montant(s) négatif(s) sur '{mesure}' — CONSERVÉS "
            f"(recours/subrogation : donnée valide, jamais transformée).")

    if annees_reference is not None:
        annee_min, n_annees, n_dev = (int(v) for v in annees_reference)
        if travail.empty:
            # Groupe VIDE sur repère imposé : cas NOMINAL (ex. aucun sinistre
            # au-dessus du seuil LLT) → matrice de zéros, jamais une exception.
            rapport['infos'].append(
                f"Aucune ligne pour '{mesure}' — triangle de zéros sur le repère "
                f"imposé ({annee_min}, {n_annees}×{n_dev}).")
    else:
        annee_min = int(travail['surv'].min())
        n_annees  = int(travail['surv'].max()) - annee_min + 1
        n_dev     = max(int(travail['dev'].max()) + 1, n_annees)

    inc = np.zeros((n_annees, n_dev))
    hors = 0
    for surv, dev, val in travail[['surv', 'dev', 'val']].itertuples(index=False):
        i, j = int(surv) - annee_min, int(dev)
        if 0 <= i < n_annees and 0 <= j < n_dev:
            inc[i, j] += float(val)
        else:
            hors += 1
    if hors > 0:
        rapport['alertes'].append(
            f"⚠️ {hors} ligne(s) de '{mesure}' hors du repère imposé "
            f"({annee_min}–{annee_min + n_annees - 1}, {n_dev} périodes) — IGNORÉE(S).")
    return inc, annee_min


def construire_depuis_long(df: pd.DataFrame, mesure: str,
                           rapport: Optional[Dict] = None,
                           annees_reference: Optional[Tuple[int, int, int]] = None
                           ) -> Tuple[np.ndarray, int]:
    """Tableau long → triangle CUMULÉ + année de la ligne 0.

    Pivot par (survenance, développement), puis cumul et masquage de la zone
    future. Aucune transformation des négatifs.

    `annees_reference = (annee_min, n_annees, n_dev)` — REPÈRE IMPOSÉ. Sans lui,
    le repère est déduit des seules lignes reçues, ce qui est correct pour un
    portefeuille entier mais FAUX pour un sous-ensemble : deux sous-ensembles d'un
    même portefeuille (attritionnel / grands sinistres) obtiendraient des repères
    différents, le sous-ensemble perdrait les années de survenance où il n'a aucun
    sinistre, et la zone connue rétrécirait (le masquage `i+j >= n` utilise le n
    LOCAL). Les triangles ne seraient alors ni comparables ni recombinables.

    ⚠️ CONTRAT POUR LA FAÇADE (module 7) : après une séparation (module 5), elle
    DOIT passer aux DEUX constructions le repère de la SOURCE COMPLÈTE — obtenu
    d'un premier appel sans repère sur la table entière. C'est ce qui garantit
    `C_attritionnel + C_grands = C_total` et un attritionnel couvrant toutes les
    années du portefeuille.

    Un groupe VIDE avec repère imposé est un cas NOMINAL (triangle de zéros), pas
    une erreur : un seuil qui ne capture aucun sinistre est une situation normale.
    """
    rapport = rapport if rapport is not None else {'alertes': [], 'infos': []}
    inc, annee_min = _pivot_long(df, mesure, rapport, annees_reference)
    C = _cumuler_et_masquer(inc)
    rapport['infos'].append(
        f"Triangle '{mesure}' construit : {C.shape[0]} années "
        f"({annee_min}→{annee_min + C.shape[0] - 1}), {C.shape[1]} périodes"
        f"{' [repère imposé]' if annees_reference is not None else ''}.")
    return C, annee_min


# =============================================================================
#  3. CHARGES DÉRIVÉES DES PROVISIONS (capacité ramenée dans la mainline)
# =============================================================================
def _filtrer_dossiers_fermes(df: pd.DataFrame, col_eval: str,
                             rapport: Dict) -> pd.DataFrame:
    """Écarte les dossiers dont le statut indique explicitement une clôture.

    UN principe appliqué aux QUATRE situations : n'exclure QUE sur un statut
    fermé RECONNU, et ne jamais rien traiter en silence.
      1. Aucune colonne de statut       → rien exclu   + alerte (hypothèse posée)
      2. Statut fermé reconnu           → EXCLU        + alerte (compte)
      3. Statut fermé + provision ≠ 0   → EXCLU        + alerte de CONTRADICTION
      4. Statut NON reconnu (typo, code
         métier, valeur vide, NaN)      → CONSERVÉ     + alerte (valeurs vues)

    Un dossier clos ne porte plus de charge à terminaison : sa provision
    résiduelle serait une donnée périmée qui gonflerait les charges. À l'inverse,
    exclure sur un statut incompris ferait disparaître une provision réelle.
    """
    col_statut = next((c for c in df.columns if c in _COLONNES_STATUT), None)
    if col_statut is None:
        rapport['alertes'].append(
            "⚠️ Aucune colonne de statut détectée : tous les dossiers sont traités "
            "comme ouverts (aucune exclusion). Les charges supposent que les "
            "évaluations fournies sont les provisions restantes — 0 si dossier clos.")
        return df

    valeurs   = df[col_statut].astype(str).str.strip().str.lower()
    est_ferme = valeurs.isin(STATUTS_FERMES)

    non_reconnus = ~est_ferme & ~valeurs.isin(STATUTS_OUVERTS)
    if bool(non_reconnus.any()):
        echantillon = sorted(set(df.loc[non_reconnus, col_statut]
                                 .astype(str).str.strip()))[:5]
        rapport['alertes'].append(
            f"⚠️ {int(non_reconnus.sum())} dossier(s) au statut NON RECONNU "
            f"{echantillon} — CONSERVÉS (traités comme ouverts) pour ne pas écarter "
            f"une provision réelle. Vérifier ces valeurs : une faute de frappe sur "
            f"un statut fermé le rendrait invisible au filtre.")

    n_fermes = int(est_ferme.sum())
    if n_fermes == 0:
        return df

    contradictoires = est_ferme & (df[col_eval] != 0)
    if int(contradictoires.sum()) > 0:
        montant = float(df.loc[contradictoires, col_eval].sum())
        rapport['alertes'].append(
            f"⚠️ {int(contradictoires.sum())} dossier(s) marqué(s) fermé(s) mais avec "
            f"une provision NON NULLE ({montant:,.0f} au total) — incohérence de la "
            f"source, VÉRIFICATION REQUISE. Ces dossiers sont exclus (cohérent avec "
            f"le statut) : si ces provisions sont réelles, corriger le fichier.")

    rapport['alertes'].append(
        f"⚠️ {n_fermes} dossier(s) au statut fermé exclu(s) du calcul des provisions "
        f"(un dossier clos ne porte plus de charge à terminaison).")
    return df[~est_ferme]


def deriver_charges_depuis_provisions(
    C_paiements: np.ndarray, df: pd.DataFrame, annee_min_paiements: int,
    rapport: Optional[Dict] = None,
) -> np.ndarray:
    """Charges = paiements + provisions dossier, posées sur la DIAGONALE.

    Chemin utilisé quand le tableau long porte 'evaluation_courante' mais PAS
    'montant_charge'. Séquentiel par construction : les paiements doivent être
    bâtis d'abord.

    Les provisions sont alignées sur l'ANNÉE RÉELLE (annee_min_paiements), jamais
    positionnellement : les deux fichiers peuvent couvrir des périmètres d'années
    différents, et un décalage produirait des charges silencieusement fausses.
    Une provision hors du triangle des paiements est ignorée AVEC alerte.
    """
    rapport = rapport if rapport is not None else {'alertes': [], 'infos': []}
    if 'evaluation_courante' not in df.columns:
        raise ConstructionImpossible(
            "'evaluation_courante' absente — impossible de dériver les charges.")
    if 'annee_survenance' not in df.columns:
        raise ConstructionImpossible(
            "'annee_survenance' absente — provisions non rattachables.")

    travail = df.copy()
    travail['annee_survenance'] = pd.to_numeric(
        travail['annee_survenance'], errors='coerce')
    travail['evaluation_courante'] = pd.to_numeric(
        travail['evaluation_courante'], errors='coerce').fillna(0.0)
    travail = _filtrer_dossiers_fermes(travail, 'evaluation_courante', rapport)

    par_annee = travail.groupby('annee_survenance')['evaluation_courante'].sum().to_dict()
    if not par_annee:
        rapport['alertes'].append(
            "⚠️ Aucune provision exploitable — charges = paiements.")
        return C_paiements.copy()

    n, m = C_paiements.shape
    annees_valides = set(range(annee_min_paiements, annee_min_paiements + n))
    hors = sorted(int(a) for a, v in par_annee.items()
                  if v != 0 and int(a) not in annees_valides)
    if hors:
        rapport['alertes'].append(
            f"⚠️ Provision(s) pour année(s) {hors} absente(s) du triangle des "
            f"paiements ({annee_min_paiements}–{annee_min_paiements + n - 1}) — "
            f"ignorée(s). Paiements et provisions doivent couvrir le même périmètre.")

    C_charges = C_paiements.copy()
    for i in range(n):
        provision = float(par_annee.get(annee_min_paiements + i, 0.0))
        if provision == 0.0:
            continue
        derniere = -1
        for j in range(m - 1, -1, -1):
            if C_paiements[i, j] != 0:
                derniere = j
                break
        if derniere >= 0:
            C_charges[i, derniere] = C_paiements[i, derniere] + provision
    rapport['infos'].append(
        f"Charges dérivées : provisions intégrées pour {len(par_annee)} année(s).")
    return C_charges


# =============================================================================
#  4. ALIGNEMENT ET PRIMES
# =============================================================================
def _aligner_dimensions(A: np.ndarray, B: np.ndarray,
                        rapport: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """Met deux triangles aux mêmes dimensions (complète de zéros / tronque).

    Munich CL compare les deux cellule à cellule : des dimensions différentes le
    rendraient inutilisable.
    """
    if A.shape == B.shape:
        return A, B
    n = max(A.shape[0], B.shape[0])
    m = max(A.shape[1], B.shape[1])
    out = []
    for M in (A, B):
        N = np.zeros((n, m))
        N[:M.shape[0], :M.shape[1]] = M
        out.append(N)
    rapport['alertes'].append(
        f"⚠️ Triangles de dimensions différentes ({A.shape} vs {B.shape}) — "
        f"alignés sur ({n}×{m}) pour permettre la comparaison payé/charges.")
    return out[0], out[1]


def primes_requises(methodes: Iterable[str]) -> bool:
    """Au moins une des méthodes demandées exige-t-elle les primes ?

    Lit UNIQUEMENT METHODES_REQUERANT_PRIMES — aucune méthode n'est nommée en dur
    ailleurs, si bien qu'ajouter Benktander se limite à une ligne dans ce set.
    """
    return bool({str(m).strip().lower() for m in methodes}
                & METHODES_REQUERANT_PRIMES)


def _methodes_bloquees(methodes: Iterable[str], primes_dispo: bool) -> Tuple[str, ...]:
    """Méthodes demandées qui NE POURRONT PAS s'exécuter faute de primes.

    On ne bloque JAMAIS tout le run : celles qui n'ont pas besoin des primes
    tournent normalement. Un actuaire qui veut CL + Mack et a coché BF par
    réflexe sans avoir les primes ne doit pas perdre CL + Mack pour autant.
    """
    if primes_dispo:
        return ()
    return tuple(sorted({str(m).strip().lower() for m in methodes}
                        & METHODES_REQUERANT_PRIMES))


def _normaliser_primes(primes, n_annees: int, rapport: Dict) -> Optional[np.ndarray]:
    """Vecteur de primes → ndarray de longueur n_annees (tronqué / complété)."""
    if primes is None:
        return None
    p = np.asarray(pd.Series(primes).values, dtype=float).ravel()
    if len(p) >= n_annees:
        return p[:n_annees]
    rapport['alertes'].append(
        f"⚠️ Vecteur de primes ({len(p)}) plus court que le triangle "
        f"({n_annees} années) — complété par des zéros.")
    return np.concatenate([p, np.zeros(n_annees - len(p))])


# =============================================================================
#  5. LE DISPATCHER
# =============================================================================
def _preparer_base(source, mode: str, mesure: str, libelle: str, rapport: Dict,
                   annees_reference: Optional[Tuple[int, int, int]] = None
                   ) -> Tuple[Optional[np.ndarray], Optional[int]]:
    """Une base (paiements OU charges) → triangle cumulé + année de la ligne 0.

    Décide du cas d'entrée : un DataFrame portant 'annee_survenance' est un
    tableau LONG (on agrège) ; tout le reste est une MATRICE positionnelle, dont
    la cumulativité vient du mode déclaré ou de la détection.
    """
    if source is None:
        return None, None

    est_long = isinstance(source, pd.DataFrame) and 'annee_survenance' in source.columns
    if mode == 'brut' or (mode == 'auto' and est_long):
        return construire_depuis_long(source, mesure, rapport, annees_reference)

    M = np.asarray(source.values if isinstance(source, pd.DataFrame) else source,
                   dtype=float)
    if mode == 'cumule':
        etat = 'cumule'
    elif mode == 'incremental':
        etat = 'incremental'
    else:
        etat = detecter_cumulativite(M)
        if etat == 'ambigu':
            raise ConstructionImpossible(
                f"{libelle} : cumulativité AMBIGUË — ce triangle décroît par "
                f"endroits. Cumulé avec recours (subrogation) ou incrémental ? "
                f"Impossible de trancher sans risque : déclarez le mode "
                f"('cumule' ou 'incremental') plutôt que 'auto'.")
        rapport['infos'].append(f"{libelle} : cumulativité détectée = {etat}.")

    C = M.astype(float).copy() if etat == 'cumule' else _cumuler_et_masquer(M)
    return C, None


def _preparer_charges(charges, mode: str, C_paie: Optional[np.ndarray],
                      annee_min: Optional[int], rapport: Dict,
                      annees_reference: Optional[Tuple[int, int, int]] = None
                      ) -> Tuple[Optional[np.ndarray], Optional[int]]:
    """Les charges par l'un des DEUX chemins, selon ce que porte la source.

    · 'montant_charge' disponible (ou matrice) → chemin DIRECT, même traitement
      que les paiements.
    · tableau long SANS 'montant_charge'       → chemin DÉRIVÉ : charges =
      paiements + provisions posées sur la diagonale. Exige les paiements ET
      l'axe des années (sinon les provisions seraient rattachées au hasard).
    """
    est_long = (isinstance(charges, pd.DataFrame)
                and 'annee_survenance' in charges.columns)
    if charges is None or not est_long or 'montant_charge' in charges.columns:
        return _preparer_base(charges, mode, 'montant_charge', 'Charges', rapport,
                              annees_reference)

    if C_paie is None:
        raise ConstructionImpossible(
            "Charges dérivées des provisions demandées, mais les paiements n'ont "
            "pas pu être construits (la dérivation part des paiements).")
    if annee_min is None:
        # Paiements en matrice positionnelle : aucun axe d'années connu. Poser les
        # provisions au hasard produirait des charges fausses en silence.
        raise ConstructionImpossible(
            "Charges dérivées de provisions, mais l'axe des années des paiements "
            "est inconnu (triangle fourni en matrice). Fournissez annee_min (année "
            "de la ligne 0) : sans elle, les provisions ne peuvent pas être "
            "rattachées à la bonne année de survenance.")
    return deriver_charges_depuis_provisions(C_paie, charges, annee_min, rapport), None


def _diagonale_payee(C_paie: Optional[np.ndarray], base_reference: str,
                     rapport: Dict) -> Optional[np.ndarray]:
    """Payé à date par année — ⚠️ le mécanisme concret de la DETTE IMPÉRATIVE.

    Rendu dès que les paiements existent, quelle que soit la base de projection :
    N4 en a besoin pour un BE correct sur base charges. Si la base est 'charges'
    et que les paiements manquent, on ALERTE au lieu de laisser N4 calculer un
    IBNR pur en croyant tenir un Best Estimate.
    """
    if C_paie is not None:
        n, m = C_paie.shape
        return np.array([float(C_paie[i, min(n - i - 1, m - 1)]) for i in range(n)])
    if base_reference == 'charges':
        rapport['alertes'].append(
            "⚠️ Base 'charges' SANS triangle de paiements : le payé à date est "
            "indisponible. Le Best Estimate calculé sur les charges serait l'IBNR "
            "PUR (amputé des provisions dossier) — fournir les paiements.")
    return None


def construire_triangles(
    paiements=None,
    charges=None,
    *,
    primes=None,
    methodes_demandees: Sequence[str] = (),
    mode_paiements: str = 'auto',
    mode_charges: str = 'auto',
    base_reference: str = 'paiements',
    annee_min: Optional[int] = None,
    annees_reference: Optional[Tuple[int, int, int]] = None,
) -> TrianglesConstruits:
    """Construit les DEUX triangles disponibles et rend un TrianglesConstruits.

    Chaque base accepte trois formes : matrice cumulée, matrice incrémentale (on
    cumule), ou tableau long déjà mappé (on agrège). Les modes valent
    'auto' | 'cumule' | 'incremental' | 'brut', indépendamment par base.

    Les CHARGES suivent deux chemins : directement depuis 'montant_charge' si la
    mesure existe, sinon dérivées des provisions ('evaluation_courante') posées
    sur la diagonale des paiements — d'où l'ordre imposé paiements → charges.

    `diagonale_paiements` est rendue DANS TOUS LES CAS où les paiements existent,
    y compris avec base_reference='charges' : c'est le payé à date dont N4 a
    besoin pour un Best Estimate correct (cf. dette impérative en en-tête).

    Les primes manquantes ne bloquent JAMAIS le run : les méthodes qui n'en ont
    pas besoin tournent, et `methodes_bloquees` nomme celles qui ne le pourront
    pas.

    `annee_min` : année de survenance de la LIGNE 0. Déduite d'un tableau long ;
    à FOURNIR quand les paiements arrivent en matrice (positionnelle, sans axe
    d'années) ET que les charges doivent être dérivées de provisions — sans elle
    l'alignement par année est impossible et le module refuse plutôt que de poser
    les provisions au hasard.

    `annees_reference = (annee_min, n_annees, n_dev)` : REPÈRE IMPOSÉ pour les
    tableaux longs — indispensable quand on construit un SOUS-ENSEMBLE (après une
    séparation LLT) pour qu'il garde toutes les années du portefeuille et reste
    recombinable. Cf. construire_depuis_long pour le contrat de la façade.

    LÈVE ConstructionImpossible si aucun triangle n'est constructible, si une
    cumulativité ambiguë n'est pas déclarée, ou si une dérivation est demandée
    sans axe d'années connu.
    """
    rapport: Dict[str, Any] = {'alertes': [], 'infos': []}
    if base_reference not in ('paiements', 'charges'):
        raise ConstructionImpossible(
            f"base_reference '{base_reference}' inconnue "
            f"(attendu 'paiements' ou 'charges').")

    C_paie, annee_min_paie = _preparer_base(
        paiements, mode_paiements, 'montant_paye', 'Paiements', rapport,
        annees_reference)
    if annee_min_paie is not None:
        annee_min = annee_min_paie      # déduite du long : prioritaire sur l'argument

    C_charges, annee_min_ch = _preparer_charges(
        charges, mode_charges, C_paie, annee_min, rapport, annees_reference)
    if annee_min is None:
        annee_min = annee_min_ch

    if C_paie is None and C_charges is None:
        raise ConstructionImpossible(
            "Aucun triangle constructible : ni paiements ni charges exploitables.")

    if C_paie is not None and C_charges is not None:
        C_paie, C_charges = _aligner_dimensions(C_paie, C_charges, rapport)

    diagonale = _diagonale_payee(C_paie, base_reference, rapport)

    reference = C_charges if base_reference == 'charges' else C_paie
    if reference is None:
        raise ConstructionImpossible(
            f"base_reference='{base_reference}' mais ce triangle n'a pas pu être "
            f"construit.")

    n_annees, n_dev = reference.shape
    primes_norm = _normaliser_primes(primes, n_annees, rapport)
    dispo   = primes_norm is not None
    requis  = primes_requises(methodes_demandees)
    bloquees = _methodes_bloquees(methodes_demandees, dispo)
    if bloquees:
        rapport['alertes'].append(
            f"⚠️ Primes absentes : {list(bloquees)} ne pourra/pourront pas "
            f"s'exécuter. Les autres méthodes demandées ne sont pas affectées.")

    return TrianglesConstruits(
        paiements=C_paie, charges=C_charges, diagonale_paiements=diagonale,
        annee_min=annee_min, n_annees=n_annees, n_dev=n_dev,
        primes=primes_norm, base_reference=base_reference,
        primes_requises=requis, primes_disponibles=dispo,
        methodes_bloquees=bloquees, rapport=rapport)
