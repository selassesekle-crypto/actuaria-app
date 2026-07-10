"""
ActuarIA — Conformité réglementaire partagée (Direction Non-Vie · Tarification)

Module créé suite à l'audit V7 (anomalie BLOQUANTE #1) : le filtre
d'exclusion des variables de genre (CJUE C-236/09, arrêt Test-Achats du
1er mars 2011) était implémenté de façon inconditionnelle dans A3 (GLM)
uniquement — A4 (Machine Learning) et A5 (Deep Learning) n'avaient AUCUN
filtre de ce type. Une colonne de genre numérique (ex. sexe=0/1,
sexe_enc, fournie telle quelle par un client ou pré-encodée hors du
pipeline standard A2) pouvait donc atteindre la matrice de features des
modèles ML/DL — et A6 peut retenir un tel modèle en production, ce que
l'audit V7 a démontré par exécution réelle.

Cause racine identifiée par l'audit : une règle de conformité correcte
à un endroit (A3), jamais propagée ailleurs. Ce module est la réponse
structurelle recommandée : une SOURCE UNIQUE de la liste des variables
interdites, partagée par tous les agents qui sélectionnent des features
(A3, A4, A5), pour éliminer par construction le risque de propagation
partielle d'un futur correctif de conformité — le même principe déjà
appliqué à la mise en forme Excel (excel_helpers.py, audit V4 point #12).

Réf. : Arrêt CJUE C-236/09 (Test-Achats, 1er mars 2011), Directive
2004/113/CE — s'applique aux primes et prestations d'assurance en
général, pas seulement à l'assurance auto.
"""

import logging
from typing import List, Optional

logger = logging.getLogger('actuaria.tarif.conformite')

# ── Colonnes interdites — INCONDITIONNEL ──────────────────────────────────────
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


def filtrer_genre(
    feature_names: List[str],
    contexte: str = '',
    logger_agent: Optional[logging.Logger] = None,
) -> List[str]:
    """
    Retire toute colonne de genre d'une liste de noms de features,
    en journalisant explicitement (niveau WARNING) toute suppression
    effective — traçabilité requise pour l'audit ACPR.

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
    avant = set(feature_names)
    apres = [f for f in feature_names if f not in COLS_GENRE_INTERDITES]
    supprimees = avant - set(apres)
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
# sans lister chaque combinaison. Précis : aucun facteur tarifaire a priori
# légitime (age, bonus_malus, puissance, zone...) ne contient ces racines.
COLS_FAMILLE_CIBLE_STEMS = [
    'prime_pure', 'cout_total_sinistres', 'cout_moyen',
    'lambda_freq', 'nb_sinistres',
]


def _est_derivee_sinistralite(nom: str) -> bool:
    """True si le nom de colonne est une grandeur dérivée de la sinistralité
    observée (famille cible), y compris ses variantes log_/_obs/_annuel."""
    base = nom[4:] if nom.startswith('log_') else nom
    if base in COLS_FAMILLE_CIBLE or nom in COLS_FAMILLE_CIBLE:
        return True
    return any(stem in nom for stem in COLS_FAMILLE_CIBLE_STEMS)


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
