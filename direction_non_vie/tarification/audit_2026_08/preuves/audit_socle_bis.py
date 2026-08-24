# ruff: noqa
"""RELEVE du SOCLE core -- LE CAVIARDAGE, LE SEUIL, ET DEUX DOCSTRINGS.

AUCUN APPEL A L'API : le caviardage se mesure localement, le reste par AST.
"""
import ast
import inspect
import io
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

import core.mapping_llm as ML
import core.severite as S
from core.plan_tarifaire import PlanTarifaire

RACINE = r'C:\Users\selse\actuaria-app'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


# ══════════════════════════════════════════════════════════════════════════════
titre("G4 -- « JAMAIS LES VALEURS » : LE CAVIARDAGE TIENT-IL ?")
# ══════════════════════════════════════════════════════════════════════════════
# Des valeurs UNIQUES et reconnaissables : si l'une sort, on la verra.
SECRETS = ['MARTIN-DUPONT-71431', 'IBAN-FR7630001007941234567890185',
           '0612345678', 'martin.dupont@exemple.fr', '971828182845904523536']
df = pd.DataFrame({
    'nom_assure':   SECRETS[:1] * 4,
    'iban':         SECRETS[1:2] * 4,
    'telephone':    SECRETS[2:3] * 4,
    'courriel':     SECRETS[3:4] * 4,
    'prime_exacte': [971828182845904523536.0] * 4,
    'BM':           [50.0, 100.0, 150.0, 200.0],
    'date_effet':   pd.to_datetime(['2026-01-01'] * 4),
})
apercu = ML.apercu_caviarde.apercu(df)
print("  Apercu transmis au modele :")
for L in apercu.split('\n')[:22]:
    print(f"      {L[:92]}")
print()
fuites = [s for s in SECRETS if s in apercu]
print(f"  {'[CONSTAT]' if fuites else '[BON    ]'} valeurs uniques retrouvees "
      f"dans l'apercu : {fuites or 'AUCUNE'}")
# et les valeurs numeriques exactes ?
for v in ('50.0', '971828182845904523536', '2026-01-01'):
    present = v in apercu
    print(f"      {v:26s} present : {present}")
print()
print("  Le prompt complet contient-il autre chose que l'apercu ?")
PLAN = PlanTarifaire.depuis_yaml(os.path.join(RACINE, 'plans', 'auto.yaml'))
prompt = ML._prompt_utilisateur(df, PLAN, 5)
fuites2 = [s for s in SECRETS if s in prompt]
print(f"  {'[CONSTAT]' if fuites2 else '[BON    ]'} valeurs uniques dans le "
      f"PROMPT ENTIER : {fuites2 or 'AUCUNE'}")
print(f"  longueur du prompt : {len(prompt)} caracteres")


# ══════════════════════════════════════════════════════════════════════════════
titre("G5 -- LA DOCSTRING DE `proposer_mapping` ET LE CODE")
# ══════════════════════════════════════════════════════════════════════════════
doc = inspect.getdoc(ML.proposer_mapping)
sig = inspect.signature(ML.proposer_mapping)
print(f"  _TEMPERATURE_DEFAUT (l.51) = {ML._TEMPERATURE_DEFAUT!r}")
print(f"  defaut du parametre        = {sig.parameters['temperature'].default!r}")
dit_zero = 'empérature 0' in doc or 'emperature 0' in doc
print(f"  {'[CONSTAT]' if dit_zero else '[BON    ]'} la docstring dit "
      f"« Température 0 pour la reproductibilité » : {dit_zero}")
print(f"  le commentaire l.45-49 dit : « TEMPERATURE RETIREE -- MESURE CONTRE")
print(f"  L'API le 2026-08-07 : ce modele REFUSE le parametre »")
print()
print(f"  `n_lignes_exemple` : defaut = "
      f"{sig.parameters['n_lignes_exemple'].default}")
src_pu = inspect.getsource(ML._prompt_utilisateur)
supprime = 'del n_lignes_exemple' in src_pu
print(f"  {'[CONSTAT]' if supprime else '[BON    ]'} il est supprime des la "
      f"1re ligne (`del`, « conserve pour l'API, sans effet ») : {supprime}")
print(f"  la docstring publique le mentionne-t-elle ? "
      f"{'n_lignes_exemple' in doc}")
print()
print(f"  la docstring dit « Claude Sonnet lit... » ; le modele reel est :")
print(f"      frontiere_llm.MODELE_RECENT = {ML.frontiere_llm.MODELE_RECENT!r}")
print(f"      _MODELE_CLAUDE              = {ML._MODELE_CLAUDE!r}")


# ══════════════════════════════════════════════════════════════════════════════
titre("G6 -- `anthropic` EST-IL IMPORTE AU CHARGEMENT ?")
# ══════════════════════════════════════════════════════════════════════════════
src = io.open(os.path.join(RACINE, 'core/mapping_llm.py'), encoding='utf-8').read()
arbre = ast.parse(src)
imports_haut = [n for n in arbre.body if isinstance(n, (ast.Import, ast.ImportFrom))]
noms = []
for n in imports_haut:
    if isinstance(n, ast.Import):
        noms += [a.name for a in n.names]
    else:
        noms.append(n.module or '')
print(f"  imports de MODULE : {sorted(set(noms))}")
print(f"  {'[CONSTAT]' if any('anthropic' in x for x in noms) else '[BON    ]'} "
      f"`anthropic` absent des imports de module")
print(f"  'anthropic' apparait dans le fichier : "
      f"{src.count('anthropic')} fois (dont commentaires)")
# et la degradation propre ?
try:
    ML.proposer_mapping(pd.DataFrame(), PLAN)
    print("  [CONSTAT] df vide : aucune exception")
except ML.MappingLLMIndisponible as e:
    print(f"  [BON    ] df vide -> MappingLLMIndisponible : {str(e)[:56]}")
for lib, brut in (("texte sans JSON", "je ne sais pas"),
                  ("JSON non parsable", "{ceci n'est pas du json}"),
                  ("JSON qui n'est pas un objet", "[1, 2, 3]"),
                  ("objet vide", "{}")):
    try:
        r = ML._parser_correspondances(brut)
        print(f"  {'[BON    ]' if r == {} else '[CONSTAT]'} {lib:28s} -> {r}")
    except ML.MappingLLMIndisponible as e:
        print(f"  [BON    ] {lib:28s} -> MappingLLMIndisponible : {str(e)[:34]}")


# ══════════════════════════════════════════════════════════════════════════════
titre("G7 -- LE SEUIL D'ECRETEMENT : CONTRAT OU SINISTRE ?")
# ══════════════════════════════════════════════════════════════════════════════
# Un portefeuille FLOTTE : beaucoup de sinistres MODESTES par contrat.
rng = np.random.default_rng(3)
k = 4000
expo = np.ones(k)
nb = rng.poisson(4.0, k).astype(float)          # flotte : 4 sinistres/an
cout_unitaire = 800.0
cout = nb * cout_unitaire                        # chaque sinistre vaut 800 EUR
c = S.construire_cible_severite(pd.Series(cout), pd.Series(nb), pd.Series(expo))
print(f"  flotte : {nb.mean():.2f} sinistres/contrat, CHAQUE sinistre = "
      f"{cout_unitaire:,.0f} EUR")
print(f"  seuil d'ecretement (q0,995 du cout TOTAL par contrat) = "
      f"{c.seuil_ecretement:,.0f} EUR")
print(f"  soit {c.seuil_ecretement / cout_unitaire:.1f} sinistres — "
      f"aucun sinistre n'est grave, ils sont tous a 800 EUR")
print(f"  n_graves = {c.n_graves} contrats ecretes")
touches = int((cout > c.seuil_ecretement).sum())
print(f"  contrats dont le TOTAL depasse le seuil : {touches}")
if touches:
    j = int(np.flatnonzero(cout > c.seuil_ecretement)[0])
    idx = np.flatnonzero(c.masque)
    pos = int(np.searchsorted(idx, j))
    print(f"    ex. nb={nb[j]:.0f}  cout total={cout[j]:,.0f}  "
          f"cout PAR SINISTRE reel = {cout_unitaire:,.0f}")
    print(f"        severite RETENUE = {c.severite[pos]:,.2f}  "
          f"(= seuil/{nb[j]:.0f})")
    print(f"    [CONSTAT] un contrat NOMBREUX est ecrete comme s'il etait GRAVE")
print(f"  charge reinjectee en prime_grave_unitaire = "
      f"{c.prime_grave_unitaire:,.2f} EUR/unite d'exposition")


# ══════════════════════════════════════════════════════════════════════════════
titre("G8 -- LA PROPAGATION DU SOCLE (AST)")
# ══════════════════════════════════════════════════════════════════════════════
fichiers = []
for base, dirs, noms_ in os.walk(RACINE):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv',
                                            'venv', '.pytest_cache', 'audit',
                                            'node_modules', 'htmlcov')]
    for nm in noms_:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))
SYMB = ['sources_brutes', 'DERIVATIONS', 'construire_cible_severite',
        'CibleSeverite', 'preparer_fichier_client', 'appliquer_mapping',
        'valider_mapping', 'charger_mapping', 'synthese_mapping',
        'proposer_mapping', 'MappingIncoherent', 'MappingLLMIndisponible']
MOI = {'core/derivations.py', 'core/severite.py', 'core/mapping_client.py',
       'core/mapping_llm.py'}
for s in SYMB:
    prod, tst = [], []
    for p in fichiers:
        rel = os.path.relpath(p, RACINE).replace('\\', '/')
        if rel in MOI or '/preuves/' in rel:
            continue
        try:
            a = ast.parse(io.open(p, encoding='utf-8').read())
        except (SyntaxError, UnicodeDecodeError):
            continue
        vu = any((isinstance(n, ast.Name) and n.id == s)
                 or (isinstance(n, ast.Attribute) and n.attr == s)
                 or (isinstance(n, ast.ImportFrom) and any(x.name == s for x in n.names))
                 for n in ast.walk(a))
        if vu:
            (tst if 'test' in rel.split('/')[-1] else prod).append(rel)
    etat = '[CONSTAT]' if not prod else '        '
    print(f"  {etat} {s:28s} production={len(prod):2d}  tests={len(tst):2d}")
    for x in sorted(prod):
        print(f"                {x}")


# ══════════════════════════════════════════════════════════════════════════════
titre("G9 -- A3 : `_calibrer_gamma` UTILISE-T-IL LA SOURCE UNIQUE ?")
# ══════════════════════════════════════════════════════════════════════════════
a3 = io.open(os.path.join(RACINE, 'direction_non_vie/tarification/a3_glm/agent.py'),
             encoding='utf-8').read()
arbre3 = ast.parse(a3)
for n in ast.walk(arbre3):
    if isinstance(n, ast.FunctionDef) and n.name == '_calibrer_gamma':
        corps = [c for c in ast.walk(n) if isinstance(c, ast.Call)]
        noms3 = {c.func.id if isinstance(c.func, ast.Name)
                 else c.func.attr if isinstance(c.func, ast.Attribute) else None
                 for c in corps}
        utilise = 'construire_cible_severite' in noms3
        print(f"  _calibrer_gamma l.{n.lineno} : appelle "
              f"construire_cible_severite = {utilise}")
        recalculs = sorted(x for x in noms3
                           if x in ('quantile', 'clip', 'where', 'mask'))
        print(f"  {'[BON    ]' if utilise else '[CONSTAT]'} "
              f"operations de masque/ecretement sur place : {recalculs or 'aucune'}")
