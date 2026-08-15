# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : L'ÉTAT DATÉ, ET CE QU'IL REFUSE
=============================================================================

⚠️⚠️ IFRS 17 NE DIT NULLE PART CE QU'UN JEU D'ÉTATS DOIT CONTENIR. Mesuré :
« jeu complet », « ensemble complet », « états financiers complets » — ZÉRO
occurrence dans le règlement. C'est le travail d'IAS 1, auquel IFRS 17 ne
renvoie que pour l'importance relative (§96) et les reclassements (§91).

⚠️ LA LISTE DES PIÈCES CI-DESSOUS EST DONC DÉRIVÉE, PAS LUE. Elle vient de
§78-92 et de §93-132. Un lecteur qui la croirait prescrite chercherait un
index qui n'existe pas — et c'est pourquoi elle est écrite ici plutôt que
supposée. Les trois index qui EXISTENT sont partiels : §78 (quatre lignes de
bilan), §80 (deux postes de performance), §93 (l'objectif des annexes).

⚠️ ET §93 ÉNONCE SON OBJECTIF PAR RAPPORT À TROIS ÉTATS : « l'état de la
situation financière, le ou les états de la performance financière ET L'ÉTAT
DES FLUX DE TRÉSORERIE ». Ce troisième est HORS DE CETTE PLATEFORME — c'est
un état d'entité, pas un état IFRS 17 — et il est NOMMÉ ici plutôt
qu'ignoré : l'objectif des annexes se lit par rapport à lui.

⚠️⚠️ CE QUE CE MODULE APPORTE, ET IL FAUT LE DIRE SANS L'ENJOLIVER : IL NE
CALCULE RIEN DE NEUF. Sa valeur tient en deux faits.

  1. LES ARTICULATIONS CESSENT D'ÊTRE FACULTATIVES. §99 b) et §80 ↔ §100
     existaient et étaient testées, et AUCUN CODE NE LES APPELAIT — c'est la
     raison d'être de ce module. Un contrôle que personne n'exécute est un
     contrôle qui ne contrôle rien : c'est la forme la plus discrète du
     motif de ce chantier, après le contrôle placé au mauvais endroit et le
     test aveugle à l'étiquette d'à côté.
     ⚠️ CETTE PHRASE EST AU PASSÉ, ET C'EST DÉLIBÉRÉ. Écrite au présent —
     « personne ne les appelle » — elle devenait fausse à l'instant même où
     ce module était écrit. Un texte qui épingle un état transitoire dérive ;
     un texte qui dit pourquoi une chose a été bâtie reste vrai.
  2. UNE ABSENCE DEVIENT DÉCLARÉE AU LIEU D'IMPLICITE. Une pièce non
     mentionnée est un REFUS ; seule une pièce déclarée absente AVEC SON
     MOTIF passe. « Sans motif, elle est indiscernable d'un oubli. »

⚠️ ET IL RENDRA UN OBJET, JAMAIS UN DOCUMENT. Un état daté doit être
RELISIBLE ET COMPARABLE — deux clôtures successives se confrontent, et un
commissaire demande ce qui a changé d'une version à l'autre. Un document ne
se compare pas. ⚠️ De plus, §96 laisse la MAILLE de regroupement à l'entité
(par ligne de produits, zone géographique ou secteur IFRS 8) : un objet à la
maille fine se regroupe de trois façons, un document en fige une. Figer la
forme ici trancherait §96 à la place du client.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023, §78, §80, §82, §93, §96, §97, §99 b), §100, §130.
=============================================================================
"""

from typing import NamedTuple

from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.rapprochement_99 import verifier_articulation_99b
from normes.ifrs17.mesure.resultat_80 import verifier_articulation

#: ⚠️ LE VOCABULAIRE DES PIÈCES EST CLOS, ET DÉRIVÉ DE §78-92 + §93-132 —
#: aucun index de la norme ne l'énumère. Chaque pièce porte le paragraphe
#: qui l'exige, EN DONNÉE : un commissaire lit la référence, pas
#: l'identifiant Python.
PIECES: dict[str, str] = {
    'PERIMETRE_PUBLIE':    'hors norme — ce que la plateforme ne fait pas',
    'BILAN_78':            '§78-79',
    'RESULTAT_80':         '§80-92',
    'RAPPROCHEMENTS_100':  '§99-100, §103, §105',
    'NOTES_97_119_120':    '§97 a) b) c), §119, §120',
    'REGISTRE_DES_GROUPES': '§14-25, scellement',
    'DEVELOPPEMENT_130':   '§130',
    'FINANCEMENT_56':      '§56, B72 d)',
}

#: ⚠️⚠️ LA LIGNE DE PARTAGE, ET ELLE N'EST PAS « IMPORTANT / ACCESSOIRE ».
#:
#:   UNE PIÈCE PEUT MANQUER SI SON ABSENCE EST UN FAIT DÉCLARABLE ;
#:   ELLE NE LE PEUT PAS SI SON ABSENCE REND LES AUTRES FAUSSES.
#:
#: · le PÉRIMÈTRE : un état sans lui laisse croire à un périmètre complet —
#:   même doctrine que `perimetre.mention_directions` ;
#: · le BILAN : §99 b) exige que le rapprochement lui soit ÉGAL. Sans lui,
#:   l'articulation n'est pas « non établie », elle est IMPOSSIBLE, et un
#:   rapprochement non confronté se lit comme confronté ;
#: · le RÉSULTAT : §80 ↔ §100 est exactement symétrique. ⚠️ CETTE SYMÉTRIE A
#:   ÉTÉ MANQUÉE À LA CONCEPTION — le rapport traitait le bilan comme
#:   indispensable et le résultat comme facultatif, sans le justifier. C'est
#:   le critère ci-dessus, appliqué, qui les a réunis.
INDISPENSABLES = ('PERIMETRE_PUBLIE', 'BILAN_78', 'RESULTAT_80')

#: ⚠️ LES DEUX ARTICULATIONS QUI EXISTAIENT SANS ÊTRE APPELÉES.
ARTICULATION_99B = '§99 b) — le rapprochement égale le bilan du §78'
ARTICULATION_80_100 = '§80 ↔ §100 — le résultat contre le déroulé du passif'
ARTICULATIONS = (ARTICULATION_99B, ARTICULATION_80_100)

#: ⚠️ DEUX VERDICTS, ET PAS UN BOOLÉEN. « Établie » et « non établie » ne
#: sont pas les deux faces d'une même pièce : la seconde porte POURQUOI le
#: contrôle n'a pas pu tourner. Un booléen écraserait le motif — la faute
#: que `verdict_53_declare` a déjà coûtée.
#: ⚠️ Il n'y a pas de troisième verdict : une articulation qui TOURNE ET
#: ÉCHOUE ne se range pas, elle REFUSE l'état entier.
ETABLIE = 'ETABLIE'
NON_ETABLIE = 'NON_ETABLIE'
VERDICTS_ARTICULATION = (ETABLIE, NON_ETABLIE)

MOTIF_PIECE_NI_FOURNIE_NI_DECLAREE = 'piece_ni_fournie_ni_declaree_absente'
MOTIF_PIECE_INDISPENSABLE_ABSENTE = 'piece_indispensable_absente'
MOTIF_ABSENCE_SANS_MOTIF = 'absence_de_piece_sans_motif'
MOTIF_PIECE_INCONNUE = 'piece_hors_du_vocabulaire'
MOTIF_ETAT_CONTREDIT = 'etat_contredit_par_une_articulation'

#: ⚠️ CE QUE CET ÉTAT NE PORTE PAS, ET QUI DESCEND AVEC LUI.
CE_QUI_MANQUE_ENCORE = (
    "⚠️ CE QUE CET ÉTAT N'EST PAS : un jeu d'états financiers. AUCUN TABLEAU "
    "n'est produit, quand §99 a) exige les rapprochements « sous forme de "
    "tableau ». La réassurance détenue n'est séparée NI au bilan (§78 c) et "
    "d), non construits) NI au compte de résultat (§82, non construit) — les "
    "deux vont ensemble, et les traiter séparément laisserait le cédé séparé "
    "d'un côté et fondu de l'autre. Et l'ÉTAT DES FLUX DE TRÉSORERIE, par "
    "rapport auquel §93 énonce l'objectif des annexes, est hors de cette "
    "plateforme : c'est un état d'entité.")


class Piece(NamedTuple):
    """Une pièce de l'état : son contenu, ou son absence AVEC son motif."""
    nom:     str      # une clé de PIECES
    contenu: object   # ce que le module a produit, ou None
    motif:   str      # pourquoi absente — obligatoire si contenu vaut None

    @property
    def presente(self) -> bool:
        return self.contenu is not None


class Articulation(NamedTuple):
    """Un contrôle croisé, et ce qu'il a pu établir.

    ⚠️ `verdict` VAUT `NON_ETABLIE` QUAND LE CONTRÔLE N'A PAS PU TOURNER, et
    le motif dit pourquoi. Une articulation qui tourne et ÉCHOUE n'arrive
    jamais jusqu'ici : elle refuse l'état.
    """
    nom:     str
    verdict: str      # l'un de VERDICTS_ARTICULATION
    motif:   str


class EtatDate(NamedTuple):
    """Un arrêté, ses pièces, ses articulations. ⚠️ UN OBJET, PAS UN
    DOCUMENT — il doit se relire, se comparer et se regrouper."""
    arrete:        str
    entite:        str
    pieces:        tuple   # (Piece, ...) — toutes celles de PIECES
    articulations: tuple   # (Articulation, ...)
    motif:         str

    def piece(self, nom: str) -> Piece:
        for p in self.pieces:
            if p.nom == nom:
                return p
        raise KeyError(f"pièce inconnue : « {nom} ». Le vocabulaire est clos "
                       f"à {len(PIECES)} : {sorted(PIECES)}")


def _exiger_vocabulaire(fournies, absences) -> None:
    """⚠️ UNE PIÈCE HORS VOCABULAIRE EST UN REFUS, PAS UN AJOUT SILENCIEUX.
    Le vocabulaire est dérivé de la norme ; l'étendre est une décision."""
    inconnues = sorted((set(fournies) | set(absences)) - set(PIECES))
    if inconnues:
        raise RefusMesure(
            MOTIF_PIECE_INCONNUE,
            f"{len(inconnues)} pièce(s) hors du vocabulaire : {inconnues}. "
            f"Il est CLOS à {len(PIECES)} pièces, dérivées de §78-92 et "
            f"§93-132 — aucun index de la norme ne les énumère, et "
            f"l'étendre est une décision, pas un ajout.")
    deux_fois = sorted(set(fournies) & set(absences))
    if deux_fois:
        raise RefusMesure(
            MOTIF_ABSENCE_SANS_MOTIF,
            f"{len(deux_fois)} pièce(s) sont à la fois fournies et déclarées "
            f"absentes : {deux_fois}. Une déclaration et une donnée qui se "
            f"contredisent ne peuvent pas être vraies toutes les deux.")


def _exiger_toutes_comptees(fournies, absences) -> None:
    """⚠️⚠️ LE CŒUR DE CE MODULE : ON NE PEUT PAS OUBLIER UNE PIÈCE, ON PEUT
    SEULEMENT LA DÉCLARER ABSENTE. Une pièce passée sous silence serait
    indiscernable d'un oubli — c'est la règle que `bilan` applique déjà aux
    portefeuilles vides."""
    oubliees = sorted(set(PIECES) - set(fournies) - set(absences))
    if oubliees:
        raise RefusMesure(
            MOTIF_PIECE_NI_FOURNIE_NI_DECLAREE,
            f"{len(oubliees)} pièce(s) ne sont NI fournies NI déclarées "
            f"absentes : {oubliees}. ⚠️ UNE PIÈCE PASSÉE SOUS SILENCE EST "
            f"INDISCERNABLE D'UN OUBLI. Déclarez-la absente avec son motif — "
            f"« aucune donnée de sinistres remise », « premier exercice, "
            f"aucun registre antérieur » — ou fournissez-la.")
    sans_motif = sorted(n for n, m in absences.items()
                        if not str(m or '').strip())
    if sans_motif:
        raise RefusMesure(
            MOTIF_ABSENCE_SANS_MOTIF,
            f"{len(sans_motif)} absence(s) sont déclarées sans motif : "
            f"{sans_motif}. Une absence motivée EST une déclaration ; sans "
            f"motif, elle est indiscernable d'un oubli.")


def _exiger_indispensables(fournies) -> None:
    """⚠️ TROIS PIÈCES NE PEUVENT PAS MANQUER, ET LE CRITÈRE EST ÉCRIT : leur
    absence rendrait les autres fausses, pas seulement incomplètes."""
    manquantes = [n for n in INDISPENSABLES if n not in fournies]
    if manquantes:
        raise RefusMesure(
            MOTIF_PIECE_INDISPENSABLE_ABSENTE,
            f"{len(manquantes)} pièce(s) indispensable(s) manquent : "
            f"{manquantes}. ⚠️ UNE PIÈCE PEUT MANQUER SI SON ABSENCE EST UN "
            f"FAIT DÉCLARABLE ; ELLE NE LE PEUT PAS SI SON ABSENCE REND LES "
            f"AUTRES FAUSSES. Sans le périmètre, l'état laisse croire à un "
            f"périmètre complet ; sans le bilan, l'égalité du §99 b) n'est "
            f"pas « non établie » mais IMPOSSIBLE, et un rapprochement non "
            f"confronté se lit comme confronté ; sans le compte de résultat, "
            f"§80 ↔ §100 l'est tout autant.")


def _articuler(nom, controle, motif_impossible) -> Articulation:
    """Exécute une articulation, ou dit pourquoi elle n'a pas pu tourner.

    ⚠️⚠️ UNE ARTICULATION QUI TOURNE ET ÉCHOUE REFUSE L'ÉTAT ENTIER. Deux
    états qui se contredisent ne se publient pas avec une note en bas de
    page : c'est la seule absence qui ne se déclare pas, parce qu'elle n'est
    pas une absence.
    """
    if controle is None:
        return Articulation(nom, NON_ETABLIE, motif_impossible)
    try:
        rendu = controle()
    except RefusMesure as refus:
        raise RefusMesure(
            MOTIF_ETAT_CONTREDIT,
            f"l'état est REFUSÉ : {nom} a été vérifiée et elle ÉCHOUE. "
            f"{refus} ⚠️ CE N'EST PAS UNE ABSENCE, C'EST UNE CONTRADICTION : "
            f"deux pièces de cet état se démentent l'une l'autre, et aucune "
            f"note ne rendrait leur publication honnête.") from refus
    return Articulation(nom, ETABLIE, rendu or 'les deux états concordent')


def assembler(*, arrete: str, entite: str, pieces: dict,
              absences: dict | None = None,
              soldes_du_rapprochement=None, nature_du_rapprochement: str = '',
              nature_emise: str = '', deroule_du_passif: dict | None = None
              ) -> EtatDate:
    """Un état daté, ou un REFUS qui dit lequel des trois cas s'applique.

    ⚠️ TROIS REFUS, ET TROIS SEULEMENT :
      · une pièce ni fournie ni déclarée absente — l'oubli ;
      · une pièce indispensable absente ;
      · une articulation qui tourne et ÉCHOUE — la contradiction.

    ⚠️ TOUT LE RESTE SE DÉCLARE. L'état DIT ce qui manque plutôt que de
    bloquer : c'est le dessin d'ensemble, celui qui commandera aussi le
    rendu — il ne demandera rien, il restituera.
    """
    absences = dict(absences or {})
    _exiger_vocabulaire(pieces, absences)
    _exiger_toutes_comptees(pieces, absences)
    _exiger_indispensables(pieces)

    lot = tuple(
        Piece(nom, pieces.get(nom), str(absences.get(nom, '') or '').strip())
        for nom in sorted(PIECES))

    #: ⚠️ §99 b) — elle ne tourne que si le rapprochement est là ET nommé par
    #: sa nature : §98 exige des rapprochements SÉPARÉS pour l'émis et le
    #: cédé, et le cédé ne peut pas boucler faute des lignes §78 c) et d).
    peut_99b = (soldes_du_rapprochement is not None
                and nature_du_rapprochement and nature_emise)
    articulation_99b = _articuler(
        ARTICULATION_99B,
        (lambda: verifier_articulation_99b(
            soldes_du_rapprochement=soldes_du_rapprochement,
            bilan=pieces['BILAN_78'],
            nature_du_rapprochement=nature_du_rapprochement,
            nature_emise=nature_emise)) if peut_99b else None,
        "le rapprochement du §100 n'est pas fourni, ou sa nature (§98 — émis "
        "ou réassurance détenue) n'est pas déclarée. Le contrôle n'a pas pu "
        "tourner ; il n'a donc RIEN établi, et surtout pas un accord.")

    articulation_80 = _articuler(
        ARTICULATION_80_100,
        (lambda: verifier_articulation(pieces['RESULTAT_80'],
                                       **deroule_du_passif))
        if deroule_du_passif else None,
        "le déroulé du passif n'est pas fourni — il faut ses trois totaux : "
        "revenu, charges et charges financières. Le contrôle n'a pas pu "
        "tourner ; il n'a donc RIEN établi.")

    absentes = [p.nom for p in lot if not p.presente]
    non_etablies = [a.nom for a in (articulation_99b, articulation_80)
                    if a.verdict == NON_ETABLIE]
    motif = (
        f"ÉTAT IFRS 17 AU {arrete} — {entite}. "
        f"{len(PIECES) - len(absentes)} pièce(s) sur {len(PIECES)} fournies"
        + (f", {len(absentes)} déclarée(s) absente(s) : {absentes}"
           if absentes else "")
        + f". Articulations : {len(ARTICULATIONS) - len(non_etablies)} "
        f"établie(s)"
        + (f", {len(non_etablies)} NON ÉTABLIE(S) : {non_etablies}"
           if non_etablies else "")
        + ". ⚠️ « NON ÉTABLIE » N'EST PAS « CONCORDANTE » : le contrôle n'a "
          "pas pu tourner, il n'a donc rien constaté. " + CE_QUI_MANQUE_ENCORE)

    return EtatDate(arrete=arrete, entite=entite, pieces=lot,
                    articulations=(articulation_99b, articulation_80),
                    motif=motif)
