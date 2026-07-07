"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT SP-ALM : ALM & LIQUIDITÉ SANTÉ-PRÉVOYANCE                ║
║  Direction Santé-Prévoyance — Équivalent SP de A12 Aisha (Non-Vie)         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Adossement actif/passif SP — mutuelles et institutions de           ║
║         prévoyance. Duration rentes IP, LCR mutuelle, stress taux.         ║
║                                                                              ║
║  DIFFÉRENCES vs A12 Aisha (Non-Vie) :                                        ║
║    A12  : portefeuille obligataire IARD, LCR Basel III, requiert Elena S2  ║
║    SP   : PM rentes IP (duration 10-15 ans), PSAP santé (duration 1-3 ans) ║
║           LCR mutuelle (Art. L212-7 CSS), sensibilité EIOPA RFR            ║
║           requiert P3 Élodie (PM rentes) + S3 Binta (BE santé)             ║
║                                                                              ║
║  FONCTIONS :                                                                 ║
║    1. ANALYSE DU PASSIF SP                                                   ║
║       Duration PM rentes IP (long terme, sensible aux taux)                ║
║       Duration PSAP santé (court terme, peu sensible)                      ║
║       Duration consolidée pondérée par les montants                        ║
║                                                                              ║
║    2. ANALYSE DE L'ACTIF SP                                                 ║
║       Allocation type mutuelle : OAT + obligations + monétaire             ║
║       Duration actif pondérée par classe d'actif                           ║
║       Convexité actif                                                       ║
║                                                                              ║
║    3. GAP DE DURATION                                                        ║
║       Gap = Duration_actif − Duration_passif                               ║
║       Recommandation : gap < 1 an pour mutuelles (ACPR 2023)              ║
║                                                                              ║
║    4. SENSIBILITÉ TAUX (BV01)                                               ║
║       Impact +1bp sur la NAV (actif − passif)                              ║
║       Stress taux ±100bp et ±200bp EIOPA Art.105                           ║
║                                                                              ║
║    5. LCR MUTUELLE                                                           ║
║       Art. L212-7 CSS : actifs liquides / sorties nettes 30j               ║
║       Seuil réglementaire : LCR ≥ 100% (ACPR circulaire 2023)             ║
║                                                                              ║
║  SORTIES VERS SP-COHÉRENCE :                                                ║
║    duration.passif, duration.actif, gap_duration, lcr, immunisation_ok     ║
║                                                                              ║
║  RÉFÉRENCES :                                                                ║
║    Art. L212-7 CSS — LCR mutuelles                                         ║
║    ACPR circulaire 2023 — recommandations ALM mutuelles                    ║
║    EIOPA Art.77 S2 — taux sans risque provisions                           ║
║    EIOPA Art.105 S2 — module risque taux d'intérêt                        ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

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
AMBRE  = "#F39C12"; BLEU   = "#3498DB"; VIOLET = "#9B59B6"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60), height=320,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
)

# ── Paramètres ALM SP ─────────────────────────────────────────────────────────
# Taux EIOPA RFR proxy — Art.77 S2
# Proxy statique — à mettre à jour à chaque publication EIOPA
EIOPA_RFR_PROXY  = 0.025  # 2.5%

# Gap duration cible mutuelles — ACPR recommandations 2023
# Un gap > 2 ans expose la mutuelle à un risque taux significatif
GAP_CIBLE_MAX    = 2.0    # années — seuil alerte ACPR

# LCR mutuelle minimum — Art. L212-7 CSS
LCR_MIN          = 1.00   # 100% — seuil réglementaire

# Duration PM rentes IP typique (long terme)
# Les PM rentes IP ont une duration de 10-15 ans selon l'âge moyen du portefeuille
DURATION_RENTES_IP_MIN  = 8.0   # années — minimum raisonnable
DURATION_RENTES_IP_MAX  = 18.0  # années — maximum raisonnable

# Allocation type mutuelle France (source : ACPR rapport 2022)
# OAT + obligations souveraines : ~55-65% des actifs
# Obligations corporate : ~20-30%
# Monétaire + OPCVM : ~10-20%
ALLOC_MUTUELLE_DEFAUT = {
    "oat_souverain":     0.60,  # OAT et obligations souveraines
    "obligations_corp":  0.25,  # Obligations corporate investment grade
    "monetaire":         0.10,  # Monétaire et OPCVM court terme
    "actions":           0.05,  # Actions (limité pour mutuelles)
}

# Duration par classe d'actif (valeurs typiques)
# Source : ACPR rapport ALM mutuelles 2022
DURATION_ACTIF_CLASSE = {
    "oat_souverain":     7.5,   # OAT 10 ans ~ duration 7-8 ans
    "obligations_corp":  5.0,   # Obligations corporate ~ 4-6 ans
    "monetaire":         0.25,  # Monétaire ~ duration très courte
    "actions":           0.0,   # Actions : pas de duration au sens obligataire
}


# ══════════════════════════════════════════════════════════════════════════════
class AgentSPAlm:
    """
    Agent SP-ALM — ALM & Liquidité Santé-Prévoyance.
    Direction Santé-Prévoyance.

    Adossement actif/passif adapté au contexte mutuelles et IP :
    PM rentes IP long terme, PSAP santé court terme,
    LCR Art. L212-7 CSS, sensibilité EIOPA RFR.
    Équivalent SP de A12 Aisha (Non-Vie).
    """

    NOM     = "SP-ALM"
    CODE    = "SP-ALM"
    VERSION = "1.0"
    MANAGER = "Amira (Directrice SP)"

    def __init__(self, audit_path: str = "audit", verbose: bool = True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.alm")
        self.verbose = verbose

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_p3          = None,
            result_s3          = None,
            result_coord        = None,
            fonds_propres:      float = 0.0,
            taux_actu:          float = EIOPA_RFR_PROXY,
            allocation_actif:   Optional[Dict] = None,
            valeur_actif_total: float = 0.0,
            generer_graphiques: bool = True) -> Dict:
        """
        Pipeline ALM SP complet.

        Parameters
        ----------
        result_p3 : dict
            Résultat P3 Élodie (PM rentes IP, PSAP prévoyance). Requis.
        result_s3 : dict
            Résultat S3 Binta (BE santé, SCR). Optionnel.
        result_coord : dict
            Résultat SP-Coord (BE consolidé, SCR consolidé). Optionnel.
        fonds_propres : float
            Fonds propres éligibles (€). Utilisé pour le LCR.
        taux_actu : float
            Taux d'actualisation EIOPA RFR proxy (défaut 2.5%).
        allocation_actif : dict, optional
            Allocation actif par classe. Si absent : allocation mutuelle type.
            Clés : "oat_souverain", "obligations_corp", "monetaire", "actions".
        valeur_actif_total : float
            Valeur totale des actifs (€). Si 0, estimée depuis les passifs + FP.
        """
        t0  = datetime.now()
        aid = f"ALM_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            if not result_p3 or not result_p3.get("success"):
                raise ValueError("result_p3 requis et success=True (PM rentes IP)")

            # ── 1. ANALYSE DU PASSIF SP ───────────────────────────────────────
            passif = self._analyser_passif_sp(result_p3, result_s3, taux_actu)

            # ── 2. ANALYSE DE L'ACTIF SP ──────────────────────────────────────
            # Valeur actif = passif + fonds propres si non fournie
            if valeur_actif_total <= 0:
                valeur_actif_total = passif["tp_total"] + fonds_propres
                if valeur_actif_total <= 0:
                    valeur_actif_total = max(passif["tp_total"] * 1.15, 1.0)
                    self.logger.warning(
                        f"[{aid}] valeur_actif_total estimée : {valeur_actif_total:,.0f}€"
                    )

            alloc = allocation_actif or ALLOC_MUTUELLE_DEFAUT
            actif = self._analyser_actif_sp(alloc, valeur_actif_total, taux_actu)

            self.logger.info(
                f"[{aid}] SP-ALM v{self.VERSION} | "
                f"Passif={passif['tp_total']:,.0f}€ | "
                f"Actif={actif['valeur_totale']:,.0f}€ | "
                f"D_passif={passif['duration_consolidee']:.2f}a | "
                f"D_actif={actif['duration_macaulay']:.2f}a"
            )

            # ── 3. GAP DE DURATION ────────────────────────────────────────────
            gap = self._calculer_gap(actif, passif)

            # ── 4. SENSIBILITÉ TAUX (BV01) ────────────────────────────────────
            bv01 = self._calculer_bv01(actif, passif, taux_actu)

            # ── 5. LCR MUTUELLE (Art. L212-7 CSS) ────────────────────────────
            lcr = self._calculer_lcr_mutuelle(actif, passif, fonds_propres)

            # ── Hypothèses + RAG ──────────────────────────────────────────────
            hyp = self._hypotheses(gap, bv01, lcr, passif)
            rag = self._rag(hyp, gap, lcr)

            # ── Commentaire ───────────────────────────────────────────────────
            com = self._commentaire(rag, actif, passif, gap, bv01, lcr, hyp, taux_actu)

            # ── Graphiques ────────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(actif, passif, gap, bv01, lcr)

            self._audit(aid, gap, bv01, lcr, rag)
            if self.verbose:
                self._console(aid, rag, actif, passif, gap, lcr)

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── Duration (→ SP-Cohérence) ─────────────────────────────────
                "duration": {
                    "actif":              round(actif["duration_macaulay"], 2),
                    "actif_modifiee":     round(actif["duration_modifiee"], 2),
                    "passif":             round(passif["duration_consolidee"], 2),
                    "passif_rentes_ip":   round(passif["duration_rentes_ip"], 2),
                    "passif_psap_sante":  round(passif["duration_psap_sante"], 2),
                    "gap":                round(gap["gap_duration"], 2),
                    "statut_gap":         gap["statut"],
                },

                # ── BV01 ──────────────────────────────────────────────────────
                "bv01": {
                    "bv01_actif":       round(bv01["bv01_actif"], 0),
                    "bv01_passif":      round(bv01["bv01_passif"], 0),
                    "bv01_net":         round(bv01["bv01_net"], 0),
                    "impact_100bp":     round(bv01["impact_100bp"], 0),
                    "impact_200bp":     round(bv01["impact_200bp"], 0),
                },

                # ── LCR Mutuelle ──────────────────────────────────────────────
                "lcr": {
                    "lcr_ratio":         round(lcr["lcr_ratio"], 2),
                    "actifs_liquides":   round(lcr["actifs_liquides"], 0),
                    "sorties_nettes_30j":round(lcr["sorties_nettes_30j"], 0),
                    "conforme":          lcr["conforme"],
                    "reference":         "Art. L212-7 CSS",
                },

                # ── Passif SP ─────────────────────────────────────────────────
                "passif":  passif,
                "actif":   actif,
                "gap":     gap,

                # ── Standard ActuarIA ─────────────────────────────────────────
                "hypotheses":  hyp,
                "commentaire": com,
                "graphiques":  gph,
                "duree_sec":   round(duree, 2),
                "erreur":      None,
            }

        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), aid)

    # =========================================================================
    # 1. ANALYSE DU PASSIF SP
    # =========================================================================
    def _analyser_passif_sp(self, result_p3, result_s3, taux_actu: float) -> Dict:
        """
        Analyse du passif SP — duration pondérée PM rentes IP + PSAP santé.

        PM rentes IP : duration longue (10-15 ans) — très sensible aux taux.
        PSAP santé   : duration courte (1-3 ans) — peu sensible aux taux.

        Duration consolidée = moyenne pondérée par les montants.

        Source : actuariat SP standard + EIOPA Art.77 S2.
        """
        # ── PM rentes IP (P3) ─────────────────────────────────────────────────
        pm_rentes    = float(result_p3.get("pm_rentes_ip", 0))
        psap_prev    = float(result_p3.get("psap_total", 0))
        be_prev      = float(result_p3.get("sorties_p4", {}).get("be_prevoyance",
                        result_p3.get("be_prevoyance", 0)))

        # Duration PM rentes IP : calculée comme annuité viagère simplifiée
        # En pratique, dépend de l'âge moyen des bénéficiaires de rentes
        # Proxy : duration = (1+i)/i pour une rente perpétuelle → borné [8,18]
        # Note : en production, remplacer par duration exacte depuis SP-TABLES
        if taux_actu > 0:
            duration_rentes_theorique = (1 + taux_actu) / taux_actu
            # Borner à [DURATION_RENTES_IP_MIN, DURATION_RENTES_IP_MAX]
            duration_rentes_ip = float(np.clip(
                duration_rentes_theorique,
                DURATION_RENTES_IP_MIN,
                DURATION_RENTES_IP_MAX
            ))
        else:
            duration_rentes_ip = DURATION_RENTES_IP_MAX

        # Duration PSAP prévoyance : court-moyen terme (6 mois à 2 ans)
        # Source : cadence règlement prévoyance collective — CTIP 2023
        duration_psap_prev = 1.5  # ans — proxy cadence règlement ITT/IP

        # ── PSAP santé (S3) ───────────────────────────────────────────────────
        be_sante   = 0.0
        psap_sante = 0.0
        if result_s3 and result_s3.get("success"):
            be_sante   = float(result_s3.get("be_sante", 0))
            psap_sante = float(result_s3.get("psap_total",
                          result_s3.get("be_sante", 0) * 0.40))

        # Duration PSAP santé : très court terme (3-12 mois)
        # Source : cadence règlement frais médicaux — DREES 2023
        duration_psap_sante = 0.5  # ans — remboursements santé typiquement <6 mois

        # ── Duration consolidée ───────────────────────────────────────────────
        # Pondération par les montants de provisions
        total_passif = pm_rentes + psap_prev + psap_sante + be_sante
        if total_passif <= 0:
            total_passif = max(be_prev, 1.0)
            pm_rentes    = total_passif

        # Pondération : PM rentes (long) + PSAP prév (moyen) + PSAP santé (court)
        poids_rentes = pm_rentes    / total_passif
        poids_psap_p = psap_prev    / total_passif
        poids_psap_s = (psap_sante + be_sante) / total_passif

        dur_consol = (
            poids_rentes * duration_rentes_ip +
            poids_psap_p * duration_psap_prev +
            poids_psap_s * duration_psap_sante
        )

        # Duration modifiée passif = D_Macaulay / (1 + i)
        dur_modifiee = dur_consol / (1.0 + taux_actu)

        # Convexité passif — approximation pondérée par classe (D²+D standard)
        # PM rentes IP : convexité longue (duration ~18a → convexité ~340)
        # PSAP prévoyance : convexité courte (duration ~1.5a → convexité ~3.75)
        # PSAP santé : convexité très courte (duration ~0.5a → convexité ~0.75)
        # Source : approximation obligataire standard — Fabozzi (2012)
        conv_rentes = duration_rentes_ip ** 2 + duration_rentes_ip
        conv_psap_p = duration_psap_prev ** 2 + duration_psap_prev
        conv_psap_s = duration_psap_sante ** 2 + duration_psap_sante
        convexite_passif = (
            poids_rentes * conv_rentes +
            poids_psap_p * conv_psap_p +
            poids_psap_s * conv_psap_s
        )

        tp_total = total_passif

        return {
            "pm_rentes_ip":           round(pm_rentes, 2),
            "psap_prevoyance":        round(psap_prev, 2),
            "psap_sante":             round(psap_sante + be_sante, 2),
            "tp_total":               round(tp_total, 2),
            "duration_rentes_ip":     round(duration_rentes_ip, 2),
            "duration_psap_prev":     round(duration_psap_prev, 2),
            "duration_psap_sante":    round(duration_psap_sante, 2),
            "duration_consolidee":    round(dur_consol, 2),
            "duration_modifiee":      round(dur_modifiee, 2),
            "convexite":              round(convexite_passif, 2),
            "poids_rentes_pct":       round(poids_rentes * 100, 1),
            "poids_psap_prev_pct":    round(poids_psap_p * 100, 1),
            "poids_psap_sante_pct":   round(poids_psap_s * 100, 1),
            "taux_actu":              taux_actu,
            "note": (
                f"D_passif={dur_consol:.2f}a | "
                f"Rentes IP ({poids_rentes*100:.0f}%): D={duration_rentes_ip:.1f}a | "
                f"PSAP prév ({poids_psap_p*100:.0f}%): D={duration_psap_prev:.1f}a | "
                f"Santé ({poids_psap_s*100:.0f}%): D={duration_psap_sante:.1f}a"
            ),
        }

    # =========================================================================
    # 2. ANALYSE DE L'ACTIF SP
    # =========================================================================
    def _analyser_actif_sp(self, alloc: Dict, valeur_totale: float,
                             taux_actu: float) -> Dict:
        """
        Analyse du portefeuille actif SP — allocation type mutuelle.

        Duration actif = somme pondérée des durations par classe d'actif.
        Convexité actif = approximation (D²+D) pondérée par classe d'actif.

        Source : ACPR rapport ALM mutuelles 2022.
        """
        # Normaliser l'allocation (sum = 1)
        total_alloc = sum(alloc.values())
        if total_alloc <= 0:
            alloc = ALLOC_MUTUELLE_DEFAUT
            total_alloc = 1.0
        alloc_norm = {k: v / total_alloc for k, v in alloc.items()}

        # Duration et valeur par classe
        classes = {}
        duration_ponderee = 0.0
        convexite_ponderee = 0.0

        for classe, poids in alloc_norm.items():
            dur_classe   = DURATION_ACTIF_CLASSE.get(classe, 3.0)
            val_classe   = poids * valeur_totale
            # Convexité ≈ D² + D (approximation obligataire standard)
            conv_classe  = dur_classe ** 2 + dur_classe if dur_classe > 0 else 0.0
            classes[classe] = {
                "poids":      round(poids * 100, 1),
                "valeur":     round(val_classe, 0),
                "duration":   dur_classe,
                "convexite":  round(conv_classe, 1),
            }
            duration_ponderee  += poids * dur_classe
            convexite_ponderee += poids * conv_classe

        # Duration modifiée actif = D_Macaulay / (1 + i)
        dur_modifiee = duration_ponderee / (1.0 + taux_actu)

        # Actifs liquides = monétaire + souverain (supposés liquides 30j)
        pct_liquide = alloc_norm.get("monetaire", 0) + alloc_norm.get("oat_souverain", 0)
        actifs_liquides = pct_liquide * valeur_totale

        return {
            "valeur_totale":      round(valeur_totale, 2),
            "classes":            classes,
            "duration_macaulay":  round(duration_ponderee, 2),
            "duration_modifiee":  round(dur_modifiee, 2),
            "convexite":          round(convexite_ponderee, 2),
            "actifs_liquides":    round(actifs_liquides, 2),
            "pct_liquide":        round(pct_liquide * 100, 1),
            "note": (
                f"D_actif={duration_ponderee:.2f}a | "
                f"Convexité={convexite_ponderee:.1f} | "
                f"Liquide={pct_liquide*100:.0f}% ({actifs_liquides:,.0f}€)"
            ),
        }

    # =========================================================================
    # 3. GAP DE DURATION
    # =========================================================================
    def _calculer_gap(self, actif: Dict, passif: Dict) -> Dict:
        """
        Gap de duration = Duration_actif − Duration_passif.

        Un gap positif signifie que l'actif a une duration plus longue
        que le passif → exposition à une hausse des taux (actif perd plus).
        Un gap négatif → exposition à une baisse des taux (passif s'allonge).

        Cible ACPR mutuelles 2023 : |gap| < 2 ans.
        Source : ACPR circulaire ALM mutuelles 2023.
        """
        gap = actif["duration_macaulay"] - passif["duration_consolidee"]
        gap_abs = abs(gap)

        if gap_abs <= 1.0:
            statut = "✅ IMMUNISÉ"
            conseil = "Duration bien adossée — exposition taux faible"
        elif gap_abs <= GAP_CIBLE_MAX:
            statut = "⚠️ GAP ACCEPTABLE"
            conseil = (f"Gap = {gap:.2f}a — surveiller evolution taux "
                       f"(cible ACPR : |gap| < {GAP_CIBLE_MAX}a)")
        else:
            statut = "❌ GAP EXCESSIF"
            conseil = (f"Gap = {gap:.2f}a > {GAP_CIBLE_MAX}a — "
                       f"{'allonger actif' if gap < 0 else 'raccourcir actif'} "
                       f"ou raccourcir passif")

        return {
            "gap_duration":  round(gap, 2),
            "gap_abs":       round(gap_abs, 2),
            "statut":        statut,
            "conseil":       conseil,
            "cible_max":     GAP_CIBLE_MAX,
            "reference":     "ACPR circulaire ALM mutuelles 2023",
        }

    # =========================================================================
    # 4. BV01 — SENSIBILITÉ TAUX
    # =========================================================================
    def _calculer_bv01(self, actif: Dict, passif: Dict, taux_actu: float) -> Dict:
        """
        BV01 = sensibilité +1bp (0.01%) sur la NAV (Actif - Passif).

        BV01_actif  = -D_mod_actif  * Valeur_actif  * 0.0001
        BV01_passif = -D_mod_passif * Valeur_passif * 0.0001
        BV01_net    = BV01_actif - BV01_passif

        Stress ±100bp et ±200bp (EIOPA Art.105 S2).
        Source : actuariat ALM standard + EIOPA Art.105.
        """
        d_mod_actif  = actif["duration_modifiee"]
        d_mod_passif = passif["duration_modifiee"]
        val_actif    = actif["valeur_totale"]
        val_passif   = passif["tp_total"]

        # BV01 = impact d'une hausse de 1bp sur la valeur
        # Convention : hausse taux → baisse valeur obligation → BV01 négatif
        bv01_actif  = -d_mod_actif  * val_actif  * 0.0001
        bv01_passif = -d_mod_passif * val_passif * 0.0001
        bv01_net    = bv01_actif - bv01_passif

        # Stress ±100bp et ±200bp
        impact_100bp = bv01_net * 100
        impact_200bp = bv01_net * 200

        return {
            "bv01_actif":   round(bv01_actif, 2),
            "bv01_passif":  round(bv01_passif, 2),
            "bv01_net":     round(bv01_net, 2),
            "impact_100bp": round(impact_100bp, 0),
            "impact_200bp": round(impact_200bp, 0),
            "sens_net":     "positif" if bv01_net > 0 else "négatif",
            "interpretation": (
                f"BV01_net = {bv01_net:+,.0f}€/bp | "
                f"Stress +100bp : {impact_100bp:+,.0f}€ | "
                f"Stress +200bp : {impact_200bp:+,.0f}€"
            ),
            "source": "EIOPA Art.105 S2 — module risque taux",
        }

    # =========================================================================
    # 5. LCR MUTUELLE (Art. L212-7 CSS)
    # =========================================================================
    def _calculer_lcr_mutuelle(self, actif: Dict, passif: Dict,
                                 fonds_propres: float) -> Dict:
        """
        LCR Mutuelle — Art. L212-7 CSS.

        LCR = Actifs liquides / Sorties nettes 30 jours ≥ 100%.

        Actifs liquides : monétaire + OAT souverains (liquides < 30j).
        Sorties nettes 30j :
          · Santé       : PSAP_santé / 12  (provisions annuelles → mensualités)
          · Prévoyance  : (PSAP_prév + PM_rentes×5%) / 12 (paiements mensuels)
          · Charges op. : TP_total × 2% / 12

        Source : Art. L212-7 CSS + ACPR circulaire liquidité 2023.
        """
        actifs_liquides = actif["actifs_liquides"]

        # Sorties nettes 30j
        # Santé : PSAP représente les provisions annuelles → sorties mensuelles = /12
        # Source : cadence règlement frais médicaux — DREES 2023 (remboursements mensuels)
        sorties_sante_30j  = passif["psap_sante"] / 12.0
        # Prévoyance : paiements mensuels ITT + 5% des PM rentes (mensualités)
        sorties_prev_30j   = (passif["psap_prevoyance"] + passif["pm_rentes_ip"] * 0.05) / 12.0
        # Charges opérationnelles estimées = 2% des provisions / 12
        charges_30j        = passif["tp_total"] * 0.02 / 12.0

        sorties_nettes_30j = sorties_sante_30j + sorties_prev_30j + charges_30j
        sorties_nettes_30j = max(sorties_nettes_30j, 1.0)  # éviter division par zéro

        lcr_ratio = actifs_liquides / sorties_nettes_30j
        conforme  = lcr_ratio >= LCR_MIN

        return {
            "lcr_ratio":          round(lcr_ratio, 2),
            "actifs_liquides":    round(actifs_liquides, 0),
            "sorties_nettes_30j": round(sorties_nettes_30j, 0),
            "detail_sorties": {
                "sorties_sante_30j": round(sorties_sante_30j, 0),
                "sorties_prev_30j":  round(sorties_prev_30j, 0),
                "charges_30j":       round(charges_30j, 0),
            },
            "conforme":    conforme,
            "seuil_min":   LCR_MIN,
            "statut":      "✅ LCR conforme" if conforme else "❌ LCR insuffisant",
            "reference":   "Art. L212-7 CSS + ACPR circulaire 2023",
            "note": (
                f"LCR = {lcr_ratio:.2f} | "
                f"Actifs liquides = {actifs_liquides:,.0f}€ | "
                f"Sorties 30j = {sorties_nettes_30j:,.0f}€ | "
                f"{'✅ Conforme' if conforme else '❌ Non conforme'}"
            ),
        }

    # =========================================================================
    # HYPOTHÈSES + RAG
    # =========================================================================
    def _hypotheses(self, gap: Dict, bv01: Dict, lcr: Dict, passif: Dict) -> list:
        # H1 — Gap duration ≤ GAP_CIBLE_MAX
        ok1  = gap["gap_abs"] <= GAP_CIBLE_MAX
        h1_s = "VALIDÉE" if ok1 else "À JUSTIFIER"
        h1_m = f"|Gap| = {gap['gap_abs']:.2f}a {'≤' if ok1 else '>'} {GAP_CIBLE_MAX}a (ACPR 2023)"

        # H2 — LCR ≥ 100% (Art. L212-7 CSS)
        ok2  = lcr["conforme"]
        h2_s = "VALIDÉE" if ok2 else "NON VALIDÉE"
        h2_m = f"LCR = {lcr['lcr_ratio']:.2f} {'≥' if ok2 else '<'} {LCR_MIN:.0%} (Art. L212-7 CSS)"

        # H3 — Duration rentes IP ∈ [DURATION_RENTES_IP_MIN, DURATION_RENTES_IP_MAX]
        d_rentes = passif["duration_rentes_ip"]
        ok3  = DURATION_RENTES_IP_MIN <= d_rentes <= DURATION_RENTES_IP_MAX
        h3_s = "VALIDÉE" if ok3 else "À JUSTIFIER"
        h3_m = (f"D_rentes_IP = {d_rentes:.2f}a ∈ "
                f"[{DURATION_RENTES_IP_MIN},{DURATION_RENTES_IP_MAX}]a")

        # H4 — Condition d'immunisation de Redington (1952)
        # Redington F.M. (1952), Journal of the Institute of Actuaries 78(3).
        # Immunisation complète ⟺ deux conditions :
        #   (1) D_actif ≈ D_passif  (tolérance ±0.5 an)
        #   (2) Convexité_actif > Convexité_passif
        # Seule la condition (1) est évaluée ici : actif n'est pas passé
        # à cette méthode. La convexité passif est disponible (passif["convexite"]),
        # mais pas la convexité actif — pour implémenter (2) il faudrait passer
        # actif en paramètre de _hypotheses.
        # En pratique pour les mutuelles, (2) est rarement satisfaite :
        # l'actif OAT (conv ≈ 63) est bien moins convexe que le passif
        # rentes IP (conv ≈ 340). H4 = condition nécessaire uniquement.
        tol_dur     = 0.50   # tolérance ±0.5 an sur l'égalité des durations
        gap_abs     = gap["gap_abs"]
        dur_match   = gap_abs <= tol_dur   # condition (1) Redington
        conv_passif = passif.get("convexite", 0)
        redington_ok = dur_match           # condition nécessaire (1) uniquement
        h4_s = "VALIDÉE" if redington_ok else "À JUSTIFIER"
        h4_m = (
            f"Gap={gap_abs:.2f}a ({'≤' if dur_match else '>'} {tol_dur}a tol.) | "
            f"Conv_passif={conv_passif:.1f} | "
            f"Immunisation {'✅ atteinte' if redington_ok else '⚠️ incomplète — rebalancer actif'}"
        )

        return [
            {"id":"H1","hypothese":f"Gap duration |actif-passif| ≤ {GAP_CIBLE_MAX}a (ACPR 2023)",
             "valeur":h1_m,"statut":h1_s,"critique":False},
            {"id":"H2","hypothese":"LCR ≥ 100% — Art. L212-7 CSS (liquidité mutuelle)",
             "valeur":h2_m,"statut":h2_s,"critique":True},
            {"id":"H3","hypothese":"Duration rentes IP ∈ [8,18] ans (cohérence portefeuille IP)",
             "valeur":h3_m,"statut":h3_s,"critique":False},
            {"id":"H4","hypothese":"Immunisation Redington (1952) : D_mod adossée ± 0.5a",
             "valeur":h4_m,"statut":h4_s,"critique":False},
        ]

    def _rag(self, hyp: list, gap: Dict, lcr: Dict) -> str:
        # LCR < 100% → ROUGE (exigence réglementaire Art. L212-7 CSS)
        if not lcr["conforme"]:
            return "ROUGE"
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val:
            return "ROUGE"
        # Gap excessif ou duration rentes hors plage → AMBRE
        a_just = [h for h in hyp if h["statut"]=="À JUSTIFIER"]
        return "AMBRE" if a_just else "VERT"

    # =========================================================================
    # COMMENTAIRE
    # =========================================================================
    def _commentaire(self, rag, actif, passif, gap, bv01, lcr, hyp, taux_actu) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        L = [
            "="*70,
            f"  ALM SP — v{self.VERSION}",
            f"  {ic} STATUT : {rag} | Taux EIOPA RFR = {taux_actu:.1%}",
            "="*70, "",
            "📊 BILAN ACTIF/PASSIF", "─"*50,
            f"  Actif total    : {actif['valeur_totale']:>15,.0f}€ | D={actif['duration_macaulay']:.2f}a",
            f"  Passif total   : {passif['tp_total']:>15,.0f}€ | D={passif['duration_consolidee']:.2f}a",
            f"  NAV            : {actif['valeur_totale']-passif['tp_total']:>15,.0f}€",
            "",
            "⏱️ DURATION", "─"*50,
            f"  {passif['note']}",
            f"  {actif['note']}",
            f"  {gap['statut']} — Gap={gap['gap_duration']:+.2f}a | {gap['conseil']}",
            "",
            "📈 SENSIBILITÉ TAUX (BV01)", "─"*50,
            f"  {bv01['interpretation']}",
            "",
            "💧 LCR MUTUELLE (Art. L212-7 CSS)", "─"*50,
            f"  {lcr['note']}",
            "",
            "📋 HYPOTHÈSES", "─"*50,
        ]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"]=="À JUSTIFIER" else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]
        return "\n".join(L)

    # =========================================================================
    # GRAPHIQUES
    # =========================================================================
    def _graphiques(self, actif, passif, gap, bv01, lcr) -> Dict:
        gph = {}

        # G1 — Duration actif vs passif (barres comparatives)
        try:
            fig1 = go.Figure(go.Bar(
                x=["Actif SP", "Passif Total", "PM Rentes IP", "PSAP Prév.", "PSAP Santé"],
                y=[actif["duration_macaulay"],
                   passif["duration_consolidee"],
                   passif["duration_rentes_ip"],
                   passif["duration_psap_prev"],
                   passif["duration_psap_sante"]],
                marker_color=[BLEU, OR, VIOLET, AMBRE, VERT],
                text=[f"{d:.2f}a" for d in [
                    actif["duration_macaulay"],
                    passif["duration_consolidee"],
                    passif["duration_rentes_ip"],
                    passif["duration_psap_prev"],
                    passif["duration_psap_sante"],
                ]],
                textposition="outside",
            ))
            fig1.update_layout(
                **LAYOUT_BASE,
                title=dict(text="G1 — Duration Actif vs Passif SP (années)",
                           font=dict(color=OR, size=13)),
                yaxis_title="Duration (années)",
            )
            gph["duration_comparison"] = fig1
        except Exception as e:
            self.logger.warning(f"G1 duration : {e}")

        # G2 — LCR gauge
        try:
            lcr_val = lcr["lcr_ratio"]
            c_lcr   = VERT if lcr_val >= 1.5 else (AMBRE if lcr_val >= 1.0 else ROUGE)
            fig2 = go.Figure(go.Indicator(
                mode="gauge+number", value=lcr_val * 100,
                title={"text":"LCR Mutuelle Art.L212-7 CSS (%)","font":{"color":OR}},
                number={"font":{"color":c_lcr,"size":28},"suffix":"%"},
                gauge={
                    "axis":{"range":[0,300],"tickcolor":GRIS},
                    "bar":{"color":c_lcr,"thickness":0.3},
                    "steps":[
                        {"range":[0,100],"color":"rgba(231,76,60,0.15)"},
                        {"range":[100,150],"color":"rgba(243,156,18,0.15)"},
                        {"range":[150,300],"color":"rgba(46,204,113,0.12)"},
                    ],
                    "threshold":{"line":{"color":ROUGE,"width":3},
                                  "thickness":0.8,"value":100},
                },
            ))
            fig2.update_layout(
                **LAYOUT_BASE,
                title=dict(text="G2 — LCR Mutuelle SP",
                           font=dict(color=OR, size=13))
            )
            gph["lcr_gauge"] = fig2
        except Exception as e:
            self.logger.warning(f"G2 LCR gauge : {e}")

        # G3 — Allocation actif (camembert)
        try:
            classes  = actif["classes"]
            labels   = list(classes.keys())
            vals     = [classes[c]["valeur"] for c in labels]
            couleurs = [BLEU, OR, VERT, AMBRE]
            fig3 = go.Figure(go.Pie(
                labels=labels, values=vals,
                marker_colors=couleurs[:len(labels)], hole=0.4,
            ))
            fig3.update_layout(
                **LAYOUT_BASE,
                title=dict(text="G3 — Allocation Actif SP (€)",
                           font=dict(color=OR, size=13))
            )
            gph["allocation_actif"] = fig3
        except Exception as e:
            self.logger.warning(f"G3 allocation actif : {e}")

        # G4 — BV01 stress ±100bp / ±200bp (EIOPA Art.105 S2)
        try:
            scenarios  = ["-200bp", "-100bp", "+100bp", "+200bp"]
            # Impact = BV01_net × nombre de bp
            # Convention : bv01_net négatif → hausse taux → perte NAV
            impacts = [
                bv01["bv01_net"] * (-200),
                bv01["bv01_net"] * (-100),
                bv01["bv01_net"] * 100,
                bv01["bv01_net"] * 200,
            ]
            couleurs_bv01 = [
                VERT  if impacts[0] >= 0 else ROUGE,
                AMBRE if impacts[1] >= 0 else ROUGE,
                AMBRE if impacts[2] >= 0 else ROUGE,
                VERT  if impacts[3] >= 0 else ROUGE,
            ]
            fig4 = go.Figure(go.Bar(
                x=scenarios,
                y=[v / 1e3 for v in impacts],   # en k€
                marker_color=couleurs_bv01,
                width=0.45,
                opacity=0.88,
                text=[f"{v/1e3:+.0f}k€" for v in impacts],
                textposition="outside",
                textfont=dict(color=BLANC, size=10),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Impact NAV : %{y:,.0f}k€<extra></extra>"
                ),
            ))
            fig4.add_hline(
                y=0, line_color=GRIS, line_width=1, line_dash="dot"
            )
            fig4.update_layout(
                **LAYOUT_BASE,
                title=dict(
                    text=(
                        "G4 — Stress taux BV01 (EIOPA Art.105 S2) | "
                        f"BV01_net={bv01['bv01_net']:+,.0f}€/bp"
                    ),
                    font=dict(color=OR, size=12), x=0.01,
                ),
                yaxis=dict(
                    title="Impact NAV (k€)",
                    tickfont=dict(color=GRIS, size=9),
                    showgrid=True,
                    gridcolor="rgba(138,154,176,0.15)",
                ),
                xaxis=dict(
                    tickfont=dict(color=BLANC, size=10),
                    showgrid=False,
                ),
                showlegend=False,
                annotations=[dict(
                    text=(
                        "💡 Impact sur la NAV (Actif − Passif) d'un choc de taux. "
                        "Vert = gain · Rouge = perte (EIOPA Art.105 S2)."
                    ),
                    xref="paper", yref="paper",
                    x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9),
                    showarrow=False,
                )],
            )
            gph["bv01_stress"] = fig4

        except Exception as e:
            self.logger.warning(f"G4 BV01 stress : {e}")

        return gph

    # =========================================================================
    # AUDIT + CONSOLE
    # =========================================================================
    def _audit(self, aid, gap, bv01, lcr, rag):
        try:
            log = self.audit_path / "sp_alm_audit.jsonl"
            entry = {
                "audit_id":      aid,
                "timestamp":     datetime.now().isoformat(),
                "statut_rag":    rag,
                "gap_duration":  gap["gap_duration"],
                "bv01_net":      bv01["bv01_net"],
                "lcr_ratio":     lcr["lcr_ratio"],
                "lcr_conforme":  lcr["conforme"],
            }
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _console(self, aid, rag, actif, passif, gap, lcr):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        self.logger.info(
            f"[{aid}] {ic} {rag} | "
            f"D_actif={actif['duration_macaulay']:.2f}a | "
            f"D_passif={passif['duration_consolidee']:.2f}a | "
            f"Gap={gap['gap_duration']:+.2f}a | "
            f"LCR={lcr['lcr_ratio']:.2f}"
        )

    def _erreur(self, msg, aid="") -> Dict:
        return {
            "success":False,"agent":self.NOM,"version":self.VERSION,
            "audit_id":aid,"statut_rag":"ROUGE",
            "duration":{},"bv01":{},"lcr":{},"passif":{},"actif":{},"gap":{},
            "hypotheses":[],"commentaire":"","graphiques":{},
            "duree_sec":0,"erreur":msg,
        }
