# ══════════════════════════════════════════════════════════════
# ACTUARIA v2.0 — APPLICATION FINALE COMPLÈTE
# Interface + Agent IA + Upload + Rapports PDF
# ══════════════════════════════════════════════════════════════

import streamlit as st

# ── Import générateur PDF ─────────────────────────────────────
try:
    from pdf_generator import generer_pdf_streamlit
    PDF_DISPONIBLE = True
except Exception as _e:
    PDF_DISPONIBLE = False

import json, os, sys, base64, copy, math, io
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import anthropic
from datetime import datetime

st.set_page_config(
    page_title="ActuarIA — Actuarial Intelligence",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded")

# ── Logo ──────────────────────────────────────────────────────
def get_logo():
    try:
        import logo_actuaria as la
        return la.LOGO_B64, la.LOGO_MIME
    except:
        return None, None

LOGO_B64, LOGO_MIME = get_logo()

def logo_html(width=120):
    if LOGO_B64:
        return (f'<img src="data:{LOGO_MIME};base64,'
                f'{LOGO_B64}" width="{width}" '
                f'style="object-fit:contain;">')
    return '🏢'


# ══════════════════════════════════════════════════════════════
# THÈME ET FONCTIONS GRAPHIQUES STYLE POWERBI
# ══════════════════════════════════════════════════════════════

POWERBI_COLORS = [
    '#118DFF','#12239E','#E66C37','#6B007B',
    '#E044A7','#744EC2','#D9B300','#D64550']

def pbi_bar_h(labels, values, titre,
              couleurs=None, highlight=None):
    """Barres horizontales style PowerBI"""
    if couleurs is None:
        couleurs = [
            '#118DFF' if (highlight and l==highlight)
            else '#C8C6C4'
            for l in labels]
    fig = go.Figure(go.Bar(
        x=values, y=labels,
        orientation='h',
        marker=dict(color=couleurs,
                    line=dict(width=0)),
        text=[f"{v:,.2f}" if v < 10
              else f"{v:,.0f}"
              for v in values],
        textposition='outside',
        hovertemplate=(
            '<b>%{y}</b><br>%{x:,.2f}'
            '<extra></extra>')))
    fig.update_layout(
        title=dict(text=titre,
                   font=dict(size=13,
                             color='#252423',
                             family='Segoe UI'),
                   x=0),
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(t=40,b=20,l=10,r=80),
        font=dict(family='Segoe UI',
                  color='#252423'),
        xaxis=dict(showgrid=True,
                   gridcolor='#F3F2F1',
                   zeroline=False,
                   showline=False),
        yaxis=dict(showgrid=False,
                   zeroline=False))
    return fig


def pbi_donut(labels, values, titre,
              couleurs=None):
    """Donut style PowerBI avec total au centre"""
    if couleurs is None:
        couleurs = POWERBI_COLORS
    total = sum(values)
    pcts  = [v/total*100 for v in values]
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.62,
        marker=dict(
            colors=couleurs[:len(labels)],
            line=dict(color='white',width=2)),
        textinfo='none',
        hovertemplate=(
            '<b>%{label}</b><br>'
            '%{value:,.0f} €<br>'
            '%{percent}<extra></extra>')))
    fig.add_annotation(
        text=(f'<b>{total/1000:.0f}k</b>'
              if total > 1000
              else f'<b>{total:,.0f}</b>'),
        x=0.5, y=0.55,
        font=dict(size=20,color='#252423',
                  family='Segoe UI'),
        showarrow=False)
    fig.add_annotation(
        text='Total',
        x=0.5, y=0.38,
        font=dict(size=10,color='#605E5C',
                  family='Segoe UI'),
        showarrow=False)
    # Légende tableau à droite
    legend_html = ""
    for lbl,val,pct,col in zip(
            labels,values,pcts,
            couleurs[:len(labels)]):
        legend_html += (
            f'<div style="display:flex;'
            f'align-items:center;gap:6px;'
            f'margin-bottom:4px;">'
            f'<div style="width:10px;height:10px;'
            f'background:{col};border-radius:2px;'
            f'flex-shrink:0;"></div>'
            f'<div style="font-size:0.7rem;'
            f'color:#252423;">{lbl}</div>'
            f'<div style="margin-left:auto;'
            f'font-size:0.7rem;font-weight:600;'
            f'color:#252423;">{pct:.1f}%</div>'
            f'</div>')
    fig.update_layout(
        title=dict(text=titre,
                   font=dict(size=13,
                             color='#252423',
                             family='Segoe UI'),
                   x=0),
        showlegend=False,
        paper_bgcolor='white',
        margin=dict(t=40,b=20,l=10,r=10),
        font=dict(family='Segoe UI'))
    return fig, legend_html


def pbi_gauge(valeur, maxi, cible, titre,
              unite='%'):
    """Jauge style PowerBI"""
    if valeur >= cible:
        couleur = '#118DFF'
    elif valeur >= cible * 0.7:
        couleur = '#E66C37'
    else:
        couleur = '#D64550'

    fig = go.Figure(go.Indicator(
        mode='gauge+number+delta',
        value=valeur,
        number=dict(
            suffix=unite,
            font=dict(size=32,color='#252423',
                      family='Segoe UI')),
        delta=dict(
            reference=cible,
            valueformat='.1f',
            suffix=unite,
            increasing=dict(color='#118DFF'),
            decreasing=dict(color='#D64550')),
        gauge=dict(
            axis=dict(
                range=[0,maxi],
                tickcolor='#C8C6C4',
                tickfont=dict(
                    color='#605E5C',size=9)),
            bar=dict(color=couleur,thickness=0.25),
            bgcolor='white',
            borderwidth=0,
            steps=[
                dict(range=[0,cible*0.5],
                     color='#FEE9E8'),
                dict(range=[cible*0.5,cible],
                     color='#FFF4CE'),
                dict(range=[cible,maxi],
                     color='#E8F4FD')],
            threshold=dict(
                line=dict(color='#D64550',width=3),
                thickness=0.8,
                value=cible))))
    fig.update_layout(
        title=dict(text=titre,
                   font=dict(size=13,
                             color='#252423',
                             family='Segoe UI'),
                   x=0),
        paper_bgcolor='white',
        margin=dict(t=50,b=20,l=30,r=30),
        height=250,
        font=dict(family='Segoe UI'))
    return fig


def pbi_waterfall(labels, values, titre):
    """Waterfall style PowerBI"""
    measures = (
        ['absolute'] +
        ['relative']*(len(values)-2) +
        ['total'])
    fig = go.Figure(go.Waterfall(
        x=labels, y=values,
        measure=measures,
        connector=dict(
            line=dict(color='#C8C6C4',
                      width=1,dash='dot')),
        increasing=dict(
            marker=dict(color='#118DFF')),
        decreasing=dict(
            marker=dict(color='#D64550')),
        totals=dict(
            marker=dict(color='#252423')),
        text=[f"{v:+,.0f}" for v in values],
        textposition='outside'))
    fig.update_layout(
        title=dict(text=titre,
                   font=dict(size=13,
                             color='#252423',
                             family='Segoe UI'),
                   x=0),
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(t=40,b=20,l=10,r=10),
        font=dict(family='Segoe UI',
                  color='#252423'),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True,
                   gridcolor='#F3F2F1'))
    return fig


def pbi_line(x_labels, series, titre):
    """
    Courbes multi-séries style PowerBI
    series = [{'name':'...','values':[...]}, ...]
    """
    fig = go.Figure()
    for idx,serie in enumerate(series):
        col = POWERBI_COLORS[
            idx % len(POWERBI_COLORS)]
        fig.add_trace(go.Scatter(
            x=x_labels,
            y=serie['values'],
            name=serie['name'],
            mode='lines+markers',
            line=dict(color=col,width=2.5),
            marker=dict(color=col,size=6),
            hovertemplate=(
                f"<b>{serie['name']}</b><br>"
                f"%{{x}}<br>%{{y:,.0f}}"
                f"<extra></extra>")))
    fig.update_layout(
        title=dict(text=titre,
                   font=dict(size=13,
                             color='#252423',
                             family='Segoe UI'),
                   x=0),
        paper_bgcolor='white',
        plot_bgcolor='white',
        legend=dict(
            orientation='h',
            yanchor='bottom',y=1.02,
            xanchor='left',x=0,
            font=dict(size=10)),
        margin=dict(t=60,b=20,l=10,r=10),
        font=dict(family='Segoe UI',
                  color='#252423'),
        xaxis=dict(showgrid=True,
                   gridcolor='#F3F2F1',
                   zeroline=False),
        yaxis=dict(showgrid=True,
                   gridcolor='#F3F2F1',
                   zeroline=False))
    return fig


def pbi_kpi_card(titre, valeur, delta,
                 delta_label, couleur='#118DFF'):
    """Card KPI style PowerBI"""
    dir_arrow = ('▲' if delta >= 0 else '▼')
    col_delta  = ('#118DFF' if delta >= 0
                  else '#D64550')
    return f"""
    <div style="background:white;
        border-radius:4px;padding:1rem 1.2rem;
        border-top:3px solid {couleur};
        box-shadow:0 1px 6px rgba(0,0,0,0.08);
        font-family:Segoe UI,sans-serif;">
      <div style="color:#605E5C;font-size:0.7rem;
          text-transform:uppercase;
          letter-spacing:0.5px;margin-bottom:0.4rem;">
        {titre}</div>
      <div style="color:#252423;font-size:1.9rem;
          font-weight:700;line-height:1.1;">
        {valeur}</div>
      <div style="color:{col_delta};
          font-size:0.75rem;margin-top:0.3rem;">
        {dir_arrow} {abs(delta):.1f} {delta_label}
      </div>
    </div>"""


# ── Palette ───────────────────────────────────────────────────
C = {
    'navy':    '#0D1B3E',
    'blue':    '#1B3A6B',
    'green':   '#4CAF1A',
    'silver':  '#C0C8D4',
    'white':   '#FFFFFF',
    'gold':    '#FFC000',
    'light':   '#F0F4FF',
    'danger':  '#E53E3E',
    'success': '#48BB78',
    'grey':    '#718096',
}

# ── CSS ───────────────────────────────────────────────────────
st.markdown(f"""
<style>
.main .block-container {{
    padding:1.5rem 2rem;max-width:1400px;}}
.header-main {{
    background:linear-gradient(135deg,
        {C['navy']} 0%,{C['blue']} 100%);
    padding:1.2rem 2rem;border-radius:14px;
    display:flex;align-items:center;gap:1.2rem;
    margin-bottom:1.5rem;
    border-bottom:3px solid {C['green']};}}
.kpi-card {{
    background:{C['white']};border-radius:10px;
    padding:1rem 1.2rem;
    border-left:4px solid {C['green']};
    border:1px solid #E2E8F0;
    border-left:4px solid {C['green']};
    box-shadow:0 2px 6px rgba(13,27,62,0.07);
    margin-bottom:0.8rem;}}
.kpi-card.navy  {{border-left-color:{C['navy']};}}
.kpi-card.gold  {{border-left-color:{C['gold']};}}
.kpi-card.red   {{border-left-color:{C['danger']};}}
.kpi-label {{
    color:{C['grey']};font-size:0.7rem;
    text-transform:uppercase;letter-spacing:1px;
    margin-bottom:0.3rem;}}
.kpi-value {{
    color:{C['navy']};font-size:1.6rem;
    font-weight:600;line-height:1.1;}}
.kpi-delta.ok   {{color:{C['success']};font-size:0.72rem;}}
.kpi-delta.warn {{color:{C['gold']};font-size:0.72rem;}}
.kpi-delta.bad  {{color:{C['danger']};font-size:0.72rem;}}
.section-header {{
    background:{C['navy']};color:{C['white']};
    padding:0.55rem 1rem;border-radius:7px;
    font-size:0.88rem;font-weight:600;
    margin:1.2rem 0 0.8rem 0;
    border-left:4px solid {C['green']};}}
.agent-msg {{
    background:#EBF3FB;border-radius:9px;
    padding:1rem 1.2rem;
    border-left:4px solid {C['blue']};
    margin-top:0.6rem;font-size:0.9rem;
    line-height:1.65;color:{C['navy']};}}
.recalcul-box {{
    background:#F0FFF4;border-radius:8px;
    padding:0.8rem 1rem;
    border:1px solid {C['success']};
    margin-top:0.5rem;font-size:0.85rem;}}
.alerte-red {{
    background:#FEE2E2;border-radius:8px;
    padding:0.7rem 1rem;
    border-left:4px solid {C['danger']};
    font-size:0.85rem;color:#742A2A;
    margin:0.5rem 0;}}
.alerte-green {{
    background:#D1FAE5;border-radius:8px;
    padding:0.7rem 1rem;
    border-left:4px solid {C['success']};
    font-size:0.85rem;color:#1C4532;
    margin:0.5rem 0;}}
.upload-zone {{
    background:{C['light']};border-radius:10px;
    padding:1.5rem;border:2px dashed #CBD5E0;
    text-align:center;margin:1rem 0;}}
section[data-testid="stSidebar"] {{
    background:{C['navy']};}}
section[data-testid="stSidebar"] * {{
    color:{C['silver']} !important;}}
.stButton > button {{
    background:linear-gradient(135deg,
        {C['navy']},{C['blue']});
    color:white !important;border:none;
    border-radius:7px;padding:0.45rem 1.2rem;
    font-weight:600;}}
.footer {{
    text-align:center;color:#A0AEC0;
    font-size:0.72rem;padding:1.5rem 0 0.5rem;
    border-top:1px solid #E2E8F0;
    margin-top:2rem;}}
</style>
""", unsafe_allow_html=True)

# ── Chargement JSON ───────────────────────────────────────────
@st.cache_data
def charger_resultats():
    r = {}
    fichiers = {
        'scr':    'scr_solvabilite2.json',
        'prov':   'provisions_finales.json',
        'cl':     'provisions_chain_ladder.json',
        'ifrs17': 'ifrs17_results.json',
        'pm_vie': 'provisions_mathematiques.json',
        'glm_g':  'glm_gamma_meta.json',
        'glm_f':  'glm_poisson_meta.json',
        'ml_v2':  'comparaison_ml.json',
    }
    for cle, fichier in fichiers.items():
        try:
            with open(fichier) as f:
                r[cle] = json.load(f)
        except:
            r[cle] = {}
    return r

DATA = charger_resultats()

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div style="text-align:center;padding:0.8rem 0;">'
        f'{logo_html(90)}'
        f'<div style="color:#4CAF1A;font-size:1rem;'
        f'font-weight:600;margin-top:0.4rem;">ActuarIA</div>'
        f'<div style="color:#718096;font-size:0.6rem;'
        f'letter-spacing:2px;">ACTUARIAL INTELLIGENCE</div>'
        f'</div>',
        unsafe_allow_html=True)

    st.markdown("---")

    # Clé API
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
        st.markdown(
            '<div style="background:#1C4532;color:#68D391;'
            'padding:0.35rem 0.7rem;border-radius:5px;'
            'font-size:0.72rem;text-align:center;">'
            '🔐 API chargée</div>',
            unsafe_allow_html=True)
    except:
        api_key = st.text_input(
            "Clé API Claude", type="password",
            placeholder="sk-ant-...")

    st.markdown("---")

    # Identité rapport
    st.markdown(
        '<div style="color:#C0C8D4;font-size:0.72rem;'
        'text-transform:uppercase;letter-spacing:1px;'
        'margin-bottom:0.4rem;">📋 Rapport</div>',
        unsafe_allow_html=True)

    nom_societe  = st.text_input(
        "Société", placeholder="Ex: Allianz France")
    nom_actuaire = st.text_input(
        "Actuaire", placeholder="Ex: Dr. Martin")
    logo_client  = st.file_uploader(
        "Logo client", type=['png','jpg','jpeg'])
    classification = st.selectbox(
        "Classification",
        ["Confidentiel","Usage interne","Public"])

    st.markdown(
        '<div style="color:#C0C8D4;font-size:0.72rem;'
        'text-transform:uppercase;letter-spacing:1px;'
        'margin:0.8rem 0 0.4rem;">🌐 Langue rapport</div>',
        unsafe_allow_html=True)

    langue_rapport = st.radio(
        "", ['🇫🇷 Français','🇬🇧 English'],
        label_visibility="collapsed")
    langue_code = ('FR' if '🇫🇷' in langue_rapport
                   else 'EN')

    st.markdown("---")

    page = st.radio("", [
        "🏠 Accueil",
        "📊 Dashboard PowerBI",
        "📉 Branche Non-Vie",
        "💼 Branche Vie",
        "📈 ALM",
        "🤖 Agent IA",
        "📤 Upload Données",
        "📄 Rapports",
    ], label_visibility="collapsed")

    st.markdown(
        f'<div style="color:#4A5568;font-size:0.65rem;'
        f'text-align:center;margin-top:0.8rem;">'
        f'ActuarIA v2.0 © {datetime.now().year}'
        f'</div>', unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────
st.markdown(
    f'<div class="header-main">'
    f'{logo_html(60)}'
    f'<div>'
    f'<div style="color:white;font-size:1.8rem;'
    f'font-weight:600;letter-spacing:-0.5px;">'
    f'Actuar<span style="color:#4CAF1A;">IA</span></div>'
    f'<div style="color:#C0C8D4;font-size:0.8rem;'
    f'letter-spacing:2px;">ACTUARIAL INTELLIGENCE</div>'
    f'</div>'
    f'<div style="margin-left:auto;text-align:right;">'
    f'<div style="color:#C0C8D4;font-size:0.7rem;">'
    f'{datetime.now().strftime("%d/%m/%Y")}</div>'
    f'<div style="color:#4CAF1A;font-size:0.78rem;'
    f'font-weight:600;">'
    f'{nom_societe if nom_societe else "Mode démo"}'
    f'</div></div></div>',
    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE ACCUEIL
# ══════════════════════════════════════════════════════════════

elif page == "📊 Dashboard PowerBI":

    # En-tête style PowerBI
    st.markdown(f"""
    <div style="background:#252423;
        padding:0.7rem 1.2rem;margin:-1rem -1rem 1.2rem;
        border-radius:8px;
        display:flex;align-items:center;gap:1rem;">
      <div style="color:#F3F2F1;font-size:1rem;
          font-weight:600;font-family:Segoe UI;">
        📊 Tableau de Bord Exécutif
      </div>
      <div style="color:#A19F9D;font-size:0.75rem;
          margin-left:auto;">
        ActuarIA v2.0 —
        {datetime.now().strftime("%d/%m/%Y %H:%M")}
      </div>
    </div>""", unsafe_allow_html=True)

    # Données
    s   = DATA.get('scr',{})
    p   = DATA.get('prov',{})
    ml  = DATA.get('ml_v2',{})
    ir  = DATA.get('ifrs17',{})
    g   = DATA.get('glm_g',{})
    pm  = DATA.get('pm_vie',{})
    mp  = p.get('methodes',{})
    paa = ir.get('modele_paa',{})
    bba = ir.get('modele_bba',{})
    pf  = pm.get('portefeuille',{})
    bscr= max(s.get('bscr',1),1)
    mod = ml.get('modele_retenu','N/A')
    r_s = s.get('ratio_scr_pct',0)
    r_m = s.get('ratio_mcr_pct',0)
    lr  = paa.get('loss_ratio_pct',0)

    # ── LIGNE 1 : KPI Cards ───────────────────────
    st.markdown(
        '<div style="font-size:0.72rem;'
        'color:#605E5C;font-family:Segoe UI;'
        'text-transform:uppercase;'
        'letter-spacing:1px;margin-bottom:0.6rem;">'
        'Indicateurs Clés</div>',
        unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    kpis = [
        (c1,'Prime Pure',
         f"{g.get('prime_pure_moy','N/A')} €",
         2.3,'vs N-1','#118DFF'),
        (c2,'Ratio SCR',f"{r_s}%",
         r_s-150,'vs cible 150%',
         '#118DFF' if r_s>=150 else '#E66C37'),
        (c3,'Loss Ratio IFRS 17',f"{lr}%",
         65-lr,'vs benchmark 65%',
         '#118DFF' if lr<=65 else '#E66C37'),
        (c4,'IBNR Best Estimate',
         f"{p.get('provision_retenue',0):,.0f} €",
         1.2,'vs trim.','#12239E'),
        (c5,'CSM BBA',
         f"{bba.get('csm',0):,.0f} €",
         0.0,'stable','#6B007B'),
    ]
    for col,titre,val,delta,lbl,col_hex in kpis:
        with col:
            st.markdown(
                pbi_kpi_card(
                    titre,val,delta,lbl,col_hex),
                unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── LIGNE 2 : Tarification + SCR ─────────────
    st.markdown(
        '<div style="font-size:0.72rem;'
        'color:#605E5C;font-family:Segoe UI;'
        'text-transform:uppercase;'
        'letter-spacing:1px;margin-bottom:0.6rem;">'
        'Tarification & Solvabilité</div>',
        unsafe_allow_html=True)

    c1,c2,c3 = st.columns([1.3,1,1])

    with c1:
        # Barres Gini modèles
        cmp = ml.get('comparaison',[])
        if cmp:
            fig = pbi_bar_h(
                labels=[m['modele'] for m in cmp],
                values=[m['gini_test'] for m in cmp],
                titre='Gini Test — Modèles ML/DL',
                highlight=mod)
            st.plotly_chart(
                fig, use_container_width=True,
                key='pbi_gini')

    with c2:
        # Donut BSCR
        fig2,leg = pbi_donut(
            labels=['Marché','Non-Vie',
                    'Contrep.','Opérat.'],
            values=[s.get('scr_marche',0),
                    s.get('scr_nv',0),
                    s.get('scr_contrepartie',0),
                    s.get('scr_operationnel',0)],
            titre='Décomposition BSCR',
            couleurs=['#118DFF','#12239E',
                      '#E66C37','#6B007B'])
        st.plotly_chart(
            fig2, use_container_width=True,
            key='pbi_bscr')
        st.markdown(leg, unsafe_allow_html=True)

    with c3:
        # Gauge SCR
        fig3 = pbi_gauge(
            valeur=r_s, maxi=250,
            cible=150,
            titre='Ratio SCR (%)',
            unite='%')
        st.plotly_chart(
            fig3, use_container_width=True,
            key='pbi_gauge_scr')

        # Gauge MCR
        fig_mcr = pbi_gauge(
            valeur=r_m, maxi=150,
            cible=100,
            titre='Ratio MCR (%)',
            unite='%')
        st.plotly_chart(
            fig_mcr, use_container_width=True,
            key='pbi_gauge_mcr')

    st.markdown("<br>", unsafe_allow_html=True)

    # ── LIGNE 3 : Provisionnement + IFRS 17 ──────
    st.markdown(
        '<div style="font-size:0.72rem;'
        'color:#605E5C;font-family:Segoe UI;'
        'text-transform:uppercase;'
        'letter-spacing:1px;margin-bottom:0.6rem;">'
        'Provisionnement & IFRS 17</div>',
        unsafe_allow_html=True)

    c1,c2 = st.columns(2)

    with c1:
        # Waterfall IBNR
        cl_v = mp.get('chain_ladder',0)
        bf_v = mp.get('bornhuetter_ferguson',0)
        cc_v = mp.get('cape_cod',0)
        be_v = p.get('provision_retenue',0)
        fig4 = pbi_waterfall(
            labels=['Chain-Ladder','→ BF',
                    '→ Cape Cod','BE retenu'],
            values=[cl_v,
                    bf_v - cl_v,
                    cc_v - bf_v,
                    be_v],
            titre='Waterfall IBNR — 3 méthodes (€)')
        st.plotly_chart(
            fig4, use_container_width=True,
            key='pbi_waterfall')

    with c2:
        # Barres IFRS 17 PAA
        fig5 = pbi_bar_h(
            labels=['Insurance Revenue',
                    'Insurance Expenses',
                    'Insurance Result',
                    'CSM BBA'],
            values=[paa.get(
                        'insurance_revenue',0),
                    paa.get(
                        'insurance_expenses',0),
                    paa.get(
                        'insurance_result',0),
                    bba.get('csm',0)],
            titre='IFRS 17 — PAA & BBA (€)',
            couleurs=['#118DFF','#D64550',
                      '#12239E','#E66C37'])
        st.plotly_chart(
            fig5, use_container_width=True,
            key='pbi_ifrs17')

    st.markdown("<br>", unsafe_allow_html=True)

    # ── LIGNE 4 : ALM Stress Tests ────────────────
    st.markdown(
        '<div style="font-size:0.72rem;'
        'color:#605E5C;font-family:Segoe UI;'
        'text-transform:uppercase;'
        'letter-spacing:1px;margin-bottom:0.6rem;">'
        'ALM — Stress Tests Taux</div>',
        unsafe_allow_html=True)

    passif = pf.get('pm_totale',763460)
    actif  = passif*1.15
    dur_a,dur_p = 6.2,9.8
    fp = s.get('fonds_propres',480000)
    chocs = [-200,-100,-50,0,50,100,200]
    imp_n = [actif*(-dur_a*c/10000) -
             passif*(-dur_p*c/10000)
             for c in chocs]

    c1,c2 = st.columns([1.5,1])

    with c1:
        # Barres stress tests
        fig6 = go.Figure(go.Bar(
            x=[f'{c:+d}bp' for c in chocs],
            y=imp_n,
            marker_color=[
                '#D64550' if v<0
                else '#118DFF'
                for v in imp_n],
            text=[f'{v:+,.0f}€' for v in imp_n],
            textposition='outside'))
        fig6.add_hline(
            y=0,
            line_color='#252423',
            line_width=1.5)
        fig6.update_layout(
            title=dict(
                text='Impact sur Fonds Propres (€)',
                font=dict(size=13,
                          color='#252423',
                          family='Segoe UI'),
                x=0),
            paper_bgcolor='white',
            plot_bgcolor='white',
            margin=dict(t=40,b=20,l=10,r=10),
            font=dict(family='Segoe UI'),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True,
                       gridcolor='#F3F2F1'))
        st.plotly_chart(
            fig6, use_container_width=True,
            key='pbi_alm')

    with c2:
        # Tableau synthèse ALM
        st.markdown(
            '<div style="background:white;'
            'border-radius:4px;padding:1rem;'
            'box-shadow:0 1px 6px rgba(0,0,0,0.08);'
            'font-family:Segoe UI;">'
            '<div style="color:#252423;'
            'font-weight:600;font-size:0.85rem;'
            'margin-bottom:0.8rem;">'
            'Synthèse ALM</div>',
            unsafe_allow_html=True)

        alm_data = [
            ('Duration Actif',
             f'{dur_a:.1f} ans',''),
            ('Duration Passif',
             f'{dur_p:.1f} ans',''),
            ('Gap Duration',
             f'{dur_a-dur_p:.1f} ans',
             '⚠️'),
            ('Couverture A/P',
             f'{actif/passif*100:.1f}%','✅'),
            ('Impact +100bp',
             f'{imp_n[5]:+,.0f} €',
             '🔵'),
            ('Impact +200bp',
             f'{imp_n[6]:+,.0f} €',
             '🟡'),
            ('Impact -200bp',
             f'{imp_n[0]:+,.0f} €',
             '🔴'),
        ]
        for lbl,val,ic in alm_data:
            st.markdown(
                f'<div style="display:flex;'
                f'justify-content:space-between;'
                f'padding:0.3rem 0;'
                f'border-bottom:1px solid #F3F2F1;'
                f'font-size:0.82rem;">'
                f'<span style="color:#605E5C;">'
                f'{lbl}</span>'
                f'<span style="color:#252423;'
                f'font-weight:600;">'
                f'{ic} {val}</span>'
                f'</div>',
                unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Footer PowerBI style ──────────────────────
    st.markdown(f"""
    <div style="background:#F3F2F1;
        border-radius:4px;padding:0.5rem 1rem;
        margin-top:1rem;
        display:flex;justify-content:space-between;
        font-family:Segoe UI;font-size:0.7rem;
        color:#605E5C;">
      <span>ActuarIA v2.0 — Actuarial Intelligence
      </span>
      <span>Données : 100 000 contrats —
        2010-2024</span>
      <span>
        {datetime.now().strftime("%d/%m/%Y %H:%M")}
      </span>
    </div>""", unsafe_allow_html=True)


if page == "🏠 Accueil":

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,
        {C['navy']},{C['blue']});border-radius:14px;
        padding:2rem;margin-bottom:1.5rem;
        border-bottom:3px solid {C['green']};">
      <h1 style="color:white;font-size:2rem;margin:0;
          font-weight:700;letter-spacing:-0.5px;">
        L'Intelligence Actuarielle<br>
        <span style="color:{C['green']};">
        au service de la décision</span></h1>
      <p style="color:{C['silver']};margin:0.8rem 0 0;
          font-size:0.95rem;max-width:580px;">
        Plateforme actuarielle IA — Tarification,
        Provisionnement, Solvabilité 2, IFRS 17,
        ALM et Agent IA en un seul outil.
      </p>
    </div>""", unsafe_allow_html=True)

    col1,col2,col3,col4,col5 = st.columns(5)
    stats = [
        (col1,"1 290 Mds €","Primes EU","Source EIOPA"),
        (col2,"224%","SCR moyen EU","EIOPA 2023"),
        (col3,"67.3%","Loss Ratio NV","Marché EU"),
        (col4,"3 200","Entités EIOPA","5 pays"),
        (col5,"1 M","Emplois EU","Actuaires+Tech"),
    ]
    for col,val,lbl,sub in stats:
        with col:
            st.markdown(f"""
            <div style="background:white;
                border-radius:10px;padding:0.9rem;
                text-align:center;
                border-top:3px solid {C['green']};
                box-shadow:0 2px 6px rgba(0,0,0,0.05);">
              <div style="color:{C['navy']};
                  font-size:1.4rem;font-weight:700;">
                {val}</div>
              <div style="color:#718096;
                  font-size:0.7rem;text-transform:uppercase;">
                {lbl}</div>
              <div style="color:{C['green']};
                  font-size:0.65rem;">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    modules = [
        (c1,"🎯","Tarification ML/DL",
         ["5 modèles comparés","Gini + Lift",
          "Variables ACPR/EIOPA","Prime pure optimisée"]),
        (c2,"🏛️","Réglementaire",
         ["Solvabilité 2 EIOPA","IFRS 17 PAA + BBA",
          "SCR formule standard","MCR + alertes"]),
        (c3,"🤖","Agent IA",
         ["Q&A portefeuille","Recalcul temps réel",
          "Modification paramètres",
          "Génération rapport auto"]),
    ]
    for col,icon,titre,items in modules:
        with col:
            items_html = "".join([
                f'<li style="margin:0.25rem 0;">'
                f'{it}</li>' for it in items])
            st.markdown(f"""
            <div style="background:{C['navy']};
                border-radius:10px;padding:1.2rem;
                border-bottom:3px solid {C['green']};">
              <div style="font-size:1.6rem;">{icon}</div>
              <div style="color:white;font-weight:600;
                  font-size:0.9rem;margin:0.5rem 0;">
                {titre}</div>
              <ul style="color:{C['silver']};
                  font-size:0.78rem;line-height:1.7;
                  padding-left:1rem;margin:0;">
                {items_html}</ul>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE BRANCHE NON-VIE
# ══════════════════════════════════════════════════════════════
elif page == "📉 Branche Non-Vie":

    st.markdown("## 📊 Branche Non-Vie")
    tab1,tab2,tab3,tab4 = st.tabs([
        "🎯 Tarification","📐 Provisionnement",
        "🏛️ Solvabilité 2","📋 IFRS 17"])

    with tab1:
        st.markdown(
            '<div class="section-header">'
            '🎯 TARIFICATION — 5 MODÈLES ML/DL</div>',
            unsafe_allow_html=True)

        ml  = DATA.get('ml_v2',{})
        g   = DATA.get('glm_g',{})
        cmp = ml.get('comparaison',[])
        mod = ml.get('modele_retenu','N/A')
        gin = ml.get('gini_retenu',0)
        lft = ml.get('lift_retenu',0)
        pp  = g.get('prime_pure_moy','N/A')

        c1,c2,c3,c4 = st.columns(4)
        for col,lbl,val,cls,delta in [
            (c1,'Modèle retenu',mod,'','✅ Optimal'),
            (c2,'Gini Test',f'{gin:.4f}','navy',
             'Bon — production'),
            (c3,'Lift D1/D10',f'{lft:.2f}x','gold',
             'Discriminant'),
            (c4,'Prime pure',f'{pp} €','',
             'GLM Gamma'),
        ]:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{lbl}</div>
                  <div class="kpi-value"
                    style="font-size:1.1rem;">{val}</div>
                  <div class="kpi-delta ok">{delta}</div>
                </div>""", unsafe_allow_html=True)

        if cmp:
            df_ml = pd.DataFrame(cmp).sort_values(
                'gini_test', ascending=False)
            fig = go.Figure(go.Bar(
                x=df_ml['gini_test'],
                y=df_ml['modele'],
                orientation='h',
                marker_color=[
                    C['green'] if m==mod
                    else C['navy']
                    for m in df_ml['modele']],
                text=[f"{g:.4f}"
                      for g in df_ml['gini_test']],
                textposition='outside'))
            fig.update_layout(
                title='Gini Test — 5 modèles',
                height=260,paper_bgcolor='white',
                plot_bgcolor=C['light'],
                margin=dict(l=10,r=80,t=40,b=10))
            st.plotly_chart(fig,
                            use_container_width=True)

    with tab2:
        st.markdown(
            '<div class="section-header">'
            '📐 PROVISIONNEMENT — TRIANGLE 15 ANS'
            '</div>', unsafe_allow_html=True)

        p  = DATA.get('prov',{})
        cl = DATA.get('cl',{})
        m  = p.get('methodes',{})

        c1,c2,c3,c4 = st.columns(4)
        for col,lbl,val,cls in [
            (c1,'Chain-Ladder',
             f"{m.get('chain_ladder',0):,.0f} €",'navy'),
            (c2,'Bornhuetter-Ferguson',
             f"{m.get('bornhuetter_ferguson',0):,.0f} €",''),
            (c3,'Cape Cod',
             f"{m.get('cape_cod',0):,.0f} €",'gold'),
            (c4,'BE Retenu',
             f"{p.get('provision_retenue',0):,.0f} €",''),
        ]:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{lbl}</div>
                  <div class="kpi-value"
                    style="font-size:1.2rem;">{val}</div>
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
        fig2.update_layout(
            title='IBNR — 3 méthodes',height=300,
            paper_bgcolor='white',
            plot_bgcolor=C['light'],
            margin=dict(l=10,r=80,t=40,b=10))
        st.plotly_chart(fig2,use_container_width=True)

    with tab3:
        st.markdown(
            '<div class="section-header">'
            '🏛️ SOLVABILITÉ 2 — SCR FORMULE STANDARD'
            '</div>', unsafe_allow_html=True)

        s = DATA.get('scr',{})
        r = s.get('ratio_scr_pct',0)
        rm = s.get('ratio_mcr_pct',0)
        bscr = max(s.get('bscr',1),1)
        ok = r >= 100

        c1,c2,c3,c4 = st.columns(4)
        for col,lbl,val,cls,delta,dcls in [
            (c1,'SCR Total',
             f"{s.get('scr_total',0):,.0f} €",
             '','Formule standard','ok'),
            (c2,'Fonds Propres',
             f"{s.get('fonds_propres',0):,.0f} €",
             'navy','Tier 1','ok'),
            (c3,'Ratio SCR',f"{r}%",
             'navy' if ok else 'red',
             '✅ Conforme' if ok else '❌','ok' if ok else 'bad'),
            (c4,'Ratio MCR',f"{rm}%",
             '' if rm>=100 else 'red',
             '✅ OK' if rm>=100 else '⚠️ Sous MCR',
             'ok' if rm>=100 else 'bad'),
        ]:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{lbl}</div>
                  <div class="kpi-value">{val}</div>
                  <div class="kpi-delta {dcls}">
                    {delta}</div>
                </div>""", unsafe_allow_html=True)

        c_g1,c_g2 = st.columns(2)
        with c_g1:
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
        with c_g2:
            fig_bar = go.Figure(go.Bar(
                x=['Marché','Non-Vie',
                   'Contrepartie','Opérationnel'],
                y=[s.get('scr_marche',0),
                   s.get('scr_nv',0),
                   s.get('scr_contrepartie',0),
                   s.get('scr_operationnel',0)],
                marker_color=C['navy'],
                text=[f"{v/bscr*100:.1f}%"
                      for v in [
                          s.get('scr_marche',0),
                          s.get('scr_nv',0),
                          s.get('scr_contrepartie',0),
                          s.get('scr_operationnel',0)]],
                textposition='outside'))
            fig_bar.update_layout(
                title='SCR par module',height=300,
                paper_bgcolor='white',
                plot_bgcolor=C['light'],
                margin=dict(l=10,r=10,t=40,b=10))
            st.plotly_chart(fig_bar,
                            use_container_width=True)

        if rm < 100:
            st.markdown(
                f'<div class="alerte-red">'
                f'⚠️ <b>MCR non couvert :</b> '
                f'Ratio = {rm}% — MCR absolu EIOPA '
                f'= 2 500 000 € — Action corrective '
                f'immédiate (Art. 129 Dir. 2009/138/CE).'
                f'</div>',
                unsafe_allow_html=True)

    with tab4:
        st.markdown(
            '<div class="section-header">'
            '📋 IFRS 17 — PAA + BBA</div>',
            unsafe_allow_html=True)

        i   = DATA.get('ifrs17',{})
        paa = i.get('modele_paa',{})
        bba = i.get('modele_bba',{})
        lr  = paa.get('loss_ratio_pct',0)

        c1,c2,c3,c4 = st.columns(4)
        for col,lbl,val,cls in [
            (c1,'Insurance Revenue',
             f"{paa.get('insurance_revenue',0):,.0f} €",''),
            (c2,'Insurance Result',
             f"{paa.get('insurance_result',0):,.0f} €",'navy'),
            (c3,'Loss Ratio IFRS 17',f"{lr}%",
             '' if lr<70 else 'gold'),
            (c4,'CSM BBA',
             f"{bba.get('csm',0):,.0f} €",'gold'),
        ]:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{lbl}</div>
                  <div class="kpi-value"
                    style="font-size:1.1rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE BRANCHE VIE
# ══════════════════════════════════════════════════════════════
elif page == "💼 Branche Vie":

    st.markdown("## 💼 Branche Vie")
    tab1,tab2,tab3,tab4 = st.tabs([
        "💀 Tarification",
        "📊 Provisions Mathématiques",
        "🏛️ Solvabilité 2",
        "📋 IFRS 17 BBA"])

    with tab1:
        pm = DATA.get('pm_vie',{})
        cr = pm.get('contrat_reference',{})
        c1,c2,c3,c4 = st.columns(4)
        for col,lbl,val,cls in [
            (c1,'Prime nivelée',
             f"{cr.get('prime_nivelee',0)} €/an",''),
            (c2,'Capital assuré',
             f"{cr.get('capital_assure',0):,.0f} €",'navy'),
            (c3,'Taux technique',
             f"{cr.get('taux_technique',0)*100:.1f}%",'gold'),
            (c4,'Table mortalité','EEA 2019',''),
        ]:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{lbl}</div>
                  <div class="kpi-value"
                    style="font-size:1.1rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

    with tab2:
        pm = DATA.get('pm_vie',{})
        cr = pm.get('contrat_reference',{})
        pf = pm.get('portefeuille',{})
        c1,c2,c3,c4 = st.columns(4)
        for col,lbl,val,cls in [
            (c1,'PM maximale',
             f"{cr.get('pm_max',0):,.0f} €",''),
            (c2,'PM à t=10',
             f"{cr.get('pm_t10',0):,.0f} €",'navy'),
            (c3,'PM portefeuille',
             f"{pf.get('pm_totale',0):,.0f} €",'gold'),
            (c4,'Taux rachat',
             f"{pf.get('taux_rachat',0.05)*100:.1f}%",''),
        ]:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{lbl}</div>
                  <div class="kpi-value"
                    style="font-size:1.2rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

    with tab3:
        pm_v = DATA.get('pm_vie',{})
        pf_v = pm_v.get('portefeuille',{})
        pm_t = pf_v.get('pm_totale',763460)
        sv   = pm_t*0.10; sl = pm_t*0.15*0.25
        sr   = pm_t*0.05; sf = pm_t*0.03
        stot = (sv**2+sl**2+sr**2+sf**2)**0.5

        c1,c2,c3,c4 = st.columns(4)
        for col,lbl,val in [
            (c1,'SCR Mortalité',f"{sv:,.0f} €"),
            (c2,'SCR Longévité',f"{sl:,.0f} €"),
            (c3,'SCR Rachat',  f"{sr:,.0f} €"),
            (c4,'SCR Vie Total',f"{stot:,.0f} €"),
        ]:
            with col:
                st.markdown(f"""
                <div class="kpi-card">
                  <div class="kpi-label">{lbl}</div>
                  <div class="kpi-value"
                    style="font-size:1.1rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

    with tab4:
        i   = DATA.get('ifrs17',{})
        bba = i.get('modele_bba',{})
        c1,c2,c3,c4 = st.columns(4)
        for col,lbl,val,cls in [
            (c1,'FCF',
             f"{bba.get('fcf',0):,.0f} €",''),
            (c2,'Risk Adjustment',
             f"{bba.get('ra',0):,.0f} €",'navy'),
            (c3,'CSM',
             f"{bba.get('csm',0):,.0f} €",'gold'),
            (c4,'Passif initial',
             f"{bba.get('total_passif_init',0):,.0f} €",''),
        ]:
            with col:
                st.markdown(f"""
                <div class="kpi-card {cls}">
                  <div class="kpi-label">{lbl}</div>
                  <div class="kpi-value"
                    style="font-size:1.2rem;">{val}</div>
                </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE ALM
# ══════════════════════════════════════════════════════════════
elif page == "📈 ALM":

    st.markdown("## 📈 ALM — Gestion Actif-Passif")

    pm_v   = DATA.get('pm_vie',{})
    pf_v   = pm_v.get('portefeuille',{})
    passif = pf_v.get('pm_totale',763460)
    actif  = passif * 1.15
    dur_a, dur_p = 6.2, 9.8
    gap    = dur_a - dur_p

    c1,c2,c3,c4 = st.columns(4)
    for col,lbl,val,cls,delta,dcls in [
        (c1,'Duration Actif',f'{dur_a:.1f} ans',
         '','Obligations','ok'),
        (c2,'Duration Passif',f'{dur_p:.1f} ans',
         'navy','PM + provisions','ok'),
        (c3,'Gap Duration',f'{gap:.1f} ans',
         'red','⚠️ Exposition taux','warn'),
        (c4,'Couverture A/P',
         f'{actif/passif*100:.1f}%','','✅ OK','ok'),
    ]:
        with col:
            st.markdown(f"""
            <div class="kpi-card {cls}">
              <div class="kpi-label">{lbl}</div>
              <div class="kpi-value">{val}</div>
              <div class="kpi-delta {dcls}">
                {delta}</div>
            </div>""", unsafe_allow_html=True)

    chocs  = [-200,-100,-50,0,50,100,200]
    imp_a  = [actif*(-dur_a*c/10000) for c in chocs]
    imp_p  = [passif*(-dur_p*c/10000) for c in chocs]
    imp_n  = [a-p for a,p in zip(imp_a,imp_p)]

    fig_alm = go.Figure(go.Bar(
        x=[f'{c:+d}bp' for c in chocs],y=imp_n,
        marker_color=[C['danger'] if v<0
                      else C['success'] for v in imp_n],
        text=[f"{v:+,.0f}€" for v in imp_n],
        textposition='outside'))
    fig_alm.add_hline(y=0,line_color=C['navy'],
                       line_width=1.5)
    fig_alm.update_layout(
        title='Stress tests taux — Impact Fonds Propres',
        height=320,paper_bgcolor='white',
        plot_bgcolor=C['light'],
        margin=dict(l=10,r=10,t=40,b=10))
    st.plotly_chart(fig_alm,use_container_width=True)

# ══════════════════════════════════════════════════════════════
# PAGE AGENT IA — NIVEAUX 1-4
# ══════════════════════════════════════════════════════════════
elif page == "🤖 Agent IA":

    st.markdown("## 🤖 Agent Actuariel IA")
    st.markdown(
        "Questions libres — Recalcul temps réel — "
        "Niveaux 1 à 4")

    if not api_key:
        st.warning("Entrez votre clé API dans la sidebar.")
        st.stop()

    if 'hist_agent' not in st.session_state:
        st.session_state.hist_agent = []

    # Niveau badges
    col_b1,col_b2,col_b3,col_b4 = st.columns(4)
    for col,n,lbl,ex in [
        (col_b1,'1','Q&A','Quel est le ratio SCR ?'),
        (col_b2,'2','Recalcul',
         'Choc taux +200bp → SCR ?'),
        (col_b3,'3','Paramètre',
         'Change tail factor à 1.010'),
        (col_b4,'4','Rapport',
         'Génère rapport EN'),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:{C['navy']};
                border-radius:8px;padding:0.6rem;
                text-align:center;">
              <div style="color:{C['green']};
                  font-size:1.2rem;font-weight:700;">
                N{n}</div>
              <div style="color:white;font-size:0.75rem;
                  font-weight:600;">{lbl}</div>
              <div style="color:{C['silver']};
                  font-size:0.65rem;
                  font-style:italic;">{ex}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Questions rapides
    qs = [
        "Situation globale du portefeuille ?",
        "Simule choc actions -39% sur SCR",
        "Taux technique à 1% → impact PM vie ?",
        "Tail factor 1.010 → IBNR ?",
        "Fonds propres à 600k€ → ratio SCR ?",
        "Synthèse et recommandations prioritaires",
    ]
    cols_q = st.columns(3)
    for j,q in enumerate(qs):
        with cols_q[j%3]:
            if st.button(q[:32]+"...",
                         key=f"qa_{j}"):
                st.session_state.q_agent = q

    question = st.text_input(
        "Votre question :",
        value=st.session_state.get('q_agent',''),
        placeholder="Ex: Recalcule le SCR avec "
                    "un choc taux +100bp")

    if st.button("Envoyer ➤",
                 type="primary") and question:

        with st.spinner("Agent actuariel..."):

            # ── Détection niveau ──────────────────
            q_low = question.lower()

            def detecter_niv(q):
                if any(m in q for m in [
                        'rapport','report','génère',
                        'generate','pdf']):
                    return 4
                if any(m in q for m in [
                        'change','modifie','fixe',
                        'nouveau','remplace']):
                    return 3
                if any(m in q for m in [
                        'simule','recalcule','choc',
                        'stress','impact','calcule',
                        'si le','si la','si on']):
                    return 2
                return 1

            niveau = detecter_niv(q_low)

            # ── Extraction paramètres ─────────────
            params = {}
            if niveau >= 2:
                try:
                    cl_nlu = anthropic.Anthropic(
                        api_key=api_key)
                    r_nlu  = cl_nlu.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=200,
                        messages=[{"role":"user",
                            "content":
                            f'Extrais les paramètres '
                            f'numériques de : '
                            f'"{question}". '
                            f'Réponds UNIQUEMENT en JSON: '
                            f'{{"choc_taux_bp":null,'
                            f'"choc_actions_pct":null,'
                            f'"fonds_propres":null,'
                            f'"tail_factor":null,'
                            f'"taux_technique":null,'
                            f'"capital_assure":null,'
                            f'"duree_ans":null,'
                            f'"module":null}}'}])
                    txt = r_nlu.content[0].text
                    txt = txt.replace('```json',
                                      '').replace(
                        '```','').strip()
                    params = json.loads(txt)
                except:
                    params = {}

            # ── Recalcul ──────────────────────────
            recalcul = None
            module   = params.get('module','') or ''

            if niveau >= 2:
                # Auto-détection module
                if not module:
                    if any(m in q_low for m in [
                            'scr','solvabilité','ratio',
                            'capital','mcr']):
                        module = 'scr'
                    elif any(m in q_low for m in [
                            'ibnr','provision','tail',
                            'triangle','chain']):
                        module = 'ibnr'
                    elif any(m in q_low for m in [
                            'pm','vie','mortalité',
                            'taux technique']):
                        module = 'pm'
                    elif any(m in q_low for m in [
                            'alm','duration','gap']):
                        module = 'alm'
                    else:
                        module = 'scr'

                s  = DATA.get('scr',{})
                p  = DATA.get('prov',{})
                pm = DATA.get('pm_vie',{})

                if module == 'scr':
                    choc_t = params.get(
                        'choc_taux_bp',0) or 0
                    choc_a = params.get(
                        'choc_actions_pct',0) or 0
                    fp_new = params.get('fonds_propres')
                    mult_m = params.get(
                        'scr_marche_mult',1.0) or 1.0
                    mult_n = params.get(
                        'scr_nv_mult',1.0) or 1.0

                    s2 = copy.deepcopy(s)
                    if choc_t:
                        d = (s2.get('scr_marche',0)*
                             0.274*abs(choc_t)/100*0.035)
                        s2['scr_marche'] = (
                            s2.get('scr_marche',0)+d)
                    if choc_a:
                        d = (s2.get('scr_marche',0)*
                             0.451*abs(choc_a)/39)
                        s2['scr_marche'] = (
                            s2.get('scr_marche',0)+d)
                    s2['scr_marche'] = (
                        s2.get('scr_marche',0)*mult_m)
                    s2['scr_nv'] = (
                        s2.get('scr_nv',0)*mult_n)
                    s2['bscr'] = math.sqrt(
                        s2.get('scr_marche',0)**2 +
                        s2.get('scr_nv',0)**2 +
                        s2.get('scr_contrepartie',0)**2)
                    s2['scr_total'] = (
                        s2['bscr'] +
                        s2.get('scr_operationnel',0))
                    fp = fp_new or s2.get(
                        'fonds_propres',0)
                    s2['fonds_propres'] = fp
                    s2['ratio_scr_pct'] = round(
                        fp/s2['scr_total']*100,2)
                    s2['ratio_mcr_pct'] = round(
                        fp/2_500_000*100,2)
                    s2['variation_ratio_scr'] = round(
                        s2['ratio_scr_pct'] -
                        s.get('ratio_scr_pct',0),2)
                    recalcul = s2

                elif module == 'ibnr':
                    tf = params.get('tail_factor')
                    m_prov = p.get('methodes',{})
                    cl_base = m_prov.get(
                        'chain_ladder',0)
                    bf_base = m_prov.get(
                        'bornhuetter_ferguson',0)
                    cc_base = m_prov.get('cape_cod',0)
                    if tf:
                        ratio = tf / max(
                            DATA.get('cl',{}).get(
                                'tail_factor',1.005),
                            0.001)
                        cl_base *= ratio
                        bf_base *= ratio*0.7
                        cc_base *= ratio*0.6
                    be = (cl_base+bf_base+cc_base)/3
                    p90 = be * math.exp(
                        1.282*0.15-0.15**2/2)
                    recalcul = {
                        'chain_ladder':  round(cl_base),
                        'bornhuetter_ferguson':
                            round(bf_base),
                        'cape_cod':      round(cc_base),
                        'provision_retenue': round(be),
                        'provision_prudente':round(p90),
                        'variation_vs_base': round(
                            (be-p.get(
                                'provision_retenue',1))/
                            max(p.get(
                                'provision_retenue',1),
                                1)*100,2),
                    }

                elif module == 'pm':
                    taux = params.get('taux_technique')
                    cap  = params.get('capital_assure')
                    dur  = params.get('duree_ans')
                    cr   = pm.get(
                        'contrat_reference',{})
                    taux = taux if taux is not None \
                           else cr.get(
                               'taux_technique',0.025)
                    cap  = cap or cr.get(
                        'capital_assure',200000)
                    dur  = dur or cr.get(
                        'duree_ans',20)
                    v    = 1/(1+max(taux,0.001))
                    pms  = []
                    for t_i in range(dur+1):
                        dr = max(dur-t_i,0)
                        ann = ((1-v**dr)/taux
                               if dr>0 and taux>0.001
                               else 0)
                        pms.append(max(
                            cap*0.003*ann*0.8,0))
                    pm_max = max(pms) if pms else 0
                    ann_t  = ((1-v**dur)/taux
                              if taux>0.001 else dur)
                    prime  = cap*0.003/max(ann_t,0.001)
                    recalcul = {
                        'prime_nivelee': round(prime,2),
                        'pm_max':        round(pm_max,2),
                        't_max':         pms.index(pm_max)
                                         if pms else 0,
                        'pm_t10':        round(pms[10],2)
                                         if len(pms)>10
                                         else 0,
                        'taux_technique':taux,
                        'variation_vs_base': round(
                            (pm_max-cr.get('pm_max',1))/
                            max(cr.get('pm_max',1),1)*100,
                            2),
                    }

                elif module == 'alm':
                    choc = params.get(
                        'choc_taux_bp',100) or 100
                    pf_v = pm.get('portefeuille',{})
                    pas  = pf_v.get('pm_totale',763460)
                    act  = pas*1.15
                    ia   = act*(-dur_a*choc/10000) \
                           if 'dur_a' in dir() \
                           else act*(-6.2*choc/10000)
                    ip   = pas*(-9.8*choc/10000)
                    recalcul = {
                        'choc_bp':       choc,
                        'impact_actif':  round(ia),
                        'impact_passif': round(ip),
                        'impact_net_fp': round(ia-ip),
                        'pct_fp': round(
                            abs(ia-ip)/max(
                                s.get('fonds_propres',
                                      480000),1)*100,2),
                    }

            # ── Réponse Claude ────────────────────
            s  = DATA.get('scr',{})
            p  = DATA.get('prov',{})
            ir = DATA.get('ifrs17',{})
            pm = DATA.get('pm_vie',{})
            g  = DATA.get('glm_g',{})
            ml = DATA.get('ml_v2',{})

            ctx = f"""
Portefeuille ActuarIA v2.0 :
Modèle={ml.get('modele_retenu')},
Gini={ml.get('gini_retenu')},
Prime={g.get('prime_pure_moy')}€,
CL={p.get('methodes',{}).get('chain_ladder')}€,
BE={p.get('provision_retenue')}€,
P90={p.get('provision_prudente')}€,
SCR={s.get('scr_total')}€,
RatioSCR={s.get('ratio_scr_pct')}%,
RatioMCR={s.get('ratio_mcr_pct')}%,
LR={ir.get('modele_paa',{}).get('loss_ratio_pct')}%,
CSM={ir.get('modele_bba',{}).get('csm')}€,
PMmax={pm.get('contrat_reference',{}).get('pm_max')}€
"""
            ctx_rc = ""
            if recalcul:
                ctx_rc = (f"\nRECALCUL effectué "
                          f"(module={module}) :"
                          f"\n{json.dumps(recalcul,indent=2)}")

            hist_msgs = []
            for h in st.session_state.hist_agent[-3:]:
                hist_msgs.append({
                    "role":"user",
                    "content":h['q']})
                hist_msgs.append({
                    "role":"assistant",
                    "content":h['r']})
            hist_msgs.append({
                "role":"user",
                "content":question})

            cl_resp = anthropic.Anthropic(
                api_key=api_key)
            resp = cl_resp.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=700,
                system=(
                    f"Actuaire senior EU. "
                    f"Données: {ctx}{ctx_rc}\n"
                    f"Niveau {niveau}. "
                    f"Réponse pro en français, "
                    f"chiffres exacts, refs réglementaires, "
                    f"4-5 paragraphes."),
                messages=hist_msgs)

            reponse = resp.content[0].text
            st.session_state.hist_agent.append({
                'q': question,
                'r': reponse,
                'niv': niveau,
                'rc': recalcul,
                'h': datetime.now().strftime('%H:%M'),
            })
            if 'q_agent' in st.session_state:
                del st.session_state.q_agent

    # Historique
    for msg in reversed(
            st.session_state.hist_agent):
        st.markdown(
            f"**❓ {msg['q']}** "
            f"<span style='background:{C['navy']};"
            f"color:{C['green']};padding:2px 8px;"
            f"border-radius:10px;font-size:0.7rem;"
            f"margin-left:8px;'>N{msg['niv']}</span>"
            f" <span style='color:#A0AEC0;"
            f"font-size:0.72rem;'>{msg['h']}</span>",
            unsafe_allow_html=True)

        st.markdown(
            f'<div class="agent-msg">'
            f'{msg["r"]}</div>',
            unsafe_allow_html=True)

        if msg.get('rc'):
            rc = msg['rc']
            items_html = ""
            for k,v in rc.items():
                if k == 'variation_vs_base' or \
                   k == 'variation_ratio_scr':
                    items_html += (
                        f"<b>📈 Variation : "
                        f"{v:+.2f}%</b><br>")
                elif isinstance(v,(int,float)) and \
                     abs(v)>100:
                    items_html += (
                        f"{k} : {v:,.0f} €<br>")
                elif isinstance(v,float):
                    items_html += (
                        f"{k} : {v:.4f}<br>")
                else:
                    items_html += (
                        f"{k} : {v}<br>")
            st.markdown(
                f'<div class="recalcul-box">'
                f'📊 <b>Recalcul effectué</b><br>'
                f'{items_html}</div>',
                unsafe_allow_html=True)

        st.markdown("---")

# ══════════════════════════════════════════════════════════════
# PAGE UPLOAD DONNÉES
# ══════════════════════════════════════════════════════════════
elif page == "📤 Upload Données":

    st.markdown("## 📤 Upload Données Client")

    # ── Sélection méthode ─────────────────────────
    methode = st.radio(
        "Méthode de chargement",
        ["📁 Upload fichier (PC)",
         "🔗 URL directe (REST/Drive)"],
        horizontal=True)

    if methode == "📁 Upload fichier (PC)":

        st.markdown(
            '<div class="upload-zone">'
            '📁 Glissez votre fichier ici<br>'
            '<small>Excel (.xlsx), CSV, '
            'Parquet (.parquet), JSON</small>'
            '</div>',
            unsafe_allow_html=True)

        fichier = st.file_uploader(
            "Choisir un fichier",
            type=['xlsx','xls','csv',
                  'parquet','json'],
            label_visibility="collapsed")

        if fichier:
            with st.spinner("Analyse en cours..."):
                try:
                    # Lecture
                    ext = fichier.name.split(
                        '.')[-1].lower()
                    if ext in ['xlsx','xls']:
                        df = pd.read_excel(fichier)
                    elif ext == 'csv':
                        for sep in [',',';','\t']:
                            try:
                                fichier.seek(0)
                                df = pd.read_csv(
                                    fichier, sep=sep)
                                if len(df.columns)>2:
                                    break
                            except:
                                continue
                    elif ext == 'parquet':
                        df = pd.read_parquet(fichier)
                    elif ext == 'json':
                        df = pd.read_json(fichier)

                    # Stats de base
                    c1,c2,c3,c4 = st.columns(4)
                    with c1:
                        st.metric("Lignes",
                                  f"{len(df):,}")
                    with c2:
                        st.metric("Colonnes",
                                  len(df.columns))
                    with c3:
                        # Détection branche
                        cols_low = [
                            c.lower()
                            for c in df.columns]
                        is_vie = any(
                            m in ' '.join(cols_low)
                            for m in [
                                'pm','vie','mortalite',
                                'rente','epargne'])
                        branche = ('VIE'
                                   if is_vie
                                   else 'IARD')
                        st.metric("Branche détectée",
                                  branche)
                    with c4:
                        # Score qualité simplifié
                        cols_oblig = {
                            'IARD': ['id_contrat',
                                     'produit',
                                     'prime_pure_eur',
                                     'nb_sinistres'],
                            'VIE':  ['id_contrat',
                                     'pm_prospective_eur',
                                     'type_contrat'],
                        }[branche]
                        score = sum(
                            1 for c in cols_oblig
                            if any(c in col.lower()
                                   for col in
                                   df.columns)
                        ) / len(cols_oblig) * 100
                        st.metric("Score qualité",
                                  f"{score:.0f}%")

                    # Aperçu
                    st.markdown(
                        '<div class="section-header">'
                        'Aperçu des données</div>',
                        unsafe_allow_html=True)
                    st.dataframe(
                        df.head(10),
                        use_container_width=True)

                    # Mapping colonnes
                    st.markdown(
                        '<div class="section-header">'
                        'Mapping colonnes</div>',
                        unsafe_allow_html=True)

                    schema_ref = {
                        'IARD': ['ID_Contrat',
                                 'Produit',
                                 'Annee_Souscription',
                                 'Prime_Pure_EUR',
                                 'Nb_Sinistres',
                                 'Montant_Sinistres_EUR'],
                        'VIE':  ['ID_Contrat',
                                 'Type_Contrat',
                                 'Age_Souscription',
                                 'PM_Prospective_EUR',
                                 'Taux_Technique'],
                    }[branche]

                    mapping_affiche = {}
                    for col_ref in schema_ref:
                        # Recherche correspondance
                        match = next(
                            (c for c in df.columns
                             if col_ref.lower() in
                             c.lower() or
                             c.lower() in
                             col_ref.lower()),
                            None)
                        mapping_affiche[col_ref] = (
                            match or '❓ Non trouvé')

                    df_map = pd.DataFrame(
                        list(mapping_affiche.items()),
                        columns=['Colonne ActuarIA',
                                 'Colonne Fichier'])
                    df_map['Statut'] = df_map[
                        'Colonne Fichier'].apply(
                        lambda x: '✅'
                        if '❓' not in str(x)
                        else '❓')
                    st.dataframe(df_map,
                                 use_container_width=True)

                    # Stats actuarielles
                    st.markdown(
                        '<div class="section-header">'
                        'Statistiques actuarielles'
                        '</div>',
                        unsafe_allow_html=True)
                    st.dataframe(
                        df.describe().round(2),
                        use_container_width=True)

                    if score >= 80:
                        st.markdown(
                            '<div class="alerte-green">'
                            '✅ <b>Données acceptées</b>'
                            ' — Prêtes pour analyse '
                            'dans ActuarIA v2.0.'
                            '</div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            f'<div class="alerte-red">'
                            f'⚠️ <b>Score {score:.0f}%</b>'
                            f' — Vérifiez les colonnes '
                            f'manquantes.'
                            f'</div>',
                            unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Erreur : {e}")

    else:  # URL REST
        url = st.text_input(
            "URL du fichier",
            placeholder="https://... ou "
                        "chemin/vers/fichier.csv")
        if st.button("Charger depuis URL") and url:
            st.info(
                "Fonctionnalité disponible en "
                "environnement local avec "
                "accès réseau.")

# ══════════════════════════════════════════════════════════════
# PAGE RAPPORTS
# ══════════════════════════════════════════════════════════════
elif page == "📄 Rapports":

    st.markdown("## 📄 Rapports Professionnels")

    st.markdown(f"""
    <div class="alerte-green">
      <b>Configuration</b> —
      Société : <b>{nom_societe or 'Non renseigné'}</b> |
      Actuaire : <b>{nom_actuaire or 'Non renseigné'}</b> |
      Langue : <b>{langue_code}</b> |
      {classification}
    </div>""", unsafe_allow_html=True)

    if not nom_societe or not nom_actuaire:
        st.warning(
            "⚠️ Renseignez **Société** et **Actuaire** "
            "dans la sidebar pour activer les rapports.")

    rapports_def = [
        ("🏢","Rapport Direction Générale",
         "Synthèse 10 pages — graphiques PowerBI — "
         "commentaires ORSA",
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
         "Rapport complet toutes branches",
         "ACPR · Commissaires aux comptes"),
    ]

    for i,(icon,titre,desc,public) in enumerate(
            rapports_def):
        c1,c2 = st.columns([4,1])
        with c1:
            st.markdown(f"""
            <div style="background:white;
                border-radius:9px;
                padding:0.9rem 1.1rem;
                border-left:4px solid {C['navy']};
                margin-bottom:0.7rem;
                box-shadow:0 1px 4px
                rgba(0,0,0,0.06);">
              <strong style="color:{C['navy']};">
                {icon} {titre}</strong>
              <div style="color:#4A5568;
                  font-size:0.8rem;
                  margin-top:0.2rem;">{desc}</div>
              <div style="color:#A0AEC0;
                  font-size:0.7rem;
                  margin-top:0.1rem;">{public}</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            if (nom_societe and nom_actuaire
                    and PDF_DISPONIBLE):
                if st.button(
                        "⚙️ Générer PDF",
                        key=f"gen_{i}"):
                    with st.spinner(
                            f"Génération {langue_code}"
                            f"..."):
                        try:
                            pdf_bytes = (
                                generer_pdf_streamlit(
                                    data=DATA,
                                    nom_societe=(
                                        nom_societe),
                                    nom_actuaire=(
                                        nom_actuaire),
                                    classification=(
                                        classification),
                                    langue=langue_code))
                            nom_pdf = (
                                f"Rapport_DG_"
                                f"{langue_code}_"
                                f"{nom_societe.replace(' ','_')}_"
                                f"{datetime.now().strftime('%Y%m%d')}"
                                f".pdf")
                            st.success(
                                f"✅ PDF généré — "
                                f"{len(pdf_bytes)/1e6:.1f}"
                                f" Mo")
                            st.download_button(
                                label=(
                                    f"📥 Télécharger "
                                    f"{nom_pdf}"),
                                data=pdf_bytes,
                                file_name=nom_pdf,
                                mime="application/pdf",
                                key=f"dl_{i}")
                        except Exception as e_pdf:
                            st.error(
                                f"Erreur PDF : "
                                f"{e_pdf}")
            else:
                st.markdown(
                    f'<div style="background:'
                    f'#F0F4FF;border-radius:7px;'
                    f'padding:0.5rem;text-align:center;'
                    f'font-size:0.75rem;'
                    f'color:#718096;">'
                    f'Phase 14 Colab</div>',
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.info(
        "💡 Pour tous les rapports (IARD, Vie, ALM) "
        "utilisez le notebook Phase14_Rapports_PDF.ipynb.")


# ── Footer ────────────────────────────────────────────────────
st.markdown(f"""
<div class="footer">
  ActuarIA v2.0 — Actuarial Intelligence<br>
  IARD · Vie · S2 · IFRS 17 · ALM · Agent IA v4<br>
  © {datetime.now().year} —
  {classification} —
  {nom_societe or 'Mode démo'}
</div>""", unsafe_allow_html=True)
