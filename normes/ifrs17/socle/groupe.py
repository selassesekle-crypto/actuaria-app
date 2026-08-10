# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : DÉRIVER LES GROUPES, L'UNITÉ DE COMPTE DE LA NORME
=============================================================================

IFRS 17 NE MESURE JAMAIS UN CONTRAT. §24 : « L'entité doit appliquer AUX
GROUPES de contrats qui ont été constitués par application des §14 à 23 les
dispositions relatives à la comptabilisation et à l'évaluation. » Le contrat
est l'intrant, le groupe est l'unité de compte — et tout ce qui suit, LRC,
élément de perte, revenu, rapprochements, se mesure par groupe.

TROIS ÉTAGES, DANS CET ORDRE :
  §14  le portefeuille  — contrats à risques similaires, gérés ensemble ;
  §16  la profitabilité — déficitaires à l'origine / sans possibilité
       importante de le devenir / les autres ;
  §22  la cohorte       — « ne pas classer dans un même groupe des contrats
       émis à plus d'un an d'intervalle ».

⚠️ LA CONVENTION DE COHORTE EST DÉCLARÉE, JAMAIS SUPPOSÉE. §22 pose une
contrainte GLISSANTE d'un an ; l'année civile est un usage de marché, pas le
texte. Un exercice décalé (avril-mars) est tout aussi conforme, et il produit
des groupes DIFFÉRENTS. Or le groupe est scellé à sa naissance : supposer la
convention reviendrait à sceller sur une hypothèse tacite.

⚠️ ET LE CONTRÔLE §22 EST DOUBLE SUR LA VOIE PRÉ-AGRÉGÉE, PAS SIMPLE. Un
ensemble dont la plage d'émission va du 15/11/2025 au 20/02/2026 dure trois
mois — il satisfait `max − min ≤ 1 an`. Mais sous convention calendaire ses
contrats relèvent de DEUX cohortes, donc de deux groupes. L'amplitude est
nécessaire, elle n'est pas suffisante :
    1. `max − min ≤ 1 an`                    — la règle littérale de §22 ;
    2. `cohorte(min) == cohorte(max)`        — l'ensemble ne chevauche pas
       deux cohortes sous la convention DÉCLARÉE.
C'est le second contrôle qui rend la convention opérante plutôt que
décorative : le même ensemble passe sous un exercice décalé et échoue sous
un calendaire.

⚠️ §16(b) RESTE VIDE SAUF CRITÈRE DÉCLARÉ. §18 pose, pour la PAA, une
PRÉSOMPTION de non-déficit : « l'entité doit supposer qu'aucun des contrats
du portefeuille n'est déficitaire […] à moins que les faits et les
circonstances n'indiquent le contraire ». Et §19, qui donne un critère
probabiliste, vise nommément les contrats NON évalués en PAA. Aucune valeur
par défaut chiffrée n'a donc de fondement : tout ce qui n'est pas déclaré
déficitaire va en (c), et la trace le dit.

⚠️ AUCUNE PERSISTANCE, AUCUN MONTANT. Ce module DÉRIVE ; il n'écrit rien et
ne porte pas un euro. La frontière avec le magasin de clôtures tient en une
phrase : le registre répond à « quels groupes existent et de quoi sont-ils
faits », le magasin à « combien valaient-ils à cet arrêté ». Un test verrouille
qu'aucun champ de `Groupe` ne porte de montant.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803, JO L 237 du
26.9.2023. §14, §16, §18, §19, §22, §24, §25, §53.
=============================================================================
"""

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Mapping, NamedTuple, Optional, Tuple

from core.arrete import FORMATS
from normes.ifrs17.socle.contrat import COUVERTURE_INDETERMINEE

# =============================================================================
#  §16 — LES TROIS CLASSES DE PROFITABILITÉ
# =============================================================================

CLASSE_16A = 'DEFICITAIRE'                   # §16 a)
CLASSE_16B = 'SANS_POSSIBILITE_IMPORTANTE'   # §16 b)
CLASSE_16C = 'AUTRES'                        # §16 c)

CLASSES_16 = (CLASSE_16A, CLASSE_16B, CLASSE_16C)

#: Ce que la plateforme retient faute de déclaration — la présomption de §18.
CLASSE_PAR_DEFAUT = CLASSE_16C

TRACE_16B_NON_DECLARE = (
    "critère §16(b) non déclaré — aucune scission (b)/(c) opérée ; "
    "présomption de non-déficit de §18 appliquée")


# =============================================================================
#  §22 — LA CONVENTION DE COHORTE
# =============================================================================

class ConventionCohorte(NamedTuple):
    """La fenêtre d'un an au sens de §22 — DÉCLARÉE, jamais supposée."""
    mois_debut: int          # 1 = année civile ; 4 = exercice avril-mars
    libelle:    str


CONVENTION_CALENDAIRE = ConventionCohorte(1, 'année civile')


def convention_exercice(mois_debut: int) -> ConventionCohorte:
    """Un exercice décalé — avril-mars se déclare `convention_exercice(4)`."""
    if not 1 <= mois_debut <= 12:
        raise ValueError(
            f"Mois de début d'exercice invalide : {mois_debut}. "
            f"Il se situe entre 1 (janvier) et 12 (décembre).")
    if mois_debut == 1:
        return CONVENTION_CALENDAIRE
    fin = mois_debut - 1
    return ConventionCohorte(
        mois_debut, f"exercice {mois_debut:02d}-{fin:02d}")


def cohorte(convention: ConventionCohorte, emission: date) -> str:
    """L'étiquette de cohorte d'une date d'émission, sous une convention.

    Année civile → « 2026 ». Exercice décalé → « 2026-27 », l'exercice étant
    nommé par l'année de son ouverture.
    """
    if convention.mois_debut == 1:
        return str(emission.year)
    an = emission.year if emission.month >= convention.mois_debut \
        else emission.year - 1
    return f"{an}-{(an + 1) % 100:02d}"


# =============================================================================
#  LE GROUPE
# =============================================================================

class CleGroupe(NamedTuple):
    """Ce qui identifie un groupe, et qui ne changera plus (§24)."""
    portefeuille: str
    classe_16:    str
    cohorte:      str

    @property
    def texte(self) -> str:
        return f"{self.portefeuille}|{self.classe_16}|{self.cohorte}"


#: Verdicts d'éligibilité PAA (§53). ⚠️ « NON_ETABLI » n'est pas « éligible » :
#: c'est l'aveu que la donnée ne permet pas de trancher.
PAA_ELIGIBLE = 'ELIGIBLE'
PAA_NON_ELIGIBLE = 'NON_ELIGIBLE'
PAA_NON_ETABLI = 'NON_ETABLI'


class Groupe(NamedTuple):
    """Un groupe dérivé. ⚠️ AUCUN MONTANT — voir l'en-tête du module.

    `nb_lignes` compte des lignes d'inventaire, pas des euros ; il sert au
    diagnostic et n'entre dans aucune évaluation.
    """
    cle:                CleGroupe
    date_compta_25:     Optional[date]
    origine_date_25:    str
    eligibilite_paa:    str
    motif_eligibilite:  str
    nb_lignes:          int
    traces:             Tuple[str, ...]


class RefusGroupe(Exception):
    """La dérivation ne peut pas produire de groupe conforme.

    Contrairement au lecteur d'inventaire, qui chiffre ce qu'il peut, il n'y
    a pas de groupe partiel : un ensemble qui enfreint §22 ne peut pas être
    « à moitié » une cohorte.
    """

    def __init__(self, motif: str, message: str):
        self.motif = motif
        super().__init__(message)


MOTIF_AMPLITUDE_22 = 'AMPLITUDE_22'
MOTIF_CHEVAUCHE_COHORTES = 'CHEVAUCHE_COHORTES'
MOTIF_SANS_PORTEFEUILLE = 'SANS_PORTEFEUILLE'
MOTIF_SANS_EMISSION = 'SANS_EMISSION'


# =============================================================================
#  LECTURE DES DATES — UNE SEULE SOURCE DE FORMATS
# =============================================================================

#: Mois français en toutes lettres. ⚠️ Table EXPLICITE plutôt que `%B` : ce
#: dernier dépend de la locale du système, donc du poste qui exécute — un
#: livrable actuariel ne peut pas dépendre de la langue de la machine.
MOIS_FR = {
    'janvier': 1, 'janv': 1, 'fevrier': 2, 'fev': 2, 'mars': 3,
    'avril': 4, 'avr': 4, 'mai': 5, 'juin': 6, 'juillet': 7, 'juil': 7,
    'aout': 8, 'septembre': 9, 'sept': 9, 'octobre': 10, 'oct': 10,
    'novembre': 11, 'nov': 11, 'decembre': 12, 'dec': 12,
}

#: Origine du calendrier Excel sous Windows. Excel compte les jours depuis le
#: 31/12/1899 avec un décalage d'un jour hérité d'un bogue de 1900, d'où cette
#: origine et non le 01/01/1900.
_ORIGINE_EXCEL = date(1899, 12, 30)

#: Bande de plausibilité d'un numéro de série Excel : du 01/01/1990 au
#: 31/12/2100. Hors d'elle, un nombre n'est pas une date mais un montant, un
#: identifiant ou un compte — le lire comme une date serait pire que de ne
#: rien lire.
_SERIE_MIN = (date(1990, 1, 1) - _ORIGINE_EXCEL).days
_SERIE_MAX = (date(2100, 12, 31) - _ORIGINE_EXCEL).days


def _sans_accent(texte: str) -> str:
    """Forme comparable d'un mois écrit en toutes lettres.

    ⚠️ IDIOME STANDARD, PAS UNE TABLE DE CORRESPONDANCE. J'avais d'abord
    écrit cinq substitutions à la main — elles auraient manqué « décembre »
    écrit avec un autre accent, ou n'importe quelle lettre non prévue.
    `unicodedata` couvre tout l'alphabet latin, et c'est un appel de
    bibliothèque, pas une règle recopiée.
    """
    return unicodedata.normalize('NFKD', texte) \
        .encode('ascii', 'ignore').decode('ascii')


def _lire_date(valeur) -> Optional[date]:
    """Une date de contrat, dans l'une des formes qu'un assureur produit.

    ⚠️ `FORMATS` vient de `arrete.py` : les formes TEXTUELLES sont une SEULE
    donnée pour tout le socle. Mais le TYPE diffère — un `Arrete` est la date
    à laquelle une entité arrête ses comptes, pas celle d'un contrat. On
    réemploie la liste, jamais le type.

    ⚠️ DEUX MÉCANISMES S'AJOUTENT ICI, ET SEULEMENT ICI, parce qu'ils ne sont
    pas des formats `strptime` et qu'ils naissent des fichiers de contrats :
    le NUMÉRO DE SÉRIE EXCEL — une colonne de dates lue en numérique — et le
    MOIS EN TOUTES LETTRES. Aucun des deux n'a de sens pour une date d'arrêté,
    qu'un humain saisit.
    """
    if valeur is None or valeur == '':
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur

    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return _depuis_serie_excel(float(valeur))

    brut = str(valeur).strip()
    if not brut or brut == COUVERTURE_INDETERMINEE:
        return None
    for motif, _ in FORMATS:
        try:
            longueur = 8 if motif == '%Y%m%d' else 10
            return datetime.strptime(brut[:longueur], motif).date()
        except ValueError:
            continue
    lu = _depuis_mois_en_lettres(brut)
    if lu is not None:
        return lu
    try:
        return _depuis_serie_excel(float(brut.replace(',', '.')))
    except ValueError:
        return None


def _depuis_serie_excel(n: float) -> Optional[date]:
    """Un numéro de série Excel → une date, si le nombre est plausible."""
    if not _SERIE_MIN <= n <= _SERIE_MAX:
        return None
    return _ORIGINE_EXCEL + timedelta(days=int(n))


def _depuis_mois_en_lettres(brut: str) -> Optional[date]:
    """« 15 mars 2026 », « 15-mars-2026 », « 15/janv/2026 »."""
    morceaux = re.split(r"[\s/.\-]+", _sans_accent(brut.lower()).strip())
    if len(morceaux) != 3:
        return None
    jour, mois, an = morceaux
    if mois not in MOIS_FR:
        return None
    try:
        return date(int(an), MOIS_FR[mois], int(jour))
    except ValueError:
        return None


def _un_an_apres(d: date) -> date:
    """La date un an plus tard, 29 février compris."""
    try:
        return d.replace(year=d.year + 1)
    except ValueError:                       # 29 février d'une année bissextile
        return d.replace(year=d.year + 1, day=28)


# =============================================================================
#  §53 — L'ÉLIGIBILITÉ, ET SON MOTIF
# =============================================================================

def _eligibilite(lignes: List[Mapping]) -> Tuple[str, str]:
    """Le verdict §53 b) d'un groupe, et le motif qui le justifie.

    §53 b) porte sur « la période de couverture de CHACUN des contrats du
    groupe » : il suffit d'un contrat plus long pour que la porte (b) se
    ferme. La porte (a) — écart non significatif avec le modèle général —
    reste ouverte en droit mais n'est pas évaluable ici : le groupe est
    alors SIGNALÉ, jamais évalué à tort (décision produit ⑦).
    """
    couvertures = []
    indeterminees = 0
    for ligne in lignes:
        fin_brute = ligne.get('fin_couverture')
        if str(fin_brute).strip() == COUVERTURE_INDETERMINEE:
            indeterminees += 1
            continue
        fin = _lire_date(fin_brute)
        debut = _lire_date(ligne.get('debut_couverture')) \
            or _lire_date(ligne.get('date_emission'))
        if fin is None or debut is None:
            continue
        couvertures.append((debut, fin))

    if indeterminees:
        return PAA_NON_ELIGIBLE, (
            f"{indeterminees} ligne(s) à couverture indéterminée : une durée "
            f"sans terme excède un an, §53 b) est fermé. La porte §53 a) "
            f"reste ouverte en droit mais n'est pas évaluable ici — groupe "
            f"signalé, non évalué.")
    if not couvertures:
        return PAA_NON_ETABLI, (
            "période de couverture non calculable — il manque `fin_couverture` "
            "ou une borne de début. §53 b) est DÉCLARÉ, non établi.")

    trop_longues = [(d, f) for d, f in couvertures if f > _un_an_apres(d)]
    if trop_longues:
        d, f = trop_longues[0]
        return PAA_NON_ELIGIBLE, (
            f"{len(trop_longues)} contrat(s) sur {len(couvertures)} couvrent "
            f"plus d'un an (ex. {d.isoformat()} → {f.isoformat()}) : §53 b) "
            f"est fermé. La porte §53 a) reste ouverte en droit mais n'est pas "
            f"évaluable ici — groupe signalé, non évalué.")
    return PAA_ELIGIBLE, (
        f"les {len(couvertures)} contrats couvrent au plus un an — §53 b) "
        f"vérifié, et non déclaré.")


# =============================================================================
#  §25 — LA DATE DE COMPTABILISATION INITIALE
# =============================================================================

def _date_25(lignes: List[Mapping]) -> Tuple[Optional[date], str]:
    """La première des trois dates de §25, et laquelle a servi.

    §25 : la PREMIÈRE de (a) début de la période de couverture, (b) échéance
    du premier paiement, (c) pour un groupe déficitaire, la date où il le
    devient. La plateforme ne dispose aujourd'hui que de (a) : les deux
    autres sont NOMMÉES comme non évaluables plutôt que passées sous silence.
    """
    debuts = [d for d in (_lire_date(l.get('debut_couverture'))
                          for l in lignes) if d]
    if not debuts:
        return None, ("§25 non établie — `debut_couverture` absent. Les "
                      "critères §25 b) et c) ne sont pas évaluables faute de "
                      "donnée sur l'échéance des primes.")
    return min(debuts), ("§25 a) — début de la période de couverture. Les "
                         "critères b) et c) ne sont pas évaluables faute de "
                         "donnée sur l'échéance des primes.")


# =============================================================================
#  §22 — LES DEUX CONTRÔLES DE LA VOIE PRÉ-AGRÉGÉE
# =============================================================================

def _controler_22(ligne: Mapping, convention: ConventionCohorte,
                  rang: int) -> Optional[str]:
    """Contrôle un ensemble pré-agrégé. Lève si §22 est rompu, sinon trace.

    DEUX contrôles, et le second est celui qui rend la convention opérante.
    """
    mini = _lire_date(ligne.get('date_emission_min'))
    maxi = _lire_date(ligne.get('date_emission_max'))
    if mini is None or maxi is None:
        return ("plage d'émission absente — §22 est DÉCLARÉ, non établi sur "
                "les ensembles pré-agrégés")
    if maxi > _un_an_apres(mini):
        raise RefusGroupe(
            MOTIF_AMPLITUDE_22,
            f"Ligne {rang} : l'ensemble réunit des contrats émis du "
            f"{mini.isoformat()} au {maxi.isoformat()}, soit plus d'un an. "
            f"IFRS 17 §22 interdit de classer dans un même groupe des "
            f"contrats émis à plus d'un an d'intervalle — cet ensemble en "
            f"réunit au moins deux qui ne peuvent pas y être. Scindez-le.")
    if cohorte(convention, mini) != cohorte(convention, maxi):
        raise RefusGroupe(
            MOTIF_CHEVAUCHE_COHORTES,
            f"Ligne {rang} : l'ensemble s'étend du {mini.isoformat()} au "
            f"{maxi.isoformat()} — moins d'un an, mais il chevauche les "
            f"cohortes « {cohorte(convention, mini)} » et "
            f"« {cohorte(convention, maxi)} » sous la convention "
            f"{convention.libelle}. Ses contrats relèvent de deux groupes "
            f"distincts (§22) : scindez-le, ou déclarez la convention qui "
            f"correspond à votre exercice.")
    return None


# =============================================================================
#  LA DÉRIVATION
# =============================================================================

def cle_de_ligne(ligne: Mapping, convention: ConventionCohorte,
                 rang: int = 1) -> CleGroupe:
    """La clé de groupe d'UNE ligne d'inventaire. Lève si elle n'en a pas.

    Existe pour que le rattachement ligne → groupe ait UNE seule définition :
    `deriver` l'emploie pour agréger, le registre pour tracer l'appartenance.
    Sans elle, la règle de classe par défaut vivrait en deux exemplaires — le
    motif que ce dépôt combat depuis les huit sources de taux.
    """
    portefeuille = str(ligne.get('portefeuille') or '').strip()
    if not portefeuille:
        raise RefusGroupe(
            MOTIF_SANS_PORTEFEUILLE,
            f"Ligne {rang} : aucun portefeuille. §14 demande de regrouper "
            f"les contrats à risques similaires, gérés ensemble.")
    emission = _lire_date(ligne.get('date_emission'))
    if emission is None:
        raise RefusGroupe(
            MOTIF_SANS_EMISSION,
            f"Ligne {rang} : date d'émission illisible « "
            f"{ligne.get('date_emission')} ». Sans elle, aucune cohorte "
            f"(§22).")
    classe = str(ligne.get('classe_profitabilite') or '').strip() \
        or CLASSE_PAR_DEFAUT
    return CleGroupe(portefeuille, classe, cohorte(convention, emission))


def date_emission_de_ligne(ligne: Mapping) -> Optional[date]:
    """La date d'émission d'une ligne, lue avec les formats du socle."""
    return _lire_date(ligne.get('date_emission'))


def deriver(lignes: Iterable[Mapping], *,
            convention: ConventionCohorte = CONVENTION_CALENDAIRE,
            critere_16b_declare: bool = False) -> Tuple[Groupe, ...]:
    """Un inventaire canonique → les groupes de §14-16-22, triés par clé.

    Ne persiste rien, ne calcule aucun montant. Lève `RefusGroupe` si un
    ensemble pré-agrégé enfreint §22 — il n'y a pas de groupe partiel.
    """
    par_cle: Dict[CleGroupe, List[Mapping]] = {}
    traces_par_cle: Dict[CleGroupe, set] = {}

    for rang, ligne in enumerate(lignes, 1):
        cle = cle_de_ligne(ligne, convention, rang)

        traces = set()
        if ligne.get('nb_contrats') is not None:
            trace = _controler_22(ligne, convention, rang)
            if trace:
                traces.add(trace)
        if not critere_16b_declare and cle.classe_16 == CLASSE_PAR_DEFAUT:
            traces.add(TRACE_16B_NON_DECLARE)

        par_cle.setdefault(cle, []).append(ligne)
        traces_par_cle.setdefault(cle, set()).update(traces)

    groupes = []
    for cle in sorted(par_cle):
        membres = par_cle[cle]
        d25, origine = _date_25(membres)
        verdict, motif = _eligibilite(membres)
        groupes.append(Groupe(
            cle=cle, date_compta_25=d25, origine_date_25=origine,
            eligibilite_paa=verdict, motif_eligibilite=motif,
            nb_lignes=len(membres),
            traces=tuple(sorted(traces_par_cle[cle]))))
    return tuple(groupes)


def resume(groupes: Tuple[Groupe, ...],
           convention: ConventionCohorte = CONVENTION_CALENDAIRE) -> str:
    """Ce que la dérivation a produit, dit à un actuaire."""
    lignes = [f"GROUPES DÉRIVÉS — {len(groupes)}, convention de cohorte : "
              f"{convention.libelle} (§22)", ""]
    for g in groupes:
        lignes.append(f"  {g.cle.texte}   {g.nb_lignes} ligne(s)")
        lignes.append(f"      §25 : {g.date_compta_25 or '—'} — "
                      f"{g.origine_date_25}")
        lignes.append(f"      §53 : {g.eligibilite_paa} — "
                      f"{g.motif_eligibilite}")
        for t in g.traces:
            lignes.append(f"      ⚠️ {t}")
    return '\n'.join(lignes)
