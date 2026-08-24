# ruff: noqa
"""CE QUI TOURNE VRAIMENT -- ET DONC CE QUI PUBLIE VRAIMENT UN FAUX.

P3 mesurait la PRESENCE d'un symbole dans un fichier. C'est trop grossier :
l'app appelle pipeline_complet, qui porte la couche qualite. On refait en
suivant la CHAINE D'APPEL.
Et la question qui change le rang 1 : `tarifer()` a-t-il un appelant ?
"""
import ast
import io
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

RACINE = r'C:\Users\selse\actuaria-app'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv',
                                            'venv', '.pytest_cache', 'audit',
                                            'node_modules', 'htmlcov')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))


def rel(p):
    return os.path.relpath(p, RACINE).replace('\\', '/')


def appelants(sym):
    prod, tst = [], []
    for p in fichiers:
        r = rel(p)
        if '/preuves/' in r:
            continue
        try:
            a = ast.parse(io.open(p, encoding='utf-8').read())
        except Exception:
            continue
        for n in ast.walk(a):
            if isinstance(n, ast.Call):
                nom = (n.func.id if isinstance(n.func, ast.Name)
                       else n.func.attr if isinstance(n.func, ast.Attribute) else None)
                if nom == sym:
                    (tst if 'test' in r.split('/')[-1] else prod).append((r, n.lineno))
                    break
    return sorted(set(prod)), sorted(set(tst))


# ══════════════════════════════════════════════════════════════════════════════
titre("Q1 -- `tarifer()` A-T-IL UN APPELANT DE PRODUCTION ?")
# ══════════════════════════════════════════════════════════════════════════════
for sym in ('tarifer', 'predire_portefeuille', 'grille', 'pipeline_complet',
            'sensibilite_tarifaire', 'etat_elasticite', 'estimer_elasticite',
            'diagnostic_exploitabilite'):
    prod, tst = appelants(sym)
    etat = '[CONSTAT]' if not prod else '        '
    print(f"  {etat} {sym:26s} production={len(prod):2d}  tests={len(tst):2d}")
    for r, L in prod:
        print(f"                {r}:{L}")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q2 -- LES BRANCHES DE L'APPLICATION, PAR 'BESOIN'")
# ══════════════════════════════════════════════════════════════════════════════
src = io.open(os.path.join(RACINE, 'actuaria_app.py'), encoding='utf-8').read()
lignes = src.split('\n')
CIBLES = ('AgentA1Ingestion(', 'AgentA2Preprocessing(', 'AgentA3GLM(',
          'AgentA4ML(', 'AgentA5DeepLearning(', 'AgentA6Comparaison(',
          'pipeline_complet(')
besoin = None
for i, L in enumerate(lignes, 1):
    s = L.strip()
    if s.startswith('if besoin ==') or s.startswith('elif besoin =='):
        besoin = s.split('==')[1].strip().rstrip(':').strip('"\' ')
        print(f"\n  besoin == {besoin!r}   (l.{i})")
    for c in CIBLES:
        if c in L and besoin is not None:
            print(f"      l.{i:<6d} {c[:-1]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q3 -- core/elasticite.py : 989 LIGNES, DANS LE CHEMIN, JAMAIS AUDITEES")
# ══════════════════════════════════════════════════════════════════════════════
e = io.open(os.path.join(RACINE, 'core/elasticite.py'), encoding='utf-8').read()
ae = ast.parse(e)
fns = [n.name for n in ae.body if isinstance(n, ast.FunctionDef)]
pub = [f for f in fns if not f.startswith('_')]
consts = [n.targets[0].id for n in ae.body
          if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
          and n.targets[0].id.isupper()]
print(f"  {len(e.split(chr(10))):,} lignes · {len(fns)} fonctions "
      f"({len(pub)} publiques) · {len(consts)} constantes")
print(f"  fonctions publiques : {pub}")
print(f"  constantes          : {consts}")
print()
print("  Qui l'appelle ?")
for s in pub:
    prod, tst = appelants(s)
    prod = [(r, L) for r, L in prod if r != 'core/elasticite.py']
    etat = '[CONSTAT]' if not prod else '        '
    print(f"  {etat} {s:28s} production={len(prod):2d}  tests={len(tst):2d}"
          f"   {[r for r, _ in prod]}")
print()
tests = [rel(p) for p in fichiers
         if 'test' in rel(p).split('/')[-1] and 'elasticite' in io.open(p, encoding='utf-8', errors='replace').read()]
print(f"  fichiers de test le mentionnant : {tests}")
for t in tests:
    a = ast.parse(io.open(os.path.join(RACINE, t), encoding='utf-8').read())
    n = len([x for x in ast.walk(a) if isinstance(x, ast.FunctionDef)
             and x.name.startswith('test')])
    print(f"      {t} : {n} tests")
