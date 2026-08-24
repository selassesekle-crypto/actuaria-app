# ruff: noqa
"""RELEVE core/qualite_donnees.py -- LES QUATRE REGLES.

« PRINCIPE DIRECTEUR : jamais de correction ou d'exclusion SILENCIEUSE. »
On plante chaque anomalie et on regarde ce qui est dit.
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
                     cible_cout='cout',
                     facteurs=(Facteur('age', 'continu'),))
PLAN_ID = PlanTarifaire(lob='q', exposition='expo', cible_frequence='nb',
                        cible_cout='cout',
                        facteurs=(Facteur('age', 'continu'),),
                        identifiant_contrat='id_pol')


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
titre("M1 -- LES QUATRE REGLES, UNE PAR UNE")
# ══════════════════════════════════════════════════════════════════════════════
CAS = [
    ("R1 frequence < 0",        'nb',   -1.0,  1, 'frequence_negative'),
    ("R1 cout < 0",             'cout', -5.0,  1, 'cout_negatif'),
    ("R1 exposition = 0",       'expo',  0.0,  1, 'exposition_non_positive'),
    ("R1 exposition < 0",       'expo', -0.5,  1, 'exposition_non_positive'),
    ("R2 exposition > 1",       'expo',  2.5,  2, 'exposition_sup_1'),
    ("R3 frequence non entiere", 'nb',   1.7,  3, 'frequence_non_entiere'),
]
for lib, col, val, regle, code in CAS:
    df = portefeuille()
    df.loc[df.index[:20], col] = val          # 20 / 1000 = 2 %, sous le seuil
    r = Q.controler_qualite(df, PLAN)
    trouvee = [a for a in (r.exclusions + r.corrections + r.signalements)
               if a.code == code]
    ok = bool(trouvee) and trouvee[0].regle == regle
    n_ret = r.lignes_retenues
    print(f"  {'[BON    ]' if ok else '[CONSTAT]'} {lib:26s} "
          f"regle={trouvee[0].regle if trouvee else '-'}  "
          f"n={trouvee[0].nb_lignes if trouvee else 0:4d}  "
          f"lignes 1000 -> {n_ret}")
# R1 doublon d'identifiant
df = portefeuille()
df.loc[df.index[:20], 'id_pol'] = df.loc[df.index[500:520], 'id_pol'].to_numpy()
r = Q.controler_qualite(df, PLAN_ID)
d = [a for a in r.exclusions if a.code == 'doublon_identifiant']
print(f"  {'[BON    ]' if d else '[CONSTAT]'} {'R1 doublon identifiant':26s} "
      f"regle={d[0].regle if d else '-'}  n={d[0].nb_lignes if d else 0:4d}  "
      f"lignes 1000 -> {r.lignes_retenues}")
# R3 doublon de ligne SANS identifiant
df = portefeuille().drop(columns=['id_pol'])
df = pd.concat([df, df.iloc[:20]], ignore_index=True)
r = Q.controler_qualite(df, PLAN)
d = [a for a in r.signalements if a.code == 'doublon_ligne']
print(f"  {'[BON    ]' if d else '[CONSTAT]'} {'R3 doublon de ligne':26s} "
      f"regle={d[0].regle if d else '-'}  n={d[0].nb_lignes if d else 0:4d}  "
      f"lignes {len(df)} -> {r.lignes_retenues}  (laissees telles quelles)")
# R3 incoherences, les deux sens
df = portefeuille()
df.loc[df.index[:15], 'nb'] = 0.0
df.loc[df.index[:15], 'cout'] = 500.0
df.loc[df.index[100:110], 'nb'] = 2.0
df.loc[df.index[100:110], 'cout'] = 0.0
r = Q.controler_qualite(df, PLAN)
for code in ('incoherence_cout_sans_sin', 'incoherence_sin_sans_cout'):
    a = [x for x in r.signalements if x.code == code]
    print(f"  {'[BON    ]' if a else '[CONSTAT]'} R3 {code:36s} "
          f"n={a[0].nb_lignes if a else 0}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M2 -- LE SEUIL DE 5 % : OU EST EXACTEMENT LA FRONTIERE ?")
# ══════════════════════════════════════════════════════════════════════════════
print(f"  SEUIL_ESCALADE = {Q.SEUIL_ESCALADE}")
for k in (49, 50, 51):
    df = portefeuille()
    df.loc[df.index[:k], 'nb'] = -1.0
    r = Q.controler_qualite(df, PLAN)
    print(f"    {k:3d}/1000 = {k / 10:.1f} %  ->  bloque={r.bloque!s:5s}  "
          f"escalade={r.escalade_declenchee!s:5s}  "
          f"au_dela={r.anomalies_au_dela_seuil}")
print()
df = portefeuille()
df.loc[df.index[:130], 'expo'] = -1.0
try:
    r = Q.controler_qualite(df, PLAN)
    print(f"  13 % d'expositions negatives -> bloque={r.bloque}  "
          f"dataframe_propre={'None' if r.dataframe_propre is None else 'fourni'}")
    r2 = Q.controler_qualite(df, PLAN, qualite_validee_par='Selasse Sekle',
                             horodatage='2026-08-24T10:00:00')
    print(f"  la meme, VALIDEE nominativement -> bloque={r2.bloque}  "
          f"lignes 1000 -> {r2.lignes_retenues}  validee_par={r2.validee_par!r}")
except Q.QualiteBloquante as e:
    print(f"  QualiteBloquante levee : {str(e)[:60]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M3 -- L'ESCALADE COMPTE PAR TYPE. ET LE TOTAL ?")
# ══════════════════════════════════════════════════════════════════════════════
df = portefeuille()
# quatre types distincts, 4,9 % chacun -- aucun n'atteint 5 %
df.loc[df.index[0:49],    'nb']   = -1.0
df.loc[df.index[50:99],   'cout'] = -5.0
df.loc[df.index[100:149], 'expo'] = 0.0
df.loc[df.index[150:199], 'id_pol'] = df.loc[df.index[600:649], 'id_pol'].to_numpy()
r = Q.controler_qualite(df, PLAN_ID)
total_exclu = sum(a.nb_lignes for a in r.exclusions)
print(f"  quatre types d'anomalie a 4,9 % chacun :")
for a in r.exclusions:
    print(f"      {a.code:26s} {a.nb_lignes:3d} lignes  ({a.proportion:.1%})")
print()
print(f"  total de lignes touchees par la regle 1 : {total_exclu} / 1000 "
      f"= {total_exclu / 1000:.1%}")
print(f"  lignes retenues : {r.lignes_retenues} / 1000")
etat = '[CONSTAT]' if not r.bloque else '[BON    ]'
print(f"  {etat} bloque = {r.bloque}   escalade = {r.escalade_declenchee}")
print(f"  synthese lue par l'actuaire :")
for L in (Q.synthese_qualite_donnees(r) or '').split('\n'):
    for k in range(0, len(L), 92):
        print(f"      {L[k:k + 92]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M4 -- LES VALEURS MANQUANTES : QUELLE REGLE LES VOIT ?")
# ══════════════════════════════════════════════════════════════════════════════
for lib, col, part in (("50 % d'expositions NaN", 'expo', 0.50),
                       ("100 % d'expositions NaN", 'expo', 1.00),
                       ("50 % de frequences NaN", 'nb', 0.50),
                       ("50 % de couts NaN", 'cout', 0.50),
                       ("50 % d'expositions en texte", 'expo', -1)):
    df = portefeuille()
    k = int(len(df) * (part if part > 0 else 0.50))
    if part < 0:
        df[col] = df[col].astype(object)
        df.loc[df.index[:k], col] = 'douze mois'
    else:
        df.loc[df.index[:k], col] = np.nan
    r = Q.controler_qualite(df, PLAN)
    n_anom = len(r.exclusions) + len(r.corrections) + len(r.signalements)
    s = Q.synthese_qualite_donnees(r)
    etat = '[CONSTAT]' if n_anom == 0 else '        '
    print(f"  {etat} {lib:30s} anomalies={n_anom}  bloque={r.bloque!s:5s}  "
          f"lignes 1000 -> {r.lignes_retenues}")
    if n_anom == 0:
        print(f"            synthese = {s!r}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M5 -- UNE EXPOSITION EN MOIS : QUE FAIT LA REGLE 2 ?")
# ══════════════════════════════════════════════════════════════════════════════
df = portefeuille()
df['expo'] = df['expo'] * 12.0          # le meme portefeuille, en MOIS
r = Q.controler_qualite(df, PLAN)
print(f"  exposition en mois (0,3 a 12) : bloque={r.bloque}  "
      f"escalade={r.escalade_declenchee}")
r2 = Q.controler_qualite(df, PLAN, qualite_validee_par='Selasse Sekle',
                         horodatage='2026-08-24T10:00:00')
dfp = r2.dataframe_propre
print(f"  une fois VALIDEE nominativement :")
print(f"      exposition avant : min={df['expo'].min():.2f} "
      f"max={df['expo'].max():.2f} somme={df['expo'].sum():,.0f}")
print(f"      exposition apres : min={dfp['expo'].min():.2f} "
      f"max={dfp['expo'].max():.2f} somme={dfp['expo'].sum():,.0f}")
print(f"      -> {(dfp['expo'] == 1.0).mean():.1%} des lignes ramenees a 1,0")
print(f"  Le seuil 1.0 est ECRIT EN DUR (l.232). Le plan declare le ROLE")
print(f"  `exposition`, jamais son UNITE.")


# ══════════════════════════════════════════════════════════════════════════════
titre("M6 -- `controler_qualite` NE LEVE JAMAIS. QUI LEVE ?")
# ══════════════════════════════════════════════════════════════════════════════
src = io.open(os.path.join(RACINE, 'core/qualite_donnees.py'), encoding='utf-8').read()
arbre = ast.parse(src)
raises = [n for n in ast.walk(arbre) if isinstance(n, ast.Raise)]
print(f"  `raise` dans core/qualite_donnees.py : {len(raises)}")
print(f"  la docstring de QualiteBloquante dit : « Levee par pipeline_complet »")
print()
fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv',
                                            'node_modules', 'venv',
                                            '.pytest_cache', 'htmlcov', 'audit')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))
for p in fichiers:
    r = os.path.relpath(p, RACINE).replace('\\', '/')
    if r == 'core/qualite_donnees.py' or '/preuves/' in r:
        continue
    try:
        s = io.open(p, encoding='utf-8').read()
        a = ast.parse(s)
    except (SyntaxError, UnicodeDecodeError):
        continue
    appelle = any(isinstance(n, ast.Call) and
                  ((isinstance(n.func, ast.Name) and n.func.id == 'controler_qualite')
                   or (isinstance(n.func, ast.Attribute) and n.func.attr == 'controler_qualite'))
                  for n in ast.walk(a))
    if not appelle:
        continue
    verifie = '.bloque' in s
    leve = 'QualiteBloquante' in s and 'raise' in s
    marque = 'TEST' if 'test' in r.split('/')[-1] else '    '
    etat = '        ' if (verifie and leve) else '[CONSTAT]'
    print(f"  {etat} [{marque}] {r[:56]:56s} lit .bloque={verifie!s:5s} "
          f"leve={leve}")

print()
print("  Qui consomme synthese_qualite_donnees ?")
for p in fichiers:
    r = os.path.relpath(p, RACINE).replace('\\', '/')
    if '/preuves/' in r:
        continue
    try:
        s = io.open(p, encoding='utf-8').read()
    except Exception:
        continue
    if 'synthese_qualite_donnees' in s and r != 'core/qualite_donnees.py':
        marque = 'TEST' if 'test' in r.split('/')[-1] else '    '
        print(f"    [{marque}] {r}")
