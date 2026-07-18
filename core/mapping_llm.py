"""
core/mapping_llm.py — PROPOSITION LLM DE MAPPING CLIENT (Phase 5, couche LLM).

Claude LIT les colonnes du fichier client + quelques lignes d'exemple + les
colonnes ATTENDUES par le plan, et PROPOSE un MappingClient (les correspondances
de noms). Claude ne propose JAMAIS le plan : le sens des colonnes reste porté par
le plan signé. La proposition est un ACCÉLÉRATEUR — le mapping manuel
(core.mapping_client) reste toujours possible et suffisant.

Garde-fous (identiques au mapping manuel) :
  · le résultat est un MappingClient, donc il passe par valider_mapping() avant
    d'être rendu : une cible inconnue du plan (ou une collision) lève
    MappingIncoherent — même mur que si un humain avait écrit un mauvais YAML ;
  · service indisponible (pas de clé, pas de réseau, paquet anthropic absent,
    réponse illisible) → MappingLLMIndisponible, message actionnable, JAMAIS un
    crash opaque.

Dépend de core (plan_tarifaire, mapping_client, derivations) + pandas ; le paquet
`anthropic` n'est importé QU'À l'appel réel — jamais requis pour importer ce
module ni pour le mapping manuel. Agnostique à l'interface (aucun import d'app).

AUTEUR : ActuarIA
"""
from __future__ import annotations

import json
import os
from typing import Dict

import pandas as pd

from core.derivations import sources_brutes
from core.mapping_client import MappingClient, valider_mapping
from core.plan_tarifaire import PlanTarifaire

__all__ = ["proposer_mapping", "MappingLLMIndisponible"]

# Modèle et température — MÊME CONVENTION que les services de narration
# (direction_non_vie/.../services/rapport_modeles_tarif.py : CLAUDE_MODEL_TARIF /
# CLAUDE_TEMPERATURE_TARIF). Rapatriés ici en constantes LOCALES : core ne doit
# pas dépendre d'un service (ce serait inverser la dépendance). temperature=0 :
# reproductibilité (statistique) recherchée — même rationale S2 que le service.
_MODELE_CLAUDE = "claude-sonnet-5"
_TEMPERATURE_DEFAUT = 0.0
_MAX_TOKENS = 2000

_MSG_MANUEL = ("ecrivez le mapping manuellement "
               "(core.mapping_client / mappings/<client>_<lob>.yaml).")


class MappingLLMIndisponible(RuntimeError):
    """Le service de proposition n'a pas pu produire un mapping : clé absente,
    réseau, paquet `anthropic` manquant, ou réponse illisible. JAMAIS un crash —
    le message dit quoi faire (écrire le mapping à la main)."""


# ── construction du prompt ──────────────────────────────────────────────────
def _roles_attendus(plan: PlanTarifaire) -> Dict[str, str]:
    """Rôle DÉCLARÉ de chaque colonne attendue (en source brute) : exposition /
    cible / identifiant / type de facteur (continu|categoriel|binaire).
    Les rôles cible/exposition/identifiant priment (setdefault)."""
    roles: Dict[str, str] = {
        plan.exposition: "exposition (offset, ne pas modeliser)",
        plan.cible_frequence: "cible : frequence (nombre de sinistres)",
        plan.cible_cout: "cible : cout total des sinistres",
    }
    if plan.identifiant_contrat:
        roles[plan.identifiant_contrat] = "identifiant de contrat"
    for f in plan.facteurs:
        for src in sources_brutes([f.nom]):     # dérivée → source brute
            roles.setdefault(src, f.type)
    return roles


def _prompt_systeme() -> str:
    return (
        "Tu es un assistant actuariel. Ta tache : proposer un mapping (une "
        "correspondance de NOMS de colonnes) entre le fichier d'un client et les "
        "colonnes attendues par un plan de tarification. Tu ne modifies PAS le "
        "plan ; tu ne fais que rapprocher des noms de colonnes.\n"
        "Regles imperatives :\n"
        "- Reponds UNIQUEMENT par un objet JSON de la forme "
        '{"nom_colonne_client": "nom_colonne_plan"}, sans aucun texte, sans '
        "explication, sans balise de code autour.\n"
        "- Chaque VALEUR doit etre EXACTEMENT l'une des colonnes attendues "
        "fournies. N'invente jamais un nom de colonne de plan.\n"
        "- Ne mappe une colonne QUE si tu es raisonnablement sur. Dans le doute, "
        "OMETS-la : une correspondance manquante (que l'actuaire completera) vaut "
        "mieux qu'une fausse correspondance.\n"
        "- N'associe jamais deux colonnes client a la meme colonne de plan."
    )


def _prompt_utilisateur(df: pd.DataFrame, plan: PlanTarifaire,
                        n_lignes_exemple: int) -> str:
    cols_client = "\n".join(f"- {c} : {df[c].dtype}" for c in df.columns)
    exemple = df.head(n_lignes_exemple).to_csv(index=False).strip()
    roles = _roles_attendus(plan)
    attendues = "\n".join(
        f"- {c} : {roles.get(c, 'facteur')}" for c in plan.colonnes_attendues())
    return (
        f"COLONNES DU FICHIER CLIENT (nom : type pandas) :\n{cols_client}\n\n"
        f"{n_lignes_exemple} LIGNES D'EXEMPLE DU FICHIER CLIENT (CSV) :\n"
        f"{exemple}\n\n"
        f"COLONNES ATTENDUES PAR LE PLAN '{plan.lob}' (nom : role) :\n"
        f"{attendues}\n\n"
        "Reponds par le seul objet JSON des correspondances "
        '{"nom_colonne_client": "nom_colonne_plan"}.'
    )


# ── appel API (SEUL point qui touche anthropic — patchable en test) ──────────
def _appeler_claude(systeme: str, utilisateur: str, *, temperature: float) -> str:
    """Appelle Claude et rend le TEXTE brut de la réponse. Toute défaillance
    (paquet absent, clé absente, réseau, HTTP) → MappingLLMIndisponible."""
    try:
        import anthropic
    except Exception as e:      # paquet absent : dégradation propre
        raise MappingLLMIndisponible(
            f"paquet 'anthropic' indisponible ({e}) — {_MSG_MANUEL}") from e
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise MappingLLMIndisponible(
            f"ANTHROPIC_API_KEY non definie — {_MSG_MANUEL}")
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=_MODELE_CLAUDE, max_tokens=_MAX_TOKENS, temperature=temperature,
            system=systeme, messages=[{"role": "user", "content": utilisateur}],
        )
        return "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text")
    except MappingLLMIndisponible:
        raise
    except Exception as e:      # réseau, HTTP, 4xx/5xx : dégradation propre
        raise MappingLLMIndisponible(
            f"service de proposition indisponible ({e}) — {_MSG_MANUEL}") from e


def _parser_correspondances(brut: str) -> Dict[str, str]:
    """Isole et parse l'objet JSON {client: plan} ; ne garde que les paires
    chaîne→chaîne non vides. Illisible → MappingLLMIndisponible."""
    texte = (brut or "").strip()
    i, j = texte.find("{"), texte.rfind("}")
    if i == -1 or j == -1 or j <= i:
        raise MappingLLMIndisponible(
            f"reponse du modele illisible (aucun objet JSON) — {_MSG_MANUEL}")
    try:
        objet = json.loads(texte[i:j + 1])
    except Exception as e:
        raise MappingLLMIndisponible(
            f"reponse du modele non parsable ({e}) — {_MSG_MANUEL}") from e
    if not isinstance(objet, dict):
        raise MappingLLMIndisponible(
            f"reponse du modele n'est pas un objet JSON — {_MSG_MANUEL}")
    return {
        str(k): str(v) for k, v in objet.items()
        if isinstance(k, str) and isinstance(v, str) and v.strip()
    }


# ── API publique ─────────────────────────────────────────────────────────────
def proposer_mapping(
    df: pd.DataFrame,
    plan: PlanTarifaire,
    *,
    n_lignes_exemple: int = 5,
    temperature: float = _TEMPERATURE_DEFAUT,
) -> MappingClient:
    """Claude Sonnet lit les colonnes du client + n lignes d'exemple + les
    colonnes attendues par le plan, et propose un MappingClient.

    Le résultat passe par valider_mapping() avant d'être rendu : une cible
    inconnue du plan (ou une collision) lève MappingIncoherent — même garde-fou
    que le mapping manuel. Service indisponible → MappingLLMIndisponible (jamais
    un crash). Température 0 pour la reproductibilité (même convention que le
    reste du projet).
    """
    if df is None or df.shape[1] == 0:
        raise MappingLLMIndisponible(
            f"fichier client vide (aucune colonne) — {_MSG_MANUEL}")

    brut = _appeler_claude(
        _prompt_systeme(),
        _prompt_utilisateur(df, plan, n_lignes_exemple),
        temperature=temperature,
    )
    correspondances = _parser_correspondances(brut)
    if not correspondances:
        raise MappingLLMIndisponible(
            f"le modele n'a propose aucune correspondance sure — {_MSG_MANUEL}")

    mapping = MappingClient(
        client="proposition_claude", plan=plan.lob,
        correspondances=correspondances)
    valider_mapping(mapping, plan)      # LÈVE MappingIncoherent sur cible inconnue
    return mapping
