"""
core/qualite_donnees.py — Couche de qualité de données GÉNÉRIQUE, pilotée par le
PLAN, pour le chemin déclaratif (Phase 0 du roadmap qualité).

PRINCIPE DIRECTEUR : jamais de correction ou d'exclusion SILENCIEUSE.

QUATRE RÈGLES (toutes pilotées par les RÔLES du plan — exposition,
cible_frequence, cible_cout, identifiant_contrat — jamais par un nom de colonne
codé en dur ; un plan futur jamais vu en bénéficie automatiquement) :

  1. IMPOSSIBLE MATHÉMATIQUEMENT (fréquence < 0, exposition ≤ 0, doublon sur
     l'identifiant de contrat déclaré) → exclut la LIGNE. Comptée et listée
     dans le rapport.
     ⚠️⚠️ LE COÛT A QUITTÉ CETTE RÈGLE LE 31/08/2026 (`qualite/C8`, rang 1).
     Un COÛT est ≥ 0 ; une CHARGE NETTE — paiements moins recours — ne l'est
     pas. Mesuré sur donnée réelle : 8,82 % des contrats, et les exclure
     sur-tarifait de 14,9 %. Il est désormais règle 3.
  2. IMPLAUSIBLE MAIS PAS IMPOSSIBLE, règle établie (exposition > la borne) →
     corrige automatiquement (plafond à la borne) et signale la correction.
     ⚠️⚠️ LA BORNE DÉRIVE DE `plan.unite_exposition` DEPUIS LE 31/08/2026
     (`qualite/C3`, étape 2) : `annee` → 1 · `mois` → 12 · `jour` → 366.
     Unité NON déclarée : hypothèse annuelle, comportement inchangé — mais
     l'hypothèse est PUBLIÉE dans le message au lieu d'être supposée en
     silence. Et une donnée qui CONTREDIT l'unité déclarée est signalée
     (règle 3), jamais corrigée : sans cela, déclarer `mois` élargirait la
     borne et le mécanisme ne pourrait plus rien attraper.
  3. AMBIGU (coût > 0 sans sinistre, ou l'inverse ; fréquence non entière ;
     doublon de ligne entière SANS identifiant pour trancher) → NE DÉCIDE RIEN :
     compte, affiche, laisse tel quel.
  4. ESCALADE PAR PROPORTION : si UN type d'anomalie (règles 1-3) touche ≥ 5 %
     des lignes ET qu'aucune confirmation actuarielle nominative n'est fournie
     (qualite_validee_par), le traitement est BLOQUÉ (QualiteBloquante). Le champ
     nominatif absent par défaut est l'unique échappatoire, et il est TRACÉ (qui,
     quand). MÊME PATTERN que valide_par_actuaire_dl (garde-fou DL).

⚠️ CONSTAT `qualite/C5` — CETTE PHRASE CITAIT `A1._evaluer_qualite`, QUI
N'EXISTE NULLE PART. Mesuré sur tout le dépôt le 01/09/2026 : une seule
occurrence du nom, cette phrase elle-même. *Un renvoi à une fonction qui
n'existe pas envoie le lecteur chercher une source d'autorité qu'il ne
trouvera jamais.* Ce module ne réutilise donc RIEN d'A1 : il porte sa
propre détection, pilotée par les RÔLES du plan, mais
SANS son défaut : ici la détection DÉCLENCHE une action (exclure / corriger /
bloquer), là où A1 se contentait de scorer (flag-only). Les détecteurs sont purs
et paramétrés par colonne — A1 pourra les réutiliser (convergence future).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, List, Tuple, TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:                       # évite un import cyclique à l'exécution
    from core.plan_tarifaire import PlanTarifaire

# Seuil d'escalade : au-delà, une confirmation actuarielle nominative est requise.
SEUIL_ESCALADE = 0.05


#: Les trois grandeurs que ce lot couvre. ⚠️ Les FACTEURS tarifaires restent
#: imputés comme avant : Selasse les a explicitement laissés hors de ce lot.
ROLES_GRANDEURS = ('exposition', 'cible_frequence', 'cible_cout')

#: ⚠️ Libellés lisibles — le message parle à l'actuaire, pas au code.
_LIBELLE_GRANDEUR = {
    'exposition': 'durée de couverture',
    'cible_frequence': 'nombre de sinistres',
    'cible_cout': 'charge de sinistres',
}


class ValeurAbsenteNonDeclaree(RuntimeError):
    """⚠️⚠️ LE SYSTÈME N'INVENTE JAMAIS UNE VALEUR À LA PLACE DE L'ACTUAIRE.

    Arbitré par Selasse le 02/09/2026. Mesuré avant l'arbitrage, sur 30
    expositions absentes parmi 1 000 :

        exposition totale AVANT : 970,0
        exposition totale APRES : 1 000,0    <- 30 ANNEES inventees
        ce que le rapport signe en disait : RIEN

    Les valeurs absentes étaient remplacées par la moyenne, en silence, et
    entraient au dénominateur du tarif. *Une valeur absente est AMBIGUË : ni le
    code ni la donnée ne savent si c'est un vrai zéro, une erreur de saisie ou
    une grandeur inconnue. Choisir à la place de l'actuaire, c'est trancher une
    question actuarielle par défaut.*

    Le plan déclare désormais `valeurs_absentes` — `exclure`,
    `imputer_mediane`, `imputer_moyenne`. **Non déclaré, on s'arrête ici**, en
    nommant les grandeurs, les comptes, et l'empreinte des positions.

    ⚠️ RGPD : le message porte des COMPTES et une EMPREINTE, jamais une
    position ni une valeur. L'annexe, elle, porte les positions — et elle ne
    quitte pas le poste de l'actuaire.
    """

    def __init__(self, manquants: dict, total: int, empreinte: str):
        self.manquants = dict(manquants)
        self.total = int(total)
        self.empreinte = empreinte
        detail = " ; ".join(
            f"{_LIBELLE_GRANDEUR.get(r, r)} : {n} ligne(s)"
            for r, n in sorted(manquants.items()))
        super().__init__(
            f"Valeurs absentes sur des grandeurs qui decident du tarif, et le "
            f"plan ne dit pas quoi en faire. {detail} — sur {total} ligne(s). "
            f"AUCUNE VALEUR N'A ETE INVENTEE. Declarez `valeurs_absentes` au "
            f"plan : 'exclure' (ces lignes sortent du calcul), "
            f"'imputer_mediane' ou 'imputer_moyenne' (elles recoivent une "
            f"valeur, et le rapport signe le dira). L'annexe de revue jointe a "
            f"ce run liste les lignes concernees, position par position, pour "
            f"que vous les repreniez vous-meme. Empreinte des cas : "
            f"{empreinte}.")


def annexe_revue_valeurs_absentes(df, plan) -> list[dict]:
    """Un cas par ligne absente — pour que l'actuaire REPRENNE les siennes.

    ⚠️⚠️ MÊME DOCTRINE QUE `annexe_revue_charges_negatives`, GÉNÉRALISÉE AUX
    TROIS GRANDEURS. Deux surfaces, deux audiences : la SYNTHÈSE (rapport
    signé, circulé) ne cite ni valeur ni position ; cette ANNEXE ne quitte pas
    le poste de l'actuaire et porte **la position de la ligne dans SON
    fichier** — une coordonnée que lui seul peut résoudre.

    ⚠️ LA POSITION EST POSITIONNELLE, jamais l'étiquette du dataframe. Mesuré :
    même sur un dataframe indexé par des numéros de police, elle reste un rang.
    *Aucun identifiant client ne peut fuir par ce canal.*

    ⚠️ ET ELLE NE PROMET QUE CE QU'ELLE PEUT PRODUIRE. Pas de « valeur
    trouvée » : il n'y en a pas — c'est tout l'objet. Elle donne la position et
    la grandeur, et rien d'autre.
    """
    if df is None:
        return []
    lignes = []
    for role in ROLES_GRANDEURS:
        col = getattr(plan, role, None)
        if not col or col not in df.columns:
            continue
        for pos in np.flatnonzero(detecter_illisible(df, col)):
            lignes.append({'position': int(pos), 'grandeur': role,
                           'colonne': col})
    return sorted(lignes, key=lambda x: (x['position'], x['grandeur']))


def facteurs_valeurs_absentes(df, plan) -> dict:
    """Les FACTEURS déclarés au plan qui portent une valeur absente.

    ⚠️⚠️ DEUXIÈME MOITIÉ DE L'ARBITRAGE DU 02/09/2026, ET ELLE NE SE CONFOND
    PAS AVEC LA PREMIÈRE. Sur les trois GRANDEURS, un trou non déclaré
    **arrête le run** : la durée, la fréquence et le coût sont le tarif
    lui-même. Sur un FACTEUR, l'arrêt serait disproportionné — *une vingtaine
    de facteurs par plan, environ cent soixante au total : arrêter sur chacun
    rendrait tout fichier client imparfait intarifable.*

    Décision de Selasse : **la ligne est EXCLUE et le système le DIT.** Il
    n'invente toujours rien ; il refuse simplement de tarifer une ligne dont
    un facteur manque, plutôt que de deviner ce facteur.

    ⚠️ ASSIETTE : les facteurs DÉCLARÉS, jamais les trois grandeurs — celles-ci
    ont leur propre porte (`exiger_valeurs_absentes_declarees`), et les
    compter deux fois publierait deux gestes pour un seul trou.

    ⚠️⚠️ ET « ABSENT » NE VEUT PAS DIRE LA MÊME CHOSE SELON LE TYPE DÉCLARÉ.
    `detecter_illisible` signifie *non convertible en nombre* — juste pour les
    trois grandeurs, qui sont numériques par construction. Appliqué à un
    facteur CATÉGORIEL, il marque **100 % de la colonne** : mesuré le
    02/09/2026 sur un témoin dont une seule colonne était trouée, il nommait
    **six facteurs au lieu d'un**, dont cinq intacts.

    > *Le rapport signé aurait dit « valeur absente sur `carburant`, 1 000
    > lignes » d'une colonne pleine de « Essence » et « Diesel ».*

    Le TYPE vient donc du PLAN — jamais du dtype, qui dépend du fichier reçu.
    C'est déjà la doctrine de `_categorie_imputation` pour les binaires.
    """
    if df is None or plan is None:
        return {}
    grandeurs = {getattr(plan, r, None) for r in ROLES_GRANDEURS}
    manquants = {}
    for f in getattr(plan, 'facteurs', ()) or ():
        col = f.nom
        if col in grandeurs or col not in getattr(df, 'columns', ()):
            continue
        masque = _masque_absence_facteur(df, f)
        n = int(np.asarray(masque, dtype=bool).sum())
        if n:
            manquants[col] = n
    return dict(sorted(manquants.items()))


def _masque_absence_facteur(df, facteur):
    """Le masque d'absence d'UN facteur, selon le TYPE que le plan déclare.

    ⚠️⚠️ Un facteur `continu` vaut par son nombre : une chaîne inconvertible y
    est aussi inutilisable qu'un vide, et `detecter_illisible` les voit tous
    les deux. Un facteur `categoriel` ou `binaire` vaut par sa MODALITÉ :
    « Essence » n'est pas une absence. *Confondre les deux fait dire à un
    rapport signé qu'une colonne pleine est vide.*
    """
    if getattr(facteur, 'type', None) == 'continu':
        return np.asarray(detecter_illisible(df, facteur.nom), dtype=bool)
    return np.asarray(df[facteur.nom].isna(), dtype=bool)


def masque_lignes_facteurs_absents(df, plan):
    """Les lignes à retirer — DÉRIVÉES DU MASQUE QUI A SERVI À COMPTER.

    ⚠️⚠️ SANS ELLE, LE COMPTE ET LE GESTE VENAIENT DE DEUX SOURCES. A2
    excluait par `dropna`, qui ne voit que les vrais `NaN` ; le compte publié
    et l'annexe venaient de `_masque_absence_facteur`, qui voit **aussi** une
    chaîne inconvertible sur un facteur `continu`. Mesuré le 02/09/2026 sur un
    facteur portant 5 vrais vides et 4 chaînes :

        compte publie  : 9 lignes absentes
        annexe publiee : 9 positions
        action reelle  : 5 lignes retirees

    *Le rapport signé aurait dit « 9 ligne(s) EXCLUE(S) » pendant que quatre
    d'entre elles restaient dans le tarif, avec un texte dans une colonne
    numérique.*

    ⚠️ SUR LE CHEMIN COMPLET, LA DIVERGENCE N'ÉTAIT PAS ATTEIGNABLE : A1
    coerce les types avant A2 et rend ces chaînes en `NaN`. **Mais rien ne
    gardait cette dépendance** — un assemblage manuel des agents sans A1
    (constat `agents/C1`) la rouvrait en silence. *On ne compte pas sur un
    agent amont pour tenir un invariant qu'on peut rendre impossible ici.*

    C'est la doctrine déjà écrite dans `_entete_alerte` : **le chiffre et la
    ligne qu'il décrit viennent de la même source, ou ils finiront par se
    contredire.**
    """
    n = 0 if df is None else len(df)
    total = np.zeros(n, dtype=bool)
    if df is None or plan is None:
        return total
    touches = facteurs_valeurs_absentes(df, plan)
    for f in getattr(plan, 'facteurs', ()) or ():
        if f.nom in touches:
            total |= _masque_absence_facteur(df, f)
    return total


def annexe_revue_facteurs_absents(df, plan) -> list[dict]:
    """Un cas par ligne exclue pour facteur absent — même doctrine que sa
    jumelle des grandeurs, sujet distinct.

    ⚠️ RGPD, identique et non négociable : la position est **positionnelle**,
    jamais l'étiquette du dataframe. *Aucun identifiant client ne peut fuir
    par ce canal.* Elle donne la position et le facteur, et rien d'autre.

    ⚠️ ELLE EST SÉPARÉE DE `annexe_revue_valeurs_absentes` PARCE QUE LES DEUX
    GESTES DIFFÈRENT : l'une accompagne un ARRÊT que l'actuaire doit lever,
    l'autre une EXCLUSION déjà faite qu'il doit vérifier. *Les fondre ferait
    lire un arrêt là où il y a eu une exclusion.*
    """
    if df is None:
        return []
    touches = facteurs_valeurs_absentes(df, plan)
    lignes = []
    for f in getattr(plan, 'facteurs', ()) or ():
        if f.nom not in touches:
            continue
        # ⚠️ LE MEME MASQUE QUE LE COMPTE, ET C'EST LA CONDITION. Un compte
        # derive d'un masque et des positions derivees d'un AUTRE finiraient
        # par se contredire dans un document signe.
        for pos in np.flatnonzero(_masque_absence_facteur(df, f)):
            lignes.append({'position': int(pos), 'facteur': f.nom})
    return sorted(lignes, key=lambda x: (x['position'], x['facteur']))


def exiger_valeurs_absentes_declarees(df, plan) -> dict:
    """SOURCE UNIQUE du refus — les trois grandeurs, jamais les facteurs.

    Rend le compte par grandeur (vide si rien n'est absent). LÈVE si le plan
    ne déclare pas quoi en faire. *Un refus qui arrive après l'imputation
    aurait laissé la valeur inventée dans le tarif.*
    """
    manquants = {}
    for role in ROLES_GRANDEURS:
        col = getattr(plan, role, None)
        if not col or col not in df.columns:
            continue
        n = int(np.asarray(detecter_illisible(df, col), dtype=bool).sum())
        if n:
            manquants[role] = n
    if manquants and getattr(plan, 'valeurs_absentes', None) is None:
        positions = [x['position'] for x in
                     annexe_revue_valeurs_absentes(df, plan)]
        raise ValeurAbsenteNonDeclaree(
            manquants, len(df), empreinte_positions(positions))
    return manquants


class SignatureSansObjet(RuntimeError):
    """⚠️⚠️ UNE SIGNATURE QUI NE VALIDE RIEN EST PIRE QUE PAS DE SIGNATURE.

    Étape ③ du chantier 1-B, 01/09/2026. Le chemin agent reçoit désormais le
    canal `qualite_validee_par` — même nom, même sens que sur le chemin
    déclaratif. Mais la couche qualité n'y est **pas encore branchée** (c'est
    1-B, étape ⑤, et elle déplace un prix) : il n'y a donc **aucun blocage à
    lever**, et une signature n'aurait aucun objet.

    *Un canal qui avale un nom sans rien valider laisse croire à l'actuaire
    qu'il a valid* — c'est exactement la silhouette de `socle/C2`, de la
    plomberie posée que rien n'alimente, et le motif que cet audit poursuit.

    Le canal EXISTE donc, typé, documenté et transporté ; il REFUSE, en
    nommant l'étape qui lui donnera un objet. L'étape ⑤ remplace ce refus par
    l'appel réel.
    """

    def __init__(self, appelant: str, nom: str):
        super().__init__(
            f"{appelant} a recu qualite_validee_par='{nom}', mais le chemin "
            f"agent n'appelle PAS ENCORE la couche qualite (constat "
            f"`qualite/C4`, etape 1-B). Il n'y a donc AUCUN blocage a lever, "
            f"et cette signature ne validerait rien. Le canal existe et sera "
            f"branche a l'etape 5, qui deplace un prix et attend un arbitrage "
            f"nominatif. Pour tarifer AVEC la couche qualite aujourd'hui, "
            f"passer par `pipeline_tarifaire.pipeline_complet`, qui la porte. "
            f"*Accepter ce nom en silence ferait croire a une validation qui "
            f"n'a pas eu lieu.*")
        self.appelant = appelant
        self.nom = nom


def exiger_canal_sans_objet(qualite_validee_par, appelant: str) -> None:
    """SOURCE UNIQUE du refus — jamais recopiée chez les appelants.

    ⚠️ Deux points d'entrée du chemin agent la partagent (`pipeline_agents` et
    `A1.run`) ; deux messages divergents auraient donné deux doctrines. `None`
    passe sans rien changer : *le second sens de ce garde-fou est qu'il ne
    gêne personne tant qu'on ne lui demande rien.*
    """
    if qualite_validee_par is not None:
        raise SignatureSansObjet(appelant, str(qualite_validee_par))


class QualiteBloquante(Exception):
    """Levée par pipeline_complet quand une anomalie ≥ seuil n'est PAS validée par
    un actuaire nommé. Porte le RapportQualite — ce que l'actuaire doit voir pour
    décider. L'échappatoire n'est PAS un try/except mais le champ
    qualite_validee_par (re-run nominatif), afin qu'aucun blocage ne soit
    contournable en silence."""

    def __init__(self, rapport: "RapportQualite"):
        self.rapport = rapport
        codes = ", ".join(rapport.anomalies_au_dela_seuil) or "?"
        # ⚠️⚠️ LA QUESTION EST POSÉE ICI, ET C'EST LE SEUL ENDROIT QUI AIT DU
        # SENS — constat `qualite/C8`. `vulture` a signalé
        # `question_charges_negatives` comme fonction MORTE : elle n'avait
        # **aucun appelant de production**. *C'est la forme de `socle/C2` — de
        # la plomberie posée que rien n'alimente — dans le lot même qui ferme
        # ce motif.* Le blocage est le moment où l'actuaire décide : la
        # question doit y être, pas ailleurs.
        _q = question_charges_negatives(rapport)
        super().__init__(
            f"Controle qualite BLOQUE : anomalie(s) [{codes}] touchant >= "
            f"{rapport.seuil:.0%} des lignes. Confirmation actuarielle nominative "
            f"requise (qualite_validee_par) pour poursuivre."
            + (f"\n\n{_q}" if _q else "")
        )


# ══════════════════════════════════════════════════════════════════════════════
#  STRUCTURES DU RAPPORT (jamais silencieux)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class EffetAgrege:
    """Ce qu'une correction fait au TOTAL d'une colonne — pas à son compte de lignes.

    ⚠️⚠️ CONSTAT `qualite/C3`. Un compte de lignes ne dit pas l'enjeu. Mesuré sur
    un portefeuille exprimé en MOIS : « 1000 ligne(s) CORRIGEE(S) » cachait une
    exposition totale passant de **10 083 à 1 000** — 90,1 % détruite, et une
    prime pure **multipliée par 10,08**. *L'actuaire validait une ligne de
    rapport et obtenait un tarif multiplié par dix.*
    """
    colonne: str
    total_avant: float
    total_apres: float

    @property
    def variation_pct(self) -> float | None:
        """Variation relative du total, ou None si le total de départ est nul."""
        if not self.total_avant:
            return None
        return (self.total_apres - self.total_avant) / self.total_avant * 100.0

    @property
    def facteur_sur_un_ratio(self) -> float | None:
        """De combien est multipliée une grandeur qui DIVISE par cette colonne.

        ⚠️ C'est la lecture qui compte pour une exposition : fréquence et prime
        pure la portent au dénominateur. Diviser par un total dix fois plus
        petit multiplie le résultat par dix.
        """
        if not self.total_apres:
            return None
        return self.total_avant / self.total_apres


@dataclass(frozen=True)
class Anomalie:
    """Une anomalie détectée, avec sa règle, le rôle/colonne concerné, le volume
    et les index — pour une traçabilité complète dans le rapport."""
    code: str            # 'frequence_negative' | 'cout_negatif' | ...
    regle: int           # 1 (exclure) | 2 (corriger) | 3 (signaler)
    role: str            # 'cible_frequence'|'cible_cout'|'exposition'|'identifiant_contrat'|'ligne'
    colonne: Optional[str]
    nb_lignes: int
    proportion: float
    index: Tuple[int, ...]           # positions (0-based) des lignes concernées
    description: str
    correction: Optional[str] = None  # règle 2 : la règle appliquée
    #: ⚠️ Règle 2 uniquement : l'effet de la correction sur le TOTAL de la
    #: colonne. Calculé À LA DÉTECTION, jamais à l'application — parce que le
    #: message qui DÉCIDE est celui du rapport BLOQUÉ, et qu'un rapport bloqué
    #: n'applique par construction aucune correction.
    effet_agrege: EffetAgrege | None = None
    #: Regle 3 des charges nettes negatives : le total et la borne, calcules a
    #: la DETECTION pour que la question se pose sur un rapport BLOQUE.
    resume_charges_negatives: ResumeChargesNegatives | None = None


@dataclass
class RapportQualite:
    lignes_initiales: int
    lignes_retenues: int
    exclusions: List[Anomalie]        # règle 1
    corrections: List[Anomalie]       # règle 2
    signalements: List[Anomalie]      # règle 3
    escalade_declenchee: bool
    anomalies_au_dela_seuil: List[str]
    seuil: float
    validee_par: Optional[str]        # nom de l'actuaire, ou None
    horodatage: Optional[str]         # FOURNI par l'appelant — jamais généré ici
    bloque: bool
    dataframe_propre: Optional[pd.DataFrame]   # None si bloqué

    def resume(self) -> dict:
        """Dict sérialisable (sans les index bruts) pour audit_trail / rapports."""
        def _a(a: Anomalie) -> dict:
            d = {'code': a.code, 'regle': a.regle, 'role': a.role,
                 'colonne': a.colonne, 'nb_lignes': a.nb_lignes,
                 'proportion': round(a.proportion, 4),
                 'description': a.description, 'correction': a.correction}
            # ⚠️ L'audit_trail porte l'effet agrégé quand il existe : ce qui est
            # publié à l'actuaire doit être retrouvable dans la trace.
            if a.effet_agrege is not None:
                d['effet_agrege'] = {
                    'colonne':     a.effet_agrege.colonne,
                    'total_avant': round(a.effet_agrege.total_avant, 4),
                    'total_apres': round(a.effet_agrege.total_apres, 4)}
            return d
        # ⚠️⚠️ CONSTAT `qualite/C6` — AUCUNE PROPORTION TOTALE N'ÉTAIT
        # PUBLIÉE. Le dict portait `lignes_initiales`, `lignes_retenues`
        # et une `proportion` PAR ANOMALIE — jamais la part du
        # portefeuille touchée. Il fallait la soustraire à la main, et
        # *additionner les proportions donne un chiffre FAUX* : deux
        # anomalies peuvent frapper la MÊME ligne.
        # ⚠️ MESURÉ le 01/09 sur un cas construit : somme des `nb_lignes`
        # = 20, UNION des index = 15 — un recouvrement de 5 lignes. La
        # part publiée est donc une UNION, jamais une somme.
        # ⚠️ LES INDEX SONT COMPARABLES, ET C'EST VÉRIFIÉ : toutes les
        # anomalies sont calculées sur le dataframe D'ENTRÉE, que
        # `controler_qualite` ne réaffecte jamais (mesuré par AST). Une
        # union d'index pris dans deux référentiels n'aurait aucun sens.
        _touchees = {i for a in (self.exclusions + self.corrections
                                 + self.signalements) for i in a.index}
        _n0 = max(self.lignes_initiales, 1)
        return {
            'lignes_initiales': self.lignes_initiales,
            'lignes_retenues':  self.lignes_retenues,
            #: UNION des lignes touchées par au moins une anomalie,
            #: rapportée aux lignes INITIALES. Jamais une somme.
            'lignes_touchees':     len(_touchees),
            'proportion_touchee':  round(len(_touchees) / _n0, 4),
            'proportion_exclue':   round(
                (self.lignes_initiales - self.lignes_retenues) / _n0, 4),
            'exclusions':   [_a(a) for a in self.exclusions],
            'corrections':  [_a(a) for a in self.corrections],
            'signalements': [_a(a) for a in self.signalements],
            'escalade_declenchee':    self.escalade_declenchee,
            'anomalies_au_dela_seuil': list(self.anomalies_au_dela_seuil),
            'seuil':       self.seuil,
            'validee_par': self.validee_par,
            'horodatage':  self.horodatage,
            'bloque':      self.bloque,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  DÉTECTEURS PURS — source unique, paramétrés par COLONNE (issue d'un rôle)
#  Retournent un masque booléen np.ndarray aligné sur les lignes de df.
# ══════════════════════════════════════════════════════════════════════════════
def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def detecter_negatifs(df: pd.DataFrame, col: str) -> np.ndarray:
    """Lignes où df[col] < 0 (NaN non compté)."""
    return (_num(df, col) < 0).to_numpy()


def detecter_non_positif(df: pd.DataFrame, col: str) -> np.ndarray:
    """Lignes où df[col] <= 0 (exposition = 0 casse l'offset log — impossible)."""
    return (_num(df, col) <= 0).to_numpy()


def detecter_sup(df: pd.DataFrame, col: str, hi: float) -> np.ndarray:
    """Lignes où df[col] > hi (ex. exposition > 1)."""
    return (_num(df, col) > hi).to_numpy()


def detecter_non_entier(df: pd.DataFrame, col: str) -> np.ndarray:
    """Lignes où df[col] n'est pas entière (comptage attendu — ambigu)."""
    s = _num(df, col)
    return (s.notna() & ((s - np.round(s)).abs() > 1e-9)).to_numpy()


def detecter_incoherence(df: pd.DataFrame, col_freq: str,
                         col_cout: str) -> Tuple[np.ndarray, np.ndarray]:
    """(coût > 0 & fréquence = 0, fréquence > 0 & coût = 0) — les deux sens."""
    f = _num(df, col_freq)
    c = _num(df, col_cout)
    cout_sans_sin = ((c > 0) & (f == 0)).to_numpy()
    sin_sans_cout = ((f > 0) & (c == 0)).to_numpy()
    return cout_sans_sin, sin_sans_cout


def detecter_doublons_id(df: pd.DataFrame, col_id: str,
                         col_ech: str | None = None) -> np.ndarray:
    """Lignes en doublon sur la CLÉ DU CONTRAT (garde la 1re occurrence).

    ⚠️⚠️ UN DOUBLON N'EST PAS UNE ÉCHÉANCE, ET C'EST TOUTE LA DIFFÉRENCE. Le
    même contrat observé sur trois exercices donne trois lignes de même
    identifiant : ce n'est pas une redondance, c'est un **historique**. Mesuré :
    un historique de renouvellement sur 3 ans porte **66,7 % de « doublons »**
    pour un seuil ROUGE à 5 % — le fichier était refusé avant d'être lu, et
    c'est justement la donnée qu'exige l'estimation d'une élasticité.

    ⚠️ A1 FAISAIT DÉJÀ CE CALCUL, PAS CETTE COUCHE-CI. Le mécanisme existait,
    correct, sur le chemin agent ; il était absent du chemin déclaratif — où il
    est en RÈGLE 1, c'est-à-dire **exclusion sans discussion**. *« Corrigé
    OÙ ? » vaut aussi entre deux chemins qui font le même métier.*

    La clé est `(identifiant, échéance)` dès que l'échéance est déclarée ET
    présente ; l'identifiant seul sinon.
    """
    cles = [col_id]
    if col_ech and col_ech in df.columns:
        cles.append(col_ech)
    return df.duplicated(subset=cles, keep='first').to_numpy()


def detecter_absent(df: pd.DataFrame, col: str) -> np.ndarray:
    """Valeur ABSENTE d'une colonne de rôle : `None`, `NaN`, ou chaîne vide.

    ⚠️⚠️ CE DÉTECTEUR EST CELUI DES RÔLES-LIBELLÉS, ET IL NE TESTE PAS LA
    NUMÉRISABILITÉ. C'est toute la différence avec `detecter_illisible`, et
    elle vient d'un défaut mesuré : `identifiant_contrat` passait par le
    détecteur des GRANDEURS, qui compte comme illisible « ce que `to_numeric`
    a détruit ». Un numéro de police est un **libellé** — `P2024-00123`,
    `AUTO/45/8891` — jamais un nombre. Mesuré : sur 400 contrats sans le
    moindre doublon, un identifiant alphanumérique rendait **100 %
    d'illisibles** et BLOQUAIT le fichier ; le même en `1..400` passait sans
    une anomalie.

    ⚠️ UNE ABSENCE, ELLE, RESTE UNE VRAIE AMBIGUÏTÉ. Une ligne sans
    identifiant ne peut être rattachée à aucun contrat : le dédoublonnage ne
    peut pas en juger. Signalée (règle 3), jamais exclue.

    ⚠️⚠️ RELATION AVEC `detecter_illisible`, MESURÉE SUR 25 FORMES, PAS
    SUPPOSÉE : tout ce que ce détecteur voit, l'autre le voit aussi —
    `None`, `NaN`, `''`, `'   '` sont tous détruits par `to_numeric`. L'inverse
    est faux, et c'est le point : `'douze mois'`, `'P2024-001'`, `'null'` sont
    ILLISIBLES pour une grandeur et PRÉSENTS pour un libellé. *J'avais d'abord
    composé `detecter_illisible` à partir d'ici ; la mesure a montré que le
    terme ajouté ne changeait rien — il a été retiré plutôt que gardé pour la
    forme.*

    ⚠️ BORNE DÉCLARÉE : `'None'`, `'null'`, `'NaN'` écrits en TEXTE sont
    comptés PRÉSENTS. Ce sont peut-être des artefacts de sérialisation d'une
    valeur manquante — mais rien dans la donnée ne le dit, et accuser sans
    savoir serait pire que se taire.
    """
    brut = df[col]
    return np.asarray(brut.isna() | (brut.astype(str).str.strip() == ''))


def detecter_illisible(df: pd.DataFrame, col: str) -> np.ndarray:
    """Valeurs MANQUANTES ou NON NUMÉRISABLES d'une colonne de rôle.

    ⚠️⚠️ LE SEUL DÉTECTEUR QUI REGARDE CE QUE `to_numeric` A DÉTRUIT. Tous les
    autres comparent la série *après* `errors='coerce'`, et **une comparaison
    sur un NaN est toujours fausse** : le trou devenait invisible à la couche
    dont c'est le métier de juger la qualité (constat `qualite/C1`).

    On compte comme illisible ce qui est vide À L'ARRIVÉE et ne l'était pas
    forcément au départ : `None`, `NaN`, chaîne vide, et toute valeur que
    `to_numeric` n'a pas su convertir (« douze mois »).
    """
    brut = df[col]
    return np.asarray(_num(df, col).isna() | brut.isna()
                      | (brut.astype(str).str.strip() == ''))


def detecter_doublons_ligne(df: pd.DataFrame) -> np.ndarray:
    """Lignes strictement identiques à une précédente (garde la 1re)."""
    return df.duplicated(keep='first').to_numpy()


# ══════════════════════════════════════════════════════════════════════════════
#  RÈGLE 2 — registre des corrections ÉTABLIES (extensible). Phase 0 : 1 entrée.
#  Chaque entrée : (rôle, code, seuil, valeur_plafond, description).
# ══════════════════════════════════════════════════════════════════════════════
#: ⚠️ LE PLAFOND VIVAIT EN QUATRE LITTÉRAUX `1.0` — la docstring du module, la
#: détection, le libellé de la correction et son application. Trois d'entre eux
#: DÉCIDENT ; si l'un change, les autres divergent en silence. Ce lot en a
#: besoin d'une source unique parce que l'effet agrégé se DÉRIVE du plafond :
#: le calculer à côté aurait ajouté un cinquième littéral.
#: ⚠️ La valeur est INCHANGÉE — aucun euro ne bouge, et c'est vérifié.
PLAFOND_EXPOSITION = 1.0
# (Gardé explicite plutôt que data-driven pour rester lisible en Phase 0 ;
#  l'unique correction établie est le plafond d'exposition, déjà présent côté
#  legacy dans A2._traiter_exposition.)

#: ⚠️⚠️ LA BORNE DÉRIVE DE L'UNITÉ DÉCLARÉE AU PLAN — étape 2 du chantier
#: `unite_exposition`, constat `qualite/C3`. Jusqu'ici la borne valait 1,0 sur
#: une hypothèse ANNUELLE que rien n'avait vérifiée : un fichier en mois y
#: perdait 90 % de son exposition, donc voyait sa prime multipliée par ~10.
#: ⚠️ `366` et non `365` : une année bissextile est un cas normal, pas une
#: aberration. *Une borne trop serrée d'un jour écraserait une donnée juste.*
#: ⚠️ Ces clés NE PEUVENT PAS être dérivées du `Literal` — une correspondance
#: n'est pas une appartenance. Un contrôle vérifie donc qu'elles LUI SONT
#: ÉGALES : ajouter une unité sans sa borne fait rougir la gate au lieu de
#: lever en production.
BORNES_EXPOSITION: dict[str, float] = {
    'annee': PLAFOND_EXPOSITION,
    'mois': 12.0,
    'jour': 366.0,
}


def borne_exposition(plan) -> float:
    """La borne de plausibilité de l'exposition, DÉRIVÉE de l'unité du plan.

    ⚠️ Unité non déclarée -> `PLAFOND_EXPOSITION` : le comportement
    d'aujourd'hui, à l'identique. *L'hypothèse annuelle n'est pas retirée, elle
    cesse d'être MUETTE* — `phrase_unite_non_declaree` la publie.
    """
    unite = getattr(plan, 'unite_exposition', None)
    if unite is None:
        return PLAFOND_EXPOSITION
    if unite not in BORNES_EXPOSITION:
        # ⚠️ Inatteignable via `PlanTarifaire`, dont la porte lève déjà. Gardé
        # pour l'appelant qui passerait un objet quelconque : un défaut
        # silencieux sur une borne qui décide d'un prix est ce que `a6/C9` a
        # fermé.
        raise ValueError(
            f"unite_exposition='{unite}' sans borne connue — attendu "
            f"{' ou '.join(repr(x) for x in sorted(BORNES_EXPOSITION))}.")
    return BORNES_EXPOSITION[unite]


#: Comment se dit l'implausibilité, selon l'unité. ⚠️ Le texte d'aujourd'hui —
#: « implausible pour un contrat annuel » — devient FAUX dès qu'une unité autre
#: est déclarée : la phrase doit suivre la borne qu'elle explique.
_PLAUSIBILITE = {
    'annee': 'implausible pour un contrat annuel.',
    'mois': 'implausible pour une exposition exprimee en mois.',
    'jour': 'implausible pour une exposition exprimee en jours.',
}


def phrase_plausibilite(unite: str | None) -> str:
    """⚠️ Unité non déclarée : la phrase d'AUJOURD'HUI, au caractère près."""
    return _PLAUSIBILITE[unite or 'annee']


def phrase_unite_non_declaree(unite: str | None) -> str:
    """L'hypothèse annuelle, DITE — le coeur de `qualite/C3`.

    ⚠️⚠️ ELLE NE S'AJOUTE QUE SI L'UNITÉ MANQUE. Une phrase qui apparaîtrait
    aussi quand l'unité EST déclarée ne dirait plus rien : *un avertissement
    permanent est un avertissement qu'on cesse de lire.*
    """
    if unite is not None:
        return ''
    return (" UNITE NON DECLAREE au plan : l'hypothese ANNUELLE a ete "
            "supposee, et c'est elle qui fixe cette borne. Si ce fichier est "
            "exprime en mois ou en jours, declarez `unite_exposition` au "
            "plan -- sans quoi cette correction detruit une donnee JUSTE, et "
            "l'exposition etant le denominateur de la prime, celle-ci est "
            "multipliee d'autant.")


def unite_apparente(maximum_observe: float) -> str | None:
    """L'unité à laquelle la DONNÉE ressemble, lue dans le jeu des bornes.

    ⚠️⚠️ AUCUN SEUIL INVENTÉ, ET C'EST LE POINT. On rend l'unité la plus
    GROSSIÈRE dont la borne contient le maximum observé : un maximum de 0,9
    ressemble à `annee`, 11,5 à `mois`, 200 à `jour`. *Le signal se dérive
    entièrement de l'ensemble fermé ; il n'y a pas de constante à justifier.*

    Rend `None` si aucune unité ne convient (maximum au-delà de la plus large).
    """
    for unite, borne in sorted(BORNES_EXPOSITION.items(), key=lambda x: x[1]):
        if maximum_observe <= borne:
            return unite
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  ORCHESTRATEUR
# ══════════════════════════════════════════════════════════════════════════════
def controler_qualite(
    df: pd.DataFrame,
    plan: "PlanTarifaire",
    qualite_validee_par: Optional[str] = None,
    horodatage: Optional[str] = None,
    seuil_escalade: float = SEUIL_ESCALADE,
) -> RapportQualite:
    """
    Applique les 4 règles, pilotées par les RÔLES du plan. Ne mute jamais `df`
    en place ; retourne un RapportQualite (avec `dataframe_propre` si non bloqué).
    Ne génère aucun horodatage — réutilise celui fourni par l'appelant.

    Ordre : détecter tout (1-3) → gate d'escalade (avant toute mutation) →
    appliquer (exclure 1, corriger 2, laisser 3) → rapport.
    """
    n0 = len(df)
    col_freq = plan.cible_frequence
    col_cout = plan.cible_cout
    col_expo = plan.exposition
    col_id = getattr(plan, "identifiant_contrat", None)
    col_ech = getattr(plan, "echeance", None)
    #: L'échéance est-elle utilisable ? Déclarée AU PLAN **et** présente dans
    #: les données — déclarer une colonne absente ne change rien au calcul.
    echeance_utilisable = bool(col_ech and col_ech in df.columns)

    anomalies: List[Anomalie] = []

    def _ajouter(code, regle, role, colonne, mask, description, correction=None,
                 effet_agrege=None, resume_cn=None):
        idx = np.flatnonzero(np.asarray(mask, dtype=bool))
        if idx.size == 0:
            return
        anomalies.append(Anomalie(
            code=code, regle=regle, role=role, colonne=colonne,
            nb_lignes=int(idx.size), proportion=idx.size / max(n0, 1),
            index=tuple(int(i) for i in idx),
            description=description, correction=correction,
            effet_agrege=effet_agrege, resume_charges_negatives=resume_cn))

    # ── RÈGLE 1 : IMPOSSIBLE → exclure ───────────────────────────────────────
    if col_freq in df.columns:
        # ⚠️⚠️ MESSAGE RÉÉCRIT POUR L'ACTUAIRE — arbitré par Selasse, 02/09.
        # L'ancien disait : « cible_frequence ('nb_sinistres') < 0 — nombre de
        # sinistres negatif, impossible. » Il nommait une COLONNE TECHNIQUE, ne
        # disait NI combien de contrats, NI ce que ça coûte, NI quoi faire.
        # *Un message que l'actuaire doit traduire avant de décider n'est pas
        # un message, c'est un code source.* Le code technique subsiste comme
        # ÉTIQUETTE de traçabilité, publiée à part par la synthèse.
        _m_freq = detecter_negatifs(df, col_freq)
        _ajouter('frequence_negative', 1, 'cible_frequence', col_freq, _m_freq,
                 _entete_alerte(_m_freq, n0, "Nombre de sinistres négatif")
                 + " Un contrat ne peut pas avoir moins de zéro sinistre. Cela"
                   " vient presque toujours d'une annulation enregistrée en"
                   " soustraction au lieu d'être supprimée. Ces contrats font"
                   " baisser la sinistralité moyenne du portefeuille, donc la"
                   " prime de tous les autres."
                   " CE QUI SE PASSE SI LE TARIF EST PRODUIT : ces contrats"
                   " sont retirés du calcul."
                   " CE QUE VOUS DEVEZ FAIRE : reprendre l'extraction pour ces"
                   " lignes, ou confirmer nommément que le tarif peut être"
                   " produit sans elles.")
    # ⚠️⚠️ LE COÛT A QUITTÉ LA RÈGLE 1 — constat `qualite/C8`, RANG 1, 31/08/2026.
    # La doctrine confondait deux grandeurs : un COÛT (un prix) est >= 0, mais
    # `cout_total_sinistres` est une CHARGE NETTE — paiements moins recours — et
    # elle peut légitimement être négative. Subrogation, sauvetage, récupération
    # sur tiers : l'assureur encaisse plus qu'il n'a payé.
    #
    # Mesuré sur la seule donnée réelle versionnée (14 243 sinistres) :
    #   1 116 contrats-annee sur 12 654 = 8,82 %, soit -563 749 EUR
    #   les EXCLURE fait monter la prime moyenne de 926,55 a 1 065,03 EUR : +14,9 %
    #
    # ⚠️ ET AUCUN INDICE NE PERMET DE TRANCHER AUTOMATIQUEMENT. Les deux
    # discriminants mesurés se chevauchent entièrement, et les deux groupes se
    # disqualifient : 44 des 80 cas « couverts » réclament plus que ce qui a été
    # payé, et AUCUN des 1 036 « non couverts » n'est aberrant (tous sous 1,87 x
    # le coût moyen positif — une erreur de saisie produirait une queue).
    # *Erreurs et recours coexistent ; ni l'un ni l'autre n'est la règle.*
    #
    # ⚠️⚠️ RÈGLE 3, DONC : signaler, CONSERVER, et ne décider à la place de
    # personne. La doctrine du module l'écrit déjà — « AMBIGU -> NE DÉCIDE
    # RIEN ». C'est exactement cela.
    if col_cout in df.columns:
        _m_cout_neg = detecter_negatifs(df, col_cout)
        _vals_cout = pd.to_numeric(df[col_cout], errors='coerce')
        _ajouter('cout_net_negatif', 3, 'cible_cout', col_cout,
                 _m_cout_neg,
                 f"cible_cout ('{col_cout}') < 0 sur certaines lignes — une "
                 f"charge NETTE negative peut etre un RECOURS legitime "
                 f"(subrogation, sauvetage) ou une ERREUR DE SAISIE. Les deux "
                 f"existent. Ces lignes sont CONSERVEES et signalees : ce "
                 f"controle voit le portefeuille agrege, jamais le detail des "
                 f"sinistres, et ne peut donc pas trancher.",
                 resume_cn=_resume_charges_negatives(_vals_cout, _m_cout_neg))
    if col_expo in df.columns:
        # ⚠️ L'ancien message parlait d'« offset log » : du jargon de modèle
        # dans un document que signe un actuaire et que lit le CAC.
        _m_expo = detecter_non_positif(df, col_expo)
        _ajouter('exposition_non_positive', 1, 'exposition', col_expo, _m_expo,
                 _entete_alerte(_m_expo, n0,
                                "Durée de couverture nulle ou négative")
                 + " Un contrat dont la durée est nulle n'a jamais été en"
                   " vigueur. Le garder reviendrait à enregistrer une période"
                   " sans sinistre qui n'a pas existé : la sinistralité"
                   " paraîtrait plus faible qu'elle ne l'est, et la prime de"
                   " tous les autres contrats baisserait."
                   " CE QUI SE PASSE SI LE TARIF EST PRODUIT : ces contrats"
                   " sont retirés du calcul."
                   " CE QUE VOUS DEVEZ FAIRE : vérifier les dates d'effet et"
                   " d'échéance de ces lignes, ou confirmer nommément que le"
                   " tarif peut être produit sans elles.")
    # ⚠️⚠️ LA RÈGLE CHANGE AVEC CE QUE LE PLAN DÉCLARE, ET C'EST VOULU.
    # Avec une échéance, deux lignes de même clé sont un VRAI doublon :
    # impossible, donc règle 1, exclu. Sans échéance, on ne peut PAS distinguer
    # un doublon d'un historique de renouvellement : la constatation devient
    # AMBIGUË, donc règle 3 — signalée, la ligne est CONSERVÉE.
    # *Exclure sans pouvoir trancher, c'est trancher à la place de l'actuaire.*
    if col_id and col_id in df.columns:
        if echeance_utilisable:
            _m_dbl = detecter_doublons_id(df, col_id, col_ech)
            _ajouter('doublon_identifiant', 1, 'identifiant_contrat', col_id,
                     _m_dbl,
                     _entete_alerte(
                         _m_dbl, n0,
                         "Le même contrat compté deux fois pour la même "
                         "échéance", unite='ligne')
                     + " Ces lignes portent le même numéro de contrat et la"
                       " même date d'échéance : c'est la même période comptée"
                       " deux fois. La durée de couverture ET les sinistres"
                       " sont doublés pour ces contrats — ils pèsent deux fois"
                       " plus lourd que les autres dans le tarif."
                       " CE QUI SE PASSE SI LE TARIF EST PRODUIT : une seule"
                       " ligne est conservée par contrat et par échéance."
                       " CE QUE VOUS DEVEZ FAIRE : vérifier s'il s'agit d'un"
                       " doublon d'extraction ou de deux garanties distinctes"
                       " du même contrat.")
        else:
            _ajouter('doublon_identifiant_sans_echeance', 3,
                     'identifiant_contrat', col_id,
                     detecter_doublons_id(df, col_id),
                     f"lignes portant le MEME identifiant de contrat "
                     f"('{col_id}'). AUCUNE echeance n'est declaree au plan : "
                     f"impossible de distinguer un doublon d'un HISTORIQUE de "
                     f"renouvellement. Ces lignes sont CONSERVEES et signalees. "
                     f"Declarer `echeance` au plan rend la distinction "
                     f"opposable.")

    # ── RÈGLE 2 : IMPLAUSIBLE établi → corriger (plafond exposition) ──────────
    # ⚠️⚠️ LA BORNE VIENT DE L'UNITÉ DÉCLARÉE AU PLAN. Non déclarée :
    # `PLAFOND_EXPOSITION`, comportement historique à l'identique.
    #
    # ⛔ CE COMMENTAIRE A AFFIRMÉ « Aucun des 20 plans ne déclare d'unité » DE
    # L'ÉTAPE 2 JUSQU'AU 01/09/2026, ET C'EST DEVENU FAUX À L'ÉTAPE 5 DU MÊME
    # CHANTIER : **les 20 plans déclarent `annee`** (re-mesuré le 01/09). La
    # conclusion tient — `borne_exposition('annee')` vaut 1,0, exactement
    # `PLAFOND_EXPOSITION`, donc aucun euro n'a bougé — mais elle tenait par
    # une raison que la phrase ne disait plus. *Une phrase de portée se mesure
    # comme un chiffre, et celle-ci a survécu quatre jours à sa propre mesure.*
    # `PM-1` la dérive désormais des plans réels.
    #
    # ⚠️⚠️ ET LA CONSÉQUENCE N'EST PAS QUE TEXTUELLE : puisque l'unité EST
    # déclarée, la RÈGLE 3 ci-dessous est VIVANTE en production. Mesuré :
    # une seule ligne à 1,02 an sur 20 000 produit un signal sur 100 % des
    # lignes, donc une escalade, donc un blocage à signature.
    _borne = borne_exposition(plan)
    _unite = getattr(plan, 'unite_exposition', None)
    mask_corr_expo = None
    if col_expo in df.columns:
        mask_corr_expo = detecter_sup(df, col_expo, _borne)
        # ⚠️⚠️ L'EFFET AGRÉGÉ SE CALCULE ICI, À LA DÉTECTION — constat
        # `qualite/C3`. Le message qui DÉCIDE est celui du rapport BLOQUÉ, et un
        # rapport bloqué n'applique aucune correction : le mesurer à
        # l'application l'aurait rendu absent du seul moment où il sert.
        # Il se dérive du MÊME masque et du MÊME plafond que l'application.
        _effet = None
        _brut = pd.to_numeric(df[col_expo], errors='coerce')
        if _brut.notna().any():
            _apres = _brut.where(~pd.Series(mask_corr_expo, index=df.index),
                                 _borne)
            _effet = EffetAgrege(colonne=col_expo,
                                 total_avant=float(_brut.sum()),
                                 total_apres=float(_apres.sum()))
        _ajouter('exposition_sup_1', 2, 'exposition', col_expo, mask_corr_expo,
                 f"exposition ('{col_expo}') > {_borne:g} — "
                 f"{phrase_plausibilite(_unite)}"
                 f"{phrase_unite_non_declaree(_unite)}",
                 # ⚠️ `{_borne}` et NON `:g` : le libellé publié disait
                 # « plafond a 1.0 », et `:g` l'aurait rendu « plafond a
                 # 1 ». *Dériver un texte d'une constante ne donne pas le droit
                 # d'en changer la forme : c'est une surface que l'actuaire lit.*
                 correction=f"plafond a {_borne}",
                 effet_agrege=_effet)

    # ── RÈGLE 3 (unité) : LA DONNÉE CONTREDIT L'UNITÉ DÉCLARÉE → signaler ─────
    # ⚠️⚠️ SANS CE CONTRÔLE, LE MÉCANISME SERAIT DÉCORATIF. Déclarer `mois`
    # élargit la borne à 12 : plus rien ne peut être attrapé, et une déclaration
    # fausse passerait pour une déclaration juste. *Un instrument qui ne peut
    # plus rien signaler cesse d'être un instrument.*
    # ⚠️ SIGNALER, JAMAIS CORRIGER (règle 3). Un portefeuille d'assistance dont
    # tous les contrats durent moins d'un mois ressemble légitimement à des
    # années : c'est à l'actuaire de trancher, pas à la couche.
    # ⚠️⚠️ LE MASQUE PORTE LES LIGNES QUI SONT LA PREUVE — étape ② du chantier
    # 1-B, 01/09/2026. Il valait `np.ones(len(df))` : **toutes** les lignes.
    # Mesuré sur 20 000 contrats dont UNE SEULE à 1,02 an — 0,005 % — le signal
    # sortait à **100 %**, donc au-dessus du seuil d'escalade, donc le fichier
    # entier était BLOQUÉ par une ligne. *Un signal qui désigne tout le monde
    # ne désigne personne, et il escalade sur sa propre imprécision.*
    #
    # ⚠️⚠️ ET L'ASSIETTE EST ASYMÉTRIQUE, POUR UNE RAISON QUI SE MESURE. La
    # contradiction se lit dans DEUX sens, et la preuve n'a pas la même forme :
    #
    #   · DONNÉE TROP GRANDE pour l'unité déclarée (`annee` déclarée,
    #     max 1,02) — les lignes AU-DESSUS de la borne sont la preuve, et
    #     elles seules. Ce sont exactement celles que la règle 2 plafonne.
    #   · DONNÉE TROP PETITE (`mois` déclarée, max 0,9) — **aucune** ligne ne
    #     dépasse la borne de 12 : la preuve est que TOUTES sont petites.
    #     Le masque reste donc total, et l'escalade avec lui.
    #
    # *Restreindre les deux sens aurait fait disparaître le second signal :
    # `_ajouter` ignore un masque vide, et une déclaration `mois` fausse serait
    # redevenue muette — exactement le décor que ce contrôle existe pour
    # empêcher (`UX-12` l'exige bloquant).*
    if _unite is not None and col_expo in df.columns:
        _obs = pd.to_numeric(df[col_expo], errors='coerce')
        if _obs.notna().any():
            _max = float(_obs.max())
            _apparente = unite_apparente(_max)
            if _apparente is not None and _apparente != _unite:
                _trop_grand = _max > _borne
                _preuve = (detecter_sup(df, col_expo, _borne) if _trop_grand
                           else np.ones(len(df), dtype=bool))
                _ou = ("les lignes au-dessus de la borne, et elles seules"
                       if _trop_grand else
                       "TOUTES les lignes : aucune ne depasse la borne, et "
                       "c'est precisement la preuve")
                _ajouter(
                    'unite_exposition_contredite', 3, 'exposition', col_expo,
                    _preuve,
                    _entete_alerte(
                        _preuve, n0,
                        "Les durées de couverture ne ressemblent pas à "
                        "l'unité déclarée au plan", unite='ligne')
                    + f" Le plan tarifaire déclare que les durées sont"
                      f" exprimées en « {_unite} » ; les valeurs observées"
                      f" ressemblent à des « {_apparente} » (durée maximale"
                      f" relevée : {_max:.4g}). Signalé sur {_ou}."
                      f" Si l'unité déclarée est fausse, la limite de"
                      f" plausibilité l'est aussi : des durées légitimes"
                      f" seront écrasées, ou des durées aberrantes passeront"
                      f" sans être vues. LA DURÉE EST LE DÉNOMINATEUR DU"
                      f" TARIF : si elle est fausse, toutes les primes le"
                      f" sont."
                      f" CE QUI SE PASSE SI LE TARIF EST PRODUIT : rien n'est"
                      f" corrigé — le système ne devine pas l'unité à votre"
                      f" place."
                      f" CE QUE VOUS DEVEZ FAIRE : corriger"
                      f" `unite_exposition` dans le plan tarifaire, ou"
                      f" confirmer nommément que l'unité déclarée est la"
                      f" bonne.",
                    correction='aucune -- contradiction SIGNALEE')

    # ── RÈGLE 3 : AMBIGU → signaler, laisser tel quel ────────────────────────
    # ⚠️⚠️ LA VALEUR MANQUANTE OU ILLISIBLE — constat `qualite/C1`.
    # Aucune des quatre règles ne la voyait : tous les détecteurs passent par
    # `pd.to_numeric(errors='coerce')`, et **toute comparaison est FAUSSE sur
    # un NaN** (`NaN < 0`, `NaN <= 0`, `NaN > 1` — toutes fausses), tandis que
    # `detecter_non_entier` exclut explicitement les NaN par `s.notna()`.
    # Mesuré : **une colonne d'exposition entièrement vide traversait la couche
    # avec ZÉRO anomalie**, et la synthèse des livrables rendait `None` —
    # c'est-à-dire « rien à signaler ». Une exposition écrite « douze mois »
    # faisait de même.
    #
    # ⚠️ POURQUOI RÈGLE 3, ET PAS RÈGLE 1. Une valeur manquante est **AMBIGUË**,
    # pas impossible : elle peut être un vrai zéro mal encodé, une erreur de
    # transmission, ou une grandeur réellement inconnue — **rien dans la donnée
    # ne le dit**. La doctrine du module est explicite : impossible → exclure,
    # implausible établi → corriger, **ambigu → signaler et laisser tel quel**.
    # Exclure serait trancher à la place de l'actuaire, et déplacerait des
    # lignes sur un jugement que la donnée ne porte pas.
    # ⚠️ Le garde-fou en aval demeure : le GLM s'arrête *loud* sur un NaN
    # (`ValueError: NaN, inf or invalid value detected in endog`). Ce qui
    # change, c'est que l'actuaire reçoit désormais un rapport de QUALITÉ, et
    # non une erreur `statsmodels` qui ne nomme pas la colonne fautive.
    # ⚠️⚠️ DEUX ASSIETTES, PARCE QU'IL Y A DEUX NATURES DE ROLE.
    # Les trois roles ci-dessous sont des GRANDEURS : y compter comme illisible
    # ce que `to_numeric` a detruit est exactement leur metier.
    for _role, _col in (('exposition', col_expo),
                        ('cible_frequence', col_freq),
                        ('cible_cout', col_cout)):
        if not _col or _col not in df.columns:
            continue
        _manquant = detecter_illisible(df, _col)
        _ajouter(f'valeur_illisible_{_role}', 3, _role, _col, _manquant,
                 f"{_role} ('{_col}') : valeur MANQUANTE ou ILLISIBLE — "
                 f"ambigu (ni exclu ni corrige). Aucune regle ne peut trancher "
                 f"entre un vrai zero, une erreur de saisie et une grandeur "
                 f"inconnue : c'est a l'actuaire de le dire.")

    # ⚠️⚠️ L'IDENTIFIANT EST UN LIBELLE, PAS UNE GRANDEUR. Il figurait dans la
    # boucle ci-dessus, ou `detecter_illisible` le declarait illisible des
    # qu'il n'etait pas numerique : mesure, 100 % sur des identifiants tout a
    # fait normaux, et le fichier BLOQUAIT. Seule son ABSENCE est ambigue.
    # ⚠️ RGPD : ce message ne cite NI valeur NI index -- un compte suffit.
    if col_id and col_id in df.columns:
        _ajouter('valeur_absente_identifiant_contrat', 3, 'identifiant_contrat',
                 col_id, detecter_absent(df, col_id),
                 f"identifiant_contrat ('{col_id}') : valeur ABSENTE — la ligne "
                 f"ne peut etre rattachee a aucun contrat, le dedoublonnage ne "
                 f"peut donc pas en juger. Ambigu : signale, jamais exclu. Un "
                 f"identifiant NON NUMERIQUE est normal et n'est pas signale.")

    if col_freq in df.columns and col_cout in df.columns:
        cout_sans_sin, sin_sans_cout = detecter_incoherence(df, col_freq, col_cout)
        _ajouter('incoherence_cout_sans_sin', 3, 'cible_cout', col_cout, cout_sans_sin,
                 "cout > 0 avec frequence = 0 — ambigu (ni exclu ni corrige).")
        _ajouter('incoherence_sin_sans_cout', 3, 'cible_frequence', col_freq, sin_sans_cout,
                 "frequence > 0 avec cout = 0 — ambigu (ni exclu ni corrige).")
    if col_freq in df.columns:
        _ajouter('frequence_non_entiere', 3, 'cible_frequence', col_freq,
                 detecter_non_entier(df, col_freq),
                 f"cible_frequence ('{col_freq}') non entiere — ambigu (comptage attendu).")
    if not (col_id and col_id in df.columns):
        # Pas d'identifiant de contrat déclaré → un doublon de ligne entière est
        # AMBIGU (deux contrats identiques peuvent être réels) : règle 3.
        _ajouter('doublon_ligne', 3, 'ligne', None, detecter_doublons_ligne(df),
                 "ligne strictement identique a une autre — ambigu sans identifiant pour trancher.")

    # ── RÈGLE 4 : ESCALADE PAR PROPORTION (avant toute mutation) ─────────────
    # ⚠️⚠️ L'UNION COMPTE AUTANT QUE CHAQUE TYPE — constat `qualite/C2`.
    # La règle ne regardait que `a.proportion` type par type. Mesuré avec
    # quatre types à **4,9 % chacun** : **196 lignes sur 1 000 exclues, soit
    # 19,6 % du portefeuille, et `escalade = False`.** Aucun type n'atteignait
    # le seuil ; leur union le dépassait de quatre fois.
    # *Un garde-fou qui ne regarde qu'une anomalie à la fois ne voit pas
    # l'état du portefeuille — c'est la question « sur quelle ASSIETTE ? »
    # posée à un seuil.*
    #
    # ⚠️ LES DEUX CRITÈRES SONT CONSERVÉS, PAS SUBSTITUÉS : un seul type à
    # 6 % doit toujours escalader, même si l'union n'ajoute rien. Le nouveau
    # critère ne peut donc qu'AJOUTER des escalades, jamais en retirer — c'est
    # la règle d'asymétrie : une liste qui accuse ne peut pas ouvrir de trou.
    # ⚠️⚠️ ET DEPUIS LE 02/09, SEULS QUATRE TYPES PEUVENT FAIRE ESCALADER —
    # `CODES_DISQUALIFIANTS`, arbitré par Selasse sur les chiffres de l'étape 4.
    # Le filtre porte sur LES DEUX critères : un type hors liste n'escalade pas
    # seul, ET n'entre pas dans l'union. *Le laisser dans l'union le rendrait
    # bloquant par la bande — un garde-fou qu'on croit désarmé et qui tire.*
    #
    # ⚠️ CE FILTRE NE PEUT QU'ENLEVER DES ESCALADES, JAMAIS EN AJOUTER : il
    # restreint deux ensembles, il n'en élargit aucun. Mesuré sur la donnée
    # réelle : `cout_net_negatif` y touche 8,82 % des contrats et escaladait ;
    # il n'escalade plus, et c'est le but — une charge nette négative est
    # légitime. *Un blocage qu'on lève chaque semaine n'est plus un blocage.*
    _bloquantes = [a for a in anomalies if a.code in CODES_DISQUALIFIANTS]
    au_dela = [a.code for a in _bloquantes if a.proportion >= seuil_escalade]
    lignes_touchees = set()
    for a in _bloquantes:
        lignes_touchees.update(a.index)
    proportion_union = len(lignes_touchees) / max(n0, 1)
    if proportion_union >= seuil_escalade and not au_dela:
        # On ne le signale que si aucun type ne l'avait déjà déclenché, pour
        # que le motif publié nomme la VRAIE raison de l'escalade.
        au_dela = [(f'union_des_anomalies ({len(lignes_touchees)}/{n0} lignes, '
                    f'{proportion_union:.1%})')]
    escalade = len(au_dela) > 0
    exclusions = [a for a in anomalies if a.regle == 1]
    corrections = [a for a in anomalies if a.regle == 2]
    signalements = [a for a in anomalies if a.regle == 3]

    if escalade and not qualite_validee_par:
        # BLOQUÉ : on ne mute rien, on ne tarife rien. dataframe_propre = None.
        return RapportQualite(
            lignes_initiales=n0, lignes_retenues=n0,
            exclusions=exclusions, corrections=corrections, signalements=signalements,
            escalade_declenchee=True, anomalies_au_dela_seuil=au_dela,
            seuil=seuil_escalade, validee_par=None, horodatage=horodatage,
            bloque=True, dataframe_propre=None)

    # ── APPLICATION : règle 1 exclut, règle 2 corrige, règle 3 ne touche rien ─
    dfp = df.copy()
    # Règle 2 d'abord (les lignes exclues ensuite seront de toute façon retirées).
    if mask_corr_expo is not None and mask_corr_expo.any():
        # ⚠️ LA MÊME borne qu'à la détection et qu'à l'effet agrégé : les trois
        # se dérivent de `_borne`. *Trois endroits, une seule valeur — c'est
        # exactement ce que 1d a rendu possible.*
        dfp.loc[mask_corr_expo, col_expo] = _borne
    # Règle 1 : union des masques d'exclusion.
    excl = np.zeros(n0, dtype=bool)
    for a in exclusions:
        m = np.zeros(n0, dtype=bool)
        m[list(a.index)] = True
        excl |= m
    if excl.any():
        dfp = dfp.loc[~excl].reset_index(drop=True)   # index propre seulement si on retire

    return RapportQualite(
        lignes_initiales=n0, lignes_retenues=len(dfp),
        exclusions=exclusions, corrections=corrections, signalements=signalements,
        escalade_declenchee=escalade, anomalies_au_dela_seuil=au_dela,
        seuil=seuil_escalade,
        validee_par=(qualite_validee_par if escalade else None),
        horodatage=horodatage, bloque=False, dataframe_propre=dfp)


# ══════════════════════════════════════════════════════════════════════════════
#  SURFAÇAGE — source unique pour Excel / Word / HTML (comme synthese_exclusions)
# ══════════════════════════════════════════════════════════════════════════════
def _date_lisible(ts: Optional[str]) -> Optional[str]:
    """Reformate un horodatage ISO existant en JJ/MM/AAAA. Ne génère rien."""
    if not ts:
        return None
    jour = str(ts).split('T')[0]
    p = jour.split('-')
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else jour


#: ⚠️ Version de SCHÉMA de l'empreinte des positions — même patron que
#: `EMPREINTE_SCHEMA` du plan. Elle bouge quand la COMPOSITION de ce qui est
#: haché change, pour qu'une empreinte ancienne se reconnaisse comme HÉRITÉE au
#: lieu de paraître simplement différente.
EMPREINTE_REVUE_SCHEMA = 1


def empreinte_positions(positions) -> str:
    """SHA-256 des positions concernées, préfixé par sa version de schéma.

    ⚠️⚠️ SANS ELLE, ON SAIT QU'UN ACTUAIRE A RÉPONDU, PAS SUR QUOI. Si le
    fichier change et qu'on rejoue, la réponse **ne doit plus valoir** — et le
    système doit le DÉTECTER, pas le supposer. C'est ce qui rend la réponse
    opposable devant un commissaire : elle est attachée à un contenu, pas à une
    intention.

    ⚠️ Le préfixe `rN:` reprend la leçon de `PlanTarifaire.empreinte()` : un
    comparateur lit le schéma **sans recalculer**, et une empreinte sans préfixe
    est reconnue comme héritée plutôt que fausse.
    """
    charge = json.dumps({"schema": EMPREINTE_REVUE_SCHEMA,
                         "positions": sorted(int(p) for p in positions)},
                        sort_keys=True)
    return (f"r{EMPREINTE_REVUE_SCHEMA}:"
            f"{hashlib.sha256(charge.encode()).hexdigest()[:16]}")


def annexe_revue_charges_negatives(rapport, df) -> list[dict]:
    """Un cas par ligne, pour que l'actuaire VOIE ce qu'on lui demande de juger.

    ⚠️⚠️ DEUX SURFACES, DEUX AUDIENCES — et la règle RGPD déjà posée n'est PAS
    affaiblie. La SYNTHÈSE (rapport signé, circulé) ne cite ni valeur ni index,
    et deux sentinelles le vérifient. Cette ANNEXE, elle, ne quitte pas le poste
    de l'actuaire : elle porte la **position de la ligne dans SON fichier** —
    une coordonnée que lui seul peut résoudre, jamais un identifiant client.

    ⚠️⚠️ ET ELLE NE PROMET QUE CE QU'ELLE PEUT PRODUIRE. J'y avais d'abord prévu
    « la somme des montants POSITIFS du contrat », mesurée comme le meilleur
    discriminant. **Cette couche ne la voit pas** : elle reçoit une ligne par
    CONTRAT, jamais le détail des sinistres. Le substitut testé —
    `nb_sinistres > 0` — est vrai pour **100 %** des cas : il ne sépare rien.
    *Une colonne que le code ne peut pas remplir est exactement le défaut que
    cet audit poursuit.* Elle a été retirée.
    """
    cas = [a for a in (rapport.signalements or [])
           if a.code == 'cout_net_negatif']
    if not cas or df is None:
        return []
    a = cas[0]
    col = a.colonne
    valeurs = pd.to_numeric(df[col], errors='coerce')
    positifs = valeurs[valeurs > 0]
    moyen = float(positifs.mean()) if len(positifs) else 0.0
    lignes = []
    for pos in a.index:
        nette = float(valeurs.iloc[pos])
        lignes.append({
            'position':    int(pos),
            'charge_nette': round(nette, 2),
            'ratio_cout_moyen_positif': (round(-nette / moyen, 3)
                                         if moyen > 0 else None),
        })
    return lignes


#: ⚠️⚠️ CE QUE LA QUESTION A BESOIN DE SAVOIR, CALCULÉ À LA DÉTECTION. Même
#: leçon que `EffetAgrege` (`qualite/C3`) : le message qui DÉCIDE est celui du
#: rapport BLOQUÉ, et un rapport bloqué ne reçoit pas le dataframe. Porter ces
#: deux agrégats sur l'anomalie rend la question calculable sans lui.
@dataclass(frozen=True)
class ResumeChargesNegatives:
    """Le total et la borne, pour que la question se pose sans le dataframe."""
    total: float
    ratio_max: float | None


def _resume_charges_negatives(valeurs, mask) -> ResumeChargesNegatives:
    """Le total et la borne des charges négatives, à la DÉTECTION."""
    neg = valeurs[mask]
    pos = valeurs[valeurs > 0]
    moyen = float(pos.mean()) if len(pos) else 0.0
    return ResumeChargesNegatives(
        total=float(neg.sum()),
        ratio_max=(round(float((-neg).max()) / moyen, 2)
                   if moyen > 0 and len(neg) else None))


def question_charges_negatives(rapport, df=None) -> str | None:
    """La question posée à l'actuaire — NEUTRE, jamais orientée.

    ⚠️⚠️ LA FORMULATION EST LE POINT DE CONCEPTION LE PLUS IMPORTANT DE CE LOT.
    La version d'abord envisagée disait : « ces cas SEMBLENT ÊTRE DES RECOURS
    LÉGITIMES — confirmez-vous ? ». **La mesure interdit cette phrase** : les
    deux discriminants se chevauchent entièrement et les deux groupes se
    disqualifient. Faire dire au système une conclusion que la donnée ne porte
    pas serait le motif exact de cet audit.

    ⚠️ Le texte dit donc ce qu'il SAIT et ce qu'il NE SAIT PAS, et il ne cite
    aucun chiffre qu'il ne sache produire à cette couche.
    """
    cas = [a for a in (rapport.signalements or [])
           if a.code == 'cout_net_negatif']
    if not cas:
        return None
    a = cas[0]
    # ⚠️ LU SUR L'ANOMALIE, PAS RECALCULÉ SUR LE DATAFRAME : un rapport BLOQUÉ
    # n'en a pas, et c'est lui qui pose la question.
    r = a.resume_charges_negatives
    total = r.total if r else 0.0
    borne = (f"Aucun ne depasse {r.ratio_max:.2f} fois le cout moyen positif du "
             f"portefeuille." if (r and r.ratio_max) else "")
    # ⚠️ LES NOMBRES SE FORMATENT UN PAR UN. Ma premiere version appliquait un
    # `.replace(',', ' ')` sur TOUT le message pour l'espace des milliers : il
    # mangeait les virgules de la PROSE — « (subrogation  sauvetage) »,
    # « CONSERVER tout  EXCLURE tout ». *Un formatage global abime le texte
    # qu'il traverse ; c'est une surface que l'actuaire lit.*
    _n = f"{a.nb_lignes:,}".replace(',', ' ')
    _t = f"{total:,.0f}".replace(',', ' ')
    return (
        f"{_n} contrat(s) ({a.proportion:.2%}) portent une charge "
        f"nette NEGATIVE, pour un total de {_t}. {borne} "
        f"Une charge nette negative peut etre un RECOURS legitime "
        f"(subrogation, sauvetage) ou une ERREUR DE SAISIE : les deux "
        f"existent. CE CONTROLE NE PEUT PAS TRANCHER — il voit le "
        f"portefeuille agrege, jamais le detail des sinistres ; distinguer "
        f"les deux demande les paiements et les recuperations ligne a ligne. "
        # ⚠️⚠️ « positions » A DISPARU DE CETTE PHRASE LE 02/09/2026, ET LE
        # GARDE-FOU N'A PAS ÉTÉ TOUCHÉ. La question ne circulait qu'avec le
        # blocage ; depuis la liste disqualifiante elle est publiée dans la
        # SYNTHÈSE, que la sentinelle RGPD garde en interdisant le mot
        # « position ». Elle a tiré, à raison de son assiette — ce texte MENTIONNE
        # le mot sans publier aucune position. *Affaiblir un garde-fou RGPD
        # pour faire passer son propre correctif est le geste qu'on ne fait
        # jamais : c'est la phrase qui cède, pas le contrôle.*
        f"Trois reponses possibles : CONSERVER tout, EXCLURE tout, ou "
        f"fournir la LISTE des cas que vous conservez. "
        f"Empreinte des cas : {empreinte_positions(a.index)}."
    )


def preambule_qualite(portefeuille, plan, qualite_validee_par=None,
                      horodatage=None):
    """Le préambule COMMUN aux deux chemins de tarification — étape 1-A.

    ⚠️⚠️ POURQUOI UNE PORTE UNIQUE. `controler_qualite` n'avait **qu'un appelant
    de production** — le chemin déclaratif (constat `qualite/C4`). Le chemin
    agent n'avait **aucune couche qualité**, et c'est ainsi que les deux ont pu
    diverger toute une journée sur la même grandeur : l'exposition. *Une porte
    unique rend la divergence IMPOSSIBLE au lieu de la rendre seulement
    évitable.* (Au passé depuis le 02/09/2026 : voir le paragraphe suivant.)

    ⚠️ CETTE ÉTAPE NE CHANGE AUCUN COMPORTEMENT, et c'est sa condition d'entrée.
    Elle extrait les trois gestes que `pipeline_complet` faisait déjà, dans le
    même ordre, avec les mêmes arguments — contrôler, lever si bloqué, rendre le
    dataframe propre. **Aucun euro ne bouge.**

    ⚠️⚠️ ELLE EST BRANCHÉE AUX DEUX CHEMINS DEPUIS LE 02/09/2026 — étape 1-B,
    arbitrée par Selasse, constat `qualite/C4` FERMÉ. `pipeline_agents`
    l'appelle entre A1 et A2 : après A1 qui rend la donnée lisible sans retirer
    de ligne, avant A2 qui mute. *Un garde-fou placé après le geste qu'il
    surveille ne surveille plus rien.*

    Ce que le branchement a déplacé, mesuré AVANT d'être fait :

        DONNEE REELLE, 12 654 contrats : 12 654 / 12 654 retenues, DELTA 0
        fichier temoin (30 freq<0 + 30 expo<=0) : BLOQUE, union 6,0 %

    **Aucun euro sur le seul portefeuille réel du dépôt.** Ce qui apparaît est
    un blocage à signature nominative sur des fichiers portant des lignes
    IMPOSSIBLES — et `CODES_DISQUALIFIANTS`, arbitré à l'étape ⑤-①, dit
    lesquelles.

    Retourne le `RapportQualite`. L'appelant y lit `dataframe_propre`.
    """
    rapport = controler_qualite(
        portefeuille, plan, qualite_validee_par=qualite_validee_par,
        horodatage=horodatage)
    if rapport.bloque:
        raise QualiteBloquante(rapport)      # arrêt loud, jamais silencieux
    return rapport


def _phrase_effet_agrege(a: Anomalie) -> str | None:
    """Ce qu'une correction fait au TOTAL de sa colonne, en toutes lettres.

    ⚠️⚠️ CONSTAT `qualite/C3` — EXIGENCE DE SELASSE, 30/08/2026. Un compte de
    lignes ne dit pas l'enjeu : « 1000 ligne(s) CORRIGEE(S) » cachait une
    exposition totale divisée par dix. *L'actuaire doit lire CE QU'IL VALIDE.*

    ⚠️ LA SECONDE PHRASE NE S'AJOUTE QUE POUR L'EXPOSITION, ET C'EST DÉLIBÉRÉ.
    Le mécanisme est générique — toute correction de règle 2 publie son effet
    sur le total. Mais « ce total est un DÉNOMINATEUR » est une propriété du
    rôle `exposition`, pas de la règle : l'affirmer pour une colonne dont on ne
    sait rien serait exactement le défaut que cet audit poursuit.

    ⚠️ RGPD : un total et un pourcentage. Aucune valeur de ligne, aucun index,
    aucun identifiant — vérifié par sentinelle.
    """
    e = a.effet_agrege
    if e is None:
        return None
    pct = e.variation_pct
    phrase = (f"EFFET SUR LE TOTAL de « {e.colonne} » : "
              f"{e.total_avant:,.0f} -> {e.total_apres:,.0f}"
              .replace(',', ' '))
    if pct is not None:
        phrase += f" ({pct:+.1f} %)"
    phrase += "."
    if a.role == 'exposition':
        facteur = e.facteur_sur_un_ratio
        if facteur is not None and abs(facteur - 1.0) > 0.005:
            phrase += (f" L'exposition est le DENOMINATEUR de la frequence et "
                       f"de la prime pure : une prime calculee sur ce total "
                       f"serait multipliee par {facteur:.2f}.")
    return phrase


#: ⚠️⚠️ LE MARQUEUR EST UNE SOURCE UNIQUE, PAS UN LITTÉRAL RECOPIÉ. Les deux
#: Excel dérivent leur badge du TEXTE de la synthèse (`"EXCLUE" in ...`) ; y
#: recopier `'NON EXECUTE'` rouvrirait très exactement la divergence que le lot
#: « 30 définitions locales -> 0 » a fermée. Les consommateurs l'IMPORTENT.
MARQUEUR_QUALITE_NON_EXECUTEE = 'NON EXECUTE'

#: ⚠️⚠️ IL Y A EU UN TROISIÈME MARQUEUR ICI, ET IL A ÉTÉ RETIRÉ LE 02/09/2026.
#: `MARQUEUR_QUALITE_OBSERVEE = 'OBSERVEE, NON APPLIQUEE'` nommait l'état d'une
#: couche qui regarde sans appliquer — l'étape ④ de 1-B, une étape de MESURE
#: destinée à donner les fréquences réelles sur lesquelles arbitrer.
#: L'arbitrage est pris (`CODES_DISQUALIFIANTS` ci-dessous), l'étape ⑤ a branché
#: la couche, et le troisième état est devenu IMPOSSIBLE.
#: *Garder un instrument après qu'il a rendu son verdict n'est pas de la
#: prudence, c'est de la dette.* Le retrait est tenu complet par `QNE-9`.
#:
#: ⚠️ ET CE BLOC EST UN COMMENTAIRE, PAS UNE CONSTANTE. J'y avais d'abord écrit
#: `MARQUEUR_QUALITE_NON_EXECUTEE_ETATS = 2`, que rien n'aurait lu : *commettre
#: le défaut qu'on ferme, dans le commit qui le ferme.*

#: ⚠️⚠️ LA LISTE DISQUALIFIANTE — arbitrée par Selasse le 02/09/2026 sur les
#: chiffres de l'étape 4. **Seuls ces quatre types peuvent faire escalader un
#: run** ; les onze autres signalent et n'arrêtent jamais rien.
#:
#: Le critère retenu : une alerte bloque si et seulement si elle établit un
#: fait IMPOSSIBLE (pas ambigu) **et** que le laisser passer fausse le tarif de
#: façon non détectable en aval. *Bloquer sur l'ambiguïté transfère à la
#: machine une décision actuarielle.*
#:
#: ⚠️ MESURÉ AVANT L'ARBITRAGE, sur la seule donnée réelle du dépôt
#: (12 654 contrats) : ces quatre types y tirent à **0 %**. La liste ne bloque
#: aucun portefeuille réel connu. *Un garde-fou se juge sur ce qu'il laisse
#: passer, pas sur ce qu'il arrête.*
#:
#: ⚠️⚠️ ET `cout_net_negatif` EN EST DÉLIBÉRÉMENT ABSENT : il tire à **8,82 %**
#: sur cette même donnée, au-dessus du seuil, pour un phénomène parfaitement
#: légitime (recours, sauvetage, subrogation). L'y mettre bloquerait un vrai
#: portefeuille sur une charge nette normale.
CODES_DISQUALIFIANTS: frozenset[str] = frozenset({
    'frequence_negative',
    'exposition_non_positive',
    'doublon_identifiant',
    'unite_exposition_contredite',
})


def compte_union_lignes(anomalies) -> tuple[int, float | None]:
    """Le nombre de lignes DISTINCTES touchées, et sa part du portefeuille.

    ⚠️⚠️ CONSTAT `qualite/C18`. Les trois en-têtes du rapport signé faisaient
    `sum(a.nb_lignes for a in ...)` — **une addition de comptes qui se
    recoupent**. Mesuré le 02/09/2026, cinq facteurs troués à 5 % sur 4 000
    contrats :

    ```
      somme publiee            : 1 000 ligne(s) EXCLUE(S)
      union reelle             :   904
      lignes vraiment retirees :   904
    ```

    > *Le rapport signé annonçait quatre-vingt-seize exclusions qui n'avaient
    > pas eu lieu — et il ne disait nulle part que 22,6 % du portefeuille
    > venait de disparaître.*

    C'est la règle déjà écrite dans [[releve-symbole-vs-prose]] et appliquée
    par `controler_qualite` pour DÉCIDER de l'escalade : *ne jamais additionner
    des sources qui se recoupent — calculer l'UNION.* Elle l'était pour la
    décision, elle ne l'était pas pour la publication. **L'asymétrie était
    entre décider et dire.**

    ⚠️ LA PART N'EST RENDUE QUE SI ELLE SE DÉRIVE. Chaque anomalie porte
    `proportion = nb_lignes / n0` ; on retrouve `n0` par division, et on ne
    publie la part que si toutes les anomalies s'accordent sur ce `n0`.
    *Un pourcentage qu'on ne peut pas dériver ne se publie pas.*

    ⚠️ `RapportQualite.lignes_initiales` NE CONVIENT PAS ICI, et c'est mesuré :
    sur le chemin agent la couche reçoit le dataframe APRÈS les exclusions
    d'A2, si bien que `lignes_initiales - lignes_retenues` vaut **0** là où
    904 lignes ont disparu.
    """
    lot = list(anomalies or [])
    union: set[int] = set()
    sans_index = False
    for a in lot:
        if a.nb_lignes and not a.index:
            sans_index = True
        union.update(a.index or ())
    if sans_index or not lot:
        # ⚠️ Repli EXPLICITE : sans index, l'union n'est pas calculable et la
        # somme redevient la seule mesure disponible. *Publier la méthode à
        # côté du chiffre plutôt qu'un chiffre dont on ignore le sens.*
        return sum(a.nb_lignes for a in lot), None
    n0 = {round(a.nb_lignes / a.proportion) for a in lot
          if a.proportion and a.nb_lignes}
    part = (len(union) / n0.pop()) if len(n0) == 1 else None
    return len(union), part


def phrase_ampleur_exclusion(part: float | None) -> str | None:
    """La MESURE DE L'AMPLEUR, comparée au seul repère que le module possède.

    ⚠️⚠️ CONSTAT `qualite/C19`. `qualite/C18` a fait publier la part du
    portefeuille exclue — mais **la pastille reste AMBRE à 0,1 % comme à
    67 %** : elle se déclenche sur le mot « EXCLUE », jamais sur l'ampleur.
    *L'information était là, la hiérarchie n'y était pas.*

    ⛔⛔ ET LA GRADATION PAR LA COULEUR A ÉTÉ ÉCARTÉE, APRÈS MESURE. Le badge
    ROUGE publie littéralement **« Non conforme »** (`_MOT_RAG`, `services/C9`)
    — or un tarif calculé sur un portefeuille réduit n'est pas *non conforme*,
    il est *réduit*. *Le rendre rouge affirmerait plus que ce qu'on sait :
    exactement le défaut que cet audit poursuit.* La hiérarchie va donc dans
    le TEXTE, où la nuance existe.

    ⚠️⚠️ LE REPÈRE N'EST PAS INVENTÉ, IL EST RÉUTILISÉ, ET C'EST DIT.
    `SEUIL_ESCALADE` est la définition que ce module s'est déjà donnée d'une
    proportion qui *« exige une confirmation actuarielle nominative »*.
    Aucun seuil neuf n'est créé : *un chiffre inventé pour trancher une
    question actuarielle est précisément ce que ce module a supprimé quatre
    fois.*

    ⚠️ ET ELLE NE JUGE PAS. Elle compare, elle dit que l'exigence n'a PAS été
    déclenchée ici, et elle rend la question à l'actuaire. *Le système publie
    ce chiffre ; il ne le juge pas.* La décision — à partir de quelle perte un
    portefeuille cesse d'être tarifable — appartient à l'actuaire signataire,
    et resterait à déclarer au plan le jour où elle sera prise.

    Rend `None` sous le repère : *un avertissement permanent cesse d'être lu.*
    """
    if part is None or part < SEUIL_ESCALADE:
        return None
    _p = f"{part:.1%}".replace('.', ',').replace('%', ' %')
    _s = f"{SEUIL_ESCALADE:.0%}".replace('%', ' %')
    _reste = f"{1 - part:.1%}".replace('.', ',').replace('%', ' %')
    _fois = f"{part / SEUIL_ESCALADE:.1f}".replace('.', ',')
    return (
        f"⚠ AMPLEUR — cette part ({_p}) vaut {_fois} fois le seuil de {_s} "
        f"au-dela duquel ce module exige une confirmation actuarielle "
        f"nominative pour les anomalies disqualifiantes. Ces retraits-ci ne "
        f"declenchent PAS cette exigence : ils sont legitimes ligne a ligne. "
        f"Le tarif publie est donc calibre sur {_reste} du portefeuille "
        f"initial. VERIFIEZ que cette assiette reduite reste representative "
        f"de votre risque avant de signer."
    )


def _phrase_union(n: int, part: float | None, verbe: str, detail: str) -> str:
    """L'en-tête d'un lot d'anomalies — compte DISTINCT, et part quand elle
    se dérive. *Un compte sans son total ne dit pas l'enjeu.*"""
    # ⚠️ CONVENTION FRANÇAISE, comme `_entete_alerte` : ce texte est lu par un
    # actuaire, un commissaire aux comptes et l'ACPR. « 22.6% » n'est pas du
    # français, et deux conventions dans le même document en seraient une de
    # trop.
    _pct = (f" — {part:.1%} du portefeuille".replace('.', ',')
            .replace('%', ' %') if part is not None else '')
    return f"✔ {n} ligne(s) {verbe}{_pct} : {detail}."


def _entete_alerte(mask, total: int, titre: str, unite: str = 'contrat') -> str:
    """L'en-tête chiffré d'une alerte — LE COMPTE SE DÉRIVE DU MASQUE.

    ⚠️⚠️ Il ne se retape pas au site d'appel. Un nombre écrit à la main à côté
    d'un masque diverge le jour où le détecteur change, et le rapport SIGNÉ
    porterait alors un compte faux. *Le chiffre et la ligne qu'il décrit
    viennent de la même source, ou ils finiront par se contredire.*

    ⚠️ RGPD : un compte et un pourcentage. Aucune valeur, aucun index, aucun
    identifiant.
    """
    # ⚠️ CONVENTION FRANÇAISE, ET C'EST UNE DÉCISION : ce texte est lu par un
    # actuaire, un commissaire aux comptes et l'ACPR. « 3.0% sur 1000 » n'est
    # pas du français. Le séparateur d'espace reprend celui que
    # `_phrase_effet_agrege` utilise déjà pour les totaux.
    n = int(np.asarray(mask, dtype=bool).sum())
    _n = f"{n:,}".replace(',', ' ')
    _tot = f"{total:,}".replace(',', ' ')
    _pct = f"{n / max(total, 1):.1%}".replace('.', ',').replace('%', ' %')
    return f"{titre} — {_n} {unite}(s) sur {_tot} ({_pct})."


#: ⚠️⚠️ CE QUE LE LIVRABLE DIT QUAND LA COUCHE N'A PAS TOURNÉ — constat de
#: Selasse, 01/09/2026. Le patron est celui d'`avertissement_fuite_par_effet`
#: (`conformite/C1`) : un contrôle qui n'a pas eu lieu le DIT, il ne se tait pas.
PHRASE_QUALITE_NON_EXECUTEE = (
    f"⚠ CONTROLE QUALITE DES DONNEES — {MARQUEUR_QUALITE_NON_EXECUTEE}. Aucun "
    f"rapport de qualite n'accompagne ce tarif : les regles d'exclusion "
    f"(impossible), de correction (implausible) et de signalement (ambigu) "
    f"n'ont examine AUCUNE ligne. Ce n'est PAS « rien a signaler » — rien n'a "
    f"ete verifie, et le nombre de lignes fautives est INCONNU. Ce tarif n'a "
    f"pas ete produit par un chemin qui applique cette couche : les deux "
    f"chemins outilles le font (`pipeline_complet` et `pipeline_agents`), un "
    f"assemblage manuel des agents ne le fait pas."
)
#: ⚠️⚠️ CETTE PHRASE A ETE RELUE LE 02/09/2026, LE JOUR DU BRANCHEMENT.
#: Elle disait : « le chemin agent (A1-A6) n'appelle pas cette couche (constat
#: `qualite/C4`) [...] tant que le branchement n'est pas fait ». **1-B l'a
#: fait** : la phrase serait devenue fausse dans un document signe, et elle
#: aurait renvoye l'actuaire vers une cause qui n'existe plus.
#: *Le texte qui accompagne un comportement se relit quand il change — surtout
#: celui qui explique une ABSENCE, parce qu'il survit a la raison de l'absence.*
#: Elle nomme desormais le vrai cas restant : un assemblage manuel des agents,
#: hors des deux orchestrateurs (constat `agents/C1`).


def synthese_qualite_donnees(rapport: RapportQualite | None) -> str | None:
    """Texte à afficher dans TOUT livrable. Un traitement silencieux est un
    défaut en soi : l'actuaire doit voir ce qui a été exclu, corrigé, signalé,
    et qui a validé une poursuite.

    ⚠️⚠️ DEUX ÉTATS, DEUX VALEURS — ET C'EST TOUT L'OBJET DE CETTE FONCTION.
    Elle rendait `None` dans DEUX cas que rien ne distinguait :

        * `rapport is None`   -> la couche N'A PAS TOURNÉ ;
        * `rapport` sans anomalie -> elle a tourné et n'a RIEN trouvé.

    Mesuré le 01/09/2026 sur 10 000 contrats dont 600 à fréquence négative
    (6 %) : le chemin agent ne les exclut pas, et la section qualité du rapport
    SIGNÉ rendait la chaîne vide — **le même rendu qu'un portefeuille sain.**
    *« Pas vérifié » et « vérifié, rien à signaler » avaient la même valeur ;
    le silence par défaut affirmait donc quelque chose de faux.*

    Désormais : `PHRASE_QUALITE_NON_EXECUTEE` pour le premier cas, `None` — et
    donc rien d'affiché — pour le second seulement. *Un contrôle qui n'a pas eu
    lieu le dit ; un contrôle qui n'a rien trouvé se tait.* C'est le patron
    d'`avertissement_fuite_par_effet` (`conformite/C1`), déjà en service.

    ⚠️ AUCUN EURO. Aucune ligne n'est exclue, corrigée ni conservée
    différemment : la fonction ne fait que RENDRE UN TEXTE, et le badge Excel
    qu'elle alimente est une couleur de cellule, sans effet sur le statut RAG.
    """
    # ⚠️⚠️ DEUX ÉTATS, ET IL Y EN A EU TROIS PENDANT UNE JOURNÉE. L'étape ④ de
    # 1-B avait ajouté « OBSERVÉE, NON APPLIQUÉE » et un paramètre `observation`
    # à cette fonction. L'étape ⑤ a branché la couche : elle s'APPLIQUE, le
    # troisième état est devenu impossible, et tout son outillage a été retiré
    # le 02/09/2026. *Un mécanisme qui survit à sa raison d'être devient un
    # mensonge ; garder l'instrument après son verdict est une dette.*
    #
    # ⚠️⚠️ LA LEÇON DE CETTE ÉTAPE SURVIT À SON MÉCANISME, ET LA VOICI. Ma
    # première version rendait `PHRASE_QUALITE_NON_EXECUTEE` dès que
    # l'observation ne trouvait RIEN — c'est-à-dire sur un portefeuille sain :
    # *le défaut de `qualite/C9` reparaissait un cran plus haut, « observé, rien
    # trouvé » redisait « pas observé ».* C'est l'EXISTENCE d'un rapport qui
    # prouve que la couche a tourné, jamais son contenu — et c'est exactement
    # ce que teste le `rapport is None` ci-dessous, sur le seul état restant.
    if rapport is None:
        return PHRASE_QUALITE_NON_EXECUTEE
    if rapport.bloque:
        # ⚠️⚠️ LE MOTIF, PAS SEULEMENT LE CODE. Le message nommait le code de
        # l'anomalie et s'arretait la : l'actuaire lisait QUOI sans lire QUE
        # FAIRE. Les descriptions portent le remede (« declarer `echeance` au
        # plan rend la distinction opposable ») et n'etaient publiees nulle
        # part quand la couche bloquait. ⚠️ RGPD : elles ne citent ni valeur
        # ni index — verifie par sentinelle.
        _toutes = ((rapport.exclusions or []) + (rapport.corrections or [])
                   + (rapport.signalements or []))
        # ⚠️⚠️ POURQUOI ÇA BLOQUE ET CE QUE LA VALIDATION FERA SONT DEUX
        # CHOSES — séparées le 02/09/2026, et c'est une RÉGRESSION QUE J'AI
        # INTRODUITE LE JOUR MÊME. Le détail filtrait sur
        # `anomalies_au_dela_seuil`. Tant que TOUT type au-dessus du seuil y
        # figurait, le filtre publiait de fait tout ce qui allait s'appliquer.
        # La liste disqualifiante a réduit cet ensemble aux quatre types qui
        # BLOQUENT — et le message s'est mis à taire les autres.
        #
        # Mesuré par la gate : un message bloqué sur `unite_exposition_contredite`
        # ne publiait plus l'effet d'`exposition_sup_1`, qui divisait pourtant
        # le total d'exposition par dix (**-90,1 %**). *L'actuaire aurait signé
        # sans voir ce qu'il validait — le défaut exact que `qualite/C3` a
        # fermé, rouvert par un correctif qui regardait ailleurs.*
        #
        # L'en-tête nomme donc ce qui BLOQUE ; le détail publie TOUT ce que la
        # validation appliquera. *Un avertissement qui ne dit pas ce qu'on
        # valide n'avertit de rien.*
        _motifs = [a.description for a in _toutes]
        _detail = ''.join(f"\n   · {m}" for m in _motifs)
        # ⚠️⚠️ C'EST ICI QUE SE PREND LA DÉCISION, ET C'EST ICI QUE L'ENJEU
        # MANQUAIT LE PLUS — constat `qualite/C3`. Mesuré : le message bloqué
        # en disait MOINS que celui d'après validation. Il ne portait ni compte
        # de lignes ni effet ; l'actuaire signait sur « implausible pour un
        # contrat annuel » et obtenait une prime multipliée par dix.
        # *Un avertissement qui ne dit pas ce qu'on valide n'avertit de rien.*
        _effets = [p for p in (_phrase_effet_agrege(a) for a in _toutes) if p]
        _detail += ''.join(f"\n   ⚠ SI VOUS VALIDEZ — {p}" for p in _effets)
        _q = question_charges_negatives(rapport)
        if _q:
            _detail += f"\n   ? {_q}"
        return (f"⚠ CONTROLE QUALITE BLOQUE — anomalie(s) "
                f"[{', '.join(rapport.anomalies_au_dela_seuil)}] touchant >= "
                f"{rapport.seuil:.0%} des lignes. Confirmation actuarielle nominative "
                f"requise (qualite_validee_par) pour poursuivre." + _detail)
    lignes: List[str] = []
    if rapport.exclusions:
        # ⚠️⚠️ L'UNION, JAMAIS LA SOMME — constat `qualite/C18`. Une ligne
        # trouee sur DEUX facteurs etait comptee DEUX FOIS : 1 000 annoncees
        # pour 904 reellement retirees. *Le rapport signe annoncait des
        # exclusions qui n'avaient pas eu lieu.*
        tot, part = compte_union_lignes(rapport.exclusions)
        det = " ; ".join(f"{a.nb_lignes}x {a.code}" for a in rapport.exclusions)
        lignes.append(_phrase_union(tot, part, 'EXCLUE(S) (impossible)', det))
        # ⚠️⚠️ `qualite/C19` — LA HIERARCHIE, PAS SEULEMENT LE CHIFFRE. La
        # pastille reste AMBRE a 0,1 % comme a 67 % : elle se declenche sur le
        # mot << EXCLUE >>, jamais sur l'ampleur. *L'information etait la, la
        # hierarchie n'y etait pas.*
        _ampleur = phrase_ampleur_exclusion(part)
        if _ampleur:
            lignes.append(f"   {_ampleur}")
        # ⚠️⚠️ LA TROISIÈME BRANCHE, TROUVÉE DANS MON PROPRE CORRECTIF.
        # L'étape 4 du chantier `unite_exposition` a fait publier leur
        # description aux CORRECTIONS puis aux SIGNALEMENTS — et a laissé les
        # EXCLUSIONS muettes. *Une exclusion est pourtant le geste le plus
        # fort des trois : elle RETIRE des contrats du calcul.* Le rapport
        # signé nommait le code sans dire pourquoi la ligne était impossible.
        for a in rapport.exclusions:
            lignes.append(f"   ⚠ {a.description}")
    if rapport.corrections:
        tot, part = compte_union_lignes(rapport.corrections)
        det = " ; ".join(f"{a.nb_lignes}x {a.code} ({a.correction})" for a in rapport.corrections)
        lignes.append(_phrase_union(tot, part, 'CORRIGEE(S)', det))
        # ⚠️ LA MÊME PHRASE QU'EN AMONT, PAS UNE REFORMULATION. Le rapport signé
        # doit porter ce que l'actuaire a validé, mot pour mot — sinon les deux
        # surfaces divergent et la trace ne prouve plus rien.
        # ⚠️⚠️ ET UNE CORRECTION SANS EFFET CHIFFRÉ PUBLIE SON MOTIF. Mesuré en
        # branchant A2 : une exposition INVENTÉE (la colonne n'existait pas)
        # n'a aucun « total avant », donc aucune phrase d'effet — et la
        # synthèse ne rendait plus que « 600x exposition_inventee ». *C'est
        # précisément le cas où il n'y a aucun nombre pour porter le sens : le
        # motif doit parler à sa place.* La branche BLOQUÉE publiait déjà les
        # descriptions ; celle-ci ne le faisait pas — l'asymétrie entre les
        # deux moitiés de la même fonction.
        # ⚠️⚠️ ÉTAPE 4 DU CHANTIER `unite_exposition` — LES DEUX, PLUS « L'UN OU
        # L'AUTRE ». Ce `if/else` publiait l'effet OU la description, jamais
        # les deux. La branche BLOQUÉE, elle, publie les deux depuis toujours.
        # *Le commentaire ci-dessus disait déjà « LA MÊME PHRASE QU'EN AMONT,
        # PAS UNE REFORMULATION » : le code publiait strictement MOINS que ce
        # qu'il promettait.*
        #
        # ⚠️ CE QUE LA MESURE A MONTRÉ, ET POURQUOI ÇA COMPTE. La description
        # est la SEULE surface qui nomme l'unité de l'exposition — « implausible
        # pour une exposition exprimee en mois », ou la phrase d'hypothèse
        # annuelle quand rien n'est déclaré. Mesuré le 31/08 : `UNITE NON
        # DECLAREE` présent dans le message bloqué, **absent du rapport
        # SIGNÉ**. *Le document que lisent le CAC et l'ACPR ne disait pas sous
        # quelle unité la correction avait été faite.*
        for a in rapport.corrections:
            lignes.append(f"   ⚠ {a.description}")
            _p = _phrase_effet_agrege(a)
            if _p:
                lignes.append(f"   ⚠ {_p}")
    if rapport.signalements:
        tot, part = compte_union_lignes(rapport.signalements)
        det = " ; ".join(f"{a.nb_lignes}x {a.code}" for a in rapport.signalements)
        lignes.append(_phrase_union(
            tot, part, 'SIGNALEE(S) (ambigu, laissees telles quelles)', det)
            .replace('✔', '⚠', 1))
        # ⚠️⚠️ LA MÊME ASYMÉTRIE, UN CRAN PLUS BAS — trouvée en mesurant
        # l'étape 4. Les signalements ne publiaient que leur CODE : le rapport
        # signé disait « 400x unite_exposition_contredite » sans dire ce que
        # ça voulait dire. *Un code nu nomme une anomalie ; il ne la dit pas.*
        # La branche BLOQUÉE publie les descriptions de TOUTES les règles ; il
        # n'y a aucune raison que la règle 3 soit muette une fois validée.
        # ⚠️ Coût mesuré avant de le faire : 59 à 332 caractères par
        # signalement, sur les trois qui existent.
        for a in rapport.signalements:
            lignes.append(f"   ⚠ {a.description}")
    if rapport.escalade_declenchee and rapport.validee_par:
        d = _date_lisible(rapport.horodatage)
        lignes.append(
            f"✔ Poursuite malgre anomalie(s) >= {rapport.seuil:.0%} VALIDEE par "
            f"« {rapport.validee_par} »" + (f" le {d}" if d else "") + ".")
    # ⚠️⚠️ LA QUESTION SUIT L'ANOMALIE, PLUS LE BLOCAGE — 02/09/2026.
    # `qualite/C8` l'avait posée dans `QualiteBloquante`, avec ce motif : *« le
    # blocage est le moment où l'actuaire décide : la question doit y être. »*
    # Vrai tant que `cout_net_negatif` pouvait bloquer. La liste disqualifiante
    # le lui a retiré — et **la question ne pouvait plus atteindre personne**.
    # *Un correctif qui retire un blocage emporte tout ce que ce blocage
    # portait.* Elle est donc publiée partout où la charge négative l'est.
    _q = question_charges_negatives(rapport)
    if _q:
        lignes.append(f"? {_q}")
    return "\n".join(lignes) if lignes else None
