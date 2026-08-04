# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n5_graphiques.py  —  Graphiques Plotly (style dashboard ActuarIA)
# =============================================================================
#
#  14 graphiques professionnels :
#
#  G1  — Heatmap triangle de développement (zone connue + projection)
#  G2  — Courbes de cadence cumulées par année (style image fournie)
#  G3  — Facteurs CL avec bande ±2σ et coloration outliers
#  G4  — IBNR par année (barres verticales + courbe cumulée, dégradé couleur)
#  G5  — Convergence des méthodes + BE S2 + IC Mack
#  G6  — Distribution Bootstrap (histogramme + P50/P90/P99.5)
#  G7  — SCR par composante (donut, style image fournie)
#  G8  — H1 Indépendance (corrélations Spearman par paire)
#  G9  — H2 Stabilité (heatmap écarts facteurs individuels vs CL)
#  G10 — H3 LR a priori par année mature vs référence marché
#  G11 — Ultimates projetés vs dernière diagonale
#  G12 — Sensibilités du BE (tornado chart)
#  G13 — Paiements cumulés par année de survenance
#  G14 — Back-testing : boni/mali de liquidation
#
#  Palette ActuarIA
#  ─────────────────
#  Fond      : #0F2E52  (Navy profond)
#  Or        : #C9A84C  (Gold)
#  Blanc     : #F0F4F8
#  Gris clair: #8A9AB0
#  Bleu vif  : #378ADD
#  Vert vif  : #2ECC71
#  Rouge vif : #E74C3C
#  Ambre     : #F39C12
#  Violet    : #9B59B6
#  Cyan      : #1ABC9C
#
# =============================================================================

import logging
from typing import Dict, List, Optional

import numpy as np

from .n2_hypotheses_bootstrap import libelle_phi_par_axe
from .methodes_be import disponible, libelle, reserve

logger = logging.getLogger('actuaria.a7')

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False
    logger.warning("Plotly non disponible — graphiques désactivés")

# ── Palette ──────────────────────────────────────────────────────────────────
NAVY     = '#0F2E52'
NAVY_L   = '#1B3A5C'
NAVY_LL  = '#243F61'
OR       = '#C9A84C'
BLANC    = '#F0F4F8'
GRIS     = '#8A9AB0'
BLEU     = '#378ADD'
VERT     = '#2ECC71'
ROUGE    = '#E74C3C'
AMBRE    = '#F39C12'
VIOLET   = '#9B59B6'
CYAN     = '#1ABC9C'

# Séquence de couleurs pour les années de survenance (style image fournie)
COULEURS_ANNEES = [
    '#00D4FF', '#7C3AED', '#10B981', '#F59E0B',
    '#EF4444', '#8B5CF6', '#06B6D4', '#F97316',
    '#84CC16', '#EC4899', '#14B8A6', '#F43F5E',
    '#A855F7', '#22D3EE', '#4ADE80',
]

# Layout de base commun à tous les graphiques
LAYOUT_BASE = dict(
    paper_bgcolor=NAVY,
    plot_bgcolor=NAVY_L,
    font=dict(family='Inter, Arial, sans-serif', color=BLANC, size=11),
    margin=dict(l=60, r=30, t=55, b=50),
    height=420,
    hoverlabel=dict(
        bgcolor=NAVY_LL,
        bordercolor=OR,
        font=dict(color=BLANC, size=11),
    ),
)


def _layout(**kwargs) -> dict:
    """Fusionne LAYOUT_BASE avec des overrides spécifiques."""
    base = LAYOUT_BASE.copy()
    base.update(kwargs)
    return base


# =============================================================================
#  G1 — HEATMAP TRIANGLE DE DÉVELOPPEMENT
# =============================================================================

def g1_heatmap_triangle(C: np.ndarray) -> 'go.Figure':
    """
    Heatmap du triangle de développement.
    Zone connue en dégradé Navy→Or→Rouge.
    Zone projetée grisée.
    """
    if not PLOTLY_OK:
        return None
    n, m = C.shape

    z_known = []
    z_proj  = []
    for i in range(n):
        row_k, row_p = [], []
        for j in range(m):
            in_zone = (j <= n - i - 1) and C[i, j] > 0
            row_k.append(float(C[i, j]) if in_zone else None)
            row_p.append(float(C[i, j]) if not in_zone and C[i, j] > 0 else None)
        z_known.append(row_k)
        z_proj.append(row_p)

    x_lbl = [f"{(j+1)*12}M" for j in range(m)]
    y_lbl = [f"An. {i}" for i in range(n)]

    fig = go.Figure()

    # Zone connue
    fig.add_trace(go.Heatmap(
        z=z_known,
        x=x_lbl, y=y_lbl,
        colorscale=[[0, NAVY_LL], [0.4, '#1A5276'], [0.75, OR], [1, ROUGE]],
        showscale=True,
        name='Zone connue',
        hovertemplate=(
            "<b>%{y} — %{x}</b><br>"
            "Cumulé payé : <b>%{z:,.0f} €</b><extra></extra>"
        ),
        colorbar=dict(
            title=dict(text='Sinistres cumulés', font=dict(color=BLANC, size=10)),
            tickfont=dict(color=BLANC, size=9),
            x=1.02,
        ),
    ))

    fig.update_layout(
        **_layout(
            title="",
            xaxis=dict(
                title="Période de développement",
                tickfont=dict(color=GRIS, size=9),
                showgrid=False,
            ),
            yaxis=dict(
                tickfont=dict(color=BLANC, size=9),
                showgrid=False,
                autorange='reversed',
            ),
            annotations=[dict(
                text=f"Triangle {n}×{m}",
                xref='paper', yref='paper',
                x=0.99, y=1.02,
                showarrow=False,
                font=dict(color=OR, size=10),
            )],
        )
    )
    return fig


# =============================================================================
#  G2 — COURBES DE CADENCE CUMULÉES PAR ANNÉE
# =============================================================================

def g2_cadences_developpement(
    C:              np.ndarray,
    facteurs_cum:   List[float],
    pct_dev:        List[float],
) -> 'go.Figure':
    """
    Courbes de développement cumulé par année de survenance.
    Style identique à l'image fournie (ligne par ligne, fond sombre).

    Montre la cadence normalisée (fraction développée) par période.
    La dernière année inclut la projection (pointillés).
    """
    if not PLOTLY_OK:
        return None
    n, m = C.shape

    fig = go.Figure()

    for i in range(n):
        color = COULEURS_ANNEES[i % len(COULEURS_ANNEES)]
        k_i   = min(n - i - 1, m - 1)   # dernière colonne connue

        # Cadence connue
        x_known, y_known = [], []
        for j in range(k_i + 1):
            if C[i, j] > 0 and C[i, k_i] > 0:
                x_known.append(f"{(j+1)*12}M")
                y_known.append(round(C[i, j] / C[i, k_i] * pct_dev[i], 4))

        if x_known:
            fig.add_trace(go.Scatter(
                x=x_known, y=y_known,
                mode='lines+markers',
                line=dict(color=color, width=2),
                marker=dict(size=4, color=color),
                name=f"An. {i}",
                legendgroup=f"An. {i}",
                hovertemplate=(
                    f"<b>Année {i}</b><br>"
                    "Développement : %{x}<br>"
                    "Fraction dev. : <b>%{y:.1%}</b><extra></extra>"
                ),
            ))

        # Projection (pointillés)
        if k_i < m - 1 and pct_dev[i] < 0.99:
            x_proj = [f"{(k_i+1)*12}M"]
            y_proj = [round(pct_dev[i], 4)]
            for j2 in range(k_i + 1, m):
                cum_j2 = float(np.prod([facteurs_cum[j3]
                                        for j3 in range(k_i, j2)]
                                       if j2 > k_i else [1.0]))
                x_proj.append(f"{(j2+1)*12}M")
                y_proj.append(round(min(pct_dev[i] * cum_j2, 1.0), 4))

            fig.add_trace(go.Scatter(
                x=x_proj, y=y_proj,
                mode='lines',
                line=dict(color=color, width=1.5, dash='dot'),
                showlegend=False,
                legendgroup=f"An. {i}",
                hovertemplate=(
                    f"<b>Année {i} (proj.)</b><br>"
                    "Développement : %{x}<br>"
                    "Fraction dev. : <b>%{y:.1%}</b><extra></extra>"
                ),
            ))

    # Masquer les traces au-delà de 10 pour éviter le chevauchement légende
    for i, trace in enumerate(fig.data):
        if i >= 10:
            trace.visible = 'legendonly'

    fig.update_layout(
        **_layout(
            title="",
            margin=dict(l=60, r=160, t=50, b=50),
            xaxis=dict(
                title="Période de développement",
                tickfont=dict(color=GRIS, size=9),
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
                tickangle=-30,
            ),
            yaxis=dict(
                title="Fraction développée",
                tickfont=dict(color=GRIS, size=10),
                tickformat='.0%',
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
                range=[0, 1.08],
            ),
            legend=dict(
                bgcolor='rgba(11,35,62,0.9)',
                bordercolor='rgba(201,168,76,0.4)',
                borderwidth=1,
                font=dict(color=BLANC, size=8),
                orientation='v',
                yanchor='top', y=1.0,
                xanchor='left', x=1.01,
                tracegroupgap=2,
            ),
            height=420,
        )
    )
    return fig


# =============================================================================
#  G3 — FACTEURS DE DÉVELOPPEMENT CL ±2σ
# =============================================================================

def g3_facteurs_cl(n3: Dict) -> 'go.Figure':
    """
    Facteurs de développement CL avec bande ±2σ.
    Coloration : vert si dans σ, ambre si dans 2σ, rouge si outlier.
    """
    if not PLOTLY_OK:
        return None
    facteurs = n3.get('chain_ladder', {}).get('facteurs', [])
    if not facteurs:
        return None

    f_arr = np.array(facteurs, dtype=float)
    moy   = float(np.mean(f_arr))
    std   = float(np.std(f_arr))
    x     = [f"j→{j+1}" for j in range(len(facteurs))]

    colors = [
        ROUGE if abs(f - moy) > 2 * std else
        AMBRE if abs(f - moy) > std else
        BLEU
        for f in facteurs
    ]

    fig = go.Figure()

    # Bande ±2σ (fond)
    x_fill = list(range(len(facteurs)))
    fig.add_trace(go.Scatter(
        x=x_fill + x_fill[::-1],
        y=[moy + 2*std]*len(x_fill) + [moy - 2*std]*len(x_fill),
        fill='toself',
        fillcolor='rgba(201,168,76,0.08)',
        line=dict(color='rgba(0,0,0,0)'),
        name='±2σ',
        showlegend=True,
    ))

    # Bande ±1σ
    fig.add_trace(go.Scatter(
        x=x_fill + x_fill[::-1],
        y=[moy + std]*len(x_fill) + [moy - std]*len(x_fill),
        fill='toself',
        fillcolor='rgba(201,168,76,0.15)',
        line=dict(color='rgba(0,0,0,0)'),
        name='±1σ',
        showlegend=True,
    ))

    # Barres facteurs
    fig.add_trace(go.Bar(
        x=x, y=list(facteurs),
        marker_color=colors,
        marker_line=dict(color=NAVY, width=1),
        width=0.5,
        name='Facteurs CL',
        text=[f"{f:.4f}" for f in facteurs],
        textposition='outside',
        textfont=dict(color=BLANC, size=9),
        hovertemplate=(
            "<b>Transition %{x}</b><br>"
            "Facteur : <b>%{y:.5f}</b><extra></extra>"
        ),
    ))

    # Ligne moyenne
    fig.add_hline(
        y=moy,
        line_color=OR, line_dash='dash', line_width=1.5,
        annotation_text=f"Moy = {moy:.4f}",
        annotation_font=dict(color=OR, size=10),
        annotation_position='top right',
    )

    fig.update_layout(
        **_layout(
            title="",
            xaxis=dict(
                title="Transition de développement",
                tickfont=dict(color=GRIS, size=9),
                showgrid=False,
            ),
            yaxis=dict(
                title="Facteur f_j",
                tickfont=dict(color=GRIS, size=10),
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
            ),
            showlegend=True,
            legend=dict(
                bgcolor='rgba(15,46,82,0.8)',
                font=dict(color=BLANC, size=9),
            ),
            barmode='overlay',
        )
    )
    return fig
# =============================================================================
#  G4 — RÉSERVE PAR ANNÉE DE SURVENANCE  (fusion g4 + g11, lot C3b)
# =============================================================================

def g4_reserve_par_annee(n3: Dict) -> 'go.Figure':
    """
    Combien reste-t-il à payer, par année de survenance — et avec quelle
    incertitude.

    ⚠️ CE GRAPHIQUE EN REMPLACE DEUX, ET RÉPARE UN DÉFAUT DATÉ.
    `g4_ibnr_par_annee` et `g11_ultimates_vs_diagonale` répondaient à la même
    question. Ils sont fondus ici, et le graphique porte en plus
    `mack['sigma_par_annee']` — qui existait, et n'était affiché nulle part.

    ⚠️ L'IBNR EST SIGNÉ. L'ancien g4 traçait `max(v, 0)` avec un commentaire
    qui reportait la correction « au chantier rapport » : une année en reprise
    (recours, subrogation) s'affichait à ZÉRO, et le cumul tracé DÉPASSAIT la
    réserve — mesuré 1 483 affiché contre 1 076 réels sur un triangle à
    recours. Une reprise descend maintenant sous l'axe, à sa valeur.

    La courbe de cumul a disparu avec le plafonnement : elle ne disait rien
    qu'un total ne dise mieux, et c'est elle qui était fausse.

    `payé à date + IBNR == ultime` exactement, pour les trois méthodes —
    vérifié sur les cinq triangles de référence.
    """
    if not PLOTLY_OK:
        return None
    cl     = n3.get('chain_ladder', {})
    ibnr   = [float(v) for v in (cl.get('ibnr_par_annee') or [])]
    diag   = [float(v) for v in (cl.get('last_diagonale') or [])]
    if not ibnr or not diag:
        return None

    n      = len(ibnr)
    labels = [f"An. {i}" for i in range(n)]
    sigma  = [float(v) for v in
              (n3.get('mack', {}).get('sigma_par_annee') or [])][:n]
    sigma  = sigma + [0.0] * (n - len(sigma))
    max_v  = max((abs(v) for v in ibnr), default=0.0) or 1.0

    # Dégradé Or → Rouge sur la MAGNITUDE ; une reprise prend une teinte
    # distincte, parce qu'un IBNR négatif n'est pas un petit IBNR.
    couleurs = [
        ('rgba(26,188,156,0.85)' if v < 0 else
         f'rgba({int(201 + 46*(abs(v)/max_v))},'
         f'{int(168 - 168*(abs(v)/max_v))},'
         f'{int(76 - 76*(abs(v)/max_v))},0.85)')
        for v in ibnr
    ]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels, y=ibnr,
        marker_color=couleurs,
        marker_line=dict(color=NAVY, width=0.5),
        name='IBNR (Chain Ladder)',
        error_y=dict(type='data', array=sigma, visible=True,
                     color=BLANC, thickness=1.2, width=4),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "IBNR : <b>%{y:,.0f} €</b><br>"
            "σ Mack : <b>%{error_y.array:,.0f} €</b><extra></extra>"
        ),
    ))

    fig.add_trace(go.Scatter(
        x=labels, y=diag,
        mode='lines+markers',
        line=dict(color=BLANC, width=1.5, dash='dot'),
        marker=dict(size=6, color=BLANC, symbol='diamond'),
        name='Payé à date',
        hovertemplate=("<b>%{x}</b><br>"
                       "Payé à date : <b>%{y:,.0f} €</b><extra></extra>"),
    ))

    # Les ultimes par méthode — ce que g11 apportait, garde `disponible`
    # comprise (lot C3a) : une méthode non calculée n'est pas une ligne à zéro.
    for cle_n3, cle_meth, lbl, clr in (
            ('chain_ladder', 'chain_ladder',         'Ultime Chain Ladder', BLEU),
            ('bf',           'bornhuetter_ferguson', 'Ultime BF',           VERT),
            ('cape_cod',     'cape_cod',             'Ultime Cape Cod',     VIOLET)):
        if not disponible(n3, cle_meth):
            continue
        ult = [float(v) for v in (n3.get(cle_n3, {}).get('ultimates') or [])]
        if not ult:
            continue
        fig.add_trace(go.Scatter(
            x=labels, y=ult,
            mode='lines+markers',
            line=dict(color=clr, width=2),
            marker=dict(size=5, color=clr),
            name=lbl,
            hovertemplate=(f"<b>%{{x}} — {lbl}</b><br>"
                           "Ultime : <b>%{y:,.0f} €</b><extra></extra>"),
        ))

    fig.update_layout(
        **_layout(
            height=440,
            title="",
            xaxis=dict(
                title="Année de survenance",
                tickfont=dict(color=GRIS, size=9),
                tickangle=-30 if n > 10 else 0,
                showgrid=False,
            ),
            yaxis=dict(
                title="Montant (€) — IBNR ± σ Mack, et niveaux",
                tickfont=dict(color=GRIS, size=9),
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
                zeroline=True,
                zerolinecolor='rgba(255,255,255,0.25)',
            ),
            legend=dict(
                bgcolor='rgba(11,35,62,0.85)',
                bordercolor='rgba(201,168,76,0.3)',
                borderwidth=1,
                font=dict(color=BLANC, size=9),
                orientation='h',
                yanchor='bottom', y=1.01,
                xanchor='right', x=1,
            ),
            barmode='group',
        )
    )
    return fig


# =============================================================================
#  G5 — CONVERGENCE DES MÉTHODES
# =============================================================================

def g5_convergence_methodes(n3: Dict, n4: Dict) -> 'go.Figure':
    """
    Convergence des méthodes actuarielles + BE S2 + IC Mack.
    Les méthodes incluses vs exclues sont visuellement différenciées.
    """
    if not PLOTLY_OK:
        return None

    methodes_incluses = n4.get('methodes_incluses', [])
    methodes_exclues  = n4.get('methodes_exclues',  [])
    be                = n4.get('best_estimate', 0)
    be_mack           = n3['mack']['reserve_best_estimate']
    sigma             = n3['mack']['sigma_total']

    fig = go.Figure()

    # Méthodes incluses (couleurs vives)
    couleurs_inc = [BLEU, CYAN, VERT, VIOLET]
    for idx, m in enumerate(methodes_incluses):
        r = reserve(n3, m)
        if r is None:                 # ceinture : N4 n'inclut jamais une
            continue                  # méthode non calculée (cf. `reserve`)
        c = couleurs_inc[idx % len(couleurs_inc)]
        w = n4.get('poids', {}).get(m, 0)
        fig.add_trace(go.Bar(
            x=[libelle(m)], y=[r],
            name=f"{libelle(m)} ({w:.0%})",
            marker_color=c,
            marker_line=dict(color=NAVY, width=1),
            width=0.45,
            text=[f"{r:,.0f}€"],
            textposition='outside',
            textfont=dict(color=BLANC, size=9),
            hovertemplate=(
                f"<b>{libelle(m)}</b><br>"
                f"Réserve : <b>%{{y:,.0f}} €</b><br>"
                f"Poids BE : {w:.0%}<extra></extra>"
            ),
        ))

    # Méthodes exclues (grisées)
    for m in methodes_exclues:
        r = reserve(n3, m)
        if r is None:
            # ⚠️ LE FAUX ZÉRO (lot C3a). `res_map.get(m, 0)` dessinait une
            # barre à 0 € étiquetée « 0€ » pour une méthode qu'on n'a PAS PU
            # calculer faute d'exposition. Une méthode exclue mais CALCULÉE
            # reste tracée, grisée : c'est une information. Une méthode
            # absente n'a pas de barre.
            continue
        fig.add_trace(go.Bar(
            x=[libelle(m)], y=[r],
            name=f"{libelle(m)} (exclu)",
            marker_color='rgba(138,154,176,0.35)',
            marker_line=dict(color=GRIS, width=1),
            width=0.45,
            text=[f"{r:,.0f}€"],
            textposition='outside',
            textfont=dict(color=GRIS, size=9),
            hovertemplate=(
                f"<b>{libelle(m)} — EXCLU</b><br>"
                f"Réserve : <b>%{{y:,.0f}} €</b><extra></extra>"
            ),
        ))

    # BE S2 (barre distincte, orange vif)
    fig.add_trace(go.Bar(
        x=['Best Estimate S2'], y=[be],
        name='BE S2',
        marker_color=OR,
        marker_line=dict(color=BLANC, width=1),
        width=0.55,
        text=[f"<b>{be:,.0f}€</b>"],
        textposition='outside',
        textfont=dict(color=OR, size=11),
        hovertemplate=(
            "<b>Best Estimate S2 (Art. 77)</b><br>"
            "BE : <b>%{y:,.0f} €</b><extra></extra>"
        ),
    ))

    # IC Mack (ligne d'erreur sur Mack)
    fig.add_trace(go.Scatter(
        x=['Mack 1993', 'Mack 1993'],
        y=[max(be_mack - sigma, 0), be_mack + sigma],
        mode='lines+markers',
        line=dict(color=BLANC, width=2, dash='dot'),
        marker=dict(size=8, color=BLANC, symbol='line-ew-open'),
        name='±σ Mack',
    ))

    # Ligne BE
    fig.add_hline(
        y=be,
        line_color=OR, line_dash='dash', line_width=2,
        annotation_text=f"BE S2 = {be:,.0f} €",
        annotation_font=dict(color=OR, size=11),
        annotation_position='top left',
    )

    fig.update_layout(
        **_layout(
            title="",
            xaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
            yaxis=dict(
                title="Réserve IBNR (€)",
                tickfont=dict(color=GRIS, size=10),
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
            ),
            showlegend=True,
            legend=dict(
                bgcolor='rgba(15,46,82,0.8)',
                bordercolor=OR,
                borderwidth=0.5,
                font=dict(color=BLANC, size=9),
                orientation='h',
                yanchor='bottom', y=1.01,
                xanchor='left', x=0,
            ),
            barmode='group',
        )
    )
    return fig


# =============================================================================
#  G6 — DISTRIBUTION BOOTSTRAP ODP
# =============================================================================

def g6_distribution_bootstrap(n3: Dict, n2: Optional[Dict] = None) -> 'go.Figure':
    """
    Histogramme de la distribution Bootstrap ODP avec :
    · P50 (médiane) · P75 · P90 · P99.5
    · Zone IC 95% surlignée
    · Courbe KDE superposée
    """
    if not PLOTLY_OK:
        return None
    boot = n3.get('bootstrap', {})
    dist = boot.get('distribution', [])
    if not dist or len(set([round(v, -3) for v in dist])) < 5:
        return None

    arr = np.array(dist)
    fig = go.Figure()

    # Zone IC 95%
    ic_inf = boot.get('ic_95_inf', np.percentile(arr, 2.5))
    ic_sup = boot.get('ic_95_sup', np.percentile(arr, 97.5))
    fig.add_vrect(
        x0=ic_inf, x1=ic_sup,
        fillcolor='rgba(55,138,221,0.08)',
        line_width=0,
        annotation_text="IC 95%",
        annotation_font=dict(color=BLEU, size=9),
        annotation_position='top left',
    )

    # Histogramme
    fig.add_trace(go.Histogram(
        x=dist,
        nbinsx=60,
        marker_color='rgba(201,168,76,0.65)',
        marker_line=dict(color=NAVY, width=0.3),
        name=f'{boot.get("n_simulations", len(dist)):,} simulations',
        hovertemplate="Réserve : <b>%{x:,.0f} €</b><br>Fréquence : <b>%{y}</b><extra></extra>",
    ))

    # Percentiles
    percentiles_config = [
        (boot.get('p50',  0), 'P50',   CYAN,  'solid',  1.5),
        (boot.get('p75',  0), 'P75',   VERT,  'dash',   1.5),
        (boot.get('p90',  0), 'P90',   AMBRE, 'dash',   2),
        # ⚠️ « P99.5 (SCR) » AU LOT C3b : un NIVEAU de réserve porte le nom
        # de son percentile, jamais celui du SCR. Le SCR de l'article 115
        # est une MARGE (3·σ·V) ; l'appeler comme un niveau faisait lire
        # 25 040 191 € pour une charge de capital publiée à 5 798 631 €.
        (boot.get('p99_5',0), 'P99.5', ROUGE, 'dash', 2.5),
    ]
    for val, lbl, clr, dash, width in percentiles_config:
        if val > 0:
            fig.add_vline(
                x=val,
                line_color=clr, line_width=width, line_dash=dash,
                annotation_text=f"<b>{lbl}</b><br>{val:,.0f}€",
                annotation_font=dict(color=clr, size=9),
                annotation_position='top right' if lbl == 'P99.5' else 'top left',
            )

    cv = (boot.get('cv_bootstrap') or 0) * 100
    # φ est un SEUL nombre pour tout le triangle — c'est l'hypothèse même du
    # modèle ODP. L'afficher seul laisse croire qu'elle est acquise ; BOOT-H3
    # sait si elle tient, et `phi_par_axe` sait où elle ne tient pas. Le
    # sous-titre est vide, et non « 0 → 0 », quand la carte n'existe pas.
    sous_titre = libelle_phi_par_axe(n2)
    fig.update_layout(
        **_layout(
            title=dict(
                text=(
                    f"Bootstrap ODP — Distribution des réserves "
                    f"({boot.get('n_simulations', len(dist)):,} simulations · "
                    f"CV={cv:.1f}% · φ={boot.get('phi') or 0:.4g})"
                    + (f"<br><span style='font-size:9px'>{sous_titre}</span>"
                       if sous_titre else '')
                ),
                font=dict(color=OR, size=12),
                x=0.01,
            ),
            xaxis=dict(
                title="Réserve IBNR simulée (€)",
                tickfont=dict(color=GRIS, size=9),
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
            ),
            yaxis=dict(
                title="Fréquence",
                tickfont=dict(color=GRIS, size=10),
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
            ),
            showlegend=True,
            legend=dict(bgcolor='rgba(15,46,82,0.8)', font=dict(color=BLANC, size=9)),
        )
    )
    return fig
# =============================================================================
#  G8 — RETIRE AU LOT C3b, REMPLACE PAR UN TABLEAU
# =============================================================================
#
# Cinq barres et une ligne de seuil. La barre ne portait QUE la correlation ;
# le seuil, la significativite et le verdict ne s'y lisaient pas. Un tableau
# porte les quatre.
#
# CE N'EST PAS UNE SUPPRESSION SECHE : `h1['details']` -- les correlations
# colonne par colonne -- n'atteignaient AUCUN livrable en dehors de ce
# graphique. `n2_hypotheses_clm.lignes_correlations_h1()` les publie desormais
# en tableau, dans l'Excel et dans le HTML.


# =============================================================================
#  G9 — H2 STABILITÉ (HEATMAP ÉCARTS FACTEURS)
# =============================================================================

def g9_h2_stabilite(C: np.ndarray, n3: Dict) -> 'go.Figure':
    """
    Heatmap des écarts facteurs individuels vs CL agrégé.
    Rouge = facteur anormalement élevé.
    Bleu  = facteur anormalement bas.
    Centre (blanc/navy) = proche du facteur CL.
    """
    if not PLOTLY_OK:
        return None
    n, m = C.shape
    fi   = n3.get('chain_ladder', {}).get('facteurs_indiv', [])
    fcl  = n3.get('chain_ladder', {}).get('facteurs', [])
    if not fi or not fcl:
        return None

    max_j = min(len(fi), 12)
    max_i = min(n, 12)
    z, text_z = [], []

    for i in range(max_i):
        row, row_t = [], []
        for j in range(max_j):
            f_ind_j = fi[j] if j < len(fi) else []
            f_cl_j  = float(fcl[j]) if j < len(fcl) and fcl[j] > 0 else 1.0
            if i < len(f_ind_j) and f_cl_j > 0:
                ecart = (f_ind_j[i] - f_cl_j) / f_cl_j * 100
                row.append(round(ecart, 1))
                row_t.append(f"{ecart:+.1f}%")
            else:
                row.append(None)
                row_t.append('')
        z.append(row)
        text_z.append(row_t)

    fig = go.Figure(go.Heatmap(
        z=z,
        text=text_z,
        texttemplate="%{text}",
        textfont=dict(color=BLANC, size=8),
        x=[f"j={j}" for j in range(max_j)],
        y=[f"i={i}" for i in range(max_i)],
        colorscale=[
            [0.0,  ROUGE],
            [0.35, AMBRE],
            [0.50, NAVY_L],
            [0.65, BLEU],
            [1.0,  VERT],
        ],
        zmid=0,
        showscale=True,
        colorbar=dict(
            title=dict(text='Écart vs CL (%)', font=dict(color=BLANC, size=9)),
            tickfont=dict(color=BLANC, size=8),
        ),
        hovertemplate=(
            "<b>Année i=%{y} — Colonne %{x}</b><br>"
            "Écart vs CL : <b>%{z:+.1f}%</b><extra></extra>"
        ),
    ))

    fig.update_layout(
        **_layout(
            title="",
            xaxis=dict(tickfont=dict(color=GRIS, size=9)),
            yaxis=dict(tickfont=dict(color=BLANC, size=9), autorange='reversed'),
        )
    )
    return fig


# =============================================================================
#  G10 — LOSS RATIO A PRIORI BF (BFCC-H4)
# =============================================================================

def g10_h3_lr_apriori(n2: Dict, n3: Dict) -> 'go.Figure':
    """
    Loss Ratio par année vs LR a priori retenu vs référence marché.

    ⚠️ LIT LE LOSS RATIO DE N3, SON UNIQUE PROPRIÉTAIRE. Ce graphique lisait
    `n2['h3_apriori_bf']`, dont le loss ratio était calculé sur la dernière
    cellule OBSERVÉE et non sur l'ultime, et pouvait provenir d'un proxy inventé
    quand aucune prime n'était fournie. Le verdict affiché est celui de BFCC-H4.

    Rend None si Bornhuetter-Ferguson n'a pas été calculée : un graphique de loss
    ratio sans loss ratio afficherait des zéros, c'est-à-dire un chiffre faux.
    """
    if not PLOTLY_OK:
        return None
    bf = n3.get('bf', {})
    if not bf.get('disponible') or bf.get('lr_apriori') is None:
        return None
    h4  = n2.get('bfcc', {}).get('hypotheses', {}).get('BFCC-H4', {})
    lr  = float(bf.get('lr_apriori') or 0.0)
    lr_ref = (h4.get('extras') or {}).get('lr_reference')
    statut = str(h4.get('statut', 'NON TESTABLE'))
    ok  = statut == 'VALIDÉE'
    src = str(bf.get('source_lr', ''))

    mu_arr = bf.get('mu_par_annee', [])
    ult_bf = bf.get('ultimates', [])

    n = max(len(mu_arr), 1)
    x = [f"Année {i}" for i in range(n)]

    fig = go.Figure()

    # Barres LR implicite BF par année (ultime BF / mu)
    if mu_arr and ult_bf:
        lr_impl = [
            float(u)/float(m)*lr if m > 0 else 0
            for u, m in zip(ult_bf, mu_arr)
        ]
        fig.add_trace(go.Bar(
            x=x, y=[v*100 for v in lr_impl],
            name='LR implicite BF',
            marker_color=[VERT if 0.5 < v < 1.5 else AMBRE for v in lr_impl],
            marker_line=dict(color=NAVY, width=1),
            width=0.4,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "LR implicite : <b>%{y:.1f}%</b><extra></extra>"
            ),
        ))

    # Ligne LR a priori retenu
    fig.add_hline(
        y=lr*100,
        line_color=OR, line_dash='solid', line_width=2,
        annotation_text=f"LR a priori = {lr:.1%} ({src})",
        annotation_font=dict(color=OR, size=10),
        annotation_position='top right',
    )

    # Référence marché
    if lr_ref:
        fig.add_hline(
            y=lr_ref*100,
            line_color=GRIS, line_dash='dot', line_width=1.5,
            annotation_text=f"Réf. marché = {lr_ref:.1%}",
            annotation_font=dict(color=GRIS, size=9),
            annotation_position='bottom right',
        )

    # Plage acceptable [30%, 150%]
    fig.add_hrect(y0=30, y1=150, fillcolor='rgba(46,204,113,0.04)', line_width=0)

    fig.update_layout(
        **_layout(
            title=dict(
                text=f"Loss ratio a priori BF — BFCC-H4 {statut}",
                font=dict(color=VERT if ok else AMBRE, size=13),
                x=0.01,
            ),
            xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
            yaxis=dict(
                title="Loss Ratio (%)",
                tickfont=dict(color=GRIS, size=10),
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
                range=[0, 200],
            ),
            showlegend=True,
            legend=dict(bgcolor='rgba(15,46,82,0.8)', font=dict(color=BLANC, size=9)),
        )
    )
    return fig
# =============================================================================
#  G11 — FUSIONNE DANS G4 AU LOT C3b
# =============================================================================
#
# g4 (IBNR par annee) et g11 (ultimes vs diagonale) repondaient a la MEME
# question : combien reste-t-il a payer, par annee de survenance. Un seul
# graphique les remplace, et il porte en plus le sigma par annee de Mack --
# `mack['sigma_par_annee']`, qui existait et n'etait affiche nulle part.


# =============================================================================
#  G12 — TORNADO CHART SENSIBILITÉS
# =============================================================================

def g12_sensibilites_tornado(n4: Dict) -> 'go.Figure':
    """
    Tornado chart des sensibilités du BE.
    Montre l'impact de l'exclusion de chaque méthode et des scénarios Bootstrap.
    """
    if not PLOTLY_OK:
        return None

    be   = n4.get('best_estimate', 0)
    sens = n4.get('sensibilites', {})
    if not sens or be <= 0:
        return None

    labels, deltas_pos, deltas_neg = [], [], []
    label_map = {
        'sans_chain_ladder':         'Sans Chain Ladder',
        'sans_mack':                 'Sans Mack 1993',
        'sans_bornhuetter_ferguson': 'Sans BF',
        'sans_cape_cod':             'Sans Cape Cod',
        'boot_ic_inf':               'Boot. IC 95% inf.',
        'boot_ic_sup':               'Boot. IC 95% sup.',
        'boot_p90':                  'Bootstrap P90',
        'boot_p99_5':                'Bootstrap P99.5',
    }

    items = []
    for k, v in sens.items():
        delta  = float(v) - be
        lbl    = label_map.get(k, k.replace('_', ' ').title())
        items.append((abs(delta), lbl, delta))

    # Trier par amplitude
    items.sort(key=lambda x: x[0], reverse=True)

    for _, lbl, delta in items[:10]:
        labels.append(lbl)
        if delta >= 0:
            deltas_pos.append(delta)
            deltas_neg.append(0)
        else:
            deltas_pos.append(0)
            deltas_neg.append(delta)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=labels,
        x=deltas_pos,
        orientation='h',
        name='Impact positif',
        marker_color=ROUGE,
        marker_line=dict(color=NAVY, width=0.5),
        hovertemplate="<b>%{y}</b><br>Δ BE : <b>+%{x:,.0f} €</b><extra></extra>",
    ))

    fig.add_trace(go.Bar(
        y=labels,
        x=deltas_neg,
        orientation='h',
        name='Impact négatif',
        marker_color=BLEU,
        marker_line=dict(color=NAVY, width=0.5),
        hovertemplate="<b>%{y}</b><br>Δ BE : <b>%{x:,.0f} €</b><extra></extra>",
    ))

    # Ligne zéro (BE de référence)
    fig.add_vline(
        x=0,
        line_color=OR, line_width=1.5,
        annotation_text=f"BE = {be:,.0f}€",
        annotation_font=dict(color=OR, size=10),
    )

    fig.update_layout(
        **_layout(
            height=max(350, len(labels) * 35),
            title="",
            xaxis=dict(
                title="Variation vs BE de référence (€)",
                tickfont=dict(color=GRIS, size=9),
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
            ),
            yaxis=dict(
                tickfont=dict(color=BLANC, size=9),
                showgrid=False,
                autorange='reversed',
            ),
            barmode='overlay',
            showlegend=True,
            legend=dict(bgcolor='rgba(15,46,82,0.8)', font=dict(color=BLANC, size=9)),
        )
    )
    return fig
# =============================================================================
#  G13 — RETIRE AU LOT C3b
# =============================================================================
#
# C'etait le triangle de g1, trace en lignes au lieu d'une carte de chaleur,
# et NON NORMALISE. g2 en est la version normalisee -- la fraction developpee
# --, et c'est elle qui est informative : le guide de l'Institut des Actuaires
# la recommande nommement (p.12). Trois graphiques pour la meme matrice,
# c'etait deux de trop.


# =============================================================================
#  G14 — BACK-TESTING BONI/MALI DE LIQUIDATION
# =============================================================================

def g14_backtesting(n3: Dict, annee_debut: int = None) -> 'go.Figure':
    """
    Boni/Mali de liquidation — back-testing N-1 et N-2.
    Barres : boni en vert, mali en rouge. Seuils ±15% guide IA 2023.
    annee_debut : si fourni, affiche les vraies années calendaires en X.
    """
    if not PLOTLY_OK: return None
    bt = n3.get('backtesting', {})
    if not bt.get('success'): return None
    resultats = bt.get('resultats', {})
    if not resultats: return None

    fig = go.Figure()

    for k_str, h_data in resultats.items():
        k      = h_data['k']
        annees = h_data['annees']
        if not annees: continue

        x_vals = [
            str(annee_debut + r['annee']) if annee_debut else f"An. {r['annee']}"
            for r in annees
        ]
        ecarts_pct = [r['ecart_pct']       for r in annees]
        statuts    = [r['statut']           for r in annees]
        bm_vals    = [r['boni_mali']        for r in annees]

        bar_colors = []
        for s, e in zip(statuts, ecarts_pct):
            if s == 'ROUGE':
                bar_colors.append('rgba(192,57,43,0.85)')
            elif s == 'AMBRE':
                bar_colors.append('rgba(243,156,18,0.85)')
            else:
                bar_colors.append('rgba(39,174,96,0.85)' if e >= 0 else 'rgba(52,152,219,0.85)')

        lbl = {1:'N-1', 2:'N-2'}.get(k, f'N-{k}')
        fig.add_trace(go.Bar(
            x=x_vals, y=ecarts_pct,
            name=f'Horizon {lbl}',
            marker_color=bar_colors,
            marker_line=dict(color=NAVY, width=0.5),
            text=[f"{e:+.1f}%" for e in ecarts_pct],
            textposition='outside',
            textfont=dict(color=BLANC, size=8),
            hovertemplate=(
                "<b>%{x}</b><br>"
                f"Horizon {lbl}<br>"
                "Écart : <b>%{y:+.1f}%</b><br>"
                "Boni/Mali : <b>%{customdata:,.0f} €</b><extra></extra>"
            ),
            customdata=bm_vals,
            offsetgroup=str(k),
        ))

    fig.add_hline(y=0,   line=dict(color=BLANC, width=1))
    fig.add_hline(y=15,  line=dict(color='rgba(192,57,43,0.7)', width=1.5, dash='dash'),
                  annotation_text="+15% (seuil IA 2023)",
                  annotation_font=dict(color='rgba(192,57,43,0.9)', size=8),
                  annotation_position="top right")
    fig.add_hline(y=-15, line=dict(color='rgba(192,57,43,0.7)', width=1.5, dash='dash'),
                  annotation_text="-15% (seuil IA 2023)",
                  annotation_font=dict(color='rgba(192,57,43,0.9)', size=8),
                  annotation_position="bottom right")
    fig.add_hrect(y0=-8, y1=8, fillcolor='rgba(39,174,96,0.06)', line_width=0)

    fig.update_layout(
        **_layout(
            height=440, title="",
            margin=dict(l=60, r=80, t=30, b=60),
            xaxis=dict(title=dict(text="Année de survenance", font=dict(color=GRIS,size=10)),
                       tickfont=dict(color=BLANC,size=9), tickangle=-30, showgrid=False),
            yaxis=dict(title=dict(text="Écart % (projeté vs observé)", font=dict(color=GRIS,size=10)),
                       tickfont=dict(color=GRIS,size=9),
                       showgrid=True, gridcolor='rgba(255,255,255,0.06)',
                       ticksuffix=' %', zeroline=False),
            legend=dict(bgcolor='rgba(11,35,62,0.92)', bordercolor='rgba(201,168,76,0.5)',
                        borderwidth=1, font=dict(color=BLANC,size=9),
                        orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1),
            barmode='group', hovermode='x unified',
        )
    )
    return fig


def generer_graphiques(
    C:              np.ndarray,
    n2:             Dict,
    n3:             Dict,
    n4:             Dict,
) -> Dict:
    """
    Génère les 10 graphiques ActuarIA.

    ⚠️ ILS ÉTAIENT 14 JUSQU'AU LOT C3b. Quatre sont partis : g7 (donut SCR,
    mauvais encodage et étiquette fausse), g13 (le triangle une troisième
    fois), g8 (cinq barres remplacées par un tableau qui en dit plus), et g11
    (fondu dans g4). Chaque retrait porte sa justification à l'endroit exact
    où la fonction se trouvait.

    Parameters
    ----------
    C  : triangle cumulé
    n2 : résultats hypothèses
    n3 : résultats méthodes
    n4 : résultats best estimate

    Returns
    -------
    dict {nom: go.Figure} — chaque graphique accessible par clé.
    Deux causes d'absence, distinguées dans les logs :
      · échec réel        → absent + logger.warning
      · pas de données    → absent + listé en info (garde légitime, ex. pas
                            d'historique de back-testing, BE ≤ 0 pour le SCR)
    """
    if not PLOTLY_OK:
        logger.warning("Plotly non disponible — graphiques non générés")
        return {}

    cl       = n3.get('chain_ladder', {})
    f_cum    = cl.get('facteurs_cumules', [])
    pct_dev  = cl.get('pct_developpe', [])

    g = {}
    specs = [
        ('g1_heatmap',        lambda: g1_heatmap_triangle(C)),
        ('g2_cadences',       lambda: g2_cadences_developpement(C, f_cum, pct_dev)),
        ('g3_facteurs_cl',    lambda: g3_facteurs_cl(n3)),
        ('g4_reserve_annee',  lambda: g4_reserve_par_annee(n3)),
        ('g5_convergence',    lambda: g5_convergence_methodes(n3, n4)),
        ('g6_bootstrap',      lambda: g6_distribution_bootstrap(n3, n2)),
        ('g9_h2',             lambda: g9_h2_stabilite(C, n3)),
        ('g10_h3',            lambda: g10_h3_lr_apriori(n2, n3)),
        ('g12_sensibilites',  lambda: g12_sensibilites_tornado(n4)),
        ('g14_backtesting',    lambda: g14_backtesting(n3, annee_debut=n3.get('annee_debut_triangle'))),
    ]

    sans_donnees = []
    for nom, fn in specs:
        try:
            fig = fn()
            if fig is not None:
                g[nom] = fig
            else:
                sans_donnees.append(nom)      # garde légitime, pas un échec
        except Exception as e:
            logger.warning(f"Graphique {nom} échoué : {e}")

    if sans_donnees:
        logger.info(f"Graphiques sans données (ignorés) : {sans_donnees}")
    logger.info(f"Graphiques générés : {len(g)}/{len(specs)}")
    return g
