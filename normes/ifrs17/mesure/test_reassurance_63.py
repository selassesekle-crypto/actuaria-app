# -*- coding: utf-8 -*-
"""Tests — IFRS 17 §63, la mesure de la réassurance détenue.

⚠️ LES DONNÉES SONT SYNTHÉTIQUES, PAR DÉCISION. Le portefeuille livré sert de
banc d'essai LOCAL et ne sera jamais versionné. Les valeurs ci-dessous sont
construites, et la seule chose qu'elles empruntent au réel est la FORME :
trois réassureurs, un collatéral non nul sur un seul d'entre eux.
"""

import unittest

from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.reassurance_63 import (
    MOTIF_HYPOTHESES_DISCORDANTES,
    MOTIF_LITIGES_ABSENTS,
    MOTIF_PARTS_NON_UNITAIRES,
    MOTIF_TAUX_INCOHERENT,
    Reassureur,
    recuperations_nettes,
    risque_non_execution,
    verifier_concordance,
)


def _panel():
    """Trois réassureurs synthétiques, dont un nanti — la forme du réel."""
    return [
        Reassureur('SYNTH_A', 0.50, 0.0010, 0.00, 0.0010),
        Reassureur('SYNTH_B', 0.30, 0.0020, 0.00, 0.0020),
        Reassureur('SYNTH_C', 0.20, 0.0050, 0.40, 0.0030),
    ]


class TestRisqueNonExecution(unittest.TestCase):

    def test_taux_pondere_par_les_parts(self):
        r = risque_non_execution(_panel())
        attendu = 0.50 * 0.0010 + 0.30 * 0.0020 + 0.20 * 0.0030
        self.assertAlmostEqual(r.taux_pondere, attendu, places=12)
        self.assertEqual(r.nb_reassureurs, 3)

    def test_le_collateral_reduit_le_taux_et_c_est_verifie(self):
        """§63 — « y compris l'effet des GARANTIES »."""
        nanti = Reassureur('SYNTH_C', 1.0, 0.0050, 0.40, 0.0030)
        self.assertAlmostEqual(
            risque_non_execution([nanti]).taux_pondere, 0.0030, places=12)

    def test_taux_qui_ignore_le_collateral_est_refuse(self):
        """Un taux égal au défaut brut ne reflète AUCUNE garantie."""
        faux = Reassureur('SYNTH_C', 1.0, 0.0050, 0.40, 0.0050)
        with self.assertRaises(RefusMesure) as e:
            risque_non_execution([faux])
        self.assertEqual(e.exception.motif, MOTIF_TAUX_INCOHERENT)

    def test_parts_qui_ne_somment_pas_a_un_refusees(self):
        panel = _panel()[:2]          # 0,50 + 0,30 = 0,80
        with self.assertRaises(RefusMesure) as e:
            risque_non_execution(panel)
        self.assertEqual(e.exception.motif, MOTIF_PARTS_NON_UNITAIRES)

    def test_panel_vide_refuse_et_ne_rend_pas_zero(self):
        with self.assertRaises(RefusMesure) as e:
            risque_non_execution([])
        self.assertEqual(e.exception.motif, 'panel_vide')

    def test_points_de_base_lus_comme_fraction_refuses(self):
        """48 bps saisis en 48 : hors bornes, et donc attrapés."""
        with self.assertRaises(RefusMesure) as e:
            risque_non_execution([Reassureur('X', 1.0, 48.0, 0.0, 48.0)])
        self.assertEqual(e.exception.motif, 'valeur_hors_bornes')


class TestLitigesAbsents(unittest.TestCase):
    """⚠️ CE QUE LE TAUX NE COUVRE PAS DESCEND AVEC LUI."""

    def test_le_motif_nomme_les_litiges_absents(self):
        r = risque_non_execution(_panel())
        self.assertEqual(r.motif, MOTIF_LITIGES_ABSENTS)
        self.assertIn('LITIGES', r.motif)

    def test_le_motif_nomme_le_sens_de_l_omission(self):
        """L'écart va en faveur de l'entité — et le motif le dit."""
        self.assertIn('en faveur de', MOTIF_LITIGES_ABSENTS)
        self.assertIn('surestime', MOTIF_LITIGES_ABSENTS)


class TestRecuperationsNettes(unittest.TestCase):

    def test_le_risque_diminue_l_actif_de_reassurance(self):
        r = risque_non_execution(_panel())
        nettes = recuperations_nettes(1_000_000.0, r)
        self.assertLess(nettes, 1_000_000.0)
        self.assertAlmostEqual(
            nettes, 1_000_000.0 * (1.0 - r.taux_pondere), places=6)

    def test_recuperations_negatives_refusees(self):
        with self.assertRaises(RefusMesure) as e:
            recuperations_nettes(-1.0, risque_non_execution(_panel()))
        self.assertEqual(e.exception.motif, 'valeur_hors_bornes')


class TestConcordance(unittest.TestCase):
    """§63 première phrase — la contrainte, pas un calcul."""

    def test_hypotheses_identiques_concordent(self):
        h = {'courbe': 'EIOPA_2025T4', 'inflation': 0.021}
        self.assertEqual(
            verifier_concordance(hypotheses_cedees=h,
                                 hypotheses_sous_jacentes=dict(h)), '')

    def test_une_hypothese_divergente_est_nommee(self):
        with self.assertRaises(RefusMesure) as e:
            verifier_concordance(
                hypotheses_cedees={'courbe': 'EIOPA_2025T3', 'infl': 0.021},
                hypotheses_sous_jacentes={'courbe': 'EIOPA_2025T4',
                                          'infl': 0.021})
        self.assertEqual(e.exception.motif, MOTIF_HYPOTHESES_DISCORDANTES)
        self.assertIn('courbe', str(e.exception))
        self.assertIn('EIOPA_2025T3', str(e.exception))
        self.assertIn('EIOPA_2025T4', str(e.exception))

    def test_aucune_hypothese_commune_refusee(self):
        """Sinon « concordant » serait rendu sans rien avoir comparé."""
        with self.assertRaises(RefusMesure) as e:
            verifier_concordance(hypotheses_cedees={'a': 1},
                                 hypotheses_sous_jacentes={'b': 2})
        self.assertEqual(e.exception.motif, MOTIF_HYPOTHESES_DISCORDANTES)
        self.assertIn('AUCUNE', str(e.exception))

    def test_jeu_vide_refuse_car_une_absence_n_est_pas_une_concordance(self):
        with self.assertRaises(RefusMesure) as e:
            verifier_concordance(hypotheses_cedees={},
                                 hypotheses_sous_jacentes={'a': 1})
        self.assertEqual(e.exception.motif, MOTIF_HYPOTHESES_DISCORDANTES)


if __name__ == '__main__':
    unittest.main()
