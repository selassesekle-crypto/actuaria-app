# -*- coding: utf-8 -*-
"""Tests — la réconciliation traité ↔ contrat de la réassurance détenue.

⚠️ FIXTURES SYNTHÉTIQUES. Le portefeuille livré reste un banc d'essai local
et non versionné ; seule la FORME est empruntée — des quote-parts et des
excédents ventilables, un excédent catastrophe qui ne l'est pas.
"""

import unittest

from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.reassurance_reconciliation import (
    ARRONDI_MAX_PAR_CONTRAT,
    MOTIF_CESSION_SANS_TRAITE,
    MOTIF_ECART_NON_EXPLIQUE,
    MOTIF_NON_VENTILABLE_INCONNU,
    MOTIF_NON_VENTILABLE_VENTILE,
    Cession,
    Traite63,
    reconcilier,
)

QP = 'QUOTE_PART'
XL = 'XS_PAR_RISQUE'
CAT = 'XS_CATASTROPHE'


def _traites():
    return [
        Traite63('QP-A', 'A', QP, 1000.00),
        Traite63('XL-A', 'A', XL, 200.00),
        Traite63('CAT-A', 'A', CAT, 300.00),
    ]


def _cessions(n=100, qp_total=1000.00, xl_total=200.00):
    """n contrats se partageant exactement les primes ventilables."""
    lot = []
    for i in range(n):
        lot.append(Cession(f'C{i}', 'A', QP, qp_total / n))
        lot.append(Cession(f'C{i}', 'A', XL, xl_total / n))
    return lot


class TestReconciliationNominale(unittest.TestCase):

    def test_le_cat_declare_sort_du_rapprochement(self):
        r = reconcilier(_traites(), _cessions(),
                        traites_non_ventilables={'CAT-A'})
        self.assertAlmostEqual(r.non_ventilable, 300.00, places=6)
        self.assertEqual(len(r.cellules), 2)
        self.assertTrue(all(c.reconcilie for c in r.cellules))

    def test_les_deux_cotes_sont_verifies_en_NIVEAU_pas_en_difference(self):
        """⚠️ Un écart juste n'exclut pas deux termes faux.

        L'écart est une différence : deux totaux erronés du même montant la
        laisseraient nulle. Les niveaux se vérifient donc séparément.
        """
        r = reconcilier(_traites(), _cessions(),
                        traites_non_ventilables={'CAT-A'})
        attendu = {QP: 1000.00, XL: 200.00}
        for c in r.cellules:
            self.assertAlmostEqual(c.prime_traites, attendu[c.type_traite])
            self.assertAlmostEqual(c.prime_cessions, attendu[c.type_traite])

    def test_le_motif_dit_que_le_non_ventilable_n_est_pas_reconcilie(self):
        r = reconcilier(_traites(), _cessions(),
                        traites_non_ventilables={'CAT-A'})
        self.assertIn('mises de côté', r.motif)
        self.assertIn('CELLULAIRE ET NON GLOBAL', r.motif)

    def test_sans_declaration_le_cat_fait_refus_et_non_tolerance(self):
        """⚠️ Un reliquat non déclaré ne s'absorbe pas en silence."""
        with self.assertRaises(RefusMesure) as e:
            reconcilier(_traites(), _cessions())
        self.assertEqual(e.exception.motif, MOTIF_ECART_NON_EXPLIQUE)
        self.assertIn('300.00', str(e.exception).replace(',', ''))

    def test_la_borne_suit_le_nombre_de_contrats(self):
        r = reconcilier(_traites(), _cessions(n=40),
                        traites_non_ventilables={'CAT-A'})
        for c in r.cellules:
            self.assertEqual(c.nb_contrats, 40)
            self.assertAlmostEqual(c.borne, 40 * ARRONDI_MAX_PAR_CONTRAT)


class TestCompensationEntreMailles(unittest.TestCase):
    """⚠️ LE MOTIF DE TOUT LE MODULE : un total qui boucle ne prouve rien."""

    def _croise(self):
        """Deux mailles fausses de +5 et -5 : le global boucle, pas elles."""
        traites = [Traite63('QP-A', 'A', QP, 1000.00),
                   Traite63('QP-B', 'B', QP, 1000.00)]
        cessions = ([Cession(f'A{i}', 'A', QP, 995.00 / 10) for i in range(10)]
                    + [Cession(f'B{i}', 'B', QP, 1005.00 / 10)
                       for i in range(10)])
        return traites, cessions

    def test_deux_erreurs_qui_se_compensent_sont_refusees(self):
        traites, cessions = self._croise()
        with self.assertRaises(RefusMesure) as e:
            reconcilier(traites, cessions)
        self.assertEqual(e.exception.motif, MOTIF_ECART_NON_EXPLIQUE)
        self.assertIn('2 maille(s)', str(e.exception))

    def test_un_controle_global_les_aurait_laissees_passer(self):
        """La contre-épreuve : la somme des écarts vaut zéro."""
        traites, cessions = self._croise()
        vendu = sum(t.prime_cedee for t in traites)
        cede = sum(c.prime_cedee for c in cessions)
        self.assertAlmostEqual(vendu - cede, 0.0, places=6)

    def test_la_compensation_masquee_est_publiee(self):
        """Sur un jeu qui passe, l'écart absolu excède l'écart net."""
        traites = [Traite63('QP-A', 'A', QP, 1000.00),
                   Traite63('QP-B', 'B', QP, 1000.00)]
        cessions = ([Cession(f'A{i}', 'A', QP, 999.98 / 10) for i in range(10)]
                    + [Cession(f'B{i}', 'B', QP, 1000.02 / 10)
                       for i in range(10)])
        r = reconcilier(traites, cessions)
        self.assertAlmostEqual(r.ecart_net, 0.0, places=6)
        self.assertGreater(r.ecart_absolu, 0.03)
        self.assertGreater(r.compensation_masquee, 0.03)


class TestMailleMixte(unittest.TestCase):
    """⚠️ UNE MAILLE QUI MÊLE DÉCLARÉ ET VENTILABLE RESTE CONTRÔLÉE.

    L'exclure d'un bloc ferait échapper au contrôle la prime du traité
    ventilable — le défaut corrigé avant le premier test.
    """

    def _mixte(self, cede_qp):
        traites = [Traite63('QP-A', 'A', QP, 1000.00),
                   Traite63('QP-A-CAT', 'A', QP, 300.00)]
        cessions = [Cession(f'C{i}', 'A', QP, cede_qp / 10) for i in range(10)]
        return traites, cessions

    def test_la_part_ventilable_est_toujours_rapprochee(self):
        r = reconcilier(*self._mixte(1000.00),
                        traites_non_ventilables={'QP-A-CAT'})
        self.assertEqual(len(r.cellules), 1)
        self.assertAlmostEqual(r.cellules[0].prime_traites, 1000.00, places=6)
        self.assertAlmostEqual(r.non_ventilable, 300.00, places=6)

    def test_une_erreur_sur_la_part_ventilable_est_attrapee(self):
        with self.assertRaises(RefusMesure) as e:
            reconcilier(*self._mixte(900.00),
                        traites_non_ventilables={'QP-A-CAT'})
        self.assertEqual(e.exception.motif, MOTIF_ECART_NON_EXPLIQUE)


class TestRefusDeDeclaration(unittest.TestCase):

    def test_declaration_qui_ne_mord_sur_rien_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            reconcilier(_traites(), _cessions(),
                        traites_non_ventilables={'CAT-A', 'CAT-INEXISTANT'})
        self.assertEqual(e.exception.motif, MOTIF_NON_VENTILABLE_INCONNU)

    def test_declare_non_ventilable_mais_ventile_refuse(self):
        traites = _traites()
        cessions = _cessions() + [Cession('C0', 'A', CAT, 300.00)]
        with self.assertRaises(RefusMesure) as e:
            reconcilier(traites, cessions,
                        traites_non_ventilables={'CAT-A'})
        self.assertEqual(e.exception.motif, MOTIF_NON_VENTILABLE_VENTILE)

    def test_cession_sans_traite_refusee(self):
        cessions = _cessions() + [Cession('C0', 'Z', QP, 10.00)]
        with self.assertRaises(RefusMesure) as e:
            reconcilier(_traites(), cessions,
                        traites_non_ventilables={'CAT-A'})
        self.assertEqual(e.exception.motif, MOTIF_CESSION_SANS_TRAITE)

    def test_aucun_traite_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            reconcilier([], _cessions())
        self.assertEqual(e.exception.motif, 'aucun_traite')


if __name__ == '__main__':
    unittest.main()
