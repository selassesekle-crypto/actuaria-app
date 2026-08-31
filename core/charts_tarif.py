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
  • Excel / Word : image statique (kaleido) — DISPONIBLE.
    ⚠️⚠️ Constat `charts/C7` : cette ligne portait « SUIVI (kaleido absent
    aujourd'hui) ». Mesuré le 31/08/2026 : kaleido est installé en **1.3.0**,
    et `to_image(png)` rend 20 826 octets — l'image statique EST produisible.
    *Le suivi était clos, la note ne l'était pas.* ⚠️ Que l'Excel et le Word
    rendent effectivement ces images relève de LEURS services, pas d'ici :
    ce n'est pas tranché par cette ligne, et c'est dit.

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

# ════════════════════════════════════════════════════════════════════════════
# STATUT RAG — LA SOURCE UNIQUE (couleur · motif · symbole · glyphe)
# ════════════════════════════════════════════════════════════════════════════
# ⚠️⚠️ POURQUOI CE BLOC EXISTE — arbitrage 2 de la feuille de route, tranché
# le 27/08/2026. Relevé PAR AST avant d'écrire : **30 définitions locales** de
# VERT/AMBRE/ROUGE dans 7 fichiers, **7 valeurs distinctes**, et AUCUNE source.
# Rien ne pouvait vérifier ni le contraste, ni la cohérence, ni même quelle
# palette s'applique à quel fond.
#
# ⚠️ LA PALETTE NE CHANGE PAS, ET C'EST UNE DÉCISION MOTIVÉE. Remesurée sur
# les vraies valeurs de production, elle tient : 6,80 / 6,51 / 3,74 sur le fond
# des figures, 4,72 / 5,44 sur le blanc des rapports. Le défaut n'était pas
# leur valeur — c'est qu'elles n'étaient tenues par rien.
# ⚠️ Les valeurs `#FFC145` / `#E8452F` d'un arbitrage antérieur sont ÉCARTÉES :
# elles avaient été mesurées sur la table d'une SONDE D'AUDIT, pas sur la
# palette de production. *Une recommandation fondée sur la mauvaise table ne
# se recycle pas.*
#
# ⚠️⚠️ LE DÉFAUT RÉEL, MESURÉ : le VERT et l'AMBRE ont un contraste mutuel de
# **1,04** — LA MÊME LUMINANCE. Seule la teinte les sépare (108°). En niveaux
# de gris, à l'impression, ou pour qui a le canal chromatique réduit, **le
# statut VERT devient indiscernable de l'AMBRE**. Et le VERT est à **1,00**
# contre l'or des axes. *C'est la démonstration mesurée qu'un second canal est
# nécessaire — la couleur seule ne suffit pas.*

#: Le fond décide de la palette, et cette dépendance est ÉCRITE, pas implicite.
FOND_SOMBRE = 'sombre'      # figures : papier #0B1E3D / tracé #122A4F
FOND_CLAIR = 'clair'        # rapports HTML et Word : fond blanc

#: Contraste minimal EXIGÉ, par usage. WCAG 2.1 : 1.4.11 (objet non textuel)
#: = 3:1 · 1.4.3 (texte normal) = 4,5:1. Le contrôle les RECALCULE.
CONTRASTE_MIN_OBJET = 3.0
CONTRASTE_MIN_TEXTE = 4.5

#: ⚠️ Chaque couleur porte SA MESURE, et `usage_texte` dit si elle a le droit
#: de servir à écrire. ROUGE sombre est à 3,74 : il passe pour une barre,
#: il ÉCHOUE pour du texte. *Interdire l'usage vaut mieux que changer une
#: couleur qui va bien là où elle sert.*
#: ⚠️⚠️ ET L'AMBRE CLAIR EST À 2,85 — LE PLUS BAS DE LA TABLE. C'est
#: `ORANGE = '#E67E22'` des rapports, mesuré, pas choisi. Il sert de BORDURE et
#: d'accent sur des fonds pâles (`#faeeda`), jamais de couleur de texte sur
#: blanc — `usage_texte` le dit. ⚠️ J'avais d'abord écrit ici une couleur que
#: j'avais INVENTÉE (`#B9770E`, déclarée à 4,51, mesurée à 3,68) : le contrôle
#: de contraste l'a attrapée avant tout commit. *Une couleur fabriquée est une
#: valeur fabriquée, même quand elle a l'air raisonnable.*
STATUT_RAG = {
    FOND_SOMBRE: {
        'VERT':  {'couleur': '#2ECC71', 'contraste': 6.80,
                  'usage_texte': True,  'usage_objet': True},
        'AMBRE': {'couleur': '#F39C12', 'contraste': 6.51,
                  'usage_texte': True,  'usage_objet': True},
        'ROUGE': {'couleur': '#E74C3C', 'contraste': 3.74,
                  'usage_texte': False, 'usage_objet': True},
    },
    FOND_CLAIR: {
        'VERT':  {'couleur': '#1E8449', 'contraste': 4.72,
                  'usage_texte': True,  'usage_objet': True},
        # ⚠️⚠️ NON CONFORME, ET DÉCLARÉ PLUTÔT QU'AJUSTÉ : 2,85 est SOUS le
        # seuil 1.4.11 (3:1) — cette couleur ne satisfait aucun des deux
        # usages sur blanc. Elle sert de bordure et d'accent sur des fonds
        # PÂLES (`#faeeda`), où son contraste réel est autre. *On ne change
        # pas une couleur de production sans arbitrage ; on dit qu'elle ne
        # passe pas.*
        'AMBRE': {'couleur': '#E67E22', 'contraste': 2.85,
                  'usage_texte': False, 'usage_objet': False},
        'ROUGE': {'couleur': '#C0392B', 'contraste': 5.44,
                  'usage_texte': True,  'usage_objet': True},
    },
}

#: Le fond de référence de chaque palette — le contrôle recalcule contre lui.
FOND_REFERENCE = {FOND_SOMBRE: '#122A4F', FOND_CLAIR: '#FFFFFF'}

#: ⚠️ SECOND CANAL — BARRES. Une barre n'a pas de forme : son canal est le
#: MOTIF de remplissage (plotly `marker.pattern.shape`).
MOTIF_RAG = {'VERT': '', 'AMBRE': '/', 'ROUGE': 'x'}

#: ⚠️ SECOND CANAL — POINTS. `marker.symbol` : trois silhouettes distinctes.
SYMBOLE_RAG = {'VERT': 'circle', 'AMBRE': 'triangle-up', 'ROUGE': 'square'}

#: ⚠️⚠️ SECOND CANAL — TEXTE. On ADOPTE la convention déjà majoritaire plutôt
#: que d'en créer une quatrième : relevé le 27/08, **585 occurrences dans 50
#: fichiers**, et elle est réellement distincte par la FORME (coche · triangle
#: · croix). *585 sites déjà conformes valent mieux qu'une migration.*
GLYPHE_RAG = {'VERT': '✅', 'AMBRE': '⚠️', 'ROUGE': '❌'}

#: ⚠️ EXCEPTION NOMMÉE — l'Excel. `excel_helpers` utilise `✓ △ ✗` (12 sites) :
#: plus sobres, plus sûrs à l'impression, et sans dépendance à une police
#: emoji. On la CONSERVE et on la DÉCLARE ici — une exception écrite n'est pas
#: une divergence subie.
GLYPHE_RAG_EXCEL = {'VERT': '✓', 'AMBRE': '△', 'ROUGE': '✗'}

#: ⚠️⚠️ CE QUI N'EST PAS UN SECOND CANAL, ET QUI EST NOMMÉ SANS ÊTRE TRAITÉ :
#: `🟢 🟡 🔴` — relevé **230 occurrences dans 39 fichiers**. Leurs noms Unicode
#: le disent : LARGE GREEN CIRCLE · LARGE YELLOW CIRCLE · LARGE RED CIRCLE.
#: **Trois cercles identiques** : c'est la COULEUR SEULE, sous forme de rond.
#: En niveaux de gris, ils sont indiscernables. *C'est un chantier à part — il
#: touche 39 fichiers dont l'app et d'autres directions.* NON OUVERT.
GLYPHES_SANS_SECOND_CANAL = ('🟢', '🟡', '🔴')


def _luminance(hexa: str) -> float:
    """Luminance relative WCAG 2.1 d'une couleur `#RRGGBB` ou `RRGGBB`."""
    h = hexa.lstrip('#')
    canaux = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
           for c in canaux]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(hexa: str, fond: str) -> float:
    """Rapport de contraste WCAG entre deux couleurs. ⚠️ CALCULÉ, jamais
    recopié : c'est ce qui permet au contrôle de RE-mesurer ce qui est déclaré.
    """
    a, b = _luminance(hexa), _luminance(fond)
    return round((max(a, b) + 0.05) / (min(a, b) + 0.05), 2)


def couleur_rag(statut: str, fond: str = FOND_SOMBRE, *, avec_diese: bool = True):
    """La couleur d'un statut sur un fond donné — ou `None` si inconnu.

    ⚠️ `None` plutôt qu'une couleur par défaut : un statut non reconnu ne doit
    pas se peindre comme un autre. *Une valeur de repli serait indiscernable
    d'une valeur mesurée.*
    """
    entree = STATUT_RAG.get(fond, {}).get(str(statut).upper())
    if entree is None:
        return None
    return entree['couleur'] if avec_diese else entree['couleur'].lstrip('#')


def couleur_texte_rag(statut: str, fond: str = FOND_SOMBRE) -> str:
    """La couleur d'un statut QUAND ELLE SERT À ÉCRIRE.

    ⚠️⚠️ AUCUN TEXTE EN ROUGE, NULLE PART — arbitré par Selasse le 27/08/2026,
    sans exception ni cas par cas. `ROUGE #E74C3C` vaut **3,74** sur le fond
    des figures : il passe comme OBJET (WCAG 1.4.11, 3:1) et échoue comme
    TEXTE (1.4.3, 4,5:1).

    ⚠️ CETTE FONCTION NE BLANCHIT PAS TOUT. Le VERT (6,80) et l'AMBRE (6,51)
    sont parfaitement lisibles : ils gardent leur couleur, donc leur signal.
    Seul un statut dont la couleur échoue au seuil bascule vers le texte de la
    charte (**12,93**). *On retire ce qui n'est pas lisible, pas ce qui porte
    du sens.*

    ⚠️ ET LE SENS DU ROUGE NE SE PERD PAS : partout où cette fonction
    s'applique, le glyphe `❌` et/ou le mot « ROUGE » figurent déjà dans le
    texte affiché. Le second canal porte l'information que la couleur ne peut
    plus porter.

    ⚠️ Les deux voies alternatives ont été ÉCARTÉES PAR LA MESURE, pas par
    goût : `#C0392B` (le rouge des rapports) tombe à **2,63** sur ce fond —
    pire que l'actuel — et inventer un rouge plus clair serait fabriquer une
    couleur.
    """
    entree = STATUT_RAG.get(fond, {}).get(str(statut).upper())
    if entree is not None and entree['usage_texte']:
        return entree['couleur']
    return COULEURS['texte']


def glyphe_rag(statut: str, *, cible: str = 'texte') -> str:
    """Le glyphe du statut. `cible='excel'` rend l'exception nommée."""
    table = GLYPHE_RAG_EXCEL if cible == 'excel' else GLYPHE_RAG
    return table.get(str(statut).upper(), '')


# ══════════════════════════════════════════════════════════════════════════════
# GRADIENT DES BARRES ORDONNÉES — MONOTONE EN LUMINANCE, PAR CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════════
# ⚠️⚠️ CONSTAT `charts/C9` : DEUX DÉCILES DIFFÉRENTS SE LISAIENT PAREIL.
# L'ancre médiane était un TURQUOISE de luminance **0,3854** — plus CLAIR que
# les deux extrémités (0,1269 et 0,2514). La rampe montait jusqu'à D5 puis
# redescendait : **4 inversions**, et D8/D9 séparés de **0,0035**.
# *Une échelle ORDONNÉE doit être monotone, sinon le rang cesse d'être lisible.*
#
# ⚠️ LES DEUX EXTRÉMITÉS NE CHANGENT PAS : elles portent le sens (bleu = bas
# risque, orange = haut). Seule l'ancre médiane bouge, et vers une luminance
# COMPRISE entre les deux — c'est la condition de la monotonie, pas un goût.
#
# ⚠️⚠️ ET LE REMÈDE N'EST PAS L'ANCRE, C'EST L'ÉCHANTILLONNAGE. Une ancre
# monotone ne suffit pas : l'interpolation est linéaire en RGB, pas en
# luminance, donc les pas restent inégaux (mesuré : écart minimal 0,0044 avec
# la bonne ancre mais un échantillonnage régulier en `t`). `_gradient_ordonne`
# échantillonne désormais à LUMINANCE RÉGULIÈRE — 0 inversion et écart minimal
# **0,0109**, contre 0,0035 avant, pour un maximum théorique de 0,0138.
_GRAD_ANCRES = [
    (0.0, (30, 100, 180)),   # bas  — bleu profond      · luminance 0,1269
    (0.5, (150, 95, 185)),   # mid  — violet            · luminance 0,1817
    (1.0, (240, 85, 35)),    # haut — orange danger     · luminance 0,2514
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


def _luminance_rgba(couleur: str) -> float:
    """Luminance relative WCAG d'une chaîne `rgba(r,g,b,a)` — l'alpha est ignoré.

    ⚠️ Parsé sans `re` À DESSEIN : l'en-tête de ce module promet qu'il ne
    dépend que de plotly et numpy. Ajouter un import pour trois entiers
    rendrait cette phrase moins vraie pour rien.
    """
    r, g, b = (int(v) for v in
               couleur.split('(', 1)[1].split(')', 1)[0].split(',')[:3])
    return _luminance(f'#{r:02X}{g:02X}{b:02X}')


def _gradient_ordonne(n: int) -> List[str]:
    """n couleurs bas → haut, à LUMINANCE RÉGULIÈREMENT ESPACÉE.

    ⚠️⚠️ CONSTAT `charts/C9`. Échantillonner régulièrement en `t` laissait des
    pas de luminance INÉGAUX — deux déciles voisins séparés de 0,0035 se
    lisent pareil. On inverse donc la question : au lieu de prendre des `t`
    réguliers et de subir les luminances, on VISE des luminances régulières et
    on cherche le `t` correspondant.

    ⚠️ Ce n'est possible que parce que `_GRAD_ANCRES` est monotone en
    luminance — la recherche par dichotomie suppose une fonction croissante.
    Un test épingle les deux propriétés ENSEMBLE : monotonie des ancres, et
    régularité du pas obtenu.

    Mesuré sur 10 déciles : **0 inversion, écart minimal 0,0109** (avant :
    4 inversions, 0,0035 ; maximum théorique atteignable 0,0138).
    """
    if n <= 1:
        return [_couleur_gradient(0.5)]
    bas = _luminance_rgba(_couleur_gradient(0.0))
    haut = _luminance_rgba(_couleur_gradient(1.0))

    def _t_pour(cible: float) -> float:
        """Le `t` dont la couleur atteint cette luminance — par dichotomie."""
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2.0
            if _luminance_rgba(_couleur_gradient(mid)) < cible:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    return [_couleur_gradient(_t_pour(bas + (haut - bas) * i / (n - 1)))
            for i in range(n)]


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


def _declarer_assiette(fig: go.Figure, *, fournis: int, traces: int,
                       quoi: str) -> go.Figure:
    """Écrit SUR LA FIGURE ce qu'elle ne montre pas — vide, ou tronquée.

    ⚠️⚠️ DEUX CONSTATS, UNE SEULE PROPRIÉTÉ. `charts/C3` : les sept fonctions
    rendaient un objet COMPLET — fond navy, titre or, axes titrés, bande verte
    — avec **zéro point tracé**, et aucune ne le disait : *une figure vide
    était visuellement indiscernable d'une figure pleine.* `charts/C5` : trois
    troncatures silencieuses, mesurées — relativités **23 → 15**, SHAP
    **30 → 15**, walk-forward **4 fenêtres fournies → 2 tracées** quand deux
    n'ont pas de A/E.

    *Dans les deux cas le lecteur ne peut pas savoir que quelque chose manque.*

    ⚠️ ON N'ÉLARGIT PAS LA TRONCATURE, ON LA DÉCLARE. Tracer 23 relativités
    rendrait la figure illisible — le `top=15` est un choix de lisibilité
    défendable. Ce qui ne l'est pas, c'est qu'il soit MUET.

    ⚠️ ET LE CAS (c) DU RELEVÉ N'EST PAS REPRODUIT : `chart_distribution_
    predictions` trace bien **1 000 valeurs sur 1 000**, il ne coupe pas à 500.
    *Un sous-cas qui ne se reproduit pas se déclare, il ne se corrige pas.*
    """
    if traces <= 0:
        # RIEN à montrer : l'annonce va AU CENTRE, en badge — elle doit être
        # impossible à manquer, c'est tout l'objet du constat.
        fig.add_annotation(
            x=0.5, y=0.5, xref='paper', yref='paper',
            text=f'<b>AUCUNE DONNÉE — {quoi}</b>',
            showarrow=False, xanchor='center', yanchor='middle',
            font={'family': POLICE, 'color': COULEURS['texte'], 'size': 13},
            bgcolor=BADGE['fond'], bordercolor=BADGE['bordure'],
            borderwidth=2, borderpad=8,
        )
    elif traces < fournis:
        # TRONQUÉE : la figure reste lisible, la mention va SOUS l'axe pour ne
        # pas recouvrir ce qui, lui, est bien tracé.
        fig.add_annotation(
            x=0.5, y=-0.16, xref='paper', yref='paper',
            text=(f'{traces} {quoi} sur {fournis} — les {fournis - traces} '
                  f'autres ne sont pas tracées'),
            showarrow=False, xanchor='center', yanchor='top',
            font={'family': POLICE, 'color': COULEURS['texte_2'], 'size': 11},
        )
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
    """Inverse de la CDF normale (Acklam) — numpy pur, sans scipy.

    ⚠️⚠️ CONSTAT `charts/C6` — LA PROMESSE ÉTAIT TENUE, MAIS PAS CELLE QUI
    ÉTAIT ÉCRITE. Cette docstring annonçait « *|err| < 1.2e-9* » sans dire de
    QUELLE erreur il s'agissait. Mesuré sur **405 003 points** contre
    `scipy.stats.norm.ppf` :

        erreur RELATIVE : 1,129e-09 partout        <- la promesse d'Acklam
        erreur ABSOLUE  : jusqu'a 5,621e-09        <- x 4,7 l'annonce

    **L'algorithme est correct et bien transcrit** : Acklam publie une erreur
    RELATIVE de 1,15e-9, et l'implémentation atteint 1,129e-9. *C'était le mot
    manquant qui rendait le chiffre faux — pas le calcul.*

    Erreur **relative** < 1,15e-9 (borne d'Acklam), sur tout le domaine.
    """
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
    _declarer_assiette(fig, fournis=len(vals), traces=len(vals),
                       quoi='déciles')
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
        if gini_modele is not None:
            mod = float(gini_modele)
            texte += f'<br>Modèle {mod:.4f}'
            # ⚠️⚠️ CONSTAT `charts/C1` — LE BADGE N'AVAIT AUCUNE BORNE. Il
            # écrivait `100 * mod / obs` sous le seul garde `obs > 0`. Mesuré :
            #     obs=0,2000  mod=0,2500  ->  « 125 % du discriminable »
            #     obs=0,2000  mod=-0,0105 ->  « -5 % du discriminable »
            #     obs=1e-6    mod=0,1800  ->  « 18 000 000 % du discriminable »
            #
            # ⚠️ ON N'ÉCRÊTE PAS À [0, 100], ET C'EST LA LEÇON DU LOT F1 D'A7 :
            # juger une valeur écrêtée est une tautologie, et l'écrêtement
            # CACHE la divergence au lieu de la dire. Le 125 % n'est pas une
            # aberration de calcul — la docstring l'explique : « le plafond est
            # calculé sur le portefeuille entier, le Gini du modèle sur la
            # seule base de test ». *Deux assiettes différentes.*
            #
            # ⚠️⚠️ UNE SEULE CONDITION COUVRE LES TROIS CAS, et elle n'invente
            # AUCUN SEUIL : le rapport n'est une PART que si `0 <= mod <= obs`.
            #   mod < 0    -> le modèle discrimine à l'envers
            #   obs <= 0   -> il n'y a pas de plafond à rapporter
            #   mod > obs  -> les deux Gini n'ont pas la même assiette
            # *Un seuil fabriqué ici aurait été le défaut que cet audit
            # poursuit ; la condition, elle, est la définition d'une part.*
            if mod < 0:
                texte += ('<br><i>part du discriminable non publiée — '
                          'le modèle discrimine à l\'envers</i>')
            elif obs <= 0:
                texte += ('<br><i>part du discriminable non publiée — '
                          'aucun plafond observé à rapporter</i>')
            elif mod > obs:
                texte += ('<br><i>part du discriminable non publiée — le '
                          'modèle dépasse le plafond : les deux Gini n\'ont '
                          'pas la même assiette</i>')
            else:
                texte += f' — soit {100.0 * mod / obs:.0f} % du discriminable'
        _badge_kpi(fig, texte)
    _declarer_assiette(fig, fournis=len(xs), traces=len(xs),
                       quoi='points de la courbe')
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
    _declarer_assiette(fig, fournis=len(relativites), traces=len(items),
                       quoi='variables')
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 4. WALK-FORWARD A/E — bandes ±15 %, seuils ACPR
# ════════════════════════════════════════════════════════════════════════════
def chart_walkforward_ae(
    fenetres: Sequence[Dict],
    *,
    bande_acceptable: tuple,
    bande_stricte: tuple,
    titre: str = 'Backtesting walk-forward — ratio A/E par fenêtre',
) -> go.Figure:
    """
    fenetres : [{'annee'|'annee_test': …, 'ae_ratio': …}] — une par fenêtre WF.
    bande_acceptable / bande_stricte : les DEUX bandes, fournies par l'appelant.

    ⚠️⚠️ CETTE FIGURE NE POSSÈDE PLUS AUCUN SEUIL, ET C'EST LE FOND DU CONSTAT
    `charts/C2`. Elle en portait TROIS, et le plus visible était le plus large :

        rectangle vert dessiné ici       0,85 – 1,15   <- le plus LARGE
        point VERT dessiné ici           0,95 – 1,05
        le verrou qui plafonne le statut 0,90 – 1,10   <- la DÉCISION

    Mesuré : un A/E de **0,87** se dessinait DANS la bande verte, et le verrou
    avertissait. *La figure promettait une acceptabilité que la règle refusait,
    et c'est la figure que l'actuaire regarde en premier.*

    ⚠️ LE REMÈDE N'EST PAS DE RECOPIER LE BON NOMBRE ICI — une copie correcte
    aujourd'hui diverge au premier ajustement, exactement comme les 30
    définitions locales de couleurs avant `STATUT_RAG`. La figure REÇOIT les
    bornes de qui décide (`core.conformite_reglementaire`), et n'en invente
    aucune.

    ⚠️ LES DEUX BANDES SONT REQUISES, sans défaut. Un défaut laisserait un
    appelant dessiner une bande qui n'est plus celle de la règle, en silence.
    *« Présent mais VIDE » a déjà mordu trois fois dans cet audit.*

    ⚠️ ET LE MODULE RESTE PUR : il ne dépend toujours que de plotly et numpy.
    C'est pourquoi les bornes arrivent en PARAMÈTRE plutôt que par un import —
    la dépendance irait dans le bon sens (la présentation lit la règle), mais
    elle rendrait fausse la phrase d'en-tête qui promet la pureté.
    """
    bas_a, haut_a = float(bande_acceptable[0]), float(bande_acceptable[1])
    bas_s, haut_s = float(bande_stricte[0]), float(bande_stricte[1])
    # ⚠️ UNE FENÊTRE SANS A/E N'EST PAS UNE FENÊTRE À 1,0. Le défaut `1.0`
    # aurait tracé un point PARFAIT là où rien n'a été mesuré — et depuis
    # qu'A6 publie `None` pour une fenêtre dont le modèle n'a pu être
    # recalibré, `float(None)` aurait de toute façon levé. Ces fenêtres
    # sortent du tracé ; le graphique montre ce qui a été mesuré.
    _mesurees = [f for f in fenetres if f.get('ae_ratio') is not None]
    annees = [f.get('annee', f.get('annee_test')) for f in _mesurees]
    ae = [float(f['ae_ratio']) for f in _mesurees]

    def _statut(v: float) -> str:
        """Le statut RAG d'une fenêtre. ⚠️ Les seuils viennent de l'appelant."""
        if bas_s <= v <= haut_s:
            return 'VERT'
        if bas_a <= v <= haut_a:
            return 'AMBRE'
        return 'ROUGE'

    fig = go.Figure()
    # ⚠️ LE RECTANGLE EST CELUI DE LA DÉCISION, plus celui d'une bande plus
    # large dessinée ici : c'était le constat `charts/C2`.
    fig.add_hrect(y0=bas_a, y1=haut_a, fillcolor='rgba(0,229,160,0.06)',
                  line_width=0)
    fig.add_hline(y=1.0, line=dict(color=COULEURS['texte_2'], dash='dash', width=1))
    for yv in (bas_a, haut_a):
        fig.add_hline(y=yv, line=dict(color=COULEURS['or_accent'], dash='dot', width=1))
    fig.add_trace(go.Scatter(
        x=annees, y=ae, mode='lines+markers', name='A/E',
        line=dict(color=COULEURS['ligne_predite'], width=2),
        # ⚠️⚠️ CONSTAT `charts/C10` — ET IL ÉTAIT PLUS LARGE QUE SON LIBELLÉ.
        # Le relevé disait « l'ambre du RAG EST l'or des axes » : le point
        # AMBRE prenait `COULEURS['or_accent']` (#D4AF37), la teinte EXACTE
        # des lignes de bande et des barres d'erreur — écart de teinte 0°,
        # contraste 1,00. *Un point « AMBRE » avait la couleur du décor.*
        # Mesuré ici : les TROIS couleurs contournaient la source RAG —
        # VERT prenait `ligne_predite` (#00E5A0), ROUGE un littéral
        # `rgba(240,85,35,0.95)`. Trois définitions locales de plus, que le
        # lot de la charte n'avait pas atteintes.
        #
        # ⚠️⚠️ ET LA COULEUR SEULE NE SUFFIT PAS — c'est mesuré, pas supposé :
        # VERT et AMBRE ont un contraste mutuel de **1,04**, la MÊME
        # luminance. En niveaux de gris, à l'impression, ou pour qui a le
        # canal chromatique réduit, les deux statuts fusionnent. `SYMBOLE_RAG`
        # existait dans la source depuis le lot de la charte et n'était employé
        # NULLE PART : une figure à POINTS est exactement son usage.
        marker=dict(color=[couleur_rag(_statut(v), FOND_SOMBRE) for v in ae],
                    symbol=[SYMBOLE_RAG[_statut(v)] for v in ae],
                    size=13,
                    line=dict(color=COULEURS['texte'], width=1)),
        hovertemplate='%{x}<br>A/E = %{y:.4f}<extra></extra>',
    ))
    _appliquer_theme(fig, titre)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title='Fenêtre (année test)', type='category')
    fig.update_yaxes(title='Ratio A/E  (attendu / prédit)')
    _declarer_assiette(fig, fournis=len(fenetres), traces=len(_mesurees),
                       quoi='fenêtres')
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
    _declarer_assiette(fig, fournis=len(importance), traces=len(items),
                       quoi='variables')
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
    _declarer_assiette(fig, fournis=int(np.size(np.asarray(predictions))),
                       traces=int(p.size), quoi='prédictions')
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
    _declarer_assiette(fig, fournis=int(np.size(np.asarray(residus))),
                       traces=int(r.size), quoi='résidus')
    return fig
