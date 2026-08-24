# ruff: noqa
"""RELEVE du SOCLE core -- derivations, severite, mapping_client, mapping_llm.

609 lignes, quatre fichiers qui se disent chacun SOURCE UNIQUE de quelque chose.
AUCUN APPEL A L'API : tout est mesure localement ou par AST.
"""
import io
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

import core.derivations as D
import core.severite as S
import core.mapping_client as MC
from core.plan_tarifaire import PlanTarifaire

RACINE = r'C:\Users\selse\actuaria-app'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


# ══════════════════════════════════════════════════════════════════════════════
titre("G1 -- `derivations` : « MIROIR EXACT de a2._calculer_indicateurs_derives »")
# ══════════════════════════════════════════════════════════════════════════════
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
a2 = AgentA2Preprocessing(verbose=False)
rng = np.random.default_rng(11)
n = 300
brut = pd.DataFrame({
    'bonus_malus': rng.uniform(50, 350, n),
    'antecedents_sinistres_n1': rng.poisson(0.3, n).astype(float),
    'kilometrage_annuel': rng.uniform(5000, 40000, n),
    'exposition': rng.uniform(0.3, 1.0, n),
    'age': rng.uniform(18, 80, n),
    'age_vehicule': rng.uniform(0, 25, n),
    'valeur_mobilier': rng.uniform(5000, 80000, n),
    'surface_m2': rng.uniform(20, 200, n),
    'annee_construction': rng.integers(1900, 2025, n).astype(float),
})
avant = set(brut.columns)
apres = set(a2._calculer_indicateurs_derives(brut.copy()).columns)
produites = apres - avant
declarees = set(D.DERIVATIONS)
print(f"  A2 produit    : {sorted(produites)}")
print(f"  table declare : {sorted(declarees)}")
print(f"  {'[BON    ]' if produites == declarees else '[CONSTAT]'} miroir exact : "
      f"{produites == declarees}")
if produites != declarees:
    print(f"      produites non declarees : {sorted(produites - declarees)}")
    print(f"      declarees non produites : {sorted(declarees - produites)}")

print()
print("  sources_brutes : recursif, ordre preserve, dedupliqué ?")
for lot, _quoi in (
    (['logement_ancien'], "recursif -> annee_construction"),
    (['km_par_an_normalise', 'jeune_conducteur'], "ordre + 2 sources"),
    (['jeune_conducteur', 'senior_conducteur'], "deduplication (age une fois)"),
    (['age', 'colonne_inconnue'], "brutes laissees telles quelles"),
):
    print(f"    {str(lot):48s} -> {D.sources_brutes(lot)}")

# cycle dans la table ?
def _cycle(k, vus=()):
    if k in vus:
        return True
    return any(_cycle(s, vus + (k,)) for s in D.DERIVATIONS.get(k, ()))
cycles = [k for k in D.DERIVATIONS if _cycle(k)]
print(f"  {'[BON    ]' if not cycles else '[CONSTAT]'} aucun cycle dans la table : "
      f"{cycles or 'aucun'}  (aucune garde de recursion dans le code)")

# le test de coherence annonce l.18 existe-t-il ?
tests = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv',
                                            'venv', '.pytest_cache', 'audit')]
    for nm in noms:
        if nm.endswith('.py') and 'test' in nm:
            s = io.open(os.path.join(base, nm), encoding='utf-8',
                        errors='replace').read()
            if 'DERIVATIONS' in s or 'derivations' in s:
                tests.append(os.path.relpath(os.path.join(base, nm), RACINE))
print(f"  test(s) de coherence annonce(s) l.18-20 : {tests or 'INTROUVABLE'}")


# ══════════════════════════════════════════════════════════════════════════════
titre("G2 -- `severite` : LA CHARGE ECRETEE EST-ELLE CONSERVEE ?")
# ══════════════════════════════════════════════════════════════════════════════
rng2 = np.random.default_rng(7)
m = 5000
expo = rng2.uniform(0.2, 1.0, m)
nb = rng2.poisson(0.15 * expo, m).astype(float)
cout = np.where(nb > 0, rng2.gamma(1.6, 900, m) * nb, 0.0)
cout[rng2.choice(m, 5, replace=False)] *= 60      # quelques graves
c = S.construire_cible_severite(pd.Series(cout), pd.Series(nb), pd.Series(expo))
charge_totale = float(cout.sum())
charge_ecretee = float(np.minimum(cout, c.seuil_ecretement).sum())
charge_grave = c.prime_grave_unitaire * float(expo.sum())
print(f"  n = {m}   n_retenus = {c.n_retenus}   n_graves = {c.n_graves}")
print(f"  seuil d'ecretement (q0,995 des couts > 0) = {c.seuil_ecretement:,.2f} EUR")
print(f"  charge TOTALE      = {charge_totale:15,.2f}")
print(f"  charge ECRETEE     = {charge_ecretee:15,.2f}")
print(f"  charge GRAVE reinjectee (prime_grave_unitaire x Sigma expo) = "
      f"{charge_grave:,.2f}")
ecart = abs(charge_ecretee + charge_grave - charge_totale)
print(f"  {'[BON    ]' if ecart < 1e-6 else '[CONSTAT]'} "
      f"ecretee + grave - totale = {ecart:.3e}")

print()
print("  La cible est-elle le cout PAR SINISTRE, jamais le total ?")
idx = np.flatnonzero(c.masque)
k = idx[np.argmax(nb[idx])]           # le contrat avec le plus de sinistres
pos = int(np.searchsorted(idx, k))
print(f"    contrat le plus sinistre : nb = {nb[k]:.0f}  cout total = {cout[k]:,.2f}")
print(f"    severite retenue = {c.severite[pos]:,.2f}  "
      f"= min(cout, seuil)/nb = {min(cout[k], c.seuil_ecretement) / nb[k]:,.2f}")

print()
print("  Le masque exige-t-il un cout OBSERVE, pas seulement un sinistre COMPTE ?")
cout2 = cout.copy()
sans_montant = idx[:50]
cout2[sans_montant] = 0.0             # 50 contrats : nb > 0, cout = 0
c2 = S.construire_cible_severite(pd.Series(cout2), pd.Series(nb), pd.Series(expo))
print(f"    50 contrats passes a cout=0 (nb>0) : n_retenus {c.n_retenus} -> "
      f"{c2.n_retenus}  (ecart {c.n_retenus - c2.n_retenus})")
print(f"    {'[BON    ]' if (c2.severite > 0).all() else '[CONSTAT]'} "
      f"aucune severite nulle dans la cible : min = {c2.severite.min():,.2f}")

print()
print("  Le seuil FOURNI est-il applique sans recalcul (piege V9 train/test) ?")
train, test = slice(0, 2500), slice(2500, m)
ct = S.construire_cible_severite(pd.Series(cout[train]), pd.Series(nb[train]),
                                 pd.Series(expo[train]))
cte_apprend = S.construire_cible_severite(pd.Series(cout[test]), pd.Series(nb[test]),
                                          pd.Series(expo[test]))
cte_fourni = S.construire_cible_severite(pd.Series(cout[test]), pd.Series(nb[test]),
                                         pd.Series(expo[test]),
                                         seuil=ct.seuil_ecretement)
print(f"    seuil appris sur le TRAIN      = {ct.seuil_ecretement:,.2f}")
print(f"    seuil re-appris sur le TEST    = {cte_apprend.seuil_ecretement:,.2f}")
print(f"    seuil FOURNI applique au TEST  = {cte_fourni.seuil_ecretement:,.2f}")
print(f"    {'[BON    ]' if cte_fourni.seuil_ecretement == ct.seuil_ecretement else '[CONSTAT]'} "
      f"le seuil fourni est applique tel quel")

print()
print("  ⚠ SEMANTIQUE : le seuil porte sur quoi, exactement ?")
print(f"    docstring l.51 : « Quantile des couts au-dela duquel un SINISTRE est")
print(f"    dit GRAVE ». Code l.110 : quantile de `cout` = le cout TOTAL du")
print(f"    CONTRAT. Sur ce portefeuille :")
multi = idx[nb[idx] >= 3]
if len(multi):
    au_dela = multi[cout[multi] > c.seuil_ecretement]
    print(f"    contrats a 3+ sinistres depassant le seuil : {len(au_dela)} "
          f"/ {len(multi)}")
    if len(au_dela):
        j = au_dela[0]
        print(f"      ex. nb={nb[j]:.0f}  cout total={cout[j]:,.0f}  "
              f"-> cout par sinistre={cout[j] / nb[j]:,.0f}  "
              f"(seuil={c.seuil_ecretement:,.0f})")

print()
print("  A3 utilise-t-il desormais cette source unique ?")
a3s = io.open(os.path.join(RACINE, 'direction_non_vie/tarification/a3_glm/agent.py'),
              encoding='utf-8').read()
print(f"    A3 importe construire_cible_severite : "
      f"{'construire_cible_severite' in a3s}")
print(f"    A3 a-t-il encore un _calibrer_gamma autonome : "
      f"{'_calibrer_gamma' in a3s}")


# ══════════════════════════════════════════════════════════════════════════════
titre("G3 -- `mapping_client` : LES QUATRE INCOHERENCES SONT-ELLES LEVEES ?")
# ══════════════════════════════════════════════════════════════════════════════
PLAN = PlanTarifaire.depuis_yaml(os.path.join(RACINE, 'plans', 'auto.yaml'))
att = list(PLAN.colonnes_attendues())
base_corr = {'BM': 'bonus_malus', 'AGE': 'age'}
CAS = [
    ("mapping d'une AUTRE LoB",
     MC.MappingClient(client='c', plan='mrh.yaml', correspondances=base_corr)),
    ("cible INCONNUE du plan",
     MC.MappingClient(client='c', plan='auto.yaml',
                      correspondances={'X': 'colonne_qui_nexiste_pas'})),
    ("COLLISION : deux clients -> une cible",
     MC.MappingClient(client='c', plan='auto.yaml',
                      correspondances={'A': 'age', 'B': 'age'})),
    ("temoin : mapping correct",
     MC.MappingClient(client='c', plan='auto.yaml', correspondances=base_corr)),
]
for lib, mp in CAS:
    try:
        MC.valider_mapping(mp, PLAN)
        etat = '[BON    ]' if lib.startswith('temoin') else '[CONSTAT]'
        print(f"  {etat} {lib:38s} ACCEPTE")
    except MC.MappingIncoherent as e:
        etat = '[CONSTAT]' if lib.startswith('temoin') else '[BON    ]'
        print(f"  {etat} {lib:38s} refuse : {str(e)[:34]}...")

# collision avec une colonne DEJA presente
df = pd.DataFrame({c: [1.0] * 5 for c in att})
df['BM'] = 1.0
mp = MC.MappingClient(client='c', plan='auto.yaml',
                      correspondances={'BM': 'bonus_malus'})
try:
    MC.appliquer_mapping(df, mp, PLAN)
    print(f"  [CONSTAT] renommage creant un DOUBLON de colonne : ACCEPTE")
except MC.MappingIncoherent as e:
    print(f"  [BON    ] renommage creant un DOUBLON : refuse -- {str(e)[:40]}...")

# le rapport
df2 = pd.DataFrame({c: [1.0] * 5 for c in att if c != 'bonus_malus'})
df2['BM'] = 1.0
df2['colonne_client_inutile'] = 1.0
mp2 = MC.MappingClient(client='ClientX', plan='auto.yaml',
                       correspondances={'BM': 'bonus_malus',
                                        'CLE_ABSENTE': 'age'})
_dfr, rap = MC.appliquer_mapping(df2, mp2, PLAN)
print()
print(f"  rapport : {rap.n_renommees}/{rap.n_colonnes_attendues} renommees")
print(f"    non couvertes  : {rap.colonnes_plan_non_couvertes}")
print(f"    mortes         : {rap.correspondances_mortes}")
print(f"    client non map.: {rap.colonnes_client_non_mappees}")
print(f"    ampute_previsionnel = {rap.synthese()['ampute_previsionnel']}")
print(f"  synthese_mapping :")
for L in (MC.synthese_mapping(rap) or '').split('. '):
    print(f"      {L[:92]}")

# retro-compat
d3, r3 = MC.preparer_fichier_client(df2, None, PLAN)
print()
print(f"  [{'BON    ' if d3 is df2 and r3 is None else 'CONSTAT'}] "
      f"chemin=None -> le df passe TEL QUEL et le rapport est None")
