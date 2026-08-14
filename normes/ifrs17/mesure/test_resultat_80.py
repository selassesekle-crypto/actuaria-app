# -*- coding: utf-8 -*-
"""Tests X1 — l'état du §80, et son articulation avec le déroulé du passif.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️⚠️ AUCUNE VALEUR DE SOURCE EXTERNE N'EST REPRISE ICI. La règle
d'articulation vérifiée ci-dessous a été LUE dans l'exemple 20 des
Illustrative Examples accompagnant IFRS 17 (IFRS Foundation), dont les
conditions de réutilisation sont restrictives et le dépôt public. L'exemple
a enseigné l'invariant ; les chiffres employés ici sont ceux de la
plateforme et de fixtures écrites pour ce test.

⚠️ ET LA DISTINCTION QUI COMPTE : `assembler()` ne fait qu'additionner, ce
qui ne prouve rien. La propriété qui vaut est CROISÉE, et c'est
`verifier_articulation()` qui la porte.
"""
import unittest

from normes.ifrs17.mesure.lrc_paa import RefusMesure, periode_annuelle
from normes.ifrs17.mesure.resultat_80 import (
    MOTIF_ARTICULATION_ROMPUE,
    MOTIF_COMPOSANTE_INVESTISSEMENT,
    MOTIF_SANS_PERIODE,
    assembler,
    verifier_articulation,
)

#: Une période quelconque, mesurée par la plateforme — aucune valeur reprise.
COMMUN = {'primes_attendues': 1200.0, 'duree_couverture': 2,
          'frais_acquisition_attribuables': 240.0,
          'frais_maintenance_attribuables': 60.0,
          'eligibilite_declaree': True}


def _periode(**kw):
    return periode_annuelle(**{**COMMUN, 'frais_non_attribuables': 40.0, **kw})


class X1_LesSeptPostesDu80(unittest.TestCase):
    """X1 — la ventilation en deux postes, et le signe qui bascule."""

    def test_les_charges_basculent_au_negatif_pour_la_presentation(self):
        """⚠️ `lrc_paa` REND DES CHARGES POSITIVES ; le §80 les presente
        NEGATIVES. Le retournement se fait ici et il est declare -- le
        laisser implicite ferait passer une inversion pour une egalite."""
        p = _periode()
        e = assembler(periode=p, charge_financiere=30.0)
        self.assertGreater(p.charges_service, 0)
        self.assertLess(e.insurance_service_expenses, 0)
        self.assertAlmostEqual(e.insurance_service_expenses,
                               -p.charges_service, 9)
        self.assertLess(e.charges_financieres, 0)
        print(f"    OK X1 : charges {p.charges_service:+.0f} en mesure -> "
              f"{e.insurance_service_expenses:+.0f} en presentation")

    def test_les_deux_postes_et_leur_somme(self):
        e = assembler(periode=_periode(), charge_financiere=30.0,
                      produits_placements=12.0)
        self.assertAlmostEqual(
            e.insurance_service_result,
            e.insurance_revenue + e.insurance_service_expenses, 9)
        self.assertAlmostEqual(
            e.finance_result, e.produits_placements + e.charges_financieres, 9)
        self.assertAlmostEqual(
            e.resultat, e.insurance_service_result + e.finance_result, 9)
        print(f"    OK X1b : service {e.insurance_service_result:+.0f} + "
              f"financier {e.finance_result:+.0f} = {e.resultat:+.0f}")

    def test_la_reserve_du_resultat_DESCEND_depuis_la_mesure(self):
        """⚠️ SANS LA SEPARATION ATTRIBUABLE / NON ATTRIBUABLE, le resultat
        n'est pas etabli -- et il ne le devient pas en changeant d'etat."""
        p = periode_annuelle(**COMMUN)          # frais_non_attribuables omis
        self.assertIsNone(p.resultat)
        e = assembler(periode=p, charge_financiere=30.0)
        self.assertIsNone(e.resultat)
        self.assertIn('NON FOURNIE', e.motif)
        # ce qui EST etabli le reste
        self.assertIsNotNone(e.insurance_service_result)
        self.assertIsNotNone(e.finance_result)
        print("    OK X1c : separation absente -> resultat NON ETABLI, mais "
              "les deux postes du §80 restent etablis")


class X2_LArticulationAvecLeDeroule(unittest.TestCase):
    """X2 — la seule propriété de ce module qui ne soit pas une tautologie."""

    def _couple(self, charge=30.0):
        e = assembler(periode=_periode(), charge_financiere=charge)
        return e, {
            'revenue_du_deroule': -e.insurance_revenue,
            'charges_du_deroule': -e.insurance_service_expenses,
            'charges_financieres_du_deroule': -e.charges_financieres}

    def test_un_couple_coherent_ne_rend_aucun_ecart(self):
        e, deroule = self._couple()
        self.assertEqual(verifier_articulation(e, **deroule), '')
        print("    OK X2 : compte de resultat et deroule du passif "
              "concordent sur les 3 lignes")

    def test_une_ligne_qui_se_contredit_est_NOMMEE(self):
        """⚠️ DEUX ETATS PEUVENT CHACUN BOUCLER SUR EUX-MEMES ET SE
        CONTREDIRE ENTRE EUX. C'est exactement ce que cette verification
        existe pour attraper -- aucun controle interne a l'un des deux ne le
        verrait."""
        e, deroule = self._couple()
        deroule['charges_financieres_du_deroule'] += 7.0
        with self.assertRaises(RefusMesure) as ctx:
            verifier_articulation(e, **deroule)
        self.assertEqual(ctx.exception.motif, MOTIF_ARTICULATION_ROMPUE)
        msg = str(ctx.exception)
        self.assertIn('financiers', msg)
        self.assertIn('+7.00', msg)
        print("    OK X2b : une ligne contredite -> refus, la ligne ET "
              "l'ecart sont nommes")

    def test_les_trois_lignes_sont_verifiees_pas_seulement_le_total(self):
        """⚠️ DEUX ERREURS QUI SE COMPENSENT ENTRE DEUX LIGNES DONNERAIENT UN
        TOTAL JUSTE. Le controle porte ligne a ligne, jamais sur la somme."""
        e, deroule = self._couple()
        deroule['revenue_du_deroule'] += 50.0
        deroule['charges_du_deroule'] -= 50.0      # le total reste juste
        with self.assertRaises(RefusMesure) as ctx:
            verifier_articulation(e, **deroule)
        msg = str(ctx.exception)
        self.assertIn('2 ligne(s)', msg)
        print("    OK X2c : 2 erreurs qui se compensent -> les DEUX lignes "
              "sont attrapees, malgre un total juste")


class X3_LArticle85(unittest.TestCase):
    """X3 — §85, rendu vérifiable."""

    def test_une_composante_d_investissement_declaree_est_refusee(self):
        """⚠️ §85 : « Les produits et charges [...] presentes en resultat net
        ne doivent pas comprendre de composantes investissement. » Elle se
        deplace entre passifs et ne touche JAMAIS le compte de resultat : il
        n'y a donc aucune ligne ou la mettre."""
        with self.assertRaises(RefusMesure) as ctx:
            assembler(periode=_periode(), composante_investissement=100.0)
        self.assertEqual(ctx.exception.motif,
                         MOTIF_COMPOSANTE_INVESTISSEMENT)
        self.assertIn('aucune ligne', str(ctx.exception))
        print("    OK X3 : composante d'investissement -> refus motive, §85 "
              "n'a pas de ligne pour elle")

    def test_l_etat_publie_que_le_85_est_tenu(self):
        e = assembler(periode=_periode(), charge_financiere=30.0)
        self.assertIn('§85 vérifié', e.motif)
        print("    OK X3b : l'etat publie que le §85 est tenu")


class X4_LesRefus(unittest.TestCase):
    """X4 — ce que le module refuse plutôt que de le fausser."""

    def test_aucune_periode_n_est_pas_un_resultat_nul(self):
        with self.assertRaises(RefusMesure) as ctx:
            assembler(periode=None)
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_PERIODE)
        self.assertIn('Ran 0 tests', str(ctx.exception))
        print("    OK X4 : aucune periode -> refus, jamais sept lignes a "
              "zero presentees comme un resultat")

    def test_une_charge_financiere_negative_est_refusee(self):
        with self.assertRaises(RefusMesure) as ctx:
            assembler(periode=_periode(), charge_financiere=-30.0)
        self.assertEqual(ctx.exception.motif, 'charge_financiere_negative')
        print("    OK X4b : charge financiere negative -> refus, convention "
              "d'appel signalee")


if __name__ == '__main__':
    unittest.main()
