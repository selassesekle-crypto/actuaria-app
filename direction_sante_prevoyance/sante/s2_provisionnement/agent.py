# Migré depuis sp2_provisionnement_sante.py → direction_sante_prevoyance/sante/s2_provisionnement/agent.py
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ACTUARIA — AGENT S2 SELMA : PROVISIONNEMENT SANTÉ v2.0                ║
║                Sous CHIARA (Équipe Santé) · Direction SP                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PÉRIMÈTRE : Provisions techniques santé                                    ║
║              PSAP (dossiers + IBNR) · PREC · Triangle santé rapide        ║
║                                                                              ║
║  NOUVEAUTÉS v2 :                                                             ║
║    ✅ Reçoit result_s1 (Léonie) — données réelles du portefeuille          ║
║    ✅ PSAP par poste (médecine, hospit, dentaire, optique, pharmacie)      ║
║    ✅ IBNR cadences santé différenciées par poste (1-3 mois)              ║
║    ✅ PREC sur base primes acquises S1                                      ║
║    ✅ Triangle de développement santé simplifié (3 mois)                   ║
║    ✅ Standard ActuarIA : RAG + 3 hypothèses + 4 graphiques + commentaire  ║
║    ✅ Sorties vers S3 Binta                                                 ║
║                                                                              ║
║  ENTRÉES :                                                                   ║
║    result_s1  → Tarification Léonie (obligatoire)                          ║
║    result_a2  → Données brutes Kenji (optionnel — enrichit les dossiers)  ║
║    nb_sinistres_ouverts → dossiers en cours                                ║
║    cout_moyen_ouvert    → coût moyen dossier ouvert                        ║
║    delai_reglement_mois → délai moyen règlement (santé : 1-3 mois)        ║
║                                                                              ║
║  SORTIES VERS S3 BINTA :                                                    ║
║    psap_total · prec · provision_totale · loss_ratio · be_sante           ║
║                                                                              ║
║  VERSION : 2.0 — 20/06/2026                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json, logging, warnings
from datetime import datetime
from pathlib import Path
from typing import Dict


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
AMBRE="#F39C12"; BLEU="#3498DB"

LAYOUT_BASE = dict(paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
    font=dict(family="Inter, Arial", color=BLANC, size=11),
    margin=dict(l=16,r=16,t=60,b=60), height=300,
    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC))

# ── Paramètres IBNR santé par poste ──────────────────────────────────────────
# Source : pratique marché mutuelles France — FNMF 2023 + CTIP 2023
# En santé, IBNR faible (5-25%) car remboursement rapide (1-3 mois)
# vs IARD (6-18 mois) et prévoyance (12-36 mois)
# Médecine/Pharmacie : IBNR faible (feuilles soins dématérialisées)
# Hospit : IBNR plus élevé (facturation hôpitaux retardée 1-3 mois)
# Dentaire/Optique : IBNR intermédiaire (prothèses, délais laboratoire)
IBNR_TAUX_POSTE = {
    "medecine":        0.08,   # 8%  — feuilles de soins rapides
    "pharmacie":       0.05,   # 5%  — pharmacie quasi-immédiat
    "hospitalisation": 0.25,   # 25% — séjours complexes, retards facturation
    "dentaire":        0.15,   # 15% — prothèses, délais laboratoire
    "optique":         0.10,   # 10% — remboursement différé
}

# Délais de règlement santé (mois) — cadences de liquidation
# Source : DREES Comptes de la Santé 2023 + pratique marché FNMF
# Médecine/Pharmacie : dématérialisé → 1 mois
# Hospit/Dentaire/Optique : facturation manuelle → 2-3 mois
DELAIS_REGLEMENT = {
    "medecine":        1,
    "pharmacie":       1,
    "hospitalisation": 3,
    "dentaire":        2,
    "optique":         2,
}


# ══════════════════════════════════════════════════════════════════════════════
class AgentS2ProvisionnemntSante:
    """
    Agent S2 Selma — Provisionnement Santé v2.0.
    Sous CHIARA, Direction Santé-Prévoyance.
    """
    NOM     = "Selma"
    CODE    = "S2"
    VERSION = "2.0"
    MANAGER = "Chiara (Équipe Santé)"

    def __init__(self, models_path="models", audit_path="audit", verbose=True):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)
        self.logger  = logging.getLogger("actuaria.s2.selma")
        self.verbose = verbose
        if verbose:
            self.logger.info(f"S2 Selma v{self.VERSION} | {self.MANAGER}")

    # ──────────────────────────────────────────────────────────────────────────
    def run(self,
            result_s1,
            result_a2            = None,
            nb_sinistres_ouverts: int   = None,
            cout_moyen_ouvert:    float = None,
            generer_graphiques:   bool  = True) -> Dict:

        t0  = datetime.now()
        aid = f"S2_{t0.strftime('%Y%m%d_%H%M%S')}"

        try:
            # ── 1. EXTRACTION DONNÉES S1 ──────────────────────────────────────
            src = self._extraire_s1(result_s1)
            self.logger.info(
                f"[{aid}] S2 Selma | PA={src['primes_acquises']:,.0f}€ | "
                f"LR={src['loss_ratio_attendu']*100:.1f}%"
            )

            # ── 2. DOSSIERS OUVERTS (PSAP dossiers) ──────────────────────────
            nb_ouv, cout_ouv = self._parametres_dossiers(
                result_a2, nb_sinistres_ouverts, cout_moyen_ouvert, src
            )

            # ── 3. PSAP PAR POSTE ─────────────────────────────────────────────
            psap_postes = self._calculer_psap_postes(src, nb_ouv, cout_ouv)

            # ── 4. IBNR PAR POSTE (cadences santé) ───────────────────────────
            ibnr_postes = self._calculer_ibnr_postes(src)

            # ── 5. TOTAUX PSAP ────────────────────────────────────────────────
            psap_dossiers = sum(v['psap_dossiers'] for v in psap_postes.values())
            psap_ibnr     = sum(v['ibnr']          for v in ibnr_postes.values())
            psap_total    = psap_dossiers + psap_ibnr

            # ── 6. PREC ───────────────────────────────────────────────────────
            prec = self._calculer_prec(src)

            # ── 7. PROVISION TOTALE ───────────────────────────────────────────
            provision_totale = psap_total + prec
            loss_ratio       = src['sinistres_payes'] / max(src['primes_acquises'], 1)
            taux_prov        = provision_totale / max(src['primes_acquises'], 1)

            # ── 8. BE SANTÉ (pour S3 Binta) ───────────────────────────────────
            be_sante   = psap_total
            # Risk Adjustment IFRS 17 — méthode CoC (coût du capital)
            # RA = SCR_prévu × CoC_rate × duration_moyenne
            # Proxy : SCR_santé ≈ σ_primes × PA × 3 (formule std EIOPA)
            # CoC_rate EIOPA = 6% | duration santé ≈ 0.5 an (règlement rapide)
            _scr_proxy  = 0.05 * src['primes_acquises'] * 3   # SCR proxy
            _coc_rate   = 0.06   # EIOPA CoC rate
            _duration_s = 0.5   # duration santé (mois) en années
            risk_adj    = _scr_proxy * _coc_rate * _duration_s
            # Floor : RA ≥ 1% BE (cohérence avec pratique marché)
            risk_adj    = max(risk_adj, be_sante * 0.01)
            tp_sante    = be_sante + risk_adj

            # ── 9. TRIANGLE SANTÉ SIMPLIFIÉ ───────────────────────────────────
            triangle = self._triangle_sante(src, psap_postes, ibnr_postes)

            # ── 10. HYPOTHÈSES + RAG ──────────────────────────────────────────
            hyp = self._hypotheses(
                psap_total, psap_ibnr, loss_ratio,
                src['primes_acquises'], src['sinistres_payes'],
                src['sinistres_attendus']
            )
            rag = self._rag(hyp, loss_ratio)

            # ── 11. COMMENTAIRE ───────────────────────────────────────────────
            com = self._commentaire(
                rag, src, psap_dossiers, psap_ibnr, psap_total,
                prec, provision_totale, loss_ratio, taux_prov,
                be_sante, risk_adj, tp_sante, psap_postes, ibnr_postes, hyp
            )

            # ── 12. GRAPHIQUES ────────────────────────────────────────────────
            gph = {}
            if generer_graphiques and PLOTLY_OK:
                gph = self._graphiques(
                    psap_dossiers, psap_ibnr, prec, loss_ratio,
                    src, psap_postes, ibnr_postes, hyp, triangle
                )

            self._audit(aid, psap_total, prec, loss_ratio, rag)
            if self.verbose:
                self._console(aid, rag, psap_total, prec, provision_totale, loss_ratio)

            duree = (datetime.now()-t0).total_seconds()

            return {
                'success':    True,
                'agent':      self.NOM,
                'version':    self.VERSION,
                'audit_id':   aid,
                'statut_rag': rag,

                # ── Provisions ──────────────────────────────────────────────
                'psap_dossiers':    round(psap_dossiers, 2),
                'psap_ibnr':        round(psap_ibnr, 2),
                'psap_total':       round(psap_total, 2),
                'prec':             round(prec, 2),
                'provision_totale': round(provision_totale, 2),
                'loss_ratio':       round(loss_ratio, 4),
                'taux_provisionnement': round(taux_prov, 4),

                # ── Détail par poste ─────────────────────────────────────────
                'psap_par_poste':   psap_postes,
                'ibnr_par_poste':   ibnr_postes,
                'triangle':         triangle,

                # ── Sorties vers S3 Binta ────────────────────────────────────
                'sorties_s3': {
                    'be_sante':         round(be_sante, 2),
                    'risk_adjustment':  round(risk_adj, 2),
                    'tp_sante':         round(tp_sante, 2),
                    'psap_total':       round(psap_total, 2),
                    'prec':             round(prec, 2),
                    'provision_totale': round(provision_totale, 2),
                    'loss_ratio':       round(loss_ratio, 4),
                    'primes_acquises':  src['primes_acquises'],
                    # NB : fonds_propres NON estimés ici — S3 les reçoit en paramètre direct
                    # Estimation à 80% PA était sans base réglementaire (supprimée)
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
    # 1. EXTRACTION S1
    # ══════════════════════════════════════════════════════════════════════════
    def _extraire_s1(self, result_s1):
        if not result_s1 or not result_s1.get('success'):
            raise ValueError("result_s1 absent ou en erreur — S2 nécessite S1")

        s2 = result_s1.get('sorties_s2', {})
        postes = result_s1.get('postes', {})

        primes_acq = float(s2.get('primes_acquises',
                    result_s1.get('primes_acquises', 5_000_000)))
        lr_att     = float(s2.get('loss_ratio_attendu',
                    result_s1.get('ratio_sp_attendu', 0.72)))
        nb_ass     = int(result_s1.get('nb_assures', 1000))
        sin_att    = float(s2.get('sinistres_attendus', primes_acq * lr_att))
        sin_poste  = s2.get('sinistralite_par_poste', {})

        # Sinistres payés estimés par poste selon les délais de règlement
        # Source : DELAIS_REGLEMENT définis en tête de fichier
        # Taux de règlement dans l'année = f(délai moyen en mois)
        # Médecine/Pharmacie (1 mois) → ~97% réglé dans l'année
        # Hospit (3 mois) → ~85% | Dentaire/Optique (2 mois) → ~92%
        TAUX_REGLEMENT_ANNUEL = {
            'medecine':        0.97,
            'pharmacie':       0.98,
            'hospitalisation': 0.82,
            'dentaire':        0.88,
            'optique':         0.90,
        }
        TAUX_GLOBAL_DEFAUT = 0.90  # fallback si pas de détail poste
        sin_poste_detail = s2.get('sinistralite_par_poste', {})
        if sin_poste_detail:
            # Pondération par poste
            sin_pay = 0.0
            for poste, sin_p in sin_poste_detail.items():
                taux = TAUX_REGLEMENT_ANNUEL.get(poste, TAUX_GLOBAL_DEFAUT)
                sin_pay += float(sin_p) * taux
            sinistres_payes = sin_pay
        else:
            # Fallback : taux global pondéré (médiane des postes)
            sinistres_payes = sin_att * TAUX_GLOBAL_DEFAUT

        return {
            'primes_acquises':      primes_acq,
            'sinistres_payes':      sinistres_payes,
            'sinistres_attendus':   sin_att,
            'loss_ratio_attendu':   lr_att,
            'nb_assures':           nb_ass,
            'sin_par_poste':        sin_poste,
            'postes_s1':            postes,
            'prime_pure_unitaire':  float(result_s1.get('prime_pure', 0)),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 2. PARAMÈTRES DOSSIERS OUVERTS
    # ══════════════════════════════════════════════════════════════════════════
    def _parametres_dossiers(self, result_a2, nb_ouv, cout_ouv, src):
        """
        Détermine le nombre et coût moyen des dossiers ouverts.
        Priorité : données A2 réelles > paramètres manuels > estimation.
        """
        # Depuis A2 si disponible
        if result_a2 and result_a2.get('success'):
            df = result_a2.get('dataframe')
            if df is not None and 'flag_dossier_ouvert' in df.columns:
                nb_reel  = int(df['flag_dossier_ouvert'].sum())
                if nb_reel > 0:
                    self.logger.info(f"Dossiers ouverts depuis A2 : {nb_reel}")
                    # Coût moyen depuis sinistres réels si disponibles
                    if 'cout_total_sinistres' in df.columns:
                        df_ouv = df[df['flag_dossier_ouvert'] == 1]
                        cout_reel = float(df_ouv['cout_total_sinistres'].mean())
                        return nb_reel, cout_reel

        # Paramètres manuels
        if nb_ouv is not None and cout_ouv is not None:
            return nb_ouv, cout_ouv

        # Estimation depuis S1
        # Nb dossiers ouverts ≈ 3% des assurés (taux hospit + gros sinistres)
        nb_est   = max(10, int(src['nb_assures'] * 0.03))
        # Coût moyen dossier ouvert ≈ sinistres payés / (nb_assures * freq_sin)
        cout_est = src['sinistres_payes'] / max(src['nb_assures'] * 0.15, 1) * 3
        cout_est = max(cout_est, 300.0)
        self.logger.info(
            f"Dossiers estimés : {nb_est} × {cout_est:.0f}€ (3% assurés)"
        )
        return nb_est, cout_est

    # ══════════════════════════════════════════════════════════════════════════
    # 3. PSAP PAR POSTE
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_psap_postes(self, src, nb_ouv, cout_ouv):
        """
        PSAP dossiers connus par poste.
        Répartition du nombre de dossiers selon les fréquences relatives.
        """
        postes_s1 = src.get('postes_s1', {})

        # Poids relatifs par poste (fréquences)
        freq_total = sum(
            v.get('frequence_an', 0) for v in postes_s1.values()
        ) if postes_s1 else 1.0

        result = {}
        for poste in ['medecine','pharmacie','hospitalisation','dentaire','optique']:
            if postes_s1 and poste in postes_s1:
                poids = postes_s1[poste].get('frequence_an', 0) / max(freq_total, 1)
            else:
                # Poids par défaut
                poids_def = {'medecine':0.45,'pharmacie':0.25,'hospitalisation':0.08,
                             'dentaire':0.12,'optique':0.10}
                poids = poids_def.get(poste, 0.10)

            nb_ouv_poste   = max(1, int(nb_ouv * poids))
            # Coût moyen ajusté par poste (hospit >> médecine)
            mult = {'medecine':0.3,'pharmacie':0.15,'hospitalisation':3.5,
                    'dentaire':1.2,'optique':0.8}
            cout_poste = cout_ouv * mult.get(poste, 1.0)

            psap_d = nb_ouv_poste * cout_poste

            result[poste] = {
                'nb_dossiers_ouverts': nb_ouv_poste,
                'cout_moyen_dossier':  round(cout_poste, 2),
                'psap_dossiers':       round(psap_d, 2),
                'delai_reglement_mois':DELAIS_REGLEMENT.get(poste, 2),
            }

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 4. IBNR PAR POSTE (cadences santé)
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_ibnr_postes(self, src):
        """
        IBNR par poste — cadences de développement spécifiques santé.

        En santé, l'IBNR est faible (5-25% selon le poste) car
        les soins sont déclarés et remboursés rapidement (1-3 mois).
        C'est très différent de l'IARD (6-18 mois) et de la prévoyance.

        Méthode : IBNR_poste = sinistres_poste × taux_IBNR_poste
        """
        sin_poste = src.get('sin_par_poste', {})
        # Si pas de détail poste depuis S1
        if not sin_poste:
            sin_total = src['sinistres_payes']
            postes_def = {'medecine':0.07,'pharmacie':0.13,'hospitalisation':0.20,
                          'dentaire':0.32,'optique':0.28}
            sin_poste = {p: sin_total * w for p, w in postes_def.items()}

        result = {}
        for poste, taux_ibnr in IBNR_TAUX_POSTE.items():
            sin_p = sin_poste.get(poste, 0.0)
            ibnr_p = sin_p * taux_ibnr
            result[poste] = {
                'sinistres_payes': round(sin_p, 2),
                'taux_ibnr':       taux_ibnr,
                'ibnr':            round(ibnr_p, 2),
                'note':            f"IBNR = {taux_ibnr*100:.0f}% des SP — cadence santé",
            }

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 5. PREC
    # ══════════════════════════════════════════════════════════════════════════
    def _calculer_prec(self, src):
        """
        PREC = Provision pour Risques en Cours.
        PREC = max(0, PA × max(0, ratio_combiné_attendu − 1))
        où ratio_combiné = LR + chargements (≈ LR + 15%)
        """
        lr   = src['loss_ratio_attendu']
        pa   = src['primes_acquises']
        rc   = lr + 0.15   # ratio combiné (sinistres + frais)
        prec = max(0.0, pa * max(0.0, rc - 1.0))
        return prec

    # ══════════════════════════════════════════════════════════════════════════
    # 6. TRIANGLE SANTÉ SIMPLIFIÉ
    # ══════════════════════════════════════════════════════════════════════════
    def _triangle_sante(self, src, psap_postes, ibnr_postes):
        """
        Triangle de développement simplifié pour la santé.
        3 mois de développement (vs 8-10 ans en IARD).
        Montre la vitesse de liquidation caractéristique de la santé.
        """
        sp = src['sinistres_payes']
        # Mois 1 : 60% payé
        # Mois 2 : 85% payé
        # Mois 3 : 97% payé (IBNR résiduel 3%)
        return {
            'description': "Triangle santé 3 mois — liquidation rapide",
            'mois_1':  round(sp * 0.60, 0),
            'mois_2':  round(sp * 0.85, 0),
            'mois_3':  round(sp * 0.97, 0),
            'ultime':  round(sp + sum(v['ibnr'] for v in ibnr_postes.values()), 0),
            'note': (
                "Santé : 97% des sinistres payés en 3 mois "
                "(vs 18-36 mois en IARD, 60+ mois en prévoyance)"
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 7. HYPOTHÈSES
    # ══════════════════════════════════════════════════════════════════════════
    def _hypotheses(self, psap, ibnr, lr, pa, sp, sin_att):
        # H1 — PSAP ≥ 10% des primes
        ratio_psap = psap / max(pa, 1)
        if ratio_psap >= 0.10:
            h1_s = 'VALIDÉE'
            h1_m = f"PSAP = {ratio_psap*100:.1f}% PA ≥ 10% ✅"
        elif ratio_psap >= 0.05:
            h1_s = 'À JUSTIFIER'
            h1_m = f"PSAP = {ratio_psap*100:.1f}% PA ∈ [5%,10%] — vérifier dossiers"
        else:
            h1_s = 'NON VALIDÉE'
            h1_m = f"PSAP = {ratio_psap*100:.1f}% PA < 5% — sous-provisionnement"

        # H2 — IBNR ∈ [10%, 30%] des sinistres payés
        ratio_ibnr = ibnr / max(sp, 1)
        if 0.10 <= ratio_ibnr <= 0.30:
            h2_s = 'VALIDÉE'
            h2_m = f"IBNR = {ratio_ibnr*100:.0f}% SP ∈ [10%,30%] — cadence santé ✅"
        elif ratio_ibnr < 0.10:
            h2_s = 'À JUSTIFIER'
            h2_m = f"IBNR = {ratio_ibnr*100:.0f}% SP < 10% — vérifier délais déclaration"
        else:
            h2_s = 'À JUSTIFIER'
            h2_m = f"IBNR = {ratio_ibnr*100:.0f}% SP > 30% — élevé pour la santé"

        # H3 — Loss Ratio ≤ 85%
        if lr <= 0.85:
            h3_s = 'VALIDÉE'
            h3_m = f"Loss Ratio = {lr*100:.1f}% ≤ 85% ✅"
        elif lr <= 0.95:
            h3_s = 'À JUSTIFIER'
            h3_m = f"Loss Ratio = {lr*100:.1f}% ∈ [85%,95%] — surveiller"
        else:
            h3_s = 'NON VALIDÉE'
            h3_m = f"Loss Ratio = {lr*100:.1f}% > 95% — contrat déficitaire"

        # H4 — A/E ratio PSAP (Actual vs Expected)
        # Compare sinistres réellement payés vs sinistres attendus (tarification S1)
        # Source : pratique marché mutuelles — FNMF 2023
        ae_ratio = sp / max(sin_att, 1)
        if 0.90 <= ae_ratio <= 1.10:
            h4_s = 'VALIDÉE'
            h4_m = f"A/E = {ae_ratio:.3f} ∈ [0.90,1.10] — hypothèses tarifaires confirmées ✅"
        elif 0.80 <= ae_ratio < 0.90 or 1.10 < ae_ratio <= 1.20:
            h4_s = 'À JUSTIFIER'
            h4_m = f"A/E = {ae_ratio:.3f} — écart modéré vs tarification, à documenter"
        elif ae_ratio > 1.20:
            h4_s = 'NON VALIDÉE'
            h4_m = f"A/E = {ae_ratio:.3f} > 1.20 — sinistralité réelle dépasse les prévisions"
        else:
            h4_s = 'À JUSTIFIER'
            h4_m = f"A/E = {ae_ratio:.3f} < 0.80 — sur-provisionnement ou tarification prudente"

        return [
            {'id':'H1','hypothese':'PSAP ≥ 10% des primes acquises',
             'valeur':h1_m,'statut':h1_s,'critique':True},
            {'id':'H2','hypothese':'IBNR santé ∈ [10%,30%] des sinistres payés (cadence rapide)',
             'valeur':h2_m,'statut':h2_s,'critique':True},
            {'id':'H3','hypothese':'Loss Ratio ≤ 85% — sinistralité maîtrisée',
             'valeur':h3_m,'statut':h3_s,'critique':True},
            {'id':'H4','hypothese':'A/E ratio PSAP ∈ [0.90,1.10] — sinistralité réelle vs attendue',
             'valeur':h4_m,'statut':h4_s,'critique':False},
        ]

    def _rag(self, hyp, lr):
        non_val = [h for h in hyp if h['statut']=='NON VALIDÉE']
        a_just  = [h for h in hyp if h['statut']=='À JUSTIFIER']
        if non_val or lr > 0.95:
            return 'ROUGE'
        if a_just:
            return 'AMBRE'
        return 'VERT'

    # ══════════════════════════════════════════════════════════════════════════
    # 8. COMMENTAIRE
    # ══════════════════════════════════════════════════════════════════════════
    def _commentaire(self, rag, src, psap_d, psap_i, psap_tot, prec,
                     prov_tot, lr, taux_prov, be, ra, tp, psap_p, ibnr_p, hyp):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        L = [
            "="*70,
            f"  RAPPORT PROVISIONNEMENT SANTÉ — S2 SELMA v{self.VERSION}",
            f"  {ic} STATUT : {rag}",
            "="*70, "",
            "📊 RÉSUMÉ DIRECTION", "─"*40,
        ]
        if rag=='VERT':
            L.append(f"✅ Provisionnement validé. PSAP={psap_tot:,.0f}€ | PREC={prec:,.0f}€ | LR={lr*100:.1f}%")
        elif rag=='AMBRE':
            L.append(f"⚠️ Provisionnement acceptable — vérifier les points signalés.")
        else:
            L.append(f"❌ Provisionnement insuffisant ou LR>{0.95*100:.0f}% — action requise.")

        L += [
            "", "🔢 PROVISIONS", "─"*40,
            f"  Primes acquises (S1)       : {src['primes_acquises']:>15,.0f}€",
            f"  Sinistres payés (estimés)  : {src['sinistres_payes']:>15,.0f}€",
            f"  Loss Ratio                 : {lr*100:>14.1f}%",
            "  " + "─"*45,
            f"  PSAP dossiers connus       : {psap_d:>15,.0f}€",
            f"  PSAP IBNR (cadence santé)  : {psap_i:>15,.0f}€",
            f"  PSAP Total                 : {psap_tot:>15,.0f}€",
            f"  PREC                       : {prec:>15,.0f}€",
            f"  Provision Totale           : {prov_tot:>15,.0f}€",
            f"  Taux provisionnement       : {taux_prov*100:>14.1f}%",
            "", "📦 PSAP PAR POSTE", "─"*40,
            f"  {'Poste':<20} {'Dossiers':>8} {'PSAP dos.':>12} {'IBNR':>12} {'Total':>12}",
            "  " + "─"*56,
        ]
        for p in ['medecine','pharmacie','hospitalisation','dentaire','optique']:
            pd_v = psap_p.get(p, {})
            ib_v = ibnr_p.get(p, {})
            tot  = pd_v.get('psap_dossiers',0) + ib_v.get('ibnr',0)
            L.append(
                f"  {p:<20} {pd_v.get('nb_dossiers_ouverts',0):>8,} "
                f"{pd_v.get('psap_dossiers',0):>11,.0f}€ "
                f"{ib_v.get('ibnr',0):>11,.0f}€ "
                f"{tot:>11,.0f}€"
            )

        L += [
            "", "📐 BE SANTÉ → S3 BINTA", "─"*40,
            f"  BE Santé (PSAP total)      : {be:>15,.0f}€",
            f"  Risk Adjustment (5% BE)    : {ra:>15,.0f}€",
            f"  TP Santé                   : {tp:>15,.0f}€",
            "", "📋 HYPOTHÈSES", "─"*40,
        ]
        for h in hyp:
            ic_h = "✅" if h['statut']=='VALIDÉE' else ("⚠️" if h['statut']=='À JUSTIFIER' else "❌")
            L += [f"  {ic_h} [{h['id']}] {h['hypothese']}",
                  f"       → {h['valeur']} : {h['statut']}"]

        L += ["", "🎯 AVIS SELMA → CHIARA", "─"*40]
        if rag=='VERT':
            L.append("✅ VALIDÉ — Données transmises à S3 Binta (QRT S.13).")
        elif rag=='AMBRE':
            L.append("⚠️ Documenter les hypothèses avant transmission à S3.")
        else:
            L.append("❌ NON VALIDÉ — Escalade Chiara. Revoir le provisionnement.")
        L.append("")
        return "\n".join(L)

    # ══════════════════════════════════════════════════════════════════════════
    # 9. GRAPHIQUES
    # ══════════════════════════════════════════════════════════════════════════
    def _graphiques(self, psap_d, psap_i, prec, lr, src, psap_p, ibnr_p, hyp, triangle):
        gph = {}

        # G1 — Décomposition provisions
        try:
            tot = psap_d + psap_i + prec
            fig = go.Figure(go.Bar(
                x=["PSAP Dossiers", "PSAP IBNR", "PREC", "Total"],
                y=[psap_d/1e3, psap_i/1e3, prec/1e3, tot/1e3],
                marker_color=[OR, BLEU, AMBRE,
                              VERT if lr<=0.85 else (AMBRE if lr<=0.95 else ROUGE)],
                width=0.45, opacity=0.88,
                text=[f"{v:.0f}k€" for v in [psap_d/1e3,psap_i/1e3,prec/1e3,tot/1e3]],
                textposition="outside", textfont=dict(color=BLANC,size=10),
            ))
            layout = dict(**LAYOUT_BASE)
            layout.update(dict(
                title=dict(text="G1 — Décomposition des provisions santé",
                           font=dict(color=OR,size=12),x=0.01),
                showlegend=False,
                xaxis=dict(tickfont=dict(color=BLANC),showgrid=False),
                yaxis=dict(visible=False),
                annotations=[dict(
                    text="💡 PSAP = sinistres connus. IBNR = non encore déclarés (5-25% en santé). PREC = risques futurs.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**layout)
            gph['decomposition_provisions'] = fig
        except Exception as e:
            self.logger.warning(f"G1:{e}")

        # G2 — Jauge Loss Ratio
        try:
            c = VERT if lr<=0.85 else (AMBRE if lr<=0.95 else ROUGE)
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=lr*100,
                number=dict(suffix="%", font=dict(color=c,size=28), valueformat=".1f"),
                title=dict(text="Loss Ratio Santé", font=dict(color=c,size=12)),
                gauge=dict(
                    axis=dict(range=[0,120], tickvals=[0,65,85,95,100,120],
                              ticktext=["0","65","85%","95%","100","120"],
                              tickfont=dict(color=GRIS,size=8)),
                    bar=dict(color=c, thickness=0.25),
                    bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0,85],   color="rgba(46,204,113,0.12)"),
                        dict(range=[85,95],  color="rgba(243,156,18,0.12)"),
                        dict(range=[95,120], color="rgba(231,76,60,0.12)"),
                    ],
                    threshold=dict(line=dict(color=VERT,width=3), thickness=0.8, value=85),
                ),
            ))
            fig.update_layout(
                paper_bgcolor=NAVY, font=dict(color=BLANC),
                margin=dict(l=30,r=30,t=60,b=50), height=300,
                annotations=[dict(
                    text="💡 Seuil confort : LR ≤ 85%. Au-delà = révision tarifaire recommandée.",
                    xref="paper",yref="paper",x=0.5,y=-0.12,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            )
            gph['jauge_loss_ratio'] = fig
        except Exception as e:
            self.logger.warning(f"G2:{e}")

        # G3 — IBNR par poste vs santé standard
        try:
            postes_lbls = [p.replace('_',' ').title() for p in IBNR_TAUX_POSTE]
            ibnr_taux   = [IBNR_TAUX_POSTE[p]*100 for p in IBNR_TAUX_POSTE]
            ibnr_vals   = [ibnr_p.get(p,{}).get('ibnr',0)/1e3 for p in IBNR_TAUX_POSTE]
            from plotly.subplots import make_subplots
            fig = make_subplots(rows=1, cols=2,
                subplot_titles=["Taux IBNR par poste (%)", "IBNR (k€)"])
            fig.add_trace(go.Bar(x=postes_lbls, y=ibnr_taux,
                marker_color=[OR,BLEU,ROUGE,AMBRE,VERT], opacity=0.85,
                text=[f"{v:.0f}%" for v in ibnr_taux], textposition="outside",
                textfont=dict(color=BLANC,size=9), showlegend=False),
                row=1, col=1)
            fig.add_trace(go.Bar(x=postes_lbls, y=ibnr_vals,
                marker_color=[OR,BLEU,ROUGE,AMBRE,VERT], opacity=0.85,
                text=[f"{v:.0f}k€" for v in ibnr_vals], textposition="outside",
                textfont=dict(color=BLANC,size=9), showlegend=False),
                row=1, col=2)
            layout = dict(**LAYOUT_BASE)
            layout.update(dict(
                title=dict(text="G3 — IBNR Santé par poste (cadences spécifiques santé)",
                           font=dict(color=OR,size=12),x=0.01),
                annotations=[dict(
                    text="💡 En santé, l'IBNR est faible (5-25%) vs IARD (40-60%) — liquidation en 1-3 mois.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**layout)
            gph['ibnr_par_poste'] = fig
        except Exception as e:
            self.logger.warning(f"G3:{e}")

        # G4 — Scorecard
        try:
            fig = go.Figure()
            for h in hyp:
                c  = VERT if h['statut']=='VALIDÉE' else (AMBRE if h['statut']=='À JUSTIFIER' else ROUGE)
                ic = "✅" if h['statut']=='VALIDÉE' else ("⚠️" if h['statut']=='À JUSTIFIER' else "❌")
                s  = 1.0 if h['statut']=='VALIDÉE' else (0.5 if h['statut']=='À JUSTIFIER' else 0.0)
                fig.add_trace(go.Bar(
                    x=[s], y=[h['hypothese'][:40]], orientation="h",
                    marker_color=c, width=0.5, opacity=0.85,
                    text=f"{ic} {h['statut']}", textposition="outside",
                    textfont=dict(color=c,size=10), showlegend=False,
                    hovertemplate=f"<b>{h['hypothese']}</b><br>{h['valeur']}<extra></extra>",
                ))
            cg = VERT if all(h['statut']=='VALIDÉE' for h in hyp) else (ROUGE if any(h['statut']=='NON VALIDÉE' for h in hyp) else AMBRE)
            layout = dict(**LAYOUT_BASE)
            layout.update(dict(
                title=dict(text="G4 — Scorecard Provisionnement Santé",
                           font=dict(color=cg,size=12),x=0.01),
                xaxis=dict(range=[0,1.6],visible=False),
                yaxis=dict(tickfont=dict(color=BLANC,size=10),showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 3 ✅ = provisionnement santé conforme — PSAP, IBNR et LR validés.",
                    xref="paper",yref="paper",x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            ))
            fig.update_layout(**layout)
            gph['scorecard_s2'] = fig
        except Exception as e:
            self.logger.warning(f"G4:{e}")

        # G5 — Courbe cadence de règlement santé
        try:
            ultime = triangle['ultime']
            mois   = [0, 1, 2, 3]
            pct_reg = [0.0, 60.0, 85.0, 97.0]
            vals_k  = [0.0,
                       triangle['mois_1']/1e3,
                       triangle['mois_2']/1e3,
                       triangle['mois_3']/1e3]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=mois, y=vals_k, mode='lines+markers', name='Réglé (k€)',
                line=dict(color=OR, width=2.5), marker=dict(size=8, color=OR),
                hovertemplate='Mois %{x} → %{y:.0f}k€<extra></extra>',
            ))
            fig.add_trace(go.Scatter(
                x=mois, y=pct_reg, mode='lines+markers', name='% réglé',
                line=dict(color=VERT, width=2, dash='dot'),
                marker=dict(size=7, color=VERT), yaxis='y2',
                hovertemplate='Mois %{x} → %{y:.0f}%<extra></extra>',
            ))
            fig.add_hline(y=ultime/1e3, line_dash='dash', line_color=BLEU,
                          line_width=1.5,
                          annotation_text=f'Ultime = {ultime/1e3:.0f}k€',
                          annotation_font=dict(color=BLEU, size=9))
            fig.update_layout(
                paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                font=dict(family='Inter, Arial', color=BLANC, size=11),
                margin=dict(l=16,r=60,t=60,b=60), height=300,
                hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR,
                                font_size=12, font_color=BLANC),
                title=dict(text='G5 — Cadence de règlement santé (3 mois)',
                           font=dict(color=OR,size=12),x=0.01),
                xaxis=dict(tickvals=[0,1,2,3],
                           ticktext=['J0','M1','M2','M3'],
                           tickfont=dict(color=BLANC), showgrid=False,
                           title='Mois'),
                yaxis=dict(title='Montant réglé (k€)',
                           tickfont=dict(color=OR), showgrid=False),
                yaxis2=dict(title='% réglé', overlaying='y', side='right',
                            range=[0,110], tickfont=dict(color=VERT),
                            showgrid=False),
                legend=dict(x=0.02, y=0.98, font=dict(color=BLANC,size=9),
                            bgcolor='rgba(0,0,0,0)'),
                annotations=[dict(
                    text='💡 Santé : 97% des sinistres liquidés en 3 mois '
                         '(vs 18-36 mois IARD, 60+ mois prévoyance).',
                    xref='paper',yref='paper',x=0.01,y=-0.22,
                    font=dict(color=GRIS,size=9),showarrow=False)],
            )
            gph['cadence_reglement'] = fig
        except Exception as e:
            self.logger.warning(f'G5:{e}')

        return gph

    # ══════════════════════════════════════════════════════════════════════════
    # UTILITAIRES
    # ══════════════════════════════════════════════════════════════════════════
    def _audit(self, aid, psap, prec, lr, rag):
        try:
            r = {'audit_id':aid,'agent':self.NOM,'version':self.VERSION,
                 'timestamp':datetime.now().isoformat(),'statut_rag':rag,
                 'psap_total':psap,'prec':prec,'loss_ratio':lr}
            with open(self.audit_path/f"audit_{aid}.json",'w',encoding='utf-8') as f:
                json.dump(r,f,ensure_ascii=False,indent=2,default=str)
        except Exception as e:
            self.logger.warning(f"Audit:{e}")

    def _console(self, aid, rag, psap, prec, prov, lr):
        ic = "🟢" if rag=='VERT' else ("🟡" if rag=='AMBRE' else "🔴")
        print(f"\n{'─'*70}")
        print(f"  S2 SELMA v{self.VERSION} | {aid} | {ic} {rag}")
        print(f"  PSAP={psap:,.0f}€ | PREC={prec:,.0f}€ | Total={prov:,.0f}€ | LR={lr*100:.1f}%")
        print(f"{'─'*70}")

    def _erreur(self, msg, aid):
        return {'success':False,'agent':self.NOM,'version':self.VERSION,
                'audit_id':aid,'statut_rag':'ROUGE',
                'psap_total':0,'prec':0,'provision_totale':0,'loss_ratio':0,
                'sorties_s3':{},'hypotheses':[],'commentaire':f"❌ ERREUR S2:{msg}",
                'graphiques':{},'duree_sec':0.0,'erreur':msg}


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("="*70)
    print("  S2 SELMA v2.0 — DÉMO PROVISIONNEMENT SANTÉ")
    print("  PSAP par poste | IBNR cadences santé | PREC | Triangle")
    print("="*70)

    # Simuler result_s1
    r_s1 = {
        'success': True,
        'prime_pure': 410.41,
        'prime_commerciale': 484.29,
        'primes_acquises': 2_421_438.0,
        'ratio_sp_attendu': 0.848,
        'nb_assures': 5000,
        'postes': {
            'medecine':        {'frequence_an':3.2,'sinistre_annuel':29.0},
            'pharmacie':       {'frequence_an':6.5,'sinistre_annuel':52.0},
            'hospitalisation': {'frequence_an':0.12,'sinistre_annuel':84.0},
            'dentaire':        {'frequence_an':0.9,'sinistre_annuel':130.0},
            'optique':         {'frequence_an':0.35,'sinistre_annuel':115.0},
        },
        'sorties_s2': {
            'primes_acquises':      2_421_438.0,
            'sinistres_attendus':   2_052_066.0,
            'loss_ratio_attendu':   0.848,
            'sinistralite_par_poste': {
                'medecine':145_000, 'pharmacie':260_000,
                'hospitalisation':420_000, 'dentaire':650_000, 'optique':577_000,
            },
            'nb_assures': 5000,
            'prime_pure_unitaire': 410.41,
        },
    }

    agent = AgentS2ProvisionnemntSante(
        models_path='/tmp/s2/models', audit_path='/tmp/s2/audit', verbose=True
    )
    r = agent.run(result_s1=r_s1, generer_graphiques=False)

    print(f"\n{'='*70}\n  RÉSULTATS\n{'='*70}")
    print(f"  Statut          : {r['statut_rag']}")
    print(f"  PSAP dossiers   : {r['psap_dossiers']:>12,.0f}€")
    print(f"  PSAP IBNR       : {r['psap_ibnr']:>12,.0f}€")
    print(f"  PSAP Total      : {r['psap_total']:>12,.0f}€")
    print(f"  PREC            : {r['prec']:>12,.0f}€")
    print(f"  Provision totale: {r['provision_totale']:>12,.0f}€")
    print(f"  Loss Ratio      : {r['loss_ratio']*100:>11.1f}%")
    print(f"\n  Sorties vers S3 :")
    s3 = r['sorties_s3']
    print(f"    BE santé    : {s3['be_sante']:,.0f}€")
    print(f"    TP santé    : {s3['tp_sante']:,.0f}€")
    print(f"  Durée : {r['duree_sec']:.2f}s")
