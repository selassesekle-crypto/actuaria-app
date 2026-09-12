# Migré depuis sp4_tarification_prevoyance.py → direction_sante_prevoyance/prevoyance/p1_tarification/agent.py
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

# ── Tables actuarielles — importées depuis le service centralisé ─────────
# Source unique : sp_tables_actuarielles.py — évite la duplication entre agents
try:
    from direction_sante_prevoyance.services.sp_tables_actuarielles import (
        get_taux_itt_bcac   as _get_taux_itt,
        get_taux_ip_td8890  as _get_taux_ip,
        get_qx_th0002       as _get_qx,
        BCAC_2019_TAUX_ITT, TD_8890_TAUX_IP, TH0002_QX,
    )
    # Facteur CSP residuel : la table centralisee porte deja le groupe.
    from direction_sante_prevoyance.services.sp_csp import facteur_residuel
    # Mortalite de tarification : unisexe par defaut, base publiee.
    from direction_sante_prevoyance.services.sp_mortalite import (
        part_hommes, qx_tarification,
    )
    _TABLES_CENTRALISEES = True
except ImportError:
    _TABLES_CENTRALISEES = False

# ── Financement patronal ───────────────────────────────────────────────────
# Une mention de conformite se CALCULE, et seulement la ou le texte
# s applique. Voir services/sp_ani.py.
try:
    from ...services.sp_ani import part_patronale_conforme
except ImportError:  # execution directe du module, hors paquet
    from direction_sante_prevoyance.services.sp_ani import (
        part_patronale_conforme,
    )

# ── Trace console tolerante a l encodage ─────────────────────────────────────
# `tracer` remplace `print` : identique a l usage, mais incapable de lever sur
# une console etroite (cp1252). Sans lui, un simple caractere de statut faisait
# echouer tout le calcul de cet agent. Voir services/sp_console.py.
try:
    from ...services.sp_console import tracer
except ImportError:  # execution directe du module, hors paquet
    from direction_sante_prevoyance.services.sp_console import tracer

# ── Tables actuarielles locales (fallback) ────────────────────────────────
# Source primaire : sp_tables_actuarielles.py (services centralisés)
# Source : BCAC 2019 — Bureau Commun des Assurances Collectives
#   Publication : « Statistiques arrêts de travail 2019 »
#   Taux d'incidence ITT annuels par âge et CSP (simplifiés)
TAUX_ITT_BCAC = {
    25:0.020, 30:0.025, 35:0.032, 40:0.042,
    45:0.055, 50:0.072, 55:0.095, 60:0.120,
}
# Source : TD 88-90 — Tables INSEE de maintien en incapacité
#   Probabilités annuelles de passage ITT → IP (invalidité permanente)
#   Calibrées sur la population active française (simplifiées)
TAUX_IP_TD88 = {
    25:0.0008, 30:0.0012, 35:0.0018, 40:0.0028,
    45:0.0045, 50:0.0072, 55:0.0115, 60:0.0180,
}
# Source : TH 00-02 — Tables de mortalité réglementaires françaises
#   BCAC / INSEE — taux annuels de décès toutes causes, hommes
#   Base : population assurée France 2000-2002
QX_TH0002 = {
    25:0.000730, 30:0.000860, 35:0.001180, 40:0.001800,
    45:0.002980, 50:0.005040, 55:0.008640, 60:0.014500, 65:0.023800,
}
# Facteurs CSP sur sinistralité ITT — source BCAC 2019
# Ouvriers : +35% vs employés | Cadres : -25% | Cadres sup : -40%
# Reflète conditions de travail et exposition au risque arrêt
FACT_CSP_ITT = {
    "ouvrier":   1.35, "employe": 1.00,
    "cadre":     0.75, "cadre_sup": 0.60,
}
# Taux d'actualisation annuités IP — proxy courbe EIOPA RFR
# Source : EIOPA Risk-Free Rate (EUR) — moyenne long terme ~2.5%
# À remplacer par la courbe EIOPA réelle en production
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
            # ⚠️ AJOUTE LE 12/09/2026 (D05) — le taux etait un LITTERAL 0.60,
            # et la mention de conformite une CHAINE CONSTANTE a cote. Quelle
            # que soit la repartition reelle du contrat client, le document
            # publiait « 60 % — conforme ». Mesure : en faisant varier la
            # prime, la garantie et la population, la chaine ne bougeait
            # jamais. C'est un controle qui atteste sans surveiller.
            part_patronale_pct: float = 0.60,
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
            # CSP retenue pour le tarif : la DOMINANTE, nommee comme telle.
            # Lire `profils[0]` ne marchait que parce que toutes les
            # categories venaient d etre ecrasees par la dominante.
            from collections import Counter as _Cnt
            _repart_p1 = _Cnt(p['categorie'] for p in profils)
            cat_m      = _repart_p1.most_common(1)[0][0]
            nb_assures = len(profils)

            self.logger.info(
                f"[{aid}] P1 Axel | {nb_assures} assuré(s) | "
                f"âge moy={age_m:.1f} | sal={salaire_m:,.0f}€ | CSP={cat_m}"
            )

            # ── 2. TAUX ACTUARIELS ────────────────────────────────────────────
            # Part d'hommes du portefeuille, si le sexe est renseigne.
            # `None` signifie « non observe » : la base publiee le dira.
            _part_h = part_hommes(profils)
            fact_csp = FACT_CSP_ITT.get(cat_m, 1.0)
            if _TABLES_CENTRALISEES:
                # ⚠️ CORRIGÉ LE 12/09/2026 — le facteur CSP était compté DEUX
                # fois. `get_taux_itt_bcac` rend un taux DÉJÀ différencié par
                # colonne cadre / non-cadre ; le remultiplier par le facteur
                # fin recomptait le groupe. Mesure : +35,0 % (ouvrier),
                # −25,0 % (cadre), −40,0 % (cadre sup.), à tout âge.
                # Le facteur ne porte plus que l'écart RÉSIDUEL au groupe,
                # ce qui conserve la finesse à quatre catégories sans
                # recompter la colonne. Voir services/sp_csp.py.
                _csp_arg, _resid = facteur_residuel(cat_m, FACT_CSP_ITT)
                taux_itt = _get_taux_itt(age_m, _csp_arg) * _resid
                # TD 88-90 n'est pas différenciée par CSP : le facteur fin y
                # reste entier, et c'est volontaire.
                taux_ip  = _get_taux_ip(age_m) * fact_csp
                qx, base_mortalite = qx_tarification(
                    age_m, _get_qx, part_h=_part_h)
            else:
                # Repli : la table locale n'a qu'UNE colonne, toutes CSP
                # confondues. Le facteur plein y est légitime — ne pas y
                # toucher était le risque principal de ce correctif.
                taux_itt = _interp(TAUX_ITT_BCAC, age_m) * fact_csp
                taux_ip  = _interp(TAUX_IP_TD88,  age_m) * fact_csp
                qx       = _interp(QX_TH0002,     age_m)
                base_mortalite = (
                    'table locale QX_TH0002 (repli) — base masculine, '
                    'non unisexe')

            # ── 3. PRIME ITT ──────────────────────────────────────────────────
            sal_men      = salaire_m / 12
            # Durée moyenne BCAC 2019 :
            # - Tous arrêts : 45j (dont beaucoup < franchise)
            # - Arrêts > franchise : 180j (dossiers graves qui "passent" la franchise)
            # La prime ITT ne couvre que les arrêts dépassant la franchise
            # Probabilité de dépassement calibrée sur BCAC 2019
            # Distribution des durées : approximation exponentielle
            # P(durée > franchise) ≈ exp(-franchise/duree_moy_tous_arrets)
            # BCAC 2019 : durée moyenne tous arrêts = 45j
            # => P(>90j) ≈ exp(-90/45) ≈ 13.5% | P(>180j) ≈ exp(-180/45) ≈ 1.8%
            duree_moy_arrets  = 45.0  # jours — tous arrêts BCAC 2019
            prob_depasse      = float(np.exp(-franchise_jours / max(duree_moy_arrets, 1)))
            # Durée résiduelle conditionnelle E[D - franchise | D > franchise]
            # Pour loi exponentielle : E[D-f | D>f] = duree_moy (propriété sans mémoire)
            jours_residuels   = duree_moy_arrets  # durée résiduelle espérée
            indemnite_j       = sal_men * 0.80 / 30  # 80% salaire / jour
            prime_itt         = taux_itt * prob_depasse * jours_residuels * indemnite_j

            # ── 4. PRIME IP ───────────────────────────────────────────────────
            age_retraite  = 65
            v             = 1.0 / (1 + TAUX_ACTUALISATION)
            duree_rente   = max(0, age_retraite - age_m)
            annuite_ip    = sum(v**k for k in range(int(duree_rente)))
            rente_ip_an   = salaire_m * taux_rente_ipp
            # ⚠️ CORRIGÉ LE 12/09/2026 — la prime IP était divisée par la
            # durée du contrat, PAS la prime ITT, alors que les deux partent
            # d'un taux d'entrée ANNUEL. `annuite_ip` porte déjà la durée de
            # service de la rente ; rediviser par la durée du CONTRAT
            # mélangeait une prime annuelle et une prime unique.
            # Mesuré avant correction, même assuré, seule la durée variant :
            #   1 an  1 937,60 EUR   |   20 ans  96,88 EUR   (rapport 20,0x)
            # Le RAG ne discriminait pas : il était ROUGE dans les quatre cas,
            # y compris à 1 an où la prime était juste.
            prime_ip      = taux_ip * rente_ip_an * annuite_ip

            # ── 5. PRIME DÉCÈS ────────────────────────────────────────────────
            # Capital décès différencié par CSP — référence marché IP France (CTIP 2023)
            # Cadres/cadres sup (CCN Cadres 1947) : 3-4 × salaire brut
            # Employés/ouvriers (accords de branche) : 1-2 × salaire brut
            _mult_dc = {'cadre_sup': 4.0, 'cadre': 3.0, 'employe': 1.5, 'ouvrier': 1.0}
            capital_deces  = salaire_m * _mult_dc.get(cat_m, 1.5)
            prime_deces    = qx * capital_deces

            # ── 6. TOTAUX ─────────────────────────────────────────────────────
            prime_pure     = prime_itt + prime_ip + prime_deces
            prime_comm     = prime_pure * (1 + chargement_pct)
            prime_mois     = prime_comm / 12
            taux_cot       = prime_comm / max(salaire_m, 1) * 100
            taux_patronal  = max(0.0, min(1.0, float(part_patronale_pct)))
            part_patronale = prime_comm * taux_patronal
            part_salariale = prime_comm - part_patronale
            # ⚠️ L art. L911-7 CSS impose 50 % de financement patronal EN
            # FRAIS DE SANTE. L etendre a la prevoyance est une extension que
            # le texte ne fait pas — sur un sujet ou un controleur verifiera
            # la source. `part_patronale_conforme` rend donc HORS CHAMP ici,
            # et non « conforme ». Voir services/sp_ani.py.
            statut_patronal, mention_patronale = part_patronale_conforme(
                taux_patronal, nature="prevoyance")
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
                taux_itt, taux_ip, qx, franchise_jours, hyp,
                mention_pat=mention_patronale,
            )

            # ── 9. GRAPHIQUES ─────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    prime_itt, prime_ip, prime_deces,
                    prime_comm, salaire_m, taux_cot, hyp,
                    part_pat=part_patronale, part_sal=part_salariale,
                    pct_pat=taux_patronal,
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
                'part_patronale_pct': round(taux_patronal, 4),
                'statut_financement_patronal': statut_patronal,
                'mention_financement_patronal': mention_patronale,
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
                    # La base de mortalite voyage AVEC le taux : un
                    # lecteur doit savoir si le tarif est unisexe.
                    'base_mortalite': base_mortalite,
                    'part_hommes':    _part_h,
                    # Composition reelle : le tarif porte sur la CSP
                    # dominante, et le lecteur doit savoir laquelle et
                    # quelle part du portefeuille elle represente.
                    'repartition_csp': dict(_repart_p1),
                    'part_csp_retenue': (
                        _repart_p1[cat_m] / max(nb_assures, 1)),
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

            # CSP dominante
            #
            # ⚠️ CORRIGÉ LE 12/09/2026. Le code écrasait la catégorie RÉELLE de
            # chaque assuré par la catégorie dominante :
            #     for p in profils: p['categorie'] = csp_dom
            # La ventilation par CSP publiée plus loin ne contenait donc plus
            # qu'une seule catégorie, et se contredisait elle-même. La
            # tarification porte bien sur un profil moyen — c'est assumé — mais
            # la composition réelle du portefeuille ne doit pas être détruite
            # pour autant : elle est conservée et publiée.
            from collections import Counter
            _repartition = Counter(p['categorie'] for p in profils)
            csp_dom = _repartition.most_common(1)[0][0]
            for p in profils:
                p['csp_retenue_tarif'] = csp_dom

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
                     t_itt, t_ip, qx, franchise, hyp,
                     mention_pat=""):
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
            "", "🤝 RÉPARTITION EMPLOYEUR / SALARIÉ", "─"*40,
            f"  Part patronale             : {part_pat:>12.2f}€/an",
            f"  Part salariale             : {part_sal:>12.2f}€/an",
            f"  → {mention_pat}",
            "", "📋 HYPOTHÈSES", "─"*40,
        ]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else ("❌" if h['statut']=='NON VALIDÉE' else "⚠️")
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
    def _graphiques(self, p_itt, p_ip, p_deces, p_comm, salaire, taux_cot,
                    hyp, part_pat=None, part_sal=None, pct_pat=0.60):
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
            part_pat = p_comm * pct_pat if part_pat is None else part_pat
            part_sal = p_comm - part_pat if part_sal is None else part_sal
            fig = go.Figure(go.Bar(
                x=[f"Part patronale ({pct_pat*100:.0f}%)",
                   f"Part salariale ({(1-pct_pat)*100:.0f}%)"],
                y=[part_pat, part_sal],
                marker_color=[VERT, BLEU], width=0.4, opacity=0.88,
                text=[f"{part_pat:.0f}€", f"{part_sal:.0f}€"],
                textposition="outside", textfont=dict(color=BLANC,size=12),
            ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G3 — Répartition prime patronale / salariale",
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
        tracer(f"\n{'─'*70}")
        tracer(f"  P1 AXEL v{self.VERSION} | {aid} | {ic} {rag}")
        tracer(f"  Prime pure={pp:.2f}€ | Commerciale={pc:.2f}€ | Taux cot.={taux_cot:.2f}%")
        tracer(f"  Taux ITT={t_itt*100:.1f}% | {nb} assuré(s)")
        tracer(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {'success':False,'agent':self.NOM,'version':self.VERSION,
                'audit_id':aid,'statut_rag':'ROUGE',
                'primes_pures':{'itt':0,'ip':0,'deces':0,'total':0},
                'prime_commerciale':0,'taux_cotisation_pct':0,
                'sorties_p2':{},'hypotheses':[],'commentaire':f"❌ ERREUR P1:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    from direction_sante_prevoyance.services.sp_console import (
        repertoire_demonstration)
    _DEMO = repertoire_demonstration('p1')
    tracer("="*70)
    tracer("  P1 AXEL v2.0 — DÉMO TARIFICATION PRÉVOYANCE ITT/IP/DÉCÈS")
    tracer("  BCAC 2019 | TD88-90 | TH0002 | Branchement A2 | ANI 2013")
    tracer("="*70)

    agent = AgentP1TarificationPrevoyance(
        models_path=_DEMO/'models', audit_path=_DEMO/'models', verbose=True
    )
    r = agent.run(
        result_a2=None,
        age=40, salaire_brut=45_000, categorie="employe",
        franchise_jours=90, taux_rente_ipp=0.60, duree_contrat=20,
        chargement_pct=0.20, generer_graphiques=False,
    )

    tracer(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    tracer(f"  Statut       : {r['statut_rag']}")
    pp = r['primes_pures']
    tracer(f"  Prime ITT    : {pp['itt']:>10.2f}€/an")
    tracer(f"  Prime IP     : {pp['ip']:>10.2f}€/an")
    tracer(f"  Prime Décès  : {pp['deces']:>10.2f}€/an")
    tracer(f"  Prime pure   : {pp['total']:>10.2f}€/an")
    tracer(f"  Prime comm.  : {r['prime_commerciale']:>10.2f}€/an ({r['prime_mensuelle']:.2f}€/mois)")
    tracer(f"  Taux cot.    : {r['taux_cotisation_pct']:>9.2f}%")
    tracer(f"\n  Taux ITT BCAC: {r['taux_sinistralite']['itt']*100:.1f}%")
    tracer(f"  Taux IP TD88 : {r['taux_sinistralite']['ip']*100:.3f}%")
    tracer(f"  qx TH0002    : {r['taux_sinistralite']['deces']*100:.4f}%")
    tracer(f"\n  Sorties P2   : âge={r['sorties_p2']['age']} | CSP={r['sorties_p2']['categorie']}")
    tracer(f"  Durée        : {r['duree_sec']:.2f}s")
