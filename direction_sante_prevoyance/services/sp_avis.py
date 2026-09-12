"""
sp_avis.py — on ne rend pas un avis actuariel sur une donnée absente.

LE DÉFAUT QUE CE MODULE FERME (D26, D12, D33)
Les règles de statut du module ne connaissaient que DEUX états : validée, ou
non. L'absence de mesure tombait donc du côté favorable, parce que toutes les
comparaisons étaient orientées dans le sens où zéro est la meilleure valeur
possible :

    statut = "VALIDÉE" if 0.55 <= lr <= 0.90 or lr == 0 else "À JUSTIFIER"
    statut = "VALIDÉE" if conforme_scr or scr_consolide == 0 else "NON VALIDÉE"
    rag    = "ROUGE"   if not conforme_mcr and mcr_consolide > 0 else …

Mesuré le 12/09/2026 : `AgentSPRapportActuariel().run()` **sans aucune donnée**
rendait `success=True`, un RAG **VERT**, un avis **FAVORABLE**, trois hypothèses
**VALIDÉES sur des zéros**, un Word de **37 005 octets** et un Excel de **12 281
octets**. Le document ne se trahissait pas lui-même : rien, dans son texte, ne
disait que le périmètre était vide.

Le même motif vivait ailleurs : l'hypothèse H1 de P3, non testable sur un
triangle trop court, sortait « VALIDÉE, score 80 » ; l'hypothèse H3 de SP-ALM
vérifiait une duration après l'avoir écrêtée aux mêmes bornes.

LE PRINCIPE : UN TROISIÈME ÉTAT
« NON MESURÉE » dit la seule chose vraie quand la donnée manque — on ne sait
pas. « NON ÉMIS » joue le même rôle au niveau de l'avis. Ce n'est pas une
prudence de façade : un actuaire qui signe engage sa responsabilité, et un
module qui rend un avis favorable sans rien examiner l'engage à sa place.

CE COMPORTEMENT EXISTAIT DÉJÀ DANS LE DÉPÔT
SP-ALM plafonne son propre RAG à AMBRE lorsqu'il travaille sur une allocation
d'actifs par défaut plutôt que sur celle du client : il refuse de se déclarer
vert sur une hypothèse qu'il a lui-même fournie. Ce module ne fait que
généraliser ce que cet agent faisait seul.
"""

__all__ = [
    "MODULES_MINIMAUX", "NON_MESUREE", "NON_EMIS",
    "statut_hypothese", "statut_borne", "rag_et_avis",
]

# Sans ces modules, aucune grandeur consolidée n'existe : le rapport n'a pas
# d'objet, et son avis n'aurait rien a decrire.
MODULES_MINIMAUX = frozenset({"S3", "P4"})

NON_MESUREE = "NON MESURÉE"
NON_EMIS = "NON ÉMIS"


def statut_hypothese(valeur, borne_basse, borne_haute, mesure):
    """Statut d'une hypothèse bornée, avec l'absence comme état distinct.

    Parameters
    ----------
    mesure : bool
        `False` quand la grandeur n'a PAS été mesurée. C'est l'appelant qui
        le sait — une valeur nulle peut être une vraie mesure à zéro.

    Returns
    -------
    (str, str) : statut et motif. Le motif accompagne le statut jusque dans
                 le document : un lecteur doit savoir POURQUOI.
    """
    if not mesure:
        return NON_MESUREE, "aucune donnée disponible — hypothèse non évaluable"
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return NON_MESUREE, "valeur non numérique — hypothèse non évaluable"
    if borne_basse <= v <= borne_haute:
        return "VALIDÉE", "%.1f%% dans [%.0f%%, %.0f%%]" % (
            v * 100, borne_basse * 100, borne_haute * 100)
    return "À JUSTIFIER", "%.1f%% hors de [%.0f%%, %.0f%%]" % (
        v * 100, borne_basse * 100, borne_haute * 100)


def statut_borne(respectee, mesure, libelle_ok, libelle_ko):
    """Statut d'une hypothèse binaire (un seuil respecté ou non).

    Même principe : l'absence de mesure ne bascule pas du côté favorable.
    """
    if not mesure:
        return NON_MESUREE, "aucune donnée disponible — seuil non vérifiable"
    return ("VALIDÉE", libelle_ok) if respectee else ("NON VALIDÉE", libelle_ko)


def rag_et_avis(hypotheses, modules_disponibles):
    """Rend (rag, avis, motif) à partir des hypothèses et du périmètre réel.

    L'ordre des règles est délibéré : le périmètre d'abord. Une hypothèse ne
    peut pas être « validée » sur un périmètre qui n'existe pas, et c'est
    précisément ce que faisait l'ancienne règle.
    """
    presents = {str(m).upper() for m in (modules_disponibles or [])}
    manquants = sorted(MODULES_MINIMAUX - presents)
    if manquants:
        return "ROUGE", NON_EMIS, (
            "Modules indispensables absents : %s. Aucun avis actuariel ne peut "
            "être émis sur ce périmètre." % ", ".join(manquants))

    non_mesurees = [h["id"] for h in hypotheses if h.get("statut") == NON_MESUREE]
    if non_mesurees:
        return "AMBRE", "AVEC RÉSERVES", (
            "Hypothèses non mesurées : %s." % ", ".join(non_mesurees))

    rejetees = [h["id"] for h in hypotheses
                if h.get("statut") == "NON VALIDÉE" and h.get("critique")]
    if rejetees:
        return "ROUGE", "DÉFAVORABLE", (
            "Hypothèse critique rejetée : %s." % ", ".join(rejetees))

    a_justifier = [h["id"] for h in hypotheses if h.get("statut") == "À JUSTIFIER"]
    if a_justifier:
        return "AMBRE", "AVEC RÉSERVES", (
            "Points à documenter : %s." % ", ".join(a_justifier))

    return "VERT", "FAVORABLE", "Toutes les hypothèses mesurées et validées."
