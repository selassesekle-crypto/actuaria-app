# ruff: noqa
"""Couverture -- resolution de chaque import vers un CHEMIN DE FICHIER REEL.
La seule methode non ambigue. Les trois precedentes ont echoue, chacune sur une
forme d'import differente."""
import ast, io, os
R = r'C:\Users\selse\actuaria-app'
PERIM = [
 'direction_non_vie/tarification/a1_ingestion/agent.py',
 'direction_non_vie/tarification/a2_preprocessing/agent.py',
 'direction_non_vie/tarification/a3_glm/agent.py',
 'direction_non_vie/tarification/a4_ml/agent.py',
 'direction_non_vie/tarification/a5_deep_learning/agent.py',
 'direction_non_vie/tarification/a6_comparaison/agent.py',
 'direction_non_vie/tarification/pipeline_tarifaire.py',
 'direction_non_vie/tarification/pipeline_agents.py',
 'direction_non_vie/tarification/services/rapport_equipe_tarif.py',
 'direction_non_vie/tarification/services/rapport_modeles_tarif.py',
 'direction_non_vie/tarification/services/tarif_excel.py',
 'core/conformite_reglementaire.py', 'core/plan_tarifaire.py',
 'core/charts_tarif.py', 'core/qualite_donnees.py', 'core/severite.py',
 'core/mapping_client.py', 'core/mapping_llm.py', 'core/derivations.py',
 'core/elasticite.py',
]
def resoudre(dotted):
    """'a.b.c' -> chemin du fichier si a/b/c.py existe."""
    c = dotted.replace('.', '/') + '.py'
    return c if os.path.isfile(os.path.join(R, c)) else None

tests = []
for base, dirs, ns in os.walk(R):
    dirs[:] = [d for d in dirs if d not in ('.git','__pycache__','.venv','venv',
                                            '.pytest_cache','audit','node_modules')]
    for nm in ns:
        if nm.endswith('.py') and 'test' in nm:
            p = os.path.join(base, nm)
            if '/preuves/' in p.replace(os.sep, '/'):
                continue
            tests.append(p)
info = {}
for p in tests:
    try:
        a = ast.parse(io.open(p, encoding='utf-8', errors='replace').read())
    except Exception:
        continue
    fichiers = set()
    for n in ast.walk(a):
        if isinstance(n, ast.ImportFrom) and n.module:
            r = resoudre(n.module)                       # from a.b.c import X
            if r: fichiers.add(r)
            for x in n.names:                            # from a.b import c
                r2 = resoudre(f"{n.module}.{x.name}")
                if r2: fichiers.add(r2)
        elif isinstance(n, ast.Import):
            for x in n.names:                            # import a.b.c
                r = resoudre(x.name)
                if r: fichiers.add(r)
    nb = len([n for n in ast.walk(a) if isinstance(n, ast.FunctionDef)
              and n.name.startswith('test')])
    info[os.path.relpath(p, R).replace(os.sep, '/')] = (fichiers, nb)

print(f"  {len(tests)} fichiers de test analyses")
print(f"  {'module':46s} {'l.':>6s} {'tests':>6s} {'l/test':>7s}  fich.")
tl = tt = 0; zero = []; faible = []
for m in PERIM:
    n = len(io.open(os.path.join(R, m), encoding='utf-8', errors='replace').read().split('\n'))
    lieux = [(f, nb) for f, (fs, nb) in info.items() if m in fs]
    t = sum(nb for _, nb in lieux)
    tl += n; tt += t
    r = f"{n/t:.0f}" if t else "0 TEST"
    fl = ''
    if t == 0: zero.append(m); fl = '  <-- AUCUN'
    elif n/t > 60: faible.append((m.split('/')[-2] if '/' in m else m, int(n/t))); fl = '  <-- FAIBLE'
    print(f"  {m[-46:]:46s} {n:6,d} {t:6d} {r:>7s}  {len(lieux)}{fl}")
print(f"  {'TOTAL PERIMETRE':46s} {tl:6,d} {tt:6d} {tl/max(tt,1):7.0f}")
print()
print(f"  ZERO TEST : {[x.split('/')[-1] if 'agent' not in x else x.split('/')[-2] for x in zero] or 'aucun'}")
print(f"  FAIBLE (>60 l/test) : {faible or 'aucun'}")
