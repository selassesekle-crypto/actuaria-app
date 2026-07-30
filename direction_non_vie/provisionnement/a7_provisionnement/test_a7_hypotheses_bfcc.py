# =============================================================================
#  Tests — n2_hypotheses_bfcc.py : BFCC-H1 … BFCC-H5
#
#  Quatre verrous portent le lot, les autres tests les entourent :
#    · ORACLE DU GUIDE — la cadence publiée en Figure 19 du guide de l'Institut
#      des Actuaires satisfait l'hypothèse (H2) qu'il énonce en Figure 21.
#      Si notre lecture de (H2) était fausse, l'exemple du guide échouerait.
#    · INVARIANT — sur GenIns et RAA, la cadence est admissible PARTOUT : le test
#      ne doit pas se déclencher sur des données saines.
#    · NON-RÉGRESSION ALGÉBRIQUE — le loss ratio a priori de BF ne doit JAMAIS
#      égaler celui de Cape Cod. Sous pondération `exposition × cadence` sur
#      toutes les années, les deux sont identiques et BF DEVIENT Cape Cod ; c'est
#      la sélection d'une fenêtre qui maintient les deux méthodes distinctes.
#    · PLANCHER — moins de deux années exploitables ⇒ le loss ratio dérivé est
#      refusé, jamais fabriqué.
# =============================================================================

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement,
)
from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_bfcc import (
    CODES, bfcc_h1_independance,
    bfcc_h2_cadence, bfcc_h3_structure, bfcc_h4_apriori, bfcc_h5_stabilite_lr,
    couverture_cadence_par_annee, lignes_hypotheses_bfcc,
    verifier_hypotheses_bfcc,
)
from direction_non_vie.provisionnement.a7_provisionnement.n3.bf_cape_cod import (
    CV_LR_MAX, ECART_LR_REFERENCE, LR_PLAGE_ALERTE, LR_PLAGE_DURE,
    MIN_ANNEES_APRIORI as _MIN, bornhuetter_ferguson, cape_cod,
)
from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import (
    cadence_admissible, calculer_facteurs, calculer_facteurs_cumules,
    calculer_pct_developpe, chain_ladder, pct_developpe_brut,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_bf_cape_cod import (
    GUIDE_CADENCE,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA, _TRI_RECOURS, _TRI_TOUT_DECROISSANT,
)

VALIDEE, A_JUSTIFIER = 'VALIDÉE', 'À JUSTIFIER'
NON_VALIDEE, NON_TESTABLE = 'NON VALIDÉE', 'NON TESTABLE'


def _cadence(triangle, tail=1.0):
    """Cadence brute et masque d'admissibilité d'un triangle."""
    C = np.array(triangle, dtype=float)
    facteurs, _ = calculer_facteurs(C, 'standard')
    f_cum = calculer_facteurs_cumules(facteurs, tail)
    brut = pct_developpe_brut(C, f_cum)
    return C, brut, cadence_admissible(brut)


def _exposition(triangle, loss_ratio=0.70):
    C = np.array(triangle, dtype=float)
    return C.max(axis=1) * 1.6 / loss_ratio


# =============================================================================
#  VERROU 1 — ORACLE PUBLIÉ : la cadence du guide satisfait sa propre (H2)
# =============================================================================

class T1_Oracle_Cadence_Du_Guide(unittest.TestCase):
    """L'hypothèse (H2) du guide, éprouvée sur la cadence que le guide publie."""

    def test_la_cadence_publiee_satisfait_h2(self):
        # GUIDE_CADENCE est indexée par PÉRIODE DE DÉVELOPPEMENT et croît vers 1.
        # Indexée par ANNÉE D'ORIGINE, la plus mature en tête, elle décroît :
        # c'est la lecture qu'applique `cadence_admissible`.
        par_annee = GUIDE_CADENCE[::-1]
        ok = cadence_admissible(par_annee)
        self.assertTrue(bool(np.all(ok)),
                        f"la cadence publiée par le guide doit satisfaire (H2) : {ok}")
        # Les trois conditions de la Figure 21, vérifiées une à une.
        self.assertTrue(bool(np.all(GUIDE_CADENCE > 0)))
        self.assertTrue(bool(np.all(GUIDE_CADENCE <= 1.0)))
        self.assertTrue(bool(np.all(np.diff(GUIDE_CADENCE) >= 0)),
                        "éléments consécutifs croissants (Figure 21)")
        self.assertAlmostEqual(float(GUIDE_CADENCE[-1]), 1.0, places=6,
                               msg="coefficient à ultime égal à 1 (Figure 21)")
        print("    OK BFCC-1 oracle du guide : la cadence de la Figure 19 "
              "satisfait l'hypothèse (H2) de la Figure 21 sur ses 11 périodes")

    def test_h2_valide_sur_la_cadence_du_guide(self):
        """Le verdict complet, pas seulement le masque."""
        par_annee = GUIDE_CADENCE[::-1]
        r = bfcc_h2_cadence(par_annee, cadence_admissible(par_annee))
        self.assertEqual(r.statut, VALIDEE)
        self.assertEqual(r.extras['annees_non_admissibles'], [])
        self.assertEqual(r.source_critere, 'guide IA 2023')
        print(f"    OK BFCC-2 verdict sur l'oracle : {r.statut}")


# =============================================================================
#  VERROU 2 — INVARIANT : rien ne se déclenche sur des données saines
# =============================================================================

class T2_Invariant_Donnees_Saines(unittest.TestCase):
    """Un test d'hypothèse qui se déclenche sur un triangle sain est inutilisable."""

    def test_genins_et_raa_entierement_admissibles(self):
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA)):
            _, brut, ok = _cadence(tri)
            self.assertTrue(bool(np.all(ok)),
                            f"{nom} : années non admissibles {np.flatnonzero(~ok)}")
            # La cadence écrêtée est alors IDENTIQUE à la brute : l'écrêtage
            # n'a rien à corriger, donc rien à masquer.
            C = np.array(tri, dtype=float)
            facteurs, _ = calculer_facteurs(C, 'standard')
            clip = calculer_pct_developpe(C, calculer_facteurs_cumules(facteurs, 1.0))
            np.testing.assert_allclose(brut, clip, rtol=0, atol=1e-12)
            print(f"    OK BFCC-3 {nom} : cadence admissible sur {len(ok)}/{len(ok)} "
                  f"années, brute == écrêtée")

    def test_le_recours_est_detecte_lui(self):
        """Contre-épreuve : sans elle, le test précédent pourrait être vide."""
        attendu = {'RECOURS': 1, 'DECR': 5}
        for nom, tri in (('RECOURS', _TRI_RECOURS), ('DECR', _TRI_TOUT_DECROISSANT)):
            _, _, ok = _cadence(tri)
            fautives = list(np.flatnonzero(~ok))
            self.assertEqual(len(fautives), attendu[nom],
                             f"{nom} : {len(fautives)} années fautives {fautives}")
            print(f"    OK BFCC-4 {nom} : {len(fautives)} année(s) non admissible(s) "
                  f"{fautives} sur {len(ok)}")


# =============================================================================
#  VERROU 3 — NON-RÉGRESSION ALGÉBRIQUE : BF ne doit pas devenir Cape Cod
# =============================================================================

class T3_BF_Nest_Pas_Cape_Cod(unittest.TestCase):
    """Le loss ratio a priori de BF ne doit jamais coïncider avec celui de Cape Cod.

    Démonstration reproduite ici : pondérer la moyenne de BF par
    `exposition × cadence` SUR TOUTES LES ANNÉES donne exactement le loss ratio
    de Cape Cod, puisque `U[i] = C[i] / α[i]` —

        Σ (expoᵢ·αᵢ)·(Uᵢ/expoᵢ) / Σ (expoᵢ·αᵢ) = Σ Cᵢ / Σ (expoᵢ·αᵢ)

    et comme les deux méthodes partagent la formule `LR × expo × (1 − α)`, BF
    deviendrait Cape Cod À L'IDENTIQUE. C'est la SÉLECTION d'une fenêtre mature,
    et elle seule, qui les maintient distinctes.
    """

    def test_la_ponderation_expo_x_cadence_reproduit_cape_cod(self):
        """On PROUVE l'identité — pour verrouiller ce qu'il ne faut pas faire."""
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA)):
            C, _, ok = _cadence(tri)
            facteurs, _ = calculer_facteurs(C, 'standard')
            pct = calculer_pct_developpe(C, calculer_facteurs_cumules(facteurs, 1.0))
            cl = chain_ladder(C, annee_base_reserve=1, tail_force=1.0)
            U = np.array(cl['ultimates'], dtype=float)
            ld = np.array(cl['last_diagonale'], dtype=float)
            expo = _exposition(tri)
            poids = expo * pct
            lr_pondere = float(np.sum(poids * (U / expo)) / np.sum(poids))
            r_cc = cape_cod(C, pct, ld, exposition=expo, annee_base=1,
                            cadence_ok=ok)
            self.assertAlmostEqual(lr_pondere, r_cc['lr_cape_cod'], places=3,
                                   msg=f"{nom} : l'identité doit tenir")
            print(f"    OK BFCC-5 {nom} : pondération expo×cadence = Cape Cod "
                  f"({lr_pondere:.4%}) — c'est bien le piège à éviter")

    def test_le_lr_reellement_produit_par_bf_en_differe(self):
        """Le verrou : ce que le code produit ne doit PAS être ce loss ratio."""
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA)):
            C, _, ok = _cadence(tri)
            facteurs, _ = calculer_facteurs(C, 'standard')
            pct = calculer_pct_developpe(C, calculer_facteurs_cumules(facteurs, 1.0))
            cl = chain_ladder(C, annee_base_reserve=1, tail_force=1.0)
            U = np.array(cl['ultimates'], dtype=float)
            ld = np.array(cl['last_diagonale'], dtype=float)
            expo = _exposition(tri)
            r_bf = bornhuetter_ferguson(C, pct, ld, U, exposition=expo,
                                        annee_base=1, cadence_ok=ok)
            r_cc = cape_cod(C, pct, ld, exposition=expo, annee_base=1,
                            cadence_ok=ok)
            self.assertNotAlmostEqual(
                r_bf['lr_apriori'], r_cc['lr_cape_cod'], places=4,
                msg=(f"{nom} : BF et Cape Cod produisent le MÊME loss ratio — "
                     f"les deux méthodes ont fusionné, cf. la démonstration "
                     f"en tête de cette classe"))
            # Et les IBNR en diffèrent bien, année par année.
            self.assertFalse(
                np.allclose(r_bf['ibnr_par_annee'], r_cc['ibnr_par_annee']),
                f"{nom} : IBNR BF et Cape Cod identiques")
            print(f"    OK BFCC-6 {nom} : LR BF {r_bf['lr_apriori']:.4%} ≠ "
                  f"LR Cape Cod {r_cc['lr_cape_cod']:.4%}")


# =============================================================================
#  VERROU 4 — PLANCHER : moins de deux années ⇒ refus, pas fabrication
# =============================================================================

class T4_Plancher_Deux_Annees(unittest.TestCase):
    """Avec une seule année, la dispersion vaut zéro PAR CONSTRUCTION."""

    def test_triangle_tout_decroissant_refuse_le_lr_derive(self):
        C, _, ok = _cadence(_TRI_TOUT_DECROISSANT)
        facteurs, _ = calculer_facteurs(C, 'standard')
        pct = calculer_pct_developpe(C, calculer_facteurs_cumules(facteurs, 1.0))
        cl = chain_ladder(C, annee_base_reserve=1, tail_force=1.0)
        r = bornhuetter_ferguson(
            C, pct, np.array(cl['last_diagonale'], dtype=float),
            np.array(cl['ultimates'], dtype=float),
            exposition=_exposition(_TRI_TOUT_DECROISSANT), annee_base=1,
            cadence_ok=ok)
        self.assertFalse(r['disponible'],
                         "une seule année admissible : BF ne doit PAS produire "
                         "de chiffre")
        self.assertEqual(r['source_lr'], 'non calculée')
        self.assertIsNone(r['lr_apriori'])
        print(f"    OK BFCC-7 tout décroissant : {int(ok.sum())} année(s) "
              f"admissible(s) < {_MIN} → loss ratio dérivé REFUSÉ")

    def test_le_refus_devient_non_testable_et_non_valide(self):
        """Un refus n'est pas un échec de l'hypothèse : il est NON TESTABLE."""
        bf = {'disponible': False, 'source_lr': 'refuse', 'lr_apriori': None,
              'detail_lr': {'annees_retenues': [0], 'annees_ecartees': [1, 2],
                            'cv': 0.0, 'fenetre': 3}}
        r = bfcc_h4_apriori(bf, LR_PLAGE_ALERTE, LR_PLAGE_DURE, CV_LR_MAX,
                            ECART_LR_REFERENCE)
        self.assertEqual(r.statut, NON_TESTABLE)
        self.assertIn('§2.b.i p14', r.message)
        print("    OK BFCC-8 refus → NON TESTABLE, et le message renvoie aux "
              "cinq sources du guide")

    def test_une_annee_ne_produit_jamais_un_verdict_favorable(self):
        """Le cœur du plancher : k=1 donnerait CV=0, donc le meilleur score."""
        expo = np.array([100.0, 100.0, 100.0])
        ult  = np.array([60.0, 60.0, 60.0])
        alertes, infos = [], []
        from direction_non_vie.provisionnement.a7_provisionnement.n3.bf_cape_cod \
            import _loss_ratio_apriori
        lr, source, detail = _loss_ratio_apriori(
            expo, ult, 3, None, None, '', None,
            np.array([True, False, False]), alertes, infos)
        self.assertIsNone(lr)
        self.assertEqual(source, 'refuse')
        self.assertEqual(detail['annees_retenues'], [0])
        print("    OK BFCC-9 une seule année exploitable → refus, malgré un "
              "CV nul qui aurait été le verdict le plus favorable")


# =============================================================================
#  BFCC-H2 — EXCLUSION ANNÉE PAR ANNÉE
# =============================================================================

class T5_Exclusion_Par_Annee(unittest.TestCase):
    """La cadence retire BF et Cape Cod des SEULES années fautives."""

    def test_couverture_cadence_est_par_annee(self):
        _, brut, ok = _cadence(_TRI_RECOURS)
        r = bfcc_h2_cadence(brut, ok)
        cov = couverture_cadence_par_annee(r)
        self.assertEqual(len(cov), len(brut))
        fautives = [i for i, s in cov.items() if s == NON_VALIDEE]
        saines   = [i for i, s in cov.items() if s == VALIDEE]
        self.assertEqual(len(fautives), 1)
        self.assertEqual(len(saines), len(brut) - 1,
                         "les années saines gardent leur couverture")
        print(f"    OK BFCC-10 recours : {fautives} exclue(s), {saines} conservée(s)")

    def test_chain_ladder_porte_les_annees_ecartees(self):
        """Le pipeline complet : l'année fautive n'a plus que Chain Ladder."""
        C = np.array(_TRI_RECOURS, dtype=float)
        r = AgentA7Provisionnement(verbose=False).run(
            source=C, mode_declare='cumule', primes=_exposition(_TRI_RECOURS),
            generer_graphiques=False)
        self.assertTrue(r['success'], r.get('erreur'))
        cov = r['n2']['bfcc']['couverture_cadence']
        fautives = [i for i, s in cov.items() if s == NON_VALIDEE]
        self.assertTrue(fautives, "le scénario doit exercer une exclusion")
        par_annee = {d['annee']: d for d in r['n4']['selection_par_annee']}
        for i in fautives:
            if i in par_annee and not par_annee[i]['sous_filet']:
                self.assertEqual(par_annee[i]['methodes'], ['chain_ladder'],
                                 f"année {i} : seule Chain Ladder doit rester")
                self.assertTrue(par_annee[i]['cadence_ko'])
        autres = [d for i, d in par_annee.items()
                  if i not in fautives and not d['sous_filet'] and d['methodes']]
        self.assertTrue(any(len(d['methodes']) > 1 for d in autres),
                        "les autres années gardent plusieurs méthodes")
        print(f"    OK BFCC-11 pipeline : années {fautives} sur Chain Ladder "
              f"seule, les autres conservent {max(len(d['methodes']) for d in autres)} "
              f"méthodes")


# =============================================================================
#  BFCC-H1 / H3 — REPRISES, PAS RÉIMPLÉMENTATIONS
# =============================================================================

class T6_Reprises(unittest.TestCase):
    """Le guide dit (H1) identique à Chain Ladder ; on reprend, on ne recalcule pas."""

    def test_h1_reprend_le_statut_de_clm_h1(self):
        for statut in (VALIDEE, A_JUSTIFIER, NON_VALIDEE):
            r = bfcc_h1_independance({'statut': statut, 'valeur': 1.23,
                                      'critere': 'critère CLM', 'message': 'msg',
                                      'detail': []})
            self.assertEqual(r.statut, statut)
            self.assertEqual(r.extras['repris_de'], 'CLM-H1')
            self.assertEqual(r.critere, 'critère CLM')
        r = bfcc_h1_independance(None)
        self.assertEqual(r.statut, NON_TESTABLE)
        print("    OK BFCC-12 H1 reprend CLM-H1 à l'identique (3 statuts + absence)")

    def test_h3_reprend_le_test_calendaire_du_glm_apc(self):
        for p, attendu in ((0.50, VALIDEE), (0.03, A_JUSTIFIER),
                           (0.001, NON_VALIDEE)):
            r = bfcc_h3_structure({'success': True, 'glm_disponible': True,
                                   'p_calendaire': p})
            self.assertEqual(r.statut, attendu, f"p={p}")
        self.assertEqual(bfcc_h3_structure({}).statut, NON_TESTABLE)
        self.assertEqual(bfcc_h3_structure(None).statut, NON_TESTABLE)
        print("    OK BFCC-13 H3 reprend le test F calendaire du GLM APC")

    def test_h3_ne_gate_rien_dans_ce_lot(self):
        r = bfcc_h3_structure({'success': True, 'glm_disponible': True,
                               'p_calendaire': 0.0001})
        self.assertEqual(r.statut, NON_VALIDEE)
        self.assertEqual(r.critique_pour, (),
                         "BFCC-H3 est DESCRIPTIVE dans ce lot")
        print("    OK BFCC-14 H3 non validée n'écarte aucune méthode "
              "(critique_pour vide)")


# =============================================================================
#  BFCC-H4 — LA PLAGE COMPTE VRAIMENT, MAINTENANT
# =============================================================================

class T7_H4_Plausibilite(unittest.TestCase):
    """L'ancien score valait `100 − CV×200` : la plage était calculée puis ignorée."""

    @staticmethod
    def _bf(lr, cv=0.05, source='matures'):
        return {'disponible': True, 'lr_apriori': lr, 'source_lr': source,
                'detail_lr': {'annees_retenues': [0, 1, 2], 'annees_ecartees': [],
                              'cv': cv, 'fenetre': 3}}

    def test_un_loss_ratio_aberrant_stable_est_desormais_rejete(self):
        """Mesuré avant ce lot : LR = 364,7 % obtenait 81/100 et passait."""
        r = bfcc_h4_apriori(self._bf(3.647, cv=0.092), LR_PLAGE_ALERTE,
                            LR_PLAGE_DURE, CV_LR_MAX, ECART_LR_REFERENCE)
        self.assertEqual(r.statut, A_JUSTIFIER)
        r_dur = bfcc_h4_apriori(self._bf(6.0, cv=0.01), LR_PLAGE_ALERTE,
                                LR_PLAGE_DURE, CV_LR_MAX, ECART_LR_REFERENCE)
        self.assertEqual(r_dur.statut, NON_VALIDEE,
                         "hors plage DURE malgré une dispersion nulle")
        print("    OK BFCC-15 LR = 600 % à CV 1 % → NON VALIDÉE (avant : 98/100)")

    def test_un_loss_ratio_sain_reste_valide(self):
        r = bfcc_h4_apriori(self._bf(0.65, cv=0.08), LR_PLAGE_ALERTE,
                            LR_PLAGE_DURE, CV_LR_MAX, ECART_LR_REFERENCE)
        self.assertEqual(r.statut, VALIDEE)
        print(f"    OK BFCC-16 LR = 65 % à CV 8 % → {r.statut}")

    def test_la_dispersion_reste_un_motif(self):
        r = bfcc_h4_apriori(self._bf(0.65, cv=0.40), LR_PLAGE_ALERTE,
                            LR_PLAGE_DURE, CV_LR_MAX, ECART_LR_REFERENCE)
        self.assertEqual(r.statut, A_JUSTIFIER)
        self.assertIn('dispersion', r.message)
        print("    OK BFCC-17 CV 40 % → À JUSTIFIER (le critère d'avant survit)")

    def test_les_bornes_valent_aussi_pour_le_lr_fourni(self):
        """L'actuaire assume son chiffre ; 900 % reste 900 %."""
        r = bfcc_h4_apriori(self._bf(9.0, cv=0.0, source='manuel'),
                            LR_PLAGE_ALERTE, LR_PLAGE_DURE, CV_LR_MAX,
                            ECART_LR_REFERENCE)
        self.assertEqual(r.statut, NON_VALIDEE)
        print("    OK BFCC-18 LR manuel de 900 % → NON VALIDÉE")

    def test_la_charge_ultime_a_priori_est_pleinement_exogene(self):
        r = bfcc_h4_apriori(
            {'disponible': True, 'lr_apriori': None,
             'source_lr': 'ultime_apriori', 'detail_lr': {}},
            LR_PLAGE_ALERTE, LR_PLAGE_DURE, CV_LR_MAX, ECART_LR_REFERENCE)
        self.assertEqual(r.statut, VALIDEE)
        print("    OK BFCC-19 charge ultime a priori fournie → VALIDÉE")

    def test_la_provenance_est_publiee(self):
        r = bfcc_h4_apriori(self._bf(0.65), LR_PLAGE_ALERTE, LR_PLAGE_DURE,
                            CV_LR_MAX, ECART_LR_REFERENCE)
        self.assertEqual(r.extras['source'], 'matures')
        self.assertIn('ALLOCATION', r.message)
        self.assertIn('NIVEAU', r.message)
        print("    OK BFCC-20 provenance publiée, avec ce qu'elle implique")


# =============================================================================
#  BFCC-H5 — DOUBLE CRITICITÉ
# =============================================================================

class T8_H5_Stabilite(unittest.TestCase):
    """Une dérive du loss ratio invalide Cape Cod, pas Bornhuetter-Ferguson."""

    def test_h5_ne_gate_que_cape_cod(self):
        r = bfcc_h5_stabilite_lr(np.arange(1.0, 11.0), np.ones(10), None)
        self.assertEqual(r.critique_pour, ('cape_cod',))
        print(f"    OK BFCC-21 critique_pour = {r.critique_pour} "
              f"(BF garde son a priori par année)")

    def test_un_loss_ratio_stable_est_valide(self):
        expo = np.full(10, 100.0)
        ult  = np.full(10, 60.0) * (1 + 0.01 * np.array(
            [1, -1, 1, -1, 1, -1, 1, -1, 1, -1]))
        r = bfcc_h5_stabilite_lr(ult, expo, None)
        self.assertEqual(r.statut, VALIDEE)
        print(f"    OK BFCC-22 loss ratio stable → {r.statut} (p={r.valeur})")

    def test_une_derive_franche_est_detectee(self):
        expo = np.full(10, 100.0)
        ult  = 60.0 * 1.08 ** np.arange(10)
        r = bfcc_h5_stabilite_lr(ult, expo, None)
        self.assertEqual(r.statut, NON_VALIDEE)
        self.assertGreater(r.extras['derive_relative_annuelle'], 0.05)
        print(f"    OK BFCC-23 dérive +8 %/an → {r.statut} "
              f"({r.extras['derive_relative_annuelle']:+.1%}/an, p={r.valeur})")

    def test_sans_exposition_h5_est_non_testable(self):
        r = bfcc_h5_stabilite_lr(np.arange(1.0, 11.0), None, None)
        self.assertEqual(r.statut, NON_TESTABLE)
        r2 = bfcc_h5_stabilite_lr(np.arange(1.0, 4.0), np.ones(3), None)
        self.assertEqual(r2.statut, NON_TESTABLE, "3 années : pas assez")
        print("    OK BFCC-24 sans exposition ou sous 4 années → NON TESTABLE")

    def test_les_annees_inadmissibles_sont_exclues_du_test(self):
        expo = np.full(10, 100.0)
        ult  = np.full(10, 60.0)
        ult[3] = 5000.0                      # année aberrante…
        ok = np.ones(10, dtype=bool)
        ok[3] = False                        # …mais déclarée inadmissible
        r = bfcc_h5_stabilite_lr(ult, expo, ok)
        self.assertEqual(r.extras['n'], 9)
        self.assertEqual(r.statut, VALIDEE)
        print("    OK BFCC-25 une année à cadence inadmissible n'influence pas H5")


# =============================================================================
#  P1 — UN SEUL LOSS RATIO, UN SEUL PROPRIÉTAIRE
# =============================================================================

class T9_Un_Seul_Loss_Ratio(unittest.TestCase):
    """N2 ne calcule plus aucun loss ratio, et le proxy inventé a disparu."""

    def test_n2_nexpose_plus_ni_h3_ni_scores(self):
        from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses \
            import HypothesesValidator
        n2 = HypothesesValidator().valider(np.array(GENINS, dtype=float))
        for interdit in ('h3_apriori_bf', 'scores_confiance'):
            self.assertNotIn(interdit, n2,
                             f"'{interdit}' doit avoir disparu de N2")
        print("    OK BFCC-26 N2 n'expose plus h3_apriori_bf ni scores_confiance")

    def test_le_proxy_invente_a_disparu_du_source(self):
        """Verrou textuel : la constante 0.30 du proxy ne doit pas revenir."""
        import inspect
        import direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses as mod
        src = inspect.getsource(mod)
        # Le proxy s'écrivait `prime_proxy = c0 / 0.30`.
        self.assertNotIn('prime_proxy', src)
        self.assertNotIn('proxy_sans_primes', src)
        self.assertNotIn('lr_apriori', src.split('=' * 70)[-1],
                         "N2 ne doit plus produire de loss ratio")
        print("    OK BFCC-27 le proxy `c0 / 0.30` a disparu du source de N2")

    def test_le_lr_affiche_est_celui_de_n3(self):
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.array(GENINS, dtype=float), mode_declare='cumule',
            primes=_exposition(GENINS), generer_graphiques=False)
        self.assertTrue(r['success'], r.get('erreur'))
        resume = r['audit_trail']['n2_resume']
        self.assertEqual(resume['lr_apriori'], r['n3']['bf']['lr_apriori'])
        self.assertEqual(resume['lr_apriori_source'], r['n3']['bf']['source_lr'])
        # L'audit ACPR ne doit plus porter trace de l'ancien mécanisme.
        self.assertNotIn('scores', resume)
        self.assertNotIn('h3_lr', resume)
        print(f"    OK BFCC-28 le résumé publie le LR de N3 "
              f"({r['n3']['bf']['lr_apriori']:.1%}, "
              f"source {r['n3']['bf']['source_lr']})")


# =============================================================================
#  P2 / P4 — DÉCOMPOSITION ET RECOUPEMENT
# =============================================================================

class T10_Decomposition_Et_Recoupement(unittest.TestCase):

    def test_la_decomposition_somme_a_lultime(self):
        C, _, ok = _cadence(GENINS)
        facteurs, _ = calculer_facteurs(C, 'standard')
        pct = calculer_pct_developpe(C, calculer_facteurs_cumules(facteurs, 1.0))
        cl = chain_ladder(C, annee_base_reserve=1, tail_force=1.0)
        r = bornhuetter_ferguson(
            C, pct, np.array(cl['last_diagonale'], dtype=float),
            np.array(cl['ultimates'], dtype=float),
            exposition=_exposition(GENINS), annee_base=1, cadence_ok=ok)
        for ligne in r['decomposition']:
            self.assertAlmostEqual(
                ligne['part_chain_ladder'] + ligne['part_apriori'],
                ligne['ultime'], delta=0.02,
                msg=f"année {ligne['annee']} : les deux parts doivent sommer")
            self.assertAlmostEqual(ligne['poids_credibilite'],
                                   float(pct[ligne['annee']]), places=6)
        print(f"    OK BFCC-29 décomposition : {len(r['decomposition'])} années, "
              f"parts sommant à l'ultime, poids = la cadence")

    def test_le_recoupement_est_informatif_et_le_dit(self):
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.array(GENINS, dtype=float), mode_declare='cumule',
            primes=_exposition(GENINS), generer_graphiques=False)
        rec = r['n2']['bfcc']['recoupement_lr']
        self.assertTrue(rec['comparable'])
        self.assertIn("n'est pas un test d'indépendance", rec['message'])
        print(f"    OK BFCC-30 recoupement : BF {rec['lr_bf']:.1%} vs "
              f"Cape Cod {rec['lr_cape_cod']:.1%}, écart {rec['ecart']:.1%}")


# =============================================================================
#  GOUVERNANCE ET PÉRIMÈTRE
# =============================================================================

class T11_Gouvernance(unittest.TestCase):

    def test_un_be_entierement_ancre_sur_cl_ne_sort_pas_en_vert(self):
        from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate \
            import _niveau_ancre_sur_chain_ladder
        cas = [
            ({'bf': {'source_lr': 'matures'}},
             {'chain_ladder': 1.0, 'bornhuetter_ferguson': 1.0}, True),
            ({'bf': {'source_lr': 'manuel'}},
             {'chain_ladder': 1.0, 'bornhuetter_ferguson': 1.0}, False),
            ({'bf': {'source_lr': 'ultime_apriori'}},
             {'chain_ladder': 1.0, 'bornhuetter_ferguson': 1.0}, False),
            ({'bf': {'source_lr': 'matures'}},
             {'chain_ladder': 1.0, 'bornhuetter_ferguson': 1.0,
              'cape_cod': 1.0}, False),
            ({'bf': {}}, {'chain_ladder': 1.0}, True),
        ]
        for n3, incluses, attendu in cas:
            self.assertEqual(_niveau_ancre_sur_chain_ladder(n3, incluses), attendu,
                             f"{n3} / {sorted(incluses)}")
        print("    OK BFCC-31 ancrage sur Chain Ladder : 5 configurations")

    def test_une_hypothese_a_justifier_interdit_le_vert(self):
        """L'état intermédiaire doit avoir une conséquence, sinon il ne sert à rien."""
        from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate \
            import _hypotheses_a_justifier
        n2 = {'bfcc': {'hypotheses': {
            'BFCC-H3': {'statut': A_JUSTIFIER, 'critique_pour': []},
            'BFCC-H4': {'statut': A_JUSTIFIER,
                        'critique_pour': ['bornhuetter_ferguson']},
            'BFCC-H5': {'statut': A_JUSTIFIER, 'critique_pour': ['cape_cod']},
        }}}
        # BF retenue, Cape Cod non : seule H4 doit plafonner.
        self.assertEqual(
            _hypotheses_a_justifier(n2, {'chain_ladder': 1.0,
                                         'bornhuetter_ferguson': 1.0}),
            ['BFCC-H4'])
        # Ni l'une ni l'autre retenue : rien ne plafonne.
        self.assertEqual(_hypotheses_a_justifier(n2, {'chain_ladder': 1.0}), [])
        # BFCC-H3 est DESCRIPTIVE : `critique_pour` vide ne plafonne jamais.
        n2_h3 = {'bfcc': {'hypotheses': {
            'BFCC-H3': {'statut': A_JUSTIFIER, 'critique_pour': []}}}}
        self.assertEqual(
            _hypotheses_a_justifier(n2_h3, {'chain_ladder': 1.0,
                                            'bornhuetter_ferguson': 1.0}), [])
        print("    OK BFCC-36 À JUSTIFIER plafonne, filtré par méthode retenue, "
              "et jamais depuis une hypothèse descriptive")

    def test_les_annees_a_cadence_retiree_sont_publiees(self):
        """Sans cette clé, le Best Estimate bougerait sans que l'on sache où."""
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.array(_TRI_RECOURS, dtype=float), mode_declare='cumule',
            primes=_exposition(_TRI_RECOURS), generer_graphiques=False)
        self.assertIn('annees_cadence_ko', r['n4'])
        self.assertIn('hypotheses_a_justifier', r['n4'])
        cov = r['n2']['bfcc']['couverture_cadence']
        attendu = sorted(i for i, s in cov.items()
                         if s == NON_VALIDEE
                         and i >= r['n3']['chain_ladder']['annee_base_reserve'])
        self.assertEqual(sorted(r['n4']['annees_cadence_ko']), attendu)
        print(f"    OK BFCC-37 années à cadence retirée publiées : "
              f"{r['n4']['annees_cadence_ko']}")

    def test_le_module_ne_tire_aucune_consequence(self):
        """VERROU DE PÉRIMÈTRE — même discipline que CLM."""
        import ast, inspect
        import direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_bfcc as mod
        arbre = ast.parse(inspect.getsource(mod))
        noms = {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name)}
        noms |= {n.attr for n in ast.walk(arbre) if isinstance(n, ast.Attribute)}
        for interdit in ('methodes_incluses', 'scores_confiance', 'poids',
                         'best_estimate', 'seuil_score'):
            self.assertNotIn(interdit, noms,
                             f"'{interdit}' : ce module ne doit rien décider")
        print("    OK BFCC-32 verrou de périmètre : aucune conséquence tirée")

    def test_le_point_dentree_rend_les_cinq_verdicts_et_les_couvertures(self):
        """`verifier_hypotheses_bfcc` — la porte que l'agent appelle."""
        C, brut, ok = _cadence(_TRI_RECOURS)
        facteurs, _ = calculer_facteurs(C, 'standard')
        pct = calculer_pct_developpe(C, calculer_facteurs_cumules(facteurs, 1.0))
        cl = chain_ladder(C, annee_base_reserve=1, tail_force=1.0)
        U    = np.array(cl['ultimates'], dtype=float)
        ld   = np.array(cl['last_diagonale'], dtype=float)
        expo = _exposition(_TRI_RECOURS)
        r = verifier_hypotheses_bfcc(
            pct_brut=brut, cadence_ok=ok,
            bf=bornhuetter_ferguson(C, pct, ld, U, exposition=expo,
                                    annee_base=1, cadence_ok=ok),
            cape_cod=cape_cod(C, pct, ld, exposition=expo, annee_base=1,
                              cadence_ok=ok),
            clm_h1={'statut': VALIDEE, 'valeur': 0.5, 'critere': 'c',
                    'message': 'm', 'detail': []},
            glm_apc={'success': True, 'glm_disponible': True, 'p_calendaire': 0.4},
            ultimates_cl=U, exposition=expo)
        self.assertEqual(sorted(r['hypotheses']), sorted(CODES))
        self.assertEqual(sorted(r['statuts']), sorted(CODES))
        self.assertEqual(len(r['couverture_cadence']), len(brut))
        self.assertEqual(r['statuts']['BFCC-H2'], NON_VALIDEE,
                         "le triangle à recours doit faire tomber H2")
        self.assertTrue(r['recoupement_lr']['comparable'])
        # Chaque verdict est sérialisable : les livrables le consomment tel quel.
        import json
        json.dumps(r['hypotheses'])
        print(f"    OK BFCC-35 point d'entrée : 5 verdicts "
              f"{ {c: s for c, s in r['statuts'].items()} }")

    def test_laffichage_a_une_source_unique_et_ne_ment_jamais(self):
        """Une hypothèse non évaluée ressort NON TESTABLE, jamais en défaut."""
        lignes = lignes_hypotheses_bfcc({})
        self.assertEqual([l['code'] for l in lignes], list(CODES))
        self.assertTrue(all(l['statut'] == NON_TESTABLE for l in lignes))
        self.assertTrue(all(not l['ok'] for l in lignes))
        print("    OK BFCC-33 affichage : 5 lignes, NON TESTABLE sans données")

    def test_les_livrables_portent_reellement_les_cinq_verdicts(self):
        """TROU DE COUVERTURE COMBLÉ — `export_html` avale ses échecs.

        Découvert en vérifiant les livrables : un import manquant faisait lever
        `_build_blocks`, `export_html` le rattrapait et rendait un document de
        88 octets, et LA GATE ENTIÈRE PASSAIT — 596 tests au vert avec le rapport
        HTML cassé. Le même piège que le paramètre qui masquait
        `generer_graphiques` (T20), sur un autre livrable. Ce test mesure la
        TAILLE et le CONTENU, jamais l'absence d'exception.
        """
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport \
            import export_html
        for lbl, kw in (('sans exposition', {}),
                        ('avec exposition',
                         {'primes': _exposition(GENINS)})):
            r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                generer_graphiques=False, n_sim_bootstrap=300, seed=42, **kw)
            html = export_html(r['n1'], r['n2'], r['n3'], r['n4'], {},
                               ref_client='test')
            self.assertGreater(len(html), 20_000,
                               f"{lbl} : rapport HTML de {len(html)} octets — "
                               f"`export_html` est retombé sur son repli")
            for code in CODES:
                self.assertIn(code, html, f"{lbl} : {code} absent du rapport")
            self.assertIn('lr_apriori', str(r['n3']['bf'].keys()))
            self.assertNotIn('LR_REEL=0.0', html)
            commentaire = r.get('commentaire') or ''
            self.assertIn('BFCC-H', commentaire,
                          f"{lbl} : commentaire sans les verdicts BFCC")
            print(f"    OK BFCC-38 {lbl} : HTML {len(html):,} octets, "
                  f"5 verdicts présents, commentaire {len(commentaire):,} octets")

    def test_bfcc_ne_fait_jamais_echouer_le_pipeline(self):
        """Un échec de vérification est signalé, il n'interrompt rien."""
        from unittest.mock import patch
        with patch('direction_non_vie.provisionnement.a7_provisionnement.agent'
                   '.verifier_hypotheses_bfcc', side_effect=RuntimeError('boum')):
            r = AgentA7Provisionnement(verbose=False).run(
                source=np.array(GENINS, dtype=float), mode_declare='cumule',
                primes=_exposition(GENINS), generer_graphiques=False)
        self.assertTrue(r['success'], r.get('erreur'))
        self.assertIn('boum', r['n2']['bfcc'].get('erreur', ''))
        self.assertEqual(r['n2']['bfcc']['couverture_cadence'], {})
        print("    OK BFCC-34 échec BFCC : run en succès, aucune année exclue")


if __name__ == '__main__':
    unittest.main(verbosity=1)
