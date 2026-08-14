# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 B65/B66 : ATTRIBUABLE OU NON, ET QUI LE DÉCIDE
=============================================================================

⚠️⚠️ CE MODULE NE DÉDUIT RIEN, ET C'EST UNE CONCLUSION MESURÉE. La question
posée était : la séparation attribuable / non attribuable est-elle une RÈGLE
CALCULABLE, ou une décision comptable de l'entité ? Réponse, en lisant le
texte : une décision de l'entité — du même bois que §54 et que l'option
§59 a), que ce dépôt a refusé d'exercer pour la même raison.

B66 d), verbatim : « les flux de trésorerie relatifs à des coûts qui NE SONT
PAS DIRECTEMENT ATTRIBUABLES au portefeuille de contrats d'assurance dont
fait partie le contrat en cause, TELS QUE certains frais de développement de
produits et de formation ».

⚠️ TROIS MOTS TRANCHENT :
  · « tels que » — la liste est ILLUSTRATIVE, jamais limitative ;
  · « certains » frais de développement — à l'intérieur même d'une
    catégorie, une part est attribuable et l'autre non ;
  · B65 e) parle de frais d'acquisition « AFFECTÉS au portefeuille » —
    l'affectation est un acte de l'entité, pas une lecture de la norme.

⚠️ LA NUANCE QUI DISTINGUE CE CAS DE §54 ET §59 a). Le §54 repose sur une
ATTENTE ; le §59 a) est une OPTION. Ici le CRITÈRE est normatif — « directement
attribuables » — et c'est son APPLICATION qui appartient à l'entité, seule à
voir sa comptabilité analytique. Le module nomme donc le critère, REÇOIT la
déclaration, et la PUBLIE.

⚠️ CE QUI RESTE CALCULABLE, ET QUI EST LE SEUL VRAI GARDE ICI : qu'aucun coût
ne disparaisse entre les deux paniers. Une somme déclarée qui ne recouvre pas
le total remis laisserait des charges s'évaporer sans que rien ne le dise —
et le résultat d'assurance en sortirait gonflé, exactement le défaut que
`MOTIF_SEPARATION_NON_FOURNIE` empêche en amont.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, B65 e) et f), B66 d).
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import est_renseigne
from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_ATTRIBUTION_SANS_SIGNATURE = 'attribution_sans_signataire'
MOTIF_CATEGORIE_DANS_LES_DEUX = 'categorie_declaree_des_deux_cotes'
MOTIF_COUT_EVAPORE = 'somme_declaree_inferieure_au_total_remis'
MOTIF_ATTRIBUTION_VIDE = 'aucune_categorie_declaree'

#: Le critère, cité pour être publié à côté de la déclaration. ⚠️ IL EST
#: NORMATIF ; c'est son application qui ne l'est pas.
CRITERE = (
    "B66 d) exclut les coûts « qui ne sont pas directement attribuables au "
    "portefeuille de contrats d'assurance dont fait partie le contrat en "
    "cause, tels que certains frais de développement de produits et de "
    "formation ». ⚠️ « TELS QUE » : la liste est illustrative, jamais "
    "limitative — et « CERTAINS » frais de développement, donc une même "
    "catégorie peut se partager. B65 e) et f) nomment à l'inverse ce qui "
    "entre : les frais d'acquisition AFFECTÉS au portefeuille, et les coûts "
    "de gestion des sinistres. L'affectation elle-même est un acte de "
    "l'entité, qui seule voit sa comptabilité analytique.")


class Attribution(NamedTuple):
    """La déclaration de l'entité, et ce qui la rend opposable."""
    attribuables:     tuple    # ((categorie, montant), ...)
    non_attribuables: tuple    # ((categorie, montant), ...)
    actuaire_resp:    str
    arrete:           str

    @property
    def total_attribuable(self) -> float:
        return sum(m for _, m in self.attribuables)

    @property
    def total_non_attribuable(self) -> float:
        return sum(m for _, m in self.non_attribuables)


def declarer(*, attribuables: dict, non_attribuables: dict,
             actuaire_resp: str, arrete: str,
             total_remis: float | None = None) -> Attribution:
    """Reçoit la déclaration, ou REFUSE en disant ce qui cloche.

    ⚠️ `total_remis` EST LE SEUL CONTRÔLE CALCULABLE DE CE MODULE. Fourni,
    il vérifie qu'aucun coût ne s'évapore entre les deux paniers. Omis, le
    contrôle n'a PAS lieu — et son absence ne se déguise pas en succès :
    c'est à l'appelant de savoir s'il a remis un total.
    """
    if not est_renseigne(actuaire_resp):
        raise RefusMesure(
            MOTIF_ATTRIBUTION_SANS_SIGNATURE,
            "personne ne se porte garant de cette répartition. Elle déplace "
            "des charges hors du résultat des activités d'assurance : elle "
            "engage quelqu'un, nommément")
    if not est_renseigne(arrete):
        raise RefusMesure(
            MOTIF_ATTRIBUTION_SANS_SIGNATURE,
            "la déclaration est fournie sans son arrêté. Une répartition "
            "vaut pour l'exercice où elle a été arrêtée, pas pour tous")
    if not attribuables and not non_attribuables:
        raise RefusMesure(
            MOTIF_ATTRIBUTION_VIDE,
            "aucune catégorie déclarée. Une déclaration vide n'est pas une "
            "déclaration que tout est attribuable — c'est une absence, et "
            "elle doit se dire comme telle")

    doubles = set(attribuables) & set(non_attribuables)
    if doubles:
        raise RefusMesure(
            MOTIF_CATEGORIE_DANS_LES_DEUX,
            f"{sorted(doubles)} figure(nt) des DEUX côtés. B66 d) admet "
            f"qu'une catégorie se partage — « certains » frais de "
            f"développement — mais elle doit alors être déclarée en DEUX "
            f"postes distincts et nommés, pas en un seul compté deux fois")

    for panier, contenu in (('attribuables', attribuables),
                            ('non attribuables', non_attribuables)):
        for categorie, montant in contenu.items():
            if montant < 0:
                raise RefusMesure(
                    'montant_negatif',
                    f"« {categorie} » vaut {montant} parmi les {panier} ; "
                    f"ce module attend des montants en valeur absolue")

    declaration = Attribution(
        attribuables=tuple(sorted(attribuables.items())),
        non_attribuables=tuple(sorted(non_attribuables.items())),
        actuaire_resp=actuaire_resp.strip(), arrete=arrete.strip())

    if total_remis is not None:
        somme = declaration.total_attribuable + declaration.total_non_attribuable
        if abs(somme - total_remis) > 0.005:
            raise RefusMesure(
                MOTIF_COUT_EVAPORE,
                f"la déclaration couvre {somme} alors que {total_remis} ont "
                f"été remis : {abs(total_remis - somme)} ne sont d'aucun "
                f"côté. Des charges qui s'évaporent gonflent le résultat "
                f"sans que rien ne le dise")
    return declaration


def resume(declaration: Attribution) -> str:
    """Ce qui a été déclaré, dit à un actuaire — et le critère avec.

    ⚠️ LE CRITÈRE EST PUBLIÉ AVEC LES MONTANTS, PAS AILLEURS. Une
    répartition sans la règle qui l'a guidée n'est pas vérifiable par un
    tiers : il lirait des chiffres sans savoir contre quoi les juger.
    """
    lignes = [
        f"ATTRIBUTION DES COÛTS (B65/B66) — arrêté {declaration.arrete}",
        f"  déclarée par {declaration.actuaire_resp}",
        "",
        f"  ATTRIBUABLES — {declaration.total_attribuable:.2f}",
    ]
    lignes += [f"      {c} : {m:.2f}" for c, m in declaration.attribuables]
    lignes += ["", ("  NON ATTRIBUABLES — "
                    f"{declaration.total_non_attribuable:.2f}")]
    lignes += [f"      {c} : {m:.2f}" for c, m in declaration.non_attribuables]
    lignes += ["", "  CRITÈRE APPLIQUÉ :", f"      {CRITERE}"]
    return '\n'.join(lignes)
