# ruff: noqa
"""LA CHARTE : DEUX SYSTEMES. LEQUEL EST LA REFERENCE DE FAIT ?

Deux questions qui decident, et aucune n'est esthetique :
  1. les deux palettes sortent-elles dans le MEME livrable ?
  2. laquelle est utilisee au-dela de la tarification ?
"""
import ast
import io
import os
import re
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


# les deux palettes, par AST
a = ast.parse(io.open(os.path.join(RACINE, 'actuaria_app.py'), encoding='utf-8').read())
APP = {}
for n in a.body:
    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) \
            and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str) \
            and re.fullmatch(r'#[0-9A-Fa-f]{6}', n.value.value):
        APP[n.targets[0].id] = n.value.value.upper()
from core.charts_tarif import COULEURS
V3 = {k: v.upper() for k, v in COULEURS.items() if v.startswith('#')}
app_v, v3_v = set(APP.values()), set(V3.values())

print(f"  palette APPLICATION : {len(app_v)} couleurs (actuaria_app.py l.23-34)")
print(f"  charte V3           : {len(v3_v)} couleurs (core/charts_tarif.py l.33-44)")
print(f"  en commun           : {sorted(app_v & v3_v)}")


# ══════════════════════════════════════════════════════════════════════════════
titre("C1 -- LES DEUX PALETTES SORTENT-ELLES DANS LE MEME LIVRABLE ?")
# ══════════════════════════════════════════════════════════════════════════════
# Le rapport HTML rend (a) les figures de charts_tarif et (b) celles des agents.
rm = io.open(os.path.join(RACINE,
    'direction_non_vie/tarification/services/rapport_modeles_tarif.py'),
    encoding='utf-8').read()
print(f"  rapport_modeles_tarif.py importe core.charts_tarif : "
      f"{'core.charts_tarif' in rm}")
# ou prend-il les figures ?
print(f"  lit-il les dicts `graphiques` des agents : "
      f"{rm.count(chr(39)+'graphiques'+chr(39)) + rm.count(chr(34)+'graphiques'+chr(34))} mentions")
appels_ct = sorted(set(re.findall(r'chart_\w+', rm)))
print(f"  appelle directement des fonctions charts_tarif : {appels_ct}")
print()
print("  Les figures des AGENTS (palette APP) arrivent-elles dans le meme HTML ?")
for cle in ('graphiques', 'figures', 'fig'):
    n = len(re.findall(rf"\[['\"]?{cle}['\"]?\]|\.get\(['\"]{cle}['\"]", rm))
    print(f"      cle '{cle}' : {n} acces")


# ══════════════════════════════════════════════════════════════════════════════
titre("C2 -- QUELLE PALETTE VIT AU-DELA DE LA TARIFICATION ?")
# ══════════════════════════════════════════════════════════════════════════════
fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv',
                                            'venv', '.pytest_cache', 'audit',
                                            'node_modules', 'htmlcov')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))
compte = {'app': [], 'v3': [], 'les deux': [], 'ni l\'une ni l\'autre': []}
for p in fichiers:
    r = os.path.relpath(p, RACINE).replace('\\', '/')
    if '/preuves/' in r or 'test' in r.split('/')[-1] or r == 'actuaria_app.py' \
            or r == 'core/charts_tarif.py':
        continue
    try:
        s = io.open(p, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    h = {x.upper() for x in re.findall(r'#[0-9A-Fa-f]{6}', s)}
    if not h:
        continue
    a_app = len(h & app_v) >= 3
    a_v3 = len(h & (v3_v - app_v)) >= 2
    cle = ('les deux' if a_app and a_v3 else 'app' if a_app
           else 'v3' if a_v3 else "ni l'une ni l'autre")
    compte[cle].append((r, len(h), len(h & app_v), len(h & v3_v)))
for cle in ('app', 'v3', 'les deux', "ni l'une ni l'autre"):
    v = compte[cle]
    print(f"  palette « {cle} » : {len(v)} fichier(s)")
    for r, n, na, nv in sorted(v)[:10]:
        print(f"      {r[:58]:58s} {n:2d} couleurs · app={na:2d} · v3={nv}")
    if len(v) > 10:
        print(f"      ... et {len(v)-10} autres")


# ══════════════════════════════════════════════════════════════════════════════
titre("C3 -- CE QUE CHAQUE PALETTE PORTE COMME SENS")
# ══════════════════════════════════════════════════════════════════════════════
print("  APPLICATION :")
for k, v in APP.items():
    sens = {'VERT': 'statut RAG', 'AMBRE': 'statut RAG', 'ROUGE': 'statut RAG'}.get(k, '')
    print(f"      {k:8s} {v}   {sens}")
print()
print("  CHARTE V3 :")
for k, v in V3.items():
    print(f"      {k:14s} {v}")
print()
rag_app = [k for k in APP if k in ('VERT', 'AMBRE', 'ROUGE')]
rag_v3 = [k for k in V3 if k.lower() in ('vert', 'ambre', 'rouge')]
print(f"  couleurs de STATUT RAG : app={rag_app}  ·  charte V3={rag_v3 or 'AUCUNE'}")


# ══════════════════════════════════════════════════════════════════════════════
titre("C4 -- LAQUELLE EST TESTABLE ? LAQUELLE EST DECLAREE ?")
# ══════════════════════════════════════════════════════════════════════════════
print(f"  palette APP  : definie dans actuaria_app.py (racine, NON GATABLE)")
print(f"  charte V3    : definie dans core/charts_tarif.py (core/, dans la gate)")
ct = io.open(os.path.join(RACINE, 'core/charts_tarif.py'), encoding='utf-8').read()
m = re.search(r'valid\w+ par ([A-Z]\w+)', ct)
print(f"  la charte V3 porte-t-elle une validation nommee : "
      f"{m.group(0) if m else 'non'}")
tests = [os.path.relpath(p, RACINE).replace('\\', '/') for p in fichiers
         if 'test' in os.path.basename(p) and 'charts_tarif' in
         io.open(p, encoding='utf-8', errors='replace').read()]
print(f"  tests de charts_tarif : {tests}")
