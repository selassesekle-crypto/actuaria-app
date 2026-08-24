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

from itertools import pairwise
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
#  L'ESTIMATION — un ε, TOUJOURS avec son intervalle
# ══════════════════════════════════════════════════════════════════════════════

#: ⚠️ DEUX CONVENTIONS DE PLUS, ET ELLES DÉCIDENT DU CINQUIÈME CAS.
#: Un intervalle qui contient zéro ne permet même pas de signer l'effet ; un
#: intervalle dont la demi-largeur dépasse la moitié de l'estimation ne peut
#: fonder aucune décision tarifaire. Aucun texte ne fixe ces bornes.
PRECISION_RELATIVE_MAX = 0.50
Z_95 = 1.959963985


def _ajuster_logit(y, X):
    """Régression logistique de la résiliation.

    Rend `(beta, se, p_moyen, ok, probabilites)`. `X` : la première colonne EST
    la variation de prix ; les suivantes sont les contrôles. `beta` et `se`
    portent donc sur la première.
    """
    import numpy as np
    try:
        import statsmodels.api as sm
    except ImportError:
        return None, None, None, False, None
    try:
        A = sm.add_constant(np.asarray(X, dtype=float), has_constant='add')
        res = sm.GLM(np.asarray(y, dtype=float), A,
                     family=sm.families.Binomial()).fit(maxiter=100)
        if not bool(getattr(res, 'converged', True)):
            return None, None, None, False, None
        beta = float(res.params[1])
        se = float(res.bse[1])
        p_moyen = float(np.mean(res.fittedvalues))
        if not (np.isfinite(beta) and np.isfinite(se) and se > 0):
            return None, None, None, False, None
        # ⚠️ LES PROBABILITÉS AJUSTÉES SONT RENDUES AVEC LE RESTE, ET C'EST
        # CE QUI PERMET À L5 DE TRACER LA VRAIE COURBE. Sans elles il faudrait
        # une approximation à élasticité constante — celle qui, mesurée, ne
        # redescend jamais et fait tomber l'optimum sur une borne.
        return beta, se, p_moyen, True, np.asarray(res.fittedvalues, dtype=float)
    except (ValueError, TypeError, IndexError, KeyError,
            np.linalg.LinAlgError, ZeroDivisionError):
        # Separation parfaite, matrice singuliere, colonne degeneree : autant
        # de cas ou l'ajustement n'aboutit pas. Ils se declarent, ils ne se
        # rattrapent pas.
        return None, None, None, False, None


def _construire_regression(plan, df, diag):
    """La régression de résiliation — SOURCE UNIQUE des deux consommateurs.

    ⚠️ `estimer_elasticite` ET `sensibilite_tarifaire` doivent ajuster LA MÊME
    régression. Deux constructions divergeraient un jour, et la courbe publiée
    ne serait plus celle dont l'élasticité a été tirée — c'est exactement le
    motif que cet audit poursuit.

    ⚠️ LA VOIE DÉCIDE DE CE QU'ON RÉGRESSE, et les deux n'ont pas la même
    arithmétique. Mesuré sur un jeu à ε connu = −0,2329, prix ENDOGÈNE : sans
    contrôle ε sort à −0,7213 (trois fois trop grand, son IC rate la vérité) ;
    avec contrôles −0,2237 ; par la moyenne de groupe −0,2108.
    """
    import numpy as np

    bloc = getattr(plan, 'comportement', None)
    p0 = np.asarray(df[bloc.prime_precedente], dtype=float)
    p1 = np.asarray(df[bloc.prime_proposee], dtype=float)
    y = np.asarray(df[bloc.issue], dtype=float)
    ok = np.isfinite(p0) & np.isfinite(p1) & (p0 > 0) & (p1 > 0) & np.isfinite(y)
    v = np.log(p1[ok] / p0[ok])
    y = y[ok]

    if diag.get('voie') == VOIE_EXPERIMENTALE:
        # Seule la variation ENTRE GROUPES est retenue : elle est tirée au
        # sort, donc exogène. Aucun contrôle — c'est tout l'intérêt.
        g = df.loc[ok, bloc.groupe_test].to_numpy()
        moyennes = {cle: float(v[g == cle].mean()) for cle in set(g)}
        X = np.array([moyennes[cle] for cle in g], dtype=float).reshape(-1, 1)
        controles: list[str] = []
        reserve = (
            "La variation exploitée est TIRÉE AU SORT : son indépendance au "
            "risque est garantie par le protocole, elle n'est pas supposée. "
            "C'est la seule situation où l'exogénéité ne se discute pas."
        )
    else:
        controles = [c for c in (plan.colonnes_produites() if plan else ())
                     if c in df.columns]
        X = np.column_stack(
            [v] + [df.loc[ok, c].to_numpy(dtype=float) for c in controles]
        ) if controles else v.reshape(-1, 1)
        reserve = (
            "L'effet-prix est identifié par la variation de prix qui RESTE "
            "une fois les facteurs tarifaires retirés. Cette variation est "
            "MESURÉE ; son indépendance à ce qui n'est pas observé n'est PAS "
            "démontrée — aucun calcul ne le peut. Seul un test de prix la "
            "garantirait."
        )
    return {'y': y, 'X': X, 'v': v, 'ok': ok, 'controles': controles,
            'reserve': reserve, 'primes': p1[ok]}


def estimer_elasticite(plan, df, diag=None,
                       precision_max: float = PRECISION_RELATIVE_MAX):
    """L'élasticité-prix de la demande, avec son intervalle de confiance.

    ⚠️ LA FORMULE, ET ELLE A ÉTÉ VÉRIFIÉE NUMÉRIQUEMENT AVANT D'ÊTRE ÉCRITE.
    Avec P(résiliation) = logistique(α + β·v), v = log(prime), et Q le nombre
    de contrats retenus :

        ε = ∂log(Q)/∂log(p) = −(∂P/∂v)/(1−P) = −β·P̄

    Contrôle numérique sur 400 000 lignes : élasticité mesurée en bougeant le
    prix de 1 % = −0,200501 ; formule −β·P̄ = −0,199792 ; écart 0,35 %, qui
    est le terme du second ordre.

    ⚠️⚠️ LES DEUX VOIES N'ONT PAS LA MÊME ARITHMÉTIQUE, et c'est la mesure qui
    l'a tranché — pas une préférence. Sur un jeu à ε connu de −0,2329, prix
    ENDOGÈNE :

        aucun contrôle              ε = −0,7213   son IC RATE la vérité
        v + contrôles (résiduelle)  ε = −0,2237   IC [−0,2947 ; −0,1528]
        v moyen du groupe (expér.)  ε = −0,2108   IC [−0,2805 ; −0,1412]

    Le premier est l'endogénéité mesurée : trois fois trop grand. Le second
    corrige, MAIS il dépend du modèle de contrôle. Le troisième n'utilise QUE
    le contraste tiré au sort et ne dépend d'AUCUN contrôle — c'est en cela
    que la voie expérimentale prime, et c'est arithmétique.

    ⚠️ L'INTERVALLE N'EST PAS OPTIONNEL. Un ε ponctuel sans son incertitude
    est exactement ce que le lot L0 a retiré. `se(ε) ≈ P̄ · se(β)` — méthode
    delta, P̄ traité comme connu, ce qui sous-estime légèrement la variance.
    C'est dit ici plutôt que tu.

    ⚠️ LE CINQUIÈME CAS : `concluante = False` quand l'ajustement ne converge
    pas, quand l'intervalle contient zéro, ou quand sa demi-largeur dépasse la
    moitié de l'estimation. Il ne se confond PAS avec `NON_IDENTIFIABLE` :
    celui-là accuse la variation de prix, celui-ci constate que le signal
    était trop faible pour conclure.
    """
    import numpy as np

    if diag is None:
        diag = diagnostic_exploitabilite(plan, df)
    conventions = {
        **diag.get('conventions', {}),
        'precision_relative_max': precision_max,
        'niveau_de_confiance': 0.95,
    }
    vide = {
        'concluante': False, 'elasticite': None, 'ic_bas': None,
        'ic_haut': None, 'erreur_type': None, 'beta': None,
        'taux_resiliation_moyen': None, 'voie': diag.get('voie'),
        'facteurs_de_controle': [], 'n_lignes': diag.get('n_lignes', 0),
        'n_resiliations': diag.get('n_resiliations', 0),
        'conventions': conventions,
    }
    if not diag.get('exploitable'):
        return {**vide, 'motif': (
            "La variation de prix n'est pas exploitable : rien n'a été estimé. "
            + (diag.get('motif') or ''))}

    reg = _construire_regression(plan, df, diag)
    y, X, controles, reserve = (reg['y'], reg['X'], reg['controles'],
                                reg['reserve'])
    ok = reg['ok']
    beta, se, p_moyen, converge, _ = _ajuster_logit(y, X)
    base = {**vide, 'facteurs_de_controle': controles, 'reserve': reserve,
            'n_lignes': int(ok.sum()), 'n_resiliations': int(np.sum(y > 0))}

    if not converge:
        return {**base, 'motif': (
            "L'ajustement du modèle de résiliation n'a pas convergé, ou son "
            "erreur type n'est pas exploitable. Aucune élasticité n'est "
            "publiée. ⚠️ Ce n'est PAS un défaut de la variation de prix, que le "
            "diagnostic a jugée exploitable.")}

    eps = -beta * p_moyen
    se_eps = abs(p_moyen) * se
    demi = Z_95 * se_eps
    bas, haut = eps - demi, eps + demi
    chiffre = {**base, 'elasticite': round(eps, 5), 'ic_bas': round(bas, 5),
               'ic_haut': round(haut, 5), 'erreur_type': round(se_eps, 6),
               'beta': round(beta, 5),
               'taux_resiliation_moyen': round(p_moyen, 5)}

    if bas <= 0.0 <= haut:
        return {**chiffre, 'motif': (
            f"L'intervalle de confiance à 95 % [{bas:+.4f} ; {haut:+.4f}] "
            f"contient zéro : le signal ne permet même pas de SIGNER l'effet "
            f"du prix sur la résiliation. Aucune élasticité n'est publiée.")}

    if abs(eps) > 0 and demi / abs(eps) > precision_max:
        return {**chiffre, 'motif': (
            f"L'intervalle est trop large pour fonder une décision : la "
            f"demi-largeur vaut {demi / abs(eps):.0%} de l'estimation, pour "
            f"un plafond de {precision_max:.0%}. Aucune élasticité n'est "
            f"publiée.")}

    return {**chiffre, 'concluante': True, 'motif': (
        f"Élasticité-prix estimée à {eps:+.4f}, intervalle de confiance à "
        f"95 % [{bas:+.4f} ; {haut:+.4f}], sur {int(ok.sum()):,} "
        f"renouvellements dont {int(np.sum(y > 0)):,} résiliations.")}


# ══════════════════════════════════════════════════════════════════════════════
#  L'ÉTAT PUBLIÉ — jamais une valeur inventée
# ══════════════════════════════════════════════════════════════════════════════

#: Les états de l'élasticité. Les trois premiers décrivent l'issue d'une
#: TENTATIVE D'ESTIMATION ; le quatrième dit que la tentative n'est pas encore
#: constructible.
#:
#: ⚠️⚠️ `NON_EXPLOITEE` A CHANGÉ DE SENS AU LOT L4, ET SA JUSTIFICATION EST
#: RÉÉCRITE PLUTÔT QUE LAISSÉE DERRIÈRE. Elle disait « l'estimation (L3-L5)
#: n'est pas construite » : elle l'est désormais. Une justification qui
#: survit à son objet est le défaut que cet audit poursuit — c'est très
#: exactement ce que fait encore `FIGURES_ECARTEES['monitoring_gini']`, qui
#: écarte une figure pour des « données FABRIQUÉES » que le correctif
#: `98dba85` a rendues mesurées. On ne le répète pas ici.
#: `NON_EXPLOITEE` signifie AUJOURD'HUI : le bloc est déclaré, mais AUCUNE
#: DONNÉE n'a été fournie à ce calcul — donc rien n'a été examiné.
#:
#: ⚠️ CE QUI RESTE VRAI, ET QUI VALAIT LA CONTESTATION DU MODÈLE À TROIS
#: ÉTATS : ce cas ne doit retomber ni sur `NON_FOURNIE` — la donnée EST
#: déclarée — ni sur `NON_IDENTIFIABLE`, qui imputerait au PORTEFEUILLE une
#: limite qui n'est pas la sienne. Rien n'a été mesuré sur lui.
ELASTICITE_ESTIMEE          = 'ESTIMEE'
ELASTICITE_NON_IDENTIFIABLE = 'NON_IDENTIFIABLE'
ELASTICITE_NON_FOURNIE      = 'NON_FOURNIE'
ELASTICITE_NON_EXPLOITEE    = 'NON_EXPLOITEE'
#: ⚠️ LE CINQUIÈME. La donnée est là, la variation est exploitable, et
#: l'estimation a bien été tentée — mais le signal ne permet pas de conclure
#: (pas de convergence, intervalle contenant zéro, ou trop large). Il
#: n'accuse NI l'absence de données NI le portefeuille : il constate un
#: manque de signal, et c'est une troisième chose.
ELASTICITE_NON_CONCLUANTE   = 'NON_CONCLUANTE'


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

    # ── LA VARIATION EST EXPLOITABLE : ON ESTIME ─────────────────────────────
    est = estimer_elasticite(plan, df, diag)
    socle = {**socle, 'estimation': est}

    if not est['concluante']:
        # ⚠️ LE CINQUIÈME CAS. Ni une absence de données, ni un défaut du
        # portefeuille : la variation était exploitable et l'estimation a bien
        # été tentée. Ce qui manquait, c'est du SIGNAL.
        return {
            **socle,
            'etat': ELASTICITE_NON_CONCLUANTE,
            'motif': est['motif'],
            'ce_que_cela_coute': (
                "L'élasticité-prix n'est pas publiée, et AUCUNE recommandation "
                "de variation tarifaire n'est produite. ⚠️ Ni les données ni "
                "leur variation de prix ne sont en cause : l'estimation a été "
                "tentée et son résultat est trop imprécis pour décider."
            ),
            'ce_quil_faudrait': (
                "Plus d'observations, ou une variation de prix de plus grande "
                "amplitude. Une élasticité faible demande davantage de "
                "renouvellements pour être tranchée qu'une élasticité forte."
            ),
        }

    return {
        **socle,
        'etat': ELASTICITE_ESTIMEE,
        'motif': est['motif'],
        'ce_que_cela_coute': (
            "Rien : l'élasticité-prix est estimée, avec son intervalle de "
            "confiance. Une analyse de sensibilité tarifaire devient "
            "légitime. " + _cout_des_absences(hors)
        ),
        'ce_quil_faudrait': (
            "Rien de plus pour l'estimation elle-même. "
            + ("Un test de prix au renouvellement (`groupe_test`) rendrait "
               "l'exogénéité garantie plutôt que supposée."
               if est['voie'] != VOIE_EXPERIMENTALE else
               "L'identification repose déjà sur un tirage au sort.")
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  LA SENSIBILITÉ TARIFAIRE — ce qui a été retiré en L0, fondé cette fois
# ══════════════════════════════════════════════════════════════════════════════

#: La grille par défaut, en variation relative du tarif. ⚠️ C'EST UNE
#: CONVENTION, ET L'ACTUAIRE PEUT LA DÉCLARER AUTREMENT. Elle ne décide de
#: rien : chaque point porte séparément l'indication de savoir s'il est appuyé
#: par les données.
VARIATIONS_DEFAUT = (-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15)

#: Le domaine observé est délimité par ces centiles de la variation de prix
#: réellement subie. Les queues sont écartées : deux contrats atypiques ne
#: font pas un domaine d'appui. Convention du module.
CENTILE_DOMAINE_BAS, CENTILE_DOMAINE_HAUT = 5.0, 95.0


def _charge_moyenne(df, plan, ok):
    """Charge sinistre moyenne par contrat — la vraie, prise dans les données.

    ⚠️ ELLE NE BAISSE PAS QUAND LE PRIX BAISSE, et c'est tout l'enjeu : une
    marge calculée comme une fraction du chiffre d'affaires n'apporte rien que
    le chiffre d'affaires ne porte déjà.
    """
    import numpy as np

    for col in (getattr(plan, 'cible_cout', None), 'prime_pure',
                'cout_total_sinistres'):
        if col and col in df.columns:
            valeurs = np.asarray(df.loc[ok, col], dtype=float)
            valeurs = valeurs[np.isfinite(valeurs)]
            if valeurs.size and float(np.mean(valeurs)) > 0:
                return float(np.mean(valeurs))
    return 0.0


def _lire_optimum(scenarios, domaine):
    """L'optimum n'est publié QUE s'il est intérieur ET appuyé par les données.

    ⚠️⚠️ UNE BORNE N'EST PAS UN OPTIMUM : c'est le bord de ce qu'on a regardé.
    L'ancienne fonction rendait « −20 % » parce que son optimum tombait
    mécaniquement sur la borne basse de sa grille — et une version fondée
    rendrait « +20 % » pour exactement la même raison si on la laissait faire.
    """
    if len(scenarios) < 3:
        return {'optimum': None, 'marge_monotone_croissante': None,
                'motif_optimum': ("Grille trop courte pour distinguer un "
                                  "optimum d'une borne.")}
    marges = [s['marge_technique'] for s in scenarios]
    i = max(range(len(marges)), key=marges.__getitem__)
    croissante = all(b >= a for a, b in pairwise(marges))
    if i in (0, len(marges) - 1):
        suite = ("Elle croît sur toute la plage examinée — élargir la grille "
                 "déplacerait simplement le maximum."
                 if croissante else
                 "Élargir la grille dans cette direction montrerait si un "
                 "optimum existe au-delà.")
        return {
            'optimum': None, 'marge_monotone_croissante': croissante,
            'motif_optimum': (
                f"La marge est maximale à la BORNE "
                f"{scenarios[i]['variation_pct']:+.0f} % de la grille : ce "
                f"n'est pas un optimum, c'est le bord de ce qui a été "
                f"examiné. " + suite),
        }
    if not scenarios[i]['dans_le_domaine_observe']:
        return {
            'optimum': None, 'marge_monotone_croissante': croissante,
            'motif_optimum': (
                f"La marge est maximale à "
                f"{scenarios[i]['variation_pct']:+.0f} %, HORS du domaine de "
                f"variation de prix réellement observé "
                f"([{domaine['delta_min']:+.1%} ; "
                f"{domaine['delta_max']:+.1%}]). Le modèle y extrapole : le "
                f"chiffre n'est pas appuyé par les données qui l'ont "
                f"produit."),
        }
    return {'optimum': scenarios[i], 'marge_monotone_croissante': croissante,
            'motif_optimum': None}


def sensibilite_tarifaire(plan, df, etat, variations=VARIATIONS_DEFAUT,
                          chargements=None):
    """Ce que deviendraient volume, chiffre d'affaires et marge si le tarif
    bougeait — avec l'incertitude de l'estimation, et ce qui l'appuie.

    ⚠️⚠️ QUATRE DÉFAUTS DE L'ANCIENNE FONCTION, ET AUCUN NE REVIENT.
    Mesurés avant son retrait au lot L0 : élasticité codée en dur à −1,5 ·
    portefeuille fictif de 450 € et 10 000 contrats · marge = CA × 0,30, donc
    proportionnelle au CA et sans information · et un optimum qui tombait
    MÉCANIQUEMENT sur la borne basse de sa propre grille.

    ⚠️⚠️ LA COURBE VIENT DU LOGIT AJUSTÉ, PAS D'UNE ÉLASTICITÉ CONSTANTE — et
    c'est la correction qui a débloqué ce lot. `Q = Q0·(p/p0)^ε` ne redescend
    JAMAIS quand ε > −1 : sa marge croît sans borne, et tout « optimum » est
    alors une borne de grille. Le logit, lui, SATURE : quand le prix monte, la
    résiliation tend vers 1 et la rétention s'effondre. Mesuré à +500 % :
    46,8 M€ et toujours croissant pour l'approximation, contre 10,6 M€ après
    un maximum de 12,9 M€ à +200 % pour le modèle réellement ajusté.

    ⚠️ LA MARGE SUIT LA STRUCTURE DE CHARGEMENTS DU DÉPÔT
    (`pipeline_tarifaire.CHARGEMENTS_DEFAUT`), pas une fraction du CA :

        marge_technique = prime × (1 − commission) − charge × (1 + frais)

    LA CHARGE SINISTRE NE BAISSE PAS QUAND LE PRIX BAISSE. C'est toute la
    différence avec `CA × 0,30`, qui ne portait aucune information que le CA
    ne portât déjà. ⚠️ Elle est AVANT coût du capital et frais d'acquisition,
    et son nom le dit.

    ⚠️⚠️ CE QUI RESTE VRAI ET QU'AUCUNE FORME NE RÈGLE : β est estimé sur les
    variations de prix RÉELLEMENT observées. Évaluer la courbe au-delà, c'est
    extrapoler hors du domaine où elle a été mesurée — et la déclaration d'une
    plage par l'actuaire n'efface pas ce fait. La grille est celle qu'il
    déclare ; chaque point dit s'il est appuyé.

    ⚠️ LES PRIMES DÉCLARÉES SONT SUPPOSÉES HORS TAXES. Si elles sont TTC, la
    marge est surestimée — les taxes sont collectées pour le compte de l'État.
    L'élasticité, elle, n'en dépend pas : les taxes étant proportionnelles,
    une variation relative du HT est la même variation relative du TTC.
    """
    import numpy as np

    from direction_non_vie.tarification.pipeline_tarifaire import (
        CHARGEMENTS_DEFAUT,
    )

    ch = dict(CHARGEMENTS_DEFAUT if chargements is None else chargements)
    conventions = {
        'chargements': ch,
        'centiles_domaine': [CENTILE_DOMAINE_BAS, CENTILE_DOMAINE_HAUT],
        'primes_supposees': 'hors taxes',
        'origine': "conventions du module — aucun texte n'en fixe",
    }
    vide = {
        'disponible': False, 'scenarios': [], 'optimum': None,
        'motif_optimum': None, 'portefeuille': {}, 'domaine_observe': {},
        'marge_monotone_croissante': None, 'conventions': conventions,
    }

    etat_nom = (etat or {}).get('etat')
    if etat_nom != ELASTICITE_ESTIMEE:
        # ⚠️ LES CINQ ÉTATS COMMANDENT. Une sensibilité sans élasticité estimée
        # serait exactement la constante qu'on a retirée.
        return {**vide, 'motif': (
            f"Aucune sensibilité tarifaire : l'élasticité-prix est en état "
            f"{etat_nom}. {(etat or {}).get('motif', '')}")}

    est = etat['estimation']
    diag = etat['exploitabilite']
    reg = _construire_regression(plan, df, diag)
    beta, se, p_moyen, converge, prob = _ajuster_logit(reg['y'], reg['X'])
    if not converge:
        return {**vide, 'motif': (
            "L'ajustement n'a pas convergé au moment de tracer la courbe.")}

    # ── LE PORTEFEUILLE RÉEL — jamais 450 EUR et 10 000 contrats ────────────
    primes = np.asarray(reg['primes'], dtype=float)
    bloc = plan.comportement
    charge = _charge_moyenne(df, plan, reg['ok'])
    pf = {
        'n_contrats': len(primes),
        'prime_moyenne': round(float(np.mean(primes)), 2),
        'charge_moyenne': round(float(charge), 2),
        # ⚠️ LE TAUX DE RESILIATION ACTUEL — le point de depart de la courbe.
        # Sans lui, une variation de volume ne se lit pas.
        'taux_resiliation_actuel': round(float(p_moyen), 5),
        'source': (f"colonnes declarees au plan : « {bloc.prime_proposee} » "
                   f"pour la prime, cible de cout pour la charge"),
    }

    # ── LE DOMAINE OBSERVÉ — ce qui appuie la courbe ────────────────────────
    v_obs = np.asarray(reg['v'], dtype=float)
    d_bas = float(np.expm1(np.percentile(v_obs, CENTILE_DOMAINE_BAS)))
    d_haut = float(np.expm1(np.percentile(v_obs, CENTILE_DOMAINE_HAUT)))
    domaine = {'delta_min': round(d_bas, 5), 'delta_max': round(d_haut, 5),
               'centile_bas': CENTILE_DOMAINE_BAS,
               'centile_haut': CENTILE_DOMAINE_HAUT}

    # ── LA COURBE, DEPUIS LE LOGIT AJUSTÉ ───────────────────────────────────
    prob = np.clip(np.asarray(prob, dtype=float), 1e-9, 1 - 1e-9)
    eta0 = np.log(prob / (1.0 - prob))       # prédicteur linéaire au tarif actuel
    a, f = 1.0 - ch['commission'], 1.0 + ch['frais']

    def _point(delta, b):
        """Volume, CA et marge au tarif (1+delta), pour un beta donné."""
        eta = eta0 + b * np.log1p(delta)
        retenus = 1.0 - 1.0 / (1.0 + np.exp(-eta))
        p_new = primes * (1.0 + delta)
        return (float(np.sum(retenus)),
                float(np.sum(retenus * p_new)),
                float(np.sum(retenus * (p_new * a - charge * f))))

    b_bas, b_haut = beta - Z_95 * se, beta + Z_95 * se
    scenarios = []
    for delta in variations:
        q, ca, mg = _point(delta, beta)
        bornes = [_point(delta, b_bas), _point(delta, b_haut)]
        scenarios.append({
            'variation_pct':  round(delta * 100, 2),
            'dans_le_domaine_observe': bool(d_bas <= delta <= d_haut),
            'contrats':       round(q, 1),
            'contrats_bas':   round(min(x[0] for x in bornes), 1),
            'contrats_haut':  round(max(x[0] for x in bornes), 1),
            'ca':             round(ca, 2),
            'ca_bas':         round(min(x[1] for x in bornes), 2),
            'ca_haut':        round(max(x[1] for x in bornes), 2),
            'marge_technique': round(mg, 2),
            'marge_bas':      round(min(x[2] for x in bornes), 2),
            'marge_haut':     round(max(x[2] for x in bornes), 2),
        })

    return {
        **vide, 'disponible': True, 'scenarios': scenarios,
        'portefeuille': pf, 'domaine_observe': domaine,
        'reserve': est.get('reserve'),
        'elasticite': est.get('elasticite'),
        'elasticite_ic': [est.get('ic_bas'), est.get('ic_haut')],
        'motif': (
            f"Sensibilite tracee depuis le modele de resiliation ajuste, sur "
            f"{pf['n_contrats']:,} contrats, avec l'incertitude de "
            f"l'estimation (eps = {est.get('elasticite'):+.4f}, IC 95 % "
            f"[{est.get('ic_bas'):+.4f} ; {est.get('ic_haut'):+.4f}])."),
        **_lire_optimum(scenarios, domaine),
    }
