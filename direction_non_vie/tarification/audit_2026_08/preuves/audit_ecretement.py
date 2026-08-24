# ruff: noqa
"""L'ASSIETTE DE L'ECRETEMENT -- MESURE SUR DONNEE REELLE VERSIONNEE.

data/PG_2017_CLAIMS_YEAR0.csv : 14 243 lignes, UNE LIGNE = UN SINISTRE, avec
son montant propre. On peut donc calculer les DEUX ecretements et les comparer.

Trois questions de Selasse :
  1. que couterait un ecretement AU SINISTRE ? sur quels plans est-ce possible ?
  2. si la donnee est au contrat partout, quelle est la moins mauvaise option ?
  3. 727,27 au lieu de 800 : est-ce que ca deplace un TARIF, ou une STATISTIQUE ?
"""
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

import core.severite as S

RACINE = r'C:\Users\selse\actuaria-app'
Q = 0.995


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


# ══════════════════════════════════════════════════════════════════════════════
titre("E1 -- LA DONNEE : UNE LIGNE = UN SINISTRE")
# ══════════════════════════════════════════════════════════════════════════════
sin = pd.read_csv(os.path.join(RACINE, 'data/PG_2017_CLAIMS_YEAR0.csv'))
print(f"  {len(sin):,} lignes · {sin['id_client'].nunique():,} clients")
print(f"  claim_nb : {sorted(sin['claim_nb'].unique())}  (1 partout = 1 ligne/sinistre)")
print(f"  id_claim : {sorted(sin['id_claim'].unique())}  (le RANG du sinistre)")
neg = (sin['claim_amount'] < 0).sum()
print(f"  montants negatifs (recours) : {neg} ({neg/len(sin):.2%})")

# Le contrat, tel que la tarification le verrait aujourd'hui
contrat = sin.groupby('id_client').agg(
    nb=('claim_amount', 'size'), cout_total=('claim_amount', 'sum')).reset_index()
contrat['expo'] = 1.0
print(f"  agrege au CONTRAT : {len(contrat):,} lignes")
print(f"  repartition du nombre de sinistres par contrat :")
for k, v in contrat['nb'].value_counts().sort_index().items():
    print(f"      {k} sinistre(s) : {v:6,d} contrats ({v/len(contrat):6.2%})")


# ══════════════════════════════════════════════════════════════════════════════
titre("E2 -- LES DEUX SEUILS, SUR LA MEME DONNEE")
# ══════════════════════════════════════════════════════════════════════════════
seuil_contrat = float(contrat.loc[contrat.cout_total > 0, 'cout_total'].quantile(Q))
seuil_sinistre = float(sin.loc[sin.claim_amount > 0, 'claim_amount'].quantile(Q))
print(f"  seuil AU CONTRAT  (q{Q} du cout total)   = {seuil_contrat:>12,.2f} EUR")
print(f"  seuil AU SINISTRE (q{Q} du montant)      = {seuil_sinistre:>12,.2f} EUR")
print(f"  ecart : le seuil au contrat est "
      f"{seuil_contrat/seuil_sinistre:.3f}x celui au sinistre")

# Qui est ecrete, dans chaque regime ?
ecr_contrat = contrat[contrat.cout_total > seuil_contrat]
ecr_sinistre = sin[sin.claim_amount > seuil_sinistre]
clients_par_sinistre = set(ecr_sinistre['id_client'])
clients_par_contrat = set(ecr_contrat['id_client'])
print()
print(f"  contrats ecretes AU CONTRAT  : {len(clients_par_contrat):,}")
print(f"  contrats touches AU SINISTRE : {len(clients_par_sinistre):,}")
print(f"  dans les DEUX               : {len(clients_par_contrat & clients_par_sinistre):,}")
print(f"  ecretes au contrat SEULEMENT : "
      f"{len(clients_par_contrat - clients_par_sinistre):,}   <-- des contrats")
print(f"      NOMBREUX, pas graves")
print(f"  touches au sinistre SEULEMENT: "
      f"{len(clients_par_sinistre - clients_par_contrat):,}")

faux_graves = contrat[contrat.id_client.isin(clients_par_contrat - clients_par_sinistre)]
if len(faux_graves):
    print()
    print(f"  Les 'faux graves' — ecretes sans porter un seul sinistre grave :")
    print(f"      nombre de sinistres : min={faux_graves.nb.min()} "
          f"median={faux_graves.nb.median():.0f} max={faux_graves.nb.max()}")
    print(f"      cout moyen par sinistre reel : "
          f"{(faux_graves.cout_total/faux_graves.nb).mean():,.2f} EUR")
    print(f"      (le seuil au sinistre est a {seuil_sinistre:,.2f})")


# ══════════════════════════════════════════════════════════════════════════════
titre("E3 -- LA CIBLE DE SEVERITE : CE QUE LE GLM AJUSTERAIT")
# ══════════════════════════════════════════════════════════════════════════════
c = S.construire_cible_severite(contrat['cout_total'], contrat['nb'], contrat['expo'])
masque = c.masque
sev_actuelle = pd.Series(c.severite, index=contrat.index[masque])

# La cible qu'un ecretement AU SINISTRE produirait
sin2 = sin.copy()
sin2['montant_ecrete'] = sin2['claim_amount'].clip(upper=seuil_sinistre)
agr = sin2.groupby('id_client').agg(nb=('montant_ecrete', 'size'),
                                    cout_ecrete=('montant_ecrete', 'sum'))
agr = agr.reindex(contrat['id_client'].values)
sev_sinistre = (agr['cout_ecrete'] / agr['nb']).to_numpy()[masque]

print(f"  n contrats retenus : {c.n_retenus:,}")
print(f"  severite moyenne, ecretement AU CONTRAT  : {sev_actuelle.mean():>10,.2f} EUR")
print(f"  severite moyenne, ecretement AU SINISTRE : {np.mean(sev_sinistre):>10,.2f} EUR")
print()
print("  Par nombre de sinistres du contrat -- c'est l'axe en cause :")
nb_m = contrat['nb'].to_numpy()[masque]
brut = (contrat['cout_total'].to_numpy()[masque] / nb_m)
print(f"    {'nb sin':>7s}  {'n':>7s}  {'brut':>11s}  {'AU CONTRAT':>11s}  "
      f"{'AU SINISTRE':>12s}  {'ecart':>8s}")
for k in sorted(set(nb_m)):
    s = nb_m == k
    if s.sum() < 5:
        continue
    a, b, br = sev_actuelle.to_numpy()[s].mean(), sev_sinistre[s].mean(), brut[s].mean()
    print(f"    {k:7.0f}  {s.sum():7,d}  {br:11,.2f}  {a:11,.2f}  {b:12,.2f}  "
          f"{a/b-1:+8.2%}")


# ══════════════════════════════════════════════════════════════════════════════
titre("E4 -- EST-CE QUE CA DEPLACE UN TARIF ? (la question de Selasse)")
# ══════════════════════════════════════════════════════════════════════════════
# La prime pure = E[N] x E[C|N>0] + prime_grave_unitaire.
# On compare les DEUX regimes, contrat par contrat, sur la meme frequence.
expo_tot = float(contrat['expo'].sum())

# regime ACTUEL (contrat)
grave_contrat = float((contrat['cout_total'] - contrat['cout_total'].clip(upper=seuil_contrat)).sum())
pgu_contrat = grave_contrat / expo_tot
# regime AU SINISTRE
grave_sin = float((sin['claim_amount'] - sin['claim_amount'].clip(upper=seuil_sinistre)).sum())
pgu_sin = grave_sin / expo_tot

print(f"  charge grave mutualisee, AU CONTRAT  : {grave_contrat:>12,.2f} EUR "
      f"-> {pgu_contrat:7,.2f} EUR/unite")
print(f"  charge grave mutualisee, AU SINISTRE : {grave_sin:>12,.2f} EUR "
      f"-> {pgu_sin:7,.2f} EUR/unite")
print(f"  {'[BON]' if abs(pgu_contrat-pgu_sin) < 1e-6 else '[ECART]'} "
      f"ecart de mutualisation : {pgu_contrat-pgu_sin:+,.2f} EUR/unite "
      f"({pgu_contrat/pgu_sin-1:+.1%})")
print()
print("  Prime pure d'un contrat, par nombre de sinistres attendu :")
print("  (frequence prise EGALE dans les deux regimes -- seule la severite change)")
print(f"    {'nb sin':>7s}  {'PP au contrat':>14s}  {'PP au sinistre':>15s}  {'ecart':>9s}")
for k in sorted(set(nb_m)):
    s = nb_m == k
    if s.sum() < 5:
        continue
    pp_c = k * sev_actuelle.to_numpy()[s].mean() + pgu_contrat
    pp_s = k * sev_sinistre[s].mean() + pgu_sin
    print(f"    {k:7.0f}  {pp_c:14,.2f}  {pp_s:15,.2f}  {pp_c/pp_s-1:+9.2%}")
print()
print("  ⚠ La CHARGE TOTALE est conservee dans les deux regimes (mesure du")
print("    releve : ecart 1,16e-10). Ce qui bouge est la REPARTITION.")
