"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      ACTUARIA — AGENT S1 LÉONIE : TARIFICATION FRAIS DE SANTÉ v2.0        ║
║                  Sous CHIARA (Équipe Santé) · Direction SP                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PÉRIMÈTRE : Complémentaire santé individuelle et collective                ║
║              Tables DREES 2023 · CCAM · NGAP · ANI 2013 · 100% Santé      ║
║                                                                              ║
║  NOUVEAUTÉS v2 :                                                             ║
║    ✅ Branchement result_a2 (données réelles client via Diana)              ║
║    ✅ Tarification par poste depuis données réelles si disponibles          ║
║    ✅ Fallback paramètres manuels si pas de données                         ║
║    ✅ Standard ActuarIA : RAG + 3 hypothèses + 4 graphiques + commentaire  ║
║    ✅ Sorties vers S2 Selma et S3 Binta                                     ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_a2     → données réelles depuis Diana/Kenji (optionnel)          ║
║    nb_assures    → nombre d'assurés (fallback si pas de données)           ║
║    age_moyen     → âge moyen du portefeuille                               ║
║    contrat       → 'individuel' | 'collectif'                              ║
║    garantie_niveau → 'eco' | 'confort' | 'premium' | 'luxe'              ║
║    chargement_pct  → taux de chargement                                    ║
║                                                                              ║
║  SORTIES VERS S2 SELMA :                                                    ║
║    primes_acquises  → base provisionnement                                 ║
║    sinistralite_par_poste → PSAP par poste                                ║
║    loss_ratio_attendu → LR attendu                                         ║
║                                                                              ║
║  VERSION : 2.0 — 20/06/2026                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json, logging, os, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

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
AMBRE="#F39C12"; BLEU="#3498DB"; VIOLET="#9B59B6"

LAYOUT_BASE = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16,r=16,t=60,b=60), height=300,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))

# ── Référentiels DREES 2023 ───────────────────────────────────────────────────
# Coûts moyens par poste (€/assuré/an) — source DREES Comptes de la Santé 2023
COUTS_POSTES_REF = {
    "medecine":        {"freq": 4.2,  "cout_acte": 28.5,   "tc_ss": 0.70},
    "pharmacie":       {"freq": 8.5,  "cout_acte": 22.0,   "tc_ss": 0.65},
    "hospitalisation": {"freq": 0.15, "cout_acte": 3_500.0,"tc_ss": 0.80},
    "dentaire":        {"freq": 1.2,  "cout_acte": 180.0,  "tc_ss": 0.25},
    "optique":         {"freq": 0.45, "cout_acte": 320.0,  "tc_ss": 0.00},
}

# Niveaux de garantie
NIVEAUX_GARANTIE = {"eco": 0.60, "confort": 1.00, "premium": 1.40, "luxe": 1.80}

# Facteur catégorie sociopro (risque santé)
FACT_CSP = {"ouvrier": 1.20, "employe": 1.00, "cadre": 0.85, "cadre_sup": 0.75}

# Seuils ANI 2013 : panier minimum obligatoire
ANI_PANIER_MIN = {
    "medecine":        30.0,   # ≥ 100% BR consultations
    "hospitalisation": 100.0,  # ≥ 100% BR séjour
    "dentaire":        75.0,   # ≥ 125% BR soins dentaires
    "optique":         100.0,  # verres + montures min
    "pharmacie":       0.0,
}


# ══════════════════════════════════════════════════════════════════════════════
class AgentS1TarificationSante:
    """
    Agent S1 Léonie — Tarification Frais de Santé v2.0.
    Sous CHIARA, Direction Santé-Prévoyance.

    Tarifie les garanties santé par poste (médecine, pharmacie,
    hospitalisation, dentaire, optique) selon les tables DREES 2023,
    avec branchement sur les données réelles du client si disponibles.
    """
    NOM     = "Léonie"
    CODE    = "S1"
    VERSION = "2.0"
    MANAGER = "Chiara (Équipe Santé)"

    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.s1.leonie")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"S1 Léonie v{self.VERSION} | {self.MANAGER}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_a2        = None,
            nb_assures:  int = 1000,
            age_moyen:   float = 42.0,
            contrat:     str = "individuel",
            garantie_niveau: str = "confort",
            chargement_pct:  float = 0.18,
            csp:         str = "employe",
            generer_graphiques: bool = True) -> Dict:

        t0  = datetime.now()
        aid = f"S1_{t0.strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"[{aid}] S1 Léonie v{self.VERSION} | {nb_assures} assurés | âge={age_moyen}")

        try:
            # ── 1. EXTRACTION DONNÉES RÉELLES (si A2 disponible) ─────────────
            source, nb_assures, age_moyen, csp = self._extraire_donnees(
                result_a2, nb_assures, age_moyen, csp
            )

            # ── 2. FACTEURS ──────────────────────────────────────────────────
            fact_age      = max(0.5, 0.7 + (age_moyen - 30) * 0.015)
            fact_garantie = NIVEAUX_GARANTIE.get(garantie_niveau, 1.0)
            fact_csp      = FACT_CSP.get(csp, 1.0)

            # ── 3. SINISTRALITÉ PAR POSTE ─────────────────────────────────────
            postes, total_sin = self._calculer_postes(
                result_a2, fact_age, fact_garantie, fact_csp, nb_assures
            )

            # ── 4. PRIMES ────────────────────────────────────────────────────
            prime_pure     = total_sin
            prime_comm     = prime_pure * (1 + chargement_pct)
            prime_mensuelle= prime_comm / 12
            prime_marche   = prime_pure * 1.20   # référence marché

            # Primes acquises portefeuille
            primes_acquises = prime_comm * nb_assures

            # Loss Ratio attendu
            lr_attendu = prime_pure / max(prime_comm, 1)

            # ── 5. CONFORMITÉ ANI 2013 ────────────────────────────────────────
            ani = self._verifier_ani(postes, garantie_niveau)

            # ── 6. STATUT RAG + HYPOTHÈSES ───────────────────────────────────
            hyp = self._hypotheses(lr_attendu, postes, prime_comm, prime_marche,
                                   ani, garantie_niveau)
            rag = self._rag(hyp, lr_attendu, ani)

            # ── 7. COMMENTAIRE ────────────────────────────────────────────────
            com = self._commentaire(rag, nb_assures, age_moyen, contrat,
                                    garantie_niveau, prime_pure, prime_comm,
                                    prime_mensuelle, lr_attendu, postes,
                                    primes_acquises, ani, source, hyp)

            # ── 8. GRAPHIQUES ─────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(postes, prime_pure, prime_comm,
                                       prime_marche, lr_attendu, hyp)

            # ── 9. AUDIT ─────────────────────────────────────────────────────
            self._audit(aid, prime_pure, prime_comm, lr_attendu, rag, nb_assures)

            if self.verbose:
                self._console(aid, rag, prime_pure, prime_comm, lr_attendu,
                              nb_assures, primes_acquises)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':         True,
                'agent':           self.NOM,
                'version':         self.VERSION,
                'audit_id':        aid,
                'statut_rag':      rag,
                'source_donnees':  source,

                # ── Tarification ────────────────────────────────────────────
                'prime_pure':           round(prime_pure, 2),
                'prime_commerciale':    round(prime_comm, 2),
                'prime_mensuelle':      round(prime_mensuelle, 2),
                'primes_acquises':      round(primes_acquises, 2),
                'chargement_pct':       chargement_pct,
                'ratio_sp_attendu':     round(lr_attendu, 4),

                # ── Portefeuille ─────────────────────────────────────────────
                'nb_assures':       nb_assures,
                'age_moyen':        age_moyen,
                'contrat':          contrat,
                'garantie_niveau':  garantie_niveau,
                'csp':              csp,

                # ── Sinistralité par poste ────────────────────────────────────
                'postes': postes,

                # ── ANI 2013 ─────────────────────────────────────────────────
                'ani_conforme': ani['conforme'],
                'ani_detail':   ani,

                # ── Sorties vers S2 Selma ────────────────────────────────────
                'sorties_s2': {
                    'primes_acquises':        round(primes_acquises, 2),
                    'sinistres_attendus':      round(prime_pure * nb_assures, 2),
                    'loss_ratio_attendu':      round(lr_attendu, 4),
                    'sinistralite_par_poste':  {
                        p: round(v['sinistre_annuel'] * nb_assures, 2)
                        for p, v in postes.items()
                    },
                    'nb_assures':              nb_assures,
                    'prime_pure_unitaire':     round(prime_pure, 2),
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
    def _extraire_donnees(self, result_a2, nb_assures, age_moyen, csp):
        """
        Extrait les paramètres depuis result_a2 si disponible.
        Fallback sur les paramètres manuels sinon.
        """
        if not result_a2 or not result_a2.get('success'):
            return 'parametres_manuels', nb_assures, age_moyen, csp

        try:
            df = result_a2.get('dataframe')
            if df is None or len(df) == 0:
                return 'parametres_manuels', nb_assures, age_moyen, csp

            import pandas as pd
            # Nombre d'assurés
            nb_reel = len(df)

            # Âge moyen
            for col in ['age','age_assure','age_client']:
                if col in df.columns:
                    age_reel = float(df[col].dropna().mean())
                    break
            else:
                age_reel = age_moyen

            # CSP
            for col in ['categorie_sociopro','csp','statut_professionnel']:
                if col in df.columns:
                    mode_csp = df[col].mode()
                    csp_reel = str(mode_csp.iloc[0]).lower() if len(mode_csp) > 0 else csp
                    break
            else:
                csp_reel = csp

            self.logger.info(
                f"Données réelles A2 : {nb_reel} assurés | "
                f"âge moy={age_reel:.1f} | CSP={csp_reel}"
            )
            return 'donnees_reelles_a2', nb_reel, age_reel, csp_reel

        except Exception as e:
            self.logger.warning(f"Extraction A2 : {e} → fallback paramètres")
            return 'parametres_manuels', nb_assures, age_moyen, csp

    # ══════════════════════════════════════════════════════════════════════════
    # 2. CALCUL SINISTRALITÉ PAR POSTE
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_postes(self, result_a2, fact_age, fact_garantie, fact_csp, nb_assures):
        """
        Calcule la sinistralité par poste.
        Si données réelles disponibles → les utilise directement.
        Sinon → tables DREES 2023.
        """
        postes = {}
        total_sin = 0.0

        # Vérifier si données réelles santé disponibles dans A2
        donnees_reelles = {}
        if result_a2 and result_a2.get('success'):
            df = result_a2.get('dataframe')
            if df is not None:
                for p in COUTS_POSTES_REF:
                    col_sin = f'sinistre_{p}'
                    if col_sin in df.columns:
                        donnees_reelles[p] = float(df[col_sin].mean())

        for poste, ref in COUTS_POSTES_REF.items():
            if poste in donnees_reelles:
                # Données réelles du client
                sin_an = donnees_reelles[poste]
                freq   = ref['freq'] * fact_age
                cout   = sin_an / max(freq, 0.01)
                remb   = cout * ref['tc_ss']
                charge = sin_an
                source_p = 'donnees_client'
            else:
                # Tables DREES 2023
                freq   = ref['freq']   * fact_age * fact_garantie * fact_csp
                cout   = ref['cout_acte'] * fact_age
                remb   = cout * ref['tc_ss']
                charge = (cout - remb) * min(fact_garantie, 2.0)
                sin_an = freq * charge
                source_p = 'DREES_2023'

            postes[poste] = {
                'frequence_an':     round(freq, 3),
                'cout_moyen':       round(cout, 2),
                'remb_ss':          round(remb, 2),
                'charge_mutuelle':  round(charge, 2),
                'sinistre_annuel':  round(sin_an, 2),
                'source':           source_p,
            }
            total_sin += sin_an

        nb_postes_reels = len(donnees_reelles)
        if nb_postes_reels > 0:
            self.logger.info(
                f"{nb_postes_reels}/5 postes depuis données client | "
                f"{5-nb_postes_reels} depuis DREES 2023"
            )

        return postes, total_sin

    # ══════════════════════════════════════════════════════════════════════════
    # 3. CONFORMITÉ ANI 2013
    # ══════════════════════════════════════════════════════════════════════════
    def _verifier_ani(self, postes, garantie_niveau):
        """
        Vérifie la conformité au panier ANI 2013 (complémentaire collective).
        Le panier minimum doit couvrir : médecine, hospit, dentaire, optique.
        """
        resultats = {}
        conforme  = True

        for poste, seuil in ANI_PANIER_MIN.items():
            if seuil == 0 or poste not in postes:
                resultats[poste] = {'ok': True, 'seuil': seuil, 'note': 'N/A'}
                continue
            charge = postes[poste].get('charge_mutuelle', 0)
            ok = charge >= seuil
            if not ok:
                conforme = False
            resultats[poste] = {
                'ok':     ok,
                'seuil':  seuil,
                'charge': round(charge, 2),
                'note':   '✅' if ok else f'❌ {charge:.0f}€ < {seuil:.0f}€ min ANI',
            }

        # Éco → ANI non requis (individuel uniquement)
        if garantie_niveau == 'eco':
            conforme = True   # L'ANI s'applique au collectif

        return {
            'conforme':   conforme,
            'detail':     resultats,
            'note_globale': (
                "✅ Garanties conformes au panier ANI 2013"
                if conforme else
                "⚠️ Panier ANI 2013 non atteint sur certains postes"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 4. HYPOTHÈSES — STANDARD ACTUARIA
    # ══════════════════════════════════════════════════════════════════════════
    def _hypotheses(self, lr, postes, prime_comm, prime_marche, ani, garantie):
        # H1 — Ratio S/P ∈ [65%, 85%]
        if 0.65 <= lr <= 0.85:
            h1_s = 'VALIDÉE'
            h1_m = f"Ratio S/P = {lr*100:.1f}% ∈ [65%, 85%] ✅"
        elif lr < 0.65:
            h1_s = 'À JUSTIFIER'
            h1_m = f"Ratio S/P = {lr*100:.1f}% < 65% — prime trop élevée"
        elif lr <= 0.95:
            h1_s = 'À JUSTIFIER'
            h1_m = f"Ratio S/P = {lr*100:.1f}% > 85% — rentabilité insuffisante"
        else:
            h1_s = 'NON VALIDÉE'
            h1_m = f"Ratio S/P = {lr*100:.1f}% > 95% — contrat déficitaire"

        # H2 — Hospitalisation ≤ 50% du total
        total = sum(v['sinistre_annuel'] for v in postes.values())
        part_hospit = postes['hospitalisation']['sinistre_annuel'] / max(total, 1)
        if part_hospit <= 0.50:
            h2_s = 'VALIDÉE'
            h2_m = f"Hospit = {part_hospit*100:.1f}% ≤ 50% — répartition équilibrée ✅"
        elif part_hospit <= 0.65:
            h2_s = 'À JUSTIFIER'
            h2_m = f"Hospit = {part_hospit*100:.1f}% ∈ [50%, 65%] — surveiller l'anti-sélection"
        else:
            h2_s = 'NON VALIDÉE'
            h2_m = f"Hospit = {part_hospit*100:.1f}% > 65% — concentration risque hospitalier"

        # H3 — Prime compétitive vs marché + conformité ANI
        ratio_comp = prime_comm / max(prime_marche, 1)
        if ratio_comp <= 1.10 and ani['conforme']:
            h3_s = 'VALIDÉE'
            h3_m = f"Prime/marché = {ratio_comp:.3f} ✅ | ANI 2013 conforme ✅"
        elif ratio_comp <= 1.25:
            h3_s = 'À JUSTIFIER'
            h3_m = f"Prime/marché = {ratio_comp:.3f} légèrement élevée | ANI: {'✅' if ani['conforme'] else '⚠️'}"
        else:
            h3_s = 'NON VALIDÉE'
            h3_m = f"Prime/marché = {ratio_comp:.3f} > 1.25 — non compétitif"
            if not ani['conforme']:
                h3_m += " | ANI 2013 non conforme"

        return [
            {'id':'H1','hypothese':'Ratio S/P dans la norme mutualité [65%, 85%]',
             'valeur':h1_m,'statut':h1_s,'critique':True},
            {'id':'H2','hypothese':'Hospitalisation ≤ 50% de la sinistralité totale',
             'valeur':h2_m,'statut':h2_s,'critique':True},
            {'id':'H3','hypothese':'Prime compétitive vs marché + conformité ANI 2013',
             'valeur':h3_m,'statut':h3_s,'critique':True},
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # 5. STATUT RAG
    # ══════════════════════════════════════════════════════════════════════════
    def _rag(self, hyp, lr, ani):
        non_val = [h for h in hyp if h['statut'] == 'NON VALIDÉE']
        a_just  = [h for h in hyp if h['statut'] == 'À JUSTIFIER']
        if non_val:
            return 'ROUGE'
        if a_just or not ani['conforme']:
            return 'AMBRE'
        return 'VERT'

    # ══════════════════════════════════════════════════════════════════════════
    # 6. COMMENTAIRE ACTUARIEL
    # ══════════════════════════════════════════════════════════════════════════
    def _commentaire(self, rag, nb_assures, age_moyen, contrat, garantie,
                     prime_pure, prime_comm, prime_mois, lr, postes,
                     primes_acq, ani, source, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        L = [
            "="*70,
            f"  RAPPORT TARIFICATION SANTÉ — S1 LÉONIE v{self.VERSION}",
            f"  Contrat : {contrat} | Garantie : {garantie} | Source : {source}",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
            "📊 RÉSUMÉ DIRECTION", "─"*40,
        ]
        if rag == 'VERT':
            L.append(f"✅ Tarification validée. Prime={prime_comm:.2f}€/an ({prime_mois:.2f}€/mois). Ratio S/P={lr*100:.1f}%.")
        elif rag == 'AMBRE':
            L.append(f"⚠️ Tarification acceptable — vérifier les points signalés. Prime={prime_comm:.2f}€/an.")
        else:
            L.append(f"❌ Tarification à corriger. Ratio S/P={lr*100:.1f}% hors norme ou prime non compétitive.")

        L += [
            "", "🔢 TARIFICATION PAR POSTE", "─"*40,
            f"  {'Poste':<20} {'Fréq/an':>8} {'Coût moy':>10} {'Charge mut':>12} {'Sinistre/an':>12} {'Source':>12}",
            "  " + "─"*66,
        ]
        for p, v in postes.items():
            L.append(
                f"  {p:<20} {v['frequence_an']:>8.3f} {v['cout_moyen']:>9.0f}€ "
                f"{v['charge_mutuelle']:>11.0f}€ {v['sinistre_annuel']:>11.0f}€ "
                f"{v['source']:>12}"
            )
        L += [
            "  " + "─"*66,
            f"  {'TOTAL':<20} {'':>8} {'':>10} {'':>12} {sum(v['sinistre_annuel'] for v in postes.values()):>11.0f}€",
            "",
            "💰 PRIMES", "─"*40,
            f"  Prime pure unitaire       : {prime_pure:>12.2f}€/an/assuré",
            f"  Prime commerciale         : {prime_comm:>12.2f}€/an/assuré ({prime_mois:.2f}€/mois)",
            f"  Primes acquises portfolio : {primes_acq:>12,.0f}€",
            f"  Ratio S/P attendu         : {lr*100:>11.1f}%",
            f"  Nombre d'assurés          : {nb_assures:>12,}",
            f"  Âge moyen                 : {age_moyen:>12.1f} ans",
            "", "📋 ANI 2013", "─"*40,
            f"  {ani['note_globale']}",
        ]
        for p, d in ani['detail'].items():
            if d['note'] != 'N/A':
                L.append(f"  {p:<20} : {d['note']}")

        L += ["", "📋 HYPOTHÈSES", "─"*40]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else "⚠️"
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        L += ["", "🎯 AVIS LÉONIE → CHIARA", "─"*40]
        if rag == 'VERT':
            L.append("✅ VALIDÉE — Données transmises à S2 Selma (provisionnement) et S3 Binta (reporting).")
        elif rag == 'AMBRE':
            L.append("⚠️ Revoir les points signalés avant transmission à S2/S3.")
        else:
            L.append("❌ NON VALIDÉE — Revoir la tarification avant déploiement.")
        L.append("")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════════════════════
    # 7. GRAPHIQUES — 4 AUTO-EXPLICATIFS
    # ══════════════════════════════════════════════════════════════════════════
    def _graphiques(self, postes, prime_pure, prime_comm, prime_marche, lr, hyp):
        gph = {}

        # G1 — Sinistralité par poste (barres)
        try:
            noms  = [p.replace('_',' ').title() for p in postes]
            vals  = [postes[p]['sinistre_annuel'] for p in postes]
            cols  = [OR, BLEU, ROUGE, AMBRE, VERT]
            fig = go.Figure(go.Bar(
                x=noms, y=vals, marker_color=cols[:len(noms)],
                width=0.5, opacity=0.88,
                text=[f"{v:.0f}€" for v in vals],
                textposition="outside", textfont=dict(color=BLANC, size=10),
                hovertemplate="<b>%{x}</b><br>%{y:.0f}€/assuré/an<extra></extra>",
            ))
            h2 = next(h for h in hyp if h['id']=='H2')
            c2 = VERT if h2['statut']=='VALIDÉE' else (AMBRE if h2['statut']=='À JUSTIFIER' else ROUGE)
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G1 — Sinistralité par poste (€/assuré/an) — DREES 2023",
                           font=dict(color=OR,size=12),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC,size=9),showgrid=False),
                yaxis=dict(visible=False),
                annotations=[dict(
                    text="💡 L'hospitalisation ne doit pas dépasser 50% du total — risque d'anti-sélection.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['sinistralite_postes'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — Jauge Ratio S/P
        try:
            h1 = next(h for h in hyp if h['id']=='H1')
            c1 = VERT if h1['statut']=='VALIDÉE' else (AMBRE if h1['statut']=='À JUSTIFIER' else ROUGE)
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=lr*100,
                number=dict(suffix="%", font=dict(color=c1, size=28), valueformat=".1f"),
                title=dict(text=f"Ratio S/P — {h1['valeur'][:40]}", font=dict(color=c1, size=11)),
                gauge=dict(
                    axis=dict(range=[0,110], tickvals=[0,55,65,75,85,95,110],
                              ticktext=["0","55","65%","75%","85%","95",""],
                              tickfont=dict(color=GRIS,size=8)),
                    bar=dict(color=c1, thickness=0.25),
                    bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0,65],  color="rgba(243,156,18,0.12)"),
                        dict(range=[65,85],  color="rgba(46,204,113,0.12)"),
                        dict(range=[85,110], color="rgba(231,76,60,0.12)"),
                    ],
                    threshold=dict(line=dict(color=VERT,width=3), thickness=0.8, value=75),
                ),
            ))
            fig.update_layout(
                paper_bgcolor=NAVY, font=dict(color=BLANC),
                margin=dict(l=30,r=30,t=80,b=50), height=300,
                annotations=[dict(
                    text="💡 Zone verte [65%-85%] = norme mutualité. En dessous = prime trop élevée.",
                    xref="paper",yref="paper",x=0.5,y=-0.12,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            )
            gph['jauge_ratio_sp'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — Prime pure vs commerciale vs marché
        try:
            h3 = next(h for h in hyp if h['id']=='H3')
            c3 = VERT if h3['statut']=='VALIDÉE' else (AMBRE if h3['statut']=='À JUSTIFIER' else ROUGE)
            fig = go.Figure(go.Bar(
                x=["Prime pure", "Prime commerciale", "Référence marché"],
                y=[prime_pure, prime_comm, prime_marche],
                marker_color=[OR, c3, GRIS],
                width=0.4, opacity=0.88,
                text=[f"{v:.0f}€" for v in [prime_pure, prime_comm, prime_marche]],
                textposition="outside", textfont=dict(color=BLANC, size=11),
            ))
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text=f"G3 — Compétitivité tarifaire | {h3['valeur'][:50]}",
                           font=dict(color=c3,size=11),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(visible=False), bargap=0.35,
                annotations=[dict(
                    text="💡 La prime commerciale doit rester proche de la référence marché pour éviter la perte d'adhérents.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['competitivite_tarifaire'] = fig
        except Exception as e:
            self.logger.warning(f"G3:{e}")

        # G4 — Scorecard hypothèses
        try:
            fig = go.Figure()
            for h in hyp:
                c = VERT if h['statut']=='VALIDÉE' else (AMBRE if h['statut']=='À JUSTIFIER' else ROUGE)
                ic = "✅" if h['statut']=='VALIDÉE' else ("⚠️" if h['statut']=='À JUSTIFIER' else "❌")
                s = 1.0 if h['statut']=='VALIDÉE' else (0.5 if h['statut']=='À JUSTIFIER' else 0.0)
                fig.add_trace(go.Bar(
                    x=[s], y=[h['hypothese'][:40]], orientation="h",
                    marker_color=c, width=0.5, opacity=0.85,
                    text=f"{ic} {h['statut']}", textposition="outside",
                    textfont=dict(color=c,size=10),
                    hovertemplate=f"<b>{h['hypothese']}</b><br>{h['valeur']}<extra></extra>",
                    showlegend=False,
                ))
            statut_glob = 'VERT' if all(h['statut']=='VALIDÉE' for h in hyp) else ('ROUGE' if any(h['statut']=='NON VALIDÉE' for h in hyp) else 'AMBRE')
            cg = VERT if statut_glob=='VERT' else (AMBRE if statut_glob=='AMBRE' else ROUGE)
            l = dict(**LAYOUT_BASE)
            l.update(dict(
                title=dict(text="G4 — Scorecard Tarification Santé",
                           font=dict(color=cg,size=12),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 3 ✅ = tarification santé validée, conforme DREES/ANI et compétitive.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**l)
            gph['scorecard_sante'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        return gph

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES
    # ══════════════════════════════════════════════════════════════════════════
    def _audit(self, aid, prime_pure, prime_comm, lr, rag, nb_assures):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'prime_pure':prime_pure,'prime_comm':prime_comm,
                 'lr_attendu':lr,'nb_assures':nb_assures}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, rag, prime_pure, prime_comm, lr, nb_assures, primes_acq):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        print(f"\n{'─'*70}")
        print(f"  S1 LÉONIE v{self.VERSION} | {aid} | {ic} {rag}")
        print(f"  Prime pure={prime_pure:.2f}€ | Commerciale={prime_comm:.2f}€ | S/P={lr*100:.1f}%")
        print(f"  Portfolio: {nb_assures:,} assurés | Primes={primes_acq:,.0f}€")
        print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {'success':False,'agent':self.NOM,'version':self.VERSION,
                'audit_id':aid,'statut_rag':'ROUGE',
                'prime_pure':0,'prime_commerciale':0,'primes_acquises':0,
                'ratio_sp_attendu':0,'postes':{},'ani_conforme':False,
                'sorties_s2':{},'hypotheses':[],'commentaire':f"❌ ERREUR S1:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  S1 LÉONIE v2.0 — DÉMO TARIFICATION FRAIS DE SANTÉ")
    print("  DREES 2023 | ANI 2013 | Branchement A2 | Standard ActuarIA")
    print("="*70)

    agent = AgentS1TarificationSante(
        models_path='/tmp/s1/models', audit_path='/tmp/s1/audit', verbose=True
    )

    # Démo sans données (paramètres manuels)
    r = agent.run(
        result_a2=None,
        nb_assures=5000,
        age_moyen=43.0,
        contrat="collectif",
        garantie_niveau="confort",
        chargement_pct=0.18,
        csp="employe",
        generer_graphiques=False,
    )

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut     : {r['statut_rag']}")
    print(f"  Source     : {r['source_donnees']}")
    print(f"  Prime pure : {r['prime_pure']:.2f}€/an/assuré")
    print(f"  Prime comm : {r['prime_commerciale']:.2f}€/an ({r['prime_mensuelle']:.2f}€/mois)")
    print(f"  Primes acq : {r['primes_acquises']:,.0f}€")
    print(f"  Ratio S/P  : {r['ratio_sp_attendu']*100:.1f}%")
    print(f"  ANI 2013   : {'✅' if r['ani_conforme'] else '⚠️'}")
    print(f"\n  Sinistralité par poste :")
    for p, v in r['postes'].items():
        print(f"    {p:<20} : {v['sinistre_annuel']:>8.0f}€/assuré/an [{v['source']}]")
    print(f"\n  Sorties vers S2 Selma :")
    s2 = r['sorties_s2']
    print(f"    Primes acquises    : {s2['primes_acquises']:,.0f}€")
    print(f"    Sinistres attendus : {s2['sinistres_attendus']:,.0f}€")
    print(f"    Loss Ratio attendu : {s2['loss_ratio_attendu']*100:.1f}%")
    print(f"\n  Durée : {r['duree_sec']:.2f}s")
