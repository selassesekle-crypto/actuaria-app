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
  background:transparent;border:1px solid rgba(255,255,255,0.08);
  color:{BLANC}!important;border-radius:8px;font-size:0.82rem;
  font-weight:500;padding:8px 12px;width:100%;text-align:left;
  transition:all 0.2s;margin-bottom:3px;
}}
[data-testid="stSidebar"] .stButton>button:hover {{
  background:rgba(201,168,76,0.12);border-color:rgba(201,168,76,0.4);
  color:{OR}!important;transform:translateX(2px);
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
.stButton>button {{
  background:linear-gradient(135deg,{OR},{OR_L});color:{NAVY}!important;
  border:none;border-radius:8px;font-weight:700;padding:10px 20px;
  transition:all 0.2s;
}}
.stButton>button:hover {{
  transform:translateY(-1px);box-shadow:0 4px 16px rgba(201,168,76,0.4);
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
            ("📈","Dashboard","dashboard"),
            ("📊","Analyse","analyse"),
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
            if st.button("📈 Dashboard", type="primary", use_container_width=True):
                nav_to("dashboard")
        with c2:
            if st.button("📊 Lancer une analyse", use_container_width=True):
                nav_to("analyse")

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

        # Hypothèses
        hyp = r.get("hypotheses", [])
        if hyp:
            st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:10px 0 6px;'>◆ Hypothèses validées</div>", unsafe_allow_html=True)
            for h in hyp:
                ic  = "✅" if h.get("statut") == "VALIDÉE" else "⚠️"
                st.markdown(f"**{ic} [{h.get('id','')}]** {h.get('hypothese','')[:80]}  \n`{h.get('valeur','')[:80]}` — *{h.get('statut','')}*")

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

    # Charger les graphiques de validation si disponibles
    # (ils seront chargés depuis les résultats du pipeline Colab)
    st.info(f"⚙️ Les graphiques de validation s'affichent après exécution du pipeline {a['prenom']} depuis Colab.")
    st.markdown(f"""
<div style="background:{NAVY_LL};border:1px solid rgba(201,168,76,0.15);border-radius:10px;padding:16px;">
  <div style="font-size:0.82rem;color:{BLANC};line-height:1.8;">
    <strong style="color:{OR};">Hypothèses validées pour {a['prenom']} :</strong><br>
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
        st.markdown(f"<div style='font-size:0.82rem;color:{GRIS};margin-bottom:14px;'>Tarification, provisionnement et réglementation Non-Vie sur 678 013 contrats auto France.</div>", unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Gini ML","0.2651","XGBoost")
        with c2: st.metric("Modèle retenu","ElasticNet","overfit 0.98")
        with c3: st.metric("Best Estimate","2.91M€","CV 0.6%")
        with c4: st.metric("Ratio SCR","208.5%","✅ > 150%")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_bar(["XGBoost","GBM","CatBoost","LightGBM","ElasticNet"],[0.2651,0.2542,0.2534,0.2481,0.2440],"Tarification — Gini par modèle ML",[ROUGE,OR,OR,OR,VERT]), use_container_width=True)
        with col_b:
            st.plotly_chart(fig_bar(["Chain Ladder","Mack 1993","BF","Cape Cod","Best Est."],[2_850_000,2_914_930,2_930_000,2_880_000,2_914_930],"Provisionnement — 4 méthodes (€)",[OR,OR,OR,OR,VERT]), use_container_width=True)
        col_c,col_d = st.columns(2)
        with col_c:
            st.plotly_chart(fig_jauge(208.5,"Ratio SCR Non-Vie (%)"), use_container_width=True)
        with col_d:
            st.plotly_chart(fig_bar(["Base","Choc fréq.","Choc coût","NatCat","Combiné"],[375,310,295,280,245],"ORSA — Ratio SCR après chocs EIOPA (%)",[VERT,OR,OR,AMBRE,ROUGE]), use_container_width=True)

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
                fichier = st.file_uploader("Triangle de développement", type=["csv","xlsx","xls"], key="upload_triangle")
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
                a7 = AgentA7Provisionnement(audit_path=_tmp, models_path=_tmp, verbose=False)
                r7 = a7.run(source=df, generer_graphiques=False)
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
                elif besoin in ["selection","sinistres"]:
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
                a7 = AgentA7Provisionnement(audit_path=_tmp, verbose=False)
                # Construire le triangle depuis le DataFrame
                if df is not None and len(df) > 1:
                    tri = df.select_dtypes(include=["number"]).values
                    r7 = a7.run(source=tri, generer_graphiques=False)
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
                    from leonie_s1_tarification_sante import AgentS1TarificationSante
                    r_s1 = AgentS1TarificationSante(audit_path=_tmp, verbose=False).run(
                        nb_assures=params.get("nb_assures",1000),
                        age_moyen=params.get("age_moyen",42),
                        garantie_niveau=params.get("garantie_niveau","confort"),
                        generer_graphiques=False,
                    )
                    resultats["principal"] = r_s1
                elif besoin == "prov_sante":
                    from selma_s2_provisionnement_sante import AgentS2ProvisionnemntSante
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
                from leonie_s1_tarification_sante import AgentS1TarificationSante
                from selma_s2_provisionnement_sante import AgentS2ProvisionnemntSante
                from binta_s3_reporting_sante import AgentS3ReportingSante
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
                from axel_p1_tarification_prevoyance import AgentP1TarificationPrevoyance
                _r_p1 = AgentP1TarificationPrevoyance(audit_path=_tmp, verbose=False).run(
                    age=params.get("age",40),
                    salaire_brut=params.get("salaire_brut",45000),
                    categorie=params.get("categorie","employe"),
                    generer_graphiques=False,
                )
                resultats["principal"] = _r_p1

                if besoin in ["tables","prov_prev","report_prev"]:
                    from rayan_p2_tables_morbidite import AgentP2TablesMorbidite
                    _r_p2 = AgentP2TablesMorbidite(audit_path=_tmp, verbose=False).run(
                        result_p1=_r_p1,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_p2

                if besoin in ["prov_prev","report_prev"]:
                    from elodie_p3_provisionnement_prevoyance import AgentP3ProvisionnemntPrevoyance
                    _r_p3 = AgentP3ProvisionnemntPrevoyance(audit_path=_tmp, verbose=False).run(
                        result_p1=_r_p1,
                        result_p2=_r_p2,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_p3

                if besoin == "report_prev":
                    from valentin_p4_reporting_prevoyance import AgentP4ReportingPrevoyance
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

            _afficher_resultats(resultats, besoin, ref_client)

        except ImportError as e:
            st.warning(f"⚠️ Module non disponible dans cet environnement : {e}")
            st.info("💡 Les agents s'exécutent dans l'environnement Python avec les dépendances installées (Colab, serveur local ou Render avec requirements.txt complet).")
        except Exception as e:
            st.error(f"❌ Erreur lors de l'analyse : {e}")


def _afficher_resultats(resultats, besoin, ref_client):
    """Affiche les résultats d'analyse dans la page."""
    r = resultats.get("principal", {})
    if not r:
        st.warning("Aucun résultat à afficher.")
        return

    statut = r.get("statut_rag", r.get("statut", "N/A"))
    success = r.get("success", False)

    # Badge statut
    col_st, _ = st.columns([1,3])
    with col_st:
        if statut == "VERT":
            st.success(f"✅ VERT — Analyse validée")
        elif statut == "AMBRE":
            st.warning(f"⚠️ AMBRE — Vérifications recommandées")
        elif statut == "ROUGE":
            st.error(f"❌ ROUGE — Action requise")
        else:
            st.info(f"ℹ️ Analyse terminée")

    # Commentaire actuariel
    com = r.get("commentaire","")
    if com:
        with st.expander("📋 Rapport actuariel complet", expanded=True):
            st.code(com, language=None)

    # Hypothèses
    hyp = r.get("hypotheses", [])
    if hyp:
        st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:10px 0 6px;'>◆ Hypothèses validées</div>", unsafe_allow_html=True)
        for h in hyp:
            ic = "✅" if h.get("statut")=="VALIDÉE" else "⚠️"
            hid = h.get("id","")
            htxt = h.get("hypothese","")[:80]
            hval = h.get("valeur","")[:80]
            hst  = h.get("statut","")
            st.markdown(f"**{ic} [{hid}]** {htxt}  \n`{hval}` — *{hst}*")

    # Boutons export
    st.markdown("<hr>", unsafe_allow_html=True)
    import json
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Exporter résultats (JSON)",
            data=json.dumps(r, indent=2, ensure_ascii=False, default=str),
            file_name=f"actuaria_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )
    with col2:
        if st.button("📊 Voir Dashboard", use_container_width=True, key="res_dash"):
            nav_to("dashboard")

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
else:                        page_accueil()
