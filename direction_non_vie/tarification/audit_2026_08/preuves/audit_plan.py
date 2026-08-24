# ruff: noqa
"""RELEVE core/plan_tarifaire.py -- LA SOURCE UNIQUE.

Elle annonce remplacer QUATRE listes, rendre la desynchronisation IMPOSSIBLE
PAR CONSTRUCTION, et rendre la fuite B9 INEXPRIMABLE des la declaration.
On plante les violations.
"""
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

from core.plan_tarifaire import (
    Comportement, Facteur, PlanTarifaire, alerte_modele_ampute,
    plafonner_statut_si_ampute, synthese_colonnes_plan_manquantes,
    verifier_completude_plan,
)

RACINE = r'C:\Users\selse\actuaria-app'
PLANS = os.path.join(RACINE, 'plans')


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


def plan_minimal(**kw):
    base = dict(lob='test', exposition='expo', cible_frequence='nb',
                cible_cout='cout', facteurs=(Facteur('age', 'continu'),))
    base.update(kw)
    return PlanTarifaire(**base)


# ══════════════════════════════════════════════════════════════════════════════
titre("M1 -- LES 20 PLANS DU DEPOT SE CHARGENT-ILS ?")
# ══════════════════════════════════════════════════════════════════════════════
charges, echecs = {}, {}
for nm in sorted(os.listdir(PLANS)):
    if not nm.endswith(('.yaml', '.yml')):
        continue
    try:
        charges[nm] = PlanTarifaire.depuis_yaml(os.path.join(PLANS, nm))
    except Exception as e:
        echecs[nm] = f"{type(e).__name__}: {e}"
print(f"  {len(charges)} plan(s) charges, {len(echecs)} en echec")
for nm, e in echecs.items():
    print(f"  [CONSTAT] {nm} : {e[:66]}")
avec_comp = [n for n, p in charges.items() if p.comportement]
avec_id = [n for n, p in charges.items() if p.identifiant_contrat]
avec_ech = [n for n, p in charges.items() if p.echeance]
avec_ant = [n for n, p in charges.items() if p.facteurs_anteriorite()]
print(f"  bloc `comportement`  : {len(avec_comp)}/{len(charges)}  {avec_comp}")
print(f"  identifiant_contrat  : {len(avec_id)}/{len(charges)}")
print(f"  echeance             : {len(avec_ech)}/{len(charges)}")
print(f"  facteurs anteriorite : {len(avec_ant)}/{len(charges)}  {avec_ant}")
print(f"  familles de severite : "
      f"{sorted(set(p.famille_severite for p in charges.values()))}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M2 -- LES VALIDATIONS DE `Facteur` : CE QU'ELLES ATTRAPENT, ET CE QU'ELLES LAISSENT")
# ══════════════════════════════════════════════════════════════════════════════
CAS = [
    ("categoriel sans encodage", dict(nom='x', type='categoriel')),
    ("continu avec encodage", dict(nom='x', type='continu', encodage='label')),
    ("one_hot sans modalites", dict(nom='x', type='categoriel', encodage='one_hot')),
    ("type INCONNU 'ordinal'", dict(nom='x', type='ordinal')),
    ("encodage INCONNU 'onehot'", dict(nom='x', type='categoriel', encodage='onehot')),
    ("binaire + one_hot + modalites",
     dict(nom='x', type='binaire', encodage='one_hot', modalites=('a', 'b'))),
    ("temoin : continu simple", dict(nom='x', type='continu')),
]
for lib, kw in CAS:
    try:
        f = Facteur(**kw)
        cols = f.colonnes_produites()
        etat = '[CONSTAT]' if not cols else '        '
        print(f"  {etat} {lib:32s} ACCEPTE -> colonnes_produites() = {cols}")
    except ValueError as e:
        print(f"           {lib:32s} refuse : {str(e)[:44]}...")


# ══════════════════════════════════════════════════════════════════════════════
titre("M3 -- LA GARDE B9 : L'EXPOSITION EST-ELLE VRAIMENT INEXPRIMABLE ?")
# ══════════════════════════════════════════════════════════════════════════════
TENTATIVES = [
    ("facteur nomme 'exposition'",
     dict(facteurs=(Facteur('exposition', 'continu'),))),
    ("facteur nomme comme self.exposition ('expo')",
     dict(facteurs=(Facteur('expo', 'continu'),))),
    ("'expo' avec transformation log",
     dict(facteurs=(Facteur('expo', 'continu', transformation='log'),))),
    ("INTERACTION age x expo",
     dict(facteurs=(Facteur('age', 'continu'),),
          interactions=(('age', 'expo'),))),
    ("'expo' en one_hot",
     dict(facteurs=(Facteur('expo', 'categoriel', encodage='one_hot',
                            modalites=('court', 'long')),))),
    ("la CIBLE de frequence declaree en facteur",
     dict(facteurs=(Facteur('nb', 'continu'),))),
    ("la CIBLE de cout declaree en facteur",
     dict(facteurs=(Facteur('cout', 'continu'),))),
]
for lib, kw in TENTATIVES:
    try:
        p = plan_minimal(**kw)
        print(f"  [CONSTAT] {lib:44s} ACCEPTE -> {p.colonnes_produites()}")
    except ValueError as e:
        print(f"           {lib:44s} refuse")


# ══════════════════════════════════════════════════════════════════════════════
titre("M4 -- `_slug` EST-IL VRAIMENT CE QUE A2 APPLIQUE ? (« c'est le contrat »)")
# ══════════════════════════════════════════════════════════════════════════════
import numpy as np
import pandas as pd
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing

MODALITES = ('Île-de-France', 'Provence-Alpes-Côte d\'Azur', 'Hauts de France',
             'Nouvelle-Aquitaine', 'RHÔNE')
p = PlanTarifaire(
    lob='slug', exposition='expo', cible_frequence='nb', cible_cout='cout',
    facteurs=(Facteur('age', 'continu'),
              Facteur('region', 'categoriel', encodage='one_hot',
                      modalites=MODALITES, reference='Hauts de France')),
)
attendues = set(p.colonnes_produites())
print(f"  le plan annonce : {sorted(attendues)}")
rng = np.random.default_rng(5)
n = 400
df = pd.DataFrame({
    'expo': rng.uniform(0.3, 1.0, n),
    'nb': rng.poisson(0.1, n).astype(float),
    'cout': rng.gamma(2, 300, n),
    'age': rng.uniform(18, 80, n),
    'region': rng.choice(list(MODALITES), n),
})
try:
    a2 = AgentA2Preprocessing()
    r = a2.run(df.copy(), plan=p)
    dfp = r.get('df') if isinstance(r, dict) else None
    if dfp is None:
        for k in ('data', 'df_preprocesse', 'dataframe'):
            if isinstance(r, dict) and k in r:
                dfp = r[k]
    produites = set(c for c in (dfp.columns if dfp is not None else []))
    reelles = {c for c in produites if c.startswith('region_')}
    print(f"  A2 a produit  : {sorted(reelles)}")
    manquantes = sorted(attendues - produites)
    en_trop = sorted(reelles - attendues)
    print(f"  {'[CONSTAT]' if manquantes else '[BON    ]'} annoncees et NON "
          f"produites : {manquantes}")
    print(f"  {'[CONSTAT]' if en_trop else '[BON    ]'} produites et NON "
          f"annoncees : {en_trop}")
except Exception as e:
    print(f"  A2 : {type(e).__name__} : {str(e)[:70]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M5 -- `valider_contre` SUR UN FACTEUR DERIVE")
# ══════════════════════════════════════════════════════════════════════════════
auto = charges.get('auto.yaml')
if auto:
    src = set(auto.colonnes_sources())
    att = set(auto.colonnes_attendues())
    derives = sorted(src - att)
    print(f"  plan auto : {len(src)} colonnes_sources, {len(att)} colonnes_attendues")
    print(f"  facteurs DERIVES (dans sources, absents d'attendues) : {derives}")
    if derives:
        # un fichier client PARFAIT : il porte exactement colonnes_attendues()
        manquants = auto.valider_contre(sorted(att))
        etat = '[CONSTAT]' if manquants else '[BON    ]'
        print(f"  {etat} un fichier portant EXACTEMENT colonnes_attendues() est "
              f"juge incomplet :")
        print(f"            manquants = {manquants}")
    else:
        print("  aucun facteur derive dans ce plan -- mesure sur un plan construit :")
        pd2 = PlanTarifaire(
            lob='d', exposition='expo', cible_frequence='nb', cible_cout='cout',
            facteurs=(Facteur('km_par_an_normalise', 'continu'),))
        att2 = sorted(pd2.colonnes_attendues())
        print(f"            colonnes_attendues = {att2}")
        print(f"            valider_contre(attendues) = {pd2.valider_contre(att2)}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M6 -- DEUX FONCTIONS 'PLAN AMPUTE', DEUX FORMES DE DICT")
# ══════════════════════════════════════════════════════════════════════════════
pl = plan_minimal(facteurs=(Facteur('age', 'continu'),
                            Facteur('bonus_malus', 'continu')))
rapport = verifier_completude_plan(pl, ['age'])       # bonus_malus manquant
print(f"  verifier_completude_plan -> {rapport}")
print(f"  plafonner_statut_si_ampute('VERT')  = "
      f"{plafonner_statut_si_ampute('VERT', rapport)}")
print(f"  plafonner_statut_si_ampute('AMBRE') = "
      f"{plafonner_statut_si_ampute('AMBRE', rapport)}")
print(f"  plafonner_statut_si_ampute('ROUGE') = "
      f"{plafonner_statut_si_ampute('ROUGE', rapport)}")
a = alerte_modele_ampute(rapport, 'GLM')
print(f"  alerte_modele_ampute -> severite={a['severite']} code={a['code']}")
s = synthese_colonnes_plan_manquantes(rapport)
etat = '[CONSTAT]' if s is None else '        '
print(f"  {etat} synthese_colonnes_plan_manquantes(MEME rapport) -> {s!r}")
print()
print("  Les cles produites par verifier_completude_plan :")
print(f"     {sorted(rapport)}")
print("  Les cles lues par synthese_colonnes_plan_manquantes :")
print("     ['plan', 'colonnes_non_produites', 'facteurs_absents']")


# ══════════════════════════════════════════════════════════════════════════════
titre("M7 -- `depuis_dict` : QUE FAIT-IL D'UNE CLE MAL ORTHOGRAPHIEE ?")
# ══════════════════════════════════════════════════════════════════════════════
BASE = {'lob': 't', 'exposition': 'expo', 'cible_frequence': 'nb',
        'cible_cout': 'cout', 'facteurs': [{'nom': 'age', 'type': 'continu'}]}
CAS = [
    ("identifiant_contract (anglais)", {'identifiant_contract': 'id_pol'},
     'identifiant_contrat'),
    ("echeances (pluriel)", {'echeances': '2026-01-01'}, 'echeance'),
    ("famille_severity (anglais)", {'famille_severity': 'lognormal'},
     'famille_severite'),
    ("cle totalement inventee", {'nimporte_quoi': 42}, None),
    ("temoin : echeance correcte", {'echeance': 'date_ech'}, 'echeance'),
]
for lib, extra, champ in CAS:
    d = dict(BASE)
    d.update(extra)
    try:
        p = PlanTarifaire.depuis_dict(d)
        val = getattr(p, champ) if champ else '-'
        pris = (val is not None) if champ else False
        etat = '        ' if (pris or champ is None and False) else '[CONSTAT]'
        if lib.startswith('temoin'):
            etat = '[BON    ]' if pris else '[CONSTAT]'
        print(f"  {etat} {lib:32s} ACCEPTE en silence   {champ or '(aucun champ)'}"
              f" = {val!r}")
    except Exception as e:
        print(f"           {lib:32s} {type(e).__name__} : {str(e)[:38]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M8 -- L'EMPREINTE : DETERMINISTE ? SENSIBLE ? A QUOI EST-ELLE AVEUGLE ?")
# ══════════════════════════════════════════════════════════════════════════════
p0 = plan_minimal()
print(f"  deux appels sur le meme plan : "
      f"{'IDENTIQUES' if p0.empreinte() == p0.empreinte() else 'DIVERGENTS'}")
VARIANTES = [
    ("version",          plan_minimal(version='2.0')),
    ("auteur",           plan_minimal(auteur='X')),
    ("famille_severite", plan_minimal(famille_severite='lognormal')),
    ("identifiant_contrat", plan_minimal(identifiant_contrat='id')),
    ("echeance",         plan_minimal(echeance='d')),
    ("comportement",     plan_minimal(comportement=Comportement('i', 'a', 'b'))),
    ("anteriorite",      plan_minimal(
        facteurs=(Facteur('age', 'continu', anteriorite=True),))),
    ("interactions",     plan_minimal(
        facteurs=(Facteur('age', 'continu'), Facteur('bm', 'continu')),
        interactions=(('age', 'bm'),))),
    ("COMMENTAIRE",      plan_minimal(
        facteurs=(Facteur('age', 'continu', commentaire='tout autre'),))),
    ("ORDRE des facteurs", plan_minimal(
        facteurs=(Facteur('bm', 'continu'), Facteur('age', 'continu')))),
]
ref = p0.empreinte()
for lib, pv in VARIANTES:
    diff = pv.empreinte() != ref
    if lib in ('COMMENTAIRE',):
        etat = '[CONSTAT]' if not diff else '        '
    else:
        etat = '        ' if diff else '[CONSTAT]'
    print(f"  {etat} {lib:22s} change l'empreinte : {diff}")
print()
print("  Le schema de l'empreinte porte-t-il un NUMERO DE VERSION ?")
import inspect
src_emp = inspect.getsource(PlanTarifaire.empreinte)
cles = sorted(set(k.strip('"\'') for k in
                  __import__('re').findall(r'"(\w+)":', src_emp)))
print(f"     cles du payload : {cles}")
print(f"     {'[CONSTAT] AUCUNE cle de version de schema' if not any('schema' in c or c == 'schema_version' for c in cles) else '[BON]'}")
