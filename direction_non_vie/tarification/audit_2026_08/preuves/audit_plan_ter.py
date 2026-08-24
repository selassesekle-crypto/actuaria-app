# ruff: noqa
"""RELEVE core/plan_tarifaire.py -- LA PROPAGATION, ET LA CONSEQUENCE.

Le fichier se dit SOURCE UNIQUE et rend la desynchronisation IMPOSSIBLE PAR
CONSTRUCTION. Mesure PAR AST de qui l'utilise reellement.
Puis : M9 a montre que la cible peut se declarer facteur. Quel Gini ?
"""
import ast
import io
import logging
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')
if __name__ == '__main__':
    logging.disable(logging.CRITICAL)

import numpy as np
import pandas as pd

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


MOI = 'core/plan_tarifaire.py'

# ══════════════════════════════════════════════════════════════════════════════
titre("P1 -- QUI APPELLE QUOI ? (AST sur tout le depot)")
# ══════════════════════════════════════════════════════════════════════════════
SYMBOLES = ['colonnes_produites', 'colonnes_sources', 'colonnes_obligatoires',
            'colonnes_attendues', 'facteurs_anteriorite', 'config_encodage',
            'empreinte', 'depuis_dict', 'depuis_yaml', 'valider_contre',
            'verifier_completude_plan', 'plafonner_statut_si_ampute',
            'alerte_modele_ampute', 'synthese_colonnes_plan_manquantes']
appels = {s: [] for s in SYMBOLES}
for p in fichiers:
    r = rel(p)
    if r == MOI:
        continue
    a = arbre_de(p)
    if a is None:
        continue
    for nd in ast.walk(a):
        if isinstance(nd, ast.Call):
            nom = (nd.func.id if isinstance(nd.func, ast.Name)
                   else nd.func.attr if isinstance(nd.func, ast.Attribute) else None)
            if nom in appels:
                appels[nom].append(r)
for s in SYMBOLES:
    lieux = sorted(set(appels[s]))
    prod = [x for x in lieux if 'test' not in x.split('/')[-1]
            and '/preuves/' not in x]
    tst = [x for x in lieux if 'test' in x.split('/')[-1]]
    etat = '[CONSTAT]' if not prod else '        '
    print(f"  {etat} {s:34s} production={len(prod):2d}  tests={len(tst):2d}")
    if s in ('empreinte', 'valider_contre', 'verifier_completude_plan',
             'config_encodage', 'facteurs_anteriorite'):
        for x in prod:
            print(f"                {x}")


# ══════════════════════════════════════════════════════════════════════════════
titre("P2 -- LES APPELANTS DE construire_matrice_x PASSENT-ILS `plan=` ?")
# ══════════════════════════════════════════════════════════════════════════════
# C'est LA question : sans `plan=`, la liste blanche reste
# FACTEURS_TARIFAIRES_AUTORISES -- la 4e liste que l'en-tete dit remplacee.
for p in fichiers:
    r = rel(p)
    a = arbre_de(p)
    if a is None:
        continue
    for nd in ast.walk(a):
        if (isinstance(nd, ast.Call)
                and ((isinstance(nd.func, ast.Name) and nd.func.id == 'construire_matrice_x')
                     or (isinstance(nd.func, ast.Attribute)
                         and nd.func.attr == 'construire_matrice_x'))):
            kw = {k.arg for k in nd.keywords if k.arg}
            marque = 'TEST' if 'test' in r.split('/')[-1] else (
                'PREUVE' if '/preuves/' in r else '    ')
            etat = '        ' if 'plan' in kw else '[CONSTAT]'
            print(f"  {etat} [{marque:6s}] {r[:52]:52s} l.{nd.lineno:<5d} "
                  f"plan={'oui' if 'plan' in kw else 'NON'}  "
                  f"df={'oui' if 'df' in kw else 'non'}  "
                  f"cible={'oui' if 'col_cible' in kw else 'non'}")


# ══════════════════════════════════════════════════════════════════════════════
titre("P3 -- M9 JUSQU'AU BOUT : QUEL GINI QUAND LA CIBLE SE DECLARE FACTEUR ?")
# ══════════════════════════════════════════════════════════════════════════════
from core.plan_tarifaire import Facteur, PlanTarifaire
import direction_non_vie.tarification.pipeline_tarifaire as P

rng = np.random.default_rng(21)
n = 4000
expo = rng.uniform(0.2, 1.0, n)
bm = rng.uniform(50, 350, n)
age = rng.uniform(18, 80, n)
nb = rng.poisson(0.12 * expo * (bm / 200.0), n).astype(float)
cout = np.where(nb > 0, rng.gamma(2, 400, n), 0.0)
df = pd.DataFrame({'expo': expo, 'bonus_malus': bm, 'age': age,
                   'nb': nb, 'cout': cout})

SAIN = PlanTarifaire(lob='sain', exposition='expo', cible_frequence='nb',
                     cible_cout='cout',
                     facteurs=(Facteur('age', 'continu'),
                               Facteur('bonus_malus', 'continu')))
FUITE = PlanTarifaire(lob='fuite', exposition='expo', cible_frequence='nb',
                      cible_cout='cout',
                      facteurs=(Facteur('age', 'continu'),
                                Facteur('bonus_malus', 'continu'),
                                Facteur('nb', 'continu')))
for lib, pl in (('plan SAIN ', SAIN), ('plan FUITE', FUITE)):
    try:
        t = P.pipeline_complet(df.copy(), pl)
        m = t.metriques() if hasattr(t, 'metriques') else {}
        g = (m.get('gini_frequence') or m.get('gini') or
             m.get('gini_freq') or m.get('gini_test'))
        print(f"  {lib} facteurs={pl.colonnes_produites()}")
        print(f"             gini = {g}   (cles : {sorted(m)[:6]})")
    except Exception as e:
        print(f"  {lib} {type(e).__name__} : {str(e)[:70]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("P4 -- LES 20 PLANS : QUELLE PART DES ROLES EST DECLAREE ?")
# ══════════════════════════════════════════════════════════════════════════════
PLANS = os.path.join(RACINE, 'plans')
lignes = []
for nm in sorted(os.listdir(PLANS)):
    if not nm.endswith(('.yaml', '.yml')):
        continue
    pl = PlanTarifaire.depuis_yaml(os.path.join(PLANS, nm))
    lignes.append((nm, len(pl.facteurs), len(pl.colonnes_produites()),
                   bool(pl.identifiant_contrat), bool(pl.echeance),
                   bool(pl.comportement), len(pl.facteurs_anteriorite()),
                   len(pl.interactions)))
print(f"    {'plan':34s} {'fact':>4s} {'cols':>4s} {'id':>3s} {'ech':>4s} "
      f"{'cmp':>4s} {'ant':>4s} {'int':>4s}")
for nm, nf, nc, i, e, c, a, it in lignes:
    print(f"    {nm:34s} {nf:4d} {nc:4d} {'oui' if i else ' - ':>3s} "
          f"{'oui' if e else ' - ':>4s} {'oui' if c else ' - ':>4s} "
          f"{a:4d} {it:4d}")
print()
print(f"  identifiant_contrat : {sum(1 for x in lignes if x[3])}/{len(lignes)}")
print(f"  echeance            : {sum(1 for x in lignes if x[4])}/{len(lignes)}")
print(f"  comportement        : {sum(1 for x in lignes if x[5])}/{len(lignes)}")
