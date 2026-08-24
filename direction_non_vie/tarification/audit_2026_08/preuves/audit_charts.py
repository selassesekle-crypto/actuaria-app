# ruff: noqa
"""RELEVE core/charts_tarif.py -- LES FIGURES PUBLIEES.

Un graphique signe par un actuaire est un livrable. On mesure ce qu'il
affiche, ce qu'il tait, et si ses seuils sont ceux du reste du systeme.
"""
import ast
import io
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np

import core.charts_tarif as CH

RACINE = r'C:\Users\selse\actuaria-app'


def titre(t):
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


def textes(fig):
    """Tout le texte visible d'une figure : titres, annotations, axes."""
    out = []
    lay = fig.layout
    if lay.title and lay.title.text:
        out.append(str(lay.title.text))
    for a in (lay.annotations or []):
        if a.text:
            out.append(str(a.text))
    for ax in ('xaxis', 'yaxis'):
        t = getattr(lay, ax).title
        if t and t.text:
            out.append(str(t.text))
    for tr in fig.data:
        if getattr(tr, 'name', None):
            out.append(str(tr.name))
    return out


# ══════════════════════════════════════════════════════════════════════════════
titre("M1 -- MODULE PUR ? SEPT FONCTIONS ?")
# ══════════════════════════════════════════════════════════════════════════════
src = io.open(os.path.join(RACINE, 'core/charts_tarif.py'), encoding='utf-8').read()
arbre = ast.parse(src)
imports = set()
for nd in ast.walk(arbre):
    if isinstance(nd, ast.Import):
        imports.update(a.name.split('.')[0] for a in nd.names)
    elif isinstance(nd, ast.ImportFrom) and nd.module:
        imports.add(nd.module.split('.')[0])
fonctions = [n.name for n in arbre.body
             if isinstance(n, ast.FunctionDef) and n.name.startswith('chart_')]
print(f"  imports  : {sorted(imports)}")
print(f"  {'[BON    ]' if imports <= {'__future__', 'typing', 'numpy', 'plotly'} else '[CONSTAT]'} "
      f"aucun import d'agent")
print(f"  fonctions chart_* : {len(fonctions)}  -> {fonctions}")
print(f"  __all__ les couvre : "
      f"{set(fonctions) <= set(CH.__all__)}  ({len(CH.__all__)} entrees)")


# ══════════════════════════════════════════════════════════════════════════════
titre("M2 -- `_qnorm` : L'ERREUR ANNONCEE EST-ELLE < 1,2e-9 ?")
# ══════════════════════════════════════════════════════════════════════════════
try:
    from scipy.stats import norm
    grilles = {
        'coeur      [0,025 ; 0,975]': np.linspace(0.025, 0.975, 200001),
        'queue bas  [1e-9 ; 0,025]':  np.linspace(1e-9, 0.02425, 100001),
        'queue haut [0,975 ; 1-1e-9]': np.linspace(0.97575, 1 - 1e-9, 100001),
        'grille QQ-plot n=5000':      (np.arange(1, 5001) - 0.5) / 5000,
    }
    pire = 0.0
    for lib, p in grilles.items():
        e = np.abs(CH._qnorm(p) - norm.ppf(p))
        pire = max(pire, float(e.max()))
        etat = '[BON    ]' if e.max() < 1.2e-9 else '[CONSTAT]'
        print(f"  {etat} {lib:30s} |err| max = {e.max():.3e}")
    print()
    print(f"  pire ecart ABSOLU sur {sum(len(g) for g in grilles.values()):,} points"
          f" : {pire:.3e}   annonce : 1.2e-09")
    print()
    print("  ⚠ Acklam publie une erreur RELATIVE de 1,15e-9, pas absolue.")
    print("    L'instruction honnete est donc de mesurer les deux :")
    pr = 0.0
    for lib, p in grilles.items():
        v = norm.ppf(p)
        m = np.abs(v) > 1e-12
        e = np.abs((CH._qnorm(p)[m] - v[m]) / v[m])
        pr = max(pr, float(e.max()))
        etat = '[BON    ]' if e.max() < 1.2e-9 else '[CONSTAT]'
        print(f"    {etat} {lib:30s} |err RELATIVE| max = {e.max():.3e}")
    print(f"    pire erreur RELATIVE : {pr:.3e}")
    print()
    print("    -> l'algorithme tient sa promesse en relatif ; la docstring")
    print("       ecrit « |err| » sans dire laquelle.")
except ImportError:
    print("  scipy absent -- comparaison impossible")


# ══════════════════════════════════════════════════════════════════════════════
titre("M3 -- LE BADGE DE LORENZ : QUE DIT-IL QUAND LE MODELE DEPASSE LE PLAFOND ?")
# ══════════════════════════════════════════════════════════════════════════════
xs = list(np.linspace(0, 1, 51))
ys = [x ** 2.5 for x in xs]
CAS = [
    ("cas nominal   obs=0,8320  mod=0,1780", 0.8320, 0.1780),
    ("modele > plafond  obs=0,20  mod=0,25", 0.20, 0.25),
    ("modele NEGATIF   obs=0,20  mod=-0,0105", 0.20, -0.0105),
    ("plafond quasi nul obs=1e-6 mod=0,18", 1e-6, 0.18),
]
for lib, obs, mod in CAS:
    f = CH.chart_lorenz_gini(xs, ys, obs, gini_modele=mod)
    badge = [t for t in textes(f) if 'Concentration' in t]
    print(f"  {lib}")
    print(f"      badge = {badge[0].replace('<br>', ' | ') if badge else '(aucun)'}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M4 -- LES BANDES A/E : LA FIGURE ET LE GATE DISENT-ILS LA MEME CHOSE ?")
# ══════════════════════════════════════════════════════════════════════════════
import core.conformite_reglementaire as C
fen = [{'annee': 2021, 'ae_ratio': 0.87}, {'annee': 2022, 'ae_ratio': 1.00},
       {'annee': 2023, 'ae_ratio': 1.13}, {'annee': 2024, 'ae_ratio': 1.02}]
f = CH.chart_walkforward_ae(fen)
rects = [s for s in (f.layout.shapes or []) if s.type == 'rect']
lignes = sorted(set(round(float(s.y0), 4) for s in (f.layout.shapes or [])
                    if s.type == 'line' and s.y0 == s.y1))
print(f"  la figure trace : bande verte {[(float(r.y0), float(r.y1)) for r in rects]}")
print(f"                    lignes horizontales a {lignes}")
print(f"  couleur des points (chart_walkforward_ae) : "
      f"VERT si 0,95<=x<=1,05 · AMBRE si 0,90<=x<=1,10 · ROUGE sinon")
print()
for ae in (0.87, 0.92, 1.00, 1.13):
    bt = {'disponible': True, 'modele_recalibre_fidele': True,
          'gini_wf_moyen': 0.25, 'ae_ratio': ae, 'ae_moyen_wf': ae,
          'n_fenetres_rouge': 0, 'stabilite_wf': 'OK'}
    av = C.avertissement_walk_forward(bt)
    dans_bande = 0.85 <= ae <= 1.15
    coul = ('VERT ' if 0.95 <= ae <= 1.05 else
            'AMBRE' if 0.90 <= ae <= 1.10 else 'ROUGE')
    verdict = 'AVERTIT' if av else 'silence'
    etat = '[CONSTAT]' if (dans_bande and av) else '        '
    print(f"  {etat} A/E={ae:.2f}  figure: point {coul}, "
          f"{'DANS' if dans_bande else 'hors'} la bande verte   "
          f"| gate: {verdict}")


# ══════════════════════════════════════════════════════════════════════════════
titre("M5 -- CE QUI EST TRONQUE OU ECARTE EST-IL DIT SUR LA FIGURE ?")
# ══════════════════════════════════════════════════════════════════════════════
# (a) relativites : top=15 sur 23 (le plan auto.yaml produit 23 colonnes)
rel = {f'facteur_{i:02d}': {'relativite': 1.0 + 0.05 * i} for i in range(23)}
f = CH.chart_relativites_glm(rel)
n_barres = len(f.data[0].y)
dit = any('23' in t or 'sur' in t.lower() or 'top' in t.lower() for t in textes(f))
print(f"  (a) relativites : {len(rel)} fournies -> {n_barres} tracees")
print(f"      {'[BON    ]' if dit else '[CONSTAT]'} la figure le dit : {dit}")
print(f"      textes = {textes(f)}")

# (b) walk-forward : fenetres sans A/E
fen2 = [{'annee': 2020, 'ae_ratio': None}, {'annee': 2021, 'ae_ratio': 0.98},
        {'annee': 2022, 'ae_ratio': None}, {'annee': 2023, 'ae_ratio': 1.02}]
f = CH.chart_walkforward_ae(fen2)
n_pts = len(f.data[-1].x)
dit = any('non mesur' in t.lower() or '2020' in t or 'fenetre' in t.lower()
          for t in textes(f))
print(f"  (b) walk-forward : {len(fen2)} fenetres fournies -> {n_pts} tracees")
print(f"      {'[BON    ]' if dit else '[CONSTAT]'} la figure signale les 2 "
      f"ecartees : {dit}")

# (c) distribution : predictions non finies
p = np.concatenate([np.random.default_rng(1).gamma(2, 100, 500),
                    np.full(500, np.nan)])
f = CH.chart_distribution_predictions(p)
n_gardes = len(f.data[0].x)
dit = any('500' in t or 'exclu' in t.lower() for t in textes(f))
print(f"  (c) distribution : {len(p)} predictions dont 500 NaN -> "
      f"{n_gardes} tracees")
print(f"      {'[BON    ]' if dit else '[CONSTAT]'} la figure le dit : {dit}")

# (d) shap : top=15
imp = {f'f{i}': float(30 - i) for i in range(30)}
f = CH.chart_shap_summary(imp)
print(f"  (d) SHAP : {len(imp)} features -> {len(f.data[0].y)} tracees")


# ══════════════════════════════════════════════════════════════════════════════
titre("M6 -- UNE FIGURE VIDE RESSEMBLE-T-ELLE A UNE FIGURE ?")
# ══════════════════════════════════════════════════════════════════════════════
for lib, f in (
        ("QQ-plot, 1 residu",        CH.chart_residus_qq([0.5])),
        ("QQ-plot, 0 residu",        CH.chart_residus_qq([])),
        ("QQ-plot, que des NaN",     CH.chart_residus_qq([np.nan] * 100)),
        ("distribution, 0 valeur",   CH.chart_distribution_predictions([])),
        ("lift, 0 decile",           CH.chart_lift_decile([])),
        ("relativites, 0 variable",  CH.chart_relativites_glm({})),
        ("walk-forward, 0 fenetre",  CH.chart_walkforward_ae([])),
):
    n = 0
    for tr in f.data:
        xv = getattr(tr, 'x', None)
        n += 0 if xv is None else len(xv)
    dit = any('aucun' in t.lower() or 'indisponible' in t.lower() or
              'non ' in t.lower() for t in textes(f))
    etat = '[CONSTAT]' if (n == 0 and not dit) else '        '
    print(f"  {etat} {lib:26s} points traces = {n:3d}   "
          f"la figure dit qu'elle est vide : {dit}")
print()
print("  Chacune rend une figure THEMEE, avec titre, axes et bande verte --")
print("  visuellement indiscernable d'une figure qui porte un resultat.")


# ══════════════════════════════════════════════════════════════════════════════
titre("M7 -- KALEIDO : LES FIGURES ATTEIGNENT-ELLES L'EXCEL ET LE WORD ?")
# ══════════════════════════════════════════════════════════════════════════════
try:
    import kaleido
    print(f"  [BON    ] kaleido present : {getattr(kaleido, '__version__', '?')}")
except ImportError:
    print("  [CONSTAT] kaleido ABSENT -- l'en-tete l.15 le dit deja (« SUIVI »)")
    try:
        CH.chart_lift_decile([1, 2, 3]).to_image(format='png')
        print("            et pourtant to_image fonctionne ?")
    except Exception as e:
        print(f"            to_image -> {type(e).__name__} : {str(e)[:56]}")
