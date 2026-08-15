# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §61 et §62 : GROUPER ET DATER LA RÉASSURANCE DÉTENUE
=============================================================================

§61 — « L'entité doit diviser les portefeuilles de contrats de réassurance
détenus CONFORMÉMENT AUX PARAGRAPHES 14 À 24, toutefois les références faites
dans ces paragraphes aux contrats déficitaires sont remplacées par des
références aux contrats donnant lieu à un PROFIT NET au moment de la
comptabilisation initiale. Pour certains contrats de réassurance détenus,
l'application des paragraphes 14 à 24 se traduira par la constitution d'un
groupe composé D'UN SEUL CONTRAT. »

§62 — « PLUTÔT QUE D'APPLIQUER LE PARAGRAPHE 25 », l'entité comptabilise un
groupe cédé à la PREMIÈRE des deux dates : a) le début de la période de
couverture du groupe cédé ; b) la date à laquelle elle comptabilise un groupe
sous-jacent DÉFICITAIRE en application du §25 c), SI elle a conclu au plus
tard à cette date le contrat de réassurance correspondant.

§62A — « NONOBSTANT LE PARAGRAPHE 62 a) », l'entité doit REPORTER la
comptabilisation d'un groupe fournissant une COUVERTURE PROPORTIONNELLE
jusqu'à la comptabilisation initiale de tout contrat sous-jacent, si cette
date est postérieure au début de la couverture cédée.

⚠️⚠️ DEUX DÉPENDANCES DIFFÉRENTES, ET LES CONFONDRE ÉTAIT MON ERREUR. Le
périmètre publié disait que « leur classement ET leur date reposent sur le
caractère déficitaire du sous-jacent ». C'est vrai de la DATE, faux du
CLASSEMENT :

  · §61 classe sur le PROFIT NET DU CONTRAT CÉDÉ lui-même — sa position
    propre, primes cédées contre recouvrements attendus ;
  · §62 b) date sur le DÉFICIT DU SOUS-JACENT — une tout autre grandeur.

Le panier des contrats déficitaires n'entre donc QUE par le §62 b).

⚠️⚠️ ET IL Y ENTRE SOUS RÉSERVE : LE PANIER COMPLET DU §47 EST REFUSÉ ICI.
Trois paniers existent (voir `socle.errata_donnees`), et le plus complet —
747 contrats — descend d'une déclaration d'ajustement pour risque en statut
`A_REMPLACER`. L'employer comme source de datation ferait hériter la date de
comptabilisation d'une déclaration non signée PAR UNE PORTE DÉROBÉE : le
statut n'apparaîtrait nulle part dans le résultat. Le module exige donc le
panier 552, qui ne dépend d'aucune déclaration, et refuse le 747 tant que la
sienne n'est pas signée.

⚠️⚠️ ET SOUS PAA, UN PANIER EN SORTIE NETTE RENVERSE UNE PRÉSOMPTION, IL NE
REND PAS UN VERDICT. §18 : « l'entité doit SUPPOSER qu'aucun des contrats du
portefeuille n'est déficitaire au moment de la comptabilisation initiale, À
MOINS QUE les faits et les circonstances n'indiquent le contraire. » Un
panier en sortie nette EST un tel fait — la date du §62 b) est donc bien
ouverte — mais son STATUT diffère de celui d'un verdict rendu en modèle
général. Un commissaire aux comptes relèvera la différence, et le motif la
porte plutôt que de la laisser deviner.

⚠️ CE QUE CE MODULE NE CALCULE PAS : la position nette du §61. Elle se compare
sur des FLUX D'EXÉCUTION, donc actualisés et ajustés du risque (§32 a)). Une
comparaison brute « recouvrements attendus contre primes cédées » est un
INDICATEUR, pas le critère — la même confusion que le panier livré à 249. Le
module reçoit donc la position, et exige qu'on lui dise ce qu'elle contient.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §61, §62, §62A, §14 à §25, §16, §18, §32 a).
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.declaration import est_renseigne
from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.socle.errata_donnees import (
    DECLARATION_CONVENTION,
    DECLARATION_COURBE,
    DECLARATION_PRIME_ILLIQUIDITE,
    DECLARATIONS_DU_TAUX_36,
    ECUEIL_TAUX_INCOMPLET,
    PANIER_AVEC_FRAIS_GESTION,
    PANIER_COMPLET_47,
    PANIER_COMPLET_47_ACTUALISE,
    PANIER_LIVRE,
    reserve_du_panier,
)

#: §61 — les trois classes du §16, avec la substitution du §61.
CLASSE_PROFIT_NET = 'PROFIT_NET_A_L_ORIGINE'
CLASSE_SANS_POSSIBILITE = 'SANS_POSSIBILITE_IMPORTANTE_DE_PROFIT_NET'
CLASSE_AUTRES = 'AUTRES'
CLASSE_NON_ETABLIE = 'NON_ETABLIE'
CLASSES_61 = (CLASSE_PROFIT_NET, CLASSE_SANS_POSSIBILITE, CLASSE_AUTRES,
              CLASSE_NON_ETABLIE)

#: §62 — d'où vient la date retenue, ce qui n'est pas la même chose que la date.
ORIGINE_62A_REPORT = 'REPORT_62A_COUVERTURE_PROPORTIONNELLE'
ORIGINE_62A_DEBUT_COUVERTURE = 'DEBUT_COUVERTURE_CEDEE'
ORIGINE_62B_DEFICIT_SOUS_JACENT = 'DEFICIT_SOUS_JACENT_25C'

#: ⚠️⚠️ DEUX PANIERS ADMIS, ET ILS NE LE SONT PAS AU MÊME TITRE. Le panier
#: COMPLET ACTUALISÉ est le seul complet au sens du §47 : il est PRÉFÉRÉ, mais
#: il exige les TROIS déclarations du taux §36 — la courbe sans risque, la
#: prime d'illiquidité et la convention. Le 552 reste admis FAUTE DE
#: MIEUX, avec sa réserve — le refuser supprimerait une date que la norme
#: exige, et un refus qui supprime une obligation est pire que le défaut
#: qu'il évite.
PANIER_PREFERE_62B = PANIER_COMPLET_47_ACTUALISE
PANIER_ADMIS_FAUTE_DE_MIEUX_62B = PANIER_AVEC_FRAIS_GESTION
PANIERS_ADMIS_62B = (PANIER_PREFERE_62B, PANIER_ADMIS_FAUTE_DE_MIEUX_62B)

MOTIF_PANIER_REFUSE = 'panier_du_deficit_refuse_pour_dater'
MOTIF_POSITION_NON_QUALIFIEE = 'position_nette_non_qualifiee'
MOTIF_ACTUALISATION_NON_DECLAREE = 'declarations_du_taux_36_incompletes'

#: ⚠️ CE QUE §18 CHANGE AU STATUT, ET QU'UN AGRÉGAT NE DOIT PAS PERDRE.
RESERVE_18_PAA = (
    "⚠️ SOUS PAA, CE DÉCLENCHEMENT RENVERSE UNE PRÉSOMPTION, IL NE REND PAS "
    "UN VERDICT. §18 impose de SUPPOSER qu'aucun contrat n'est déficitaire à "
    "l'origine « à moins que les faits et les circonstances n'indiquent le "
    "contraire ». Un panier en sortie nette EST un tel fait et ouvre bien la "
    "date du §62 b) ; mais il ne vaut pas le verdict qu'un calcul de flux "
    "d'exécution rend en modèle général, et la différence se documente.")


class Classement61(NamedTuple):
    """La classe du §61, et ce sur quoi elle a été prononcée."""
    classe: str
    motif:  str


class Comptabilisation62(NamedTuple):
    """La date du §62, son origine, et la réserve qu'elle porte."""
    date:    object
    origine: str
    motif:   str


def classe_61(*, position_nette: float, panier_de_la_position: str,
              possibilite_importante_declaree: str = '') -> Classement61:
    """§61 — le classement, avec le critère INVERSÉ du §16.

    ⚠️ LA SUBSTITUTION EST LE TOUT DU §61 : là où §16 sépare les contrats
    DÉFICITAIRES, §61 sépare ceux donnant lieu à un PROFIT NET. Même
    agrégation, critère retourné — et §61 admet explicitement qu'un groupe
    puisse ne compter qu'un seul contrat.

    ⚠️ ET LA CLASSE b) N'EST PAS CALCULABLE. « Aucune possibilité IMPORTANTE
    de donner lieu à un profit net par la suite » est un jugement, au même
    titre que §54 et §69 a) : sans déclaration, la classe reste
    `NON_ETABLIE` plutôt que de tomber par défaut dans `AUTRES`, ce qui
    affirmerait un examen qui n'a pas eu lieu.
    """
    if not est_renseigne(panier_de_la_position):
        raise RefusMesure(
            MOTIF_POSITION_NON_QUALIFIEE,
            f"la position nette vaut {position_nette} mais son panier n'est "
            f"pas qualifié (reçu {panier_de_la_position!r}). §61 renvoie au "
            f"§16, dont le critère se prononce sur des FLUX D'EXÉCUTION — "
            f"actualisés et ajustés du risque par §32 a). Une comparaison "
            f"brute des recouvrements aux primes cédées est un indicateur, "
            f"pas le critère : le panier livré à 249 contrats a coûté cette "
            f"confusion, et elle ne se répète pas ici")

    if position_nette > 0:
        return Classement61(CLASSE_PROFIT_NET, (
            f"position nette de {position_nette:,.2f} en faveur de l'entité "
            f"à la comptabilisation initiale, sur le panier "
            f"« {panier_de_la_position} ». §61 substitue le PROFIT NET au "
            f"caractère déficitaire du §16 a) : c'est ce groupe-ci qui se "
            f"sépare, et §61 admet qu'il ne compte qu'un seul contrat."))

    if est_renseigne(possibilite_importante_declaree):
        return Classement61(CLASSE_SANS_POSSIBILITE, (
            f"position nette de {position_nette:,.2f}, et l'absence de "
            f"possibilité importante de profit net ultérieur est DÉCLARÉE : "
            f"« {possibilite_importante_declaree} ». ⚠️ Cette appréciation "
            f"engage l'entité, pas ce code — « importante » n'a aucun seuil "
            f"dans le texte."))

    return Classement61(CLASSE_NON_ETABLIE, (
        f"position nette de {position_nette:,.2f}, donc §16 a) substitué est "
        f"fermé ; mais §16 b) demande s'il existe « une possibilité "
        f"IMPORTANTE » de profit net ultérieur, et rien ne le déclare. "
        f"Classer en AUTRES par défaut affirmerait un examen qui n'a pas eu "
        f"lieu — c'est la leçon de `NON_ELIGIBLE`, et elle vaut ici."))


def _verifier_panier_62b(panier: str, courbe: str,
                         prime_illiquidite: str, convention: str) -> str:
    """Le panier admis pour dater, et la réserve qu'il fait descendre.

    ⚠️ REFUSER LES DEUX PANIERS IMPARFAITS SUPPRIMERAIT UNE DATE QUE LA NORME
    EXIGE. §62 impose de comptabiliser à la PREMIÈRE des deux dates ; fermer
    le b) faute de panier complet retiendrait systématiquement le a), donc
    une date potentiellement trop tardive. Un refus qui supprime une
    obligation est pire que le défaut qu'il évite — d'où l'admission du 552
    SOUS RÉSERVE, plutôt que son rejet.
    """
    if panier == PANIER_COMPLET_47:
        raise RefusMesure(
            MOTIF_PANIER_REFUSE,
            "le panier complet du §47 (747 contrats) est REFUSÉ comme source "
            "de datation : il descend d'une déclaration d'ajustement pour "
            "risque en statut A_REMPLACER, que `declaration.est_renseigne` "
            "refuse. L'employer ferait hériter la date de comptabilisation "
            "d'une déclaration non signée par une porte dérobée — le statut "
            "n'apparaîtrait nulle part dans le résultat. ⚠️ Et il n'est pas "
            "actualisé non plus : §32 a) ii) y reste omis. Employer "
            f"« {PANIER_PREFERE_62B} » avec sa courbe et sa convention, ou "
            f"« {PANIER_ADMIS_FAUTE_DE_MIEUX_62B} » sous sa réserve.")
    if panier == PANIER_LIVRE:
        raise RefusMesure(
            MOTIF_PANIER_REFUSE,
            "le panier livré (249 contrats) est REFUSÉ comme source de "
            "datation : il omet les frais de gestion des sinistres et "
            "l'ajustement au titre du risque non financier, que §32 a) range "
            "dans les flux d'exécution. Erratum E1.")
    if panier not in PANIERS_ADMIS_62B:
        raise RefusMesure(
            MOTIF_PANIER_REFUSE,
            f"panier {panier!r} inconnu. §62 b) date sur un groupe "
            f"sous-jacent DÉFICITAIRE : sans savoir de quel panier ce "
            f"caractère est tiré, la date n'est pas traçable. Paniers "
            f"admis : {PANIERS_ADMIS_62B}")

    if panier == PANIER_PREFERE_62B:
        #: ⚠️ DEUX DÉCLARATIONS, PAS UNE. Ce n'est pas seulement la COURBE
        #: qui se déclare (§36 b), c'est aussi CE QU'ON ACTUALISE : mesuré,
        #: la convention seule déplace 23 % de l'effet qu'elle mesure.
        libelle_illiquidite = (
            f"{DECLARATION_PRIME_ILLIQUIDITE} (la prime d'illiquidité du "
            f"§36 a) et de B80, AVEC SA TECHNIQUE)")
        attendues = (
            (f'{DECLARATION_COURBE} (la courbe sans risque du §36 b))',
             courbe),
            (libelle_illiquidite, prime_illiquidite),
            (f"{DECLARATION_CONVENTION} (ce qu'on actualise)", convention),
        )
        manquants = [nom for nom, v in attendues if not est_renseigne(v)]
        if manquants:
            raise RefusMesure(
                MOTIF_ACTUALISATION_NON_DECLAREE,
                f"le panier complet actualisé est employé mais "
                f"{len(manquants)} des {len(DECLARATIONS_DU_TAUX_36)} "
                f"déclarations du taux §36 manque(nt) : "
                f"{' · '.join(manquants)}. "
                f"⚠️⚠️ LES TROIS SE DÉCLARENT SÉPARÉMENT, ET CE N'EST PAS UNE "
                f"formalité : fondre la prime d'illiquidité dans « la "
                f"courbe » la rendrait invisible, et un terme absorbé dans "
                f"un mot global ne se rouvre pas. Ce module en a fait la "
                f"preuve — il a exigé pendant un temps qu'on « retraite » "
                f"l'ajustement pour risque de crédit, à l'envers, et il a "
                f"fallu une source externe pour le voir. "
                f"⚠️ LA COURBE EIOPA SANS VA NE SUFFIT PAS : il lui manque la "
                f"prime d'illiquidité que §36 a) exige — « les "
                f"caractéristiques de liquidité des contrats d'assurance » — "
                f"et que B80 construit par voie ascendante. Son ajustement "
                f"pour risque de crédit, lui, est DÉJÀ conforme : il retire "
                f"de la courbe swap un facteur qui influe sur les prix de "
                f"marché mais pas sur les flux d'assurance, ce que §36 c) "
                f"impose d'exclure. "
                f"⚠️ ET LA CONVENTION N'EST PAS MOINS UNE DÉCISION : mesuré à "
                f"4 % sur le portefeuille livré, quatre conventions également "
                f"défendables donnent 521, 539, 541 et 568 déficitaires — 47 "
                f"contrats d'écart pour un effet d'actualisation de 208, soit "
                f"23 % de l'effet qu'elles mesurent. "
                + ECUEIL_TAUX_INCOMPLET)
        return ''

    return reserve_du_panier(PANIER_ADMIS_FAUTE_DE_MIEUX_62B)


def date_comptabilisation_62(*, debut_couverture_cedee,
                             couverture_proportionnelle: bool,
                             premiere_compta_sous_jacent=None,
                             date_deficit_sous_jacent=None,
                             traite_conclu_au_plus_tard: bool = False,
                             panier_du_deficit: str = '',
                             courbe_declaree: str = '',
                             prime_illiquidite_declaree: str = '',
                             convention_actualisation_declaree: str = '',
                             sous_jacent_en_paa: bool = False
                             ) -> Comptabilisation62:
    """§62, §62A — la date de comptabilisation du groupe cédé.

    ⚠️ §62A PRIME SUR §62 a), ET IL DIT « NONOBSTANT ». Pour une couverture
    PROPORTIONNELLE, la date du début de couverture cédée est REPORTÉE à la
    comptabilisation initiale d'un contrat sous-jacent quand celle-ci est
    postérieure. Mesuré sur les treize traités livrés : six quote-parts sont
    concernées, sept excédents ne le sont pas.

    ⚠️ DEUX PANIERS SONT ADMIS, ET PAS AU MÊME TITRE. Le complet actualisé
    est PRÉFÉRÉ et exige courbe et convention déclarées ; le 552 reste admis
    FAUTE DE MIEUX, sa réserve descendant avec la date.
    """
    if date_deficit_sous_jacent is not None:
        reserve = _verifier_panier_62b(panier_du_deficit, courbe_declaree,
                                       prime_illiquidite_declaree,
                                       convention_actualisation_declaree)
    else:
        reserve = ''

    candidates = []
    if couverture_proportionnelle and premiere_compta_sous_jacent is not None \
            and premiere_compta_sous_jacent > debut_couverture_cedee:
        candidates.append((premiere_compta_sous_jacent, ORIGINE_62A_REPORT))
    else:
        candidates.append((debut_couverture_cedee,
                           ORIGINE_62A_DEBUT_COUVERTURE))

    if date_deficit_sous_jacent is not None and traite_conclu_au_plus_tard:
        candidates.append((date_deficit_sous_jacent,
                           ORIGINE_62B_DEFICIT_SOUS_JACENT))

    date, origine = min(candidates, key=lambda c: c[0])
    return Comptabilisation62(
        date, origine,
        _motif_62(origine, sous_jacent_en_paa, panier_du_deficit, reserve))


def _motif_62(origine: str, sous_jacent_en_paa: bool,
              panier: str = '', reserve: str = '') -> str:
    """Ce que la date établit, et sous quelle réserve.

    ⚠️ LA RÉSERVE DU PANIER NE DESCEND QUE SI LE PANIER A SERVI. Elle est
    attachée au §62 b) ; l'accrocher à une date retenue par le §62 a) ou le
    §62A ferait porter à un résultat une réserve qui ne le concerne pas, et
    une réserve hors sujet finit par ne plus être lue.
    """
    if origine == ORIGINE_62A_REPORT:
        return (
            "§62A appliqué : la couverture est PROPORTIONNELLE et la "
            "comptabilisation initiale du sous-jacent est postérieure au "
            "début de la couverture cédée. §62A dit « NONOBSTANT le §62 a) » "
            "— il ne concourt pas avec lui, il l'écarte.")
    if origine == ORIGINE_62B_DEFICIT_SOUS_JACENT:
        base = ("§62 b) retenu : le groupe sous-jacent est devenu "
                "déficitaire avant le début de la couverture cédée, et le "
                "traité était conclu à cette date. Caractère déficitaire "
                f"tiré du panier « {panier} ».")
        if reserve:
            base += ' ' + reserve
        if sous_jacent_en_paa:
            base += ' ' + RESERVE_18_PAA
        return base
    return ("§62 a) retenu : le début de la période de couverture cédée est "
            "la première des dates applicables.")
