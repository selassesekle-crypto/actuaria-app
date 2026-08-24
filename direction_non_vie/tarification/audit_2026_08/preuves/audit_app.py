# ruff: noqa
"""actuaria_app.py -- QU'EST-CE QUE C'EST, AVANT DE RECOMMANDER QUOI QUE CE SOIT.

5 181 lignes jamais dans le perimetre. Une recommandation sur un fichier qu'on
n'a pas mesure ne vaut rien.
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
APP = os.path.join(RACINE, 'actuaria_app.py')
src = io.open(APP, encoding='utf-8').read()
lignes = src.split('\n')
arbre = ast.parse(src)


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


# ══════════════════════════════════════════════════════════════════════════════
titre("A1 -- LA FORME DU FICHIER")
# ══════════════════════════════════════════════════════════════════════════════
fns = [n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)]
cls = [n for n in ast.walk(arbre) if isinstance(n, ast.ClassDef)]
haut = [n for n in arbre.body if isinstance(n, ast.FunctionDef)]
code_nu = [n for n in arbre.body
           if not isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import,
                                 ast.ImportFrom, ast.Assign, ast.AnnAssign,
                                 ast.Expr))]
print(f"  {len(lignes):,} lignes · {len(fns)} fonctions ({len(haut)} au niveau module)"
      f" · {len(cls)} classes")
print(f"  instructions de CONTROLE au niveau module (if/for/while/try) : "
      f"{len(code_nu)}")
plus_longues = sorted(haut, key=lambda n: (n.end_lineno or 0) - n.lineno,
                      reverse=True)[:6]
print(f"  les 6 plus longues fonctions :")
for n in plus_longues:
    print(f"      {(n.end_lineno or 0) - n.lineno:5d} l   {n.name}  (l.{n.lineno})")
tot_fn = sum((n.end_lineno or 0) - n.lineno for n in haut)
print(f"  lignes DANS des fonctions : {tot_fn:,} / {len(lignes):,} "
      f"({tot_fn/len(lignes):.0%})")


# ══════════════════════════════════════════════════════════════════════════════
titre("A2 -- LE DISPATCH : COMBIEN DE BRANCHES, ET POUR QUELLES DIRECTIONS ?")
# ══════════════════════════════════════════════════════════════════════════════
besoins = sorted(set(re.findall(r'besoin\s*==\s*["\']([a-z0-9_]+)["\']', src)))
print(f"  {len(besoins)} valeurs distinctes de `besoin` : {besoins}")
DIR = {'tarification': ('prime_glm','prime_ml','prime_dl','selection','sinistres'),
       'provisionnement': ('triangle_xl','ibnr','provisions'),
       'vie/epargne':  ('tarif_deces','tarif_epargne_vie','pm_vie','pb_vie','qrt_vie','ias19'),
       'reglementation': ('stress','s2','mortalite')}
classe = {}
for b in besoins:
    d = next((k for k, v in DIR.items() if b in v), 'autre / non classe')
    classe.setdefault(d, []).append(b)
for d, v in classe.items():
    print(f"      {d:22s} {len(v):2d}  {v}")


# ══════════════════════════════════════════════════════════════════════════════
titre("A3 -- EST-IL TESTE ? EST-IL DANS UNE GATE ?")
# ══════════════════════════════════════════════════════════════════════════════
fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv',
                                            'venv', '.pytest_cache', 'audit',
                                            'node_modules', 'htmlcov')]
    for nm in noms:
        if nm.endswith(('.py', '.yml', '.yaml')):
            fichiers.append(os.path.join(base, nm))
tests_app, gates = [], []
for p in fichiers:
    r = os.path.relpath(p, RACINE).replace('\\', '/')
    if '/preuves/' in r:
        continue
    try:
        s = io.open(p, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    if 'actuaria_app' in s:
        if 'test' in r.split('/')[-1]:
            tests_app.append(r)
        elif r.endswith(('.yml', '.yaml')) or 'gate' in r:
            gates.append(r)
print(f"  fichiers de TEST le mentionnant  : {tests_app or 'AUCUN'}")
print(f"  gates / CI le mentionnant        : {gates or 'AUCUNE'}")
# une fonction de l'app est-elle importable/testable ?
print(f"  le module s'importe-t-il sans effet de bord ? "
      f"{'NON -- code au niveau module' if code_nu else 'a verifier'}")


# ══════════════════════════════════════════════════════════════════════════════
titre("A4 -- CE QU'IL DUPLIQUE DU SOCLE")
# ══════════════════════════════════════════════════════════════════════════════
from core.charts_tarif import COULEURS
charte = {v.upper() for v in COULEURS.values() if v.startswith('#')}
hexs = {h.upper() for h in re.findall(r'#[0-9A-Fa-f]{6}', src)}
print(f"  couleurs hexa en dur : {len(hexs)}  dont {len(hexs & charte)} de la charte V3")
print(f"  importe-t-il core.charts_tarif ? {'core.charts_tarif' in src}")
DUPL = [
    ("config plotly", r'displayModeBar', 'core.charts_tarif.CONFIG_PLOTLY'),
    ("chargement de plan", r'PlanTarifaire\.depuis_yaml', '-'),
    ("seuils RAG en dur", r'\bVERT\b|\bAMBRE\b|\bROUGE\b', '-'),
    ("calcul de prime", r'prime_pure\s*=', 'pipeline_tarifaire'),
    ("gini", r'gini', 'pipeline_tarifaire.gini_lorenz'),
]
for lib, pat, source in DUPL:
    n = len(re.findall(pat, src))
    print(f"      {lib:22s} {n:4d} occurrence(s)   (source unique : {source})")


# ══════════════════════════════════════════════════════════════════════════════
titre("A5 -- QUE PUBLIE-T-IL, ET AVALE-T-IL SES ERREURS ?")
# ══════════════════════════════════════════════════════════════════════════════
st_calls = {}
for n in ast.walk(arbre):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
            and isinstance(n.func.value, ast.Name) and n.func.value.id == 'st':
        st_calls[n.func.attr] = st_calls.get(n.func.attr, 0) + 1
top = sorted(st_calls.items(), key=lambda kv: -kv[1])[:12]
print(f"  {sum(st_calls.values()):,} appels Streamlit, {len(st_calls)} primitives")
print(f"      {', '.join(f'{k}={v}' for k, v in top)}")
tries = [n for n in ast.walk(arbre) if isinstance(n, ast.Try)]
muets = []
for t in tries:
    for h in t.handlers:
        corps = h.body
        if len(corps) == 1 and isinstance(corps[0], ast.Pass):
            muets.append(h.lineno)
        elif all(isinstance(c, ast.Expr) and isinstance(c.value, ast.Constant)
                 for c in corps):
            muets.append(h.lineno)
print(f"  {len(tries)} blocs try · {len(muets)} handler(s) MUETS (pass / docstring)")
if muets:
    print(f"      lignes : {muets[:14]}")
larges = [h.lineno for t in tries for h in t.handlers
          if h.type is None or (isinstance(h.type, ast.Name) and h.type.id == 'Exception')]
print(f"  handlers `except Exception` ou nus : {len(larges)}")


# ══════════════════════════════════════════════════════════════════════════════
titre("A6 -- LE PERIMETRE QUI PUBLIE UN NOMBRE")
# ══════════════════════════════════════════════════════════════════════════════
# Ce qui compte pour un audit : les lignes qui font sortir un CHIFFRE.
chiffres = 0
for i, L in enumerate(lignes, 1):
    if re.search(r'st\.(metric|dataframe|table|write|plotly_chart|markdown)', L) \
            and re.search(r'\{|:\.\d|format|round|f"', L):
        chiffres += 1
print(f"  lignes qui publient un nombre formate a l'ecran : ~{chiffres}")
bloc_tarif = [i for i, L in enumerate(lignes, 1)
              if re.search(r'AgentA[1-6]|pipeline_complet|_plan_auto', L)]
if bloc_tarif:
    print(f"  le bloc de TARIFICATION s'etend de l.{min(bloc_tarif)} a "
          f"l.{max(bloc_tarif)}  ({max(bloc_tarif)-min(bloc_tarif)} lignes)")
print()
print("  -> un audit du fichier ENTIER n'est pas le meme objet qu'un audit")
print("     de ce qui ASSEMBLE et de ce qui PUBLIE UN CHIFFRE.")
