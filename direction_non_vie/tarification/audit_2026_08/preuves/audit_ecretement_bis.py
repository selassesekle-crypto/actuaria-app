# ruff: noqa
"""L'ASSIETTE DE L'ECRETEMENT -- POURQUOI MON EXEMPLE DISAIT -9,1 % ET LE REEL -1,1 %.

Mon exemple synthetique : severite CONSTANTE (800 EUR exactement) a 4 sin/an.
Le portefeuille reel : severite tres dispersee, 0,14 sin/contrat-sinistre.
Un ordre de grandeur d'ecart s'instruit, il ne se commente pas.

Les DEUX parametres en cause :
  · la FREQUENCE  (combien de sinistres par contrat)
  · la DISPERSION de la severite (si elle est nulle, le quantile du TOTAL
    n'est plus qu'un quantile du NOMBRE)
"""
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

Q = 0.995


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


def ecart_severite(freq, cv, n=60000, seed=5):
    """Ecart de severite entre ecretement AU CONTRAT et AU SINISTRE, sur les
    contrats a 2+ sinistres. cv = coefficient de variation de la severite.
    cv=0 -> severite constante (mon exemple) ; cv~2,5 -> reel."""
    rng = np.random.default_rng(seed)
    nb = rng.poisson(freq, n)
    total = int(nb.sum())
    if total == 0:
        return np.nan, np.nan, 0
    if cv <= 1e-9:
        montants = np.full(total, 1000.0)
    else:
        k = 1.0 / cv ** 2                       # gamma : cv = 1/sqrt(k)
        montants = rng.gamma(k, 1000.0 / k, total)
    idx = np.repeat(np.arange(n), nb)
    sin = pd.DataFrame({'c': idx, 'm': montants})
    ct = sin.groupby('c')['m'].agg(['sum', 'size'])
    s_ctr = float(ct.loc[ct['sum'] > 0, 'sum'].quantile(Q))
    s_sin = float(sin.loc[sin.m > 0, 'm'].quantile(Q))
    sev_ctr = ct['sum'].clip(upper=s_ctr) / ct['size']
    sin['me'] = sin['m'].clip(upper=s_sin)
    sev_sin = sin.groupby('c')['me'].sum() / ct['size']
    multi = ct['size'] >= 2
    if multi.sum() < 20:
        return np.nan, np.nan, int(multi.sum())
    a, b = sev_ctr[multi].mean(), sev_sin[multi].mean()
    return a / b - 1.0, float(ct.loc[multi, 'size'].mean()), int(multi.sum())


# ══════════════════════════════════════════════════════════════════════════════
titre("E5 -- L'ECART DEPEND DE DEUX CHOSES, PAS D'UNE")
# ══════════════════════════════════════════════════════════════════════════════
print("  Ecart de severite (contrats a 2+ sinistres), ecretement CONTRAT vs SINISTRE")
print()
CV = [(0.0, 'constante (mon exemple)'), (0.5, 'peu dispersee'),
      (1.0, 'exponentielle'), (2.5, 'proche du reel PG_2017')]
print(f"    {'freq':>6s} | " + " | ".join(f"{lib[:22]:>22s}" for _, lib in CV))
print(f"    {'':>6s} | " + " | ".join(f"{'cv=' + str(cv):>22s}" for cv, _ in CV))
print("    " + "-" * 100)
for freq in (0.15, 0.5, 1.0, 2.0, 4.0, 8.0):
    cells = []
    for cv, _ in CV:
        e, _m, n = ecart_severite(freq, cv)
        cells.append("       n<20         " if np.isnan(e) else f"{e:+21.2%} ")
    print(f"    {freq:6.2f} | " + " | ".join(f"{c:>22s}" for c in cells))
print()
print("  -> a severite CONSTANTE, le quantile du TOTAL n'est plus qu'un quantile")
print("     du NOMBRE : l'ecretement frappe les contrats nombreux, personne d'autre.")
print("  -> des que la severite est dispersee, le quantile du total est domine par")
print("     la QUEUE des montants, et l'effet s'effondre.")


# ══════════════════════════════════════════════════════════════════════════════
titre("E6 -- OU EST LE PORTEFEUILLE REEL DANS CE TABLEAU ?")
# ══════════════════════════════════════════════════════════════════════════════
import os
RACINE = r'C:\Users\selse\actuaria-app'
sin = pd.read_csv(os.path.join(RACINE, 'data/PG_2017_CLAIMS_YEAR0.csv'))
pos = sin.loc[sin.claim_amount > 0, 'claim_amount']
cv_reel = pos.std() / pos.mean()
ct = sin.groupby('id_client')['claim_amount'].size()
print(f"  PG_2017 : cv de la severite = {cv_reel:.2f}")
print(f"            sinistres/contrat-sinistre = {ct.mean():.2f}  "
      f"(part a 2+ : {(ct >= 2).mean():.1%})")
print(f"  -> colonne cv=2,5, ligne freq basse : l'ecart mesure etait -1,07 %")
print()
print("  Et les LoB du depot qui pourraient sortir de ce regime :")
for lob, f, cv, note in (
        ('auto particuliers', 0.15, 2.5, 'le regime mesure'),
        ('flotte automobile', 4.0, 2.0, 'flotte_automobile.yaml existe'),
        ('protection juridique', 0.30, 0.6, 'prestations peu dispersees'),
        ('assistance', 1.50, 0.4, 'forfaits -> dispersion FAIBLE'),
        ('garantie loyers impayes', 0.20, 0.5, 'loyers = montants proches')):
    e, m, n = ecart_severite(f, cv)
    if np.isnan(e):
        print(f"    {lob:26s} freq={f:4.2f} cv={cv:3.1f}  n<20 contrats a 2+")
    else:
        alerte = '  <-- MATERIEL' if abs(e) > 0.05 else ''
        print(f"    {lob:26s} freq={f:4.2f} cv={cv:3.1f}  ecart={e:+7.2%}"
              f"  ({n:,} contrats a 2+){alerte}   {note}")


# ══════════════════════════════════════════════════════════════════════════════
titre("E7 -- CE QUE COUTERAIT L'ECRETEMENT AU SINISTRE, EN STRUCTURE")
# ══════════════════════════════════════════════════════════════════════════════
import ast
import io
print("  Ce qu'il faudrait, mesure par AST :")
src = io.open(os.path.join(RACINE, 'core/plan_tarifaire.py'), encoding='utf-8').read()
a = ast.parse(src)
for n in a.body:
    if isinstance(n, ast.ClassDef) and n.name == 'PlanTarifaire':
        champs = [c.target.id for c in n.body if isinstance(c, ast.AnnAssign)]
print(f"  1. PlanTarifaire : {len(champs)} champs, AUCUN ne designe une table")
print(f"     seconde -> il faudrait un champ `table_sinistres` + son contrat.")
import inspect
import direction_non_vie.tarification.pipeline_tarifaire as P
print(f"  2. pipeline_complet(portefeuille, plan, ...) : "
      f"{len(inspect.signature(P.pipeline_complet).parameters)} parametres, "
      f"UN seul dataframe")
print("  3. A1.run(dataframe=...) : idem, UN seul dataframe")
print(f"  4. construire_cible_severite(cout_total, nb_sinistres, exposition) : "
      f"3 series AGREGEES")
print()
print("  -> ce n'est pas un correctif : c'est un CONTRAT DE DONNEES nouveau")
print("     (declarer une table sinistres, la charger, la joindre, la propager)")
print()
print("  Ce qui existe DEJA et qu'on ne referait pas :")
print(f"     · A1 reconnait `id_sinistre` dans SYNONYMES_COLONNES (l.110)")
print(f"       -- declare, et utilise NULLE PART ailleurs dans A1")
print(f"     · direction_non_vie/services/nv_triangle_mapping.py mappe DEJA une")
print(f"       table sinistres complete (sinistre_id + 3 mesures) pour A7")
