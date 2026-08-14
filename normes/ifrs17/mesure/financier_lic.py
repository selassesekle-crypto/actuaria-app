# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §87 a) : LE MOUVEMENT FINANCIER DU PASSIF SINISTRES
=============================================================================

§87 : « Les produits financiers ou charges financières d'assurance
comprennent la variation de la valeur comptable du groupe de contrats
d'assurance résultant de : a) l'effet de la valeur temps de l'argent ET DE
SES VARIATIONS ; et b) l'effet du risque financier et de ses variations. »

⚠️ CE MODULE COMPLÈTE UN MANQUE NOMMÉ AU PÉRIMÈTRE. La plateforme produisait
le déroulement du LRC au taux VERROUILLÉ (§56) — insensible aux variations,
puisque son taux est figé par B72 a). Le passif au titre des sinistres
survenus, lui, relève du §59 b) → §33-37 → §36, qui exige des taux
« concordant avec les prix de marché COURANTS ». Les variations de taux
frappent donc le LIC, et cette part du §87 n'existait pas.

⚠️⚠️ LA VENTILATION OFFERTE ICI EST LA SEULE QUE CES ENTRÉES DÉTERMINENT, ET
CE N'EST PAS UN CHOIX. §87 impose de présenter le TOTAL ; il ne prescrit
aucun partage entre l'effet du temps et celui des variations de taux. Un
partage différent existe bel et bien — réévaluer d'abord la position
d'OUVERTURE au taux de clôture, puis dérouler — mais il exige une QUATRIÈME
valorisation que ce module ne reçoit pas. Avec trois, la décomposition est
unique.

⚠️ ET CETTE PRÉCISION A ÉTÉ PAYÉE. Une première version proposait deux
« conventions » déclarables ; elles rendaient les MÊMES deux nombres, parce
qu'aucune quatrième valorisation ne les distinguait. Le mécanisme de
déclaration existait pour un choix qui n'existait pas — et un commentaire
avait été écrit pour justifier la coïncidence au lieu de la corriger. Offrir
un choix fictif est pire que n'en offrir aucun : le lecteur croit avoir
arbitré.

⚠️ ET CE MODULE NE RÉÉVALUE RIEN LUI-MÊME. Il reçoit trois valorisations et
les DÉCOMPOSE. Les produire est le travail de `flux_execution.assembler`,
avec ses courbes déclarées et signées ; les mélanger ici ferait de ce module
un second lieu où vit la règle d'actualisation.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §87 a), §36, §59 b), B72 a).
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_FLUX_PAYES_NEGATIFS = 'flux_payes_negatifs'
MOTIF_VALEUR_NEGATIVE = 'valorisation_negative'

#: Le partage rendu, et le seul que trois valorisations déterminent.
TEMPS_PUIS_TAUX = 'TEMPS_PUIS_TAUX'

#: ⚠️ CE QUE §87 IMPOSE ET CE QU'IL N'IMPOSE PAS.
CONVENTION = (
    "§87 impose de PRÉSENTER les produits et charges financiers d'assurance ; "
    "il ne prescrit AUCUN partage entre l'effet du temps et l'effet des "
    "variations de taux. Le partage rendu ici — dérouler au taux d'ouverture, "
    "puis imputer l'écart de courbe — est le SEUL que trois valorisations "
    "déterminent. ⚠️ Un partage alternatif existe (réévaluer d'abord la "
    "position d'ouverture au taux de clôture) : il exige une QUATRIÈME "
    "valorisation, non reçue ici, et n'est donc PAS offert. Seul le TOTAL "
    "est invariant, et c'est lui que la norme exige.")


class MouvementFinancier(NamedTuple):
    """§87 a) sur le passif au titre des sinistres survenus.

    ⚠️ `total` EST LE SEUL POSTE QUE §87 EXIGE. `desactualisation` et
    `effet_taux` sont une ventilation de gestion : utile, mais non prescrite
    par la norme — et un partage alternatif exigerait une valorisation de
    plus, non reçue ici.
    """
    desactualisation: float   # effet du seul écoulement du temps
    effet_taux:       float   # effet du changement de courbe
    total:            float   # §87 a) — le seul poste exigé
    ordre:            str
    motif:            str


def decomposer(*, valeur_ouverture: float,
               valeur_cloture_taux_ouverture: float,
               valeur_cloture_taux_cloture: float,
               flux_payes: float) -> MouvementFinancier:
    """Le mouvement financier du LIC, ventile de la SEULE facon possible.

    Les trois valorisations attendues, toutes produites par
    `flux_execution.assembler` avec ses courbes signees :
      · `valeur_ouverture` — les flux restants a l'ouverture, au taux
        d'ouverture ;
      · `valeur_cloture_taux_ouverture` — les flux restants a la CLOTURE,
        encore evalues au taux d'OUVERTURE : c'est le deroulement pur ;
      · `valeur_cloture_taux_cloture` — les memes flux au taux de cloture.

    ⚠️ IL N'Y A PAS DE PARAMETRE D'ORDRE, ET C'EST LE RESULTAT D'UNE
    CORRECTION. Avec ces trois entrees, la ventilation est UNIQUE : offrir
    un choix ferait croire a un arbitrage qui n'existe pas.
    """
    if flux_payes < 0:
        raise RefusMesure(
            MOTIF_FLUX_PAYES_NEGATIFS,
            f"les flux payes de la periode valent {flux_payes}. Ce module "
            f"les attend en valeur absolue — un reglement diminue le passif, "
            f"et c'est lui qui pose le signe")
    for nom, v in (('valeur_ouverture', valeur_ouverture),
                   ('valeur_cloture_taux_ouverture',
                    valeur_cloture_taux_ouverture),
                   ('valeur_cloture_taux_cloture',
                    valeur_cloture_taux_cloture)):
        if v < 0:
            raise RefusMesure(
                MOTIF_VALEUR_NEGATIVE,
                f"« {nom} » vaut {v}. Une valorisation de passif negative "
                f"signalerait des recours excedant la charge, ce qui se "
                f"declare autrement")

    # ⚠️ LE TOTAL EST LE SEUL POSTE QUE §87 EXIGE.
    total = (valeur_cloture_taux_cloture + flux_payes) - valeur_ouverture
    desactualisation = ((valeur_cloture_taux_ouverture + flux_payes)
                        - valeur_ouverture)
    effet_taux = valeur_cloture_taux_cloture - valeur_cloture_taux_ouverture

    return MouvementFinancier(
        desactualisation=desactualisation, effet_taux=effet_taux,
        total=total, ordre=TEMPS_PUIS_TAUX,
        motif=(f"{CONVENTION} ⚠️ Seul `total` est exige par §87 ; la "
               f"ventilation est une information de gestion."))
