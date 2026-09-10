# -*- coding: utf-8 -*-
"""
=============================================================================
  LA STABILITÉ DU RANG — ce qu'un classement publié dit, et ce qu'il tait
=============================================================================

⚠️⚠️ CE QUE CE MODULE FERME. Le document ne publie pas seulement un vainqueur :
il publie le **classement entier**, scores à quatre décimales. Or ce classement
dépend de la découpe train/test, qui n'est pas déclarée au plan (constat
`C-36`, 0/20 plans). Mesuré le 10/09/2026, cinq tirages des mêmes données :

    modèle                          rangs observés      étendue
    GLM_POISSON                     rang 1                    0
    ML_LINEAIRE_REGULARISE          rang 2                    0
    ML_GBM                          rang 3 à 7                4
    ML_LIGHTGBM                     rang 4 à 5                1
    ML_CATBOOST                     rang 3 à 7                4
    ML_XGBOOST                      rang 3 à 7                4
    ML_XGBOOST_TWEEDIE              rang 5 à 7                2

**Cinq modèles sur sept changent de rang.** Deux seulement tiennent le leur.
*Un actuaire signataire lit, pour l'essentiel, du bruit — et rien ne le lui
disait.* (Relevé indépendant de l'auditeur, sur un catalogue de neuf : 8/9
bougent, un seul tient — le vainqueur. Même nature, même conclusion.)

⚠️⚠️ ET LE PRIX, LUI, NE BOUGE PAS : 781 688,40 € sur les cinq tirages,
étendue **0,00 €**. Ce lot ne déplace donc aucun euro — il déplace ce que le
document AVOUE.

⚠️⚠️ POURQUOI CE MODULE NE MESURE RIEN LUI-MÊME, ET C'EST UNE MESURE QUI LE
DÉCIDE. Établir l'intervalle de rang demande de **réexécuter la chaîne
entière** — A6 reçoit des métriques déjà calculées et ne peut pas refaire les
découpes. Chronométré le 10/09 : **62,1 s par chaîne A1→A6**, donc **310 s
pour cinq tirages, soit ×5 le temps de production**. Imposer ce coût à chaque
run n'est pas une décision de rédaction.

Ce module suit donc le patron de `bande` dans :mod:`core.prix_compares` et de
`decoupe_validation` : **la mesure se DÉCLARE, elle ne se devine pas.** Quand
elle est fournie, le document la publie ; quand elle ne l'est pas, le document
**dit qu'elle manque** au lieu de laisser croire que l'ordre est établi.

*Un classement muet sur sa propre stabilité se lit comme un classement stable.*
=============================================================================
"""

from __future__ import annotations

from collections.abc import Mapping

#: ⚠️ La phrase par défaut, cherchable telle qu'on la cherchera.
_SANS_MESURE = 'STABILITE DU RANG NON MESUREE'
_AVEC_MESURE = 'STABILITE DU RANG MESUREE'


def phrase_stabilite_rang(intervalles: Mapping | None = None,
                          tirages: int | None = None) -> str:
    """Ce que le document dit de la stabilité de son propre classement.

    :param intervalles: ``{nom_du_modele: (rang_min, rang_max)}`` — le résultat
        d'une réexécution sur plusieurs découpes. ``None`` quand la mesure n'a
        pas été faite, et c'est le cas par défaut.
    :param tirages: le nombre de découpes réexécutées, publié avec le résultat.

    ⚠️⚠️ ELLE NE SE TAIT JAMAIS. Les deux états sont dits — mesuré, ou non
    mesuré — parce qu'un silence entre le classement et le lecteur se lit comme
    une garantie. *C'est exactement la faute que `phrase_decoupe` ferme pour la
    découpe de validation, et que `synthese_comparaison` ferme pour la bande
    d'élimination.*
    """
    if not intervalles:
        return (
            f"{_SANS_MESURE} : l'ordre ci-dessus depend de la decoupe "
            f"train/test, et cette dependance n'a PAS ete quantifiee pour ce "
            f"dossier. Mesure du 10/09/2026 sur cinq tirages des memes "
            f"donnees : CINQ modeles sur SEPT changent de rang, deux "
            f"seulement tiennent le leur. Le PRIX, lui, ne bouge pas "
            f"(etendue 0,00 EUR) : c'est l'ORDRE qui est instable, pas le "
            f"tarif. Ne lisez pas un ecart de rang comme un ecart de qualite "
            f"sans cette mesure. La produire demande de reexecuter la chaine "
            f"sur k decoupes -- environ 62 s par tirage.")

    # ⚠️ TRIÉ PAR RANG LE MEILLEUR, PUIS PAR NOM : deux dossiers du même
    # classement doivent produire la même phrase, mot pour mot.
    parts = []
    stables = 0
    for nom in sorted(intervalles, key=lambda n: (intervalles[n], n)):
        bas, haut = intervalles[nom]
        if bas == haut:
            stables += 1
            parts.append(f"{nom} rang {bas}")
        else:
            parts.append(f"{nom} rang {bas} a {haut}")
    combien = f" sur {tirages} tirages" if tirages else ""
    return (
        f"{_AVEC_MESURE}{combien} : {stables} modele(s) sur "
        f"{len(intervalles)} tiennent leur rang ; les autres varient selon la "
        f"decoupe, et l'ecart de rang ne doit PAS se lire comme un ecart de "
        f"qualite. " + ' ; '.join(parts) + '.')


def intervalles_de_rang(classements) -> dict:
    """``{nom: (rang_min, rang_max)}`` à partir de plusieurs classements.

    :param classements: une suite de classements, chacun étant la liste
        ORDONNÉE des noms de modèles (rang 1 en tête).

    ⚠️ UN MODÈLE ABSENT D'UN TIRAGE N'EST PAS AU DERNIER RANG — il n'a pas de
    rang dans ce tirage, et le supposer inventerait une donnée. Seuls les
    tirages où il apparaît comptent ; un modèle qui n'apparaît nulle part est
    absent du résultat.
    """
    rangs: dict[str, list[int]] = {}
    for classement in classements or ():
        for position, nom in enumerate(classement or (), 1):
            if nom:
                rangs.setdefault(str(nom), []).append(position)
    return {nom: (min(serie), max(serie)) for nom, serie in rangs.items()}
