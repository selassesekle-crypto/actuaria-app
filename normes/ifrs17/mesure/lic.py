# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §59 b) : LE PASSIF AU TITRE DES SINISTRES SURVENUS
=============================================================================

§59 b), verbatim : « [l'entité] doit évaluer le passif au titre des sinistres
survenus pour le groupe de contrats d'assurance comme étant égal au montant
des FLUX DE TRÉSORERIE D'EXÉCUTION relatifs aux sinistres survenus,
conformément aux paragraphes 33 à 37 et B36 à B92. Cependant, l'entité n'est
pas tenue d'ajuster les flux de trésorerie futurs pour refléter la valeur
temps de l'argent et l'effet du risque financier si le versement […] est
attendu dans un délai n'excédant pas un an à compter de la DATE DU SINISTRE. »

⚠️⚠️ CE MODULE NE PROJETTE RIEN, ET C'EST UNE DÉCISION, PAS UNE LACUNE. La
charge ultime d'un triangle se projette par une méthode — Chain Ladder,
Mack, Bornhuetter-Ferguson, Cape Cod, Bootstrap — et LE CHOIX DE LA MÉTHODE
EST UN JUGEMENT ACTUARIEL, pas une lecture de la norme. Le module REÇOIT la
projection déclarée et signée, avec sa méthode nommée. Septième fois que ce
chantier répond à une décision d'entité par une déclaration plutôt que par
une devinette.

⚠️ ET IL N'IMPORTE PAS L'AGENT DE PROVISIONNEMENT. Deux raisons, la seconde
mesurée : un actuaire qui signe une réserve ne signe pas « ce que tel agent
avait sous la main » ; et dépendre de `direction_non_vie/` condamnerait tout
lot futur du chantier IFRS 17 à la gate non-vie de vingt-quatre minutes.

⚠️⚠️ CE QUE LES DONNÉES DISPONIBLES NE PERMETTENT PAS D'AFFIRMER. Le triangle
livré porte la mention « synthétique — déduit du jeu v2, CADENCES INVENTÉES ».
Une projection sur ces cadences rend UN NOMBRE, PAS UNE RÉSERVE. Elles
testent la plomberie ; elles ne disent rien de l'exactitude, et aucune
quantité de tests verts ne changera cela. Toute sortie de ce module porte
cette réserve tant que la source du triangle n'est pas attestée.

⚠️ ET LE §130 SERA COURT. Il demande le développement des sinistres « pour
autant que remonte le délai le plus long », dans la limite de dix ans. Le
triangle disponible porte TROIS années de survenance et TROIS de
développement. Le module publie ce qu'il a et NOMME la limite — un tableau
de trois colonnes présenté sans réserve laisserait croire à un historique
complet.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §59 b), §33 à §37, §130.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import (
    COMPARAISON_EGAL,
    est_renseigne,
    exiger_arrete_dans_le_contexte,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_AUCUNE_CELLULE = 'aucune_cellule_de_triangle'
MOTIF_TRIANGLE_INCOHERENT = 'paiements_superieurs_a_la_charge'
MOTIF_PROJECTION_NON_DECLAREE = 'projection_non_declaree'
MOTIF_PROJECTION_INFERIEURE = 'ultime_inferieur_a_la_charge_connue'
MOTIF_DISPENSE_NON_DECLAREE = 'dispense_59b_non_declaree'
MOTIF_ACTUALISATION_INCOHERENTE = 'actualisation_incoherente'

#: ⚠️ CE QUI ACCOMPAGNE TOUTE SORTIE TANT QUE LE TRIANGLE EST SYNTHÉTIQUE.
MOTIF_CADENCES_INVENTEES = (
    "⚠️ TRIANGLE À SOURCE NON ATTESTÉE — le jeu disponible porte la mention "
    "« synthétique, cadences inventées ». Une projection sur ces cadences "
    "rend UN NOMBRE, PAS UNE RÉSERVE : elle éprouve la plomberie, jamais "
    "l'exactitude. Aucun montant descendant de ce triangle n'est opposable "
    "tant que la source n'est pas attestée par l'actuaire signataire.")

#: ⚠️ LA LIMITE DU §130, NOMMÉE PLUTÔT QUE LAISSÉE DÉCOUVRIR.
MOTIF_130_COURT = (
    "⚠️ DÉVELOPPEMENT PARTIEL — §130 demande de remonter aussi loin que le "
    "délai le plus long de règlement, dans la limite de dix ans. Le triangle "
    "fourni n'en porte que {n}. Le tableau publié est donc COURT, et un "
    "lecteur qui l'ignorerait croirait à un historique complet.")


class Cellule(NamedTuple):
    """Une case de triangle : ce qui est OBSERVÉ, jamais projeté."""
    portefeuille:        str
    annee_survenance:    int
    annee_developpement: int
    paiements_cumules:   float
    charge_cumulee:      float


class Projection(NamedTuple):
    """La charge ultime, telle que l'actuaire la porte.

    ⚠️ `methode` EST OBLIGATOIRE ET NOMMÉE. Chain Ladder et Bornhuetter-
    Ferguson sur le même triangle ne donnent pas le même ultime ; publier un
    montant sans sa méthode le rend invérifiable.
    """
    ultime:        float
    methode:       str
    actuaire_resp: str
    arrete:        str


class PassifSinistres(NamedTuple):
    """Le LIC du §59 b). ⚠️ `motif` PORTE TOUTES LES RÉSERVES ACCUMULÉES."""
    charge_connue:       float   # observé : la charge cumulée
    paiements:           float   # observé
    provision_connue:    float   # charge connue - paiements
    ultime_declare:      float   # déclaré
    ibnr:                float   # ultime - charge connue
    lic_avant_risque:    float   # ultime - paiements
    actualisation_faite: bool
    motif:               str


def _controler(cellules) -> list:
    lot = list(cellules)
    if not lot:
        raise RefusMesure(
            MOTIF_AUCUNE_CELLULE,
            "aucune cellule de triangle. Un passif au titre des sinistres "
            "survenus calculé sur un triangle vide n'est pas nul — il "
            "n'existe pas, et rendre zéro serait la même faute qu'une gate "
            "rendant « Ran 0 tests » en sortant 0")
    for c in lot:
        if c.paiements_cumules > c.charge_cumulee + 0.02:
            raise RefusMesure(
                MOTIF_TRIANGLE_INCOHERENT,
                f"{c.portefeuille} survenance {c.annee_survenance} "
                f"développement {c.annee_developpement} : les paiements "
                f"cumulés ({c.paiements_cumules}) dépassent la charge "
                f"cumulée ({c.charge_cumulee}). La charge comprend les "
                f"paiements par définition ; l'inverse signale un triangle "
                f"mal construit ou deux conventions mélangées")
    return lot


def _derniers(lot) -> dict:
    """La dernière cellule connue de chaque (portefeuille, survenance).

    ⚠️ C'EST ELLE QUI PORTE L'OBSERVATION, pas la somme de la colonne : les
    cellules sont CUMULÉES, les additionner compterait chaque paiement
    autant de fois qu'il y a de développements.
    """
    der = {}
    for c in lot:
        cle = (c.portefeuille, c.annee_survenance)
        if cle not in der or c.annee_developpement > der[cle].annee_developpement:
            der[cle] = c
    return der


def declarer_projection(*, ultime: float, methode: str, actuaire_resp: str,
                        arrete: str) -> Projection:
    """Reçoit la charge ultime, ou REFUSE en disant ce qui manque."""
    if not est_renseigne(actuaire_resp):
        raise RefusMesure(
            MOTIF_PROJECTION_NON_DECLAREE,
            "aucun actuaire ne se porte garant de cette projection. Le §59 b) "
            "en fait un passif inscrit au bilan : elle engage quelqu'un, "
            "nommément")
    if not est_renseigne(methode):
        raise RefusMesure(
            MOTIF_PROJECTION_NON_DECLAREE,
            "la projection est fournie sans sa méthode. Chain Ladder et "
            "Bornhuetter-Ferguson sur le même triangle ne donnent pas le "
            "même ultime : un montant sans sa méthode est invérifiable")
    if not est_renseigne(arrete):
        raise RefusMesure(
            MOTIF_PROJECTION_NON_DECLAREE,
            "la projection est fournie sans son arrêté ; un ultime vaut pour "
            "une date d'observation, pas pour toutes")
    if ultime < 0:
        raise RefusMesure(
            'ultime_negatif',
            f"la charge ultime vaut {ultime}. Un passif au titre des "
            f"sinistres survenus négatif signalerait des recours excédant "
            f"la charge, ce qui se déclare autrement")
    return Projection(ultime=ultime, methode=methode.strip(),
                      actuaire_resp=actuaire_resp.strip(),
                      arrete=arrete.strip())


def passif_sinistres(cellules, projection: Projection, contexte, *,
                     source_attestee: bool = False,
                     dispense_59b: bool = False,
                     actualisation: float | None = None) -> PassifSinistres:
    """§59 b) — le passif, à partir de l'observé et d'un ultime déclaré.

    ⚠️ CE QUI EST OBSERVÉ ET CE QUI EST DÉCLARÉ NE SE MÉLANGENT PAS. La
    charge connue et les paiements viennent du triangle ; l'ultime vient de
    l'actuaire. L'IBNR est leur DIFFÉRENCE, et il hérite donc entièrement de
    l'incertitude du second.

    ⚠️ LA DISPENSE DU §59 b) S'EXERCE SUR DÉCLARATION, JAMAIS PAR DÉFAUT, et
    elle porte sur le délai « à compter de la DATE DU SINISTRE » — non sur
    une durée moyenne de portefeuille. Une moyenne est un PROXY : elle peut
    passer sous un an alors que la queue s'étale bien au-delà.
    """
    exiger_arrete_dans_le_contexte(
        arrete=projection.arrete, comparaison=COMPARAISON_EGAL,
        contexte=contexte, erreur=RefusMesure,
        objet="la projection du §59 b)")

    lot = _controler(cellules)
    der = _derniers(lot)
    charge = sum(c.charge_cumulee for c in der.values())
    payes = sum(c.paiements_cumules for c in der.values())

    if projection.ultime < charge - 0.02:
        raise RefusMesure(
            MOTIF_PROJECTION_INFERIEURE,
            f"l'ultime déclaré ({projection.ultime:.2f}) est INFÉRIEUR à la "
            f"charge déjà connue ({charge:.2f}). L'ultime est la charge "
            f"FINALE : il ne peut pas être plus petit que ce qui est déjà "
            f"survenu et évalué. Un IBNR négatif se déclare et se motive, il "
            f"ne se produit pas par accident")

    if dispense_59b:
        actualise, faite = 0.0, False
    elif actualisation is None:
        raise RefusMesure(
            MOTIF_DISPENSE_NON_DECLAREE,
            "ni actualisation fournie, ni dispense du §59 b) déclarée. Le "
            "§59 b) renvoie aux §33-37, donc au §36 : rendre un passif non "
            "actualisé sans le dire serait rendre un chiffre faux en "
            "silence. La dispense EXISTE — « délai n'excédant pas un an à "
            "compter de la date du sinistre » — mais elle s'exerce, elle ne "
            "se suppose pas")
    else:
        # ⚠️ L'ACTUALISATION DIMINUE, TOUJOURS. Un montant actualisé
        # supérieur au non actualisé signale une erreur de convention ou un
        # montant qui n'a rien à voir avec ce triangle. Sans ce contrôle, le
        # module RECOPIERAIT le paramètre de l'appelant sans jamais le
        # confronter à l'ultime déclaré — et rien ne le dirait.
        brut = projection.ultime - payes
        if actualisation > brut + 0.02:
            raise RefusMesure(
                MOTIF_ACTUALISATION_INCOHERENTE,
                f"le passif actualisé ({actualisation:.2f}) dépasse le "
                f"passif NON actualisé ({brut:.2f} = ultime "
                f"{projection.ultime:.2f} − paiements {payes:.2f}). "
                f"L'actualisation diminue : un montant plus grand signale "
                f"une convention inverse, ou un montant sans rapport avec ce "
                f"triangle")
        if actualisation < 0:
            raise RefusMesure(
                MOTIF_ACTUALISATION_INCOHERENTE,
                f"le passif actualisé vaut {actualisation}. Un passif au "
                f"titre des sinistres survenus négatif se déclare et se "
                f"motive, il ne se produit pas par accident")
        actualise, faite = actualisation, True

    reserves = []
    if not source_attestee:
        reserves.append(MOTIF_CADENCES_INVENTEES)
    if not faite:
        reserves.append(
            "actualisation NON appliquée sur déclaration de la dispense du "
            "§59 b). ⚠️ Cette dispense porte sur le délai à compter de la "
            "DATE DU SINISTRE, contrat par contrat — une durée moyenne de "
            "portefeuille n'en est qu'un proxy, et une moyenne sous un an "
            "peut recouvrir une queue bien plus longue.")

    return PassifSinistres(
        charge_connue=charge, paiements=payes,
        provision_connue=charge - payes,
        ultime_declare=projection.ultime,
        ibnr=projection.ultime - charge,
        lic_avant_risque=(actualise if faite
                          else projection.ultime - payes),
        actualisation_faite=faite,
        motif=' '.join(reserves))


def developpement_130(cellules, *, source_attestee: bool = False) -> dict:
    """§130 — le développement des sinistres, et sa limite NOMMÉE.

    ⚠️ TROIS ANNÉES NE SONT PAS DIX. §130 demande de remonter aussi loin que
    le délai le plus long de règlement, plafonné à dix ans. Publier trois
    colonnes sans le dire laisserait croire à un historique complet.
    """
    lot = _controler(cellules)
    annees = sorted({c.annee_survenance for c in lot})
    tableau = {}
    for c in lot:
        tableau.setdefault(c.annee_survenance, {})[c.annee_developpement] = (
            c.charge_cumulee)
    reserves = [MOTIF_130_COURT.format(n=len(annees))] if len(annees) < 10 else []
    if not source_attestee:
        reserves.append(MOTIF_CADENCES_INVENTEES)
    return {'annees_survenance': annees,
            'profondeur_disponible': len(annees),
            'profondeur_demandee_par_130': 10,
            'charge_cumulee': tableau,
            'motif': ' '.join(reserves)}


MOTIF_PONT_130_ROMPU = 'rapprochement_130_vers_100c_rompu'
MOTIF_PONT_130_INCOMPLET = 'rapprochement_130_sans_ses_termes'

#: ⚠️ MÊME BORNE QUE LES AUTRES ARTICULATIONS DU DÉPÔT : ce pont relie les
#: MÊMES montants lus par deux chemins. Seule l'erreur de virgule flottante
#: est tolérée.
TOLERANCE_PONT_130 = 1e-6

#: ⚠️⚠️ LA DISPENSE DU §130 LIBÈRE DU TABLEAU, PAS DU RAPPROCHEMENT — et
#: c'est toute la force de son « cependant ». Le texte : « L'entité N'EST PAS
#: TENUE de fournir d'informations sur le développement des demandes
#: d'indemnisation pour lesquels l'incertitude […] est habituellement levée
#: dans un délai d'un an. Elle doit CEPENDANT fournir un rapprochement entre
#: les informations communiquées sur le développement des demandes
#: d'indemnisation et la valeur comptable totale des groupes de contrats
#: d'assurance présentée en application du PARAGRAPHE 100 c). »
#:
#: ⚠️ Une plateforme non-vie en PAA est précisément celle qui sera tentée par
#: la dispense — beaucoup de branches se règlent dans l'année. Croire qu'elle
#: dispense aussi du rapprochement serait la lecture la plus coûteuse du
#: paragraphe.
DISPENSE_NE_LIBERE_PAS_DU_PONT = (
    "⚠️ LA DISPENSE DU §130 LIBÈRE DU TABLEAU DE DÉVELOPPEMENT, PAS DU "
    "RAPPROCHEMENT. Le texte dit « elle doit CEPENDANT fournir un "
    "rapprochement entre les informations communiquées sur le développement "
    "et la valeur comptable totale des groupes présentée en application du "
    "paragraphe 100 c) ». Une branche qui se règle dans l'année échappe au "
    "tableau ; son passif reste à rapprocher.")

#: ⚠️⚠️ CE PONT N'EST PAS UNE ÉGALITÉ, ET LES CONFONDRE SERAIT FAUX. §130
#: porte des montants NON ACTUALISÉS — « les estimations antérieures de leur
#: montant non actualisé » — quand §100 c) porte i) la valeur ACTUALISÉE des
#: flux futurs et ii) l'AJUSTEMENT POUR RISQUE. Deux termes les séparent, et
#: ce module ne peut calculer NI L'UN NI L'AUTRE : l'actualisation exigerait
#: la courbe et l'échéancier de règlement, l'ajustement pour risque est une
#: décision de l'entité (§37, sans méthode prescrite).
#:
#: ⚠️ ILS SE REÇOIVENT DONC DÉCLARÉS. Les calculer ici reviendrait à
#: fabriquer les deux chiffres qui font boucler le pont — un pont qui
#: fabrique ses propres appuis ne prouve rien.
PONT_A_DEUX_TERMES = (
    "⚠️ LE PONT DU §130 N'EST PAS UNE ÉGALITÉ : §130 porte des montants NON "
    "ACTUALISÉS, §100 c) porte la valeur ACTUALISÉE des flux futurs et "
    "l'ajustement pour risque. Deux termes les séparent — l'effet "
    "d'actualisation et l'ajustement pour risque — et ce module ne peut "
    "calculer ni l'un ni l'autre : le premier exigerait la courbe et "
    "l'échéancier de règlement, le second est une décision de l'entité que "
    "§37 laisse sans méthode prescrite. Ils se REÇOIVENT déclarés. Un pont "
    "qui fabriquerait ses propres appuis ne prouverait rien.")


def rapprocher_130_vers_100c(*, ultime_non_actualise: float,
                             paiements_cumules: float,
                             effet_actualisation, ajustement_risque,
                             lic_flux_futurs: float,
                             lic_ajustement_risque: float) -> str:
    """§130 — le « cependant » : le développement se rapproche du §100 c).

    ⚠️ LE CHEMIN, TERME À TERME :

        ultime non actualisé  −  paiements cumulés   = passif non actualisé
        passif non actualisé  −  effet d'actualisation = §100 c) i)
        ajustement pour risque                         = §100 c) ii)

    ⚠️ `effet_actualisation` EST POSITIF QUAND L'ACTUALISATION RÉDUIT LE
    PASSIF, ce qui est le cas ordinaire. Aucun signe n'est imposé au-delà :
    ce module ne pose pas une troisième convention là où le dépôt en a déjà
    payé deux contradictoires.
    """
    if effet_actualisation is None or ajustement_risque is None:
        manquants = [n for n, v in (('effet_actualisation',
                                     effet_actualisation),
                                    ('ajustement_risque', ajustement_risque))
                     if v is None]
        raise RefusMesure(
            MOTIF_PONT_130_INCOMPLET,
            f"le rapprochement du §130 est demandé sans {manquants}. "
            + PONT_A_DEUX_TERMES)

    non_actualise = ultime_non_actualise - paiements_cumules
    attendu_flux = non_actualise - effet_actualisation
    ecarts = []
    if abs(attendu_flux - lic_flux_futurs) > TOLERANCE_PONT_130:
        ecarts.append(
            f"§100 c) i) — flux futurs : le développement donne "
            f"{ultime_non_actualise:.2f} − {paiements_cumules:.2f} − "
            f"{effet_actualisation:.2f} = {attendu_flux:.2f}, le "
            f"rapprochement porte {lic_flux_futurs:.2f} "
            f"(écart {attendu_flux - lic_flux_futurs:+.2f})")
    if abs(ajustement_risque - lic_ajustement_risque) > TOLERANCE_PONT_130:
        ecarts.append(
            f"§100 c) ii) — ajustement pour risque : déclaré "
            f"{ajustement_risque:.2f}, rapprochement "
            f"{lic_ajustement_risque:.2f} "
            f"(écart {ajustement_risque - lic_ajustement_risque:+.2f})")
    if ecarts:
        raise RefusMesure(
            MOTIF_PONT_130_ROMPU,
            "le développement des sinistres et le passif du §100 c) ne se "
            "rapprochent pas — " + ' · '.join(ecarts) + ". "
            + PONT_A_DEUX_TERMES)

    return (f"§130 — le développement se rapproche du §100 c) : "
            f"{ultime_non_actualise:.2f} d'ultime non actualisé, moins "
            f"{paiements_cumules:.2f} de paiements, moins "
            f"{effet_actualisation:.2f} d'actualisation = "
            f"{lic_flux_futurs:.2f} de flux futurs, plus "
            f"{lic_ajustement_risque:.2f} d'ajustement pour risque. "
            + PONT_A_DEUX_TERMES + ' ' + DISPENSE_NE_LIBERE_PAS_DU_PONT)
