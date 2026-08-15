# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §64 : L'AJUSTEMENT POUR RISQUE DE LA RÉASSURANCE DÉTENUE
=============================================================================

§64, intégral — « AU LIEU D'APPLIQUER LE PARAGRAPHE 37, l'entité doit
déterminer l'ajustement au titre du risque non financier de façon à ce qu'il
corresponde AU MONTANT DU RISQUE QUI EST TRANSFÉRÉ par le titulaire du groupe
de contrats de réassurance à l'émetteur de ces derniers. »

⚠️⚠️ C'EST LE SEUL DES CINQ PARAGRAPHES DE LA MESURE CÉDÉE QUI NE CALCULE
RIEN, ET IL FAUT LE DIRE AUSSI NETTEMENT QUE LE RESTE. §65 est une somme,
§66 un déroulé, §67 une contrainte, §68 un invariant — tous vérifiables. §64,
lui, remplace une règle sans méthode (§37) par une autre règle sans méthode.
Il change ce que la grandeur SIGNIFIE — le risque TRANSFÉRÉ, non le risque
supporté — sans dire comment la mesurer. C'est le douzième paragraphe de ce
chantier à remettre la décision à l'entité.

⚠️ MAIS IL N'EST PAS VIDE POUR AUTANT, ET C'EST LÀ QUE LE MODULE SERT. En
substituant « transféré » à « supporté », §64 impose une BORNE : on ne peut
pas transférer plus de risque qu'il n'en existe. L'ajustement cédé ne peut
donc excéder l'ajustement brut du groupe sous-jacent. Une seule chose est
vérifiable, elle l'est, et le module ne prétend à rien d'autre.

⚠️ ET LE SENS DE CETTE BORNE N'EST PAS NEUTRE. Un ajustement cédé surestimé
GONFLE l'actif de réassurance — l'écart va en faveur de l'entité, comme
l'omission des litiges au §63 et comme la décomptabilisation supposée nulle
au §65 b). Trois omissions différentes, un même sens : c'est ce qui rend le
contrôle utile plutôt que formel.

⚠️ CE QUE LA BORNE NE PROUVE PAS : qu'un ajustement qui la respecte soit
JUSTE. Un ajustement cédé de zéro passe la borne et serait absurde sur un
traité en quote-part. La borne écarte l'impossible, elle ne valide pas le
plausible — et un contrôle qui ne dit pas sa portée se fait surévaluer.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §64, §37, B86 à B92.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import est_renseigne
from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_AJUSTEMENT_NON_DECLARE = 'ajustement_64_non_declare'
MOTIF_AJUSTEMENT_HORS_BORNE = 'ajustement_64_excede_le_risque_brut'

#: ⚠️ L'ÉTIQUETTE QUI DIT CE QUE LE CONTRÔLE NE PROUVE PAS.
PORTEE_DE_LA_BORNE_64 = (
    "⚠️ CETTE BORNE ÉCARTE L'IMPOSSIBLE, ELLE NE VALIDE PAS LE PLAUSIBLE. "
    "§64 ne prescrit AUCUNE méthode pour mesurer le risque transféré : il "
    "remplace la règle sans méthode du §37 par une autre règle sans méthode, "
    "en changeant seulement ce que la grandeur signifie. Un ajustement cédé "
    "de zéro respecterait cette borne et serait absurde sur une quote-part. "
    "Ne PAS citer ce contrôle comme attestant la conformité au §64.")


class AjustementCede64(NamedTuple):
    """L'ajustement cédé déclaré, sa borne, et la portée du contrôle."""
    ajustement_cede: float
    ajustement_brut: float
    part_transferee: float
    motif:           str


def ajustement_risque_64(*, ajustement_cede_declare=None,
                         ajustement_brut_sous_jacent: float,
                         methode_declaree: str = '') -> AjustementCede64:
    """§64 — reçoit l'ajustement cédé déclaré, et vérifie la seule borne.

    ⚠️ IL NE CALCULE PAS L'AJUSTEMENT, ET C'EST DÉLIBÉRÉ. Le déduire de la
    part de cession — « 40 % du risque brut pour une quote-part à 40 % » —
    serait une MÉTHODE, non une lecture du texte : §64 parle du risque
    transféré, que la structure du traité ne détermine pas à elle seule
    (garanties plafonnées, priorités, reconstitutions). Poser cette méthode
    en silence reviendrait à décider à la place de l'entité.
    """
    if ajustement_brut_sous_jacent < 0:
        raise RefusMesure(
            MOTIF_AJUSTEMENT_HORS_BORNE,
            f"l'ajustement pour risque brut du sous-jacent vaut "
            f"{ajustement_brut_sous_jacent} ; §37 le définit comme une "
            f"compensation exigée pour supporter l'incertitude, donc un "
            f"montant positif ou nul")
    if ajustement_cede_declare is None:
        raise RefusMesure(
            MOTIF_AJUSTEMENT_NON_DECLARE,
            "§64 exige que l'ajustement pour risque du groupe cédé "
            "« corresponde au montant du risque QUI EST TRANSFÉRÉ » — et il "
            "ne prescrit AUCUNE méthode pour le mesurer, pas plus que le §37 "
            "qu'il remplace. ⚠️ LE DÉDUIRE DE LA PART DE CESSION SERAIT UNE "
            "MÉTHODE, PAS UNE LECTURE : le risque transféré ne se déduit pas "
            "de la seule structure du traité, que des garanties plafonnées, "
            "une priorité ou des reconstitutions modifient. Reçu déclaré, "
            "refusé à défaut")
    if not est_renseigne(methode_declaree):
        raise RefusMesure(
            MOTIF_AJUSTEMENT_NON_DECLARE,
            f"l'ajustement cédé vaut {ajustement_cede_declare} mais aucune "
            f"méthode ne l'établit (reçu {methode_declaree!r}). §64 porte sur "
            f"une GRANDEUR À DÉTERMINER : un montant sans la méthode qui le "
            f"détermine est invérifiable, et « non vide » n'est pas "
            f"« renseigné »")

    cede = float(ajustement_cede_declare)
    if cede < 0:
        raise RefusMesure(
            MOTIF_AJUSTEMENT_HORS_BORNE,
            f"l'ajustement cédé vaut {cede} ; un risque transféré négatif "
            f"n'a pas de sens — l'entité ne transfère pas un risque à "
            f"l'envers")
    if cede > ajustement_brut_sous_jacent + 1e-9:
        raise RefusMesure(
            MOTIF_AJUSTEMENT_HORS_BORNE,
            f"l'ajustement cédé ({cede}) excède l'ajustement brut du groupe "
            f"sous-jacent ({ajustement_brut_sous_jacent}). §64 le définit "
            f"comme le risque TRANSFÉRÉ : on ne transfère pas plus de risque "
            f"qu'il n'en existe. ⚠️ ET LE SENS DE L'ÉCART COMPTE : un "
            f"ajustement cédé surestimé GONFLE l'actif de réassurance, en "
            f"faveur de l'entité")

    part = (cede / ajustement_brut_sous_jacent
            if ajustement_brut_sous_jacent else 0.0)
    return AjustementCede64(
        ajustement_cede=cede, ajustement_brut=ajustement_brut_sous_jacent,
        part_transferee=part,
        motif=(f"§64 : ajustement pour risque du groupe cédé de {cede:,.2f}, "
               f"soit {part:.1%} de l'ajustement brut du sous-jacent "
               f"({ajustement_brut_sous_jacent:,.2f}). Déterminé par l'entité "
               f"selon « {methode_declaree} » — §64 remplace le §37 sans "
               f"prescrire de méthode, il change seulement ce que la grandeur "
               f"signifie : le risque TRANSFÉRÉ, non le risque supporté. "
               + PORTEE_DE_LA_BORNE_64))
