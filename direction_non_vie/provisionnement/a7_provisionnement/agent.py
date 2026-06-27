# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  agent.py  —  Classe principale AgentA7Provisionnement
# =============================================================================
#
#  Pipeline complet N1 → N2 → N3 → N4 → N5 :
#
#  N1 — Ingestion & validation (n1_ingestion.TriangleValidator)
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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# ── Imports modules A7 ───────────────────────────────────────────────────────
from direction_non_vie.services.nv_triangle_validator import TriangleValidator
from .n2_hypotheses     import HypothesesValidator
from .n4_best_estimate  import BestEstimateS2
from .n5_graphiques     import generer_graphiques
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
from .n3.barnett_zehnwirth   import barnett_zehnwirth

logger = logging.getLogger('actuaria.a7')


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
    graphiques, commentaire
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

        # Sous-modules
        self._tv  = TriangleValidator(verbose=verbose)
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
        n_sim_bootstrap:  int           = 5000,
        seed:             int           = 42,
        generer_graphiques_flag: bool   = True,
        generer_word:     bool          = True,
        generer_pdf_flag: bool          = True,
        # ── Compatibilité ancienne API ────────────────────────────────────────
        triangle                        = None,
        result_a2                       = None,
        mode_declare:     str           = 'auto',
        taux_bf_manuel: Optional[float] = None,   # alias lr_bf_manuel
        generer_graphiques: bool        = True,    # alias generer_graphiques_flag
        annee_debut:      Optional[int]  = None,   # année calendaire de la 1ère ligne
        **kwargs,
    ) -> Dict:
        """
        Pipeline complet N1 → N2 → N3 → N4 → N5.

        Tous les paramètres sont optionnels sauf source.
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

            C, C_engage, primes_norm, n1_rapport = self._tv.charger(
                source          = source,
                mode            = mode_declare,
                triangle_engage = triangle_engage,
                primes          = primes,
                schema_mapping  = schema_mapping,
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
                logger.info("N2 — Validation hypothèses H1/H2/H3/H4")

            n2 = self._hv.valider(C_calc, primes=primes_norm, lob=lob)

            # CORRECTION BUG v4.0 :
            # methode_cl_retenue est maintenant dans n2 directement
            # (calculé par HypothesesValidator._choisir_variante_cl)
            if methode_cl == 'auto':
                methode_cl_retenue = n2['methode_cl_retenue']
            else:
                methode_cl_retenue = methode_cl
                n2['methode_cl_retenue'] = methode_cl_retenue

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
                logger.info("N4 — Best Estimate S2 + SCR provisions")

            # Back-testing boni/mali (calculé ici avec C_calc)
            try:
                n3['backtesting'] = calculer_backtesting(C_calc, annee_debut=annee_debut)
            except Exception as _ebt:
                logger.warning(f"Back-testing ignoré : {_ebt}")
                n3['backtesting'] = {}
            # Effets calendaire Barnett-Zehnwirth
            try:
                n3['barnett_zehnwirth'] = barnett_zehnwirth(C_calc, annee_debut=annee_debut, annee_base=annee_base_reserve)
            except Exception as _ebz:
                logger.warning(f"Barnett-Zehnwirth ignoré : {_ebz}")
                n3['barnett_zehnwirth'] = {}
            # Année début pour labels calendaires (G14)
            if annee_debut:
                n3['annee_debut_triangle'] = annee_debut

            n4 = self._be.calculer(n2, n3, C_calc, lob=lob)

            if self.verbose:
                logger.info(
                    f"N4 OK | BE={n4['best_estimate']:,.0f}€ "
                    f"P90={n4['reserve_p90']:,.0f}€ "
                    f"CV={n4['cv_inter_methodes']:.1f}% "
                    f"SCR={n4['scr']['scr_provisions']:,.0f}€"
                )

            # =================================================================
            # N5 — LIVRABLES
            # =================================================================
            if self.verbose:
                logger.info("N5 — Génération livrables")

            # Graphiques Plotly
            graphiques_dict = {}
            if gen_g:
                try:
                    graphiques_dict = generer_graphiques(C_calc, n2, n3, n4)
                    if self.verbose:
                        logger.info(f"N5 — {len(graphiques_dict)}/12 graphiques")
                except Exception as e:
                    logger.warning(f"N5 graphiques échoués : {e}")

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
                'n1': {}, 'n2': {}, 'n3': {}, 'n4': {},
            }

    # =========================================================================
    #  N3 — ORCHESTRATEUR DES MÉTHODES
    # =========================================================================

    def _calculer_n3(
        self,
        C:               np.ndarray,
        C_engage:        Optional[np.ndarray],
        primes:          Optional[np.ndarray],
        methode_cl:      str,
        lr_bf_manuel:    Optional[float],
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
            lob_tail_max_alerte = cfg_lob.get('tail_factor_max_alerte', 1.05),
        )

        # ── Facteurs cumulés + % développé ────────────────────────────────────
        f_cum   = calculer_facteurs_cumules(facteurs, tail_info['tail_factor'])
        pct_dev = calculer_pct_developpe(C, f_cum)

        # ── Chain Ladder ──────────────────────────────────────────────────────
        r_cl = chain_ladder(
            C                  = C,
            methode            = methode_cl,
            annee_base_reserve = annee_base,
            lob_tail_max_alerte= cfg_lob.get('tail_factor_max_alerte', 1.05),
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
        r_bf = bornhuetter_ferguson(
            C              = C,
            pct_dev        = pct_dev,
            last_diag      = ld,
            ultimates_cl   = ult_cl,
            primes         = primes,
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
            ultimates_cl   = ult_cl,
            primes         = primes,
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
            'barnett_zehnwirth': {},
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
