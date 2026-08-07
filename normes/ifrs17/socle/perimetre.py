# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : LE PÉRIMÈTRE PUBLIÉ, ET SURTOUT CE QU'IL EXCLUT
=============================================================================

CE QU'UN ACTUAIRE QUI SIGNE ET UN COMMISSAIRE QUI LIT REGARDENT EN PREMIER,
c'est ce que la plateforme NE fait pas. Un périmètre écrit et assumé est
défendable ; une liste d'exigences ouvertes ne l'est pas.

⚠️ TROIS ÉTATS, ET NON DEUX. Confondre « hors périmètre » et « pas encore
construit » tromperait dans les deux sens : présenter un chantier en cours
comme une exclusion délibérée, ou laisser croire qu'une exclusion assumée
sera comblée. Chacun porte sa RAISON, et elle est obligatoire.

⚠️ LES ÉLÉMENTS « COUVERT » SONT VÉRIFIÉS CONTRE `contrat.EXIGENCES`. Le
périmètre ne peut pas revendiquer plus que le socle ne nomme : un test
l'interdit. Sans ce verrou, la promesse commerciale dériverait du code —
et c'est le sens même de ce module d'empêcher cela.

⚠️ CE QUE LA PLATEFORME NE VÉRIFIE PAS, ET QUI N'ÉTAIT PAS DANS MA LISTE.
Relevé sur le texte : IFRS 17 porte QUATRE choix obligatoires (§7, §8A, §88,
§89) et SEPT options (§8, §21, §59 a), §69, B6, B115, B137). La plateforme en
tranche plusieurs implicitement, et le plus lourd est en amont de tout :
elle ne teste JAMAIS si ce qu'on lui remet entre dans le champ d'IFRS 17
(§3, §7, §8, §8A, appendice A, B2-B30). Elle prend l'inventaire pour ce
qu'il dit être. C'est défendable — un assureur connaît ses contrats — mais
cela se DÉCLARE, parce qu'un contrôleur le demandera.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023. Chaque paragraphe cité ci-dessous a été relu dans ce texte.
=============================================================================
"""

from typing import Dict, Iterable, Mapping, NamedTuple, Tuple

#: Le socle le fait, et `contrat.EXIGENCES` le nomme.
COUVERT = 'COUVERT'
#: Décision assumée : la plateforme ne le fera pas, et dit pourquoi.
HORS_PERIMETRE = 'HORS_PERIMETRE'
#: Prévu, pas encore fait. ⚠️ N'est PAS une exclusion.
NON_CONSTRUIT = 'NON_CONSTRUIT'

ETATS = (COUVERT, HORS_PERIMETRE, NON_CONSTRUIT)


class Element(NamedTuple):
    """Un pan de la norme, et ce que la plateforme en fait.

    `raison` est obligatoire hors du cas COUVERT : une exclusion sans motif
    est une omission déguisée.
    """
    reference: str
    etat:      str
    libelle:   str
    raison:    str = ''


PERIMETRE: Tuple[Element, ...] = (

    # ── Ce que le socle fait ────────────────────────────────────────────────
    Element('§14, §16, §22, §25', COUVERT,
            "Unité de compte : portefeuilles, classes de profitabilité, "
            "cohortes annuelles, date de comptabilisation initiale"),
    Element('§17', COUVERT,
            "Évaluation d'un ensemble de contrats plutôt que contrat "
            "par contrat"),
    Element('§18', COUVERT,
            "Présomption de non-déficit en PAA, faute de critère déclaré"),
    Element('§53', COUVERT,
            "Test d'éligibilité à la méthode d'affectation des primes"),
    Element('§36 a), B79', COUVERT,
            "Courbe d'actualisation dans la monnaie des flux"),
    Element('§78', COUVERT,
            "Un jeu d'états par entité juridique"),

    # ── Hors périmètre, par décision assumée ────────────────────────────────
    Element('§3, §7, §8, §8A, appendice A, B2-B30', HORS_PERIMETRE,
            "Test du champ d'application : la plateforme ne vérifie pas "
            "qu'un contrat qu'on lui remet EST un contrat d'assurance",
            "Le §7 exclut lui-même garanties de biens, avantages du "
            "personnel et droits d'usage ; le §8A impose de choisir entre "
            "IFRS 17 et IFRS 9 pour certains contrats. Ces qualifications "
            "relèvent de l'entité, qui connaît ses contrats. La plateforme "
            "prend l'inventaire pour ce qu'il déclare être, et le dit."),
    Element('§8, B6', HORS_PERIMETRE,
            "Option d'appliquer IFRS 15 aux contrats de services à tarif "
            "forfaitaire",
            "Choix contractuel de l'entité, exercé en amont de toute "
            "évaluation. Un contrat remis à la plateforme est traité selon "
            "IFRS 17."),
    Element('§32-52', HORS_PERIMETRE,
            "Modèle général (BBA) et marge sur services contractuels",
            "La plateforme mesure en PAA. Les groupes qui échouent au test "
            "du §53 sont SIGNALÉS et non évalués — jamais mesurés à tort "
            "sous une méthode qui ne leur convient pas."),
    Element('§45, §71, B101-B118', HORS_PERIMETRE,
            "Contrats avec éléments de participation directe (VFA) et "
            "contrats d'investissement avec participation discrétionnaire",
            "Le §71 pose qu'un contrat d'investissement avec participation "
            "discrétionnaire « n'a pas pour effet de transférer un risque "
            "d'assurance important » : ces contrats relèvent de la vie, non "
            "du périmètre non-vie de cette version. L'option de "
            "l'atténuation du risque (B115-B116) tombe avec eux."),
    Element('§72-77', HORS_PERIMETRE,
            "Modification et décomptabilisation de contrats",
            "Événements de gestion de contrat, non calculs de clôture : "
            "leur place est le système de gestion de l'entité."),
    Element('§88-89', HORS_PERIMETRE,
            "Option de ventiler les produits et charges financiers entre "
            "résultat net et autres éléments du résultat global (OCI)",
            "Le §88 impose de CHOISIR l'une des deux méthodes. La "
            "plateforme retient la première : l'intégralité en résultat "
            "net. ⚠️ C'est une MÉTHODE COMPTABLE et elle se déclare en "
            "annexe aux états financiers, non seulement ici."),
    Element('B72 b) à e), B73', HORS_PERIMETRE,
            "Révision du taux d'actualisation initial d'un groupe quand des "
            "contrats y entrent, et magasin de courbes indexé par date",
            "Mesuré : le B72 énumère cinq usages du taux verrouillé. Deux "
            "visent la marge sur services contractuels, ABSENTE en PAA ; un "
            "vise l'option OCI, exclue ci-dessus ; un vise les taux "
            "COURANTS, donc sans objet. Reste le §56 seul — qui s'exempte "
            "lui-même quand le délai entre service et échéance de prime "
            "n'excède pas un an, c'est-à-dire le contrat annuel — et les "
            "cas pluriannuels qui le déclencheraient échouent au §53 b). "
            "Construire un magasin de courbes historiques pour servir un "
            "usage que le périmètre exclut serait disproportionné."),
    Element('annexe C', HORS_PERIMETRE,
            "Dispositions transitoires (rétrospective, rétrospective "
            "modifiée, juste valeur)",
            "IFRS 17 s'applique depuis le 1er janvier 2023 : la plateforme "
            "s'adresse à des entités ayant achevé leur transition. Réserve "
            "assumée — un premier adoptant, entité nouvelle ou passant aux "
            "IFRS aujourd'hui, sort de ce périmètre."),

    # ── Signalé par contrôle, non évalué ────────────────────────────────────
    Element('§10-13', HORS_PERIMETRE,
            "Séparation des composantes d'un contrat d'assurance",
            "Rare en non-vie. Non évaluée, mais SIGNALÉE par contrôle "
            "lorsque l'inventaire la déclare — voir `signaler`."),
    Element('§85', HORS_PERIMETRE,
            "Exclusion des composantes d'investissement des produits des "
            "activités d'assurance",
            "Rare en non-vie. Non évaluée, mais SIGNALÉE par contrôle "
            "lorsque l'inventaire la déclare — voir `signaler`."),

    # ── Prévu, pas encore construit ─────────────────────────────────────────
    Element('§55-59, B125-B126', NON_CONSTRUIT,
            "Évaluation PAA : LRC, élément de perte, revenu, charges",
            "Le socle constitue les groupes et les scelle ; la mesure "
            "elle-même reste à bâtir."),
    Element('§60-70A', NON_CONSTRUIT,
            "Réassurance détenue",
            "Régime propre — agrégation adaptée (§61), PAA sous conditions "
            "distinctes (§69), composante recouvrement de perte (§66B, "
            "§70A). Dans le périmètre, non encore bâti."),
    Element('§78-92', NON_CONSTRUIT,
            "Présentation au bilan et au compte de résultat",
            "Le §80 impose de ventiler le résultat en DEUX postes ; aucun "
            "n'est encore produit."),
    Element('§93-132', NON_CONSTRUIT,
            "Informations à fournir, dont le développement des sinistres "
            "(§130) et l'analyse de sensibilité (§128-129)",
            "Le §119, niveau de confiance de l'ajustement pour risque, est "
            "le seul déjà tenu — hors de ce socle, dans l'agent A11."),
    Element('§21', NON_CONSTRUIT,
            "Subdivision des groupes au-delà de §16",
            "Le champ `groupe_declare` de l'inventaire la permet ; elle "
            "n'est pas encore exploitée par la dérivation."),
    Element('§28, B73', NON_CONSTRUIT,
            "Entrée de contrats dans un groupe existant",
            "L'appartenance est construite ; la révision du taux qu'elle "
            "entraîne est hors périmètre — voir B72 ci-dessus."),
)


# =============================================================================
#  LES CONTRÔLES DE NON-APPLICABILITÉ
# =============================================================================

#: Champ de l'inventaire → (référence, ce que le contrôle dit).
#: ⚠️ Ces drapeaux ont été posés en D1 pour ce moment précis : reconnaître ce
#: qu'on ne traite pas plutôt que de le mesurer en silence.
CONTROLES: Dict[str, Tuple[str, str]] = {
    'participation_directe': (
        '§45, B101-B118',
        "contrat(s) déclaré(s) avec éléments de participation directe : "
        "la méthode de la commission variable est HORS PÉRIMÈTRE. Ces "
        "contrats ne doivent pas être mesurés par cette plateforme."),
    'composante_investissement': (
        '§85',
        "contrat(s) déclaré(s) avec une composante d'investissement : elle "
        "doit être exclue des produits des activités d'assurance, ce que "
        "cette plateforme ne fait pas. Traiter ces contrats à part."),
}


class Alerte(NamedTuple):
    """Un cas hors périmètre rencontré dans un inventaire réel."""
    champ:     str
    reference: str
    nb_lignes: int
    message:   str


def signaler(lignes: Iterable[Mapping]) -> Tuple[Alerte, ...]:
    """Les cas hors périmètre présents dans un inventaire.

    ⚠️ SIGNALE, NE REFUSE PAS. Un inventaire peut légitimement contenir des
    contrats que cette plateforme ne mesure pas ; ce qui serait fautif, c'est
    de les mesurer quand même. L'alerte nomme le paragraphe et dit quoi faire.
    """
    compte: Dict[str, int] = {}
    for ligne in lignes:
        for champ in CONTROLES:
            if _est_vrai(ligne.get(champ)):
                compte[champ] = compte.get(champ, 0) + 1
    return tuple(
        Alerte(champ, CONTROLES[champ][0], n,
               f"{n} {CONTROLES[champ][1]}")
        for champ, n in sorted(compte.items()))


def _est_vrai(valeur) -> bool:
    """Un drapeau posé, quelle que soit la façon dont le client l'écrit."""
    if valeur is None:
        return False
    if isinstance(valeur, bool):
        return valeur
    return str(valeur).strip().lower() in (
        'oui', 'o', 'yes', 'y', 'true', 'vrai', '1', 'x')


# =============================================================================
#  LE PÉRIMÈTRE PUBLIÉ
# =============================================================================

def elements(etat: str) -> Tuple[Element, ...]:
    """Les éléments d'un état donné. Lève sur un état inconnu."""
    if etat not in ETATS:
        raise KeyError(
            f"État inconnu : « {etat} ». Les états sont {', '.join(ETATS)}.")
    return tuple(e for e in PERIMETRE if e.etat == etat)


def mention_directions(directions: Iterable[str]) -> str:
    """La mention à porter sur des états produits pour un abonnement partiel.

    ⚠️ UN JEU PARTIEL PRIS POUR UN JEU COMPLET EST CE QU'UN COMMISSAIRE
    RELÈVE. L'accès filtré au bord est une décision produit légitime ; la
    taire sur le livrable ne le serait pas.
    """
    d = sorted(set(directions))
    if not d:
        raise ValueError(
            "Aucune direction : des états financiers portent toujours sur "
            "un périmètre, fût-il unique.")
    if len(d) == 1:
        return (f"États financiers IFRS 17 limités aux groupes de la "
                f"direction {d[0]} — périmètre partiel.")
    return (f"États financiers IFRS 17 portant sur les directions "
            f"{', '.join(d)} — périmètre partiel.")


def texte() -> str:
    """Le périmètre publié, tel qu'il se remet à un actuaire ou à un CAC."""
    lignes = [
        "PÉRIMÈTRE IFRS 17 — ASSURANCE NON-VIE",
        "",
        "La plateforme couvre l'évaluation, la présentation et la clôture",
        "IFRS 17 en non-vie selon la MÉTHODE D'AFFECTATION DES PRIMES",
        "(§53-59), pour les contrats d'assurance émis et les contrats de",
        "réassurance détenus (§60-70A). Elle constitue l'unité de compte",
        "réglementaire à partir d'un inventaire de contrats fourni par",
        "l'entité, et conserve les clôtures successives.",
        "",
    ]
    for etat, titre in (
            (COUVERT, "CE QUI EST COUVERT"),
            (NON_CONSTRUIT, "DANS LE PÉRIMÈTRE, PAS ENCORE CONSTRUIT"),
            (HORS_PERIMETRE, "HORS PÉRIMÈTRE — DÉCISIONS ASSUMÉES")):
        groupe = elements(etat)
        lignes.append(f"{titre} ({len(groupe)})")
        for e in groupe:
            lignes.append(f"  {e.reference} — {e.libelle}")
            if e.raison:
                lignes.append(f"      {e.raison}")
        lignes.append("")
    lignes.append(
        "Les contrats relevant d'un pan hors périmètre sont SIGNALÉS par")
    lignes.append(
        "contrôle lorsque l'inventaire les déclare — ils ne sont jamais")
    lignes.append("mesurés à tort.")
    return '\n'.join(lignes)
