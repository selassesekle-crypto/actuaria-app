"""
ActuarIA — core/conformite_reglementaire.py
Conformité réglementaire — MODULE TRANSVERSAL PLATEFORME

⚠ SOURCE UNIQUE, POUR LES TROIS DIRECTIONS.
Ce module doit être importé par TOUT agent, de TOUTE direction (Non-Vie,
Vie/EP-RE, Santé-Prévoyance), qui construit une matrice de features à partir
de données client. Il ne doit jamais être dupliqué ni réimplémenté localement.

⚠⚠ ET CE QUI PRÉCÈDE EST UNE EXIGENCE, PAS UN ÉTAT — constat `conformite/C14`.
La phrase est à l'impératif (« doit être importé ») ; lue dans un module qui
s'appelle `conformite_reglementaire`, elle se lit comme la description de ce
qui EST surveillé. Les deux ne coïncident pas, et rien ici ne le disait.

  CE QUE CE MODULE SURVEILLE AUJOURD'HUI : la direction NON-VIE, elle seule.

Relevé par AST le 29/08/2026 — méthode rejouable : parcourir tous les `.py`
hors `.venv`, retenir ceux dont un `import` / `from ... import` cite
`conformite_reglementaire`, compter par répertoire de tête.

    446 fichiers balayés
      core                          2 importateur(s)
      demos                         1
      direction_non_vie            19
      direction_vie_epre            0   <-- AUCUNE surveillance
      direction_sante_prevoyance    0   <-- AUCUNE surveillance

⚠ LES DEUX AUTRES DIRECTIONS RELÈVENT DE LA MÊME RÈGLE ET NE SONT PAS
COUVERTES ICI. Test-Achats s'applique à toute l'assurance ; ce module n'y est
pas appelé. *Une règle universelle surveillée sur un tiers du périmètre reste
une règle universelle — mais la surveillance, elle, doit dire son assiette.*

⚠ L'EXEMPTION CI-DESSOUS EST MOTIVÉE PAR LE MÉCANISME, LA RÈGLE PORTE SUR LE
CRITÈRE. « Leurs agents sont PARAMÉTRIQUES (pas de matrice X) » est vrai et
vérifié — mais l'absence de matrice X est une propriété de la FORME du modèle,
elle ne dit rien de l'usage du critère genre. *Ce n'est pas une couverture.*

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
     ⚠ « POUR TOUTE BRANCHE » décrit l'étendue de la RÈGLE CJUE, pas celle de
     la surveillance exercée par ce module — bornée à la Non-Vie, voir l'encadré
     de l'en-tête. *La règle est universelle ; le filtre ne l'est pas.*

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
import math
from typing import List, Optional

# ⚠️ Le formatage des nombres passe par le formateur PARTAGE de core :
# une troisieme convention dans le depot serait une divergence de plus.
from core.format_fr import nombre

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
#
# ⚠️⚠️ CE QUE CETTE RÈGLE DE PRINCIPE CORRIGE, ET CE QU'ELLE NE CORRIGE PAS —
# PRÉCISION DU LOT 1.3 (constat `conformite/C3`). Le texte ci-dessus se lisait
# comme si la destruction des six variables avait cessé. Mesuré, elle n'a cessé
# que sur UN garde-fou :
#
#   garde-fou n°3 (anti-fuite par le nom)  ->  6/6 SURVIVENT   <- corrigé ici
#   garde-fou n°1 (liste blanche codée)    ->  0/6 PASSENT     <- NON corrigé
#
# `MARQUEURS_EXPERIENCE_PASSEE` n'est pas consulté par `est_facteur_autorise` :
# `charge_sinistres_n1` n'y échoue pas *parce qu'elle ressemble à une fuite*,
# mais parce que `charge` n'est tout simplement pas un facteur déclaré. Élargir
# la liste blanche à « tout ce qui porte un marqueur de passé » y ferait entrer
# `prime_anterieure` — la prime précédente, que le plan interdit explicitement
# comme facteur (voir `Comportement` dans `core/plan_tarifaire.py`). **On ne
# l'élargit donc pas.**
#
# ⚠️ ET CE N'EST PAS UN DÉFAUT DE PRODUCTION : mesuré, les six appelants de
# production passent tous `plan=`, et sur ce chemin la liste blanche EST le plan
# signé — une variable d'expérience passée déclarée au plan entre dans la
# matrice X (`exclusions = {}`). Le garde-fou n°1 codé en dur ne gouverne que le
# chemin rétrocompat. **Le remède n'est pas d'allonger la liste : c'est de
# déclarer un plan.**
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
    # ⚠️ CONSTAT `conformite/C13` — `valeur_mobilier` était rangée plus bas,
    # sous « Indicateurs DÉRIVÉS générés par A2 ». Mesuré : A2 la LIT
    # (`_feature_engineering`, pour construire `valeur_par_m2`) et ne l'écrit
    # jamais. C'est une colonne SOURCE du fichier client. Sans conséquence sur
    # l'autorisation — elle passe dans les deux cas — mais un inventaire qui
    # se dit « recensé exhaustivement sur le code d'A2 » doit dire vrai.
    'valeur_mobilier',
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
    'logement_ancien', 'valeur_par_m2',
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


def mots_metriques_du_suffixe(suffixe: str) -> list:
    """Les mots métriques présents dans un suffixe de one-hot, **en MOTS
    ENTIERS** — jamais en sous-chaîne.

    ⚠️⚠️ CORRECTIF DU LOT 1.3 — constat `conformite/C5`. Le test était
    `any(m in suffixe for m in MOTS_METRIQUES_INTERDITS)`, c'est-à-dire une
    recherche de SOUS-CHAÎNE. Mesuré sur des modalités réelles de RC Pro :

        secteur_activite_imprimerie   ->  'imprimerie' contient 'prime'
        secteur_activite_couture      ->  'couture'    contient 'cout'
        secteur_activite_primeur      ->  'primeur'    contient 'prime'

    **Trois secteurs d'activité légitimes détruits parce qu'un mot métrique se
    cachait DANS un autre mot.** Une modalité de one-hot est composée de mots
    séparés par `_` : on teste donc les MOTS, pas les lettres.

    ⚠️ CE QUE CE CORRECTIF NE CHANGE PAS, ET C'EST VOULU : `garantie_montant_regle`
    (le BLOQUANT B6, Gini 0,0709 → 0,9222) reste détruit — `montant` et `regle`
    y sont des mots entiers. **Le second sens de ce contrôle est l'objet même du
    lot** : réparer un faux positif sans ouvrir un vrai négatif.

    ⚠️ RESTE CONNU, NON CORRIGÉ ICI, ET LE MOTIF LE DIT MAINTENANT :
    `garantie_perte_exploitation` et `garantie_perte_financiere` — la garantie
    CENTRALE de la RC Pro — portent `perte` en mot entier et restent écartées
    **sur ce chemin**. Ce n'est pas réparable par le nom : `perte_exploitation`
    est un péril, `perte_moyenne` et `perte_annuelle` sont des montants, et rien
    dans le nom ne les sépare (mesuré). Le remède est le PLAN SIGNÉ — sur le
    chemin déclaratif, la colonne déclarée passe (mesuré : `exclusions = {}`) —
    et c'est désormais ce que le motif d'exclusion indique.
    """
    jetons = set(suffixe.split('_'))
    return [m for m in MOTS_METRIQUES_INTERDITS if m in jetons]


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
            if (mots_metriques_du_suffixe(suffixe)
                    and not _est_experience_passee(suffixe)):
                continue   # 'garantie_montant_regle' → suffixe 'montant_regle'
            return True
    return False


def motif_mot_metrique(nom: str) -> str | None:
    """Si `nom` dérive d'un facteur AUTORISÉ mais a été écarté à cause d'un mot
    métrique dans son suffixe, rend le motif EXACT. Sinon None.

    ⚠️⚠️ POURQUOI CETTE FONCTION EXISTE — c'est la leçon du BLOQUANT B7.
    Le motif publié était « *non déclarée comme facteur tarifaire légitime
    (liste blanche) — à déclarer si elle est valide* », et la synthèse invitait
    l'actuaire à la déclarer dans `FACTEURS_TARIFAIRES_AUTORISES`. Or pour
    `garantie_perte_exploitation`, **`garantie` Y EST DÉJÀ DÉCLARÉ** : suivre
    l'instruction ne change rien. *Une instruction erronée est pire qu'un
    silence* — c'est exactement ce que B7 a établi.
    """
    n = nom.lower()
    base = _base_facteur(n)
    for f in FACTEURS_TARIFAIRES_AUTORISES:
        if base.startswith(f + '_'):
            suffixe = base[len(f) + 1:]
            mots = mots_metriques_du_suffixe(suffixe)
            if mots and not _est_experience_passee(suffixe):
                return (
                    f"suffixe de one-hot contenant un mot de GRANDEUR "
                    f"MONÉTAIRE ({', '.join(mots)}) — une modalité de facteur "
                    f"nomme un péril ou une catégorie, jamais un montant "
                    f"(BLOQUANT B6). Le facteur de base '{f}' EST déjà "
                    f"autorisé : la redéclarer en liste blanche ne changera "
                    f"RIEN. Si '{suffixe}' est bien une modalité légitime (ex. "
                    f"la garantie « perte d'exploitation » en RC Pro), "
                    f"DÉCLAREZ-LA DANS LE PLAN DE TARIFICATION SIGNÉ et "
                    f"relancez : le chemin déclaratif l'accepte."
                )
            return None
    return None


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

def agreger_controle_effet(sources: dict) -> dict:
    """Agrège l'état du contrôle par l'effet sur plusieurs agents.

    `sources` : {nom d'agent: son `result['controle_effet']`}.

    ⚠️⚠️ ON AGRÈGE PAR LE PIRE, JAMAIS PAR LE MEILLEUR. Si UN SEUL agent n'a
    pas pu faire tourner le garde-fou n°4, le tarif qui en sort n'est pas
    protégé par lui. Agréger par « au moins un l'a fait » publierait une
    couverture que le calcul ne porte pas.

    ⚠️⚠️ ET LES MOTIFS SONT CLÉS PAR (AGENT, CIBLE), PAS PAR CIBLE SEULE.
    Ma première version faisait `motifs.update(...)` sur des clés de cible :
    **deux agents en échec sur la MÊME cible écrasaient l'un l'autre, et un
    motif sur deux disparaissait.** Le drapeau restait juste — rien de faux
    n'était publié — mais l'actuaire perdait une des deux causes, et aucun
    motif ne nommait l'agent concerné. *Un agrégat qui perd une cause est un
    agrégat qui masque.*

    ⚠️ Aucune source renseignée → on ne peut RIEN attester : `execute=False`.
    Le silence ne vaut jamais accord pour un garde-fou.
    """
    resultat = {'execute': True, 'motifs': {}}
    vu = False
    for agent, rapport in (sources or {}).items():
        if not isinstance(rapport, dict):
            continue
        vu = True
        if not rapport.get('execute'):
            resultat['execute'] = False
        for cible, motif in (rapport.get('motifs') or {}).items():
            resultat['motifs'][f"{agent} / {cible}"] = motif
    if not vu:
        return {'execute': False,
                'motifs': {'(tous)': "aucun agent n'a rapporte l'etat du "
                                     "controle par l'effet"}}
    return resultat


def avertissement_controle_effet(rapport: dict | None) -> str | None:
    """SOURCE UNIQUE du texte « le garde-fou n°4 n'a pas tourné », à afficher
    dans TOUT livrable. `None` s'il n'y a rien à signaler.

    ⚠️⚠️ POURQUOI CETTE FONCTION EXISTE — constat `conformite/C7`. La propriété
    `MatriceX.controle_effet_execute` a été ajoutée par l'audit V14 avec la
    mention explicite « ⚠ À REMONTER DANS LES RAPPORTS », et la raison écrite
    dans ce module : *« le WARNING existait dans les logs, mais l'objet n'en
    portait aucune trace — donc rien n'atteignait l'actuaire »*. Mesuré le
    25/08/2026 : **elle n'était lue par aucun agent, aucun service, aucun
    livrable.** Elle est restée une trace interne pendant tout ce temps.

    ⚠️⚠️ ET ELLE NE POUVAIT PAS ÊTRE PUBLIÉE SEULE. Tant que
    `controle_effet_execute` attestait la simple fourniture des arguments
    (constat `conformite/C1`), la remonter dans les rapports aurait publié une
    ATTESTATION FAUSSE : « garde-fou n°4 exécuté » sur une matrice où il
    n'avait examiné aucune colonne. **`C1` a donc été corrigé d'abord, dans le
    même changement.** Ne jamais revenir sur l'un sans l'autre.

    `rapport` est le dict porté par `result_a3/a4/a5['controle_effet']` et
    relayé par A6 : `{'execute': bool, 'motifs': {cible: pourquoi}}`.
    """
    r = rapport or {}
    if not r:
        return None
    if r.get('execute') and not r.get('motifs'):
        return None
    motifs = r.get('motifs') or {}
    detail = (" MOTIF(S) : " + " · ".join(f"{k} — {v}" for k, v in motifs.items())
              if motifs else "")
    if not r.get('execute'):
        return (
            "⚠ CONTRÔLE ANTI-FUITE PAR L'EFFET — NON EXÉCUTÉ. Le garde-fou n°4, "
            "le SEUL qui ne dépende d'aucun nom de colonne, n'a examiné AUCUNE "
            "colonne. Seuls les contrôles par le nom protègent ce tarif, et "
            "l'audit a démontré qu'ils sont structurellement insuffisants "
            "('garantie_montant_regle' : Gini 0,0709 → 0,9222)." + detail
        )
    return (
        f"⚠ CONTRÔLE ANTI-FUITE PAR L'EFFET — PARTIEL. Il a tourné, mais "
        f"{len(motifs)} cible(s) n'ont PAS été examinées : la couverture n'est "
        f"pas complète." + detail
    )


#: ⚠️⚠️ LE MARQUEUR DU LIVRABLE MANQUANT — source unique, importée par les
#: badges Excel comme `MARQUEUR_QUALITE_NON_EXECUTEE`. Y recopier le littéral
#: rouvrirait la divergence que le lot « 30 définitions locales -> 0 » a fermée.
MARQUEUR_LIVRABLE_ABSENT = 'LIVRABLE NON PRODUIT'


def avertissement_livrables_absents(livrables: dict | None) -> str | None:
    """⚠️⚠️ UN RUN PEUT ÊTRE VERT ET N'AVOIR PRODUIT AUCUN DOCUMENT.

    Constat `services/C13`. Les **neuf** exportateurs du module partagent une
    seule et même forme :

    ```
      try:   ... construire le classeur ...  return octets
      except Exception as e:
          logger.error(...);  return b''
    ```

    Ce n'est pas silencieux dans le JOURNAL — c'est silencieux dans le
    **verdict du run**. Mesuré le 02/09/2026 : un défaut simulé fait passer
    l'Excel A6 de **10 976 octets à 0**, `success` reste `True`, le statut RAG
    ne bouge pas, et l'appelant reçoit un `b''` qui ne distingue pas
    « non demandé » de « demandé et échoué ».

    > *C'est le mécanisme qui a caché `conformite/C16` : un Excel entier
    > disparu sur un `logger.warning`, sous une gate verte.*

    ⚠️⚠️ L'ENTRÉE PORTE LA DEMANDE, PAS SEULEMENT LE RÉSULTAT. Une table
    `{nom: octets}` ne contient QUE les livrables réellement demandés :
    l'absence d'une clé veut dire « pas demandé », une valeur vide veut dire
    « demandé et manquant ». *Sans cette distinction, l'avertissement crierait
    sur chaque run qui ne demande pas de PDF — et un avertissement permanent
    est un avertissement qu'on cesse de lire.*

    ⚠️ ELLE NE DÉGRADE PAS LE STATUT RAG, ET C'EST DÉLIBÉRÉ. Le RAG mesure la
    qualité du TARIF ; un document non produit est un incident de RENDU.
    *Rendre à chacun sa propre question* — c'est l'arbitrage de `qualite/C16`,
    appliqué ici.

    Retourne `None` quand tout ce qui a été demandé a été produit : *un
    contrôle qui n'a rien trouvé se tait.*
    """
    demandes = livrables or {}
    absents = sorted(nom for nom, octets in demandes.items()
                     if not (octets or b''))
    if not absents:
        return None
    total = len(demandes)
    return (
        f"⚠ {MARQUEUR_LIVRABLE_ABSENT} — {len(absents)} document(s) sur "
        f"{total} demandé(s) n'ont PAS été produits : {', '.join(absents)}. "
        f"L'échec est tracé au journal (niveau ERREUR) mais n'arrête pas le "
        f"run : le tarif ci-dessus reste valide, c'est sa RESTITUTION qui est "
        f"incomplète. Ne diffusez pas ce dossier comme complet — relancez la "
        f"production des documents manquants, ou joignez le motif au dossier "
        f"signé."
    )


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
                 '_controle_effet_execute', '_motifs_controle_effet',
                 '_ecartees_amont', '_exemptees_effet')

    def __init__(self, features, exclusions, contexte, _jeton=None, alertes=None,
                 controle_effet_execute=True, motifs_controle_effet=None,
                 ecartees_amont=None, exemptees_effet=None):
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
        # ⚠️ LE MOTIF VOYAGE AVEC LE DRAPEAU — constat `conformite/C7`.
        # Un booléen seul dit QU'IL n'a pas tourné, jamais POURQUOI :
        # l'actuaire ne peut alors rien en faire.
        object.__setattr__(self, '_motifs_controle_effet',
                           dict(motifs_controle_effet or {}))
        object.__setattr__(self, '_ecartees_amont',
                           dict(ecartees_amont or {}))
        # ⚠️⚠️ CONSTAT `conformite/C4` — L'EXEMPTION SILENCIEUSE.
        # Deux chemins exemptent du controle par l'effet. Celui par le NOM
        # alimente `alertes` et produit un texte de rapport ; celui par le
        # PLAN (`plan.facteurs_anteriorite()`) faisait un `continue` nu :
        # ni exclusion, ni alerte, ni log. Mesure du 01/09 sur un
        # portefeuille auto reel : `antecedents_sinistres_n1` est exemptee
        # et n'apparait NULLE PART -- 0 mention dans les logs, 0 dans
        # `exclusions`, 0 dans `alertes`.
        # *Une variable soustraite au garde-fou le plus fort du module ne
        # peut pas l'etre sans que le lecteur du rapport le sache.*
        object.__setattr__(self, '_exemptees_effet',
                           dict(exemptees_effet or {}))

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
    def ecartees_amont(self):
        """Colonnes DÉCLARÉES AU PLAN qui n'ont jamais été soumises à ce filtre.

        ⚠️⚠️ CONSTAT `conformite/C15` — CE GARDE-FOU SURVEILLAIT L'INTERSECTION,
        JAMAIS L'ABSENCE. La liste blanche compare ce qu'elle REÇOIT à ce qui est
        PERMIS : une colonne retirée EN AMONT lui est structurellement invisible.
        Violation plantée le 31/08 — on retire une colonne déclarée avant
        l'appel : 22 reçues au lieu de 23, **0 exclusion, 0 alerte**. *Un facteur
        du plan SIGNÉ disparaissait sans un mot.*

        ⚠️ CE N'EST PAS UNE EXCLUSION, ET ELLE N'EST DONC PAS DANS `exclusions`.
        Cette porte n'a pas écarté ce qu'elle n'a jamais reçu : *un instrument ne
        revendique pas un acte qu'il n'a pas commis* — c'est le motif que ce
        module tout entier poursuit.

        ⚠️ ELLE CONSTATE, ELLE NE TRANCHE PAS : aucune levée. Un fichier client
        peut légitimement ne pas porter une colonne déclarée, et A2 le déclare
        déjà (`colonnes_plan_manquantes`). Lever casserait des exécutions justes.

        ⚠️ Vide quand `plan` n'est pas fourni : sans contrat, il n'y a rien à
        comparer, et le dire vaut mieux que de rendre une liste trompeuse.
        """
        return dict(self._ecartees_amont)

    @property
    def exemptees_effet(self):
        """Colonnes SOUSTRAITES au contrôle par l'effet, et pourquoi.

        ⚠️⚠️ CONSTAT `conformite/C4` — L'EXEMPTION PAR LE PLAN ÉTAIT MUETTE,
        CELLE PAR LE NOM EST SIGNALÉE. Deux chemins exemptent du garde-fou le
        plus fort du module. Celui par le NOM (`exposition`, la cible) est
        structurel et documenté ; celui par le PLAN — `facteurs_anteriorite()`
        — faisait un `continue` nu. Mesuré le 01/09 sur un portefeuille auto
        réel : `antecedents_sinistres_n1` est exemptée et **n'apparaît nulle
        part** — 0 mention en log, 0 dans `exclusions`, 0 dans `alertes`.

        > *L'asymétrie entre deux chemins qui font le même geste est ce qui
        > localise le défaut : ici, l'un parle et l'autre se tait.*

        ⚠️ CE N'EST PAS UNE EXCLUSION : ces colonnes sont **conservées**. Les
        mettre dans `exclusions` dirait le contraire de ce qui s'est passé.
        C'est une DÉCISION déclarée au plan signé, et elle se lit comme telle.

        ⚠️ Vide quand `plan` n'est pas fourni : sans contrat, aucune exemption
        déclarative n'existe, et les exemptions structurelles ne sont pas des
        décisions de l'actuaire.
        """
        return dict(self._exemptees_effet)

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
    def motifs_controle_effet(self):
        """{cible: pourquoi le contrôle par l'effet n'a pas pu l'examiner}.

        Vide quand tout a été examiné. Alimente `avertissement_controle_effet`,
        qui est la SOURCE UNIQUE du texte à publier."""
        return dict(self._motifs_controle_effet)

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


def _phrase_signal(mesures) -> str:
    """Rend LISIBLE le signal d'une fuite par l'effet.

    ⚠️⚠️ CONSTAT `conformite/C8` — LE MOTIF LU PAR L'ACTUAIRE CONTENAIT UN
    DICTIONNAIRE PYTHON. `fuites_effet[c]` est un `dict` depuis l'ajout du Gini
    normalisé, et il partait tel quel dans un texte qui voyage jusqu'au rapport
    signé, lu par cinq fichiers de production :

        corrélation de {'spearman': 0.4563, 'gini_normalise': 1.0}

    > *Un dict Python n'est pas une phrase.*

    ⚠️ ET LE MOT ÉTAIT FAUX AUSSI. Le texte disait « corrélation » au
    singulier, alors que le critère appliqué est `max(spearman, gini_normalise)`
    depuis que la seconde mesure existe. Le motif NOMME désormais les deux
    grandeurs et celle qui a déclenché. *Quand un comportement change, le
    texte qui l'accompagne se relit.*
    """
    if not isinstance(mesures, dict):
        return f"corrélation de {mesures}"
    nommees = [('Spearman', mesures.get('spearman')),
               ('Gini normalisé', mesures.get('gini_normalise'))]
    presentes = [(nom, float(v)) for nom, v in nommees if v is not None]
    if not presentes:
        return f"signal de {mesures}"
    declencheur = max(presentes, key=lambda kv: kv[1])[0]
    return (f"signal mesuré {' et '.join(f'{n} {v:.3f}' for n, v in presentes)}"
            f" (critère : le plus élevé des deux, ici {declencheur})")


def _phrase_cibles(cibles) -> str:
    """« la cible ['nb_sinistres'] » : la LISTE Python arrivait telle quelle.

    Même constat que `_phrase_signal`, sur la même ligne — `conformite/C8`.
    """
    noms = [cibles] if isinstance(cibles, str) else list(cibles)
    return ' et '.join(f"\u00ab {c} \u00bb" for c in noms)
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
    #: Vide sans plan : sans contrat, il n'y a rien a comparer.
    ecartees_amont: dict = {}
    #: Idem — sans plan, aucune exemption DECLARATIVE n'existe. Les exemptions
    #: structurelles (exposition, cible) ne sont pas des decisions d'actuaire
    #: et n'ont donc rien a faire dans un canal qui publie des DECISIONS.
    exemptees_effet: dict = {}
    if plan is not None:
        # DÉCLARATIVE : n'est légitime que ce que le plan SIGNÉ annonce. Les
        # garde-fous 2·3 restent appliqués — non contournables par le plan.
        declarees = set(plan.colonnes_produites())
        cols_exemptees_effet = list(plan.facteurs_anteriorite())
        # ⚠️⚠️ CONSTAT `conformite/C4` — L'EXEMPTION SE DIT. On ne publie que
        # celles qui étaient RÉELLEMENT présentées : exempter une colonne
        # absente du fichier n'est pas un acte, et l'annoncer ferait un
        # avertissement permanent — donc un avertissement qu'on cesse de lire.
        exemptees_effet = {
            c: MOTIF_EXEMPTEE_ANTERIORITE
            for c in sorted(set(cols_exemptees_effet) & set(candidates))
        }
        # ⚠️⚠️ CONSTAT `conformite/C15` — CE QUI N'EST JAMAIS ARRIVÉ JUSQU'ICI.
        # La ligne suivante compare les CANDIDATES aux DÉCLARÉES : elle ne peut
        # rien dire de ce qui a été retiré AVANT l'appel. Or quatre appelants sur
        # six construisent leur liste PAR SOUSTRACTION (`a3`, `a4`, `a5`, `a6`),
        # là où `pipeline_tarifaire` et la démo passent le contrat lui-même.
        # *C'est l'asymétrie entre chemins qui localise le défaut.*
        # ⚠️ On CONSTATE ici, on ne tranche pas — voir `MatriceX.ecartees_amont`.
        # ⚠️⚠️ ET LE MOTIF VOYAGE AVEC LE FAIT. Mesuré le 31/08 : sur un
        # portefeuille NORMAL, `carburant_electrique` est écartée — modalité
        # one-hot d'un portefeuille sans véhicule électrique, donc CONSTANTE.
        # C'est légitime. *Publier « ACTION REQUISE » là-dessus à chaque
        # exécution ferait un avertissement permanent, donc un avertissement
        # qu'on cesse de lire.* La cause est dérivable ICI — cette porte reçoit
        # déjà `df` pour le garde-fou n°4 — et elle l'est en UN SEUL endroit
        # plutôt que dans les trois agents qui soustraient.
        ecartees_amont = {c: _motif_ecartee_amont(c, df)
                          for c in sorted(declarees - set(candidates))}
        # ⚠️⚠️ CONSTAT `conformite/C11` — LA TRACE ACPR PASSAIT APRÈS LE
        # FILTRE QUI LUI ÔTAIT SON OBJET. `filtrer_genre` journalise « toute
        # suppression effective — traçabilité requise pour l'audit ACPR »,
        # mais il recevait une liste dont l'intersection avec le plan avait
        # DÉJÀ retiré `sexe`. Mesuré le 01/09 sur un portefeuille qui PORTE
        # la colonne : 0 log citant C-236/09.
        # *Un filtre placé après celui qui lui ôte son objet ne peut plus rien
        # tracer — et un contrôle qui ne peut pas se déclencher est du décor.*
        # ⚠️ L'ENSEMBLE RETENU EST LE MÊME : filtrer puis intersecter et
        # intersecter puis filtrer donnent le même résultat. Seule la TRACE
        # change — aucun euro ne bouge, et `A1-2` du lot voisin le prouve
        # par exécution ici même (CF-4, CF-5).
        conformes = filtrer_genre(list(candidates), contexte=contexte,
                                  logger_agent=logger_agent)             # ② INV-3
        conformes = [c for c in conformes if c in declarees]
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

    # ⚠️⚠️ LA PROPRIÉTÉ ATTESTE L'EXÉCUTION, PLUS LA FOURNITURE DES ARGUMENTS —
    # constat `conformite/C1`. Elle valait `not (df is None or not cibles)`,
    # c'est-à-dire « les arguments ont été passés ». Or `detecter_fuites_par_effet`
    # renonce en silence quand la cible est absente du DataFrame ou de variance
    # nulle : le contrôle n'examinait AUCUNE colonne et se déclarait exécuté.
    # On interroge donc la SOURCE UNIQUE, cible par cible.
    # ⚠️ DEUX NATURES, UN SEUL CANAL DE PUBLICATION. Un EMPÊCHEMENT rend le
    # contrôle non exécuté ; une RÉSERVE dit qu'il a tourné sur un
    # sous-ensemble. Les deux sont publiés, **seuls les empêchements pilotent
    # `controle_effet_execute`** — sinon une cible à moitié vide ferait croire
    # que rien n'a été vérifié.
    motifs_effet = {}
    empechements = 0
    for _c in cibles:
        _m = motif_controle_effet_impossible(df, _c)
        if _m is not None:
            motifs_effet[str(_c)] = _m
            empechements += 1
            continue
        _r = reserve_controle_effet(df, _c)
        if _r is not None:
            motifs_effet[str(_c)] = _r
    # Exécuté = au moins une cible a réellement pu être examinée. Une seule
    # cible exploitable suffit à faire tourner le garde-fou ; aucune ne le
    # laisse muet, et c'est alors qu'il faut le DIRE.
    controle_effet_execute = bool(cibles) and empechements < len(cibles)
    if motifs_effet and controle_effet_execute:
        # Cas partiel : une cible sur deux. Le contrôle a tourné, mais pas sur
        # tout — le taire ferait croire à une couverture complète.
        _log.warning(
            f"[ANTI-FUITE PAR L'EFFET — PARTIEL] "
            f"{len(motifs_effet)}/{len(cibles)} cible(s) non examinée(s)"
            f"{' (' + contexte + ')' if contexte else ''} : "
            + " · ".join(f"{k} — {v}" for k, v in motifs_effet.items())
        )
    if not controle_effet_execute:
        # ⚠ LE GARDE-FOU NE DOIT JAMAIS SE DÉSACTIVER EN SILENCE.
        # ⚠️⚠️ LA CONDITION PORTE DÉSORMAIS SUR L'EXÉCUTION, plus sur la seule
        # absence d'arguments : une cible fournie mais ABSENTE des données, ou
        # CONSTANTE, laissait le contrôle muet et cette branche non prise.
        # `df` et `col_cible` sont techniquement optionnels — un agent peut donc
        # les omettre, et le contrôle par l'effet (le SEUL qui ne dépende d'aucun
        # nom de colonne) ne tourne alors PAS. Sans cet avertissement, cette
        # désactivation serait indiscernable d'un contrôle qui n'a rien trouvé :
        # c'est très exactement le motif du bug V6 et du BLOQUANT B2.
        # Un contrôle dont on ne vérifie pas l'exécution n'est pas un contrôle.
        # ⚠️ L'EN-TÊTE DOIT DIRE LA VRAIE CAUSE. Il annonçait « appelée SANS df
        # et/ou SANS col_cible » — or depuis le correctif de `C1`, cette branche
        # est aussi prise quand les DEUX ont été fournis mais que la cible est
        # absente des données ou constante. Un message qui contredit le motif
        # qu'il porte est le défaut que ce module poursuit.
        _cause = ("appelée SANS df et/ou SANS col_cible"
                  if (df is None or not cibles)
                  else "appelée AVEC df et col_cible, mais aucune cible "
                       "exploitable")
        _log.warning(
            f"[ANTI-FUITE PAR L'EFFET — NON EXÉCUTÉ] "
            f"construire_matrice_x() {_cause}"
            f"{' (' + contexte + ')' if contexte else ''}. Le garde-fou n°4 — le "
            f"seul qui ne dépende d'aucun nom de colonne — N'A PAS TOURNÉ. Seuls "
            f"les contrôles par le nom protègent cette matrice X, et l'audit V12 "
            f"a démontré qu'ils sont structurellement insuffisants "
            f"('garantie_montant_regle' : Gini 0,0709 → 0,9222). "
            f"Fournissez df= et col_cible=."
            + (" MOTIF(S) : " + " · ".join(
                f"{k} — {v}" for k, v in motifs_effet.items())
               if motifs_effet else "")
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
                f"FUITE DÉTECTÉE PAR L'EFFET — "
                f"{_phrase_signal(fuites_effet[c])} "
                f"avec la cible {_phrase_cibles(cibles)}. Aucun facteur "
                f"tarifaire légitime n'atteint ce niveau : cette variable EST "
                f"la cible déguisée, et n'existe pas encore au moment de "
                f"tarifer un contrat neuf."
            )
        elif _est_variable_genre(c):
            exclusions[c] = "genre ou proxy de genre — CJUE C-236/09 (Test-Achats)"
        elif _est_derivee_sinistralite(c):
            exclusions[c] = ("dérivée de la sinistralité observée — fuite de "
                             "données (inconnue au moment de tarifer)")
        elif declarees is not None and c not in declarees:
            # ⚠️⚠️ CONSTAT `conformite/C12` — L'INSTRUCTION ÉTAIT FAUSSE SUR
            # CE CHEMIN. Le motif portait « (liste blanche) », et
            # `synthese_exclusions` en déduisait « déclarez-la
            # (FACTEURS_TARIFAIRES_AUTORISES) et relancez ». Or ici la source
            # de vérité est `plan.colonnes_produites()` : éditer la constante
            # ne change RIEN. *Une instruction que l'actuaire ne peut pas
            # suivre est pire que le silence — c'est le jugement déjà porté
            # par le BLOQUANT B7, ici sur un autre chemin.*
            exclusions[c] = ("non déclarée dans le PLAN DE TARIFICATION SIGNÉ "
                             "— à déclarer DANS LE PLAN si elle est valide")
        elif declarees is None and not (est_facteur_autorise(c) or c.lower() in autorises_extra):
            # ⚠️ LOT 1.3 — LE MOTIF NOMME LA VRAIE CAUSE, PAS UNE CAUSE
            # GÉNÉRIQUE. Une colonne dérivée d'un facteur DÉJÀ autorisé et
            # écartée pour un mot métrique recevait « à déclarer si elle est
            # valide » — instruction que l'actuaire ne pouvait pas suivre,
            # puisque le facteur de base était déjà déclaré. C'est le défaut
            # que le BLOQUANT B7 a jugé pire que le silence.
            exclusions[c] = motif_mot_metrique(c) or (
                "non déclarée comme facteur tarifaire légitime "
                "(liste blanche) — à déclarer si elle est valide")
        else:
            exclusions[c] = "exclue par le filtre de conformité"
    return MatriceX(conformes, exclusions, contexte, _jeton=_JETON,
                    motifs_controle_effet=motifs_effet,
                    alertes=alertes_experience,
                    controle_effet_execute=controle_effet_execute,
                    ecartees_amont=ecartees_amont,
                    exemptees_effet=exemptees_effet)


#: ⚠️⚠️ LE SEUL MOTIF QUI APPELLE UNE ACTION. Les autres décrivent une donnée
#: (absente, constante, non numérique) : l'actuaire ne peut rien y faire, et le
#: lui présenter comme une faute serait du bruit. Celui-ci dit qu'un facteur
#: DÉCLARÉ, présent et exploitable, a été retiré par un filtre en amont — c'est
#: `conformite/C15` dans sa forme active.
MOTIF_ECARTEE_FILTRE = 'retiree par un filtre en amont'

#: ⚠️ Le motif rendu quand une source ne fournit que des NOMS, sans sa table.
#: `fusionner_ecartees_amont` ne devine pas la cause : elle dit qu'elle
#: l'ignore. *Une cause inventee est pire qu'une cause manquante.*
MOTIF_MOTIF_ABSENT = 'cause non transmise par l agent source'

# ⚠️ CONSTAT `conformite/C4` — le motif de l'exemption par le plan, en UN seul
# endroit : le publier et le tester au même texte est ce qui empêche qu'il
# dérive du geste qu'il décrit.
MOTIF_EXEMPTEE_ANTERIORITE = (
    "CONSERVEE, exemptee du controle par l'effet -- declaree `anteriorite=True` "
    "au plan signe : sa valeur est connue a la DATE D'EFFET du contrat. "
    "La correlation avec la cible est alors un SYMPTOME d'heterogeneite "
    "persistante (Buhlmann-Straub), pas une fuite."
)


def _motif_ecartee_amont(colonne: str, df) -> str:
    """POURQUOI une colonne déclarée n'est jamais parvenue au filtre.

    ⚠️ Un drapeau sans son motif ne se traite pas — c'est la leçon déjà écrite
    pour `controle_effet` (`conformite/C7`). On dérive donc la cause plutôt que
    de rendre une liste nue.

    ⚠️ `df` absent : on le DIT, plutôt que de deviner. *Une cause inventée est
    pire qu'une cause manquante.*
    """
    if df is None:
        return 'cause non determinable (df non fourni a la porte)'
    if colonne not in getattr(df, 'columns', ()):
        return 'absente du dataframe en entree'
    serie = df[colonne]
    if str(serie.dtype) not in ('int64', 'float64', 'int32', 'float32'):
        return f'non numerique (dtype {serie.dtype})'
    try:
        if float(serie.std()) == 0.0:
            return 'constante (variance nulle) sur ce portefeuille'
    except (TypeError, ValueError):          # pragma: no cover
        return 'variance non calculable'
    return MOTIF_ECARTEE_FILTRE


def fusionner_ecartees_amont(*sources) -> dict:
    """Fusionne les `ecartees_amont` de PLUSIEURS agents — **par le PIRE**.

    ⚠️⚠️ CONSTAT `conformite/C16`. A3, A4 et A5 dérivent chacun leur table
    `{colonne: motif}` sur LEUR dataframe. A6 les agrégeait dans un `set`, ce
    qui ne gardait que les clés : *le motif était détruit avant d'atteindre le
    rapport signé, et `synthese_colonnes_plan_ecartees` levait sur la liste
    ainsi produite.* Mesuré : Excel A6 de 10 977 octets a **0 octet** dès
    qu'une seule colonne est écartée.

    ⚠️⚠️ POURQUOI « PAR LE PIRE » ET PAS « LE DERNIER GAGNE ». Deux agents
    peuvent donner deux motifs pour la même colonne — leurs dataframes
    diffèrent. `update()` garderait celui du dernier agent de la boucle, sans
    que rien ne le dise. *C'est exactement la leçon déjà écrite dans A6 pour
    `agreger_controle_effet` : deux agents en échec sur la même clé
    s'écrasaient, un motif sur deux disparaissait.*

    Un seul motif appelle une action — `MOTIF_ECARTEE_FILTRE`, un facteur
    DÉCLARÉ et exploitable retiré par un filtre amont. Il l'emporte donc sur
    tout autre : *un garde-fou se trompe du côté qui fait regarder.* À gravité
    égale, l'ordre des sources tranche, et il est déterministe.

    ⚠️ Accepte indifféremment un `dict` ou un itérable de noms : un appelant
    qui n'aurait que des noms reçoit un motif qui DIT qu'il n'y en a pas,
    plutôt qu'une table trompeuse. *Une cause inventée est pire qu'une cause
    manquante* — c'est la règle de `_motif_ecartee_amont`.
    """
    fusion: dict = {}
    for src in sources:
        if not src:
            continue
        if isinstance(src, dict):
            paires = src.items()
        else:
            paires = ((c, MOTIF_MOTIF_ABSENT) for c in src)
        for colonne, motif in paires:
            ancien = fusion.get(colonne)
            if ancien is None or (motif == MOTIF_ECARTEE_FILTRE
                                  and ancien != MOTIF_ECARTEE_FILTRE):
                fusion[colonne] = motif
    return dict(sorted(fusion.items()))


def synthese_colonnes_plan_ecartees(ecartees, plan_nom: str = '') -> str | None:
    """SOURCE UNIQUE du libellé « colonnes du plan écartées AVANT le filtre ».

    ⚠️⚠️ CONSTAT `conformite/C15`. Partagée par l'Excel A6, le rapport équipe et
    le Word/HTML — comme `synthese_exclusions` pour les exclusions et
    `synthese_colonnes_plan_manquantes` pour les colonnes absentes du fichier.

    ⚠️⚠️ DEUX CAUSES VOISINES, DEUX LIBELLÉS, ET LES CONFONDRE EFFACERAIT CE QUI
    COMPTE. L'actuaire ne corrige pas la même chose dans les deux cas :

    | libellé | ce qu'il dit | ce que l'actuaire corrige |
    |---|---|---|
    | `..._manquantes` | le plan déclare, **le fichier** ne l'a pas | son EXTRACTION |
    | `..._ecartees`   | le fichier l'a, **un filtre** l'a retirée | son PLAN, ou le filtre |

    Retourne None quand rien n'a été écarté : *un avertissement permanent est un
    avertissement qu'on cesse de lire.*

    ⚠️⚠️ ELLE NORMALISE SON ENTRÉE, ET CE N'EST PAS DE LA COMPLAISANCE. Elle
    faisait `dict(ecartees or {})`, qui **lève** sur une liste de noms — et A6
    lui en passait une. Les trois surfaces l'appellent dans un `try` qui rend
    `b''` : *le rapport signé disparaissait en entier, sur un `logger.warning`.*
    Mesuré le 02/09 : Excel A6 de **10 977 octets à 0**.

    On délègue donc à `fusionner_ecartees_amont`, qui accepte les deux formes
    **sans inventer de cause** : des noms nus reçoivent un motif qui DIT que la
    cause n'a pas été transmise. *Rendre l'échec impossible vaut mieux que le
    rendre rare, et un texte qui dit « cause non transmise » vaut mieux qu'un
    rapport absent.*
    """
    motifs = fusionner_ecartees_amont(ecartees)
    if not motifs:
        return None
    # ⚠️⚠️ LA GRAVITE SUIT LE MOTIF, PAS LE COMPTE. Une modalite one-hot absente
    # du portefeuille est CONSTANTE : c'est normal, et le crier a chaque
    # execution rendrait l'avertissement invisible. Seul un retrait par un
    # filtre amont appelle une action.
    actives = sorted(c for c, m in motifs.items() if m == MOTIF_ECARTEE_FILTRE)
    detail = " ; ".join(f"{c} ({m})" for c, m in sorted(motifs.items()))
    tete = (f"⚠ ACTION REQUISE — plan '{plan_nom or '?'}' : "
            f"{len(actives)} facteur(s) DECLARE(S), exploitable(s), RETIRE(S) "
            f"par un filtre en amont"
            if actives else
            f"Colonnes declarees au plan '{plan_nom or '?'}' non parvenues au "
            f"filtre de conformite (aucune action requise)")
    return (
        f"{tete} : {len(motifs)} colonne(s) declaree(s) n'ont jamais atteint "
        f"le filtre, et n'ont donc ete ni retenues ni ecartees explicitement. "
        f"{detail}."
    )


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

    ⚠⚠ CINQ MOTIFS, ET CETTE PHRASE EN ANNONÇAIT TROIS — constat `C6`, dont
    elle était la preuve citée. Le lot 1.3 a rendu le tri EXCLUSIF et ordonné ;
    la docstring, elle, est restée sur « Trois motifs » jusqu'au 29/08/2026.
    *Quand un comportement change, le texte qui l'accompagne se relit.*

    Cinq motifs, trois niveaux de gravité pour l'actuaire lecteur :
      · genre / proxy de genre  → exclusion OBLIGATOIRE (CJUE C-236/09). RAS.
      · dérivée de sinistralité → exclusion OBLIGATOIRE (fuite). RAS.
      · FUITE DÉTECTÉE PAR L'EFFET → ⚠ ACTION REQUISE. Exclusion **mesurée**,
        pas déduite d'un nom : elle ne distingue pas une fuite d'une variable
        de VOLUME légitime (en RC Pro, l'effectif joue le rôle que l'exposition
        joue en auto). *C'est le seul motif que l'actuaire peut légitimement
        contester, et il était publié comme indiscutable.*
      · mot de grandeur MONÉTAIRE → ⚠ ACTION REQUISE, à déclarer AU PLAN.
      · non déclarée en liste blanche → ⚠ À VÉRIFIER : si la variable est un
        facteur tarifaire légitime, elle doit être déclarée, sinon le modèle est
        amputé en silence.
    """
    exc = exclusions or {}
    if not exc:
        return None

    # ⚠️⚠️ LOT 1.3 — LES QUATRE MOTIFS SONT TRIÉS SÉPARÉMENT (constat `C6`).
    # Le tri se faisait par sous-chaîne `'fuite' in m.lower()`, qui capturait
    # AUSSI BIEN « dérivée de la sinistralité — fuite de données » (obligatoire,
    # aucune action) QUE « FUITE DÉTECTÉE PAR L'EFFET » (mesurée, et qui PEUT
    # frapper une variable légitime). Les deux recevaient donc le même texte —
    # « exclusion obligatoire, aucune action » — alors qu'une seule le mérite.
    # ⚠️⚠️ LE TRI EST ORDONNÉ ET EXCLUSIF, et il doit l'être.
    # Ma première version de ce correctif classait par sous-chaîne indépendante,
    # et `garantie_perte_exploitation` ressortait dans DEUX lignes à la fois :
    # son motif contient « ne changera RIEN — il y est déjà », mais aussi les
    # mots « liste blanche ». **Le défaut que ce bloc corrige, reproduit dans le
    # correctif lui-même.** Chaque colonne appartient désormais à UN seul motif,
    # le premier qui la reconnaît, par ordre de spécificité décroissante.
    _restant = dict(exc)

    def _prendre(predicat) -> list:
        pris = sorted(c for c, m in _restant.items() if predicat(m))
        for c in pris:
            _restant.pop(c, None)
        return pris

    genre = _prendre(lambda m: 'C-236/09' in m)
    effet = _prendre(lambda m: "PAR L'EFFET" in m)
    metrique = _prendre(lambda m: 'GRANDEUR MONÉTAIRE' in m)
    fuite = _prendre(lambda m: 'fuite' in m.lower())
    # ⚠️⚠️ CONSTAT `conformite/C12` — DEUX SOURCES DE VÉRITÉ, UNE SEULE
    # INSTRUCTION. Les deux motifs de non-déclaration portaient « (liste
    # blanche) », et cette synthèse en tirait « déclarez-la
    # (FACTEURS_TARIFAIRES_AUTORISES) ». Sur le chemin `plan`, éditer cette
    # constante NE CHANGE RIEN : la vérité est `plan.colonnes_produites()`.
    # Le seau du plan se prélève EN PREMIER — l'ordre est ce qui rend le tri
    # exclusif, comme pour les cinq motifs d'exclusion.
    a_declarer_au_plan = _prendre(lambda m: 'PLAN DE TARIFICATION SIGNÉ' in m)
    a_verifier = _prendre(lambda m: 'liste blanche' in m)
    autres = sorted(_restant)

    lignes = []
    if a_declarer_au_plan:
        lignes.append(
            f"⚠ ACTION REQUISE — {len(a_declarer_au_plan)} colonne(s) "
            f"écartée(s) de la matrice X car NON DÉCLARÉE(S) dans le PLAN DE "
            f"TARIFICATION SIGNÉ : {', '.join(a_declarer_au_plan)}. Si l'une "
            f"d'elles est un facteur valide de votre portefeuille, le modèle "
            f"en est amputé — déclarez-la DANS LE PLAN (le YAML signé), "
            f"resignez-le, et relancez. ⚠ Modifier la constante "
            f"FACTEURS_TARIFAIRES_AUTORISES NE CHANGERA RIEN sur ce chemin : "
            f"la source de vérité est le plan."
        )
    if a_verifier:
        lignes.append(
            f"⚠ ACTION REQUISE — {len(a_verifier)} colonne(s) écartée(s) de la "
            f"matrice X car NON DÉCLARÉE(S) comme facteur tarifaire légitime : "
            f"{', '.join(a_verifier)}. Si l'une d'elles est un facteur valide de "
            f"votre portefeuille, le modèle en est amputé — déclarez-la "
            f"(FACTEURS_TARIFAIRES_AUTORISES) et relancez la tarification."
        )
    if metrique:
        # ⚠️ Le motif porte déjà l'action exacte (déclarer AU PLAN, pas en liste
        # blanche) : on ne le remplace pas par un texte générique qui la perdrait.
        lignes.append(
            f"⚠ ACTION REQUISE — {len(metrique)} modalité(s) écartée(s) parce "
            f"que leur nom contient un mot de grandeur monétaire : "
            f"{', '.join(metrique)}. Redéclarer le facteur de base en liste "
            f"blanche NE CHANGERA RIEN — il y est déjà. Si ce sont des "
            f"modalités légitimes, déclarez-les DANS LE PLAN DE TARIFICATION "
            f"SIGNÉ et relancez."
        )
    if effet:
        lignes.append(
            f"⚠ ACTION REQUISE — {len(effet)} colonne(s) écartée(s) par le "
            f"CONTRÔLE PAR L'EFFET : {', '.join(effet)}. Cette exclusion est "
            f"MESURÉE (corrélation avec la cible), pas déduite d'un nom — et "
            f"elle ne distingue pas une fuite d'une variable de VOLUME "
            f"légitime. En RC Pro, l'effectif joue le rôle que l'exposition "
            f"joue en auto : il corrèle fortement avec le nombre de sinistres "
            f"PARCE QUE la relation est réelle et connue à la souscription. "
            f"VÉRIFIEZ chaque colonne : si elle est connue au moment de "
            f"tarifer un contrat neuf, déclarez-la au plan comme exemptée "
            f"(`anteriorite=True`) et relancez ; sinon, l'exclusion est juste."
        )
    if genre:
        lignes.append(
            f"✔ {len(genre)} colonne(s) exclue(s) au titre de l'interdiction du "
            f"genre en tarification — CJUE C-236/09 (Test-Achats) : "
            f"{', '.join(genre)}. Exclusion obligatoire, aucune action."
        )
    if fuite:
        # ⚠️ « Aucune action » n'est légitime QUE pour l'exclusion par le NOM
        # d'une grandeur de la période observée : celle-là est, par
        # construction, inconnue au moment de tarifer. L'exclusion par l'EFFET,
        # elle, est mesurée et peut frapper du légitime — elle a sa propre
        # ligne ci-dessus, avec une action.
        lignes.append(
            f"✔ {len(fuite)} colonne(s) exclue(s) comme dérivée(s) de la "
            f"sinistralité observée (fuite de données — inconnues au moment de "
            f"tarifer un contrat neuf) : {', '.join(fuite)}. Exclusion "
            f"obligatoire, aucune action."
        )
    if autres:
        lignes.append(f"· Autres exclusions : {', '.join(autres)}.")
    return "\n".join(lignes)



def synthese_exemptions_effet(exemptees) -> str | None:
    """SOURCE UNIQUE — texte disant quelles colonnes ont été SOUSTRAITES au
    contrôle par l'effet, et pourquoi. `None` s'il n'y en a aucune.

    ⚠️⚠️ CONSTAT `conformite/C4` — L'UN DES DEUX CHEMINS SE TAISAIT.
    L'exemption par le NOM alimente `alertes` et produit un texte ; celle par
    le PLAN (`facteurs_anteriorite()`) faisait un `continue` nu. Mesuré le
    01/09 sur un portefeuille auto réel : `antecedents_sinistres_n1` est
    exemptée et n'apparaît NULLE PART — 0 log, 0 exclusion, 0 alerte.

    > *Une variable soustraite au garde-fou le plus fort du module ne peut pas
    > l'être sans que le lecteur du rapport signé le sache.*

    ⚠️ LE TON N'EST PAS CELUI D'UNE EXCLUSION : ces colonnes sont CONSERVÉES,
    délibérément, par une décision écrite au plan. Ce qui se demande à
    l'actuaire n'est pas de les rétablir, c'est de VÉRIFIER que l'antériorité
    déclarée est vraie — une colonne nommée « antérieure » mais remplie avec
    la période observée est exactement la fuite que le contrôle cherchait.
    """
    exc = exemptees or {}
    if not exc:
        return None
    noms = ', '.join(sorted(exc))
    return (
        f"i {len(exc)} colonne(s) SOUSTRAITE(S) au contrôle par l'effet parce "
        f"que le plan signé les déclare `anteriorite=True` : {noms}. Elles "
        f"sont CONSERVÉES — leur valeur est connue à la date d'effet du "
        f"contrat, et leur corrélation avec la cible est alors un symptôme "
        f"d'hétérogénéité persistante (Buhlmann-Straub), pas une fuite. "
        f"⚠ VÉRIFIEZ que chacune porte bien sur le PASSÉ et non, par erreur de "
        f"mapping, sur la période observée : c'est le seul cas où cette "
        f"exemption ferait entrer une vraie fuite."
    )

def synthese_modele_dl(modele_production: Optional[dict],
                       valide_par: Optional[str],
                       date_validation: Optional[str] = None) -> Optional[str]:
    """
    SOURCE UNIQUE — texte à afficher dans TOUT livrable (Excel, Word, HTML,
    rapport d'équipe) quand le modèle retenu en production appartient à la
    famille Deep Learning. Retourne None sinon (aucune ligne à afficher).

    Pourquoi (garde-fou délibéré, 2026-07) : un modèle Deep Learning (CANN,
    TabNet) est une boîte noire. Même sain et bien ancré, sa mise en production
    demande une VALIDATION ACTUARIELLE HUMAINE explicite — délibérée, indépendante
    de tout garde-fou automatique (fidélité de recalibration walk-forward, ancrage
    du CANN). Ce qui n'est que dans un champ technique n'existe pas pour l'actuaire
    qui relit le dossier plus tard : la validation (ou son absence) doit être
    VISIBLE dans le rapport, au même titre que les exclusions de conformité.

    La trace « validé » est purement FACTUELLE — qui a validé, et quand — au même
    titre que profil_valide_par ailleurs dans le système. Elle ne qualifie PAS ce
    que la validation engage (pas de mention de responsabilité juridique). La date
    RÉUTILISE l'horodatage du dossier (audit_trail['timestamp']) — aucune date
    n'est générée ici.

    Deux états :
      · non validé (valide_par=None) → ⚠ ACTION REQUISE.
      · validé (valide_par=nom)      → ✔ trace factuelle (qui / quand).
    """
    mp = modele_production or {}
    if str(mp.get('famille', '')) != 'Deep Learning':
        return None
    nom = mp.get('modele', 'Deep Learning')
    if valide_par:
        # Date lisible JJ/MM/AAAA à partir de l'horodatage EXISTANT du dossier
        # (ISO 'AAAA-MM-JJThh:mm:ss'). On ne génère aucune date : on réutilise.
        _jour = str(date_validation or '').split('T')[0]     # 'AAAA-MM-JJ'
        _p = _jour.split('-')
        _date = f"{_p[2]}/{_p[1]}/{_p[0]}" if len(_p) == 3 else _jour
        _le = f" le {_date}" if _date else ""
        return (f"✔ Modèle Deep Learning retenu en production ({nom}) — "
                f"validé par « {valide_par} »{_le}.")
    return (f"⚠ ACTION REQUISE — modèle Deep Learning retenu en production ({nom}) : "
            f"validation actuarielle humaine requise avant déploiement, quel que soit "
            f"le statut RAG. Renseigner valide_par_actuaire_dl (nom de l'actuaire).")


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


# ═══════════════════════════════════════════════════════════════════════════════
#  LES BANDES DU RATIO A/E — SOURCE UNIQUE DE CE QUI EST « ACCEPTABLE »
# ═══════════════════════════════════════════════════════════════════════════════
#
# ⚠️⚠️ CONSTAT `charts/C2` : TROIS BANDES COEXISTAIENT DANS LE MÊME SYSTÈME.
#   · le rectangle vert de la figure       0,85 – 1,15   (le plus LARGE)
#   · le point VERT de la même figure      0,95 – 1,05
#   · le verrou qui plafonne le statut     0,90 – 1,10   (la DÉCISION)
# Mesuré : un A/E de 0,87 se dessinait DANS la bande verte, et le verrou
# avertissait. *La figure promettait une acceptabilité que la règle refusait.*
#
# ⚠️ LA DÉCISION VIT ICI, LA FIGURE LA LIT — jamais l'inverse. `charts_tarif`
# importe ces bornes ; ce module n'importe rien de lui (vérifié, aucun cycle).
#
# ⚠️⚠️ ET IL Y A UN HOMONYME, QUI NE DOIT PAS ÊTRE FUSIONNÉ. L'analyse PAR
# SEGMENT d'A6 gradue elle aussi sur `0,90 – 1,10` — mais là, c'est la bande
# VERTE (« modèle non biaisé sur ce segment »), avec un AMBRE à 0,80 – 1,20.
# Ici, sur une FENÊTRE de walk-forward, `0,90 – 1,10` est l'AMBRE et le VERT
# est plus serré. *Deux échelles, deux objets, les mêmes nombres.* Unifier les
# six sites sur une seule constante aurait mélangé les deux.

#: Bande ACCEPTABLE du ratio A/E d'une FENÊTRE de walk-forward. C'est elle qui
#: décide : hors de cette bande, le verrou refuse de conclure au VERT.
AE_FENETRE_ACCEPTABLE = (0.90, 1.10)

#: Bande STRICTE, le grain fin À L'INTÉRIEUR de la précédente : un A/E qui y
#: tombe est « non biaisé », pas seulement « acceptable ».
AE_FENETRE_STRICTE = (0.95, 1.05)


class EchecControleEffet(RuntimeError):
    """Le contrôle anti-fuite par l'effet n'a pas pu s'exécuter.

    Levée plutôt qu'avalée : ce contrôle est le garde-fou principal contre les
    fuites de données, et le seul qui ne dépende d'aucun nom de colonne. Son
    échec silencieux (return {} = « aucune fuite ») serait indiscernable d'un
    succès — c'est précisément le motif du bug V6. L'appelant doit décider :
    échouer, ou poursuivre en le SIGNALANT. Jamais l'ignorer.
    """


def motif_controle_effet_impossible(df, col_cible) -> str | None:
    """Pourquoi le contrôle par l'effet ne peut PAS s'exécuter sur cette cible —
    ou `None` s'il le peut.

    ⚠️⚠️ SOURCE UNIQUE DU CONSTAT `conformite/C1`. `detecter_fuites_par_effet`
    rendait `{}` **sans un mot** dans deux cas — cible absente du DataFrame, et
    cible de variance nulle — pendant que `construire_matrice_x` calculait
    `controle_effet_execute` AVANT l'appel, sur la seule présence des
    arguments : `not (df is None or not cibles)`. **La propriété attestait la
    FOURNITURE DES ARGUMENTS, pas l'EXÉCUTION DU CONTRÔLE.**

    Mesuré : cible absente du `df` → `controle_effet_execute = True`, fuite
    NON écartée, aucun avertissement. La fuite entrait dans la matrice X et
    l'objet livré à l'actuaire déclarait le garde-fou exécuté.

    ⚠️ C'est le motif que ce module est écrit pour interdire, reproduit dans la
    fonction qui l'interdit — le module le nomme lui-même deux fois (bug V6,
    BLOQUANT B2) : *« un résultat indiscernable de : le contrôle n'a pas
    tourné »*. Un contrôle dont on ne vérifie pas l'exécution n'est pas un
    contrôle.
    """
    if df is None:
        return ("aucun DataFrame fourni — le garde-fou n°4 ne peut pas "
                "s'exécuter")
    if not col_cible:
        return "aucune cible fournie — le garde-fou n°4 ne peut pas s'exécuter"
    if col_cible not in getattr(df, 'columns', []):
        return (f"la cible '{col_cible}' est ABSENTE des données soumises : "
                f"aucune corrélation ne peut être calculée, et AUCUNE colonne "
                f"n'a donc été examinée par le contrôle par l'effet")
    try:
        # ⚠️⚠️ ON TESTE L'ABSENCE DE VALEUR EXPLOITABLE, PAS L'ÉGALITÉ À ZÉRO.
        # Ma première version écrivait `float(serie.std()) == 0.0`. Sur une
        # colonne ENTIÈREMENT VIDE, `std()` vaut **NaN**, et `NaN == 0.0` est
        # **FAUX** : aucun motif n'était produit, `controle_effet_execute`
        # valait `True`, et le classeur qui part au CAC écrivait
        # « exécuté sur toutes les cibles » sur une cible qui n'existe pas.
        # ⚠️ **C'est `qualite/C1` — l'aveuglement au NaN — reproduit dans la
        # correction de `conformite/C1`, qui portait précisément sur un
        # contrôle qui s'atteste sans avoir rien examiné.** Le motif de cet
        # audit, dans le correctif de ce motif. *Toute comparaison sur un NaN
        # est fausse : on ne teste jamais une borne, on teste ce qui RESTE.*
        _valides = df[col_cible].astype(float).dropna()
        if _valides.empty:
            return (f"la cible '{col_cible}' est PRÉSENTE mais ENTIÈREMENT "
                    f"VIDE : aucune valeur exploitable, aucune corrélation "
                    f"calculable, et aucune colonne examinée par le contrôle "
                    f"par l'effet")
        if float(_valides.std()) == 0.0:
            return (f"la cible '{col_cible}' est CONSTANTE (variance nulle) : "
                    f"la corrélation est indéfinie, et aucune colonne n'a été "
                    f"examinée par le contrôle par l'effet")
    except (TypeError, ValueError) as exc:
        return (f"la cible '{col_cible}' n'est pas numérisable ({exc}) : le "
                f"contrôle par l'effet n'a examiné aucune colonne")
    except Exception as exc:
        # ⚠️⚠️ UN ÉCHEC INATTENDU RESTE BRUYANT ET TYPÉ — INV-11c.
        # `detecter_fuites_par_effet` lève `EchecControleEffet` dans ce cas
        # depuis le bug V6, et l'invariant l'exige : *« l'échec du contrôle par
        # l'effet doit LEVER, jamais retourner "aucune fuite" »*. Cette
        # fonction s'exécutant AVANT lui, une exception brute la traversait et
        # changeait le type levé. **La gate l'a attrapé, l'invariant a fait son
        # travail** : une source unique doit honorer le contrat aux DEUX
        # endroits, pas seulement là où il était écrit.
        _log = logger
        _log.error(
            f"[ANTI-FUITE PAR L'EFFET] ÉCHEC DU CONTRÔLE — "
            f"{type(exc).__name__}: {exc}. Le garde-fou principal contre les "
            f"fuites de données n'a PAS pu s'exécuter. Ne pas poursuivre comme "
            f"si tout allait bien."
        )
        raise EchecControleEffet(str(exc)) from exc
    return None


def reserve_controle_effet(df, col_cible) -> str | None:
    """Le contrôle par l'effet PEUT s'exécuter — mais pas sur toutes les lignes.

    ⚠️⚠️ UN EMPÊCHEMENT ET UNE RÉSERVE NE SONT PAS LA MÊME CHOSE, et les
    confondre casserait l'un ou l'autre. Un **empêchement** (voir
    `motif_controle_effet_impossible`) veut dire que le garde-fou n'a rien
    examiné : il rend `controle_effet_execute` faux. Une **réserve** veut dire
    qu'il a tourné sur un SOUS-ENSEMBLE : il s'est exécuté, et sa couverture
    est incomplète.

    ⚠️ *Une couverture partielle est un FAIT À PUBLIER, pas un défaut à
    arrondir* — dans un sens comme dans l'autre : l'arrondir au pire ferait
    croire que rien n'a été vérifié, l'arrondir au mieux ferait croire que tout
    l'a été. Une cible à moitié vide laissait le contrôle tourner sur la moitié
    des lignes **sans le dire**.
    """
    try:
        serie = df[col_cible].astype(float)
    except (TypeError, ValueError, KeyError):
        return None                      # l'empêchement l'aura déjà signalé
    n_total = len(serie)
    n_valides = int(serie.notna().sum())
    if n_total == 0 or n_valides == n_total:
        return None
    return (f"la cible '{col_cible}' porte {n_total - n_valides} valeur(s) "
            f"manquante(s) sur {n_total} : le contrôle par l'effet n'a examiné "
            f"que {n_valides} ligne(s) ({n_valides / n_total:.1%}). Sa "
            f"couverture est INCOMPLÈTE.")


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

    Retourne `{colonne: {'spearman': float, 'gini_normalise': float}}` pour
    toute feature dont le SIGNAL dépasse `seuil`. Le signal est
    `max(spearman, gini_normalise)` : on déclenche si l'UNE OU L'AUTRE des
    deux mesures dépasse — c'est-à-dire toute variable qui « connaît » déjà
    la réponse, que ce soit de façon monotone (Spearman) ou par son pouvoir
    de tri (Gini).

    ⚠️⚠️ CONSTAT `conformite/C9` — CE TEXTE DÉCRIVAIT UN CRITÈRE QUI N'ÉTAIT
    PLUS LE SIEN. Il annonçait « Retourne {colonne: corrélation} » et « la
    corrélation de Spearman … dépasse `seuil` ». Mesuré le 01/09 : la valeur
    rendue est un DICT de deux mesures, et le critère est leur MAXIMUM. Le
    Gini a été ajouté parce que Spearman seul ne pouvait pas se déclencher sur
    une cible à fort ex aequo (voir le bloc de commentaire du seuil).
    *Quand un comportement change, le texte qui l'accompagne se relit.*

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
    # ⚠️ SOURCE UNIQUE DES DEUX SORTIES MUETTES — constat `conformite/C1`.
    # Ces deux `return {}` existaient ici, et `construire_matrice_x` attestait
    # malgré tout l'exécution du contrôle. Le motif est désormais calculé par
    # UNE fonction que les deux endroits consultent : la sortie ne peut plus
    # être muette d'un côté et attestée de l'autre.
    if motif_controle_effet_impossible(df, col_cible) is not None:
        return (fuites, signaux_experience) if retourner_alertes else fuites
    try:
        import numpy as np
        y = df[col_cible].astype(float)
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

        # ⚠️⚠️ CONSTAT `conformite/C10` — CE QUE LE GARDE-FOU NE PEUT PAS LIRE,
        # IL LE DIT. Une colonne non numérique tombait dans le
        # `except (TypeError, ValueError): continue` en bas de boucle et
        # disparaissait SANS UN MOT. Mesuré : une cible binarisée en texte
        # (`libelle_gravite`) est totalement invisible, là où la MÊME
        # information en numérique est attrapée à Spearman 0,988.
        # *Un contrôle qui saute ce qu'il ne sait pas lire, en silence, rend
        # « aucune fuite trouvée » indiscernable de « pas regardé ».* C'est
        # mot pour mot la doctrine que le `except` global de cette fonction
        # écrit déjà — le saut interne la contredisait.
        non_examinees = []
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
                # ⚠️ ON ENREGISTRE, ON NE SE TAIT PLUS. Le `continue` reste :
                # une colonne illisible ne PEUT pas être corrélée, et lever
                # ici désactiverait le garde-fou entier pour une seule
                # colonne. Ce qui change, c'est qu'elle est NOMMÉE.
                non_examinees.append(c)
                continue
        if non_examinees:
            _log.warning(
                f"[ANTI-FUITE PAR L'EFFET — COUVERTURE INCOMPLÈTE] "
                f"{len(non_examinees)} colonne(s) NON NUMÉRIQUE(S) n'ont PAS "
                f"pu être examinées par le garde-fou n°4 sur la cible "
                f"'{col_cible}' : {', '.join(sorted(non_examinees))}. Une "
                f"fuite en texte — par exemple la cible binarisée en libellés "
                f"— y serait INVISIBLE. Ces colonnes ne sont protégées que par "
                f"les contrôles par le NOM, que l'audit V12 a démontrés "
                f"structurellement insuffisants."
            )
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


#: ⚠️⚠️ LA BASE D'UN GINI — CONSTAT `a4/C10`. Un Gini est un indice de
#: CONCORDANCE : il trie par la prédiction et cumule l'observé. Deux modèles
#: qui trient sur des grandeurs différentes ne rendent donc PAS le même
#: nombre, même à qualité identique.
#: MESURÉ le 27/08/2026 sur un portefeuille à exposition variable :
#:     base COMPTAGE 0,4339 · base UNITAIRE 0,3675 — soit +18,1 %
#:     à exposition CONSTANTE l'écart tombe à 0,0000
#: L'écart vient donc ENTIÈREMENT de la variation d'exposition, et il est
#: SYSTÉMATIQUEMENT favorable à la base comptage.
#: ⚠️ Ces constantes ne CORRIGENT rien : elles DÉCLARENT. Aligner les bases
#: changerait un Gini publié, donc potentiellement le modèle retenu, donc un
#: prix — c'est une décision, pas un nettoyage.
BASE_GINI_COMPTAGE = 'comptage'          # prédiction × exposition (offset)
BASE_GINI_UNITAIRE = 'unitaire'          # prédiction par unité d'exposition
BASE_GINI_COUT_MOYEN = 'cout_moyen'      # sévérité, sur les sinistrés seuls
BASE_GINI_NON_DECLAREE = None            # ⚠️ jamais supposée


#: Libellé lisible par un actuaire, pour chaque base.
LIBELLES_BASE_GINI = {
    BASE_GINI_COMPTAGE: "comptage prédit (exposition incorporée)",
    BASE_GINI_UNITAIRE: "prédiction unitaire (hors exposition)",
    BASE_GINI_COUT_MOYEN: "coût moyen (sinistrés seuls)",
}


def reserve_bases_gini_melangees(catalogue) -> str | None:
    """SOURCE UNIQUE — la phrase que lit l'actuaire quand un classement
    compare des Gini qui ne mesurent pas la même chose.

    ⚠️ Elle NE BLOQUE RIEN et ne change aucun nombre : elle rend VISIBLE que
    deux colonnes d'un même tableau ne sont pas sur le même pied. *Un écart de
    18 % qui vient de la convention, et non du modèle, ne doit pas se lire
    comme un écart de qualité.*

    ⚠️ Une base NON DÉCLARÉE est signalée comme telle — jamais assimilée à
    l'une des autres.
    """
    par_base: dict = {}
    for modele in catalogue or []:
        par_base.setdefault(modele.get('base_gini'), []).append(
            modele.get('modele', '?'))
    if len(par_base) <= 1:
        return None
    morceaux = []
    for base, modeles in par_base.items():
        libelle = (LIBELLES_BASE_GINI.get(base)
                   if base is not None else "base NON DÉCLARÉE")
        morceaux.append(f"{libelle} : {', '.join(sorted(modeles))}")
    return (
        "⚠ BASES DE GINI MÉLANGÉES DANS UN MÊME CLASSEMENT — "
        + " · ".join(morceaux)
        + ". Un Gini trie par la prédiction : deux modèles qui trient sur des "
          "grandeurs différentes ne rendent pas le même nombre à qualité "
          "égale. Mesuré sur un portefeuille à exposition variable : +18,1 % "
          "pour la base comptage, et 0,0 % à exposition constante. "
          "*L'écart de convention ne se lit pas comme un écart de qualité.*")


def meilleur_par_base(classement, modele_production=None) -> list:
    """Le MEILLEUR modèle de chaque base de Gini — constat `a4/C10`, suite.

    ⚠️⚠️ POURQUOI CE CHAMP NE S'APPELLE PAS `finalistes_par_base`. Mesuré sur
    un catalogue réel de 9 modèles : `GLM_POISSON` (comptage) score **1,0000**
    contre **0,1912** pour le meilleur unitaire. Ce ne sont pas deux
    finalistes — c'est un gagnant et un second lointain. *Une étiquette qui
    affirme une égalité que les chiffres ne montrent pas est le défaut que cet
    audit poursuit.*

    ⚠️ AUCUN SEUIL DE PROXIMITÉ. On présente TOUJOURS le meilleur de chaque
    base, quel que soit l'écart — même règle qu'`alternatives`, qui montre les
    trois suivants sans condition. *L'actuaire juge la proximité ; le code ne
    l'invente pas.* Le score étant normalisé par le gagnant, un écart de 10 %
    ne veut pas la même chose selon la dispersion du catalogue : fixer une
    coupure ici serait fabriquer un nombre.

    ⚠️ `rang_global` est publié À CÔTÉ du score : sans lui, deux lignes se
    liraient à égalité alors que l'une est 2ᵉ et l'autre 9ᵉ.

    ⚠️ `est_retenu` se DÉRIVE par comparaison au modèle de production — jamais
    écrit à la main : un booléen posé deviendrait faux le jour où le choix
    change ailleurs.

    ⚠️ Une base NON DÉCLARÉE (`None`) a sa propre ligne — jamais fondue dans
    une autre. Voir [`reserve_bases_gini_melangees`].
    """
    retenu = (modele_production or {}).get('modele')
    vu: dict = {}
    for rang, modele in enumerate(classement or [], start=1):
        base = modele.get('base_gini')
        if base in vu:                      # le classement est déjà trié
            continue
        vu[base] = {
            'base':         base,
            'base_libelle': (LIBELLES_BASE_GINI.get(base)
                             if base is not None else 'base NON DÉCLARÉE'),
            'modele':       modele.get('modele'),
            'score_global': modele.get('score_global'),
            'gini_test':    modele.get('gini_test'),
            'rang_global':  rang,
            'est_retenu':   modele.get('modele') == retenu,
        }
    return list(vu.values())


def reserve_arbitrage_contestable(meilleurs, modele_production=None) -> str | None:
    """SOURCE UNIQUE — la phrase qui dit qu'un choix automatique est discutable.

    ⚠️ Elle NE BLOQUE RIEN, ne plafonne aucun statut et ne change aucun euro :
    `modele_production` reste choisi automatiquement. *Un fail-safe qui met la
    chaîne hors service n'est pas un fail-safe.* Elle rend seulement le choix
    CONTESTABLE À VOIX HAUTE, pour que l'actuaire garde la main.

    ⚠️ `None` quand une seule base est représentée : il n'y a alors rien à
    contester, et une réserve qui se déclenche toujours n'informe plus de rien.
    """
    if not meilleurs or len(meilleurs) < 2:
        return None
    retenu = (modele_production or {}).get('modele') or '?'
    lignes = []
    for m in meilleurs:
        score = m.get('score_global')
        lignes.append(
            f"{m['modele']} ({m['base_libelle']}) score "
            f"{score if score is None else round(float(score), 4)}, "
            f"rang {m['rang_global']}")
    return (
        f"⚠ ARBITRAGE CONTESTABLE — le modèle retenu ({retenu}) l'a été par un "
        f"tri automatique sur `score_global`, alors que le catalogue contient "
        f"{len(meilleurs)} bases de Gini différentes : "
        + " · ".join(lignes)
        + ". Un Gini de base comptage est SYSTÉMATIQUEMENT flatté par rapport "
          "à un Gini unitaire dès que l'exposition varie — mesuré à +18,1 %, "
          "et 0,0 % à exposition constante. Le score est en outre normalisé "
          "par le gagnant : l'écart affiché n'est pas une distance absolue. "
          "*Le choix automatique tient ; il n'est pas pour autant établi.*")


#: Les trois verdicts du plafond de vraisemblance. ⚠️⚠️ IL Y EN A TROIS, ET PAS
#: DEUX : « je ne sais pas juger cette cible » n'est ni « plausible » ni
#: « implausible », et le confondre avec l'un des deux publie un faux.
VRAISEMBLANCE_PLAUSIBLE = 'PLAUSIBLE'
VRAISEMBLANCE_IMPLAUSIBLE = 'IMPLAUSIBLE'
VRAISEMBLANCE_NON_CALIBRE = 'NON_CALIBRE'
VRAISEMBLANCE_SANS_OBJET = 'SANS_OBJET'


def verdict_vraisemblance_gini(gini: float | None,
                               *,
                               cible_est_frequence: bool) -> str:
    """
    Le Gini trahit-il une fuite — ou ne sait-on pas en juger sur cette cible ?

    Un Gini de fréquence > 0,60 sur un portefeuille Non-Vie n'est pas un exploit :
    c'est une alerte. Les deux fuites bloquantes de l'histoire de ce module
    affichaient 0,91 (V8, `prime_pure`) et 0,92 (V12), contre 0,20 et 0,07 une
    fois corrigées.

    ⚠️⚠️ POURQUOI CETTE FONCTION A REMPLACÉ `gini_est_plausible` (constat
    `a6/C8`, 27/08/2026). L'ancienne rendait un **booléen** et son appelant
    unique passait `cible_est_frequence=True` **codé en dur**, alors que la
    cible peut valoir `cout_moyen` ou `prime_pure`. Les deux corrections
    évidentes étaient fausses, et c'est mesuré :

      · passer la vraie cible → l'ancienne rendait `True` **sans plafond**
        pour toute cible non-fréquence. MESURÉ : 0,91 et 0,99 passaient alors
        **sans une alerte** — sur `prime_pure`, LA CIBLE MÊME de la fuite V8
        qui a motivé ce garde-fou. *Le correctif évident retirait le filet là
        où il avait été tendu.*
      · laisser `True` → on applique à une prime pure un seuil calibré sur
        une fréquence.

    ⚠️ Le seuil `GINI_PLAUSIBLE_MAX_FREQUENCE` n'est PAS transposable : la
    littérature citée (GLM de fréquence auto entre 0,15 et 0,35) ne dit rien
    de la prime pure. **Inventer un nombre ici serait le défaut que cet audit
    poursuit.** La fonction DÉCLARE donc qu'elle ne sait pas juger, au lieu de
    répondre « plausible ».

    ⚠️ ET LE NOM A CHANGÉ EXPRÈS. `gini_est_plausible` était un prédicat : tout
    appelant écrivait `if not gini_est_plausible(...)`. Un retour à trois états
    sous ce nom aurait été **silencieusement faux** — `NON_CALIBRE` est une
    chaîne vraie, l'alerte n'aurait plus jamais tiré. En renommant, tout
    appelant resté en arrière échoue **bruyamment**, jamais en silence.

    Référence : ACPR-2022-P-01 §4.3 (vraisemblance des performances publiées).
    """
    if gini is None:
        return VRAISEMBLANCE_SANS_OBJET   # rien à juger (gate de disponibilité)
    if not cible_est_frequence:
        return VRAISEMBLANCE_NON_CALIBRE
    return (VRAISEMBLANCE_PLAUSIBLE
            if float(gini) <= GINI_PLAUSIBLE_MAX_FREQUENCE
            else VRAISEMBLANCE_IMPLAUSIBLE)


def reserve_vraisemblance_non_calibree(cible: str | None,
                                       gini: float | None) -> str | None:
    """SOURCE UNIQUE — la phrase que lit l'actuaire quand le plafond ne sait
    pas juger sa cible. ⚠️ Sans elle, l'absence de contrôle serait INVISIBLE,
    et c'est précisément ce qui distingue une réserve d'un silence.
    """
    if cible is None or gini is None:
        return None
    return (f"⚠ PLAFOND DE VRAISEMBLANCE NON CALIBRÉ pour la cible "
            f"'{cible}' — Gini = {float(gini):.4f}. Le seuil "
            f"{GINI_PLAUSIBLE_MAX_FREQUENCE} est calibré sur la FRÉQUENCE ; "
            f"aucune borne publiée ne s'applique à cette cible. Le contrôle "
            f"anti-fuite par la performance n'a donc PAS été exercé ici : "
            f"il reste à faire par l'examen des variables.")


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


# =============================================================================
#  LE GINI D'UN MODÈLE : ANTI-SÉLECTION, ET ABSENCE DE MESURE
# =============================================================================
#
# ⚠️⚠️ DEUX SITUATIONS QUI N'ONT RIEN À VOIR, ET QU'IL NE FAUT SURTOUT PAS
# TRAITER PAREIL. C'est l'arbitrage de Selasse du 03/09/2026, et il prolonge
# le constat `a3/C6` :
#
#   Gini MESURÉ et NÉGATIF  → le modèle discrimine À L'ENVERS. Ce n'est pas
#       une question de performance, c'est une question de VALIDITÉ : il fait
#       payer moins les mauvais risques. **Le statut passe ROUGE**, que le
#       modèle soit retenu en production ou non.
#
#   Gini NON MESURABLE (`None`) → on ne sait pas. **Cela ne colore RIEN.**
#       Dégrader reviendrait à confondre « pas pu mesurer » avec « mesuré et
#       mauvais » — exactement la confusion que `a3/C6` a supprimée en
#       remplaçant le zéro fabriqué par `None`. On publie une RÉSERVE.
#
# > *Une absence de mesure se déclare ; elle ne se convertit pas en verdict.*
#
# ⚠️ POURQUOI A6 NE SUFFIT PAS, ET C'EST MESURÉ. A6 force ROUGE sur un Gini
# négatif — mais **seulement pour le modèle de PRODUCTION** (son
# `_calculer_statut_rag` ne regarde que le retenu). Un GLM anti-sélectif qui
# ne gagne pas l'arbitrage était donc journalisé par son agent et publié
# dans AUCUN statut. C'est ce trou que ces fonctions ferment.

#: Les trois GLM d'A3. `poisson` vise la fréquence, `gamma` le coût moyen,
#: `tweedie` la prime pure — c'est ce dernier qui concourt chez A6 sur la
#: cible par défaut, les deux autres étant écartés par le filtre de cible.
MODELES_GLM = ('poisson', 'gamma', 'tweedie')

#: ⚠️ Le vocabulaire de l'état d'un Gini. `ABSENT` n'est PAS `NON_MESURE` :
#: une clé qui manque dit qu'aucun modèle de ce type n'a été ajusté ; un
#: `None` dit qu'il l'a été et que son Gini n'a pas pu être calculé.
GINI_ABSENT = 'ABSENT'
GINI_NON_MESURE = 'NON_MESURE'


def etats_gini(metriques: dict | None,
               modeles: tuple = MODELES_GLM) -> dict[str, object]:
    """L'état du Gini de chaque modèle : une valeur, `ABSENT`, ou `NON_MESURE`.

    ⚠️ TROIS ÉTATS, PAS DEUX. Les confondre est la racine du défaut que
    `a3/C6` a fermé : un modèle jamais ajusté et un modèle dont le Gini n'a
    pas pu être calculé ne se disent pas de la même façon, et aucun des deux
    ne vaut zéro.
    """
    etats: dict[str, object] = {}
    m = metriques if isinstance(metriques, dict) else {}
    for nom in modeles:
        bloc = m.get(nom)
        if not isinstance(bloc, dict) or 'gini' not in bloc:
            etats[nom] = GINI_ABSENT
            continue
        valeur = bloc['gini']
        if valeur is None:
            etats[nom] = GINI_NON_MESURE
        elif (isinstance(valeur, (int, float))
                and not isinstance(valeur, bool)
                and math.isfinite(valeur)):
            etats[nom] = float(valeur)
        else:
            # ⚠️ Un Gini d'un type inattendu ne se convertit pas au jugé : il
            # est traité comme NON MESURÉ, donc réservé, jamais coloré.
            #
            # ⚠️⚠️ ET `math.isfinite` EST LA MOITIÉ QUI MANQUAIT. Mesuré le
            # 03/09/2026 : A5 publiait un `nan`, qui EST un `float` et
            # passait donc par la branche du dessus. Consequence : `nan < 0`
            # etant faux, l'anti-selection ne tirait pas ; `nan is None`
            # etant faux, la reserve ne se declenchait pas non plus.
            #   *Un `nan` franchit les gardes ecrites pour un nombre ET
            #   celles ecrites pour une absence.*
            etats[nom] = GINI_NON_MESURE
    return etats


def modeles_anti_selectifs(metriques: dict | None,
                           modeles: tuple = MODELES_GLM) -> list[tuple]:
    """Les modèles dont le Gini est MESURÉ et STRICTEMENT négatif.

    ⚠️ Un `None` n'entre jamais ici : `None < 0` lève, et surtout une absence
    de mesure n'est pas un constat d'anti-sélection.
    """
    return [(nom, etat) for nom, etat in etats_gini(metriques, modeles).items()
            if isinstance(etat, float) and etat < 0]


def statut_anti_selection(statut: str, metriques: dict | None,
                          modeles: tuple = MODELES_GLM) -> str:
    """ROUGE dès qu'un modèle ajusté discrimine à l'envers.

    ⚠️ CE N'EST PAS UN PLAFOND, C'EST UN PLANCHER INVERSÉ. `plafonner_statut_
    si_ampute` ramène VERT à AMBRE ; ici on force ROUGE depuis n'importe quel
    statut, parce qu'un modèle anti-sélectif n'est pas « moins bon » : il est
    ruineux. Un portefeuille tarifé à l'envers organise sa propre
    anti-sélection.

    ⚠️ Et il s'applique MÊME SI LE MODÈLE N'EST PAS RETENU : le statut d'un
    agent décrit le travail de cet agent, pas seulement la part qui gagne
    l'arbitrage aval.
    """
    return 'ROUGE' if modeles_anti_selectifs(metriques, modeles) else statut


def synthese_anti_selection(metriques: dict | None,
                            modeles: tuple = MODELES_GLM) -> str | None:
    """SOURCE UNIQUE — la RAISON du ROUGE, à publier dans tout livrable.

    Rend `None` quand aucun modèle n'est anti-sélectif : il n'y a alors rien
    à dire, et une ligne vide dans un rapport est du bruit.
    """
    fautifs = modeles_anti_selectifs(metriques, modeles)
    if not fautifs:
        return None
    detail = ", ".join(f"{nom} (Gini = {g:+.4f})".replace('.', ',')
                       for nom, g in fautifs)
    pluriel = 's' if len(fautifs) > 1 else ''
    return (
        f"⚠ ANTI-SÉLECTION — {len(fautifs)} modèle{pluriel} discrimine"
        f"{'nt' if len(fautifs) > 1 else ''} À L'ENVERS : {detail}. "
        f"Un Gini négatif signifie que les primes les plus FAIBLES sont "
        f"attribuées aux risques les plus ÉLEVÉS. Le statut est forcé à "
        f"ROUGE même si ce modèle n'est pas retenu en production : il est "
        f"inutilisable en l'état, et le publier sans le dire exposerait le "
        f"portefeuille à une sélection adverse."
    )


def synthese_gini_non_mesure(metriques: dict | None,
                             modeles: tuple = MODELES_GLM) -> str | None:
    """SOURCE UNIQUE — la RÉSERVE, qui ne colore RIEN.

    ⚠️⚠️ ELLE NE JUGE PAS, ET C'EST TOUT SON OBJET. Le statut reste ce qu'il
    était. Ce qui est publié, c'est ce qui n'a pas pu être mesuré et ce que
    cette absence coûte à celui qui signe — à lui d'en tirer les
    conséquences, pas à ce module.

    Rend `None` quand tous les Ginis attendus sont mesurés.
    """
    etats = etats_gini(metriques, modeles)
    non_mesures = [n for n, e in etats.items() if e == GINI_NON_MESURE]
    if not non_mesures:
        return None
    mesures = [n for n, e in etats.items() if isinstance(e, float)]
    reste = (f"Les {len(mesures)} autre(s) ({', '.join(mesures)}) le sont."
             if mesures else
             "AUCUN Gini n'a pu être mesuré : le pouvoir discriminant de "
             "cette calibration est entièrement inconnu.")
    return (
        f"RÉSERVE — Gini NON MESURÉ pour : {', '.join(non_mesures)}. "
        f"{reste} Un Gini non mesurable n'est pas un Gini nul : il n'est "
        f"pas publié à zéro, et il ne dégrade AUCUN statut — le confondre "
        f"avec un pouvoir discriminant nul serait une note fabriquée. "
        f"Conséquence à connaître : A6 ÉCARTE de l'arbitrage tout modèle "
        f"non noté, ce qui peut réduire la comparaison à un seul candidat."
    )


# =============================================================================
#  ÉVALUATION IMPOSSIBLE — quand AUCUN modèle ne peut être départagé
# =============================================================================
#
# ⚠️⚠️ DEUX IMPOSSIBILITÉS DE NATURE DIFFÉRENTE, ET C'EST TOUTE LA CONCEPTION.
#
#   EN AMONT, DÉJÀ EN PLACE — `CalibrationImpossible` (A3) : le jeu
#   d'ENTRAÎNEMENT ne porte aucun sinistre. Le maximum de vraisemblance de
#   l'intercept vaut log(0) : aucun modèle n'existe, aucun tarif n'est
#   possible. *On ne bricole pas un modèle sur rien, on le DIT.*
#
#   ICI — `ArbitrageImpossible` : le jeu d'ENTRAÎNEMENT porte des sinistres,
#   les modèles sont donc CALIBRÉS et utilisables ; c'est le jeu de TEST qui
#   n'en porte aucun. Ce qui est impossible n'est pas l'ajustement, c'est le
#   CLASSEMENT.
#
# > *On peut ajuster, on ne peut pas départager. Choisir quand même serait
# > tirer au sort le modèle qui fixera des primes.*
#
# ⚠️ ON REFUSE LA SÉLECTION, PAS LA CALIBRATION. Arbitré le 03/09/2026 :
# refus sec, sans échappement. Les calibrations restent dans `result_a3`,
# `result_a4`, `result_a5` — le travail n'est pas détruit, la DÉCISION est
# rendue à l'actuaire.
#
# ⚠️⚠️ ET LE `0.0` FABRIQUÉ N'EST PAS CORRIGÉ ICI — MESURÉ, PAS SUPPOSÉ.
# `_calculer_gini` rend encore `0.0` sur un jeu non mesurable, dans les trois
# agents (A3 : 3 branches, A4 : 3, A5 : 2 — et A5 n'a AUCUNE garde sur la
# somme nulle, il divise par zéro et son `except` rattrape). Le convertir en
# `None` casserait **196 lignes de production, dont 111 DANS les trois
# agents**, relevées par AST le 03/09/2026 : chacune exigerait de décider quoi
# AFFICHER, soit 111 occasions de fabriquer une nouvelle valeur sur le chemin
# qui produit le tarif. Ce qui compte — *ne jamais SÉLECTIONNER sur une note
# fabriquée* — est obtenu ici sans y toucher : le diagnostic voyage à côté de
# la valeur, et l'arbitrage s'arrête avant de la lire.


class ArbitrageImpossible(ValueError):
    """Aucun modèle ne peut être ÉVALUÉ, donc aucun ne peut être choisi.

    ⚠️ Hérite de `ValueError` comme `CalibrationImpossible`, et pour la même
    raison : c'est déjà le type que lève A6 quand son catalogue est vide. Un
    appelant qui filtre `except ValueError` continue de fonctionner — on
    enrichit le message, on ne déplace pas le type.
    """


#: Les causes d'une évaluation impossible. ⚠️ Elles se DÉRIVENT de faits
#: mesurés sur le fichier, jamais d'une supposition : c'est la différence
#: entre un diagnostic et une devinette.
#: ⚠️ LES COLONNES QUI DÉCLENCHENT UN DÉCOUPAGE TEMPOREL, ET LEUR ORDRE.
#: Cette liste vivait TRIPLÉE — une copie identique dans `_preparer_donnees`
#: d'A3, d'A4 et d'A5. Elles concordaient au 03/09/2026, vérifié ligne à
#: ligne. Le diagnostic ci-dessous NOMME la colonne qui a servi au
#: découpage : le laisser en deviner une quatrième copie l'exposerait à
#: nommer la mauvaise le jour où une liste dérive.
#:   *Un diagnostic qui redérive ce qu'il décrit finit par décrire autre
#:   chose.*
COLONNES_TEMPORELLES = ('annee_souscription', 'date_souscription',
                        'annee', 'year')


def colonne_temporelle(colonnes) -> str | None:
    """La colonne qui gouverne le découpage temporel, ou `None`.

    Source unique : A3, A4, A5 et le diagnostic lisent la MÊME.
    """
    # ⚠️ PAS DE `colonnes or ()` : sur un `Index` pandas, l'évaluation
    # booléenne LÈVE (« The truth value of a Index is ambiguous »). Les
    # trois appelants passent `df.columns`. *Un idiome Python courant n'est
    # pas neutre sur un objet qui redéfinit `__bool__`.*
    disponibles = set(colonnes) if colonnes is not None else set()
    return next((c for c in COLONNES_TEMPORELLES if c in disponibles), None)


CAUSE_CIBLE_NON_RENSEIGNEE = 'cible_non_renseignee_en_test'
CAUSE_PORTEFEUILLE_PETIT = 'portefeuille_trop_petit'
CAUSE_TEST_PERIODE_RECENTE = 'test_periode_recente'
CAUSE_DECOUPAGE_ALEATOIRE = 'decoupage_aleatoire'
CAUSE_INDETERMINEE = 'indeterminee'

#: ⚠️ LA RÈGLE DE TROIS, ET ELLE EST DÉJÀ DOCTRINE ICI : la docstring de
#: `CalibrationImpossible` l'invoque. À zéro événement observé sur n
#: expositions, la borne haute à 95 % de la fréquence vaut 3/n — donc aucune
#: fréquence inférieure à 3/n n'est distinguable de zéro.
#: Sous 3 sinistres ATTENDUS, observer 0 n'apprend donc rien : ce n'est pas
#: une information sur le portefeuille, c'est une limite du découpage.
SEUIL_REGLE_DE_TROIS = 3.0


def diagnostiquer_evaluation(
    *,
    cible: str,
    n_train: int,
    n_test: int,
    sinistres_train: float,
    sinistres_test: float,
    colonne_temporelle: str | None = None,
    periode_train: tuple | None = None,
    periode_test: tuple | None = None,
    exposition_test: float | None = None,
    cible_vide_en_test: bool = False,
) -> dict | None:
    """Pourquoi l'évaluation est-elle impossible ? `None` si elle ne l'est pas.

    ⚠️⚠️ TOUT EST DÉRIVÉ DES FAITS PASSÉS, RIEN N'EST DEVINÉ. La fonction ne
    reçoit que des grandeurs observables sur le fichier de l'actuaire, et
    l'ordre de priorité des causes est actuariel, pas arbitraire :

      1. `CIBLE_NON_RENSEIGNEE` — le test porte des lignes et de l'exposition
         mais la cible y est vide/nulle PARTOUT alors qu'elle est renseignée
         en entraînement. Signature d'une jointure qui a perdu les sinistres.
      2. `PORTEFEUILLE_PETIT` — moins de trois sinistres ATTENDUS en test.
         ⚠️ ELLE PASSE AVANT LA CAUSE TEMPORELLE, et c'est délibéré : sous
         trois attendus, observer zéro n'est PAS remarquable, donc n'accuse
         rien. Conclure à une sous-déclaration serait une affirmation que la
         mesure ne porte pas.
      3. `TEST_PERIODE_RECENTE` — découpage temporel, et le test est la
         période la plus récente. Là, zéro EST remarquable, et la cause
         actuarielle dominante est la sous-déclaration des exercices récents.
      4. `DECOUPAGE_ALEATOIRE` — pas de colonne temporelle : la cause
         temporelle ne s'applique pas, et l'absence de cette colonne est un
         défaut en soi (le Gini mesuré serait optimiste).

    ⚠️ AUCUN SEUIL DE FIABILITÉ N'EST INVENTÉ. `SEUIL_REGLE_DE_TROIS` est le
    seuil de l'IMPOSSIBILITÉ (rien n'est distinguable en dessous), pas celui
    de la fiabilité — un Gini sur cinq sinistres est mesurable et ne vaut
    rien. Ce second seuil est un choix actuariel : le nombre attendu est
    PUBLIÉ, et l'actuaire juge.
    """
    if sinistres_test > 0:
        return None

    # ⚠️⚠️ L'ARTICULATION AVEC LE REFUS AMONT EST APPLIQUÉE ICI, PAS SUPPOSÉE.
    # J'avais écrit en concevant que le cas « aucun sinistre NULLE PART » était
    # « exclu par construction », le refus amont l'ayant déjà arrêté. **C'EST
    # FAUX, et le pipeline réel l'a montré** : `CalibrationImpossible` tire
    # pendant l'AJUSTEMENT, donc APRÈS ce diagnostic. Sans cette garde, le
    # message publiait « le modèle est CALIBRÉ (l'entraînement porte
    # 0 sinistre) » — une phrase que la ligne suivante du journal démentait.
    #
    #   *Une articulation décrite dans une conception n'est pas une
    #   articulation tenue : c'est l'ordre d'exécution qui décide, et il ne
    #   se déduit pas d'un schéma.*
    #
    # Sans sinistre à l'entraînement, il n'y a pas de problème d'ÉVALUATION :
    # il n'y a pas de modèle du tout, et c'est `CalibrationImpossible` qui
    # porte ce message-là.
    if sinistres_train <= 0:
        return None

    frequence = (sinistres_train / n_train) if n_train else 0.0
    attendus = frequence * n_test

    facteurs: list[str] = []
    if colonne_temporelle is None:
        facteurs.append(CAUSE_DECOUPAGE_ALEATOIRE)
    if attendus < SEUIL_REGLE_DE_TROIS:
        facteurs.append(CAUSE_PORTEFEUILLE_PETIT)
    if cible_vide_en_test:
        facteurs.append(CAUSE_CIBLE_NON_RENSEIGNEE)
    if colonne_temporelle is not None and periode_test:
        facteurs.append(CAUSE_TEST_PERIODE_RECENTE)

    if cible_vide_en_test:
        cause = CAUSE_CIBLE_NON_RENSEIGNEE
    elif attendus < SEUIL_REGLE_DE_TROIS:
        cause = CAUSE_PORTEFEUILLE_PETIT
    elif colonne_temporelle is not None:
        cause = CAUSE_TEST_PERIODE_RECENTE
    elif colonne_temporelle is None:
        cause = CAUSE_DECOUPAGE_ALEATOIRE
    else:                                              # pragma: no cover
        cause = CAUSE_INDETERMINEE

    return {
        'cible': cible,
        'cause': cause,
        'facteurs': [f for f in facteurs if f != cause],
        'n_train': int(n_train),
        'n_test': int(n_test),
        'sinistres_train': float(sinistres_train),
        'sinistres_test': float(sinistres_test),
        'frequence_train': float(frequence),
        'sinistres_attendus_test': float(attendus),
        'borne_regle_de_trois': (SEUIL_REGLE_DE_TROIS / n_test
                                 if n_test else None),
        'colonne_temporelle': colonne_temporelle,
        'periode_train': periode_train,
        'periode_test': periode_test,
        'exposition_test': exposition_test,
    }


def _periode(bornes: tuple | None) -> str:
    """« 2019–2022 », ou « 2022 » si les bornes coïncident."""
    if not bornes:
        return 'période inconnue'
    debut, fin = bornes
    return f'{debut}' if str(debut) == str(fin) else f'{debut}–{fin}'


def cause_mesuree(diag: dict) -> str:
    """La CAUSE, en une phrase, adossée aux chiffres du fichier."""
    n_test = diag['n_test']
    cause = diag['cause']

    # ⚠️ LE FORMATAGE PASSE PAR `core/format_fr`, PAS PAR UN `replace` LOCAL.
    # Ma première version faisait `.replace(',', ' ')` sur la phrase ENTIÈRE
    # pour transformer les séparateurs de milliers : elle mangeait aussi les
    # virgules de la prose (« la période 2023  la plus récente »). *Un
    # remplacement global appliqué à une phrase corrige un chiffre et casse
    # le texte autour.*
    n_test_f = nombre(n_test)
    attendus_f = nombre(diag['sinistres_attendus_test'], 1)
    sin_train_f = nombre(diag['sinistres_train'])

    if cause == CAUSE_CIBLE_NON_RENSEIGNEE:
        expo = diag.get('exposition_test')
        expo_txt = f" et {nombre(expo)} d'exposition" if expo else ""
        return (
            f"Le jeu de test porte {n_test_f} ligne(s){expo_txt}, mais la "
            f"colonne « {diag['cible']} » y est VIDE OU NULLE PARTOUT, alors "
            f"qu'elle est renseignée sur l'entraînement "
            f"({sin_train_f} sinistre(s)). Ce motif est la "
            f"signature d'une jointure qui a perdu les sinistres récents."
        )

    if cause == CAUSE_PORTEFEUILLE_PETIT:
        return (
            f"Le portefeuille compte {nombre(diag['n_train'] + n_test)} "
            f"ligne(s). Avec un découpage 80/20, le test n'en reçoit que "
            f"{n_test_f}, pour une fréquence observée de "
            f"{nombre(diag['frequence_train'], 4)} — soit {attendus_f} "
            f"sinistre(s) ATTENDU(S). En observer zéro n'est donc pas "
            f"remarquable : sous la règle de trois, aucune fréquence "
            f"inférieure à 3/{n_test_f} = "
            f"{nombre(diag['borne_regle_de_trois'], 5)} n'est distinguable "
            f"de zéro. Ce ne sont pas vos données qui manquent, c'est le "
            f"découpage qui est trop fin pour elles."
        )

    if cause == CAUSE_TEST_PERIODE_RECENTE:
        return (
            f"Le découpage est TEMPOREL sur « {diag['colonne_temporelle']} » : "
            f"le test est la période {_periode(diag['periode_test'])}, la plus "
            f"récente. Elle porte 0 sinistre, alors que la période "
            f"d'entraînement {_periode(diag['periode_train'])} en porte "
            f"{sin_train_f} et que {attendus_f} étaient attendus. "
            f"Un exercice récent est presque toujours SOUS-DÉCLARÉ : les "
            f"sinistres survenus n'y sont pas encore tous déclarés ni "
            f"évalués."
        )

    if cause == CAUSE_DECOUPAGE_ALEATOIRE:
        return (
            f"Aucune colonne temporelle (annee_souscription, "
            f"date_souscription, annee, year) n'a été trouvée : le découpage "
            f"est ALÉATOIRE. Le test est un tirage de {n_test_f} ligne(s) qui "
            f"ne porte aucun sinistre, pour {attendus_f} attendu(s)."
        )

    return (                                            # pragma: no cover
        f"Le jeu de test porte {n_test_f} ligne(s) et aucun sinistre, pour "
        f"{attendus_f} attendu(s). Les signaux disponibles ne désignent pas "
        f"une cause : elle n'est pas établie."
    )


def conseil_actionnable(diag: dict) -> str:
    """CE QUE L'ACTUAIRE PEUT FAIRE — apparié à la cause, jamais générique.

    ⚠️ Un message d'erreur qui dit seulement ce qui ne va pas laisse son
    lecteur devant un fichier qu'il ne sait pas corriger. Chaque conseil
    ci-dessous nomme un GESTE, pas une intention.
    """
    cause = diag['cause']

    if cause == CAUSE_CIBLE_NON_RENSEIGNEE:
        return (
            "Vérifiez l'extraction : le nombre de sinistres PAR PÉRIODE doit "
            "décroître régulièrement vers la fin, jamais tomber à zéro d'un "
            "coup. Contrôlez la jointure sur la table de sinistres — une "
            "jointure gauche mal bornée perd les exercices récents."
        )

    if cause == CAUSE_PORTEFEUILLE_PETIT:
        return (
            "N'évaluez pas sur un holdout unique à cette taille : une "
            "validation croisée ou un bootstrap utilise TOUT le portefeuille "
            "au lieu d'en réserver 20 %. À défaut, tarifez sur un modèle "
            "IMPOSÉ et signé plutôt que sélectionné — le choix redevient "
            "alors une décision d'actuaire, pas un tirage."
        )

    if cause == CAUSE_TEST_PERIODE_RECENTE:
        bornes = diag.get('periode_test') or ()
        recente = bornes[0] if bornes else None
        relance = (f" Relancez en arrêtant l'observation avant {recente}."
                   if recente is not None else "")
        return (
            "Excluez la période la plus récente de l'évaluation, ou "
            "fournissez une date d'arrêté et un délai de déclaration pour la "
            "retraiter." + relance +
            " Si vous devez conserver cette période, l'évaluation exige des "
            "sinistres SURVENUS ET DÉCLARÉS, pas seulement des contrats."
        )

    if cause == CAUSE_DECOUPAGE_ALEATOIRE:
        return (
            "Ajoutez une colonne d'année de souscription "
            "(« annee_souscription ») : sans elle le découpage est aléatoire, "
            "et un Gini mesuré ainsi est OPTIMISTE — de l'information future "
            "entre dans l'entraînement."
        )

    return (                                            # pragma: no cover
        "Vérifiez que le fichier porte des sinistres sur la période "
        "d'évaluation, et non seulement sur celle d'entraînement."
    )


def phrase_evaluation_impossible(diag: dict, modele: str) -> str:
    """Le message AU NIVEAU AGENT — factuel, sans verdict.

    ⚠️ Il dit que le modèle est CALIBRÉ. C'est la moitié qu'on oublie : un
    actuaire qui lit « Gini non mesuré » sans cette précision croit son
    modèle inutilisable, alors qu'il ne l'est pas.
    """
    return (
        f"GINI NON MESURÉ — « {modele} » sur la cible « {diag['cible']} ». "
        f"Le jeu de test porte {nombre(diag['n_test'])} ligne(s) et "
        f"{nombre(diag['sinistres_test'])} sinistre(s). Le modèle est CALIBRÉ "
        f"(l'entraînement porte {nombre(diag['sinistres_train'])} sinistre(s) "
        f"sur {nombre(diag['n_train'])} lignes) : c'est son ÉVALUATION qui "
        f"est impossible, pas son ajustement. Un Gini n'est pas publié à "
        f"zéro — un zéro signifierait « aucun pouvoir discriminant mesuré », "
        f"ce que rien ne fonde ici."
    )


def doit_refuser_arbitrage(diagnostics: list, sources: list) -> bool:
    """Faut-il refuser de choisir ? `True` si PLUS AUCUNE source n'est évaluable.

    ⚠️⚠️ TOUS, PAS AU MOINS UN. Si un seul agent a pu évaluer ses modèles, la
    comparaison garde un sens — réduite, et `reserve_arbitrage` le dit déjà.
    Refuser dès qu'UN agent trébuche interdirait des arbitrages parfaitement
    fondés.

    ⚠️ ET `sources` NE PEUT PAS ÊTRE VIDE. Sans aucun agent en amont il n'y a
    rien à arbitrer, mais ce n'est pas ce refus-ci : c'est le refus existant
    sur catalogue vide, qui porte un autre message.

    Extrait de `run()` À DESSEIN : une décision inline ne s'éprouve que par
    une intégration lourde, et un contrôle qu'on renonce à écrire est un
    contrôle qui n'existe pas.
    """
    return bool(sources) and len(diagnostics) == len(sources)


def message_arbitrage_impossible(diag: dict, modeles: list) -> str:
    """LE MESSAGE D'A6 — celui que l'actuaire lira quand rien ne sort.

    Trois blocs, dans cet ordre : ce qui est impossible et pourquoi ce n'est
    PAS une perte de travail ; la cause mesurée ; le geste à faire.
    """
    noms = ", ".join(str(m) for m in modeles) if modeles else "aucun"
    return (
        f"ARBITRAGE IMPOSSIBLE — aucun des {len(modeles)} modèle(s) ajusté(s) "
        f"sur la cible « {diag['cible']} » n'a pu être ÉVALUÉ ({noms}).\n"
        f"\n"
        f"Ces modèles sont CALIBRÉS et disponibles dans result_a3 / "
        f"result_a4 / result_a5. Ce qui est impossible, c'est de les "
        f"CLASSER : leur Gini de test n'existe pas. Les départager sur des "
        f"notes fabriquées reviendrait à tirer au sort le modèle qui fixera "
        f"des primes.\n"
        f"\n"
        f"CAUSE LA PLUS PROBABLE, MESURÉE SUR VOS DONNÉES — "
        f"{cause_mesuree(diag)}\n"
        f"\n"
        f"CE QUE VOUS POUVEZ FAIRE — {conseil_actionnable(diag)}\n"
        f"\n"
        f"AUCUN TARIF N'EST PRODUIT : les calibrations restent valides, "
        f"c'est la SÉLECTION qui est refusée."
    )
