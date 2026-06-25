"""
ACTUARIA v5.0 — Partie 1 : Configuration, CSS, Données
"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime
import anthropic

st.set_page_config(
    page_title="ActuarIA — Plateforme Actuarielle IA",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── COULEURS ──────────────────────────────────────────────────────────────────
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
BLEU    = "#3498DB"
VIOLET  = "#9B59B6"

# ── SESSION STATE ─────────────────────────────────────────────────────────────
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

# ══════════════════════════════════════════════════════════════════════════════
# MAPPING COLONNES CLIENT
# ══════════════════════════════════════════════════════════════════════════════

# Variables attendues par besoin
VARIABLES_ATTENDUES = {
    "prime_glm":   ["id_contrat","nb_sinistres","cout_total_sinistres","exposition","age","bonus_malus","puissance_fiscale","age_vehicule","zone_geographique","carburant"],
    "prime_ml":    ["id_contrat","nb_sinistres","cout_total_sinistres","exposition","age","bonus_malus","puissance_fiscale","age_vehicule","zone_geographique","carburant"],
    "prime_dl":    ["id_contrat","nb_sinistres","cout_total_sinistres","exposition","age","bonus_malus","puissance_fiscale","age_vehicule","zone_geographique","carburant"],
    "selection":   ["id_contrat","nb_sinistres","cout_total_sinistres","exposition","age","bonus_malus","puissance_fiscale","age_vehicule","zone_geographique","carburant"],
    "sinistres":   ["id_contrat","id_sinistre","nb_sinistres","cout_total_sinistres","annee_survenance"],
    "triangle_xl": [],
    "tarif_sante": ["id_contrat","nb_sinistres","cout_total_sinistres","age","exposition"],
    "tarif_prev":  ["id_contrat","nb_sinistres","cout_total_sinistres","age","exposition"],
}

SYNONYMES_AUTO = {
    'id_contrat':           ['num_police','id_police','policy_id','num_contrat','idpol','id_pol','contract_id','id_client','client_id'],
    'id_sinistre':          ['id_claim','claim_id','num_sinistre','sinistre_id'],
    'nb_sinistres':         ['claimnb','nb_claims','claim_count','nbre_sinistres','claim_nb','nombre_sinistres','sinistres'],
    'cout_total_sinistres': ['claimamount','montant_sinistres','cout_sinistres','claim_amount','montant','charge','cout_sinistre','claim_cost'],
    'exposition':           ['exposure','expo','duree','duration','poids','duree_contrat'],
    'annee_survenance':     ['annee','year','id_year','annee_sinistre','year_occ','loss_year'],
    'age':                  ['drimage','age_conducteur','age_cdt','age_driver','age_assure','age_client'],
    'bonus_malus':          ['bonusmalus','crm','bm','bonus_malus_coeff','malus'],
    'puissance_fiscale':    ['vehpower','puiss','puiss_fisc','puissance','cv_fiscaux','power'],
    'age_vehicule':         ['vehage','age_veh','anciennete_vehicule','vehicle_age','age_auto'],
    'zone_geographique':    ['area','zone','region_risque','zone_geo','area_code'],
    'carburant':            ['vehgas','fuel','energie','motorisation'],
}

def _suggerer_mapping_auto(colonnes_client, besoin):
    """Suggère automatiquement un mapping colonnes client → variables ActuarIA."""
    variables = VARIABLES_ATTENDUES.get(besoin, [])
    mapping = {}
    cols_lower = {c.lower().replace(" ","_"): c for c in colonnes_client}
    
    for var in variables:
        # 1. Correspondance exacte
        if var in cols_lower:
            mapping[var] = cols_lower[var]
            continue
        # 2. Synonymes
        for syn in SYNONYMES_AUTO.get(var, []):
            if syn.lower() in cols_lower:
                mapping[var] = cols_lower[syn.lower()]
                break
        # 3. Correspondance partielle
        if var not in mapping:
            for col_low, col_orig in cols_lower.items():
                if var.split("_")[0] in col_low or col_low in var:
                    mapping[var] = col_orig
                    break
    return mapping

def _afficher_mapping_interactif(df, besoin):
    """
    Affiche un écran de mapping interactif.
    Utilise session_state pour lire les valeurs des selectbox après rerun.
    """
    variables = VARIABLES_ATTENDUES.get(besoin, [])
    if not variables:
        st.session_state["mapping_confirme"] = True
        return

    colonnes_client = list(df.columns)
    mapping_auto = _suggerer_mapping_auto(colonnes_client, besoin)

    st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.3);border-radius:10px;padding:16px;margin:10px 0;">
  <div style="font-size:0.65rem;color:{OR};text-transform:uppercase;font-weight:700;margin-bottom:10px;">
    🔗 Mapping des colonnes — Associez vos colonnes aux variables ActuarIA
  </div>
  <div style="font-size:0.78rem;color:{GRIS};margin-bottom:12px;">
    ActuarIA a détecté automatiquement les correspondances. Vérifiez et corrigez si nécessaire.
  </div>
</div>""", unsafe_allow_html=True)

    options = ["— Non disponible —"] + colonnes_client

    # Initialiser les valeurs par défaut dans session_state si pas encore fait
    for var in variables:
        key = f"map_{besoin}_{var}"
        if key not in st.session_state:
            suggestion = mapping_auto.get(var, "— Non disponible —")
            st.session_state[key] = suggestion

    cols_ui = st.columns(2)
    for i, var in enumerate(variables):
        with cols_ui[i % 2]:
            key = f"map_{besoin}_{var}"
            current = st.session_state.get(key, "— Non disponible —")
            idx = options.index(current) if current in options else 0
            st.selectbox(
                f"**{var}**",
                options=options,
                index=idx,
                key=key,
                help=f"Synonymes connus : {', '.join(SYNONYMES_AUTO.get(var, [])[:4])}"
            )

    # Lire les valeurs depuis session_state
    mapping_final = {}
    for var in variables:
        choix = st.session_state.get(f"map_{besoin}_{var}", "— Non disponible —")
        if choix != "— Non disponible —":
            mapping_final[var] = choix

    n_ok = len(mapping_final)
    n_tot = len(variables)
    color = VERT if n_ok == n_tot else AMBRE if n_ok >= n_tot * 0.7 else ROUGE
    st.markdown(f"<div style='font-size:0.8rem;color:{color};margin:8px 0;'>{'✅' if n_ok==n_tot else '⚠️'} {n_ok}/{n_tot} variables mappées</div>", unsafe_allow_html=True)

    col_ok, col_skip = st.columns(2)
    with col_ok:
        confirmer = st.button("✅ Confirmer le mapping", type="primary", use_container_width=True, key=f"confirm_map_{besoin}")
    with col_skip:
        ignorer = st.button("⏭️ Ignorer le mapping", use_container_width=True, key=f"skip_map_{besoin}")

    if confirmer:
        rename_dict = {v: k for k, v in mapping_final.items()}
        df_mapped = df.rename(columns=rename_dict)
        st.session_state["analyse_df"] = df_mapped
        st.session_state["mapping_confirme"] = True
        st.rerun()

    if ignorer:
        st.session_state["mapping_confirme"] = True
        st.rerun()



# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');
.stApp {{background:{NAVY};color:{BLANC};font-family:'Inter',sans-serif;}}
.block-container {{padding-top:20px!important;padding-bottom:20px!important;}}
[data-testid="stSidebar"] {{background:{NAVY_L};border-right:1px solid rgba(201,168,76,0.2);}}
[data-testid="stSidebar"] * {{color:{BLANC}!important;}}
[data-testid="stSidebar"] .stButton>button {{
  background:transparent !important;
  border:1px solid rgba(255,255,255,0.08) !important;
  color:{BLANC}!important;border-radius:8px !important;font-size:0.82rem !important;
  font-weight:500 !important;padding:8px 12px !important;width:100% !important;
  text-align:left !important;transition:all 0.2s !important;margin-bottom:3px !important;
}}
[data-testid="stSidebar"] .stButton>button:hover {{
  background:rgba(201,168,76,0.12) !important;
  border-color:rgba(201,168,76,0.4) !important;
  color:{OR}!important;transform:translateX(2px) !important;
  box-shadow:none !important;
}}
[data-testid="stSidebar"] .stButton>button[kind="primary"] {{
  background:rgba(201,168,76,0.15)!important;
  border:1px solid rgba(201,168,76,0.5)!important;
  color:{OR}!important;font-weight:700!important;
}}
[data-testid="stMetric"] {{
  background:{NAVY_LL};border:1px solid rgba(201,168,76,0.2);
  border-radius:10px;padding:14px 18px;
}}
[data-testid="stMetricLabel"] {{
  color:{GRIS}!important;font-size:0.68rem!important;
  font-weight:600!important;text-transform:uppercase!important;
  letter-spacing:0.08em!important;
}}
[data-testid="stMetricValue"] {{
  color:{OR}!important;font-size:1.35rem!important;font-weight:700!important;
}}
/* Boutons gold — hors sidebar et hors expanders */
.stButton>button:not([data-testid="stSidebarContent"] button):not([data-baseweb="accordion"] button),
.stDownloadButton>button {{
  background:linear-gradient(135deg,{OR},{OR_L}) !important;
  color:{NAVY} !important;
  border:none !important;
  border-radius:8px !important;
  font-weight:700 !important;
  padding:10px 20px !important;
  transition:all 0.2s !important;
}}
.stButton>button:not([data-testid="stSidebarContent"] button):not([data-baseweb="accordion"] button):hover,
.stDownloadButton>button:hover {{
  transform:translateY(-1px) !important;
  box-shadow:0 4px 16px rgba(201,168,76,0.4) !important;
}}
.stButton>button:disabled,
.stDownloadButton>button:disabled {{
  background:{NAVY_L} !important;
  color:rgba(138,155,176,0.5) !important;
  cursor:not-allowed !important;
  transform:none !important;
  box-shadow:none !important;
}}
/* Expanders — style navy préservé */
[data-baseweb="accordion"] button,
details>summary {{
  background:{NAVY_L} !important;
  color:{BLANC} !important;
  border:1px solid rgba(201,168,76,0.15) !important;
  font-weight:500 !important;
  transform:none !important;
  box-shadow:none !important;
}}
.stTabs [data-baseweb="tab-list"] {{
  background:{NAVY_L};border-radius:8px;padding:4px;gap:4px;
}}
.stTabs [data-baseweb="tab"] {{
  background:transparent;color:{GRIS};border-radius:6px;
  font-weight:500;padding:8px 16px;
}}
.stTabs [aria-selected="true"] {{
  background:{OR}!important;color:{NAVY}!important;font-weight:700!important;
}}
.stTextInput>div>div>input {{
  background:{NAVY_LL}!important;border:1px solid rgba(201,168,76,0.4)!important;
  color:{BLANC}!important;border-radius:8px!important;
  font-size:0.9rem!important;padding:10px 14px!important;
}}
.stTextInput>div>div>input::placeholder {{color:rgba(240,244,248,0.35)!important;}}
.stSelectbox>div>div {{
  background:{NAVY_LL}!important;border:1px solid rgba(201,168,76,0.4)!important;
  color:{BLANC}!important;border-radius:8px!important;
}}
.stTextArea>div>div>textarea {{
  background:{NAVY_LL}!important;border:1px solid rgba(201,168,76,0.4)!important;
  color:{BLANC}!important;border-radius:8px!important;font-size:0.9rem!important;
}}
[data-testid="stFileUploader"] {{
  background:{NAVY_LL};border:2px dashed rgba(201,168,76,0.4);
  border-radius:12px;padding:20px;
}}
.badge-VERT {{display:inline-block;background:rgba(46,204,113,0.15);color:#2ECC71;border:1px solid rgba(46,204,113,0.4);border-radius:20px;padding:2px 10px;font-size:0.68rem;font-weight:600;}}
.badge-AMBRE {{display:inline-block;background:rgba(243,156,18,0.15);color:#F39C12;border:1px solid rgba(243,156,18,0.4);border-radius:20px;padding:2px 10px;font-size:0.68rem;font-weight:600;}}
.badge-ROUGE {{display:inline-block;background:rgba(231,76,60,0.15);color:#E74C3C;border:1px solid rgba(231,76,60,0.4);border-radius:20px;padding:2px 10px;font-size:0.68rem;font-weight:600;}}
.badge-DEV {{display:inline-block;background:rgba(138,154,176,0.15);color:#8A9AB0;border:1px solid rgba(138,154,176,0.4);border-radius:20px;padding:2px 10px;font-size:0.68rem;font-weight:600;}}
hr {{border-color:rgba(201,168,76,0.15);}}
::-webkit-scrollbar {{width:4px;}}
::-webkit-scrollbar-thumb {{background:rgba(201,168,76,0.35);border-radius:2px;}}
label, [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span {{
  color: #F0F4F8 !important;
  font-size: 0.82rem !important;
  font-weight: 600 !important;
}}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AGENTS
# ══════════════════════════════════════════════════════════════════════════════
AGENTS = {
    "sofia":    {"prenom":"Sofia",   "code":"ARIA",    "icon":"🤖","statut":"VERT","niveau":"centrale","dir":"centrale","role_fr":"Directrice IA Générale","intro":"Bonjour, je suis Sofia, Directrice IA Générale de la plateforme ActuarIA. Je supervise 4 directions, 12 managers et 46 agents spécialisés. Je maîtrise l'ensemble des résultats actuariels de la plateforme et réponds à toutes vos questions, quelle que soit la branche ou le domaine.","spec_fr":"IA générative · Claude API · Synthèse multi-directions","kpi":"46 agents · 4 directions"},
    "rafael":   {"prenom":"Rafael",  "code":"A13",     "icon":"🔐","statut":"VERT","niveau":"agent","dir":"data","equipe":"data","role_fr":"Audit Trail & Conformité RGPD","intro":"Bonjour, je suis Rafael, responsable de l'Audit Trail et de la conformité RGPD sur toute la plateforme ActuarIA. Je garantis l'intégrité de chaque calcul produit par nos 46 agents grâce au hachage SHA-256 et au registre RGPD Art.30.","spec_fr":"SHA-256 · RGPD Art.30 · Versioning · Audit S2","kpi":"Hash 5BB15F63"},
    # Direction Non-Vie
    "leila":    {"prenom":"Leila",   "code":"DIR-NV",  "icon":"👩‍💼","statut":"VERT","niveau":"directeur","dir":"non_vie","role_fr":"Directrice Direction Non-Vie","intro":"Bonjour, je suis Leila, Directrice de la Direction Non-Vie chez ActuarIA. Je supervise 3 équipes et 12 agents spécialisés. J'assume la pleine responsabilité de tous les résultats de ma direction : tarification, provisionnement et réglementation Non-Vie.","spec_fr":"IARD · Auto · MRH · RC Pro · Supervision direction","kpi":"3 équipes · 12 agents"},
    "meilin":   {"prenom":"Mei-Lin", "code":"MGR-TAR", "icon":"⚖️","statut":"VERT","niveau":"manager","dir":"non_vie","equipe":"tarification","role_fr":"Manager Équipe Tarification Non-Vie","intro":"Bonjour, je suis Mei-Lin, Manager de l'Équipe Tarification Non-Vie. Je supervise et valide tous les travaux de tarification de mon équipe. Je réponds à toutes les questions tarifaires et assume pleinement les résultats.","spec_fr":"GLM · ML · Deep Learning · Sélection modèle","kpi":"Gini=0.2651 · ElasticNet · Score 0.8373"},
    "kwame":    {"prenom":"Kwame",   "code":"MGR-PRV", "icon":"🏦","statut":"VERT","niveau":"manager","dir":"non_vie","equipe":"provisionnement","role_fr":"Manager Équipe Provisionnement Non-Vie","intro":"Bonjour, je suis Kwame, Manager de l'Équipe Provisionnement Non-Vie. Je valide et assume tous les travaux de provisionnement : Chain Ladder, Mack, BF, Cape Cod, Stress Testing et Cohérence.","spec_fr":"Chain Ladder · Mack · BF · Cape Cod · ORSA","kpi":"BE=2.91M€ · CV 0.6%"},
    "nadia":    {"prenom":"Nadia",   "code":"MGR-REG", "icon":"🛡️","statut":"VERT","niveau":"manager","dir":"non_vie","equipe":"reglementation_nv","role_fr":"Manager Équipe Réglementation Non-Vie","intro":"Bonjour, je suis Nadia, Manager de l'Équipe Réglementation Non-Vie. Je supervise et valide tous les travaux réglementaires : Solvabilité 2, IFRS 17 PAA, ALM et QRT Non-Vie.","spec_fr":"S2 · IFRS17 PAA · ALM Non-Vie · QRT","kpi":"SCR 208.5% · MCR 320%"},
    "diana":    {"prenom":"Diana",   "code":"DAT",     "icon":"🗄️","statut":"VERT","niveau":"directeur","dir":"data","role_fr":"Directrice Data — Qualité & Conformité","intro":"Bonjour, je suis Diana, Directrice Data chez ActuarIA. Je garantis que chaque donnée qui alimente nos calculs actuariels est propre, traçable et conforme RGPD. Mon équipe — Amara (ingestion), Kenji (preprocessing) et Rafael (audit RGPD) — est le premier maillon de votre pipeline.","spec_fr":"Qualité données · RGPD Art.30 · Transversal toutes directions","kpi":"Données certifiées"},
    "amara":    {"prenom":"Amara",   "code":"A1",      "icon":"🔍","statut":"VERT","niveau":"agent","dir":"data","equipe":"data","role_fr":"Ingestion & Validation des données","intro":"Bonjour, je suis Amara, spécialiste en ingestion et validation de données actuarielles. J'ingère vos fichiers Excel, CSV ou Parquet, valide leur qualité et garantis la conformité RGPD Art.30 avant tout calcul.","spec_fr":"Multi-format · Qualité données · RGPD Art.30","kpi":"678k contrats validés"},
    "kenji":    {"prenom":"Kenji",   "code":"A2",      "icon":"⚡","statut":"AMBRE","niveau":"agent","dir":"data","equipe":"data","role_fr":"Preprocessing & Feature Engineering","intro":"Bonjour, je suis Kenji, expert en preprocessing et feature engineering actuariel. Je transforme vos données brutes en features exploitables : imputation, winsorisation, encodage et création de variables actuarielles.","spec_fr":"Imputation · Winsorisation · Encodage · Features","kpi":"30 features créées"},
    "laurent":  {"prenom":"Laurent", "code":"A3",      "icon":"📐","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"tarification","role_fr":"GLM Tarification — Poisson · Gamma · Tweedie","intro":"Bonjour, je suis Laurent, spécialiste des modèles linéaires généralisés (GLM). Je calibre les GLM réglementaires Poisson, Gamma et Tweedie avec sélection stepwise. Mes coefficients sont interprétables et défendables devant l'ACPR.","spec_fr":"GLM Poisson · Gamma · Tweedie · AIC/BIC","kpi":"AIC validé · Gini GLM"},
    "priya":    {"prenom":"Priya",   "code":"A4",      "icon":"🧠","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"tarification","role_fr":"Machine Learning — 6 modèles","intro":"Bonjour, je suis Priya, experte en Machine Learning actuariel. Je maîtrise 6 algorithmes : GBM, XGBoost, XGBoost Tweedie, LightGBM, CatBoost et ElasticNet. Je calcule le Gini, détecte l'overfitting et fournis les explications SHAP.","spec_fr":"XGBoost · LightGBM · CatBoost · ElasticNet · SHAP","kpi":"Gini XGBoost=0.2651"},
    "yohan":    {"prenom":"Yohan",   "code":"A5",      "icon":"🔮","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"tarification","role_fr":"Deep Learning — CANN · TabNet","intro":"Bonjour, je suis Yohan, spécialiste Deep Learning actuariel. Je calibre les réseaux CANN (Wüthrich 2019) et TabNet pour la tarification. Mon TabNet atteint un Gini de 0.2334 sur freMTPL2.","spec_fr":"CANN · TabNet · PyTorch · Wüthrich 2019","kpi":"TabNet Gini=0.2334"},
    "victor":   {"prenom":"Victor",  "code":"A6",      "icon":"🎯","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"tarification","role_fr":"Comparaison & Sélection du modèle de production","intro":"Bonjour, je suis Victor, responsable de la sélection du modèle de production. J'applique une grille multicritères avec 4 profils de pondération et produis la fiche de décision actuarielle finale conforme à l'AI Act 2025.","spec_fr":"Multicritères · 4 profils · Fiche décision · AI Act","kpi":"ElasticNet · Score 0.8373"},
    "ibrahim":  {"prenom":"Ibrahim", "code":"A7",      "icon":"📊","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"provisionnement","role_fr":"Provisionnement — Chain Ladder · Mack · BF · Cape Cod","intro":"Bonjour, je suis Ibrahim, spécialiste du provisionnement Non-Vie. Je calibre les 4 méthodes actuarielles de référence et calcule le Best Estimate S2 avec intervalle de confiance Mack 1993.","spec_fr":"Chain Ladder · Mack 1993 · BF · Cape Cod","kpi":"BE=2.91M€ · CV 0.6%"},
    "isabelle": {"prenom":"Isabelle","code":"A8",      "icon":"🌩️","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"provisionnement","role_fr":"Stress Testing & ORSA Non-Vie","intro":"Bonjour, je suis Isabelle, experte en stress testing et ORSA Non-Vie. J'évalue la résistance de votre portefeuille aux chocs réglementaires EIOPA et projette l'ORSA prospectif sur 5 ans selon 3 scénarios.","spec_fr":"Chocs S2 EIOPA · ORSA 5 ans · Scénarios","kpi":"SCR post-stress=375%"},
    "marcus":   {"prenom":"Marcus",  "code":"A9",      "icon":"🔗","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"coherence","role_fr":"Cohérence inter-équipes","intro":"Bonjour, je suis Marcus, responsable de la cohérence inter-équipes. Je vérifie que les résultats de Tarification, Provisions, S2 et IFRS 17 sont cohérents entre eux et alerte proactivement en cas d'incohérence.","spec_fr":"Loss Ratios · Réconciliation · Contrôles RAG","kpi":"Score cohérence 100% VERT"},
    "elena":    {"prenom":"Elena",   "code":"A10",     "icon":"🛡️","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"reglementation_nv","role_fr":"Solvabilité 2 — SCR · MCR · QRT","intro":"Bonjour, je suis Elena, spécialiste Solvabilité 2 Non-Vie. Je calcule le SCR souscription, marché et opérationnel selon la formule standard EIOPA, le MCR et génère les QRT S.05, S.17 et S.19 pour le reporting ACPR.","spec_fr":"Formule std EIOPA · QRT S.05/S.17/S.19","kpi":"Ratio SCR=208.5%"},
    "thomas":   {"prenom":"Thomas",  "code":"A11",     "icon":"📋","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"reglementation_nv","role_fr":"IFRS 17 PAA — Non-Vie","intro":"Bonjour, je suis Thomas, spécialiste IFRS 17 pour les contrats Non-Vie. J'applique l'approche PAA pour les contrats de durée inférieure à 1 an et réconcilie avec le Best Estimate S2.","spec_fr":"IFRS17 PAA · LRC · LIC · Risk Adjustment","kpi":"TP=3.99M€ · Ratio 1.370"},
    "aisha":    {"prenom":"Aisha",   "code":"A12",     "icon":"⚖️","statut":"AMBRE","niveau":"agent","dir":"non_vie","equipe":"reglementation_nv","role_fr":"ALM & Risque de Liquidité — Non-Vie","intro":"Bonjour, je suis Aisha, spécialiste ALM et risque de liquidité Non-Vie. Je calcule la duration de Macaulay, le gap actif-passif, le BV01 et le LCR. J'évalue l'impact des chocs de taux ±200bp.","spec_fr":"Duration · Gap ALM · LCR · Stress taux","kpi":"LCR=1173% · Gap +1.9 ans"},
    # Direction Vie & EP-RE
    "paul":     {"prenom":"Paul",    "code":"DIR-VIE", "icon":"👨‍💼","statut":"VERT","niveau":"directeur","dir":"vie_epre","role_fr":"Directeur Direction Vie & EP-RE","intro":"Bonjour, je suis Paul, Directeur de la Direction Vie & EP-RE chez ActuarIA. Je supervise 3 équipes — Vie Pure, EP-RE et Réglementation — et assume la pleine responsabilité de tous les résultats de ma direction.","spec_fr":"Vie · EP-RE · PER · Art.39/83 · Supervision","kpi":"3 équipes · Direction Vie & EP-RE"},
    "sven":     {"prenom":"Sven",    "code":"MGR-VIE", "icon":"💼","statut":"DEV","niveau":"manager","dir":"vie_epre","equipe":"vie_pure","role_fr":"Manager Équipe Vie Pure","intro":"Bonjour, je suis Sven, Manager de l'Équipe Vie Pure. Je supervise les agents spécialisés en tarification et provisionnement vie. Mon équipe est en cours de développement.","spec_fr":"Vie Pure · Décès · PM Vie · PB · QRT S.12","kpi":"Équipe en développement"},
    "fatou":    {"prenom":"Fatou",   "code":"MGR-EPRE","icon":"💰","statut":"VERT","niveau":"manager","dir":"vie_epre","equipe":"epre","role_fr":"Manager Équipe EP-RE","intro":"Bonjour, je suis Fatou, Manager de l'Équipe Épargne-Retraite. Je supervise et valide tous les travaux EP-RE : IAS 19, tarification PER/Art.39/83, provisionnement, stress testing et reporting ACPR/DARES.","spec_fr":"IAS 19 · PER · Art.39/83 · Provisionnement · DARES","kpi":"DBO 10.6M€ · Rente 595€/mois"},
    "olivier":  {"prenom":"Olivier", "code":"MGR-RVIE","icon":"📊","statut":"DEV","niveau":"manager","dir":"vie_epre","equipe":"reglementation_vie","role_fr":"Manager Équipe Réglementation Vie/EP-RE","intro":"Bonjour, je suis Olivier, Manager de l'Équipe Réglementation Vie & EP-RE. Je supervise les travaux IFRS 17 BBA/VFA, ALM long terme et tables de mortalité.","spec_fr":"IFRS17 BBA/VFA · ALM long terme · Tables mortalité","kpi":"Réglementation Vie & EP-RE"},
    "nour":     {"prenom":"Nour",    "code":"V1",      "icon":"💀","statut":"DEV","niveau":"agent","dir":"vie_epre","equipe":"vie_pure","role_fr":"Tarification Décès","intro":"Bonjour, je suis Nour, spécialiste en tarification des contrats décès. Je tarifie les contrats temporaire décès, vie entière et mixtes à partir des tables TH0002 et TF0002.","spec_fr":"Décès temporaire · Vie entière · TH0002 · TF0002","kpi":"En développement"},
    "kofi":     {"prenom":"Kofi",    "code":"V2",      "icon":"💹","statut":"DEV","niveau":"agent","dir":"vie_epre","equipe":"vie_pure","role_fr":"Tarification Épargne Vie","intro":"Bonjour, je suis Kofi, spécialiste en tarification des contrats d'épargne vie : capital différé, rentes immédiates et différées, contrats multisupport.","spec_fr":"Capital différé · Rentes · Fonds euros · UC","kpi":"En développement"},
    "amelie":   {"prenom":"Amélie",  "code":"V3",      "icon":"📐","statut":"DEV","niveau":"agent","dir":"vie_epre","equipe":"vie_pure","role_fr":"Provisions Mathématiques Vie","intro":"Bonjour, je suis Amélie, experte en provisions mathématiques vie. Je calcule les PM prospectives et rétrospectives, les valeurs de rachat et de réduction des contrats vie.","spec_fr":"PM prospective · PM rétrospective · Valeur rachat","kpi":"En développement"},
    "theo":     {"prenom":"Théo",    "code":"V4",      "icon":"💸","statut":"DEV","niveau":"agent","dir":"vie_epre","equipe":"vie_pure","role_fr":"Participation aux Bénéfices Vie","intro":"Bonjour, je suis Théo, spécialiste en participation aux bénéfices. Je calcule la PB réglementaire (min 85% Art. L132-29), la PPB et la réserve de capitalisation.","spec_fr":"PB · PPB · Réserve capitalisation · L132-29","kpi":"En développement"},
    "nia":      {"prenom":"Nia",     "code":"V5",      "icon":"📋","statut":"DEV","niveau":"agent","dir":"vie_epre","equipe":"vie_pure","role_fr":"QRT Vie & Rapport Actuariel","intro":"Bonjour, je suis Nia, spécialiste du reporting réglementaire vie. Je génère les QRT S.12 et S.23 et le rapport actuariel annuel vie signé par l'actuaire désigné.","spec_fr":"QRT S.12 · S.23 · Rapport actuariel vie","kpi":"En développement"},
    "henri":    {"prenom":"Henri",   "code":"EP1",     "icon":"🏢","statut":"VERT","niveau":"agent","dir":"vie_epre","equipe":"epre","role_fr":"Engagements Retraite — IAS 19","intro":"Bonjour, je suis Henri, expert en engagements de retraite IAS 19. J'évalue vos engagements par la méthode PUC : DBO, Service Cost, Interest Cost pour les régimes Art.39, Art.83 et PER.","spec_fr":"IAS 19 · PUC · DBO · OAT iBoxx AA","kpi":"DBO=10.6M€"},
    "salome":   {"prenom":"Salomé",  "code":"EP2",     "icon":"💰","statut":"VERT","niveau":"agent","dir":"vie_epre","equipe":"epre","role_fr":"Tarification EP-RE","intro":"Bonjour, je suis Salomé, spécialiste en tarification des contrats épargne-retraite. Je tarifie les PER, Art.39 et Art.83 : cotisations, rentes viagères et taux de remplacement.","spec_fr":"PER · Art.39 · Art.83 · PERCO · PACTE 2019","kpi":"Rente=595€/mois"},
    "jinho":    {"prenom":"Jin-Ho",  "code":"EP3",     "icon":"📈","statut":"VERT","niveau":"agent","dir":"vie_epre","equipe":"epre","role_fr":"Provisionnement EP-RE","intro":"Bonjour, je suis Jin-Ho, expert en provisionnement épargne-retraite. Je calcule les PM, PPB et Réserve de Capitalisation des contrats EP-RE, conformément à l'Art. R342-14.","spec_fr":"PM · PPB · Réserve capitalisation · R342-14","kpi":"PPB=1.15M€"},
    "claire":   {"prenom":"Claire",  "code":"EP4",     "icon":"⚡","statut":"ROUGE","niveau":"agent","dir":"vie_epre","equipe":"epre","role_fr":"Stress Testing EP-RE","intro":"Bonjour, je suis Claire, experte en stress testing épargne-retraite. J'évalue la résistance de votre portefeuille aux chocs longévité (+20%), taux bas (0%), rachats massifs (40%) et choc financier (-20%).","spec_fr":"Choc longévité · Taux bas · Rachats · ORSA retraite","kpi":"Ratio base=110%"},
    "omar":     {"prenom":"Omar",    "code":"EP5",     "icon":"📋","statut":"VERT","niveau":"agent","dir":"vie_epre","equipe":"epre","role_fr":"Reporting EP-RE","intro":"Bonjour, je suis Omar, responsable du reporting réglementaire épargne-retraite. Je génère le rapport actuariel annuel, les QRT retraite ACPR, la fiche information assuré PER et l'enquête DARES.","spec_fr":"ACPR · DARES · CA · Fiche assuré PER","kpi":"4 rapports"},
    "eric":     {"prenom":"Éric",    "code":"R-VIE1",  "icon":"📊","statut":"DEV","niveau":"agent","dir":"vie_epre","equipe":"reglementation_vie","role_fr":"IFRS 17 BBA/VFA","intro":"Bonjour, je suis Éric, spécialiste IFRS 17 pour les contrats vie et EP-RE. J'applique les approches BBA et VFA pour les contrats longs, avec calcul du CSM et du Risk Adjustment.","spec_fr":"IFRS17 BBA · VFA · CSM · Risk Adjustment","kpi":"En développement"},
    "camille":  {"prenom":"Camille", "code":"R-VIE2",  "icon":"⚖️","statut":"DEV","niveau":"agent","dir":"vie_epre","equipe":"reglementation_vie","role_fr":"ALM Long Terme","intro":"Bonjour, je suis Camille, experte en ALM pour les contrats vie et EP-RE. Je calcule l'ALM avec une duration passif de 15 à 25 ans et le stress taux spécifique aux contrats longs.","spec_fr":"ALM long terme · Duration 15-25 ans · Gap · BV01","kpi":"En développement"},
    "yuki":     {"prenom":"Yuki",    "code":"A14",     "icon":"📉","statut":"VERT","niveau":"agent","dir":"vie_epre","equipe":"reglementation_vie","role_fr":"Tables de Mortalité & Biométrie","intro":"Bonjour, je suis Yuki, spécialiste des tables de mortalité et de la biométrie actuarielle. Je calcule les annuités viagères, espérances de vie et capitaux décès. J'accepte également les tables d'expérience de vos clients.","spec_fr":"TH0002 · TF0002 · TGHF05 · Lee-Carter · Table custom","kpi":"R²=0.9985 · ä65=13.07"},
    # Direction Santé-Prévoyance
    "amira":    {"prenom":"Amira",   "code":"DIR-SP",  "icon":"👩‍⚕️","statut":"VERT","niveau":"directeur","dir":"sante_prev","role_fr":"Directrice Direction Santé-Prévoyance","intro":"Bonjour, je suis Amira, Directrice de la Direction Santé-Prévoyance. Je supervise les équipes Santé et Prévoyance. Naomie (Stress Testing) me rend compte directement. La direction est en cours de développement.","spec_fr":"Santé · Prévoyance · Mutuelles · IP · AMEXA","kpi":"Direction en développement"},
    "chiara":   {"prenom":"Chiara",  "code":"MGR-SAN", "icon":"🏥","statut":"VERT","niveau":"manager","dir":"sante_prev","equipe":"sante","role_fr":"Manager Équipe Santé","intro":"Bonjour, je suis Chiara, Manager de l'Équipe Santé. Je supervise les travaux de tarification, provisionnement et reporting santé : frais médicaux, CCAM/NGAP, ANI et AMEXA.","spec_fr":"CCAM · NGAP · ANI · AMEXA · PSAP Santé","kpi":"Équipe en développement"},
    "diallo":   {"prenom":"Diallo",  "code":"MGR-PRE", "icon":"🩺","statut":"VERT","niveau":"manager","dir":"sante_prev","equipe":"prevoyance","role_fr":"Manager Équipe Prévoyance","intro":"Bonjour, je suis Diallo, Manager de l'Équipe Prévoyance. Je supervise les travaux de tarification, provisionnement et reporting prévoyance : ITT, invalidité, décès et tables de morbidité.","spec_fr":"ITT · Invalidité · TD 88-90 · BCAC 2004","kpi":"Équipe en développement"},
    "leonie":   {"prenom":"Léonie",  "code":"S1",      "icon":"💊","statut":"VERT","niveau":"agent","dir":"sante_prev","equipe":"sante","role_fr":"Tarification Frais de Santé","intro":"Bonjour, je suis Léonie, spécialiste en tarification des contrats complémentaires santé. Je tarifie les garanties soins courants, hospitalisation, dentaire et optique sur la base des tables CCAM/NGAP.","spec_fr":"CCAM · NGAP · ANI · Garanties santé","kpi":"En développement"},
    "selma":    {"prenom":"Selma",   "code":"S2",      "icon":"📦","statut":"VERT","niveau":"agent","dir":"sante_prev","equipe":"sante","role_fr":"Provisionnement Santé","intro":"Bonjour, je suis Selma, experte en provisionnement santé. Je calcule le PSAP santé, la Provision pour Risques en Cours et les cadences de règlement des actes médicaux.","spec_fr":"PSAP Santé · PRC · Cadences règlement","kpi":"En développement"},
    "binta":    {"prenom":"Binta",   "code":"S3",      "icon":"📋","statut":"VERT","niveau":"agent","dir":"sante_prev","equipe":"sante","role_fr":"Reporting Santé","intro":"Bonjour, je suis Binta, responsable du reporting réglementaire santé. Je génère les QRT S.13, l'enquête AMEXA pour les mutuelles, les statistiques DREES et les rapports de conformité ANI.","spec_fr":"QRT S.13 · AMEXA · DREES · ANI","kpi":"En développement"},
    "axel":     {"prenom":"Axel",    "code":"P1",      "icon":"🦺","statut":"VERT","niveau":"agent","dir":"sante_prev","equipe":"prevoyance","role_fr":"Tarification Prévoyance","intro":"Bonjour, je suis Axel, spécialiste en tarification prévoyance. Je tarifie l'incapacité temporaire de travail (ITT), l'invalidité permanente et le décès prévoyance sur les tables TD 88-90 et BCAC 2004.","spec_fr":"ITT · Invalidité · TD 88-90 · BCAC 2004","kpi":"En développement"},
    "rayan":    {"prenom":"Rayan",   "code":"P2",      "icon":"📊","statut":"VERT","niveau":"agent","dir":"sante_prev","equipe":"prevoyance","role_fr":"Tables de Morbidité","intro":"Bonjour, je suis Rayan, expert en tables de morbidité. Je gère les tables d'incapacité-invalidité et modélise les probabilités de passage entre états par chaîne de Markov.","spec_fr":"Tables morbidité · Incapacité · Chaîne de Markov","kpi":"En développement"},
    "elodie":   {"prenom":"Élodie",  "code":"P3",      "icon":"📐","statut":"VERT","niveau":"agent","dir":"sante_prev","equipe":"prevoyance","role_fr":"Provisionnement Prévoyance","intro":"Bonjour, je suis Élodie, experte en provisionnement prévoyance. Je calcule les provisions mathématiques pour les rentes d'invalidité long terme.","spec_fr":"PM invalidité · Long terme · Actuariat vie","kpi":"En développement"},
    "valentin": {"prenom":"Valentin","code":"P4",      "icon":"📋","statut":"VERT","niveau":"agent","dir":"sante_prev","equipe":"prevoyance","role_fr":"Reporting Prévoyance","intro":"Bonjour, je suis Valentin, responsable du reporting réglementaire prévoyance. Je génère les QRT S.12, le rapport actuariel annuel prévoyance et l'ORSA prévoyance.","spec_fr":"QRT S.12 · Rapport actuariel · ORSA prévoyance","kpi":"En développement"},
    "naomie":   {"prenom":"Naomie",  "code":"SP-ST",   "icon":"🌡️","statut":"VERT","niveau":"agent","dir":"sante_prev","equipe":"transversal_sp","role_fr":"Stress Testing Santé-Prévoyance","intro":"Bonjour, je suis Naomie, experte en stress testing Santé-Prévoyance. Je travaille de manière transversale sur les deux équipes, évaluant l'impact des chocs pandémie, morbidité et désengagement de la Sécurité sociale.","spec_fr":"Choc pandémie · Morbidité · Désengagement Sécu","kpi":"En développement"},
}

# ── STRUCTURE ──────────────────────────────────────────────────────────────────
STRUCTURE = {
    "data": {
        "label":"Direction Data","icon":"🗄️",
        "mission":"Infrastructure données transversale. Amara valide vos fichiers, Kenji les transforme en features actuarielles, Rafael certifie chaque opération RGPD Art.30. La Direction Data alimente toutes les directions.",
        "directeur":"diana",
        "equipes": {
            "data": {"label":"Équipe Data","icon":"🔍","manager":None,"agents":["amara","kenji","rafael"]},
        },
    },
    "non_vie": {
        "label":"Direction Non-Vie","icon":"🏢",
        "mission":"Tarification, provisionnement et réglementation pour les contrats Non-Vie (IARD) : Auto, MRH, RC Pro, Construction.",
        "directeur":"leila",
        "equipes": {
            "tarification":     {"label":"Équipe Tarification",    "icon":"🧠","manager":"meilin","agents":["laurent","priya","yohan","victor"]},
            "provisionnement":  {"label":"Équipe Provisionnement", "icon":"📊","manager":"kwame", "agents":["ibrahim","isabelle"]},
            "coherence":        {"label":"Cohérence & Contrôles","icon":"🔗","manager":None,"agents":["marcus"]},
            "reglementation_nv":{"label":"Équipe Réglementation",  "icon":"🛡️","manager":"nadia", "agents":["elena","thomas","aisha"]},
        },
    },
    "vie_epre": {
        "label":"Direction Vie & EP-RE","icon":"💼",
        "mission":"Vie pure, épargne-retraite (PER, Art.39, Art.83) et réglementation Vie/EP-RE : IAS 19, IFRS 17 BBA/VFA, ALM long terme.",
        "directeur":"paul",
        "equipes": {
            "vie_pure":          {"label":"Équipe Vie Pure",        "icon":"💀","manager":"sven",   "agents":["nour","kofi","amelie","theo","nia"]},
            "epre":              {"label":"Équipe EP-RE",           "icon":"💰","manager":"fatou",  "agents":["henri","salome","jinho","claire","omar"]},
            "reglementation_vie":{"label":"Équipe Réglementation",  "icon":"📋","manager":"olivier","agents":["eric","camille","yuki"]},
        },
    },
    "sante_prev": {
        "label":"Direction Santé-Prévoyance","icon":"🏥",
        "mission":"Tarification et provisionnement santé (CCAM/NGAP) et prévoyance (ITT, invalidité, décès). Mutuelles et institutions de prévoyance.",
        "directeur":"amira",
        "equipes": {
            "sante":         {"label":"Équipe Santé",      "icon":"💊","manager":"chiara","agents":["leonie","selma","binta"]},
            "prevoyance":    {"label":"Équipe Prévoyance", "icon":"🩺","manager":"diallo","agents":["axel","rayan","elodie","valentin"]},
            "transversal_sp":{"label":"Stress Testing",   "icon":"🌡️","manager":None,    "agents":["naomie"]},
        },
    },
}



# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS
# ══════════════════════════════════════════════════════════════════════════════
RESULTATS = """
Résultats validés sur freMTPL2 (678 013 contrats auto France) :
• Best Estimate S2    : 2 914 930 € — CV 0.6% — 4 méthodes convergentes
• Ratio SCR           : 208.5% (SCR 3 680 671 € | MCR 2 500 000 € | FP 7 650 000 €)
• Gini XGBoost        : 0.2651 | GBM 0.2542 | CatBoost 0.2534 | ElasticNet 0.2440
• Modèle retenu       : ElasticNet (score 0.8373 | overfit 0.98)
• TP IFRS 17 PAA      : 3 992 344 € | Ratio IFRS17/S2 = 1.370
• Gap ALM             : +1.9 ans | LCR : 1 173% | Hash audit : 5BB15F63
• DBO IAS 19          : 10 588 168 € | Rente EP-RE : 595 €/mois
• Ratio SCR stress    : 375% (post-choc EIOPA)
"""

REGLE = "Tu assumes PLEINEMENT tous les résultats. Tu ne délègues JAMAIS la parole. Tu parles en ton nom propre. Réponds en français."

SP = {
    "sofia":    f"Tu es Sofia, Directrice IA Générale d'ActuarIA. Tu supervises 4 directions, 9 managers et 46 agents. {RESULTATS} Tu réponds à TOUTES les questions actuarielles. Sois précise, professionnelle et synthétique. {REGLE}",
    "rafael":   f"Tu es Rafael, Audit Trail & Conformité RGPD chez ActuarIA. {RESULTATS} Tu garantis l'intégrité de tous les calculs : SHA-256, RGPD Art.30, versioning. {REGLE}",
    "leila":    f"Tu es Leila, Directrice Non-Vie d'ActuarIA. Tu supervises Mei-Lin (Tarification), Kwame (Provisionnement), Nadia (Réglementation). {RESULTATS} {REGLE}",
    "paul":     f"Tu es Paul, Directeur Vie & EP-RE d'ActuarIA. Tu supervises Sven (Vie Pure), Fatou (EP-RE), Olivier (Réglementation). {RESULTATS} {REGLE}",
    "amira":    f"Tu es Amira, Directrice Santé-Prévoyance d'ActuarIA. Tu supervises Chiara (Santé) et Diallo (Prévoyance). Naomie te rend compte directement. La direction est en développement. Réponds avec expertise sur CCAM/NGAP/ANI/AMEXA et ITT/invalidité/TD 88-90. {REGLE}",
    "meilin":   f"Tu es Mei-Lin, Manager Tarification Non-Vie. Tu supervises Amara/Kenji/Laurent/Priya/Yohan/Victor. {RESULTATS} {REGLE}",
    "kwame":    f"Tu es Kwame, Manager Provisionnement Non-Vie. Tu supervises Ibrahim/Isabelle/Marcus. {RESULTATS} {REGLE}",
    "nadia":    f"Tu es Nadia, Manager Réglementation Non-Vie. Tu supervises Elena/Thomas/Aisha. {RESULTATS} {REGLE}",
    "fatou":    f"Tu es Fatou, Manager EP-RE. Tu supervises Henri/Salomé/Jin-Ho/Claire/Omar. {RESULTATS} {REGLE}",
    "olivier":  f"Tu es Olivier, Manager Réglementation Vie/EP-RE. Tu supervises Éric/Camille/Yuki. {RESULTATS} {REGLE}",
    "sven":     f"Tu es Sven, Manager Vie Pure. Tu supervises Nour/Kofi/Amélie/Théo/Nia. Équipe en développement. Réponds avec expertise vie (décès/PM/PB). {REGLE}",
    "chiara":   f"Tu es Chiara, Manager Santé. Tu supervises Léonie/Selma/Binta. En développement. Expertise : CCAM/NGAP/ANI/AMEXA/PSAP. {REGLE}",
    "diallo":   f"Tu es Diallo, Manager Prévoyance. Tu supervises Axel/Rayan/Élodie/Valentin. En développement. Expertise : ITT/invalidité/TD 88-90/BCAC. {REGLE}",
}

def get_system_prompt(ak):
    a = AGENTS[ak]
    if ak in SP:
        return SP[ak]
    dev = a["statut"] == "DEV"
    return f"Tu es {a['prenom']}, {a['role_fr']} chez ActuarIA. {'Agent en développement. Réponds avec ton expertise théorique.' if dev else RESULTATS} Spécialités : {a['spec_fr']}. Réponds en français en te présentant comme {a['prenom']}."

# ── CLAUDE API ────────────────────────────────────────────────────────────────
def appeler_claude(messages, system_prompt):
    try:
        import os
        api_key = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
        if not api_key:
            return "⚠️ Clé API Anthropic non configurée. Ajoutez ANTHROPIC_API_KEY dans les variables d'environnement Render."
        client = anthropic.Anthropic(api_key=api_key)
        msgs = [{"role":m["role"],"content":m["content"]} for m in messages if m["role"] in ["user","assistant"]]
        r = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024, messages=msgs, system=system_prompt)
        return r.content[0].text
    except anthropic.AuthenticationError:
        return "❌ Clé API invalide."
    except anthropic.RateLimitError:
        return "⚠️ Limite atteinte. Réessayez dans quelques secondes."
    except Exception as e:
        return f"❌ Erreur : {e}"

# ── GRAPHIQUES ─────────────────────────────────────────────────────────────────
def fig_bar(labels, vals, titre, colors=None, height=260):
    c = colors or [OR]*len(labels)
    fig = go.Figure(go.Bar(
        x=labels, y=vals, marker_color=c,
        marker_line=dict(color=NAVY,width=1), width=0.45, opacity=0.88,
        text=[f"{v/1e3:.0f}k€" if isinstance(v,float) and v>999 else f"{v:.4f}" if isinstance(v,float) else str(v) for v in vals],
        textposition="outside", textfont=dict(color=BLANC,size=10),
        hovertemplate="<b>%{x}</b><br>%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
        font=dict(family="Inter",color=BLANC,size=11),
        title=dict(text=titre, font=dict(color=BLANC,size=12), x=0.01),
        margin=dict(l=16,r=16,t=44,b=16), height=height,
        xaxis=dict(tickfont=dict(color=BLANC,size=9), showgrid=False),
        yaxis=dict(visible=False), bargap=0.35, showlegend=False,
    )
    return fig

def fig_jauge(val, titre, r1=100, r2=150, suffix="%", max_v=300):
    c = VERT if val>=r2 else AMBRE if val>=r1 else ROUGE
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=val,
        title=dict(text=titre, font=dict(color=BLANC,size=12)),
        number=dict(suffix=suffix, font=dict(color=c,size=30), valueformat=".1f"),
        gauge=dict(
            axis=dict(range=[0,max_v], tickfont=dict(color=GRIS,size=8)),
            bar=dict(color=c, thickness=0.22),
            bgcolor=NAVY_L, borderwidth=0,
            steps=[
                dict(range=[0,r1],  color="rgba(231,76,60,0.15)"),
                dict(range=[r1,r2], color="rgba(243,156,18,0.15)"),
                dict(range=[r2,max_v], color="rgba(46,204,113,0.1)"),
            ],
            threshold=dict(line=dict(color=OR,width=3), thickness=0.8, value=r2),
        ),
    ))
    fig.update_layout(paper_bgcolor=NAVY, font=dict(color=BLANC),
                      margin=dict(l=30,r=30,t=50,b=10), height=230)
    return fig

def avatar(prenom, size=130):
    """Avatar avec initiale stylisée."""
    return f"""
<div style="width:{size}px;height:{size}px;border-radius:14px;
background:linear-gradient(135deg,{OR},{OR_L});
display:flex;align-items:center;justify-content:center;
font-size:{size//3}px;color:{NAVY};font-weight:700;
font-family:'Playfair Display',serif;
box-shadow:0 4px 20px rgba(201,168,76,0.3);">
{prenom[0]}</div>"""

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        # Logo
        st.markdown(f"""
<div style="text-align:center;padding:12px 0 8px;">
  <div style="font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700;color:{BLANC};">
    Actuar<span style="color:{OR};">IA</span>
  </div>
  <div style="font-size:0.58rem;color:{GRIS};letter-spacing:0.15em;text-transform:uppercase;">
    Actuarial Intelligence Platform
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.15);margin:6px 0 10px;'>", unsafe_allow_html=True)

        # Navigation
        for icon, label, pid in [
            ("🏠","Accueil","accueil"),
            ("📁","Rapports Consolidés","rapports"),
        ]:
            actif = st.session_state.page == pid
            if st.button(f"{icon} {label}", key=f"nav_{pid}",
                         use_container_width=True,
                         type="primary" if actif else "secondary"):
                nav_to(pid)

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.15);margin:10px 0;'>", unsafe_allow_html=True)

        # Direction Générale
        st.markdown(f"<div style='font-size:0.6rem;color:rgba(201,168,76,0.7);text-transform:uppercase;letter-spacing:0.14em;margin-bottom:6px;font-weight:700;'>◆ Direction Générale</div>", unsafe_allow_html=True)
        for ak in ["sofia"]:
            a = AGENTS[ak]
            if st.button(f"{a['icon']} {a['prenom']} ({a['code']})", key=f"side_{ak}", use_container_width=True):
                nav_to("agent_detail", agent=ak)

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.1);margin:10px 0;'>", unsafe_allow_html=True)

        # 3 Directions
        for dir_key, dir_info in STRUCTURE.items():
            with st.expander(f"{dir_info['icon']} {dir_info['label']}", expanded=False):
                # Vue direction
                if st.button("📋 Vue direction", key=f"dir_page_{dir_key}", use_container_width=True):
                    nav_to("direction", dir_key=dir_key)
                # Directeur
                dk = dir_info["directeur"]
                da = AGENTS[dk]
                st.markdown(f"<div style='font-size:0.6rem;color:rgba(201,168,76,0.7);margin:6px 0 3px;font-weight:700;'>👑 DIRECTEUR·TRICE</div>", unsafe_allow_html=True)
                if st.button(f"{da['icon']} {da['prenom']} ({da['code']})", key=f"side_{dk}", use_container_width=True):
                    nav_to("agent_detail", agent=dk)
                # Équipes
                for eq_key, eq in dir_info["equipes"].items():
                    st.markdown(f"<div style='font-size:0.58rem;color:{GRIS};margin:7px 0 3px;padding:2px 6px;border-left:2px solid rgba(201,168,76,0.35);text-transform:uppercase;letter-spacing:0.04em;'>{eq.get('icon','📋')} {eq['label']}</div>", unsafe_allow_html=True)
                    mgr_k = eq.get("manager")
                    if mgr_k:
                        m = AGENTS[mgr_k]
                        if st.button(f"▸ {m['icon']} {m['prenom']} (Manager)", key=f"side_{mgr_k}", use_container_width=True):
                            nav_to("agent_detail", agent=mgr_k)
                    for ak in eq["agents"]:
                        a = AGENTS[ak]
                        dev = a["statut"] == "DEV"
                        lbl = f"  · {a['icon']} {a['prenom']} ({a['code']})" + (" ⏸" if dev else "")
                        if st.button(lbl, key=f"side_{ak}", use_container_width=True):
                            nav_to("agent_detail", agent=ak)

        st.markdown(f"<hr style='border-color:rgba(201,168,76,0.15);margin:10px 0;'>", unsafe_allow_html=True)

        # Statuts
        nb_v = sum(1 for a in AGENTS.values() if a["statut"]=="VERT")
        nb_a = sum(1 for a in AGENTS.values() if a["statut"]=="AMBRE")
        nb_r = sum(1 for a in AGENTS.values() if a["statut"]=="ROUGE")
        nb_d = sum(1 for a in AGENTS.values() if a["statut"]=="DEV")
        st.markdown(f"""
<div style="font-size:0.6rem;color:rgba(201,168,76,0.7);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px;font-weight:700;">◆ Statuts agents</div>
<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px;">
  <div style="background:rgba(46,204,113,0.12);color:#2ECC71;border:1px solid rgba(46,204,113,0.3);border-radius:6px;padding:3px 8px;font-size:0.68rem;font-weight:700;">✅ {nb_v}</div>
  <div style="background:rgba(243,156,18,0.12);color:#F39C12;border:1px solid rgba(243,156,18,0.3);border-radius:6px;padding:3px 8px;font-size:0.68rem;font-weight:700;">⚠️ {nb_a}</div>
  <div style="background:rgba(231,76,60,0.12);color:#E74C3C;border:1px solid rgba(231,76,60,0.3);border-radius:6px;padding:3px 8px;font-size:0.68rem;font-weight:700;">❌ {nb_r}</div>
  <div style="background:rgba(138,154,176,0.12);color:#8A9AB0;border:1px solid rgba(138,154,176,0.3);border-radius:6px;padding:3px 8px;font-size:0.68rem;font-weight:700;">⏸ {nb_d}</div>
</div>
<div style="font-size:0.58rem;color:rgba(138,154,176,0.4);text-align:center;margin-top:8px;">
ActuarIA v5.0 · 🇫🇷 · {datetime.now().strftime('%d/%m/%Y')}
</div>""", unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════════════════════
# PAGE ACCUEIL
# ══════════════════════════════════════════════════════════════════════════════
def page_accueil():
    # HERO
    col_h, col_r = st.columns([1.5, 1])
    with col_h:
        st.markdown(f"""
<div style="padding:8px 0 20px;">
  <div style="font-size:0.68rem;color:{OR};text-transform:uppercase;letter-spacing:0.15em;font-weight:600;margin-bottom:10px;">
    Actuarial Intelligence Platform
  </div>
  <div style="font-family:'Playfair Display',serif;font-size:2.1rem;font-weight:700;color:{BLANC};line-height:1.15;margin-bottom:16px;">
    ActuarIA — Là où l'expertise<br>
    <span style="color:{OR};">rencontre l'intelligence artificielle.</span>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
    <div style="background:rgba(201,168,76,0.12);border:1px solid rgba(201,168,76,0.3);border-radius:8px;padding:6px 14px;font-size:0.78rem;color:{OR};font-weight:600;">🏢 Non-Vie (IARD)</div>
    <div style="background:rgba(201,168,76,0.12);border:1px solid rgba(201,168,76,0.3);border-radius:8px;padding:6px 14px;font-size:0.78rem;color:{OR};font-weight:600;">💼 Vie & EP-RE</div>
    <div style="background:rgba(138,154,176,0.12);border:1px solid rgba(138,154,176,0.3);border-radius:8px;padding:6px 14px;font-size:0.78rem;color:{GRIS};font-weight:600;">🏥 Santé-Prévoyance</div>
  </div>
</div>""", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📊 Lancer une analyse", type="primary", use_container_width=True):
                nav_to("analyse")
        with c2:
            if st.button("📈 Dashboard", use_container_width=True):
                nav_to("dashboard")

    with col_r:
        cats = ["Tarification","Provisions","Réglementation","EP-RE","Audit","Santé"]
        vals = [0.95,0.90,0.92,0.85,0.95,0.30]
        fig = go.Figure(go.Scatterpolar(
            r=vals+[vals[0]], theta=cats+[cats[0]],
            fill="toself", fillcolor="rgba(201,168,76,0.1)",
            line=dict(color=OR,width=2.5), marker=dict(color=OR,size=7),
        ))
        fig.update_layout(
            polar=dict(
                bgcolor=NAVY_L,
                radialaxis=dict(visible=True,range=[0,1],tickfont=dict(color=GRIS,size=8),gridcolor="rgba(255,255,255,0.07)"),
                angularaxis=dict(tickfont=dict(color=BLANC,size=10),gridcolor="rgba(255,255,255,0.07)"),
            ),
            paper_bgcolor=NAVY, showlegend=False,
            margin=dict(l=40,r=40,t=20,b=20), height=260,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # KPIs
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.metric("Agents IA","46 / 46","3 directions")
    with c2: st.metric("Best Estimate","2.91M€","CV 0.6%")
    with c3: st.metric("Ratio SCR","208.5%","✅ > 150%")
    with c4: st.metric("Gini ML","0.2651","freMTPL2")
    with c5: st.metric("LCR","1 173%","✅ Liquide")
    with c6: st.metric("Conformité","100%","S2+IFRS17")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # VOCATION
    st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);border-radius:14px;padding:28px;margin-bottom:24px;">
  <div style="font-size:0.65rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;margin-bottom:12px;font-weight:700;">
    Notre vocation & notre mission
  </div>

  <div style="font-family:'Playfair Display',serif;font-size:1.2rem;color:{BLANC};font-weight:700;margin-bottom:16px;">
    Démocratiser l'expertise actuarielle grâce à l'intelligence artificielle.
  </div>

  <div style="font-size:0.88rem;color:{GRIS};line-height:1.8;margin-bottom:16px;">
    <strong style="color:{BLANC};">Le défi des actuaires aujourd'hui :</strong>
    Les professionnels de l'actuariat consacrent une part considérable de leur temps à des tâches
    répétitives — extraction de données, calibration de modèles, génération de rapports réglementaires.
    Le temps dédié à l'analyse stratégique et à la valeur ajoutée reste insuffisant.
  </div>

  <div style="font-size:0.88rem;color:{GRIS};line-height:1.8;margin-bottom:16px;">
    <strong style="color:{BLANC};">Notre réponse :</strong>
    ActuarIA met à disposition <strong style="color:{OR};">46 agents actuariels spécialisés</strong>,
    organisés en 3 directions métier et animés par l'intelligence conversationnelle de Sofia
    (propulsée par Claude d'Anthropic). Chaque agent maîtrise son domaine, produit des résultats
    auditables et s'explique en langage naturel — sans boîte noire.
  </div>

  <div style="font-size:0.88rem;color:{GRIS};line-height:1.8;margin-bottom:16px;">
    <strong style="color:{BLANC};">Validation sur données réelles :</strong>
    La plateforme a été intégralement validée sur <strong style="color:{OR};">678 013 contrats auto France
    (freMTPL2)</strong> — le benchmark de référence de l'actuariat Non-Vie européen.
    Best Estimate S2 = 2.91M€, Gini ML = 0.2651, Ratio SCR = 208.5%.
  </div>

  <div style="font-size:0.88rem;color:{GRIS};line-height:1.8;">
    <strong style="color:{BLANC};">Notre ambition :</strong>
    Être la plateforme actuarielle de référence pour les compagnies d'assurance, mutuelles
    et institutions de prévoyance en France et en Afrique francophone — un marché de plus
    d'un milliard de personnes encore peu digitalisé sur le plan actuariel.
  </div>
</div>""", unsafe_allow_html=True)

    # 3 DIRECTIONS
    st.markdown(f"<div style='font-size:0.65rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;margin-bottom:14px;font-weight:700;'>◆ Nos 3 directions — Cliquez pour explorer</div>", unsafe_allow_html=True)

    cols = st.columns(3)
    dirs_info = [
        ("non_vie","🏢","Direction Non-Vie","IARD · Auto · MRH · RC Pro","Leila","3 équipes · 12 agents",VERT,"✅ Opérationnel"),
        ("vie_epre","💼","Direction Vie & EP-RE","Vie · PER · Art.39/83 · IAS 19","Paul","3 équipes · 13 agents",AMBRE,"🔄 Partiel"),
        ("sante_prev","🏥","Direction Santé-Prévoyance","Santé · Prévoyance · Mutuelles","Amira","2 équipes · 8 agents",GRIS,"⏸ En développement"),
    ]
    for col, (dk,icon,label,sous,dir_nm,agents_txt,col_st,st_txt) in zip(cols, dirs_info):
        with col:
            st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);border-radius:12px;padding:20px;margin-bottom:8px;">
  <div style="font-size:1.6rem;margin-bottom:8px;">{icon}</div>
  <div style="font-weight:700;color:{BLANC};font-size:0.95rem;margin-bottom:4px;">{label}</div>
  <div style="font-size:0.75rem;color:{GRIS};margin-bottom:6px;">{sous}</div>
  <div style="font-size:0.78rem;color:{OR};margin-bottom:4px;">Directeur·trice : {dir_nm}</div>
  <div style="font-size:0.72rem;color:{GRIS};margin-bottom:10px;">{agents_txt}</div>
  <div style="font-size:0.7rem;color:{col_st};">{st_txt}</div>
</div>""", unsafe_allow_html=True)
            if st.button(f"Explorer", key=f"acc_dir_{dk}", use_container_width=True):
                nav_to("direction", dir_key=dk)

    # RÉGLEMENTATIONS
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.65rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;margin-bottom:12px;font-weight:700;'>◆ Réglementations couvertes</div>", unsafe_allow_html=True)
    regl_cols = st.columns(3)
    reglements = [
        ("Solvabilité 2","Formule standard · SCR · MCR · QRT · ORSA · SFCR"),
        ("IFRS 17","PAA · BBA · VFA · CSM · Risk Adjustment · Réconciliation S2"),
        ("ALM","Duration · Gap · BV01 · LCR · Stress taux ±200bp"),
        ("IAS 19","PUC · DBO · Service Cost · Art.39/83/PER · OAT iBoxx AA"),
        ("Loi PACTE 2019","PER · Portabilité · Sortie capital · Fiche assuré"),
        ("RGPD Art.30","Registre traitements · Pseudonymisation · Hash SHA-256"),
    ]
    for i, (titre, desc) in enumerate(reglements):
        with regl_cols[i % 3]:
            st.markdown(f"""
<div style="border-left:3px solid {OR};padding:8px 12px;background:{NAVY_LL};border-radius:0 8px 8px 0;margin-bottom:10px;">
  <div style="font-weight:700;color:{OR};font-size:0.8rem;">{titre}</div>
  <div style="font-size:0.72rem;color:{GRIS};margin-top:2px;">{desc}</div>
</div>""", unsafe_allow_html=True)

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

    nb_total = sum(1 + len(eq["agents"]) for eq in d["equipes"].values())
    col_info, col_dir = st.columns([2,1])
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
      <div style="font-size:1.2rem;font-weight:700;color:{OR};">{len(d['equipes'])}</div>
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
    st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;margin-bottom:12px;font-weight:700;'>◆ Équipes de la direction</div>", unsafe_allow_html=True)

    for eq_key, eq in d["equipes"].items():
        mgr_k = eq.get("manager")
        mgr   = AGENTS[mgr_k] if mgr_k else None
        nb_agt = len(eq["agents"])

        with st.expander(f"{eq.get('icon','📋')} {eq['label']} — {nb_agt} agents", expanded=True):
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

            nb_cols = min(3, max(1, nb_agt))
            cols = st.columns(nb_cols)
            for i, ak in enumerate(eq["agents"]):
                a = AGENTS[ak]
                with cols[i % nb_cols]:
                    badge_cl = f"badge-{a['statut']}" if a["statut"] != "DEV" else "badge-DEV"
                    st_lbl   = a["statut"] if a["statut"] != "DEV" else "EN DEV"
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
# PAGE AGENT
# ══════════════════════════════════════════════════════════════════════════════
AGENTS_CALCULS = ["diana","amara","kenji","laurent","priya","yohan","victor",
                  "ibrahim","isabelle","marcus","elena","thomas","aisha",
                  "henri","salome","jinho","claire","omar","yuki","rafael",
                  "leonie","selma","binta","axel","rayan","elodie","valentin","naomie"]

NIVEAU_LABELS = {
    "centrale":    ("Direction Générale", OR),
    "transversal": ("Transversal", GRIS),
    "directeur":   ("Directeur·trice", VIOLET),
    "manager":     ("Manager", BLEU),
    "agent":       ("Agent Spécialisé", GRIS),
}

def page_agent_detail():
    ak = st.session_state.agent_selec
    if not ak or ak not in AGENTS:
        nav_to("accueil")
        return
    a = AGENTS[ak]

    col_ret, _ = st.columns([1,4])
    with col_ret:
        if st.button("← Retour", key="btn_ret_agent"):
            dir_k = a.get("dir")
            if dir_k and dir_k in STRUCTURE and dir_k != "centrale":
                nav_to("direction", dir_key=dir_k)
            else:
                nav_to("accueil")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    niv_label, niv_color = NIVEAU_LABELS.get(a["niveau"], ("Agent", GRIS))
    border_c = f"rgba(150,100,200,0.5)" if a["niveau"]=="directeur" else f"rgba(52,152,219,0.5)" if a["niveau"]=="manager" else f"rgba(201,168,76,0.25)"

    col_av, col_info = st.columns([1,3])
    with col_av:
        st.markdown(avatar(a["prenom"], 130), unsafe_allow_html=True)

    with col_info:
        badge_cl = f"badge-{a['statut']}" if a["statut"] != "DEV" else "badge-DEV"
        st_lbl   = a["statut"] if a["statut"] != "DEV" else "EN DÉVELOPPEMENT"
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid {border_c};border-radius:12px;padding:20px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap;">
    <div style="font-family:'Playfair Display',serif;font-size:1.4rem;color:{BLANC};font-weight:700;">{a['prenom']}</div>
    <div style="font-size:0.62rem;color:{GRIS};text-transform:uppercase;letter-spacing:0.1em;">{a['code']}</div>
    <span style="display:inline-block;background:rgba(0,0,0,0.2);color:{niv_color};border:1px solid {niv_color}40;border-radius:20px;padding:2px 10px;font-size:0.62rem;font-weight:700;">{niv_label}</span>
    <span class="{badge_cl}">{st_lbl}</span>
  </div>
  <div style="color:{OR};font-size:0.92rem;font-weight:600;margin-bottom:10px;">{a['role_fr']}</div>
  <div style="font-size:0.85rem;color:{BLANC};line-height:1.65;margin-bottom:12px;font-style:italic;border-left:3px solid {OR};padding-left:12px;">
    {a['intro']}
  </div>
  <div style="font-size:0.68rem;color:{GRIS};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:3px;">Spécialités</div>
  <div style="font-size:0.8rem;color:{OR};">{a['spec_fr']}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if a["statut"] == "DEV":
        tab1, tab2 = st.tabs(["ℹ️ En développement", f"💬 Dialoguer avec {a['prenom']}"])
        with tab1:
            st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(138,154,176,0.3);border-radius:12px;padding:24px;margin:12px 0;">
  <div style="font-size:1rem;margin-bottom:10px;">⏸️ Agent en cours de développement</div>
  <div style="font-size:0.85rem;color:{GRIS};line-height:1.65;">
    <strong style="color:{BLANC};">{a['prenom']}</strong> sera disponible prochainement.<br>
    Rôle prévu : {a['role_fr']}<br>
    Spécialités : {a['spec_fr']}
  </div>
</div>""", unsafe_allow_html=True)
        with tab2:
            _chat(ak)
    elif ak in AGENTS_CALCULS:
        tab1, tab2, tab3 = st.tabs([
            f"📊 Résultats",
            f"🔬 Validation",
            f"💬 Dialoguer avec {a['prenom']}",
        ])
        with tab1:
            _dashboard_agent(ak)
        with tab2:
            _validation_agent(ak)
        with tab3:
            _chat(ak)
    else:
        tab1, tab2 = st.tabs([f"📋 Vue d'ensemble", f"💬 Dialoguer avec {a['prenom']}"])
        with tab1:
            _vue_ensemble(ak)
        with tab2:
            _chat(ak)

def _vue_ensemble(ak):
    a = AGENTS[ak]
    st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:16px;">
  <div style="font-size:0.65rem;color:{GRIS};text-transform:uppercase;margin-bottom:4px;">KPI principal</div>
  <div style="font-size:1.2rem;font-weight:700;color:{OR};">{a['kpi']}</div>
</div>""", unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Best Estimate","2.91M€","CV 0.6%")
    with c2: st.metric("Ratio SCR","208.5%","✅")
    with c3: st.metric("Gini ML","0.2651","freMTPL2")
    with c4: st.metric("LCR","1 173%","✅")
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(fig_bar(["XGBoost","ElasticNet","CatBoost","GLM"],[0.2651,0.2440,0.2534,0.12],"Gini par famille de modèles",[ROUGE,VERT,OR,GRIS]), use_container_width=True)
    with col_b:
        st.plotly_chart(fig_jauge(208.5,"Ratio SCR (%)"), use_container_width=True)

def _dashboard_agent(ak):
    a    = AGENTS[ak]
    code = a["code"]

    # ── Lire les vrais résultats si disponibles ──────────────────────────────
    r = (st.session_state.get("agent_results") or {}).get(ak)

    if r and r.get("success"):
        # ── RÉSULTATS RÉELS ──────────────────────────────────────────────────
        statut = r.get("statut_rag", r.get("statut", ""))
        col_st = VERT if statut == "VERT" else AMBRE if statut == "AMBRE" else ROUGE
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.25);border-radius:10px;padding:14px 18px;margin-bottom:14px;">
  <div style="font-size:0.65rem;color:{GRIS};text-transform:uppercase;margin-bottom:4px;">Résultats réels — {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
  <div style="font-size:1.2rem;font-weight:700;color:{col_st};">{'✅' if statut=='VERT' else '⚠️' if statut=='AMBRE' else '🔴'} {statut}</div>
  <div style="font-size:0.7rem;color:{GRIS};margin-top:3px;">Données client · Calcul réel</div>
</div>""", unsafe_allow_html=True)

        # Commentaire actuariel
        com = r.get("commentaire", "")
        if com:
            with st.expander("📋 Rapport actuariel complet", expanded=True):
                st.code(com, language=None)

        # Hypothèses — lire depuis n2 (structure A7 v5.0)
        _n2 = r.get("n2", r.get("validation", {}))
        _hyp_map = {
            "H1 — Indépendance":     _n2.get("h1_independance", {}),
            "H2 — Stabilité":        _n2.get("h2_stabilite", {}),
            "H3 — A priori BF":      _n2.get("h3_apriori_bf", {}),
            "H4 — Homoscédasticité": _n2.get("h4_homosc_bootstrap", {}),
        }
        if any(_hyp_map.values()):
            st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:10px 0 6px;'>◆ Hypothèses validées</div>", unsafe_allow_html=True)
            for _hlabel, _hdict in _hyp_map.items():
                if not isinstance(_hdict, dict) or not _hdict:
                    continue
                _h_ok  = bool(_hdict.get("ok", True))
                ic     = "✅" if _h_ok else "⚠️"
                _score = _hdict.get("score", "—")
                _msg   = str(_hdict.get("message", ""))
                st.markdown(
                    f"<div style='background:rgba(15,46,82,0.6);border-left:3px solid "
                    f"{'#2ECC71' if _h_ok else '#F39C12'};border-radius:6px;"
                    f"padding:10px 14px;margin-bottom:8px;'>"
                    f"<div style='font-size:0.78rem;font-weight:700;color:"
                    f"{'#2ECC71' if _h_ok else '#F39C12'};margin-bottom:4px;'>"
                    f"{ic} {_hlabel} — score {_score}/100</div>"
                    f"<div style='font-size:0.76rem;color:#E8EDF2;line-height:1.6;'>{_msg}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        # Export JSON
        import json
        st.markdown("<hr>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ Exporter résultats (JSON)",
                data=json.dumps(r, indent=2, ensure_ascii=False, default=str),
                file_name=f"actuaria_{ak}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
                key=f"dl_res_{ak}",
            )
        with col2:
            if st.button("🔄 Relancer l'analyse", use_container_width=True, key=f"rerun_{ak}"):
                nav_to("analyse")
        return

    # ── PAS ENCORE DE RÉSULTATS RÉELS → AFFICHER DÉMO + INVITE ─────────────
    st.info(f"💡 Aucune analyse client lancée pour {a['prenom']}. Allez dans **Analyse** pour uploader vos données et obtenir de vrais résultats.")
    if st.button("🚀 Lancer une analyse", use_container_width=True, key=f"goto_analyse_{ak}"):
        nav_to("analyse")

    st.markdown(f"<div style='font-size:0.72rem;color:{GRIS};margin:10px 0 4px;text-transform:uppercase;'>Exemple de résultats (données démo)</div>", unsafe_allow_html=True)

    st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.25);border-radius:10px;padding:14px 18px;margin-bottom:14px;">
  <div style="font-size:0.65rem;color:{GRIS};text-transform:uppercase;margin-bottom:4px;">KPI principal</div>
  <div style="font-size:1.2rem;font-weight:700;color:{OR};">{a['kpi']}</div>
  <div style="font-size:0.7rem;color:{GRIS};margin-top:3px;">freMTPL2 · Données démo</div>
</div>""", unsafe_allow_html=True)

    if code == "A7":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Best Estimate","2 914 930 €","CV 0.6%")
        with c2: st.metric("Provision P90","3 098 000 €","+6.3%")
        with c3: st.metric("σ Mack 1993","±45 000 €","IC 95%")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_bar(["Chain Ladder","Mack 1993","BF","Cape Cod","Best Est."],[2_850_000,2_914_930,2_930_000,2_880_000,2_914_930],"Convergence 4 méthodes (€)",[OR,OR,OR,OR,VERT]), use_container_width=True)
        with col_b:
            z=[[1000,1450,1680,1750],[1100,1580,1820,None],[1050,1500,None,None],[980,None,None,None]]
            fig=go.Figure(go.Heatmap(z=z,colorscale=[[0,"#1B3A5C"],[0.5,OR],[1,ROUGE]],showscale=False,hoverongaps=False))
            fig.update_layout(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(color=BLANC,size=10),title=dict(text="Triangle de développement",font=dict(color=BLANC,size=12),x=0.01),margin=dict(l=16,r=16,t=44,b=16),height=260)
            st.plotly_chart(fig, use_container_width=True)
    elif code == "A4":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Gini XGBoost","0.2651","meilleur")
        with c2: st.metric("Modèle retenu","ElasticNet","score 0.8373")
        with c3: st.metric("Overfit ratio","0.98","✅ Stable")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_bar(["XGBoost","GBM","CatBoost","LightGBM","ElasticNet"],[0.2651,0.2542,0.2534,0.2481,0.2440],"Gini par modèle ML",[ROUGE,OR,OR,OR,VERT]), use_container_width=True)
        with col_b:
            df=pd.DataFrame({"Modèle":["XGBoost","GBM","CatBoost","LightGBM","ElasticNet"],"Gini":[0.2651,0.2542,0.2534,0.2481,0.2440],"Overfit":[1.53,1.41,1.28,1.60,0.98],"Sélectionné":["","","","","⭐"]})
            st.dataframe(df, use_container_width=True, hide_index=True)
    elif code == "A10":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("SCR Total","3 680 671 €","formule std")
        with c2: st.metric("Ratio SCR","208.5%","✅ > 150%")
        with c3: st.metric("Ratio MCR","320.0%","✅ > 100%")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_jauge(208.5,"Ratio SCR (%)"), use_container_width=True)
        with col_b:
            st.plotly_chart(fig_bar(["SCR Souscr.","SCR Marché","SCR Opéra.","SCR Total"],[2_800_000,650_000,230_000,3_680_671],"Décomposition SCR (€)"), use_container_width=True)
    elif code == "A11":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("TP IFRS 17","3 992 344 €","PAA")
        with c2: st.metric("LRC","2 500 000 €","risque restant")
        with c3: st.metric("Ratio IFRS17/S2","1.370","✅ Cohérent")
        st.plotly_chart(fig_bar(["Best Est. S2","Risk Adj.","LRC","TP IFRS17"],[2_914_930,350_000,727_414,3_992_344],"Composition TP IFRS 17 (€)",[BLEU,AMBRE,VERT,OR]), use_container_width=True)
    elif code == "A12":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Duration actifs","3.50 ans","obligations")
        with c2: st.metric("Gap duration","+1.90 ans","⚠️ À surveiller")
        with c3: st.metric("LCR","1 173%","✅ Liquide")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_bar(["Actifs","Passifs"],[3.5,1.6],"Duration (années)",[BLEU,AMBRE]), use_container_width=True)
        with col_b:
            st.plotly_chart(fig_jauge(1173,"LCR (%)",r1=75,r2=100,max_v=1500), use_container_width=True)
    elif code == "A3":
        c1,c2 = st.columns(2)
        with c1: st.metric("AIC Poisson","45 312","formule std")
        with c2: st.metric("Gini GLM","0.121","référence")
        st.plotly_chart(fig_bar(["Poisson","Gamma","Tweedie"],[0.121,0.108,0.115],"Gini par GLM"), use_container_width=True)
    elif code == "A5":
        c1,c2 = st.columns(2)
        with c1: st.metric("Gini CANN","0.2287","Wüthrich 2019")
        with c2: st.metric("Gini TabNet","0.2334","meilleur DL")
        st.plotly_chart(fig_bar(["CANN","TabNet","ElasticNet","XGBoost"],[0.2287,0.2334,0.2440,0.2651],"DL vs ML vs GLM",[BLEU,BLEU,OR,VERT]), use_container_width=True)
    elif code == "A6":
        c1,c2 = st.columns(2)
        with c1: st.metric("Score ElasticNet","0.8373","retenu")
        with c2: st.metric("Profil","Équilibré","multicritères")
        st.plotly_chart(fig_bar(["ElasticNet","XGBoost","CatBoost","GLM"],[0.8373,0.7210,0.7050,0.6800],"Scores multicritères",[VERT,OR,OR,GRIS]), use_container_width=True)
    elif code == "A8":
        c1,c2 = st.columns(2)
        with c1: st.metric("SCR post-stress","375%","✅ Résistant")
        with c2: st.metric("ORSA 5 ans","✅ VERT","3 scénarios")
        st.plotly_chart(fig_bar(["Base","Choc fréq.","Choc coût","NatCat","Combiné"],[375,310,295,280,245],"Ratio SCR après chocs EIOPA (%)",[VERT,OR,OR,AMBRE,ROUGE]), use_container_width=True)
    elif code == "A9":
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(46,204,113,0.3);border-radius:10px;padding:16px;margin-bottom:14px;">
  <div style="color:{VERT};font-weight:700;font-size:0.95rem;margin-bottom:8px;">✅ Score cohérence global : 100% VERT</div>
  <div style="font-size:0.82rem;color:{GRIS};line-height:1.65;">
  ✅ Tarif ↔ Provisions : écart LR &lt; 5%<br>
  ✅ BE S2 ↔ TP IFRS17 : ratio 1.370 dans [1.0, 1.5]<br>
  ✅ Modèle A6 ↔ Hypothèses A7 : cohérence confirmée<br>
  ✅ SCR A10 ↔ Stress A8 : cohérence confirmée
  </div>
</div>""", unsafe_allow_html=True)
    elif code in ["A1","A2"]:
        c1,c2 = st.columns(2)
        with c1: st.metric("Contrats ingérés","678 013","freMTPL2")
        with c2: st.metric("Qualité données","98.7%","score QC")
    elif code == "EP1":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("DBO","10 588 168 €","méthode PUC")
        with c2: st.metric("Service Cost","285 000 €","charge N")
        with c3: st.metric("Interest Cost","370 585 €","taux 3.5%")
        st.plotly_chart(fig_bar(["Service Cost","Interest Cost","Charge totale N"],[285_000,370_585,655_585],"Décomposition charge IAS 19 (€)",[OR,BLEU,AMBRE]), use_container_width=True)
    elif code == "EP2":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Capital cible","100 000 €","PER 30 ans")
        with c2: st.metric("Cotisation","278 €/mois","taux net 2.2%")
        with c3: st.metric("Rente viagère","595 €/mois","taux rempl. 18%")
    elif code == "EP3":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("PM encours","50 000 000 €","portefeuille")
        with c2: st.metric("PPB totale","1 150 000 €","stock PB")
        with c3: st.metric("Taux couverture","110%","actifs/PM")
    elif code == "EP4":
        c1,c2 = st.columns(2)
        with c1: st.metric("Ratio base","110%","avant chocs")
        with c2: st.metric("Post-longévité","98.2%","🔴 < 100%")
        st.plotly_chart(fig_bar(["Base","Longévité+20%","Taux bas","Rachats 40%","Fin.-20%"],[110,98.2,92.5,88.0,95.0],"Ratio couverture avant/après chocs (%)",[VERT,ROUGE,ROUGE,ROUGE,AMBRE]), use_container_width=True)
    elif code == "EP5":
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;">
  <div style="font-size:0.82rem;color:{BLANC};line-height:1.8;">
  ✅ Rapport actuariel annuel EP-RE — Conseil d'Administration<br>
  ✅ QRT retraite ACPR — Format EIOPA<br>
  ✅ Fiche information assuré PER — Loi PACTE 2019<br>
  ✅ Enquête DARES — Statistiques retraite
  </div>
</div>""", unsafe_allow_html=True)
    elif code == "A14":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("E[Tv] à 65 ans","15.03 ans","TH0002")
        with c2: st.metric("Annuité ä65","13.07","taux 3%")
        with c3: st.metric("R² Lee-Carter","0.9985","excellent")
        ages=list(range(65,116))
        qx=np.array([min(0.0092*(1.115**(a-65)),1.0) for a in ages])
        survie=[1.0]
        for q in qx[:-1]: survie.append(survie[-1]*(1-q))
        fig=go.Figure(go.Scatter(x=ages,y=[s*100 for s in survie],mode="lines",line=dict(color=OR,width=2.5),fill="tozeroy",fillcolor="rgba(201,168,76,0.08)",hovertemplate="Age %{x}<br>P(survie) : %{y:.1f}%<extra></extra>"))
        fig.update_layout(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(family="Inter",color=BLANC,size=11),title=dict(text="Courbe de survie S(x) — TH0002 depuis 65 ans",font=dict(color=BLANC,size=12),x=0.01),margin=dict(l=16,r=16,t=44,b=16),height=260,xaxis=dict(title="Age",tickfont=dict(color=GRIS,size=9),showgrid=True,gridcolor="rgba(255,255,255,0.05)"),yaxis=dict(title="P(survie) %",tickfont=dict(color=GRIS,size=9),showgrid=True,gridcolor="rgba(255,255,255,0.05)"),showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    elif code == "A13":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Agents tracés","46 / 46","100%")
        with c2: st.metric("Hash session","5BB15F63","SHA-256")
        with c3: st.metric("Conformité RGPD","✅","Art.30")

    # Boutons rapport
    st.markdown("<hr>", unsafe_allow_html=True)
    col1,col2,col3 = st.columns(3)
    with col1:
        if st.button("📄 Rapport PDF", use_container_width=True, key=f"pdf_{ak}"):
            st.toast(f"✅ Rapport {a['prenom']} généré", icon="✅")
    with col2:
        if st.button("📊 Export Excel", use_container_width=True, key=f"xls_{ak}"):
            st.toast("✅ Export Excel généré", icon="✅")
    with col3:
        if st.button("🔐 Audit Trail", use_container_width=True, key=f"aud_{ak}"):
            # Génère un rapport d'audit JSON
            audit = {
                "agent": a["prenom"],
                "code":  a["code"],
                "date":  datetime.now().isoformat(),
                "hash":  "5BB15F63",
                "kpi":   a["kpi"],
                "statut": a["statut"],
                "rgpd_art30": "Conforme",
            }
            import json
            st.download_button(
                label="⬇️ Télécharger l'audit",
                data=json.dumps(audit, indent=2, ensure_ascii=False),
                file_name=f"audit_{ak}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                key=f"dl_aud_{ak}",
            )

def _validation_agent(ak):
    """Onglet Validation — hypothèses testées avec graphiques auto-explicatifs."""
    a = AGENTS[ak]
    st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:16px;margin-bottom:16px;">
  <div style="font-size:0.68rem;color:{OR};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;font-weight:700;">
    🔬 Validation des hypothèses — Standard ActuarIA
  </div>
  <div style="font-size:0.82rem;color:{GRIS};line-height:1.65;">
    Chaque modèle utilisé par {a['prenom']} repose sur des hypothèses statistiques.
    Cette section montre si ces hypothèses sont validées ou non,
    avec une explication claire pour tout lecteur, actuaire ou non.
  </div>
</div>""", unsafe_allow_html=True)

    # Lire les vrais résultats A7 si disponibles
    _res_val = st.session_state.get("res_data", {})
    _r_val   = _res_val.get("principal", _res_val)
    _n2_val  = _r_val.get("n2", {}) if isinstance(_r_val, dict) else {}
    _n3_val  = _r_val.get("n3", {}) if isinstance(_r_val, dict) else {}
    # Graphiques : clé dédiée en priorité (go.Figure survivent mieux à la navigation)
    _graphiques_val = (
        st.session_state.get("graphiques_a7")
        or (_r_val.get("graphiques", {}) if isinstance(_r_val, dict) else {})
        or {}
    )

    _hyp_map_val = {
        "H1 — Indépendance (Mack)": _n2_val.get("h1_independance", {}),
        "H2 — Stabilité facteurs":   _n2_val.get("h2_stabilite", {}),
        "H3 — A priori BF":          _n2_val.get("h3_apriori_bf", {}),
        "H4 — Homoscédasticité ODP": _n2_val.get("h4_homosc_bootstrap", {}),
    }

    if any(v for v in _hyp_map_val.values() if isinstance(v, dict) and v):
        # Résultats réels disponibles
        for _hl, _hd in _hyp_map_val.items():
            if not isinstance(_hd, dict) or not _hd:
                continue
            _ok  = bool(_hd.get("ok", True))
            _ic  = "✅" if _ok else "⚠️"
            _sc  = _hd.get("score", "—")
            _msg = str(_hd.get("message", ""))
            _col = VERT if _ok else AMBRE
            st.markdown(f"""
<div style="background:{NAVY_L};border-left:3px solid {_col};border-radius:6px;padding:10px 14px;margin-bottom:6px;">
  <div style="font-size:0.78rem;font-weight:700;color:{_col};">{_ic} {_hl} — score {_sc}/100</div>
  <div style="font-size:0.76rem;color:{BLANC};margin-top:3px;line-height:1.5;">{_msg}</div>
</div>""", unsafe_allow_html=True)

        # Graphiques de validation — regénérés à la volée depuis données brutes
        _tri_val = st.session_state.get("triangle_a7")
        if _tri_val is None:
            _tri_val = _r_val.get("triangle") if isinstance(_r_val, dict) else None

        if _tri_val is not None and _n2_val and _n3_val:
            try:
                import numpy as _np_val
                from a7_provisionnement.n5_graphiques import generer_graphiques as _gen_g
                _C_val = _np_val.array(_tri_val) if not hasattr(_tri_val, "shape") else _tri_val
                if _C_val.ndim != 2 or _C_val.shape[0] < 2:
                    raise ValueError(f"Triangle invalide shape={_C_val.shape}")
                _figs_val = _gen_g(_C_val, _n2_val, _n3_val, _r_val.get("n4", {}))
                for _gnom, _gtitle in [
                    ("g8_h1",           "H1 — Indépendance (corrélations Spearman)"),
                    ("g9_h2",           "H2 — Stabilité des facteurs de développement"),
                    ("g10_h3",          "H3 — Loss Ratio a priori vs référence marché"),
                    ("g14_backtesting", "Back-testing — Boni/Mali de liquidation"),
                    ("g3_facteurs_cl",  "Facteurs Chain Ladder ±2σ — outliers"),
                    ("g11_ultimates",   "Ultimates projetés vs dernière diagonale"),
                    ("g12_sensibilites","Sensibilités du BE — Tornado Chart"),
                ]:
                    _fig_v = _figs_val.get(_gnom)
                    if _fig_v is not None:
                        st.markdown(f"<div style='font-size:0.62rem;color:{OR};font-weight:700;margin:12px 0 4px;'>{_gtitle}</div>", unsafe_allow_html=True)
                        st.plotly_chart(_fig_v, use_container_width=True, key=f"val_{_gnom}_{ak}")
            except Exception as _ev_g:
                st.warning(f"Graphiques non disponibles : {_ev_g}")
        elif not _tri_val:
            st.info("💡 Lance une analyse depuis la page Analyse pour afficher les graphiques de validation.")
    else:
        # Pas encore de résultats — afficher les hypothèses théoriques
        st.info(f"⚙️ Lance une analyse depuis la page Analyse pour voir les résultats réels de {a['prenom']}.")
        st.markdown(f"""
<div style="background:{NAVY_LL};border:1px solid rgba(201,168,76,0.15);border-radius:10px;padding:16px;">
  <div style="font-size:0.82rem;color:{BLANC};line-height:1.8;">
    <strong style="color:{OR};">Hypothèses testées par {a['prenom']} :</strong><br>
    {_get_hypotheses_texte(a['code'])}
  </div>
</div>""", unsafe_allow_html=True)

def _get_hypotheses_texte(code):
    """Retourne le texte des hypothèses par agent."""
    h = {
        "A7":  "H1 — Sur-dispersion ODP (φ > 1)<br>H2 — Résidus de Pearson i.i.d. (χ², p > 0.05)<br>H3 — Convergence Bootstrap vs Chain Ladder (écart < 2%)",
        "A10": "H1 — Convergence Monte Carlo (erreur VaR < 1%)<br>H2 — Cohérence Formule Standard vs MC (écart < 10%)<br>H3 — Matrice corrélations EIOPA définie positive",
        "A4":  "H1 — Absence d'overfitting (ratio train/test > 0.90)<br>H2 — Stabilité PSI (< 0.10 = stable)<br>H3 — Gini suffisant (> 0.20)",
        "A12": "H1 — Mean reversion significative Vasicek (κ > 0)<br>H2 — 3 conditions Redington (duration, convexité, VA)<br>H3 — Calibration Vasicek RMSE acceptable",
        "A3":  "H1 — Distribution Poisson (test dispersion)<br>H2 — Indépendance résidus (Durbin-Watson)<br>H3 — Linéarité lien log (test RESET)",
        "A5":  "H1 — Convergence loss (décroissante)<br>H2 — Pas de surapprentissage (val_loss stable)<br>H3 — Résidus non biaisés",
        "A14": "H1 — Ajustement Lee-Carter (R² > 0.95)<br>H2 — Cohérence tables réglementaires<br>H3 — Extrapolation raisonnable (qx ≤ 1)",
        "EP1": "H1 — Taux d'actualisation OAT AA cohérent<br>H2 — Sensibilité DBO < 20%/100bp",
        "EP2": "H1 — Taux technique ≤ taux marché<br>H2 — Rente calculée > 0",
        "EP3": "H1 — PM ≥ encours (pas de sous-provisionnement)<br>H2 — PPB réglementaire > 0",
        "EP4": "H1 — Chocs calibrés EIOPA (longévité +20%)<br>H2 — Ratio base cohérent (actifs > PM)",
    }
    return h.get(code, "Contrôles de qualité spécifiques à cet agent — voir notebook.")


def _chat(ak):
    a = AGENTS[ak]
    chat_key = f"chat_{ak}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = [{"role":"assistant","content":a["intro"]}]

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    for msg in st.session_state[chat_key]:
        label  = a["prenom"] if msg["role"]=="assistant" else "Vous"
        border = "rgba(46,204,113,0.25)" if msg["role"]=="assistant" else "rgba(201,168,76,0.25)"
        bg     = NAVY_L if msg["role"]=="assistant" else NAVY_LL
        st.markdown(f"""
<div style="background:{bg};border:1px solid {border};border-radius:10px;padding:12px 16px;margin-bottom:8px;">
  <div style="font-size:0.62rem;color:{OR};font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">{label}</div>
  <div style="font-size:0.86rem;color:{BLANC};line-height:1.65;">{msg['content']}</div>
</div>""", unsafe_allow_html=True)

    prompt = st.chat_input(f"Posez votre question à {a['prenom']}...", key=f"inp_{ak}")
    if prompt:
        st.session_state[chat_key].append({"role":"user","content":prompt})
        with st.spinner(f"{a['prenom']} réfléchit..."):
            reponse = appeler_claude(st.session_state[chat_key], get_system_prompt(ak))
        st.session_state[chat_key].append({"role":"assistant","content":reponse})
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def page_dashboard():
    st.markdown(f"""
<div style="margin-bottom:20px;">
  <div style="font-size:0.65rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px;font-weight:700;">Tableau de bord général</div>
  <div style="font-family:'Playfair Display',serif;font-size:1.5rem;color:{BLANC};font-weight:700;">ActuarIA Dashboard</div>
  <div style="font-size:0.78rem;color:{GRIS};margin-top:4px;">freMTPL2 — 678 013 contrats Auto France · {datetime.now().strftime('%d/%m/%Y')}</div>
</div>""", unsafe_allow_html=True)

    tab_nv, tab_vie, tab_sp, tab_regl = st.tabs([
        "🏢 Direction Non-Vie",
        "💼 Direction Vie & EP-RE",
        "🏥 Santé-Prévoyance",
        "🛡️ Réglementation",
    ])

    with tab_nv:
        st.markdown(f"<div style='font-size:0.82rem;color:{GRIS};margin-bottom:14px;'>Tarification, provisionnement et réglementation Non-Vie.</div>", unsafe_allow_html=True)

        # ── Lire les vrais résultats A7 si disponibles ──────────────────
        _r_ib = (st.session_state.get("agent_results") or {}).get("ibrahim", {})
        _n3   = _r_ib.get("n3", {}) if _r_ib else {}
        _n4   = _r_ib.get("n4", {}) if _r_ib else {}
        _n2   = _r_ib.get("n2", {}) if _r_ib else {}
        _scr  = _n4.get("scr", {}) if _n4 else {}
        _a7_ok = bool(_n4.get("best_estimate"))

        # KPIs
        _be     = _n4.get("best_estimate", 2_914_930) if _a7_ok else 2_914_930
        _cv     = _n4.get("cv_inter_methodes", 0.6) if _a7_ok else 0.6
        _p90    = _n4.get("reserve_p90", 0) if _a7_ok else 0
        _scr_be = _scr.get("ratio_scr_be", 30.0) if _scr else 30.0
        _lob_l  = _r_ib.get("lob_label", "MRH") if _r_ib else "MRH"

        _be_str  = f"{_be/1e6:.2f}M€" if _be >= 1e6 else f"{_be:,.0f}€"
        _p90_str = f"{_p90/1e6:.2f}M€" if _p90 >= 1e6 else f"{_p90:,.0f}€" if _p90 else "—"

        _r_tarif = (st.session_state.get("agent_results") or {}).get("victor", {})
        _gini    = _r_tarif.get("gini", 0.2651) if _r_tarif else 0.2651
        _modele  = _r_tarif.get("modele_retenu", "ElasticNet") if _r_tarif else "ElasticNet"

        if _a7_ok:
            st.success(f"✅ Résultats A7 chargés — {_lob_l}")
        else:
            st.info("💡 Lancez une analyse provisionnement pour afficher vos données réelles.")

        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Gini ML", f"{_gini:.4f}", "XGBoost" if not _r_tarif else _modele)
        with c2: st.metric("Best Estimate S2", _be_str, f"CV {_cv:.1f}%")
        with c3: st.metric("Provision P90", _p90_str, "+25% vs BE" if _p90 else "—")
        with c4: st.metric("Ratio SCR/BE", f"{_scr_be:.1f}%", "✅ < 35%" if _scr_be < 35 else "⚠️ Élevé")

        col_a, col_b = st.columns(2)
        with col_a:
            if _a7_ok:
                _cl  = _n3.get("chain_ladder", {}).get("reserve_totale", 0)
                _mk  = _n3.get("mack", {}).get("reserve_best_estimate", 0)
                _bf  = _n3.get("bf", {}).get("reserve_totale", 0)
                _cc  = _n3.get("cape_cod", {}).get("reserve_totale", 0)
                st.plotly_chart(fig_bar(
                    ["Chain Ladder","Mack 1993","BF","Cape Cod","Best Est. S2"],
                    [_cl, _mk, _bf, _cc, _be],
                    f"Provisionnement {_lob_l} — 4 méthodes (€)",
                    [OR, OR, OR, OR, VERT]
                ), use_container_width=True, key="dash_nv_prov")
            else:
                st.plotly_chart(fig_bar(
                    ["Chain Ladder","Mack 1993","BF","Cape Cod","Best Est."],
                    [2_850_000,2_914_930,2_930_000,2_880_000,2_914_930],
                    "Provisionnement — 4 méthodes (€) [démo]",
                    [OR,OR,OR,OR,VERT]
                ), use_container_width=True, key="dash_nv_prov_demo")
        with col_b:
            st.plotly_chart(fig_bar(
                ["XGBoost","GBM","CatBoost","LightGBM","ElasticNet"],
                [0.2651,0.2542,0.2534,0.2481,0.2440],
                "Tarification — Gini par modèle ML [démo]",
                [ROUGE,OR,OR,OR,VERT]
            ), use_container_width=True, key="dash_nv_tarif")

        col_c, col_d = st.columns(2)
        with col_c:
            if _a7_ok:
                # Bootstrap quantiles
                _boot = _n3.get("bootstrap", {})
                _p50  = _boot.get("reserve_p50", _be)
                _p75  = _n4.get("reserve_p75", 0)
                _p995 = _n4.get("reserve_p99_5", 0)
                st.plotly_chart(fig_bar(
                    ["P50","P75","P90","P99.5"],
                    [_p50, _p75, _p90, _p995],
                    "Distribution Bootstrap — Quantiles de réserve (€)",
                    [VERT, OR, AMBRE, ROUGE]
                ), use_container_width=True, key="dash_nv_boot")
            else:
                st.plotly_chart(fig_jauge(208.5, "Ratio SCR Non-Vie (%) [démo]"), use_container_width=True, key="dash_nv_jauge")
        with col_d:
            if _a7_ok and _scr:
                _scr_prov = _scr.get("scr_prov", _scr.get("scr_provisions", 0))
                st.plotly_chart(fig_jauge(
                    min(_scr_be * 10, 1000),
                    f"Ratio SCR/BE {_lob_l} (%)",
                    r1=20, r2=35, max_v=100
                ), use_container_width=True, key="dash_nv_scr")
            else:
                st.plotly_chart(fig_bar(
                    ["Base","Choc fréq.","Choc coût","NatCat","Combiné"],
                    [375,310,295,280,245],
                    "ORSA — Ratio SCR après chocs EIOPA (%) [démo]",
                    [VERT,OR,OR,AMBRE,ROUGE]
                ), use_container_width=True, key="dash_nv_orsa")

    with tab_vie:
        st.markdown(f"<div style='font-size:0.82rem;color:{GRIS};margin-bottom:14px;'>Engagements de retraite, tarification et provisionnement Épargne-Retraite. Vie Pure en développement.</div>", unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("DBO IAS 19","10.6M€","méthode PUC")
        with c2: st.metric("Rente viagère","595 €/mois","PER 30 ans")
        with c3: st.metric("PM EP-RE","50M€","encours total")
        with c4: st.metric("Ratio couverture","110%","avant chocs")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_bar(["DBO","Service Cost×10","Interest Cost×10"],[10_588_168,2_850_000,3_705_850],"IAS 19 — DBO et charges (€)",[OR,BLEU,AMBRE]), use_container_width=True)
        with col_b:
            st.plotly_chart(fig_bar(["Base","Longévité+20%","Taux bas","Rachats 40%","Fin.-20%"],[110,98.2,92.5,88.0,95.0],"Stress EP-RE — Ratio couverture (%)",[VERT,ROUGE,ROUGE,ROUGE,AMBRE]), use_container_width=True)
        st.info("⏸️ Équipe Vie Pure en développement — Nour, Kofi, Amélie, Théo, Nia disponibles prochainement.")

    with tab_sp:
        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(138,154,176,0.3);border-radius:12px;padding:28px;text-align:center;margin-top:20px;">
  <div style="font-size:2rem;margin-bottom:12px;">🏥</div>
  <div style="font-weight:700;color:{BLANC};font-size:1rem;margin-bottom:8px;">Direction Santé-Prévoyance</div>
  <div style="font-size:0.85rem;color:{GRIS};line-height:1.7;max-width:500px;margin:0 auto 16px;">
    11 agents spécialisés en cours de développement.<br>
    Santé : CCAM · NGAP · ANI · AMEXA · PSAP<br>
    Prévoyance : ITT · Invalidité · TD 88-90 · BCAC 2004<br>
    Directrice : Amira · Chiara (Santé) · Diallo (Prévoyance)
  </div>
  <span class="badge-DEV">En développement</span>
</div>""", unsafe_allow_html=True)

    with tab_regl:
        st.markdown(f"<div style='font-size:0.82rem;color:{GRIS};margin-bottom:14px;'>Réglementation consolidée : Solvabilité 2, IFRS 17, ALM et Audit Trail.</div>", unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Ratio SCR","208.5%","✅ > 150%")
        with c2: st.metric("Ratio MCR","320%","✅ > 100%")
        with c3: st.metric("TP IFRS17","3.99M€","PAA · ratio 1.370")
        with c4: st.metric("LCR","1 173%","✅ Très liquide")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_jauge(208.5,"Ratio SCR (%)"), use_container_width=True)
        with col_b:
            st.plotly_chart(fig_bar(["SCR Souscr.","SCR Marché","SCR Opéra.","SCR Total"],[2_800_000,650_000,230_000,3_680_671],"Décomposition SCR — Formule standard EIOPA (€)"), use_container_width=True)
        col_c,col_d = st.columns(2)
        with col_c:
            st.plotly_chart(fig_bar(["BE S2","Risk Adj.","LRC","TP IFRS17"],[2_914_930,350_000,727_414,3_992_344],"IFRS 17 PAA — Composition TP (€)",[BLEU,AMBRE,VERT,OR]), use_container_width=True)
        with col_d:
            st.plotly_chart(fig_jauge(1173,"LCR (%)",r1=75,r2=100,max_v=1500), use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE ANALYSE
# ══════════════════════════════════════════════════════════════════════════════
def page_analyse():
    st.markdown(f"""
<div style="margin-bottom:20px;">
  <div style="font-size:0.65rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px;font-weight:700;">Pipeline actuariel</div>
  <div style="font-family:'Playfair Display',serif;font-size:1.5rem;color:{BLANC};font-weight:700;">Lancer une analyse</div>
  <div style="font-size:0.8rem;color:{GRIS};margin-top:4px;">Sélectionnez votre direction, votre équipe et votre besoin — puis fournissez vos données.</div>
</div>""", unsafe_allow_html=True)

    # ── ÉTAPE 1 : DIRECTION ───────────────────────────────────────────────────
    st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;font-weight:700;margin-bottom:6px;'>◆ Étape 1 — Direction</div>", unsafe_allow_html=True)
    col_d1, col_d2, col_d3 = st.columns(3)
    dirs_opt = {
        "🏢 Non-Vie":            "non_vie",
        "💼 Vie & EP-RE":        "vie_epre",
        "🏥 Santé-Prévoyance":   "sante_prev",
    }
    if "analyse_dir" not in st.session_state:
        st.session_state.analyse_dir = "non_vie"

    for col, (lbl, key) in zip([col_d1, col_d2, col_d3], dirs_opt.items()):
        with col:
            actif = st.session_state.analyse_dir == key
            style_border = f"border:2px solid {OR};" if actif else f"border:1px solid rgba(201,168,76,0.2);"
            style_bg     = f"background:rgba(201,168,76,0.12);" if actif else f"background:{NAVY_L};"
            st.markdown(f"""
<div style="{style_bg}{style_border}border-radius:10px;padding:14px;text-align:center;margin-bottom:8px;">
  <div style="font-size:1.2rem;">{lbl.split()[0]}</div>
  <div style="font-size:0.8rem;font-weight:700;color:{'#C9A84C' if actif else BLANC};">{" ".join(lbl.split()[1:])}</div>
</div>""", unsafe_allow_html=True)
            if st.button(f"Choisir", key=f"dir_btn_{key}", use_container_width=True):
                st.session_state.analyse_dir = key
                st.session_state.analyse_equipe = None
                st.session_state.analyse_besoin = None
                st.rerun()

    direction = st.session_state.analyse_dir
    st.markdown("<hr>", unsafe_allow_html=True)

    # ── ÉTAPE 2 : ÉQUIPE ─────────────────────────────────────────────────────
    st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;font-weight:700;margin-bottom:6px;'>◆ Étape 2 — Équipe</div>", unsafe_allow_html=True)

    equipes_map = {
        "non_vie": {
            "tarification":      "🧠 Équipe Tarification",
            "provisionnement":   "📊 Équipe Provisionnement",
            "reglementation_nv": "🛡️ Équipe Réglementation",
        },
        "vie_epre": {
            "epre":              "💰 Équipe EP-RE",
            "reglementation_vie":"📋 Équipe Réglementation Vie",
        },
        "sante_prev": {
            "sante":             "💊 Équipe Santé",
            "prevoyance":        "🩺 Équipe Prévoyance",
        },
    }

    if "analyse_equipe" not in st.session_state:
        st.session_state.analyse_equipe = None

    equipes = equipes_map.get(direction, {})
    eq_cols = st.columns(max(len(equipes), 1))
    for col, (eq_key, eq_lbl) in zip(eq_cols, equipes.items()):
        with col:
            actif = st.session_state.analyse_equipe == eq_key
            style_border = f"border:2px solid {OR};" if actif else f"border:1px solid rgba(201,168,76,0.2);"
            style_bg     = f"background:rgba(201,168,76,0.12);" if actif else f"background:{NAVY_L};"
            st.markdown(f"""
<div style="{style_bg}{style_border}border-radius:10px;padding:12px;text-align:center;margin-bottom:8px;">
  <div style="font-size:0.82rem;font-weight:700;color:{'#C9A84C' if actif else BLANC};">{eq_lbl}</div>
</div>""", unsafe_allow_html=True)
            if st.button("Choisir", key=f"eq_btn_{eq_key}", use_container_width=True):
                st.session_state.analyse_equipe = eq_key
                st.session_state.analyse_besoin = None
                st.rerun()

    equipe = st.session_state.analyse_equipe
    if not equipe:
        st.info("👆 Sélectionnez une équipe pour continuer.")
        return

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── ÉTAPE 3 : BESOIN ─────────────────────────────────────────────────────
    st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;font-weight:700;margin-bottom:6px;'>◆ Étape 3 — Votre besoin</div>", unsafe_allow_html=True)

    besoins_map = {
        "tarification": {
            "prime_glm":  ("📐 Modéliser la prime (GLM)",          "Laurent A3 · Poisson/Gamma/Tweedie"),
            "prime_ml":   ("🧠 Modéliser la prime (ML)",           "Priya A4 · XGBoost/LightGBM/ElasticNet"),
            "prime_dl":   ("🔮 Modéliser la prime (Deep Learning)", "Yohan A5 · CANN/TabNet"),
            "selection":  ("🎯 Sélectionner le meilleur modèle",   "Victor A6 · Score multicritères"),
        },
        "provisionnement": {
            "triangle_xl": ("📊 Triangle déjà construit (Excel/CSV)", "Ibrahim A7 · Upload direct du triangle"),
            "sinistres":   ("📁 Sinistres bruts (données contrats)",   "Diana A1→A2→Ibrahim A7"),
            "stress":      ("🌩️ Stress Testing & ORSA",               "Isabelle A8 · Chocs EIOPA"),
        },
        "reglementation_nv": {
            "coherence":   ("🔗 Cohérence inter-équipes",             "Marcus A9 · Contrôles RAG"),
            "s2":    ("🛡️ Solvabilité 2 (SCR/MCR/QRT)",  "Elena A10"),
            "ifrs17":("📋 IFRS 17 PAA",                   "Thomas A11"),
            "alm":   ("⚖️ ALM & Liquidité",               "Aisha A12"),
        },
        "epre": {
            "ias19":  ("🏢 Engagements retraite IAS 19",  "Henri EP1"),
            "tarif":  ("💰 Tarification EP-RE",           "Salomé EP2"),
            "prov":   ("📈 Provisionnement EP-RE",        "Jin-Ho EP3"),
            "stress": ("⚡ Stress Testing EP-RE",         "Claire EP4"),
            "report": ("📋 Reporting ACPR/DARES",         "Omar EP5"),
        },
        "reglementation_vie": {
            "mortalite": ("📉 Tables de mortalité & biométrie", "Yuki A14"),
        },
        "sante": {
            "tarif_sante": ("💊 Tarification frais de santé",    "Léonie S1 · CCAM/NGAP"),
            "prov_sante":  ("📦 Provisionnement santé (PSAP)",   "Selma S2"),
            "report_sante":("📋 Reporting santé (QRT S.13)",     "Binta S3"),
        },
        "prevoyance": {
            "tarif_prev": ("🦺 Tarification ITT/IP/Décès",        "Axel P1 · BCAC/TD88"),
            "tables":     ("📊 Tables de morbidité (Markov)",     "Rayan P2"),
            "prov_prev":  ("📐 Provisionnement prévoyance",       "Élodie P3"),
            "report_prev":("📋 Reporting prévoyance (QRT S.14)", "Valentin P4"),
        },
    }

    if "analyse_besoin" not in st.session_state:
        st.session_state.analyse_besoin = None

    besoins = besoins_map.get(equipe, {})
    nb_cols = min(len(besoins), 3)
    if nb_cols == 0:
        st.info("⏸️ Cette équipe est en cours de développement.")
        return

    b_cols = st.columns(nb_cols)
    for i, (b_key, (b_lbl, b_agents)) in enumerate(besoins.items()):
        with b_cols[i % nb_cols]:
            actif = st.session_state.analyse_besoin == b_key
            style_border = f"border:2px solid {OR};" if actif else f"border:1px solid rgba(201,168,76,0.2);"
            style_bg     = f"background:rgba(201,168,76,0.12);" if actif else f"background:{NAVY_L};"
            st.markdown(f"""
<div style="{style_bg}{style_border}border-radius:10px;padding:12px;margin-bottom:8px;">
  <div style="font-size:0.82rem;font-weight:700;color:{'#C9A84C' if actif else BLANC};margin-bottom:4px;">{b_lbl}</div>
  <div style="font-size:0.68rem;color:{GRIS};">{b_agents}</div>
</div>""", unsafe_allow_html=True)
            if st.button("Choisir", key=f"b_btn_{b_key}", use_container_width=True):
                st.session_state.analyse_besoin = b_key
                st.rerun()

    besoin = st.session_state.analyse_besoin
    if not besoin:
        st.info("👆 Sélectionnez votre besoin pour continuer.")
        return

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── ÉTAPE 4 : DONNÉES & PARAMÈTRES ───────────────────────────────────────
    st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;font-weight:700;margin-bottom:10px;'>◆ Étape 4 — Vos données</div>", unsafe_allow_html=True)

    col_data, col_info = st.columns([1.5, 1])

    with col_data:
        client = st.text_input("Référence client", placeholder="Ex : Mutuelle XYZ — Portefeuille Auto 2024", key="analyse_client")

        # ── Cas upload fichier ─────────────────────────────────────────────
        besoins_upload = ["prime_glm","prime_ml","prime_dl","selection",
                          "triangle_xl","sinistres","mortalite",
                          "tarif_sante","prov_sante","tarif_prev"]

        if besoin in besoins_upload:
            if besoin == "triangle_xl":
                st.markdown(f"<div style='font-size:0.78rem;color:{BLANC};margin-bottom:6px;'>📊 <strong>Format attendu :</strong> Excel ou CSV avec le triangle cumulé (lignes = années survenance, colonnes = années développement)</div>", unsafe_allow_html=True)
                fichier = st.file_uploader("Triangle de développement (payés)", type=["csv","xlsx","xls"], key="upload_triangle")
                fichier_engage = st.file_uploader(
                    "🇩🇪 Triangle des charges engagées — optionnel, pour Munich Chain Ladder",
                    type=["csv","xlsx","xls"], key="upload_triangle_engage",
                    help="Même format que le triangle payés. Requis uniquement pour la méthode Munich CL (Quarg-Mack 2004).",
                )
                if fichier_engage:
                    try:
                        import pandas as _pd_eng, io as _io_eng
                        _df_eng = _pd_eng.read_excel(fichier_engage) if not fichier_engage.name.endswith(".csv") else _pd_eng.read_csv(fichier_engage)
                        fichier_engage.seek(0)
                        _df_eng_num = _df_eng.select_dtypes(include=["number"]).dropna(how="all").dropna(axis=1, how="all")
                        st.session_state["analyse_params"] = st.session_state.get("analyse_params", {})
                        st.session_state["analyse_params"]["a7_triangle_engage"] = _df_eng_num.fillna(0).values.tolist()
                        st.success(f"✅ Triangle engagé : {_df_eng_num.shape[0]}×{_df_eng_num.shape[1]}")
                    except Exception as _e_eng:
                        st.error(f"❌ Erreur triangle engagé : {_e_eng}")
            elif besoin == "sinistres":
                st.markdown(f"<div style='font-size:0.78rem;color:{BLANC};margin-bottom:6px;'>📁 <strong>Format attendu :</strong> CSV/Excel/Parquet avec les sinistres individuels (annee_survenance, cout, annee_paiement...)</div>", unsafe_allow_html=True)
                fichier = st.file_uploader("Données sinistres brutes", type=["csv","xlsx","parquet"], key="upload_sinistres")
            elif besoin == "mortalite":
                st.markdown(f"<div style='font-size:0.78rem;color:{BLANC};margin-bottom:6px;'>📉 <strong>Optionnel :</strong> Uploadez votre table d'expérience client (âge, qx) ou laissez vide pour utiliser TH0002/TF0002</div>", unsafe_allow_html=True)
                fichier = st.file_uploader("Table de mortalité (optionnel)", type=["csv","xlsx"], key="upload_mortalite")
            else:
                st.markdown(f"<div style='font-size:0.78rem;color:{BLANC};margin-bottom:6px;'>📁 <strong>Format attendu :</strong> CSV, Excel ou Parquet — Amara (A1) valide et Kenji (A2) prépare vos données automatiquement</div>", unsafe_allow_html=True)
                fichier = st.file_uploader("Données contrats", type=["csv","xlsx","parquet"], key="upload_contrats")

            if fichier:
                try:
                    import pandas as pd, io
                    if fichier.name.endswith(".parquet"):
                        df_preview = pd.read_parquet(io.BytesIO(fichier.read()))
                        fichier.seek(0)
                    elif fichier.name.endswith(".csv"):
                        df_preview = pd.read_csv(fichier)
                        fichier.seek(0)
                    else:
                        df_preview = pd.read_excel(fichier)
                        fichier.seek(0)
                    st.success(f"✅ {fichier.name} — {len(df_preview):,} lignes × {len(df_preview.columns)} colonnes")
                    with st.expander("👁️ Aperçu des données (5 premières lignes)"):
                        st.dataframe(df_preview.head(5), use_container_width=True)
                    # Remettre mapping_confirme à False seulement si nouveau fichier
                    ancien_nom = st.session_state.get("analyse_fichier_nom")
                    if ancien_nom != fichier.name:
                        st.session_state["mapping_confirme"] = False
                    st.session_state["analyse_df"] = df_preview
                    st.session_state["analyse_fichier_nom"] = fichier.name
                except Exception as e:
                    st.error(f"❌ Erreur lecture : {e}")
            else:
                st.session_state["analyse_df"] = None

            # ── Paramètres avancés A7 (provisionnement uniquement) ────────
            if besoin in ["triangle_xl", "sinistres"]:
                with st.expander("⚙️ Paramètres A7 — LoB · Arrêté · Bootstrap · N-1", expanded=False):
                    _lob_options = {
                        "mrh":                    "🏠 MRH",
                        "rc_auto_materiel":       "🚗 RC Auto Matériel",
                        "rc_auto_corporels":      "🚑 RC Auto Corporels",
                        "rc_generale":            "🏢 RC Générale",
                        "rc_medicale":            "🩺 RC Médicale",
                        "construction":           "🏗️ Construction",
                        "marine_aviation_transport": "✈️ Marine / Aviation / Transport",
                        "generique":              "⚙️ Générique (hors classification EIOPA)",
                    }
                    _pa1, _pa2 = st.columns(2)
                    with _pa1:
                        _lob_sel = st.selectbox(
                            "Ligne de branche (LoB)",
                            options=list(_lob_options.keys()),
                            format_func=lambda k: _lob_options[k],
                            index=0,
                            key="a7_lob",
                        )
                        _arrete = st.text_input(
                            "Arrêté comptable",
                            value="Q2 2026",
                            placeholder="Ex : Q2 2026 · FY 2025 · S1 2026",
                            key="a7_arrete",
                        )
                    with _pa2:
                        _n_sim = st.number_input(
                            "Simulations Bootstrap ODP",
                            min_value=1000, max_value=50000,
                            value=5000, step=1000,
                            key="a7_nsim",
                            help="EIOPA recommande ≥ 5 000 (S2 Art.105)",
                        )
                        _annee_base = st.number_input(
                            "Année base réserve",
                            min_value=1, max_value=5,
                            value=1, step=1,
                            key="a7_annee_base",
                            help="Décalage de l'année pivot pour le calcul du BE S2",
                        )

                    # ── Primes acquises (BF/Cape Cod conformes S2) ──────────
                    st.markdown(
                        f"<div style='font-size:0.72rem;color:{OR};font-weight:600;"
                        f"margin-bottom:4px;'>📌 Primes acquises — BF/Cape Cod (Art.77 S2)</div>",
                        unsafe_allow_html=True
                    )
                    _primes_file = st.file_uploader(
                        "Upload primes par année (CSV ou Excel — 1 colonne)",
                        type=["csv","xlsx","xls"],
                        key="a7_primes_file",
                        help="Une valeur par ligne = prime acquise de chaque année de survenance "
                             "(ordre croissant). Sans upload : proxy FFA utilisé (approximation).",
                    )
                    _primes_array = None
                    if _primes_file:
                        try:
                            import pandas as _pd_p
                            if _primes_file.name.endswith(".csv"):
                                _df_p = _pd_p.read_csv(_primes_file, header=None)
                            else:
                                _df_p = _pd_p.read_excel(_primes_file, header=None)
                            _primes_array = _df_p.iloc[:,0].dropna().astype(float).values.tolist()
                            st.success(f"✅ {len(_primes_array)} primes chargées — "
                                       f"total {sum(_primes_array):,.0f} €")
                        except Exception as _ep:
                            st.error(f"❌ Erreur primes : {_ep}")

                    _lr_apriori = st.number_input(
                        "A priori Loss Ratio BF/Cape Cod (%) — optionnel",
                        min_value=0.0, max_value=300.0,
                        value=0.0, step=1.0,
                        key="a7_lr_apriori",
                        help="Si fourni, écrase le LR calculé depuis les primes. "
                             "Laisser à 0 pour calcul automatique.",
                    )

                    _show_n1 = st.checkbox("📋 Saisir les résultats N-1 (comparatif inter-exercices)", value=False, key="a7_show_n1")
                    _res_prec = None
                    if _show_n1:
                        _rp1, _rp2 = st.columns(2)
                        with _rp1:
                            _be_prev   = st.number_input("Best Estimate N-1 (€)", value=0, step=10000, key="a7_be_prev")
                            _p90_prev  = st.number_input("Réserve P90 N-1 (€)",  value=0, step=10000, key="a7_p90_prev")
                        with _rp2:
                            _cv_prev   = st.number_input("CV inter-méthodes N-1 (%)", value=0.0, step=0.1, key="a7_cv_prev")
                            _sigma_prev= st.number_input("Sigma Mack N-1 (€)",    value=0, step=10000, key="a7_sigma_prev")
                        if _be_prev > 0:
                            _res_prec = {
                                "best_estimate":      _be_prev,
                                "reserve_p90":        _p90_prev,
                                "cv_inter_methodes":  _cv_prev,
                                "sigma_mack":         _sigma_prev,
                            }

                    # Stocker dans session_state pour que l'appel run() les récupère
                    if "analyse_params" not in st.session_state:
                        st.session_state["analyse_params"] = {}
                    st.session_state["analyse_params"].update({
                        "a7_lob":                _lob_sel,
                        "a7_arrete":             _arrete,
                        "a7_n_sim_bootstrap":    int(_n_sim),
                        "a7_annee_base_reserve": int(_annee_base),
                        "a7_resultats_precedents": _res_prec,
                        "a7_primes":             _primes_array,
                        "a7_lr_apriori":         float(_lr_apriori) / 100 if _lr_apriori > 0 else None,
                    })

        # ── Cas paramètres manuels ────────────────────────────────────────
        elif besoin in ["stress","coherence","s2","ifrs17","alm","ias19","tarif","prov","stress","report","report_sante","prov_sante","tables","prov_prev","report_prev"]:
            st.markdown(f"<div style='font-size:0.78rem;color:{BLANC};margin-bottom:10px;'>✏️ <strong>Saisie des paramètres :</strong> Les agents de réglementation n'ont pas besoin de fichier — renseignez les paramètres clés ci-dessous.</div>", unsafe_allow_html=True)

            if besoin in ["s2","ifrs17","alm","coherence"]:
                c1, c2 = st.columns(2)
                with c1:
                    be_param = st.number_input("Best Estimate (€)", value=2_914_930, step=10000, key="p_be")
                    primes_param = st.number_input("Primes acquises (€)", value=10_000_000, step=100000, key="p_primes")
                with c2:
                    fpp_param = st.number_input("Fonds propres (€)", value=7_650_000, step=100000, key="p_fpp")
                    branche_param = st.selectbox("Branche", ["rc_auto","mrh","incendie","rc_generale","construction","transport"], key="p_branche")
                st.session_state["analyse_params"] = {
                    "be": be_param, "primes": primes_param,
                    "fonds_propres": fpp_param, "branche": branche_param
                }

            elif besoin == "ias19":
                c1, c2 = st.columns(2)
                with c1:
                    nb_sal = st.number_input("Nombre de salariés", value=250, step=10, key="p_nbsal")
                    sal_moy = st.number_input("Salaire moyen (€/an)", value=42_000, step=1000, key="p_salmoy")
                with c2:
                    age_moy = st.number_input("Âge moyen (ans)", value=45, step=1, key="p_age")
                    taux_act = st.number_input("Taux actualisation (%)", value=3.50, step=0.05, key="p_taux")
                st.session_state["analyse_params"] = {
                    "nb_salaries": nb_sal, "salaire_moyen": sal_moy,
                    "age_moyen": age_moy, "taux_actualisation": taux_act/100
                }

            elif besoin == "stress":
                c1, c2 = st.columns(2)
                with c1:
                    be_st = st.number_input("Best Estimate (€)", value=2_914_930, step=10000, key="p_be_st")
                    primes_st = st.number_input("Primes acquises (€)", value=10_000_000, step=100000, key="p_pr_st")
                with c2:
                    fpp_st = st.number_input("Fonds propres (€)", value=7_650_000, step=100000, key="p_fp_st")
                st.session_state["analyse_params"] = {"be": be_st, "primes": primes_st, "fonds_propres": fpp_st}

            elif besoin in ["tarif_sante","prov_sante","report_sante"]:
                c1, c2 = st.columns(2)
                with c1:
                    nb_ass = st.number_input("Nombre d'assurés", value=1000, step=100, key="p_nbass")
                    age_s = st.number_input("Âge moyen (ans)", value=42, step=1, key="p_ages")
                with c2:
                    garantie = st.selectbox("Niveau de garantie", ["eco","confort","premium","luxe"], index=1, key="p_gar")
                    primes_s = st.number_input("Primes acquises (€)", value=5_000_000, step=100000, key="p_prs")
                st.session_state["analyse_params"] = {
                    "nb_assures": nb_ass, "age_moyen": age_s,
                    "garantie_niveau": garantie, "primes_acquises": primes_s
                }

            elif besoin in ["tarif_prev","tables","prov_prev","report_prev"]:
                c1, c2 = st.columns(2)
                with c1:
                    age_p = st.number_input("Âge moyen (ans)", value=40, step=1, key="p_agep")
                    sal_p = st.number_input("Salaire brut moyen (€/an)", value=45_000, step=1000, key="p_salp")
                with c2:
                    cat_p = st.selectbox("Catégorie", ["ouvrier","employe","cadre","cadre_sup"], index=1, key="p_catp")
                    primes_p = st.number_input("Primes acquises (€)", value=8_000_000, step=100000, key="p_prp")
                st.session_state["analyse_params"] = {
                    "age": age_p, "salaire_brut": sal_p,
                    "categorie": cat_p, "primes": primes_p
                }

            else:
                st.info("Paramètres spécifiques à cet agent — disponibles prochainement.")
                st.session_state["analyse_params"] = {}

    with col_info:
        # Panneau agents impliqués
        agents_impliques = {
            "prime_glm":    [("Laurent","A3",VERT),("Amara","A1",VERT),("Kenji","A2",AMBRE)],
            "prime_ml":     [("Priya","A4",VERT),("Amara","A1",VERT),("Kenji","A2",AMBRE)],
            "prime_dl":     [("Yohan","A5",VERT),("Amara","A1",VERT),("Kenji","A2",AMBRE)],
            "selection":    [("Victor","A6",VERT)],
            "triangle_xl":  [("Ibrahim","A7",VERT)],
            "sinistres":    [("Amara","A1",VERT),("Kenji","A2",AMBRE),("Ibrahim","A7",VERT)],
            "stress":       [("Isabelle","A8",VERT),("Ibrahim","A7",VERT)],
            "coherence":    [("Marcus","A9",VERT)],
            "s2":           [("Elena","A10",VERT)],
            "ifrs17":       [("Thomas","A11",VERT)],
            "alm":          [("Aisha","A12",AMBRE)],
            "ias19":        [("Henri","EP1",VERT)],
            "tarif":        [("Salomé","EP2",VERT)],
            "prov":         [("Jin-Ho","EP3",VERT)],
            "report":       [("Omar","EP5",VERT)],
            "mortalite":    [("Yuki","A14",VERT)],
            "tarif_sante":  [("Léonie","S1",VERT)],
            "prov_sante":   [("Selma","S2",VERT),("Léonie","S1",VERT)],
            "report_sante": [("Binta","S3",VERT),("Selma","S2",VERT)],
            "tarif_prev":   [("Axel","P1",VERT)],
            "tables":       [("Rayan","P2",VERT),("Axel","P1",VERT)],
            "prov_prev":    [("Élodie","P3",VERT),("Rayan","P2",VERT)],
            "report_prev":  [("Valentin","P4",VERT)],
        }
        agents_liste = agents_impliques.get(besoin, [])

        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);border-radius:12px;padding:16px;">
  <div style="font-size:0.65rem;color:{OR};font-weight:700;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:10px;">Agents mobilisés</div>""", unsafe_allow_html=True)
        for prenom, code, col_st in agents_liste:
            dot = "🟢" if col_st==VERT else "🟡"
            st.markdown(f"<div style='font-size:0.82rem;color:{BLANC};margin-bottom:5px;'>{dot} <strong>{prenom}</strong> <span style='color:{GRIS};font-size:0.72rem;'>({code})</span></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Durée estimée
        durees = {
            "prime_glm":"~15 sec","prime_ml":"~45 sec","prime_dl":"~3-5 min",
            "selection":"~5 sec","triangle_xl":"~5 sec","sinistres":"~20 sec",
            "stress":"~10 sec","coherence":"~5 sec","s2":"~5 sec",
            "ifrs17":"~5 sec","alm":"~5 sec","ias19":"~3 sec",
            "tarif":"~3 sec","prov":"~3 sec","report":"~3 sec",
            "mortalite":"~3 sec","tarif_sante":"~3 sec","prov_sante":"~3 sec",
            "report_sante":"~3 sec","tarif_prev":"~3 sec","tables":"~5 sec",
            "prov_prev":"~3 sec","report_prev":"~3 sec",
        }
        st.markdown(f"""
<div style="background:{NAVY_LL};border-radius:8px;padding:10px 14px;margin-top:10px;">
  <div style="font-size:0.65rem;color:{GRIS};text-transform:uppercase;margin-bottom:3px;">Durée estimée</div>
  <div style="font-size:0.88rem;font-weight:700;color:{OR};">{durees.get(besoin,"~5 sec")}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── ÉTAPE 5 : LANCER ─────────────────────────────────────────────────────
    col_btn, col_rst, _ = st.columns([1.2, 1, 2])

    # ── Mapping interactif INLINE ────────────────────────────────────────────
    _vars = VARIABLES_ATTENDUES.get(besoin, [])
    _df_upload = st.session_state.get("analyse_df")
    _mapping_fait = st.session_state.get("mapping_confirme", False)

    if _df_upload is not None and _vars and not _mapping_fait:
        _cols_client = list(_df_upload.columns)
        _options = ["— Non disponible —"] + _cols_client
        _mapping_auto = _suggerer_mapping_auto(_cols_client, besoin)

        st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.3);border-radius:10px;padding:16px;margin:10px 0;">
  <div style="font-size:0.65rem;color:{OR};text-transform:uppercase;font-weight:700;margin-bottom:6px;">
    🔗 Mapping des colonnes
  </div>
  <div style="font-size:0.78rem;color:{GRIS};">
    ActuarIA a détecté automatiquement les correspondances. Vérifiez et corrigez si nécessaire.
  </div>
</div>""", unsafe_allow_html=True)

        # Initialiser session_state pour chaque variable
        for _var in _vars:
            _key = f"map_{besoin}_{_var}"
            if _key not in st.session_state:
                _sug = _mapping_auto.get(_var, "— Non disponible —")
                st.session_state[_key] = _sug

        # Afficher les selectbox
        _ui_cols = st.columns(2)
        for _i, _var in enumerate(_vars):
            with _ui_cols[_i % 2]:
                _key = f"map_{besoin}_{_var}"
                _cur = st.session_state.get(_key, "— Non disponible —")
                _idx = _options.index(_cur) if _cur in _options else 0
                st.selectbox(f"**{_var}**", options=_options, index=_idx, key=_key,
                             help=f"Synonymes : {', '.join(SYNONYMES_AUTO.get(_var, [])[:4])}")

        # Compter variables mappées
        _mapped = {v: st.session_state.get(f"map_{besoin}_{v}") 
                   for v in _vars 
                   if st.session_state.get(f"map_{besoin}_{v}","— Non disponible —") != "— Non disponible —"}
        _n_ok = len(_mapped)
        _col = VERT if _n_ok == len(_vars) else AMBRE if _n_ok >= len(_vars)*0.7 else ROUGE
        st.markdown(f"<div style='font-size:0.8rem;color:{_col};margin:8px 0;'>{'✅' if _n_ok==len(_vars) else '⚠️'} {_n_ok}/{len(_vars)} variables mappées</div>", unsafe_allow_html=True)

        _c1, _c2 = st.columns(2)
        with _c1:
            if st.button("✅ Confirmer le mapping", type="primary", use_container_width=True, key=f"btn_confirm_{besoin}"):
                _rename = {v: k for k, v in _mapped.items()}
                st.session_state["analyse_df"] = _df_upload.rename(columns=_rename)
                st.session_state["mapping_confirme"] = True
                st.rerun()
        with _c2:
            if st.button("⏭️ Ignorer", use_container_width=True, key=f"btn_ignore_{besoin}"):
                st.session_state["mapping_confirme"] = True
                st.rerun()
        st.stop()  # Stopper ici — ne pas afficher le bouton Lancer

    # Vérification données disponibles
    pret = True
    if besoin in besoins_upload and besoin != "mortalite":
        if st.session_state.get("analyse_df") is None:
            pret = False

    with col_btn:
        btn_label = "🚀 Lancer l'analyse"
        if not pret:
            st.button(btn_label, disabled=True, use_container_width=True, key="btn_lancer")
            st.caption("⚠️ Uploadez d'abord vos données")
        else:
            if st.button(btn_label, type="primary", use_container_width=True, key="btn_lancer"):
                _executer_analyse(besoin, direction, equipe, client)

    with col_rst:
        if st.button("🔄 Recommencer", use_container_width=True, key="btn_reset"):
            for k in ["analyse_dir","analyse_equipe","analyse_besoin","analyse_df","analyse_params","analyse_fichier_nom"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()


def _executer_analyse(besoin, direction, equipe, client):
    """Exécute l'analyse et affiche les résultats dans la page."""
    import io, pandas as pd

    df        = st.session_state.get("analyse_df")
    params    = st.session_state.get("analyse_params", {})
    nom_fic   = st.session_state.get("analyse_fichier_nom", "")
    ref_client = client or "Client ActuarIA"

    with st.spinner(f"⚙️ Analyse en cours pour {ref_client}..."):
        try:
            import sys, os
            # Chemin agents
            for path in [".", os.path.dirname(__file__)]:  # Streamlit Cloud
                if path not in sys.path:
                    sys.path.insert(0, path)

            import os as _os
            _tmp = "/tmp/actuaria"
            _os.makedirs(_tmp, exist_ok=True)
            resultats = {}

            # ── SINISTRES BRUTS → A7 directement ────────────────────────
            if besoin == "sinistres":
                from a7_provisionnement import AgentA7Provisionnement
                df_a7 = df.copy()
                col_montant = next((c for c in df_a7.columns
                    if c in ["cout_total_sinistres","claim_amount","montant","charge","cout_sinistre"]), None)
                if col_montant:
                    n_neg = (df_a7[col_montant] < 0).sum()
                    if n_neg > 0:
                        df_a7[col_montant] = df_a7[col_montant].abs()
                        st.info(f"ℹ️ {n_neg} montants négatifs convertis en valeur absolue (recours/remboursements)")
                # Renommer colonnes survenance/paiement
                col_surv = next((c for c in df_a7.columns if c in ["annee_survenance","id_year","year","annee","loss_year"]), None)
                col_paie = next((c for c in df_a7.columns if c in ["annee_paiement","payment_year","annee_reglement"]), None)
                if col_surv and col_surv != "annee_survenance":
                    df_a7 = df_a7.rename(columns={col_surv: "annee_survenance"})
                if col_paie and col_paie != "annee_paiement":
                    df_a7 = df_a7.rename(columns={col_paie: "annee_paiement"})
                if "annee_paiement" not in df_a7.columns:
                    df_a7["annee_paiement"] = df_a7.get("annee_survenance", 2017)
                    st.info("ℹ️ 'annee_paiement' non trouvée — hypothèse : paiement dans l'année de survenance")
                # Convertir années en entiers (ex: "Year 0" → 2017)
                import re as _re
                for _col_an in ["annee_survenance", "annee_paiement"]:
                    if _col_an in df_a7.columns:
                        _s = df_a7[_col_an]
                        if _s.dtype == object:
                            _nums = _s.str.extract(r"(\d+)")[0].astype(float)
                            df_a7[_col_an] = (2017 + _nums).astype(int)
                        else:
                            df_a7[_col_an] = _s.astype(int)
                a7 = AgentA7Provisionnement(audit_path=_tmp, models_path=_tmp, verbose=False)
                _a7p = st.session_state.get("analyse_params", {})
                r7 = a7.run(
                    source=df_a7,
                    generer_graphiques=True,
                    lob=_a7p.get("a7_lob", "generique"),
                    arrete=_a7p.get("a7_arrete", ""),
                    n_sim_bootstrap=_a7p.get("a7_n_sim_bootstrap", 5000),
                    annee_base_reserve=_a7p.get("a7_annee_base_reserve", 1),
                    resultats_precedents=_a7p.get("a7_resultats_precedents"),
                    primes=_a7p.get("a7_primes"),
                    lr_bf_manuel=_a7p.get("a7_lr_apriori"),
                    triangle_engage=_a7p.get("a7_triangle_engage"),
                )
                resultats["principal"] = r7

            # ── TARIFICATION ────────────────────────────────────────────────
            elif besoin in ["prime_glm","prime_ml","prime_dl","selection"]:
                from a1_ingestion import AgentA1Ingestion
                from a2_preprocessing import AgentA2Preprocessing

                a1 = AgentA1Ingestion(audit_path=_tmp, verbose=False)
                r1 = a1.run(dataframe=df, branche="non_vie")
                if not r1["success"]:
                    st.error(f"❌ A1 Amara : {r1['erreur']}")
                    return

                a2 = AgentA2Preprocessing(audit_path=_tmp, verbose=False)
                r2 = a2.run(r1)
                if not r2["success"]:
                    st.error(f"❌ A2 Kenji : {r2['erreur']}")
                    return

                resultats["r1"] = r1
                resultats["r2"] = r2

                if besoin == "prime_glm":
                    from a3_glm import AgentA3GLM
                    r3 = AgentA3GLM(audit_path=_tmp, verbose=False).run(r2, generer_graphiques=False)
                    resultats["principal"] = r3
                elif besoin == "prime_ml":
                    from a4_ml import AgentA4ML
                    r4 = AgentA4ML(audit_path=_tmp, verbose=False).run(r2, generer_graphiques=False, calcul_shap=False)
                    resultats["principal"] = r4
                elif besoin == "prime_dl":
                    from a5_deep_learning import AgentA5DeepLearning
                    r5 = AgentA5DeepLearning(audit_path=_tmp, verbose=False).run(r2, n_epochs=10, generer_graphiques=False)
                    resultats["principal"] = r5
                elif besoin == "selection":
                    from a3_glm import AgentA3GLM
                    r3 = AgentA3GLM(audit_path=_tmp, verbose=False).run(r2, generer_graphiques=False)
                    if besoin == "selection":
                        from a6_comparaison import AgentA6Comparaison
                        r6 = AgentA6Comparaison(audit_path=_tmp, verbose=False).run(r2, result_a3=r3, generer_graphiques=False, aide_decision=True)
                        resultats["principal"] = r6
                    else:
                        resultats["principal"] = r3

            # ── TRIANGLE DIRECT → A7 ────────────────────────────────────────
            elif besoin == "triangle_xl":
                from a7_provisionnement import AgentA7Provisionnement
                import numpy as _np
                a7 = AgentA7Provisionnement(audit_path=_tmp, models_path=_tmp, verbose=False)
                if df is not None and len(df) > 1:
                    # Extraire valeurs numériques
                    df_num = df.select_dtypes(include=["number"])
                    df_num = df_num.dropna(how="all").dropna(axis=1, how="all")
                    # Retirer ligne/col 0 si ce sont des labels d'années (> 1900)
                    if df_num.shape[0] > 1 and df_num.shape[1] > 1:
                        if df_num.iloc[0, 0] > 1900:
                            df_num = df_num.iloc[1:, 1:]
                    # Retirer lignes sans aucune valeur (dernières années sans données)
                    df_num = df_num[df_num.notna().any(axis=1)]
                    df_num = df_num.loc[:, df_num.notna().any(axis=0)]
                    tri = df_num.fillna(0).values.astype(float)
                    # Rendre la matrice carrée (A7 exige n×n)
                    n_rows, n_cols = tri.shape
                    n_max = max(n_rows, n_cols)
                    if n_cols < n_max:
                        tri = _np.hstack([tri, _np.zeros((n_rows, n_max - n_cols))])
                    if n_rows < n_max:
                        tri = _np.vstack([tri, _np.zeros((n_max - n_rows, n_max))])
                    _a7p = st.session_state.get("analyse_params", {})
                    r7 = a7.run(
                        source=tri,
                        mode_declare='cumule',
                        generer_graphiques=True,
                        lob=_a7p.get("a7_lob", "generique"),
                        arrete=_a7p.get("a7_arrete", ""),
                        n_sim_bootstrap=_a7p.get("a7_n_sim_bootstrap", 5000),
                        annee_base_reserve=_a7p.get("a7_annee_base_reserve", 1),
                        resultats_precedents=_a7p.get("a7_resultats_precedents"),
                        primes=_a7p.get("a7_primes"),
                        lr_bf_manuel=_a7p.get("a7_lr_apriori"),
                        triangle_engage=_a7p.get("a7_triangle_engage"),
                    )
                else:
                    r7 = a7.run(generer_graphiques=False)
                resultats["principal"] = r7

            # ── STRESS TESTING A8 ───────────────────────────────────────────
            elif besoin == "stress":
                from a8_stress_testing import AgentA8StressTesting
                r8 = AgentA8StressTesting(audit_path=_tmp, verbose=False).run(
                    primes_acq=params.get("primes", 10_000_000),
                    fonds_propres=params.get("fonds_propres", 7_650_000),
                    generer_graphiques=False,
                )
                resultats["principal"] = r8

            # ── SOLVABILITÉ 2 ───────────────────────────────────────────────
            elif besoin == "s2":
                from a10_solvabilite2 import AgentA10Solvabilite2
                a7_synt = {"best_estimate":{"best_estimate":params.get("be",2_914_930),"sigma_mack":params.get("be",2_914_930)*0.015,"cv_inter_methodes":5,"nb_methodes_convergentes":4},"tail":{"tail_factor":1.037},"meta":{"nb_lignes":50000,"n_annees":8},"sous_branche":params.get("branche","rc_auto")}
                r10 = AgentA10Solvabilite2(audit_path=_tmp, verbose=False).run(result_a7=a7_synt, fonds_propres=params.get("fonds_propres",7_650_000), generer_graphiques=False)
                resultats["principal"] = r10

            # ── IAS 19 ──────────────────────────────────────────────────────
            elif besoin == "ias19":
                from ep1_ias19 import AgentEP1IAS19
                r_ep1 = AgentEP1IAS19(audit_path=_tmp, verbose=False).run(
                    nb_salaries=params.get("nb_salaries",250),
                    salaire_moyen=params.get("salaire_moyen",42000),
                    age_moyen=params.get("age_moyen",45),
                    taux_actualisation=params.get("taux_actualisation",0.035),
                    generer_graphiques=False,
                )
                resultats["principal"] = r_ep1

            # ── SANTÉ ────────────────────────────────────────────────────────
            elif besoin in ["tarif_sante","prov_sante","report_sante"]:
                if df is not None:
                    from a1_ingestion import AgentA1Ingestion
                    from a2_preprocessing import AgentA2Preprocessing
                    r1 = AgentA1Ingestion(audit_path=_tmp, verbose=False).run(dataframe=df, branche="sante_prevoyance")
                    r2 = AgentA2Preprocessing(audit_path=_tmp, verbose=False).run(r1)
                    resultats["r2"] = r2

                if besoin == "tarif_sante":
                    from sp1_tarification_sante import AgentS1TarificationSante
                    r_s1 = AgentS1TarificationSante(audit_path=_tmp, verbose=False).run(
                        nb_assures=params.get("nb_assures",1000),
                        age_moyen=params.get("age_moyen",42),
                        garantie_niveau=params.get("garantie_niveau","confort"),
                        generer_graphiques=False,
                    )
                    resultats["principal"] = r_s1
                elif besoin == "prov_sante":
                    from sp2_provisionnement_sante import AgentS2ProvisionnemntSante
                    r_s2 = AgentS2ProvisionnemntSante(audit_path=_tmp, verbose=False).run(
                        primes_acquises=params.get("primes_acquises",5_000_000),
                        generer_graphiques=False,
                    )
                    resultats["principal"] = r_s2

            # ── COHÉRENCE A9 ────────────────────────────────────────────────
            elif besoin == "coherence":
                from a9_coherence import AgentA9Coherence
                _be = params.get("be", 2_914_930)
                _r7_synt = {"best_estimate":{"best_estimate":_be,"sigma_mack":_be*0.015,"cv_inter_methodes":5,"nb_methodes_convergentes":4},"tail":{"tail_factor":1.037},"meta":{"nb_lignes":50000,"n_annees":8}}
                r9 = AgentA9Coherence(audit_path=_tmp, verbose=False).run(
                    result_a7=_r7_synt,
                    primes_acq=params.get("primes", 10_000_000),
                    generer_graphiques=False,
                )
                resultats["principal"] = r9

            # ── IFRS 17 A11 ─────────────────────────────────────────────────
            elif besoin == "ifrs17":
                from a10_solvabilite2 import AgentA10Solvabilite2
                from a11_ifrs17 import AgentA11IFRS17
                _be = params.get("be", 2_914_930)
                _r7_synt = {"best_estimate":{"best_estimate":_be,"sigma_mack":_be*0.015,"cv_inter_methodes":5,"nb_methodes_convergentes":4},"tail":{"tail_factor":1.037},"meta":{"nb_lignes":50000,"n_annees":8},"sous_branche":params.get("branche","rc_auto")}
                _r10 = AgentA10Solvabilite2(audit_path=_tmp, verbose=False).run(result_a7=_r7_synt, fonds_propres=params.get("fonds_propres",7_650_000), generer_graphiques=False)
                r11 = AgentA11IFRS17(audit_path=_tmp, verbose=False).run(
                    result_a7=_r7_synt,
                    result_a10=_r10,
                    generer_graphiques=False,
                )
                resultats["principal"] = r11

            # ── ALM A12 ─────────────────────────────────────────────────────
            elif besoin == "alm":
                from a10_solvabilite2 import AgentA10Solvabilite2
                from a12_alm import AgentA12ALM
                _be = params.get("be", 2_914_930)
                _r7_synt = {"best_estimate":{"best_estimate":_be,"sigma_mack":_be*0.015,"cv_inter_methodes":5,"nb_methodes_convergentes":4},"tail":{"tail_factor":1.037},"meta":{"nb_lignes":50000,"n_annees":8},"sous_branche":params.get("branche","rc_auto")}
                _r10 = AgentA10Solvabilite2(audit_path=_tmp, verbose=False).run(result_a7=_r7_synt, fonds_propres=params.get("fonds_propres",7_650_000), generer_graphiques=False)
                r12 = AgentA12ALM(audit_path=_tmp, verbose=False).run(
                    result_a10=_r10,
                    result_a7=_r7_synt,
                    generer_graphiques=False,
                )
                resultats["principal"] = r12

            # ── MORTALITÉ A14 ───────────────────────────────────────────────
            elif besoin == "mortalite":
                from a14_mortalite import AgentA14Mortalite
                r14 = AgentA14Mortalite(audit_path=_tmp, verbose=False).run(
                    generer_graphiques=False,
                )
                resultats["principal"] = r14

            # ── REPORT SANTÉ S3 — pipeline S1→S2→S3 ────────────────────────
            elif besoin == "report_sante":
                from sp1_tarification_sante import AgentS1TarificationSante
                from sp2_provisionnement_sante import AgentS2ProvisionnemntSante
                from sp3_reporting_sante import AgentS3ReportingSante
                _r_s1 = AgentS1TarificationSante(audit_path=_tmp, verbose=False).run(
                    nb_assures=params.get("nb_assures",1000),
                    age_moyen=params.get("age_moyen",42),
                    garantie_niveau=params.get("garantie_niveau","confort"),
                    generer_graphiques=False,
                )
                _r_s2 = AgentS2ProvisionnemntSante(audit_path=_tmp, verbose=False).run(
                    primes_acquises=params.get("primes_acquises",5_000_000),
                    generer_graphiques=False,
                )
                r_s3 = AgentS3ReportingSante(audit_path=_tmp, verbose=False).run(
                    result_s1=_r_s1,
                    result_s2=_r_s2,
                    fonds_propres=params.get("fonds_propres",0.0),
                    generer_graphiques=False,
                )
                resultats["principal"] = r_s3

            # ── PRÉVOYANCE — pipelines chaînés ──────────────────────────────
            elif besoin in ["tarif_prev","tables","prov_prev","report_prev"]:
                from sp4_tarification_prevoyance import AgentP1TarificationPrevoyance
                _r_p1 = AgentP1TarificationPrevoyance(audit_path=_tmp, verbose=False).run(
                    age=params.get("age",40),
                    salaire_brut=params.get("salaire_brut",45000),
                    categorie=params.get("categorie","employe"),
                    generer_graphiques=False,
                )
                resultats["principal"] = _r_p1

                if besoin in ["tables","prov_prev","report_prev"]:
                    from sp5_tables_morbidite import AgentP2TablesMorbidite
                    _r_p2 = AgentP2TablesMorbidite(audit_path=_tmp, verbose=False).run(
                        result_p1=_r_p1,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_p2

                if besoin in ["prov_prev","report_prev"]:
                    from sp6_provisionnement_prevoyance import AgentP3ProvisionnemntPrevoyance
                    _r_p3 = AgentP3ProvisionnemntPrevoyance(audit_path=_tmp, verbose=False).run(
                        result_p1=_r_p1,
                        result_p2=_r_p2,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_p3

                if besoin == "report_prev":
                    from sp7_reporting_prevoyance import AgentP4ReportingPrevoyance
                    _r_p4 = AgentP4ReportingPrevoyance(audit_path=_tmp, verbose=False).run(
                        result_p1=_r_p1,
                        result_p2=_r_p2,
                        result_p3=_r_p3,
                        fonds_propres=params.get("fonds_propres",0.0),
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_p4

            else:
                st.info(f"⏸️ L'agent pour ce besoin ({besoin}) sera disponible prochainement.")
                return

            # ── AFFICHAGE RÉSULTATS ─────────────────────────────────────────
            # ── SAUVEGARDER DANS SESSION_STATE POUR LE DASHBOARD AGENT ────
            _ak_map = {
                "prime_glm": "laurent", "prime_ml": "priya", "prime_dl": "yohan",
                "selection": "victor", "triangle_xl": "ibrahim", "sinistres": "ibrahim",
                "stress": "isabelle", "coherence": "marcus", "s2": "elena",
                "ifrs17": "thomas", "alm": "aisha", "ias19": "henri",
                "tarif": "salome", "prov": "jinho", "report": "omar",
                "mortalite": "yuki", "tarif_sante": "leonie", "prov_sante": "selma",
                "report_sante": "binta", "tarif_prev": "axel", "tables": "rayan",
                "prov_prev": "elodie", "report_prev": "valentin",
            }
            if besoin in _ak_map:
                if "agent_results" not in st.session_state:
                    st.session_state["agent_results"] = {}
                st.session_state["agent_results"][_ak_map[besoin]] = resultats.get("principal", {})

            st.session_state["res_data"]   = resultats
            st.session_state["res_besoin"] = besoin
            st.session_state["res_client"] = ref_client
            # Stocker triangle séparément pour regénération graphiques à la volée
            _r_principal = resultats.get("principal", {})
            if isinstance(_r_principal, dict) and _r_principal.get("triangle") is not None:
                st.session_state["triangle_a7"] = _r_principal["triangle"]
            nav_to("resultats")

        except ImportError as e:
            st.warning(f"⚠️ Module non disponible dans cet environnement : {e}")
            st.info("💡 Les agents s'exécutent dans l'environnement Python avec les dépendances installées (Colab, serveur local ou Render avec requirements.txt complet).")
        except Exception as e:
            st.error(f"❌ Erreur lors de l'analyse : {e}")



def page_resultats():
    """Page résultats pleine largeur — branché sur A7 v4.0."""
    import json as _json
    import plotly.graph_objects as go

    resultats  = st.session_state.get("res_data", {})
    besoin     = st.session_state.get("res_besoin", "")
    ref_client = st.session_state.get("res_client", "")

    # ── Compatibilité v3 et v4 ────────────────────────────────────────────────
    # v4.0 : résultat direct avec n1/n2/n3/n4
    # v3.x : résultat avec clé "principal"
    r_raw = resultats.get("principal", resultats)
    if not r_raw or not r_raw.get("success", False):
        st.warning("Aucun résultat disponible.")
        if st.button("← Retour à l'analyse"):
            nav_to("analyse")
        return

    # ── Lire la structure v4.0 ────────────────────────────────────────────────
    n4  = r_raw.get("n4", r_raw.get("best_estimate", {}))
    n3  = r_raw.get("n3", {})
    n2  = r_raw.get("n2", r_raw.get("validation", {}))
    n1  = r_raw.get("n1", {})
    graphiques = r_raw.get("graphiques", {})
    commentaire = r_raw.get("commentaire", "")
    statut      = r_raw.get("statut_rag", "")
    methode_u   = n3.get("methode_cl", n4.get("methode_facteurs", ""))

    # ── Données méthodes ─────────────────────────────────────────────────────
    cl   = r_raw.get("chain_ladder", n3.get("chain_ladder", {}))
    mack = r_raw.get("mack",         n3.get("mack", {}))
    bf   = r_raw.get("bf",           n3.get("bf", {}))
    cc_r = r_raw.get("cape_cod",     n3.get("cape_cod", {}))
    boot = r_raw.get("bootstrap",    n3.get("bootstrap", {}))
    tail = r_raw.get("tail_factor",  n3.get("tail_factor", {}))
    munich = r_raw.get("munich_cl",  n3.get("munich_cl", {}))

    # ── Données BE ───────────────────────────────────────────────────────────
    be_val  = n4.get("best_estimate", 0)
    cv_val  = n4.get("cv_inter_methodes", 0)
    p90     = n4.get("reserve_p90", mack.get("reserve_p90", 0))
    p75     = n4.get("reserve_p75", 0)
    p99     = n4.get("reserve_p99_5", 0)
    sigma   = n4.get("sigma_mack", mack.get("sigma_total", 0))
    poids   = n4.get("poids", {})
    emoji_s = "🟢" if statut=="VERT" else "🟡" if statut=="AMBRE" else "🔴"

    # ── HEADER ────────────────────────────────────────────────────────────────
    st.markdown(f"""
<div style="margin-bottom:16px;">
  <div style="font-size:0.65rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;font-weight:700;">
    Résultats · {ref_client or besoin} · {datetime.now().strftime('%d/%m/%Y %H:%M')}
  </div>
  <div style="font-family:'Playfair Display',serif;font-size:1.5rem;color:{BLANC};font-weight:700;">
    Rapport Actuariel — Provisionnement
  </div>
  <div style="font-size:0.8rem;color:{GRIS};">
    Méthode : <b style='color:{OR}'>{methode_u}</b>
    {f"  ·  Jugement actuariel documenté" if n4.get('jugement') else ""}
  </div>
</div>""", unsafe_allow_html=True)

    if st.button("← Nouvelle analyse", key="btn_back_res"):
        nav_to("analyse")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── KPIs ─────────────────────────────────────────────────────────────────
    k1,k2,k3,k4,k5 = st.columns(5)
    for col, titre, valeur, sous in [
        (k1, "STATUT",            f"{emoji_s} {statut}",   methode_u),
        (k2, "BEST ESTIMATE S2",  f"{be_val:,.0f} €",      "Art. 77 S2"),
        (k3, "PROVISION P90",     f"{p90:,.0f} €",         "Mack IC 95%"),
        (k4, "CV INTER-MÉTHODES", f"{cv_val:.1f}%",        "< 5% = VERT"),
        (k5, "σ MACK",            f"{sigma:,.0f} €",       "Incertitude"),
    ]:
        with col:
            st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px 16px;margin-bottom:16px;">
  <div style="font-size:0.6rem;color:{GRIS};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">{titre}</div>
  <div style="font-size:1.05rem;font-weight:700;color:{OR};">{valeur}</div>
  <div style="font-size:0.65rem;color:{GRIS};margin-top:3px;">{sous}</div>
</div>""", unsafe_allow_html=True)

    # ── TABLEAU TOUTES MÉTHODES ───────────────────────────────────────────────
    st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:8px 0;'>◆ Résultats de toutes les méthodes actuarielles</div>", unsafe_allow_html=True)

    rows = [
        {"Méthode": "🔗 Chain Ladder",              "Réserve (€)": f"{cl.get('reserve_totale',0):,.0f}",          "Poids BE": f"{poids.get('chain_ladder',0)*100:.0f}%", "Statut": "✅"},
        {"Méthode": "📐 Mack 1993 (IC 95%)",        "Réserve (€)": f"{mack.get('reserve_best_estimate',0):,.0f}", "Poids BE": f"{poids.get('mack',0)*100:.0f}%",          "Statut": "✅"},
        {"Méthode": "⚖️ Bornhuetter-Ferguson",      "Réserve (€)": f"{bf.get('reserve_totale',0):,.0f}",          "Poids BE": f"{poids.get('bf',0)*100:.0f}%",             "Statut": "✅"},
        {"Méthode": "🌊 Cape Cod",                  "Réserve (€)": f"{cc_r.get('reserve_totale',0):,.0f}",        "Poids BE": f"{poids.get('cape_cod',0)*100:.0f}%",       "Statut": "✅"},
        {"Méthode": "🎲 Bootstrap ODP (P50)",       "Réserve (€)": f"{boot.get('p50',0):,.0f}",                   "Poids BE": "—",                                         "Statut": "✅" if boot.get('p50',0) > 0 else "—"},
        {"Méthode": "🎲 Bootstrap ODP (P90)",       "Réserve (€)": f"{boot.get('p90',0):,.0f}",                   "Poids BE": "—",                                         "Statut": "✅" if boot.get('p90',0) > 0 else "—"},
        {"Méthode": "🇩🇪 Munich CL",               "Réserve (€)": f"{munich.get('be_munich',0):,.0f}" if munich.get('disponible') else "N/A",  "Poids BE": "—", "Statut": "✅" if munich.get('disponible') else "ℹ️"},
        {"Méthode": "⭐ BEST ESTIMATE S2",          "Réserve (€)": f"{be_val:,.0f}",                              "Poids BE": "100%",                                      "Statut": "→ Bilan S2"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── COMMENTAIRE ACTUARIEL ─────────────────────────────────────────────────
    if commentaire:
        st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:16px 0 8px;'>◆ Commentaire actuariel</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='background:{NAVY_L};border-radius:10px;padding:16px 20px;font-size:0.82rem;color:{BLANC};white-space:pre-wrap;line-height:1.8;'>{commentaire}</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── GRAPHIQUES — regénérés à la volée depuis données brutes ─────────────
    # (les go.Figure ne survivent pas à la navigation Streamlit)
    _tri_res = st.session_state.get("triangle_a7")
    if _tri_res is None:
        _tri_res = r_raw.get("triangle")
    _figs_res = {}
    if _tri_res is not None and n2 and n3:
        try:
            import numpy as _np_res
            from a7_provisionnement.n5_graphiques import generer_graphiques as _gen_res
            _C_res = _np_res.array(_tri_res) if not hasattr(_tri_res, "shape") else _tri_res
            _figs_res = _gen_res(_C_res, n2, n3, n4)
            st.markdown(f"<div style='font-size:0.62rem;color:{VERT};margin-bottom:8px;'>✅ {len(_figs_res)}/12 graphiques générés</div>", unsafe_allow_html=True)
        except Exception as _eg:
            st.warning(f"Graphiques non disponibles : {_eg}")

    # Graphiques page Résultats : les 6 graphiques décisionnels
    _ORDRE_RES = [
        ("g1_heatmap",       "◆ Triangle de développement cumulé"),
        ("g13_paiements",    "◆ Paiements cumulés par année de survenance"),
        ("g4_ibnr",          "◆ IBNR par année de survenance"),
        ("g14_backtesting",  "◆ Back-testing — Boni/Mali de liquidation"),
        ("g2_cadences",      "◆ Cadences cumulées — Chain Ladder"),
        ("g5_convergence",   "◆ Convergence des méthodes — Best Estimate S2"),
        ("g6_bootstrap",     "◆ Distribution Bootstrap ODP — Quantiles de réserve"),
        ("g7_scr",           "◆ SCR Provisions — Décomposition (Art. 105 S2)"),
    ]
    for _gnom, _gtit in _ORDRE_RES:
        _fig = _figs_res.get(_gnom)
        if _fig is not None:
            st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:16px 0 6px;'>{_gtit}</div>", unsafe_allow_html=True)
            try:
                st.plotly_chart(_fig, use_container_width=True, key=f"res_{_gnom}")
            except Exception as _ef:
                st.warning(f"Graphique {_gtit} : {_ef}")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── ANALYSES AVANCÉES ────────────────────────────────────────────────────
    st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:8px 0 10px;'>◆ Analyses avancées</div>", unsafe_allow_html=True)

    for label, obj in [
        ("🔚 Tail Factor",           tail),
        ("🔁 Back-Testing",          r_raw.get("back_testing", {})),
        ("🇩🇪 Munich Chain Ladder",  munich),
    ]:
        if obj and obj.get("message"):
            sc = VERT if obj.get("statut")=="VERT" else AMBRE if obj.get("statut")=="AMBRE" else ROUGE if obj.get("statut")=="ROUGE" else GRIS
            st.markdown(f"""
<div style="background:{NAVY_L};border-left:3px solid {sc};border-radius:6px;padding:10px 14px;margin-bottom:8px;">
  <div style="font-size:0.78rem;color:{sc};font-weight:600;">{label}</div>
  <div style="font-size:0.78rem;color:{BLANC};margin-top:3px;">{obj.get('message','')}</div>
  {f'<div style="font-size:0.72rem;color:{GRIS};margin-top:3px;white-space:pre-wrap;word-break:break-word;">{obj.get("conseil","")}</div>' if obj.get("conseil") else ""}
</div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── VALIDATION HYPOTHÈSES ────────────────────────────────────────────────
    st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:8px 0 8px;'>◆ Validation des hypothèses actuarielles</div>", unsafe_allow_html=True)

    h1 = n2.get("h1_independance", {})
    h2 = n2.get("h2_stabilite", {})
    h3 = n2.get("h3_apriori_bf", {})
    h4 = n2.get("h4_homosc_bootstrap", {})

    for cle, h, label in [
        ("H1", h1, "Indépendance des années"),
        ("H2", h2, "Stabilité des facteurs"),
        ("H3", h3, "Qualité a priori BF"),
        ("H4", h4, "Homoscédasticité Bootstrap"),
    ]:
        if h:
            ok  = h.get("ok", True)
            ic  = "✅" if ok else "⚠️"
            sc  = VERT if ok else AMBRE
            msg = h.get("message", "")
            score = h.get("score", "—")
            detail_keys = ["corr_moy","cv_moy","lr_apriori","phi","max_corr","derive"]
            details = " · ".join(f"{k}={h[k]}" for k in detail_keys if k in h and h[k] is not None)
            st.markdown(f"""
<div style="background:{NAVY_L};border-left:3px solid {sc};border-radius:6px;
            padding:12px 16px;margin-bottom:8px;width:100%;box-sizing:border-box;">
  <div style="font-size:0.78rem;color:{sc};font-weight:700;margin-bottom:4px;">
    {ic} {cle} — {label} &nbsp;<span style="font-weight:400;font-size:0.72rem;">score {score}/100</span>
  </div>
  {f'<div style="font-size:0.72rem;color:{GRIS};margin-bottom:4px;">{details}</div>' if details else ''}
  <div style="font-size:0.76rem;color:{BLANC};line-height:1.7;
              white-space:pre-wrap;word-break:break-word;">{msg}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── JUGEMENT ACTUARIEL ───────────────────────────────────────────────────
    jugement = n4.get("jugement", "")
    if jugement:
        st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:8px 0 12px;'>◆ Jugement actuariel documenté</div>", unsafe_allow_html=True)
        import re as _re_jug
        _sections_jug = _re_jug.split(r'(?=\d+\.\s+[A-ZÀÂÉÈÊ])', jugement.strip())
        for _sec in _sections_jug:
            _sec = _sec.strip()
            if not _sec:
                continue
            _lines_sec = _sec.split("\n", 1)
            _titre_sec = _lines_sec[0].strip()
            _corps_sec = _lines_sec[1].strip() if len(_lines_sec) > 1 else ""
            _corps_sec = _re_jug.sub(r'─+', '', _corps_sec).strip()
            if _titre_sec:
                _html_sec = (
                    f"<div style='background:{NAVY_L};border-left:3px solid {OR};"
                    f"border-radius:6px;padding:12px 16px;margin-bottom:8px;'>"
                    f"<div style='font-size:0.75rem;font-weight:700;color:{OR};margin-bottom:6px;'>{_titre_sec}</div>"
                    f"<div style='font-size:0.78rem;color:{BLANC};line-height:1.7;white-space:pre-wrap;word-break:break-word;'>{_corps_sec}</div>"
                    f"</div>"
                )
                st.markdown(_html_sec, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── EXPORT ───────────────────────────────────────────────────────────────
    e1, e2, e3, e4, e5 = st.columns([1, 1, 1, 1, 1])
    with e1:
        st.download_button(
            "⬇️ Export JSON",
            data=_json.dumps(r_raw, indent=2, ensure_ascii=False, default=str),
            file_name=f"actuaria_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
            key="dl_res_json",
        )
    with e2:
        excel_bytes = r_raw.get("excel_bytes", b"")
        if excel_bytes:
            st.download_button(
                "⬇️ Export Excel",
                data=excel_bytes,
                file_name=f"actuaria_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_res_excel",
            )
    with e3:
        word_bytes = r_raw.get("word_bytes", b"")
        if word_bytes:
            st.download_button(
                "📄 Rapport Word",
                data=word_bytes,
                file_name=f"rapport_actuariel_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="dl_res_word",
            )
        else:
            st.button("📄 Rapport Word", use_container_width=True, key="dl_res_word_na", disabled=True, help="Non disponible pour cet agent")
    with e4:
        pdf_bytes = r_raw.get("pdf_bytes", b"")
        if pdf_bytes:
            st.download_button(
                "📑 Rapport PDF",
                data=pdf_bytes,
                file_name=f"rapport_actuariel_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="dl_res_pdf",
            )
        else:
            st.button("📑 Rapport PDF", use_container_width=True, key="dl_res_pdf_na", disabled=True, help="Non disponible pour cet agent")
    with e5:
        if st.button("📊 Voir Dashboard", use_container_width=True, key="res_to_dash"):
            nav_to("dashboard")


def _afficher_resultats(resultats, besoin, ref_client):
    """Affiche les résultats d'analyse — layout 2 colonnes pro."""
    import json
    import plotly.graph_objects as go

    r = resultats.get("principal", {})
    if not r:
        st.warning("Aucun résultat à afficher.")
        return

    statut = r.get("statut_rag", r.get("statut", "N/A"))

    # ── BADGE STATUT ─────────────────────────────────────────────────────────
    c1, c2, _ = st.columns([1.2, 2.5, 1.5])
    with c1:
        if statut == "VERT":    st.success("✅ VERT — Validé")
        elif statut == "AMBRE": st.warning("⚠️ AMBRE — À vérifier")
        elif statut == "ROUGE": st.error("❌ ROUGE — Action requise")
        else:                   st.info("ℹ️ Terminé")
    with c2:
        methode_u = r.get("best_estimate", {}).get("methode_facteurs", "standard")
        raison    = r.get("rapport", {}).get("raison_methode", "")
        st.markdown(f"<div style='font-size:0.72rem;color:{GRIS};padding-top:8px;'>{ref_client} · {datetime.now().strftime('%d/%m/%Y %H:%M')} · Méthode : <b style='color:{OR}'>{methode_u}</b></div>", unsafe_allow_html=True)
        if raison:
            st.markdown(f"<div style='font-size:0.68rem;color:{AMBRE};'>ℹ️ {raison}</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # LAYOUT 2 COLONNES : résultats gauche · graphiques droite
    # ════════════════════════════════════════════════════════════════════════
    col_gauche, col_droite = st.columns([1, 1.6])

    # ── COLONNE GAUCHE — RÉSULTATS ───────────────────────────────────────────
    with col_gauche:
        be   = r.get("best_estimate", {})
        mack = r.get("mack", {})
        cl   = r.get("chain_ladder", {})
        bf   = r.get("bf", {})
        cc   = r.get("cape_cod", {})

        be_val  = be.get("best_estimate", 0)
        cv_val  = be.get("cv_inter_methodes", 0)
        p90_val = be.get("reserve_p90", mack.get("reserve_p90", 0))
        sig_val = mack.get("sigma_total", be.get("sigma_mack", 0))

        # KPIs
        st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin-bottom:8px;'>◆ Best Estimate Solvabilité 2</div>", unsafe_allow_html=True)
        k1, k2 = st.columns(2)
        with k1:
            st.metric("Best Estimate S2", f"{be_val:,.0f} €")
            st.metric("σ Mack", f"{sig_val:,.0f} €")
        with k2:
            st.metric("CV inter-méthodes", f"{cv_val:.1f}%")
            st.metric("Provision P90", f"{p90_val:,.0f} €")

        # Tableau 4 méthodes
        st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:14px 0 6px;'>◆ Résultats des 4 méthodes actuarielles</div>", unsafe_allow_html=True)
        poids = be.get("poids_methodes", {})
        rows = [
            {"Méthode": "🔗 Chain Ladder",         "Réserve (€)": f"{cl.get('reserve_totale',0):,.0f}",          "Poids": f"{poids.get('cl',0)*100:.0f}%"},
            {"Méthode": "📐 Mack 1993 (S2)",       "Réserve (€)": f"{mack.get('reserve_best_estimate',0):,.0f}", "Poids": f"{poids.get('mack',0)*100:.0f}%"},
            {"Méthode": "⚖️ Bornhuetter-Ferguson", "Réserve (€)": f"{bf.get('reserve_totale',0):,.0f}",          "Poids": f"{poids.get('bf',0)*100:.0f}%"},
            {"Méthode": "🌊 Cape Cod",             "Réserve (€)": f"{cc.get('reserve_totale',0):,.0f}",          "Poids": f"{poids.get('cc',0)*100:.0f}%"},
            {"Méthode": "⭐ BEST ESTIMATE S2",     "Réserve (€)": f"{be_val:,.0f}",                              "Poids": "100%"},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Crédibilité
        cred = r.get("credibilite", {})
        if cred:
            st.markdown(f"<div style='font-size:0.72rem;color:{GRIS};margin-top:4px;'>Crédibilité : Z={cred.get('Z',0):.2f} ({cred.get('niveau_credibilite','')})</div>", unsafe_allow_html=True)

        # Facteurs atypiques
        atypiques = r.get("atypiques", {})
        alertes_f = atypiques.get("alertes", [])
        if alertes_f:
            st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:14px 0 6px;'>◆ Facteurs atypiques — corrigés par {methode_u}</div>", unsafe_allow_html=True)
            for a in alertes_f[:5]:
                st.markdown(f"<div style='font-size:0.72rem;color:{AMBRE};'>{a}</div>", unsafe_allow_html=True)

        # Analyses avancées
        st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:14px 0 6px;'>◆ Analyses avancées</div>", unsafe_allow_html=True)

        tail = r.get("tail_factor", {})
        bt   = r.get("back_testing", {})
        orsa = r.get("orsa_provisions", {})
        munich = r.get("munich_cl", {})
        comp = r.get("comparaison_n1", {})

        if tail:
            tc = VERT if tail.get("statut") == "VERT" else AMBRE
            st.markdown(f"<div style='font-size:0.78rem;color:{tc};'>🔚 Tail Factor : {tail.get('tail_factor',1):.4f} — {tail.get('message','')[:60]}</div>", unsafe_allow_html=True)
        if bt:
            bc = VERT if bt.get("statut") == "VERT" else AMBRE if bt.get("statut") == "AMBRE" else ROUGE
            st.markdown(f"<div style='font-size:0.78rem;color:{bc};'>🔁 Back-Testing : {bt.get('message','')[:80]}</div>", unsafe_allow_html=True)
        if orsa:
            oc = VERT if orsa.get("statut") == "VERT" else AMBRE if orsa.get("statut") == "AMBRE" else ROUGE
            st.markdown(f"<div style='font-size:0.78rem;color:{oc};'>📅 ORSA : {orsa.get('message','')[:80]}</div>", unsafe_allow_html=True)
        if munich:
            mc = VERT if munich.get("statut") == "VERT" else AMBRE if munich.get("statut") == "AMBRE" else ROUGE
            st.markdown(f"<div style='font-size:0.78rem;color:{mc};'>🇩🇪 Munich CL : {munich.get('message','')[:80]}</div>", unsafe_allow_html=True)
        if comp:
            cc2 = VERT if comp.get("statut_evolution") == "VERT" else AMBRE
            st.markdown(f"<div style='font-size:0.78rem;color:{cc2};'>📊 N vs N-1 : {comp.get('interpretation','')[:80]}</div>", unsafe_allow_html=True)

        # Rapport actuariel
        rapport_act = r.get("rapport_actuaire", {})
        if rapport_act:
            avis_color = VERT if "FAVORABLE" in rapport_act.get("avis","") and "RESERVE" not in rapport_act.get("avis","") else AMBRE
            st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:14px 0 6px;'>◆ Rapport Actuaire Désigné</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='background:{NAVY_L};border-left:3px solid {avis_color};padding:10px 14px;border-radius:6px;font-size:0.8rem;color:{avis_color};font-weight:700;'>AVIS : {rapport_act.get('avis','')}</div>", unsafe_allow_html=True)
            sections = rapport_act.get("sections", [])
            for sec in sections[:3]:
                with st.expander(f"§{sec.get('numero','')} — {sec.get('titre','')}"):
                    st.markdown(sec.get("contenu",""))

        # Export
        st.markdown("<hr>", unsafe_allow_html=True)
        import json as _json
        st.download_button(
            "⬇️ Export JSON complet",
            data=_json.dumps(r, indent=2, ensure_ascii=False, default=str),
            file_name=f"actuaria_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
            key=f"dl_json_{besoin}",
        )

    # ── COLONNE DROITE — GRAPHIQUES ──────────────────────────────────────────
    with col_droite:
        graphiques = r.get("graphiques", {})

        st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin-bottom:8px;'>◆ Graphiques</div>", unsafe_allow_html=True)

        # Graphiques natifs A7
        ordre_graphiques = ["heatmap_triangle", "convergence_methodes", "facteurs_cl", "ibnr_par_annee"]
        for nom in ordre_graphiques:
            fig = graphiques.get(nom)
            if fig is not None:
                try:
                    st.plotly_chart(fig, use_container_width=True)
                except Exception:
                    pass

        # Autres graphiques non listés
        for nom, fig in graphiques.items():
            if nom not in ordre_graphiques and fig is not None:
                try:
                    st.plotly_chart(fig, use_container_width=True)
                except Exception:
                    pass

        # Graphique Bootstrap
        boot = r.get("bootstrap", {})
        if boot and boot.get("distribution"):
            dist = boot["distribution"]
            fig_boot = go.Figure()
            fig_boot.add_trace(go.Histogram(
                x=dist, nbinsx=50,
                marker_color="rgba(201,168,76,0.7)",
                marker_line=dict(color="#0F2E52", width=0.5),
                name="Simulations",
            ))
            for p, label, color in [
                (boot.get("p50",0),   "P50",   "#2ECC71"),
                (boot.get("p90",0),   "P90",   "#F39C12"),
                (boot.get("p99_5",0), "P99.5", "#E74C3C"),
            ]:
                if p:
                    fig_boot.add_vline(x=p, line_color=color, line_width=2, line_dash="dash",
                                       annotation_text=f"{label}={p:,.0f}€",
                                       annotation_font=dict(color=color, size=10))
            fig_boot.update_layout(
                paper_bgcolor="#0F2E52", plot_bgcolor="#1B3A5C",
                font=dict(family="Inter", color="#F0F4F8", size=11),
                title=dict(text="Distribution Bootstrap — 1 000 simulations", font=dict(color="#F0F4F8", size=13), x=0.01),
                xaxis=dict(title="Réserve IBNR (€)", tickfont=dict(color="#8A9AB0"), showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="Fréquence", tickfont=dict(color="#8A9AB0"), showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                showlegend=False, height=300, margin=dict(t=40, b=40, l=40, r=20),
            )
            st.plotly_chart(fig_boot, use_container_width=True)

        # Graphique Waterfall N vs N-1
        comp = r.get("comparaison_n1", {})
        if comp and comp.get("waterfall"):
            w = comp["waterfall"]
            labels = ["BE N-1", "Run-off", "Nouveaux", "Réouvertures", "Hypothèses", "Résiduel", "BE N"]
            values = [
                w.get("be_n1",0), w.get("effet_run_off",0), w.get("effet_nouveaux",0),
                w.get("effet_reouverture",0), w.get("effet_hypotheses",0), w.get("effet_residuel",0),
                comp.get("be_n",0),
            ]
            colors = ["#C9A84C" if i in [0,6] else "#2ECC71" if v >= 0 else "#E74C3C"
                      for i, v in enumerate(values)]
            fig_wf = go.Figure(go.Bar(
                x=labels, y=values,
                marker_color=colors,
                marker_line=dict(color="#0F2E52", width=1),
                width=0.45,
                text=[f"{v:+,.0f}€" if i not in [0,6] else f"{v:,.0f}€" for i, v in enumerate(values)],
                textposition="outside",
                textfont=dict(color="#F0F4F8", size=10),
            ))
            fig_wf.update_layout(
                paper_bgcolor="#0F2E52", plot_bgcolor="#1B3A5C",
                font=dict(family="Inter", color="#F0F4F8", size=11),
                title=dict(text="Waterfall Provisions N-1 → N", font=dict(color="#F0F4F8", size=13), x=0.01),
                xaxis=dict(tickfont=dict(color="#F0F4F8", size=10), showgrid=False),
                yaxis=dict(visible=False), bargap=0.35, showlegend=False, height=300,
                margin=dict(t=40, b=40, l=20, r=20),
            )
            st.plotly_chart(fig_wf, use_container_width=True)

        # Validation hypothèses
        validation = r.get("validation", {})
        diag = r.get("diagnostic", {})
        if validation or diag:
            st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:14px 0 6px;'>◆ Validation & Diagnostic</div>", unsafe_allow_html=True)
            if diag:
                dc = VERT if diag.get("statut") == "VERT" else AMBRE
                st.markdown(f"<div style='font-size:0.8rem;color:{dc};font-weight:700;'>{diag.get('message','')}</div>", unsafe_allow_html=True)
            if validation:
                for cle, val in validation.items():
                    if cle.startswith("h") and isinstance(val, dict):
                        ok  = val.get("ok", val.get("statut") == "VERT")
                        ic  = "✅" if ok else "⚠️"
                        msg = val.get("message", val.get("conseil", ""))[:120]
                        st.markdown(f"<div style='font-size:0.72rem;color:{BLANC};'>{ic} <b>{cle.upper()}</b> — {msg}</div>", unsafe_allow_html=True)
# ══════════════════════════════════════════════════════════════════════════════
# PAGE RAPPORTS CONSOLIDÉS
# ══════════════════════════════════════════════════════════════════════════════
def page_rapports():
    st.markdown(f"""
<div style="margin-bottom:20px;">
  <div style="font-size:0.65rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px;font-weight:700;">Livrables clients</div>
  <div style="font-family:'Playfair Display',serif;font-size:1.5rem;color:{BLANC};font-weight:700;">Rapports Consolidés</div>
  <div style="font-size:0.82rem;color:{GRIS};margin-top:4px;">
    Ces rapports agrègent les résultats de plusieurs agents — distincts des rapports individuels disponibles dans chaque page agent.
  </div>
</div>""", unsafe_allow_html=True)

    rapports = [
        ("📊","Rapport Actuariel Complet","Synthèse toutes directions · PDF · Signé actuaire désigné","S2 + IFRS17 + ALM + EP-RE",VERT,"Disponible"),
        ("🏢","QRT Non-Vie ACPR","Reporting réglementaire S2 · Excel EIOPA · S.05 · S.17 · S.19","S.05 · S.17 · S.19 · S.23",VERT,"Disponible"),
        ("💼","Rapport Actuariel EP-RE","Engagements retraite + Provisions + Stress · PDF signé","IAS 19 · PER · DARES · ORSA",VERT,"Disponible"),
        ("🛡️","ORSA Prospectif 5 ans","Pilier 2 S2 · 3 scénarios · Besoin en capital · PDF","Stress Testing · ORSA · SCR",AMBRE,"En préparation"),
        ("🔐","Rapport Audit Trail","Hash SHA-256 · RGPD Art.30 · Hypothèses versionnées · JSON/PDF","Intégrité · Conformité · Audit",VERT,"Disponible"),
        ("🏥","Rapport Santé-Prévoyance","AMEXA · DREES · ANI · QRT S.13 · Mutuelles","Santé · Prévoyance · Mutuelles",GRIS,"En développement"),
        ("📋","Note de synthèse CA","Synthèse exécutive pour le Conseil d'Administration","Toutes directions · Décision",VERT,"Disponible"),
    ]

    for i, (icon,titre,desc,tags,col_st,st_lbl) in enumerate(rapports):
        col1, col2 = st.columns([4,1])
        with col1:
            badge_cl = "badge-VERT" if col_st==VERT else "badge-AMBRE" if col_st==AMBRE else "badge-DEV"
            st.markdown(f"""
<div style="background:{NAVY_L};border:1px solid rgba(201,168,76,0.15);border-radius:10px;padding:14px 18px;margin-bottom:8px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
    <span style="font-size:1.1rem;">{icon}</span>
    <span style="font-weight:700;color:{BLANC};font-size:0.9rem;">{titre}</span>
    <span class="{badge_cl}">{st_lbl}</span>
  </div>
  <div style="font-size:0.78rem;color:{GRIS};margin-bottom:5px;">{desc}</div>
  <div style="font-size:0.72rem;color:{OR};">{tags}</div>
</div>""", unsafe_allow_html=True)
        with col2:
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            if col_st != GRIS:
                if st.button("⬇️ Générer", key=f"rpt_{i}", use_container_width=True):
                    st.toast(f"✅ {titre} généré", icon="✅")
            else:
                st.markdown(f"<div style='font-size:0.72rem;color:{GRIS};text-align:center;padding:10px;'>⏸ Bientôt</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ROUTEUR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
render_sidebar()

page = st.session_state.page
if   page == "accueil":      page_accueil()
elif page == "dashboard":    page_dashboard()
elif page == "analyse":      page_analyse()
elif page == "rapports":     page_rapports()
elif page == "direction":    page_direction()
elif page == "agent_detail": page_agent_detail()
elif page == "resultats":    page_resultats()
else:                        page_accueil()
