# ruff: noqa
"""RELEVE core/conformite_reglementaire.py -- LA MARGE, LE MOTIF, LA PROPAGATION.

H2 m'a refute : 'effectif' plafonne a 0,784 sous un seuil de 0,80. Une marge de
0,016 ne se commente pas -- elle s'instruit.
Puis : le module se dit SOURCE UNIQUE et dit que TOUS les livrables l'appellent.
Mesure PAR AST, jamais par grep.
"""
import ast
import io
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

import core.conformite_reglementaire as C

RACINE = r'C:\Users\selse\actuaria-app'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


# ══════════════════════════════════════════════════════════════════════════════
titre("H2b -- OU EST LE POINT DE BASCULE DE LA VARIABLE DE TAILLE ?")
# ══════════════════════════════════════════════════════════════════════════════
print("  'effectif' est une CONNAISSANCE PARFAITE de lambda : aucun bruit sur x,")
print("  tout le bruit est du cote de la cible (Poisson). Son signal ne depend")
print("  donc que de la FREQUENCE. Le module cite lui-meme une flotte a 4,2")
print("  sinistres/an (l.1180). Mesure du signal en fonction de la frequence :")
print()


def _signal(x, y):
    tr = getattr(np, 'trapezoid', None) or np.trapz
    ya = np.asarray(y, float)

    def g(xa):
        o = np.argsort(-np.asarray(xa, float))
        yo = ya[o]
        t = yo.sum()
        if t <= 0:
            return 0.0
        return float(2.0 * tr(np.cumsum(yo) / t,
                              np.arange(1, len(yo) + 1) / len(yo)) - 1.0)
    gp = g(ya)
    gn = abs(g(x) / gp) if gp > 1e-9 else 0.0
    rho = abs(float(pd.Series(ya).rank().corr(pd.Series(np.asarray(x, float)).rank())))
    return rho, gn


print(f"    {'freq/an':>8s}  {'spearman':>9s}  {'gini_norm':>10s}   verdict "
      f"(seuil {C.SEUIL_CORRELATION_FUITE})")
bascule = None
for freq in (1.0, 2.0, 4.0, 6.0, 8.0, 12.0, 20.0, 40.0):
    rg = np.random.default_rng(101)
    eff = rg.integers(1, 400, 6000).astype(float)
    lam = freq * eff / eff.mean()
    y = rg.poisson(lam).astype(float)
    rho, gn = _signal(eff, y)
    depasse = max(rho, gn) >= C.SEUIL_CORRELATION_FUITE
    if depasse and bascule is None:
        bascule = freq
    print(f"    {freq:8.1f}  {rho:9.4f}  {gn:10.4f}   "
          f"{'ECARTEE -- « la cible deguisee »' if depasse else 'gardee'}")
print()
print(f"  -> bascule entre {C.SEUIL_CORRELATION_FUITE} atteinte a partir de "
      f"~{bascule} sinistre(s)/an/contrat.")
print("     'effectif' et 'nb_salaries' sont DECLARES facteurs legitimes (l.381)")
print("     et ne portent AUCUN marqueur de passe : rien ne les protege.")


# ══════════════════════════════════════════════════════════════════════════════
titre("H5b -- LE MOTIF D'UNE FUITE PAR L'EFFET, TEL QUE L'ACTUAIRE LE LIT")
# ══════════════════════════════════════════════════════════════════════════════
rng = np.random.default_rng(3)
n = 3000
expo = rng.uniform(0.2, 1.0, n)
nb = rng.poisson(0.12 * expo, n).astype(float)
df = pd.DataFrame({'age': rng.uniform(18, 80, n),
                   'bonus_malus': rng.uniform(50, 350, n),
                   'nb_sinistres': nb,
                   'zorglub': nb + rng.normal(0, 1e-6, n)})
mx = C.construire_matrice_x(['age', 'bonus_malus', 'zorglub'], contexte='H5b',
                            df=df, col_cible='nb_sinistres',
                            facteurs_supplementaires=['zorglub'])
for c, motif in mx.exclusions.items():
    print(f"  {c!r} :")
    for k in range(0, len(motif), 88):
        print(f"      {motif[k:k + 88]}")
print()
print("  Et dans le rapport (synthese_exclusions) :")
for L in (C.synthese_exclusions(mx.exclusions) or '').split('\n'):
    for k in range(0, len(L), 92):
        print(f"      {L[k:k + 92]}")
print()
print(f"  docstring de detecter_fuites_par_effet : "
      f"« Retourne {{colonne: correlation}} ... Spearman »")
f = C.detecter_fuites_par_effet(df, ['zorglub'], 'nb_sinistres')
print(f"  valeur reellement retournee            : {f}")
print(f"  critere reellement applique            : max(spearman, gini_normalise)")


# ══════════════════════════════════════════════════════════════════════════════
titre("P1 -- QUI IMPORTE CE MODULE ? (AST, jamais grep)")
# ══════════════════════════════════════════════════════════════════════════════
SYMBOLES = ['filtrer_genre', 'filtrer_famille_cible', 'filtrer_features',
            'selectionner_features_autorisees', 'construire_matrice_x',
            'detecter_fuites_par_effet', 'avertissement_walk_forward',
            'synthese_exclusions', 'synthese_alertes_experience',
            'synthese_modele_dl', 'gini_est_plausible', 'est_facteur_autorise',
            'MatriceX', 'EchecControleEffet']

fichiers = []
for base, dirs, noms in os.walk(RACINE):
    dirs[:] = [d for d in dirs
               if d not in ('.git', '__pycache__', '.venv', 'node_modules',
                            'venv', '.pytest_cache', 'htmlcov', 'audit')]
    for nm in noms:
        if nm.endswith('.py'):
            fichiers.append(os.path.join(base, nm))

importeurs = {}
appels = {s: [] for s in SYMBOLES}
attributs = {'controle_effet_execute': [], 'alertes': [], 'exclusions': []}
for chemin in fichiers:
    rel = os.path.relpath(chemin, RACINE).replace('\\', '/')
    try:
        arbre = ast.parse(io.open(chemin, encoding='utf-8').read())
    except (SyntaxError, UnicodeDecodeError):
        continue
    for nd in ast.walk(arbre):
        if isinstance(nd, ast.ImportFrom) and (nd.module or '').endswith(
                'conformite_reglementaire'):
            importeurs.setdefault(rel, []).extend(a.name for a in nd.names)
        elif isinstance(nd, ast.Import):
            for a in nd.names:
                if a.name.endswith('conformite_reglementaire'):
                    importeurs.setdefault(rel, []).append('<module>')
    for nd in ast.walk(arbre):
        if isinstance(nd, ast.Call):
            nom = (nd.func.id if isinstance(nd.func, ast.Name)
                   else nd.func.attr if isinstance(nd.func, ast.Attribute) else None)
            if nom in appels:
                appels[nom].append(rel)
        if isinstance(nd, ast.Attribute) and nd.attr in attributs:
            attributs[nd.attr].append(rel)

MOI = 'core/conformite_reglementaire.py'
print(f"  {len(fichiers)} fichiers .py analyses par AST.")
print(f"  {len(importeurs)} fichier(s) importent le module :")
for rel in sorted(importeurs):
    marque = 'TEST' if ('test' in rel.split('/')[-1]) else '    '
    print(f"    [{marque}] {rel}")

print()
print("  Par DIRECTION :")
for d in ('direction_non_vie/', 'direction_vie/', 'direction_sante',
          'direction_epargne', 'core/', 'services/'):
    k = [r for r in importeurs if r.startswith(d)]
    print(f"    {d:26s} {len(k)} importateur(s)")
autres = sorted(set(os.path.relpath(f, RACINE).replace('\\', '/').split('/')[0]
                    for f in fichiers))
print(f"  racines du depot : {autres}")


# ══════════════════════════════════════════════════════════════════════════════
titre("P2 -- « TOUS LES LIVRABLES L'APPELLENT » -- LESQUELS ?")
# ══════════════════════════════════════════════════════════════════════════════
for s in SYMBOLES:
    lieux = sorted(set(a for a in appels[s] if a != MOI))
    prod = [x for x in lieux if 'test' not in x.split('/')[-1]]
    tst = [x for x in lieux if 'test' in x.split('/')[-1]]
    etat = '        ' if prod else '[CONSTAT]'
    print(f"  {etat} {s:34s} production={len(prod):2d}  tests={len(tst):2d}")
    for x in prod:
        print(f"                {x}")

print()
print("  Lecture des trois canaux que le module dit indispensables :")
for att, lieux in attributs.items():
    lieux = sorted(set(x for x in lieux if x != MOI))
    prod = [x for x in lieux if 'test' not in x.split('/')[-1]]
    tst = [x for x in lieux if 'test' in x.split('/')[-1]]
    etat = '        ' if prod else '[CONSTAT]'
    print(f"  {etat} .{att:26s} production={len(prod):2d}  tests={len(tst):2d}"
          f"   {prod if prod else ''}")


# ══════════════════════════════════════════════════════════════════════════════
titre("P3 -- LE FILTRE EST-IL REIMPLEMENTE AILLEURS ? (l.7-8 : « jamais duplique »)")
# ══════════════════════════════════════════════════════════════════════════════
MOTS = ('sexe', 'genre', 'gender', 'civilite')
suspects = []
for chemin in fichiers:
    rel = os.path.relpath(chemin, RACINE).replace('\\', '/')
    if rel == MOI:
        continue
    try:
        arbre = ast.parse(io.open(chemin, encoding='utf-8').read())
    except (SyntaxError, UnicodeDecodeError):
        continue
    for nd in ast.walk(arbre):
        if isinstance(nd, (ast.List, ast.Tuple, ast.Set)):
            vals = [e.value.lower() for e in nd.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if sum(1 for v in vals if any(m in v for m in MOTS)) >= 2:
                suspects.append((rel, getattr(nd, 'lineno', '?'), vals[:6]))
print(f"  {len(suspects)} litteral(aux) de 2+ noms genres hors de ce module :")
for rel, ln, vals in suspects[:14]:
    marque = 'TEST' if 'test' in rel.split('/')[-1] else '⚠   '
    print(f"    [{marque}] {rel}:{ln}  {vals}")


# ══════════════════════════════════════════════════════════════════════════════
titre("P4 -- LES DERIVEES D'A2 SONT-ELLES ENCORE CELLES QUI SONT DECLAREES ?")
# ══════════════════════════════════════════════════════════════════════════════
DECLAREES_A2 = ['jeune_conducteur', 'senior_conducteur', 'vehicule_recent',
                'vehicule_ancien', 'logement_ancien', 'valeur_mobilier',
                'valeur_par_m2', 'km_par_an_normalise']
a2 = None
for chemin in fichiers:
    if chemin.replace('\\', '/').endswith('a2_preprocessing/agent.py'):
        a2 = chemin
if a2:
    src = io.open(a2, encoding='utf-8').read()
    arbre = ast.parse(src)
    produites = set()
    for nd in ast.walk(arbre):
        # df['x'] = ...  et  df.loc[:, 'x'] = ...
        if isinstance(nd, ast.Assign):
            for t in nd.targets:
                if (isinstance(t, ast.Subscript)
                        and isinstance(t.slice, ast.Constant)
                        and isinstance(t.slice.value, str)):
                    produites.add(t.slice.value)
    rel = os.path.relpath(a2, RACINE).replace('\\', '/')
    print(f"  {rel} : {len(produites)} colonnes affectees par df['...'] = ...")
    manquantes = sorted(c for c in produites
                        if not C.est_facteur_autorise(c)
                        and not C._est_variable_genre(c)
                        and not C._est_derivee_sinistralite(c))
    print(f"  colonnes produites par A2 qui ne passent AUCUN des trois filtres "
          f"(donc detruites) : {len(manquantes)}")
    for c in manquantes:
        print(f"      {c}")
    absentes = [c for c in DECLAREES_A2 if c not in produites]
    print(f"  derivees DECLAREES l.389-392 introuvables dans A2 : "
          f"{absentes if absentes else 'aucune'}")
else:
    print("  a2_preprocessing/agent.py introuvable")
