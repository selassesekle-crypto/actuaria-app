# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — LA DATE D'ARRÊTÉ DE L'ENTITÉ, UNE SEULE FOIS ET TYPÉE
=============================================================================

⚠️ CE MODULE NE CRÉE PAS UN CHAMP — IL FERME UNE DIVERGENCE. Relevé par le
code au 2026-08-07 : **26 formes distinctes sur 71 sites** portent ce qui est
la même notion, réparties sur les quatre directions et `core/` :

  · `arrete: str = ''`      — un LIBELLÉ LIBRE ('Q2 2026'), jamais validé,
                              jamais comparé ; le plus répandu ;
  · `date_arrete: str = ""` — une date typée… en DEUX formats coexistants,
                              '2026-07-31' et '31/12/2025' ;
  · `date_valorisation`     — la même notion sous un troisième nom, dans la
                              gouvernance de la courbe.

C'est le motif exact du chantier RFR, où huit sources de taux divergeaient.
Un libellé libre ne se compare pas, ne s'ordonne pas et ne sert pas de clé.

⚠️ ET UNE COLLISION DE NOMS QU'IL NE FAUT SURTOUT PAS FUSIONNER.
`CourbeRFR.date_arrete` (`core/courbe_rfr.py`) est la date DE LA COURBE —
l'arrêté EIOPA auquel elle a été publiée. Ce module porte la date d'arrêté
DE L'ENTITÉ — celle à laquelle elle établit ses comptes. Deux notions
distinctes qui partagent un nom : les confondre daterait les comptes sur le
calendrier d'EIOPA. Elles se RENCONTRENT (voir `iso()` ci-dessous), elles ne
se confondent pas.

⚠️ LE LIBELLÉ EST DÉRIVÉ, JAMAIS SAISI. C'est ce qui tue la divergence : un
`arrete: str = 'Q2 2026'` peut dire n'importe quoi, y compris contredire la
date qu'il accompagne. Ici le libellé se CALCULE à partir de la date, donc
les deux ne peuvent plus diverger.

⚠️ POURQUOI CE MODULE VIT DANS `core/` ET NON DANS `normes/ifrs17/`. Il y a
été écrit parce que c'est là qu'il a servi en premier, mais la date d'arrêté
d'une entité n'est pas une notion IFRS 17 : le relevé ci-dessus la trouve sur
les quatre directions et dans `core/`. Le laisser sous `normes/` aurait obligé
`direction_non_vie` à importer `normes/` pour brancher la gouvernance de la
courbe — un sens de dépendance que le dépôt n'a nulle part, et qui aurait mis
une norme comptable sur le chemin d'un calcul prudentiel. Il ne dépend que de
la bibliothèque standard ; il est donc descendu là où les quatre directions
peuvent le lire sans rien inverser.

⚠️ CE MODULE NE BASCULE TOUJOURS AUCUN CONSOMMATEUR. La gouvernance de la
courbe sait désormais refuser une courbe POSTÉRIEURE à l'arrêté — cause
ajoutée à `diagnostic_peremption` — mais elle dort tant que personne ne lui
fournit de date. Ce que la descente déclenchera est mesuré : sur les arrêtés
lisibles, TROIS SUR CINQ passent au ROUGE avec la courbe embarquée, tous par
anachronisme, et AUCUN quand la courbe correspond à l'arrêté.

⚠️ ET UN CHIFFRE À NE PAS REPRENDRE. Une version antérieure de cette note
annonçait « quatre verdicts déplacés sur huit ». Ce compte DÉRIVE avec l'âge
de la courbe embarquée — mesuré à zéro le 10/08/2026, six à six mois, quatre à
douze. Ce n'était pas une propriété du défaut, c'était une photo.
=============================================================================
"""

from datetime import date, datetime
from typing import Dict, NamedTuple, Tuple

#: Formats acceptés en entrée, et l'ordre dans lequel on les essaie.
#: Les deux existent dans le dépôt — on les lit tous deux plutôt que d'en
#: décréter un et de casser l'autre, mais on DIT lequel a été reconnu.
#: ⚠️ L'ORDRE COMPTE. Les formes à quatre chiffres d'année passent AVANT
#: celles à deux : « 15/03/2026 » ne doit jamais tomber dans `%d/%m/%y`. Et
#: `%y` suit la convention POSIX — 00-68 vaut 2000-2068, 69-99 vaut 1969-1999.
#: Un contrat émis en 2070 s'y lirait donc de travers ; la bande de
#: plausibilité et la porte de confirmation sont ce qui l'attrape.
FORMATS: Tuple[Tuple[str, str], ...] = (
    ('%Y-%m-%d', 'AAAA-MM-JJ'),
    ('%d/%m/%Y', 'JJ/MM/AAAA'),
    ('%d-%m-%Y', 'JJ-MM-AAAA'),
    ('%Y/%m/%d', 'AAAA/MM/JJ'),
    ('%Y%m%d',   'AAAAMMJJ'),
    ('%d.%m.%Y', 'JJ.MM.AAAA'),
    ('%d/%m/%y', 'JJ/MM/AA'),
)

#: Bande de plausibilité. Hors d'elle, c'est une faute de saisie, et il n'y a
#: pas de résultat partiel utile pour une date d'arrêté : on lève.
ANNEE_MIN = 1990
ANNEE_MAX = 2100

#: Les fins de période comptables usuelles — (mois, jour) -> libellé.
FINS_DE_PERIODE: Dict[Tuple[int, int], str] = {
    (3, 31):  'T1',
    (6, 30):  'T2',
    (9, 30):  'T3',
    (12, 31): 'T4',
}


class Arrete(NamedTuple):
    """La date à laquelle une entité établit ses comptes.

    `format_lu` et `texte_origine` sont des DONNÉES et non des commentaires :
    un contrôleur qui demande « d'où vient cette date ? » obtient la réponse
    depuis le livrable. C'est la discipline de `parametres_fs.py`.
    """
    valeur:        date
    format_lu:     str
    texte_origine: str


class ArreteInvalide(ValueError):
    """La date d'arrêté ne peut pas être établie. Il n'y a pas de clôture
    partielle : contrairement à l'inventaire de contrats, on lève."""


def lire(texte) -> Arrete:
    """Un texte (ou une date) → un `Arrete` typé. Lève si indéchiffrable.

    Accepte les quatre formats de `FORMATS` et retient CELUI QUI A MARCHÉ,
    pour que le client puisse vérifier qu'on a lu 03/04 comme le 3 avril et
    non comme le 4 mars.
    """
    if isinstance(texte, Arrete):
        return texte
    if isinstance(texte, datetime):
        return _valider(Arrete(texte.date(), 'datetime', texte.isoformat()))
    if isinstance(texte, date):
        return _valider(Arrete(texte, 'date', texte.isoformat()))

    # ⚠️ `None` est traité à part parce qu'il EXISTE dans le dépôt :
    # `date_arrete: str = None` chez A13 et EP5. `str(None)` vaudrait
    # « None », et le message parlerait d'un texte indéchiffrable là où le
    # vrai défaut est qu'aucune date n'a été fournie.
    brut = '' if texte is None else str(texte).strip()
    if not brut:
        raise ArreteInvalide(
            "Aucune date d'arrêté fournie. Elle est la clé de la clôture : "
            "sans elle, aucun rapprochement ne peut se rattacher à un "
            "exercice, et aucune version ne peut s'archiver.")
    for motif, libelle_format in FORMATS:
        try:
            lu = datetime.strptime(brut, motif).date()
        except ValueError:
            continue
        return _valider(Arrete(lu, libelle_format, brut))
    raise ArreteInvalide(
        f"Date d'arrêté indéchiffrable : « {brut} ». Formats acceptés : "
        f"{', '.join(f for _, f in FORMATS)}. ⚠️ Un libellé libre du type "
        f"« Q2 2026 » n'en est pas un — il ne se compare pas, ne s'ordonne "
        f"pas et ne peut pas servir de clé d'archivage.")


def _valider(arrete: Arrete) -> Arrete:
    """Refuse une date hors de la bande de plausibilité."""
    if not ANNEE_MIN <= arrete.valeur.year <= ANNEE_MAX:
        raise ArreteInvalide(
            f"Date d'arrêté hors bande : {arrete.valeur.isoformat()}. "
            f"Une clôture se situe entre {ANNEE_MIN} et {ANNEE_MAX} — "
            f"« {arrete.texte_origine} » est vraisemblablement une faute de "
            f"saisie.")
    return arrete


def iso(arrete: Arrete) -> str:
    """La forme 'AAAA-MM-JJ' — celle qu'attend `age_courbe_mois`.

    C'est ici que la date d'arrêté DE L'ENTITÉ rencontre la date de la
    COURBE sans se confondre avec elle : la gouvernance de la courbe juge
    sa fraîcheur À CETTE DATE, et non à celle du jour du calcul.
    """
    return arrete.valeur.isoformat()


def libelle(arrete: Arrete) -> str:
    """Le libellé lisible — DÉRIVÉ de la date, jamais saisi.

    Un libellé saisi peut contredire la date qu'il accompagne ; un libellé
    calculé ne le peut pas.
    """
    marque = FINS_DE_PERIODE.get((arrete.valeur.month, arrete.valeur.day))
    if marque:
        return f"{marque} {arrete.valeur.year}"
    return arrete.valeur.strftime('%d/%m/%Y')


def est_fin_de_periode(arrete: Arrete) -> bool:
    """Une fin de trimestre comptable usuelle ?

    Une clôture en milieu de mois existe — run-off, cession de portefeuille —
    mais elle est assez rare pour mériter d'être SIGNALÉE, pas refusée.
    """
    return (arrete.valeur.month, arrete.valeur.day) in FINS_DE_PERIODE


def resume_confirmation(arrete: Arrete) -> str:
    """Ce que le lecteur affiche pour se faire confirmer sa lecture.

    Même patron que le lecteur EIOPA et que le lecteur d'inventaire : on
    montre ce qu'on a compris avant de s'en servir.
    """
    lignes = [
        f"ARRÊTÉ LU — {libelle(arrete)}  ({iso(arrete)})",
        f"  saisi « {arrete.texte_origine} », reconnu au format "
        f"{arrete.format_lu}.",
    ]
    if not est_fin_de_periode(arrete):
        lignes.append(
            "  ⚠️ Ce n'est pas une fin de trimestre usuelle (31/03, 30/06, "
            "30/09, 31/12). Vérifiez qu'il s'agit bien de la date voulue.")
    return '\n'.join(lignes)
