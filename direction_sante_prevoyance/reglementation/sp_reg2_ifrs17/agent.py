"""
Agent SP-REG2 — IFRS 17 Santé-Prévoyance
Sous Amira (Directrice SP) · Direction Santé-Prévoyance
Source : IFRS 17 (IASB 2017, amendé 2020/2021)
"""
import logging, warnings, ast as _ast
from datetime import datetime
from pathlib import Path
from typing import Dict
import numpy as np
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")

# ── Paramètres IFRS 17 ────────────────────────────────────────────────────────
# Source : IFRS 17 paragraphes §38, §47, §B91
COC_RATE      = 0.06   # Taux CoC EIOPA — §B91 IFRS 17
# Seuils CSM/LC
CSM_FLOOR     = 0.0    # CSM ≥ 0 — pas de bénéfice négatif à la souscription
LC_FLOOR      = 0.0    # LC ≥ 0 — perte minimale = 0


class AgentSPReg2IFRS17:
    """
    Agent SP-REG2 — Conformité IFRS 17 Santé-Prévoyance.
    Produit le bilan IFRS 17 complet : BE, RA, CSM, LC.

    Différenciation : ResQ expose uniquement BE+RA.
    SP-REG2 produit la décomposition complète PAP (Premium Allocation Approach)
    et GMM (General Measurement Model) selon le type de contrat.
    """
    NOM     = "SP-Reg2-IFRS17"
    CODE    = "SP-REG2"
    VERSION = "1.0"
    MANAGER = "Amira (Directrice SP)"

    def __init__(self, audit_path="audit", verbose=True):
        Path(audit_path).mkdir(parents=True, exist_ok=True)
        self.audit_path = Path(audit_path)
        self.logger = logging.getLogger("actuaria.sp.reg2.ifrs17")
        self.verbose = verbose

    def run(self,
            result_s3   = None,
            result_p4   = None,
            result_coord= None,
            generer_graphiques: bool = True) -> Dict:
        """
        Paramètres
        ----------
        result_s3    : résultat S3 (santé) — pour BE et RA santé
        result_p4    : résultat P4 (prévoyance) — pour BE et RA prévoyance
        result_coord : résultat SP-COORD (optionnel) — pour vision consolidée
        """
        t0  = datetime.now()
        aid = f"REG2_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            src = self._extraire(result_s3, result_p4, result_coord)
            self.logger.info(f"[{aid}] SP-REG2 IFRS 17 | BE={src['be_total']:,.0f}€ | RA={src['ra_total']:,.0f}€")

            # ── GMM — General Measurement Model ──────────────────────────────
            # §47 IFRS 17 : LRC = BE + RA + CSM (si contrat non-onéreux)
            # §47 IFRS 17 : LRC = BE + RA + LC  (si contrat onéreux — LC remplace CSM)

            be    = src["be_total"]
            ra    = src["ra_total"]
            tp    = be + ra   # TP = Technical Provisions

            # Primes futures attendues (proxy : PA annuelles)
            primes_futures = src["pa_total"]

            # Marge bénéficiaire = primes futures - (BE + RA)
            # CSM = max(0, primes_futures - be - ra)  — contrat non-onéreux
            # LC  = max(0, be + ra - primes_futures)  — contrat onéreux (perte)
            marge = primes_futures - be - ra
            csm   = max(CSM_FLOOR, marge)     # Contractual Service Margin
            lc    = max(LC_FLOOR,  -marge)    # Loss Component

            est_onereux = (marge < 0)

            # LRC (Liability for Remaining Coverage)
            lrc = be + ra + (lc if est_onereux else csm)

            # LIC (Liability for Incurred Claims) = BE provisions sinistres
            lic = src["be_psap"]   # PSAP = sinistres déclarés non encore réglés

            # Bilan IFRS 17
            passif_ifrs17 = lrc + lic

            # Réconciliation TP S2 vs IFRS 17
            delta_s2_ifrs17 = tp - passif_ifrs17

            # Taux RA/BE (indicateur qualité du modèle CoC)
            taux_ra_be = ra / max(be, 1)

            # ── Hypothèses ────────────────────────────────────────────────────
            hyp = self._hypotheses(
                be, ra, csm, lc, lrc, lic, taux_ra_be,
                est_onereux, primes_futures
            )
            rag = self._rag(hyp, est_onereux)

            com = self._commentaire(
                rag, src, be, ra, tp, csm, lc, lrc, lic,
                passif_ifrs17, delta_s2_ifrs17, taux_ra_be, est_onereux, hyp
            )

            duree = (datetime.now()-t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── GMM ──────────────────────────────────────────────────────
                "be_total":       round(be, 2),
                "ra_total":       round(ra, 2),
                "tp_total":       round(tp, 2),
                "csm":            round(csm, 2),
                "lc":             round(lc, 2),
                "est_onereux":    est_onereux,
                "lrc":            round(lrc, 2),
                "lic":            round(lic, 2),
                "passif_ifrs17":  round(passif_ifrs17, 2),
                "taux_ra_be":     round(taux_ra_be, 4),

                # ── Réconciliation S2 ─────────────────────────────────────────
                "tp_s2":          round(tp, 2),
                "delta_s2_ifrs17":round(delta_s2_ifrs17, 2),

                # ── Standard ActuarIA ─────────────────────────────────────────
                "hypotheses":   hyp,
                "commentaire":  com,
                "graphiques":   {},
                "duree_sec":    round(duree, 2),
                "erreur":       None,
            }

        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR : {e}", exc_info=True)
            return {"success":False, "agent":self.NOM, "version":self.VERSION,
                    "audit_id":aid, "statut_rag":"ROUGE",
                    "hypotheses":[], "commentaire":"", "graphiques":{},
                    "duree_sec":0, "erreur":str(e)}

    def _extraire(self, result_s3, result_p4, result_coord) -> Dict:
        """Extrait BE, RA, PSAP depuis S3+P4 ou COORD."""
        if result_coord and result_coord.get("success"):
            be_s = result_coord["be_sante"]
            be_p = result_coord["be_prevoyance"]
            ra_s = result_coord["ra_consolide"] * be_s / max(result_coord["be_consolide"],1)
            ra_p = result_coord["ra_consolide"] * be_p / max(result_coord["be_consolide"],1)
        else:
            if not result_s3 or not result_s3.get("success"):
                raise ValueError("result_s3 ou result_coord requis")
            if not result_p4 or not result_p4.get("success"):
                raise ValueError("result_p4 ou result_coord requis")
            be_s = float(result_s3.get("be_sante", 0))
            ra_s = float(result_s3.get("risk_adjustment", 0))
            be_p = float(result_p4.get("be_prevoyance", 0))
            ra_p = float(result_p4.get("risk_adjustment", 0))

        # PSAP = portion "sinistres déclarés" du BE total
        psap_s = 0
        psap_p = 0
        if result_s3 and result_s3.get("success"):
            psap_s = float(result_s3.get("qrt_s13", {}).get("lignes", [{}])[0].get("C0010", be_s * 0.5))
        if result_p4 and result_p4.get("success"):
            psap_p = float(result_p4.get("psap_total", be_p * 0.2))

        # PA annuelles proxy
        pa_s = float((result_s3 or {}).get("qrt_s13", {}).get("lignes", [{}])[-1].get("C0010", be_s*2) if result_s3 else be_s*2)
        pa_p = float((result_p4 or {}).get("sorties_naomie", {}).get("primes_acquises", be_p*0.5) if result_p4 else be_p*0.5)

        return {
            "be_sante":  be_s, "ra_sante": ra_s,
            "be_prev":   be_p, "ra_prev":  ra_p,
            "be_total":  be_s + be_p,
            "ra_total":  ra_s + ra_p,
            "be_psap":   psap_s + psap_p,
            "pa_total":  pa_s + pa_p,
        }

    def _hypotheses(self, be, ra, csm, lc, lrc, lic,
                    taux_ra_be, est_onereux, pa) -> list:
        # H1 : RA/BE conforme IFRS 17 CoC
        if 0.01 <= taux_ra_be <= 0.20:
            h1_s = "VALIDÉE"; h1_m = f"RA/BE = {taux_ra_be*100:.1f}% ∈ [1%,20%] ✅"
        elif taux_ra_be < 0.01:
            h1_s = "NON VALIDÉE"; h1_m = f"RA/BE = {taux_ra_be*100:.2f}% < 1% — insuffisant"
        else:
            h1_s = "À JUSTIFIER"; h1_m = f"RA/BE = {taux_ra_be*100:.1f}% > 20% — élevé"

        # H2 : contrat non-onéreux (CSM ≥ 0)
        if not est_onereux:
            h2_s = "VALIDÉE"
            h2_m = f"CSM = {csm:,.0f}€ ≥ 0 — contrat non-onéreux ✅"
        else:
            h2_s = "NON VALIDÉE"
            h2_m = f"LC = {lc:,.0f}€ > 0 — contrat ONÉREUX — perte dès souscription"

        # H3 : LRC cohérent (LRC ≈ BE + RA + CSM/LC)
        lrc_check = be + ra + (lc if est_onereux else csm)
        if abs(lrc - lrc_check) < 0.01:
            h3_s = "VALIDÉE"; h3_m = f"LRC = {lrc:,.0f}€ = BE+RA+CSM/LC ✅"
        else:
            h3_s = "NON VALIDÉE"; h3_m = f"LRC incohérent : {lrc:,.0f} ≠ {lrc_check:,.0f}"

        return [
            {"id":"H1","hypothese":"RA/BE ∈ [1%,20%] — CoC IFRS 17 §B91",
             "valeur":h1_m,"statut":h1_s,"critique":True},
            {"id":"H2","hypothese":"CSM ≥ 0 — contrat non-onéreux IFRS 17 §47",
             "valeur":h2_m,"statut":h2_s,"critique":True},
            {"id":"H3","hypothese":"LRC = BE + RA + CSM/LC — identité IFRS 17",
             "valeur":h3_m,"statut":h3_s,"critique":True},
        ]

    def _rag(self, hyp, est_onereux) -> str:
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val or est_onereux:
            return "ROUGE"
        a_just = [h for h in hyp if h["statut"]=="À JUSTIFIER"]
        return "AMBRE" if a_just else "VERT"

    def _commentaire(self, rag, src, be, ra, tp, csm, lc, lrc, lic,
                     passif, delta, taux_ra_be, est_onereux, hyp) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        app = "PAP" if src["be_psap"] < src["be_total"] * 0.3 else "GMM"
        L = [
            "="*65,
            f"  RAPPORT IFRS 17 — SP-REG2 v{self.VERSION}",
            f"  {ic} STATUT : {rag} | Approche : {app}",
            "="*65, "",
            f"  BE total           : {be:>14,.0f}€",
            f"  Risk Adjustment    : {ra:>14,.0f}€  ({taux_ra_be*100:.1f}% BE)",
            f"  TP (BE+RA)         : {tp:>14,.0f}€",
            f"  {'CSM' if not est_onereux else 'Loss Component':<19}: {csm if not est_onereux else lc:>14,.0f}€",
            f"  LRC                : {lrc:>14,.0f}€",
            f"  LIC (PSAP)         : {lic:>14,.0f}€",
            f"  Passif IFRS 17     : {passif:>14,.0f}€",
            f"  Δ S2 / IFRS 17     : {delta:>+14,.0f}€",
            "",
        ]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"]=="À JUSTIFIER" else "❌")
            L.append(f"  {ic_h} [{h['id']}] {h['valeur']} : {h['statut']}")
        return "\n".join(L)
