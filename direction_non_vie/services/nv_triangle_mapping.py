# =============================================================================
#  ActuarIA — Bloc II, module 2 : MAPPING DÉCLARATIF DES COLONNES
#  nv_triangle_mapping.py
# =============================================================================
#
#  RESPONSABILITÉ UNIQUE — renommer les colonnes d'UN tableau client vers le
#  vocabulaire canonique A7, et décrire ce que ce tableau permet de construire.
#  S'inspire de l'ESPRIT de core/mapping_client (déclaratif + validation statique
#  + rapport à l'actuaire) mais n'en dépend PAS et n'en copie AUCUN code : système
#  neuf et séparé, dédié à A7 (décision projet).
#
#  CE MODULE NE FAIT PAS (une seule responsabilité) :
#    · lire le fichier                 → nv_triangle_io (module 1)
#    · identifier le rôle d'un onglet   → nv_triangle_mapping_llm (module 3)
#    · construire le triangle           → nv_triangle_construction
#    · détecter cumulé / incrémental    → nv_triangle_construction
#
#  DÉSAMBIGUÏSATION PAYÉ / CHARGE — le cœur de ce module. Les méthodes N3
#  (chain_ladder, mack, …) sont AGNOSTIQUES : elles tournent sur « un triangle
#  cumulé » sans savoir si c'est du payé ou de la charge. En pratique (branches
#  longues, RC corporelle) l'actuaire peut vouloir tourner N'IMPORTE QUELLE
#  méthode sur les charges plutôt que sur les paiements. Le vocabulaire distingue
#  donc trois briques de mesure — montant_paye, montant_charge, evaluation_courante
#  — là où l'ancien système confondait tout dans un seul champ 'montant'. Le
#  rapport annonce, brique par brique, ce qui est constructible.
#
#  ⚠️ DETTE IMPÉRATIVE POUR LE MODULE DE CONSTRUCTION / N4 (pas ici) : si une
#  méthode tourne sur les CHARGES, le Best Estimate doit être `ultime_charges −
#  payé_à_date` et NON `ultime_charges − charges_à_date` (sinon on obtient l'IBNR
#  pur, amputé des provisions dossier — sous-estimation du BE, du SCR et de la RM).
#  La diagonale des paiements doit donc rester disponible même en base charges.
#
#  Agnostique de l'interface : aucun import Streamlit, testable isolément.
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import pandas as pd

logger = logging.getLogger('actuaria.nv.mapping')

__all__ = [
    'CHAMPS_SINISTRES', 'CHAMPS_PRIMES',
    'TriangleSchema', 'RapportMappingTriangle', 'MappingTriangleIncoherent',
    'charger_mapping_triangle', 'valider_mapping_triangle',
    'appliquer_mapping_triangle', 'preparer_tableau', 'capacites',
]


# =============================================================================
#  VOCABULAIRE CANONIQUE
# =============================================================================
#  Deux tableaux possibles (kind) : 'sinistres' (une table de sinistres) et
#  'primes' (une table de primes par année). Les champs ci-dessous sont les
#  SEULES cibles de mapping valides.

# ── Axes de développement : au moins l'un des deux pour un vrai triangle ──────
_AXES = ('annee_developpement', 'annee_paiement')
# ── Mesures : les trois briques ──────────────────────────────────────────────
_MESURES = ('montant_paye', 'montant_charge', 'evaluation_courante')

CHAMPS_SINISTRES: frozenset = frozenset(
    {'annee_survenance'} | set(_AXES) | set(_MESURES))
CHAMPS_PRIMES:    frozenset = frozenset({'annee_survenance', 'prime'})
_CANONIQUES:      frozenset = CHAMPS_SINISTRES | CHAMPS_PRIMES

# ── Synonymes : nom brut d'une colonne client → champ canonique ──────────────
#  Source UNIQUE de la reconnaissance de noms pour A7 (remplace à terme les deux
#  dictionnaires hérités SYNONYMES / SYNONYMES_COLONNES). Utilisés SANS mapping
#  explicite : passthrough et capacites(). Un mapping YAML explicite reste
#  prioritaire et cible directement le champ canonique.
SYNONYMES: Dict[str, Tuple[str, ...]] = {
    'annee_survenance':    ('annee_survenance', 'survenance', 'ay', 'accident_year',
                            'annee_sinistre', 'origin_year', 'loss_year', 'annee', 'year'),
    'annee_developpement': ('annee_developpement', 'dev', 'development', 'lag',
                            'periode', 'periode_dev', 'dev_year', 'development_period'),
    'annee_paiement':      ('annee_paiement', 'payment_year', 'annee_reglement',
                            'calendar_year', 'annee_calendaire'),
    'montant_paye':        ('montant_paye', 'paid', 'paid_losses', 'reglements',
                            'reglements_cumules', 'regle', 'cumulative_paid', 'paiement'),
    'montant_charge':      ('montant_charge', 'incurred', 'incurred_losses', 'charge',
                            'charges', 'charge_totale', 'cout_total', 'cout_total_sinistres'),
    'evaluation_courante': ('evaluation_courante', 'evaluation', 'reserve', 'provision',
                            'case_reserve', 'outstanding', 'encours', 'provision_dossier',
                            'montant_reserve', 'charge_courante'),
    'prime':               ('prime', 'primes', 'premium', 'premiums', 'prime_acquise',
                            'primes_acquises', 'earned_premium'),
}

# ── Termes AMBIGUS : rattachés par défaut, mais JAMAIS en silence ─────────────
#  'montant' seul ne dit pas payé vs charge. On le rattache aux paiements (usage
#  le plus fréquent) AVEC une alerte invitant à lever l'ambiguïté.
AMBIGUS: Dict[str, str] = {
    'montant':          'montant_paye',
    'amount':           'montant_paye',
    'cout':             'montant_paye',
    'claim_amount':     'montant_paye',
    'montant_sinistre': 'montant_paye',
    'montant_cumule':   'montant_paye',
}

# Index inverse {nom_brut → champ_canonique}, construit une fois.
_INDEX_SYNONYMES: Dict[str, str] = {
    brut: canon for canon, bruts in SYNONYMES.items() for brut in bruts
}


def _normaliser(nom: Any) -> str:
    """Nom de colonne → forme comparable (minuscule, sans espaces de bord)."""
    return str(nom).strip().lower().replace(' ', '_')


def _reconnaitre(nom: Any) -> Tuple[Optional[str], bool]:
    """Reconnaît un nom brut de colonne. Retourne (champ_canonique|None, ambigu).

    Priorité : nom déjà canonique > synonyme connu > terme ambigu (→ défaut + True).
    """
    n = _normaliser(nom)
    if n in CHAMPS_SINISTRES or n in CHAMPS_PRIMES:
        return n, False
    if n in _INDEX_SYNONYMES:
        return _INDEX_SYNONYMES[n], False
    if n in AMBIGUS:
        return AMBIGUS[n], True
    return None, False


# =============================================================================
#  EXCEPTION
# =============================================================================
class MappingTriangleIncoherent(ValueError):
    """Le mapping ne peut pas s'appliquer PROPREMENT, ou le tableau ne permet de
    construire NI paiements NI charges. Jamais silencieux."""


# =============================================================================
#  LE SCHÉMA DE MAPPING (déclaré par l'actuaire)
# =============================================================================
@dataclass(frozen=True)
class TriangleSchema:
    kind:            str                 # 'sinistres' | 'primes'
    correspondances: Mapping[str, str]   # {nom_colonne_client: champ_canonique}
    client:          str = ''            # traçabilité
    source:          str = ''            # traçabilité (fichier / onglet d'origine)

    _KINDS = ('sinistres', 'primes')

    @classmethod
    def depuis_dict(cls, d: Dict[str, Any]) -> 'TriangleSchema':
        if not isinstance(d, dict):
            raise MappingTriangleIncoherent("Mapping : racine attendue = dict.")
        kind = str(d.get('kind', 'sinistres')).strip().lower()
        if kind not in cls._KINDS:
            raise MappingTriangleIncoherent(
                f"Mapping : kind '{kind}' inconnu (attendu {cls._KINDS}).")
        corr = d.get('correspondances')
        if not isinstance(corr, dict) or not corr:
            raise MappingTriangleIncoherent(
                "Mapping : 'correspondances' doit être un dict non vide "
                "{nom_client: champ_canonique}.")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in corr.items()):
            raise MappingTriangleIncoherent(
                "Mapping : 'correspondances' = chaînes uniquement.")
        return cls(kind=kind, correspondances=dict(corr),
                   client=str(d.get('client', '')), source=str(d.get('source', '')))

    @classmethod
    def depuis_yaml(cls, chemin) -> 'TriangleSchema':
        import yaml
        with open(chemin, encoding='utf-8') as fh:
            return cls.depuis_dict(yaml.safe_load(fh))


# =============================================================================
#  LE RAPPORT (ce que l'actuaire doit voir)
# =============================================================================
@dataclass(frozen=True)
class RapportMappingTriangle:
    kind:   str
    source: str
    n_renommees: int
    champs_couverts:              Tuple[str, ...]   # champs canoniques présents
    peut_construire_paiements:    bool              # montant_paye  + un axe
    peut_construire_charges:      bool              # montant_charge + un axe
    peut_deriver_charges:         bool              # evaluation_courante + paiements
    mesures_ambigues:             Tuple[str, ...]   # colonnes rattachées par défaut
    colonnes_client_non_mappees:  Tuple[str, ...]   # présentes, non consommées
    correspondances_mortes:       Tuple[str, ...]   # clé de mapping absente du fichier

    def synthese(self) -> Dict[str, Any]:
        """Vue json-sérialisable (types natifs) — livrables / audit."""
        return {
            'kind':   self.kind,
            'source': self.source,
            'n_renommees': int(self.n_renommees),
            'champs_couverts': list(self.champs_couverts),
            'peut_construire_paiements': bool(self.peut_construire_paiements),
            'peut_construire_charges':   bool(self.peut_construire_charges),
            'peut_deriver_charges':      bool(self.peut_deriver_charges),
            'mesures_ambigues':          list(self.mesures_ambigues),
            'colonnes_client_non_mappees': list(self.colonnes_client_non_mappees),
            'correspondances_mortes':      list(self.correspondances_mortes),
        }


def _catalogue(kind: str) -> frozenset:
    """Vocabulaire canonique applicable à un kind — SOURCE UNIQUE.

    Seul 'primes' ouvre le vocabulaire des primes ; toute autre valeur relève des
    sinistres, même convention que _lever_si_inexploitable (sans cette source
    unique, les deux divergeaient sur un kind inattendu).
    """
    return CHAMPS_PRIMES if kind == 'primes' else CHAMPS_SINISTRES


def _capacites_depuis_champs(champs: set) -> Dict[str, bool]:
    """Les trois booléens de capacité à partir des champs canoniques présents.

    · paiements : montant_paye + un axe de développement
    · charges   : montant_charge + un axe
    · dériver   : evaluation_courante ET paiements constructibles (charges =
                  paiements + provisions dossier sur la diagonale)
    """
    a_axe = bool(champs & set(_AXES))
    p = ('montant_paye' in champs) and a_axe
    c = ('montant_charge' in champs) and a_axe
    d = ('evaluation_courante' in champs) and p
    return {'peut_construire_paiements': p,
            'peut_construire_charges':   c,
            'peut_deriver_charges':      d}


# =============================================================================
#  FONCTIONS PUBLIQUES
# =============================================================================
def charger_mapping_triangle(chemin) -> TriangleSchema:
    """Charge un schéma de mapping depuis un YAML."""
    return TriangleSchema.depuis_yaml(chemin)


def valider_mapping_triangle(schema: TriangleSchema) -> Tuple[str, ...]:
    """Contrôle STATIQUE (sans données). Lève MappingTriangleIncoherent si une
    cible est inconnue du vocabulaire, ou si deux colonnes visent la même cible.

    Retourne le tuple des colonnes client dont la cible était AMBIGUË (rattachée
    par défaut) — vide si aucune. Ne lève PAS sur l'ambiguïté : elle est signalée.
    """
    catalogue = _catalogue(schema.kind)

    cibles: List[str] = []
    ambigues: List[str] = []
    inconnues: List[str] = []
    for col_client, cible in schema.correspondances.items():
        canon, ambigu = _reconnaitre(cible)
        # Une cible peut être écrite directement (champ canonique) ou via un terme
        # ambigu (montant → montant_paye). Tout le reste est une erreur.
        cible_norm = _normaliser(cible)
        if cible_norm in catalogue:
            cibles.append(cible_norm)
        elif ambigu and canon in catalogue:
            cibles.append(canon)
            ambigues.append(col_client)
        else:
            inconnues.append(cible)

    if inconnues:
        raise MappingTriangleIncoherent(
            f"Mapping (kind={schema.kind}) : cible(s) inconnue(s) {sorted(set(inconnues))}. "
            f"Cibles valides : {sorted(catalogue)}.")

    doublons = sorted({c for c in cibles if cibles.count(c) > 1})
    if doublons:
        raise MappingTriangleIncoherent(
            f"Mapping (kind={schema.kind}) : plusieurs colonnes client visent la "
            f"même cible {doublons}.")

    return tuple(ambigues)


def appliquer_mapping_triangle(
    df: pd.DataFrame, schema: TriangleSchema,
) -> Tuple[pd.DataFrame, RapportMappingTriangle]:
    """Valide, renomme le df vers le vocabulaire canonique, rend (df, rapport).

    LÈVE si le tableau ne permet RIEN de constructible ni exploitable :
      · annee_survenance absent, OU
      · aucune mesure (montant_paye / montant_charge / evaluation_courante), OU
      · (kind=primes) prime absente.
    Sinon : ne lève pas — le rapport décrit ce qui est faisable.
    """
    ambigues = valider_mapping_triangle(schema)  # lève si incohérent

    cols = list(df.columns)
    # cible normalisée + résolution des termes ambigus (montant → montant_paye)
    vivantes = {}
    for col_client, cible in schema.correspondances.items():
        if col_client in cols:
            cible_norm = _normaliser(cible)
            if cible_norm in _CANONIQUES:
                vivantes[col_client] = cible_norm
            else:
                canon, _ = _reconnaitre(cible)
                vivantes[col_client] = canon
    mortes = tuple(sorted(k for k in schema.correspondances if k not in cols))

    # Collision : le renommage créerait-il deux colonnes de même nom ?
    finaux = [vivantes.get(c, c) for c in cols]
    if len(set(finaux)) != len(finaux):
        collisions = sorted({n for n in finaux if finaux.count(n) > 1})
        raise MappingTriangleIncoherent(
            f"Mapping (kind={schema.kind}) : le renommage crée des colonnes en "
            f"double {collisions}.")

    df_renomme = df.rename(columns=vivantes)
    catalogue = _catalogue(schema.kind)
    champs_couverts = sorted(set(df_renomme.columns) & catalogue)

    _lever_si_inexploitable(schema.kind, set(champs_couverts))

    caps = _capacites_depuis_champs(set(champs_couverts))
    rapport = RapportMappingTriangle(
        kind=schema.kind, source=schema.source or schema.client,
        n_renommees=len(vivantes),
        champs_couverts=tuple(champs_couverts),
        peut_construire_paiements=caps['peut_construire_paiements'],
        peut_construire_charges=caps['peut_construire_charges'],
        peut_deriver_charges=caps['peut_deriver_charges'],
        mesures_ambigues=ambigues,
        colonnes_client_non_mappees=tuple(
            str(c) for c in df_renomme.columns if c not in catalogue),
        correspondances_mortes=mortes,
    )
    if ambigues:
        logger.warning(
            "Mapping A7 : colonne(s) %s à cible ambiguë — rattachée(s) aux paiements "
            "par défaut. Préciser montant_paye ou montant_charge dans le mapping.",
            list(ambigues))
    return df_renomme, rapport


def preparer_tableau(
    df: pd.DataFrame, chemin_mapping: Optional[str], kind: str = 'sinistres',
) -> Tuple[pd.DataFrame, Optional[RapportMappingTriangle]]:
    """Point d'entrée. chemin_mapping=None → PASSTHROUGH : les colonnes sont
    reconnues par leur nom (synonymes), renommées vers le vocabulaire canonique,
    et un rapport est produit. Sinon : charge le YAML et applique le mapping.
    """
    if chemin_mapping is not None:
        return appliquer_mapping_triangle(df, charger_mapping_triangle(chemin_mapping))

    # Passthrough : reconnaissance par nom (aucun mapping fourni). Une colonne
    # AMBIGUË garde son nom comme cible pour que la validation la signale ; un
    # synonyme clair est pré-résolu vers son champ canonique.
    #
    # FILTRE PAR KIND — une colonne reconnue HORS du vocabulaire demandé est
    # ignorée, pas proposée en cible : sur une table « tout en un » (sinistres +
    # une colonne de primes), la reconnaître puis la soumettre à la validation
    # faisait lever alors qu'il n'y a rien d'anormal. Effet direct : la même table
    # peut être lue en 'sinistres' PUIS en 'primes', chaque passe ignorant ce qui
    # ne la concerne pas.
    catalogue = _catalogue(kind)
    correspondances: Dict[str, str] = {}
    for col in df.columns:
        canon, ambigu = _reconnaitre(col)
        if canon is not None and canon in catalogue:
            correspondances[str(col)] = _normaliser(col) if ambigu else canon
    if not correspondances:
        _lever_si_inexploitable(kind, set())   # aucune colonne reconnue → lève
    schema = TriangleSchema(kind=kind, correspondances=correspondances,
                            source='(passthrough)')
    return appliquer_mapping_triangle(df, schema)


def capacites(source: Union[pd.DataFrame, List, Tuple]) -> Dict[str, Any]:
    """« Que peut-on construire à partir de ce tableau ? » — SANS appliquer de
    mapping ni muter les données. Reconnaît les colonnes par leur nom et rend les
    trois booléens + les champs reconnus + les colonnes ambiguës.
    """
    colonnes = list(source.columns) if isinstance(source, pd.DataFrame) else list(source)
    champs: set = set()
    ambigues: List[str] = []
    for col in colonnes:
        canon, ambigu = _reconnaitre(col)
        if canon is not None:
            champs.add(canon)
            if ambigu:
                ambigues.append(str(col))
    caps = _capacites_depuis_champs(champs)
    return {**caps,
            'champs_reconnus': sorted(champs),
            'mesures_ambigues': ambigues}


# =============================================================================
#  INTERNES
# =============================================================================
def _lever_si_inexploitable(kind: str, champs: set) -> None:
    """Lève MappingTriangleIncoherent si le tableau ne porte RIEN d'exploitable."""
    if kind == 'primes':
        manquants = CHAMPS_PRIMES - champs
        if manquants:
            raise MappingTriangleIncoherent(
                f"Mapping primes : champ(s) obligatoire(s) absent(s) {sorted(manquants)}.")
        return

    if 'annee_survenance' not in champs:
        raise MappingTriangleIncoherent(
            "Mapping sinistres : 'annee_survenance' absente — aucun triangle possible.")
    if not (champs & set(_MESURES)):
        raise MappingTriangleIncoherent(
            "Mapping sinistres : aucune mesure (montant_paye / montant_charge / "
            "evaluation_courante) — rien à agréger.")
