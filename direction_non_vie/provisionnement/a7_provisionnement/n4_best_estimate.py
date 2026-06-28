# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n4_best_estimate.py  —  Best Estimate S2 + SCR provisions
# =============================================================================
#
#  Références réglementaires
#  -------------------------
#  Directive Solvabilité II (2009/138/CE), Art. 77 :
#    Best Estimate = espérance de la valeur actuelle des flux futurs
#
#  Règlement Délégué (UE) 2015/35, Art. 105 :
#    SCR provisions Non-Vie = formule standard par LoB
#
#  EIOPA Guidelines on valuation of technical provisions (2014) :
#    TP.5.26 — distribution log-normale pour IBNR
#    Statut : CV < 10% VERT | 10-20% AMBRE | > 20% ROUGE
#
#  Formules implémentées
#  ---------------------
#
#  Best Estimate (Art. 77)
#  ────────────────────────
#  Combinaison pondérée des méthodes actuarielles validées :
#
#      BE = Σ_{m ∈ M_inc} w_m × R_m
#
#  où  M_inc  = méthodes avec score ≥ seuil_score (défaut 60)
#      w_m    = s_m / Σ s_k   (poids proportionnels aux scores N2)
#      R_m    = réserve estimée par la méthode m
#
#  Percentiles log-normale (QIS5 TP.5.26)
#  ────────────────────────────────────────
#  σ = σ_Mack (incertitude de réserve totale Mack 1993)
#
#      σ_LN = √(ln(1 + (σ/BE)²))
#      μ_LN = ln(BE) - σ²_LN / 2
#      P_α  = exp(μ_LN + z_α × σ_LN)
#
#  SCR provisions formule standard (Art. 105 S2)
#  ───────────────────────────────────────────────
#  Pour une seule LoB :
#
#      SCR_prov(LoB) = 3 × σ(LoB) × BE(LoB)
#
#  Pour plusieurs LoB, agrégation avec matrice de corrélation EIOPA :
#
#      SCR_NL = √(Σ_{i,j} ρ_{ij} × SCR_i × SCR_j)
#
#  où σ(LoB) est le facteur de volatilité EIOPA (Annexe II, Rgt 2015/35)
#  et ρ_{ij} la corrélation entre LoB i et j (Annexe IV, Rgt 2015/35).
#
# =============================================================================

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

from .config.lob_config import get_lob_config, get_sigma_eiopa, CORRELATION_EIOPA

logger = logging.getLogger('actuaria.a7')


class BestEstimateS2:
    """
    Calcule le Best Estimate S2 conforme Art. 77 avec :
      · Sélection des méthodes validées (score ≥ seuil_score)
      · Poids dynamiques proportionnels aux scores N2
      · Percentiles log-normale (QIS5 TP.5.26)
      · SCR provisions formule standard (Art. 105 S2)
      · Sensibilités aux hypothèses clés
      · Jugement actuariel documenté (style rapport ORSA)
    """

    def calculer(
        self,
        n2:           Dict,
        n3:           Dict,
        C:            np.ndarray,
        lob:          str   = 'generique',
        seuil_score:  int   = 60,
    ) -> Dict:
        """
        Calcule le Best Estimate S2 et le SCR provisions.

        Parameters
        ----------
        n2 : dict
            Résultats de HypothesesValidator.valider() — scores, statuts H1-H4.
        n3 : dict
            Résultats des méthodes actuarielles N3 — réserves par méthode.
        C : np.ndarray
            Triangle cumulé (pour calculs complémentaires).
        lob : str
            Ligne d'activité — pilote σ(LoB) EIOPA pour le SCR.
        seuil_score : int
            Score minimum pour inclure une méthode dans le BE (défaut 60).

        Returns
        -------
        dict conforme standard ActuarIA.
        """
        scores = n2.get('scores_confiance', {})
        cfg    = get_lob_config(lob)

        # ── Réserves par méthode ──────────────────────────────────────────────
        cl_res   = n3['chain_ladder']['reserve_totale']
        mack_res = n3['mack']['reserve_best_estimate']
        bf_res   = n3['bf']['reserve_totale']
        cc_res   = n3['cape_cod']['reserve_totale']
        sigma    = n3['mack']['sigma_total']
        boot     = n3.get('bootstrap', {})

        # Clé 'mack_1993' dans les scores → mapper vers 'mack'
        score_map = {
            'chain_ladder':         scores.get('chain_ladder', 70),
            'mack':                 scores.get('mack_1993', scores.get('mack', 70)),
            'bornhuetter_ferguson': scores.get('bornhuetter_ferguson', 70),
            'cape_cod':             scores.get('cape_cod', 70),
        }

        methodes_dispo = {
            'chain_ladder':         cl_res,
            'mack':                 mack_res,
            'bornhuetter_ferguson': bf_res,
            'cape_cod':             cc_res,
        }

        # ── 1. Sélection des méthodes validées ────────────────────────────────
        methodes_incluses: Dict[str, Tuple[float, int]] = {}
        methodes_exclues:  Dict[str, Tuple[float, int]] = {}

        for m, r in methodes_dispo.items():
            s = score_map.get(m, 70)
            if s >= seuil_score and r > 0:
                methodes_incluses[m] = (r, s)
            else:
                methodes_exclues[m]  = (r, s)

        # Garde-fou : si tout exclu → garder Mack et BF par défaut
        if not methodes_incluses:
            methodes_incluses = {
                'mack': (mack_res, 50),
                'bornhuetter_ferguson': (bf_res, 50),
            }
            logger.warning(
                "BE N4 : toutes les méthodes exclues (score < seuil). "
                "Fallback sur Mack + BF avec score=50."
            )

        # Forcer l'inclusion de la méthode recommandée par N2
        # même si son score est bas (le jugement actuariel prime sur le score mécanique)
        methode_rec_check = n2.get('methode_recommandee', '').lower().replace(' ', '_')
        _rec_map_check = {
            'bornhuetter_ferguson': 'bornhuetter_ferguson',
            'bf': 'bornhuetter_ferguson',
            'mack': 'mack', 'mack_1993': 'mack',
            'chain_ladder': 'chain_ladder',
            'cape_cod': 'cape_cod',
        }
        methode_rec_norm_check = _rec_map_check.get(methode_rec_check, '')
        if methode_rec_norm_check and methode_rec_norm_check not in methodes_incluses:
            # La méthode recommandée a été exclue par le seuil de score
            # On la force avec un score de 70 (score de référence)
            reserve_rec = methodes_dispo.get(methode_rec_norm_check, 0)
            if reserve_rec > 0:
                methodes_incluses[methode_rec_norm_check] = (reserve_rec, 70)
                if methode_rec_norm_check in methodes_exclues:
                    del methodes_exclues[methode_rec_norm_check]
                logger.info(
                    f"BE N4 : méthode recommandée '{methode_rec_norm_check}' "
                    f"forcée dans les incluses malgré score bas."
                )

        # ── 2. Poids dynamiques — méthode recommandée dominante ──────────────
        # Si une méthode est recommandée par N2 (ex: BF car H1 rejetée),
        # elle reçoit un poids minimum de 50% pour refléter le jugement actuariel.
        # Les autres méthodes se partagent le reste proportionnellement à leurs scores.
        methode_rec = n2.get('methode_recommandee', '')
        # Normaliser le nom de la méthode recommandée
        _rec_map = {
            'bornhuetter_ferguson': 'bornhuetter_ferguson',
            'bf': 'bornhuetter_ferguson',
            'mack': 'mack',
            'mack_1993': 'mack',
            'chain_ladder': 'chain_ladder',
            'cape_cod': 'cape_cod',
        }
        methode_rec_norm = _rec_map.get(methode_rec.lower().replace(' ','_'), '')

        total_scores = sum(s for _, s in methodes_incluses.values())
        poids_bruts = {
            m: s / max(total_scores, 1)
            for m, (_, s) in methodes_incluses.items()
        }

        # Appliquer bonus méthode recommandée si présente dans les incluses
        if methode_rec_norm and methode_rec_norm in methodes_incluses:
            POIDS_MIN_REC = 0.50  # Poids minimum garanti à la méthode recommandée
            poids_rec     = max(poids_bruts.get(methode_rec_norm, 0), POIDS_MIN_REC)
            reste         = 1.0 - poids_rec
            autres        = {m: v for m, v in poids_bruts.items() if m != methode_rec_norm}
            total_autres  = sum(autres.values())
            poids = {methode_rec_norm: round(poids_rec, 4)}
            if total_autres > 0:
                for m, v in autres.items():
                    poids[m] = round(v / total_autres * reste, 4)
            else:
                poids = {methode_rec_norm: 1.0}
        else:
            poids = {m: round(v, 4) for m, v in poids_bruts.items()}

        # Normaliser pour que la somme = 1.0 exactement
        total_poids = sum(poids.values())
        if total_poids > 0:
            poids = {m: round(v / total_poids, 4) for m, v in poids.items()}

        # ── 3. Best Estimate (Art. 77) ────────────────────────────────────────
        # BE = Σ w_m × R_m
        be = float(sum(
            poids[m] * r
            for m, (r, _) in methodes_incluses.items()
        ))

        # ── 4. CV inter-méthodes ──────────────────────────────────────────────
        reserves_val = [r for r, _ in methodes_incluses.values()]
        cv_inter = (
            float(np.std(reserves_val) / max(np.mean(reserves_val), 1e-9) * 100)
            if len(reserves_val) > 1 else 0.0
        )

        # ── 5. Percentiles log-normale (QIS5 TP.5.26) ────────────────────────
        if sigma > 0 and be > 0:
            cv_ln  = sigma / be
            s2_ln  = np.log(1.0 + cv_ln ** 2)
            s_ln   = np.sqrt(s2_ln)
            m_ln   = np.log(be) - s2_ln / 2.0

            p75  = float(np.exp(m_ln + 0.6745 * s_ln))
            p90  = float(np.exp(m_ln + 1.2816 * s_ln))
            p995 = float(np.exp(m_ln + 2.5758 * s_ln))
        else:
            p75 = p90 = p995 = be

        # ── 6. SCR provisions formule standard (Art. 105 S2) ──────────────────
        scr = self._calculer_scr(be, lob, cfg)

        # ── 7. Sensibilités ───────────────────────────────────────────────────
        sensibilites = self._calculer_sensibilites(
            methodes_incluses, poids, boot, be
        )

        # ── 8. Statut ─────────────────────────────────────────────────────────
        if cv_inter < 5.0:
            statut = 'VERT'
        elif cv_inter < 15.0:
            statut = 'AMBRE'
        else:
            statut = 'ROUGE'

        # ── 9. Jugement actuariel (alertes, recommandations, avis) ───────────
        alertes_jugement = []
        recommandations  = []

        # Reprendre les alertes de N2
        for a in n2.get('alertes', []):
            alertes_jugement.append(str(a))

        # Recommandations depuis la méthode recommandée
        methode_rec = n2.get('methode_recommandee', 'chain_ladder')
        raison_rec  = n2.get('raison_recommandation', '')
        if raison_rec:
            # Tronquer proprement à la dernière phrase complète
            _raison_short = raison_rec[:300]
            if len(raison_rec) > 300 and '.' in _raison_short:
                _raison_short = _raison_short[:_raison_short.rfind('.')+1]
            recommandations.append(f"Méthode principale : {methode_rec.replace('_',' ').title()} — {_raison_short}")

        # Recommandation back-testing si dispo
        bt_statut_val = n3.get('backtesting', {}).get('statut', '')
        if bt_statut_val == 'ROUGE':
            recommandations.append(
                "Back-testing ROUGE — réviser les hypothèses de provisionnement N-1/N-2 "
                "avant inscription au bilan S2."
            )

        # Recommandation effets calendaire si dispo
        bz_statut_val = n3.get('barnett_zehnwirth', {}).get('statut', '')
        if bz_statut_val in ('ROUGE', 'AMBRE'):
            recommandations.append(
                "Effets calendaire détectés — documenter la cause (inflation, changement législatif) "
                "dans la note méthodologique S2."
            )

        # Avis actuariel global
        h1_ok = n2.get('h1_independance', {}).get('ok', True)
        if statut == 'ROUGE' or (not h1_ok and bt_statut_val == 'ROUGE'):
            avis_actuariel = 'FAVORABLE SOUS RÉSERVE — révisions requises avant bilan S2'
        elif statut == 'AMBRE' or not h1_ok:
            avis_actuariel = 'FAVORABLE SOUS RÉSERVE — points de vigilance à documenter'
        else:
            avis_actuariel = "FAVORABLE — Best Estimate conforme aux exigences Solvabilité 2"

        # ── 9. Jugement actuariel documenté ───────────────────────────────────
        jugement = self._documenter_jugement(
            methodes_incluses, methodes_exclues, poids,
            be, cv_inter, n2, n3, statut, scr, cfg
        )

        msg = (
            f"BE S2 = {be:,.0f}€ · P90 = {p90:,.0f}€ · "
            f"CV = {cv_inter:.1f}% · σ = {sigma:,.0f}€ · "
            f"SCR_prov = {scr['scr_provisions']:,.0f}€"
        )
        logger.info(msg)

        return {
            # Best Estimate
            'best_estimate':         round(be,     0),

            # Percentiles log-normale (QIS5 TP.5.26)
            'reserve_p75':           round(p75,    0),
            'reserve_p90':           round(p90,    0),
            'reserve_p99_5':         round(p995,   0),

            # Incertitude Mack
            'sigma_mack':            round(sigma,  0),
            'cv_inter_methodes':     round(cv_inter, 2),

            # Méthodes
            'methodes_incluses':     list(methodes_incluses.keys()),
            'methodes_exclues':      list(methodes_exclues.keys()),
            'poids':                 poids,

            # SCR formule standard
            'scr':                   scr,

            # Sensibilités
            'sensibilites':          sensibilites,

            # Jugement
            'jugement':              jugement,

            # Statut
            'statut':                statut,
            'message':               msg,

            # Jugement actuariel — alimenté depuis les alertes N2/N4
            'alertes':               alertes_jugement,
            'recommandations':       recommandations,
            'avis_actuariel':        avis_actuariel,

            # Alias pour compatibilité rapport
            'scr_prov':              scr['scr_provisions'],
            'methode_facteurs':      methode_rec,
        }

    # =========================================================================
    #  SCR PROVISIONS FORMULE STANDARD (Art. 105 S2)
    # =========================================================================

    def _calculer_scr(
        self,
        be:  float,
        lob: str,
        cfg: Dict,
    ) -> Dict:
        """
        SCR provisions formule standard pour une LoB unique.

        Art. 105(2) Règlement Délégué 2015/35 :

            SCR_prov(LoB) = 3 × σ(LoB) × BE(LoB)

        σ(LoB) = facteur de volatilité EIOPA (Annexe II, Rgt 2015/35).
        Le facteur 3 correspond au quantile 99.5% d'une loi normale.

        Pour plusieurs LoB : agrégation avec matrice corrélation EIOPA.
        Ici, calcul mono-LoB — l'agrégation multi-LoB est prévue
        au niveau du tableau de bord consolidé.

        Returns
        -------
        dict avec scr_provisions, sigma_eiopa, lob, methode.
        """
        sigma_eiopa  = get_sigma_eiopa(lob)
        scr_prov     = 3.0 * sigma_eiopa * be

        # Ratio SCR/BE : signal de niveau de risque
        ratio = scr_prov / max(be, 1e-9)

        return {
            'scr_provisions':   round(scr_prov,    0),
            'sigma_eiopa':      sigma_eiopa,
            'ratio_scr_be':     round(ratio,        4),
            'lob':              lob,
            'lob_label':        cfg.get('label', lob),
            'methode':          'Formule standard Art. 105 S2 (Rgt 2015/35)',
            'message': (
                f"SCR_prov = 3 × {sigma_eiopa:.0%} × {be:,.0f}€ "
                f"= {scr_prov:,.0f}€ "
                f"(ratio SCR/BE = {ratio:.1%})"
            ),
        }

    # =========================================================================
    #  SENSIBILITÉS
    # =========================================================================

    def _calculer_sensibilites(
        self,
        methodes_incluses: Dict,
        poids:             Dict,
        boot:              Dict,
        be:                float,
    ) -> Dict:
        """
        Analyse de sensibilité du BE aux hypothèses clés.

        Tests :
        · Exclusion de chaque méthode tour à tour
        · Fourchette Bootstrap (IC 95%)
        """
        sensibilites: Dict[str, float] = {}

        # Sensibilité à l'exclusion de chaque méthode
        for m_exclu in methodes_incluses:
            autres = {k: v for k, v in methodes_incluses.items() if k != m_exclu}
            if autres:
                tot_s    = sum(s for _, s in autres.values())
                p_autres = {k: s / max(tot_s, 1) for k, (_, s) in autres.items()}
                be_sans  = sum(p_autres[k] * autres[k][0] for k in autres)
                sensibilites[f'sans_{m_exclu}'] = round(be_sans, 0)

        # Fourchette Bootstrap
        if boot.get('be_bootstrap', 0) > 0:
            sensibilites['boot_ic_inf'] = round(boot.get('ic_95_inf', be * 0.85), 0)
            sensibilites['boot_ic_sup'] = round(boot.get('ic_95_sup', be * 1.15), 0)
            sensibilites['boot_p90']    = round(boot.get('p90', be * 1.10), 0)
            sensibilites['boot_p99_5']  = round(boot.get('p99_5', be * 1.30), 0)

        return sensibilites

    # =========================================================================
    #  JUGEMENT ACTUARIEL DOCUMENTÉ
    # =========================================================================

    def _documenter_jugement(
        self,
        incluses:  Dict,
        exclues:   Dict,
        poids:     Dict,
        be:        float,
        cv:        float,
        n2:        Dict,
        n3:        Dict,
        statut:    str,
        scr:       Dict,
        cfg:       Dict,
    ) -> str:
        """
        Génère le texte de jugement actuariel documenté.

        Format conforme à un rapport actuaire désigné ACPR :
        sections numérotées, décision explicite, recommandations.
        """
        methode_rec = n2.get('methode_recommandee', 'mack')
        raison_rec  = n2.get('raison_recommandation', '')
        raison_cl   = n2.get('raison_cl', '')
        h1          = n2.get('h1_independance', {})
        h2          = n2.get('h2_stabilite', {})
        h3          = n2.get('h3_apriori_bf', {})
        h4          = n2.get('h4_homosc_bootstrap', {})
        lob_label   = cfg.get('label', 'Non précisée')
        date_str    = datetime.now().strftime('%d/%m/%Y')
        sigma       = n3['mack']['sigma_total']
        p90         = n3['mack']['reserve_p90']
        p995        = n3['mack']['reserve_p99_5']

        lignes = [
            f"JUGEMENT ACTUARIEL — {date_str}",
            f"Branche : {lob_label}",
            "─" * 60,
            "",
            "1. MÉTHODES RETENUES ET EXCLUES",
            "─" * 40,
        ]

        for m, (r, s) in incluses.items():
            lignes.append(
                f"  ✅ {m.replace('_', ' ').title():30s} "
                f"réserve={r:>14,.0f}€  poids={poids.get(m, 0):.0%}  "
                f"score={s}/100"
            )
        for m, (r, s) in exclues.items():
            lignes.append(
                f"  ❌ {m.replace('_', ' ').title():30s} "
                f"exclu  (score={s}/100 < seuil)"
            )

        lignes += [
            "",
            "2. VALIDATION DES HYPOTHÈSES ACTUARIELLES",
            "─" * 40,
            f"  H1 Indépendance   : "
            f"{'✅ VALIDÉE' if h1.get('ok') else '⚠️ REJETÉE':15s} "
            f"corr_moy={h1.get('corr_moy', 0):.2f}  "
            f"score={h1.get('score', 0)}/100",
            f"  H2 Stabilité      : "
            f"{'✅ VALIDÉE' if h2.get('ok') else '⚠️ REJETÉE':15s} "
            f"CV={h2.get('cv_moy', 0):.1%}  "
            f"dérive={h2.get('derive_moy', 0):.1%}  "
            f"score={h2.get('score', 0)}/100",
            f"  H3 A priori BF    : "
            f"{'✅ VALIDÉE' if h3.get('ok') else '⚠️ ESTIMÉE':15s} "
            f"LR={h3.get('lr_apriori', 0):.1%}  "
            f"source={h3.get('source', '—')}",
            f"  H4 Homoscédasticité: "
            f"{'✅ VALIDÉE' if h4.get('ok') else '⚠️ REJETÉE':15s} "
            f"φ={h4.get('phi', 0):.6f}  "
            f"score={h4.get('score', 0)}/100",
            "",
            f"  Méthode CL retenue    : {n2.get('methode_cl_retenue', '—')}",
            f"  Justification CL      : {raison_cl}",
            f"  Méthode recommandée   : {methode_rec}",
            f"  Justification         : {raison_rec}",
            "",
            "3. BEST ESTIMATE S2 (Art. 77)",
            "─" * 40,
            f"  BE retenu         : {be:>16,.0f} €",
            f"  Provision P75     : {n3['mack'].get('reserve_p75', 0):>16,.0f} €",
            f"  Provision P90     : {p90:>16,.0f} €",
            f"  Provision P99.5   : {p995:>16,.0f} €",
            f"  σ Mack total      : {sigma:>16,.0f} €",
            f"  CV inter-méthodes : {cv:>15.1f} %"
            f"  {'(acceptable)' if cv < 5 else '(à surveiller)' if cv < 15 else '(élevé)'}",
            "",
            "4. SCR PROVISIONS (Art. 105 S2)",
            "─" * 40,
            f"  {scr['message']}",
            f"  Ratio SCR/BE      : {scr['ratio_scr_be']:.1%}",
        ]

        # Alertes LoB spécifiques
        alertes_lob = cfg.get('alertes_specifiques', [])
        if alertes_lob:
            lignes += ["", "5. POINTS DE VIGILANCE — BRANCHE", "─" * 40]
            for a in alertes_lob[:4]:
                lignes.append(f"  ⚠️  {a}")
        else:
            lignes += ["", "5. POINTS DE VIGILANCE", "─" * 40]

        # Alertes N2
        for alerte in n2.get('alertes', [])[:3]:
            clean = str(alerte).strip()
            if clean:
                lignes.append(f"  {clean}")

        lignes += [
            "",
            "6. DÉCISION ET RECOMMANDATIONS",
            "─" * 40,
        ]

        if statut == 'VERT':
            lignes += [
                f"  AVIS FAVORABLE — Les méthodes convergent (CV={cv:.1f}%).",
                f"  BE de {be:,.0f}€ retenu pour inscription au bilan S2.",
                f"  Utiliser {p90:,.0f}€ pour le calcul du SCR provisions.",
                f"  Archiver ce rapport et l'audit trail associé.",
            ]
        elif statut == 'AMBRE':
            lignes += [
                f"  AVIS AVEC RÉSERVES — Divergence modérée (CV={cv:.1f}%).",
                f"  BE de {be:,.0f}€ utilisable sous réserve de validation",
                f"  par l'actuaire désigné avant signature du bilan.",
                f"  Constituer une provision de risque complémentaire.",
            ]
        else:
            lignes += [
                f"  AVIS DÉFAVORABLE — Divergence importante (CV={cv:.1f}%).",
                f"  BE à valider impérativement par l'actuaire désigné.",
                f"  Ne pas inscrire au bilan S2 sans validation formelle.",
                f"  Révision approfondie des hypothèses recommandée.",
            ]

        return "\n".join(lignes)
