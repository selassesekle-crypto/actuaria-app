# ruff: noqa
"""RELEVE core/plan_tarifaire.py -- CE QUE LE SITE D'APPEL CORRIGE.

M5 disait : « valider_contre juge incomplet un fichier complet ». Le site
d'appel (a2.fit, l.779-780) calcule les derivees AVANT de valider. Verification.
Puis P3 : la conséquence reelle de la cible declaree facteur.
"""
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

from core.plan_tarifaire import Facteur, PlanTarifaire
import direction_non_vie.tarification.pipeline_tarifaire as P

RACINE = r'C:\Users\selse\actuaria-app'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


# ══════════════════════════════════════════════════════════════════════════════
titre("M5b -- LE SITE D'APPEL DE `valider_contre` ME CORRIGE-T-IL ?")
# ══════════════════════════════════════════════════════════════════════════════
AUTO = PlanTarifaire.depuis_yaml(os.path.join(RACINE, 'plans', 'auto.yaml'))
print("  a2.fit (l.779-780) fait : _calculer_indicateurs_derives PUIS")
print("  plan.valider_contre. Un fichier portant exactement colonnes_attendues()")
print("  est-il refuse ?")
print()
rng = np.random.default_rng(9)
n = 800
df = pd.DataFrame(index=range(n))
for c in AUTO.colonnes_attendues():
    df[c] = rng.uniform(1, 100, n)
for f in AUTO.facteurs:
    if f.nom in df.columns and f.modalites:
        df[f.nom] = rng.choice([str(m) for m in f.modalites], n)
df[AUTO.exposition] = rng.uniform(0.2, 1.0, n)
df[AUTO.cible_frequence] = rng.poisson(0.1, n).astype(float)
df[AUTO.cible_cout] = rng.gamma(2, 300, n)

manquants_avant = AUTO.valider_contre(list(df.columns))
print(f"  valider_contre SUR LE FICHIER BRUT      : {len(manquants_avant)} "
      f"manquant(s)  {manquants_avant}")

from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
a2 = AgentA2Preprocessing()
df_derive = a2._calculer_indicateurs_derives(df.copy())
manquants_apres = AUTO.valider_contre(list(df_derive.columns))
print(f"  valider_contre APRES les derivees (a2.fit): {len(manquants_apres)} "
      f"manquant(s)  {manquants_apres}")
print()
try:
    a2.fit(df.copy(), AUTO)
    print("  [BON    ] a2.fit(fichier complet, plan auto) : ACCEPTE, ne leve pas")
except ValueError as e:
    print(f"  [CONSTAT] a2.fit leve : {str(e)[:80]}")
print()
print("  -> mon M5 est REFUTE par le site d'appel : `valider_contre` n'est")
print("     jamais appele sur le fichier brut.")


# ══════════════════════════════════════════════════════════════════════════════
titre("P3b -- LA CIBLE DECLAREE FACTEUR : QUEL GINI EN SORTIE ?")
# ══════════════════════════════════════════════════════════════════════════════
rng2 = np.random.default_rng(21)
m = 5000
expo = rng2.uniform(0.2, 1.0, m)
bm = rng2.uniform(50, 350, m)
age = rng2.uniform(18, 80, m)
nb = rng2.poisson(0.12 * expo * (bm / 200.0), m).astype(float)
cout = np.where(nb > 0, rng2.gamma(2, 400, m), 0.0)
dfp = pd.DataFrame({'expo': expo, 'bonus_malus': bm, 'age': age,
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
        t = P.pipeline_complet(dfp.copy(), pl, equilibrer=False)
        pred = t.predire_portefeuille(dfp.copy())
        col = 'frequence' if 'frequence' in pred.columns else pred.columns[0]
        g = P.gini_lorenz(dfp['nb'].to_numpy(), pred[col].to_numpy())
        etat = '[CONSTAT]' if g > 0.60 else '[bon    ]'
        print(f"  {etat} {lib} facteurs={pl.colonnes_produites()}")
        print(f"            colonnes de prediction : {list(pred.columns)}")
        print(f"            gini_lorenz (frequence) = {g:.4f}")
    except Exception as e:
        print(f"  {lib} {type(e).__name__} : {str(e)[:70]}")
print()
print(f"  seuil de vraisemblance du module : "
      f"GINI_PLAUSIBLE_MAX_FREQUENCE = 0.60")


# ══════════════════════════════════════════════════════════════════════════════
titre("P5 -- L'INTERACTION AVEC L'EXPOSITION : MEME QUESTION")
# ══════════════════════════════════════════════════════════════════════════════
B9 = PlanTarifaire(lob='b9', exposition='expo', cible_frequence='nb',
                   cible_cout='cout',
                   facteurs=(Facteur('age', 'continu'),
                             Facteur('bonus_malus', 'continu')),
                   interactions=(('age', 'expo'),))
print(f"  plan accepte : colonnes_produites() = {B9.colonnes_produites()}")
print(f"  'inter_age_expo' porte l'exposition dans la matrice de conception.")
import core.conformite_reglementaire as C
dfb = dfp.copy()
dfb['inter_age_expo'] = dfb['age'] * dfb['expo']
mx = C.construire_matrice_x(list(B9.colonnes_produites()), contexte='P5',
                            df=dfb, col_cible='nb', plan=B9)
dans = 'inter_age_expo' in list(mx)
print(f"  {'[CONSTAT]' if dans else '[BON    ]'} matrice X = {list(mx)}")
print(f"            exclusions = {dict(mx.exclusions)}")
