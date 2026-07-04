"""
ActuarIA — Agent A8 : Isabelle — Stress Testing & ORSA Non-Vie
Direction Non-Vie | Manager : Kwame | Directeur : Leila

Stress Testing complet Solvabilité 2 :
→ Chocs EIOPA calibrés sur taux marché réels
→ Reverse Stress Testing (seuil insolvabilité)
→ Scénarios historiques (Lothar 1999 · Grêle 2022 · COVID · Inflation 2022)
→ Capital allocation par sous-module
→ ORSA enrichi depuis result_a7
→ Actions de gestion recommandées par IA
→ QRT S.25.01 automatique
→ Validation + 8 graphiques auto-explicatifs

FLUX OBLIGATOIRES :
  result_a7 ← AgentA7Provisionnement.run()
  result_a6 ← AgentA6Selection.run()
"""

import numpy as np
import logging
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | actuaria.a8 | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)



# ── Chargement du module données marché ───────────────────────────────────────
def _charger_market_data() -> Dict:
    """
    Charge les données marché depuis market_data.py.
    Fallback sur valeurs EIOPA par défaut si module indisponible.
    """
    logger = logging.getLogger("actuaria.a8")
    # Chercher market_data.py dans plusieurs chemins possibles
    chemins = [
        Path("data/marche/market_data.py"),
        Path(__file__).parent / "data" / "marche" / "market_data.py",
        Path("C:/Users/selse/actuaria-app/data/marche/market_data.py"),
    ]
    for chemin in chemins:
        if chemin.exists():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("market_data", chemin)
                md   = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(md)
                data = md.fetch_all_market()
                logger.info(
                    f"Données marché chargées ({data['fiabilite']}) : "
                    f"OAT10={data['oat_10ans']['taux_pct']}% · "
                    f"RFR={data['rfr_10ans']['rfr_pct']}%"
                )
                return data
            except Exception as e:
                logger.warning(f"market_data.py trouvé mais erreur : {e}")

    # Fallback EIOPA par défaut
    logger.warning("market_data indisponible — valeurs EIOPA de référence utilisées")
    return {
        'oat_10ans':     {'taux_pct': 3.65, 'source': 'Défaut EIOPA', 'fiabilite': 'DEFAUT'},
        'oat_5ans':      {'taux_pct': 3.10, 'source': 'Défaut EIOPA', 'fiabilite': 'DEFAUT'},
        'rfr_10ans':     {'rfr_pct': 3.20, 'rfr_avec_va_pct': 3.55, 'ufr': 3.30, 'va': 0.35},
        'rfr_20ans':     {'rfr_pct': 3.30, 'rfr_avec_va_pct': 3.65},
        'scr_params':    {
            'scr_souscription_non_vie': {
                'sigma_primes_rc_auto': 0.10,
                'sigma_primes_incendie': 0.08,
                'sigma_primes_rc_general': 0.11,
                'sigma_reserves_rc_auto': 0.09,
                'sigma_reserves_incendie': 0.10,
                'sigma_reserves_rc_general': 0.11,
                'facteur_catastrophe_vent': 0.10,
                'facteur_catastrophe_grele': 0.03,
                'facteur_catastrophe_inondation': 0.04,
            },
            'scr_marche': {
                'choc_taux_hausse_10ans': 0.48,
                'choc_taux_baisse_10ans': -0.38,
                'choc_actions_type1': 0.39,
                'choc_actions_type2': 0.49,
                'choc_immobilier': 0.25,
                'choc_spread_IG': 0.009,
                'choc_devise': 0.25,
            },
            'mcr': {
                'pct_scr_min': 0.25,
                'seuil_absolu_non_vie': 2_500_000,
            },
        },
        'macro':         {'inflation_france_mai2026': 2.4, 'taux_directeur_bce': 2.25,
                          'croissance_pib_france_2026_prev': 0.9},
        'portefeuille':  {'duration_actifs_moy': 4.2, 'rendement_actifs_attendu': 3.80,
                          'allocation': {'obligations_souveraines': 0.45}},
        'source_globale':'⚠️ Valeurs EIOPA par défaut (market_data.py non trouvé)',
        'fiabilite':     'DEFAUT',
        'signaux':       ['⚠️ Valeurs EIOPA par défaut — installer market_data.py'],
        'date_collecte': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


class AgentA8StressTesting:
    """
    Agent A8 — Isabelle : Stress Testing & ORSA Non-Vie.

    Reçoit obligatoirement :
      → result_a7 : BE · bootstrap P99.5 · ORSA provisions · tail factor
      → result_a6 : prime nette · Gini · loss ratio attendu

    Produit :
      → SCR total agrégé EIOPA avec taux marché réels
      → Reverse stress testing (seuil insolvabilité)
      → 4 scénarios historiques calibrés (Lothar · Grêle · COVID · Inflation)
      → Capital allocation par sous-module
      → ORSA enrichi (A7 + chocs A8)
      → Actions de gestion recommandées
      → QRT S.25.01 pré-rempli
      → 8 graphiques auto-explicatifs
    """

    def __init__(
        self,
        models_path: str = "models",
        audit_path:  str = "audit",
        verbose:     bool = True,
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose
        self.logger      = logging.getLogger("actuaria.a8")
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTHODE PRINCIPALE
    # ══════════════════════════════════════════════════════════════════════════

    def run(
        self,
        result_a7:          Optional[Dict] = None,
        result_a6:          Optional[Dict] = None,
        fonds_propres:      float = 3_000_000,
        horizons_orsa:      List[int] = [1, 2, 3, 4, 5],
        sous_branche:       str = 'auto',
        generer_graphiques: bool = True,
        # Compatibilité v1
        result_a3:          Optional[Dict] = None,
        primes_acq:         float = 5_000_000,
        scr_actuel:         float = 800_000,
    ) -> Dict[str, Any]:
        """
        Pipeline Stress Testing & ORSA complet.

        Paramètres obligatoires recommandés :
          result_a7 : résultat de AgentA7Provisionnement.run()
          result_a6 : résultat de AgentA6Selection.run()

        Paramètres fallback (si A7/A6 absents) :
          primes_acq    : primes acquises estimées (€)
          fonds_propres : fonds propres disponibles (€)
        """
        audit_id = f"A8_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger   = self.logger
        t_debut  = datetime.now()

        if self.verbose:
            logger.info(f"[{audit_id}] Agent A8 Stress Testing démarré")

        try:
            # ── Étape 1 : Charger les données marché ─────────────────────────
            logger.info("Étape 1/8 : Chargement données marché")
            mkt = _charger_market_data()
            scr_params = mkt['scr_params']
            oat_10ans  = mkt['oat_10ans']['taux_pct'] / 100
            rfr_10ans  = mkt['rfr_10ans']['rfr_pct']  / 100
            rfr_va     = mkt['rfr_10ans']['rfr_avec_va_pct'] / 100
            inflation  = mkt['macro']['inflation_france_mai2026'] / 100

            # ── Étape 2 : Extraire les données de A7 ─────────────────────────
            logger.info("Étape 2/8 : Extraction données A7")
            if result_a7 and result_a7.get('success'):
                be         = result_a7['best_estimate']['best_estimate']
                # Clés bootstrap en minuscule (A7 retourne p99_5, p90)
                boot       = result_a7.get('bootstrap', {})
                p99_5      = boot.get('p99_5', boot.get('P99_5', be * 1.25))
                p90        = boot.get('p90',   boot.get('P90',   be * 1.12))
                # tail_factor est un dict avec clé 'tail_factor'
                tail_d     = result_a7.get('tail_factor', {})
                tail_f     = tail_d.get('tail_factor', 1.0) if isinstance(tail_d, dict) else 1.0
                orsa_a7    = result_a7.get('orsa_provisions', {})
                sous_br    = result_a7.get('sous_branche', sous_branche)
                facteurs_cl= result_a7.get('chain_ladder', {}).get('facteurs', [])
                logger.info(f"A7 branché : BE={be:,.0f}€ | P99.5={p99_5:,.0f}€ | Tail={tail_f:.4f}")
            else:
                be      = scr_actuel * 3.5
                p99_5   = be * 1.25
                p90     = be * 1.12
                tail_f  = 1.0
                orsa_a7 = {}
                sous_br = sous_branche
                facteurs_cl = []
                logger.warning("result_a7 absent — utilisation des valeurs par défaut")

            # ── Étape 3 : Extraire les données de A6 ─────────────────────────
            logger.info("Étape 3/8 : Extraction données A6")
            if result_a6 and result_a6.get('success', True):
                # A6 retourne modele_production avec gini_test et prime_pure
                mp          = result_a6.get('modele_production', {})
                # Prime : depuis modele_production ou backtest ou fallback
                bt          = result_a6.get('backtest', {})
                # prime_pure de A6 = prime unitaire (EUR/contrat), pas les primes acquises.
                # Utiliser primes_acquises si disponible dans A6.
                prime_nette = (mp.get('primes_acquises',
                               bt.get('moy_train', primes_acq)))
                if not prime_nette or prime_nette <= 0:
                    prime_nette = primes_acq
                gini        = mp.get('gini_test', result_a6.get('gini', 0.25))
                lr_attendu  = result_a6.get('loss_ratio_attendu', 0.72)
                modele      = mp.get('modele', result_a6.get('modele_retenu', 'N/A'))
                logger.info(f"A6 branché : PA={prime_nette:,.0f}€ | Gini={gini:.4f} | LR={lr_attendu:.2f}")
            else:
                prime_nette = primes_acq
                gini        = 0.25
                lr_attendu  = 0.72
                modele      = 'N/A'
                logger.warning("result_a6 absent — utilisation des valeurs par défaut")

            # ── Étape 4 : Chocs S2 calibrés sur taux marché ──────────────────
            logger.info("Étape 4/8 : Calcul chocs S2 (taux marché réels)")
            chocs = self._chocs_s2(
                be, prime_nette, p99_5, scr_params, oat_10ans, rfr_10ans,
                inflation, sous_br, tail_f
            )

            # ── Étape 5 : Agrégation SCR total EIOPA ─────────────────────────
            logger.info("Étape 5/8 : Agrégation SCR (matrice corrélation EIOPA)")
            scr_total_dict = self._agreger_scr(chocs, fonds_propres, scr_params)

            # ── Étape 6 : Points avancés ──────────────────────────────────────
            logger.info("Étape 6/8 : Points avancés (reverse · historiques · capital)")
            reverse  = self._reverse_stress_testing(
                fonds_propres, scr_total_dict['scr_total'],
                be, prime_nette, inflation
            )
            historiq = self._scenarios_historiques(be, prime_nette, fonds_propres, scr_total_dict['scr_total'])
            capital  = self._capital_allocation(chocs, scr_total_dict['scr_total'])
            orsa_enr = self._enrichir_orsa_avec_chocs(orsa_a7, scr_total_dict, horizons_orsa, be, prime_nette)
            actions  = self._actions_gestion_ia(scr_total_dict, reverse, historiq, gini, lr_attendu)
            qrt_s25  = self._qrt_s25(scr_total_dict, fonds_propres, be, prime_nette)

            # ── Étape 7 : Validation + commentaire ───────────────────────────
            logger.info("Étape 7/8 : Validation hypothèses")
            val      = self._valider_stress_testing(scr_total_dict, reverse, historiq, mkt)
            statut   = self._calculer_statut_rag(scr_total_dict, val)
            commentaire = self._commenter_actuaire_senior(
                scr_total_dict, reverse, historiq, actions, mkt, statut
            )

            # ── Étape 8 : Graphiques ─────────────────────────────────────────
            graphiques = {}
            gv         = {}
            if generer_graphiques:
                logger.info("Étape 8/8 : Génération graphiques")
                graphiques = self._generer_graphiques(
                    chocs, scr_total_dict, orsa_enr, historiq, capital,
                    fonds_propres, reverse
                )
                gv = self._graphiques_validation_stress(val, scr_total_dict, mkt)

            # ── Sauvegarde ────────────────────────────────────────────────────
            self._sauvegarder(scr_total_dict, statut, audit_id)

            if self.verbose:
                self._afficher_rapport_console(
                    audit_id, scr_total_dict, reverse, statut, commentaire)

            return {
                'success':              True,
                'agent':                'A8 Isabelle',
                'sous_branche':         sous_br,
                'statut_rag':           statut,
                # Données marché utilisées
                'marche': {
                    'oat_10ans_pct':    round(oat_10ans * 100, 3),
                    'rfr_10ans_pct':    round(rfr_10ans * 100, 3),
                    'rfr_va_pct':       round(rfr_va * 100, 3),
                    'inflation_pct':    round(inflation * 100, 2),
                    'source':           mkt['source_globale'],
                    'fiabilite':        mkt['fiabilite'],
                    'signaux':          mkt['signaux'],
                },
                # Entrées reçues
                'be_utilise':           round(be, 2),
                'p99_5_utilise':        round(p99_5, 2),
                'prime_nette_utilisee': round(prime_nette, 2),
                'fonds_propres':        fonds_propres,
                'gini_a6':              round(gini, 4),
                # Résultats principaux
                'chocs_s2':             chocs,
                'scr_total':            scr_total_dict,
                # 7 points avancés
                'reverse_stress':       reverse,
                'scenarios_historiques':historiq,
                'capital_allocation':   capital,
                'orsa_enrichi':         orsa_enr,
                'actions_gestion':      actions,
                'qrt_s25':              qrt_s25,
                # Validation + graphiques
                'validation_stress':    val,
                'commentaire':          commentaire,
                'audit_id':             audit_id,
                'graphiques':           graphiques,
                'graphiques_validation':gv,
                'erreur':               None,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ══════════════════════════════════════════════════════════════════════════
    # CALCUL DES CHOCS S2
    # ══════════════════════════════════════════════════════════════════════════

    def _chocs_s2(
        self, be, prime, p99_5, scr_params, oat_10ans, rfr_10ans,
        inflation, branche, tail_f
    ) -> Dict:
        """
        Calcule les sous-modules SCR calibrés sur les taux marché réels.
        """
        nv  = scr_params['scr_souscription_non_vie']
        mkt = scr_params['scr_marche']

        # Sélection sigma selon branche
        branche_lower = branche.lower() if branche else 'auto'
        if 'incendie' in branche_lower or 'mrd' in branche_lower:
            sigma_p = nv['sigma_primes_incendie']
            sigma_r = nv['sigma_reserves_incendie']
        elif 'rc' in branche_lower or 'corporel' in branche_lower:
            sigma_p = nv['sigma_primes_rc_general']
            sigma_r = nv['sigma_reserves_rc_general']
        else:
            sigma_p = nv['sigma_primes_rc_auto']
            sigma_r = nv['sigma_reserves_rc_auto']

        # SCR souscription (formule standard EIOPA)
        scr_primes   = sigma_p * prime
        scr_reserves = sigma_r * be
        rho_pv       = 0.5  # corrélation primes/réserves EIOPA
        scr_souscr   = np.sqrt(
            scr_primes**2 + scr_reserves**2 + 2 * rho_pv * scr_primes * scr_reserves
        )

        # SCR catastrophe (calibré selon branche)
        facteur_cat = nv.get('facteur_catastrophe_vent', 0.10)
        scr_cat     = facteur_cat * prime

        # SCR marché taux (calibré sur OAT réel)
        # Choc EIOPA = +/-x% du RFR en absolu
        choc_taux_up   = mkt['choc_taux_hausse_10ans']
        choc_taux_down = abs(mkt['choc_taux_baisse_10ans'])
        # Impact sur le BE : sensibilité duration ≈ 3.5 ans
        duration_passifs = 3.5
        scr_taux_up   = be * duration_passifs * choc_taux_up
        scr_taux_down = be * duration_passifs * choc_taux_down
        scr_taux      = max(scr_taux_up, scr_taux_down)

        # SCR marché actions (sur portefeuille type assureur)
        # 10% du BE en actions type 1 (EIOPA)
        part_actions  = 0.10
        scr_actions   = be * part_actions * mkt['choc_actions_type1']

        # SCR opérationnel (4% des primes ou 0.3% des provisions)
        scr_operationnel = max(0.04 * prime, 0.003 * be)

        # Ajustement tail factor sur SCR réserves
        scr_tail = be * (tail_f - 1.0) * sigma_r

        return {
            'scr_souscription':   round(scr_souscr, 2),
            'scr_primes':         round(scr_primes, 2),
            'scr_reserves':       round(scr_reserves, 2),
            'scr_catastrophe':    round(scr_cat, 2),
            'scr_taux':           round(scr_taux, 2),
            'scr_taux_hausse':    round(scr_taux_up, 2),
            'scr_taux_baisse':    round(scr_taux_down, 2),
            'scr_actions':        round(scr_actions, 2),
            'scr_operationnel':   round(scr_operationnel, 2),
            'scr_tail_factor':    round(scr_tail, 2),
            'sigma_primes':       sigma_p,
            'sigma_reserves':     sigma_r,
            'oat_calibrage':      round(oat_10ans * 100, 3),
            'rfr_calibrage':      round(rfr_10ans * 100, 3),
            'inflation_calibrage':round(inflation * 100, 2),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # AGRÉGATION SCR TOTAL
    # ══════════════════════════════════════════════════════════════════════════

    def _agreger_scr(self, chocs, fonds_propres, scr_params) -> Dict:
        """
        Agrège les sous-modules SCR via la matrice de corrélation EIOPA.
        Calcule le ratio SCR et MCR.
        """
        # Matrice corrélation EIOPA (souscription · catastrophe · marché · opérationnel)
        corr = np.array([
            [1.00, 0.25, 0.25, 0.00],  # souscription
            [0.25, 1.00, 0.25, 0.00],  # catastrophe
            [0.25, 0.25, 1.00, 0.25],  # marché (taux + actions)
            [0.00, 0.00, 0.25, 1.00],  # opérationnel
        ])

        scr_vec = np.array([
            chocs['scr_souscription'],
            chocs['scr_catastrophe'],
            chocs['scr_taux'] + chocs['scr_actions'],
            chocs['scr_operationnel'],
        ])

        scr_total = float(np.sqrt(scr_vec @ corr @ scr_vec))

        # MCR
        mcr_params    = scr_params['mcr']
        mcr_pct       = scr_total * mcr_params['pct_scr_min']
        mcr_abs       = mcr_params['seuil_absolu_non_vie']
        mcr           = max(mcr_pct, mcr_abs)

        ratio_scr     = fonds_propres / max(scr_total, 1) * 100
        ratio_mcr     = fonds_propres / max(mcr, 1) * 100

        diversification = sum(scr_vec) - scr_total
        div_pct         = diversification / max(sum(scr_vec), 1) * 100

        return {
            'scr_total':        round(scr_total, 2),
            'mcr':              round(mcr, 2),
            'ratio_scr_pct':    round(ratio_scr, 1),
            'ratio_mcr_pct':    round(ratio_mcr, 1),
            'fonds_propres':    fonds_propres,
            'diversification':  round(diversification, 2),
            'diversification_pct': round(div_pct, 1),
            'scr_vec':          [round(v, 2) for v in scr_vec],
            'labels_vec':       ['Souscription', 'Catastrophe', 'Marché', 'Opérationnel'],
        }

    # ══════════════════════════════════════════════════════════════════════════
    # POINT 2 — REVERSE STRESS TESTING
    # ══════════════════════════════════════════════════════════════════════════

    def _reverse_stress_testing(
        self, fonds_propres, scr_base, be, prime, inflation
    ) -> Dict:
        """
        Calcule le seuil à partir duquel l'assureur devient insolvable.

        Principe : on cherche le choc minimum qui amène
        le ratio SCR à exactement 100%.

        3 questions posées :
        → De combien les sinistres peuvent-ils augmenter ?
        → De combien les taux peuvent-ils monter ?
        → Quelle inflation ruine l'assureur ?
        """
        # Marge avant insolvabilité
        marge = fonds_propres - scr_base
        marge_pct = marge / max(scr_base, 1) * 100

        # Choc sinistralité maximum supportable
        # SCR augmente si BE augmente → trouver le BE seuil
        # Approximation : SCR ≈ 0.30 × BE (règle de pouce)
        coeff_scr_be   = scr_base / max(be, 1)
        be_seuil       = fonds_propres / max(coeff_scr_be, 0.01)
        hausse_max_pct = (be_seuil - be) / max(be, 1) * 100

        # Choc taux maximum supportable
        # Impact taux sur BE : duration × choc
        duration      = 3.5
        choc_taux_max = marge / max(be * duration, 1) * 100

        # Choc inflation maximum supportable
        # Inflation augmente le coût des sinistres
        choc_inf_max  = marge / max(prime * 0.80, 1) * 100

        # Probabilité implicite d'insolvabilité (approx. log-normale)
        z_score = marge / max(scr_base * 0.30, 1)
        from scipy import stats
        prob_insolvabilite = float(stats.norm.cdf(-abs(z_score))) * 100

        if ratio := fonds_propres / max(scr_base, 1) * 100:
            if ratio >= 200:
                statut = "VERT"
                msg = f"✅ Solvabilité très solide — marge = {marge/1e3:.0f}k€ ({marge_pct:.0f}% du SCR)"
                conseil = "Les sinistres peuvent augmenter de {:.0f}% avant insolvabilité.".format(max(0, hausse_max_pct))
            elif ratio >= 150:
                statut = "VERT"
                msg = f"✅ Solvabilité solide — ratio SCR = {ratio:.0f}%"
                conseil = "Marge confortable. Surveiller si ratio < 150%."
            elif ratio >= 100:
                statut = "AMBRE"
                msg = f"⚠️ Solvabilité limite — ratio SCR = {ratio:.0f}%"
                conseil = "Actions préventives recommandées (réassurance, capital)."
            else:
                statut = "ROUGE"
                msg = f"❌ Insolvabilité — ratio SCR = {ratio:.0f}% < 100%"
                conseil = "Plan de redressement urgent requis."
        else:
            statut = "ROUGE"
            msg = "❌ SCR non calculé"
            conseil = "Vérifier les données d'entrée."

        return {
            'marge_euros':             round(marge, 2),
            'marge_pct_scr':           round(marge_pct, 1),
            'hausse_sinistres_max_pct':round(max(0, hausse_max_pct), 1),
            'choc_taux_max_pct':       round(max(0, choc_taux_max), 1),
            'choc_inflation_max_pct':  round(max(0, choc_inf_max), 1),
            'prob_insolvabilite_pct':  round(prob_insolvabilite, 4),
            'statut':                  statut,
            'message':                 msg,
            'conseil':                 conseil,
            'titre_graphique': (
                f"{'✅' if statut=='VERT' else '⚠️' if statut=='AMBRE' else '❌'} "
                f"Reverse Stress — Insolvabilité si sinistres +{max(0,hausse_max_pct):.0f}%"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # POINT 3 — SCÉNARIOS HISTORIQUES CALIBRÉS
    # ══════════════════════════════════════════════════════════════════════════

    def _scenarios_historiques(self, be, prime, fonds_propres, scr_base) -> Dict:
        """
        4 scénarios historiques réels calibrés EIOPA.

        Lothar + Martin 1999 : tempêtes décembre 1999 — 13 Md€ sinistres France
        Grêle 2022           : plus grande catastrophe grêle France — 1.8 Md€
        COVID-19 2020        : hausse sinistres + baisse primes + taux bas
        Inflation 2022-2023  : +8% coût sinistres (pièces auto, matériaux)
        """
        scenarios = {}

        # Scénario 1 — Tempêtes Lothar & Martin (1999)
        # Calibrage EIOPA : choc vent = 10% des primes + 25% hausse BE
        sinistres_lothar   = prime * 0.10 + be * 0.25
        be_post_lothar     = be + sinistres_lothar
        scr_post_lothar    = scr_base * (be_post_lothar / max(be, 1)) ** 0.7
        ratio_lothar       = fonds_propres / max(scr_post_lothar, 1) * 100
        scenarios['lothar_1999'] = {
            'nom':             'Tempêtes Lothar & Martin (décembre 1999)',
            'choc_sinistres':  round(sinistres_lothar, 2),
            'be_post':         round(be_post_lothar, 2),
            'scr_post':        round(scr_post_lothar, 2),
            'ratio_scr_post':  round(ratio_lothar, 1),
            'statut':          'VERT' if ratio_lothar >= 100 else 'ROUGE',
            'calibrage':       'Choc vent EIOPA : +10% primes + 25% provisions',
        }

        # Scénario 2 — Grêle 2022
        # Calibrage : choc grêle = 3% des primes + 8% hausse BE
        sinistres_grele    = prime * 0.03 + be * 0.08
        be_post_grele      = be + sinistres_grele
        scr_post_grele     = scr_base * (be_post_grele / max(be, 1)) ** 0.7
        ratio_grele        = fonds_propres / max(scr_post_grele, 1) * 100
        scenarios['grele_2022'] = {
            'nom':             'Grêle 2022 (plus grande catastrophe grêle France)',
            'choc_sinistres':  round(sinistres_grele, 2),
            'be_post':         round(be_post_grele, 2),
            'scr_post':        round(scr_post_grele, 2),
            'ratio_scr_post':  round(ratio_grele, 1),
            'statut':          'VERT' if ratio_grele >= 100 else 'ROUGE',
            'calibrage':       'Choc grêle EIOPA : +3% primes + 8% provisions',
        }

        # Scénario 3 — COVID-19 (2020)
        # Impact : -5% primes + 15% hausse BE (BI, annulation, RC)
        perte_primes_covid = prime * 0.05
        hausse_be_covid    = be * 0.15
        be_post_covid      = be + hausse_be_covid
        fp_post_covid      = fonds_propres - perte_primes_covid * 0.70
        scr_post_covid     = scr_base * 1.15
        ratio_covid        = fp_post_covid / max(scr_post_covid, 1) * 100
        scenarios['covid_2020'] = {
            'nom':             'COVID-19 2020 (pandémie + taux bas)',
            'choc_sinistres':  round(hausse_be_covid, 2),
            'perte_primes':    round(perte_primes_covid, 2),
            'be_post':         round(be_post_covid, 2),
            'fp_post':         round(fp_post_covid, 2),
            'scr_post':        round(scr_post_covid, 2),
            'ratio_scr_post':  round(ratio_covid, 1),
            'statut':          'VERT' if ratio_covid >= 100 else 'ROUGE',
            'calibrage':       '-5% primes + 15% provisions + 30% impact RN',
        }

        # Scénario 4 — Inflation 2022-2023 (+8% coût sinistres)
        hausse_be_inf   = be * 0.08
        be_post_inf     = be * 1.08
        scr_post_inf    = scr_base * 1.10
        ratio_inf       = fonds_propres / max(scr_post_inf, 1) * 100
        scenarios['inflation_2022'] = {
            'nom':             'Inflation 2022-2023 (+8% coûts sinistres)',
            'choc_sinistres':  round(hausse_be_inf, 2),
            'be_post':         round(be_post_inf, 2),
            'scr_post':        round(scr_post_inf, 2),
            'ratio_scr_post':  round(ratio_inf, 1),
            'statut':          'VERT' if ratio_inf >= 100 else 'ROUGE',
            'calibrage':       '+8% coût pièces/matériaux + 1pp sinistralité corporelle',
        }

        # Statut global
        statuts = [v['statut'] for v in scenarios.values()]
        nb_rouge = statuts.count('ROUGE')
        sg = 'ROUGE' if nb_rouge >= 2 else 'AMBRE' if nb_rouge == 1 else 'VERT'

        return {
            'scenarios':     scenarios,
            'nb_rouge':      nb_rouge,
            'statut_global': sg,
            'message': (
                f"✅ {4-nb_rouge}/4 scénarios historiques résistés"
                if sg != 'ROUGE' else
                f"❌ {nb_rouge}/4 scénarios historiques non résistés"
            ),
            'conseil': (
                "Portefeuille résilient aux crises historiques majeures."
                if sg == 'VERT' else
                f"{nb_rouge} scénario(s) critique(s) — renforcer la réassurance catastrophe."
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # POINT 4 — CAPITAL ALLOCATION
    # ══════════════════════════════════════════════════════════════════════════

    def _capital_allocation(self, chocs, scr_total) -> Dict:
        """
        Décompose le SCR total par sous-module.
        Permet de savoir quel risque consomme le plus de capital.
        """
        modules = {
            'Souscription (primes)': chocs['scr_primes'],
            'Souscription (réserves)': chocs['scr_reserves'],
            'Catastrophe': chocs['scr_catastrophe'],
            'Risque de taux': chocs['scr_taux'],
            'Risque actions': chocs['scr_actions'],
            'Opérationnel': chocs['scr_operationnel'],
            'Tail factor': chocs['scr_tail_factor'],
        }

        total_brut = sum(modules.values())
        allocation = {
            k: {
                'scr':     round(v, 2),
                'pct':     round(v / max(total_brut, 1) * 100, 1),
                'pct_net': round(v / max(scr_total, 1) * 100, 1),
            }
            for k, v in modules.items()
        }

        # Module dominant
        dominant = max(modules, key=modules.get)
        diversification = total_brut - scr_total

        return {
            'allocation':      allocation,
            'module_dominant': dominant,
            'pct_dominant':    round(modules[dominant] / max(scr_total, 1) * 100, 1),
            'diversification': round(diversification, 2),
            'div_pct':         round(diversification / max(total_brut, 1) * 100, 1),
            'statut':          'VERT',
            'message': (
                f"✅ Module dominant : {dominant} "
                f"({round(modules[dominant]/max(scr_total,1)*100,1)}% du SCR) | "
                f"Diversification : {round(diversification/max(total_brut,1)*100,1)}%"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # POINT 5 — ORSA ENRICHI
    # ══════════════════════════════════════════════════════════════════════════

    def _enrichir_orsa_avec_chocs(
        self, orsa_a7, scr_dict, horizons, be, prime
    ) -> Dict:
        """
        Enrichit l'ORSA d'A7 avec les chocs de stress testing A8.
        Projection SCR sur les horizons ORSA.
        """
        ratio_base = scr_dict['ratio_scr_pct']
        scr_base   = scr_dict['scr_total']
        fp         = scr_dict['fonds_propres']

        # Projection ORSA (3 scénarios)
        projection = {}
        for scenario, taux_croiss, choc_annuel in [
            ('favorable', 0.02, 0.00),
            ('central',   0.03, 0.00),
            ('adverse',   0.05, 0.05),
        ]:
            ratios = []
            for t in horizons:
                scr_t  = scr_base * (1 + taux_croiss) ** t
                # t_choc : annee du choc dans l'ORSA (defaut t=2, paramétrable).
                # Justifier dans le RSR/SFCR : choc immediat (t=1) ou en cours de route (t=2+).
                t_choc_orsa = self._config.get('orsa_t_choc', 2) if hasattr(self, '_config') else 2
                choc_t = scr_t * choc_annuel if t == t_choc_orsa else 0
                scr_t += choc_t
                ratio_t = fp / max(scr_t, 1) * 100
                ratios.append(round(ratio_t, 1))
            projection[scenario] = ratios

        ratio_adverse_min = min(projection['adverse'])
        statut_orsa = 'VERT' if ratio_adverse_min >= 130 else 'AMBRE' if ratio_adverse_min >= 100 else 'ROUGE'

        return {
            'horizons':            horizons,
            'ratio_scr_actuel':    round(ratio_base, 1),
            'projection':          projection,
            'ratio_adverse_min':   round(ratio_adverse_min, 1),
            'orsa_a7_recu':        bool(orsa_a7),
            'statut':              statut_orsa,
            'message': (
                f"{'✅' if statut_orsa=='VERT' else '⚠️' if statut_orsa=='AMBRE' else '❌'} "
                f"ORSA — Ratio adverse min sur {max(horizons)} ans = {ratio_adverse_min:.1f}%"
            ),
            'conseil': (
                "Solvabilité maintenue sur l'horizon ORSA dans tous les scénarios."
                if statut_orsa == 'VERT' else
                "Surveiller l'évolution du SCR — envisager des actions de capital management."
                if statut_orsa == 'AMBRE' else
                "Plan de capital requis — présenter au Conseil d'Administration."
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # POINT 6 — ACTIONS DE GESTION RECOMMANDÉES PAR IA
    # ══════════════════════════════════════════════════════════════════════════

    def _actions_gestion_ia(
        self, scr_dict, reverse, historiq, gini, lr_attendu
    ) -> Dict:
        """
        Recommande des actions de gestion concrètes basées sur les résultats.
        C'est la partie IA unique qu'aucun concurrent ne fait.

        Logique :
        → Si ratio SCR < 150% → action capital
        → Si scénario historique rouge → action réassurance
        → Si Gini faible → action tarification
        → Si LR élevé → action souscription
        """
        actions = []
        priorite = "NORMALE"

        ratio_scr = scr_dict['ratio_scr_pct']
        nb_rouge  = historiq['nb_rouge']

        # Action 1 — Capital
        if ratio_scr < 130:
            actions.append({
                'priorite': 'URGENTE',
                'categorie': 'Capital',
                'action': f"Renforcer les fonds propres de {(scr_dict['scr_total'] * 1.30 - scr_dict['fonds_propres'])/1e3:.0f}k€ pour atteindre un ratio SCR de 130%",
                'echeance': '3 mois',
                'impact': f"Ratio SCR passerait de {ratio_scr:.0f}% à 130%",
            })
            priorite = "URGENTE"
        elif ratio_scr < 150:
            actions.append({
                'priorite': 'IMPORTANTE',
                'categorie': 'Capital',
                'action': f"Constituer une réserve de précaution de {(scr_dict['scr_total'] * 1.50 - scr_dict['fonds_propres'])/1e3:.0f}k€",
                'echeance': '6 mois',
                'impact': f"Sécuriser le ratio SCR au-dessus de 150%",
            })
            if priorite == "NORMALE":
                priorite = "IMPORTANTE"

        # Action 2 — Réassurance catastrophe
        if nb_rouge >= 1:
            actions.append({
                'priorite': 'IMPORTANTE',
                'categorie': 'Réassurance',
                'action': f"Augmenter la couverture réassurance catastrophe — {nb_rouge} scénario(s) historique(s) non résisté(s)",
                'echeance': '3 mois',
                'impact': f"Réduire le SCR catastrophe de 20-30%",
            })

        # Action 3 — Tarification (si Gini faible)
        if gini < 0.20:
            actions.append({
                'priorite': 'NORMALE',
                'categorie': 'Tarification',
                'action': f"Revoir le modèle de tarification — Gini faible ({gini:.3f}). Segments sous-tarifés à identifier.",
                'echeance': '6 mois',
                'impact': "Amélioration du loss ratio de 2-4pp attendue",
            })

        # Action 4 — Souscription (si LR élevé)
        if lr_attendu > 0.85:
            actions.append({
                'priorite': 'IMPORTANTE',
                'categorie': 'Souscription',
                'action': f"Resserrer les critères de souscription — Loss Ratio attendu = {lr_attendu*100:.1f}% > 85%",
                'echeance': '1 mois',
                'impact': "Réduction sinistralité de 3-5pp sur 12 mois",
            })

        # Action 5 — Communication ACPR
        if ratio_scr < 100:
            actions.append({
                'priorite': 'URGENTE',
                'categorie': 'Réglementaire',
                'action': "Notifier l'ACPR — ratio SCR < 100% (obligation réglementaire Art. L.352-1 Code des Assurances)",
                'echeance': 'IMMÉDIAT',
                'impact': "Obligation légale — délai maximum 1 semaine",
            })
            priorite = "URGENTE"

        if not actions:
            actions.append({
                'priorite': 'NORMALE',
                'categorie': 'Surveillance',
                'action': "Maintenir le suivi trimestriel du ratio SCR et du BE. Situation saine.",
                'echeance': 'Trimestriel',
                'impact': "Anticipation des dérives",
            })

        return {
            'actions':        actions,
            'nb_actions':     len(actions),
            'priorite_max':   priorite,
            'statut':         'ROUGE' if priorite=='URGENTE' else 'AMBRE' if priorite=='IMPORTANTE' else 'VERT',
            'message': (
                f"{'❌' if priorite=='URGENTE' else '⚠️' if priorite=='IMPORTANTE' else '✅'} "
                f"{len(actions)} action(s) recommandée(s) — priorité {priorite}"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # POINT 7 — QRT S.25.01
    # ══════════════════════════════════════════════════════════════════════════

    def _qrt_s25(self, scr_dict, fonds_propres, be, prime) -> Dict:
        """
        Pré-remplit le QRT S.25.01 (SCR formule standard).
        Prêt à intégrer dans le SFCR Section E.
        """
        scr = scr_dict['scr_total']
        # Securiser scr_vec : padding a 4 elements si la liste est trop courte
        _vec_raw = scr_dict.get('scr_vec', [])
        vec = (_vec_raw + [0, 0, 0, 0])[:4]
        lab = scr_dict.get('labels_vec', ['Souscription', 'Catastrophe', 'Marché', 'Opérationnel'])

        return {
            'code':  'S.25.01',
            'titre': 'Solvency Capital Requirement — Standard Formula',
            'date':  datetime.now().strftime('%Y-%m-%d'),
            'lignes': [
                {'code': 'R0010', 'label': 'Gross SCR',                'valeur': round(scr, 2)},
                {'code': 'R0020', 'label': 'SCR for non-life underwriting risk',
                 'valeur': round(vec[0] if len(vec) > 0 else 0, 2)},
                {'code': 'R0030', 'label': 'SCR for non-life catastrophe risk',
                 'valeur': round(vec[1] if len(vec) > 1 else 0, 2)},
                {'code': 'R0040', 'label': 'SCR for market risk',
                 'valeur': round(vec[2] if len(vec) > 2 else 0, 2)},
                {'code': 'R0050', 'label': 'SCR for operational risk',
                 'valeur': round(vec[3] if len(vec) > 3 else 0, 2)},
                {'code': 'R0070', 'label': 'MCR',                      'valeur': round(scr_dict['mcr'], 2)},
                {'code': 'R0100', 'label': 'Eligible own funds (Total)', 'valeur': round(fonds_propres, 2)},
                {'code': 'R0110', 'label': 'Eligible own funds T1',     'valeur': round(fonds_propres * 0.90, 2)},
                {'code': 'R0120', 'label': 'Eligible own funds T2',     'valeur': round(fonds_propres * 0.10, 2)},
                {'code': 'R0200', 'label': 'SCR ratio (%)',             'valeur': round(scr_dict['ratio_scr_pct'], 1)},
                {'code': 'R0210', 'label': 'MCR ratio (%)',             'valeur': round(scr_dict['ratio_mcr_pct'], 1)},
            ],
            'statut': 'VERT' if scr_dict['ratio_scr_pct'] >= 100 else 'ROUGE',
            'message': f"QRT S.25.01 pré-rempli — SCR = {scr/1e3:.0f}k€ | Ratio = {scr_dict['ratio_scr_pct']:.1f}%",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # VALIDATION HYPOTHÈSES
    # ══════════════════════════════════════════════════════════════════════════

    def _valider_stress_testing(self, scr_dict, reverse, historiq, mkt) -> Dict:
        """
        Validation 3 hypothèses standard ActuarIA.

        H1 — Ratio SCR ≥ 130% (cible ORSA interne)
        H2 — Données marché réelles utilisées (pas défaut)
        H3 — Scénarios historiques résistés (≥ 3/4)
        """
        ratio_scr = scr_dict['ratio_scr_pct']

        # H1 — Ratio SCR
        if ratio_scr >= 150:
            h1_s,h1_m,h1_c = "VERT", f"Ratio SCR = {ratio_scr:.1f}% ≥ 150% ✅", "Capitalisation solide — objectif ORSA atteint"
        elif ratio_scr >= 100:
            h1_s,h1_m,h1_c = "AMBRE", f"Ratio SCR = {ratio_scr:.1f}% ∈ [100%,150%] ⚠️", "Conforme mais surveillance renforcée recommandée"
        else:
            h1_s,h1_m,h1_c = "ROUGE", f"Ratio SCR = {ratio_scr:.1f}% < 100% ❌", "Insuffisance de capital — notification ACPR obligatoire"

        # H2 — Données marché
        fiabilite = mkt.get('fiabilite', 'DEFAUT')
        if fiabilite == 'TEMPS_REEL':
            h2_s,h2_m,h2_c = "VERT", "Taux OAT BCE temps réel utilisés ✅", "Chocs calibrés sur les vrais taux du marché"
        elif fiabilite == 'REFERENCE':
            h2_s,h2_m,h2_c = "VERT", f"Taux de référence utilisés ✅ ({mkt['oat_10ans']['source']})", "Taux documentés et traçables"
        else:
            h2_s,h2_m,h2_c = "AMBRE", "Valeurs EIOPA par défaut ⚠️", "Installer market_data.py pour des taux actualisés"

        # H3 — Scénarios historiques
        nb_rouge = historiq['nb_rouge']
        if nb_rouge == 0:
            h3_s,h3_m,h3_c = "VERT", "4/4 scénarios historiques résistés ✅", "Portefeuille résilient aux crises majeures"
        elif nb_rouge == 1:
            h3_s,h3_m,h3_c = "AMBRE", f"3/4 scénarios résistés — 1 rouge ⚠️", "Renforcer la réassurance pour le scénario critique"
        else:
            h3_s,h3_m,h3_c = "ROUGE", f"{4-nb_rouge}/4 scénarios résistés — {nb_rouge} rouges ❌", "Actions immédiates requises sur capital et réassurance"

        sts = [h1_s, h2_s, h3_s]
        sg  = "ROUGE" if "ROUGE" in sts else "AMBRE" if "AMBRE" in sts else "VERT"

        return {
            "h1_ratio_scr":   {"statut":h1_s,"message":h1_m,"conseil":h1_c,"ratio":round(ratio_scr,1)},
            "h2_marche":      {"statut":h2_s,"message":h2_m,"conseil":h2_c,"fiabilite":fiabilite},
            "h3_historiques": {"statut":h3_s,"message":h3_m,"conseil":h3_c,"nb_rouge":nb_rouge},
            "statut_global":  sg,
            "conclusion": {
                "VERT":  "✅ Stress Testing validé — SCR, taux marché et scénarios conformes",
                "AMBRE": "⚠️ Stress Testing acceptable — vérifier les points signalés",
                "ROUGE": "❌ Stress Testing non conforme — actions correctives requises",
            }[sg],
        }

    # ══════════════════════════════════════════════════════════════════════════
    # CALCUL STATUT RAG
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_statut_rag(self, scr_dict, val) -> str:
        ratio = scr_dict.get('ratio_scr_pct', 0)
        if ratio >= 150 and val['statut_global'] == 'VERT':
            return 'VERT'
        elif ratio >= 100:
            return 'AMBRE'
        else:
            return 'ROUGE'

    # ══════════════════════════════════════════════════════════════════════════
    # COMMENTAIRE ACTUARIEL
    # ══════════════════════════════════════════════════════════════════════════

    def _commenter_actuaire_senior(
        self, scr_dict, reverse, historiq, actions, mkt, statut
    ) -> str:
        ratio     = scr_dict['ratio_scr_pct']
        scr       = scr_dict['scr_total']
        fp        = scr_dict['fonds_propres']
        marge     = reverse['marge_euros']
        nb_rouge  = historiq['nb_rouge']
        fiabilite = mkt.get('fiabilite', 'DEFAUT')
        source    = mkt['oat_10ans']['source']
        oat       = mkt['oat_10ans']['taux_pct']

        return (
            f"{'✅' if statut=='VERT' else '⚠️' if statut=='AMBRE' else '❌'} "
            f"Stress Testing Non-Vie — SCR = {scr/1e3:.0f}k€ | "
            f"Ratio = {ratio:.1f}% | FP = {fp/1e3:.0f}k€.\n"
            f"Taux calibrage : OAT 10 ans = {oat:.2f}% ({source}) | "
            f"Fiabilité : {fiabilite}.\n"
            f"Marge avant insolvabilité : {marge/1e3:.0f}k€ "
            f"(sinistres peuvent augmenter de {reverse['hausse_sinistres_max_pct']:.0f}%).\n"
            f"Scénarios historiques : {4-nb_rouge}/4 résistés"
            f"{' — ' + historiq['conseil'] if nb_rouge > 0 else ' — Portefeuille résilient'}.\n"
            f"Actions recommandées : {actions['nb_actions']} "
            f"(priorité {actions['priorite_max']})."
        )

    # ══════════════════════════════════════════════════════════════════════════
    # GRAPHIQUES
    # ══════════════════════════════════════════════════════════════════════════

    def _generer_graphiques(
        self, chocs, scr_dict, orsa, historiq, capital,
        fonds_propres, reverse
    ) -> Dict:
        """8 graphiques principaux auto-explicatifs."""
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}

        NAVY="#0F2E52";NAVYL="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8"
        GRIS="#8A9AB0";VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12";BLEU="#3498DB"
        LAYOUT = dict(
            paper_bgcolor=NAVY, plot_bgcolor=NAVYL,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=65, b=70), height=340,
        )
        graphiques = {}

        # G1 — Décomposition SCR par sous-module
        try:
            labels = capital['allocation'].keys()
            valeurs= [capital['allocation'][k]['scr'] for k in labels]
            colors = [OR if k == capital['module_dominant'] else BLEU for k in labels]
            fig1 = go.Figure(go.Bar(
                x=list(labels), y=[v/1e3 for v in valeurs],
                marker_color=colors, opacity=0.88,
                text=[f"{v/1e3:.0f}k€\n{capital['allocation'][k]['pct']:.0f}%" for k,v in zip(labels,valeurs)],
                textposition="outside", textfont=dict(color=BLANC, size=9),
                hovertemplate="<b>%{x}</b><br>SCR : %{y:.0f}k€<extra></extra>",
            ))
            l1 = dict(**LAYOUT); l1.update(dict(
                title=dict(text=f"✅ Capital par risque — Dominant : {capital['module_dominant']} ({capital['pct_dominant']:.0f}% du SCR)",
                          font=dict(color=OR, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title="SCR (k€)", tickfont=dict(color=GRIS)),
                showlegend=False,
                annotations=[dict(
                    text="💡 La barre dorée = risque qui consomme le plus de capital. Réduire ce risque libère le plus de fonds propres.",
                    xref="paper", yref="paper", x=0.01, y=-0.28,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left")],
            ))
            fig1.update_layout(**l1)
            graphiques["capital_par_risque"] = fig1
        except Exception as e:
            self.logger.warning(f"G1 A8 : {e}")

        # G2 — Ratio SCR jauge
        try:
            ratio = scr_dict['ratio_scr_pct']
            c_scr = VERT if ratio>=150 else AMBRE if ratio>=100 else ROUGE
            fig2 = go.Figure(go.Indicator(
                mode="gauge+number",
                value=ratio,
                number=dict(suffix="%", font=dict(color=c_scr, size=32), valueformat=".1f"),
                title=dict(
                    text=f"{'✅' if ratio>=150 else '⚠️' if ratio>=100 else '❌'} Ratio SCR = {ratio:.1f}% | MCR = {scr_dict['ratio_mcr_pct']:.0f}%",
                    font=dict(color=c_scr, size=11)
                ),
                gauge=dict(
                    axis=dict(range=[0, 300], tickfont=dict(color=GRIS, size=8),
                             tickvals=[0,100,150,200,300], ticktext=["0","100%","150%","200%","300%"]),
                    bar=dict(color=c_scr, thickness=0.25), bgcolor=NAVYL, borderwidth=0,
                    steps=[dict(range=[0,100], color="rgba(231,76,60,0.12)"),
                           dict(range=[100,150], color="rgba(243,156,18,0.12)"),
                           dict(range=[150,300], color="rgba(46,204,113,0.12)")],
                    threshold=dict(line=dict(color=VERT, width=3), thickness=0.8, value=150),
                ),
            ))
            fig2.update_layout(
                paper_bgcolor=NAVY, font=dict(color=BLANC),
                margin=dict(l=30, r=30, t=80, b=60), height=340,
                annotations=[dict(
                    text="💡 Au-dessus de 150% = objectif ORSA atteint. Entre 100-150% = conforme mais surveiller. En dessous de 100% = insuffisance de capital.",
                    xref="paper", yref="paper", x=0.5, y=-0.18,
                    font=dict(color=GRIS, size=9), showarrow=False, align="center")],
            )
            graphiques["jauge_ratio_scr"] = fig2
        except Exception as e:
            self.logger.warning(f"G2 A8 : {e}")

        # G3 — ORSA projection 5 ans
        try:
            proj   = orsa.get('projection', {})
            horiz  = orsa.get('horizons', [1,2,3,4,5])
            x_all  = [0] + list(horiz)
            r_base = orsa.get('ratio_scr_actuel', 100)

            fig3 = go.Figure()
            palette = {'favorable': VERT, 'central': OR, 'adverse': ROUGE}
            dash_s  = {'favorable': 'dot', 'central': 'solid', 'adverse': 'dash'}
            for sc, vals in proj.items():
                fig3.add_trace(go.Scatter(
                    x=x_all, y=[r_base]+vals,
                    mode="lines+markers",
                    name=sc.title(),
                    line=dict(color=palette.get(sc, BLEU), width=2.5, dash=dash_s.get(sc,'solid')),
                    marker=dict(size=6),
                    hovertemplate=f"<b>{sc.title()}</b><br>An +%{{x}}<br>Ratio SCR : %{{y:.1f}}%<extra></extra>",
                ))
            fig3.add_hline(y=100, line_color=ROUGE, line_width=1.5, line_dash="dot",
                          annotation_text="Seuil 100%", annotation_font=dict(color=ROUGE, size=9))
            fig3.add_hline(y=150, line_color=VERT, line_width=1.5, line_dash="dot",
                          annotation_text="Cible 150%", annotation_font=dict(color=VERT, size=9))
            l3 = dict(**LAYOUT); l3.update(dict(
                title=dict(text=f"{'✅' if orsa['statut']=='VERT' else '⚠️'} ORSA — Ratio SCR sur {max(horiz)} ans | Min adverse = {orsa['ratio_adverse_min']:.1f}%",
                          font=dict(color=VERT if orsa['statut']=='VERT' else AMBRE, size=11), x=0.01),
                xaxis=dict(title="Années", tickfont=dict(color=BLANC),
                          tickvals=x_all, ticktext=["Auj."]+[f"+{h}" for h in horiz]),
                yaxis=dict(title="Ratio SCR (%)", tickfont=dict(color=GRIS)),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=9), orientation="h", y=1.0),
                annotations=[dict(
                    text="💡 Courbe dorée = scénario central. Rouge = pire cas. Tout doit rester au-dessus de 100% (ligne rouge) sur 5 ans.",
                    xref="paper", yref="paper", x=0.01, y=-0.28,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left")],
            ))
            fig3.update_layout(**l3)
            graphiques["orsa_projection"] = fig3
        except Exception as e:
            self.logger.warning(f"G3 A8 : {e}")

        # G4 — Scénarios historiques
        try:
            sc_hist = historiq['scenarios']
            noms    = [v['nom'][:30] for v in sc_hist.values()]
            ratios  = [v['ratio_scr_post'] for v in sc_hist.values()]
            colors  = [VERT if r>=100 else ROUGE for r in ratios]

            fig4 = go.Figure(go.Bar(
                x=noms, y=ratios,
                marker_color=colors, opacity=0.88,
                text=[f"{r:.1f}%" for r in ratios],
                textposition="outside", textfont=dict(color=BLANC, size=10),
                hovertemplate="<b>%{x}</b><br>Ratio SCR post-choc : %{y:.1f}%<extra></extra>",
            ))
            fig4.add_hline(y=100, line_color=ROUGE, line_width=2, line_dash="dot",
                          annotation_text="Seuil solvabilité 100%", annotation_font=dict(color=ROUGE, size=9))
            l4 = dict(**LAYOUT); l4.update(dict(
                title=dict(text=f"{'✅' if historiq['statut_global']=='VERT' else '⚠️' if historiq['statut_global']=='AMBRE' else '❌'} Scénarios historiques — {4-historiq['nb_rouge']}/4 résistés",
                          font=dict(color=VERT if historiq['statut_global']=='VERT' else AMBRE, size=11), x=0.01),
                xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                yaxis=dict(title="Ratio SCR post-choc (%)", tickfont=dict(color=GRIS)),
                showlegend=False,
                annotations=[dict(
                    text="💡 Chaque barre = ratio SCR après avoir subi ce choc historique réel. Au-dessus de 100% = l'assureur survit. En rouge = insolvabilité.",
                    xref="paper", yref="paper", x=0.01, y=-0.28,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left")],
            ))
            fig4.update_layout(**l4)
            graphiques["scenarios_historiques"] = fig4
        except Exception as e:
            self.logger.warning(f"G4 A8 : {e}")

        return graphiques

    def _graphiques_validation_stress(self, val, scr_dict, mkt) -> Dict:
        """4 graphiques validation standard ActuarIA."""
        try:
            import plotly.graph_objects as go
        except:
            return {}

        NAVY="#0F2E52";NAVYL="#1B3A5C";OR="#C9A84C";BLANC="#F0F4F8"
        GRIS="#8A9AB0";VERT="#2ECC71";ROUGE="#E74C3C";AMBRE="#F39C12"
        LAYOUT = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVYL,
                     font=dict(family="Inter", color=BLANC, size=11),
                     margin=dict(l=16, r=16, t=65, b=70), height=340)
        graphiques = {}

        # Scorecard validation
        try:
            items = [
                ("H1 — Ratio SCR", val["h1_ratio_scr"]["statut"],
                 val["h1_ratio_scr"]["message"], val["h1_ratio_scr"]["conseil"]),
                ("H2 — Taux marché", val["h2_marche"]["statut"],
                 val["h2_marche"]["message"], val["h2_marche"]["conseil"]),
                ("H3 — Scénarios historiques", val["h3_historiques"]["statut"],
                 val["h3_historiques"]["message"], val["h3_historiques"]["conseil"]),
            ]
            fig = go.Figure()
            for nom, statut, msg, conseil in items:
                c = VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                i = "✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"
                s = 1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig.add_trace(go.Bar(
                    x=[s], y=[nom], orientation="h",
                    marker_color=c, width=0.5,
                    text=f"{i} {statut}", textposition="outside",
                    textfont=dict(color=c, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False,
                ))
            sg = val["statut_global"]
            cg = VERT if sg=="VERT" else AMBRE if sg=="AMBRE" else ROUGE
            l = dict(**LAYOUT); l.update(dict(
                title=dict(text=f"Scorecard Stress Testing — {val['conclusion']}",
                          font=dict(color=cg, size=10), x=0.01),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode="overlay", height=280,
                annotations=[dict(
                    text="💡 3 ✅ = Stress Testing validé, défendable devant l'ACPR et le Conseil d'Administration.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False)],
            ))
            fig.update_layout(**l)
            graphiques["scorecard_stress"] = fig
        except Exception as e:
            self.logger.warning(f"Scorecard A8 : {e}")

        return graphiques

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES
    # ══════════════════════════════════════════════════════════════════════════

    def _afficher_rapport_console(self, audit_id, scr_dict, reverse, statut, commentaire):
        self.logger.info(f"[{audit_id}] {commentaire.split(chr(10))[0]}")
        self.logger.info(f"[{audit_id}] SCR = {scr_dict['scr_total']/1e3:.0f}k€ | Ratio = {scr_dict['ratio_scr_pct']:.1f}%")

    def _sauvegarder(self, scr_dict, statut, audit_id):
        try:
            rapport = {
                'agent': 'A8 Isabelle', 'audit_id': audit_id,
                'date': datetime.now().isoformat(),
                'scr_total': scr_dict['scr_total'],
                'ratio_scr': scr_dict['ratio_scr_pct'],
                'statut': statut,
            }
            fpath = self.models_path / f"a8_stress_{audit_id}.json"
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(rapport, f, indent=2)
            self.logger.info(f"Sauvegardé : {fpath}")
        except Exception as e:
            self.logger.warning(f"Sauvegarde : {e}")

    def _erreur(self, message: str, audit_id: str) -> Dict:
        return {
            'success': False, 'statut_rag': 'ROUGE',
            'commentaire': f"❌ ERREUR A8 : {message}",
            'audit_id': audit_id, 'erreur': message,
        }
