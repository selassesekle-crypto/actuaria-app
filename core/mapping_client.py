"""
core/mapping_client.py — LE MOTEUR DE MAPPING CLIENT (Phase 5, couche 1).

Renomme les colonnes d'un fichier client vers les noms ATTENDUS par un plan, AVANT
A1 : c'est une transformation du FICHIER, pas une étape du pipeline actuariel. Le
dataframe renommé passe ensuite normalement à A1 → A2 → … → A6.

Ce que le moteur garantit :
  · renommage déclaré par un YAML (mappings/<client>_<lob>.yaml), ZÉRO logique
    métier — le sens des colonnes reste porté par le PLAN ;
  · COHÉRENCE : toute cible doit exister dans plan.colonnes_attendues() (les noms
    d'ENTRÉE en source brute — kilometrage_annuel, pas la dérivée) ; sinon
    MappingIncoherent (typo / mapping périmé / mauvais plan / collision) ;
  · un RAPPORT à l'actuaire : colonnes client ignorées (candidates), colonnes du
    plan non couvertes (futures amputées), correspondances mortes (clé absente).

Rétro-compatible : sans mapping (chemin=None), le df passe TEL QUEL — les noms
doivent alors déjà correspondre au plan.

Dépend UNIQUEMENT de core (plan_tarifaire, derivations via colonnes_attendues),
pandas, yaml — JAMAIS d'un agent (couche core).

AUTEUR : ActuarIA
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

import pandas as pd

from core.plan_tarifaire import PlanTarifaire

__all__ = [
    "MappingClient", "RapportMapping", "MappingIncoherent",
    "charger_mapping", "valider_mapping", "appliquer_mapping",
    "preparer_fichier_client", "synthese_mapping",
]


class MappingIncoherent(ValueError):
    """Le mapping ne peut pas s'appliquer PROPREMENT : cible inconnue du plan,
    collision de cible, mauvais plan ciblé, ou fichier malformé. Jamais silencieux."""


def _lob(ref: str) -> str:
    """'auto.yaml' → 'auto' — pour comparer mapping.plan à plan.lob."""
    base = str(ref).strip().rsplit("/", 1)[-1]
    for suf in (".yaml", ".yml", ".json"):
        if base.lower().endswith(suf):
            return base[: -len(suf)].lower()
    return base.lower()


# ══════════════════════════════════════════════════════════════════════════════
#  Le fichier de mapping
# ══════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class MappingClient:
    client: str                          # nom du client (traçabilité)
    plan:   str                          # réf du plan ciblé, ex "auto.yaml"
    correspondances: Mapping[str, str]   # {nom_colonne_client: nom_colonne_plan}

    @classmethod
    def depuis_dict(cls, d: Dict[str, Any]) -> "MappingClient":
        if not isinstance(d, dict):
            raise MappingIncoherent("Mapping : racine YAML attendue = dict.")
        manquants = [k for k in ("client", "plan", "correspondances") if k not in d]
        if manquants:
            raise MappingIncoherent(
                f"Mapping : champ(s) obligatoire(s) absent(s) {manquants}.")
        corr = d["correspondances"]
        if not isinstance(corr, dict) or not corr:
            raise MappingIncoherent(
                "Mapping : 'correspondances' doit être un dict non vide.")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in corr.items()):
            raise MappingIncoherent(
                "Mapping : 'correspondances' = {nom_client: nom_plan}, chaînes uniquement.")
        return cls(client=str(d["client"]), plan=str(d["plan"]),
                   correspondances=dict(corr))

    @classmethod
    def depuis_yaml(cls, chemin) -> "MappingClient":
        import yaml
        with open(chemin, encoding="utf-8") as fh:
            return cls.depuis_dict(yaml.safe_load(fh))


# ══════════════════════════════════════════════════════════════════════════════
#  Le rapport (ce que l'actuaire doit voir)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class RapportMapping:
    client: str
    plan:   str
    n_renommees:         int
    n_colonnes_attendues: int                     # total des colonnes d'entrée du plan
    colonnes_client_non_mappees: Tuple[str, ...]  # présentes mais NON consommées → candidates
    colonnes_plan_non_couvertes: Tuple[str, ...]  # attendues absentes après renommage → futures amputées
    correspondances_mortes:      Tuple[str, ...]  # clé du mapping absente du fichier client

    def synthese(self) -> Dict[str, Any]:
        """Vue json-sérialisable (types natifs) — pour les livrables / l'audit."""
        return {
            "client":  self.client,
            "plan":    self.plan,
            "n_renommees": int(self.n_renommees),
            "n_colonnes_attendues": int(self.n_colonnes_attendues),
            "colonnes_client_non_mappees": list(self.colonnes_client_non_mappees),
            "colonnes_plan_non_couvertes": list(self.colonnes_plan_non_couvertes),
            "correspondances_mortes":      list(self.correspondances_mortes),
            "ampute_previsionnel": bool(self.colonnes_plan_non_couvertes),
        }


def synthese_mapping(rapport: Optional[RapportMapping]) -> Optional[str]:
    """SOURCE UNIQUE du libellé « mapping client appliqué », partagée par l'Excel
    A6, le rapport équipe et le Word/HTML — même mécanisme que
    synthese_qualite_donnees() et synthese_colonnes_plan_manquantes().

    Retourne None si AUCUN mapping n'a été appliqué (chemin sans mapping = la
    plupart des appels) : rien n'est alors affiché dans les livrables (rétro-compat).
    Le préfixe ⚠ signale à l'appelant (Excel/équipe) qu'un point mérite AMBRE.
    """
    if rapport is None:
        return None
    lignes = [
        f"Mapping client '{rapport.client}' → plan '{rapport.plan}' : "
        f"{rapport.n_renommees}/{rapport.n_colonnes_attendues} colonne(s) attendue(s) renommee(s)."
    ]
    if rapport.colonnes_plan_non_couvertes:
        lignes.append(
            f"⚠ {len(rapport.colonnes_plan_non_couvertes)} colonne(s) du plan NON "
            f"couverte(s) — MODELE AMPUTE : {', '.join(rapport.colonnes_plan_non_couvertes)}.")
    if rapport.correspondances_mortes:
        lignes.append(
            f"⚠ {len(rapport.correspondances_mortes)} correspondance(s) MORTE(s) "
            f"(cle absente du fichier — mapping perime ?) : "
            f"{', '.join(rapport.correspondances_mortes)}.")
    if rapport.colonnes_client_non_mappees:
        lignes.append(
            f"{len(rapport.colonnes_client_non_mappees)} colonne(s) client NON mappee(s) "
            f"(candidates a devenir facteurs) : "
            f"{', '.join(rapport.colonnes_client_non_mappees)}.")
    return " ".join(lignes)


# ══════════════════════════════════════════════════════════════════════════════
#  Le moteur
# ══════════════════════════════════════════════════════════════════════════════
def charger_mapping(chemin) -> MappingClient:
    return MappingClient.depuis_yaml(chemin)


def valider_mapping(mapping: MappingClient, plan: PlanTarifaire) -> None:
    """Contrôle STATIQUE (sans dataframe). Lève MappingIncoherent si :
       · mapping.plan ≠ plan fourni (garde : un mapping 'auto' sur un plan 'mrh') ;
       · une CIBLE ∉ plan.colonnes_attendues() (typo / mapping périmé) ;
       · deux colonnes client → la MÊME cible (collision)."""
    if _lob(mapping.plan) != _lob(plan.lob):
        raise MappingIncoherent(
            f"Mapping du client '{mapping.client}' cible le plan '{mapping.plan}' "
            f"mais le plan fourni est '{plan.lob}'.")

    attendues = set(plan.colonnes_attendues())
    inconnues = sorted({v for v in mapping.correspondances.values() if v not in attendues})
    if inconnues:
        raise MappingIncoherent(
            f"Mapping du client '{mapping.client}' : cible(s) inconnue(s) du plan "
            f"'{plan.lob}' {inconnues}. Cibles valides : {sorted(attendues)}.")

    cibles = list(mapping.correspondances.values())
    doublons = sorted({c for c in cibles if cibles.count(c) > 1})
    if doublons:
        raise MappingIncoherent(
            f"Mapping du client '{mapping.client}' : plusieurs colonnes client "
            f"pointent vers la même cible {doublons}.")


def appliquer_mapping(df: pd.DataFrame, mapping: MappingClient, plan: PlanTarifaire
                      ) -> Tuple[pd.DataFrame, RapportMapping]:
    """Valide (lève si incohérent), renomme le df, rend (df_renommé, RapportMapping).
    Ne renomme que les clés PRÉSENTES ; les clés absentes → correspondances_mortes."""
    valider_mapping(mapping, plan)

    cols = list(df.columns)
    vivantes = {k: v for k, v in mapping.correspondances.items() if k in cols}
    mortes = tuple(sorted(k for k in mapping.correspondances if k not in cols))

    # collision avec l'existant : le renommage créerait-il deux colonnes de même nom ?
    finaux = [vivantes.get(c, c) for c in cols]
    if len(set(finaux)) != len(finaux):
        collisions = sorted({n for n in finaux if finaux.count(n) > 1})
        raise MappingIncoherent(
            f"Mapping du client '{mapping.client}' : le renommage crée des colonnes "
            f"en double {collisions} (une cible coïncide avec une colonne déjà présente).")

    df_renomme = df.rename(columns=vivantes)
    attendues = set(plan.colonnes_attendues())

    rapport = RapportMapping(
        client=mapping.client, plan=plan.lob, n_renommees=len(vivantes),
        n_colonnes_attendues=len(attendues),
        colonnes_client_non_mappees=tuple(
            c for c in df_renomme.columns if c not in attendues),
        colonnes_plan_non_couvertes=tuple(
            sorted(attendues - set(df_renomme.columns))),
        correspondances_mortes=mortes)
    return df_renomme, rapport


def preparer_fichier_client(df: pd.DataFrame, chemin_mapping: Optional[str],
                            plan: PlanTarifaire
                            ) -> Tuple[pd.DataFrame, Optional[RapportMapping]]:
    """Point d'entrée AVANT A1. chemin_mapping=None → (df, None) : RÉTRO-COMPAT
    totale, le df passe tel quel. Sinon : charge + applique + rend le rapport,
    à surfacer à côté des livrables (câblage = couche 2).

    ⚠️⚠️ CONSTAT `socle/C2` — CETTE PORTE N'A AUCUN APPELANT DE PRODUCTION
    DANS CE DÉPÔT, et c'est mesuré par AST (01/09/2026), pas supposé. Ce n'est
    PAS du code mort : la couche est conçue pour être appelée par CELUI QUI
    APPELLE le pipeline, avant lui — la jonction prévue est
    `pipeline_agents(rapport_mapping=...)`, dont le rapport voyage jusqu'aux
    trois livrables via `synthese_mapping`. **Aucun code de ce dépôt ne joue
    ce rôle d'appelant aujourd'hui.**

    ⚠️ ET IL EXISTE UN SECOND MÉCANISME DE MAPPING, DANS A1. Mesuré :
    `a1_ingestion.agent._appliquer_mapping_client` fait le même métier avec un
    autre format (`{client_id}_mapping.json`, JSON) et A1 n'importe PAS ce
    module. *Deux moteurs pour un seul geste, et rien ne le disait.* Les
    unifier déplacerait un comportement : c'est nommé ici, pas tranché.
    """
    if chemin_mapping is None:
        return df, None
    return appliquer_mapping(df, charger_mapping(chemin_mapping), plan)
