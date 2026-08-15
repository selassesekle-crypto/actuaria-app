# -*- coding: utf-8 -*-
"""Tests — §66 et §67 : le déroulé de la CSM cédée.

⚠️ FIXTURES SYNTHÉTIQUES.
"""

import unittest

from normes.ifrs17.mesure.csm_cedee_65 import (
    COUT_NET_NEGATIF,
    MOTIF_CONVENTION_DE_SIGNE_NON_DECLAREE,
)
from normes.ifrs17.mesure.csm_cedee_66 import (
    EXCLUSION_67,
    MOTIF_MODELE_SOUS_JACENT_NON_DECLARE,
    MOTIF_UNITES_NON_DECLAREES,
    deroule_66,
    variations_futures_66c,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure


def _deroule(**kw):
    base = {'ouverture': -1000.0, 'convention_de_signe': COUT_NET_NEGATIF,
            'unites_periode': 0.0, 'unites_restantes': 100.0}
    base.update(kw)
    return deroule_66(**base)


class T1_LesSixPostesSAdditionnent(unittest.TestCase):

    def test_le_deroule_somme_ses_postes(self):
        r = _deroule(nouveaux_contrats=200.0, interet_capitalise=30.0,
                     produits_66a=40.0, reprises_66b=10.0,
                     variation_totale_flux=-60.0, ecarts_de_change=5.0)
        self.assertAlmostEqual(r.cloture, -775.0, places=9)

    def test_chaque_poste_est_rendu_separement(self):
        """⚠️ Un total qui ne rend pas ses composantes ne se vérifie pas."""
        r = _deroule(nouveaux_contrats=200.0, interet_capitalise=30.0,
                     produits_66a=40.0, reprises_66b=10.0,
                     variation_totale_flux=-60.0, ecarts_de_change=5.0)
        somme = (r.ouverture + r.nouveaux_contrats + r.interet_capitalise
                 + r.produits_66a + r.reprises_66b + r.variations_futures
                 + r.ecarts_de_change - r.services_recus)
        self.assertAlmostEqual(somme, r.cloture, places=9)

    def test_aucun_plancher_a_zero(self):
        """⚠️ §68 écarte les §47-52 : un coût net sort tel quel."""
        self.assertAlmostEqual(_deroule(ouverture=-9000.0).cloture, -9000.0)

    def test_sans_convention_le_deroule_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            _deroule(convention_de_signe='')
        self.assertEqual(e.exception.motif,
                         MOTIF_CONVENTION_DE_SIGNE_NON_DECLAREE)


class T2_Le67EstUneContrainteNegative(unittest.TestCase):
    """⚠️ CE PARAGRAPHE DIT QUOI NE PAS METTRE — et c'est vérifiable."""

    def test_le_mouvement_de_non_execution_est_exclu_du_poste_c(self):
        r = _deroule(variation_totale_flux=-100.0,
                     mouvement_non_execution_67=-30.0)
        self.assertAlmostEqual(r.variations_futures, -70.0, places=9)

    def test_le_montant_exclu_est_publie_et_non_fondu(self):
        r = _deroule(variation_totale_flux=-100.0,
                     mouvement_non_execution_67=-30.0)
        self.assertAlmostEqual(r.exclu_67, -30.0, places=9)
        self.assertIn('EXCLU au titre du §67', r.motif)

    def test_l_exclusion_change_la_cloture(self):
        """⚠️ La preuve que la contrainte mord : sans elle, autre résultat."""
        avec = _deroule(variation_totale_flux=-100.0,
                        mouvement_non_execution_67=-30.0)
        sans = _deroule(variation_totale_flux=-100.0)
        self.assertNotAlmostEqual(avec.cloture, sans.cloture)
        self.assertAlmostEqual(avec.cloture - sans.cloture, 30.0, places=9)

    def test_l_etiquette_du_67_descend_avec_chaque_deroule(self):
        self.assertIn(EXCLUSION_67, _deroule().motif)


class T3_LesDeuxExclusionsDuC(unittest.TestCase):
    """⚠️ ET LA SECONDE DÉPEND DU MODÈLE DU SOUS-JACENT, PAS DU CÉDÉ."""

    def test_la_variation_sans_ajustement_du_sous_jacent_est_exclue(self):
        self.assertAlmostEqual(
            variations_futures_66c(variation_totale=-100.0,
                                   mouvement_non_execution_67=0.0,
                                   variation_sous_jacent_sans_csm=-40.0),
            -60.0, places=9)

    def test_le_57_58_est_exclu_si_le_sous_jacent_est_en_paa(self):
        self.assertAlmostEqual(
            variations_futures_66c(variation_totale=-100.0,
                                   mouvement_non_execution_67=0.0,
                                   variation_57_58=-25.0,
                                   sous_jacent_en_paa=True),
            -75.0, places=9)

    def test_le_57_58_n_est_PAS_exclu_hors_paa(self):
        """⚠️ Les deux branches diffèrent — c) ii) porte une condition."""
        self.assertAlmostEqual(
            variations_futures_66c(variation_totale=-100.0,
                                   mouvement_non_execution_67=0.0,
                                   variation_57_58=-25.0,
                                   sous_jacent_en_paa=False),
            -100.0, places=9)

    def test_sans_le_modele_du_sous_jacent_le_module_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            variations_futures_66c(variation_totale=-100.0,
                                   mouvement_non_execution_67=0.0,
                                   variation_57_58=-25.0)
        self.assertEqual(e.exception.motif,
                         MOTIF_MODELE_SOUS_JACENT_NON_DECLARE)

    def test_le_refus_distingue_le_sous_jacent_du_groupe_cede(self):
        """⚠️ Deux élections distinctes — la faute du §70A ne se répète pas."""
        with self.assertRaises(RefusMesure) as e:
            variations_futures_66c(variation_totale=-100.0,
                                   mouvement_non_execution_67=0.0,
                                   variation_57_58=-25.0)
        self.assertIn('SOUS-JACENT', str(e.exception))
        self.assertIn('pas celui du groupe cédé', str(e.exception))

    def test_sans_variation_57_58_le_modele_n_est_pas_exige(self):
        """La déclaration n'est exigée que là où elle change le résultat."""
        self.assertAlmostEqual(
            variations_futures_66c(variation_totale=-100.0,
                                   mouvement_non_execution_67=0.0),
            -100.0, places=9)


class T4_LePosteEExigeLesUnitesDeB119(unittest.TestCase):
    """⚠️ RÉPARTIR LINÉAIREMENT SERAIT UNE HYPOTHÈSE, PAS SON ABSENCE."""

    def test_sans_unites_le_module_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            deroule_66(ouverture=-1000.0,
                       convention_de_signe=COUT_NET_NEGATIF)
        self.assertEqual(e.exception.motif, MOTIF_UNITES_NON_DECLAREES)

    def test_le_refus_nomme_le_volume_de_prestations(self):
        with self.assertRaises(RefusMesure) as e:
            deroule_66(ouverture=-1000.0,
                       convention_de_signe=COUT_NET_NEGATIF)
        self.assertIn('VOLUME DE PRESTATIONS', str(e.exception))
        self.assertIn('RÉPARTIR LINÉAIREMENT', str(e.exception))

    def test_la_repartition_suit_les_unites_declarees(self):
        r = _deroule(ouverture=-1000.0, unites_periode=25.0,
                     unites_restantes=100.0)
        self.assertAlmostEqual(r.services_recus, -250.0, places=9)
        self.assertAlmostEqual(r.cloture, -750.0, places=9)

    def test_des_unites_negatives_sont_refusees(self):
        with self.assertRaises(RefusMesure) as e:
            _deroule(unites_periode=-1.0)
        self.assertEqual(e.exception.motif, MOTIF_UNITES_NON_DECLAREES)

    def test_la_part_de_la_periode_ne_peut_exceder_le_tout(self):
        with self.assertRaises(RefusMesure) as e:
            _deroule(unites_periode=120.0, unites_restantes=100.0)
        self.assertEqual(e.exception.motif, MOTIF_UNITES_NON_DECLAREES)

    def test_zero_unite_restante_reconnait_toute_la_marge(self):
        """⚠️ Nommé plutôt qu'évité : la couverture est entièrement fournie."""
        r = _deroule(ouverture=-1000.0, unites_periode=0.0,
                     unites_restantes=0.0)
        self.assertAlmostEqual(r.services_recus, -1000.0, places=9)
        self.assertAlmostEqual(r.cloture, 0.0, places=9)
        self.assertIn('AUCUNE UNITÉ RESTANTE', r.motif)


if __name__ == '__main__':
    unittest.main()
