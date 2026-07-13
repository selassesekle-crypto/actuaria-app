"""
ActuarIA — core/conformite_reglementaire.py
Conformité réglementaire — MODULE TRANSVERSAL PLATEFORME

⚠ SOURCE UNIQUE, POUR LES TROIS DIRECTIONS.
Ce module doit être importé par TOUT agent, de TOUTE direction (Non-Vie,
Vie/EP-RE, Santé-Prévoyance), qui construit une matrice de features à partir
de données client. Il ne doit jamais être dupliqué ni réimplémenté localement.

Pourquoi au niveau plateforme (promu depuis
direction_non_vie/tarification/services/ le 11/07/2026) :

  Le mode de défaillance DOMINANT de ce codebase, documenté sur six cycles
  d'audit (V4 → V9), est toujours le même : « une règle de conformité correcte
  à un endroit, jamais propagée ailleurs ».
    · V7 : filtre genre présent dans A3, absent d'A4 et A5 → BLOQUANT.
    · V8 : filtre anti-fuite absent du walk-forward d'A6 → BLOQUANT.
    · V9 : filtre genre par égalité stricte, contourné par le one-hot d'A2
           (sexe_m/sexe_f) hors branche auto → BLOQUANT.
    · V9+ : filtre genre contourné une seconde fois par l'encodage label
           automatique de repli d'A2 (sexe_enc) → trouvé en exécution.

  La conclusion pratique est nette : la mutualisation des règles de conformité
  est la SEULE protection qui tienne. Les directions sont autonomes sur leurs
  pipelines de données et leur logique métier — mais PAS sur la conformité
  réglementaire, qui est une propriété de la plateforme entière. Trois copies
  d'un filtre genre, ce sont trois endroits à corriger à chaque évolution
  ACPR/CJUE, et l'un d'eux sera oublié : l'historique ci-dessus le prouve.

  ⚠ ÉTAT AU 11/07/2026 : les directions Vie/EP-RE et Santé-Prévoyance
  n'appliquent AUCUN filtre de conformité (ni genre, ni anti-fuite). Elles ne
  sont pas exposées aujourd'hui parce que leurs agents de tarification sont
  PARAMÉTRIQUES (ils ne construisent pas de matrice X à partir de données
  client). Dès qu'un agent de ces directions tarifera sur données réelles, il
  DEVRA importer ce module. Test-Achats s'applique à toute l'assurance, et le
  risque de fuite de données est structurellement plus élevé encore en
  provisionnement (triangles de sinistralité).

Deux familles de règles y sont centralisées :

  1. GENRE (filtrer_genre) — CJUE C-236/09, arrêt Test-Achats du 1er mars 2011,
     Directive 2004/113/CE. Interdit comme critère de tarification en assurance
     depuis le 21 décembre 2012, POUR TOUTE BRANCHE (pas seulement la RC Auto).

  2. FAMILLE CIBLE (filtrer_famille_cible) — prévention du data leakage : toute
     grandeur dérivée de la sinistralité de la période observée est interdite
     comme feature (elle est de toute façon inconnue au moment de tarifer un
     contrat neuf). Les variables d'expérience PASSÉE (N-1, antécédents), elles,
     restent légitimes — c'est la distinction qui fonde le bonus-malus.

Usage :
    from core.conformite_reglementaire import filtrer_genre, filtrer_famille_cible

    feature_names = filtrer_genre(feature_names, contexte='A4 — features ML')
    feature_names = filtrer_famille_cible(feature_names, contexte='A4 — features ML')
"""

import logging
from typing import List, Optional

logger = logging.getLogger('actuaria.tarif.conformite')

# ── Colonnes/racines interdites — INCONDITIONNEL ──────────────────────────────
# Pas de scoping par sous-branche : un scoping par nom de branche serait
# lui-même une faille si la sous-branche est mal nommée ou non reconnue
# (cas testé et confirmé lors de l'audit V4 : une sous-branche non détectée
# déclenche un fallback sans aucune protection si le filtre est conditionné
# au nom de la branche). Le genre n'a par ailleurs aucune justification
# actuarielle valide comme facteur de tarification, quelle que soit la
# branche ou le produit d'assurance.
COLS_GENRE_INTERDITES = [
    'sexe', 'sexe_enc', 'genre', 'genre_enc', 'gender', 'gender_enc',
]

# Racines (correspondance par sous-chaîne, insensible à la casse) — ajoutées
# suite à l'audit V9 (double BLOQUANT). L'égalité stricte précédente ne
# capturait que 6 noms exacts et laissait passer : (a) les colonnes filles du
# one-hot encodé par A2 pour TOUTES les sous-branches sauf 'auto' (sexe_M,
# sexe_F — prouvé par exécution : ces colonnes atteignaient directement la
# matrice d'entraînement d'A4 en branche MRH, pas seulement un scénario
# walk-forward) ; (b) les variantes de casse (Sexe, SEXE) et de langue (sex) ;
# (c) le proxy direct de genre que constitue la civilité (M./Mme).
# Vérifié sur le vocabulaire de colonnes réellement produit par A1/A2/A4/A5 :
# aucune collision avec un facteur tarifaire légitime (age, bonus_malus,
# puissance_fiscale, zone_geographique, carburant, etc. — aucun ne contient
# ces racines).
COLS_GENRE_STEMS = [
    'sex', 'genre', 'gender', 'civilite', 'titre_civil', 'titre',
    'prenom', 'madame', 'monsieur', 'is_male', 'is_female',
]
# ⚠ 'titre' ajouté le 11/07/2026 (audit V10, BLOQUANT B1) : un fichier client
# contenant une colonne 'titre' (M./Mme — la civilité, proxy PARFAIT du genre)
# était encodé par A2 en 'titre_enc', qui atteignait ensuite la matrice de
# conception du GLM. La racine 'titre_civil' était trop spécifique pour le
# capturer. Aucun facteur tarifaire légitime ne contient ces racines.


def _est_variable_genre(nom: str) -> bool:
    """True si le nom de colonne est une variable de genre ou un proxy direct
    (civilité), y compris ses formes dérivées (one-hot, casse, langue)."""
    n = nom.lower()
    if n in COLS_GENRE_INTERDITES:
        return True
    return any(stem in n for stem in COLS_GENRE_STEMS)


def filtrer_genre(
    feature_names: List[str],
    contexte: str = '',
    logger_agent: Optional[logging.Logger] = None,
) -> List[str]:
    """
    Retire toute colonne de genre (ou proxy direct de genre) d'une liste de
    noms de features, en journalisant explicitement (niveau WARNING) toute
    suppression effective — traçabilité requise pour l'audit ACPR.

    Correspondance par racine, insensible à la casse (audit V9) : capture
    aussi bien les colonnes brutes (sexe, Sexe, gender) que leurs dérivées
    one-hot (sexe_M, sexe_F, genre_H) et le proxy civilité (civilite_Mme).

    Paramètres
    ----------
    feature_names : liste des noms de colonnes candidates comme features.
    contexte : texte libre identifiant l'appelant dans le message de log
        (ex. "A4 — sélection features ML").
    logger_agent : logger de l'agent appelant, pour que le message
        apparaisse dans les logs de cet agent plutôt que ceux de ce
        module partagé. Si None, utilise le logger de ce module.

    Retourne la liste filtrée (nouvel objet, ne modifie pas l'original).
    """
    _log = logger_agent or logger
    apres = [f for f in feature_names if not _est_variable_genre(f)]
    supprimees = set(feature_names) - set(apres)
    if supprimees:
        _log.warning(
            f"[CONFORMITE REGLEMENTAIRE] Variable(s) {sorted(supprimees)} "
            f"exclue(s) de la sélection de features"
            f"{' (' + contexte + ')' if contexte else ''}. "
            f"Réf. : Arrêt CJUE C-236/09 (Test-Achats)."
        )
    return apres


# ── Variables « famille cible » — anti-fuite de données ───────────────────────
# Créé suite à l'audit V8 (anomalie BLOQUANTE) : le correctif de l'audit V7
# (BLOQUANT #2) a fait calculer automatiquement 'prime_pure' par A2 pour
# réparer le contrat de données du walk-forward. Effet de bord : 'prime_pure'
# (= cout_total_sinistres / exposition) — donc une grandeur DÉRIVÉE de la
# sinistralité observée — s'est mise à circuler comme FEATURE dans A4/A5
# (quand la cible est la fréquence ou le coût) et dans le walk-forward d'A6.
# Conséquence prouvée par exécution : Gini fréquence auto = 0,91 AVEC
# prime_pure vs 0,20 SANS — signature nette de data leakage. Ces variables
# sont par ailleurs INCONNUES au moment de tarifer un contrat neuf : un
# modèle entraîné dessus est sur-ajusté ET non déployable.
#
# Même maladie que la fuite genre, autre symptôme : « certaines colonnes ne
# doivent JAMAIS être des features ». On centralise donc ici aussi, pour
# immuniser par construction tout agent de sélection de features présent ou
# futur (A3/A4/A5/A6). La cible reste lue via df[col_cible] (accès direct,
# indépendant de la liste de features) : l'exclusion ne casse donc jamais
# l'usage légitime de prime_pure/nb_sinistres/cout comme VARIABLE CIBLE.
COLS_FAMILLE_CIBLE = [
    'prime_pure', 'prime_pure_obs', 'prime_pure_annuelle',
    'prime_commerciale',
    'cout_total_sinistres', 'cout_moyen_attendu', 'cout_moyen',
    'nb_sinistres', 'nb_sinistres_rc', 'nb_sinistres_dommages',
    'lambda_freq', 'lambda_freq_annuel',
    'charge_annuelle_eur', 'charge_ij_annuelle_eur',
]

# Racines pour capturer les variantes dérivées (log_*, *_obs, *_annuel...)
# sans lister chaque combinaison. Élargies suite à l'audit V9 (BLOQUANT) :
# les racines initiales (V8) ne couvraient que le cas qui les a motivées
# (auto/prime_pure) — en branche santé, A2 produit des grandeurs de
# sinistralité OBSERVÉE sous des noms entièrement différents (sinistre_*,
# total_sinistres_sante, cout_hospitalisation...) qui ne partageaient aucune
# des 5 racines V8 et atteignaient donc la matrice X. Preuve par exécution :
# Gini fréquence santé 0,8093 avec ces colonnes vs 0,0725 sans (+0,74) —
# même signature que la fuite V8 (0,91 vs 0,20).
# 'sinistre' et 'cout_' sont volontairement larges (vérifié sur tout le
# vocabulaire de colonnes du module : aucun facteur tarifaire a priori
# légitime n'en contient) pour couvrir aussi les postes/variantes futurs
# sans nécessiter un nouveau correctif à chaque nouveau nom.
COLS_FAMILLE_CIBLE_STEMS = [
    'prime_pure', 'cout_total_sinistres', 'cout_moyen',
    'lambda_freq', 'nb_sinistres',
    'sinistre', 'cout_', 'part_hospit',
]

# Exceptions explicites — variables dont le nom contient une racine ci-dessus
# mais qui sont des facteurs tarifaires a priori LÉGITIMES : sinistralité
# PASSÉE (N-1, antécédents), connue au moment de la souscription d'un contrat
# neuf — par opposition à la sinistralité de la PÉRIODE OBSERVÉE que la
# cible cherche à prédire. C'est la même distinction actuarielle que celle
# qui fonde le bonus-malus. Élargir 'sinistre'/'cout_' en racines (ci-dessus)
# sans cette liste d'exceptions aurait exclu à tort ces variables — c'est
# le faux positif identifié par l'audit V9 (constat 4.4).
# Toute nouvelle variable d'expérience passée (ex. futurs agents A7+
# provisionnement) doit être ajoutée ici explicitement plutôt que de relâcher
# une racine — préserve la traçabilité ACPR de ce qui est autorisé et
# pourquoi.
COLS_FAMILLE_CIBLE_EXCEPTIONS = [
    'antecedents_sinistres_n1',   # variable réelle produite par A2 (l.1183+)
    'nb_sinistres_anterieurs',    # nom plausible côté client — même sémantique
    'antecedents_sinistres_3ans', # facteur central RC Pro, déclaré par A3
    # ⚠ Ces variables portent sur la sinistralité PASSÉE (N-1, 3 dernières
    # années), connue au moment de souscrire un contrat neuf — par opposition à
    # la sinistralité de la PÉRIODE OBSERVÉE que la cible cherche à prédire.
    # C'est la distinction actuarielle qui fonde le bonus-malus et toute la
    # tarification d'expérience. Les exclure serait un contresens : ce ne sont
    # pas des fuites, ce sont les meilleurs prédicteurs légitimes disponibles.
]


# ── Marqueurs d'EXPÉRIENCE PASSÉE ────────────────────────────────────────────
# Trouvé par relecture (auto-audit, 11/07/2026) — MIROIR EXACT DU BLOQUANT B5.
# COLS_FAMILLE_CIBLE_EXCEPTIONS était une LISTE DE NOMS EXACTS : seuls trois noms
# étaient exemptés. Toute autre variable d'expérience passée était donc DÉTRUITE
# comme si c'était une fuite :
#   cout_total_sinistres_anterieurs · charge_sinistres_n1 · nb_sinistres_passes
#   historique_sinistres_3ans · montant_sinistres_anterieurs · sinistres_anterieurs_5ans
# Et pire que B5 : leur motif d'exclusion aurait été « dérivée de sinistralité —
# exclusion OBLIGATOIRE, aucune action », donc l'actuaire n'aurait même pas été
# invité à réagir. Une amputation silencieuse ET présentée comme normale.
#
# C'est, une fois de plus, la maladie de ce module : une liste de noms exacts ne
# peut pas être exhaustive. On la remplace par une RÈGLE DE PRINCIPE — la
# distinction actuarielle qui fonde toute la tarification d'expérience :
#
#     sinistralité de la PÉRIODE OBSERVÉE  → c'est la cible → FUITE
#     sinistralité PASSÉE (N-1, antécédents) → connue à la souscription → LÉGITIME
#
# Un nom portant un marqueur de passé désigne la seconde. Et si une variable
# ainsi nommée se révélait tout de même être la cible déguisée, le CONTRÔLE PAR
# L'EFFET la rattraperait (corrélation ≥ 0,80) : la règle de nom donne le sens,
# l'effet donne la vérité.
MARQUEURS_EXPERIENCE_PASSEE = (
    'anterieur', 'antecedent', 'historique', 'precedent',
    '_passe', '_n1', '_n2', '_n3', '_3ans', '_5ans',
)


def _est_experience_passee(nom: str) -> bool:
    """True si le nom désigne de la sinistralité PASSÉE (connue à la
    souscription d'un contrat neuf) et non celle de la période observée."""
    n = nom.lower()
    return any(m in n for m in MARQUEURS_EXPERIENCE_PASSEE)


def _est_derivee_sinistralite(nom: str) -> bool:
    """True si le nom de colonne est une grandeur dérivée de la sinistralité
    de la PÉRIODE OBSERVÉE (famille cible), y compris ses variantes
    log_/_obs/_annuel. Les variables d'expérience passée explicitement
    listées dans COLS_FAMILLE_CIBLE_EXCEPTIONS sont préservées.

    ⚠ CORRECTIONS (audit V10, 11/07/2026) :
    · INSENSIBILITÉ À LA CASSE. La comparaison était sensible à la casse, là où
      filtrer_genre ne l'était pas : 'MONTANT_SINISTRES' (majuscules — cas
      courant dans les extractions SI mainframe) passait le filtre. Asymétrie
      corrigée : les deux filtres se comportent désormais de la même façon.
    · INTERACTIONS AVEC L'EXPÉRIENCE PASSÉE. A2 génère des interactions du type
      'inter_bonus_malus_antecedents_sinistres_n1' — parfaitement légitimes
      (la sinistralité N-1 est connue à la souscription : c'est le fondement du
      bonus-malus). Elles étaient exclues à tort parce que la racine 'sinistre'
      y apparaît. On neutralise les noms d'exceptions AVANT de chercher les
      racines de sinistralité observée.
    """
    n = nom.lower()
    # ── RÈGLE DE PRINCIPE : la sinistralité PASSÉE n'est pas une fuite ────────
    # (voir MARQUEURS_EXPERIENCE_PASSEE ci-dessus — remplace l'ancienne liste de
    #  noms exacts, qui détruisait 6 variables légitimes sur les 9 testées).
    # Le contrôle par l'EFFET reste le filet : si une variable ainsi nommée est
    # en réalité la cible déguisée, sa corrélation la trahira.
    if _est_experience_passee(n):
        return False
    exceptions = [e.lower() for e in COLS_FAMILLE_CIBLE_EXCEPTIONS]
    if n in exceptions:
        return False
    reste = n
    for e in exceptions:
        reste = reste.replace(e, '')
    base = n[4:] if n.startswith('log_') else n
    if (base in [c.lower() for c in COLS_FAMILLE_CIBLE]
            or n in [c.lower() for c in COLS_FAMILLE_CIBLE]):
        return True
    return any(stem in reste for stem in COLS_FAMILLE_CIBLE_STEMS)


def filtrer_famille_cible(
    feature_names: List[str],
    contexte: str = '',
    logger_agent: Optional[logging.Logger] = None,
) -> List[str]:
    """
    Retire de la liste de features toute grandeur dérivée de la sinistralité
    observée (prime_pure, cout_total_sinistres, nb_sinistres, et variantes) —
    prévention du data leakage (audit V8).

    À appeler par tout agent qui construit une matrice X à partir des colonnes
    d'un DataFrame preprocessé (A4, A5, walk-forward d'A6). N'affecte JAMAIS la
    variable cible, qui est lue séparément via df[col_cible].

    Retourne la liste filtrée (nouvel objet, ne modifie pas l'original).
    """
    _log = logger_agent or logger
    apres = [f for f in feature_names if not _est_derivee_sinistralite(f)]
    supprimees = set(feature_names) - set(apres)
    if supprimees:
        _log.warning(
            f"[CONFORMITE REGLEMENTAIRE] Variable(s) {sorted(supprimees)} "
            f"exclue(s) de la sélection de features — grandeur(s) dérivée(s) "
            f"de la sinistralité (prévention data leakage)"
            f"{' (' + contexte + ')' if contexte else ''}."
        )
    return apres


# ══════════════════════════════════════════════════════════════════════════════
#  LISTE BLANCHE — LE GARDE-FOU STRUCTUREL
# ══════════════════════════════════════════════════════════════════════════════
# Pourquoi une liste blanche EN PLUS des deux listes noires ci-dessus :
#
# Les listes noires (genre, famille cible) ne peuvent PAS être exhaustives, et
# l'historique le prouve à chaque cycle : chaque audit trouve de nouveaux noms
# qui passent au travers. Audit interne du 11/07/2026, sur des noms de colonnes
# parfaitement réalistes dans un fichier client d'assureur :
#   · sinistralité NON capturée par la liste noire : loss_ratio, taux_S_sur_P,
#     ratio_sp, frequence_observee, severite_observee, charge_totale,
#     montant_regle, indemnite_versee, provision_dossier, burning_cost,
#     sinistralite_n  → 11 fuites potentielles.
#   · proxys de genre NON capturés : prenom, titre, madame, mr_mme, is_male,
#     homme_femme, f_h  → 7 variables prohibées potentielles.
# Chaque correctif de liste noire n'a fait que déplacer la frontière.
#
# La liste blanche inverse la charge de la preuve : une colonne n'entre dans la
# matrice X que si elle est DÉCLARÉE comme facteur tarifaire légitime. Tout ce
# qui est inconnu est exclu PAR DÉFAUT (fail-safe) et JOURNALISÉ (transparence :
# l'actuaire voit ce qui a été écarté et peut déclarer une variable manquante).
#
# Les deux listes noires sont CONSERVÉES en défense en profondeur : une variable
# qui passerait la liste blanche (ex. par un préfixe partagé) reste bloquée si
# elle est genrée ou dérivée de la sinistralité.

# Facteurs tarifaires légitimes — Direction Non-Vie (auto · MRH · RC Pro).
# Toute direction qui utilisera ce module devra déclarer ses propres facteurs.
FACTEURS_TARIFAIRES_AUTORISES = {
    # ── Communs ───────────────────────────────────────────────────────────────
    'age', 'csp', 'zone_geographique', 'densite_population',
    'milieu_geographique', 'region', 'departement', 'code_postal',
    'latitude', 'longitude',
    'anciennete_client', 'anciennete_contrat', 'nb_contrats',
    'fractionnement', 'mode_paiement', 'canal_distribution',
    # Exposition / offset (jamais prédicteur, mais doit traverser les filtres)
    'exposition', 'log_exposition',
    # Expérience PASSÉE — légitime (connue à la souscription : fonde le B/M)
    'antecedents_sinistres_n1', 'nb_sinistres_anterieurs', 'risque_historique',
    'antecedents_sinistres_3ans',
    # ⚠ 'antecedents_sinistres_3ans' ajouté le 11/07/2026 (audit V11, BLOQUANT
    # B5). C'est LE facteur tarifaire central de la RC Pro (β = +0,43,
    # p = 7,8e-24, relativité 1,536 par sinistre antérieur), et il est DÉCLARÉ
    # par A3 lui-même dans VARS_GLM['rcpro'] — mais il était absent de cette
    # liste blanche, donc détruit en silence : −17,4 % de pouvoir discriminant
    # du GLM RC Pro. Comme 'antecedents_sinistres_n1', il porte sur la
    # sinistralité PASSÉE (3 dernières années, connue à la souscription) : ce
    # n'est pas une fuite, c'est le fondement même de la tarification
    # d'expérience. Il figure aussi à ce titre dans
    # COLS_FAMILLE_CIBLE_EXCEPTIONS.
    # ── Auto ──────────────────────────────────────────────────────────────────
    'bonus_malus', 'coefficient_reduction_majoration', 'anciennete_permis',
    'puissance_fiscale', 'puissance', 'valeur_venale', 'kilometrage_annuel',
    'age_vehicule', 'annee_mise_circulation', 'carburant', 'marque_vehicule',
    'modele_vehicule', 'usage', 'garantie', 'type_conduite', 'parking',
    # ── MRH ───────────────────────────────────────────────────────────────────
    'surface_m2', 'type_logement', 'statut_occupation', 'etage', 'nb_pieces',
    'annee_construction', 'alarme', 'capital_assure_biens_eur',
    'age_logement', 'dependances',
    'double_vitrage', 'garantie_vol',   # déclarés par VARS_GLM['mrh'] (audit V11)
    # ── RC Pro ────────────────────────────────────────────────────────────────
    'ca_annuel_eur', 'nb_salaries', 'secteur_activite', 'forme_juridique',
    'anciennete_entreprise_ans', 'type_garantie', 'effectif',
    # ── Indicateurs DÉRIVÉS générés par A2 (_feature_engineering) ─────────────
    # Recensés exhaustivement sur le code d'A2 au 11/07/2026. Ils dérivent tous
    # d'un facteur autorisé ci-dessus (age, age_vehicule, kilometrage, surface...)
    # mais leur nom ne permet pas de le déduire mécaniquement — ils doivent donc
    # être déclarés. ⚠ Tout NOUVEAU dérivé ajouté à A2 devra être déclaré ici,
    # sans quoi il sera écarté de la matrice X (et journalisé : le WARNING de
    # selectionner_features_autorisees le rendra visible immédiatement).
    'jeune_conducteur', 'senior_conducteur',
    'vehicule_recent', 'vehicule_ancien',
    'logement_ancien', 'valeur_mobilier', 'valeur_par_m2',
    'km_par_an_normalise',
}

# Préfixes de features DÉRIVÉES générées par A2 à partir d'un facteur autorisé.
# Une dérivée n'est acceptée que si sa BASE est elle-même autorisée (ex.
# 'age_carre' ← 'age' ; 'carburant_diesel' ← 'carburant' ; 'zone_geographique_enc'
# ← 'zone_geographique'). Cela évite de devoir déclarer chaque nom généré.
PREFIXES_DERIVEES = ('log_', 'inter_')
SUFFIXES_DERIVEES = ('_enc', '_carre', '_log')


def _base_facteur(nom: str) -> str:
    """Ramène une feature dérivée à son facteur de base présumé."""
    n = nom.lower()
    for p in PREFIXES_DERIVEES:
        if n.startswith(p):
            n = n[len(p):]
    for s in SUFFIXES_DERIVEES:
        if n.endswith(s):
            n = n[: -len(s)]
    return n


# Mots qui désignent une GRANDEUR MONÉTAIRE ou de SINISTRALITÉ, jamais une
# modalité de facteur tarifaire. Ajoutés après le BLOQUANT B6 (audit V12) :
# la règle de préfixe ci-dessous acceptait N'IMPORTE QUEL suffixe derrière un
# facteur autorisé, si bien que 'garantie_montant_regle' (le montant réglé au
# titre de la garantie — colonne standard d'une extraction jointe aux sinistres)
# passait la liste blanche, 'garantie' étant un facteur légitime.
# Gini 0,0709 → 0,9222.
# Une colonne fille de one-hot porte une MODALITÉ ('carburant_diesel',
# 'type_logement_maison', 'statut_occupation_locataire') — jamais un montant.
MOTS_METRIQUES_INTERDITS = (
    'montant', 'cout', 'charge', 'sinistre', 'sinistralite', 'ratio', 'loss',
    'burning', 'prime', 'indemnite', 'provision', 'regle', 'frequence',
    'severite', 'perte',
)


def est_facteur_autorise(nom: str) -> bool:
    """
    True si la colonne est (ou dérive d')un facteur tarifaire déclaré légitime.

    Accepte :
      · le facteur lui-même            ('age', 'bonus_malus')
      · ses dérivées connues           ('age_carre', 'log_exposition')
      · ses colonnes filles one-hot    ('carburant_diesel' ← 'carburant')
      · les interactions entre facteurs autorisés ('inter_age_bonus_malus')
      · les indicateurs binaires dérivés ('jeune_conducteur' ← déclaré)

    ⚠ LIMITE CONNUE, ET C'EST IMPORTANT DE L'ÉCRIRE : la règle de préfixe
    (facteur autorisé + '_' + suffixe) ne peut pas, par le seul nom, distinguer
    une MODALITÉ de one-hot ('carburant_diesel') d'une grandeur arbitraire
    ('garantie_montant_regle'). C'est ce qui a produit le BLOQUANT B6 (V12).
    Deux garde-fous s'y ajoutent donc :
      1. le suffixe ne doit contenir aucun MOT MÉTRIQUE (montant, coût, charge,
         sinistre, ratio…) — une modalité n'est jamais un montant ;
      2. surtout, le CONTRÔLE PAR L'EFFET (detecter_fuites_par_effet), qui ne
         dépend d'aucun nom et rattrape ce que celui-ci ne peut pas trancher.
    Le nom ne suffit pas et ne suffira jamais : il donne le sens, pas la vérité.
    """
    n = nom.lower()
    if n in FACTEURS_TARIFAIRES_AUTORISES:
        return True
    base = _base_facteur(n)
    if base in FACTEURS_TARIFAIRES_AUTORISES:
        return True
    # Interaction : 'inter_a_b' / 'a_x_b' — autorisée si TOUS les facteurs
    # qui la composent sont eux-mêmes autorisés.
    # ⚠ BUG LATENT trouvé en relecture (11/07/2026) : la condition testait
    # `base.startswith('inter_')`, or _base_facteur() a DÉJÀ retiré le préfixe
    # 'inter_'. Cette branche était donc MORTE pour tous les noms 'inter_*' —
    # ils ne passaient que par hasard, via la règle de préfixe plus bas. On teste
    # désormais le nom d'origine.
    if n.startswith('inter_') or '_x_' in base:
        corps = base
        for f1 in FACTEURS_TARIFAIRES_AUTORISES:
            if corps.startswith(f1):
                reste = corps[len(f1):].lstrip('_').replace('x_', '', 1).lstrip('_')
                if reste in FACTEURS_TARIFAIRES_AUTORISES:
                    return True
    # Colonne fille d'un one-hot / label : 'carburant_diesel' ← 'carburant'.
    # On exige que le facteur autorisé soit un préfixe SUIVI d'un '_' pour
    # éviter les collisions accidentelles ('agent_...' ne dérive pas de 'age') —
    # ET que le suffixe soit une MODALITÉ plausible, c'est-à-dire qu'il ne porte
    # aucun mot métrique (BLOQUANT B6 : 'garantie_montant_regle' passait ici).
    for f in FACTEURS_TARIFAIRES_AUTORISES:
        if base.startswith(f + '_'):
            suffixe = base[len(f) + 1:]
            # ⚠ Ne PAS frapper l'expérience PASSÉE : 'bonus_malus_antecedents_
            # sinistres_n1' (interaction légitime générée par A2) a un suffixe
            # contenant 'sinistre'. Le rejeter recréerait exactement le BLOQUANT
            # B5 — c'est ce qu'a fait ma première version, et l'invariant INV-1c
            # l'a attrapée immédiatement.
            if (any(m in suffixe for m in MOTS_METRIQUES_INTERDITS)
                    and not _est_experience_passee(suffixe)):
                continue   # 'garantie_montant_regle' → suffixe 'montant_regle'
            return True
    return False


def selectionner_features_autorisees(
    feature_names: List[str],
    contexte: str = '',
    logger_agent: Optional[logging.Logger] = None,
    facteurs_supplementaires: Optional[List[str]] = None,
) -> List[str]:
    """
    LISTE BLANCHE — ne conserve que les facteurs tarifaires déclarés légitimes.

    Toute colonne inconnue est EXCLUE par défaut (fail-safe) et JOURNALISÉE en
    WARNING (transparence ACPR : l'actuaire voit exactement ce qui a été écarté
    et peut déclarer une variable manquante via `facteurs_supplementaires` ou en
    l'ajoutant à FACTEURS_TARIFAIRES_AUTORISES).

    À utiliser en PREMIER, avant filtrer_genre / filtrer_famille_cible, qui
    restent appliqués ensuite en défense en profondeur.

    Paramètres
    ----------
    facteurs_supplementaires : facteurs propres à un portefeuille client,
        déclarés explicitement par l'actuaire. Étend la liste blanche pour cet
        appel uniquement (ne modifie pas la source de vérité).
    """
    _log = logger_agent or logger
    autorises_extra = {f.lower() for f in (facteurs_supplementaires or [])}
    apres = [
        f for f in feature_names
        if est_facteur_autorise(f) or f.lower() in autorises_extra
    ]
    exclues = [f for f in feature_names if f not in apres]
    if exclues:
        _log.warning(
            f"[CONFORMITE REGLEMENTAIRE — LISTE BLANCHE] "
            f"{len(exclues)} colonne(s) NON déclarée(s) comme facteur tarifaire "
            f"légitime, exclue(s) de la matrice X par défaut (fail-safe) : "
            f"{sorted(exclues)}"
            f"{' (' + contexte + ')' if contexte else ''}. "
            f"Si l'une d'elles est un facteur tarifaire valide, la déclarer "
            f"dans FACTEURS_TARIFAIRES_AUTORISES (core/conformite_reglementaire.py) "
            f"ou via le paramètre facteurs_supplementaires."
        )
    return apres


def filtrer_features(
    feature_names: List[str],
    contexte: str = '',
    logger_agent: Optional[logging.Logger] = None,
    facteurs_supplementaires: Optional[List[str]] = None,
) -> List[str]:
    """
    POINT D'ENTRÉE UNIQUE de la conformité sur une liste de features.

    Enchaîne les trois garde-fous, dans cet ordre :
      1. LISTE BLANCHE  — seuls les facteurs tarifaires déclarés passent ;
      2. filtrer_genre  — défense en profondeur (CJUE C-236/09) ;
      3. filtrer_famille_cible — défense en profondeur (anti data leakage).

    Tout agent de TOUTE direction construisant une matrice X doit appeler
    cette fonction — et elle seule.

    ⚠ À APPELER AU DERNIER MOMENT POSSIBLE, sur la liste effectivement utilisée
    pour construire la matrice X — jamais sur une liste intermédiaire qu'un code
    ultérieur pourrait enrichir. L'audit V10 a démontré (BLOQUANT B1) qu'un
    filtre appliqué à une liste intermédiaire peut être intégralement contourné
    vingt lignes plus bas.
    """
    f = selectionner_features_autorisees(
        feature_names, contexte=contexte, logger_agent=logger_agent,
        facteurs_supplementaires=facteurs_supplementaires,
    )
    f = filtrer_genre(f, contexte=contexte, logger_agent=logger_agent)
    f = filtrer_famille_cible(f, contexte=contexte, logger_agent=logger_agent)
    return f


# ══════════════════════════════════════════════════════════════════════════════
#  PORTÉE DE LA VALIDATION TEMPORELLE — source unique pour TOUS les livrables
# ══════════════════════════════════════════════════════════════════════════════
# Créé le 11/07/2026 (audit V11). Le correctif de l'audit V10 (BLOQUANT B3) —
# avertir l'actuaire quand le walk-forward n'a pas porté sur le modèle de
# production — n'avait été appliqué qu'à l'export Excel d'A6. Word, HTML et le
# rapport d'équipe continuaient d'afficher la chaîne brute « GLM → proxy GBM »
# sans le moindre avertissement : le motif « corrigé à un endroit, non propagé
# ailleurs » se reproduisait pour la SIXIÈME fois.
#
# Remède structurel : une SEULE fonction dit la vérité sur la portée de la
# validation temporelle, et TOUS les livrables l'appellent. Il devient impossible
# qu'un format de rapport diverge des autres — ou du gate de certification.

def avertissement_walk_forward(backtest: Optional[dict]) -> Optional[str]:
    """
    Retourne l'avertissement à afficher dans TOUT livrable (Excel, Word, HTML,
    rapport d'équipe, prompt de narration) lorsque la validation temporelle ne
    vaut PAS validation du modèle de production — ou None s'il n'y a rien à
    signaler.

    Trois situations distinctes, trois messages :
      · backtest indisponible          → aucune validation temporelle du tout ;
      · recalibration sur proxy        → validation d'un AUTRE modèle ;
      · résultat insuffisant           → validation menée, mais échouée.

    ⚠ Ne JAMAIS déduire le statut d'un livrable de la véracité (truthiness) du
    champ 'modele_recalibre' : c'est une CHAÎNE, et « GLM → proxy GBM (...) »
    est truthy. C'était le BLOQUANT B3 de l'audit V10 : l'Excel estampillait
    « ✓ Conforme » en VERT sur la ligne annonçant une recalibration sur proxy.
    """
    bt = backtest or {}

    if not bt.get('disponible', False):
        return (
            "⚠ AUCUNE VALIDATION TEMPORELLE — le backtesting walk-forward n'a "
            "pas pu être exécuté. La stabilité du modèle dans le temps n'est "
            f"PAS établie. Motif : {bt.get('note', 'non renseigné')}."
        )

    if not bt.get('modele_recalibre_fidele', False):
        return (
            "⚠ PORTÉE DE LA VALIDATION TEMPORELLE — la recalibration "
            "walk-forward n'a PAS porté sur le modèle de production "
            f"({bt.get('modele_recalibre', 'proxy')}) : la stabilité temporelle "
            "mesurée est celle d'un AUTRE modèle. Ne vaut pas validation du "
            "modèle retenu."
        )

    gini_wf = bt.get('gini_wf_moyen')
    ae      = bt.get('ae_ratio')
    ae_moy  = bt.get('ae_moyen_wf')
    n_rouge = bt.get('n_fenetres_rouge', 0) or 0
    stab    = str(bt.get('stabilite_wf', ''))
    if gini_wf is None:
        return ("⚠ VALIDATION TEMPORELLE SANS RÉSULTAT — le walk-forward a "
                "tourné mais n'a produit aucune métrique de discrimination "
                "(Gini indisponible). Il ne valide rien.")
    if ae is None or not (0.90 <= float(ae) <= 1.10):
        return (f"⚠ BIAIS DE TARIFICATION — A/E walk-forward = {ae}, hors de la "
                f"bande acceptable [0,90 ; 1,10]. Le modèle sur- ou "
                f"sous-tarifie systématiquement hors échantillon.")
    # ⚠ 'ae_ratio' ne porte que sur la DERNIÈRE fenêtre. Un modèle peut avoir
    # échoué plusieurs exercices et rester acceptable sur la dernière année :
    # ces deux critères lisent TOUTES les fenêtres (audit V11).
    if n_rouge > 0:
        return (f"⚠ ÉCHEC SUR {n_rouge} EXERCICE(S) — {n_rouge} fenêtre(s) "
                f"walk-forward en ROUGE. Le modèle a échoué la validation "
                f"temporelle sur au moins un exercice passé, même si la dernière "
                f"année est satisfaisante.")
    if ae_moy is not None and not (0.90 <= float(ae_moy) <= 1.10):
        return (f"⚠ BIAIS PERSISTANT — A/E moyen sur toutes les fenêtres = "
                f"{ae_moy}, hors bande acceptable [0,90 ; 1,10].")
    if '🔴' in stab:
        return (f"⚠ INSTABILITÉ TEMPORELLE — stabilité inter-fenêtres : {stab}. "
                f"Les performances du modèle varient fortement d'un exercice à "
                f"l'autre.")
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  MatriceX — RENDRE LE CONTOURNEMENT IMPOSSIBLE, PAS SEULEMENT INTERDIT
# ══════════════════════════════════════════════════════════════════════════════
# Créé le 11/07/2026, sur recommandation du certificateur indépendant (audit V10).
#
# LE PROBLÈME QUE CELA RÉSOUT
# Six cycles d'audit ont produit six variantes du MÊME défaut : le filtre de
# conformité est correct, et il est contourné ailleurs.
#   · V7  — filtre présent dans A3, absent d'A4/A5.
#   · V8  — filtre absent du walk-forward d'A6.
#   · V9  — filtre contourné par le one-hot, puis par l'encodage automatique.
#   · V10 — filtre appelé dans A3, puis NEUTRALISÉ vingt lignes plus bas par un
#           bloc qui réinjectait les colonnes *_enc dans la liste déjà filtrée.
#           Résultat : le GLM tarifait la civilité (37,9 % d'écart H/F).
#
# Tant que `filtrer_features()` reste UNE FONCTION QU'ON PEUT OUBLIER D'APPELER
# — ou dont on peut modifier le résultat après coup — un septième chemin
# apparaîtra. Le certificateur l'a écrit sans détour : « rends le contournement
# impossible ».
#
# LA SOLUTION
# Une liste de features conforme n'est plus une `list` que n'importe quel code
# peut enrichir : c'est un objet MatriceX
#   · INSTANCIABLE UNIQUEMENT par ce module (jeton privé) — un agent ne peut pas
#     en fabriquer une sans passer par le filtre ;
#   · IMMUABLE (tuple) — `vars_pred.extend(colonnes_brutes)` lève désormais une
#     AttributeError au lieu de rouvrir silencieusement une faille. Le BLOQUANT
#     B1 de l'audit V10 aurait été impossible à écrire.
#   · TRAÇANTE — elle transporte la liste des colonnes exclues et pourquoi, ce
#     qui permet aux rapports d'en informer l'actuaire. C'est la réponse au
#     silence qui a rendu le BLOQUANT B5 si coûteux : `antecedents_sinistres_3ans`
#     (le facteur central de la RC Pro) était détruit sans que rien ne l'indique
#     dans aucun livrable.

_JETON = object()   # sentinelle de module — non exposée sur la classe (audit V12/I6)


class MatriceX:
    """
    Liste de features CERTIFIÉE CONFORME, immuable.

    Ne peut pas être construite directement : passer par `construire_matrice_x()`,
    qui applique liste blanche → filtre genre → filtre anti-fuite.

        mx = construire_matrice_x(df.columns, contexte='A3 — GLM')
        X  = df[list(mx)]           # itérable, indexable
        mx.exclusions                # ce qui a été écarté, et pourquoi

    Toute tentative de modification après construction échoue — c'est le but.
    """
    __slots__ = ('_features', '_exclusions', '_contexte', '_alertes',
                 '_controle_effet_execute')

    def __init__(self, features, exclusions, contexte, _jeton=None, alertes=None,
                 controle_effet_execute=True):
        # ⚠ AUDIT V12 (I6) — le jeton était un ATTRIBUT DE CLASSE public
        # (MatriceX._JETON), et la docstring affirmait « seul ce module y a
        # accès ». C'ÉTAIT FAUX : MatriceX([...], _jeton=MatriceX._JETON)
        # fonctionnait parfaitement. Le jeton est désormais une sentinelle de
        # MODULE, non exposée sur la classe.
        #
        # HONNÊTETÉ SUR LA PORTÉE DE CETTE PROTECTION : Python n'offre pas de
        # privé strict. Quelqu'un qui importe _JETON depuis ce module peut
        # toujours forger une MatriceX. Ce garde-fou ne rend pas le
        # contournement IMPOSSIBLE — il le rend DÉLIBÉRÉ, VISIBLE en revue de
        # code, et impossible par accident. C'est tout ce qu'un langage
        # dynamique permet, et il faut le dire plutôt que le prétendre.
        # La défense qui, elle, ne se contourne pas est le contrôle par l'EFFET
        # (detecter_fuites_par_effet) : il ne dépend d'aucune convention.
        if _jeton is not _JETON:
            raise TypeError(
                "MatriceX ne peut pas être instanciée directement — c'est "
                "délibéré. Utilisez core.conformite_reglementaire."
                "construire_matrice_x(), qui applique les filtres de conformité "
                "(CJUE C-236/09 · anti data leakage). Contourner ce point de "
                "passage a produit six anomalies bloquantes en six cycles d'audit."
            )
        object.__setattr__(self, '_features', tuple(features))
        object.__setattr__(self, '_exclusions', dict(exclusions))
        object.__setattr__(self, '_contexte', contexte)
        object.__setattr__(self, '_alertes', dict(alertes or {}))
        object.__setattr__(self, '_controle_effet_execute',
                           bool(controle_effet_execute))

    # ── Lecture seule ────────────────────────────────────────────────────────
    @property
    def features(self):
        """Tuple des features conformes (immuable — .extend() n'existe pas)."""
        return self._features

    @property
    def exclusions(self):
        """{colonne: motif} — ce qui a été écarté et pourquoi. À REMONTER DANS
        LES RAPPORTS : une exclusion silencieuse est un défaut en soi (V11/B5)."""
        return dict(self._exclusions)

    @property
    def alertes(self):
        """{colonne: signal} — variables d'expérience PASSÉE CONSERVÉES malgré un
        signal fort. À REMONTER DANS LES RAPPORTS : ce n'est pas une exclusion,
        c'est une VÉRIFICATION demandée à l'actuaire (la variable porte-t-elle
        bien sur le passé, ou est-elle mal étiquetée ?).
        Constat I5 : ce qui n'est que dans les logs n'existe pas."""
        return dict(self._alertes)

    @property
    def controle_effet_execute(self):
        """Le garde-fou n°4 (contrôle par l'effet — le SEUL indépendant des noms)
        a-t-il réellement tourné ? Faux si df/col_cible n'ont pas été fournis.

        ⚠ À REMONTER DANS LES RAPPORTS (I7, audit V14) : le WARNING existait dans
        les logs, mais l'objet n'en portait aucune trace — donc rien n'atteignait
        l'actuaire. Or ce module écrit lui-même : « ce qui n'est que dans les logs
        n'existe pas ». Une matrice X construite sans ce contrôle n'offre que des
        garde-fous par le NOM, structurellement insuffisants (audit V12)."""
        return self._controle_effet_execute

    @property
    def contexte(self):
        return self._contexte

    def __iter__(self):     return iter(self._features)
    def __len__(self):      return len(self._features)
    def __contains__(self, x): return x in self._features
    def __getitem__(self, i):  return self._features[i]
    def __repr__(self):
        return (f"MatriceX({len(self._features)} features conformes, "
                f"{len(self._exclusions)} exclues — {self._contexte})")

    # ── Immuabilité stricte ──────────────────────────────────────────────────
    def __setattr__(self, *a):
        raise AttributeError(
            "MatriceX est immuable. Ajouter une colonne à une matrice déjà "
            "filtrée est précisément le BLOQUANT B1 de l'audit V10 (le GLM "
            "tarifait la civilité). Reconstruire via construire_matrice_x()."
        )
    __delattr__ = __setattr__


def construire_matrice_x(
    colonnes,
    contexte: str = '',
    logger_agent: Optional[logging.Logger] = None,
    facteurs_supplementaires: Optional[List[str]] = None,
    df=None,
    col_cible=None,
    plan=None,
) -> MatriceX:
    """
    SEUL point de construction d'une matrice de features conforme.

    QUATRE garde-fous, dont le dernier ne dépend d'aucun nom :
      1. LISTE BLANCHE           — seuls les facteurs déclarés passent ;
      2. FILTRE GENRE            — CJUE C-236/09 ;
      3. FILTRE ANTI-FUITE       — grandeurs de sinistralité (par le nom) ;
      4. CONTRÔLE PAR L'EFFET    — corrélation avec la cible ≥ 0,80 → fuite,
                                   QUEL QUE SOIT LE NOM (audit V12).

    ── LISTE BLANCHE DÉCLARATIVE (étape 4 du plan d'exécution) ──────────────
    Si `plan` (un PlanTarifaire signé) est fourni, la liste blanche n'est plus
    une constante codée (FACTEURS_TARIFAIRES_AUTORISES) mais « déclaré dans le
    plan signé » : `c in plan.colonnes_produites()`. Et les exemptions du
    contrôle par l'effet deviennent `plan.facteurs_anteriorite()` — plus de
    devinette. Les garde-fous 2·3·4 restent INCHANGÉS et NON contournables par
    le plan : un actuaire qui déclarerait `sexe` (INV-3) ou `prime_pure` (INV-4)
    est quand même bloqué. Le plan AUTORISE, il ne DISPENSE pas.

    Sans `plan`, on conserve le comportement historique (liste blanche codée +
    facteurs_supplementaires) pour les appelants non encore migrés.

    ⚠ FOURNIR `df` ET `col_cible` DÈS QUE POSSIBLE. Sans eux, le garde-fou n°4
    ne peut pas s'exécuter, et seuls les contrôles par le nom protègent — or
    l'audit V12 a démontré qu'ils sont structurellement insuffisants :
    'garantie_montant_regle' (le montant réglé au titre de la garantie, colonne
    standard d'une extraction jointe aux sinistres) traversait les trois filtres
    nominaux via le préfixe 'garantie_' et faisait passer le Gini de 0,0709 à
    0,9222. Le contrôle par l'effet, lui, l'attrape sans connaître son nom.

    ⚠ À appeler au DERNIER MOMENT, sur les colonnes effectivement candidates.
    """
    candidates = [str(c) for c in colonnes]

    # ── ① LISTE BLANCHE + ② GENRE + ③ FUITE PAR LE NOM ────────────────────────
    _log = logger_agent or logger
    declarees = None
    cols_exemptees_effet = None
    if plan is not None:
        # DÉCLARATIVE : n'est légitime que ce que le plan SIGNÉ annonce. Les
        # garde-fous 2·3 restent appliqués — non contournables par le plan.
        declarees = set(plan.colonnes_produites())
        cols_exemptees_effet = list(plan.facteurs_anteriorite())
        conformes = [c for c in candidates if c in declarees]
        conformes = filtrer_genre(conformes, contexte=contexte,
                                  logger_agent=logger_agent)             # ② INV-3
        conformes = filtrer_famille_cible(conformes, contexte=contexte,
                                          logger_agent=logger_agent)     # ③ (par le nom)
    else:
        # Rétrocompat : liste blanche codée + facteurs_supplementaires. Chemin
        # des appelants (A3/A4/A5/A6) non encore migrés vers le plan déclaratif.
        conformes = filtrer_features(
            candidates, contexte=contexte, logger_agent=logger_agent,
            facteurs_supplementaires=facteurs_supplementaires,
        )

    # ── GARDE-FOU N°4 : CONTRÔLE PAR L'EFFET (audit V12) ──────────────────────
    # `col_cible` accepte UNE cible (str) ou PLUSIEURS (liste) : le GLM d'A3 en a
    # deux (fréquence ET coût moyen), et une fuite peut viser l'une ou l'autre.
    # Un SEUL appel suffit donc — le point de passage reste unique.
    fuites_effet = {}
    alertes_experience = {}
    cibles = ([col_cible] if isinstance(col_cible, str)
              else list(col_cible or []))

    controle_effet_execute = not (df is None or not cibles)
    if df is None or not cibles:
        # ⚠ LE GARDE-FOU NE DOIT JAMAIS SE DÉSACTIVER EN SILENCE.
        # `df` et `col_cible` sont techniquement optionnels — un agent peut donc
        # les omettre, et le contrôle par l'effet (le SEUL qui ne dépende d'aucun
        # nom de colonne) ne tourne alors PAS. Sans cet avertissement, cette
        # désactivation serait indiscernable d'un contrôle qui n'a rien trouvé :
        # c'est très exactement le motif du bug V6 et du BLOQUANT B2.
        # Un contrôle dont on ne vérifie pas l'exécution n'est pas un contrôle.
        _log.warning(
            f"[ANTI-FUITE PAR L'EFFET — NON EXÉCUTÉ] "
            f"construire_matrice_x() appelée SANS df et/ou SANS col_cible"
            f"{' (' + contexte + ')' if contexte else ''}. Le garde-fou n°4 — le "
            f"seul qui ne dépende d'aucun nom de colonne — N'A PAS TOURNÉ. Seuls "
            f"les contrôles par le nom protègent cette matrice X, et l'audit V12 "
            f"a démontré qu'ils sont structurellement insuffisants "
            f"('garantie_montant_regle' : Gini 0,0709 → 0,9222). "
            f"Fournissez df= et col_cible=."
        )
    else:
        for _cible in cibles:
            f, alertes = detecter_fuites_par_effet(
                df, conformes, _cible, logger_agent=logger_agent,
                cols_exemptees=cols_exemptees_effet,   # plan.facteurs_anteriorite()
                retourner_alertes=True,
            )
            fuites_effet.update(f)
            alertes_experience.update(alertes)
        if fuites_effet:
            conformes = [c for c in conformes if c not in fuites_effet]
    # Motif d'exclusion, par ordre de priorité réglementaire.
    exclusions = {}
    autorises_extra = {f.lower() for f in (facteurs_supplementaires or [])}
    for c in candidates:
        if c in conformes:
            continue
        if c in fuites_effet:
            exclusions[c] = (
                f"FUITE DÉTECTÉE PAR L'EFFET — corrélation de {fuites_effet[c]} "
                f"avec la cible {cibles}. Aucun facteur tarifaire légitime "
                f"n'atteint ce niveau : cette variable EST la cible déguisée, et "
                f"n'existe pas encore au moment de tarifer un contrat neuf."
            )
        elif _est_variable_genre(c):
            exclusions[c] = "genre ou proxy de genre — CJUE C-236/09 (Test-Achats)"
        elif _est_derivee_sinistralite(c):
            exclusions[c] = ("dérivée de la sinistralité observée — fuite de "
                             "données (inconnue au moment de tarifer)")
        elif declarees is not None and c not in declarees:
            exclusions[c] = ("non déclarée dans le plan de tarification signé "
                             "(liste blanche) — à déclarer si elle est valide")
        elif declarees is None and not (est_facteur_autorise(c) or c.lower() in autorises_extra):
            exclusions[c] = ("non déclarée comme facteur tarifaire légitime "
                             "(liste blanche) — à déclarer si elle est valide")
        else:
            exclusions[c] = "exclue par le filtre de conformité"
    return MatriceX(conformes, exclusions, contexte, _jeton=_JETON,
                    alertes=alertes_experience,
                    controle_effet_execute=controle_effet_execute)


def synthese_exclusions(exclusions: Optional[dict]) -> Optional[str]:
    """
    SOURCE UNIQUE — texte à afficher dans TOUT livrable (Excel, Word, HTML,
    rapport d'équipe) pour informer l'actuaire des colonnes écartées de la
    matrice X, et pourquoi. Retourne None s'il n'y a rien à signaler.

    Pourquoi c'est indispensable (audit V11, constat I5) :
    une exclusion SILENCIEUSE est un défaut en soi. Le BLOQUANT B5 l'a démontré
    au prix fort : 'antecedents_sinistres_3ans' — LE facteur tarifaire central
    de la RC Pro (β = +0,43, relativité 1,536) — était détruit par la liste
    blanche, coûtant 17,4 % du pouvoir discriminant du GLM. Aucun rapport ne le
    mentionnait : seul un WARNING de log, que personne ne lit.

    Trois motifs, trois niveaux de gravité pour l'actuaire lecteur :
      · genre / proxy de genre  → exclusion OBLIGATOIRE (CJUE C-236/09). RAS.
      · dérivée de sinistralité → exclusion OBLIGATOIRE (fuite). RAS.
      · non déclarée en liste blanche → ⚠ À VÉRIFIER : si la variable est un
        facteur tarifaire légitime, elle doit être déclarée, sinon le modèle est
        amputé en silence. C'est le seul motif qui appelle une ACTION.
    """
    exc = exclusions or {}
    if not exc:
        return None

    genre = sorted(c for c, m in exc.items() if 'C-236/09' in m)
    fuite = sorted(c for c, m in exc.items() if 'fuite' in m.lower())
    a_verifier = sorted(c for c, m in exc.items() if 'liste blanche' in m)
    autres = sorted(c for c in exc
                    if c not in genre and c not in fuite and c not in a_verifier)

    lignes = []
    if a_verifier:
        lignes.append(
            f"⚠ ACTION REQUISE — {len(a_verifier)} colonne(s) écartée(s) de la "
            f"matrice X car NON DÉCLARÉE(S) comme facteur tarifaire légitime : "
            f"{', '.join(a_verifier)}. Si l'une d'elles est un facteur valide de "
            f"votre portefeuille, le modèle en est amputé — déclarez-la "
            f"(FACTEURS_TARIFAIRES_AUTORISES) et relancez la tarification."
        )
    if genre:
        lignes.append(
            f"✔ {len(genre)} colonne(s) exclue(s) au titre de l'interdiction du "
            f"genre en tarification — CJUE C-236/09 (Test-Achats) : "
            f"{', '.join(genre)}. Exclusion obligatoire, aucune action."
        )
    if fuite:
        lignes.append(
            f"✔ {len(fuite)} colonne(s) exclue(s) comme dérivée(s) de la "
            f"sinistralité observée (fuite de données — inconnues au moment de "
            f"tarifer un contrat neuf) : {', '.join(fuite)}. Exclusion "
            f"obligatoire, aucune action."
        )
    if autres:
        lignes.append(f"· Autres exclusions : {', '.join(autres)}.")
    return "\n".join(lignes)


# ══════════════════════════════════════════════════════════════════════════════
#  CONTRÔLE PAR L'EFFET — LA FIN DE LA COURSE AUX NOMS DE COLONNES
# ══════════════════════════════════════════════════════════════════════════════
# Créé le 11/07/2026, sur recommandation du certificateur indépendant (audit V12).
#
# POURQUOI LES CONTRÔLES PAR LE NOM ONT ÉCHOUÉ — SEPT FOIS
# Chaque cycle a durci une liste de noms, et chaque cycle suivant a trouvé le nom
# qui passait au travers :
#   V7  'sexe' absent d'A4/A5          V9  'sexe_m' (one-hot)
#   V8  'prime_pure'                   V9  'total_sinistres_sante'
#   V10 'titre_enc' (civilité)         V11 'antecedents_sinistres_3ans' (faux positif)
#   V12 'garantie_montant_regle'  ← passe la liste blanche via le préfixe 'garantie_'
#       (le montant réglé au titre de la garantie — colonne parfaitement standard
#        d'une extraction jointe aux sinistres). Gini 0,0709 → 0,9222 (+1201 %).
#
# Une liste noire ne peut pas être exhaustive. Une liste blanche par PRÉFIXE ne
# peut pas l'être non plus : 'garantie' est un facteur légitime, donc
# 'garantie_<n_importe_quoi>' est accepté. Et il FAUT accepter 'carburant_diesel'
# (colonne fille d'un one-hot). Le nom, à lui seul, ne permet pas de trancher.
#
# LA SOLUTION : NE PLUS REGARDER LE NOM, MAIS L'EFFET
# Une variable qui fuite se trahit par sa CORRÉLATION avec la cible — quel que
# soit son nom, y compris celui que personne n'a encore imaginé. Aucun facteur
# tarifaire légitime ne corrèle à 0,80+ avec la sinistralité d'un contrat :
# le bonus-malus, meilleur prédicteur de l'auto, plafonne autour de 0,10-0,30.
# Une corrélation de 0,90 n'est pas un bon modèle : c'est la cible déguisée.
#
# Ce contrôle attrape 'garantie_montant_regle', 'prime_pure', 'loss_ratio' ET
# ceux que personne n'a encore inventés. C'est le seul garde-fou qui ne dépende
# pas de l'imagination de celui qui l'écrit.

SEUIL_CORRELATION_FUITE = 0.80
# DEUX mesures, et on déclenche si l'UNE OU L'AUTRE dépasse le seuil.
#
# 1. Corrélation de SPEARMAN (rangs) — robuste aux relations non linéaires.
#
# 2. GINI NORMALISÉ — indispensable, et voici pourquoi (trouvé en RELECTURE, sur
#    un cas que Spearman RATAIT) :
#    une cible de comptage de sinistres est massivement EX ÆQUO (environ 75 % de
#    zéros en auto). Les rangs de la cible sont donc écrasés, alors que ceux d'une
#    variable continue ne le sont pas — et la corrélation de Spearman s'en trouve
#    mécaniquement DILUÉE. Mesuré : une fuite PARFAITE (la cible plus un bruit
#    infinitésimal) plafonne à rho = 0,55-0,77 sur une cible de Poisson. Autrement
#    dit, le seuil de 0,80 ne pouvait JAMAIS se déclencher sur ce cas — pourtant
#    le plus fréquent en assurance. Erreur de calibration de ma part, corrigée.
#
#    Le Gini normalisé — Gini(y trié par x) divisé par Gini(y trié par y) — mesure
#    la part du pouvoir discriminant MAXIMAL que la variable capte à elle seule.
#    Il est insensible à la structure d'ex aequo, et c'est la métrique actuarielle
#    standard. Mesuré sur les mêmes données :
#         fuites    : 1,00 / 0,99 / 1,00
#         legitimes : 0,03 / 0,04 / 0,05 / 0,10
#    La séparation est nette. Une variable qui capte à elle seule 80 % du pouvoir
#    discriminant maximal n'est pas un facteur tarifaire : c'est la cible.

# Bornes de vraisemblance actuarielle du Gini — Non-Vie.
# Littérature : un GLM de fréquence auto se situe entre 0,15 et 0,35 ; 0,50 est
# déjà exceptionnel. Au-delà de 0,60, l'hypothèse la plus probable n'est pas
# « excellent modèle » mais « fuite de données ». Réf. : le BLOQUANT V8 affichait
# 0,91 ; le BLOQUANT V12, 0,92.
GINI_PLAUSIBLE_MAX_FREQUENCE = 0.60


class EchecControleEffet(RuntimeError):
    """Le contrôle anti-fuite par l'effet n'a pas pu s'exécuter.

    Levée plutôt qu'avalée : ce contrôle est le garde-fou principal contre les
    fuites de données, et le seul qui ne dépende d'aucun nom de colonne. Son
    échec silencieux (return {} = « aucune fuite ») serait indiscernable d'un
    succès — c'est précisément le motif du bug V6. L'appelant doit décider :
    échouer, ou poursuivre en le SIGNALANT. Jamais l'ignorer.
    """


def detecter_fuites_par_effet(
    df,
    feature_names: List[str],
    col_cible: str,
    cols_exemptees: Optional[List[str]] = None,
    seuil: float = SEUIL_CORRELATION_FUITE,
    logger_agent: Optional[logging.Logger] = None,
    retourner_alertes: bool = False,
):
    """
    Détecte les fuites de données par leur EFFET, non par leur nom.

    Retourne {colonne: corrélation} pour toute feature dont la corrélation de
    Spearman avec la cible dépasse `seuil` en valeur absolue — c'est-à-dire toute
    variable qui « connaît » déjà la réponse.

    Ce contrôle est INDÉPENDANT du nom de la colonne : il attrape les fuites que
    personne n'a imaginées, ce qu'aucune liste ne peut faire.

    cols_exemptees : colonnes structurellement corrélées à la cible sans être des
        fuites — typiquement l'exposition (un contrat exposé 12 mois a
        mécaniquement plus de sinistres qu'un contrat exposé 1 mois). Elle sert
        d'offset, pas de prédicteur.
    """
    _log = logger_agent or logger
    exemptees = set(cols_exemptees or []) | {
        'exposition', 'log_exposition', col_cible,
    }
    fuites = {}
    signaux_experience = {}   # expérience passée à signal fort : informer, pas exclure
    if col_cible not in getattr(df, 'columns', []):
        return (fuites, signaux_experience) if retourner_alertes else fuites
    try:
        import numpy as np
        y = df[col_cible].astype(float)
        if float(y.std()) == 0.0:
            # cible constante : corrélation indéfinie
            return (fuites, signaux_experience) if retourner_alertes else fuites
        rang_y = y.rank()
        y_arr = y.to_numpy(dtype=float)
        _trapz = getattr(np, 'trapezoid', None) or getattr(np, 'trapz')

        def _gini_trie_par(x_arr):
            # Gini de la cible lorsqu'on trie les contrats par la variable x.
            ordre = np.argsort(-x_arr)
            y_ord = y_arr[ordre]
            total = float(y_ord.sum())
            if total <= 0:
                return 0.0
            cum_y = np.cumsum(y_ord) / total
            cum_pop = np.arange(1, len(y_ord) + 1) / len(y_ord)
            return float(2.0 * _trapz(cum_y, cum_pop) - 1.0)

        # Plafond : le Gini obtenu en triant par la cible ELLE-MÊME. C'est le
        # pouvoir discriminant MAXIMAL atteignable sur ces données — et c'est ce
        # qui rend la mesure insensible aux ex aequo de la cible.
        gini_parfait = _gini_trie_par(y_arr)

        for c in feature_names:
            if c in exemptees or c not in df.columns:
                continue
            try:
                x = df[c].astype(float)
                if float(x.std()) == 0.0:
                    continue
                rho = float(rang_y.corr(x.rank()))            # Spearman
                rho = 0.0 if rho != rho else abs(rho)          # NaN -> 0
                g_norm = 0.0
                if gini_parfait > 1e-9:
                    g_norm = abs(_gini_trie_par(x.to_numpy(dtype=float))
                                 / gini_parfait)
                signal = max(rho, g_norm)
                if signal < seuil:
                    continue
                # ═══════════════════════════════════════════════════════════════
                #  L'ANTÉRIORITÉ EST LE CRITÈRE — PAS LA CORRÉLATION
                # ═══════════════════════════════════════════════════════════════
                # BLOQUANT B7 (audit V13). Ma prémisse — écrite noir sur blanc
                # dans ce module — était : « aucun facteur tarifaire légitime ne
                # corrèle à 0,80+ avec la sinistralité ». ELLE EST FAUSSE dès que
                # la fréquence monte.
                #
                # Sur une flotte de transport (4,2 sinistres/an/contrat), les
                # sinistres des 3 années PASSÉES corrèlent à 0,93 avec ceux de
                # l'année N — et il n'y a AUCUNE FUITE : ce sont deux tirages
                # de Poisson indépendants conditionnellement au risque
                # intrinsèque θ du contrat. La corrélation vient de
                # l'HÉTÉROGÉNÉITÉ PERSISTANTE — c'est-à-dire du fondement même
                # de la théorie de la crédibilité de Bühlmann-Straub, que ce
                # module implémente par ailleurs (A3._credibilite_buhlmann_straub).
                #
                # Mon contrôle détruisait donc le meilleur prédicteur légitime
                # qui existe, sur 4 régimes actuariels réalistes sur 9 :
                #     GLM avec le facteur d'expérience : Gini  0,4245
                #     GLM réellement livré             : Gini −0,0105  (!)
                # Le modèle livré ne discriminait plus rien — il était même
                # légèrement ANTI-SÉLECTIF. Et le rapport disait à l'actuaire
                # « exclusion obligatoire, aucune action », mettant le facteur
                # d'expérience sur le même plan que prime_pure. Pire que le
                # silence : une INSTRUCTION ERRONÉE.
                #
                # LA BONNE QUESTION n'est pas « cette variable connaît-elle la
                # réponse ? » mais « la connaît-elle AVANT QU'ELLE N'EXISTE ? ».
                # La corrélation est un SYMPTÔME ; l'antériorité est le CRITÈRE.
                # Une variable est admissible si et seulement si sa valeur est
                # connue à la DATE D'EFFET du contrat.
                #
                # On n'exclut donc JAMAIS une variable d'expérience passée sur la
                # foi de sa corrélation. On la signale — parce qu'un signal très
                # fort peut aussi trahir une colonne MAL ÉTIQUETÉE (nommée
                # « antérieure » mais remplie avec la période observée), et cela,
                # l'actuaire seul peut le trancher.
                if _est_experience_passee(c):
                    signaux_experience[c] = {'spearman': round(rho, 4),
                                             'gini_normalise': round(g_norm, 4)}
                    continue
                fuites[c] = {'spearman': round(rho, 4),
                             'gini_normalise': round(g_norm, 4)}
            except (TypeError, ValueError):
                continue
    except Exception as e:   # pragma: no cover
        # ⚠ ÉCHEC VISIBLE, JAMAIS SILENCIEUX (relecture, 11/07/2026).
        # Ce bloc retournait {} — c'est-à-dire « aucune fuite trouvée », un
        # résultat INDISCERNABLE de « le contrôle n'a pas tourné ». Or c'est
        # notre garde-fou principal, et le seul qui ne dépende d'aucun nom : le
        # voir se désactiver en silence, c'est exactement le bug V6 (np.trapz
        # avalé, Gini walk-forward toujours None, personne ne le sait).
        # Un contrôle dont on ne vérifie pas l'exécution n'est pas un contrôle.
        # On lève une exception dédiée : l'appelant DOIT décider quoi en faire,
        # il ne peut plus l'ignorer par construction.
        _log.error(
            f"[ANTI-FUITE PAR L'EFFET] ÉCHEC DU CONTRÔLE — {type(e).__name__}: {e}. "
            f"Le garde-fou principal contre les fuites de données n'a PAS pu "
            f"s'exécuter. Ne pas poursuivre comme si tout allait bien."
        )
        raise EchecControleEffet(str(e)) from e

    if signaux_experience:
        _log.warning(
            f"[EXPÉRIENCE PASSÉE — SIGNAL FORT, CONSERVÉE] "
            f"{len(signaux_experience)} variable(s) de sinistralité PASSÉE "
            f"présentent un signal élevé avec la cible '{col_cible}' : "
            f"{signaux_experience}. C'est NORMAL et ATTENDU sur un portefeuille à "
            f"forte fréquence ou forte hétérogénéité (flotte, RC Pro, grands "
            f"risques) : c'est l'hétérogénéité persistante, le fondement même de "
            f"la crédibilité de Bühlmann-Straub. Ces variables sont CONSERVÉES — "
            f"elles sont connues à la date d'effet du contrat, et ce sont les "
            f"meilleurs prédicteurs légitimes qui existent. "
            f"⚠ Vérifiez toutefois qu'elles portent bien sur le PASSÉ et non, par "
            f"erreur de mapping, sur la période observée."
        )

    if fuites:
        _log.warning(
            f"[ANTI-FUITE PAR L'EFFET] {len(fuites)} variable(s) écartée(s) — "
            f"signal (Spearman OU Gini normalisé) avec la cible '{col_cible}' "
            f"≥ {seuil} : {fuites}. "
            f"Aucun facteur tarifaire légitime n'atteint ce niveau (le "
            f"bonus-malus, meilleur prédicteur de l'auto, plafonne vers 0,30). "
            f"Une telle variable EST la cible déguisée : elle n'existe pas encore "
            f"au moment de tarifer un contrat neuf."
        )
    return (fuites, signaux_experience) if retourner_alertes else fuites


def gini_est_plausible(gini: Optional[float],
                       cible_est_frequence: bool = True) -> bool:
    """
    Le Gini est-il actuariellement plausible, ou trahit-il une fuite ?

    Un Gini de fréquence > 0,60 sur un portefeuille Non-Vie n'est pas un exploit :
    c'est une alerte. Les deux fuites bloquantes de l'histoire de ce module
    affichaient 0,91 (V8) et 0,92 (V12), contre 0,20 et 0,07 une fois corrigées.
    """
    if gini is None:
        return True   # rien à juger ici (traité par le gate de disponibilité)
    if not cible_est_frequence:
        return True
    return float(gini) <= GINI_PLAUSIBLE_MAX_FREQUENCE


def synthese_alertes_experience(alertes: Optional[dict]) -> Optional[str]:
    """
    SOURCE UNIQUE — texte à afficher dans TOUT livrable lorsque des variables
    d'expérience passée ont été CONSERVÉES malgré un signal très fort.

    Ce n'est PAS une exclusion : c'est une VÉRIFICATION demandée à l'actuaire.

    Pourquoi (BLOQUANT B7, audit V13) : sur un portefeuille à forte fréquence ou
    forte hétérogénéité (flotte, RC Pro, grands risques), la sinistralité passée
    corrèle très fortement avec celle de l'année N — c'est NORMAL, c'est
    l'hétérogénéité persistante, et c'est le fondement de la crédibilité de
    Bühlmann-Straub. Ces variables sont donc conservées : ce sont les meilleurs
    prédicteurs légitimes qui existent.

    MAIS un signal aussi fort peut aussi trahir une colonne MAL ÉTIQUETÉE —
    nommée « antérieure » et remplie, par erreur de mapping, avec la période
    observée. Seul l'actuaire peut trancher. Il faut donc le lui DIRE, dans le
    livrable — pas seulement dans un log que personne ne lit (constat I5).
    """
    a = alertes or {}
    if not a:
        return None
    details = ", ".join(
        f"{c} (Gini normalisé {v.get('gini_normalise')})" if isinstance(v, dict)
        else f"{c} ({v})"
        for c, v in sorted(a.items())
    )
    return (
        f"ℹ À VÉRIFIER — {len(a)} variable(s) de sinistralité PASSÉE conservée(s) "
        f"malgré un signal très élevé avec la cible : {details}. "
        f"Ce n'est PAS une anomalie : sur un portefeuille à forte fréquence ou "
        f"forte hétérogénéité (flotte, RC Pro, grands risques), la sinistralité "
        f"passée est fortement corrélée à celle de l'année en cours — c'est "
        f"l'hétérogénéité persistante, le fondement de la crédibilité de "
        f"Bühlmann-Straub, et ce sont les meilleurs prédicteurs légitimes qui "
        f"existent. Ces variables ont donc été CONSERVÉES. "
        f"⚠ Vérifiez néanmoins qu'elles portent bien sur des exercices PASSÉS, et "
        f"non — par erreur de mapping — sur la période observée : dans ce second "
        f"cas, il s'agirait d'une fuite de données et le modèle serait invalide."
    )
