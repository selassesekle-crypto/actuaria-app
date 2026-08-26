# -*- coding: utf-8 -*-
"""
ActuarIA — Tarification · L'EN-TÊTE DU LIVRABLE : deux dates, une seule source
=============================================================================

Deux dates cohabitent dans un livrable de tarification, et les confondre est le
défaut `services/C1` (« Arrêté : » portait la date d'IMPRESSION, avec une heure) :

  · la DATE D'ARRÊTÉ  — la clôture à laquelle le tarif se rapporte. Une date de
    RÉFÉRENCE métier, déclarée par l'actuaire. Dérivée ici de `core/arrete.py`,
    jamais recalculée en local (source unique, comme le versionnage de schéma).
  · la DATE DE GÉNÉRATION — le moment d'impression du document. Une métadonnée,
    honnête, qui VARIE d'une exécution à l'autre. Exclue du contenu reproductible
    (empreinte du plan + primes) : deux exécutions rejouent le même contenu, seule
    « Généré le » change.

⚠️ L'ABSENCE D'ARRÊTÉ EST VISIBLE, JAMAIS MASQUÉE. Si aucun arrêté n'est déclaré,
le document dit « non déclaré » — il ne glisse PAS la date du jour sous l'étiquette
« Arrêté ». Un défaut par défaut silencieux serait l'étiquette qui ment, celle que
le versionnage de schéma a appris à refuser. On ne bloque pas la génération (pas de
`ArreteInvalide` ici) ; on rend l'absence lisible.

⚠️ CE MODULE NE DUPLIQUE PAS `core/arrete.py` — il l'enveloppe. Le parsing, la
validation et le libellé dérivé vivent là-bas, en un seul endroit.
"""
from datetime import datetime
from typing import Optional, Union
from datetime import date as _date

from core import arrete as _arrete

#: Ce qui s'affiche sous « Arrêté : » quand rien n'est déclaré. VISIBLE par choix.
ARRETE_NON_DECLARE = "non déclaré"


def libelle_arrete(declare: Optional[Union[str, _date]] = None) -> str:
    """Le libellé d'arrêté pour un bandeau ou un pied de page.

    · déclaré (texte, date, ou `Arrete`) → libellé DÉRIVÉ par `core/arrete.py`
      (ex. « T2 2026 » ou « 30/06/2026 »), jamais un horodatage à l'heure ;
    · absent (`None` / '') → « non déclaré », VISIBLE ;
    · déclaré mais illisible → « non déclaré (illisible : … ) », VISIBLE aussi —
      on ne bloque pas la génération, on nomme le problème dans le document.
    """
    if declare is None or (isinstance(declare, str) and not declare.strip()):
        return ARRETE_NON_DECLARE
    try:
        return _arrete.libelle(_arrete.lire(declare))
    except _arrete.ArreteInvalide:
        return f"{ARRETE_NON_DECLARE} (illisible : {declare})"


def genere_le() -> str:
    """La date de GÉNÉRATION — le vrai moment d'impression, à la minute.

    Elle figure sur TOUT document (arrêté déclaré ou non) : sans elle, on perd
    l'information de quand ce document précis a été produit. Elle VARIE d'un run
    à l'autre — c'est voulu, c'est une métadonnée d'impression, pas du contenu.
    """
    return datetime.now().strftime('%d/%m/%Y %H:%M')
