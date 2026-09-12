"""
sp_fonds_propres.py — des fonds propres ne se calculent pas, et un MCR non plus.

LES DÉFAUTS FERMÉS (D13, D20, D22, D23)

D20 / D13 / D22 — TROIS MONTANTS POUR LA MÊME ENTITÉ. En l'absence de fonds
propres fournis, chaque agent en fabriquait par une règle qui lui était propre,
et aucun ne le signalait :

    S3 santé       pa x 0,80               ->    379 652 EUR
    P4 prévoyance  max(est, pa x 2,00)     ->    877 105 EUR
    SP-Coord       max(..., BE x 1,50)     ->  3 309 743 EUR

Le consolidé valait **2,63x la somme de ses branches**, et deux de ces montants
apparaissaient dans le **même dépôt réglementaire**, dans deux QRT différents.
Pire : le `max` de SP-Coord **écrasait la donnée client** dès qu'elle lui était
inférieure — testé à 1 200 000 EUR. Un `max` sur une donnée fournie n'est pas un
repli, c'est une substitution.

Des fonds propres éligibles **se lisent dans un bilan prudentiel**. Aucune
formule ne peut les produire à partir des primes ou du Best Estimate : la
question n'est donc pas laquelle des trois règles est la bonne — **aucune des
trois n'est une formule légitime**.

D23 — LE MCR CONSOLIDÉ ADDITIONNAIT DEUX PLANCHERS ABSOLUS.
Le Règlement délégué (UE) 2015/35 fixe l'ordre des opérations :

    MCR = max(MCR_combined ; AMCR)                              — art. 248 §1
    MCR_combined = min( max(MCR_linear ; 0,25 x SCR) ; 0,45 x SCR )
                                                                — art. 248 §2
    MCR_linear = MCR(linear,nl) + MCR(linear,l)                 — art. 249

Ce sont les termes LINÉAIRES qui s'additionnent, jamais des MCR déjà planchés.
Puis le corridor. Puis le plancher absolu, **une seule fois**. L'article 252
confirme le même ordre pour les entreprises multibranches.

LES COEFFICIENTS, À LEUR VRAIE SOURCE
Le code citait « Art. 252 » — lequel s'intitule *Minimum de capital requis :
entreprises d'assurance multibranches* et ne contient aucun coefficient. Les
facteurs sont à l'**annexe XIX**, appelée par l'**article 250 §1 point d)**.
Aucune des six valeurs présentes dans le code n'y figure, et toutes
sous-estimaient le MCR :

    segment                      alpha (prov.)   beta (primes)   code avant
    1 frais medicaux (sante)         4,7 %          4,7 %        4,53 / 3,51
    2 protection du revenu (prev.)  13,1 %          8,5 %        3,38 / 1,91

⚠️ Noter aussi que le Règlement nomme **alpha le facteur sur les PROVISIONS**
et **beta celui sur les PRIMES** : `p4_reporting` avait les deux à l'envers.
"""

__all__ = [
    "AMCR_NON_VIE", "COEFF_MCR", "MCR_CORRIDOR_BAS", "MCR_CORRIDOR_HAUT",
    "fonds_propres_declares", "ligne_qrt_fonds_propres",
    "mcr_lineaire_segment", "mcr_entite",
    "MENTION_NON_CALCULABLE", "RATIO_NON_CALCULABLE",
    "ratio_atteint", "ratio_couverture", "statut_sans_ratio",
    "texte_ratio",
]

# Annexe XIX du RD (UE) 2015/35, appelee par l article 250 par. 1 point d).
# alpha porte sur les PROVISIONS TECHNIQUES, beta sur les PRIMES EMISES.
COEFF_MCR = {
    "frais_medicaux":       {"alpha": 0.047, "beta": 0.047,
                             "libelle": "Segment 1 — assurance des frais medicaux",
                             "lob": "1 et 13"},
    "protection_du_revenu": {"alpha": 0.131, "beta": 0.085,
                             "libelle": "Segment 2 — assurance de protection du revenu",
                             "lob": "2 et 14"},
}

# Corridor de l article 248 par. 2.
MCR_CORRIDOR_BAS = 0.25
MCR_CORRIDOR_HAUT = 0.45

# ⚠️ SEUIL PLANCHER ABSOLU -- NON VERIFIE.
# Il vient de l article 129 par. 1 point d) de la DIRECTIVE 2009/138/CE, qui
# n est PAS sur ce disque (seul le reglement delegue y est), et il est revisable
# et indexe. C est le seul chiffre de ce module qui ne repose pas sur une
# lecture. A confirmer avant toute soumission.
AMCR_NON_VIE = 2_500_000.0


def fonds_propres_declares(fonds_propres, primes_acquises, coefficient, origine):
    """Rend `(valeur, estimee, mention)`.

    Le troisième élément est l'apport : une estimation qui ne se déclare pas
    est indiscernable d'une donnée de bilan, et c'est exactement ce qui
    permettait à trois montants différents de coexister sans que personne ne
    s'en aperçoive.

    ⚠️ Ce module ne fait PAS converger les trois valeurs — choisir suppose de
    savoir ce que l'entité entend par fonds propres éligibles consolidés, et
    c'est une décision d'actuaire, pas de code. Il rend le problème VISIBLE.
    """
    if float(fonds_propres or 0.0) > 0:
        return float(fonds_propres), False, ""

    valeur = float(primes_acquises or 0.0) * float(coefficient)
    mention = (
        "ESTIMATION — fonds propres non fournis : %.0f%% des primes acquises "
        "(%s). Sans base reglementaire ; a remplacer par les fonds propres "
        "eligibles du bilan prudentiel avant toute soumission."
        % (float(coefficient) * 100, origine))
    return valeur, True, mention


def ligne_qrt_fonds_propres(code, valeur, estimee, mention, colonne="C0050"):
    """Ligne de QRT qui porte sa mention d'estimation DANS son libellé.

    Un avertissement de journal n'atteint pas le document ; un libellé de
    ligne, si. C'est toute la différence entre signaler et être lu.
    """
    ligne = {
        "code": code,
        "libelle": "Fonds propres eligibles",
        colonne: round(float(valeur), 0),
    }
    if estimee:
        ligne["libelle"] += " — VALEUR ESTIMEE, NON AUDITABLE"
        ligne["mention_obligatoire"] = mention
        ligne["estime"] = True
    return ligne


def mcr_lineaire_segment(segment, provisions_techniques, primes_emises):
    """Terme linéaire d'un segment — art. 250 §1 et annexe XIX.

    Returns
    -------
    (float, str) : le terme, et la référence exacte à publier à côté.
    """
    coefficients = COEFF_MCR.get(segment)
    if coefficients is None:
        raise KeyError(
            "Segment MCR inconnu : %r. Segments connus : %s"
            % (segment, sorted(COEFF_MCR)))

    terme = (coefficients["alpha"] * max(0.0, float(provisions_techniques))
             + coefficients["beta"] * max(0.0, float(primes_emises)))
    reference = (
        "%s (lignes d'activite %s) — alpha %.1f%% sur provisions, beta %.1f%% "
        "sur primes, annexe XIX du RD (UE) 2015/35 appelee par l'art. 250"
        % (coefficients["libelle"], coefficients["lob"],
           coefficients["alpha"] * 100, coefficients["beta"] * 100))
    return terme, reference


def mcr_entite(mcr_lineaire_total, scr_consolide, amcr=AMCR_NON_VIE):
    """MCR au niveau ENTITÉ — art. 248 §1 et §2, art. 249.

    L'ordre est celui du Règlement : sommer les termes LINÉAIRES, appliquer le
    corridor sur le SCR, puis le plancher absolu **une seule fois**.

    Returns
    -------
    (float, str) : le MCR, et la contrainte qui a effectivement mordu — pour
                   qu'un lecteur sache si le chiffre vient du linéaire, du
                   corridor ou du plancher.
    """
    lineaire = max(0.0, float(mcr_lineaire_total))
    scr = max(0.0, float(scr_consolide))

    plancher_corridor = MCR_CORRIDOR_BAS * scr
    plafond_corridor = MCR_CORRIDOR_HAUT * scr
    combine = min(max(lineaire, plancher_corridor), plafond_corridor)

    if combine > lineaire:
        contrainte = "plancher du corridor (%.0f%% du SCR)" % (MCR_CORRIDOR_BAS * 100)
    elif combine < lineaire:
        contrainte = "plafond du corridor (%.0f%% du SCR)" % (MCR_CORRIDOR_HAUT * 100)
    else:
        contrainte = "formule lineaire"

    if combine < amcr:
        return float(amcr), (
            "plancher absolu AMCR, applique UNE SEULE FOIS au niveau entite "
            "(art. 248 par. 1) — valeur a confirmer sur la directive")
    return combine, contrainte


#: Un ratio de couverture qu'on ne peut pas calculer. Ce n'est ni 0 %, ni
#: 100 %, ni « on ne sait pas et on affiche quand même » : c'est l'absence.
RATIO_NON_CALCULABLE = None
MENTION_NON_CALCULABLE = (
    "NON CALCULABLE — fonds propres eligibles non fournis. Un ratio de "
    "couverture se lit dans un bilan prudentiel ; il ne s'estime pas a "
    "partir des primes ou du Best Estimate. Fournir `fonds_propres=` "
    "(fonds propres eligibles, QRT S.23.01) pour obtenir un ratio."
)


def ratio_couverture(fonds_propres, exigence, fonds_propres_estimes,
                     libelle="SCR"):
    """Rend `(ratio, publiable, mention)` — et REFUSE de publier une estimation.

    ⛔ LA DÉCISION D'ARBITRAGE A3, PRISE PAR LE COMMANDITAIRE LE 12/09/2026.
    Trois agents publiaient un ratio de couverture assis sur des fonds propres
    FABRIQUÉS, chacun par sa propre formule :

        S3       fpp = primes x 0,80               ->   379 652 EUR
        P4       fpp = max(estime ; primes x 2,00) ->   877 105 EUR
        SP-Coord fpp = max(... ; BE x 1,50)        -> 3 309 743 EUR

    Trois montants pour la MÊME entité, aucun signalé comme estimation. Le
    correctif du lot 9 les a rendus VISIBLES — c'était déjà beaucoup. La
    décision d'arbitrage va plus loin, et c'est la bonne : **on ne publie pas
    un ratio de solvabilité dont le numérateur est inventé.**

    Les fonds propres éligibles ne se calculent pas : ils se lisent dans un
    bilan prudentiel. Aucun coefficient ne peut les produire à partir des
    primes ou du Best Estimate — ce qui veut dire qu'aucune des trois formules
    n'était légitime, pas qu'il fallait choisir la meilleure.

    ⚠️ CE QUE CELA COÛTE, ET QUI A ÉTÉ ACCEPTÉ EN CONNAISSANCE DE CAUSE : le
    module ne rendra plus de ratio chez un prospect qui n'a pas encore son
    bilan Solvabilité 2 sous la main. C'est le prix d'un chiffre qu'on peut
    défendre devant un contrôleur.

    Returns
    -------
    (float|None, bool, str)
        Le ratio en pourcentage, `publiable`, et la mention à porter DANS le
        document. `ratio` vaut None quand il n'est pas publiable — jamais 0,
        qui se confondrait avec une insuffisance réelle.
    """
    if fonds_propres_estimes:
        return RATIO_NON_CALCULABLE, False, MENTION_NON_CALCULABLE

    try:
        fp = float(fonds_propres or 0.0)
        exig = float(exigence or 0.0)
    except (TypeError, ValueError):
        return RATIO_NON_CALCULABLE, False, MENTION_NON_CALCULABLE

    if exig <= 0:
        return (RATIO_NON_CALCULABLE, False,
                "NON CALCULABLE — %s nul ou absent : un ratio de couverture "
                "sans exigence au denominateur ne mesure rien." % libelle)

    return round(fp / exig * 100.0, 1), True, ""


def statut_sans_ratio(rag_calcule, ratio_publiable):
    """Le RAG quand le ratio n'est pas publiable.

    ⛔ Ni VERT ni ROUGE : **ROUGE**, et pour un motif explicite.
    Un module qui ne peut pas mesurer sa solvabilité ne doit pas sortir VERT —
    ce serait exactement le défaut « non mesuré = VERT ». Mais il ne doit pas
    non plus se taire : le motif dit que c'est l'ABSENCE DE DONNÉE qui rougit,
    et non une insuffisance de capital. La nuance décide de ce que le lecteur
    va faire.
    """
    if ratio_publiable:
        return rag_calcule, ""
    return "ROUGE", (
        "ROUGE par ABSENCE DE DONNEE, et non par insuffisance de capital : "
        "les fonds propres eligibles n'ont pas ete fournis, donc aucun ratio "
        "de couverture n'a pu etre calcule."
    )


def texte_ratio(ratio, suffixe=" %"):
    """Rend un ratio en texte, ou « NON CALCULABLE » quand il n'existe pas.

    ⚠️ POURQUOI UNE FONCTION POUR SI PEU. Les trois agents formatent leur ratio
    à une trentaine d'endroits — console, QRT, hypothèses, graphique, audit.
    Un `f"{ratio:.1f}%%"` sur `None` lève ; un repli à 0 à chacun de ces
    endroits rouvrirait le défaut, parce que 0 %% se lit comme une INSUFFISANCE
    DE CAPITAL et non comme une absence de mesure. Un seul endroit décide.
    """
    if ratio is None:
        return "NON CALCULABLE"
    return "%.1f%s" % (ratio, suffixe)


def ratio_atteint(ratio, seuil):
    """`ratio >= seuil`, mais FAUX quand le ratio n'existe pas.

    Un seuil non atteint parce qu'on n'a pas mesuré n'est pas un seuil
    franchi : les appelants doivent distinguer les deux, et c'est le rôle du
    couple `(ratio_atteint, publiable)`, jamais d'une comparaison nue.
    """
    return ratio is not None and ratio >= seuil
