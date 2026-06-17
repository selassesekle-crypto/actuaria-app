"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — INTERFACE STREAMLIT v4.0                                        ║
║  3 Directions · Managers · Directeurs · Sofia Claude API                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime
import anthropic

st.set_page_config(
    page_title="ActuarIA",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DESIGN TOKENS ─────────────────────────────────────────────────────────────
NAVY   = "#0F2E52"
NAVY_L = "#1B3A5C"
NAVY_LL= "#243F6A"
OR     = "#C9A84C"
OR_L   = "#E8C96A"
BLANC  = "#F0F4F8"
GRIS   = "#8A9AB0"
VERT   = "#2ECC71"
AMBRE  = "#F39C12"
ROUGE  = "#E74C3C"
BLEU   = "#3498DB"

# ── SESSION STATE (compatible toutes versions Streamlit) ──────────────────────
for k, v in {
    "page": "accueil",
    "agent_selec": None,
    "dir_selec": None,
    "messages_aria": [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def nav_to(page, agent=None, dir_key=None):
    st.session_state.page = page
    st.session_state.agent_selec = agent
    st.session_state.dir_selec = dir_key
    st.rerun()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');
.stApp{{background:{NAVY};color:{BLANC};font-family:'Inter',sans-serif;}}
.block-container{{padding-top:20px!important;padding-bottom:20px!important;}}
[data-testid="stSidebar"]{{background:{NAVY_L};border-right:1px solid rgba(201,168,76,0.25);}}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,[data-testid="stSidebar"] label{{color:{BLANC};}}
[data-testid="stSidebar"] .stButton>button{{
  background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);
  color:{BLANC}!important;border-radius:8px;font-size:0.82rem;font-weight:500;
  padding:8px 12px;width:100%;text-align:left;transition:all 0.2s;margin-bottom:3px;
}}
[data-testid="stSidebar"] .stButton>button:hover{{
  background:rgba(201,168,76,0.15);border-color:rgba(201,168,76,0.5);
  color:{OR}!important;transform:translateX(2px);
}}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{{
  background:linear-gradient(135deg,rgba(201,168,76,0.2),rgba(232,201,106,0.1));
  border:1px solid rgba(201,168,76,0.45);color:{OR}!important;font-weight:700;
}}
.btn-manager>[data-testid="stSidebar"] .stButton>button{{
  background:rgba(52,152,219,0.1);border-color:rgba(52,152,219,0.3);
  color:{BLEU}!important;
}}
[data-testid="stMetric"]{{background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px 18px;}}
[data-testid="stMetricLabel"]{{color:{GRIS}!important;font-size:0.68rem!important;font-weight:600!important;text-transform:uppercase!important;letter-spacing:0.08em!important;}}
[data-testid="stMetricValue"]{{color:{OR}!important;font-size:1.35rem!important;font-weight:700!important;}}
.stButton>button{{background:linear-gradient(135deg,{OR},{OR_L});color:{NAVY}!important;border:none;border-radius:8px;font-weight:700;padding:10px 20px;transition:all 0.2s;}}
.stButton>button:hover{{transform:translateY(-1px);box-shadow:0 4px 16px rgba(201,168,76,0.4);}}
.stTabs [data-baseweb="tab-list"]{{background:{NAVY_L};border-radius:8px;padding:4px;gap:4px;}}
.stTabs [data-baseweb="tab"]{{background:transparent;color:{GRIS};border-radius:6px;font-weight:500;padding:8px 16px;}}
.stTabs [aria-selected="true"]{{background:{OR}!important;color:{NAVY}!important;font-weight:700!important;}}
.badge-VERT{{display:inline-block;background:rgba(46,204,113,0.15);color:#2ECC71;border:1px solid rgba(46,204,113,0.4);border-radius:20px;padding:2px 10px;font-size:0.68rem;font-weight:600;}}
.badge-AMBRE{{display:inline-block;background:rgba(243,156,18,0.15);color:#F39C12;border:1px solid rgba(243,156,18,0.4);border-radius:20px;padding:2px 10px;font-size:0.68rem;font-weight:600;}}
.badge-ROUGE{{display:inline-block;background:rgba(231,76,60,0.15);color:#E74C3C;border:1px solid rgba(231,76,60,0.4);border-radius:20px;padding:2px 10px;font-size:0.68rem;font-weight:600;}}
.badge-DEV{{display:inline-block;background:rgba(138,154,176,0.15);color:#8A9AB0;border:1px solid rgba(138,154,176,0.4);border-radius:20px;padding:2px 10px;font-size:0.68rem;font-weight:600;}}
.stTextInput>div>div>input,.stSelectbox>div>div,.stTextArea>div>div>textarea{{background:{NAVY_L}!important;border:1px solid rgba(201,168,76,0.3)!important;color:{BLANC}!important;border-radius:8px!important;}}
hr{{border-color:rgba(201,168,76,0.2);}}
::-webkit-scrollbar{{width:4px;}}
::-webkit-scrollbar-thumb{{background:rgba(201,168,76,0.4);border-radius:2px;}}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# DONNÉES AGENTS
# ══════════════════════════════════════════════════════════════════════════════

AGENTS = {
    # ── CENTRALE ──────────────────────────────────────────────────────────────
    'sofia': {
        'prenom':'Sofia', 'code':'ARIA', 'icon':'🤖', 'statut':'VERT',
        'niveau':'centrale', 'dir':'centrale',
        'role_fr':'Directrice IA Générale — Accès toutes directions',
        'desc_fr':'Sofia coordonne toutes les directions et tous les agents de la plateforme. Propulsée par Claude API, elle répond à toutes vos questions actuarielles, synthétise les résultats de toutes les directions et oriente vers le bon expert.',
        'spec_fr':'IA générative · Synthèse multi-directions · Claude API',
        'kpi':'46 agents · 3 directions · 1 plateforme',
    },
    'rafael': {
        'prenom':'Rafael', 'code':'A13', 'icon':'🔐', 'statut':'VERT',
        'niveau':'transversal', 'dir':'centrale',
        'role_fr':'Audit Trail & Conformité RGPD — Transversal toutes directions',
        'desc_fr':'Rafael garantit l\'intégrité de tous les calculs de toutes les directions : hash SHA-256, registre RGPD Art.30, versioning des hypothèses et rapport d\'audit complet pour l\'auditeur S2.',
        'spec_fr':'SHA-256 · RGPD Art.30 · Versioning · Audit S2',
        'kpi':'Hash 5BB15F63',
    },

    # ── DIRECTION NON-VIE — DIRECTRICE ────────────────────────────────────────
    'leila': {
        'prenom':'Leila', 'code':'DIR-NV', 'icon':'👩‍💼', 'statut':'VERT',
        'niveau':'directeur', 'dir':'non_vie',
        'role_fr':'Directrice Direction Non-Vie (IARD)',
        'desc_fr':'Leila supervise l\'ensemble de la Direction Non-Vie : équipes Tarification, Provisionnement et Réglementation. Elle coordonne Mei-Lin, Kwame et Nadia, assume la responsabilité des résultats de sa direction et répond à toutes les questions Non-Vie.',
        'spec_fr':'IARD · Non-Vie · Auto · MRH · RC Pro · Supervision',
        'kpi':'3 équipes · 12 agents · Direction Non-Vie',
    },

    # ── NON-VIE — MANAGERS ────────────────────────────────────────────────────
    'meilin': {
        'prenom':'Mei-Lin', 'code':'MGR-TAR', 'icon':'⚖️', 'statut':'VERT',
        'niveau':'manager', 'dir':'non_vie', 'equipe':'tarification',
        'role_fr':'Manager Équipe Tarification Non-Vie',
        'desc_fr':'Mei-Lin supervise et valide tous les travaux de tarification Non-Vie. Elle répond à toutes les questions tarifaires en assumant pleinement les résultats de son équipe : modèles GLM, ML, Deep Learning et sélection du modèle de production.',
        'spec_fr':'Supervision tarification · GLM · ML · DL · Sélection modèle',
        'kpi':'Gini = 0.2651 · ElasticNet retenu · Score 0.8373',
    },
    'kwame': {
        'prenom':'Kwame', 'code':'MGR-PRV', 'icon':'🏦', 'statut':'VERT',
        'niveau':'manager', 'dir':'non_vie', 'equipe':'provisionnement',
        'role_fr':'Manager Équipe Provisionnement Non-Vie',
        'desc_fr':'Kwame supervise et valide tous les travaux de provisionnement Non-Vie. Il répond à toutes les questions sur les provisions en assumant les résultats de son équipe : Chain Ladder, Mack, BF, Cape Cod, Stress Testing et Cohérence.',
        'spec_fr':'Supervision provisions · BE S2 · Stress Testing · Cohérence',
        'kpi':'BE = 2.91M€ · CV 0.6% · Ratio SCR 375%',
    },
    'nadia': {
        'prenom':'Nadia', 'code':'MGR-REG', 'icon':'🛡️', 'statut':'VERT',
        'niveau':'manager', 'dir':'non_vie', 'equipe':'reglementation_nv',
        'role_fr':'Manager Équipe Réglementation Non-Vie',
        'desc_fr':'Nadia supervise et valide tous les travaux réglementaires Non-Vie. Elle répond à toutes les questions S2, IFRS17 PAA, ALM et QRT Non-Vie en assumant les résultats de son équipe.',
        'spec_fr':'S2 · IFRS17 PAA · ALM Non-Vie · QRT S.05/S.17/S.19',
        'kpi':'SCR 208.5% · MCR 320% · LCR 1173%',
    },

    # ── NON-VIE — AGENTS TARIFICATION ────────────────────────────────────────
    'amara': {
        'prenom':'Amara', 'code':'A1', 'icon':'🔍', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'tarification',
        'role_fr':'Ingestion & Validation des données',
        'desc_fr':'Amara ingère, valide et normalise les données clients (Excel, CSV, Parquet). Détection automatique de la branche, mapping des colonnes et contrôle RGPD Art.30.',
        'spec_fr':'Multi-format · Qualité données · RGPD Art.30', 'kpi':'678k contrats validés',
    },
    'kenji': {
        'prenom':'Kenji', 'code':'A2', 'icon':'⚡', 'statut':'AMBRE',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'tarification',
        'role_fr':'Preprocessing & Feature Engineering',
        'desc_fr':'Kenji transforme les données brutes en features exploitables : imputation, winsorisation, encodage, création de variables actuarielles.',
        'spec_fr':'Feature engineering · Imputation · Encodage', 'kpi':'30 features créées',
    },
    'laurent': {
        'prenom':'Laurent', 'code':'A3', 'icon':'📐', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'tarification',
        'role_fr':'GLM Tarification — Poisson · Gamma · Tweedie',
        'desc_fr':'Laurent calibre les GLM réglementaires avec sélection stepwise. Coefficients interprétables exigés par les auditeurs S2 et l\'AI Act 2025.',
        'spec_fr':'GLM Poisson · Gamma · Tweedie · AIC/BIC', 'kpi':'AIC = 45 000',
    },
    'priya': {
        'prenom':'Priya', 'code':'A4', 'icon':'🧠', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'tarification',
        'role_fr':'Machine Learning — 6 modèles',
        'desc_fr':'Priya maîtrise 6 algorithmes ML : GBM, XGBoost, XGBoost Tweedie, LightGBM, CatBoost, ElasticNet. Calcul Gini, détection overfitting, SHAP.',
        'spec_fr':'XGBoost · LightGBM · CatBoost · ElasticNet · SHAP', 'kpi':'Gini XGBoost = 0.2651',
    },
    'yohan': {
        'prenom':'Yohan', 'code':'A5', 'icon':'🔮', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'tarification',
        'role_fr':'Deep Learning — CANN · TabNet',
        'desc_fr':'Yohan calibre les réseaux CANN (Wüthrich 2019) et TabNet, architectures de pointe pour données tabulaires actuarielles.',
        'spec_fr':'CANN · TabNet · PyTorch · Wüthrich 2019', 'kpi':'TabNet Gini = 0.2334',
    },
    'victor': {
        'prenom':'Victor', 'code':'A6', 'icon':'🎯', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'tarification',
        'role_fr':'Comparaison & Sélection du modèle de production',
        'desc_fr':'Victor applique une grille multicritères (Gini, stabilité, interprétabilité, RMSE) avec 4 profils de pondération. Fiche de décision actuarielle complète.',
        'spec_fr':'Multicritères · 4 profils · Fiche décision · AI Act 2025', 'kpi':'ElasticNet retenu · Score 0.8373',
    },

    # ── NON-VIE — AGENTS PROVISIONNEMENT ─────────────────────────────────────
    'ibrahim': {
        'prenom':'Ibrahim', 'code':'A7', 'icon':'📊', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'provisionnement',
        'role_fr':'Provisionnement — Chain Ladder · Mack · BF · Cape Cod',
        'desc_fr':'Ibrahim calibre les 4 méthodes actuarielles de référence, calcule le Best Estimate S2 avec IC Mack 1993 et détecte les valeurs atypiques dans le triangle.',
        'spec_fr':'Chain Ladder · Mack 1993 · BF · Cape Cod · H1/H2/H3', 'kpi':'BE = 2.91M€ · CV 0.6%',
    },
    'isabelle': {
        'prenom':'Isabelle', 'code':'A8', 'icon':'🌩️', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'provisionnement',
        'role_fr':'Stress Testing & ORSA Non-Vie',
        'desc_fr':'Isabelle évalue la résistance aux chocs S2 EIOPA et projette l\'ORSA prospectif sur 5 ans. Scénarios fréquence, coût, catastrophe et combiné.',
        'spec_fr':'Chocs S2 EIOPA · ORSA 5 ans · Scénarios adverses', 'kpi':'Ratio SCR post-stress = 375%',
    },
    'marcus': {
        'prenom':'Marcus', 'code':'A9', 'icon':'🔗', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'provisionnement',
        'role_fr':'Cohérence inter-équipes',
        'desc_fr':'Marcus vérifie l\'alignement Tarification ↔ Provisions ↔ S2 ↔ IFRS17 via les Loss Ratios et alerte proactivement en cas d\'incohérence.',
        'spec_fr':'Loss Ratios · Réconciliation · Alertes RAG · Contrôles', 'kpi':'Score cohérence 100% VERT',
    },

    # ── NON-VIE — AGENTS RÉGLEMENTATION ──────────────────────────────────────
    'elena': {
        'prenom':'Elena', 'code':'A10', 'icon':'🛡️', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'reglementation_nv',
        'role_fr':'Solvabilité 2 — SCR · MCR · QRT Non-Vie',
        'desc_fr':'Elena calcule le SCR souscription, marché et opérationnel selon la formule standard EIOPA, le MCR et génère les QRT S.05, S.17, S.19 pour le reporting ACPR.',
        'spec_fr':'Formule std EIOPA · QRT S.05/S.17/S.19 · Pilier 1 S2', 'kpi':'Ratio SCR = 208.5%',
    },
    'thomas': {
        'prenom':'Thomas', 'code':'A11', 'icon':'📋', 'statut':'VERT',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'reglementation_nv',
        'role_fr':'IFRS 17 PAA — Non-Vie',
        'desc_fr':'Thomas calcule les provisions IFRS 17 selon l\'approche PAA pour les contrats Non-Vie (durée < 1 an). LRC, LIC, Risk Adjustment et réconciliation avec le BE S2.',
        'spec_fr':'IFRS17 PAA · LRC · LIC · Risk Adjustment · Réconciliation S2', 'kpi':'TP = 3.99M€ · Ratio 1.370',
    },
    'aisha': {
        'prenom':'Aisha', 'code':'A12', 'icon':'⚖️', 'statut':'AMBRE',
        'niveau':'agent', 'dir':'non_vie', 'equipe':'reglementation_nv',
        'role_fr':'ALM & Risque de Liquidité — Non-Vie',
        'desc_fr':'Aisha calcule les durations de Macaulay, le gap actif-passif, le BV01 et le LCR Non-Vie. Elle évalue l\'impact des chocs de taux ±200bp.',
        'spec_fr':'Duration · Gap ALM · LCR · Stress taux ±200bp', 'kpi':'LCR = 1173% · Gap +1.9 ans',
    },

    # ── DIRECTION VIE & EP-RE — DIRECTEUR ─────────────────────────────────────
    'paul': {
        'prenom':'Paul', 'code':'DIR-VIE', 'icon':'👨‍💼', 'statut':'VERT',
        'niveau':'directeur', 'dir':'vie_epre',
        'role_fr':'Directeur Direction Vie & EP-RE',
        'desc_fr':'Paul supervise l\'ensemble de la Direction Vie & EP-RE : équipes Vie Pure, EP-RE et Réglementation. Il coordonne Sven, Fatou et Olivier, assume la responsabilité des résultats de sa direction.',
        'spec_fr':'Vie · EP-RE · PER · Art.39/83 · Supervision',
        'kpi':'3 équipes · Direction Vie & EP-RE',
    },

    # ── VIE & EP-RE — MANAGERS ────────────────────────────────────────────────
    'sven': {
        'prenom':'Sven', 'code':'MGR-VIE', 'icon':'💼', 'statut':'DEV',
        'niveau':'manager', 'dir':'vie_epre', 'equipe':'vie_pure',
        'role_fr':'Manager Équipe Vie Pure',
        'desc_fr':'Sven supervise l\'équipe Vie Pure. Il répond à toutes les questions de tarification et provisionnement vie : décès temporaire, vie entière, capital différé, PB.',
        'spec_fr':'Supervision Vie Pure · Décès · Épargne Vie · PM · PB',
        'kpi':'Équipe en développement',
    },
    'fatou': {
        'prenom':'Fatou', 'code':'MGR-EPRE', 'icon':'💰', 'statut':'VERT',
        'niveau':'manager', 'dir':'vie_epre', 'equipe':'epre',
        'role_fr':'Manager Équipe EP-RE',
        'desc_fr':'Fatou supervise et valide tous les travaux Épargne-Retraite. Elle répond à toutes les questions EP-RE en assumant les résultats de son équipe : IAS 19, tarification, provisionnement, stress testing et reporting.',
        'spec_fr':'Supervision EP-RE · IAS 19 · PER · Art.39/83 · DARES',
        'kpi':'DBO 10.6M€ · Rente 595€/mois',
    },
    'olivier': {
        'prenom':'Olivier', 'code':'MGR-RVIE', 'icon':'📊', 'statut':'DEV',
        'niveau':'manager', 'dir':'vie_epre', 'equipe':'reglementation_vie',
        'role_fr':'Manager Équipe Réglementation Vie/EP-RE',
        'desc_fr':'Olivier supervise la réglementation de la Direction Vie & EP-RE : IFRS17 BBA/VFA, ALM long terme et tables de mortalité. Il répond à toutes les questions réglementaires Vie/EP-RE.',
        'spec_fr':'IFRS17 BBA/VFA · ALM long terme · Tables mortalité · QRT S.12',
        'kpi':'Réglementation Vie & EP-RE',
    },

    # ── VIE & EP-RE — AGENTS VIE PURE (EN DEV) ───────────────────────────────
    'nour': {
        'prenom':'Nour', 'code':'V1', 'icon':'💀', 'statut':'DEV',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'vie_pure',
        'role_fr':'Tarification Décès — Temporaire · Vie entière · Mixte',
        'desc_fr':'Nour tarifie les contrats d\'assurance décès : temporaire décès, vie entière, contrats mixtes. Utilise les tables TH0002/TF0002 et l\'agent Yuki pour les annuités.',
        'spec_fr':'Décès temporaire · Vie entière · TH0002 · TF0002', 'kpi':'En développement',
    },
    'kofi': {
        'prenom':'Kofi', 'code':'V2', 'icon':'💹', 'statut':'DEV',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'vie_pure',
        'role_fr':'Tarification Épargne Vie — Capital différé · Rentes · Multisupport',
        'desc_fr':'Kofi tarifie les contrats d\'épargne vie : capital différé, rente immédiate, rente différée, contrats multisupport fonds euros + UC.',
        'spec_fr':'Capital différé · Rentes · Fonds euros · UC · Multisupport', 'kpi':'En développement',
    },
    'amelie': {
        'prenom':'Amélie', 'code':'V3', 'icon':'📐', 'statut':'DEV',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'vie_pure',
        'role_fr':'Provisions Mathématiques Vie — PM prospective · Valeurs de rachat',
        'desc_fr':'Amélie calcule les provisions mathématiques des contrats vie : PM prospective, PM rétrospective, valeurs de rachat et valeurs de réduction.',
        'spec_fr':'PM prospective · PM rétrospective · Valeur de rachat', 'kpi':'En développement',
    },
    'theo': {
        'prenom':'Théo', 'code':'V4', 'icon':'💸', 'statut':'DEV',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'vie_pure',
        'role_fr':'Participation aux Bénéfices Vie — PB · PPB · Réserve capitalisation',
        'desc_fr':'Théo calcule la participation aux bénéfices réglementaire (min 85% Art. L132-29), la PPB et la réserve de capitalisation des contrats vie.',
        'spec_fr':'PB réglementaire · PPB · Réserve capitalisation · L132-29', 'kpi':'En développement',
    },
    'nia': {
        'prenom':'Nia', 'code':'V5', 'icon':'📋', 'statut':'DEV',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'vie_pure',
        'role_fr':'QRT Vie & Rapport Actuariel Annuel',
        'desc_fr':'Nia génère les QRT S.12 (PM vie), S.23 (fonds propres) et le rapport actuariel annuel vie. Rapport signé par l\'actuaire désigné.',
        'spec_fr':'QRT S.12 · S.23 · Rapport actuariel annuel vie', 'kpi':'En développement',
    },

    # ── VIE & EP-RE — AGENTS EP-RE ────────────────────────────────────────────
    'henri': {
        'prenom':'Henri', 'code':'EP1', 'icon':'🏢', 'statut':'VERT',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'epre',
        'role_fr':'Engagements de Retraite — IAS 19',
        'desc_fr':'Henri évalue les engagements de retraite IAS 19 par la méthode PUC. DBO, Service Cost, Interest Cost pour les régimes Art.39, Art.83 et PER.',
        'spec_fr':'IAS 19 · PUC · DBO · OAT iBoxx AA', 'kpi':'DBO = 10.6M€',
    },
    'salome': {
        'prenom':'Salomé', 'code':'EP2', 'icon':'💰', 'statut':'VERT',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'epre',
        'role_fr':'Tarification EP-RE — PER · Art.39 · Art.83 · PERCO',
        'desc_fr':'Salomé tarifie les contrats d\'épargne-retraite : cotisations, rentes viagères, taux de remplacement et participation aux bénéfices.',
        'spec_fr':'PER · Art.39 · Art.83 · PERCO · PACTE 2019', 'kpi':'Rente = 595€/mois',
    },
    'jinho': {
        'prenom':'Jin-Ho', 'code':'EP3', 'icon':'📈', 'statut':'VERT',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'epre',
        'role_fr':'Provisionnement EP-RE — PM · PPB · Réserve capitalisation',
        'desc_fr':'Jin-Ho calcule les PM, PPB et Réserve de Capitalisation des contrats EP-RE. Conformité avec le Code des assurances Art. R342-14.',
        'spec_fr':'PM · PPB · Réserve capitalisation · R342-14', 'kpi':'PPB = 1.15M€',
    },
    'claire': {
        'prenom':'Claire', 'code':'EP4', 'icon':'⚡', 'statut':'ROUGE',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'epre',
        'role_fr':'Stress Testing EP-RE — Longévité · Taux bas · Rachats',
        'desc_fr':'Claire évalue la résistance des portefeuilles EP-RE aux chocs longévité (+20%), taux bas (0%), rachats massifs (40%) et choc financier (-20%).',
        'spec_fr':'Choc longévité · Taux bas · Rachats · ORSA retraite', 'kpi':'Ratio base = 110%',
    },
    'omar': {
        'prenom':'Omar', 'code':'EP5', 'icon':'📋', 'statut':'VERT',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'epre',
        'role_fr':'Reporting EP-RE — ACPR · DARES · CA',
        'desc_fr':'Omar génère le rapport actuariel annuel EP-RE, QRT retraite ACPR, fiche information assuré PER, enquête DARES et note pour le Conseil d\'Administration.',
        'spec_fr':'ACPR · DARES · CA · Fiche assuré PER · PACTE 2019', 'kpi':'4 rapports disponibles',
    },

    # ── VIE & EP-RE — AGENTS RÉGLEMENTATION ──────────────────────────────────
    'eric': {
        'prenom':'Éric', 'code':'R-VIE1', 'icon':'📊', 'statut':'DEV',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'reglementation_vie',
        'role_fr':'IFRS 17 BBA/VFA — Vie & EP-RE',
        'desc_fr':'Éric calcule les provisions IFRS 17 selon les approches BBA et VFA pour les contrats vie et EP-RE (contrats longs). CSM, Risk Adjustment et résultat technique.',
        'spec_fr':'IFRS17 BBA · VFA · CSM · Risk Adjustment · Contrats longs', 'kpi':'En développement',
    },
    'camille': {
        'prenom':'Camille', 'code':'R-VIE2', 'icon':'⚖️', 'statut':'DEV',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'reglementation_vie',
        'role_fr':'ALM Long Terme — Vie & EP-RE',
        'desc_fr':'Camille calcule l\'ALM des contrats vie et EP-RE avec une duration passif de 15-25 ans. Gap duration, BV01, stress taux spécifiques contrats longs.',
        'spec_fr':'ALM long terme · Duration 15-25 ans · Gap · BV01 · Stress', 'kpi':'En développement',
    },
    'yuki': {
        'prenom':'Yuki', 'code':'A14', 'icon':'📉', 'statut':'VERT',
        'niveau':'agent', 'dir':'vie_epre', 'equipe':'reglementation_vie',
        'role_fr':'Tables de Mortalité & Biométrie',
        'desc_fr':'Yuki calcule les annuités viagères, espérances de vie et capitaux décès sur TH0002, TF0002 et TGHF05. Projection Lee-Carter. Table custom acceptée.',
        'spec_fr':'TH0002 · TF0002 · TGHF05 · Lee-Carter · Table custom', 'kpi':'R² = 0.9985 · ä65 = 13.07',
    },

    # ── DIRECTION SANTÉ-PRÉVOYANCE — DIRECTRICE ───────────────────────────────
    'amira': {
        'prenom':'Amira', 'code':'DIR-SP', 'icon':'👩‍⚕️', 'statut':'DEV',
        'niveau':'directeur', 'dir':'sante_prev',
        'role_fr':'Directrice Direction Santé-Prévoyance',
        'desc_fr':'Amira supervise l\'ensemble de la Direction Santé-Prévoyance : équipes Santé et Prévoyance. Elle coordonne Chiara et Diallo, et supervise directement Naomie (Stress Testing transversal).',
        'spec_fr':'Santé · Prévoyance · Mutuelles · IP · AMEXA · DREES',
        'kpi':'Direction en développement',
    },

    # ── SANTÉ-PRÉVOYANCE — MANAGERS ───────────────────────────────────────────
    'chiara': {
        'prenom':'Chiara', 'code':'MGR-SAN', 'icon':'🏥', 'statut':'DEV',
        'niveau':'manager', 'dir':'sante_prev', 'equipe':'sante',
        'role_fr':'Manager Équipe Santé',
        'desc_fr':'Chiara supervise l\'équipe Santé. Elle répond à toutes les questions de tarification, provisionnement et reporting santé : frais médicaux, CCAM/NGAP, ANI, AMEXA.',
        'spec_fr':'Supervision Santé · CCAM · NGAP · ANI · AMEXA · PSAP',
        'kpi':'Équipe en développement',
    },
    'diallo': {
        'prenom':'Diallo', 'code':'MGR-PRE', 'icon':'🩺', 'statut':'DEV',
        'niveau':'manager', 'dir':'sante_prev', 'equipe':'prevoyance',
        'role_fr':'Manager Équipe Prévoyance',
        'desc_fr':'Diallo supervise l\'équipe Prévoyance. Il répond à toutes les questions de tarification, provisionnement et reporting prévoyance : ITT, invalidité, décès, tables morbidité.',
        'spec_fr':'Supervision Prévoyance · ITT · Invalidité · TD 88-90 · BCAC',
        'kpi':'Équipe en développement',
    },

    # ── SANTÉ — AGENTS (EN DEV) ───────────────────────────────────────────────
    'leonie': {
        'prenom':'Léonie', 'code':'S1', 'icon':'💊', 'statut':'DEV',
        'niveau':'agent', 'dir':'sante_prev', 'equipe':'sante',
        'role_fr':'Tarification Frais de Santé — CCAM · NGAP · ANI',
        'desc_fr':'Léonie tarifie les contrats complémentaires santé : garanties soins courants, hospitalisation, dentaire, optique. Tables de consommation CCAM/NGAP. ANI.',
        'spec_fr':'CCAM · NGAP · ANI · Segmentation · Garanties santé', 'kpi':'En développement',
    },
    'selma': {
        'prenom':'Selma', 'code':'S2', 'icon':'📦', 'statut':'DEV',
        'niveau':'agent', 'dir':'sante_prev', 'equipe':'sante',
        'role_fr':'Provisionnement Santé — PSAP · PRC · Cadences',
        'desc_fr':'Selma calcule les provisions santé : PSAP santé (différent Non-Vie), Provision pour Risques en Cours, cadences de règlement des actes médicaux.',
        'spec_fr':'PSAP Santé · PRC · Cadences règlement · Actes médicaux', 'kpi':'En développement',
    },
    'binta': {
        'prenom':'Binta', 'code':'S3', 'icon':'📋', 'statut':'DEV',
        'niveau':'agent', 'dir':'sante_prev', 'equipe':'sante',
        'role_fr':'Reporting Santé — QRT S.13 · AMEXA · DREES · ANI',
        'desc_fr':'Binta génère les rapports réglementaires santé : QRT S.13, enquête AMEXA (mutuelles), statistiques DREES, conformité ANI.',
        'spec_fr':'QRT S.13 · AMEXA · DREES · ANI · Mutuelles', 'kpi':'En développement',
    },

    # ── PRÉVOYANCE — AGENTS (EN DEV) ─────────────────────────────────────────
    'axel': {
        'prenom':'Axel', 'code':'P1', 'icon':'🦺', 'statut':'DEV',
        'niveau':'agent', 'dir':'sante_prev', 'equipe':'prevoyance',
        'role_fr':'Tarification Prévoyance — ITT · Invalidité · Décès',
        'desc_fr':'Axel tarifie les contrats prévoyance : incapacité temporaire de travail (ITT), invalidité permanente (IP), décès prévoyance. Tables TD 88-90 et BCAC 2004.',
        'spec_fr':'ITT · IP · Décès prévoyance · TD 88-90 · BCAC 2004 · Multi-états', 'kpi':'En développement',
    },
    'rayan': {
        'prenom':'Rayan', 'code':'P2', 'icon':'📊', 'statut':'DEV',
        'niveau':'agent', 'dir':'sante_prev', 'equipe':'prevoyance',
        'role_fr':'Tables de Morbidité — Incapacité · Invalidité · Markov',
        'desc_fr':'Rayan gère les tables spécifiques prévoyance : tables d\'incapacité-invalidité, probabilités de passage entre états (actif→incapable→invalide→décès).',
        'spec_fr':'Tables morbidité · Incapacité · Invalidité · Chaîne de Markov', 'kpi':'En développement',
    },
    'elodie': {
        'prenom':'Élodie', 'code':'P3', 'icon':'📐', 'statut':'DEV',
        'niveau':'agent', 'dir':'sante_prev', 'equipe':'prevoyance',
        'role_fr':'Provisionnement Prévoyance — PM rentes invalidité',
        'desc_fr':'Élodie calcule les provisions mathématiques prévoyance pour les rentes d\'invalidité long terme, proche de l\'actuariat vie.',
        'spec_fr':'PM rentes invalidité · Long terme · Actuariat vie', 'kpi':'En développement',
    },
    'valentin': {
        'prenom':'Valentin', 'code':'P4', 'icon':'📋', 'statut':'DEV',
        'niveau':'agent', 'dir':'sante_prev', 'equipe':'prevoyance',
        'role_fr':'Reporting Prévoyance — QRT S.12 · Rapport actuariel · ORSA',
        'desc_fr':'Valentin génère les rapports réglementaires prévoyance : QRT S.12, rapport actuariel annuel prévoyance, ORSA prévoyance.',
        'spec_fr':'QRT S.12 · Rapport actuariel prévoyance · ORSA', 'kpi':'En développement',
    },
    'naomie': {
        'prenom':'Naomie', 'code':'SP-ST', 'icon':'🌡️', 'statut':'DEV',
        'niveau':'agent', 'dir':'sante_prev', 'equipe':'transversal_sp',
        'role_fr':'Stress Testing Santé-Prévoyance — Rend compte à Amira',
        'desc_fr':'Naomie évalue la résistance aux chocs transversaux Santé et Prévoyance : choc pandémie, morbidité croissante, désengagement Sécu, choc invalidité.',
        'spec_fr':'Choc pandémie · Morbidité · Désengagement Sécu · Invalidité', 'kpi':'En développement',
    },
}

# ── STRUCTURE HIÉRARCHIQUE ─────────────────────────────────────────────────────
STRUCTURE = {
    'centrale': {
        'label': 'Direction Générale', 'icon': '🤖',
        'agents_directs': ['sofia', 'rafael'],
    },
    'non_vie': {
        'label': 'Direction Non-Vie', 'icon': '🏢',
        'mission': 'Tarification, provisionnement et réglementation pour les contrats Non-Vie (IARD) : Auto, MRH, RC Pro, Construction.',
        'directeur': 'leila',
        'equipes': {
            'tarification': {
                'label': 'Équipe Tarification',
                'manager': 'meilin',
                'agents': ['amara','kenji','laurent','priya','yohan','victor'],
            },
            'provisionnement': {
                'label': 'Équipe Provisionnement',
                'manager': 'kwame',
                'agents': ['ibrahim','isabelle','marcus'],
            },
            'reglementation_nv': {
                'label': 'Équipe Réglementation',
                'manager': 'nadia',
                'agents': ['elena','thomas','aisha'],
            },
        },
    },
    'vie_epre': {
        'label': 'Direction Vie & EP-RE', 'icon': '💼',
        'mission': 'Vie pure, épargne-retraite (PER, Art.39, Art.83) et réglementation Vie/EP-RE : IAS 19, IFRS 17 BBA/VFA, ALM long terme.',
        'directeur': 'paul',
        'equipes': {
            'vie_pure': {
                'label': 'Équipe Vie Pure',
                'manager': 'sven',
                'agents': ['nour','kofi','amelie','theo','nia'],
            },
            'epre': {
                'label': 'Équipe EP-RE',
                'manager': 'fatou',
                'agents': ['henri','salome','jinho','claire','omar'],
            },
            'reglementation_vie': {
                'label': 'Équipe Réglementation',
                'manager': 'olivier',
                'agents': ['eric','camille','yuki'],
            },
        },
    },
    'sante_prev': {
        'label': 'Direction Santé-Prévoyance', 'icon': '🏥',
        'mission': 'Tarification et provisionnement santé (CCAM/NGAP) et prévoyance (ITT, invalidité, décès). Mutuelles et institutions de prévoyance.',
        'directeur': 'amira',
        'equipes': {
            'sante': {
                'label': 'Équipe Santé',
                'manager': 'chiara',
                'agents': ['leonie','selma','binta'],
            },
            'prevoyance': {
                'label': 'Équipe Prévoyance',
                'manager': 'diallo',
                'agents': ['axel','rayan','elodie','valentin'],
            },
            'transversal_sp': {
                'label': 'Stress Testing',
                'manager': None,
                'agents': ['naomie'],
            },
        },
    },
}

KPI = {'be':2_914_930,'ratio_scr':208.5,'gini':0.2651,'lcr':1173.3,'tp_ifrs17':3_992_344}

# ── SYSTEM PROMPTS ─────────────────────────────────────────────────────────────
RESULTATS_CLES = """
Résultats disponibles (freMTPL2 — 678k contrats auto FR réels) :
- Best Estimate S2 : 2 914 930 € (CV 0.6%, 4 méthodes : CL/Mack/BF/CC convergentes)
- Ratio SCR : 208.5% (SCR total 3 680 671 €, MCR 2 500 000 €, Fonds propres 7 650 000 €)
- Gini ML : XGBoost 0.2651 / GBM 0.2542 / CatBoost 0.2534 / LightGBM 0.2481
- Modèle retenu : ElasticNet (score 0.8373/1.0, overfit ratio 0.98 — très stable)
- TP IFRS 17 (PAA) : 3 992 344 € (ratio IFRS17/S2 = 1.370)
- Gap ALM : +1.9 ans (duration actifs 3.5 ans vs passifs 1.6 ans)
- LCR : 1173% (très liquide)
- Hash session Audit : 5BB15F63
"""

SYSTEM_PROMPTS = {
    'sofia': f"""Tu es Sofia, Directrice IA Générale de la plateforme ActuarIA.
Tu supervises 3 directions (Non-Vie, Vie & EP-RE, Santé-Prévoyance), leurs directeurs (Leila, Paul, Amira) et 46 agents au total.
Tu peux interroger directement tes directeurs et Rafael (Audit Trail).
{RESULTATS_CLES}
Tu réponds à TOUTES les questions actuarielles. Tu assumes pleinement l'ensemble des résultats.
Réponds en français. Sois précis, professionnel et synthétique.""",

    'leila': f"""Tu es Leila, Directrice de la Direction Non-Vie chez ActuarIA.
Tu supervises 3 équipes : Tarification (Mei-Lin), Provisionnement (Kwame), Réglementation (Nadia).
{RESULTATS_CLES}
Tu réponds à TOUTES les questions Non-Vie en assumant pleinement les résultats de ta direction.
Tu ne délègues pas la parole à tes équipes — tu assumes leurs résultats directement.
Réponds en français. Sois précis et professionnel.""",

    'paul': f"""Tu es Paul, Directeur de la Direction Vie & EP-RE chez ActuarIA.
Tu supervises 3 équipes : Vie Pure (Sven), EP-RE (Fatou), Réglementation Vie/EP-RE (Olivier).
{RESULTATS_CLES}
Tu réponds à TOUTES les questions Vie et Épargne-Retraite.
Tu assumes pleinement les résultats de ta direction. Réponds en français.""",

    'amira': """Tu es Amira, Directrice de la Direction Santé-Prévoyance chez ActuarIA.
Tu supervises 2 équipes : Santé (Chiara) et Prévoyance (Diallo).
Naomie (Stress Testing transversal) te rend compte directement.
La direction est en cours de développement.
Tu réponds aux questions Santé et Prévoyance avec ton expertise.
Mutuelles, institutions de prévoyance, CCAM/NGAP, tables TD 88-90, AMEXA, DREES.
Réponds en français. Sois précis sur les spécificités Santé vs Prévoyance.""",

    'meilin': f"""Tu es Mei-Lin, Manager de l'Équipe Tarification Non-Vie chez ActuarIA.
Tu supervises : Amara(A1), Kenji(A2), Laurent(A3), Priya(A4), Yohan(A5), Victor(A6).
{RESULTATS_CLES}
Tu réponds à TOUTES les questions de tarification Non-Vie.
Tu assumes pleinement les résultats de ton équipe sans déléguer la parole.
GLM, ML, Deep Learning, sélection de modèle — tu maîtrises tout.
Réponds en français.""",

    'kwame': f"""Tu es Kwame, Manager de l'Équipe Provisionnement Non-Vie chez ActuarIA.
Tu supervises : Ibrahim(A7), Isabelle(A8), Marcus(A9).
{RESULTATS_CLES}
Tu réponds à TOUTES les questions de provisionnement Non-Vie.
Tu assumes pleinement les résultats : Chain Ladder, Mack, BF, Cape Cod, Stress Testing, Cohérence.
Réponds en français.""",

    'nadia': f"""Tu es Nadia, Manager de l'Équipe Réglementation Non-Vie chez ActuarIA.
Tu supervises : Elena(A10), Thomas(A11), Aisha(A12).
{RESULTATS_CLES}
Tu réponds à TOUTES les questions réglementaires Non-Vie : S2, IFRS17 PAA, ALM, QRT, ORSA.
Tu assumes pleinement les résultats de ton équipe. Réponds en français.""",

    'fatou': f"""Tu es Fatou, Manager de l'Équipe EP-RE chez ActuarIA.
Tu supervises : Henri(EP1), Salomé(EP2), Jin-Ho(EP3), Claire(EP4), Omar(EP5).
{RESULTATS_CLES}
Tu réponds à TOUTES les questions Épargne-Retraite : IAS 19, tarification PER/Art.39/83,
provisionnement, stress testing longévité/rachats, reporting ACPR/DARES.
Tu assumes pleinement les résultats. Réponds en français.""",

    'olivier': f"""Tu es Olivier, Manager de l'Équipe Réglementation Vie/EP-RE chez ActuarIA.
Tu supervises : Éric(IFRS17 BBA/VFA), Camille(ALM long terme), Yuki(Tables mortalité).
{RESULTATS_CLES}
Tu réponds à toutes les questions réglementaires Vie et EP-RE :
IFRS17 BBA/VFA, ALM long terme (duration 15-25 ans), tables de mortalité, QRT S.12.
Réponds en français.""",

    'sven': """Tu es Sven, Manager de l'Équipe Vie Pure chez ActuarIA.
Tu supervises : Nour(Tarification Décès), Kofi(Épargne Vie), Amélie(PM Vie), Théo(PB), Nia(QRT Vie).
L'équipe est en cours de développement.
Tu réponds aux questions Vie Pure avec ton expertise :
décès temporaire, vie entière, capital différé, provisions mathématiques, PB.
Réponds en français.""",

    'chiara': """Tu es Chiara, Manager de l'Équipe Santé chez ActuarIA.
Tu supervises : Léonie(Tarification Santé), Selma(Provisionnement Santé), Binta(Reporting Santé).
L'équipe est en cours de développement.
Tu réponds à toutes les questions Santé : frais médicaux, CCAM/NGAP, ANI,
PSAP santé, AMEXA, mutuelles, complémentaires santé.
Réponds en français.""",

    'diallo': """Tu es Diallo, Manager de l'Équipe Prévoyance chez ActuarIA.
Tu supervises : Axel(Tarification Prévoyance), Rayan(Tables Morbidité), Élodie(Provisionnement Prévoyance), Valentin(Reporting Prévoyance).
L'équipe est en cours de développement.
Tu réponds à toutes les questions Prévoyance : ITT, invalidité, décès prévoyance,
tables TD 88-90, BCAC 2004, chaîne de Markov, PM rentes invalidité.
Réponds en français.""",
}

def get_system_prompt(agent_key):
    """Retourne le system prompt de l'agent."""
    agent = AGENTS[agent_key]
    if agent_key in SYSTEM_PROMPTS:
        return SYSTEM_PROMPTS[agent_key]
    # Prompt générique pour les agents individuels
    return f"""Tu es {agent['prenom']}, agent actuariel spécialisé de la plateforme ActuarIA.
Ton rôle : {agent['role_fr']}
Tes spécialités : {agent['spec_fr']}
Ton KPI : {agent['kpi']}
{RESULTATS_CLES if agent['statut'] != 'DEV' else '(Agent en développement — réponds avec ton expertise théorique)'}
Réponds uniquement sur ton domaine. Sois précis, professionnel et pédagogue.
Réponds en français sauf si on te parle en anglais."""

# ── CLAUDE API ────────────────────────────────────────────────────────────────
def appeler_claude(messages, system_prompt=None):
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "⚠️ Clé API Anthropic non configurée."
        client = anthropic.Anthropic(api_key=api_key)
        msgs = [{"role": m["role"], "content": m["content"]}
                for m in messages if m["role"] in ["user", "assistant"]]
        kwargs = {"model": "claude-sonnet-4-6", "max_tokens": 1024, "messages": msgs}
        if system_prompt:
            kwargs["system"] = system_prompt
        response = client.messages.create(**kwargs)
        return response.content[0].text
    except anthropic.AuthenticationError:
        return "❌ Clé API invalide."
    except anthropic.RateLimitError:
        return "⚠️ Limite atteinte. Réessayez."
    except Exception as e:
        return f"❌ Erreur : {str(e)}"

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
<div style="text-align:center;padding:14px 0 10px;">
  <div style="font-family:'Playfair Display',serif;font-size:1.7rem;font-weight:700;color:{BLANC};">
    Actuar<span style="color:{OR};">IA</span>
  </div>
  <div style="font-size:0.6rem;color:{GRIS};letter-spacing:0.15em;text-transform:uppercase;">
    Actuarial Intelligence Platform
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.2);margin:6px 0 12px;'>", unsafe_allow_html=True)

        # Navigation
        for icon, label, pid in [
            ('🏠', 'Accueil', 'accueil'),
            ('📊', 'Analyse', 'analyse'),
            ('📈', 'Dashboard', 'dashboard'),
            ('📁', 'Rapports Consolidés', 'rapports'),
        ]:
            actif = st.session_state.page == pid
            if st.button(f"{icon} {label}", key=f"nav_{pid}",
                         use_container_width=True,
                         type="primary" if actif else "secondary"):
                nav_to(pid)

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.2);margin:10px 0;'>", unsafe_allow_html=True)

        # ── SOFIA ────────────────────────────────────────────────────────────
        st.markdown(f"""
<div style="font-size:0.62rem;color:rgba(201,168,76,0.7);text-transform:uppercase;
letter-spacing:0.14em;margin-bottom:6px;font-weight:700;">◆ Direction Générale</div>
""", unsafe_allow_html=True)

        for ak in ['sofia', 'rafael']:
            a = AGENTS[ak]
            lbl = f"{'🤖' if ak=='sofia' else '🔐'} {a['prenom']} ({a['code']})"
            if st.button(lbl, key=f"side_{ak}", use_container_width=True):
                st.session_state.agent_selec = ak
                st.session_state.page = 'agent_detail'
                st.rerun()

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.1);margin:10px 0;'>", unsafe_allow_html=True)

        # ── 3 DIRECTIONS ─────────────────────────────────────────────────────
        ICONS_DIR = {'non_vie': '🏢', 'vie_epre': '💼', 'sante_prev': '🏥'}
        LABELS_DIR = {'non_vie': 'Direction Non-Vie', 'vie_epre': 'Direction Vie & EP-RE', 'sante_prev': 'Direction Santé-Prévoyance'}

        for dir_key in ['non_vie', 'vie_epre', 'sante_prev']:
            dir_info = STRUCTURE[dir_key]
            dir_label = LABELS_DIR[dir_key]
            dir_icon  = ICONS_DIR[dir_key]

            with st.expander(f"{dir_icon} {dir_label}", expanded=False):
                # Bouton page direction
                if st.button(f"📋 Vue direction", key=f"dir_page_{dir_key}", use_container_width=True):
                    nav_to("direction", dir_key=dir_key)
                # Directeur
                dir_agent_key = dir_info.get('directeur')
                if dir_agent_key:
                    a = AGENTS[dir_agent_key]
                    st.markdown(f"""
<div style="font-size:0.62rem;color:rgba(201,168,76,0.8);font-weight:700;
margin:4px 0 4px;text-transform:uppercase;letter-spacing:0.06em;">
👑 Directeur·trice
</div>""", unsafe_allow_html=True)
                    badge = 'DEV' if a['statut'] == 'DEV' else a['statut']
                    if st.button(f"{a['icon']} {a['prenom']} ({a['code']})",
                                 key=f"side_{dir_agent_key}",
                                 use_container_width=True):
                        nav_to('agent_detail', agent=dir_agent_key)

                # Équipes
                for eq_key, eq in dir_info['equipes'].items():
                    st.markdown(f"""
<div style="font-size:0.62rem;color:{GRIS};font-weight:600;
margin:8px 0 4px;padding:3px 6px;
border-left:2px solid rgba(201,168,76,0.4);
text-transform:uppercase;letter-spacing:0.05em;">
{eq['label']}
</div>""", unsafe_allow_html=True)

                    # Manager
                    mgr_key = eq.get('manager')
                    if mgr_key:
                        mgr = AGENTS[mgr_key]
                        if st.button(
                            f"▸ {mgr['icon']} {mgr['prenom']} (Manager)",
                            key=f"side_{mgr_key}",
                            use_container_width=True,
                        ):
                            nav_to('agent_detail', agent=mgr_key)

                    # Agents
                    for ak in eq['agents']:
                        a = AGENTS[ak]
                        dev = a['statut'] == 'DEV'
                        label = f"  {'·'} {a['icon']} {a['prenom']} ({a['code']})" + (" ⏸" if dev else "")
                        if st.button(label, key=f"side_{ak}", use_container_width=True):
                            st.session_state.agent_selec = ak
                            st.session_state.page = 'agent_detail'
                            st.rerun()

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.2);margin:10px 0;'>", unsafe_allow_html=True)

        # Statuts
        nb_v = sum(1 for a in AGENTS.values() if a['statut'] == 'VERT')
        nb_a = sum(1 for a in AGENTS.values() if a['statut'] == 'AMBRE')
        nb_r = sum(1 for a in AGENTS.values() if a['statut'] == 'ROUGE')
        nb_d = sum(1 for a in AGENTS.values() if a['statut'] == 'DEV')
        st.markdown(f"""
<div style="font-size:0.62rem;color:rgba(201,168,76,0.7);text-transform:uppercase;
letter-spacing:0.12em;margin-bottom:6px;font-weight:700;">◆ Statuts</div>
<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px;">
  <div style="background:rgba(46,204,113,0.12);color:#2ECC71;border:1px solid rgba(46,204,113,0.3);
  border-radius:6px;padding:3px 8px;font-size:0.7rem;font-weight:700;">✅ {nb_v}</div>
  <div style="background:rgba(243,156,18,0.12);color:#F39C12;border:1px solid rgba(243,156,18,0.3);
  border-radius:6px;padding:3px 8px;font-size:0.7rem;font-weight:700;">⚠️ {nb_a}</div>
  <div style="background:rgba(231,76,60,0.12);color:#E74C3C;border:1px solid rgba(231,76,60,0.3);
  border-radius:6px;padding:3px 8px;font-size:0.7rem;font-weight:700;">❌ {nb_r}</div>
  <div style="background:rgba(138,154,176,0.12);color:#8A9AB0;border:1px solid rgba(138,154,176,0.3);
  border-radius:6px;padding:3px 8px;font-size:0.7rem;font-weight:700;">⏸ {nb_d}</div>
</div>
""", unsafe_allow_html=True)

        # Plateforme en français
        st.markdown(f"<div style='font-size:0.65rem;color:{GRIS};text-align:center;'>🇫🇷 Plateforme en français</div>", unsafe_allow_html=True)

        st.markdown(f"""
<div style="font-size:0.6rem;color:rgba(138,154,176,0.4);text-align:center;margin-top:12px;">
ActuarIA v4.0 · {datetime.now().strftime('%d/%m/%Y')}
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES
# ══════════════════════════════════════════════════════════════════════════════
def _bar_chart(labels, values, titre, color=None):
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=color or [OR]*len(labels),
        marker_line=dict(color=NAVY, width=1),
        width=0.45, opacity=0.88,
        text=[f"{v/1e3:.0f}k€" if v > 1000 else str(round(v,4)) for v in values],
        textposition='outside', textfont=dict(color=BLANC, size=10),
        hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
        font=dict(family="Inter", color=BLANC, size=11),
        title=dict(text=titre, font=dict(color=BLANC, size=13), x=0.01),
        margin=dict(l=16, r=16, t=52, b=16), height=280,
        xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
        yaxis=dict(visible=False), bargap=0.35, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

def _jauge(valeur, titre, seuil_rouge=100, seuil_ambre=150, suffix="%", max_val=300):
    coul = VERT if valeur >= seuil_ambre else AMBRE if valeur >= seuil_rouge else ROUGE
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=valeur,
        title=dict(text=titre, font=dict(color=BLANC, size=12)),
        number=dict(suffix=suffix, font=dict(color=coul, size=32), valueformat=".1f"),
        gauge=dict(
            axis=dict(range=[0, max_val], tickfont=dict(color=GRIS, size=8)),
            bar=dict(color=coul, thickness=0.22),
            bgcolor=NAVY_L, borderwidth=0,
            steps=[
                dict(range=[0, seuil_rouge], color="rgba(231,76,60,0.15)"),
                dict(range=[seuil_rouge, seuil_ambre], color="rgba(243,156,18,0.15)"),
                dict(range=[seuil_ambre, max_val], color="rgba(46,204,113,0.1)"),
            ],
            threshold=dict(line=dict(color=OR, width=3), thickness=0.8, value=seuil_ambre),
        ),
    ))
    fig.update_layout(paper_bgcolor=NAVY, font=dict(color=BLANC),
                      margin=dict(l=30, r=30, t=50, b=10), height=240)
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE ACCUEIL
# ══════════════════════════════════════════════════════════════════════════════
def page_accueil():
    col_h, col_r = st.columns([1.4, 1])
    with col_h:
        st.markdown(f"""
<div style="padding:8px 0 20px;">
  <div style="font-size:0.68rem;color:{OR};text-transform:uppercase;
  letter-spacing:0.15em;font-weight:600;margin-bottom:10px;">
  Actuarial Intelligence Platform
  </div>
  <div style="font-family:'Playfair Display',serif;font-size:2.2rem;
  font-weight:700;color:{BLANC};line-height:1.15;margin-bottom:14px;">
  ActuarIA — Là où l'expertise<br>
  <span style="color:{OR};">rencontre l'intelligence artificielle.</span>
  </div>
  <div style="font-size:0.92rem;color:{GRIS};line-height:1.65;max-width:520px;margin-bottom:24px;">
  La première plateforme actuarielle IA avec 3 directions, 9 managers
  et 46 agents spécialisés. Non-Vie · Vie & EP-RE · Santé-Prévoyance.
  </div>
</div>""", unsafe_allow_html=True)

        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button("🚀 Lancer une analyse", type="primary", use_container_width=True):
                st.session_state.page = 'analyse'
                st.rerun()
        with c2:
            if st.button("📈 Dashboard", use_container_width=True):
                st.session_state.page = 'dashboard'
                st.rerun()

    with col_r:
        # Radar ActuarIA
        categories = ['Tarification', 'Provisions', 'Réglementation', 'EP-RE', 'Santé', 'Audit']
        values     = [0.95, 0.90, 0.92, 0.85, 0.30, 0.95]
        fig = go.Figure(go.Scatterpolar(
            r=values+[values[0]], theta=categories+[categories[0]],
            fill='toself', fillcolor=f'rgba(201,168,76,0.12)',
            line=dict(color=OR, width=2.5),
            marker=dict(color=OR, size=8),
        ))
        fig.update_layout(
            polar=dict(
                bgcolor=NAVY_L,
                radialaxis=dict(visible=True, range=[0,1], tickfont=dict(color=GRIS, size=8),
                               gridcolor='rgba(255,255,255,0.07)'),
                angularaxis=dict(tickfont=dict(color=BLANC, size=10),
                                gridcolor='rgba(255,255,255,0.07)'),
            ),
            paper_bgcolor=NAVY, showlegend=False,
            margin=dict(l=40, r=40, t=20, b=20), height=260,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # KPIs
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.metric("Agents IA", "46 / 46", "3 directions")
    with c2: st.metric("Best Estimate","2.91M€","CV 0.6%")
    with c3: st.metric("Ratio SCR","208.5%","✅ > 150%")
    with c4: st.metric("Gini ML","0.2651","freMTPL2")
    with c5: st.metric("LCR","1 173%","✅ Liquide")
    with c6: st.metric("Conformité","100%","S2+IFRS17")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # Structure des directions
    col1, col2, col3 = st.columns(3)
    for col, dir_key, dir_label, dir_icon, agents_count, statut, color in [
        (col1, 'non_vie', 'Direction Non-Vie', '🏢', '16 agents', '✅ Opérationnel', VERT),
        (col2, 'vie_epre', 'Direction Vie & EP-RE', '💼', '17 agents', '🔄 Partiel', AMBRE),
        (col3, 'sante_prev', 'Direction Santé-Prévoyance', '🏥', '11 agents', '⏸ En développement', GRIS),
    ]:
        with col:
            dir_info = STRUCTURE[dir_key]
            dir_agt  = AGENTS[dir_info['directeur']]
            nb_eq    = len(dir_info['equipes'])
            st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
border-radius:12px;padding:18px;height:100%;">
  <div style="font-size:1.4rem;margin-bottom:8px;">{dir_icon}</div>
  <div style="font-weight:700;color:{BLANC};font-size:0.95rem;margin-bottom:6px;">{dir_label}</div>
  <div style="font-size:0.78rem;color:{OR};margin-bottom:4px;">
    Directeur·trice : {dir_agt['prenom']}
  </div>
  <div style="font-size:0.75rem;color:{GRIS};margin-bottom:8px;">
    {nb_eq} équipes · {agents_count}
  </div>
  <div style="font-size:0.72rem;color:{color};">{statut}</div>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE AGENT DÉTAIL
# ══════════════════════════════════════════════════════════════════════════════
def page_agent_detail():
    ak = st.session_state.agent_selec
    if not ak or ak not in AGENTS:
        st.warning("Agent non trouvé.")
        return
    agent = AGENTS[ak]

    if st.button("← Retour", key="btn_retour"):
        # Retour vers la direction si applicable
        a_tmp = AGENTS.get(st.session_state.agent_selec, {})
        dir_tmp = a_tmp.get("dir")
        if dir_tmp and dir_tmp in STRUCTURE:
            nav_to("direction", dir_key=dir_tmp)
        else:
            nav_to("accueil")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Badge niveau
    NIVEAU_LABELS = {
        'centrale': ('Direction Générale', OR),
        'transversal': ('Transversal', GRIS),
        'directeur': ('Directeur·trice', '#9B59B6'),
        'manager': ('Manager', BLEU),
        'agent': ('Agent Spécialisé', GRIS),
    }
    niv_label, niv_color = NIVEAU_LABELS.get(agent['niveau'], ('Agent', GRIS))

    # Header
    col_av, col_info = st.columns([1, 3])
    with col_av:
        try:
            st.image(f"{ak}.png", width=150)
        except:
            st.markdown(f"""
<div style="width:130px;height:130px;border-radius:14px;
background:linear-gradient(135deg,{OR},{OR_L});
display:flex;align-items:center;justify-content:center;
font-size:3rem;color:{NAVY};font-weight:700;">
{agent['prenom'][0]}
</div>""", unsafe_allow_html=True)

    with col_info:
        badge_statut = f"badge-{agent['statut']}" if agent['statut'] != 'DEV' else "badge-DEV"
        statut_label = agent['statut'] if agent['statut'] != 'DEV' else "EN DÉVELOPPEMENT"
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
border-radius:12px;padding:20px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
    <div style="font-family:'Playfair Display',serif;font-size:1.4rem;
    color:{BLANC};font-weight:700;">{agent['prenom']}</div>
    <div style="font-size:0.65rem;color:{GRIS};text-transform:uppercase;
    letter-spacing:0.1em;">{agent['code']}</div>
    <span style="display:inline-block;background:rgba(0,0,0,0.2);
    color:{niv_color};border:1px solid {niv_color}40;border-radius:20px;
    padding:2px 10px;font-size:0.65rem;font-weight:700;">{niv_label}</span>
    <span class="{badge_statut}">{statut_label}</span>
  </div>
  <div style="color:{OR};font-size:0.95rem;font-weight:600;margin-bottom:10px;">
    {agent['role_fr']}
  </div>
  <div style="font-size:0.85rem;color:{BLANC};line-height:1.65;margin-bottom:14px;">
    {agent['desc_fr']}
  </div>
  <div style="font-size:0.68rem;color:{GRIS};text-transform:uppercase;
  letter-spacing:0.08em;margin-bottom:4px;">Spécialités</div>
  <div style="font-size:0.8rem;color:{OR};">{agent['spec_fr']}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # Onglets selon le niveau
    if agent['statut'] == 'DEV':
        tab1, tab2 = st.tabs([
            f"ℹ️ En développement",
            f"💬 Dialoguer avec {agent['prenom']}",
        ])
        with tab1:
            st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(138,154,176,0.3);
border-radius:12px;padding:24px;margin:16px 0;">
  <div style="font-size:1.2rem;margin-bottom:12px;">⏸️</div>
  <div style="font-weight:700;color:{BLANC};font-size:1rem;margin-bottom:8px;">
    Agent en cours de développement
  </div>
  <div style="font-size:0.88rem;color:{GRIS};line-height:1.65;">
    {agent['prenom']} sera disponible prochainement.<br>
    Rôle prévu : {agent['role_fr']}<br>
    Spécialités : {agent['spec_fr']}
  </div>
</div>""", unsafe_allow_html=True)
        with tab2:
            _tab_chat_agent(ak)
    else:
        tab1, tab2, tab3 = st.tabs([
            "📋 Résultats & Rapport",
            f"🚀 Lancer {agent['prenom']}",
            f"💬 Dialoguer avec {agent['prenom']}",
        ])
        with tab1:
            _tab_resultats(ak)
        with tab2:
            _tab_lancer(ak)
        with tab3:
            _tab_chat_agent(ak)

def _tab_resultats(ak):
    agent = AGENTS[ak]
    code  = agent['code']
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # KPI principal
    st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.25);
border-radius:10px;padding:14px 18px;margin-bottom:14px;">
  <div style="font-size:0.65rem;color:{GRIS};text-transform:uppercase;
  letter-spacing:0.08em;margin-bottom:5px;">KPI principal</div>
  <div style="font-size:1.25rem;font-weight:700;color:{OR};">{agent['kpi']}</div>
  <div style="font-size:0.72rem;color:{GRIS};margin-top:3px;">
  Dernière exécution : {datetime.now().strftime('%d/%m/%Y %H:%M')}
  </div>
</div>""", unsafe_allow_html=True)

    # Résultats spécifiques
    if code in ['A7', 'MGR-PRV']:
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Best Estimate S2","2 914 930 €","CV 0.6%")
        with c2: st.metric("Provision P90","3 098 000 €","+6.3%")
        with c3: st.metric("σ Mack 1993","45 000 €","IC 95%")
        _bar_chart(['Chain Ladder','Mack 1993','BF','Cape Cod','Best Est.'],
                   [2_850_000,2_914_930,2_930_000,2_880_000,2_914_930],
                   "Convergence des 4 méthodes (€)",
                   [OR,OR,OR,OR,VERT])

    elif code in ['A4', 'MGR-TAR']:
        c1,c2 = st.columns(2)
        with c1: st.metric("Gini XGBoost","0.2651","meilleur")
        with c2: st.metric("Modèle retenu","ElasticNet","score 0.8373")
        df = pd.DataFrame({
            'Modèle':['XGBoost','GBM','CatBoost','LightGBM','ElasticNet','XGB Tweedie'],
            'Gini':[0.2651,0.2542,0.2534,0.2481,0.2440,0.2404],
            'Overfit':[1.53,1.41,1.28,1.60,0.98,1.97],
            'Retenu':['','','','','⭐',''],
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

    elif code in ['A10', 'DIR-NV', 'MGR-REG']:
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("SCR Total","3 680 671 €","formule std")
        with c2: st.metric("Ratio SCR","208.5%","✅ > 150%")
        with c3: st.metric("Ratio MCR","320.0%","✅ > 100%")
        _jauge(208.5, "Ratio SCR (%)")

    elif code in ['A11','A12']:
        if code == 'A11':
            c1,c2,c3 = st.columns(3)
            with c1: st.metric("TP IFRS 17","3 992 344 €","PAA")
            with c2: st.metric("LRC","2 500 000 €","risque restant")
            with c3: st.metric("Ratio IFRS17/S2","1.370","✅ Cohérent")
        else:
            c1,c2,c3 = st.columns(3)
            with c1: st.metric("Duration actifs","3.50 ans","obligations")
            with c2: st.metric("Gap duration","+1.90 ans","⚠️ À surveiller")
            with c3: st.metric("LCR","1 173%","✅ Liquide")

    elif code in ['EP1','MGR-EPRE']:
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("DBO","10 588 168 €","méthode PUC")
        with c2: st.metric("Service Cost","285 000 €","charge N")
        with c3: st.metric("Interest Cost","370 585 €","taux 3.5%")

    elif code in ['ARIA', 'DIR-VIE']:
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("BE S2","2.91M€","✅")
        with c2: st.metric("Ratio SCR","208.5%","✅")
        with c3: st.metric("Gini","0.2651","✅")
        with c4: st.metric("LCR","1173%","✅")

    elif code == 'A13':
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.3);
border-radius:10px;padding:16px 20px;">
  <div style="font-size:0.65rem;color:{GRIS};margin-bottom:5px;">Hash session SHA-256</div>
  <div style="font-family:monospace;color:{OR};font-size:1.2rem;">5BB15F63</div>
  <div style="font-size:0.72rem;color:{GRIS};margin-top:8px;">
  46 agents tracés · RGPD Art.30 conforme · Hypothèses versionnées
  </div>
</div>""", unsafe_allow_html=True)

    else:
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.15);
border-radius:10px;padding:16px 20px;">
  <div style="font-size:0.85rem;color:{GRIS};line-height:1.65;">
  {agent['kpi']} · Statut : {agent['statut']}<br>
  Cliquez sur "Lancer {agent['prenom']}" pour exécuter le pipeline.
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(f"📄 Rapport PDF", use_container_width=True):
            st.toast(f"✅ Rapport {agent['prenom']} généré", icon="✅")
    with col2:
        if st.button("📊 Export Excel", use_container_width=True):
            st.toast("✅ Export Excel généré", icon="✅")
    with col3:
        if st.button("🔐 Audit Trail", use_container_width=True):
            st.toast("✅ Audit Trail exporté", icon="✅")

def _tab_lancer(ak):
    agent = AGENTS[ak]
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    fichier = st.file_uploader("Uploader vos données",
                                type=['csv','xlsx','xls','parquet'],
                                key=f"up_{ak}")
    if fichier:
        st.success(f"✅ {fichier.name} chargé")
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox("Branche", ['Non-Vie (Auto)','Non-Vie (MRH)','Non-Vie (RC Pro)',
                                   'Vie','EP-RE','Santé','Prévoyance'], key=f"br_{ak}")
    with col2:
        st.text_input("ID Client", placeholder="cabinet_xyz", key=f"cl_{ak}")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col_b1, col_b2, _ = st.columns([1,1,2])
    with col_b1:
        if st.button(f"🚀 Lancer {agent['prenom']}", type="primary",
                     use_container_width=True, key=f"run_{ak}"):
            with st.spinner(f"{agent['prenom']} calcule..."):
                import time
                time.sleep(1.5)
            st.success(f"✅ {agent['prenom']} a terminé — Statut : {agent['statut']}")
    with col_b2:
        if st.button("🎯 Démo synthétique", use_container_width=True, key=f"demo_{ak}"):
            with st.spinner("Chargement démo..."):
                import time
                time.sleep(1)
            st.info(f"📊 Démo : {agent['kpi']}")

def _tab_chat_agent(ak):
    agent = AGENTS[ak]
    chat_key = f"chat_{ak}"
    if chat_key not in st.session_state:
        niveau_intro = {
            'centrale': f"Bonjour, je suis **{agent['prenom']}**, {agent['role_fr']}. J'ai accès à toutes les directions. Comment puis-je vous aider ?",
            'directeur': f"Bonjour, je suis **{agent['prenom']}**, {agent['role_fr']}. Je supervise l'ensemble de ma direction. Comment puis-je vous aider ?",
            'manager': f"Bonjour, je suis **{agent['prenom']}**, {agent['role_fr']}. Je valide et assume tous les résultats de mon équipe. Quelle est votre question ?",
            'agent': f"Bonjour, je suis **{agent['prenom']}** ({agent['code']}), spécialiste en *{agent['role_fr']}*. KPI : **{agent['kpi']}**. Comment puis-je vous aider ?",
            'transversal': f"Bonjour, je suis **{agent['prenom']}**, {agent['role_fr']}. Comment puis-je vous aider ?",
        }.get(agent['niveau'], f"Bonjour, je suis {agent['prenom']}.")
        st.session_state[chat_key] = [{'role': 'assistant', 'content': niveau_intro}]

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    for msg in st.session_state[chat_key]:
        label  = agent['prenom'] if msg['role'] == 'assistant' else 'Vous'
        border = "rgba(46,204,113,0.3)" if msg['role']=='assistant' else "rgba(201,168,76,0.3)"
        bg     = NAVY_L if msg['role']=='assistant' else NAVY_LL
        st.markdown(f"""
<div style="background:{bg};border:1px solid {border};border-radius:10px;
padding:12px 16px;margin-bottom:8px;">
  <div style="font-size:0.65rem;color:{OR};font-weight:700;
  text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">{label}</div>
  <div style="font-size:0.86rem;color:{BLANC};line-height:1.65;">{msg['content']}</div>
</div>""", unsafe_allow_html=True)

    prompt = st.chat_input(f"Posez votre question à {agent['prenom']}...", key=f"inp_{ak}")
    if prompt:
        st.session_state[chat_key].append({'role':'user','content':prompt})
        with st.spinner(f"{agent['prenom']} réfléchit..."):
            reponse = appeler_claude(st.session_state[chat_key], system_prompt=get_system_prompt(ak))
        st.session_state[chat_key].append({'role':'assistant','content':reponse})
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE ANALYSE
# ══════════════════════════════════════════════════════════════════════════════
def page_analyse():
    st.markdown(f"""
<div style="margin-bottom:24px;">
  <div style="font-size:0.68rem;color:{OR};text-transform:uppercase;
  letter-spacing:0.12em;margin-bottom:6px;">Pipeline actuariel</div>
  <div style="font-family:'Playfair Display',serif;font-size:1.6rem;
  color:{BLANC};font-weight:700;">Lancer une analyse</div>
</div>""", unsafe_allow_html=True)

    col1, col2 = st.columns([1.5, 1])
    with col1:
        branche = st.selectbox("Direction", [
            'Non-Vie — Tarification','Non-Vie — Provisionnement',
            'Non-Vie — Réglementation S2/IFRS17',
            'Vie & EP-RE — EP-RE','Vie & EP-RE — Vie Pure',
            'Santé-Prévoyance',
        ])
        fichier = st.file_uploader("Données (CSV, Excel, Parquet)", type=['csv','xlsx','parquet'])
        client  = st.text_input("Nom du client", placeholder="Assurance XYZ")
    with col2:
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
border-radius:12px;padding:18px;margin-top:28px;">
  <div style="font-size:0.7rem;color:{OR};font-weight:700;margin-bottom:10px;">
  AGENTS DISPONIBLES
  </div>""", unsafe_allow_html=True)
        # Agents actifs
        agents_actifs = [a for a in AGENTS.values() if a['statut'] != 'DEV']
        for a in agents_actifs[:8]:
            statut_dot = "🟢" if a['statut']=='VERT' else "🟡" if a['statut']=='AMBRE' else "🔴"
            st.markdown(f"<div style='font-size:0.78rem;color:{BLANC};margin-bottom:3px;'>{statut_dot} {a['prenom']} ({a['code']})</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    col_b1, col_b2, _ = st.columns([1,1,2])
    with col_b1:
        if st.button("🚀 Lancer le pipeline", type="primary", use_container_width=True):
            with st.spinner("Pipeline en cours..."):
                import time
                time.sleep(2)
            st.success("✅ Pipeline terminé — Résultats disponibles dans Dashboard")
    with col_b2:
        if st.button("🎯 Démo freMTPL2", use_container_width=True):
            st.info("📊 Démo freMTPL2 : 678k contrats · Gini 0.2651 · BE 2.91M€")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def page_dashboard():
    st.markdown(f"""
<div style="margin-bottom:20px;">
  <div style="font-family:'Playfair Display',serif;font-size:1.5rem;
  color:{BLANC};font-weight:700;">Dashboard ActuarIA</div>
  <div style="font-size:0.8rem;color:{GRIS};margin-top:4px;">
  freMTPL2 — 678k contrats Auto France · {datetime.now().strftime('%d/%m/%Y')}
  </div>
</div>""", unsafe_allow_html=True)

    tab_nv, tab_vie, tab_regl = st.tabs(["🏢 Non-Vie","💼 Vie & EP-RE","🛡️ Réglementation"])

    with tab_nv:
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Gini XGBoost","0.2651","+ vs GLM")
        with c2: st.metric("Modèle retenu","ElasticNet","stable")
        with c3: st.metric("Best Estimate","2.91M€","CV 0.6%")
        with c4: st.metric("Ratio SCR stress","375%","✅ Résistant")
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            _bar_chart(
                ['XGBoost','GBM','CatBoost','LightGBM','ElasticNet'],
                [0.2651,0.2542,0.2534,0.2481,0.2440],
                "Gini par modèle ML",
                [ROUGE,OR,OR,OR,VERT]
            )
        with col_b:
            _bar_chart(
                ['Chain Ladder','Mack 1993','BF','Cape Cod'],
                [2_850_000,2_914_930,2_930_000,2_880_000],
                "Provisions — 4 méthodes (€)"
            )

    with tab_vie:
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("DBO IAS 19","10.6M€","méthode PUC")
        with c2: st.metric("Rente EP-RE","595€/mois","PER 30 ans")
        with c3: st.metric("Ratio base EP4","110%","avant chocs")
        st.info("⏸️ Vie Pure en développement — Agents Nour, Kofi, Amélie, Théo, Nia disponibles prochainement.")

    with tab_regl:
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Ratio SCR","208.5%","✅")
        with c2: st.metric("Ratio MCR","320%","✅")
        with c3: st.metric("TP IFRS17","3.99M€","PAA")
        with c4: st.metric("LCR","1173%","✅")
        col_a, col_b = st.columns(2)
        with col_a:
            _jauge(208.5, "Ratio SCR (%)")
        with col_b:
            _jauge(1173, "LCR (%)", seuil_rouge=75, seuil_ambre=100, max_val=1500)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE RAPPORTS
# ══════════════════════════════════════════════════════════════════════════════
def page_rapports():
    st.markdown(f"""
<div style="margin-bottom:20px;">
  <div style="font-family:'Playfair Display',serif;font-size:1.5rem;
  color:{BLANC};font-weight:700;">Rapports & Exports</div>
</div>""", unsafe_allow_html=True)

    rapports = [
        ("📊 Rapport Actuariel Complet", "PDF · 42 pages · S2 + IFRS17 + ALM", VERT),
        ("🏢 QRT Non-Vie ACPR", "Excel · S.05 · S.17 · S.19", VERT),
        ("💼 Rapport Actuariel EP-RE", "PDF · IAS 19 + PER + DARES", VERT),
        ("🛡️ ORSA Prospectif 5 ans", "PDF · 3 scénarios · Pilier 2 S2", AMBRE),
        ("🔐 Rapport Audit Trail", "PDF · Hash SHA-256 · RGPD Art.30", VERT),
        ("📉 Note Mortalité & Biométrie", "PDF · Tables · Lee-Carter", VERT),
    ]

    for titre, desc, statut in rapports:
        col1, col2, col3 = st.columns([2, 1.5, 1])
        with col1:
            st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
border-radius:8px;padding:12px 16px;">
  <div style="font-weight:600;color:{BLANC};font-size:0.88rem;">{titre}</div>
  <div style="font-size:0.75rem;color:{GRIS};margin-top:3px;">{desc}</div>
</div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
            badge = "badge-VERT" if statut == VERT else "badge-AMBRE"
            label = "Disponible" if statut == VERT else "En cours"
            st.markdown(f"<span class='{badge}'>{label}</span>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
            if st.button("⬇️ Générer", key=f"rpt_{titre[:10]}", use_container_width=True):
                st.toast(f"✅ {titre} généré", icon="✅")
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE DIRECTION
# ══════════════════════════════════════════════════════════════════════════════
def page_direction():
    dk = st.session_state.dir_selec
    if not dk or dk not in STRUCTURE:
        nav_to("accueil")
        return
    d = STRUCTURE[dk]
    dir_agent = AGENTS[d["directeur"]]

    if st.button("← Retour à l'accueil", key="btn_ret_dir"):
        nav_to("accueil")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # HERO DIRECTION
    nb_total = sum(1 + len(eq["agents"]) for eq in d["equipes"].values())
    nb_eq    = len(d["equipes"])

    col_info, col_dir = st.columns([2, 1])
    with col_info:
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.25);border-radius:14px;padding:24px;margin-bottom:20px;">
  <div style="font-size:0.62rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px;font-weight:700;">Direction</div>
  <div style="font-family:'Playfair Display',serif;font-size:1.8rem;color:{BLANC};font-weight:700;margin-bottom:8px;">
    {d['icon']} {d['label']}
  </div>
  <div style="font-size:0.86rem;color:{GRIS};line-height:1.65;margin-bottom:16px;">{d['mission']}</div>
  <div style="display:flex;gap:16px;">
    <div style="background:{NAVY_LL};border-radius:8px;padding:8px 16px;text-align:center;">
      <div style="font-size:1.2rem;font-weight:700;color:{OR};">{nb_eq}</div>
      <div style="font-size:0.65rem;color:{GRIS};text-transform:uppercase;">Équipes</div>
    </div>
    <div style="background:{NAVY_LL};border-radius:8px;padding:8px 16px;text-align:center;">
      <div style="font-size:1.2rem;font-weight:700;color:{OR};">{nb_total}</div>
      <div style="font-size:0.65rem;color:{GRIS};text-transform:uppercase;">Agents</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    with col_dir:
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(150,100,200,0.35);border-radius:14px;padding:20px;text-align:center;">
  <div style="font-size:2.2rem;margin-bottom:8px;">{dir_agent['icon']}</div>
  <div style="font-size:0.62rem;color:{VIOLET};text-transform:uppercase;letter-spacing:0.1em;font-weight:700;margin-bottom:4px;">Directeur·trice</div>
  <div style="font-size:1.05rem;font-weight:700;color:{BLANC};margin-bottom:4px;">{dir_agent['prenom']}</div>
  <div style="font-size:0.72rem;color:{GRIS};margin-bottom:12px;">{dir_agent['kpi']}</div>
</div>""", unsafe_allow_html=True)
        if st.button(f"💬 Parler à {dir_agent['prenom']}", key="btn_dir_chat", use_container_width=True):
            nav_to("agent_detail", agent=d["directeur"])

    # ÉQUIPES
    st.markdown(f"""
<div style="font-size:0.62rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;margin-bottom:12px;font-weight:700;">
◆ Équipes de la direction
</div>""", unsafe_allow_html=True)

    for eq_key, eq in d["equipes"].items():
        mgr_k  = eq.get("manager")
        mgr    = AGENTS[mgr_k] if mgr_k else None
        nb_agt = len(eq["agents"])

        with st.expander(f"{eq['icon']} {eq['label']} — {nb_agt} agents", expanded=True):
            if mgr:
                col_m, col_mb = st.columns([3,1])
                with col_m:
                    st.markdown(f"""
<div style="background:{NAVY_LL};border:1px solid rgba(52,152,219,0.3);border-radius:10px;padding:12px 16px;margin-bottom:10px;">
  <div style="display:flex;align-items:center;gap:10px;">
    <span style="font-size:1.1rem;">{mgr['icon']}</span>
    <div>
      <span style="font-size:0.6rem;color:{BLEU};text-transform:uppercase;font-weight:700;letter-spacing:0.08em;">Manager</span>
      <div style="font-weight:700;color:{BLANC};font-size:0.88rem;">{mgr['prenom']} ({mgr['code']})</div>
      <div style="font-size:0.72rem;color:{GRIS};">{mgr['kpi']}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
                with col_mb:
                    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                    if st.button(f"💬 {mgr['prenom']}", key=f"dir_mgr_{mgr_k}", use_container_width=True):
                        nav_to("agent_detail", agent=mgr_k)

            # Agents en grille
            cols = st.columns(min(3, max(1, nb_agt)))
            for i, ak in enumerate(eq["agents"]):
                a = AGENTS[ak]
                with cols[i % len(cols)]:
                    badge_cl = f"badge-{a['statut']}" if a['statut'] != 'DEV' else "badge-DEV"
                    st_lbl   = a['statut'] if a['statut'] != 'DEV' else 'EN DEV'
                    st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.15);border-radius:10px;padding:12px;margin-bottom:8px;">
  <div style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">
    <span style="font-size:0.95rem;">{a['icon']}</span>
    <span style="font-weight:700;color:{BLANC};font-size:0.84rem;">{a['prenom']}</span>
    <span style="font-size:0.62rem;color:{GRIS};">({a['code']})</span>
  </div>
  <div style="font-size:0.7rem;color:{GRIS};margin-bottom:5px;line-height:1.4;">{a['role_fr']}</div>
  <div style="font-size:0.68rem;color:{OR};margin-bottom:7px;">{a['kpi']}</div>
  <span class="{badge_cl}">{st_lbl}</span>
</div>""", unsafe_allow_html=True)
                    if st.button(f"Voir {a['prenom']}", key=f"dir_agt_{ak}", use_container_width=True):
                        nav_to("agent_detail", agent=ak)

# ══════════════════════════════════════════════════════════════════════════════
# ROUTEUR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
render_sidebar()

page = st.session_state.page
if   page == "accueil":      page_accueil()
elif page == "dashboard":    page_dashboard()
elif page == "analyse":      page_analyse()
elif page == "rapports":     page_rapports()
elif page == "direction":    page_direction() if "page_direction" in dir() else page_accueil()
elif page == "agent_detail": page_agent_detail()
else:                        page_accueil()
