# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — IFRS 17 §28 : CE QUI ARRIVE QUAND UN CONTRAT ENTRE
=============================================================================

UN CONTRAT QUI ENTRE REJOINT LE GROUPE DE SA CLÉ, OU EN CRÉE UN. Il n'est
jamais refusé, et il ne provoque jamais de reclassement.

⚠️ IL N'EXISTE PAS DE « FENÊTRE FERMÉE » — ET C'EST UNE CORRECTION DE MA
PROPRE CONCEPTION. J'avais écrit, et fait valider, qu'un contrat de cohorte
2024 déclaré en 2027 créerait un NOUVEAU groupe de cohorte 2024, distinct du
premier, parce que la fenêtre serait close. En relisant le texte pour
l'implémenter, deux constats l'infirment :

  · §28 dit exactement l'inverse : « Sous réserve des §14 à 22, l'entité
    PEUT AJOUTER de nouveaux contrats au groupe APRÈS LA DATE DE CLÔTURE. »
    La seule réserve porte sur §14 à 22, c'est-à-dire sur la clé du groupe —
    que la cohorte 2024 satisfait précisément.
  · Relevé sur les 303 paragraphes de la norme : **AUCUN ne ferme un
    groupe**. La notion n'existe pas.

Et créer un second groupe de même clé aurait un coût propre : la clé
cesserait d'identifier un groupe, alors qu'elle EST son identité (§24).

CE QUI EST IRRÉGULIER DANS CE CAS N'EST DONC PAS L'APPARTENANCE, C'EST LA
DATE. §28 : « L'ajout d'un contrat doit se faire DANS LA PÉRIODE DE REPORTING
où ce contrat satisfait à l'un des critères énoncés au paragraphe 25. »
Déclarer en 2027 un contrat qui satisfaisait §25 en 2024, c'est une omission
d'exercice antérieur — matière d'IAS 8, pas de la constitution des groupes.
Le contrat entre, et le retard est NOMMÉ.

⚠️ RIEN N'EST STOCKÉ. Le retard se DÉRIVE de deux faits déjà enregistrés :
la période où §25 est satisfait, et l'arrêté d'entrée. C'est la leçon de D3 —
un état stocké peut contredire la donnée qui le détermine, un état dérivé ne
le peut pas.

RÉFÉRENCES — IFRS 17, annexe au règlement (UE) 2023/1803. §22, §24, §25, §28.
=============================================================================
"""

from collections.abc import Mapping
from datetime import date
from typing import NamedTuple

from normes.ifrs17.socle.groupe import (
    CleGroupe,
    ConventionCohorte,
    cle_de_ligne,
    cohorte,
    date_emission_de_ligne,
)

#: Les deux seuls effets possibles. Il n'y en a pas de troisième : ni refus,
#: ni reclassement, ni création d'un doublon de clé.
REJOINT = 'REJOINT'
CREE = 'CREE'

EFFETS = (REJOINT, CREE)


class Entree(NamedTuple):
    """Ce qu'une ligne d'inventaire fait en entrant dans un registre."""
    cle:              CleGroupe
    effet:            str          # REJOINT ou CREE
    periode_25:       str          # période où §25 est satisfait
    periode_entree:   str          # période de l'arrêté d'entrée
    retard_periodes:  int          # 0 si l'entrée est dans les temps


def _periode_25(ligne: Mapping, convention: ConventionCohorte) -> str:
    """La période de reporting où §25 est satisfait, sous la convention.

    §25 retient la PREMIÈRE de trois dates ; la plateforme ne dispose que du
    début de couverture (a). À défaut, on retombe sur la date d'émission —
    non pour deviner §25, mais parce que la cohorte suffit à situer la
    période, et qu'un contrat ne peut pas être reconnu avant d'être émis.
    """
    from normes.ifrs17.socle.groupe import _lire_date
    debut = _lire_date(ligne.get('debut_couverture'))
    if debut is None:
        debut = date_emission_de_ligne(ligne)
    return cohorte(convention, debut)


def _ecart_periodes(convention: ConventionCohorte, a: str, b: str) -> int:
    """Nombre de périodes entre deux étiquettes, `b` − `a`.

    Les étiquettes sont « 2026 » ou « 2025-26 » : leur première année suffit,
    puisqu'une période dure un an par construction (§22).
    """
    return int(b.split('-')[0]) - int(a.split('-')[0])


def analyser(cles_enregistrees: set[CleGroupe], ligne: Mapping,
             convention: ConventionCohorte, arrete_entree: date,
             rang: int = 1) -> Entree:
    """Ce qu'une ligne fait en entrant. Ne décide rien, ne refuse rien."""
    cle = cle_de_ligne(ligne, convention, rang)
    p25 = _periode_25(ligne, convention)
    pentree = cohorte(convention, arrete_entree)
    return Entree(
        cle=cle,
        effet=REJOINT if cle in cles_enregistrees else CREE,
        periode_25=p25,
        periode_entree=pentree,
        retard_periodes=max(0, _ecart_periodes(convention, p25, pentree)))


def trace_reconnaissance_tardive(entree: Entree) -> str | None:
    """La trace d'une entrée hors de sa période, ou None si elle est dans
    les temps.

    ⚠️ CE N'EST PAS UN REFUS. §28 autorise l'ajout après la date de clôture ;
    ce qu'il situe dans une période précise, c'est le MOMENT de l'ajout. Une
    entrée tardive est une omission d'exercice antérieur — IAS 8 — et elle se
    nomme plutôt qu'elle ne se bloque.
    """
    if entree.retard_periodes <= 0:
        return None
    return (
        f"reconnaissance tardive — le groupe « {entree.cle.texte} » reçoit à "
        f"l'arrêté {entree.periode_entree} des contrats qui satisfaisaient "
        f"§25 en {entree.periode_25}, soit {entree.retard_periodes} "
        f"période(s) plus tôt. §28 situe l'ajout « dans la période de "
        f"reporting où ce contrat satisfait à l'un des critères du §25 » : "
        f"l'écart relève d'une omission d'exercice antérieur (IAS 8), non de "
        f"la constitution des groupes. Le contrat est enregistré.")


def resume_entrees(entrees) -> str:
    """Ce que le versement a produit, dit à un actuaire."""
    entrees = list(entrees)
    rejoints = sum(1 for e in entrees if e.effet == REJOINT)
    crees = len({e.cle for e in entrees if e.effet == CREE})
    tardifs = [e for e in entrees if e.retard_periodes > 0]
    lignes = [
        f"ENTRÉES (§28) — {len(entrees)} ligne(s)",
        (f"  {rejoints} rejoignent un groupe existant, "
         f"{crees} groupe(s) créé(s)"),
    ]
    if tardifs:
        pires = max(e.retard_periodes for e in tardifs)
        lignes.append(
            f"  ⚠️ {len(tardifs)} ligne(s) en reconnaissance tardive, "
            f"jusqu'à {pires} période(s) — voir IAS 8")
    return '\n'.join(lignes)
