# -*- coding: utf-8 -*-
"""
ActuarIA — Socle · CE QUE LE TARIF SAIT DE SA PROPRE QUALITÉ
============================================================

⚠️⚠️ L'OBJET QUI VEND NE MESURAIT RIEN DE LUI-MÊME. `TarifNonVie` portait le
plan, deux GLM, un écrêtement et des chargements — **aucun Gini, aucun statut,
aucun garde-fou**. Le pouvoir discriminant du modèle vivait chez A3, dans un
rapport que le tarif ne lit pas. *Un objet qui produit un prix sans savoir ce
que vaut son modèle ne peut pas le dire à celui qui le signe.*

⚠️⚠️ ET IL NE BLOQUE RIEN TOUT SEUL — C'EST LA DÉCISION DU 05/09/2026, PRISE
CONTRE MA PREMIÈRE PROPOSITION ET SUR MESURE.

Une première version refusait de produire un tarif quand l'intervalle de
confiance du Gini de holdout était entièrement sous zéro. Elle a été câblée,
et **la gate l'a réfutée** : le refus s'est déclenché sur trois cas. Mesuré
ensuite sur le chemin réel (`pipeline_complet`), 18 plans × 3 tailles :

    1 500 lignes : 2 refus sur 18   (`auto`, `bris_machine`)
    3 000 lignes : 1 refus sur 18   (`rc_produit`)
    4 000 lignes : 0 refus sur 18

***`auto` est refusé à 1 500 et accepté à 3 000 et 4 000 — même générateur,
même graine, même plan.*** Un verdict qui change avec la TAILLE de
l'échantillon sur les mêmes données mesure du bruit, pas un fait.

Et la cause se mesure. Sinistres d'apprentissage par paramètre du GLM de
sévérité, contre le Gini de holdout :

    `auto`         : 6,5 → 13,5 → 19,8   pour  -0,0900 → +0,0247 → +0,0418
    `bris_machine` : 12,9 → 27,1 → 37,6  pour  -0,1274 → -0,0134 → +0,0313
    `rc_produit`   : 11,3 → 21,9 → 27,0  pour  -0,0231 → **-0,1249** → -0,0577

Les deux premiers sont **monotones** : c'est un sur-apprentissage réel à faible
n/p. Le troisième est **non monotone** : celui-là a tiré sur du bruit — un
intervalle à 95 % tombe entièrement sous zéro environ 2,5 % du temps quand le
vrai effet est nul, et on en mesure dix-huit par exécution.

  **Deux mécanismes se confondaient sous un seul verdict, et l'effet était le
  plus violent du module : aucun tarif produit. Ce module PUBLIE — le Gini,
  son intervalle, l'effectif du holdout ET le rapport n/p qui dit si la
  mesure avait la puissance de conclure. L'actuaire signataire tranche.**

⚠️ Un blocage dur reste possible, mais il **se déclare au plan**
(`refus_anti_selection`, défaut `False`) : *un seuil qui bloque un tarif ne
s'invente pas dans le code qui l'applique.*
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

#: Le niveau de confiance de l'intervalle. ⚠️ 95 % est la convention usuelle
#: d'un intervalle de confiance — ce n'est pas un seuil de qualité inventé
#: pour ce module, et il est DIT plutôt que caché dans un littéral.
CONFIANCE = 0.95

#: Nombre de rééchantillonnages. ⚠️ Il ne décide de rien : il ne fait que
#: resserrer l'estimation des bornes. 400 suffit pour un IC à 95 % ; le
#: publier permet à un lecteur de refaire la mesure.
N_REECHANTILLONS = 400

#: En dessous, on ne prétend pas mesurer un intervalle. ⚠️ Ce n'est pas un
#: seuil de qualité : c'est le nombre en dessous duquel un rééchantillonnage
#: ne dit plus rien de fiable. L'absence est alors DÉCLARÉE, jamais remplacée
#: par des bornes fabriquées.
MINIMUM_POUR_INTERVALLE = 30

#: Les deux niveaux de mention. ⚠️ ROUGE ne veut pas dire « bloqué » : il veut
#: dire « à lire avant de signer ». Le blocage, lui, se déclare au plan.
ROUGE = 'ROUGE'
AMBRE = 'AMBRE'


def gini_lorenz(y_vrai, y_pred) -> float | None:
    """LE calcul de Gini de Lorenz DU SOCLE — 2 × aire de Lorenz − 1, en
    triant les contrats par la PRÉDICTION décroissante.

    ⚠️⚠️ IL EST ICI POUR NE PAS ÊTRE ÉCRIT UNE FOIS DE PLUS. Le contrôle
    `pipeline/C3` a mesuré, le 05/09/2026, que ce module en avait ajouté un
    **neuvième** au dépôt. *Deux chemins qui calculent la même grandeur avec
    deux codes finissent par diverger* — et ce n'est pas une crainte, c'est
    mesuré : voir la note de `direction_non_vie...pipeline_tarifaire.gini_lorenz`,
    qui délègue ici.

    ⚠️ IL REND `None`, JAMAIS `0.0`, quand le Gini n'est pas calculable :
    moins de deux lignes, longueurs incohérentes, ou cible de somme nulle.
    *Un zéro se lit « aucune discrimination mesurée », ce qui est un
    résultat ; l'absence de mesure n'en est pas un.* Un appelant qui a
    besoin d'un flottant convertit lui-même, **et le déclare**.

    ⚠️ Le tri est `mergesort` — donc STABLE. Ce n'est pas un détail de
    performance : sur des prédictions EX AEQUO (un GLM catégoriel en produit
    massivement), l'ordre des égalités change le Gini. Mesuré le 05/09/2026
    sur 500 lignes et 8 modalités : trois tris différents donnent 0,027476,
    0,046857 et 0,035429 pour la même donnée.
    """
    y_vrai = np.asarray(y_vrai, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_vrai) < 2 or len(y_vrai) != len(y_pred):
        return None
    ordre = np.argsort(-y_pred, kind='mergesort')
    y = y_vrai[ordre]
    total = float(y.sum())
    if total <= 0:
        return None
    cumul = np.cumsum(y) / total
    population = np.arange(1, len(y) + 1) / len(y)
    trapeze = getattr(np, 'trapezoid', None) or np.trapz
    return float(2.0 * trapeze(cumul, population) - 1.0)


@dataclass(frozen=True)
class Discrimination:
    """Le pouvoir discriminant d'un modèle, avec TOUT ce qui le fonde.

    ⚠️ `gini` peut être `None` : une mesure impossible n'est pas un zéro.
    ⚠️ `ic_bas`/`ic_haut` peuvent être `None` : sur trop peu de sinistres,
    l'intervalle n'est pas mesuré et **on le dit** au lieu d'inventer.
    ⚠️⚠️ `n_apprentissage` et `n_parametres` ne sont PAS décoratifs : leur
    rapport est ce qui permet de distinguer « ce modèle ne segmente pas » de
    « ce modèle a été ajusté sur trop peu de sinistres pour qu'on puisse le
    dire ». Sans eux, un Gini de holdout négatif n'est pas diagnosticable.
    """

    gini: float | None
    n_observations: int
    ic_bas: float | None = None
    ic_haut: float | None = None
    confiance: float = CONFIANCE
    #: Nombre de SINISTRES d'apprentissage. ⚠️ Le dénominateur d'un GLM de
    #: comptage ou de coût est le nombre d'ÉVÉNEMENTS, jamais de contrats —
    #: même doctrine qu'au lot 17a pour la puissance de sélection.
    n_apprentissage: int | None = None
    #: Nombre de paramètres du modèle ajusté (constante comprise).
    n_parametres: int | None = None

    @property
    def ic_entierement_negatif(self) -> bool:
        """L'intervalle est ENTIÈREMENT sous zéro.

        ⚠️⚠️ LE NOM DIT CE QUI EST MESURÉ, PAS CE QU'ON EN CONCLUT. Il
        s'appelait `anti_selection_etablie` : c'était un verdict, et la mesure
        du 05/09/2026 a montré qu'il ne le portait pas — le même plan bascule
        selon la taille du portefeuille. *Un nom qui conclut fait conclure
        ses lecteurs.*
        """
        return self.ic_haut is not None and self.ic_haut < 0

    @property
    def distinguable_de_zero(self) -> bool:
        """L'intervalle exclut zéro, d'un côté ou de l'autre."""
        if self.ic_bas is None or self.ic_haut is None:
            return False
        return not (self.ic_bas <= 0 <= self.ic_haut)

    @property
    def sinistres_par_parametre(self) -> float | None:
        """⚠️⚠️ LA PUISSANCE, EN UN NOMBRE. `None` si elle n'est pas mesurée —
        et une puissance non mesurée ne se remplace pas par une valeur
        rassurante."""
        if not self.n_apprentissage or not self.n_parametres:
            return None
        return float(self.n_apprentissage) / float(self.n_parametres)


@dataclass(frozen=True)
class Mention:
    """Une chose à lire avant de signer, avec son niveau et sa grandeur.

    ⚠️ `niveau` vaut `ROUGE` ou `AMBRE`. ROUGE ne bloque pas : il dit que
    c'est le point le plus lourd du rapport de validation.
    """

    niveau: str
    grandeur: str
    texte: str


@dataclass
class ValidationTarif:
    """Ce qu'un tarif sait de sa propre qualité, et ce qu'il en dit."""

    frequence: Discrimination | None = None
    severite: Discrimination | None = None
    #: Ce qui doit être LU. ⚠️ Aucune mention ne bloque, par construction.
    mentions: list[Mention] = field(default_factory=list)
    #: Les motifs de blocage, nommés. ⚠️ Vide sauf si le PLAN a demandé le
    #: blocage dur (`refus_anti_selection`). Le code ne le décide jamais seul.
    refus: list[str] = field(default_factory=list)

    @property
    def refuse(self) -> bool:
        return bool(self.refus)

    @property
    def niveau_max(self) -> str | None:
        """Le niveau le plus lourd présent, ou `None` s'il n'y a rien à lire."""
        niveaux = {m.niveau for m in self.mentions}
        if ROUGE in niveaux:
            return ROUGE
        if AMBRE in niveaux:
            return AMBRE
        return None


def mesurer_discrimination(y_vrai, y_pred, *, graine: int = 11,
                           n_tirages: int = N_REECHANTILLONS,
                           n_apprentissage: int | None = None,
                           n_parametres: int | None = None
                           ) -> Discrimination:
    """Le Gini et son intervalle de confiance, par rééchantillonnage.

    ⚠️ L'intervalle se mesure SUR LES MÊMES LIGNES que le Gini : c'est le
    portefeuille observé qui porte l'incertitude, pas une loi supposée.
    ⚠️ `n_apprentissage`/`n_parametres` traversent sans être recalculés : ils
    décrivent le modèle QUI A PRODUIT `y_pred`, que cette fonction ne voit pas.
    """
    y_vrai = np.asarray(y_vrai, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    n = len(y_vrai)
    point = gini_lorenz(y_vrai, y_pred)
    socle = {'n_apprentissage': n_apprentissage, 'n_parametres': n_parametres}
    if n < MINIMUM_POUR_INTERVALLE or point is None:
        # ⚠️ Trop peu d'observations : on rend le point s'il existe, et on
        # DÉCLARE l'absence d'intervalle. *Des bornes fabriquées sur douze
        # sinistres seraient plus trompeuses que pas de bornes du tout.*
        return Discrimination(gini=point, n_observations=n, **socle)
    rng = np.random.default_rng(graine)
    tirages = []
    for _ in range(n_tirages):
        indices = rng.integers(0, n, n)
        valeur = gini_lorenz(y_vrai[indices], y_pred[indices])
        if valeur is not None:
            tirages.append(valeur)
    if not tirages:
        return Discrimination(gini=point, n_observations=n, **socle)
    marge = (1.0 - CONFIANCE) / 2.0 * 100.0
    return Discrimination(
        gini=point, n_observations=n,
        ic_bas=float(np.percentile(tirages, marge)),
        ic_haut=float(np.percentile(tirages, 100.0 - marge)), **socle)


def _phrase_puissance(d: Discrimination) -> str:
    """La puissance de la mesure, en clair — ou son absence, déclarée."""
    ratio = d.sinistres_par_parametre
    if ratio is None:
        return ("Le rapport sinistres d'apprentissage / parametres N'A PAS ETE "
                "TRANSMIS : on ne peut pas dire si la mesure avait la "
                "puissance de conclure.")
    return (f"Le modele a ete ajuste sur {d.n_apprentissage} sinistres pour "
            f"{d.n_parametres} parametres, soit {ratio:.1f} sinistres par "
            f"parametre.")


def _phrase_ic_negatif(nom: str, d: Discrimination) -> str:
    """⚠️⚠️ LA MENTION ROUGE, ET ELLE EST DIAGNOSTICABLE.

    Elle ne dit PAS « anti-selection etablie » : la mesure du 05/09/2026 a
    montre que ce verdict n'est pas porte par la donnee — le meme plan bascule
    selon la taille du portefeuille. Elle dit ce qui est MESURE, puis ce qui
    permet de l'interpreter, puis ce qu'elle ne tranche pas.
    """
    return (
        f"NE DISCRIMINE PAS SUR HOLDOUT ({nom}) : Gini de holdout "
        f"{d.gini:+.4f} sur {d.n_observations} observations, intervalle a "
        f"{d.confiance:.0%} [{d.ic_bas:+.4f} ; {d.ic_haut:+.4f}] -- "
        f"entierement sous zero. {_phrase_puissance(d)} A ce rapport, un Gini "
        f"de holdout negatif s'explique aussi bien par un SUR-APPRENTISSAGE "
        f"que par un defaut de segmentation : cette mesure NE LES DISTINGUE "
        f"PAS. Aucun tarif n'est bloque -- l'actuaire signataire tranche."
    )


def _phrase_indistinguable(nom: str, d: Discrimination) -> str:
    return (
        f"POUVOIR DISCRIMINANT NON DISTINGUABLE DE ZERO ({nom}) : Gini de "
        f"holdout {d.gini:+.4f} sur {d.n_observations} observations, "
        f"intervalle a {d.confiance:.0%} [{d.ic_bas:+.4f} ; {d.ic_haut:+.4f}] "
        f"-- il contient zero. {_phrase_puissance(d)} Ce modele ne segmente "
        f"pas de facon etablie sur ce portefeuille. Ce n'est pas un defaut "
        f"prouve, c'est une mesure qui n'etablit rien : l'actuaire signataire "
        f"tranche."
    )


def _phrase_refus(nom: str, d: Discrimination) -> str:
    return (
        f"BLOCAGE DEMANDE PAR LE PLAN ({nom}) : `refus_anti_selection` est "
        f"declare, et l'intervalle du Gini de holdout est entierement sous "
        f"zero -- [{d.ic_bas:+.4f} ; {d.ic_haut:+.4f}] sur "
        f"{d.n_observations} observations. {_phrase_puissance(d)} Aucun tarif "
        f"n'est produit. Ce blocage vient du PLAN, pas du moteur."
    )


def valider(frequence: Discrimination | None = None,
            severite: Discrimination | None = None,
            *, refus_anti_selection: bool = False) -> ValidationTarif:
    """Le verdict du tarif sur lui-même. **Il PUBLIE ; il ne bloque pas.**

    ⚠️⚠️ AUCUN BLOCAGE PAR DÉFAUT, ET C'EST MESURÉ, PAS PRÉFÉRÉ. Une règle
    de refus sur « intervalle entièrement sous zéro » a été câblée puis
    réfutée par la gate : elle refusait `auto` à 1 500 lignes et l'acceptait
    à 3 000 et 4 000, mêmes données. *Une règle dont le verdict dépend de la
    taille de l'échantillon mesure du bruit.*

    ⚠️ `refus_anti_selection` vient du PLAN et de lui seul. Quand il est
    déclaré, l'assureur assume que ce cas doit bloquer ; le moteur ne prend
    jamais cette décision à sa place.
    """
    validation = ValidationTarif(frequence=frequence, severite=severite)
    for nom, d in (('frequence', frequence), ('severite', severite)):
        if d is None or d.gini is None:
            continue
        if d.ic_entierement_negatif:
            # ⚠️ La mention est ROUGE, et elle est publiée DANS TOUS LES CAS —
            # y compris quand le plan a demandé le blocage : *ce qui bloque
            # doit aussi être lisible par qui n'a pas vu la levée.*
            validation.mentions.append(
                Mention(ROUGE, nom, _phrase_ic_negatif(nom, d)))
            if refus_anti_selection:
                validation.refus.append(_phrase_refus(nom, d))
        elif d.ic_bas is not None and not d.distinguable_de_zero:
            validation.mentions.append(
                Mention(AMBRE, nom, _phrase_indistinguable(nom, d)))
    return validation


def publication(validation: ValidationTarif) -> dict[str, Any]:
    """La validation, sous une forme que les livrables savent lire.

    ⚠️ Chaque grandeur porte le nombre d'observations qui la fonde ET la
    puissance de la mesure : *un Gini sans son effectif ne se conteste pas, et
    un Gini négatif sans son n/p ne se diagnostique pas.*
    """
    def _bloc(d: Discrimination | None) -> dict[str, Any] | None:
        if d is None:
            return None
        ratio = d.sinistres_par_parametre
        return {
            'gini': None if d.gini is None else round(d.gini, 4),
            'n_observations': d.n_observations,
            'ic_bas': None if d.ic_bas is None else round(d.ic_bas, 4),
            'ic_haut': None if d.ic_haut is None else round(d.ic_haut, 4),
            'confiance': d.confiance,
            'n_apprentissage': d.n_apprentissage,
            'n_parametres': d.n_parametres,
            'sinistres_par_parametre': (None if ratio is None
                                        else round(ratio, 2)),
            'distinguable_de_zero': d.distinguable_de_zero,
            'ic_entierement_negatif': d.ic_entierement_negatif,
        }

    return {
        'frequence': _bloc(validation.frequence),
        'severite': _bloc(validation.severite),
        'mentions': [{'niveau': m.niveau, 'grandeur': m.grandeur,
                      'texte': m.texte} for m in validation.mentions],
        'niveau_max': validation.niveau_max,
        'refus': list(validation.refus),
        'refuse': validation.refuse,
    }
