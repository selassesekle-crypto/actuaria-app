# ruff: noqa
"""QU'EST-CE QUI TARIFE, ET QU'EST-CE QUI A ETE AUDITE ?

Deux vagues ont couvert 23 033 lignes. Le module en fait combien ?
Et surtout : QUEL CHEMIN TOURNE DEVANT UN ACTUAIRE ?
"""
import ast
import io
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

RACINE = r'C:\Users\selse\actuaria-app'

AUDITES = {
    # vague 1
    'direction_non_vie/tarification/a1_ingestion/agent.py',
    'direction_non_vie/tarification/a2_preprocessing/agent.py',
    'direction_non_vie/tarification/a3_glm/agent.py',
    'direction_non_vie/tarification/a4_ml/agent.py',
    'direction_non_vie/tarification/a5_deep_learning/agent.py',
    'direction_non_vie/tarification/a6_comparaison/agent.py',
    'direction_non_vie/tarification/services/rapport_equipe_tarif.py',
    'direction_non_vie/tarification/services/rapport_modeles_tarif.py',
    'direction_non_vie/tarification/services/tarif_excel.py',
    # vague 2
    'direction_non_vie/tarification/pipeline_tarifaire.py',
    'direction_non_vie/tarification/pipeline_agents.py',
    'core/conformite_reglementaire.py', 'core/plan_tarifaire.py',
    'core/charts_tarif.py', 'core/qualite_donnees.py', 'core/severite.py',
    'core/mapping_client.py', 'core/mapping_llm.py', 'core/derivations.py',
}


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


def lignes(p):
    try:
        return len(io.open(os.path.join(RACINE, p), encoding='utf-8').read().split('\n'))
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
titre("P1 -- LE PERIMETRE : QU'EST-CE QUI TARIFE ?")
# ══════════════════════════════════════════════════════════════════════════════
# Tout module NON-TEST atteint depuis pipeline_tarifaire, pipeline_agents,
# ou l'app -- mesure par AST du graphe d'imports.
def imports_de(p):
    try:
        a = ast.parse(io.open(os.path.join(RACINE, p), encoding='utf-8').read())
    except Exception:
        return set()
    out = set()
    for n in ast.walk(a):
        mods = []
        if isinstance(n, ast.ImportFrom) and n.module:
            mods = [n.module]
        elif isinstance(n, ast.Import):
            mods = [x.name for x in n.names]
        for m in mods:
            c = m.replace('.', '/') + '.py'
            if os.path.isfile(os.path.join(RACINE, c)):
                out.add(c)
            c2 = m.replace('.', '/') + '/__init__.py'
            if os.path.isfile(os.path.join(RACINE, c2)):
                out.add(c2)
    return out


RACINES = ['direction_non_vie/tarification/pipeline_tarifaire.py',
           'direction_non_vie/tarification/pipeline_agents.py']
vus, pile = set(), list(RACINES)
while pile:
    p = pile.pop()
    if p in vus:
        continue
    vus.add(p)
    for q in imports_de(p):
        if q not in vus and 'test' not in q.split('/')[-1]:
            pile.append(q)
tarif = sorted(p for p in vus if 'test' not in p.split('/')[-1])
tot = sum(lignes(p) for p in tarif)
aud = sorted(p for p in tarif if p in AUDITES)
non = sorted(p for p in tarif if p not in AUDITES)
print(f"  {len(tarif)} modules atteints depuis les deux pipelines · "
      f"{tot:,} lignes")
print(f"  AUDITES     : {len(aud):2d} modules · {sum(lignes(p) for p in aud):,} l")
print(f"  NON AUDITES : {len(non):2d} modules · {sum(lignes(p) for p in non):,} l")
for p in sorted(non, key=lambda x: -lignes(x)):
    print(f"      {lignes(p):5d} l  {p}")


# ══════════════════════════════════════════════════════════════════════════════
titre("P2 -- LE TROISIEME CHEMIN : CE QUE L'APPLICATION FAIT VRAIMENT")
# ══════════════════════════════════════════════════════════════════════════════
app = io.open(os.path.join(RACINE, 'actuaria_app.py'), encoding='utf-8').read()
a = ast.parse(app)
AGENTS = {'AgentA1Ingestion','AgentA2Preprocessing','AgentA3GLM','AgentA4ML',
          'AgentA5DeepLearning','AgentA6Comparaison'}
appels = []
for n in ast.walk(a):
    if isinstance(n, ast.Call):
        nom = (n.func.id if isinstance(n.func, ast.Name)
               else n.func.attr if isinstance(n.func, ast.Attribute) else None)
        if nom in AGENTS or nom in ('pipeline_complet', 'pipeline_agents',
                                    'controler_qualite', 'construire_matrice_x',
                                    'preparer_fichier_client'):
            appels.append((n.lineno, nom))
print(f"  actuaria_app.py : {len(app.split(chr(10))):,} lignes")
print(f"  instanciations / appels de la chaine de tarification :")
for L, nom in sorted(appels):
    print(f"      l.{L:<6d} {nom}")
print()
for nom in ('pipeline_complet', 'pipeline_agents', 'controler_qualite',
            'preparer_fichier_client', 'tarifer'):
    n = sum(1 for _, x in appels if x == nom) if nom != 'tarifer' else app.count('.tarifer(')
    etat = '[CONSTAT]' if n == 0 else '        '
    print(f"  {etat} l'app appelle {nom:24s} : {n} fois")


# ══════════════════════════════════════════════════════════════════════════════
titre("P3 -- LES TROIS CHEMINS, COTE A COTE")
# ══════════════════════════════════════════════════════════════════════════════
def a_t_il(p, sym):
    try:
        s = io.open(os.path.join(RACINE, p), encoding='utf-8').read()
    except Exception:
        return False
    return sym in s

CHEMINS = {
  'declaratif (pipeline_complet)': 'direction_non_vie/tarification/pipeline_tarifaire.py',
  'agent (pipeline_agents)':       'direction_non_vie/tarification/pipeline_agents.py',
  'application (actuaria_app)':    'actuaria_app.py',
}
PROPS = [('couche qualite', 'controler_qualite'),
         ('conformite declarative', 'construire_matrice_x'),
         ('severite source unique', 'construire_cible_severite'),
         ('mapping client', 'preparer_fichier_client'),
         ('empreinte du plan', 'empreinte()'),
         ('ML (A4)', 'AgentA4ML'),
         ('DL (A5)', 'AgentA5DeepLearning'),
         ('arbitrage (A6)', 'AgentA6Comparaison')]
print(f"    {'propriete':26s} " + " ".join(f"{k[:20]:>22s}" for k in CHEMINS))
for lib, sym in PROPS:
    cells = []
    for k, p in CHEMINS.items():
        cells.append('oui' if a_t_il(p, sym) else '---')
    print(f"    {lib:26s} " + " ".join(f"{c:>22s}" for c in cells))
print()
print("  ⚠ Le chemin qui tourne DEVANT UN ACTUAIRE est la 3e colonne.")
