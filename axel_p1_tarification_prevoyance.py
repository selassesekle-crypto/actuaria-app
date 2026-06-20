"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ACTUARIA — AGENT P1 AXEL : TARIFICATION PRÉVOYANCE v2.0               ║
║              Sous DIALLO (Équipe Prévoyance) · Direction SP                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PÉRIMÈTRE : Tarification prévoyance collective et individuelle             ║
║              ITT · IP · Décès · Tables BCAC 2019 · TD88-90 · TH0002       ║
║                                                                              ║
║  NOUVEAUTÉS v2 :                                                             ║
║    ✅ Branchement result_a2 (données réelles — âge, salaire, CSP)          ║
║    ✅ Tarification collective multi-salariés depuis DataFrame               ║
║    ✅ Fallback paramètres manuels si pas de données                         ║
║    ✅ Standard ActuarIA : RAG + 3 hypothèses + 4 graphiques + commentaire  ║
║    ✅ Sorties structurées vers P2 Rayan (tables Markov)                    ║
║    ✅ Conformité ANI 2013 (part patronale ≥ 50%)                           ║
║                                                                              ║
║  TABLES ACTUARIELLES :                                                       ║
║    BCAC 2019  → taux d'incidence ITT par âge et catégorie                 ║
║    TD 88-90   → probabilités d'invalidité permanente par âge               ║
║    TH0002     → tables de mortalité toutes causes                          ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_a2     → données réelles (optionnel)                             ║
║    age           → âge de l'assuré (ou âge moyen du collectif)            ║
║    salaire_brut  → salaire brut annuel                                     ║
║    categorie     → ouvrier/employe/cadre/cadre_sup                        ║
║    franchise_jours → franchise ITT (90 jours standard)                    ║
║    taux_rente_ipp  → taux rente invalidité (% salaire)                    ║
║    duree_contrat   → durée du contrat (ans)                               ║
║                                                                              ║
║  SORTIES VERS P2 RAYAN :                                                    ║
║    age · categorie · taux_itt · taux_ip · qx                             ║
║    franchise_jours · duree_contrat · salaire_brut                         ║
║                                                                              ║
║  VERSION : 2.0 — 20/06/2026                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

# ── Palette ActuarIA ──────────────────────────────────────────────────────────
NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"; OR="#C9A84C"
BLANC="#F0F4F8"; GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"
AMBRE="#F39C12"; BLEU="#3498DB"

LAYOUT_BASE = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16,r=16,t=60,b=60), height=300,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))

# ══════════════════════════════════════════════════════════════════════════════
# TABLES ACTUARIELLES
# ══════════════════════════════════════════════════════════════════════════════

# Taux d'incidence ITT par âge (BCAC 2019 — simplifiés)
TAUX_ITT_BCAC = {
    25:0.020, 30:0.025, 35:0.032, 40:0.042,
    45:0.055, 50:0.072, 55:0.095, 60:0.120,
}

# Probabilités d'invalidité permanente par âge (TD 88-90)
TAUX_IP_TD88 = {
    25:0.0008, 30:0.0012, 35:0.0018, 40:0.0028,
    45:0.0045, 50:0.0072, 55:0.0115, 60:0.0180,
}

# Tables mortalité TH0002
QX_TH0002 = {
    25:0.000730, 30:0.000860, 35:0.001180, 40:0.001800,
    45:0.002980, 50:0.005040, 55:0.008640, 60:0.014500, 65:0.023800,
}

# Facteurs catégorie socioprofessionnelle (sinistralité ITT)
FACT_CSP_ITT = {
    "ouvrier":   1.35,
    "employe":   1.00,
    "cadre":     0.75,
    "cadre_sup": 0.60,
}

# Taux actualisation annuités IP
TAUX_ACTUALISATION = 0.025


def _interp(table: dict, age: float) -> float:
    """Interpolation linéaire dans une table actuarielle."""
    ages = sorted(table.keys())
    if age >= ages[-1]: return table[ages[-1]]
    if age <= ages[0]:  return table[ages[0]]
    for i in range(len(ages)-1):
        if ages[i] <= age < ages[i+1]:
            r = (age - ages[i]) / (ages[i+1] - ages[i])
            return table[ages[i]] * (1-r) + table[ages[i+1]] * r
    return table[ages[-1]]


# ══════════════════════════════════════════════════════════════════════════════
class AgentP1TarificationPrevoyance:
    """
    Agent P1 Axel — Tarification Prévoyance v2.0.
    Sous DIALLO, Direction Santé-Prévoyance.

    Tarifie ITT, IP et Décès sur les tables BCAC 2019 / TD 88-90 / TH0002.
    Branchement sur les données réelles du client si disponibles via A2.
    """
    NOM     = "Axel"
    CODE    = "P1"
    VERSION = "2.0"
    MANAGER = "Diallo (Équipe Prévoyance)"

    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.p1.axel")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"P1 Axel v{self.VERSION} | {self.MANAGER}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_a2          = None,
            age:           float = 40.0,
            salaire_brut:  float = 45_000.0,
            categorie:     str   = "employe",
            franchise_jours: int = 90,
            taux_rente_ipp:float = 0.60,
            duree_contrat: int   = 20,
            chargement_pct:float = 0.20,
            generer_graphiques: bool = True) -> Dict:

        t0  = datetime.now()
        aid = f"P1_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # ── 1. EXTRACTION DONNÉES RÉELLES ─────────────────────────────────
            source, profils = self._extraire_donnees(
                result_a2, age, salaire_brut, categorie
            )
            # Calcul sur profil moyen (ou profil unique)
            age_m      = np.mean([p['age']      for p in profils])
            salaire_m  = np.mean([p['salaire']  for p in profils])
            cat_m      = profils[0]['categorie']  # CSP dominant
            nb_assures = len(profils)

            self.logger.info(
                f"[{aid}] P1 Axel | {nb_assures} assuré(s) | "
                f"âge moy={age_m:.1f} | sal={salaire_m:,.0f}€ | CSP={cat_m}"
            )

            # ── 2. TAUX ACTUARIELS ────────────────────────────────────────────
            fact_csp = FACT_CSP_ITT.get(cat_m, 1.0)
            taux_itt = _interp(TAUX_ITT_BCAC, age_m) * fact_csp
            taux_ip  = _interp(TAUX_IP_TD88,  age_m) * fact_csp
            qx       = _interp(QX_TH0002,     age_m)

            # ── 3. PRIME ITT ──────────────────────────────────────────────────
            sal_men      = salaire_m / 12
            # Durée moyenne BCAC 2019 :
            # - Tous arrêts : 45j (dont beaucoup < franchise)
            # - Arrêts > franchise : 180j (dossiers graves qui "passent" la franchise)
            # La prime ITT ne couvre que les arrêts dépassant la franchise
            # donc on utilise la durée conditionnelle au dépassement
            duree_moy_itt_all       = 45    # jours — tous arrêts
            duree_moy_itt_franchise = 180   # jours — arrêts > franchise (BCAC)
            prob_depasse_franchise  = max(0.0, 1.0 - franchise_jours / 270.0)
            jours_charges = max(0, duree_moy_itt_franchise - franchise_jours) * prob_depasse_franchise
            indemnite_j   = sal_men * 0.80 / 30   # 80% salaire / jour
            prime_itt     = taux_itt * jours_charges * indemnite_j

            # ── 4. PRIME IP ───────────────────────────────────────────────────
            age_retraite  = 65
            v             = 1.0 / (1 + TAUX_ACTUALISATION)
            duree_rente   = max(0, age_retraite - age_m)
            annuite_ip    = sum(v**k for k in range(int(duree_rente)))
            rente_ip_an   = salaire_m * taux_rente_ipp
            prime_ip      = taux_ip * rente_ip_an * annuite_ip / max(duree_contrat, 1)

            # ── 5. PRIME DÉCÈS ────────────────────────────────────────────────
            capital_deces  = salaire_m * 3   # 3 × salaire annuel
            prime_deces    = qx * capital_deces

            # ── 6. TOTAUX ─────────────────────────────────────────────────────
            prime_pure     = prime_itt + prime_ip + prime_deces
            prime_comm     = prime_pure * (1 + chargement_pct)
            prime_mois     = prime_comm / 12
            taux_cot       = prime_comm / max(salaire_m, 1) * 100
            part_patronale = prime_comm * 0.60
            part_salariale = prime_comm * 0.40
            primes_acq     = prime_comm * nb_assures

            # ── 7. HYPOTHÈSES + RAG ───────────────────────────────────────────
            hyp = self._hypotheses(
                prime_itt, prime_ip, prime_deces,
                prime_comm, salaire_m, taux_itt, taux_cot
            )
            rag = self._rag(hyp)

            # ── 8. COMMENTAIRE ────────────────────────────────────────────────
            com = self._commentaire(
                rag, age_m, salaire_m, cat_m, nb_assures, source,
                prime_itt, prime_ip, prime_deces, prime_pure,
                prime_comm, prime_mois, taux_cot,
                part_patronale, part_salariale,
                taux_itt, taux_ip, qx, franchise_jours, hyp
            )

            # ── 9. GRAPHIQUES ─────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    prime_itt, prime_ip, prime_deces,
                    prime_comm, salaire_m, taux_cot, hyp
                )

            self._audit(aid, prime_pure, prime_comm, taux_cot, rag, nb_assures)
            if self.verbose:
                self._console(aid, rag, prime_pure, prime_comm, taux_cot,
                              taux_itt, nb_assures)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':    True,
                'agent':      self.NOM,
                'version':    self.VERSION,
                'audit_id':   aid,
                'statut_rag': rag,
                'source_donnees': source,

                # ── Profil assuré ────────────────────────────────────────────
                'age':          round(age_m, 1),
                'salaire_brut': round(salaire_m, 2),
                'categorie':    cat_m,
                'nb_assures':   nb_assures,

                # ── Primes pures ─────────────────────────────────────────────
                'primes_pures': {
                    'itt':   round(prime_itt, 2),
                    'ip':    round(prime_ip, 2),
                    'deces': round(prime_deces, 2),
                    'total': round(prime_pure, 2),
                },

                # ── Primes commerciales ───────────────────────────────────────
                'prime_commerciale': round(prime_comm, 2),
                'prime_mensuelle':   round(prime_mois, 2),
                'taux_cotisation_pct': round(taux_cot, 3),
                'part_patronale':    round(part_patronale, 2),
                'part_salariale':    round(part_salariale, 2),
                'primes_acquises':   round(primes_acq, 2),

                # ── Taux actuariels ───────────────────────────────────────────
                'taux_sinistralite': {
                    'itt':   round(taux_itt, 4),
                    'ip':    round(taux_ip, 6),
                    'deces': round(qx, 6),
                },

                # ── Paramètres actuariels ────────────────────────────────────
                'franchise_jours':  franchise_jours,
                'taux_rente_ipp':   taux_rente_ipp,
                'duree_contrat':    duree_contrat,
                'annuite_ip':       round(annuite_ip, 4),

                # ── Sorties vers P2 Rayan ────────────────────────────────────
                'sorties_p2': {
                    'age':            round(age_m, 1),
                    'categorie':      cat_m,
                    'fact_csp':       fact_csp,
                    'taux_itt':       round(taux_itt, 4),
                    'taux_ip':        round(taux_ip, 6),
                    'qx':             round(qx, 6),
                    'franchise_jours':franchise_jours,
                    'duree_contrat':  duree_contrat,
                    'salaire_brut':   round(salaire_m, 2),
                    'nb_assures':     nb_assures,
                    'primes_acquises':round(primes_acq, 2),
                },

                # ── Standard ActuarIA ────────────────────────────────────────
                'hypotheses':  hyp,
                'commentaire': com,
                'graphiques':  gph,
                'duree_sec':   round(duree, 2),
                'erreur':      None,
            }

        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), aid)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. EXTRACTION DONNÉES RÉELLES
    # ══════════════════════════════════════════════════════════════════════════
    def _extraire_donnees(self, result_a2, age, salaire, categorie):
        """
        Extrait les profils assurés depuis result_a2 si disponible.
        Priorité : données réelles > paramètres manuels.
        """
        if not result_a2 or not result_a2.get('success'):
            return 'parametres_manuels', [{'age':age,'salaire':salaire,'categorie':categorie}]

        try:
            df = result_a2.get('dataframe')
            if df is None or len(df) == 0:
                return 'parametres_manuels', [{'age':age,'salaire':salaire,'categorie':categorie}]

            profils = []
            for _, row in df.iterrows():
                # Âge
                age_col = next((c for c in ['age','age_assure','age_client'] if c in df.columns), None)
                age_r   = float(row[age_col]) if age_col else age
                age_r   = max(18.0, min(age_r, 64.0))

                # Salaire
                sal_col = next((c for c in ['salaire_annuel_ref','salaire_brut','salaire'] if c in df.columns), None)
                sal_r   = float(row[sal_col]) if sal_col else salaire
                sal_r   = max(15_000.0, sal_r)

                # Catégorie
                cat_col = next((c for c in ['categorie_sociopro','csp','statut_professionnel'] if c in df.columns), None)
                cat_r   = str(row[cat_col]).lower() if cat_col else categorie
                cat_r   = cat_r if cat_r in FACT_CSP_ITT else 'employe'

                profils.append({'age':age_r,'salaire':sal_r,'categorie':cat_r})

            # CSP dominant
            from collections import Counter
            csp_dom = Counter(p['categorie'] for p in profils).most_common(1)[0][0]
            for p in profils:
                p['categorie'] = csp_dom

            self.logger.info(
                f"Données réelles A2 : {len(profils)} assurés | "
                f"âge moy={np.mean([p['age'] for p in profils]):.1f} | "
                f"sal moy={np.mean([p['salaire'] for p in profils]):,.0f}€ | "
                f"CSP dominant={csp_dom}"
            )
            return 'donnees_reelles_a2', profils

        except Exception as e:
            self.logger.warning(f"Extraction A2 : {e} → fallback paramètres")
            return 'parametres_manuels', [{'age':age,'salaire':salaire,'categorie':categorie}]

    # ══════════════════════════════════════════════════════════════════════════
    # 2. HYPOTHÈSES
    # ══════════════════════════════════════════════════════════════════════════
    def _hypotheses(self, p_itt, p_ip, p_deces, p_comm, salaire, t_itt, taux_cot):
        # H1 — Taux cotisation ∈ [1.5%, 4%]
        if 1.5 <= taux_cot <= 4.0:
            h1_s = 'VALIDÉE'
            h1_m = f"Taux cotisation = {taux_cot:.2f}% ∈ [1.5%,4%] ✅"
        elif taux_cot < 1.5:
            h1_s = 'À JUSTIFIER'
            h1_m = f"Taux cotisation = {taux_cot:.2f}% < 1.5% — adéquation garanties ?"
        else:
            h1_s = 'NON VALIDÉE'
            h1_m = f"Taux cotisation = {taux_cot:.2f}% > 4% — trop élevé, revoir garanties"

        # H2 — ITT > 50% de la prime pure
        total = p_itt + p_ip + p_deces
        part_itt = p_itt / max(total, 1)
        if part_itt >= 0.50:
            h2_s = 'VALIDÉE'
            h2_m = f"ITT = {part_itt*100:.1f}% ≥ 50% — structure normale prévoyance ✅"
        elif part_itt >= 0.30:
            h2_s = 'À JUSTIFIER'
            h2_m = f"ITT = {part_itt*100:.1f}% ∈ [30%,50%] — vérifier franchise et durée"
        else:
            h2_s = 'NON VALIDÉE'
            h2_m = f"ITT = {part_itt*100:.1f}% < 30% — structure anormale"

        # H3 — Taux ITT BCAC ∈ [1%, 15%]
        if 0.01 <= t_itt <= 0.15:
            h3_s = 'VALIDÉE'
            h3_m = f"Taux ITT BCAC = {t_itt*100:.1f}% ∈ [1%,15%] — cohérent âge/CSP ✅"
        else:
            h3_s = 'À JUSTIFIER'
            h3_m = f"Taux ITT BCAC = {t_itt*100:.1f}% hors [1%,15%] — vérifier paramètres"

        return [
            {'id':'H1','hypothese':'Taux de cotisation ∈ [1.5%,4%] du salaire brut (norme CCN)',
             'valeur':h1_m,'statut':h1_s,'critique':True},
            {'id':'H2','hypothese':'ITT ≥ 50% de la prime pure — risque dominant en prévoyance',
             'valeur':h2_m,'statut':h2_s,'critique':True},
            {'id':'H3','hypothese':'Taux ITT BCAC 2019 cohérent avec âge et catégorie',
             'valeur':h3_m,'statut':h3_s,'critique':True},
        ]

    def _rag(self, hyp):
        non_val = [h for h in hyp if h['statut']=='NON VALIDÉE']
        a_just  = [h for h in hyp if h['statut']=='À JUSTIFIER']
        if non_val: return 'ROUGE'
        if a_just:  return 'AMBRE'
        return 'VERT'

    # ══════════════════════════════════════════════════════════════════════════
    # 3. COMMENTAIRE
    # ══════════════════════════════════════════════════════════════════════════
    def _commentaire(self, rag, age, sal, cat, nb_ass, source,
                     p_itt, p_ip, p_deces, p_pure, p_comm, p_mois,
                     taux_cot, part_pat, part_sal,
                     t_itt, t_ip, qx, franchise, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        L = [
            "="*70,
            f"  RAPPORT TARIFICATION PRÉVOYANCE — P1 AXEL v{self.VERSION}",
            f"  {age:.0f} ans | {cat} | {sal:,.0f}€/an | {nb_ass} assuré(s) | Source: {source}",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
            "📊 RÉSUMÉ DIRECTION", "─"*40,
        ]
        if rag=='VERT':
            L.append(f"✅ Tarification validée. Prime={p_comm:.2f}€/an ({p_mois:.2f}€/mois). Taux cot.={taux_cot:.2f}%.")
        elif rag=='AMBRE':
            L.append(f"⚠️ Acceptable — vérifier les points signalés. Prime={p_comm:.2f}€/an.")
        else:
            L.append(f"❌ À corriger. Taux cot.={taux_cot:.2f}% hors norme ou structure ITT anormale.")

        L += [
            "", "🔢 DÉCOMPOSITION PRIMES PURES", "─"*40,
            f"  ITT (BCAC 2019)           : {p_itt:>12.2f}€/an",
            f"    Taux incidence ITT       : {t_itt*100:>11.1f}%",
            f"    Franchise                : {franchise:>11} jours",
            f"  IP (TD 88-90)             : {p_ip:>12.2f}€/an",
            f"    Taux invalidité IP       : {t_ip*100:>11.3f}%",
            f"  Décès (TH0002)            : {p_deces:>12.2f}€/an",
            f"    qx mortalité             : {qx*100:>11.4f}%",
            "  " + "─"*45,
            f"  Prime pure totale          : {p_pure:>12.2f}€/an",
            f"  Prime commerciale          : {p_comm:>12.2f}€/an ({p_mois:.2f}€/mois)",
            f"  Taux de cotisation         : {taux_cot:>11.2f}% du salaire brut",
            "", "🤝 RÉPARTITION ANI 2013", "─"*40,
            f"  Part patronale (60%)       : {part_pat:>12.2f}€/an",
            f"  Part salariale (40%)       : {part_sal:>12.2f}€/an",
            f"  → Conforme ANI 2013 (employeur ≥ 50%) ✅",
            "", "📋 HYPOTHÈSES", "─"*40,
        ]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else "⚠️"
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        L += ["", "🎯 AVIS AXEL → DIALLO", "─"*40]
        if rag=='VERT':
            L.append("✅ VALIDÉE — Données transmises à P2 Rayan (tables Markov).")
        elif rag=='AMBRE':
            L.append("⚠️ Revoir les points signalés avant transmission à P2.")
        else:
            L.append("❌ NON VALIDÉE — Escalade Diallo.")
        L.append("")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════════════════════
    # 4. GRAPHIQUES
    # ══════════════════════════════════════════════════════════════════════════
    def _graphiques(self, p_itt, p_ip, p_deces, p_comm, salaire, taux_cot, hyp):
        gph = {}

        # G1 — Décomposition primes pures
        try:
            h2 = next(h for h in hyp if h['id']=='H2')
            c2 = VERT if h2['statut']=='VALIDÉE' else (AMBRE if h2['statut']=='À JUSTIFIER' else ROUGE)
            fig = go.Figure(go.Bar(
                x=["ITT","Invalidité (IP)","Décès"],
                y=[p_itt, p_ip, p_deces],
                marker_color=[OR, BLEU, AMBRE],
                width=0.45, opacity=0.88,
                text=[f"{v:.0f}€" for v in [p_itt,p_ip,p_deces]],
                textposition="outside", textfont=dict(color=BLANC,size=10),
                hovertemplate="<b>%{x}</b><br>%{y:.2f}€/an<extra></extra>",
            ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text=f"G1 — Décomposition prime pure | {h2['valeur'][:40]}",
                           font=dict(color=c2,size=11),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(visible=False), bargap=0.35,
                annotations=[dict(
                    text="💡 L'ITT doit représenter ≥ 50% — c'est le risque dominant en prévoyance collective.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['decomposition_prime_prev'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — Jauge taux de cotisation
        try:
            h1 = next(h for h in hyp if h['id']=='H1')
            c1 = VERT if h1['statut']=='VALIDÉE' else (AMBRE if h1['statut']=='À JUSTIFIER' else ROUGE)
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=taux_cot,
                number=dict(suffix="%", font=dict(color=c1,size=28), valueformat=".2f"),
                title=dict(text=f"Taux cotisation | {h1['valeur'][:40]}", font=dict(color=c1,size=10)),
                gauge=dict(
                    axis=dict(range=[0,6], tickvals=[0,1.5,2.5,4,6],
                              ticktext=["0","1.5%","2.5%","4%","6%"],
                              tickfont=dict(color=GRIS,size=8)),
                    bar=dict(color=c1, thickness=0.25),
                    bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0,1.5], color="rgba(243,156,18,0.15)"),
                        dict(range=[1.5,4], color="rgba(46,204,113,0.12)"),
                        dict(range=[4,6],   color="rgba(231,76,60,0.15)"),
                    ],
                    threshold=dict(line=dict(color=VERT,width=3), thickness=0.8, value=2.5),
                ),
            ))
            fig.update_layout(
                paper_bgcolor=NAVY, font=dict(color=BLANC),
                margin=dict(l=30,r=30,t=80,b=50), height=300,
                annotations=[dict(
                    text="💡 Norme CCN : taux ∈ [1.5%,4%]. Cible marché ≈ 2.5% du salaire brut.",
                    xref="paper",yref="paper",x=0.5,y=-0.12,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            )
            gph['jauge_cotisation_prev'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — Part patronale vs salariale
        try:
            part_pat = p_comm * 0.60
            part_sal = p_comm * 0.40
            fig = go.Figure(go.Bar(
                x=["Part patronale (60%)", "Part salariale (40%)"],
                y=[part_pat, part_sal],
                marker_color=[VERT, BLEU], width=0.4, opacity=0.88,
                text=[f"{part_pat:.0f}€", f"{part_sal:.0f}€"],
                textposition="outside", textfont=dict(color=BLANC,size=12),
            ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G3 — Répartition prime patronale/salariale (ANI 2013)",
                           font=dict(color=BLANC,size=11),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(visible=False), bargap=0.4,
                annotations=[dict(
                    text="💡 ANI 2013 : l'employeur doit prendre en charge ≥ 50% de la prime — ici 60%.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['repartition_cotisation'] = fig
        except Exception as e:
            self.logger.warning(f"G3:{e}")

        # G4 — Scorecard
        try:
            fig = go.Figure()
            for h in hyp:
                c  = VERT if h['statut']=='VALIDÉE' else (AMBRE if h['statut']=='À JUSTIFIER' else ROUGE)
                ic = "✅" if h['statut']=='VALIDÉE' else ("⚠️" if h['statut']=='À JUSTIFIER' else "❌")
                s  = 1.0 if h['statut']=='VALIDÉE' else (0.5 if h['statut']=='À JUSTIFIER' else 0.0)
                fig.add_trace(go.Bar(
                    x=[s], y=[h['hypothese'][:40]], orientation="h",
                    marker_color=c, width=0.5, opacity=0.85,
                    text=f"{ic} {h['statut']}", textposition="outside",
                    textfont=dict(color=c,size=10), showlegend=False,
                    hovertemplate=f"<b>{h['hypothese']}</b><br>{h['valeur']}<extra></extra>",
                ))
            cg = VERT if all(h['statut']=='VALIDÉE' for h in hyp) else (ROUGE if any(h['statut']=='NON VALIDÉE' for h in hyp) else AMBRE)
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G4 — Scorecard Prévoyance P1 Axel",
                           font=dict(color=cg,size=12),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 3 ✅ = tarification prévoyance conforme BCAC/TD88 et ANI 2013.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['scorecard_p1'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        return gph

    # ══════════════════════════════════════════════════════════════════════════
    def _audit(self, aid, pp, pc, taux_cot, rag, nb):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'prime_pure':pp,'prime_comm':pc,'taux_cot':taux_cot,'nb_assures':nb}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, rag, pp, pc, taux_cot, t_itt, nb):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        print(f"\n{'─'*70}")
        print(f"  P1 AXEL v{self.VERSION} | {aid} | {ic} {rag}")
        print(f"  Prime pure={pp:.2f}€ | Commerciale={pc:.2f}€ | Taux cot.={taux_cot:.2f}%")
        print(f"  Taux ITT={t_itt*100:.1f}% | {nb} assuré(s)")
        print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {'success':False,'agent':self.NOM,'version':self.VERSION,
                'audit_id':aid,'statut_rag':'ROUGE',
                'primes_pures':{'itt':0,'ip':0,'deces':0,'total':0},
                'prime_commerciale':0,'taux_cotisation_pct':0,
                'sorties_p2':{},'hypotheses':[],'commentaire':f"❌ ERREUR P1:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  P1 AXEL v2.0 — DÉMO TARIFICATION PRÉVOYANCE ITT/IP/DÉCÈS")
    print("  BCAC 2019 | TD88-90 | TH0002 | Branchement A2 | ANI 2013")
    print("="*70)

    agent = AgentP1TarificationPrevoyance(
        models_path='/tmp/p1/models', audit_path='/tmp/p1/audit', verbose=True
    )
    r = agent.run(
        result_a2=None,
        age=40, salaire_brut=45_000, categorie="employe",
        franchise_jours=90, taux_rente_ipp=0.60, duree_contrat=20,
        chargement_pct=0.20, generer_graphiques=False,
    )

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut       : {r['statut_rag']}")
    pp = r['primes_pures']
    print(f"  Prime ITT    : {pp['itt']:>10.2f}€/an")
    print(f"  Prime IP     : {pp['ip']:>10.2f}€/an")
    print(f"  Prime Décès  : {pp['deces']:>10.2f}€/an")
    print(f"  Prime pure   : {pp['total']:>10.2f}€/an")
    print(f"  Prime comm.  : {r['prime_commerciale']:>10.2f}€/an ({r['prime_mensuelle']:.2f}€/mois)")
    print(f"  Taux cot.    : {r['taux_cotisation_pct']:>9.2f}%")
    print(f"\n  Taux ITT BCAC: {r['taux_sinistralite']['itt']*100:.1f}%")
    print(f"  Taux IP TD88 : {r['taux_sinistralite']['ip']*100:.3f}%")
    print(f"  qx TH0002    : {r['taux_sinistralite']['deces']*100:.4f}%")
    print(f"\n  Sorties P2   : âge={r['sorties_p2']['age']} | CSP={r['sorties_p2']['categorie']}")
    print(f"  Durée        : {r['duree_sec']:.2f}s")
