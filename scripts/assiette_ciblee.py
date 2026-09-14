"""L'ASSIETTE D'UNE GATE CIBLEE — QUELS SCEAUX DOIVENT TOURNER POUR CE LOT.

⚠️⚠️ POURQUOI CET OUTIL EXISTE, ET CE QU'IL NE PROMET PAS.

La gate complete de `direction_non_vie/tarification` mesure 1 951 tests en
**2 049 s**. A un lot par constat et une vingtaine de constats restants,
cela fait dix a douze heures de gate pure. Cet outil derive les sceaux qui
doivent VRAIMENT tourner pour un lot donne. *Il ne remplace pas la gate
complete : il la reporte au moment ou elle compte, c'est-a-dire avant la
POUSSEE — le seul instant ou le travail devient public.*

TROIS FACONS D'ENTRER DANS L'ASSIETTE, ET CHACUNE A ETE PAYEE :

  I  le sceau IMPORTE le module touche.
     La facon evidente, et la seule qu'on pense d'abord.

  N  le sceau NOMME le fichier touche dans une chaine.
     ⚠️ SANS CE CRITERE L'OUTIL SERAIT FAUX. Rejeu du 14/09 : `CM-4`
     (`test_conditions_mesure`) est tombe sur un refactor d'A6 alors qu'il
     n'importe PAS l'agent — il en relit le TEXTE par AST. Ce depot est
     plein de sceaux de cette forme ; une assiette batie sur les seuls
     imports les raterait tous.

  B  le sceau BALAIE le depot (`os.walk`, `rglob`, `glob`, `iterdir`,
     `listdir`, `scandir`, `git ls-files`) — il tourne TOUJOURS, quoi
     qu'on touche.
     ⚠️ Ce sont les garde-fous transverses : RGPD (`RD-7`/`RD-8`), plafond
     de dette (`VC-4`), contrats derives (`AD-3`). Ils ne nomment aucun
     fichier et n'en importent aucun. **Les deux rouges de la gate du
     14/09 au soir etaient exactement ceux-la.**

  T  le fichier touche EST un module de test — il tourne, evidemment.

⛔⛔ UNE ERREUR DEJA COMMISE DANS CET OUTIL, ET GARDEE ICI PAR ECRIT :
ma premiere version comptait `ast.walk()` comme un balayage de disque et
rendait **124 balayeurs sur 194**, ce qui detruisait tout le gain annonce.
`ast.walk` parcourt un ARBRE DE SYNTAXE. Le releve corrige en trouve **54**.
*Le 15e piege dans l'autre sens : une assiette trop LARGE ne rate pas, elle
rend l'instrument inutile — et on ne s'en apercoit pas, puisqu'elle passe.*

⚠️⚠️ ET UNE CONDITION D'EMPLOI, MESUREE LE 14/09 : `git add` LE LOT AVANT
DE LANCER. Les sceaux `B` derivent leur corpus de `git ls-files`, qui lit
l'INDEX. Un fichier de test neuf non indexe leur est INVISIBLE : la gate de
son propre lot passe au vert, et il ne mord qu'au lot suivant — c'est
arrive, sur du code deja pousse, et DEUX sceaux independants l'ont dit un
commit trop tard.

LE VERDICT N'EST PAS RENDU ICI. `--lancer` delegue a `unittest`, puis lit
la sortie avec `gate.py::_verdict` — **importe, jamais recopie**. Le
constat `GATE-1` a coute assez cher pour qu'il n'existe qu'UNE lecture de
verdict dans ce depot, et l'environnement des enfants vient de la meme
source (`environnement_des_enfants`), parce qu'un lanceur ampute a deja
rendu CINQ plants << VERT >>.
"""
import argparse
import ast
import functools
import pathlib
import subprocess
import sys

_RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RACINE / 'scripts'))

#: Les gestes par lesquels un sceau se donne une assiette a lui tout seul.
_BALAYAGE = {'rglob', 'glob', 'walk', 'iterdir', 'listdir', 'scandir'}
_ZONE_DEFAUT = 'direction_non_vie/tarification'


def _git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=str(_RACINE), check=False,
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace').stdout


def fichiers_touches() -> list[str]:
    """Ce que le lot modifie : index ET arbre de travail, suivis ou non."""
    sortie = _git('status', '--porcelain')
    touches = []
    for ligne in sortie.splitlines():
        if len(ligne) < 4:
            continue
        chemin = ligne[3:].strip().strip('"')
        #: un renommage s'ecrit `ancien -> nouveau` : les DEUX comptent
        if ' -> ' in chemin:
            touches.extend(x.strip() for x in chemin.split(' -> '))
        else:
            touches.append(chemin)
    return [t for t in touches if t.endswith('.py')]


def modules_de_test(zone: str) -> list[str]:
    """Les modules de test de la zone, tels que GIT les publie."""
    return [r for r in _git('ls-files').split()
            if r.startswith(zone)
            and pathlib.PurePosixPath(r).name.startswith('test_')
            and r.endswith('.py')]


@functools.cache
def _arbre(rel: str):
    """L'arbre de syntaxe d'un fichier, analyse UNE fois par processus.

    ⚠️ MESURE AVANT/APRES : sans ce cache, la sentinelle de cet outil
    reanalysait les ~194 modules de la zone a chaque appel d'`assiette()`,
    soit ~1 200 analyses pour ses 7 tests -- 58 s dans la gate, pour un
    outil dont le but est de la raccourcir. *Un instrument qui coute plus
    qu'il n'economise n'est pas un instrument.*

    ⚠️ Sans risque ici : les fichiers ne changent pas pendant un processus,
    et personne ne MUTE l'arbre rendu (`ast.walk` ne fait que parcourir).
    Un plant, lui, tourne dans un processus NEUF -- le cache ne peut donc
    pas lui cacher sa propre modification.
    """
    try:
        return ast.parse((_RACINE / rel).read_text(encoding='utf-8',
                                                   errors='replace'))
    except (OSError, SyntaxError):
        return None


def _est_balayeur(arbre: ast.AST) -> set[str]:
    """Les balayages de DISQUE d'un module — `ast.walk` n'en est pas un."""
    motifs: set[str] = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        recepteur = (ast.unparse(noeud.func.value)[:24]
                     if isinstance(noeud.func, ast.Attribute) else '')
        nom = (noeud.func.attr if isinstance(noeud.func, ast.Attribute)
               else noeud.func.id if isinstance(noeud.func, ast.Name) else '')
        #: ⚠️ `ast.walk` parcourt un arbre de syntaxe, pas le disque.
        if nom == 'walk' and recepteur != 'os':
            continue
        if nom in _BALAYAGE:
            motifs.add((recepteur + '.' if recepteur else '') + nom + '()')
        if 'ls-files' in ast.unparse(noeud)[:220]:
            motifs.add('git ls-files')
    return motifs


def assiette(touches: list[str], zone: str = _ZONE_DEFAUT) -> dict:
    """{module de test : {raisons}} — ce qui doit tourner pour ce lot."""
    modules = {t[:-3].replace('/', '.') for t in touches}
    bases = {pathlib.PurePosixPath(t).name for t in touches}
    retenus: dict[str, set[str]] = {}

    for rel in modules_de_test(zone):
        arbre = _arbre(rel)
        if arbre is None:
            continue
        raisons: set[str] = set()

        #: T — le fichier touche EST ce module de test
        if rel in touches:
            raisons.add('T touche')

        #: I — il importe un module touche
        for noeud in ast.walk(arbre):
            noms: list[str] = []
            if isinstance(noeud, ast.Import):
                noms = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                noms = [noeud.module] + [f'{noeud.module}.{a.name}'
                                         for a in noeud.names]
            for x in noms:
                if x in modules or any(x.startswith(m + '.') for m in modules):
                    raisons.add('I import')

        #: N — il nomme un fichier touche dans une chaine
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant)
                    and isinstance(noeud.value, str)
                    and any(b in noeud.value for b in bases)):
                raisons.add('N nomme')

        #: B — il balaie le depot : il tourne toujours
        motifs = _est_balayeur(arbre)
        if motifs:
            raisons.add('B balaie (' + ', '.join(sorted(motifs))[:40] + ')')

        if raisons:
            retenus[rel] = raisons
    return retenus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--zone', default=_ZONE_DEFAUT)
    ap.add_argument('--touches', nargs='*', default=None,
                    help='fichiers du lot ; par defaut, `git status`')
    ap.add_argument('--pourquoi', action='store_true',
                    help='dire pour chaque module POURQUOI il est retenu')
    ap.add_argument('--lancer', action='store_true',
                    help='lancer unittest sur l assiette et rendre le verdict')
    ap.add_argument('--sortie', default=None)
    args = ap.parse_args()

    touches = args.touches if args.touches is not None else fichiers_touches()
    if not touches:
        print('AUCUN FICHIER TOUCHE : rien a cibler. Lancez la gate '
              'complete, ou passez --touches.', flush=True)
        return 2

    retenus = assiette(touches, args.zone)
    tous = modules_de_test(args.zone)
    print(f'fichiers touches : {len(touches)}', flush=True)
    for t in sorted(touches):
        print(f'    {t}', flush=True)
    print(f'assiette : {len(retenus)} modules sur {len(tous)} '
          f'({100 * len(retenus) // max(len(tous), 1)} %)', flush=True)
    #: ⚠️ On DIT quand l'assiette vaut le corpus entier : ce n'est pas une
    #: panne, c'est une information — le lot touche quelque chose de
    #: central, et il n'y a rien a gagner a cibler.
    if len(retenus) == len(tous):
        print('    /!\\ l assiette vaut TOUT le corpus : aucun gain a '
              'attendre, lancez la gate complete.', flush=True)
    if args.pourquoi:
        for rel in sorted(retenus):
            print(f'    {rel}', flush=True)
            print(f'        {" | ".join(sorted(retenus[rel]))}', flush=True)

    if not args.lancer:
        for rel in sorted(retenus):
            print(rel[:-3].replace('/', '.'), flush=True)
        return 0

    #: ⚠️ IMPORT TARDIF, ET DELIBERE : `gate` n'est utile qu'au lancement.
    #: Le charger au module ferait dependre le simple LISTAGE de l'assiette
    #: d'un import qui n'a rien a y faire.
    import gate

    sortie = pathlib.Path(args.sortie or (_RACINE / 'assiette_sortie.txt'))
    modules = sorted(r[:-3].replace('/', '.') for r in retenus)
    with open(sortie, 'w', encoding='utf-8') as flux:
        subprocess.run([sys.executable, '-B', '-m', 'unittest', *modules],
                       cwd=str(_RACINE), check=False, stdout=flux,
                       stderr=subprocess.STDOUT,
                       env=gate.environnement_des_enfants())
    #: ⚠️ LE VERDICT VIENT DE `gate.py`, IMPORTE. Une seconde lecture de
    #: verdict dans ce depot divergerait au premier correctif — et c'est
    #: precisement ce que `GATE-1` a coute.
    etat, nombre = gate._verdict(sortie)
    print(f'VERDICT : {etat}   sur {nombre:,} tests   ({sortie})', flush=True)
    return 0 if etat.startswith('OK') else 1


if __name__ == '__main__':
    raise SystemExit(main())
