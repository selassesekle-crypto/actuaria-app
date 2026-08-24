# ruff: noqa
"""RELEVE core/charts_tarif.py -- LA PROPAGATION ET LES CLAIMS DU DOCSTRING.

L'en-tete dit « kaleido absent aujourd'hui » et « SOURCE UNIQUE du style ».
Le docstring de Lorenz porte quatre mesures chiffrees. On verifie.
"""
import ast
import io
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np

import core.charts_tarif as CH

RACINE = r'C:\Users\selse\actuaria-app'
MOI = 'core/charts_tarif.py'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs
               if d not in ('.git', '__pycache__', '.venv', 'node_modules',
                            'venv', '.pytest_cache', 'htmlcov', 'audit')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))


def rel(p):
    return os.path.relpath(p, RACINE).replace('\\', '/')


# ══════════════════════════════════════════════════════════════════════════════
titre("M7b -- KALEIDO EST PRESENT : L'EN-TETE l.15 EST-ELLE PERIMEE ?")
# ══════════════════════════════════════════════════════════════════════════════
import importlib.metadata as md
try:
    v = md.version('kaleido')
except Exception:
    v = '?'
print(f"  kaleido installe : version {v}")
f = CH.chart_lift_decile([0.05, 0.08, 0.12, 0.19, 0.31])
try:
    img = f.to_image(format='png', width=600, height=380)
    print(f"  [BON    ] to_image(png) rend {len(img):,} octets -- "
          f"l'image statique EST produisible")
except Exception as e:
    print(f"  [CONSTAT] to_image -> {type(e).__name__} : {str(e)[:60]}")
print()
print("  L'en-tete l.15 dit : « image statique (kaleido) -- SUIVI (kaleido")
print("  absent aujourd'hui) ».")


# ══════════════════════════════════════════════════════════════════════════════
titre("M8 -- QUI APPELLE LES SEPT FONCTIONS ? (AST)")
# ══════════════════════════════════════════════════════════════════════════════
SYMB = list(CH.__all__)
appels = {s: [] for s in SYMB}
importeurs = {}
for p in fichiers:
    r = rel(p)
    if r == MOI:
        continue
    try:
        a = ast.parse(io.open(p, encoding='utf-8').read())
    except (SyntaxError, UnicodeDecodeError):
        continue
    for nd in ast.walk(a):
        if isinstance(nd, ast.ImportFrom) and (nd.module or '').endswith('charts_tarif'):
            importeurs.setdefault(r, []).extend(x.name for x in nd.names)
        if isinstance(nd, ast.Import):
            for x in nd.names:
                if x.name.endswith('charts_tarif'):
                    importeurs.setdefault(r, []).append('<module>')
        nom = None
        if isinstance(nd, ast.Call):
            nom = (nd.func.id if isinstance(nd.func, ast.Name)
                   else nd.func.attr if isinstance(nd.func, ast.Attribute) else None)
        elif isinstance(nd, ast.Name):
            nom = nd.id
        elif isinstance(nd, ast.Attribute):
            nom = nd.attr
        if nom in appels:
            appels[nom].append(r)
print(f"  {len(importeurs)} fichier(s) importent le module :")
for r in sorted(importeurs):
    marque = 'TEST' if 'test' in r.split('/')[-1] else (
        'PREUVE' if '/preuves/' in r else '    ')
    print(f"    [{marque:6s}] {r}")
print()
for s in SYMB:
    lieux = sorted(set(appels[s]))
    prod = [x for x in lieux if 'test' not in x.split('/')[-1] and '/preuves/' not in x]
    tst = [x for x in lieux if 'test' in x.split('/')[-1]]
    etat = '[CONSTAT]' if not prod else '        '
    print(f"  {etat} {s:32s} production={len(prod):2d}  tests={len(tst):2d}"
          f"   {[x.split('/')[-2] + '/' + x.split('/')[-1] for x in prod]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M9 -- « SOURCE UNIQUE DU STYLE » : Y A-T-IL D'AUTRES FIGURES PLOTLY ?")
# ══════════════════════════════════════════════════════════════════════════════
autres = {}
for p in fichiers:
    r = rel(p)
    if r == MOI or '/preuves/' in r:
        continue
    try:
        s = io.open(p, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    if 'plotly' not in s and 'go.Figure' not in s:
        continue
    n_fig = s.count('go.Figure(') + s.count('make_subplots(')
    n_layout = s.count('update_layout(')
    if n_fig or n_layout:
        autres[r] = (n_fig, n_layout)
print(f"  {len(autres)} fichier(s) construisent une figure plotly hors de ce module :")
for r, (nf, nl) in sorted(autres.items(), key=lambda kv: -kv[1][0]):
    marque = 'TEST' if 'test' in r.split('/')[-1] else '⚠   '
    print(f"    [{marque}] {r[:60]:60s} go.Figure={nf:2d}  update_layout={nl:2d}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M10 -- LES QUATRE MESURES DU DOCSTRING DE LORENZ")
# ══════════════════════════════════════════════════════════════════════════════
# « il ne bouge pas d'un iota quand la prediction passe du hasard a l'oracle »
# « il BAISSE quand le portefeuille se degrade (frequence 0,05 -> 0,95 ;
#    frequence 1,50 -> 0,44) »
# « sur huit tirages : le plafond varie de 1,8 % et le rapport reste entre
#    21,0 % et 21,5 % »
def plafond(y):
    """Gini obtenu en TRIANT PAR LA VALEUR OBSERVEE (l'oracle parfait)."""
    y = np.sort(np.asarray(y, float))[::-1]
    tot = y.sum()
    if tot <= 0:
        return 0.0
    cum = np.cumsum(y) / tot
    pop = np.arange(1, len(y) + 1) / len(y)
    tr = getattr(np, 'trapezoid', None) or np.trapz
    return float(2.0 * tr(cum, pop) - 1.0)


print("  (a) « ne bouge pas d'un iota du hasard a l'oracle » :")
rng = np.random.default_rng(3)
y = rng.poisson(0.10, 20000).astype(float)
print(f"      plafond, tri par l'observe (hasard ou oracle, meme tri) = "
      f"{plafond(y):.4f}")
print(f"      -> le plafond ne depend QUE de y : la prediction n'y entre pas.")

print()
print("  (b) « frequence 0,05 -> 0,95 ; frequence 1,50 -> 0,44 » :")
for fq in (0.05, 0.10, 0.50, 1.00, 1.50, 4.00):
    g = plafond(rng.poisson(fq, 40000).astype(float))
    marque = '  <-- annonce 0,95' if fq == 0.05 else (
        '  <-- annonce 0,44' if fq == 1.50 else '')
    print(f"      frequence {fq:5.2f}  ->  plafond {g:.4f}{marque}")

print()
print("  (c) « sur huit tirages : le plafond varie de 1,8 % » :")
vals = [plafond(np.random.default_rng(100 + k).poisson(0.10, 20000).astype(float))
        for k in range(8)]
etendue = (max(vals) - min(vals)) / np.mean(vals)
print(f"      huit plafonds : {[round(v, 4) for v in vals]}")
print(f"      etendue relative = {etendue:.1%}   (annonce : 1,8 %)")
