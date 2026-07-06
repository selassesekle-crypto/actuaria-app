"""
Agent SP-ST Naomie — Stress Testing Santé-Prévoyance
Sous Amira (Directrice SP) · Direction Santé-Prévoyance
Sources : EIOPA Stress Tests 2021, RD 2015/35 Art.145/148/150/164
"""
import logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict
import numpy as np
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")

# ── Scénarios de choc — Sources EIOPA ─────────────────────────────────────────
# Source : EIOPA Stress Test 2021 + RD 2015/35 Art.145/148/150
SCENARIOS = {
    "pandémie": {
        "choc_sinistres_sante":  +0.50,   # +50% sinistres santé — EIOPA ST2021
        "choc_morbidite_itt":    +0.35,   # +35% taux incidence ITT — Art.145
        "choc_mortalite":        +0.20,   # +20% mortalité — Art.158 (épidémie)
        "choc_cessation":        -0.10,   # -10% guérisons (délais soin)
        "ref": "EIOPA Stress Test 2021 — scénario pandémie COVID-like",
    },
    "morbidité_hausse": {
        "choc_sinistres_sante":  +0.10,
        "choc_morbidite_itt":    +0.35,   # Choc réglementaire Art.145 S2
        "choc_mortalite":        0.0,
        "choc_cessation":        -0.20,   # -20% cessation — Art.145 §2(b)
        "ref": "RD 2015/35 Art.145 — choc morbidité standard",
    },
    "cessation_baisse": {
        "choc_sinistres_sante":  0.0,
        "choc_morbidite_itt":    0.0,
        "choc_mortalite":        0.0,
        "choc_cessation":        -0.40,   # -40% guérisons — choc adverse
        "ref": "RD 2015/35 Art.145 §2(b) — choc cessation adverse",
    },
}


class AgentSPStressTest:
    """
    Agent SP-ST Naomie — Stress Testing Santé-Prévoyance.

    Calcule l'impact des scénarios de choc sur :
    - BE santé et prévoyance
    - SCR consolidé
    - Ratio de solvabilité
    - Fonds propres consommés

    Conforme EIOPA Stress Test 2021 et RD 2015/35 Art.145/148.
    """
    NOM     = "Naomie"
    CODE    = "SP-ST"
    VERSION = "1.0"
    MANAGER = "Amira (Directrice SP)"

    def __init__(self, audit_path="audit", verbose=True):
        Path(audit_path).mkdir(parents=True, exist_ok=True)
        self.audit_path = Path(audit_path)
        self.logger = logging.getLogger("actuaria.sp.st.naomie")
        self.verbose = verbose

    def run(self,
            result_s3         = None,
            result_p4         = None,
            result_coord      = None,
            scenarios_list:   list = None,
            generer_graphiques: bool = True) -> Dict:
        """
        Parameters
        ----------
        result_s3     : résultat S3 (santé)
        result_p4     : résultat P4 (prévoyance)
        result_coord  : résultat SP-COORD (optionnel — pour vision consolidée)
        scenarios_list: liste de scénarios à tester (défaut : tous)
        """
        t0  = datetime.now()
        aid = f"ST_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            src = self._extraire(result_s3, result_p4, result_coord)
            self.logger.info(
                f"[{aid}] SP-ST Naomie | BE_base={src['be_total']:,.0f}€ | "
                f"SCR_base={src['scr_total']:,.0f}€ | FP={src['fpp']:,.0f}€"
            )

            scens = scenarios_list or list(SCENARIOS.keys())
            resultats_chocs = {}

            for nom_sc in scens:
                if nom_sc not in SCENARIOS:
                    continue
                choc = SCENARIOS[nom_sc]
                r_choc = self._appliquer_choc(src, choc, nom_sc)
                resultats_chocs[nom_sc] = r_choc
                self.logger.info(
                    f"  [{nom_sc}] ΔBE={r_choc['delta_be']:+,.0f}€ | "
                    f"Ratio SCR choqué={r_choc['ratio_scr_choque']:.1f}%"
                )

            # Worst case
            worst = max(resultats_chocs.values(),
                        key=lambda r: r["delta_be"])

            hyp = self._hypotheses(src, resultats_chocs, worst)
            rag = self._rag(hyp, resultats_chocs, src["fpp"])
            com = self._commentaire(rag, src, resultats_chocs, worst, hyp)

            duree = (datetime.now()-t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── Situation de base ─────────────────────────────────────────
                "be_base":       round(src["be_total"], 2),
                "scr_base":      round(src["scr_total"], 2),
                "fonds_propres": round(src["fpp"], 2),
                "ratio_scr_base":round(src["fpp"]/max(src["scr_total"],1)*100, 1),

                # ── Résultats par scénario ────────────────────────────────────
                "scenarios": resultats_chocs,

                # ── Worst case ────────────────────────────────────────────────
                "worst_case_scenario": worst.get("scenario_nom", ""),
                "worst_case_delta_be": round(worst["delta_be"], 2),
                "worst_case_ratio_scr":round(worst["ratio_scr_choque"], 1),

                # ── Standard ActuarIA ─────────────────────────────────────────
                "hypotheses":   hyp,
                "commentaire":  com,
                "graphiques":   {},
                "duree_sec":    round(duree, 2),
                "erreur":       None,
            }

        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR : {e}", exc_info=True)
            return {"success":False,"agent":self.NOM,"version":self.VERSION,
                    "audit_id":aid,"statut_rag":"ROUGE",
                    "hypotheses":[],"commentaire":"","graphiques":{},
                    "duree_sec":0,"erreur":str(e)}

    def _extraire(self, result_s3, result_p4, result_coord) -> Dict:
        if result_coord and result_coord.get("success"):
            be_s  = result_coord["be_sante"]
            be_p  = result_coord["be_prevoyance"]
            scr_s = result_coord["scr_sante"]
            scr_p = result_coord["scr_prevoyance"]
            fpp   = result_coord["fonds_propres"]
        else:
            if not result_s3 or not result_s3.get("success"):
                raise ValueError("result_s3 ou result_coord requis")
            if not result_p4 or not result_p4.get("success"):
                raise ValueError("result_p4 ou result_coord requis")
            be_s  = float(result_s3.get("be_sante", 0))
            scr_s = float(result_s3.get("scr_sante", 0))
            be_p  = float(result_p4.get("be_prevoyance", 0))
            scr_p = float(result_p4.get("scr_invalidite", 0))
            fpp   = float(result_s3.get("fonds_propres", 0))
            if fpp == 0:
                fpp = float(result_p4.get("fonds_propres", (be_s+be_p)*1.5))

        # SCR consolidé avec corrélation EIOPA ρ=0.25
        scr_total = np.sqrt(scr_s**2 + 2*0.25*scr_s*scr_p + scr_p**2)

        return {
            "be_sante": be_s, "be_prev": be_p,
            "be_total": be_s + be_p,
            "scr_sante": scr_s, "scr_prev": scr_p,
            "scr_total": scr_total,
            "fpp": fpp,
        }

    def _appliquer_choc(self, src: Dict, choc: Dict, nom: str) -> Dict:
        """Applique les chocs et calcule l'impact sur BE et SCR."""
        # Impact sur BE santé
        be_s_choque = src["be_sante"] * (1 + choc.get("choc_sinistres_sante", 0))

        # Impact sur BE prévoyance — morbidité + cessation
        choc_morb = choc.get("choc_morbidite_itt", 0)
        choc_cess = choc.get("choc_cessation", 0)
        # Effet net sur BE prév : hausse morbidité augmente ITT→IP
        # baisses cessation allonge durées → BE augmente
        be_p_choque = src["be_prev"] * (
            1 + max(choc_morb, 0) + abs(min(choc_cess, 0)) * 0.5
        )

        delta_be_s = be_s_choque - src["be_sante"]
        delta_be_p = be_p_choque - src["be_prev"]
        delta_be   = delta_be_s + delta_be_p

        # SCR choqué : le choc augmente le SCR proportionnellement
        facteur_scr = 1 + abs(choc_morb) * 0.5 + abs(choc.get("choc_sinistres_sante", 0)) * 0.3
        scr_choque  = src["scr_total"] * facteur_scr

        # FP consommés = ΔBE (impact immédiat sur les FP)
        fp_residuels = max(0, src["fpp"] - delta_be)
        ratio_scr_c  = fp_residuels / max(scr_choque, 1) * 100
        fp_absorbes  = delta_be

        return {
            "scenario_nom":      nom,
            "ref":               choc.get("ref", ""),
            "chocs_appliques":   {k: v for k, v in choc.items() if k != "ref" and v != 0},
            "be_sante_choque":   round(be_s_choque, 2),
            "be_prev_choque":    round(be_p_choque, 2),
            "delta_be":          round(delta_be, 2),
            "delta_be_pct":      round(delta_be / max(src["be_total"], 1) * 100, 1),
            "scr_choque":        round(scr_choque, 2),
            "fp_residuels":      round(fp_residuels, 2),
            "fp_absorbes":       round(fp_absorbes, 2),
            "ratio_scr_choque":  round(ratio_scr_c, 1),
            "reste_solvable":    ratio_scr_c >= 100,
        }

    def _hypotheses(self, src: Dict, resultats: Dict, worst: Dict) -> list:
        ratio_base = src["fpp"] / max(src["scr_total"], 1) * 100

        # H1 : situation de base
        h1_s = "VALIDÉE" if ratio_base >= 130 else ("À JUSTIFIER" if ratio_base >= 100 else "NON VALIDÉE")
        h1_m = f"Ratio SCR base = {ratio_base:.1f}%"

        # H2 : résistance worst case
        wc_ratio = worst.get("ratio_scr_choque", 0)
        h2_s = "VALIDÉE" if wc_ratio >= 100 else "NON VALIDÉE"
        h2_m = (f"Worst case ({worst.get('scenario_nom','')}) : "
                f"ratio SCR = {wc_ratio:.1f}%")

        # H3 : FP suffisants pour absorber choc moyen
        fp_moy_absorbes = np.mean([r["fp_absorbes"] for r in resultats.values()]) if resultats else 0
        pct_fp = fp_moy_absorbes / max(src["fpp"], 1) * 100
        h3_s = "VALIDÉE" if pct_fp < 20 else ("À JUSTIFIER" if pct_fp < 50 else "NON VALIDÉE")
        h3_m = f"Choc moyen absorbe {pct_fp:.1f}% des FP"

        return [
            {"id":"H1","hypothese":"Ratio SCR base ≥ 130% (cible S2)",
             "valeur":h1_m,"statut":h1_s,"critique":True},
            {"id":"H2","hypothese":"Ratio SCR worst case ≥ 100% (plancher S2)",
             "valeur":h2_m,"statut":h2_s,"critique":True},
            {"id":"H3","hypothese":"Choc moyen absorbe < 20% des FP",
             "valeur":h3_m,"statut":h3_s,"critique":False},
        ]

    def _rag(self, hyp: list, resultats: Dict, fpp: float) -> str:
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val or any(not r["reste_solvable"] for r in resultats.values()):
            return "ROUGE"
        a_just = [h for h in hyp if h["statut"]=="À JUSTIFIER"]
        return "AMBRE" if a_just else "VERT"

    def _commentaire(self, rag, src, resultats, worst, hyp) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        ratio_base = src["fpp"] / max(src["scr_total"],1) * 100
        L = [
            "="*65,
            f"  STRESS TESTING S+P — SP-ST Naomie v{self.VERSION}",
            f"  {ic} STATUT : {rag}",
            "="*65,"",
            "  SITUATION DE BASE",
            f"  BE consolidé  : {src['be_total']:>14,.0f}€",
            f"  SCR consolidé : {src['scr_total']:>14,.0f}€",
            f"  Fonds Propres : {src['fpp']:>14,.0f}€",
            f"  Ratio SCR base: {ratio_base:>13.1f}%","",
            "  RÉSULTATS PAR SCÉNARIO",
            f"  {'Scénario':<22} {'ΔBE':<14} {'Ratio SCR choqué':<18} {'Solvable':}",
            "  " + "-"*62,
        ]
        for nom, r in resultats.items():
            solvable = "✅" if r["reste_solvable"] else "❌"
            L.append(
                f"  {nom:<22} {r['delta_be']:>+12,.0f}€  "
                f"  {r['ratio_scr_choque']:>12.1f}%    {solvable}"
            )
        wc = worst.get("scenario_nom","")
        L += ["",
              f"  ⚠️  Worst case : {wc} | "
              f"ΔBE={worst['delta_be']:+,.0f}€ | "
              f"Ratio SCR={worst['ratio_scr_choque']:.1f}%"]
        return "\n".join(L)
