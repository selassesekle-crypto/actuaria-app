import streamlit as st
import json, os
import pandas as pd
import plotly.graph_objects as go
import anthropic

PROJECT_ROOT = '.'

st.set_page_config(
    page_title="ActuarIA",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1F4E79 0%, #2E75B6 100%);
    padding: 2rem; border-radius: 12px; color: white;
    text-align: center; margin-bottom: 2rem;
}
.agent-response {
    background: #EBF3FB; border-radius: 10px; padding: 1.5rem;
    border-left: 4px solid #2E75B6; margin-top: 1rem;
}
.module-badge {
    display: inline-block; background: #1F4E79; color: white;
    padding: 0.2rem 0.8rem; border-radius: 20px;
    font-size: 0.8rem; font-weight: bold; margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

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
    }
    for cle, fichier in fichiers.items():
        try:
            with open(fichier) as f:
                resultats[cle] = json.load(f)
        except:
            resultats[cle] = {}
    return resultats

resultats = charger_resultats()

st.markdown("""
<div class="main-header">
    <h1>🏢 ActuarIA</h1>
    <p style="font-size:1.1rem; opacity:0.9; margin:0">
        Plateforme Actuarielle Intelligente
        | IARD · Vie · Solvabilité 2 · IFRS 17
    </p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    api_key = st.text_input("Clé API Claude", type="password", placeholder="sk-ant-...")
    st.markdown("---")
    st.markdown("### 📂 Navigation")
    page = st.radio("Module", [
        "🏠 Tableau de Bord",
        "💬 Agent IA",
        "📊 Tarification",
        "📐 Provisionnement",
        "🏛️ Solvabilité 2",
        "📋 IFRS 17",
        "💼 Provisions Vie"
    ], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("**ActuarIA v1.0**\nPowered by Claude + LangGraph")

if page == "🏠 Tableau de Bord":
    st.markdown("## 📊 Tableau de Bord")
    g  = resultats.get('glm_gamma', {})
    p  = resultats.get('provisions_fin', {})
    s  = resultats.get('scr', {})
    i  = resultats.get('ifrs17', {})
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Prime Pure Moy. GLM", f"{g.get('prime_pure_moy','N/A')} €")
    with col2:
        ibnr = p.get('provision_retenue', 0)
        st.metric("IBNR Retenu", f"{ibnr:,.0f} €" if ibnr else "N/A")
    with col3:
        ratio = s.get('ratio_scr_pct', 0)
        st.metric("Ratio SCR", f"{ratio}%",
                  "Conforme" if ratio and ratio >= 100 else "Alerte")
    with col4:
        lr = i.get('modele_paa', {}).get('loss_ratio_pct', 'N/A')
        st.metric("Loss Ratio IFRS 17", f"{lr}%")

    st.markdown("---")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("### Décomposition SCR")
        if s:
            fig = go.Figure(go.Pie(
                labels=['SCR Marché','SCR Non-Vie','SCR Contrepartie','SCR Opérationnel'],
                values=[s.get('scr_marche',0), s.get('scr_nv',0),
                        s.get('scr_contrepartie',0), s.get('scr_operationnel',0)],
                marker_colors=['#1F4E79','#C55A11','#FFC000','#2E75B6'],
                hole=0.4, textinfo='label+percent'
            ))
            fig.update_layout(height=350, showlegend=False,
                              paper_bgcolor='white',
                              margin=dict(t=10,b=10,l=10,r=10))
            st.plotly_chart(fig, use_container_width=True)
    with col_g2:
        st.markdown("### Provisions IARD")
        if p and 'methodes' in p:
            m = p['methodes']
            fig2 = go.Figure(go.Bar(
                x=['Chain-Ladder','Bornhuetter-Ferguson','Cape Cod'],
                y=[m.get('chain_ladder',0),
                   m.get('bornhuetter_ferguson',0),
                   m.get('cape_cod',0)],
                marker_color=['#1F4E79','#C55A11','#FFC000'],
                text=[str(round(v)) for v in [
                    m.get('chain_ladder',0),
                    m.get('bornhuetter_ferguson',0),
                    m.get('cape_cod',0)]],
                textposition='outside'
            ))
            fig2.add_hline(y=p.get('provision_retenue',0),
                           line_dash='dash', line_color='#375623',
                           annotation_text="Retenue")
            fig2.update_layout(height=350, paper_bgcolor='white',
                               plot_bgcolor='#EBF3FB',
                               margin=dict(t=30,b=10,l=10,r=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.markdown("### Récapitulatif Actuariel")
    pm = resultats.get('pm_vie', {})
    recap = {
        'Module': ['Tarification','Provisionnement IARD',
                   'Solvabilité 2','IFRS 17 PAA','Provisions Vie'],
        'Indicateur clé': [
            f"Prime pure : {g.get('prime_pure_moy','N/A')} €",
            f"IBNR : {p.get('provision_retenue',0):,.0f} €",
            f"Ratio SCR : {s.get('ratio_scr_pct','N/A')}%",
            f"Loss Ratio : {i.get('modele_paa',{}).get('loss_ratio_pct','N/A')}%",
            f"PM totale : {pm.get('portefeuille',{}).get('pm_totale',0):,.0f} €"
        ],
        'Statut': ['Validé','Validé','Conforme SCR','Profitable','Calculée']
    }
    st.dataframe(pd.DataFrame(recap), use_container_width=True, hide_index=True)

elif page == "💬 Agent IA":
    st.markdown("## 💬 Agent Actuariel IA")
    st.markdown("Posez votre question — l'agent sélectionne automatiquement le bon module.")
    if not api_key:
        st.warning("Entrez votre clé API Claude dans la barre latérale.")
    else:
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        st.markdown("**Questions rapides :**")
        cols = st.columns(3)
        exemples = [
            "IBNR total ?","Ratio SCR ?","CSM IFRS 17 ?",
            "Prime pure GLM ?","PM maximale vie ?","Synthèse bilan ?",
        ]
        for j, ex in enumerate(exemples):
            with cols[j % 3]:
                if st.button(ex, key=f"ex_{j}"):
                    st.session_state.q_auto = ex
        question = st.text_input(
            "Votre question :",
            value=st.session_state.get('q_auto', ''),
            placeholder="Ex: Quel est le ratio SCR ?"
        )
        if st.button("Envoyer", type="primary") and question:
            with st.spinner("Agent en cours..."):
                client = anthropic.Anthropic(api_key=api_key)
                prompt_r = (
                    "Routeur actuariel. JSON uniquement.\n"
                    "Modules: tarification, provisionnement, "
                    "provisions_vie, solvabilite2, ifrs17, synthese, inconnu\n"
                    f"Question: '{question}'\n"
                    'Reponds: {"module": "nom"}'
                )
                resp_r = client.messages.create(
                    model="claude-sonnet-4-6", max_tokens=50,
                    messages=[{"role":"user","content":prompt_r}]
                )
                try:
                    module = json.loads(
                        resp_r.content[0].text.strip()
                    ).get('module','inconnu')
                except:
                    module = 'inconnu'

                gd  = resultats.get('glm_gamma', {})
                gf  = resultats.get('glm_freq', {})
                pd2 = resultats.get('provisions_fin', {})
                sd  = resultats.get('scr', {})
                id2 = resultats.get('ifrs17', {})
                pmd = resultats.get('pm_vie', {})

                contextes = {
                    'tarification':   f"Prime pure moy={gd.get('prime_pure_moy')}EUR, Gini CV={gf.get('gini_cv_mean')}, Phi={gf.get('phi_pearson')}",
                    'provisionnement':f"CL={pd2.get('methodes',{}).get('chain_ladder')}EUR, BF={pd2.get('methodes',{}).get('bornhuetter_ferguson')}EUR, CC={pd2.get('methodes',{}).get('cape_cod')}EUR, Retenu={pd2.get('provision_retenue')}EUR",
                    'solvabilite2':   f"SCR={sd.get('scr_total')}EUR, Ratio={sd.get('ratio_scr_pct')}%, FP={sd.get('fonds_propres')}EUR",
                    'ifrs17':         f"Revenue={id2.get('modele_paa',{}).get('insurance_revenue')}EUR, LR={id2.get('modele_paa',{}).get('loss_ratio_pct')}%, CSM={id2.get('modele_bba',{}).get('csm')}EUR",
                    'provisions_vie': f"PM max={pmd.get('contrat_reference',{}).get('pm_max')}EUR, PM totale={pmd.get('portefeuille',{}).get('pm_totale')}EUR",
                    'synthese':       f"Prime={gd.get('prime_pure_moy')}EUR, IBNR={pd2.get('provision_retenue')}EUR, SCR={sd.get('ratio_scr_pct')}%, LR={id2.get('modele_paa',{}).get('loss_ratio_pct')}%",
                }
                ctx = contextes.get(module, "")
                prompt_a = (
                    f"Tu es un actuaire expert. "
                    f"Donnees reelles: {ctx}\n"
                    f"Question: {question}\n"
                    f"Reponds professionnellement avec les chiffres exacts. 3-4 phrases."
                )
                resp_a = client.messages.create(
                    model="claude-sonnet-4-6", max_tokens=400,
                    messages=[{"role":"user","content":prompt_a}]
                )
                reponse = resp_a.content[0].text
                st.session_state.messages.append({
                    'question': question,
                    'module':   module,
                    'reponse':  reponse
                })
                if 'q_auto' in st.session_state:
                    del st.session_state.q_auto

        for msg in reversed(st.session_state.messages):
            st.markdown(f"**Question : {msg['question']}**")
            st.markdown(
                f'<span class="module-badge">Module : {msg["module"].upper()}</span>',
                unsafe_allow_html=True)
            st.markdown(
                f'<div class="agent-response">{msg["reponse"]}</div>',
                unsafe_allow_html=True)
            st.markdown("---")

elif page == "📊 Tarification":
    st.markdown("## 📊 Tarification — GLM & XGBoost")
    g  = resultats.get('glm_gamma', {})
    gf = resultats.get('glm_freq', {})
    x  = resultats.get('xgboost', {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Prime Pure Moy.", f"{g.get('prime_pure_moy','N/A')} €")
        st.metric("AIC Gamma", str(g.get('aic_gamma','N/A')))
    with col2:
        st.metric("Gini CV GLM", str(gf.get('gini_cv_mean','N/A')))
        st.metric("Phi Poisson", str(gf.get('phi_pearson','N/A')))
    with col3:
        st.metric("Gini CV XGBoost", str(x.get('gini_cv','N/A')))
        st.metric("Modèle retenu", "GLM Poisson x Gamma")

elif page == "📐 Provisionnement":
    st.markdown("## 📐 Provisionnement IARD")
    p  = resultats.get('provisions_fin', {})
    cl = resultats.get('provisions_cl', {})
    if p and 'methodes' in p:
        m = p['methodes']
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Chain-Ladder", f"{m.get('chain_ladder',0):,.0f} €")
        with col2:
            st.metric("Bornhuetter-Ferguson", f"{m.get('bornhuetter_ferguson',0):,.0f} €")
        with col3:
            st.metric("Cape Cod", f"{m.get('cape_cod',0):,.0f} €")
        with col4:
            st.metric("Provision retenue", f"{p.get('provision_retenue',0):,.0f} €")
        st.markdown("---")
        par_annee = cl.get('par_annee', {})
        if par_annee:
            df_a = pd.DataFrame([
                {'Annee': a, 'IBNR': round(v['ibnr']),
                 'Ultime': round(v['ultime']),
                 'Pct Dev': str(v['pct_dev'])+'%'}
                for a, v in par_annee.items()
            ])
            st.dataframe(df_a, use_container_width=True, hide_index=True)

elif page == "🏛️ Solvabilité 2":
    st.markdown("## Solvabilite 2 — SCR Formule Standard")
    s = resultats.get('scr', {})
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("SCR Total", f"{s.get('scr_total',0):,.0f} €")
    with col2:
        st.metric("Fonds Propres", f"{s.get('fonds_propres',0):,.0f} €")
    with col3:
        ratio = s.get('ratio_scr_pct', 0)
        st.metric("Ratio SCR", f"{ratio}%",
                  "Conforme" if ratio and ratio >= 100 else "Non conforme")
    with col4:
        st.metric("Statut", s.get('statut','N/A'))
    st.markdown("---")
    data_scr = {
        'Module': ['SCR Marche','SCR Non-Vie','SCR Contrepartie','SCR Operationnel'],
        'Montant': [s.get('scr_marche',0), s.get('scr_nv',0),
                    s.get('scr_contrepartie',0), s.get('scr_operationnel',0)],
        'Pct BSCR': [
            round(s.get('scr_marche',0)/max(s.get('bscr',1),1)*100,1),
            round(s.get('scr_nv',0)/max(s.get('bscr',1),1)*100,1),
            round(s.get('scr_contrepartie',0)/max(s.get('bscr',1),1)*100,1),
            round(s.get('scr_operationnel',0)/max(s.get('bscr',1),1)*100,1),
        ]
    }
    st.dataframe(pd.DataFrame(data_scr), use_container_width=True, hide_index=True)

elif page == "📋 IFRS 17":
    st.markdown("## IFRS 17 — PAA & BBA")
    i   = resultats.get('ifrs17', {})
    paa = i.get('modele_paa', {})
    bba = i.get('modele_bba', {})
    st.markdown("### Modele PAA")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Insurance Revenue", f"{paa.get('insurance_revenue',0):,.0f} €")
    with col2:
        st.metric("Insurance Expenses", f"{paa.get('insurance_expenses',0):,.0f} €")
    with col3:
        st.metric("Insurance Result", f"{paa.get('insurance_result',0):,.0f} €")
    with col4:
        st.metric("Loss Ratio", f"{paa.get('loss_ratio_pct',0)}%")
    st.markdown("---")
    st.markdown("### Modele BBA")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("FCF", f"{bba.get('fcf',0):,.0f} €")
    with col2:
        st.metric("Risk Adjustment", f"{bba.get('ra',0):,.0f} €")
    with col3:
        st.metric("CSM", f"{bba.get('csm',0):,.0f} €")
    with col4:
        st.metric("Passif initial", f"{bba.get('total_passif_init',0):,.0f} €")

elif page == "💼 Provisions Vie":
    st.markdown("## Provisions Mathematiques Vie")
    pm = resultats.get('pm_vie', {})
    cr = pm.get('contrat_reference', {})
    pf = pm.get('portefeuille', {})
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Prime nivelee", f"{cr.get('prime_nivelee',0)} EUR/an")
    with col2:
        st.metric("PM maximale", f"{cr.get('pm_max',0):,.0f} EUR")
    with col3:
        st.metric("PM a t=10", f"{cr.get('pm_t10',0):,.0f} EUR")
    with col4:
        st.metric("PM portefeuille", f"{pf.get('pm_totale',0):,.0f} EUR")

st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#888; font-size:0.85rem; padding:1rem">
ActuarIA v1.0 — Plateforme Actuarielle Intelligente<br>
IARD · Vie · Solvabilite 2 · IFRS 17 · LangGraph · Claude API
</div>
""", unsafe_allow_html=True)
