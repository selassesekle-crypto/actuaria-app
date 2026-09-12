"""
sp_reconciliation.py — un contrôle de cohérence n'atteste que si ses deux
côtés peuvent diverger.

LE DÉFAUT FERMÉ (D31)
C2, C3 et C4 de SP-COHÉRENCE comparent chacun deux « sources » d'une même
grandeur. En remontant les deux chemins de lecture, ils aboutissent **au même
dictionnaire, produit par le même agent** : SP-REG2 lit le BE santé chez S3 et
le compare à celui de S3 ; SP-REG1 lit le SCR consolidé chez SP-Coord et le
compare à celui de SP-Coord.

⚠️ LA MESURE QUI TRANCHE, ET ELLE N'EST PAS CELLE DE L'AUDIT.
L'audit avait injecté un écart *entre les deux lectures* et conclu « le code
du filet est bon » — ce qui est vrai et ne dit rien de l'assiette. La mesure
décisive perturbe **le producteur amont**, une seule fois, et regarde si les
deux côtés suivent :

    BE santé de S3 multiplié par 3      -> les DEUX côtés passent à 412 660 €,
                                           écart 0,0 %, statut « ✅ OK »
    BE prévoyance de P4 multiplié par 3 -> les DEUX côtés passent à  45 400 €,
                                           écart 0,0 %, statut « ✅ OK »
    SCR de SP-Coord multiplié par 3     -> les DEUX côtés passent à 338 213 €,
                                           écart 0,0 %, statut « ✅ OK »

Un contrôle qui certifie une grandeur multipliée par trois ne surveille pas
cette grandeur. Et SP-COHÉRENCE était le seul agent VERT du pipeline : sa
couleur verte était le meilleur argument de fiabilité du module, et elle
venait de contrôles qui ne pouvaient pas échouer.

CE QUE CE MODULE FAIT — ET CE QU'IL NE FAIT PAS
Il RECOMPOSE chaque grandeur **à partir de ses composantes**, chez l'agent qui
les calcule, par un chemin arithmétique qui ne passe pas par l'agent contrôlé :

    BE santé      = PSAP dossiers + PSAP IBNR              (chez S2, pas S3)
    BE prévoyance = PSAP IP + PM rentes IP + BE ITT        (chez P3, pas P4)
    SCR consolidé = racine(SCR_s² + SCR_p² + 2 rho SCR_s SCR_p)
                                                           (depuis S3 et P4,
                                                            pas depuis SP-Coord)

⛔ CE QUE CETTE RECOMPOSITION NE PROUVE PAS, et je refuse de le laisser croire.
Elle détecte une transcription fautive, un double compte, une composante
oubliée, une erreur d'unité, une agrégation erronée — c'est-à-dire tout ce
qui se passe ENTRE le calcul et la publication. Elle ne détecte PAS une erreur
à l'intérieur du calcul de S2 ou de P3 : les deux côtés reposent alors sur les
mêmes composantes. Une indépendance complète exigerait un second modèle de
provisionnement, ce qui est une décision d'architecture et non une fonction à
écrire. `independant` vaut donc `True` au sens « chemins arithmétiques
distincts », pas au sens « modèles distincts », et `nature_independance` le
dit en toutes lettres dans le document.

LE PRINCIPE QUI NE SE NÉGOCIE PAS
`statut_reconciliation` ne peut **pas** rendre « OK » quand l'indépendance
n'est pas établie. Un écart nul entre deux copies n'est pas une concordance,
et le document doit porter la différence.
"""

import math

__all__ = [
    "NON_INDEPENDANT", "RHO_SANTE_PREVOYANCE",
    "recomposer_be_sante", "recomposer_be_prevoyance",
    "recomposer_scr_consolide", "statut_reconciliation",
]

# Coefficient de correlation entre module sante NSLT et module vie invalidite,
# annexe IV du RD (UE) 2015/35.
RHO_SANTE_PREVOYANCE = 0.25

# L etat qu un controle prend lorsque ses deux cotes ne sont PAS independants.
# Ce n est ni OK ni ECART : c est l aveu que le controle n a rien mesure.
NON_INDEPENDANT = "NON INDEPENDANT"

NATURE_COMPOSANTES = (
    "chemins arithmetiques distincts (recomposition par composantes) — "
    "NON deux modeles distincts"
)


def _nombre(source, cle):
    """Lit un nombre sans jamais lever, et dit si la clé existait."""
    if not isinstance(source, dict) or cle not in source:
        return 0.0, False
    try:
        return float(source[cle]), True
    except (TypeError, ValueError):
        return 0.0, False


def _recomposer(source, composantes, libelle):
    """Somme des composantes, avec le détail de ce qui a été trouvé.

    Rend `(valeur, detail, complete)`. `complete` est faux dès qu'une
    composante manque : une somme amputée ressemblerait à un écart réel, et
    ferait crier le contrôle au lieu de le faire taire.
    """
    total = 0.0
    trouvees, manquantes = [], []
    for cle in composantes:
        valeur, presente = _nombre(source, cle)
        if presente:
            total += valeur
            trouvees.append("%s=%s" % (cle, format(valeur, ",.2f")))
        else:
            manquantes.append(cle)
    detail = "%s = %s" % (libelle, " + ".join(trouvees) or "(aucune composante)")
    if manquantes:
        detail += " | composantes absentes : %s" % ", ".join(manquantes)
    return total, detail, not manquantes


def recomposer_be_sante(result_s2):
    """BE santé recomposé chez S2 — le chemin qui ne passe pas par S3.

    S3 publie `be_sante` en recopiant la provision totale de S2. S2, lui,
    calcule la PSAP dossier par dossier et l'IBNR par triangle : les deux
    composantes existent séparément, et leur somme est une seconde arrivée
    à la même grandeur.
    """
    return _recomposer(result_s2, ("psap_dossiers", "psap_ibnr"),
                       "BE sante recompose")


def recomposer_be_prevoyance(result_p3):
    """BE prévoyance recomposé chez P3 — le chemin qui ne passe pas par P4.

    P4 publie `be_prevoyance` en le lisant dans `sorties_p4`. P3 calcule
    séparément la PSAP IP, la PM de rentes IP et le BE ITT.
    """
    return _recomposer(result_p3, ("psap_ip", "pm_rentes_ip", "be_itt"),
                       "BE prevoyance recompose")


def recomposer_scr_consolide(scr_sante, scr_prevoyance, rho=RHO_SANTE_PREVOYANCE):
    """SCR consolidé recalculé depuis les SCR de branche.

    SP-REG1 lisait le SCR consolidé chez SP-Coord. Ici il est REFAIT à partir
    de `scr_sante` (S3) et `scr_invalidite` (P4), par la formule d'agrégation
    de l'annexe IV. Le contrôle porte alors sur l'AGRÉGATION elle-même, ce
    qu'une lecture ne pouvait pas faire.

    Rend `(valeur, detail, complete)`.
    """
    try:
        a = float(scr_sante or 0.0)
        b = float(scr_prevoyance or 0.0)
    except (TypeError, ValueError):
        return 0.0, "SCR de branche illisibles", False

    if a <= 0 or b <= 0:
        return 0.0, (
            "SCR de branche indisponibles (sante=%s, prevoyance=%s) : "
            "l agregation ne peut pas etre refaite" % (a, b)), False

    valeur = math.sqrt(a ** 2 + b ** 2 + 2 * rho * a * b)
    detail = (
        "SCR consolide recalcule = racine(%s^2 + %s^2 + 2 x %s x %s x %s) = %s"
        % (format(a, ",.0f"), format(b, ",.0f"), rho,
           format(a, ",.0f"), format(b, ",.0f"), format(valeur, ",.0f"))
    )
    return valeur, detail, True


def statut_reconciliation(valeur_a, valeur_b, seuil, independant,
                          motif_non_independance=""):
    """Rend `(ok, statut, ecart, mention)`.

    ⛔ LA RÈGLE CENTRALE : `ok` est FAUX dès que `independant` est faux, quel
    que soit l'écart. Un écart nul entre deux copies de la même valeur n'est
    pas une concordance — c'est l'absence de mesure, et le document doit le
    dire au lieu d'afficher « ✅ Réconciliation OK ».
    """
    if not independant:
        return (False, NON_INDEPENDANT, None,
                motif_non_independance or
                "les deux cotes proviennent du meme producteur : ce controle "
                "n atteste rien")

    try:
        a = float(valeur_a)
        b = float(valeur_b)
    except (TypeError, ValueError):
        return (False, NON_INDEPENDANT, None,
                "valeurs illisibles : aucun ecart calculable")

    if a == 0 and b == 0:
        return (False, NON_INDEPENDANT, None,
                "les deux cotes valent zero : un ecart nul ne mesure rien")

    ecart = abs(a - b) / max(abs(a), 1.0)
    ok = ecart <= seuil
    mention = "%s : ecart %s %s seuil %s (%s)" % (
        "CONCORDANT" if ok else "ECART",
        format(ecart, ".2%"), "<=" if ok else ">", format(seuil, ".0%"),
        NATURE_COMPOSANTES)
    return ok, ("OK" if ok else "ECART"), ecart, mention
