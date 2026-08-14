# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §63 : LA MESURE DES CONTRATS DE RÉASSURANCE DÉTENUS
=============================================================================

§63, verbatim : « les hypothèses qu'elle utilise pour évaluer les estimations
de la valeur actualisée des flux de trésorerie futurs du groupe de contrats
de réassurance détenus doivent CONCORDER avec celles qu'elle utilise pour
évaluer les estimations […] du ou des groupes de contrats d'assurance
SOUS-JACENTS. De plus, les estimations […] doivent refléter l'effet du RISQUE
DE NON-EXÉCUTION de la part de l'émetteur du contrat de réassurance, Y
COMPRIS L'EFFET DES GARANTIES ET DES PERTES DÉCOULANT DE LITIGES. »

Deux exigences distinctes, et elles ne se traitent pas de la même façon :

  · la CONCORDANCE des hypothèses est une CONTRAINTE — elle se vérifie entre
    deux jeux d'hypothèses fournis, elle ne se calcule pas ;
  · le RISQUE DE NON-EXÉCUTION est un CALCUL — et il se vérifie.

⚠️ CE QUE LE §63 ÉNUMÈRE EN TROIS TERMES, ET CE QUE LES DONNÉES PORTENT.
« Y compris l'effet des GARANTIES et des PERTES DÉCOULANT DE LITIGES » :

  · le défaut de crédit  — PRÉSENT, par notation du réassureur ;
  · les GARANTIES        — PRÉSENTES : le collatéral réduit le taux, et la
    relation `taux = défaut × (1 − collatéral)` se vérifie exactement ;
  · les LITIGES          — ⚠️ ABSENTS. Aucune donnée livrée ne les porte,
    et le taux de non-exécution NE LES COUVRE PAS.

⚠️ ET J'AI D'ABORD ANNONCÉ LES GARANTIES ABSENTES, À TORT. La colonne
existait et servait. La mesure a corrigé l'affirmation — c'est pourquoi
l'absence des litiges, elle, est ÉTABLIE par la même mesure et non
supposée : rien dans les cinq fichiers de réassurance ne s'y rapporte.

⚠️ POURQUOI L'ABSENCE DES LITIGES COMPTE. Le §63 les nomme au même rang que
les garanties. Un taux qui n'en tient pas compte SOUS-ESTIME le risque de
non-exécution, donc SURESTIME les récupérations attendues, donc SURESTIME
l'actif de réassurance — un écart qui va dans le sens favorable à l'entité.
Le module le publie plutôt que de le laisser découvrir.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §63, §64 à §68.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_PARTS_NON_UNITAIRES = 'parts_du_panel_ne_somment_pas_a_un'
MOTIF_TAUX_INCOHERENT = 'taux_incoherent_avec_defaut_et_collateral'
MOTIF_BORNES = 'valeur_hors_bornes'
MOTIF_HYPOTHESES_DISCORDANTES = 'hypotheses_discordantes_avec_le_sous_jacent'

#: ⚠️ CE QUE LE TAUX NE COUVRE PAS, PUBLIÉ AVEC TOUT MONTANT QUI EN DESCEND.
MOTIF_LITIGES_ABSENTS = (
    "⚠️ LE RISQUE DE NON-EXÉCUTION NE COUVRE PAS LES LITIGES. §63 impose de "
    "refléter ce risque « Y COMPRIS l'effet des garanties ET DES PERTES "
    "DÉCOULANT DE LITIGES ». Le taux employé ici tient compte du défaut de "
    "crédit et du collatéral ; AUCUNE donnée livrée ne porte les litiges. "
    "L'omission va dans un sens : elle sous-estime le risque, donc surestime "
    "les récupérations et l'actif de réassurance — en faveur de l'entité.")


class Reassureur(NamedTuple):
    """Une ligne du panel, et ce qui la rend vérifiable."""
    nom:                str
    part:               float   # part du risque cédé, somme à 1
    defaut:             float   # probabilité de défaut, en fraction
    collateral:         float   # part du risque couverte par nantissement
    taux_non_execution: float   # déclaré, et VÉRIFIÉ contre les deux ci-dessus


class RisqueNonExecution(NamedTuple):
    """Le taux du §63, et ce qu'il ne couvre pas."""
    taux_pondere: float
    nb_reassureurs: int
    motif: str


def _borner(nom: str, v: float, haut: float = 1.0) -> None:
    if not 0.0 <= v <= haut:
        raise RefusMesure(
            MOTIF_BORNES,
            f"« {nom} » vaut {v} ; il est attendu dans [0, {haut}]. Une "
            f"probabilité ou une part hors de ces bornes signale une unité "
            f"divergente — des points de base lus comme une fraction, par "
            f"exemple")


def risque_non_execution(panel) -> RisqueNonExecution:
    """§63 — le taux pondéré du panel, et sa vérification.

    ⚠️ LE TAUX DÉCLARÉ EST VÉRIFIÉ, PAS REPRIS. La relation
    `taux = défaut × (1 − collatéral)` se contrôle ligne à ligne : c'est
    l'effet des GARANTIES que §63 exige de refléter, et le vérifier est le
    seul moyen de savoir qu'il l'a été.
    """
    lot = list(panel)
    if not lot:
        raise RefusMesure(
            'panel_vide',
            "aucun réassureur au panel. Un risque de non-exécution calculé "
            "sur un panel vide n'est pas nul — il n'existe pas, et rendre "
            "zéro serait la même faute qu'une gate rendant « Ran 0 tests » "
            "en sortant 0")

    for r in lot:
        _borner(f'part de {r.nom}', r.part)
        _borner(f'défaut de {r.nom}', r.defaut)
        _borner(f'collatéral de {r.nom}', r.collateral)
        _borner(f'taux de {r.nom}', r.taux_non_execution)
        attendu = r.defaut * (1.0 - r.collateral)
        if abs(r.taux_non_execution - attendu) > 1e-9:
            raise RefusMesure(
                MOTIF_TAUX_INCOHERENT,
                f"pour {r.nom}, le taux de non-exécution déclaré "
                f"({r.taux_non_execution}) ne vaut pas défaut × (1 − "
                f"collatéral) = {r.defaut} × {1.0 - r.collateral:.4f} = "
                f"{attendu}. §63 exige de refléter l'effet des GARANTIES : "
                f"un taux qui ne s'en déduit pas ne permet pas de savoir si "
                f"elles ont été prises en compte")

    somme = sum(r.part for r in lot)
    if abs(somme - 1.0) > 1e-9:
        raise RefusMesure(
            MOTIF_PARTS_NON_UNITAIRES,
            f"les parts du panel somment à {somme}, pas à 1. Une part "
            f"manquante laisserait du risque cédé à personne, et le taux "
            f"pondéré sous-estimerait le risque de non-exécution")

    return RisqueNonExecution(
        taux_pondere=sum(r.part * r.taux_non_execution for r in lot),
        nb_reassureurs=len(lot), motif=MOTIF_LITIGES_ABSENTS)


def recuperations_nettes(recuperations_brutes: float,
                         risque: RisqueNonExecution) -> float:
    """Les récupérations attendues, diminuées du risque de non-exécution.

    ⚠️ LE SENS DE L'AJUSTEMENT N'EST PAS NEUTRE : il DIMINUE l'actif de
    réassurance. Un ajustement qui l'augmenterait signalerait une convention
    retournée, et il serait favorable à l'entité — d'où le contrôle.
    """
    if recuperations_brutes < 0:
        raise RefusMesure(
            MOTIF_BORNES,
            f"les récupérations brutes valent {recuperations_brutes} ; ce "
            f"module les attend en valeur absolue")
    nettes = recuperations_brutes * (1.0 - risque.taux_pondere)
    if nettes > recuperations_brutes + 1e-9:
        raise RefusMesure(
            MOTIF_BORNES,
            f"les récupérations nettes ({nettes}) dépassent les brutes "
            f"({recuperations_brutes}). Le risque de non-exécution DIMINUE "
            f"l'actif de réassurance ; l'augmenter serait favorable à "
            f"l'entité et contraire au §63")
    return nettes


def verifier_concordance(*, hypotheses_cedees: dict,
                         hypotheses_sous_jacentes: dict) -> str:
    """§63 première phrase — la CONCORDANCE, qui se vérifie sans se calculer.

    ⚠️ C'EST UNE CONTRAINTE, PAS UN CALCUL. §63 exige que les hypothèses du
    groupe cédé CONCORDENT avec celles du sous-jacent. Deux jeux
    d'hypothèses évalués séparément peuvent chacun être défendable et se
    contredire entre eux — c'est exactement ce que cette vérification
    attrape, et rien d'autre ne l'attraperait.

    Rendre une chaîne vide vaut « ils concordent ». Toute divergence est
    NOMMÉE, hypothèse par hypothèse.
    """
    if not hypotheses_cedees or not hypotheses_sous_jacentes:
        raise RefusMesure(
            MOTIF_HYPOTHESES_DISCORDANTES,
            "l'un des deux jeux d'hypothèses est vide. La concordance du "
            "§63 ne se vérifie pas contre rien — et une absence n'est pas "
            "une concordance")

    communes = set(hypotheses_cedees) & set(hypotheses_sous_jacentes)
    if not communes:
        raise RefusMesure(
            MOTIF_HYPOTHESES_DISCORDANTES,
            f"les deux jeux n'ont AUCUNE hypothèse en commun "
            f"({sorted(hypotheses_cedees)} contre "
            f"{sorted(hypotheses_sous_jacentes)}). Une comparaison sur un "
            f"ensemble vide rendrait « concordant » sans rien avoir comparé")

    ecarts = [f"« {c} » : {hypotheses_cedees[c]!r} côté cédé contre "
              f"{hypotheses_sous_jacentes[c]!r} côté sous-jacent"
              for c in sorted(communes)
              if hypotheses_cedees[c] != hypotheses_sous_jacentes[c]]
    if not ecarts:
        return ''
    raise RefusMesure(
        MOTIF_HYPOTHESES_DISCORDANTES,
        f"{len(ecarts)} hypothèse(s) discordante(s) entre le groupe cédé et "
        f"son sous-jacent, sur {len(communes)} comparée(s) : "
        + " · ".join(ecarts)
        + ". §63 exige qu'elles CONCORDENT — deux jeux évalués séparément "
          "peuvent chacun être défendable et se contredire entre eux")
