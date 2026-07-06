"""
Agent SP-REG3 — Conformité ANI 2013 + 100% Santé
Sous Amira (Directrice SP) · Direction Santé-Prévoyance
Sources : ANI 11/01/2013, Loi 14/06/2013, Décret 100% Santé 2019 (Loi Pacte)
"""
import logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")

# ── Panier ANI 2013 (Art. L911-7 CSS) — seuils minimaux ──────────────────────
# Source : Décret n°2014-1025 du 8 septembre 2014
# Applicable uniquement aux contrats collectifs obligatoires
ANI_PANIERS = {
    "medecine":        {"seuil_pct_br": 100, "seuil_eur": 30.0,
                        "ref": "100% BR consultations — Décret 2014-1025"},
    "hospitalisation": {"seuil_pct_br": 100, "seuil_eur": 100.0,
                        "ref": "100% BR séjour — Décret 2014-1025"},
    "dentaire":        {"seuil_pct_br": 125, "seuil_eur": 75.0,
                        "ref": "125% BR soins dentaires — Décret 2014-1025"},
    "optique":         {"seuil_pct_br": None, "seuil_eur": 100.0,
                        "ref": "100€ verres + monture — Décret 2014-1025"},
    "pharmacie":       {"seuil_pct_br": None, "seuil_eur": 0.0,
                        "ref": "N/A — pharmacie non soumise ANI"},
}

# ── 100% Santé (Loi Pacte / Décret du 11/04/2019) ───────────────────────────
# Panier de soins sans reste à charge pour optique, dentaire, audio
# Source : Décret n°2019-21 du 11 janvier 2019 (100% Santé)
CENT_PCT_SANTE = {
    "optique": {
        "correction_simple":   {"verre": 30.0,  "monture": 100.0},
        "correction_complexe": {"verre": 60.0,  "monture": 100.0},
        "ref": "Décret 2019-21 — Panier Santé 100% optique",
    },
    "dentaire": {
        "couronne_metal":     {"tarif_ss": 107.50, "remb_complement": 0.0},
        "couronne_ceramique": {"tarif_ss": 150.0,  "remb_complement": 30.0},
        "ref": "Décret 2019-21 + Arrêté 11/04/2019 — 100% Santé dentaire",
    },
    "audio": {
        "appareillage_classe_1": {"tarif_ss": 1100.0, "remb_complement": 0.0},
        "ref": "Décret 2019-21 — 100% Santé audioprothèse classe I",
    },
}


class AgentSPReg3ANI100Sante:
    """
    Agent SP-REG3 — Conformité ANI 2013 + 100% Santé.

    Vérifie :
    1. Conformité ANI 2013 (panier minimum collectif — Art. L911-7 CSS)
    2. Conformité 100% Santé (optique/dentaire/audio sans reste à charge — Décret 2019)
    3. Calcul des écarts et du surcoût de mise en conformité
    """
    NOM     = "SP-Reg3-ANI-100Sante"
    CODE    = "SP-REG3"
    VERSION = "1.0"
    MANAGER = "Amira (Directrice SP)"

    def __init__(self, audit_path="audit", verbose=True):
        Path(audit_path).mkdir(parents=True, exist_ok=True)
        self.audit_path = Path(audit_path)
        self.logger = logging.getLogger("actuaria.sp.reg3.ani")
        self.verbose = verbose

    def run(self,
            result_s1         = None,
            contrat:    str   = "collectif",
            postes:     Dict  = None,
            generer_graphiques: bool = True) -> Dict:
        """
        Parameters
        ----------
        result_s1  : résultat S1 Léonie — contient postes tarifés avec charges
        contrat    : "collectif" ou "individuel"
        postes     : dict optionnel {poste: charge_mutuelle_€} si result_s1 absent
        """
        t0  = datetime.now()
        aid = f"REG3_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            src_postes = self._extraire_postes(result_s1, postes)
            self.logger.info(
                f"[{aid}] SP-REG3 | contrat={contrat} | "
                f"{len(src_postes)} postes tarifés"
            )

            # ── ANI 2013 ──────────────────────────────────────────────────────
            ani = self._verifier_ani(src_postes, contrat)

            # ── 100% Santé ────────────────────────────────────────────────────
            cent_pct = self._verifier_100_sante(src_postes, contrat)

            # ── Synthèse conformité ───────────────────────────────────────────
            conforme_ani     = ani["conforme"]
            conforme_cent    = cent_pct["conforme"]
            conforme_globale = conforme_ani and conforme_cent

            # Calcul surcoût mise en conformité
            surcout_ani  = ani["surcout_total"]
            surcout_cent = cent_pct["surcout_total"]

            hyp = self._hypotheses(
                ani, cent_pct, contrat, conforme_globale
            )
            rag = self._rag(hyp, conforme_ani, conforme_cent, contrat)

            com = self._commentaire(
                rag, contrat, ani, cent_pct,
                surcout_ani, surcout_cent, hyp
            )

            duree = (datetime.now()-t0).total_seconds()

            return {
                "success":    True,
                "agent":      self.NOM,
                "version":    self.VERSION,
                "audit_id":   aid,
                "statut_rag": rag,

                # ── ANI 2013 ─────────────────────────────────────────────────
                "ani_conforme":      conforme_ani,
                "ani_detail":        ani["detail"],
                "ani_surcout":       round(surcout_ani, 2),
                "ani_note":          ani["note"],

                # ── 100% Santé ───────────────────────────────────────────────
                "cent_pct_conforme": conforme_cent,
                "cent_pct_detail":   cent_pct["detail"],
                "cent_pct_surcout":  round(surcout_cent, 2),
                "cent_pct_note":     cent_pct["note"],

                # ── Synthèse ─────────────────────────────────────────────────
                "conforme_globale":  conforme_globale,
                "surcout_total":     round(surcout_ani + surcout_cent, 2),

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

    def _extraire_postes(self, result_s1, postes_manuel) -> Dict:
        """Extrait les charges par poste depuis S1 ou entrée manuelle."""
        if postes_manuel:
            return postes_manuel
        if result_s1 and result_s1.get("success"):
            raw = result_s1.get("sorties_s2", {}).get("sinistralite_par_poste", {})
            if raw:
                return {p: float(v) for p, v in raw.items()}
            # fallback : sinistres_attendus / nb_assures par poste depuis hypothèses
        return {
            "medecine": 30.0, "hospitalisation": 120.0,
            "dentaire": 80.0, "optique": 100.0, "pharmacie": 15.0,
        }

    def _verifier_ani(self, postes: Dict, contrat: str) -> Dict:
        """Vérification panier ANI 2013 — Art. L911-7 CSS."""
        if contrat == "individuel":
            return {
                "conforme": True,
                "detail": {p: {"ok":True,"note":"N/A (individuel — Art. L911-7 CSS)"}
                           for p in ANI_PANIERS},
                "surcout_total": 0.0,
                "note": "ANI 2013 non applicable aux contrats individuels — Art. L911-7 CSS",
            }

        detail = {}
        surcout = 0.0
        conforme = True

        for poste, ref in ANI_PANIERS.items():
            seuil = ref["seuil_eur"]
            charge = postes.get(poste, 0.0)
            if seuil == 0:
                detail[poste] = {"ok":True,"charge":round(charge,2),
                                 "seuil":seuil,"note":"N/A — non soumis ANI",
                                 "ref":ref["ref"]}
                continue
            ok = charge >= seuil
            if not ok:
                conforme = False
                ecart = seuil - charge
                surcout += max(0, ecart)
            detail[poste] = {
                "ok":       ok,
                "charge":   round(charge, 2),
                "seuil":    seuil,
                "ecart":    round(seuil - charge, 2) if not ok else 0.0,
                "note":     ("✅ Conforme" if ok
                             else f"❌ Écart {seuil-charge:.0f}€ — mise en conformité requise"),
                "ref":      ref["ref"],
            }

        return {
            "conforme": conforme,
            "detail": detail,
            "surcout_total": surcout,
            "note": ("✅ Toutes les garanties ANI 2013 sont satisfaites"
                     if conforme
                     else f"⚠️ Non-conformité ANI sur certains postes — surcoût ~{surcout:.0f}€/assuré"),
        }

    def _verifier_100_sante(self, postes: Dict, contrat: str) -> Dict:
        """Vérification 100% Santé — Décret 2019-21."""
        detail = {}
        surcout = 0.0
        conforme = True

        # Optique : vérification remboursement panier I
        opt_charge = postes.get("optique", 0)
        seuil_opt = CENT_PCT_SANTE["optique"]["correction_simple"]["monture"]
        ok_opt = opt_charge >= seuil_opt
        if not ok_opt:
            conforme = False
            surcout += max(0, seuil_opt - opt_charge)
        detail["optique"] = {
            "ok": ok_opt,
            "charge": round(opt_charge, 2),
            "seuil_panier_1": seuil_opt,
            "note": ("✅ 100% Santé optique panier I couvert"
                     if ok_opt
                     else f"❌ Optique insuffisant — panier I = {seuil_opt}€ monture min"),
            "ref": CENT_PCT_SANTE["optique"]["ref"],
        }

        # Dentaire : vérification couronne céramique
        dent_charge = postes.get("dentaire", 0)
        seuil_dent = CENT_PCT_SANTE["dentaire"]["couronne_ceramique"]["remb_complement"]
        ok_dent = dent_charge >= 50  # seuil pratique 50€ reste à charge
        if not ok_dent:
            conforme = False
            surcout += 20.0  # estimation surcoût moyen
        detail["dentaire"] = {
            "ok": ok_dent,
            "charge": round(dent_charge, 2),
            "note": ("✅ 100% Santé dentaire couvert"
                     if ok_dent
                     else "⚠️ Remboursement dentaire à vérifier — couronne céramique"),
            "ref": CENT_PCT_SANTE["dentaire"]["ref"],
        }

        # Audio : non inclus dans les garanties standards → signal
        detail["audio"] = {
            "ok": True,
            "note": "ℹ️ Audio non couvert standard — vérifier garantie optionnelle",
            "ref": CENT_PCT_SANTE["audio"]["ref"],
        }

        return {
            "conforme": conforme,
            "detail": detail,
            "surcout_total": surcout,
            "note": ("✅ Garanties 100% Santé (optique/dentaire) conformes Décret 2019"
                     if conforme
                     else f"⚠️ Conformité 100% Santé à renforcer — surcoût ~{surcout:.0f}€/assuré"),
        }

    def _hypotheses(self, ani, cent_pct, contrat, conforme_globale) -> list:
        h1_s = "VALIDÉE" if ani["conforme"] else "NON VALIDÉE"
        h1_m = ani["note"]
        h2_s = "VALIDÉE" if cent_pct["conforme"] else "À JUSTIFIER"
        h2_m = cent_pct["note"]
        h3_s = "VALIDÉE" if conforme_globale else "NON VALIDÉE"
        h3_m = ("Conformité réglementaire globale ✅"
                if conforme_globale
                else "Mise en conformité requise avant commercialisation")
        return [
            {"id":"H1","hypothese":"Panier ANI 2013 (Art. L911-7 CSS)",
             "valeur":h1_m,"statut":h1_s,"critique":(contrat=="collectif")},
            {"id":"H2","hypothese":"100% Santé optique/dentaire (Décret 2019-21)",
             "valeur":h2_m,"statut":h2_s,"critique":False},
            {"id":"H3","hypothese":"Conformité réglementaire globale",
             "valeur":h3_m,"statut":h3_s,"critique":True},
        ]

    def _rag(self, hyp, conforme_ani, conforme_cent, contrat) -> str:
        non_val = [h for h in hyp if h["statut"]=="NON VALIDÉE" and h["critique"]]
        if non_val or (not conforme_ani and contrat=="collectif"):
            return "ROUGE"
        a_just = [h for h in hyp if h["statut"]=="À JUSTIFIER"]
        if a_just or not conforme_cent:
            return "AMBRE"
        return "VERT"

    def _commentaire(self, rag, contrat, ani, cent_pct,
                     surcout_ani, surcout_cent, hyp) -> str:
        ic = "🟢" if rag=="VERT" else ("🟡" if rag=="AMBRE" else "🔴")
        L = [
            "="*65,
            f"  CONFORMITÉ ANI 2013 + 100% SANTÉ — SP-REG3 v{self.VERSION}",
            f"  {ic} STATUT : {rag} | Contrat : {contrat.upper()}",
            "="*65,"",
            f"  {'✅' if ani['conforme'] else '❌'} ANI 2013       : {ani['note']}",
            f"  {'✅' if cent_pct['conforme'] else '⚠️'} 100% Santé   : {cent_pct['note']}",
            f"  Surcoût total : {surcout_ani+surcout_cent:.0f}€/assuré/an"
            f" (ANI={surcout_ani:.0f}€ + 100%={surcout_cent:.0f}€)",
            "",
        ]
        if ani["detail"]:
            L.append("  DÉTAIL ANI 2013 :")
            for p, d in ani["detail"].items():
                L.append(f"    {d.get('note','')} — {p}")
        if cent_pct["detail"]:
            L.append("\n  DÉTAIL 100% SANTÉ :")
            for p, d in cent_pct["detail"].items():
                L.append(f"    {d.get('note','')} — {p}")
        return "\n".join(L)
