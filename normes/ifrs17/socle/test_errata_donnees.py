# -*- coding: utf-8 -*-
"""Tests — l'errata des données livrées, et ce qui le rend opérant."""

import unittest

from normes.ifrs17.mesure.declaration import est_renseigne
from normes.ifrs17.socle.errata_donnees import (
    COLONNE_DESAVOUEE_TEST_47,
    COMPTAGE_DEFICITAIRES,
    ERRATA,
    PANIER_AVEC_FRAIS_GESTION,
    PANIER_COMPLET_47,
    PANIER_LIVRE,
    PANIERS_TRIBUTAIRES_D_UNE_DECLARATION,
    SourceDesavouee,
    refuser_source_test_47,
    reserve_du_panier,
)


class T1_LErrataEstComplet(unittest.TestCase):

    def test_chaque_erratum_porte_nature_impact_et_action(self):
        """⚠️ Un défaut sans suite à donner n'est qu'une plainte."""
        for e in ERRATA:
            self.assertTrue(e.ref and e.objet, e)
            self.assertTrue(e.nature and e.description, e.ref)
            self.assertTrue(e.impact and e.action, e.ref)

    def test_les_references_sont_uniques(self):
        refs = [e.ref for e in ERRATA]
        self.assertEqual(len(refs), len(set(refs)))

    def test_chaque_impact_est_chiffre(self):
        """⚠️ « Impact significatif » n'est pas un impact."""
        for e in ERRATA:
            self.assertTrue(any(c.isdigit() for c in e.impact), e.ref)


class T2_E1_LaSourceDesavoueeEstRefusee(unittest.TestCase):
    """⚠️ CE QUI SÉPARE UN ERRATA D'UNE PROSE."""

    def test_la_colonne_desavouee_leve(self):
        with self.assertRaises(SourceDesavouee) as e:
            refuser_source_test_47(COLONNE_DESAVOUEE_TEST_47)
        self.assertIn('249', str(e.exception))
        self.assertIn('747', str(e.exception))

    def test_une_autre_colonne_passe(self):
        refuser_source_test_47('fcf_avec_frais_gestion')

    def test_le_refus_dit_CE_QUI_MANQUE_au_panier(self):
        with self.assertRaises(SourceDesavouee) as e:
            refuser_source_test_47(COLONNE_DESAVOUEE_TEST_47)
        self.assertIn('frais de gestion', str(e.exception))
        self.assertIn('risque non financier', str(e.exception))


class T3_LesTroisPaniersNOntPasLaMemeSolidite(unittest.TestCase):

    def test_les_trois_comptages_mesures(self):
        self.assertEqual(COMPTAGE_DEFICITAIRES[PANIER_LIVRE], 249)
        self.assertEqual(COMPTAGE_DEFICITAIRES[PANIER_AVEC_FRAIS_GESTION], 552)
        self.assertEqual(COMPTAGE_DEFICITAIRES[PANIER_COMPLET_47], 747)

    def test_le_552_ne_porte_aucune_reserve(self):
        """Vérifié : ses taux ne dépendent d'aucune déclaration."""
        self.assertEqual(reserve_du_panier(PANIER_AVEC_FRAIS_GESTION), '')
        self.assertEqual(reserve_du_panier(PANIER_LIVRE), '')

    def test_le_747_porte_sa_reserve_et_elle_descend_avec_lui(self):
        r = reserve_du_panier(PANIER_COMPLET_47)
        self.assertIn('A_REMPLACER', r)
        self.assertIn('DÉCLARATION NON SIGNÉE', r)

    def test_la_reserve_separe_le_droit_de_la_valeur(self):
        """⚠️ §32 a) iii) fonde le 747 EN DROIT ; sa VALEUR reste ouverte."""
        r = reserve_du_panier(PANIER_COMPLET_47)
        self.assertIn('EN DROIT', r)
        self.assertIn('la VALEUR ne l', r)

    def test_un_panier_inconnu_leve_au_lieu_de_rendre_vide(self):
        """Sinon « pas de réserve » vaudrait « je ne connais pas »."""
        with self.assertRaises(SourceDesavouee):
            reserve_du_panier('PANIER_INVENTE')

    def test_seul_le_747_est_tributaire(self):
        self.assertEqual(PANIERS_TRIBUTAIRES_D_UNE_DECLARATION,
                         frozenset({PANIER_COMPLET_47}))


class T4_LeDepotRefuseEffectivementLeStatutDu747(unittest.TestCase):
    """⚠️ LA COHÉRENCE SE VÉRIFIE, ELLE NE SE PROMET PAS."""

    def test_est_renseigne_refuse_le_statut_qui_alimente_le_747(self):
        self.assertFalse(est_renseigne('A_REMPLACER'))
        self.assertFalse(est_renseigne('A REMPLACER'))

    def test_une_declaration_signee_passerait(self):
        """Le refus vise le STATUT, pas la déclaration en général."""
        self.assertTrue(est_renseigne('note actuarielle du 12/06/2026'))


if __name__ == '__main__':
    unittest.main()
