"""
sp_provenance.py — la provenance se déduit de la valeur, elle ne se déclare pas.

C'EST LA CAUSE COMMUNE DE L'AUDIT
Vingt-neuf des quarante-quatre constats relèvent d'un seul motif : **le nom
publié ne suit pas la valeur calculée**. Une provenance dit « données réelles »
sur une table nationale. Une table dit « TABLE PROPRIÉTAIRE CLIENT » en servant
la table interne. Le calcul n'est pas toujours faux ; la phrase qui l'accompagne
l'est presque toujours — et c'est elle qui sera lue par le commissaire aux
comptes.

LES DÉFAUTS FERMÉS

D18 — S1 cherchait la colonne `sinistre_<poste>` au SINGULIER quand
`SPDataBuilder` produit `sinistres_<poste>` au pluriel. Un `s` d'écart : la
recherche échouait en silence et tous les postes basculaient sur DREES 2023.
Mesuré, avec un portefeuille client complet : **5 postes sur 5 calculés depuis
DREES**, pendant que la sortie publiait `source_donnees = "donnees_reelles_a2"`.
La provenance était fixée **en amont**, sur la seule présence d'un DataFrame,
jamais sur l'usage effectif de ses colonnes.

C'est le défaut le plus coûteux commercialement : l'argument de vente du module
est la tarification sur données réelles. La donnée était chargée, nettoyée,
diagnostiquée… puis non lue, et la sortie affirmait le contraire.

D32 — SP-TABLES publiait `source_tables = "TABLE PROPRIÉTAIRE CLIENT"` dès que
`tables_client` était fourni, alors que cette table n'était transmise à **aucune
des cinq méthodes de calcul**. Injection d'une valeur témoin de 0,950 — choisie
pour être immanquable : la sortie valait 0,066, exactement la valeur du cas sans
client, et l'étiquette annonçait la table du client.

LE PRINCIPE
Une valeur et son étiquette sortent de la MÊME fonction, sur le MÊME chemin
d'exécution. Il devient alors structurellement impossible de publier une
provenance qui n'a pas servi. Et le cas MIXTE — une partie des postes du client,
le reste de la table — devient dicible, ce que l'ancienne version ne savait pas
exprimer.
"""

__all__ = [
    "colonne_sinistres", "source_reellement_retenue", "etiquette_et_valeur",
]


def colonne_sinistres(colonnes_disponibles, poste):
    """Nom de la colonne de sinistres pour un poste, ou `None`.

    Le nom canonique — celui que produit `SPDataBuilder` — est cherché
    d'abord ; l'ancienne orthographe ensuite, pour ne pas casser un jeu de
    données existant.
    """
    # ⚠️ Pas de `or []` ici : un `pandas.Index` leve sur l evaluation
    # booleenne (« The truth value of a Index is ambiguous »).
    colonnes = set(colonnes_disponibles) if colonnes_disponibles is not None else set()
    for candidat in ("sinistres_%s" % poste, "sinistre_%s" % poste):
        if candidat in colonnes:
            return candidat
    return None


def source_reellement_retenue(postes, source_amont=""):
    """Provenance DÉDUITE des postes réellement alimentés.

    Parameters
    ----------
    postes : dict
        `{nom du poste : {"source": ...}}`, tel que le calcul l'a produit.
    source_amont : str
        Ce que l'agent croyait avoir en entrée. Conservé pour mémoire, jamais
        publié seul.

    Returns
    -------
    (str, str) : la provenance, et son détail chiffré. Les deux voyagent avec
                 la valeur jusque dans le document.
    """
    postes = postes or {}
    if not postes:
        return "indeterminee", "Aucun poste calcule."

    reels = sorted(p for p, v in postes.items()
                   if (v or {}).get("source") == "donnees_client")
    total = len(postes)

    if not reels:
        return "tables_de_reference", (
            "Aucun des %d postes n'est alimente par les donnees client ; "
            "tarification sur tables de reference (amont declare : %s)."
            % (total, source_amont or "non precise"))

    if len(reels) == total:
        return "donnees_client", (
            "Les %d postes proviennent des donnees client." % total)

    return "mixte", (
        "%d poste(s) sur %d depuis les donnees client (%s) ; les autres sur "
        "tables de reference." % (len(reels), total, ", ".join(reels)))


def etiquette_et_valeur(valeur_client, etiquette_client,
                        valeur_defaut, etiquette_defaut,
                        lecture_reussie):
    """Rend `(valeur, étiquette)` — jamais l'une sans l'autre.

    ⚠️ Le troisième argument de `lecture_reussie` est le cœur du correctif :
    une étiquette ne doit JAMAIS rester accrochée à une lecture qui a échoué.
    C'est précisément le piège que l'ancien code n'évitait pas — il choisissait
    l'étiquette sur la seule PRÉSENCE d'une table client, sans savoir si elle
    avait servi.
    """
    if lecture_reussie:
        return valeur_client, etiquette_client
    return valeur_defaut, etiquette_defaut
