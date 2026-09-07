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

from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd

from core.plan_tarifaire import PlanTarifaire

__all__ = [
    "MappingClient", "RapportMapping", "MappingIncoherent",
    "charger_mapping", "valider_mapping", "appliquer_mapping",
    "diagnostiquer_mapping",
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
    def depuis_plat(cls, correspondances: dict[str, str],
                    client: str) -> MappingClient:
        """Le format PLAT d'A1 — ``{"NUM_POL": "id_contrat", …}`` — accepté tel
        quel, SANS plan déclaré.

        ⚠️⚠️ LE FORMAT DEVIENT ADDITIF, ET C'EST DÉLIBÉRÉ — constat `A1-1`.
        `config/{client}_mapping.json` ne porte ni `client` ni `plan` : le
        passer à :meth:`depuis_dict` lèverait sur tous les clients existants.
        On accepte donc les DEUX formes — la plate, et l'enveloppée
        ``{"plan": "auto", "correspondances": {…}}`` qui gagne le contrôle de
        plan.

        ⚠️ ET LE PLAN N'EST PAS SYNTHÉTISÉ. La tentation était d'y mettre
        `plan.lob`, ce qui rendrait le garde « le mapping cible un autre
        plan » comparateur de `plan.lob` à lui-même : il ne pourrait plus
        JAMAIS se déclencher, tout en figurant au rapport comme un contrôle
        effectué. *Un garde qui ne peut pas tirer est pire que pas de garde.*
        `plan` reste vide, et le rapport déclare le contrôle NON exercé.
        """
        if not isinstance(correspondances, dict) or not correspondances:
            raise MappingIncoherent(
                "Mapping : 'correspondances' doit être un dict non vide.")
        if not all(isinstance(k, str) and isinstance(v, str)
                   for k, v in correspondances.items()):
            raise MappingIncoherent(
                "Mapping : {nom_client: nom_plan}, chaînes uniquement.")
        return cls(client=str(client), plan='',
                   correspondances=dict(correspondances))

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> MappingClient:
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
    def depuis_yaml(cls, chemin) -> MappingClient:
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
    colonnes_client_non_mappees: tuple[str, ...]  # présentes mais NON consommées → candidates
    colonnes_plan_non_couvertes: tuple[str, ...]  # attendues absentes après renommage → futures amputées
    correspondances_mortes:      tuple[str, ...]  # clé du mapping absente du fichier client
    # ⚠️⚠️ LES TROIS INCOHÉRENCES, RENDUES ET NON LEVÉES — constat `A1-1`.
    # `valider_mapping` les LÈVE, ce qui convient à `appliquer_mapping` mais
    # pas à A1 : lever changerait le comportement d'ingestion de clients
    # existants. Elles voyagent donc dans le rapport, et l'appelant décide.
    # *Signaler d'abord, lever ensuite — et une seule implémentation des
    # règles, jamais deux qui divergeront.*
    # Valeurs par défaut : les constructions existantes restent valides.
    cibles_inconnues_du_plan: tuple[str, ...] = ()   # typo / mapping périmé
    collisions:               tuple[str, ...] = ()   # deux sources → même cible
    plan_declare:             str | None = None   # le plan que le fichier vise
    plan_incoherent:          bool = False           # ...et il n'est pas celui-ci
    #: La table source → cible. Conservée pour CROISER les correspondances
    #: mortes avec les colonnes du plan non couvertes — sans elle, on ne peut
    #: pas dire laquelle des deux a causé l'autre.
    correspondances: Mapping[str, str] = field(default_factory=dict)

    def synthese(self) -> dict[str, Any]:
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
            "cibles_inconnues_du_plan": list(self.cibles_inconnues_du_plan),
            "collisions":               list(self.collisions),
            "plan_declare":             self.plan_declare,
            "plan_incoherent":          bool(self.plan_incoherent),
            # ⚠️ CE QUI N'A PAS ÉTÉ CONTRÔLÉ SE DIT, comme ce qui l'a été. Un
            # fichier au format PLAT ne déclare pas le plan qu'il vise : le
            # contrôle de plan ne peut alors PAS être exercé, et le rapport
            # doit le dire. *Un garde qui ne peut pas se déclencher figurerait
            # sinon comme un contrôle effectué.*
            "controle_plan_effectue": self.plan_declare is not None,
        }

    def mortes_qui_causent_une_amputation(self) -> tuple[str, ...]:
        """Les correspondances mortes dont la CIBLE manque au plan.

        ⚠️⚠️ LA SÉVÉRITÉ EST CROISÉE, ET C'EST TOUT L'INTÉRÊT. Une
        correspondance morte est INFORMATIVE en général — un mapping garde
        souvent des lignes pour d'anciens exports. Elle devient GRAVE quand la
        colonne du plan qu'elle visait est justement non couverte : c'est
        alors la SEULE phrase qui nomme la cause de l'amputation.
          *Le cas réel le plus fréquent est un export client renommé en
          amont : la clé source ne correspond plus, l'entrée est écartée en
          silence, et le modèle sort amputé sans que rien ne dise pourquoi.*
        """
        manquantes = set(self.colonnes_plan_non_couvertes)
        return tuple(k for k in self.correspondances_mortes
                     if (self.correspondances or {}).get(k) in manquantes)


def synthese_mapping(rapport: RapportMapping | None) -> str | None:
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
    # ⚠️⚠️ LES INCOHERENCES SE DISENT AVANT LE RESTE — constat `A1-1`. Elles
    # nomment la CAUSE : sans elles, l'actuaire lit un modele ampute sans
    # pouvoir distinguer << le client n'a pas fourni la colonne >> de
    # << mon mapping l'a mal nommee >>.
    if rapport.cibles_inconnues_du_plan:
        lignes.append(
            f"⚠ {len(rapport.cibles_inconnues_du_plan)} cible(s) INCONNUE(S) du "
            f"plan (faute de frappe ou mapping perime) : "
            f"{', '.join(rapport.cibles_inconnues_du_plan)}.")
    if rapport.collisions:
        lignes.append(
            f"⚠ COLLISION : plusieurs colonnes pointent vers la meme cible "
            f"{', '.join(rapport.collisions)} — le renommage creerait des "
            f"colonnes en double.")
    if rapport.plan_incoherent:
        lignes.append(
            f"⚠ Le mapping declare viser le plan '{rapport.plan_declare}' et "
            f"non '{rapport.plan}'.")
    elif rapport.plan_declare is None:
        # ⚠️ CE QUI N'A PAS ETE CONTROLE SE DIT. Le fichier plat ne declare pas
        # son plan : le garde n'a pas pu s'exercer, et le taire le ferait
        # passer pour un controle effectue.
        lignes.append(
            "Le fichier de mapping ne declare pas le plan qu'il vise : le "
            "controle de coherence de plan n'a PAS ete exerce.")
    # ⚠️⚠️ LA SEVERITE CROISEE. Une correspondance morte est informative, SAUF
    # si la colonne du plan qu'elle visait est justement non couverte : c'est
    # alors la seule phrase qui nomme la cause de l'amputation, et le cas reel
    # le plus frequent — un export client renomme en amont.
    _causantes = rapport.mortes_qui_causent_une_amputation()
    if _causantes:
        _paires = ', '.join(
            f"{k} → {(rapport.correspondances or {}).get(k)}"
            for k in _causantes)
        lignes.append(
            f"⚠ CAUSE DE L'AMPUTATION : {len(_causantes)} correspondance(s) "
            f"morte(s) visaient une colonne du plan NON couverte ({_paires}) "
            f"— la colonne source a probablement ete renommee en amont.")
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


def diagnostiquer_mapping(df: pd.DataFrame, mapping: MappingClient,
                          plan: PlanTarifaire) -> RapportMapping:
    """Les MÊMES règles que :func:`valider_mapping`, sans lever ni renommer.

    ⚠️⚠️ POURQUOI ELLE EXISTE — constat `A1-1`. `a1._appliquer_mapping_client`
    renomme sans RIEN valider : ni cible inconnue du plan, ni collision, ni
    plan visé. Une faute de frappe dans `config/{client}_mapping.json` renomme
    vers une colonne que le plan n'attend pas ; A2 la déclare manquante et le
    modèle est publié « amputé ».
      ***L'effet est publié, la cause ne l'est pas*** — et l'actuaire ne peut
      pas distinguer « le client n'a pas fourni la colonne » de « mon mapping
      l'a mal nommée ».

    ⚠️ MAIS A1 NE PEUT PAS LEVER, et c'est pourquoi cette fonction n'est pas
    un drapeau sur :func:`appliquer_mapping`. Les trois incohérences n'ont pas
    la même disposition possible : une COLLISION ne peut pas s'appliquer — le
    renommage créerait deux colonnes de même nom ; une CIBLE INCONNUE peut être
    appliquée-et-signalée ou écartée-et-signalée, et les deux se défendent ; un
    MAUVAIS PLAN ne produit rien d'utile. *Un booléen unique masquerait trois
    décisions.* On rend donc les faits, et l'appelant décide.

    ⚠️ UNE SEULE IMPLÉMENTATION DES RÈGLES : :func:`appliquer_mapping` appelle
    cette fonction puis lève. Les recopier dans A1 aurait produit deux jeux de
    règles qui divergent — le défaut que ce chantier ferme partout.
    """
    cols = list(df.columns)
    attendues = set(plan.colonnes_attendues())
    vivantes = {k: v for k, v in mapping.correspondances.items() if k in cols}
    mortes = tuple(sorted(k for k in mapping.correspondances if k not in cols))

    # ── Les trois incohérences, MESURÉES et non levées ────────────────────
    inconnues = tuple(sorted(
        {v for v in mapping.correspondances.values() if v not in attendues}))
    cibles = list(mapping.correspondances.values())
    doublons = tuple(sorted({c for c in cibles if cibles.count(c) > 1}))
    # collision avec l'existant : le renommage créerait-il deux colonnes de
    # même nom ? On le calcule SANS renommer.
    finaux = [vivantes.get(c, c) for c in cols]
    collisions = tuple(sorted(
        set(doublons) | {n for n in finaux if finaux.count(n) > 1}))

    # ⚠️ LE PLAN VISÉ N'EST CONTRÔLABLE QUE S'IL EST DÉCLARÉ. Un fichier au
    # format PLAT n'en porte pas : `plan_declare` reste `None` et le rapport
    # dit que le contrôle n'a PAS été exercé, plutôt que de le simuler.
    declare = mapping.plan if mapping.plan else None
    incoherent = bool(declare and _lob(declare) != _lob(plan.lob))

    return RapportMapping(
        client=mapping.client, plan=plan.lob, n_renommees=len(vivantes),
        n_colonnes_attendues=len(attendues),
        colonnes_client_non_mappees=tuple(
            c for c in finaux if c not in attendues),
        colonnes_plan_non_couvertes=tuple(sorted(attendues - set(finaux))),
        correspondances_mortes=mortes,
        cibles_inconnues_du_plan=inconnues,
        collisions=collisions,
        plan_declare=declare,
        plan_incoherent=incoherent,
        correspondances=dict(mapping.correspondances))


def appliquer_mapping(df: pd.DataFrame, mapping: MappingClient, plan: PlanTarifaire
                      ) -> tuple[pd.DataFrame, RapportMapping]:
    """Valide (lève si incohérent), renomme le df, rend (df_renommé, RapportMapping).
    Ne renomme que les clés PRÉSENTES ; les clés absentes → correspondances_mortes.

    ⚠️ Les règles vivent dans :func:`diagnostiquer_mapping` ; ici on les LÈVE.
    Le contrat publié de cette fonction est inchangé."""
    valider_mapping(mapping, plan)
    rapport = diagnostiquer_mapping(df, mapping, plan)

    if rapport.collisions:
        raise MappingIncoherent(
            f"Mapping du client '{mapping.client}' : le renommage crée des colonnes "
            f"en double {list(rapport.collisions)} (une cible coïncide avec une "
            f"colonne déjà présente).")

    vivantes = {k: v for k, v in mapping.correspondances.items()
                if k in df.columns}
    return df.rename(columns=vivantes), rapport


def preparer_fichier_client(df: pd.DataFrame, chemin_mapping: str | None,
                            plan: PlanTarifaire
                            ) -> tuple[pd.DataFrame, RapportMapping | None]:
    """Point d'entrée AVANT A1. chemin_mapping=None → (df, None) : RÉTRO-COMPAT
    totale, le df passe tel quel. Sinon : charge + applique + rend le rapport,
    à surfacer à côté des livrables (câblage = couche 2).

    ⚠️⚠️ CONSTAT `socle/C2` — CETTE PORTE N'A TOUJOURS
    AUCUN APPELANT DE PRODUCTION DANS CE DÉPÔT, et c'est mesuré par AST,
    pas supposé. (La phrase tient sur UNE ligne à dessein : la sentinelle
    `SO-1` la cherche telle quelle, et mon premier jet l'avait coupée entre
    « DE » et « PRODUCTION ». *Un texte destiné à être vérifié porte ses
    phrases telles qu'on les cherchera.*) Ce n'est PAS du code mort : la
    couche est conçue pour être appelée par CELUI QUI APPELLE le pipeline,
    AVANT lui — un fichier de mapping déjà en YAML enveloppé, hors chaîne
    A1. *Elle reste une porte ouverte pour un appelant qui n'existe pas
    encore.*

    ⚠️⚠️ MAIS LE DÉFAUT QU'ELLE PORTAIT EST FERMÉ — constat `A1-1`, le
    07/09/2026. Le trajet du rapport ne passe plus par ici : A1 diagnostique
    lui-même (`a1._appliquer_mapping_client` → :func:`diagnostiquer_mapping`),
    A6 relaie, et les trois livrables lisent
    `result_a6['rapport_mapping']` via :func:`synthese_mapping`. La jonction
    `pipeline_agents(rapport_mapping=...)` reste offerte et l'argument
    explicite PRIME, mais elle n'est plus le SEUL chemin — et c'était tout le
    problème : elle avait zéro appelant, donc les trois surfaces recevaient
    toujours `None`.

    ⚠️ LES DEUX MÉCANISMES SUBSISTENT, MAIS PLUS LES DEUX JEUX DE RÈGLES.
    `a1._appliquer_mapping_client` garde son format propre
    (`{client_id}_mapping.json`, JSON plat, accepté par
    :meth:`MappingClient.depuis_plat`) et son geste propre : il RENOMME sans
    lever, là où :func:`appliquer_mapping` lève. Ce qui a été unifié, c'est
    ce qui devait l'être — les RÈGLES, qui vivent désormais dans
    :func:`diagnostiquer_mapping` seule. *Deux portes d'entrée, une seule
    définition de ce qui est incohérent.*
    """
    if chemin_mapping is None:
        return df, None
    return appliquer_mapping(df, charger_mapping(chemin_mapping), plan)
