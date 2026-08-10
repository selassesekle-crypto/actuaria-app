# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : LA PORTE DE CONFIRMATION AVANT TOUT SCELLEMENT
=============================================================================

TROIS CHAMPS SCELLENT L'UNITÉ DE COMPTE — `portefeuille` (§14),
`date_emission` (§22) et `classe_profitabilite` (§16). §16, §22 et §53
s'apprécient tous « à la date de la création du groupe » : une erreur sur
l'un d'eux n'est pas rattrapable à la clôture suivante, elle est dans le
registre.

⚠️ POURQUOI CETTE PORTE N'EXISTE PAS POUR LES AUTRES CHAMPS. Une colonne mal
reconnue dans un triangle de sinistres produit un triangle visiblement faux,
que les diagnostics rattrapent. Une `date_emission` mal reconnue produit des
COHORTES fausses — et rien ne les rattrape, parce qu'elles sont scellées. La
dissymétrie du risque justifie la dissymétrie du traitement.

⚠️ ELLE NE SE DÉCLENCHE QUE SUR CE QUI A ÉTÉ INFÉRÉ. Une colonne nommée
`date_emission` n'a rien fait deviner : il n'y a rien à attester. Une colonne
`DT_SOUSCRIPTION` reconnue par synonyme, si — et un contrôleur qui demande
« comment savez-vous que ce n'est pas la date d'effet ? » doit obtenir un nom
et une date, pas un fichier de correspondances.

⚠️ QUI SIGNE N'EST PAS À INVENTER. A13 porte déjà `client_nom` et
`actuaire_resp` — « nom de l'actuaire responsable (signataire du rapport) » —
tous deux réellement employés. On reprend ce vocabulaire plutôt que d'en
créer un concurrent : c'est la même personne qui signe.

⚠️ ET UNE CONFIRMATION NE SE CORRIGE PAS. Elle est enregistrée dans un
registre append-only : on ne la modifie pas, on en ajoute une nouvelle. Le
registre porte donc la SUITE des confirmations, une par versement — ce qui
répond à « qui a scellé quoi, et quand » pour chaque arrêté, et non
seulement pour le premier.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803. §14, §16, §22, §53.
=============================================================================
"""

from typing import NamedTuple, Optional, Tuple

from core.arrete import Arrete, iso, lire as lire_arrete
from normes.ifrs17.socle.contrat import CHAMPS, champs_scelles


class Confirmation(NamedTuple):
    """Qui atteste quelle lecture, et quand.

    `correspondances` ne porte que les champs SCELLÉS qui ont été inférés :
    ce sont les seuls sur lesquels quelqu'un doit engager sa signature.
    """
    actuaire_resp:   str
    arrete:          str                        # 'AAAA-MM-JJ'
    correspondances: Tuple[Tuple[str, str], ...]   # (colonne, champ)


class RefusConfirmation(Exception):
    """Le scellement est refusé faute d'attestation."""

    def __init__(self, motif: str, message: str):
        self.motif = motif
        super().__init__(message)


MOTIF_SANS_SIGNATAIRE = 'SANS_SIGNATAIRE'
MOTIF_ARRETE_DISCORDANT = 'ARRETE_DISCORDANT'


def a_confirmer(rapport) -> Tuple:
    """Les correspondances qui exigent une signature avant scellement.

    ⚠️ LA RÈGLE VIT DANS `RapportInventaire.a_confirmer`, ET ELLE Y VIT SEULE.
    Cette fonction n'en tient pas une seconde copie : elle s'y rapporte. Deux
    définitions de « ce qui doit être confirmé » finiraient par diverger —
    c'est le motif que ce dépôt combat depuis les huit sources de taux.
    """
    return rapport.a_confirmer


def confirmer(rapport, actuaire_resp: str, arrete) -> Confirmation:
    """Fabrique la confirmation à partir de ce que le lecteur a compris.

    ⚠️ C'est le chemin normal, et le seul qui garantisse que l'attestation
    porte EXACTEMENT sur ce qui a été inféré. Un appelant qui construirait
    une `Confirmation` à la main devrait nommer lui-même le signataire —
    l'acte reste conscient, mais la couverture n'est plus vérifiée. La
    limite est réelle et vaut d'être dite : les lignes qui parviennent au
    registre sont déjà canoniques, l'information sur la façon dont elles
    ont été reconnues n'y est plus.
    """
    nom = str(actuaire_resp or '').strip()
    if not nom:
        raise RefusConfirmation(
            MOTIF_SANS_SIGNATAIRE,
            "Aucun signataire. Sceller l'unité de compte engage une "
            "responsabilité : §16, §22 et §53 s'apprécient à la date de "
            "création du groupe, et ne se corrigent plus ensuite. Nommez "
            "l'actuaire responsable.")
    arr = arrete if isinstance(arrete, Arrete) else lire_arrete(arrete)
    return Confirmation(
        actuaire_resp=nom,
        arrete=iso(arr),
        correspondances=tuple((c.colonne, c.champ)
                              for c in a_confirmer(rapport)))


def verifier(confirmation: Optional[Confirmation], arrete_iso: str) -> None:
    """Contrôle qu'un scellement peut avoir lieu. Lève sinon.

    ⚠️ LA PORTE EST AU SCELLEMENT, PAS À LA LECTURE. Un client dépose son
    inventaire, obtient son diagnostic et voit ses groupes dérivés sans
    signer quoi que ce soit — c'est l'exigence de facilité. La signature
    n'est demandée qu'au moment où l'irréversible commence.
    """
    if confirmation is None:
        raise RefusConfirmation(
            MOTIF_SANS_SIGNATAIRE,
            f"Scellement refusé : aucune confirmation. Les champs qui "
            f"fixent l'unité de compte — {', '.join(champs_scelles())} — "
            f"ne s'acceptent pas sur la seule foi d'un synonyme. Le lecteur "
            f"affiche ce qu'il a compris ; un actuaire responsable "
            f"l'atteste, une fois, avant que le registre n'existe. "
            f"Lecture et dérivation restent possibles sans signature.")
    if not str(confirmation.actuaire_resp or '').strip():
        raise RefusConfirmation(
            MOTIF_SANS_SIGNATAIRE,
            "Confirmation sans signataire — voir `confirmer`.")
    if confirmation.arrete != arrete_iso:
        raise RefusConfirmation(
            MOTIF_ARRETE_DISCORDANT,
            f"La confirmation porte l'arrêté {confirmation.arrete}, le "
            f"versement l'arrêté {arrete_iso}. Une attestation vaut pour le "
            f"scellement qu'elle accompagne, pas pour un autre.")


def resume_confirmation(confirmation: Confirmation) -> str:
    """Ce qu'un contrôleur lit pour savoir qui a scellé quoi."""
    lignes = [f"CONFIRMÉ par {confirmation.actuaire_resp} "
              f"au {confirmation.arrete}"]
    if not confirmation.correspondances:
        lignes.append("  aucune correspondance inférée : les champs scellés "
                      "portaient leur nom canonique.")
    for colonne, champ in confirmation.correspondances:
        lignes.append(f"  {colonne} lu comme « {champ} » — "
                      f"{CHAMPS[champ].libelle}")
    return '\n'.join(lignes)
