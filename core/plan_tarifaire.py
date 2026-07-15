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
