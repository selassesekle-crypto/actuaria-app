"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      ACTUARIA — AGENT A10 ELENA : SOLVABILITÉ 2 NON-VIE v2.0 DÉFINITIVE  ║
║                     Sous NADIA (Direction Non-Vie)                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  NOUVEAUTÉS v2 :                                                             ║
║    ✅ MCR complet (linéaire + bornes 25%/45% SCR + plancher 2.5M€)         ║
║    ✅ Réassurance configurable (XL + Quote-Part)                            ║
║    ✅ 3 niveaux SCR (standard / recalibration σ / modèle interne)          ║
║    ✅ Courbe des taux 3 points (RFR 5/10/20 ans)                           ║
║    ✅ Multi-branches avec agrégation inter-LoB EIOPA                       ║
║    ✅ Allocation actif configurable                                         ║
║    ✅ Fonds propres par tier (Tier 1/2/3) + éligibilité MCR                ║
║    ✅ Risk Margin méthode duration-based EIOPA Art.58                      ║
║    ✅ Validation σ client (bornes 40%-200% EIOPA)                          ║
║                                                                              ║
║  SORTIES VERS A9 MARCUS :                                                   ║
║    provisions.best_estimate → C4 | provisions.risk_margin → C4             ║
║    duration.passif → C5 | capital.scr_total → C2 | capital.mcr → C2       ║
║                                                                              ║
║  VERSION : 2.0 DÉFINITIVE — 19/06/2026                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

ÉTAT DES SOURCES RÉGLEMENTAIRES (lot B10-b)
───────────────────────────────────────────
VÉRIFIÉ contre le Règlement délégué (UE) 2015/35 consolidé au 02.08.2022 :
  · les écarts types σ_prime et σ_réserve — annexes II p.389 et XIV p.430,
    désormais DÉRIVÉS de `reglementation/segments_s2.py` et non plus saisis ;
  · la combinaison σ_s de `_scr_fs` — article 117(2), terme croisé compris ;
  · la matrice de corrélation entre segments — annexe IV, conformément au
    renvoi de l'article 117(1)(c). Citation d'origine JUSTE, conservée.

NON VÉRIFIÉ, ET SIGNALÉ COMME TEL — la source n'était plus disponible à la
clôture du lot, et une citation qu'on ne peut pas remonter ne doit pas passer
pour une citation vérifiée :
  · « Risk Margin duration-based Art. 58 » : la marge de risque est définie à
    l'article 77(5) de la DIRECTIVE 2009/138/CE, que cite A7 ; le renvoi à un
    article 58 n'a pas pu être confronté au texte ;
  · « bornes 40 %-200 % » sur le σ client : les paramètres propres à
    l'entreprise relèvent d'un régime d'approbation dédié, non confronté ici ;
  · les facteurs catastrophe `F_CAT_LOB`, isolés à cet effet — cf. leur bloc.
"""

import json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple   # Any/List/Optional etaient importes sans usage
import numpy as np

from ..segments_s2 import (SEGMENTS_S2, libelle_reference,
                           verifier_rattachements)

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"; OR="#C9A84C"
BLANC="#F0F4F8"; GRIS="#8A9AB0"; VERT="#2ECC71"; ROUGE="#E74C3C"
AMBRE="#F39C12"; BLEU="#3498DB"; VIOLET="#9B59B6"; TURQUOISE="#1ABC9C"

LAYOUT_BASE = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16,r=16,t=60,b=60), height=320,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))

# ── Écarts types réglementaires ──────────────────────────────────────────────
#
#  LES σ NE SONT PLUS SAISIS ICI. Ils sont DÉRIVÉS de la table partagée
#  `direction_non_vie/reglementation/segments_s2.py`, qui porte la source
#  (Règlement délégué (UE) 2015/35 consolidé au 02.08.2022, annexe II p.389
#  et annexe XIV p.430) et les articles applicables.
#
#  POURQUOI CE LOT A EXISTÉ (B10-b). A10 détenait sa propre copie de cette
#  table et A7 la sienne ; elles avaient divergé sans que rien ne le voie.
#  Sur 22 entrées, A10 n'avait que 7 σ_prime et 9 σ_réserve justes, et
#  SEULEMENT 5 justes sur les DEUX colonnes. Pire, A10 se contredisait
#  lui-même : le segment II-4 « incendie » recevait trois σ différents selon
#  qu'on l'appelait `mrh` (0,07/0,10), `incendie` (0,08/0,11) ou
#  `catastrophes_naturelles` (0,10/0,20), et le segment II-5 « RC générale »
#  en recevait trois aussi. Le même segment réglementaire ne peut pas avoir
#  trois écarts types : c'est désormais structurellement impossible.
#
#  A10 EMPLOIE LES DEUX COLONNES, contrairement à A7. Il calcule le module
#  COMPLET primes + réserve de l'article 117(2) — cf. `_scr_souscription`.
#
#  ⚠️ LE COMMENTAIRE « sigma calibres EIOPA Annexe II » PORTÉ PAR LES
#  BRANCHES LONGUES ÉTAIT FAUX : 0,13/0,11 n'est le couple d'aucun segment
#  de l'annexe II (la RC générale y vaut 0,14/0,11).
SEGMENT_PAR_LOB: Dict[str, Tuple[str, int]] = {
    'rc_auto':                   ('II',  1),
    'rc_auto_materiel':          ('II',  1),
    'rc_auto_corporels':         ('II',  1),
    'auto_autre':                ('II',  2),
    'transport':                 ('II',  3),
    'marine_aviation_transport': ('II',  3),
    'incendie':                  ('II',  4),
    'incendie_dommages':         ('II',  4),
    'mrh':                       ('II',  4),
    # Le risque de RÉSERVE d'un portefeuille cat-nat est celui de tout dommage
    # aux biens. Le risque de CATASTROPHE proprement dit — les événements
    # futurs — est un module distinct (art. 119 et suivants) : cf. `f_cat`.
    'catastrophes_naturelles':   ('II',  4),
    'rc_generale':               ('II',  5),
    # Ni « construction » ni « RC professionnelle » ne sont des segments :
    # la décennale et la RC médicale relèvent de la RC générale (ligne 8).
    'construction':              ('II',  5),
    'rc_medicale':               ('II',  5),
    # ⚠️ `corporels_graves` et `dommage_corporel_individuel` se ressemblent
    # mais ne relèvent PAS du même segment, et c'est délibéré. Le premier est
    # une CATÉGORIE DE SINISTRES au sein de la responsabilité civile — c'est
    # ainsi que CORR_LOB le traite déjà, en le corrélant à rc_generale et
    # rc_medicale. Le second est un PRODUIT vendu à un particulier, qui sert
    # des rentes : santé non-SLT, comme dans A7 (lot B10-a).
    'corporels_graves':          ('II',  5),
    'dommage_corporel_individuel': ('XIV', 2),
    'credit':                    ('II',  6),
    'credit_caution':            ('II',  6),
    'protection_juridique':      ('II',  7),
    'assistance':                ('II',  8),
    'pertes_pecuniaires':        ('II',  9),
    # Repli quand la branche n'est pas reconnue : RC générale, comme la LoB
    # `generique` d'A7. Ce n'est PAS une valeur réglementaire, c'est un choix.
    'generique':                 ('II',  5),
}

#  ⚠️ CE QUI SUIT N'EST PAS DANS LES ANNEXES II ET XIV, ET N'EST PAS VÉRIFIÉ.
#  Le facteur catastrophe est appliqué comme `f_cat × V_primes`, alors que le
#  module catastrophe non-vie du Règlement délégué (art. 119 et suivants) a
#  une tout autre structure. Ces valeurs n'ont pas de source identifiée dans
#  le dépôt et n'ont PAS pu être confrontées au texte dans le lot B10-b, qui
#  porte sur les écarts types. Elles sont conservées TELLES QUELLES et isolées
#  ici pour que la frontière de provenance soit visible : au-dessus, le texte ;
#  ici, des valeurs à auditer.
F_CAT_LOB: Dict[str, float] = {
    'rc_auto': 0.15, 'rc_auto_materiel': 0.15, 'rc_auto_corporels': 0.15,
    'auto_autre': 0.10, 'transport': 0.15, 'marine_aviation_transport': 0.15,
    'incendie': 0.25, 'incendie_dommages': 0.25, 'mrh': 0.25,
    'catastrophes_naturelles': 0.50, 'rc_generale': 0.15, 'construction': 0.20,
    'rc_medicale': 0.15, 'corporels_graves': 0.15,
    'dommage_corporel_individuel': 0.15, 'credit': 0.10, 'credit_caution': 0.10,
    'protection_juridique': 0.05, 'assistance': 0.08, 'pertes_pecuniaires': 0.15,
    'generique': 0.15,
}

#: Construit au chargement à partir de SEGMENT_PAR_LOB — cf. `_construire_sigma_lob`.
SIGMA_LOB: Dict[str, Dict[str, float]] = {}

CORR_LOB = {
    # Correlations EIOPA — Annexe IV Reglement Delegue 2015/35
    frozenset(['rc_auto',      'auto_autre']):         0.50,
    frozenset(['incendie',     'mrh']):                0.50,
    frozenset(['rc_auto',      'rc_generale']):        0.50,
    frozenset(['rc_generale',  'rc_medicale']):        0.50,
    frozenset(['rc_auto',      'rc_medicale']):        0.25,
    frozenset(['incendie',     'construction']):       0.25,
    frozenset(['rc_generale',  'construction']):       0.25,
    frozenset(['transport',    'rc_auto']):            0.25,
    frozenset(['corporels_graves', 'rc_medicale']):    0.25,
    frozenset(['corporels_graves', 'rc_generale']):    0.25,
    frozenset(['rc_auto_corporels', 'rc_medicale']):   0.50,
    frozenset(['rc_auto_corporels', 'rc_auto_materiel']): 0.50,
    frozenset(['dommage_corporel_individuel', 'rc_medicale']): 0.25,
    frozenset(['incendie_dommages', 'construction']): 0.25,
    frozenset(['incendie_dommages', 'mrh']): 0.50,
    frozenset(['credit_caution', 'rc_generale']): 0.25,
    # Paires non listees : correlation par defaut 0.25 (conservateur EIOPA)
}

CORR_MODULES = np.array([[1.00,0.25,0.25],[0.25,1.00,0.25],[0.25,0.25,1.00]])

MCR_ALPHA = 0.0418; MCR_BETA = 0.0261; MCR_PLANCHER_ABS = 2_500_000.0
COC = 0.06

DURATION_LOB = {
    # Durees moyennes de liquidation par branche (en annees)
    # Source : pratique de marche + Guide IA 2023
    'rc_auto':               4.0,
    'auto_autre':            2.5,
    'mrh':                   2.0,
    'incendie':              3.0,
    'rc_generale':           6.0,
    'construction':          10.0,  # Garantie decennale — queue 10 ans minimum
    'transport':             3.0,
    'credit':                3.0,
    'assistance':            1.5,
    'protection_juridique':  4.0,
    'pertes_pecuniaires':    3.0,
    # Branches longues — queues lourdes reglementaires
    'rc_medicale':           17.0,  # Erreurs medicales, revelation tardive : 15-20 ans
    'corporels_graves':      20.0,  # Rentes versageres, prejudices corporels : 15-25 ans
    # Branches supplementaires lob_config.py (nomenclature A7)
    'catastrophes_naturelles':    3.0,   # Cat Nat : liquidation rapide post-sinistre
    'marine_aviation_transport':  3.0,   # Identique transport
    'incendie_dommages':          3.0,   # Identique incendie
    'credit_caution':             3.0,   # Identique credit
    'dommage_corporel_individuel':15.0,  # Queue longue — voir corporels_graves
    'rc_auto_materiel':           2.5,   # Queue courte — materiel uniquement
    'rc_auto_corporels':          8.0,   # Queue longue — corporels
    'generique':                  4.0,   # Defaut generique
    # Defaut si branche inconnue : 4.0 ans (voir DURATION_LOB.get(n, 4.0))
    # ATTENTION : toujours verifier que la branche est mappee ici
}

TAUX_DEFAUT = {
    'rfr_5ans':0.0310,'rfr_10ans':0.0320,'rfr_20ans':0.0330,
    'oat_10ans':0.0365,'inflation':0.0240,'ufr':0.0330,
}

BRANCHE_MAP = {
    'rc_auto':                 'rc_auto',
    'auto':                    'rc_auto',
    'automobile':              'rc_auto',
    'mrh':                     'mrh',
    'habitation':              'mrh',
    'incendie':                'incendie',
    'fire':                    'incendie',
    'construction':            'construction',
    'dommages_ouvrage':        'construction',
    'rc_generale':             'rc_generale',
    'rc':                      'rc_generale',
    'transport':               'transport',
    'auto_autre':              'auto_autre',
    'credit':                  'credit',
    'assistance':              'assistance',
    'protection_juridique':    'protection_juridique',
    'pertes_pecuniaires':      'pertes_pecuniaires',
    # Branches longues
    'rc_medicale':             'rc_medicale',
    'responsabilite_medicale': 'rc_medicale',
    'corporels_graves':        'corporels_graves',
    'corporel_grave':          'corporels_graves',
    'prejudice_corporel':      'corporels_graves',
    # Nomenclature lob_config.py (A7) -> nomenclature A10
    'rc_auto_materiel':            'rc_auto_materiel',
    'rc_auto_corporels':           'rc_auto_corporels',
    'marine_aviation_transport':   'marine_aviation_transport',
    'marine':                      'marine_aviation_transport',
    'aviation':                    'marine_aviation_transport',
    'incendie_dommages':           'incendie_dommages',
    'catastrophes_naturelles':     'catastrophes_naturelles',
    'cat_nat':                     'catastrophes_naturelles',
    'catnat':                      'catastrophes_naturelles',
    'credit_caution':              'credit_caution',
    'caution':                     'credit_caution',
    'dommage_corporel_individuel': 'dommage_corporel_individuel',
    'dommage_corporel':            'dommage_corporel_individuel',
    # `accidents_corporels` est une LoB d'A7 qui ne figurait dans AUCUN
    # BRANCHE_MAP : elle tombait donc au repli (`rc_auto` pour A10). A7 la
    # rattache au segment XIV-2, comme `dommage_corporel_individuel` avec
    # laquelle elle partage deja son sigma -- trou comble au lot B10-c.
    'accidents_corporels':         'dommage_corporel_individuel',
    'generique':                   'generique',
}


def _construire_sigma_lob() -> None:
    """Remplit SIGMA_LOB depuis la table officielle, au chargement du module.

    Trois contrôles y sont faits, et chacun LÈVE plutôt que de laisser passer
    une valeur silencieusement fausse — c'est ce qui manquait :
      1. tout segment désigné existe bien aux annexes II ou XIV ;
      2. toute branche atteignable par BRANCHE_MAP a un rattachement ;
      3. tout rattachement a son facteur catastrophe.
    Le contrôle 2 est la raison pour laquelle cette fonction est appelée ICI
    et non plus haut : elle a besoin de BRANCHE_MAP.
    """
    verifier_rattachements(SEGMENT_PAR_LOB, origine="A10 SEGMENT_PAR_LOB")
    orphelines = sorted(set(BRANCHE_MAP.values()) - set(SEGMENT_PAR_LOB))
    if orphelines:
        raise KeyError(f"A10 : branches atteignables sans segment S2 : {orphelines}")
    sans_cat = sorted(set(SEGMENT_PAR_LOB) - set(F_CAT_LOB))
    if sans_cat:
        raise KeyError(f"A10 : branches sans facteur catastrophe : {sans_cat}")
    for cle, segment in SEGMENT_PAR_LOB.items():
        seg = SEGMENTS_S2[segment]
        SIGMA_LOB[cle] = {'sigma_prem': seg.sigma_prime,
                          'sigma_res':  seg.sigma_reserve,
                          'f_cat':      F_CAT_LOB[cle],
                          'segment_s2': segment,
                          'reference_s2': libelle_reference(segment)}


_construire_sigma_lob()

PD_MAP = {'AAA':0.001,'AA':0.001,'A':0.003,'BBB':0.010,'BB':0.050}


# ══════════════════════════════════════════════════════════════════════════════
class AgentA10Solvabilite2:
    """Agent A10 Elena — Solvabilité 2 Non-Vie v2.0 DÉFINITIVE."""
    NOM="Elena"; CODE="A10"; VERSION="2.0"; RESPONSABLE="NADIA (Réglementation)"

    def __init__(self, audit_path='/tmp/actuaria',
                 verbose=True):
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger('actuaria.a10.elena')
        self.verbose = verbose
        if verbose:
            self.logger.info(f"A10 Elena v{self.VERSION} | {self.RESPONSABLE}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self, result_a7, result_a6=None, market_data=None,
            branches=None, sous_branche='rc_auto',
            mode_scr='formule_standard', sigma_client=None, modele_interne=None,
            reassurance=None, fonds_propres=0.0, tiers_fpp=None,
            duration_actif=3.5, allocation_actif=None,
            generer_graphiques=True) -> Dict:
        t0 = datetime.now()
        aid = f"A10_{t0.strftime('%Y%m%d_%H%M%S')}"
        self.logger.info(f"[{aid}] mode={mode_scr}")
        try:
            taux     = self._taux(market_data)
            branches = self._branches(branches, sous_branche, result_a7, result_a6)
            reass    = self._reassurance(reassurance, branches)
            be_act   = self._actualiser_be(branches, taux)
            rm       = self._risk_margin(branches, be_act, taux)
            scr_sous = self._scr_souscription(branches, mode_scr, sigma_client,
                                               modele_interne, reass)
            scr_mkt  = self._scr_marche(be_act, taux, duration_actif,
                                         allocation_actif, mode_scr, modele_interne)
            scr_ctp  = self._scr_contrepartie(branches, reass)
            scr_ope  = self._scr_operationnel(branches, scr_sous, mode_scr, modele_interne)
            scr_tot  = self._agregation(scr_sous, scr_mkt, scr_ctp, scr_ope)
            mcr      = self._mcr(branches, scr_tot)
            capital  = self._capital(fonds_propres, tiers_fpp, be_act, rm, scr_tot, mcr)
            dur      = self._duration(branches, taux)
            qrt      = self._qrt(be_act, rm, scr_sous, scr_mkt, scr_ctp,
                                  scr_ope, scr_tot, mcr, capital, taux, reass)
            rag, motif = self._rag(capital, mcr, scr_sous, taux, mode_scr)
            hyp      = self._hypotheses(taux, branches, be_act, scr_sous,
                                         capital, mcr, mode_scr, reass)
            com      = self._commentaire(rag, capital, mcr, scr_tot, scr_sous,
                                          scr_mkt, rm, be_act, taux, branches,
                                          mode_scr, reass, hyp)
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(be_act, rm, scr_sous, scr_mkt, scr_ctp,
                                        scr_ope, scr_tot, mcr, capital, taux,
                                        branches, reass)
            self._audit(aid, branches, capital, mcr, scr_tot, rag, mode_scr)
            if self.verbose:
                self._console(aid, capital, mcr, scr_tot, scr_sous, rm, be_act, rag, com)
            duree = (datetime.now() - t0).total_seconds()
            return {
                'success':True, 'agent':self.NOM, 'version':self.VERSION,
                'audit_id':aid, 'mode_scr':mode_scr,
                'statut_rag':rag, 'motif_rag':motif,
                'provisions':{
                    'best_estimate': be_act['be_s2_total'],
                    'be_brut':       be_act['be_brut_total'],
                    'impact_taux':   be_act['impact_total'],
                    'risk_margin':   rm['risk_margin'],
                    'tp_s2':         be_act['be_s2_total'] + rm['risk_margin'],
                    'par_branche':   be_act['par_branche'],
                },
                'duration':{
                    'passif':      dur['dur_ponderee'],
                    'actif':       duration_actif,
                    'gap':         abs(duration_actif - dur['dur_ponderee']),
                    'par_branche': dur['par_branche'],
                },
                'scr':{
                    'souscription':     scr_sous['scr_souscription'],
                    'souscription_net': scr_sous['scr_souscription_net'],
                    'scr_prem':         scr_sous['scr_prem'],
                    'scr_res':          scr_sous['scr_res'],
                    'scr_cat':          scr_sous['scr_cat'],
                    'marche':           scr_mkt['scr_marche'],
                    'contrepartie':     scr_ctp['scr_contrepartie'],
                    'operationnel':     scr_ope['scr_operationnel'],
                    'bscr':             scr_tot['bscr'],
                    'total':            scr_tot['scr_total'],
                },
                'mcr':{
                    'mcr':          mcr['mcr'],
                    'mcr_lineaire': mcr['mcr_lineaire'],
                    'plancher':     mcr['plancher'],
                    'plafond':      mcr['plafond'],
                    'ratio_mcr':    capital['ratio_mcr'],
                    'statut_mcr':   capital['statut_mcr'],
                    'regime':       mcr['regime'],
                },
                'capital':{
                    'fonds_propres':     capital['fonds_propres'],
                    'tier1':             capital['tier1'],
                    'tier2':             capital['tier2'],
                    'tier3':             capital['tier3'],
                    'fpp_eligible_scr':  capital['fpp_scr'],
                    'fpp_eligible_mcr':  capital['fpp_mcr'],
                    'scr_total':         scr_tot['scr_total'],
                    'mcr':               mcr['mcr'],
                    'ratio_scr':         capital['ratio_scr'],
                    'ratio_mcr':         capital['ratio_mcr'],
                    'marge_scr':         capital['marge_scr'],
                    'marge_mcr':         capital['marge_mcr'],
                    'statut_ratio':      capital['statut_ratio'],
                    'statut_mcr':        capital['statut_mcr'],
                },
                'reassurance': reass,
                'taux':        taux,
                'qrt_s25':     qrt,
                'detail':{'be_act':be_act,'rm':rm,'scr_sous':scr_sous,
                           'scr_mkt':scr_mkt,'scr_ctp':scr_ctp,'scr_ope':scr_ope,
                           'scr_tot':scr_tot,'mcr':mcr,'branches':branches,'dur':dur},
                'hypotheses':  hyp,
                'commentaire': com,
                'graphiques':  gph,
                'duree_sec':   round(duree,2),
                'erreur':      None,
            }
        except Exception as e:
            self.logger.error(f"[{aid}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), aid)

    # ══════════════════════════════════════════════════════════════════════════
    # TAUX — COURBE 3 POINTS
    # ══════════════════════════════════════════════════════════════════════════
    def _taux(self, md):
        if md and isinstance(md, dict):
            r5  = md.get('rfr_5ans',  {}).get('valeur', TAUX_DEFAUT['rfr_5ans'])
            r10 = md.get('rfr_10ans', {}).get('valeur', TAUX_DEFAUT['rfr_10ans'])
            r20 = md.get('rfr_20ans', {}).get('valeur', TAUX_DEFAUT['rfr_20ans'])
            oat = md.get('oat_10ans', {}).get('valeur', TAUX_DEFAUT['oat_10ans'])
            inf = md.get('macro',{}).get('inflation', TAUX_DEFAUT['inflation'])
            src = md.get('source_globale','market_data')
            fib = md.get('fiabilite','REFERENCE')
            dat = md.get('date_collecte','19/06/2026')
        else:
            r5,r10,r20 = TAUX_DEFAUT['rfr_5ans'],TAUX_DEFAUT['rfr_10ans'],TAUX_DEFAUT['rfr_20ans']
            oat = TAUX_DEFAUT['oat_10ans']; inf = TAUX_DEFAUT['inflation']
            src='FALLBACK_REFERENCE (19/06/2026)'; fib='REFERENCE'; dat='19/06/2026'
            self.logger.warning(f"market_data absent — courbe référence RFR5={r5:.3%} RFR10={r10:.3%} RFR20={r20:.3%}")
        r5=max(0.0001,min(r5,0.15)); r10=max(0.0001,min(r10,0.15)); r20=max(0.0001,min(r20,0.15))
        va = max(0.0, oat - r10)
        return {'rfr_5ans':r5,'rfr_10ans':r10,'rfr_20ans':r20,'rfr':r10,
                'rfr_va':r10+va,'oat':oat,'va':va,'ufr':TAUX_DEFAUT['ufr'],
                'inflation':inf,'source':src,'fiabilite':fib,'date':dat}

    def _rfr_dur(self, dur, taux):
        r5,r10,r20 = taux['rfr_5ans'],taux['rfr_10ans'],taux['rfr_20ans']
        if dur<=5:   return r5
        elif dur<=10: return r5 + (dur-5)/5*(r10-r5)
        elif dur<=20: return r10 + (dur-10)/10*(r20-r10)
        else:         return r20

    # ══════════════════════════════════════════════════════════════════════════
    # BRANCHES
    # ══════════════════════════════════════════════════════════════════════════
    def _branches(self, branches, sous_branche, result_a7, result_a6):
        be7    = result_a7.get('best_estimate',{})
        be_tot = be7.get('best_estimate',0.0)
        n_tri  = result_a7.get('meta',{}).get('n_annees',8)
        nb_l   = result_a7.get('meta',{}).get('nb_lignes',50000)
        prim_tot = 0.0
        if result_a6:
            mp = result_a6.get('modele_production',{})
            prim_tot = mp.get('primes_acquises',
                       mp.get('prime_pure',0.0)/0.70*nb_l*0.80)
        def norm(nom):
            return BRANCHE_MAP.get(nom.lower().replace(' ','_').replace('-','_'),'rc_auto')
        def sigma(nom):
            # Indexation DIRECTE, sans repli : `norm` ne rend qu'une cible de
            # BRANCHE_MAP, et `_construire_sigma_lob` lève au chargement si une
            # cible n'a pas de segment. L'ancien `SIGMA_DEFAULT` (0,10/0,11,
            # sans source) était donc inatteignable — un repli mort qui
            # ressemblait à un garde-fou.
            return SIGMA_LOB[nom]
        if branches:
            res=[]; be_f=sum(b.get('be',0) for b in branches)
            for b in branches:
                n=norm(b.get('nom','rc_auto')); s=sigma(n)
                be_b=b.get('be',be_tot/len(branches) if be_f==0 else 0.0)
                res.append({'nom':n,'be':be_b,
                    'primes':b.get('primes',prim_tot/len(branches)),
                    'sigma_prem':s['sigma_prem'],'sigma_res':s['sigma_res'],
                    'f_cat':s['f_cat'],'duration':DURATION_LOB.get(n,4.0),
                    'n_tri':b.get('n_tri',n_tri)})
            return res
        else:
            n=norm(sous_branche); s=sigma(n)
            return [{'nom':n,'be':be_tot,'primes':prim_tot,
                'sigma_prem':s['sigma_prem'],'sigma_res':s['sigma_res'],
                'f_cat':s['f_cat'],'duration':DURATION_LOB.get(n,4.0),'n_tri':n_tri}]

    # ══════════════════════════════════════════════════════════════════════════
    # RÉASSURANCE
    # ══════════════════════════════════════════════════════════════════════════
    def _reassurance(self, r, branches):
        be = sum(b['be'] for b in branches)
        if not r:
            return {'type':'aucune','taux_cession':0.0,'reduction_scr':0.0,
                    'reass_recuperable':0.0,'rating_reassureur':'A','pd':0.003,
                    'lgd':0.0,'description':'Pas de réassurance'}
        rt    = r.get('type','aucune').lower()
        rating= r.get('rating_reassureur','A')
        pd    = PD_MAP.get(rating,0.005)
        if rt=='xl':
            portee = r.get('portee', be*0.30)
            tc     = r.get('taux_cession',0.70)
            recup  = min(portee*tc, be*0.40)
            reduc  = min(tc*0.60, 0.45)
            desc   = f"XL portée={portee:,.0f}€ cession={tc:.0%} réassureur {rating}"
        elif rt=='quote_part':
            tc     = r.get('taux_cession',0.30)
            recup  = be*tc
            reduc  = tc*0.85
            desc   = f"Quote-part cession={tc:.0%} réassureur {rating}"
        else:
            tc=0.0; recup=0.0; reduc=0.0; desc='Type non reconnu'
        return {'type':rt,'taux_cession':tc,'reduction_scr':reduc,
                'reass_recuperable':recup,'rating_reassureur':rating,
                'pd':pd,'lgd':recup*0.50,'description':desc}

    # ══════════════════════════════════════════════════════════════════════════
    # ACTUALISATION BE MULTI-BRANCHES (COURBE 3 POINTS)
    # ══════════════════════════════════════════════════════════════════════════
    def _actualiser_be(self, branches, taux):
        par=[]; be_brut=be_s2=imp=0.0
        for b in branches:
            rfr = self._rfr_dur(b['duration'],taux)
            f   = 1.0/(1+rfr)**b['duration']
            bs  = b['be']*f; ib=bs-b['be']
            be_brut+=b['be']; be_s2+=bs; imp+=ib
            par.append({'nom':b['nom'],'be_brut':b['be'],'rfr_utilise':rfr,
                'duration':b['duration'],'facteur':round(f,6),
                'be_s2':bs,'impact':ib})
        return {'be_brut_total':be_brut,'be_s2_total':be_s2,
                'impact_total':imp,'par_branche':par}

    # ══════════════════════════════════════════════════════════════════════════
    # RISK MARGIN — DURATION-BASED
    # ══════════════════════════════════════════════════════════════════════════
    def _risk_margin(self, branches, be_act, taux):
        rm_tot=0.0; par=[]
        for b,ba in zip(branches,be_act['par_branche']):
            rfr = self._rfr_dur(b['duration'],taux)
            T   = max(int(b['duration']),1)
            fac = sum((1-t/T)/(1+rfr)**(t+1) for t in range(T))
            scr_px = 3.0*b['sigma_res']*ba['be_s2']
            rm_b   = COC*scr_px*fac
            rm_b   = max(ba['be_s2']*0.03, min(rm_b, ba['be_s2']*0.12))
            rm_tot+=rm_b
            par.append({'nom':b['nom'],'risk_margin':rm_b,'scr_proxy':scr_px,'facteur':fac})
        return {'risk_margin':rm_tot,'coc':COC,'methode':'Duration-based Art.58','par_branche':par}

    # ══════════════════════════════════════════════════════════════════════════
    # SCR SOUSCRIPTION — 3 MODES
    # ══════════════════════════════════════════════════════════════════════════
    def _scr_souscription(self, branches, mode_scr, sigma_client, modele_interne, reass):
        fs = self._scr_fs(branches, None)
        if mode_scr=='formule_standard':
            scr_brut=fs['scr_souscription']; src='EIOPA standard'; det=dict(fs)
        elif mode_scr=='recalibration_sigma':
            if sigma_client:
                sv=self._valider_sigma(sigma_client,branches)
                rec=self._scr_fs(branches,sv)
                scr_brut=rec['scr_souscription']
                red=(fs['scr_souscription']-scr_brut)/max(fs['scr_souscription'],1)*100
                src=f'Recalibration client — réduction vs FS={red:.1f}%'
                det=dict(rec); det['scr_fs_ref']=fs['scr_souscription']; det['reduction_vs_fs']=red
            else:
                self.logger.warning("recalibration_sigma sans sigma_client → FS")
                scr_brut=fs['scr_souscription']; src='EIOPA standard (sigma_client absent)'; det=dict(fs)
        elif mode_scr=='modele_interne':
            if modele_interne and 'scr_souscription' in modele_interne:
                scr_mi=float(modele_interne['scr_souscription'])
                ratio_mi=scr_mi/max(fs['scr_souscription'],1)
                alerte=ratio_mi<0.40
                if alerte: self.logger.warning(f"SCR MI={scr_mi:,.0f}€ ratio={ratio_mi:.1%}<40%")
                scr_brut=scr_mi; src='Modèle interne (approbation ACPR)'
                det=dict(fs); det.update({'scr_souscription_mi':scr_mi,'scr_fs_ref':fs['scr_souscription'],
                    'ratio_mi_vs_fs':ratio_mi,'alerte_coherence':alerte})
            else:
                self.logger.warning("modele_interne sans scr_souscription → FS")
                scr_brut=fs['scr_souscription']; src='EIOPA standard (MI non fourni)'; det=dict(fs)
        else:
            scr_brut=fs['scr_souscription']; src='EIOPA standard'; det=dict(fs)
        scr_net=scr_brut*(1-reass['reduction_scr'])
        return {**det,'scr_souscription':scr_brut,'scr_souscription_net':scr_net,
                'reduction_reass':scr_brut-scr_net,'taux_reduction_reass':reass['reduction_scr'],
                'mode_scr':mode_scr,'sigma_source':src,'alerte_coherence':det.get('alerte_coherence',False)}

    def _scr_fs(self, branches, sigma_ov):
        par=[]; sp_tot=sr_tot=sc_tot=0.0
        for b in branches:
            n=b['nom']
            sp=sigma_ov[n]['sigma_prem'] if sigma_ov and n in sigma_ov else b['sigma_prem']
            sr=sigma_ov[n]['sigma_res']  if sigma_ov and n in sigma_ov else b['sigma_res']
            Vp=b['primes'] if b['primes']>0 else b['be']*0.80; Vr=b['be']; Vt=Vp+Vr
            # Art. 117(2) : le terme croise porte le coefficient 1 du texte
            # (ecrit ici 2 x 0,5, soit une correlation implicite de 0,5 entre
            # risque de primes et risque de reserve).
            sc=np.sqrt((sp*Vp)**2+2*0.5*(sp*Vp)*(sr*Vr)+(sr*Vr)**2)/max(Vt,1)
            sp_b=3*sp*Vp; sr_b=3*sr*Vr; spr=3*sc*Vt; cat=b['f_cat']*Vp; lap=0.005*Vp
            par.append({'nom':n,'scr_prem':sp_b,'scr_res':sr_b,'scr_pr':spr,
                'scr_cat':cat,'scr_lapse':lap,'sigma_net':sc,'Vp':Vp,'Vr':Vr,
                # La provenance voyage AVEC le resultat : quelle annexe, quel
                # segment, et quels sigma ont reellement servi.
                'segment_s2':SIGMA_LOB[n]['segment_s2'],
                'reference_s2':SIGMA_LOB[n]['reference_s2'],
                'sigma_prem':sp,'sigma_res':sr})
            sp_tot+=sp_b; sr_tot+=sr_b; sc_tot+=cat
        if len(branches)==1:
            b0=par[0]
            v=np.array([b0['scr_pr'],b0['scr_cat'],b0['scr_lapse']])
            cm=np.array([[1.00,0.25,0.00],[0.25,1.00,0.00],[0.00,0.00,1.00]])
            scr=float(np.sqrt(max(float(v@cm@v),0.0))); sg=b0['sigma_net']
        else:
            nms=[b['nom'] for b in branches]; n=len(branches)
            cm=np.full((n,n),0.25); np.fill_diagonal(cm,1.0)
            for i in range(n):
                for j in range(n):
                    k=frozenset([nms[i],nms[j]])
                    if k in CORR_LOB: cm[i,j]=CORR_LOB[k]
            vpr=np.array([b['scr_pr'] for b in par])
            spr_t=float(np.sqrt(max(float(vpr@cm@vpr),0.0)))
            cat_t=sc_tot; lap_t=sum(b['scr_lapse'] for b in par)
            v=np.array([spr_t,cat_t,lap_t])
            cms=np.array([[1.00,0.25,0.00],[0.25,1.00,0.00],[0.00,0.00,1.00]])
            scr=float(np.sqrt(max(float(v@cms@v),0.0)))
            be_t=sum(b['be'] for b in branches)
            sg=sum(p['sigma_net']*b['be']/max(be_t,1) for p,b in zip(par,branches))
        return {'scr_souscription':scr,'scr_prem':sp_tot,'scr_res':sr_tot,
                'scr_cat':sc_tot,'scr_lapse':sum(b['scr_lapse'] for b in par),
                'sigma_net':sg,'par_branche':par,'nb_branches':len(branches)}

    def _valider_sigma(self, sc, branches):
        sv={}
        for b in branches:
            n=b['nom']
            if n not in sc: continue
            se=SIGMA_LOB[n]   # n vient de `norm()` : toujours présent (cf. sigma())
            sp=sc[n].get('sigma_prem',se['sigma_prem']); sr=sc[n].get('sigma_res',se['sigma_res'])
            if not (0.40<=sp/max(se['sigma_prem'],0.001)<=2.00):
                self.logger.warning(f"σ_prem {n} hors plage → EIOPA"); sp=se['sigma_prem']
            if not (0.40<=sr/max(se['sigma_res'],0.001)<=2.00):
                self.logger.warning(f"σ_res {n} hors plage → EIOPA"); sr=se['sigma_res']
            sv[n]={'sigma_prem':sp,'sigma_res':sr}
        return sv

    def _scr_marche(self, be_act, taux, dur_a, alloc, mode_scr, mi):
        if mode_scr=='modele_interne' and mi and 'scr_marche' in mi:
            scr=float(mi['scr_marche'])
            return {'scr_marche':scr,'scr_taux':scr*0.40,'scr_spread':scr*0.30,
                    'scr_actions':scr*0.20,'scr_immo':scr*0.05,'scr_concentration':0,
                    'mode':'modele_interne','actif_total':be_act['be_s2_total']*1.35}
        if not alloc:
            self.logger.warning(
                'SCR marche : allocation_actif non fournie '
                '(hypothese par defaut : 70%% oblig / 10%% actions / 5%% immo). '
                'Le SCR marche peut etre sur-estime de 20-30%% '
                'si le portefeuille est atypique. '
                'Fournir allocation_actif pour un calcul precis.'
            )
        ob=alloc.get('obligations',0.70) if alloc else 0.70
        ac=alloc.get('actions',0.10) if alloc else 0.10
        im=alloc.get('immo',0.05)    if alloc else 0.05
        at=be_act['be_s2_total']*1.35; Vo=at*ob; Va=at*ac; Vi=at*im
        dur_p=np.mean([b['duration'] for b in be_act['par_branche']])
        ch=0.012; dah=Vo*dur_a*ch; dbh=be_act['be_s2_total']*dur_p*ch
        st=max(abs(dah-dbh),abs(-(dah-dbh)*0.70))
        ss=Vo*0.009*dur_a; sa=Va*0.39; si=Vi*0.25
        cm=np.array([[1,0.25,0.25,0.25,0],[0.25,1,0.25,0.25,0],[0.25,0.25,1,0.25,0],
                     [0.25,0.25,0.25,1,0],[0,0,0,0,1]],dtype=float)
        v=np.array([st,ss,sa,si,0.0])
        return {'scr_marche':float(np.sqrt(max(float(v@cm@v),0.0))),
                'scr_taux':st,'scr_spread':ss,'scr_actions':sa,'scr_immo':si,
                'scr_concentration':0,'actif_total':at,'mode':'formule_standard',
                'allocation':{'obligations':ob,'actions':ac,'immo':im}}

    def _scr_contrepartie(self, branches, reass):
        be=sum(b['be'] for b in branches); lgd=reass['lgd']; pd=reass['pd']
        t1=max(np.sqrt(lgd**2*pd*(1-pd)+(lgd*pd)**2),lgd*pd*3) if lgd>0 else be*0.002
        t2=be*0.005
        return {'scr_contrepartie':float(np.sqrt(t1**2+t2**2)),'scr_type1':t1,'scr_type2':t2,
                'reass_recuperable':reass['reass_recuperable'],'rating':reass['rating_reassureur']}

    def _scr_operationnel(self, branches, scr_sous, mode_scr, mi):
        if mode_scr=='modele_interne' and mi and 'scr_operationnel' in mi:
            return {'scr_operationnel':float(mi['scr_operationnel']),'mode':'modele_interne'}
        pt=sum(b['primes'] for b in branches); be=sum(b['be'] for b in branches)
        bp=scr_sous['scr_souscription']*1.30
        op=min(0.30*bp,max(0.03*(pt if pt>0 else be*0.80),0.03*be))
        return {'scr_operationnel':op,'mode':'formule_standard'}

    def _agregation(self, ss, sm, sc, so):
        v=np.array([ss['scr_souscription_net'],sm['scr_marche'],sc['scr_contrepartie']])
        bscr=float(np.sqrt(max(float(v@CORR_MODULES@v),0.0)))
        return {'bscr':bscr,'scr_operationnel':so['scr_operationnel'],'scr_total':bscr+so['scr_operationnel'],
                'contributions':{'souscription':round(v[0]/max(bscr,1)*100,1),
                                  'marche':round(v[1]/max(bscr,1)*100,1),'contrepartie':round(v[2]/max(bscr,1)*100,1)}}

    def _mcr(self, branches, scr_tot):
        scr=scr_tot['scr_total']
        lin=sum(MCR_ALPHA*b['primes']+MCR_BETA*b['be'] for b in branches)
        plan=max(0.25*scr,MCR_PLANCHER_ABS); plaf=0.45*scr; mcr=max(min(lin,plaf),plan)
        reg='PLANCHER_ACTIF' if lin<plan else ('PLAFOND_ACTIF' if lin>plaf else 'MCR_LINEAIRE')
        return {'mcr':mcr,'mcr_lineaire':lin,'plancher':plan,'plancher_scr':0.25*scr,
                'plancher_abs':MCR_PLANCHER_ABS,'plafond':plaf,'regime':reg}

    def _capital(self, fpp, tiers, be_act, rm, scr_tot, mcr):
        tp=be_act['be_s2_total']+rm['risk_margin']; scr=scr_tot['scr_total']; mcr_v=mcr['mcr']
        if fpp<=0: fpp=tp*0.35; self.logger.warning(f"FPP estimés {fpp:,.0f}€")
        if tiers: t1=tiers.get('tier1',fpp*0.80); t2=tiers.get('tier2',fpp*0.15); t3=tiers.get('tier3',fpp*0.05); fpp=t1+t2+t3
        else: t1=fpp*0.80; t2=fpp*0.15; t3=fpp*0.05
        fpp_scr=min(t1+min(t2,(t1+t2)*0.50)+min(t3,fpp*0.15),fpp)
        fpp_mcr=t1+min(t2,t1*0.25)
        # Si SCR ou MCR nul : erreur amont — forcer ROUGE, ne pas calculer ratio
        if scr <= 0 or mcr_v <= 0:
            self.logger.warning(
                f'SCR={scr:,.0f}EUR ou MCR={mcr_v:,.0f}EUR nul '
                '— erreur amont. Ratios forces a 0 et statut ROUGE.'
            )
            rscr = 0.0
            rmcr = 0.0
        else:
            rscr = fpp_scr / scr * 100
            rmcr = fpp_mcr / mcr_v * 100
        return {'fonds_propres':fpp,'tier1':t1,'tier2':t2,'tier3':t3,'fpp_scr':fpp_scr,'fpp_mcr':fpp_mcr,
                'tp_s2':tp,'ratio_scr':rscr,'ratio_mcr':rmcr,'marge_scr':fpp_scr-scr,'marge_mcr':fpp_mcr-mcr_v,
                'statut_ratio':'VERT' if rscr>=150 else ('AMBRE' if rscr>=100 else 'ROUGE'),
                'statut_mcr':'VERT' if rmcr>=100 else 'ROUGE'}

    def _duration(self, branches, taux):
        be_t=sum(b['be'] for b in branches); dp=0.0; par=[]
        for b in branches:
            rfr=self._rfr_dur(b['duration'],taux); dm=b['duration']/(1+rfr); w=b['be']/max(be_t,1)
            dp+=dm*w; par.append({'nom':b['nom'],'duration_macaulay':b['duration'],'duration_modifiee':dm,'poids':w})
        return {'dur_ponderee':dp,'par_branche':par}

    def _qrt(self, be_act, rm, ss, sm, sc, so, st, mcr, cap, taux, reass):
        be=be_act['be_s2_total']; rmv=rm['risk_margin']; tp=be+rmv; scr=st['scr_total']
        return [
            {'code':'R0010','libelle':'BE S2 (actualisé RFR courbe 3 pts)','C0010':round(be,0)},
            {'code':'R0020','libelle':'Risk Margin (CoC 6% duration-based)','C0010':round(rmv,0)},
            {'code':'R0030','libelle':'Provisions Techniques S2','C0010':round(tp,0)},
            {'code':'R0040','libelle':'SCR Souscription NV brut réass.','C0040':round(ss['scr_souscription'],0),
             'detail':{'mode':ss['mode_scr'],'src':ss['sigma_source'],'red_reass':round(ss['reduction_reass'],0)}},
            {'code':'R0041','libelle':'SCR Souscription NV net réass.','C0040':round(ss['scr_souscription_net'],0)},
            {'code':'R0050','libelle':'SCR Marché','C0040':round(sm['scr_marche'],0),
             'detail':{'taux':round(sm['scr_taux'],0),'spread':round(sm['scr_spread'],0),'actions':round(sm['scr_actions'],0)}},
            {'code':'R0060','libelle':'SCR Contrepartie','C0040':round(sc['scr_contrepartie'],0),
             'detail':{'reassureur':reass['rating_reassureur'],'type':reass['type'],'recuperable':round(reass['reass_recuperable'],0)}},
            {'code':'R0100','libelle':'BSCR','C0040':round(st['bscr'],0)},
            {'code':'R0130','libelle':'SCR Opérationnel','C0040':round(so['scr_operationnel'],0)},
            {'code':'R0200','libelle':'SCR Total','C0040':round(scr,0)},
            {'code':'R0210','libelle':'MCR linéaire (α×primes + β×prov)','C0040':round(mcr['mcr_lineaire'],0)},
            {'code':'R0220','libelle':'MCR final (bornes 25%-45% SCR)','C0040':round(mcr['mcr'],0),
             'detail':{'plancher':round(mcr['plancher'],0),'plafond':round(mcr['plafond'],0),'regime':mcr['regime']}},
            {'code':'R0230','libelle':'FPP Tier 1','C0050':round(cap['tier1'],0)},
            {'code':'R0231','libelle':'FPP Tier 2','C0050':round(cap['tier2'],0)},
            {'code':'R0232','libelle':'FPP Tier 3','C0050':round(cap['tier3'],0)},
            {'code':'R0240','libelle':'FPP éligibles SCR','C0050':round(cap['fpp_scr'],0)},
            {'code':'R0241','libelle':'FPP éligibles MCR','C0050':round(cap['fpp_mcr'],0)},
            {'code':'R0250','libelle':'Ratio SCR (%)','C0060':round(cap['ratio_scr'],2)},
            {'code':'R0260','libelle':'Ratio MCR (%)','C0060':round(cap['ratio_mcr'],2)},
            {'code':'R0270','libelle':'RFR 10 ans','C0070':round(taux['rfr_10ans']*100,4),'source':taux['source'],'date':taux['date']},
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # RAG, HYPOTHÈSES, COMMENTAIRE, GRAPHIQUES
    # ══════════════════════════════════════════════════════════════════════════
    def _rag(self, cap, mcr, ss, taux, mode_scr):
        rs=cap['ratio_scr']; rm=cap['ratio_mcr']
        if rm<100: return 'ROUGE',f"MCR non couvert ({rm:.1f}%) — retrait agrément imminent"
        if rs<100: return 'ROUGE',f"SCR non couvert ({rs:.1f}%) — notification ACPR"
        if rs<130: return 'ROUGE',f"SCR={rs:.1f}%<130% — mesures correctives ACPR"
        if rs<150: return 'AMBRE',f"SCR={rs:.1f}% tampon limité"
        if mode_scr=='modele_interne' and ss.get('alerte_coherence',False):
            return 'AMBRE',"SCR MI diverge de FS>60% — justification ACPR requise"
        if taux['fiabilite']=='REFERENCE': return 'AMBRE',f"SCR={rs:.1f}% — taux de référence (connecter BCE)"
        return 'VERT',f"SCR={rs:.1f}% | MCR={rm:.1f}% — conforme"

    def _hypotheses(self, taux, branches, be_act, ss, cap, mcr, mode_scr, reass):
        h1={'id':'H1','hypothese':f"Courbe RFR EIOPA 5a={taux['rfr_5ans']:.2%} 10a={taux['rfr_10ans']:.2%} 20a={taux['rfr_20ans']:.2%}",
            'valeur':f"VA={taux['va']:.2%} | {taux['fiabilite']}",
            'statut':'VALIDÉE' if 0.005<=taux['rfr_10ans']<=0.10 else 'À JUSTIFIER','critique':True}
        if mode_scr=='formule_standard':
            h2t=f"Formule standard EIOPA — {len(branches)} branche(s)"; h2v=f"σ_net={ss['sigma_net']:.4f}"; ok=True
        elif mode_scr=='recalibration_sigma':
            red=ss.get('reduction_vs_fs',0); h2t="Recalibration σ client"; h2v=f"Réduction vs FS={red:.1f}%"; ok=abs(red)<=50
        else:
            ratio=ss.get('ratio_mi_vs_fs',1); h2t="Modèle interne (ACPR requis)"; h2v=f"Ratio MI/FS={ratio:.1%}"; ok=ratio>=0.40
        h2={'id':'H2','hypothese':h2t,'valeur':h2v,'statut':'VALIDÉE' if ok else 'À JUSTIFIER','critique':True}
        h3={'id':'H3','hypothese':'FPP couvrent SCR ET MCR + tiers FPP cohérents',
            'valeur':f"SCR={cap['ratio_scr']:.1f}%[{cap['statut_ratio']}] MCR={cap['ratio_mcr']:.1f}%[{cap['statut_mcr']}] T1={cap['tier1']:,.0f}€ T2={cap['tier2']:,.0f}€",
            'statut':'VALIDÉE' if cap['ratio_scr']>=100 and cap['ratio_mcr']>=100 else 'NON VALIDÉE','critique':True}
        return [h1,h2,h3]

    def _commentaire(self, rag, cap, mcr, scr_tot, ss, sm, rm, be_act, taux, branches, mode_scr, reass, hyp):
        ic="🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        noms=" + ".join(b['nom'] for b in branches)
        ml={'formule_standard':'FS EIOPA','recalibration_sigma':'FS recalibrée (σ client)','modele_interne':'Modèle Interne'}.get(mode_scr,mode_scr)
        be=be_act['be_s2_total']; rmv=rm['risk_margin']; tp=be+rmv; scr=scr_tot['scr_total']
        L=[
            "="*70,f"  RAPPORT S2 NON-VIE | Branches : {noms} | Mode : {ml}",
            f"  A10 Elena v{self.VERSION} | {ic} STATUT : {rag}","="*70,"",
            "📊 RÉSUMÉ DIRECTION","─"*40,
        ]
        if rag=='VERT': L.append(f"✅ Conforme. SCR={cap['ratio_scr']:.1f}% MCR={cap['ratio_mcr']:.1f}%. TP={tp:,.0f}€ @ RFR={taux['rfr_10ans']:.2%}.")
        elif rag=='AMBRE': L.append(f"⚠️ Conforme sous surveillance. SCR={cap['ratio_scr']:.1f}% MCR={cap['ratio_mcr']:.1f}%.")
        else: L.append(f"❌ ALERTE RÉGLEMENTAIRE. SCR={cap['ratio_scr']:.1f}% MCR={cap['ratio_mcr']:.1f}%. Action immédiate.")
        L+=[""," 🔢 PROVISIONS & SCR","─"*40,
            f"  BE actualisé (courbe 3 pts)  : {be:>15,.0f}€",
            f"  Risk Margin (CoC 6% dur-based): {rmv:>15,.0f}€",
            f"  Provisions Techniques S2      : {tp:>15,.0f}€","  "+"─"*45,
            f"  SCR Sous. brut [{ml}]: {ss['scr_souscription']:>12,.0f}€",
            f"  Réduction réassurance [{reass['type']}]: {ss['reduction_reass']:>8,.0f}€",
            f"  SCR Sous. net                 : {ss['scr_souscription_net']:>15,.0f}€",
            f"  SCR Marché                    : {sm['scr_marche']:>15,.0f}€",
            f"  BSCR                          : {scr_tot['bscr']:>15,.0f}€",
            f"  SCR Opérationnel              : {scr_tot['scr_operationnel']:>15,.0f}€",
            f"  SCR Total                     : {scr:>15,.0f}€",
            "","🛡️ MCR & CAPITAL","─"*40,
            f"  MCR linéaire                  : {mcr['mcr_lineaire']:>15,.0f}€",
            f"  MCR final [{mcr['regime']}]           : {mcr['mcr']:>15,.0f}€","  "+"─"*45,
            f"  Fonds Propres Tier 1          : {cap['tier1']:>15,.0f}€",
            f"  Fonds Propres Tier 2          : {cap['tier2']:>15,.0f}€",
            f"  Fonds Propres Tier 3          : {cap['tier3']:>15,.0f}€",
            f"  FPP éligibles SCR             : {cap['fpp_scr']:>15,.0f}€",
            f"  FPP éligibles MCR             : {cap['fpp_mcr']:>15,.0f}€",
            f"  Ratio SCR                     : {cap['ratio_scr']:>14.1f}%  [{cap['statut_ratio']}]",
            f"  Ratio MCR                     : {cap['ratio_mcr']:>14.1f}%  [{cap['statut_mcr']}]",
            "","📋 HYPOTHÈSES","─"*40,
        ]
        for h in hyp:
            ic_h="✅" if h['statut']=='VALIDÉE' else "⚠️"
            L+=[f"  {ic_h} [{h['id']}] {h['hypothese']}",f"       → {h['valeur']} : {h['statut']}"]
        L+=["","🎯 AVIS ELENA → NADIA","─"*40]
        if rag=='VERT': L.append("✅ CONFORME — QRT S.25.01 prêt. Données transmises à A9/A11/A12.")
        elif rag=='AMBRE': L.append("⚠️ Documenter les hypothèses avant soumission QRT.")
        else: L.append("❌ NON CONFORME — Escalade LEILA. Plan restauration capital ACPR.")
        L.append(""); return "\n".join(L)

    def _graphiques(self, be_act, rm, ss, sm, sc, so, st, mcr, cap, taux, branches, reass):
        gph={}
        def crag(s): return VERT if s=='VERT' else (AMBRE if s=='AMBRE' else ROUGE)
        try:
            be_b=be_act['be_brut_total']; be_s=be_act['be_s2_total']
            imp=be_act['impact_total']; rmv=rm['risk_margin']; tp=be_s+rmv
            fig=go.Figure(go.Waterfall(
                x=['BE Brut (A7)','Actualisation\nRFR 3 pts','Risk Margin\nCoC 6%','TP S2'],
                y=[be_b,imp,rmv,tp],measure=['absolute','relative','relative','total'],
                text=[f"{v/1e6:.2f}M€" for v in [be_b,imp,rmv,tp]],textposition='outside',
                textfont=dict(color=BLANC,size=11),
                connector=dict(line=dict(color=GRIS,width=1,dash='dot')),
                increasing=dict(marker_color=AMBRE),decreasing=dict(marker_color=VERT),
                totals=dict(marker_color=OR),
                hovertemplate='<b>%{x}</b><br>%{y:,.0f}€<extra></extra>'))
            l=dict(**LAYOUT_BASE)
            l.update(dict(title=dict(text="G1 — BE → Provisions Techniques S2",font=dict(color=OR,size=12),x=0.01),
                showlegend=False,
                annotations=[dict(text=f"💡 Courbe RFR : {taux['rfr_5ans']:.2%}/{taux['rfr_10ans']:.2%}/{taux['rfr_20ans']:.2%}. RM = coût capital run-off.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,font=dict(color=GRIS,size=9),showarrow=False)],
                xaxis=dict(tickfont=dict(color=BLANC,size=9),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,gridcolor='rgba(255,255,255,0.05)')))
            fig.update_layout(**l); gph['waterfall_be_tp']=fig
        except Exception as e: self.logger.warning(f"G1:{e}")
        try:
            s_b=ss['scr_souscription']; s_n=ss['scr_souscription_net']
            s_m=sm['scr_marche']; s_c=sc['scr_contrepartie']; s_o=so['scr_operationnel']; red=ss['reduction_reass']
            fig=make_subplots(rows=1,cols=2,specs=[[{'type':'pie'},{'type':'pie'}]],subplot_titles=['SCR Brut','SCR Net Réassurance'])
            fig.add_trace(go.Pie(labels=['Souscription','Marché','Contrepartie','Opérationnel'],
                values=[s_b,s_m,s_c,s_o],hole=0.50,
                marker=dict(colors=[ROUGE,AMBRE,VIOLET,BLEU],line=dict(color=NAVY,width=2)),
                textinfo='percent',textfont=dict(size=9,color=BLANC),showlegend=True,name='Brut'),row=1,col=1)
            fig.add_trace(go.Pie(labels=['Souscription nette','Marché','Contrepartie','Opérationnel','Réduction réass.'],
                values=[s_n,s_m,s_c,s_o,red],hole=0.50,
                marker=dict(colors=[ROUGE,AMBRE,VIOLET,BLEU,VERT],line=dict(color=NAVY,width=2)),
                textinfo='percent',textfont=dict(size=9,color=BLANC),showlegend=False,name='Net'),row=1,col=2)
            l=dict(**LAYOUT_BASE)
            l.update(dict(title=dict(text=f"G2 — SCR Brut vs Net ({reass['type']} {reass['taux_cession']:.0%})",font=dict(color=OR,size=12),x=0.01),
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)'),
                annotations=[dict(text="Brut",x=0.18,y=0.5,showarrow=False,font=dict(color=OR,size=11)),
                    dict(text="Net",x=0.82,y=0.5,showarrow=False,font=dict(color=VERT,size=11)),
                    dict(text=f"💡 Réassurance libère {ss['taux_reduction_reass']:.0%} de capital SCR souscription.",
                        xref="paper",yref="paper",x=0.01,y=-0.15,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig.update_layout(**l); gph['donut_scr_reass']=fig
        except Exception as e: self.logger.warning(f"G2:{e}")
        try:
            rs=cap['ratio_scr']; rm_=cap['ratio_mcr']; cs=crag(cap['statut_ratio']); cm=crag(cap['statut_mcr'])
            fig=make_subplots(rows=1,cols=2,specs=[[{'type':'indicator'},{'type':'indicator'}]],subplot_titles=['Ratio SCR','Ratio MCR'])
            def jauge(val,col):
                return go.Indicator(mode="gauge+number",value=val,
                    number=dict(suffix="%",font=dict(color=col,size=22)),
                    gauge=dict(axis=dict(range=[0,300],tickvals=[0,100,130,150,200,300],
                        ticktext=['0','100%','130%','150%','200%','300%'],tickfont=dict(color=BLANC,size=8)),
                        bar=dict(color=col,thickness=0.3),bgcolor=NAVY_L,borderwidth=1,bordercolor=GRIS,
                        steps=[dict(range=[0,100],color='rgba(231,76,60,0.3)'),dict(range=[100,130],color='rgba(231,76,60,0.15)'),
                               dict(range=[130,150],color='rgba(243,156,18,0.3)'),dict(range=[150,300],color='rgba(46,204,113,0.15)')],
                        threshold=dict(line=dict(color=ROUGE,width=2),thickness=0.8,value=100)))
            fig.add_trace(jauge(rs,cs),row=1,col=1); fig.add_trace(jauge(rm_,cm),row=1,col=2)
            l=dict(**LAYOUT_BASE); l.update(dict(title=dict(text="G3 — Ratios Couverture SCR et MCR",font=dict(color=OR,size=12),x=0.01),height=300,
                annotations=[dict(text="💡 SCR confort ≥150%. MCR légal =100% (dessous = retrait agrément ACPR).",
                    xref="paper",yref="paper",x=0.01,y=-0.15,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig.update_layout(**l); gph['double_jauge_scr_mcr']=fig
        except Exception as e: self.logger.warning(f"G3:{e}")
        try:
            t1=cap['tier1']; t2=cap['tier2']; t3=cap['tier3']; scr=st['scr_total']; mcr_v=mcr['mcr']
            fig=go.Figure()
            for nom,val,col in [('Tier 1',t1,VERT),('Tier 2',t2,AMBRE),('Tier 3',t3,BLEU)]:
                fig.add_trace(go.Bar(name=nom,x=['Fonds Propres'],y=[val],marker_color=col,opacity=0.85,
                    text=f"{val/1e6:.2f}M€",textposition='inside',textfont=dict(color=BLANC,size=10),
                    hovertemplate=f'<b>{nom}</b><br>%{{y:,.0f}}€<extra></extra>'))
            for nom,val,col in [('SCR Sous.net',ss['scr_souscription_net'],ROUGE),('SCR Marché',sm['scr_marche'],AMBRE),
                                 ('SCR Ctpt',sc['scr_contrepartie'],VIOLET),('SCR Op.',so['scr_operationnel'],BLEU)]:
                fig.add_trace(go.Bar(name=nom,x=['SCR Requis'],y=[val],marker_color=col,opacity=0.85,
                    text=f"{val/1e6:.2f}M€" if val>1e5 else f"{val:,.0f}€",textposition='inside',
                    textfont=dict(color=BLANC,size=9),hovertemplate=f'<b>{nom}</b><br>%{{y:,.0f}}€<extra></extra>'))
            fig.add_trace(go.Bar(name='MCR',x=['MCR'],y=[mcr_v],marker_color=TURQUOISE,opacity=0.85,
                text=f"{mcr_v/1e6:.2f}M€",textposition='outside',textfont=dict(color=TURQUOISE,size=11),
                hovertemplate=f'<b>MCR</b><br>%{{y:,.0f}}€<extra></extra>'))
            l=dict(**LAYOUT_BASE); cg=crag(cap['statut_ratio'])
            l.update(dict(title=dict(text=f"G4 — Capital Tier 1/2/3 vs SCR vs MCR | Ratio={cap['ratio_scr']:.1f}%",
                font=dict(color=cg,size=11),x=0.01),barmode='stack',
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(tickfont=dict(color=GRIS),showgrid=True,gridcolor='rgba(255,255,255,0.05)'),
                legend=dict(font=dict(color=BLANC,size=9),bgcolor='rgba(0,0,0,0)',orientation='h',y=-0.22),
                annotations=[dict(text="💡 Tier 1 (vert) = capital de meilleure qualité. Tier 3 non éligible au MCR. MCR = plancher légal absolu.",
                    xref="paper",yref="paper",x=0.01,y=-0.32,font=dict(color=GRIS,size=9),showarrow=False)]))
            fig.update_layout(**l); gph['bilan_capital_tiers']=fig
        except Exception as e: self.logger.warning(f"G4:{e}")
        return gph

    def _audit(self, aid, branches, cap, mcr, scr_tot, rag, mode_scr):
        try:
            r={'audit_id':aid,'agent':self.NOM,'version':self.VERSION,'timestamp':datetime.now().isoformat(),
               'mode_scr':mode_scr,'statut_rag':rag,'ratio_scr':cap['ratio_scr'],'ratio_mcr':cap['ratio_mcr'],
               'scr_total':scr_tot['scr_total'],'mcr':mcr['mcr'],'fonds_propres':cap['fonds_propres'],
               'branches':[b['nom'] for b in branches]}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e: self.logger.warning(f"Audit:{e}")

    def _console(self, aid, cap, mcr, scr_tot, ss, rm, be_act, rag, com):
        print(f"\n{'─'*70}\n  A10 ELENA v{self.VERSION} | {aid}\n{'─'*70}")
        print(com); print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        z={'fonds_propres':0,'tier1':0,'tier2':0,'tier3':0,'fpp_scr':0,'fpp_mcr':0,
           'scr_total':0,'mcr':0,'ratio_scr':0,'ratio_mcr':0,'marge_scr':0,'marge_mcr':0,
           'statut_ratio':'ROUGE','statut_mcr':'ROUGE','tp_s2':0}
        return {'success':False,'agent':self.NOM,'version':self.VERSION,'audit_id':aid,
                'statut_rag':'ROUGE','provisions':{'best_estimate':0,'risk_margin':0,'tp_s2':0},
                'duration':{'passif':4.0,'actif':3.5,'gap':0.5},'capital':z,
                'mcr':{'mcr':0,'mcr_lineaire':0,'plancher':0,'plafond':0,'ratio_mcr':0,'statut_mcr':'ROUGE','regime':'N/A'},
                'scr':{},'reassurance':{'type':'aucune','taux_cession':0,'reduction_scr':0,'reass_recuperable':0,'lgd':0,'pd':0.003,'rating_reassureur':'A'},
                'taux':TAUX_DEFAUT,'qrt_s25':[],'hypotheses':[],'commentaire':f"❌ ERREUR:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  A10 ELENA v2.0 DÉFINITIVE — DÉMO")
    print("  MCR + 3 modes SCR + Multi-branches + Réassurance XL + Tiers FPP")
    print("="*70)
    a7={'best_estimate':{'best_estimate':7_359_000.0,'sigma_mack':450_000.0,'cv_inter_methodes':8.5,'nb_methodes_convergentes':5},
        'tail':{'tail_factor':1.0374},'meta':{'nb_lignes':70000,'n_annees':8}}
    a6={'modele_production':{'modele':'XGBoost','gini_test':0.312,'prime_pure':720.0,'primes_acquises':10_000_000.0}}
    agent=AgentA10Solvabilite2(audit_path='/tmp/a10/audit',verbose=True)
    r=agent.run(
        result_a7=a7,result_a6=a6,market_data=None,
        branches=[{'nom':'rc_auto','be':5_000_000,'primes':7_000_000},{'nom':'mrh','be':2_359_000,'primes':3_000_000}],
        mode_scr='recalibration_sigma',
        sigma_client={'rc_auto':{'sigma_prem':0.075,'sigma_res':0.070},'mrh':{'sigma_prem':0.060,'sigma_res':0.085}},
        reassurance={'type':'xl','priorite':500_000,'portee':2_000_000,'taux_cession':0.70,'rating_reassureur':'AA'},
        fonds_propres=5_000_000.0,tiers_fpp={'tier1':4_000_000,'tier2':800_000,'tier3':200_000},
        allocation_actif={'obligations':0.72,'actions':0.08,'immo':0.05,'cash':0.15},
        duration_actif=3.5,generer_graphiques=False)
    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut   : {r['statut_rag']} | {r.get('motif_rag','')}")
    pv=r['provisions']; print(f"  BE S2    : {pv['best_estimate']:>15,.0f}€ | RM={pv['risk_margin']:,.0f}€ | TP={pv['tp_s2']:,.0f}€")
    s=r['scr']; print(f"  SCR      : sous_brut={s['souscription']:,.0f}€ net={s['souscription_net']:,.0f}€ total={s['total']:,.0f}€")
    m=r['mcr']; print(f"  MCR      : lin={m['mcr_lineaire']:,.0f}€ final={m['mcr']:,.0f}€ [{m['regime']}]")
    c=r['capital']; print(f"  Capital  : T1={c['tier1']:,.0f}€ T2={c['tier2']:,.0f}€ T3={c['tier3']:,.0f}€")
    print(f"  Ratio SCR: {c['ratio_scr']:.1f}% [{c['statut_ratio']}] | MCR: {c['ratio_mcr']:.1f}% [{c['statut_mcr']}]")
    print(f"  Duration : passif={r['duration']['passif']:.2f}a gap={r['duration']['gap']:.2f}a")
    print(f"  QRT      : {len(r['qrt_s25'])} lignes | Durée={r['duree_sec']:.2f}s")
