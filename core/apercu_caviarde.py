# -*- coding: utf-8 -*-
"""C2 — l'aperçu caviardé : la structure part, les valeurs restent.

⚠️ POURQUOI CE MODULE EXISTE. Deux sites du dépôt envoyaient à l'API de VRAIES
lignes du fichier client — `df.head(n).to_csv()` : primes, numéros de police,
âges, montants de sinistres. C'étaient les deux seuls. Ils reçoivent désormais
la FORME des valeurs, jamais les valeurs.

⚠️ CE QUE LA MESURE D'IA-0 A ÉTABLI, ET QUI JUSTIFIE LE COÛT NUL. Le signal
qui permet de reconnaître une colonne est dans son NOM, que le caviardage
préserve intégralement. Le seul cas mesuré où le caviardage détruit de
l'information — l'en-tête décalé, dont les noms d'en-tête SONT des valeurs —
est justement celui que le lecteur déterministe résout déjà seul.

⚠️ CE QUE JE MESURE ET CE QUE JE NE MESURE PAS. Ce module garantit qu'aucune
valeur ne sort : c'est vérifiable, et un test le vérifie sur des sentinelles.
Il ne garantit PAS que le modèle propose aussi bien qu'avant — cela demanderait
un appel réel, impossible ici (paquet `anthropic` absent).

LA BANDE NUMÉRIQUE EST UNE CATÉGORIE, PAS UNE VALEUR. Dire d'une colonne
d'entiers qu'elle tient dans 1900-2100 ne désigne aucun assureur : c'est ce qui
sépare `annee_survenance` de `annee_developpement` (0, 1, 2...), deux champs du
vocabulaire A7 que le seul type « entier » confond. Même raisonnement que pour
la branche en C3 — une catégorie universelle n'identifie personne.
"""
import re
from typing import Any

# ── le vocabulaire des formes ────────────────────────────────────────────────
FORME_VIDE = 'vide'
FORME_DATE_ISO = 'date AAAA-MM-JJ'
FORME_DATE_FR = 'date JJ/MM/AAAA'
FORME_COMPACTE = '8 chiffres (date compacte ou identifiant)'
FORME_ENTIER = 'entier'
FORME_DECIMAL = 'décimal'
FORME_TEXTE = 'texte'

# ── les bandes numériques, qui sont des catégories ──────────────────────────
BANDE_MILLESIME = (1900, 2100)
BANDE_PETIT_RANG = (0, 99)
ETIQUETTE_MILLESIME = 'millésime (1900-2100)'
ETIQUETTE_PETIT_RANG = 'petit rang (0-99)'

# Profondeur de profilage. ⚠️ CE N'EST PAS UN NOMBRE DE LIGNES ENVOYÉES :
# AUCUNE ligne ne sort. C'est le nombre de lignes LUES LOCALEMENT pour établir
# le profil d'une colonne — borné pour rester rapide sur un gros fichier.
LIGNES_PROFILEES = 1000

_ISO = re.compile(r'\d{4}-\d{2}-\d{2}$')
_FR = re.compile(r'\d{2}/\d{2}/\d{4}$')
_COMPACTE = re.compile(r'\d{8}$')
_ENTIER = re.compile(r'-?\d+$')
_DECIMAL = re.compile(r'-?\d+[.,]\d+$')


def forme(valeur: Any) -> str:
    """La FORME d'une valeur, jamais sa valeur.

    ⚠️ L'ORDRE DES TESTS COMPTE : « 20260315 » est huit chiffres avant d'être
    un entier, et le dire ainsi permet de reconnaître une date compacte que le
    seul mot « entier » masquerait.
    """
    if valeur is None:
        return FORME_VIDE
    texte = str(valeur).strip()
    if texte == '' or texte.lower() in ('nan', 'nat', 'none'):
        return FORME_VIDE
    if _ISO.match(texte):
        return FORME_DATE_ISO
    if _FR.match(texte):
        return FORME_DATE_FR
    if _COMPACTE.match(texte):
        return FORME_COMPACTE
    if _DECIMAL.match(texte):
        return FORME_DECIMAL
    if _ENTIER.match(texte):
        return FORME_ENTIER
    return FORME_TEXTE


def _bande(valeurs) -> str:
    """L'étiquette de bande d'une colonne d'entiers, ou '' si aucune ne colle.

    Rend une CATÉGORIE, jamais un minimum ni un maximum : la bande sépare un
    millésime d'un rang de développement sans divulguer aucune valeur.
    """
    entiers = []
    for v in valeurs:
        try:
            entiers.append(int(str(v).strip()))
        except (TypeError, ValueError):
            return ''
    if not entiers:
        return ''
    bas, haut = min(entiers), max(entiers)
    if BANDE_PETIT_RANG[0] <= bas and haut <= BANDE_PETIT_RANG[1]:
        return ETIQUETTE_PETIT_RANG
    if BANDE_MILLESIME[0] <= bas and haut <= BANDE_MILLESIME[1]:
        return ETIQUETTE_MILLESIME
    return ''


def profil_colonne(serie: Any) -> str:
    """Le profil caviardé d'une colonne : forme dominante, bande, cardinalité.

    Exemple rendu : « entier, millésime (1900-2100), 10 valeurs distinctes ».
    """
    echantillon = list(serie.head(LIGNES_PROFILEES))
    formes = [forme(v) for v in echantillon]
    utiles = [f for f in formes if f != FORME_VIDE]
    dominante = max(set(utiles), key=utiles.count) if utiles else FORME_VIDE

    morceaux = [dominante]
    if dominante in (FORME_ENTIER, FORME_COMPACTE):
        etiquette = _bande(v for v, f in zip(echantillon, formes)
                           if f != FORME_VIDE)
        if etiquette:
            morceaux.append(etiquette)
    try:
        distinctes = int(serie.nunique(dropna=True))
        morceaux.append(f'{distinctes} valeurs distinctes')
    except Exception:                       # type non hachable : on s'abstient
        pass
    if FORME_VIDE in formes:
        morceaux.append('valeurs manquantes présentes')
    return ', '.join(morceaux)


def apercu(df: Any) -> str:
    """L'aperçu CAVIARDÉ envoyé au modèle. Aucune valeur du fichier n'y figure.

    Ce qui part : les dimensions, les noms de colonnes, leur type pandas, et le
    profil de forme de chacune. Ce qui ne part plus : les lignes.
    """
    lignes = [f'dimensions : {df.shape[0]} lignes x {df.shape[1]} colonnes',
              'colonnes (nom : type pandas | profil des valeurs, CAVIARDÉ) :']
    for colonne in df.columns:
        try:
            profil = profil_colonne(df[colonne])
        except Exception:                   # colonne exotique : on le dit
            profil = 'profil indisponible'
        lignes.append(f'- {colonne} : {df[colonne].dtype} | {profil}')
    lignes.append(
        "(Les valeurs du fichier ne sont pas transmises : seules leur forme et "
        "leur cardinalite le sont. Raisonne sur les NOMS de colonnes et ces "
        "profils.)")
    return '\n'.join(lignes)
