# =============================================================================
#  ActuarIA — A7 · COURBE DES TAUX SANS RISQUE  (adaptateur)
#  rfr_eiopa.py
#
#  ⚠️ CE MODULE NE PORTE PLUS DE COURBE. Il ADAPTE le référentiel commun
#     `core/courbe_rfr.py` à la forme de dictionnaire qu'A7 consomme déjà.
#
#  POURQUOI IL A CESSÉ D'EN PORTER UNE. Le relevé exhaustif du chantier RFR a
#  trouvé HUIT sources de taux dans le dépôt, SIX en non-vie, divergeant de
#  45 bps sur le 10 ans — et pas dans le même sens : A7 était 41 bps SOUS la
#  courbe en vigueur, tout le bloc réglementaire 4 bps AU-DESSUS. Un décalage
#  commun s'annulerait dans un rapport consolidé ; celui-là non. Il se voit
#  dès qu'on recoupe la Risk Margin d'A7 avec le Best Estimate actualisé
#  d'A10.
#
#  CE QUI A DISPARU D'ICI, ET NE DOIT PAS Y REVENIR :
#    · les 30 taux de la courbe embarquée — ils vivent dans le référentiel,
#      aux 150 maturités publiées ;
#    · le garde-fou d'unité (seuil, consigne, diagnostic) — il y vit aussi,
#      et il y sert les trois portes d'entrée au lieu de deux ;
#    · `DEVISE`, `AVEC_VA`, `AVEC_CRA`, `get_courbe_rfr`,
#      `get_facteur_actualisation` — CINQ noms publics que le relevé a
#      trouvés à ZÉRO consommateur dans tout le dépôt. Les métadonnées sont
#      désormais portées par la courbe elle-même (`CourbeRFR`).
#
#  CE QUE LA BASCULE APPORTE, ET QUI N'EXISTAIT PAS :
#    · le classeur EIOPA OFFICIEL est lu tel qu'il est publié — plus besoin
#      de fabriquer un extrait à deux colonnes à la main ;
#    · une courbe importée porte SA date d'arrêté, donc sa péremption devient
#      TESTABLE là où elle était « NON TESTABLE » ;
#    · une courbe SANS date d'arrêté est ROUGE, donc plafonnante. Elle
#      traversait jusqu'ici les deux circuits de gouvernance en silence.
#
#  Réf. : Art. 77 du règlement délégué (UE) 2015/35.
#
#  Utilisation, inchangée pour les appelants :
#      from config.rfr_eiopa import get_taux_rfr, DATE_COURBE
#      taux_t = get_taux_rfr(t)     # taux spot à la maturité t (années)
# =============================================================================

from __future__ import annotations

from typing import Optional, Union

from core.courbe_rfr import (
    MOIS_ALERTE_PEREMPTION,
    MOIS_ROUGE_PEREMPTION,
    TAUX_MIN_PLAUSIBLE_PCT,
    CourbeIllisible,
    actualiser,
    age_courbe_mois as _age_courbe_mois,
    courbe_embarquee as _courbe_embarquee,
    diagnostic_peremption as _diagnostic_peremption,
    lire_classeur_eiopa,
    lire_deux_colonnes,
    taux_plat,
)

__all__ = [
    'DATE_COURBE', 'SOURCE', 'TAUX_MIN_PLAUSIBLE_PCT',
    'MOIS_ALERTE_PEREMPTION', 'MOIS_ROUGE_PEREMPTION',
    'get_taux_rfr', 'age_courbe_mois', 'diagnostic_peremption',
    'get_courbe_embarquee', 'get_courbe_taux_plat', 'get_courbe_depuis_excel',
]

_EMBARQUEE = _courbe_embarquee()

# ── Métadonnées, reprises de la courbe et non recopiées ──────────────────────
DATE_COURBE = _EMBARQUEE.date_arrete
SOURCE = f"EIOPA RFR Term Structures — arrêté du {DATE_COURBE}"


def get_taux_rfr(maturite: Union[int, float]) -> float:
    """Taux sans risque EIOPA EUR à la maturité donnée, en DÉCIMAL.

    Rend le taux de la courbe EMBARQUÉE. Une courbe fournie par l'actuaire
    ne passe pas par ici : elle circule par `courbe_rfr['taux_fn']`.
    """
    return actualiser(_EMBARQUEE, maturite)


def age_courbe_mois(date_valorisation=None) -> float:
    """Âge de la courbe embarquée en mois, à la date de valorisation."""
    return _age_courbe_mois(_EMBARQUEE, date_valorisation)


def diagnostic_peremption(date_valorisation=None) -> dict:
    """Péremption de la courbe EMBARQUÉE — VERT / AMBRE / ROUGE."""
    return _diagnostic_peremption(_EMBARQUEE, date_valorisation)


# =============================================================================
#  L'ADAPTATION — d'une `CourbeRFR` vers le dictionnaire qu'A7 consomme
# =============================================================================

def _en_dict(courbe, type_: str, label: str, source: Optional[str] = None,
             erreur: Optional[str] = None, date_valorisation=None) -> dict:
    """La forme attendue par `n4_best_estimate` et par l'application.

    ⚠️ LA CLÉ `'courbe'` EST CE QUI BRANCHE LA GOUVERNANCE. Elle transporte la
    `CourbeRFR` elle-même — donc sa date d'arrêté, ou son absence. Sans elle,
    `_meta_courbe` ne pouvait juger que la courbe embarquée et rendait
    « NON TESTABLE » pour tout le reste : un taux plat produisait un VERT
    sans que rien ne signale que l'actualisation reposait sur un taux supposé.
    """
    diag = _diagnostic_peremption(courbe, date_valorisation)
    return {
        'type':       type_,
        'courbe':     courbe,
        'taux_fn':    lambda t: actualiser(courbe, t),
        'source':     source or courbe.provenance,
        'date':       courbe.date_arrete or '—',
        'label':      label,
        'peremption': diag,
        'erreur':     erreur if erreur is not None else (
            diag['message'] if diag['statut'] != 'VERT' else None),
    }


def get_courbe_embarquee(date_valorisation=None) -> dict:
    """La courbe de repli, avec son diagnostic de péremption."""
    return _en_dict(_EMBARQUEE, 'embarquee',
                    f'Courbe EIOPA embarquée ({DATE_COURBE})',
                    source=SOURCE, date_valorisation=date_valorisation)


def get_courbe_taux_plat(taux_pct: float) -> dict:
    """Un taux unique, toutes maturités — UN OUTIL DE SENSIBILITÉ.

    ⚠️ CE N'EST PAS UN IMPORT DE COURBE. « Que devient ma marge de risque à
    2 % ? » est une question légitime avant de signer ; le résultat n'est pas
    pour autant un chiffre d'arrêté. Sans date, la courbe est ROUGE et
    plafonne — c'est la règle que le référentiel pose.
    """
    try:
        courbe = taux_plat(taux_pct)
    except CourbeIllisible as e:
        return _repli(str(e), 'Courbe embarquée (taux manuel refusé)')
    return _en_dict(courbe, 'taux_plat',
                    f'Taux manuel {float(taux_pct):.3f}%')


def get_courbe_depuis_excel(fichier_bytes: bytes) -> dict:
    """Une courbe importée — LE CLASSEUR EIOPA OFFICIEL D'ABORD.

    ⚠️ L'ORDRE DES DEUX LECTEURS EST LE SUJET. Le classeur officiel est
    essayé EN PREMIER parce que lui seul apporte la date d'arrêté, et donc
    seul il produit une courbe capable de porter un chiffre définitif.
    L'extrait à deux colonnes reste accepté — pour une courbe qui n'est pas
    EIOPA — mais il ne porte pas de date, donc il plafonne.

    ⚠️ ET LE REPLI VIT ICI, PAS DANS LE RÉFÉRENTIEL. Une bibliothèque qui
    substitue une autre donnée en silence est pire qu'une qui refuse ; c'est
    à l'agent, qui sait ce qu'il publie, de décider de se rabattre sur
    l'embarquée. Le calcul de la marge de risque ne peut pas s'arrêter là.
    """
    try:
        courbe = lire_classeur_eiopa(fichier_bytes)
    except CourbeIllisible as officiel:
        try:
            courbe = lire_deux_colonnes(fichier_bytes)
        except CourbeIllisible as extrait:
            return _repli(f"{extrait} (lu aussi comme classeur EIOPA "
                          f"officiel : {officiel})",
                          'Courbe embarquée (erreur fichier)')
        return _en_dict(courbe, 'fichier_excel',
                        f'Extrait deux colonnes ({len(courbe.maturites)} '
                        f'maturités)')
    return _en_dict(courbe, 'fichier_excel',
                    f'Classeur EIOPA officiel ({courbe.date_arrete}, '
                    f'{len(courbe.maturites)} maturités)')


def _repli(motif: str, label: str) -> dict:
    """Un refus rend toujours une courbe utilisable — l'embarquée, jamais
    `None` — et le motif du refus est publié plutôt que journalisé."""
    sortie = _en_dict(_EMBARQUEE, 'erreur', label,
                      source=f'{motif} — courbe embarquée utilisée')
    sortie['erreur'] = motif
    return sortie
