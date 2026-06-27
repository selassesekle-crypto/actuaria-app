# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  n5_rapport.py  —  Rapport actuariel professionnel
#
#  3 formats de sortie au choix du client :
#    · HTML  — rapport interactif principal avec graphiques Plotly embarqués
#    · PDF   — export depuis HTML via weasyprint (archivage, signature)
#    · Word  — format .docx pour clients avec processus internes Word
#
#  Narration actuarielle :
#    · Niveau 1 : Claude API (claude-sonnet-4-6) — narration contextuelle premium
#    · Niveau 2 : Templates n5_commentaire.py — fallback si API indisponible
#    · Niveau 3 : Données chiffrées uniquement — fallback ultime
#
#  Logo : ActuarIA embarqué en base64 (page de garde + en-tête)
#
#  Palette : Navy #0F2E52 / Gold #C9A84C / Blanc #FFFFFF / Gris #8A9BB0
#
#  Auteur  : ActuarIA v5.0
#  Version : 3.0.0
# =============================================================================

from __future__ import annotations

import base64
import io
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger('actuaria.a7.rapport')

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY   = '#0F2E52'
NAVY_L = '#1A3F6B'
GOLD   = '#C9A84C'
BLANC  = '#FFFFFF'
GRIS   = '#8A9BB0'
ROUGE  = '#C0392B'
VERT   = '#27AE60'
AMBRE  = '#F39C12'
BLEU   = '#2980B9'


# =============================================================================
#  LOGO ACTUARIA — SVG embarqué (indépendant de tout fichier externe)
# =============================================================================

LOGO_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 110" width="400" height="110">
  <rect width="400" height="110" fill="#0F2E52" rx="8"/>
  <g transform="translate(42,55)">
    <circle cx="0" cy="-27" r="5" fill="none" stroke="#4A8FD4" stroke-width="1.2"/>
    <circle cx="0" cy="-9"  r="5" fill="none" stroke="#4A8FD4" stroke-width="1.2"/>
    <circle cx="0" cy="9"   r="5" fill="none" stroke="#4A8FD4" stroke-width="1.2"/>
    <circle cx="0" cy="27"  r="5" fill="none" stroke="#4A8FD4" stroke-width="1.2"/>
    <circle cx="26" cy="-16" r="5" fill="none" stroke="#C9A84C" stroke-width="1.2"/>
    <circle cx="26" cy="4"   r="5" fill="none" stroke="#C9A84C" stroke-width="1.2"/>
    <circle cx="26" cy="24"  r="5" fill="none" stroke="#C9A84C" stroke-width="1.2"/>
    <circle cx="52" cy="4"   r="8" fill="none" stroke="#C9A84C" stroke-width="1.5"/>
    <text x="52" y="8" text-anchor="middle" font-family="Georgia,serif" font-size="8" font-weight="700" fill="#C9A84C">A</text>
    <line x1="5" y1="-27" x2="21" y2="-16" stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>
    <line x1="5" y1="-9"  x2="21" y2="-16" stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>
    <line x1="5" y1="-9"  x2="21" y2="4"   stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>
    <line x1="5" y1="9"   x2="21" y2="4"   stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>
    <line x1="5" y1="9"   x2="21" y2="24"  stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>
    <line x1="5" y1="27"  x2="21" y2="24"  stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>
    <line x1="31" y1="-16" x2="44" y2="1"  stroke="#C9A84C" stroke-width="0.8" opacity="0.7"/>
    <line x1="31" y1="4"   x2="44" y2="4"  stroke="#C9A84C" stroke-width="0.8" opacity="0.7"/>
    <line x1="31" y1="24"  x2="44" y2="8"  stroke="#C9A84C" stroke-width="0.8" opacity="0.7"/>
  </g>
  <text x="122" y="50" font-family="Georgia,serif" font-size="38" font-weight="700" fill="none">
    <tspan fill="#FFFFFF">Actuar</tspan><tspan fill="#C9A84C">IA</tspan>
  </text>
  <line x1="122" y1="58" x2="328" y2="58" stroke="#C9A84C" stroke-width="0.6" opacity="0.5"/>
  <text x="122" y="73" font-family="Georgia,serif" font-size="7.5" font-weight="400" fill="#8A9BB0" letter-spacing="3">ACTUARIAL INTELLIGENCE PLATFORM</text>
</svg>'''

# Convertir SVG en data URI pour embedding HTML
LOGO_DATA_URI = f"data:image/svg+xml;base64,{base64.b64encode(LOGO_SVG.encode()).decode()}"


# =============================================================================
#  HELPERS COMMUNS
# =============================================================================

def _f(v, dec=0) -> str:
    """Formater un montant en euros avec séparateurs de milliers."""
    if v is None: return '—'
    try:
        fv = float(v)
        if np.isnan(fv) or np.isinf(fv): return '—'
        return f"{fv:,.0f} €".replace(',', '\u202f') if dec == 0 else f"{fv:,.{dec}f}".replace(',', '\u202f')
    except: return '—'

def _pct(v, dec=1) -> str:
    """Formater un pourcentage."""
    if v is None: return '—'
    try:
        fv = float(v)
        return '—' if (np.isnan(fv) or np.isinf(fv)) else f"{fv:.{dec}f} %"
    except: return '—'

def _clean(txt: str) -> str:
    """Nettoyer les caractères spéciaux du commentaire."""
    if not txt: return ''
    txt = re.sub(r'[■□▪▸►═╔╗╚╝║]+', '', txt)
    txt = re.sub(r'─+', '', txt)
    txt = re.sub(r'={4,}', '', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()

def _statut_badge(statut: str) -> str:
    """Retourne un badge HTML coloré selon le statut."""
    colors = {'VERT': VERT, 'AMBRE': AMBRE, 'ROUGE': ROUGE}
    icons  = {'VERT': '✅', 'AMBRE': '⚠️', 'ROUGE': '🔴'}
    c = colors.get(statut, GRIS)
    i = icons.get(statut, 'ℹ️')
    return (
        f"<span style='background:{c};color:#fff;padding:2px 10px;"
        f"border-radius:4px;font-size:0.8rem;font-weight:600;'>{i} {statut}</span>"
    )


# =============================================================================
#  NIVEAU 1 — NARRATION CLAUDE API
# =============================================================================

SYSTEM_PROMPT = """Tu es un actuaire Non-Vie senior certifié par l'Institut des Actuaires (IA), \
expert en provisionnement Solvabilité 2 et IFRS 17, avec 20 ans d'expérience auprès de mutuelles, \
institutions de prévoyance et grands groupes d'assurance.

Tu rédiges le commentaire actuariel d'un rapport de provisionnement Non-Vie destiné à être présenté \
au Conseil d'Administration et à l'actuaire désigné. Ce rapport sera soumis à l'ACPR dans le cadre \
du reporting Solvabilité 2.

═══════════════════════════════════════════════
RÈGLES ABSOLUES
═══════════════════════════════════════════════

0. FORMAT DE RÉDACTION : Utilise ces marqueurs UNIQUEMENT :
   §N — TITRE pour les sections principales (ex: §1 — CONTEXTE ET QUALITÉ DES DONNÉES)
   ### Sous-titre pour les sous-sections
   **texte** pour les termes importants ou chiffres clés
   - Tiret pour les éléments de liste
   N'utilise PAS de tableaux Markdown. N'utilise PAS de > pour les blockquotes.
   N'utilise PAS de # ou ## seuls. Sépare les sections par une ligne vide.

1. LANGUE : Français professionnel et précis. Anglais uniquement pour les termes techniques \
consacrés (Best Estimate, Chain Ladder, Bootstrap ODP, etc.)

2. RIGUEUR : Chaque affirmation est justifiée par les données fournies. Jamais d'affirmation \
sans données.

3. CHIFFRES : Toujours en euros avec séparateurs (ex : 2 526 597 €). Pourcentages avec une \
décimale (ex : 20.9 %).

4. RÉFÉRENCES : Citer les références réglementaires (Art. 77 S2, Art. 105 S2, Guide IA 2023, \
Mack 1993, Clark 2003, Barnett-Zehnwirth 1998).

5. ALERTES : Ne jamais minimiser une alerte. La présenter avec son implication réelle pour le \
bilan S2.

6. CAUSALITÉ : Toujours relier les éléments. Ex : "H1 rejetée (corr=0.52) → CL biaisé → \
BF retenu → impact de X € sur le BE."

7. INCERTITUDE : Toujours quantifier. Ne jamais dire "l'incertitude est élevée" sans donner \
le CV ou l'intervalle de confiance.

8. POSTURE : Assertif mais prudent. Recommandations claires avec justification. Distinguer \
ce qui est robuste de ce qui nécessite un jugement actuariel complémentaire.

9. TABLEAUX : Référencer les tableaux et graphiques du rapport (ex : "Comme l'illustre le \
Graphique G5 — Convergence des méthodes...").

10. TON : Adapté à un CA. Synthétique en introduction, technique dans le corps, conclusif \
dans les recommandations.

═══════════════════════════════════════════════
STRUCTURE OBLIGATOIRE
═══════════════════════════════════════════════

§1 — CONTEXTE ET QUALITÉ DES DONNÉES
§2 — VALIDATION DES HYPOTHÈSES ACTUARIELLES
§3 — RÉSULTATS PAR MÉTHODE ET CONVERGENCE
§4 — INCERTITUDE STOCHASTIQUE ET PROVISIONS DE PRÉCAUTION
§5 — BACK-TESTING ET QUALITÉ DU PROVISIONNEMENT HISTORIQUE
§6 — EFFETS CALENDAIRE ET RISQUES IDENTIFIÉS
§7 — CONCLUSION ET RECOMMANDATIONS POUR LE CA

═══════════════════════════════════════════════
INTERDIT
═══════════════════════════════════════════════

- Phrases génériques sans lien avec les données
- "Les résultats sont satisfaisants" sans quantifier
- Répéter les chiffres sans les commenter
- Conclure FAVORABLE si H1 rejetée ET back-testing ROUGE simultanément
- Utiliser "significatif" sans préciser le seuil statistique"""


def _construire_contexte_claude(
    n2: Dict, n3: Dict, n4: Dict,
    lob_label: str, arrete: str,
) -> str:
    """
    Construit le message utilisateur pour Claude API.
    Résume toutes les données du dossier en texte structuré.
    """
    cl   = n3.get('chain_ladder', {})
    mk   = n3.get('mack', {})
    bf   = n3.get('bf', {})
    cc   = n3.get('cape_cod', {})
    bt   = n3.get('bootstrap', {})
    clark = n3.get('clark', {})
    bz   = n3.get('barnett_zehnwirth', {})
    sc   = n4.get('scr', {})
    h1   = n2.get('h1_independance', {})
    h2   = n2.get('h2_stabilite', {})
    h3   = n2.get('h3_apriori_bf', {})
    h4   = n2.get('h4_homosc_bootstrap', {})
    bt_res = n3.get('backtesting', {})
    pw   = n4.get('poids', {})

    BE   = float(n4.get('best_estimate', 0) or 0)
    SIG  = float(mk.get('sigma_total', 0) or 0)
    CV   = float(n4.get('cv_inter_methodes', 0) or 0)
    P75  = float(n4.get('reserve_p75', 0) or 0)
    P90  = float(n4.get('reserve_p90', 0) or 0)
    P99  = float(n4.get('reserve_p99_5', 0) or 0)
    SCP  = float(sc.get('scr_prov', BE * 0.30) if sc else BE * 0.30)
    SCR  = SCP / BE * 100 if BE else 0

    ctx = f"""DOSSIER DE PROVISIONNEMENT — {lob_label.upper()} — Arrêté {arrete}

═══ TRIANGLE ═══
Dimensions : {n2.get('dimensions', '—')}
Branche : {lob_label}
Méthode retenue : {n4.get('methode_facteurs', n2.get('methode_recommandee', '—'))}

═══ HYPOTHÈSES ACTUARIELLES ═══
H1 — Indépendance (Mack 1993) : {'VALIDÉE' if h1.get('ok') else 'REJETÉE'} | corr_moy={h1.get('corr_moy', '—')} | score={h1.get('score', '—')}/100
Message H1 : {h1.get('message', '—')[:200]}

H2 — Stabilité des facteurs : {'VALIDÉE' if h2.get('ok') else 'REJETÉE'} | CV={h2.get('cv_moy', '—')} | score={h2.get('score', '—')}/100
Message H2 : {h2.get('message', '—')[:200]}

H3 — A priori BF/Cape Cod : {'VALIDÉE' if h3.get('ok') else 'REJETÉE'} | LR={h3.get('lr_apriori', '—')} | score={h3.get('score', '—')}/100
Message H3 : {h3.get('message', '—')[:200]}

H4 — Homoscédasticité Bootstrap : {'VALIDÉE' if h4.get('ok') else 'REJETÉE'} | φ={h4.get('phi', '—')} | score={h4.get('score', '—')}/100

═══ RÉSULTATS PAR MÉTHODE ═══
Chain Ladder     : {_f(cl.get('reserve_totale'))} | poids={_pct(pw.get('chain_ladder', 0)*100)}
Mack 1993        : {_f(mk.get('reserve_best_estimate'))} | poids={_pct(pw.get('mack', 0)*100)}
Bornhuetter-Ferguson : {_f(bf.get('reserve_totale'))} | poids={_pct(pw.get('bf', 0)*100)}
Cape Cod         : {_f(cc.get('reserve_totale'))} | poids={_pct(pw.get('cape_cod', 0)*100)}
Clark LDF        : {_f(clark.get('reserve_be_clark'))} | courbe={clark.get('courbe_choisie', '—')} | ω={clark.get('omega', '—')} | θ={clark.get('theta', '—')} mois | tail={clark.get('tail_factor', '—')}
BEST ESTIMATE S2 : {_f(BE)} | CV inter-méthodes={_pct(CV)}

═══ INCERTITUDE STOCHASTIQUE ═══
σ Mack total     : {_f(SIG)}
Bootstrap ODP P75 : {_f(P75)}
Bootstrap ODP P90 : {_f(P90)}
Bootstrap ODP P99.5 : {_f(P99)}

═══ SCR PROVISIONS ═══
SCR Provisions   : {_f(SCP)} (Art. 105 S2)
Ratio SCR/BE     : {_pct(SCR)}

═══ BACK-TESTING BONI/MALI ═══
Statut           : {bt_res.get('statut', '—')}
Score qualité    : {bt_res.get('score_qualite', '—')}/100
N-1 alertes      : {bt_res.get('n_rouge_n1', 0)} rouge · {bt_res.get('n_ambre_n1', 0)} ambre
N-2 alertes      : {bt_res.get('n_rouge_n2', 0)} rouge · {bt_res.get('n_ambre_n2', 0)} ambre
Années matures évaluées : {bt_res.get('n_matures', 0)}
Message BT : {bt_res.get('message', '—')[:300]}

═══ EFFETS CALENDAIRE (BARNETT-ZEHNWIRTH) ═══
Statut           : {bz.get('statut', '—')}
Effets significatifs : {bz.get('n_effets_significatifs', 0)}/{bz.get('n_diagonales_evaluees', 0)}
Diagonales anormales : {', '.join(bz.get('diagonales_anormales', [])) or 'Aucune'}
Recommandation   : {bz.get('recommandation', '—')}

═══ JUGEMENT ACTUARIEL (système) ═══
{_clean(n4.get('jugement', ''))[:500]}

Rédige maintenant le commentaire actuariel complet selon la structure en 7 sections."""

    return ctx


def _narration_claude_api(
    n2: Dict, n3: Dict, n4: Dict,
    lob_label: str, arrete: str,
) -> str:
    """
    Niveau 1 : Génère la narration actuarielle via Claude API.
    Retourne le texte du commentaire ou lève une exception si indisponible.
    """
    try:
        import anthropic
        # Lire la clé API depuis les variables d'environnement
        # En production FastAPI : variable d'environnement ANTHROPIC_API_KEY
        # En Streamlit : st.secrets["ANTHROPIC_API_KEY"]
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            # Tentative via streamlit secrets (mode Streamlit)
            try:
                import streamlit as st
                api_key = st.secrets.get("ANTHROPIC_API_KEY")
            except Exception:
                pass

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY non définie")

        client  = anthropic.Anthropic(api_key=api_key)
        contexte = _construire_contexte_claude(n2, n3, n4, lob_label, arrete)

        response = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 3000,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": contexte}],
        )

        narration = response.content[0].text
        logger.info(f"Narration Claude API : {len(narration)} chars")
        return narration

    except Exception as e:
        logger.warning(f"Claude API indisponible : {e}")
        raise


def _narration_templates(n4: Dict, commentaire: str) -> str:
    """
    Niveau 2 : Narration depuis les templates existants (n5_commentaire).
    Fallback si Claude API est indisponible.
    """
    try:
        jugement   = _clean(n4.get('jugement', ''))
        comm_clean = _clean(commentaire)
        if comm_clean:
            return comm_clean
        if jugement:
            return jugement
        return ""
    except Exception as e:
        logger.warning(f"Templates indisponibles : {e}")
        return ""


def _generer_narration(
    n2: Dict, n3: Dict, n4: Dict,
    commentaire: str, lob_label: str, arrete: str,
) -> tuple[str, str]:
    """
    Orchestrateur des 3 niveaux de narration.

    Returns
    -------
    Tuple (narration: str, source: str)
    source : 'claude_api' | 'templates' | 'aucune'
    """
    # Niveau 1 — Claude API
    try:
        narration = _narration_claude_api(n2, n3, n4, lob_label, arrete)
        return narration, 'claude_api'
    except Exception:
        pass

    # Niveau 2 — Templates
    try:
        narration = _narration_templates(n4, commentaire)
        if narration:
            return narration, 'templates'
    except Exception:
        pass

    # Niveau 3 — Aucune narration (rapport chiffré uniquement)
    return "", 'aucune'


# =============================================================================
#  CSS DU RAPPORT HTML
# =============================================================================

def _css_rapport() -> str:
    """CSS complet du rapport HTML — palette Navy/Gold ActuarIA."""
    return f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Inter:wght@300;400;500;600&display=swap');

  :root {{
    --navy:   {NAVY};
    --navy-l: {NAVY_L};
    --gold:   {GOLD};
    --blanc:  {BLANC};
    --gris:   {GRIS};
    --rouge:  {ROUGE};
    --vert:   {VERT};
    --ambre:  {AMBRE};
    --bleu:   {BLEU};
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Inter', sans-serif;
    font-size: 10pt;
    color: #1a1a2e;
    background: #f4f6f9;
    line-height: 1.7;
  }}

  .rapport-container {{
    max-width: 900px;
    margin: 0 auto;
    background: white;
    box-shadow: 0 2px 20px rgba(0,0,0,0.08);
  }}

  /* ── PAGE DE GARDE ──────────────────────────────────────────── */
  .page-garde {{
    background: var(--navy);
    padding: 60px 60px 40px;
    position: relative;
  }}

  .page-garde .logo {{
    margin-bottom: 48px;
  }}

  .page-garde .titre-rapport {{
    font-family: 'EB Garamond', serif;
    font-size: 36pt;
    font-weight: 700;
    color: var(--blanc);
    line-height: 1.2;
    margin-bottom: 8px;
  }}

  .page-garde .sous-titre {{
    font-family: 'EB Garamond', serif;
    font-size: 18pt;
    color: var(--gold);
    margin-bottom: 40px;
  }}

  .page-garde .meta-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
    border-top: 1px solid rgba(201,168,76,0.3);
    padding-top: 24px;
    margin-top: 32px;
  }}

  .page-garde .meta-item .label {{
    font-size: 7.5pt;
    color: var(--gris);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 4px;
  }}

  .page-garde .meta-item .valeur {{
    font-size: 10pt;
    color: var(--blanc);
    font-weight: 500;
  }}

  .page-garde .confidentiel {{
    position: absolute;
    top: 24px;
    right: 40px;
    font-size: 8pt;
    color: var(--rouge);
    font-weight: 600;
    letter-spacing: 2px;
    border: 1px solid var(--rouge);
    padding: 4px 10px;
    border-radius: 3px;
  }}

  .statut-badge {{
    display: inline-block;
    padding: 6px 16px;
    border-radius: 4px;
    font-size: 9pt;
    font-weight: 600;
    margin-top: 16px;
  }}

  /* ── CORPS DU RAPPORT ───────────────────────────────────────── */
  .rapport-body {{
    padding: 40px 60px;
  }}

  /* ── EN-TÊTE DE SECTION ─────────────────────────────────────── */
  .section {{
    margin-bottom: 40px;
    page-break-inside: avoid;
  }}

  .section-titre {{
    font-family: 'EB Garamond', serif;
    font-size: 16pt;
    font-weight: 700;
    color: var(--navy);
    border-bottom: 2px solid var(--gold);
    padding-bottom: 8px;
    margin-bottom: 20px;
  }}

  .section-sous-titre {{
    font-family: 'EB Garamond', serif;
    font-size: 12pt;
    font-weight: 600;
    color: var(--gold);
    margin: 20px 0 10px;
  }}

  /* ── TABLEAUX ───────────────────────────────────────────────── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
    margin: 16px 0;
  }}

  thead tr {{
    background: var(--navy);
    color: var(--blanc);
  }}

  thead th {{
    padding: 9px 12px;
    text-align: center;
    font-weight: 600;
    font-size: 8.5pt;
    letter-spacing: 0.3px;
  }}

  tbody tr:nth-child(even) {{
    background: #f0f4f8;
  }}

  tbody tr:hover {{
    background: #e8eef5;
  }}

  tbody td {{
    padding: 8px 12px;
    border-bottom: 1px solid #dde3ea;
    text-align: right;
  }}

  tbody td:first-child {{
    text-align: left;
    font-weight: 500;
    color: var(--navy);
  }}

  .row-total {{
    background: var(--navy) !important;
    color: var(--blanc) !important;
    font-weight: 700;
  }}

  .row-total td {{
    color: var(--blanc) !important;
    border: none;
  }}

  .row-be {{
    background: rgba(201,168,76,0.15) !important;
    font-weight: 700;
  }}

  /* ── CARTES KPI ─────────────────────────────────────────────── */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 16px 0;
  }}

  .kpi-card {{
    background: var(--navy);
    border-radius: 8px;
    padding: 16px 14px;
    text-align: center;
  }}

  .kpi-label {{
    font-size: 7.5pt;
    color: var(--gris);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
  }}

  .kpi-value {{
    font-family: 'EB Garamond', serif;
    font-size: 16pt;
    font-weight: 700;
    color: var(--blanc);
    line-height: 1.2;
  }}

  .kpi-sub {{
    font-size: 8pt;
    color: var(--gold);
    margin-top: 4px;
  }}

  /* ── NARRATION ACTUARIELLE ──────────────────────────────────── */
  .narration {{
    background: #f9fafc;
    border-left: 3px solid var(--gold);
    padding: 24px 28px;
    border-radius: 0 6px 6px 0;
    margin: 20px 0;
  }}

  .narration p {{
    margin-bottom: 12px;
    line-height: 1.8;
    color: #2c3e50;
  }}

  .narration h3 {{
    font-family: 'EB Garamond', serif;
    font-size: 11pt;
    font-weight: 700;
    color: var(--navy);
    margin: 20px 0 8px;
  }}

  .narration-source {{
    font-size: 7.5pt;
    color: var(--gris);
    font-style: italic;
    margin-top: 16px;
    border-top: 1px solid #e0e0e0;
    padding-top: 8px;
  }}

  /* ── ALERTES ────────────────────────────────────────────────── */
  .alerte {{
    border-left: 3px solid var(--rouge);
    background: rgba(192,57,43,0.05);
    padding: 10px 14px;
    border-radius: 0 4px 4px 0;
    margin: 8px 0;
    font-size: 9pt;
    color: #2c3e50;
  }}

  .alerte-ambre {{
    border-color: var(--ambre);
    background: rgba(243,156,18,0.05);
  }}

  .alerte-vert {{
    border-color: var(--vert);
    background: rgba(39,174,96,0.05);
  }}

  /* ── HYPOTHÈSES ─────────────────────────────────────────────── */
  .hyp-card {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 6px;
    margin: 8px 0;
    background: #f0f4f8;
    border-left: 3px solid var(--gris);
  }}

  .hyp-card.ok   {{ border-color: var(--vert); background: rgba(39,174,96,0.06); }}
  .hyp-card.fail {{ border-color: var(--ambre); background: rgba(243,156,18,0.06); }}

  .hyp-badge {{
    font-size: 8pt;
    font-weight: 700;
    min-width: 100px;
  }}

  .hyp-message {{ font-size: 9pt; color: #2c3e50; flex: 1; }}

  /* ── PIED DE PAGE ───────────────────────────────────────────── */
  .pied-de-page {{
    background: var(--navy);
    padding: 20px 60px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .pied-de-page .pied-logo img {{ height: 28px; }}

  .pied-de-page .pied-info {{
    font-size: 8pt;
    color: var(--gris);
    text-align: right;
  }}

  /* ── PRINT ──────────────────────────────────────────────────── */
  @media print {{
    body {{ background: white; }}
    .rapport-container {{ box-shadow: none; }}
    .section {{ page-break-inside: avoid; }}
    .page-garde {{ page-break-after: always; }}
  }}
</style>"""


# =============================================================================
#  GÉNÉRATION HTML
# =============================================================================

def _render_hyp_cards(h1, h2, h3, h4) -> str:
    """Génère les cartes HTML des hypothèses actuarielles."""
    result = ""
    for code, h in [
        ('H1 Indépendance (Mack 1993)', h1),
        ('H2 Stabilité des facteurs',   h2),
        ('H3 A priori BF/Cape Cod',     h3),
        ('H4 Homoscédasticité ODP',     h4),
    ]:
        if not h:
            continue
        ok    = bool(h.get('ok', True))
        cls   = 'ok' if ok else 'fail'
        col   = VERT if ok else AMBRE
        icon  = '✅' if ok else '⚠️'
        label = 'VALIDÉE' if ok else 'REJETÉE'
        score = h.get('score', '—')
        msg   = h.get('message', '')
        result += (
            f"<div class='hyp-card {cls}'>"
            f"<div class='hyp-badge' style='color:{col};'>"
            f"{icon} {code} — {label}"
            f"<br><span style='font-weight:400;font-size:7.5pt;color:#666;'>Score {score}/100</span>"
            f"</div>"
            f"<div class='hyp-message'>{msg}</div>"
            f"</div>"
        )
    return result


def export_html(
    n1: Dict, n2: Dict, n3: Dict, n4: Dict,
    commentaire : str  = '',
    ref_client  : str  = '',
    arrete      : str  = '',
    audit_id    : str  = '',
    lob_label   : str  = '',
    graphiques  : Dict = None,
) -> str:
    """
    Génère le rapport complet au format HTML.

    Parameters
    ----------
    n1-n4      : dicts des niveaux actuariels
    commentaire: texte du commentaire branche
    ref_client : nom du client
    arrete     : date d'arrêté
    audit_id   : identifiant audit trail
    lob_label  : libellé de la branche
    graphiques : dict {nom: go.Figure} pour les graphiques Plotly

    Returns
    -------
    str : HTML complet du rapport
    """
    try:
        cl   = n3.get('chain_ladder', {});  mk  = n3.get('mack', {})
        bf   = n3.get('bf', {});            cc  = n3.get('cape_cod', {})
        bt_s = n3.get('bootstrap', {});     sc  = n4.get('scr', {})
        clark = n3.get('clark', {});        bz  = n3.get('barnett_zehnwirth', {})
        bt_r = n3.get('backtesting', {});   pw  = n4.get('poids', {})
        h1   = n2.get('h1_independance', {}); h2 = n2.get('h2_stabilite', {})
        h3   = n2.get('h3_apriori_bf', {});   h4 = n2.get('h4_homosc_bootstrap', {})

        BE   = float(n4.get('best_estimate', 0) or 0)
        SIG  = float(mk.get('sigma_total', 0) or 0)
        CV   = float(n4.get('cv_inter_methodes', 0) or 0)
        P75  = float(n4.get('reserve_p75', 0) or 0)
        P90  = float(n4.get('reserve_p90', 0) or 0)
        P99  = float(n4.get('reserve_p99_5', 0) or 0)
        SCP  = float(sc.get('scr_prov', BE * 0.30) if sc else BE * 0.30)
        SCR  = SCP / BE * 100 if BE else 0

        dt       = datetime.now().strftime('%d/%m/%Y')
        arr      = arrete or dt
        cli      = ref_client or 'ActuarIA'
        lob      = lob_label or n2.get('lob_label', '—')
        methode  = n4.get('methode_facteurs', n2.get('methode_recommandee', '—'))
        statut   = n4.get('statut', 'AMBRE')
        s_colors = {'VERT': VERT, 'AMBRE': AMBRE, 'ROUGE': ROUGE}
        s_col    = s_colors.get(statut, GRIS)

        # ── Ligne Clark pour tableau HTML ────────────────────────────────────
        if clark.get('disponible'):
            _clark_courbe = clark.get('courbe_choisie', '')
            _clark_reserve = _f(clark.get('reserve_be_clark'))
            _clark_aic = str(clark.get('aic_optimal', '—'))
            _clark_row = (
                f"<tr><td>Clark LDF ({_clark_courbe})</td>"
                f"<td>{_clark_reserve}</td><td>—</td>"
                f"<td>AIC={_clark_aic}</td>"
                f"<td style='text-align:center;'>✅</td></tr>"
            )
        else:
            _clark_row = ""

        # ── Narration actuarielle (3 niveaux) ─────────────────────────────────
        narration, source_narration = _generer_narration(
            n2, n3, n4, commentaire, lob, arr
        )

        source_label = {
            'claude_api': '✨ Narration générée par Claude — ActuarIA Intelligence',
            'templates':  '📝 Narration générée en mode standard',
            'aucune':     '',
        }.get(source_narration, '')

        # ── Graphiques Plotly en HTML ──────────────────────────────────────────
        graphiques_html = {}
        if graphiques:
            try:
                import plotly.io as pio
                for nom, fig in graphiques.items():
                    try:
                        html_g = pio.to_html(
                            fig,
                            full_html=False,
                            include_plotlyjs=False,
                            config={'displayModeBar': False},
                        )
                        graphiques_html[nom] = html_g
                    except Exception as eg:
                        logger.debug(f"Graphique {nom} ignoré : {eg}")
            except ImportError:
                pass

        def _graphique(nom: str, titre: str) -> str:
            """Retourne le bloc HTML d'un graphique si disponible."""
            if nom not in graphiques_html:
                return ''
            return (
                f"<div class='section-sous-titre'>{titre}</div>"
                f"<div style='margin:12px 0;border:1px solid #e0e5ec;border-radius:6px;overflow:hidden;'>"
                f"{graphiques_html[nom]}"
                f"</div>"
            )

        # ── Narration structurée ───────────────────────────────────────────────
        def _render_narration(texte: str) -> str:
            """Convertit le texte Markdown de Claude en HTML structuré propre."""
            if not texte:
                return "<p style='color:#999;font-style:italic;'>Narration non disponible.</p>"

            txt = texte.strip()

            # 1. Séparateurs --- → ligne horizontale
            txt = re.sub(r'\n---+\n', '\n<hr style="border:none;border-top:1px solid #dde3ea;margin:16px 0;">\n', txt)

            # 2. Blockquotes > ... → encart gold
            def _bq(m):
                inner = re.sub(r'^>\s*', '', m.group(0), flags=re.MULTILINE).strip()
                inner = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', inner)
                return (
                    "<div style='background:rgba(201,168,76,0.08);border-left:3px solid #C9A84C;"
                    "padding:12px 16px;border-radius:0 4px 4px 0;margin:12px 0;"
                    f"font-size:9pt;'>{inner}</div>"
                )
            txt = re.sub(r'(?:^>.*\n?)+', _bq, txt, flags=re.MULTILINE)

            # 3. §N — TITRE → h3 gold
            txt = re.sub(
                r'(§\d+\s*[—\-]\s*[A-ZÀÉÈÊËÎÏÔÙÛÜÇ][^\n]+)',
                lambda m: (
                    "<h3 style='font-family:Georgia,serif;font-size:11pt;font-weight:700;"
                    "color:#C9A84C;margin:24px 0 8px;border-bottom:1px solid rgba(201,168,76,0.3);"
                    f"padding-bottom:4px;'>{m.group(1)}</h3>"
                ),
                txt
            )

            # 4. ### Sous-titre → h4 navy
            txt = re.sub(
                r'^###\s+(.+)$',
                lambda m: f"<h4 style='font-family:Georgia,serif;font-size:10pt;font-weight:600;color:#0F2E52;margin:14px 0 6px;'>\U0001f539 {m.group(1)}</h4>",
                txt, flags=re.MULTILINE
            )

            # 5. ## Titre → h3
            txt = re.sub(r'^##\s+(.+)$', r'<h3 style="color:#0F2E52;">\1</h3>', txt, flags=re.MULTILINE)

            # 6. **gras** → strong gold
            txt = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#0F2E52;">\1</strong>', txt)

            # 7. *italique* → em
            txt = re.sub(r'\*(.+?)\*', r'<em>\1</em>', txt)

            # 8. Puces - → liste
            txt = re.sub(r'^-\s+(.+)$', r'<li style="margin:3px 0;">\1</li>', txt, flags=re.MULTILINE)
            txt = re.sub(r'(<li[^>]*>.*?</li>\n?)+',
                lambda m: f"<ul style='margin:8px 0 8px 18px;'>{m.group(0)}</ul>",
                txt, flags=re.DOTALL)

            # 9. Paragraphes — double saut de ligne
            blocs = re.split(r'\n{2,}', txt)
            result = ""
            for bloc in blocs:
                bloc = bloc.strip()
                if not bloc:
                    continue
                if bloc.startswith('<'):
                    result += bloc + "\n"
                else:
                    bloc_clean = bloc.replace('\n', ' ')
                    result += f"<p style='margin-bottom:10px;line-height:1.85;color:#2c3e50;'>{bloc_clean}</p>\n"

            return result or f"<p>{texte}</p>"

        # ── Variables HTML complexes (évite les f-strings imbriquées) ──────────
        # Alertes Barnett-Zehnwirth
        # Filtrer BZ : FORT et MODÉRÉ → alerte individuelle, FAIBLE → résumé compact
        _bz_forts   = [e for e in bz.get("effets_calendaire", []) if e.get("significatif") and e.get("niveau") in ("FORT", "MODÉRÉ")]
        _bz_faibles = [e for e in bz.get("effets_calendaire", []) if e.get("significatif") and e.get("niveau") == "FAIBLE"]
        _bz_alertes_html = ""
        for _e in _bz_forts:
            _icon  = "🔴" if _e.get("niveau") == "FORT" else "⚠️"
            _cls   = "" if _e.get("niveau") == "FORT" else "alerte-ambre"
            _e_label = _e.get("annee_label", "—")
            _e_amp   = _e.get("amplitude_pct", 0)
            _e_niv   = _e.get("niveau", "—")
            _bz_alertes_html += (
                f"<div class='alerte {_cls}'>"
                f"{_icon} {_e_label} : {_e_amp:+.1f}% ({_e_niv})"
                f"</div>"
            )
        if _bz_faibles:
            _n_f = len(_bz_faibles)
            _annees_f = ", ".join(e.get("annee_label", "") for e in _bz_faibles[:3])
            _suite = f" et {_n_f - 3} autre(s)" if _n_f > 3 else ""
            _bz_alertes_html += (
                f"<div class='alerte alerte-ambre'>"
                f"ℹ️ {_n_f} diagonale(s) avec effet FAIBLE (&lt;8%) : {_annees_f}{_suite} — surveillance recommandée."
                f"</div>"
            )
        _bz_ok_msg = "Aucun effet calendaire significatif détecté — triangle conforme à l'hypothèse d'indépendance des diagonales."
        _bz_ok_html = f"<div class='alerte-vert alerte'>✅ {_bz_ok_msg}</div>" if bz.get('n_effets_significatifs', 0) == 0 else ""
        _bz_reco_txt = bz.get('recommandation', '')
        _bz_reco_html2 = (
            f"<div style='margin-top:12px;font-size:9pt;color:{NAVY};'>"
            f"<strong>Recommandation :</strong> {_bz_reco_txt}</div>"
        ) if bz.get('n_effets_significatifs', 0) > 0 else ""


        _avis_txt = _clean(n4.get('avis_actuariel', ''))
        if _avis_txt:
            _avis_col = ROUGE if 'DÉFAVORABLE' in _avis_txt.upper() else VERT
            _avis_html = (
                f"<div style='background:{_avis_col};color:#fff;padding:14px 20px;"
                f"border-radius:6px;margin-top:20px;font-size:10pt;font-weight:600;'>"
                f"{_avis_txt}</div>"
            )
        else:
            _avis_html = ""

        # ── HTML COMPLET ───────────────────────────────────────────────────────
        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rapport Actuariel — {cli} — {arr}</title>
  <script src="https://cdn.jsdelivr.net/npm/plotly.js-dist@2.26.0/plotly.min.js"></script>
  {_css_rapport()}
</head>
<body>
<div class="rapport-container">

<!-- ═══════════════════════════════════════════ PAGE DE GARDE ══ -->
<div class="page-garde">
  <div class="confidentiel">CONFIDENTIEL</div>
  <div class="logo">
    <img src="{LOGO_DATA_URI}" alt="ActuarIA" height="70"/>
  </div>
  <div class="titre-rapport">Rapport de Provisionnement<br>Non-Vie</div>
  <div class="sous-titre">{lob}</div>
  <div style="margin-top:16px;">{_statut_badge(statut)}</div>
  <div class="meta-grid">
    <div class="meta-item">
      <div class="label">Client</div>
      <div class="valeur">{cli}</div>
    </div>
    <div class="meta-item">
      <div class="label">Arrêté</div>
      <div class="valeur">{arr}</div>
    </div>
    <div class="meta-item">
      <div class="label">Méthode retenue</div>
      <div class="valeur">{methode.replace('_', ' ').title()}</div>
    </div>
    <div class="meta-item">
      <div class="label">Best Estimate S2</div>
      <div class="valeur" style="color:{GOLD};">{_f(BE)}</div>
    </div>
    <div class="meta-item">
      <div class="label">Date rapport</div>
      <div class="valeur">{dt}</div>
    </div>
    <div class="meta-item">
      <div class="label">Audit ID</div>
      <div class="valeur">{audit_id or '—'}</div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════ CORPS ══ -->
<div class="rapport-body">

<!-- ── 1. SYNTHÈSE EXÉCUTIVE ── -->
<div class="section">
  <div class="section-titre">1. Synthèse exécutive</div>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Best Estimate S2</div>
      <div class="kpi-value">{_f(BE)}</div>
      <div class="kpi-sub">Art. 77 Directive S2</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">σ Mack total</div>
      <div class="kpi-value">{_f(SIG)}</div>
      <div class="kpi-sub">CV inter-méthodes : {_pct(CV)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">SCR Provisions</div>
      <div class="kpi-value">{_f(SCP)}</div>
      <div class="kpi-sub">Ratio SCR/BE : {_pct(SCR)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Provision P99.5</div>
      <div class="kpi-value">{_f(P99)}</div>
      <div class="kpi-sub">P90 : {_f(P90)}</div>
    </div>
  </div>
  {_graphique('g5_convergence', 'Convergence des méthodes — Best Estimate S2')}
</div>

<!-- ── 2. RÉSULTATS PAR MÉTHODE ── -->
<div class="section">
  <div class="section-titre">2. Résultats par méthode actuarielle</div>
  <table>
    <thead>
      <tr>
        <th style="text-align:left;">Méthode</th>
        <th>Réserve IBNR (€)</th>
        <th>Poids BE</th>
        <th>Score /100</th>
        <th>Statut</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Chain Ladder</td>
        <td>{_f(cl.get('reserve_totale'))}</td>
        <td>{_pct(pw.get('chain_ladder', 0)*100)}</td>
        <td>{n2.get('scores_confiance', {}).get('chain_ladder', '—')}</td>
        <td style="text-align:center;">✅</td>
      </tr>
      <tr>
        <td>Mack 1993</td>
        <td>{_f(mk.get('reserve_best_estimate'))}</td>
        <td>{_pct(pw.get('mack', 0)*100)}</td>
        <td>{n2.get('scores_confiance', {}).get('mack', '—')}</td>
        <td style="text-align:center;">✅</td>
      </tr>
      <tr>
        <td>Bornhuetter-Ferguson</td>
        <td>{_f(bf.get('reserve_totale'))}</td>
        <td>{_pct(pw.get('bf', 0)*100)}</td>
        <td>{n2.get('scores_confiance', {}).get('bf', '—')}</td>
        <td style="text-align:center;">✅</td>
      </tr>
      <tr>
        <td>Cape Cod</td>
        <td>{_f(cc.get('reserve_totale'))}</td>
        <td>{_pct(pw.get('cape_cod', 0)*100)}</td>
        <td>{n2.get('scores_confiance', {}).get('cape_cod', '—')}</td>
        <td style="text-align:center;">✅</td>
      </tr>
      {_clark_row}
      <tr class="row-be">
        <td>⭐ BEST ESTIMATE S2</td>
        <td>{_f(BE)}</td>
        <td>100 %</td>
        <td>—</td>
        <td style="text-align:center;">→ Bilan S2</td>
      </tr>
    </tbody>
  </table>

  <!-- Incertitude stochastique -->
  <div class="section-sous-titre">Incertitude stochastique — Bootstrap ODP & Mack 1993</div>
  <table>
    <thead>
      <tr>
        <th style="text-align:left;">Approche</th>
        <th>BE (€)</th>
        <th>P75 (€)</th>
        <th>P90 (€)</th>
        <th>P99.5 (€)</th>
        <th>CV (%)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Mack 1993 (analytique)</td>
        <td>{_f(BE)}</td>
        <td>{_f(P75)}</td>
        <td>{_f(P90)}</td>
        <td>{_f(P99)}</td>
        <td>{_pct(SIG/BE*100 if BE else 0)}</td>
      </tr>
      <tr>
        <td>Bootstrap ODP (5 000 sim.)</td>
        <td>{_f(bt_s.get('be_bootstrap', BE))}</td>
        <td>{_f(bt_s.get('reserve_p75', P75))}</td>
        <td>{_f(bt_s.get('reserve_p90', P90))}</td>
        <td>{_f(bt_s.get('reserve_p99_5', P99))}</td>
        <td>{_pct(bt_s.get('cv', CV))}</td>
      </tr>
    </tbody>
  </table>

  {_graphique('g1_heatmap', 'Triangle de développement cumulé')}
  {_graphique('g4_ibnr', 'IBNR par année de survenance')}
  {_graphique('g6_bootstrap', 'Distribution Bootstrap ODP — Quantiles de réserve')}
  {_graphique('g13_paiements', 'Paiements cumulés par année de survenance')}
</div>

<!-- ── 3. VALIDATION DES HYPOTHÈSES ── -->
<div class="section">
  <div class="section-titre">3. Validation des hypothèses actuarielles</div>
  {_render_hyp_cards(h1, h2, h3, h4)}

  <!-- Méthode recommandée -->
  <div style="background:{NAVY};color:{BLANC};padding:14px 20px;border-radius:6px;margin-top:16px;">
    <span style="font-size:8pt;color:{GOLD};text-transform:uppercase;letter-spacing:1px;">Méthode recommandée</span><br>
    <span style="font-size:11pt;font-weight:600;">{methode.replace('_',' ').title()}</span>
    <span style="font-size:9pt;color:{GRIS};margin-left:16px;">{_clean(n2.get('raison_recommandation',''))[:150]}</span>
  </div>
</div>

<!-- ── 4. SCR PROVISIONS ── -->
<div class="section">
  <div class="section-titre">4. SCR Provisions — Art. 105 Solvabilité 2</div>
  <table>
    <thead>
      <tr>
        <th style="text-align:left;">Composante</th>
        <th>Valeur</th>
        <th style="text-align:left;">Référence réglementaire</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>Best Estimate S2</td><td>{_f(BE)}</td><td style="text-align:left;">Art. 77 Directive S2</td></tr>
      <tr><td>Facteur σ EIOPA</td><td>10 %</td><td style="text-align:left;">{lob} (Annexe II, Règlement 2015/35)</td></tr>
      <tr><td>SCR Provisions</td><td>{_f(SCP)}</td><td style="text-align:left;">SCR = 3 × σ(LoB) × BE (Art. 105)</td></tr>
      <tr class="row-be"><td>Ratio SCR/BE</td><td>{_pct(SCR)}</td><td style="text-align:left;">Cible pratique marché : &lt; 35 %</td></tr>
    </tbody>
  </table>
</div>

<!-- ── 5. BACK-TESTING BONI/MALI ── -->
<div class="section">
  <div class="section-titre">5. Back-testing — Boni/Mali de liquidation</div>
  <div style="display:flex;gap:16px;margin-bottom:16px;flex-wrap:wrap;">
    <div style="background:{s_col};color:#fff;padding:10px 20px;border-radius:6px;text-align:center;">
      <div style="font-size:8pt;opacity:0.8;">Statut</div>
      <div style="font-size:14pt;font-weight:700;">{bt_r.get('statut','—')}</div>
    </div>
    <div style="background:{NAVY};color:#fff;padding:10px 20px;border-radius:6px;text-align:center;">
      <div style="font-size:8pt;color:{GRIS};">Score qualité</div>
      <div style="font-size:14pt;font-weight:700;color:{GOLD};">{bt_r.get('score_qualite','—')}/100</div>
    </div>
    <div style="background:{NAVY};color:#fff;padding:10px 20px;border-radius:6px;text-align:center;">
      <div style="font-size:8pt;color:{GRIS};">Alertes N-1</div>
      <div style="font-size:14pt;font-weight:700;">{bt_r.get('n_rouge_n1',0)} 🔴 {bt_r.get('n_ambre_n1',0)} 🟡</div>
    </div>
    <div style="background:{NAVY};color:#fff;padding:10px 20px;border-radius:6px;text-align:center;">
      <div style="font-size:8pt;color:{GRIS};">Alertes N-2</div>
      <div style="font-size:14pt;font-weight:700;">{bt_r.get('n_rouge_n2',0)} 🔴 {bt_r.get('n_ambre_n2',0)} 🟡</div>
    </div>
  </div>
  {_graphique('g14_backtesting', 'Boni/Mali de liquidation — Horizons N-1 et N-2')}
</div>

<!-- ── 6. EFFETS CALENDAIRE ── -->
<div class="section">
  <div class="section-titre">6. Effets calendaire — Barnett-Zehnwirth (1998)</div>
  {_bz_ok_html}
  {_bz_alertes_html}
  {_bz_reco_html2}
</div>

<!-- ── 7. COMMENTAIRE ACTUARIEL ── -->
<div class="section">
  <div class="section-titre">7. Commentaire actuariel</div>
  <div class="narration">
    {_render_narration(narration)}
    {f"<div class='narration-source'>{source_label}</div>" if source_label else ''}
  </div>
</div>

<!-- ── 8. JUGEMENT ET RECOMMANDATIONS ── -->
<div class="section">
  <div class="section-titre">8. Jugement actuariel &amp; Recommandations</div>
  {''.join([
      f"<div class='alerte'>{_clean(str(a))}</div>"
      for a in n4.get('alertes', n2.get('alertes', []))
  ])}
  {''.join([
      f"<div style='padding:8px 0;border-bottom:1px solid #eee;font-size:9pt;'>"
      f"<span style='color:{GOLD};font-weight:700;'>{i}. </span>{_clean(str(r))}</div>"
      for i, r in enumerate(n4.get('recommandations', []), 1)
  ])}
  {_avis_html}
</div>

</div><!-- fin rapport-body -->

<!-- ═══════════════════════════════════════════ PIED DE PAGE ══ -->
<div class="pied-de-page">
  <div class="pied-logo">
    <img src="{LOGO_DATA_URI}" alt="ActuarIA" height="28"/>
  </div>
  <div class="pied-info">
    {cli} · {lob} · Arrêté {arr} · Audit ID : {audit_id or '—'} · {dt}<br>
    <span style="color:{ROUGE};font-weight:600;">CONFIDENTIEL — USAGE STRICTEMENT ACTUARIEL</span>
  </div>
</div>

</div><!-- fin rapport-container -->
</body>
</html>"""

        logger.info(f"HTML généré : {len(html):,} chars — narration={source_narration}")
        return html

    except Exception as e:
        logger.error(f"export_html échoué : {e}", exc_info=True)
        return f"<html><body><h1>Erreur génération rapport</h1><p>{e}</p></body></html>"


# =============================================================================
#  EXPORT PDF (weasyprint)
# =============================================================================

def export_pdf(
    n1: Dict = None, n2: Dict = None, n3: Dict = None, n4: Dict = None,
    commentaire='', ref_client='', arrete='',
    audit_id='', lob_label='', graphiques=None, **kwargs,
) -> bytes:
    """
    Génère le rapport PDF depuis le HTML via weasyprint.

    weasyprint convertit le HTML/CSS en PDF fidèle — polices, couleurs,
    tableaux, graphiques (si SVG) sont tous préservés.

    Returns
    -------
    bytes : contenu du PDF, ou b'' si échec
    """
    n1=n1 or {}; n2=n2 or {}; n3=n3 or {}; n4=n4 or {}
    try:
        from weasyprint import HTML as WH, CSS
        html_content = export_html(
            n1, n2, n3, n4,
            commentaire=commentaire,
            ref_client=ref_client,
            arrete=arrete,
            audit_id=audit_id,
            lob_label=lob_label,
            graphiques=graphiques,
        )
        pdf = WH(string=html_content).write_pdf()
        logger.info(f"PDF généré : {len(pdf):,} bytes")
        return pdf
    except ImportError:
        logger.error("weasyprint non installé — pip install weasyprint")
        return b''
    except Exception as e:
        logger.error(f"export_pdf échoué : {e}", exc_info=True)
        return b''


# =============================================================================
#  EXPORT WORD (.docx)
# =============================================================================

def export_word(
    n1: Dict, n2: Dict, n3: Dict, n4: Dict,
    commentaire='', ref_client='', arrete='',
    audit_id='', lob_label='', graphiques=None,
) -> bytes:
    """
    Génère le rapport Word (.docx) via python-docx.

    Format secondaire — pour les clients avec processus internes Word
    (archivage, signatures électroniques, annotations collaboratives).

    Returns
    -------
    bytes : contenu du .docx, ou b'' si échec
    """
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError as e:
        logger.error(f"python-docx absent : {e}"); return b''

    try:
        def rgb(h):
            h = h.lstrip('#')
            return RGBColor(int(h[:2],16), int(h[2:4],16), int(h[4:],16))

        NR=rgb(NAVY); GR=rgb(GOLD); BR=rgb(BLANC)
        GrR=rgb(GRIS); RgR=rgb(ROUGE); VR=rgb(VERT); AR=rgb(AMBRE)

        doc = Document()
        for s in doc.sections:
            s.top_margin=Cm(2); s.bottom_margin=Cm(2)
            s.left_margin=Cm(2.5); s.right_margin=Cm(2.5)

        cl=n3.get('chain_ladder',{}); mk=n3.get('mack',{})
        bf=n3.get('bf',{});           cc=n3.get('cape_cod',{})
        bt_s=n3.get('bootstrap',{});  sc=n4.get('scr',{})
        clark=n3.get('clark',{});     bz=n3.get('barnett_zehnwirth',{})
        bt_r=n3.get('backtesting',{}); pw=n4.get('poids',{})
        h1=n2.get('h1_independance',{}); h2=n2.get('h2_stabilite',{})
        h3=n2.get('h3_apriori_bf',{});   h4=n2.get('h4_homosc_bootstrap',{})

        BE=float(n4.get('best_estimate',0) or 0)
        SIG=float(mk.get('sigma_total',0) or 0)
        CV=float(n4.get('cv_inter_methodes',0) or 0)
        P75=float(n4.get('reserve_p75',0) or 0)
        P90=float(n4.get('reserve_p90',0) or 0)
        P99=float(n4.get('reserve_p99_5',0) or 0)
        SCP=float(sc.get('scr_prov',BE*0.30) if sc else BE*0.30)
        SCR=SCP/BE*100 if BE else 0

        dt=datetime.now().strftime('%d/%m/%Y')
        arr=arrete or dt; cli=ref_client or 'ActuarIA'
        lob=lob_label or n2.get('lob_label','—')
        methode=n4.get('methode_facteurs',n2.get('methode_recommandee','—'))
        statut=n4.get('statut','AMBRE')

        # Narration
        narration, source_narration = _generer_narration(
            n2, n3, n4, commentaire, lob, arr
        )

        def _bg(cell, hex6):
            tc=cell._tc; tcp=tc.get_or_add_tcPr()
            s=OxmlElement('w:shd')
            s.set(qn('w:fill'),hex6.lstrip('#'))
            s.set(qn('w:color'),'auto')
            s.set(qn('w:val'),'clear')
            tcp.append(s)

        def _run(p, txt, bold=False, italic=False, sz=10, col=None):
            r=p.add_run(str(txt)); r.bold=bold; r.italic=italic; r.font.size=Pt(sz)
            if col: r.font.color.rgb=col
            return r

        def _h(txt, lv=1, col=None, sb=8, sa=3):
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(sb)
            p.paragraph_format.space_after=Pt(sa)
            sz={1:16,2:12,3:10}.get(lv,10)
            c=col or (NR if lv==1 else GR)
            _run(p,txt,bold=True,sz=sz,col=c); return p

        def _sep(col='C9A84C'):
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(2); p.paragraph_format.space_after=Pt(2)
            pPr=p._p.get_or_add_pPr(); pBdr=OxmlElement('w:pBdr')
            b=OxmlElement('w:bottom')
            b.set(qn('w:val'),'single'); b.set(qn('w:sz'),'6')
            b.set(qn('w:space'),'1'); b.set(qn('w:color'),col)
            pBdr.append(b); pPr.append(pBdr)

        def _tbl(heads, rows, ws=None, hbg='0F2E52'):
            from docx.enum.table import WD_ALIGN_VERTICAL
            t=doc.add_table(rows=1+len(rows), cols=len(heads)); t.style='Table Grid'
            for i,hd in enumerate(heads):
                c=t.rows[0].cells[i]; _bg(c,hbg)
                p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                r=p.add_run(str(hd)); r.bold=True; r.font.size=Pt(9); r.font.color.rgb=BR
                c.vertical_alignment=WD_ALIGN_VERTICAL.CENTER
            for ri,row in enumerate(rows):
                for ci,v in enumerate(row):
                    c=t.rows[ri+1].cells[ci]
                    if ri%2==1: _bg(c,'EEF2F7')
                    p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    r=p.add_run(str(v) if v is not None else '—')
                    r.font.size=Pt(9); c.vertical_alignment=WD_ALIGN_VERTICAL.CENTER
            if ws:
                for i,w in enumerate(ws):
                    for row in t.rows: row.cells[i].width=Cm(w)
            doc.add_paragraph().paragraph_format.space_after=Pt(2)

        # ── Logo + page de garde ──────────────────────────────────────────────
        # Logo SVG → PNG via conversion (si disponible)
        try:
            import cairosvg
            logo_png = cairosvg.svg2png(bytestring=LOGO_SVG.encode(), output_width=300)
            doc.add_picture(io.BytesIO(logo_png), width=Cm(8))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.LEFT
        except Exception:
            # Logo non disponible → texte de remplacement
            p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.LEFT
            _run(p,'Actuar',bold=True,sz=28,col=NR)
            _run(p,'IA',bold=True,sz=28,col=GR)

        doc.add_paragraph()
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.LEFT
        _run(p,'RAPPORT DE PROVISIONNEMENT NON-VIE\n',bold=True,sz=22,col=NR)
        _run(p,lob,bold=True,sz=16,col=GR)
        doc.add_paragraph()
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.LEFT
        _run(p,'Statut : ',sz=11,col=NR)
        s_col_r = VR if statut=='VERT' else AR if statut=='AMBRE' else RgR
        _run(p,f"{statut}",bold=True,sz=11,col=s_col_r)
        doc.add_paragraph()
        _tbl(['Client','Branche','Méthode','Arrêté','Audit ID'],
             [[cli,lob,methode.replace('_',' ').title(),arr,audit_id or '—']],
             ws=[3.0,3.0,3.5,2.5,4.0])
        doc.add_page_break()

        # ── 1. Synthèse ───────────────────────────────────────────────────────
        _h('1. Synthèse exécutive'); _sep()
        _tbl(['Indicateur','Valeur','Indicateur','Valeur'],
             [['Best Estimate S2',_f(BE),'σ Mack total',_f(SIG)],
              ['Provision P75',_f(P75),'CV inter-méthodes',_pct(CV)],
              ['Provision P90',_f(P90),'SCR Provisions',_f(SCP)],
              ['Provision P99.5',_f(P99),'Ratio SCR/BE',_pct(SCR)]],
             ws=[4.5,3.5,4.5,3.5])
        doc.add_page_break()

        # ── 2. Résultats ──────────────────────────────────────────────────────
        _h('2. Résultats par méthode actuarielle'); _sep()
        rows_m=[
            ['Chain Ladder',_f(cl.get('reserve_totale')),_pct(pw.get('chain_ladder',0)*100),str(n2.get('scores_confiance',{}).get('chain_ladder','—')),'✅'],
            ['Mack 1993',_f(mk.get('reserve_best_estimate')),_pct(pw.get('mack',0)*100),str(n2.get('scores_confiance',{}).get('mack','—')),'✅'],
            ['Bornhuetter-Ferguson',_f(bf.get('reserve_totale')),_pct(pw.get('bf',0)*100),str(n2.get('scores_confiance',{}).get('bf','—')),'✅'],
            ['Cape Cod',_f(cc.get('reserve_totale')),_pct(pw.get('cape_cod',0)*100),str(n2.get('scores_confiance',{}).get('cape_cod','—')),'✅'],
        ]
        if clark.get('disponible'):
            rows_m.append(['Clark LDF ('+clark.get('courbe_choisie','')+')','','—','AIC='+str(clark.get('aic_optimal','—')),'✅'])
        rows_m.append(['⭐ BEST ESTIMATE S2',_f(BE),'100 %','—','→ Bilan S2'])
        _tbl(['Méthode','Réserve IBNR (€)','Poids BE','Score /100','Statut'],rows_m,ws=[4.5,3.5,2.5,2.5,3.0])
        doc.add_page_break()

        # ── 3. Hypothèses ─────────────────────────────────────────────────────
        _h('3. Validation des hypothèses actuarielles'); _sep()
        rows_h=[]
        for lbl,h in [('H1 — Indépendance',h1),('H2 — Stabilité',h2),('H3 — A priori BF',h3),('H4 — Homoscédasticité',h4)]:
            if not h: continue
            ok=bool(h.get('ok',True))
            _h_score = h.get("score", "—")
        _h_msg   = h.get("message", "")[:80]
        rows_h.append([lbl, 'VALIDÉE' if ok else 'REJETÉE', f"{_h_score}/100", _h_msg])
        if rows_h:
            _tbl(['Hypothèse','Résultat','Score','Message'],rows_h,ws=[4.5,2.5,2.0,7.0])
        doc.add_page_break()

        # ── 4. SCR ────────────────────────────────────────────────────────────
        _h('4. SCR Provisions — Art. 105 S2'); _sep()
        _tbl(['Composante','Valeur','Référence'],
             [['Best Estimate S2',_f(BE),'Art. 77 S2'],
              ['Facteur σ EIOPA','10 %',f'LoB : {lob}'],
              ['SCR Provisions',_f(SCP),'3 × σ × BE'],
              ['Ratio SCR/BE',_pct(SCR),'< 35 %']],ws=[4.5,3.5,8.0])
        doc.add_page_break()

        # ── 5. Back-testing ───────────────────────────────────────────────────
        _h('5. Back-testing — Boni/Mali de liquidation'); _sep()
        p=doc.add_paragraph()
        _run(p,f"Statut : ",sz=9,col=NR)
        s_col_r2 = VR if bt_r.get('statut')=='VERT' else AR if bt_r.get('statut')=='AMBRE' else RgR
        _run(p,bt_r.get('statut','—'),bold=True,sz=9,col=s_col_r2)
        _bt_score2 = bt_r.get("score_qualite", "—")
        _bt_r_n1   = bt_r.get("n_rouge_n1", 0)
        _bt_a_n1   = bt_r.get("n_ambre_n1", 0)
        _bt_r_n2   = bt_r.get("n_rouge_n2", 0)
        _bt_a_n2   = bt_r.get("n_ambre_n2", 0)
        _run(p, f" | Score qualité : {_bt_score2}/100", sz=9, col=NR)
        _run(p, f" | N-1 : {_bt_r_n1} rouge · {_bt_a_n1} ambre", sz=9, col=NR)
        _run(p, f" | N-2 : {_bt_r_n2} rouge · {_bt_a_n2} ambre", sz=9, col=NR)
        doc.add_page_break()

        # ── 6. Effets calendaire ──────────────────────────────────────────────
        _h('6. Effets calendaire — Barnett-Zehnwirth (1998)'); _sep()
        n_sig_bz = bz.get('n_effets_significatifs', 0)
        if n_sig_bz == 0:
            p=doc.add_paragraph()
            _run(p,'✅ Aucun effet calendaire significatif détecté.',sz=9,col=VR)
        else:
            for e in bz.get('effets_calendaire',[]):
                if e.get('significatif'):
                    p=doc.add_paragraph()
                    p.paragraph_format.left_indent=Cm(0.4)
                    _e2_label = e.get("annee_label", "—")
                    _e2_amp   = e.get("amplitude_pct", 0)
                    _e2_niv   = e.get("niveau", "—")
                    _run(p, f"⚠️ {_e2_label} : {_e2_amp:+.1f}% ({_e2_niv})", sz=9, col=AR)
        doc.add_page_break()

        # ── 7. Commentaire actuariel ──────────────────────────────────────────
        _h('7. Commentaire actuariel'); _sep()
        if narration:
            sections_n = re.split(r'(?=§\d+\s*—)', _clean(narration))
            for sec in sections_n:
                sec=sec.strip()
                if not sec: continue
                ls=sec.split('\n',1)
                if ls[0]: _h(ls[0],lv=2)
                if len(ls)>1:
                    for ln in ls[1].split('\n'):
                        ln=ln.strip()
                        if ln:
                            p=doc.add_paragraph()
                            p.paragraph_format.space_after=Pt(3)
                            p.paragraph_format.left_indent=Cm(0.3)
                            _run(p,ln,sz=9,col=NR)
            if source_narration == 'claude_api':
                p=doc.add_paragraph()
                _run(p,'✨ Narration générée par Claude — ActuarIA Intelligence',sz=7,italic=True,col=rgb(GRIS))
        else:
            p=doc.add_paragraph()
            _run(p,'Commentaire non disponible.',sz=9,italic=True)
        doc.add_page_break()

        # ── 8. Jugement et recommandations ────────────────────────────────────
        _h('8. Jugement actuariel & Recommandations'); _sep()
        for a in n4.get('alertes',n2.get('alertes',[])):
            at=_clean(str(a))
            if not at: continue
            p=doc.add_paragraph(); p.paragraph_format.left_indent=Cm(0.4)
            _run(p,'⚠️  ',sz=10,col=AR); _run(p,at,sz=9,col=NR)
        for i,rec in enumerate(n4.get('recommandations',[]),1):
            r=_clean(str(rec))
            if not r: continue
            p=doc.add_paragraph(); p.paragraph_format.left_indent=Cm(0.4)
            _run(p,f'{i}.  ',bold=True,sz=10,col=GR); _run(p,r,sz=9,col=NR)
        avis=_clean(n4.get('avis_actuariel',''))
        if avis:
            doc.add_paragraph()
            p=doc.add_paragraph()
            a_col = RgR if 'DÉFAVORABLE' in avis.upper() else VR
            _run(p,avis,sz=10,bold=True,col=a_col)

        # ── Pied de page ──────────────────────────────────────────────────────
        _sep('0F2E52')
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        _run(p,f'ActuarIA · {cli} · {lob} · Arrêté {arr} · Audit ID : {audit_id or "—"} · {dt} · CONFIDENTIEL',
             sz=7,italic=True,col=GrR)

        buf=io.BytesIO(); doc.save(buf); buf.seek(0)
        wb=buf.read()
        logger.info(f"Word : {len(wb):,} bytes — narration={source_narration}")
        return wb

    except Exception as e:
        logger.error(f"export_word : {e}", exc_info=True)
        return b''
