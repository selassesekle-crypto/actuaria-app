# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §66 et §67 : LE DÉROULÉ DE LA CSM CÉDÉE
=============================================================================

§66 — « AU LIEU D'APPLIQUER LE PARAGRAPHE 44 », l'entité évalue la marge sur
services contractuels à la clôture comme la valeur comptable à l'ouverture,
ajustée de : a) l'effet des nouveaux contrats ajoutés au groupe ; b)
l'intérêt capitalisé, aux taux du B72 b) ; ba) les produits comptabilisés en
application du §66A ; bb) les reprises d'une composante recouvrement de perte
du §66B, DANS LA MESURE OÙ ces reprises ne sont pas des variations des flux
d'exécution ; c) les variations des flux d'exécution se rattachant aux
SERVICES FUTURS, À MOINS QUE i) elles résultent d'une variation des flux d'un
groupe sous-jacent qui n'entraîne PAS d'ajustement de la CSM de ce groupe, ou
ii) elles résultent des §57 et §58 (contrats déficitaires) SI le groupe
sous-jacent est évalué selon la PAA ; d) l'effet des écarts de change ; et
e) le montant comptabilisé en résultat net en raison des services reçus,
déterminé par répartition CONFORMÉMENT AU §B119.

§67 — « Les variations des flux de trésorerie d'exécution qui résultent de
l'évolution du RISQUE DE NON-EXÉCUTION de la part de l'émetteur du contrat de
réassurance détenu NE SE RATTACHENT PAS AUX SERVICES FUTURS et ne doivent
donc PAS entraîner d'ajustement de la marge sur services contractuels. »

⚠️⚠️ §67 EST UNE CONTRAINTE NÉGATIVE, ET C'EST CE QUI LA REND VÉRIFIABLE. La
plupart des paragraphes de ce chantier disent quoi mettre ; celui-ci dit quoi
NE PAS mettre. Le mouvement du risque de non-exécution est mesuré par
`reassurance_63`, et il doit être EXCLU du poste c). Le module le reçoit
SÉPARÉ, l'exclut lui-même et PUBLIE le montant exclu, plutôt que d'accepter
une variation déjà nettoyée sur la parole de l'appelant : un montant qu'on
croit exclu sans qu'il le soit ne laisse aucune trace dans un total.

⚠️⚠️ LES DEUX EXCLUSIONS DU c) NE SONT PAS SYMÉTRIQUES, ET LA SECONDE DÉPEND
DU MODÈLE DU SOUS-JACENT. c) ii) ne joue QUE « si l'entité évalue le groupe
de contrats d'assurance SOUS-JACENTS selon la méthode d'affectation des
primes ». C'est le modèle du SOUS-JACENT, pas celui du groupe cédé — deux
élections distinctes, et les confondre reproduirait exactement la faute du
§70A corrigée juste avant ce lot.

⚠️ LE POSTE e) N'EST PAS CALCULABLE SANS DÉCLARATION. B119 définit les unités
de couverture par « le VOLUME DE PRESTATIONS fourni » et la « période de
couverture prévue » — aucune méthode n'est prescrite pour mesurer un volume
de prestations. C'est un jugement, au même rang que §54, §69 a) et §16 b)
substitué. Le module reçoit les unités déclarées et REFUSE à défaut, plutôt
que de répartir linéairement en silence : une répartition linéaire est une
hypothèse sur le volume, pas une absence d'hypothèse.

⚠️ ET §68 CONTINUE DE S'APPLIQUER AU DÉROULÉ : aucun plancher à zéro. Voir
`csm_cedee_65.ASYMETRIE_65_68`, qui descend aussi d'ici.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §66, §67, §68, §44, §57, §58, §66A, §66B, B72 b), B72 c), B119,
B119F.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.csm_cedee_65 import (
    ASYMETRIE_65_68,
    CONVENTIONS,
    MOTIF_CONVENTION_DE_SIGNE_NON_DECLAREE,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_UNITES_NON_DECLAREES = 'unites_de_couverture_b119_non_declarees'
MOTIF_MODELE_SOUS_JACENT_NON_DECLARE = 'modele_du_sous_jacent_non_declare'

#: ⚠️ CE QUE §67 INTERDIT, PUBLIÉ AVEC CHAQUE DÉROULÉ.
EXCLUSION_67 = (
    "⚠️ §67 : la variation due au RISQUE DE NON-EXÉCUTION du réassureur est "
    "EXCLUE de l'ajustement de la marge — elle « ne se rattache pas aux "
    "services futurs ». Elle est reçue séparée et non retranchée à "
    "l'aveugle : un montant qu'on croit exclu et qui ne l'est pas ne laisse "
    "aucune trace dans un total.")


class DerouleCsm66(NamedTuple):
    """La CSM cédée de clôture, poste par poste."""
    ouverture:            float
    nouveaux_contrats:    float
    interet_capitalise:   float
    produits_66a:         float
    reprises_66b:         float
    variations_futures:   float
    ecarts_de_change:     float
    services_recus:       float
    cloture:              float
    exclu_67:             float
    motif:                str


def variations_futures_66c(*, variation_totale: float,
                           mouvement_non_execution_67: float,
                           variation_sous_jacent_sans_csm: float = 0.0,
                           variation_57_58: float = 0.0,
                           sous_jacent_en_paa=None) -> float:
    """§66 c) — ce qui reste après les exclusions du texte, §67 compris.

    ⚠️ `sous_jacent_en_paa` N'A PAS DE DÉFAUT, et c'est le point : c) ii) ne
    joue QUE si le groupe SOUS-JACENT est évalué en PAA. C'est une seconde
    élection, distincte de celle du groupe cédé, et la deviner reproduirait
    la faute du §70A.
    """
    if variation_57_58 and sous_jacent_en_paa is None:
        raise RefusMesure(
            MOTIF_MODELE_SOUS_JACENT_NON_DECLARE,
            f"une variation de {variation_57_58} est rattachée aux §57-58 "
            f"(contrats déficitaires), mais le modèle d'évaluation du groupe "
            f"SOUS-JACENT n'est pas déclaré. §66 c) ii) ne l'exclut QUE « si "
            f"l'entité évalue le groupe de contrats d'assurance SOUS-JACENTS "
            f"selon la méthode d'affectation des primes » — c'est le modèle "
            f"du sous-jacent, pas celui du groupe cédé, et ce sont deux "
            f"élections distinctes")

    reste = variation_totale - mouvement_non_execution_67
    reste -= variation_sous_jacent_sans_csm
    if variation_57_58 and sous_jacent_en_paa:
        reste -= variation_57_58
    return reste


def deroule_66(*, ouverture: float, convention_de_signe: str,
               unites_periode=None, unites_restantes=None,
               nouveaux_contrats: float = 0.0,
               interet_capitalise: float = 0.0,
               produits_66a: float = 0.0,
               reprises_66b: float = 0.0,
               variation_totale_flux: float = 0.0,
               mouvement_non_execution_67: float = 0.0,
               variation_sous_jacent_sans_csm: float = 0.0,
               variation_57_58: float = 0.0,
               sous_jacent_en_paa=None,
               ecarts_de_change: float = 0.0) -> DerouleCsm66:
    """§66 — le déroulé complet, avec c) filtré et e) réparti selon B119.

    ⚠️ L'EXCLUSION DU §67 SE FAIT ICI, LÀ OÙ LE RÉSULTAT SE CONSTRUIT, et le
    montant exclu est PUBLIÉ. Recevoir une variation déjà nettoyée obligerait
    à croire l'appelant sur parole, et un montant qu'on croit exclu sans
    qu'il le soit ne laisse aucune trace dans un total.

    ⚠️ AUCUN PLANCHER : §68 écarte les §47-52, et la clôture sort telle
    qu'elle est calculée, fût-elle un coût net.
    """
    if convention_de_signe not in CONVENTIONS:
        raise RefusMesure(
            MOTIF_CONVENTION_DE_SIGNE_NON_DECLAREE,
            f"la convention de signe n'est pas déclarée (reçu "
            f"{convention_de_signe!r}, attendu l'une de {CONVENTIONS}). Elle "
            f"gouverne la lecture du résultat, et §68 interdisant tout "
            f"plancher, la clôture peut sortir des deux côtés de zéro")
    if unites_periode is None or unites_restantes is None:
        raise RefusMesure(
            MOTIF_UNITES_NON_DECLAREES,
            "§66 e) répartit la marge « CONFORMÉMENT AU PARAGRAPHE B119 », "
            "lequel définit les unités de couverture par « le VOLUME DE "
            "PRESTATIONS fourni » et la période de couverture prévue. Aucune "
            "méthode n'est prescrite pour mesurer ce volume : c'est un "
            "jugement de l'entité. ⚠️ RÉPARTIR LINÉAIREMENT À DÉFAUT SERAIT "
            "UNE HYPOTHÈSE SUR LE VOLUME, PAS UNE ABSENCE D'HYPOTHÈSE — elle "
            "supposerait des prestations uniformes dans le temps, ce qui est "
            "faux pour la plupart des couvertures")
    if unites_periode < 0 or unites_restantes < 0:
        raise RefusMesure(
            MOTIF_UNITES_NON_DECLAREES,
            f"unités négatives ({unites_periode}, {unites_restantes}) : une "
            f"unité de couverture est un volume de prestations, jamais "
            f"négatif")
    if unites_periode > unites_restantes:
        raise RefusMesure(
            MOTIF_UNITES_NON_DECLAREES,
            f"les unités de la période ({unites_periode}) excèdent les unités "
            f"restantes à la clôture avant répartition ({unites_restantes}). "
            f"B119 répartit la marge « sur la période considérée ET la "
            f"période de couverture restante » : la part de la période ne "
            f"peut pas excéder le tout")

    variations_futures = variations_futures_66c(
        variation_totale=variation_totale_flux,
        mouvement_non_execution_67=mouvement_non_execution_67,
        variation_sous_jacent_sans_csm=variation_sous_jacent_sans_csm,
        variation_57_58=variation_57_58,
        sous_jacent_en_paa=sous_jacent_en_paa)

    avant_repartition = (ouverture + nouveaux_contrats + interet_capitalise
                         + produits_66a + reprises_66b + variations_futures
                         + ecarts_de_change)
    if unites_restantes == 0:
        #: ⚠️ Zéro unité restante : toute la marge est reconnue. Ce n'est pas
        #: une division par zéro évitée, c'est le cas où la couverture est
        #: entièrement fournie — et il se nomme.
        services_recus = avant_repartition
    else:
        services_recus = avant_repartition * (unites_periode
                                              / unites_restantes)

    return DerouleCsm66(
        ouverture=ouverture, nouveaux_contrats=nouveaux_contrats,
        interet_capitalise=interet_capitalise, produits_66a=produits_66a,
        reprises_66b=reprises_66b, variations_futures=variations_futures,
        ecarts_de_change=ecarts_de_change, services_recus=services_recus,
        cloture=avant_repartition - services_recus,
        exclu_67=mouvement_non_execution_67,
        motif=_motif_66(unites_periode, unites_restantes,
                        mouvement_non_execution_67))


def _motif_66(unites_periode, unites_restantes, exclu_67) -> str:
    """Ce que le déroulé établit, et sous quelles étiquettes."""
    base = (f"§66 : déroulé de la marge cédée, poste par poste. Poste e) "
            f"réparti selon B119 sur des unités de couverture DÉCLARÉES "
            f"({unites_periode} sur {unites_restantes}) — B119 les définit "
            f"par le volume de prestations, qu'aucune méthode ne prescrit de "
            f"mesurer : la répartition engage l'entité. ")
    if exclu_67:
        base += (f"⚠️ {exclu_67:,.2f} EXCLU au titre du §67 (risque de "
                 f"non-exécution), et le montant est publié plutôt que "
                 f"fondu. ")
    if unites_restantes == 0:
        base += ("⚠️ AUCUNE UNITÉ RESTANTE : la couverture est entièrement "
                 "fournie et la totalité de la marge est comptabilisée en "
                 "résultat. ")
    return base + EXCLUSION_67 + ' ' + ASYMETRIE_65_68
