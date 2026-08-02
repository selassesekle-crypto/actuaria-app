# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — écrêter AVANT de juger : filet du lot F1
=============================================================================

 UN SEUL DÉFAUT, TROIS FOIS. Une grandeur est ramenée dans une plage, puis
 c'est la valeur RAMENÉE qui est publiée, jugée, et parfois portée au Best
 Estimate. Le garde-fou efface la trace de ce contre quoi il gardait.

 Le cas le plus net est celui de Cape Cod, parce que la plage d'écrêtage y
 est EXACTEMENT la plage de plausibilité :

     lr = clip(num / den, 0.10, 3.00)     puis     0.10 ≤ lr ≤ 3.00 ?

 La seconde ligne est une tautologie. Mesuré sur GenIns, exposition ×60 :
 loss ratio réel 2,94 %, publié 10,0 %, réserve portée de 17,5 M€ à 59,4 M€,
 et Cape Cod au Best Estimate à poids plein. L'écrêtage ne corrigeait pas
 l'aberration : il la FABRIQUAIT.

 Bornhuetter-Ferguson avait la même structure, en moins visible : le loss
 ratio manuel était borné à la plage DURE, celle dont le dépassement vaut
 « non validée ». Un a priori de 5 000 % arrivait donc à 500 %, et le verdict
 « non validée » était structurellement inatteignable.

 Le tail factor, lui, ne déplaçait aucun euro — son statut était déjà calculé
 après écrêtage — mais publiait 1,500000 aussi bien pour une queue extrapolée
 à 1,64 que pour une queue à 117,79.

 CE FILET VERROUILLE LES DEUX PROPRIÉTÉS QUI COMPTENT :
   · la valeur BRUTE est publiée, à côté de celle qui sert au calcul ;
   · c'est la BRUTE qui est jugée — un test qui ne vérifierait que la
     présence de la clé laisserait revenir le défaut par la porte du
     jugement.
=============================================================================
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement import (
    n2_hypotheses_bfcc as H)
from direction_non_vie.provisionnement.a7_provisionnement import (
    n4_best_estimate as N4)
from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.n3.bf_cape_cod import (
    LR_CC_PLAGE_ALERTE, LR_PLAGE_ALERTE, LR_PLAGE_DURE, libelle_loss_ratio)
from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import (
    calculer_tail_factor, calculer_tail_factor_multi)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA)

_C = np.asarray(GENINS, dtype=float)
_BASE = float(np.mean(_C[:, 0])) * 8.0

#: Deux queues très différentes qui ressortaient au même chiffre écrêté.
_QUEUE_LOURDE = np.array([3.0, 2.2, 1.8, 1.5, 1.35, 1.25])
_QUEUE_ENORME = np.array([9.0, 7.0, 5.5, 4.4, 3.6, 3.0])


def _run(**kwargs):
    """Un run d'A7 sur GenIns, exposition par défaut, livrables coupés."""
    kwargs.setdefault('primes', np.full(_C.shape[0], _BASE))
    return AgentA7Provisionnement(verbose=False).run(
        source=_C, mode_declare='cumule', generer_graphiques=False,
        generer_word=False, generer_pdf_flag=False, n_sim_bootstrap=60,
        seed=42, **kwargs)


# =============================================================================
#  1. LE VERROU STRUCTUREL — ÉCRÊTER DANS LA PLAGE QUI JUGE EST UNE TAUTOLOGIE
# =============================================================================

class T1_Verrou_Structurel(unittest.TestCase):
    """Pourquoi juger la valeur écrêtée ne pouvait pas marcher."""

    def test_la_plage_de_cape_cod_est_sa_propre_plage_de_jugement(self):
        """Écrêtage et critère de BFCC-H6 sont le MÊME intervalle."""
        bas, haut = LR_CC_PLAGE_ALERTE
        for brut in (0.0001, 0.02941, 3.5, 35.29, 1e6):
            ecrete = float(np.clip(brut, bas, haut))
            self.assertTrue(
                bas <= ecrete <= haut,
                "l'écrêté est TOUJOURS dans la plage, par construction")
        print(f"    OK F1-1 Cape Cod : écrêtage [{bas:.0%}–{haut:.0%}] == "
              f"critère BFCC-H6 → juger l'écrêté est une tautologie")

    def test_les_bornes_dures_de_bf_sont_dans_la_plage_qui_valide(self):
        """Écrêter à la plage dure rendait « non validée » inatteignable."""
        bas_d, haut_d = LR_PLAGE_DURE
        for brut in (0.0001, 9.0, 50.0, 1e6):
            ecrete = float(np.clip(brut, bas_d, haut_d))
            self.assertTrue(bas_d <= ecrete <= haut_d)
        self.assertLess(bas_d, LR_PLAGE_ALERTE[0])
        self.assertGreater(haut_d, LR_PLAGE_ALERTE[1])
        print(f"    OK F1-2 BF : écrêtage [{bas_d:.0%}–{haut_d:.0%}] == plage "
              f"dont le dépassement vaut « non validée » → inatteignable")


# =============================================================================
#  2. LA VALEUR BRUTE EST PUBLIÉE
# =============================================================================

class T2_Valeur_Brute_Publiee(unittest.TestCase):

    def test_bf_publie_le_loss_ratio_manuel_tel_qu_il_a_ete_saisi(self):
        bf = _run(lr_bf_manuel=50.0)['n3']['bf']
        self.assertAlmostEqual(bf['lr_apriori_brut'], 50.0, places=6)
        self.assertAlmostEqual(bf['lr_apriori'], LR_PLAGE_DURE[1], places=6)
        self.assertTrue(bf['lr_ecrete'])
        print(f"    OK F1-3 BF : saisi {bf['lr_apriori_brut']:.0%} publié tel "
              f"quel, {bf['lr_apriori']:.0%} pour le seul calcul")

    def test_bf_non_ecrete_publie_les_deux_fois_la_meme_valeur(self):
        bf = _run(lr_bf_manuel=0.75)['n3']['bf']
        self.assertFalse(bf['lr_ecrete'])
        self.assertAlmostEqual(bf['lr_apriori_brut'], 0.75, places=6)
        print("    OK F1-4 BF : un a priori dans la plage n'est pas signalé "
              "comme écrêté")

    def test_cape_cod_publie_le_loss_ratio_reellement_observe(self):
        cc = _run(primes=np.full(_C.shape[0], _BASE * 60))['n3']['cape_cod']
        self.assertLess(cc['lr_cape_cod_brut'], LR_CC_PLAGE_ALERTE[0])
        self.assertAlmostEqual(cc['lr_cape_cod'], LR_CC_PLAGE_ALERTE[0],
                               places=4)
        self.assertTrue(cc['lr_ecrete'])
        print(f"    OK F1-5 Cape Cod : LR réel {cc['lr_cape_cod_brut']:.2%} "
              f"publié, {cc['lr_cape_cod']:.0%} pour le seul calcul")

    def test_le_tail_factor_publie_la_queue_reellement_extrapolee(self):
        a = calculer_tail_factor(_QUEUE_LOURDE, lob_tail_max_alerte=1.05)
        b = calculer_tail_factor(_QUEUE_ENORME, lob_tail_max_alerte=1.05)
        self.assertAlmostEqual(a['tail_factor'], b['tail_factor'], places=6)
        self.assertGreater(b['tail_brut'], a['tail_brut'] * 10)
        self.assertTrue(a['tail_ecrete'] and b['tail_ecrete'])
        print(f"    OK F1-6 tail : deux queues au même {a['tail_factor']:.4f} "
              f"publié, brut {a['tail_brut']:.2f} contre {b['tail_brut']:.2f}")

    def test_les_deux_chemins_du_tail_factor_publient_les_memes_cles(self):
        """`calculer_tail_factor` sert en production, `_multi` aux tests."""
        cles = {'tail_brut', 'tail_ecrete', 'tail_max'}
        simple = calculer_tail_factor(_QUEUE_ENORME, lob_tail_max_alerte=1.05)
        multi = calculer_tail_factor_multi(_QUEUE_ENORME,
                                           lob_tail_max_alerte=1.05)
        self.assertTrue(cles <= set(simple), "chemin de production")
        self.assertTrue(cles <= set(multi), "chemin multi-méthodes")
        print("    OK F1-7 tail : les deux chemins publient tail_brut / "
              "tail_ecrete / tail_max, ils ne peuvent plus diverger")


# =============================================================================
#  3. C'EST LA BRUTE QUI EST JUGÉE — ET LE JUGEMENT GATE
# =============================================================================

class T3_La_Brute_Est_Jugee(unittest.TestCase):

    def test_bfcc_h4_lit_la_valeur_brute_et_non_celle_du_calcul(self):
        """Un bloc fabriqué où les deux valeurs diffèrent tranche la question."""
        bloc = {'disponible': True, 'source_lr': 'manuel',
                'lr_apriori': 5.0, 'lr_apriori_brut': 50.0,
                'lr_ecrete': True, 'detail_lr': {'cv': 0.0}}
        r = H.bfcc_h4_apriori(bloc, LR_PLAGE_ALERTE, LR_PLAGE_DURE,
                              0.25, 0.20, None, '')
        self.assertAlmostEqual(r.valeur, 50.0, places=6)
        self.assertEqual(r.statut, H.NON_VALIDEE)
        print(f"    OK F1-8 BFCC-H4 juge {r.valeur:.0%} (brut) et non "
              f"{bloc['lr_apriori']:.0%} (calcul) → {r.statut}")

    def test_bfcc_h6_lit_la_valeur_brute_et_non_celle_du_calcul(self):
        bloc = {'disponible': True, 'lr_cape_cod': LR_CC_PLAGE_ALERTE[0],
                'lr_cape_cod_brut': 0.02941, 'lr_ecrete': True}
        r = H.bfcc_h6_plage_lr_poole(bloc, LR_CC_PLAGE_ALERTE)
        self.assertAlmostEqual(r.valeur, 0.02941, places=6)
        self.assertEqual(r.statut, H.NON_VALIDEE)
        print(f"    OK F1-9 BFCC-H6 juge {r.valeur:.2%} (brut) et non "
              f"{bloc['lr_cape_cod']:.0%} (calcul) → {r.statut}")

    def test_bfcc_h6_est_binaire_et_critique_pour_cape_cod(self):
        """Une appartenance à un intervalle ne se « justifie » pas."""
        dedans = H.bfcc_h6_plage_lr_poole(
            {'disponible': True, 'lr_cape_cod': 1.2,
             'lr_cape_cod_brut': 1.2, 'lr_ecrete': False},
            LR_CC_PLAGE_ALERTE)
        self.assertEqual(dedans.statut, H.VALIDEE)
        self.assertEqual(dedans.critique_pour, (H.CC,))
        for lr in (0.001, 0.05, 0.099, 3.01, 12.0, 400.0):
            r = H.bfcc_h6_plage_lr_poole(
                {'disponible': True, 'lr_cape_cod': 1.0,
                 'lr_cape_cod_brut': lr, 'lr_ecrete': True},
                LR_CC_PLAGE_ALERTE)
            self.assertIn(r.statut, (H.VALIDEE, H.NON_VALIDEE),
                          "BFCC-H6 n'a pas d'« à justifier »")
        self.assertIn('BFCC-H6', H.CODES)
        self.assertIn('BFCC-H6', H.LIBELLES)
        print("    OK F1-10 BFCC-H6 : verdict binaire, critique pour Cape Cod, "
              "présente dans CODES et LIBELLES")

    def test_bfcc_h6_est_gatante_pour_cape_cod(self):
        self.assertIn('BFCC-H6', N4._HYPOTHESES_BLOQUANTES['cape_cod'])
        self.assertIn('BFCC-H5', N4._HYPOTHESES_BLOQUANTES['cape_cod'])
        print("    OK F1-11 BFCC-H6 rejoint BFCC-H5 dans les hypothèses "
              "bloquantes de Cape Cod (niveau et dérive, deux tests)")

    def test_une_exposition_aberrante_ecarte_cape_cod_du_best_estimate(self):
        for mult in (0.05, 60.0):
            r = _run(primes=np.full(_C.shape[0], _BASE * mult))
            self.assertEqual(r['n2']['bfcc']['statuts']['BFCC-H6'],
                             H.NON_VALIDEE, f"exposition ×{mult}")
            self.assertIn('cape_cod', r['n4']['methodes_exclues'])
            self.assertNotIn('cape_cod', r['n4']['methodes_incluses'])
        print("    OK F1-12 exposition ×0,05 et ×60 : Cape Cod écartée du BE "
              "au lieu d'y entrer avec une réserve bâtie sur une borne")

    def test_un_apriori_aberrant_ecarte_bf_du_best_estimate(self):
        r = _run(lr_bf_manuel=50.0)
        self.assertEqual(r['n2']['bfcc']['statuts']['BFCC-H4'], H.NON_VALIDEE)
        self.assertIn('bornhuetter_ferguson', r['n4']['methodes_exclues'])
        print("    OK F1-13 a priori 5 000 % : BF écartée du BE — avant F1 le "
              "verdict portait sur 500 % et valait « à justifier »")


# =============================================================================
#  4. CE QUE L'ACTUAIRE LIT
# =============================================================================

class T4_Affichage(unittest.TestCase):
    """`libelle_loss_ratio` est la source UNIQUE des trois formats."""

    def test_une_valeur_ecretee_affiche_les_deux_nombres(self):
        cc = _run(primes=np.full(_C.shape[0], _BASE * 60))['n3']['cape_cod']
        texte = libelle_loss_ratio(cc, 'lr_cape_cod')
        self.assertIn('écrêté', texte)
        self.assertIn(f"{cc['lr_cape_cod_brut']:.1%}", texte)
        self.assertIn(f"{cc['lr_cape_cod']:.1%}", texte)
        print(f"    OK F1-14 affichage écrêté : « {texte} »")

    def test_une_valeur_intacte_affiche_un_seul_nombre(self):
        """⚠️ Le piège : brut et calcul sont arrondis à 6 et 4 décimales.

        Les comparer annonçait « 169,4 % (écrêté à 169,3 %) » sur un cas où
        RIEN n'avait été écrêté. Le drapeau `lr_ecrete` fait foi.
        """
        r = _run()
        for bloc, cle in ((r['n3']['bf'], 'lr_apriori'),
                          (r['n3']['cape_cod'], 'lr_cape_cod')):
            texte = libelle_loss_ratio(bloc, cle)
            self.assertNotIn('écrêté', texte)
            self.assertNotIn('(', texte)
        print("    OK F1-15 affichage intact : un seul nombre, jamais de "
              "mention d'écrêtage due à un écart d'arrondi")

    def test_une_methode_ecartee_reste_visible_avec_sa_valeur(self):
        r = _run(primes=np.full(_C.shape[0], _BASE * 60))
        self.assertIn('cape_cod', r['n4']['methodes_exclues'])
        self.assertGreater(r['n3']['cape_cod']['reserve_totale'], 0.0)
        message = r['n2']['bfcc']['objets']['BFCC-H6'].message
        self.assertIn('exposition', message)
        print("    OK F1-16 une méthode écartée garde sa réserve publiée et "
              "un message qui nomme la cause (l'exposition)")

    def test_bfcc_h6_apparait_dans_les_cellules_de_l_excel(self):
        """⚠️ La CELLULE est relue, pas les octets — leçon des lots Munich
        et Benktander, où sonder le XML n'avait pas vu le caractère cherché.

        BFCC-H6 n'est câblée nulle part dans les livrables : la boucle est
        générique sur `CODES`. Ce test vérifie que l'ajout d'une hypothèse
        suffit, et que la valeur montrée est bien la BRUTE.
        """
        import io as _io
        import openpyxl

        r = AgentA7Provisionnement(verbose=False).run(
            source=_C, mode_declare='cumule',
            primes=np.full(_C.shape[0], _BASE * 60), lob='generique',
            n_sim_bootstrap=100, generer_word=False, generer_pdf_flag=False,
            generer_graphiques=False)
        octets = r.get('excel_bytes', b'')
        if not octets:
            self.skipTest("openpyxl absent — pas d'Excel à relire")
        wb = openpyxl.load_workbook(_io.BytesIO(octets))
        cellules = [str(c.value) for ws in wb.worksheets
                    for row in ws.iter_rows() for c in row
                    if c.value and 'BFCC-H6' in str(c.value)]
        self.assertGreaterEqual(len(cellules), 2,
                                "BFCC-H6 doit paraître en synthèse ET dans "
                                "la feuille des hypothèses")
        brut = r['n3']['cape_cod']['lr_cape_cod_brut']
        self.assertTrue(any(f"{brut:.1%}" in c for c in cellules),
                        "l'Excel doit montrer le loss ratio RÉEL, pas la borne")
        print(f"    OK F1-17 Excel : BFCC-H6 dans {len(cellules)} cellules, "
              f"avec le loss ratio réel {brut:.1%} et non la borne")


# =============================================================================
#  5. NON-RÉGRESSION — AUCUN CAS SAIN NE BOUGE
# =============================================================================

class T5_Non_Regression(unittest.TestCase):

    def test_les_scenarios_sains_ne_bougent_pas(self):
        """F1 ne change RIEN quand aucune valeur n'est écrêtée."""
        for nom, tri, be_attendu in (('GenIns', _C, 17_571_609.0),
                                     ('RAA', np.asarray(RAA, float), 55_535.0)):
            src = np.asarray(tri, float)
            r = AgentA7Provisionnement(verbose=False).run(
                source=src, mode_declare='cumule',
                primes=np.full(src.shape[0],
                               float(np.nanmean(src[:, 0])) * 8.0),
                generer_graphiques=False, generer_word=False,
                generer_pdf_flag=False, n_sim_bootstrap=60, seed=42)
            self.assertAlmostEqual(r['n4']['best_estimate'], be_attendu,
                                   delta=1.0, msg=nom)
            self.assertEqual(r['n2']['bfcc']['statuts']['BFCC-H6'], H.VALIDEE)
            self.assertFalse(r['n3']['cape_cod']['lr_ecrete'])
        print("    OK F1-18 GenIns 17 571 609 € et RAA 55 535 € inchangés, "
              "BFCC-H6 validée, aucun écrêtage")

    def test_le_tail_retenu_est_inchange_par_le_lot(self):
        """Publier la brute ne déplace pas un euro : le retenu reste l'écrêté."""
        for queue in (_QUEUE_LOURDE, _QUEUE_ENORME):
            r = calculer_tail_factor(queue, lob_tail_max_alerte=1.05)
            attendu = min(1.05 * 1.5, 1.50)
            self.assertAlmostEqual(r['tail_factor'], attendu, places=6)
            self.assertAlmostEqual(r['tail_max'], attendu, places=6)
            self.assertEqual(r['statut'], 'ROUGE')
        print("    OK F1-19 tail : le facteur retenu et le statut sont ceux "
              "d'avant F1 — la correction est de transparence, pas de calcul")


if __name__ == '__main__':
    unittest.main(verbosity=2)
