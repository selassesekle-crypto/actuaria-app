# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  agent.py  —  Classe principale AgentA7Provisionnement
# =============================================================================
#
#  Pipeline complet N1 → N2 → N3 → N4 → N5 :
#
#  N1 — Ingestion & validation (services.nv_triangle, façade du Bloc II :
#       lire → mapper → séparer → construire → diagnostiquer)
#  N2 — Hypothèses H1/H2/H3/H4 (n2_hypotheses.HypothesesValidator)
#  N3 — Méthodes actuarielles (n3/chain_ladder, mack, bf_cape_cod,
#                               bootstrap_odp, munich_cl)
#  N4 — Best Estimate S2 + SCR Art.105 (n4_best_estimate.BestEstimateS2)
#  N5 — Livrables (graphiques, commentaire, Excel, Word, PDF)
#
#  Interface publique inchangée vs v4.0 :
#    from a7_provisionnement import AgentA7Provisionnement
#    r = a7.run(source=...) → même dict de retour
#
#  Nouveautés v5.0 :
#    · lob               : paramètre LoB (branche) pour seuils adaptés
#    · schema_mapping    : mapping explicite des colonnes
#    · arrete            : libellé arrêté pour le rapport
#    · resultats_precedents : dict N-1 pour comparatif
#    · word_bytes / pdf_bytes dans le dict retourné
#    · n_sim_bootstrap   : défaut 5000 (recommandé EIOPA)
#
# =============================================================================

import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# ── Imports modules A7 ───────────────────────────────────────────────────────
from direction_non_vie.services.nv_triangle import preparer_pour_agent
from .n2_hypotheses     import HypothesesValidator
from .n2_hypotheses_clm import verifier_hypotheses_clm
from .n4_best_estimate  import BestEstimateS2, garde_fou_be_negatif, s2_non_calculable
# Alias VOLONTAIRE — ne pas « nettoyer » : `generer_graphiques` est aussi un
# PARAMÈTRE public de run() (compatibilité ancienne API, cf. plus bas). Sans
# alias, le paramètre (un bool) masque la fonction dans le corps de run() et
# l'appel lève TypeError: 'bool' object is not callable → aucun graphique.
from .n5_graphiques     import generer_graphiques as _generer_graphiques
from .n5_commentaire    import generer_commentaire
from .n5_excel          import export_excel
from .n5_rapport        import export_word, export_pdf
from .config.lob_config import get_lob_config

# ── Imports méthodes N3 ───────────────────────────────────────────────────────
from .n3.chain_ladder  import (
    calculer_facteurs,
    calculer_facteurs_cumules,
    calculer_tail_factor,
    calculer_pct_developpe,
    chain_ladder,
)
from .n3.mack         import mack_1993
from .n3.bf_cape_cod  import bornhuetter_ferguson, cape_cod
from .n3.bootstrap_odp import bootstrap_odp
from .n3.munich_cl    import munich_cl
from .n3.backtesting  import calculer_backtesting
from .n3.clark               import clark_ldf
from .n3.glm_apc_poisson     import glm_apc_poisson
from .n3.barnett_zehnwirth_ptf import barnett_zehnwirth_ptf

logger = logging.getLogger('actuaria.a7')


def _provisions_dossier(n1_rapport: Dict, triangle_reference: str,
                        annee_base: int, n1: Dict) -> Optional[float]:
    """Σ(charges à date − payé à date) sur les années de réserve, ou None.

    None dès que la base de projection est les PAIEMENTS : le BE est alors déjà
    `ultime − payé`, il n'y a rien à réintégrer (comportement historique intact).

    En base CHARGES, les méthodes N3 rendent l'IBNR pur — il manque les
    provisions dossier, comprises dans les charges mais pas encore payées.
    L'écart est lu sur ce que la façade a DÉJÀ construit (`charges` et
    `diagonale_paiements` de TrianglesConstruits) : aucun recalcul ici.
    Renvoie None si les paiements manquent — la façade a alors déjà alerté que
    le BE serait l'IBNR pur, et un chiffre inventé serait pire que rien.
    """
    if triangle_reference != 'charges':
        return None
    prep = n1_rapport.get('preparation')
    tri = getattr(prep, 'triangles', None)
    if tri is None or tri.charges is None or tri.diagonale_paiements is None:
        n1['alertes'].append(
            "⚠️ Base 'charges' sans triangle de paiements : provisions dossier "
            "non réintégrables — le Best Estimate reste l'IBNR PUR, sous-estimé.")
        return None
    n, m = tri.charges.shape
    diag_charges = np.array(
        [float(tri.charges[i, min(n - i - 1, m - 1)]) for i in range(n)])
    idx = max(0, min(int(annee_base), n - 1))
    provisions = float(np.sum(diag_charges[idx:] - tri.diagonale_paiements[idx:]))
    n1['infos'].append(
        f"Base 'charges' : {provisions:,.0f}€ de provisions dossier réintégrées "
        f"au Best Estimate (BE = IBNR pur + provisions dossier).")
    return provisions


class AgentA7Provisionnement:
    """
    Agent A7 Ibrahim — Provisionnement actuariel Non-Vie.

    Usage minimal
    -------------
    >>> a7 = AgentA7Provisionnement()
    >>> r  = a7.run(source=mon_triangle)

    Usage complet
    -------------
    >>> r = a7.run(
    ...     source              = df_sinistres,      # tout format accepté
    ...     triangle_engage     = engage.xlsx,        # Munich CL
    ...     primes              = vecteur_primes,     # BF/Cape Cod fiables
    ...     lob                 = 'rc_auto_corporels',# seuils adaptés
    ...     methode_cl          = 'auto',             # choix automatique
    ...     lr_bf_manuel        = 0.74,               # a priori expert
    ...     annees_a_exclure    = [0],                # exclusion manuelle
    ...     schema_mapping      = {'montant': 'cout'},# mapping colonnes
    ...     ref_client          = 'RC Auto Q2 2026',
    ...     arrete              = 'Q2 2026',
    ...     n_sim_bootstrap     = 5000,               # EIOPA recommande 5000
    ...     resultats_precedents= dict_n1,            # comparatif N-1/N
    ... )

    Dict retourné (inchangé vs v4.0 + nouvelles clés)
    --------------------------------------------------
    success, statut_rag, audit_id, erreur
    n1, n2, n3, n4
    graphiques, graphiques_erreur (None si OK), commentaire
    excel_bytes, word_bytes, pdf_bytes, audit_trail
    — compatibilité ancienne API —
    chain_ladder, mack, bf, cape_cod, bootstrap, munich_cl
    best_estimate, validation, tail_factor
    """

    def __init__(
        self,
        models_path: str  = '/tmp/actuaria',
        audit_path:  str  = '/tmp/actuaria',
        verbose:     bool = True,
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

        # Sous-modules (N1 est désormais la façade nv_triangle, sans état)
        self._hv  = HypothesesValidator()
        self._be  = BestEstimateS2()

    # =========================================================================
    #  POINT D'ENTRÉE PRINCIPAL
    # =========================================================================

    def run(
        self,
        # ── Données ───────────────────────────────────────────────────────────
        source                          = None,
        triangle_engage                 = None,
        primes                          = None,
        schema_mapping: Optional[Dict]  = None,
        # ── Paramètres actuariels ─────────────────────────────────────────────
        lob:              str           = 'generique',
        methode_cl:       str           = 'auto',
        lr_bf_manuel: Optional[float]   = None,
        annees_a_exclure: Optional[List[int]] = None,
        annee_base_reserve: int         = 1,
        # ── Rapport ───────────────────────────────────────────────────────────
        ref_client:       str           = '',
        arrete:           str           = '',
        resultats_precedents: Optional[Dict] = None,
        # ── Options ───────────────────────────────────────────────────────────
        triangle_reference: str        = 'paiements',  # 'paiements' | 'charges'
        courbe_rfr:       object        = None,   # Courbe EIOPA RFR (dict rfr_eiopa)
        n_sim_bootstrap:  int           = 5000,
        seed:             int           = 42,
        generer_graphiques_flag: bool   = True,
        generer_word:     bool          = True,
        generer_pdf_flag: bool          = True,
        # ── Compatibilité ancienne API ────────────────────────────────────────
        triangle                        = None,
        result_a2                       = None,
        mode_declare:     str           = 'auto',
        ultime_apriori: Optional[np.ndarray] = None,  # charge ultime a priori (BF 1972)
        taux_bf_manuel: Optional[float] = None,   # alias lr_bf_manuel
        generer_graphiques: bool        = True,    # alias generer_graphiques_flag
        annee_debut:      Optional[int]  = None,   # année calendaire de la 1ère ligne
        reserve_grands_sinistres: Optional[float] = None,  # réserve LLT à ajouter au BE
        n_grands_sinistres: int          = 0,       # nombre de grands sinistres identifiés
        methode_grands: str              = 'manuel', # 'manuel' | 'bf_auto' | 'cl_separe'
        **kwargs,
    ) -> Dict:
        """
        Pipeline complet N1 → N2 → N3 → N4 → N5.

        Tous les paramètres sont optionnels sauf source.

        `triangle_reference` choisit le triangle que les méthodes projettent :
        'paiements' (défaut) ou 'charges'. En base 'charges', les réserves N3
        sont l'IBNR PUR ; les provisions dossier sont réintégrées au BE en N4
        pour retrouver la grandeur S2 `ultime − payé`. Cf. `_provisions_dossier`.
        """
        t_debut  = datetime.now()
        audit_id = f"A7_{t_debut.strftime('%Y%m%d_%H%M%S')}"

        # Aliases compatibilité
        if taux_bf_manuel is not None and lr_bf_manuel is None:
            lr_bf_manuel = taux_bf_manuel
        gen_g = generer_graphiques_flag and generer_graphiques

        if self.verbose:
            logger.info(f"[{audit_id}] Agent A7 v5.0 démarré | lob={lob}")

        try:
            # ── Source ────────────────────────────────────────────────────────
            if source is None:
                if triangle is not None:
                    source = triangle
                elif result_a2 is not None:
                    source = result_a2
                else:
                    raise ValueError(
                        "Aucune donnée fournie. "
                        "Passez source=votre_triangle ou source=df_sinistres."
                    )

            # ── Config LoB ────────────────────────────────────────────────────
            cfg_lob   = get_lob_config(lob)
            lob_label = cfg_lob.get('label', lob)

            # =================================================================
            # N1 — INGESTION
            # =================================================================
            if self.verbose:
                logger.info("N1 — Ingestion & validation")

            # Façade nv_triangle (Bloc II) : lire → mapper → séparer → construire
            # → diagnostiquer. Remplace TriangleValidator, dont la branche
            # triangle_engage forçait le mode 'cumule' SANS détection — un engagé
            # fourni en incrémental était utilisé tel quel, silencieusement faux.
            # mode_charges='auto' ferme ce trou (détection à trois états).
            C, C_engage, primes_norm, n1_rapport = preparer_pour_agent(
                source,
                source_charges     = triangle_engage,
                primes             = primes,
                chemin_mapping     = schema_mapping,   # dict {standard: fichier} accepté
                mode_paiements     = mode_declare,
                mode_charges       = 'auto',
                triangle_reference = triangle_reference,
                lob                = lob,
                annee_debut        = annee_debut,
            )

            n, m = C.shape
            n1   = {
                **n1_rapport,
                'C':        C,
                'C_engage': C_engage,
                'primes':   primes_norm,
            }

            # Exclusions manuelles
            C_calc = C.copy()
            if annees_a_exclure:
                idx_valides = [i for i in range(n) if i not in annees_a_exclure]
                C_calc = C[idx_valides, :]
                n1['infos'].append(
                    f"ℹ️ {len(annees_a_exclure)} année(s) exclue(s) : "
                    f"{annees_a_exclure}"
                )
                if self.verbose:
                    logger.info(f"N1 — Exclusion années {annees_a_exclure}")

            if self.verbose:
                logger.info(
                    f"N1 OK — {n}×{m} | statut={n1['statut']} | "
                    f"{len(n1['alertes'])} alerte(s)"
                )

            # =================================================================
            # N2 — HYPOTHÈSES
            # =================================================================
            if self.verbose:
                logger.info("N2 — Validation hypothèses H1/H2/H3/H4 + CLM-H1..H4")

            n2 = self._hv.valider(C_calc, primes=primes_norm, lob=lob, lr_manuel=lr_bf_manuel)

            # ── CLM-H1..H4 : les hypothèses propres à Chain Ladder et Mack ────
            # Elles doivent être disponibles AU NIVEAU OÙ LA SÉLECTION SE DÉCIDE,
            # donc ici et non en N3 comme le test calendaire vivait jusqu'alors.
            #
            # ⚠️ L'ESTIMATEUR EST IMPOSÉ, PAS CHOISI. CLM teste les hypothèses de
            # Mack, qui sont énoncées pour l'estimateur volume-weighted
            # (`E(C[i,j+1]|C[i,j]) = λ_j·C[i,j]` avec `λ̂_j = ΣC[i,j+1]/ΣC[i,j]`).
            # Les tester sur une variante médiane ou écrêtée reviendrait à
            # valider un autre modèle que celui décrit par la théorie. C'est
            # aussi ce qui lève la circularité : `methode_cl_retenue` est produit
            # PAR N2, il ne peut donc pas conditionner un calcul qui s'y déroule.
            #
            # ⚠️ INCOHÉRENCE HÉRITÉE, SIGNALÉE ET NON CORRIGÉE ICI : si N3 retient
            # ensuite une variante (mesuré : 'mediane' sur le triangle RAA), les
            # hypothèses auront été vérifiées sur un estimateur différent de celui
            # qui produit la réserve. Le choix de variante dépend de l'ancienne H2,
            # elle-même destinée à être remplacée — à traiter au lot suivant.
            n2['clm'] = self._verifier_clm(C_calc, cfg_lob, annee_base_reserve)

            # CORRECTION BUG v4.0 :
            # methode_cl_retenue est maintenant dans n2 directement
            # (calculé par HypothesesValidator._choisir_variante_cl)
            if methode_cl == 'auto':
                methode_cl_retenue = n2['methode_cl_retenue']
            else:
                methode_cl_retenue = methode_cl
                n2['methode_cl_retenue'] = methode_cl_retenue

            # Enrichir n2 avec les dimensions du triangle pour le contexte Claude
            n, m = C_calc.shape
            n2['n_lignes']   = n
            n2['n_colonnes'] = m
            n2['dimensions'] = f"{n}×{m}"
            if annee_debut:
                n2['annee_debut'] = annee_debut
                n2['annee_fin']   = annee_debut + n - 1

            # Alerte ROUGE hypothèses
            if n2['statut_global'] == 'ROUGE':
                n2['alertes'].insert(0,
                    "HYPOTHESES NON VALIDEES — Résultats à interpréter avec "
                    "prudence. Validation actuaire désigné requise avant tout usage."
                )

            if self.verbose:
                logger.info(
                    f"N2 OK | H1={'OK' if n2['h1_independance']['ok'] else 'KO'} "
                    f"H2={'OK' if n2['h2_stabilite']['ok'] else 'KO'} "
                    f"methode_cl={methode_cl_retenue} "
                    f"recommandee={n2['methode_recommandee']}"
                )

            # =================================================================
            # N3 — MÉTHODES ACTUARIELLES
            # =================================================================
            if self.verbose:
                logger.info(f"N3 — Méthodes ({methode_cl_retenue})")

            n3 = self._calculer_n3(
                C              = C_calc,
                C_engage       = C_engage,
                primes         = primes_norm,
                methode_cl     = methode_cl_retenue,
                lr_bf_manuel   = lr_bf_manuel,
                ultime_apriori = ultime_apriori,
                annee_base     = annee_base_reserve,
                n_sim_bootstrap= max(200, n_sim_bootstrap),
                seed           = seed,
                cfg_lob        = cfg_lob,
            )

            if self.verbose:
                logger.info(
                    f"N3 OK | CL={n3['chain_ladder']['reserve_totale']:,.0f}€ "
                    f"Mack={n3['mack']['reserve_best_estimate']:,.0f}€ "
                    f"BF={n3['bf']['reserve_totale']:,.0f}€ "
                    f"CC={n3['cape_cod']['reserve_totale']:,.0f}€"
                )

            # =================================================================
            # N4 — BEST ESTIMATE S2 + SCR
            # =================================================================
            if self.verbose:
                logger.info("N4 — Best Estimate (réserve brute) + SCR provisions")

            # Back-testing boni/mali (calculé ici avec C_calc)
            try:
                n3['backtesting'] = calculer_backtesting(C_calc, annee_debut=annee_debut)
            except Exception as _ebt:
                logger.warning(f"Back-testing ignoré : {_ebt}")
                n3['backtesting'] = {}
            # Effet calendaire — GLM Poisson APC (Renshaw-Verrall)
            try:
                n3['glm_apc'] = glm_apc_poisson(C_calc, annee_debut=annee_debut, annee_base=annee_base_reserve)
            except Exception as _eapc:
                logger.warning(f"GLM Poisson APC ignoré : {_eapc}")
                n3['glm_apc'] = {}
            # Détection tendances/ruptures — Barnett-Zehnwirth PTF (étape 2a, diagnostic)
            # Sans ruptures déclarées : le scan propose des candidats, rien n'est testé.
            try:
                n3['bz_ptf'] = barnett_zehnwirth_ptf(C_calc, annee_debut=annee_debut)
            except Exception as _eptf:
                logger.warning(f"Barnett-Zehnwirth PTF ignoré : {_eptf}")
                n3['bz_ptf'] = {}
            # Année début pour labels calendaires (G14)
            if annee_debut:
                n3['annee_debut_triangle'] = annee_debut

            # ── Base CHARGES : provisions dossier à réintégrer au BE ──────────
            # Les méthodes N3 rendent `ultime − charges à date` (IBNR pur) quand
            # elles tournent sur les charges. Le BE S2 est `ultime − PAYÉ à date`.
            # L'écart est exactement Σ(charges à date − payé à date), que la
            # façade fournit déjà : rien n'est recalculé ici. Cf. n4 § 3bis.
            _prov_dossier = _provisions_dossier(
                n1_rapport, triangle_reference, annee_base_reserve, n1)

            n4 = self._be.calculer(n2, n3, C_calc, lob=lob, courbe_rfr=courbe_rfr,
                                   provisions_dossier=_prov_dossier)

            # ── Réintégration grands sinistres (LLT) ──────────────────────────
            if reserve_grands_sinistres is not None and reserve_grands_sinistres > 0:
                _rgs = float(reserve_grands_sinistres)
                # `be_attritional` devient le pivot de la décomposition N4 :
                # be_ibnr_pur + provisions_dossier == be_attritional, et
                # best_estimate == be_attritional + reserve_grands_sinistres.
                _be_attrit = float(n4['best_estimate'])
                _be_final  = _be_attrit + _rgs
                n4['best_estimate']              = round(_be_final, 0)
                n4['be_attritional']             = round(_be_attrit, 0)
                n4['reserve_grands_sinistres']   = round(_rgs, 0)
                n4['n_grands_sinistres']         = n_grands_sinistres
                n4['methode_grands']             = methode_grands
                n4['llt_applique']               = True

                # ── B5 : recalcul des agrégats S2 sur le BE final (post-LLT) ───
                # Le σ de réserve (incertitude du processus) est indépendant du
                # niveau LLT — seul le BE change. Sans ce recalcul, SCR / percentiles
                # / RM / PT restaient calculés sur l'attritional → PT S2 < BE_final
                # (aberrant sous Solvabilité 2).

                # 1. SCR formule standard (Art. 105) : 3 × σ_eiopa × BE_final
                _sig_eiopa = float(n4['scr']['sigma_eiopa'])
                _scr_new   = 3.0 * _sig_eiopa * _be_final
                _ratio_scr = _scr_new / max(_be_final, 1e-9)
                n4['scr']['scr_provisions'] = round(_scr_new, 0)
                n4['scr']['ratio_scr_be']   = round(_ratio_scr, 4)
                n4['scr']['message'] = (
                    f"SCR_prov = 3 × {_sig_eiopa:.0%} × {_be_final:,.0f}€ "
                    f"= {_scr_new:,.0f}€ (ratio SCR/BE = {_ratio_scr:.1%})"
                )
                n4['scr_prov'] = n4['scr']['scr_provisions']

                # 2. Percentiles log-normale (QIS5 TP.5.26) recentrés sur BE_final,
                #    σ inchangé (σ_total composé, comme les percentiles d'origine).
                #    Les variantes _mack / _boot restent sur l'attritional (transparence).
                _sig_pct = float(n4.get('sigma_total_compose') or n4.get('sigma_mack') or 0.0)
                if _sig_pct > 0 and _be_final > 0:
                    _cv    = _sig_pct / _be_final
                    _s2_ln = float(np.log(1.0 + _cv ** 2))
                    _s_ln  = float(np.sqrt(_s2_ln))
                    _m_ln  = float(np.log(_be_final) - _s2_ln / 2.0)
                    n4['reserve_p75']   = round(float(np.exp(_m_ln + 0.6745 * _s_ln)), 0)
                    n4['reserve_p90']   = round(float(np.exp(_m_ln + 1.2816 * _s_ln)), 0)
                    n4['reserve_p99_5'] = round(float(np.exp(_m_ln + 2.5758 * _s_ln)), 0)

                # 3. Risk Margin RECALCULÉE À NEUF sur le BE final, via la MÊME
                #    formule que N4 (_calculer_risk_margin : CoC × Σ SCR(t) actualisés,
                #    même run-off f_cum, même courbe RFR). La RM étant LINÉAIRE en SCR
                #    (donc en BE), ce recalcul vaut EXACTEMENT l'ancienne proratisation
                #    RM×(SCR_final/SCR_attritionnel) quand l'attritionnel est positif —
                #    et il reste CORRECT quand N4 a nullé la RM attritionnelle (BE
                #    attritionnel < 0) : il repart du BE final (> 0) et de son SCR.
                _scr_final = {**n4['scr'], 'scr_provisions': _scr_new}
                _f_cum_llt = n3.get('chain_ladder', {}).get('facteurs_cumules', [])
                _rm_data   = self._be._calculer_risk_margin(
                    _be_final, _scr_final, _f_cum_llt, courbe_rfr)
                _rm_new    = float(_rm_data['risk_margin'])
                n4['risk_margin'] = _rm_data['risk_margin']
                n4['ratio_rm_be'] = _rm_data['ratio_rm_be']

                # 4. Provisions techniques S2 = BE_final + RM  (doit être ≥ BE_final)
                n4['provisions_techniques_s2'] = _rm_data['provisions_techniques_s2']

                # 5. Message enrichi (BE + SCR + RM + PT recalculés)
                n4['message'] = (
                    f"BE brut final = {_be_final:,.0f}€ "
                    f"(attritional {_be_attrit:,.0f}€ + grands sinistres {_rgs:,.0f}€) · "
                    f"LLT appliqué — {n_grands_sinistres} grand(s) sinistre(s) · "
                    f"méthode grands : {methode_grands} · "
                    f"SCR_prov = {_scr_new:,.0f}€ · RM = {_rm_new:,.0f}€ · "
                    f"PT S2 = {n4['provisions_techniques_s2']:,.0f}€"
                )

                # 6. Garde-fou TOTAL : BE final <= 0 (reprise nette) → agrégats S2
                # non calculables (SCR/RM/PT/percentiles absurdes sur un BE négatif).
                # Signalé ROUGE, jamais plancheré en silence. Dormant tant que BE > 0
                # (aujourd'hui : _be_attrit >= 0 et _rgs > 0 → _be_final > 0).
                _garde = garde_fou_be_negatif(_be_final)
                if _garde is not None:
                    n4['scr']['scr_provisions']    = _garde['scr_provisions']
                    n4['scr']['ratio_scr_be']      = _garde['ratio_scr_be']
                    n4['scr']['message']           = _garde['message']
                    n4['scr_prov']                 = _garde['scr_provisions']
                    n4['reserve_p75']              = _garde['reserve_p75']
                    n4['reserve_p90']              = _garde['reserve_p90']
                    n4['reserve_p99_5']            = _garde['reserve_p99_5']
                    n4['risk_margin']              = _garde['risk_margin']
                    n4['ratio_rm_be']              = _garde['ratio_rm_be']
                    n4['provisions_techniques_s2'] = _garde['provisions_techniques_s2']
                    n4['be_negatif']               = True
                    n4.setdefault('alertes', []).insert(0, _garde['message'])
                    n4['message']                  = _garde['message']
                else:
                    # BE final > 0 : si N4 avait signalé l'attritional négatif (avant
                    # ajout des grands sinistres), les agrégats S2 recalculés ci-dessus
                    # sur _be_final > 0 sont valides → on lève le drapeau et l'alerte.
                    if n4.pop('be_negatif', None):
                        n4['alertes'] = [a for a in n4.get('alertes', [])
                                         if 'BE brut négatif' not in str(a)]
                if self.verbose:
                    logger.info(
                        f"LLT | BE_final={_be_final:,.0f}€ "
                        f"= attrit {_be_attrit:,.0f}€ + grands {_rgs:,.0f}€ "
                        f"({n_grands_sinistres} sinistres, méthode={methode_grands})"
                    )

            if self.verbose:
                if n4.get('reserve_p90') is not None and n4['scr'].get('scr_provisions') is not None:
                    logger.info(
                        f"N4 OK | BE={n4['best_estimate']:,.0f}€ "
                        f"P90={n4['reserve_p90']:,.0f}€ "
                        f"CV={n4['cv_inter_methodes']:.1f}% "
                        f"SCR={n4['scr']['scr_provisions']:,.0f}€"
                    )
                else:
                    logger.info(
                        f"N4 OK | BE={n4['best_estimate']:,.0f}€ | "
                        f"agrégats S2 non calculables (BE négatif — revue actuaire)"
                    )

            # ── Livrables : neutraliser les None AVANT N5 (point unique) ──────
            # Un BE négatif rend les agrégats S2 non calculables (None côté N4).
            # Les 4 générateurs N5 (commentaire / rapport / Excel / graphiques)
            # formatent et calculent sur ces clés (~40 points d'usage) : aucun
            # None ne doit les atteindre. On neutralise ICI, en UN seul endroit,
            # tout en CONSERVANT be_negatif — les sections N5 s'en servent pour
            # afficher MSG_S2_NON_CALCULABLE au lieu de chiffres trompeurs.
            if s2_non_calculable(n4):
                for _k in ('reserve_p75', 'reserve_p90', 'reserve_p99_5',
                           'risk_margin', 'provisions_techniques_s2',
                           'ratio_rm_be', 'scr_prov'):
                    if n4.get(_k) is None:
                        n4[_k] = 0
                if n4.get('scr', {}).get('scr_provisions') is None:
                    n4['scr']['scr_provisions'] = 0
                    n4['scr']['ratio_scr_be']   = 0

            # =================================================================
            # N5 — LIVRABLES
            # =================================================================
            if self.verbose:
                logger.info("N5 — Génération livrables")

            # Graphiques Plotly — un échec ne fait pas tomber le run, mais il est
            # REMONTÉ dans le résultat (graphiques_erreur) : sans ça un « succès
            # dégradé » sans aucun graphique reste invisible côté appelant.
            graphiques_dict   = {}
            graphiques_erreur = None
            if gen_g:
                try:
                    graphiques_dict = _generer_graphiques(C_calc, n2, n3, n4)
                    if graphiques_dict:
                        logger.info(f"N5 — {len(graphiques_dict)} graphiques générés : "
                                    f"{list(graphiques_dict.keys())}")
                    else:
                        graphiques_erreur = "aucun graphique produit (générateur silencieux)"
                        logger.error(f"N5 graphiques : {graphiques_erreur}")
                except Exception as e:
                    graphiques_erreur = f"{type(e).__name__} : {e}"
                    logger.error(f"N5 graphiques ECHEC : {e}\n{traceback.format_exc()}")
                    graphiques_dict = {}

            # Commentaire actuariel
            commentaire = generer_commentaire(
                n1=n1, n2=n2, n3=n3, n4=n4,
                lob=lob, lob_label=lob_label,
                ref_client=ref_client,
            )

            # Excel
            try:
                excel_bytes = export_excel(
                    C            = C_calc,
                    n1           = n1,
                    n2           = n2,
                    n3           = n3,
                    n4           = n4,
                    ref_client   = ref_client,
                    arrete       = arrete,
                    resultats_precedents = resultats_precedents,
                )
            except Exception as e:
                logger.warning(f"N5 Excel échoué : {e}")
                excel_bytes = b''

            # Word
            word_bytes = b''
            if generer_word:
                try:
                    word_bytes = export_word(
                        n1          = n1,
                        n2          = n2,
                        n3          = n3,
                        n4          = n4,
                        commentaire = commentaire,
                        graphiques  = graphiques_dict,
                        ref_client  = ref_client,
                        arrete      = arrete,
                        audit_id    = audit_id,
                        lob_label   = lob_label,
                    )
                    if self.verbose:
                        logger.info(f"N5 Word : {len(word_bytes):,} bytes")
                except Exception as e:
                    logger.warning(f"N5 Word échoué : {e}")

            # PDF
            pdf_bytes = b''
            if generer_pdf_flag:
                try:
                    pdf_bytes = export_pdf(
                        n1          = n1,
                        n2          = n2,
                        n3          = n3,
                        n4          = n4,
                        commentaire = commentaire,
                        graphiques  = graphiques_dict,
                        ref_client  = ref_client,
                        arrete      = arrete,
                        audit_id    = audit_id,
                        lob_label   = lob_label,
                    )
                    if self.verbose:
                        logger.info(f"N5 PDF : {len(pdf_bytes):,} bytes")
                except Exception as e:
                    logger.warning(f"N5 PDF échoué : {e}")

            # Audit trail
            audit = self._audit_trail(
                audit_id, n1, n2, n3, n4,
                n4['statut'], t_debut, ref_client, lob,
            )
            self._sauvegarder_audit(audit_id, audit)

            # Statut global final
            statut_rag = n4['statut']
            if n1['statut'] == 'ROUGE' or n2['statut_global'] == 'ROUGE':
                statut_rag = 'ROUGE'
            elif n1['statut'] == 'AMBRE' or n2['statut_global'] == 'AMBRE':
                if statut_rag == 'VERT':
                    statut_rag = 'AMBRE'

            duree = (datetime.now() - t_debut).total_seconds()
            if self.verbose:
                logger.info(
                    f"[{audit_id}] A7 terminé | "
                    f"statut={statut_rag} | durée={duree:.1f}s"
                )

            # =============================================================
            # RÉSULTAT FINAL
            # Dict identique v4.0 + nouvelles clés v5.0
            # =============================================================
            return {
                # ── Standard ────────────────────────────────────────────
                'success':     True,
                'statut_rag':  statut_rag,
                'audit_id':    audit_id,
                'erreur':      None,

                # ── Données ─────────────────────────────────────────────
                'triangle':    C_calc.tolist() if hasattr(C_calc, 'tolist') else C_calc,
                'lob':         lob,
                'lob_label':   lob_label,

                # ── Niveaux ─────────────────────────────────────────────
                'n1': {k: v for k, v in n1.items() if k not in ('C', 'C_engage', 'primes')},
                'n2': n2,
                'n3': {k: v for k, v in n3.items() if k != 'facteurs_indiv'},
                'n4': n4,

                # ── Livrables ───────────────────────────────────────────
                'graphiques':   graphiques_dict,
                'graphiques_erreur': graphiques_erreur,   # None si OK
                'commentaire':  commentaire,
                'excel_bytes':  excel_bytes,
                'word_bytes':   word_bytes,    # ← NOUVEAU v5.0
                'pdf_bytes':    pdf_bytes,     # ← NOUVEAU v5.0
                'audit_trail':  audit,

                # ── Compatibilité ancienne API v4.0 ─────────────────────
                'chain_ladder':     n3['chain_ladder'],
                'mack':             n3['mack'],
                'bf':               n3['bf'],
                'cape_cod':         n3['cape_cod'],
                'bootstrap':        n3['bootstrap'],
                'munich_cl':        n3['munich_cl'],
                'tail_factor':      n3['chain_ladder'].get('tail_factor', {}),
                'best_estimate':    n4,
                'validation':       n2,
                'hypotheses':       n2,
                'back_testing':     {'statut': 'INFO', 'message': 'Voir audit trail'},
                'atypiques':        {'alertes': n2.get('alertes', [])},
                'rapport_actuaire': {
                    'avis': (
                        'FAVORABLE' if statut_rag == 'VERT' else
                        'AVEC RÉSERVES' if statut_rag == 'AMBRE' else
                        'DÉFAVORABLE'
                    ),
                    'sections': [{'numero': 1, 'titre': 'Rapport complet', 'contenu': commentaire}],
                },
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR A7 : {e}", exc_info=True)
            return {
                'success':     False,
                'statut_rag':  'ROUGE',
                'audit_id':    audit_id,
                'erreur':      str(e),
                'commentaire': f"ERREUR A7 : {str(e)}",
                'excel_bytes': b'',
                'word_bytes':  b'',
                'pdf_bytes':   b'',
                'graphiques':  {},
                'graphiques_erreur': 'run interrompu avant N5',
                'n1': {}, 'n2': {}, 'n3': {}, 'n4': {},
            }

    # =========================================================================
    #  N3 — ORCHESTRATEUR DES MÉTHODES
    # =========================================================================

    def _verifier_clm(
        self,
        C:          np.ndarray,
        cfg_lob:    Dict,
        annee_base: int,
    ) -> Dict:
        """CLM-H1..H4 sur l'estimateur STANDARD, avec sa propre queue.

        Les facteurs et la queue sont recalculés ici plutôt que repris de N3 :
        N3 tourne APRÈS N2 et sur la variante choisie par N2. Ce n'est donc pas
        un doublon mais deux grandeurs distinctes — l'estimateur de référence de
        Mack d'un côté, celui effectivement retenu de l'autre. Quand la variante
        retenue est 'standard', le cas courant, les deux coïncident.

        Ne LÈVE JAMAIS : un échec de vérification ne doit pas empêcher un
        provisionnement de se produire. Il est signalé, pas fatal.
        """
        try:
            facteurs, _ = calculer_facteurs(C, 'standard')
            tail_info = calculer_tail_factor(
                facteurs,
                lob_tail_max_alerte      = cfg_lob.get('tail_factor_max_alerte', 1.05),
                risque_long              = cfg_lob.get('risque_long', True),
                tail_seuil_stabilisation = cfg_lob.get('tail_seuil_stabilisation', 1.02),
            )
            return verifier_hypotheses_clm(
                C, tail_info=tail_info, facteurs=facteurs, annee_base=annee_base)
        except Exception as e:
            logger.warning(f"CLM-H1..H4 non calculées : {e}")
            return {'erreur': str(e), 'hypotheses': {}, 'couvertures': {}}

    def _calculer_n3(
        self,
        C:               np.ndarray,
        C_engage:        Optional[np.ndarray],
        primes:          Optional[np.ndarray],
        methode_cl:      str,
        lr_bf_manuel:    Optional[float],
        ultime_apriori:  Optional[np.ndarray],
        annee_base:      int,
        n_sim_bootstrap: int,
        seed:            int,
        cfg_lob:         Dict,
    ) -> Dict:
        """
        Calcule toutes les méthodes actuarielles N3 et retourne un dict unifié.
        """
        # ── Facteurs CL ───────────────────────────────────────────────────────
        facteurs, facteurs_indiv = calculer_facteurs(C, methode_cl)

        # ── Tail factor ───────────────────────────────────────────────────────
        tail_info = calculer_tail_factor(
            facteurs,
            lob_tail_max_alerte      = cfg_lob.get('tail_factor_max_alerte', 1.05),
            risque_long              = cfg_lob.get('risque_long', True),
            tail_seuil_stabilisation = cfg_lob.get('tail_seuil_stabilisation', 1.02),
        )

        # ── Facteurs cumulés + % développé ────────────────────────────────────
        f_cum   = calculer_facteurs_cumules(facteurs, tail_info['tail_factor'])
        pct_dev = calculer_pct_developpe(C, f_cum)

        # ── Chain Ladder ──────────────────────────────────────────────────────
        r_cl = chain_ladder(
            C                   = C,
            methode             = methode_cl,
            annee_base_reserve  = annee_base,
            lob_tail_max_alerte = cfg_lob.get('tail_factor_max_alerte', 1.05),
            tail_force          = tail_info['tail_factor'],  # tail pré-calculé
        )
        # Injecter tail_factor et facteurs_indiv pour les niveaux suivants
        r_cl['tail_factor']    = tail_info
        r_cl['facteurs_indiv'] = facteurs_indiv
        ult_cl  = np.array(r_cl['ultimates'])
        ibnr_cl = np.array(r_cl['ibnr_par_annee'])
        ld      = np.array(r_cl['last_diagonale'])

        # ── Mack 1993 ─────────────────────────────────────────────────────────
        r_mack = mack_1993(
            C              = C,
            facteurs       = facteurs,
            facteurs_indiv = facteurs_indiv,
            ultimates_cl   = ult_cl,
            ibnr_cl        = ibnr_cl,
            annee_base     = annee_base,
        )

        # ── Bornhuetter-Ferguson ──────────────────────────────────────────────
        # `primes` est ici la MESURE D'EXPOSITION. Le paramètre amont s'appelle
        # encore `primes` par héritage, mais BF et Cape Cod acceptent toute
        # mesure de volume (contrats, capitaux assurés…) — cf. leur en-tête.
        r_bf = bornhuetter_ferguson(
            C              = C,
            pct_dev        = pct_dev,
            last_diag      = ld,
            ultimates_cl   = ult_cl,
            exposition     = primes,
            ultime_apriori = ultime_apriori,
            lr_manuel      = lr_bf_manuel,
            annee_base     = annee_base,
            lr_reference   = cfg_lob.get('lr_marche_reference'),
            lr_reference_src = cfg_lob.get('lr_marche_source', ''),
        )

        # ── Cape Cod ──────────────────────────────────────────────────────────
        r_cc = cape_cod(
            C              = C,
            pct_dev        = pct_dev,
            last_diag      = ld,
            exposition     = primes,
            annee_base     = annee_base,
            lr_reference   = cfg_lob.get('lr_marche_reference'),
            lr_reference_src = cfg_lob.get('lr_marche_source', ''),
        )

        # ── Bootstrap ODP ─────────────────────────────────────────────────────
        # Toujours sur facteurs standard (indépendant de la variante CL retenue)
        f_std, _ = calculer_facteurs(C, 'standard')
        r_boot   = bootstrap_odp(
            C          = C,
            facteurs   = f_std,
            n_sim      = n_sim_bootstrap,
            seed       = seed,
            annee_base = annee_base,
        )

        # ── Munich CL ─────────────────────────────────────────────────────────
        if C_engage is not None and cfg_lob.get('munich_cl_disponible', False):
            r_munich = munich_cl(C, C_engage, annee_base=annee_base)
        else:
            msg = (
                "Munich CL non calculé — triangle engagé non fourni."
                if C_engage is None else
                f"Munich CL désactivé pour la branche {cfg_lob.get('label','—')} "
                "(nécessite triangle engagé conforme)."
            )
            r_munich = {
                'disponible': False,
                'statut':     'INFO',
                'message':    msg,
                'conseil':    "Fournissez triangle_engage= pour activer Munich CL.",
                'methode':    'Munich Chain Ladder (Quarg & Mack 2004)',
            }

        return {
            'methode_cl':      methode_cl,
            'facteurs':        [float(f) for f in facteurs],
            'facteurs_cumules': [float(f) for f in f_cum],
            'facteurs_indiv':  facteurs_indiv,
            'pct_developpe':   [float(p) for p in pct_dev],
            'chain_ladder':    r_cl,
            'mack':            r_mack,
            'bf':              r_bf,
            'cape_cod':        r_cc,
            'bootstrap':       r_boot,
            'munich_cl':       r_munich,
            'tail_factor':     tail_info,
            'backtesting':     {},
            'clark':           clark_ldf(C) if C is not None and C.shape[0] >= 4 else {'success': False, 'disponible': False},
            'glm_apc':         {},
            'bz_ptf':          {},
        }

    # =========================================================================
    #  AUDIT TRAIL
    # =========================================================================

    def _audit_trail(
        self,
        audit_id:   str,
        n1:         Dict,
        n2:         Dict,
        n3:         Dict,
        n4:         Dict,
        statut:     str,
        t_debut:    datetime,
        ref_client: str,
        lob:        str,
    ) -> Dict:
        """Génère l'audit trail JSON complet et traçable ACPR."""
        duree = (datetime.now() - t_debut).total_seconds()
        return {
            'audit_id':       audit_id,
            'ref_client':     ref_client,
            'lob':            lob,
            'date':           datetime.now().isoformat(),
            'duree_sec':      round(duree, 2),
            'statut':         statut,
            'version':        'A7-v5.0',

            'n1_resume': {
                'taille':    n1.get('taille'),
                'n_annees':  n1.get('n_annees'),
                'n_dev':     n1.get('n_dev'),
                'mode':      n1.get('mode_detecte'),
                'statut':    n1.get('statut'),
                'alertes':   n1.get('alertes', []),
            },
            'n2_resume': {
                'h1_ok':              n2['h1_independance']['ok'],
                'h1_corr_moy':        n2['h1_independance'].get('corr_moy'),
                'h2_ok':              n2['h2_stabilite']['ok'],
                'h2_cv_moy':          n2['h2_stabilite'].get('cv_moy'),
                'h3_lr':              n2['h3_apriori_bf'].get('lr_apriori'),
                'h4_phi':             n2['h4_homosc_bootstrap'].get('phi'),
                'methode_cl_retenue': n2.get('methode_cl_retenue'),
                'methode_recommandee': n2.get('methode_recommandee'),
                'statut_global':      n2.get('statut_global'),
                'scores':             n2.get('scores_confiance', {}),
                # CLM-H1..H4 — EXPOSÉES, CONSOMMÉES PAR RIEN. Elles sont
                # visibles par l'actuaire dès maintenant ; le mécanisme de
                # sélection continue de reposer sur les scores ci-dessus.
                'clm_hypotheses':     {c: {'statut': h['statut'],
                                           'message': h['message']}
                                       for c, h in n2.get('clm', {})
                                       .get('hypotheses', {}).items()},
                'clm_couvertures':    n2.get('clm', {})
                                        .get('couvertures', {}).get('synthese', {}),
            },
            'n3_resume': {
                'cl':          n3['chain_ladder']['reserve_totale'],
                'mack':        n3['mack']['reserve_best_estimate'],
                'mack_sigma':  n3['mack']['sigma_total'],
                'bf':          n3['bf']['reserve_totale'],
                'cc':          n3['cape_cod']['reserve_totale'],
                'boot_be':     n3['bootstrap'].get('be_bootstrap', 0),
                'boot_p90':    n3['bootstrap'].get('p90', 0),
                'boot_p99_5':  n3['bootstrap'].get('p99_5', 0),
                'tail_factor': n3['tail_factor'].get('tail_factor', 1),
                'munich_cl_disponible': n3['munich_cl'].get('disponible', False),
            },
            'n4_resume': {
                'best_estimate':     n4['best_estimate'],
                'reserve_p75':       n4['reserve_p75'],
                'reserve_p90':       n4['reserve_p90'],
                'reserve_p99_5':     n4['reserve_p99_5'],
                'sigma_mack':        n4['sigma_mack'],
                'cv_inter_methodes': n4['cv_inter_methodes'],
                'methodes_incluses': n4['methodes_incluses'],
                'methodes_exclues':  n4['methodes_exclues'],
                'poids':             n4['poids'],
                'scr_provisions':    n4['scr']['scr_provisions'],
                'sigma_eiopa':       n4['scr']['sigma_eiopa'],
                'statut':            n4['statut'],
            },
        }

    def _sauvegarder_audit(self, audit_id: str, audit: Dict):
        """Sauvegarde l'audit trail en JSON dans audit_path."""
        try:
            path = self.audit_path / f"{audit_id}.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(audit, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Audit non sauvegardé : {e}")
