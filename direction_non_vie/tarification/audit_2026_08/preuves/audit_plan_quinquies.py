# ruff: noqa
"""RELEVE core/plan_tarifaire.py -- POURQUOI LA FUITE N'A PAS EU LIEU.

P3b m'a refute : le plan declare la cible en facteur, et le Gini ne bouge pas.
Une coincidence pareille ne se commente pas -- elle s'instruit.
"""
import ast
import io
import logging
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')
logging.disable(logging.CRITICAL)

import numpy as np
import pandas as pd

import core.conformite_reglementaire as C
from core.plan_tarifaire import Facteur, PlanTarifaire
import direction_non_vie.tarification.pipeline_tarifaire as P

RACINE = r'C:\Users\selse\actuaria-app'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


rng = np.random.default_rng(21)
m = 5000
expo = rng.uniform(0.2, 1.0, m)
bm = rng.uniform(50, 350, m)
age = rng.uniform(18, 80, m)
nb = rng.poisson(0.12 * expo * (bm / 200.0), m).astype(float)
cout = np.where(nb > 0, rng.gamma(2, 400, m), 0.0)
dfp = pd.DataFrame({'expo': expo, 'bonus_malus': bm, 'age': age,
                    'nb': nb, 'cout': cout})
FUITE = PlanTarifaire(lob='fuite', exposition='expo', cible_frequence='nb',
                      cible_cout='cout',
                      facteurs=(Facteur('age', 'continu'),
                                Facteur('bonus_malus', 'continu'),
                                Facteur('nb', 'continu')))

# ══════════════════════════════════════════════════════════════════════════════
titre("Q1 -- UNE CIBLE, OU DEUX ? C'EST TOUTE LA DIFFERENCE")
# ══════════════════════════════════════════════════════════════════════════════
for lib, cible in (("col_cible='nb'          (UNE seule)", 'nb'),
                   ("col_cible=['nb','cout'] (les DEUX)", ['nb', 'cout'])):
    mx = C.construire_matrice_x(list(FUITE.colonnes_produites()), contexte='Q1',
                                df=dfp, col_cible=cible, plan=FUITE)
    dans = 'nb' in list(mx)
    print(f"  {'[CONSTAT]' if dans else '[BON    ]'} {lib} -> matrice X = {list(mx)}")
    if not dans:
        print(f"            motif = {mx.exclusions.get('nb', '')[:74]}")
print()
print("  C'est la DEUXIEME cible qui denonce la premiere : `exemptees`")
print("  (conformite l.1123-1125) contient la cible EN COURS d'examen, pas les")
print("  autres. Le pipeline passe les deux -- d'ou l'absence de fuite en P3b.")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q2 -- LES APPELANTS PASSENT-ILS UNE CIBLE, OU DEUX ?")
# ══════════════════════════════════════════════════════════════════════════════
fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs
               if d not in ('.git', '__pycache__', '.venv', 'node_modules',
                            'venv', '.pytest_cache', 'htmlcov', 'audit')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))
for p in fichiers:
    r = os.path.relpath(p, RACINE).replace('\\', '/')
    if 'test' in r.split('/')[-1] or '/preuves/' in r:
        continue
    try:
        a = ast.parse(io.open(p, encoding='utf-8').read())
    except (SyntaxError, UnicodeDecodeError):
        continue
    for nd in ast.walk(a):
        if (isinstance(nd, ast.Call)
                and ((isinstance(nd.func, ast.Name) and nd.func.id == 'construire_matrice_x')
                     or (isinstance(nd.func, ast.Attribute)
                         and nd.func.attr == 'construire_matrice_x'))):
            for k in nd.keywords:
                if k.arg == 'col_cible':
                    forme = ('LISTE' if isinstance(k.value, (ast.List, ast.Tuple))
                             else 'une seule')
                    etat = '        ' if forme == 'LISTE' else '[CONSTAT]'
                    try:
                        txt = ast.unparse(k.value)[:40]
                    except Exception:
                        txt = '?'
                    print(f"  {etat} {r[31:][:44]:44s} l.{nd.lineno:<5d} "
                          f"{forme:9s} {txt}")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q3 -- ET SI LA DEUXIEME CIBLE NE DENONCE PAS ? (cout constant)")
# ══════════════════════════════════════════════════════════════════════════════
# La protection de Q1 repose sur la CORRELATION entre les deux cibles. Si le
# cout ne varie pas (portefeuille a cout forfaitaire -- assistance, protection
# juridique, GLI : des prestations a montant fixe), elle disparait.
dfc = dfp.copy()
dfc['cout'] = np.where(dfc['nb'] > 0, 500.0, 0.0)     # cout forfaitaire
mx = C.construire_matrice_x(list(FUITE.colonnes_produites()), contexte='Q3',
                            df=dfc, col_cible=['nb', 'cout'], plan=FUITE)
print(f"  cout strictement forfaitaire (500 EUR par sinistre) :")
print(f"  matrice X = {list(mx)}   exclusions = {list(mx.exclusions)}")
dfc2 = dfp.copy()
dfc2['cout'] = 500.0                                   # cout CONSTANT
mx2 = C.construire_matrice_x(list(FUITE.colonnes_produites()), contexte='Q3',
                             df=dfc2, col_cible=['nb', 'cout'], plan=FUITE)
dans = 'nb' in list(mx2)
print(f"  cout CONSTANT (variance nulle) :")
print(f"  {'[CONSTAT]' if dans else '[BON    ]'} matrice X = {list(mx2)}   "
      f"exclusions = {list(mx2.exclusions)}")
print(f"            controle_effet_execute = {mx2.controle_effet_execute}")


# ══════════════════════════════════════════════════════════════════════════════
titre("Q4 -- L'INTERACTION AVEC L'EXPOSITION, JUSQU'AU BOUT")
# ══════════════════════════════════════════════════════════════════════════════
B9 = PlanTarifaire(lob='b9', exposition='expo', cible_frequence='nb',
                   cible_cout='cout',
                   facteurs=(Facteur('age', 'continu'),
                             Facteur('bonus_malus', 'continu')),
                   interactions=(('age', 'expo'),))
print(f"  le plan ACCEPTE : {B9.colonnes_produites()}")
try:
    t = P.pipeline_complet(dfp.copy(), B9, equilibrer=False)
    print(f"  [BON    ] pipeline_complet tourne. features retenues = {t.features}")
    dedans = any('expo' in f for f in t.features)
    print(f"  {'[CONSTAT]' if dedans else '[BON    ]'} une feature porte "
          f"l'exposition : {dedans}")
    if dedans:
        # symptome B9 : la prime cesse d'etre proportionnelle a l'exposition
        d1 = dfp.copy(); d1['expo'] = 0.5
        d2 = dfp.copy(); d2['expo'] = 1.0
        p1 = t.predire_portefeuille(d1)['prime_pure'].sum()
        p2 = t.predire_portefeuille(d2)['prime_pure'].sum()
        print(f"            prime totale a expo=0,5 : {p1:12.2f}")
        print(f"            prime totale a expo=1,0 : {p2:12.2f}")
        print(f"            rapport = {p2 / p1:.4f}   (2,0000 attendu si "
              f"proportionnel)")
except Exception as e:
    print(f"  pipeline_complet : {type(e).__name__} : {str(e)[:66]}")
