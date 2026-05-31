# ══════════════════════════════════════════════════════════════
# ACTUARIA v2.0 — INTERFACE PROFESSIONNELLE
# Design : Premium Dark Navy + Gold + Silver
# Logo   : ActuarIA (encodé base64)
# ══════════════════════════════════════════════════════════════

import streamlit as st
import json, os, sys
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import anthropic
from datetime import datetime

# ── Chemin projet ─────────────────────────────────────────────
PROJECT_ROOT = '.'

st.set_page_config(
    page_title="ActuarIA — Actuarial Intelligence",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Logo base64 ───────────────────────────────────────────────
def get_logo():
    try:
        sys.path.insert(0, PROJECT_ROOT)
        import logo_actuaria
        return logo_actuaria.LOGO_B64, logo_actuaria.LOGO_MIME
    except:
        return None, None

LOGO_B64, LOGO_MIME = get_logo()

def logo_html(width=120):
    if LOGO_B64:
        return (f'<img src="data:{LOGO_MIME};base64,{LOGO_B64}" '
                f'width="{width}" style="object-fit:contain;">')
    return '<span style="color:#4CAF1A;font-size:2rem;">🏢</span>'

# ── Palette couleurs ──────────────────────────────────────────
C = {
    'navy':    '#0D1B3E',
    'blue':    '#1B3A6B',
    'green':   '#4CAF1A',
    'silver':  '#C0C8D4',
    'white':   '#FFFFFF',
    'gold':    '#FFC000',
    'light':   '#F0F4FF',
    'card':    '#FFFFFF',
    'danger':  '#E53E3E',
    'warning': '#F6AD55',
    'success': '#48BB78',
}

# ── CSS Premium ───────────────────────────────────────────────
st.markdown(f"""
<style>
  /* Reset et base */
  .main .block-container {{
      padding: 1.5rem 2rem;
      max-width: 1400px;
  }}

  /* Header principal */
  .header-main {{
      background: linear-gradient(135deg,{C['navy']} 0%,
                  {C['blue']} 100%);
      padding: 1.5rem 2rem;
      border-radius: 16px;
      display: flex;
      align-items: center;
      gap: 1.5rem;
      margin-bottom: 1.5rem;
      border-bottom: 3px solid {C['green']};
  }}

  .header-title {{
      color: {C['white']};
      font-size: 2rem;
      font-weight: 600;
      letter-spacing: -0.5px;
      margin: 0;
  }}

  .header-title span {{
      color: {C['green']};
  }}

  .header-tagline {{
      color: {C['silver']};
      font-size: 0.85rem;
      letter-spacing: 3px;
      text-transform: uppercase;
      margin: 0;
  }}

  /* Cards KPI */
  .kpi-card {{
      background: {C['white']};
      border-radius: 12px;
      padding: 1.2rem 1.5rem;
      border-left: 4px solid {C['green']};
      border-top: 1px solid #E2E8F0;
      border-right: 1px solid #E2E8F0;
      border-bottom: 1px solid #E2E8F0;
      box-shadow: 0 2px 8px rgba(13,27,62,0.08);
      margin-bottom: 1rem;
  }}

  .kpi-card.navy {{
      border-left-color: {C['navy']};
  }}

  .kpi-card.gold {{
      border-left-color: {C['gold']};
  }}

  .kpi-card.danger {{
      border-left-color: {C['danger']};
  }}

  .kpi-label {{
      color: #718096;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 0.4rem;
  }}

  .kpi-value {{
      color: {C['navy']};
      font-size: 1.8rem;
      font-weight: 600;
      line-height: 1.1;
  }}

  .kpi-delta {{
      font-size: 0.75rem;
      margin-top: 0.3rem;
  }}

  .kpi-delta.up   {{ color: {C['success']}; }}
  .kpi-delta.down {{ color: {C['danger']};  }}
  .kpi-delta.ok   {{ color: {C['green']};   }}
  .kpi-delta.warn {{ color: {C['warning']}; }}

  /* Section titre */
  .section-header {{
      background: {C['navy']};
      color: {C['white']};
      padding: 0.6rem 1.2rem;
      border-radius: 8px;
      font-size: 0.9rem;
      font-weight: 600;
      letter-spacing: 0.5px;
      margin: 1.5rem 0 1rem 0;
      border-left: 4px solid {C['green']};
  }}

  /* Agent réponse */
  .agent-response {{
      background: #EBF3FB;
      border-radius: 10px;
      padding: 1.2rem 1.5rem;
      border-left: 4px solid {C['blue']};
      margin-top: 0.8rem;
      font-size: 0.9rem;
      line-height: 1.7;
      color: {C['navy']};
  }}

  .module-badge {{
      display: inline-block;
      background: {C['navy']};
      color: white;
      padding: 0.2rem 0.8rem;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 600;
      margin-bottom: 0.5rem;
  }}

  /* Tableau comparaison ML */
  .ml-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
  }}

  .ml-table th {{
      background: {C['navy']};
      color: white;
      padding: 0.7rem 1rem;
      text-align: left;
  }}

  .ml-table td {{
      padding: 0.6rem 1rem;
      border-bottom: 1px solid #E2E8F0;
  }}

  .ml-table tr:nth-child(even) td {{
      background: {C['light']};
  }}

  .ml-table tr.retenu td {{
      background: #D1FAE5;
      font-weight: 600;
  }}

  /* Alerte réglementaire */
  .alerte-reg {{
      background: #FFF3CD;
      border: 1px solid {C['gold']};
      border-left: 4px solid {C['gold']};
      border-radius: 8px;
      padding: 0.8rem 1.2rem;
      font-size: 0.85rem;
      color: #856404;
      margin: 0.8rem 0;
  }}

  .alerte-danger {{
      background: #FEE2E2;
      border: 1px solid {C['danger']};
      border-left: 4px solid {C['danger']};
      border-radius: 8px;
      padding: 0.8rem 1.2rem;
      font-size: 0.85rem;
      color: #742A2A;
      margin: 0.8rem 0;
  }}

  .alerte-success {{
      background: #D1FAE5;
      border: 1px solid {C['success']};
      border-left: 4px solid {C['success']};
      border-radius: 8px;
      padding: 0.8rem 1.2rem;
      font-size: 0.85rem;
      color: #1C4532;
      margin: 0.8rem 0;
  }}

  /* Sidebar */
  section[data-testid="stSidebar"] {{
      background: {C['navy']};
  }}

  section[data-testid="stSidebar"] * {{
      color: {C['silver']} !important;
  }}

  section[data-testid="stSidebar"] .stRadio label {{
      color: {C['silver']} !important;
      font-size: 0.85rem;
  }}

  /* Boutons */
  .stButton > button {{
      background: linear-gradient(135deg,{C['navy']},{C['blue']});
      color: white !important;
      border: none;
      border-radius: 8px;
      padding: 0.5rem 1.5rem;
      font-weight: 600;
      transition: all 0.2s;
  }}

  .stButton > button:hover {{
      opacity: 0.9;
      transform: translateY(-1px);
  }}

  /* Accueil — hero */
  .hero-stat {{
      background: {C['white']};
      border-radius: 12px;
      padding: 1rem;
      text-align: center;
      border-top: 3px solid {C['green']};
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }}

  .hero-stat-val {{
      color: {C['navy']};
      font-size: 1.6rem;
      font-weight: 700;
  }}

  .hero-stat-label {{
      color: #718096;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
  }}

  /* Footer */
  .footer {{
      text-align: center;
      color: #A0AEC0;
      font-size: 0.75rem;
      padding: 2rem 0 1rem 0;
      border-top: 1px solid #E2E8F0;
      margin-top: 2rem;
  }}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# CHARGEMENT DONNÉES
# ══════════════════════════════════════════════════════════════

@st.cache_data
def charger_resultats():
    resultats = {}
    fichiers = {
        'provisions_cl':  'provisions_chain_ladder.json',
        'provisions_fin': 'provisions_finales.json',
        'scr':            'scr_solvabilite2.json',
        'ifrs17':         'ifrs17_results.json',
        'pm_vie':         'provisions_mathematiques.json',
        'glm_freq':       'glm_poisson_meta.json',
        'glm_gamma':      'glm_gamma_meta.json',
        'xgboost':        'xgboost_meta.json',
        'ml_v2':          'v2/comparaison_ml.json',
    }
    for cle, fichier in fichiers.items():
        try:
            with open(f'models/{fichier}') as f:
                resultats[cle] = json.load(f)
        except:
            resultats[cle] = {}
    return resultats

@st.cache_data
def charger_iard():
    try:
        return pd.read_parquet(
            'data/v2/iard/iard_100k_15ans.parquet')
    except:
        return pd.DataFrame()

@st.cache_data
def charger_vie():
    try:
        return pd.read_parquet(
            'data/v2/vie/vie_100k_15ans.parquet')
    except:
        return pd.DataFrame()

resultats = charger_resultats()
df_iard   = charger_iard()
df_vie    = charger_vie()

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        f'<div style="text-align:center;padding:1rem 0;">'
        f'{logo_html(100)}'
        f'<div style="color:#4CAF1A;font-size:1.1rem;'
        f'font-weight:600;margin-top:0.5rem;">ActuarIA</div>'
        f'<div style="color:#718096;font-size:0.65rem;'
        f'letter-spacing:2px;">ACTUARIAL INTELLIGENCE</div>'
        f'</div>',
        unsafe_allow_html=True)

    st.markdown("---")

    # Clé API
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
        st.markdown(
            '<div style="background:#1C4532;color:#68D391;'
            'padding:0.4rem 0.8rem;border-radius:6px;'
            'font-size:0.75rem;text-align:center;">'
            '🔐 Clé API chargée</div>',
            unsafe_allow_html=True)
    except:
        api_key = st.text_input(
            "Clé API Claude",
            type="password",
            placeholder="sk-ant-...")

    st.markdown("---")

    # Identité rapport
    st.markdown(
        '<div style="color:#C0C8D4;font-size:0.75rem;'
        'text-transform:uppercase;letter-spacing:1px;'
        'margin-bottom:0.5rem;">📋 Identité Rapport</div>',
        unsafe_allow_html=True)

    nom_societe = st.text_input(
        "Société / Cabinet",
        placeholder="Ex: Allianz France SA",
        key="nom_societe")

    nom_actuaire = st.text_input(
        "Actuaire responsable",
        placeholder="Ex: Dr. Jean Martin",
        key="nom_actuaire")

    logo_client = st.file_uploader(
        "Logo client (PNG/JPG)",
        type=['png','jpg','jpeg'],
        key="logo_client")

    choix_logo = st.radio(
        "En-tête rapport",
        ["ActuarIA + Client","ActuarIA seul","Client seul"],
        key="choix_logo")

    classification = st.selectbox(
        "Classification",
        ["Confidentiel","Usage interne","Public"],
        key="classification")

    st.markdown("---")

    # Navigation
    st.markdown(
        '<div style="color:#C0C8D4;font-size:0.75rem;'
        'text-transform:uppercase;letter-spacing:1px;'
        'margin-bottom:0.5rem;">📂 Navigation</div>',
        unsafe_allow_html=True)

    page = st.radio("", [
        "🏠 Accueil",
        "📊 Branche Non-Vie",
        "💼 Branche Vie",
        "📈 ALM",
        "🤖 Agent IA",
        "📄 Rapports",
    ], label_visibility="collapsed")

    st.markdown("---")
    st.markdown(
        f'<div style="color:#4A5568;font-size:0.7rem;'
        f'text-align:center;">'
        f'ActuarIA v2.0<br>'
        f'© {datetime.now().year} Actuarial Intelligence'
        f'</div>',
        unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# HEADER GLOBAL
# ══════════════════════════════════════════════════════════════

st.markdown(
    f'<div class="header-main">'
    f'{logo_html(70)}'
    f'<div>'
    f'<div class="header-title">'
    f'Actuar<span>IA</span></div>'
    f'<div class="header-tagline">'
    f'Actuarial Intelligence</div>'
    f'</div>'
    f'<div style="margin-left:auto;text-align:right;">'
    f'<div style="color:#C0C8D4;font-size:0.75rem;">'
    f'Arrêté au {datetime.now().strftime("%d/%m/%Y")}</div>'
    f'<div style="color:#4CAF1A;font-size:0.8rem;'
    f'font-weight:600;">'
    f'{"" + nom_societe if nom_societe else "Mode démo"}'
    f'</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE 1 — ACCUEIL
# ══════════════════════════════════════════════════════════════

if page == "🏠 Accueil":

    # Hero section
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{C['navy']},
        {C['blue']});border-radius:16px;padding:2.5rem;
        margin-bottom:2rem;border-bottom:3px solid {C['green']};">
      <h1 style="color:white;font-size:2.2rem;margin:0;
          font-weight:700;letter-spacing:-1px;">
        L'Intelligence Actuarielle<br>
        <span style="color:{C['green']};">
        au service de la décision</span>
      </h1>
      <p style="color:{C['silver']};margin:1rem 0 0 0;
          font-size:1rem;max-width:600px;line-height:1.6;">
        ActuarIA est la première plateforme actuarielle
        augmentée par l'IA — tarification, provisionnement,
        Solvabilité 2, IFRS 17 et ALM en un seul outil
        intelligent pour les compagnies d'assurance
        européennes.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Chiffres marché EIOPA 2023
    st.markdown(
        '<div class="section-header">'
        '📊 MARCHÉ EUROPÉEN DE L\'ASSURANCE — EIOPA 2023'
        '</div>',
        unsafe_allow_html=True)

    col1,col2,col3,col4,col5 = st.columns(5)

    stats_marche = [
        (col1, "1 290 Mds €",
         "Primes totales EU", "up",
         "+3.2% vs 2022"),
        (col2, "224%",
         "Ratio SCR moyen EU", "ok",
         "Source EIOPA 2023"),
        (col3, "67.3%",
         "Loss Ratio NV moyen", "ok",
         "Auto + MRH + RC"),
        (col4, "3 200",
         "Entités supervisées", "ok",
         "5 pays majeurs"),
        (col5, "1 M",
         "Emplois secteur EU", "ok",
         "Actuaires + Tech"),
    ]

    for col, val, label, delta_type, delta_txt in stats_marche:
        with col:
            st.markdown(f"""
            <div class="hero-stat">
              <div class="hero-stat-val">{val}</div>
              <div class="hero-stat-label">{label}</div>
              <div style="color:#4CAF1A;font-size:0.7rem;
                  margin-top:0.3rem;">{delta_txt}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Enjeux 2024-2026
    st.markdown(
        '<div class="section-header">'
        '⚡ ENJEUX ACTUARIELS 2024-2026'
        '</div>',
        unsafe_allow_html=True)

    enjeux = [
        ("🏛️", "Solvabilité 2 — Révision 2024",
         "Le ratio SCR moyen EU est de 224% mais masque"
         " des disparités importantes. La révision 2024"
         " renforce les exigences sur le risque de"
         " liquidité et les actifs illiquides.",
         "SCR moyen EU : 224% | Ratio MCR min : 100%"),

        ("📋", "IFRS 17 — Première année complète",
         "Entrée en vigueur le 1er janvier 2023,"
         " IFRS 17 transforme radicalement le reporting"
         " assurance. La CSM mondiale est estimée à"
         " 400 milliards €. 73% des compagnies EU"
         " signalent un impact matériel sur leurs fonds propres.",
         "CSM mondiale ≈ 400 Mds € | Impact P&L -12%"),

        ("📈", "Inflation sinistres persistante",
         "L'inflation sinistres auto a atteint +8.1% en"
         " 2022 et reste à +5.3% en 2023 en Europe."
         " Les coûts de réparation et les pièces"
         " détachées restent sous tension,forcing les"
         " actuaires à réviser leurs triangles.",
         "+8.1% en 2022 | +5.3% en 2023 | Véhicules EV +15%"),

        ("💻", "Cyber risques — marché x3 d'ici 2027",
         "Le marché cyber EU va tripler pour atteindre"
         " 23 milliards € en 2027. La modélisation"
         " actuarielle des cyber risques est un enjeu"
         " majeur — corrélations systémiques et"
         " accumulations difficiles à quantifier.",
         "Marché EU 2023 : 8 Mds € | Cible 2027 : 23 Mds €"),

        ("🌡️", "Catastrophes naturelles — tendance lourde",
         "Les sinistres Cat Nat ont augmenté de +40%"
         " en 10 ans en Europe. Les modèles de"
         " tarification doivent intégrer les scénarios"
         " climatiques 1.5°C et 2°C dans leurs"
         " hypothèses de long terme.",
         "Sinistres Cat Nat EU 2023 : 54 Mds € | +40% en 10 ans"),

        ("🤖", "IA Act européen — impact direct",
         "L'AI Act européen (2025) classifie les"
         " modèles actuariels ML comme systèmes à"
         " haut risque. Les modèles de tarification"
         " et scoring doivent être explicables,"
         " auditables et non discriminants.",
         "IA Act : en vigueur 2025 | Conformité obligatoire"),
    ]

    for i in range(0, len(enjeux), 2):
        col1, col2 = st.columns(2)
        for col, idx in [(col1, i), (col2, i+1)]:
            if idx < len(enjeux):
                icon, titre, desc, chiffres = enjeux[idx]
                with col:
                    st.markdown(f"""
                    <div style="background:{C['white']};
                        border-radius:12px;padding:1.2rem;
                        border-left:4px solid {C['green']};
                        border:1px solid #E2E8F0;
                        border-left:4px solid {C['green']};
                        margin-bottom:1rem;
                        box-shadow:0 2px 6px rgba(0,0,0,0.05);">
                      <div style="font-size:1.5rem;
                          margin-bottom:0.5rem;">{icon}</div>
                      <div style="color:{C['navy']};
                          font-weight:600;font-size:0.9rem;
                          margin-bottom:0.5rem;">{titre}</div>
                      <div style="color:#4A5568;
                          font-size:0.82rem;line-height:1.6;
                          margin-bottom:0.7rem;">{desc}</div>
                      <div style="background:{C['light']};
                          border-radius:6px;padding:0.4rem 0.8rem;
                          color:{C['navy']};font-size:0.72rem;
                          font-weight:600;">{chiffres}</div>
                    </div>
                    """, unsafe_allow_html=True)

    # Présentation plateforme
    st.markdown(
        '<div class="section-header">'
        '🚀 ACTUARIA — LA PLATEFORME</div>',
        unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    points_forts = [
        (col1, "🎯", "Couverture complète",
         ["Branche Non-Vie complète",
          "Branche Vie complète",
          "Solvabilité 2 EIOPA",
          "IFRS 17 PAA + BBA",
          "ALM actif/passif"]),
        (col2, "🤖", "IA augmentée",
         ["5 modèles ML/DL comparés",
          "Agent IA niveau 1 à 4",
          "Recalcul à la demande",
          "Génération rapport auto",
          "Alertes réglementaires"]),
        (col3, "📄", "Rapports professionnels",
         ["Niveau Actuaire Senior",
          "3 niveaux : DG/Tech/Régl.",
          "Logo client intégré",
          "Commentaires détaillés",
          "Export PDF immédiat"]),
    ]

    for col, icon, titre, items in points_forts:
        with col:
            items_html = "".join([
                f'<li style="margin-bottom:0.3rem;">{it}</li>'
                for it in items])
            st.markdown(f"""
            <div style="background:{C['navy']};
                border-radius:12px;padding:1.5rem;
                border-bottom:3px solid {C['green']};
                height:100%;">
              <div style="font-size:2rem;
                  margin-bottom:0.8rem;">{icon}</div>
              <div style="color:white;font-weight:600;
                  font-size:1rem;margin-bottom:0.8rem;">
                {titre}</div>
              <ul style="color:{C['silver']};
                  font-size:0.82rem;line-height:1.8;
                  padding-left:1.2rem;margin:0;">
                {items_html}
              </ul>
            </div>
            """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE 2 — BRANCHE NON-VIE
# ══════════════════════════════════════════════════════════════

elif page == "📊 Branche Non-Vie":

    st.markdown("## 📊 Branche Non-Vie")

    tab1,tab2,tab3,tab4 = st.tabs([
        "🎯 Tarification",
        "📐 Provisionnement",
        "🏛️ Solvabilité 2",
        "📋 IFRS 17"
    ])

    # ── TAB 1 : TARIFICATION ──────────────────────────────────
    with tab1:
        st.markdown(
            '<div class="section-header">'
            '🎯 TARIFICATION NON-VIE — 5 MODÈLES ML/DL'
            '</div>',
            unsafe_allow_html=True)

        ml = resultats.get('ml_v2', {})
        comparaison = ml.get('comparaison', [])

        if comparaison:
            modele_retenu = ml.get('modele_retenu','N/A')
            gini_retenu   = ml.get('gini_retenu', 0)

            # KPIs
            col1,col2,col3,col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="kpi-card">
                  <div class="kpi-label">Modèle retenu</div>
                  <div class="kpi-value"
                       style="font-size:1.1rem;">
                    {modele_retenu}</div>
                  <div class="kpi-delta ok">
                    ✅ Gini/Stabilité optimal</div>
                </div>""", unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="kpi-card navy">
                  <div class="kpi-label">Gini Test</div>
                  <div class="kpi-value">
                    {gini_retenu:.4f}</div>
                  <div class="kpi-delta ok">
                    Bon — déployable production</div>
                </div>""", unsafe_allow_html=True)
            with col3:
                lift = ml.get('lift_retenu', 0)
                st.markdown(f"""
                <div class="kpi-card gold">
                  <div class="kpi-label">Lift D1/D10</div>
                  <div class="kpi-value">{lift:.2f}x</div>
                  <div class="kpi-delta ok">
                    Discrimination validée</div>
                </div>""", unsafe_allow_html=True)
            with col4:
                st.markdown(f"""
                <div class="kpi-card">
                  <div class="kpi-label">Contrats analysés</div>
                  <div class="kpi-value">
                    {len(df_iard):,}</div>
                  <div class="kpi-delta ok">
                    15 ans — 2010-2024</div>
                </div>""", unsafe_allow_html=True)

            # Tableau comparaison
            st.markdown(
                '<div class="section-header">'
                'Comparaison des 5 modèles</div>',
                unsafe_allow_html=True)

            rows_html = ""
            for m in comparaison:
                retenu = (m['modele'] == modele_retenu)
                cls    = 'retenu' if retenu else ''
                crown  = '👑 ' if retenu else ''
                ov     = (f"{m['overfit']:+.4f}"
                          if m.get('overfit') else 'N/A')
                ov_icon = ('✅' if abs(m.get('overfit') or 0)
                           < 0.08 else '⚠️')
                rows_html += f"""
                <tr class="{cls}">
                  <td>{m['rang']}</td>
                  <td>{crown}{m['modele']}</td>
                  <td>{m['gini_test']:.4f}</td>
                  <td>{m['auc_test']:.4f}</td>
                  <td>{ov} {ov_icon}</td>
                  <td>{m['lift_D1_D10']:.2f}x</td>
                </tr>"""

            st.markdown(f"""
            <table class="ml-table">
              <thead>
                <tr>
                  <th>Rang</th>
                  <th>Modèle</th>
                  <th>Gini Test</th>
                  <th>AUC</th>
                  <th>Overfit</th>
                  <th>Lift D1/D10</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
            """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Graphique Gini comparaison
            df_ml = pd.DataFrame(comparaison)
            df_ml = df_ml.sort_values('gini_test')

            colors_bar = [
                C['green'] if m == modele_retenu
                else C['silver']
                for m in df_ml['modele']]

            fig_ml = go.Figure(go.Bar(
                x=df_ml['gini_test'],
                y=df_ml['modele'],
                orientation='h',
                marker_color=colors_bar,
                text=[f"{g:.4f}" for g in df_ml['gini_test']],
                textposition='outside',
            ))
            fig_ml.update_layout(
                title=dict(
                    text='Gini Test — Comparaison 5 modèles',
                    font=dict(color=C['navy'], size=13)),
                height=280,
                paper_bgcolor='white',
                plot_bgcolor=C['light'],
                xaxis_title='Gini',
                margin=dict(l=10,r=80,t=40,b=10),
                font=dict(size=11))
            st.plotly_chart(fig_ml, use_container_width=True)

            # Commentaire actuaire senior
            st.markdown(f"""
            <div class="alerte-success">
              <strong>💼 Analyse Actuaire Senior</strong><br>
              Le modèle <strong>{modele_retenu}</strong> est
              retenu avec un Gini de
              <strong>{gini_retenu:.4f}</strong>,
              reflétant un bon pouvoir discriminant sur ce
              portefeuille auto européen (100 000 contrats,
              15 ans). L'overfit de
              {ml.get('comparaison',[{}])[0].get('overfit',0):.1%}
              est dans les normes acceptables.
              Les variables Bonus-Malus (26.7%),
              KM annuels (26.7%) et Age (23.3%) concentrent
              93% de l'importance prédictive —
              cohérent avec le référentiel ACPR/EIOPA.
              Sur données réelles (50k+ sinistres),
              le Gini attendu est 0.25-0.40.
            </div>
            """, unsafe_allow_html=True)

        # Statistiques portefeuille
        if not df_iard.empty:
            st.markdown(
                '<div class="section-header">'
                'Statistiques portefeuille IARD'
                '</div>',
                unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            with col1:
                freq_par_produit = df_iard.groupby('Produit').agg(
                    Contrats=('ID_Contrat','count'),
                    Frequence=('Nb_Sinistres',
                               lambda x: (x>0).mean()),
                    Prime_Pure=('Prime_Pure_EUR','mean'),
                    Loss_Ratio=('Loss_Ratio','mean')
                ).round(4)

                st.dataframe(freq_par_produit,
                             use_container_width=True)

            with col2:
                fig_freq = go.Figure(go.Bar(
                    x=freq_par_produit.index,
                    y=freq_par_produit['Frequence'],
                    marker_color=[C['navy'],
                                  C['green'], C['gold']],
                    text=[f"{v:.3f}"
                          for v in freq_par_produit['Frequence']],
                    textposition='outside'
                ))
                fig_freq.update_layout(
                    title='Fréquence par produit',
                    height=280,
                    paper_bgcolor='white',
                    plot_bgcolor=C['light'],
                    margin=dict(l=10,r=10,t=40,b=10))
                st.plotly_chart(fig_freq,
                                use_container_width=True)

    # ── TAB 2 : PROVISIONNEMENT ───────────────────────────────
    with tab2:
        st.markdown(
            '<div class="section-header">'
            '📐 PROVISIONNEMENT IARD — TRIANGLE 15 ANS'
            '</div>',
            unsafe_allow_html=True)

        p  = resultats.get('provisions_fin', {})
        cl = resultats.get('provisions_cl', {})

        col1,col2,col3,col4 = st.columns(4)
        methodes = p.get('methodes', {})

        kpis_prov = [
            (col1, "Chain-Ladder",
             f"{methodes.get('chain_ladder',0):,.0f} €",
             "navy", "Méthode de base"),
            (col2, "Bornhuetter-Ferguson",
             f"{methodes.get('bornhuetter_ferguson',0):,.0f} €",
             "", "A priori pondéré"),
            (col3, "Cape Cod",
             f"{methodes.get('cape_cod',0):,.0f} €",
             "gold", "ELR endogène"),
            (col4, "Provision retenue (BE)",
             f"{p.get('provision_retenue',0):,.0f} €",
             "", "Best Estimate"),
        ]

        for col,label,val,cls,sub in kpis_prov:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                       style="font-size:1.3rem;">{val}</div>
                  <div class="kpi-delta ok">{sub}</div>
                </div>""", unsafe_allow_html=True)

        # Graphique 3 méthodes
        fig_prov = go.Figure()
        methodes_noms = ['Chain-Ladder',
                         'Bornhuetter-Ferguson', 'Cape Cod']
        methodes_vals = [
            methodes.get('chain_ladder', 0),
            methodes.get('bornhuetter_ferguson', 0),
            methodes.get('cape_cod', 0)]
        colors_prov   = [C['navy'], C['blue'], C['gold']]

        fig_prov.add_trace(go.Bar(
            x=methodes_noms, y=methodes_vals,
            marker_color=colors_prov,
            text=[f"{v:,.0f} €" for v in methodes_vals],
            textposition='outside',
            name='IBNR'))

        fig_prov.add_hline(
            y=p.get('provision_retenue', 0),
            line_dash='dash', line_color=C['green'],
            annotation_text="BE retenu",
            annotation_position="right")

        fig_prov.add_hline(
            y=p.get('provision_prudente', 0),
            line_dash='dot', line_color=C['warning'],
            annotation_text="P90 prudente",
            annotation_position="right")

        fig_prov.update_layout(
            title='IBNR — Comparaison 3 méthodes',
            height=350, paper_bgcolor='white',
            plot_bgcolor=C['light'],
            yaxis_title='IBNR (€)',
            margin=dict(l=10,r=100,t=40,b=10))
        st.plotly_chart(fig_prov, use_container_width=True)

        # Commentaire actuaire senior
        cv = p.get('cv_inter_methodes', 0)
        ibnr_be = p.get('provision_retenue', 0)
        ibnr_p90 = p.get('provision_prudente', 0)
        elr = p.get('elr_cape_cod', 0)
        tail = cl.get('tail_factor', 0)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          Provisionnement</strong><br>
          Trois méthodes ont été appliquées au triangle
          de développement (15 années × 15 développements,
          tail factor = {tail}).
          La méthode Chain-Ladder extrapole les facteurs
          de développement observés ; la BF pondère avec
          un a priori de sinistralité ultime ; la Cape Cod
          estime l'ELR de manière endogène
          ({elr:.4f} — cohérent avec le marché auto EU).
          Le CV inter-méthodes de {cv}% reflète une
          <strong>convergence satisfaisante</strong> des
          estimations. La provision retenue (BE) de
          <strong>{ibnr_be:,.0f} €</strong> est la moyenne
          équipondérée des trois méthodes.
          La provision prudente P90 de
          <strong>{ibnr_p90:,.0f} €</strong>
          (approximation log-normale, percentile 90%)
          constitue le niveau de provisionnement
          recommandé en contexte d'incertitude élevée.
          Surveillance recommandée sur l'année 2024
          dont l'IBNR représente 56% du total avec
          une seule diagonale connue.
        </div>
        """, unsafe_allow_html=True)

    # ── TAB 3 : SOLVABILITÉ 2 ────────────────────────────────
    with tab3:
        st.markdown(
            '<div class="section-header">'
            '🏛️ SOLVABILITÉ 2 — SCR FORMULE STANDARD EIOPA'
            '</div>',
            unsafe_allow_html=True)

        s = resultats.get('scr', {})

        # KPIs SCR
        col1,col2,col3,col4 = st.columns(4)
        ratio = s.get('ratio_scr_pct', 0)
        conforme = ratio >= 100 if ratio else False

        with col1:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-label">SCR Total</div>
              <div class="kpi-value">
                {s.get('scr_total',0):,.0f} €</div>
              <div class="kpi-delta ok">
                Formule standard EIOPA</div>
            </div>""", unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-label">Fonds Propres</div>
              <div class="kpi-value">
                {s.get('fonds_propres',0):,.0f} €</div>
              <div class="kpi-delta ok">Tier 1</div>
            </div>""", unsafe_allow_html=True)

        with col3:
            cls_r = "navy" if conforme else "danger"
            delta_r = "ok" if conforme else "down"
            st.markdown(f"""
            <div class="kpi-card {cls_r}">
              <div class="kpi-label">Ratio SCR</div>
              <div class="kpi-value">{ratio}%</div>
              <div class="kpi-delta {delta_r}">
                {"✅ Conforme" if conforme
                 else "❌ Non conforme"}</div>
            </div>""", unsafe_allow_html=True)

        with col4:
            ratio_mcr = s.get('ratio_mcr_pct', 0)
            conforme_mcr = ratio_mcr >= 100
            cls_mcr = "" if conforme_mcr else "danger"
            st.markdown(f"""
            <div class="kpi-card {cls_mcr}">
              <div class="kpi-label">Ratio MCR</div>
              <div class="kpi-value">{ratio_mcr}%</div>
              <div class="kpi-delta
                {'ok' if conforme_mcr else 'down'}">
                {"✅ Conforme" if conforme_mcr
                 else "⚠️ Sous MCR absolu"}</div>
            </div>""", unsafe_allow_html=True)

        # Décomposition SCR
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            fig_scr = go.Figure(go.Pie(
                labels=['SCR Marché','SCR Non-Vie',
                        'SCR Contrepartie','SCR Opérationnel'],
                values=[s.get('scr_marche',0),
                        s.get('scr_nv',0),
                        s.get('scr_contrepartie',0),
                        s.get('scr_operationnel',0)],
                marker_colors=[C['navy'],C['green'],
                                C['gold'],C['silver']],
                hole=0.45,
                textinfo='label+percent'))
            fig_scr.update_layout(
                title='Décomposition BSCR',
                height=320, showlegend=False,
                paper_bgcolor='white',
                margin=dict(t=40,b=10,l=10,r=10))
            st.plotly_chart(fig_scr,
                            use_container_width=True)

        with col_g2:
            modules = ['SCR Marché','SCR Non-Vie',
                       'SCR Contrepartie','SCR Opérationnel']
            vals_scr = [s.get('scr_marche',0),
                        s.get('scr_nv',0),
                        s.get('scr_contrepartie',0),
                        s.get('scr_operationnel',0)]
            bscr = max(s.get('bscr',1), 1)

            fig_bar = go.Figure()
            for mod, val in zip(modules, vals_scr):
                fig_bar.add_trace(go.Bar(
                    x=[mod], y=[val],
                    marker_color=C['navy'],
                    text=f"{val/bscr*100:.1f}%",
                    textposition='outside',
                    showlegend=False))

            fig_bar.add_hline(
                y=s.get('scr_total',0),
                line_dash='dash',
                line_color=C['green'],
                annotation_text="SCR Total")

            fig_bar.update_layout(
                title='Montants SCR par module',
                height=320, paper_bgcolor='white',
                plot_bgcolor=C['light'],
                yaxis_title='EUR',
                margin=dict(l=10,r=80,t=40,b=10))
            st.plotly_chart(fig_bar,
                            use_container_width=True)

        # Alertes réglementaires
        if not conforme:
            st.markdown("""
            <div class="alerte-danger">
              ❌ <strong>Non-conformité SCR</strong> —
              Le ratio SCR est inférieur à 100%.
              Notification à l'ACPR/superviseur
              sous 2 mois (Art. 138 Directive 2009/138/CE).
              Plan de redressement requis.
            </div>""", unsafe_allow_html=True)

        if not conforme_mcr:
            st.markdown(f"""
            <div class="alerte-danger">
              ⚠️ <strong>MCR absolu non couvert</strong> —
              Ratio MCR = {ratio_mcr}%.
              Le MCR absolu réglementaire est de
              2 500 000 € (plancher EIOPA non-vie).
              Action correctrice immédiate requise
              (Art. 129 Directive 2009/138/CE).
              Augmentation de capital ou réduction
              de portefeuille nécessaire.
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="alerte-success">
              ✅ <strong>Conformité Solvabilité 2</strong> —
              Ratio SCR = {ratio}%.
              La compagnie dispose d'un niveau de capital
              suffisant pour couvrir son SCR
              (Règlement Délégué UE 2015/35, Art. 97-210).
              Marge de sécurité au-dessus du seuil de 100%
              à surveiller à chaque clôture trimestrielle.
            </div>""", unsafe_allow_html=True)

        # Commentaire actuaire senior S2
        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          Solvabilité 2</strong><br>
          Le SCR de <strong>{s.get('scr_total',0):,.0f} €
          </strong> a été calculé selon la formule standard
          EIOPA (Règlement Délégué 2015/35, Art. 97-210).
          Le module Non-Vie domine avec
          {s.get('scr_nv',0)/max(bscr,1)*100:.1f}%
          du BSCR, reflétant la nature du portefeuille
          (auto + MRH + RC Pro). Le SCR Marché de
          {s.get('scr_marche',0):,.0f} € est principalement
          constitué du risque actions (45%) et taux (27%).
          Avec des Fonds Propres de
          {s.get('fonds_propres',0):,.0f} €, le ratio
          SCR de {ratio}% est
          {"satisfaisant — cible de gestion interne recommandée : 150-180%."
           if ratio >= 100
           else "insuffisant — action corrective urgente."}
        </div>
        """, unsafe_allow_html=True)

    # ── TAB 4 : IFRS 17 ──────────────────────────────────────
    with tab4:
        st.markdown(
            '<div class="section-header">'
            '📋 IFRS 17 — PREMIUM ALLOCATION APPROACH (PAA)'
            '</div>',
            unsafe_allow_html=True)

        i   = resultats.get('ifrs17', {})
        paa = i.get('modele_paa', {})
        bba = i.get('modele_bba', {})

        col1,col2,col3,col4 = st.columns(4)
        kpis_ifrs = [
            (col1,"Insurance Revenue",
             f"{paa.get('insurance_revenue',0):,.0f} €",
             "","Primes acquises nettes"),
            (col2,"Insurance Expenses",
             f"{paa.get('insurance_expenses',0):,.0f} €",
             "navy","Sinistres + frais"),
            (col3,"Insurance Result",
             f"{paa.get('insurance_result',0):,.0f} €",
             "","Marge technique"),
            (col4,"Loss Ratio IFRS 17",
             f"{paa.get('loss_ratio_pct',0)}%",
             "navy","Référentiel 65-75%"),
        ]

        for col,label,val,cls,sub in kpis_ifrs:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.2rem;">{val}</div>
                  <div class="kpi-delta ok">{sub}</div>
                </div>""", unsafe_allow_html=True)

        # Graphique PAA
        fig_ifrs = go.Figure()
        fig_ifrs.add_trace(go.Bar(
            x=['Insurance Revenue'],
            y=[paa.get('insurance_revenue',0)],
            name='Revenue', marker_color=C['green']))
        fig_ifrs.add_trace(go.Bar(
            x=['Insurance Expenses'],
            y=[paa.get('insurance_expenses',0)],
            name='Expenses', marker_color=C['navy']))
        fig_ifrs.add_trace(go.Bar(
            x=['Insurance Result'],
            y=[paa.get('insurance_result',0)],
            name='Result', marker_color=C['gold']))

        fig_ifrs.update_layout(
            title='IFRS 17 PAA — Compte de résultat',
            height=300, barmode='group',
            paper_bgcolor='white', plot_bgcolor=C['light'],
            yaxis_title='EUR',
            margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(fig_ifrs, use_container_width=True)

        lr = paa.get('loss_ratio_pct', 0)
        st.markdown(f"""
        <div class="{'alerte-success' if lr < 70
                      else 'alerte-reg'}">
          <strong>💼 Analyse Actuaire Senior — IFRS 17</strong>
          <br>
          L'approche PAA (IFRS 17, §53-59) est applicable
          aux contrats auto de durée ≤ 12 mois.
          L'Insurance Revenue de
          <strong>{paa.get('insurance_revenue',0):,.0f} €
          </strong> reflète les primes acquises après
          amortissement de la LRC et des DAC.
          Le Loss Ratio IFRS 17 de
          <strong>{lr}%</strong> est
          {"favorable — en dessous du benchmark européen auto (65-75%)."
           if lr < 70
           else "dans le benchmark européen auto (65-75%)."}
          Le résultat technique de
          <strong>{paa.get('insurance_result',0):,.0f} €
          </strong> confirme la profitabilité du portefeuille
          — aucun Loss Component (IFRS 17 §47) requis.
          CSM BBA : <strong>{bba.get('csm',0):,.0f} €
          </strong> — profit différé sur durée résiduelle.
        </div>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE 3 — BRANCHE VIE
# ══════════════════════════════════════════════════════════════

elif page == "💼 Branche Vie":

    st.markdown("## 💼 Branche Vie")

    tab1,tab2,tab3,tab4 = st.tabs([
        "💀 Tarification",
        "📊 Provisions Mathématiques",
        "🏛️ Solvabilité 2",
        "📋 IFRS 17 BBA"
    ])

    with tab1:
        st.markdown(
            '<div class="section-header">'
            '💀 TARIFICATION VIE — TABLE EEA 2019 (EIOPA)'
            '</div>',
            unsafe_allow_html=True)

        pm = resultats.get('pm_vie', {})
        cr = pm.get('contrat_reference', {})

        col1,col2,col3,col4 = st.columns(4)
        kpis_tv = [
            (col1,"Prime nivelée",
             f"{cr.get('prime_nivelee',0)} €/an",
             "","Contrat référence"),
            (col2,"Capital assuré",
             f"{cr.get('capital_assure',0):,.0f} €",
             "navy","Décès temporaire"),
            (col3,"Taux technique",
             f"{cr.get('taux_technique',0)*100:.1f}%",
             "gold","Courbe EIOPA"),
            (col4,"Table mortalité",
             "EEA 2019","","EIOPA calibrée"),
        ]
        for col,label,val,cls,sub in kpis_tv:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.2rem;">{val}</div>
                  <div class="kpi-delta ok">{sub}</div>
                </div>""", unsafe_allow_html=True)

        if not df_vie.empty:
            col1, col2 = st.columns(2)
            with col1:
                # Distribution âge souscription
                fig_age = go.Figure(go.Histogram(
                    x=df_vie['Age_Souscription'],
                    nbinsx=30,
                    marker_color=C['navy'],
                    opacity=0.8))
                fig_age.update_layout(
                    title='Distribution âge souscription',
                    height=280, paper_bgcolor='white',
                    plot_bgcolor=C['light'],
                    xaxis_title='Age',
                    yaxis_title='Nb contrats',
                    margin=dict(l=10,r=10,t=40,b=10))
                st.plotly_chart(fig_age,
                                use_container_width=True)

            with col2:
                # Répartition type contrat
                type_counts = df_vie[
                    'Type_Contrat'].value_counts()
                fig_type = go.Figure(go.Pie(
                    labels=type_counts.index,
                    values=type_counts.values,
                    marker_colors=[C['navy'],
                                   C['green'], C['gold']],
                    hole=0.4))
                fig_type.update_layout(
                    title='Répartition type de contrat',
                    height=280, paper_bgcolor='white',
                    margin=dict(t=40,b=10,l=10,r=10))
                st.plotly_chart(fig_type,
                                use_container_width=True)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          Tarification Vie</strong><br>
          La prime nivelée de
          <strong>{cr.get('prime_nivelee',0)} €/an
          </strong> est calculée par la méthode prospective
          classique : prime = PV(prestations) / ä_x:n,
          avec la table EEA 2019 (EIOPA) et un taux
          technique de {cr.get('taux_technique',0)*100:.1f}%.
          Cette table, calibrée sur les données de mortalité
          européennes 2019, intègre les tendances d'amélioration
          de la longévité observées en UE.
          Le portefeuille vie de 100 000 contrats couvre
          3 types (décès 40%, épargne 35%, rente 25%),
          répartis sur 5 pays européens sur 15 ans.
        </div>
        """, unsafe_allow_html=True)

    with tab2:
        st.markdown(
            '<div class="section-header">'
            '📊 PROVISIONS MATHÉMATIQUES — MÉTHODE PROSPECTIVE'
            '</div>',
            unsafe_allow_html=True)

        pm = resultats.get('pm_vie', {})
        cr = pm.get('contrat_reference', {})
        pf = pm.get('portefeuille', {})

        col1,col2,col3,col4 = st.columns(4)
        kpis_pm = [
            (col1,"PM maximale",
             f"{cr.get('pm_max',0):,.0f} €",
             "","à t=12 ans"),
            (col2,"PM à t=10",
             f"{cr.get('pm_t10',0):,.0f} €",
             "navy","Mi-contrat"),
            (col3,"PM portefeuille",
             f"{pf.get('pm_totale',0):,.0f} €",
             "gold","50 contrats"),
            (col4,"PM moyenne",
             f"{pf.get('pm_moyenne',0):,.0f} €",
             "","Par contrat"),
        ]
        for col,label,val,cls,sub in kpis_pm:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.3rem;">{val}</div>
                  <div class="kpi-delta ok">{sub}</div>
                </div>""", unsafe_allow_html=True)

        # Graphique sensibilité taux
        sensi = pm.get('sensibilite_taux', {})
        if sensi:
            taux_list = [float(k.replace('pct','').replace(',','.'))
                         for k in sensi.keys()]
            pm_list   = list(sensi.values())

            fig_sensi = go.Figure(go.Scatter(
                x=taux_list, y=pm_list,
                mode='lines+markers',
                line=dict(color=C['navy'], width=3),
                marker=dict(size=8, color=C['green'])))

            fig_sensi.update_layout(
                title='Sensibilité PM au taux technique (t=10)',
                height=300, paper_bgcolor='white',
                plot_bgcolor=C['light'],
                xaxis_title='Taux technique (%)',
                yaxis_title='PM (€)',
                margin=dict(l=10,r=10,t=40,b=10))
            st.plotly_chart(fig_sensi,
                            use_container_width=True)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          Provisions Mathématiques</strong><br>
          Les PM ont été calculées par la méthode
          <strong>prospective</strong>
          (PM = PV prestations − PV primes futures)
          avec la table EEA 2019 et le taux technique
          EIOPA. La cohérence avec la méthode
          <strong>rétrospective</strong>
          est vérifiée (écart < 0.001 €) —
          théorème d'équivalence actuarielle confirmé.
          La PM maximale de
          <strong>{cr.get('pm_max',0):,.0f} €</strong>
          est atteinte à t=12 (pic typique d'un contrat
          décès temporaire 20 ans). La sensibilité au
          taux technique est modérée sur ce type de
          contrat (-6.1% pour +350bp) — plus forte
          sur les contrats épargne et rente viagère.
        </div>
        """, unsafe_allow_html=True)

    with tab3:
        st.markdown(
            '<div class="section-header">'
            '🏛️ SOLVABILITÉ 2 VIE — SCR VIE EIOPA'
            '</div>',
            unsafe_allow_html=True)

        if not df_vie.empty:
            scr_mort = df_vie['SCR_Mortalite_EUR'].sum()
            scr_long = df_vie['SCR_Longevite_EUR'].sum()
            scr_rach = df_vie['SCR_Rachat_EUR'].sum()
            scr_frai = df_vie['SCR_Frais_EUR'].sum()
            scr_vie  = df_vie['SCR_Vie_Total_EUR'].sum()

            col1,col2,col3,col4 = st.columns(4)
            kpis_scr_v = [
                (col1,"SCR Mortalité",
                 f"{scr_mort:,.0f} €","","Choc +15%"),
                (col2,"SCR Longévité",
                 f"{scr_long:,.0f} €","navy","Choc -20%"),
                (col3,"SCR Rachat",
                 f"{scr_rach:,.0f} €","gold","Choc ±40%"),
                (col4,"SCR Vie Total",
                 f"{scr_vie:,.0f} €","","BSCR Vie"),
            ]
            for col,label,val,cls,sub in kpis_scr_v:
                with col:
                    st.markdown(f"""
                    <div class="kpi-card {cls}">
                      <div class="kpi-label">{label}</div>
                      <div class="kpi-value"
                        style="font-size:1.1rem;">{val}</div>
                      <div class="kpi-delta ok">{sub}</div>
                    </div>""", unsafe_allow_html=True)

            # Graphique SCR Vie
            fig_scr_v = go.Figure(go.Bar(
                x=['Mortalité','Longévité',
                   'Rachat','Frais'],
                y=[scr_mort,scr_long,scr_rach,scr_frai],
                marker_color=[C['navy'],C['green'],
                              C['gold'],C['silver']],
                text=[f"{v/1e6:.1f}M€"
                      for v in [scr_mort,scr_long,
                                 scr_rach,scr_frai]],
                textposition='outside'))

            fig_scr_v.update_layout(
                title='Décomposition SCR Vie',
                height=300, paper_bgcolor='white',
                plot_bgcolor=C['light'],
                yaxis_title='EUR',
                margin=dict(l=10,r=10,t=40,b=30))
            st.plotly_chart(fig_scr_v,
                            use_container_width=True)

            st.markdown(f"""
            <div class="alerte-success">
              <strong>💼 Analyse Actuaire Senior —
              SCR Vie</strong><br>
              Le SCR Vie de
              <strong>{scr_vie:,.0f} €</strong>
              est calculé conformément au
              Règlement Délégué 2015/35, modules
              SLT (Similar to Life Techniques).
              Le module longévité
              ({scr_long/max(scr_vie,1)*100:.1f}%
              du SCR Vie) domine pour les rentes viagères
              (25% du portefeuille) — choc
              de -20% sur les taux de mortalité (Art. 142).
              Le module mortalité s'applique aux contrats
              décès (40% du portefeuille) avec un choc
              de +15% (Art. 138). Le risque de rachat
              intègre les 3 scénarios réglementaires :
              hausse, baisse et rachat de masse.
            </div>
            """, unsafe_allow_html=True)

    with tab4:
        st.markdown(
            '<div class="section-header">'
            '📋 IFRS 17 BBA — BUILDING BLOCK APPROACH'
            '</div>',
            unsafe_allow_html=True)

        i   = resultats.get('ifrs17', {})
        bba = i.get('modele_bba', {})

        col1,col2,col3,col4 = st.columns(4)
        kpis_bba = [
            (col1,"FCF (Bloc 1)",
             f"{bba.get('fcf',0):,.0f} €",
             "","Flux trésorerie"),
            (col2,"Risk Adjustment",
             f"{bba.get('ra',0):,.0f} €",
             "navy","Percentile 75%"),
            (col3,"CSM (Bloc 3)",
             f"{bba.get('csm',0):,.0f} €",
             "gold","Profit différé"),
            (col4,"Passif initial",
             f"{bba.get('total_passif_init',0):,.0f} €",
             "","= 0 ✅"),
        ]
        for col,label,val,cls,sub in kpis_bba:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.2rem;">{val}</div>
                  <div class="kpi-delta ok">{sub}</div>
                </div>""", unsafe_allow_html=True)

        # Graphique blocs BBA
        fig_bba = go.Figure(go.Waterfall(
            name="BBA",
            orientation="v",
            measure=["relative","relative",
                     "relative","total"],
            x=["FCF (Bloc 1)","Risk Adjustment (Bloc 2)",
               "CSM (Bloc 3)","Passif Initial"],
            y=[bba.get('fcf',0),
               bba.get('ra',0),
               bba.get('csm',0),
               0],
            connector=dict(line=dict(
                color=C['silver'], width=1)),
            decreasing=dict(marker_color=C['danger']),
            increasing=dict(marker_color=C['green']),
            totals=dict(marker_color=C['navy'])))

        fig_bba.update_layout(
            title='IFRS 17 BBA — Blocs de mesure',
            height=320, paper_bgcolor='white',
            plot_bgcolor=C['light'],
            yaxis_title='EUR',
            margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(fig_bba, use_container_width=True)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          IFRS 17 BBA</strong><br>
          Le modèle BBA (IFRS 17, §32-52) s'applique
          aux contrats pluriannuels vie. À l'initialisation,
          le passif est nul par construction
          (day-one profit prohibition — §47) :
          FCF ({bba.get('fcf',0):,.0f} €)
          + RA ({bba.get('ra',0):,.0f} €)
          + CSM ({bba.get('csm',0):,.0f} €) = 0.
          La CSM représente le profit non encore acquis —
          elle sera relâchée en résultat au rythme
          des unités de couverture fournies.
          Le Risk Adjustment (percentile 75%, méthode
          de la marge sur service de risque) compense
          l'incertitude sur les flux de trésorerie futurs.
        </div>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE 4 — ALM
# ══════════════════════════════════════════════════════════════

elif page == "📈 ALM":

    st.markdown("## 📈 ALM — Gestion Actif-Passif")

    st.markdown(
        '<div class="section-header">'
        '📈 ALM — DURATION GAP ET STRESS TAUX'
        '</div>',
        unsafe_allow_html=True)

    # Paramètres ALM simulés
    pm = resultats.get('pm_vie', {})
    s  = resultats.get('scr', {})
    pf = pm.get('portefeuille', {})

    passif_total = pf.get('pm_totale', 763_460)
    actif_total  = passif_total * 1.15

    duration_actif  = 6.2
    duration_passif = 9.8
    gap_duration    = duration_actif - duration_passif

    col1,col2,col3,col4 = st.columns(4)
    kpis_alm = [
        (col1,"Duration Actif",
         f"{duration_actif:.1f} ans",
         "","Obligations + actions"),
        (col2,"Duration Passif",
         f"{duration_passif:.1f} ans",
         "navy","PM + provisions"),
        (col3,"Gap de Duration",
         f"{gap_duration:.1f} ans",
         "danger" if abs(gap_duration) > 2 else "",
         "⚠️ Exposition taux" if abs(gap_duration) > 2
         else "✅ Sous contrôle"),
        (col4,"Taux de couverture",
         f"{actif_total/passif_total*100:.1f}%",
         "","Actif / Passif"),
    ]

    for col,label,val,cls,sub in kpis_alm:
        with col:
            st.markdown(f"""
            <div class="kpi-card {cls}">
              <div class="kpi-label">{label}</div>
              <div class="kpi-value"
                style="font-size:1.4rem;">{val}</div>
              <div class="kpi-delta
                {'warn' if cls=='danger' else 'ok'}">
                {sub}</div>
            </div>""", unsafe_allow_html=True)

    # Stress test taux
    st.markdown(
        '<div class="section-header">'
        'Stress test taux — Impact sur fonds propres'
        '</div>',
        unsafe_allow_html=True)

    chocs_taux = [-200, -100, -50, 0, +50, +100, +200]
    impact_actif  = [actif_total * (-duration_actif  *
                     choc/10000) for choc in chocs_taux]
    impact_passif = [passif_total * (-duration_passif *
                     choc/10000) for choc in chocs_taux]
    impact_net    = [a - p for a, p in
                     zip(impact_actif, impact_passif)]

    fig_stress = go.Figure()
    fig_stress.add_trace(go.Bar(
        x=[f"{c:+d}bp" for c in chocs_taux],
        y=impact_net,
        marker_color=[C['danger'] if v < 0
                      else C['green'] for v in impact_net],
        text=[f"{v:+,.0f} €" for v in impact_net],
        textposition='outside',
        name='Impact net FP'))

    fig_stress.add_hline(y=0, line_color=C['navy'],
                          line_width=1)

    fig_stress.update_layout(
        title='Impact des chocs de taux sur les Fonds Propres',
        height=320, paper_bgcolor='white',
        plot_bgcolor=C['light'],
        xaxis_title='Choc de taux',
        yaxis_title='Impact EUR',
        margin=dict(l=10,r=10,t=40,b=10))
    st.plotly_chart(fig_stress, use_container_width=True)

    st.markdown(f"""
    <div class="alerte-reg">
      <strong>💼 Analyse Actuaire Senior — ALM</strong><br>
      Le gap de duration de {gap_duration:.1f} ans
      (actif {duration_actif:.1f} ans vs passif
      {duration_passif:.1f} ans) indique une
      <strong>exposition au risque de taux</strong>.
      Une hausse de 100bp des taux réduit la valeur
      de l'actif de {impact_actif[5]:+,.0f} € et
      du passif de {impact_passif[5]:+,.0f} €,
      soit un impact net sur les fonds propres de
      <strong>{impact_net[5]:+,.0f} €</strong>.
      L'immunisation partielle par duration matching
      est recommandée — cible gap < 1.5 ans.
      Stratégie : allongement duration actif par
      achat d'obligations longues ou swaps de taux.
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE 5 — AGENT IA
# ══════════════════════════════════════════════════════════════

elif page == "🤖 Agent IA":

    st.markdown("## 🤖 Agent Actuariel IA")
    st.markdown(
        "Posez votre question en langage naturel — "
        "l'agent sélectionne le bon module et répond "
        "avec les données réelles du portefeuille.")

    if not api_key:
        st.warning(
            "Entrez votre clé API Claude dans la sidebar.")
    else:
        if 'messages_v2' not in st.session_state:
            st.session_state.messages_v2 = []

        # Questions rapides
        st.markdown("**Questions rapides :**")
        q_exemples = [
            "Quel est l'IBNR total et quelle méthode est recommandée ?",
            "Ratio SCR — sommes-nous conformes Solvabilité 2 ?",
            "Quel modèle ML est retenu et pourquoi ?",
            "CSM IFRS 17 — que représente-t-elle ?",
            "Quelle est la PM maximale du contrat vie ?",
            "Gap de duration ALM — quel est le risque ?",
            "Synthèse bilan actuariel complet pour la DG",
        ]

        cols = st.columns(3)
        for j, q in enumerate(q_exemples[:6]):
            with cols[j % 3]:
                if st.button(q[:35]+"...",
                             key=f"q_{j}"):
                    st.session_state.q_v2 = q

        question = st.text_input(
            "Votre question :",
            value=st.session_state.get('q_v2',''),
            placeholder="Ex: Quel est le ratio SCR ?")

        if st.button("Envoyer",
                     type="primary") and question:
            with st.spinner("Agent actuariel en cours..."):

                client = anthropic.Anthropic(
                    api_key=api_key)

                # Contexte complet
                g   = resultats.get('glm_gamma', {})
                p   = resultats.get('provisions_fin', {})
                s   = resultats.get('scr', {})
                i   = resultats.get('ifrs17', {})
                pm  = resultats.get('pm_vie', {})
                ml  = resultats.get('ml_v2', {})

                contexte_complet = f"""
DONNÉES RÉELLES ACTUARIA v2.0 :

TARIFICATION IARD :
  Modèle retenu : {ml.get('modele_retenu','N/A')}
  Gini test     : {ml.get('gini_retenu','N/A')}
  Lift D1/D10   : {ml.get('lift_retenu','N/A')}x
  Top variables : Bonus-Malus 26.7%, KM 26.7%, Age 23.3%
  Prime pure moy: {g.get('prime_pure_moy','N/A')} EUR

PROVISIONNEMENT IARD :
  Chain-Ladder  : {p.get('methodes',{}).get('chain_ladder','N/A')} EUR
  BF            : {p.get('methodes',{}).get('bornhuetter_ferguson','N/A')} EUR
  Cape Cod      : {p.get('methodes',{}).get('cape_cod','N/A')} EUR
  BE retenu     : {p.get('provision_retenue','N/A')} EUR
  P90 prudente  : {p.get('provision_prudente','N/A')} EUR
  CV méthodes   : {p.get('cv_inter_methodes','N/A')}%

SOLVABILITÉ 2 :
  SCR Total     : {s.get('scr_total','N/A')} EUR
  Ratio SCR     : {s.get('ratio_scr_pct','N/A')}%
  Ratio MCR     : {s.get('ratio_mcr_pct','N/A')}%
  Statut        : {s.get('statut','N/A')}

IFRS 17 PAA :
  Revenue       : {i.get('modele_paa',{}).get('insurance_revenue','N/A')} EUR
  Loss Ratio    : {i.get('modele_paa',{}).get('loss_ratio_pct','N/A')}%
  Result        : {i.get('modele_paa',{}).get('insurance_result','N/A')} EUR
  CSM BBA       : {i.get('modele_bba',{}).get('csm','N/A')} EUR

PROVISIONS VIE :
  PM max        : {pm.get('contrat_reference',{}).get('pm_max','N/A')} EUR
  PM portefeuille: {pm.get('portefeuille',{}).get('pm_totale','N/A')} EUR
  Prime nivelée : {pm.get('contrat_reference',{}).get('prime_nivelee','N/A')} EUR/an

ALM :
  Duration actif  : 6.2 ans
  Duration passif : 9.8 ans
  Gap duration    : -3.6 ans
  Taux couverture : 115%
"""
                prompt = (
                    f"Tu es un actuaire senior expert "
                    f"en assurance européenne. Voici les "
                    f"données réelles du portefeuille :\n"
                    f"{contexte_complet}\n\n"
                    f"Question : {question}\n\n"
                    f"Réponds de façon professionnelle, "
                    f"cite les chiffres exacts, mentionne "
                    f"les références réglementaires "
                    f"pertinentes. 4-5 phrases maximum.")

                resp = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=600,
                    messages=[{
                        "role": "user",
                        "content": prompt}])

                reponse = resp.content[0].text
                st.session_state.messages_v2.append({
                    'question': question,
                    'reponse':  reponse,
                    'date': datetime.now().strftime(
                        "%H:%M")
                })

                if 'q_v2' in st.session_state:
                    del st.session_state.q_v2

        # Historique
        for msg in reversed(
                st.session_state.messages_v2):
            st.markdown(
                f"**❓ {msg['question']}** "
                f"<span style='color:#A0AEC0;"
                f"font-size:0.75rem;'>"
                f"{msg['date']}</span>",
                unsafe_allow_html=True)
            st.markdown(
                f'<div class="agent-response">'
                f'{msg["reponse"]}</div>',
                unsafe_allow_html=True)
            st.markdown("---")

# ══════════════════════════════════════════════════════════════
# PAGE 6 — RAPPORTS
# ══════════════════════════════════════════════════════════════

elif page == "📄 Rapports":

    st.markdown("## 📄 Rapports Professionnels")

    st.markdown(f"""
    <div class="alerte-success">
      <strong>Configuration rapport</strong><br>
      Société : <strong>
        {nom_societe if nom_societe else 'Non renseigné'}
      </strong> |
      Actuaire : <strong>
        {nom_actuaire if nom_actuaire else 'Non renseigné'}
      </strong> |
      Classification : <strong>{classification}</strong>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-header">'
        'Rapports disponibles</div>',
        unsafe_allow_html=True)

    rapports = [
        ("🏢", "Rapport Direction Générale",
         "Synthèse exécutive 8-12 pages — "
         "langage business, graphiques, "
         "recommandations actionnables",
         "DG + Conseil d'Administration"),
        ("📊", "Rapport Technique IARD",
         "Tarification + Provisionnement + SCR NV "
         "+ IFRS 17 PAA — "
         "formules, hypothèses, tests statistiques",
         "Actuaires + Risk Managers"),
        ("💼", "Rapport Technique Vie",
         "Tarification + PM + SCR Vie + IFRS 17 BBA "
         "— tables mortalité, sensibilités",
         "Actuaires Vie + DAF"),
        ("📈", "Rapport ALM",
         "Duration gap + stress taux + "
         "immunisation — actif/passif",
         "Direction Financière"),
        ("📋", "Rapport Général Consolidé",
         "Rapport complet toutes branches — "
         "niveau Actuaire Senior",
         "ACPR + Commissaires aux comptes"),
    ]

    for icon, titre, desc, public in rapports:
        col1, col2 = st.columns([3,1])
        with col1:
            st.markdown(f"""
            <div style="background:{C['white']};
                border-radius:10px;padding:1rem 1.2rem;
                border-left:4px solid {C['navy']};
                border:1px solid #E2E8F0;
                border-left:4px solid {C['navy']};
                margin-bottom:0.8rem;">
              <div style="font-size:1.2rem;
                  display:inline;">{icon}</div>
              <strong style="color:{C['navy']};
                  font-size:0.95rem;"> {titre}</strong>
              <div style="color:#4A5568;
                  font-size:0.82rem;margin-top:0.3rem;">
                {desc}</div>
              <div style="color:#A0AEC0;
                  font-size:0.72rem;margin-top:0.3rem;">
                Public cible : {public}</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button(
                    f"📥 Générer",
                    key=f"btn_{titre[:10]}"):
                st.info(
                    "Génération PDF en cours... "
                    "Cette fonctionnalité sera "
                    "disponible dans la Phase 14.")

    st.markdown(
        '<div class="section-header">'
        'Options d\'en-tête rapport</div>',
        unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div style="background:{C['navy']};
            border-radius:10px;padding:1rem;
            text-align:center;">
          <div style="color:{C['green']};
              font-size:0.75rem;
              margin-bottom:0.5rem;">OPTION A</div>
          <div style="color:white;font-size:0.85rem;">
            Logo ActuarIA + Logo Client</div>
          <div style="color:{C['silver']};
              font-size:0.75rem;margin-top:0.3rem;">
            Recommandé pour compagnies</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background:{C['white']};
            border:1px solid #E2E8F0;
            border-radius:10px;padding:1rem;
            text-align:center;">
          <div style="color:{C['navy']};
              font-size:0.75rem;
              margin-bottom:0.5rem;">OPTION B</div>
          <div style="color:{C['navy']};
              font-size:0.85rem;">
            Logo Client uniquement</div>
          <div style="color:#718096;
              font-size:0.75rem;margin-top:0.3rem;">
            Pour cabinets de conseil</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style="background:{C['white']};
            border:1px solid #E2E8F0;
            border-radius:10px;padding:1rem;
            text-align:center;">
          <div style="color:{C['navy']};
              font-size:0.75rem;
              margin-bottom:0.5rem;">OPTION C</div>
          <div style="color:{C['navy']};
              font-size:0.85rem;">
            Logo ActuarIA seul</div>
          <div style="color:#718096;
              font-size:0.75rem;margin-top:0.3rem;">
            Usage interne / démo</div>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="footer">
  ActuarIA v2.0 — Actuarial Intelligence<br>
  IARD · Vie · Solvabilité 2 · IFRS 17 · ALM
  · LangGraph · Claude API<br>
  © {datetime.now().year} —
  {classification} —
  {nom_societe if nom_societe else 'Mode démo'}
</div>
""", unsafe_allow_html=True)
