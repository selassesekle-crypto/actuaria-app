"""
sp_csp.py — la catégorie socio-professionnelle, comptée une fois et une seule.

DEUX DÉFAUTS, UNE MÊME GRANDEUR.

D01 — LE FACTEUR CSP ÉTAIT APPLIQUÉ DEUX FOIS
La table BCAC 2019 centralisée est indexée `(age_min, age_max) : (cadre,
non_cadre)` : **elle porte déjà la différenciation CSP**. P1 multipliait ce taux
déjà différencié par un second facteur local, plus fin (quatre catégories), sans
jamais retirer le premier.

Mesuré le 12/09/2026, à 30, 40, 50 et 60 ans — l'écart est multiplicatif, donc
constant en relatif :

    ouvrier    table non_cadre 0,0630 × 1,35  →  0,0851   +35,0 %
    employe    table non_cadre 0,0630 × 1,00  →  0,0630     0,0 %
    cadre      table cadre     0,0380 × 0,75  →  0,0285   −25,0 %
    cadre_sup  table cadre     0,0380 × 0,60  →  0,0228   −40,0 %

La preuve la moins contestable est l'asymétrie entre voisins : P2, sur la MÊME
table centralisée, n'applique PAS le facteur — et l'applique sur son repli
local, où la table n'est pas différenciée et où il est légitime. Les deux agents
lisent la même source et en tirent deux tarifs.

LE CORRECTIF : UN FACTEUR RÉSIDUEL
Le facteur fin ne doit plus exprimer le groupe — que la table porte déjà — mais
seulement l'écart À L'INTÉRIEUR du groupe. On le normalise par le facteur de
référence de sa colonne. Le taux du groupe reste celui de la table, et la
finesse à quatre catégories est conservée au lieu d'être jetée.

Sur le chemin de REPLI, où la table locale n'a qu'une colonne (toutes CSP
confondues, 0,0420 à 40 ans — une valeur qui tombe bien entre 0,0380 et 0,0630),
le facteur plein reste légitime et n'est pas touché. C'était le risque principal
du correctif : corriger le bon chemin et casser l'autre.

D36 — LES CODES D'UNE LETTRE ÉTAIENT TOUS PERDUS
`sp_data_builder` met la colonne en minuscules, puis la compare à une table qui
contient « O », « E », « C », « CS » en MAJUSCULES. Mesuré : un portefeuille en
codes courts voyait **100 % de ses lignes devenir « employe »**. Combinée à D01,
toute la population était tarifée au facteur 1,00 — ni les ouvriers ni les
cadres ne recevaient leur tarif.

Et la reconnaissance était MUETTE : personne ne pouvait savoir combien de lignes
avaient été repliées. `normaliser_csp` rend désormais un couple
`(catégorie, reconnue)`, pour que l'appelant puisse compter et le diagnostic le
publier.
"""

__all__ = [
    "FACT_GROUPE_CENTRAL", "GROUPES", "groupe_bcac",
    "facteur_residuel", "construire_map_csp", "normaliser_csp",
]

# Facteur de reference de chaque colonne de la table centralisee.
# `employe` est la reference de la colonne non_cadre (facteur 1,00) ;
# `cadre` est celle de la colonne cadre (facteur 0,75).
FACT_GROUPE_CENTRAL = {"cadre": 0.75, "non_cadre": 1.00}

# Categories fines rattachees a chaque colonne de la table BCAC.
GROUPES = {
    "ouvrier":   "non_cadre",
    "employe":   "non_cadre",
    "cadre":     "cadre",
    "cadre_sup": "cadre",
}


def groupe_bcac(categorie):
    """Colonne de la table BCAC dont relève une catégorie fine."""
    return GROUPES.get(str(categorie).lower().strip(), "non_cadre")


def facteur_residuel(categorie, facteurs_fins):
    """Part du facteur CSP qui n'est PAS déjà portée par la table centralisée.

    Parameters
    ----------
    categorie : str
        Catégorie fine : ouvrier, employe, cadre, cadre_sup.
    facteurs_fins : dict
        La table locale des facteurs, p. ex. `FACT_CSP_ITT`.

    Returns
    -------
    (str, float) : la colonne BCAC à interroger, et le facteur résiduel à
                   appliquer à son taux.

    Exemple, avec FACT_CSP_ITT = {ouvrier 1,35 ; employe 1,00 ;
    cadre 0,75 ; cadre_sup 0,60} :

        ouvrier    → ('non_cadre', 1,35)   le taux non-cadre, majoré
        employe    → ('non_cadre', 1,00)   le taux non-cadre, tel quel
        cadre      → ('cadre',     1,00)   le taux cadre, tel quel
        cadre_sup  → ('cadre',     0,80)   le taux cadre, minoré
    """
    cat = str(categorie).lower().strip()
    groupe = groupe_bcac(cat)
    reference = FACT_GROUPE_CENTRAL.get(groupe, 1.0)
    if reference == 0:
        return groupe, 1.0
    return groupe, facteurs_fins.get(cat, 1.0) / reference


def construire_map_csp(csp_valides):
    """Table de correspondance variante → catégorie, insensible à la casse.

    ⚠️ Le `.lower()` est le correctif. Sans lui, les codes « O », « E », « C »
    et « CS » de la table de référence ne pouvaient pas rencontrer la colonne,
    qui avait été mise en minuscules juste avant la comparaison.
    """
    return {
        str(variante).lower().strip(): categorie
        for categorie, variantes in csp_valides.items()
        for variante in variantes
    }


def normaliser_csp(valeur, map_csp, csp_valides, defaut="employe"):
    """Rend `(catégorie, reconnue)`.

    Le second élément est l'apport : un repli silencieux ne se compte pas, et
    un diagnostic qui ne sait pas combien de lignes il a réparées ne mesure
    pas la qualité des données — il mesure ses propres réparations.
    """
    v = str(valeur).lower().strip()
    if v in map_csp:
        return map_csp[v], True
    if v in csp_valides:
        return v, True
    return defaut, False
