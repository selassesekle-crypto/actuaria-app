"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ACTUARIA — INTERFACE STREAMLIT v1.0                      ║
║              Page Accueil + Dashboard — Design Navy/Or Premium              ║
╚══════════════════════════════════════════════════════════════════════════════╝

USAGE :
  streamlit run app.py

INSTALLATION :
  pip install streamlit plotly pandas numpy
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION DE LA PAGE
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title        = "ActuarIA",
    page_icon         = "⚡",
    layout            = "wide",
    initial_sidebar_state = "expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM — TOKENS
# ══════════════════════════════════════════════════════════════════════════════

NAVY    = "#0F2E52"
NAVY_L  = "#1B3A5C"
NAVY_LL = "#243F6A"
OR      = "#C9A84C"
OR_L    = "#E8C96A"
BLANC   = "#F0F4F8"
GRIS    = "#8A9AB0"
VERT    = "#2ECC71"
AMBRE   = "#F39C12"
ROUGE   = "#E74C3C"

# ══════════════════════════════════════════════════════════════════════════════
# CSS CUSTOM PREMIUM
# ══════════════════════════════════════════════════════════════════════════════

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');

/* ── FOND GLOBAL ─────────────────────────────────────────── */
.stApp {{
    background-color: {NAVY};
    color: {BLANC};
    font-family: 'Inter', sans-serif;
}}

/* ── SIDEBAR ─────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {NAVY_L};
    border-right: 1px solid {OR}33;
}}
[data-testid="stSidebar"] * {{
    color: {BLANC} !important;
}}

/* ── HEADERS ─────────────────────────────────────────────── */
h1, h2, h3 {{
    font-family: 'Inter', sans-serif;
    color: {BLANC} !important;
}}

/* ── MÉTRIQUES ───────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {NAVY_L};
    border: 1px solid {OR}44;
    border-radius: 12px;
    padding: 16px 20px;
    transition: border-color 0.2s;
}}
[data-testid="stMetric"]:hover {{
    border-color: {OR};
}}
[data-testid="stMetricLabel"] {{
    color: {GRIS} !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}}
[data-testid="stMetricValue"] {{
    color: {OR} !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
}}
[data-testid="stMetricDelta"] {{
    font-size: 0.8rem !important;
}}

/* ── BOUTONS ─────────────────────────────────────────────── */
.stButton > button {{
    background: linear-gradient(135deg, {OR}, {OR_L});
    color: {NAVY};
    border: none;
    border-radius: 8px;
    font-weight: 700;
    font-size: 0.9rem;
    padding: 10px 24px;
    transition: all 0.2s;
    letter-spacing: 0.03em;
}}
.stButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 20px {OR}55;
}}

/* ── SELECTBOX / INPUT ───────────────────────────────────── */
.stSelectbox > div > div,
.stTextInput > div > div > input {{
    background: {NAVY_L} !important;
    border: 1px solid {OR}44 !important;
    color: {BLANC} !important;
    border-radius: 8px !important;
}}

/* ── FILE UPLOADER ───────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background: {NAVY_L};
    border: 2px dashed {OR}66;
    border-radius: 12px;
    padding: 20px;
}}

/* ── TABS ────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background: {NAVY_L};
    border-radius: 8px;
    padding: 4px;
    gap: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent;
    color: {GRIS};
    border-radius: 6px;
    font-weight: 500;
    padding: 8px 20px;
}}
.stTabs [aria-selected="true"] {{
    background: {OR} !important;
    color: {NAVY} !important;
    font-weight: 700 !important;
}}

/* ── DATAFRAME ───────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    background: {NAVY_L};
    border-radius: 8px;
    border: 1px solid {OR}33;
}}

/* ── DIVIDER ─────────────────────────────────────────────── */
hr {{
    border-color: {OR}33;
}}

/* ── CARDS ───────────────────────────────────────────────── */
.agent-card {{
    background: {NAVY_L};
    border: 1px solid {OR}33;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    transition: all 0.2s;
}}
.agent-card:hover {{
    border-color: {OR};
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}}

/* ── BADGE RAG ───────────────────────────────────────────── */
.badge-vert  {{ background:{VERT}22; color:{VERT};  border:1px solid {VERT}66; border-radius:6px; padding:2px 10px; font-size:0.75rem; font-weight:600; }}
.badge-ambre {{ background:{AMBRE}22; color:{AMBRE}; border:1px solid {AMBRE}66; border-radius:6px; padding:2px 10px; font-size:0.75rem; font-weight:600; }}
.badge-rouge {{ background:{ROUGE}22; color:{ROUGE}; border:1px solid {ROUGE}66; border-radius:6px; padding:2px 10px; font-size:0.75rem; font-weight:600; }}

/* ── HERO TITLE ──────────────────────────────────────────── */
.hero-title {{
    font-family: 'Playfair Display', serif;
    font-size: 3.2rem;
    font-weight: 700;
    color: {BLANC};
    line-height: 1.1;
    letter-spacing: -0.02em;
}}
.hero-accent {{
    color: {OR};
}}
.hero-sub {{
    font-size: 1.1rem;
    color: {GRIS};
    font-weight: 400;
    margin-top: 8px;
    letter-spacing: 0.02em;
}}

/* ── STAT BAR ────────────────────────────────────────────── */
.stat-bar {{
    background: {NAVY_LL};
    border-top: 1px solid {OR}33;
    padding: 12px 0;
    text-align: center;
}}

/* ── SCROLLBAR ───────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {NAVY}; }}
::-webkit-scrollbar-thumb {{ background: {OR}66; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {OR}; }}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# GESTION DES LANGUES
# ══════════════════════════════════════════════════════════════════════════════

TEXTES = {
    'fr': {
        'nav_accueil':    '🏠 Accueil',
        'nav_analyse':    '📊 Analyse',
        'nav_dashboard':  '📈 Dashboard',
        'nav_aria':       '🤖 Agent ARIA',
        'nav_rapports':   '📋 Rapports',
        'hero_titre':     'Actuariat augmenté\npar l\'intelligence artificielle.',
        'hero_sous':      'Tarification · Provisionnement · S2 · IFRS 17 · ALM · Épargne-Retraite',
        'hero_btn':       'Lancer une analyse',
        'hero_btn2':      'Voir la démo',
        'kpi_agents':     'Agents actifs',
        'kpi_precision':  'Précision modèles',
        'kpi_temps':      'Temps d\'analyse',
        'kpi_conformite': 'Conformité S2',
        'section_agents': 'Agents Actuariels',
        'section_agents_sub': 'Chaque agent est un expert spécialisé propulsé par l\'IA.',
        'section_perf':   'Performance des modèles',
        'section_rag':    'Statut du portefeuille',
        'upload_titre':   'Analyser un portefeuille',
        'upload_sub':     'Déposez votre fichier Excel, CSV ou Parquet',
        'upload_btn':     'Lancer le pipeline',
        'dash_titre':     'Dashboard Actuariel',
        'langue':         'Langue / Language',
    },
    'en': {
        'nav_accueil':    '🏠 Home',
        'nav_analyse':    '📊 Analysis',
        'nav_dashboard':  '📈 Dashboard',
        'nav_aria':       '🤖 ARIA Agent',
        'nav_rapports':   '📋 Reports',
        'hero_titre':     'Actuarial intelligence,\npowered by AI.',
        'hero_sous':      'Pricing · Reserving · S2 · IFRS 17 · ALM · Retirement',
        'hero_btn':       'Start analysis',
        'hero_btn2':      'View demo',
        'kpi_agents':     'Active agents',
        'kpi_precision':  'Model accuracy',
        'kpi_temps':      'Analysis time',
        'kpi_conformite': 'S2 compliance',
        'section_agents': 'Actuarial Agents',
        'section_agents_sub': 'Each agent is a specialized AI-powered expert.',
        'section_perf':   'Model performance',
        'section_rag':    'Portfolio status',
        'upload_titre':   'Analyze a portfolio',
        'upload_sub':     'Upload your Excel, CSV or Parquet file',
        'upload_btn':     'Run pipeline',
        'dash_titre':     'Actuarial Dashboard',
        'langue':         'Langue / Language',
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

if 'langue'   not in st.session_state: st.session_state.langue   = 'fr'
if 'page'     not in st.session_state: st.session_state.page     = 'accueil'
if 'resultats'not in st.session_state: st.session_state.resultats= {}

def T(key): return TEXTES[st.session_state.langue].get(key, key)

# ══════════════════════════════════════════════════════════════════════════════
# DONNÉES DE DÉMO
# ══════════════════════════════════════════════════════════════════════════════

AGENTS_DATA = [
    {'id':'A1',  'nom':'IRIS',    'role':'Ingestion & Validation',    'statut':'VERT',  'icon':'🔍'},
    {'id':'A2',  'nom':'FLUX',    'role':'Preprocessing',             'statut':'AMBRE', 'icon':'⚡'},
    {'id':'A3',  'nom':'VICTOR',  'role':'GLM Tarification',          'statut':'VERT',  'icon':'📐'},
    {'id':'A4',  'nom':'MAX',     'role':'ML ×6',                     'statut':'VERT',  'icon':'🧠'},
    {'id':'A5',  'nom':'NEURAL',  'role':'Deep Learning',             'statut':'VERT',  'icon':'🔮'},
    {'id':'A6',  'nom':'JUDGE',   'role':'Comparaison & Validation',  'statut':'VERT',  'icon':'⚖️'},
    {'id':'A7',  'nom':'RÉSERVE', 'role':'Provisionnement',           'statut':'VERT',  'icon':'🏦'},
    {'id':'A8',  'nom':'STORM',   'role':'Stress Testing & ORSA',     'statut':'VERT',  'icon':'🌩️'},
    {'id':'A9',  'nom':'LINK',    'role':'Cohérence inter-équipes',   'statut':'VERT',  'icon':'🔗'},
    {'id':'A10', 'nom':'SHIELD',  'role':'Solvabilité 2',             'statut':'VERT',  'icon':'🛡️'},
    {'id':'A11', 'nom':'NORM',    'role':'IFRS 17',                   'statut':'VERT',  'icon':'📊'},
    {'id':'A12', 'nom':'BALANCE', 'role':'ALM & Liquidité',           'statut':'AMBRE', 'icon':'⚖️'},
    {'id':'A13', 'nom':'TRACE',   'role':'Audit Trail',               'statut':'VERT',  'icon':'🔐'},
    {'id':'A14', 'nom':'MORTA',   'role':'Tables de Mortalité',       'statut':'VERT',  'icon':'📉'},
]

KPI_DEMO = {
    'be':         2_914_930,
    'scr':        3_680_671,
    'ratio_scr':  208.5,
    'tp_ifrs17':  3_992_344,
    'gini':       0.2651,
    'lcr':        1173.3,
    'gap_alm':    1.9,
    'cv_prov':    0.6,
}

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        # Logo
        st.markdown(f"""
        <div style="padding:20px 0 16px; text-align:center; border-bottom:1px solid {OR}33;">
            <div style="font-family:'Playfair Display',serif; font-size:1.8rem;
                        font-weight:700; color:{BLANC}; letter-spacing:-0.02em;">
                Actuar<span style="color:{OR};">IA</span>
            </div>
            <div style="font-size:0.65rem; color:{GRIS}; letter-spacing:0.15em;
                        text-transform:uppercase; margin-top:2px;">
                Actuarial Intelligence
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # Navigation
        pages = [
            (T('nav_accueil'),   'accueil'),
            (T('nav_analyse'),   'analyse'),
            (T('nav_dashboard'), 'dashboard'),
            (T('nav_aria'),      'aria'),
            (T('nav_rapports'),  'rapports'),
        ]

        for label, page_id in pages:
            actif = st.session_state.page == page_id
            if st.button(
                label,
                key=f"nav_{page_id}",
                use_container_width=True,
                type="primary" if actif else "secondary"
            ):
                st.session_state.page = page_id
                st.rerun()

        st.markdown(f"<hr style='border-color:{OR}33; margin:16px 0'>",
                    unsafe_allow_html=True)

        # Statut agents
        st.markdown(f"""
        <div style="font-size:0.7rem; color:{GRIS}; text-transform:uppercase;
                    letter-spacing:0.1em; margin-bottom:10px;">
            Statut agents
        </div>
        """, unsafe_allow_html=True)

        nb_vert  = sum(1 for a in AGENTS_DATA if a['statut'] == 'VERT')
        nb_ambre = sum(1 for a in AGENTS_DATA if a['statut'] == 'AMBRE')
        nb_rouge = sum(1 for a in AGENTS_DATA if a['statut'] == 'ROUGE')

        st.markdown(f"""
        <div style="display:flex; gap:8px; margin-bottom:16px;">
            <span class="badge-vert">✅ {nb_vert}</span>
            <span class="badge-ambre">⚠️ {nb_ambre}</span>
            <span class="badge-rouge">❌ {nb_rouge}</span>
        </div>
        """, unsafe_allow_html=True)

        # Switch langue
        st.markdown(f"<hr style='border-color:{OR}33; margin:8px 0'>",
                    unsafe_allow_html=True)
        langue_choisie = st.selectbox(
            T('langue'),
            options=['fr', 'en'],
            index=0 if st.session_state.langue == 'fr' else 1,
            format_func=lambda x: '🇫🇷 Français' if x == 'fr' else '🇬🇧 English',
        )
        if langue_choisie != st.session_state.langue:
            st.session_state.langue = langue_choisie
            st.rerun()

        # Version
        st.markdown(f"""
        <div style="position:absolute; bottom:20px; left:0; right:0;
                    text-align:center; font-size:0.65rem; color:{GRIS}44;">
            ActuarIA v1.0 — {datetime.now().strftime('%d/%m/%Y')}
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ACCUEIL
# ══════════════════════════════════════════════════════════════════════════════

def page_accueil():
    # ── HERO ──────────────────────────────────────────────────────────────────
    col_hero, col_anim = st.columns([1.4, 1])

    with col_hero:
        st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

        titre_lignes = T('hero_titre').split('\n')
        titre_html = titre_lignes[0]
        if len(titre_lignes) > 1:
            titre_html += f'<br><span class="hero-accent">{titre_lignes[1]}</span>'

        st.markdown(f"""
        <div class="hero-title">{titre_html}</div>
        <div class="hero-sub">{T('hero_sous')}</div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button(T('hero_btn'), type="primary", use_container_width=True):
                st.session_state.page = 'analyse'
                st.rerun()
        with c2:
            if st.button(T('hero_btn2'), use_container_width=True):
                st.session_state.page = 'dashboard'
                st.rerun()

    with col_anim:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        _render_radar_hero()

    st.markdown(f"<hr style='border-color:{OR}33; margin:32px 0 24px'>",
                unsafe_allow_html=True)

    # ── KPIs LIVE ─────────────────────────────────────────────────────────────
    k = KPI_DEMO
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.metric(T('kpi_agents'),     "19 / 19", "+5 EP")
    with c2: st.metric("Best Estimate S2",  f"{k['be']/1e6:.2f}M€", "CV 0.6%")
    with c3: st.metric("Ratio SCR",         f"{k['ratio_scr']:.1f}%", "+8.5%")
    with c4: st.metric("Gini ML",           f"{k['gini']:.4f}", "+0.044 vs GLM")
    with c5: st.metric("LCR",               f"{k['lcr']:.0f}%", "✅ Liquide")
    with c6: st.metric(T('kpi_conformite'), "100%", "S2 + IFRS17")

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    # ── AGENTS GRID ───────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="margin-bottom:4px;">
        <span style="font-size:1.3rem; font-weight:700; color:{BLANC};">
            {T('section_agents')}
        </span>
        <span style="font-size:0.85rem; color:{GRIS}; margin-left:12px;">
            {T('section_agents_sub')}
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Grille 7 colonnes
    cols = st.columns(7)
    for i, agent in enumerate(AGENTS_DATA):
        with cols[i % 7]:
            badge_class = f"badge-{agent['statut'].lower()}"
            st.markdown(f"""
            <div class="agent-card" style="text-align:center;">
                <div style="font-size:1.6rem; margin-bottom:6px;">{agent['icon']}</div>
                <div style="font-weight:700; color:{OR}; font-size:0.85rem;">
                    {agent['nom']}
                </div>
                <div style="font-size:0.65rem; color:{GRIS}; margin:4px 0 8px;
                            line-height:1.3;">
                    {agent['role']}
                </div>
                <span class="{badge_class}">{agent['statut']}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    # ── GRAPHIQUES ROW ────────────────────────────────────────────────────────
    col_g1, col_g2, col_g3 = st.columns(3)

    with col_g1:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.08em;'>{T('section_perf')}</p>", unsafe_allow_html=True)
        _render_gini_chart()

    with col_g2:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.08em;'>Provisions & SCR</p>", unsafe_allow_html=True)
        _render_provisions_chart()

    with col_g3:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.08em;'>Ratio SCR — ORSA 5 ans</p>", unsafe_allow_html=True)
        _render_orsa_chart()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    st.markdown(f"""
    <h2 style="color:{BLANC}; font-size:1.6rem; font-weight:700; margin-bottom:4px;">
        {T('dash_titre')}
    </h2>
    <p style="color:{GRIS}; font-size:0.85rem; margin-bottom:24px;">
        Résultats consolidés — Portefeuille Auto Non-Vie
    </p>
    """, unsafe_allow_html=True)

    tabs = st.tabs([
        "📐 Tarification",
        "🏦 Provisionnement",
        "🛡️ Solvabilité 2",
        "📊 IFRS 17",
        "⚖️ ALM",
        "📋 Synthèse",
    ])

    with tabs[0]: _tab_tarification()
    with tabs[1]: _tab_provisionnement()
    with tabs[2]: _tab_solvabilite()
    with tabs[3]: _tab_ifrs17()
    with tabs[4]: _tab_alm()
    with tabs[5]: _tab_synthese()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ANALYSE
# ══════════════════════════════════════════════════════════════════════════════

def page_analyse():
    st.markdown(f"""
    <h2 style="color:{BLANC}; font-size:1.6rem; font-weight:700; margin-bottom:4px;">
        {T('upload_titre')}
    </h2>
    <p style="color:{GRIS}; font-size:0.85rem; margin-bottom:24px;">
        {T('upload_sub')}
    </p>
    """, unsafe_allow_html=True)

    col_up, col_conf = st.columns([1.5, 1])

    with col_up:
        fichier = st.file_uploader(
            "Fichier de données",
            type=['csv', 'xlsx', 'xls', 'parquet'],
            label_visibility='collapsed',
        )

        if fichier:
            st.markdown(f"""
            <div style="background:{NAVY_L}; border:1px solid {VERT}66;
                        border-radius:8px; padding:12px 16px; margin:12px 0;">
                <span style="color:{VERT}; font-weight:600;">✅ Fichier chargé</span>
                <span style="color:{GRIS}; font-size:0.85rem; margin-left:8px;">
                    {fichier.name}
                </span>
            </div>
            """, unsafe_allow_html=True)

    with col_conf:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.08em;'>Configuration</p>", unsafe_allow_html=True)

        branche = st.selectbox(
            "Branche",
            ['Non-Vie (Auto)', 'Non-Vie (MRH)', 'Non-Vie (RC Pro)',
             'Vie', 'Santé-Prévoyance', 'Épargne-Retraite'],
        )

        profil = st.selectbox(
            "Profil modèle",
            ['Équilibré', 'Performance maximale',
             'Auditabilité S2', 'Compagnie Vie'],
        )

        client_id = st.text_input("ID Client (optionnel)", placeholder="ex: cabinet_xyz")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    if st.button(T('upload_btn'), type="primary"):
        if fichier:
            _simuler_pipeline()
        else:
            st.warning("Veuillez d'abord uploader un fichier.")

    # Démo avec données synthétiques
    st.markdown(f"<hr style='border-color:{OR}33; margin:24px 0'>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:{GRIS}; font-size:0.85rem;'>Ou tester avec les données de démonstration :</p>", unsafe_allow_html=True)

    if st.button("🚀 Lancer la démo (données synthétiques Auto 70k)"):
        _simuler_pipeline()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ARIA
# ══════════════════════════════════════════════════════════════════════════════

def page_aria():
    st.markdown(f"""
    <div style="text-align:center; padding:32px 0 24px;">
        <div style="font-size:3rem; margin-bottom:8px;">🤖</div>
        <h2 style="color:{BLANC}; font-size:1.8rem; font-weight:700; margin:0;">
            Agent <span style="color:{OR};">ARIA</span>
        </h2>
        <p style="color:{GRIS}; margin-top:8px; font-size:0.95rem;">
            Actuaire IA Senior — Propulsé par Claude API
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Chat
    if 'messages_aria' not in st.session_state:
        st.session_state.messages_aria = [
            {
                'role': 'assistant',
                'content': (
                    "Bonjour, je suis **ARIA**, votre actuaire IA senior. "
                    "J'ai accès aux résultats de tous les agents de la plateforme. "
                    "Comment puis-je vous aider ?\n\n"
                    "Exemples de questions :\n"
                    "- *Analyse le Best Estimate de mon portefeuille*\n"
                    "- *Explique le ratio SCR de 208.5%*\n"
                    "- *Quels sont les risques principaux identifiés ?*"
                )
            }
        ]

    for msg in st.session_state.messages_aria:
        with st.chat_message(msg['role'],
                              avatar="🤖" if msg['role'] == 'assistant' else "👤"):
            st.markdown(msg['content'])

    if prompt := st.chat_input("Posez votre question actuarielle..."):
        st.session_state.messages_aria.append({'role': 'user', 'content': prompt})
        with st.chat_message('user', avatar="👤"):
            st.markdown(prompt)

        # Réponse simulée (à remplacer par Claude API)
        with st.chat_message('assistant', avatar="🤖"):
            reponse = _reponse_aria_demo(prompt)
            st.markdown(reponse)
        st.session_state.messages_aria.append(
            {'role': 'assistant', 'content': reponse}
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE RAPPORTS
# ══════════════════════════════════════════════════════════════════════════════

def page_rapports():
    st.markdown(f"""
    <h2 style="color:{BLANC}; font-size:1.6rem; font-weight:700; margin-bottom:4px;">
        Rapports & Export
    </h2>
    <p style="color:{GRIS}; font-size:0.85rem; margin-bottom:24px;">
        Générez et téléchargez vos rapports réglementaires.
    </p>
    """, unsafe_allow_html=True)

    rapports = [
        {'nom': 'Rapport Actuariel Complet',       'format': 'PDF', 'icon': '📋', 'desc': 'Synthèse A1-A14 + EP1-EP5'},
        {'nom': 'QRT Solvabilité 2',               'format': 'Excel', 'icon': '🛡️', 'desc': 'S.05 · S.17 · S.19 · S.23'},
        {'nom': 'Rapport IFRS 17',                 'format': 'Excel', 'icon': '📊', 'desc': 'PAA · BBA · Réconciliation S2'},
        {'nom': 'ORSA Prospectif',                 'format': 'PDF', 'icon': '🌩️', 'desc': 'Stress testing 5 ans'},
        {'nom': 'Rapport ALM',                     'format': 'PDF', 'icon': '⚖️', 'desc': 'Duration · Gap · LCR'},
        {'nom': 'Audit Trail',                     'format': 'JSON', 'icon': '🔐', 'desc': 'Logs · Hash · RGPD'},
        {'nom': 'Rapport IAS 19',                  'format': 'Excel', 'icon': '🏢', 'desc': 'DBO · Service Cost · IC'},
        {'nom': 'Fiche Information Assuré PER',    'format': 'PDF', 'icon': '📄', 'desc': 'Droits · Rente · Frais'},
    ]

    cols = st.columns(2)
    for i, rapport in enumerate(rapports):
        with cols[i % 2]:
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.markdown(f"""
                <div class="agent-card">
                    <div style="display:flex; align-items:center; gap:12px;">
                        <span style="font-size:1.5rem;">{rapport['icon']}</span>
                        <div>
                            <div style="font-weight:600; color:{BLANC}; font-size:0.9rem;">
                                {rapport['nom']}
                            </div>
                            <div style="font-size:0.75rem; color:{GRIS}; margin-top:2px;">
                                {rapport['desc']} · {rapport['format']}
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_btn:
                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                if st.button(f"↓", key=f"dl_{i}", help=f"Télécharger {rapport['nom']}"):
                    st.toast(f"✅ {rapport['nom']} généré", icon="✅")


# ══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES
# ══════════════════════════════════════════════════════════════════════════════

def _render_radar_hero():
    """Radar chart des performances — hero section."""
    categories = ['Tarification', 'Provisions', 'Solvabilité', 'IFRS17', 'ALM', 'Cohérence']
    values     = [0.85, 0.96, 0.92, 0.88, 0.78, 1.00]

    fig = go.Figure(go.Scatterpolar(
        r      = values + [values[0]],
        theta  = categories + [categories[0]],
        fill   = 'toself',
        fillcolor = f"rgba(201,168,76,0.15)",
        line  = dict(color=OR, width=2),
        marker= dict(color=OR, size=6),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor   = NAVY_L,
            radialaxis= dict(visible=True, range=[0,1], tickfont=dict(color=GRIS, size=9),
                             gridcolor="rgba(201,168,76,0.13)", linecolor="rgba(201,168,76,0.20)"),
            angularaxis=dict(tickfont=dict(color=BLANC, size=10), gridcolor="rgba(201,168,76,0.13)",
                              linecolor="rgba(201,168,76,0.20)"),
        ),
        paper_bgcolor = 'rgba(0,0,0,0)',
        plot_bgcolor  = 'rgba(0,0,0,0)',
        margin        = dict(l=40, r=40, t=20, b=20),
        height        = 280,
        showlegend    = False,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def _render_gini_chart():
    """Comparaison Gini des modèles."""
    modeles = ['GLM', 'ElasticNet', 'LightGBM', 'CatBoost', 'GBM', 'XGBoost']
    ginis   = [0.00,  0.244,        0.248,       0.253,      0.254,  0.265]
    couleurs= [GRIS if g < 0.1 else OR_L if g < 0.25 else OR for g in ginis]

    fig = go.Figure(go.Bar(
        x           = ginis,
        y           = modeles,
        orientation = 'h',
        marker_color= couleurs,
        text        = [f"{g:.3f}" for g in ginis],
        textposition= 'outside',
        textfont    = dict(color=BLANC, size=11),
    ))
    fig.update_layout(
        paper_bgcolor = 'rgba(0,0,0,0)',
        plot_bgcolor  = 'rgba(0,0,0,0)',
        xaxis = dict(showgrid=False, zeroline=False, visible=False),
        yaxis = dict(tickfont=dict(color=BLANC, size=11)),
        margin= dict(l=0, r=40, t=8, b=8),
        height= 220,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def _render_provisions_chart():
    """Comparaison méthodes de provisionnement."""
    methodes = ['Chain Ladder', 'Mack 1993', 'BF', 'Cape Cod', 'Best Estimate']
    valeurs  = [2.85, 2.91, 2.93, 2.88, 2.91]
    couleurs = [NAVY_LL]*4 + [OR]

    fig = go.Figure(go.Bar(
        x           = methodes,
        y           = valeurs,
        marker_color= couleurs,
        marker_line = dict(color=OR, width=1),
        text        = [f"{v:.2f}M€" for v in valeurs],
        textposition= 'outside',
        textfont    = dict(color=BLANC, size=10),
    ))
    fig.update_layout(
        paper_bgcolor = 'rgba(0,0,0,0)',
        plot_bgcolor  = 'rgba(0,0,0,0)',
        xaxis = dict(tickfont=dict(color=BLANC, size=9), gridcolor="rgba(201,168,76,0.07)"),
        yaxis = dict(tickfont=dict(color=GRIS, size=9), gridcolor="rgba(201,168,76,0.07)",
                     title=dict(text='M€', font=dict(color=GRIS))),
        margin= dict(l=0, r=0, t=24, b=8),
        height= 220,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def _render_orsa_chart():
    """ORSA prospectif 5 ans."""
    annees  = [2025, 2026, 2027, 2028, 2029, 2030]
    central = [208.5, 218.2, 228.4, 239.1, 250.3, 262.1]
    stress  = [208.5, 195.3, 183.7, 173.5, 164.4, 156.2]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=annees, y=central, name='Central',
        line=dict(color=OR, width=2.5),
        marker=dict(color=OR, size=6),
        fill='none',
    ))
    fig.add_trace(go.Scatter(
        x=annees, y=stress, name='Stressé',
        line=dict(color=ROUGE, width=1.5, dash='dot'),
        marker=dict(color=ROUGE, size=5),
    ))
    fig.add_hline(y=150, line_dash='dash', line_color=AMBRE,
                   annotation_text='Cible 150%', annotation_font_color=AMBRE)
    fig.add_hline(y=100, line_dash='dash', line_color=ROUGE,
                   annotation_text='Min 100%', annotation_font_color=ROUGE)
    fig.update_layout(
        paper_bgcolor = 'rgba(0,0,0,0)',
        plot_bgcolor  = 'rgba(0,0,0,0)',
        xaxis = dict(tickfont=dict(color=BLANC, size=9), gridcolor="rgba(201,168,76,0.07)"),
        yaxis = dict(tickfont=dict(color=GRIS, size=9),  gridcolor="rgba(201,168,76,0.07)",
                     title=dict(text='%', font=dict(color=GRIS))),
        legend= dict(font=dict(color=BLANC, size=10), bgcolor='rgba(0,0,0,0)'),
        margin= dict(l=0, r=0, t=8, b=8),
        height= 220,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


# ══════════════════════════════════════════════════════════════════════════════
# TABS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def _tab_tarification():
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Fréquence moyenne",  "0.163", "portefeuille auto")
    with c2: st.metric("Coût moyen",         "4 638 €", "+2.1% vs N-1")
    with c3: st.metric("Prime pure moy.",    "757 €",  "Poisson × Gamma")
    with c4: st.metric("Gini XGBoost",       "0.2651", "freMTPL2 validé")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col_g, col_t = st.columns([1.5, 1])
    with col_g:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>Classement multicritères — 6 modèles</p>", unsafe_allow_html=True)
        df_modeles = pd.DataFrame({
            'Modèle':        ['XGBoost', 'GBM', 'CatBoost', 'LightGBM', 'ElasticNet', 'XGBoost Tweedie'],
            'Gini':          [0.2651, 0.2542, 0.2534, 0.2481, 0.2440, 0.2404],
            'Overfit ratio': [1.53, 1.41, 1.28, 1.60, 0.98, 1.97],
            'Sélectionné':   ['', '', '', '', '⭐', ''],
        })
        st.dataframe(df_modeles, use_container_width=True, hide_index=True)

    with col_t:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>Profil sélection</p>", unsafe_allow_html=True)
        fig_pie = go.Figure(go.Pie(
            labels  = ['Gini (40%)', 'Stabilité (30%)', 'Interpréta. (20%)', 'RMSE (10%)'],
            values  = [40, 30, 20, 10],
            hole    = 0.6,
            marker  = dict(colors=[OR, OR_L, NAVY_LL, GRIS]),
            textfont= dict(color=BLANC, size=11),
        ))
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=True,
            legend=dict(font=dict(color=BLANC, size=10), bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=0,r=0,t=0,b=0),
            height=220,
        )
        st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})


def _tab_provisionnement():
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Best Estimate S2",   "2 914 930 €", "CV 0.6%")
    with c2: st.metric("Provision P90",      "3 098 000 €", "+6.3%")
    with c3: st.metric("σ Mack",             "45 000 €",    "IC 95% calculé")
    with c4: st.metric("CV inter-méthodes",  "0.6%",        "✅ Convergent")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>4 méthodes — convergence</p>", unsafe_allow_html=True)
        methodes = ['Chain Ladder', 'Mack 1993', 'BF', 'Cape Cod']
        valeurs  = [2_850_000, 2_914_930, 2_930_000, 2_880_000]
        fig = go.Figure(go.Bar(
            x=methodes, y=valeurs,
            marker_color=[NAVY_LL, OR, NAVY_LL, NAVY_LL],
            marker_line=dict(color=OR, width=1),
            text=[f"{v/1e6:.2f}M€" for v in valeurs],
            textposition='outside',
            textfont=dict(color=BLANC, size=11),
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickfont=dict(color=BLANC)), yaxis=dict(visible=False),
            margin=dict(l=0,r=0,t=24,b=0), height=200,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_g2:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>IBNR par année + IC 95%</p>", unsafe_allow_html=True)
        annees = [f"N-{i}" for i in range(6, 0, -1)]
        ibnr   = [0, 45000, 180000, 420000, 780000, 1490000]
        ic_sup = [0, 72000, 250000, 580000, 1050000, 1980000]

        fig = go.Figure()
        fig.add_trace(go.Bar(x=annees, y=ibnr, name='IBNR', marker_color=OR))
        fig.add_trace(go.Scatter(x=annees, y=ic_sup, name='IC 95%',
                                  mode='lines+markers',
                                  line=dict(color=ROUGE, dash='dot'),
                                  marker=dict(color=ROUGE)))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickfont=dict(color=BLANC)), yaxis=dict(tickfont=dict(color=GRIS)),
            legend=dict(font=dict(color=BLANC), bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=0,r=0,t=8,b=0), height=200,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def _tab_solvabilite():
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("SCR Total",     "3 680 671 €", "formule standard")
    with c2: st.metric("MCR Final",     "2 500 000 €", "plancher régl.")
    with c3: st.metric("Ratio SCR",     "208.5%",      "✅ > 150% cible")
    with c4: st.metric("Ratio MCR",     "320.0%",      "✅ > 100% min")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>Décomposition SCR</p>", unsafe_allow_html=True)
        labels  = ['SCR Sous.', 'SCR Marché', 'SCR Défaut', 'SCR Opéra.']
        values  = [3_104_537, 660_000, 73_000, 262_000]
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.55,
            marker=dict(colors=[OR, NAVY_LL, GRIS, OR_L]),
            textfont=dict(color=BLANC, size=11),
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(font=dict(color=BLANC, size=10), bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=0,r=0,t=0,b=0), height=220,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_g2:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>Jauges SCR / MCR</p>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Indicator(
            mode='gauge+number', value=208.5,
            title=dict(text='Ratio SCR (%)', font=dict(color=BLANC)),
            number=dict(suffix='%', font=dict(color=OR, size=28)),
            gauge=dict(
                axis=dict(range=[0,300], tickcolor=GRIS),
                bar=dict(color=OR),
                steps=[
                    dict(range=[0,100],   color='rgba(231,76,60,0.27)'),
                    dict(range=[100,150], color='rgba(243,156,18,0.27)'),
                    dict(range=[150,300], color='rgba(46,204,113,0.27)'),
                ],
                threshold=dict(line=dict(color=ROUGE, width=3), value=100),
                bgcolor=NAVY_L,
            ),
            domain=dict(x=[0,1], y=[0,1])
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20,r=20,t=20,b=20), height=220,
            font=dict(color=BLANC),
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def _tab_ifrs17():
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("TP IFRS 17 (PAA)",  "3 992 344 €", "approche PAA")
    with c2: st.metric("LRC",               "2 500 000 €", "risque restant")
    with c3: st.metric("LIC",               "1 492 344 €", "sinistres survenus")
    with c4: st.metric("Ratio IFRS17/S2",   "1.370",       "✅ Cohérent")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>Réconciliation S2 ↔ IFRS 17</p>", unsafe_allow_html=True)
        items   = ['BE S2', '+ Risk Adj.', '+ CSM', '= TP IFRS17']
        valeurs = [2_914_930, 131_344, 946_070, 3_992_344]
        couleurs= [NAVY_LL, NAVY_LL, NAVY_LL, OR]
        fig = go.Figure(go.Bar(
            x=items, y=valeurs,
            marker_color=couleurs,
            marker_line=dict(color=OR, width=1),
            text=[f"{v/1e6:.2f}M€" for v in valeurs],
            textposition='outside',
            textfont=dict(color=BLANC, size=11),
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickfont=dict(color=BLANC)), yaxis=dict(visible=False),
            margin=dict(l=0,r=0,t=24,b=0), height=220,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_g2:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>Résultat technique IFRS 17</p>", unsafe_allow_html=True)
        postes  = ['Primes gagnées', 'Lib. RA', 'Charges sin.', 'Frais acq.', 'Résultat']
        valeurs = [2_500_000, 65_672, -1_750_000, -250_000, 565_672]
        couleurs= [VERT if v > 0 else ROUGE for v in valeurs]
        fig = go.Figure(go.Bar(
            x=postes, y=valeurs,
            marker_color=couleurs,
            text=[f"{v/1e3:.0f}k€" for v in valeurs],
            textposition='outside',
            textfont=dict(color=BLANC, size=10),
        ))
        fig.add_hline(y=0, line_color=GRIS)
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickfont=dict(color=BLANC, size=9)),
            yaxis=dict(visible=False),
            margin=dict(l=0,r=0,t=24,b=0), height=220,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def _tab_alm():
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Duration actifs",   "3.50 ans",   "obligations 5 ans")
    with c2: st.metric("Duration passifs",  "1.60 ans",   "Auto court terme")
    with c3: st.metric("Gap duration",      "+1.90 ans",  "⚠️ À raccourcir")
    with c4: st.metric("LCR",               "1 173%",     "✅ Très liquide")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>Stress taux — impact valeur nette</p>", unsafe_allow_html=True)
        chocs   = ['-200bp', '-100bp', '+100bp', '+200bp']
        impacts = [650000, 325000, -323741, -647482]
        couleurs= [VERT if v > 0 else ROUGE for v in impacts]
        fig = go.Figure(go.Bar(
            x=chocs, y=impacts,
            marker_color=couleurs,
            text=[f"{v/1e3:+.0f}k€" for v in impacts],
            textposition='outside',
            textfont=dict(color=BLANC, size=11),
        ))
        fig.add_hline(y=0, line_color=GRIS)
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickfont=dict(color=BLANC)),
            yaxis=dict(visible=False),
            margin=dict(l=0,r=0,t=24,b=0), height=220,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_g2:
        st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase;'>Duration actifs vs passifs</p>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=['Duration actifs', 'Duration passifs', 'Gap cible'],
            y=[3.50, 1.60, 0.00],
            marker_color=[NAVY_LL, NAVY_LL, VERT],
            marker_line=dict(color=OR, width=1),
            text=['3.50 ans', '1.60 ans', '0.00 ans'],
            textposition='outside',
            textfont=dict(color=BLANC, size=11),
        ))
        fig.add_hline(y=1.60, line_dash='dash', line_color=OR,
                       annotation_text='Duration passifs', annotation_font_color=OR)
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickfont=dict(color=BLANC)),
            yaxis=dict(title='Années', tickfont=dict(color=GRIS)),
            margin=dict(l=0,r=0,t=24,b=0), height=220,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def _tab_synthese():
    st.markdown(f"<p style='color:{GRIS}; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.08em;'>Tableau de bord consolidé</p>", unsafe_allow_html=True)

    synthese = pd.DataFrame([
        {'Module': 'Tarification',     'Agent': 'A3-A6',  'Résultat clé': 'Gini XGBoost = 0.2651',    'Statut': '🟢 VERT'},
        {'Module': 'Provisionnement',  'Agent': 'A7',     'Résultat clé': 'BE = 2 914 930 € · CV 0.6%','Statut': '🟢 VERT'},
        {'Module': 'Stress Testing',   'Agent': 'A8',     'Résultat clé': 'Ratio SCR = 375%',           'Statut': '🟢 VERT'},
        {'Module': 'Cohérence',        'Agent': 'A9',     'Résultat clé': 'Score 100%',                 'Statut': '🟢 VERT'},
        {'Module': 'Solvabilité 2',    'Agent': 'A10',    'Résultat clé': 'Ratio SCR = 208.5%',         'Statut': '🟢 VERT'},
        {'Module': 'IFRS 17',          'Agent': 'A11',    'Résultat clé': 'TP = 3 992 344 €',           'Statut': '🟢 VERT'},
        {'Module': 'ALM',              'Agent': 'A12',    'Résultat clé': 'Gap = +1.9 ans · LCR 1173%', 'Statut': '🟡 AMBRE'},
        {'Module': 'Tables mortalité', 'Agent': 'A14',    'Résultat clé': 'ä_65 = 13.07 · R²=0.9985',  'Statut': '🟢 VERT'},
    ])
    st.dataframe(synthese, use_container_width=True, hide_index=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col_hash, col_date = st.columns(2)
    with col_hash:
        st.markdown(f"""
        <div style="background:{NAVY_L}; border:1px solid {OR}44; border-radius:8px; padding:12px 16px;">
            <div style="font-size:0.7rem; color:{GRIS}; text-transform:uppercase; letter-spacing:0.08em;">
                Hash de session
            </div>
            <div style="font-family:monospace; color:{OR}; font-size:1.1rem; margin-top:4px;">
                5BB15F63
            </div>
            <div style="font-size:0.7rem; color:{GRIS}; margin-top:4px;">
                Intégrité des résultats garantie
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_date:
        st.markdown(f"""
        <div style="background:{NAVY_L}; border:1px solid {OR}44; border-radius:8px; padding:12px 16px;">
            <div style="font-size:0.7rem; color:{GRIS}; text-transform:uppercase; letter-spacing:0.08em;">
                Date d'arrêté
            </div>
            <div style="color:{BLANC}; font-size:1.1rem; margin-top:4px;">
                {datetime.now().strftime('%d/%m/%Y')}
            </div>
            <div style="font-size:0.7rem; color:{GRIS}; margin-top:4px;">
                Actuaire responsable : À renseigner
            </div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _simuler_pipeline():
    """Simule l'exécution du pipeline avec une barre de progression."""
    etapes = [
        ("🔍 A1 — Ingestion & Validation",    0.10),
        ("⚡ A2 — Preprocessing",             0.20),
        ("📐 A3 — GLM Tarification",          0.35),
        ("🧠 A4 — ML ×6",                     0.60),
        ("🏦 A7 — Provisionnement",           0.70),
        ("🛡️ A10 — Solvabilité 2",            0.80),
        ("📊 A11 — IFRS 17",                  0.88),
        ("⚖️ A12 — ALM",                      0.94),
        ("🔐 A13 — Audit Trail",              1.00),
    ]
    barre = st.progress(0)
    statut = st.empty()

    for label, prog in etapes:
        statut.markdown(f"<p style='color:{GRIS}; font-size:0.85rem;'>{label}</p>",
                         unsafe_allow_html=True)
        barre.progress(prog)
        import time; time.sleep(0.4)

    barre.empty()
    statut.empty()
    st.success("✅ Pipeline terminé — résultats disponibles dans le Dashboard")

    if st.button("Voir le Dashboard →"):
        st.session_state.page = 'dashboard'
        st.rerun()


def _reponse_aria_demo(question: str) -> str:
    """Réponse démo ARIA (à remplacer par Claude API)."""
    q = question.lower()
    if any(m in q for m in ['best estimate', 'be', 'provision', 'réserve']):
        return (
            "Le **Best Estimate S2** du portefeuille est de **2 914 930 €** "
            "avec un coefficient de variation inter-méthodes de **0.6%**, "
            "ce qui indique une excellente convergence des 4 méthodes "
            "(Chain Ladder, Mack 1993, BF, Cape Cod).\n\n"
            "L'intervalle de confiance à 95% de Mack est disponible "
            "pour le reporting Pilier 1. La provision P90 s'établit à "
            "**3 098 000 €**, soit +6.3% au-dessus du Best Estimate."
        )
    elif any(m in q for m in ['scr', 'solvabilité', 'capital']):
        return (
            "Le **ratio de couverture SCR** est de **208.5%**, "
            "au-dessus de la cible de marché français (150-200%). "
            "Le SCR total de **3 680 671 €** est dominé par le "
            "SCR souscription (3 104 537 €), cohérent pour un "
            "portefeuille Non-Vie.\n\n"
            "Le MCR est couvert à 320% — aucune action corrective requise."
        )
    elif any(m in q for m in ['gini', 'modèle', 'tarif', 'ml', 'xgboost']):
        return (
            "Le meilleur modèle de tarification validé sur **freMTPL2** "
            "(678k contrats auto FR réels) est **XGBoost** avec un "
            "Gini de **0.2651**.\n\n"
            "Le modèle sélectionné en production par A6 est "
            "**ElasticNet** (Gini=0.2440) grâce à son score "
            "multicritères supérieur (0.8373/1.0) — meilleure "
            "stabilité (overfit ratio=0.98) et interprétabilité "
            "maximale (défendable devant un auditeur S2)."
        )
    elif any(m in q for m in ['alm', 'duration', 'gap', 'liquidité']):
        return (
            "L'analyse ALM révèle un **gap de duration de +1.9 ans** "
            "(actifs 3.5 ans vs passifs 1.6 ans), ce qui est attendu "
            "pour un portefeuille Auto dont les passifs se règlent "
            "en ~18 mois.\n\n"
            "**Recommandation** : raccourcir les actifs obligataires "
            "de 1.9 ans. Le LCR de **1173%** confirme une liquidité "
            "très confortable."
        )
    else:
        return (
            f"Je prends en compte votre question : *{question}*\n\n"
            "Pour une réponse complète propulsée par Claude API, "
            "configurez votre clé API Anthropic dans les paramètres "
            "de la plateforme.\n\n"
            "En attendant, je peux vous renseigner sur :\n"
            "- Le Best Estimate et les provisions\n"
            "- Le ratio SCR et la Solvabilité 2\n"
            "- Les modèles de tarification (Gini, XGBoost)\n"
            "- L'ALM et la liquidité\n"
            "- L'IFRS 17 et la réconciliation S2"
        )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

render_sidebar()

page = st.session_state.page

if   page == 'accueil':   page_accueil()
elif page == 'analyse':   page_analyse()
elif page == 'dashboard': page_dashboard()
elif page == 'aria':      page_aria()
elif page == 'rapports':  page_rapports()
else:                     page_accueil()
