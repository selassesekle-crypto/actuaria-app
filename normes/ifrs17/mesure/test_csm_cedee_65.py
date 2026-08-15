# -*- coding: utf-8 -*-
"""Tests — §65, §65A et l'invariant §68 sur la CSM cédée.

⚠️ FIXTURES SYNTHÉTIQUES.
"""

import unittest

from normes.ifrs17.mesure.csm_cedee_65 import (
    ASYMETRIE_65_68,
    CONVENTIONS,
    COUT_NET_NEGATIF,
    COUT_NET_POSITIF,
    MOTIF_CONVENTION_DE_SIGNE_NON_DECLAREE,
    MOTIF_DECOMPTABILISATION_NON_DECLAREE,
    MOTIF_PART_ANTERIEURE_INVALIDE,
    csm_initiale_65,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

SOURCE = 'inventaire des actifs de flux au 31/12/2025, signe'


def _csm(**kw):
    base = {'flux_execution': -1000.0,
            'convention_de_signe': COUT_NET_NEGATIF,
            'decomptabilisation_declaree': 0.0,
            'motif_decomptabilisation': SOURCE}
    base.update(kw)
    return csm_initiale_65(**base)


class T1_LaSommeDesQuatreTermes(unittest.TestCase):

    def test_les_quatre_termes_s_additionnent(self):
        r = _csm(flux_execution=-1000.0, decomptabilisation_declaree=120.0,
                 flux_du_jour=-50.0, produit_66a=30.0)
        self.assertAlmostEqual(r.csm, -900.0, places=9)

    def test_chaque_terme_est_rendu_separement(self):
        """⚠️ Un total qui ne rend pas ses composantes ne se vérifie pas."""
        r = _csm(flux_execution=-1000.0, decomptabilisation_declaree=120.0,
                 flux_du_jour=-50.0, produit_66a=30.0)
        self.assertAlmostEqual(r.flux_execution, -1000.0)
        self.assertAlmostEqual(r.decomptabilisation, 120.0)
        self.assertAlmostEqual(r.flux_du_jour, -50.0)
        self.assertAlmostEqual(r.produit_66a, 30.0)
        self.assertAlmostEqual(
            r.flux_execution + r.decomptabilisation + r.flux_du_jour
            + r.produit_66a, r.csm, places=9)


class T2_Le68InterditToutPlancher(unittest.TestCase):
    """⚠️ L'INVARIANT QUI CHANGE LE TYPE DU RÉSULTAT."""

    def test_un_cout_net_sort_negatif_sans_etre_planche(self):
        r = _csm(flux_execution=-5000.0)
        self.assertAlmostEqual(r.csm, -5000.0)
        self.assertLess(r.csm, 0.0)

    def test_le_cout_net_est_rendu_en_valeur_absolue(self):
        self.assertAlmostEqual(_csm(flux_execution=-5000.0).cout_net, 5000.0)

    def test_un_profit_net_ne_rend_aucun_cout(self):
        self.assertAlmostEqual(_csm(flux_execution=300.0).cout_net, 0.0)

    def test_l_asymetrie_avec_un_groupe_emis_est_ecrite(self):
        """⚠️ Le même mot désigne deux objets aux bornes différentes."""
        r = _csm(flux_execution=-5000.0)
        self.assertIn(ASYMETRIE_65_68, r.motif)
        self.assertIn('sans plancher', r.motif)
        self.assertIn('composante de perte', r.motif)


class T3_LaConventionDeSigneSeDeclare(unittest.TestCase):
    """⚠️ ET LES DEUX BRANCHES DIFFÈRENT — sinon le choix serait fictif."""

    def test_sans_convention_le_module_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            csm_initiale_65(flux_execution=-1000.0, convention_de_signe='',
                            decomptabilisation_declaree=0.0,
                            motif_decomptabilisation=SOURCE)
        self.assertEqual(e.exception.motif,
                         MOTIF_CONVENTION_DE_SIGNE_NON_DECLAREE)

    def test_les_deux_conventions_lisent_la_meme_csm_differemment(self):
        """La preuve que le choix n'est pas fictif, sur le MÊME nombre."""
        neg = _csm(flux_execution=-100.0)
        pos = _csm(flux_execution=-100.0,
                   convention_de_signe=COUT_NET_POSITIF)
        self.assertAlmostEqual(neg.csm, pos.csm, places=9)
        self.assertAlmostEqual(neg.cout_net, 100.0)
        self.assertAlmostEqual(pos.cout_net, 0.0)

    def test_le_65a_admis_sous_une_convention_est_refuse_sous_l_autre(self):
        """⚠️ Le garde-fou lui-même dépend de la convention."""
        self.assertAlmostEqual(
            _csm(flux_execution=-100.0, part_anterieure_65a=60.0).csm, -40.0)
        with self.assertRaises(RefusMesure) as e:
            _csm(flux_execution=-100.0, part_anterieure_65a=60.0,
                 convention_de_signe=COUT_NET_POSITIF)
        self.assertEqual(e.exception.motif, MOTIF_PART_ANTERIEURE_INVALIDE)

    def test_la_convention_descend_avec_le_resultat(self):
        self.assertIn(COUT_NET_NEGATIF, _csm().motif)

    def test_il_n_y_a_que_deux_conventions_et_chacune_a_sa_branche(self):
        """⚠️ Une troisième ajoutée sans branche tomberait en silence dans
        le `else` de `cout_net`, donc dans la convention positive."""
        self.assertEqual(CONVENTIONS, (COUT_NET_NEGATIF, COUT_NET_POSITIF))
        for c in CONVENTIONS:
            self.assertIn(c, _csm(convention_de_signe=c).motif)


class T4_Le65bSeDeclareEtNeSeSupposePas(unittest.TestCase):
    """⚠️ LA LEÇON DE B66 d) : supposer nul est un choix silencieux."""

    def test_sans_declaration_le_module_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            csm_initiale_65(flux_execution=-1000.0,
                            convention_de_signe=COUT_NET_NEGATIF,
                            motif_decomptabilisation=SOURCE)
        self.assertEqual(e.exception.motif,
                         MOTIF_DECOMPTABILISATION_NON_DECLAREE)

    def test_le_refus_dit_dans_quel_sens_l_omission_penche(self):
        with self.assertRaises(RefusMesure) as e:
            csm_initiale_65(flux_execution=-1000.0,
                            convention_de_signe=COUT_NET_NEGATIF)
        self.assertIn('gonfle', str(e.exception))

    def test_declarer_zero_est_legitime(self):
        """⚠️ Zéro déclaré et zéro supposé ne sont pas le même objet."""
        self.assertAlmostEqual(_csm(decomptabilisation_declaree=0.0).csm,
                               -1000.0)

    def test_un_montant_sans_motif_est_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            _csm(decomptabilisation_declaree=120.0,
                 motif_decomptabilisation='')
        self.assertEqual(e.exception.motif,
                         MOTIF_DECOMPTABILISATION_NON_DECLAREE)

    def test_un_motif_en_placeholder_est_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            _csm(decomptabilisation_declaree=120.0,
                 motif_decomptabilisation='A_RENSEIGNER')
        self.assertEqual(e.exception.motif,
                         MOTIF_DECOMPTABILISATION_NON_DECLAREE)


class T5_Le65ASortDeLaMarge(unittest.TestCase):

    def test_la_part_anterieure_quitte_la_csm(self):
        r = _csm(flux_execution=-1000.0, part_anterieure_65a=300.0)
        self.assertAlmostEqual(r.csm, -700.0, places=9)
        self.assertAlmostEqual(r.charge_immediate_65a, 300.0)

    def test_le_motif_nomme_la_charge_immediate_et_le_B5(self):
        r = _csm(flux_execution=-1000.0, part_anterieure_65a=300.0)
        self.assertIn('charge', r.motif)
        self.assertIn('B5', r.motif)

    def test_le_motif_dit_que_la_qualification_appartient_a_l_entite(self):
        r = _csm(flux_execution=-1000.0, part_anterieure_65a=300.0)
        self.assertIn("appartient à", r.motif)

    def test_une_part_excedant_le_cout_net_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _csm(flux_execution=-100.0, part_anterieure_65a=150.0)
        self.assertEqual(e.exception.motif, MOTIF_PART_ANTERIEURE_INVALIDE)

    def test_une_part_negative_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            _csm(part_anterieure_65a=-1.0)
        self.assertEqual(e.exception.motif, MOTIF_PART_ANTERIEURE_INVALIDE)

    def test_sans_65a_le_motif_ne_le_mentionne_pas(self):
        self.assertNotIn('§65A appliqué', _csm().motif)


if __name__ == '__main__':
    unittest.main()
