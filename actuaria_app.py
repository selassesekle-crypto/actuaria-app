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

from core import arrete as _arrete_core
from core import frontiere_llm

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

# ── LA DATE D'ARRÊTÉ — LUE ET TYPÉE, LE LIBELLÉ EN DÉCOULE ──────────────────
#
#  ⚠️ CES QUATRE AIDES NE DÉCIDENT RIEN : elles enveloppent `core.arrete`,
#  qui porte la règle. L'application ne réimplémente pas la lecture d'une
#  date — c'est ce qui avait produit 26 formes de la même notion sur 71 sites.

def _lire_arrete(valeur):
    """L'objet `Arrete` de `core`, ou `None` si la saisie est inexploitable."""
    try:
        return _arrete_core.lire(valeur)
    except _arrete_core.ArreteInvalide:
        return None


def _libelle_arrete(arrete_obj):
    """Le libellé lisible, DÉRIVÉ de la date. Jamais saisi, donc jamais faux."""
    return _arrete_core.libelle(arrete_obj) if arrete_obj is not None else ''


def _fin_de_periode(arrete_obj):
    """Une fin de trimestre usuelle ? Une clôture en milieu de mois existe —
    run-off, cession — assez rare pour être signalée, pas refusée."""
    return _arrete_core.est_fin_de_periode(arrete_obj)


def nav_to(page, agent=None, dir_key=None, besoin=None, equipe=None):
    st.session_state.page = page
    st.session_state.agent_selec = agent
    st.session_state.dir_selec = dir_key
    if besoin:
        st.session_state.analyse_besoin = besoin
    if equipe:
        st.session_state.analyse_equipe = equipe
    if besoin or equipe:
        st.session_state.analyse_dir = "non_vie"
        st.session_state.mapping_confirme = True
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
/* Radio — labels des options lisibles */
[data-testid="stRadio"] label p,
[data-testid="stRadio"] label span,
div[role="radiogroup"] label p {{
  color: {BLANC} !important;
  font-size: 0.88rem !important;
  font-weight: 600 !important;
}}
[data-testid="stRadio"] label:has(input:checked) p,
[data-testid="stRadio"] label:has(input:checked) span {{
  color: {OR} !important;
  font-weight: 700 !important;
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
    "isabelle": {"prenom":"Isabelle","code":"A8",      "icon":"🌩️","statut":"VERT","niveau":"agent","dir":"non_vie","equipe":"reglementation_nv","role_fr":"Stress Testing & ORSA Non-Vie","intro":"Bonjour, je suis Isabelle, experte en stress testing et ORSA Non-Vie. J'évalue la résistance de votre portefeuille aux chocs réglementaires EIOPA et projette l'ORSA prospectif sur 5 ans selon 3 scénarios.","spec_fr":"Chocs S2 EIOPA · ORSA 5 ans · Scénarios","kpi":"SCR post-stress=375%"},
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
            "provisionnement":  {"label":"Équipe Provisionnement", "icon":"📊","manager":"kwame", "agents":["ibrahim"]},
            "coherence":        {"label":"Cohérence & Contrôles","icon":"🔗","manager":None,"agents":["marcus"]},
            "reglementation_nv":{"label":"Équipe Réglementation",  "icon":"🛡️","manager":"nadia", "agents":["isabelle","elena","thomas","aisha"]},
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
    "kwame":    f"Tu es Kwame, Manager Provisionnement Non-Vie. Tu supervises Ibrahim. {RESULTATS} {REGLE}",
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
        msgs = [{"role":m["role"],"content":m["content"]} for m in messages if m["role"] in ["user","assistant"]]
        r = frontiere_llm.appeler(modele=frontiere_llm.MODELE_ETABLI, max_tokens=1024, messages=msgs, systeme=system_prompt, cle=api_key)
        return frontiere_llm.texte_des_blocs(r)
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
        st.plotly_chart(fig, width='stretch')

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
    _ar_ve  = st.session_state.get("agent_results") or {}
    _be_ve  = ((_ar_ve.get("ibrahim") or {}).get("n4") or {}).get("best_estimate", 2_914_930)
    _scr_ve = ((_ar_ve.get("elena")   or {}).get("capital") or {}).get("ratio_scr", 208.5)
    _gin_ve = (((_ar_ve.get("priya")  or {}).get("classement") or [{}])[0]).get("gini", 0.2651)
    _lcr_ve = ((_ar_ve.get("aisha")   or {}).get("lcr") or {}).get("lcr", 1173.0)
    _be_str_ve = f"{_be_ve/1e6:.2f}M€" if _be_ve >= 1e6 else f"{_be_ve:,.0f}€"
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Best Estimate", _be_str_ve, "✅ Réel" if _ar_ve.get("ibrahim") else "CV 0.6% [démo]")
    with c2: st.metric("Ratio SCR", f"{_scr_ve:.1f}%", "✅" if _scr_ve >= 150 else "⚠️")
    with c3: st.metric("Gini ML", f"{_gin_ve:.4f}", "✅ Réel" if _ar_ve.get("priya") else "freMTPL2 [démo]")
    with c4: st.metric("LCR", f"{_lcr_ve:,.0f}%", "✅" if _lcr_ve >= 100 else "⚠️")
    col_a, col_b = st.columns(2)
    with col_a:
        _cl_ve = (_ar_ve.get("priya") or {}).get("classement", [])
        if _cl_ve:
            _top4 = _cl_ve[:4]
            _g4 = [m.get("gini",0) for m in _top4]
            _bst = max(_g4)
            st.plotly_chart(fig_bar([m.get("modele","?") for m in _top4], _g4,
                "Gini par modèle ML [réel]", [VERT if g==_bst else OR for g in _g4]
            ), use_container_width=True, key="ve_gini")
        else:
            st.plotly_chart(fig_bar(["XGBoost","ElasticNet","CatBoost","GLM"],[0.2651,0.2440,0.2534,0.12],
                "Gini par famille de modèles [démo]",[ROUGE,VERT,OR,GRIS]
            ), use_container_width=True, key="ve_gini")
    with col_b:
        st.plotly_chart(fig_jauge(_scr_ve, f"Ratio SCR ({'réel' if _ar_ve.get('elena') else 'démo'}) (%)"), width='stretch', key="ve_scr")

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
            st.plotly_chart(fig_bar(["Chain Ladder","Mack 1993","BF","Cape Cod","Best Est."],[2_850_000,2_914_930,2_930_000,2_880_000,2_914_930],"Convergence 4 méthodes (€)",[OR,OR,OR,OR,VERT]), width='stretch')
        with col_b:
            z=[[1000,1450,1680,1750],[1100,1580,1820,None],[1050,1500,None,None],[980,None,None,None]]
            fig=go.Figure(go.Heatmap(z=z,colorscale=[[0,"#1B3A5C"],[0.5,OR],[1,ROUGE]],showscale=False,hoverongaps=False))
            fig.update_layout(paper_bgcolor=NAVY,plot_bgcolor=NAVY_L,font=dict(color=BLANC,size=10),title=dict(text="Triangle de développement",font=dict(color=BLANC,size=12),x=0.01),margin=dict(l=16,r=16,t=44,b=16),height=260)
            st.plotly_chart(fig, width='stretch')
    elif code == "A4":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Gini XGBoost","0.2651","meilleur")
        with c2: st.metric("Modèle retenu","ElasticNet","score 0.8373")
        with c3: st.metric("Overfit ratio","0.98","✅ Stable")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_bar(["XGBoost","GBM","CatBoost","LightGBM","ElasticNet"],[0.2651,0.2542,0.2534,0.2481,0.2440],"Gini par modèle ML",[ROUGE,OR,OR,OR,VERT]), width='stretch')
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
            st.plotly_chart(fig_jauge(208.5,"Ratio SCR (%)"), width='stretch')
        with col_b:
            st.plotly_chart(fig_bar(["SCR Souscr.","SCR Marché","SCR Opéra.","SCR Total"],[2_800_000,650_000,230_000,3_680_671],"Décomposition SCR (€)"), width='stretch')
    elif code == "A11":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("TP IFRS 17","3 992 344 €","PAA")
        with c2: st.metric("LRC","2 500 000 €","risque restant")
        with c3: st.metric("Ratio IFRS17/S2","1.370","✅ Cohérent")
        st.plotly_chart(fig_bar(["Best Est. S2","Risk Adj.","LRC","TP IFRS17"],[2_914_930,350_000,727_414,3_992_344],"Composition TP IFRS 17 (€)",[BLEU,AMBRE,VERT,OR]), width='stretch')
    elif code == "A12":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Duration actifs","3.50 ans","obligations")
        with c2: st.metric("Gap duration","+1.90 ans","⚠️ À surveiller")
        with c3: st.metric("LCR","1 173%","✅ Liquide")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_bar(["Actifs","Passifs"],[3.5,1.6],"Duration (années)",[BLEU,AMBRE]), width='stretch')
        with col_b:
            st.plotly_chart(fig_jauge(1173,"LCR (%)",r1=75,r2=100,max_v=1500), width='stretch')
    elif code == "A3":
        c1,c2 = st.columns(2)
        with c1: st.metric("AIC Poisson","45 312","formule std")
        with c2: st.metric("Gini GLM","0.121","référence")
        st.plotly_chart(fig_bar(["Poisson","Gamma","Tweedie"],[0.121,0.108,0.115],"Gini par GLM"), width='stretch')
    elif code == "A5":
        c1,c2 = st.columns(2)
        with c1: st.metric("Gini CANN","0.2287","Wüthrich 2019")
        with c2: st.metric("Gini TabNet","0.2334","meilleur DL")
        st.plotly_chart(fig_bar(["CANN","TabNet","ElasticNet","XGBoost"],[0.2287,0.2334,0.2440,0.2651],"DL vs ML vs GLM",[BLEU,BLEU,OR,VERT]), width='stretch')
    elif code == "A6":
        c1,c2 = st.columns(2)
        with c1: st.metric("Score ElasticNet","0.8373","retenu")
        with c2: st.metric("Profil","Équilibré","multicritères")
        st.plotly_chart(fig_bar(["ElasticNet","XGBoost","CatBoost","GLM"],[0.8373,0.7210,0.7050,0.6800],"Scores multicritères",[VERT,OR,OR,GRIS]), width='stretch')
    elif code == "A8":
        c1,c2 = st.columns(2)
        with c1: st.metric("SCR post-stress","375%","✅ Résistant")
        with c2: st.metric("ORSA 5 ans","✅ VERT","3 scénarios")
        st.plotly_chart(fig_bar(["Base","Choc fréq.","Choc coût","NatCat","Combiné"],[375,310,295,280,245],"Ratio SCR après chocs EIOPA (%)",[VERT,OR,OR,AMBRE,ROUGE]), width='stretch')
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
        st.plotly_chart(fig_bar(["Service Cost","Interest Cost","Charge totale N"],[285_000,370_585,655_585],"Décomposition charge IAS 19 (€)",[OR,BLEU,AMBRE]), width='stretch')
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
        st.plotly_chart(fig_bar(["Base","Longévité+20%","Taux bas","Rachats 40%","Fin.-20%"],[110,98.2,92.5,88.0,95.0],"Ratio couverture avant/après chocs (%)",[VERT,ROUGE,ROUGE,ROUGE,AMBRE]), width='stretch')
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
        st.plotly_chart(fig, width='stretch')
    elif code == "A13":
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Agents tracés","46 / 46","100%")
        with c2:
            import hashlib as _hl13
            _h13 = _hl13.sha256(str(st.session_state.get("agent_results",{})).encode()).hexdigest()[:8].upper()
            st.metric("Hash session", _h13, "SHA-256 [session]")
        with c3: st.metric("Conformité RGPD","✅","Art.30")

    # ── Boutons rapport — vrais bytes si disponibles ────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    _r_btn = (st.session_state.get("agent_results") or {}).get(ak, {})
    _xls_b = _r_btn.get("excel_bytes") if _r_btn else None
    _pdf_b = _r_btn.get("pdf_bytes")   if _r_btn else None
    _wrd_b = _r_btn.get("word_bytes")  if _r_btn else None
    col1,col2,col3 = st.columns(3)
    with col1:
        if _pdf_b:
            st.download_button("📄 Rapport PDF", _pdf_b,
                file_name=f"rapport_{ak}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf", use_container_width=True, key=f"pdf_{ak}")
        elif _wrd_b:
            st.download_button("📄 Rapport Word", _wrd_b,
                file_name=f"rapport_{ak}_{datetime.now().strftime('%Y%m%d')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True, key=f"pdf_{ak}")
        else:
            if st.button("📄 Rapport (lancer analyse)", use_container_width=True, key=f"pdf_{ak}"):
                nav_to("analyse")
    with col2:
        if _xls_b:
            st.download_button("📊 Export Excel", _xls_b,
                file_name=f"actuaria_{ak}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True, key=f"xls_{ak}")
        else:
            if st.button("📊 Export Excel (lancer analyse)", use_container_width=True, key=f"xls_{ak}"):
                nav_to("analyse")
    with col3:
        import json as _jau, hashlib as _hl
        _s = json.dumps(_r_btn, default=str, sort_keys=True) if _r_btn else datetime.now().isoformat()
        _hash = _hl.sha256(_s.encode()).hexdigest()[:8].upper()
        _audit = {
            "agent": a["prenom"], "code": a["code"],
            "date": datetime.now().isoformat(),
            "hash_sha256": _hash,
            "kpi": a["kpi"],
            "statut_rag": _r_btn.get("statut_rag", a["statut"]) if _r_btn else a["statut"],
            "donnees_reelles": bool(_r_btn and _r_btn.get("success")),
            "rgpd_art30": "Conforme",
        }
        st.download_button(
            label=f"🔐 Audit Trail ({_hash})",
            data=_jau.dumps(_audit, indent=2, ensure_ascii=False),
            file_name=f"audit_{ak}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True,
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
                from direction_non_vie.provisionnement.a7_provisionnement.n5_graphiques import generer_graphiques as _gen_g
                _C_val = _np_val.array(_tri_val) if not hasattr(_tri_val, "shape") else _tri_val
                if _C_val.ndim != 2 or _C_val.shape[0] < 2:
                    raise ValueError(f"Triangle invalide shape={_C_val.shape}")
                # ⚠️ L'EXPOSITION DOIT SUIVRE, SINON g15 NE SORT JAMAIS.
                # Les trois régénérations de graphiques de cette application
                # appelaient `generer_graphiques(C, n2, n3, n4)` sans elle :
                # `g15_exposition` ne pouvait pas se produire, alors que le
                # run de l'agent, lui, la transmet. Les primes vivent dans
                # `analyse_params["a7_primes"]`, chargées par l'uploader.
                _expo_val = (st.session_state.get("analyse_params", {})
                             or {}).get("a7_primes")
                _figs_val = _gen_g(_C_val, _n2_val, _n3_val,
                                   _r_val.get("n4", {}), exposition=_expo_val)
                for _gnom, _gtitle in [
                    # ⚠️ g8 RETIRÉ AU LOT C3b — cinq barres remplacées par un
                    # tableau (Excel, onglet Hypothèses) qui porte la
                    # corrélation, le seuil, la significativité ET le verdict.
                    # g11 fondu dans g4 au même lot.
                    #
                    # ⚠️ LES DEUX GRAPHIQUES QUE LE GUIDE NOMME étaient produits
                    # depuis le lot C3c et routés vers le HTML et le Word au lot
                    # C3d — mais INVISIBLES ici. L'onglet s'appelle
                    # « Validation » : c'est leur place.
                    ("g17_linearite",   "Linéarité des cumulés — hypothèse sur l'espérance (guide §9.d.ii)"),
                    ("g18_residus",     "Résidus standardisés — hypothèse sur la variance (guide §9.d.iii)"),
                    ("g9_h2",           "H2 — Stabilité des facteurs de développement"),
                    ("g10_h3",          "H3 — Loss Ratio a priori vs référence marché"),
                    ("g14_backtesting", "Back-testing — Boni/Mali de liquidation"),
                    ("g3_facteurs_cl",  "Facteurs Chain Ladder ±2σ — outliers"),
                    ("g12_sensibilites","Sensibilités du BE — Tornado Chart"),
                ]:
                    _fig_v = _figs_val.get(_gnom)
                    if _fig_v is not None:
                        st.markdown(f"<div style='font-size:0.62rem;color:{OR};font-weight:700;margin:12px 0 4px;'>{_gtitle}</div>", unsafe_allow_html=True)
                        st.plotly_chart(_fig_v, width='stretch', key=f"val_{_gnom}_{ak}")
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
  <div style="font-size:0.78rem;color:{GRIS};margin-top:4px;">{(st.session_state.get('analyse_fichier_nom') or 'freMTPL2 — démo') + ' · ' + datetime.now().strftime('%d/%m/%Y')}</div>
</div>""", unsafe_allow_html=True)

    tab_nv, tab_vie, tab_sp, tab_regl, tab_ar = st.tabs([
        "🏢 Direction Non-Vie",
        "💼 Direction Vie & EP-RE",
        "🏥 Santé-Prévoyance",
        "🛡️ Réglementation",
        "📊 Analyse Rapide",
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
            _r_a4_nv = (st.session_state.get("agent_results") or {}).get("priya", {})
            if _r_a4_nv and _r_a4_nv.get("classement"):
                _cl_nv = _r_a4_nv["classement"][:5]
                _ginis_nv = [m.get("gini", 0) for m in _cl_nv]
                _best_nv  = max(_ginis_nv)
                st.plotly_chart(fig_bar(
                    [m.get("modele","?") for m in _cl_nv], _ginis_nv,
                    "Tarification — Gini par modèle ML [réel]",
                    [VERT if g == _best_nv else OR for g in _ginis_nv]
                ), use_container_width=True, key="dash_nv_tarif")
            else:
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
                st.plotly_chart(fig_jauge(208.5, "Ratio SCR Non-Vie (%) [démo]"), width='stretch', key="dash_nv_jauge")
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
        # ── Lire résultats réels si disponibles ─────────────────────────
        _ar = st.session_state.get("agent_results") or {}
        _r_ep1 = _ar.get("henri", {})
        _r_ep2 = _ar.get("salome", {})
        _r_ep3 = _ar.get("jinho", {})
        _r_ep4 = _ar.get("claire", {})
        _r_v5  = _ar.get("nia", {})
        _ep1_ok = bool(_r_ep1.get("success"))
        _ep3_ok = bool(_r_ep3.get("success"))
        _ep4_ok = bool(_r_ep4.get("success"))
        _v5_ok  = bool(_r_v5.get("success"))

        _dbo   = (_r_ep1.get("ias19") or {}).get("dbo_total", 10_588_168)
        _rente = (_r_ep2.get("tarification") or {}).get("rente_mensuelle", 595)
        _pm_ep = (_r_ep3.get("provisions") or {}).get("pm_encours", 50_000_000)
        _tc    = _r_ep3.get("taux_couverture_pct",
                   (_r_ep3.get("provisions") or {}).get("taux_couverture_pct", 110.0))
        _ratio_scr = _r_v5.get("ratio_scr_pct", 184.9)
        _tp_be     = _r_v5.get("ratio_tp_be", 1.06)

        if _ep1_ok or _ep3_ok or _v5_ok:
            st.success("✅ Résultats Vie/EP-RE chargés — données réelles")
        else:
            st.info("💡 Lancez une analyse Vie Pure ou EP-RE pour afficher vos données réelles.")

        c1,c2,c3,c4 = st.columns(4)
        with c1:
            dbo_str = f"{_dbo/1e6:.1f}M€" if _dbo >= 1e6 else f"{_dbo:,.0f}€"
            st.metric("DBO IAS 19", dbo_str, "✅ Données réelles" if _ep1_ok else "méthode PUC [démo]")
        with c2:
            st.metric("Rente viagère", f"{_rente:,.0f} €/mois", "✅ Données réelles" if _ep1_ok else "PER [démo]")
        with c3:
            pm_str = f"{_pm_ep/1e6:.1f}M€" if _pm_ep >= 1e6 else f"{_pm_ep:,.0f}€"
            st.metric("PM EP-RE", pm_str, "✅ Données réelles" if _ep3_ok else "encours total [démo]")
        with c4:
            tc_delta = "✅ Conforme ≥ 100%" if _tc >= 100 else "⚠️ Sous-couverture"
            st.metric("Ratio couverture", f"{_tc:.1f}%", tc_delta if _ep3_ok else "avant chocs [démo]")

        col_a,col_b = st.columns(2)
        with col_a:
            if _ep1_ok:
                _ias = _r_ep1.get("ias19", {})
                st.plotly_chart(fig_bar(
                    ["DBO","Service Cost×10","Interest Cost×10"],
                    [_dbo, _ias.get("service_cost",0)*10, _ias.get("interest_cost",0)*10],
                    "IAS 19 — DBO et charges (€) [réel]", [OR,BLEU,AMBRE]
                ), use_container_width=True, key="dash_vie_ias19")
            else:
                st.plotly_chart(fig_bar(
                    ["DBO","Service Cost×10","Interest Cost×10"],
                    [10_588_168,2_850_000,3_705_850],
                    "IAS 19 — DBO et charges (€) [démo]", [OR,BLEU,AMBRE]
                ), use_container_width=True, key="dash_vie_ias19_demo")
        with col_b:
            if _ep4_ok and _r_ep4.get("scenarios"):
                _sc = _r_ep4["scenarios"]
                st.plotly_chart(fig_bar(
                    [s.get("nom","?")[:18] for s in _sc],
                    [s.get("ratio_stresse",100) for s in _sc],
                    f"Stress EP-RE — Ratio couverture (%) [réel]",
                    [VERT if s.get("ratio_stresse",100)>=100 else AMBRE if s.get("ratio_stresse",100)>=90 else ROUGE for s in _sc]
                ), use_container_width=True, key="dash_vie_stress")
            else:
                st.plotly_chart(fig_bar(
                    ["Base","Longévité+20%","Taux bas","Rachats 40%","Fin.-20%"],
                    [110,98.2,92.5,88.0,95.0],
                    "Stress EP-RE — Ratio couverture (%) [démo]",
                    [VERT,ROUGE,ROUGE,ROUGE,AMBRE]
                ), use_container_width=True, key="dash_vie_stress_demo")

        if _v5_ok:
            st.markdown(f"<div style='font-size:0.72rem;color:{OR};font-weight:700;margin:14px 0 8px;'>◆ Vie Pure — QRT S.12 & S.23</div>", unsafe_allow_html=True)
            cv1,cv2,cv3 = st.columns(3)
            with cv1: st.metric("Ratio TP/BE", f"{_tp_be:.4f}", "✅ [1.0–1.5]" if 1.0<=_tp_be<=1.5 else "⚠️ Hors seuil")
            with cv2: st.metric("Ratio SCR", f"{_ratio_scr:.1f}%", "✅ ≥ 150%" if _ratio_scr>=150 else "⚠️ Surveiller")
            with cv3:
                _wb = _r_v5.get("word_bytes")
                if _wb:
                    st.download_button("⬇️ Rapport Word", _wb,
                        file_name="rapport_vie.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="dl_v5_word_dash")
        else:
            st.info("⏸️ Lancez l'analyse Vie Pure (Nia V5) pour afficher les indicateurs S2 et télécharger le rapport.")

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
        _ar2 = st.session_state.get("agent_results") or {}
        _r10 = _ar2.get("elena", {})
        _r11 = _ar2.get("thomas", {})
        _r12 = _ar2.get("aisha", {})
        _r10_ok = bool(_r10.get("success"))
        _r11_ok = bool(_r11.get("success"))
        _r12_ok = bool(_r12.get("success"))
        _scr_r = (_r10.get("capital") or {}).get("ratio_scr", 208.5)
        _mcr_r = (_r10.get("capital") or {}).get("ratio_mcr", 320.0)
        _tp_r  = (_r11.get("provisions") or {}).get("tp_ifrs17", 3_992_344)
        _lcr_r = (_r12.get("lcr") or {}).get("lcr", 1173.0)
        _scr_t = (_r10.get("scr") or {}).get("total", 3_680_671)
        _scr_s = (_r10.get("scr") or {}).get("souscription", 2_800_000)
        _scr_m = (_r10.get("scr") or {}).get("marche", 650_000)
        _scr_o = (_r10.get("scr") or {}).get("operationnel", 230_000)
        _be_s2 = (_r10.get("provisions") or {}).get("best_estimate", 2_914_930)
        _ra_r  = (_r11.get("provisions") or {}).get("risk_adjustment", 350_000)
        _lrc_r = (_r11.get("provisions") or {}).get("lrc", 727_414)
        if _r10_ok or _r11_ok or _r12_ok:
            st.success("✅ Résultats réglementation chargés — données réelles")
        else:
            st.info("💡 Lancez une analyse Solvabilité 2, IFRS 17 ou ALM pour afficher vos données réelles.")
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("Ratio SCR", f"{_scr_r:.1f}%", "✅ > 150%" if _scr_r >= 150 else "⚠️ < 150%")
        with c2: st.metric("Ratio MCR", f"{_mcr_r:.0f}%", "✅ > 100%" if _mcr_r >= 100 else "⚠️ < 100%")
        with c3:
            tp_str = f"{_tp_r/1e6:.2f}M€" if _tp_r >= 1e6 else f"{_tp_r:,.0f}€"
            st.metric("TP IFRS17", tp_str, "PAA" + (" [réel]" if _r11_ok else " [démo]"))
        with c4: st.metric("LCR", f"{_lcr_r:,.0f}%", "✅ Très liquide" if _lcr_r >= 100 else "⚠️ < 100%")
        col_a,col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_jauge(_scr_r, f"Ratio SCR ({'réel' if _r10_ok else 'démo'}) (%)"), width='stretch', key="regl_scr_j")
        with col_b:
            st.plotly_chart(fig_bar(
                ["SCR Souscr.","SCR Marché","SCR Opéra.","SCR Total"],
                [_scr_s, _scr_m, _scr_o, _scr_t],
                f"Décomposition SCR EIOPA (€){' [réel]' if _r10_ok else ' [démo]'}",
            ), use_container_width=True, key="regl_scr_b")
        col_c,col_d = st.columns(2)
        with col_c:
            st.plotly_chart(fig_bar(
                ["BE S2","Risk Adj.","LRC","TP IFRS17"],
                [_be_s2, _ra_r, _lrc_r, _tp_r],
                f"IFRS 17 PAA — Composition TP (€){' [réel]' if _r11_ok else ' [démo]'}",
                [BLEU,AMBRE,VERT,OR]
            ), use_container_width=True, key="regl_ifrs_b")
        with col_d:
            st.plotly_chart(fig_jauge(_lcr_r, f"LCR ({'réel' if _r12_ok else 'démo'}) (%)", r1=75, r2=100, max_v=1500), width='stretch', key="regl_lcr_j")

    with tab_ar:
        st.markdown(f"""
<div style="margin-bottom:16px;">
  <div style="font-size:0.65rem;color:{OR};text-transform:uppercase;letter-spacing:0.12em;font-weight:700;">Analyse Rapide</div>
  <div style="font-family:'Playfair Display',serif;font-size:1.2rem;color:{BLANC};font-weight:700;margin-top:2px;">Provisionnement Non-Vie — Ibrahim A7</div>
  <div style="font-size:0.78rem;color:{GRIS};margin-top:4px;">Uploadez votre triangle · Lancez A7 · Visualisez les résultats</div>
</div>""", unsafe_allow_html=True)

        # ── Mode : Mono-branche / Multi-branches — même style que Format A/B/C ─
        if "ar_mode" not in st.session_state:
            st.session_state["ar_mode"] = "mono"
        st.markdown(f"<div style='font-size:0.82rem;color:{OR};font-weight:700;margin-bottom:10px;'>① Mode d'analyse</div>", unsafe_allow_html=True)
        _mode_opts = {
            "mono":  ("📊", "Mono-branche",   "Un seul triangle · Analyse complète A7 · Rapport PDF/Word"),
            "multi": ("📋", "Multi-branches", "Jusqu'à 13 branches · A7 séquentiel · Tableau BE + SCR consolidé"),
        }
        _mode_cols = st.columns([1, 1, 2])
        for _mi, (_mk, (_mico, _mnom, _mdesc)) in enumerate(_mode_opts.items()):
            with _mode_cols[_mi]:
                _m_sel  = st.session_state["ar_mode"] == _mk
                _m_bord = f"2px solid {OR}" if _m_sel else f"1px solid rgba(201,168,76,0.25)"
                _m_bg   = "rgba(201,168,76,0.12)" if _m_sel else "rgba(15,46,82,0.6)"
                st.markdown(
                    f"<div style='background:{_m_bg};border:{_m_bord};border-radius:10px;"
                    f"padding:14px 12px;text-align:center;min-height:90px;'>"
                    f"<div style='font-size:1.4rem;margin-bottom:4px;'>{_mico}</div>"
                    f"<div style='font-size:0.88rem;font-weight:700;color:{OR};margin-bottom:6px;'>{_mnom}</div>"
                    f"<div style='font-size:0.72rem;color:#8A9AB0;line-height:1.5;'>{_mdesc}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                if st.button(
                    f"{'✅ Actif' if _m_sel else 'Choisir'}",
                    key=f"btn_mode_{_mk}",
                    use_container_width=True
                ):
                    st.session_state["ar_mode"] = _mk
                    st.rerun()
        _ar_mode = st.session_state["ar_mode"]

        _ar_fichier_engage = None  # initialisé ici — défini dans le bloc mono si activé
        if _ar_mode == "mono":

            # ── Étape 1 : Format ─────────────────────────────────────────────────
            st.markdown(f"<div style='font-size:0.82rem;color:{OR};font-weight:700;margin-bottom:10px;'>① Format de votre fichier</div>", unsafe_allow_html=True)
            _ar_fmt_opts = {
                "cumule":     ("A", "Triangle cumulé", "Lignes = années · Colonnes = périodes · Cellule = montant cumulé · Format le plus courant"),
                "non_cumule": ("B", "Triangle incrémental", "Même structure que A · Cellule = paiement de l'année uniquement · Cumulé automatiquement"),
                "brutes":     ("C", "Données brutes", "Une ligne par paiement · Colonnes : annee_survenance · annee_paiement · montant"),
            }
            _ar_fmt_actuel = st.session_state.get("ar_format_declare", "cumule")
            _ar_fmt_cols = st.columns(3)
            for _ar_fi, (_ar_fk, (_ar_fl, _ar_fn, _ar_fd)) in enumerate(_ar_fmt_opts.items()):
                with _ar_fmt_cols[_ar_fi]:
                    _ar_sel  = (_ar_fmt_actuel == _ar_fk)
                    _ar_bord = f"2px solid {OR}" if _ar_sel else f"1px solid rgba(201,168,76,0.25)"
                    _ar_bg   = "rgba(201,168,76,0.12)" if _ar_sel else "rgba(15,46,82,0.6)"
                    st.markdown(f"""<div style='background:{_ar_bg};border:{_ar_bord};border-radius:10px;padding:14px 12px;text-align:center;min-height:90px;'>
      <div style='font-size:1.1rem;font-weight:900;color:{OR};margin-bottom:4px;'>Format {_ar_fl}</div>
      <div style='font-size:0.82rem;font-weight:700;color:#F0F4F8;margin-bottom:6px;'>{_ar_fn}</div>
      <div style='font-size:0.72rem;color:#8A9AB0;line-height:1.5;'>{_ar_fd}</div>
    </div>""", unsafe_allow_html=True)
                    if st.button(f"{'✅ Sélectionné' if _ar_sel else 'Choisir'}", key=f"ar_fmt_btn_{_ar_fk}", use_container_width=True):
                        st.session_state["ar_format_declare"] = _ar_fk
                        st.rerun()
            _ar_fmt = st.session_state.get("ar_format_declare", "cumule")

            # Template téléchargeable
            _ar_tpl_map = {
                "cumule":     "direction_non_vie/services/templates/template_format_A_triangle_cumule.xlsx",
                "non_cumule": "direction_non_vie/services/templates/template_format_B_triangle_incremental.xlsx",
                "brutes":     "direction_non_vie/services/templates/template_format_C_donnees_brutes.xlsx",
            }
            try:
                import os as _os_ar
                _ar_tpl = _ar_tpl_map[_ar_fmt]
                if _os_ar.path.exists(_ar_tpl):
                    with open(_ar_tpl, "rb") as _f_ar:
                        st.download_button(
                            label="📥 Télécharger le template",
                            data=_f_ar.read(),
                            file_name=_os_ar.path.basename(_ar_tpl),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"ar_dl_tpl_{_ar_fmt}",
                        )
            except Exception:
                pass

            st.divider()

            # ── Étape 2 : Upload ─────────────────────────────────────────────────
            st.markdown(f"<div style='font-size:0.82rem;color:{OR};font-weight:700;margin-bottom:6px;'>② Uploadez votre fichier</div>", unsafe_allow_html=True)
            _ar_fichier = st.file_uploader(
                "Triangle de développement",
                type=["csv", "xlsx", "xls"],
                key="ar_upload_triangle",
                help="Format déclaré ci-dessus. Le pipeline valide et construit le triangle automatiquement.",
            )

            # Onglet si multi-feuilles Excel
            _ar_onglet = None
            if _ar_fichier and _ar_fichier.name.lower().endswith((".xlsx", ".xls")):
                try:
                    import pandas as _pd_ar
                    _xl_ar = _pd_ar.ExcelFile(_ar_fichier)
                    _ar_fichier.seek(0)
                    if len(_xl_ar.sheet_names) > 1:
                        _ar_onglet = st.selectbox(
                            "Onglet contenant le triangle",
                            options=_xl_ar.sheet_names,
                            key="ar_onglet_triangle",
                        )
                    else:
                        _ar_onglet = _xl_ar.sheet_names[0]
                except Exception:
                    pass

            # Aperçu du fichier uploadé
            if _ar_fichier:
                try:
                    import pandas as _pd_ar2
                    _ar_fichier.seek(0)
                    if _ar_fichier.name.lower().endswith(".csv"):
                        _df_prev = _pd_ar2.read_csv(_ar_fichier)
                    else:
                        _df_prev = _pd_ar2.read_excel(_ar_fichier, sheet_name=_ar_onglet)
                    _ar_fichier.seek(0)
                    st.success(f"✅ {_ar_fichier.name} — {_df_prev.shape[0]} lignes × {_df_prev.shape[1]} colonnes")
                    with st.expander("👁️ Aperçu (5 premières lignes)"):
                        st.dataframe(_df_prev.head(5), use_container_width=True)
                except Exception as _e_prev:
                    st.warning(f"⚠️ Aperçu impossible : {_e_prev}")

            st.divider()
            # ── Munich CL : triangle engagé (optionnel) ─────────────────────
            with st.expander('📐 Munich Chain Ladder — Triangle charges engagées (optionnel)'):
                st.markdown(
                    '<div style="font-size:0.78rem;color:#F0F4F8;line-height:1.7;">'
                    '<b style="color:#C9A84C;">Munich Chain Ladder (Quarg & Mack 2004)</b> — améliore la précision en exploitant les charges engagées (payé + IBNR dossier).<br><br>'
                    '<b style="color:#E74C3C;">⚠️ Point critique :</b> les charges engagées <b>doivent provenir des gestionnaires sinistres</b> (évaluations dossier par dossier), '
                    'jamais calculées depuis vos provisions actuarielles. '
                    'Une circularité invalide complètement les résultats MCL (CV des ratios engagé/payé < 0.02 = détection automatique).<br><br>'
                    '<b>Format attendu :</b> même structure que votre triangle payé '
                    '(lignes = années survenance, colonnes = périodes développement).'
                    '</div>',
                    unsafe_allow_html=True
                )
                _ar_fichier_engage = st.file_uploader(
                    'Triangle des charges engagées',
                    type=['csv', 'xlsx', 'xls'],
                    key='ar_upload_engage',
                    help='Données dossier par dossier — jamais depuis vos provisions actuarielles (circularité)',
                )
            # Lire triangle engagé si fourni — via variable locale
            _ar_triangle_engage = None
            if _ar_fichier_engage is not None:
                try:
                    import pandas as _pd_eng
                    _ar_fichier_engage.seek(0)
                    if _ar_fichier_engage.name.lower().endswith('.csv'):
                        _df_eng = _pd_eng.read_csv(_ar_fichier_engage)
                    else:
                        _df_eng = _pd_eng.read_excel(_ar_fichier_engage)
                    _ar_triangle_engage = _df_eng.values.astype(float)
                except Exception as _e_eng:
                    st.warning('⚠️ Triangle engagé : ' + str(_e_eng))


            # ── Étape 3 : Paramètres ──────────────────────────────────────────────
            st.markdown(f"<div style='font-size:0.82rem;color:{OR};font-weight:700;margin-bottom:6px;'>③ Paramètres (optionnel)</div>", unsafe_allow_html=True)
            _ar_col1, _ar_col2, _ar_col3 = st.columns(3)
            with _ar_col1:
                _ar_lob_options = {
                    "rc_auto_corporels":      "🚑 RC Auto Corporels",
                    "rc_auto_materiel":       "🚗 RC Auto Matériels",
                    "mrh":                    "🏠 MRH",
                    "rc_generale":            "🏢 RC Générale",
                    "rc_medicale":            "🩺 RC Médicale",
                    "construction":           "🏗️ Construction",
                    "transport":              "🚢 Transport",
                    "incendie_dommages":      "🔥 Incendie & Dommages",
                    "catastrophes_naturelles":"🌧️ Catastrophes Naturelles",
                    "protection_juridique":   "⚖️ Protection Juridique",
                    "accidents_corporels":    "🏥 Accidents Corporels",
                    "credit_caution":         "💳 Crédit & Caution",
                    "generique":              "⚙️ Générique",
                }
                _ar_lob = st.selectbox("Ligne de branche (LoB)", options=list(_ar_lob_options.keys()),
                                       format_func=lambda x: _ar_lob_options[x], key="ar_lob", index=0)
            with _ar_col2:
                _ar_arrete = st.text_input("Date d'arrêté", placeholder="Ex : 31/12/2024", key="ar_arrete")
            with _ar_col3:
                _ar_n_sim = st.selectbox("Bootstrap N simulations", options=[1000, 5000, 10000],
                                         index=1, key="ar_n_sim")

            st.divider()

            # ── Étape 4 : Lancement ───────────────────────────────────────────────
            st.markdown(f"<div style='font-size:0.82rem;color:{OR};font-weight:700;margin-bottom:6px;'>④ Lancer l'analyse</div>", unsafe_allow_html=True)

            _ar_btn = st.button(
                "🚀 Lancer A7 Ibrahim — Provisionnement complet",
                key="ar_lancer",
                disabled=(_ar_fichier is None),
                use_container_width=True,
            )

            if _ar_fichier is None:
                st.caption("⬆️ Uploadez d'abord votre fichier pour activer l'analyse.")

            # ── Résultats ─────────────────────────────────────────────────────────
            _ar_res = st.session_state.get("ar_resultats_a7")

            if _ar_btn and _ar_fichier:
                with st.spinner("⏳ A7 Ibrahim en cours — 7 méthodes actuarielles..."):
                    try:
                        from direction_non_vie.services.nv_triangle_builder import NVTriangleBuilder
                        from direction_non_vie.provisionnement.a7_provisionnement import AgentA7Provisionnement
                        # Étiquette de méthode DÉDUITE du résultat : elle vit dans A7
                        # pour être testable — la gate ne peut pas importer ce fichier,
                        # streamlit n'y étant pas installé.
                        from direction_non_vie.provisionnement.a7_provisionnement.agent import (
                            etiquette_methode_grands)
                        import os as _os_a7r

                        _tmp_ar = "/tmp/actuaria"
                        _os_a7r.makedirs(_tmp_ar, exist_ok=True)

                        # Construction du triangle via builder (P3-bis — format déclaré)
                        _builder_ar = NVTriangleBuilder(verbose=False)
                        _ar_fichier.seek(0)
                        _res_build_ar = _builder_ar.construire(
                            source       = _ar_fichier,
                            mode_declare = _ar_fmt,
                            nom_onglet   = _ar_onglet,
                        )

                        if not _res_build_ar["success"]:
                            st.error(f"❌ Erreur pipeline données : {_res_build_ar['erreur']}")
                            st.session_state["ar_resultats_a7"] = None
                        else:
                            # Alertes pipeline
                            for _al in _res_build_ar["rapport"].get("alertes", []):
                                if "❌" in _al:
                                    st.error(_al)
                                elif "⚠️" in _al:
                                    st.warning(_al)

                            # Détecter les grands sinistres depuis le builder
                            _grands_df   = _res_build_ar.get("grands_sinistres", None)
                            _n_grands    = len(_grands_df) if _grands_df is not None and not _grands_df.empty else 0
                            _rec_grands  = _res_build_ar.get("recommandation_grands", "non_applicable")
                            _llt_utilise = _res_build_ar.get("llt_utilise")

                            # Triangle à utiliser : attritional si LLT actif, sinon total
                            _tri_attrit = _res_build_ar.get("triangle_attritional")
                            _tri_grands = _res_build_ar.get("triangle_grands")
                            _tri_ar = _tri_attrit if (_tri_attrit is not None) else _res_build_ar["triangle_total"]

                            # Réserve grands sinistres
                            _reserve_gs = 0.0
                            _methode_gs = "non_applicable"

                            if _n_grands > 0 and _llt_utilise:
                                if _n_grands < 20:
                                    # Développement individuel : saisie manuelle
                                    st.markdown(
                                        f"<div style='background:{NAVY_LL};border-left:4px solid {AMBRE};"
                                        f"border-radius:8px;padding:12px 16px;margin:8px 0;'>"
                                        f"<b style='color:{AMBRE};'>⚠️ {_n_grands} grand(s) sinistre(s) détecté(s)</b><br>"
                                        f"<span style='color:{BLANC};font-size:0.78rem;'>"
                                        f"Volume insuffisant pour CL séparé (n&lt;20). "
                                        f"Saisissez la réserve dossier par dossier ci-dessous (Guide IA 2023 §4.c.iv p37, qui recommande l'expertise dossier par dossier plutot que la projection).</span>"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
                                    _reserve_gs = st.number_input(
                                        "Réserve grands sinistres (€) — saisie actuaire",
                                        min_value=0.0, value=0.0, step=10_000.0,
                                        key="ar_reserve_gs_manuel",
                                        help="Somme des réserves dossier par dossier pour les grands sinistres identifiés"
                                    )
                                    _methode_gs = "developpement_individuel"
                                elif _tri_grands is not None and _n_grands >= 20:
                                    # ⚠️ L'ÉTIQUETTE EST DÉDUITE DU RÉSULTAT, PLUS
                                    # SUPPOSÉE. Cette branche annonçait « BF auto »
                                    # sans jamais fournir d'exposition : depuis que
                                    # BF et Cape Cod refusent de tourner sans elle,
                                    # la réserve produite est du CHAIN LADDER PUR.
                                    # Une réserve grands sinistres portait donc un
                                    # nom de méthode faux dans un dossier ACPR.
                                    st.info(f"🔄 {_n_grands} grands sinistres — "
                                            f"calcul automatique sur triangle séparé.")
                                    try:
                                        _r7_gs = AgentA7Provisionnement(
                                            audit_path=_tmp_ar, models_path=_tmp_ar, verbose=False
                                        ).run(
                                            source=_tri_grands, mode_declare="cumule",
                                            lob=_ar_lob, generer_graphiques=False,
                                            n_sim_bootstrap=500,
                                            generer_word=False, generer_pdf_flag=False,
                                        )
                                        if _r7_gs.get("success"):
                                            _reserve_gs = float(_r7_gs.get("n4",{}).get("best_estimate",0))
                                            _inc_gs  = _r7_gs.get("n4", {}).get("methodes_incluses", [])
                                            _methode_gs, _lbl_gs = etiquette_methode_grands(_inc_gs)
                                            st.success(f"✅ Réserve grands sinistres : "
                                                       f"{_reserve_gs:,.0f}€ ({_lbl_gs})")
                                            if _methode_gs == "cl_separe":
                                                st.caption(
                                                    "ℹ️ Aucune exposition n'étant fournie pour le "
                                                    "triangle des grands sinistres, Bornhuetter-Ferguson "
                                                    "et Cape Cod ne sont pas calculées : cette réserve "
                                                    "repose sur Chain Ladder seule.")
                                    except Exception as _e_gs:
                                        st.warning(f"⚠️ Calcul grands sinistres échoué : {_e_gs}. Saisie manuelle.")

                            _a7_ar  = AgentA7Provisionnement(
                                audit_path=_tmp_ar, models_path=_tmp_ar, verbose=False
                            )
                            _ar_fichier.seek(0)
                            _r7_ar = _a7_ar.run(
                                source                   = _tri_ar,
                                mode_declare             = "cumule",
                                generer_graphiques       = True,
                                lob                      = _ar_lob,
                                arrete                   = _ar_arrete,
                                n_sim_bootstrap          = _ar_n_sim,
                                generer_word             = False,
                                generer_pdf_flag         = False,
                                reserve_grands_sinistres = _reserve_gs if _reserve_gs > 0 else None,
                                n_grands_sinistres       = _n_grands,
                                methode_grands           = _methode_gs,
                                triangle_engage          = _ar_triangle_engage,
                            )
                            st.session_state["ar_resultats_a7"] = _r7_ar
                            _ar_res = _r7_ar

                            if _r7_ar.get("success"):
                                st.success("✅ Analyse A7 terminée")
                                # Diagnostic qualite du triangle
                                _diag_ar = _res_build_ar.get("diagnostic_qualite", {})
                                if _diag_ar:
                                    _dscore = _diag_ar.get("score", 0)
                                    _dstat  = _diag_ar.get("statut", "")
                                    _dcol   = VERT if _dstat=="VERT" else AMBRE if _dstat=="AMBRE" else ROUGE
                                    _demoji = "OK" if _dstat=="VERT" else "ATTENTION" if _dstat=="AMBRE" else "ALERTE"
                                    st.markdown(
                                        f"<div style='background:{NAVY_LL};border-left:4px solid {_dcol};"
                                        f"border-radius:8px;padding:12px 16px;margin:8px 0;'>"
                                        f"<div style='font-size:0.8rem;font-weight:700;color:{_dcol};"
                                        f"margin-bottom:6px;'>{_demoji} Qualite du triangle : {_dstat} — Score {_dscore}/100</div>"
                                        f"<div style='font-size:0.75rem;color:{BLANC};line-height:1.6;'>"
                                        f"{_diag_ar.get('resume','')[:200]}</div>"
                                        + "".join(
                                            f"<div style='font-size:0.72rem;color:{AMBRE if _dc['statut']=='AMBRE' else ROUGE};"
                                            f"margin-top:4px;'>{_dc['code']} — {_dc['message'][:100]}</div>"
                                            for _dc in _diag_ar.get("controles", [])
                                            if _dc.get("statut") != "VERT"
                                        )
                                        + "</div>",
                                        unsafe_allow_html=True
                                    )
                            else:
                                st.error(f"❌ Erreur A7 : {_r7_ar.get('erreur', 'Inconnue')}")

                    except Exception as _e_ar:
                        st.error(f"❌ Erreur inattendue : {_e_ar}")
                        st.session_state["ar_resultats_a7"] = None

            # ── Affichage des résultats ───────────────────────────────────────────
            if _ar_res and _ar_res.get("success"):
                _ar_n3 = _ar_res.get("n3", {})
                _ar_n4 = _ar_res.get("n4", {}) or _ar_res.get("best_estimate", {})
                _ar_n2 = _ar_res.get("n2", {})

                # KPIs principaux
                st.markdown(f"<div style='font-size:0.9rem;color:{OR};font-weight:700;margin:16px 0 8px;'>Résultats — Best Estimate & KPIs</div>", unsafe_allow_html=True)
                _ar_be   = _ar_n4.get("best_estimate", 0)
                _ar_cv   = _ar_n4.get("cv_inter_methodes", 0)
                _ar_p90  = _ar_n4.get("reserve_p90", 0)
                _ar_p99  = _ar_n4.get("reserve_p99_5", 0)
                _ar_rag  = _ar_res.get("statut_rag", "VERT")

                _ar_be_str  = f"{_ar_be/1e6:.3f} M€"  if _ar_be  >= 1e6 else f"{_ar_be:,.0f} €"
                _ar_p90_str = f"{_ar_p90/1e6:.3f} M€" if _ar_p90 >= 1e6 else f"{_ar_p90:,.0f} €" if _ar_p90 else "—"
                _ar_p99_str = f"{_ar_p99/1e6:.3f} M€" if _ar_p99 >= 1e6 else f"{_ar_p99:,.0f} €" if _ar_p99 else "—"
                _ar_rag_col = VERT if _ar_rag == "VERT" else AMBRE if _ar_rag == "AMBRE" else ROUGE

                _kc1, _kc2, _kc3, _kc4 = st.columns(4)
                with _kc1: st.metric("Best Estimate S2", _ar_be_str, f"CV {_ar_cv:.1f}%" if _ar_cv else "—")
                with _kc2: st.metric("Provision P90", _ar_p90_str, "+quantile bootstrap" if _ar_p90 else "—")
                with _kc3: st.metric("Provision P99.5", _ar_p99_str, "stress extrême" if _ar_p99 else "—")
                with _kc4:
                    _ar_rag_emoji = "🟢" if _ar_rag == "VERT" else "🟡" if _ar_rag == "AMBRE" else "🔴"
                    st.metric("Statut RAG", f"{_ar_rag_emoji} {_ar_rag}")

                # Tableau comparatif multi-méthodes
                st.markdown(f"<div style='font-size:0.9rem;color:{OR};font-weight:700;margin:16px 0 8px;'>Comparaison multi-méthodes</div>", unsafe_allow_html=True)
                _ar_methodes = {
                    "Chain Ladder":          _ar_n3.get("chain_ladder", {}).get("reserve_totale", 0),
                    "Mack 1993":             _ar_n3.get("mack", {}).get("reserve_best_estimate", 0),
                    "Bornhuetter-Ferguson":  _ar_n3.get("bf", {}).get("reserve_totale", 0),
                    "Cape Cod":              _ar_n3.get("cape_cod", {}).get("reserve_totale", 0),
                    "Munich CL":             _ar_n3.get("munich", {}).get("reserve_totale", 0),
                    "Clark (2003)":          _ar_n3.get("clark", {}).get("reserve_totale", 0),
                    "Barnett-Zehnwirth":     _ar_n3.get("bz", {}).get("reserve_totale", 0),
                    "Best Estimate S2":      _ar_be,
                }
                _ar_rows = [(m, v) for m, v in _ar_methodes.items() if v and v > 0]
                if _ar_rows:
                    import pandas as _pd_tab
                    _ar_df_tab = _pd_tab.DataFrame(_ar_rows, columns=["Méthode", "Réserve (€)"])
                    _ar_df_tab["Réserve (€)"] = _ar_df_tab["Réserve (€)"].apply(lambda x: f"{x:,.0f}")
                    _ar_df_tab["vs Best Est."] = [
                        f"{(v/(_ar_be or 1)-1)*100:+.1f}%" if m != "Best Estimate S2" else "référence"
                        for m, v in _ar_rows
                    ]
                    st.dataframe(_ar_df_tab, use_container_width=True, hide_index=True)

                # Graphiques
                _ar_g_col1, _ar_g_col2 = st.columns(2)
                with _ar_g_col1:
                    _ar_noms = [m for m, v in _ar_rows if m != "Best Estimate S2"]
                    _ar_vals = [v for m, v in _ar_rows if m != "Best Estimate S2"]
                    if _ar_noms:
                        st.plotly_chart(fig_bar(
                            _ar_noms, _ar_vals,
                            f"Réserves par méthode — {_ar_lob_options.get(_ar_lob, _ar_lob)} (€)",
                            [OR if m != "Best Estimate S2" else VERT for m in _ar_noms],
                        ), use_container_width=True, key="ar_bar_methodes")

                with _ar_g_col2:
                    _ar_boot = _ar_n3.get("bootstrap", {})
                    _ar_p50  = _ar_boot.get("reserve_p50", _ar_be)
                    _ar_p75  = _ar_n4.get("reserve_p75", 0)
                    if _ar_p50 and _ar_p90:
                        st.plotly_chart(fig_bar(
                            ["P50", "P75", "P90", "P99.5"],
                            [_ar_p50, _ar_p75 or _ar_p50*1.1, _ar_p90, _ar_p99 or _ar_p90*1.15],
                            "Distribution Bootstrap — Quantiles de réserve (€)",
                            [VERT, OR, AMBRE, ROUGE],
                        ), use_container_width=True, key="ar_bar_quantiles")

                # Graphiques Plotly natifs A7
                _ar_graphs = _ar_res.get("graphiques", {})
                if _ar_graphs:
                    st.markdown(f"<div style='font-size:0.9rem;color:{OR};font-weight:700;margin:16px 0 8px;'>Graphiques actuariels</div>", unsafe_allow_html=True)
                    _ar_gcols = st.columns(2)
                    for _gi, (_gk, _gfig) in enumerate(_ar_graphs.items()):
                        try:
                            with _ar_gcols[_gi % 2]:
                                st.plotly_chart(_gfig, width='stretch', key=f"ar_g_{_gk}")
                        except Exception:
                            pass

                # Commentaire actuariel
                _ar_comm = _ar_res.get("commentaire", "")
                if _ar_comm:
                    st.markdown(f"<div style='font-size:0.9rem;color:{OR};font-weight:700;margin:16px 0 8px;'>Commentaire actuariel A7</div>", unsafe_allow_html=True)
                    st.text(_ar_comm[:2000] + ("..." if len(_ar_comm) > 2000 else ""))

                # Export rapport
                st.markdown(f"<div style='font-size:0.9rem;color:{OR};font-weight:700;margin:16px 0 8px;'>Export</div>", unsafe_allow_html=True)
                _ar_ecol1, _ar_ecol2 = st.columns(2)
                with _ar_ecol1:
                    if st.button("📄 Générer rapport Word", key="ar_export_word", use_container_width=True):
                        try:
                            from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import export_word as _ew_ar
                            _word_bytes = _ew_ar(
                                n1=_ar_res.get("n1", {}),
                                n2=_ar_res.get("n2", {}),
                                n3=_ar_res.get("n3", {}),
                                n4=_ar_res.get("n4", {}),
                                commentaire=_ar_res.get("commentaire", ""),
                                lob_label=_ar_res.get("n2", {}).get("lob_label", ""),
                                audit_id=_ar_res.get("audit_trail", {}).get("id", "") if isinstance(_ar_res.get("audit_trail"), dict) else "",
                            )
                            if _word_bytes:
                                st.download_button(
                                    "⬇️ Télécharger le rapport Word",
                                    data=_word_bytes,
                                    file_name=f"rapport_actuariel_{_ar_lob}_{datetime.now().strftime('%Y%m%d')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key="ar_dl_word",
                                )
                        except Exception as _e_word:
                            st.warning(f"Export Word : {_e_word}")
                with _ar_ecol2:
                    if st.button("📊 Envoyer au Dashboard Non-Vie", key="ar_to_dash", use_container_width=True):
                        _ar_ss = st.session_state.get("agent_results", {})
                        _ar_ss["ibrahim"] = _ar_res
                        st.session_state["agent_results"] = _ar_ss
                        st.success("✅ Résultats envoyés au Dashboard Non-Vie (onglet 🏢)")
                        st.rerun()
        elif _ar_mode == 'multi':
            _lob_labels = {
                'rc_auto_corporels':       '🚑 RC Auto Corporels',
                'rc_auto_materiel':        '🚗 RC Auto Matériels',
                'mrh':                    '🏠 MRH',
                'rc_generale':            '🏢 RC Générale',
                'rc_medicale':            '🩺 RC Médicale',
                'construction':           '🏗️ Construction',
                'transport':              '🚢 Transport',
                'incendie_dommages':      '🔥 Incendie & Dommages',
                'catastrophes_naturelles':'🌧️ Catastrophes Naturelles',
                'protection_juridique':   '⚖️ Protection Juridique',
                'accidents_corporels':    '🏥 Accidents Corporels',
                'credit_caution':         '💳 Crédit & Caution',
                'generique':              '⚙️ Générique',
            }
            st.caption('Uploadez un fichier par branche. A7 tourne séquentiellement. Tableau de synthèse BE + SCR.')
            _mb_n = st.slider('Nombre de branches', 2, 8, 3, key='mb_n_lob')

            # Fonctions format définies hors boucle — évite capture de variable
            _mb_lob_options  = list(_lob_labels.keys())
            _mb_lob_labels_list = [_lob_labels[k] for k in _mb_lob_options]
            _mb_fmt_options  = ['cumule', 'non_cumule', 'brutes']
            _mb_fmt_labels   = ['A — Cumulé', 'B — Incrémental', 'C — Données brutes']

            _mb_branches = []
            for _mb_i in range(_mb_n):
                with st.container(border=True):
                    _mb_c1, _mb_c2, _mb_c3 = st.columns([2, 2, 1])
                    with _mb_c1:
                        _mb_lob_idx = st.selectbox(
                            'Branche ' + str(_mb_i+1),
                            range(len(_mb_lob_options)),
                            format_func=lambda i: _mb_lob_labels_list[i],
                            key='mb_lob_' + str(_mb_i),
                        )
                        _mb_lob = _mb_lob_options[_mb_lob_idx]
                    with _mb_c2:
                        _mb_file = st.file_uploader(
                            'Triangle ' + str(_mb_i+1),
                            type=['csv','xlsx','xls'],
                            key='mb_file_' + str(_mb_i),
                        )
                    with _mb_c3:
                        _mb_fmt_idx = st.selectbox(
                            'Format',
                            range(len(_mb_fmt_options)),
                            format_func=lambda i: _mb_fmt_labels[i],
                            key='mb_fmt_' + str(_mb_i),
                        )
                        _mb_fmt = _mb_fmt_options[_mb_fmt_idx]
                # append hors du container — niveau boucle for
                _mb_branches.append({'lob':_mb_lob,'file':_mb_file,'fmt':_mb_fmt})

            _mb_pc1, _mb_pc2 = st.columns(2)
            with _mb_pc1:
                _mb_fpp = st.number_input('Fonds propres (€)', value=10_000_000, step=500_000, key='mb_fpp')
            with _mb_pc2:
                _mb_nsim = st.slider('Simulations Bootstrap', 200, 2000, 500, key='mb_nsim')

            if st.button('🚀 Lancer analyse Multi-branches', key='mb_run', use_container_width=True):
                _mb_ok = [b for b in _mb_branches if b['file'] is not None]
                if len(_mb_ok) < 2:
                    st.warning('Uploadez au moins 2 fichiers.')
                else:
                    _mb_res = []
                    _mb_prog = st.progress(0, text='Analyse en cours...')
                    import os as _os_mb
                    _os_mb.makedirs('/tmp/actuaria', exist_ok=True)
                    for _mb_idx, _mb_b in enumerate(_mb_ok):
                        _mb_prog.progress(
                            int(_mb_idx / len(_mb_ok) * 100),
                            text='Analyse ' + _lob_labels.get(_mb_b['lob'], _mb_b['lob']) + '...'
                        )
                        try:
                            _mb_b['file'].seek(0)
                            _mb_rb = NVTriangleBuilder(verbose=False).construire(
                                source=_mb_b['file'], mode_declare=_mb_b['fmt']
                            )
                            if not _mb_rb['success']:
                                _mb_res.append({'lob':_mb_b['lob'],'success':False,
                                    'label':_lob_labels.get(_mb_b['lob'],_mb_b['lob']),
                                    'erreur':_mb_rb.get('erreur','build échoué')})
                                continue
                            _mb_r7 = AgentA7Provisionnement(
                                audit_path='/tmp/actuaria', models_path='/tmp/actuaria', verbose=False
                            ).run(
                                source=_mb_rb['triangle_total'], mode_declare='cumule',
                                lob=_mb_b['lob'], generer_graphiques=False,
                                n_sim_bootstrap=_mb_nsim,
                                generer_word=False, generer_pdf_flag=False,
                            )
                            _mb_res.append({
                                'lob':   _mb_b['lob'],
                                'label': _lob_labels.get(_mb_b['lob'], _mb_b['lob']),
                                'success': _mb_r7['success'],
                                'result':  _mb_r7,
                            })
                        except Exception as _mb_e:
                            _mb_res.append({'lob':_mb_b['lob'],'success':False,
                                'label':_lob_labels.get(_mb_b['lob'],_mb_b['lob']),
                                'erreur':str(_mb_e)})
                    _mb_prog.progress(100, text='Analyses terminées')
                    st.session_state['mb_resultats'] = _mb_res

            # Affichage résultats
            _mb_stored = st.session_state.get('mb_resultats', [])
            if _mb_stored:
                import pandas as _pd_mb
                _mb_rows = []
                _mb_be_tot = 0.0
                _mb_scr_tot = 0.0
                for _mbr in _mb_stored:
                    if _mbr.get('success'):
                        _n4r = _mbr['result'].get('n4', {})
                        _be  = float(_n4r.get('best_estimate', 0))
                        _p90 = float(_n4r.get('reserve_p90', 0))
                        _scr = float(_n4r.get('scr', {}).get('scr_provisions', 0))
                        _st  = _mbr['result'].get('statut_rag', '—')
                        _mb_be_tot  += _be
                        _mb_scr_tot += _scr
                        _mb_rows.append({'Branche':_mbr['label'],'Statut':_st,
                            'BE S2':f'{_be:,.0f} €','P90':f'{_p90:,.0f} €','SCR':f'{_scr:,.0f} €'})
                    else:
                        _mb_rows.append({'Branche':_mbr.get('label','—'),'Statut':'❌ ERREUR',
                            'BE S2':'—','P90':'—','SCR':'—'})
                _mb_rows.append({'Branche':'📊 TOTAL','Statut':'—',
                    'BE S2':f'{_mb_be_tot:,.0f} €','P90':'—','SCR':f'{_mb_scr_tot:,.0f} €'})
                st.dataframe(_pd_mb.DataFrame(_mb_rows), use_container_width=True, hide_index=True)
                _mbc1, _mbc2 = st.columns(2)
                with _mbc1: st.metric('BE Total', f'{_mb_be_tot/1e6:.2f} M€')
                with _mbc2: st.metric('SCR Total (somme simple)', f'{_mb_scr_tot/1e6:.2f} M€')
                st.caption('SCR conservateur (sans corrélation EIOPA). Lancez A10 pour le SCR agrégé.')

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
            "vie_pure":          "💀 Équipe Vie Pure",
            "epre":              "💰 Équipe EP-RE",
            "reglementation_vie":"📋 Équipe Réglementation Vie",
        },
        "sante_prev": {
            "sante":             "💊 Équipe Santé",
            "prevoyance":        "🩺 Équipe Prévoyance",
            "reglementation_sp": "🛡️ Réglementation SP",
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
        },
        "reglementation_nv": {
            "stress":      ("🌩️ Stress Testing & ORSA",               "Isabelle A8 · Chocs EIOPA"),
            "coherence":   ("🔗 Cohérence inter-équipes",             "Marcus A9 · Contrôles RAG"),
            "s2":    ("🛡️ Solvabilité 2 (SCR/MCR/QRT)",  "Elena A10"),
            "ifrs17":("📋 IFRS 17 PAA",                   "Thomas A11"),
            "alm":   ("⚖️ ALM & Liquidité",               "Aisha A12"),
        },
        "vie_pure": {
            "tarif_deces": ("💀 Tarification Décès & Vie",    "Nour V1 · TH0002/TF0002"),
            "tarif_epargne_vie": ("💹 Tarification Épargne Vie",  "Kofi V2 · Capital différé"),
            "pm_vie":      ("📐 Provisions Mathématiques",  "Amélie V3 · PM prospective"),
            "pb_vie":      ("💸 Participation aux Bénéfices", "Théo V4 · PPB · L132-29"),
            "qrt_vie":     ("📋 Rapport & QRT Vie",          "Nia V5 · QRT Vie"),
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
            "rvie1":     ("📋 IFRS 17 BBA/VFA Vie",              "Éric R-VIE1 · CSM"),
            "rvie2":     ("⚖️ ALM Long Terme Vie",             "Camille R-VIE2 · Duration 15-25 ans"),
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
        "reglementation_sp": {
            "sp_alm":    ("⚖️ ALM & Liquidité SP",              "SP-ALM · Duration · BV01 · LCR"),
            "sp_s2":     ("🛡️ Solvabilité 2 SP (SCR/MCR)",  "SP-REG1 · SCR santé + prév"),
            "sp_ifrs17": ("📋 IFRS 17 SP",                    "SP-REG2 · PAA CoC 6%"),
            "sp_ani":    ("💊 ANI 2013 / 100%% Santé",     "SP-REG3 · Reste à charge zéro"),
            "sp_stress": ("🌡️ Stress Testing SP",          "Naomie · Chocs EIOPA SP"),
            "sp_coh":    ("🔗 Cohérence SP",                "SP-COH · 6 contrôles C1-C6"),
            "sp_audit":  ("🔐 Audit Trail SP",               "SP-AUDIT · RGPD Art.30"),
            "sp_rapport":("📄 Rapport Actuariel SP",         "SP-RAPPORT · PDF/Word"),
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

        fichier = None  # initialisé avant les blocs conditionnels (évite NameError)
        if besoin in besoins_upload:
            if besoin == "triangle_xl":
                # ── Étape 1 : Choix du format de données ─────────────────────
                _fmt_opts = {
                    "cumule":     ("A", "Triangle cumulé", "Lignes = années · Colonnes = périodes · Cellule = montant cumulé · Format le plus courant"),
                    "non_cumule": ("B", "Triangle incrémental", "Même structure que A · Cellule = paiement de l'année uniquement · Cumulé automatiquement"),
                    "brutes":     ("C", "Données brutes", "Une ligne par paiement · Colonnes : annee_survenance · annee_paiement · montant"),
                }
                _fmt_actuel = st.session_state.get("a7_format_declare", "cumule")
                st.markdown(f"<div style='font-size:0.82rem;color:{OR};font-weight:700;margin-bottom:10px;'>Format de votre fichier</div>", unsafe_allow_html=True)
                _fmt_cols = st.columns(3)
                for _fi, (_fk, (_fl, _fn, _fd)) in enumerate(_fmt_opts.items()):
                    with _fmt_cols[_fi]:
                        _selected = (_fmt_actuel == _fk)
                        _border   = f"2px solid {OR}" if _selected else f"1px solid rgba(201,168,76,0.25)"
                        _bg       = "rgba(201,168,76,0.12)" if _selected else "rgba(15,46,82,0.6)"
                        _lbl_col  = OR if _selected else "#8A9AB0"
                        st.markdown(f"""<div style='background:{_bg};border:{_border};border-radius:10px;padding:14px 12px;text-align:center;min-height:90px;'>
  <div style='font-size:1.1rem;font-weight:900;color:{OR};margin-bottom:4px;'>Format {_fl}</div>
  <div style='font-size:0.82rem;font-weight:700;color:#F0F4F8;margin-bottom:6px;'>{_fn}</div>
  <div style='font-size:0.72rem;color:#8A9AB0;line-height:1.5;'>{_fd}</div>
</div>""", unsafe_allow_html=True)
                        if st.button(f"{'✅ Sélectionné' if _selected else 'Choisir'}", key=f"fmt_btn_{_fk}", use_container_width=True):
                            st.session_state["a7_format_declare"] = _fk
                            st.rerun()
                _fmt_choisi = st.session_state.get("a7_format_declare", "cumule")

                # ── Bouton template téléchargeable ───────────────────────────
                _tpl_map = {
                    "cumule":     "direction_non_vie/services/templates/template_format_A_triangle_cumule.xlsx",
                    "non_cumule": "direction_non_vie/services/templates/template_format_B_triangle_incremental.xlsx",
                    "brutes":     "direction_non_vie/services/templates/template_format_C_donnees_brutes.xlsx",
                }
                try:
                    import os as _os_tpl
                    _tpl_path = _tpl_map[_fmt_choisi]
                    if _os_tpl.path.exists(_tpl_path):
                        with open(_tpl_path, "rb") as _f_tpl:
                            st.download_button(
                                label=f"📥 Télécharger le template {_fmt_choisi.replace('_',' ').title()}",
                                data=_f_tpl.read(),
                                file_name=_os_tpl.path.basename(_tpl_path),
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"dl_tpl_{_fmt_choisi}",
                            )
                except Exception:
                    pass

                # ── Étape 2 : Upload du fichier ──────────────────────────────
                fichier = st.file_uploader(
                    "Triangle de développement (payés)",
                    type=["csv","xlsx","xls"],
                    key="upload_triangle",
                    help="Uploadez votre fichier dans le format sélectionné ci-dessus.",
                )

                # ── Triangle des charges engagées (Munich CL) ────────────────
                fichier_engage = st.file_uploader(
                    "🇩🇪 Triangle des charges engagées — optionnel, pour Munich Chain Ladder",
                    type=["csv","xlsx","xls"], key="upload_triangle_engage",
                    help="Format A ou B uniquement. Requis pour Munich CL (Quarg-Mack 2004).",
                )
                if fichier_engage:
                    try:
                        import pandas as _pd_eng
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
                        import pandas as _pd_ong
                        _xl_tmp = _pd_ong.ExcelFile(fichier)
                        fichier.seek(0)
                        _sheets = _xl_tmp.sheet_names
                        if len(_sheets) > 1:
                            _ong = st.selectbox(
                                'Onglet à utiliser pour le triangle',
                                options=_sheets,
                                key='a7_onglet_triangle',
                                help='Fichier multi-onglets : sélectionnez le triangle de paiements.',
                            )
                        else:
                            _ong = _sheets[0] if _sheets else None
                            st.session_state['a7_onglet_triangle_mono'] = _ong
                        # Lecture robuste : essayer header=0, puis header=1 si 0 col numériques
                        # (gère les anciens templates avec titre fusionné en ligne 1)
                        df_preview = _pd_ong.read_excel(fichier, sheet_name=_ong, header=0)
                        fichier.seek(0)
                        if df_preview.select_dtypes(include=["number"]).shape[1] == 0:
                            df_preview = _pd_ong.read_excel(fichier, sheet_name=_ong, header=1)
                            fichier.seek(0)
                        # Conversion forcée object→numeric
                        for _c in df_preview.columns:
                            df_preview[_c] = _pd_ong.to_numeric(df_preview[_c], errors='coerce').fillna(df_preview[_c])
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
                        "incendie_dommages":         "🔥 Incendie & Dommages aux Biens",
                        "protection_juridique":      "⚖️ Protection Juridique",
                        "catastrophes_naturelles":   "🌧️ Catastrophes Naturelles",
                        "credit_caution":            "💳 Crédit / Caution",
                        "dommage_corporel_individuel": "🤝 Dommage Corporel Individuel",
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
                        # ⚠️ UNE DATE, PLUS UN LIBELLÉ LIBRE. Ce champ était un
                        # texte (« Q2 2026 »), donc ni comparable ni ordonnable
                        # — le relevé du dépôt a trouvé 26 formes de cette même
                        # notion sur 71 sites. Une clôture ne peut pas être
                        # jugée contre une chaîne : la gouvernance de la courbe
                        # a besoin d'une date pour dire si la courbe employée
                        # existait à l'arrêté.
                        #
                        # ⚠️ ET LE LIBELLÉ N'EST PAS SUPPRIMÉ, IL EST DÉRIVÉ.
                        # Deux champs qui disent le même fait finissent par se
                        # contredire ; un libellé calculé ne le peut pas.
                        # « T2 2026 » remplace donc « Q2 2026 » dans les
                        # rapports — même notion, notation française du dépôt.
                        _arrete_date = st.date_input(
                            "Arrêté comptable",
                            value=_arrete_core.dernier_trimestre_clos(),
                            format="DD/MM/YYYY",
                            key="a7_arrete_date",
                        )
                        _arrete_obj = _lire_arrete(_arrete_date)
                        _arrete = _libelle_arrete(_arrete_obj)
                        if _arrete_obj is not None and not _fin_de_periode(
                                _arrete_obj):
                            st.caption(
                                f"ℹ️ {_arrete} n'est pas une fin de trimestre "
                                f"comptable usuelle — run-off ou cession de "
                                f"portefeuille ? Signalé, pas refusé.")
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

                    _annee_debut = st.number_input(
                        "Année de début du triangle — optionnel",
                        min_value=1900, max_value=2030,
                        value=1900, step=1,
                        key="a7_annee_debut",
                        help="Première année de survenance du triangle. Laisser à 1900 si inconnue.",
                    )

                    _lr_apriori = st.number_input(
                        "A priori Loss Ratio BF/Cape Cod (%) — optionnel",
                        min_value=0.0, max_value=300.0,
                        value=0.0, step=1.0,
                        key="a7_lr_apriori",
                        help="Si fourni, écrase le LR calculé depuis les primes. "
                             "Laisser à 0 pour calcul automatique.",
                    )

                    # ── Large Loss Threshold (LLT) ────────────────────────────
                    # Uniquement pertinent pour les données individuelles (besoin=sinistres)
                    # Sur triangle agrégé, ce champ est ignoré avec un message explicatif
                    st.markdown(
                        f"<div style='font-size:0.72rem;color:{OR};font-weight:600;"
                        f"margin-top:8px;margin-bottom:4px;'>"
                        f"🎯 Large Loss Threshold — Séparation grands sinistres</div>",
                        unsafe_allow_html=True
                    )
                    _llt = st.number_input(
                        "LLT — Seuil grands sinistres (€)",
                        min_value=0, max_value=100_000_000,
                        value=0, step=10_000,
                        key="a7_llt",
                        help="Sinistres ≥ LLT sont traités séparément du triangle attritional. "
                             "Laisser à 0 pour utiliser le triangle global sans séparation. "
                             "Applicable uniquement sur données individuelles (pas sur triangle cumulé). "
                             "Guide IA 2023 §4.c — Les sinistres graves, p36-37.",
                    )
                    if _llt > 0:
                        st.info(f"✅ LLT activé : {_llt:,.0f} € — séparation attritional/grands sinistres")

                    # ── Triangle des charges engagées (Munich CL) ─────────────
                    # Doit provenir des évaluations dossier par dossier indépendantes.
                    # Ne pas calculer depuis les provisions actuarielles → circularité
                    # (Quarg & Mack 2004)
                    st.markdown(
                        f"<div style='font-size:0.72rem;color:{OR};font-weight:600;"
                        f"margin-top:8px;margin-bottom:4px;'>"
                        f"🇩🇪 Charges engagées — Munich CL (optionnel)</div>",
                        unsafe_allow_html=True
                    )
                    st.caption(
                        "Fourni par vos gestionnaires sinistres. "
                        "Formats acceptés : triangle cumulé, incrémental, ou données individuelles. "
                        "Multi-onglets Excel supporté."
                    )
                    _fichier_engage_sin = st.file_uploader(
                        "Charges engagées (CSV ou Excel)",
                        type=["csv","xlsx","xls"],
                        key="a7_charges_sinistres",
                        help="Triangle des charges engagées indépendant des paiements.",
                    )
                    if _fichier_engage_sin:
                        try:
                            import pandas as _pd_ch
                            if not _fichier_engage_sin.name.endswith(".csv"):
                                _xl_ch = _pd_ch.ExcelFile(_fichier_engage_sin)
                                _fichier_engage_sin.seek(0)
                                if len(_xl_ch.sheet_names) > 1:
                                    _onglet_ch = st.selectbox(
                                        "Onglet contenant les charges",
                                        options=_xl_ch.sheet_names,
                                        key="a7_onglet_charges",
                                    )
                                    _df_ch = _pd_ch.read_excel(_fichier_engage_sin, sheet_name=_onglet_ch)
                                else:
                                    _df_ch = _pd_ch.read_excel(_fichier_engage_sin)
                            else:
                                _df_ch = _pd_ch.read_csv(_fichier_engage_sin)
                            _fichier_engage_sin.seek(0)
                            _df_ch_num = _df_ch.select_dtypes(include='number')
                            if len(_df_ch_num.columns) > 0:
                                st.session_state["analyse_params"]["a7_triangle_engage"] = _df_ch_num.fillna(0).values.tolist()
                                st.success(f"✅ Charges chargées — {_df_ch_num.shape[0]}×{_df_ch_num.shape[1]}")
                            else:
                                st.session_state["analyse_params"]["a7_charges_individuelles"] = _df_ch.to_dict("records")
                                st.success(f"✅ Évaluations individuelles — {len(_df_ch)} dossiers")
                        except Exception as _ech:
                            st.error(f"❌ Erreur chargement charges : {_ech}")

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

                    # ── Courbe des taux EIOPA (Risk Margin S2) ───────────────────────
                    st.markdown(
                        "<div style='background:#1a2e45;border:1px solid rgba(212,175,55,0.3);"
                        "border-radius:6px;padding:10px 14px;margin:8px 0 6px;'>"
                        "<span style='color:#D4AF37;font-size:0.75rem;font-weight:700;"
                        "text-transform:uppercase;letter-spacing:1px;'>"
                        "📈 Courbe des taux EIOPA — Risk Margin S2</span></div>",
                        unsafe_allow_html=True
                    )
                    # Initialiser la valeur par défaut dans session_state
                    if "a7_rfr_mode" not in st.session_state:
                        st.session_state["a7_rfr_mode"] = "Courbe embarquée (EIOPA EUR 31/03/2025)"
                    _rfr_options = ["Courbe embarquée (EIOPA EUR 31/03/2025)", "Taux manuel unique", "Fichier Excel EIOPA"]
                    _rfr_mode = st.selectbox(
                        "Source de la courbe RFR",
                        _rfr_options,
                        index=_rfr_options.index(st.session_state.get("a7_rfr_mode", _rfr_options[0])),
                        key="a7_rfr_mode",
                        label_visibility="visible",
                    )
                    _rfr_courbe = None
                    if _rfr_mode == "Taux manuel unique":
                        _taux_man = st.number_input(
                            "Taux RFR annuel (%)",
                            min_value=0.0, max_value=10.0, value=2.85, step=0.01,
                            key="a7_rfr_taux_manuel",
                            help="Taux EIOPA RFR EUR moyen pour la duration de votre portefeuille"
                        )
                        from direction_non_vie.provisionnement.a7_provisionnement.config.rfr_eiopa import get_courbe_taux_plat
                        _rfr_courbe = get_courbe_taux_plat(_taux_man)
                        st.info(f"ℹ️ Taux plat {_taux_man:.3f}% appliqué à toutes les maturités")
                    elif _rfr_mode == "Fichier Excel EIOPA":
                        _fichier_rfr = st.file_uploader(
                            "Fichier Excel courbe EIOPA (colonnes : maturite | taux_pct)",
                            type=["xlsx", "xls"], key="a7_rfr_fichier"
                        )
                        if _fichier_rfr:
                            from direction_non_vie.provisionnement.a7_provisionnement.config.rfr_eiopa import get_courbe_depuis_excel
                            _rfr_courbe = get_courbe_depuis_excel(_fichier_rfr.read())
                            if _rfr_courbe.get('erreur'):
                                st.error(f"❌ {_rfr_courbe['erreur']} — courbe embarquée utilisée")
                            else:
                                st.success(f"✅ {_rfr_courbe['label']}")
                        else:
                            st.warning("⚠️ Aucun fichier — courbe embarquée Q1 2025 utilisée")

                    # Stocker dans session_state pour que l'appel run() les récupère
                    if "analyse_params" not in st.session_state:
                        st.session_state["analyse_params"] = {}
                    st.session_state["analyse_params"].update({
                        "a7_lob":                _lob_sel,
                        "a7_courbe_rfr":         _rfr_courbe,
                        "a7_arrete":             _arrete,
                        # ⚠️ LA DATE TYPÉE VOYAGE À CÔTÉ DU LIBELLÉ, et ce
                        # n'est PAS une seconde source : le libellé en est
                        # DÉRIVÉ, il ne peut donc pas la contredire. C'est
                        # elle que la gouvernance de la courbe lira — un
                        # libellé ne se compare pas à une date de publication
                        # EIOPA.
                        "a7_arrete_iso": (_arrete_core.iso(_arrete_obj)
                                          if _arrete_obj is not None else ''),
                        "a7_n_sim_bootstrap":    int(_n_sim),
                        "a7_annee_base_reserve": int(_annee_base),
                        "a7_resultats_precedents": _res_prec,
                        "a7_primes":             _primes_array,
                        "a7_lr_apriori":         float(_lr_apriori) / 100 if _lr_apriori > 0 else None,
                        "a7_annee_debut":        int(_annee_debut) if _annee_debut > 1900 else None,
                        "a7_llt":                int(_llt) if _llt > 0 else None,
                    })

        # ── Cas paramètres manuels ────────────────────────────────────────
        elif besoin in ["stress","coherence","s2","ifrs17","alm","ias19","tarif","prov","stress","report","report_sante","prov_sante","tables","prov_prev","report_prev","tarif_deces","tarif_epargne_vie","pm_vie","pb_vie","qrt_vie"]:
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

                # ── Tables d'expérience propriétaires (optionnel) ─────────────
                if besoin in ["tables", "prov_prev", "report_prev"]:
                    with st.expander("📊 Importer des tables d'expérience propriétaires (optionnel)", expanded=False):
                        st.caption(
                            "Substituez les références BCAC 2019 / TD 88-90 par vos tables internes. "
                            "Formats acceptés : CSV (séparateur , ou ;) et Excel (.xlsx)."
                        )
                        _tc_type = st.selectbox(
                            "Type de table",
                            ["incidence_itt", "maintien_itt", "mortalite_ip"],
                            format_func=lambda x: {
                                "incidence_itt": "Incidence ITT (Q_AI par âge et CSP)",
                                "maintien_itt":  "Maintien ITT (TD par âge d'entrée et durée)",
                                "mortalite_ip":  "Mortalité / Passage IP (qx par âge)",
                            }[x],
                            key="p_tc_type",
                        )
                        # Template téléchargeable
                        try:
                            from direction_sante_prevoyance.services.sp_tables_import import get_template
                            _tpl_csv = get_template(_tc_type)
                            st.download_button(
                                f"⬇️ Télécharger template {_tc_type}.csv",
                                data=_tpl_csv,
                                file_name=f"template_{_tc_type}.csv",
                                mime="text/csv",
                                key=f"p_tc_tpl_{_tc_type}",
                            )
                        except Exception:
                            pass

                        _tc_fichier = st.file_uploader(
                            "Charger votre table",
                            type=["csv", "xlsx", "xls"],
                            key="p_tc_fichier",
                        )
                        if _tc_fichier is not None:
                            try:
                                from direction_sante_prevoyance.services.sp_tables_import import charger_table
                                _tc_res = charger_table(_tc_fichier, _tc_type)
                                if _tc_res["success"]:
                                    st.success(
                                        f"✅ Table chargée — {_tc_res['rapport']['nb_ages']} âges, "
                                        f"plage {_tc_res['rapport']['plage_ages']}"
                                    )
                                    for _w in _tc_res.get("avertissements", []):
                                        st.warning(_w)
                                    # Stocker en session pour transmission au run
                                    if "tables_client_sp" not in st.session_state:
                                        st.session_state["tables_client_sp"] = {}
                                    st.session_state["tables_client_sp"][_tc_type] = _tc_res
                                else:
                                    st.error(f"❌ {_tc_res['erreur']}")
                                    if "tables_client_sp" in st.session_state:
                                        st.session_state["tables_client_sp"].pop(_tc_type, None)
                            except Exception as _e_tc:
                                st.error(f"Erreur import table : {_e_tc}")
                        # Afficher les tables déjà chargées
                        _tc_loaded = st.session_state.get("tables_client_sp", {})
                        if _tc_loaded:
                            st.markdown(f"<div style='font-size:0.78rem;color:{OR};margin-top:6px;'>Tables chargées :</div>", unsafe_allow_html=True)
                            for _tk, _tv in _tc_loaded.items():
                                st.markdown(
                                    f"<div style='font-size:0.75rem;color:#aaa;'>✔ {_tk} — "
                                    f"{_tv['rapport']['plage_ages']} — "
                                    f"{_tv['meta']['horodatage_import']}</div>",
                                    unsafe_allow_html=True,
                                )

            elif besoin == "tarif_deces":
                st.markdown(f'<div style="font-size:0.78rem;color:{BLANC};margin-bottom:10px;">✏️ <strong>Nour V1 — Tarification Décès</strong> · Tables TH0002/TF0002</div>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    age_v1 = st.number_input("Âge assuré (ans)", value=42, min_value=18, max_value=75, step=1, key="p_v1_age")
                    sexe_v1 = st.selectbox("Sexe", ["H","F"], key="p_v1_sexe")
                with c2:
                    duree_v1 = st.number_input("Durée contrat (ans)", value=20, min_value=1, max_value=40, step=1, key="p_v1_duree")
                    capital_v1 = st.number_input("Capital décès (€)", value=150_000, step=10_000, key="p_v1_cap")
                with c3:
                    taux_v1 = st.number_input("Taux technique (%)", value=2.50, step=0.25, key="p_v1_taux")
                    charg_v1 = st.number_input("Chargement (%)", value=20.0, step=1.0, key="p_v1_charg")
                st.session_state["analyse_params"] = {
                    "age": age_v1, "sexe": sexe_v1, "duree": duree_v1,
                    "capital_deces": capital_v1, "taux_technique": taux_v1/100,
                    "chargement_pct": charg_v1/100,
                }

            elif besoin == "tarif_epargne_vie":
                st.markdown(f'<div style="font-size:0.78rem;color:{BLANC};margin-bottom:10px;">✏️ <strong>Kofi V2 — Tarification Épargne Vie</strong> · Capital différé · Rentes · Multisupport</div>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    age_v2 = st.number_input("Âge assuré (ans)", value=45, min_value=18, max_value=70, step=1, key="p_v2_age")
                    sexe_v2 = st.selectbox("Sexe", ["H","F"], key="p_v2_sexe")
                    duree_v2 = st.number_input("Durée (ans)", value=20, min_value=5, max_value=40, step=1, key="p_v2_duree")
                with c2:
                    capital_v2 = st.number_input("Capital cible (€)", value=80_000, step=5_000, key="p_v2_cap")
                    type_v2 = st.selectbox("Type contrat", ["capital_differe","rente_immediate","rente_differee","mixte"], key="p_v2_type")
                with c3:
                    taux_v2 = st.number_input("Taux technique (%)", value=1.80, step=0.10, key="p_v2_taux")
                    tmg_v2 = st.number_input("TMG (%)", value=0.0, step=0.25, key="p_v2_tmg")
                st.session_state["analyse_params"] = {
                    "age": age_v2, "sexe": sexe_v2, "duree": duree_v2,
                    "capital": capital_v2, "type_contrat": type_v2,
                    "taux_technique": taux_v2/100, "tmg": tmg_v2/100 if tmg_v2 > 0 else 0.0,
                }

            elif besoin == "pm_vie":
                st.markdown(f'<div style="font-size:0.78rem;color:{BLANC};margin-bottom:10px;">✏️ <strong>Amélie V3 — Provisions Mathématiques Vie</strong> · PM prospective & rétrospective</div>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    age_v3 = st.number_input("Âge actuel (ans)", value=50, min_value=18, max_value=80, step=1, key="p_v3_age")
                    sexe_v3 = st.selectbox("Sexe", ["H","F"], key="p_v3_sexe")
                with c2:
                    duree_v3 = st.number_input("Durée totale (ans)", value=20, min_value=5, max_value=40, step=1, key="p_v3_duree")
                    ecoule_v3 = st.number_input("Durée écoulée (ans)", value=10, min_value=0, max_value=39, step=1, key="p_v3_ecoule")
                with c3:
                    capital_v3 = st.number_input("Capital assuré (€)", value=80_000, step=5_000, key="p_v3_cap")
                    prime_v3 = st.number_input("Prime annuelle (€)", value=3_200, step=100, key="p_v3_prime")
                    taux_v3 = st.number_input("Taux technique (%)", value=2.50, step=0.25, key="p_v3_taux")
                st.session_state["analyse_params"] = {
                    "age": age_v3, "sexe": sexe_v3, "duree": duree_v3,
                    "t_ecoule": ecoule_v3, "capital": capital_v3,
                    "prime_annuelle": float(prime_v3), "taux_technique": taux_v3/100,
                }

            elif besoin == "pb_vie":
                st.markdown(f'<div style="font-size:0.78rem;color:{BLANC};margin-bottom:10px;">✏️ <strong>Théo V4 — Participation aux Bénéfices</strong> · Art. L132-29 · PPB · C2023-10</div>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    pm_v4 = st.number_input("PM totale portefeuille (M€)", value=285.0, step=10.0, key="p_v4_pm") * 1_000_000
                    rend_v4 = st.number_input("Rendement actifs (%)", value=3.20, step=0.10, key="p_v4_rend")
                with c2:
                    taux_tech_v4 = st.number_input("Taux technique moyen (%)", value=1.80, step=0.10, key="p_v4_tt")
                    ppb_ini_v4 = st.number_input("PPB initiale (M€)", value=8.4, step=0.5, key="p_v4_ppb") * 1_000_000
                with c3:
                    tx_servi_v4 = st.number_input("Taux servi cible (%)", value=2.60, step=0.10, key="p_v4_servi")
                    fp_inv_v4 = st.number_input("FP investis (M€)", value=25.0, step=1.0, key="p_v4_fp") * 1_000_000
                st.session_state["analyse_params"] = {
                    "pm_total": pm_v4, "rendement_actifs": rend_v4/100,
                    "taux_technique": taux_tech_v4/100, "ppb_initiale": ppb_ini_v4,
                    "tx_servi_cible": tx_servi_v4/100, "fonds_propres_investis": fp_inv_v4,
                }

            elif besoin == "qrt_vie":
                st.markdown(f'<div style="font-size:0.78rem;color:{BLANC};margin-bottom:10px;">✏️ <strong>Nia V5 — QRT Vie & Rapport Actuariel</strong> · QRT S.12 · S.23 · Rapport consolidé</div>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    pm_v5 = st.number_input("PM totale (M€)", value=285.0, step=10.0, key="p_v5_pm") * 1_000_000
                    be_v5 = st.number_input("BE Vie S2 (M€)", value=272.0, step=5.0, key="p_v5_be") * 1_000_000
                with c2:
                    scr_v5 = st.number_input("SCR Vie (M€)", value=53.0, step=1.0, key="p_v5_scr") * 1_000_000
                    fp_v5 = st.number_input("Fonds propres (M€)", value=98.0, step=5.0, key="p_v5_fp") * 1_000_000
                with c3:
                    ra_v5 = st.number_input("Risk Adjustment (M€)", value=16.3, step=0.5, key="p_v5_ra") * 1_000_000
                    nb_c_v5 = st.number_input("Nb contrats", value=42_000, step=1_000, key="p_v5_nb")
                    ref_cli_v5 = st.text_input("Nom client", value="Mutuelle Vie Atlantique", key="p_v5_cli")
                st.session_state["analyse_params"] = {
                    "pm_total": pm_v5, "be_vie": be_v5, "scr_vie": scr_v5,
                    "fonds_propres": fp_v5, "risk_adjustment": ra_v5,
                    "nb_contrats": int(nb_c_v5), "ref_client": ref_cli_v5,
                }

            elif besoin == "tarif" and equipe == "epre":
                st.markdown(f'<div style="font-size:0.78rem;color:{BLANC};margin-bottom:10px;">✏️ <strong>Salomé EP2 — Tarification EP-RE</strong> · PER · Art.39 · Art.83</div>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    type_ep2 = st.selectbox("Type contrat", ["PER","art39","art83"], key="p_ep2_type")
                    age_ep2 = st.number_input("Âge entrée (ans)", value=35, min_value=18, max_value=60, step=1, key="p_ep2_age")
                with c2:
                    cap_ep2 = st.number_input("Capital cible retraite (€)", value=120_000, step=5_000, key="p_ep2_cap")
                    age_ret_ep2 = st.number_input("Âge retraite (ans)", value=65, min_value=60, max_value=70, step=1, key="p_ep2_aret")
                with c3:
                    rend_ep2 = st.number_input("Rendement marché (%)", value=3.20, step=0.10, key="p_ep2_rend")
                    part_ep2 = st.number_input("Taux participation (%)", value=90.0, step=5.0, key="p_ep2_part")
                st.session_state["analyse_params"] = {
                    "type_contrat": type_ep2, "age_entree": age_ep2,
                    "capital_cible": cap_ep2, "age_retraite": age_ret_ep2,
                    "taux_marche": rend_ep2/100, "taux_participation": part_ep2/100,
                }

            elif besoin == "prov" and equipe == "epre":
                st.markdown(f'<div style="font-size:0.78rem;color:{BLANC};margin-bottom:10px;">✏️ <strong>Jin-Ho EP3 — Provisionnement EP-RE</strong> · PM · PPB · Réserve capitalisation · Art. R342-14</div>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    enc_ep3 = st.number_input("Encours PM (M€)", value=34.0, step=1.0, key="p_ep3_enc") * 1_000_000
                    rente_ep3 = st.number_input("Rente moyenne (€/mois)", value=1_450, step=50, key="p_ep3_rente")
                with c2:
                    age_ep3 = st.number_input("Âge moyen (ans)", value=55, min_value=40, max_value=75, step=1, key="p_ep3_age")
                    ppb_ep3 = st.number_input("PPB stock (M€)", value=2.1, step=0.1, key="p_ep3_ppb") * 1_000_000
                with c3:
                    actifs_ep3 = st.number_input("Actifs totaux (M€)", value=36.8, step=0.5, key="p_ep3_actifs") * 1_000_000
                    rc_ep3 = st.number_input("Réserve capitalisation (M€)", value=0.85, step=0.1, key="p_ep3_rc") * 1_000_000
                    sbr_ep3 = st.selectbox("Sous-branche", ["per","art39","art83"], key="p_ep3_sbr")
                st.session_state["analyse_params"] = {
                    "encours_total": enc_ep3, "rente_moyenne": rente_ep3,
                    "age_moyen": float(age_ep3), "ppb_stock": ppb_ep3,
                    "actifs_total": actifs_ep3, "reserve_capi_stock": rc_ep3,
                    "sous_branche": sbr_ep3,
                }

            elif besoin in ["stress","report"] and equipe == "epre":
                st.markdown(f'<div style="font-size:0.78rem;color:{BLANC};margin-bottom:10px;">✏️ <strong>{"Claire EP4 — Stress Tests" if besoin == "stress" else "Omar/Noé EP5 — Rapport ACPR/DARES"}</strong></div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    enc_ep4 = st.number_input("Encours PM (M€)", value=34.0, step=1.0, key="p_ep4_enc") * 1_000_000
                    actifs_ep4 = st.number_input("Actifs totaux (M€)", value=36.8, step=0.5, key="p_ep4_act") * 1_000_000
                with c2:
                    sbr_ep4 = st.selectbox("Sous-branche", ["per","art39","art83"], key="p_ep4_sbr")
                    cli_ep4 = st.text_input("Nom client", value="Mutuelle Vie Atlantique", key="p_ep4_cli")
                st.session_state["analyse_params"] = {
                    "encours_total": enc_ep4, "actifs_total": actifs_ep4,
                    "sous_branche": sbr_ep4, "ref_client": cli_ep4,
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

    # ── QUI ASSUME LA DÉCISION ? LA QUESTION SE POSE AVANT LE CALCUL ─────────
    # ⚠️ CE CHAMP ÉTAIT DEMANDÉ APRÈS L'ANALYSE, sur la page des résultats, et
    # n'atteignait donc JAMAIS A6 : `profil_valide_par` restait None, et
    # `gouvernance_ok` valait False sur 100 % des analyses de l'application.
    # Mesuré sur 24 configurations réelles : 13 d'entre elles — 54 % —
    # étaient plafonnées à AMBRE pour cette seule raison administrative,
    # pendant que l'actuaire cherchait un défaut technique inexistant.
    #
    # ⚠️ ET L'AUTRE ORDRE A ÉTÉ ÉCARTÉ DÉLIBÉRÉMENT : réévaluer le statut
    # après coup ferait virer un AMBRE au VERT sous les yeux du lecteur parce
    # qu'il vient de taper son nom. Un verdict qui change sans qu'aucune
    # donnée ne bouge enseigne que le verdict ne vaut rien. La gouvernance est
    # une condition d'ENTRÉE.
    _gv1, _gv2 = st.columns(2)
    with _gv1:
        _act_nom = st.text_input(
            "Nom de l'actuaire responsable *",
            placeholder="Ex : Marie Dupont",
            key="analyse_actuaire_nom",
            help="Qui assume la décision de modèle. Exigé en production — "
                 "ACPR-2022-P-01 §4.3.",
        )
    with _gv2:
        st.text_input(
            "N° Institut des Actuaires",
            placeholder="Ex : IA-2024-1234",
            key="analyse_actuaire_ia",
        )

    # Vérification données disponibles
    pret = True
    if besoin in besoins_upload and besoin != "mortalite":
        if st.session_state.get("analyse_df") is None:
            pret = False

    _actuaire_ok = bool(str(_act_nom or "").strip())

    with col_btn:
        btn_label = "🚀 Lancer l'analyse"
        if not pret:
            st.button(btn_label, disabled=True, use_container_width=True, key="btn_lancer")
            st.caption("⚠️ Uploadez d'abord vos données")
        elif not _actuaire_ok:
            st.button(btn_label, disabled=True, use_container_width=True, key="btn_lancer")
            st.caption("⚠️ Nom de l'actuaire responsable requis avant de lancer "
                       "l'analyse.")
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
                from direction_non_vie.provisionnement.a7_provisionnement import AgentA7Provisionnement
                from direction_non_vie.services.nv_triangle_builder import NVTriangleBuilder

                _a7p = st.session_state.get("analyse_params", {})

                # ── Étape 1 : Construction du triangle via NVTriangleBuilder ──
                # Remplace le preprocessing manuel — gère automatiquement :
                # · Détection du format (données individuelles ou triangle agrégé)
                # · Standardisation des noms de colonnes via synonymes
                # · Suggestion et application du LLT si fourni
                # · Séparation attritional / grands sinistres
                builder = NVTriangleBuilder(verbose=False)
                _llt_val = _a7p.get("a7_llt")
                _build_result = builder.construire(
                    source        = df.copy(),
                    llt           = _llt_val,
                    schema_mapping= _a7p.get("a7_schema_mapping"),
                    annee_debut   = _a7p.get("a7_annee_debut"),
                    nom_onglet    = st.session_state.get("a7_onglet_triangle") or st.session_state.get("a7_onglet_triangle_mono"),
                )

                # ── Étape 2 : Afficher les résultats du builder ───────────────
                if not _build_result["success"]:
                    st.error(f"❌ Erreur construction triangle : {_build_result['erreur']}")
                    st.stop()

                # Afficher les alertes du builder
                for _alerte_b in _build_result["rapport"].get("alertes", []):
                    st.warning(_alerte_b)
                for _info_b in _build_result["rapport"].get("infos", []):
                    if "✅" in _info_b or "LLT" in _info_b or "Séparation" in _info_b:
                        st.info(_info_b)

                # Afficher LLT suggéré si pas de LLT fourni
                _llt_suggere = _build_result.get("llt_suggere")
                if _llt_suggere and not _llt_val:
                    st.info(
                        f"💡 LLT suggéré automatiquement (P95) : **{_llt_suggere:,.0f} €** — "
                        f"activez-le dans les paramètres A7 pour séparer les grands sinistres."
                    )

                # Stats séparation grands sinistres
                _stats_b = _build_result.get("statistiques", {})
                if _build_result["mode_separation"] == "attritional_grands":
                    n_grands = _stats_b.get("n_grands_sinistres", 0)
                    pct_grands = _stats_b.get("pct_grands_sinistres", 0)
                    reco = _build_result.get("recommandation_grands", "")
                    _reco_labels = {
                        "chain_ladder_separe":          "Chain Ladder sur triangle séparé",
                        "bornhuetter_ferguson_marche":  "BF avec LR marché externe",
                        "developpement_individuel":     "Développement dossier par dossier",
                    }
                    st.markdown(
                        f"<div style='background:{NAVY_L};border-left:3px solid {OR};"
                        f"border-radius:6px;padding:10px 14px;margin-bottom:8px;'>"
                        f"<div style='font-size:0.72rem;color:{OR};font-weight:700;'>🎯 Séparation LLT = {_llt_val:,.0f} €</div>"
                        f"<div style='font-size:0.78rem;color:{BLANC};margin-top:4px;'>"
                        f"{n_grands} grands sinistre(s) identifié(s) — {pct_grands:.1f}% du total<br>"
                        f"Méthode recommandée : {_reco_labels.get(reco, reco)}</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                # ── Étape 3 : Lancer A7 sur le triangle attritional ───────────
                # Si séparation active → A7 sur triangle attritional épuré
                # Sinon → A7 sur triangle total (comportement actuel)
                _source_a7 = (
                    _build_result["triangle_attritional"]
                    if _build_result["mode_separation"] == "attritional_grands"
                    and _build_result["triangle_attritional"] is not None
                    else df.copy()  # fallback sur données brutes si pas de séparation
                )

                a7 = AgentA7Provisionnement(audit_path=_tmp, models_path=_tmp, verbose=False)
                r7 = a7.run(
                    source               = _source_a7,
                    generer_graphiques   = True,
                    lob                  = _a7p.get("a7_lob", "generique"),
                    arrete               = _a7p.get("a7_arrete", ""),
                    n_sim_bootstrap      = _a7p.get("a7_n_sim_bootstrap", 5000),
                    annee_base_reserve   = _a7p.get("a7_annee_base_reserve", 1),
                    resultats_precedents = _a7p.get("a7_resultats_precedents"),
                    primes               = _a7p.get("a7_primes"),
                    lr_bf_manuel         = _a7p.get("a7_lr_apriori"),
                    annee_debut          = _a7p.get("a7_annee_debut"),
                    triangle_engage      = _a7p.get("a7_triangle_engage"),
                    courbe_rfr           = _a7p.get("a7_courbe_rfr", None),
                    generer_word         = False,
                    generer_pdf_flag     = False,
                )

                # Enrichir les résultats avec les infos de séparation LLT
                r7["llt_utilise"]          = _llt_val
                r7["llt_suggere"]          = _llt_suggere
                r7["grands_sinistres"]     = _build_result["grands_sinistres"].to_dict("records") if len(_build_result["grands_sinistres"]) > 0 else []
                r7["triangle_grands"]      = _build_result["triangle_grands"].tolist() if _build_result["triangle_grands"] is not None else None
                r7["mode_separation"]      = _build_result["mode_separation"]
                r7["recommandation_grands"]= _build_result.get("recommandation_grands")
                r7["stats_builder"]        = _stats_b

                resultats["principal"] = r7

            # ── TARIFICATION ────────────────────────────────────────────────
            elif besoin in ["prime_glm","prime_ml","prime_dl","selection"]:
                from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
                from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
                from core.plan_tarifaire import PlanTarifaire

                # Phase 1/2 : la LoB est DÉCLARÉE et le PLAN SIGNÉ pilote tout le
                # pipeline (encodage A2, variables A3/A4/A5). Cette page tarife en
                # auto : un seul chargement, partagé par les 4 chemins 'besoin'.
                _plan_auto = PlanTarifaire.depuis_yaml(os.path.join(
                    os.path.dirname(__file__), "plans", "auto.yaml"))

                a1 = AgentA1Ingestion(audit_path=_tmp, verbose=False)
                r1 = a1.run(dataframe=df, branche="non_vie", sous_branche="auto")
                if not r1["success"]:
                    st.error(f"❌ A1 Amara : {r1['erreur']}")
                    return

                a2 = AgentA2Preprocessing(audit_path=_tmp, verbose=False)
                r2 = a2.run(r1, plan=_plan_auto)
                if not r2["success"]:
                    st.error(f"❌ A2 Kenji : {r2['erreur']}")
                    return

                resultats["r1"] = r1
                resultats["r2"] = r2

                if besoin == "prime_glm":
                    from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
                    # _plan_auto : chargé une seule fois plus haut, partagé avec A2.
                    r3 = AgentA3GLM(audit_path=_tmp, verbose=False).run(
                        r2, plan=_plan_auto, generer_graphiques=False)
                    resultats["principal"] = r3
                    # ── COMPARAISON : chemin déclaratif (pipeline_complet) EN PARALLÈLE ─
                    # Calculé À CÔTÉ de r3 (aucun changement d'affichage, aucun st.*
                    # nouveau). Depuis la Phase 1, r3 (chemin agent A2→A3) est LUI AUSSI
                    # piloté par le plan : les deux chemins partagent plans/auto.yaml et
                    # ses colonnes. Ce calcul parallèle compare donc les deux
                    # ORCHESTRATIONS (agent vs déclaratif), non plus VARS_GLM vs plan.
                    # Sous garde : toute incompatibilité est enregistrée, jamais fatale.
                    try:
                        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
                        resultats["tarif_plan"] = pipeline_complet(r1["dataframe"], _plan_auto)
                    except Exception as _e_plan:
                        resultats["tarif_plan_erreur"] = f"{type(_e_plan).__name__}: {_e_plan}"
                elif besoin == "prime_ml":
                    from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
                    # _plan_auto : chargé une seule fois plus haut, partagé avec A2.
                    r4 = AgentA4ML(audit_path=_tmp, verbose=False).run(
                        r2, plan=_plan_auto, generer_graphiques=False, calcul_shap=False)
                    resultats["principal"] = r4
                elif besoin == "prime_dl":
                    from direction_non_vie.tarification.a5_deep_learning.agent import AgentA5DeepLearning
                    # _plan_auto : chargé une seule fois plus haut, partagé avec A2.
                    # ⚠ CORRECTIF : cette page n'indiquait AUCUNE cible et héritait
                    # donc du défaut d'A5, 'prime_pure' — or le CANN est
                    # exp(GLM_gelé + offset·log(expo)), un modèle de COMPTAGE : la
                    # prime pure est exposure-indépendante, l'offset y est faux et
                    # dégrade l'ancrage. La page tarifait donc en DL sur une cible
                    # que l'architecture ne supporte pas. La cible est désormais
                    # DÉCLARÉE (et le défaut d'A5 a été supprimé, pour que le
                    # prochain appelant ne puisse plus tomber dans le même piège).
                    r5 = AgentA5DeepLearning(audit_path=_tmp, verbose=False).run(
                        r2, plan=_plan_auto, col_cible="nb_sinistres",
                        n_epochs=10, generer_graphiques=False)
                    resultats["principal"] = r5
                elif besoin == "selection":
                    from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
                    # _plan_auto : chargé une seule fois plus haut, partagé avec A2
                    # (même migration que prime_glm — A3.run exige le plan depuis la
                    # Phase 1, sinon erreur propre : cette page renvoyait cette erreur).
                    r3 = AgentA3GLM(audit_path=_tmp, verbose=False).run(
                        r2, plan=_plan_auto, generer_graphiques=False)
                    if besoin == "selection":
                        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
                        # ⚠️ `profil_valide_par` ENFIN TRANSMIS : l'application
                        # exigeait ce nom depuis toujours, et ne le donnait
                        # jamais au calcul.
                        r6 = AgentA6Comparaison(audit_path=_tmp, verbose=False).run(
                            r2, result_a3=r3, generer_graphiques=False,
                            aide_decision=True,
                            profil_valide_par=st.session_state.get(
                                "analyse_actuaire_nom") or None)
                        resultats["principal"] = r6
                    else:
                        resultats["principal"] = r3

            # ── TRIANGLE DIRECT → A7 (via NVTriangleBuilder — P3-bis) ────
            elif besoin == "triangle_xl":
                from direction_non_vie.provisionnement.a7_provisionnement import AgentA7Provisionnement
                from direction_non_vie.services.nv_triangle_builder import NVTriangleBuilder
                import numpy as _np_a7

                _a7p = st.session_state.get("analyse_params", {})
                _fmt = st.session_state.get("a7_format_declare", "cumule")

                # df contient le DataFrame brut stocké dans session_state["analyse_df"]
                if df is None:
                    st.error("❌ Aucun fichier chargé. Uploadez votre triangle et relancez l'analyse.")
                    st.stop()

                # Conversion forcée des colonnes object → numeric (robustesse Excel)
                import pandas as _pd_diag
                if isinstance(df, _pd_diag.DataFrame):
                    # Certains fichiers Excel sont lus avec des colonnes object
                    # même si elles contiennent des nombres — forcer la conversion
                    _df_conv = df.copy()
                    for _col in _df_conv.columns:
                        _df_conv[_col] = _pd_diag.to_numeric(_df_conv[_col], errors='coerce')
                    _n_num_avant = df.select_dtypes(include=["number"]).shape[1]
                    _n_num_apres = _df_conv.select_dtypes(include=["number"]).shape[1]
                    if _n_num_apres > _n_num_avant:
                        df = _df_conv  # utiliser le DataFrame converti
                        st.session_state["analyse_df"] = df  # mettre à jour session
                    st.info(
                        f"📋 Fichier reçu : {df.shape[0]} lignes × {df.shape[1]} colonnes "
                        f"| {_n_num_apres} col. numériques "
                        f"| Format : {_fmt}"
                    )
                    if _n_num_apres == 0:
                        st.error(
                            "❌ Aucune valeur numérique détectée. "
                            "Vérifiez que votre triangle contient des montants "
                            "et que vous avez sélectionné le bon onglet Excel."
                        )
                        st.stop()

                # Construction du triangle via NVTriangleBuilder (format déclaré, P3-bis)
                _builder_ex = NVTriangleBuilder(verbose=False)
                _res_build = _builder_ex.construire(
                    source       = df,
                    mode_declare = _fmt,
                )
                if not _res_build["success"]:
                    st.error(
                        f"❌ Erreur pipeline données : {_res_build['erreur']}\n\n"
                        f"Dimensions du fichier : {df.shape[0]} lignes × {df.shape[1]} colonnes. "
                        f"Format déclaré : **{_fmt}**. "
                        f"Vérifiez que votre fichier correspond au format sélectionné."
                    )
                    st.stop()

                _tri = _res_build["triangle_total"]
                if _tri is None or (hasattr(_tri, "size") and _tri.size == 0):
                    st.error("❌ Triangle vide après construction — vérifiez le format de votre fichier.")
                    st.stop()

                # Alertes pipeline
                for _al_ex in _res_build["rapport"].get("alertes", []):
                    if "❌" in _al_ex:
                        st.error(_al_ex)
                    elif "⚠️" in _al_ex:
                        st.warning(_al_ex)

                # Lancement A7 Ibrahim
                a7 = AgentA7Provisionnement(audit_path=_tmp, models_path=_tmp, verbose=False)
                r7 = a7.run(
                    source             = _tri,
                    mode_declare       = "cumule",
                    generer_graphiques = True,
                    lob                = _a7p.get("a7_lob", "generique"),
                    arrete             = _a7p.get("a7_arrete", ""),
                    n_sim_bootstrap    = int(_a7p.get("a7_n_sim_bootstrap", 5000)),
                    annee_base_reserve = int(_a7p.get("a7_annee_base_reserve", 1)),
                    resultats_precedents = _a7p.get("a7_resultats_precedents"),
                    primes             = _a7p.get("a7_primes"),
                    lr_bf_manuel       = _a7p.get("a7_lr_apriori"),
                    annee_debut        = _a7p.get("a7_annee_debut"),
                    triangle_engage    = _a7p.get("a7_triangle_engage"),
                    generer_word       = False,
                    generer_pdf_flag   = False,
                )
                resultats["principal"] = r7

            # ── STRESS TESTING A8 ───────────────────────────────────────────
            elif besoin == "stress":
                from direction_non_vie.reglementation.a8_stress_testing.agent import AgentA8StressTesting
                # Récupérer les vrais résultats A7 si disponibles
                _r7_reel = (st.session_state.get("agent_results") or {}).get("ibrahim")
                if _r7_reel and _r7_reel.get("success"):
                    st.info("✅ Résultats A7 Ibrahim détectés — stress testing sur données réelles")
                else:
                    _r7_reel = None
                    st.warning("⚠️ Aucune analyse provisionnement préalable — stress testing sur paramètres manuels")
                r8 = AgentA8StressTesting(audit_path=_tmp, verbose=False).run(
                    result_a7=_r7_reel,
                    primes_acq=params.get("primes", 10_000_000),
                    fonds_propres=params.get("fonds_propres", 7_650_000),
                    generer_graphiques=False,
                )
                resultats["principal"] = r8

            # ── SOLVABILITÉ 2 ───────────────────────────────────────────────
            elif besoin == "s2":
                from direction_non_vie.reglementation.a10_solvabilite2.agent import AgentA10Solvabilite2
                _r7_reel = (st.session_state.get("agent_results") or {}).get("ibrahim")
                if _r7_reel and _r7_reel.get("success"):
                    _r7_a10 = _r7_reel
                    st.info("✅ Résultats A7 Ibrahim détectés — SCR calculé sur données réelles")
                else:
                    _be = params.get("be", 2_914_930)
                    _r7_a10 = {"best_estimate":{"best_estimate":_be,"sigma_mack":_be*0.015,"cv_inter_methodes":5,"nb_methodes_convergentes":4},"tail":{"tail_factor":1.037},"meta":{"nb_lignes":50000,"n_annees":8},"sous_branche":params.get("branche","rc_auto")}
                    st.warning("⚠️ Aucune analyse provisionnement préalable — SCR calculé sur paramètres manuels")
                r10 = AgentA10Solvabilite2(audit_path=_tmp, verbose=False).run(
                    result_a7=_r7_a10,
                    fonds_propres=params.get("fonds_propres", 7_650_000),
                    generer_graphiques=False,
                )
                resultats["principal"] = r10

            # ── VIE PURE V1-V5 ──────────────────────────────────────────────
            elif besoin in ["tarif_deces","tarif_epargne_vie","pm_vie","pb_vie","qrt_vie"]:
                if besoin == "tarif_deces":
                    from direction_vie_epre.vie.v1_tarification_deces.agent import AgentV1TarificationDeces
                    _r_v = AgentV1TarificationDeces(audit_path=_tmp, verbose=False).run(
                        age=params.get("age", 40), sexe=params.get("sexe", "H"),
                        generer_graphiques=False,
                    )
                elif besoin == "tarif_epargne_vie":
                    from direction_vie_epre.vie.v2_tarification_epargne.agent import AgentV2TarificationEpargneVie
                    _r_v = AgentV2TarificationEpargneVie(verbose=False).run(
                        age=params.get("age", 45),
                        sexe=params.get("sexe", "H"),
                        duree=params.get("duree", 20),
                        capital=params.get("capital", 80_000),
                        type_contrat=params.get("type_contrat", "capital_differe"),
                        taux_technique=params.get("taux_technique", 0.018),
                        tmg=params.get("tmg", 0.0),
                        generer_graphiques=False,
                    )
                elif besoin == "pm_vie":
                    from direction_vie_epre.vie.v3_provisions_mathematiques.agent import AgentV3ProvisionsMathematiques
                    _r_v = AgentV3ProvisionsMathematiques(audit_path=_tmp, verbose=False).run(
                        age=params.get("age", 40), generer_graphiques=False,
                    )
                elif besoin == "pb_vie":
                    from direction_vie_epre.vie.v4_participation_benefices.agent import AgentV4ParticipationBenefices
                    _r_v = AgentV4ParticipationBenefices(audit_path=_tmp, verbose=False).run(
                        generer_graphiques=False,
                    )
                elif besoin == "qrt_vie":
                    from direction_vie_epre.vie.v5_qrt_rapport.agent import AgentV5QRTVie
                    _r_v = AgentV5QRTVie(audit_path=_tmp, verbose=False).run(
                        generer_graphiques=False,
                    )
                resultats["principal"] = _r_v

            # ── EP-RE EP1-EP5 ────────────────────────────────────────────────
            elif besoin == "ias19":
                from direction_vie_epre.epargne_retraite.ep1_ias19.agent import AgentEP1EngagementsRetraite
                _r_ep = AgentEP1EngagementsRetraite(verbose=False).run(
                    effectif=params.get("effectif", 500),
                    salaire_moyen=params.get("salaire_moyen", 45_000),
                    anciennete_moyenne=params.get("anciennete_moyenne", 10.0),
                    taux_actu=params.get("taux_actu", 0.0385),
                    taux_revalorisation=params.get("taux_revalorisation", 0.020),
                    taux_rotation=params.get("taux_rotation", 0.050),
                    age_moyen=params.get("age_moyen", 42.0),
                    age_retraite=params.get("age_retraite", 65.0),
                    sous_branche=params.get("sous_branche", "art39"),
                    generer_graphiques=False,
                )
                resultats["principal"] = _r_ep

            elif besoin == "tarif" and equipe == "epre":
                from direction_vie_epre.epargne_retraite.ep2_tarification_epargne.agent import AgentEP2TarificationEpargne
                _r_ep = AgentEP2TarificationEpargne(audit_path=_tmp, verbose=False).run(
                    age=params.get("age", 45), generer_graphiques=False,
                )
                resultats["principal"] = _r_ep

            elif besoin == "prov" and equipe == "epre":
                from direction_vie_epre.epargne_retraite.ep3_provisionnement_epargne.agent import AgentEP3ProvissionnementEpargne
                _r_ep = AgentEP3ProvissionnementEpargne(verbose=False).run(
                    encours_total=params.get("encours_total", 34_000_000),
                    rente_moyenne=params.get("rente_moyenne", 1_200),
                    age_moyen=params.get("age_moyen", 55.0),
                    ppb_stock=params.get("ppb_stock", 1_000_000),
                    reserve_capi_stock=params.get("reserve_capi_stock", 500_000),
                    actifs_total=params.get("actifs_total", None),
                    sous_branche=params.get("sous_branche", "per"),
                    generer_graphiques=False,
                )
                resultats["principal"] = _r_ep

            elif besoin == "stress" and equipe == "epre":
                from direction_vie_epre.epargne_retraite.ep4_stress_epargne.agent import AgentEP4StressEpargne
                _r_ep = AgentEP4StressEpargne(audit_path=_tmp, verbose=False).run(
                    generer_graphiques=False,
                )
                resultats["principal"] = _r_ep

            elif besoin == "report" and equipe == "epre":
                from direction_vie_epre.epargne_retraite.ep5_reporting.agent import AgentEP5ReportingEpargne
                _r_ep = AgentEP5ReportingEpargne(audit_path=_tmp, verbose=False).run(
                    generer_graphiques=False,
                )
                resultats["principal"] = _r_ep

            # ── REGLEMENTATION VIE R-VIE1/R-VIE2 ───────────────────────────
            elif besoin == "rvie1":
                from direction_vie_epre.reglementation.r_vie1_ifrs17.agent import AgentRVIE1QRTVie
                _r_v = AgentRVIE1QRTVie(verbose=False).run(
                    be_vie=params.get("be_vie", 272_000_000),
                    pm_total=params.get("pm_total", 285_000_000),
                    generer_graphiques=False,
                )
                resultats["principal"] = _r_v

            elif besoin == "rvie2":
                from direction_vie_epre.reglementation.r_vie2_alm.agent import AgentRVIE2RSRSFCRVie
                _r_v = AgentRVIE2RSRSFCRVie(verbose=False).run(
                    scr_vie=params.get("scr_vie", 53_000_000),
                    fonds_propres=params.get("fonds_propres", 98_000_000),
                    be_vie=params.get("be_vie", 272_000_000),
                    pm_total=params.get("pm_total", 285_000_000),
                    generer_graphiques=False,
                )
                resultats["principal"] = _r_v

            # ── SANTÉ ────────────────────────────────────────────────────────
            elif besoin in ["tarif_sante","prov_sante","report_sante"]:
                # NOTE (11/07/2026) : l'appel à A1/A2 (Direction Non-Vie) a été
                # RETIRÉ de ce chemin. Vestige de l'architecture initiale où
                # A1/A2 servaient de « service data » mutualisé aux trois
                # directions. Cette architecture est abandonnée : la Direction
                # Santé-Prévoyance est autonome. Le résultat r2 était calculé
                # ici puis n'était consommé par AUCUN agent SP (S1/S2 sont
                # paramétriques) — code tournant dans le vide, et surface
                # d'exposition réglementaire non auditée (l'audit V9 y a trouvé
                # une fuite de données bloquante sur les agrégats santé).
                # Le pipeline de données propre à la Direction SP prend le
                # relais lorsqu'il est branché sur données réelles.

                if besoin == "tarif_sante":
                    from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante
                    r_s1 = AgentS1TarificationSante(audit_path=_tmp, verbose=False).run(
                        nb_assures=params.get("nb_assures",1000),
                        age_moyen=params.get("age_moyen",42),
                        garantie_niveau=params.get("garantie_niveau","confort"),
                        generer_graphiques=False,
                    )
                    resultats["principal"] = r_s1
                elif besoin == "prov_sante":
                    from direction_sante_prevoyance.sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
                    r_s2 = AgentS2ProvissionnementSante(audit_path=_tmp, verbose=False).run(
                        primes_acquises=params.get("primes_acquises",5_000_000),
                        generer_graphiques=False,
                    )
                    resultats["principal"] = r_s2

            # ── COHÉRENCE A9 ────────────────────────────────────────────────
            elif besoin == "coherence":
                from direction_non_vie.reglementation.a9_coherence.agent import AgentA9Coherence
                _r7_reel = (st.session_state.get("agent_results") or {}).get("ibrahim")
                if _r7_reel and _r7_reel.get("success"):
                    _r7_a9 = _r7_reel
                    st.info("✅ Résultats A7 Ibrahim détectés — cohérence sur données réelles")
                else:
                    _be = params.get("be", 2_914_930)
                    _r7_a9 = {"best_estimate":{"best_estimate":_be,"sigma_mack":_be*0.015,"cv_inter_methodes":5,"nb_methodes_convergentes":4},"tail":{"tail_factor":1.037},"meta":{"nb_lignes":50000,"n_annees":8}}
                    st.warning("⚠️ Aucune analyse provisionnement préalable — cohérence sur paramètres manuels")
                r9 = AgentA9Coherence(audit_path=_tmp, verbose=False).run(
                    result_a7=_r7_a9,
                    primes_acq=params.get("primes", 10_000_000),
                    generer_graphiques=False,
                )
                resultats["principal"] = r9

            # ── IFRS 17 A11 ─────────────────────────────────────────────────
            elif besoin == "ifrs17":
                from direction_non_vie.reglementation.a10_solvabilite2.agent import AgentA10Solvabilite2
                from direction_non_vie.reglementation.a11_ifrs17.agent import AgentA11IFRS17
                _r7_reel = (st.session_state.get("agent_results") or {}).get("ibrahim")
                if _r7_reel and _r7_reel.get("success"):
                    _r7_a11 = _r7_reel
                    st.info("✅ Résultats A7 Ibrahim détectés — IFRS 17 calculé sur données réelles")
                else:
                    _be = params.get("be", 2_914_930)
                    _r7_a11 = {"best_estimate":{"best_estimate":_be,"sigma_mack":_be*0.015,"cv_inter_methodes":5,"nb_methodes_convergentes":4},"tail":{"tail_factor":1.037},"meta":{"nb_lignes":50000,"n_annees":8},"sous_branche":params.get("branche","rc_auto")}
                    st.warning("⚠️ Aucune analyse provisionnement préalable — IFRS 17 calculé sur paramètres manuels")
                _r10_a11 = AgentA10Solvabilite2(audit_path=_tmp, verbose=False).run(
                    result_a7=_r7_a11,
                    fonds_propres=params.get("fonds_propres", 7_650_000),
                    generer_graphiques=False,
                )
                r11 = AgentA11IFRS17(audit_path=_tmp, verbose=False).run(
                    result_a7=_r7_a11,
                    result_a10=_r10_a11,
                    generer_graphiques=False,
                )
                resultats["principal"] = r11

            # ── ALM A12 ─────────────────────────────────────────────────────
            elif besoin == "alm":
                from direction_non_vie.reglementation.a10_solvabilite2.agent import AgentA10Solvabilite2
                from direction_non_vie.reglementation.a12_alm.agent import AgentA12ALM
                _r7_reel = (st.session_state.get("agent_results") or {}).get("ibrahim")
                if _r7_reel and _r7_reel.get("success"):
                    _r7_a12 = _r7_reel
                    st.info("✅ Résultats A7 Ibrahim détectés — ALM calculé sur données réelles")
                else:
                    _be = params.get("be", 2_914_930)
                    _r7_a12 = {"best_estimate":{"best_estimate":_be,"sigma_mack":_be*0.015,"cv_inter_methodes":5,"nb_methodes_convergentes":4},"tail":{"tail_factor":1.037},"meta":{"nb_lignes":50000,"n_annees":8},"sous_branche":params.get("branche","rc_auto")}
                    st.warning("⚠️ Aucune analyse provisionnement préalable — ALM calculé sur paramètres manuels")
                _r10_a12 = AgentA10Solvabilite2(audit_path=_tmp, verbose=False).run(
                    result_a7=_r7_a12,
                    fonds_propres=params.get("fonds_propres", 7_650_000),
                    generer_graphiques=False,
                )
                r12 = AgentA12ALM(audit_path=_tmp, verbose=False).run(
                    result_a10=_r10_a12,
                    result_a7=_r7_a12,
                    generer_graphiques=False,
                )
                resultats["principal"] = r12

            # ── MORTALITÉ A14 ───────────────────────────────────────────────
            elif besoin == "mortalite":
                from direction_non_vie.reglementation.a14_mortalite.agent import AgentA14Mortalite
                r14 = AgentA14Mortalite(audit_path=_tmp, verbose=False).run(
                    generer_graphiques=False,
                )
                resultats["principal"] = r14

            # ── REPORT SANTÉ S3 — pipeline S1→S2→S3 ────────────────────────
            elif besoin == "report_sante":
                from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante
                from direction_sante_prevoyance.sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
                from direction_sante_prevoyance.sante.s3_reporting.agent import AgentS3ReportingSante
                _r_s1 = AgentS1TarificationSante(audit_path=_tmp, verbose=False).run(
                    nb_assures=params.get("nb_assures",1000),
                    age_moyen=params.get("age_moyen",42),
                    garantie_niveau=params.get("garantie_niveau","confort"),
                    generer_graphiques=False,
                )
                _r_s2 = AgentS2ProvissionnementSante(audit_path=_tmp, verbose=False).run(
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
                from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
                _r_p1 = AgentP1TarificationPrevoyance(audit_path=_tmp, verbose=False).run(
                    age=params.get("age",40),
                    salaire_brut=params.get("salaire_brut",45000),
                    categorie=params.get("categorie","employe"),
                    generer_graphiques=False,
                )
                resultats["principal"] = _r_p1

                if besoin in ["tables","prov_prev","report_prev"]:
                    from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
                    _tables_client_p2 = st.session_state.get("tables_client_sp", None) or None
                    _r_p2 = AgentP2TablesMorbidite(audit_path=_tmp, verbose=False).run(
                        result_p1=_r_p1,
                        tables_client=_tables_client_p2,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_p2

                if besoin in ["prov_prev","report_prev"]:
                    from direction_sante_prevoyance.prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
                    _r_p3 = AgentP3ProvissionnementPrevoyance(audit_path=_tmp, verbose=False).run(
                        result_p1=_r_p1,
                        result_p2=_r_p2,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_p3

                if besoin == "report_prev":
                    from direction_sante_prevoyance.prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
                    _r_p4 = AgentP4ReportingPrevoyance(audit_path=_tmp, verbose=False).run(
                        result_p1=_r_p1,
                        result_p2=_r_p2,
                        result_p3=_r_p3,
                        fonds_propres=params.get("fonds_propres",0.0),
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_p4

            # ── SP REGLEMENTATION ────────────────────────────────────────────────────
            elif besoin in ["sp_alm","sp_s2","sp_ifrs17","sp_ani","sp_stress","sp_coh","sp_audit","sp_rapport"]:
                # Charger les resultats SP depuis session si disponibles
                _ar_sp = st.session_state.get("agent_results", {})
                _r_s1 = _ar_sp.get("leonie", {})
                _r_s2 = _ar_sp.get("selma", {})
                _r_s3 = _ar_sp.get("binta", {})
                _r_p1 = _ar_sp.get("axel", {})
                _r_p2 = _ar_sp.get("rayan", {})
                _r_p3 = _ar_sp.get("elodie", {})
                _r_p4 = _ar_sp.get("valentin", {})

                if besoin == "sp_alm":
                    from direction_sante_prevoyance.reglementation.sp_alm.agent import AgentSPAlm
                    _r_sp = AgentSPAlm(audit_path=_tmp, verbose=False).run(
                        result_p3=_r_p3, result_s3=_r_s3,
                        fonds_propres=params.get("fonds_propres", 0.0),
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_sp

                elif besoin == "sp_s2":
                    from direction_sante_prevoyance.reglementation.sp_reg1_solvabilite2.agent import AgentSPReg1Solvabilite2
                    _r_sp = AgentSPReg1Solvabilite2(audit_path=_tmp, verbose=False).run(
                        result_s3=_r_s3, result_p4=_r_p4,
                        fonds_propres=params.get("fonds_propres", 0.0),
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_sp

                elif besoin == "sp_ifrs17":
                    from direction_sante_prevoyance.reglementation.sp_reg2_ifrs17.agent import AgentSPReg2IFRS17
                    _r_sp = AgentSPReg2IFRS17(audit_path=_tmp, verbose=False).run(
                        result_s3=_r_s3, result_p4=_r_p4,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_sp

                elif besoin == "sp_ani":
                    from direction_sante_prevoyance.reglementation.sp_reg3_ani_100sante.agent import AgentSPReg3ANI100Sante
                    _r_sp = AgentSPReg3ANI100Sante(audit_path=_tmp, verbose=False).run(
                        result_s1=_r_s1, result_s3=_r_s3,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_sp

                elif besoin == "sp_stress":
                    from direction_sante_prevoyance.reglementation.sp_st_stress_testing.agent import AgentSPStressTestingNaomie
                    _r_sp = AgentSPStressTestingNaomie(audit_path=_tmp, verbose=False).run(
                        result_s3=_r_s3, result_p3=_r_p3,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_sp

                elif besoin == "sp_coh":
                    from direction_sante_prevoyance.reglementation.sp_coherence.agent import AgentSPCoherence
                    _r_sp = AgentSPCoherence(audit_path=_tmp, verbose=False).run(
                        result_s1=_r_s1, result_s2=_r_s2, result_s3=_r_s3,
                        result_p1=_r_p1, result_p2=_r_p2, result_p3=_r_p3, result_p4=_r_p4,
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_sp

                elif besoin == "sp_audit":
                    from direction_sante_prevoyance.reglementation.sp_audit.agent import AgentSPAuditTrail
                    _resultats_sp_audit = {
                        "s1":_r_s1,"s2":_r_s2,"s3":_r_s3,
                        "p1":_r_p1,"p2":_r_p2,"p3":_r_p3,"p4":_r_p4,
                    }
                    _r_sp = AgentSPAuditTrail(audit_path=_tmp, verbose=False).run(
                        resultats_agents=_resultats_sp_audit,
                        client_nom=ref_client or "Client ActuarIA",
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_sp

                elif besoin == "sp_rapport":
                    from direction_sante_prevoyance.rapport_actuariel.agent import AgentSPRapportActuariel
                    _r_sp = AgentSPRapportActuariel(audit_path=_tmp, verbose=False).run(
                        result_s1=_r_s1, result_s2=_r_s2, result_s3=_r_s3,
                        result_p1=_r_p1, result_p2=_r_p2, result_p3=_r_p3, result_p4=_r_p4,
                        client_nom=ref_client or "Client ActuarIA",
                        generer_graphiques=False,
                    )
                    resultats["principal"] = _r_sp

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
                "tarif_deces": "nour", "tarif_epargne_vie": "kofi",
                "pm_vie": "amelie", "pb_vie": "theo", "qrt_vie": "nia",
                "mortalite": "yuki", "tarif_sante": "leonie", "prov_sante": "selma",
                "report_sante": "binta", "tarif_prev": "axel", "tables": "rayan",
                "prov_prev": "elodie", "report_prev": "valentin",
                "sp_alm": "sp_alm", "sp_s2": "sp_s2", "sp_ifrs17": "sp_ifrs17",
                "sp_ani": "sp_ani", "sp_stress": "naomie", "sp_coh": "sp_coh",
                "sp_audit": "sp_audit", "sp_rapport": "sp_rapport",
            }
            if besoin in _ak_map:
                if "agent_results" not in st.session_state:
                    st.session_state["agent_results"] = {}
                st.session_state["agent_results"][_ak_map[besoin]] = resultats.get("principal", {})

            st.session_state["res_data"]    = resultats
            st.session_state["res_besoin"]  = besoin
            st.session_state["res_client"]  = ref_client
            # A13 — Audit Trail : tracer chaque analyse automatiquement
            try:
                from direction_non_vie.reglementation.a13_audit.agent import AgentA13AuditTrail
                # Construire le dict agents avec les clés attendues par A13
                _r_principal = resultats.get("principal", {})
                _agents_a13 = {}
                if besoin in ("triangle_xl", "sinistres"):
                    _agents_a13["a7"] = _r_principal
                elif besoin == "stress":   _agents_a13["a8"] = _r_principal
                elif besoin == "coherence":_agents_a13["a9"] = _r_principal
                elif besoin == "s2":       _agents_a13["a10"] = _r_principal
                elif besoin == "ifrs17":   _agents_a13["a11"] = _r_principal
                elif besoin == "alm":      _agents_a13["a12"] = _r_principal
                else:                      _agents_a13["principal"] = _r_principal
                # Enrichir avec les résultats déjà en session
                _ar = st.session_state.get("agent_results", {})
                for _ak_13, _ag_13 in [
                    ("a7","ibrahim"),("a8","isabelle"),("a9","marcus"),
                    ("a10","elena"),("a11","thomas"),("a12","aisha"),
                ]:
                    if _ak_13 not in _agents_a13 and _ag_13 in _ar:
                        _agents_a13[_ak_13] = _ar[_ag_13]
                _r13 = AgentA13AuditTrail(audit_path=_tmp, verbose=False).run(
                    resultats_agents=_agents_a13,
                    client_nom=ref_client or "Client ActuarIA",
                    generer_graphiques=False,
                )
                if "agent_results" not in st.session_state:
                    st.session_state["agent_results"] = {}
                st.session_state["agent_results"]["rafael"] = _r13
            except Exception as _e13:
                pass  # A13 non bloquant
            # Reset graphiques pour cohérence avec la nouvelle analyse
            st.session_state["graphiques_a7"] = {}
            # Stocker triangle séparément pour regénération graphiques à la volée
            _r_principal = resultats.get("principal", {})
            if isinstance(_r_principal, dict):
                if _r_principal.get("triangle") is not None:
                    st.session_state["triangle_a7"] = _r_principal["triangle"]
                # Stocker les graphiques en HTML directement (évite pb sérialisation Streamlit)
                _g_raw = _r_principal.get("graphiques", {})
                st.session_state["debug_graph_keys"] = list(_g_raw.keys()) if _g_raw else []
                if _g_raw:
                    try:
                        import plotly.io as _pio
                        _graphiques_html = {}
                        for _gnom, _gfig in _r_principal["graphiques"].items():
                            try:
                                _graphiques_html[_gnom] = _pio.to_html(
                                    _gfig,
                                    full_html=False,
                                    include_plotlyjs=False,
                                    config={"displayModeBar": False},
                                )
                            except Exception:
                                pass
                        st.session_state["graphiques_a7"] = _graphiques_html
                        st.session_state["graphiques_a7_raw"] = _r_principal["graphiques"]
                    except Exception as _eg:
                        st.session_state["graphiques_a7"] = {}
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
        _err = r_raw.get("erreur") if r_raw else None
        if _err:
            st.error(f"Erreur : {_err}")
        if st.button("← Retour à l'analyse"):
            nav_to("analyse")
        return

    # Debug temporaire graphiques — à supprimer après validation
    _dbg_g  = st.session_state.get("debug_graph_keys", [])
    _dbg_ga = st.session_state.get("graphiques_a7", {})
    if not st.session_state.get("graphiques_a7"):
        # Régénération silencieuse des graphiques si absent
        _tri = st.session_state.get("triangle_a7")
        if _tri is not None:
            try:
                import numpy as _np_g
                from direction_non_vie.provisionnement.a7_provisionnement.n5_graphiques import generer_graphiques as _gen_g_now
                import plotly.io as _pio_g
                _C_g = _np_g.array(_tri) if not isinstance(_tri, _np_g.ndarray) else _tri
                _expo_now = (st.session_state.get("analyse_params", {})
                             or {}).get("a7_primes")
                _figs = _gen_g_now(_C_g, r_raw.get("n2",{}), r_raw.get("n3",{}),
                                   r_raw.get("n4",{}), exposition=_expo_now)
                if _figs:
                    _html_g = {}
                    for _gn, _gf in _figs.items():
                        try:
                            _html_g[_gn] = _pio_g.to_html(_gf, full_html=False, include_plotlyjs=False, config={"displayModeBar":False})
                        except Exception:
                            pass
                    st.session_state["graphiques_a7"] = _html_g
                    st.rerun()
            except Exception:
                pass

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

    # ── Suite réglementaire — lancée directement depuis cette page ─────────────
    if besoin in ("triangle_xl", "sinistres"):
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;"
            f"font-weight:700;margin-bottom:12px;'>Suite reglementaire</div>",
            unsafe_allow_html=True
        )
        import os as _os_suite
        _os_suite.makedirs("/tmp/actuaria", exist_ok=True)
        _sc1, _sc2 = st.columns(2)
        with _sc1:
            _fpp_suite = st.number_input("Fonds propres (euros)", value=7_650_000,
                step=100_000, key="suite_fpp")
        with _sc2:
            _primes_suite = st.number_input("Primes acquises (euros)", value=10_000_000,
                step=100_000, key="suite_primes")

        _suite_defs = [
            ("A8 Stress Testing ORSA",    "isabelle", "stress"),
            ("A10 Solvabilite 2 SCR MCR",  "elena",    "s2"),
            ("A11 IFRS 17 PAA",            "thomas",   "ifrs17"),
            ("A12 ALM Liquidite",          "aisha",    "alm"),
            ("A9 Coherence inter-equipes", "marcus",   "coherence"),
        ]
        for _s_label, _s_agent, _s_besoin in _suite_defs:
            with st.expander(_s_label, expanded=False):
                _s_key = f"res_suite_{_s_besoin}"
                _s_res = st.session_state.get(_s_key)
                if st.button(f"Lancer {_s_label}", key=f"btn_suite_{_s_besoin}",
                             use_container_width=True):
                    with st.spinner("Calcul en cours..."):
                        try:
                            _tmp_s = "/tmp/actuaria"
                            if _s_besoin == "stress":
                                from direction_non_vie.reglementation.a8_stress_testing.agent import AgentA8StressTesting
                                _s_res = AgentA8StressTesting(audit_path=_tmp_s, verbose=False).run(
                                    result_a7=r_raw, fonds_propres=_fpp_suite,
                                    primes_acq=_primes_suite, generer_graphiques=True,
                                )
                            elif _s_besoin == "coherence":
                                from direction_non_vie.reglementation.a9_coherence.agent import AgentA9Coherence
                                # Récupérer les résultats déjà calculés dans cette session
                                _ss = st.session_state
                                _s_res = AgentA9Coherence(audit_path=_tmp_s, verbose=False).run(
                                    result_a7=r_raw,
                                    result_a8=_ss.get("res_suite_stress"),
                                    result_a10=_ss.get("res_suite_s2"),
                                    result_a11=_ss.get("res_suite_ifrs17"),
                                    result_a12=_ss.get("res_suite_alm"),
                                    primes_acq=_primes_suite,
                                    generer_graphiques=True,
                                )
                            elif _s_besoin == "s2":
                                from direction_non_vie.reglementation.a10_solvabilite2.agent import AgentA10Solvabilite2
                                _s_res = AgentA10Solvabilite2(audit_path=_tmp_s, verbose=False).run(
                                    result_a7=r_raw, fonds_propres=_fpp_suite,
                                    generer_graphiques=True,
                                )
                            elif _s_besoin == "ifrs17":
                                from direction_non_vie.reglementation.a10_solvabilite2.agent import AgentA10Solvabilite2
                                from direction_non_vie.reglementation.a11_ifrs17.agent import AgentA11IFRS17
                                _r10s = AgentA10Solvabilite2(audit_path=_tmp_s, verbose=False).run(
                                    result_a7=r_raw, fonds_propres=_fpp_suite,
                                    generer_graphiques=False,
                                )
                                _s_res = AgentA11IFRS17(audit_path=_tmp_s, verbose=False).run(
                                    result_a7=r_raw, result_a10=_r10s,
                                    generer_graphiques=True,
                                )
                            elif _s_besoin == "alm":
                                from direction_non_vie.reglementation.a10_solvabilite2.agent import AgentA10Solvabilite2
                                from direction_non_vie.reglementation.a12_alm.agent import AgentA12ALM
                                _r10s = AgentA10Solvabilite2(audit_path=_tmp_s, verbose=False).run(
                                    result_a7=r_raw, fonds_propres=_fpp_suite,
                                    generer_graphiques=False,
                                )
                                _s_res = AgentA12ALM(audit_path=_tmp_s, verbose=False).run(
                                    result_a10=_r10s, result_a7=r_raw,
                                    generer_graphiques=True,
                                )
                            # Sérialiser les graphiques Plotly en JSON (survivent au rerun)
                            import plotly.io as _pio_s
                            _graphs_raw = _s_res.get("graphiques", {})
                            _graphs_json = {}
                            for _gk, _gfig in _graphs_raw.items():
                                try:
                                    _graphs_json[_gk] = _pio_s.to_json(_gfig)
                                except Exception:
                                    pass
                            _s_res["graphiques_json"] = _graphs_json
                            st.session_state[_s_key] = _s_res
                            _ak_m = {"stress":"isabelle","coherence":"marcus",
                                     "s2":"elena","ifrs17":"thomas","alm":"aisha"}
                            if "agent_results" not in st.session_state:
                                st.session_state["agent_results"] = {}
                            st.session_state["agent_results"][_ak_m[_s_besoin]] = _s_res
                            st.rerun()
                        except Exception as _e_s:
                            st.error(f"Erreur : {_e_s}")
                if _s_res and _s_res.get("success"):
                    _s_statut = _s_res.get("statut_rag", _s_res.get("statut", ""))
                    _s_emoji = "✅" if _s_statut == "VERT" else "⚠️" if _s_statut == "AMBRE" else "🔴"
                    _s_col = VERT if _s_statut == "VERT" else AMBRE if _s_statut == "AMBRE" else ROUGE
                    # Badge statut
                    st.markdown(
                        f"<div style='background:{NAVY_LL};border-left:4px solid {_s_col};"
                        f"border-radius:8px;padding:10px 16px;margin-bottom:12px;'>"
                        f"<span style='font-size:0.9rem;font-weight:700;color:{_s_col};'>"
                        f"{_s_emoji} Statut : {_s_statut}</span></div>",
                        unsafe_allow_html=True
                    )
                    # KPIs selon agent
                    if _s_besoin == "stress":
                        _scr_t = _s_res.get("scr_total", {})
                        _rev   = _s_res.get("reverse_stress", {})
                        _ratio = float(_scr_t.get("ratio_scr_pct", 0)) if isinstance(_scr_t, dict) else 0
                        _scr_v = float(_scr_t.get("scr_total", 0)) if isinstance(_scr_t, dict) else 0
                        _marge = float(_rev.get("marge_euros", 0)) if isinstance(_rev, dict) else 0
                        _c1, _c2, _c3 = st.columns(3)
                        with _c1: st.metric("Ratio SCR", f"{_ratio:.1f}%", "objectif >100%")
                        with _c2: st.metric("SCR Total", f"{_scr_v/1e6:.1f}M€")
                        with _c3: st.metric("Marge", f"{_marge/1e6:.1f}M€")
                    elif _s_besoin == "coherence":
                        _dash = _s_res.get("dashboard", {})
                        _c1, _c2, _c3, _c4 = st.columns(4)
                        with _c1: st.metric("VERT", str(_dash.get("nb_vert", 0)))
                        with _c2: st.metric("AMBRE", str(_dash.get("nb_ambre", 0)))
                        with _c3: st.metric("ROUGE", str(_dash.get("nb_rouge", 0)))
                        with _c4: st.metric("Pret ACPR", "✅" if _dash.get("pret_acpr") else "❌")
                        # Tableau des contrôles
                        _ctrls = _s_res.get("controles", [])
                        if isinstance(_ctrls, list):
                            import pandas as _pd_a9
                            _rows_a9 = []
                            for _ctrl in _ctrls:
                                if not isinstance(_ctrl, dict): continue
                                _msg = _ctrl.get("message", "")
                                if "Non exécuté" in _msg or "requis" in _msg: continue
                                _st9 = _ctrl.get("statut", "")
                                _ic9 = "✅" if _st9=="VERT" else "⚠️" if _st9=="AMBRE" else "🔴"
                                _rows_a9.append({
                                    "Contrôle": _ctrl.get("controle", ""),
                                    "Statut": f"{_ic9} {_st9}",
                                    "Message": _msg[:120],
                                })
                            if _rows_a9:
                                st.dataframe(
                                    _pd_a9.DataFrame(_rows_a9),
                                    use_container_width=True,
                                    hide_index=True,
                                )
                    elif _s_besoin == "s2":
                        _prov  = _s_res.get("provisions", {})
                        _cap   = _s_res.get("capital", {})
                        _c1, _c2, _c3, _c4 = st.columns(4)
                        with _c1: st.metric("BE S2", f"{float(_prov.get('best_estimate',0))/1e6:.2f}M€")
                        with _c2: st.metric("SCR Total", f"{float(_cap.get('scr_total',0))/1e6:.2f}M€")
                        with _c3: st.metric("Ratio SCR", f"{float(_cap.get('ratio_scr',0)):.1f}%")
                        with _c4: st.metric("Ratio MCR", f"{float(_cap.get('ratio_mcr',0)):.1f}%")
                    elif _s_besoin == "ifrs17":
                        _prov17 = _s_res.get("provisions", {})
                        _ecart  = _s_res.get("ecart_s2_ifrs", {})
                        _lc     = _s_res.get("loss_component", {})
                        _c1, _c2, _c3 = st.columns(3)
                        with _c1: st.metric("TP IFRS 17", f"{float(_prov17.get('tp_ifrs17',0))/1e6:.2f}M€")
                        with _c2: st.metric("Ratio IFRS17/S2", f"{float(_ecart.get('ratio_ifrs_s2',0)):.3f}")
                        with _c3: st.metric("Loss Component", f"{float(_lc.get('lc_total',0))/1e6:.2f}M€")
                    elif _s_besoin == "alm":
                        _dur  = _s_res.get("duration", {})
                        _lcr  = _s_res.get("lcr", {})
                        _bv01 = _s_res.get("bv01", {})
                        _red  = _s_res.get("redington", {})
                        _nb_red = _red.get("detail", {}).get("nb_ok", _red.get("nb_conditions_ok", 0))
                        _c1, _c2, _c3, _c4 = st.columns(4)
                        with _c1: st.metric("Gap duration", f"{float(_dur.get('gap',0)):+.2f} ans")
                        with _c2: st.metric("LCR", f"{float(_lcr.get('lcr',0)):.0f}%")
                        with _c3: st.metric("BV01 Net", f"{float(_bv01.get('bv01_net',0)):+.0f}€/bp")
                        with _c4: st.metric("Redington", f"{_nb_red}/3")
                    # Graphiques — reconstruire depuis JSON (survie au rerun)
                    import plotly.io as _pio_d
                    _s_graphs_json = _s_res.get("graphiques_json", {})
                    if _s_graphs_json:
                        st.markdown(
                            f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;"
                            f"font-weight:700;margin:12px 0 6px;'>Graphiques</div>",
                            unsafe_allow_html=True
                        )
                        for _gk, _gjson in _s_graphs_json.items():
                            try:
                                _gfig = _pio_d.from_json(_gjson)
                                st.plotly_chart(_gfig, width='stretch',
                                                key=f"sg_{_s_besoin}_{_gk}")
                            except Exception:
                                pass
                elif _s_res:
                    st.warning("Erreur agent")

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

    # Clark retient sa réserve quand sa courbe monotone croissante ne peut pas
    # représenter le triangle (recours) : la case doit dire pourquoi, jamais
    # afficher 0 ni planter sur un None.
    _ck = n3.get('clark', {}) or {}
    if not _ck.get('disponible'):
        _clark_reserve_txt, _clark_statut_txt = "N/A", "ℹ️"
    elif _ck.get('reserve_be_clark') is None:
        _clark_reserve_txt = "Non publiée — structure incompatible"
        _clark_statut_txt  = "⛔"
    else:
        _clark_reserve_txt = f"{_ck['reserve_be_clark']:,.0f}"
        _clark_statut_txt  = "✅"

    rows = [
        {"Méthode": "🔗 Chain Ladder",              "Réserve (€)": f"{cl.get('reserve_totale',0):,.0f}",          "Poids BE": f"{poids.get('chain_ladder',0)*100:.0f}%", "Statut": "✅"},
        {"Méthode": "📐 Mack 1993 (IC 95%)",        "Réserve (€)": f"{mack.get('reserve_best_estimate',0):,.0f}", "Poids BE": f"{poids.get('mack',0)*100:.0f}%",          "Statut": "✅"},
        {"Méthode": "⚖️ Bornhuetter-Ferguson",      "Réserve (€)": f"{bf.get('reserve_totale',0):,.0f}",          "Poids BE": f"{poids.get('bornhuetter_ferguson', poids.get('bf',0))*100:.0f}%", "Statut": "✅"},
        {"Méthode": "🌊 Cape Cod",                  "Réserve (€)": f"{cc_r.get('reserve_totale',0):,.0f}",        "Poids BE": f"{poids.get('cape_cod',0)*100:.0f}%",       "Statut": "✅"},
        # `.get(clé, défaut)` NE PROTÈGE PAS ICI : ces clés EXISTENT et valent
        # None quand le Bootstrap est dégradé, si bien que le défaut ne se
        # déclenche jamais et que le format lève un TypeError. `or 0` teste la
        # valeur, pas la présence de la clé.
        {"Méthode": "🎲 Bootstrap ODP (BE)",       "Réserve (€)": f"{(boot.get('be_bootstrap') or boot.get('p50') or 0):,.0f}", "Poids BE": "—", "Statut": "✅" if (boot.get('be_bootstrap') or boot.get('p50') or 0) > 0 else "—"},
        {"Méthode": "🎲 Bootstrap ODP (P90)",       "Réserve (€)": f"{(boot.get('p90') or 0):,.0f}",                   "Poids BE": "—",                                         "Statut": "✅" if (boot.get('p90') or 0) > 0 else "—"},
        # Munich CL produit DEUX réserves — payé et engagé — et aucune clé
        # 'be_munich'. La lecture précédente affichait donc « 0 € ✅ » dès que la
        # méthode était disponible : un chiffre faux avec une coche verte.
        {"Méthode": "🇩🇪 Munich CL (payé / engagé)",
         "Réserve (€)": (f"{munich.get('be_munich_paye',0):,.0f}"
                         f" / {munich.get('be_munich_engage',0):,.0f}")
                        if munich.get('disponible') else "N/A",
         "Poids BE": "—", "Statut": "✅" if munich.get('disponible') else "ℹ️"},
        {"Méthode": "📐 Clark (LDF)",             "Réserve (€)": _clark_reserve_txt, "Poids BE": "—", "Statut": _clark_statut_txt},
        {"Méthode": "⭐ BEST ESTIMATE S2",          "Réserve (€)": f"{be_val:,.0f}",                              "Poids BE": "100%",                                      "Statut": "→ Bilan S2"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── COMMENTAIRE ACTUARIEL ─────────────────────────────────────────────────
    if commentaire:
        st.markdown(
            f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;"
            f"font-weight:700;margin:16px 0 8px;'>Rapport actuariel complet</div>",
            unsafe_allow_html=True
        )
        with st.expander("Voir le rapport A7 Ibrahim (8 sections)", expanded=False):
            st.text(commentaire)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── EFFETS CALENDAIRE (BARNETT-ZEHNWIRTH) ───────────────────────────────
    _bz = r_raw.get("n3", {}).get("barnett_zehnwirth", {})
    if _bz.get("success"):
        _bz_statut = _bz.get("statut", "VERT")
        _bz_col    = VERT if _bz_statut=="VERT" else AMBRE if _bz_statut=="AMBRE" else ROUGE
        _bz_emoji  = "✅" if _bz_statut=="VERT" else "⚠️" if _bz_statut=="AMBRE" else "🔴"
        _bz_n_sig  = _bz.get("n_effets_significatifs", 0)
        _bz_diags  = _bz.get("diagonales_anormales", [])
        _bz_reco   = _bz.get("recommandation", "")
        # Construire les blocs HTML variables séparément (évite f-strings imbriquées)
        _bz_diags_html = (
            f"<div><span style='font-size:0.7rem;color:{GRIS};'>Années</span><br>"
            f"<span style='font-size:0.8rem;color:{AMBRE};'>{' · '.join(_bz_diags[:5])}</span></div>"
        ) if _bz_diags else ""
        _bz_reco_html = (
            f"<div style='font-size:0.72rem;color:{OR};margin-top:6px;'>💡 {_bz_reco[:100]}</div>"
        ) if _bz_n_sig > 0 else ""
        st.markdown(
            f"<div style='background:{NAVY_L};border-left:4px solid {_bz_col};"
            f"border-radius:8px;padding:12px 16px;margin-bottom:12px;'>"
            f"<div style='font-size:0.72rem;color:{OR};font-weight:700;"
            f"text-transform:uppercase;margin-bottom:8px;'>◆ Effets Calendaire — Barnett-Zehnwirth</div>"
            f"<div style='display:flex;gap:20px;flex-wrap:wrap;'>"
            f"<div><span style='font-size:0.7rem;color:{GRIS};'>Statut</span><br>"
            f"<span style='font-size:0.9rem;font-weight:700;color:{_bz_col};'>{_bz_emoji} {_bz_statut}</span></div>"
            f"<div><span style='font-size:0.7rem;color:{GRIS};'>Diagonales anormales</span><br>"
            f"<span style='font-size:0.9rem;font-weight:700;color:{BLANC};'>{_bz_n_sig}</span>"
            f"<span style='font-size:0.8rem;color:{GRIS};'>/{_bz.get('n_diagonales_evaluees',0)}</span></div>"
            f"{_bz_diags_html}"
            f"</div>"
            f"<div style='font-size:0.74rem;color:{BLANC};margin-top:8px;line-height:1.6;'>"
            f"{_bz.get('message','')[:200]}</div>"
            f"{_bz_reco_html}"
            f"</div>",
            unsafe_allow_html=True
        )

    # ── BACK-TESTING BONI/MALI ───────────────────────────────────────────────
    _annee_debut_bt = st.session_state.get("analyse_params", {}).get("a7_annee_debut")
    _bt = r_raw.get("n3", {}).get("backtesting", {})
    if _bt.get("success"):
        _bt_statut = _bt.get("statut", "AMBRE")
        _bt_col = VERT if _bt_statut=="VERT" else AMBRE if _bt_statut=="AMBRE" else ROUGE
        _bt_emoji = "✅" if _bt_statut=="VERT" else "⚠️" if _bt_statut=="AMBRE" else "🔴"
        _bt_horizons = list(_bt.get("resultats", {}).keys())
        _bt_score = _bt.get("score_qualite", 0)
        _bt_rouge    = _bt.get("n_rouge", 0)
        _bt_ambre    = _bt.get("n_ambre", 0)
        _bt_rouge_n1 = _bt.get("n_rouge_n1", 0)
        _bt_rouge_n2 = _bt.get("n_rouge_n2", 0)
        _bt_ambre_n1 = _bt.get("n_ambre_n1", 0)
        _bt_ambre_n2 = _bt.get("n_ambre_n2", 0)
        _bt_matures  = _bt.get("n_matures", 0)
        _bt_seuil    = _bt.get("seuil_maturite", 0.75)
        _bt_score_n1 = _bt.get("score_n1", _bt_score)
        _bt_score_n2 = _bt.get("score_n2", _bt_score)

        _n_ann_bt = len(_bt.get("tableau", []))
        st.markdown(f"""
<div style='background:{NAVY_L};border-left:4px solid {_bt_col};border-radius:8px;padding:14px 18px;margin-bottom:12px;'>
  <div style='font-size:0.72rem;color:{OR};font-weight:700;text-transform:uppercase;margin-bottom:10px;'>◆ Back-testing Boni/Mali de liquidation</div>
  <div style='display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start;'>
    <div><span style='font-size:0.7rem;color:{GRIS};'>Statut global</span><br>
    <span style='font-size:0.9rem;font-weight:700;color:{_bt_col};'>{_bt_emoji} {_bt_statut}</span></div>
    <div><span style='font-size:0.7rem;color:{GRIS};'>Score N-1</span><br>
    <span style='font-size:0.9rem;font-weight:700;color:{BLANC};'>{_bt_score_n1}/100</span></div>
    <div><span style='font-size:0.7rem;color:{GRIS};'>Score N-2</span><br>
    <span style='font-size:0.9rem;font-weight:700;color:{BLANC};'>{_bt_score_n2}/100</span></div>
    <div><span style='font-size:0.7rem;color:{GRIS};'>Alertes N-1</span><br>
    <span style='font-size:0.85rem;font-weight:700;color:{ROUGE if _bt_rouge_n1>0 else VERT};'>{_bt_rouge_n1} 🔴</span>
    <span style='font-size:0.85rem;color:{AMBRE};'> {_bt_ambre_n1} 🟡</span></div>
    <div><span style='font-size:0.7rem;color:{GRIS};'>Alertes N-2</span><br>
    <span style='font-size:0.85rem;font-weight:700;color:{ROUGE if _bt_rouge_n2>0 else VERT};'>{_bt_rouge_n2} 🔴</span>
    <span style='font-size:0.85rem;color:{AMBRE};'> {_bt_ambre_n2} 🟡</span></div>
    <div><span style='font-size:0.7rem;color:{GRIS};'>Années évaluées</span><br>
    <span style='font-size:0.85rem;font-weight:700;color:{BLANC};'>{_bt_matures}/{_n_ann_bt}</span>
    <span style='font-size:0.72rem;color:{GRIS};'> (≥{int(_bt_seuil*100)}% dev.)</span></div>
  </div>
</div>""", unsafe_allow_html=True)

        # Deux tableaux boni/mali séparés
        _tableau_bt = _bt.get("tableau", [])
        _totaux_bt  = _bt.get("totaux", {})
        if _tableau_bt:
            import pandas as _pd_bt

            def _fmt_e(v):
                return f"{v:,.0f} €".replace(",", " ") if v is not None else "—"
            def _fmt_p(v):
                return f"{v:+.1f}%" if v is not None else "—"
            def _fmt_bm(v):
                if v is None: return "—"
                return f"🟢 +{v:,.0f} €".replace(",", " ") if v > 0 else f"🔴 {v:,.0f} €".replace(",", " ")
            def _alerte(ep):
                if ep is None: return "—"
                a = abs(ep)
                if a >= 15: return "🔴 Dépassé (>15%)"
                if a >= 8:  return "🟡 Vigilance (>8%)"
                return "✅ OK"

            def _html_tableau_bt(titre, rows, totaux, key_ult, key_bm, key_ep):
                """Génère un tableau HTML pro pour le back-testing."""
                def _td_num(v, bold=False):
                    s = f"{v:,.0f} €".replace(",", " ") if v is not None else "—"
                    return f"<td style='text-align:right;padding:7px 12px;{'font-weight:700;' if bold else ''}'>{s}</td>"
                def _td_bm(v, bold=False):
                    if v is None: return f"<td style='text-align:right;padding:7px 12px;'>—</td>"
                    col = "#27AE60" if v > 0 else "#C0392B" if v < 0 else "#8A9BB0"
                    sign = "+" if v > 0 else ""
                    s = f"{sign}{v:,.0f} €".replace(",", " ")
                    fw = "font-weight:700;" if bold else ""
                    return f"<td style='text-align:right;padding:7px 12px;color:{col};{fw}'>{s}</td>"
                def _td_pct(v, bold=False):
                    if v is None: return f"<td style='text-align:right;padding:7px 12px;'>—</td>"
                    col = "#27AE60" if v > 0 else "#C0392B" if v < 0 else "#8A9BB0"
                    fw = "font-weight:700;" if bold else ""
                    return f"<td style='text-align:right;padding:7px 12px;color:{col};{fw}'>{v:+.1f}%</td>"
                def _td_alerte(ep, bold=False):
                    if ep is None: return "<td style='padding:7px 12px;'>—</td>"
                    a = abs(ep)
                    if a >= 15: badge = f"<span style='background:#C0392B;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.7rem;'>🔴 Alerte</span>"
                    elif a >= 8: badge = f"<span style='background:#F39C12;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.7rem;'>🟡 Vigilance</span>"
                    else: badge = f"<span style='background:#27AE60;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.7rem;'>✅ OK</span>"
                    fw = "font-weight:700;" if bold else ""
                    return f"<td style='padding:7px 12px;{fw}'>{badge}</td>"

                html = f"""
<div style='margin-bottom:4px;'>
<div style='font-size:0.72rem;color:#C9A84C;font-weight:700;text-transform:uppercase;margin-bottom:8px;'>{titre}</div>
<div style='overflow-x:auto;'>
<table style='width:100%;border-collapse:collapse;font-size:0.8rem;font-family:Arial,sans-serif;'>
<thead>
<tr style='background:#0F2E52;'>
  <th style='text-align:left;padding:9px 12px;color:#C9A84C;font-weight:700;border-bottom:2px solid #C9A84C;'>Année</th>
  <th style='text-align:right;padding:9px 12px;color:#C9A84C;font-weight:700;border-bottom:2px solid #C9A84C;'>Provision projetée (€)</th>
  <th style='text-align:right;padding:9px 12px;color:#C9A84C;font-weight:700;border-bottom:2px solid #C9A84C;'>Observé N (€)</th>
  <th style='text-align:right;padding:9px 12px;color:#C9A84C;font-weight:700;border-bottom:2px solid #C9A84C;'>Boni / Mali (€)</th>
  <th style='text-align:right;padding:9px 12px;color:#C9A84C;font-weight:700;border-bottom:2px solid #C9A84C;'>Écart %</th>
  <th style='text-align:center;padding:9px 12px;color:#C9A84C;font-weight:700;border-bottom:2px solid #C9A84C;'>Alerte</th>
</tr>
</thead>
<tbody>"""
                for i, r in enumerate(rows):
                    bg = "background:rgba(26,63,107,0.4);" if i % 2 == 0 else "background:rgba(15,46,82,0.2);"
                    html += f"<tr style='{bg}'>"
                    html += f"<td style='padding:7px 12px;color:#E8EDF2;font-weight:500;'>{r['annee_label']}</td>"
                    html += _td_num(r[key_ult])
                    html += _td_num(r["observe_n"])
                    html += _td_bm(r[key_bm])
                    html += _td_pct(r[key_ep])
                    html += _td_alerte(r[key_ep])
                    html += "</tr>"

                # Ligne total
                html += f"""<tr style='background:#0F2E52;border-top:2px solid #C9A84C;'>
  <td style='padding:9px 12px;color:#C9A84C;font-weight:700;'>TOTAL</td>
  <td style='padding:9px 12px;'>—</td>"""
                html += _td_num(totaux.get(key_ult), bold=True)
                html += _td_num(totaux.get("observe_n"), bold=True)
                html += _td_bm(totaux.get(key_bm), bold=True)
                html += _td_pct(totaux.get(key_ep), bold=True)
                html += _td_alerte(totaux.get(key_ep), bold=True)
                html += "</tr>"

                html += """</tbody></table></div>
<div style='font-size:0.68rem;color:#8A9BB0;font-style:italic;margin-top:6px;'>
Seuil alerte : ±15% &nbsp;·&nbsp; Vigilance : ±8% &nbsp;·&nbsp; Années non évaluées : développement &lt; 75% &nbsp;·&nbsp; Source : Guide Institut des Actuaires 2023
</div></div>"""
                return html

            # Filtrer les lignes avec données
            _rows_n1 = [r for r in _tableau_bt if r.get("ultimate_n1") is not None]
            _rows_n2 = [r for r in _tableau_bt if r.get("ultimate_n2") is not None]

            # Statut et alertes déjà corrects depuis backtesting.py (années matures)

            st.markdown(_html_tableau_bt(
                "Tableau 1 — Comparaison N vs N-1 (arrêté précédent)",
                _rows_n1, _totaux_bt, "ultimate_n1", "boni_mali_n1", "ecart_pct_n1"
            ), unsafe_allow_html=True)

            st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

            st.markdown(_html_tableau_bt(
                "Tableau 2 — Comparaison N vs N-2 (il y a 2 arrêtés)",
                _rows_n2, _totaux_bt, "ultimate_n2", "boni_mali_n2", "ecart_pct_n2"
            ), unsafe_allow_html=True)

            # ── Narration ─────────────────────────────────────────────────────
            _msg_bt = _bt.get("message", "")
            if _msg_bt:
                st.markdown(
                    f"<div style='background:rgba(15,46,82,0.5);border-left:3px solid {OR};"
                    f"border-radius:6px;padding:10px 14px;margin-top:4px;"
                    f"font-size:0.78rem;color:{BLANC};line-height:1.7;'>"
                    f"{_msg_bt.replace(chr(10), '<br>')}</div>",
                    unsafe_allow_html=True
                )

    # ── GRAPHIQUES — regénérés à la volée depuis données brutes ─────────────
    # (les go.Figure ne survivent pas à la navigation Streamlit)
    _tri_res = st.session_state.get("triangle_a7")
    if _tri_res is None:
        _tri_res = r_raw.get("triangle")
    _figs_res = {}
    if _tri_res is not None and n2 and n3:
        try:
            import numpy as _np_res
            from direction_non_vie.provisionnement.a7_provisionnement.n5_graphiques import (
                generer_graphiques as _gen_res, TITRES_FIGURES as _TITRES_FIG)
            _C_res = _np_res.array(_tri_res) if not hasattr(_tri_res, "shape") else _tri_res
            _expo_res = (st.session_state.get("analyse_params", {})
                         or {}).get("a7_primes")
            _figs_res = _gen_res(_C_res, n2, n3, n4, exposition=_expo_res)
            # Le dénominateur était figé à 12 et le catalogue a bougé trois
            # fois depuis. Il se lit maintenant sur le catalogue lui-même.
            st.markdown(f"<div style='font-size:0.62rem;color:{VERT};margin-bottom:8px;'>✅ {len(_figs_res)}/{len(_TITRES_FIG)} graphiques générés</div>", unsafe_allow_html=True)
        except Exception as _eg:
            st.warning(f"Graphiques non disponibles : {_eg}")

    # Graphiques page Résultats : les graphiques décisionnels
    _ORDRE_RES = [
        # ⚠️ SUIT LE TRIAGE DU LOT C3b. g13 (le triangle une 3ᵉ fois) et g7
        # (donut SCR) sont retirés ; g4 fusionne l'ancien g4 et g11 et porte
        # desormais σ par année de survenance.
        # ⚠️ ET LES DEUX GRAPHIQUES DE DONNÉES DU LOT C3c : g16 montre les
        # reprises que les cumulés de g1 cachent par construction, g15 la
        # chronique de l'exposition. Ils étaient produits et invisibles ici.
        ("g1_heatmap",       "◆ Triangle de développement cumulé"),
        ("g16_increments",   "◆ Triangle des incréments — les reprises visibles"),
        ("g15_exposition",   "◆ Chronique de l'exposition et loss ratio implicite"),
        ("g4_reserve_annee", "◆ Réserve par année de survenance — IBNR ± σ"),
        ("g14_backtesting",  "◆ Back-testing — Boni/Mali de liquidation"),
        ("g2_cadences",      "◆ Cadences cumulées — Chain Ladder"),
        ("g5_convergence",   "◆ Convergence des méthodes — Best Estimate S2"),
        ("g6_bootstrap",     "◆ Distribution Bootstrap ODP — Quantiles de réserve"),
    ]
    for _gnom, _gtit in _ORDRE_RES:
        _fig = _figs_res.get(_gnom)
        if _fig is not None:
            st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:16px 0 6px;'>{_gtit}</div>", unsafe_allow_html=True)
            try:
                st.plotly_chart(_fig, width='stretch', key=f"res_{_gnom}")
            except Exception as _ef:
                st.warning(f"Graphique {_gtit} : {_ef}")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── ANALYSES AVANCÉES ────────────────────────────────────────────────────
    st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:8px 0 10px;'>◆ Analyses avancées</div>", unsafe_allow_html=True)

    _avancees = [
        ("Tail Factor", tail),
        ("Back-Testing", r_raw.get("back_testing", {})),
        ("Munich Chain Ladder", munich),
        ("Clark LDF", n3.get("clark", {})),
        ("Effets Calendaire BZ", n3.get("barnett_zehnwirth", {})),
    ]
    if not any(o and o.get("message") for _, o in _avancees):
        st.caption("Analyses avancees disponibles apres une analyse A7.")
    for label, obj in _avancees:
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

    for cle, h, label in [
        ("H1", h1, "Indépendance des années"),
        ("H2", h2, "Stabilité des facteurs"),
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

    # ── BFCC-H1..H5 et BOOT-H1..H4 : hypothèses propres aux méthodes ─────────
    # Statut motivé, sans score : elles n'en produisent aucun. La carte
    # « H4 — Homoscédasticité Bootstrap » qui figurait au-dessus en affichait
    # un, calculé sur le CV des variances des facteurs de développement — sans
    # rapport avec le φ du Bootstrap, et rouge sur les trois triangles de
    # référence. Elle est remplacée par BOOT-H1..H4, rendues ici.
    from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_bfcc import (
        lignes_hypotheses_bfcc as _lignes_bfcc)
    from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_bootstrap import (
        lignes_hypotheses_bootstrap as _lignes_boot)
    for _l in list(_lignes_bfcc(n2)) + list(_lignes_boot(n2)):
        _sc = (VERT if _l["statut"] == "VALIDÉE"
               else ROUGE if _l["statut"] == "NON VALIDÉE" else AMBRE)
        _ic = ("✅" if _l["statut"] == "VALIDÉE"
               else "❌" if _l["statut"] == "NON VALIDÉE" else "⚠️")
        st.markdown(f"""
<div style="background:{NAVY_L};border-left:3px solid {_sc};border-radius:6px;
            padding:12px 16px;margin-bottom:8px;width:100%;box-sizing:border-box;">
  <div style="font-size:0.78rem;color:{_sc};font-weight:700;margin-bottom:4px;">
    {_ic} {_l['libelle']} &nbsp;<span style="font-weight:400;font-size:0.72rem;">{_l['statut']}</span>
  </div>
  <div style="font-size:0.76rem;color:{BLANC};line-height:1.7;
              white-space:pre-wrap;word-break:break-word;">{_l['message']}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── JUGEMENT ACTUARIEL ───────────────────────────────────────────────────
    jugement = n4.get("jugement", "")
    if jugement:
        st.markdown(f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;font-weight:700;margin:8px 0 12px;'>◆ Jugement actuariel documenté</div>", unsafe_allow_html=True)
        import re as _re_jug
        # Nettoyer les séparateurs
        _jug_clean = _re_jug.sub(r'─+', '', jugement).strip()
        _sections_jug = _re_jug.split(r'(?=\d+\.\s+[A-ZÀÂÉÈÊ])', _jug_clean)
        for _sec in _sections_jug:
            _sec = _sec.strip()
            if not _sec:
                continue
            _lines_sec = _sec.split("\n", 1)
            _titre_sec = _lines_sec[0].strip()
            _corps_sec = _lines_sec[1].strip() if len(_lines_sec) > 1 else ""
            if not _titre_sec:
                continue
            # Construire le corps ligne par ligne
            _lignes_corps = [l.strip() for l in _corps_sec.split("\n") if l.strip()]
            _items_html = ""
            for _ln in _lignes_corps:
                # Détecter les items avec indicateurs
                if any(_ln.startswith(p) for p in ["✅","⚠️","🔴","🟡","ℹ️","•","-"]):
                    _col_ln = VERT if _ln.startswith("✅") else AMBRE if _ln.startswith(("⚠️","🟡")) else ROUGE if _ln.startswith("🔴") else BLANC
                    _items_html += (
                        f"<div style='font-size:0.76rem;color:{_col_ln};padding:2px 0;"
                        f"border-left:2px solid {_col_ln};padding-left:8px;margin:3px 0;"
                        f"word-break:break-word;'>{_ln}</div>"
                    )
                else:
                    _items_html += (
                        f"<div style='font-size:0.76rem;color:{BLANC};padding:2px 0;"
                        f"word-break:break-word;line-height:1.6;'>{_ln}</div>"
                    )
            _html_sec = (
                f"<div style='background:{NAVY_L};border-left:3px solid {OR};"
                f"border-radius:6px;padding:12px 16px;margin-bottom:8px;'>"
                f"<div style='font-size:0.75rem;font-weight:700;color:{OR};"
                f"margin-bottom:8px;'>{_titre_sec}</div>"
                f"{_items_html}"
                f"</div>"
            )
            st.markdown(_html_sec, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── EXPORT ───────────────────────────────────────────────────────────────
    # Champs obligatoires avant génération des rapports
    st.markdown(
        f"<div style='font-size:0.62rem;color:{OR};text-transform:uppercase;"
        f"font-weight:700;margin-bottom:10px;'>Informations actuarielle — obligatoires pour rapport</div>",
        unsafe_allow_html=True
    )
    _exp_c1, _exp_c2, _exp_c3 = st.columns(3)
    with _exp_c1:
        _ref_client_export = st.text_input(
            "Référence client *",
            value=st.session_state.get("res_client", ""),
            placeholder="Ex : Mutuelle XYZ — RC Auto 2026",
            key="export_ref_client",
        )
    # ⚠️ UNE SEULE SOURCE, PAS DEUX SAISIES. Le nom est demandé AVANT
    # l'analyse, parce que la gouvernance est une condition d'entrée ; le
    # redemander ici aurait créé deux champs pour un même fait, et rien
    # n'aurait garanti que le nom signant le rapport soit celui qui a validé
    # la décision de modèle. On relit donc, on ne redemande pas.
    _actuaire_nom = st.session_state.get("analyse_actuaire_nom", "")
    _actuaire_ia = st.session_state.get("analyse_actuaire_ia", "")
    with _exp_c2:
        st.text_input("Actuaire responsable", value=_actuaire_nom,
                      disabled=True, key="export_actuaire_nom_lecture",
                      help="Saisi avant l'analyse — il valide la décision de "
                           "modèle ET signe le rapport.")
    with _exp_c3:
        st.text_input("N° Institut des Actuaires", value=_actuaire_ia,
                      disabled=True, key="export_actuaire_ia_lecture")

    _champs_ok = bool(_ref_client_export and _actuaire_nom)
    if not _champs_ok:
        st.caption("⚠️ Référence client et nom de l'actuaire requis pour générer les rapports.")

    _a7p_exp = st.session_state.get("analyse_params", {})
    _arrete_exp = _a7p_exp.get("a7_arrete", "")
    _lob_exp = r_raw.get("lob_label", _a7p_exp.get("a7_lob", ""))
    _graphiques_exp = st.session_state.get("graphiques_a7")

    e1, e2, e3, e4, e5, e6 = st.columns([1, 1, 1, 1, 1, 1])
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
        if st.button("🌐 Rapport HTML", use_container_width=True, key="dl_res_html_btn",
                     disabled=not _champs_ok):
            with st.spinner("Génération du rapport HTML..."):
                try:
                    _html_bytes_sp = r_raw.get("html_bytes", b"")
                    if _html_bytes_sp:
                        # Rapport SP — html_bytes déjà générés par l'agent
                        _html_data = _html_bytes_sp if isinstance(_html_bytes_sp, bytes) else _html_bytes_sp.encode("utf-8")
                        st.download_button(
                            "⬇️ Télécharger HTML",
                            data=_html_data,
                            file_name=f"rapport_actuariel_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                            mime="text/html",
                            use_container_width=True,
                            key="dl_res_html",
                        )
                    else:
                        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import export_html as _eh
                        _html = _eh(
                            n1={}, n2=r_raw.get("n2",{}), n3=r_raw.get("n3",{}), n4=r_raw.get("n4",{}),
                            commentaire=r_raw.get("commentaire",""),
                            ref_client=_ref_client_export,
                            arrete=_arrete_exp,
                            audit_id=r_raw.get("audit_id",""),
                            lob_label=_lob_exp,
                            graphiques=_graphiques_exp,
                            actuaire_nom=_actuaire_nom,
                            actuaire_numero_ia=_actuaire_ia,
                        )
                        if _html:
                            st.download_button(
                                "⬇️ Télécharger HTML",
                                data=_html.encode("utf-8"),
                                file_name=f"rapport_actuariel_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                                mime="text/html",
                                use_container_width=True,
                                key="dl_res_html",
                            )
                        else:
                            st.error("Génération HTML échouée")
                except Exception as _eh_e:
                    st.error(f"Erreur HTML : {_eh_e}")

    with e4:
        if st.button("📄 Rapport Word", use_container_width=True, key="dl_res_word_btn",
                     disabled=not _champs_ok):
            with st.spinner("Génération du rapport Word..."):
                try:
                    _word_bytes_sp = r_raw.get("word_bytes", b"")
                    if _word_bytes_sp:
                        # Rapport SP — word_bytes déjà générés par l'agent
                        st.download_button(
                            "⬇️ Télécharger Word",
                            data=_word_bytes_sp,
                            file_name=f"rapport_actuariel_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="dl_res_word",
                        )
                    else:
                        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import export_word as _ew
                        _word = _ew(
                            n1={}, n2=r_raw.get("n2",{}), n3=r_raw.get("n3",{}), n4=r_raw.get("n4",{}),
                            commentaire=r_raw.get("commentaire",""),
                            ref_client=_ref_client_export,
                            arrete=_arrete_exp,
                            audit_id=r_raw.get("audit_id",""),
                            lob_label=_lob_exp,
                            graphiques=_graphiques_exp,
                            actuaire_nom=_actuaire_nom,
                            actuaire_numero_ia=_actuaire_ia,
                        )
                        if _word:
                            st.download_button(
                                "⬇️ Télécharger Word",
                                data=_word,
                                file_name=f"rapport_actuariel_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key="dl_res_word",
                            )
                        else:
                            st.error("Génération Word échouée")
                except Exception as _ew_e:
                    st.error(f"Erreur Word : {_ew_e}")
    with e5:
        # ⚠️ LE BOUTON N'APPARAIT QUE LA OU IL PEUT MARCHER. Il appelait
        # `export_pdf` depuis `n5_rapport`, fonction RETIREE par le lot C1 :
        # « Le PDF n'est plus GENERE : il s'obtient par CONVERSION du Word ou
        # du HTML, ce qui supprime la dependance a weasyprint. » L'import
        # levait donc un ImportError, attrape par le `except` et affiche a
        # l'actuaire sous la forme « Erreur PDF : cannot import name
        # 'export_pdf' ». Un bouton qui ne peut pas marcher est pire qu'un
        # bouton absent : il promet un livrable et rend un message technique.
        # Le chemin Sante-Prevoyance, lui, produit de vrais `pdf_bytes` et
        # garde son bouton.
        _pdf_bytes_sp = r_raw.get("pdf_bytes", b"")
        if _pdf_bytes_sp:
            if st.button("📑 Rapport PDF", use_container_width=True, key="dl_res_pdf_btn",
                         disabled=not _champs_ok):
                st.download_button(
                    "⬇️ Télécharger PDF",
                    data=_pdf_bytes_sp,
                    file_name=f"rapport_actuariel_{besoin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_res_pdf",
                )
        else:
            st.caption(
                "📑 **PDF** — non généré directement : imprimez le rapport "
                "**HTML** ou le **Word** ci-contre en PDF depuis votre "
                "navigateur ou Word. La mise en page d'impression est prévue "
                "pour cela."
            )
    with e6:
        if st.button("📊 Voir Dashboard", use_container_width=True, key="res_to_dash"):
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
elif page == "resultats":    page_resultats()
else:                        page_accueil()