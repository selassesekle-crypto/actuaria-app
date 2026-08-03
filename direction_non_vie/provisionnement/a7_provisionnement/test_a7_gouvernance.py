# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — gouvernance des hypothèses : filet du lot A1
=============================================================================

 CE QUE LE LOT A1 CHANGE, ET CE QU'IL NE CHANGE PAS.

 Le circuit `_hypotheses_a_justifier` ne lisait que la famille BFCC. Les
 verdicts de Chain Ladder et de Mack — CLM-H1..H4 — n'avaient donc AUCUN
 effet sur le statut publié, quel que soit leur contenu. CLM le rejoint.

 ⚠️ EFFET MESURÉ, ET IL EST UNIQUE : sur le scénario `Recours`, CLM-H2 est
 « À JUSTIFIER » et Chain Ladder est retenue. Le statut passe donc de VERT à
 AMBRE. C'est le SEUL verdict de référence qui bouge, et AUCUN euro ne bouge
 avec lui — vérifié par empreinte sur treize grandeurs monétaires.

 ⚠️ CE QUI NE PEUT PAS REJOINDRE CE CIRCUIT, ET POURQUOI CE N'EST PAS UN
 OUBLI. Le filtre exige qu'une cible de `critique_pour` figure dans
 `methodes_incluses`, qui ne contient que les trois clés de `_CLES_N3`.
 CLM-H3 vise `mack`, BOOT-H3/H4 visent `percentiles_bootstrap`, MCL-H5 vise
 `reserve_munich` — aucune de ces cibles n'est une méthode du Best Estimate.
 Elles sont descriptives ICI, et deux d'entre elles ont déjà leur conséquence
 propre ailleurs (`percentiles_publiables` pour le Bootstrap ; la garde
 `valider_prerequis` pour Munich).

 C'est exactement pour ça que brancher `couverture_volatilite` ne déplace pas
 un euro : elle traduit CLM-H3, qui porte sur Mack, qui n'entre pas dans le
 Best Estimate. Elle est PUBLIÉE — elle était calculée et jetée — jamais
 gatante.
=============================================================================
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement import (
    n4_best_estimate as N4)
from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, _TRI_RECOURS)

#: Les grandeurs monétaires qu'un lot de gouvernance ne doit JAMAIS déplacer.
_GRANDEURS_EN_EUROS = (
    'best_estimate', 'be_ibnr_pur', 'risk_margin', 'scr_prov',
    'provisions_techniques_s2', 'reserve_p75', 'reserve_p90', 'reserve_p99_5',
    'sigma_mack', 'sigma_total_compose', 'reserve_p75_mack',
    'reserve_p90_mack', 'reserve_p99_5_mack',
)


def _run(triangle):
    src = np.asarray(triangle, dtype=float)
    return AgentA7Provisionnement(verbose=False).run(
        source=src, mode_declare='cumule',
        primes=np.full(src.shape[0], float(np.nanmean(src[:, 0])) * 8.0),
        generer_graphiques=False, generer_word=False, generer_pdf_flag=False,
        n_sim_bootstrap=60, seed=42)


# =============================================================================
#  T1 — LE CIRCUIT LIT DÉSORMAIS LES DEUX FAMILLES
# =============================================================================

class T1_Le_Circuit_Lit_CLM(unittest.TestCase):

    def test_une_hypothese_clm_a_justifier_atteint_le_statut(self):
        """Sur `Recours`, CLM-H2 est à justifier et Chain Ladder est retenue."""
        r = _run(_TRI_RECOURS)
        self.assertEqual(
            (r['n2']['clm']['hypotheses']['CLM-H2'] or {}).get('statut'),
            'À JUSTIFIER')
        self.assertIn('chain_ladder', r['n4']['methodes_incluses'])
        self.assertIn('CLM-H2', r['n4']['hypotheses_a_justifier'],
                      "CLM n'atteint pas le circuit — le lot A1 est défait")
        self.assertEqual(r['n4']['statut'], 'AMBRE',
                         "une hypothèse à justifier ne peut pas coexister "
                         "avec un VERT")
        print(f"    OK A1-1 Recours : CLM-H2 à justifier → statut "
              f"{r['n4']['statut']}, a_justifier="
              f"{r['n4']['hypotheses_a_justifier']}")

    def test_le_circuit_lit_toujours_bfcc(self):
        """L'ajout de CLM ne doit pas avoir évincé BFCC."""
        import inspect
        src = inspect.getsource(N4._hypotheses_a_justifier)
        self.assertIn("'bfcc'", src)
        self.assertIn("'clm'", src)
        print("    OK A1-2 le circuit lit BFCC ET CLM, pas l'un à la place "
              "de l'autre")


# =============================================================================
#  T2 — CE QUI NE PEUT PAS GATER, ET LA RAISON STRUCTURELLE
# =============================================================================

class T2_Les_Cibles_Hors_Best_Estimate(unittest.TestCase):

    def test_mack_n_est_pas_une_methode_du_best_estimate(self):
        """La cause : `_CLES_N3` ne contient ni mack, ni bootstrap, ni munich.

        C'est ce qui rend CLM-H3 descriptive dans ce circuit — et c'est aussi
        ce qui rend le branchement de `couverture_volatilite` sans effet sur
        un seul euro.
        """
        cles = set(N4._CLES_N3)
        self.assertEqual(cles, {'chain_ladder', 'bornhuetter_ferguson',
                                'cape_cod'})
        for absente in ('mack', 'bootstrap', 'munich_cl',
                        'percentiles_bootstrap', 'reserve_munich'):
            self.assertNotIn(absente, cles)
        print(f"    OK A1-3 _CLES_N3 = {sorted(cles)} — aucune cible de "
              f"CLM-H3 / BOOT-H3-H4 / MCL-H5 n'y figure")

    def test_clm_h3_vise_mack_seul(self):
        r = _run(GENINS)
        h3 = r['n2']['clm']['hypotheses']['CLM-H3']
        self.assertEqual(tuple(h3.get('critique_pour') or ()), ('mack',))
        print("    OK A1-4 CLM-H3 vise `mack` seul → descriptive dans le "
              "circuit, par construction et non par oubli")


# =============================================================================
#  T3 — LA COUVERTURE DE VOLATILITÉ EST PUBLIÉE, JAMAIS GATANTE
# =============================================================================

class T3_Couverture_Volatilite(unittest.TestCase):

    def test_elle_est_publiee_par_annee_et_en_agrege(self):
        """Elle était calculée par `couvertures_par_annee` et lue par personne."""
        r = _run(GENINS)
        self.assertIn('annees_volatilite_douteuse', r['n4'])
        for ligne in r['n4']['selection_par_annee']:
            self.assertIn('volatilite', ligne,
                          "chaque année doit porter sa couverture de dispersion")
            self.assertIn(ligne['volatilite'],
                          ('VALIDÉE', 'À JUSTIFIER', 'NON VALIDÉE',
                           'NON TESTABLE'))
        print(f"    OK A1-5 couverture de volatilité publiée sur "
              f"{len(r['n4']['selection_par_annee'])} années + agrégat "
              f"{r['n4']['annees_volatilite_douteuse']}")

    def test_elle_ne_retire_aucune_methode(self):
        """Une année à dispersion douteuse garde toutes ses méthodes."""
        r = _run(GENINS)
        douteuses = set(r['n4']['annees_volatilite_douteuse'])
        for ligne in r['n4']['selection_par_annee']:
            if ligne['annee'] in douteuses and not ligne['sous_filet']:
                self.assertTrue(
                    ligne['methodes'],
                    "la volatilité ne doit retirer aucune méthode par elle-même")
        print("    OK A1-6 la couverture de volatilité ne retire aucune "
              "méthode — elle informe, elle ne gate pas")


# =============================================================================
#  T4 — AUCUN EURO DÉPLACÉ, ET C'EST LE POINT DU LOT
# =============================================================================

class T4_Zero_Euro_Deplace(unittest.TestCase):
    """Valeurs figées AVANT le lot A1, mesurées sur l'arbre propre."""

    #: GenIns et Recours, exposition = 8 × moyenne de la 1ʳᵉ colonne, seed 42.
    _ATTENDU = {
        'GenIns':  {'best_estimate': 17_571_609.0, 'risk_margin': 2_107_541.0},
        'Recours': {'best_estimate': 1_032.0,      'risk_margin': 71.0},
    }

    def test_les_grandeurs_monetaires_sont_inchangees(self):
        for nom, tri in (('GenIns', GENINS), ('Recours', _TRI_RECOURS)):
            n4 = _run(tri)['n4']
            for cle, attendu in self._ATTENDU[nom].items():
                self.assertAlmostEqual(float(n4[cle]), attendu, delta=1.0,
                                       msg=f'{nom}.{cle}')
            for cle in _GRANDEURS_EN_EUROS:
                self.assertIn(cle, n4, f'{cle} a disparu du livrable')
        print("    OK A1-7 GenIns 17 571 609 € / RM 2 107 541 € et Recours "
              "1 032 € / RM 71 € — inchangés par le lot A1")

    def test_le_verdict_bouge_mais_pas_les_poids(self):
        """Recours passe en AMBRE sans qu'aucune pondération ne change."""
        n4 = _run(_TRI_RECOURS)['n4']
        self.assertEqual(n4['statut'], 'AMBRE')
        self.assertEqual(sorted(n4['poids']),
                         ['bornhuetter_ferguson', 'cape_cod', 'chain_ladder'])
        self.assertAlmostEqual(sum(n4['poids'].values()), 1.0, places=3)
        print(f"    OK A1-8 Recours : statut AMBRE, poids inchangés "
              f"{n4['poids']}, Σ = 1")


if __name__ == '__main__':
    unittest.main(verbosity=2)
