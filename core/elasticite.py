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
#  L'EXPLOITABILITÉ DE LA VARIATION DE PRIX — mesurée AVANT toute estimation
# ══════════════════════════════════════════════════════════════════════════════

#: ⚠️⚠️ TROIS CONVENTIONS, ET AUCUNE NE VIENT D'UN TEXTE. Un seuil sans son
#: origine se lit comme une norme ; ceux-ci sont des choix du module, publiés
#: avec le diagnostic pour que le lecteur puisse les contester.
#:
#: `R2_MAX` — au-delà, la variation de prix est considérée comme entièrement
#: expliquée par les facteurs de risque : il ne reste rien d'indépendant à
#: exploiter. 0,95 est le seuil pratique du « quasi déterministe ».
#: `N_MIN_LIGNES` / `N_MIN_RESILIATIONS` — en dessous, l'échantillon ne porte
#: pas une élasticité, quelle que soit la qualité de sa variation de prix. Un
#: modèle de résiliation a besoin d'ÉVÉNEMENTS, pas seulement de lignes.
R2_MAX = 0.95
N_MIN_LIGNES = 200
N_MIN_RESILIATIONS = 30
#: En dessous, la variation résiduelle est indiscernable d'un bruit d'arrondi.
ECART_TYPE_MIN = 1e-4

VOIE_EXPERIMENTALE = 'experimentale'
VOIE_RESIDUELLE = 'residuelle'


def _r2_prix_sur_risque(v, X):
    """Part de la variation de prix expliquée par les facteurs de risque.

    ⚠️ C'EST LA MESURE QUI DÉCIDE, ET ELLE NE DEMANDE AUCUN MODÈLE. La question
    n'est pas « le modèle prédit-il bien ? » mais « le prix a-t-il bougé
    AUTREMENT que le risque ? ». C'est une propriété des données seules, donc
    elle se mesure avant toute estimation — et c'est ce qui rend le troisième
    état atteignable sans rien estimer.

    Rend `(r2, ecart_type_residuel)`, ou `(None, ecart_type)` si la régression
    n'a pas pu être faite.
    """
    import numpy as np

    v = np.asarray(v, dtype=float)
    ss_tot = float(np.sum((v - v.mean()) ** 2))
    if ss_tot <= 0:
        return None, 0.0
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[0] != v.size or X.shape[1] == 0:
        return None, float(np.std(v))
    A = np.column_stack([np.ones(v.size), X])
    try:
        beta, *_ = np.linalg.lstsq(A, v, rcond=None)
    except np.linalg.LinAlgError:
        return None, float(np.std(v))
    residus = v - A @ beta
    r2 = 1.0 - float(np.sum(residus ** 2)) / ss_tot
    return max(0.0, min(1.0, r2)), float(np.std(residus))


def diagnostic_exploitabilite(plan, df,
                              r2_max: float = R2_MAX,
                              n_min: int = N_MIN_LIGNES,
                              n_min_resiliations: int = N_MIN_RESILIATIONS):
    """La variation de prix observée permet-elle d'identifier un effet-prix ?

    ⚠️⚠️ LE POINT DUR. L'assureur fixe le prix D'APRÈS LE RISQUE. Si les
    segments dont la sinistralité s'est dégradée ont été augmentés, alors prix,
    résiliation et risque bougent ensemble : régresser la résiliation sur le
    prix mesure UN MÉLANGE de l'effet-prix et de la sélection du risque. C'est
    de l'endogénéité au sens strict, et c'est ce qui sépare une élasticité
    d'une corrélation.

    ⚠️ DEUX VOIES, ET ELLES NE SE VALENT PAS :

      `experimentale`  un test de prix au renouvellement — remise ou hausse
                       TIRÉE AU SORT. Son exogénéité ne se mesure pas, elle se
                       déclare : c'est la seule situation où c'est vrai.
      `residuelle`     le prix a bougé autrement que le risque, et c'est cette
                       part-là qui identifie l'effet. Valide seulement s'il en
                       reste quelque chose — d'où la mesure du R².

    ⚠️⚠️ CE QUE CETTE FONCTION NE PEUT PAS FAIRE, ET QUI DOIT FIGURER DANS LE
    LIVRABLE : elle mesure la variation RÉSIDUELLE, elle ne démontre PAS que
    cette variation est indépendante de ce qu'on n'observe pas. Un R² faible
    dit qu'il reste de la variation ; il ne dit pas qu'elle est exogène. Aucun
    calcul ne peut le dire — seule une expérience le garantit.

    ⚠️ TROIS RAISONS DE REFUSER, ET ELLES NE SE CONFONDENT PAS : aucune
    variation de prix · une variation entièrement expliquée par le risque ·
    un effectif insuffisant. Elles appellent des actions différentes du
    client, donc le motif les distingue.
    """
    import numpy as np

    bloc = getattr(plan, 'comportement', None) if plan is not None else None
    conventions = {
        'r2_max': r2_max,
        'n_min_lignes': n_min,
        'n_min_resiliations': n_min_resiliations,
        'origine': "conventions du module — aucun texte n'en fixe",
    }
    vide = {
        'exploitable': False, 'voie': None, 'r2_prix_sur_risque': None,
        'ecart_type_residuel': None, 'n_lignes': 0, 'n_resiliations': 0,
        'n_groupes_test': 0, 'conventions': conventions,
        'reserve': (
            "La variation résiduelle est MESURÉE ; son indépendance à ce qui "
            "n'est pas observé n'est pas démontrée — aucun calcul ne le peut. "
            "Seul un test de prix la garantit."
        ),
    }
    if bloc is None or df is None or not hasattr(df, 'columns'):
        return {**vide, 'motif': "Aucun bloc `comportement` déclaré, ou aucune "
                                 "donnée fournie : rien n'a été mesuré."}

    manquantes = [c for c in bloc.colonnes() if c not in df.columns]
    if manquantes:
        return {**vide, 'motif': (
            f"Colonnes déclarées au plan mais absentes du fichier : "
            f"{sorted(manquantes)}. La déclaration n'est pas honorée.")}

    p0 = np.asarray(df[bloc.prime_precedente], dtype=float)
    p1 = np.asarray(df[bloc.prime_proposee], dtype=float)
    issue = np.asarray(df[bloc.issue], dtype=float)
    ok = np.isfinite(p0) & np.isfinite(p1) & (p0 > 0) & (p1 > 0)
    n_resil = int(np.nansum(issue[ok] > 0)) if ok.any() else 0

    # ── L'EFFECTIF D'ABORD : il conditionne tout le reste ────────────────────
    if int(ok.sum()) < n_min or n_resil < n_min_resiliations:
        return {**vide, 'n_lignes': int(ok.sum()), 'n_resiliations': n_resil,
                'motif': (
                    f"Effectif insuffisant : {int(ok.sum())} renouvellement(s) "
                    f"exploitable(s) et {n_resil} résiliation(s), pour un "
                    f"plancher de {n_min} et {n_min_resiliations}. Un modèle "
                    f"de résiliation a besoin d'ÉVÉNEMENTS, pas seulement de "
                    f"lignes.")}

    # ── LA VOIE EXPÉRIMENTALE : elle prime, et elle ne se mesure pas ─────────
    n_groupes = 0
    if bloc.groupe_test and bloc.groupe_test in df.columns:
        n_groupes = int(df.loc[ok, bloc.groupe_test].nunique())
        if n_groupes >= 2:
            v = np.log(p1[ok] / p0[ok])
            return {
                **vide, 'exploitable': True, 'voie': VOIE_EXPERIMENTALE,
                'n_lignes': int(ok.sum()), 'n_resiliations': n_resil,
                'n_groupes_test': n_groupes,
                'ecart_type_residuel': float(np.std(v)),
                'motif': (
                    f"Test de prix déclaré ({n_groupes} groupes) : la variation "
                    f"est exogène par construction. C'est la seule situation où "
                    f"l'exogénéité ne se discute pas."),
            }

    # ── LA VOIE RÉSIDUELLE : ce qui reste quand le risque est retiré ─────────
    v = np.log(p1[ok] / p0[ok])
    cols_risque = [c for c in (plan.colonnes_produites() if plan else ())
                   if c in df.columns]
    X = df.loc[ok, cols_risque].to_numpy(dtype=float) if cols_risque else None
    r2, sigma = _r2_prix_sur_risque(v, X if X is not None else np.empty((v.size, 0)))

    base = {**vide, 'n_lignes': int(ok.sum()), 'n_resiliations': n_resil,
            'n_groupes_test': n_groupes, 'r2_prix_sur_risque': r2,
            'ecart_type_residuel': sigma}

    if sigma <= ECART_TYPE_MIN and (r2 is None or float(np.std(v)) <= ECART_TYPE_MIN):
        return {**base, 'motif': (
            "Aucune variation de prix observée : les deux primes déclarées "
            "sont identiques sur tout l'échantillon. Aucune méthode ne "
            "récupère une élasticité sans variation à laquelle répondre.")}

    if r2 is None:
        return {**base, 'motif': (
            "La part de variation expliquée par les facteurs n'a pas pu être "
            "mesurée (aucun facteur exploitable dans le fichier).")}

    if r2 >= r2_max:
        return {**base, 'motif': (
            f"Le prix proposé est une fonction (quasi) déterministe du risque : "
            f"{r2:.1%} de sa variation est expliquée par les facteurs "
            f"tarifaires, pour un plafond de {r2_max:.0%}. Prix et risque sont "
            f"colinéaires — aucune méthode ne sépare l'effet-prix de la "
            f"sélection du risque.")}

    return {**base, 'exploitable': True, 'voie': VOIE_RESIDUELLE, 'motif': (
        f"{1 - r2:.1%} de la variation de prix reste inexpliquée par les "
        f"facteurs tarifaires (R² = {r2:.4f}) : c'est cette part qui identifie "
        f"l'effet-prix.")}


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


def etat_elasticite(plan=None, df=None) -> dict:
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

    # ── LA DONNÉE EST DÉCLARÉE : SA VARIATION DE PRIX EST-ELLE EXPLOITABLE ? ─
    # ⚠️ CE DIAGNOSTIC NE DEMANDE AUCUN MODÈLE. Il mesure une propriété des
    # DONNÉES — le prix a-t-il bougé autrement que le risque — et c'est ce qui
    # rend `NON_IDENTIFIABLE` atteignable sans rien estimer.
    if df is None:
        return {
            **socle,
            'etat': ELASTICITE_NON_EXPLOITEE,
            'motif': (
                "Le bloc `comportement` est déclaré et complet : la donnée "
                "nécessaire est là. Aucun fichier n'a été fourni à ce calcul, "
                "donc l'exploitabilité de la variation de prix n'a pas été "
                "examinée."
            ),
            'ce_que_cela_coute': (
                "L'élasticité-prix n'est pas estimée, et AUCUNE recommandation "
                "de variation tarifaire n'est produite. ⚠️ Ce n'est PAS une "
                "limite du portefeuille : rien n'a été mesuré sur lui. "
                + _cout_des_absences(hors)
            ),
            'ce_quil_faudrait': (
                "Rien de plus du client. Ce qui manque est dans le module."
            ),
        }

    diag = diagnostic_exploitabilite(plan, df)
    socle = {**socle, 'exploitabilite': diag}

    if not diag['exploitable']:
        # ⚠️ ICI LA LIMITE EST BIEN CELLE DU PORTEFEUILLE, ET L'ÉTAT DOIT LE
        # DIRE — c'est le pendant exact de `NON_EXPLOITEE`. Se tromper d'axe
        # ferait corriger au client la mauvaise chose.
        return {
            **socle,
            'etat': ELASTICITE_NON_IDENTIFIABLE,
            'motif': diag['motif'],
            'ce_que_cela_coute': (
                "L'élasticité-prix n'est pas estimée, et AUCUNE recommandation "
                "de variation tarifaire n'est produite. ⚠️ Cette fois la limite "
                "est celle des DONNÉES, pas du module : aucune méthode ne "
                "récupérerait une élasticité de cette variation de prix."
            ),
            'ce_quil_faudrait': (
                "Une variation de prix qui ne suive pas le risque — une "
                "révision tarifaire différenciée, ou mieux un test de prix au "
                "renouvellement (déclarer `groupe_test`), dont l'exogénéité ne "
                "se discute pas."
            ),
        }

    return {
        **socle,
        'etat': ELASTICITE_NON_EXPLOITEE,
        'motif': (
            f"Le bloc `comportement` est déclaré, et la variation de prix est "
            f"exploitable par la voie « {diag['voie']} » : {diag['motif']} "
            f"L'estimation elle-même (lots L4-L5) n'est pas construite."
        ),
        'ce_que_cela_coute': (
            "L'élasticité-prix n'est pas estimée, et AUCUNE recommandation de "
            "variation tarifaire n'est produite. ⚠️ Ce n'est PAS une limite du "
            "portefeuille : sa variation de prix a été examinée et elle "
            "convient. " + _cout_des_absences(hors)
        ),
        'ce_quil_faudrait': (
            "Rien de plus du client. Ce qui manque est dans le module."
        ),
    }
