# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  n5_rapport.py  —  Rapport actuariel professionnel v4.0
#
#  3 formats : HTML (principal) · PDF (weasyprint) · Word (.docx)
#  Narration : Claude API → Templates → Données seules (3 niveaux)
#  Architecture : ZÉRO f-string imbriquée — toutes les variables HTML
#                 sont pré-calculées avant le rendu du template
#
#  Auteur  : ActuarIA v5.0
#  Version : 4.0.0
# =============================================================================

from __future__ import annotations
import base64, io, logging, os, re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
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

# ── Mapping LOB codes → libellés français professionnels ─────────────────────
LOB_LABELS = {
    'mrh':             'MRH — Multirisques Habitation',
    'rc_auto':         'RC Automobile',
    'rc_generale':     'RC Générale',
    'rc_medicale':     'RC Médicale',
    'construction':    'Construction (DO / RC Décennale)',
    'transport':       'Transport Maritime & Terrestre',
    'credit_caution':  'Crédit & Caution',
    'catastrophe_nat': 'Catastrophes Naturelles',
    'autre':           'Autre branche Non-Vie',
    'generique':       'Branche Non-Vie',
}

def _lob(code: str) -> str:
    """Convertit un code LOB en libellé français professionnel."""
    if not code:
        return 'Branche Non-Vie'
    c = str(code).lower().strip().replace(' ', '_')
    return LOB_LABELS.get(c, code.replace('_', ' ').title())


# =============================================================================
#  LOGO SVG ACTUARIA
# =============================================================================

LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 110" width="400" height="110">'
    '<rect width="400" height="110" fill="#0F2E52" rx="8"/>'
    '<g transform="translate(42,55)">'
    '<circle cx="0" cy="-27" r="5" fill="none" stroke="#4A8FD4" stroke-width="1.2"/>'
    '<circle cx="0" cy="-9"  r="5" fill="none" stroke="#4A8FD4" stroke-width="1.2"/>'
    '<circle cx="0" cy="9"   r="5" fill="none" stroke="#4A8FD4" stroke-width="1.2"/>'
    '<circle cx="0" cy="27"  r="5" fill="none" stroke="#4A8FD4" stroke-width="1.2"/>'
    '<circle cx="26" cy="-16" r="5" fill="none" stroke="#C9A84C" stroke-width="1.2"/>'
    '<circle cx="26" cy="4"   r="5" fill="none" stroke="#C9A84C" stroke-width="1.2"/>'
    '<circle cx="26" cy="24"  r="5" fill="none" stroke="#C9A84C" stroke-width="1.2"/>'
    '<circle cx="52" cy="4"   r="8" fill="none" stroke="#C9A84C" stroke-width="1.5"/>'
    '<text x="52" y="8" text-anchor="middle" font-family="Georgia,serif" font-size="8" font-weight="700" fill="#C9A84C">A</text>'
    '<line x1="5" y1="-27" x2="21" y2="-16" stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>'
    '<line x1="5" y1="-9"  x2="21" y2="-16" stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>'
    '<line x1="5" y1="-9"  x2="21" y2="4"   stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>'
    '<line x1="5" y1="9"   x2="21" y2="4"   stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>'
    '<line x1="5" y1="9"   x2="21" y2="24"  stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>'
    '<line x1="5" y1="27"  x2="21" y2="24"  stroke="#4A8FD4" stroke-width="0.6" opacity="0.6"/>'
    '<line x1="31" y1="-16" x2="44" y2="1"  stroke="#C9A84C" stroke-width="0.8" opacity="0.7"/>'
    '<line x1="31" y1="4"   x2="44" y2="4"  stroke="#C9A84C" stroke-width="0.8" opacity="0.7"/>'
    '<line x1="31" y1="24"  x2="44" y2="8"  stroke="#C9A84C" stroke-width="0.8" opacity="0.7"/>'
    '</g>'
    '<text x="122" y="50" font-family="Georgia,serif" font-size="38" font-weight="700">'
    '<tspan fill="#FFFFFF">Actuar</tspan><tspan fill="#C9A84C">IA</tspan>'
    '</text>'
    '<line x1="122" y1="58" x2="328" y2="58" stroke="#C9A84C" stroke-width="0.6" opacity="0.5"/>'
    '<text x="122" y="73" font-family="Georgia,serif" font-size="7.5" fill="#8A9BB0" letter-spacing="3">ACTUARIAL INTELLIGENCE PLATFORM</text>'
    '</svg>'
)
LOGO_URI = 'data:image/svg+xml;base64,' + base64.b64encode(LOGO_SVG.encode()).decode()


# =============================================================================
#  HELPERS
# =============================================================================

def _f(v, dec=0) -> str:
    """Formate un montant en euros."""
    if v is None:
        return '—'
    try:
        fv = float(v)
        if not np.isfinite(fv):
            return '—'
        sep = '\u202f'
        if dec == 0:
            return f"{fv:,.0f}\u202f€".replace(',', sep)
        return f"{fv:,.{dec}f}".replace(',', sep)
    except Exception:
        return '—'


def _pct(v, dec=1) -> str:
    """Formate un pourcentage."""
    if v is None:
        return '—'
    try:
        fv = float(v)
        return '—' if not np.isfinite(fv) else f"{fv:.{dec}f}\u202f%"
    except Exception:
        return '—'


def _s(v) -> str:
    """Convertit en string propre."""
    if v is None:
        return '—'
    return re.sub(r'\s+', ' ', str(v)).strip() or '—'


def _clean(txt) -> str:
    """Nettoie le texte des caractères parasites."""
    if not txt:
        return ''
    txt = re.sub(r'[■□▪▸►═╔╗╚╝║─]+', '', str(txt))
    txt = re.sub(r'={4,}', '', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()


def _statut_col(statut: str) -> str:
    """Retourne la couleur HTML associée au statut."""
    return {'VERT': VERT, 'AMBRE': AMBRE, 'ROUGE': ROUGE}.get(statut, GRIS)


def _statut_icon(statut: str) -> str:
    return {'VERT': '✅', 'AMBRE': '⚠️', 'ROUGE': '🔴'}.get(statut, 'ℹ️')


# =============================================================================
#  SYSTEM PROMPT CLAUDE API
# =============================================================================

SYSTEM_PROMPT = """\
Tu es un actuaire Non-Vie senior certifié par l'Institut des Actuaires (IA), \
expert en provisionnement Solvabilité 2 et IFRS 17, avec 20 ans d'expérience \
auprès de mutuelles, institutions de prévoyance et grands groupes d'assurance.

Tu rédiges le commentaire actuariel d'un rapport de provisionnement Non-Vie \
destiné à être présenté au Conseil d'Administration et à l'actuaire désigné. \
Ce rapport sera soumis à l'ACPR dans le cadre du reporting Solvabilité 2.

RÈGLES ABSOLUES :
0. FORMAT : §N — TITRE pour les sections, ### pour les sous-titres, \
**gras** pour les termes importants, - tirets pour les listes. \
PAS de tableaux Markdown. PAS de blockquotes >. Sépare les sections par une ligne vide.
1. LANGUE : Français professionnel. Anglais uniquement pour les termes consacrés.
2. RIGUEUR : Chaque affirmation est justifiée par les données fournies.
3. CHIFFRES : En euros avec séparateurs (ex : 2 526 597 €). Pourcentages avec une décimale.
4. RÉFÉRENCES : Art. 77 S2, Art. 105 S2, Guide IA 2023, Mack 1993, Clark 2003.
5. ALERTES : Ne jamais minimiser. Présenter avec l'implication réelle pour le bilan S2.
6. CAUSALITÉ : H1 rejetée (corr=0.52) → CL biaisé → BF retenu → impact X € sur BE.
7. INCERTITUDE : Toujours quantifier via CV ou intervalles de confiance.
8. POSTURE : Assertif mais prudent. Recommandations claires avec justification.
9. INTERDIT : Phrases génériques sans données. FAVORABLE si H1 rejetée ET BT ROUGE.

STRUCTURE OBLIGATOIRE EN 7 SECTIONS :
§1 — CONTEXTE ET QUALITÉ DES DONNÉES
§2 — VALIDATION DES HYPOTHÈSES ACTUARIELLES
§3 — RÉSULTATS PAR MÉTHODE ET CONVERGENCE
§4 — INCERTITUDE STOCHASTIQUE ET PROVISIONS DE PRÉCAUTION
§5 — BACK-TESTING ET QUALITÉ DU PROVISIONNEMENT HISTORIQUE
§6 — EFFETS CALENDAIRE ET RISQUES IDENTIFIÉS
§7 — CONCLUSION ET RECOMMANDATIONS POUR LE CONSEIL D'ADMINISTRATION\
"""


# =============================================================================
#  CONTEXTE POUR CLAUDE API
# =============================================================================

def _construire_contexte(
    n2: Dict, n3: Dict, n4: Dict,
    lob_label: str, arrete: str,
) -> str:
    """Construit le message utilisateur pour Claude API."""
    cl    = n3.get('chain_ladder', {})
    mk    = n3.get('mack', {})
    bf    = n3.get('bf', {})
    cc    = n3.get('cape_cod', {})
    clark = n3.get('clark', {})
    bz    = n3.get('barnett_zehnwirth', {})
    bt    = n3.get('backtesting', {})
    sc    = n4.get('scr', {})
    h1    = n2.get('h1_independance', {})
    h2    = n2.get('h2_stabilite', {})
    h3    = n2.get('h3_apriori_bf', {})
    h4    = n2.get('h4_homosc_bootstrap', {})
    pw    = n4.get('poids', {})

    BE  = float(n4.get('best_estimate', 0) or 0)
    SIG = float(mk.get('sigma_total', 0) or 0)
    CV  = float(n4.get('cv_inter_methodes', 0) or 0)
    P75 = float(n4.get('reserve_p75', 0) or 0)
    P90 = float(n4.get('reserve_p90', 0) or 0)
    P99 = float(n4.get('reserve_p99_5', 0) or 0)
    SCP = float(sc.get('scr_prov', BE * 0.30) if sc else BE * 0.30)
    SCR = SCP / BE * 100 if BE else 0

    lines = [
        f"DOSSIER DE PROVISIONNEMENT — {lob_label.upper()} — Arrêté {arrete}",
        "",
        "=== TRIANGLE ===",
        f"Dimensions : {n2.get('dimensions', '—')}",
        f"Méthode retenue : {n4.get('methode_facteurs', n2.get('methode_recommandee', '—'))}",
        "",
        "=== HYPOTHÈSES ===",
        f"H1 Indépendance : {'VALIDÉE' if h1.get('ok') else 'REJETÉE'} | corr_moy={h1.get('corr_moy', '—')} | score={h1.get('score', '—')}/100",
        f"  Message : {str(h1.get('message', ''))[:200]}",
        f"H2 Stabilité : {'VALIDÉE' if h2.get('ok') else 'REJETÉE'} | CV={h2.get('cv_moy', '—')} | score={h2.get('score', '—')}/100",
        f"H3 A priori BF : {'VALIDÉE' if h3.get('ok') else 'REJETÉE'} | LR={h3.get('lr_apriori', '—')} | score={h3.get('score', '—')}/100",
        f"H4 Homoscédasticité : {'VALIDÉE' if h4.get('ok') else 'REJETÉE'} | phi={h4.get('phi', '—')} | score={h4.get('score', '—')}/100",
        "",
        "=== RÉSULTATS PAR MÉTHODE ===",
        f"Chain Ladder     : {_f(cl.get('reserve_totale'))} | poids={_pct(pw.get('chain_ladder', 0)*100)}",
        f"Mack 1993        : {_f(mk.get('reserve_best_estimate'))} | poids={_pct(pw.get('mack', 0)*100)}",
        f"BF               : {_f(bf.get('reserve_totale'))} | poids={_pct(pw.get('bornhuetter_ferguson', 0)*100)}",
        f"Cape Cod         : {_f(cc.get('reserve_totale'))} | poids={_pct(pw.get('cape_cod', 0)*100)}",
        f"Clark LDF        : {_f(clark.get('reserve_be_clark'))} | courbe={clark.get('courbe_choisie', '—')} | tail={clark.get('tail_factor', '—')} | AIC={clark.get('aic_optimal', '—')}",
        f"BEST ESTIMATE S2 : {_f(BE)} | CV inter-méthodes={_pct(CV)}",
        "",
        "=== INCERTITUDE ===",
        f"σ Mack total : {_f(SIG)} | P75={_f(P75)} | P90={_f(P90)} | P99.5={_f(P99)}",
        "",
        "=== SCR PROVISIONS ===",
        f"SCR={_f(SCP)} | Ratio SCR/BE={_pct(SCR)}",
        "",
        "=== BACK-TESTING ===",
        f"Statut={bt.get('statut', '—')} | Score={bt.get('score_qualite', '—')}/100",
        f"N-1 : {bt.get('n_rouge_n1', 0)} rouge / {bt.get('n_ambre_n1', 0)} ambre | N-2 : {bt.get('n_rouge_n2', 0)} rouge / {bt.get('n_ambre_n2', 0)} ambre",
        f"Message : {str(bt.get('message', ''))[:300]}",
        "",
        "=== EFFETS CALENDAIRE ===",
        f"Statut={bz.get('statut', '—')} | Effets sig.={bz.get('n_effets_significatifs', 0)}/{bz.get('n_diagonales_evaluees', 0)}",
        f"Diagonales anormales : {', '.join(bz.get('diagonales_anormales', [])) or 'Aucune'}",
        f"Recommandation : {bz.get('recommandation', '—')}",
        "",
        "Rédige maintenant le commentaire actuariel complet selon la structure en 7 sections.",
    ]
    return '\n'.join(lines)


# =============================================================================
#  GÉNÉRATION NARRATION (3 NIVEAUX)
# =============================================================================

def _narration_claude_api(
    n2: Dict, n3: Dict, n4: Dict, lob_label: str, arrete: str,
) -> str:
    """Niveau 1 : Narration via Claude API."""
    try:
        import anthropic
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get('ANTHROPIC_API_KEY')
            except Exception:
                pass
        if not api_key:
            raise ValueError('ANTHROPIC_API_KEY non définie')
        client = anthropic.Anthropic(api_key=api_key)
        ctx    = _construire_contexte(n2, n3, n4, lob_label, arrete)
        resp   = client.messages.create(
            model      = 'claude-sonnet-4-6',
            max_tokens = 3000,
            system     = SYSTEM_PROMPT,
            messages   = [{'role': 'user', 'content': ctx}],
        )
        return resp.content[0].text
    except Exception as e:
        logger.warning(f'Claude API indisponible : {e}')
        raise


def _narration_templates(n4: Dict, commentaire: str) -> str:
    """Niveau 2 : Templates existants."""
    return _clean(commentaire) or _clean(n4.get('jugement', ''))


def _generer_narration(
    n2: Dict, n3: Dict, n4: Dict,
    commentaire: str, lob_label: str, arrete: str,
) -> Tuple[str, str]:
    """Orchestrateur 3 niveaux. Retourne (texte, source)."""
    try:
        txt = _narration_claude_api(n2, n3, n4, lob_label, arrete)
        if txt:
            return txt, 'claude_api'
    except Exception:
        pass
    try:
        txt = _narration_templates(n4, commentaire)
        if txt:
            return txt, 'templates'
    except Exception:
        pass
    return '', 'aucune'


# =============================================================================
#  RENDU MARKDOWN → HTML
# =============================================================================

def _md_to_html(texte: str) -> str:
    """Convertit le Markdown de Claude en HTML structuré."""
    if not texte:
        return '<p style="color:#999;font-style:italic;">Narration non disponible.</p>'

    txt = texte.strip()

    # §N — TITRE → h3 gold
    def _section(m):
        t = m.group(1).strip()
        return (
            '<h3 style="font-family:Georgia,serif;font-size:11pt;font-weight:700;'
            'color:#C9A84C;margin:24px 0 8px;border-bottom:1px solid rgba(201,168,76,0.3);'
            'padding-bottom:4px;">' + t + '</h3>'
        )
    txt = re.sub(r'(§\d+\s*[—\-–]\s*[^\n]+)', _section, txt)

    # ### Sous-titre → h4 navy
    def _h4(m):
        return (
            '<h4 style="font-family:Georgia,serif;font-size:10pt;font-weight:600;'
            'color:#0F2E52;margin:16px 0 6px;">' + m.group(1).strip() + '</h4>'
        )
    txt = re.sub(r'^###\s+(.+)$', _h4, txt, flags=re.MULTILINE)

    # ## Titre → h3 navy
    txt = re.sub(r'^##\s+(.+)$',
        lambda m: '<h3 style="color:#0F2E52;">' + m.group(1).strip() + '</h3>',
        txt, flags=re.MULTILINE)

    # --- → séparateur
    txt = re.sub(r'^---+$',
        '<hr style="border:none;border-top:1px solid #dde3ea;margin:16px 0;">',
        txt, flags=re.MULTILINE)

    # **gras** → strong
    txt = re.sub(r'\*\*(.+?)\*\*',
        lambda m: '<strong style="color:#0F2E52;">' + m.group(1) + '</strong>', txt)

    # *italique* → em
    txt = re.sub(r'\*(.+?)\*', lambda m: '<em>' + m.group(1) + '</em>', txt)

    # Puces - ou • → li
    txt = re.sub(r'^[-•]\s+(.+)$',
        lambda m: '<li style="margin:3px 0 3px 18px;">' + m.group(1) + '</li>',
        txt, flags=re.MULTILINE)

    # Regrouper les li consécutifs en ul
    txt = re.sub(
        r'(<li[^>]*>.*?</li>\n?)+',
        lambda m: '<ul style="margin:8px 0;">' + m.group(0) + '</ul>',
        txt, flags=re.DOTALL
    )

    # Paragraphes : double saut de ligne
    blocs = re.split(r'\n{2,}', txt)
    result = ''
    for bloc in blocs:
        bloc = bloc.strip()
        if not bloc:
            continue
        if bloc.startswith('<'):
            result += bloc + '\n'
        else:
            clean = bloc.replace('\n', ' ').strip()
            result += (
                '<p style="margin-bottom:10px;line-height:1.85;color:#2c3e50;">'
                + clean + '</p>\n'
            )
    return result or '<p>' + texte + '</p>'


# =============================================================================
#  CONSTRUCTION DES BLOCS HTML PAR SECTION
# =============================================================================

def _build_html_blocks(
    n2: Dict, n3: Dict, n4: Dict,
    narration: str, source_narration: str,
    lob: str, cli: str, arr: str, dt: str,
    audit_id: str, methode: str, statut: str,
    graphiques_html: Dict,
) -> Dict[str, str]:
    """
    Construit tous les blocs HTML séparément.
    Aucune f-string imbriquée ici — chaque bloc est une string simple.
    """
    cl    = n3.get('chain_ladder', {})
    mk    = n3.get('mack', {})
    bf    = n3.get('bf', {})
    cc    = n3.get('cape_cod', {})
    clark = n3.get('clark', {})
    bz    = n3.get('barnett_zehnwirth', {})
    bt    = n3.get('backtesting', {})
    sc    = n4.get('scr', {})
    h1    = n2.get('h1_independance', {})
    h2    = n2.get('h2_stabilite', {})
    h3    = n2.get('h3_apriori_bf', {})
    h4    = n2.get('h4_homosc_bootstrap', {})
    pw    = n4.get('poids', {})

    BE  = float(n4.get('best_estimate', 0) or 0)
    SIG = float(mk.get('sigma_total', 0) or 0)
    CV  = float(n4.get('cv_inter_methodes', 0) or 0)
    P75 = float(n4.get('reserve_p75', 0) or 0)
    P90 = float(n4.get('reserve_p90', 0) or 0)
    P99 = float(n4.get('reserve_p99_5', 0) or 0)
    SCP = float(sc.get('scr_prov', BE * 0.30) if sc else BE * 0.30)
    SCR = SCP / BE * 100 if BE else 0

    s_col  = _statut_col(statut)
    s_icon = _statut_icon(statut)

    b = {}  # dictionnaire des blocs

    # ── MÉTA PAGE DE GARDE ────────────────────────────────────────────────────
    b['statut_badge'] = (
        '<span style="display:inline-block;background:' + s_col + ';color:#fff;'
        'padding:6px 18px;border-radius:4px;font-size:9pt;font-weight:700;'
        'letter-spacing:1px;">' + s_icon + ' ' + statut + '</span>'
    )
    b['meta_grid'] = (
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:24px;'
        'border-top:1px solid rgba(201,168,76,0.3);padding-top:24px;margin-top:32px;">'

        '<div><div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;'
        'letter-spacing:1.5px;margin-bottom:4px;">Client</div>'
        '<div style="font-size:10pt;color:#fff;font-weight:500;">' + cli + '</div></div>'

        '<div><div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;'
        'letter-spacing:1.5px;margin-bottom:4px;">Arrêté</div>'
        '<div style="font-size:10pt;color:#fff;font-weight:500;">' + arr + '</div></div>'

        '<div><div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;'
        'letter-spacing:1.5px;margin-bottom:4px;">Méthode retenue</div>'
        '<div style="font-size:10pt;color:#fff;font-weight:500;">'
        + methode.replace('_', ' ').title() + '</div></div>'

        '<div><div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;'
        'letter-spacing:1.5px;margin-bottom:4px;">Best Estimate S2</div>'
        '<div style="font-size:13pt;color:#C9A84C;font-weight:700;">' + _f(BE) + '</div></div>'

        '<div><div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;'
        'letter-spacing:1.5px;margin-bottom:4px;">Date rapport</div>'
        '<div style="font-size:10pt;color:#fff;font-weight:500;">' + dt + '</div></div>'

        '<div><div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;'
        'letter-spacing:1.5px;margin-bottom:4px;">Audit ID</div>'
        '<div style="font-size:10pt;color:#fff;font-weight:500;">' + (audit_id or '—') + '</div></div>'

        '</div>'
    )

    # ── SECTION 1 : SYNTHÈSE ──────────────────────────────────────────────────
    b['kpi_grid'] = (
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0;">'

        '<div style="background:#0F2E52;border-radius:8px;padding:16px 14px;text-align:center;">'
        '<div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Best Estimate S2</div>'
        '<div style="font-family:Georgia,serif;font-size:16pt;font-weight:700;color:#fff;line-height:1.2;">' + _f(BE) + '</div>'
        '<div style="font-size:8pt;color:#C9A84C;margin-top:4px;">Art. 77 Directive S2</div>'
        '</div>'

        '<div style="background:#0F2E52;border-radius:8px;padding:16px 14px;text-align:center;">'
        '<div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">σ Mack total</div>'
        '<div style="font-family:Georgia,serif;font-size:16pt;font-weight:700;color:#fff;line-height:1.2;">' + _f(SIG) + '</div>'
        '<div style="font-size:8pt;color:#C9A84C;margin-top:4px;">CV inter-méthodes : ' + _pct(CV) + '</div>'
        '</div>'

        '<div style="background:#0F2E52;border-radius:8px;padding:16px 14px;text-align:center;">'
        '<div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">SCR Provisions</div>'
        '<div style="font-family:Georgia,serif;font-size:16pt;font-weight:700;color:#fff;line-height:1.2;">' + _f(SCP) + '</div>'
        '<div style="font-size:8pt;color:#C9A84C;margin-top:4px;">Ratio SCR/BE : ' + _pct(SCR) + '</div>'
        '</div>'

        '<div style="background:#0F2E52;border-radius:8px;padding:16px 14px;text-align:center;">'
        '<div style="font-size:7.5pt;color:#8A9BB0;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Provision P99.5</div>'
        '<div style="font-family:Georgia,serif;font-size:16pt;font-weight:700;color:#fff;line-height:1.2;">' + _f(P99) + '</div>'
        '<div style="font-size:8pt;color:#C9A84C;margin-top:4px;">P90 : ' + _f(P90) + '</div>'
        '</div>'

        '</div>'
    )
    b['graph_convergence'] = graphiques_html.get('g5_convergence', '')

    # ── SECTION 2 : MÉTHODES ─────────────────────────────────────────────────
    # Tableau méthodes
    rows_methodes = [
        ('Chain Ladder',         cl.get('reserve_totale'),          pw.get('chain_ladder', 0)*100,          n2.get('scores_confiance', {}).get('chain_ladder', '—')),
        ('Mack 1993',            mk.get('reserve_best_estimate'),   pw.get('mack', 0)*100,                  '—'),
        ('Bornhuetter-Ferguson', bf.get('reserve_totale'),          pw.get('bornhuetter_ferguson', 0)*100,  '—'),
        ('Cape Cod',             cc.get('reserve_totale'),          pw.get('cape_cod', 0)*100,              n2.get('scores_confiance', {}).get('cape_cod', '—')),
    ]
    tbl_m = (
        '<table style="width:100%;border-collapse:collapse;font-size:9pt;margin:16px 0;">'
        '<thead><tr style="background:#0F2E52;color:#fff;">'
        '<th style="padding:9px 12px;text-align:left;">Méthode</th>'
        '<th style="padding:9px 12px;">Réserve IBNR (€)</th>'
        '<th style="padding:9px 12px;">Poids BE</th>'
        '<th style="padding:9px 12px;">Score /100</th>'
        '<th style="padding:9px 12px;">Statut</th>'
        '</tr></thead><tbody>'
    )
    for idx, (nom, res, pds, score) in enumerate(rows_methodes):
        bg = '#f0f4f8' if idx % 2 == 1 else '#fff'
        tbl_m += (
            '<tr style="background:' + bg + ';">'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;font-weight:500;color:#0F2E52;">' + nom + '</td>'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;text-align:right;">' + _f(res) + '</td>'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;text-align:center;">' + _pct(pds) + '</td>'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;text-align:center;">' + _s(score) + '</td>'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;text-align:center;">✅</td>'
            '</tr>'
        )
    if clark.get('disponible'):
        clark_aic = _s(clark.get('aic_optimal'))
        tbl_m += (
            '<tr style="background:#fff;">'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;font-weight:500;color:#0F2E52;">Clark LDF (' + _s(clark.get('courbe_choisie')) + ')</td>'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;text-align:right;">' + _f(clark.get('reserve_be_clark')) + '</td>'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;text-align:center;">—</td>'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;text-align:center;font-size:8pt;">AIC=' + clark_aic + '</td>'
            '<td style="padding:8px 12px;border-bottom:1px solid #dde3ea;text-align:center;">ℹ️</td>'
            '</tr>'
        )
    tbl_m += (
        '<tr style="background:rgba(201,168,76,0.15);font-weight:700;">'
        '<td style="padding:9px 12px;">⭐ BEST ESTIMATE S2</td>'
        '<td style="padding:9px 12px;text-align:right;">' + _f(BE) + '</td>'
        '<td style="padding:9px 12px;text-align:center;">100\u202f%</td>'
        '<td style="padding:9px 12px;text-align:center;">—</td>'
        '<td style="padding:9px 12px;text-align:center;">→ Bilan S2</td>'
        '</tr>'
        '</tbody></table>'
    )
    b['tableau_methodes'] = tbl_m

    # Tableau incertitude
    tbl_i = (
        '<table style="width:100%;border-collapse:collapse;font-size:9pt;margin:16px 0;">'
        '<thead><tr style="background:#0F2E52;color:#fff;">'
        '<th style="padding:9px 12px;text-align:left;">Approche</th>'
        '<th style="padding:9px 12px;">BE (€)</th>'
        '<th style="padding:9px 12px;">P75 (€)</th>'
        '<th style="padding:9px 12px;">P90 (€)</th>'
        '<th style="padding:9px 12px;">P99.5 (€)</th>'
        '<th style="padding:9px 12px;">CV (%)</th>'
        '</tr></thead><tbody>'
        '<tr style="background:#fff;">'
        '<td style="padding:8px 12px;font-weight:500;color:#0F2E52;">Mack 1993 (analytique)</td>'
        '<td style="padding:8px 12px;text-align:right;">' + _f(BE) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">' + _f(P75) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">' + _f(P90) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">' + _f(P99) + '</td>'
        '<td style="padding:8px 12px;text-align:center;">' + _pct(SIG/BE*100 if BE else 0) + '</td>'
        '</tr>'
        '<tr style="background:#f0f4f8;">'
        '<td style="padding:8px 12px;font-weight:500;color:#0F2E52;">Bootstrap ODP (5\u202f000 sim.)</td>'
        '<td style="padding:8px 12px;text-align:right;">' + _f(n3.get('bootstrap', {}).get('be_bootstrap', BE)) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">' + _f(P75) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">' + _f(P90) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">' + _f(P99) + '</td>'
        '<td style="padding:8px 12px;text-align:center;">' + _pct(CV) + '</td>'
        '</tr>'
        '</tbody></table>'
    )
    b['tableau_incertitude'] = tbl_i
    b['graph_ibnr']      = graphiques_html.get('g4_ibnr', '')
    b['graph_bootstrap'] = graphiques_html.get('g6_bootstrap', '')
    b['graph_heatmap']   = graphiques_html.get('g1_heatmap', '')

    # ── SECTION 3 : HYPOTHÈSES ────────────────────────────────────────────────
    hyp_list = [
        ('H1 — Indépendance des facteurs (Mack 1993)', h1),
        ('H2 — Stabilité des facteurs de développement', h2),
        ('H3 — A priori BF / Cape Cod', h3),
        ('H4 — Homoscédasticité Bootstrap ODP', h4),
    ]
    hyp_html = ''
    for label, h in hyp_list:
        if not h:
            continue
        ok    = bool(h.get('ok', True))
        col   = VERT if ok else AMBRE
        icon  = '✅' if ok else '⚠️'
        lbl   = 'VALIDÉE' if ok else 'REJETÉE'
        score = _s(h.get('score'))
        msg   = _s(h.get('message'))
        hyp_html += (
            '<div style="display:flex;align-items:flex-start;gap:12px;padding:12px 16px;'
            'border-radius:6px;margin:8px 0;background:#f0f4f8;'
            'border-left:3px solid ' + col + ';">'
            '<div style="min-width:200px;font-size:8pt;font-weight:700;color:' + col + ';">'
            + icon + ' ' + label + '<br>'
            '<span style="color:#666;font-weight:400;">— ' + lbl + ' | Score ' + score + '/100</span>'
            '</div>'
            '<div style="font-size:9pt;color:#2c3e50;flex:1;">' + msg + '</div>'
            '</div>'
        )
    methode_block = (
        '<div style="background:#0F2E52;color:#fff;padding:14px 20px;border-radius:6px;margin-top:16px;">'
        '<span style="font-size:8pt;color:#C9A84C;text-transform:uppercase;letter-spacing:1px;">Méthode recommandée</span><br>'
        '<span style="font-size:11pt;font-weight:600;">' + methode.replace('_', ' ').title() + '</span>'
        '<span style="font-size:9pt;color:#8A9BB0;margin-left:16px;">'
        + _s(n2.get('raison_recommandation'))[:150] + '</span>'
        '</div>'
    )
    b['hypotheses']  = hyp_html
    b['methode_rec'] = methode_block

    # ── SECTION 4 : SCR ───────────────────────────────────────────────────────
    sigma_eiopa = _s(sc.get('sigma_eiopa', '10\u202f%') if sc else '10\u202f%')
    b['tableau_scr'] = (
        '<table style="width:100%;border-collapse:collapse;font-size:9pt;margin:16px 0;">'
        '<thead><tr style="background:#0F2E52;color:#fff;">'
        '<th style="padding:9px 12px;text-align:left;">Composante</th>'
        '<th style="padding:9px 12px;">Valeur</th>'
        '<th style="padding:9px 12px;text-align:left;">Référence réglementaire</th>'
        '</tr></thead><tbody>'
        '<tr><td style="padding:8px 12px;font-weight:500;">Best Estimate S2</td>'
        '<td style="padding:8px 12px;text-align:center;">' + _f(BE) + '</td>'
        '<td style="padding:8px 12px;">Art. 77 Directive Solvabilité 2</td></tr>'
        '<tr style="background:#f0f4f8;"><td style="padding:8px 12px;font-weight:500;">Facteur σ EIOPA</td>'
        '<td style="padding:8px 12px;text-align:center;">' + sigma_eiopa + '</td>'
        '<td style="padding:8px 12px;">' + lob + ' (Annexe II, Règlement 2015/35)</td></tr>'
        '<tr><td style="padding:8px 12px;font-weight:500;">SCR Provisions</td>'
        '<td style="padding:8px 12px;text-align:center;">' + _f(SCP) + '</td>'
        '<td style="padding:8px 12px;">SCR = 3 × σ(LoB) × BE (Art. 105)</td></tr>'
        '<tr style="background:rgba(201,168,76,0.15);font-weight:700;">'
        '<td style="padding:9px 12px;">Ratio SCR / BE</td>'
        '<td style="padding:9px 12px;text-align:center;">' + _pct(SCR) + '</td>'
        '<td style="padding:9px 12px;">Cible pratique marché : &lt; 35\u202f%</td></tr>'
        '</tbody></table>'
    )

    # ── SECTION 5 : BACK-TESTING ──────────────────────────────────────────────
    bt_statut = _s(bt.get('statut'))
    bt_col    = _statut_col(bt_statut)
    bt_score  = _s(bt.get('score_qualite'))

    b['bt_kpis'] = (
        '<div style="display:flex;gap:16px;margin-bottom:16px;flex-wrap:wrap;">'

        '<div style="background:' + bt_col + ';color:#fff;padding:10px 20px;border-radius:6px;text-align:center;">'
        '<div style="font-size:8pt;opacity:0.8;">Statut</div>'
        '<div style="font-size:14pt;font-weight:700;">' + bt_statut + '</div>'
        '</div>'

        '<div style="background:#0F2E52;color:#fff;padding:10px 20px;border-radius:6px;text-align:center;">'
        '<div style="font-size:8pt;color:#8A9BB0;">Score qualité</div>'
        '<div style="font-size:14pt;font-weight:700;color:#C9A84C;">' + bt_score + '/100</div>'
        '</div>'

        '<div style="background:#0F2E52;color:#fff;padding:10px 20px;border-radius:6px;text-align:center;">'
        '<div style="font-size:8pt;color:#8A9BB0;">Alertes N-1</div>'
        '<div style="font-size:14pt;font-weight:700;">'
        + str(bt.get('n_rouge_n1', 0)) + ' 🔴  '
        + str(bt.get('n_ambre_n1', 0)) + ' 🟡</div>'
        '</div>'

        '<div style="background:#0F2E52;color:#fff;padding:10px 20px;border-radius:6px;text-align:center;">'
        '<div style="font-size:8pt;color:#8A9BB0;">Alertes N-2</div>'
        '<div style="font-size:14pt;font-weight:700;">'
        + str(bt.get('n_rouge_n2', 0)) + ' 🔴  '
        + str(bt.get('n_ambre_n2', 0)) + ' 🟡</div>'
        '</div>'

        '</div>'
    )

    # Tableau boni/mali N-1
    tbl_bt_n1 = _build_tableau_bonimaili(bt, horizon='n1')
    tbl_bt_n2 = _build_tableau_bonimaili(bt, horizon='n2')
    b['tableau_bt_n1']  = tbl_bt_n1
    b['tableau_bt_n2']  = tbl_bt_n2
    b['graph_bt']       = graphiques_html.get('g14_backtesting', '')
    b['bt_message']     = (
        '<div style="background:#f0f4f8;border-left:3px solid ' + bt_col + ';'
        'padding:12px 16px;border-radius:0 6px 6px 0;margin-top:12px;font-size:9pt;color:#2c3e50;">'
        + _s(bt.get('message'))[:500] + '</div>'
    )

    # ── SECTION 6 : EFFETS CALENDAIRE ────────────────────────────────────────
    bz_statut = _s(bz.get('statut'))
    bz_col    = _statut_col(bz_statut)
    n_sig     = int(bz.get('n_effets_significatifs', 0))
    n_eval    = int(bz.get('n_diagonales_evaluees', 0))

    bz_alertes = ''
    if n_sig == 0:
        bz_alertes = (
            '<div style="border-left:3px solid #27AE60;background:rgba(39,174,96,0.06);'
            'padding:10px 14px;border-radius:0 4px 4px 0;margin:8px 0;font-size:9pt;">'
            '✅ Aucun effet calendaire significatif détecté sur '
            + str(n_eval) + ' diagonale(s) — triangle conforme à l\'hypothèse d\'indépendance.'
            '</div>'
        )
    else:
        forts   = [e for e in bz.get('effets_calendaire', []) if e.get('significatif') and e.get('niveau') in ('FORT', 'MODÉRÉ')]
        faibles = [e for e in bz.get('effets_calendaire', []) if e.get('significatif') and e.get('niveau') == 'FAIBLE']
        for e in forts:
            icon = '🔴' if e.get('niveau') == 'FORT' else '⚠️'
            col_e = ROUGE if e.get('niveau') == 'FORT' else AMBRE
            bz_alertes += (
                '<div style="border-left:3px solid ' + col_e + ';background:rgba(192,57,43,0.05);'
                'padding:10px 14px;border-radius:0 4px 4px 0;margin:8px 0;font-size:9pt;">'
                + icon + ' ' + _s(e.get('annee_label')) + ' : '
                + str(round(e.get('amplitude_pct', 0), 1)) + '% ('
                + _s(e.get('sens')) + ', ' + _s(e.get('niveau')) + ')'
                '</div>'
            )
        if faibles:
            n_f = len(faibles)
            annees_f = ', '.join(_s(e.get('annee_label')) for e in faibles[:3])
            suite = (' et ' + str(n_f - 3) + ' autre(s)') if n_f > 3 else ''
            bz_alertes += (
                '<div style="border-left:3px solid #F39C12;background:rgba(243,156,18,0.05);'
                'padding:10px 14px;border-radius:0 4px 4px 0;margin:8px 0;font-size:9pt;">'
                'ℹ️ ' + str(n_f) + ' diagonale(s) avec effet FAIBLE (&lt;8\u202f%) : '
                + annees_f + suite + ' — surveillance recommandée.'
                '</div>'
            )
    b['bz_alertes'] = bz_alertes
    b['bz_reco']    = (
        '<div style="margin-top:12px;font-size:9pt;color:#0F2E52;">'
        '<strong>Recommandation :</strong> ' + _s(bz.get('recommandation')) + '</div>'
    ) if n_sig > 0 else ''

    # ── SECTION 7 : COMMENTAIRE ACTUARIEL ────────────────────────────────────
    try:
        narration_html = _md_to_html(narration)
    except Exception as e_nar:
        logger.warning(f'_md_to_html échoué : {e_nar}')
        narration_html = '<p>' + _clean(narration) + '</p>' if narration else \
            '<p style="color:#999;font-style:italic;">Narration non disponible.</p>'

    source_labels = {
        'claude_api': '✨ Narration générée par Claude — ActuarIA Intelligence',
        'templates':  '📝 Narration générée en mode standard',
        'aucune':     '',
    }
    b['narration']        = narration_html
    b['narration_source'] = (
        '<div style="font-size:7.5pt;color:#8A9BB0;font-style:italic;margin-top:16px;'
        'border-top:1px solid #e0e0e0;padding-top:8px;">'
        + source_labels.get(source_narration, '') + '</div>'
    ) if source_narration != 'aucune' else ''

    # ── SECTION 8 : JUGEMENT ─────────────────────────────────────────────────
    alertes_html = ''
    for a in n4.get('alertes', n2.get('alertes', [])):
        at = _clean(str(a))
        if at:
            alertes_html += (
                '<div style="border-left:3px solid #C0392B;background:rgba(192,57,43,0.05);'
                'padding:10px 14px;border-radius:0 4px 4px 0;margin:8px 0;font-size:9pt;">'
                + at + '</div>'
            )
    b['alertes'] = alertes_html

    recs_html = ''
    for i, r in enumerate(n4.get('recommandations', []), 1):
        rt = _clean(str(r))
        if rt:
            recs_html += (
                '<div style="padding:8px 0;border-bottom:1px solid #eee;font-size:9pt;">'
                '<span style="color:#C9A84C;font-weight:700;">' + str(i) + '.  </span>'
                + rt + '</div>'
            )
    b['recommandations'] = recs_html

    avis_txt = _clean(n4.get('avis_actuariel', ''))
    if avis_txt:
        avis_col = ROUGE if 'DÉFAVORABLE' in avis_txt.upper() else VERT
        b['avis'] = (
            '<div style="background:' + avis_col + ';color:#fff;padding:14px 20px;'
            'border-radius:6px;margin-top:20px;font-size:10pt;font-weight:600;">'
            + avis_txt + '</div>'
        )
    else:
        b['avis'] = ''

    # ── PIED DE PAGE ─────────────────────────────────────────────────────────
    b['pied_info'] = cli + ' · ' + lob + ' · Arrêté ' + arr + ' · Audit ID : ' + (audit_id or '—') + ' · ' + dt

    return b


def _build_tableau_bonimaili(bt: Dict, horizon: str) -> str:
    """Construit le tableau HTML des boni/mali de liquidation."""
    key_data = bt.get('tableau_' + horizon, bt.get('details_' + horizon, []))
    if not key_data:
        return '<p style="font-size:9pt;color:#8A9BB0;font-style:italic;">Données de back-testing non disponibles.</p>'

    seuil = 0.15  # ±15%
    html = (
        '<table style="width:100%;border-collapse:collapse;font-size:8.5pt;margin:12px 0;">'
        '<thead><tr style="background:#0F2E52;color:#fff;">'
        '<th style="padding:8px 10px;text-align:left;">Année</th>'
        '<th style="padding:8px 10px;">Observé N (€)</th>'
        '<th style="padding:8px 10px;">Ultimate N-' + ('1' if horizon == 'n1' else '2') + ' (€)</th>'
        '<th style="padding:8px 10px;">Boni/Mali (€)</th>'
        '<th style="padding:8px 10px;">Écart (%)</th>'
        '<th style="padding:8px 10px;">Statut</th>'
        '</tr></thead><tbody>'
    )
    if isinstance(key_data, list):
        for idx, row in enumerate(key_data):
            if not isinstance(row, dict):
                continue
            annee  = _s(row.get('annee', row.get('year', '—')))
            obs    = row.get('observe_n', row.get('paid_n', 0))
            ult    = row.get('ultimate_' + horizon, row.get('ultimate', 0))
            bm     = row.get('boni_mali_' + horizon, row.get('boni_mali', 0))
            ecart  = row.get('ecart_pct_' + horizon, row.get('ecart_pct', 0))
            try:
                ecart_f = float(ecart)
                if abs(ecart_f) > seuil * 100:
                    statut_icon = '🔴'
                    row_col = 'rgba(192,57,43,0.05)'
                elif abs(ecart_f) > seuil * 100 * 0.6:
                    statut_icon = '🟡'
                    row_col = 'rgba(243,156,18,0.05)'
                else:
                    statut_icon = '✅'
                    row_col = '#fff' if idx % 2 == 0 else '#f0f4f8'
            except Exception:
                statut_icon = '—'
                row_col = '#fff' if idx % 2 == 0 else '#f0f4f8'

            html += (
                '<tr style="background:' + row_col + ';">'
                '<td style="padding:7px 10px;font-weight:500;">' + annee + '</td>'
                '<td style="padding:7px 10px;text-align:right;">' + _f(obs) + '</td>'
                '<td style="padding:7px 10px;text-align:right;">' + _f(ult) + '</td>'
                '<td style="padding:7px 10px;text-align:right;">' + _f(bm) + '</td>'
                '<td style="padding:7px 10px;text-align:center;">' + _pct(ecart) + '</td>'
                '<td style="padding:7px 10px;text-align:center;">' + statut_icon + '</td>'
                '</tr>'
            )
    html += '</tbody></table>'
    return html


def _wrap_graphique(html_g: str, titre: str) -> str:
    """Encapsule un graphique Plotly dans un bloc HTML."""
    if not html_g:
        return ''
    return (
        '<div style="font-family:Georgia,serif;font-size:10pt;font-weight:600;'
        'color:#C9A84C;margin:20px 0 10px;">' + titre + '</div>'
        '<div style="margin:12px 0;border:1px solid #e0e5ec;border-radius:6px;overflow:hidden;">'
        + html_g + '</div>'
    )


# =============================================================================
#  CSS DU RAPPORT
# =============================================================================

def _css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Inter:wght@300;400;500;600&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', sans-serif;
  font-size: 10pt;
  color: #1a1a2e;
  background: #f4f6f9;
  line-height: 1.7;
}

.rapport-container {
  max-width: 920px;
  margin: 0 auto;
  background: white;
  box-shadow: 0 2px 20px rgba(0,0,0,0.08);
}

/* ── PAGE DE GARDE ── */
.page-garde {
  background: linear-gradient(160deg, #0F2E52 0%, #1A3F6B 60%, #0F2E52 100%);
  padding: 0;
  position: relative;
  min-height: 520px;
  display: flex;
  flex-direction: column;
  page-break-after: always;
}

.garde-top {
  padding: 36px 60px 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.garde-hero {
  flex: 1;
  padding: 60px 60px 0;
  text-align: center;
}

.garde-titre {
  font-family: 'EB Garamond', serif;
  font-size: 48pt;
  font-weight: 700;
  color: #fff;
  line-height: 1.1;
  margin-bottom: 12px;
  letter-spacing: -1px;
}

.garde-branche {
  font-family: 'EB Garamond', serif;
  font-size: 22pt;
  color: #C9A84C;
  margin-bottom: 28px;
  letter-spacing: 0.5px;
}

.garde-separateur {
  width: 120px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #C9A84C, transparent);
  margin: 0 auto 28px;
}

.garde-footer {
  padding: 28px 60px 36px;
  margin-top: auto;
}

.confidentiel {
  font-size: 8pt;
  color: #C0392B;
  font-weight: 600;
  letter-spacing: 2px;
  border: 1px solid #C0392B;
  padding: 4px 10px;
  border-radius: 3px;
}

/* ── CORPS ── */
.rapport-body { padding: 40px 60px; }

.section { margin-bottom: 40px; page-break-inside: avoid; }

.section-titre {
  font-family: 'EB Garamond', serif;
  font-size: 16pt;
  font-weight: 700;
  color: #0F2E52;
  border-bottom: 2px solid #C9A84C;
  padding-bottom: 8px;
  margin-bottom: 20px;
}

.narration {
  background: #f9fafc;
  border-left: 3px solid #C9A84C;
  padding: 24px 28px;
  border-radius: 0 6px 6px 0;
  margin: 20px 0;
}

.narration p { margin-bottom: 12px; line-height: 1.8; color: #2c3e50; }

/* ── PIED ── */
.pied-de-page {
  background: #0F2E52;
  padding: 20px 60px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

@media print {
  body { background: white; }
  .rapport-container { box-shadow: none; }
  .section { page-break-inside: avoid; }
  .page-garde { page-break-after: always; }
}
</style>"""


# =============================================================================
#  EXPORT HTML
# =============================================================================

def export_html(
    n1: Dict, n2: Dict, n3: Dict, n4: Dict,
    commentaire='', ref_client='', arrete='',
    audit_id='', lob_label='', graphiques=None,
) -> str:
    """Génère le rapport complet au format HTML."""
    try:
        n1=n1 or {}; n2=n2 or {}; n3=n3 or {}; n4=n4 or {}

        dt      = datetime.now().strftime('%d/%m/%Y')
        arr     = arrete or dt
        cli     = ref_client or 'À renseigner'
        lob     = _lob(lob_label or n2.get('lob_label', '') or n2.get('lob', ''))
        methode = n4.get('methode_facteurs', n2.get('methode_recommandee', '—'))
        statut  = n4.get('statut', 'AMBRE')

        # Narration
        narration, source = _generer_narration(n2, n3, n4, commentaire, lob, arr)

        # Graphiques Plotly → HTML
        graphiques_html = {}
        if graphiques:
            try:
                import plotly.io as pio
                for nom, fig in graphiques.items():
                    try:
                        graphiques_html[nom] = pio.to_html(
                            fig, full_html=False, include_plotlyjs=False,
                            config={'displayModeBar': False},
                        )
                    except Exception:
                        pass
            except ImportError:
                pass

        # Construire tous les blocs HTML
        b = _build_html_blocks(
            n2, n3, n4, narration, source,
            lob, cli, arr, dt, audit_id, methode, statut,
            graphiques_html,
        )

        # Assembler le HTML final — aucune logique dans le template
        html = (
            '<!DOCTYPE html>\n<html lang="fr">\n<head>\n'
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '<title>Rapport Actuariel — ' + cli + ' — ' + arr + '</title>\n'
            '<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist@2.26.0/plotly.min.js"></script>\n'
            + _css() +
            '\n</head>\n<body>\n'
            '<div class="rapport-container">\n\n'

            # ── PAGE DE GARDE ──────────────────────────────────────────────
            '<div class="page-garde">\n'
            '  <div class="garde-top">\n'
            '    <img src="' + LOGO_URI + '" alt="ActuarIA" height="60"/>\n'
            '    <span class="confidentiel">CONFIDENTIEL</span>\n'
            '  </div>\n'
            '  <div class="garde-hero">\n'
            '    <div class="garde-titre">Rapport de<br>Provisionnement<br>Non-Vie</div>\n'
            '    <div class="garde-branche">' + lob + '</div>\n'
            '    <div class="garde-separateur"></div>\n'
            '    <div>' + b['statut_badge'] + '</div>\n'
            '  </div>\n'
            '  <div class="garde-footer">\n'
            + b['meta_grid'] +
            '  </div>\n'
            '</div>\n\n'

            # ── CORPS ──────────────────────────────────────────────────────
            '<div class="rapport-body">\n\n'

            # Section 1
            '<div class="section">\n'
            '<div class="section-titre">1. Synthèse exécutive</div>\n'
            + b['kpi_grid']
            + _wrap_graphique(b['graph_convergence'], 'Convergence des méthodes — Best Estimate S2')
            + '\n</div>\n\n'

            # Section 2
            '<div class="section">\n'
            '<div class="section-titre">2. Résultats par méthode actuarielle</div>\n'
            + b['tableau_methodes']
            + '<div style="font-family:Georgia,serif;font-size:10pt;font-weight:600;color:#C9A84C;margin:20px 0 10px;">Incertitude stochastique — Bootstrap ODP &amp; Mack 1993</div>\n'
            + b['tableau_incertitude']
            + _wrap_graphique(b['graph_heatmap'], 'Triangle de développement cumulé')
            + _wrap_graphique(b['graph_ibnr'], 'IBNR par année de survenance')
            + _wrap_graphique(b['graph_bootstrap'], 'Distribution Bootstrap ODP — Quantiles de réserve')
            + '\n</div>\n\n'

            # Section 3
            '<div class="section">\n'
            '<div class="section-titre">3. Validation des hypothèses actuarielles</div>\n'
            + b['hypotheses']
            + b['methode_rec']
            + '\n</div>\n\n'

            # Section 4
            '<div class="section">\n'
            '<div class="section-titre">4. SCR Provisions — Art. 105 Solvabilité 2</div>\n'
            + b['tableau_scr']
            + '\n</div>\n\n'

            # Section 5
            '<div class="section">\n'
            '<div class="section-titre">5. Back-testing — Boni/Mali de liquidation</div>\n'
            + b['bt_kpis']
            + '<div style="font-family:Georgia,serif;font-size:10pt;font-weight:600;color:#C9A84C;margin:20px 0 8px;">Tableau N-1 — Horizon un an</div>\n'
            + b['tableau_bt_n1']
            + '<div style="font-family:Georgia,serif;font-size:10pt;font-weight:600;color:#C9A84C;margin:20px 0 8px;">Tableau N-2 — Horizon deux ans</div>\n'
            + b['tableau_bt_n2']
            + _wrap_graphique(b['graph_bt'], 'Boni/Mali de liquidation — Horizons N-1 et N-2')
            + b['bt_message']
            + '\n</div>\n\n'

            # Section 6
            '<div class="section">\n'
            '<div class="section-titre">6. Effets calendaire — Barnett-Zehnwirth (1998)</div>\n'
            + b['bz_alertes']
            + b['bz_reco']
            + '\n</div>\n\n'

            # Section 7
            '<div class="section">\n'
            '<div class="section-titre">7. Commentaire actuariel</div>\n'
            '<div class="narration">\n'
            + b['narration']
            + b['narration_source']
            + '\n</div>\n</div>\n\n'

            # Section 8
            '<div class="section">\n'
            '<div class="section-titre">8. Jugement actuariel &amp; Recommandations</div>\n'
            + b['alertes']
            + b['recommandations']
            + b['avis']
            + '\n</div>\n\n'

            '</div>\n\n'

            # ── PIED DE PAGE ───────────────────────────────────────────────
            '<div class="pied-de-page">\n'
            '  <img src="' + LOGO_URI + '" alt="ActuarIA" height="28"/>\n'
            '  <div style="font-size:8pt;color:#8A9BB0;text-align:right;">\n'
            '    ' + b['pied_info'] + '<br>\n'
            '    <span style="color:#C0392B;font-weight:600;">CONFIDENTIEL — USAGE STRICTEMENT ACTUARIEL</span>\n'
            '  </div>\n'
            '</div>\n\n'

            '</div>\n</body>\n</html>'
        )

        logger.info(f'HTML : {len(html):,} chars — narration={source}')
        return html

    except Exception as e:
        logger.error(f'export_html échoué : {e}', exc_info=True)
        return '<html><body><h1>Erreur génération rapport</h1><p>' + str(e) + '</p></body></html>'


# =============================================================================
#  EXPORT PDF
# =============================================================================

def export_pdf(
    n1=None, n2=None, n3=None, n4=None,
    commentaire='', ref_client='', arrete='',
    audit_id='', lob_label='', graphiques=None, **kwargs,
) -> bytes:
    """Génère le rapport PDF via weasyprint."""
    n1=n1 or {}; n2=n2 or {}; n3=n3 or {}; n4=n4 or {}
    try:
        from weasyprint import HTML as WH
        html = export_html(n1, n2, n3, n4, commentaire, ref_client, arrete, audit_id, lob_label, graphiques)
        pdf  = WH(string=html).write_pdf()
        logger.info(f'PDF : {len(pdf):,} bytes')
        return pdf
    except ImportError:
        logger.error('weasyprint non installé')
        return b''
    except Exception as e:
        logger.error(f'export_pdf échoué : {e}', exc_info=True)
        return b''


# =============================================================================
#  EXPORT WORD
# =============================================================================

def export_word(
    n1: Dict, n2: Dict, n3: Dict, n4: Dict,
    commentaire='', ref_client='', arrete='',
    audit_id='', lob_label='', graphiques=None,
) -> bytes:
    """Génère le rapport Word (.docx)."""
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError as e:
        logger.error(f'python-docx absent : {e}')
        return b''

    try:
        n1=n1 or {}; n2=n2 or {}; n3=n3 or {}; n4=n4 or {}

        def rgb(h):
            h = h.lstrip('#')
            return RGBColor(int(h[:2],16), int(h[2:4],16), int(h[4:],16))

        NR=rgb(NAVY); GR=rgb(GOLD); BR=rgb(BLANC)
        GrR=rgb(GRIS); RgR=rgb(ROUGE); VR=rgb(VERT); AR=rgb(AMBRE)

        dt      = datetime.now().strftime('%d/%m/%Y')
        arr     = arrete or dt
        cli     = ref_client or 'À renseigner'
        lob     = _lob(lob_label or n2.get('lob_label','') or n2.get('lob',''))
        methode = n4.get('methode_facteurs', n2.get('methode_recommandee','—'))
        statut  = n4.get('statut','AMBRE')
        narration, source = _generer_narration(n2, n3, n4, commentaire, lob, arr)

        cl  = n3.get('chain_ladder',{});  mk = n3.get('mack',{})
        bf  = n3.get('bf',{});            cc = n3.get('cape_cod',{})
        sc  = n4.get('scr',{});           pw = n4.get('poids',{})
        bt  = n3.get('backtesting',{});   bz = n3.get('barnett_zehnwirth',{})
        h1  = n2.get('h1_independance',{}); h2 = n2.get('h2_stabilite',{})
        h3  = n2.get('h3_apriori_bf',{});  h4 = n2.get('h4_homosc_bootstrap',{})

        BE  = float(n4.get('best_estimate',0) or 0)
        SIG = float(mk.get('sigma_total',0) or 0)
        CV  = float(n4.get('cv_inter_methodes',0) or 0)
        P75 = float(n4.get('reserve_p75',0) or 0)
        P90 = float(n4.get('reserve_p90',0) or 0)
        P99 = float(n4.get('reserve_p99_5',0) or 0)
        SCP = float(sc.get('scr_prov',BE*0.30) if sc else BE*0.30)
        SCR = SCP/BE*100 if BE else 0

        doc = Document()
        for s in doc.sections:
            s.top_margin=Cm(2); s.bottom_margin=Cm(2)
            s.left_margin=Cm(2.5); s.right_margin=Cm(2.5)

        def _bg(cell, hex6):
            tc=cell._tc; tcp=tc.get_or_add_tcPr()
            sd=OxmlElement('w:shd')
            sd.set(qn('w:fill'), hex6.lstrip('#'))
            sd.set(qn('w:color'),'auto')
            sd.set(qn('w:val'),'clear')
            tcp.append(sd)

        def _run(p, txt, bold=False, italic=False, sz=10, col=None):
            r=p.add_run(str(txt)); r.bold=bold; r.italic=italic
            r.font.size=Pt(sz)
            if col: r.font.color.rgb=col
            return r

        def _h(txt, lv=1, col=None, sb=8, sa=3):
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(sb)
            p.paragraph_format.space_after=Pt(sa)
            sz={1:16,2:12,3:10}.get(lv,10)
            c=col or (NR if lv==1 else GR)
            _run(p,txt,bold=True,sz=sz,col=c)

        def _sep(col='C9A84C'):
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(2)
            p.paragraph_format.space_after=Pt(2)
            pPr=p._p.get_or_add_pPr(); pBdr=OxmlElement('w:pBdr')
            b=OxmlElement('w:bottom')
            b.set(qn('w:val'),'single'); b.set(qn('w:sz'),'6')
            b.set(qn('w:space'),'1'); b.set(qn('w:color'),col)
            pBdr.append(b); pPr.append(pBdr)

        def _tbl(heads, rows, ws=None, hbg='0F2E52'):
            from docx.enum.table import WD_ALIGN_VERTICAL
            t=doc.add_table(rows=1+len(rows), cols=len(heads))
            t.style='Table Grid'
            for i,hd in enumerate(heads):
                c=t.rows[0].cells[i]; _bg(c,hbg)
                pp=c.paragraphs[0]; pp.alignment=WD_ALIGN_PARAGRAPH.CENTER
                r=pp.add_run(str(hd)); r.bold=True; r.font.size=Pt(9)
                r.font.color.rgb=BR
            for ri,row in enumerate(rows):
                for ci,v in enumerate(row):
                    c=t.rows[ri+1].cells[ci]
                    if ri%2==1: _bg(c,'EEF2F7')
                    pp=c.paragraphs[0]; pp.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    r=pp.add_run(str(v) if v is not None else '—')
                    r.font.size=Pt(9)
            if ws:
                for i,w in enumerate(ws):
                    for row in t.rows:
                        row.cells[i].width=Cm(w)
            doc.add_paragraph().paragraph_format.space_after=Pt(2)

        # Page de garde
        try:
            import cairosvg
            logo_png = cairosvg.svg2png(bytestring=LOGO_SVG.encode(), output_width=280)
            doc.add_picture(io.BytesIO(logo_png), width=Cm(7))
        except Exception:
            p=doc.add_paragraph()
            _run(p,'Actuar',bold=True,sz=26,col=NR)
            _run(p,'IA',bold=True,sz=26,col=GR)

        doc.add_paragraph()
        p=doc.add_paragraph()
        p.alignment=WD_ALIGN_PARAGRAPH.LEFT
        _run(p,'RAPPORT DE PROVISIONNEMENT NON-VIE\n',bold=True,sz=20,col=NR)
        _run(p,lob,bold=True,sz=14,col=GR)
        doc.add_paragraph()

        s_col_r = VR if statut=='VERT' else AR if statut=='AMBRE' else RgR
        p=doc.add_paragraph()
        _run(p,'Statut : ',sz=11,col=NR)
        _run(p,statut,bold=True,sz=11,col=s_col_r)
        doc.add_paragraph()

        _tbl(
            ['Client','Branche','Méthode','Arrêté'],
            [[cli, lob, methode.replace('_',' ').title(), arr]],
            ws=[3.5,4.0,4.0,2.5]
        )
        doc.add_page_break()

        # 1. Synthèse
        _h('1. Synthèse exécutive'); _sep()
        _tbl(
            ['Indicateur','Valeur','Indicateur','Valeur'],
            [
                ['Best Estimate S2',_f(BE),'σ Mack total',_f(SIG)],
                ['Provision P75',_f(P75),'CV inter-méthodes',_pct(CV)],
                ['Provision P90',_f(P90),'SCR Provisions',_f(SCP)],
                ['Provision P99.5',_f(P99),'Ratio SCR/BE',_pct(SCR)],
            ],
            ws=[4.5,3.5,4.5,3.5]
        )
        doc.add_page_break()

        # 2. Résultats
        _h('2. Résultats par méthode actuarielle'); _sep()
        _tbl(
            ['Méthode','Réserve IBNR (€)','Poids BE','Score /100','Statut'],
            [
                ['Chain Ladder',_f(cl.get('reserve_totale')),_pct(pw.get('chain_ladder',0)*100),str(n2.get('scores_confiance',{}).get('chain_ladder','—')),'✅'],
                ['Mack 1993',_f(mk.get('reserve_best_estimate')),_pct(pw.get('mack',0)*100),'—','✅'],
                ['Bornhuetter-Ferguson',_f(bf.get('reserve_totale')),_pct(pw.get('bornhuetter_ferguson',0)*100),'—','✅'],
                ['Cape Cod',_f(cc.get('reserve_totale')),_pct(pw.get('cape_cod',0)*100),str(n2.get('scores_confiance',{}).get('cape_cod','—')),'✅'],
                ['BEST ESTIMATE S2',_f(BE),'100 %','—','→ Bilan S2'],
            ],
            ws=[4.5,3.5,2.5,2.5,3.0]
        )
        doc.add_page_break()

        # 3. Hypothèses
        _h('3. Validation des hypothèses actuarielles'); _sep()
        rows_h=[]
        for lbl,h in [('H1 Indépendance',h1),('H2 Stabilité',h2),('H3 A priori BF',h3),('H4 Homoscédasticité',h4)]:
            if not h: continue
            ok=bool(h.get('ok',True))
            h_score=str(h.get('score','—'))
            h_msg=str(h.get('message',''))[:80]
            rows_h.append([lbl,'VALIDÉE' if ok else 'REJETÉE',h_score+'/100',h_msg])
        if rows_h:
            _tbl(['Hypothèse','Résultat','Score','Message'],rows_h,ws=[4.0,2.5,2.0,7.5])
        doc.add_page_break()

        # 4. SCR
        _h('4. SCR Provisions — Art. 105 S2'); _sep()
        _tbl(
            ['Composante','Valeur','Référence'],
            [
                ['Best Estimate S2',_f(BE),'Art. 77 S2'],
                ['Facteur σ EIOPA','10 %','LoB : '+lob],
                ['SCR Provisions',_f(SCP),'3 × σ × BE'],
                ['Ratio SCR/BE',_pct(SCR),'< 35 %'],
            ],
            ws=[4.5,3.5,8.0]
        )
        doc.add_page_break()

        # 5. Back-testing
        _h('5. Back-testing — Boni/Mali de liquidation'); _sep()
        bt_score_w = str(bt.get('score_qualite','—'))
        bt_r_n1 = str(bt.get('n_rouge_n1',0))
        bt_a_n1 = str(bt.get('n_ambre_n1',0))
        bt_r_n2 = str(bt.get('n_rouge_n2',0))
        bt_a_n2 = str(bt.get('n_ambre_n2',0))
        p=doc.add_paragraph()
        s_bt_col = VR if bt.get('statut')=='VERT' else AR if bt.get('statut')=='AMBRE' else RgR
        _run(p,'Statut : ',sz=9,col=NR)
        _run(p,str(bt.get('statut','—')),bold=True,sz=9,col=s_bt_col)
        _run(p,' | Score : '+bt_score_w+'/100',sz=9,col=NR)
        _run(p,' | N-1 : '+bt_r_n1+' rouge / '+bt_a_n1+' ambre',sz=9,col=NR)
        _run(p,' | N-2 : '+bt_r_n2+' rouge / '+bt_a_n2+' ambre',sz=9,col=NR)
        doc.add_page_break()

        # 6. Effets calendaire
        _h('6. Effets calendaire — Barnett-Zehnwirth (1998)'); _sep()
        n_sig_w = int(bz.get('n_effets_significatifs',0))
        if n_sig_w == 0:
            p=doc.add_paragraph()
            _run(p,'✅ Aucun effet calendaire significatif détecté.',sz=9,col=VR)
        else:
            for e in bz.get('effets_calendaire',[]):
                if e.get('significatif'):
                    e_label = str(e.get('annee_label','—'))
                    e_amp   = round(float(e.get('amplitude_pct',0)),1)
                    e_niv   = str(e.get('niveau','—'))
                    p=doc.add_paragraph()
                    p.paragraph_format.left_indent=Cm(0.4)
                    _run(p,f'⚠️ {e_label} : {e_amp:+.1f}% ({e_niv})',sz=9,col=AR)
        doc.add_page_break()

        # 7. Commentaire
        _h('7. Commentaire actuariel'); _sep()
        if narration:
            sections_n = re.split(r'(?=§\d+\s*[—\-–])', _clean(narration))
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
            if source == 'claude_api':
                p=doc.add_paragraph()
                _run(p,'✨ Narration générée par Claude — ActuarIA Intelligence',sz=7,italic=True,col=GrR)
        else:
            p=doc.add_paragraph()
            _run(p,'Commentaire non disponible.',sz=9,italic=True)
        doc.add_page_break()

        # 8. Jugement
        _h('8. Jugement actuariel & Recommandations'); _sep()
        for a in n4.get('alertes',n2.get('alertes',[])):
            at=_clean(str(a))
            if at:
                p=doc.add_paragraph(); p.paragraph_format.left_indent=Cm(0.4)
                _run(p,'⚠️  ',sz=10,col=AR); _run(p,at,sz=9,col=NR)
        for i,rec in enumerate(n4.get('recommandations',[]),1):
            rt=_clean(str(rec))
            if rt:
                p=doc.add_paragraph(); p.paragraph_format.left_indent=Cm(0.4)
                _run(p,str(i)+'.  ',bold=True,sz=10,col=GR)
                _run(p,rt,sz=9,col=NR)
        avis_w=_clean(n4.get('avis_actuariel',''))
        if avis_w:
            doc.add_paragraph()
            p=doc.add_paragraph()
            a_col=RgR if 'DÉFAVORABLE' in avis_w.upper() else VR
            _run(p,avis_w,sz=10,bold=True,col=a_col)

        # Pied
        _sep('0F2E52')
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        _run(p,'ActuarIA · '+cli+' · '+lob+' · Arrêté '+arr+' · '+dt+' · CONFIDENTIEL',sz=7,italic=True,col=GrR)

        buf=io.BytesIO(); doc.save(buf); buf.seek(0)
        wb=buf.read()
        logger.info(f'Word : {len(wb):,} bytes — narration={source}')
        return wb

    except Exception as e:
        logger.error(f'export_word échoué : {e}', exc_info=True)
        return b''
