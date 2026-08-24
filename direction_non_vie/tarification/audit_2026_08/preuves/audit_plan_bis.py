# ruff: noqa
"""RELEVE core/plan_tarifaire.py -- LA CHAINE, ET LE CONTRAT AVEC A2.

M4 avait echoue par MA faute (mauvaise cle de retour). On reprend.
Et M3 a ouvert une question qui ne se tranche pas dans ce fichier : le plan
accepte de declarer LA CIBLE comme facteur. Jusqu'ou va-t-elle ?
"""
import logging
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')
if __name__ == '__main__':
    logging.disable(logging.CRITICAL)

import numpy as np
import pandas as pd

import core.conformite_reglementaire as C
from core.plan_tarifaire import (
    Facteur, PlanTarifaire, synthese_colonnes_plan_manquantes,
)

def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


# ══════════════════════════════════════════════════════════════════════════════
titre("M4b -- `_slug` EST-IL CE QUE A2 APPLIQUE ? (« c'est le contrat », l.54)")
# ══════════════════════════════════════════════════════════════════════════════
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing

MODALITES = ('Île-de-France', "Provence-Alpes-Côte d'Azur", 'Hauts de France',
             'Nouvelle-Aquitaine', 'RHÔNE')
p = PlanTarifaire(
    lob='slug', exposition='expo', cible_frequence='nb', cible_cout='cout',
    facteurs=(Facteur('age', 'continu'),
              Facteur('region', 'categoriel', encodage='one_hot',
                      modalites=MODALITES, reference='Hauts de France')),
)
attendues = set(p.colonnes_produites())
rng = np.random.default_rng(5)
n = 600
df = pd.DataFrame({
    'expo': rng.uniform(0.3, 1.0, n),
    'nb': rng.poisson(0.1, n).astype(float),
    'cout': rng.gamma(2, 300, n),
    'age': rng.uniform(18, 80, n),
    'region': rng.choice(list(MODALITES), n),
})
r = AgentA2Preprocessing().run(
    {'dataframe': df.copy(), 'branche': 'auto', 'success': True},
    cible_frequence='nb', cible_cout='cout', plan=p)
assert r['success'], r.get('erreur')
dfp = r['dataframe']
produites = set(dfp.columns)
reelles = sorted(c for c in produites if c.startswith('region_'))
print(f"  le plan ANNONCE : {sorted(c for c in attendues if c.startswith('region_'))}")
print(f"  A2 PRODUIT      : {reelles}")
manq = sorted(attendues - produites)
trop = sorted(set(reelles) - attendues)
print(f"  {'[CONSTAT]' if manq else '[BON    ]'} annoncees NON produites : {manq}")
print(f"  {'[CONSTAT]' if trop else '[BON    ]'} produites NON annoncees : {trop}")
print()
print(f"  ce que A2 rapporte comme manquantes : {r.get('colonnes_plan_manquantes')}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M6b -- LA TROISIEME FORME DE DICT : CELLE QUE A2 PRODUIT REELLEMENT")
# ══════════════════════════════════════════════════════════════════════════════
# Un plan dont un facteur source est ABSENT du fichier -> A2 doit le rapporter.
p2 = PlanTarifaire(
    lob='ampute', exposition='expo', cible_frequence='nb', cible_cout='cout',
    facteurs=(Facteur('age', 'continu'),
              Facteur('bonus_malus', 'continu'),
              Facteur('facteur_absent_du_fichier', 'continu')),
)
r2 = AgentA2Preprocessing().run(
    {'dataframe': df.drop(columns=['region']).assign(
        bonus_malus=rng.uniform(50, 350, n)),
     'branche': 'auto', 'success': True},
    cible_frequence='nb', cible_cout='cout', plan=p2)
rap = r2.get('colonnes_plan_manquantes')
print(f"  A2 -> colonnes_plan_manquantes = {rap}")
print(f"  cles                           = {sorted(rap) if isinstance(rap, dict) else type(rap).__name__}")
s = synthese_colonnes_plan_manquantes(rap)
etat = '[BON    ]' if s else '[CONSTAT]'
print(f"  {etat} synthese_colonnes_plan_manquantes(ce dict) -> ", end='')
print((s[:88] + '...') if s else 'None  <-- rien ne sera affiche')


# ══════════════════════════════════════════════════════════════════════════════
titre("M9 -- LE PLAN ACCEPTE LA CIBLE COMME FACTEUR. QUI L'ARRETE ENSUITE ?")
# ══════════════════════════════════════════════════════════════════════════════
print("  M3 a montre que le plan accepte `Facteur('nb','continu')` alors que")
print("  `cible_frequence='nb'`. Les trois garde-fous suivants la voient-ils ?")
print()
for nom in ('nb', 'cout', 'nb_sinistres', 'cout_total_sinistres', 'prime_pure'):
    print(f"    {nom:22s} genre={C._est_variable_genre(nom)!s:5s} "
          f"sinistralite={C._est_derivee_sinistralite(nom)!s:5s} "
          f"liste_blanche={C.est_facteur_autorise(nom)}")
print()
pc = PlanTarifaire(
    lob='cible', exposition='expo', cible_frequence='nb', cible_cout='cout',
    facteurs=(Facteur('age', 'continu'), Facteur('nb', 'continu')),
)
dfc = pd.DataFrame({
    'expo': rng.uniform(0.3, 1.0, n), 'age': rng.uniform(18, 80, n),
    'nb': rng.poisson(2.0, n).astype(float),
    'cout': rng.gamma(2, 300, n),
})
mx = C.construire_matrice_x(list(pc.colonnes_produites()), contexte='M9',
                            df=dfc, col_cible='nb', plan=pc)
dans = 'nb' in list(mx)
print(f"  plan declare : {pc.colonnes_produites()}   cible = 'nb'")
print(f"  {'[CONSTAT]' if dans else '[BON    ]'} matrice X = {list(mx)}")
print(f"            exclusions = {dict(mx.exclusions)}")
print(f"            alertes    = {dict(mx.alertes)}")
print()
print("  Pourquoi : `exemptees` (l.1123-1125 de conformite) contient col_cible")
print("  elle-meme. La colonne portant le NOM de la cible est donc sautee par le")
print("  garde-fou n.4 -- l'exemption la protege au lieu de la denoncer.")


# ══════════════════════════════════════════════════════════════════════════════
titre("M10 -- UN TYPE MAL ORTHOGRAPHIE : L'AMPUTATION EST-ELLE DETECTABLE ?")
# ══════════════════════════════════════════════════════════════════════════════
from core.plan_tarifaire import verifier_completude_plan
pt = PlanTarifaire(
    lob='typo', exposition='expo', cible_frequence='nb', cible_cout='cout',
    facteurs=(Facteur('age', 'continu'),
              Facteur('bonus_malus', 'ordinal')),   # <-- type inexistant
)
print(f"  plan avec un facteur de type 'ordinal' (inexistant) :")
print(f"    colonnes_produites()  = {pt.colonnes_produites()}")
rap = verifier_completude_plan(pt, ['age', 'bonus_malus'])
print(f"    verifier_completude_plan -> ampute={rap['ampute']}  "
      f"n_attendues={rap['n_attendues']}  manquantes={rap['colonnes_manquantes']}")
print()
print("  `bonus_malus` est DANS les donnees, DECLARE au plan, et n'atteint")
print("  aucun modele. Le detecteur d'amputation ne le voit pas : il compare")
print("  colonnes_produites() aux donnees, et colonnes_produites() ne le")
print("  contient pas.")
