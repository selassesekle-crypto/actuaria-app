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
 CLM-H3 vise `percentiles_mack`, BOOT-H3/H4 visent `percentiles_bootstrap`,
 MCL-H5 vise `reserve_munich` — aucune n'est une méthode du Best Estimate.
 Elles sont descriptives ICI, et CHACUNE a désormais son porteur propre
 ailleurs. C'est ce que verrouille le registre `PORTEURS_DE_CIBLE`.

 C'est exactement pour ça que brancher `couverture_volatilite` ne déplace pas
 un euro : elle traduit CLM-H3, qui porte sur l'INCERTITUDE de Mack, laquelle
 n'entre pas dans le Best Estimate. Elle est PUBLIÉE — elle était calculée et
 jetée — jamais gatante.
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

    def test_clm_h3_vise_les_percentiles_de_mack_et_non_le_modele(self):
        """⚠️ LA CIBLE A CHANGÉ AU LOT MACK, ET LA DISTINCTION EST ACTUARIELLE.

        CLM-H3 déclarait `('mack',)`, c'est-à-dire le MODÈLE. C'était imprécis
        et ça avait une conséquence mesurable : le porteur se serait aussi
        déclenché sur CLM-H2, qui vise `mack` à juste titre puisqu'elle
        invalide le modèle — et DEUX des cinq scénarios de référence auraient
        perdu leurs percentiles Mack.

        Or une hétéroscédasticité ne biaise PAS le point estimate : celui de
        Mack VAUT Chain Ladder. Elle invalide l'ERREUR DE PRÉDICTION. La cible
        exacte est donc `percentiles_mack`, parallèle de `percentiles_bootstrap`.
        """
        r = _run(GENINS)
        h3 = r['n2']['clm']['hypotheses']['CLM-H3']
        self.assertEqual(tuple(h3.get('critique_pour') or ()),
                         ('percentiles_mack',))
        h2 = r['n2']['clm']['hypotheses']['CLM-H2']
        self.assertIn('mack', tuple(h2.get('critique_pour') or ()),
                      "CLM-H2 vise bien le MODÈLE, elle")
        self.assertNotIn('percentiles_mack', tuple(h2.get('critique_pour') or ()))
        print("    OK A1-4 CLM-H3 vise `percentiles_mack` (l'incertitude), "
              "CLM-H2 vise `mack` (le modèle) — deux cibles distinctes")


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


# =============================================================================
#  T5 — LE REGISTRE DES PORTEURS : le vrai livrable du lot « Mack »
# =============================================================================

class T5_Registre_Des_Porteurs(unittest.TestCase):
    """(!) CE TEST EST LE LIVRABLE, PAS LE CORRECTIF MACK.

    Quatre fois de suite on a redécouvert par hasard une hypothèse dont la
    cible n'était portée par personne : BOOT-H3/H4, MCL-H5, puis CLM-H3. Ce
    test échoue à la CINQUIÈME, avant qu'on ne la trouve par accident.
    """

    @staticmethod
    def _cibles_declarees():
        """Toutes les valeurs de `critique_pour`, des quatre familles."""
        r = _run(GENINS)
        blocs = [r['n2'].get('clm'), r['n2'].get('bfcc'),
                 r['n2'].get('bootstrap_hyp'), r['n2'].get('munich_hyp')]
        cibles = {}
        for b in blocs:
            for code, h in ((b or {}).get('hypotheses') or {}).items():
                for cible in (h.get('critique_pour') or ()):
                    cibles.setdefault(cible, []).append(code)
        return cibles

    def test_toute_cible_declaree_a_un_porteur(self):
        cibles = self._cibles_declarees()
        self.assertTrue(cibles, "aucune cible lue — la sonde est cassée")
        orphelines = {c: h for c, h in cibles.items()
                      if c not in N4.PORTEURS_DE_CIBLE}
        self.assertEqual(
            orphelines, {},
            "Cible déclarée sans porteur : l'hypothèse se croit gatante et ne "
            "l'est pas. Soit on lui donne un porteur dans PORTEURS_DE_CIBLE, "
            "soit elle déclare critique_pour=() et s'assume descriptive. "
            + str(orphelines))
        print(f"    OK MACK-1 {len(cibles)} cibles déclarées, toutes portées : "
              f"{sorted(cibles)}")

    def test_le_registre_ne_porte_pas_de_cible_fantome(self):
        """Un porteur pour une cible que personne ne déclare est du code mort."""
        cibles = set(self._cibles_declarees())
        fantomes = set(N4.PORTEURS_DE_CIBLE) - cibles
        self.assertEqual(fantomes, set(),
                         f"porteur sans cible déclarée : {fantomes}")
        print("    OK MACK-2 aucun porteur orphelin — le registre ne diverge "
              "pas des hypothèses")

    def test_les_cibles_du_be_sont_exactement_cles_n3(self):
        dans_be = {c for c in N4.PORTEURS_DE_CIBLE if c in N4._CLES_N3}
        self.assertEqual(dans_be, set(N4._CLES_N3))
        print(f"    OK MACK-3 les cibles du BE sont exactement _CLES_N3 : "
              f"{sorted(dans_be)}")


# =============================================================================
#  T6 — LA CONSÉQUENCE SUR MACK, PROUVÉE SUR UN TRIANGLE CONSTRUIT
# =============================================================================

def _triangle_hetero(n=12, sd=0.30, k=1.0, graine=0, reprises_col=None,
                     reprises_pct=0.03):
    """Triangle dont la variance suit C^3 au lieu de C — Mack suppose C.

    Les cinq scénarios de référence VALIDENT tous CLM-H3 : sans ce triangle
    construit, le mécanisme serait livré sans preuve. Le bruit est
    MULTIPLICATIF et son amplitude croît avec le volume, si bien que
    |résidu|/racine(C) croît en C^(0.5+k) — exactement ce que CLM-H3 cherche.
    `reprises_col` casse EN PLUS le Bootstrap, pour exercer la seconde branche.
    """
    f = [2.2, 1.5, 1.25, 1.14, 1.08, 1.05] + [1.03] * (n - 7)
    vols = np.linspace(100_000, 100_000 * 200, n)
    rng = np.random.default_rng(graine)
    C = np.full((n, n), np.nan)
    C[:, 0] = vols
    vmax = float(np.max(vols))
    for j in range(n - 1):
        for i in range(n - j - 1):
            ech = (C[i, 0] / vmax) ** k
            C[i, j + 1] = C[i, j] * f[j] * (1 + rng.normal(0, sd * ech))
    if reprises_col is not None:
        for i in range(n):
            for j in range(reprises_col, n - i):
                if not np.isnan(C[i, j]):
                    C[i, j] = C[i, j - 1] * (1 - reprises_pct)
    return C


class T6_Consequence_Sur_Mack(unittest.TestCase):

    def test_clm_h3_validee_ne_retire_rien(self):
        """Le témoin : sur GenIns, tout reste publié."""
        r = _run(GENINS)
        self.assertEqual(r['n2']['clm']['hypotheses']['CLM-H3']['statut'],
                         'VALIDÉE')
        self.assertTrue(r['n2']['clm']['percentiles_mack_publiables'])
        for cle in ('reserve_p75_mack', 'reserve_p90_mack',
                    'reserve_p99_5_mack'):
            self.assertIsNotNone(r['n4'][cle])
        self.assertEqual(r['n4']['source_percentiles'],
                         'Incertitude composée (\u03c3_Mack + \u03c3_mod\xe8le)')
        print("    OK MACK-4 témoin GenIns : CLM-H3 validée, colonne Mack "
              "publiée, source inchangée")

    def test_branche_1_bascule_sur_le_bootstrap(self):
        """CLM-H3 tombe, le Bootstrap est publiable : il prend le relais."""
        r = _run(_triangle_hetero())
        self.assertEqual(r['n2']['clm']['hypotheses']['CLM-H3']['statut'],
                         'NON VALIDÉE')
        self.assertFalse(r['n2']['clm']['percentiles_mack_publiables'])
        self.assertTrue(r['n2']['bootstrap_hyp']['percentiles_publiables'])
        for cle in ('reserve_p75_mack', 'reserve_p90_mack',
                    'reserve_p99_5_mack'):
            self.assertIsNone(r['n4'][cle], f'{cle} devrait être retirée')
        self.assertIn('Bootstrap ODP', r['n4']['source_percentiles'])
        self.assertAlmostEqual(float(r['n4']['reserve_p90']),
                               float(r['n3']['bootstrap']['p90']), delta=1.0)
        print(f"    OK MACK-5 branche 1 : colonne Mack retirée, P90 basculé "
              f"sur le Bootstrap ({r['n4']['reserve_p90']:,.0f}), source "
              f"explicite")

    def test_branche_2_aucun_relais_mais_jamais_de_vide(self):
        """CLM-H3 tombe ET le Bootstrap n'est pas publiable.

        Le composite est CONSERVÉ — le retirer laisserait le rapport sans
        aucune mesure d'incertitude — mais sa provenance est étiquetée
        CONTESTÉE.
        """
        r = _run(_triangle_hetero(reprises_col=6, reprises_pct=0.03))
        self.assertEqual(r['n2']['clm']['hypotheses']['CLM-H3']['statut'],
                         'NON VALIDÉE')
        self.assertFalse(r['n2']['bootstrap_hyp']['percentiles_publiables'])
        self.assertIsNone(r['n4']['reserve_p90_mack'])
        self.assertIsNotNone(r['n4']['reserve_p90'])
        self.assertGreater(float(r['n4']['reserve_p90']), 0.0)
        self.assertIn('CONTESTÉE', r['n4']['source_percentiles'])
        print(f"    OK MACK-6 branche 2 : pas de relais, composite CONSERVÉ "
              f"(P90 = {r['n4']['reserve_p90']:,.0f}), provenance étiquetée "
              f"CONTESTÉE")

    def test_la_reserve_centrale_ne_bouge_dans_aucune_branche(self):
        """Tout ceci ne touche QUE l'incertitude, jamais la réserve centrale."""
        for lbl, tri in (('branche 1', _triangle_hetero()),
                         ('branche 2', _triangle_hetero(reprises_col=6))):
            n4 = _run(tri)['n4']
            for cle in ('best_estimate', 'risk_margin', 'scr_prov',
                        'provisions_techniques_s2'):
                self.assertIsNotNone(n4[cle], f'{lbl}.{cle}')
                self.assertNotEqual(float(n4[cle]), 0.0, f'{lbl}.{cle}')
        print("    OK MACK-7 BE, Risk Margin, SCR et provisions techniques "
              "intacts dans les deux branches")


if __name__ == '__main__':
    unittest.main(verbosity=2)
