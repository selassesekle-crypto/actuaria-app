# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §55 : LE PASSIF AU TITRE DE LA COUVERTURE RESTANTE
=============================================================================

Le LRC en méthode d'affectation des primes, à la comptabilisation initiale
(§55 a) et aux arrêtés suivants (§55 b).

⚠️ CE MODULE N'ACTUALISE PAS, ET IL LE DIT PLUTÔT QUE DE SE TAIRE. Le §56
impose d'ajuster le LRC de la valeur temps de l'argent quand la composante
de financement est significative. Ce lot ne le construit pas. Une entrée qui
DÉCLARE un financement significatif est donc REFUSÉE, jamais mesurée sans
lui : rendre un LRC silencieusement faux serait pire que ne rien rendre.

⚠️ LES FRAIS D'ACQUISITION NE SONT PAS UN ACTIF SÉPARÉ. C'est le piège que
l'oracle ICA 5.2 attrape, et le seul qu'il attrape seul. Ils entrent dans le
LRC en DIMINUTION (§55 a) ii), et leur amortissement le RELÈVE au fur et à
mesure qu'il passe en charges (§55 b) iv). Une implémentation qui les
logerait dans une ligne d'actif distincte rendrait un LRC de 500 là où la
norme en veut 400 — avec un bilan qui équilibre quand même.

⚠️ ATTRIBUABLE N'EST PAS TOUT. Les frais NON attribuables au portefeuille
n'entrent ni dans le LRC, ni dans le résultat des activités d'assurance :
ils vont en « autres charges ». Les y oublier gonflerait le résultat
d'assurance de 55 sur l'exemple 5.2. Le socle ne porte pas encore cette
distinction — c'est l'appelant qui la fournit.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §55 à §59. Chaque paragraphe cité a été relu dans ce texte.
=============================================================================
"""

from typing import NamedTuple

MOTIF_SANS_ELIGIBILITE = 'eligibilite_paa_non_declaree'
MOTIF_FINANCEMENT_NON_CONSTRUIT = 'financement_significatif_non_construit'
MOTIF_DUREE_INVALIDE = 'duree_de_couverture_invalide'
MOTIF_MONTANT_NEGATIF = 'montant_negatif'


class RefusMesure(Exception):
    """Un refus motivé. ⚠️ JAMAIS UN DÉFAUT SILENCIEUX : rendre zéro, ou
    rendre un LRC non actualisé quand §56 s'applique, laisserait un chiffre
    faux entrer dans des états financiers."""

    def __init__(self, motif: str, message: str):
        self.motif = motif
        super().__init__(f'{message} [{motif}]')


#: Ce que porte `motif_resultat` quand la séparation n'a pas été fournie.
MOTIF_SEPARATION_NON_FOURNIE = (
    "séparation attribuable / non attribuable NON FOURNIE — le résultat "
    "n'est PAS établi. Elle relève d'une décision comptable de l'entité "
    "(§B65 énumère ce qui est attribuable), pas d'une règle calculable : ce "
    "module ne la devine pas. ⚠️ La supposer nulle gonflerait le résultat "
    "de tous les frais non attribuables — 55 sur l'exemple ICA 5.2.")


class Periode(NamedTuple):
    """Le résultat d'un arrêté, dans la présentation du §80.

    ⚠️ `resultat` N'EST PAS `service_result`. Le §80 ventile en DEUX postes,
    et les frais non attribuables vivent hors du résultat d'assurance.

    ⚠️ `autres_charges` ET `resultat` VALENT `None` QUAND LA SÉPARATION N'A
    PAS ÉTÉ FOURNIE, et `motif_resultat` dit pourquoi. C'est la leçon de
    `PAA_NON_ETABLI` dans le socle : « on ne sait pas » ne doit jamais
    ressembler à « zéro ». Rendre `resultat = service_result` par défaut
    aurait publié un total silencieusement gonflé.
    """
    revenue:          float           # produits des activités d'assurance
    charges_service:  float           # charges afférentes aux activités
    service_result:   float           # revenue - charges_service
    autres_charges:   float | None    # non attribuables — hors résultat
    resultat:         float | None    # service_result - autres_charges
    lrc_cloture:      float
    motif_resultat:   str = ''        # vide quand le résultat EST établi


def _controler(valeurs: dict, duree_ans: int, financement_significatif: bool,
               eligibilite_declaree: bool) -> None:
    """Les refus, tous groupés, AVANT le moindre calcul."""
    if not eligibilite_declaree:
        raise RefusMesure(
            MOTIF_SANS_ELIGIBILITE,
            "l'éligibilité à la PAA n'est pas déclarée. §53 s'apprécie à la "
            "création du groupe et le socle la scelle ; ce module ne la "
            "réévalue pas et ne la suppose pas")
    if financement_significatif:
        raise RefusMesure(
            MOTIF_FINANCEMENT_NON_CONSTRUIT,
            "le §56 impose d'ajuster le LRC de la valeur temps de l'argent "
            "quand la composante de financement est significative ; ce "
            "module ne le construit pas encore. Mesurer sans lui rendrait "
            "un LRC faux sans le dire")
    if duree_ans <= 0:
        raise RefusMesure(
            MOTIF_DUREE_INVALIDE,
            f"la durée de couverture vaut {duree_ans} ; l'affectation "
            f"prorata temporis exige une durée strictement positive")
    for nom, v in valeurs.items():
        if v < 0:
            raise RefusMesure(
                MOTIF_MONTANT_NEGATIF,
                f"« {nom} » vaut {v}. Ce module attend des montants en "
                f"valeur absolue et pose les signes lui-même ; un négatif "
                f"ici signale une convention d'appel divergente")


def lrc_initial(primes_recues: float, frais_acquisition: float, *,
                eligibilite_declaree: bool = False,
                financement_significatif: bool = False) -> float:
    """§55 a) — le LRC à la comptabilisation initiale.

    « Les primes reçues à la comptabilisation initiale, DIMINUÉES des flux
    de trésorerie liés aux frais d'acquisition à cette date. »

    ⚠️ LA SOUSTRACTION EST LE POINT. Les frais d'acquisition capitalisés ne
    forment pas un actif à côté du LRC : ils le réduisent.
    """
    _controler({'primes_recues': primes_recues,
                'frais_acquisition': frais_acquisition},
               1, financement_significatif, eligibilite_declaree)
    return primes_recues - frais_acquisition


def lrc_suivant(lrc_ouverture: float, *, primes_periode: float = 0.0,
                frais_acquisition_periode: float = 0.0,
                amortissement_frais_acquisition: float = 0.0,
                revenue_periode: float = 0.0,
                eligibilite_declaree: bool = False,
                financement_significatif: bool = False) -> float:
    """§55 b) — le LRC à un arrêté ultérieur.

    Le LRC d'ouverture, AUGMENTÉ des primes encaissées dans la période et de
    l'amortissement des frais d'acquisition passé en charges, DIMINUÉ des
    frais d'acquisition payés dans la période et des montants comptabilisés
    en produits pour les services rendus.

    ⚠️ L'AMORTISSEMENT AUGMENTE LE LRC, IL NE LE DIMINUE PAS. Il annule
    progressivement la soustraction faite au §55 a) : ce qui est passé en
    charges n'a plus à rester déduit du passif. C'est contre-intuitif, et
    c'est exactement ce que l'oracle 5.2 vérifie — 800 + 100 − 500 = 400.
    """
    _controler({'lrc_ouverture': lrc_ouverture,
                'primes_periode': primes_periode,
                'frais_acquisition_periode': frais_acquisition_periode,
                'amortissement_frais_acquisition':
                    amortissement_frais_acquisition,
                'revenue_periode': revenue_periode},
               1, financement_significatif, eligibilite_declaree)
    return (lrc_ouverture
            + primes_periode
            - frais_acquisition_periode
            + amortissement_frais_acquisition
            - revenue_periode)


def revenue_prorata_temporis(primes_attendues: float, duree_ans: int) -> float:
    """§55 b) i — les produits d'une période, sur l'écoulement du temps.

    ⚠️ C'EST LA BASE PAR DÉFAUT, PAS LA SEULE. Le §55 b) ii impose une
    autre base — le rythme attendu des décaissements — lorsque la libération
    du risque n'est pas uniforme dans le temps. Ce module ne construit que
    la première, et ne prétend pas décider laquelle s'applique.
    """
    if duree_ans <= 0:
        raise RefusMesure(
            MOTIF_DUREE_INVALIDE,
            f"la durée de couverture vaut {duree_ans}")
    return primes_attendues / duree_ans


def periode_annuelle(*, primes_attendues: float, duree_ans: int,
                     frais_acquisition_attribuables: float = 0.0,
                     frais_maintenance_attribuables: float = 0.0,
                     frais_non_attribuables: float | None = None,
                     sinistres_survenus: float = 0.0,
                     lrc_ouverture: float | None = None,
                     primes_periode: float | None = None,
                     eligibilite_declaree: bool = False,
                     financement_significatif: bool = False) -> Periode:
    """Un arrêté annuel complet, dans la présentation du §80.

    ⚠️ `lrc_ouverture` À `None` VAUT « PREMIER ARRÊTÉ » : le LRC d'ouverture
    est alors calculé par le §55 a), et les primes de la période valent la
    totalité des primes attendues sauf indication contraire. Distinguer les
    deux cas par une valeur par défaut plutôt que par un drapeau évite
    qu'un appelant oublie de dire lequel il veut.

    ⚠️ LES FRAIS NON ATTRIBUABLES NE TOUCHENT NI LE LRC NI LE RÉSULTAT
    D'ASSURANCE. Ils sortent en `autres_charges`.

    ⚠️ ET `None` N'EST PAS `0.0`. Ne pas fournir la séparation laisse le
    résultat NON ÉTABLI, motif à l'appui ; fournir `0.0` affirme qu'il n'y a
    aucun frais non attribuable. Confondre les deux publierait un résultat
    d'assurance gonflé sans que rien ne le signale.
    """
    premier = lrc_ouverture is None
    amortissement = frais_acquisition_attribuables / duree_ans
    revenue = revenue_prorata_temporis(primes_attendues, duree_ans)

    if premier:
        encaisse = (primes_attendues if primes_periode is None
                    else primes_periode)
        ouverture = lrc_initial(
            encaisse, frais_acquisition_attribuables,
            eligibilite_declaree=eligibilite_declaree,
            financement_significatif=financement_significatif)
        entrees = 0.0
    else:
        ouverture = lrc_ouverture
        entrees = primes_periode or 0.0

    cloture = lrc_suivant(
        ouverture, primes_periode=entrees,
        amortissement_frais_acquisition=amortissement,
        revenue_periode=revenue,
        eligibilite_declaree=eligibilite_declaree,
        financement_significatif=financement_significatif)

    charges = (frais_maintenance_attribuables + amortissement
               + sinistres_survenus)
    service_result = revenue - charges
    etabli = frais_non_attribuables is not None
    return Periode(
        revenue=revenue,
        charges_service=charges,
        service_result=service_result,
        autres_charges=frais_non_attribuables if etabli else None,
        resultat=(service_result - frais_non_attribuables) if etabli else None,
        lrc_cloture=cloture,
        motif_resultat='' if etabli else MOTIF_SEPARATION_NON_FOURNIE)
