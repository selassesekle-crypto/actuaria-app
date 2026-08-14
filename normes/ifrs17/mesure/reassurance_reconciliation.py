# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — RÉASSURANCE : LA RÉCONCILIATION TRAITÉ ↔ CONTRAT
=============================================================================

⚠️⚠️ CE MODULE N'IMPLÉMENTE AUCUN PARAGRAPHE, ET LE DIRE EST LE PREMIER
CONTRÔLE. C'est une vérification d'INTÉGRITÉ qui sert le §63 : la mesure des
contrats de réassurance détenus repose sur des primes cédées ventilées par
contrat, et si ces ventilations ne se rattachent pas aux traités qui les
engendrent, tout ce qui en descend est bâti sur du sable. Le registre le
rattache au §60-70A parce qu'il sert cette mesure — pas parce qu'un
paragraphe le prescrit.

⚠️ LA RÈGLE DU PRODUCTEUR, ET ELLE EST STRUCTURELLE : JAMAIS UNE ÉGALITÉ
STRICTE. `somme(cessions) + primes non ventilables = total`. Un traité en
excédent de sinistres CATASTROPHE protège le portefeuille contre un cumul
d'événements ; il ne répond pas contrat par contrat, et sa prime n'a donc
aucune ventilation à laquelle se rattacher. Forcer l'égalité obligerait à
inventer une clé de répartition.

⚠️⚠️ LE CONTRÔLE SE FAIT CELLULE PAR CELLULE, ET LA MESURE L'A IMPOSÉ. Sur
le portefeuille livré, un contrôle GLOBAL rend « écart 0,14 € » alors que
0,86 € de mouvement existe : 0,72 € s'annulent entre portefeuilles. Ici ce
n'est que de l'arrondi — mais le MÉCANISME est le même qui absorberait une
erreur d'affectation réelle, deux portefeuilles se compensant. Un total qui
boucle ne prouve pas que ses composantes bouclent. Le résultat publie donc
les DEUX écarts, net et absolu, et la compensation qui les sépare.

⚠️ LA BORNE N'EST PAS UN SEUIL ACCORDÉ, C'EST UNE BORNE DÉMONTRABLE. Chaque
prime cédée est arrondie au centime, donc chaque contrat porte au plus
0,005 € d'erreur, donc une cellule de n contrats en porte au plus
n × 0,005 €. Ce n'est pas un réglage : c'est le pire cas, et il ne rejette
jamais un arrondi légitime. Mesuré : borne 3,00 € contre 0,12 € observé au
pire sur RC_AUTO, soit trois ordres de grandeur sous la prime d'un traité.

⚠️ ET CE QUI N'EST PAS VENTILÉ DOIT ÊTRE DÉCLARÉ, JAMAIS DEVINÉ. Reconnaître
la chaîne « XS_CATASTROPHE » ferait dépendre un verdict d'une convention de
nommage du producteur — exactement la faute évitée au §69 b), où deviner la
base d'attachement faisait basculer treize traités. Un reliquat NON DÉCLARÉ
est un REFUS, pas une tolérance : sinon la borne absorberait en silence une
prime entière restée sans ventilation.
=============================================================================
"""

from collections import defaultdict
from typing import NamedTuple

from normes.ifrs17.mesure.lrc_paa import RefusMesure

#: Erreur maximale d'un arrondi au centime, par contrat. ⚠️ DÉMONTRÉE, PAS
#: RÉGLÉE : une valeur arrondie à deux décimales s'écarte d'au plus 0,005.
ARRONDI_MAX_PAR_CONTRAT = 0.005

MOTIF_ECART_NON_EXPLIQUE = 'ecart_non_explique_et_non_declare'
MOTIF_NON_VENTILABLE_INCONNU = 'traite_non_ventilable_inconnu'
MOTIF_NON_VENTILABLE_VENTILE = 'traite_declare_non_ventilable_mais_ventile'
MOTIF_CESSION_SANS_TRAITE = 'cession_sans_traite_correspondant'


class Traite63(NamedTuple):
    """Un traité, du côté qui engage."""
    traite_id:    str
    portefeuille: str
    type_traite:  str
    prime_cedee:  float


class Cession(NamedTuple):
    """Une prime cédée ventilée, du côté qui s'attribue."""
    id_contrat:   str
    portefeuille: str
    type_traite:  str
    prime_cedee:  float


class Cellule(NamedTuple):
    """Une maille (portefeuille × type), et ce qui s'y joue."""
    portefeuille:   str
    type_traite:    str
    prime_traites:  float
    prime_cessions: float
    nb_contrats:    int
    ecart:          float
    borne:          float

    @property
    def reconcilie(self) -> bool:
        return abs(self.ecart) <= self.borne


class Reconciliation(NamedTuple):
    """Le résultat, et ce qu'il refuse de laisser croire."""
    cellules:            tuple
    non_ventilable:      float
    ecart_net:           float
    ecart_absolu:        float
    compensation_masquee: float
    motif:               str


def _clef(x) -> tuple:
    return (x.portefeuille, x.type_traite)


def reconcilier(traites, cessions, *,
                traites_non_ventilables=frozenset()) -> Reconciliation:
    """Rattache les primes cédées ventilées aux traités qui les engendrent.

    ⚠️ `traites_non_ventilables` EST UNE DÉCLARATION, PAS UNE DÉDUCTION. Le
    module ne reconnaît aucun type par son nom : ce qui échappe à la
    ventilation doit être nommé traité par traité, et tout reliquat non
    déclaré fait REFUS.
    """
    traites = list(traites)
    cessions = list(cessions)
    if not traites:
        raise RefusMesure(
            'aucun_traite',
            "aucun traité fourni. Une réconciliation sur un ensemble vide "
            "bouclerait trivialement et ne prouverait rien")

    connus = {t.traite_id for t in traites}
    inconnus = sorted(set(traites_non_ventilables) - connus)
    if inconnus:
        raise RefusMesure(
            MOTIF_NON_VENTILABLE_INCONNU,
            f"{len(inconnus)} traité(s) déclaré(s) non ventilable(s) ne "
            f"figurent pas parmi les traités fournis : {inconnus}. Une "
            f"déclaration qui ne mord sur rien laisserait croire qu'un "
            f"reliquat est expliqué alors qu'il ne l'est pas")

    hors = {_clef(t) for t in traites if t.traite_id in traites_non_ventilables}
    non_ventilable = sum(t.prime_cedee for t in traites
                         if t.traite_id in traites_non_ventilables)

    par_traite, par_cession, contrats = (defaultdict(float),
                                         defaultdict(float),
                                         defaultdict(set))
    for t in traites:
        if t.traite_id not in traites_non_ventilables:
            par_traite[_clef(t)] += t.prime_cedee
    for c in cessions:
        par_cession[_clef(c)] += c.prime_cedee
        contrats[_clef(c)].add(c.id_contrat)

    #: ⚠️ SEULES LES MAILLES *ENTIÈREMENT* NON VENTILABLES SORTENT. Une maille
    #: qui mêle un traité déclaré et un traité ventilable reste rapprochée sur
    #: la part ventilable — l'exclure d'un bloc ferait échapper au contrôle la
    #: prime du traité qui, lui, doit se rattacher à des contrats.
    hors_pur = hors - set(par_traite)

    ventile_a_tort = sorted(k for k in hors_pur if par_cession.get(k, 0.0))
    if ventile_a_tort:
        raise RefusMesure(
            MOTIF_NON_VENTILABLE_VENTILE,
            f"{len(ventile_a_tort)} maille(s) n'ont que des traités déclarés "
            f"non ventilables et portent pourtant des primes ventilées : "
            f"{ventile_a_tort}. Une déclaration et une donnée qui se "
            f"contredisent ne peuvent pas être vraies toutes les deux, et "
            f"les départager relève de l'entité")

    orphelines = sorted(set(par_cession) - set(par_traite) - hors_pur)
    if orphelines:
        raise RefusMesure(
            MOTIF_CESSION_SANS_TRAITE,
            f"{len(orphelines)} maille(s) portent des primes cédées sans "
            f"aucun traité correspondant : {orphelines}. Une prime cédée à "
            f"personne n'est pas une cession")

    cellules, non_expliquees = [], []
    for k in sorted((set(par_traite) | set(par_cession)) - hors_pur):
        n = len(contrats.get(k, ()))
        cel = Cellule(k[0], k[1], par_traite.get(k, 0.0),
                      par_cession.get(k, 0.0), n,
                      par_traite.get(k, 0.0) - par_cession.get(k, 0.0),
                      n * ARRONDI_MAX_PAR_CONTRAT)
        cellules.append(cel)
        if not cel.reconcilie:
            non_expliquees.append(cel)

    if non_expliquees:
        detail = " · ".join(
            f"{c.portefeuille}/{c.type_traite} : écart {c.ecart:,.2f} pour "
            f"une borne d'arrondi de {c.borne:,.2f} sur {c.nb_contrats} "
            f"contrat(s)" for c in non_expliquees)
        raise RefusMesure(
            MOTIF_ECART_NON_EXPLIQUE,
            f"{len(non_expliquees)} maille(s) ne se réconcilient pas, et "
            f"aucun traité ne les déclare non ventilables : {detail}. La "
            f"borne ne couvre QUE l'arrondi au centime ; la dépasser signale "
            f"une prime restée sans ventilation, et l'absorber en silence "
            f"laisserait la mesure du §63 reposer sur des flux faux")

    net = sum(c.ecart for c in cellules)
    absolu = sum(abs(c.ecart) for c in cellules)
    return Reconciliation(
        cellules=tuple(cellules), non_ventilable=non_ventilable,
        ecart_net=net, ecart_absolu=absolu,
        compensation_masquee=absolu - abs(net),
        motif=_motif(len(cellules), non_ventilable, absolu - abs(net)))


def _motif(nb: int, non_ventilable: float, masquee: float) -> str:
    """Ce que la réconciliation établit, et ce qu'elle n'établit pas."""
    phrase = (f"{nb} maille(s) (portefeuille × type) rapprochées une à une, "
              f"chacune sous sa propre borne d'arrondi. ⚠️ LE CONTRÔLE EST "
              f"CELLULAIRE ET NON GLOBAL : un total qui boucle ne prouve pas "
              f"que ses composantes bouclent, et sur ce jeu la compensation "
              f"entre mailles masque {masquee:,.2f} € d'écart à un contrôle "
              f"global.")
    if non_ventilable:
        return phrase + (
            f" {non_ventilable:,.2f} € de primes DÉCLARÉES non ventilables "
            f"sont exclues du rapprochement : elles ne sont pas réconciliées, "
            f"elles sont mises de côté, et aucun contrat ne les porte.")
    return phrase + (
        " Aucune prime n'est déclarée non ventilable : la totalité des "
        "primes de traité se rattache à des contrats.")
