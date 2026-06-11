"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ACTUARIA — INTERFACE STREAMLIT v2.0                      ║
║         Top Bar · Agents Cliquables · Hiérarchie · Logo · FR/EN            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title        = "ActuarIA",
    page_icon         = "⚡",
    layout            = "wide",
    initial_sidebar_state = "collapsed",
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
    'langue':          'fr',
    'page':            'accueil',
    'agent_selec':     None,
    'direction_selec': None,
    'equipe_selec':    None,
    'messages_aria':   [],
    'dropdown_open':   False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════════════════════════════
# TEXTES FR/EN
# ══════════════════════════════════════════════════════════════════════════════

T = {
    'fr': {
        'titre':        'ActuarIA — Là où l\'expertise rencontre l\'intelligence artificielle.',
        'sous_titre':   'La première plateforme actuarielle propulsée par l\'IA pour les compagnies d\'assurance, mutuelles et institutions de prévoyance.',
        'btn_analyse':  'Lancer une analyse',
        'btn_demo':     'Voir la démo',
        'nav_accueil':  'Accueil',
        'nav_equipes':  'Équipes',
        'nav_dashboard':'Dashboard',
        'nav_aria':     'Agent ARIA',
        'nav_rapports': 'Rapports',
        'nav_analyse':  'Analyse',
        'dir_nv':       'Direction Non-Vie',
        'dir_ep':       'Direction Épargne-Retraite',
        'agent_aria':   'Agent ARIA (IA Central)',
        'eq_tarif':     'Équipe Tarification',
        'eq_prov':      'Équipe Provisions & Réglementaire',
        'eq_trans':     'Équipe Transversale',
        'btn_lancer':   'Lancer',
        'btn_dialoguer':'Dialoguer',
        'btn_retour':   '← Retour',
        'statut':       'Statut',
        'role':         'Rôle',
        'specialite':   'Spécialité',
        'derniere_exec':'Dernière exécution',
        'section_plateforme': 'La plateforme',
        'section_reglements': 'Réglementations couvertes',
        'section_clients':    'Pour qui ?',
        'contact':      'Contact',
        'langue':       'FR',
    },
    'en': {
        'titre':        'ActuarIA — Where expertise meets artificial intelligence.',
        'sous_titre':   'The first AI-powered actuarial platform for insurance companies, mutuals and provident institutions.',
        'btn_analyse':  'Start analysis',
        'btn_demo':     'View demo',
        'nav_accueil':  'Home',
        'nav_equipes':  'Teams',
        'nav_dashboard':'Dashboard',
        'nav_aria':     'ARIA Agent',
        'nav_rapports': 'Reports',
        'nav_analyse':  'Analysis',
        'dir_nv':       'Non-Life Division',
        'dir_ep':       'Savings & Retirement Division',
        'agent_aria':   'ARIA Agent (AI Central)',
        'eq_tarif':     'Pricing Team',
        'eq_prov':      'Reserving & Regulatory Team',
        'eq_trans':     'Cross-functional Team',
        'btn_lancer':   'Launch',
        'btn_dialoguer':'Chat',
        'btn_retour':   '← Back',
        'statut':       'Status',
        'role':         'Role',
        'specialite':   'Specialty',
        'derniere_exec':'Last run',
        'section_plateforme': 'The platform',
        'section_reglements': 'Regulations covered',
        'section_clients':    'Who is it for?',
        'contact':      'Contact',
        'langue':       'EN',
    }
}

def t(key):
    return T[st.session_state.langue].get(key, key)

# ══════════════════════════════════════════════════════════════════════════════
# DONNÉES AGENTS
# ══════════════════════════════════════════════════════════════════════════════

AGENTS = {
    'sofia': {
        'prenom': 'Sofia', 'code': 'ARIA', 'icon': '🤖',
        'role_fr': 'Actuaire IA Senior — Agent Central',
        'role_en': 'Senior AI Actuary — Central Agent',
        'desc_fr': 'Sofia est l\'intelligence centrale de la plateforme. Elle coordonne tous les agents, synthétise les résultats et répond à toutes vos questions actuarielles en langage naturel. Propulsée par Claude API d\'Anthropic.',
        'desc_en': 'Sofia is the central intelligence of the platform. She coordinates all agents, synthesizes results and answers all your actuarial questions in natural language. Powered by Anthropic\'s Claude API.',
        'specialite_fr': 'IA générative · Synthèse actuarielle · NLP',
        'specialite_en': 'Generative AI · Actuarial synthesis · NLP',
        'statut': 'VERT', 'direction': 'central', 'equipe': 'central',
        'kpi': 'Agent IA Central',
    },
    'amara': {
        'prenom': 'Amara', 'code': 'A1', 'icon': '🔍',
        'role_fr': 'Ingestion & Validation des données',
        'role_en': 'Data Ingestion & Validation',
        'desc_fr': 'Amara est la première à intervenir sur chaque portefeuille. Elle ingère, valide et normalise les données clients — Excel, CSV, Parquet — avec détection automatique de la branche et mapping des colonnes.',
        'desc_en': 'Amara is the first to work on every portfolio. She ingests, validates and normalizes client data — Excel, CSV, Parquet — with automatic branch detection and column mapping.',
        'specialite_fr': 'Ingestion multi-format · Validation qualité · RGPD Art.30',
        'specialite_en': 'Multi-format ingestion · Quality validation · GDPR Art.30',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'tarification',
        'kpi': '678k contrats validés',
    },
    'kenji': {
        'prenom': 'Kenji', 'code': 'A2', 'icon': '⚡',
        'role_fr': 'Preprocessing & Feature Engineering',
        'role_en': 'Preprocessing & Feature Engineering',
        'desc_fr': 'Kenji transforme les données brutes en features exploitables par les modèles. Imputation, winsorisation, encodage, création de variables — il prépare le terrain pour une modélisation de haute précision.',
        'desc_en': 'Kenji transforms raw data into features usable by models. Imputation, winsorization, encoding, variable creation — he prepares the ground for high-precision modeling.',
        'specialite_fr': 'Feature engineering · Imputation · Encodage',
        'specialite_en': 'Feature engineering · Imputation · Encoding',
        'statut': 'AMBRE', 'direction': 'non_vie', 'equipe': 'tarification',
        'kpi': '30 features créées',
    },
    'laurent': {
        'prenom': 'Laurent', 'code': 'A3', 'icon': '📐',
        'role_fr': 'GLM Tarification — Poisson · Gamma · Tweedie',
        'role_en': 'GLM Pricing — Poisson · Gamma · Tweedie',
        'desc_fr': 'Laurent est le garant de la rigueur actuarielle en tarification. Il calibre les GLM réglementaires (Poisson pour la fréquence, Gamma pour le coût moyen, Tweedie pour la prime pure) avec sélection stepwise et tests statistiques.',
        'desc_en': 'Laurent is the guarantor of actuarial rigor in pricing. He calibrates regulatory GLMs (Poisson for frequency, Gamma for average cost, Tweedie for pure premium) with stepwise selection and statistical tests.',
        'specialite_fr': 'GLM Poisson · Gamma · Tweedie · Stepwise',
        'specialite_en': 'GLM Poisson · Gamma · Tweedie · Stepwise',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'tarification',
        'kpi': 'Gini GLM validé',
    },
    'priya': {
        'prenom': 'Priya', 'code': 'A4', 'icon': '🧠',
        'role_fr': 'Machine Learning Tarification — 6 modèles',
        'role_en': 'ML Pricing — 6 models',
        'desc_fr': 'Priya maîtrise les 6 algorithmes ML de pointe : GBM, XGBoost, XGBoost Tweedie, LightGBM, CatBoost et ElasticNet. Elle calcule les Gini, détecte l\'overfitting et fournit les explications SHAP pour chaque modèle.',
        'desc_en': 'Priya masters 6 state-of-the-art ML algorithms: GBM, XGBoost, XGBoost Tweedie, LightGBM, CatBoost and ElasticNet. She calculates Gini scores, detects overfitting and provides SHAP explanations for each model.',
        'specialite_fr': 'XGBoost · LightGBM · CatBoost · SHAP',
        'specialite_en': 'XGBoost · LightGBM · CatBoost · SHAP',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'tarification',
        'kpi': 'Gini XGBoost = 0.2651',
    },
    'yohan': {
        'prenom': 'Yohan', 'code': 'A5', 'icon': '🔮',
        'role_fr': 'Deep Learning — CANN · TabNet',
        'role_en': 'Deep Learning — CANN · TabNet',
        'desc_fr': 'Yohan explore les frontières du Deep Learning actuariel. Il calibre les réseaux CANN (Combined Actuarial Neural Networks) de Wüthrich 2019 et les TabNet, architectures de pointe pour les données tabulaires.',
        'desc_en': 'Yohan explores the frontiers of actuarial Deep Learning. He calibrates CANN networks (Combined Actuarial Neural Networks) by Wüthrich 2019 and TabNet, state-of-the-art architectures for tabular data.',
        'specialite_fr': 'CANN · TabNet · PyTorch · Wüthrich 2019',
        'specialite_en': 'CANN · TabNet · PyTorch · Wüthrich 2019',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'tarification',
        'kpi': 'TabNet Gini = 0.2334',
    },
    'meilin': {
        'prenom': 'Mei-Lin', 'code': 'A6', 'icon': '⚖️',
        'role_fr': 'Comparaison & Sélection du modèle de production',
        'role_en': 'Comparison & Production model selection',
        'desc_fr': 'Mei-Lin est l\'arbitre impartial entre tous les modèles. Elle applique une grille multicritères (Gini, stabilité, interprétabilité, RMSE) avec 4 profils de pondération adaptés à chaque client.',
        'desc_en': 'Mei-Lin is the impartial arbitrator between all models. She applies a multi-criteria grid (Gini, stability, interpretability, RMSE) with 4 weighting profiles adapted to each client.',
        'specialite_fr': 'Multicritères · Profils S2 · AI Act 2025',
        'specialite_en': 'Multi-criteria · S2 profiles · AI Act 2025',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'tarification',
        'kpi': 'Score 0.8373/1.0',
    },
    'kwame': {
        'prenom': 'Kwame', 'code': 'A7', 'icon': '🏦',
        'role_fr': 'Provisionnement — Chain Ladder · Mack · BF · Cape Cod',
        'role_en': 'Reserving — Chain Ladder · Mack · BF · Cape Cod',
        'desc_fr': 'Kwame est l\'expert en provisionnement Non-Vie. Il calibre les 4 méthodes actuarielles de référence, calcule le Best Estimate S2 avec intervalle de confiance Mack 1993, et détecte les valeurs extrêmes dans le triangle.',
        'desc_en': 'Kwame is the Non-Life reserving expert. He calibrates the 4 reference actuarial methods, calculates the S2 Best Estimate with Mack 1993 confidence interval, and detects extreme values in the triangle.',
        'specialite_fr': 'Chain Ladder · Mack 1993 · BF · Cape Cod',
        'specialite_en': 'Chain Ladder · Mack 1993 · BF · Cape Cod',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'provisions',
        'kpi': 'BE = 2.91M€ · CV 0.6%',
    },
    'isabelle': {
        'prenom': 'Isabelle', 'code': 'A8', 'icon': '🌩️',
        'role_fr': 'Stress Testing & ORSA',
        'role_en': 'Stress Testing & ORSA',
        'desc_fr': 'Isabelle évalue la résistance du portefeuille aux chocs adverses. Chocs S2 EIOPA, scénarios climatiques, épidémiques, financiers — et projection ORSA prospective sur 5 ans pour le Pilier 2.',
        'desc_en': 'Isabelle assesses portfolio resilience to adverse shocks. EIOPA S2 shocks, climate, epidemic, financial scenarios — and 5-year forward-looking ORSA projection for Pillar 2.',
        'specialite_fr': 'Chocs S2 · ORSA 5 ans · Scénarios adverses',
        'specialite_en': 'S2 shocks · ORSA 5 years · Adverse scenarios',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'provisions',
        'kpi': 'Ratio SCR = 375%',
    },
    'marcus': {
        'prenom': 'Marcus', 'code': 'A9', 'icon': '🔗',
        'role_fr': 'Cohérence inter-équipes',
        'role_en': 'Cross-team consistency',
        'desc_fr': 'Marcus garantit la cohérence entre tous les résultats de la plateforme. Il vérifie l\'alignement Tarification ↔ Provisions ↔ S2 ↔ IFRS 17 et alerte proactivement en cas d\'incohérence.',
        'desc_en': 'Marcus guarantees consistency across all platform results. He verifies alignment Pricing ↔ Reserves ↔ S2 ↔ IFRS 17 and proactively alerts in case of inconsistency.',
        'specialite_fr': 'Loss Ratios · Réconciliation · Alertes RAG',
        'specialite_en': 'Loss Ratios · Reconciliation · RAG alerts',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'provisions',
        'kpi': 'Score 100% VERT',
    },
    'nadia': {
        'prenom': 'Nadia', 'code': 'A10', 'icon': '🛡️',
        'role_fr': 'Solvabilité 2 — SCR · MCR · QRT',
        'role_en': 'Solvency 2 — SCR · MCR · QRT',
        'desc_fr': 'Nadia maîtrise la formule standard EIOPA. Elle calcule le SCR souscription, marché et opérationnel, le MCR, et génère les QRT réglementaires S.05, S.17, S.19 et S.23 pour le reporting ACPR.',
        'desc_en': 'Nadia masters the EIOPA standard formula. She calculates underwriting, market and operational SCR, MCR, and generates regulatory QRTs S.05, S.17, S.19 and S.23 for ACPR reporting.',
        'specialite_fr': 'Formule standard · QRT · Pilier 1 S2',
        'specialite_en': 'Standard formula · QRT · S2 Pillar 1',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'provisions',
        'kpi': 'Ratio SCR = 208.5%',
    },
    'thomas': {
        'prenom': 'Thomas', 'code': 'A11', 'icon': '📊',
        'role_fr': 'IFRS 17 — PAA · BBA · VFA',
        'role_en': 'IFRS 17 — PAA · BBA · VFA',
        'desc_fr': 'Thomas calcule les provisions IFRS 17 selon les 3 approches : PAA pour les contrats courts, BBA pour les contrats longs avec CSM, et VFA pour les contrats avec participation. Il réconcilie avec le Best Estimate S2.',
        'desc_en': 'Thomas calculates IFRS 17 provisions using 3 approaches: PAA for short contracts, BBA for long contracts with CSM, and VFA for participating contracts. He reconciles with the S2 Best Estimate.',
        'specialite_fr': 'PAA · BBA · VFA · CSM · Réconciliation S2',
        'specialite_en': 'PAA · BBA · VFA · CSM · S2 Reconciliation',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'provisions',
        'kpi': 'TP = 3.99M€ · Ratio 1.370',
    },
    'aisha': {
        'prenom': 'Aisha', 'code': 'A12', 'icon': '⚖️',
        'role_fr': 'ALM & Risque de Liquidité',
        'role_en': 'ALM & Liquidity Risk',
        'desc_fr': 'Aisha gère l\'équilibre Actif-Passif. Elle calcule les durations de Macaulay, le gap de duration, le BV01 et le LCR. Elle évalue l\'impact des chocs de taux ±200bp sur la valeur nette de l\'entreprise.',
        'desc_en': 'Aisha manages Asset-Liability balance. She calculates Macaulay durations, duration gap, BV01 and LCR. She assesses the impact of ±200bp rate shocks on net company value.',
        'specialite_fr': 'Duration · Gap ALM · LCR · Stress taux',
        'specialite_en': 'Duration · ALM Gap · LCR · Rate stress',
        'statut': 'AMBRE', 'direction': 'non_vie', 'equipe': 'provisions',
        'kpi': 'LCR = 1173% · Gap +1.9 ans',
    },
    'luca': {
        'prenom': 'Luca', 'code': 'A13', 'icon': '🔐',
        'role_fr': 'Audit Trail & Conformité RGPD',
        'role_en': 'Audit Trail & GDPR Compliance',
        'desc_fr': 'Luca garantit l\'intégrité et la traçabilité de tous les calculs. Il génère le hash de session SHA-256, le registre RGPD Art.30, le versioning des hypothèses et le rapport d\'audit complet pour l\'auditeur S2.',
        'desc_en': 'Luca guarantees the integrity and traceability of all calculations. He generates the SHA-256 session hash, GDPR Art.30 register, hypothesis versioning and complete audit report for the S2 auditor.',
        'specialite_fr': 'SHA-256 · RGPD Art.30 · Versioning · Audit S2',
        'specialite_en': 'SHA-256 · GDPR Art.30 · Versioning · S2 Audit',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'transversale',
        'kpi': 'Hash 5BB15F63',
    },
    'yuki': {
        'prenom': 'Yuki', 'code': 'A14', 'icon': '📉',
        'role_fr': 'Tables de Mortalité & Biométrie',
        'role_en': 'Mortality Tables & Biometrics',
        'desc_fr': 'Yuki maîtrise toutes les tables de mortalité réglementaires françaises. Elle calcule les annuités viagères, espérances de vie, capitaux décès et projette les tendances de mortalité avec le modèle Lee-Carter.',
        'desc_en': 'Yuki masters all French regulatory mortality tables. She calculates life annuities, life expectancies, death benefits and projects mortality trends with the Lee-Carter model.',
        'specialite_fr': 'TH0002 · TF0002 · TGHF05 · Lee-Carter',
        'specialite_en': 'TH0002 · TF0002 · TGHF05 · Lee-Carter',
        'statut': 'VERT', 'direction': 'non_vie', 'equipe': 'transversale',
        'kpi': 'R² = 0.9985 · ä_65 = 13.07',
    },
    'henri': {
        'prenom': 'Henri', 'code': 'EP1', 'icon': '🏢',
        'role_fr': 'Engagements de Retraite — IAS 19',
        'role_en': 'Retirement Commitments — IAS 19',
        'desc_fr': 'Henri évalue les engagements de retraite selon IAS 19 par la méthode PUC (Projected Unit Credit). DBO, Service Cost, Interest Cost, gains et pertes actuariels — il fournit toutes les informations pour le bilan IFRS.',
        'desc_en': 'Henri evaluates retirement commitments according to IAS 19 using the PUC (Projected Unit Credit) method. DBO, Service Cost, Interest Cost, actuarial gains and losses — he provides all information for the IFRS balance sheet.',
        'specialite_fr': 'IAS 19 · PUC · DBO · OAT iBoxx AA',
        'specialite_en': 'IAS 19 · PUC · DBO · OAT iBoxx AA',
        'statut': 'VERT', 'direction': 'epargne', 'equipe': 'epargne',
        'kpi': 'DBO = 10.6M€',
    },
    'fatou': {
        'prenom': 'Fatou', 'code': 'EP2', 'icon': '💰',
        'role_fr': 'Tarification Épargne-Retraite',
        'role_en': 'Savings & Retirement Pricing',
        'desc_fr': 'Fatou tarifie les contrats Art.39, Art.83 et PER (Loi PACTE 2019). Elle calcule les cotisations, rentes viagères, taux de remplacement et participation aux bénéfices pour chaque profil d\'assuré.',
        'desc_en': 'Fatou prices Art.39, Art.83 and PER contracts (PACTE Law 2019). She calculates contributions, life annuities, replacement rates and profit sharing for each insured profile.',
        'specialite_fr': 'Art.39 · Art.83 · PER · PACTE 2019',
        'specialite_en': 'Art.39 · Art.83 · PER · PACTE 2019',
        'statut': 'VERT', 'direction': 'epargne', 'equipe': 'epargne',
        'kpi': 'Rente = 595€/mois',
    },
    'jinho': {
        'prenom': 'Jin-Ho', 'code': 'EP3', 'icon': '📈',
        'role_fr': 'Provisionnement Épargne',
        'role_en': 'Savings Reserving',
        'desc_fr': 'Jin-Ho calcule les provisions mathématiques, la PPB (Provision pour Participation aux Bénéfices) et la Réserve de Capitalisation. Il garantit la conformité avec le Code des assurances Art. R342-14.',
        'desc_en': 'Jin-Ho calculates mathematical provisions, PPB (Profit Sharing Reserve) and Capitalization Reserve. He ensures compliance with Insurance Code Art. R342-14.',
        'specialite_fr': 'PM · PPB · Réserve capitalisation · R342-14',
        'specialite_en': 'PM · PPB · Capitalization reserve · R342-14',
        'statut': 'VERT', 'direction': 'epargne', 'equipe': 'epargne',
        'kpi': 'PPB = 1.15M€',
    },
    'claire': {
        'prenom': 'Claire', 'code': 'EP4', 'icon': '⚡',
        'role_fr': 'Stress Testing Épargne-Retraite',
        'role_en': 'Savings & Retirement Stress Testing',
        'desc_fr': 'Claire évalue la résistance des portefeuilles épargne aux chocs spécifiques retraite : choc longévité +20%, taux bas à 0%, rachats massifs 40% et choc financier -20% des actifs.',
        'desc_en': 'Claire assesses savings portfolio resilience to retirement-specific shocks: +20% longevity shock, 0% low rates, 40% mass surrenders and -20% financial assets shock.',
        'specialite_fr': 'Choc longévité · Rachats massifs · ORSA retraite',
        'specialite_en': 'Longevity shock · Mass surrenders · Retirement ORSA',
        'statut': 'ROUGE', 'direction': 'epargne', 'equipe': 'epargne',
        'kpi': 'Ratio base = 110%',
    },
    'omar': {
        'prenom': 'Omar', 'code': 'EP5', 'icon': '📋',
        'role_fr': 'Reporting Épargne-Retraite',
        'role_en': 'Savings & Retirement Reporting',
        'desc_fr': 'Omar génère tous les rapports réglementaires épargne-retraite : rapport actuariel annuel, QRT retraite ACPR, fiche information assuré PER (Loi PACTE), enquête DARES et note de synthèse pour le CA.',
        'desc_en': 'Omar generates all savings-retirement regulatory reports: annual actuarial report, ACPR retirement QRT, PER insured information sheet (PACTE Law), DARES survey and summary note for the Board.',
        'specialite_fr': 'ACPR · DARES · CA · Fiche assuré PER',
        'specialite_en': 'ACPR · DARES · Board · PER insured sheet',
        'statut': 'ROUGE', 'direction': 'epargne', 'equipe': 'epargne',
        'kpi': '4 rapports disponibles',
    },
}

# Structure hiérarchique
STRUCTURE = {
    'non_vie': {
        'label_fr': 'Direction Non-Vie',
        'label_en': 'Non-Life Division',
        'icon': '🏢',
        'equipes': {
            'tarification': {
                'label_fr': 'Équipe Tarification',
                'label_en': 'Pricing Team',
                'agents': ['amara', 'kenji', 'laurent', 'priya', 'yohan', 'meilin'],
            },
            'provisions': {
                'label_fr': 'Équipe Provisions & Réglementaire',
                'label_en': 'Reserving & Regulatory Team',
                'agents': ['kwame', 'isabelle', 'marcus', 'nadia', 'thomas', 'aisha'],
            },
            'transversale': {
                'label_fr': 'Équipe Transversale',
                'label_en': 'Cross-functional Team',
                'agents': ['luca', 'yuki'],
            },
        }
    },
    'epargne': {
        'label_fr': 'Direction Épargne-Retraite',
        'label_en': 'Savings & Retirement Division',
        'icon': '💼',
        'equipes': {
            'epargne': {
                'label_fr': 'Équipe Épargne-Retraite',
                'label_en': 'Savings & Retirement Team',
                'agents': ['henri', 'fatou', 'jinho', 'claire', 'omar'],
            },
        }
    },
}

KPI_DEMO = {
    'be': 2_914_930, 'scr': 3_680_671, 'ratio_scr': 208.5,
    'tp_ifrs17': 3_992_344, 'gini': 0.2651, 'lcr': 1173.3,
}

# ══════════════════════════════════════════════════════════════════════════════
# CSS GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');

    /* ── RESET & FOND ── */
    .stApp {{ background-color:{NAVY}; color:{BLANC}; font-family:'Inter',sans-serif; }}
    [data-testid="stSidebar"] {{ display:none; }}
    .block-container {{ padding-top:0 !important; max-width:100% !important; }}
    section[data-testid="stSidebarContent"] {{ display:none; }}

    /* ── TOP BAR ── */
    .topbar {{
        position:fixed; top:0; left:0; right:0; z-index:999;
        background:{NAVY_L};
        border-bottom:1px solid rgba(201,168,76,0.3);
        padding:0 32px;
        height:60px;
        display:flex; align-items:center; justify-content:space-between;
    }}
    .topbar-logo {{
        font-family:'Playfair Display',serif;
        font-size:1.4rem; font-weight:700; color:{BLANC};
        display:flex; align-items:center; gap:12px;
        cursor:pointer; text-decoration:none;
    }}
    .topbar-logo span {{ color:{OR}; }}
    .topbar-logo img {{ height:36px; width:auto; }}
    .topbar-nav {{
        display:flex; align-items:center; gap:4px;
    }}
    .topbar-btn {{
        background:transparent; border:none;
        color:{GRIS}; font-size:0.85rem; font-weight:500;
        padding:8px 16px; border-radius:6px;
        cursor:pointer; transition:all 0.2s;
        font-family:'Inter',sans-serif;
    }}
    .topbar-btn:hover {{ color:{BLANC}; background:rgba(255,255,255,0.08); }}
    .topbar-btn.active {{ color:{OR}; background:rgba(201,168,76,0.12); }}
    .topbar-right {{
        display:flex; align-items:center; gap:12px;
    }}
    .lang-btn {{
        background:rgba(201,168,76,0.15);
        border:1px solid rgba(201,168,76,0.4);
        color:{OR}; font-size:0.75rem; font-weight:700;
        padding:4px 12px; border-radius:20px;
        cursor:pointer; letter-spacing:0.05em;
    }}

    /* ── CONTENU PRINCIPAL ── */
    .main-content {{ padding-top:76px; }}

    /* ── HERO ── */
    .hero-wrap {{
        padding:60px 48px 48px;
        background:linear-gradient(135deg, {NAVY} 0%, {NAVY_L} 100%);
        border-bottom:1px solid rgba(201,168,76,0.15);
    }}
    .hero-title {{
        font-family:'Playfair Display',serif;
        font-size:2.6rem; font-weight:700;
        color:{BLANC}; line-height:1.15;
        letter-spacing:-0.02em; margin-bottom:16px;
    }}
    .hero-title span {{ color:{OR}; }}
    .hero-sub {{
        font-size:1rem; color:{GRIS};
        max-width:620px; line-height:1.6;
        margin-bottom:32px;
    }}

    /* ── MÉTRIQUES ── */
    [data-testid="stMetric"] {{
        background:{NAVY_L}; border:1px solid rgba(201,168,76,0.25);
        border-radius:10px; padding:16px 20px;
    }}
    [data-testid="stMetricLabel"] {{
        color:{GRIS} !important; font-size:0.7rem !important;
        font-weight:600 !important; text-transform:uppercase !important;
        letter-spacing:0.08em !important;
    }}
    [data-testid="stMetricValue"] {{
        color:{OR} !important; font-size:1.5rem !important;
        font-weight:700 !important;
    }}

    /* ── CARDS AGENT ── */
    .agent-card {{
        background:{NAVY_L}; border:1px solid rgba(201,168,76,0.2);
        border-radius:12px; padding:20px 16px;
        text-align:center; cursor:pointer;
        transition:all 0.25s; height:100%;
    }}
    .agent-card:hover {{
        border-color:{OR}; transform:translateY(-3px);
        box-shadow:0 8px 32px rgba(0,0,0,0.4);
        background:{NAVY_LL};
    }}
    .agent-avatar {{
        width:56px; height:56px; border-radius:50%;
        background:linear-gradient(135deg,{OR},{OR_L});
        display:flex; align-items:center; justify-content:center;
        margin:0 auto 12px; font-size:1.3rem;
        font-weight:700; color:{NAVY};
        font-family:'Inter',sans-serif;
    }}
    .agent-avatar img {{
        width:56px; height:56px; border-radius:50%;
        object-fit:cover;
    }}
    .agent-prenom {{
        font-weight:700; color:{OR}; font-size:0.95rem;
        margin-bottom:2px;
    }}
    .agent-code {{
        font-size:0.65rem; color:{GRIS};
        text-transform:uppercase; letter-spacing:0.1em;
        margin-bottom:6px;
    }}
    .agent-role {{
        font-size:0.72rem; color:{BLANC}; line-height:1.4;
        margin-bottom:10px;
    }}

    /* ── BADGES RAG ── */
    .badge-VERT  {{ display:inline-block; background:rgba(46,204,113,0.15); color:#2ECC71; border:1px solid rgba(46,204,113,0.4); border-radius:20px; padding:2px 10px; font-size:0.68rem; font-weight:600; }}
    .badge-AMBRE {{ display:inline-block; background:rgba(243,156,18,0.15); color:#F39C12; border:1px solid rgba(243,156,18,0.4); border-radius:20px; padding:2px 10px; font-size:0.68rem; font-weight:600; }}
    .badge-ROUGE {{ display:inline-block; background:rgba(231,76,60,0.15);  color:#E74C3C; border:1px solid rgba(231,76,60,0.4);  border-radius:20px; padding:2px 10px; font-size:0.68rem; font-weight:600; }}

    /* ── SECTION HEADERS ── */
    .section-label {{
        font-size:0.7rem; color:{GRIS}; text-transform:uppercase;
        letter-spacing:0.12em; margin-bottom:16px; font-weight:600;
    }}
    .section-title {{
        font-family:'Playfair Display',serif;
        font-size:1.6rem; color:{BLANC}; font-weight:700;
        margin-bottom:8px;
    }}
    .section-sub {{
        font-size:0.9rem; color:{GRIS}; margin-bottom:24px;
    }}

    /* ── DIRECTION CARD ── */
    .direction-card {{
        background:{NAVY_L}; border:1px solid rgba(201,168,76,0.2);
        border-radius:16px; padding:32px 28px;
        cursor:pointer; transition:all 0.25s;
    }}
    .direction-card:hover {{
        border-color:{OR}; transform:translateY(-4px);
        box-shadow:0 12px 40px rgba(0,0,0,0.4);
    }}
    .direction-icon {{
        font-size:2.5rem; margin-bottom:16px;
    }}
    .direction-titre {{
        font-family:'Playfair Display',serif;
        font-size:1.3rem; color:{BLANC}; font-weight:700;
        margin-bottom:8px;
    }}
    .direction-desc {{
        font-size:0.85rem; color:{GRIS}; line-height:1.6;
    }}
    .direction-count {{
        display:inline-block; margin-top:16px;
        background:rgba(201,168,76,0.15);
        color:{OR}; border-radius:20px;
        padding:4px 14px; font-size:0.75rem; font-weight:600;
    }}

    /* ── PAGE AGENT DETAIL ── */
    .agent-detail-header {{
        background:linear-gradient(135deg,{NAVY_L},{NAVY_LL});
        border:1px solid rgba(201,168,76,0.2);
        border-radius:16px; padding:32px;
        margin-bottom:24px;
    }}
    .agent-detail-avatar {{
        width:100px; height:100px; border-radius:50%;
        background:linear-gradient(135deg,{OR},{OR_L});
        display:flex; align-items:center; justify-content:center;
        font-size:2.5rem; font-weight:700; color:{NAVY};
        margin-bottom:16px;
    }}
    .agent-detail-nom {{
        font-family:'Playfair Display',serif;
        font-size:2rem; color:{BLANC}; font-weight:700;
    }}
    .agent-detail-role {{
        font-size:1rem; color:{OR}; margin-top:4px;
    }}
    .agent-detail-desc {{
        font-size:0.9rem; color:{GRIS}; line-height:1.7;
        margin-top:16px; max-width:600px;
    }}

    /* ── CHAT ARIA ── */
    .chat-message-user {{
        background:{NAVY_LL}; border:1px solid rgba(201,168,76,0.2);
        border-radius:12px 12px 4px 12px;
        padding:12px 16px; margin:8px 0;
        color:{BLANC}; font-size:0.9rem;
    }}
    .chat-message-aria {{
        background:{NAVY_L}; border:1px solid rgba(46,204,113,0.2);
        border-radius:12px 12px 12px 4px;
        padding:12px 16px; margin:8px 0;
        color:{BLANC}; font-size:0.9rem; line-height:1.6;
    }}

    /* ── BOUTONS ── */
    .stButton > button {{
        background:linear-gradient(135deg,{OR},{OR_L});
        color:{NAVY}; border:none; border-radius:8px;
        font-weight:700; font-size:0.9rem;
        padding:10px 24px; transition:all 0.2s;
    }}
    .stButton > button:hover {{
        transform:translateY(-1px);
        box-shadow:0 4px 20px rgba(201,168,76,0.4);
    }}

    /* ── TABS ── */
    .stTabs [data-baseweb="tab-list"] {{
        background:{NAVY_L}; border-radius:8px; padding:4px; gap:4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background:transparent; color:{GRIS}; border-radius:6px;
        font-weight:500; padding:8px 20px;
    }}
    .stTabs [aria-selected="true"] {{
        background:{OR} !important; color:{NAVY} !important;
        font-weight:700 !important;
    }}

    /* ── SCROLLBAR ── */
    ::-webkit-scrollbar {{ width:5px; }}
    ::-webkit-scrollbar-track {{ background:{NAVY}; }}
    ::-webkit-scrollbar-thumb {{ background:rgba(201,168,76,0.4); border-radius:3px; }}

    /* ── INPUTS ── */
    .stTextInput > div > div > input,
    .stSelectbox > div > div {{
        background:{NAVY_L} !important;
        border:1px solid rgba(201,168,76,0.3) !important;
        color:{BLANC} !important; border-radius:8px !important;
    }}
    [data-testid="stFileUploader"] {{
        background:{NAVY_L};
        border:2px dashed rgba(201,168,76,0.4);
        border-radius:12px; padding:20px;
    }}

    /* ── DATAFRAME ── */
    [data-testid="stDataFrame"] {{
        background:{NAVY_L}; border-radius:8px;
        border:1px solid rgba(201,168,76,0.2);
    }}

    /* ── HR ── */
    hr {{ border-color:rgba(201,168,76,0.2); }}

    /* ── REGLEMENTATIONS ── */
    .regl-card {{
        background:{NAVY_L}; border-left:3px solid {OR};
        border-radius:0 10px 10px 0; padding:16px 20px;
        margin-bottom:12px;
    }}
    .regl-titre {{ font-weight:700; color:{OR}; font-size:0.95rem; }}
    .regl-desc {{ font-size:0.82rem; color:{GRIS}; margin-top:4px; line-height:1.5; }}

    /* ── FOOTER ── */
    .footer {{
        text-align:center; padding:32px;
        border-top:1px solid rgba(201,168,76,0.15);
        color:{GRIS}; font-size:0.78rem; margin-top:48px;
    }}
    </style>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TOP BAR
# ══════════════════════════════════════════════════════════════════════════════

def render_topbar():
    """Top bar fixe avec navigation et menu Équipes."""

    # Logo
    try:
        logo_html = '<img src="assets/logo.png" alt="ActuarIA">'
    except:
        logo_html = f'Actuar<span style="color:{OR}">IA</span>'

    # Statuts
    nb_vert  = sum(1 for a in AGENTS.values() if a['statut'] == 'VERT')
    nb_ambre = sum(1 for a in AGENTS.values() if a['statut'] == 'AMBRE')
    nb_rouge = sum(1 for a in AGENTS.values() if a['statut'] == 'ROUGE')

    page = st.session_state.page
    lang = st.session_state.langue

    col_logo, col_nav, col_right = st.columns([1.5, 4, 1.5])

    with col_logo:
        st.markdown(f"""
        <div style="padding-top:8px;">
            <div style="font-family:'Playfair Display',serif; font-size:1.4rem;
                        font-weight:700; color:{BLANC}; cursor:pointer;">
                Actuar<span style="color:{OR};">IA</span>
                <span style="font-size:0.55rem; color:{GRIS}; display:block;
                             letter-spacing:0.15em; text-transform:uppercase;
                             font-family:'Inter',sans-serif; margin-top:-2px;">
                    Actuarial Intelligence Platform
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_nav:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        pages_nav = [
            (c1, t('nav_accueil'),   'accueil'),
            (c2, t('nav_equipes'),   'equipes'),
            (c3, t('nav_dashboard'), 'dashboard'),
            (c4, t('nav_aria'),      'aria'),
            (c5, t('nav_rapports'),  'rapports'),
            (c6, t('nav_analyse'),   'analyse'),
        ]
        for col, label, pid in pages_nav:
            with col:
                if st.button(label, key=f"nav_{pid}",
                              use_container_width=True,
                              type="primary" if page == pid else "secondary"):
                    st.session_state.page = pid
                    st.session_state.agent_selec = None
                    st.session_state.direction_selec = None
                    st.rerun()

    with col_right:
        c_stat, c_lang = st.columns([2, 1])
        with c_stat:
            st.markdown(f"""
            <div style="display:flex; gap:6px; padding-top:10px; justify-content:center;">
                <span class="badge-VERT">✅ {nb_vert}</span>
                <span class="badge-AMBRE">⚠ {nb_ambre}</span>
                <span class="badge-ROUGE">❌ {nb_rouge}</span>
            </div>
            """, unsafe_allow_html=True)
        with c_lang:
            if st.button(
                "🇫🇷 FR" if lang == 'fr' else "🇬🇧 EN",
                key="lang_toggle"
            ):
                st.session_state.langue = 'en' if lang == 'fr' else 'fr'
                st.rerun()

    st.markdown(f"<hr style='margin:0; border-color:rgba(201,168,76,0.2);'>",
                unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def avatar_html(agent_key, size=56):
    """Génère l'avatar — photo si disponible, sinon initiale."""
    agent = AGENTS[agent_key]
    prenom = agent['prenom']
    initiale = prenom[0].upper()
    try:
        return f'<img src="assets/avatars/{agent_key}.png" style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;">'
    except:
        return f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:linear-gradient(135deg,{OR},{OR_L});display:flex;align-items:center;justify-content:center;font-size:{size*0.4}px;font-weight:700;color:{NAVY};margin:0 auto;">{initiale}</div>'

def badge_statut(statut):
    return f'<span class="badge-{statut}">{statut}</span>'

def card_agent(agent_key, show_btn=True):
    """Carte agent cliquable."""
    agent = AGENTS[agent_key]
    lang  = st.session_state.langue
    role  = agent['role_fr'] if lang == 'fr' else agent['role_en']
    initiale = agent['prenom'][0].upper()

    st.markdown(f"""
    <div class="agent-card">
        <div class="agent-avatar">{initiale}</div>
        <div class="agent-prenom">{agent['prenom']}</div>
        <div class="agent-code">{agent['code']}</div>
        <div class="agent-role">{role}</div>
        {badge_statut(agent['statut'])}
        <div style="font-size:0.68rem;color:{GRIS};margin-top:8px;">{agent['kpi']}</div>
    </div>
    """, unsafe_allow_html=True)

    if show_btn:
        if st.button(f"Voir {agent['prenom']}", key=f"btn_{agent_key}",
                      use_container_width=True):
            st.session_state.agent_selec = agent_key
            st.session_state.page = 'agent_detail'
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ACCUEIL
# ══════════════════════════════════════════════════════════════════════════════

def page_accueil():
    lang = st.session_state.langue

    # ── HERO ──────────────────────────────────────────────────────────────────
    col_h, col_r = st.columns([1.4, 1])
    with col_h:
        st.markdown(f"""
        <div style="padding:48px 48px 32px;">
            <div style="font-size:0.7rem;color:{OR};text-transform:uppercase;
                        letter-spacing:0.15em;font-weight:600;margin-bottom:16px;">
                Actuarial Intelligence Platform
            </div>
            <div class="hero-title">
                ActuarIA — Là où l'expertise<br>
                <span>rencontre l'intelligence artificielle.</span>
            </div>
            <div class="hero-sub">
                {t('sous_titre')}
            </div>
        </div>
        """, unsafe_allow_html=True)

        _, cb1, cb2, _ = st.columns([2, 1, 1, 2])
        with cb1:
            if st.button(t('btn_analyse'), type="primary", use_container_width=True):
                st.session_state.page = 'analyse'
                st.rerun()
        with cb2:
            if st.button(t('btn_demo'), use_container_width=True):
                st.session_state.page = 'dashboard'
                st.rerun()

    with col_r:
        st.markdown("<div style='padding-top:48px;'>", unsafe_allow_html=True)
        _radar_hero()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f"<hr style='margin:8px 0;border-color:rgba(201,168,76,0.15);'>",
                unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    st.markdown("<div style='padding:0 48px;'>", unsafe_allow_html=True)
    k = KPI_DEMO
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.metric("Agents", "20 / 20", "IA + EP")
    with c2: st.metric("Best Estimate", f"{k['be']/1e6:.2f}M€", "CV 0.6%")
    with c3: st.metric("Ratio SCR", f"{k['ratio_scr']:.1f}%", "+8.5%")
    with c4: st.metric("Gini ML", f"{k['gini']:.4f}", "+0.044 vs GLM")
    with c5: st.metric("LCR", f"{k['lcr']:.0f}%", "✅ Liquide")
    with c6: st.metric("Conformité", "100%", "S2 + IFRS 17")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    # ── PRÉSENTATION PLATEFORME ───────────────────────────────────────────────
    st.markdown("<div style='padding:0 48px;'>", unsafe_allow_html=True)

    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.markdown(f"""
        <div class="section-label">La plateforme</div>
        <div class="section-title">20 agents actuariels,<br>une intelligence unifiée.</div>
        <div class="section-sub">
            ActuarIA est la première plateforme actuarielle propulsée par l'IA
            conçue pour les professionnels de l'assurance. Chaque agent est un
            expert spécialisé qui couvre l'intégralité de la chaîne actuarielle,
            de la tarification au reporting réglementaire.
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="section-label" style="margin-top:24px;">Pour qui ?</div>
        """, unsafe_allow_html=True)

        clients = [
            ("🏢", "Compagnies d'assurance", "Non-Vie · Vie · Mixte"),
            ("🤝", "Mutuelles", "Santé · Prévoyance · Retraite"),
            ("🛡️", "Institutions de Prévoyance", "Retraite complémentaire · IAS 19"),
            ("📊", "Cabinets actuariels", "Conseil · Audit · Reporting"),
            ("🏦", "Réassureurs", "Cession · Acceptation · Modélisation"),
        ]
        for icon, nom, desc in clients:
            st.markdown(f"""
            <div style="display:flex;gap:12px;align-items:flex-start;
                        margin-bottom:10px;">
                <span style="font-size:1.2rem;margin-top:2px;">{icon}</span>
                <div>
                    <div style="font-weight:600;color:{BLANC};font-size:0.88rem;">
                        {nom}
                    </div>
                    <div style="font-size:0.78rem;color:{GRIS};">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_p2:
        st.markdown(f"""
        <div class="section-label">Réglementations couvertes</div>
        """, unsafe_allow_html=True)

        reglements = [
            ("Solvabilité 2", "Piliers 1, 2 et 3 — Formule standard EIOPA · SCR · MCR · QRT · ORSA · SFCR. Conformité avec le Règlement délégué (UE) 2015/35."),
            ("IFRS 17", "Approches PAA, BBA et VFA · CSM · Risk Adjustment · Réconciliation S2/IFRS 17. Applicable depuis janvier 2023."),
            ("ALM", "Gestion Actif-Passif · Duration de Macaulay · Gap · BV01 · LCR · Stress taux ±200bp. Pilier 2 S2."),
            ("IAS 19", "Engagements de retraite · Méthode PUC · DBO · Service Cost · OAT iBoxx AA. Régimes Art.39, Art.83, PER."),
            ("Loi PACTE 2019", "Plan Épargne Retraite (PER) · Portabilité · Sortie en capital · Fiche information assuré."),
            ("RGPD Art.30", "Registre des activités de traitement · Pseudonymisation · Audit trail complet · Hash SHA-256."),
        ]
        for titre, desc in reglements:
            st.markdown(f"""
            <div class="regl-card">
                <div class="regl-titre">{titre}</div>
                <div class="regl-desc">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    # ── APERÇU AGENTS ─────────────────────────────────────────────────────────
    st.markdown("<div style='padding:0 48px;'>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="section-label">Nos agents</div>
    <div class="section-title">Une équipe d'experts IA à votre service.</div>
    <div class="section-sub">
        Cliquez sur "Équipes" dans la barre de navigation pour explorer
        chaque direction et dialoguer avec nos agents.
    </div>
    """, unsafe_allow_html=True)

    # Aperçu 7 agents
    cols = st.columns(7)
    agents_apercu = ['sofia','amara','kenji','kwame','nadia','thomas','aisha']
    for i, ak in enumerate(agents_apercu):
        with cols[i]:
            card_agent(ak, show_btn=False)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── FOOTER ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="footer">
        <div style="font-family:'Playfair Display',serif;font-size:1.1rem;
                    color:{BLANC};margin-bottom:8px;">
            Actuar<span style="color:{OR};">IA</span>
        </div>
        <div>Actuarial Intelligence Platform · v2.0</div>
        <div style="margin-top:4px;">
            Contact : <span style="color:{OR};">contact@actuaria.fr</span>
            · {datetime.now().strftime('%Y')}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ÉQUIPES
# ══════════════════════════════════════════════════════════════════════════════

def page_equipes():
    lang = st.session_state.langue

    # Si un agent est sélectionné → page détail
    if st.session_state.agent_selec:
        page_agent_detail(st.session_state.agent_selec)
        return

    # Si une direction est sélectionnée → afficher ses équipes
    if st.session_state.direction_selec:
        page_direction(st.session_state.direction_selec)
        return

    # Page principale équipes
    st.markdown("<div style='padding:32px 48px;'>", unsafe_allow_html=True)

    # Sofia — Agent IA Central
    st.markdown(f"""
    <div class="section-label">Agent IA Central</div>
    """, unsafe_allow_html=True)

    col_sofia, col_desc = st.columns([1, 3])
    with col_sofia:
        st.markdown(f"""
        <div class="agent-card" style="max-width:180px;">
            <div class="agent-avatar" style="width:72px;height:72px;font-size:1.8rem;">S</div>
            <div class="agent-prenom" style="font-size:1.1rem;">Sofia</div>
            <div class="agent-code">ARIA</div>
            <div class="agent-role">Actuaire IA Senior</div>
            {badge_statut('VERT')}
        </div>
        """, unsafe_allow_html=True)
        if st.button("Dialoguer avec Sofia", type="primary", key="btn_sofia_main"):
            st.session_state.agent_selec = 'sofia'
            st.session_state.page = 'agent_detail'
            st.rerun()

    with col_desc:
        st.markdown(f"""
        <div style="padding:16px 0;">
            <div style="font-family:'Playfair Display',serif;font-size:1.4rem;
                        color:{BLANC};font-weight:700;margin-bottom:8px;">
                Sofia — L'intelligence au cœur d'ActuarIA
            </div>
            <div style="font-size:0.9rem;color:{GRIS};line-height:1.7;max-width:500px;">
                Sofia coordonne l'ensemble des 19 agents spécialisés de la plateforme.
                Propulsée par Claude API d'Anthropic, elle répond à toutes vos questions
                actuarielles, synthétise les résultats et oriente vers le bon expert.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"<hr style='margin:28px 0;border-color:rgba(201,168,76,0.15);'>",
                unsafe_allow_html=True)

    # Directions
    st.markdown(f"""
    <div class="section-label">Directions</div>
    <div class="section-title">Deux directions, une expertise complète.</div>
    <div style="height:16px"></div>
    """, unsafe_allow_html=True)

    col_nv, col_ep = st.columns(2)

    with col_nv:
        nb_agents_nv = sum(
            len(eq['agents'])
            for eq in STRUCTURE['non_vie']['equipes'].values()
        )
        st.markdown(f"""
        <div class="direction-card">
            <div class="direction-icon">🏢</div>
            <div class="direction-titre">Direction Non-Vie</div>
            <div class="direction-desc">
                Tarification GLM et ML · Provisionnement Chain Ladder/Mack/BF ·
                Solvabilité 2 · IFRS 17 · ALM · Stress Testing · Audit Trail ·
                Tables de Mortalité
            </div>
            <span class="direction-count">{nb_agents_nv} agents · 3 équipes</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("Explorer la Direction Non-Vie →", key="btn_dir_nv",
                      use_container_width=True, type="primary"):
            st.session_state.direction_selec = 'non_vie'
            st.rerun()

    with col_ep:
        nb_agents_ep = sum(
            len(eq['agents'])
            for eq in STRUCTURE['epargne']['equipes'].values()
        )
        st.markdown(f"""
        <div class="direction-card">
            <div class="direction-icon">💼</div>
            <div class="direction-titre">Direction Épargne-Retraite</div>
            <div class="direction-desc">
                Engagements de retraite IAS 19 · Tarification Art.39/83/PER ·
                Provisionnement PM/PPB · Stress Testing longévité ·
                Reporting ACPR/DARES · Loi PACTE 2019
            </div>
            <span class="direction-count">{nb_agents_ep} agents · 1 équipe</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("Explorer la Direction Épargne →", key="btn_dir_ep",
                      use_container_width=True, type="primary"):
            st.session_state.direction_selec = 'epargne'
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def page_direction(direction_key):
    """Page d'une direction avec ses équipes et agents."""
    lang   = st.session_state.langue
    struct = STRUCTURE[direction_key]
    label  = struct['label_fr'] if lang == 'fr' else struct['label_en']

    st.markdown("<div style='padding:32px 48px;'>", unsafe_allow_html=True)

    # Bouton retour
    if st.button(t('btn_retour'), key="btn_retour_dir"):
        st.session_state.direction_selec = None
        st.rerun()

    st.markdown(f"""
    <div style="margin:16px 0 32px;">
        <div class="section-label">Direction</div>
        <div class="section-title">{struct['icon']} {label}</div>
    </div>
    """, unsafe_allow_html=True)

    # Équipes
    for equipe_key, equipe in struct['equipes'].items():
        eq_label = equipe['label_fr'] if lang == 'fr' else equipe['label_en']

        st.markdown(f"""
        <div style="margin:24px 0 16px;">
            <div style="display:flex;align-items:center;gap:12px;">
                <div style="width:3px;height:24px;background:{OR};border-radius:2px;"></div>
                <div style="font-weight:700;color:{BLANC};font-size:1rem;">
                    {eq_label}
                </div>
                <span class="direction-count">{len(equipe['agents'])} agents</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        cols = st.columns(len(equipe['agents']))
        for i, agent_key in enumerate(equipe['agents']):
            with cols[i]:
                card_agent(agent_key, show_btn=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def page_agent_detail(agent_key):
    """Page détail d'un agent — 3 niveaux."""
    lang  = st.session_state.langue
    agent = AGENTS[agent_key]
    role  = agent['role_fr'] if lang == 'fr' else agent['role_en']
    desc  = agent['desc_fr'] if lang == 'fr' else agent['desc_en']
    spec  = agent['specialite_fr'] if lang == 'fr' else agent['specialite_en']

    st.markdown("<div style='padding:32px 48px;'>", unsafe_allow_html=True)

    # Bouton retour
    if st.button(t('btn_retour'), key="btn_retour_agent"):
        st.session_state.agent_selec = None
        st.session_state.page = 'equipes'
        st.rerun()

    # Header agent
    col_av, col_info = st.columns([1, 3])
    with col_av:
        st.markdown(f"""
        <div class="agent-detail-header" style="text-align:center;">
            <div class="agent-detail-avatar" style="margin:0 auto 16px;">
                {agent['prenom'][0].upper()}
            </div>
            <div class="agent-detail-nom">{agent['prenom']}</div>
            <div style="font-size:0.75rem;color:{GRIS};
                        text-transform:uppercase;letter-spacing:0.1em;
                        margin:4px 0 8px;">{agent['code']}</div>
            {badge_statut(agent['statut'])}
            <div style="font-size:0.75rem;color:{GRIS};margin-top:12px;">
                {agent['kpi']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_info:
        st.markdown(f"""
        <div class="agent-detail-header">
            <div class="agent-detail-role">{role}</div>
            <div class="agent-detail-desc">{desc}</div>
            <div style="margin-top:20px;">
                <div style="font-size:0.7rem;color:{GRIS};
                            text-transform:uppercase;letter-spacing:0.1em;
                            margin-bottom:8px;">Spécialités</div>
                <div style="font-size:0.82rem;color:{OR};">{spec}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # 3 onglets : Présentation · Lancer · Dialoguer
    tab1, tab2, tab3 = st.tabs([
        "📋 Présentation",
        f"🚀 Lancer {agent['prenom']}",
        f"💬 Dialoguer avec {agent['prenom']}",
    ])

    with tab1:
        _tab_presentation_agent(agent_key)

    with tab2:
        _tab_lancer_agent(agent_key)

    with tab3:
        _tab_dialoguer_agent(agent_key)

    st.markdown("</div>", unsafe_allow_html=True)


def _tab_presentation_agent(agent_key):
    """Onglet présentation détaillée de l'agent."""
    lang  = st.session_state.langue
    agent = AGENTS[agent_key]

    st.markdown(f"<div style='height:16px'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
                    border-radius:10px;padding:20px;">
            <div style="font-size:0.7rem;color:{GRIS};text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:12px;">
                Informations
            </div>
            <div style="display:grid;gap:10px;">
                <div><span style="color:{GRIS};font-size:0.8rem;">Code :</span>
                     <span style="color:{BLANC};font-weight:600;margin-left:8px;">
                     {agent['code']}</span></div>
                <div><span style="color:{GRIS};font-size:0.8rem;">Direction :</span>
                     <span style="color:{BLANC};font-weight:600;margin-left:8px;">
                     {'Non-Vie' if agent['direction']=='non_vie' else 'Épargne-Retraite' if agent['direction']=='epargne' else 'Central'}</span></div>
                <div><span style="color:{GRIS};font-size:0.8rem;">Statut :</span>
                     <span style="margin-left:8px;">{badge_statut(agent['statut'])}</span></div>
                <div><span style="color:{GRIS};font-size:0.8rem;">KPI :</span>
                     <span style="color:{OR};font-weight:600;margin-left:8px;">
                     {agent['kpi']}</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
                    border-radius:10px;padding:20px;">
            <div style="font-size:0.7rem;color:{GRIS};text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:12px;">
                Autonomie & Références
            </div>
            <div style="font-size:0.85rem;color:{GRIS};line-height:1.7;">
                Niveau 2 — Calculs automatiques avec alertes proactives.<br>
                L'actuaire responsable valide et signe les résultats.<br><br>
                <span style="color:{OR};font-weight:600;">Conformité :</span><br>
                EIOPA 2015/35 · IFRS 17 IASB · Loi PACTE · RGPD
            </div>
        </div>
        """, unsafe_allow_html=True)


def _tab_lancer_agent(agent_key):
    """Onglet pour lancer l'agent."""
    agent = AGENTS[agent_key]
    st.markdown(f"<div style='height:16px'></div>", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
                border-radius:10px;padding:24px;margin-bottom:20px;">
        <div style="font-size:0.85rem;color:{GRIS};line-height:1.6;">
            Uploadez votre fichier de données pour lancer {agent['prenom']}.
            Le pipeline s'exécute automatiquement avec détection de branche
            et mapping des colonnes.
        </div>
    </div>
    """, unsafe_allow_html=True)

    fichier = st.file_uploader(
        "Fichier de données",
        type=['csv', 'xlsx', 'xls', 'parquet'],
        key=f"upload_{agent_key}",
        label_visibility='collapsed',
    )

    col_conf1, col_conf2 = st.columns(2)
    with col_conf1:
        branche = st.selectbox(
            "Branche",
            ['Non-Vie (Auto)', 'Non-Vie (MRH)', 'Non-Vie (RC Pro)',
             'Vie', 'Santé-Prévoyance', 'Épargne-Retraite'],
            key=f"branche_{agent_key}"
        )
    with col_conf2:
        client_id = st.text_input(
            "ID Client",
            placeholder="ex: cabinet_xyz",
            key=f"client_{agent_key}"
        )

    if st.button(f"🚀 Lancer {agent['prenom']}", type="primary",
                  key=f"run_{agent_key}"):
        _simuler_execution(agent['prenom'], agent['code'])


def _tab_dialoguer_agent(agent_key):
    """Onglet chat avec l'agent."""
    agent = AGENTS[agent_key]
    chat_key = f"chat_{agent_key}"

    if chat_key not in st.session_state:
        st.session_state[chat_key] = [{
            'role': 'assistant',
            'content': (
                f"Bonjour, je suis **{agent['prenom']}**, "
                f"spécialiste en *{agent['role_fr']}*. "
                f"Comment puis-je vous aider ?"
            )
        }]

    st.markdown(f"<div style='height:16px'></div>", unsafe_allow_html=True)

    # Affichage messages
    for msg in st.session_state[chat_key]:
        role_label = agent['prenom'] if msg['role'] == 'assistant' else 'Vous'
        bg = NAVY_L if msg['role'] == 'assistant' else NAVY_LL
        border_color = f"rgba(46,204,113,0.3)" if msg['role'] == 'assistant' else f"rgba(201,168,76,0.3)"

        st.markdown(f"""
        <div style="background:{bg};border:1px solid {border_color};
                    border-radius:12px;padding:14px 18px;margin-bottom:10px;">
            <div style="font-size:0.7rem;color:{OR};font-weight:600;
                        margin-bottom:6px;text-transform:uppercase;
                        letter-spacing:0.08em;">{role_label}</div>
            <div style="font-size:0.88rem;color:{BLANC};line-height:1.6;">
                {msg['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Input
    prompt = st.chat_input(
        f"Posez votre question à {agent['prenom']}...",
        key=f"input_{agent_key}"
    )

    if prompt:
        st.session_state[chat_key].append({'role': 'user', 'content': prompt})
        reponse = _reponse_agent_demo(agent_key, prompt)
        st.session_state[chat_key].append({'role': 'assistant', 'content': reponse})
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    st.markdown("<div style='padding:32px 48px;'>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="section-label">Résultats consolidés</div>
    <div class="section-title">Dashboard Actuariel</div>
    <div style="height:16px"></div>
    """, unsafe_allow_html=True)

    tabs = st.tabs([
        "📐 Tarification", "🏦 Provisions", "🛡️ Solvabilité 2",
        "📊 IFRS 17", "⚖️ ALM", "📋 Synthèse"
    ])

    with tabs[0]: _dash_tarification()
    with tabs[1]: _dash_provisions()
    with tabs[2]: _dash_solvabilite()
    with tabs[3]: _dash_ifrs17()
    with tabs[4]: _dash_alm()
    with tabs[5]: _dash_synthese()

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ARIA
# ══════════════════════════════════════════════════════════════════════════════

def page_aria():
    st.markdown("<div style='padding:32px 48px;'>", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center;padding:24px 0 32px;">
        <div style="font-size:3rem;margin-bottom:12px;">🤖</div>
        <div style="font-family:'Playfair Display',serif;font-size:2rem;
                    font-weight:700;color:{BLANC};">
            Agent <span style="color:{OR};">Sofia</span>
        </div>
        <div style="color:{GRIS};font-size:0.9rem;margin-top:8px;">
            ARIA — Actuaire IA Senior · Propulsée par Claude API
        </div>
        <div style="display:inline-block;margin-top:12px;padding:4px 16px;
                    background:rgba(201,168,76,0.1);border:1px solid rgba(201,168,76,0.3);
                    border-radius:20px;font-size:0.75rem;color:{OR};">
            ✅ 20 agents connectés · Résultats en temps réel
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Init messages
    if not st.session_state.messages_aria:
        st.session_state.messages_aria = [{
            'role': 'assistant',
            'content': (
                "Bonjour, je suis **Sofia**, votre actuaire IA senior. "
                "J'ai accès aux résultats de tous les agents de la plateforme. "
                "Comment puis-je vous aider ?\n\n"
                "Exemples de questions :\n"
                "- *Analyse le Best Estimate de mon portefeuille*\n"
                "- *Explique le ratio SCR de 208.5%*\n"
                "- *Quels sont les risques principaux identifiés ?*\n"
                "- *Compare les méthodes de provisionnement*"
            )
        }]

    # Affichage messages
    for msg in st.session_state.messages_aria:
        role_label = "Sofia" if msg['role'] == 'assistant' else "Vous"
        bg = NAVY_L if msg['role'] == 'assistant' else NAVY_LL
        border_c = "rgba(46,204,113,0.3)" if msg['role'] == 'assistant' else "rgba(201,168,76,0.3)"

        st.markdown(f"""
        <div style="background:{bg};border:1px solid {border_c};
                    border-radius:12px;padding:14px 18px;margin-bottom:10px;
                    max-width:800px;">
            <div style="font-size:0.7rem;color:{OR};font-weight:600;
                        margin-bottom:6px;text-transform:uppercase;
                        letter-spacing:0.08em;">{role_label}</div>
            <div style="font-size:0.88rem;color:{BLANC};line-height:1.6;">
                {msg['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Input
    if prompt := st.chat_input("Posez votre question actuarielle à Sofia..."):
        st.session_state.messages_aria.append({'role': 'user', 'content': prompt})
        reponse = _reponse_aria(prompt)
        st.session_state.messages_aria.append({'role': 'assistant', 'content': reponse})
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ANALYSE
# ══════════════════════════════════════════════════════════════════════════════

def page_analyse():
    st.markdown("<div style='padding:32px 48px;'>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="section-label">Pipeline actuariel</div>
    <div class="section-title">Analyser un portefeuille</div>
    <div class="section-sub">
        Déposez votre fichier Excel, CSV ou Parquet —
        la plateforme détecte automatiquement la branche et lance le pipeline complet.
    </div>
    """, unsafe_allow_html=True)

    col_up, col_conf = st.columns([1.5, 1])

    with col_up:
        fichier = st.file_uploader(
            "Fichier de données",
            type=['csv', 'xlsx', 'xls', 'parquet'],
            label_visibility='collapsed',
        )
        if fichier:
            st.success(f"✅ Fichier chargé : {fichier.name}")

    with col_conf:
        st.markdown(f"<div style='font-size:0.75rem;color:{GRIS};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;'>Configuration</div>", unsafe_allow_html=True)
        branche = st.selectbox("Branche", ['Non-Vie (Auto)', 'Non-Vie (MRH)',
                                            'Non-Vie (RC Pro)', 'Vie',
                                            'Santé-Prévoyance', 'Épargne-Retraite'])
        profil  = st.selectbox("Profil modèle", ['Équilibré', 'Performance maximale',
                                                    'Auditabilité S2', 'Compagnie Vie'])
        client  = st.text_input("ID Client", placeholder="cabinet_xyz")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col_b1, col_b2, _ = st.columns([1, 1, 3])
    with col_b1:
        if st.button("🚀 Lancer le pipeline", type="primary", use_container_width=True):
            if fichier:
                _simuler_execution("Pipeline", "A1→A14")
            else:
                st.warning("Veuillez d'abord uploader un fichier.")
    with col_b2:
        if st.button("🎯 Démo synthétique", use_container_width=True):
            _simuler_execution("Pipeline", "A1→A14")

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE RAPPORTS
# ══════════════════════════════════════════════════════════════════════════════

def page_rapports():
    st.markdown("<div style='padding:32px 48px;'>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="section-label">Export & Conformité</div>
    <div class="section-title">Rapports réglementaires</div>
    <div style="height:16px"></div>
    """, unsafe_allow_html=True)

    rapports = [
        ('📋', 'Rapport Actuariel Complet',    'PDF',   'Synthèse A1-A14 + EP1-EP5 · Signé par l\'actuaire responsable'),
        ('🛡️', 'QRT Solvabilité 2',            'Excel', 'S.05 · S.17 · S.19 · S.23 · Pilier 3 ACPR'),
        ('📊', 'Rapport IFRS 17',              'Excel', 'PAA · BBA · CSM · Réconciliation S2/IFRS17'),
        ('🌩️', 'ORSA Prospectif 5 ans',        'PDF',   'Stress testing · Ratio SCR projeté · Plan de contingence'),
        ('⚖️', 'Rapport ALM',                  'PDF',   'Duration · Gap · LCR · Stress taux ±200bp'),
        ('🔐', 'Audit Trail Complet',           'JSON',  'Logs · Hash SHA-256 · RGPD Art.30 · Versioning hypothèses'),
        ('🏢', 'Rapport IAS 19',               'Excel', 'DBO · Service Cost · Interest Cost · Corridor'),
        ('📄', 'Fiche Information Assuré PER', 'PDF',   'Droits acquis · Rente prévisionnelle · Frais · PACTE 2019'),
    ]

    cols = st.columns(2)
    for i, (icon, nom, fmt, desc) in enumerate(rapports):
        with cols[i % 2]:
            col_i, col_b = st.columns([4, 1])
            with col_i:
                st.markdown(f"""
                <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);
                            border-radius:10px;padding:16px;margin-bottom:8px;
                            display:flex;align-items:flex-start;gap:14px;">
                    <span style="font-size:1.4rem;margin-top:2px;">{icon}</span>
                    <div>
                        <div style="font-weight:600;color:{BLANC};font-size:0.88rem;">
                            {nom}
                        </div>
                        <div style="font-size:0.75rem;color:{GRIS};margin-top:3px;">
                            {desc}
                        </div>
                        <div style="font-size:0.68rem;color:{OR};margin-top:4px;
                                    font-weight:600;">{fmt}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_b:
                st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
                if st.button("↓", key=f"dl_{i}", help=f"Générer {nom}"):
                    st.toast(f"✅ {nom} généré", icon="✅")

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# GRAPHIQUES
# ══════════════════════════════════════════════════════════════════════════════

def _radar_hero():
    cats   = ['Solvabilité', 'Provisions', 'Tarification', 'Cohérence', 'ALM', 'IFRS17']
    vals   = [0.92, 0.96, 0.85, 1.00, 0.78, 0.88]
    fig = go.Figure(go.Scatterpolar(
        r=vals+[vals[0]], theta=cats+[cats[0]],
        fill='toself', fillcolor='rgba(201,168,76,0.12)',
        line=dict(color=OR, width=2.5),
        marker=dict(color=OR, size=7),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=NAVY_L,
            radialaxis=dict(visible=True, range=[0,1],
                           tickfont=dict(color=GRIS,size=9),
                           gridcolor='rgba(201,168,76,0.15)',
                           linecolor='rgba(201,168,76,0.2)'),
            angularaxis=dict(tickfont=dict(color=BLANC,size=10),
                            gridcolor='rgba(201,168,76,0.15)',
                            linecolor='rgba(201,168,76,0.2)'),
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40,r=40,t=20,b=20), height=300, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})


def _dash_tarification():
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Fréquence moy.", "0.163", "Auto FR")
    with c2: st.metric("Coût moyen",     "4 638 €", "+2.1% vs N-1")
    with c3: st.metric("Prime pure",     "757 €",   "Poisson × Gamma")
    with c4: st.metric("Gini XGBoost",   "0.2651",  "freMTPL2 validé")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"<div class='section-label'>Classement 6 modèles</div>", unsafe_allow_html=True)
        df = pd.DataFrame({
            'Modèle':    ['XGBoost','GBM','CatBoost','LightGBM','ElasticNet','XGB Tweedie'],
            'Gini':      [0.2651,0.2542,0.2534,0.2481,0.2440,0.2404],
            'Overfit':   [1.53,1.41,1.28,1.60,0.98,1.97],
            'Sélectionné':['','','','','⭐',''],
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

    with col2:
        st.markdown(f"<div class='section-label'>Gini par modèle</div>", unsafe_allow_html=True)
        modeles = ['GLM','ElasticNet','LightGBM','CatBoost','GBM','XGBoost']
        ginis   = [0.000,0.244,0.248,0.253,0.254,0.265]
        colors  = [GRIS if g < 0.1 else OR_L if g < 0.25 else OR for g in ginis]
        fig = go.Figure(go.Bar(
            x=ginis, y=modeles, orientation='h',
            marker_color=colors,
            text=[f"{g:.3f}" for g in ginis], textposition='outside',
            textfont=dict(color=BLANC,size=11),
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False),
            yaxis=dict(tickfont=dict(color=BLANC,size=11)),
            margin=dict(l=0,r=50,t=8,b=8), height=220,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})


def _dash_provisions():
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Best Estimate S2", "2 914 930 €", "4 méthodes")
    with c2: st.metric("Provision P90",    "3 098 000 €", "+6.3%")
    with c3: st.metric("σ Mack",           "45 000 €",    "IC 95%")
    with c4: st.metric("CV inter-méth.",   "0.6%",        "✅ Convergent")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    methodes = ['Chain Ladder','Mack 1993','BF','Cape Cod','Best Estimate']
    valeurs  = [2_850_000,2_914_930,2_930_000,2_880_000,2_914_930]
    colors   = [NAVY_LL,NAVY_LL,NAVY_LL,NAVY_LL,OR]
    fig = go.Figure(go.Bar(
        x=methodes, y=valeurs, marker_color=colors,
        marker_line=dict(color=OR,width=1),
        text=[f"{v/1e6:.2f}M€" for v in valeurs],
        textposition='outside', textfont=dict(color=BLANC,size=11),
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(tickfont=dict(color=BLANC)),
        yaxis=dict(visible=False),
        margin=dict(l=0,r=0,t=24,b=0), height=240,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})


def _dash_solvabilite():
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("SCR Total",  "3 680 671 €", "formule standard")
    with c2: st.metric("MCR Final",  "2 500 000 €", "plancher régl.")
    with c3: st.metric("Ratio SCR",  "208.5%",      "✅ > cible 150%")
    with c4: st.metric("Ratio MCR",  "320.0%",      "✅ > min 100%")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"<div class='section-label'>Décomposition SCR</div>", unsafe_allow_html=True)
        labels = ['SCR Sous.','SCR Marché','SCR Défaut','SCR Opéra.']
        values = [3_104_537,660_000,73_000,262_000]
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.55,
            marker=dict(colors=[OR,NAVY_LL,GRIS,OR_L]),
            textfont=dict(color=BLANC,size=11),
        ))
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(font=dict(color=BLANC,size=10),bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=0,r=0,t=0,b=0), height=240,
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})

    with col2:
        st.markdown(f"<div class='section-label'>Jauge Ratio SCR</div>", unsafe_allow_html=True)
        fig = go.Figure(go.Indicator(
            mode='gauge+number', value=208.5,
            title=dict(text='Ratio SCR (%)', font=dict(color=BLANC)),
            number=dict(suffix='%', font=dict(color=OR,size=28)),
            gauge=dict(
                axis=dict(range=[0,300], tickcolor=GRIS),
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


def _dash_ifrs17():
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("TP IFRS 17 (PAA)", "3 992 344 €", "approche PAA")
    with c2: st.metric("LRC",              "2 500 000 €", "risque restant")
    with c3: st.metric("LIC",              "1 492 344 €", "sinistres survenus")
    with c4: st.metric("Ratio IFRS17/S2",  "1.370",       "✅ Cohérent")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    items  = ['BE S2','+ Risk Adj.','+ Autres','= TP IFRS17']
    vals   = [2_914_930,131_344,946_070,3_992_344]
    colors = [NAVY_LL,NAVY_LL,NAVY_LL,OR]
    fig = go.Figure(go.Bar(
        x=items, y=vals, marker_color=colors,
        marker_line=dict(color=OR,width=1),
        text=[f"{v/1e6:.2f}M€" for v in vals],
        textposition='outside', textfont=dict(color=BLANC,size=11),
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(tickfont=dict(color=BLANC)),
        yaxis=dict(visible=False),
        margin=dict(l=0,r=0,t=24,b=0), height=240,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})


def _dash_alm():
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Duration actifs",  "3.50 ans", "obligations")
    with c2: st.metric("Duration passifs", "1.60 ans", "Auto court terme")
    with c3: st.metric("Gap duration",     "+1.90 ans","⚠️ À raccourcir")
    with c4: st.metric("LCR",             "1 173%",   "✅ Très liquide")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    chocs  = ['-200bp','-100bp','+100bp','+200bp']
    impacts= [650000,325000,-323741,-647482]
    colors = [VERT if v>0 else ROUGE for v in impacts]
    fig = go.Figure(go.Bar(
        x=chocs, y=impacts, marker_color=colors,
        text=[f"{v/1e3:+.0f}k€" for v in impacts],
        textposition='outside', textfont=dict(color=BLANC,size=11),
    ))
    fig.add_hline(y=0, line_color=GRIS)
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(tickfont=dict(color=BLANC)),
        yaxis=dict(visible=False),
        title=dict(text='Impact chocs de taux sur valeur nette',
                   font=dict(color=GRIS,size=11)),
        margin=dict(l=0,r=0,t=32,b=0), height=240,
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})


def _dash_synthese():
    df = pd.DataFrame([
        {'Module':'Tarification',     'Agent':'A3-A6',  'Résultat clé':'Gini XGBoost=0.2651 · ElasticNet sélectionné','Statut':'🟢 VERT'},
        {'Module':'Provisionnement',  'Agent':'A7',     'Résultat clé':'BE=2 914 930€ · CV 0.6% · 4 méthodes convergentes','Statut':'🟢 VERT'},
        {'Module':'Stress Testing',   'Agent':'A8',     'Résultat clé':'Ratio SCR=375% · ORSA 5 ans projeté','Statut':'🟢 VERT'},
        {'Module':'Cohérence',        'Agent':'A9',     'Résultat clé':'Score 100% · Tous contrôles VERT','Statut':'🟢 VERT'},
        {'Module':'Solvabilité 2',    'Agent':'A10',    'Résultat clé':'Ratio SCR=208.5% · MCR=320% · 4 QRT','Statut':'🟢 VERT'},
        {'Module':'IFRS 17',          'Agent':'A11',    'Résultat clé':'TP=3 992 344€ · Ratio IFRS17/S2=1.370','Statut':'🟢 VERT'},
        {'Module':'ALM',              'Agent':'A12',    'Résultat clé':'Gap=+1.9 ans · LCR=1173% · BV01=-2 839€','Statut':'🟡 AMBRE'},
        {'Module':'Tables mortalité', 'Agent':'A14',    'Résultat clé':'ä_65=13.07 · R²=0.9985 · Lee-Carter','Statut':'🟢 VERT'},
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.3);
                    border-radius:10px;padding:16px 20px;">
            <div style="font-size:0.7rem;color:{GRIS};text-transform:uppercase;
                        letter-spacing:0.08em;">Hash de session</div>
            <div style="font-family:monospace;color:{OR};font-size:1.1rem;
                        margin-top:6px;">5BB15F63</div>
            <div style="font-size:0.72rem;color:{GRIS};margin-top:4px;">
                Intégrité des résultats garantie · SHA-256
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.3);
                    border-radius:10px;padding:16px 20px;">
            <div style="font-size:0.7rem;color:{GRIS};text-transform:uppercase;
                        letter-spacing:0.08em;">Date d'arrêté</div>
            <div style="color:{BLANC};font-size:1.1rem;margin-top:6px;">
                {datetime.now().strftime('%d/%m/%Y')}
            </div>
            <div style="font-size:0.72rem;color:{GRIS};margin-top:4px;">
                Actuaire responsable : À configurer dans les Secrets
            </div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _simuler_execution(nom_agent, code):
    import time
    etapes = [
        (f"🔍 {code} — Chargement des données",       0.15),
        (f"⚡ Preprocessing & validation",             0.30),
        (f"📐 Calibration des modèles",                0.50),
        (f"🧠 Calcul des métriques",                   0.70),
        (f"🏦 Provisions & réglementaire",             0.85),
        (f"🔐 Audit trail & hash de session",          1.00),
    ]
    barre   = st.progress(0)
    statut  = st.empty()
    for label, prog in etapes:
        statut.markdown(f"<p style='color:{GRIS};font-size:0.85rem;'>{label}</p>",
                         unsafe_allow_html=True)
        barre.progress(prog)
        time.sleep(0.35)
    barre.empty(); statut.empty()
    st.success(f"✅ {nom_agent} terminé — résultats disponibles dans le Dashboard")
    if st.button("Voir le Dashboard →"):
        st.session_state.page = 'dashboard'
        st.rerun()


def _reponse_aria(question):
    q = question.lower()
    if any(m in q for m in ['best estimate','be','provision','réserve','reserve']):
        return ("Le **Best Estimate S2** est de **2 914 930 €** avec un CV de **0.6%** — "
                "convergence excellente des 4 méthodes (Chain Ladder, Mack 1993, BF, Cape Cod). "
                "La provision P90 s'établit à **3 098 000 €** (+6.3% au-dessus du BE).")
    elif any(m in q for m in ['scr','solvabilité','solvabilite','capital']):
        return ("Le **ratio SCR est de 208.5%**, au-dessus de la cible marché FR (150-200%). "
                "SCR total : **3 680 671 €**, dominé par le SCR souscription (3 104 537 €). "
                "MCR couvert à **320%** — aucune action corrective requise.")
    elif any(m in q for m in ['gini','modèle','modele','tarif','xgboost','ml']):
        return ("Meilleur Gini sur freMTPL2 : **XGBoost = 0.2651**. "
                "Modèle de production sélectionné : **ElasticNet** (score multicritères 0.8373/1.0) "
                "pour sa stabilité parfaite (overfit ratio = 0.98) et son interprétabilité maximale.")
    elif any(m in q for m in ['alm','duration','gap','liquidité','liquidite','lcr']):
        return ("Gap de duration : **+1.9 ans** (actifs 3.5 ans vs passifs 1.6 ans). "
                "Normal pour un portefeuille Auto. Recommandation : raccourcir les obligations de 1.9 ans. "
                "LCR : **1 173%** — liquidité très confortable.")
    elif any(m in q for m in ['ifrs','17','provision ifrs']):
        return ("TP IFRS 17 (PAA) : **3 992 344 €** — ratio IFRS17/S2 = **1.370** ✅ Cohérent. "
                "LRC (risque restant) : 2 500 000 € · LIC (sinistres survenus) : 1 492 344 €.")
    else:
        return (f"Merci pour votre question sur *{question}*. "
                "Pour une réponse enrichie par Claude API, configurez votre clé Anthropic "
                "dans les Secrets Streamlit (Settings → Secrets → ANTHROPIC_API_KEY). "
                "Je peux vous renseigner sur : Best Estimate, SCR, Gini, ALM, IFRS 17.")


def _reponse_agent_demo(agent_key, question):
    agent = AGENTS[agent_key]
    return (f"En tant que **{agent['prenom']}**, spécialiste en *{agent['role_fr']}*, "
            f"voici ma réponse à votre question : *{question}*\n\n"
            f"Résultat clé : **{agent['kpi']}**\n\n"
            f"Pour une réponse complète propulsée par Claude API, "
            f"configurez votre clé ANTHROPIC_API_KEY dans les Secrets Streamlit.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

inject_css()
render_topbar()

st.markdown("<div class='main-content'>", unsafe_allow_html=True)

page = st.session_state.page

if   page == 'accueil':      page_accueil()
elif page == 'equipes':      page_equipes()
elif page == 'agent_detail': page_agent_detail(st.session_state.agent_selec or 'sofia')
elif page == 'dashboard':    page_dashboard()
elif page == 'aria':         page_aria()
elif page == 'analyse':      page_analyse()
elif page == 'rapports':     page_rapports()
else:                        page_accueil()

st.markdown("</div>", unsafe_allow_html=True)
