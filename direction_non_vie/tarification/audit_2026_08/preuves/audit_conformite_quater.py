# ruff: noqa
"""RELEVE core/conformite_reglementaire.py -- LES TROIS DERNIERES QUESTIONS.

Q1. « TOUS les livrables l'appellent » -- combien de livrables existe-t-il ?
Q2. La justification que le module se donne pour Vie/Sante tient-elle ?
Q3. sp_data_builder : mon soupcon de filtre duplique etait FAUX. Que fait-il ?
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
    dirs[:] = [d for d in dirs
               if d not in ('.git', '__pycache__', '.venv', 'node_modules',
                            'venv', '.pytest_cache', 'htmlcov', 'audit')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))


def rel(p):
    return os.path.relpath(p, RACINE).replace('\\', '/')


def arbre_de(p):
    try:
        return ast.parse(io.open(p, encoding='utf-8').read())
    except (SyntaxError, UnicodeDecodeError):
        return None


# ══════════════════════════════════════════════════════════════════════════════
titre("Q1 -- COMBIEN DE LIVRABLES LA TARIFICATION PRODUIT-ELLE ?")
# ══════════════════════════════════════════════════════════════════════════════
# Un livrable = un fichier qui ECRIT un document destine a l'actuaire.
MARQUES_ECRITURE = ('Document(', 'Workbook(', 'to_excel', 'xlsxwriter',
                    '.docx', '.xlsx', '.html', 'write_html', 'add_heading',
                    'add_paragraph', 'ExcelWriter')
SOURCES_UNIQUES = ('avertissement_walk_forward', 'synthese_exclusions',
                   'synthese_alertes_experience', 'synthese_modele_dl')

livrables = {}
for p in fichiers:
    r = rel(p)
    if not r.startswith('direction_non_vie/tarification/'):
        continue
    if 'test' in r.split('/')[-1] or '/preuves/' in r:
        continue
    src = io.open(p, encoding='utf-8', errors='replace').read()
    if not any(m in src for m in MARQUES_ECRITURE):
        continue
    a = arbre_de(p)
    if a is None:
        continue
    appelees = set()
    for nd in ast.walk(a):
        if isinstance(nd, ast.Call):
            nom = (nd.func.id if isinstance(nd.func, ast.Name)
                   else nd.func.attr if isinstance(nd.func, ast.Attribute) else None)
            if nom in SOURCES_UNIQUES:
                appelees.add(nom)
    livrables[r] = appelees

print(f"  {len(livrables)} fichier(s) de tarification ecrivent un document :")
print()
print(f"    {'fichier':52s} {'wf':>3s} {'exc':>4s} {'alt':>4s} {'dl':>3s}")
for r in sorted(livrables):
    a = livrables[r]
    def m(x):
        return ' ok' if x in a else ' --'
    etat = '        ' if len(a) == 4 else '[CONSTAT]'
    print(f"  {etat}{r[31:]:44s} {m('avertissement_walk_forward')} "
          f"{m('synthese_exclusions'):>4s} {m('synthese_alertes_experience'):>4s} "
          f"{m('synthese_modele_dl'):>3s}")
complets = [r for r, a in livrables.items() if len(a) == 4]
print()
print(f"  {len(complets)}/{len(livrables)} livrable(s) appellent les QUATRE "
      f"sources uniques.")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q2 -- VIE ET SANTE CONSTRUISENT-ELLES UNE MATRICE X ?")
# ══════════════════════════════════════════════════════════════════════════════
# Le module (l.30-37) se justifie ainsi : « Elles ne sont pas exposees
# aujourd'hui parce que leurs agents de tarification sont PARAMETRIQUES (ils ne
# construisent pas de matrice X a partir de donnees client). »
# Un ajustement sur donnees = un appel a un estimateur sklearn/statsmodels.
ESTIMATEURS = ('GLM', 'OLS', 'Logit', 'Poisson', 'GLMGam',
               'LinearRegression', 'LogisticRegression', 'RandomForestRegressor',
               'RandomForestClassifier', 'GradientBoostingRegressor',
               'XGBRegressor', 'LGBMRegressor', 'HistGradientBoostingRegressor',
               'DecisionTreeRegressor', 'Sequential', 'fit')
for direction in ('direction_vie_epre', 'direction_sante_prevoyance'):
    trouves = {}
    for p in fichiers:
        r = rel(p)
        if not r.startswith(direction + '/'):
            continue
        if 'test' in r.split('/')[-1]:
            continue
        a = arbre_de(p)
        if a is None:
            continue
        for nd in ast.walk(a):
            if isinstance(nd, ast.Call):
                nom = (nd.func.id if isinstance(nd.func, ast.Name)
                       else nd.func.attr if isinstance(nd.func, ast.Attribute)
                       else None)
                if nom in ESTIMATEURS and nom != 'fit':
                    trouves.setdefault(r, set()).add(nom)
    print(f"  {direction:28s} : {len(trouves)} fichier(s) instancient un "
          f"estimateur statistique")
    for r in sorted(trouves)[:8]:
        print(f"      {r[len(direction) + 1:]:52s} {sorted(trouves[r])}")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q3 -- QUE FAIT REELLEMENT sp_data_builder AVEC 'sexe' ?")
# ══════════════════════════════════════════════════════════════════════════════
p = os.path.join(RACINE, 'direction_sante_prevoyance/services/sp_data_builder.py')
src = io.open(p, encoding='utf-8').read()
print("  Mon soupcon (P3) etait : « un filtre genre reimplemente localement ».")
print("  Lecture : c'est une table de SYNONYMES. Elle ne FILTRE pas le genre,")
print("  elle le NORMALISE en une colonne canonique 'sexe'. Soupcon REFUTE.")
print()
lignes = [(i + 1, L) for i, L in enumerate(src.split('\n'))
          if 'sexe' in L.lower()]
print(f"  {len(lignes)} ligne(s) mentionnent 'sexe' dans ce fichier :")
for i, L in lignes[:14]:
    print(f"    {i:5d}  {L.strip()[:88]}")
print()
# et ailleurs en Sante/Vie : la colonne canonique atteint-elle un modele ?
print("  La colonne canonique 'sexe' est-elle LUE ailleurs en Sante/Vie ?")
for direction in ('direction_sante_prevoyance', 'direction_vie_epre'):
    n = 0
    lieux = []
    for q in fichiers:
        r = rel(q)
        if not r.startswith(direction + '/') or r.endswith('sp_data_builder.py'):
            continue
        s = io.open(q, encoding='utf-8', errors='replace').read()
        c = s.lower().count("'sexe'") + s.lower().count('"sexe"')
        if c:
            n += c
            lieux.append((r, c))
    print(f"    {direction:28s} {n} occurrence(s) sur {len(lieux)} fichier(s)")
    for r, c in sorted(lieux, key=lambda t: -t[1])[:6]:
        marque = 'TEST' if 'test' in r.split('/')[-1] else '    '
        print(f"      [{marque}] {r[len(direction) + 1:]:56s} {c}")
