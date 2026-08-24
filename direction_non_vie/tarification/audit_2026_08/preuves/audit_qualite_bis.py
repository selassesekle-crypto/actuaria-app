# ruff: noqa
"""RELEVE core/qualite_donnees.py -- CE QUE L'ACTUAIRE LIT, ET QUI APPELLE.

M6 a ete releve AU TEXTE : il comptait les mentions en docstring comme des
appels. On refait PAR AST.
"""
import ast
import io
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

import core.qualite_donnees as Q
from core.plan_tarifaire import Facteur, PlanTarifaire

RACINE = r'C:\Users\selse\actuaria-app'
PLAN = PlanTarifaire(lob='q', exposition='expo', cible_frequence='nb',
                     cible_cout='cout', facteurs=(Facteur('age', 'continu'),))


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


def portefeuille(n=1000, seed=4):
    rng = np.random.default_rng(seed)
    nb = rng.poisson(0.12, n).astype(float)
    return pd.DataFrame({
        'id_pol': np.arange(n), 'expo': rng.uniform(0.3, 1.0, n),
        'age': rng.uniform(18, 80, n), 'nb': nb,
        'cout': np.where(nb > 0, rng.gamma(2, 300, n), 0.0),
    })


# ══════════════════════════════════════════════════════════════════════════════
titre("M5b -- L'EXPOSITION EN MOIS : QUE LIT EXACTEMENT L'ACTUAIRE ?")
# ══════════════════════════════════════════════════════════════════════════════
df = portefeuille()
df['expo'] = df['expo'] * 12.0
print("  AVANT validation (ce qui bloque) :")
r = Q.controler_qualite(df, PLAN)
for L in (Q.synthese_qualite_donnees(r) or '').split('\n'):
    for k in range(0, len(L), 92):
        print(f"      {L[k:k + 92]}")
print()
print("  APRES validation nominative (ce qui part dans les livrables) :")
r2 = Q.controler_qualite(df, PLAN, qualite_validee_par='Selasse Sekle',
                         horodatage='2026-08-24T10:00:00')
for L in (Q.synthese_qualite_donnees(r2) or '').split('\n'):
    for k in range(0, len(L), 92):
        print(f"      {L[k:k + 92]}")
print()
print(f"  exposition totale : {df['expo'].sum():,.0f} -> "
      f"{r2.dataframe_propre['expo'].sum():,.0f}  "
      f"({1 - r2.dataframe_propre['expo'].sum() / df['expo'].sum():.0%} perdue)")


# ══════════════════════════════════════════════════════════════════════════════
titre("M3b -- LES QUATRE TYPES A 4,9 % : LE RAPPORT DIT-IL LE TOTAL ?")
# ══════════════════════════════════════════════════════════════════════════════
df = portefeuille()
df.loc[df.index[0:49],    'nb']   = -1.0
df.loc[df.index[50:99],   'cout'] = -5.0
df.loc[df.index[100:149], 'expo'] = 0.0
df.loc[df.index[150:199], 'nb']   = 1.5           # regle 3
r = Q.controler_qualite(df, PLAN)
res = r.resume()
print(f"  bloque={r.bloque}  escalade={r.escalade_declenchee}  "
      f"au_dela={r.anomalies_au_dela_seuil}")
print(f"  lignes_initiales={res['lignes_initiales']}  "
      f"lignes_retenues={res['lignes_retenues']}  "
      f"-> {res['lignes_initiales'] - res['lignes_retenues']} retirees "
      f"({(res['lignes_initiales'] - res['lignes_retenues']) / 10:.1f} %)")
print(f"  proportions publiees, par type : "
      f"{[a['proportion'] for a in res['exclusions']]}")
print(f"  {'[CONSTAT]' if 'proportion_totale' not in res else '[BON]'} "
      f"le resume porte-t-il une proportion TOTALE ? "
      f"{'proportion_totale' in res}")
print(f"  cles du resume : {sorted(res)}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M6b -- QUI APPELLE VRAIMENT ? (AST, pas au texte)")
# ══════════════════════════════════════════════════════════════════════════════
fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv',
                                            'node_modules', 'venv',
                                            '.pytest_cache', 'htmlcov', 'audit')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))

SYMB = ['controler_qualite', 'synthese_qualite_donnees', 'QualiteBloquante',
        'detecter_negatifs', 'detecter_non_positif', 'detecter_sup',
        'detecter_non_entier', 'detecter_incoherence', 'detecter_doublons_id',
        'detecter_doublons_ligne', 'RapportQualite', 'resume']
appels = {s: [] for s in SYMB}
mentions = {s: [] for s in SYMB}
for p in fichiers:
    rel = os.path.relpath(p, RACINE).replace('\\', '/')
    if rel == 'core/qualite_donnees.py' or '/preuves/' in rel:
        continue
    try:
        src = io.open(p, encoding='utf-8').read()
        a = ast.parse(src)
    except (SyntaxError, UnicodeDecodeError):
        continue
    for s in SYMB:
        if s in src:
            mentions[s].append(rel)
    for nd in ast.walk(a):
        if isinstance(nd, ast.Call):
            nom = (nd.func.id if isinstance(nd.func, ast.Name)
                   else nd.func.attr if isinstance(nd.func, ast.Attribute) else None)
            if nom in appels:
                appels[nom].append(rel)
        elif isinstance(nd, ast.Name) and nd.id in appels:
            appels[nd.id].append(rel)

for s in SYMB:
    ap = sorted(set(x for x in appels[s] if 'test' not in x.split('/')[-1]))
    me = sorted(set(x for x in mentions[s] if 'test' not in x.split('/')[-1]))
    fantomes = [x for x in me if x not in ap]
    etat = '[CONSTAT]' if not ap else '        '
    print(f"  {etat} {s:26s} appels={len(ap)}  mentions_texte={len(me)}")
    for x in ap:
        print(f"                APPEL   {x}")
    for x in fantomes:
        print(f"                (mention seule, pas un appel) {x}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M7 -- LES DETECTEURS SONT-ILS REUTILISES PAR A1, COMME ANNONCE ?")
# ══════════════════════════════════════════════════════════════════════════════
# l.25-28 : « Reutilise la logique de detection deja pensee dans A1
# (_evaluer_qualite) ... A1 pourra les reutiliser (convergence future) »
a1 = os.path.join(RACINE, 'direction_non_vie/tarification/a1_ingestion/agent.py')
s1 = io.open(a1, encoding='utf-8').read()
print(f"  A1 importe core.qualite_donnees : {'core.qualite_donnees' in s1}")
print(f"  A1 a-t-il son propre _evaluer_qualite : {'_evaluer_qualite' in s1}")
import re
for pat, lib in ((r'<\s*0', 'comparaison < 0'), (r'<=\s*0', 'comparaison <= 0'),
                 (r'>\s*1\b', 'comparaison > 1'), (r'duplicated', 'duplicated')):
    n = len(re.findall(pat, s1))
    print(f"    A1 : {lib:22s} {n:3d} occurrence(s)")
print()
print("  -> la « convergence future » annoncee l.28 est-elle faite ? "
      f"{'oui' if 'core.qualite_donnees' in s1 else 'NON -- deux implementations'}")
print(f"  -> `_evaluer_qualite` (citee l.25 comme la fonction d'A1) existe "
      f"dans A1 : {'_evaluer_qualite' in s1}")
print(f"     A1 porte en realite : "
      f"{[m.group(0) for m in re.finditer(r'def (_valider_qualite|_evaluer_qualite)', s1)]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M8 -- `df` EST-IL MUTE EN PLACE ? LES ROLES VIENNENT-ILS TOUS DU PLAN ?")
# ══════════════════════════════════════════════════════════════════════════════
df = portefeuille()
avant = df.copy()
df.loc[df.index[:30], 'expo'] = 3.0            # regle 2
df.loc[df.index[30:50], 'nb'] = -1.0           # regle 1
avant = df.copy()
r = Q.controler_qualite(df, PLAN)
identique = df.equals(avant)
print(f"  [{'BON    ' if identique else 'CONSTAT'}] `df` d'entree inchange "
      f"apres controler_qualite : {identique}")
print(f"            lignes {len(df)} -> dataframe_propre {len(r.dataframe_propre)}")
print(f"            exposition d'entree max = {df['expo'].max():.1f} ; "
      f"de sortie max = {r.dataframe_propre['expo'].max():.1f}")

# Les noms de colonnes sont-ils tous issus du plan ?
srcq = io.open(os.path.join(RACINE, 'core/qualite_donnees.py'), encoding='utf-8').read()
aq = ast.parse(srcq)
fn = [n for n in ast.walk(aq)
      if isinstance(n, ast.FunctionDef) and n.name == 'controler_qualite'][0]
litteraux = set()
for nd in ast.walk(fn):
    if isinstance(nd, ast.Subscript) and isinstance(nd.slice, ast.Constant) \
            and isinstance(nd.slice.value, str):
        litteraux.add(nd.slice.value)
attributs = sorted({nd.attr for nd in ast.walk(fn)
                    if isinstance(nd, ast.Attribute)
                    and isinstance(nd.value, ast.Name) and nd.value.id == 'plan'})
print()
print(f"  roles lus sur le plan : {attributs}")
print(f"  + getattr(plan, ...) : "
      f"{[nd.args[1].value for nd in ast.walk(fn) if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name) and nd.func.id == 'getattr' and isinstance(nd.args[1], ast.Constant)]}")
print(f"  [{'BON    ' if not litteraux else 'CONSTAT'}] noms de colonnes "
      f"litteraux dans controler_qualite : {sorted(litteraux) or 'aucun'}")

# Et les CONSTANTES numeriques codees en dur ?
consts = sorted({nd.value for nd in ast.walk(fn)
                 if isinstance(nd, ast.Constant)
                 and isinstance(nd.value, (int, float))
                 and not isinstance(nd.value, bool)})
print(f"  constantes numeriques dans controler_qualite : {consts}")
