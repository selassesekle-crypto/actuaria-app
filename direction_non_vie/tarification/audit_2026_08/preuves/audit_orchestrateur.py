# ruff: noqa
"""RELEVE pipeline_agents.py -- L'ORCHESTRATEUR.

Trois regles non negociables, trois cibles, un contrat de serialisation.
D'abord ce qui se mesure sans faire tourner la chaine.
"""
import ast
import inspect
import io
import json
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import direction_non_vie.tarification.pipeline_agents as PA

RACINE = r'C:\Users\selse\actuaria-app'
MOI = 'direction_non_vie/tarification/pipeline_agents.py'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


src = io.open(os.path.join(RACINE, MOI), encoding='utf-8').read()
arbre = ast.parse(src)
fn_pa = [n for n in ast.walk(arbre)
         if isinstance(n, ast.FunctionDef) and n.name == 'pipeline_agents'][0]

# ══════════════════════════════════════════════════════════════════════════════
titre("M1 -- LES TROIS REGLES NON NEGOCIABLES, PAR AST")
# ══════════════════════════════════════════════════════════════════════════════
# Regle 1 : le masque vient de construire_cible_severite, jamais recalcule ici.
appels = [n for n in ast.walk(arbre) if isinstance(n, ast.Call)]
noms = [n.func.id if isinstance(n.func, ast.Name)
        else n.func.attr if isinstance(n.func, ast.Attribute) else None
        for n in appels]
print(f"  R1 `construire_cible_severite` appelee : "
      f"{noms.count('construire_cible_severite')} fois")
recalculs = [m for m in ('duplicated', 'where', 'mask') if m in noms]
print(f"  {'[BON    ]' if noms.count('construire_cible_severite') == 1 else '[CONSTAT]'}"
      f" et aucun masque recalcule sur place : "
      f"{'aucun' if not recalculs else recalculs}")

# Regles 2 et 3 : les arguments passes a _arbitrer, par cible.
for nd in ast.walk(fn_pa):
    if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name) \
            and nd.func.id == '_arbitrer':
        cible = ast.unparse(nd.args[0]) if nd.args else '?'
        kw = {k.arg: ast.unparse(k.value) for k in nd.keywords}
        print(f"  cible {cible:26s} modeles_dl={kw.get('modeles_dl'):<22s} "
              f"ponderer={kw.get('ponderer')}")
print("  R2 : CANN exclu de la cible cout et de la prime pure  -> "
      f"{'BON' if '(\'tabnet\',)' in src else 'a verifier'}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M2 -- LE CONTRAT DE SERIALISATION : json.dumps NE LEVE JAMAIS ?")
# ══════════════════════════════════════════════════════════════════════════════
from core.plan_tarifaire import Facteur, PlanTarifaire
PLAN = PlanTarifaire(lob='orch', exposition='expo', cible_frequence='nb',
                     cible_cout='cout', facteurs=(Facteur('age', 'continu'),))


def _echec_complet():
    """Le pire cas : A3 echoue, les trois arbitrages sont des echecs."""
    ech = PA.ArbitrageCible(cible='x', a4=None, a5=None, a6=None,
                            statut_rag=None, n_candidats=0, erreur='A3 a echoue')
    return PA.ResultatAgents(
        plan=PLAN, a1={'success': False}, a2={}, a3={'success': False},
        frequence=ech, cout=ech, prime_pure=ech, audit_id='TEST')


r = _echec_complet()
try:
    s = json.dumps(r.resume())
    print(f"  [BON    ] resume() sur un ECHEC total : json.dumps OK "
          f"({len(s)} caracteres)")
except Exception as e:
    print(f"  [CONSTAT] json.dumps -> {type(e).__name__} : {str(e)[:60]}")
print(f"  success sur cet echec = {r.success}")

# Et avec des objets NON serialisables dans a6 ?
import numpy as np
import pandas as pd
a6_lourd = {
    'modele_production': {'modele': 'GLM Poisson'},
    'classement': [{'modele': 'GLM', 'famille': 'GLM', 'cible': 'nb',
                    'gini_test': np.float64(0.21),
                    'score_global': np.float32(0.8),
                    'objet_lourd': pd.DataFrame({'a': [1]})}],
    'exclusions_cible': [{'modele': 'X', 'cible_modele': 'y', 'raison': 'z'}],
    'alertes_modele': [{'code': 'plan_incomplet_modele_ampute'}],
    'dataframe': pd.DataFrame({'b': [1, 2]}),
}
arb = PA.ArbitrageCible(cible='nb', a4={'m': np.array([1, 2])}, a5=None,
                        a6=a6_lourd, statut_rag='VERT', n_candidats=1)
r2 = PA.ResultatAgents(plan=PLAN, a1={}, a2={}, a3={'success': True},
                       frequence=arb, cout=arb, prime_pure=arb, audit_id='T2')
try:
    s = json.dumps(r2.resume())
    print(f"  [BON    ] resume() avec DataFrame/np dans a6 : json.dumps OK "
          f"({len(s)} caracteres)")
except Exception as e:
    print(f"  [CONSTAT] json.dumps -> {type(e).__name__} : {str(e)[:60]}")
print(f"  success = {r2.success}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M3 -- `resume()` EST-IL REPRODUCTIBLE ?")
# ══════════════════════════════════════════════════════════════════════════════
a = r2.resume()
b = r2.resume()
diffs = sorted(k for k in a if a[k] != b[k])
print(f"  deux appels sur le MEME objet -> champs qui different : {diffs}")
print(f"      {[(k, a[k], b[k]) for k in diffs]}")
print()
print("  Les modules freres refusent explicitement de generer une date :")
print("    core/qualite_donnees.py  : « Ne genere aucun horodatage — reutilise")
print("                                celui fourni par l'appelant »")
print("    core/conformite_regl.py  : « aucune date n'est generee ici : on reutilise »")
print(f"    pipeline_agents.py l.157 : datetime.now().isoformat()")


# ══════════════════════════════════════════════════════════════════════════════
titre("M4 -- `.success` EST-IL VRAI QUAND A6 A ECHOUE ?")
# ══════════════════════════════════════════════════════════════════════════════
a6_rate = {'success': False, 'erreur': 'A6 a echoue', 'classement': []}
arb_rate = PA.ArbitrageCible(cible='nb', a4={}, a5=None, a6=a6_rate,
                             statut_rag=None, n_candidats=0)
r3 = PA.ResultatAgents(plan=PLAN, a1={}, a2={}, a3={'success': True},
                       frequence=arb_rate, cout=arb_rate, prime_pure=arb_rate,
                       audit_id='T3')
print(f"  a6 = {{'success': False, 'erreur': 'A6 a echoue', 'classement': []}}")
print(f"  {'[CONSTAT]' if r3.success else '[BON    ]'} "
      f"ResultatAgents.success = {r3.success}")
print(f"      statut_rag  = {r3.frequence.statut_rag}")
print(f"      n_candidats = {r3.frequence.n_candidats}")
print(f"  la propriete teste : `self.frequence.a6 is not None` (l.112)")
print(f"  resume()['success'] = {r3.resume()['success']}   "
      f"modele_production = {r3.resume()['frequence']['modele_production']}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M5 -- « UN ARBITRAGE QUI ECHOUE N'EMPECHE PAS LES AUTRES » ?")
# ══════════════════════════════════════════════════════════════════════════════
# Les trois cibles sont-elles enveloppees de la meme facon ?
enveloppes = {}
for nd in ast.walk(fn_pa):
    if isinstance(nd, ast.Try):
        for h in nd.body:
            for c in ast.walk(h):
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
                        and c.func.id in ('_arbitrer', '_vue_sinistres'):
                    enveloppes.setdefault(c.func.id, []).append(nd.lineno)
print(f"  appels ENVELOPPES dans un try : {enveloppes}")
lignes_arb = [nd.lineno for nd in ast.walk(fn_pa)
              if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Name)
              and nd.func.id == '_arbitrer']
print(f"  les trois appels a _arbitrer sont aux lignes {lignes_arb}")
for L in lignes_arb:
    dans_try = any(t.lineno <= L <= max(n.lineno for n in ast.walk(t)
                                        if hasattr(n, 'lineno'))
                   for t in ast.walk(fn_pa) if isinstance(t, ast.Try))
    etat = '        ' if dans_try else '[CONSTAT]'
    print(f"  {etat} _arbitrer l.{L:<4d} protege par un try : {dans_try}")
print()
print("  La docstring l.216-219 dit : « Un arbitrage peut echouer la ou un autre")
print("  reussit ... n'empeche pas les autres d'aboutir. »")


# ══════════════════════════════════════════════════════════════════════════════
titre("M6 -- ANNOTATIONS ET CHEMINS PAR DEFAUT")
# ══════════════════════════════════════════════════════════════════════════════
fn_vue = [n for n in ast.walk(arbre)
          if isinstance(n, ast.FunctionDef) and n.name == '_vue_sinistres'][0]
annot = ast.unparse(fn_vue.returns) if fn_vue.returns else '(aucune)'
ret = [ast.unparse(n.value) for n in ast.walk(fn_vue) if isinstance(n, ast.Return)]
print(f"  _vue_sinistres annonce  -> {annot}")
print(f"  _vue_sinistres retourne -> {ret}")
etat = '[CONSTAT]' if 'Dict' in annot and ret and ',' in ret[0] else '[BON    ]'
print(f"  {etat} l'annotation decrit-elle ce qui est rendu ?")
print()
sig = inspect.signature(PA.pipeline_agents)
for nom in ('models_path', 'audit_path'):
    d = sig.parameters[nom].default
    existe = os.path.isdir(d)
    print(f"  {'[CONSTAT]' if not existe else '[BON    ]'} {nom:12s} defaut = "
          f"{d!r}   existe sur cette machine : {existe}")
print(f"  plateforme : {sys.platform}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M7 -- QUI APPELLE L'ORCHESTRATEUR ? (AST)")
# ══════════════════════════════════════════════════════════════════════════════
fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv',
                                            'node_modules', 'venv',
                                            '.pytest_cache', 'htmlcov', 'audit')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))
for s in ('pipeline_agents', 'ResultatAgents', 'ArbitrageCible',
          'CIBLE_COUT', 'CIBLE_PRIME_PURE'):
    lieux = []
    for p in fichiers:
        rel = os.path.relpath(p, RACINE).replace('\\', '/')
        if rel == MOI or '/preuves/' in rel:
            continue
        try:
            a = ast.parse(io.open(p, encoding='utf-8').read())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nd in ast.walk(a):
            if (isinstance(nd, ast.Name) and nd.id == s) or \
               (isinstance(nd, ast.Attribute) and nd.attr == s) or \
               (isinstance(nd, ast.ImportFrom) and any(x.name == s for x in nd.names)):
                lieux.append(rel)
                break
    prod = sorted(set(x for x in lieux if 'test' not in x.split('/')[-1]))
    tst = sorted(set(x for x in lieux if 'test' in x.split('/')[-1]))
    etat = '[CONSTAT]' if not prod else '        '
    print(f"  {etat} {s:18s} production={len(prod)}  tests={len(tst)}   {prod}")

print()
print("  « pipeline_complet ne reference ni A4 ni A5 » :")
pc = io.open(os.path.join(RACINE,
                          'direction_non_vie/tarification/pipeline_tarifaire.py'),
             encoding='utf-8').read()
for m in ('AgentA4ML', 'AgentA5DeepLearning', 'a4_ml', 'a5_deep_learning'):
    print(f"    {m:22s} present dans pipeline_tarifaire.py : {m in pc}")
