"""
core/plan_tarifaire.py — LA SOURCE UNIQUE.

Remplace les QUATRE listes codées en dur qui se désynchronisaient :
    A1   MOTS_CLES_DETECTION          → supprimée (l'actuaire déclare sa LoB)
    A2   VARS_CATEGORIELLES           → dérivée du plan
    A3   VARS_GLM                     → dérivée du plan
    core FACTEURS_TARIFAIRES_AUTORISES → dérivée du plan

Les trois classes de bloquants trouvées en audit venaient TOUTES d'une
désynchronisation entre ces listes :
    B4  : MOTS_CLES_DETECTION  ≠ VARS_GLM        → RC Pro indétectable
    B5  : FACTEURS_AUTORISES   ≠ VARS_GLM        → facteurs déclarés détruits
    ——  : VARS_CATEGORIELLES   ≠ VARS_GLM        → 9 variables perdues (one-hot vs _enc)

Avec une source unique, la désynchronisation devient IMPOSSIBLE PAR CONSTRUCTION.

Ce que le plan NE remplace PAS — et c'est essentiel :
    · le filtre GENRE          (CJUE C-236/09)  — agnostique à la LoB
    · le contrôle par l'EFFET  (anti-fuite)     — agnostique à la LoB
    · le critère d'ANTÉRIORITÉ                  — agnostique à la LoB
Ces trois garde-fous s'appliquent à TOUT ce que l'actuaire déclare. Le plan
déplace la charge de la preuve — d'« ActuarIA l'a codé en dur » vers
« l'actuaire l'a signé » — ce qui est précisément ce que l'ACPR attend : un
plan de tarification explicite, versionné, opposable.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence

from core.derivations import sources_brutes

TypeFacteur = Literal["continu", "categoriel", "binaire"]
Encodage = Literal["one_hot", "label", "aucun"]
Transformation = Literal["log", "carre", "racine"]
# Famille de la loi du GLM de COÛT MOYEN (sévérité). Déclarée dans le plan
# plutôt que codée en dur dans A3 : gamma reste le défaut (comportement des LoB
# existantes inchangé), mais l'actuaire peut désormais choisir une log-normale
# ou une inverse-gaussienne quand la distribution des coûts le justifie (queue
# épaisse, grands risques). C'est un choix de modélisation qui fait partie du
# plan signé — donc opposable, et inscrit dans l'empreinte.
FamilleSeverite = Literal["gamma", "lognormal", "inverse_gaussienne"]

# Transformations dérivées : suffixe appliqué par A2
_SUFFIXE_TRANSFO = {"log": "log_{}", "carre": "{}_carre", "racine": "{}_racine"}


def _slug(valeur: str) -> str:
    """Normalise une modalité en suffixe de colonne one-hot.
    DOIT être identique à ce que A2 applique — c'est le contrat."""
    return (
        str(valeur).strip().lower()
        .replace(" ", "_").replace("-", "_").replace("'", "_")
        .replace("é", "e").replace("è", "e").replace("ê", "e")
        .replace("à", "a").replace("ç", "c").replace("ô", "o").replace("û", "u")
    )


@dataclass(frozen=True)
class Facteur:
    """Un facteur tarifaire déclaré par l'actuaire."""
    nom: str                                   # colonne source du fichier client
    type: TypeFacteur
    encodage: Encodage = "aucun"
    transformation: Optional[Transformation] = None
    modalites: Optional[tuple] = None          # figées à l'apprentissage (one_hot/label)
    anteriorite: bool = False                  # sinistralité passée légitime (V14)
    reference: Optional[str] = None            # modalité de référence du one-hot
    commentaire: str = ""

    def __post_init__(self):
        if self.type == "categoriel" and self.encodage == "aucun":
            raise ValueError(
                f"'{self.nom}' : un facteur catégoriel doit déclarer un encodage "
                f"('one_hot' ou 'label')."
            )
        if self.type == "continu" and self.encodage != "aucun":
            raise ValueError(
                f"'{self.nom}' : un facteur continu ne s'encode pas "
                f"(encodage='{self.encodage}')."
            )
        if self.encodage == "one_hot" and not self.modalites:
            raise ValueError(
                f"'{self.nom}' : un one-hot exige des modalites figées "
                f"(sinon le contrat A2→A3 est indéterminé)."
            )

    # ── LE CŒUR : les noms exacts que A2 produira ──────────────────────────
    def colonnes_produites(self) -> tuple[str, ...]:
        """Noms EXACTS des colonnes que A2 créera à partir de ce facteur.

        C'est l'unique définition du contrat entre A2 et A3.
        A2 les CRÉE, A3 les ATTEND, la conformité les AUTORISE — tous depuis ici.
        """
        cols: list[str] = []

        if self.type == "binaire" or (self.type == "continu" and not self.transformation):
            cols.append(self.nom)

        elif self.type == "continu" and self.transformation:
            cols.append(self.nom)
            cols.append(_SUFFIXE_TRANSFO[self.transformation].format(self.nom))

        elif self.encodage == "label":
            cols.append(f"{self.nom}_enc")

        elif self.encodage == "one_hot":
            ref = self.reference or self.modalites[0]
            for m in self.modalites:
                if m == ref:            # modalité de référence : pas de colonne
                    continue
                cols.append(f"{self.nom}_{_slug(m)}")

        return tuple(cols)


@dataclass(frozen=True)
class PlanTarifaire:
    """Le plan de tarification signé par l'actuaire. Une LoB = un plan."""
    lob: str
    exposition: str
    cible_frequence: str
    cible_cout: str
    facteurs: tuple[Facteur, ...]
    interactions: tuple[tuple[str, str], ...] = field(default=())
    auteur: str = ""
    version: str = "1.0"
    # Famille du GLM de coût moyen — déclarée, plus codée en dur dans A3.
    # Défaut "gamma" : aucune LoB existante ne change de comportement.
    famille_severite: FamilleSeverite = "gamma"
    # Colonne identifiant de contrat/police (optionnelle). Si déclarée, la couche
    # qualité (core/qualite_donnees.py) dédoublonne PAR CET IDENTIFIANT (règle 1,
    # exclusion sans discussion) ; sinon un doublon de LIGNE entière reste ambigu
    # (règle 3, signalé et laissé). Purement un RÔLE de données — jamais un facteur
    # tarifaire (n'entre pas dans colonnes_produites()).
    identifiant_contrat: Optional[str] = None

    def __post_init__(self):
        # ── GARDE B9 (offset) : l'exposition n'est JAMAIS un prédicteur ─────────
        # exposition / log_exposition servent d'OFFSET au GLM (terme dont le
        # coefficient est fixé à 1), jamais de facteur tarifaire. S'ils figuraient
        # dans colonnes_produites(), ils entreraient dans la matrice de conception
        # comme variables LIBRES — c'est très exactement la fuite structurelle B9
        # (le modèle « explique » la sinistralité par la durée d'exposition au
        # lieu de la porter en offset, et la prime cesse d'être proportionnelle à
        # l'exposition). Le plan rend cette erreur INEXPRIMABLE dès la déclaration.
        produites = set(self.colonnes_produites())
        interdits = {
            "exposition", "log_exposition",
            self.exposition, f"log_{self.exposition}",
        }
        collision = produites & interdits
        if collision:
            raise ValueError(
                f"Plan '{self.lob}' : {sorted(collision)} ne peut(vent) pas être "
                f"déclaré(s) comme facteur(s) tarifaire(s) — l'exposition sert "
                f"d'OFFSET au GLM (coefficient fixé à 1), jamais de prédicteur. "
                f"La déclarer comme facteur rouvrirait la fuite structurelle B9 "
                f"(prime non proportionnelle à l'exposition)."
            )
        # Cohérence : la famille de sévérité doit être une valeur connue.
        if self.famille_severite not in ("gamma", "lognormal", "inverse_gaussienne"):
            raise ValueError(
                f"Plan '{self.lob}' : famille_severite='{self.famille_severite}' "
                f"inconnue — attendu 'gamma', 'lognormal' ou 'inverse_gaussienne'."
            )

    # ── Contrat A2 → A3 → conformité : une seule vérité ────────────────────
    def colonnes_produites(self) -> tuple[str, ...]:
        cols: list[str] = []
        for f in self.facteurs:
            cols.extend(f.colonnes_produites())
        for a, b in self.interactions:
            cols.append(f"inter_{a}_{b}")
        return tuple(cols)

    def colonnes_sources(self) -> tuple[str, ...]:
        """Colonnes que le fichier client DOIT contenir."""
        return tuple(f.nom for f in self.facteurs)

    def colonnes_obligatoires(self) -> tuple[str, ...]:
        return (self.exposition, self.cible_frequence, self.cible_cout)

    def colonnes_attendues(self) -> tuple[str, ...]:
        """Colonnes que le fichier client doit RÉELLEMENT fournir, en noms de
        SOURCE BRUTE.

        Diffère de `colonnes_sources()` (qui renvoie `f.nom`) pour les facteurs
        DÉRIVÉS : le client livre `kilometrage_annuel`, A2 en calcule
        `km_par_an_normalise`. C'est le référentiel des cibles de mapping valides
        (core.mapping_client) et de la couverture (« futures amputées »).
        Résolution récursive via core.derivations (source unique dérivée→source).
        """
        cols: list[str] = list(self.colonnes_obligatoires())
        if self.identifiant_contrat:
            cols.append(self.identifiant_contrat)
        cols.extend(sources_brutes([f.nom for f in self.facteurs]))
        vu: set = set()
        return tuple(x for x in cols if not (x in vu or vu.add(x)))

    def facteurs_anteriorite(self) -> tuple[str, ...]:
        """Variables exemptées du contrôle par l'effet (critère V14)."""
        cols: list[str] = []
        for f in self.facteurs:
            if f.anteriorite:
                cols.extend(f.colonnes_produites())
        return tuple(cols)

    def config_encodage(self) -> dict:
        """Ce que A2 consomme — remplace VARS_CATEGORIELLES."""
        return {
            "one_hot": [f.nom for f in self.facteurs if f.encodage == "one_hot"],
            "label":   [f.nom for f in self.facteurs if f.encodage == "label"],
            "transformations": {
                f.nom: f.transformation
                for f in self.facteurs if f.transformation
            },
            "modalites": {
                f.nom: f.modalites
                for f in self.facteurs if f.modalites
            },
            "references": {
                f.nom: (f.reference or f.modalites[0])
                for f in self.facteurs if f.encodage == "one_hot"
            },
        }

    # ── Traçabilité ACPR : le plan est opposable ───────────────────────────
    def empreinte(self) -> str:
        """SHA-256 du plan — à inscrire dans l'audit_trail et les rapports."""
        payload = json.dumps({
            "lob": self.lob, "version": self.version, "auteur": self.auteur,
            "exposition": self.exposition,
            "cibles": [self.cible_frequence, self.cible_cout],
            "famille_severite": self.famille_severite,
            "identifiant_contrat": self.identifiant_contrat,
            "facteurs": [
                {"nom": f.nom, "type": f.type, "encodage": f.encodage,
                 "transformation": f.transformation, "modalites": f.modalites,
                 "anteriorite": f.anteriorite, "reference": f.reference}
                for f in self.facteurs
            ],
            "interactions": [list(i) for i in self.interactions],
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    # ── Chargement depuis YAML/JSON ────────────────────────────────────────
    @classmethod
    def depuis_dict(cls, d: dict) -> "PlanTarifaire":
        facteurs = tuple(
            Facteur(
                nom=f["nom"], type=f["type"],
                encodage=f.get("encodage", "aucun"),
                transformation=f.get("transformation"),
                modalites=tuple(f["modalites"]) if f.get("modalites") else None,
                anteriorite=bool(f.get("anteriorite", False)),
                reference=f.get("reference"),
                commentaire=f.get("commentaire", ""),
            )
            for f in d["facteurs"]
        )
        return cls(
            lob=d["lob"], exposition=d["exposition"],
            cible_frequence=d["cible_frequence"], cible_cout=d["cible_cout"],
            facteurs=facteurs,
            interactions=tuple(tuple(i) for i in d.get("interactions", [])),
            auteur=d.get("auteur", ""), version=str(d.get("version", "1.0")),
            famille_severite=d.get("famille_severite", "gamma"),
            identifiant_contrat=d.get("identifiant_contrat"),
        )

    @classmethod
    def depuis_yaml(cls, chemin) -> "PlanTarifaire":
        """Charge un plan depuis un fichier YAML (ou JSON — YAML en est un
        sur-ensemble). C'est le point d'entrée du test de vérité INV-9 :
        une LoB inconnue du code se tarife par ce seul fichier."""
        import yaml
        with open(chemin, encoding="utf-8") as fh:
            return cls.depuis_dict(yaml.safe_load(fh))

    def valider_contre(self, colonnes_df: Sequence[str]) -> list[str]:
        """Contrôle de recevabilité du fichier client. Retourne les manquants."""
        requis = set(self.colonnes_sources()) | set(self.colonnes_obligatoires())
        return sorted(requis - set(colonnes_df))


def verifier_completude_plan(plan: "PlanTarifaire",
                             colonnes_df: Sequence[str]) -> dict:
    """Le modèle est-il AMPUTÉ ? Compare ce que le plan DÉCLARE à ce que les
    données PORTENT réellement. SOURCE UNIQUE, appelée par A3/A4/A5 (qui
    plafonnent leur propre statut) et par A6 (qui plafonne son gate).

    ⚠ La comparaison porte sur les colonnes DISPONIBLES EN DONNÉES, pas sur la
    liste post-garde-fous. Deux pertes distinctes qu'il ne faut jamais confondre :
      · colonne déclarée ABSENTE des données  → le modèle est amputé (ICI) ;
      · colonne écartée par un garde-fou (genre/fuite/effet) → le garde-fou
        FONCTIONNE (cf. INV-3/INV-4 : un plan qui déclare 'sexe' doit se la voir
        retirer). C'est déjà rapporté par exclusions_conformite, et plafonner
        là-dessus reviendrait à punir le contrôle de faire son travail.
    Un plan qui déclare un facteur illégal est un défaut de PLAN, pas une
    amputation : autre défaut, autre remède.
    """
    attendues = list(plan.colonnes_produites())
    dispo     = set(colonnes_df)
    presentes = [c for c in attendues if c in dispo]
    manquantes = [c for c in attendues if c not in dispo]
    return {
        'plan':                plan.lob,
        'n_attendues':         len(attendues),
        'n_presentes':         len(presentes),
        'colonnes_manquantes': manquantes,
        'ampute':              bool(manquantes),
    }


def plafonner_statut_si_ampute(statut: str, rapport) -> str:
    """Un modèle AMPUTÉ ne peut pas être certifié VERT, quelle que soit la
    qualité de son Gini ou de son walk-forward. On PLAFONNE à AMBRE — on ne
    bloque JAMAIS : même logique que le garde-fou DL (valide_par_actuaire_dl).

    Ne remonte jamais un statut : AMBRE et ROUGE sont laissés tels quels. Pas de
    seuil — une SEULE colonne manquante suffit. Un plan signé déclare ce qui est
    NÉCESSAIRE, pas un surplus optionnel : le BLOQUANT B5 l'a prouvé au prix fort
    (un seul facteur détruit, antecedents_sinistres_3ans → −17,4 % de Gini).
    Hiérarchiser les facteurs pour se donner un seuil reviendrait à inventer une
    information que le plan ne porte pas.
    """
    if statut == 'VERT' and rapport and rapport.get('ampute'):
        return 'AMBRE'
    return statut


def alerte_modele_ampute(rapport, modele: str) -> Optional[dict]:
    """Entrée `alertes_modele` normalisée (source unique du libellé), au format
    déjà agrégé par A6 depuis result_a3/a4/a5 et rendu dans les 3 livrables.
    None si le plan est honoré : rien n'est alors signalé."""
    if not rapport or not rapport.get('ampute'):
        return None
    manq = rapport['colonnes_manquantes']
    return {
        'modele': modele,
        'severite': 'AMBRE',
        'code': 'plan_incomplet_modele_ampute',
        'message': (
            f"Modele AMPUTE : {len(manq)} colonne(s) declaree(s) au plan "
            f"'{rapport['plan']}' sont ABSENTES des donnees "
            f"({rapport['n_presentes']}/{rapport['n_attendues']} presentes) : "
            f"{', '.join(manq)}. {modele} est calibre SANS ces facteurs. Statut "
            f"plafonne a AMBRE : un modele ampute ne peut pas etre certifie VERT, "
            f"quelle que soit la qualite du Gini. Verifiez le mapping de colonnes."
        ),
    }


def synthese_colonnes_plan_manquantes(rapport) -> Optional[str]:
    """SOURCE UNIQUE du libellé « colonnes du plan non produites », partagée par
    l'Excel A6, le rapport équipe et le Word/HTML — comme
    synthese_qualite_donnees() pour la qualité de données.

    `rapport` est le dict porté par result_a2['colonnes_plan_manquantes'] (et
    relayé par A6). Retourne None si le plan a été honoré intégralement : rien
    n'est alors affiché dans les livrables.

    Pourquoi ce libellé existe : A2.run produit les colonnes déclarées pour les
    facteurs PRÉSENTS et ignore les autres — un fichier client incomplet donne
    donc un modèle AMPUTÉ. Tant que cet écart n'était que dans les logs, il
    n'existait pas : sur une LoB neuve, le GLM tournait sans ses facteurs
    majeurs sans que personne ne le voie.
    """
    if not rapport:
        return None
    non_produites = rapport.get("colonnes_non_produites") or []
    if not non_produites:
        return None
    absents = rapport.get("facteurs_absents") or []
    txt = (f"⚠ MODELE AMPUTE — plan '{rapport.get('plan', '?')}' : "
           f"{len(non_produites)} colonne(s) declaree(s) NON produite(s) : "
           f"{', '.join(non_produites)}.")
    if absents:
        txt += (f" Facteur(s) source absent(s) du fichier client : "
                f"{', '.join(absents)}.")
    txt += (" Les modeles GLM/ML/DL tournent SANS ces facteurs — verifiez le "
            "mapping de colonnes avant d'exploiter ce tarif.")
    return txt
