"""
sp_mortalite.py — la mortalité de tarification, et la base qui l'accompagne.

LE DÉFAUT QUE CE MODULE FERME (D04)
P1 appelait `_get_qx(age_m)` alors que la signature est
`get_qx_th0002(age, sexe="M")`. L'argument était omis : **tout le portefeuille
était tarifé au taux masculin**. Écart de table mesuré : **+78,8 % à 45 ans**
(0,00295 contre 0,00165) et **+85,8 % à 60 ans**.

Le sexe n'était pas manquant : `sp_data_builder` produit une colonne `sexe` et
lui applique même un repli. C'était un argument oublié, pas une donnée absente.

POURQUOI LE DÉFAUT SUBSISTE QUELLE QUE SOIT LA DOCTRINE
Si l'entité tarifie en unisexe, le code appliquait un taux **masculin** — ce
n'est pas la même chose, et il sur-tarifait les femmes de 78,8 %. Si elle
tarifie en différencié, il ignorait une donnée disponible. **Aucune doctrine ne
rendait le code correct**, ce qui est le point : la correction n'attendait pas
l'arbitrage.

LE CHOIX RETENU, ET IL EST DÉCLARÉ
Par défaut, la tarification est **unisexe** — c'est le réglage le plus sûr au
regard du droit européen depuis l'arrêt Test-Achats (CJUE, 2011), qui a invalidé
la dérogation permettant d'utiliser le sexe comme facteur de tarification.
La fonction rend TOUJOURS un couple `(taux, base)` : la base voyage avec le
chiffre jusque dans le document, et un contrôleur peut la lire.

⚠️ Ce module ne tranche PAS la doctrine de l'entité — c'est l'arbitrage A4, et
il appartient à l'actuaire signataire. Il la rend explicite et traçable au lieu
de la prendre par défaut et en silence. La distinction tarification /
provisionnement reste entière : interdire le sexe au tarif n'interdit pas de
s'en servir pour évaluer un engagement.
"""

__all__ = ["DOCTRINE_SEXE", "doctrine", "mention_doctrine",
           "part_hommes", "qx_provisionnement", "qx_tarification"]


def part_hommes(profils, defaut=None):
    """Part d'hommes d'un portefeuille, ou `defaut` si le sexe n'est pas connu.

    Rend `None` quand aucun profil ne porte l'information : l'appelant saura
    alors qu'il tarifie sur une hypothèse et non sur une observation.
    """
    connus = [str(p.get("sexe", "")).strip().upper()[:1]
              for p in (profils or [])
              if str(p.get("sexe", "")).strip()]
    connus = [s for s in connus if s in ("M", "F")]
    if not connus:
        return defaut
    return sum(1 for s in connus if s == "M") / len(connus)


def qx_tarification(age, qx_fonction, part_h=None, unisexe=True):
    """Taux de décès de tarification, avec la base qui l'a produit.

    Parameters
    ----------
    qx_fonction : callable
        `f(age, sexe)` rendant le taux de la table, p. ex. `get_qx_th0002`.
    part_h : float, optionnel
        Part d'hommes observée dans le portefeuille. `None` si inconnue.
    unisexe : bool
        `True` (défaut) : un taux unique, quelle que soit la composition.
        `False` : le taux suit la composition réelle du portefeuille — à
        n'employer que si la doctrine de l'entité le permet.

    Returns
    -------
    (float, str) : le taux, et la base de mortalité, à publier À CÔTÉ du
                   chiffre. Jamais l'un sans l'autre.
    """
    q_h = float(qx_fonction(age, "M"))
    q_f = float(qx_fonction(age, "F"))

    if unisexe:
        if part_h is None:
            # Aucune observation : moyenne simple, et on le DIT.
            return (q_h + q_f) / 2.0, (
                "TH 00-02 unisexe (50/50 — composition du portefeuille inconnue)")
        taux = part_h * q_h + (1.0 - part_h) * q_f
        return taux, (
            "TH 00-02 unisexe (pondéré : %.0f%% d'hommes observés)"
            % (part_h * 100))

    if part_h is None:
        return (q_h + q_f) / 2.0, (
            "TH 00-02 unisexe (50/50 — tarification différenciée demandée "
            "mais sexe non renseigné)")
    taux = part_h * q_h + (1.0 - part_h) * q_f
    return taux, "TH 00-02 différencié par sexe (%.0f%% d'hommes)" % (part_h * 100)


# ── LES DEUX AXES DE L ARBITRAGE A4 ────────────────────────────────────────
# ⛔ DOCTRINE TRANCHEE PAR LE COMMANDITAIRE LE 12/09/2026.
#
# Tarifer et provisionner sont DEUX CHOSES DIFFERENTES, et l arbitrage porte
# sur deux axes qu il aurait ete faux de mettre sur le meme interrupteur :
#
#   TARIFICATION   -> UNISEXE. L arret Test-Achats (CJUE, 2011) a invalide la
#                     derogation permettant d utiliser le sexe comme facteur
#                     de tarification en assurance, pour les contrats conclus
#                     a compter de decembre 2012. C est le reglage le plus sur
#                     au regard du droit europeen.
#
#   PROVISIONNEMENT -> DIFFERENCIE. Interdire le sexe au TARIF n interdit pas
#                     de s en servir pour EVALUER un engagement. Une provision
#                     doit representer l engagement reel ; s interdire une
#                     information disponible la rendrait moins juste, sans
#                     rien apporter a l egalite de traitement des assures.
#
# ⚠️ ET LE REGLAGE SE DECLARE DANS LE DOCUMENT. C est un point qu un
# controleur demande a voir ecrit : `doctrine_sexe` porte les deux axes et
# leur motif jusqu au rapport, au lieu d etre une constante enfouie.

#: Les deux axes, et leur valeur par defaut arbitree.
DOCTRINE_SEXE = {
    "tarification": {
        "unisexe": True,
        "motif": ("arret Test-Achats (CJUE, 1er mars 2011, C-236/09) : le sexe "
                  "ne peut pas etre un facteur de tarification pour les "
                  "contrats conclus a compter du 21 decembre 2012"),
    },
    "provisionnement": {
        "unisexe": False,
        "motif": ("une provision evalue un engagement reel ; l interdiction "
                  "porte sur la TARIFICATION, pas sur l EVALUATION"),
    },
}


def doctrine(axe):
    """Rend `(unisexe, motif)` pour un axe — et refuse un axe inconnu.

    ⛔ Pas de valeur par defaut sur un axe inconnu : une doctrine supposee est
    exactement ce que cet arbitrage supprime. Un axe qu'on n'a pas prevu doit
    faire lever, pas retomber silencieusement sur l'unisexe.
    """
    if axe not in DOCTRINE_SEXE:
        raise KeyError(
            "Axe de doctrine inconnu : %r. Axes arbitres : %s. "
            "Un axe non arbitre ne doit pas heriter d'une valeur par defaut."
            % (axe, ", ".join(sorted(DOCTRINE_SEXE))))
    reglage = DOCTRINE_SEXE[axe]
    return reglage["unisexe"], reglage["motif"]


def mention_doctrine(axe):
    """La phrase a porter DANS le document, pour l'axe demande."""
    unisexe, motif = doctrine(axe)
    return ("Doctrine %s : mortalite %s. Motif : %s."
            % (axe, "UNISEXE" if unisexe else "DIFFERENCIEE PAR SEXE", motif))


def qx_provisionnement(age, qx_fonction, sexe=None):
    """Taux de deces de PROVISIONNEMENT — l'autre axe.

    Contrairement a `qx_tarification`, cet axe utilise le sexe quand il est
    connu : la doctrine arbitree est « differencie ». Quand il ne l'est pas,
    la fonction ne l'invente pas — elle rend le taux unisexe ET le dit.

    Returns
    -------
    (float, str) : le taux, et la base qui l'a produit.
    """
    unisexe_par_doctrine, _ = doctrine("provisionnement")

    sexe_lu = str(sexe or "").strip().upper()[:1]
    if not unisexe_par_doctrine and sexe_lu in ("M", "F"):
        return (float(qx_fonction(age, sexe_lu)),
                "TH/TF 00-02 sexe %s (provisionnement differencie)" % sexe_lu)

    taux_h = float(qx_fonction(age, "M"))
    taux_f = float(qx_fonction(age, "F"))
    moyenne = (taux_h + taux_f) / 2.0
    if unisexe_par_doctrine:
        base = "TH/TF 00-02 UNISEXE (doctrine de provisionnement)"
    else:
        base = ("TH/TF 00-02 UNISEXE — sexe NON RENSEIGNE, alors que la "
                "doctrine de provisionnement est differenciee")
    return moyenne, base
