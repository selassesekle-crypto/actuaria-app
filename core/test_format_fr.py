# -*- coding: utf-8 -*-
"""Tests T3 — la convention française des nombres, et sa fidélité à A7.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_frontiere_llm.py.
"""
import unittest

from core.format_fr import (
    ABSENT, DEC_EFFECTIF, DEC_GINI, DEC_POURCENT, DEC_RATIO, SEP_MILLIERS,
    euros, nombre, pourcent)


class T1_LaFideliteAA7(unittest.TestCase):
    """T1 — le verrou qui empêche une SEIZIÈME convention.

    ⚠️ Le dépôt porte quinze fichiers définissant chacun leur `_f`. Ce module
    ne doit pas en ajouter un de plus : il TRANSPOSE celui d'A7.
    """

    def test_la_transposition_est_identique_a_A7(self):
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport \
            import _f as a7_f, _pct as a7_pct
        for v in (18680856, 2435, 0, -1200, 7):
            self.assertEqual(euros(v, 0), a7_f(v, 0), f'euros({v})')
        for v, d in ((1234.5678, 2), (0.1775, 4), (1.0, 3)):
            self.assertEqual(nombre(v, d), a7_f(v, d), f'nombre({v},{d})')
        for v in (0.6, 208.53):
            self.assertEqual(pourcent(v, 1), a7_pct(v, 1), f'pourcent({v})')
        print('    OK T1 : transposition identique à A7 sur 10 cas')

    def test_le_cas_que_A7_ne_couvre_PAS(self):
        """⚠️ `_f(v, 0)` d'A7 suffixe « € ». Appliqué à « 7 modèles
        comparés », il donnerait « 7 € »."""
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport \
            import _f as a7_f
        self.assertIn('€', a7_f(7, 0))
        self.assertEqual(nombre(7), '7')
        self.assertNotIn('€', nombre(7))
        print('    OK T1b : `nombre` couvre le cas sans unité qu\'A7 n\'a pas')


class T2_LaConvention(unittest.TestCase):
    """T2 — espace fine INSÉCABLE, et l'unité attachée à son nombre."""

    def test_le_separateur_de_milliers_est_insecable(self):
        """⚠️ UNE ESPACE ORDINAIRE AUTORISE UNE COUPURE DE LIGNE : le montant
        se scinde sur deux lignes d'un rapport signé. C'est l'écart mesuré
        entre A7 (U+202F) et la tarification (U+0020) avant ce lot."""
        self.assertEqual(SEP_MILLIERS, ' ')
        rendu = euros(18680856)
        self.assertNotIn(' ', rendu)          # aucune espace ordinaire
        self.assertEqual(rendu.count(' '), 3)   # 2 milliers + avant €
        print(f'    OK T2 : {rendu!r} — trois espaces fines, aucune ordinaire')

    def test_l_unite_est_attachee_au_nombre(self):
        for rendu in (euros(1200), pourcent(12.3)):
            self.assertIn(' ', rendu[-2:])
        print('    OK T2b : « € » et « % » attachés par une espace insécable')

    def test_aucun_separateur_anglais(self):
        """Le rapport mesuré affichait « 2,435 » — la virgule des milliers."""
        for v in (2435, 1060288.99, 12000):
            self.assertNotIn(',', nombre(v, 2))
        print('    OK T2c : plus aucune virgule de milliers')


class T3_CeQuiNEstPasCalculable(unittest.TestCase):
    """T3 — un zéro affirme une valeur, un tiret avoue une absence."""

    def test_toute_la_famille_rend_le_tiret(self):
        for absent in (None, float('nan'), float('inf'), 'texte', [], {}):
            for fonction in (nombre, euros, pourcent):
                self.assertEqual(fonction(absent), ABSENT,
                                 f'{fonction.__name__}({absent!r})')
        print(f'    OK T3 : 6 formes d\'absence × 3 fonctions → {ABSENT!r}')

    def test_zero_reste_zero(self):
        """⚠️ UN VRAI ZÉRO N'EST PAS UNE ABSENCE. Les confondre serait le
        défaut inverse."""
        self.assertEqual(nombre(0), '0')
        self.assertEqual(euros(0), '0 €')
        self.assertEqual(pourcent(0.0, 1), '0.0 %')
        print('    OK T3b : un zéro mesuré reste « 0 », il ne devient pas « — »')


class T4_LesDecimales(unittest.TestCase):
    """T4 — une précision se justifie, elle ne se choisit pas ligne à ligne."""

    def test_les_precisions_sont_nommees(self):
        """Le rapport mesuré affichait la MÊME colonne à 1, 3 et 4 décimales
        — « 1.0 » à côté de « 1.2176 »."""
        self.assertEqual((DEC_GINI, DEC_RATIO, DEC_POURCENT, DEC_EFFECTIF),
                         (4, 3, 1, 0))
        self.assertEqual(nombre(1.0, DEC_GINI), '1.0000')
        self.assertEqual(nombre(1.2176, DEC_GINI), '1.2176')
        print('    OK T4 : Gini 4 · ratio 3 · pourcent 1 · effectif 0')


if __name__ == '__main__':
    unittest.main(verbosity=2)
