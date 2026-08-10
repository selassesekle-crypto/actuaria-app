# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 : LE REGISTRE DE GROUPES, PERSISTANT ET APPEND-ONLY
=============================================================================

CE QUI EST SCELLÉ À LA NAISSANCE D'UN GROUPE NE SE RECALCULE PLUS. §53 :
« si, et seulement si, **à la date de la création du groupe** » — le test
d'éligibilité se passe UNE FOIS. §16 et §25 de même : « au moment de la
comptabilisation initiale ». Un groupe créé en 2024 doit se retrouver en 2027
avec son verdict et sa classe INCHANGÉS, sinon la plateforme reclasse
silencieusement d'un exercice à l'autre et aucun rapprochement ne le rattrape.

⚠️ MAIS §24 SCELLE LA COMPOSITION, PAS LA TAILLE. « L'entité doit constituer
les groupes au moment de la comptabilisation initiale et AJOUTER des contrats
aux groupes par application du §28. L'entité ne doit pas en REVOIR la
composition par la suite. » Ce qui est interdit, c'est de sortir un contrat ou
de le reclasser — pas au groupe de grossir. D'où un magasin **append-only** et
non figé. Les effets de l'entrée d'un contrat vivent dans `entree.py` (§28) :
il rejoint un groupe ou en crée un, jamais rien d'autre, et une entrée hors de
sa période de reconnaissance est TRACÉE sans être bloquée. La révision du taux
initial que §28 entraîne selon B73 n'est PAS construite : mesuré, son seul
usage possible dans le périmètre publié est §56, qui s'exempte lui-même pour
les contrats annuels — et elle exigerait un magasin de courbes indexé par
date, que le socle n'a pas.

⚠️ LES TROIS INVARIANTS, ET C'EST LEUR MÉCANIQUE QUI COMPTE, PAS LEUR ÉNONCÉ.

  1. AUCUN MONTANT. Le registre répond à « quels groupes existent et de quoi
     sont-ils faits » ; le magasin de clôtures répondra à « combien
     valaient-ils à cet arrêté ». Un euro ici ferait fuir la seconde question
     dans le premier objet. Un test fige la liste des champs.

  2. AUCUNE FONCTION DE MODIFICATION NI DE SUPPRESSION. Il n'y a pas de
     `modifier`, pas de `supprimer`, pas de `reclasser` — et ce n'est pas une
     convention de nommage : **c'est l'absence de la fonction qui rend le
     geste impossible**. Même discipline que `actualiser`, qui REFUSE une
     courbe avec VA plutôt que de documenter qu'il ne faut pas. Les structures
     sont des NamedTuple, donc immuables ; `ajouter` rend un NOUVEAU registre.

  3. AUCUNE RECLASSIFICATION SILENCIEUSE. Une clé de contrat déjà présente
     sous un AUTRE groupe est refusée, en nommant le contrat et les deux
     groupes. Sous le MÊME groupe, c'est une resoumission : elle est absorbée
     sans doublon et tracée.

⚠️ ET UN ATTRIBUT SCELLÉ NE SE LAISSE PAS ÉCRASER — MAIS LA DIVERGENCE SE DIT.
Si une dérivation nouvelle contredit le verdict §53 d'un groupe déjà
enregistré, le verdict SCELLÉ l'emporte (§53 s'apprécie à la création) et
l'écart est TRACÉ. Écraser serait non conforme ; ignorer en silence serait le
défaut que ce module existe pour empêcher.

⚠️ LA CONVENTION DE COHORTE DU REGISTRE GOUVERNE, PAS CELLE DE L'APPELANT.
Elle est fixée à l'ouverture et `ajouter` s'en sert : personne ne peut verser
des contrats sous une convention différente de celle qui a scellé les groupes
existants.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803. §16, §24, §25, §28,
§53. Format de fichier : JSON, un par (client, entité) — mesuré à 0,55 Mo pour
41 812 contrats et 6,51 Mo pour 500 000.
=============================================================================
"""

import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, NamedTuple, Optional, Tuple

from core.arrete import Arrete, iso, lire as lire_arrete
from normes.ifrs17.socle.confirmation import Confirmation, verifier
from normes.ifrs17.socle.entree import (analyser,
                                        trace_reconnaissance_tardive)
from normes.ifrs17.socle.groupe import (
    CONVENTION_CALENDAIRE, CleGroupe, ConventionCohorte, cle_de_ligne,
    date_emission_de_ligne, deriver)

#: Version du format de fichier. Elle est ÉCRITE dans le fichier : une
#: relecture doit pouvoir refuser un format qu'elle ne connaît pas plutôt que
#: de l'interpréter de travers.
FORMAT_REGISTRE = 'actuaria.ifrs17.registre/1'

TRACE_APPARTENANCE_NON_TRACABLE = (
    "appartenance non traçable — `identifiant_contrat` absent : la "
    "reclassification silencieuse ne peut pas être détectée sur ce groupe, "
    "et une resoumission du même inventaire compterait deux fois")


class Membre(NamedTuple):
    """Un contrat dans un groupe. ⚠️ `arrete_entree` n'est pas décoratif :
    sans lui, on ne peut pas reconstituer la moyenne pondérée de B73 telle
    qu'elle était à un arrêté passé, donc pas rejouer une clôture."""
    cle_contrat:   str
    date_emission: str          # 'AAAA-MM-JJ'
    arrete_entree: str          # 'AAAA-MM-JJ'


class GroupeEnregistre(NamedTuple):
    """Un groupe et ses attributs scellés. ⚠️ AUCUN MONTANT."""
    cle:               CleGroupe
    date_compta_25:    Optional[str]     # 'AAAA-MM-JJ', §25
    origine_date_25:   str
    eligibilite_paa:   str               # §53, scellé
    motif_eligibilite: str
    arrete_creation:   str               # quand le groupe est né
    nb_lignes:         int               # des lignes, pas des euros
    membres:           Tuple[Membre, ...]
    traces:            Tuple[str, ...]


class Registre(NamedTuple):
    """Le registre d'une entité. Immuable : `ajouter` en rend un nouveau.

    ⚠️ `confirmations` est une SUITE, append-only : une confirmation ne se
    corrige pas, on en ajoute une. Le registre répond donc à « qui a scellé
    quoi, et quand » pour CHAQUE versement, pas seulement pour le premier.
    """
    client:        str
    entite:        str
    convention:    ConventionCohorte
    groupes:       Tuple[GroupeEnregistre, ...]
    confirmations: Tuple[Confirmation, ...] = ()


class RefusRegistre(Exception):
    """Le registre refuse d'enregistrer — jamais en silence."""

    def __init__(self, motif: str, message: str):
        self.motif = motif
        super().__init__(message)


MOTIF_RECLASSIFICATION = 'RECLASSIFICATION'
MOTIF_FORMAT_INCONNU = 'FORMAT_INCONNU'
MOTIF_CLE_DIVERGENTE = 'CLE_DIVERGENTE'


# =============================================================================
#  OUVRIR, AJOUTER — ET RIEN D'AUTRE
# =============================================================================

def ouvrir(client: str, entite: str,
           convention: ConventionCohorte = CONVENTION_CALENDAIRE) -> Registre:
    """Un registre neuf. La convention est fixée ici et ne bougera plus."""
    if not str(client).strip() or not str(entite).strip():
        raise RefusRegistre(
            MOTIF_CLE_DIVERGENTE,
            "Un registre s'identifie par (client, entité, convention de "
            "cohorte). Le client et l'entité ne peuvent pas être vides : "
            "IFRS 17 se publie par entité juridique (§78).")
    return Registre(str(client).strip(), str(entite).strip(), convention, ())


def ajouter(registre: Registre, lignes: Iterable[Mapping], arrete,
            confirmation: Optional[Confirmation] = None,
            *, critere_16b_declare: bool = False) -> Registre:
    """Verse un inventaire dans le registre et rend un NOUVEAU registre.

    ⚠️ C'est la SEULE opération d'écriture du module. Il n'existe ni
    `modifier`, ni `supprimer`, ni `reclasser` : le geste est impossible
    parce que la fonction n'existe pas.

    ⚠️ ET C'EST L'ACTE QUI SCELLE, donc celui qui exige une signature. La
    lecture (`lecture_inventaire`) et la dérivation (`groupe`) restent
    accessibles sans confirmation : un client dépose, voit son diagnostic et
    ses groupes, et ne signe qu'au moment où l'irréversible commence.

    La convention employée est celle DU REGISTRE, jamais celle de l'appelant.
    """
    arr = arrete if isinstance(arrete, Arrete) else lire_arrete(arrete)
    quand = iso(arr)
    verifier(confirmation, quand)
    lignes = list(lignes)

    derives = deriver(lignes, convention=registre.convention,
                      critere_16b_declare=critere_16b_declare)
    membres_par_cle = _membres_par_cle(lignes, registre.convention, quand)
    tardives = _traces_entree(registre, lignes, arr)

    _refuser_si_reclassification(registre, membres_par_cle)

    existants = {g.cle: g for g in registre.groupes}
    fusionnes: List[GroupeEnregistre] = []

    for d in derives:
        nouveaux = membres_par_cle.get(d.cle, ())
        ancien = existants.pop(d.cle, None)
        base = _traces(d.traces, nouveaux, d.nb_lignes) \
            + tardives.get(d.cle, ())
        if ancien is None:
            fusionnes.append(GroupeEnregistre(
                cle=d.cle,
                date_compta_25=d.date_compta_25.isoformat()
                if d.date_compta_25 else None,
                origine_date_25=d.origine_date_25,
                eligibilite_paa=d.eligibilite_paa,
                motif_eligibilite=d.motif_eligibilite,
                arrete_creation=quand,
                nb_lignes=d.nb_lignes,
                membres=nouveaux,
                traces=tuple(sorted(set(base)))))
        else:
            fusionnes.append(_absorber(ancien, d, nouveaux, quand, base))

    fusionnes.extend(existants.values())
    return registre._replace(
        groupes=tuple(sorted(fusionnes, key=lambda g: g.cle)),
        confirmations=registre.confirmations + (confirmation,))


def _traces(base: Tuple[str, ...], membres: Tuple[Membre, ...],
            nb_lignes: int) -> Tuple[str, ...]:
    """Les traces du groupe, plus celle de l'appartenance intraçable."""
    t = set(base)
    if len(membres) < nb_lignes:
        t.add(TRACE_APPARTENANCE_NON_TRACABLE)
    return tuple(sorted(t))


def _traces_entree(registre: Registre, lignes: List[Mapping],
                   arr: Arrete) -> Dict[CleGroupe, Tuple[str, ...]]:
    """Les traces de §28 : ce qui rejoint, ce qui crée, ce qui arrive tard.

    ⚠️ Aucune de ces traces ne refuse quoi que ce soit. §28 autorise l'ajout
    après la date de clôture ; ce qu'il situe dans une période, c'est le
    MOMENT de l'ajout, et un écart relève d'IAS 8.
    """
    cles = {g.cle for g in registre.groupes}
    par_cle: Dict[CleGroupe, set] = {}
    for rang, ligne in enumerate(lignes, 1):
        e = analyser(cles, ligne, registre.convention, arr.valeur, rang)
        t = trace_reconnaissance_tardive(e)
        if t:
            par_cle.setdefault(e.cle, set()).add(t)
    return {c: tuple(sorted(t)) for c, t in par_cle.items()}


def _absorber(ancien: GroupeEnregistre, derive, nouveaux: Tuple[Membre, ...],
              quand: str, base: Tuple[str, ...] = ()) -> GroupeEnregistre:
    """Ajoute des membres à un groupe existant SANS toucher à ses scellés.

    ⚠️ Le verdict §53 et la date §25 de l'ancien l'emportent — ils ont été
    établis à la création du groupe et §53 s'apprécie à cette date. Une
    dérivation nouvelle qui les contredit ne les écrase pas : elle est TRACÉE.
    """
    connus = {m.cle_contrat for m in ancien.membres}
    frais = tuple(m for m in nouveaux if m.cle_contrat not in connus)
    deja = len(nouveaux) - len(frais)

    traces = set(ancien.traces) | set(base)
    if derive.eligibilite_paa != ancien.eligibilite_paa:
        traces.add(
            f"verdict §53 SCELLÉ à {ancien.eligibilite_paa} le "
            f"{ancien.arrete_creation} ; la dérivation du {quand} dit "
            f"{derive.eligibilite_paa} — l'attribut scellé est conservé "
            f"(§53 s'apprécie à la date de création du groupe)")
    if deja:
        traces.add(
            f"{deja} contrat(s) déjà enregistré(s) dans ce groupe au "
            f"{quand} — resoumission absorbée, aucun doublon")

    return ancien._replace(
        nb_lignes=ancien.nb_lignes + derive.nb_lignes - deja,
        membres=ancien.membres + frais,
        traces=tuple(sorted(traces)))


def _membres_par_cle(lignes: List[Mapping], convention: ConventionCohorte,
                     quand: str) -> Dict[CleGroupe, Tuple[Membre, ...]]:
    """L'appartenance, quand elle est traçable.

    Sans `identifiant_contrat`, on ne peut pas nommer un contrat : le groupe
    est enregistré avec son compte de lignes et la trace qui dit que
    l'appartenance n'est pas suivie.

    ⚠️ Le rattachement ligne → groupe vient de `cle_de_ligne`, dans `groupe`,
    et pas d'une seconde copie de la règle ici : sinon la classe par défaut
    de §16 vivrait en deux exemplaires, et l'une des deux dériverait un jour.
    """
    par_cle: Dict[CleGroupe, List[Membre]] = {}
    for rang, ligne in enumerate(lignes, 1):
        ident = ligne.get('identifiant_contrat')
        if ident is None or str(ident).strip() == '':
            continue
        cle = cle_de_ligne(ligne, convention, rang)
        emission = date_emission_de_ligne(ligne)
        par_cle.setdefault(cle, []).append(
            Membre(str(ident).strip(), emission.isoformat(), quand))
    return {c: tuple(m) for c, m in par_cle.items()}


def _refuser_si_reclassification(
        registre: Registre,
        membres_par_cle: Dict[CleGroupe, Tuple[Membre, ...]]) -> None:
    """Une clé de contrat ne change jamais de groupe (§24)."""
    place = {m.cle_contrat: g.cle for g in registre.groupes
             for m in g.membres}
    for cle, membres in membres_par_cle.items():
        for m in membres:
            ancienne = place.get(m.cle_contrat)
            if ancienne is not None and ancienne != cle:
                raise RefusRegistre(
                    MOTIF_RECLASSIFICATION,
                    f"Le contrat « {m.cle_contrat} » est enregistré dans le "
                    f"groupe « {ancienne.texte} » et se présente sous "
                    f"« {cle.texte} ». IFRS 17 §24 : l'entité « ne doit pas "
                    f"revoir la composition » d'un groupe par la suite. "
                    f"Reclasser un contrat déjà enregistré est interdit — "
                    f"vérifiez sa date d'émission, son portefeuille ou sa "
                    f"classe de profitabilité dans l'inventaire fourni.")


def groupe(registre: Registre, cle: CleGroupe) -> GroupeEnregistre:
    """Un groupe par sa clé. Lève sur une clé absente, plutôt qu'un défaut."""
    for g in registre.groupes:
        if g.cle == cle:
            return g
    raise KeyError(
        f"Groupe absent du registre : « {cle.texte} ». Le registre en "
        f"contient {len(registre.groupes)}.")


# =============================================================================
#  ÉCRIRE ET RELIRE
# =============================================================================

def _en_dict(registre: Registre) -> Dict:
    """La forme sérialisée — ordre FIXE, pour que deux écritures du même
    registre rendent les mêmes octets. Un livrable auditable ne peut pas
    changer de forme sans changer de fond."""
    return {
        'format': FORMAT_REGISTRE,
        'client': registre.client,
        'entite': registre.entite,
        'convention_cohorte': {
            'mois_debut': registre.convention.mois_debut,
            'libelle': registre.convention.libelle,
        },
        'confirmations': [
            {'actuaire_resp': c.actuaire_resp, 'arrete': c.arrete,
             'correspondances': [list(x) for x in c.correspondances]}
            for c in registre.confirmations
        ],
        'groupes': [
            {
                'portefeuille': g.cle.portefeuille,
                'classe_16': g.cle.classe_16,
                'cohorte': g.cle.cohorte,
                'date_compta_25': g.date_compta_25,
                'origine_date_25': g.origine_date_25,
                'eligibilite_paa': g.eligibilite_paa,
                'motif_eligibilite': g.motif_eligibilite,
                'arrete_creation': g.arrete_creation,
                'nb_lignes': g.nb_lignes,
                'traces': list(g.traces),
                'membres': [
                    {'cle_contrat': m.cle_contrat,
                     'date_emission': m.date_emission,
                     'arrete_entree': m.arrete_entree}
                    for m in sorted(g.membres)
                ],
            }
            for g in sorted(registre.groupes, key=lambda x: x.cle)
        ],
    }


def ecrire(registre: Registre, chemin) -> Path:
    """Écrit le registre en JSON. Déterministe : mêmes données, mêmes octets."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps(_en_dict(registre), ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8')
    return chemin


def relire(chemin) -> Registre:
    """Relit un registre écrit par `ecrire`. Refuse un format inconnu."""
    brut = json.loads(Path(chemin).read_text(encoding='utf-8'))
    fmt = brut.get('format')
    if fmt != FORMAT_REGISTRE:
        raise RefusRegistre(
            MOTIF_FORMAT_INCONNU,
            f"Format de registre inconnu : « {fmt} ». Ce module lit "
            f"« {FORMAT_REGISTRE} ». Interpréter un format qu'on ne connaît "
            f"pas reviendrait à deviner des attributs scellés.")
    conv = brut['convention_cohorte']
    return Registre(
        client=brut['client'], entite=brut['entite'],
        convention=ConventionCohorte(int(conv['mois_debut']),
                                     conv['libelle']),
        confirmations=tuple(
            Confirmation(c['actuaire_resp'], c['arrete'],
                         tuple(tuple(x) for x in c['correspondances']))
            for c in brut.get('confirmations', ())),
        groupes=tuple(
            GroupeEnregistre(
                cle=CleGroupe(g['portefeuille'], g['classe_16'],
                              g['cohorte']),
                date_compta_25=g['date_compta_25'],
                origine_date_25=g['origine_date_25'],
                eligibilite_paa=g['eligibilite_paa'],
                motif_eligibilite=g['motif_eligibilite'],
                arrete_creation=g['arrete_creation'],
                nb_lignes=int(g['nb_lignes']),
                membres=tuple(Membre(m['cle_contrat'], m['date_emission'],
                                     m['arrete_entree'])
                              for m in g['membres']),
                traces=tuple(g['traces']))
            for g in brut['groupes']))


def resume(registre: Registre) -> str:
    """Ce que le registre contient, dit à un actuaire."""
    total = sum(g.nb_lignes for g in registre.groupes)
    suivis = sum(len(g.membres) for g in registre.groupes)
    dernier = registre.confirmations[-1] if registre.confirmations else None
    lignes = [
        f"REGISTRE — {registre.client} / {registre.entite}",
        f"  convention de cohorte : {registre.convention.libelle} (§22)",
        f"  {len(registre.confirmations)} confirmation(s), la dernière par "
        f"{dernier.actuaire_resp} au {dernier.arrete}"
        if dernier else "  aucune confirmation",
        f"  {len(registre.groupes)} groupe(s), {total} ligne(s), "
        f"{suivis} contrat(s) suivi(s) nominativement",
        "",
    ]
    for g in registre.groupes:
        lignes.append(f"  {g.cle.texte}   {g.nb_lignes} ligne(s), "
                      f"né le {g.arrete_creation}")
        lignes.append(f"      §25 : {g.date_compta_25 or '—'}   "
                      f"§53 : {g.eligibilite_paa}")
        for t in g.traces:
            lignes.append(f"      ⚠️ {t}")
    return '\n'.join(lignes)


#: ⚠️ LA SURFACE PUBLIQUE, CLOSE ET VÉRIFIÉE PAR UN TEST. Toute fonction
#: ajoutée ici doit l'être délibérément — et aucune ne modifie ni ne supprime.
API_PUBLIQUE = ('ouvrir', 'ajouter', 'groupe', 'ecrire', 'relire', 'resume')
