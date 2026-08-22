# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — RÉFÉRENTIEL DE COURBE DES TAUX SANS RISQUE (EIOPA)
=============================================================================

UN SEUL ENDROIT POUR LE TAUX QUI ACTUALISE UN ENGAGEMENT AU BILAN.

⚠️ POURQUOI CE MODULE EXISTE. Le relevé exhaustif a trouvé HUIT sources de
taux dans le dépôt, dont six en Non-Vie, divergeant de 45 points de base sur
le 10 ans — et pas dans le même sens : A7 était 41 bps SOUS la courbe en
vigueur, tout le bloc réglementaire 4 bps AU-DESSUS. Ce n'est donc pas un
décalage commun qui s'annulerait dans un rapport consolidé : c'est une
incohérence interne qu'un contrôleur trouve en recoupant deux agents.

⚠️ CE MODULE N'EST PAS UN FOURRE-TOUT, ET C'EST SA RAISON D'ÊTRE. Un
référentiel « unique » où chacun pioche reproduirait le problème qu'il
prétend résoudre. Trois natures de taux circulent, et une seule entre ici :

  (A) LE TAUX RÉGLEMENTAIRE D'ACTUALISATION — il y en a UN.
      La courbe EIOPA SANS Volatility Adjustment. C'est le seul taux qui
      actualise un engagement inscrit au bilan — **art. 77, paragraphe 2, de
      la DIRECTIVE 2009/138/CE**. C'est ce que ce module expose par défaut.

      ⚠️⚠️ CE TEXTE RATTACHAIT CE NUMÉRO AU RÈGLEMENT DÉLÉGUÉ, ET C'ÉTAIT
      FAUX. Établi au consolidé 02015R0035 (FR, 02.08.2022) : l'article 77
      DU RÈGLEMENT s'intitule « Fonds propres de base de niveau 3 —
      Caractéristiques déterminant le classement » (p. 72). Le règlement
      nomme lui-même le bon article, dans sa définition de la « courbe des
      taux sans risque de base » (art. 1er, point 36) : « … la courbe des
      taux sans risque pertinents à utiliser pour calculer la meilleure
      estimation visée à l'article 77, paragraphe 2, de la directive
      2009/138/CE … ». Les modalités de CONSTRUCTION, elles, sont bien dans
      le règlement délégué : section 4, articles 43 à 48.

      ⚠️ CE MODULE SERT TOUT LE DÉPÔT — une citation fausse y voyage partout,
      et c'est exactement ce que le défaut « Art. 105 » a coûté à vingt
      endroits. Un contrôle de test l'interdit désormais.

  (B) LES VARIANTES OFFICIELLES DE CETTE MÊME COURBE, sous accès DISTINCTS.
      · avec VA — suppose l'agrément de l'autorité de contrôle
        (art. 77 quinquies **de la même DIRECTIVE** : mesuré, le règlement
        délégué ne possède aucun article 77 bis/ter/quater/quinquies, il ne
        fait que citer ceux de la directive) ; d'où un argument sans valeur
        par défaut ;
      · courbes choquées (`Spot_*_shock_UP/DOWN`) — servent le SCR de taux,
        pas l'actualisation. NON implémentées ici : A8 calcule son choc par
        les facteurs relatifs des art. 166 et 167, ce qui EST la formule
        standard. Les courbes choquées d'EIOPA sont une commodité, pas une
        correction. Signalé, pas traité.

  (C) CE QUI N'EST PAS UN TAUX D'ACTUALISATION RÉGLEMENTAIRE — EXCLU.
      Mesuré agent par agent avant de trancher :
        · OAT France 10 ans .... n'entre dans AUCUN calcul. Publié en
          descriptif par A8 ; son seul usage arithmétique est
          `va = max(0, oat - r10)` dans A10, qui fabrique un VA au lieu de
          le lire — c'est un défaut, pas un usage ;
        · taux directeur BCE ... aucun usage nulle part, ni calcul ni
          publication. Maintenu mensuellement par un robot, lu par personne ;
        · inflation ........... hypothèse de PROJECTION (ORSA d'A8), pas
          d'actualisation ;
        · taux IFRS 17 ........ `rfr + prime d'illiquidité`. Référentiel
          COMPTABLE, pas prudentiel. C'est un DÉRIVÉ : il se calcule chez
          A11 À PARTIR d'ici, il n'entre pas ici. Un dérivé qui remonte dans
          sa source est le début d'un cycle.

⚠️ UNE FONCTION PAR QUESTION, AUCUN ACCESSEUR GÉNÉRIQUE. Pas de
`get_taux(nature)` : un paramètre chaîne EST le fourre-tout. C'est ce
mécanisme qui avait fait choisir un écart type par sous-chaîne du nom de
branche au lot B10-c — `'rc' in 'rc_auto'` était vrai, et le choix était faux
sur treize noms sur dix-sept.

⚠️ CE MODULE LÈVE, IL NE SE RABAT PAS. Une bibliothèque qui substitue
silencieusement une autre donnée est pire qu'une qui refuse. Le repli sur la
courbe embarquée est une décision d'AGENT, prise par l'appelant, qui sait ce
qu'il publie.

⚠️ DOUBLON TEMPORAIRE ASSUMÉ. `a7_provisionnement/config/rfr_eiopa.py` porte
encore sa propre courbe et son propre garde-fou d'unité. Ce lot (R1) ne
bascule AUCUN consommateur : il pose le référentiel et rien d'autre, pour que
zéro euro bouge. Le doublon disparaît en R2, quand A7 bascule.

RÉFÉRENCES
  ⚠️ CE BLOC PORTAIT LA MÊME ERREUR QUE LE POINT (A), DANS L'ORDRE INVERSE —
  le texte d'abord, l'article ensuite. C'est ce qui l'a rendu invisible au
  premier contrôle, qui ne cherchait qu'une seule tournure. Corriger un site
  sur deux dans le MÊME fichier est le motif que ce dépôt paie sans cesse.

  Directive 2009/138/CE
    · art. 77, paragraphe 2 — meilleure estimation, actualisée par la courbe
      des taux sans risque pertinents. C'est le fondement du taux exposé ici.
    · art. 77 quinquies — Volatility Adjustment, soumis à agrément.
  Règlement délégué (UE) 2015/35
    · section 4, art. 43 à 48 — CONSTRUCTION de la courbe : instruments
      retenus (44), ajustement des swaps (45), extrapolation (46), taux à
      terme ultime (47), monnaies rattachées (48).
    · art. 1er, point 36 — définition de la « courbe des taux sans risque de
      base », qui renvoie elle-même à l'art. 77 §2 de la directive.
  EIOPA — Risk-Free Interest Rate Term Structures, publication mensuelle.
=============================================================================
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Dict, NamedTuple, Optional, Sequence, Tuple

import numpy as np


# =============================================================================
#  LA COURBE — LA PROVENANCE EST PORTÉE PAR LA DONNÉE
# =============================================================================

class CourbeRFR(NamedTuple):
    """Une courbe des taux sans risque, avec de quoi la justifier.

    La provenance vit dans la DONNÉE, pas dans un commentaire : c'est la leçon
    des lots B10-a et B10-b, où les valeurs fausses étaient toutes commentées
    « Annexe II » et où certaines citaient un segment inexistant.

    ⚠️ `date_arrete` À `None` N'EST PAS UN DÉTAIL. C'est ce qui distingue une
    courbe opposable d'une courbe supposée, et `diagnostic_peremption` en tire
    un statut plafonnant. Voir la note de `taux_plat`.

    ⚠️ `avec_va` EST LU, JAMAIS DÉCLARÉ. Le classeur EIOPA porte une ligne
    `VA` vide sur l'onglet sans VA et renseignée sur l'onglet avec. La courbe
    sait donc d'elle-même ce qu'elle est, et l'appelant ne peut pas se
    tromper en l'affirmant.
    """
    date_arrete:  Optional[str]            # 'AAAA-MM-JJ', ou None si inconnue
    devise:       str
    avec_va:      bool
    maturites:    Tuple[float, ...]        # en années, croissantes
    taux_decimal: Tuple[float, ...]        # 0.03159 pour 3,159 % — UNE unité
    provenance:   str                      # d'où elle sort, en une phrase
    concordance:  Optional[str]            # ce qui a été recoupé, ou None
    ufr:          Optional[float] = None   # en %, tel que publié
    cra_bps:      Optional[float] = None   # en points de base, tel que publié
    llp:          Optional[float] = None   # Last Liquid Point, en années
    convergence:  Optional[float] = None   # durée de convergence, en années
    alpha:        Optional[float] = None   # paramètre Smith-Wilson
    va_bps:       Optional[float] = None   # en points de base, si avec_va


class CourbeIllisible(ValueError):
    """Le fichier fourni n'a pas pu être lu SANS DEVINER.

    ⚠️ LA LIGNE DE PARTAGE N'EST PAS « convertir ou non », C'EST « deviner ou
    refuser ». Un lecteur qui devine continue de produire quelque chose quand
    EIOPA réorganise son classeur — sans produire la bonne chose.
    """


# =============================================================================
#  LA COURBE EMBARQUÉE — UN REPLI EXPLICITEMENT DATÉ
# =============================================================================

DATE_EMBARQUEE = "2026-07-31"
DEVISE_EMBARQUEE = "EUR"

#: Au-delà de ce délai la courbe embarquée est SIGNALÉE comme périmée. EIOPA
#: publie MENSUELLEMENT : un trimestre de retard reste usuel entre deux
#: arrêtés, un an ne l'est pas.
MOIS_ALERTE_PEREMPTION = 3
MOIS_ROUGE_PEREMPTION = 12

#: Jours par mois moyen — 365,25 / 12. Le nombre existait en dur au seul
#: endroit qui l'employait ; il est nommé parce qu'un second site le lit
#: désormais, et deux copies d'une même constante finissent par diverger.
JOURS_PAR_MOIS = 30.4375

#: EIOPA RFR EUR au 31/07/2026, onglet `RFR_spot_no_VA`, colonne Euro.
#: LES 150 MATURITÉS PUBLIÉES, PAS UN ÉCHANTILLON INTERPOLÉ. Une embarquée à
#: trente points-clés — le découpage qu'employait A7 — s'écarte au maximum de
#: 0,172 bps et dépasse 0,1 bps sur 33 maturités sur 150. C'est peu, et ce
#: n'est pas rien pour un nombre qui entre au bilan ; les 150 valeurs coûtent
#: quinze lignes et rendent l'erreur d'interpolation NULLE aux maturités
#: publiées.
_TAUX_EMBARQUES: Tuple[float, ...] = (
    0.02826, 0.02931, 0.02945, 0.02964, 0.02987, 0.03012, 0.03046, 0.03083, 0.03119, 0.03159,   # 1-10
    0.03195, 0.03226, 0.03259, 0.03286, 0.03307, 0.03322, 0.03333, 0.03342, 0.03349, 0.03354,   # 11-20
    0.03358, 0.03361, 0.03364, 0.03366, 0.03368, 0.03369, 0.03370, 0.03371, 0.03371, 0.03371,   # 21-30
    0.03372, 0.03371, 0.03371, 0.03371, 0.03370, 0.03370, 0.03369, 0.03369, 0.03368, 0.03367,   # 31-40
    0.03367, 0.03366, 0.03365, 0.03364, 0.03364, 0.03363, 0.03362, 0.03361, 0.03360, 0.03360,   # 41-50
    0.03359, 0.03358, 0.03357, 0.03357, 0.03356, 0.03355, 0.03354, 0.03354, 0.03353, 0.03352,   # 51-60
    0.03351, 0.03351, 0.03350, 0.03349, 0.03349, 0.03348, 0.03348, 0.03347, 0.03346, 0.03346,   # 61-70
    0.03345, 0.03345, 0.03344, 0.03344, 0.03343, 0.03342, 0.03342, 0.03341, 0.03341, 0.03341,   # 71-80
    0.03340, 0.03340, 0.03339, 0.03339, 0.03338, 0.03338, 0.03337, 0.03337, 0.03337, 0.03336,   # 81-90
    0.03336, 0.03335, 0.03335, 0.03335, 0.03334, 0.03334, 0.03334, 0.03333, 0.03333, 0.03333,   # 91-100
    0.03332, 0.03332, 0.03332, 0.03331, 0.03331, 0.03331, 0.03331, 0.03330, 0.03330, 0.03330,   # 101-110
    0.03330, 0.03329, 0.03329, 0.03329, 0.03329, 0.03328, 0.03328, 0.03328, 0.03328, 0.03327,   # 111-120
    0.03327, 0.03327, 0.03327, 0.03326, 0.03326, 0.03326, 0.03326, 0.03326, 0.03325, 0.03325,   # 121-130
    0.03325, 0.03325, 0.03325, 0.03324, 0.03324, 0.03324, 0.03324, 0.03324, 0.03324, 0.03323,   # 131-140
    0.03323, 0.03323, 0.03323, 0.03323, 0.03323, 0.03322, 0.03322, 0.03322, 0.03322, 0.03322,   # 141-150
)

_MATURITES_EMBARQUEES: Tuple[float, ...] = tuple(float(m) for m in range(1, 151))


def courbe_embarquee() -> CourbeRFR:
    """La courbe de repli — datée, et donc jugeable.

    ⚠️ ELLE PORTE SA DATE, ET C'EST TOUT L'INTÉRÊT. Une courbe embarquée sans
    date se périme en silence : c'est l'état dont ce chantier sort. Celle-ci
    est datée, donc `diagnostic_peremption` la déclasse toute seule quand elle
    vieillit, sans que personne ait à y penser.
    """
    return CourbeRFR(
        date_arrete=DATE_EMBARQUEE,
        devise=DEVISE_EMBARQUEE,
        avec_va=False,
        maturites=_MATURITES_EMBARQUEES,
        taux_decimal=_TAUX_EMBARQUES,
        provenance=("EIOPA RFR Term Structures du 31/07/2026, onglet "
                    "RFR_spot_no_VA, colonne Euro — 150 maturités publiées"),
        concordance=None,
        ufr=3.30, cra_bps=10.0, llp=20.0, convergence=40.0, alpha=0.066628,
    )


# =============================================================================
#  (A) LE TAUX RÉGLEMENTAIRE D'ACTUALISATION — UNE FONCTION, UNE QUESTION
# =============================================================================

#: Un code ISO 4217 : trois lettres. Le décodeur d'onglet EIOPA accepte un
#: préfixe de DEUX OU TROIS lettres, et les onglets réels en portent des deux
#: sortes — `EUR_...` mais aussi `FR_...` et `UK_...`. Le champ `devise` d'une
#: courbe mélange donc des devises et des PAYS.
_ISO_4217 = re.compile(r'^[A-Z]{3}$')


def _verifier_devise(courbe: CourbeRFR, devise_engagement) -> None:
    """Refuse d'actualiser un engagement dans une monnaie qui n'est pas
    celle de la courbe — ou dont on ne peut pas l'affirmer.

    ⚠️ ON NE COMPARE PAS CE QU'ON NE SAIT PAS LIRE. `UK` n'est pas une
    devise (GBP l'est), `FR` non plus (EUR l'est), et deux fabriques posent
    `'?'`. Traduire `FR` en `EUR` serait DEVINER — la ligne de partage que
    `CourbeIllisible` trace déjà pour la lecture du classeur : deviner ou
    refuser. On refuse, en disant ce qui manque.
    """
    if devise_engagement is None:
        return
    demandee = str(devise_engagement).strip().upper()
    portee = str(courbe.devise or '').strip().upper()
    if not _ISO_4217.match(demandee):
        raise ValueError(
            f"Devise d'engagement « {devise_engagement} » non reconnue : "
            f"un code ISO 4217 de trois lettres est attendu (EUR, USD, GBP).")
    if not _ISO_4217.match(portee):
        raise ValueError(
            f"Actualisation en {demandee} demandée sur une courbe dont la "
            f"devise n'est pas établie (« {courbe.devise} » — "
            f"{courbe.provenance}). Le nom d'onglet EIOPA porte parfois un "
            f"PAYS et non une monnaie : il n'est pas traduit ici, car "
            f"supposer que FR vaut EUR serait deviner. Charger la courbe de "
            f"la monnaie voulue, ou établir sa devise avant d'actualiser.")
    if demandee != portee:
        raise ValueError(
            f"Engagement en {demandee} actualisé sur une courbe {portee}. "
            f"B79 exige « la courbe des taux dans la monnaie appropriée » : "
            f"charger la courbe {demandee}, ou convertir les flux avant "
            f"actualisation — jamais l'inverse.")


def actualiser(courbe: CourbeRFR, maturite: float,
               devise_engagement: str | None = None) -> float:
    """Le taux qui actualise un engagement au bilan (art. 77). En DÉCIMAL.

    ⚠️ REFUSE UNE COURBE AVEC VA, ET C'EST LE POINT. Le Volatility Adjustment
    suppose l'agrément de l'autorité de contrôle (art. 77 quinquies).
    L'exigence devient ainsi un fait de code plutôt qu'un commentaire que
    personne ne relit. Qui a l'agrément appelle `actualiser_avec_va`, et
    l'agrément apparaît alors sur CHAQUE site d'appel — c'est-à-dire à
    l'endroit exact où un contrôleur le cherchera.

    ⚠️ ET REFUSE UNE DEVISE QUI NE CONCORDE PAS, sur le même dessin. Cette
    fonction ne lisait JAMAIS `courbe.devise` : un engagement en dollars
    aurait été actualisé sur la courbe euro EN SILENCE, contre B79 — « la
    courbe des taux dans la monnaie appropriée », exigence que le socle
    IFRS 17 de ce dépôt déclare déjà sous `courbe_dans_la_monnaie`.

    ⚠️ `None` NE DÉCLENCHE RIEN, et c'est délibéré : aucun appelant du dépôt
    ne déclare de devise aujourd'hui, le passif Non-Vie n'en porte pas. La
    garde est LATENTE, comme l'était le refus du VA quand il a été posé —
    elle n'a pas de client, elle rend l'omission impossible le jour où elle
    en aura un.
    """
    _verifier_devise(courbe, devise_engagement)
    if courbe.avec_va:
        raise ValueError(
            "Courbe AVEC Volatility Adjustment employée pour une "
            "actualisation de base. Le VA suppose l'agrément de l'autorité "
            "de contrôle (art. 77 quinquies) : appeler `actualiser_avec_va` "
            "en déclarant l'agrément, ou repartir de la courbe sans VA.")
    return _interpoler(courbe, maturite)


def actualiser_avec_va(courbe: CourbeRFR, maturite: float,
                       agrement_acpr: bool,
                       devise_engagement: str | None = None) -> float:
    """Idem, avec Volatility Adjustment — l'agrément n'a PAS de valeur par
    défaut, et il est redemandé à chaque appel.

    ⚠️ POURQUOI LE REDEMANDER PLUTÔT QUE LE PORTER SUR LA COURBE. Un agrément
    posé une fois à la construction se propage ensuite en silence. Ici il
    s'écrit sur chaque site d'appel : le lire dans le code, c'est le vérifier.
    """
    _verifier_devise(courbe, devise_engagement)
    if not agrement_acpr:
        raise ValueError(
            "Volatility Adjustment demandé sans agrément déclaré. L'art. 77 "
            "quinquies le subordonne à l'approbation de l'autorité de "
            "contrôle ; sans elle, employer la courbe sans VA.")
    if not courbe.avec_va:
        raise ValueError(
            "Actualisation avec VA demandée sur une courbe SANS VA. Charger "
            "l'onglet RFR_spot_with_VA du classeur EIOPA.")
    return _interpoler(courbe, maturite)


def facteur_actualisation(courbe: CourbeRFR, maturite: float) -> float:
    """Facteur d'escompte 1/(1+r_t)^t à la maturité t, courbe sans VA."""
    t = max(1.0, float(maturite))
    return 1.0 / (1.0 + actualiser(courbe, t)) ** t


def _interpoler(courbe: CourbeRFR, maturite: float) -> float:
    """Interpolation linéaire, bornée aux maturités publiées.

    Borner plutôt qu'extrapoler : au-delà du dernier point publié, EIOPA ne
    dit rien, et prolonger une droite y inventerait un taux.
    """
    mats = np.asarray(courbe.maturites, dtype=float)
    taux = np.asarray(courbe.taux_decimal, dtype=float)
    t = min(max(float(maturite), float(mats[0])), float(mats[-1]))
    return float(np.interp(t, mats, taux))


# =============================================================================
#  (B) LA VARIANTE OFFICIELLE — LE CLASSEUR EIOPA, LU SANS DEVINER
# =============================================================================

_ONGLET_SANS_VA = 'RFR_spot_no_VA'
_ONGLET_AVEC_VA = 'RFR_spot_with_VA'
_PAYS_EURO = 'Euro'

#: Le code que le classeur porte en tête de chaque colonne pays. Il DÉCRIT la
#: courbe : devise, arrêté, méthode, Last Liquid Point, convergence, UFR.
#: Exemples relevés dans le fichier du 31/07/2026 :
#:      EUR_31_07_2026_SWP_LLP_20_EXT_40_UFR_3.30
#:      FR_31_07_2026_SWP_LLP_20_EXT_40_UFR_3.30      (préfixe à 2 lettres)
#:      UK_31_07_2026_OIS_LLP_50_EXT_40_UFR_3.30      (méthode et LLP autres)
#: Le préfixe et la méthode varient : le motif ne les fige pas.
_MOTIF_CODE = re.compile(
    r'^(?P<devise>[A-Z]{2,3})'
    r'_(?P<jour>\d{2})_(?P<mois>\d{2})_(?P<annee>\d{4})'
    r'_(?P<methode>[A-Z]+)'
    r'_LLP_(?P<llp>\d+)'
    r'_EXT_(?P<ext>\d+)'
    r'_UFR_(?P<ufr>[\d.]+)$')

#: Les paramètres sont trouvés par LEUR LIBELLÉ en colonne 1, jamais par leur
#: rang. Une ligne insérée par EIOPA décalerait tout lecteur qui compte les
#: lignes ; elle est sans effet sur un lecteur qui lit les étiquettes.
_LIBELLES_PARAMETRES = ('Coupon_freq', 'LLP', 'Convergence', 'UFR',
                        'alpha', 'CRA', 'VA')


def lire_classeur_eiopa(fichier_bytes: bytes) -> CourbeRFR:
    """Le classeur EIOPA officiel, onglet SANS VA — la porte principale.

    ⚠️ C'EST LA SEULE PORTE QUI APPORTE LA DATE D'ARRÊTÉ, et donc la seule
    dont sort une courbe capable de porter un chiffre définitif. Les deux
    autres restent en état de marche mais plafonnent comme une courbe
    périmée : voir `diagnostic_peremption`.

    ⚠️ ET LE FICHIER EST REDONDANT AVEC LUI-MÊME — c'est ce qui permet de ne
    jamais deviner. Le code de la ligne 2 dit `LLP_20_EXT_40_UFR_3.30`, et
    les lignes de paramètres disent `LLP = 20`, `Convergence = 40`,
    `UFR = 3.3`. Les deux lectures sont exigées CONCORDANTES. Si EIOPA
    réorganise son classeur, elles divergent et ce lecteur refuse au lieu de
    rendre une courbe qu'il n'a pas comprise.
    """
    return _lire_onglet(fichier_bytes, _ONGLET_SANS_VA, attendu_avec_va=False)


def lire_classeur_eiopa_avec_va(fichier_bytes: bytes,
                                agrement_acpr: bool) -> CourbeRFR:
    """Le même classeur, onglet AVEC VA — l'agrément n'a pas de défaut."""
    if not agrement_acpr:
        raise ValueError(
            "Courbe avec Volatility Adjustment demandée sans agrément "
            "déclaré (art. 77 quinquies). Employer `lire_classeur_eiopa` "
            "pour la courbe de base.")
    return _lire_onglet(fichier_bytes, _ONGLET_AVEC_VA, attendu_avec_va=True)


def _lire_onglet(fichier_bytes: bytes, onglet: str,
                 attendu_avec_va: bool) -> CourbeRFR:
    try:
        import pandas as pd
    except ImportError as e:                                # pragma: no cover
        raise CourbeIllisible(f"pandas indisponible : {e}") from e

    try:
        brut = pd.read_excel(io.BytesIO(fichier_bytes), sheet_name=onglet,
                             header=None)
    except Exception as e:
        raise CourbeIllisible(
            f"Onglet « {onglet} » illisible dans ce classeur : {e}. Fournir "
            f"le fichier EIOPA « Term Structures » tel qu'il est publié, sans "
            f"le retravailler.") from e

    colonne, rang_pays = _colonne_pays(brut, _PAYS_EURO, onglet)
    lignes = _lignes_par_libelle(brut, _LIBELLES_PARAMETRES)
    code, decode = _code_courbe(brut, colonne, rang_pays, onglet)
    parametres = {lib: brut.iloc[rang, colonne]
                  for lib, rang in lignes.items()}

    concordance = _exiger_concordance(decode, parametres, code)
    va_bps = _lire_va(parametres.get('VA'), attendu_avec_va, onglet)
    maturites, taux = _lire_taux(brut, colonne, max(lignes.values()), onglet)

    return CourbeRFR(
        date_arrete=decode['date'],
        devise=decode['devise'],
        avec_va=attendu_avec_va,
        maturites=maturites,
        taux_decimal=taux,
        provenance=(f"EIOPA RFR Term Structures du "
                    f"{decode['date'][8:]}/{decode['date'][5:7]}/"
                    f"{decode['date'][:4]}, onglet {onglet}, colonne "
                    f"{_PAYS_EURO} — {len(maturites)} maturités, "
                    f"code {code}"),
        concordance=concordance,
        ufr=_flottant(parametres.get('UFR')),
        cra_bps=_flottant(parametres.get('CRA')),
        llp=_flottant(parametres.get('LLP')),
        convergence=_flottant(parametres.get('Convergence')),
        alpha=_flottant(parametres.get('alpha')),
        va_bps=va_bps,
    )


#: Profondeur de balayage de l'en-tête. Le classeur EIOPA place le pays en
#: troisième ligne ; on cherche large pour qu'une ligne insérée n'arrête pas
#: la lecture, et on s'arrête bien avant les taux.
_LIGNES_ENTETE = 8


def _colonne_pays(brut, pays: str, onglet: str) -> Tuple[int, int]:
    """La colonne du pays et le rang où son nom figure — par CONTENU.

    ⚠️ NI LE PAYS NI LE CODE NE SONT CHERCHÉS PAR LEUR RANG. Les paramètres
    portent un libellé en colonne 1 ; ces deux-là n'en ont pas, et les figer
    à la ligne 2 et à la ligne 3 rendrait le lecteur sensible à une ligne
    insérée — exactement ce que la lecture par libellé évite ailleurs. On les
    cherche donc par ce qu'ils CONTIENNENT.
    """
    for rang in range(min(_LIGNES_ENTETE, len(brut))):
        for col in brut.columns:
            if str(brut.iloc[rang, col]).strip() == pays:
                return int(col), rang
    raise CourbeIllisible(
        f"Colonne « {pays} » introuvable dans l'en-tête de l'onglet {onglet}. "
        f"Le classeur EIOPA porte le nom du pays en tête de sa colonne ; son "
        f"absence signifie que ce n'est pas le bon fichier, ou que sa "
        f"structure a changé.")


def _code_courbe(brut, colonne: int, rang_pays: int,
                 onglet: str) -> Tuple[str, Dict[str, object]]:
    """Le code de la courbe et ce qu'il déclare — cherché par sa FORME.

    La recherche et le décodage sont le MÊME geste : le code est reconnu
    parce qu'il se décode. Les séparer laisserait une branche d'erreur morte
    dans le décodeur.
    """
    for rang in range(rang_pays + 1,
                      min(rang_pays + 1 + _LIGNES_ENTETE, len(brut))):
        valeur = str(brut.iloc[rang, colonne]).strip()
        trouve = _MOTIF_CODE.match(valeur)
        if trouve:
            g = trouve.groupdict()
            return valeur, {
                'devise': g['devise'],
                'date':   f"{g['annee']}-{g['mois']}-{g['jour']}",
                'llp':    float(g['llp']),
                'ext':    float(g['ext']),
                'ufr':    float(g['ufr']),
            }
    raise CourbeIllisible(
        f"Code de courbe introuvable sous « {_PAYS_EURO} » dans l'onglet "
        f"{onglet}. Forme attendue "
        f"« EUR_JJ_MM_AAAA_SWP_LLP_20_EXT_40_UFR_3.30 ». Sans lui, la date "
        f"d'arrêté ne peut pas être établie et la courbe ne serait pas "
        f"opposable.")


def _lignes_par_libelle(brut, libelles: Sequence[str]) -> Dict[str, int]:
    """Le rang de chaque paramètre, cherché par son LIBELLÉ en colonne 1."""
    trouves: Dict[str, int] = {}
    colonne_libelles = [str(brut.iloc[r, 1]).strip()
                        for r in range(min(40, len(brut)))]
    for lib in libelles:
        if lib in colonne_libelles:
            trouves[lib] = colonne_libelles.index(lib)
    manquants = [lib for lib in libelles if lib not in trouves]
    if manquants:
        raise CourbeIllisible(
            f"Paramètres introuvables en colonne 1 : {', '.join(manquants)}. "
            f"Ils sont lus par leur libellé et non par leur rang ; leur "
            f"absence signifie que la structure du classeur a changé.")
    return trouves


def _exiger_concordance(decode: Dict[str, object], parametres: Dict,
                        code: str) -> str:
    """LES DEUX DÉCLARATIONS DU FICHIER DOIVENT DIRE LA MÊME CHOSE.

    C'est ce contrôle qui distingue « j'ai compris » de « j'ai cru
    comprendre ». Il n'a rien de théorique : il porte sur trois grandeurs que
    le classeur écrit DEUX FOIS, sous deux formes.

    Le CRA et l'alpha ne sont PAS recoupés — le code ne les porte pas. Ils
    sont lus des lignes de paramètres et publiés tels quels, et cette limite
    est dite ici plutôt que tue.
    """
    controles = (('LLP', 'llp', 'LLP'),
                 ('convergence', 'ext', 'Convergence'),
                 ('UFR', 'ufr', 'UFR'))
    ecarts = []
    for libelle, cle_code, cle_param in controles:
        du_code = float(decode[cle_code])
        de_ligne = _flottant(parametres.get(cle_param))
        if de_ligne is None or abs(du_code - de_ligne) > 1e-6:
            ecarts.append(f"{libelle} : le code dit {du_code:g}, la ligne de "
                          f"paramètres dit {de_ligne}")
    if ecarts:
        raise CourbeIllisible(
            "Le classeur se contredit — les deux déclarations de la même "
            "courbe divergent : " + " ; ".join(ecarts) + ". Ce lecteur "
            "refuse plutôt que de choisir l'une des deux : une courbe lue de "
            "travers produirait un chiffre faux sans le dire.")
    return (f"LLP {decode['llp']:g} ans · convergence {decode['ext']:g} ans · "
            f"UFR {decode['ufr']:g} % — concordants entre le code de la "
            f"courbe ({code}) et les lignes de paramètres")


def _lire_va(brut_va, attendu_avec_va: bool, onglet: str) -> Optional[float]:
    """`avec_va` est LU, jamais déclaré — et le désaccord est un refus."""
    valeur = _flottant(brut_va)
    renseigne = valeur is not None
    if attendu_avec_va and not renseigne:
        raise CourbeIllisible(
            f"L'onglet {onglet} est censé porter un Volatility Adjustment, "
            f"et sa ligne VA est vide. Le classeur ne correspond pas à ce "
            f"qui est demandé.")
    if not attendu_avec_va and renseigne:
        raise CourbeIllisible(
            f"L'onglet {onglet} est censé être SANS Volatility Adjustment, "
            f"et sa ligne VA vaut {valeur:g}. Employer `lire_classeur_eiopa"
            f"_avec_va` en déclarant l'agrément, ou vérifier le fichier.")
    return valeur if attendu_avec_va else None


def _lire_taux(brut, colonne: int, apres: int,
               onglet: str) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    """Les taux, lus sous les paramètres, la maturité étant son propre
    libellé en colonne 1."""
    maturites, taux = [], []
    for rang in range(apres + 1, len(brut)):
        etiquette = _flottant(brut.iloc[rang, 1])
        valeur = _flottant(brut.iloc[rang, colonne])
        if etiquette is None or valeur is None:
            break
        maturites.append(float(etiquette))
        taux.append(float(valeur))
    if len(maturites) < 2:
        raise CourbeIllisible(
            f"Moins de deux maturités lues dans l'onglet {onglet}. Le "
            f"classeur EIOPA en publie cent cinquante ; ce fichier n'est pas "
            f"celui attendu.")
    return tuple(maturites), tuple(taux)


def _flottant(valeur) -> Optional[float]:
    """Un flottant fini, ou `None` — une cellule vide n'est pas un zéro."""
    if valeur is None:
        return None
    try:
        sortie = float(valeur)
    except (TypeError, ValueError):
        return None
    return sortie if np.isfinite(sortie) else None


# =============================================================================
#  LES PORTES SECONDAIRES — EN ÉTAT DE MARCHE, JAMAIS DÉFINITIVES
# =============================================================================

#: En deçà de ce maximum EN VALEUR ABSOLUE, une série est lue comme étant en
#: DÉCIMAL et non en pourcentage, et refusée plutôt que divisée par cent une
#: seconde fois. SEUIL CALIBRÉ PAR LA MESURE sur le cas le plus défavorable —
#: une courbe légitime en régime de taux NÉGATIFS, tronquée aux maturités
#: courtes :
#:      EIOPA 2026 en décimal ................ 0,0337   refuser
#:      EIOPA 2026 en pourcentage ............ 3,3720   accepter
#:      EUR fin 2020, complète ............... 3,1500   accepter
#:      EUR fin 2020, tronquée à 10 ans ...... 0,6000   accepter  ← le cas serré
#: Tout seuil de 0,05 à 0,50 sépare ; 0,15 est le milieu géométrique, soit un
#: facteur 4,4 de marge de part et d'autre. LA VALEUR ABSOLUE EST
#: STRUCTURANTE : le maximum SIGNÉ du dernier cas vaut −0,25, sous n'importe
#: quel seuil.
TAUX_MIN_PLAUSIBLE_PCT = 0.15

_CONSIGNE_POURCENT = (
    "Les taux doivent être exprimés EN POURCENTAGE — 2,826 pour 2,826 %. "
    "Les fichiers EIOPA les publient en décimal (0,02826) : multipliez la "
    "colonne par 100 avant l'import. Si votre courbe est réellement de cet "
    "ordre, saisissez-la comme taux manuel plutôt que par fichier.")


def _diagnostic_unite(taux_pct) -> Optional[str]:
    """Un message si la série ressemble à des décimaux, sinon `None`.

    Le zéro est admis sans réserve : une actualisation nulle assumée est un
    choix, pas une erreur d'unité.
    """
    valeurs = np.asarray(
        [v for v in np.ravel(np.asarray(taux_pct, dtype=float))
         if np.isfinite(v)], dtype=float)
    if valeurs.size == 0:
        return None
    maxi = float(np.abs(valeurs).max())
    if maxi == 0.0 or maxi >= TAUX_MIN_PLAUSIBLE_PCT:
        return None
    return (f"Taux lus comme des décimaux : le plus élevé vaut {maxi:.5f} en "
            f"valeur absolue, là où une courbe en pourcentage dépasse "
            f"{TAUX_MIN_PLAUSIBLE_PCT}. {_CONSIGNE_POURCENT}")


def lire_deux_colonnes(fichier_bytes: bytes) -> CourbeRFR:
    """Un extrait à deux colonnes — maturité, taux en POURCENTAGE.

    ⚠️ PORTE SECONDAIRE, DÉLIBÉRÉMENT NON INVESTIE. Elle n'apporte AUCUNE
    date d'arrêté : la courbe qui en sort ne peut pas porter un chiffre
    définitif, et `diagnostic_peremption` le dit. Son seul cas d'usage
    restant, une fois le lecteur officiel en place, est une courbe qui n'est
    pas EIOPA. Elle est maintenue en état de marche, pas développée.
    """
    try:
        import pandas as pd
    except ImportError as e:                                # pragma: no cover
        raise CourbeIllisible(f"pandas indisponible : {e}") from e
    try:
        df = pd.read_excel(io.BytesIO(fichier_bytes))
    except Exception as e:
        raise CourbeIllisible(f"Classeur illisible : {e}") from e

    df.columns = [str(c).lower().strip() for c in df.columns]
    if len(df.columns) < 2:
        raise CourbeIllisible(
            "Deux colonnes attendues : maturité (années) et taux (%).")
    col_mat = next((c for c in df.columns if 'mat' in c or c in
                    ('t', 'annee', 'année', 'year')), df.columns[0])
    col_taux = next((c for c in df.columns if 'taux' in c or 'rate' in c
                     or 'rfr' in c or c in ('r', 'pct')), df.columns[1])

    mats = [float(x) for x in df[col_mat].dropna()]
    taux = [float(x) for x in df[col_taux].dropna()]
    if len(mats) < 2 or len(taux) < 2:
        raise CourbeIllisible("Moins de deux maturités exploitables.")
    if len(mats) != len(taux):
        raise CourbeIllisible(
            f"{len(mats)} maturités pour {len(taux)} taux — les deux colonnes "
            f"ne s'alignent pas.")

    alerte = _diagnostic_unite(taux)
    if alerte:
        raise CourbeIllisible(alerte)

    ordre = sorted(range(len(mats)), key=lambda i: mats[i])
    return CourbeRFR(
        date_arrete=None,
        devise='?',
        avec_va=False,
        maturites=tuple(mats[i] for i in ordre),
        taux_decimal=tuple(taux[i] / 100.0 for i in ordre),
        provenance=(f"Extrait à deux colonnes fourni par l'actuaire — "
                    f"{len(mats)} maturités, sans date d'arrêté"),
        concordance=None,
    )


def taux_plat(taux_pct: float) -> CourbeRFR:
    """Un taux unique, toutes maturités — UN OUTIL DE SENSIBILITÉ.

    ⚠️ CE N'EST PAS UN IMPORT DE COURBE, et le nommer ainsi entretenait la
    confusion. « Que devient ma marge de risque à 2 % ? » est une question
    légitime avant de signer. Le résultat n'est pas pour autant un chiffre
    d'arrêté : sans date, il plafonne.

    ⚠️ MÊME PIÈGE D'UNITÉ QUE POUR LE FICHIER, ET IL A DÉJÀ SERVI. Saisir
    `0.03` en pensant 3 % rendait une courbe à 0,030 % sans un mot ; l'erreur
    a été commise pendant la conception du garde-fou, sur cette fonction même.
    """
    alerte = _diagnostic_unite(taux_pct)
    if alerte:
        raise CourbeIllisible(alerte)
    valeur = float(taux_pct) / 100.0
    return CourbeRFR(
        date_arrete=None,
        devise='?',
        avec_va=False,
        maturites=(1.0, 150.0),
        taux_decimal=(valeur, valeur),
        provenance=(f"Taux plat de {float(taux_pct):.3f} % assumé par "
                    f"l'actuaire — outil de sensibilité, sans date d'arrêté"),
        concordance=None,
    )


# =============================================================================
#  LA GOUVERNANCE — SANS DATE D'ARRÊTÉ, JAMAIS UN CHIFFRE DÉFINITIF
# =============================================================================

def age_courbe_mois(courbe: CourbeRFR, date_valorisation=None) -> Optional[float]:
    """Âge de la courbe en mois à la date de valorisation, ou `None`.

    `None` en entrée = aujourd'hui. Le paramètre existe pour qu'un arrêté
    passé soit jugé à SA date : un arrêté du 31/12/2026 recalculé en 2028 ne
    doit pas déclarer sa courbe périmée à tort.
    """
    if courbe.date_arrete is None:
        return None
    arrete = datetime.strptime(courbe.date_arrete, '%Y-%m-%d').date()
    return (date_reference(date_valorisation) - arrete).days / JOURS_PAR_MOIS


def date_reference(date_valorisation=None) -> date:
    """La date à laquelle on juge la courbe. `None` = aujourd'hui.

    ⚠️ EXTRAITE POUR N'EXISTER QU'UNE FOIS. L'âge et le message de refus la
    lisent tous deux ; deux normalisations de la même entrée finiraient par
    diverger sur un format, et le message nommerait alors une autre date que
    celle qui a servi au calcul.
    """
    if date_valorisation is None:
        return date.today()
    if isinstance(date_valorisation, str):
        return datetime.strptime(date_valorisation[:10], '%Y-%m-%d').date()
    return date_valorisation


def diagnostic_peremption(courbe: CourbeRFR, date_valorisation=None) -> Dict:
    """VERT / AMBRE / ROUGE — et une courbe SANS DATE est ROUGE.

    ⚠️ CETTE FONCTION NE JUGE PLUS SEULEMENT LA PÉREMPTION, et son nom ne le
    dit plus tout à fait. Elle répond désormais à la question complète :
    « cette courbe est-elle admissible pour cet arrêté ? » — dont la
    péremption n'est qu'une des causes de refus, l'anachronisme en étant une
    autre. Le nom est conservé délibérément : le renommer toucherait quatorze
    sites d'appel pour un gain de vocabulaire.

    ⚠️ ET C'EST UN STATUT, PAS DEUX. Rendre l'anachronisme par un second
    verdict aurait laissé DEUX valeurs à consulter, et un consommateur n'en
    aurait lu qu'une — le défaut « contrôle correct, non câblé » qu'A6 a déjà
    payé. Un statut, des causes nommées : la forme retenue hier pour le RAG.

    ⚠️ C'EST LA RÈGLE QUE CE LOT POSE, ET ELLE CORRIGE UN SILENCE MESURÉ. Une
    courbe fournie sans date recevait « NON TESTABLE », qui n'est ni ROUGE ni
    dans (AMBRE, ROUGE) : elle traversait DEUX circuits de gouvernance sans en
    déclencher aucun. Un actuaire saisissait un taux plat, obtenait un VERT,
    et rien ne disait que l'actualisation reposait sur un taux supposé. La
    courbe embarquée périmée, elle, était plafonnée — le repli explicite était
    donc MIEUX gouverné que la saisie de l'actuaire.

    ⚠️ SEUL LE ROUGE PLAFONNE, PAS L'AMBRE, chez le consommateur. EIOPA
    publie mensuellement : un trimestre de retard reste usuel entre deux
    arrêtés, un an ne l'est pas. Faire plafonner l'AMBRE interdirait le VERT
    presque toute l'année.

    ⚠️ CE LOT NE BRANCHE AUCUN CONSOMMATEUR. La règle est posée et verrouillée
    ici ; les verdicts qu'elle déplacera se mesureront en R2.
    """
    mois = age_courbe_mois(courbe, date_valorisation)
    reference = date_reference(date_valorisation)
    if mois is None:
        return {
            'statut': 'ROUGE', 'age_mois': None, 'date_courbe': None,
            'message': (
                "⚠️ COURBE SANS DATE D'ARRÊTÉ — "
                f"{courbe.provenance}. Une courbe dont l'arrêté n'est pas "
                "établi ne peut pas porter un chiffre définitif : la Risk "
                "Margin et toute actualisation qui en découlent restent des "
                "ordres de grandeur. Importer le classeur EIOPA officiel, "
                "qui porte sa date, avant toute inscription au bilan."),
            'seuil_ambre_mois': MOIS_ALERTE_PEREMPTION,
            'seuil_rouge_mois': MOIS_ROUGE_PEREMPTION,
        }
    if mois < 0:
        # ⚠️ QUATRIÈME CAUSE DE ROUGE, ET CE N'EST PAS DE LA PÉREMPTION. Une
        # courbe POSTÉRIEURE à l'arrêté n'est pas « trop vieille » : elle
        # n'existait pas quand la clôture a été arrêtée. La valoriser avec
        # elle revient à employer une information future.
        #
        # ⚠️ ET LE SILENCE ÉTAIT TOTAL : un âge négatif passe sous TOUS les
        # seuils, donc sortait VERT, avec ce message publié —
        # « Courbe EIOPA du 2026-07-31 (-24 mois) — à jour pour l'arrêté
        # retenu ». Un âge négatif s'affichait ET se certifiait à jour.
        #
        # ⚠️ ROUGE ET NON AMBRE : cela ne se corrige pas en « vérifiant ».
        # L'AMBRE dit « regardez de plus près » ; ici il n'y a rien à
        # regarder, la courbe est inadmissible pour cet arrêté.
        # ⚠️ L'ÉCART SE DIT EN JOURS SOUS UN MOIS, et c'est mon propre test qui
        # l'a exigé : à un jour d'écart, -0,03 mois s'arrondit à zéro et le
        # message annonçait « 0 mois APRÈS l'arrêté » — un chiffre qui nie la
        # phrase qui le porte.
        ecart = (f"{-mois:.0f} mois" if -mois >= 1
                 else f"{round(-mois * JOURS_PAR_MOIS)} jour(s)")
        # ⚠️ LE MESSAGE NOMME LA DATE À CHERCHER. Dire « charger la courbe de
        # la date d'arrêté » laisse l'actuaire la deviner dans un classeur
        # EIOPA qui en publie une par mois ; un remède qui ne dit pas quoi
        # chercher n'est pas un remède.
        statut = 'ROUGE'
        message = (
            f"⚠️ COURBE POSTÉRIEURE À L'ARRÊTÉ — la courbe employée est datée "
            f"du {courbe.date_arrete}, soit {ecart} APRÈS l'arrêté du "
            f"{reference.isoformat()}. Elle n'existait pas à la date de "
            f"clôture : l'actualiser avec elle emploierait une information "
            f"future. Charger la courbe EIOPA publiée au "
            f"{reference.isoformat()}.")
    elif mois >= MOIS_ROUGE_PEREMPTION:
        statut = 'ROUGE'
        message = (
            f"⚠️ COURBE DES TAUX PÉRIMÉE — la courbe employée date du "
            f"{courbe.date_arrete}, soit {mois:.0f} mois. La Risk Margin et "
            f"toute actualisation en découlent et ne sont pas à jour. "
            f"Importer la courbe EIOPA en vigueur avant toute inscription au "
            f"bilan.")
    elif mois >= MOIS_ALERTE_PEREMPTION:
        statut = 'AMBRE'
        message = (
            f"🟡 La courbe employée date du {courbe.date_arrete}, soit "
            f"{mois:.0f} mois. EIOPA publie mensuellement — vérifier qu'elle "
            f"correspond bien à la date d'arrêté retenue.")
    else:
        statut = 'VERT'
        message = (f"Courbe EIOPA du {courbe.date_arrete} ({mois:.0f} mois) — "
                   f"à jour pour l'arrêté retenu.")
    return {'statut': statut, 'age_mois': round(mois, 1),
            'date_courbe': courbe.date_arrete, 'message': message,
            'seuil_ambre_mois': MOIS_ALERTE_PEREMPTION,
            'seuil_rouge_mois': MOIS_ROUGE_PEREMPTION}


#: Maturités montrées à l'actuaire pour qu'il reconnaisse SA courbe.
_MATURITES_TEMOINS = (1, 10, 30)


def resume_confirmation(courbe: CourbeRFR) -> str:
    """Ce que le lecteur a compris du fichier — à confirmer d'un coup d'œil.

    ⚠️ LA DERNIÈRE LIGNE EST CELLE QUI COMPTE. Sans elle, cet affichage
    demanderait à l'actuaire de contrôler quelque chose qu'il n'a aucun moyen
    de contrôler : il verrait « 150 maturités, 10 ans 3,159 % » sans pouvoir
    savoir si c'est la bonne colonne pays. La concordance, elle, est une
    PREUVE que le fichier a été lu comme il se déclare. L'affichage sert à
    reconnaître SA courbe, pas à rattraper un lecteur qui aurait deviné.
    """
    entete = (f"{courbe.devise} — arrêté du "
              f"{courbe.date_arrete or 'NON ÉTABLI'}, "
              f"{'avec' if courbe.avec_va else 'sans'} VA")
    temoins = ' · '.join(
        f"{m} an{'s' if m > 1 else ''} {100 * _interpoler(courbe, m):.3f} %"
        for m in _MATURITES_TEMOINS
        if courbe.maturites[0] <= m <= courbe.maturites[-1])
    lignes = [entete, f"{len(courbe.maturites)} maturités  ·  {temoins}"]

    parametres = [f"UFR {courbe.ufr:g} %" if courbe.ufr is not None else '',
                  f"CRA {courbe.cra_bps:g} bps" if courbe.cra_bps is not None else '',
                  f"LLP {courbe.llp:g} ans" if courbe.llp is not None else '',
                  f"convergence {courbe.convergence:g} ans" if courbe.convergence is not None else '',
                  f"VA {courbe.va_bps:g} bps" if courbe.va_bps is not None else '']
    parametres = [p for p in parametres if p]
    if parametres:
        lignes.append('  ·  '.join(parametres))

    lignes.append(f"✓ {courbe.concordance}" if courbe.concordance
                  else "⚠️ Aucune concordance vérifiable — "
                       + diagnostic_peremption(courbe)['statut']
                       + " : cette courbe ne peut pas porter un chiffre "
                         "définitif")
    return '\n'.join(lignes)
