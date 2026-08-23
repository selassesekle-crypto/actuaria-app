"""
core/elasticite.py — CE QUE LA DÉCLARATION DE COMPORTEMENT REND ATTEIGNABLE.

⚠️ LE MODULE CONSTATE, IL NE DEMANDE PAS. Une question posée à l'exécution
(« avez-vous des données d'élasticité ? ») invite une réponse fausse : un
utilisateur répond « oui » et fournit un fichier inutilisable. L'actuaire
DÉCLARE dans le plan signé, et le système VÉRIFIE ce que cette déclaration
ouvre. C'est le patron du socle IFRS 17.

⚠️⚠️ CE FICHIER EST LA TROISIÈME INSTANCE DU MÊME MÉCANISME, ET C'EST DIT
PLUTÔT QUE TU. Le dépôt en porte déjà deux :

  · `direction_non_vie/services/nv_triangle_mapping.py::_capacites_depuis_champs`
    — la forme booléenne ;
  · `normes/ifrs17/socle/contrat.py` — la forme étendue au catalogue nommé,
    qui se décrit elle-même comme « le pendant de `_capacites_depuis_champs`
    de la couche triangle ».

Ce fichier reprend la seconde. L'extraction du mécanisme commun est un
chantier à part : elle toucherait `normes/`, une autre zone et une autre gate.

⚠️⚠️ AUCUNE EXIGENCE ICI NE VIENT D'UNE NORME, et le champ `source` l'oblige à
se dire. C'est la différence avec le socle IFRS 17, dont les exigences citent
des paragraphes relus dans le texte officiel : **aucun texte réglementaire ne
fixe une élasticité-prix ni une méthode pour l'estimer**. Tout ce qui suit est
une convention du module, opposable comme telle et pas davantage.
"""
from __future__ import annotations

from typing import NamedTuple

#: ⚠️ LE VOCABULAIRE DES SOURCES, REPRIS DU SOCLE — il existe pour empêcher
#: qu'une règle maison passe silencieusement pour une obligation. Ici il n'a
#: qu'une valeur, et c'est l'information : rien n'est normatif.
SOURCE_CONVENTION = 'CONVENTION_MODULE'
SOURCES_ADMISES = (SOURCE_CONVENTION,)


class Exigence(NamedTuple):
    """Une capacité que le module peut ou non atteindre, et à quel prix.

    `requiert` est une conjonction de disjonctions : chaque élément est un
    groupe de rôles dont AU MOINS UN doit être déclaré, et TOUS les groupes
    doivent être satisfaits. Même forme que le socle IFRS 17.
    """
    reference: str      # d'où vient la règle, telle qu'elle se cite
    source:    str      # l'un de SOURCES_ADMISES
    libelle:   str
    requiert:  tuple[frozenset[str], ...]


def _et(*groupes: tuple[str, ...]) -> tuple[frozenset[str], ...]:
    """Conjonction de groupes ; dans un groupe, un rôle suffit."""
    return tuple(frozenset(g) for g in groupes)


#: Ce que chaque capacité exige du bloc `comportement` du plan.
#:
#: ⚠️ LES RÔLES, PAS LES NOMS DE COLONNES. Le catalogue raisonne sur « une
#: prime précédente est-elle déclarée ? », jamais sur « la colonne s'appelle-
#: t-elle prime_n_1 ? » — c'est `Comportement.champs_declares()` qui traduit.
EXIGENCES: dict[str, Exigence] = {
    'variation_de_prix_observable': Exigence(
        'conception L2', SOURCE_CONVENTION,
        "Observer la VARIATION de prix subie à l'échéance. Une élasticité "
        "répond à une variation, jamais à un niveau : deux prix sont "
        "nécessaires, celui d'avant et celui qui a été proposé",
        _et(('prime_precedente',), ('prime_proposee',))),

    'elasticite_estimable': Exigence(
        'conception L2', SOURCE_CONVENTION,
        "Estimer une élasticité-prix : relier la décision de renouvellement "
        "à la variation de prix qui l'a précédée",
        _et(('issue',), ('prime_precedente',), ('prime_proposee',))),

    'identification_experimentale': Exigence(
        'conception L2', SOURCE_CONVENTION,
        "Identifier l'effet-prix SANS hypothèse d'exogénéité : un test de "
        "prix au renouvellement (remise ou hausse tirée au sort) est la "
        "seule source de variation dont l'indépendance au risque ne se "
        "discute pas. Sans lui, l'estimation repose sur une variation "
        "résiduelle dont l'exogénéité se mesure mais ne se démontre pas",
        _et(('issue',), ('prime_precedente',), ('prime_proposee',),
            ('groupe_test',))),

    'elasticite_par_canal': Exigence(
        'conception L2', SOURCE_CONVENTION,
        "Distinguer l'élasticité par canal de distribution. Elle varie d'un "
        "facteur plusieurs entre courtage, direct et comparateur : une "
        "estimation globale mélange des populations qui ne réagissent pas au "
        "même prix",
        _et(('issue',), ('prime_precedente',), ('prime_proposee',),
            ('canal',))),
}


def capacites(roles_declares) -> dict[str, bool]:
    """Exigence par exigence : atteignable ou non, depuis les rôles déclarés.

    Les rôles inconnus sont ignorés en silence — un plan a le droit de
    déclarer des choses qui ne nous concernent pas.
    """
    presents = set(roles_declares)
    return {nom: all(bool(groupe & presents) for groupe in ex.requiert)
            for nom, ex in EXIGENCES.items()}


def exigences_hors_portee(roles_declares) -> dict[str, tuple[str, ...]]:
    """Ce qui reste inatteignable, et LE RÔLE QUI MANQUE pour chacune.

    ⚠️ EXISTE POUR QUE LE DIAGNOSTIC DISE LE COÛT D'UNE ABSENCE PLUTÔT QUE DE
    LA TAIRE. « Pas d'élasticité » ne veut rien dire pour un actuaire ; « sans
    l'issue du contrat, l'estimation et l'optimisation tarifaire sont hors de
    portée » se comprend et se fournit. Reprise mot pour mot de l'intention du
    socle IFRS 17.
    """
    presents = set(roles_declares)
    manquantes: dict[str, tuple[str, ...]] = {}
    for nom, ex in EXIGENCES.items():
        absents = tuple(sorted(
            r for groupe in ex.requiert if not (groupe & presents)
            for r in groupe))
        if absents:
            manquantes[nom] = absents
    return manquantes


def roles_du_plan(plan) -> frozenset[str]:
    """Les rôles que le plan déclare — vide si aucun bloc `comportement`."""
    bloc = getattr(plan, 'comportement', None) if plan is not None else None
    return bloc.champs_declares() if bloc is not None else frozenset()


def diagnostic(plan) -> str:
    """La mise en mots. Rien n'y est calculé qui ne soit dans le catalogue.

    ⚠️ MÊME CONTRAT QUE LE SOCLE : le diagnostic ne décide de rien, il dit ce
    que `capacites()` et `exigences_hors_portee()` ont établi. Un diagnostic
    qui calculerait pour son compte pourrait diverger de ce que le module fait
    réellement — et c'est précisément le défaut que cet audit poursuit.
    """
    roles = roles_du_plan(plan)
    caps = capacites(roles)
    hors = exigences_hors_portee(roles)
    lignes: list[str] = []
    a = lignes.append

    a("ÉLASTICITÉ-PRIX — CE QUE LA DÉCLARATION DU PLAN REND ATTEIGNABLE")
    a("")
    if roles:
        a(f"Rôles déclarés au bloc `comportement` ({len(roles)}) : "
          f"{', '.join(sorted(roles))}")
    else:
        a("Aucun bloc `comportement` déclaré au plan.")

    possibles = sorted(n for n, ok in caps.items() if ok)
    a("")
    a(f"CE QUE JE PEUX PRODUIRE ({len(possibles)} sur {len(EXIGENCES)})")
    if possibles:
        for n in possibles:
            a(f"  OK  {EXIGENCES[n].libelle}")
    else:
        a("  — rien : aucune capacité n'est atteignable en l'état.")

    if hors:
        a("")
        a(f"CE QUI MANQUE, ET CE QUE CELA COÛTE ({len(hors)})")
        par_role: dict[str, list[str]] = {}
        for nom, absents in hors.items():
            par_role.setdefault(' ou '.join(absents), []).append(nom)
        for role, noms in sorted(par_role.items()):
            a(f"  Sans « {role} » :")
            for n in sorted(noms):
                a(f"      {EXIGENCES[n].libelle}")

    a("")
    a("⚠️ AUCUNE de ces exigences ne vient d'un texte réglementaire : aucune "
      "norme ne fixe une élasticité-prix ni une méthode pour l'estimer. "
      "Ce sont des conventions du module.")
    return "\n".join(lignes)


# ══════════════════════════════════════════════════════════════════════════════
#  L'ÉTAT PUBLIÉ — jamais une valeur inventée
# ══════════════════════════════════════════════════════════════════════════════

#: Les états de l'élasticité. Les trois premiers décrivent l'issue d'une
#: TENTATIVE D'ESTIMATION ; le quatrième dit que la tentative n'est pas encore
#: constructible.
#:
#: ⚠️⚠️ `NON_EXPLOITEE` EST UN AJOUT, ET C'EST UNE CONTESTATION ASSUMÉE DU
#: MODÈLE À TROIS ÉTATS. Sans lui, un plan qui déclare correctement son bloc
#: `comportement` retomberait sur `NON_FOURNIE` — ce qui serait FAUX, la
#: donnée étant fournie — ou sur `NON_IDENTIFIABLE`, ce qui serait pire :
#: cela imputerait au PORTEFEUILLE une limite qui est celle du LOGICIEL.
#: Confondre « les données ne permettent pas » et « le module ne sait pas
#: encore » est exactement le motif que cet audit poursuit.
#: ⚠️ IL DISPARAÎT QUAND L4 ATTERRIT : il n'a de sens que tant que
#: l'estimation n'est pas construite.
ELASTICITE_ESTIMEE          = 'ESTIMEE'
ELASTICITE_NON_IDENTIFIABLE = 'NON_IDENTIFIABLE'
ELASTICITE_NON_FOURNIE      = 'NON_FOURNIE'
ELASTICITE_NON_EXPLOITEE    = 'NON_EXPLOITEE'


def _cout_des_absences(hors: dict[str, tuple[str, ...]]) -> str:
    """Ce que les exigences manquantes coûtent, en une phrase par rôle."""
    if not hors:
        return ""
    par_role: dict[str, list[str]] = {}
    for nom, absents in hors.items():
        par_role.setdefault(' ou '.join(absents), []).append(nom)
    return " ".join(
        f"Sans « {role} » : {'; '.join(EXIGENCES[n].libelle for n in sorted(noms))}."
        for role, noms in sorted(par_role.items()))


def etat_elasticite(plan=None) -> dict:
    """L'élasticité-prix : un ÉTAT déclaré, jamais une valeur inventée.

    ⚠️ AUCUN BLOCAGE, DANS AUCUN ÉTAT. La tarification se fait normalement ;
    seule la dimension élasticité est ignorée, et signalée.

      ESTIMEE           les données sont déclarées ET la variation de prix est
                        exploitable : l'élasticité est estimée, et une
                        optimisation tarifaire devient légitime.
      NON_IDENTIFIABLE  les données existent, mais le prix est une fonction
                        (quasi) déterministe du risque : la variation
                        résiduelle ne permet à AUCUNE méthode de séparer
                        l'effet-prix de la sélection du risque.
      NON_FOURNIE       aucun bloc `comportement` n'est déclaré au plan.
      NON_EXPLOITEE     le bloc est déclaré et complet, mais l'estimation
                        (lots L3 à L5) n'est pas construite. Voir la note
                        ci-dessus : ce n'est ni une absence de données, ni une
                        limite du portefeuille.
    """
    roles = roles_du_plan(plan)
    caps = capacites(roles)
    hors = exigences_hors_portee(roles)
    socle = {
        'capacites':   caps,
        'hors_portee': {n: list(v) for n, v in hors.items()},
        'diagnostic':  diagnostic(plan),
    }

    if not caps.get('elasticite_estimable'):
        return {
            **socle,
            'etat': ELASTICITE_NON_FOURNIE,
            'motif': (
                "Aucune donnée de comportement de renouvellement n'est "
                "déclarée au plan tarifaire : ni l'issue du contrat "
                "(renouvelé / résilié), ni la prime précédente, ni la prime "
                "proposée à l'échéance."
            ),
            'ce_que_cela_coute': (
                "L'élasticité-prix n'est pas estimée, et AUCUNE "
                "recommandation de variation tarifaire n'est produite. Le "
                "reste de la tarification n'est pas affecté. "
                + _cout_des_absences(hors)
            ),
            'ce_quil_faudrait': (
                "Un historique de renouvellement : une ligne par contrat ET "
                "par échéance, portant l'issue, la prime précédente et la "
                "prime proposée. Une élasticité répond à une VARIATION de "
                "prix, pas à un niveau."
            ),
        }

    return {
        **socle,
        'etat': ELASTICITE_NON_EXPLOITEE,
        'motif': (
            "Le bloc `comportement` est déclaré et complet : la donnée "
            "nécessaire est là. L'exploitation — diagnostic d'exploitabilité "
            "de la variation de prix, puis estimation — n'est pas encore "
            "construite (lots L3 à L5)."
        ),
        'ce_que_cela_coute': (
            "L'élasticité-prix n'est pas estimée, et AUCUNE recommandation de "
            "variation tarifaire n'est produite. ⚠️ Ce n'est PAS une limite du "
            "portefeuille : sa variation de prix n'a pas été examinée. "
            + _cout_des_absences(hors)
        ),
        'ce_quil_faudrait': (
            "Rien de plus du client. Ce qui manque est dans le module."
        ),
    }
