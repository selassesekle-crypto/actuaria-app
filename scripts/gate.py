"""Lance une gate SOUS DELAI, et rend son verdict LU AU FICHIER.

A quoi il sert : rendre reproductible une facon de lancer qui vivait dans une
habitude, et poser un garde-fou sur un incident mesure. Quatre pieges ont
fausse cette operation au moins une fois chacun, et chacun est desamorce ici
plutot que d'etre rappele a qui s'en souviendra.

  1. UNE GATE PEUT NE PAS RENDRE LA MAIN APRES SON VERDICT. Mesure le
     22/08/2026 : le processus etait vivant 46 MINUTES apres avoir ecrit
     << Ran 1362 tests -- OK >>, CPU fige sur trois releves. Cause inconnue,
     non reproduite. Ce script tue le processus passe le delai : une heure
     perdue devient impossible, ce qui vaut mieux que de chercher une cause
     qui ne se represente pas.

  2. LE STATUT DU HARNAIS N'EST PAS LE VERDICT. Tant que le processus vit,
     la tache est annoncee << en cours >> -- meme si le verdict est ecrit
     depuis trois quarts d'heure. On lit le FICHIER, jamais l'etat de la
     tache.

  3. UN PIPE PERD LE VERDICT. `... | tail` peut rendre 0 alors que la
     campagne a echoue. La sortie est REDIRIGEE dans un fichier, puis lue.

  4. LA PRESENCE D'UN PROCESSUS N'EST PAS UNE ACTIVITE. Pour savoir si une
     gate travaille encore, ce script regarde si le FICHIER GROSSIT -- pas
     si un python.exe existe.

Usage :
    py scripts/gate.py direction_non_vie            # delai par defaut
    py scripts/gate.py normes --delai 300
    py scripts/gate.py core --sortie /tmp/core.txt
"""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import tempfile
import time

#: Les delais par defaut, en secondes, PAR GATE. Ils viennent de mesures
#: reelles, avec de la marge -- pas d'une estimation.
#: ⚠️ direction_non_vie : mesuree de 2 038 s a 4 257 s selon la charge.
#:    Le delai est genereux exprès : un faux positif de delai coute une gate
#:    a relancer, ce qui est pire que d'attendre dix minutes de plus.
DELAIS = {
    'direction_non_vie': 5400,
    'normes':             600,
    'core':               600,
}
DELAI_PAR_DEFAUT = 3600

#: On considere la gate VIVANTE tant que son fichier grossit. Sans cela, un
#: run lent passerait pour un run bloque.
PATIENCE_SANS_ECRITURE = 900

#: ⚠️⚠️ L'ENCODAGE DE SORTIE DU PROCESSUS FILS, ET SON GESTIONNAIRE D'ERREUR.
#: Le gestionnaire compte autant que l'encodage : sans lui, un caractere non
#: representable LEVE et fait tomber le test qui l'imprimait. Le depot emploie
#: 26 caracteres hors cp1252 au voisinage de ses `print`, dans 51 fichiers.
ENCODAGE_SORTIE = 'utf-8:backslashreplace'


#: Les trois jetons que `unittest` ecrit SOUS sa ligne « Ran N tests ».
#: ⚠️ `NO TESTS RAN` (Python >= 3.12) n'est PAS un succes : une cible vide ou
#: mal orthographiee ne doit jamais rendre 0.
_JETONS = {'OK': 'OK', 'FAILED': 'FAILED', 'NO TESTS RAN': 'AUCUN TEST'}


def environnement_des_enfants() -> dict:
    """L'environnement que ce lanceur donne au processus de tests.

    ⚠️⚠️ LE VERDICT NE DOIT PAS DEPENDRE DE LA CONSOLE. Mesure du
    11/09/2026 : les memes 882 tests rendent << OK >> sous `PYTHONUTF8=1`
    et << FAILED (errors=87) >> dans une console cp1252 -- 87
    `UnicodeEncodeError` levees par des `print` de TESTS, aucun cadre en
    production. `backslashreplace` fait DEGRADER un caractere non
    representable au lieu de le faire LEVER : plus aucune impression ne
    peut faire tomber un test.

    ⚠️ CE N'EST PAS LA MEME CHOSE QUE `PYTHONUTF8=1`, QUI EST CONSERVE :
    l'un choisit l'encodage, l'autre garantit que l'ECHEC D'ENCODAGE
    n'existe plus. Le premier seul laissait le probleme entier des qu'on
    lancait la suite autrement que par ce script.

    ⚠️⚠️ LA VARIABLE VIENT DU SOCLE, ELLE N'EST PLUS RECOPIEE ICI --
    constat `TEST-D2`, 14/09/2026. `('PYTHONUTF8', '1')` etait ecrit a la
    fois dans `core/sortie_console.py` (en prose) et dans ce lanceur (en
    dur) : *deux endroits qui declarent la meme condition finissent par
    en declarer deux differentes.*

    ⚠️⚠️ ET CETTE FONCTION EXISTE POUR QU'UN CONTROLE PUISSE LA LIRE. Le
    sceau `EN-3` verifiait le TEXTE du code -- il cherchait le litteral
    `'PYTHONUTF8': '1'` dans un `ast.Dict` -- et il a donc ACCUSE ce lot,
    alors que le comportement qu'il protege etait intact. *Un controle
    qui lit le texte et non le comportement se trompe dans les DEUX
    sens.* Il appelle desormais cette fonction et lit ce qu'elle REND.

    ⚠️ LA RACINE ENTRE DANS `sys.path` AVANT L'IMPORT : ce script vit dans
    `scripts/`, et sans cela `core` n'est pas importable -- le lanceur
    ENTIER tombait, et mon premier sceau ne l'avait pas vu.
    """
    racine = str(pathlib.Path(__file__).resolve().parent.parent)
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.sortie_console import ENCODAGE_IMPOSE
    cle, valeur = ENCODAGE_IMPOSE
    return {**os.environ, cle: valeur, 'PYTHONPATH': '.',
            'PYTHONIOENCODING': ENCODAGE_SORTIE}


def _verdict(chemin: pathlib.Path) -> tuple[str, int]:
    """Le verdict LU AU FICHIER, DANS LE BLOC DU LANCEUR : (etat, nb tests).

    ⚠️⚠️ LA LIGNE NE SUFFIT PAS, SA PLACE COMPTE. Cette fonction retenait la
    DERNIERE ligne commencant par `OK` ou `FAILED`, ou qu'elle soit. Or les
    `print` des tests partent sur stdout -- BLOC-bufferise quand la sortie est
    redirigee -- et le verdict du lanceur sur stderr : le contenu de stdout est
    donc vide APRES le verdict. Mesure du 11/09/2026 sur la sortie REELLE de la
    suite A7 : 34 lignes de tests commencent par `OK` en colonne 0 apres le
    verdict, et l'ancienne lecture rendait **OK sur un fichier portant
    `FAILED (errors=87)`** -- 882 tests, 87 erreurs, code de sortie 0.
      Le meme trou laissait passer deux autres formes, mesurees : un
    `atexit` qui ecrit une ligne commencant par `OK`, et un test qui ecrit
    `OK ...` puis se fige jusqu'a etre tue (le fichier ne porte alors AUCUNE
    ligne `Ran`, et l'ancienne lecture rendait quand meme OK).

    On ancre donc la lecture sur la ligne `Ran N tests in ...` du lanceur : le
    verdict est la premiere ligne non vide qui la SUIT, et elle doit etre l'un
    des trois jetons de `unittest`. Aucune autre ligne du fichier n'est lue.
    """
    if not chemin.exists():
        return 'AUCUNE SORTIE', 0
    lignes = chemin.read_text(encoding='utf-8',
                              errors='ignore').splitlines()
    etat, n = 'SANS VERDICT', 0
    # ⚠️ ON PARCOURT A L'ENVERS et on s'arrete au PREMIER bloc complet : un
    # test qui imprimerait une fausse ligne « Ran 9999 tests » ne serait pas
    # suivi d'un jeton, donc ne serait pas retenu.
    for i in range(len(lignes) - 1, -1, -1):
        ligne = lignes[i]
        if not (ligne.startswith('Ran ') and ' test' in ligne):
            continue
        suite = next((x.strip() for x in lignes[i + 1:] if x.strip()), '')
        trouve = next((v for k, v in _JETONS.items() if suite.startswith(k)),
                      None)
        if trouve is None:
            continue
        etat = trouve
        try:
            n = int(ligne.split()[1])
        except (IndexError, ValueError):
            n = 0
        break
    return etat, n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('cible', help='repertoire de decouverte, ex. direction_non_vie')
    ap.add_argument('--delai', type=int, default=None,
                    help='secondes avant de tuer le processus')
    ap.add_argument('--sortie', default=None, help='fichier de sortie')
    a = ap.parse_args()

    delai = a.delai or DELAIS.get(a.cible, DELAI_PAR_DEFAUT)
    sortie = pathlib.Path(a.sortie or (
        pathlib.Path(tempfile.gettempdir()) / f'gate_{a.cible.replace("/", "_")}.txt'))
    env = environnement_des_enfants()

    print(f'  gate {a.cible} — delai {delai} s — sortie {sortie}')
    t0 = time.time()
    with sortie.open('w', encoding='utf-8') as f:
        p = subprocess.Popen(
            [sys.executable, '-m', 'unittest', 'discover', '-s', a.cible, '-t', '.'],
            stdout=f, stderr=subprocess.STDOUT, env=env)
        taille, dernier_progres = -1, time.time()
        while p.poll() is None:
            time.sleep(15)
            actuelle = sortie.stat().st_size
            if actuelle != taille:
                taille, dernier_progres = actuelle, time.time()
            fige = time.time() - dernier_progres
            if time.time() - t0 > delai or fige > PATIENCE_SANS_ECRITURE:
                # ⚠️ ON DIT LEQUEL DES DEUX A MORDU : un delai global depasse
                # et une sortie figee ne se diagnostiquent pas pareil.
                motif = ('delai global depasse' if time.time() - t0 > delai
                         else f'sortie figee depuis {fige:.0f} s')
                print(f'  /!\\ {motif} — le processus est tue')
                p.kill()
                break

    etat, n = _verdict(sortie)
    duree = time.time() - t0
    # ⚠️ LE VERDICT VIENT DU FICHIER, PAS DU CODE DE SORTIE DU PROCESSUS :
    # un processus tue apres avoir ecrit son OK reste un OK. Mais quand le
    # processus a rendu la main NORMALEMENT, son code de sortie est un SECOND
    # temoin, independant du texte : s'ils se contredisent, on ne choisit pas,
    # on le DIT et on rend 1. Un desaccord entre deux temoins n'est jamais un
    # succes.
    code = p.poll()
    desaccord = (code is not None
                 and ((etat == 'OK' and code != 0)
                      or (etat != 'OK' and code == 0)))
    # ⚠️ UN VERDICT SE LIT AVEC SES CONDITIONS. Celui-ci a ete obtenu sous
    # un encodage impose par ce script ; le taire, c'est laisser croire qu'il
    # vaut sous n'importe quelle console — ce que la mesure dement.
    print(f'  {etat} — {n} tests — {duree:.0f} s '
          f'— sortie {ENCODAGE_SORTIE}')
    if desaccord:
        print(f'  /!\\ DESACCORD : le fichier dit « {etat} », le processus a '
              f'rendu {code}. Verdict force a l echec.')
    return 0 if (etat == 'OK' and not desaccord) else 1


if __name__ == '__main__':
    sys.exit(main())
