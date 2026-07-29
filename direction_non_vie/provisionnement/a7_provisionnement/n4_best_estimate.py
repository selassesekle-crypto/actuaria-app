# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n4_best_estimate.py  —  Best Estimate S2 + SCR provisions
# =============================================================================
#
#  Références réglementaires
#  -------------------------
#  Directive Solvabilité II (2009/138/CE), Art. 77 :
#    Best Estimate = espérance de la valeur actuelle des flux futurs.
#    ⚠️ A7 calcule ici la RÉSERVE BRUTE (non actualisée). L'actualisation à la
#    courbe RFR EIOPA — la « valeur actuelle » au sens de l'Art. 77 — est opérée
#    en aval par A10 (Solvabilité 2) et A11 (IFRS 17, à son propre taux).
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
#  Best Estimate — réserve brute (Art. 77 ; actualisation S2 en aval, A10)
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
from .config.rfr_eiopa  import get_taux_rfr, DATE_COURBE, get_courbe_embarquee

logger = logging.getLogger('actuaria.a7')


def garde_fou_be_negatif(be_final: float) -> Optional[Dict]:
    """Garde-fou TOTAL : si le Best Estimate final est <= 0 (reprise nette), les
    agrégats S2 deviennent mathématiquement absurdes — SCR = 3σ×BE devient négatif,
    le ratio SCR/max(BE,1e-9) explose, la log-normale des percentiles n'est pas
    définie. Retourne alors un descriptif ROUGE + marqueurs 'non calculable' (None) ;
    retourne None si BE > 0 (l'appelant calcule normalement).

    Le BE négatif n'est JAMAIS écrasé en silence (aucun plancher caché) : il est
    signalé pour revue actuarielle. Le point estimate BE lui-même reste tel quel."""
    if be_final > 0:
        return None
    return {
        'be_negatif':               True,
        'statut':                   'ROUGE',
        'message': ("BE brut négatif — reprise nette, SCR/RM non calculables sur "
                    "BE négatif, revue actuaire impérative."),
        'scr_provisions':           None,
        'ratio_scr_be':             None,
        'reserve_p75':              None,
        'reserve_p90':              None,
        'reserve_p99_5':            None,
        'risk_margin':              None,
        'ratio_rm_be':              None,
        'provisions_techniques_s2': None,
    }


# Message UNIQUE affiché par les livrables N5 quand les agrégats S2 ne sont pas
# calculables (BE négatif). Source unique — ne pas dupliquer dans N5.
MSG_S2_NON_CALCULABLE = (
    "Agrégats S2 NON CALCULABLES — Best Estimate négatif (reprise nette) : SCR, "
    "Risk Margin, provisions techniques et percentiles ne sont pas définis sur un "
    "BE négatif. Revue actuaire impérative avant toute inscription au bilan."
)


def s2_non_calculable(n4: Dict) -> bool:
    """True si les agrégats S2 (SCR / Risk Margin / PT / percentiles) sont non
    calculables parce que le Best Estimate est négatif (cf. garde_fou_be_negatif).

    Les générateurs N5 (commentaire, rapport, Excel, graphiques) doivent alors
    afficher MSG_S2_NON_CALCULABLE AU LIEU des chiffres : aucune valeur None ne
    doit atteindre un formatage ou un calcul. Source UNIQUE partagée par les 4."""
    return bool(n4.get('be_negatif'))


class BestEstimateS2:
    """
    Calcule le Best Estimate — réserve BRUTE, avant actualisation (la valeur
    actuelle S2 au sens de l'Art. 77 est produite en aval par A10) — avec :
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
        provisions_dossier: Optional[float] = None,
        **kwargs,
    ) -> Dict:
        """
        Calcule le Best Estimate (réserve brute, avant actualisation) et le SCR.

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
        provisions_dossier : float, optionnel
            Σ(charges à date − payé à date), à fournir UNIQUEMENT quand les
            méthodes N3 ont tourné sur un triangle de CHARGES : leurs réserves
            sont alors l'IBNR pur, et il manque au BE les provisions dossier.
            None (défaut) = base paiements, aucune correction — cf. § 3bis.

        Returns
        -------
        dict conforme standard ActuarIA. `best_estimate` est le BE S2 complet ;
        `be_ibnr_pur` et `provisions_dossier` en donnent la décomposition (en
        base paiements, `be_ibnr_pur == best_estimate` et les provisions sont 0).
        """
        scores = n2.get('scores_confiance', {})
        cfg    = get_lob_config(lob)

        # ── Réserves par méthode ──────────────────────────────────────────────
        cl_res   = n3['chain_ladder']['reserve_totale']
        bf_res   = n3['bf']['reserve_totale']
        cc_res   = n3['cape_cod']['reserve_totale']
        sigma    = n3['mack']['sigma_total']
        boot     = n3.get('bootstrap', {})

        # Mack RETIRÉ du point estimate du BE : son point = celui du Chain Ladder
        # (Mack = CL + σ ; réserve identique par construction, mack consomme les
        # facteurs du CL). L'inclure comme méthode pondérée double-compterait le CL.
        # Mack reste utilisé pour la VOLATILITÉ (sigma, n3['mack']['sigma_total']).
        score_map = {
            'chain_ladder':         scores.get('chain_ladder', 70),
            'bornhuetter_ferguson': scores.get('bornhuetter_ferguson', 70),
            'cape_cod':             scores.get('cape_cod', 70),
        }

        methodes_dispo = {
            'chain_ladder':         cl_res,
            'bornhuetter_ferguson': bf_res,
            'cape_cod':             cc_res,
        }

        # ── 1. Sélection des méthodes validées ────────────────────────────────
        methodes_incluses: Dict[str, Tuple[float, int]] = {}
        methodes_exclues:  Dict[str, Tuple[float, int]] = {}

        for m, r in methodes_dispo.items():
            s = score_map.get(m, 70)
            # r != 0 (fini) : une réserve NÉGATIVE (reprise / recours net) est une
            # donnée VALIDE et doit entrer dans le BE ; seuls les vrais échecs
            # (r == 0 par dégénérescence, ou NaN) sont exclus.
            if s >= seuil_score and np.isfinite(r) and r != 0:
                methodes_incluses[m] = (r, s)
            else:
                methodes_exclues[m]  = (r, s)

        # Garde-fou : si tout exclu → garder Chain Ladder et BF par défaut
        if not methodes_incluses:
            methodes_incluses = {
                'chain_ladder': (cl_res, 50),
                'bornhuetter_ferguson': (bf_res, 50),
            }
            # Les retirer des exclues : elles viennent d'être forcées dans les
            # incluses (sinon elles figureraient dans les deux listes).
            for _m in ('chain_ladder', 'bornhuetter_ferguson'):
                if _m in methodes_exclues:
                    del methodes_exclues[_m]
            logger.warning(
                "BE N4 : toutes les méthodes exclues (score < seuil). "
                "Fallback sur Chain Ladder + BF avec score=50."
            )

        # Forcer l'inclusion de la méthode recommandée par N2
        # même si son score est bas (le jugement actuariel prime sur le score mécanique)
        methode_rec_check = n2.get('methode_recommandee', '').lower().replace(' ', '_')
        _rec_map_check = {
            'bornhuetter_ferguson': 'bornhuetter_ferguson',
            'bf': 'bornhuetter_ferguson',
            'mack': 'chain_ladder', 'mack_1993': 'chain_ladder',  # remap : point Mack = CL
            'chain_ladder': 'chain_ladder',
            'cape_cod': 'cape_cod',
        }
        methode_rec_norm_check = _rec_map_check.get(methode_rec_check, '')
        if methode_rec_norm_check and methode_rec_norm_check not in methodes_incluses:
            # La méthode recommandée a été exclue par le seuil de score
            # On la force avec un score de 70 (score de référence)
            reserve_rec = methodes_dispo.get(methode_rec_norm_check, 0)
            if np.isfinite(reserve_rec) and reserve_rec != 0:
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
            'mack': 'chain_ladder',       # remap : point Mack = CL (garde le forçage 50% sur CL)
            'mack_1993': 'chain_ladder',
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

        # ── 3. Best Estimate — réserve brute (Art. 77 ; actualisation aval A10) ──
        # BE = Σ w_m × R_m  (réserve brute non actualisée)
        be = float(sum(
            poids[m] * r
            for m, (r, _) in methodes_incluses.items()
        ))

        # ── 3bis. BASE CHARGES : réintégration des provisions dossier ──────────
        #
        # ⚠️ CORRECTION RÉGLEMENTAIRE. Les méthodes N3 calculent toutes
        # `IBNR = ultime − dernière diagonale DU TRIANGLE QU'ON LEUR A PASSÉ`.
        # Sur un triangle de CHARGES, cette diagonale est la charge à date, donc
        # chaque R_m — et donc `be` — vaut l'IBNR PUR : il MANQUE les provisions
        # dossier, déjà comprises dans les charges mais pas encore payées. Or le
        # Best Estimate S2 (Art. 77) est l'ensemble des flux FUTURS, soit
        # `ultime − PAYÉ à date`.
        #
        #     ultime − payé  =  (ultime − charges)  +  (charges − payé)
        #     réserve totale =      IBNR pur        + provisions dossier
        #
        # Exemple : ultime 300, charge 270, payé 50
        #     sans correction : 300 − 270 =  30   ← IBNR pur, BE sous-estimé
        #     avec correction :  30 + 220 = 250   ← correct (220 = 270 − 50)
        #
        # La correction est ADDITIVE et UNIFORME : un seul point suffit, aucune
        # des 9 méthodes N3 n'est touchée. Elle est placée AVANT tout ce qui
        # dérive de `be` (σ composé, percentiles, SCR, RM, PT), qui devient donc
        # correct automatiquement.
        #
        # `provisions_dossier=None` (défaut) = base paiements : AUCUN changement.
        be_ibnr_pur = be
        if provisions_dossier:
            be += float(provisions_dossier)

        # ── 4. CV inter-méthodes ──────────────────────────────────────────────
        reserves_val = [r for r, _ in methodes_incluses.values()]
        cv_inter = (
            float(np.std(reserves_val) / max(np.mean(reserves_val), 1e-9) * 100)
            if len(reserves_val) > 1 else 0.0
        )

        # ── 5. Percentiles — Incertitude composée (Option B) ──────────────────
        #
        # Approche : σ_total² = σ_Mack² + σ_modèle²
        #
        # σ_Mack   = incertitude stochastique (England & Verrall 2002 via Mack)
        # σ_modèle = incertitude de modèle = std(réserves des méthodes incluses)
        #            mesure la dispersion entre méthodes — EIOPA TP.5.22
        #
        # Cette approche est plus rigoureuse que d'utiliser les percentiles
        # Bootstrap bruts (centrés sur BE_Bootstrap ≠ BE pondéré) et garantit
        # P90 > BE pondéré même quand les méthodes divergent fortement.
        #
        # Références :
        #   · EIOPA (2014) Guidelines TP.5.22 — risque de modèle
        #   · Mack (1993) — σ stochastique
        #   · England & Verrall (2002) — Bootstrap ODP comme alternative
        #
        _boot = n3.get('bootstrap', {})
        _boot_ok = bool(_boot.get('be_bootstrap', 0) > 0)

        # σ_modèle : std des réserves des méthodes incluses (pondérées par poids)
        # Si une seule méthode → σ_modèle = 0 (pas de dispersion inter-méthodes)
        reserves_val = [r for r, _ in methodes_incluses.values()]
        sigma_modele = (
            float(np.std(reserves_val, ddof=0))
            if len(reserves_val) > 1 else 0.0
        )

        # σ_total composé — centré sur le BE pondéré
        sigma_total_compose = float(np.sqrt(sigma ** 2 + sigma_modele ** 2))

        # Percentiles log-normale centrés sur le BE pondéré (QIS5 TP.5.26)
        # avec σ_total composé
        if sigma_total_compose > 0 and be > 0:
            cv_ln  = sigma_total_compose / be
            s2_ln  = np.log(1.0 + cv_ln ** 2)
            s_ln   = np.sqrt(s2_ln)
            m_ln   = np.log(be) - s2_ln / 2.0

            p75  = float(np.exp(m_ln + 0.6745 * s_ln))
            p90  = float(np.exp(m_ln + 1.2816 * s_ln))
            p995 = float(np.exp(m_ln + 2.5758 * s_ln))
        else:
            p75 = p90 = p995 = be

        p75_source  = 'Incertitude composée (σ_Mack + σ_modèle)'
        p90_source  = 'Incertitude composée (σ_Mack + σ_modèle)'
        p995_source = 'Incertitude composée (σ_Mack + σ_modèle)'

        # Percentiles Mack seul — centrés sur BE pondéré (pour affichage comparatif)
        if sigma > 0 and be > 0:
            cv_ln_m  = sigma / be
            s2_ln_m  = np.log(1.0 + cv_ln_m ** 2)
            s_ln_m   = np.sqrt(s2_ln_m)
            m_ln_m   = np.log(be) - s2_ln_m / 2.0
            p75_mack  = float(np.exp(m_ln_m + 0.6745 * s_ln_m))
            p90_mack  = float(np.exp(m_ln_m + 1.2816 * s_ln_m))
            p995_mack = float(np.exp(m_ln_m + 2.5758 * s_ln_m))
        else:
            p75_mack = p90_mack = p995_mack = be

        # Stocker les deux séries pour affichage comparatif dans le rapport
        p75_mack_val  = p75_mack
        p90_mack_val  = p90_mack
        p995_mack_val = p995_mack

        # Exposer σ_modèle et σ_total composé dans le dict retour
        sigma_modele_val       = round(sigma_modele, 2)
        sigma_total_compose_val = round(sigma_total_compose, 2)

        # ── 6. SCR provisions formule standard (Art. 105 S2) ──────────────────
        scr = self._calculer_scr(be, lob, cfg)

        # ── 7. Risk Margin S2 (Art. 77 §5) ───────────────────────────────────
        _f_cum  = n3.get('chain_ladder', {}).get('facteurs_cumules', [])
        _courbe = kwargs.get('courbe_rfr', None)
        if _courbe is None:
            _courbe = get_courbe_embarquee()
        _courbe['_lob'] = lob
        risk_margin_data = self._calculer_risk_margin(be, scr, _f_cum, _courbe)

        # ── 8. Sensibilités ───────────────────────────────────────────────────
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
        bz_statut_val = n3.get('glm_apc', {}).get('statut', '')
        if bz_statut_val == 'AMBRE':   # le GLM APC n'emet que VERT/AMBRE (pas de ROUGE)
            recommandations.append(
                "Effets calendaire détectés — documenter la cause (inflation, changement législatif) "
                "dans la note méthodologique S2."
            )

        # H1 rejetée → déjà dans "Point de vigilance" section 08, on ne la
        # duplique pas ici. (Les deux lectures de `h1_independance` qui vivaient
        # à cet endroit étaient mortes : `h1_corr` n'était jamais utilisée et
        # `h1_ok` était réassignée à l'identique plus bas, là où elle sert.)

        # Recommandation H4 hétéroscédasticité
        # Clé correcte : 'h4_homosc_bootstrap' (conforme n2_hypotheses.py L156)
        # Sous-clé CV : 'cv_var' (conforme n2_hypotheses.py L678)
        h4_ok = n2.get('h4_homosc_bootstrap', {}).get('ok', True)
        h4_cv = n2.get('h4_homosc_bootstrap', {}).get('cv_var', 0.0)
        if not h4_ok:
            recommandations.append(
                f"H4 Homogénéité rejetée (CV variances = {h4_cv:.2f}) — "
                "Bootstrap ODP non fiable sur ce triangle. "
                "Percentiles P99/P99.5 à interpréter avec prudence pour le Risk Margin S2."
            )

        # Recommandation Clark aberrant
        clark = n3.get('clark', {})
        if clark.get('aberrant'):
            recommandations.append(
                "Clark LDF produit un résultat aberrant — méthode exclue de la pondération. "
                "Vérifier la structure du triangle et la longueur de la queue de développement."
            )

        # Recommandation Risk Margin
        recommandations.append(
            "Risk Margin S2 calculé par la méthode proportionnelle au BE (méthode 2 EIOPA, CoC 6%). "
            "Documenter la courbe EIOPA RFR utilisée dans la note méthodologique. "
            "Vérifier la cohérence avec le Risk Margin du dernier arrêté."
        )

        # Recommandation tail factor si appliqué
        tail_info = n3.get('chain_ladder', {}).get('tail_factor', {})
        if isinstance(tail_info, dict) and tail_info.get('tail_factor', 1.0) > 1.0:
            tail_val = tail_info.get('tail_factor', 1.0)
            recommandations.append(
                f"Tail factor = {tail_val:.4f} appliqué (Guide IA 2023 — régression log-linéaire). "
                "Justifier le seuil de stabilisation retenu dans la note méthodologique S2."
            )

        def _safe_year(s):
            try: return int(s.strip()[-4:])
            except: return 0

        # Recommandation rupture sinistralité (back-testing rouge récent)
        bt_tableau = n3.get('backtesting', {}).get('tableau', [])
        annees_rouge_recentes = [
            r.get('annee_label', r.get('annee', '')) for r in bt_tableau
            if isinstance(r, dict) and r.get('mature', True)
            and abs(float(r.get('ecart_pct_n1', 0) or 0)) >= 15.0
            and _safe_year(str(r.get('annee_label', r.get('annee', '0')))) >= 2020
        ]
        if annees_rouge_recentes:
            recommandations.append(
                f"Rupture de sinistralité détectée sur les années récentes "
                f"({', '.join(str(a) for a in annees_rouge_recentes[:3])}) — "
                "écart back-testing > 15% sur N-1. Analyser la cause (inflation judiciaire, "
                "changement de portefeuille) et envisager un chargement prudentiel "
                "sur les années 2020+ avant inscription au bilan S2."
            )

        # Avis actuariel global
        h1_ok = n2.get('h1_independance', {}).get('ok', True)
        if statut == 'ROUGE' or (not h1_ok and bt_statut_val == 'ROUGE'):
            avis_actuariel = 'FAVORABLE SOUS RÉSERVE — révisions requises avant bilan S2'
        elif statut == 'AMBRE' or not h1_ok:
            avis_actuariel = 'FAVORABLE SOUS RÉSERVE — points de vigilance à documenter'
        else:
            avis_actuariel = "FAVORABLE — Best Estimate (réserve brute) robuste ; actualisation S2 opérée en aval (A10)"

        # ── 9. Jugement actuariel documenté ───────────────────────────────────
        jugement = self._documenter_jugement(
            methodes_incluses, methodes_exclues, poids,
            be, cv_inter, n2, n3, statut, scr, cfg
        )

        msg = (
            f"BE brut = {be:,.0f}€ · P90 = {p90:,.0f}€ · "
            f"CV = {cv_inter:.1f}% · σ = {sigma:,.0f}€ · "
            f"SCR_prov = {scr['scr_provisions']:,.0f}€"
        )
        logger.info(msg)

        resultat = {
            # Best Estimate
            'best_estimate':         round(be,     0),

            # Décomposition en base CHARGES — exposée pour qu'aucun lecteur ne
            # confonde les réserves PAR MÉTHODE (qui restent l'IBNR pur sur un
            # triangle de charges) avec le BE total. En base paiements,
            # provisions_dossier vaut 0 et be_ibnr_pur == best_estimate.
            # ATTENTION : la somme des deux reconstitue le BE ATTRITIONNEL, celui
            # que N4 calcule. Si l'appelant réintègre ensuite des grands sinistres
            # (LLT), il écrase `best_estimate` et conserve le pivot dans
            # `be_attritional` — c'est à lui que la décomposition se compare.
            'be_ibnr_pur':           round(be_ibnr_pur, 0),
            'provisions_dossier':    round(float(provisions_dossier or 0.0), 0),

            # Percentiles log-normale (QIS5 TP.5.26)
            'reserve_p75':           round(p75,    0),
            'reserve_p90':           round(p90,    0),
            'reserve_p99_5':         round(p995,   0),
            'reserve_p75_mack':      round(p75_mack_val,  0),
            'reserve_p90_mack':      round(p90_mack_val,  0),
            'reserve_p99_5_mack':    round(p995_mack_val, 0),
            'reserve_p75_boot':      round(float(_boot.get('p75',  p75_mack_val)), 0) if _boot_ok else None,
            'reserve_p90_boot':      round(float(_boot.get('p90',  p90_mack_val)), 0) if _boot_ok else None,
            'reserve_p99_5_boot':    round(float(_boot.get('p99_5',p995_mack_val)),0) if _boot_ok else None,
            'source_percentiles':    p90_source,

            # Incertitude composée (Option B — σ_Mack² + σ_modèle²)
            'sigma_mack':            round(sigma,  0),
            'sigma_modele':          sigma_modele_val,
            'sigma_total_compose':   sigma_total_compose_val,
            'cv_inter_methodes':     round(cv_inter, 2),

            # Méthodes
            'methodes_incluses':     list(methodes_incluses.keys()),
            'methodes_exclues':      list(methodes_exclues.keys()),
            'poids':                 poids,

            # SCR formule standard
            'scr':                   scr,

            # Risk Margin S2 (Art. 77 §5)
            'risk_margin':              risk_margin_data.get('risk_margin', 0),
            'provisions_techniques_s2': risk_margin_data.get('provisions_techniques_s2', round(be, 0)),
            'ratio_rm_be':              risk_margin_data.get('ratio_rm_be', 0),
            'date_courbe_rfr':          risk_margin_data.get('date_courbe_rfr', '—'),
            'tableau_run_off':          risk_margin_data.get('tableau_run_off', []),
            'message_rm':               risk_margin_data.get('message', ''),


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

        # ── 10. Garde-fou TOTAL — BE pondéré <= 0 (reprise nette) ──────────────
        # Chemin PRIMAIRE (sans grands sinistres) : si le BE est négatif, les
        # agrégats S2 (SCR = 3σ×BE, ratio, RM, PT, percentiles log-normaux) sont
        # non calculables → marqueurs None + statut ROUGE, jamais de plancher
        # silencieux. Le bloc LLT d'agent.py applique le même garde-fou sur le BE
        # final post-grands-sinistres. Dormant tant que les méthodes planchent.
        _garde = garde_fou_be_negatif(be)
        if _garde is not None:
            resultat['scr']['scr_provisions']    = None
            resultat['scr']['ratio_scr_be']      = None
            resultat['scr']['message']           = _garde['message']
            resultat['scr_prov']                 = None
            resultat['reserve_p75']              = None
            resultat['reserve_p90']              = None
            resultat['reserve_p99_5']            = None
            resultat['risk_margin']              = None
            resultat['provisions_techniques_s2'] = None
            resultat['ratio_rm_be']              = None
            resultat['statut']                   = 'ROUGE'
            resultat['be_negatif']               = True
            resultat['alertes']    = [_garde['message']] + list(resultat.get('alertes', []))
            resultat['message']                  = _garde['message']

        return resultat

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
    #  RISK MARGIN S2 (Art. 77 §5 — Directive Solvabilité 2)
    # =========================================================================

    def _calculer_risk_margin(
        self,
        be:     float,
        scr:    Dict,
        f_cum:  list,
        courbe: dict = None,
    ) -> Dict:
        """
        Risk Margin S2 — Méthode proportionnelle au BE (méthode 2 EIOPA).

        RM = CoC × Σ_{t=0}^{T} [ SCR_NL(t) / (1+r_t)^(t+1) ]

        SCR_NL(t) = SCR_NL(0) × BE(t) / BE(0)   [méthode 2]
        BE(t)     = BE(0) / CDF(t)               [run-off CL]
        CoC       = 6%                            [EIOPA fixé]
        r_t       = courbe EIOPA RFR EUR embarquée (Q1 2025)
        """
        COC  = 0.06
        be_0 = max(float(be), 1.0)
        scr_0 = float(scr.get('scr_provisions', 0))

        if be_0 <= 0 or scr_0 <= 0 or not f_cum:
            return {
                'risk_margin':              0.0,
                'provisions_techniques_s2': round(be_0, 0),
                'ratio_rm_be':              0.0,
                'coc':                      COC,
                'date_courbe_rfr':          DATE_COURBE,
                'tableau_run_off':          [],
                'message':                  'Risk Margin non calculable — données insuffisantes.',
            }

        m      = len(f_cum)
        rm_sum = 0.0
        tableau = []

        # f_cum est dans l'ordre [CDF_dernière_col, ..., CDF_1ère_col]
        # CDF le plus grand en premier (période la moins développée)
        # Pour le run-off : à l'année t, la proportion de BE résiduelle est
        # approximée par la part des IBNR qui ne seront pas encore développés
        # Méthode : utiliser les pct_developpe pour projeter le run-off
        # pct_dev[i] = % développé de l'année i → IBNR[i] = BE[i] × (1 - pct_dev[i])
        # À t=1 : les années qui se développent d'un pas → recalculer pct_dev
        # 
        # Simplification (méthode 2 EIOPA) : run-off proportionnel aux LDF
        # BE(t) = BE(0) × facteur_run_off(t)
        # facteur_run_off(t) = Σ_j [ 1/f_cum[max(0, m-1-j+t)] ] pour j=0..n
        #
        # Projection BE en run-off — méthode pct résiduel par CDF (décroissant)
        # pct_résiduel[j] = 1/f_cum[j] → proportion encore à développer à la colonne j
        # BE(t) = BE(0) × Σ_{j≥t} pct_résiduel[j] / Σ_j pct_résiduel[j]
        pct_res  = [1.0 / max(float(f), 1.0) for f in f_cum]
        total_pr = max(sum(pct_res), 1e-10)
        m_rm     = len(pct_res)
        be_par_t = []
        for _t in range(m_rm + 15):
            if _t == 0:
                be_par_t.append(be_0)
            elif _t < m_rm:
                be_par_t.append(be_0 * sum(pct_res[_t:]) / total_pr)
            else:
                be_par_t.append(0.0)

        for t, be_t in enumerate(be_par_t):
            if be_t < be_0 * 0.001:
                break

            # SCR projeté (méthode 2 — proportionnel au BE)
            scr_t    = scr_0 * (be_t / be_0)
            r_t      = get_taux_rfr(t + 1)
            fact_act = 1.0 / (1.0 + r_t) ** (t + 1)
            contrib  = COC * scr_t * fact_act
            rm_sum  += contrib

            tableau.append({
                'annee':      t,
                'be_t':       round(be_t,    0),
                'scr_t':      round(scr_t,   0),
                'taux_rfr':   round(r_t * 100, 4),
                'fact_act':   round(fact_act,  6),
                'contrib_rm': round(contrib,   0),
            })

        risk_margin = round(rm_sum, 0)
        pt_s2       = round(be_0 + risk_margin, 0)
        ratio_rm_be = round(risk_margin / be_0 * 100, 2)

        return {
            'risk_margin':              risk_margin,
            'provisions_techniques_s2': pt_s2,
            'ratio_rm_be':              ratio_rm_be,
            'coc':                      COC,
            'date_courbe_rfr':          DATE_COURBE,
            'tableau_run_off':          tableau,
            'message': (
                f"Risk Margin = {risk_margin:,.0f}€ ({ratio_rm_be:.1f}% du BE). "
                f"Provisions Techniques S2 = {pt_s2:,.0f}€. "
                f"CoC=6%, courbe EIOPA RFR EUR du {DATE_COURBE}. "
                f"Méthode proportionnelle au BE (méthode 2 EIOPA, Art. 77 §5)."
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
            "3. BEST ESTIMATE — RÉSERVE BRUTE (Art. 77 ; actualisation S2 par A10)",
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
