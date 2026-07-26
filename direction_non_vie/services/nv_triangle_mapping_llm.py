# =============================================================================
#  ActuarIA — Bloc II, module 3 : PROPOSITION LLM (rôles d'onglets + mapping)
#  nv_triangle_mapping_llm.py
# =============================================================================
#
#  RESPONSABILITÉ — Claude PROPOSE, l'actuaire VALIDE. Rien n'est jamais appliqué
#  automatiquement. Deux propositions distinctes :
#    1. proposer_roles_onglets()   — quel RÔLE joue chaque onglet, d'après son
#                                    CONTENU (le nom n'est qu'un signal secondaire).
#    2. proposer_mapping_colonnes() — quel champ canonique vise chaque colonne.
#
#  DEUX FONCTIONS, PAS UN APPEL COMBINÉ : le vocabulaire cible du mapping DÉPEND
#  du rôle identifié (CHAMPS_SINISTRES à 6 champs vs CHAMPS_PRIMES à 2). Les
#  enchaîner en un seul appel obligerait le modèle à choisir son propre
#  vocabulaire puis à s'y tenir — surface d'erreur inutile. Et l'actuaire valide
#  les rôles AVANT qu'un mapping soit construit dessus.
#
#  ASYMÉTRIE DE VALIDATION, VOLONTAIRE :
#    · MAPPING → STRICT. La proposition repasse par valider_mapping_triangle()
#      du module 2 : une cible inventée lève MappingTriangleIncoherent, EXACTEMENT
#      comme un YAML humain erroné. Aucun passe-droit pour le LLM — un mauvais
#      mapping RENOMMERAIT des colonnes, donc corromprait des données.
#    · RÔLES  → TOLÉRANT. Une entrée douteuse (rôle hors énumération, onglet
#      halluciné) est ÉCARTÉE et TRACÉE, sans faire tomber les bonnes. Un rôle
#      n'est qu'une proposition soumise à validation humaine, jamais appliquée
#      seule : tout rejeter perdrait de l'information utile.
#
#  ANTI-DÉRIVE — les prompts sont CONSTRUITS à partir des constantes du module 2
#  (CHAMPS_SINISTRES / CHAMPS_PRIMES), jamais recopiés à la main. Si le
#  vocabulaire canonique évolue, le prompt suit automatiquement ; sans ça un
#  prompt figé ferait proposer des cibles périmées que la validation rejetterait
#  systématiquement. Un test le prouve.
#
#  S'inspire de l'ESPRIT de core/mapping_llm.py (tarif, clos) sans en dépendre ni
#  en copier le code. Divergences VOLONTAIRES vs le tarif : deux fonctions au lieu
#  d'une ; validation tolérante pour les rôles ; vocabulaire interne et fixe au
#  lieu d'un plan signé.
#
#  Le paquet `anthropic` n'est importé QU'À l'appel réel — jamais requis pour
#  importer ce module. Agnostique de l'interface (aucun import Streamlit/agent).
# =============================================================================

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

import pandas as pd

from direction_non_vie.services.nv_triangle_mapping import (
    CHAMPS_PRIMES, CHAMPS_SINISTRES, TriangleSchema, valider_mapping_triangle,
)

logger = logging.getLogger('actuaria.nv.mapping_llm')

__all__ = [
    'ROLES', 'RolePropose', 'RapportRolesLLM', 'MappingTriangleLLMIndisponible',
    'proposer_roles_onglets', 'proposer_mapping_colonnes',
]

# Modèle et température — même convention que le reste du projet. temperature=0 :
# reproductibilité recherchée (une proposition doit être stable d'un run à l'autre).
_MODELE_CLAUDE = 'claude-sonnet-5'
_TEMPERATURE_DEFAUT = 0.0
_MAX_TOKENS = 2000

_MSG_MANUEL = ("mappez manuellement (nv_triangle_mapping / un YAML de mapping) — "
               "la proposition n'est qu'un accélérateur, jamais un passage obligé.")

# ── Les cinq rôles, avec ce que chacun implique en aval ──────────────────────
ROLES: Dict[str, str] = {
    'triangle_paiements': "matrice deja construite : triangle des PAIEMENTS cumules "
                          "(lignes = annees de survenance, colonnes = developpement)",
    'triangle_charges':   "matrice deja construite : triangle des CHARGES (payes + "
                          "provisions dossier)",
    'sinistres':          "tableau LONG : une ligne par sinistre ou par cellule "
                          "(annee de survenance, developpement, montants)",
    'primes':             "tableau des PRIMES par annee de survenance "
                          "(typiquement une ligne par annee)",
    'inconnu':            "ni l'un ni l'autre : notice, parametres, feuille vide, "
                          "contenu non exploitable",
}

# Rôles dont le contenu est POSITIONNEL : aucun mapping de colonnes n'a de sens.
ROLES_MATRICE: Tuple[str, ...] = ('triangle_paiements', 'triangle_charges')

# Libellés actuariels des champs canoniques — c'est ce qui permet au modèle de
# distinguer payé / charge / provision. Les CLÉS ne sont jamais écrites en dur :
# elles sont filtrées contre CHAMPS_SINISTRES | CHAMPS_PRIMES à la construction
# du prompt (cf. _lignes_vocabulaire), donc un champ ajouté au module 2 sans
# libellé ici reste annoncé au modèle plutôt que d'être silencieusement omis.
_LIBELLES_CHAMPS: Dict[str, str] = {
    'annee_survenance':    "annee de survenance du sinistre (axe des lignes)",
    'annee_developpement': "age de developpement en periodes (0, 1, 2, ...)",
    'annee_paiement':      "annee de reglement (le developpement s'en deduit : "
                           "paiement moins survenance)",
    'montant_paye':        "montant PAYE (reglements)",
    'montant_charge':      "montant de CHARGE (paye + provision dossier)",
    'evaluation_courante': "PROVISION dossier a la date d'arrete (evaluation en cours)",
    'prime':               "prime acquise de l'annee de survenance",
}


class MappingTriangleLLMIndisponible(RuntimeError):
    """La proposition n'a pas pu être produite : paquet `anthropic` absent, clé
    absente, réseau/HTTP, réponse illisible, ou proposition vide. JAMAIS un crash
    opaque — le message dit quoi faire (mapper à la main)."""


# =============================================================================
#  RAPPORT DES RÔLES
# =============================================================================
@dataclass(frozen=True)
class RolePropose:
    role:          str
    confiance:     str    # 'haute' | 'moyenne' | 'basse'
    justification: str


@dataclass(frozen=True)
class RapportRolesLLM:
    roles:            Mapping[str, RolePropose]   # {onglet: proposition retenue}
    onglets_ignores:  Tuple[str, ...]             # soumis, sans proposition exploitable
    entrees_ecartees: Tuple[str, ...]             # écartées + raison (traçabilité)

    def synthese(self) -> Dict[str, Any]:
        """Vue json-sérialisable (types natifs) — livrables / audit."""
        return {
            'roles': {o: {'role': p.role, 'confiance': p.confiance,
                          'justification': p.justification}
                      for o, p in self.roles.items()},
            'onglets_ignores':  list(self.onglets_ignores),
            'entrees_ecartees': list(self.entrees_ecartees),
        }


# =============================================================================
#  CONSTRUCTION DES PROMPTS (dérivée du module 2 — anti-dérive)
# =============================================================================
def _lignes_vocabulaire(kind: str) -> str:
    """Vocabulaire canonique du module 2, en lignes « champ : rôle actuariel ».

    Les champs viennent de CHAMPS_SINISTRES / CHAMPS_PRIMES — jamais d'une liste
    recopiée. Un champ sans libellé connu est quand même annoncé (libellé par
    défaut) plutôt qu'omis en silence.
    """
    champs = CHAMPS_PRIMES if kind == 'primes' else CHAMPS_SINISTRES
    return "\n".join(
        f"- {c} : {_LIBELLES_CHAMPS.get(c, 'champ canonique A7')}"
        for c in sorted(champs))


def _apercu(df: pd.DataFrame, n_lignes: int) -> str:
    """Colonnes + dtypes + n lignes d'exemple (CSV) — l'aperçu envoyé au modèle."""
    colonnes = "\n".join(f"- {c} : {df[c].dtype}" for c in df.columns)
    try:
        exemple = df.head(n_lignes).to_csv(index=False).strip()
    except Exception:                       # types exotiques : on dégrade l'aperçu
        exemple = "(apercu indisponible)"
    return (f"dimensions : {df.shape[0]} lignes x {df.shape[1]} colonnes\n"
            f"colonnes (nom : type) :\n{colonnes}\n"
            f"{n_lignes} premieres lignes (CSV) :\n{exemple}")


def _prompt_systeme_roles() -> str:
    roles = "\n".join(f"- {r} : {d}" for r, d in ROLES.items())
    return (
        "Tu es un assistant actuariel. Ta tache : dire quel ROLE joue chaque onglet "
        "d'un classeur, en analysant son CONTENU.\n"
        f"Roles possibles (utilise EXACTEMENT ces identifiants) :\n{roles}\n"
        "Regles imperatives :\n"
        "- Reponds UNIQUEMENT par un objet JSON, sans texte autour, sans balise de "
        'code, de la forme {"nom_onglet": {"role": "...", "confiance": "haute|'
        'moyenne|basse", "justification": "..."}}.\n'
        "- Le nom de l'onglet est un indice SECONDAIRE : il peut etre trompeur ou "
        "absent. Ta justification doit s'appuyer sur le CONTENU REEL observe "
        "(forme des donnees, colonnes, ordres de grandeur, nombre de lignes) et "
        "CITER cet element de contenu. Ne justifie JAMAIS par le seul nom.\n"
        "- Dans le doute, reponds 'inconnu' avec une confiance basse : un onglet "
        "non classe (que l'actuaire tranchera) vaut mieux qu'un role errone.\n"
        "- N'invente aucun nom d'onglet : n'utilise que ceux qui te sont fournis."
    )


def _prompt_utilisateur_roles(onglets: Mapping[str, pd.DataFrame],
                              n_lignes_exemple: int) -> str:
    blocs = "\n\n".join(
        f"=== ONGLET '{nom}' ===\n{_apercu(df, n_lignes_exemple)}"
        for nom, df in onglets.items())
    return (f"{blocs}\n\n"
            "Donne le seul objet JSON des roles pour ces onglets.")


def _prompt_systeme_mapping(kind: str) -> str:
    return (
        "Tu es un assistant actuariel. Ta tache : proposer une correspondance "
        "entre les colonnes d'un tableau client et les champs canoniques attendus. "
        "Tu ne fais que rapprocher des noms de colonnes.\n"
        "Regles imperatives :\n"
        '- Reponds UNIQUEMENT par un objet JSON {"nom_colonne_client": '
        '"champ_canonique"}, sans texte, sans explication, sans balise de code.\n'
        "- Chaque VALEUR doit etre EXACTEMENT l'un des champs canoniques fournis. "
        "N'invente jamais un nom de champ.\n"
        "- Ne mappe une colonne QUE si tu es raisonnablement sur. Dans le doute, "
        "OMETS-la : une correspondance manquante (que l'actuaire completera) vaut "
        "mieux qu'une fausse correspondance.\n"
        "- N'associe jamais deux colonnes client au meme champ canonique.\n"
        "- Distingue avec soin le montant PAYE, le montant de CHARGE (paye + "
        "provision) et la PROVISION dossier seule : ce sont trois champs "
        "differents, ne les confonds pas."
    )


def _prompt_utilisateur_mapping(df: pd.DataFrame, kind: str,
                                n_lignes_exemple: int) -> str:
    return (f"TABLEAU CLIENT :\n{_apercu(df, n_lignes_exemple)}\n\n"
            f"CHAMPS CANONIQUES ATTENDUS (kind={kind}) :\n"
            f"{_lignes_vocabulaire(kind)}\n\n"
            'Reponds par le seul objet JSON {"nom_colonne_client": "champ_canonique"}.')


# =============================================================================
#  FRONTIÈRE API — SEUL point qui touche `anthropic` (patché en test)
# =============================================================================
def _appeler_claude(systeme: str, utilisateur: str, *, temperature: float) -> str:
    """Appelle Claude et rend le TEXTE brut de la réponse.

    Toute défaillance (paquet absent, clé absente, réseau, HTTP) est convertie en
    MappingTriangleLLMIndisponible avec un message actionnable. `anthropic` est
    importé ICI, jamais au chargement du module.
    """
    try:
        import anthropic
    except Exception as e:
        raise MappingTriangleLLMIndisponible(
            f"paquet 'anthropic' indisponible ({e}) — {_MSG_MANUEL}") from e

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise MappingTriangleLLMIndisponible(
            f"ANTHROPIC_API_KEY non definie — {_MSG_MANUEL}")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=_MODELE_CLAUDE, max_tokens=_MAX_TOKENS, temperature=temperature,
            system=systeme, messages=[{'role': 'user', 'content': utilisateur}],
        )
        return "".join(
            b.text for b in resp.content if getattr(b, 'type', None) == 'text')
    except MappingTriangleLLMIndisponible:
        raise
    except Exception as e:
        raise MappingTriangleLLMIndisponible(
            f"service de proposition indisponible ({e}) — {_MSG_MANUEL}") from e


def _extraire_objet_json(brut: str) -> Dict[str, Any]:
    """Isole et parse l'objet JSON de la réponse (tolère un préambule).

    Illisible ou non-objet → MappingTriangleLLMIndisponible.
    """
    texte = (brut or "").strip()
    i, j = texte.find('{'), texte.rfind('}')
    if i == -1 or j == -1 or j <= i:
        raise MappingTriangleLLMIndisponible(
            f"reponse du modele illisible (aucun objet JSON) — {_MSG_MANUEL}")
    try:
        objet = json.loads(texte[i:j + 1])
    except Exception as e:
        raise MappingTriangleLLMIndisponible(
            f"reponse du modele non parsable ({e}) — {_MSG_MANUEL}") from e
    if not isinstance(objet, dict):
        raise MappingTriangleLLMIndisponible(
            f"reponse du modele n'est pas un objet JSON — {_MSG_MANUEL}")
    return objet


# =============================================================================
#  API PUBLIQUE
# =============================================================================
def proposer_roles_onglets(
    onglets: Mapping[str, pd.DataFrame],
    *,
    n_lignes_exemple: int = 5,
    temperature: float = _TEMPERATURE_DEFAUT,
) -> RapportRolesLLM:
    """Claude lit un aperçu de chaque onglet et propose son RÔLE (cf. ROLES).

    Validation TOLÉRANTE, volontairement : une entrée dont le rôle est hors
    énumération, ou qui vise un onglet non soumis, est ÉCARTÉE et tracée dans
    `entrees_ecartees` — les propositions saines sont conservées. Un rôle est une
    proposition soumise à l'actuaire, jamais appliquée seule : tout rejeter en
    bloc perdrait de l'information utile.

    LÈVE MappingTriangleLLMIndisponible si le service est indisponible, si la
    réponse est illisible, ou si AUCUNE proposition n'est exploitable.
    """
    if not onglets:
        raise MappingTriangleLLMIndisponible(
            f"aucun onglet a analyser — {_MSG_MANUEL}")

    brut = _appeler_claude(
        _prompt_systeme_roles(),
        _prompt_utilisateur_roles(onglets, n_lignes_exemple),
        temperature=temperature)
    objet = _extraire_objet_json(brut)

    roles: Dict[str, RolePropose] = {}
    ecartees: List[str] = []
    for nom, valeur in objet.items():
        if nom not in onglets:
            ecartees.append(f"'{nom}' : onglet inconnu (non soumis)")
            continue
        if not isinstance(valeur, dict):
            ecartees.append(f"'{nom}' : proposition mal formee (objet attendu)")
            continue
        role = str(valeur.get('role', '')).strip().lower()
        if role not in ROLES:
            ecartees.append(f"'{nom}' : role '{role or '(vide)'}' hors enumeration")
            continue
        confiance = str(valeur.get('confiance', 'basse')).strip().lower()
        if confiance not in ('haute', 'moyenne', 'basse'):
            confiance = 'basse'          # valeur inattendue → prudence
        roles[nom] = RolePropose(
            role=role, confiance=confiance,
            justification=str(valeur.get('justification', '')).strip())

    if not roles:
        raise MappingTriangleLLMIndisponible(
            f"aucun role exploitable dans la reponse — {_MSG_MANUEL}")

    ignores = tuple(sorted(o for o in onglets if o not in roles))
    if ecartees:
        logger.warning("Roles LLM : %d entree(s) ecartee(s) — %s",
                       len(ecartees), ecartees)
    return RapportRolesLLM(roles=roles, onglets_ignores=ignores,
                           entrees_ecartees=tuple(ecartees))


def proposer_mapping_colonnes(
    df: pd.DataFrame,
    kind: str = 'sinistres',
    *,
    n_lignes_exemple: int = 5,
    temperature: float = _TEMPERATURE_DEFAUT,
) -> TriangleSchema:
    """Claude lit un aperçu du tableau + le vocabulaire canonique, et propose un
    TriangleSchema (module 2) prêt à passer à appliquer_mapping_triangle().

    Validation STRICTE, volontairement : le schéma proposé repasse par
    valider_mapping_triangle() AVANT d'être rendu — une cible inventée ou une
    collision lève MappingTriangleIncoherent, exactement comme un YAML humain
    erroné. Aucun passe-droit pour le LLM : un mauvais mapping renommerait des
    colonnes, donc corromprait des données.

    LÈVE MappingTriangleLLMIndisponible si le service est indisponible, si la
    réponse est illisible, ou si aucune correspondance n'est proposée.
    """
    if df is None or df.shape[1] == 0:
        raise MappingTriangleLLMIndisponible(
            f"tableau vide (aucune colonne) — {_MSG_MANUEL}")

    brut = _appeler_claude(
        _prompt_systeme_mapping(kind),
        _prompt_utilisateur_mapping(df, kind, n_lignes_exemple),
        temperature=temperature)
    objet = _extraire_objet_json(brut)

    correspondances = {
        str(k): str(v) for k, v in objet.items()
        if isinstance(k, str) and isinstance(v, str) and v.strip()
    }
    if not correspondances:
        raise MappingTriangleLLMIndisponible(
            f"le modele n'a propose aucune correspondance sure — {_MSG_MANUEL}")

    schema = TriangleSchema(kind=kind, correspondances=correspondances,
                            client='proposition_claude', source='(proposition LLM)')
    valider_mapping_triangle(schema)     # LÈVE MappingTriangleIncoherent si invalide
    return schema
