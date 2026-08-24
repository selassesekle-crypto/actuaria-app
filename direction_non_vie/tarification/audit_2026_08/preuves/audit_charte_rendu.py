# ruff: noqa
"""LES DEUX CHARTES, RENDUES COTE A COTE SUR DE VRAIES FIGURES.

Rien n'est modifie dans le depot : on RE-THEME une copie de la figure produite
par core/charts_tarif, avec chaque palette, et on rend en PNG.
Plus la mesure OBJECTIVE : les contrastes WCAG.
"""
import os
import sys
import warnings

sys.path.insert(0, r'C:\Users\selse\actuaria-app')
warnings.filterwarnings('ignore')

import numpy as np
from PIL import Image

import core.charts_tarif as CH

SORTIE = r'C:\Users\selse\AppData\Local\Temp\claude\C--Users-selse-actuaria-app\076f6e80-846d-43dc-bfa8-ba814f936a34\scratchpad\rendus'
os.makedirs(SORTIE, exist_ok=True)

# ── LES TROIS JEUX DE ROLES ───────────────────────────────────────────────────
V3 = {
    'papier': '#0B1E3D', 'graphique': '#122A4F', 'texte': '#F0F4F8',
    'texte_2': '#8A9BB0', 'or_titre': '#F0D060', 'or_accent': '#D4AF37',
    'hover_fond': '#1A3A60', 'ligne_predite': '#00E5A0',
    'grille': 'rgba(255,255,255,0.06)',
    'rag_vert': '#00E5A0', 'rag_ambre': '#D4AF37', 'rag_rouge': 'rgb(240,85,35)',
    'barre': 'rgba(212,175,55,0.85)',
    'grad': [(30, 100, 180), (70, 185, 160), (240, 85, 35)],
}
APP = {
    'papier': '#0F2E52', 'graphique': '#1B3A5C', 'texte': '#F0F4F8',
    'texte_2': '#8A9AB0', 'or_titre': '#E8C96A', 'or_accent': '#C9A84C',
    'hover_fond': '#243F6A', 'ligne_predite': '#2ECC71',
    'grille': 'rgba(255,255,255,0.06)',
    'rag_vert': '#2ECC71', 'rag_ambre': '#F39C12', 'rag_rouge': '#E74C3C',
    'barre': 'rgba(201,168,76,0.85)',
    'grad': [(52, 152, 219), (46, 204, 113), (231, 76, 60)],
}


# ── CONTRASTE WCAG ────────────────────────────────────────────────────────────
def _rgb(c):
    c = c.strip()
    if c.startswith('#'):
        return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    n = [float(x) for x in c[c.find('(') + 1:c.find(')')].split(',')[:3]]
    return tuple(int(x) for x in n)


def _lum(c):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(c)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


print("=" * 78)
print("  CONTRASTES WCAG — mesure OBJECTIVE de la lisibilite")
print("=" * 78)
PAIRES = [
    ("texte sur papier",          'texte', 'papier'),
    ("texte secondaire / graph",  'texte_2', 'graphique'),
    ("titre or sur papier",       'or_titre', 'papier'),
    ("accent or sur graphique",   'or_accent', 'graphique'),
    ("ligne predite / graphique", 'ligne_predite', 'graphique'),
    ("RAG VERT sur graphique",    'rag_vert', 'graphique'),
    ("RAG AMBRE sur graphique",   'rag_ambre', 'graphique'),
    ("RAG ROUGE sur graphique",   'rag_rouge', 'graphique'),
]
print(f"  {'role':30s} {'CHARTE V3':>12s} {'PALETTE APP':>12s}   meilleur")
gagnants = {}
for lib, a, b in PAIRES:
    cv, ca = contraste(V3[a], V3[b]), contraste(APP[a], APP[b])
    g = 'V3' if cv > ca else 'APP'
    gagnants[a] = g
    aa = lambda c: 'AAA' if c >= 7 else 'AA' if c >= 4.5 else 'AA-large' if c >= 3 else 'INSUFF'
    print(f"  {lib:30s} {cv:7.2f} {aa(cv):>5s} {ca:7.2f} {aa(ca):>5s}   {g}")
print()
print("  Distinguabilite des trois RAG entre eux (plus haut = plus distinct) :")
for nom, P in (('CHARTE V3', V3), ('PALETTE APP', APP)):
    d = [contraste(P['rag_vert'], P['rag_ambre']),
         contraste(P['rag_ambre'], P['rag_rouge']),
         contraste(P['rag_vert'], P['rag_rouge'])]
    print(f"      {nom:12s} vert/ambre={d[0]:.2f}  ambre/rouge={d[1]:.2f}  "
          f"vert/rouge={d[2]:.2f}   min={min(d):.2f}")
print()
print(f"  -> roles ou la V3 gagne  : "
      f"{[k for k, v in gagnants.items() if v == 'V3']}")
print(f"  -> roles ou l'APP gagne  : "
      f"{[k for k, v in gagnants.items() if v == 'APP']}")


# ── LE THEME, APPLIQUE A UNE FIGURE EXISTANTE ─────────────────────────────────
def rethemer(fig, P):
    """Re-theme une figure produite par charts_tarif avec le jeu de roles P."""
    fig.update_layout(
        paper_bgcolor=P['papier'], plot_bgcolor=P['graphique'],
        font=dict(color=P['texte']),
        title=dict(font=dict(color=P['or_titre'])),
        hoverlabel=dict(bgcolor=P['hover_fond'], bordercolor=P['or_accent']),
        legend=dict(bgcolor=P['papier'], bordercolor=P['or_accent']),
    )
    ax = dict(gridcolor=P['grille'], zerolinecolor=P['grille'],
              linecolor=P['texte_2'], tickfont=dict(color=P['texte_2']),
              title_font=dict(color=P['texte_2']))
    fig.update_xaxes(**ax)
    fig.update_yaxes(**ax)
    for a in (fig.layout.annotations or []):
        if a.bgcolor:
            a.bgcolor = P['rag_rouge']
            a.bordercolor = P['or_titre']
        a.font.color = P['texte']
    for s in (fig.layout.shapes or []):
        if s.type == 'rect':
            s.fillcolor = _rgba(P['rag_vert'], 0.07)
        elif s.type == 'line' and s.line.dash == 'dot':
            s.line.color = P['or_accent']
        elif s.type == 'line':
            s.line.color = P['texte_2']
    return fig


def _rgba(c, a):
    r, g, b = _rgb(c)
    return f'rgba({r},{g},{b},{a})'


def grad(P, t):
    t = min(max(t, 0.0), 1.0)
    anc = [(0.0, P['grad'][0]), (0.5, P['grad'][1]), (1.0, P['grad'][2])]
    for (t0, c0), (t1, c1) in zip(anc, anc[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            r, g, b = (round(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
            return f'rgba({r},{g},{b},0.90)'
    r, g, b = anc[-1][1]
    return f'rgba({r},{g},{b},0.90)'


# ── LES TROIS FIGURES, EN CONDITIONS REELLES ──────────────────────────────────


def figures(P, suffixe):
    out = []

    # 1. LIFT PAR DECILE -- le gradient + le badge
    dec = [0.031, 0.044, 0.052, 0.061, 0.073, 0.088, 0.106, 0.131, 0.172, 0.264]
    f = CH.chart_lift_decile(dec, lift_ratio=8.52)
    f = rethemer(f, P)
    f.data[0].marker.color = [grad(P, i / 9) for i in range(10)]
    f.data[0].marker.line.color = 'rgba(255,255,255,0.15)'
    out.append(('lift_decile', f))

    # 2. WALK-FORWARD A/E -- les trois RAG + les bandes
    fen = [{'annee': 2019, 'ae_ratio': 0.88}, {'annee': 2020, 'ae_ratio': 0.97},
           {'annee': 2021, 'ae_ratio': 1.02}, {'annee': 2022, 'ae_ratio': 1.09},
           {'annee': 2023, 'ae_ratio': 1.16}, {'annee': 2024, 'ae_ratio': 1.01}]
    f = CH.chart_walkforward_ae(fen)
    f = rethemer(f, P)
    ae = [x['ae_ratio'] for x in fen]
    coul = [P['rag_vert'] if 0.95 <= v <= 1.05 else
            P['rag_ambre'] if 0.90 <= v <= 1.10 else P['rag_rouge'] for v in ae]
    f.data[-1].line.color = P['ligne_predite']
    f.data[-1].marker.color = coul
    f.data[-1].marker.line.color = P['texte']
    out.append(('walkforward_ae', f))

    # 3. RELATIVITES GLM -- barres horizontales + IC + ligne neutre
    rel = {'bonus_malus': {'relativite': 1.62, 'ic95_low': 1.51, 'ic95_high': 1.74},
           'age_vehicule': {'relativite': 1.28, 'ic95_low': 1.19, 'ic95_high': 1.38},
           'zone_geographique_urbain': {'relativite': 1.21, 'ic95_low': 1.10, 'ic95_high': 1.33},
           'puissance_fiscale': {'relativite': 1.11, 'ic95_low': 1.04, 'ic95_high': 1.19},
           'anciennete_permis': {'relativite': 0.93, 'ic95_low': 0.87, 'ic95_high': 0.99},
           'carburant_diesel': {'relativite': 0.88, 'ic95_low': 0.81, 'ic95_high': 0.96},
           'usage_prive': {'relativite': 0.74, 'ic95_low': 0.67, 'ic95_high': 0.82},
           'parking_box': {'relativite': 0.66, 'ic95_low': 0.58, 'ic95_high': 0.75}}
    f = CH.chart_relativites_glm(rel)
    f = rethemer(f, P)
    n = len(f.data[0].x)
    mags = [abs(np.log(v)) for v in f.data[0].x]
    mx = max(mags)
    f.data[0].marker.color = [grad(P, m / mx) for m in mags]
    f.data[0].error_x.color = P['or_accent']
    out.append(('relativites', f))

    for nom, fig in out:
        fig.write_image(os.path.join(SORTIE, f'{nom}_{suffixe}.png'),
                        width=760, height=470, scale=2)
    return [n for n, _ in out]


noms = figures(V3, 'V3')
figures(APP, 'APP')

# ── ASSEMBLAGE COTE A COTE ────────────────────────────────────────────────────
from PIL import ImageDraw, ImageFont
try:
    police = ImageFont.truetype("arialbd.ttf", 30)
except Exception:
    police = ImageFont.load_default()

for nom in noms:
    a = Image.open(os.path.join(SORTIE, f'{nom}_V3.png'))
    b = Image.open(os.path.join(SORTIE, f'{nom}_APP.png'))
    H = 56
    canvas = Image.new('RGB', (a.width + b.width + 24, a.height + H + 16),
                       (28, 28, 32))
    canvas.paste(a, (0, H))
    canvas.paste(b, (a.width + 24, H))
    d = ImageDraw.Draw(canvas)
    d.text((16, 14), "CHARTE V3  (core/charts_tarif)", fill=(240, 208, 96), font=police)
    d.text((a.width + 40, 14), "PALETTE APPLICATION", fill=(232, 201, 106), font=police)
    canvas.save(os.path.join(SORTIE, f'COMPARAISON_{nom}.png'))
    print(f"  ecrit : COMPARAISON_{nom}.png   ({canvas.width}x{canvas.height})")
