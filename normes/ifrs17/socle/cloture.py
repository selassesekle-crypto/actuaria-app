# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §100 : LE MAGASIN DE CLÔTURES
=============================================================================

⚠️⚠️ POURQUOI CE MODULE EXISTE, ET C'EST MESURÉ. La plateforme n'avait AUCUNE
MÉMOIRE DES MONTANTS. Le registre porte les groupes — un test y verrouille
qu'aucun champ de `Groupe` ne porte un euro — et le magasin de clôtures était
nommé partout comme la frontière, sans être bâti. Or :

  §100 — « L'entité doit présenter séparément les rapprochements des soldes
  D'OUVERTURE ET DE CLÔTURE […] Pour les contrats d'assurance évalués selon
  LA MÉTHODE D'AFFECTATION DES PRIMES décrite aux paragraphes 53 à 59 ou aux
  paragraphes 69 à 70A […] »

§100 nomme la PAA, et il exige un ouverture → clôture. `roll_forward` déroule
une PROJECTION depuis l'origine ; il ne part pas d'un solde d'ouverture
audité. Un client qui clôture 2027 a besoin de son solde 2026, et rien ne le
portait. On ne met pas en forme ce qu'on ne sait pas calculer : c'est
pourquoi ce module passe AVANT le rendu des états.

⚠️ CE MODULE N'EST PAS UNE EXTENSION DU REGISTRE, ET L'ARGUMENT QUI TRANCHE
N'EST PAS TECHNIQUE : une identité de groupe est une DÉRIVATION, un solde de
clôture est un CHIFFRE SIGNÉ qui entre dans des comptes audités. Ils n'ont ni
le même signataire ni la même opposabilité. La frontière déjà écrite dans
`socle.groupe` tient — « le registre répond à quels groupes existent, le
magasin à combien valaient-ils à cet arrêté ».

⚠️ CE QUE CE LOT (M1) FAIT, ET CE QU'IL NE FAIT PAS. Il constitue un dossier
de clôture et REFUSE une articulation rompue. La SIGNATURE (M2), la
PERSISTANCE (M3) et le CHAÎNAGE N → N+1 (M4) ne sont pas ici. En
particulier : rien n'empêche encore de servir une clôture non signée comme
ouverture — c'est M2, et c'est la seule place où la règle mordra utilement.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023. §97, §98, §99, §100, §103, §105. Chacun relu dans ce texte.
=============================================================================
"""

from typing import NamedTuple

#: ⚠️⚠️ §98 EXIGE DEUX RAPPROCHEMENTS SÉPARÉS, ET LA CLÉ DE GROUPE NE LE
#: PERMETTAIT PAS. « L'entité doit présenter des rapprochements SÉPARÉS pour
#: les contrats d'assurance ÉMIS et les contrats de réassurance DÉTENUS. »
#: `CleGroupe` porte (portefeuille, classe_16, cohorte) — mesuré : aucune
#: nature, et le socle n'a aucune clé de groupe cédé.
#:
#: ⚠️ ET LA NATURE NE S'AJOUTE PAS À `CleGroupe` : celle-ci est scellée à la
#: naissance (§24) et un test refuse la reclassification ; y ajouter un champ
#: changerait l'identité de TOUTES les clés déjà écrites. Elle se déclare donc
#: ICI, avec le dossier — et `MOTIF_NATURE_DIVERGENTE` interdit qu'une même
#: clé de groupe apparaisse sous deux natures.
NATURE_EMIS = 'EMIS'
NATURE_REASSURANCE_DETENUE = 'REASSURANCE_DETENUE'
NATURES = (NATURE_EMIS, NATURE_REASSURANCE_DETENUE)

#: ⚠️⚠️ QUATRE SOLDES, ET NON SIX — LA MISE EN PAGE DU §100 LE DIT. Le texte
#: aplati laisse croire que la ventilation PAA porte sur les trois éléments ;
#: la mise en page brute la place À L'INTÉRIEUR DE c) :
#:
#:     a) le passif net au titre de la couverture restante, hors élément
#:        de perte ;
#:     b) les éléments de perte éventuels ;
#:     c) le passif au titre des sinistres survenus. Pour les contrats
#:        évalués selon la PAA […] des rapprochements séparés pour :
#:          i) les estimations de la valeur actualisée des flux futurs ; et
#:          ii) l'ajustement au titre du risque non financier ;
#:
#: ⚠️ SIX AURAIT ÉTÉ PIRE QU'UN COMPTE FAUX : cela aurait suggéré que le LRC
#: en PAA se ventile entre flux et ajustement pour risque. Il ne le fait pas —
#: la PAA le mesure sur la prime.
AXE_LRC_HORS_PERTE = 'LRC_HORS_PERTE'                    # §100 a)
AXE_ELEMENT_DE_PERTE = 'ELEMENT_DE_PERTE'                # §100 b)
AXE_LIC_FLUX_FUTURS = 'LIC_FLUX_FUTURS'                  # §100 c) i)
AXE_LIC_AJUSTEMENT_RISQUE = 'LIC_AJUSTEMENT_RISQUE'      # §100 c) ii)

AXES = (AXE_LRC_HORS_PERTE, AXE_ELEMENT_DE_PERTE,
        AXE_LIC_FLUX_FUTURS, AXE_LIC_AJUSTEMENT_RISQUE)

#: ⚠️⚠️ LE VOCABULAIRE DES MOUVEMENTS EN PAA VIENT DE §103 ET §105, JAMAIS DE
#: §104. Les trois paragraphes se désignent eux-mêmes :
#:
#:   · §103 — « dans les rapprochements exigés au PARAGRAPHE 100 » → la PAA ;
#:   · §104 — « exigés au PARAGRAPHE 101 », et §101 vise les contrats « QUI NE
#:     SONT PAS évalués selon la méthode d'affectation des primes » ;
#:   · §105 — « pour COMPLÉTER les rapprochements exigés aux paragraphes 100
#:     ET 101 » → les deux.
#:
#: ⚠️ §104 aurait apporté la MARGE SUR SERVICES CONTRACTUELS, qui n'existe pas
#: en PAA, dans un magasin non-vie.
#:
#: ⚠️⚠️ ET LA LISTE N'EST PAS ENTIÈREMENT CLOSE — LA NORME OUVRE ELLE-MÊME LA
#: DERNIÈRE CASE. §105 d) : « tout autre poste pouvant être nécessaire à la
#: compréhension de la variation de la valeur comptable nette ». Une liste
#: entièrement fermée aurait donc REFUSÉ DU CORRECT. Onze postes clos, plus un
#: résidu qui EXIGE son libellé : un résidu sans libellé n'affirmerait rien,
#: ce qui serait la faute inverse et connue de ce dépôt.
#:
#: ⚠️ CHAQUE POSTE PORTE SA RÉFÉRENCE EXACTE, en donnée et non dans son nom :
#: un commissaire aux comptes lit la référence, pas l'identifiant Python.
#: ⚠️ Et « §105 b) » n'est PAS « §105B » — le premier est le risque de
#: non-exécution du réassureur, le second la perte de valeur de l'actif de
#: frais d'acquisition. Deux choses différentes à une capitale près.
POSTE_AUTRE = 'AUTRE'

POSTES: dict[str, str] = {
    'PRODUITS_ASSURANCE':            '§103 a)',
    'CHARGES_SINISTRES_ET_AUTRES':   '§103 b) i)',
    'AMORTISSEMENT_FRAIS_ACQ':       '§103 b) ii)',
    'SERVICES_PASSES':               '§103 b) iii)',
    'SERVICES_FUTURS':               '§103 b) iv)',
    'COMPOSANTES_INVESTISSEMENT':    '§103 c)',
    'PRIMES':                        '§105 a) i)',
    'FLUX_FRAIS_ACQUISITION':        '§105 a) ii)',
    'PAIEMENTS_SINISTRES':           '§105 a) iii)',
    'RISQUE_DE_NON_EXECUTION':       '§105 b)',
    'PRODUITS_CHARGES_FINANCIERS':   '§105 c)',
    POSTE_AUTRE:                     '§105 d)',
}

#: ⚠️ « LE CAS ÉCHÉANT » FIGURE DANS §103 ET DANS §105, et cela se code : la
#: liste est close, mais LA PRÉSENCE DE CHAQUE POSTE EST CONDITIONNELLE. Un
#: magasin qui exigerait les onze refuserait un groupe simple — un groupe sans
#: réassurance n'a pas de « risque de non-exécution » à présenter.
PRESENCE_CONDITIONNELLE = (
    "⚠️ AUCUN POSTE N'EST OBLIGATOIRE : §103 et §105 disent tous deux « le cas "
    "échéant ». La liste des postes est CLOSE, leur présence est "
    "CONDITIONNELLE. Un groupe sans réassurance détenue n'a pas de risque de "
    "non-exécution à présenter, et l'exiger refuserait un dossier correct.")

#: ⚠️⚠️ L'AXE D'UN MOUVEMENT SE DÉCLARE, IL NE SE DÉDUIT PAS. §103 et §105
#: énumèrent les POSTES à présenter séparément ; ILS NE DISENT PAS quel poste
#: déplace quel solde du §100. Une table poste → axe serait donc une invention
#: de ce module, présentée comme une lecture — exactement la faute que ce
#: chantier a payée deux fois (§22 invoqué à tort, puis la cohorte prise pour
#: la comptabilisation initiale).
#:
#: ⚠️ ET SANS L'AXE, L'ARTICULATION N'EST PAS VÉRIFIABLE : on ne pourrait
#: contrôler qu'un total global, où deux erreurs de sens contraire sur deux
#: axes se compenseraient sans bruit. C'est le défaut que ce module existe
#: pour attraper, un étage plus bas.
AXE_DECLARE = (
    "⚠️ L'AXE D'UN MOUVEMENT EST DÉCLARÉ, PAS DÉDUIT. §103 et §105 énumèrent "
    "les postes à présenter séparément ; aucun des deux ne dit quel poste "
    "déplace quel solde du §100. Déduire la correspondance reviendrait à "
    "présenter une invention comme une lecture. ⚠️ Et sans l'axe, seule une "
    "articulation GLOBALE serait possible — où deux erreurs de sens contraire "
    "sur deux axes se compenseraient sans bruit.")


class CleCloture(NamedTuple):
    """Ce qu'identifie un dossier de clôture. ⚠️ TROIS composantes.

    ⚠️ `nature` vient du §98, qui exige des rapprochements SÉPARÉS pour les
    contrats émis et la réassurance détenue. Elle ne vit pas dans `CleGroupe`,
    scellée à la naissance : voir la note en tête de module.
    """
    nature:     str    # l'une de NATURES
    cle_groupe: str    # la forme texte d'une `CleGroupe` du registre
    arrete:     str    # 'AAAA-MM-JJ'

    @property
    def texte(self) -> str:
        return f"{self.nature}|{self.cle_groupe}|{self.arrete}"


class Soldes(NamedTuple):
    """Les quatre soldes du §100 en PAA. ⚠️ Quatre, pas six — voir AXES.

    ⚠️ AUCUNE CONVENTION DE SIGNE N'EST IMPOSÉE ICI, ET C'EST DÉLIBÉRÉ. §98
    prévient que la réassurance détenue donne « des charges ou des réductions
    de charges plutôt que des produits ». Ce dépôt a déjà payé DEUX
    conventions contradictoires — l'oracle ICA publie en 5.2 un revenu positif
    et en 5.6.1 le même négatif. Poser une troisième convention sans l'avoir
    mesurée serait la faute connue. L'articulation vérifiée plus bas est
    INDIFFÉRENTE AU SIGNE : elle vaut quelle que soit la convention retenue.
    """
    lrc_hors_perte:        float
    element_de_perte:      float
    lic_flux_futurs:       float
    lic_ajustement_risque: float

    def par_axe(self) -> dict[str, float]:
        return dict(zip(AXES, self))


class Mouvement(NamedTuple):
    """Un mouvement de la période : son poste, son axe, son montant."""
    poste:   str      # une clé de POSTES
    axe:     str      # l'un de AXES — DÉCLARÉ, voir AXE_DECLARE
    montant: float
    libelle: str = ''    # obligatoire pour POSTE_AUTRE (§105 d)


class DossierCloture(NamedTuple):
    """Un arrêté d'un groupe : ouverture, mouvements, clôture.

    ⚠️ LES TROIS SONT PORTÉS, ET C'EST L'ARBITRAGE CENTRAL DE CE MODULE.
    Porter les soldes seuls rendrait §103 impossible — une différence n'a pas
    de cause. Porter les mouvements seuls et calculer la clôture la rendrait
    INCAPABLE DE SE CONTREDIRE : un mouvement perdu passerait sans bruit,
    exactement le défaut qui a laissé 550,66 € de résidu dans un roll-forward
    composé à la main. ⚠️ Un magasin qui ne peut pas se contredire ne peut
    rien détecter.

    ⚠️ `version` ET `motif` : une clôture EST rectifiée avant signature. Elle
    ne s'écrase JAMAIS — on en ajoute une, et la suivante porte son motif. Un
    commissaire aux comptes demandera si le chiffre a changé après le premier
    passage ; un magasin qui écrase ne peut pas répondre.
    """
    cle:        CleCloture
    ouverture:  Soldes
    mouvements: tuple[Mouvement, ...]
    cloture:    Soldes
    version:    int = 1
    motif:      str = ''


class RefusCloture(Exception):
    """Le magasin refuse — jamais en silence."""

    def __init__(self, motif: str, message: str):
        self.motif = motif
        super().__init__(message)


MOTIF_NATURE_NON_DECLAREE = 'nature_du_dossier_non_declaree'
MOTIF_NATURE_DIVERGENTE = 'meme_groupe_sous_deux_natures'
MOTIF_ARRETE_INVALIDE = 'arrete_de_cloture_invalide'
MOTIF_POSTE_INCONNU = 'poste_de_mouvement_inconnu'
MOTIF_AXE_NON_DECLARE = 'axe_du_mouvement_non_declare'
MOTIF_LIBELLE_MANQUANT = 'residu_105d_sans_libelle'
MOTIF_ARTICULATION_ROMPUE = 'articulation_ouverture_mouvements_cloture'
MOTIF_VERSION_SANS_MOTIF = 'rectification_sans_motif'
MOTIF_DOSSIER_ABSENT = 'dossier_de_cloture_absent'

#: ⚠️⚠️ L'ARTICULATION EST STRICTE, ET SON RÉSIDU SE DÉCLARE PLUTÔT QU'IL NE
#: SE TOLÈRE. `ouverture + Σ mouvements = clôture` est une IDENTITÉ, pas une
#: mesure : la clôture EST la somme. Le seul écart légitime est l'erreur de
#: virgule flottante, d'où 1e-6 — la même borne que le contrôle d'extinction
#: de `mesure.financement`.
#:
#: ⚠️ ET SI VOS CHIFFRES SONT ARRONDIS INDÉPENDAMMENT, LE RÉSIDU A UNE PLACE
#: PRÉVUE PAR LA NORME : §105 d), « tout autre poste pouvant être nécessaire à
#: la compréhension ». Le déclarer avec son libellé vaut mieux qu'une
#: tolérance qui absorberait aussi un mouvement perdu. Une tolérance ne
#: distingue pas l'arrondi de l'oubli ; une déclaration, si.
TOLERANCE_ARTICULATION = 1e-6


def _exiger_arrete(valeur, quoi: str) -> None:
    """⚠️ L'ISO EST IMPOSÉE, JAMAIS DEVINÉE — même règle que `declaration`."""
    v = str(valeur or '')
    if len(v) != 10 or v[4] != '-' or v[7] != '-' \
            or not (v[:4] + v[5:7] + v[8:]).isdigit():
        raise RefusCloture(
            MOTIF_ARRETE_INVALIDE,
            f"{quoi} vaut {valeur!r} : la forme AAAA-MM-JJ est attendue. Les "
            f"arrêtés se COMPARENT et se CHAÎNENT ici, et comparer deux "
            f"formats différents exigerait d'en deviner un.")


def _exiger_mouvements(mouvements) -> None:
    """Chaque mouvement dit son poste, son axe, et son libellé s'il est
    le résidu du §105 d)."""
    for rang, m in enumerate(mouvements, 1):
        if m.poste not in POSTES:
            raise RefusCloture(
                MOTIF_POSTE_INCONNU,
                f"mouvement {rang} : poste « {m.poste} » inconnu. Le "
                f"vocabulaire vient de §103 et §105 — jamais de §104, qui "
                f"vise les contrats NON évalués en PAA — et il est CLOS à "
                f"{len(POSTES)} postes : {sorted(POSTES)}. "
                + PRESENCE_CONDITIONNELLE)
        if m.axe not in AXES:
            raise RefusCloture(
                MOTIF_AXE_NON_DECLARE,
                f"mouvement {rang} ({m.poste}) : axe « {m.axe} » non déclaré "
                f"(attendu l'un de {list(AXES)}). " + AXE_DECLARE)
        if m.poste == POSTE_AUTRE and not str(m.libelle or '').strip():
            raise RefusCloture(
                MOTIF_LIBELLE_MANQUANT,
                f"mouvement {rang} : le poste {POSTE_AUTRE} ({POSTES[POSTE_AUTRE]}) "
                f"est présenté sans libellé. ⚠️ LA NORME OUVRE CETTE CASE — "
                f"« tout autre poste pouvant être nécessaire à la "
                f"compréhension » — et c'est justement pourquoi elle exige "
                f"qu'on dise DE QUOI il s'agit. Un résidu sans libellé "
                f"n'affirme rien, et rendrait la liste des onze autres "
                f"inutile : tout y tomberait.")


def _exiger_articulation(ouverture: Soldes, mouvements, cloture: Soldes,
                         cle: CleCloture) -> None:
    """⚠️ PAR AXE, ET NON GLOBALEMENT. Un contrôle global laisserait deux
    erreurs de sens contraire sur deux axes se compenser sans bruit."""
    ouv, clo = ouverture.par_axe(), cloture.par_axe()
    ecarts = []
    for axe in AXES:
        somme = sum(m.montant for m in mouvements if m.axe == axe)
        attendu = ouv[axe] + somme
        if abs(attendu - clo[axe]) > TOLERANCE_ARTICULATION:
            ecarts.append(
                f"{axe} : ouverture {ouv[axe]:.2f} + mouvements {somme:.2f} "
                f"= {attendu:.2f}, clôture déclarée {clo[axe]:.2f} "
                f"(écart {clo[axe] - attendu:+.2f})")
    if ecarts:
        raise RefusCloture(
            MOTIF_ARTICULATION_ROMPUE,
            f"dossier {cle.texte} : l'articulation est rompue sur "
            f"{len(ecarts)} axe(s) sur {len(AXES)} — " + ' · '.join(ecarts)
            + ". ⚠️ CE N'EST PAS UNE MESURE, C'EST UNE IDENTITÉ : la clôture "
              "EST l'ouverture augmentée des mouvements. Un écart signale un "
              "mouvement perdu, compté deux fois, ou porté sur le mauvais "
              "axe. ⚠️ Si vos montants sont arrondis indépendamment, le "
              "résidu a une place PRÉVUE PAR LA NORME — le poste "
              f"{POSTE_AUTRE} ({POSTES[POSTE_AUTRE]}), avec son libellé. Le "
              "déclarer vaut mieux qu'une tolérance, qui ne distinguerait pas "
              "l'arrondi de l'oubli.")


def constituer(*, nature: str, cle_groupe: str, arrete: str,
               ouverture: Soldes, mouvements, cloture: Soldes,
               version: int = 1, motif: str = '') -> DossierCloture:
    """Un dossier de clôture, ou un REFUS qui dit ce qui ne va pas."""
    if nature not in NATURES:
        raise RefusCloture(
            MOTIF_NATURE_NON_DECLAREE,
            f"la nature du dossier n'est pas déclarée (reçu {nature!r}, "
            f"attendu l'une de {list(NATURES)}). ⚠️ §98 EXIGE DES "
            f"RAPPROCHEMENTS SÉPARÉS pour les contrats émis et la réassurance "
            f"détenue, et il demande d'ADAPTER §100 à §109 aux "
            f"caractéristiques du cédé. La nature ne se devine pas depuis la "
            f"clé de groupe : celle-ci ne la porte pas.")
    if not str(cle_groupe or '').strip():
        raise RefusCloture(
            MOTIF_NATURE_NON_DECLAREE,
            "le dossier ne nomme aucun groupe. Un solde de clôture appartient "
            "à UN groupe — c'est l'unité de compte du §24.")
    _exiger_arrete(arrete, "l'arrêté du dossier de clôture")
    mouvements = tuple(mouvements)
    _exiger_mouvements(mouvements)
    cle = CleCloture(nature, str(cle_groupe).strip(), arrete)
    _exiger_articulation(ouverture, mouvements, cloture, cle)
    if version > 1 and not str(motif or '').strip():
        raise RefusCloture(
            MOTIF_VERSION_SANS_MOTIF,
            f"le dossier {cle.texte} est présenté en version {version} sans "
            f"motif. ⚠️ UNE CLÔTURE NE S'ÉCRASE PAS, ON EN AJOUTE UNE — et "
            f"une rectification sans motif est indistinguable d'une erreur. "
            f"Un commissaire aux comptes demandera pourquoi le chiffre a "
            f"changé.")
    return DossierCloture(cle, ouverture, mouvements, cloture, version,
                          str(motif or '').strip())


class Magasin(NamedTuple):
    """Les clôtures d'une entité. ⚠️ APPEND-ONLY, comme le registre.

    Immuable : `deposer` en rend un nouveau. Aucune fonction ne modifie ni ne
    supprime — une clôture rectifiée s'AJOUTE en version suivante.
    """
    entite:   str
    dossiers: tuple[DossierCloture, ...] = ()


def ouvrir(entite: str) -> Magasin:
    """Un magasin vide pour une entité."""
    if not str(entite or '').strip():
        raise RefusCloture(
            MOTIF_NATURE_NON_DECLAREE,
            "un magasin de clôtures appartient à une entité nommée.")
    return Magasin(str(entite).strip())


def deposer(magasin: Magasin, dossier: DossierCloture) -> Magasin:
    """Ajoute un dossier. ⚠️ N'ÉCRASE JAMAIS — rend un nouveau magasin."""
    natures = {d.cle.nature for d in magasin.dossiers
               if d.cle.cle_groupe == dossier.cle.cle_groupe}
    if natures and dossier.cle.nature not in natures:
        raise RefusCloture(
            MOTIF_NATURE_DIVERGENTE,
            f"le groupe « {dossier.cle.cle_groupe} » est déjà déposé sous la "
            f"nature {sorted(natures)} et se présente en "
            f"{dossier.cle.nature}. ⚠️ UN GROUPE EST ÉMIS OU DÉTENU, JAMAIS "
            f"LES DEUX : §98 en fait deux rapprochements séparés, et une clé "
            f"qui traverse les deux les rendrait incomparables d'un arrêté à "
            f"l'autre.")
    return magasin._replace(dossiers=magasin.dossiers + (dossier,))


def dossier_courant(magasin: Magasin, cle: CleCloture) -> DossierCloture:
    """La DERNIÈRE version déposée pour cette clé, ou un refus.

    ⚠️ « Dernière » se lit dans l'ORDRE DE DÉPÔT, pas sur le numéro de
    version : le magasin est append-only, et l'ordre de dépôt est le seul
    fait qu'il constate. Un numéro de version est une déclaration de
    l'appelant, et deux dossiers peuvent la porter identique.
    """
    trouves = [d for d in magasin.dossiers if d.cle == cle]
    if not trouves:
        raise RefusCloture(
            MOTIF_DOSSIER_ABSENT,
            f"aucun dossier de clôture pour {cle.texte}. ⚠️ Un dossier ABSENT "
            f"n'est pas un dossier à ZÉRO : rendre des soldes nuls ferait "
            f"passer une absence pour une mesure.")
    return trouves[-1]


def versions(magasin: Magasin, cle: CleCloture) -> tuple[DossierCloture, ...]:
    """Toutes les versions déposées, dans l'ordre. ⚠️ C'est ce que
    l'append-only rend possible et qu'un écrasement détruirait."""
    return tuple(d for d in magasin.dossiers if d.cle == cle)


def resume(magasin: Magasin) -> str:
    """Ce qu'un actuaire ou un commissaire lit du magasin."""
    par_nature = {n: sum(1 for d in magasin.dossiers if d.cle.nature == n)
                  for n in NATURES}
    arretes = sorted({d.cle.arrete for d in magasin.dossiers})
    rectifies = sum(1 for d in magasin.dossiers if d.version > 1)
    return (
        f"MAGASIN DE CLÔTURES — {magasin.entite}\n"
        f"  {len(magasin.dossiers)} dossier(s), "
        f"{par_nature[NATURE_EMIS]} émis et "
        f"{par_nature[NATURE_REASSURANCE_DETENUE]} en réassurance détenue "
        f"(§98 les sépare)\n"
        f"  arrêtés couverts : {arretes or 'aucun'}\n"
        f"  {rectifies} rectification(s) déposée(s), aucune n'a écrasé la "
        f"version qu'elle corrige\n"
        f"  ⚠️ CE QUE CE MAGASIN N'ÉTABLIT PAS ENCORE : aucune clôture n'est "
        f"SIGNÉE, et rien n'empêche donc de servir une clôture non signée "
        f"comme ouverture de l'exercice suivant. C'est le lot M2.")
