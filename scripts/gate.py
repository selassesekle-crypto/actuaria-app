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


def _verdict(chemin: pathlib.Path) -> tuple[str, int]:
    """Le verdict LU AU FICHIER : (etat, nombre de tests)."""
    if not chemin.exists():
        return 'AUCUNE SORTIE', 0
    n = 0
    etat = 'SANS VERDICT'
    for ligne in chemin.read_text(encoding='utf-8', errors='ignore').splitlines():
        if ligne.startswith('Ran ') and ' test' in ligne:
            try:
                n = int(ligne.split()[1])
            except (IndexError, ValueError):
                pass
        elif ligne.startswith('OK'):
            etat = 'OK'
        elif ligne.startswith('FAILED'):
            etat = 'FAILED'
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
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONPATH': '.'}

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
    print(f'  {etat} — {n} tests — {duree:.0f} s')
    # ⚠️ LE VERDICT VIENT DU FICHIER, PAS DU CODE DE SORTIE DU PROCESSUS :
    # un processus tue apres avoir ecrit son OK reste un OK.
    return 0 if etat == 'OK' else 1


if __name__ == '__main__':
    sys.exit(main())
