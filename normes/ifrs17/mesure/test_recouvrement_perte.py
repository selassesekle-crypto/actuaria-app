# -*- coding: utf-8 -*-
"""Tests — la composante de recouvrement de perte (§66A, §66B, §70A, B119D-F).

⚠️ FIXTURES SYNTHÉTIQUES. Le portefeuille livré reste un banc d'essai local
et non versionné ; seuls les ORDRES DE GRANDEUR sont empruntés.
"""

import unittest

from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.reassurance_69 import (
    PAA_RA_69A_NON_EVALUEE,
    PAA_RA_ELIGIBLE,
    PAA_RA_NON_ETABLI,
)
from normes.ifrs17.mesure.recouvrement_perte import (
    DESTINATION_ACTIF,
    DESTINATION_CSM,
    EPSILON_REPRESENTATION,
    MOTIF_AFFECTATION_B119E,
    MOTIF_PART_HORS_BORNES,
    MOTIF_PERTE_NEGATIVE,
    MOTIF_PLAFOND_B119F,
    MOTIF_ROUTAGE_NON_ETABLI,
    PORTEE_DU_CONTROLE_B119F,
    destination_66a,
    destination_66a_hors_paa,
    part_couverte_b119e,
    recouvrement_b119d,
    verifier_plafond_b119f,
)


class TestB119D(unittest.TestCase):

    def test_la_composante_est_le_produit_perte_x_part(self):
        r = recouvrement_b119d(perte_comptabilisee=1000.0,
                               part_recuperable=0.46,
                               verdict_69=PAA_RA_ELIGIBLE)
        self.assertAlmostEqual(r.composante, 460.0, places=9)

    def test_la_destination_est_portee_par_le_resultat_lui_meme(self):
        """⚠️ Le montant et sa destination voyagent ensemble.

        Un recouvrement rendu sans sa destination laisserait l'appelant la
        choisir — or c'est §70A qui la fixe, pas lui.
        """
        r = recouvrement_b119d(perte_comptabilisee=1000.0,
                               part_recuperable=0.46,
                               verdict_69=PAA_RA_ELIGIBLE)
        self.assertEqual(r.destination, DESTINATION_ACTIF)

    def test_une_perte_negative_n_ouvre_aucun_recouvrement(self):
        with self.assertRaises(RefusMesure) as e:
            recouvrement_b119d(perte_comptabilisee=-1.0, part_recuperable=0.5,
                               verdict_69=PAA_RA_ELIGIBLE)
        self.assertEqual(e.exception.motif, MOTIF_PERTE_NEGATIVE)

    def test_une_part_hors_de_zero_un_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            recouvrement_b119d(perte_comptabilisee=1000.0,
                               part_recuperable=46.0,
                               verdict_69=PAA_RA_ELIGIBLE)
        self.assertEqual(e.exception.motif, MOTIF_PART_HORS_BORNES)


class TestAiguillage70A(unittest.TestCase):
    """⚠️ L'AIGUILLE DU §70A EST LE VERDICT §69, ET ELLE PEUT MANQUER."""

    def test_en_paa_l_ajustement_va_a_l_actif(self):
        self.assertEqual(destination_66a(PAA_RA_ELIGIBLE), DESTINATION_ACTIF)

    def test_hors_paa_l_ajustement_va_a_la_csm(self):
        self.assertEqual(destination_66a_hors_paa(), DESTINATION_CSM)

    def test_un_verdict_non_etabli_refuse_de_router(self):
        with self.assertRaises(RefusMesure) as e:
            destination_66a(PAA_RA_NON_ETABLI)
        self.assertEqual(e.exception.motif, MOTIF_ROUTAGE_NON_ETABLI)

    def test_un_69a_non_evalue_refuse_aussi(self):
        with self.assertRaises(RefusMesure) as e:
            destination_66a(PAA_RA_69A_NON_EVALUEE)
        self.assertEqual(e.exception.motif, MOTIF_ROUTAGE_NON_ETABLI)

    def test_le_refus_nomme_les_deux_postes_possibles(self):
        """Un refus qui ne dit pas ce qui manque ne se lève pas."""
        with self.assertRaises(RefusMesure) as e:
            destination_66a(PAA_RA_NON_ETABLI)
        self.assertIn('couverture restante', str(e.exception))
        self.assertIn('services contractuels', str(e.exception))

    def test_le_recouvrement_ne_se_calcule_pas_sans_destination(self):
        """⚠️ Le montant n'est pas rendu « en attendant » sa destination."""
        with self.assertRaises(RefusMesure) as e:
            recouvrement_b119d(perte_comptabilisee=1000.0,
                               part_recuperable=0.46,
                               verdict_69=PAA_RA_NON_ETABLI)
        self.assertEqual(e.exception.motif, MOTIF_ROUTAGE_NON_ETABLI)


class TestB119E(unittest.TestCase):
    """B119E — une méthode de l'entité, jamais une déduction du code."""

    def test_sans_part_declaree_le_module_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            part_couverte_b119e(perte_du_groupe=1000.0)
        self.assertEqual(e.exception.motif, MOTIF_AFFECTATION_B119E)

    def test_un_montant_sans_sa_methode_est_refuse(self):
        """⚠️ B119E porte sur la MÉTHODE, pas sur le montant."""
        with self.assertRaises(RefusMesure) as e:
            part_couverte_b119e(perte_du_groupe=1000.0,
                                part_couverte_declaree=600.0,
                                methode_affectation_declaree='')
        self.assertEqual(e.exception.motif, MOTIF_AFFECTATION_B119E)

    def test_une_methode_en_placeholder_est_refusee(self):
        """« A_RENSEIGNER » n'est pas une méthode systématique."""
        with self.assertRaises(RefusMesure) as e:
            part_couverte_b119e(perte_du_groupe=1000.0,
                                part_couverte_declaree=600.0,
                                methode_affectation_declaree='A_RENSEIGNER')
        self.assertEqual(e.exception.motif, MOTIF_AFFECTATION_B119E)

    def test_une_part_excedant_la_perte_du_groupe_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            part_couverte_b119e(
                perte_du_groupe=1000.0, part_couverte_declaree=1200.0,
                methode_affectation_declaree='prorata des primes cedees')
        self.assertEqual(e.exception.motif, MOTIF_AFFECTATION_B119E)

    def test_une_declaration_complete_est_acceptee(self):
        self.assertAlmostEqual(
            part_couverte_b119e(
                perte_du_groupe=1000.0, part_couverte_declaree=600.0,
                methode_affectation_declaree='prorata des primes cedees'),
            600.0)


class TestB119F_FiletDeNonRegression_PasPreuveDeConformite(unittest.TestCase):
    """⚠️⚠️ CE QUE CETTE CLASSE PROUVE, ET CE QU'ELLE NE PROUVE PAS.

    Quand la composante est calculée par B119D, le plafond de B119F vaut
    `perte × part`, donc exactement la composante : il est atteint PAR
    CONSTRUCTION et sa vérification ne démontre AUCUNE conformité.

    ⚠️ NE PAS CITER CETTE CLASSE COMME ATTESTANT LA CONFORMITÉ À B119F. Sa
    seule valeur est de mordre le jour où le calcul changera — indexation,
    plancher, ajustement pour risque introduit.
    """

    def test_l_etiquette_descend_avec_le_resultat(self):
        """⚠️ Sinon quelqu'un citera le contrôle comme une preuve."""
        r = recouvrement_b119d(perte_comptabilisee=1000.0,
                               part_recuperable=0.46,
                               verdict_69=PAA_RA_ELIGIBLE)
        self.assertEqual(r.motif, PORTEE_DU_CONTROLE_B119F)
        self.assertIn('PAS PREUVE DE CONFORMITÉ', r.motif)
        self.assertIn('PAR CONSTRUCTION', r.motif)

    def test_le_plafond_egale_la_composante_et_c_est_dit(self):
        """La gratuité du contrôle est MESURÉE, pas seulement annoncée."""
        r = recouvrement_b119d(perte_comptabilisee=1000.0,
                               part_recuperable=0.46,
                               verdict_69=PAA_RA_ELIGIBLE)
        self.assertAlmostEqual(r.composante, r.plafond, places=12)

    def test_non_regression_un_calcul_qui_deriverait_est_attrape(self):
        """LA valeur réelle du contrôle : le jour où le calcul changera."""
        with self.assertRaises(RefusMesure) as e:
            verifier_plafond_b119f(500.0, 460.0)
        self.assertEqual(e.exception.motif, MOTIF_PLAFOND_B119F)

    def test_l_arrondi_au_centime_ne_fait_pas_echouer(self):
        """⚠️ Un contrôle strict échouerait sur 129 des 235 lignes livrées.

        ⚠️ ET CE CAS EXACT EXIGE `EPSILON_REPRESENTATION` : en binaire,
        14.38 - 14.375 vaut 0,005000000000000782, donc STRICTEMENT au-dessus
        d'une borne pourtant atteinte à l'égalité en décimal. Retirer
        l'epsilon fait échouer ce test — c'est ce qui l'a révélé.
        """
        self.assertGreater(14.38 - 14.375, 0.005)   # le piège, mesuré
        self.assertLess(14.38 - 14.375, 0.005 + EPSILON_REPRESENTATION * 14.375)
        verifier_plafond_b119f(14.38, 14.375)

    def test_la_borne_suit_le_nombre_de_lignes_agregees(self):
        verifier_plafond_b119f(8460.04, 8459.72, nb_lignes=235)
        with self.assertRaises(RefusMesure):
            verifier_plafond_b119f(8460.04, 8459.72, nb_lignes=1)


if __name__ == '__main__':
    unittest.main()
