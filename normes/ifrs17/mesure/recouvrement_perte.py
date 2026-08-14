# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : LA COMPOSANTE DE RECOUVREMENT DE PERTE
  §66A, §66B, §70A, B119D, B119E, B119F
=============================================================================

§66A — l'entité DOIT ajuster la marge sur services contractuels d'un groupe
de réassurance détenus et comptabiliser un produit « lorsqu'elle comptabilise
une perte lors de la comptabilisation initiale d'un groupe de contrats
d'assurance sous-jacents DÉFICITAIRE ou lors de l'ajout de contrats
d'assurance sous-jacents déficitaires au groupe ».

§66B — l'entité DOIT établir (ou ajuster) une COMPOSANTE RECOUVREMENT DE
PERTE de l'actif au titre de la couverture restante du groupe cédé.

§70A — « SI l'entité évalue un groupe de contrats de réassurance détenus
selon la méthode d'affectation des primes, elle doit appliquer le §66A en
ajustant la valeur comptable de l'ACTIF au titre de la couverture restante
PLUTÔT QU'EN AJUSTANT LA MARGE sur services contractuels. »

⚠️⚠️ LE COUPLAGE §66A / §70A EST UN AIGUILLAGE, ET SON AIGUILLE EST LE §69.
La destination de l'ajustement — l'actif ou la CSM — dépend entièrement de
l'évaluation du groupe cédé en PAA, que §69 tranche. Or `reassurance_69`
rend TROIS verdicts, et l'un d'eux n'établit rien. Mesuré sur les treize
traités livrés : SEPT éligibles, SIX `NON_ETABLI` — et pour ces six, NI la
CSM NI l'actif ne peuvent être désignés. Ce module REFUSE alors de router,
au lieu de choisir une destination par défaut.

⚠️ ET LES SIX NON ÉTABLIS SONT LES QUOTE-PARTS, c'est-à-dire exactement les
traités qui portent la part de sinistres récupérable dont descend le
recouvrement. L'aiguillage n'est pas indéterminé sur un coin du portefeuille :
il l'est là où le recouvrement se joue.

B119D — l'ajustement se calcule « en multipliant a) la perte comptabilisée au
titre des contrats d'assurance sous-jacents ; et b) le POURCENTAGE des
demandes d'indemnisation […] que l'entité s'attend à recouvrer ».

B119E — un groupe déficitaire peut mêler des contrats COUVERTS par la
réassurance et des contrats NON couverts. L'entité doit alors « utiliser une
méthode d'affectation SYSTÉMATIQUE ET RATIONNELLE ». ⚠️ C'est un jugement
remis à l'entité, au même titre que B66 d) : deux méthodes systématiques et
rationnelles peuvent donner deux montants, et le texte n'en départage aucune.
Ce module la reçoit DÉCLARÉE et refuse à défaut.

B119F — la composante s'ajuste pour refléter les variations de l'élément de
perte, et « la valeur comptable de la composante recouvrement de perte NE
DOIT PAS EXCÉDER la partie de la valeur comptable de l'élément de perte […]
que l'entité s'attend à recouvrer ».

⚠️⚠️ CE QUE LE PLAFOND B119F PROUVE, ET CE QU'IL NE PROUVE PAS — À LIRE AVANT
DE LE CITER. Quand la composante est calculée par B119D, soit
`perte × part`, le plafond de B119F vaut `perte × part` : il est atteint par
CONSTRUCTION, et le vérifier ne démontre AUCUNE conformité. Il garde
néanmoins une valeur réelle, et une seule : celle d'un FILET DE
NON-RÉGRESSION. Le jour où le calcul change — indexation, plancher, ordre des
opérations, ajustement pour risque introduit — le plafond cesse d'être
gratuit et se met à mordre.

⚠️ ET « RESPECTÉ PAR CONSTRUCTION » EST LITTÉRALEMENT FAUX, mesuré. Le
producteur l'écrit dans l'avertissement de son propre fichier ; un contrôle
écrit `composante <= perte × part` ÉCHOUE sur 129 des 235 lignes livrées. La
cause est bénigne — l'arrondi au centime, maximum 0,005 €, total 0,32 € soit
0,0038 % du recouvrement, et zéro ligne au-delà de cette borne. La formule
exacte n'est donc pas « respecté par construction » mais « respecté À
L'ARRONDI DU CENTIME PRÈS », et la différence est précisément ce qui sépare
une affirmation d'un contrôle qui passe.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §66A, §66B, §70A, B119C à B119F.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import est_renseigne
from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.reassurance_69 import PAA_RA_ELIGIBLE
from normes.ifrs17.mesure.reassurance_reconciliation import (
    ARRONDI_MAX_PAR_CONTRAT,
)

#: Les deux destinations de l'ajustement du §66A, et rien d'autre.
DESTINATION_ACTIF = 'ACTIF_COUVERTURE_RESTANTE'      # §70A — groupe en PAA
DESTINATION_CSM = 'MARGE_SERVICES_CONTRACTUELS'      # §66A — modèle général

MOTIF_ROUTAGE_NON_ETABLI = 'destination_66a_non_etablie'
MOTIF_PART_HORS_BORNES = 'part_recuperable_hors_bornes'
MOTIF_PERTE_NEGATIVE = 'perte_comptabilisee_negative'
MOTIF_PLAFOND_B119F = 'composante_au_dessus_du_plafond_b119f'
MOTIF_AFFECTATION_B119E = 'affectation_b119e_non_declaree'

#: ⚠️ BRUIT DE REPRÉSENTATION BINAIRE, ET SURTOUT PAS UNE TOLÉRANCE MÉTIER.
#: `14.38 - 14.375` vaut 0,005000000000000782 en virgule flottante : la borne
#: d'arrondi est atteinte EXACTEMENT en décimal et dépassée en binaire. Le
#: confondre avec la borne du centime effacerait la distinction entre ce qui
#: est démontré (l'arrondi au centime) et ce qui est subi (le codage binaire).
EPSILON_REPRESENTATION = 1e-9

#: ⚠️ L'ÉTIQUETTE QUE TOUT CITATEUR DOIT LIRE. Elle descend avec le contrôle.
PORTEE_DU_CONTROLE_B119F = (
    "⚠️ FILET DE NON-RÉGRESSION, PAS PREUVE DE CONFORMITÉ. Quand la "
    "composante est calculée par B119D (perte × part), le plafond B119F vaut "
    "exactement cette valeur : il est atteint PAR CONSTRUCTION et ne démontre "
    "rien. Sa seule valeur est de mordre le jour où le calcul changera. Ne "
    "PAS le citer comme attestant la conformité à B119F.")


class Recouvrement(NamedTuple):
    """La composante du §66B, sa destination, et la portée de son contrôle."""
    composante:  float
    plafond:     float
    destination: str
    motif:       str


def destination_66a(verdict_69: str) -> str:
    """§70A — l'aiguillage, et il refuse de deviner.

    ⚠️ TROIS VERDICTS ENTRENT, DEUX DESTINATIONS SORTENT, ET LE TROISIÈME NE
    SORT PAS. §70A ne s'applique que « SI l'entité évalue le groupe selon la
    méthode d'affectation des primes ». Tant que §69 n'a rien établi, la
    condition du §70A n'est ni vraie ni fausse : router quand même
    placerait un ajustement sur un poste que la norme ne désigne pas.
    """
    if verdict_69 == PAA_RA_ELIGIBLE:
        return DESTINATION_ACTIF
    raise RefusMesure(
        MOTIF_ROUTAGE_NON_ETABLI,
        f"le verdict §69 du groupe cédé vaut {verdict_69!r} : l'éligibilité à "
        f"la PAA n'est pas ÉTABLIE, et §70A y subordonne toute sa règle "
        f"(« SI l'entité évalue […] selon la méthode d'affectation des "
        f"primes »). L'ajustement du §66A irait à l'actif au titre de la "
        f"couverture restante si le groupe est en PAA, à la marge sur "
        f"services contractuels sinon : les deux postes sont réels, ils ne "
        f"sont pas le même, et rien ne permet de choisir. ⚠️ Sur le "
        f"portefeuille mesuré, les six groupes concernés sont les "
        f"quote-parts — celles-là mêmes qui portent la part de sinistres "
        f"récupérable dont descend le recouvrement")


def destination_66a_hors_paa() -> str:
    """La destination quand le groupe cédé N'EST PAS en PAA — et elle se
    déclare. ⚠️ Passer par une fonction distincte plutôt que par un défaut
    de `destination_66a` est délibéré : « pas éligible » et « non établi »
    sont deux états différents, et un défaut les confondrait."""
    return DESTINATION_CSM


def part_couverte_b119e(*, perte_du_groupe: float,
                        methode_affectation_declaree: str = '',
                        part_couverte_declaree=None) -> float:
    """B119E — la part de la perte qui se rattache aux contrats couverts.

    ⚠️ CE N'EST PAS UN CALCUL, C'EST UNE MÉTHODE DE L'ENTITÉ. B119E exige
    « une méthode d'affectation SYSTÉMATIQUE ET RATIONNELLE » sans en
    prescrire aucune : deux méthodes également systématiques et rationnelles
    donnent deux montants, et le texte n'en départage pas. Le module reçoit
    donc le résultat DÉCLARÉ, avec sa méthode, et refuse à défaut.
    """
    if part_couverte_declaree is None:
        raise RefusMesure(
            MOTIF_AFFECTATION_B119E,
            "le groupe sous-jacent déficitaire mêle des contrats couverts "
            "par la réassurance et des contrats non couverts, et aucune part "
            "couverte n'est déclarée. B119E impose une méthode d'affectation "
            "systématique et rationnelle SANS en prescrire aucune : la "
            "choisir reviendrait à trancher à la place de l'entité")
    if not est_renseigne(methode_affectation_declaree):
        raise RefusMesure(
            MOTIF_AFFECTATION_B119E,
            f"une part couverte est déclarée ({part_couverte_declaree}) mais "
            f"la méthode qui la produit ne l'est pas (reçu "
            f"{methode_affectation_declaree!r}). B119E porte sur la MÉTHODE, "
            f"pas sur le montant : un montant sans sa méthode n'est pas "
            f"vérifiable, et « systématique et rationnelle » ne se constate "
            f"que sur elle")
    if not 0.0 <= part_couverte_declaree <= perte_du_groupe:
        raise RefusMesure(
            MOTIF_AFFECTATION_B119E,
            f"la part couverte déclarée ({part_couverte_declaree}) sort de "
            f"[0, {perte_du_groupe}] : elle ne peut ni être négative ni "
            f"excéder la perte du groupe qu'elle découpe")
    return float(part_couverte_declaree)


def recouvrement_b119d(*, perte_comptabilisee: float,
                       part_recuperable: float,
                       verdict_69: str) -> Recouvrement:
    """B119D + §66B + §70A — la composante, son plafond et sa destination.

    ⚠️ LE PLAFOND EST RENDU AVEC LA COMPOSANTE, et il lui est ici ÉGAL. C'est
    voulu et c'est dit : voir `PORTEE_DU_CONTROLE_B119F`.
    """
    if perte_comptabilisee < 0:
        raise RefusMesure(
            MOTIF_PERTE_NEGATIVE,
            f"la perte comptabilisée vaut {perte_comptabilisee} ; §66A ne se "
            f"déclenche que « lorsqu'elle comptabilise une PERTE », et une "
            f"perte négative serait un profit, qui n'ouvre aucun "
            f"recouvrement")
    if not 0.0 <= part_recuperable <= 1.0:
        raise RefusMesure(
            MOTIF_PART_HORS_BORNES,
            f"la part récupérable vaut {part_recuperable} ; B119D la définit "
            f"comme un POURCENTAGE des demandes d'indemnisation attendu au "
            f"recouvrement, donc dans [0, 1]")

    composante = perte_comptabilisee * part_recuperable
    return Recouvrement(
        composante=composante,
        plafond=perte_comptabilisee * part_recuperable,
        destination=destination_66a(verdict_69),
        motif=PORTEE_DU_CONTROLE_B119F)


def verifier_plafond_b119f(composante: float, plafond: float, *,
                           nb_lignes: int = 1) -> None:
    """B119F — le plafond, avec une borne d'arrondi DÉMONTRÉE, pas accordée.

    ⚠️ LA BORNE N'EST PAS UNE TOLÉRANCE DE CONFORT. Une valeur arrondie au
    centime s'écarte d'au plus 0,005 ; n lignes agrégées, d'au plus
    n × 0,005. C'est le pire cas, et il ne laisse passer que l'arrondi.
    Sans elle, un contrôle strict échouerait sur 129 des 235 lignes livrées
    pour un dépassement total de 0,32 € — un faux signalement.

    ⚠️ ET CE CONTRÔLE NE PROUVE PAS LA CONFORMITÉ : voir
    `PORTEE_DU_CONTROLE_B119F`.
    """
    borne = nb_lignes * ARRONDI_MAX_PAR_CONTRAT
    if composante - plafond > borne + abs(plafond) * EPSILON_REPRESENTATION:
        raise RefusMesure(
            MOTIF_PLAFOND_B119F,
            f"la composante de recouvrement ({composante:,.2f}) excède son "
            f"plafond B119F ({plafond:,.2f}) de "
            f"{composante - plafond:,.2f}, au-delà de la borne d'arrondi de "
            f"{borne:,.2f} sur {nb_lignes} ligne(s). B119F interdit à la "
            f"composante d'excéder la part récupérable de l'élément de "
            f"perte : la dépasser inscrirait à l'actif un recouvrement que "
            f"la perte sous-jacente ne porte pas")
