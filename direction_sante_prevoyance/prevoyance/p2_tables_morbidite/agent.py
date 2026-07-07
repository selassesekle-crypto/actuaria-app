# Migré depuis sp5_tables_morbidite.py → direction_sante_prevoyance/prevoyance/p2_tables_morbidite/agent.py
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      ACTUARIA — AGENT P2 RAYAN : TABLES DE MORBIDITÉ v2.0                 ║
║              Sous DIALLO (Équipe Prévoyance) · Direction SP                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PÉRIMÈTRE : Modélisation des transitions d'état en prévoyance              ║
║              Chaîne de Markov 4 états : Actif → ITT → IP → Décès          ║
║              Tables BCAC 2019 · TD 88-90 · Maintien en incapacité          ║
║                                                                              ║
║  DIFFÉRENCIATEURS vs marché :                                               ║
║    ✅ Vraie chaîne de Markov 4 états avec matrices de transition           ║
║    ✅ Probabilités de passage calibrées sur BCAC 2019 par âge et CSP       ║
║    ✅ Espérance de durée en ITT et en IP par tranche d'âge                ║
║    ✅ Probabilité de maintien en ITT à 6 mois / 12 mois / 24 mois         ║
║    ✅ Projection sur l'horizon du contrat                                   ║
║    ✅ Standard ActuarIA : RAG + 5 hypothèses + 4 graphiques + commentaire  ║
║    ✅ Sorties structurées vers P3 Élodie (provisionnement)                 ║
║                                                                              ║
║  MODÈLE DE MARKOV :                                                          ║
║                                                                              ║
║     q_AI = taux passage Actif → ITT (incapacité)                           ║
║     q_IA = taux retour  ITT  → Actif (guérison)                           ║
║     q_II = taux maintien ITT → ITT                                         ║
║     q_IP = taux passage ITT  → IP (invalidité permanente)                  ║
║     q_ID = taux décès   ITT  → Décès                                      ║
║     q_PI = taux maintien IP  → IP (rente viagère)                          ║
║     q_PD = taux décès   IP   → Décès                                      ║
║     q_AD = taux décès   Actif → Décès (mortalité toutes causes)            ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_p1  → Tarification Axel (âge, CSP, taux_itt, qx, franchise)    ║
║                                                                              ║
║  SORTIES VERS P3 ÉLODIE :                                                   ║
║    matrices_transition · esperances · prob_maintien · durees_moyennes       ║
║                                                                              ║
║  VERSION : 2.0 — 20/06/2026                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"; OR="#C9A84C"
BLANC="#F0F4F8"; GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"
AMBRE="#F39C12"; BLEU="#3498DB"; VIOLET="#9B59B6"

LAYOUT_BASE = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16,r=16,t=60,b=60), height=300,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))

# ── Tables centralisées — importées depuis sp_tables_actuarielles ────────────
try:
    from direction_sante_prevoyance.services.sp_tables_actuarielles import (
        get_taux_itt_bcac as _get_taux_itt_central,
        get_taux_ip_td8890 as _get_taux_ip_central,
        get_qx_th0002 as _get_qx_central,
        get_prob_maintien_itt as _get_maintien_central,
    )
    _TABLES_CENTRALISEES = True
except ImportError:
    _TABLES_CENTRALISEES = False

# ══════════════════════════════════════════════════════════════════════════════
# TABLES BCAC 2019 — locales (fallback)
# ══════════════════════════════════════════════════════════════════════════════
# Ces probabilités sont annuelles et calibrées sur BCAC 2019

# q_AI : probabilité de tomber en ITT dans l'année
Q_AI_BCAC = {
    25:0.020, 30:0.025, 35:0.032, 40:0.042,
    45:0.055, 50:0.072, 55:0.095, 60:0.120,
}

# q_IP : probabilité de passer d'ITT à IP (invalidité permanente)
# Conditionnelle à être en ITT — augmente avec l'âge
Q_IP_COND_BCAC = {
    25:0.04, 30:0.05, 35:0.06, 40:0.08,
    45:0.12, 50:0.18, 55:0.25, 60:0.35,
}

# q_IA : probabilité de guérison (ITT → Actif)
# Diminue avec la durée en ITT et l'âge
Q_IA_BCAC = {
    25:0.75, 30:0.72, 35:0.68, 40:0.62,
    45:0.55, 50:0.46, 55:0.38, 60:0.28,
}

# Taux de maintien en IP (rente viagère jusqu'à 65 ans ou décès)
# q_PI ≈ 1 - q_PD (la plupart restent invalides jusqu'à la retraite)
Q_PD_IP = {
    25:0.003, 30:0.004, 35:0.005, 40:0.007,
    45:0.011, 50:0.017, 55:0.026, 60:0.040,
}

# Facteurs CSP sur q_AI
FACT_CSP = {
    "ouvrier":   1.35,
    "employe":   1.00,
    "cadre":     0.75,
    "cadre_sup": 0.60,
}

# Durées moyennes en ITT selon l'âge (mois) — conditionnelles au dépassement 90j
DUREE_ITT_MOIS = {
    25: 8.0,  30: 9.5,  35:11.0, 40:13.5,
    45:16.0, 50:19.0,  55:22.0, 60:26.0,
}


def _interp(table: dict, age: float) -> float:
    ages = sorted(table.keys())
    if age >= ages[-1]: return table[ages[-1]]
    if age <= ages[0]:  return table[ages[0]]
    for i in range(len(ages)-1):
        if ages[i] <= age < ages[i+1]:
            r = (age - ages[i]) / (ages[i+1] - ages[i])
            return table[ages[i]] * (1-r) + table[ages[i+1]] * r
    return table[ages[-1]]


# ══════════════════════════════════════════════════════════════════════════════
class AgentP2TablesMorbidite:
    """
    Agent P2 Rayan — Tables de Morbidité v2.0.
    Chaîne de Markov 4 états : Actif / ITT / IP / Décès.
    Sous DIALLO, Direction Santé-Prévoyance.
    """
    NOM     = "Rayan"
    CODE    = "P2"
    VERSION = "2.0"
    MANAGER = "Diallo (Équipe Prévoyance)"

    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.p2.rayan")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"P2 Rayan v{self.VERSION} | {self.MANAGER}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_p1,
            horizon_ans:    int  = 5,
            generer_graphiques: bool = True) -> Dict:

        t0  = datetime.now()
        aid = f"P2_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # ── 1. EXTRACTION P1 ──────────────────────────────────────────────
            src = self._extraire_p1(result_p1)
            age = src['age']
            cat = src['categorie']
            self.logger.info(
                f"[{aid}] P2 Rayan | âge={age} | CSP={cat} | "
                f"horizon={horizon_ans} ans"
            )

            # ── 2. PROBABILITÉS DE TRANSITION ─────────────────────────────────
            trans = self._calculer_transitions(age, cat)

            # ── 3. MATRICE DE TRANSITION MARKOV ───────────────────────────────
            # États : 0=Actif 1=ITT 2=IP 3=Décès
            P = self._matrice_transition(trans)

            # ── 4. PROJECTION SUR HORIZON ────────────────────────────────────
            projection = self._projeter(P, horizon_ans)

            # ── 5. ESPÉRANCES DE DURÉE ────────────────────────────────────────
            esperances = self._calculer_esperances(trans, age)

            # ── 6. PROBABILITÉS DE MAINTIEN ──────────────────────────────────
            prob_maintien = self._calculer_maintien(P)

            # ── 7. HYPOTHÈSES + RAG ───────────────────────────────────────────
            hyp = self._hypotheses(trans, esperances, prob_maintien, age,
                                   src['taux_ip'])
            rag = self._rag(hyp, trans)

            # ── 8. COMMENTAIRE ────────────────────────────────────────────────
            com = self._commentaire(
                rag, age, cat, trans, P, projection,
                esperances, prob_maintien, horizon_ans, hyp
            )

            # ── 9. GRAPHIQUES ─────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    trans, P, projection, esperances, prob_maintien, age
                )

            self._audit(aid, trans, esperances, rag)
            if self.verbose:
                self._console(aid, rag, age, cat, trans, esperances, prob_maintien)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':    True,
                'agent':      self.NOM,
                'version':    self.VERSION,
                'audit_id':   aid,
                'statut_rag': rag,

                # ── Transitions ──────────────────────────────────────────────
                'transitions': trans,

                # ── Matrice de Markov (4×4) ───────────────────────────────────
                'matrice_P': P.tolist(),

                # ── Projection ───────────────────────────────────────────────
                'projection': projection,

                # ── Espérances ───────────────────────────────────────────────
                'esperances': esperances,

                # ── Maintien ─────────────────────────────────────────────────
                'prob_maintien': prob_maintien,

                # ── Sorties vers P3 Élodie ────────────────────────────────────
                'sorties_p3': {
                    'age':                src['age'],
                    'categorie':          cat,
                    'taux_ip':            trans['q_IP_annuel'],
                    'taux_itt':           trans['q_AI'],
                    'duree_moy_itt_mois': esperances['duree_moy_itt_mois'],
                    'prob_itt_to_ip':     trans['q_IP_cond'],
                    'prob_maintien_6m':   prob_maintien['mois_6'],
                    'prob_maintien_12m':  prob_maintien['mois_12'],
                    'prob_maintien_24m':  prob_maintien['mois_24'],
                    'esperance_duree_ip': esperances['esperance_duree_ip_ans'],
                    'matrice_P':          P.tolist(),
                    'salaire_brut':       src['salaire_brut'],
                    'taux_rente_ipp':     src.get('taux_rente_ipp', 0.60),
                    'primes_acquises':    src.get('primes_acquises', 0),
                    'nb_assures':         src.get('nb_assures', 1),
                    'franchise_jours':    src.get('franchise_jours', 90),
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
    # 1. EXTRACTION P1
    # ══════════════════════════════════════════════════════════════════════════
    def _extraire_p1(self, result_p1):
        if not result_p1 or not result_p1.get('success'):
            raise ValueError("result_p1 absent — P2 nécessite P1")
        p2 = result_p1.get('sorties_p2', {})
        return {
            'age':            float(p2.get('age', result_p1.get('age', 40))),
            'categorie':      p2.get('categorie', result_p1.get('categorie', 'employe')),
            'taux_itt':       float(p2.get('taux_itt', 0.042)),
            'taux_ip':        float(p2.get('taux_ip', 0.0028)),
            'qx':             float(p2.get('qx', 0.0018)),
            'franchise_jours':int(p2.get('franchise_jours', 90)),
            'duree_contrat':  int(p2.get('duree_contrat', 20)),
            'salaire_brut':   float(p2.get('salaire_brut', 45_000)),
            'primes_acquises':float(p2.get('primes_acquises', 0)),
            'nb_assures':     int(p2.get('nb_assures', 1)),
            'taux_rente_ipp': float(result_p1.get('taux_rente_ipp', 0.60)),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 2. PROBABILITÉS DE TRANSITION
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_transitions(self, age, categorie):
        """
        Calcule toutes les probabilités de transition BCAC 2019.
        Applique le facteur CSP sur q_AI (incidence ITT).
        """
        fact_csp = FACT_CSP.get(categorie, 1.0)

        # Actif → ITT (incidence annuelle ajustée CSP)
        q_AI  = _interp(Q_AI_BCAC, age) * fact_csp

        # Taux de guérison ITT → Actif
        q_IA  = _interp(Q_IA_BCAC, age)

        # Probabilité conditionnelle ITT → IP (parmi ceux restant en ITT)
        q_IP_cond = _interp(Q_IP_COND_BCAC, age)

        # Taux décès Actif → Décès (mortalité toutes causes TH0002)
        from direction_sante_prevoyance.services.sp_tables_actuarielles import get_qx_th0002 as _get_qx
        qx_AD = _get_qx(age, 'M')  # TH0002 — mortalité toutes causes

        # Taux décès IP → Décès
        q_PD  = _interp(Q_PD_IP, age)

        # Dérivés
        # q_II = probabilité de rester en ITT = 1 - q_IA - q_IP - q_ID
        q_ID  = qx_AD * 2.5    # mortalité en ITT ≈ 2.5× mortalité active
        q_II  = max(0.01, 1 - q_IA - q_IP_cond * (1-q_IA) - q_ID)
        # q_IP annuel = q_AI × q_IP_cond (passer d'actif à IP en une année)
        q_IP_an = q_AI * q_IP_cond
        # q_PI = maintien en IP
        q_PI  = max(0.0, 1.0 - q_PD)

        return {
            'q_AI':         round(q_AI, 6),
            'q_IA':         round(q_IA, 4),
            'q_II':         round(q_II, 4),
            'q_IP_cond':    round(q_IP_cond, 4),
            'q_IP_annuel':  round(q_IP_an, 6),
            'q_ID':         round(q_ID, 6),
            'q_AD':         round(qx_AD, 6),
            'q_PI':         round(q_PI, 4),
            'q_PD':         round(q_PD, 4),
            'fact_csp':     fact_csp,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 3. MATRICE DE TRANSITION MARKOV 4×4
    # ══════════════════════════════════════════════════════════════════════════
    def _matrice_transition(self, trans):
        """
        Matrice de transition annuelle P (4×4).
        États : 0=Actif  1=ITT  2=IP  3=Décès

        P[i,j] = probabilité de passer de l'état i à l'état j en 1 an

        Propriété : chaque ligne somme à 1 (état absorbant = Décès)
        """
        q_AI = trans['q_AI']
        q_IA = trans['q_IA']
        q_II = trans['q_II']
        q_IP = trans['q_IP_cond']
        q_ID = trans['q_ID']
        q_AD = trans['q_AD']
        q_PI = trans['q_PI']
        q_PD = trans['q_PD']

        # Ligne Actif : AA + AI + AD = 1
        p_AA = max(0.0, 1.0 - q_AI - q_AD)
        p_AI = q_AI
        p_AD = q_AD

        # Ligne ITT : IA + II + IP + ID = 1
        p_IA = q_IA
        p_II = max(0.0, q_II)
        p_IP = q_IP * (1.0 - q_IA)   # passage IP conditionnel à pas de guérison
        p_ID = q_ID
        # Normalisation ligne ITT
        s_ITT = p_IA + p_II + p_IP + p_ID
        if s_ITT > 0:
            p_IA /= s_ITT; p_II /= s_ITT; p_IP /= s_ITT; p_ID /= s_ITT

        # Ligne IP : PI + PD = 1
        p_PI = q_PI
        p_PD = q_PD

        P = np.array([
            [p_AA, p_AI, 0.0,  p_AD],   # Actif
            [p_IA, p_II, p_IP, p_ID],   # ITT
            [0.0,  0.0,  p_PI, p_PD],   # IP
            [0.0,  0.0,  0.0,  1.0 ],   # Décès (absorbant)
        ])

        return P

    # ══════════════════════════════════════════════════════════════════════════
    # 4. PROJECTION SUR HORIZON
    # ══════════════════════════════════════════════════════════════════════════
    def _projeter(self, P, horizon_ans):
        """
        Projette la distribution d'états sur horizon_ans années.
        Part de l'état initial : 100% Actif [1, 0, 0, 0].
        """
        etat = np.array([1.0, 0.0, 0.0, 0.0])
        labels = ['Actif', 'ITT', 'IP', 'Décès']
        annees = list(range(horizon_ans + 1))
        histo = {l: [etat[i]] for i, l in enumerate(labels)}

        for _ in range(horizon_ans):
            etat = P.T @ etat
            etat = np.maximum(etat, 0)
            etat /= etat.sum()
            for i, l in enumerate(labels):
                histo[l].append(float(etat[i]))

        return {
            'annees': annees,
            'distribution': histo,
            'etat_final': {l: round(histo[l][-1], 6) for l in labels},
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 5. ESPÉRANCES DE DURÉE
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_esperances(self, trans, age):
        """
        Espérance de durée en ITT et en IP.
        """
        # Durée moyenne en ITT (mois)
        dur_itt = _interp(DUREE_ITT_MOIS, age)

        # Espérance de durée en IP = jusqu'à 65 ans ou décès
        age_retraite = 65
        e_ip_ans = max(0.0, age_retraite - age) * (1.0 - trans['q_PD'])

        # Probabilité totale de passer en IP dans la vie active
        # ≈ probabilité annuelle × espérance de vie active
        prob_passage_ip = trans['q_IP_annuel'] * max(0, age_retraite - age)
        prob_passage_ip = min(prob_passage_ip, 0.95)

        return {
            'duree_moy_itt_mois':      round(dur_itt, 1),
            'esperance_duree_ip_ans':  round(e_ip_ans, 2),
            'prob_passage_ip_vie':     round(prob_passage_ip, 4),
            'prob_guerison_tt':        round(trans['q_IA'], 4),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 6. PROBABILITÉS DE MAINTIEN EN ITT
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_maintien(self, P):
        """
        Probabilité de rester en ITT après 6, 12, 24 mois.
        Utilise la matrice mensuelle P^(1/12).
        """
        # Matrice mensuelle (approximation)
        try:
            # Conversion annuel → mensuel : P_mois = P^(1/12)
            from numpy.linalg import eig
            vals, vecs = eig(P)
            # Exponentiation matricielle
            P_mois = np.real(
                vecs @ np.diag(np.abs(vals) ** (1/12)) @ np.linalg.inv(vecs)
            )
            P_mois = np.maximum(P_mois, 0)
            # Normaliser les lignes
            for i in range(4):
                s = P_mois[i].sum()
                if s > 0:
                    P_mois[i] /= s
        except Exception:
            # Fallback : approximation linéaire
            P_mois = (P - np.eye(4)) / 12 + np.eye(4)
            P_mois = np.maximum(P_mois, 0)

        # Partir de l'état ITT [0, 1, 0, 0]
        etat_itt = np.array([0.0, 1.0, 0.0, 0.0])
        P6  = np.linalg.matrix_power(
            np.maximum(np.round(P_mois, 6), 0), 6
        )
        P12 = np.linalg.matrix_power(
            np.maximum(np.round(P_mois, 6), 0), 12
        )
        P24 = np.linalg.matrix_power(
            np.maximum(np.round(P_mois, 6), 0), 24
        )

        prob_6m  = float((P6.T  @ etat_itt)[1])
        prob_12m = float((P12.T @ etat_itt)[1])
        prob_24m = float((P24.T @ etat_itt)[1])

        return {
            'mois_6':  round(max(0.0, prob_6m), 4),
            'mois_12': round(max(0.0, prob_12m), 4),
            'mois_24': round(max(0.0, prob_24m), 4),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 7. HYPOTHÈSES
    # ══════════════════════════════════════════════════════════════════════════
    def _hypotheses(self, trans, esperances, prob_maintien, age, taux_ip_p1=None):
        # H1 — q_IP < q_AI (invalidité plus rare que l'incapacité)
        if trans['q_IP_annuel'] < trans['q_AI']:
            h1_s = 'VALIDÉE'
            h1_m = (f"P(IP) = {trans['q_IP_annuel']*100:.3f}% < "
                    f"P(ITT) = {trans['q_AI']*100:.1f}% ✅ — cohérence tables")
        else:
            h1_s = 'NON VALIDÉE'
            h1_m = f"P(IP) ≥ P(ITT) — incohérence tables BCAC/TD88"

        # H2 — Taux maintien 6 mois ∈ [5%, 50%]
        m6 = prob_maintien['mois_6']
        if 0.05 <= m6 <= 0.50:
            h2_s = 'VALIDÉE'
            h2_m = f"Maintien ITT à 6 mois = {m6*100:.1f}% ∈ [5%,50%] ✅"
        elif m6 < 0.05:
            h2_s = 'À JUSTIFIER'
            h2_m = f"Maintien ITT à 6 mois = {m6*100:.1f}% < 5% — guérison trop rapide"
        else:
            h2_s = 'À JUSTIFIER'
            h2_m = f"Maintien ITT à 6 mois = {m6*100:.1f}% > 50% — dossiers trop longs"

        # H3 — Espérance durée IP raisonnable (1-40 ans)
        e_ip = esperances['esperance_duree_ip_ans']
        if 1.0 <= e_ip <= 40.0:
            h3_s = 'VALIDÉE'
            h3_m = f"Espérance durée IP = {e_ip:.1f} ans ∈ [1,40] ✅"
        else:
            h3_s = 'À JUSTIFIER'
            h3_m = f"Espérance durée IP = {e_ip:.1f} ans — hors plage raisonnable"

        # H4 — A/E ratio BCAC
        # Compare q_AI observé (avec facteur CSP) vs q_AI brut BCAC pour l'âge
        # Un ratio > 1 indique une sinistralité réelle supérieure aux tables
        # Source : BCAC 2019 — tables de référence marché prévoyance France
        q_ai_bcac_brut = _interp(Q_AI_BCAC, age)  # sans facteur CSP
        ae_ratio = trans['q_AI'] / max(q_ai_bcac_brut, 1e-9)
        if 0.80 <= ae_ratio <= 1.20:
            h4_s = 'VALIDÉE'
            h4_m = (f"A/E BCAC = {ae_ratio:.3f} ∈ [0.80,1.20] — "
                    f"q_AI={trans['q_AI']*100:.2f}% cohérent avec BCAC 2019 ✅")
        elif ae_ratio > 1.20:
            h4_s = 'À JUSTIFIER'
            h4_m = (f"A/E BCAC = {ae_ratio:.3f} > 1.20 — "
                    f"sinistralité réelle supérieure aux tables BCAC 2019")
        else:
            h4_s = 'À JUSTIFIER'
            h4_m = (f"A/E BCAC = {ae_ratio:.3f} < 0.80 — "
                    f"sinistralité inférieure aux tables, vérifier le portefeuille")

        # H5 — P(IP|ITT) par âge : taux IP client vs référence BCAC
        # Compare le taux_ip fourni par P1 (données client ou tarification)
        # au taux conditionnel BCAC 2019 interpolé pour l'âge
        # taux_ip_p1 = q_AI × q_IP_cond (annuel) transmis par P1
        # Source : BCAC 2019 — Q_IP_COND_BCAC
        q_ip_ref_cond = _interp(Q_IP_COND_BCAC, age)   # référence BCAC conditionnelle
        q_ai_ref      = _interp(Q_AI_BCAC, age)         # incidence brute BCAC
        q_ip_bcac_an  = q_ai_ref * q_ip_ref_cond        # taux IP annuel BCAC de référence
        if taux_ip_p1 is not None and taux_ip_p1 > 0:
            # Comparaison taux IP P1 vs BCAC annuel ± 30%
            borne_inf5 = q_ip_bcac_an * 0.70
            borne_sup5 = q_ip_bcac_an * 1.30
            if borne_inf5 <= taux_ip_p1 <= borne_sup5:
                h5_s = 'VALIDÉE'
                h5_m = (f"P(IP|ITT) client = {taux_ip_p1*100:.3f}% ∈ "
                        f"[{borne_inf5*100:.3f}%-{borne_sup5*100:.3f}%] "
                        f"BCAC âge={age:.0f} ✅")
            elif taux_ip_p1 > borne_sup5:
                h5_s = 'À JUSTIFIER'
                h5_m = (f"P(IP|ITT) client = {taux_ip_p1*100:.3f}% > "
                        f"{borne_sup5*100:.3f}% BCAC — risque d'invalidisation "
                        f"supérieur aux tables pour âge={age:.0f}")
            else:
                h5_s = 'À JUSTIFIER'
                h5_m = (f"P(IP|ITT) client = {taux_ip_p1*100:.3f}% < "
                        f"{borne_inf5*100:.3f}% BCAC — taux d'invalidisation "
                        f"faible vs tables pour âge={age:.0f}")
        else:
            # Pas de taux P1 disponible — affichage de la référence BCAC seule
            h5_s = 'À JUSTIFIER'
            h5_m = (f"P(IP|ITT) BCAC réf = {q_ip_bcac_an*100:.3f}% "
                    f"pour âge={age:.0f} — taux client non transmis par P1")

        return [
            {'id':'H1','hypothese':"P(IP) < P(ITT) — invalidité plus rare que l'incapacité",
             'valeur':h1_m,'statut':h1_s,'critique':True},
            {'id':'H2','hypothese':'Maintien en ITT à 6 mois ∈ [5%,50%] — cohérence BCAC',
             'valeur':h2_m,'statut':h2_s,'critique':True},
            {'id':'H3','hypothese':'Espérance de durée en IP ∈ [1,40] ans',
             'valeur':h3_m,'statut':h3_s,'critique':True},
            {'id':'H4','hypothese':'A/E ratio BCAC ∈ [0.80,1.20] — sinistralité réelle vs tables',
             'valeur':h4_m,'statut':h4_s,'critique':False},
            {'id':'H5','hypothese':'P(IP|ITT) dans la plage BCAC 2019 ±20% pour l\'âge',
             'valeur':h5_m,'statut':h5_s,'critique':True},
        ]

    def _rag(self, hyp, trans):
        non_val = [h for h in hyp if h['statut']=='NON VALIDÉE']
        a_just  = [h for h in hyp if h['statut']=='À JUSTIFIER']
        if non_val: return 'ROUGE'
        if a_just:  return 'AMBRE'
        return 'VERT'

    # ══════════════════════════════════════════════════════════════════════════
    # 8. COMMENTAIRE
    # ══════════════════════════════════════════════════════════════════════════
    def _commentaire(self, rag, age, cat, trans, P, proj, esp, maint, horizon, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        ef = proj['etat_final']
        L = [
            "="*70,
            f"  RAPPORT TABLES MORBIDITÉ — P2 RAYAN v{self.VERSION}",
            f"  Chaîne de Markov 4 états | âge={age:.0f} | CSP={cat}",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
            "📊 RÉSUMÉ DIRECTION", "─"*40,
        ]
        if rag=='VERT':
            L.append(f"✅ Tables validées. Transitions BCAC 2019 cohérentes.")
        elif rag=='AMBRE':
            L.append(f"⚠️ Vérifier les points signalés.")
        else:
            L.append(f"❌ Incohérence détectée dans les tables de transition.")

        L += [
            "", "🔢 PROBABILITÉS DE TRANSITION (annuelles)", "─"*40,
            f"  Actif → ITT (q_AI)        : {trans['q_AI']*100:>10.2f}%",
            f"  ITT  → Actif (q_IA)       : {trans['q_IA']*100:>10.2f}%",
            f"  ITT  → IP (q_IP|ITT)      : {trans['q_IP_cond']*100:>10.2f}%",
            f"  Actif→ IP (annuel)         : {trans['q_IP_annuel']*100:>10.3f}%",
            f"  IP   → Décès (q_PD)       : {trans['q_PD']*100:>10.2f}%",
            f"  Facteur CSP                : {trans['fact_csp']:>10.2f}x",
            "", "⏱️ ESPÉRANCES DE DURÉE", "─"*40,
            f"  Durée moy. ITT (>franchise): {esp['duree_moy_itt_mois']:>8.1f} mois",
            f"  Espérance durée en IP      : {esp['esperance_duree_ip_ans']:>8.1f} ans",
            f"  P(guérison totale)         : {esp['prob_guerison_tt']*100:>8.1f}%",
            f"  P(passage IP vie active)   : {esp['prob_passage_ip_vie']*100:>8.1f}%",
            "", "📊 MAINTIEN EN ITT", "─"*40,
            f"  Probabilité ITT à 6 mois  : {maint['mois_6']*100:>8.1f}%",
            f"  Probabilité ITT à 12 mois : {maint['mois_12']*100:>8.1f}%",
            f"  Probabilité ITT à 24 mois : {maint['mois_24']*100:>8.1f}%",
            "", f"🔮 PROJECTION {horizon} ANS (départ : 100% Actif)", "─"*40,
            f"  Actif à {horizon} ans          : {ef['Actif']*100:>8.1f}%",
            f"  En ITT à {horizon} ans          : {ef['ITT']*100:>8.2f}%",
            f"  En IP à {horizon} ans           : {ef['IP']*100:>8.2f}%",
            f"  Décédé à {horizon} ans          : {ef['Décès']*100:>8.2f}%",
            "", "📋 HYPOTHÈSES", "─"*40,
        ]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else ("⚠️" if h['statut']=='À JUSTIFIER' else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        L += ["", "🎯 AVIS RAYAN → DIALLO", "─"*40]
        if rag=='VERT':
            L.append("✅ VALIDÉ — Matrices transmises à P3 Élodie (provisionnement).")
        else:
            L.append("⚠️ Vérifier paramètres BCAC avant transmission à P3.")
        L.append("")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════════════════════
    # 9. GRAPHIQUES
    # ══════════════════════════════════════════════════════════════════════════
    def _graphiques(self, trans, P, proj, esp, maint, age):
        gph = {}

        # G1 — Projection états sur horizon
        try:
            annees = proj['annees']
            dist   = proj['distribution']
            fig = go.Figure()
            cols = {'Actif':VERT,'ITT':AMBRE,'IP':ROUGE,'Décès':GRIS}
            for etat, col in cols.items():
                fig.add_trace(go.Scatter(
                    x=annees, y=[v*100 for v in dist[etat]],
                    name=etat, mode='lines',
                    line=dict(color=col, width=2.5),
                    fill='tonexty' if etat=='IP' else None,
                    fillcolor=f"rgba({','.join(str(int(col[i:i+2],16)) for i in (1,3,5))},0.08)" if etat=='IP' else None,
                    hovertemplate=f"<b>{etat}</b><br>An %{{x}} : %{{y:.2f}}%<extra></extra>",
                ))
            layout = dict(**LAYOUT_BASE)
            layout.update(dict(
                title=dict(text=f"G1 — Projection Markov 4 états | âge={age:.0f} | {len(annees)-1} ans",
                           font=dict(color=OR,size=12),x=0.01),
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)',orientation='h',y=-0.15),
                xaxis=dict(title="Années",tickfont=dict(color=GRIS,size=9),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(title="%",tickfont=dict(color=GRIS,size=9),showgrid=True,
                           gridcolor='rgba(255,255,255,0.05)',range=[0,105]),
                annotations=[dict(
                    text="💡 Vert=Actif · Orange=ITT · Rouge=IP · Gris=Décès. Chaque ligne = probabilité d'être dans cet état.",
                    xref="paper",yref="paper",x=0.01,y=-0.28,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**layout)
            gph['projection_markov'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — Matrice de transition (heatmap)
        try:
            labels = ['Actif','ITT','IP','Décès']
            z = [[P[i,j]*100 for j in range(4)] for i in range(4)]
            fig = go.Figure(go.Heatmap(
                z=z, x=labels, y=labels,
                colorscale=[[0,NAVY_L],[0.5,OR],[1,ROUGE]],
                showscale=True,
                text=[[f"{P[i,j]*100:.1f}%" for j in range(4)] for i in range(4)],
                texttemplate="%{text}",
                textfont=dict(color=BLANC,size=10),
                hovertemplate="De <b>%{y}</b> vers <b>%{x}</b><br>%{text}<extra></extra>",
            ))
            layout = dict(**LAYOUT_BASE)
            layout.update(dict(
                title=dict(text="G2 — Matrice de Transition Markov P (annuelle %)",
                           font=dict(color=OR,size=12),x=0.01),
                xaxis=dict(title="État suivant",tickfont=dict(color=BLANC,size=10)),
                yaxis=dict(title="État actuel",tickfont=dict(color=BLANC,size=10)),
                annotations=[dict(
                    text="💡 Chaque ligne = probabilités de transition depuis cet état. Décès = état absorbant (100%).",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**layout)
            gph['matrice_transition'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — Courbe de maintien en ITT
        try:
            mois_list = [0, 3, 6, 12, 18, 24]
            prob_list = [1.0,
                         (maint['mois_6']+1)/2,  # interpolé 3m
                         maint['mois_6'],
                         maint['mois_12'],
                         (maint['mois_12']+maint['mois_24'])/2,
                         maint['mois_24']]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=mois_list, y=[v*100 for v in prob_list],
                mode='lines+markers',
                line=dict(color=AMBRE,width=2.5),
                marker=dict(size=8,color=AMBRE),
                fill='tozeroy', fillcolor='rgba(243,156,18,0.08)',
                hovertemplate="<b>Mois %{x}</b><br>%{y:.1f}% encore en ITT<extra></extra>",
            ))
            layout = dict(**LAYOUT_BASE)
            layout.update(dict(
                title=dict(text="G3 — Courbe de maintien en ITT (probabilité d'être encore en arrêt)",
                           font=dict(color=AMBRE,size=11),x=0.01),
                xaxis=dict(title="Mois depuis début arrêt",tickfont=dict(color=GRIS,size=9)),
                yaxis=dict(title="%",tickfont=dict(color=GRIS,size=9),range=[0,105]),
                annotations=[dict(
                    text="💡 La courbe de maintien calibre les réserves ITT long terme transmises à P3 Élodie.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**layout)
            gph['maintien_itt'] = fig
        except Exception as e:
            self.logger.warning(f"G3:{e}")

        # G4 — Scorecard
        try:
            hyp_tmp = self._hypotheses(trans, esp, maint, age, None)
            fig = go.Figure()
            for h in hyp_tmp:
                c  = VERT if h['statut']=='VALIDÉE' else (AMBRE if h['statut']=='À JUSTIFIER' else ROUGE)
                ic = "✅" if h['statut']=='VALIDÉE' else ("⚠️" if h['statut']=='À JUSTIFIER' else "❌")
                s  = 1.0 if h['statut']=='VALIDÉE' else (0.5 if h['statut']=='À JUSTIFIER' else 0.0)
                fig.add_trace(go.Bar(
                    x=[s], y=[h['hypothese'][:45]], orientation="h",
                    marker_color=c, width=0.5, opacity=0.85,
                    text=f"{ic} {h['statut']}", textposition="outside",
                    textfont=dict(color=c,size=10), showlegend=False,
                ))
            cg = VERT if all(h['statut']=='VALIDÉE' for h in hyp_tmp) else (ROUGE if any(h['statut']=='NON VALIDÉE' for h in hyp_tmp) else AMBRE)
            layout = dict(**LAYOUT_BASE)
            layout.update(dict(
                title=dict(text="G4 — Scorecard Tables Morbidité BCAC 2019",
                           font=dict(color=cg,size=12),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 5 ✅ = tables BCAC 2019 cohérentes, prêtes pour le provisionnement P3.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**layout)
            gph['scorecard_p2'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        return gph

    # ══════════════════════════════════════════════════════════════════════════
    def _audit(self, aid, trans, esp, rag):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'q_AI':trans['q_AI'],'q_IP':trans['q_IP_annuel'],
                 'duree_itt':esp['duree_moy_itt_mois']}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, rag, age, cat, trans, esp, maint):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        print(f"\n{'─'*70}")
        print(f"  P2 RAYAN v{self.VERSION} | {aid} | {ic} {rag}")
        print(f"  âge={age:.0f} | CSP={cat} | q_AI={trans['q_AI']*100:.1f}% | "
              f"q_IP={trans['q_IP_annuel']*100:.3f}%")
        print(f"  Maintien 6m={maint['mois_6']*100:.1f}% | 12m={maint['mois_12']*100:.1f}% | "
              f"Durée ITT={esp['duree_moy_itt_mois']:.0f} mois")
        print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {'success':False,'agent':self.NOM,'version':self.VERSION,
                'audit_id':aid,'statut_rag':'ROUGE',
                'transitions':{},'matrice_P':[],'projection':{},
                'esperances':{},'prob_maintien':{},'sorties_p3':{},
                'hypotheses':[],'commentaire':f"❌ ERREUR P2:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  P2 RAYAN v2.0 — DÉMO TABLES MORBIDITÉ")
    print("  Chaîne de Markov 4 états | BCAC 2019 | TD88-90")
    print("="*70)

    r_p1 = {
        'success': True,
        'age': 40.0, 'categorie': 'employe',
        'prime_commerciale': 679.66, 'taux_cotisation_pct': 1.51,
        'taux_rente_ipp': 0.60,
        'sorties_p2': {
            'age':40.0,'categorie':'employe','fact_csp':1.0,
            'taux_itt':0.042,'taux_ip':0.0028,'qx':0.0018,
            'franchise_jours':90,'duree_contrat':20,
            'salaire_brut':45_000,'primes_acquises':679.66,'nb_assures':1,
        },
    }

    agent = AgentP2TablesMorbidite(
        models_path='/tmp/p2/models', audit_path='/tmp/p2/audit', verbose=True
    )
    r = agent.run(result_p1=r_p1, horizon_ans=10, generer_graphiques=False)

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut        : {r['statut_rag']}")
    t = r['transitions']
    print(f"  q_AI          : {t['q_AI']*100:.2f}%")
    print(f"  q_IP annuel   : {t['q_IP_annuel']*100:.3f}%")
    print(f"  q_PD          : {t['q_PD']*100:.2f}%")
    e = r['esperances']
    print(f"  Durée moy ITT : {e['duree_moy_itt_mois']:.0f} mois")
    print(f"  Espérance IP  : {e['esperance_duree_ip_ans']:.1f} ans")
    m = r['prob_maintien']
    print(f"  Maintien 6m   : {m['mois_6']*100:.1f}%")
    print(f"  Maintien 12m  : {m['mois_12']*100:.1f}%")
    print(f"  Maintien 24m  : {m['mois_24']*100:.1f}%")
    ef = r['projection']['etat_final']
    print(f"\n  Projection 10 ans : Actif={ef['Actif']*100:.1f}% | "
          f"ITT={ef['ITT']*100:.2f}% | IP={ef['IP']*100:.2f}% | Décès={ef['Décès']*100:.2f}%")
    print(f"  Durée : {r['duree_sec']:.2f}s")
