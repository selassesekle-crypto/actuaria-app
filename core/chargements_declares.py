"""
=============================================================================
  ActuarIA — LES CHARGEMENTS COMMERCIAUX, DÉCLARÉS PAR LE CLIENT
=============================================================================

LA PRIME PURE EST UN FAIT. LA PRIME COMMERCIALE EST UNE DÉCISION.

⚠️⚠️ POURQUOI CE MODULE EXISTE — ARBITRAGE DU 08/09/2026. Le dépôt appliquait
`frais 15 % · commission 10 % · marge 3 %` à **vingt LoB sur vingt**, sans que
personne les ait déclarés. L'enquête d'origine les fait remonter au commit
`a17f058` du 14/07/2026 — **le même jour, le même commit et la même absence de
source que le `taxes: 0.33`** que le registre fiscal a remplacé.

  *Ces trois nombres ne sont pas des faits actuariels : ils dépendent du
  client et de son réseau de distribution. Le système ne peut pas les deviner
  à sa place, et un repli silencieux les devinait vingt fois.*

CE QUE LA RÈGLE DEVIENT
  · la **prime pure** se calcule TOUJOURS, sur les vingt plans, sans
    condition — c'est un fait actuariel, rien à déclarer pour l'obtenir ;
  · la **prime commerciale** (HT, puis TTC) n'existe QUE si le client a
    déclaré ses trois chargements. Sans déclaration, elle n'est pas calculée
    et **le refus est publié** — jamais un repli muet.

DEUX NIVEAUX DE DÉCLARATION
  1. un **taux général**, obligatoire et complet, qui vaut pour tout le
     portefeuille du plan ;
  2. des **exceptions**, qui ne déclarent que ce qui diffère.

⚠️⚠️ ET DEUX VOIES POUR UNE EXCEPTION, PARCE QUE LE RGPD EN FERME UNE.
Les vingt plans sont **versionnés dans un dépôt public** (mesuré : 20/20
suivis par git). Un identifiant de contrat écrit dans un plan serait une
donnée personnelle publiée. Donc :

  · **par CRITÈRE** — sur un axe CATÉGORIEL déclaré du plan, exactement la
    forme de `RegimeFiscalRoute` : elle est déjà validée dans les deux sens.
    **Un seul axe par plan**, et c'est un choix : avec deux axes, deux
    exceptions peuvent frapper le même contrat et le recouvrement cesse
    d'être décidable au chargement. Avec un axe, deux règles sur la même
    modalité se refusent — *quand deux déclarations se contredisent, on
    refuse, on ne choisit pas.*
  · **par CONTRAT** — le plan déclare qu'une table existe, sa provenance et
    son **SHA-256**, jamais son contenu. La table vit hors du dépôt, comme
    les données. C'est la doctrine de `reference_gel.json` : le hash seul,
    aucune donnée, donc publiable.

⚠️ `declare_par` EST UN RÔLE, JAMAIS UN NOM. Un nom de personne dans un YAML
public serait la même faute que l'identifiant. Le nom de l'actuaire
signataire vit dans le rapport, où il est déjà reçu (`actuaire_nom`).

⚠️ UNE EXCEPTION HÉRITE DU NIVEAU GÉNÉRAL, et c'est sans ambiguïté ICI —
contrairement au cas fiscal — parce que **le niveau général est obligatoire
et complet** : il y a toujours une valeur DÉCLARÉE à hériter, jamais une
valeur devinée.
=============================================================================
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping, Sequence
from typing import NamedTuple

__all__ = [
    'CHAMPS_CHARGEMENT',
    'CasException',
    'ExceptionsChargements',
    'TableExceptionsContrat',
    'chargements_du_contrat',
    'empreinte_table',
    'exceptions_depuis_dict',
    'synthese_chargements',
    'table_depuis_dict',
    'valider_chargements',
]

#: Les trois chargements COMMERCIAUX. ⚠️ `taxes` n'en fait pas partie : c'est
#: un fait LÉGAL, porté par `core.taxes_assurance` et qualifié au plan par
#: `regime_fiscal`. Les mélanger reviendrait à laisser un client déclarer un
#: taux de taxe — exactement ce que `TX-17` interdit.
CHAMPS_CHARGEMENT = ('frais', 'commission', 'marge')


class CasException(NamedTuple):
    """Un taux exceptionnel, et de quoi le justifier.

    ⚠️ Les trois montants sont `None` quand ils ne sont PAS repris : le cas
    hérite alors du niveau général. `motif`, `declare_par` et `declare_le`
    sont OBLIGATOIRES — une exception sans motif est une dérogation dont
    personne ne peut dire d'où elle vient.
    """
    frais: float | None = None
    commission: float | None = None
    marge: float | None = None
    motif: str = ''
    declare_par: str = ''       # un RÔLE, jamais un nom de personne
    declare_le: str = ''        # 'AAAA-MM-JJ'


@dataclasses.dataclass(frozen=True)
class ExceptionsChargements:
    """Les exceptions déclarées sur UN axe catégoriel du plan.

    ⚠️ `cas` est un tuple de paires TRIÉ, pas un dict : le plan entre dans une
    empreinte SHA-256 opposable, et seule une structure ordonnée déterministe
    garantit que deux chargements du même YAML signent pareil. C'est la même
    raison que pour `RegimeFiscalRoute.regimes`.
    """
    selon: str
    cas: tuple[tuple[str, CasException], ...]

    def pour(self, modalite) -> CasException | None:
        for m, c in self.cas:
            if m == modalite:
                return c
        return None


@dataclasses.dataclass(frozen=True)
class TableExceptionsContrat:
    """La DÉCLARATION d'une table d'exceptions par contrat — pas la table.

    ⚠️⚠️ AUCUN IDENTIFIANT N'ENTRE ICI. Le plan dit qu'une table existe, d'où
    elle vient, combien de contrats elle porte et quelle est son empreinte.
    La table elle-même vit hors du dépôt. *Un identifiant de contrat dans un
    YAML versionné publiquement serait une donnée personnelle publiée.*

    ⚠️ L'EMPREINTE N'EST PAS DÉCORATIVE : au chargement de la table, elle est
    RECALCULÉE et comparée. Divergence → refus. Sans cela, la déclaration
    signerait une table et le calcul en appliquerait une autre.
    """
    source: str                 # d'où vient la table, en clair
    empreinte_sha256: str       # 64 hexadécimaux
    nb_contrats: int
    declare_par: str = ''
    declare_le: str = ''


# =============================================================================
#  CONSTRUIRE DEPUIS LE YAML — le tri vit ici, et nulle part ailleurs
# =============================================================================

def exceptions_depuis_dict(d: Mapping) -> ExceptionsChargements:
    """Construit les exceptions par critère, en TRIANT les modalités."""
    if not isinstance(d, Mapping):
        raise TypeError(
            f"`chargements.exceptions` doit être un bloc `selon:`/`cas:`, "
            f"reçu {type(d).__name__}.")
    inconnues = sorted(set(d) - {'selon', 'cas'})
    if inconnues:
        raise ValueError(
            f"`chargements.exceptions` : clé(s) inconnue(s) {inconnues}. Le "
            f"bloc ne porte que `selon` (le facteur) et `cas` (les modalités).")
    if not d.get('selon') or not isinstance(d.get('cas'), Mapping):
        raise ValueError(
            "`chargements.exceptions` exige `selon` (le nom d'un facteur "
            "catégoriel déclaré) ET `cas` (une modalité -> ses taux).")
    cas = []
    for modalite, valeurs in d['cas'].items():
        if not isinstance(valeurs, Mapping):
            raise TypeError(
                f"`chargements.exceptions.cas['{modalite}']` doit être un "
                f"bloc, reçu {type(valeurs).__name__}.")
        admis = set(CHAMPS_CHARGEMENT) | {'motif', 'declare_par', 'declare_le'}
        surnumeraires = sorted(set(valeurs) - admis)
        if surnumeraires:
            raise ValueError(
                f"exception '{modalite}' : clé(s) inconnue(s) "
                f"{surnumeraires}. Admis : {sorted(admis)}.")
        cas.append((str(modalite), CasException(**valeurs)))
    return ExceptionsChargements(selon=str(d['selon']),
                                 cas=tuple(sorted(cas, key=lambda p: p[0])))


def table_depuis_dict(d: Mapping) -> TableExceptionsContrat:
    """Construit la DÉCLARATION d'une table par contrat."""
    if not isinstance(d, Mapping):
        raise TypeError(
            f"`chargements.exceptions_par_contrat` doit être un bloc, reçu "
            f"{type(d).__name__}.")
    champs = {f.name for f in dataclasses.fields(TableExceptionsContrat)}
    inconnues = sorted(set(d) - champs)
    if inconnues:
        raise ValueError(
            f"`chargements.exceptions_par_contrat` : clé(s) inconnue(s) "
            f"{inconnues}. Admis : {sorted(champs)}. ⚠️ Aucun identifiant de "
            f"contrat ne se déclare ici : la table vit HORS du dépôt.")
    return TableExceptionsContrat(**d)


def empreinte_table(lignes: Sequence[Mapping]) -> str:
    """L'empreinte d'une table d'exceptions par contrat.

    ⚠️ Elle porte le CONTENU, normalisé et trié : deux lectures de la même
    table doivent rendre le même hash, quel que soit l'ordre du fichier.
    """
    canon = []
    for ligne in lignes:
        idc = str(ligne.get('identifiant_contrat', ''))
        valeurs = '|'.join(
            f'{c}={ligne.get(c)!r}' for c in CHAMPS_CHARGEMENT)
        canon.append(f'{idc}::{valeurs}')
    charge = '\n'.join(sorted(canon)).encode('utf-8')
    return hashlib.sha256(charge).hexdigest()


# =============================================================================
#  VALIDER — la porte qui REFUSE
# =============================================================================

def _refuser_taux(nom: str, valeur, ou: str) -> float:
    if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
        raise TypeError(f"{ou} : `{nom}` doit être un nombre, reçu {valeur!r}.")
    valeur = float(valeur)
    if valeur < 0:
        raise ValueError(f"{ou} : `{nom}` = {valeur} est négatif.")
    if nom == 'commission' and valeur >= 1.0:
        raise ValueError(
            f"{ou} : `commission` = {valeur} >= 1 — la prime commerciale "
            f"divise par (1 - commission).")
    return valeur


def valider_chargements(chargements, facteurs: Sequence, lob: str,
                        identifiant_contrat) -> None:
    """Refuse une déclaration de chargements qui ne peut pas être tenue.

    ⚠️⚠️ TOUT OU RIEN SUR LES TROIS. Déclarer `frais` sans `commission` est une
    déclaration à moitié faite, et le dépôt a déjà arbitré ce cas pour
    `Comportement` : *son absence n'est pas une erreur ; sa déclaration A
    MOITIÉ en est une.* Il n'y a rien à hériter au niveau général — c'est LUI
    la racine.

    ⚠️⚠️ ET LES DEUX SENS DU ROUTAGE, comme pour le régime fiscal : une
    exception sur une modalité qui n'existe pas est une règle qui **ne se
    déclenchera jamais**, donc un garde-fou qui n'en est pas.

    ⚠️⚠️ `identifiant_contrat` N'A PAS DE VALEUR PAR DÉFAUT, ET C'EST VOULU.
    Un `= None` laisserait un futur appelant rouvrir le trou en silence, et
    ce contrôle-ci existe précisément parce qu'un trou s'était ouvert en
    silence. Il n'y a **qu'un seul appelant** (`PlanTarifaire`, relevé par
    AST le 15/09/2026), et il possède le nom : le lui faire passer coûte un
    argument et ferme le cas.
    """
    if chargements is None:
        return
    ou = f"Plan '{lob}', bloc `chargements`"

    # ── le niveau général : les trois, ou le refus ────────────────────────
    presents = [c for c in CHAMPS_CHARGEMENT
                if getattr(chargements, c, None) is not None]
    if len(presents) != len(CHAMPS_CHARGEMENT):
        manquants = [c for c in CHAMPS_CHARGEMENT if c not in presents]
        raise ValueError(
            f"{ou} : déclaration INCOMPLÈTE — il manque {manquants}. Le "
            f"niveau général est la racine dont les exceptions héritent : il "
            f"n'a lui-même rien à hériter. Déclarez les trois "
            f"({', '.join(CHAMPS_CHARGEMENT)}), ou ne déclarez pas de "
            f"chargements du tout — la prime pure reste publiée dans les deux "
            f"cas.")
    for c in CHAMPS_CHARGEMENT:
        _refuser_taux(c, getattr(chargements, c), ou)
    if not str(getattr(chargements, 'declare_par', '') or '').strip():
        raise ValueError(
            f"{ou} : `declare_par` est obligatoire — un chargement décide du "
            f"prix payé, et un régulateur demande QUI l'a fixé. Déclarez un "
            f"RÔLE (« Direction Technique »), jamais un nom de personne : ce "
            f"fichier est versionné.")
    if not str(getattr(chargements, 'declare_le', '') or '').strip():
        raise ValueError(f"{ou} : `declare_le` est obligatoire (AAAA-MM-JJ).")

    # ── les exceptions par CRITÈRE ────────────────────────────────────────
    exc = getattr(chargements, 'exceptions', None)
    if exc is not None:
        if not isinstance(exc, ExceptionsChargements):
            raise TypeError(
                f"{ou} : `exceptions` doit être un bloc `selon:`/`cas:`.")
        par_nom = {getattr(f, 'nom', None): f for f in facteurs}
        facteur = par_nom.get(exc.selon)
        if facteur is None:
            raise ValueError(
                f"{ou} : les exceptions portent SELON '{exc.selon}', qui n'est "
                f"pas un facteur déclaré du plan (facteurs : "
                f"{', '.join(sorted(n for n in par_nom if n)) or 'aucun'}). "
                f"Une exception sur un facteur inexistant ne se déclencherait "
                f"jamais.")
        modalites = tuple(getattr(facteur, 'modalites', None) or ())
        if not modalites:
            raise ValueError(
                f"{ou} : le facteur '{exc.selon}' ne déclare aucune modalité. "
                f"Une exception se pose sur un axe CATÉGORIEL énuméré ; sur un "
                f"facteur continu, il n'y a rien à désigner.")
        fantomes = sorted({m for m, _ in exc.cas} - set(modalites))
        if fantomes:
            raise ValueError(
                f"{ou} : exception(s) déclarée(s) pour {fantomes}, qui ne sont "
                f"PAS des modalités de '{exc.selon}' ({', '.join(modalites)}). "
                f"Une règle écrite pour une modalité inexistante ne se "
                f"déclenche jamais : elle a l'apparence d'un garde-fou sans en "
                f"être un.")
        vues = [m for m, _ in exc.cas]
        if len(vues) != len(set(vues)):
            doubles = sorted({m for m in vues if vues.count(m) > 1})
            raise ValueError(
                f"{ou} : {doubles} porte(nt) DEUX exceptions. Laquelle "
                f"s'applique deviendrait une affaire d'ordre dans le code, "
                f"invisible depuis le document signé.")
        for modalite, cas in exc.cas:
            place = f"{ou}, exception '{modalite}'"
            repris = [c for c in CHAMPS_CHARGEMENT
                      if getattr(cas, c, None) is not None]
            if not repris:
                raise ValueError(
                    f"{place} : ne redéclare AUCUN des trois chargements. Une "
                    f"exception qui ne change rien n'est pas une exception ; "
                    f"elle ferait croire à une dérogation qui n'existe pas.")
            for c in repris:
                _refuser_taux(c, getattr(cas, c), place)
            for champ in ('motif', 'declare_par', 'declare_le'):
                if not str(getattr(cas, champ, '') or '').strip():
                    raise ValueError(
                        f"{place} : `{champ}` est obligatoire. Une dérogation "
                        f"au taux général sans motif ni auteur ni date n'est "
                        f"pas opposable.")

    # ── la table par CONTRAT ──────────────────────────────────────────────
    tab = getattr(chargements, 'exceptions_par_contrat', None)
    if tab is not None:
        if not isinstance(tab, TableExceptionsContrat):
            raise TypeError(f"{ou} : `exceptions_par_contrat` mal formé.")
        # ⚠️⚠️ LE MÊME DEUX-SENS QUE CI-DESSUS, ET IL MANQUAIT PRÉCISÉMENT
        # LÀ OÙ IL COÛTE LE PLUS. `chargements_du_contrat` joint la table au
        # portefeuille par `plan.identifiant_contrat` : sans ce nom, `cle`
        # vaut `None`, `ligne` vaut `None`, et **le taux GÉNÉRAL s'applique
        # sans un mot**. La déclaration est pourtant scellée (sha256), signée
        # par un rôle et datée — tout ce qu'un régulateur demande.
        #   *Mesuré le 15/09/2026, deux plans identiques à ce nom près, même
        #   contrat, même table : prime HT 438,62 EUR contre 571,56 EUR, soit
        #   **+132,94 EUR et +30,3 %** payés par le contrat qui avait une
        #   dérogation signée.*
        # ⚠️ Et c'est le défaut que cette fonction DÉNONCE deux fois plus
        # haut, dans ses propres mots : « Une règle écrite pour une modalité
        # inexistante ne se déclenche jamais : elle a l'apparence d'un
        # garde-fou sans en être un. » Elle ne se l'appliquait pas.
        if not str(identifiant_contrat or '').strip():
            raise ValueError(
                f"{ou} : une table d'exceptions PAR CONTRAT est déclarée "
                f"({tab.nb_contrats} contrat(s), source {tab.source!r}), mais "
                f"le plan ne déclare AUCUN `identifiant_contrat`. La table se "
                f"joint au portefeuille par ce nom et par lui seul : sans "
                f"lui, elle ne s'appliquerait JAMAIS, et chaque contrat "
                f"qu'elle nomme paierait le taux général — en silence. "
                f"Déclarez `identifiant_contrat` sur le plan, ou retirez "
                f"`exceptions_par_contrat`.")
        emp = str(tab.empreinte_sha256 or '')
        if len(emp) != 64 or any(c not in '0123456789abcdef' for c in emp):
            raise ValueError(
                f"{ou} : `empreinte_sha256` doit être 64 hexadécimaux, reçu "
                f"{emp!r}. Sans elle, la déclaration signerait une table et le "
                f"calcul en appliquerait une autre.")
        if not isinstance(tab.nb_contrats, int) or tab.nb_contrats <= 0:
            raise ValueError(
                f"{ou} : `nb_contrats` doit être un entier > 0.")
        for champ in ('source', 'declare_par', 'declare_le'):
            if not str(getattr(tab, champ, '') or '').strip():
                raise ValueError(f"{ou} : `{champ}` est obligatoire.")


# =============================================================================
#  RÉSOUDRE POUR UN CONTRAT
# =============================================================================

#: L'origine du taux appliqué — publiée à côté du prix.
GENERAL = 'general'
EXCEPTION_CRITERE = 'exception_critere'
EXCEPTION_CONTRAT = 'exception_contrat'
NON_DECLARE = 'non_declare'


def chargements_du_contrat(plan, contrat: Mapping | None = None,
                           table: Mapping | None = None) -> tuple:
    """Les trois chargements applicables à CE contrat, et d'où ils viennent.

    Rend ``(valeurs, origine, detail)`` :
      · ``valeurs``  un dict des trois chargements, ou ``None`` si le plan
        n'en déclare aucun — et alors **aucune prime commerciale ne sort** ;
      · ``origine``  `general`, `exception_critere`, `exception_contrat` ou
        `non_declare` ;
      · ``detail``   le cas appliqué (motif, auteur, date), ou ``None``.

    ⚠️⚠️ L'ORDRE DE PRIORITÉ, ET IL EST DÉCLARÉ : la table par CONTRAT prime
    sur l'exception par CRITÈRE, qui prime sur le général. Le plus SPÉCIFIQUE
    l'emporte — un client qui nomme un contrat précis a voulu ce contrat
    précis, pas la moyenne de son segment.

    ⚠️ `table` est le contenu DÉJÀ CHARGÉ et DÉJÀ VÉRIFIÉ (voir
    :func:`empreinte_table`). Cette fonction ne lit aucun fichier : le socle
    ne va pas chercher des données personnelles de lui-même.
    """
    ch = getattr(plan, 'chargements', None) if plan is not None else None
    if ch is None:
        return None, NON_DECLARE, None

    base = {c: float(getattr(ch, c)) for c in CHAMPS_CHARGEMENT}
    if contrat is None:
        return base, GENERAL, None

    # ── le plus spécifique d'abord : la table par contrat ─────────────────
    tab = getattr(ch, 'exceptions_par_contrat', None)
    if tab is not None and table:
        idc = getattr(plan, 'identifiant_contrat', None)
        cle = contrat.get(idc) if idc else None
        ligne = table.get(cle) if cle is not None else None
        if ligne:
            valeurs = dict(base)
            repris = []
            for c in CHAMPS_CHARGEMENT:
                if ligne.get(c) is not None:
                    valeurs[c] = float(ligne[c])
                    repris.append(c)
            if repris:
                return valeurs, EXCEPTION_CONTRAT, {
                    'champs': tuple(repris),
                    'motif': str(ligne.get('motif', '')),
                    'source': tab.source,
                    'declare_par': tab.declare_par,
                    'declare_le': tab.declare_le}

    # ── puis l'exception par critère ──────────────────────────────────────
    exc = getattr(ch, 'exceptions', None)
    if exc is not None:
        cas = exc.pour(contrat.get(exc.selon))
        if cas is not None:
            valeurs = dict(base)
            repris = [c for c in CHAMPS_CHARGEMENT
                      if getattr(cas, c, None) is not None]
            for c in repris:
                valeurs[c] = float(getattr(cas, c))
            return valeurs, EXCEPTION_CRITERE, {
                'champs': tuple(repris),
                'selon': exc.selon,
                'modalite': contrat.get(exc.selon),
                'motif': cas.motif,
                'declare_par': cas.declare_par,
                'declare_le': cas.declare_le}

    return base, GENERAL, None


# =============================================================================
#  LA PHRASE PUBLIABLE — source unique des surfaces signées
# =============================================================================

def synthese_chargements(plan, contrat: Mapping | None = None,
                         table: Mapping | None = None) -> str:
    """Ce qui a été appliqué, d'où ça vient et qui l'a déclaré.

    ⚠️ SOURCE UNIQUE, comme `synthese_regime_fiscal` et `synthese_mapping` :
    deux rédactions du même fait finissent par en dire deux choses.
    """
    valeurs, origine, detail = chargements_du_contrat(plan, contrat, table)
    lob = getattr(plan, 'lob', '?')
    if valeurs is None:
        return (
            f"CHARGEMENTS NON DECLARES au plan '{lob}' : aucune prime "
            f"commerciale n'est calculee. Frais, commission et marge "
            f"dependent du client et de son reseau de distribution -- ce sont "
            f"des decisions commerciales, pas des faits actuariels, et le "
            f"systeme ne les devine pas. La prime PURE, elle, est publiee : "
            f"elle ne depend d'aucune declaration. Declarez `chargements` au "
            f"plan pour obtenir la prime commerciale.")
    ch = plan.chargements
    phrase = (
        f"Chargements appliques : frais {100 * valeurs['frais']:.4g} %, "
        f"commission {100 * valeurs['commission']:.4g} %, "
        f"marge {100 * valeurs['marge']:.4g} % -- declares par "
        f"{ch.declare_par} le {ch.declare_le}.")
    if origine == EXCEPTION_CRITERE:
        phrase += (
            f" ⚠ EXCEPTION appliquee sur {detail['selon']} = "
            f"{detail['modalite']!r} : {', '.join(detail['champs'])} "
            f"redeclare(s), motif << {detail['motif']} >>, par "
            f"{detail['declare_par']} le {detail['declare_le']}.")
    elif origine == EXCEPTION_CONTRAT:
        phrase += (
            f" ⚠ EXCEPTION PAR CONTRAT appliquee : "
            f"{', '.join(detail['champs'])} redeclare(s), motif "
            f"<< {detail['motif']} >>, table {detail['source']!r} declaree par "
            f"{detail['declare_par']} le {detail['declare_le']}.")
    return phrase
