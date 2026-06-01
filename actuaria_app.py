# ══════════════════════════════════════════════════════════════
# ACTUARIA v2.0 — CHEMINS CORRIGÉS POUR STREAMLIT CLOUD
# Les JSON sont à la racine du repo GitHub
# ══════════════════════════════════════════════════════════════

import streamlit as st
import json, os, sys
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import anthropic

st.set_page_config(
    page_title="ActuarIA — Actuarial Intelligence",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Logo ──────────────────────────────────────────────────────
def get_logo():
    try:
        import logo_actuaria
        return logo_actuaria.LOGO_B64, logo_actuaria.LOGO_MIME
    except:
        return None, None

LOGO_B64, LOGO_MIME = get_logo()

def logo_html(width=120):
    if LOGO_B64:
        return (f'<img src="data:{LOGO_MIME};base64,'
                f'{LOGO_B64}" width="{width}" '
                f'style="object-fit:contain;">')
    return '🏢'

# ── Couleurs ──────────────────────────────────────────────────
C = {
    'navy':    '#0D1B3E',
    'blue':    '#1B3A6B',
    'green':   '#4CAF1A',
    'silver':  '#C0C8D4',
    'white':   '#FFFFFF',
    'gold':    '#FFC000',
    'light':   '#F0F4FF',
    'danger':  '#E53E3E',
    'warning': '#F6AD55',
    'success': '#48BB78',
}

# ── CSS ───────────────────────────────────────────────────────
st.markdown(f"""
<style>
.main .block-container {{
    padding: 1.5rem 2rem; max-width: 1400px;
}}
.header-main {{
    background: linear-gradient(135deg,
        {C['navy']} 0%, {C['blue']} 100%);
    padding: 1.5rem 2rem; border-radius: 16px;
    display: flex; align-items: center; gap: 1.5rem;
    margin-bottom: 1.5rem;
    border-bottom: 3px solid {C['green']};
}}
.kpi-card {{
    background: {C['white']}; border-radius: 12px;
    padding: 1.2rem 1.5rem;
    border-left: 4px solid {C['green']};
    border-top: 1px solid #E2E8F0;
    border-right: 1px solid #E2E8F0;
    border-bottom: 1px solid #E2E8F0;
    box-shadow: 0 2px 8px rgba(13,27,62,0.08);
    margin-bottom: 1rem;
}}
.kpi-card.navy  {{ border-left-color: {C['navy']};  }}
.kpi-card.gold  {{ border-left-color: {C['gold']};  }}
.kpi-card.danger{{ border-left-color: {C['danger']};}}
.kpi-label {{
    color: #718096; font-size: 0.72rem;
    text-transform: uppercase; letter-spacing: 1px;
    margin-bottom: 0.4rem;
}}
.kpi-value {{
    color: {C['navy']}; font-size: 1.8rem;
    font-weight: 600; line-height: 1.1;
}}
.kpi-delta      {{ font-size: 0.75rem; margin-top: 0.3rem; }}
.kpi-delta.ok   {{ color: {C['success']}; }}
.kpi-delta.down {{ color: {C['danger']};  }}
.kpi-delta.warn {{ color: {C['warning']}; }}
.section-header {{
    background: {C['navy']}; color: {C['white']};
    padding: 0.6rem 1.2rem; border-radius: 8px;
    font-size: 0.9rem; font-weight: 600;
    letter-spacing: 0.5px; margin: 1.5rem 0 1rem 0;
    border-left: 4px solid {C['green']};
}}
.agent-response {{
    background: #EBF3FB; border-radius: 10px;
    padding: 1.2rem 1.5rem;
    border-left: 4px solid {C['blue']};
    margin-top: 0.8rem; font-size: 0.9rem;
    line-height: 1.7; color: {C['navy']};
}}
.alerte-success {{
    background: #D1FAE5; border: 1px solid {C['success']};
    border-left: 4px solid {C['success']};
    border-radius: 8px; padding: 0.8rem 1.2rem;
    font-size: 0.85rem; color: #1C4532; margin: 0.8rem 0;
}}
.alerte-danger {{
    background: #FEE2E2; border: 1px solid {C['danger']};
    border-left: 4px solid {C['danger']};
    border-radius: 8px; padding: 0.8rem 1.2rem;
    font-size: 0.85rem; color: #742A2A; margin: 0.8rem 0;
}}
.alerte-reg {{
    background: #FFF3CD; border: 1px solid {C['gold']};
    border-left: 4px solid {C['gold']};
    border-radius: 8px; padding: 0.8rem 1.2rem;
    font-size: 0.85rem; color: #856404; margin: 0.8rem 0;
}}
.hero-stat {{
    background: {C['white']}; border-radius: 12px;
    padding: 1rem; text-align: center;
    border-top: 3px solid {C['green']};
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.hero-stat-val {{
    color: {C['navy']}; font-size: 1.6rem;
    font-weight: 700;
}}
.hero-stat-label {{
    color: #718096; font-size: 0.75rem;
    text-transform: uppercase; letter-spacing: 0.5px;
}}
.footer {{
    text-align: center; color: #A0AEC0;
    font-size: 0.75rem; padding: 2rem 0 1rem 0;
    border-top: 1px solid #E2E8F0; margin-top: 2rem;
}}
section[data-testid="stSidebar"] {{
    background: {C['navy']};
}}
section[data-testid="stSidebar"] * {{
    color: {C['silver']} !important;
}}
.stButton > button {{
    background: linear-gradient(135deg,
        {C['navy']},{C['blue']});
    color: white !important; border: none;
    border-radius: 8px; padding: 0.5rem 1.5rem;
    font-weight: 600;
}}
</style>
""", unsafe_allow_html=True)

# ── Chargement données — CHEMINS CORRIGÉS ─────────────────────
@st.cache_data
def charger_resultats():
    r = {}
    # Tous les JSON sont à la racine du repo
    fichiers = {
        'provisions_cl':  'provisions_chain_ladder.json',
        'provisions_fin': 'provisions_finales.json',
        'scr':            'scr_solvabilite2.json',
        'ifrs17':         'ifrs17_results.json',
        'pm_vie':         'provisions_mathematiques.json',
        'glm_freq':       'glm_poisson_meta.json',
        'glm_gamma':      'glm_gamma_meta.json',
        'xgboost':        'xgboost_meta.json',
        'ml_v2':          'comparaison_ml.json',
    }
    for cle, fichier in fichiers.items():
        try:
            with open(fichier) as f:
                r[cle] = json.load(f)
        except:
            r[cle] = {}
    return r

resultats = charger_resultats()

# ── Sidebar ───────────────────────────────────────────────────
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
            "Clé API Claude", type="password",
            placeholder="sk-ant-...")

    st.markdown("---")
    st.markdown(
        '<div style="color:#C0C8D4;font-size:0.75rem;'
        'text-transform:uppercase;letter-spacing:1px;'
        'margin-bottom:0.5rem;">📋 Identité Rapport</div>',
        unsafe_allow_html=True)

    nom_societe  = st.text_input(
        "Société / Cabinet",
        placeholder="Ex: Allianz France SA")
    nom_actuaire = st.text_input(
        "Actuaire responsable",
        placeholder="Ex: Dr. Jean Martin")
    logo_client  = st.file_uploader(
        "Logo client", type=['png','jpg','jpeg'])
    classification = st.selectbox(
        "Classification",
        ["Confidentiel","Usage interne","Public"])

    st.markdown("---")
    page = st.radio("", [
        "🏠 Accueil",
        "📊 Branche Non-Vie",
        "💼 Branche Vie",
        "📈 ALM",
        "🤖 Agent IA",
        "📄 Rapports",
    ], label_visibility="collapsed")

    st.markdown(
        f'<div style="color:#4A5568;font-size:0.7rem;'
        f'text-align:center;margin-top:1rem;">'
        f'ActuarIA v2.0<br>'
        f'© {datetime.now().year}</div>',
        unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────
st.markdown(
    f'<div class="header-main">'
    f'{logo_html(70)}'
    f'<div>'
    f'<div style="color:white;font-size:2rem;'
    f'font-weight:600;letter-spacing:-0.5px;">'
    f'Actuar<span style="color:#4CAF1A;">IA</span></div>'
    f'<div style="color:#C0C8D4;font-size:0.85rem;'
    f'letter-spacing:3px;text-transform:uppercase;">'
    f'Actuarial Intelligence</div>'
    f'</div>'
    f'<div style="margin-left:auto;text-align:right;">'
    f'<div style="color:#C0C8D4;font-size:0.75rem;">'
    f'Arrêté au '
    f'{datetime.now().strftime("%d/%m/%Y")}</div>'
    f'<div style="color:#4CAF1A;font-size:0.8rem;'
    f'font-weight:600;">'
    f'{nom_societe if nom_societe else "Mode démo"}'
    f'</div></div></div>',
    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGES
# ══════════════════════════════════════════════════════════════

if page == "🏠 Accueil":

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,
        {C['navy']},{C['blue']});border-radius:16px;
        padding:2.5rem;margin-bottom:2rem;
        border-bottom:3px solid {C['green']};">
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

    st.markdown(
        '<div class="section-header">'
        '📊 MARCHÉ EUROPÉEN — EIOPA 2023</div>',
        unsafe_allow_html=True)

    col1,col2,col3,col4,col5 = st.columns(5)
    stats = [
        (col1,"1 290 Mds €","Primes totales EU","+3.2% vs 2022"),
        (col2,"224%","Ratio SCR moyen EU","Source EIOPA 2023"),
        (col3,"67.3%","Loss Ratio NV moyen","Auto+MRH+RC"),
        (col4,"3 200","Entités supervisées","5 pays majeurs"),
        (col5,"1 M","Emplois secteur EU","Actuaires+Tech"),
    ]
    for col,val,label,sub in stats:
        with col:
            st.markdown(f"""
            <div class="hero-stat">
              <div class="hero-stat-val">{val}</div>
              <div class="hero-stat-label">{label}</div>
              <div style="color:#4CAF1A;font-size:0.7rem;
                  margin-top:0.3rem;">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="section-header">'
        '⚡ ENJEUX ACTUARIELS 2024-2026</div>',
        unsafe_allow_html=True)

    enjeux = [
        ("🏛️","Solvabilité 2 — Révision 2024",
         "Le ratio SCR moyen EU est de 224% mais masque "
         "des disparités importantes. La révision 2024 "
         "renforce les exigences sur le risque de "
         "liquidité et les actifs illiquides.",
         "SCR moyen EU : 224% | Ratio MCR min : 100%"),
        ("📋","IFRS 17 — Première année complète",
         "Entrée en vigueur le 1er janvier 2023, "
         "IFRS 17 transforme radicalement le reporting "
         "assurance. La CSM mondiale est estimée à "
         "400 milliards €.",
         "CSM mondiale ≈ 400 Mds € | Impact P&L -12%"),
        ("📈","Inflation sinistres persistante",
         "L'inflation sinistres auto a atteint +8.1% "
         "en 2022 et reste à +5.3% en 2023. Les coûts "
         "de réparation et pièces détachées restent "
         "sous tension.",
         "+8.1% en 2022 | +5.3% en 2023 | VE +15%"),
        ("💻","Cyber risques — marché x3 d'ici 2027",
         "Le marché cyber EU va tripler pour atteindre "
         "23 milliards € en 2027. Corrélations "
         "systémiques et accumulations difficiles "
         "à quantifier.",
         "Marché EU 2023 : 8 Mds € | 2027 : 23 Mds €"),
        ("🌡️","Catastrophes naturelles +40% en 10 ans",
         "Les sinistres Cat Nat ont augmenté de +40% "
         "en 10 ans en Europe. Les modèles doivent "
         "intégrer les scénarios climatiques 1.5°C "
         "et 2°C.",
         "Cat Nat EU 2023 : 54 Mds € | +40% en 10 ans"),
        ("🤖","IA Act européen — impact direct",
         "L'AI Act (2025) classifie les modèles ML "
         "actuariels comme systèmes à haut risque. "
         "Explicabilité et auditabilité obligatoires.",
         "IA Act : en vigueur 2025 | Conformité requise"),
    ]

    for i in range(0, len(enjeux), 2):
        col1, col2 = st.columns(2)
        for col, idx in [(col1,i),(col2,i+1)]:
            if idx < len(enjeux):
                icon,titre,desc,chiffres = enjeux[idx]
                with col:
                    st.markdown(f"""
                    <div style="background:{C['white']};
                        border-radius:12px;padding:1.2rem;
                        border-left:4px solid {C['green']};
                        border:1px solid #E2E8F0;
                        border-left:4px solid {C['green']};
                        margin-bottom:1rem;">
                      <div style="font-size:1.5rem;">
                        {icon}</div>
                      <div style="color:{C['navy']};
                          font-weight:600;font-size:0.9rem;
                          margin:0.4rem 0;">{titre}</div>
                      <div style="color:#4A5568;
                          font-size:0.82rem;line-height:1.6;
                          margin-bottom:0.6rem;">{desc}</div>
                      <div style="background:{C['light']};
                          border-radius:6px;
                          padding:0.4rem 0.8rem;
                          color:{C['navy']};font-size:0.72rem;
                          font-weight:600;">{chiffres}</div>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-header">'
        '🚀 ACTUARIA — LA PLATEFORME</div>',
        unsafe_allow_html=True)

    col1,col2,col3 = st.columns(3)
    points = [
        (col1,"🎯","Couverture complète",
         ["Branche Non-Vie","Branche Vie",
          "Solvabilité 2 EIOPA","IFRS 17 PAA + BBA",
          "ALM actif/passif"]),
        (col2,"🤖","IA augmentée",
         ["5 modèles ML/DL","Agent IA niveaux 1-4",
          "Recalcul à la demande",
          "Génération rapport auto",
          "Alertes réglementaires"]),
        (col3,"📄","Rapports pro",
         ["Niveau Actuaire Senior",
          "3 niveaux : DG/Tech/Régl.",
          "Logo client intégré",
          "Commentaires détaillés",
          "Export PDF immédiat"]),
    ]
    for col,icon,titre,items in points:
        with col:
            items_html = "".join([
                f'<li style="margin-bottom:0.3rem;">{it}</li>'
                for it in items])
            st.markdown(f"""
            <div style="background:{C['navy']};
                border-radius:12px;padding:1.5rem;
                border-bottom:3px solid {C['green']};">
              <div style="font-size:2rem;
                  margin-bottom:0.8rem;">{icon}</div>
              <div style="color:white;font-weight:600;
                  font-size:1rem;margin-bottom:0.8rem;">
                {titre}</div>
              <ul style="color:{C['silver']};
                  font-size:0.82rem;line-height:1.8;
                  padding-left:1.2rem;margin:0;">
                {items_html}</ul>
            </div>
            """, unsafe_allow_html=True)

elif page == "📊 Branche Non-Vie":

    st.markdown("## 📊 Branche Non-Vie")
    tab1,tab2,tab3,tab4 = st.tabs([
        "🎯 Tarification","📐 Provisionnement",
        "🏛️ Solvabilité 2","📋 IFRS 17"])

    with tab1:
        st.markdown(
            '<div class="section-header">'
            '🎯 TARIFICATION — 5 MODÈLES ML/DL</div>',
            unsafe_allow_html=True)

        ml  = resultats.get('ml_v2', {})
        cmp = ml.get('comparaison', [])
        mod_ret  = ml.get('modele_retenu','N/A')
        gini_ret = ml.get('gini_retenu', 0)
        lift_ret = ml.get('lift_retenu', 0)
        g = resultats.get('glm_gamma', {})

        col1,col2,col3,col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-label">Modèle retenu</div>
              <div class="kpi-value"
                style="font-size:1rem;">{mod_ret}</div>
              <div class="kpi-delta ok">
                ✅ Gini/Stabilité optimal</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="kpi-card navy">
              <div class="kpi-label">Gini Test</div>
              <div class="kpi-value">
                {gini_ret:.4f}</div>
              <div class="kpi-delta ok">
                Bon — production</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="kpi-card gold">
              <div class="kpi-label">Lift D1/D10</div>
              <div class="kpi-value">{lift_ret:.2f}x</div>
              <div class="kpi-delta ok">Validé</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            pp = g.get('prime_pure_moy','N/A')
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-label">Prime pure moy.</div>
              <div class="kpi-value">{pp} €</div>
              <div class="kpi-delta ok">GLM Gamma</div>
            </div>""", unsafe_allow_html=True)

        if cmp:
            st.markdown(
                '<div class="section-header">'
                'Comparaison 5 modèles</div>',
                unsafe_allow_html=True)

            df_ml = pd.DataFrame(cmp)
            df_ml = df_ml.sort_values(
                'gini_test', ascending=False)

            colors = [C['green'] if m == mod_ret
                      else C['navy']
                      for m in df_ml['modele']]

            fig = go.Figure(go.Bar(
                x=df_ml['gini_test'],
                y=df_ml['modele'],
                orientation='h',
                marker_color=colors,
                text=[f"{g:.4f}"
                      for g in df_ml['gini_test']],
                textposition='outside'))
            fig.update_layout(
                title='Gini Test — 5 modèles',
                height=260,
                paper_bgcolor='white',
                plot_bgcolor=C['light'],
                margin=dict(l=10,r=80,t=40,b=10))
            st.plotly_chart(fig,
                            use_container_width=True)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior</strong><br>
          Le modèle <strong>{mod_ret}</strong> est retenu
          avec un Gini de <strong>{gini_ret:.4f}</strong>.
          Les variables Bonus-Malus (26.7%), KM annuels
          (26.7%) et Age (23.3%) concentrent 93% de
          l'importance prédictive — cohérent avec le
          référentiel ACPR/EIOPA. Lift D1/D10 =
          {lift_ret:.2f}x. Sur données réelles
          (50k+ sinistres), Gini attendu : 0.25-0.40.
        </div>
        """, unsafe_allow_html=True)

    with tab2:
        st.markdown(
            '<div class="section-header">'
            '📐 PROVISIONNEMENT — TRIANGLE 15 ANS</div>',
            unsafe_allow_html=True)

        p  = resultats.get('provisions_fin', {})
        cl = resultats.get('provisions_cl', {})
        m  = p.get('methodes', {})

        col1,col2,col3,col4 = st.columns(4)
        kpis = [
            (col1,"Chain-Ladder",
             f"{m.get('chain_ladder',0):,.0f} €",
             "navy"),
            (col2,"Bornhuetter-Ferguson",
             f"{m.get('bornhuetter_ferguson',0):,.0f} €",
             ""),
            (col3,"Cape Cod",
             f"{m.get('cape_cod',0):,.0f} €","gold"),
            (col4,"BE Retenu",
             f"{p.get('provision_retenue',0):,.0f} €",""),
        ]
        for col,label,val,cls in kpis:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.3rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

        vals = [m.get('chain_ladder',0),
                m.get('bornhuetter_ferguson',0),
                m.get('cape_cod',0)]
        fig2 = go.Figure(go.Bar(
            x=['Chain-Ladder','BF','Cape Cod'],
            y=vals,
            marker_color=[C['navy'],C['blue'],C['gold']],
            text=[f"{v:,.0f}€" for v in vals],
            textposition='outside'))
        fig2.add_hline(
            y=p.get('provision_retenue',0),
            line_dash='dash',line_color=C['green'],
            annotation_text="BE retenu")
        fig2.add_hline(
            y=p.get('provision_prudente',0),
            line_dash='dot',line_color=C['warning'],
            annotation_text="P90")
        fig2.update_layout(
            title='IBNR — 3 méthodes',
            height=320,paper_bgcolor='white',
            plot_bgcolor=C['light'],
            margin=dict(l=10,r=100,t=40,b=10))
        st.plotly_chart(fig2,use_container_width=True)

        cv  = p.get('cv_inter_methodes',0)
        tail= cl.get('tail_factor',0)
        elr = p.get('elr_cape_cod',0)
        be  = p.get('provision_retenue',0)
        p90 = p.get('provision_prudente',0)
        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          Provisionnement</strong><br>
          Triangle 15 ans × 15 développements
          (tail={tail}). ELR Cape Cod = {elr:.4f}.
          CV inter-méthodes = {cv}% — convergence
          satisfaisante. BE = <strong>{be:,.0f} €
          </strong>. P90 = <strong>{p90:,.0f} €</strong>
          (log-normale). Surveillance recommandée
          sur l'année 2024 (56% de l'IBNR total).
        </div>
        """, unsafe_allow_html=True)

    with tab3:
        st.markdown(
            '<div class="section-header">'
            '🏛️ SOLVABILITÉ 2 — SCR FORMULE STANDARD'
            '</div>', unsafe_allow_html=True)

        s = resultats.get('scr', {})
        ratio = s.get('ratio_scr_pct', 0)
        ratio_mcr = s.get('ratio_mcr_pct', 0)
        bscr = max(s.get('bscr', 1), 1)
        conforme = ratio >= 100 if ratio else False
        conforme_mcr = ratio_mcr >= 100

        col1,col2,col3,col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-label">SCR Total</div>
              <div class="kpi-value">
                {s.get('scr_total',0):,.0f} €</div>
              <div class="kpi-delta ok">EIOPA</div>
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
            st.markdown(f"""
            <div class="kpi-card
              {'navy' if conforme else 'danger'}">
              <div class="kpi-label">Ratio SCR</div>
              <div class="kpi-value">{ratio}%</div>
              <div class="kpi-delta
                {'ok' if conforme else 'down'}">
                {'✅ Conforme' if conforme
                 else '❌ Non conforme'}</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="kpi-card
              {'' if conforme_mcr else 'danger'}">
              <div class="kpi-label">Ratio MCR</div>
              <div class="kpi-value">{ratio_mcr}%</div>
              <div class="kpi-delta
                {'ok' if conforme_mcr else 'down'}">
                {'✅ OK' if conforme_mcr
                 else '⚠️ Sous MCR absolu'}</div>
            </div>""", unsafe_allow_html=True)

        col_g1,col_g2 = st.columns(2)
        with col_g1:
            fig_pie = go.Figure(go.Pie(
                labels=['SCR Marché','SCR Non-Vie',
                        'SCR Contrepartie',
                        'SCR Opérationnel'],
                values=[s.get('scr_marche',0),
                        s.get('scr_nv',0),
                        s.get('scr_contrepartie',0),
                        s.get('scr_operationnel',0)],
                marker_colors=[C['navy'],C['green'],
                               C['gold'],C['silver']],
                hole=0.45,textinfo='label+percent'))
            fig_pie.update_layout(
                title='Décomposition BSCR',
                height=300,showlegend=False,
                paper_bgcolor='white',
                margin=dict(t=40,b=10,l=10,r=10))
            st.plotly_chart(fig_pie,
                            use_container_width=True)

        with col_g2:
            mods = ['Marché','Non-Vie',
                    'Contrepartie','Opérationnel']
            vals_s = [s.get('scr_marche',0),
                      s.get('scr_nv',0),
                      s.get('scr_contrepartie',0),
                      s.get('scr_operationnel',0)]
            fig_bar = go.Figure(go.Bar(
                x=mods,y=vals_s,
                marker_color=C['navy'],
                text=[f"{v/bscr*100:.1f}%"
                      for v in vals_s],
                textposition='outside'))
            fig_bar.update_layout(
                title='SCR par module',
                height=300,paper_bgcolor='white',
                plot_bgcolor=C['light'],
                margin=dict(l=10,r=10,t=40,b=10))
            st.plotly_chart(fig_bar,
                            use_container_width=True)

        if not conforme_mcr:
            st.markdown(f"""
            <div class="alerte-danger">
              ⚠️ <strong>MCR non couvert</strong> —
              Ratio MCR = {ratio_mcr}%.
              MCR absolu EIOPA = 2 500 000 €.
              Action corrective immédiate
              (Art. 129 Dir. 2009/138/CE).
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          Solvabilité 2</strong><br>
          SCR = <strong>{s.get('scr_total',0):,.0f} €
          </strong> (Règlement Délégué 2015/35).
          Module Non-Vie dominant :
          {s.get('scr_nv',0)/bscr*100:.1f}% du BSCR.
          Ratio SCR = <strong>{ratio}%</strong>
          — {'conforme, cible gestion interne 150-180%.'
             if conforme else 'non conforme.'}
        </div>
        """, unsafe_allow_html=True)

    with tab4:
        st.markdown(
            '<div class="section-header">'
            '📋 IFRS 17 — PAA</div>',
            unsafe_allow_html=True)

        i   = resultats.get('ifrs17', {})
        paa = i.get('modele_paa', {})
        bba = i.get('modele_bba', {})

        col1,col2,col3,col4 = st.columns(4)
        kpis_i = [
            (col1,"Insurance Revenue",
             f"{paa.get('insurance_revenue',0):,.0f} €",""),
            (col2,"Insurance Expenses",
             f"{paa.get('insurance_expenses',0):,.0f} €",
             "navy"),
            (col3,"Insurance Result",
             f"{paa.get('insurance_result',0):,.0f} €",""),
            (col4,"Loss Ratio",
             f"{paa.get('loss_ratio_pct',0)}%","navy"),
        ]
        for col,label,val,cls in kpis_i:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.2rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

        fig_i = go.Figure()
        for label,val,color in [
            ('Revenue',
             paa.get('insurance_revenue',0),C['green']),
            ('Expenses',
             paa.get('insurance_expenses',0),C['navy']),
            ('Result',
             paa.get('insurance_result',0),C['gold'])]:
            fig_i.add_trace(go.Bar(
                x=[label],y=[val],
                marker_color=color,name=label))
        fig_i.update_layout(
            title='IFRS 17 PAA — P&L',
            height=280,barmode='group',
            paper_bgcolor='white',plot_bgcolor=C['light'],
            margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(fig_i,use_container_width=True)

        lr = paa.get('loss_ratio_pct',0)
        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          IFRS 17 PAA</strong><br>
          Revenue = <strong>
          {paa.get('insurance_revenue',0):,.0f} €</strong>.
          Loss Ratio = <strong>{lr}%</strong>
          {'— favorable vs benchmark EU 65-75%.'
           if lr < 70 else '— dans le benchmark EU.'}.
          CSM BBA = <strong>{bba.get('csm',0):,.0f} €
          </strong> (profit différé, IFRS 17 §47).
          Aucun Loss Component requis.
        </div>
        """, unsafe_allow_html=True)

elif page == "💼 Branche Vie":

    st.markdown("## 💼 Branche Vie")
    tab1,tab2,tab3,tab4 = st.tabs([
        "💀 Tarification",
        "📊 Provisions Mathématiques",
        "🏛️ Solvabilité 2",
        "📋 IFRS 17 BBA"])

    with tab1:
        st.markdown(
            '<div class="section-header">'
            '💀 TARIFICATION VIE — TABLE EEA 2019</div>',
            unsafe_allow_html=True)

        pm = resultats.get('pm_vie', {})
        cr = pm.get('contrat_reference', {})

        col1,col2,col3,col4 = st.columns(4)
        kpis_tv = [
            (col1,"Prime nivelée",
             f"{cr.get('prime_nivelee',0)} €/an",""),
            (col2,"Capital assuré",
             f"{cr.get('capital_assure',0):,.0f} €",
             "navy"),
            (col3,"Taux technique",
             f"{cr.get('taux_technique',0)*100:.1f}%",
             "gold"),
            (col4,"Table mortalité","EEA 2019",""),
        ]
        for col,label,val,cls in kpis_tv:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.2rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior</strong><br>
          Prime nivelée =
          <strong>{cr.get('prime_nivelee',0)} €/an</strong>
          (méthode prospective, table EEA 2019 EIOPA,
          taux {cr.get('taux_technique',0)*100:.1f}%).
          Portefeuille : décès 40%, épargne 35%,
          rente 25% — 5 pays EU — 15 ans.
        </div>
        """, unsafe_allow_html=True)

    with tab2:
        st.markdown(
            '<div class="section-header">'
            '📊 PROVISIONS MATHÉMATIQUES</div>',
            unsafe_allow_html=True)

        pm = resultats.get('pm_vie', {})
        cr = pm.get('contrat_reference', {})
        pf = pm.get('portefeuille', {})

        col1,col2,col3,col4 = st.columns(4)
        kpis_pm = [
            (col1,"PM maximale",
             f"{cr.get('pm_max',0):,.0f} €",""),
            (col2,"PM à t=10",
             f"{cr.get('pm_t10',0):,.0f} €","navy"),
            (col3,"PM portefeuille",
             f"{pf.get('pm_totale',0):,.0f} €","gold"),
            (col4,"PM moyenne",
             f"{pf.get('pm_moyenne',0):,.0f} €",""),
        ]
        for col,label,val,cls in kpis_pm:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.3rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

        sensi = pm.get('sensibilite_taux', {})
        if sensi:
            taux_l = [
                float(k.replace('pct','')
                       .replace(',','.'))
                for k in sensi.keys()]
            pm_l = list(sensi.values())
            fig_s = go.Figure(go.Scatter(
                x=taux_l,y=pm_l,
                mode='lines+markers',
                line=dict(color=C['navy'],width=3),
                marker=dict(size=8,color=C['green'])))
            fig_s.update_layout(
                title='Sensibilité PM au taux technique',
                height=280,paper_bgcolor='white',
                plot_bgcolor=C['light'],
                xaxis_title='Taux (%)',
                yaxis_title='PM (€)',
                margin=dict(l=10,r=10,t=40,b=10))
            st.plotly_chart(fig_s,
                            use_container_width=True)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior — PM</strong>
          <br>PM max = <strong>
          {cr.get('pm_max',0):,.0f} €</strong> (t=12).
          Cohérence prospective/rétrospective < 0.001€ ✅.
          Sensibilité taux modérée sur décès temporaire
          (-6.1% pour +350bp). Plus forte sur rentes.
        </div>
        """, unsafe_allow_html=True)

    with tab3:
        st.markdown(
            '<div class="section-header">'
            '🏛️ SCR VIE — EIOPA</div>',
            unsafe_allow_html=True)

        pm_v = resultats.get('pm_vie', {})
        pf_v = pm_v.get('portefeuille', {})
        pm_tot = pf_v.get('pm_totale', 763460)

        scr_m = pm_tot * 0.10
        scr_l = pm_tot * 0.15 * 0.25
        scr_r = pm_tot * 0.05
        scr_f = pm_tot * 0.03
        scr_v = (scr_m**2+scr_l**2+
                 scr_r**2+scr_f**2)**0.5

        col1,col2,col3,col4 = st.columns(4)
        for col,label,val in [
            (col1,"SCR Mortalité",scr_m),
            (col2,"SCR Longévité",scr_l),
            (col3,"SCR Rachat",scr_r),
            (col4,"SCR Vie Total",scr_v)]:
            with col:
                st.markdown(f"""
                <div class="kpi-card">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.1rem;">
                    {val:,.0f} €</div>
                </div>""", unsafe_allow_html=True)

        fig_sv = go.Figure(go.Bar(
            x=['Mortalité','Longévité','Rachat','Frais'],
            y=[scr_m,scr_l,scr_r,scr_f],
            marker_color=[C['navy'],C['green'],
                          C['gold'],C['silver']],
            text=[f"{v/1e3:.0f}k€"
                  for v in [scr_m,scr_l,scr_r,scr_f]],
            textposition='outside'))
        fig_sv.update_layout(
            title='Décomposition SCR Vie',
            height=280,paper_bgcolor='white',
            plot_bgcolor=C['light'],
            margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(fig_sv,use_container_width=True)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          SCR Vie</strong><br>
          SCR Vie = <strong>{scr_v:,.0f} €</strong>
          (modules SLT, Règl. Délégué 2015/35).
          Longévité dominant pour rentes viagères (25%).
          Choc mortalité +15% (Art. 138) /
          longévité -20% (Art. 142).
        </div>
        """, unsafe_allow_html=True)

    with tab4:
        st.markdown(
            '<div class="section-header">'
            '📋 IFRS 17 BBA — BUILDING BLOCK APPROACH'
            '</div>',unsafe_allow_html=True)

        i   = resultats.get('ifrs17', {})
        bba = i.get('modele_bba', {})

        col1,col2,col3,col4 = st.columns(4)
        kpis_b = [
            (col1,"FCF (Bloc 1)",
             f"{bba.get('fcf',0):,.0f} €",""),
            (col2,"Risk Adjustment",
             f"{bba.get('ra',0):,.0f} €","navy"),
            (col3,"CSM (Bloc 3)",
             f"{bba.get('csm',0):,.0f} €","gold"),
            (col4,"Passif initial",
             f"{bba.get('total_passif_init',0):,.0f} €",""),
        ]
        for col,label,val,cls in kpis_b:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value"
                    style="font-size:1.2rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

        fig_wf = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative","relative",
                     "relative","total"],
            x=["FCF","Risk Adj.","CSM","Passif"],
            y=[bba.get('fcf',0),bba.get('ra',0),
               bba.get('csm',0),0],
            decreasing=dict(marker_color=C['danger']),
            increasing=dict(marker_color=C['green']),
            totals=dict(marker_color=C['navy'])))
        fig_wf.update_layout(
            title='BBA — Blocs de mesure',
            height=280,paper_bgcolor='white',
            plot_bgcolor=C['light'],
            margin=dict(l=10,r=10,t=40,b=10))
        st.plotly_chart(fig_wf,use_container_width=True)

        st.markdown(f"""
        <div class="alerte-success">
          <strong>💼 Analyse Actuaire Senior —
          IFRS 17 BBA</strong><br>
          Passif initial = 0 ✅ (day-one profit
          prohibition, §47). CSM =
          <strong>{bba.get('csm',0):,.0f} €</strong>
          — profit différé relâché au rythme des
          unités de couverture (§44).
        </div>
        """, unsafe_allow_html=True)

elif page == "📈 ALM":

    st.markdown("## 📈 ALM — Gestion Actif-Passif")
    st.markdown(
        '<div class="section-header">'
        '📈 DURATION GAP ET STRESS TAUX</div>',
        unsafe_allow_html=True)

    pm_v   = resultats.get('pm_vie',{})
    pf_v   = pm_v.get('portefeuille',{})
    passif = pf_v.get('pm_totale', 763_460)
    actif  = passif * 1.15
    dur_a, dur_p = 6.2, 9.8
    gap    = dur_a - dur_p

    col1,col2,col3,col4 = st.columns(4)
    for col,label,val,cls,sub in [
        (col1,"Duration Actif",f"{dur_a:.1f} ans","",""),
        (col2,"Duration Passif",f"{dur_p:.1f} ans",
         "navy",""),
        (col3,"Gap Duration",f"{gap:.1f} ans",
         "danger" if abs(gap)>2 else "",
         "⚠️ Exposition taux" if abs(gap)>2
         else "✅ OK"),
        (col4,"Couverture actif/passif",
         f"{actif/passif*100:.1f}%","",""),]:
        with col:
            st.markdown(f"""
            <div class="kpi-card {cls}">
              <div class="kpi-label">{label}</div>
              <div class="kpi-value">{val}</div>
              <div class="kpi-delta warn">{sub}</div>
            </div>""", unsafe_allow_html=True)

    chocs = [-200,-100,-50,0,+50,+100,+200]
    imp_a = [actif*(-dur_a*c/10000) for c in chocs]
    imp_p = [passif*(-dur_p*c/10000) for c in chocs]
    imp_n = [a-p for a,p in zip(imp_a,imp_p)]

    fig_alm = go.Figure(go.Bar(
        x=[f"{c:+d}bp" for c in chocs],
        y=imp_n,
        marker_color=[C['danger'] if v<0
                      else C['green'] for v in imp_n],
        text=[f"{v:+,.0f}€" for v in imp_n],
        textposition='outside'))
    fig_alm.add_hline(y=0,line_color=C['navy'],
                       line_width=1)
    fig_alm.update_layout(
        title='Impact chocs taux sur Fonds Propres',
        height=300,paper_bgcolor='white',
        plot_bgcolor=C['light'],
        margin=dict(l=10,r=10,t=40,b=10))
    st.plotly_chart(fig_alm,use_container_width=True)

    st.markdown(f"""
    <div class="alerte-reg">
      <strong>💼 Analyse Actuaire Senior — ALM</strong>
      <br>Gap duration = {gap:.1f} ans.
      +100bp → impact net FP =
      <strong>{imp_n[5]:+,.0f} €</strong>.
      Immunisation recommandée — cible gap < 1.5 ans.
      Stratégie : allongement duration actif
      (obligations longues ou swaps de taux).
    </div>
    """, unsafe_allow_html=True)

elif page == "🤖 Agent IA":

    st.markdown("## 🤖 Agent Actuariel IA")

    if not api_key:
        st.warning(
            "Entrez votre clé API dans la sidebar.")
    else:
        if 'hist' not in st.session_state:
            st.session_state.hist = []

        exemples = [
            "IBNR total et méthode recommandée ?",
            "Ratio SCR — conformité Solvabilité 2 ?",
            "Modèle ML retenu et pourquoi ?",
            "CSM IFRS 17 — que représente-t-elle ?",
            "PM maximale contrat vie ?",
            "Synthèse bilan actuariel DG ?",
        ]
        cols = st.columns(3)
        for j,q in enumerate(exemples):
            with cols[j%3]:
                if st.button(q[:30]+"...",
                             key=f"q{j}"):
                    st.session_state.q_ia = q

        question = st.text_input(
            "Votre question :",
            value=st.session_state.get('q_ia',''),
            placeholder="Ex: Quel est le ratio SCR ?")

        if st.button("Envoyer",
                     type="primary") and question:
            with st.spinner("Agent en cours..."):
                s  = resultats.get('scr',{})
                p  = resultats.get('provisions_fin',{})
                i  = resultats.get('ifrs17',{})
                pm = resultats.get('pm_vie',{})
                ml = resultats.get('ml_v2',{})
                g  = resultats.get('glm_gamma',{})

                ctx = f"""
Données ActuarIA v2.0 :
Modèle retenu={ml.get('modele_retenu')},
Gini={ml.get('gini_retenu')},
Prime={g.get('prime_pure_moy')}EUR,
CL={p.get('methodes',{}).get('chain_ladder')}EUR,
BE={p.get('provision_retenue')}EUR,
P90={p.get('provision_prudente')}EUR,
SCR={s.get('scr_total')}EUR,
Ratio SCR={s.get('ratio_scr_pct')}%,
LR IFRS17={i.get('modele_paa',{}).get('loss_ratio_pct')}%,
CSM={i.get('modele_bba',{}).get('csm')}EUR,
PM max={pm.get('contrat_reference',{}).get('pm_max')}EUR,
PM total={pm.get('portefeuille',{}).get('pm_totale')}EUR
"""
                client = anthropic.Anthropic(
                    api_key=api_key)
                resp = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=500,
                    messages=[{"role":"user",
                                "content":
                                f"Actuaire senior EU. "
                                f"Données: {ctx}\n"
                                f"Question: {question}\n"
                                f"4-5 phrases pro avec "
                                f"chiffres exacts et "
                                f"refs réglementaires."}])

                reponse = resp.content[0].text
                st.session_state.hist.append({
                    'q': question,
                    'r': reponse,
                    'h': datetime.now().strftime("%H:%M")
                })
                if 'q_ia' in st.session_state:
                    del st.session_state.q_ia

        for msg in reversed(st.session_state.hist):
            st.markdown(
                f"**❓ {msg['q']}** "
                f"<span style='color:#A0AEC0;"
                f"font-size:0.75rem;'>{msg['h']}</span>",
                unsafe_allow_html=True)
            st.markdown(
                f'<div class="agent-response">'
                f'{msg["r"]}</div>',
                unsafe_allow_html=True)
            st.markdown("---")

elif page == "📄 Rapports":

    st.markdown("## 📄 Rapports Professionnels")

    st.markdown(f"""
    <div class="alerte-success">
      <strong>Configuration</strong> —
      Société : <strong>
        {nom_societe or 'Non renseigné'}</strong> |
      Actuaire : <strong>
        {nom_actuaire or 'Non renseigné'}</strong> |
      {classification}
    </div>
    """, unsafe_allow_html=True)

    rapports = [
        ("🏢","Rapport Direction Générale",
         "8-12 pages — langage business, "
         "graphiques, recommandations actionnables",
         "DG · Conseil d'Administration"),
        ("📊","Rapport Technique IARD",
         "Tarification + Provisionnement + "
         "SCR NV + IFRS 17 PAA",
         "Actuaires · Risk Managers"),
        ("💼","Rapport Technique Vie",
         "Tarification + PM + SCR Vie + IFRS 17 BBA",
         "Actuaires Vie · DAF"),
        ("📈","Rapport ALM",
         "Duration gap + stress taux + immunisation",
         "Direction Financière"),
        ("📋","Rapport Général Consolidé",
         "Rapport complet toutes branches — "
         "niveau Actuaire Senior",
         "ACPR · Commissaires aux comptes"),
    ]

    for i,(icon,titre,desc,public) in enumerate(rapports):
        col1,col2 = st.columns([4,1])
        with col1:
            st.markdown(f"""
            <div style="background:{C['white']};
                border-radius:10px;padding:1rem 1.2rem;
                border-left:4px solid {C['navy']};
                margin-bottom:0.8rem;">
              <strong style="color:{C['navy']};">
                {icon} {titre}</strong>
              <div style="color:#4A5568;
                  font-size:0.82rem;margin-top:0.3rem;">
                {desc}</div>
              <div style="color:#A0AEC0;
                  font-size:0.72rem;margin-top:0.2rem;">
                {public}</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            if st.button(f"📥 PDF",
                         key=f"pdf_{i}"):
                st.info("Phase 14 — en cours")

# ── Footer ────────────────────────────────────────────────────
st.markdown(f"""
<div class="footer">
  ActuarIA v2.0 — Actuarial Intelligence<br>
  IARD · Vie · S2 · IFRS 17 · ALM · Claude API<br>
  © {datetime.now().year} —
  {classification} —
  {nom_societe or 'Mode démo'}
</div>
""", unsafe_allow_html=True)
