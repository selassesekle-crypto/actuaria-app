# -*- coding: utf-8 -*-
"""
core/charts_tarif.py — Graphiques de tarification, charte visuelle V3.
════════════════════════════════════════════════════════════════════════════

SOURCE UNIQUE du style graphique de la tarification (validé par Selasse, V3).
Module PUR : ne dépend que de plotly + numpy — AUCUN import d'agent (même
principe que core/plan_tarifaire.py, core/severite.py). Chaque fonction prend
des DONNÉES EXPLICITES et retourne un objet `plotly.graph_objects.Figure`.

Les agents (A3/A4/A6) appellent ces fonctions avec leurs données EN PORTÉE
(relativités, résidus, courbes, SHAP…) et stockent la figure dans leur dict
`graphiques`. Les services rendent la figure :
  • HTML / app  : natif interactif  → fig.to_html(config=CONFIG_PLOTLY)
  • Excel / Word : image statique (kaleido) — SUIVI (kaleido absent aujourd'hui).

7 fonctions :
  1. chart_lift_decile               5. chart_shap_summary
  2. chart_lorenz_gini               6. chart_distribution_predictions
  3. chart_relativites_glm           7. chart_residus_qq
  4. chart_walkforward_ae
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np
import plotly.graph_objects as go

# ════════════════════════════════════════════════════════════════════════════
# CHARTE VISUELLE V3 (constantes — la charte, une seule fois)
# ════════════════════════════════════════════════════════════════════════════
COULEURS = {
    'papier':        '#0B1E3D',   # fond papier — navy très profond
    'graphique':     '#122A4F',   # fond zone de tracé — navy moyen
    'texte':         '#F0F4F8',   # texte principal — blanc cassé
    'texte_2':       '#8A9BB0',   # texte secondaire — gris-bleu
    'or_titre':      '#F0D060',   # or titres — gold bright
    'or_accent':     '#D4AF37',   # or annotations / bordures
    'grille':        'rgba(255,255,255,0.06)',
    'hover_fond':    '#1A3A60',
    'hover_bordure': '#D4AF37',
    'ligne_predite': '#00E5A0',   # vert lumineux (ligne prédite, avec halo)
}

# Gradient des barres ORDONNÉES (déciles / catégories ordonnées) : bleu → orange
_GRAD_ANCRES = [
    (0.0, (30, 100, 180)),   # bas  — bleu profond
    (0.5, (70, 185, 160)),   # mid  — turquoise
    (1.0, (240, 85, 35)),    # haut — orange danger
]
BARRE_OR       = 'rgba(212,175,55,0.85)'    # barres NON ordonnées — or
BARRE_BORDURE  = 'rgba(255,255,255,0.15)'
BADGE          = {'fond': 'rgba(240,85,35,0.85)', 'bordure': '#F0D060'}
LEGENDE        = {'fond': 'rgba(11,30,61,0.92)', 'bordure': 'rgba(212,175,55,0.4)'}
POLICE         = 'Inter, Arial, sans-serif'

# Config de RENDU (pas du layout) — displayModeBar off. Passée à to_html/show.
CONFIG_PLOTLY  = {'displayModeBar': False, 'responsive': True}

__all__ = [
    'COULEURS', 'BARRE_OR', 'BADGE', 'LEGENDE', 'POLICE', 'CONFIG_PLOTLY',
    'chart_lift_decile', 'chart_lorenz_gini', 'chart_relativites_glm',
    'chart_walkforward_ae', 'chart_shap_summary',
    'chart_distribution_predictions', 'chart_residus_qq',
]


# ════════════════════════════════════════════════════════════════════════════
# HELPERS PRIVÉS
# ════════════════════════════════════════════════════════════════════════════
def _couleur_gradient(t: float) -> str:
    """Interpole la charte bleu → turquoise → orange pour t ∈ [0, 1]."""
    t = float(min(max(t, 0.0), 1.0))
    for (t0, c0), (t1, c1) in zip(_GRAD_ANCRES, _GRAD_ANCRES[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            r, g, b = (round(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
            return f'rgba({r},{g},{b},0.90)'
    r, g, b = _GRAD_ANCRES[-1][1]
    return f'rgba({r},{g},{b},0.90)'


def _gradient_ordonne(n: int) -> List[str]:
    """n couleurs interpolées bas → haut (barres ordonnées)."""
    if n <= 1:
        return [_couleur_gradient(0.5)]
    return [_couleur_gradient(i / (n - 1)) for i in range(n)]


def _appliquer_theme(fig: go.Figure, titre: Optional[str] = None) -> go.Figure:
    """Applique le layout commun de la charte V3 à une figure."""
    fig.update_layout(
        paper_bgcolor=COULEURS['papier'],
        plot_bgcolor=COULEURS['graphique'],
        font=dict(family=POLICE, color=COULEURS['texte'], size=13),
        title=dict(
            text=titre or '',
            font=dict(family=POLICE, color=COULEURS['or_titre'], size=18),
            x=0.02, xanchor='left', y=0.97, yanchor='top',
        ),
        margin=dict(l=70, r=30, t=64 if titre else 28, b=54),
        hoverlabel=dict(
            bgcolor=COULEURS['hover_fond'], bordercolor=COULEURS['hover_bordure'],
            font=dict(family=POLICE, color=COULEURS['texte']),
        ),
        legend=dict(
            orientation='h', yanchor='top', y=1.0, xanchor='right', x=1.0,
            bgcolor=LEGENDE['fond'], bordercolor=LEGENDE['bordure'], borderwidth=1,
            font=dict(family=POLICE, color=COULEURS['texte'], size=11),
        ),
    )
    _axes = dict(
        gridcolor=COULEURS['grille'], zerolinecolor=COULEURS['grille'],
        linecolor=COULEURS['texte_2'],
        tickfont=dict(family=POLICE, color=COULEURS['texte_2']),
        title_font=dict(family=POLICE, color=COULEURS['texte_2']),
    )
    fig.update_xaxes(**_axes)
    fig.update_yaxes(**_axes)
    return fig


def _badge_kpi(fig: go.Figure, texte: str, x: float = 0.985, y: float = 0.96) -> go.Figure:
    """Badge KPI (fond orange, bordure or) façon badge LIFT du prototype V3."""
    fig.add_annotation(
        x=x, y=y, xref='paper', yref='paper', text=f'<b>{texte}</b>',
        showarrow=False, xanchor='right', yanchor='top',
        font=dict(family=POLICE, color=COULEURS['texte'], size=14),
        bgcolor=BADGE['fond'], bordercolor=BADGE['bordure'], borderwidth=2, borderpad=6,
    )
    return fig


def _qnorm(p: np.ndarray) -> np.ndarray:
    """Inverse de la CDF normale (Acklam) — numpy pur, sans scipy. |err| < 1.2e-9."""
    p = np.asarray(p, dtype=float)
    a = [-3.969683028665376e+01,  2.209460984245205e+02, -2.759285104469687e+02,
          1.383577518672690e+02, -3.066479806614716e+01,  2.506628277459239e+00]
    b = [-5.447609879822406e+01,  1.615858368580409e+02, -1.556989798598866e+02,
          6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00,  4.374664141464968e+00,  2.938163982698783e+00]
    d = [ 7.784695709041462e-03,  3.224671290700398e-01,  2.445134137142996e+00,
          3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    x = np.zeros_like(p)
    lo = p < plow
    if np.any(lo):
        q = np.sqrt(-2 * np.log(p[lo]))
        x[lo] = ((((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) /
                 ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1))
    mid = (p >= plow) & (p <= phigh)
    if np.any(mid):
        q = p[mid] - 0.5
        r = q * q
        x[mid] = ((((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5])*q /
                  (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1))
    hi = p > phigh
    if np.any(hi):
        q = np.sqrt(-2 * np.log(1 - p[hi]))
        x[hi] = -((((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) /
                  ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1))
    return x


# ════════════════════════════════════════════════════════════════════════════
# 1. LIFT PAR DÉCILE — reproduit le prototype V3 (badge LIFT)
# ════════════════════════════════════════════════════════════════════════════
def chart_lift_decile(
    deciles: Sequence[float],
    lift_ratio: Optional[float] = None,
    *,
    titre: str = 'Lift par décile de risque prédit',
) -> go.Figure:
    """
    deciles    : sinistralité observée par décile de risque PRÉDIT
                 (décile 1 = bas risque → décile n = haut risque).
    lift_ratio : décile haut / décile bas — affiché en badge KPI.
    """
    vals = [float(v) for v in deciles]
    n = len(vals)
    x = [f'D{i + 1}' for i in range(n)]
    fig = go.Figure(go.Bar(
        x=x, y=vals,
        marker=dict(color=_gradient_ordonne(n),
                    line=dict(color=BARRE_BORDURE, width=1)),
        hovertemplate='%{x}<br>Sinistralité observée : %{y:.4f}<extra></extra>',
    ))
    _appliquer_theme(fig, titre)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title='Décile de risque prédit  (bas → haut)')
    fig.update_yaxes(title='Sinistralité observée')
    if lift_ratio is not None:
        _badge_kpi(fig, f'LIFT ×{float(lift_ratio):.2f}')
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 2. COURBE DE LORENZ + AIRE GINI
# ════════════════════════════════════════════════════════════════════════════
def chart_lorenz_gini(
    lorenz_x: Sequence[float],
    lorenz_y: Sequence[float],
    gini_observe: Optional[float] = None,
    *,
    gini_modele: Optional[float] = None,
    titre: str = 'Courbe de Lorenz — concentration du risque',
) -> go.Figure:
    """
    lorenz_x / lorenz_y : points de la courbe de Lorenz dans [0, 1]
                          (x = % cumulé de contrats, y = % cumulé de sinistres).
    gini_observe        : concentration des sinistres OBSERVÉS — le PLAFOND.
    gini_modele         : Gini prédictif du modèle retenu, si connu.

    ⚠️ CE BADGE DISAIT « GINI », ET C'ÉTAIT TROMPEUR. La courbe est construite
    en triant par la valeur OBSERVÉE : c'est trier comme un oracle parfait.
    Le nombre affiché est donc le PLAFOND atteignable sur ce portefeuille, pas
    une performance — mesuré, il ne bouge pas d'un iota quand la prédiction
    passe du hasard à l'oracle, et il BAISSE quand le portefeuille se dégrade
    (fréquence 0,05 → 0,95 ; fréquence 1,50 → 0,44). Or ailleurs dans le
    rapport, « Gini » désigne le pouvoir discriminant du modèle. Sur le
    rapport mesuré, le badge affichait 0,832 quand les tableaux affichaient
    0,178 : lu comme un Gini, le premier classait « excellent » un modèle que
    l'échelle du dépôt situe sous « acceptable ».

    ⚠️ ET LES DEUX ENSEMBLE VALENT MIEUX QUE L'UN CORRIGÉ. Leur rapport dit
    quelle part du discriminable le modèle capte réellement — une information
    qu'aucun des deux ne donne seul. Il est APPROXIMATIF et se lit comme tel :
    le plafond est calculé sur le portefeuille entier, le Gini du modèle sur
    la seule base de test. Mesuré sur huit tirages : le plafond varie de 1,8 %
    et le rapport reste entre 21,0 % et 21,5 %. C'est un ordre de grandeur
    fiable, pas une quatrième décimale.
    """
    xs = [float(v) for v in lorenz_x]
    ys = [float(v) for v in lorenz_y]
    fig = go.Figure()
    # Aire de Gini (polygone entre la courbe et la diagonale)
    fig.add_trace(go.Scatter(
        x=xs + [0.0], y=ys + [0.0], mode='lines', fill='toself',
        fillcolor='rgba(0,229,160,0.13)', line=dict(width=0),
        hoverinfo='skip', showlegend=False, name='Aire Gini',
    ))
    # Diagonale d'égalité parfaite
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode='lines', name='Égalité parfaite',
        line=dict(color=COULEURS['texte_2'], dash='dash', width=1), hoverinfo='skip',
    ))
    # Halo puis ligne prédite (vert lumineux)
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode='lines', hoverinfo='skip', showlegend=False,
        line=dict(color='rgba(0,229,160,0.25)', width=8),
    ))
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode='lines', name='Lorenz',
        line=dict(color=COULEURS['ligne_predite'], width=2.5),
        hovertemplate='%{x:.0%} contrats<br>%{y:.0%} sinistres<extra></extra>',
    ))
    _appliquer_theme(fig, titre)
    fig.update_xaxes(title='% cumulé de contrats (bas → haut risque)',
                     tickformat='.0%', range=[0, 1])
    fig.update_yaxes(title='% cumulé de sinistres', tickformat='.0%', range=[0, 1])
    if gini_observe is not None:
        obs = float(gini_observe)
        # 4 décimales : la convention des tableaux du rapport pour un Gini.
        texte = f'Concentration observée {obs:.4f}'
        if gini_modele is not None and obs > 0:
            mod = float(gini_modele)
            texte += (f'<br>Modèle {mod:.4f} — soit {100.0 * mod / obs:.0f} %'
                      f' du discriminable')
        _badge_kpi(fig, texte)
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 3. RELATIVITÉS GLM  exp(β)
# ════════════════════════════════════════════════════════════════════════════
def chart_relativites_glm(
    relativites: Dict[str, object],
    *,
    top: int = 15,
    titre: str = 'Relativités tarifaires GLM  exp(β)',
) -> go.Figure:
    """
    relativites : {variable: {'relativite': exp(β), 'ic95_low', 'ic95_high'}}
                  (accepte aussi {variable: exp(β)} en scalaire). Barres H triées
                  par MAGNITUDE d'effet |log(exp β)|, gradient, IC95 en error-bars,
                  ligne neutre à 1.0.
    """
    items = []
    for var, d in relativites.items():
        if isinstance(d, dict):
            rel, lo, hi = d.get('relativite'), d.get('ic95_low'), d.get('ic95_high')
        else:
            rel, lo, hi = d, None, None
        if rel is None:
            continue
        items.append((str(var), float(rel),
                      None if lo is None else float(lo),
                      None if hi is None else float(hi)))
    items.sort(key=lambda t: abs(np.log(max(t[1], 1e-9))), reverse=True)
    items = items[:top][::-1]                      # top N, plus fort en HAUT
    noms = [t[0] for t in items]
    rels = [t[1] for t in items]
    mags = [abs(np.log(max(r, 1e-9))) for r in rels]
    mx = max(mags) if mags else 1.0
    couleurs = [_couleur_gradient(m / mx if mx else 0.0) for m in mags]
    err_plus = [(t[3] - t[1]) if t[3] is not None else 0.0 for t in items]
    err_moins = [(t[1] - t[2]) if t[2] is not None else 0.0 for t in items]
    fig = go.Figure(go.Bar(
        x=rels, y=noms, orientation='h',
        marker=dict(color=couleurs, line=dict(color=BARRE_BORDURE, width=1)),
        error_x=dict(type='data', symmetric=False, array=err_plus, arrayminus=err_moins,
                     color=COULEURS['or_accent'], thickness=1.2, width=4),
        hovertemplate='%{y}<br>exp(β) = %{x:.3f}<extra></extra>',
    ))
    _appliquer_theme(fig, titre)
    fig.update_layout(showlegend=False)
    fig.add_vline(x=1.0, line=dict(color=COULEURS['texte_2'], dash='dash', width=1))
    fig.update_xaxes(title='Relativité exp(β)   (1 = neutre)')
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 4. WALK-FORWARD A/E — bandes ±15 %, seuils ACPR
# ════════════════════════════════════════════════════════════════════════════
def chart_walkforward_ae(
    fenetres: Sequence[Dict],
    *,
    titre: str = 'Backtesting walk-forward — ratio A/E par fenêtre',
) -> go.Figure:
    """
    fenetres : [{'annee'|'annee_test': …, 'ae_ratio': …}] — une par fenêtre WF.
    Bande d'acceptabilité ±15 % (0.85–1.15), cible à 1.0, points colorés
    VERT (0.95–1.05) / AMBRE (0.90–1.10) / ROUGE sinon.
    """
    annees = [f.get('annee', f.get('annee_test')) for f in fenetres]
    ae = [float(f.get('ae_ratio', 1.0)) for f in fenetres]

    def _coul(v: float) -> str:
        if 0.95 <= v <= 1.05:
            return COULEURS['ligne_predite']
        if 0.90 <= v <= 1.10:
            return COULEURS['or_accent']
        return 'rgba(240,85,35,0.95)'

    fig = go.Figure()
    fig.add_hrect(y0=0.85, y1=1.15, fillcolor='rgba(0,229,160,0.06)', line_width=0)
    fig.add_hline(y=1.0, line=dict(color=COULEURS['texte_2'], dash='dash', width=1))
    for yv in (0.85, 1.15):
        fig.add_hline(y=yv, line=dict(color=COULEURS['or_accent'], dash='dot', width=1))
    fig.add_trace(go.Scatter(
        x=annees, y=ae, mode='lines+markers', name='A/E',
        line=dict(color=COULEURS['ligne_predite'], width=2),
        marker=dict(color=[_coul(v) for v in ae], size=13,
                    line=dict(color=COULEURS['texte'], width=1)),
        hovertemplate='%{x}<br>A/E = %{y:.4f}<extra></extra>',
    ))
    _appliquer_theme(fig, titre)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title='Fenêtre (année test)', type='category')
    fig.update_yaxes(title='Ratio A/E  (attendu / prédit)')
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 5. IMPORTANCE SHAP
# ════════════════════════════════════════════════════════════════════════════
def chart_shap_summary(
    importance: Dict[str, float],
    *,
    top: int = 15,
    titre: str = 'Importance SHAP — contribution moyenne |φ|',
) -> go.Figure:
    """
    importance : {feature: importance moyenne |SHAP|}. Barres H triées desc,
                 gradient par magnitude.
    """
    items = sorted(importance.items(), key=lambda kv: float(kv[1]), reverse=True)[:top]
    items = items[::-1]                            # plus fort en HAUT
    noms = [str(k) for k, _ in items]
    vals = [float(v) for _, v in items]
    mx = max(vals) if vals else 1.0
    couleurs = [_couleur_gradient(v / mx if mx else 0.0) for v in vals]
    fig = go.Figure(go.Bar(
        x=vals, y=noms, orientation='h',
        marker=dict(color=couleurs, line=dict(color=BARRE_BORDURE, width=1)),
        hovertemplate='%{y}<br>|SHAP| moyen = %{x:.4f}<extra></extra>',
    ))
    _appliquer_theme(fig, titre)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title='Importance moyenne |SHAP|')
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 6. DISTRIBUTION DES PRÉDICTIONS
# ════════════════════════════════════════════════════════════════════════════
def chart_distribution_predictions(
    predictions: Sequence[float],
    *,
    quantiles: Sequence[float] = (0.5, 0.9, 0.99),
    unite: str = '€',
    titre: str = 'Distribution des primes prédites',
) -> go.Figure:
    """
    predictions : array des primes/prédictions du portefeuille. Histogramme +
                  lignes de quantiles annotées (ligne prédite vert lumineux).
    """
    p = np.asarray(predictions, dtype=float)
    p = p[np.isfinite(p)]
    fig = go.Figure(go.Histogram(
        x=p, nbinsx=50, name='Primes',
        marker=dict(color=BARRE_OR, line=dict(color=BARRE_BORDURE, width=1)),
        hovertemplate='%{x}<br>%{y} contrats<extra></extra>',
    ))
    _appliquer_theme(fig, titre)
    fig.update_layout(showlegend=False)
    if p.size:
        for q in quantiles:
            qv = float(np.quantile(p, q))
            fig.add_vline(
                x=qv, line=dict(color=COULEURS['ligne_predite'], dash='dash', width=1.5),
                annotation_text=f'Q{int(round(q * 100))} = {qv:,.0f}{unite}',
                annotation_position='top',
                annotation_font=dict(family=POLICE, color=COULEURS['ligne_predite'], size=11),
            )
    fig.update_xaxes(title=f'Prime prédite ({unite})')
    fig.update_yaxes(title='Nombre de contrats')
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 7. QQ-PLOT DES RÉSIDUS
# ════════════════════════════════════════════════════════════════════════════
def chart_residus_qq(
    residus: Sequence[float],
    *,
    titre: str = 'QQ-plot des résidus de Pearson',
) -> go.Figure:
    """
    residus : array des résidus (Pearson) du GLM. Compare leurs quantiles aux
              quantiles théoriques d'une loi normale ; ligne y=x or, points
              colorés par écart à la théorie.
    """
    r = np.asarray(residus, dtype=float)
    r = np.sort(r[np.isfinite(r)])
    n = r.size
    fig = go.Figure()
    if n >= 2:
        probs = (np.arange(1, n + 1) - 0.5) / n
        theo = _qnorm(probs)
        ecart = np.abs(r - theo)
        mx = float(ecart.max()) or 1.0
        couleurs = [_couleur_gradient(e / mx) for e in ecart]
        lim = float(max(np.abs(theo).max(), np.abs(r).max()))
        fig.add_trace(go.Scatter(
            x=[-lim, lim], y=[-lim, lim], mode='lines', name='y = x',
            line=dict(color=COULEURS['or_accent'], dash='dash', width=1.5), hoverinfo='skip',
        ))
        fig.add_trace(go.Scatter(
            x=theo, y=r, mode='markers', name='Résidus',
            marker=dict(color=couleurs, size=5, line=dict(width=0)),
            hovertemplate='théorique %{x:.2f}<br>observé %{y:.2f}<extra></extra>',
        ))
    _appliquer_theme(fig, titre)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title='Quantiles théoriques (normale)')
    fig.update_yaxes(title='Quantiles observés (résidus)')
    return fig
