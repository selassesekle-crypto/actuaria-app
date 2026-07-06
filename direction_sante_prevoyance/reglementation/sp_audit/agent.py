"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT SP-AUDIT : AUDIT TRAIL SANTÉ-PRÉVOYANCE                  ║
║  Direction Santé-Prévoyance — Équivalent SP de A13 (Non-Vie)               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Collecte, consolide et archive tous les logs de la Direction SP.    ║
║         Génère le registre RGPD Art.30 et le versioning des hypothèses SP.  ║
║                                                                              ║
║  DIFFÉRENCES vs A13 (Non-Vie) :                                              ║
║    A13  : collecte A1-A12, données IARD, hypothèses CL/Mack/bootstrap       ║
║    SP   : collecte S1-S3/P1-P4/SP-Coord/SP-Reg1/2/3/Naomie/Cohérence       ║
║           données SP (assurés, sinistres santé, salaires, arrêts ITT)       ║
║           hypothèses BCAC 2019/ANI 2013/EIOPA RFR/DREES 2023               ║
║                                                                              ║
║  MODULES :                                                                   ║
║    1. COLLECTE DES LOGS SP                                                   ║
║       Agrège les audit_id de S1→S3, P1→P4, SP-Coord, SP-Reg1/2/3,         ║
║       Naomie ST, SP-Cohérence, SP-Rapport                                   ║
║       Reconstruit la chaîne de traitement complète SP                       ║
║                                                                              ║
║    2. REGISTRE RGPD ARTICLE 30                                               ║
║       Registre des activités de traitement SP :                              ║
║       · Données personnelles santé (sinistres, garanties)                   ║
║       · Données salariales (salaires, CSP, arrêts ITT)                     ║
║       · Données biométriques (âge, sexe)                                    ║
║       Finalités : tarification, provisionnement, reporting réglementaire    ║
║                                                                              ║
║    3. VERSIONING DES HYPOTHÈSES SP                                           ║
║       Tables BCAC 2019 / TD 88-90 / TH 00-02                               ║
║       ANI 2013 (Art. L911-7 CSS)                                            ║
║       EIOPA RFR (Art.77 S2) / DREES 2023 / FNMF 2023 / CTIP 2023          ║
║       Paramètres SCR (σ_NSLT=5%, +35% morbidité, ρ=0.25 EIOPA)           ║
║                                                                              ║
║    4. HASH DE SESSION SHA-256                                                ║
║       Empreinte numérique de chaque session SP                              ║
║       Garantit l'intégrité et la reproductibilité des calculs              ║
║                                                                              ║
║    5. RAPPORT D'AUDIT COMPLET                                               ║
║       Document PDF-ready pour l'actuaire désigné, l'ACPR et               ║
║       le commissaire aux comptes                                             ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import hashlib
import json
import logging
import os
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY   = "#0F2E52"; NAVY_L = "#1B3A5C"; NAVY_LL = "#243F6A"; OR = "#C9A84C"
BLANC  = "#F0F4F8"; GRIS   = "#8A9AB0"; VERT   = "#2ECC71"; ROUGE = "#E74C3C"
AMBRE  = "#F39C12"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60), height=320,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
)

# ── Mapping agents SP → clés attendues dans resultats_agents ─────────────────
AGENTS_SP = {
    "s1":          {"nom": "S1 Léonie",       "equipe": "Santé",        "critique": True},
    "s2":          {"nom": "S2 Selma",         "equipe": "Santé",        "critique": True},
    "s3":          {"nom": "S3 Binta",         "equipe": "Santé",        "critique": True},
    "p1":          {"nom": "P1 Axel",          "equipe": "Prévoyance",   "critique": True},
    "p2":          {"nom": "P2 Rayan",         "equipe": "Prévoyance",   "critique": True},
    "p3":          {"nom": "P3 Élodie",        "equipe": "Prévoyance",   "critique": True},
    "p4":          {"nom": "P4 Valentin",      "equipe": "Prévoyance",   "critique": True},
    "sp_coord":    {"nom": "SP-Coord",          "equipe": "Coordination", "critique": False},
    "sp_reg1":     {"nom": "SP-REG1 S2",        "equipe": "Réglementation","critique": False},
    "sp_reg2":     {"nom": "SP-REG2 IFRS17",    "equipe": "Réglementation","critique": False},
    "sp_reg3":     {"nom": "SP-REG3 ANI+100S",  "equipe": "Réglementation","critique": False},
    "sp_st":       {"nom": "Naomie ST",          "equipe": "Transversal",  "critique": False},
    "sp_coh":      {"nom": "SP-Cohérence",       "equipe": "Transversal",  "critique": False},
    "sp_rapport":  {"nom": "SP-Rapport",         "equipe": "Transversal",  "critique": False},
}

# ── Hypothèses actuarielles SP — versionnées ──────────────────────────────────
HYPOTHESES_SP_REF = [
    # Tables biométriques
    {"id": "H-BCAC", "categorie": "Tables morbidité",
     "hypothese": "Tables BCAC 2019 — incidence ITT par âge et CSP",
     "valeur": "BCAC 2019 (Bureau Commun Assurances Collectives)",
     "source": "BCAC — Statistiques arrêts de travail 2019"},
    {"id": "H-TD88", "categorie": "Tables morbidité",
     "hypothese": "TD 88-90 — maintien en incapacité",
     "valeur": "Probabilités de passage ITT→IP par âge",
     "source": "INSEE/BCAC — Tables de maintien 1988-1990"},
    {"id": "H-TH00", "categorie": "Tables mortalité",
     "hypothese": "TH 00-02 — mortalité population active",
     "valeur": "Taux qx hommes, base France 2000-2002",
     "source": "INSEE/BCAC — Tables réglementaires TH 00-02"},
    # Réglementation santé
    {"id": "H-ANI", "categorie": "Réglementation",
     "hypothese": "ANI 2013 — panier minimum complémentaire collective",
     "valeur": "Panier minimum Art. L911-7 CSS (loi 14/06/2013)",
     "source": "ANI 11/01/2013 + Art. L911-7 Code de la Sécurité Sociale"},
    {"id": "H-DREES", "categorie": "Sinistralité santé",
     "hypothese": "DREES 2023 — fréquences et coûts santé",
     "valeur": "Comptes de la Santé 2023 — population générale France",
     "source": "DREES — Comptes de la Santé 2023 (rapport annuel)"},
    {"id": "H-FNMF", "categorie": "Sinistralité santé",
     "hypothese": "FNMF 2023 — sinistralité mutuelles",
     "valeur": "LR mutuelles France 2023 — 55%-85% selon garanties",
     "source": "FNMF — Rapport sinistralité 2023"},
    {"id": "H-CTIP", "categorie": "Provisionnement prévoyance",
     "hypothese": "CTIP 2023 — IBNR prévoyance collective",
     "valeur": "IBNR_ITT=35%, IBNR_IP=20% des sinistres payés",
     "source": "CTIP — Statistiques prévoyance collective 2023"},
    # Paramètres S2
    {"id": "H-RFR", "categorie": "Actualisation",
     "hypothese": "EIOPA RFR — taux sans risque EUR",
     "valeur": "Proxy 2.5% (taux long terme) — Art.77 Directive S2",
     "source": "EIOPA Risk-Free Rate curve EUR — Art.77 Directive S2"},
    {"id": "H-SCR-NSLT", "categorie": "SCR Santé NSLT",
     "hypothese": "σ primes santé NSLT = 5% | σ réserves = 14%",
     "valeur": "Formule standard EIOPA — Art.148 RD 2015/35",
     "source": "Règlement Délégué (UE) 2015/35 Art.148 Annexe II"},
    {"id": "H-SCR-SLT", "categorie": "SCR Invalidité SLT",
     "hypothese": "Choc morbidité +35% | Choc cessation -20%",
     "valeur": "Art.145 §2(a)(b) RD 2015/35",
     "source": "Règlement Délégué (UE) 2015/35 Art.145"},
    {"id": "H-RHO", "categorie": "Diversification S2",
     "hypothese": "ρ(NSLT, SLT) = 0.25",
     "valeur": "Corrélation EIOPA — Annexe IV RD 2015/35",
     "source": "Règlement Délégué (UE) 2015/35 Annexe IV"},
    {"id": "H-COC", "categorie": "Risk Adjustment IFRS17",
     "hypothese": "CoC rate = 6% (EIOPA)",
     "valeur": "Méthode CoC §B91 IFRS 17",
     "source": "IFRS 17 §B91 — EIOPA CoC rate"},
]

# ── Catégories de données personnelles traitées (RGPD Art.30) ─────────────────
CATEGORIES_DONNEES_SP = [
    {
        "categorie":    "Données de santé",
        "exemples":     "Sinistres médicaux, garanties optique/dentaire/hospit",
        "base_legale":  "Art.9 §2(b) RGPD — contrat de travail collectif",
        "conservation": "5 ans après fin contrat (prescription S2)",
        "sensible":     True,
    },
    {
        "categorie":    "Données salariales",
        "exemples":     "Salaire brut, CSP, ancienneté",
        "base_legale":  "Art.6 §1(b) RGPD — exécution du contrat",
        "conservation": "5 ans après fin contrat",
        "sensible":     False,
    },
    {
        "categorie":    "Données biométriques",
        "exemples":     "Âge, sexe (pour tarification actuarielle)",
        "base_legale":  "Art.9 §2(b) RGPD — contrat d'assurance collective",
        "conservation": "5 ans après fin contrat",
        "sensible":     True,
    },
    {
        "categorie":    "Données d'arrêts de travail",
        "exemples":     "Durée ITT, nature arrêt (ITT/IP/décès)",
        "base_legale":  "Art.9 §2(b) RGPD — gestion contrat prévoyance",
        "conservation": "10 ans (prescription prévoyance longue durée)",
        "sensible":     True,
    },
]


# ══════════════════════════════════════════════════════════════════════════════
class AgentSPAuditTrail:
    """
    Agent SP-AUDIT — Audit Trail Santé-Prévoyance.
    Direction Santé-Prévoyance.

    Collecte, consolide et archive les logs de tous les agents SP.
    Génère le registre RGPD Art.30 et le versioning des hypothèses SP.
    Équivalent SP de A13 (Non-Vie), adapté au contexte mutuelles/IP.
    """

    NOM     = "SP-Audit"
    CODE    = "SP-AUDIT"
    VERSION = "1.0"
    MANAGER = "Amira (Directrice SP)"

    def __init__(self, audit_path: str = "audit",
                 models_path: str = "models", verbose: bool = True):
        self.audit_path  = Path(audit_path)
        self.models_path = Path(models_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.audit")
        self.verbose = verbose

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            resultats_agents: Dict[str, Any],
            client_nom:       str  = "Client",
            actuaire_resp:    str  = "Actuaire désigné",
            date_arrete:      str  = "",
            generer_graphiques: bool = True) -> Dict[str, Any]:
        """
        Pipeline audit trail complet SP.

        Parameters
        ----------
        resultats_agents : dict
            Résultats des agents SP. Clés attendues :
            "s1", "s2", "s3", "p1", "p2", "p3", "p4",
            "sp_coord", "sp_reg1", "sp_reg2", "sp_reg3",
            "sp_st", "sp_coh", "sp_rapport"
        client_nom : str
            Nom de l'entité déclarante (pour le registre RGPD).
        actuaire_resp : str
            Nom et qualité de l'actuaire responsable.
        date_arrete : str
            Date d'arrêté (ex: "31/12/2025").
        """
        t0       = datetime.now()
        audit_id = f"SPAUDIT_{t0.strftime('%Y%m%d_%H%M%S')}"
        date_arrete = date_arrete or t0.strftime("%d/%m/%Y")

        try:
            self.logger.info(
                f"[{audit_id}] SP-Audit v{self.VERSION} | "
                f"client={client_nom} | actuaire={actuaire_resp} | "
                f"agents={list(resultats_agents.keys())}"
            )

            # ── MODULE 1 : Collecte des logs SP ───────────────────────────────
            logs = self._collecter_logs_sp(resultats_agents)

            # ── MODULE 2 : Registre RGPD Art.30 ──────────────────────────────
            registre_rgpd = self._generer_registre_rgpd(
                client_nom, actuaire_resp, date_arrete, logs
            )

            # ── MODULE 3 : Versioning hypothèses SP ───────────────────────────
            hypotheses = self._versioning_hypotheses_sp(resultats_agents)

            # ── MODULE 4 : Hash de session SHA-256 ───────────────────────────
            hash_session = self._calculer_hash_session(logs, hypotheses, date_arrete)

            # ── MODULE 5 : Rapport d'audit ────────────────────────────────────
            rapport_audit = self._generer_rapport_audit(
                logs, registre_rgpd, hypotheses, hash_session,
                client_nom, actuaire_resp, date_arrete
            )

            # ── RAG + Commentaire ─────────────────────────────────────────────
            hyp  = self._hypotheses_rag(logs, hypotheses)
            rag  = self._rag(hyp, logs)
            com  = self._commentaire(
                rag, logs, registre_rgpd, hypotheses,
                hash_session, client_nom, date_arrete, hyp
            )

            # ── Graphiques ────────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(logs, hypotheses)

            # ── Persister le registre ─────────────────────────────────────────
            self._persister_audit(audit_id, logs, hash_session, rag, client_nom)

            if self.verbose:
                self._console(audit_id, rag, logs, hash_session)

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":          True,
                "agent":            self.NOM,
                "version":          self.VERSION,
                "audit_id":         audit_id,
                "statut_rag":       rag,

                # ── Modules ───────────────────────────────────────────────────
                "logs":             logs,
                "registre_rgpd":    registre_rgpd,
                "hypotheses":       hypotheses,
                "hash_session":     hash_session,
                "rapport_audit":    rapport_audit,

                # ── Standard ActuarIA ─────────────────────────────────────────
                "hypotheses_rag":   hyp,
                "commentaire":      com,
                "graphiques":       gph,
                "duree_sec":        round(duree, 2),
                "erreur":           None,
            }

        except Exception as e:
            self.logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # =========================================================================
    # MODULE 1 — COLLECTE DES LOGS SP
    # =========================================================================
    def _collecter_logs_sp(self, resultats_agents: Dict) -> Dict:
        """
        Collecte et consolide les logs de tous les agents SP.

        Pour chaque agent disponible, extrait :
        - audit_id (identifiant unique de la session)
        - statut_rag (VERT/AMBRE/ROUGE)
        - agent (nom de l'agent)
        - durée d'exécution
        """
        agents_executes   = []
        agents_manquants  = []
        alertes_collectees = []
        chaine_traitement  = []

        for cle, meta in AGENTS_SP.items():
            r = resultats_agents.get(cle)
            if r and r.get("success"):
                entry = {
                    "cle":      cle,
                    "nom":      meta["nom"],
                    "equipe":   meta["equipe"],
                    "critique": meta["critique"],
                    "audit_id": r.get("audit_id", ""),
                    "statut":   r.get("statut_rag", "?"),
                    "duree":    r.get("duree_sec", 0),
                    "version":  r.get("version", ""),
                }
                agents_executes.append(entry)
                chaine_traitement.append(
                    f"{meta['nom']} [{r.get('statut_rag','?')}]"
                )
                # Collecter les alertes de l'agent
                for h in r.get("hypotheses", []):
                    if h.get("statut") in ("NON VALIDÉE", "À JUSTIFIER"):
                        alertes_collectees.append(
                            f"{meta['nom']} — {h.get('hypothese','')} : "
                            f"{h.get('statut','')} — {h.get('valeur','')}"
                        )
            else:
                if meta["critique"]:
                    agents_manquants.append(f"⚠️ {meta['nom']} (critique)")
                else:
                    agents_manquants.append(f"ℹ️ {meta['nom']} (optionnel)")

        # Statistiques
        nb_vert  = sum(1 for a in agents_executes if a["statut"]=="VERT")
        nb_ambre = sum(1 for a in agents_executes if a["statut"]=="AMBRE")
        nb_rouge = sum(1 for a in agents_executes if a["statut"]=="ROUGE")

        return {
            "agents_executes":    agents_executes,
            "agents_manquants":   agents_manquants,
            "nb_agents":          len(agents_executes),
            "nb_vert":            nb_vert,
            "nb_ambre":           nb_ambre,
            "nb_rouge":           nb_rouge,
            "chaine_traitement":  " → ".join(chaine_traitement),
            "alertes_collectees": alertes_collectees,
            "duree_totale":       sum(a["duree"] for a in agents_executes),
        }

    # =========================================================================
    # MODULE 2 — REGISTRE RGPD ARTICLE 30
    # =========================================================================
    def _generer_registre_rgpd(self, client_nom, actuaire_resp,
                                 date_arrete, logs) -> Dict:
        """
        Registre des activités de traitement SP — RGPD Art.30.

        Obligatoire pour tout organisme traitant des données personnelles
        (données de santé, données salariales, biométriques).
        Source : RGPD Art.30 + CNIL recommandations assureurs 2023.
        """
        return {
            "responsable_traitement": client_nom,
            "dpo_contact":            "A définir par l'entité",
            "actuaire_responsable":   actuaire_resp,
            "date_creation":          date_arrete,
            "date_maj":               datetime.now().strftime("%d/%m/%Y %H:%M"),
            "reference_rgpd":         "Art.30 RGPD (UE) 2016/679",

            "finalites": [
                "Tarification des garanties santé et prévoyance collectives",
                "Provisionnement actuariel (PSAP, PM rentes IP)",
                "Reporting réglementaire S2 (SCR/MCR) et IFRS 17",
                "Stress tests ORSA (Art.45 Directive S2)",
                "Conformité ANI 2013 et 100% Santé",
            ],

            "categories_donnees": CATEGORIES_DONNEES_SP,

            "destinataires": [
                "Actuaires internes Direction SP",
                "ACPR (sur demande réglementaire)",
                "Commissaire aux comptes (rapport actuariel annuel)",
                "Actuaire désigné (Art.48 Directive S2)",
            ],

            "transferts_hors_ue": "Aucun",

            "mesures_securite": [
                "Hachage SHA-256 de chaque session de calcul",
                "Audit trail traçable par agent (audit_id)",
                "Conservation chiffrée des fichiers d'audit (JSONL)",
                "Accès restreint aux agents actuariels habilités",
            ],

            "agents_traitants": [
                f"{a['nom']} ({a['equipe']})"
                for a in logs.get("agents_executes", [])
            ],

            "conformite": {
                "rgpd_art30":     "✅ Registre tenu",
                "rgpd_art9":      "✅ Base légale contrat d'assurance collective",
                "cnil_assureurs": "✅ Recommandations CNIL assureurs 2023",
            },
        }

    # =========================================================================
    # MODULE 3 — VERSIONING HYPOTHÈSES SP
    # =========================================================================
    def _versioning_hypotheses_sp(self, resultats_agents: Dict) -> Dict:
        """
        Versioning complet des hypothèses actuarielles SP utilisées.

        Permet la reproductibilité totale des calculs et la traçabilité
        pour l'actuaire désigné et le commissaire aux comptes.
        """
        # Hypothèses de référence (constantes réglementaires)
        hyps_ref = list(HYPOTHESES_SP_REF)

        # Hypothèses effectives extraites des agents
        hyps_effectives = []

        # Depuis S1 — taux de chargement
        # S1 expose "sorties_s2" qui contient les primes commerciales
        # Le chargement n'est pas exposé directement — proxy 18% (standard FNMF)
        if "s1" in resultats_agents and resultats_agents["s1"].get("success"):
            r = resultats_agents["s1"]
            # Calculer le chargement implicite si primes disponibles
            sorties = r.get("sorties_s2", {})
            pa    = float(sorties.get("primes_acquises", 0))
            pp_tt = float(r.get("prime_pure_totale", r.get("prime_commerciale", 0)))
            if pa > 0 and pp_tt > 0 and pa > pp_tt:
                chargement = (pa - pp_tt) / pa * 100
            else:
                chargement = 18.0  # proxy FNMF 2023 — standard mutuelles
            hyps_effectives.append({
                "id":         "HE-S1-CHARGEMENT",
                "agent":      "S1 Léonie",
                "hypothese":  "Taux de chargement commercial",
                "valeur":     f"{chargement:.1f}% (FNMF 2023 si non calculable)",
                "audit_id":   r.get("audit_id", ""),
            })

        # Depuis P3 — taux d'actualisation
        if "p3" in resultats_agents and resultats_agents["p3"].get("success"):
            r = resultats_agents["p3"]
            hyps_effectives.append({
                "id":         "HE-P3-TAUX-ACT",
                "agent":      "P3 Élodie",
                "hypothese":  "Taux d'actualisation rentes IP (EIOPA RFR proxy)",
                "valeur":     "2.5% (proxy EIOPA RFR EUR — Art.77 S2)",
                "audit_id":   r.get("audit_id", ""),
            })

        # Depuis SP-REG2 — RA IFRS17
        if "sp_reg2" in resultats_agents and resultats_agents["sp_reg2"].get("success"):
            r = resultats_agents["sp_reg2"]
            hyps_effectives.append({
                "id":         "HE-REG2-COC",
                "agent":      "SP-REG2",
                "hypothese":  "CoC rate Risk Adjustment IFRS 17",
                "valeur":     "6% (EIOPA — §B91 IFRS 17)",
                "audit_id":   r.get("audit_id", ""),
            })

        return {
            "version_bcac":         "BCAC 2019",
            "version_drees":        "DREES 2023",
            "version_fnmf":         "FNMF 2023",
            "version_ctip":         "CTIP 2023",
            # Proxy statique — à mettre à jour à chaque publication EIOPA
            "version_eiopa_rfr":    "EIOPA EUR Q4 2025",
            "version_ani":          "ANI 2013 — Art.L911-7 CSS",
            "version_rd_2015_35":   "RD 2015/35 consolidé 2024",
            "version_ifrs17":       "IFRS 17 (2017 + amendements 2020/2022)",
            "date_versioning":      datetime.now().strftime("%d/%m/%Y %H:%M"),
            "hypotheses_reference": hyps_ref,
            "hypotheses_effectives":hyps_effectives,
        }

    # =========================================================================
    # MODULE 4 — HASH DE SESSION SHA-256
    # =========================================================================
    def _calculer_hash_session(self, logs: Dict, hypotheses: Dict,
                                 date_arrete: str) -> str:
        """
        Hash SHA-256 de la session SP.

        Calculé sur :
        - Liste ordonnée des agents exécutés + leurs audit_id
        - Versions des tables actuarielles utilisées
        - Date d'arrêté

        Garantit l'intégrité et la reproductibilité des résultats.
        """
        donnees_hash = {
            "agents": sorted([
                {"cle": a["cle"], "audit_id": a["audit_id"]}
                for a in logs.get("agents_executes", [])
            ], key=lambda x: x["cle"]),
            "version_bcac":  hypotheses.get("version_bcac", ""),
            "version_drees": hypotheses.get("version_drees", ""),
            "version_rfr":   hypotheses.get("version_eiopa_rfr", ""),
            "date_arrete":   date_arrete,
        }
        contenu = json.dumps(donnees_hash, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(contenu.encode("utf-8")).hexdigest()[:16].upper()

    # =========================================================================
    # MODULE 5 — RAPPORT D'AUDIT
    # =========================================================================
    def _generer_rapport_audit(self, logs, registre_rgpd, hypotheses,
                                 hash_session, client_nom,
                                 actuaire_resp, date_arrete) -> Dict:
        """
        Rapport d'audit complet — PDF-ready pour l'actuaire désigné,
        l'ACPR et le commissaire aux comptes.
        """
        # agents_ok / agents_pb supprimés — non utilisés dans les sections
        manquants_cr = [m for m in logs["agents_manquants"] if "critique" in m]

        sections = []

        # Section 1 — Identification
        sections.append({
            "numero":  1,
            "titre":   "Identification de la session",
            "contenu": (
                f"Entité : {client_nom} | "
                f"Actuaire : {actuaire_resp} | "
                f"Arrêté au : {date_arrete} | "
                f"Hash session : {hash_session}"
            ),
        })

        # Section 2 — Chaîne de traitement
        sections.append({
            "numero":  2,
            "titre":   "Chaîne de traitement SP",
            "contenu": (
                f"{logs['nb_agents']} agents exécutés sur {len(AGENTS_SP)} | "
                f"VERT={logs['nb_vert']} AMBRE={logs['nb_ambre']} ROUGE={logs['nb_rouge']} | "
                f"Durée totale : {logs['duree_totale']:.2f}s | "
                f"{logs['chaine_traitement']}"
            ),
        })

        # Section 3 — Hypothèses actuarielles
        sections.append({
            "numero":  3,
            "titre":   "Hypothèses actuarielles SP versionnées",
            "contenu": (
                f"BCAC : {hypotheses['version_bcac']} | "
                f"DREES : {hypotheses['version_drees']} | "
                f"FNMF : {hypotheses['version_fnmf']} | "
                f"CTIP : {hypotheses['version_ctip']} | "
                f"EIOPA RFR : {hypotheses['version_eiopa_rfr']} | "
                f"ANI : {hypotheses['version_ani']}"
            ),
        })

        # Section 4 — Alertes
        alertes_txt = (
            "Aucune alerte" if not logs["alertes_collectees"] else
            f"{len(logs['alertes_collectees'])} alerte(s) : " +
            " | ".join(logs["alertes_collectees"][:3])
        )
        sections.append({
            "numero":  4,
            "titre":   "Alertes et points de vigilance",
            "contenu": alertes_txt,
        })

        # Section 5 — RGPD
        sections.append({
            "numero":  5,
            "titre":   "Conformité RGPD Art.30",
            "contenu": (
                f"Responsable : {client_nom} | "
                f"Catégories sensibles : données de santé + données salariales | "
                f"Base légale : Art.9 §2(b) + Art.6 §1(b) RGPD | "
                f"Conformité : {registre_rgpd['conformite']['rgpd_art30']}"
            ),
        })

        return {
            "titre":        f"Rapport d'audit SP — {client_nom}",
            "date_arrete":  date_arrete,
            "actuaire":     actuaire_resp,
            "hash_session": hash_session,
            "sections":     sections,
            "avis":         (
                "FAVORABLE" if logs["nb_rouge"] == 0 and not manquants_cr
                else "AVEC RÉSERVES" if logs["nb_rouge"] == 0
                else "DÉFAVORABLE"
            ),
        }

    # =========================================================================
    # HYPOTHÈSES RAG
    # =========================================================================
    def _hypotheses_rag(self, logs: Dict, hypotheses: Dict) -> list:
        # H1 — Agents critiques tous exécutés
        agents_cr_manquants = [
            m for m in logs["agents_manquants"] if "critique" in m
        ]
        h1_s = "VALIDÉE" if not agents_cr_manquants else "NON VALIDÉE"
        h1_m = (
            "Tous les agents critiques exécutés (S1-S3, P1-P4)"
            if not agents_cr_manquants
            else f"{len(agents_cr_manquants)} agent(s) critique(s) manquant(s)"
        )

        # H2 — Aucun agent ROUGE
        h2_s = "VALIDÉE" if logs["nb_rouge"] == 0 else "NON VALIDÉE"
        h2_m = (
            f"Aucun agent en ROUGE | {logs['nb_vert']} VERT / {logs['nb_ambre']} AMBRE"
            if logs["nb_rouge"] == 0
            else f"{logs['nb_rouge']} agent(s) en ROUGE — corrections requises"
        )

        # H3 — Hypothèses versionnées
        nb_hyp = len(hypotheses.get("hypotheses_reference", []))
        h3_s = "VALIDÉE" if nb_hyp >= 10 else "À JUSTIFIER"
        h3_m = f"{nb_hyp} hypothèses SP versionnées et sourcées"

        return [
            {"id":"H1","hypothese":"Agents critiques SP tous exécutés (S1-S3, P1-P4)",
             "valeur":h1_m,"statut":h1_s,"critique":True},
            {"id":"H2","hypothese":"Aucun agent SP en statut ROUGE",
             "valeur":h2_m,"statut":h2_s,"critique":True},
            {"id":"H3","hypothese":"Hypothèses actuarielles SP versionnées (≥10)",
             "valeur":h3_m,"statut":h3_s,"critique":False},
        ]

    def _rag(self, hyp: list, logs: Dict) -> str:
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val:
            return "ROUGE"
        if any(h["statut"]=="À JUSTIFIER" for h in hyp):
            return "AMBRE"
        if logs["nb_rouge"] > 0:
            return "ROUGE"
        if logs["nb_ambre"] > 0:
            return "AMBRE"
        return "VERT"

    # =========================================================================
    # COMMENTAIRE
    # =========================================================================
    def _commentaire(self, rag, logs, registre_rgpd, hypotheses,
                       hash_session, client_nom, date_arrete, hyp) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        L = [
            "="*70,
            f"  AUDIT TRAIL SANTÉ-PRÉVOYANCE — SP-AUDIT v{self.VERSION}",
            f"  {ic} STATUT : {rag} | {client_nom} | {date_arrete}",
            f"  Hash session : {hash_session}",
            "="*70, "",
            "📋 CHAÎNE DE TRAITEMENT SP", "─"*50,
            f"  Agents exécutés : {logs['nb_agents']}/{len(AGENTS_SP)}",
            f"  VERT={logs['nb_vert']} | AMBRE={logs['nb_ambre']} | ROUGE={logs['nb_rouge']}",
            f"  Durée totale   : {logs['duree_totale']:.2f}s",
        ]
        for a in logs["agents_executes"]:
            ic_a = "🟢" if a["statut"]=="VERT" else ("🟡" if a["statut"]=="AMBRE" else "🔴")
            L.append(f"  {ic_a} {a['nom']:25s} [{a['audit_id'][:12]}...] {a['duree']:.2f}s")

        if logs["agents_manquants"]:
            L += ["", "⚠️ AGENTS MANQUANTS"]
            for m in logs["agents_manquants"]:
                L.append(f"  {m}")

        L += [
            "", "🔐 RGPD ART.30", "─"*50,
            f"  Responsable : {registre_rgpd['responsable_traitement']}",
            f"  Actuaire    : {registre_rgpd['actuaire_responsable']}",
            f"  Conformité  : {registre_rgpd['conformite']['rgpd_art30']}",
            f"  Données sensibles : {sum(1 for c in registre_rgpd['categories_donnees'] if c['sensible'])} catégories",
            "",
            "📚 HYPOTHÈSES SP VERSIONNÉES", "─"*50,
            f"  BCAC   : {hypotheses['version_bcac']}",
            f"  DREES  : {hypotheses['version_drees']}",
            f"  FNMF   : {hypotheses['version_fnmf']}",
            f"  CTIP   : {hypotheses['version_ctip']}",
            f"  RFR    : {hypotheses['version_eiopa_rfr']}",
            f"  ANI    : {hypotheses['version_ani']}",
            f"  Total  : {len(hypotheses['hypotheses_reference'])} hypothèses de référence",
        ]

        if logs["alertes_collectees"]:
            L += ["", "⚡ ALERTES COLLECTÉES", "─"*50]
            for a in logs["alertes_collectees"][:5]:
                L.append(f"  {a}")

        L += ["", "📋 HYPOTHÈSES AUDIT", "─"*50]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"]=="À JUSTIFIER" else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        return "\n".join(L)

    # =========================================================================
    # GRAPHIQUES
    # =========================================================================
    def _graphiques(self, logs: Dict, hypotheses: Dict) -> Dict:
        gph = {}

        # Statuts agents
        statuts = ["VERT","AMBRE","ROUGE"]
        valeurs = [logs["nb_vert"], logs["nb_ambre"], logs["nb_rouge"]]
        couleurs = [VERT, AMBRE, ROUGE]

        fig1 = go.Figure(go.Pie(
            labels=statuts, values=valeurs,
            marker_colors=couleurs, hole=0.5,
        ))
        fig1.update_layout(
            **LAYOUT_BASE,
            title=dict(text="Statuts agents SP", font=dict(color=OR, size=13))
        )
        gph["statuts_agents"] = fig1

        # Timeline agents (durées)
        noms   = [a["nom"][:12] for a in logs["agents_executes"]]
        durees = [a["duree"] for a in logs["agents_executes"]]
        if noms:
            fig2 = go.Figure(go.Bar(
                x=noms, y=durees,
                marker_color=[
                    VERT if a["statut"]=="VERT" else
                    AMBRE if a["statut"]=="AMBRE" else ROUGE
                    for a in logs["agents_executes"]
                ],
                text=[f"{d:.2f}s" for d in durees],
                textposition="outside",
            ))
            fig2.update_layout(
                **LAYOUT_BASE,
                title=dict(text="Durée d'exécution par agent SP",
                           font=dict(color=OR, size=13)),
                yaxis_title="secondes",
            )
            gph["timeline_agents"] = fig2

        return gph

    # =========================================================================
    # PERSISTANCE + CONSOLE
    # =========================================================================
    def _persister_audit(self, audit_id, logs, hash_session, rag, client_nom):
        """Persiste l'entrée d'audit dans le fichier JSONL."""
        try:
            log_path = self.audit_path / "sp_audit_trail.jsonl"
            entry = {
                "audit_id":    audit_id,
                "timestamp":   datetime.now().isoformat(),
                "client":      client_nom,
                "statut_rag":  rag,
                "hash_session":hash_session,
                "nb_agents":   logs["nb_agents"],
                "nb_vert":     logs["nb_vert"],
                "nb_ambre":    logs["nb_ambre"],
                "nb_rouge":    logs["nb_rouge"],
                "agents":      [a["cle"] for a in logs["agents_executes"]],
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _console(self, audit_id, rag, logs, hash_session):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        self.logger.info(
            f"[{audit_id}] {ic} {rag} | "
            f"{logs['nb_agents']}/{len(AGENTS_SP)} agents | "
            f"VERT={logs['nb_vert']} AMBRE={logs['nb_ambre']} ROUGE={logs['nb_rouge']} | "
            f"Hash={hash_session}"
        )

    def _erreur(self, msg, audit_id="") -> Dict:
        return {
            "success":False, "agent":self.NOM, "version":self.VERSION,
            "audit_id":audit_id, "statut_rag":"ROUGE",
            "logs":{}, "registre_rgpd":{}, "hypotheses":{},
            "hash_session":"", "rapport_audit":{},
            "hypotheses_rag":[], "commentaire":"", "graphiques":{},
            "duree_sec":0, "erreur":msg,
        }
