"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT SP-COHERENCE : COHÉRENCE GLOBALE SANTÉ-PRÉVOYANCE        ║
║  Direction Santé-Prévoyance · Équivalent SP de A9 Marcus (Non-Vie)         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Contrôle transversal de toute la Direction SP.                      ║
║         Vérifie la cohérence entre TOUS les agents SP.                      ║
║         Émet des alertes proactives avant soumission ACPR.                  ║
║                                                                              ║
║  DIFFÉRENCES vs A9 Marcus (Non-Vie) :                                        ║
║    A9  : Chain Ladder ↔ GLM ↔ Stress ↔ S2 ↔ IFRS17 ↔ ALM (IARD)          ║
║    SP  : LR tarif ↔ LR prov | BE ↔ IFRS17 | SCR ↔ S2 | Stress ↔ ORSA     ║
║          + contrôles SP-spécifiques : ANI / poly-sinistralité / morbidité  ║
║                                                                              ║
║  CONTRÔLES EFFECTUÉS (6) :                                                  ║
║    C1 — LR tarification (S1) ↔ LR provisionnement (S2)                    ║
║         Cohérence fondamentale : tarif et provisions doivent être alignés   ║
║                                                                              ║
║    C2 — BE santé (S3) ↔ BE IFRS17 santé (SP-REG2)                         ║
║         Réconciliation réglementaire S2/IFRS17 — santé NSLT                ║
║                                                                              ║
║    C3 — BE prévoyance (P4) ↔ BE IFRS17 prévoyance (SP-REG2)               ║
║         Réconciliation réglementaire S2/IFRS17 — invalidité SLT            ║
║                                                                              ║
║    C4 — SCR SP-Coord ↔ SCR SP-REG1 (deux chemins de calcul)               ║
║         Le SCR doit être identique quel que soit l'agent qui le calcule    ║
║                                                                              ║
║    C5 — Stress tests Naomie ↔ ORSA SP-REG1                                 ║
║         Les stress tests doivent alimenter le résumé ORSA de manière        ║
║         cohérente (même scénarios, même ratios)                             ║
║                                                                              ║
║    C6 — Cohérence globale — synthèse + alertes proactives                  ║
║         Poly-sinistralité, dérive morbidité, ANI non conforme              ║
║                                                                              ║
║  ENTRÉES (toutes optionnelles — dégradation gracieuse) :                   ║
║    result_s1   → S1 Léonie (LR tarification santé)                        ║
║    result_s2   → S2 Selma  (LR provisionnement santé)                     ║
║    result_s3   → S3 Binta  (BE santé, SCR NSLT)                           ║
║    result_p4   → P4 Valentin (BE prévoyance, SCR SLT)                     ║
║    result_coord→ SP-Coord  (SCR consolidé, diversification)                ║
║    result_reg1 → SP-REG1   (SCR S2 narratif, ORSA)                        ║
║    result_reg2 → SP-REG2   (BE IFRS17 S+P)                                ║
║    result_reg3 → SP-REG3   (ANI conformité)                                ║
║    result_st   → Naomie    (stress tests ORSA)                             ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY   = "#0F2E52"; NAVY_L = "#1B3A5C"; NAVY_LL = "#243F6A"; OR = "#C9A84C"
BLANC  = "#F0F4F8"; GRIS   = "#8A9AB0"; VERT   = "#2ECC71"; ROUGE = "#E74C3C"
AMBRE  = "#F39C12"; BLEU   = "#3498DB"; VIOLET = "#9B59B6"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60), height=340,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
)

# ── Seuils de tolérance actuariels ────────────────────────────────────────────
# Écart LR tarif/provisionnement acceptable — pratique marché FNMF/CTIP
SEUIL_LR_ECART         = 0.15   # ≤ 15pp d'écart
# Écart BE S2/IFRS17 acceptable — réconciliation réglementaire
SEUIL_BE_ECART_PCT     = 0.05   # ≤ 5% d'écart relatif
# Écart SCR deux chemins de calcul
SEUIL_SCR_ECART_PCT    = 0.02   # ≤ 2% — même formule, doit être identique
# Seuil poly-sinistralité alerte
SEUIL_POLY_ALERTE      = 5.0    # % — source CTIP/FNMF


# ══════════════════════════════════════════════════════════════════════════════
class AgentSPCoherence:
    """
    Agent SP-COHÉRENCE — Cohérence Globale Santé-Prévoyance.
    Direction Santé-Prévoyance.

    Contrôle transversal de tous les agents SP — 6 contrôles C1-C6.
    Équivalent SP de A9 Marcus (Non-Vie), adapté au contexte mutuelles/IP.
    """

    NOM          = "SP-Cohérence"
    CODE         = "SP-COH"
    VERSION      = "1.0"
    RESPONSABLE  = "Amira (Directrice SP)"

    def __init__(self, audit_path: str = "audit", verbose: bool = True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.coherence")
        self.verbose = verbose

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s1    = None,
            result_s2    = None,
            result_s3    = None,
            result_p4    = None,
            result_coord  = None,
            result_reg1   = None,
            result_reg2   = None,
            result_reg3   = None,
            result_st     = None,
            generer_graphiques: bool = True) -> Dict:
        """
        Pipeline de contrôle de cohérence SP — 6 contrôles C1-C6.

        Toutes les entrées sont optionnelles. Un contrôle est marqué N/A
        si les agents nécessaires sont absents.
        """
        t0       = datetime.now()
        audit_id = f"COH_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # Détecter agents présents
            agents_presents = self._detecter_agents(
                result_s1, result_s2, result_s3, result_p4,
                result_coord, result_reg1, result_reg2, result_reg3, result_st
            )
            self.logger.info(
                f"[{audit_id}] SP-Cohérence | agents={agents_presents}"
            )

            # ── C1 : LR tarification ↔ LR provisionnement ────────────────────
            c1 = self._c1_lr_tarif_vs_prov(result_s1, result_s2)

            # ── C2 : BE santé S3 ↔ BE IFRS17 REG2 ───────────────────────────
            c2 = self._c2_be_sante_s2_vs_ifrs17(result_s3, result_reg2)

            # ── C3 : BE prévoyance P4 ↔ BE IFRS17 REG2 ───────────────────────
            c3 = self._c3_be_prev_s2_vs_ifrs17(result_p4, result_reg2)

            # ── C4 : SCR SP-Coord ↔ SCR SP-REG1 ─────────────────────────────
            c4 = self._c4_scr_coord_vs_reg1(result_coord, result_reg1)

            # ── C5 : Stress Naomie ↔ ORSA SP-REG1 ───────────────────────────
            c5 = self._c5_stress_vs_orsa(result_st, result_reg1)

            # ── C6 : Cohérence globale + alertes proactives ───────────────────
            c6 = self._c6_coherence_globale(
                [c1,c2,c3,c4,c5],
                result_coord, result_reg3, result_st
            )

            controles = [c1, c2, c3, c4, c5, c6]

            # Dashboard synthèse
            dashboard = self._dashboard(controles)

            # Alertes proactives
            alertes_ia = self._alertes_proactives(
                result_s1, result_s2, result_s3, result_p4,
                result_coord, result_reg3, result_st, controles
            )

            # Hypothèses + RAG
            hyp = self._hypotheses(controles, alertes_ia)
            rag = self._rag(controles, hyp)

            # Commentaire
            com = self._commentaire(
                rag, controles, dashboard, alertes_ia, agents_presents, hyp
            )

            # Graphiques
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(controles, dashboard)

            self._audit(audit_id, controles, rag, agents_presents)
            if self.verbose:
                self._console(audit_id, rag, controles, alertes_ia)

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":           True,
                "agent":             self.NOM,
                "version":           self.VERSION,
                "rattachement":      self.RESPONSABLE,
                "audit_id":          audit_id,
                "statut_rag":        rag,

                # ── Contrôles ───────────────────────────────────────────────
                "controles":         controles,
                "dashboard":         dashboard,
                "alertes_proactives":alertes_ia,
                "agents_analyses":   agents_presents,
                "flux_ok":           all(c["ok"] for c in controles if c["ok"] is not None),

                # ── Standard ActuarIA ────────────────────────────────────────
                "hypotheses":  hyp,
                "commentaire": com,
                "graphiques":  gph,
                "duree_sec":   round(duree, 2),
                "erreur":      None,
            }

        except Exception as e:
            self.logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # =========================================================================
    # DÉTECTION AGENTS
    # =========================================================================
    def _detecter_agents(self, r_s1, r_s2, r_s3, r_p4,
                          r_coord, r_reg1, r_reg2, r_reg3, r_st) -> List[str]:
        agents = []
        for r, nom in [(r_s1,"S1"),(r_s2,"S2"),(r_s3,"S3"),(r_p4,"P4"),
                        (r_coord,"SP-Coord"),(r_reg1,"SP-REG1"),
                        (r_reg2,"SP-REG2"),(r_reg3,"SP-REG3"),(r_st,"Naomie-ST")]:
            if r and r.get("success"):
                agents.append(nom)
        return agents

    def _na(self, nom: str, agents_requis: str) -> Dict:
        """Retourne un contrôle N/A si les agents requis sont absents."""
        return {
            "id": nom, "libelle": f"{nom} — N/A",
            "ok": None, "statut": "N/A",
            "detail": f"Agents requis absents : {agents_requis}",
            "valeur_a": None, "valeur_b": None, "ecart": None,
        }

    # =========================================================================
    # C1 — LR TARIFICATION ↔ LR PROVISIONNEMENT
    # =========================================================================
    def _c1_lr_tarif_vs_prov(self, result_s1, result_s2) -> Dict:
        """
        Contrôle C1 — Cohérence LR tarification (S1 Léonie) ↔ LR provisionnement (S2 Selma).

        LR_tarif = 1 / (1 + chargement) — LR cible de tarification (S1 Léonie)
        LR_prov  = sinistres_payés / primes_acquises — LR observé (S2 Selma)

        Un écart important peut signaler :
        - une dérive de sinistralité (portefeuille plus sinistré que tarifé)
        - une différence de maturité (portefeuille jeune → LR prov faible)
        - une inadéquation de la prime commerciale
        Seuil 15pp : pratique marché FNMF 2023 — au-delà, justification requise.
        Note : l'écart S2/IFRS17 attendu est nul (même données sources).
        Source : FNMF 2023 + DREES Comptes de la Santé 2023.
        """
        if not (result_s1 and result_s1.get("success") and
                result_s2 and result_s2.get("success")):
            return self._na("C1", "S1 + S2")

        lr_tarif = float(result_s1.get("ratio_sp_attendu", 0))
        lr_prov  = float(result_s2.get("loss_ratio", 0))

        if not lr_tarif or not lr_prov:
            return self._na("C1", "LR non disponibles dans S1/S2")

        ecart = abs(lr_tarif - lr_prov)
        ok    = ecart <= SEUIL_LR_ECART

        return {
            "id":      "C1",
            "libelle": "LR Tarification (S1) ↔ LR Provisionnement (S2)",
            "ok":      ok,
            "statut":  "✅ OK" if ok else "❌ ÉCART",
            "valeur_a":round(lr_tarif, 4),
            "valeur_b":round(lr_prov,  4),
            "ecart":   round(ecart, 4),
            "seuil":   SEUIL_LR_ECART,
            "detail":  (
                f"LR_tarif={lr_tarif:.1%} | LR_prov={lr_prov:.1%} | "
                f"Écart={ecart:.1%} {'≤' if ok else '>'} {SEUIL_LR_ECART:.0%} "
                f"{'✅ Cohérent' if ok else '⚠️ Dérive à investiguer'}"
            ),
            "source":  "FNMF 2023 — seuil tolérance 15pp tarif/prov",
        }

    # =========================================================================
    # C2 — BE SANTÉ S2 ↔ BE SANTÉ IFRS17
    # =========================================================================
    def _c2_be_sante_s2_vs_ifrs17(self, result_s3, result_reg2) -> Dict:
        """
        Contrôle C2 — Réconciliation BE santé S2 (S3 Binta) ↔ BE santé IFRS17 (SP-REG2).

        Dans l'architecture actuelle, SP-REG2 extrait le BE santé directement
        de S3 (même source que S3). L'écart attendu est donc nul ou très faible.
        Ce contrôle valide que les deux agents lisent bien les mêmes données
        et qu'aucune transformation parasite n'a été appliquée.

        En production avec des systèmes distincts (S2 vs IFRS17 séparés),
        cet écart peut atteindre 2-5% selon les ajustements de valorisation.
        Seuil 5% : ACPR Q&A IFRS17 2023 — réconciliation S2/IFRS17.
        """
        if not (result_s3 and result_s3.get("success") and
                result_reg2 and result_reg2.get("success")):
            return self._na("C2", "S3 + SP-REG2")

        be_s2    = float(result_s3.get("be_sante", 0))
        be_ifrs  = float(result_reg2.get("be_sante", 0))

        if not be_s2 or not be_ifrs:
            return self._na("C2", "BE santé non disponibles")

        ecart_pct = abs(be_s2 - be_ifrs) / max(be_s2, 1)
        ok        = ecart_pct <= SEUIL_BE_ECART_PCT

        return {
            "id":      "C2",
            "libelle": "BE Santé S2 (S3) ↔ BE Santé IFRS17 (SP-REG2)",
            "ok":      ok,
            "statut":  "✅ OK" if ok else "❌ ÉCART",
            "valeur_a":round(be_s2, 2),
            "valeur_b":round(be_ifrs, 2),
            "ecart":   round(ecart_pct, 4),
            "seuil":   SEUIL_BE_ECART_PCT,
            "detail":  (
                f"BE_S2={be_s2:,.0f}€ | BE_IFRS17={be_ifrs:,.0f}€ | "
                f"Écart={ecart_pct:.1%} {'≤' if ok else '>'} {SEUIL_BE_ECART_PCT:.0%} "
                f"{'✅ Réconciliation OK' if ok else '⚠️ Documenter ecart S2/IFRS17'}"
            ),
            "source":  "ACPR Q&A IFRS17 2023 — seuil tolérance 5%",
        }

    # =========================================================================
    # C3 — BE PRÉVOYANCE S2 ↔ BE PRÉVOYANCE IFRS17
    # =========================================================================
    def _c3_be_prev_s2_vs_ifrs17(self, result_p4, result_reg2) -> Dict:
        """
        Contrôle C3 — Réconciliation BE prévoyance S2 (P4) ↔ BE prévoyance IFRS17 (SP-REG2).

        Même logique que C2 pour la prévoyance SLT.
        SP-REG2 extrait le BE prévoyance de P4 (même source).
        L'écart attendu est nul dans l'architecture actuelle.
        En production (systèmes séparés), l'écart GMM vs PAA peut atteindre
        3-8% selon les ajustements de valorisation prévoyance long terme.
        Seuil 5% — si > 5%, documenter la divergence PAA/GMM (§53 IFRS17).
        """
        if not (result_p4 and result_p4.get("success") and
                result_reg2 and result_reg2.get("success")):
            return self._na("C3", "P4 + SP-REG2")

        be_s2   = float(result_p4.get("be_prevoyance", 0))
        be_ifrs = float(result_reg2.get("be_prevoyance", 0))

        if not be_s2 or not be_ifrs:
            return self._na("C3", "BE prévoyance non disponibles")

        ecart_pct = abs(be_s2 - be_ifrs) / max(be_s2, 1)
        ok        = ecart_pct <= SEUIL_BE_ECART_PCT

        return {
            "id":      "C3",
            "libelle": "BE Prévoyance S2 (P4) ↔ BE Prévoyance IFRS17 (SP-REG2)",
            "ok":      ok,
            "statut":  "✅ OK" if ok else "❌ ÉCART",
            "valeur_a":round(be_s2, 2),
            "valeur_b":round(be_ifrs, 2),
            "ecart":   round(ecart_pct, 4),
            "seuil":   SEUIL_BE_ECART_PCT,
            "detail":  (
                f"BE_S2={be_s2:,.0f}€ | BE_IFRS17={be_ifrs:,.0f}€ | "
                f"Écart={ecart_pct:.1%} {'≤' if ok else '>'} {SEUIL_BE_ECART_PCT:.0%} "
                f"{'✅ OK' if ok else '⚠️ Vérifier GMM vs PAA — §53 IFRS17'}"
            ),
            "source":  "IFRS17 §53 — PAA santé vs GMM prévoyance",
        }

    # =========================================================================
    # C4 — SCR SP-COORD ↔ SCR SP-REG1
    # =========================================================================
    def _c4_scr_coord_vs_reg1(self, result_coord, result_reg1) -> Dict:
        """
        Contrôle C4 — Cohérence SCR SP-Coord ↔ SCR SP-REG1.

        SP-Coord et SP-REG1 calculent tous les deux le SCR consolidé
        avec la même formule (ρ=0.25 EIOPA Annexe IV).
        Un écart > 2% signale une erreur de données ou de paramétrage.
        Source : EIOPA — principe de cohérence interne des QRT.
        """
        if not (result_coord and result_coord.get("success") and
                result_reg1  and result_reg1.get("success")):
            return self._na("C4", "SP-Coord + SP-REG1")

        scr_coord = float(result_coord.get("scr_consolide", 0))
        scr_reg1  = float(result_reg1.get("scr_consolide", 0))

        if not scr_coord or not scr_reg1:
            return self._na("C4", "SCR consolidé non disponible")

        ecart_pct = abs(scr_coord - scr_reg1) / max(scr_coord, 1)
        ok        = ecart_pct <= SEUIL_SCR_ECART_PCT

        return {
            "id":      "C4",
            "libelle": "SCR Consolidé SP-Coord ↔ SCR SP-REG1 (deux chemins)",
            "ok":      ok,
            "statut":  "✅ OK" if ok else "❌ INCOHÉRENCE",
            "valeur_a":round(scr_coord, 2),
            "valeur_b":round(scr_reg1, 2),
            "ecart":   round(ecart_pct, 4),
            "seuil":   SEUIL_SCR_ECART_PCT,
            "detail":  (
                f"SCR_Coord={scr_coord:,.0f}€ | SCR_REG1={scr_reg1:,.0f}€ | "
                f"Écart={ecart_pct:.2%} {'≤' if ok else '>'} {SEUIL_SCR_ECART_PCT:.0%} "
                f"{'✅ Même formule EIOPA' if ok else '❌ Erreur paramétrage à corriger'}"
            ),
            "source":  "EIOPA Annexe IV RD 2015/35 — ρ=0.25 cohérence interne",
        }

    # =========================================================================
    # C5 — STRESS NAOMIE ↔ ORSA SP-REG1
    # =========================================================================
    def _c5_stress_vs_orsa(self, result_st, result_reg1) -> Dict:
        """
        Contrôle C5 — Cohérence Stress Tests Naomie ↔ ORSA SP-REG1.

        Les stress tests de Naomie doivent alimenter le résumé ORSA de SP-REG1.
        Vérification : même pire scénario, ratio stressé cohérent.
        Source : EIOPA ORSA Guidelines 2016 + Directive S2 Art.45.
        """
        if not (result_st  and result_st.get("success") and
                result_reg1 and result_reg1.get("success")):
            return self._na("C5", "Naomie-ST + SP-REG1")

        # Pire ratio stressé de Naomie
        scenarios = result_st.get("scenarios", {})
        pire_nom  = result_st.get("pire_scenario", "")
        pire_ratio_st = min(
            (s.get("ratio_scr_stresse", 999) for s in scenarios.values()),
            default=None
        )

        # Ratio ORSA dans SP-REG1
        orsa = result_reg1.get("orsa_resume", {})
        st_reg1 = orsa.get("stress_tests", {})
        pire_ratio_reg1 = st_reg1.get("ratio_stresse", None) if st_reg1 else None

        if pire_ratio_st is None or pire_ratio_reg1 is None:
            return self._na("C5", "Ratios ORSA non transmis entre Naomie et SP-REG1")

        ecart = abs(pire_ratio_st - pire_ratio_reg1)
        ok    = ecart <= 1.0   # tolérance 1pp — même données

        return {
            "id":      "C5",
            "libelle": "Stress Tests Naomie ↔ ORSA SP-REG1 (cohérence pire scénario)",
            "ok":      ok,
            "statut":  "✅ OK" if ok else "⚠️ ÉCART",
            "valeur_a":round(pire_ratio_st, 1),
            "valeur_b":round(pire_ratio_reg1, 1),
            "ecart":   round(ecart, 2),
            "seuil":   1.0,
            "detail":  (
                f"Ratio_stressé_Naomie={pire_ratio_st:.1f}% "
                f"| Ratio_ORSA_REG1={pire_ratio_reg1:.1f}% "
                f"| Écart={ecart:.1f}pp {'≤' if ok else '>'} 1pp "
                f"{'✅ ORSA alimenté correctement' if ok else '⚠️ ORSA non synchronisé'}"
            ),
            "source":  "EIOPA ORSA Guidelines 2016 + Directive S2 Art.45",
        }

    # =========================================================================
    # C6 — COHÉRENCE GLOBALE + ALERTES PROACTIVES
    # =========================================================================
    def _c6_coherence_globale(self, controles_precedents: List,
                               result_coord, result_reg3, result_st) -> Dict:
        """
        Contrôle C6 — Synthèse + alertes proactives SP.

        Vérifie la cohérence d'ensemble et détecte des patterns à risque
        spécifiques SP : poly-sinistralité, non-conformité ANI,
        ratio SCR post-stress insuffisant.
        """
        nb_ok   = sum(1 for c in controles_precedents if c["ok"] is True)
        nb_ko   = sum(1 for c in controles_precedents if c["ok"] is False)
        nb_na   = sum(1 for c in controles_precedents if c["ok"] is None)
        nb_tot  = len(controles_precedents)

        alertes = []

        # Poly-sinistralité
        if result_coord and result_coord.get("success"):
            poly = result_coord.get("poly_sinistralite_pct")
            if poly is not None and poly > SEUIL_POLY_ALERTE:
                alertes.append(
                    f"⚠️ Poly-sinistralité {poly:.1f}% > {SEUIL_POLY_ALERTE}% "
                    f"— risque accumulation S+P (CTIP/FNMF 2023)"
                )

        # ANI non conforme
        if result_reg3 and result_reg3.get("success"):
            if result_reg3.get("ani_conforme") is False:
                alertes.append(
                    "❌ ANI 2013 non conforme — risque ACPR "
                    "(Art. L911-7 CSS — action corrective requise)"
                )

        # Ratio SCR post-stress insuffisant
        if result_st and result_st.get("success"):
            for nom, r in result_st.get("scenarios", {}).items():
                if not r.get("ratio_ok", True):
                    alertes.append(
                        f"⚠️ Ratio SCR stressé ({nom}) = "
                        f"{r.get('ratio_scr_stresse',0):.1f}% < 100% "
                        f"— plan de mesures ORSA requis (Art.45 S2)"
                    )

        # Score global
        score = nb_ok / max(nb_tot - nb_na, 1) * 100
        ok    = nb_ko == 0

        return {
            "id":      "C6",
            "libelle": "Cohérence Globale SP — Synthèse",
            "ok":      ok,
            "statut":  "✅ OK" if ok else ("⚠️ POINTS" if nb_ko < 3 else "❌ CRITIQUE"),
            "valeur_a":nb_ok,
            "valeur_b":nb_tot - nb_na,
            "ecart":   None,
            "detail":  (
                f"{nb_ok}/{nb_tot-nb_na} contrôles OK "
                f"({nb_na} N/A faute de données) | Score={score:.0f}% | "
                f"{'✅ Direction SP cohérente' if ok else f'❌ {nb_ko} incohérence(s) à corriger'}"
            ),
            "alertes_sp": alertes,
            "score_pct":  round(score, 1),
            "source":     "Contrôle interne SP — ACPR supervision",
        }

    # =========================================================================
    # DASHBOARD SYNTHÈSE
    # =========================================================================
    def _dashboard(self, controles: List) -> Dict:
        ok_list  = [c for c in controles if c["ok"] is True]
        ko_list  = [c for c in controles if c["ok"] is False]
        na_list  = [c for c in controles if c["ok"] is None]
        score    = len(ok_list) / max(len(controles) - len(na_list), 1) * 100

        return {
            "nb_ok":     len(ok_list),
            "nb_ko":     len(ko_list),
            "nb_na":     len(na_list),
            "nb_total":  len(controles),
            "score_pct": round(score, 1),
            "controles_ko": [c["libelle"] for c in ko_list],
        }

    # =========================================================================
    # ALERTES PROACTIVES
    # =========================================================================
    def _alertes_proactives(self, r_s1, r_s2, r_s3, r_p4,
                              r_coord, r_reg3, r_st,
                              controles: List) -> List[str]:
        """
        6 patterns à risque détectés automatiquement — spécifiques SP.
        """
        alertes = []

        # P1 — LR santé > 90% (sinistralité élevée)
        if r_s1 and r_s1.get("success"):
            lr = float(r_s1.get("ratio_sp_attendu", 0))
            if lr > 0.90:
                alertes.append(
                    f"🔴 LR tarification santé = {lr:.1%} > 90% "
                    f"— réviser la tarification (primes insuffisantes)"
                )

        # P2 — PSAP/PA > 25% (provisionnement élevé)
        if r_s2 and r_s2.get("success") and r_s1 and r_s1.get("success"):
            pa = float(r_s1.get("sorties_s2",{}).get("primes_acquises", 0))
            psap = float(r_s2.get("psap_total", 0))
            if pa > 0 and psap/pa > 0.25:
                alertes.append(
                    f"⚠️ PSAP/PA = {psap/pa:.1%} > 25% "
                    f"— vérifier cadences règlement (DREES 2023)"
                )

        # P3 — SCR < 110% (solvabilité tendue)
        if r_s3 and r_s3.get("success"):
            ratio = float(r_s3.get("ratio_scr_pct", 0))
            if 0 < ratio < 110:
                alertes.append(
                    f"🔴 Ratio SCR santé = {ratio:.1f}% < 110% "
                    f"— marge de sécurité insuffisante (seuil interne 130%)"
                )

        # P4 — Diversification < 5% (corrélation S+P trop forte)
        if r_coord and r_coord.get("success"):
            div = float(r_coord.get("diversification", 0))
            scr_s = float(r_coord.get("scr_sante", 0))
            scr_p = float(r_coord.get("scr_prevoyance", 0))
            if scr_s + scr_p > 0:
                pct_div = div / (scr_s + scr_p) * 100
                if pct_div < 5:
                    alertes.append(
                        f"ℹ️ Bénéfice diversification S+P = {pct_div:.1f}% < 5% "
                        f"— vérifier ρ=0.25 EIOPA (Annexe IV RD 2015/35)"
                    )

        # P5 — ANI non conforme collectif
        if r_reg3 and r_reg3.get("success"):
            if r_reg3.get("ani_conforme") is False:
                alertes.append(
                    "❌ ANI 2013 non conforme — action corrective immédiate requise "
                    "(Art. L911-7 CSS + loi 14/06/2013)"
                )

        # P6 — Ratio stressé sous 100%
        if r_st and r_st.get("success"):
            pire = r_st.get("pire_scenario", "")
            pire_ratio = r_st.get("scenarios", {}).get(
                pire, {}).get("ratio_scr_stresse", 999)
            if pire_ratio < 100:
                alertes.append(
                    f"❌ Pire scénario ORSA ({pire}) : ratio stressé "
                    f"{pire_ratio:.1f}% < 100% — plan de capital requis (Art.45 S2)"
                )

        return alertes

    # =========================================================================
    # HYPOTHÈSES + RAG
    # =========================================================================
    def _hypotheses(self, controles: List, alertes: List) -> list:
        dash = self._dashboard(controles)
        score = dash["score_pct"]

        # H1 — Score global ≥ 80%
        ok1 = score >= 80
        h1_s = "VALIDÉE" if ok1 else "NON VALIDÉE"
        h1_m = (f"{dash['nb_ok']}/{dash['nb_total']-dash['nb_na']} contrôles OK "
                f"| Score={score:.0f}%")

        # H2 — Aucun contrôle en erreur critique (C1-C4)
        ko_critiques = [c for c in controles[:4] if c["ok"] is False]
        h2_s = "VALIDÉE" if not ko_critiques else "NON VALIDÉE"
        h2_m = ("Tous contrôles critiques OK" if not ko_critiques
                 else f"{len(ko_critiques)} contrôle(s) critique(s) en erreur")

        # H3 — Alertes proactives sous contrôle
        alertes_rouge = [a for a in alertes if a.startswith("🔴") or a.startswith("❌")]
        h3_s = "VALIDÉE" if not alertes_rouge else "À JUSTIFIER"
        h3_m = (f"Aucune alerte critique" if not alertes_rouge
                 else f"{len(alertes_rouge)} alerte(s) critique(s) détectée(s)")

        return [
            {"id":"H1","hypothese":"Score cohérence globale SP ≥ 80%",
             "valeur":h1_m,"statut":h1_s,"critique":True},
            {"id":"H2","hypothese":"Contrôles critiques C1-C4 tous OK",
             "valeur":h2_m,"statut":h2_s,"critique":True},
            {"id":"H3","hypothese":"Alertes proactives sous contrôle",
             "valeur":h3_m,"statut":h3_s,"critique":False},
        ]

    def _rag(self, controles: List, hyp: list) -> str:
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val:
            return "ROUGE"
        if any(h["statut"]=="À JUSTIFIER" for h in hyp):
            return "AMBRE"
        return "VERT"

    # =========================================================================
    # COMMENTAIRE
    # =========================================================================
    def _commentaire(self, rag, controles, dashboard, alertes, agents, hyp) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        L = [
            "="*70,
            f"  COHÉRENCE GLOBALE SANTÉ-PRÉVOYANCE — SP-COHÉRENCE v{self.VERSION}",
            f"  {ic} STATUT : {rag} | Agents : {', '.join(agents) or 'Aucun'}",
            "="*70, "",
            "📊 DASHBOARD", "─"*50,
            f"  Score global    : {dashboard['score_pct']:.0f}%",
            f"  Contrôles OK    : {dashboard['nb_ok']}/{dashboard['nb_total']-dashboard['nb_na']}",
            f"  N/A (données)   : {dashboard['nb_na']}",
        ]
        if dashboard["controles_ko"]:
            L.append(f"  En erreur       : {', '.join(dashboard['controles_ko'])}")

        L += ["", "🔍 DÉTAIL CONTRÔLES", "─"*50]
        for c in controles:
            # True→✅ | False→❌ | None→— (N/A)
            ic_c = "✅" if c["ok"] is True else ("❌" if c["ok"] is False else "—")
            L.append(f"  {ic_c} [{c['id']}] {c.get('libelle', c['id'])}")
            L.append(f"       → {c['detail']}")

        if alertes:
            L += ["", "⚡ ALERTES PROACTIVES", "─"*50]
            for a in alertes:
                L.append(f"  {a}")

        L += ["", "📋 HYPOTHÈSES", "─"*50]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"]=="À JUSTIFIER" else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        return "\n".join(L)

    # =========================================================================
    # GRAPHIQUES
    # =========================================================================
    def _graphiques(self, controles: List, dashboard: Dict) -> Dict:
        gph = {}

        # Radar des 6 contrôles
        labels = [c["id"] for c in controles]
        values = [1 if c["ok"] is True else (0.5 if c["ok"] is None else 0)
                  for c in controles]
        fig = go.Figure(go.Scatterpolar(
            r=values + [values[0]],
            theta=labels + [labels[0]],
            fill="toself",
            fillcolor="rgba(201,168,76,0.15)",
            line=dict(color=OR, width=2),
            name="Cohérence",
        ))
        fig.update_layout(
            **LAYOUT_BASE,
            polar=dict(
                bgcolor=NAVY_L,
                radialaxis=dict(visible=True, range=[0,1], tickcolor=GRIS,
                                gridcolor=GRIS),
                angularaxis=dict(tickcolor=BLANC, gridcolor=GRIS),
            ),
            title=dict(text="Radar Cohérence SP — C1 à C6",
                       font=dict(color=OR, size=13)),
        )
        gph["radar_coherence"] = fig

        # Scorecard
        couleurs = []
        for c in controles:
            couleurs.append(VERT if c["ok"] is True else
                            GRIS if c["ok"] is None else ROUGE)
        fig2 = go.Figure(go.Bar(
            x=labels,
            y=[1 if c["ok"] is True else (0.5 if c["ok"] is None else 0)
               for c in controles],
            marker_color=couleurs,
            text=[c["statut"] for c in controles],
            textposition="outside",
        ))
        fig2.update_layout(
            **LAYOUT_BASE,
            title=dict(text="Scorecard Cohérence SP — C1 à C6",
                       font=dict(color=OR, size=13)),
            yaxis=dict(range=[0, 1.3], showticklabels=False),
        )
        gph["scorecard"] = fig2

        return gph

    # =========================================================================
    # AUDIT + CONSOLE
    # =========================================================================
    def _audit(self, audit_id, controles, rag, agents):
        try:
            import json as _json
            log = self.audit_path / "sp_coherence_audit.jsonl"
            entry = {
                "audit_id":  audit_id,
                "timestamp": datetime.now().isoformat(),
                "statut_rag":rag,
                "nb_ok":     sum(1 for c in controles if c["ok"] is True),
                "nb_ko":     sum(1 for c in controles if c["ok"] is False),
                "agents":    agents,
            }
            with open(log, "a", encoding="utf-8") as f:
                f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _console(self, audit_id, rag, controles, alertes):
        ic  = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        nb_ok = sum(1 for c in controles if c["ok"] is True)
        nb_ko = sum(1 for c in controles if c["ok"] is False)
        self.logger.info(
            f"[{audit_id}] {ic} {rag} | "
            f"C1-C6 : {nb_ok} OK / {nb_ko} KO | "
            f"{len(alertes)} alerte(s) proactive(s)"
        )

    def _erreur(self, msg, audit_id="") -> Dict:
        return {
            "success":False, "agent":self.NOM, "version":self.VERSION,
            "audit_id":audit_id, "statut_rag":"ROUGE",
            "controles":[], "dashboard":{}, "alertes_proactives":[],
            "agents_analyses":[], "flux_ok":False,
            "hypotheses":[], "commentaire":"", "graphiques":{},
            "duree_sec":0, "erreur":msg,
        }
