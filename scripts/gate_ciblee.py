"""GATE CIBLEE -- ne lancer que ce que le lot peut casser.

⚠️⚠️ LE PROBLEME MESURE : la gate `tarification` prend **1 745 s (29 min)**
pour 1 730 tests. Le lot L0 ne touchait que DEUX fichiers de test, que rien
n'importe : 29 minutes pour 41 tests utiles.

CE QUE FAIT CET OUTIL
  1. releve par AST QUI IMPORTE QUOI, transitivement, dans le perimetre ;
  2. a partir des fichiers modifies (`git status`), rend la liste des
     modules de test REELLEMENT atteignables ;
  3. dit le gain de temps attendu.

⚠️⚠️ CE N'EST PAS UN REMPLACANT DE LA GATE COMPLETE, ET LA RAISON EST
MESURABLE : un test peut depend d'un module SANS l'importer -- il execute
la chaine, qui l'importe a sa place. Le releve d'imports est donc un
MINORANT de l'assiette. La regle qui en decoule :

    · gate CIBLEE  : a chaque lot, pour le retour rapide ;
    · gate COMPLETE : une fois, en fin de chantier, et sur tout lot qui
      touche un module de production consomme par la chaine.

⚠️ ET LA LIGNE DE BASE SE MESURE UNE FOIS. Un arbre de depart deja rouge
rend toute gate rouge : sans ligne de base, on impute au lot un echec qui
ne lui appartient pas. Mesure du 12/09 : `2b4966b` est DEJA rouge sur
`GEL-15b` (3 surfaces A7 apparues, reference non refigee).
"""
import ast
import collections
import pathlib
import subprocess
import sys

RACINE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
PERIMETRE = ('direction_non_vie/tarification/', 'core/')


def _modules_suivis() -> dict:
    """{nom.de.module: chemin} pour le perimetre."""
    sortie = subprocess.run(['git', 'ls-files'], cwd=str(RACINE),
                            capture_output=True, text=True, encoding='utf-8',
                            errors='replace', check=False).stdout
    mods = {}
    for rel in sortie.split('\n'):
        if not rel.endswith('.py'):
            continue
        if not any(rel.startswith(p) for p in PERIMETRE):
            continue
        if (RACINE / rel).is_file():
            mods[rel[:-3].replace('/', '.')] = rel
    return mods


def _importe(chemin: pathlib.Path) -> set:
    """Les modules qu'un fichier importe -- releve PAR AST."""
    try:
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
    except (SyntaxError, OSError):
        return set()
    vus = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            vus.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            vus.add(n.module)
            vus.update(f'{n.module}.{a.name}' for a in n.names)
    return vus


def modules_a_lancer(modifies: list) -> tuple:
    """Les modules de test atteignables depuis les fichiers modifies."""
    mods = _modules_suivis()
    # graphe INVERSE : qui importe X ?
    lecteurs = collections.defaultdict(set)
    for nom, rel in mods.items():
        for cible in _importe(RACINE / rel):
            if cible in mods:
                lecteurs[cible].add(nom)

    depart = {rel[:-3].replace('/', '.') for rel in modifies
              if rel.endswith('.py')}
    atteints, pile = set(depart), list(depart)
    while pile:                      # fermeture transitive
        courant = pile.pop()
        for lecteur in lecteurs.get(courant, ()):
            if lecteur not in atteints:
                atteints.add(lecteur)
                pile.append(lecteur)
    tests = sorted(m for m in atteints
                   if m.rsplit('.', 1)[-1].startswith('test_'))
    return tests, len(mods)


if __name__ == '__main__':
    porcelaine = subprocess.run(['git', 'status', '--porcelain'],
                                cwd=str(RACINE), capture_output=True,
                                text=True, encoding='utf-8',
                                errors='replace', check=False).stdout
    modifies = [l[3:].strip().strip('"') for l in porcelaine.split('\n')
                if l.strip()]
    print(f"  arbre    : {RACINE}")
    print(f"  modifies : {len(modifies)} fichier(s)")
    for m in modifies[:12]:
        print(f"      {m}")
    tests, total = modules_a_lancer(modifies)
    print()
    print(f"  modules du perimetre releves  : {total}")
    print(f"  modules de TEST a lancer      : {len(tests)}")
    for t in tests[:25]:
        print(f"      {t}")
    if len(tests) > 25:
        print(f"      ... et {len(tests) - 25} autre(s)")
    print()
    print("  commande :")
    print("    py -B -m unittest " + ' '.join(tests[:6])
          + (' ...' if len(tests) > 6 else ''))
