# ruff: noqa
"""Le point le plus grave : un facteur ILLISIBLE rend success=True.
Et : quelle ligne leve reellement dans le repli 'degenere mais defini' ?
Et : l'oracle INV-7 existe-t-il ?
"""
import io
import os
import re
import sys
import traceback
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
import direction_non_vie.tarification.pipeline_tarifaire as P

RACINE = r'C:\Users\selse\actuaria-app'
PLAN = PlanTarifaire.depuis_yaml(os.path.join(RACINE, 'plans', 'auto.yaml'))


def portefeuille(n=3000, seed=1, sans_sinistre=False):
    rng = np.random.default_rng(seed)
    expo = rng.uniform(0.2, 1.0, n)
    bm = rng.uniform(50, 350, n)
    nb = np.zeros(n) if sans_sinistre else rng.poisson(0.10 * expo * (bm / 200.0), n).astype(float)
    df = pd.DataFrame({
        'id_contrat': np.arange(n), 'exposition': expo, 'nb_sinistres': nb,
        'cout_total_sinistres': np.where(nb > 0, rng.gamma(2, 400, n), 0.0),
        'bonus_malus': bm,
    })
    for f in PLAN.facteurs:
        if f.nom in df.columns:
            continue
        if f.type == 'continu':
            df[f.nom] = rng.uniform(1, 100, n)
        elif f.type == 'binaire':
            df[f.nom] = rng.integers(0, 2, n).astype(float)
        else:
            df[f.nom] = rng.choice([str(m) for m in f.modalites], n)
    for col in PLAN.colonnes_attendues():
        if col not in df.columns:
            df[col] = rng.uniform(1, 100, n)
    return df


DF = portefeuille()
T = P.pipeline_complet(DF, PLAN)

print("=" * 78)
print("  UN FACTEUR TARIFAIRE ECRIT EN TOUTES LETTRES -- QUE SE PASSE-T-IL ?")
print("=" * 78)
base = DF.iloc[0].to_dict()
base.pop('exposition')
ref = T.tarifer(dict(base), exposition=1.0)
print(f"  contrat de reference        prime_pure = {ref['prime_pure']:>9.2f}  "
      f"success={ref['success']}")

for nom, val in (('beaucoup', 'beaucoup'), ('texte vide', ''),
                 ('None', None), ('-999', -999.0), ('1e12', 1e12)):
    c = dict(base)
    c['bonus_malus'] = val
    r = T.tarifer(c, exposition=1.0)
    if r['success']:
        ecart = r['prime_pure'] / ref['prime_pure'] - 1 if ref['prime_pure'] else float('nan')
        print(f"  bonus_malus = {nom:12s}  prime_pure = {r['prime_pure']:>9.2f}  "
              f"success=True   ecart vs reference = {ecart:+.1%}")
    else:
        print(f"  bonus_malus = {nom:12s}  success=False  erreur={str(r['erreur'])[:44]!r}")

print()
print("  Et la MEME valeur passee au portefeuille vectoriel ?")
d = DF.iloc[:3].copy()
d['bonus_malus'] = d['bonus_malus'].astype(object)
d.loc[d.index[0], 'bonus_malus'] = 'beaucoup'
try:
    pv = T.predire_portefeuille(d)
    print(f"  predire_portefeuille  -> prime_pure = "
          f"{[round(float(x), 2) for x in pv['prime_pure']]}  (aucune erreur)")
except Exception as ex:
    print(f"  predire_portefeuille  -> {type(ex).__name__} : {str(ex)[:60]}")

print()
print("=" * 78)
print("  QUELLE LIGNE LEVE DANS LE REPLI 'DEGENERE MAIS DEFINI' ?")
print("=" * 78)
try:
    P.pipeline_complet(portefeuille(sans_sinistre=True), PLAN, equilibrer=False)
except Exception:
    for L in traceback.format_exc().split('\n'):
        if 'line' in L and ('actuaria-app' in L):
            print(f"    {L.strip()[:104]}")

print()
print("=" * 78)
print("  L'ORACLE INV-7 EXISTE-T-IL ?")
print("=" * 78)
for f in ('test_plan_invariants.py', 'test_invariants.py'):
    s = io.open(os.path.join(RACINE, 'direction_non_vie/tarification', f),
                encoding='utf-8').read()
    n = len(re.findall(r'INV-?7', s))
    print(f"  {f:26s} mentions de INV-7 : {n}")
    if n:
        i = s.find('INV-7')
        for L in s[i:i + 2000].split('\n'):
            if re.search(r'assertAlmostEqual|places=|delta=|tarifer\(|predire_portefeuille', L):
                print(f"      {L.strip()[:94]}")
