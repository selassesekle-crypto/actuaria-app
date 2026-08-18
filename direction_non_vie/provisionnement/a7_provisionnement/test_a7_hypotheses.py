# =============================================================================
#  H2 NE PUBLIE PLUS DE MESURE QU'IL N'A PRISE
# =============================================================================
#
#  ⚠️ GATE : `py -m unittest discover -s direction_non_vie -t .`
#
#  ⚠️ POURQUOI CE FICHIER EXISTE, ET POURQUOI IL N'EXISTAIT PAS. Des quatre
#  modules d'hypothèses d'A7, trois ont leur fichier de test —
#  `test_a7_hypotheses_clm`, `_bfcc`, `_bootstrap`. `n2_hypotheses.py`, le
#  cadre historique qui pilote ENCORE le score, la sélection des méthodes et le
#  commentaire signé, n'en avait aucun. C'est aussi le seul des quatre où le
#  relevé B1 a trouvé des affirmations fausses publiées. La corrélation n'est
#  pas une coïncidence, c'est l'explication : corriger sans poser de filet
#  aurait reproduit la cause.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  CE QUE LE LOT FERME, ET CE QUE CHAQUE CLASSE VERROUILLE
#
#  Mesuré AVANT correction, sur un triangle 3×3 parfaitement sain, LoB
#  `credit_caution` (seuils réels 20 % / 30 %). Le commentaire signé publiait :
#
#      H2 — STABILITÉ DES FACTEURS : VALIDÉE [score 80/100]
#      Le coefficient de variation moyen [...] est de 0.0% (seuil branche :
#      15.0%), et la dérive temporelle est de 0.0% (seuil : 20.0%). Les
#      facteurs sont stables dans le temps : les années récentes se
#      développent de la même façon que les années anciennes.
#
#  Sur ZÉRO colonne testée. Quatre faussetés dans un paragraphe : un verdict,
#  deux mesures qui n'existent pas, un constat sur le portefeuille, et des
#  seuils qui sont ceux du générique et non de la branche. Trois lignes plus
#  bas, BFCC-H2 et BOOT-H2 écrivaient NON TESTABLE sur le même triangle.
#
#  ⚠️ LE VERDICT INTERNE NE BOUGE PAS — c'est `A1_Aucun_Euro_Ne_Se_Deplace` qui
#  le tient. `ok`, `score`, `cv_moy`, `derive_moy`, `ok_cv`, `ok_derive` gardent
#  EXACTEMENT les valeurs d'avant le lot, parce que N4 les lit pour composer le
#  Best Estimate. Ce lot corrige ce qui est ÉCRIT, pas ce qui est décidé — même
#  arbitrage qu'au lot A1 pour H1. Les valeurs attendues ci-dessous ont été
#  RELEVÉES sur le code d'avant : ce sont des oracles, pas des recopies.
# =============================================================================

import unittest

import numpy as np

from .n2_hypotheses import HypothesesValidator
from .n5_commentaire import _s3_hypotheses

#: ⚠️ 3×3 : colonne 0 porte 2 facteurs, colonne 1 en porte 1 — jamais les 3
#: qu'exige `_tester_h2_stabilite`. `cv_cols` reste vide. Rien de pathologique
#: dans ce triangle : il est strictement croissant.
COURT = np.array([[100.0, 150.0, 180.0],
                  [120.0, 170.0,   0.0],
                  [130.0,   0.0,   0.0]])

#: ⚠️ 4×4 : colonne 0 porte EXACTEMENT 3 facteurs — assez pour le CV, pas assez
#: pour la dérive, qui exige 4 (`mid >= 2`). C'est le seul cas où le CV est
#: mesuré et la dérive ne l'est pas, et il se produit sur un triangle ordinaire.
MOYEN = np.array([[1000.0, 1400.0, 1600.0, 1700.0],
                  [1100.0, 1560.0, 1780.0,    0.0],
                  [1200.0, 1660.0,    0.0,    0.0],
                  [1300.0,    0.0,    0.0,    0.0]])

#: 5×5 : deux colonnes testables, dérive calculée. Le cas nominal.
LONG = np.array([[1000.0, 1400.0, 1600.0, 1700.0, 1750.0],
                 [1100.0, 1550.0, 1770.0, 1880.0,    0.0],
                 [1200.0, 1680.0, 1900.0,    0.0,    0.0],
                 [1300.0, 1830.0,    0.0,    0.0,    0.0],
                 [1400.0,    0.0,    0.0,    0.0,    0.0]])

#: ⚠️ LoB DONT LES SEUILS NE SONT PAS LES GÉNÉRIQUES, ET C'EST TOUT L'INTÉRÊT.
#: `credit_caution` vaut 20 % / 30 % quand le générique vaut 15 % / 20 %. Un
#: test conduit sur `generique` n'aurait RIEN vu : les deux valeurs coïncident.
#: Dix LoB sur quinze diffèrent du générique — mesuré sur `lob_config`.
LOB = 'credit_caution'
LOB_CV, LOB_DERIVE = 0.20, 0.30

#: La phrase exacte que le rapport publiait sur zéro mesure. Elle est ici en
#: toutes lettres pour qu'une recherche plein texte la retrouve le jour où elle
#: reviendrait — un constat sur le portefeuille ne se déduit pas d'un défaut.
CONSTAT_INTERDIT = ("les années récentes se développent de la même façon que "
                    "les années anciennes")

#: `n5_excel` et `n5_rapport` tronquent le message à 200 caractères.
TRONCATURE = 200


def _h2(C, lob=LOB):
    return HypothesesValidator().valider(C, lob=lob)['h2_stabilite']


def _texte(C, lob=LOB):
    return _s3_hypotheses(HypothesesValidator().valider(C, lob=lob))


class A1_Aucun_Euro_Ne_Se_Deplace(unittest.TestCase):
    """⚠️ LE VERROU DU LOT. Si l'un de ces champs bouge, N4 recompose le Best
    Estimate autrement et le lot a dépassé son mandat."""

    def test_le_chemin_non_testable_rend_les_memes_valeurs(self):
        h = _h2(COURT)
        # Oracles relevés sur le code d'AVANT le lot.
        self.assertIs(h['ok'], True)
        self.assertEqual(h['score'], 80)
        self.assertEqual(h['cv_moy'], 0)
        self.assertEqual(h['derive_moy'], 0)
        self.assertIs(h['ok_cv'], True)
        self.assertIs(h['ok_derive'], True)
        print('    OK A1-1 le verdict interne est inchange (zero colonne)')

    def test_le_chemin_nominal_rend_les_memes_valeurs(self):
        h = _h2(LONG)
        self.assertIs(h['ok'], True)
        self.assertEqual(h['score'], 98)
        self.assertAlmostEqual(h['cv_moy'], 0.0046, places=4)
        self.assertAlmostEqual(h['derive_moy'], 0.0005, places=4)
        print('    OK A1-2 le verdict interne est inchange (nominal)')


class B1_Zero_Colonne_Testee(unittest.TestCase):
    """⚠️ « VALIDÉE [score 80/100] » SUR RIEN — le defaut central du lot."""

    def test_le_module_dit_non_testable(self):
        h = _h2(COURT)
        self.assertEqual(h['statut'], 'NON TESTABLE')
        self.assertEqual(h['n_colonnes_testees'], 0)
        self.assertIs(h['derive_calculee'], False)
        print('    OK B1-1 le module publie NON TESTABLE et son assiette')

    def test_la_narration_ne_dit_plus_validee(self):
        txt = _texte(COURT)
        self.assertIn('H2 — STABILITÉ DES FACTEURS : NON TESTABLE', txt)
        self.assertNotIn('H2 — STABILITÉ DES FACTEURS : VALIDÉE', txt)
        print('    OK B1-2 la narration ne publie plus VALIDEE sur zero test')

    def test_la_narration_n_affirme_rien_sur_le_portefeuille(self):
        # ⚠️ LA FAUSSETÉ LA PLUS GRAVE : un constat, pas un score.
        self.assertNotIn(CONSTAT_INTERDIT, _texte(COURT))
        print('    OK B1-3 le constat sur le portefeuille a disparu')

    def test_aucun_chiffre_de_stabilite_n_est_publie(self):
        # Les zéros par défaut ne doivent plus paraître comme des mesures.
        txt = _texte(COURT)
        for faux in ('est de 0.0%', 'est de 0,0%', 'dérive temporelle est de'):
            self.assertNotIn(faux, txt, f'{faux!r} est encore publie')
        print('    OK B1-4 les zeros par defaut ne sont plus affiches')

    def test_le_motif_du_module_est_cite(self):
        # Même règle qu'en H1 : on cite, on ne parse pas.
        self.assertIn(_h2(COURT)['message'], _texte(COURT))
        print('    OK B1-5 le motif du module est cite mot pour mot')


class C1_Les_Seuils_Sont_Ceux_De_La_Branche(unittest.TestCase):
    """⚠️ 15 % ET 20 % ÉTAIENT PUBLIÉS SOUS LE MOT « BRANCHE ». Ils venaient du
    repli générique : `_h2` ne publiait pas ses seuils sur ce chemin."""

    def test_le_module_publie_les_seuils_meme_sans_test(self):
        h = _h2(COURT)
        self.assertEqual(h['seuil_cv'], LOB_CV)
        self.assertEqual(h['seuil_derive'], LOB_DERIVE)
        print('    OK C1-1 les seuils de la branche sont publies (zero test)')

    def test_la_narration_publie_le_seuil_de_la_branche(self):
        txt = _texte(MOYEN)
        self.assertIn('seuil branche : 20.0%', txt)
        self.assertNotIn('seuil branche : 15.0%', txt)
        print('    OK C1-2 la narration publie 20% et non le generique 15%')


class D1_La_Derive_Non_Calculee(unittest.TestCase):
    """⚠️ UNE DÉRIVE JAMAIS CALCULÉE VALAIT 0,0 % ET SE LISAIT « AUCUNE
    DÉRIVE ». Chemin ordinaire, pas un repli."""

    def test_le_module_dit_qu_il_ne_l_a_pas_calculee(self):
        h = _h2(MOYEN)
        self.assertEqual(h['n_colonnes_testees'], 1)
        self.assertIs(h['derive_calculee'], False)
        self.assertIn('NON CALCULÉE', h['message'])
        print('    OK D1-1 le module signale la derive non calculee')

    def test_la_narration_ne_certifie_pas_la_stabilite_dans_le_temps(self):
        txt = _texte(MOYEN)
        self.assertIn("LA DÉRIVE TEMPORELLE N'A PAS ÉTÉ CALCULÉE", txt)
        self.assertNotIn(CONSTAT_INTERDIT, txt)
        print('    OK D1-2 la stabilite dans le temps n est plus affirmee')

    def test_le_cv_mesure_reste_publie(self):
        # ⚠️ NE PAS SUR-CORRIGER : le CV, lui, A été mesuré. Le taire
        # retirerait une information juste.
        self.assertIn('est de 1.2%', _texte(MOYEN))
        print('    OK D1-3 le CV reellement mesure reste publie')


class E1_Aucune_Regression_Sur_Un_Triangle_NORMAL(unittest.TestCase):
    """⚠️ UN FILET QUI DÉGRADE LE CAS NOMINAL SE FAIT DÉSACTIVER."""

    def test_le_texte_nominal_est_intact(self):
        txt = _texte(LONG)
        self.assertIn('H2 — STABILITÉ DES FACTEURS : VALIDÉE', txt)
        self.assertIn(CONSTAT_INTERDIT, txt)
        self.assertIn('dérive temporelle est de', txt)
        print('    OK E1-1 le triangle nominal publie le texte d avant')

    def test_un_dict_ancien_produit_le_texte_d_avant(self):
        # ⚠️ LE REPLI EST CALIBRÉ POUR CELA. Un dict sans `statut` ni
        # `derive_calculee` — ancienne exécution, fixture écrite à la main —
        # doit produire EXACTEMENT le texte d'avant le lot, sinon le lot
        # casserait la lecture d'un résultat archivé.
        n2 = {'h2_stabilite': {'ok': True, 'score': 80, 'cv_moy': 0.05,
                               'derive_moy': 0.03, 'seuil_cv': 0.15,
                               'seuil_derive': 0.20}}
        txt = _s3_hypotheses(n2)
        self.assertIn('H2 — STABILITÉ DES FACTEURS : VALIDÉE', txt)
        self.assertIn(CONSTAT_INTERDIT, txt)
        print('    OK E1-2 un dict ancien produit le texte d avant')


class F1_Le_Motif_Survit_A_LA_Troncature(unittest.TestCase):
    """⚠️ DEUX LIVRABLES COUPENT LE MESSAGE À 200 CARACTÈRES. Un motif coupé en
    deux publierait « les zéros publiés sont des valeurs par… » — pire que pas
    de motif, parce que la phrase qui les disqualifie disparaît."""

    def test_le_motif_non_testable_tient_entier(self):
        msg = _h2(COURT)['message']
        self.assertLessEqual(len(msg), TRONCATURE)
        self.assertEqual(msg, msg[:TRONCATURE])
        print(f'    OK F1-1 le motif NON TESTABLE tient en {len(msg)} car.')

    def test_la_derive_non_calculee_survit_a_la_coupe(self):
        # Ce message-ci dépasse 200 ; ce qui compte est que l'essentiel soit
        # AVANT la coupe.
        self.assertIn('NON CALCULÉE', _h2(MOYEN)['message'][:TRONCATURE])
        print('    OK F1-2 « NON CALCULEE » survit a la troncature')


if __name__ == '__main__':
    unittest.main(verbosity=2)
