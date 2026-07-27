# =============================================================================
#  ActuarIA — Bloc II, module 7 : FAÇADE DE PRÉPARATION DES TRIANGLES
#  nv_triangle.py
# =============================================================================
#
#  RESPONSABILITÉ — ORCHESTRER les modules 1 à 6, et RIEN d'autre. Cette façade
#  n'implémente aucune logique métier : pas de pivot, pas de cumul, pas de
#  masquage de zone future, pas de classement par seuil, pas de contrôle qualité.
#  Chaque étape délègue au module qui en a la charge. Un test AST vérifie cette
#  absence de duplication (test_nv_triangle.py, T7).
#
#  ORDRE DU FLUX (≠ ordre des numéros de modules) :
#      1 lire → 2/3 mapper → 5 SÉPARER → 4 construire (×2) → 6 diagnostiquer
#  Le module 5 vient AVANT le 4 : une cellule de triangle est une somme, et on ne
#  dé-somme pas — la séparation exige les données individuelles.
#
#  CONTRATS HÉRITÉS, honorés ici (chacun a son test) :
#   · MODULE 4 — après une séparation, les DEUX constructions reçoivent le REPÈRE
#     D'ANNÉES de la source complète, sans quoi un sous-ensemble perdrait les
#     années où il n'a aucun sinistre et sa zone connue rétrécirait.
#   · MODULE 4 — `triangle_reference` ('paiements' | 'charges') est un réglage
#     GLOBAL du run, jamais un choix par méthode : le BE est une moyenne pondérée,
#     mélanger les bases produirait un agrégat incohérent.
#   · MODULE 4 — DETTE IMPÉRATIVE : les deux triangles restent accessibles pour
#     que N4 calcule `ultime_charges − payé_à_date` (et non `− charges_à_date`,
#     qui donnerait l'IBNR pur, BE/SCR/RM sous-estimés). La façade ne fait PAS ce
#     calcul ; elle garantit que `diagonale_paiements` reste disponible.
#   · MODULE 5 — séparation demandée sur un agrégat → AVERTIR et POURSUIVRE sans
#     séparation ; jamais faire tomber tout le run pour ça.
#   · MODULE 6 — diagnostiquer paiements / charges / attritionnel, JAMAIS le
#     triangle « grands » (clairsemé par nature : fausse alerte systématique), et
#     transmettre la VRAIE LoB (le builder envoyait 'generique' en dur).
#
#  ⚠️ LE STATUT GLOBAL NE DÉPEND PAS DU DIAGNOSTIC (décision tranchée). Le
#  diagnostic INFORME : il est intégralement exposé (par triangle, et ses alertes
#  préfixées `[diagnostic]`), mais ne colore aucun statut. Deux raisons : (1) la
#  gouvernance « la qualité doit-elle colorer un dossier ? » est une décision de
#  phase 3, la coupler ici la préempterait par effet de bord ; (2) le contrôle C1
#  du module 6 a un défaut CONNU — il compte toute baisse > 1 % comme une
#  violation et bascule en ROUGE dès 3, si bien qu'un recours légitime (≥ 2 %)
#  coûte systématiquement 15 points à une donnée saine. `diagnostic_statut_le_
#  plus_severe` est calculé et exposé pour que le couplage se fasse EN UNE LIGNE
#  le jour où la gouvernance tranchera et où C1 sera corrigé.
#
#  Agnostique de l'interface : aucun import Streamlit ni agent. Testable seul.
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from direction_non_vie.services.nv_triangle_construction import (
    TrianglesConstruits, construire_triangles,
)
from direction_non_vie.services.nv_triangle_diagnostics import diagnostiquer_triangle
from direction_non_vie.services.nv_triangle_io import lire_source
from direction_non_vie.services.nv_triangle_mapping import (
    RapportMappingTriangle, TriangleSchema, appliquer_mapping_triangle,
    preparer_tableau,
)
from direction_non_vie.services.nv_triangle_separation import (
    SeparationLLT, avertir_si_agregat, separer_par_seuil,
)

logger = logging.getLogger('actuaria.nv.facade')

__all__ = [
    'PreparationTriangles', 'preparer_triangles', 'preparer_pour_agent',
]

_SEVERITE = {'VERT': 0, 'AMBRE': 1, 'ROUGE': 2}


# =============================================================================
#  RÉSULTAT
# =============================================================================
@dataclass(frozen=True)
class PreparationTriangles:
    """Tout ce que la préparation a produit — rien n'est perdu en route."""
    triangles:        TrianglesConstruits            # le jeu RETENU (attritionnel si séparé)
    triangles_total:  Optional[TrianglesConstruits]  # portefeuille entier, avant séparation
    triangles_grands: Optional[TrianglesConstruits]  # présent ssi séparation effectuée
    separation:       Optional[SeparationLLT]
    diagnostics:      Dict[str, Dict[str, Any]]      # {'paiements'|'charges'|'attritionnel'}
    rapport_mapping:  Optional[RapportMappingTriangle]
    rapport_mapping_primes: Optional[RapportMappingTriangle]
    diagnostic_statut_le_plus_severe: str            # EXPOSÉ, non consommé par le statut
    rapport: Dict[str, Any] = field(default_factory=dict)

    def synthese(self) -> Dict[str, Any]:
        """Vue json-sérialisable (types natifs) — livrables / audit."""
        return {
            'statut':   self.rapport.get('statut'),
            'etapes':   dict(self.rapport.get('etapes', {})),
            'alertes':  list(self.rapport.get('alertes', [])),
            'infos':    list(self.rapport.get('infos', [])),
            'triangles': self.triangles.synthese(),
            'separation': self.separation.synthese() if self.separation else None,
            'diagnostics': {k: {'score': v.get('score'), 'statut': v.get('statut')}
                            for k, v in self.diagnostics.items()},
            'diagnostic_statut_le_plus_severe': self.diagnostic_statut_le_plus_severe,
            'mapping': (self.rapport_mapping.synthese()
                        if self.rapport_mapping else None),
        }


# =============================================================================
#  ÉTAPES — chacune délègue, aucune ne calcule
# =============================================================================
def _etape_lecture(source, nom_onglet: Optional[str], rapport: Dict,
                   libelle: str = 'lecture'):
    """Étape A — délègue au module 1 si la source est un fichier ; sinon laisse
    passer l'objet en mémoire tel quel.

    `libelle` distingue les deux sources (sinistres / charges) : sans lui, la
    seconde lecture écraserait la trace de la première dans le rapport.
    """
    if source is None:
        rapport['etapes'][libelle] = 'aucune source'
        return None
    if isinstance(source, (pd.DataFrame, np.ndarray, list, dict)):
        rapport['etapes'][libelle] = 'ignoree (source en memoire)'
        return source
    lu = lire_source(source, nom_onglet=nom_onglet)
    rapport['etapes'][libelle] = f"ok ({lu['format_fichier']})"
    _absorber(rapport, lu.get('rapport', {}), libelle)
    return lu['brut']


def _schema_depuis_dict(mapping: Dict[str, str], kind: str) -> TriangleSchema:
    """Convertit le `schema_mapping` historique en TriangleSchema du module 2.

    ⚠️ LES DEUX CONVENTIONS SONT INVERSES, et s'y tromper mismapperait les
    colonnes en silence :
      · agent.py / validator : {nom_STANDARD: nom_dans_le_FICHIER}
        ex. {'montant': 'cout_total', 'annee_survenance': 'ay'}
      · module 2             : {nom_CLIENT: champ_CANONIQUE}
        ex. {'cout_total': 'montant_paye', 'ay': 'annee_survenance'}
    On inverse donc le dict. Les noms standard hérités et ambigus (`montant`)
    sont résolus par le module 2 lui-même, avec son alerte d'ambiguïté.
    """
    return TriangleSchema(kind=kind, source='(schema_mapping)',
                          correspondances={str(fichier): str(standard)
                                           for standard, fichier in mapping.items()})


def _etape_mapping(brut, chemin_mapping, kind: str, rapport: Dict,
                   libelle: str) -> Tuple[Any, Optional[RapportMappingTriangle]]:
    """Étape B — délègue au module 2. Une MATRICE est positionnelle : aucun
    mapping de colonnes n'a de sens, on la laisse passer.

    `chemin_mapping` accepte un chemin YAML, un DICT `{standard: fichier}`
    (convention historique d'agent.py, cf. _schema_depuis_dict), ou None
    (passthrough par reconnaissance de noms).
    """
    if not isinstance(brut, pd.DataFrame):
        rapport['etapes'][f'mapping_{libelle}'] = 'ignore (matrice positionnelle)'
        return brut, None
    if isinstance(chemin_mapping, dict):
        df, rap = appliquer_mapping_triangle(
            brut, _schema_depuis_dict(chemin_mapping, kind))
        rapport['etapes'][f'mapping_{libelle}'] = 'ok (schema_mapping)'
    else:
        df, rap = preparer_tableau(brut, chemin_mapping, kind=kind)
        rapport['etapes'][f'mapping_{libelle}'] = 'ok'
    if rap is not None:
        for col in rap.mesures_ambigues:
            rapport['alertes'].append(
                f"[mapping] colonne '{col}' à cible ambiguë — rattachée aux paiements.")
        for col in rap.correspondances_mortes:
            rapport['alertes'].append(
                f"[mapping] correspondance morte '{col}' (absente du fichier).")
    return df, rap


def _etape_separation(df, seuil_llt: Optional[float], base_classement: str,
                      rapport: Dict) -> Optional[SeparationLLT]:
    """Étape C — délègue au module 5. Une séparation demandée sur un agrégat
    AVERTIT et laisse le flux continuer : jamais de blocage total pour ça."""
    if seuil_llt is None:
        rapport['etapes']['separation'] = 'non demandee'
        return None
    message = avertir_si_agregat(df)
    if message is not None:
        rapport['etapes']['separation'] = 'ignoree (donnees agregees)'
        rapport['alertes'].append(f"[separation] {message}")
        return None
    sep = separer_par_seuil(df, seuil_llt, base_classement=base_classement)
    rapport['etapes']['separation'] = f"ok ({sep.n_grands} ligne(s) grands sinistres)"
    _absorber(rapport, sep.rapport, 'separation')
    rapport['infos'].append(f"[separation] {sep.avertissement_volume}")
    return sep


def _etape_construction(paiements, charges, sep: Optional[SeparationLLT],
                        rapport: Dict, **kw
                        ) -> Tuple[TrianglesConstruits, Optional[TrianglesConstruits],
                                   Optional[TrianglesConstruits]]:
    """Étape D — délègue au module 4. Sans séparation : une construction. Avec
    séparation : le TOTAL d'abord (il fournit le REPÈRE et sert de contrôle de
    cohérence), puis attritionnel et grands SUR CE REPÈRE (contrat du module 4)."""
    total = construire_triangles(paiements=paiements, charges=charges, **kw)
    if sep is None:
        rapport['etapes']['construction'] = 'ok (sans separation)'
        _absorber(rapport, total.rapport, 'construction')
        return total, total, None

    repere = (total.annee_min, *total.reference.shape)
    attrit = construire_triangles(paiements=sep.attritionnel, charges=charges,
                                  annees_reference=repere, **kw)
    grands = construire_triangles(paiements=sep.grands, charges=None,
                                  annees_reference=repere, **kw)
    rapport['etapes']['construction'] = f"ok (separee, repere {repere})"
    _absorber(rapport, attrit.rapport, 'construction')
    return attrit, total, grands


def _etape_diagnostic(retenus: TrianglesConstruits, sep: Optional[SeparationLLT],
                      lob: str, annee_debut: Optional[int], rapport: Dict
                      ) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """Étape E — délègue au module 6, sur les triangles RETENUS uniquement.

    JAMAIS sur le triangle « grands » : clairsemé par nature, il produirait une
    alerte systématique sans signification. La VRAIE LoB est transmise (le
    builder envoyait 'generique' en dur).
    """
    an = annee_debut if annee_debut is not None else retenus.annee_min
    cibles = {('attritionnel' if sep is not None else 'paiements'): retenus.paiements,
              'charges': retenus.charges}
    diags: Dict[str, Dict[str, Any]] = {}
    for nom, C in cibles.items():
        if C is None:
            continue
        try:
            d = diagnostiquer_triangle(C, annee_debut=an, lob=lob)
        except Exception as e:                    # un diagnostic raté n'arrête rien
            rapport['alertes'].append(f"[diagnostic] '{nom}' échoué : {e}")
            continue
        diags[nom] = d
        for c in d.get('controles', []):
            if c.get('statut') == 'ROUGE':
                rapport['infos'].append(
                    f"[diagnostic] {nom} [{c['code']}] {str(c.get('message'))[:110]}")
    pire = max((d.get('statut', 'VERT') for d in diags.values()),
               key=lambda s: _SEVERITE.get(s, 0), default='VERT')
    rapport['etapes']['diagnostic'] = f"ok ({len(diags)} triangle(s))"
    return diags, pire


# =============================================================================
#  CONSOLIDATION
# =============================================================================
def _absorber(rapport: Dict, source: Dict, etape: str) -> None:
    """Recopie les alertes/infos d'un sous-module en les PRÉFIXANT par l'étape.

    La liste consolidée est une VUE : les objets d'origine restent exposés
    entiers dans PreparationTriangles, donc rien n'est perdu.
    """
    for cle in ('alertes', 'infos'):
        for message in source.get(cle, []):
            rapport[cle].append(f"[{etape}] {message}")


def _mode_resolu(retenus: TrianglesConstruits, mode_paiements: str) -> str:
    """Mode RÉELLEMENT retenu, pour le champ `mode_detecte` des livrables.

    Rapporter 'auto' serait une perte d'information : l'ancien N1 affichait la
    cumulativité DÉTECTÉE. On redemande donc le verdict à la source unique
    (delegation, pas duplication — même politique que le contrôle C1).
    """
    if mode_paiements != 'auto' or retenus.reference is None:
        return mode_paiements
    from direction_non_vie.services.nv_triangle_construction import (
        detecter_cumulativite,
    )
    return detecter_cumulativite(retenus.reference)


def _finaliser_rapport(rapport: Dict, retenus: TrianglesConstruits,
                       mode_paiements: str) -> None:
    """Statut global + les clés de forme qu'`agent.py` consomme (cf. adaptateur).

    ⚠️ LE STATUT NE CONSOMME PAS LE DIAGNOSTIC (décision tranchée) : le diagnostic
    informe, il ne colore pas. Cf. l'en-tête du module pour les deux raisons.
    ROUGE si une étape indispensable a échoué, AMBRE s'il y a des alertes, VERT
    sinon.
    """
    if any(str(v).startswith('echec') for v in rapport['etapes'].values()):
        rapport['statut'] = 'ROUGE'
    else:
        rapport['statut'] = 'AMBRE' if rapport['alertes'] else 'VERT'
    rapport.update({'taille': f"{retenus.n_annees}×{retenus.n_dev}",
                    'n_annees': retenus.n_annees, 'n_dev': retenus.n_dev,
                    'mode_detecte': _mode_resolu(retenus, mode_paiements)})


# =============================================================================
#  API PUBLIQUE
# =============================================================================
def preparer_triangles(
    source,
    *,
    source_charges=None,
    primes=None,
    nom_onglet: Optional[str] = None,
    chemin_mapping: Optional[str] = None,
    chemin_mapping_primes: Optional[str] = None,
    seuil_llt: Optional[float] = None,
    base_classement: str = 'auto',
    triangle_reference: str = 'paiements',
    methodes_demandees: Sequence[str] = (),
    mode_paiements: str = 'auto',
    mode_charges: str = 'auto',
    lob: str = 'generique',
    annee_debut: Optional[int] = None,
) -> PreparationTriangles:
    """Porte d'entrée unique : de la source brute aux triangles diagnostiqués.

    Enchaîne lire (1) → mapper (2) → séparer (5) → construire (4) → diagnostiquer
    (6), en déléguant chaque étape. Aucune logique métier n'est réimplémentée ici.

    ERREURS PARTIELLES — le flux CONTINUE avec ce qui est possible : séparation
    demandée sur un agrégat (avertie, ignorée), primes absentes pour une méthode
    qui les exige (`methodes_bloquees`), charges absentes, diagnostic en échec.

    LÈVE (ConstructionImpossible) dans les trois seuls cas où poursuivre
    produirait un résultat faux : aucun triangle constructible · cumulativité
    AMBIGUË non déclarée (un cumulé à recours ressemble à un incrémental) ·
    `triangle_reference` désignant un triangle qui n'a pas pu être construit.

    Le statut global NE DÉPEND PAS du diagnostic ; `diagnostic_statut_le_plus_
    severe` l'expose sans le consommer.
    """
    rapport: Dict[str, Any] = {'alertes': [], 'infos': [], 'etapes': {}}

    df, df_charges, rap_map = _preparer_sources(
        source, source_charges, nom_onglet, chemin_mapping, rapport)
    primes_vec, rap_primes = _preparer_primes(primes, chemin_mapping_primes, rapport)

    sep = _etape_separation(df, seuil_llt, base_classement, rapport)

    retenus, total, grands = _etape_construction(
        df, df_charges, sep, rapport,
        primes=primes_vec, methodes_demandees=methodes_demandees,
        mode_paiements=mode_paiements, mode_charges=mode_charges,
        base_reference=triangle_reference)

    if retenus.methodes_bloquees:
        rapport['alertes'].append(
            f"[construction] primes absentes : {list(retenus.methodes_bloquees)} "
            f"ne pourra/pourront pas s'exécuter.")

    diags, pire = _etape_diagnostic(retenus, sep, lob, annee_debut, rapport)
    _finaliser_rapport(rapport, retenus, mode_paiements)

    return PreparationTriangles(
        triangles=retenus, triangles_total=total, triangles_grands=grands,
        separation=sep, diagnostics=diags,
        rapport_mapping=rap_map, rapport_mapping_primes=rap_primes,
        diagnostic_statut_le_plus_severe=pire, rapport=rapport)


def preparer_pour_agent(source, **kwargs
                        ) -> Tuple[np.ndarray, Optional[np.ndarray],
                                   Optional[np.ndarray], Dict[str, Any]]:
    """ADAPTATEUR de compatibilité — même flux, sortie au format qu'`agent.py`
    consomme déjà : `(C, C_engage, primes, rapport_n1)`.

    Le rapport porte les sept clés lues aujourd'hui par agent.py : `statut`
    (l.571, pilote le RAG), `alertes`, `infos`, `taille`, `n_annees`, `n_dev`,
    `mode_detecte`. Le câblage (module 8) se réduit ainsi au remplacement d'une
    ligne, sans refonte d'agent.py.
    """
    prep = preparer_triangles(source, **kwargs)
    t = prep.triangles
    rapport = dict(prep.rapport)
    rapport['preparation'] = prep            # objet complet, rien n'est perdu
    return t.reference, t.charges, t.primes, rapport


# =============================================================================
#  INTERNE
# =============================================================================
def _preparer_sources(source, source_charges, nom_onglet: Optional[str],
                      chemin_mapping: Optional[str], rapport: Dict
                      ) -> Tuple[Any, Any, Optional[RapportMappingTriangle]]:
    """Lit et mappe les deux sources (étapes A et B).

    Cas « TOUT EN UN » : si aucune source de charges n'est fournie mais que la
    table des sinistres porte 'montant_charge', c'est LA MÊME table qui alimente
    les deux triangles — une table peut fournir plusieurs mesures (module 2).
    """
    brut = _etape_lecture(source, nom_onglet, rapport, 'lecture')
    brut_charges = _etape_lecture(source_charges, nom_onglet, rapport,
                                  'lecture_charges')
    df, rap_map = _etape_mapping(brut, chemin_mapping, 'sinistres',
                                 rapport, 'sinistres')
    df_charges, _ = _etape_mapping(brut_charges, chemin_mapping, 'sinistres',
                                   rapport, 'charges')
    if df_charges is None and isinstance(df, pd.DataFrame) \
            and 'montant_charge' in df.columns:
        df_charges = df
        rapport['infos'].append(
            "[mapping] table unique portant paiements ET charges — les deux "
            "triangles en sont dérivés.")
    return df, df_charges, rap_map


def _preparer_primes(primes, chemin_mapping_primes: Optional[str], rapport: Dict
                     ) -> Tuple[Any, Optional[RapportMappingTriangle]]:
    """Primes : soit un vecteur déjà prêt, soit une TABLE à mapper (kind='primes').

    La double passe sur une même table (sinistres puis primes) est autorisée
    depuis le correctif du module 2 : chaque passe ignore l'autre vocabulaire.
    """
    if not isinstance(primes, pd.DataFrame):
        return primes, None
    df, rap = _etape_mapping(primes, chemin_mapping_primes, 'primes', rapport, 'primes')
    if isinstance(df, pd.DataFrame) and 'prime' in df.columns:
        colonnes = ['annee_survenance', 'prime']
        agrege = df[colonnes].groupby('annee_survenance', as_index=False)['prime'].sum()
        return agrege['prime'].to_numpy(dtype=float), rap
    rapport['alertes'].append(
        "[mapping] table de primes sans colonne 'prime' exploitable — primes ignorées.")
    return None, rap
