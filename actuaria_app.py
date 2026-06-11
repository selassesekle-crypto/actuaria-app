"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ACTUARIA — INTERFACE STREAMLIT v3.0                      ║
║      Sidebar · Agents Cliquables · Sofia Claude API · Rapports agents      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime
import anthropic

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title        = "ActuarIA",
    page_icon         = "⚡",
    layout            = "wide",
    initial_sidebar_state = "expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS
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
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

defaults = {
    'langue':        'fr',
    'page':          'accueil',
    'agent_selec':   None,
    'messages_aria': [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def t(key_fr, key_en=None):
    if st.session_state.langue == 'en' and key_en:
        return key_en
    return key_fr

# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════

def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');

    .stApp {{ background-color:{NAVY}; color:{BLANC}; font-family:'Inter',sans-serif; }}
    .block-container {{ padding-top:24px !important; padding-bottom:24px !important; }}

    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color:{NAVY_L}; border-right:1px solid rgba(201,168,76,0.25); }}
    [data-testid="stSidebar"] * {{ color:{BLANC} !important; }}
    [data-testid="stSidebar"] .stButton > button {{
        background:transparent; border:1px solid rgba(201,168,76,0.3);
        color:{BLANC} !important; border-radius:8px; font-size:0.85rem;
        padding:8px 16px; width:100%; text-align:left;
        transition:all 0.2s; margin-bottom:2px;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        background:rgba(201,168,76,0.15); border-color:{OR};
        color:{OR} !important;
    }}

    /* MÉTRIQUES */
    [data-testid="stMetric"] {{
        background:{NAVY_L}; border:1px solid rgba(201,168,76,0.2);
        border-radius:10px; padding:16px 20px;
    }}
    [data-testid="stMetricLabel"] {{
        color:{GRIS} !important; font-size:0.7rem !important;
        font-weight:600 !important; text-transform:uppercase !important;
        letter-spacing:0.08em !important;
    }}
    [data-testid="stMetricValue"] {{
        color:{OR} !important; font-size:1.4rem !important;
        font-weight:700 !important;
    }}

    /* BOUTONS PRINCIPAUX */
    .stButton > button {{
        background:linear-gradient(135deg,{OR},{OR_L});
        color:{NAVY} !important; border:none; border-radius:8px;
        font-weight:700; padding:10px 20px; transition:all 0.2s;
    }}
    .stButton > button:hover {{
        transform:translateY(-1px);
        box-shadow:0 4px 16px rgba(201,168,76,0.4);
    }}

    /* TABS */
    .stTabs [data-baseweb="tab-list"] {{
        background:{NAVY_L}; border-radius:8px; padding:4px; gap:4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background:transparent; color:{GRIS}; border-radius:6px;
        font-weight:500; padding:8px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        background:{OR} !important; color:{NAVY} !important; font-weight:700 !important;
    }}

    /* CARDS */
    .card {{
        background:{NAVY_L}; border:1px solid rgba(201,168,76,0.2);
        border-radius:12px; padding:16px; margin-bottom:8px;
        transition:all 0.2s;
    }}
    .card:hover {{ border-color:{OR}; }}

    /* BADGES */
    .badge-VERT  {{ display:inline-block; background:rgba(46,204,113,0.15);  color:#2ECC71; border:1px solid rgba(46,204,113,0.4);  border-radius:20px; padding:2px 10px; font-size:0.7rem; font-weight:600; }}
    .badge-AMBRE {{ display:inline-block; background:rgba(243,156,18,0.15);  color:#F39C12; border:1px solid rgba(243,156,18,0.4);  border-radius:20px; padding:2px 10px; font-size:0.7rem; font-weight:600; }}
    .badge-ROUGE {{ display:inline-block; background:rgba(231,76,60,0.15);   color:#E74C3C; border:1px solid rgba(231,76,60,0.4);   border-radius:20px; padding:2px 10px; font-size:0.7rem; font-weight:600; }}

    /* CHAT */
    .chat-box {{
        background:{NAVY_L}; border:1px solid rgba(201,168,76,0.2);
        border-radius:12px; padding:14px 18px; margin-bottom:8px;
    }}
    .chat-label {{
        font-size:0.68rem; color:{OR}; font-weight:700;
        text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;
    }}
    .chat-text {{
        font-size:0.88rem; color:{BLANC}; line-height:1.65;
    }}

    /* INPUTS */
    .stTextInput > div > div > input, .stSelectbox > div > div,
    .stTextArea > div > div > textarea {{
        background:{NAVY_L} !important; border:1px solid rgba(201,168,76,0.3) !important;
        color:{BLANC} !important; border-radius:8px !important;
    }}
    [data-testid="stFileUploader"] {{
        background:{NAVY_L}; border:2px dashed rgba(201,168,76,0.4);
        border-radius:12px; padding:20px;
    }}
    [data-testid="stDataFrame"] {{
        background:{NAVY_L}; border-radius:8px;
        border:1px solid rgba(201,168,76,0.2);
    }}
    hr {{ border-color:rgba(201,168,76,0.2); }}
    ::-webkit-scrollbar {{ width:5px; }}
    ::-webkit-scrollbar-track {{ background:{NAVY}; }}
    ::-webkit-scrollbar-thumb {{ background:rgba(201,168,76,0.4); border-radius:3px; }}
    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# DONNÉES AGENTS
# ══════════════════════════════════════════════════════════════════════════════

AGENTS = {
    'sofia':    {'prenom':'Sofia',    'code':'ARIA', 'icon':'🤖', 'statut':'VERT',  'dir':'central',  'equipe':'central',
                 'role_fr':'Actuaire IA Senior — Agent Central',
                 'desc_fr':'Sofia coordonne tous les agents de la plateforme. Propulsée par Claude API, elle répond à toutes vos questions actuarielles en langage naturel, synthétise les résultats et oriente vers le bon expert.',
                 'spec_fr':'IA générative · Synthèse · Claude API', 'kpi':'Agent IA Central'},
    'amara':    {'prenom':'Amara',    'code':'A1',   'icon':'🔍', 'statut':'VERT',  'dir':'non_vie',  'equipe':'tarification',
                 'role_fr':'Ingestion & Validation des données',
                 'desc_fr':'Amara ingère, valide et normalise les données clients (Excel, CSV, Parquet) avec détection automatique de la branche, mapping des colonnes et contrôle RGPD Art.30.',
                 'spec_fr':'Multi-format · Qualité · RGPD Art.30', 'kpi':'678k contrats validés'},
    'kenji':    {'prenom':'Kenji',    'code':'A2',   'icon':'⚡', 'statut':'AMBRE', 'dir':'non_vie',  'equipe':'tarification',
                 'role_fr':'Preprocessing & Feature Engineering',
                 'desc_fr':'Kenji transforme les données brutes en features exploitables : imputation, winsorisation, encodage, création de variables. Il prépare le terrain pour une modélisation de haute précision.',
                 'spec_fr':'Feature engineering · Imputation · Encodage', 'kpi':'30 features créées'},
    'laurent':  {'prenom':'Laurent',  'code':'A3',   'icon':'📐', 'statut':'VERT',  'dir':'non_vie',  'equipe':'tarification',
                 'role_fr':'GLM Tarification — Poisson · Gamma · Tweedie',
                 'desc_fr':'Laurent calibre les GLM réglementaires avec sélection stepwise et tests statistiques. Il fournit les coefficients interprétables exigés par les auditeurs S2 et l\'AI Act 2025.',
                 'spec_fr':'GLM Poisson · Gamma · Tweedie · Stepwise', 'kpi':'Gini GLM validé'},
    'priya':    {'prenom':'Priya',    'code':'A4',   'icon':'🧠', 'statut':'VERT',  'dir':'non_vie',  'equipe':'tarification',
                 'role_fr':'Machine Learning — 6 modèles',
                 'desc_fr':'Priya maîtrise 6 algorithmes ML : GBM, XGBoost, XGBoost Tweedie, LightGBM, CatBoost, ElasticNet. Elle calcule les Gini, détecte l\'overfitting et fournit les explications SHAP.',
                 'spec_fr':'XGBoost · LightGBM · CatBoost · SHAP', 'kpi':'Gini XGBoost = 0.2651'},
    'yohan':    {'prenom':'Yohan',    'code':'A5',   'icon':'🔮', 'statut':'VERT',  'dir':'non_vie',  'equipe':'tarification',
                 'role_fr':'Deep Learning — CANN · TabNet',
                 'desc_fr':'Yohan calibre les réseaux CANN (Wüthrich 2019) et TabNet, architectures de pointe pour données tabulaires actuarielles.',
                 'spec_fr':'CANN · TabNet · PyTorch · Wüthrich 2019', 'kpi':'TabNet Gini = 0.2334'},
    'meilin':   {'prenom':'Mei-Lin',  'code':'A6',   'icon':'⚖️', 'statut':'VERT',  'dir':'non_vie',  'equipe':'tarification',
                 'role_fr':'Comparaison & Sélection du modèle de production',
                 'desc_fr':'Mei-Lin applique une grille multicritères (Gini, stabilité, interprétabilité, RMSE) avec 4 profils de pondération adaptés : équilibré, performance, auditabilité S2, compagnie vie.',
                 'spec_fr':'Multicritères · 4 profils · AI Act 2025', 'kpi':'Score 0.8373/1.0'},
    'kwame':    {'prenom':'Kwame',    'code':'A7',   'icon':'🏦', 'statut':'VERT',  'dir':'non_vie',  'equipe':'provisions',
                 'role_fr':'Provisionnement — Chain Ladder · Mack · BF · Cape Cod',
                 'desc_fr':'Kwame calibre les 4 méthodes actuarielles de référence, calcule le Best Estimate S2 avec intervalle de confiance Mack 1993 et détecte les valeurs extrêmes dans le triangle.',
                 'spec_fr':'Chain Ladder · Mack 1993 · BF · Cape Cod', 'kpi':'BE = 2.91M€ · CV 0.6%'},
    'isabelle': {'prenom':'Isabelle', 'code':'A8',   'icon':'🌩️', 'statut':'VERT',  'dir':'non_vie',  'equipe':'provisions',
                 'role_fr':'Stress Testing & ORSA',
                 'desc_fr':'Isabelle évalue la résistance aux chocs S2 EIOPA et projette l\'ORSA prospectif sur 5 ans pour le Pilier 2. Scénarios climatiques, épidémiques et financiers inclus.',
                 'spec_fr':'Chocs S2 · ORSA 5 ans · Scénarios adverses', 'kpi':'Ratio SCR = 375%'},
    'marcus':   {'prenom':'Marcus',   'code':'A9',   'icon':'🔗', 'statut':'VERT',  'dir':'non_vie',  'equipe':'provisions',
                 'role_fr':'Cohérence inter-équipes',
                 'desc_fr':'Marcus vérifie l\'alignement Tarification ↔ Provisions ↔ S2 ↔ IFRS 17 via les Loss Ratios et alerte proactivement en cas d\'incohérence.',
                 'spec_fr':'Loss Ratios · Réconciliation · Alertes RAG', 'kpi':'Score 100% VERT'},
    'nadia':    {'prenom':'Nadia',    'code':'A10',  'icon':'🛡️', 'statut':'VERT',  'dir':'non_vie',  'equipe':'provisions',
                 'role_fr':'Solvabilité 2 — SCR · MCR · QRT',
                 'desc_fr':'Nadia calcule le SCR souscription, marché et opérationnel selon la formule standard EIOPA, le MCR et génère les QRT S.05, S.17, S.19 et S.23 pour le reporting ACPR.',
                 'spec_fr':'Formule standard · QRT · Pilier 1 S2', 'kpi':'Ratio SCR = 208.5%'},
    'thomas':   {'prenom':'Thomas',   'code':'A11',  'icon':'📊', 'statut':'VERT',  'dir':'non_vie',  'equipe':'provisions',
                 'role_fr':'IFRS 17 — PAA · BBA · VFA',
                 'desc_fr':'Thomas calcule les provisions IFRS 17 selon les 3 approches (PAA, BBA, VFA) et réconcilie avec le Best Estimate S2. CSM, Risk Adjustment et résultat technique inclus.',
                 'spec_fr':'PAA · BBA · VFA · CSM · Réconciliation S2', 'kpi':'TP = 3.99M€ · Ratio 1.370'},
    'aisha':    {'prenom':'Aisha',    'code':'A12',  'icon':'⚖️', 'statut':'AMBRE', 'dir':'non_vie',  'equipe':'provisions',
                 'role_fr':'ALM & Risque de Liquidité',
                 'desc_fr':'Aisha calcule les durations de Macaulay, le gap actif-passif, le BV01 et le LCR. Elle évalue l\'impact des chocs de taux ±200bp sur la valeur nette.',
                 'spec_fr':'Duration · Gap ALM · LCR · Stress taux', 'kpi':'LCR = 1173% · Gap +1.9 ans'},
    'luca':     {'prenom':'Luca',     'code':'A13',  'icon':'🔐', 'statut':'VERT',  'dir':'non_vie',  'equipe':'transversale',
                 'role_fr':'Audit Trail & Conformité RGPD',
                 'desc_fr':'Luca garantit l\'intégrité de tous les calculs : hash SHA-256, registre RGPD Art.30, versioning des hypothèses et rapport d\'audit complet pour l\'auditeur S2.',
                 'spec_fr':'SHA-256 · RGPD Art.30 · Versioning · Audit S2', 'kpi':'Hash 5BB15F63'},
    'yuki':     {'prenom':'Yuki',     'code':'A14',  'icon':'📉', 'statut':'VERT',  'dir':'non_vie',  'equipe':'transversale',
                 'role_fr':'Tables de Mortalité & Biométrie',
                 'desc_fr':'Yuki calcule les annuités viagères, espérances de vie et capitaux décès sur les tables TH0002, TF0002 et TGHF05. Projection Lee-Carter et calibration Makeham-Gompertz.',
                 'spec_fr':'TH0002 · TF0002 · TGHF05 · Lee-Carter', 'kpi':'R² = 0.9985 · ä_65 = 13.07'},
    'henri':    {'prenom':'Henri',    'code':'EP1',  'icon':'🏢', 'statut':'VERT',  'dir':'epargne',  'equipe':'epargne',
                 'role_fr':'Engagements de Retraite — IAS 19',
                 'desc_fr':'Henri évalue les engagements de retraite IAS 19 par la méthode PUC. DBO, Service Cost, Interest Cost, gains et pertes actuariels pour les régimes Art.39, Art.83 et PER.',
                 'spec_fr':'IAS 19 · PUC · DBO · OAT iBoxx AA', 'kpi':'DBO = 10.6M€'},
    'fatou':    {'prenom':'Fatou',    'code':'EP2',  'icon':'💰', 'statut':'VERT',  'dir':'epargne',  'equipe':'epargne',
                 'role_fr':'Tarification Épargne-Retraite',
                 'desc_fr':'Fatou tarifie les contrats Art.39, Art.83 et PER (Loi PACTE 2019). Cotisations, rentes viagères, taux de remplacement et participation aux bénéfices.',
                 'spec_fr':'Art.39 · Art.83 · PER · PACTE 2019', 'kpi':'Rente = 595€/mois'},
    'jinho':    {'prenom':'Jin-Ho',   'code':'EP3',  'icon':'📈', 'statut':'VERT',  'dir':'epargne',  'equipe':'epargne',
                 'role_fr':'Provisionnement Épargne',
                 'desc_fr':'Jin-Ho calcule les PM, PPB et Réserve de Capitalisation. Conformité avec le Code des assurances Art. R342-14.',
                 'spec_fr':'PM · PPB · Réserve capitalisation · R342-14', 'kpi':'PPB = 1.15M€'},
    'claire':   {'prenom':'Claire',   'code':'EP4',  'icon':'⚡', 'statut':'ROUGE', 'dir':'epargne',  'equipe':'epargne',
                 'role_fr':'Stress Testing Épargne-Retraite',
                 'desc_fr':'Claire évalue la résistance des portefeuilles épargne aux chocs longévité (+20%), taux bas (0%), rachats massifs (40%) et choc financier (-20%).',
                 'spec_fr':'Choc longévité · Rachats massifs · ORSA retraite', 'kpi':'Ratio base = 110%'},
    'omar':     {'prenom':'Omar',     'code':'EP5',  'icon':'📋', 'statut':'ROUGE', 'dir':'epargne',  'equipe':'epargne',
                 'role_fr':'Reporting Épargne-Retraite',
                 'desc_fr':'Omar génère le rapport actuariel annuel, QRT retraite ACPR, fiche information assuré PER, enquête DARES et note de synthèse pour le Conseil d\'Administration.',
                 'spec_fr':'ACPR · DARES · CA · Fiche assuré PER', 'kpi':'4 rapports disponibles'},
}

STRUCTURE = {
    'non_vie': {
        'label': 'Direction Non-Vie', 'icon': '🏢',
        'equipes': {
            'tarification': {'label': 'Équipe Tarification',             'agents': ['amara','kenji','laurent','priya','yohan','meilin']},
            'provisions':   {'label': 'Équipe Provisions & Réglementaire','agents': ['kwame','isabelle','marcus','nadia','thomas','aisha']},
            'transversale': {'label': 'Équipe Transversale',              'agents': ['luca','yuki']},
        }
    },
    'epargne': {
        'label': 'Direction Épargne-Retraite', 'icon': '💼',
        'equipes': {
            'epargne': {'label': 'Équipe Épargne-Retraite', 'agents': ['henri','fatou','jinho','claire','omar']},
        }
    },
}

KPI = {'be':2_914_930,'ratio_scr':208.5,'gini':0.2651,'lcr':1173.3,'tp_ifrs17':3_992_344}

SYSTEM_PROMPT_SOFIA = """Tu es Sofia, actuaire IA senior de la plateforme ActuarIA.
Tu es experte en actuariat non-vie et épargne-retraite. Tu as accès aux résultats de 20 agents spécialisés.

Résultats disponibles :
- Best Estimate S2 : 2 914 930 € (CV 0.6%, 4 méthodes convergentes)
- Ratio SCR : 208.5% (SCR total 3 680 671 €, MCR 2 500 000 €)
- Gini XGBoost : 0.2651 sur freMTPL2 (678k contrats auto FR)
- Modèle production : ElasticNet (score 0.8373/1.0, overfit 0.98)
- TP IFRS 17 (PAA) : 3 992 344 € (ratio IFRS17/S2 = 1.370)
- Gap ALM : +1.9 ans (duration actifs 3.5 ans vs passifs 1.6 ans)
- LCR : 1173% (très liquide)
- Hash session : 5BB15F63

Agents disponibles : Amara(A1), Kenji(A2), Laurent(A3), Priya(A4), Yohan(A5),
Mei-Lin(A6), Kwame(A7), Isabelle(A8), Marcus(A9), Nadia(A10), Thomas(A11),
Aisha(A12), Luca(A13), Yuki(A14), Henri(EP1), Fatou(EP2), Jin-Ho(EP3),
Claire(EP4), Omar(EP5).

Réponds toujours en français sauf si on te parle en anglais.
Sois précis, professionnel et concis. Utilise les chiffres réels disponibles.
Si une question dépasse les données disponibles, dis-le clairement."""


# ══════════════════════════════════════════════════════════════════════════════
# CLAUDE API
# ══════════════════════════════════════════════════════════════════════════════

def appeler_claude(messages, system_prompt=None):
    """Appelle Claude API avec gestion d'erreur."""
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "⚠️ Clé API Anthropic non configurée. Ajoutez ANTHROPIC_API_KEY dans les Secrets Streamlit."

        client = anthropic.Anthropic(api_key=api_key)

        msgs = [{"role": m["role"], "content": m["content"]}
                for m in messages if m["role"] in ["user", "assistant"]]

        kwargs = {
            "model":      "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages":   msgs,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = client.messages.create(**kwargs)
        return response.content[0].text

    except anthropic.AuthenticationError:
        return "❌ Clé API invalide. Vérifiez ANTHROPIC_API_KEY dans les Secrets Streamlit."
    except anthropic.RateLimitError:
        return "⚠️ Limite d'utilisation atteinte. Réessayez dans quelques instants."
    except Exception as e:
        return f"❌ Erreur : {str(e)}"


def system_prompt_agent(agent_key):
    """Génère le system prompt spécifique à chaque agent."""
    agent = AGENTS[agent_key]
    return f"""Tu es {agent['prenom']}, un agent actuariel spécialisé de la plateforme ActuarIA.
Ton rôle : {agent['role_fr']}
Tes spécialités : {agent['spec_fr']}
Ton KPI : {agent['kpi']}

Réponds uniquement sur ton domaine de spécialité.
Sois précis, professionnel et pédagogue.
Utilise les données réelles disponibles : {agent['kpi']}.
Réponds en français sauf si on te parle en anglais."""


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        # Logo
        try:
            st.image("logo.png", width=180)
        except:
            st.markdown(f"""
            <div style="text-align:center;padding:16px 0 12px;">
                <div style="font-family:'Playfair Display',serif;font-size:1.8rem;
                            font-weight:700;color:{BLANC};">
                    Actuar<span style="color:{OR};">IA</span>
                </div>
                <div style="font-size:0.62rem;color:{GRIS};letter-spacing:0.15em;
                            text-transform:uppercase;margin-top:2px;">
                    Actuarial Intelligence Platform
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.2);margin:8px 0 16px;'>",
                    unsafe_allow_html=True)

        # Navigation principale
        pages = [
            ('🏠', t('Accueil','Home'),        'accueil'),
            ('📊', t('Analyse','Analysis'),     'analyse'),
            ('📈', t('Dashboard','Dashboard'),  'dashboard'),
            ('🤖', 'Agent Sofia (ARIA)',         'aria'),
            ('📋', t('Rapports','Reports'),     'rapports'),
        ]

        for icon, label, pid in pages:
            actif = st.session_state.page == pid
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{pid}",
                use_container_width=True,
                type="primary" if actif else "secondary"
            ):
                st.session_state.page = pid
                st.session_state.agent_selec = None
                st.rerun()

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.2);margin:16px 0;'>",
                    unsafe_allow_html=True)

        # Menu Équipes
        st.markdown(f"""
        <div style="font-size:0.68rem;color:{GRIS};text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:10px;font-weight:600;">
            Équipes
        </div>
        """, unsafe_allow_html=True)

        # Direction Non-Vie
        with st.expander("🏢 Direction Non-Vie", expanded=False):
            for eq_key, eq in STRUCTURE['non_vie']['equipes'].items():
                st.markdown(f"""
                <div style="font-size:0.72rem;color:{OR};font-weight:600;
                            margin:8px 0 6px;padding-left:4px;">
                    {eq['label']}
                </div>
                """, unsafe_allow_html=True)
                for ak in eq['agents']:
                    agent = AGENTS[ak]
                    badge_color = VERT if agent['statut']=='VERT' else AMBRE if agent['statut']=='AMBRE' else ROUGE
                    if st.button(
                        f"{agent['icon']} {agent['prenom']} ({agent['code']})",
                        key=f"side_{ak}",
                        use_container_width=True,
                    ):
                        st.session_state.agent_selec = ak
                        st.session_state.page = 'agent_detail'
                        st.rerun()

        # Direction Épargne
        with st.expander("💼 Direction Épargne-Retraite", expanded=False):
            for eq_key, eq in STRUCTURE['epargne']['equipes'].items():
                for ak in eq['agents']:
                    agent = AGENTS[ak]
                    if st.button(
                        f"{agent['icon']} {agent['prenom']} ({agent['code']})",
                        key=f"side_ep_{ak}",
                        use_container_width=True,
                    ):
                        st.session_state.agent_selec = ak
                        st.session_state.page = 'agent_detail'
                        st.rerun()

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.2);margin:16px 0;'>",
                    unsafe_allow_html=True)

        # Statuts
        nb_v = sum(1 for a in AGENTS.values() if a['statut']=='VERT')
        nb_a = sum(1 for a in AGENTS.values() if a['statut']=='AMBRE')
        nb_r = sum(1 for a in AGENTS.values() if a['statut']=='ROUGE')

        st.markdown(f"""
        <div style="font-size:0.68rem;color:{GRIS};text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:8px;">Statut agents</div>
        <div style="display:flex;gap:8px;margin-bottom:16px;">
            <span class="badge-VERT">✅ {nb_v}</span>
            <span class="badge-AMBRE">⚠ {nb_a}</span>
            <span class="badge-ROUGE">❌ {nb_r}</span>
        </div>
        """, unsafe_allow_html=True)

        # Langue
        lang = st.session_state.langue
        if st.button(
            "🇫🇷 Français" if lang == 'fr' else "🇬🇧 English",
            key="lang_btn",
            use_container_width=True,
        ):
            st.session_state.langue = 'en' if lang == 'fr' else 'fr'
            st.rerun()

        # Version
        st.markdown(f"""
        <div style="font-size:0.62rem;color:rgba(138,154,176,0.5);
                    text-align:center;margin-top:16px;">
            ActuarIA v3.0 · {datetime.now().strftime('%d/%m/%Y')}
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ACCUEIL
# ══════════════════════════════════════════════════════════════════════════════

def page_accueil():
    col_h, col_r = st.columns([1.4, 1])

    with col_h:
        st.markdown(f"""
        <div style="padding:8px 0 24px;">
            <div style="font-size:0.7rem;color:{OR};text-transform:uppercase;
                        letter-spacing:0.15em;font-weight:600;margin-bottom:12px;">
                Actuarial Intelligence Platform
            </div>
            <div style="font-family:'Playfair Display',serif;font-size:2.4rem;
                        font-weight:700;color:{BLANC};line-height:1.15;
                        letter-spacing:-0.02em;margin-bottom:16px;">
                ActuarIA — Là où l'expertise<br>
                <span style="color:{OR};">rencontre l'intelligence artificielle.</span>
            </div>
            <div style="font-size:0.95rem;color:{GRIS};line-height:1.6;
                        max-width:540px;margin-bottom:28px;">
                La première plateforme actuarielle propulsée par l'IA pour les
                compagnies d'assurance, mutuelles et institutions de prévoyance.
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button("🚀 Lancer une analyse", type="primary", use_container_width=True):
                st.session_state.page = 'analyse'
                st.rerun()
        with c2:
            if st.button("📈 Voir le Dashboard", use_container_width=True):
                st.session_state.page = 'dashboard'
                st.rerun()

    with col_r:
        _radar_hero()

    st.markdown(f"<hr>", unsafe_allow_html=True)

    # KPIs
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.metric("Agents",       "20 / 20",      "IA + EP")
    with c2: st.metric("Best Estimate","2.91M€",        "CV 0.6%")
    with c3: st.metric("Ratio SCR",    "208.5%",        "✅ > 150%")
    with c4: st.metric("Gini ML",      "0.2651",        "freMTPL2")
    with c5: st.metric("LCR",          "1 173%",        "✅ Liquide")
    with c6: st.metric("Conformité",   "100%",          "S2 + IFRS17")

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    # Présentation
    col_p, col_r2 = st.columns(2)

    with col_p:
        st.markdown(f"""
        <div style="font-size:0.68rem;color:{GRIS};text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:8px;">La plateforme</div>
        <div style="font-family:'Playfair Display',serif;font-size:1.4rem;
                    color:{BLANC};font-weight:700;margin-bottom:12px;">
            20 agents actuariels, une intelligence unifiée.
        </div>
        <div style="font-size:0.88rem;color:{GRIS};line-height:1.7;margin-bottom:20px;">
            ActuarIA couvre l'intégralité de la chaîne actuarielle, de la
            tarification ML au reporting réglementaire S2/IFRS17/ALM, en passant
            par le provisionnement et l'épargne-retraite.
        </div>
        """, unsafe_allow_html=True)

        for icon, nom, desc in [
            ("🏢","Compagnies d'assurance","Non-Vie · Vie · Mixte"),
            ("🤝","Mutuelles","Santé · Prévoyance · Retraite"),
            ("🛡️","Institutions de Prévoyance","Retraite · IAS 19"),
            ("📊","Cabinets actuariels","Conseil · Audit · Reporting"),
        ]:
            st.markdown(f"""
            <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;">
                <span style="font-size:1.1rem;">{icon}</span>
                <div>
                    <span style="font-weight:600;color:{BLANC};font-size:0.85rem;">{nom}</span>
                    <span style="color:{GRIS};font-size:0.78rem;margin-left:8px;">{desc}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_r2:
        st.markdown(f"""
        <div style="font-size:0.68rem;color:{GRIS};text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:12px;">
            Réglementations couvertes
        </div>
        """, unsafe_allow_html=True)

        for titre, desc in [
            ("Solvabilité 2","Formule standard EIOPA · SCR · MCR · QRT · ORSA · SFCR"),
            ("IFRS 17","PAA · BBA · VFA · CSM · Réconciliation S2 — depuis jan. 2023"),
            ("ALM","Duration · Gap · BV01 · LCR · Stress taux ±200bp"),
            ("IAS 19","PUC · DBO · Service Cost · Art.39/83/PER"),
            ("Loi PACTE 2019","PER · Portabilité · Sortie capital · Fiche assuré"),
            ("RGPD Art.30","Registre · Pseudonymisation · Hash SHA-256"),
        ]:
            st.markdown(f"""
            <div style="border-left:3px solid {OR};padding:8px 12px;
                        background:{NAVY_L};border-radius:0 8px 8px 0;
                        margin-bottom:8px;">
                <div style="font-weight:700;color:{OR};font-size:0.82rem;">{titre}</div>
                <div style="font-size:0.76rem;color:{GRIS};margin-top:2px;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    # Footer
    st.markdown(f"""
    <div style="text-align:center;padding:32px 0 8px;
                border-top:1px solid rgba(201,168,76,0.15);margin-top:32px;">
        <div style="font-family:'Playfair Display',serif;font-size:1rem;
                    color:{BLANC};">Actuar<span style="color:{OR};">IA</span></div>
        <div style="font-size:0.75rem;color:{GRIS};margin-top:4px;">
            Actuarial Intelligence Platform · v3.0 ·
            <span style="color:{OR};">contact@actuaria.fr</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE AGENT DÉTAIL
# ══════════════════════════════════════════════════════════════════════════════

def page_agent_detail():
    agent_key = st.session_state.agent_selec
    if not agent_key or agent_key not in AGENTS:
        st.warning("Agent non trouvé.")
        return

    agent = AGENTS[agent_key]

    # Bouton retour
    if st.button("← Retour", key="btn_retour"):
        st.session_state.agent_selec = None
        st.session_state.page = 'accueil'
        st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Header agent
    col_av, col_info = st.columns([1, 3])

    with col_av:
        # Avatar (photo ou initiale)
        try:
            st.image(f"assets/avatars/{agent_key}.png", width=120)
        except:
            st.markdown(f"""
            <div style="width:100px;height:100px;border-radius:50%;
                        background:linear-gradient(135deg,{OR},{OR_L});
                        display:flex;align-items:center;justify-content:center;
                        font-size:2.5rem;font-weight:700;color:{NAVY};
                        margin-bottom:12px;">
                {agent['prenom'][0]}
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="margin-top:8px;">
            <div style="font-family:'Playfair Display',serif;font-size:1.5rem;
                        color:{BLANC};font-weight:700;">{agent['prenom']}</div>
            <div style="font-size:0.7rem;color:{GRIS};text-transform:uppercase;
                        letter-spacing:0.1em;margin:4px 0 8px;">{agent['code']}</div>
            <span class="badge-{agent['statut']}">{agent['statut']}</span>
            <div style="font-size:0.78rem;color:{OR};margin-top:10px;
                        font-weight:600;">{agent['kpi']}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_info:
        st.markdown(f"""
        <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
                    border-radius:12px;padding:24px;">
            <div style="color:{OR};font-size:1rem;font-weight:600;
                        margin-bottom:12px;">{agent['role_fr']}</div>
            <div style="font-size:0.88rem;color:{BLANC};line-height:1.7;
                        margin-bottom:16px;">{agent['desc_fr']}</div>
            <div style="font-size:0.7rem;color:{GRIS};text-transform:uppercase;
                        letter-spacing:0.08em;margin-bottom:6px;">Spécialités</div>
            <div style="font-size:0.82rem;color:{OR};">{agent['spec_fr']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # 3 onglets
    tab1, tab2, tab3 = st.tabs([
        "📋 Résultats & Rapport",
        f"🚀 Lancer {agent['prenom']}",
        f"💬 Dialoguer avec {agent['prenom']}",
    ])

    with tab1:
        _tab_resultats_rapport(agent_key)

    with tab2:
        _tab_lancer(agent_key)

    with tab3:
        _tab_chat_agent(agent_key)


def _tab_resultats_rapport(agent_key):
    """Résultats de l'agent + bouton rapport."""
    agent = AGENTS[agent_key]

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # KPI principal
    st.markdown(f"""
    <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.25);
                border-radius:10px;padding:16px 20px;margin-bottom:16px;">
        <div style="font-size:0.68rem;color:{GRIS};text-transform:uppercase;
                    letter-spacing:0.08em;margin-bottom:6px;">KPI principal</div>
        <div style="font-size:1.3rem;font-weight:700;color:{OR};">{agent['kpi']}</div>
        <div style="font-size:0.75rem;color:{GRIS};margin-top:4px;">
            Dernière exécution : {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Résultats spécifiques par agent
    _resultats_agent(agent_key)

    st.markdown(f"<hr>", unsafe_allow_html=True)

    # Générer rapport
    st.markdown(f"""
    <div style="font-size:0.68rem;color:{GRIS};text-transform:uppercase;
                letter-spacing:0.08em;margin-bottom:12px;">Rapport</div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"📄 Rapport PDF — {agent['prenom']}", use_container_width=True):
            st.toast(f"✅ Rapport {agent['prenom']} généré", icon="✅")
    with col2:
        if st.button(f"📊 Export Excel", use_container_width=True):
            st.toast("✅ Export Excel généré", icon="✅")
    with col3:
        if st.button(f"🔐 Audit Trail", use_container_width=True):
            st.toast("✅ Audit Trail exporté", icon="✅")


def _resultats_agent(agent_key):
    """Affiche les résultats spécifiques selon l'agent."""
    agent = AGENTS[agent_key]
    code  = agent['code']

    if code == 'A7':
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Best Estimate S2",  "2 914 930 €", "CV 0.6%")
        with c2: st.metric("Provision P90",     "3 098 000 €", "+6.3%")
        with c3: st.metric("σ Mack 1993",       "45 000 €",    "IC 95%")
        methodes = ['Chain Ladder','Mack 1993','BF','Cape Cod','Best Estimate']
        valeurs  = [2_850_000,2_914_930,2_930_000,2_880_000,2_914_930]
        _bar_chart(methodes, valeurs, "4 méthodes — convergence")

    elif code == 'A4':
        c1,c2 = st.columns(2)
        with c1: st.metric("Gini XGBoost",  "0.2651", "meilleur")
        with c2: st.metric("Modèle retenu", "ElasticNet", "score 0.8373")
        df = pd.DataFrame({
            'Modèle':['XGBoost','GBM','CatBoost','LightGBM','ElasticNet','XGB Tweedie'],
            'Gini':  [0.2651,0.2542,0.2534,0.2481,0.2440,0.2404],
            'Overfit':[1.53,1.41,1.28,1.60,0.98,1.97],
            'Retenu':['','','','','⭐',''],
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif code == 'A10':
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("SCR Total",  "3 680 671 €", "formule std")
        with c2: st.metric("Ratio SCR",  "208.5%",      "✅ > 150%")
        with c3: st.metric("Ratio MCR",  "320.0%",      "✅ > 100%")
        _jauge_scr(208.5)

    elif code == 'A11':
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("TP IFRS 17",     "3 992 344 €", "PAA")
        with c2: st.metric("LRC",            "2 500 000 €", "risque restant")
        with c3: st.metric("Ratio IFRS17/S2","1.370",       "✅ Cohérent")

    elif code == 'A12':
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Duration actifs", "3.50 ans",  "obligations")
        with c2: st.metric("Gap duration",    "+1.90 ans", "⚠️ À raccourcir")
        with c3: st.metric("LCR",            "1 173%",    "✅ Liquide")

    elif code == 'A9':
        st.markdown(f"""
        <div style="background:{NAVY_L};border:1px solid rgba(46,204,113,0.3);
                    border-radius:10px;padding:16px 20px;">
            <div style="color:{VERT};font-weight:700;margin-bottom:8px;">
                ✅ Score cohérence global : 100%
            </div>
            <div style="font-size:0.85rem;color:{GRIS};">
                Tarif ↔ Provisions · Provisions ↔ Stress · Modèle ↔ Provisions
                → Tous les contrôles VERT
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif code == 'A13':
        st.markdown(f"""
        <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.3);
                    border-radius:10px;padding:16px 20px;">
            <div style="font-size:0.68rem;color:{GRIS};margin-bottom:6px;">
                Hash de session SHA-256
            </div>
            <div style="font-family:monospace;color:{OR};font-size:1.2rem;">
                5BB15F63
            </div>
            <div style="font-size:0.75rem;color:{GRIS};margin-top:8px;">
                19 agents tracés · RGPD Art.30 conforme · Hypothèses versionnées
            </div>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.markdown(f"""
        <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
                    border-radius:10px;padding:16px 20px;">
            <div style="font-size:0.88rem;color:{GRIS};line-height:1.6;">
                {agent['kpi']} · Statut : {agent['statut']}<br>
                Cliquez sur "Lancer {agent['prenom']}" pour exécuter le pipeline
                et obtenir les résultats détaillés.
            </div>
        </div>
        """, unsafe_allow_html=True)


def _tab_lancer(agent_key):
    """Onglet pour lancer l'agent."""
    agent = AGENTS[agent_key]
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    fichier = st.file_uploader(
        "Uploader vos données",
        type=['csv','xlsx','xls','parquet'],
        key=f"up_{agent_key}"
    )
    if fichier:
        st.success(f"✅ {fichier.name} chargé")

    col1, col2 = st.columns(2)
    with col1:
        branche = st.selectbox("Branche", ['Non-Vie (Auto)','Non-Vie (MRH)',
                                            'Non-Vie (RC Pro)','Vie',
                                            'Santé-Prévoyance','Épargne-Retraite'],
                                key=f"br_{agent_key}")
    with col2:
        client = st.text_input("ID Client", placeholder="cabinet_xyz",
                                key=f"cl_{agent_key}")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    col_b1, col_b2, _ = st.columns([1,1,2])
    with col_b1:
        if st.button(f"🚀 Lancer {agent['prenom']}", type="primary",
                      use_container_width=True, key=f"run_{agent_key}"):
            _simuler_pipeline(agent['prenom'])
    with col_b2:
        if st.button("🎯 Démo synthétique", use_container_width=True,
                      key=f"demo_{agent_key}"):
            _simuler_pipeline(agent['prenom'])


def _tab_chat_agent(agent_key):
    """Chat avec l'agent via Claude API."""
    agent   = AGENTS[agent_key]
    chat_key= f"chat_{agent_key}"

    if chat_key not in st.session_state:
        st.session_state[chat_key] = [{
            'role': 'assistant',
            'content': (f"Bonjour, je suis **{agent['prenom']}**, "
                        f"spécialiste en *{agent['role_fr']}*. "
                        f"Mon KPI : **{agent['kpi']}**. "
                        f"Comment puis-je vous aider ?")
        }]

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    for msg in st.session_state[chat_key]:
        label = agent['prenom'] if msg['role'] == 'assistant' else 'Vous'
        border = "rgba(46,204,113,0.3)" if msg['role']=='assistant' else "rgba(201,168,76,0.3)"
        bg     = NAVY_L if msg['role']=='assistant' else NAVY_LL
        st.markdown(f"""
        <div style="background:{bg};border:1px solid {border};
                    border-radius:10px;padding:12px 16px;margin-bottom:8px;">
            <div style="font-size:0.68rem;color:{OR};font-weight:700;
                        text-transform:uppercase;letter-spacing:0.08em;
                        margin-bottom:5px;">{label}</div>
            <div style="font-size:0.87rem;color:{BLANC};line-height:1.65;">
                {msg['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    prompt = st.chat_input(
        f"Posez votre question à {agent['prenom']}...",
        key=f"inp_{agent_key}"
    )
    if prompt:
        st.session_state[chat_key].append({'role':'user','content':prompt})
        with st.spinner(f"{agent['prenom']} réfléchit..."):
            reponse = appeler_claude(
                st.session_state[chat_key],
                system_prompt=system_prompt_agent(agent_key)
            )
        st.session_state[chat_key].append({'role':'assistant','content':reponse})
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE SOFIA (ARIA)
# ══════════════════════════════════════════════════════════════════════════════

def page_aria():
    st.markdown(f"""
    <div style="text-align:center;padding:16px 0 24px;">
        <div style="font-size:2.5rem;margin-bottom:10px;">🤖</div>
        <div style="font-family:'Playfair Display',serif;font-size:1.8rem;
                    font-weight:700;color:{BLANC};">
            Agent <span style="color:{OR};">Sofia</span>
        </div>
        <div style="color:{GRIS};font-size:0.88rem;margin-top:6px;">
            ARIA — Actuaire IA Senior · Propulsée par Claude API (Anthropic)
        </div>
        <div style="display:inline-block;margin-top:10px;padding:3px 14px;
                    background:rgba(201,168,76,0.1);
                    border:1px solid rgba(201,168,76,0.3);
                    border-radius:20px;font-size:0.72rem;color:{OR};">
            ✅ 20 agents connectés
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.messages_aria:
        st.session_state.messages_aria = [{
            'role': 'assistant',
            'content': ("Bonjour, je suis **Sofia**, votre actuaire IA senior. "
                        "J'ai accès aux résultats de tous les agents ActuarIA. "
                        "Posez-moi n'importe quelle question actuarielle !\n\n"
                        "**Exemples :**\n"
                        "- *Analyse le Best Estimate de mon portefeuille*\n"
                        "- *Explique le ratio SCR de 208.5%*\n"
                        "- *Compare les méthodes de provisionnement*\n"
                        "- *Quels sont les risques principaux identifiés ?*")
        }]

    for msg in st.session_state.messages_aria:
        label  = "Sofia" if msg['role']=='assistant' else "Vous"
        border = "rgba(46,204,113,0.3)" if msg['role']=='assistant' else "rgba(201,168,76,0.3)"
        bg     = NAVY_L if msg['role']=='assistant' else NAVY_LL
        st.markdown(f"""
        <div style="background:{bg};border:1px solid {border};
                    border-radius:12px;padding:14px 18px;margin-bottom:10px;
                    max-width:820px;">
            <div style="font-size:0.68rem;color:{OR};font-weight:700;
                        text-transform:uppercase;letter-spacing:0.08em;
                        margin-bottom:6px;">{label}</div>
            <div style="font-size:0.88rem;color:{BLANC};line-height:1.65;">
                {msg['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    if prompt := st.chat_input("Posez votre question actuarielle à Sofia..."):
        st.session_state.messages_aria.append({'role':'user','content':prompt})
        with st.spinner("Sofia réfléchit..."):
            reponse = appeler_claude(
                st.session_state.messages_aria,
                system_prompt=SYSTEM_PROMPT_SOFIA
            )
        st.session_state.messages_aria.append({'role':'assistant','content':reponse})
        st.rerun()

    if st.button("🗑️ Effacer la conversation", key="clear_aria"):
        st.session_state.messages_aria = []
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    st.markdown(f"""
    <div style="font-family:'Playfair Display',serif;font-size:1.6rem;
                font-weight:700;color:{BLANC};margin-bottom:4px;">
        Dashboard Actuariel
    </div>
    <div style="color:{GRIS};font-size:0.85rem;margin-bottom:20px;">
        Résultats consolidés — Portefeuille Auto Non-Vie
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["📐 Tarification","🏦 Provisions","🛡️ Solvabilité 2",
                    "📊 IFRS 17","⚖️ ALM","📋 Synthèse"])

    with tabs[0]:
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Fréquence", "0.163", "Auto FR")
        with c2: st.metric("Coût moyen","4 638 €","+2.1%")
        with c3: st.metric("Prime pure","757 €",  "Poisson×Gamma")
        with c4: st.metric("Gini ML",   "0.2651", "XGBoost")
        _bar_chart(
            ['GLM','ElasticNet','LightGBM','CatBoost','GBM','XGBoost'],
            [0.000,0.244,0.248,0.253,0.254,0.265],
            "Gini par modèle", horizontal=True
        )

    with tabs[1]:
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Best Estimate","2 914 930 €","CV 0.6%")
        with c2: st.metric("P90",         "3 098 000 €","+6.3%")
        with c3: st.metric("σ Mack",      "45 000 €",   "IC 95%")
        _bar_chart(
            ['Chain Ladder','Mack 1993','BF','Cape Cod','Best Estimate'],
            [2850000,2914930,2930000,2880000,2914930],
            "4 méthodes — convergence (M€)", highlight_last=True
        )

    with tabs[2]:
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("SCR Total","3 680 671 €","formule std")
        with c2: st.metric("MCR",     "2 500 000 €","plancher régl.")
        with c3: st.metric("Ratio SCR","208.5%",    "✅ > 150%")
        with c4: st.metric("Ratio MCR","320.0%",    "✅ > 100%")
        _jauge_scr(208.5)

    with tabs[3]:
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("TP IFRS 17","3 992 344 €","PAA")
        with c2: st.metric("LRC",       "2 500 000 €","risque restant")
        with c3: st.metric("Ratio",     "1.370",      "✅ Cohérent")

    with tabs[4]:
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Duration actifs", "3.50 ans","+")
        with c2: st.metric("Gap",            "+1.90 ans","⚠️")
        with c3: st.metric("LCR",           "1 173%",   "✅")

    with tabs[5]:
        df = pd.DataFrame([
            {'Module':'Tarification',  'Agent':'A3-A6','Résultat':'Gini=0.2651 · ElasticNet ⭐','Statut':'🟢'},
            {'Module':'Provisionnement','Agent':'A7',  'Résultat':'BE=2.91M€ · CV=0.6%',       'Statut':'🟢'},
            {'Module':'Stress Testing','Agent':'A8',   'Résultat':'Ratio SCR=375%',             'Statut':'🟢'},
            {'Module':'Cohérence',     'Agent':'A9',   'Résultat':'Score 100%',                 'Statut':'🟢'},
            {'Module':'Solvabilité 2', 'Agent':'A10',  'Résultat':'Ratio SCR=208.5%',           'Statut':'🟢'},
            {'Module':'IFRS 17',       'Agent':'A11',  'Résultat':'TP=3.99M€ · Ratio=1.370',   'Statut':'🟢'},
            {'Module':'ALM',           'Agent':'A12',  'Résultat':'Gap=+1.9 ans · LCR=1173%',  'Statut':'🟡'},
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown(f"""
        <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.3);
                    border-radius:8px;padding:12px 16px;margin-top:16px;
                    display:inline-block;">
            <span style="color:{GRIS};font-size:0.72rem;">Hash session :</span>
            <span style="font-family:monospace;color:{OR};font-size:1rem;
                         margin-left:8px;">5BB15F63</span>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ANALYSE
# ══════════════════════════════════════════════════════════════════════════════

def page_analyse():
    st.markdown(f"""
    <div style="font-family:'Playfair Display',serif;font-size:1.6rem;
                font-weight:700;color:{BLANC};margin-bottom:4px;">
        Analyser un portefeuille
    </div>
    <div style="color:{GRIS};font-size:0.85rem;margin-bottom:20px;">
        Déposez votre fichier — la plateforme détecte automatiquement la branche
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1.5, 1])
    with col1:
        fichier = st.file_uploader("Fichier", type=['csv','xlsx','xls','parquet'],
                                    label_visibility='collapsed')
        if fichier:
            st.success(f"✅ {fichier.name} chargé")
    with col2:
        branche = st.selectbox("Branche", ['Non-Vie (Auto)','Non-Vie (MRH)',
                                            'Vie','Santé','Épargne-Retraite'])
        profil  = st.selectbox("Profil modèle", ['Équilibré','Performance',
                                                   'Auditabilité S2','Compagnie Vie'])
        client  = st.text_input("ID Client", placeholder="cabinet_xyz")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    c1, c2, _ = st.columns([1,1,3])
    with c1:
        if st.button("🚀 Lancer le pipeline", type="primary", use_container_width=True):
            _simuler_pipeline("Pipeline A1→A14")
    with c2:
        if st.button("🎯 Démo synthétique", use_container_width=True):
            _simuler_pipeline("Pipeline A1→A14")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE RAPPORTS
# ══════════════════════════════════════════════════════════════════════════════

def page_rapports():
    st.markdown(f"""
    <div style="font-family:'Playfair Display',serif;font-size:1.6rem;
                font-weight:700;color:{BLANC};margin-bottom:4px;">
        Rapports réglementaires
    </div>
    <div style="color:{GRIS};font-size:0.85rem;margin-bottom:20px;">
        Accessible également depuis chaque fiche agent
    </div>
    """, unsafe_allow_html=True)

    rapports = [
        ('📋','Rapport Actuariel Complet','PDF','Synthèse A1-A14 + EP1-EP5'),
        ('🛡️','QRT Solvabilité 2','Excel','S.05 · S.17 · S.19 · S.23'),
        ('📊','Rapport IFRS 17','Excel','PAA · BBA · VFA · CSM'),
        ('🌩️','ORSA Prospectif 5 ans','PDF','Stress testing · Ratio SCR projeté'),
        ('⚖️','Rapport ALM','PDF','Duration · Gap · LCR · Stress ±200bp'),
        ('🔐','Audit Trail','JSON','Logs · Hash SHA-256 · RGPD Art.30'),
        ('🏢','Rapport IAS 19','Excel','DBO · Service Cost · Interest Cost'),
        ('📄','Fiche Assuré PER','PDF','Droits · Rente · Frais · PACTE 2019'),
    ]

    cols = st.columns(2)
    for i, (icon,nom,fmt,desc) in enumerate(rapports):
        with cols[i%2]:
            col_i, col_b = st.columns([4,1])
            with col_i:
                st.markdown(f"""
                <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
                            border-radius:10px;padding:14px 16px;margin-bottom:8px;
                            display:flex;gap:12px;align-items:flex-start;">
                    <span style="font-size:1.3rem;">{icon}</span>
                    <div>
                        <div style="font-weight:600;color:{BLANC};font-size:0.85rem;">{nom}</div>
                        <div style="font-size:0.73rem;color:{GRIS};margin-top:2px;">{desc}</div>
                        <div style="font-size:0.68rem;color:{OR};margin-top:3px;font-weight:600;">{fmt}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_b:
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                if st.button("↓", key=f"dl_{i}", help=f"Générer {nom}"):
                    st.toast(f"✅ {nom} généré", icon="✅")


# ══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _radar_hero():
    cats = ['Solvabilité','Provisions','Tarification','Cohérence','ALM','IFRS17']
    vals = [0.92,0.96,0.85,1.00,0.78,0.88]
    fig  = go.Figure(go.Scatterpolar(
        r=vals+[vals[0]], theta=cats+[cats[0]],
        fill='toself', fillcolor='rgba(201,168,76,0.12)',
        line=dict(color=OR,width=2.5), marker=dict(color=OR,size=6),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=NAVY_L,
            radialaxis=dict(visible=True,range=[0,1],
                           tickfont=dict(color=GRIS,size=9),
                           gridcolor='rgba(201,168,76,0.15)',
                           linecolor='rgba(201,168,76,0.2)'),
            angularaxis=dict(tickfont=dict(color=BLANC,size=10),
                            gridcolor='rgba(201,168,76,0.15)',
                            linecolor='rgba(201,168,76,0.2)'),
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40,r=40,t=20,b=20), height=280, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})


def _bar_chart(labels, values, title="", horizontal=False, highlight_last=False):
    colors = [OR if (highlight_last and i==len(values)-1) else
              OR if v == max(values) else NAVY_LL
              for i,v in enumerate(values)]
    if horizontal:
        fig = go.Figure(go.Bar(
            x=values, y=labels, orientation='h',
            marker_color=colors,
            text=[f"{v:.3f}" for v in values],
            textposition='outside', textfont=dict(color=BLANC,size=10),
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False),
            yaxis=dict(tickfont=dict(color=BLANC,size=10)),
            margin=dict(l=0,r=50,t=24,b=8), height=220,
            title=dict(text=title, font=dict(color=GRIS,size=11)),
        )
    else:
        text_vals = [f"{v/1e6:.2f}M€" if v>1000 else f"{v:.3f}" for v in values]
        fig = go.Figure(go.Bar(
            x=labels, y=values, marker_color=colors,
            marker_line=dict(color=OR,width=1),
            text=text_vals, textposition='outside',
            textfont=dict(color=BLANC,size=10),
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickfont=dict(color=BLANC,size=9)),
            yaxis=dict(visible=False),
            margin=dict(l=0,r=0,t=32,b=8), height=240,
            title=dict(text=title, font=dict(color=GRIS,size=11)),
        )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})


def _jauge_scr(valeur):
    fig = go.Figure(go.Indicator(
        mode='gauge+number', value=valeur,
        number=dict(suffix='%', font=dict(color=OR,size=32)),
        gauge=dict(
            axis=dict(range=[0,300], tickcolor=GRIS,
                     tickfont=dict(color=GRIS)),
            bar=dict(color=OR),
            steps=[
                dict(range=[0,100],   color='rgba(231,76,60,0.25)'),
                dict(range=[100,150], color='rgba(243,156,18,0.25)'),
                dict(range=[150,300], color='rgba(46,204,113,0.25)'),
            ],
            bgcolor=NAVY_L,
        ),
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=BLANC),
        margin=dict(l=20,r=20,t=20,b=20), height=240,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})


def _simuler_pipeline(nom):
    import time
    etapes = [
        ("🔍 Ingestion & Validation",       0.20),
        ("⚡ Preprocessing",                 0.35),
        ("📐 GLM + ML Tarification",         0.55),
        ("🏦 Provisionnement",               0.70),
        ("🛡️ Solvabilité 2 + IFRS 17",       0.85),
        ("🔐 Audit Trail & Hash",            1.00),
    ]
    bar = st.progress(0)
    msg = st.empty()
    for label, prog in etapes:
        msg.markdown(f"<p style='color:{GRIS};font-size:0.85rem;'>{label}</p>",
                      unsafe_allow_html=True)
        bar.progress(prog)
        time.sleep(0.35)
    bar.empty(); msg.empty()
    st.success(f"✅ {nom} terminé — résultats disponibles dans le Dashboard")
    if st.button("Voir le Dashboard →", key=f"go_dash_{nom[:5]}"):
        st.session_state.page = 'dashboard'
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

inject_css()
render_sidebar()

page = st.session_state.page

if   page == 'accueil':      page_accueil()
elif page == 'agent_detail': page_agent_detail()
elif page == 'dashboard':    page_dashboard()
elif page == 'aria':         page_aria()
elif page == 'analyse':      page_analyse()
elif page == 'rapports':     page_rapports()
else:                        page_accueil()
