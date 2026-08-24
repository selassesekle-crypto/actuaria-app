# ruff: noqa
"""RELEVE pipeline_agents.py -- CE QUE L'ORCHESTRATEUR DEVAIT REPARER.

Son en-tete dit : « Aucun orchestrateur n'existait : chaque appelant (app,
demos, tests) assemblait la chaine a la main -- et `result_a5` valait `None`
PARTOUT dans le depot : A5 n'etait jamais cable dans A6. »
Il existe. Personne ne l'appelle. Qui assemble la chaine aujourd'hui ?
"""
import ast
import io
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

RACINE = r'C:\Users\selse\actuaria-app'
MOI = 'direction_non_vie/tarification/pipeline_agents.py'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv',
                                            'node_modules', 'venv',
                                            '.pytest_cache', 'htmlcov', 'audit')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))


def rel(p):
    return os.path.relpath(p, RACINE).replace('\\', '/')


# ══════════════════════════════════════════════════════════════════════════════
titre("Q1 -- QUI INSTANCIE LES AGENTS A LA MAIN ?")
# ══════════════════════════════════════════════════════════════════════════════
AGENTS = ['AgentA1Ingestion', 'AgentA2Preprocessing', 'AgentA3GLM',
          'AgentA4ML', 'AgentA5DeepLearning', 'AgentA6Comparaison']
assembleurs = {}
for p in fichiers:
    r = rel(p)
    if r == MOI or '/preuves/' in r:
        continue
    try:
        a = ast.parse(io.open(p, encoding='utf-8').read())
    except (SyntaxError, UnicodeDecodeError):
        continue
    vus = set()
    for nd in ast.walk(a):
        if isinstance(nd, ast.Call):
            nom = (nd.func.id if isinstance(nd.func, ast.Name)
                   else nd.func.attr if isinstance(nd.func, ast.Attribute) else None)
            if nom in AGENTS:
                vus.add(nom)
    if len(vus) >= 3:
        assembleurs[r] = sorted(vus)
print(f"  {len(assembleurs)} fichier(s) instancient 3 agents ou plus :")
for r, v in sorted(assembleurs.items()):
    marque = 'TEST' if 'test' in r.split('/')[-1] else '⚠   '
    complet = 'CHAINE COMPLETE' if len(v) == 6 else f'{len(v)}/6'
    print(f"    [{marque}] {r[:52]:52s} {complet}")
    print(f"              {[x.replace('Agent', '') for x in v]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q2 -- `result_a5=None` EST-IL ENCORE PASSE A A6 ?")
# ══════════════════════════════════════════════════════════════════════════════
for p in fichiers:
    r = rel(p)
    if '/preuves/' in r:
        continue
    try:
        a = ast.parse(io.open(p, encoding='utf-8').read())
    except (SyntaxError, UnicodeDecodeError):
        continue
    for nd in ast.walk(a):
        if isinstance(nd, ast.Call):
            nom = (nd.func.id if isinstance(nd.func, ast.Name)
                   else nd.func.attr if isinstance(nd.func, ast.Attribute) else None)
            if nom != 'run':
                continue
            for k in nd.keywords:
                if k.arg == 'result_a5':
                    txt = ast.unparse(k.value)
                    est_none = txt == 'None'
                    marque = ('TEST' if 'test' in r.split('/')[-1]
                              else 'MOI ' if r == MOI else '⚠   ')
                    etat = '[CONSTAT]' if est_none and r != MOI else '        '
                    print(f"  {etat} [{marque}] {r[:44]:44s} l.{nd.lineno:<5d} "
                          f"result_a5={txt[:34]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q3 -- LA CIBLE COUT EST-ELLE ARBITREE HORS DE L'ORCHESTRATEUR ?")
# ══════════════════════════════════════════════════════════════════════════════
# Le motif que l'orchestrateur repare : A4/A5 entraines uniquement sur la
# frequence -> A6 arbitre la cible cout contre un seul candidat.
for p in fichiers:
    r = rel(p)
    if r == MOI or '/preuves/' in r:
        continue
    try:
        a = ast.parse(io.open(p, encoding='utf-8').read())
    except (SyntaxError, UnicodeDecodeError):
        continue
    cibles_a4, cibles_a6 = [], []
    for nd in ast.walk(a):
        if isinstance(nd, ast.Call):
            nom = (nd.func.id if isinstance(nd.func, ast.Name)
                   else nd.func.attr if isinstance(nd.func, ast.Attribute) else None)
            if nom != 'run':
                continue
            kw = {k.arg: ast.unparse(k.value) for k in nd.keywords if k.arg}
            if 'result_a3' in kw and 'result_a5' not in kw and 'col_cible' in kw:
                cibles_a4.append((nd.lineno, kw['col_cible']))
            if 'result_a5' in kw and 'col_cible' in kw:
                cibles_a6.append((nd.lineno, kw['col_cible']))
    if cibles_a4 or cibles_a6:
        marque = 'TEST' if 'test' in r.split('/')[-1] else '⚠   '
        print(f"  [{marque}] {r}")
        for L, c in cibles_a4:
            print(f"          l.{L:<5d} A4/A5  col_cible={c}")
        for L, c in cibles_a6:
            print(f"          l.{L:<5d} A6     col_cible={c}")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q4 -- LA COUVERTURE DE TEST DE L'ORCHESTRATEUR")
# ══════════════════════════════════════════════════════════════════════════════
for p in fichiers:
    r = rel(p)
    if 'test' not in r.split('/')[-1] or '/preuves/' in r:
        continue
    try:
        s = io.open(p, encoding='utf-8').read()
    except Exception:
        continue
    if 'pipeline_agents' not in s:
        continue
    a = ast.parse(s)
    tests = [n.name for n in ast.walk(a)
             if isinstance(n, ast.FunctionDef) and n.name.startswith('test')]
    appelle_reellement = 'pipeline_agents(' in s
    print(f"  {r}")
    print(f"      {len(tests)} test(s) ; appelle pipeline_agents() : "
          f"{appelle_reellement}")
    for t in tests:
        print(f"        · {t}")
