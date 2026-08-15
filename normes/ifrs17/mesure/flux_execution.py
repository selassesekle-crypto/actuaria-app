# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §33-37 : LES FLUX DE TRÉSORERIE D'EXÉCUTION
=============================================================================

L'estimation des flux futurs (§33), leur actualisation (§36) et l'ajustement
au titre du risque non financier (§37) — assemblés sous les règles d'IFRS 17.

⚠️⚠️ CE MODULE N'EST ADOSSÉ À AUCUNE SOURCE EXTERNE, ET C'EST ÉCRIT ICI POUR
QU'ON NE LISE JAMAIS UN FICHIER VERT COMME UNE VALIDATION IFRS 17. Ses
garanties sont INTERNES : des invariants arithmétiques et des refus. Aucun
exemple publié disponible ne chiffre une valeur actualisée de flux
d'exécution avec ses hypothèses complètes. Le classeur de la section 7 de la
note ICA, s'il arrive un jour, servira d'oracle à l'ÉLÉMENT DE PERTE (§57-58),
pas à ce module-ci.

⚠️ CE MODULE NE DEVINE RIEN, ET CE N'EST PAS UNE PRUDENCE EXCESSIVE : LA
NORME ELLE-MÊME CONFIE CES DÉCISIONS À L'ENTITÉ.
  · §36 b) veut des taux qui « CONCORDENT avec les prix de marché courants
    observables » — concorder est une appréciation, pas une formule ;
  · §37 veut « l'indemnité QU'ELLE EXIGE pour la prise en charge de
    l'incertitude » — la norme n'impose AUCUNE méthode.
C'est la cinquième fois dans ce chantier qu'un paragraphe remet la décision à
l'entité, après §54, §59 a), B66 d) et le déclenchement du §57. Le module
reçoit, il publie, il refuse.

⚠️ ET IL N'IMPORTE RIEN HORS DU CHANTIER, POUR DEUX RAISONS. La première est
de principe : un actuaire qui signe un ajustement pour risque ne signe pas
« ce que tel agent avait sous la main ». La seconde est mesurée : `core/` est
le seul nœud bidirectionnel du graphe d'imports du dépôt (il importe la
direction non-vie). En dépendre condamnerait TOUT lot futur du chantier
IFRS 17 à la gate non-vie de vingt-quatre minutes, au lieu de vingt secondes.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §33 à §37, et §59 b) pour la dispense d'actualisation.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import (
    COMPARAISON_EGAL,
    est_renseigne,
    exiger_arrete_dans_le_contexte,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_SANS_SIGNATURE = 'declaration_sans_signataire'
MOTIF_SANS_SOURCE = 'declaration_sans_source'
MOTIF_PROBABILITES = 'probabilites_ne_somment_pas_a_un'
MOTIF_AUCUN_SCENARIO = 'aucun_scenario_fourni'
MOTIF_AUCUN_FLUX = 'aucun_flux_fourni'
MOTIF_AJUSTEMENT_NEGATIF = 'ajustement_risque_negatif'
MOTIF_SANS_NIVEAU_CONFIANCE = 'ajustement_sans_niveau_de_confiance'
MOTIF_ANNEE_HORS_COURBE = 'annee_absente_de_la_courbe'
MOTIF_ANNEE_INVALIDE = 'annee_de_flux_invalide'

#: Les deux façons dont un flux de période peut exister. ⚠️ ELLES NE VALENT
#: PAS LA MÊME CHOSE, et tout ce module tient à cette distinction.
ESPERANCE_CALCULEE = 'ESPERANCE_CALCULEE'
MONTANT_DECLARE = 'MONTANT_DECLARE'

#: ⚠️ CE QUE §33 a) EXIGE ET QU'UN MONTANT UNIQUE NE PROUVE PAS. Le texte
#: demande « la valeur attendue (c'est-à-dire l'ESPÉRANCE MATHÉMATIQUE) de
#: l'éventail complet des résultats possibles ». Un nombre remis sans ses
#: scénarios PEUT être une espérance — mais rien ne permet de l'établir, et
#: le présenter comme telle serait affirmer plus que la donnée ne porte.
MOTIF_ESPERANCE_NON_ETABLIE = (
    "au moins un flux est un MONTANT DÉCLARÉ, pas une espérance calculée. "
    "§33 a) exige « la valeur attendue (c'est-à-dire l'espérance "
    "mathématique) de l'éventail complet des résultats possibles » : sans "
    "les scénarios et leurs probabilités, le caractère probabilisé N'EST "
    "PAS ÉTABLI. Le montant est repris tel qu'il a été remis, et cette "
    "réserve doit accompagner tout chiffre qui en descend.")


class Scenario(NamedTuple):
    """Un résultat possible et sa probabilité (§33 a)."""
    montant:     float
    probabilite: float


class FluxPeriode(NamedTuple):
    """Un flux attendu sur une année, et COMMENT il a été obtenu."""
    annee:   int      # 1 = première année suivant l'arrêté
    montant: float
    base:    str      # ESPERANCE_CALCULEE ou MONTANT_DECLARE


class CourbeDeclaree(NamedTuple):
    """La courbe du §36, avec ce qui la rend opposable.

    ⚠️ `taux` EST INDEXÉ PAR ANNÉE, pas plat. §36 a) parle des
    « caractéristiques de liquidité » : un taux unique serait une hypothèse
    supplémentaire, et elle se déclarerait comme telle.
    """
    taux:          tuple   # ((annee, taux), ...)
    source:        str
    arrete:        str
    actuaire_resp: str


class AjustementRisque(NamedTuple):
    """Le §37, et le niveau de confiance que §119 impose de publier."""
    montant:          float
    niveau_confiance: str    # p. ex. « quantile 75 % »
    methode:          str    # p. ex. « coût du capital 6 % »
    arrete:           str
    actuaire_resp:    str


class FluxExecution(NamedTuple):
    """Le résultat assemblé. ⚠️ `motif_esperance` VIDE = §33 a) établi."""
    valeur_brute:            float   # somme non actualisée
    valeur_actualisee:       float   # §36 appliqué
    ajustement_risque:       float   # §37
    total:                   float   # actualisée + ajustement
    nb_periodes:             int
    actualisation_appliquee: bool
    motif_esperance:         str
    motif_actualisation:     str


# =============================================================================
#  §33 — L'ESTIMATION, ET SES DEUX FORMES
# =============================================================================


def esperance(annee: int, scenarios) -> FluxPeriode:
    """§33 a) — l'espérance mathématique sur un éventail déclaré.

    ⚠️ LES PROBABILITÉS DOIVENT SOMMER À 1. Un éventail incomplet donnerait
    une espérance systématiquement basse, et rien ne le signalerait : c'est
    l'erreur silencieuse type de ce calcul.
    """
    lot = list(scenarios)
    if not lot:
        raise RefusMesure(
            MOTIF_AUCUN_SCENARIO,
            "aucun scénario fourni. Une espérance sur un éventail vide n'est "
            "pas nulle — elle n'existe pas")
    if any(s.probabilite < 0 for s in lot):
        raise RefusMesure(
            MOTIF_PROBABILITES, "une probabilité négative a été fournie")
    somme = sum(s.probabilite for s in lot)
    if abs(somme - 1.0) > 1e-9:
        raise RefusMesure(
            MOTIF_PROBABILITES,
            f"les probabilités somment à {somme}, pas à 1. §33 a) parle de "
            f"l'éventail COMPLET des résultats possibles ; un éventail "
            f"tronqué rendrait une espérance basse sans que rien ne le dise")
    _controler_annee(annee)
    return FluxPeriode(annee=annee,
                       montant=sum(s.montant * s.probabilite for s in lot),
                       base=ESPERANCE_CALCULEE)


def montant_declare(annee: int, montant: float) -> FluxPeriode:
    """Un flux remis sans ses scénarios — repris tel quel, et MARQUÉ.

    ⚠️ CE N'EST PAS UN RACCOURCI, C'EST UN AVEU. Le montant est utilisable,
    mais tout résultat qui en descend portera `motif_esperance`.
    """
    _controler_annee(annee)
    return FluxPeriode(annee=annee, montant=montant, base=MONTANT_DECLARE)


def _controler_annee(annee: int) -> None:
    if not isinstance(annee, int) or annee < 1:
        raise RefusMesure(
            MOTIF_ANNEE_INVALIDE,
            f"l'année vaut {annee!r} ; les années se comptent en entiers à "
            f"partir de 1, la première suivant la date d'arrêté")


# =============================================================================
#  §36 ET §37 — LES DEUX DÉCLARATIONS SIGNÉES
# =============================================================================


def declarer_courbe(taux: dict, source: str, arrete: str,
                    actuaire_resp: str) -> CourbeDeclaree:
    """La courbe du §36, ou un REFUS disant ce qui manque."""
    if not est_renseigne(actuaire_resp):
        raise RefusMesure(
            MOTIF_SANS_SIGNATURE,
            "aucun actuaire ne se porte garant de cette courbe. §36 b) "
            "exige qu'elle CONCORDE avec des prix de marché observables — "
            "une appréciation, donc quelqu'un qui l'assume")
    if not est_renseigne(source):
        raise RefusMesure(
            MOTIF_SANS_SOURCE,
            "la courbe est fournie sans sa source. « D'où vient cette "
            "courbe » est la première question d'un commissaire aux comptes")
    if not est_renseigne(arrete):
        raise RefusMesure(
            MOTIF_SANS_SIGNATURE,
            "la courbe est fournie sans son arrêté ; une courbe vaut pour "
            "une date, pas pour toutes")
    if not taux:
        raise RefusMesure(
            MOTIF_SANS_SOURCE,
            "la courbe ne porte aucun taux. Une courbe vide n'est pas une "
            "courbe plate à zéro : c'est une absence")
    return CourbeDeclaree(taux=tuple(sorted(taux.items())),
                          source=source.strip(), arrete=arrete.strip(),
                          actuaire_resp=actuaire_resp.strip())


def declarer_ajustement(montant: float, niveau_confiance: str, methode: str,
                        arrete: str, actuaire_resp: str) -> AjustementRisque:
    """Le §37, ou un REFUS.

    ⚠️ LE MONTANT NE PEUT PAS ÊTRE NÉGATIF. §37 parle de « l'indemnité
    qu'elle EXIGE pour la prise en charge de l'incertitude » : c'est une
    majoration du passif, jamais une remise. Un négatif ici traduirait une
    convention de signe inverse, et il faut le dire plutôt que l'absorber.
    """
    if not est_renseigne(actuaire_resp):
        raise RefusMesure(
            MOTIF_SANS_SIGNATURE,
            "aucun actuaire ne se porte garant de cet ajustement. §37 ne "
            "prescrit AUCUNE méthode : c'est l'indemnité que l'entité exige, "
            "donc une décision qui engage quelqu'un nommément")
    if not est_renseigne(niveau_confiance):
        raise RefusMesure(
            MOTIF_SANS_NIVEAU_CONFIANCE,
            "l'ajustement est fourni sans son niveau de confiance. §119 "
            "impose de le PUBLIER : un ajustement dont on ne peut pas dire "
            "à quel quantile il correspond n'est pas présentable en annexe")
    if not est_renseigne(methode) or not est_renseigne(arrete):
        raise RefusMesure(
            MOTIF_SANS_SIGNATURE,
            "l'ajustement est fourni sans sa méthode ou sans son arrêté. "
            "§37 n'en imposant aucune, celle qui a été retenue doit être "
            "nommée pour être vérifiable")
    if montant < 0:
        raise RefusMesure(
            MOTIF_AJUSTEMENT_NEGATIF,
            f"l'ajustement vaut {montant}. §37 décrit une INDEMNITÉ EXIGÉE "
            f"pour la prise en charge de l'incertitude : elle majore le "
            f"passif, elle ne le réduit jamais")
    return AjustementRisque(montant=montant,
                            niveau_confiance=niveau_confiance.strip(),
                            methode=methode.strip(), arrete=arrete.strip(),
                            actuaire_resp=actuaire_resp.strip())


# =============================================================================
#  L'ASSEMBLAGE
# =============================================================================

#: ⚠️ §59 b) DISPENSE, IL N'EXCLUT PAS. « L'entité n'est pas tenue d'ajuster
#: les flux de trésorerie futurs pour refléter la valeur temps de l'argent
#: […] si le versement ou l'encaissement de ces flux est attendu dans un
#: délai n'excédant pas un an à compter de la date du sinistre. » C'est une
#: FACULTÉ : elle s'exerce sur déclaration, jamais par défaut.
MOTIF_DISPENSE_59B = (
    "actualisation NON appliquée sur déclaration de la dispense du §59 b) — "
    "règlement attendu dans l'année suivant le sinistre. ⚠️ C'est une "
    "FACULTÉ exercée, pas une exclusion subie : elle engage celui qui l'a "
    "déclarée, et elle se mentionne à côté de tout montant qui en descend.")


def assembler(flux, courbe: CourbeDeclaree | None,
              ajustement: AjustementRisque, contexte,
              dispense_59b: bool = False) -> FluxExecution:
    """§33 + §36 + §37 — les flux d'exécution d'un groupe.

    ⚠️ `courbe` PEUT ÊTRE `None` UNIQUEMENT SOUS LA DISPENSE DU §59 b), et
    le résultat porte alors le motif qui le dit. Autrement, l'absence de
    courbe est un refus : rendre une valeur non actualisée sans le signaler
    serait rendre un chiffre faux en silence.

    ⚠️⚠️ `contexte` EST OBLIGATOIRE, ET C'EST ICI QUE LA PÉREMPTION SE JUGE.
    Elle ne se juge PAS à la constitution : au moment où `declarer_courbe`
    fabrique une courbe, son arrêté est nécessairement celui du jour — c'est
    à la CONSOMMATION qu'une courbe de l'exercice précédent devient fausse.
    Un contrôle placé au mauvais moment donne du réconfort, ce qui est pire
    qu'aucun contrôle : on cesse de chercher.

    ⚠️ ET IL N'A PAS DE DÉFAUT À `None`. Un défaut recréerait exactement le
    contrôle qui ne tire pas — celui qu'on vient de fermer.
    """
    exiger_arrete_dans_le_contexte(
        arrete=ajustement.arrete, comparaison=COMPARAISON_EGAL,
        contexte=contexte, erreur=RefusMesure,
        objet="l'ajustement pour risque du §37")
    if courbe is not None:
        exiger_arrete_dans_le_contexte(
            arrete=courbe.arrete, comparaison=COMPARAISON_EGAL,
            contexte=contexte, erreur=RefusMesure,
            objet="la courbe du §36")
    lot = list(flux)
    if not lot:
        raise RefusMesure(
            MOTIF_AUCUN_FLUX,
            "aucun flux fourni. Des flux d'exécution vides ne valent pas "
            "zéro — ils ne valent rien, et rendre 0 ici serait la même faute "
            "qu'une gate rendant « Ran 0 tests » en sortant 0")

    brute = sum(f.montant for f in lot)

    if dispense_59b:
        actualisee, applique = brute, False
        motif_act = MOTIF_DISPENSE_59B
    else:
        if courbe is None:
            raise RefusMesure(
                MOTIF_SANS_SOURCE,
                "aucune courbe d'actualisation, et la dispense du §59 b) "
                "n'est pas déclarée. §36 impose d'ajuster de la valeur temps "
                "de l'argent ; rendre une valeur brute sans le dire serait "
                "rendre un chiffre faux en silence")
        connus = dict(courbe.taux)
        manquantes = sorted({f.annee for f in lot} - set(connus))
        if manquantes:
            raise RefusMesure(
                MOTIF_ANNEE_HORS_COURBE,
                f"la courbe ne porte aucun taux pour l'année ou les années "
                f"{manquantes}. Extrapoler serait inventer une hypothèse "
                f"que personne n'a signée ; ignorer ces flux les ferait "
                f"disparaître de l'actualisation")
        actualisee = sum(f.montant / (1.0 + connus[f.annee]) ** f.annee
                         for f in lot)
        applique, motif_act = True, ''

    declares = [f for f in lot if f.base == MONTANT_DECLARE]
    return FluxExecution(
        valeur_brute=brute,
        valeur_actualisee=actualisee,
        ajustement_risque=ajustement.montant,
        total=actualisee + ajustement.montant,
        nb_periodes=len(lot),
        actualisation_appliquee=applique,
        motif_esperance=MOTIF_ESPERANCE_NON_ETABLIE if declares else '',
        motif_actualisation=motif_act)
