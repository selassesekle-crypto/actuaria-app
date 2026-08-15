# -*- coding: utf-8 -*-
"""Tests — §64 : l'ajustement pour risque de la réassurance détenue.

⚠️ FIXTURES SYNTHÉTIQUES.
"""

import unittest

from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.risque_cede_64 import (
    MOTIF_AJUSTEMENT_HORS_BORNE,
    MOTIF_AJUSTEMENT_NON_DECLARE,
    PORTEE_DE_LA_BORNE_64,
    ajustement_risque_64,
)

METHODE = 'niveau de confiance 75 %, note actuarielle du 30/06/2026'


def _aj(**kw):
    base = {'ajustement_cede_declare': 400.0,
            'ajustement_brut_sous_jacent': 1000.0,
            'methode_declaree': METHODE}
    base.update(kw)
    return ajustement_risque_64(**base)


class T1_LeModuleNeCalculeRien(unittest.TestCase):
    """⚠️ §64 REMPLACE UNE RÈGLE SANS MÉTHODE PAR UNE AUTRE."""

    def test_sans_declaration_le_module_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            ajustement_risque_64(ajustement_brut_sous_jacent=1000.0,
                                 methode_declaree=METHODE)
        self.assertEqual(e.exception.motif, MOTIF_AJUSTEMENT_NON_DECLARE)

    def test_le_refus_ecarte_la_deduction_par_la_part_de_cession(self):
        """⚠️ « 40 % du brut pour une quote-part à 40 % » serait une MÉTHODE."""
        with self.assertRaises(RefusMesure) as e:
            ajustement_risque_64(ajustement_brut_sous_jacent=1000.0,
                                 methode_declaree=METHODE)
        self.assertIn('PART DE CESSION SERAIT UNE', str(e.exception))
        self.assertIn('garanties plafonnées', str(e.exception))

    def test_un_montant_sans_methode_est_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            _aj(methode_declaree='')
        self.assertEqual(e.exception.motif, MOTIF_AJUSTEMENT_NON_DECLARE)

    def test_une_methode_en_placeholder_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _aj(methode_declaree='A_RENSEIGNER')
        self.assertEqual(e.exception.motif, MOTIF_AJUSTEMENT_NON_DECLARE)

    def test_la_methode_declaree_descend_avec_le_resultat(self):
        self.assertIn(METHODE, _aj().motif)


class T2_LaSeuleBorneVerifiable(unittest.TestCase):
    """⚠️ ON NE TRANSFÈRE PAS PLUS DE RISQUE QU'IL N'EN EXISTE."""

    def test_un_ajustement_cede_dans_la_borne_passe(self):
        r = _aj(ajustement_cede_declare=400.0)
        self.assertAlmostEqual(r.ajustement_cede, 400.0)
        self.assertAlmostEqual(r.part_transferee, 0.4, places=9)

    def test_un_ajustement_egal_au_brut_passe(self):
        """La borne est un maximum atteignable, pas un interdit strict."""
        self.assertAlmostEqual(
            _aj(ajustement_cede_declare=1000.0).part_transferee, 1.0)

    def test_un_ajustement_excedant_le_brut_est_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            _aj(ajustement_cede_declare=1200.0)
        self.assertEqual(e.exception.motif, MOTIF_AJUSTEMENT_HORS_BORNE)

    def test_le_refus_nomme_le_SENS_de_l_ecart(self):
        """⚠️ Il va en faveur de l'entité — comme §63 et §65 b)."""
        with self.assertRaises(RefusMesure) as e:
            _aj(ajustement_cede_declare=1200.0)
        self.assertIn('GONFLE', str(e.exception))
        self.assertIn("faveur de l'entité", str(e.exception))

    def test_un_ajustement_cede_negatif_est_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            _aj(ajustement_cede_declare=-1.0)
        self.assertEqual(e.exception.motif, MOTIF_AJUSTEMENT_HORS_BORNE)

    def test_un_brut_negatif_est_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            _aj(ajustement_brut_sous_jacent=-1.0)
        self.assertEqual(e.exception.motif, MOTIF_AJUSTEMENT_HORS_BORNE)


class T3_CeQueLaBorneNeProuvePas(unittest.TestCase):
    """⚠️ ELLE ÉCARTE L'IMPOSSIBLE, ELLE NE VALIDE PAS LE PLAUSIBLE."""

    def test_un_ajustement_cede_nul_passe_la_borne(self):
        """Absurde sur une quote-part — et pourtant la borne l'accepte."""
        r = _aj(ajustement_cede_declare=0.0)
        self.assertAlmostEqual(r.ajustement_cede, 0.0)
        self.assertAlmostEqual(r.part_transferee, 0.0)

    def test_l_etiquette_de_portee_descend_avec_chaque_resultat(self):
        self.assertIn(PORTEE_DE_LA_BORNE_64, _aj().motif)

    def test_l_etiquette_interdit_de_citer_le_controle_comme_conformite(self):
        self.assertIn('Ne PAS citer', PORTEE_DE_LA_BORNE_64)
        self.assertIn('AUCUNE méthode', PORTEE_DE_LA_BORNE_64)

    def test_un_brut_nul_ne_divise_pas_par_zero(self):
        r = _aj(ajustement_cede_declare=0.0, ajustement_brut_sous_jacent=0.0)
        self.assertAlmostEqual(r.part_transferee, 0.0)
        self.assertAlmostEqual(r.ajustement_brut, 0.0)


if __name__ == '__main__':
    unittest.main()
