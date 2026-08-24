# ruff: noqa
"""Instruction de M16 et M12, et verification de l'oracle INV-7."""
import io
import os
import re
import sys
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


print("=" * 78)
print("  M16 -- LE REPLI 'DEGENERE MAIS DEFINI' EST-IL DEFINI ?")
print("=" * 78)
print("  Le commentaire l.323 dit : « aucun cout observe : cout moyen constant")
print("  (degenere mais DEFINI) ».  Mesure :")
d = portefeuille(sans_sinistre=True)
try:
    t = P.pipeline_complet(d, PLAN, equilibrer=False)
    print(f"  [BON     ] le repli tient : cout = {t.glm_cout.predict(t._design(d))[0]:.4f}")
except Exception as ex:
    print(f"  [CONSTAT ] {type(ex).__name__} : {str(ex)[:88]}")
    # ou exactement ?
    import traceback
    tb = traceback.format_exc().strip().split('\n')
    for L in tb:
        if 'pipeline_tarifaire' in L or 'severite' in L:
            print(f"            {L.strip()[:96]}")

print()
print("  Et le GLM de FREQUENCE, lui, tient-il sur zero sinistre ?")
try:
    from core.severite import construire_cible_severite
    cs = construire_cible_severite(
        pd.Series(np.zeros(len(d))), pd.Series(np.zeros(len(d))),
        pd.Series(d['exposition'].to_numpy()))
    print(f"  n_retenus = {cs.n_retenus}  -> le repli l.323 est-il ATTEINT ? "
          f"{cs.n_retenus == 0}")
except Exception as ex:
    print(f"  construire_cible_severite : {type(ex).__name__} : {str(ex)[:70]}")

print()
print("=" * 78)
print("  M12 -- L'ERREUR RENDUE PERMET-ELLE D'AGIR ?")
print("=" * 78)
df2 = portefeuille()
t2 = P.pipeline_complet(df2, PLAN)
cas = [
    ("colonne manquante", {'age': 40.0, 'bonus_malus': 200.0}),
    ("type impossible", {**df2.iloc[0].to_dict(), 'bonus_malus': 'beaucoup'}),
]
for nom, contrat in cas:
    contrat.pop('exposition', None)
    r = t2.tarifer(contrat, exposition=1.0)
    print(f"  {nom:22s} success={r['success']}  erreur={str(r.get('erreur'))[:56]!r}")
print("  -> le contrat de sortie {success, erreur} est TENU (docstring l.140).")
print("     La question est la LISIBILITE du message, pas le contrat.")

print()
print("=" * 78)
print("  INV-7 -- COMMENT L'ORACLE VERIFIE-T-IL LA COINCIDENCE ?")
print("=" * 78)
s = io.open(os.path.join(RACINE, 'direction_non_vie/tarification/test_plan_invariants.py'),
            encoding='utf-8').read()
i = s.find('INV-7')
bloc = s[i:i + 2400]
for L in bloc.split('\n'):
    if re.search(r'assert|tarifer|predire_portefeuille|1e-|places=|delta=', L):
        print(f"    {L.strip()[:96]}")
