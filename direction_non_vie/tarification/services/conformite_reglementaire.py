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
