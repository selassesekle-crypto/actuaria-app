# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §78-79 : LA PRÉSENTATION AU BILAN
=============================================================================

§78, verbatim : « L'entité doit présenter SÉPARÉMENT dans l'état de la
situation financière la valeur comptable : a) des PORTEFEUILLES de contrats
d'assurance émis qui sont des ACTIFS ; b) des portefeuilles de contrats
d'assurance émis qui sont des PASSIFS ; c) des portefeuilles de contrats de
réassurance détenus qui sont des actifs ; et d) […] qui sont des passifs. »

⚠️⚠️ LE PIÈGE EST LE MOT « SÉPARÉMENT », ET IL COÛTE CHER. Un portefeuille
dont la valeur comptable nette est négative EST UN ACTIF, et il ne se
compense PAS avec les portefeuilles passifs. Compenser donnerait un bilan
dont le total est juste et dont les deux lignes sont fausses — une erreur
qu'aucun contrôle d'équilibre ne verrait, puisque l'équilibre tient. Ce
module refuse la compensation et un test montre l'écart qu'elle produit.

⚠️ ET L'UNITÉ EST LE PORTEFEUILLE, PAS LE GROUPE. §78 le dit quatre fois. La
compensation À L'INTÉRIEUR d'un portefeuille est donc normale et voulue ; ce
qui est interdit, c'est de la franchir. Le socle constitue les groupes et
connaît leur portefeuille : c'est l'appelant qui les apparie, ce module ne
va rien y chercher.

⚠️ RÉASSURANCE DÉTENUE : §78 c) et d) l'exigent séparément, et elle n'est
PAS construite (voir le périmètre, §60-70A). Ce module ne rend donc que les
deux premières lignes, et il le DIT dans son résultat — un bilan à deux
lignes présenté comme complet laisserait croire qu'il n'y a pas de
réassurance, ce qui n'est pas la même chose que ne pas la mesurer.

⚠️ §79 — L'ACTIF DE FRAIS D'ACQUISITION S'INCORPORE. « L'entité doit
incorporer dans la valeur comptable de chacun des portefeuilles […] tout
actif comptabilisé, en application du paragraphe 28B, au titre des flux de
trésorerie liés aux frais d'acquisition ». Il ne se présente donc pas sur une
ligne à lui — même règle qu'au §55 a), où ces frais diminuent le passif au
lieu de former un actif séparé.

AUCUN ORACLE : aucune source publiée disponible ne chiffre un bilan IFRS 17
par portefeuille. Les garanties de ce module sont internes.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §78 et §79.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.lrc_paa import RefusMesure

MOTIF_AUCUN_SOLDE = 'aucun_solde_fourni'
MOTIF_PORTEFEUILLE_VIDE = 'portefeuille_sans_nom'

#: ⚠️ CE QUE LE BILAN RENDU NE COUVRE PAS, ET QUI DOIT L'ACCOMPAGNER. §78 c)
#: et d) exigent les portefeuilles de réassurance détenue, séparément. Ils ne
#: sont pas construits. Un état à deux lignes présenté comme complet ferait
#: lire « pas de réassurance » là où il faut lire « réassurance non mesurée ».
MOTIF_REASSURANCE_ABSENTE = (
    "état de la situation financière PARTIEL — §78 c) et d) exigent de "
    "présenter séparément les portefeuilles de réassurance DÉTENUE qui sont "
    "des actifs et ceux qui sont des passifs. La réassurance détenue "
    "(§60-70A) n'est pas construite : ces deux lignes sont ABSENTES, elles "
    "ne valent pas zéro. ⚠️ Un état à deux lignes lu comme complet ferait "
    "conclure qu'il n'y a pas de réassurance, ce qui n'est pas la même "
    "chose que ne pas la mesurer.")


class SoldeGroupe(NamedTuple):
    """La valeur comptable d'un groupe, et le portefeuille dont il relève.

    ⚠️ `valeur_comptable` EST SIGNÉE : positive pour un passif, négative
    pour un actif. C'est la convention du §55 tenue par `lrc_paa`, et un
    LRC négatif est un cas réel — une créance de prime non encaissée.
    """
    portefeuille:     str
    cle_groupe:       str
    valeur_comptable: float


class PosteBilan(NamedTuple):
    """Un portefeuille, sa valeur ABSOLUE, et de quel côté il tombe."""
    portefeuille: str
    valeur:       float   # toujours positive : le côté est porté par `est_actif`
    est_actif:    bool
    nb_groupes:   int


class Bilan(NamedTuple):
    """L'état du §78. ⚠️ Les deux totaux ne se compensent JAMAIS."""
    actifs:            tuple   # (PosteBilan, ...) — §78 a)
    passifs:           tuple   # (PosteBilan, ...) — §78 b)
    total_actifs:      float
    total_passifs:     float
    nb_portefeuilles:  int
    motif:             str


def etat_situation_financiere(soldes) -> Bilan:
    """§78 — les portefeuilles, séparés par côté, jamais compensés.

    ⚠️ LA COMPENSATION INTERNE AU PORTEFEUILLE EST VOULUE ; CELLE QUI LE
    FRANCHIT EST INTERDITE. §78 nomme le portefeuille quatre fois : c'est
    l'unité de présentation. Additionner les groupes d'un même portefeuille
    est donc juste ; additionner deux portefeuilles de côtés opposés
    donnerait un bilan dont le total est bon et dont les deux lignes sont
    fausses.
    """
    lot = list(soldes)
    if not lot:
        raise RefusMesure(
            MOTIF_AUCUN_SOLDE,
            "aucun solde fourni. Un état de la situation financière vide "
            "n'est pas un bilan à zéro — c'est l'absence d'état, et rendre "
            "deux lignes nulles serait la même faute qu'une gate rendant "
            "« Ran 0 tests » en sortant 0")
    for s in lot:
        if not (s.portefeuille or '').strip():
            raise RefusMesure(
                MOTIF_PORTEFEUILLE_VIDE,
                f"le groupe « {s.cle_groupe} » ne nomme aucun portefeuille. "
                f"§78 présente PAR PORTEFEUILLE : sans lui, la ligne du "
                f"bilan où ce groupe atterrit n'est pas déterminée")

    par_portefeuille: dict = {}
    for s in lot:
        nom = s.portefeuille.strip()
        somme, compte = par_portefeuille.get(nom, (0.0, 0))
        par_portefeuille[nom] = (somme + s.valeur_comptable, compte + 1)

    actifs, passifs = [], []
    for nom, (net, compte) in sorted(par_portefeuille.items()):
        poste = PosteBilan(portefeuille=nom, valeur=abs(net),
                           est_actif=net < 0, nb_groupes=compte)
        (actifs if poste.est_actif else passifs).append(poste)

    return Bilan(actifs=tuple(actifs), passifs=tuple(passifs),
                 total_actifs=sum(p.valeur for p in actifs),
                 total_passifs=sum(p.valeur for p in passifs),
                 nb_portefeuilles=len(par_portefeuille),
                 motif=MOTIF_REASSURANCE_ABSENTE)


def valeur_comptable_avec_frais_acquisition(valeur_comptable: float,
                                            actif_frais_acquisition: float
                                            ) -> float:
    """§79 — l'actif de frais d'acquisition s'INCORPORE au portefeuille.

    ⚠️ IL NE SE PRÉSENTE PAS SUR UNE LIGNE À LUI. C'est la même règle qu'au
    §55 a), où ces frais viennent en diminution du passif au lieu de former
    un actif séparé — et c'est le piège que l'oracle ICA 5.2 attrape, avec
    un LRC de 400 là où le traitement séparé en donnerait 500.
    """
    if actif_frais_acquisition < 0:
        raise RefusMesure(
            'actif_frais_acquisition_negatif',
            f"l'actif de frais d'acquisition vaut {actif_frais_acquisition}. "
            f"§28B en fait un ACTIF : un négatif signale une convention de "
            f"signe inverse, et l'absorber fausserait le portefeuille")
    return valeur_comptable - actif_frais_acquisition
