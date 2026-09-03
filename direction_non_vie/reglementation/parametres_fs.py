# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — PARAMÈTRES DE LA FORMULE STANDARD (Solvabilité II)
=============================================================================

UNE SEULE COPIE, ET CHAQUE VALEUR PORTE SA PROVENANCE.

⚠️ POURQUOI CE MODULE EXISTE. Ces paramètres vivaient en DEUX exemplaires —
en dur dans `a8_stress_testing/agent.py`, et dans
`data/marche/reference_actuaria.json` — plus une TROISIÈME copie des bornes du
MCR chez A10, dont deux écrites en clair dans une expression. Les douze
valeurs concordaient à la dernière décimale au moment de la bascule, vérifié
paramètre par paramètre.

⚠️ MAIS CINQ D'ENTRE ELLES N'ÉTAIENT SURVEILLÉES PAR RIEN. Le filet
`test_a8_sigma_s2.py` ne recoupait que le bloc `scr_marche` — sept valeurs.
Les trois facteurs catastrophe et les deux paramètres du MCR étaient
dupliqués sans aucun contrôle. C'est exactement la configuration dans
laquelle `sigma_primes_rc_general` avait dérivé de 0,14 à 0,11 avant le lot
B10-c : deux copies, aucun gardien.

⚠️ LA PROVENANCE VIT DANS LA DONNÉE, JAMAIS DANS UN COMMENTAIRE. C'est la
leçon des lots B10-a et B10-b : avant eux, TOUTES les valeurs fausses étaient
commentées « Annexe II », et certaines citaient un segment qui n'existe pas.
Un commentaire ne se vérifie pas ; un champ, si — et le champ `source`
ci-dessous distingue ce qui a été LU dans le texte de ce qui ne l'a pas été.

⚠️ ET IL DISTINGUE HONNÊTEMENT, PARCE QUE J'AI DÉJÀ FAIT L'ERREUR INVERSE. Au
lot B10-d j'avais écrit deux chocs de taux « du texte » — 48 % et 38 % — qui
ne figurent à AUCUNE échéance des tables. Le lot B10-e les a corrigés en
relisant. Ici, sept valeurs ont été relues dans le règlement délégué et cinq
ne s'y trouvent pas : elles sont marquées comme telles plutôt que parées d'un
article plausible.

RÉFÉRENCES
  Règlement délégué (UE) 2015/35, texte consolidé au 02.08.2022 —
  CELEX 02015R0035-20220802.
  Directive 2009/138/CE, art. 129 (minimum de capital requis) — AUTRE
  DOCUMENT, non relu ici.
=============================================================================
"""

from typing import Dict, NamedTuple

#: Vocabulaire contrôlé du champ `source` : c'est ce qui empêche de parer une
#: approximation d'une référence d'article inventée.
#:
#: ⚠️⚠️ CE COMMENTAIRE AFFIRMAIT « Un test verrouille qu'aucune autre valeur ne
#: s'y glisse ». **C'ÉTAIT FAUX, et mesuré le 03/09/2026** : aucun test
#: n'importait ce module ni ne citait `PARAMETRES_FS`, `SOURCES_ADMISES`
#: n'apparaissait qu'à sa propre définition, et
#: `ParametreFS(0.42, 'ANNEXE_II_INVENTEE', 'art. 999', ...)` se construisait
#: **sans la moindre erreur**.
#:
#:   *Une contrainte écrite dans un commentaire n'est pas une contrainte ;
#:   c'est une intention.*
#:
#: ⚠️ ET C'EST EXACTEMENT LE RISQUE QUE CE MODULE EXISTE POUR EMPÊCHER. Son
#: en-tête raconte les lots B10-a et B10-b : *« TOUTES les valeurs fausses
#: étaient commentées Annexe II, et certaines citaient un segment qui n'existe
#: pas. »* Le garde-fou censé fermer ça n'existait pas.
#:
#: La contrainte est désormais APPLIQUÉE par `_parametre()`, seule porte
#: d'entrée de la table, et un test l'épingle pour de bon.
SOURCE_DELEGUE = 'REGLEMENT_DELEGUE'      # relu dans le texte consolidé
SOURCE_DIRECTIVE = 'DIRECTIVE_2009_138'   # autre document, NON relu ici
SOURCE_APPROXIMATION = 'APPROXIMATION'    # pas une valeur du texte

SOURCES_ADMISES = (SOURCE_DELEGUE, SOURCE_DIRECTIVE, SOURCE_APPROXIMATION)


class ParametreFS(NamedTuple):
    """Un paramètre de la formule standard, avec de quoi le justifier.

    `source` dit d'où la valeur vient, et `reference` où la retrouver. Les
    deux sont des DONNÉES : un contrôleur qui demande « d'où sort ce 39 % ? »
    obtient la réponse depuis le livrable, pas depuis un commentaire de code.
    """
    valeur:    float
    source:    str    # l'un de SOURCES_ADMISES
    reference: str    # 'art. 169 par. 1 c)', ou ce qui en tient lieu
    libelle:   str


def _parametre(valeur: float, source: str, reference: str,
               libelle: str) -> ParametreFS:
    """Seule porte d'entrée de `PARAMETRES_FS`, et elle REFUSE.

    ⚠️ La porte existe parce que le champ `source` ne se vérifie pas tout
    seul : `ParametreFS` est un `NamedTuple`, il accepte n'importe quelle
    chaîne. Une source inventée — « ANNEXE_II », « art. 999 » — se serait
    installée dans la table sans que rien ne bronche, et un livrable
    l'aurait citée à un contrôleur.

    ⚠️ ELLE LÈVE PLUTÔT QUE DE CORRIGER. Substituer `APPROXIMATION` à une
    source inconnue reviendrait à décider à la place de celui qui écrit la
    valeur : c'est à lui de dire s'il a LU l'article ou s'il l'approxime.
    """
    if source not in SOURCES_ADMISES:
        raise ValueError(
            f"Source de paramètre non admise : « {source} » "
            f"(paramètre « {libelle} », référence « {reference} »). "
            f"Le vocabulaire contrôlé est {', '.join(SOURCES_ADMISES)}. "
            f"Une valeur qui ne vient pas du règlement délégué se marque "
            f"« {SOURCE_APPROXIMATION} » ou « {SOURCE_DIRECTIVE} » — elle "
            f"ne se pare pas d'une référence d'article.")
    return ParametreFS(valeur, source, reference, libelle)


PARAMETRES_FS: Dict[str, ParametreFS] = {

    # ── Module « risque de marché » ──────────────────────────────────────────
    # RELU LE 2026-08-06 dans le texte consolidé, article par article.
    'choc_taux_hausse_10ans_relatif': _parametre(
        0.42, SOURCE_DELEGUE, 'art. 166 par. 1 (échéance 10 ans)',
        "Choc de hausse des taux — facteur RELATIF au taux sans risque"),
    'choc_taux_baisse_10ans_relatif': _parametre(
        -0.31, SOURCE_DELEGUE, 'art. 167 par. 1 (échéance 10 ans)',
        "Choc de baisse des taux — facteur RELATIF au taux sans risque"),
    'choc_actions_type1': _parametre(
        0.39, SOURCE_DELEGUE, 'art. 169 par. 1 point c)',
        "Actions de type 1 — hors ajustement symétrique de l'art. 172"),
    'choc_actions_type2': _parametre(
        0.49, SOURCE_DELEGUE, 'art. 169 par. 2 point c)',
        "Actions de type 2 — hors ajustement symétrique de l'art. 172"),
    'choc_immobilier': _parametre(
        0.25, SOURCE_DELEGUE, 'art. 174',
        "Diminution soudaine de la valeur des actifs immobiliers"),
    'choc_devise': _parametre(
        0.25, SOURCE_DELEGUE, 'art. 188 par. 3 et 4',
        "Variation soudaine de la valeur d'une monnaie étrangère"),
    'choc_spread_IG': _parametre(
        0.009, SOURCE_DELEGUE,
        'art. 176 par. 3, tableau — échelon 0, duration <= 5 ans',
        "Facteur b_i du spread. ⚠️ LE TEXTE DONNE UNE MATRICE échelon de "
        "qualité de crédit x duration ; cette valeur en est UNE CELLULE, "
        "celle du meilleur échelon a duration courte. L'employer seule est "
        "une simplification, et elle est PRUDENTE dans le mauvais sens : "
        "tous les autres echelons portent un facteur PLUS ELEVE."),

    # ── Module « catastrophe » ───────────────────────────────────────────────
    # ⚠️ AUCUNE DE CES TROIS VALEURS N'EST DANS LE TEXTE. L'art. 121 calibre
    # le risque catastrophe sur les SOMMES ASSURÉES PAR RÉGION (annexe VII et
    # suivantes), donnée que le dépôt n'a pas. Ce sont des facteurs de
    # substitution appliqués au volume — utiles, mais ils ne se justifient pas
    # par un article, et ce module ne prétendra pas le contraire.
    'facteur_catastrophe_vent': _parametre(
        0.10, SOURCE_APPROXIMATION,
        "art. 121 non applicable — sommes assurées par région indisponibles",
        "Facteur de substitution — tempête"),
    'facteur_catastrophe_grele': _parametre(
        0.03, SOURCE_APPROXIMATION,
        "art. 121 non applicable — sommes assurées par région indisponibles",
        "Facteur de substitution — grêle"),
    'facteur_catastrophe_inondation': _parametre(
        0.04, SOURCE_APPROXIMATION,
        "art. 121 non applicable — sommes assurées par région indisponibles",
        "Facteur de substitution — inondation"),

    # ── Minimum de capital requis ────────────────────────────────────────────
    # ⚠️ CES CINQ VALEURS NE SONT PAS DANS LE RÈGLEMENT DÉLÉGUÉ. Cherchées
    # dans le texte consolidé : `0,0418` et `0,0261` y sont INTROUVABLES, et
    # le « 45 % » qu'on y trouve concerne le risque d'inondation, pas le MCR.
    # Le corridor et le plancher absolu relèvent de la DIRECTIVE 2009/138/CE
    # art. 129, qui est un autre document — non relu ici. Elles sont donc
    # marquées `DIRECTIVE`, et non parées d'un article du délégué.
    'mcr_pct_scr_min': _parametre(
        0.25, SOURCE_DIRECTIVE, 'Directive 2009/138/CE, art. 129 par. 3',
        "Plancher du MCR, en part du SCR"),
    'mcr_pct_scr_max': _parametre(
        0.45, SOURCE_DIRECTIVE, 'Directive 2009/138/CE, art. 129 par. 3',
        "Plafond du MCR, en part du SCR"),
    'mcr_seuil_absolu_non_vie': _parametre(
        2_500_000.0, SOURCE_DIRECTIVE,
        'Directive 2009/138/CE, art. 129 par. 1 point d)',
        "Plancher absolu du MCR — engagements non-vie, en euros"),
    'mcr_alpha_primes': _parametre(
        0.0418, SOURCE_DIRECTIVE, 'Directive 2009/138/CE, art. 129 par. 1',
        "Coefficient du MCR linéaire appliqué aux primes"),
    'mcr_beta_provisions': _parametre(
        0.0261, SOURCE_DIRECTIVE, 'Directive 2009/138/CE, art. 129 par. 1',
        "Coefficient du MCR linéaire appliqué aux provisions"),
}


def valeur(cle: str) -> float:
    """La valeur d'un paramètre. Lève sur une clé inconnue, plutôt que de
    rendre un défaut : un paramètre absent est une erreur, pas un zéro."""
    if cle not in PARAMETRES_FS:
        raise KeyError(
            f"Paramètre de formule standard inconnu : « {cle} ». "
            f"Les {len(PARAMETRES_FS)} clés disponibles sont "
            f"{', '.join(sorted(PARAMETRES_FS))}.")
    return PARAMETRES_FS[cle].valeur


def libelle_reference(cle: str) -> str:
    """Ce qu'il faut CITER dans un livrable, provenance comprise.

    ⚠️ LE DERNIER CAS N'EST PAS UN DÉFAUT DE REPLI. Il l'était : la fonction
    finissait par `return f"Approximation — ..."`, ce qui AFFIRMAIT
    « approximation » de toute source qu'elle ne connaissait pas. Élargir
    `SOURCES_ADMISES` sans revenir ici aurait donc fait citer, dans un
    livrable réglementaire, une provenance que personne n'avait décidée.
    Chaque source admise est désormais traitée NOMMÉMENT, et l'inconnue
    lève — comme `valeur()` lève sur une clé inconnue plutôt que de rendre
    un zéro.
    """
    p = PARAMETRES_FS[cle]
    if p.source == SOURCE_DELEGUE:
        return f"Règlement délégué (UE) 2015/35, {p.reference}"
    if p.source == SOURCE_DIRECTIVE:
        return p.reference
    if p.source == SOURCE_APPROXIMATION:
        return f"Approximation — {p.reference}"
    raise ValueError(
        f"Le paramètre « {cle} » porte la source « {p.source} », que "
        f"`libelle_reference` ne sait pas citer. Une source ajoutée à "
        f"SOURCES_ADMISES doit recevoir ici sa formulation : sans quoi elle "
        f"serait publiée comme une approximation sans que personne "
        f"l'ait décidé.")


def parametres_non_textuels() -> Dict[str, ParametreFS]:
    """Les paramètres qui NE SONT PAS des valeurs du règlement délégué.

    Existe pour qu'un livrable puisse les nommer plutôt que de les noyer :
    c'est une proportion qu'un actuaire qui signe a le droit de connaître.
    `phrase_provenance()` la DÉRIVE — cette docstring ne la chiffre pas.
    """
    return {c: p for c, p in PARAMETRES_FS.items()
            if p.source != SOURCE_DELEGUE}


def phrase_provenance() -> str:
    """La provenance des paramètres, comptée sur la table elle-même.

    ⚠️ ELLE SE DÉRIVE, ELLE NE S'ÉCRIT PAS. La docstring de
    `parametres_non_textuels` annonçait « HUIT SUR QUINZE » en toutes
    lettres. Le compte était exact au moment où il a été écrit — mais rien
    ne le rattachait à la table : ajouter un paramètre l'aurait rendu faux
    en silence, dans un texte destiné à un livrable réglementaire.
    """
    total = len(PARAMETRES_FS)
    directive = sum(1 for p in PARAMETRES_FS.values()
                    if p.source == SOURCE_DIRECTIVE)
    approx = sum(1 for p in PARAMETRES_FS.values()
                 if p.source == SOURCE_APPROXIMATION)
    hors = directive + approx
    if not hors:
        return (f"Les {total} paramètres de la formule standard ont tous été "
                f"relus dans le règlement délégué (UE) 2015/35.")
    morceaux = []
    if directive:
        morceaux.append(f"{directive} de la directive 2009/138/CE, qui est un "
                        f"autre document, non relu ici")
    if approx:
        morceaux.append(f"{approx} sont des approximations assumées, sans "
                        f"article qui les fonde")
    return (f"Sur les {total} paramètres de la formule standard, {hors} ne "
            f"viennent pas du texte relu : " + " ; ".join(morceaux) + ".")
