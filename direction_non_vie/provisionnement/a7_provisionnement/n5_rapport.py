# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  n5_rapport.py  —  Rapport actuariel professionnel v5.0
#
#  Style : reproduction exacte du rapport premium ActuarIA
#  3 formats : HTML · PDF (weasyprint) · Word (.docx)
#  Narration : Claude API → Templates → Données seules (3 niveaux)
#
#  Corrections vs premium :
#    · "Version A7-IBRAHIM · v4.0.0" supprimé de la page de garde
#    · Back-testing : tableau détaillé si données dispo, message sinon
#    · Section 7 : narration complète sans coupure
#    · LOB codes → libellés français (rc_medicale → RC Médicale)
#    · BF poids garanti ≥ 50% si méthode recommandée
#
#  Auteur  : ActuarIA v5.0
#  Version : 5.0.0
# =============================================================================

from __future__ import annotations
import base64, io, logging, os, re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger('actuaria.a7.rapport')

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY      = '#0B1E3D'
NAVY_MID  = '#132844'
NAVY_L    = '#1E3A5F'
GOLD      = '#C9A84C'
GOLD_L    = '#E2C97E'
GOLD_PALE = 'rgba(201,168,76,0.12)'
CYAN      = '#4A8FD4'
ROUGE     = '#C0392B'
ORANGE    = '#E67E22'
VERT      = '#1E8449'
SLATE     = '#8A9BB0'
SLATE_L   = '#B8C5D3'
BG        = '#F5F7FA'
WHITE     = '#FFFFFF'
TEXT      = '#1C2B3A'
TEXT_MID  = '#3D5166'
BORDER    = '#DDE4EE'

# ── Mapping LOB ───────────────────────────────────────────────────────────────
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
    if not code:
        return 'Branche Non-Vie'
    c = str(code).lower().strip().replace(' ', '_')
    return LOB_LABELS.get(c, code.replace('_', ' ').title())

def _lob_short(code: str) -> str:
    """Version courte pour la page de garde."""
    full = _lob(code)
    return full.split(' — ')[0] if ' — ' in full else full


# =============================================================================
#  LOGO SVG
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
    if v is None:
        return '—'
    try:
        fv = float(v)
        if not np.isfinite(fv):
            return '—'
        sep = '\u202f'
        return f"{fv:,.0f}\u202f\u20ac".replace(',', sep) if dec == 0 else f"{fv:,.{dec}f}".replace(',', sep)
    except Exception:
        return '—'

def _pct(v, dec=1) -> str:
    if v is None:
        return '—'
    try:
        fv = float(v)
        return '—' if not np.isfinite(fv) else f"{fv:.{dec}f}\u202f%"
    except Exception:
        return '—'

def _s(v) -> str:
    if v is None:
        return '—'
    return re.sub(r'\s+', ' ', str(v)).strip() or '—'

def _clean(txt) -> str:
    if not txt:
        return ''
    txt = re.sub(r'[■□▪▸►═╔╗╚╝║─]+', '', str(txt))
    txt = re.sub(r'={4,}', '', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()

def _statut_col(s: str) -> str:
    return {'VERT': VERT, 'AMBRE': ORANGE, 'ROUGE': ROUGE}.get(s, SLATE)

def _statut_label(s: str) -> str:
    return {
        'VERT':  'Statut RAG : Vert — Conforme',
        'AMBRE': 'Statut RAG : Ambre — Vigilance',
        'ROUGE': 'Statut RAG : Rouge — Surveillance renforcée',
    }.get(s, 'Statut : ' + s)


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
3. CHIFFRES : En euros avec séparateurs (ex : 2\u202f526\u202f597\u202f€). Pourcentages avec une décimale.
4. RÉFÉRENCES : Art. 77 S2, Art. 105 S2, Guide IA 2023, Mack 1993, Clark 2003.
5. ALERTES : Ne jamais minimiser. Présenter avec l'implication réelle pour le bilan S2.
6. CAUSALITÉ : H1 rejetée (corr=0.52) → CL biaisé → BF retenu → impact X\u202f€ sur BE.
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
#  CONTEXTE CLAUDE API
# =============================================================================

def _construire_contexte(n2: Dict, n3: Dict, n4: Dict, lob_label: str, arrete: str) -> str:
    cl    = n3.get('chain_ladder', {});  mk  = n3.get('mack', {})
    bf    = n3.get('bf', {});            cc  = n3.get('cape_cod', {})
    clark = n3.get('clark', {});         bz  = n3.get('glm_apc', {})
    bt    = n3.get('backtesting', {});   sc  = n4.get('scr', {})
    h1    = n2.get('h1_independance', {}); h2 = n2.get('h2_stabilite', {})
    h3    = n2.get('h3_apriori_bf', {});  h4  = n2.get('h4_homosc_bootstrap', {})
    pw    = n4.get('poids', {})
    BE  = float(n4.get('best_estimate', 0) or 0)
    SIG = float(mk.get('sigma_total', 0) or 0)
    CV  = float(n4.get('cv_inter_methodes', 0) or 0)
    P75 = float(n4.get('reserve_p75', 0) or 0)
    P90 = float(n4.get('reserve_p90', 0) or 0)
    P99 = float(n4.get('reserve_p99_5', 0) or 0)
    SCP = float(sc.get('scr_provisions', sc.get('scr_prov', BE * 0.30)) if sc else BE * 0.30)
    SCR = SCP / BE * 100 if BE else 0
    lines = [
        f"DOSSIER DE PROVISIONNEMENT — {lob_label.upper()} — Arrêté {arrete}",
        "",
        "=== TRIANGLE ===",
        f"Dimensions : {n2.get('dimensions', '—')} (n={n2.get('n_lignes', '?')} années × m={n2.get('n_colonnes', '?')} périodes)",
        f"Années de survenance : {n2.get('annee_debut', '?')} à {n2.get('annee_fin', '?')}",
        f"Méthode retenue : {n4.get('methode_facteurs', n2.get('methode_recommandee', '—'))}",
        "",
        "=== HYPOTHÈSES ===",
        f"H1 Indépendance : {'VALIDÉE' if h1.get('ok') else 'REJETÉE'} | corr_moy={h1.get('corr_moy', '—')} | score={h1.get('score', '—')}/100",
        f"  Message : {str(h1.get('message', ''))[:200]}",
        f"H2 Stabilité : {'VALIDÉE' if h2.get('ok') else 'REJETÉE'} | CV={h2.get('cv_moy', '—')} | score={h2.get('score', '—')}/100",
        f"H3 A priori BF : {'VALIDÉE' if h3.get('ok') else 'REJETÉE'} | LR_REEL={h3.get('lr_apriori', '—')} | LR_PROXY={h3.get('lr_proxy', '—')} | score={h3.get('score', '—')}/100",
        "  IMPORTANT: Si LR_REEL est fourni par l'utilisateur (valeur numérique, pas —), citer ce LR dans le commentaire, pas le LR proxy.",
        f"H4 Homoscédasticité : {'VALIDÉE' if h4.get('ok') else 'REJETÉE'} | phi={h4.get('phi', '—')} | score={h4.get('score', '—')}/100",
        "",
        "=== RÉSULTATS ===",
        f"Chain Ladder : {_f(cl.get('reserve_totale'))} | poids={_pct(pw.get('chain_ladder', 0)*100)}",
        f"Mack 1993 : {_f(mk.get('reserve_best_estimate'))} | poids={_pct(pw.get('mack', 0)*100)}",
        f"BF : {_f(bf.get('reserve_totale'))} | poids={_pct(pw.get('bornhuetter_ferguson', 0)*100)}",
        f"Cape Cod : {_f(cc.get('reserve_totale'))} | poids={_pct(pw.get('cape_cod', 0)*100)}",
        f"Clark LDF : {_f(clark.get('reserve_be_clark'))} | courbe={clark.get('courbe_choisie', '—')} | AIC={clark.get('aic_optimal', '—')}",
        f"BEST ESTIMATE S2 : {_f(BE)} | CV={_pct(CV)}",
        "",
        "=== INCERTITUDE ===",
        f"σ Mack={_f(SIG)} | P75={_f(P75)} | P90={_f(P90)} | P99.5={_f(P99)}",
        "",
        "=== SCR ===",
        f"SCR={_f(SCP)} | Ratio SCR/BE={_pct(SCR)}",
        "",
        "=== BACK-TESTING ===",
        f"Statut={bt.get('statut', '—')} | Score={bt.get('score_qualite', '—')}/100",
        f"N-1: {bt.get('n_rouge_n1', 0)} rouge / {bt.get('n_ambre_n1', 0)} ambre | N-2: {bt.get('n_rouge_n2', 0)} rouge / {bt.get('n_ambre_n2', 0)} ambre",
        f"Message: {str(bt.get('message', ''))[:300]}",
        "",
        "=== EFFETS CALENDAIRE (GLM POISSON APC) ===",
        f"Statut={bz.get('statut', '—')} | Sig.={bz.get('n_effets_significatifs', 0)}/{bz.get('n_diagonales_evaluees', 0)}",
        f"Réserve GLM APC={_f(bz.get('reserve_apc', 0))} (= chain-ladder par MLE) | "
        f"test calendaire {'SIGNIFICATIF' if bz.get('cal_significatif') else 'non significatif'} "
        f"(F quasi-Poisson, p={bz.get('p_calendaire', '—')})",
        f"Diagonales anormales: {', '.join(bz.get('diagonales_anormales', [])) or 'Aucune'}",
        f"Recommandation: {bz.get('recommandation', '—')}",
        "",
        "Rédige le commentaire actuariel complet en 7 sections.",
    ]
    return '\n'.join(lines)


# =============================================================================
#  GÉNÉRATION NARRATION (3 NIVEAUX)
# =============================================================================

def _narration_claude_api(n2, n3, n4, lob_label, arrete) -> str:
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
        ctx = _construire_contexte(n2, n3, n4, lob_label, arrete)
        resp = client.messages.create(
            model='claude-sonnet-4-6', max_tokens=10000,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': ctx}],
        )
        return resp.content[0].text
    except Exception as e:
        logger.warning(f'Claude API indisponible : {e}')
        raise

def _narration_templates(n4, commentaire) -> str:
    return _clean(commentaire) or _clean(n4.get('jugement', ''))

def _generer_narration(n2, n3, n4, commentaire, lob_label, arrete) -> Tuple[str, str]:
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
#  RENDU MARKDOWN → HTML (style premium)
# =============================================================================

def _nettoyer_narration(texte: str) -> str:
    """
    Supprime le header générique que Claude ajoute en début de narration.
    Ex: "# RAPPORT ACTUARIEL...", "Arrêté au...", "Document destiné..."

    Tout ce qui précède le premier § est supprimé car c'est du remplissage
    que Claude génère parfois malgré les instructions du system prompt.
    """
    if not texte:
        return ''
    txt = texte.strip()

    # Si le texte commence par un header Markdown # ou ##
    # supprimer tout jusqu'au premier §
    premier_s = re.search(r'§\s*\d+', txt)
    if premier_s and premier_s.start() > 10:
        # Du texte avant le premier § → le couper
        txt = txt[premier_s.start():]

    # Supprimer les lignes de header génériques ligne par ligne
    lignes = txt.split(chr(10))
    filtrees = []
    patterns_supprimer = [
        r'^#+\s+RAPPORT',
        r'^Arrêté\s+(au|Q\d)',
        r'^Document\s+destin',
        r'^Commentaire\s+destin',
        r'^Reporting\s+Solvabilit',
        r'^Ce\s+rapport.*ACPR',
    ]
    for ligne in lignes:
        supprimer = any(re.match(p, ligne.strip(), re.IGNORECASE) for p in patterns_supprimer)
        if not supprimer:
            filtrees.append(ligne)
    txt = chr(10).join(filtrees)

    # Supprimer les tableaux Markdown (lignes avec |)
    _lignes_ok = []
    for _l in txt.split(chr(10)):
        if re.match(r'^\s*\|', _l) or re.match(r'^\s*[-|:]+\s*$', _l):
            continue
        _lignes_ok.append(_l)
    txt = chr(10).join(_lignes_ok)

    # Normaliser les sauts de ligne
    txt = re.sub(r'\n{3,}', '\n\n', txt)

    return txt.strip()


def _md_to_html(texte: str) -> str:
    """Convertit le Markdown de Claude en HTML avec les classes premium."""
    if not texte:
        return '<p class="comm-p" style="color:#8A9BB0;font-style:italic;">Narration non disponible.</p>'

    # Nettoyer le header générique avant conversion
    texte = _nettoyer_narration(texte)
    if not texte:
        return '<p class="comm-p" style="color:#8A9BB0;font-style:italic;">Narration non disponible.</p>'

    txt = texte.strip()

    # §N — TITRE → comm-section-title
    def _section(m):
        t = m.group(1).strip()
        return '<div class="comm-section-title">' + t + '</div>'
    txt = re.sub(r'(§\d+\s*[—\-–]\s*[^\n]+)', _section, txt)

    # ### Sous-titre → comm-h4
    txt = re.sub(r'^###\s+(.+)$',
        lambda m: '<div class="comm-h4">' + m.group(1).strip() + '</div>',
        txt, flags=re.MULTILINE)

    # ## Titre → comm-h4
    txt = re.sub(r'^##\s+(.+)$',
        lambda m: '<div class="comm-h4">' + m.group(1).strip() + '</div>',
        txt, flags=re.MULTILINE)

    # --- → comm-divider
    txt = re.sub(r'^---+$', '<hr class="comm-divider">', txt, flags=re.MULTILINE)

    # **gras** → strong (y compris multi-lignes courts)
    txt = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', txt, flags=re.DOTALL)

    # *italique* → em
    txt = re.sub(r'\*(.+?)\*', r'<em>\1</em>', txt)

    # Puces - → comm-ul li
    txt = re.sub(r'^[-•]\s+(.+)$', r'<li>\1</li>', txt, flags=re.MULTILINE)
    txt = re.sub(
        r'(<li>.*?</li>\n?)+',
        lambda m: '<ul class="comm-ul">' + m.group(0) + '</ul>',
        txt, flags=re.DOTALL
    )

    # Paragraphes
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
            result += '<p class="comm-p">' + clean + '</p>\n'
    return result or '<p class="comm-p">' + texte + '</p>'


# =============================================================================
#  CSS PREMIUM
# =============================================================================

def _css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,400&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --navy:        #0B1E3D;
  --navy-mid:    #132844;
  --navy-light:  #1E3A5F;
  --gold:        #C9A84C;
  --gold-light:  #E2C97E;
  --gold-pale:   rgba(201,168,76,0.12);
  --cyan:        #4A8FD4;
  --cyan-pale:   rgba(74,143,212,0.10);
  --rouge:       #C0392B;
  --rouge-pale:  rgba(192,57,43,0.08);
  --orange:      #E67E22;
  --vert:        #1E8449;
  --slate:       #8A9BB0;
  --slate-light: #B8C5D3;
  --bg:          #F5F7FA;
  --white:       #FFFFFF;
  --text:        #1C2B3A;
  --text-mid:    #3D5166;
  --border:      #DDE4EE;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', sans-serif;
  font-size: 10pt;
  color: var(--text);
  background: var(--bg);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
}

.rapport-container {
  max-width: 960px;
  margin: 0 auto;
  background: var(--white);
  box-shadow: 0 4px 40px rgba(11,30,61,0.14);
}

/* ── PAGE DE GARDE ── */
.page-garde {
  position: relative;
  min-height: 680px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--navy);
  page-break-after: always;
}

.garde-bg { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }

.garde-bg::before {
  content: '';
  position: absolute;
  top: -120px; right: -80px;
  width: 520px; height: 520px;
  border: 1px solid rgba(201,168,76,0.12);
  border-radius: 50%;
  transform: rotate(15deg);
}

.garde-bg::after {
  content: '';
  position: absolute;
  top: -60px; right: -20px;
  width: 360px; height: 360px;
  border: 1px solid rgba(201,168,76,0.20);
  border-radius: 50%;
}

.garde-dots {
  position: absolute;
  top: 0; right: 0;
  width: 320px; height: 100%;
  background-image: radial-gradient(circle, rgba(201,168,76,0.25) 1px, transparent 1px);
  background-size: 22px 22px;
  mask-image: linear-gradient(to left, rgba(0,0,0,0.7) 0%, transparent 100%);
  -webkit-mask-image: linear-gradient(to left, rgba(0,0,0,0.7) 0%, transparent 100%);
}

.garde-diagonal {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(135deg, transparent 0%, transparent 62%, rgba(201,168,76,0.06) 62%, rgba(201,168,76,0.06) 100%);
}

.garde-accent-line {
  position: absolute;
  left: 52px; top: 0; bottom: 0;
  width: 2px;
  background: linear-gradient(to bottom, transparent 0%, var(--gold) 20%, var(--gold) 80%, transparent 100%);
  opacity: 0.5;
}

.garde-inner {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}

.garde-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 36px 56px 0;
}

.garde-logo-wrap img { height: 52px; }

.garde-badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.badge-confidentiel {
  font-size: 7.5pt;
  font-weight: 700;
  color: var(--rouge);
  letter-spacing: 2.5px;
  border: 1.5px solid var(--rouge);
  padding: 5px 12px;
  text-transform: uppercase;
}

.garde-hero {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 48px 56px 0 80px;
}

.garde-eyebrow {
  font-size: 8pt;
  font-weight: 600;
  color: var(--gold);
  letter-spacing: 4px;
  text-transform: uppercase;
  margin-bottom: 20px;
}

.garde-titre {
  font-family: 'Playfair Display', serif;
  font-size: 52pt;
  font-weight: 900;
  color: var(--white);
  line-height: 1.05;
  letter-spacing: -1.5px;
  margin-bottom: 8px;
}

.garde-titre em {
  font-style: italic;
  color: var(--gold);
}

.garde-subtitle {
  font-family: 'Playfair Display', serif;
  font-size: 18pt;
  font-weight: 400;
  font-style: italic;
  color: var(--slate-light);
  margin-bottom: 32px;
}

.garde-sep {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

.garde-sep-line { height: 1px; width: 80px; background: var(--gold); opacity: 0.6; }

.garde-sep-diamond {
  width: 8px; height: 8px;
  background: var(--gold);
  transform: rotate(45deg);
  flex-shrink: 0;
}

.garde-statut {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 10px 24px;
  margin-bottom: 0;
}

.garde-statut-rouge { background: rgba(192,57,43,0.15); border: 1px solid rgba(192,57,43,0.5); }
.garde-statut-ambre { background: rgba(230,126,34,0.15); border: 1px solid rgba(230,126,34,0.5); }
.garde-statut-vert  { background: rgba(30,132,73,0.15);  border: 1px solid rgba(30,132,73,0.5); }

.statut-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  box-shadow: 0 0 8px rgba(192,57,43,0.7);
  animation: pulse 2s ease-in-out infinite;
}

.statut-dot-rouge { background: var(--rouge); box-shadow: 0 0 8px rgba(192,57,43,0.7); }
.statut-dot-ambre { background: var(--orange); box-shadow: 0 0 8px rgba(230,126,34,0.7); }
.statut-dot-vert  { background: var(--vert);  box-shadow: 0 0 8px rgba(30,132,73,0.7); }

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.2); }
}

.statut-label-rouge { font-size: 8pt; font-weight: 700; color: var(--rouge); letter-spacing: 3px; text-transform: uppercase; }
.statut-label-ambre { font-size: 8pt; font-weight: 700; color: var(--orange); letter-spacing: 3px; text-transform: uppercase; }
.statut-label-vert  { font-size: 8pt; font-weight: 700; color: var(--vert);  letter-spacing: 3px; text-transform: uppercase; }

.garde-footer {
  border-top: 1px solid rgba(201,168,76,0.25);
  margin: 40px 56px 0;
  padding: 28px 0 40px;
}

.garde-kpis { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0; }

.garde-kpi {
  padding: 0 20px 0 0;
  border-right: 1px solid rgba(255,255,255,0.08);
}

.garde-kpi:last-child { border-right: none; }

.kpi-label {
  font-size: 6.5pt;
  font-weight: 600;
  color: var(--slate);
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-bottom: 6px;
}

.kpi-value {
  font-family: 'Playfair Display', serif;
  font-size: 12pt;
  font-weight: 700;
  color: var(--white);
  line-height: 1.2;
}

.kpi-value.highlight { color: var(--gold); font-size: 14pt; }
.kpi-sub { font-size: 7pt; color: var(--slate); margin-top: 3px; }

/* ── CORPS ── */
.rapport-body { padding: 0; }

.section-header {
  background: linear-gradient(to right, var(--navy) 0%, var(--navy-light) 100%);
  padding: 22px 56px;
  display: flex;
  align-items: center;
  gap: 20px;
}

.section-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9pt;
  font-weight: 500;
  color: var(--gold);
  opacity: 0.8;
  min-width: 28px;
}

.section-titre {
  font-family: 'Playfair Display', serif;
  font-size: 16pt;
  font-weight: 700;
  color: var(--white);
}

.section-body { padding: 36px 56px 48px; }

.section-divider { height: 1px; background: var(--border); }

/* ── KPI CARDS ── */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}

.kpi-card {
  background: var(--navy);
  border-radius: 6px;
  padding: 20px 18px;
  position: relative;
  overflow: hidden;
}

.kpi-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--gold);
}

.kpi-card-rouge::before { background: var(--rouge); }

.kpi-card-label { font-size: 7pt; font-weight: 600; color: var(--slate); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px; }
.kpi-card-value { font-family: 'Playfair Display', serif; font-size: 18pt; font-weight: 700; color: var(--white); line-height: 1.1; margin-bottom: 6px; }
.kpi-card-value-rouge { color: var(--rouge) !important; }
.kpi-card-sub { font-size: 7.5pt; color: var(--gold); }

/* ── TABLEAUX PREMIUM ── */
.table-section-title {
  font-family: 'Playfair Display', serif;
  font-size: 10pt;
  font-weight: 600;
  color: var(--gold);
  margin: 28px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--gold-pale);
}

table.premium { width: 100%; border-collapse: collapse; font-size: 9pt; }
table.premium thead tr { background: var(--navy); }
table.premium thead th { padding: 11px 14px; color: var(--white); font-weight: 600; font-size: 8pt; letter-spacing: 0.5px; text-align: left; }
table.premium thead th.right { text-align: right; }
table.premium thead th.center { text-align: center; }
table.premium tbody tr:nth-child(even) { background: #F8FAFB; }
table.premium tbody tr.highlight-gold { background: var(--gold-pale); font-weight: 700; }
table.premium tbody td { padding: 9px 14px; border-bottom: 1px solid var(--border); color: var(--text); }
table.premium tbody td.right { text-align: right; }
table.premium tbody td.center { text-align: center; }
table.premium tbody td.label { font-weight: 600; color: var(--navy); }
table.premium tbody td .mono { font-family: 'JetBrains Mono', monospace; font-size: 8.5pt; }

/* ── BADGES ── */
.badge { display: inline-flex; align-items: center; gap: 4px; font-size: 7.5pt; font-weight: 700; padding: 2px 8px; border-radius: 3px; letter-spacing: 0.5px; }
.badge-ok   { background: rgba(30,132,73,0.12);  color: var(--vert); }
.badge-warn { background: rgba(230,126,34,0.12); color: var(--orange); }
.badge-excl { background: rgba(138,155,176,0.15); color: var(--slate); }

/* ── HYPOTHÈSES ── */
.hyp-grid { display: flex; flex-direction: column; gap: 10px; }

.hyp-card {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 0;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border);
}

.hyp-label { padding: 14px 18px; font-size: 8pt; font-weight: 700; }
.hyp-label .hyp-code { font-family: 'JetBrains Mono', monospace; font-size: 7.5pt; opacity: 0.9; }
.hyp-label .hyp-score { font-weight: 400; opacity: 0.8; margin-top: 4px; font-size: 7.5pt; }

.hyp-ok   .hyp-label { background: rgba(30,132,73,0.10);  color: var(--vert);   border-right: 3px solid var(--vert); }
.hyp-warn .hyp-label { background: rgba(230,126,34,0.10); color: var(--orange); border-right: 3px solid var(--orange); }

.hyp-text { padding: 14px 18px; font-size: 9pt; color: var(--text-mid); line-height: 1.6; background: #FAFBFC; }

/* ── RECOMMANDATION BOX ── */
.recommandation-box {
  background: var(--navy);
  padding: 18px 24px;
  border-radius: 6px;
  margin-top: 20px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.reco-icon { font-size: 18pt; line-height: 1; flex-shrink: 0; color: var(--gold); }
.reco-label { font-size: 7pt; font-weight: 700; color: var(--gold); text-transform: uppercase; letter-spacing: 2px; margin-bottom: 4px; }
.reco-value { font-family: 'Playfair Display', serif; font-size: 13pt; font-weight: 700; color: var(--white); margin-bottom: 4px; }
.reco-text { font-size: 8.5pt; color: var(--slate); line-height: 1.5; }

/* ── EFFETS CALENDAIRE ── */
.bz-grid { display: flex; flex-direction: column; gap: 6px; }

.bz-item { display: flex; align-items: center; gap: 14px; padding: 10px 16px; border-radius: 4px; font-size: 9pt; }
.bz-warn { background: rgba(230,126,34,0.08); border-left: 3px solid var(--orange); }
.bz-info { background: var(--cyan-pale); border-left: 3px solid var(--cyan); }
.bz-ok   { background: rgba(30,132,73,0.06); border-left: 3px solid var(--vert); }

.bz-year { font-family: 'JetBrains Mono', monospace; font-size: 8.5pt; font-weight: 700; min-width: 42px; }
.bz-bar { flex: 1; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.bz-fill { height: 100%; border-radius: 2px; }
.bz-pct { font-size: 8.5pt; font-weight: 600; min-width: 120px; text-align: right; }

/* ── COMMENTAIRE ACTUARIEL ── */
.commentaire-wrap { border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }

.commentaire-header {
  background: var(--navy);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.commentaire-header-title { font-size: 8pt; font-weight: 600; color: var(--gold); letter-spacing: 2px; text-transform: uppercase; }
.commentaire-ai-badge { font-size: 7pt; color: var(--slate); font-family: 'JetBrains Mono', monospace; }
.commentaire-body { padding: 28px 32px; background: #FAFBFC; }

.comm-section-title {
  font-family: 'Playfair Display', serif;
  font-size: 11pt;
  font-weight: 700;
  color: var(--navy);
  border-bottom: 1.5px solid var(--gold);
  padding-bottom: 6px;
  margin: 24px 0 12px;
}

.comm-section-title:first-child { margin-top: 0; }
.comm-h4 { font-size: 9.5pt; font-weight: 700; color: var(--navy); margin: 16px 0 8px; }
.comm-p { font-size: 9.5pt; line-height: 1.85; color: var(--text-mid); margin-bottom: 12px; }
.comm-p strong { color: var(--navy); font-weight: 700; }

.comm-ul { margin: 10px 0 12px 20px; list-style: none; }
.comm-ul li { position: relative; padding-left: 16px; font-size: 9.5pt; line-height: 1.7; color: var(--text-mid); margin-bottom: 6px; }
.comm-ul li::before { content: '—'; position: absolute; left: 0; color: var(--gold); font-weight: 700; }
.comm-ul li strong { color: var(--navy); }

.comm-divider { border: none; border-top: 1px solid var(--border); margin: 20px 0; }
.comm-footer { font-size: 7.5pt; color: var(--slate); font-style: italic; text-align: right; border-top: 1px solid var(--border); padding-top: 10px; margin-top: 8px; }

/* ── BACK-TESTING ── */
.bt-summary { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
.bt-card { padding: 14px 20px; border-radius: 6px; text-align: center; min-width: 120px; }
.bt-card-rouge { background: var(--rouge); color: var(--white); }
.bt-card-ambre { background: var(--orange); color: var(--white); }
.bt-card-vert  { background: var(--vert);  color: var(--white); }
.bt-card-navy  { background: var(--navy);  color: var(--white); }
.bt-card-label { font-size: 7.5pt; opacity: 0.8; margin-bottom: 4px; }
.bt-card-value { font-family: 'Playfair Display', serif; font-size: 15pt; font-weight: 700; }
.bt-card-sub   { font-size: 7.5pt; color: var(--gold); margin-top: 2px; }

.bt-note {
  background: var(--rouge-pale);
  border-left: 3px solid var(--rouge);
  padding: 12px 16px;
  border-radius: 0 4px 4px 0;
  font-size: 9pt;
  color: var(--text-mid);
  line-height: 1.6;
  margin-top: 12px;
}

/* ── PIED DE PAGE ── */
.pied-de-page {
  background: var(--navy);
  padding: 20px 56px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 2px solid var(--gold);
}

.pied-logo img { height: 26px; }
.pied-meta { text-align: right; font-size: 7.5pt; color: var(--slate); line-height: 1.7; }
.pied-meta .confidentiel-footer { color: var(--rouge); font-weight: 700; letter-spacing: 1px; }

@media print {
  body { background: white; }
  .rapport-container { box-shadow: none; max-width: none; margin: 0; }
  .page-garde { page-break-after: always; min-height: 100vh; }
  @page { margin: 0; }
}
</style>"""


# =============================================================================
#  CONSTRUCTION DES BLOCS HTML
# =============================================================================

def _build_blocks(n2, n3, n4, narration, source_narration, lob, cli, arr, dt, audit_id, methode, statut, graphiques_html, actuaire_nom='', actuaire_numero_ia='') -> Dict:
    cl    = n3.get('chain_ladder', {});  mk  = n3.get('mack', {})
    bf    = n3.get('bf', {});            cc  = n3.get('cape_cod', {})
    clark = n3.get('clark', {});         bz  = n3.get('glm_apc', {})
    bt    = n3.get('backtesting', {});   sc  = n4.get('scr', {})
    h1    = n2.get('h1_independance', {}); h2 = n2.get('h2_stabilite', {})
    h3    = n2.get('h3_apriori_bf', {});  h4  = n2.get('h4_homosc_bootstrap', {})
    pw    = n4.get('poids', {})

    BE  = float(n4.get('best_estimate', 0) or 0)
    SIG = float(mk.get('sigma_total', 0) or 0)
    CV  = float(n4.get('cv_inter_methodes', 0) or 0)
    P75 = float(n4.get('reserve_p75', 0) or 0)
    P90 = float(n4.get('reserve_p90', 0) or 0)
    P99 = float(n4.get('reserve_p99_5', 0) or 0)
    # Percentiles Mack et Bootstrap séparés
    P75_mack = float(n4.get('reserve_p75_mack', P75) or P75)
    P90_mack = float(n4.get('reserve_p90_mack', P90) or P90)
    P99_mack = float(n4.get('reserve_p99_5_mack', P99) or P99)
    P75_boot = n4.get('reserve_p75_boot')
    P90_boot = n4.get('reserve_p90_boot')
    P99_boot = n4.get('reserve_p99_5_boot')
    _boot_dispo = P75_boot is not None and float(P75_boot or 0) > 0
    SCP = float(sc.get('scr_provisions', sc.get('scr_prov', BE * 0.30)) if sc else BE * 0.30)
    SCR = SCP / BE * 100 if BE else 0

    s_col   = _statut_col(statut)
    s_label = _statut_label(statut)
    s_cls   = statut.lower()

    b = {}

    # ── PAGE DE GARDE ─────────────────────────────────────────────────────────
    # Titre branche : première partie en blanc, deuxième en or italic si " — "
    lob_parts = lob.split(' — ')
    if len(lob_parts) == 2:
        garde_titre = lob_parts[0] + '<br><em>' + lob_parts[1] + '</em>'
    else:
        # RC Médicale → RC / Médicale (style premium)
        words = lob.split()
        if len(words) >= 2:
            garde_titre = ' '.join(words[:-1]) + '<br><em>' + words[-1] + '</em>'
        else:
            garde_titre = '<em>' + lob + '</em>'

    b['garde_titre']   = garde_titre
    b['garde_statut_cls'] = 'garde-statut-' + s_cls
    b['garde_dot_cls']    = 'statut-dot-' + s_cls
    b['garde_label_cls']  = 'statut-label-' + s_cls
    b['garde_label']      = s_label

    # KPIs page de garde
    scr_style = 'color:var(--rouge);' if statut == 'ROUGE' else ''
    b['garde_kpis'] = (
        '<div class="garde-kpi"><div class="kpi-label">Client</div>'
        '<div class="kpi-value">' + cli + '</div></div>'

        '<div class="garde-kpi"><div class="kpi-label">Arrêté</div>'
        '<div class="kpi-value">' + arr + '</div></div>'

        '<div class="garde-kpi"><div class="kpi-label">Méthode principale</div>'
        '<div class="kpi-value" style="font-size:10pt;">'
        + methode.replace('_', ' ').replace('bornhuetter ferguson', 'Bornhuetter-Ferguson').title()
        + '</div></div>'

        '<div class="garde-kpi"><div class="kpi-label">Best Estimate (brut)</div>'
        '<div class="kpi-value highlight">' + _f(BE) + '</div></div>'

        '<div class="garde-kpi"><div class="kpi-label">SCR Provisions</div>'
        '<div class="kpi-value" style="font-size:11pt;' + scr_style + '">' + _f(SCP) + '</div>'
        '<div class="kpi-sub">Ratio SCR/BE : ' + _pct(SCR) + '</div></div>'

        '<div class="garde-kpi"><div class="kpi-label">Audit ID</div>'
        '<div class="kpi-value" style="font-family:\'JetBrains Mono\',monospace;font-size:8pt;color:var(--slate-light);">'
        + (audit_id or '—') + '</div></div>'
    )

    # ── SECTION 1 : KPI GRID ─────────────────────────────────────────────────
    # 4ème KPI : PT S2 si RM disponible, sinon P99,5
    _kpi4 = (
        '<div class="kpi-card" style="border-left:3px solid var(--gold);">'
        '<div class="kpi-card-label">Provisions Tech. S2</div>'
        '<div class="kpi-card-value">' + _f(n4.get('provisions_techniques_s2', 0)) + '</div>'
        '<div class="kpi-card-sub">BE + RM — Art. 77 §1</div>'
        '</div>'
        if n4.get('risk_margin', 0) > 0
        else '<div class="kpi-card">'
        '<div class="kpi-card-label">Provision P99,5 (composé)</div>'
        '<div class="kpi-card-value">' + _f(P99) + '</div>'
        '<div class="kpi-card-sub">P90 (composé) : ' + _f(P90) + '</div>'
        '</div>'
    )
    b['kpi_grid'] = (
        '<div class="kpi-grid">'
        '<div class="kpi-card">'
        '<div class="kpi-card-label">Best Estimate (brut)</div>'
        '<div class="kpi-card-value">' + _f(BE) + '</div>'
        '<div class="kpi-card-sub">Réserve avant actualisation — S2 par A10</div>'
        '</div>'
        '<div class="kpi-card">'
        '<div class="kpi-card-label">σ Mack total</div>'
        '<div class="kpi-card-value">' + _f(SIG) + '</div>'
        '<div class="kpi-card-sub">CV inter-méthodes : ' + _pct(CV) + '</div>'
        '</div>'
        '<div class="kpi-card kpi-card-rouge">'
        '<div class="kpi-card-label">SCR Provisions</div>'
        '<div class="kpi-card-value kpi-card-value-rouge">' + _f(SCP) + '</div>'
        '<div class="kpi-card-sub">Ratio SCR/BE : ' + _pct(SCR) + '</div>'
        '</div>'
        + _kpi4
        + '</div>'
    )
    b['graph_convergence'] = graphiques_html.get('g5_convergence', '')

    # ── SECTION 2 : MÉTHODES ─────────────────────────────────────────────────
    def _badge_statut(m_name, pw_val):
        if 'Mack' in m_name:   # Mack = volatilité (σ), non pondérée dans le BE (point = CL)
            return ('<span class="badge badge-excl" style="background:rgba(74,144,226,0.15);'
                    'color:#4A90E2;">σ (volatilité)</span>')
        if pw_val > 0:
            return '<span class="badge badge-ok">✓ Inclus</span>'
        return '<span class="badge badge-excl">⊘ Exclu</span>'

    rows_m = [
        ('Chain Ladder',         cl.get('reserve_totale'),         pw.get('chain_ladder', 0),         n2.get('scores_confiance', {}).get('chain_ladder', '—')),
        ('Mack 1993',            mk.get('reserve_best_estimate'),  pw.get('mack', 0),                 '—'),
        ('Bornhuetter-Ferguson', bf.get('reserve_totale'),         pw.get('bornhuetter_ferguson', 0), '—'),
        ('Cape Cod',             cc.get('reserve_totale'),         pw.get('cape_cod', 0),             n2.get('scores_confiance', {}).get('cape_cod', '—')),
    ]
    tbl = (
        '<table class="premium"><thead><tr>'
        '<th>Méthode</th>'
        '<th class="right">Réserve IBNR</th>'
        '<th class="center">Poids BE</th>'
        '<th class="center">Score</th>'
        '<th class="center">Statut</th>'
        '</tr></thead><tbody>'
    )
    for nom, res, pds, score in rows_m:
        s_txt = str(score) + ' / 100' if score != '—' else '—'
        tbl += (
            '<tr><td class="label">' + nom + '</td>'
            '<td class="right"><span class="mono">' + _f(res) + '</span></td>'
            '<td class="center">' + _pct(pds * 100) + '</td>'
            '<td class="center">' + s_txt + '</td>'
            '<td class="center">' + _badge_statut(nom, pds) + '</td></tr>'
        )
    # Clark
    if clark.get('disponible'):
        aic_val = str(clark.get('aic_optimal', '—'))
        if aic_val != '—':
            try:
                aic_f = float(aic_val)
                aic_disp = f'{aic_f/1e6:.0f}M' if abs(aic_f) > 1e6 else aic_val
            except Exception:
                aic_disp = aic_val
        else:
            aic_disp = '—'
        tbl += (
            '<tr><td class="label">Clark LDF (' + _s(clark.get('courbe_choisie')).title() + ')</td>'
            '<td class="right"><span class="mono">' + _f(clark.get('reserve_be_clark')) + '</span></td>'
            '<td class="center">—</td>'
            '<td class="center" style="font-size:7.5pt;color:var(--slate);">AIC = ' + aic_disp + '</td>'
            '<td class="center"><span class="badge badge-excl">⊘ Exclu</span></td></tr>'
        )
    if bz.get('glm_disponible') and bz.get('reserve_apc'):
        _p_bz = bz.get('p_calendaire', 1) or 1
        _p_bz_txt = 'p\u202f&lt;\u202f0,0001' if _p_bz < 0.0001 else f'p\u202f=\u202f{_p_bz:.4f}'
        tbl += (
            '<tr><td class="label">GLM Poisson APC (= CL)</td>'
            '<td class="right"><span class="mono">' + _f(bz.get('reserve_apc')) + '</span></td>'
            '<td class="center">—</td>'
            '<td class="center" style="font-size:7.5pt;color:var(--slate);">' + _p_bz_txt + '</td>'
            '<td class="center"><span class="badge badge-excl" style="background:rgba(74,144,226,0.15);color:#4A90E2;">ℹ️ Informatif</span></td></tr>'
        )
    tbl += (
        '<tr class="highlight-gold">'
        '<td class="label" style="color:var(--navy);">⭐ Best Estimate (brut)</td>'
        '<td class="right" style="color:var(--navy);"><span class="mono">' + _f(BE) + '</span></td>'
        '<td class="center">100\u202f%</td>'
        '<td class="center">—</td>'
        '<td class="center" style="color:var(--navy-light);font-size:8.5pt;">→ Bilan S2</td>'
        '</tr></tbody></table>'
    )
    b['tableau_methodes'] = tbl

    # Table diagnostic — décomposition de l'incertitude (4 lignes, colonne Centre)
    _mk = n3.get('mack', {}); _bo = n3.get('bootstrap', {})
    P90_natif      = float(_mk.get('reserve_p90', 0) or 0)
    SIG_COMPOSE    = float(n4.get('sigma_total_compose', SIG) or SIG)
    SIG_MACK       = float(n4.get('sigma_mack', SIG) or SIG)
    SIG_MACK_NATIF = float(_mk.get('sigma_total', SIG) or SIG)
    STD_BOOT       = float(_bo.get('std_bootstrap', 0) or 0)
    _bp90 = ('<span class="mono">' + _f(P90_boot) + '</span>') if _boot_dispo else '<span style="color:var(--slate)">—</span>'
    _bsig = ('<span class="mono">' + _f(STD_BOOT) + '</span>')  if _boot_dispo else '<span style="color:var(--slate)">—</span>'
    tbl_i = (
        '<table class="premium"><thead><tr>'
        '<th>Approche</th><th class="right">P90</th><th class="right">σ</th><th>Centre</th>'
        '</tr></thead><tbody>'
        '<tr class="highlight-gold"><td class="label">Incertitude composée (retenue)</td>'
        '<td class="right"><span class="mono">' + _f(P90) + '</span></td>'
        '<td class="right"><span class="mono">' + _f(SIG_COMPOSE) + '</span></td>'
        '<td>BE pondéré</td></tr>'
        '<tr><td class="label">Mack recentré</td>'
        '<td class="right"><span class="mono">' + _f(P90_mack) + '</span></td>'
        '<td class="right"><span class="mono">' + _f(SIG_MACK) + '</span></td>'
        '<td>BE pondéré</td></tr>'
        '<tr><td class="label">Mack natif</td>'
        '<td class="right"><span class="mono">' + _f(P90_natif) + '</span></td>'
        '<td class="right"><span class="mono">' + _f(SIG_MACK_NATIF) + '</span></td>'
        '<td>réserve Mack</td></tr>'
        '<tr><td class="label">Bootstrap ODP</td>'
        '<td class="right">' + _bp90 + '</td>'
        '<td class="right">' + _bsig + '</td>'
        '<td>réserve Bootstrap</td></tr>'
        '</tbody></table>'
        '<p style="font-size:8pt;color:var(--slate);font-style:italic;margin-top:6px;">'
        'Ces valeurs diffèrent par le σ (Mack seul / composé / bootstrap) et/ou le point de '
        'centrage (colonne Centre). Le livrable retient le P90 composé.</p>'
    )
    b['tableau_incertitude'] = tbl_i
    b['graph_ibnr']      = graphiques_html.get('g4_ibnr', '')
    b['graph_heatmap']   = graphiques_html.get('g1_heatmap', '')
    b['graph_bootstrap'] = graphiques_html.get('g6_bootstrap', '')

    # ── SECTION 3 : HYPOTHÈSES ────────────────────────────────────────────────
    hyp_cards = ''
    for label, h, code in [
        ('H1 — Indépendance des facteurs', h1, 'H1'),
        ('H2 — Stabilité des facteurs', h2, 'H2'),
        ('H3 — A priori BF / Cape Cod', h3, 'H3'),
        ('H4 — Homoscédasticité Bootstrap ODP', h4, 'H4'),
    ]:
        if not h:
            continue
        ok    = bool(h.get('ok', True))
        cls   = 'hyp-ok' if ok else 'hyp-warn'
        lbl   = '✓ VALIDÉE' if ok else '⚠ REJETÉE'
        score = _s(h.get('score'))
        msg   = _s(h.get('message'))
        hyp_cards += (
            '<div class="hyp-card ' + cls + '">'
            '<div class="hyp-label">'
            '<div class="hyp-code">' + label + '</div>'
            '<div class="hyp-score">' + lbl + ' · Score ' + score + ' / 100</div>'
            '</div>'
            '<div class="hyp-text">' + msg + '</div>'
            '</div>'
        )
    b['hyp_cards'] = hyp_cards

    raison = _s(n2.get('raison_recommandation'))[:200]
    b['methode_rec_box'] = (
        '<div class="recommandation-box">'
        '<div class="reco-icon">→</div>'
        '<div>'
        '<div class="reco-label">Méthode recommandée par ActuarIA</div>'
        '<div class="reco-value">' + methode.replace('_', ' ').title() + '</div>'
        '<div class="reco-text">' + raison + '</div>'
        '</div>'
        '</div>'
    )

    # ── SECTION 4 : SCR ───────────────────────────────────────────────────────
    sigma_eiopa = _s(sc.get('sigma_eiopa', '0,10') if sc else '0,10')  # depuis n4['scr']['sigma_eiopa']
    b['tableau_scr'] = (
        '<table class="premium"><thead><tr>'
        '<th>Composante</th><th class="center">Valeur</th><th>Référence réglementaire</th>'
        '</tr></thead><tbody>'
        '<tr><td class="label">Best Estimate (brut)</td>'
        '<td class="center"><span class="mono">' + _f(BE) + '</span></td>'
        '<td>Réserve brute — actualisation S2 en aval (A10)</td></tr>'
        '<tr><td class="label">Facteur σ EIOPA</td>'
        '<td class="center"><span class="mono">' + sigma_eiopa + '</span></td>'
        '<td>' + lob + ' — Annexe II, Règlement 2015/35</td></tr>'
        '<tr><td class="label">SCR Provisions</td>'
        '<td class="center"><span class="mono" style="color:var(--rouge);font-weight:700;">' + _f(SCP) + '</span></td>'
        '<td>SCR = 3 × σ(LoB) × BE — Art. 105</td></tr>'
        '<tr class="highlight-gold"><td class="label">Ratio SCR / BE</td>'
        '<td class="center" style="color:var(--rouge);font-weight:700;"><span class="mono">' + _pct(SCR) + '</span></td>'
        '<td>Cible pratique marché : &lt; 35\u202f%</td></tr>'
        # Risk Margin S2
        + ('<tr style="border-top:2px solid var(--navy);"><td class="label" style="color:var(--navy);font-weight:600;">Risk Margin S2</td>'
        '<td class="center"><span class="mono" style="color:var(--navy);font-weight:700;">'
        + _f(n4.get('risk_margin', 0)) + '</span></td>'
        '<td>Art. 77 §5 — CoC 6% · Méthode proportionnelle · Courbe EIOPA '
        + _s(n4.get('date_courbe_rfr', '—')) + '</td></tr>'
        '<tr class="highlight-gold"><td class="label">Provisions Techniques S2</td>'
        '<td class="center"><span class="mono" style="font-weight:700;">'
        + _f(n4.get('provisions_techniques_s2', 0)) + '</span></td>'
        '<td>PT S2 = BE + RM — Art. 77 §1</td></tr>')
        + '</tbody></table>'
    )

    # ── SECTION 5 : BACK-TESTING ──────────────────────────────────────────────
    bt_statut = _s(bt.get('statut', 'AMBRE'))
    bt_col_cls = 'bt-card-' + bt_statut.lower() if bt_statut in ('ROUGE', 'AMBRE', 'VERT') else 'bt-card-navy'
    bt_score  = _s(bt.get('score_qualite', '—'))
    n_mat     = int(bt.get('n_matures', bt.get('n_annees_matures', 0)))
    n_tot     = int(bt.get('n_total', n_mat))
    # Recalculer depuis le tableau réel pour cohérence
    _bt_tab = bt.get('tableau', [])
    _SR, _SA = 15.0, 8.0
    _nr1 = _na1 = _nr2 = _na2 = 0
    for _r in _bt_tab:
        if not isinstance(_r, dict) or not _r.get('mature', True): continue
        for _hor in ['n1', 'n2']:
            try:
                _ep = abs(float(_r.get('ecart_pct_' + _hor, 0) or 0))
                if _ep >= _SR:
                    if _hor == 'n1': _nr1 += 1
                    else: _nr2 += 1
                elif _ep >= _SA:
                    if _hor == 'n1': _na1 += 1
                    else: _na2 += 1
            except Exception: pass
    n_rouge_n1_disp = _nr1 if _bt_tab else int(bt.get('n_rouge_n1', 0))
    n_ambre_n1_disp = _na1 if _bt_tab else int(bt.get('n_ambre_n1', 0))
    n_rouge_n2_disp = _nr2 if _bt_tab else int(bt.get('n_rouge_n2', 0))
    n_ambre_n2_disp = _na2 if _bt_tab else int(bt.get('n_ambre_n2', 0))

    b['bt_summary'] = (
        '<div class="bt-summary">'
        '<div class="bt-card ' + bt_col_cls + '">'
        '<div class="bt-card-label">Statut RAG</div>'
        '<div class="bt-card-value">' + bt_statut + '</div>'
        '</div>'
        '<div class="bt-card bt-card-navy">'
        '<div class="bt-card-label">Score qualité</div>'
        '<div class="bt-card-value">' + bt_score + '</div>'
        '<div class="bt-card-sub">/ 100</div>'
        '</div>'
        '<div class="bt-card bt-card-navy">'
        '<div class="bt-card-label">Alertes N-1</div>'
        '<div class="bt-card-value">' + str(n_rouge_n1_disp) + '🔴  ' + str(n_ambre_n1_disp) + '🟡</div>'
        '</div>'
        '<div class="bt-card bt-card-navy">'
        '<div class="bt-card-label">Alertes N-2</div>'
        '<div class="bt-card-value">' + str(n_rouge_n2_disp) + '🔴  ' + str(n_ambre_n2_disp) + '🟡</div>'
        '</div>'
        '</div>'
    )

    # Tableaux boni/mali détaillés
    b['tableau_bt_n1'] = _build_bt_table(bt, 'n1')
    b['tableau_bt_n2'] = _build_bt_table(bt, 'n2')
    b['graph_bt']      = graphiques_html.get('g14_backtesting', '')

    msg_bt = _s(bt.get('message'))
    _bt_note_txt = msg_bt if msg_bt and msg_bt != '—' else ''
    b['bt_note'] = '<div class="bt-note">' + _bt_note_txt + '</div>' if _bt_note_txt else ''

    # ── SECTION 6 : EFFETS CALENDAIRE ────────────────────────────────────────
    n_sig    = int(bz.get('n_effets_significatifs', 0))
    _glm_ok  = bz.get('glm_disponible', False)
    _cal_sig = bz.get('cal_significatif', False)
    bz_items = ''
    if n_sig == 0:
        if not _glm_ok:
            # FIX 2 : test indisponible -> ne jamais afficher "aucun effet".
            bz_items = (
                '<div class="bz-item bz-info">'
                '<span class="bz-year" style="color:var(--cyan);">n/d</span>'
                '<div class="bz-bar"><div class="bz-fill" style="width:0%;background:var(--cyan);"></div></div>'
                '<span class="bz-pct" style="color:var(--cyan);">Test calendaire indisponible</span>'
                '</div>'
            )
        elif _cal_sig:
            # FIX 1 : F global significatif mais aucune diagonale isolee dominante (effet diffus).
            bz_items = (
                '<div class="bz-item bz-warn">'
                '<span class="bz-year" style="color:var(--orange);">Diffus</span>'
                '<div class="bz-bar"><div class="bz-fill" style="width:60%;background:var(--orange);"></div></div>'
                '<span class="bz-pct" style="color:var(--orange);">Effet calendaire global réparti (aucune diagonale isolée dominante)</span>'
                '</div>'
            )
        else:
            bz_items = (
                '<div class="bz-item bz-ok">'
                '<span class="bz-year" style="color:var(--vert);">&#10003; OK</span>'
                '<div class="bz-bar"><div class="bz-fill" style="width:0%;background:var(--vert);"></div></div>'
                '<span class="bz-pct" style="color:var(--vert);">Aucun effet significatif</span>'
                '</div>'
            )
    else:
        forts   = [e for e in bz.get('effets_calendaire', []) if e.get('significatif') and e.get('niveau') in ('FORT', 'MODÉRÉ')]
        faibles = [e for e in bz.get('effets_calendaire', []) if e.get('significatif') and e.get('niveau') == 'FAIBLE']
        for e in forts:
            amp  = float(e.get('amplitude_pct', 0))
            w    = min(abs(amp) * 5, 100)
            col  = 'var(--rouge)' if e.get('niveau') == 'FORT' else 'var(--orange)'
            niv  = e.get('niveau', '')
            sens = '↑' if e.get('sens') == 'hausse' else '↓'
            bz_items += (
                '<div class="bz-item bz-warn">'
                '<span class="bz-year">' + _s(e.get('annee_label')) + '</span>'
                '<div class="bz-bar"><div class="bz-fill" style="width:' + str(w) + '%;background:' + col + ';"></div></div>'
                '<span class="bz-pct" style="color:' + col + ';">' + f'{amp:+.1f}\u202f%' + ' ' + sens + ' ' + niv + '</span>'
                '</div>'
            )
        if faibles:
            n_f = len(faibles)
            bz_items += (
                '<div class="bz-item bz-info">'
                '<span class="bz-year" style="color:var(--cyan);">+' + str(n_f) + ' diag.</span>'
                '<div class="bz-bar"><div class="bz-fill" style="width:20%;background:var(--cyan);"></div></div>'
                '<span class="bz-pct" style="color:var(--cyan);">' + str(n_f) + ' diag. &lt; 8\u202f%</span>'
                '</div>'
            )
    b['bz_items'] = bz_items

    # -- Resultats GLM Poisson APC (test calendaire F quasi-Poisson) --
    glm_dispo  = bz.get('glm_disponible', False)
    p_cal      = bz.get('p_calendaire')
    cal_sig    = bz.get('cal_significatif')
    F_cal      = bz.get('F_calendaire')
    phi_disp   = bz.get('phi_dispersion')
    ddl_cal    = bz.get('ddl_calendaire')
    res_apc    = bz.get('reserve_apc')

    if glm_dispo and p_cal is not None:
        _cal_col  = 'var(--orange)' if cal_sig else 'var(--vert)'
        _p_fmt    = 'p &lt; 0,0001' if p_cal < 0.0001 else ('p = ' + f'{p_cal:.4f}'.replace('.', ','))
        _cal_txt  = ('Effet calendaire significatif au seuil 5 % (' + _p_fmt + ')'
                     if cal_sig else 'Effet calendaire non significatif (' + _p_fmt + ')')
        _stat_fmt = (('F = ' + f'{F_cal:.2f}'.replace('.', ',') + ' (ddl = ' + str(ddl_cal) + ')')
                     if F_cal is not None else '-')
        _phi_fmt  = (f'{phi_disp:,.0f}'.replace(',', ' ') if phi_disp else '-')
        b['bz_glm'] = (
            '<div class="section-body" style="margin-top:24px;padding:20px 28px;'
            'background:var(--navy-mid, #0D2137);border-radius:8px;'
            'border:1px solid rgba(212,175,55,0.25);">'

            '<div style="font-size:7.5pt;font-weight:700;color:var(--gold);'
            'text-transform:uppercase;letter-spacing:1.5px;margin-bottom:16px;">'
            '&#9670; GLM Poisson APC &mdash; Test F quasi-Poisson (effet calendaire)</div>'

            '<table style="width:100%;border-collapse:collapse;font-size:8.5pt;"><tbody>'
            '<tr style="border-bottom:1px solid rgba(255,255,255,0.08);">'
            '<td style="padding:8px 0;color:var(--slate);width:55%;">Conclusion du test F</td>'
            '<td style="padding:8px 0;font-weight:700;color:' + _cal_col + ';">' + _cal_txt + '</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid rgba(255,255,255,0.08);">'
            '<td style="padding:8px 0;color:var(--slate);">Statistique de test</td>'
            '<td style="padding:8px 0;"><span class="mono" style="color:var(--white);">' + _stat_fmt + '</span>'
            '<span style="color:var(--slate);font-size:7.5pt;"> &mdash; &#966; = ' + _phi_fmt + ' (sur-dispersion Poisson)</span></td>'
            '</tr>'
            + ('<tr><td style="padding:8px 0;color:var(--slate);">Réserve GLM APC (âge-cohorte)</td>'
               '<td style="padding:8px 0;"><span class="mono" style="color:var(--gold);font-weight:700;">'
               + _f(res_apc) +
               '</span><span style="color:var(--slate);font-size:7.5pt;"> &mdash; = chain-ladder par MLE '
               '(Renshaw-Verrall 1998) ; le calendaire n’est pas projeté</span></td></tr>'
               if res_apc else '') +
            '</tbody></table>'

            '<div style="margin-top:12px;font-size:7.5pt;color:var(--slate);'
            'border-top:1px solid rgba(255,255,255,0.06);padding-top:10px;">'
            'GLM Poisson cross-classifié âge-période-cohorte (Renshaw &amp; Verrall 1998). '
            'H&#8320; : effets calendaires nuls &mdash; test F quasi-Poisson (LR / &#966;), rejeté si p &lt; 0,05. '
            'Le test capte la courbure (chocs, changements de régime) ; une inflation '
            'constante est non identifiable sur le triangle seul (VERT ne l’exclut pas).</div>'
            '</div>'
        )
    else:
        b['bz_glm'] = ''

    reco_bz = _s(bz.get('recommandation'))
    bz_reco_val = reco_bz.split(' — ')[0] if ' — ' in reco_bz else reco_bz
    bz_reco_txt = reco_bz.split(' — ')[1] if ' — ' in reco_bz else ''
    b['bz_reco_box'] = (
        '<div class="recommandation-box" style="margin-top:20px;">'
        '<div class="reco-icon" style="color:var(--cyan);">↗</div>'
        '<div>'
        '<div class="reco-label">Recommandation GLM Poisson APC</div>'
        '<div class="reco-value">' + bz_reco_val + '</div>'
        '<div class="reco-text">' + bz_reco_txt + '</div>'
        '</div>'
        '</div>'
    )

    # -- Sous-section : Barnett-Zehnwirth PTF (detection tendances/ruptures, etape 2a) --
    ptf = n3.get('bz_ptf', {})
    if ptf and ptf.get('disponible'):
        _p_rc   = ptf.get('ruptures_calendaires_testees', [])
        _p_scan = ptf.get('ruptures_candidates_scan', [])
        _p_sig  = ptf.get('calendaire_significatif')
        _p_col  = 'var(--orange)' if _p_sig else 'var(--vert)'
        if _p_rc:
            _p_rows = ''.join(
                '<tr><td style="padding:6px 0;color:var(--slate);">' + _s(r.get('annee_label')) + '</td>'
                '<td style="padding:6px 0;text-align:right;"><span class="mono" style="color:'
                + ('var(--orange)' if r.get('significatif') else 'var(--slate)') + ';">'
                + ('%+.1f %%/an' % float(r.get('delta_pct_par_an', 0)))
                + ((' <span style="font-weight:400;color:var(--slate);">[%+.1f %% ; %+.1f %%]</span>'
                    % (r['ic95_pct_par_an'][0], r['ic95_pct_par_an'][1])) if r.get('ic95_pct_par_an') else '')
                + '</span></td>'
                '<td style="padding:6px 0 6px 16px;color:var(--slate);font-size:7.5pt;">p = '
                + ('%.4f' % float(r.get('p_value', 1))) + (' (significatif)' if r.get('significatif') else ' (non sig.)')
                + '</td></tr>'
                for r in _p_rc)
            _p_rcbloc = ('<table style="width:100%;border-collapse:collapse;font-size:8.5pt;margin-top:8px;">'
                         '<tbody>' + _p_rows + '</tbody></table>')
        else:
            _p_rcbloc = ('<div style="font-size:8pt;color:var(--slate);margin-top:6px;">'
                         'Aucune rupture declaree par l\'actuaire (mode semi-manuel) ; '
                         'le scan ci-dessous propose des candidats a examiner.</div>')
        _p_scantxt = ', '.join(_s(c.get('annee_label')) + ' (t = ' + ('%.1f' % float(c.get('t_stat', 0))) + ')'
                               for c in _p_scan) or 'aucun'
        _p_sigb = ptf.get('sigma_par_bande')
        _p_sigtxt = (('sigma par bande dev = ' + ', '.join(str(v) for v in _p_sigb.values()))
                     if _p_sigb else ('sigma constante = ' + str(ptf.get('sigma_constante'))))
        b['ptf_block'] = (
            '<div class="section-body" style="margin-top:20px;padding:20px 28px;'
            'background:var(--navy-mid, #0D2137);border-radius:8px;border:1px solid rgba(212,175,55,0.25);">'
            '<div style="font-size:7.5pt;font-weight:700;color:var(--gold);text-transform:uppercase;'
            'letter-spacing:1.5px;margin-bottom:12px;">'
            '&#9670; Barnett-Zehnwirth PTF (log-normal) &mdash; Tendances &amp; ruptures</div>'
            '<div style="font-size:8.5pt;font-weight:700;color:' + _p_col + ';">'
            + ('Rupture calendaire significative detectee.' if _p_sig
               else 'Aucune rupture calendaire significative confirmee.') + '</div>'
            + _p_rcbloc +
            '<div style="font-size:8pt;color:var(--slate);margin-top:10px;">'
            'Candidats de rupture (scan diagnostic, <b>non</b> testes ni retenus) : ' + _p_scantxt + '. '
            + _p_sigtxt + '.</div>'
            '<div style="margin-top:10px;font-size:7.5pt;color:var(--slate);'
            'border-top:1px solid rgba(255,255,255,0.06);padding-top:8px;">'
            'Detection log-normale (B&amp;Z 2000) &mdash; complete le test F du GLM APC '
            '(plus puissante sur tendances moderees, localise les ruptures). Ruptures semi-manuelles. '
            '&#9888; B&amp;Z detecte les <b>changements</b> de tendance, pas une inflation <b>constante</b> '
            '(non identifiable sur le triangle seul). Aucune reserve produite (etape 2a).</div>'
            '</div>'
        )
    elif ptf and (not ptf.get('disponible')) and ptf.get('message'):
        b['ptf_block'] = (
            '<div class="section-body" style="margin-top:20px;padding:14px 20px;'
            'background:var(--cyan-pale);border-left:3px solid var(--cyan);border-radius:4px;">'
            '<div style="font-size:8pt;color:var(--slate);">&#9670; Barnett-Zehnwirth PTF : '
            + _s(ptf.get('message')) + '</div></div>'
        )
    else:
        b['ptf_block'] = ''

    # ── SECTION 7 : COMMENTAIRE ACTUARIEL ────────────────────────────────────
    try:
        narration_html = _md_to_html(narration)
    except Exception as e_nar:
        logger.warning(f'_md_to_html échoué : {e_nar}')
        narration_html = '<p class="comm-p">' + _clean(narration) + '</p>' if narration else \
            '<p class="comm-p" style="color:#8A9BB0;font-style:italic;">Narration non disponible.</p>'

    source_badge = {
        'claude_api': '✦ ActuarIA Intelligence',
        'templates':  '📝 Mode standard',
        'aucune':     '',
    }.get(source_narration, '')

    b['narration_html']  = narration_html
    b['commentaire_badge'] = source_badge
    b['commentaire_header_title'] = 'Rapport de Provisionnement — ' + lob + ' · Arrêté ' + arr

    # ── SECTION 8 : JUGEMENT ─────────────────────────────────────────────────
    alertes = ''
    for a in n4.get('alertes', n2.get('alertes', [])):
        at = _clean(str(a))
        if at:
            alertes += (
                '<div class="hyp-card hyp-warn" style="margin-bottom:10px;">'
                '<div class="hyp-label"><div class="hyp-code">Point de vigilance</div></div>'
                '<div class="hyp-text">' + at + '</div>'
                '</div>'
            )
    b['alertes'] = alertes

    recs = ''
    for r in n4.get('recommandations', []):
        rt = _clean(str(r))
        if rt:
            recs += (
                '<div class="hyp-card hyp-ok" style="margin-bottom:10px;">'
                '<div class="hyp-label"><div class="hyp-code">Recommandation</div></div>'
                '<div class="hyp-text">' + rt + '</div>'
                '</div>'
            )
    b['recommandations'] = recs

    avis_txt = _clean(n4.get('avis_actuariel', ''))
    if avis_txt:
        avis_col = 'var(--rouge)' if 'DÉFAVORABLE' in avis_txt.upper() else 'var(--vert)'
        b['avis'] = (
            '<div style="background:' + avis_col + ';color:#fff;padding:16px 24px;'
            'border-radius:6px;margin-top:20px;font-size:10pt;font-weight:600;">'
            + avis_txt + '</div>'
        )
    else:
        b['avis'] = ''

    # ── PIED ─────────────────────────────────────────────────────────────────
    # Signature actuaire
    act_nom = actuaire_nom or ''
    act_ia  = actuaire_numero_ia or ''
    act_str = ''
    if act_nom:
        act_str = act_nom + (' — N° IA : ' + act_ia if act_ia else '') + ' · '
    b['pied_info'] = cli + ' · ' + lob + ' · Arrêté ' + arr + ' · Audit ID : ' + (audit_id or '—') + ' · ' + dt
    b['signature_actuaire'] = act_str
    b['actuaire_nom'] = act_nom
    b['actuaire_ia']  = act_ia

    return b


def _build_bt_table(bt: Dict, horizon: str) -> str:
    """
    Construit le tableau boni/mali pour un horizon donné.
    Affiche TOUTES les années :
    - Matures (pct_dev >= 75%) : évaluées avec statut ROUGE/AMBRE/VERT
    - Immatures : grisées, mention "Immature", non comptabilisées dans les alertes
    """
    tableau = bt.get('tableau', [])
    if not tableau:
        resultats = bt.get('resultats', {})
        hor_key = 'horizon_1' if horizon == 'n1' else 'horizon_2'
        tableau = resultats.get(hor_key, {}).get('annees', [])

    data = [r for r in tableau if isinstance(r, dict) and r.get('observe_n', 0) > 0]

    if not data:
        return (
            '<p style="font-size:9pt;color:var(--slate);font-style:italic;">'
            'Données de back-testing non disponibles pour cet arrêté.</p>'
        )

    hor_label  = 'N-1' if horizon == 'n1' else 'N-2'
    seuil_r, seuil_a = 15.0, 8.0

    html = (
        '<table class="premium"><thead><tr>'
        '<th>Année</th>'
        '<th class="right">Observé N (€)</th>'
        '<th class="right">Ultimate ' + hor_label + ' (€)</th>'
        '<th class="right">Boni/Mali (€)</th>'
        '<th class="center">Écart (%)</th>'
        '<th class="center">Développé</th>'
        '<th class="center">Statut</th>'
        '</tr></thead><tbody>'
    )

    for idx, row in enumerate(data):
        annee   = _s(row.get('annee_label', row.get('annee', '—')))
        obs     = row.get('observe_n', 0)
        ult     = row.get('ultimate_' + horizon)
        bm      = row.get('boni_mali_' + horizon)
        ecart   = row.get('ecart_pct_' + horizon)
        mature  = bool(row.get('mature', True))
        pct_dev = float(row.get('pct_developpe', 0))

        if not mature:
            # Immature — grisée et non évaluée
            html += (
                '<tr style="opacity:0.55;background:#F5F7FA;">'
                '<td class="label" style="color:var(--slate);">' + annee + '</td>'
                '<td class="right" style="color:var(--slate);"><span class="mono">' + _f(obs) + '</span></td>'
                '<td class="right" style="color:var(--slate);">—</td>'
                '<td class="right" style="color:var(--slate);">—</td>'
                '<td class="center" style="color:var(--slate);">—</td>'
                '<td class="center" style="font-size:8pt;color:var(--slate);">' + _pct(pct_dev) + '</td>'
                '<td class="center" style="font-size:8pt;color:var(--slate);font-style:italic;">Immature</td>'
                '</tr>'
            )
            continue

        # Mature — évaluée
        try:
            ecart_f = float(ecart) if ecart is not None else 0.0
            if abs(ecart_f) >= seuil_r:
                icon = '🔴'; row_bg = 'background:rgba(192,57,43,0.05);'
            elif abs(ecart_f) >= seuil_a:
                icon = '🟡'; row_bg = 'background:rgba(230,126,34,0.04);'
            else:
                icon = '✅'; row_bg = 'background:#fff;' if idx % 2 == 0 else 'background:#F8FAFB;'
        except Exception:
            icon = '—'; row_bg = ''

        html += (
            '<tr style="' + row_bg + '">'
            '<td class="label">' + annee + '</td>'
            '<td class="right"><span class="mono">' + _f(obs) + '</span></td>'
            '<td class="right"><span class="mono">' + _f(ult) + '</span></td>'
            '<td class="right"><span class="mono">' + _f(bm) + '</span></td>'
            '<td class="center">' + _pct(ecart) + '</td>'
            '<td class="center" style="font-size:8pt;color:var(--vert);">' + _pct(pct_dev) + '</td>'
            '<td class="center">' + icon + '</td>'
            '</tr>'
        )

    n_mat = sum(1 for r in data if r.get('mature', True))
    n_tot = len(data)
    n_imm = n_tot - n_mat
    note  = (' — ' + str(n_imm) + ' année(s) immature(s) non évaluée(s)') if n_imm > 0 else ''
    html += (
        '</tbody>'
        '<tfoot><tr style="background:var(--gold-pale);">'
        '<td colspan="7" style="padding:8px 14px;font-size:8pt;color:var(--text-mid);">'
        + str(n_mat) + ' année(s) mature(s) (≥ 75 %) évaluée(s) sur '
        + str(n_tot) + ' au total' + note
        + '</td></tr></tfoot>'
        '</table>'
    )
    return html
def _wrap_graph(html_g: str, titre: str) -> str:
    if not html_g:
        return ''
    return (
        '<div class="table-section-title">' + titre + '</div>'
        '<div style="margin:12px 0;border:1px solid var(--border);border-radius:6px;overflow:hidden;">'
        + html_g + '</div>'
    )


# =============================================================================
#  EXPORT HTML
# =============================================================================

def export_html(
    n1, n2, n3, n4,
    commentaire='', ref_client='', arrete='',
    audit_id='', lob_label='', graphiques=None,
    actuaire_nom='', actuaire_numero_ia='',
) -> str:
    try:
        n1=n1 or {}; n2=n2 or {}; n3=n3 or {}; n4=n4 or {}

        dt      = datetime.now().strftime('%d/%m/%Y')
        arr     = arrete or dt
        cli     = ref_client or 'À renseigner'
        lob     = _lob(lob_label or n2.get('lob_label', '') or n2.get('lob', ''))
        methode = n4.get('methode_facteurs', n2.get('methode_recommandee', '—'))
        statut  = n4.get('statut', 'AMBRE')

        narration, source = _generer_narration(n2, n3, n4, commentaire, lob, arr)

        # Graphiques Plotly — accepte go.Figure ou HTML pré-converti
        graphiques_html = {}
        if graphiques:
            for nom, fig_or_html in graphiques.items():
                try:
                    if isinstance(fig_or_html, str):
                        # Déjà converti en HTML (stockage session_state optimisé)
                        graphiques_html[nom] = fig_or_html
                    else:
                        # Objet go.Figure → convertir en HTML
                        import plotly.io as pio
                        graphiques_html[nom] = pio.to_html(
                            fig_or_html, full_html=False, include_plotlyjs=False,
                            config={'displayModeBar': False},
                        )
                except Exception as _eg:
                    logger.debug(f'Graphique {nom} ignoré : {_eg}')

        # Construire tous les blocs
        b = _build_blocks(n2, n3, n4, narration, source, lob, cli, arr, dt, audit_id, methode, statut, graphiques_html, actuaire_nom=actuaire_nom, actuaire_numero_ia=actuaire_numero_ia)

        # Assembler
        html = (
            '<!DOCTYPE html>\n<html lang="fr">\n<head>\n'
            '<meta charset="UTF-8">\n'
            '<title>Rapport Actuariel — ' + cli + ' — ' + arr + '</title>\n'
            '<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist@2.26.0/plotly.min.js"></script>\n'
            + _css() +
            '\n</head>\n<body>\n<div class="rapport-container">\n\n'

            # ── PAGE DE GARDE ──────────────────────────────────────────────
            '<div class="page-garde">\n'
            '  <div class="garde-bg">\n'
            '    <div class="garde-dots"></div>\n'
            '    <div class="garde-diagonal"></div>\n'
            '    <div class="garde-accent-line"></div>\n'
            '  </div>\n'
            '  <div class="garde-inner">\n'
            '    <div class="garde-header">\n'
            '      <div class="garde-logo-wrap"><img src="' + LOGO_URI + '" alt="ActuarIA"/></div>\n'
            '      <div class="garde-badges">\n'
            '        <span class="badge-confidentiel">⬛ Confidentiel</span>\n'
            '      </div>\n'
            '    </div>\n'
            '    <div class="garde-hero">\n'
            '      <div class="garde-eyebrow">Rapport de Provisionnement Non-Vie</div>\n'
            '      <div class="garde-titre">' + b['garde_titre'] + '</div>\n'
            '      <div class="garde-subtitle">Arrêté au ' + arr + '</div>\n'
            '      <div class="garde-sep">\n'
            '        <div class="garde-sep-line"></div>\n'
            '        <div class="garde-sep-diamond"></div>\n'
            '        <div class="garde-sep-line"></div>\n'
            '      </div>\n'
            '      <div class="garde-statut ' + b['garde_statut_cls'] + '">\n'
            '        <div class="statut-dot ' + b['garde_dot_cls'] + '"></div>\n'
            '        <div class="' + b['garde_label_cls'] + '">' + b['garde_label'] + '</div>\n'
            '      </div>\n'
            '    </div>\n'
            '    <div class="garde-footer">\n'
            '      <div class="garde-kpis">' + b['garde_kpis'] + '</div>\n'
            '    </div>\n'
            '  </div>\n'
            '</div>\n\n'

            # ── CORPS ──────────────────────────────────────────────────────
            '<div class="rapport-body">\n\n'

            # Section 1
            '<div class="section-header"><span class="section-num">01</span><span class="section-titre">Synthèse exécutive</span></div>\n'
            '<div class="section-body">\n'
            + b['kpi_grid']
            + _wrap_graph(b['graph_convergence'], 'Convergence des méthodes — Best Estimate S2')
            + '\n</div>\n<div class="section-divider"></div>\n\n'

            # Section 2
            '<div class="section-header"><span class="section-num">02</span><span class="section-titre">Résultats par méthode actuarielle</span></div>\n'
            '<div class="section-body">\n'
            + b['tableau_methodes']
            + '<div class="table-section-title">Diagnostic — décomposition de l\'incertitude (outil analytique interne, non destiné au bilan)</div>\n'
            + b['tableau_incertitude']
            + _wrap_graph(b['graph_heatmap'], 'Triangle de développement cumulé')
            + _wrap_graph(b['graph_ibnr'], 'IBNR par année de survenance')
            + _wrap_graph(b['graph_bootstrap'], 'Distribution Bootstrap ODP — Quantiles de réserve')
            + '\n</div>\n<div class="section-divider"></div>\n\n'

            # Section 3
            '<div class="section-header"><span class="section-num">03</span><span class="section-titre">Validation des hypothèses actuarielles</span></div>\n'
            '<div class="section-body">\n'
            '<div class="hyp-grid">' + b['hyp_cards'] + '</div>\n'
            + b['methode_rec_box']
            + '\n</div>\n<div class="section-divider"></div>\n\n'

            # Section 4
            '<div class="section-header"><span class="section-num">04</span><span class="section-titre">SCR Provisions — Art. 105 Solvabilité 2</span></div>\n'
            '<div class="section-body">\n'
            + b['tableau_scr']
            + '\n</div>\n<div class="section-divider"></div>\n\n'

            # Section 5
            '<div class="section-header"><span class="section-num">05</span><span class="section-titre">Back-testing — Boni / Mali de liquidation</span></div>\n'
            '<div class="section-body">\n'
            + b['bt_summary']
            + '<div class="table-section-title">Tableau N-1 — Horizon un an</div>\n'
            + b['tableau_bt_n1']
            + '<div class="table-section-title" style="margin-top:20px;">Tableau N-2 — Horizon deux ans</div>\n'
            + b['tableau_bt_n2']
            + _wrap_graph(b['graph_bt'], 'Boni/Mali de liquidation — Horizons N-1 et N-2')
            + b['bt_note']
            + '\n</div>\n<div class="section-divider"></div>\n\n'

            # Section 6
            '<div class="section-header"><span class="section-num">06</span><span class="section-titre">Effets calendaires — GLM Poisson APC (Renshaw-Verrall 1998)</span></div>\n'
            '<div class="section-body">\n'
            '<div class="bz-grid">' + b['bz_items'] + '</div>\n'
            + b.get('bz_glm', '') + '\n'
            + b['bz_reco_box']
            + b.get('ptf_block', '')
            + '\n</div>\n<div class="section-divider"></div>\n\n'

            # Section 7 — COMMENTAIRE COMPLET
            '<div class="section-header"><span class="section-num">07</span><span class="section-titre">Commentaire actuariel</span></div>\n'
            '<div class="section-body">\n'
            '<div class="commentaire-wrap">\n'
            '  <div class="commentaire-header">\n'
            '    <span class="commentaire-header-title">' + b['commentaire_header_title'] + '</span>\n'
            '    <span class="commentaire-ai-badge">' + b['commentaire_badge'] + '</span>\n'
            '  </div>\n'
            '  <div class="commentaire-body">\n'
            '    <p style="font-size:8pt;color:var(--slate);margin-bottom:20px;font-style:italic;">'
            'Commentaire à destination du Conseil d\'Administration et de l\'Actuaire Désigné.<br>'
            'Document soumis à l\'ACPR dans le cadre du reporting Solvabilité 2.</p>\n'
            + b['narration_html']
            + '\n    <div class="comm-footer">✦ Narration générée par ActuarIA Intelligence · Agent A7 Ibrahim v5.0 · ' + dt + '</div>\n'
            '  </div>\n'
            '</div>\n'
            '</div>\n<div class="section-divider"></div>\n\n'

            # Section 8
            '<div class="section-header"><span class="section-num">08</span><span class="section-titre">Jugement actuariel &amp; Recommandations</span></div>\n'
            '<div class="section-body">\n'
            '<div class="hyp-grid">' + b['alertes'] + b['recommandations'] + '</div>\n'
            + b['avis']
            + '\n</div>\n\n'

            '</div>\n\n'

            # ── PIED DE PAGE ───────────────────────────────────────────────
            '<div class="pied-de-page">\n'
            '  <div class="pied-logo"><img src="' + LOGO_URI + '" alt="ActuarIA"/></div>\n'
            '  <div class="pied-meta">'
            + b['signature_actuaire']
            + b['pied_info'] + '<br>'
            '    <span style="font-size:6.5pt;color:#8A9AB0;">'
            'Rapport établi conformément à l\'Art. 77 et 105 de la Directive Solvabilité II '
            'et au Guide Institut des Actuaires 2023</span><br>'
            '    <span class="confidentiel-footer">CONFIDENTIEL — USAGE STRICTEMENT ACTUARIEL</span>\n'
            '  </div>\n'
            '</div>\n\n'
            '</div>\n</body>\n</html>'
        )

        logger.info(f'HTML v5 : {len(html):,} chars — narration={source}')
        return html

    except Exception as e:
        logger.error(f'export_html échoué : {e}', exc_info=True)
        return '<html><body><h1>Erreur : ' + str(e) + '</h1></body></html>'


# =============================================================================
#  EXPORT PDF
# =============================================================================

def export_pdf(n1=None, n2=None, n3=None, n4=None,
               commentaire='', ref_client='', arrete='',
               audit_id='', lob_label='', graphiques=None,
               actuaire_nom='', actuaire_numero_ia='', **kw) -> bytes:
    n1=n1 or {}; n2=n2 or {}; n3=n3 or {}; n4=n4 or {}
    try:
        from weasyprint import HTML as WH
        html = export_html(n1, n2, n3, n4, commentaire, ref_client, arrete, audit_id, lob_label, graphiques,
                           actuaire_nom=actuaire_nom, actuaire_numero_ia=actuaire_numero_ia)
        pdf  = WH(string=html).write_pdf()
        logger.info(f'PDF : {len(pdf):,} bytes')
        return pdf
    except ImportError:
        logger.error('weasyprint non installé')
        return b''
    except Exception as e:
        logger.error(f'export_pdf : {e}', exc_info=True)
        return b''


# =============================================================================
#  EXPORT WORD
# =============================================================================

def export_word(n1, n2, n3, n4,
                commentaire='', ref_client='', arrete='',
                audit_id='', lob_label='', graphiques=None,
                actuaire_nom='', actuaire_numero_ia='') -> bytes:
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError as e:
        logger.error(f'python-docx absent : {e}'); return b''

    try:
        n1=n1 or {}; n2=n2 or {}; n3=n3 or {}; n4=n4 or {}

        def rgb(h):
            h = h.lstrip('#')
            return RGBColor(int(h[:2],16), int(h[2:4],16), int(h[4:],16))

        NR=rgb(NAVY); GR=rgb(GOLD); BR=rgb('#FFFFFF')
        GrR=rgb(SLATE); RgR=rgb(ROUGE); VR=rgb(VERT); AR=rgb(ORANGE)

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
        bt  = n3.get('backtesting',{});   bz = n3.get('glm_apc',{})
        h1  = n2.get('h1_independance',{}); h2 = n2.get('h2_stabilite',{})
        h3  = n2.get('h3_apriori_bf',{});  h4  = n2.get('h4_homosc_bootstrap',{})

        BE  = float(n4.get('best_estimate',0) or 0)
        SIG = float(mk.get('sigma_total',0) or 0)
        P75 = float(n4.get('reserve_p75',0) or 0)
        P90 = float(n4.get('reserve_p90',0) or 0)
        P99 = float(n4.get('reserve_p99_5',0) or 0)
        CV  = float(n4.get('cv_inter_methodes',0) or 0)
        SCP = float(sc.get('scr_provisions', sc.get('scr_prov', BE*0.30)) if sc else BE*0.30)
        SCR = SCP/BE*100 if BE else 0
        SIG_EIOPA = _s(sc.get('sigma_eiopa', '0,10') if sc else '0,10')  # dynamique — cf. version HTML (L1166)

        doc = Document()
        for s in doc.sections:
            s.top_margin=Cm(2); s.bottom_margin=Cm(2)
            s.left_margin=Cm(2.5); s.right_margin=Cm(2.5)

        def _bg(cell, hex6):
            tc=cell._tc; tcp=tc.get_or_add_tcPr()
            sd=OxmlElement('w:shd')
            sd.set(qn('w:fill'),hex6.lstrip('#'))
            sd.set(qn('w:color'),'auto'); sd.set(qn('w:val'),'clear')
            tcp.append(sd)

        def _run(p, txt, bold=False, italic=False, sz=10, col=None):
            r=p.add_run(str(txt)); r.bold=bold; r.italic=italic; r.font.size=Pt(sz)
            if col: r.font.color.rgb=col
            return r

        def _h(txt, lv=1, col=None):
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(8); p.paragraph_format.space_after=Pt(3)
            sz={1:16,2:12,3:10}.get(lv,10)
            c=col or (NR if lv==1 else GR)
            _run(p,txt,bold=True,sz=sz,col=c)

        def _sep():
            p=doc.add_paragraph()
            p.paragraph_format.space_before=Pt(2); p.paragraph_format.space_after=Pt(2)
            pPr=p._p.get_or_add_pPr(); pBdr=OxmlElement('w:pBdr')
            bo=OxmlElement('w:bottom')
            bo.set(qn('w:val'),'single'); bo.set(qn('w:sz'),'6')
            bo.set(qn('w:space'),'1'); bo.set(qn('w:color'),'C9A84C')
            pBdr.append(bo); pPr.append(pBdr)

        def _tbl(heads, rows, ws=None):
            from docx.enum.table import WD_ALIGN_VERTICAL
            t=doc.add_table(rows=1+len(rows), cols=len(heads)); t.style='Table Grid'
            for i,hd in enumerate(heads):
                c=t.rows[0].cells[i]; _bg(c,'0B1E3D')
                pp=c.paragraphs[0]; pp.alignment=WD_ALIGN_PARAGRAPH.CENTER
                r=pp.add_run(str(hd)); r.bold=True; r.font.size=Pt(9); r.font.color.rgb=BR
            for ri,row in enumerate(rows):
                for ci,v in enumerate(row):
                    c=t.rows[ri+1].cells[ci]
                    if ri%2==1: _bg(c,'EEF2F7')
                    pp=c.paragraphs[0]; pp.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    r=pp.add_run(str(v) if v is not None else '—'); r.font.size=Pt(9)
            if ws:
                for i,w in enumerate(ws):
                    for row in t.rows: row.cells[i].width=Cm(w)
            doc.add_paragraph().paragraph_format.space_after=Pt(2)

        # Page de garde
        try:
            import cairosvg
            logo_png = cairosvg.svg2png(bytestring=LOGO_SVG.encode(), output_width=280)
            doc.add_picture(io.BytesIO(logo_png), width=Cm(7))
        except Exception:
            p=doc.add_paragraph()
            _run(p,'Actuar',bold=True,sz=26,col=NR); _run(p,'IA',bold=True,sz=26,col=GR)

        doc.add_paragraph()
        p=doc.add_paragraph()
        _run(p,'RAPPORT DE PROVISIONNEMENT NON-VIE\n',bold=True,sz=20,col=NR)
        _run(p,lob,bold=True,sz=14,col=GR)
        doc.add_paragraph()
        s_col_r = VR if statut=='VERT' else AR if statut=='AMBRE' else RgR
        p=doc.add_paragraph()
        _run(p,'Statut : ',sz=11,col=NR); _run(p,statut,bold=True,sz=11,col=s_col_r)
        doc.add_paragraph()
        _tbl(['Client','Branche','Méthode','Arrêté'],
             [[cli,lob,methode.replace('_',' ').title(),arr]],ws=[3.5,4.0,4.0,2.5])
        doc.add_page_break()

        _h('1. Synthèse exécutive'); _sep()
        _tbl(['Indicateur','Valeur','Indicateur','Valeur'],
             [['Best Estimate (brut)',_f(BE),'σ Mack total',_f(SIG)],
              ['P75 (composé)',_f(P75),'CV inter-méthodes',_pct(CV)],
              ['P90 (composé)',_f(P90),'SCR Provisions',_f(SCP)],
              ['P99.5 (composé)',_f(P99),'Ratio SCR/BE',_pct(SCR)]],ws=[4.5,3.5,4.5,3.5])

        _h("Diagnostic — décomposition de l'incertitude (outil analytique interne, non destiné au bilan)"); _sep()
        _tbl(['Approche','P90','σ','Centre'],
             [['Incertitude composée (retenue)',_f(P90),_f(n4.get('sigma_total_compose',SIG)),'BE pondéré'],
              ['Mack recentré',_f(n4.get('reserve_p90_mack',P90)),_f(n4.get('sigma_mack',SIG)),'BE pondéré'],
              ['Mack natif',_f(mk.get('reserve_p90',0)),_f(mk.get('sigma_total',SIG)),'réserve Mack'],
              ['Bootstrap ODP',_f(n3.get('bootstrap',{}).get('p90',0)),_f(n3.get('bootstrap',{}).get('std_bootstrap',0)),'réserve Bootstrap']],ws=[5.0,3.0,3.0,3.0])
        doc.add_page_break()

        _h('2. Résultats par méthode actuarielle'); _sep()
        _tbl(['Méthode','Réserve IBNR','Poids BE','Score','Statut'],
             [['Chain Ladder',_f(cl.get('reserve_totale')),_pct(pw.get('chain_ladder',0)*100),
               str(n2.get('scores_confiance',{}).get('chain_ladder','—')),'✓ Inclus'],
              ['Mack 1993',_f(mk.get('reserve_best_estimate')),_pct(pw.get('mack',0)*100),'—','σ (volatilité)'],
              ['Bornhuetter-Ferguson',_f(bf.get('reserve_totale')),_pct(pw.get('bornhuetter_ferguson',0)*100),'—','✓ Inclus'],
              ['Cape Cod',_f(cc.get('reserve_totale')),_pct(pw.get('cape_cod',0)*100),
               str(n2.get('scores_confiance',{}).get('cape_cod','—')),'✓ Inclus'],
              ['BEST ESTIMATE (brut)',_f(BE),'100 %','—','→ A10 (actualisation)']],ws=[4.5,3.5,2.5,2.5,3.0])
        doc.add_page_break()

        _h('3. Validation des hypothèses actuarielles'); _sep()
        rows_h=[]
        for lbl,h in [('H1 Indépendance',h1),('H2 Stabilité',h2),('H3 A priori BF',h3),('H4 Homoscédasticité',h4)]:
            if not h: continue
            ok=bool(h.get('ok',True))
            rows_h.append([lbl,'VALIDÉE' if ok else 'REJETÉE',str(h.get('score','—'))+'/100',str(h.get('message',''))[:80]])
        if rows_h: _tbl(['Hypothèse','Résultat','Score','Message'],rows_h,ws=[4.0,2.5,2.0,7.5])
        doc.add_page_break()

        _h('4. SCR Provisions — Art. 105 S2'); _sep()
        _tbl(['Composante','Valeur','Référence'],
             [['Best Estimate (brut)',_f(BE),'Art. 77 — avant actualisation'],
              ['Facteur σ EIOPA',SIG_EIOPA,'Annexe II, Rgt 2015/35'],
              ['SCR Provisions',_f(SCP),'3 × σ × BE'],
              ['Ratio SCR/BE',_pct(SCR),'< 35 %']],ws=[4.5,3.5,8.0])
        doc.add_page_break()

        _h('5. Back-testing — Boni / Mali de liquidation'); _sep()
        bt_s = str(bt.get('statut','—')); bt_sc = str(bt.get('score_qualite','—'))
        p=doc.add_paragraph()
        s_bt = VR if bt_s=='VERT' else AR if bt_s=='AMBRE' else RgR
        _run(p,'Statut : ',sz=9,col=NR); _run(p,bt_s,bold=True,sz=9,col=s_bt)
        _run(p,' | Score : '+bt_sc+'/100',sz=9,col=NR)
        _run(p,' | N-1 : '+str(bt.get('n_rouge_n1',0))+' rouge / '+str(bt.get('n_ambre_n1',0))+' ambre',sz=9,col=NR)
        _run(p,' | N-2 : '+str(bt.get('n_rouge_n2',0))+' rouge / '+str(bt.get('n_ambre_n2',0))+' ambre',sz=9,col=NR)
        doc.add_page_break()

        _h('6. Effets calendaire — GLM Poisson APC (Renshaw-Verrall 1998)'); _sep()
        n_sig_w = int(bz.get('n_effets_significatifs',0))
        if n_sig_w == 0:
            p=doc.add_paragraph(); _run(p,'✅ Aucun effet calendaire significatif.',sz=9,col=VR)
        else:
            for e in bz.get('effets_calendaire',[]):
                if e.get('significatif'):
                    e_l=str(e.get('annee_label','—')); e_a=round(float(e.get('amplitude_pct',0)),1); e_n=str(e.get('niveau','—'))
                    p=doc.add_paragraph(); p.paragraph_format.left_indent=Cm(0.4)
                    _run(p,f'⚠️ {e_l} : {e_a:+.1f}% ({e_n})',sz=9,col=AR)
        doc.add_page_break()

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
                            p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(3)
                            p.paragraph_format.left_indent=Cm(0.3)
                            _run(p,ln,sz=9,col=NR)
            if source=='claude_api':
                p=doc.add_paragraph()
                _run(p,'✦ Narration générée par ActuarIA Intelligence',sz=7,italic=True,col=GrR)
        else:
            p=doc.add_paragraph(); _run(p,'Narration non disponible.',sz=9,italic=True)
        doc.add_page_break()

        _h('8. Jugement actuariel & Recommandations'); _sep()
        for a in n4.get('alertes',n2.get('alertes',[])):
            at=_clean(str(a))
            if at:
                p=doc.add_paragraph(); p.paragraph_format.left_indent=Cm(0.4)
                _run(p,'⚠️  ',sz=10,col=AR); _run(p,at,sz=9,col=NR)
        for r in n4.get('recommandations',[]):
            rt=_clean(str(r))
            if rt:
                p=doc.add_paragraph(); p.paragraph_format.left_indent=Cm(0.4)
                _run(p,'→  ',bold=True,sz=10,col=GR); _run(p,rt,sz=9,col=NR)
        avis_w=_clean(n4.get('avis_actuariel',''))
        if avis_w:
            doc.add_paragraph()
            p=doc.add_paragraph()
            _run(p,avis_w,sz=10,bold=True,col=RgR if 'DÉFAVORABLE' in avis_w.upper() else VR)

        _sep()
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        _run(p,'ActuarIA · '+cli+' · '+lob+' · Arrêté '+arr+' · '+dt+' · CONFIDENTIEL',sz=7,italic=True,col=GrR)

        buf=io.BytesIO(); doc.save(buf); buf.seek(0)
        wb=buf.read()
        logger.info(f'Word : {len(wb):,} bytes')
        return wb

    except Exception as e:
        logger.error(f'export_word : {e}', exc_info=True)
        return b''
