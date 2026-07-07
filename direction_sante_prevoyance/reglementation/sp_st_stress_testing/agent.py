"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT SP-ST : STRESS TESTING SANTÉ-PRÉVOYANCE                  ║
║  Naomie · Direction Santé-Prévoyance                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Stress tests réglementaires et de gestion — scénarios adverses.     ║
║                                                                              ║
║  SCÉNARIOS :                                                                  ║
║    1. Pandémie / Épidémie (COVID-like)                                       ║
║       → +50% sinistres santé + +30% arrêts ITT sur 6 mois                  ║
║    2. Choc morbidité EIOPA (S2 Art.145)                                     ║
║       → +35% taux incidence ITT/IP pendant 1 an                             ║
║    3. Choc cessation (arrêt de cotisations)                                  ║
║       → -20% taux de cessation (maintien arrêts)                            ║
║    4. Choc combiné (pandémie + morbidité)                                    ║
║       → scénario adverse maximum pour ORSA                                   ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_s3  → S3 Binta (SCR santé, BE, ratio SCR)                        ║
║    result_p4  → P4 Valentin (SCR invalidité, BE prév, sorties_naomie)      ║
║                                                                              ║
║  RÉFÉRENCES RÉGLEMENTAIRES :                                                 ║
║    RD 2015/35 Art.145 (choc morbidité)                                      ║
║    RD 2015/35 Art.159 (choc CAT santé — pandémie)                          ║
║    EIOPA ORSA Guidelines 2016 (stress tests internes)                       ║
║    ACPR — Exercice stress tests 2022/2023                                    ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict

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

NAVY = "#0F2E52"; NAVY_L = "#1B3A5C"; NAVY_LL = "#243F6A"; OR = "#C9A84C"
BLANC = "#F0F4F8"; GRIS = "#8A9AB0"; VERT = "#2ECC71"; ROUGE = "#E74C3C"
AMBRE = "#F39C12"; BLEU = "#3498DB"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60), height=340,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
)

# ── Paramètres des scénarios de stress ────────────────────────────────────────
# Source : RD 2015/35 Art.145, Art.159 | EIOPA ORSA Guidelines 2016
SCENARIOS = {
    "pandemie": {
        "label":           "Pandémie / Épidémie (COVID-like)",
        "source":          "RD 2015/35 Art.159 + ACPR stress tests 2022",
        "choc_sante_pct":  0.50,   # +50% sinistres santé
        "choc_itt_pct":    0.30,   # +30% arrêts ITT
        "choc_dc_pct":     0.05,   # +5% mortalité
        "duree_mois":      6,      # durée du choc
    },
    "morbidite": {
        "label":           "Choc Morbidité EIOPA",
        "source":          "RD 2015/35 Art.145 §2(a) — +35% incidence",
        "choc_sante_pct":  0.00,
        "choc_itt_pct":    0.35,
        "choc_dc_pct":     0.00,
        "duree_mois":      12,
    },
    "cessation": {
        "label":           "Choc Cessation (maintien arrêts)",
        "source":          "RD 2015/35 Art.145 §2(b) — -20% taux cessation",
        "choc_sante_pct":  0.00,
        "choc_itt_pct":    0.00,
        "choc_dc_pct":     0.00,
        "choc_cessation":  0.20,   # -20% taux de guérison
        "duree_mois":      12,
    },
    "adverse": {
        "label":           "Scénario Adverse Combiné (ORSA)",
        "source":          "EIOPA ORSA Guidelines 2016 — scénario interne",
        "choc_sante_pct":  0.50,
        "choc_itt_pct":    0.35,
        "choc_dc_pct":     0.05,
        "choc_cessation":  0.20,
        "duree_mois":      12,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
class AgentSPStressTestingNaomie:
    """
    Agent SP-ST Naomie — Stress Testing Santé-Prévoyance.
    Direction Santé-Prévoyance.

    Calcule l'impact des scénarios de stress sur le bilan et la solvabilité.
    Produit les résultats ORSA et les recommandations de gestion.
    """

    NOM     = "Naomie"
    CODE    = "SP-ST"
    VERSION = "1.0"
    MANAGER = "Amira (Directrice SP)"

    def __init__(self, audit_path="audit", verbose=True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.st.naomie")
        self.verbose = verbose

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s3,
            result_p4,
            scenarios_actifs: list = None,
            fonds_propres:    float = 0.0,
            generer_graphiques: bool = True) -> Dict:
        """
        Parameters
        ----------
        result_s3 : dict — résultat S3 Binta
        result_p4 : dict — résultat P4 Valentin
        scenarios_actifs : list — sous-ensemble de ["pandemie","morbidite","cessation","adverse"]
                           None = tous les scénarios
        fonds_propres : float — FP de l'entité pour calcul ratios stressés
        """
        t0  = datetime.now()
        aid = f"ST_{t0.strftime('%Y%m%d_%H%M%S')}"

        if scenarios_actifs is None:
            scenarios_actifs = list(SCENARIOS.keys())

        try:
            src = self._extraire(result_s3, result_p4, fonds_propres)
            self.logger.info(
                f"[{aid}] Naomie ST | BE_S={src['be_sante']:,.0f}€ | "
                f"BE_P={src['be_prev']:,.0f}€ | FP={src['fpp']:,.0f}€ | "
                f"scénarios={scenarios_actifs}"
            )

            # ── Calculer chaque scénario ───────────────────────────────────────
            resultats = {}
            for scen in scenarios_actifs:
                if scen in SCENARIOS:
                    resultats[scen] = self._appliquer_scenario(src, scen)

            # ── Scénario le plus adverse ───────────────────────────────────────
            pire = self._pire_scenario(resultats)

            # ── Hypothèses + RAG ─────────────────────────────────────────────
            hyp = self._hypotheses(src, resultats, pire)
            rag = self._rag(hyp, resultats, src)

            # ── Commentaire ───────────────────────────────────────────────────
            com = self._commentaire(rag, src, resultats, pire, hyp)

            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(src, resultats)

            self._audit(aid, src, resultats, rag)
            if self.verbose:
                self._console(aid, rag, src, resultats, pire)

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── Baseline ────────────────────────────────────────────────
                "be_sante_baseline":   round(src["be_sante"], 2),
                "be_prev_baseline":    round(src["be_prev"], 2),
                "scr_sante_baseline":  round(src["scr_sante"], 2),
                "scr_prev_baseline":   round(src["scr_prev"], 2),
                "ratio_scr_baseline":  round(src["ratio_scr"], 1),

                # ── Résultats par scénario ────────────────────────────────────
                "scenarios": resultats,
                "pire_scenario": pire,

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
    def _extraire(self, result_s3, result_p4, fonds_propres):
        if not result_s3 or not result_s3.get("success"):
            raise ValueError("result_s3 requis")
        if not result_p4 or not result_p4.get("success"):
            raise ValueError("result_p4 requis")

        be_sante  = float(result_s3.get("be_sante", 0))
        scr_sante = float(result_s3.get("scr_sante", 0))
        fpp_s3    = float(result_s3.get("fonds_propres", 0))

        nav_p4    = result_p4.get("sorties_naomie", {})
        be_prev   = float(result_p4.get("be_prevoyance", 0))
        scr_prev  = float(result_p4.get("scr_invalidite", 0))
        fpp_p4    = float(result_p4.get("fonds_propres", 0))
        pa_sante  = float(result_s3.get("qrt_s13", {}).get("lignes", [{}])[-1]
                          .get("C0010", be_sante * 2) if result_s3.get("qrt_s13") else be_sante * 2)
        pa_prev   = float(nav_p4.get("primes_acquises", be_prev))
        nb_ass    = int(nav_p4.get("nb_assures", 0))
        taux_ip   = float(nav_p4.get("taux_ip", 0.005))
        taux_itt  = float(nav_p4.get("taux_itt", 0.04))

        if fonds_propres > 0:
            fpp = fonds_propres
        else:
            fpp = max(fpp_s3, fpp_p4, (be_sante + be_prev) * 1.5)

        # SCR consolidé baseline (ρ=0.25 EIOPA)
        rho = 0.25
        scr_tot = np.sqrt(scr_sante**2 + 2*rho*scr_sante*scr_prev + scr_prev**2)
        ratio_scr = fpp / max(scr_tot, 1) * 100

        return {
            "be_sante":  be_sante, "scr_sante": scr_sante,
            "be_prev":   be_prev,  "scr_prev":  scr_prev,
            "pa_sante":  pa_sante, "pa_prev":   pa_prev,
            "fpp":       fpp,      "scr_tot":   scr_tot,
            "ratio_scr": ratio_scr,
            "nb_assures":nb_ass,
            "taux_ip":   taux_ip,  "taux_itt":  taux_itt,
        }

    def _appliquer_scenario(self, src, nom_scen):
        """
        Calcule l'impact d'un scénario de stress sur le bilan.
        Impact = variation des provisions + SCR stressé.
        """
        scen = SCENARIOS[nom_scen]
        duree_frac = scen["duree_mois"] / 12.0

        # Impact sur BE santé
        choc_s   = scen.get("choc_sante_pct", 0)
        delta_be_sante = src["be_sante"] * choc_s * duree_frac

        # Impact sur BE prévoyance (ITT → charge + potentiel basculement IP)
        choc_itt = scen.get("choc_itt_pct", 0)
        choc_ces = scen.get("choc_cessation", 0)
        # ITT : augmentation des arrêts
        # Proxy : 30% du BE prévoyance est constitué de PSAP_ITT
        # (source : décomposition P3 — PSAP_ITT / BE_prév ≈ 20-35% selon portefeuille)
        # Le choc s'applique sur cette portion sensible aux nouveaux arrêts
        PCT_BE_ITT = 0.30   # proportion BE prév sensible aux chocs ITT
        delta_be_itt = src["be_prev"] * PCT_BE_ITT * choc_itt * duree_frac
        # Cessation : maintien des arrêts → allongement durées
        # Proxy : 15% du BE prévoyance est sensible aux taux de cessation
        # (correspond à la part de PSAP en phase de consolidation)
        PCT_BE_CES = 0.15   # proportion BE prév sensible au taux de cessation
        delta_be_ces = src["be_prev"] * PCT_BE_CES * choc_ces * duree_frac
        # Décès supplémentaires
        choc_dc = scen.get("choc_dc_pct", 0)
        delta_be_dc = src["pa_prev"] * choc_dc * duree_frac

        delta_be_prev  = delta_be_itt + delta_be_ces + delta_be_dc

        # BE stressé
        be_sante_str = src["be_sante"] + delta_be_sante
        be_prev_str  = src["be_prev"]  + delta_be_prev
        be_total_str = be_sante_str + be_prev_str

        # SCR stressé (proportionnel aux BE stressés + chocs directs)
        # Santé : σ × PA × 3 mais avec BE plus élevé
        scr_sante_str = src["scr_sante"] * (1 + choc_s * duree_frac)
        scr_prev_str  = src["scr_prev"]  * (1 + choc_itt)

        rho = 0.25
        scr_str = np.sqrt(
            scr_sante_str**2 + 2*rho*scr_sante_str*scr_prev_str + scr_prev_str**2
        )

        # FP érodés par la perte supplémentaire (sinistres en excès)
        perte_totale = delta_be_sante + delta_be_prev
        fpp_str = max(0, src["fpp"] - perte_totale)
        ratio_str = fpp_str / max(scr_str, 1) * 100

        # Variation de ratio
        delta_ratio = ratio_str - src["ratio_scr"]

        return {
            "label":          scen["label"],
            "source":         scen["source"],
            "duree_mois":     scen["duree_mois"],

            # Impacts
            "delta_be_sante": round(delta_be_sante, 2),
            "delta_be_prev":  round(delta_be_prev, 2),
            "perte_totale":   round(perte_totale, 2),

            # Résultats stressés
            "be_total_stresse":   round(be_total_str, 2),
            "scr_stresse":        round(scr_str, 2),
            "fpp_stresse":        round(fpp_str, 2),
            "ratio_scr_stresse":  round(ratio_str, 1),
            "delta_ratio_scr":    round(delta_ratio, 1),

            # Statut
            "ratio_ok":  ratio_str >= 100,
            "note":      (f"✅ Ratio maintenu à {ratio_str:.1f}% après stress"
                          if ratio_str >= 100 else
                          f"❌ Insuffisance : ratio {ratio_str:.1f}% < 100%"),
        }

    def _pire_scenario(self, resultats):
        if not resultats:
            return None
        return min(resultats.items(),
                   key=lambda x: x[1].get("ratio_scr_stresse", 999))[0]

    def _hypotheses(self, src, resultats, pire):
        # H1 — Ratio baseline > 100%
        h1_s = "VALIDÉE" if src["ratio_scr"] >= 100 else "NON VALIDÉE"
        h1_m = f"Ratio SCR baseline = {src['ratio_scr']:.1f}%"

        # H2 — Ratio stressé pandémie > 100%
        if "pandemie" in resultats:
            r_pan = resultats["pandemie"]["ratio_scr_stresse"]
            h2_s = "VALIDÉE" if r_pan >= 100 else "NON VALIDÉE"
            h2_m = f"Ratio SCR post-pandémie = {r_pan:.1f}%"
        else:
            h2_s = "À JUSTIFIER"; h2_m = "Scénario pandémie non calculé"

        # H3 — Pire scénario documenté + mesures correctives si < 100%
        if pire and resultats.get(pire, {}).get("ratio_ok", True):
            h3_s = "VALIDÉE"
            h3_m = (f"Pire scénario : {pire} → "
                    f"ratio={resultats[pire]['ratio_scr_stresse']:.1f}% ≥ 100%")
        else:
            h3_s = "NON VALIDÉE"
            pire_ratio = resultats.get(pire, {}).get("ratio_scr_stresse", 0) if pire else 0
            h3_m = f"Pire scénario ({pire}) → ratio={pire_ratio:.1f}% < 100% — mesures correctives requises"

        return [
            {"id":"H1","hypothese":"Ratio SCR baseline ≥ 100%",
             "valeur":h1_m,"statut":h1_s,"critique":True},
            {"id":"H2","hypothese":"Ratio SCR post-pandémie ≥ 100% (Art.159 RD 2015/35)",
             "valeur":h2_m,"statut":h2_s,"critique":True},
            {"id":"H3","hypothese":"Pire scénario ORSA ≥ 100% (EIOPA Guidelines 2016)",
             "valeur":h3_m,"statut":h3_s,"critique":True},
        ]

    def _rag(self, hyp, resultats, src):
        if src["ratio_scr"] < 100:
            return "ROUGE"
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val:
            return "ROUGE"
        # Tout ratio stressé < 100% = AMBRE minimum
        if any(not r.get("ratio_ok", True) for r in resultats.values()):
            return "AMBRE"
        return "VERT"

    def _commentaire(self, rag, src, resultats, pire, hyp):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        L = [
            "="*70,
            f"  STRESS TESTING SANTÉ-PRÉVOYANCE — NAOMIE v{self.VERSION}",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
            "📊 SITUATION BASELINE", "─"*50,
            f"  BE Santé       : {src['be_sante']:>12,.0f}€",
            f"  BE Prévoyance  : {src['be_prev']:>12,.0f}€",
            f"  SCR Consolidé  : {src['scr_tot']:>12,.0f}€",
            f"  Fonds Propres  : {src['fpp']:>12,.0f}€",
            f"  Ratio SCR      : {src['ratio_scr']:>11.1f}%",
            "",
            "🔴 RÉSULTATS PAR SCÉNARIO", "─"*50,
        ]
        for nom, r in resultats.items():
            ic_r = "✅" if r["ratio_ok"] else "❌"
            L += [
                f"  {ic_r} {r['label']}",
                f"     Source   : {r['source']}",
                f"     Perte    : {r['perte_totale']:,.0f}€ | "
                f"SCR stressé : {r['scr_stresse']:,.0f}€",
                f"     Ratio stressé : {r['ratio_scr_stresse']:.1f}% "
                f"(Δ={r['delta_ratio_scr']:+.1f}pp)",
                f"     → {r['note']}",
                "",
            ]
        if pire:
            L += [
                f"⚠️  PIRE SCÉNARIO : {pire.upper()} "
                f"— ratio={resultats[pire]['ratio_scr_stresse']:.1f}%",
                "",
            ]
        L += ["📋 HYPOTHÈSES", "─"*50]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"]=="À JUSTIFIER" else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]
        return "\n".join(L)

    def _graphiques(self, src, resultats):
        gph = {}
        noms   = ["Baseline"] + [r["label"] for r in resultats.values()]
        ratios = [src["ratio_scr"]] + [r["ratio_scr_stresse"] for r in resultats.values()]
        couleurs = []
        for ratio in ratios:
            if ratio >= 130:
                couleurs.append(VERT)
            elif ratio >= 100:
                couleurs.append(AMBRE)
            else:
                couleurs.append(ROUGE)

        fig = go.Figure(go.Bar(
            x=noms, y=ratios,
            marker_color=couleurs,
            text=[f"{r:.0f}%" for r in ratios],
            textposition="outside",
        ))
        fig.add_shape(type="line", x0=-0.5, x1=len(noms)-0.5,
                      y0=100, y1=100,
                      line=dict(color=ROUGE, width=2, dash="dash"))
        fig.add_shape(type="line", x0=-0.5, x1=len(noms)-0.5,
                      y0=130, y1=130,
                      line=dict(color=VERT, width=1, dash="dot"))
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text="Ratio SCR — Baseline vs Scénarios de Stress",
                       font=dict(color=OR, size=13)),
            yaxis_title="Ratio SCR (%)",
        )
        gph["ratios_stress"] = fig

        # Pertes par scénario
        fig2 = go.Figure(go.Bar(
            x=[r["label"] for r in resultats.values()],
            y=[r["perte_totale"] for r in resultats.values()],
            marker_color=ROUGE,
            text=[f"{r['perte_totale']/1000:.0f}k€" for r in resultats.values()],
            textposition="outside",
        ))
        fig2.update_layout(
            **LAYOUT_BASE,
            title=dict(text="Pertes par Scénario de Stress",
                       font=dict(color=OR, size=13)),
            yaxis_title="Perte (€)",
        )
        gph["pertes_scenarios"] = fig2
        return gph

    def _audit(self, aid, src, resultats, rag):
        try:
            log_path = self.audit_path / "sp_st_audit.jsonl"
            entry = {
                "audit_id": aid,
                "timestamp": datetime.now().isoformat(),
                "statut_rag": rag,
                "ratio_scr_baseline": round(src["ratio_scr"], 1),
                "pire_ratio_stresse": min(
                    (r["ratio_scr_stresse"] for r in resultats.values()), default=0
                ),
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _console(self, aid, rag, src, resultats, pire):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        pire_ratio = resultats.get(pire, {}).get("ratio_scr_stresse", 0) if pire else 0
        self.logger.info(
            f"[{aid}] {ic} {rag} | Baseline={src['ratio_scr']:.1f}% | "
            f"Pire={pire}:{pire_ratio:.1f}%"
        )

    def _erreur(self, msg, aid=""):
        return {
            "success":False,"agent":self.NOM,"version":self.VERSION,
            "audit_id":aid,"statut_rag":"ROUGE",
            "scenarios":{},"pire_scenario":None,
            "hypotheses":[],"commentaire":"","graphiques":{},
            "duree_sec":0,"erreur":msg,
        }
