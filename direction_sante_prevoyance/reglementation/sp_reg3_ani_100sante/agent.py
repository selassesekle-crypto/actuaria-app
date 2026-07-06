"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — AGENT SP-REG3 : CONFORMITÉ ANI 2013 + 100% SANTÉ               ║
║  Direction Santé-Prévoyance · Équipe Réglementation & Finance              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE : Vérification conformité réglementaire pour la santé collective.     ║
║                                                                              ║
║  PÉRIMÈTRE :                                                                 ║
║    · ANI 2013 (Accord National Interprofessionnel 11/01/2013)               ║
║      Art. L911-7 CSS — panier minimum complémentaire collective             ║
║    · Réforme 100% Santé (Reste à Charge Zéro — RAC 0)                      ║
║      Décrets 2019-21 — optique, dentaire, audiologie                        ║
║    · Contrat responsable (Art. L871-1 CSS + Décret 2014-1374)              ║
║      Franchises plancher/plafond, exclusions réglementées                   ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_s1 → S1 Léonie (postes tarifés + ANI déjà calculé)               ║
║    contrat : str — "individuel" | "collectif" | "collectif_cadres"          ║
║    inclure_100pct_sante : bool — vérifier RAC 0 optique/dentaire/audio      ║
║                                                                              ║
║  RÉFÉRENCES RÉGLEMENTAIRES :                                                 ║
║    ANI 11/01/2013 | Art. L911-7 CSS | Loi 14/06/2013                       ║
║    Décrets 2019-21 (100% Santé) | Art. L871-1 CSS + D.2014-1374           ║
║    UNOCAM — guide contrat responsable 2023                                  ║
║                                                                              ║
║  VERSION : 1.0 — Juillet 2026                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict

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
BLANC = "#F0F4F8"; VERT = "#2ECC71"; ROUGE = "#E74C3C"; AMBRE = "#F39C12"

LAYOUT_BASE = dict(
    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16, r=16, t=60, b=60), height=300,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
)

# ── Seuils réglementaires ─────────────────────────────────────────────────────
# ANI 2013 — panier minimum annuel par poste (€/assuré)
# Source : ANI 11/01/2013 + Art. L911-7 CSS
ANI_SEUILS = {
    "medecine":        30.0,    # ≥ 100% BR consultations généraliste
    "hospitalisation": 100.0,   # ≥ 100% BR séjour + forfait journalier
    "dentaire":        75.0,    # ≥ 125% BR soins dentaires
    "optique":         100.0,   # verres + montures, minimum conventionnel
    "pharmacie":       0.0,     # pas de seuil ANI (pharmaco couvert SS)
}

# 100% Santé — paniers RAC 0 (Décrets 2019-21)
# Optique : verres classe A + monture ≤ 30€ → prise en charge totale
# Dentaire : couronnes, inlay-cores classe 1 → RAC 0
# Audio : appareils auditifs classe 1 → RAC 0
SEUILS_100_SANTE = {
    "optique_verres_A":   200.0,   # remboursement plancher verres classe A
    "optique_monture":     30.0,   # monture RAC 0 (plafond SS)
    "dentaire_couronne":  200.0,   # couronne classe 1 RAC 0
    "audio_classe1":      950.0,   # appareils classe 1 par oreille
}

# Contrat responsable — Art. L871-1 CSS + Décret 2014-1374
CONTRAT_RESP_PLANCHERS = {
    "medecine":        25.0,    # prise en charge min ticket modérateur
    "hospitalisation": 100.0,   # forfait journalier + chambre particulière min
}
CONTRAT_RESP_PLAFONDS = {
    "honoraires_depassement": 200.0,  # % SS — plafond dépassements honoraires
}


# ══════════════════════════════════════════════════════════════════════════════
class AgentSPReg3ANI100Sante:
    """
    Agent SP-REG3 — Conformité ANI 2013 + 100% Santé.
    Direction Santé-Prévoyance · Équipe Réglementation & Finance.
    """

    NOM     = "SP-Reg3-ANI-100Santé"
    CODE    = "SP-REG3"
    VERSION = "1.0"
    MANAGER = "Équipe Réglementation & Finance SP"

    def __init__(self, audit_path="audit", verbose=True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.sp.reg3.ani")
        self.verbose = verbose

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s1,
            contrat:              str  = "collectif",
            inclure_100pct_sante: bool = True,
            inclure_contrat_resp: bool = True,
            generer_graphiques:   bool = True) -> Dict:
        """
        Parameters
        ----------
        result_s1 : dict — résultat S1 Léonie
        contrat : "individuel" | "collectif" | "collectif_cadres"
        inclure_100pct_sante : bool — vérifier RAC 0 optique/dentaire/audio
        inclure_contrat_resp : bool — vérifier contrat responsable
        """
        t0  = datetime.now()
        aid = f"REG3_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            src = self._extraire(result_s1)
            self.logger.info(
                f"[{aid}] SP-Reg3 ANI+100S | contrat={contrat} | "
                f"garantie={src['garantie_niveau']} | postes={len(src['postes'])}"
            )

            # ── 1. CONFORMITÉ ANI 2013 ────────────────────────────────────────
            ani = self._verifier_ani(src, contrat)

            # ── 2. CONFORMITÉ 100% SANTÉ (RAC 0) ─────────────────────────────
            sante_100 = None
            if inclure_100pct_sante:
                sante_100 = self._verifier_100_sante(src)

            # ── 3. CONTRAT RESPONSABLE ────────────────────────────────────────
            contrat_resp = None
            if inclure_contrat_resp:
                contrat_resp = self._verifier_contrat_responsable(src)

            # ── 4. SYNTHÈSE + RAG ────────────────────────────────────────────
            hyp = self._hypotheses(ani, sante_100, contrat_resp, contrat)
            rag = self._rag(hyp, ani, contrat)

            com = self._commentaire(
                rag, contrat, src, ani, sante_100, contrat_resp, hyp
            )

            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(ani, sante_100)

            duree = (datetime.now() - t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── Conformités ───────────────────────────────────────────────
                "ani_conforme":        ani["conforme_global"],
                "ani_detail":          ani["detail"],
                "ani_note":            ani["note_globale"],
                "sante_100_conforme":  sante_100["conforme"] if sante_100 else None,
                "sante_100_detail":    sante_100 if sante_100 else {},
                "contrat_resp":        contrat_resp if contrat_resp else {},

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
    def _extraire(self, result_s1):
        if not result_s1 or not result_s1.get("success"):
            raise ValueError("result_s1 requis et success=True")
        # S1 retourne r["postes"] — dict de dicts avec charge_mutuelle, frequence_an...
        # Ne pas confondre avec sorties_s2["sinistralite_par_poste"] qui est un dict de floats
        postes = result_s1.get("postes", {})
        if not postes or not isinstance(next(iter(postes.values()), None), dict):
            postes = {}  # postes vides → vérification ANI impossible
            self.logger.warning(
                "Postes S1 absents ou format incorrect — "
                "ANI/100%S vérifiés sur seuils mais charge_mutuelle = 0"
            )
        return {
            "postes":         postes,
            "garantie_niveau":result_s1.get("garantie_niveau", "confort"),
            "contrat":        result_s1.get("contrat", "individuel"),
            "prime_pure":     float(result_s1.get("prime_pure", 0)),
            "nb_assures":     int(result_s1.get("nb_assures", 0)),
        }

    def _verifier_ani(self, src, contrat):
        """
        Vérifie la conformité au panier ANI 2013.
        Source : ANI 11/01/2013 | Art. L911-7 CSS.
        Applicable uniquement aux contrats collectifs obligatoires.
        """
        if contrat == "individuel":
            detail = {p: {"ok":True, "note":"N/A (individuel — ANI non applicable)"}
                      for p in ANI_SEUILS}
            return {
                "conforme_global": True,
                "detail":          detail,
                "note_globale":    "N/A — ANI 2013 s'applique uniquement au collectif (Art. L911-7 CSS)",
            }

        postes = src["postes"]
        detail = {}
        conforme = True

        for poste, seuil in ANI_SEUILS.items():
            if seuil == 0:
                detail[poste] = {"ok":True, "seuil":seuil, "note":"Pas de seuil ANI"}
                continue
            # Charge mutuelle par poste (annuelle par assuré)
            p_info  = postes.get(poste, {})
            charge  = float(p_info.get("charge_mutuelle", 0))
            ok      = charge >= seuil
            if not ok:
                conforme = False
            detail[poste] = {
                "ok":     ok,
                "seuil":  seuil,
                "charge": round(charge, 2),
                "ecart":  round(charge - seuil, 2),
                "note":   (f"✅ {charge:.0f}€ ≥ {seuil:.0f}€ seuil ANI"
                           if ok else
                           f"❌ {charge:.0f}€ < {seuil:.0f}€ — déficit {seuil-charge:.0f}€"),
            }

        return {
            "conforme_global": conforme,
            "detail":          detail,
            "note_globale":    (
                "✅ Panier ANI 2013 respecté sur tous les postes"
                if conforme else
                "❌ Panier ANI 2013 non atteint — réviser les niveaux de garantie"
            ),
        }

    def _verifier_100_sante(self, src):
        """
        Vérifie la conformité 100% Santé (RAC 0).
        Décrets 2019-21 — optique, dentaire, audiologie.
        """
        postes  = src["postes"]
        detail  = {}
        conforme = True

        # Optique — vérifier prise en charge classe A
        ch_opt = float(postes.get("optique", {}).get("charge_mutuelle", 0))
        seuil_opt = SEUILS_100_SANTE["optique_verres_A"] + SEUILS_100_SANTE["optique_monture"]
        ok_opt = ch_opt >= seuil_opt
        if not ok_opt:
            conforme = False
        detail["optique_rac0"] = {
            "ok":       ok_opt,
            "seuil":    seuil_opt,
            "charge":   round(ch_opt, 2),
            "note":     (f"✅ Optique RAC 0 — prise en charge {ch_opt:.0f}€ ≥ {seuil_opt:.0f}€"
                         if ok_opt else
                         f"❌ Optique RAC 0 insuffisant — {ch_opt:.0f}€ < {seuil_opt:.0f}€"),
        }

        # Dentaire — couronnes classe 1
        ch_dent = float(postes.get("dentaire", {}).get("charge_mutuelle", 0))
        seuil_dent = SEUILS_100_SANTE["dentaire_couronne"]
        ok_dent = ch_dent >= seuil_dent
        if not ok_dent:
            conforme = False
        detail["dentaire_rac0"] = {
            "ok":     ok_dent,
            "seuil":  seuil_dent,
            "charge": round(ch_dent, 2),
            "note":   (f"✅ Dentaire RAC 0 — {ch_dent:.0f}€ ≥ {seuil_dent:.0f}€"
                       if ok_dent else
                       f"❌ Dentaire RAC 0 insuffisant — {ch_dent:.0f}€ < {seuil_dent:.0f}€"),
        }

        detail["audio"] = {
            "ok":   None,
            "note": "Audiologie : non tarifée par S1 — vérification manuelle requise",
        }

        return {
            "conforme":       conforme,
            "detail":         detail,
            "note_globale":   (
                "✅ Contrat conforme 100% Santé (RAC 0) — Décrets 2019-21"
                if conforme else
                "⚠️ 100% Santé partiellement respecté — compléter optique/dentaire"
            ),
        }

    def _verifier_contrat_responsable(self, src):
        """
        Vérifie les critères du contrat responsable.
        Art. L871-1 CSS + Décret 2014-1374 + UNOCAM 2023.
        """
        postes = src["postes"]
        detail = {}

        # Médecine — prise en charge min ticket modérateur
        ch_med = float(postes.get("medecine", {}).get("charge_mutuelle", 0))
        ok_med = ch_med >= CONTRAT_RESP_PLANCHERS["medecine"]
        detail["plancher_medecine"] = {
            "ok": ok_med,
            "note": (f"✅ Ticket modérateur couvert : {ch_med:.0f}€ ≥ {CONTRAT_RESP_PLANCHERS['medecine']:.0f}€"
                     if ok_med else
                     f"❌ Ticket modérateur insuffisant : {ch_med:.0f}€ < {CONTRAT_RESP_PLANCHERS['medecine']:.0f}€"),
        }

        # Hospit — forfait journalier
        ch_hos = float(postes.get("hospitalisation", {}).get("charge_mutuelle", 0))
        ok_hos = ch_hos >= CONTRAT_RESP_PLANCHERS["hospitalisation"]
        detail["plancher_hospitalisation"] = {
            "ok": ok_hos,
            "note": (f"✅ Forfait journalier couvert : {ch_hos:.0f}€ ≥ {CONTRAT_RESP_PLANCHERS['hospitalisation']:.0f}€"
                     if ok_hos else
                     f"❌ Forfait journalier insuffisant"),
        }

        conforme = ok_med and ok_hos
        return {
            "conforme": conforme,
            "detail":   detail,
            "note":     ("✅ Contrat responsable — Art. L871-1 CSS"
                         if conforme else
                         "❌ Non conforme contrat responsable — revoir planchers"),
        }

    def _hypotheses(self, ani, sante_100, contrat_resp, contrat):
        h1_s = "VALIDÉE" if ani["conforme_global"] else "NON VALIDÉE"
        h1_m = ani["note_globale"]

        if sante_100:
            h2_s = "VALIDÉE" if sante_100["conforme"] else "À JUSTIFIER"
            h2_m = sante_100["note_globale"]
        else:
            h2_s = "À JUSTIFIER"; h2_m = "100% Santé non vérifié"

        if contrat_resp:
            h3_s = "VALIDÉE" if contrat_resp["conforme"] else "NON VALIDÉE"
            h3_m = contrat_resp["note"]
        else:
            h3_s = "À JUSTIFIER"; h3_m = "Contrat responsable non vérifié"

        return [
            {"id":"H1","hypothese":"Panier ANI 2013 — Art. L911-7 CSS",
             "valeur":h1_m,"statut":h1_s,"critique":(contrat!="individuel")},
            {"id":"H2","hypothese":"100% Santé RAC 0 — Décrets 2019-21",
             "valeur":h2_m,"statut":h2_s,"critique":False},
            {"id":"H3","hypothese":"Contrat responsable — Art. L871-1 CSS",
             "valeur":h3_m,"statut":h3_s,"critique":True},
        ]

    def _rag(self, hyp, ani, contrat):
        if contrat != "individuel" and not ani["conforme_global"]:
            return "ROUGE"
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val:
            return "ROUGE"
        a_just = [h for h in hyp if h["statut"]=="À JUSTIFIER"]
        return "AMBRE" if a_just else "VERT"

    def _commentaire(self, rag, contrat, src, ani, sante_100, cr, hyp):
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        L = [
            "="*70,
            f"  RAPPORT RÉGLEMENTAIRE ANI 2013 + 100% SANTÉ — SP-REG3 v{self.VERSION}",
            f"  {ic} STATUT : {rag} | Contrat : {contrat.upper()} | Garantie : {src['garantie_niveau']}",
            "="*70, "",
            "📋 ANI 2013 — ART. L911-7 CSS", "─"*50,
        ]
        for poste, d in ani["detail"].items():
            L.append(f"  {poste:20s} : {d.get('note','N/A')}")
        L.append(f"  → {ani['note_globale']}")

        if sante_100:
            L += ["", "💯 100% SANTÉ — DÉCRETS 2019-21 (RAC 0)", "─"*50]
            for k, d in sante_100["detail"].items():
                L.append(f"  {k:25s} : {d.get('note','N/A')}")
            L.append(f"  → {sante_100['note_globale']}")

        if cr:
            L += ["", "✅ CONTRAT RESPONSABLE — ART. L871-1 CSS", "─"*50]
            for k, d in cr["detail"].items():
                L.append(f"  {k:30s} : {d.get('note','N/A')}")
            L.append(f"  → {cr['note']}")

        L += ["", "📋 HYPOTHÈSES", "─"*50]
        for h in hyp:
            ic_h = "✅" if h["statut"]=="VALIDÉE" else ("⚠️" if h["statut"]=="À JUSTIFIER" else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]
        return "\n".join(L)

    def _graphiques(self, ani, sante_100):
        gph = {}
        postes = list(ANI_SEUILS.keys())
        seuils = [ANI_SEUILS[p] for p in postes]
        charges = [ani["detail"].get(p, {}).get("charge", 0) for p in postes]
        couleurs = [("#2ECC71" if ani["detail"].get(p,{}).get("ok", True) else "#E74C3C")
                    for p in postes]

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Seuil ANI", x=postes, y=seuils,
                             marker_color="#F39C12", opacity=0.5))
        fig.add_trace(go.Bar(name="Charge mutuelle", x=postes, y=charges,
                             marker_color=couleurs))
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text="Conformité Panier ANI 2013", font=dict(color="#C9A84C", size=13)),
            barmode="group",
        )
        gph["ani_conformite"] = fig
        return gph

    def _erreur(self, msg, aid=""):
        return {
            "success":False,"agent":self.NOM,"version":self.VERSION,
            "audit_id":aid,"statut_rag":"ROUGE",
            "ani_conforme":False,"hypotheses":[],"commentaire":"",
            "graphiques":{},"duree_sec":0,"erreur":msg,
        }
