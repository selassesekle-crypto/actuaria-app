# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §80 : L'ÉTAT DE LA PERFORMANCE FINANCIÈRE
=============================================================================

§80, verbatim : « l'entité doit ventiler entre les postes suivants les
montants qu'elle comptabilise dans le ou les états de la performance
financière : a) le résultat des activités d'assurance (§83 à 86), constitué
des produits des activités d'assurance et des charges afférentes aux
activités d'assurance ; et b) les produits financiers ou charges financières
d'assurance (§87 à 92). »

⚠️ CE MODULE N'INVENTE AUCUN CHIFFRE. Les deux postes existent déjà : le
résultat des activités d'assurance vient de `lrc_paa.Periode`, la charge
financière de `financement.ArreteFinancement`. Ce module les ASSEMBLE et,
surtout, VÉRIFIE leur cohérence avec le déroulé du passif.

⚠️⚠️ CE QUI DONNE SA VALEUR À CE MODULE N'EST PAS L'ADDITION. Que le résultat
égale la somme de ses deux postes est une tautologie : on testerait
l'arithmétique de Python. La propriété qui vaut quelque chose est
CROISÉE — les trois lignes du compte de résultat doivent égaler les lignes
correspondantes du déroulé du passif (§100), au signe près, et ce signe est
UNIFORME. Deux états produits séparément peuvent chacun boucler sur lui-même
et se contredire entre eux ; c'est ce que cette vérification attrape.

⚠️ D'OÙ VIENT CETTE RÈGLE, ET CE QU'ELLE N'EST PAS. Elle a été LUE dans
l'exemple 20 des Illustrative Examples accompagnant IFRS 17 (IFRS
Foundation), où les trois lignes se répondent avec un retournement de signe
sans une seule exception. ⚠️ MAIS AUCUNE VALEUR DE CETTE SOURCE N'EST REPRISE
ICI : ses conditions de réutilisation sont restrictives et ce dépôt est
public. L'exemple a enseigné l'invariant ; il ne le vérifie pas. La
vérification porte sur les sorties de la plateforme elle-même.

⚠️ ET LA CONVENTION DE SIGNE CHANGE ICI, DÉLIBÉRÉMENT. `lrc_paa` rend des
charges POSITIVES ; le §80 les présente NÉGATIVES, comme une diminution du
résultat. Le retournement se fait dans ce module et il est déclaré — le
laisser implicite ferait passer une inversion pour une égalité.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §80, §83 à §86, §85 et §100.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.lrc_paa import Periode, RefusMesure

MOTIF_SANS_PERIODE = 'aucune_periode_fournie'
MOTIF_COMPOSANTE_INVESTISSEMENT = 'composante_investissement_dans_le_resultat'
MOTIF_ARTICULATION_ROMPUE = 'articulation_avec_le_deroule_rompue'

#: ⚠️ CE QUE §85 INTERDIT, ET QUE L'ON PEUT VÉRIFIER. « Les produits et
#: charges afférents aux activités d'assurance présentés en résultat net ne
#: doivent pas comprendre de composantes investissement. » Une composante
#: d'investissement se DÉPLACE entre le passif au titre de la couverture
#: restante et celui des sinistres survenus, et ne touche JAMAIS le compte de
#: résultat. C'est une propriété testable, pas seulement une déclaration.
MOTIF_85_RESPECTE = (
    "§85 vérifié : aucune composante d'investissement n'entre dans les "
    "produits ni dans les charges. Une composante d'investissement se "
    "déplace entre passifs et laisse le résultat inchangé.")


class ResultatGlobal(NamedTuple):
    """Les postes du §80. ⚠️ CHARGES NÉGATIVES, convention de présentation.

    ⚠️ `resultat` VAUT `None` QUAND IL N'EST PAS ÉTABLI — typiquement parce
    que la séparation attribuable / non attribuable n'a pas été fournie.
    La réserve DESCEND depuis `lrc_paa.Periode`, elle ne se perd pas en
    changeant d'état.
    """
    insurance_revenue:          float          # §83
    insurance_service_expenses: float          # §84, négatif
    insurance_service_result:   float          # §80 a)
    produits_placements:        float
    charges_financieres:        float          # §87, négatif si charge
    finance_result:             float          # §80 b)
    resultat:                   float | None
    motif:                      str


def assembler(*, periode: Periode, charge_financiere: float = 0.0,
              produits_placements: float = 0.0,
              composante_investissement: float = 0.0) -> ResultatGlobal:
    """§80 — les deux postes, et leur somme.

    ⚠️ `composante_investissement` N'EST PAS UN POSTE, C'EST UN CONTRÔLE. Le
    §85 l'interdit dans les produits comme dans les charges : en déclarer une
    non nulle ici est donc un REFUS, pas une ligne de plus.
    """
    if periode is None:
        raise RefusMesure(
            MOTIF_SANS_PERIODE,
            "aucune période fournie. Un état de la performance financière "
            "vide n'est pas un résultat nul — c'est l'absence d'état, et "
            "rendre sept lignes à zéro serait la même faute qu'une gate "
            "rendant « Ran 0 tests » en sortant 0")
    if composante_investissement:
        raise RefusMesure(
            MOTIF_COMPOSANTE_INVESTISSEMENT,
            f"une composante d'investissement de {composante_investissement} "
            f"est déclarée. §85 l'exclut des produits ET des charges "
            f"présentés en résultat net : elle se déplace entre le passif au "
            f"titre de la couverture restante et celui des sinistres "
            f"survenus, sans jamais toucher le compte de résultat. Il n'y a "
            f"donc aucune ligne où la mettre ici")
    if charge_financiere < 0:
        raise RefusMesure(
            'charge_financiere_negative',
            f"la charge financière vaut {charge_financiere}. Ce module la "
            f"reçoit en valeur absolue — c'est LUI qui pose le signe de "
            f"présentation du §80 — et un négatif signale une convention "
            f"d'appel divergente")

    # ⚠️ LE RETOURNEMENT DE SIGNE, ICI ET NULLE PART AILLEURS.
    charges = -periode.charges_service
    financieres = -charge_financiere
    service_result = periode.revenue + charges
    finance_result = produits_placements + financieres

    etabli = periode.resultat is not None
    return ResultatGlobal(
        insurance_revenue=periode.revenue,
        insurance_service_expenses=charges,
        insurance_service_result=service_result,
        produits_placements=produits_placements,
        charges_financieres=financieres,
        finance_result=finance_result,
        resultat=(service_result + finance_result) if etabli else None,
        motif=periode.motif_resultat if not etabli else MOTIF_85_RESPECTE)


def verifier_articulation(etat: ResultatGlobal, *, revenue_du_deroule: float,
                          charges_du_deroule: float,
                          charges_financieres_du_deroule: float,
                          epsilon: float = 1e-6) -> str:
    """Le compte de résultat contre le déroulé du passif (§100).

    ⚠️ LA RÈGLE EST UNIFORME : chaque ligne du déroulé vaut l'OPPOSÉ de la
    ligne correspondante du compte de résultat. Le déroulé est un mouvement
    de passif — le produit le DIMINUE, la charge et la charge financière
    l'AUGMENTENT ; le compte de résultat inverse chacun.

    ⚠️ ET C'EST LA SEULE PROPRIÉTÉ DE CE MODULE QUI NE SOIT PAS UNE
    TAUTOLOGIE. Deux états produits séparément peuvent chacun boucler sur
    eux-mêmes et se contredire entre eux. Rendre une chaîne vide vaut
    « ils concordent » ; toute rupture est NOMMÉE, ligne par ligne.
    """
    ecarts = []
    for nom, cr, deroule in (
            ('produits des activités d\'assurance',
             etat.insurance_revenue, revenue_du_deroule),
            ('charges afférentes aux activités d\'assurance',
             etat.insurance_service_expenses, charges_du_deroule),
            ('produits ou charges financiers d\'assurance',
             etat.charges_financieres, charges_financieres_du_deroule)):
        if abs(cr + deroule) > epsilon:
            ecarts.append(
                f"{nom} : {cr:+.2f} au compte de résultat contre "
                f"{deroule:+.2f} au déroulé du passif — leur somme devrait "
                f"être nulle, elle vaut {cr + deroule:+.2f}")
    if not ecarts:
        return ''
    raise RefusMesure(
        MOTIF_ARTICULATION_ROMPUE,
        "le compte de résultat et le déroulé du passif se contredisent sur "
        + f"{len(ecarts)} ligne(s). " + " · ".join(ecarts)
        + " ⚠️ Chacun peut boucler sur lui-même tout en contredisant "
          "l'autre : c'est exactement ce que cette vérification existe pour "
          "attraper")
