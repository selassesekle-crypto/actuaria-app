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

import dataclasses
import difflib
import hashlib
import json
from dataclasses import asdict as dataclasses_asdict
from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence, get_args

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

#: VERSION DE SCHÉMA DE L'EMPREINTE — la génération de la STRUCTURE hachée par
#: `empreinte()`, distincte du champ `version` (le CONTENU signé par l'actuaire).
#: ⚠️⚠️ À BUMPER quand, et seulement quand, la COMPOSITION du payload de
#: `empreinte()` change (un champ ajouté / retiré / renommé, un attribut de
#: facteur). JAMAIS pour du contenu, jamais pour du code hors payload. Un bump
#: SANS mise à jour du test-golden (`test_plan_invariants`), OU une dérive de
#: structure SANS bump, fait rougir la gate : c'est le SCEAU. Une empreinte sans
#: préfixe `sN:` est HÉRITÉE (pré-versionnement), non revalidable — voir
#: `PlanTarifaire.comparer_empreinte`.
EMPREINTE_SCHEMA = 1

# Transformations dérivées : suffixe appliqué par A2
_SUFFIXE_TRANSFO = {"log": "log_{}", "carre": "{}_carre", "racine": "{}_racine"}

# ⚠️⚠️ LES VALEURS ADMISES SONT DÉRIVÉES DES `Literal`, JAMAIS RECOPIÉES.
# Python n'applique PAS les `Literal` à l'exécution : `type="ordinal"` passait
# sans un mot, et le facteur disparaissait ensuite en silence (constat
# `plan/C3`). On valide donc l'appartenance — et on la valide contre le type
# lui-même, de sorte qu'une valeur ajoutée au `Literal` soit acceptée sans
# qu'on ait à toucher au contrôle. Recopier ces listes ici rouvrirait très
# exactement la désynchronisation que ce fichier existe pour supprimer.
_TYPES_FACTEUR = frozenset(get_args(TypeFacteur))
_ENCODAGES = frozenset(get_args(Encodage))
_TRANSFORMATIONS = frozenset(get_args(Transformation))
_FAMILLES_SEVERITE = frozenset(get_args(FamilleSeverite))


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
        # ── ① L'APPARTENANCE D'ABORD, LA COMBINAISON ENSUITE ───────────────────
        # ⚠️⚠️ CORRECTIF DU LOT 1.2 — constat `plan/C3`. Ce bloc ne validait que
        # la COHÉRENCE des combinaisons, jamais l'APPARTENANCE des valeurs.
        # `TypeFacteur`, `Encodage` et `Transformation` sont des `Literal`, que
        # Python n'applique pas : `type="ordinal"` et `encodage="onehot"` étaient
        # acceptés sans un mot, et `colonnes_produites()` rendait alors `()` —
        # le facteur, pourtant présent dans les données et déclaré au plan,
        # n'atteignait AUCUN modèle. C'est le BLOQUANT B5 sous une forme neuve :
        # un seul facteur détruit avait coûté −17,4 % de Gini.
        for champ, valeur, admises in (
            ("type", self.type, _TYPES_FACTEUR),
            ("encodage", self.encodage, _ENCODAGES),
            ("transformation", self.transformation, _TRANSFORMATIONS | {None}),
        ):
            if valeur not in admises:
                connues = sorted(x for x in admises if x is not None)
                raise ValueError(
                    f"'{self.nom}' : {champ}='{valeur}' inconnu — attendu "
                    f"{' ou '.join(repr(x) for x in connues)}"
                    f"{' (ou aucune)' if None in admises else ''}. "
                    f"Une valeur inconnue ne leve pas d'erreur de typage a "
                    f"l'execution : sans ce controle, le facteur disparait EN "
                    f"SILENCE et aucun modele ne le voit."
                )

        # ── ② Cohérence des combinaisons ──────────────────────────────────────
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
        # ⚠️ `binaire` + un encodage était accepté, et l'encodage était ensuite
        # IGNORÉ par `colonnes_produites()` (mesuré : binaire + one_hot +
        # modalités → ('x',)). L'actuaire signait un one-hot et obtenait autre
        # chose : le plan est opposable, il ne peut pas dire deux choses.
        if self.type == "binaire" and self.encodage != "aucun":
            raise ValueError(
                f"'{self.nom}' : un facteur binaire ne s'encode pas "
                f"(encodage='{self.encodage}') — il produit sa seule colonne "
                f"telle quelle. Un encodage declare ici serait IGNORE."
            )
        if self.encodage == "one_hot" and not self.modalites:
            raise ValueError(
                f"'{self.nom}' : un one-hot exige des modalites figées "
                f"(sinon le contrat A2→A3 est indéterminé)."
            )

        # ── ③ LE FILET : un facteur déclaré qui ne produit RIEN est un défaut ──
        # ⚠️⚠️ Les contrôles ci-dessus nomment les causes que j'ai mesurées. Ce
        # filet-ci attrape la PROPRIÉTÉ, y compris les causes que je n'ai pas
        # vues — par exemple un one-hot à modalité unique égale à la référence,
        # qui ne produit aucune colonne et n'est refusé par aucun contrôle
        # nommé. Il le faut, parce que `verifier_completude_plan` est
        # STRUCTURELLEMENT aveugle à cette perte : il compare
        # `colonnes_produites()` aux données, et le facteur perdu n'est
        # justement plus dans `colonnes_produites()` — il annonce `ampute=False`.
        if not self.colonnes_produites():
            raise ValueError(
                f"'{self.nom}' : ce facteur est declare mais ne produit AUCUNE "
                f"colonne (type='{self.type}', encodage='{self.encodage}', "
                f"modalites={self.modalites}). Il n'atteindrait aucun modele, et "
                f"le detecteur d'amputation ne le verrait pas : il compare les "
                f"colonnes PRODUITES aux donnees, or ce facteur n'en produit "
                f"aucune — il annoncerait `ampute=False`."
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
class Comportement:
    """Le comportement de renouvellement, DÉCLARÉ par l'actuaire.

    ⚠️ C'EST LA TROISIÈME NATURE DE CIBLE DU PLAN, et elle n'a rien d'un
    montant. `cible_frequence` et `cible_cout` sont des grandeurs OBSERVÉES SUR
    UNE PÉRIODE ; une issue de contrat est une DÉCISION PRISE À UNE DATE.
    C'est pourquoi elle ne devient pas un troisième `cible_*` : elle ne vient
    jamais seule.

    ⚠️⚠️ LES TROIS PREMIERS CHAMPS SONT INDISSOCIABLES, et le bloc les exige
    ensemble. Une élasticité-prix répond à une VARIATION de prix, pas à un
    niveau : l'issue sans les deux primes ne dit rien, et deux primes sans
    issue ne disent rien non plus. Un bloc à moitié déclaré promettrait une
    capacité qu'il ne porte pas — c'est très exactement le défaut que cet
    audit poursuit. Le bloc ENTIER absent, lui, n'est pas une erreur : aucun
    des vingt plans du dépôt n'en a, et la chaîne tarife sans.

    ⚠️ PUREMENT DES RÔLES DE DONNÉES — comme `identifiant_contrat` et
    `echeance`. Ces colonnes n'entrent JAMAIS dans `colonnes_produites()` :
    si la prime précédente devenait un facteur, elle prédirait la sinistralité
    et l'on retomberait sur la fuite structurelle que le plan rend
    inexprimable pour l'exposition (garde B9).
    """
    #: L'issue de l'échéance : le contrat a-t-il été renouvelé, ou résilié ?
    issue:            str
    #: La prime de l'exercice précédent.
    prime_precedente: str
    #: La prime proposée à l'échéance. Avec la précédente, elle donne la
    #: VARIATION — la seule grandeur à laquelle une élasticité répond.
    prime_proposee:   str
    #: Canal de distribution (optionnel). L'élasticité y varie d'un facteur
    #: plusieurs entre courtage, direct et comparateur : sans lui, l'estimation
    #: mélange des populations qui ne réagissent pas au même prix.
    canal:            str | None = None
    #: Groupe d'un test de prix (optionnel) — remise ou hausse tirée au sort au
    #: renouvellement. C'est la SEULE source de variation dont l'exogénéité ne
    #: se discute pas : elle identifie l'effet-prix proprement.
    groupe_test:      str | None = None

    def __post_init__(self):
        for champ in ('issue', 'prime_precedente', 'prime_proposee'):
            if not str(getattr(self, champ) or '').strip():
                raise ValueError(
                    f"bloc `comportement` incomplet : '{champ}' n'est pas "
                    f"déclaré. Les trois champs `issue`, `prime_precedente` et "
                    f"`prime_proposee` vont ensemble — une élasticité répond à "
                    f"une VARIATION de prix, pas à un niveau. Retirer le bloc "
                    f"entier est licite ; le déclarer à moitié ne l'est pas."
                )

    def colonnes(self) -> tuple[str, ...]:
        """Les colonnes du fichier client que ce bloc déclare."""
        return tuple(c for c in (self.issue, self.prime_precedente,
                                 self.prime_proposee, self.canal,
                                 self.groupe_test) if c)

    def champs_declares(self) -> frozenset[str]:
        """Les RÔLES déclarés — le vocabulaire du catalogue d'exigences.

        ⚠️ Ce sont les rôles, pas les noms de colonnes : le catalogue
        (`core/elasticite.py`) raisonne sur « une prime précédente est-elle
        déclarée ? », jamais sur « la colonne s'appelle-t-elle prime_n_1 ? ».
        """
        return frozenset(
            r for r, v in (('issue', self.issue),
                           ('prime_precedente', self.prime_precedente),
                           ('prime_proposee', self.prime_proposee),
                           ('canal', self.canal),
                           ('groupe_test', self.groupe_test)) if v)


def _refuser_cles_inconnues(d: dict, classe, ou: str) -> None:
    """Refuse toute clé que la structure ne connaît pas — constat `plan/C5`.

    ⚠️⚠️ POURQUOI LEVER, ET NON AVERTIR. Le plan est le document que l'actuaire
    SIGNE, et il est opposable. Une clé mal orthographiée ne produit pas une
    approximation : elle produit **un autre tarif, sans un mot**. Mesuré sur
    `famille_severity` (l'anglais) : log-normale signée, **gamma appliquée**,
    **+1,00 % de prime totale et +42 124 EUR sur 1 500 contrats**. C'est la
    règle déjà arbitrée pour `INTERPRETABILITE` (`a6/C9`) : *aucune valeur par
    défaut ne s'invente à la place de l'actuaire.*

    ⚠️ LES CLÉS CONNUES SONT DÉRIVÉES DE LA DATACLASSE, JAMAIS RECOPIÉES. Une
    liste en dur divergerait au premier champ ajouté — et c'est exactement ce
    qui va arriver : `unite_exposition` est le prochain. *Le garde-fou suit la
    structure sans qu'on y pense.*

    ⚠️ LE MOTIF DIT QUOI FAIRE. Il nomme la clé fautive, l'endroit, et propose
    la plus proche des clés connues : une erreur d'orthographe se corrige si on
    voit le bon mot, pas si on lit « clé invalide ».
    """
    connues = {f.name for f in dataclasses.fields(classe)}
    inconnues = [k for k in d if k not in connues]
    if not inconnues:
        return
    details = []
    for k in sorted(inconnues):
        proches = difflib.get_close_matches(str(k), sorted(connues), n=1,
                                            cutoff=0.6)
        details.append(f"'{k}'" + (f" (vouliez-vous '{proches[0]}' ?)"
                                   if proches else ""))
    raise ValueError(
        f"Cle(s) inconnue(s) dans {ou} : {', '.join(details)}. "
        f"Le plan est le document que vous signez : une cle mal orthographiee "
        f"serait ignoree en silence et vous obtiendriez un autre tarif. "
        f"Cles acceptees ici : {', '.join(sorted(connues))}.")


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
    # Colonne d'ÉCHÉANCE (optionnelle) — l'observation d'un contrat à une date.
    # ⚠️ SANS ELLE, « DOUBLON » ET « ÉCHÉANCE » SONT INDISCERNABLES. Un contrat
    # observé sur trois exercices donne trois lignes de même identifiant : la
    # couche qualité les compte alors comme des redondances. Mesuré : un
    # historique de renouvellement sur 3 ans porte ~67 % de « doublons » pour
    # un seuil ROUGE à 5 % — le fichier est refusé avant d'être lu.
    #   déclarée   → un doublon est (identifiant, échéance) identiques ;
    #   non déclarée → un doublon est un identifiant répété, comme avant.
    # Purement un RÔLE de données, comme `identifiant_contrat` : elle n'entre
    # jamais dans colonnes_produites() et n'est donc jamais un facteur.
    echeance: str | None = None
    # Le comportement de renouvellement (optionnel). Voir `Comportement` :
    # c'est la troisieme nature de cible du plan, et la seule qui ouvre
    # l'estimation d'une elasticite-prix. Son ABSENCE n'est pas une erreur ;
    # sa declaration A MOITIE en est une.
    comportement: Comportement | None = None

    def __post_init__(self):
        # ── LES RÔLES FIXES DU PLAN : jamais des prédicteurs LIBRES ────────────
        # Trois colonnes déclarées portent un rôle FIXE dans les modèles :
        #   · `exposition`      → OFFSET du GLM de fréquence (coefficient figé à 1)
        #   · `cible_frequence` → RÉPONSE du modèle de fréquence, et POIDS du
        #                         modèle de coût moyen
        #   · `cible_cout`      → RÉPONSE du modèle de coût moyen
        # Aucune ne peut devenir un facteur libre. Pour l'exposition, ce serait la
        # fuite structurelle B9 : le modèle « explique » la sinistralité par la
        # durée d'exposition au lieu de la porter en offset, et la prime cesse
        # d'être proportionnelle à l'exposition. Pour les cibles, ce serait
        # prédire une grandeur PAR ELLE-MÊME.
        #
        # ⚠️⚠️ ET LE CONTRÔLE PORTE SUR TROIS SURFACES, PAS UNE — C'EST LE
        # CORRECTIF DU LOT 1.2 (constats `plan/C1` et `plan/C2`).
        # La spec (`plan_execution_6_actions.md` l.294) demandait : « `exposition`
        # et `log_exposition` ne doivent jamais figurer dans
        # `colonnes_produites()` ». Le code faisait EXACTEMENT cela — et c'était
        # insuffisant : une interaction produit `inter_age_expo`, qui n'est ni
        # `expo` ni `log_expo`, et passait donc la garde. Mesuré jusqu'à la prime :
        # rapport de 1,8339 au lieu de 2,0000 quand l'exposition double, soit
        # −8,3 %. **Le garde-fou était exact sur les formes prévues et muet sur
        # les autres** — il regardait une LISTE de noms au lieu d'une PROPRIÉTÉ.
        # On contrôle donc « cette déclaration dérive-t-elle d'un rôle fixe ? »
        # sur les trois surfaces par lesquelles un rôle fixe peut entrer :
        #   1. le NOM SOURCE du facteur    → attrape `expo` en one_hot (`expo_long`)
        #   2. les OPÉRANDES d'interaction → attrape `age × expo` (`inter_age_expo`)
        #   3. les COLONNES PRODUITES      → le contrôle d'origine, CONSERVÉ
        for role, interdits in (
            ("l'exposition (offset du GLM, coefficient figé à 1)",
             {"exposition", "log_exposition",
              self.exposition, f"log_{self.exposition}"}),
            ("la cible de FRÉQUENCE (réponse du modèle, poids du coût moyen)",
             {self.cible_frequence, f"log_{self.cible_frequence}"}),
            ("la cible de COÛT MOYEN (réponse du modèle)",
             {self.cible_cout, f"log_{self.cible_cout}"}),
        ):
            interdits = {x for x in interdits if x}
            self._refuser_role_fixe(
                role, "facteur", interdits,
                sorted({f.nom for f in self.facteurs if f.nom in interdits}))
            self._refuser_role_fixe(
                role, "operande d'interaction", interdits,
                sorted({f"{a} x {b}" for a, b in self.interactions
                        if a in interdits or b in interdits}))
            self._refuser_role_fixe(
                role, "colonne produite", interdits,
                sorted(set(self.colonnes_produites()) & interdits))

        # Cohérence : la famille de sévérité doit être une valeur connue.
        # ⚠️ Le jeu de valeurs est DÉRIVÉ du `Literal`, jamais recopié : une
        # famille ajoutée au type est acceptée sans toucher à ce contrôle. Une
        # liste recopiée ici se désynchroniserait — c'est le défaut que ce
        # fichier tout entier existe pour supprimer.
        if self.famille_severite not in _FAMILLES_SEVERITE:
            raise ValueError(
                f"Plan '{self.lob}' : famille_severite='{self.famille_severite}' "
                f"inconnue — attendu {' ou '.join(repr(x) for x in sorted(_FAMILLES_SEVERITE))}."
            )

    def _refuser_role_fixe(self, role: str, surface: str,
                           interdits: set, coupables: list) -> None:
        """Refuse une déclaration qui ferait entrer un rôle fixe comme prédicteur.

        ⚠️ La `surface` est nommée dans le message : un actuaire qui déclare une
        interaction avec l'exposition doit lire « operande d'interaction », pas
        un message générique qui l'enverrait chercher dans ses facteurs.
        """
        if not coupables:
            return
        raise ValueError(
            f"Plan '{self.lob}' : {coupables} — declaration refusee comme "
            f"{surface}. Cette colonne est {role} : elle entre dans les modeles "
            f"avec un ROLE FIXE, jamais comme predicteur libre. "
            f"Noms reserves pour ce role : {sorted(interdits)}. "
            f"Une interaction compte : `inter_a_b` fait entrer A ET B dans la "
            f"matrice de conception, et la prime cesse d'etre proportionnelle a "
            f"l'exposition (mesure : rapport 1,8339 au lieu de 2,0000)."
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
        if self.echeance:
            cols.append(self.echeance)
        if self.comportement:
            cols.extend(self.comportement.colonnes())
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
        """SHA-256 du plan, préfixé par la version de SCHÉMA — `sN:hash`.

        À inscrire dans l'audit_trail et les rapports. Deux axes, longtemps
        confondus dans un seul champ :
          · le CONTENU signé par l'actuaire — `version`, haché comme le reste ;
          · la STRUCTURE de ce qui est haché — `EMPREINTE_SCHEMA`, qui bouge
            quand la COMPOSITION du payload change (un champ ajouté / retiré).
        La version de schéma est À LA FOIS dans le payload haché — elle scelle
        l'empreinte et la fait bouger avec la constante — ET en préfixe lisible
        `sN:`, pour qu'un comparateur lise le schéma SANS recalculer. Une
        empreinte sans préfixe est HÉRITÉE, non revalidable — voir
        `comparer_empreinte`.
        """
        payload = json.dumps({
            "schema": EMPREINTE_SCHEMA,
            "lob": self.lob, "version": self.version, "auteur": self.auteur,
            "exposition": self.exposition,
            "cibles": [self.cible_frequence, self.cible_cout],
            "famille_severite": self.famille_severite,
            "identifiant_contrat": self.identifiant_contrat,
            "echeance": self.echeance,
            "comportement": (dataclasses_asdict(self.comportement)
                             if self.comportement else None),
            "facteurs": [
                {"nom": f.nom, "type": f.type, "encodage": f.encodage,
                 "transformation": f.transformation, "modalites": f.modalites,
                 "anteriorite": f.anteriorite, "reference": f.reference}
                for f in self.facteurs
            ],
            "interactions": [list(i) for i in self.interactions],
        }, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"s{EMPREINTE_SCHEMA}:{digest}"

    @staticmethod
    def comparer_empreinte(reference: str, actuelle: str) -> str:
        """Verdict schéma-conscient entre une empreinte signée et l'actuelle.

        Transforme un mismatch MUET (deux hex qui diffèrent, sans raison dite)
        en un verdict qui dit POURQUOI — c'est ce que le versionnage sert à
        publier. Quatre états, chacun appelant une action distincte :
          · IDENTIQUE            : même schéma, même hash — le tarif se rejoue ;
          · CONTENU_DIFFERENT    : même schéma, hash différent — la structure
                                   est la même, la différence est VRAIMENT du
                                   contenu (le plan a changé) ;
          · SCHEMA_DIFFERENT     : schémas différents — les hash ne se comparent
                                   pas (la composition diffère) ; pour comparer
                                   le contenu, RE-TARIFER le plan sous ce code ;
          · HERITE_NON_VERSIONNE : au moins une empreinte sans préfixe `sN:`
                                   (pré-versionnement) — non revalidable
                                   automatiquement (voie « retrait », arbitrée).
        """
        if ":" not in reference or ":" not in actuelle:
            return "HERITE_NON_VERSIONNE"
        schema_ref, hash_ref = reference.split(":", 1)
        schema_act, hash_act = actuelle.split(":", 1)
        if schema_ref != schema_act:
            return "SCHEMA_DIFFERENT"
        return "IDENTIQUE" if hash_ref == hash_act else "CONTENU_DIFFERENT"

    # ── Chargement depuis YAML/JSON ────────────────────────────────────────
    @classmethod
    def depuis_dict(cls, d: dict) -> "PlanTarifaire":
        # ⚠️⚠️ CONSTAT `plan/C5`, RANG 1 — LA PORTE AVALAIT LES CLÉS INCONNUES.
        # Le plan est le document OPPOSABLE : l'actuaire le signe. Mesuré,
        # `famille_severity: lognormal` (l'anglais) était accepté sans un mot
        # et rendait une **gamma** — soit **+1,00 % de prime totale, +42 124 €
        # sur 1 500 contrats**, jusqu'à 525,35 € sur un seul. *Il signait une
        # log-normale et obtenait autre chose.*
        #
        # ⚠️ ET LE CORRECTIF N'INVENTE RIEN : `Comportement` LEVAIT DÉJÀ sur une
        # clé inconnue (`TypeError` de son constructeur). Deux des trois
        # sous-objets du plan se taisaient, le troisième refusait. *L'asymétrie
        # entre voisins, dans le même fichier — et c'est le voisin qui a raison.*
        # Les trois passent désormais par la même porte, avec le même motif.
        _refuser_cles_inconnues(d, PlanTarifaire, "le plan")
        for _i, _f in enumerate(d.get("facteurs") or [], 1):
            _refuser_cles_inconnues(_f, Facteur, f"le facteur n°{_i} "
                                                f"('{_f.get('nom', '?')}')")
        if d.get("comportement"):
            _refuser_cles_inconnues(d["comportement"], Comportement,
                                    "le bloc `comportement`")
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
            echeance=d.get("echeance"),
            comportement=(Comportement(**d["comportement"])
                          if d.get("comportement") else None),
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
