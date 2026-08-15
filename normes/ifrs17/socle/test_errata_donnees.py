# -*- coding: utf-8 -*-
"""Tests — l'errata des données livrées, et ce qui le rend opérant."""

import unittest

from normes.ifrs17.mesure.declaration import est_renseigne
from normes.ifrs17.socle.errata_donnees import (
    COLONNE_DESAVOUEE_TEST_47,
    COMPTAGE_DEFICITAIRES,
    CONVENTION_DES_SENSIBILITES,
    ECART_ENTRE_CONVENTIONS_A_4PCT,
    ECUEIL_TAUX_INCOMPLET,
    EFFET_ACTUALISATION_A_4PCT,
    ERRATA,
    FORME_NEANT_MOTIVE,
    FORME_REFUS,
    FORME_TECHNIQUE,
    FORMES_PRIME_ILLIQUIDITE,
    MOTIF_NON_OPPOSABLE_CEIOPS,
    MOTIF_OPPOSABLE_ECART_DE_LIQUIDITE,
    PANIER_AVEC_FRAIS_GESTION,
    PANIER_COMPLET_47,
    PANIER_COMPLET_47_ACTUALISE,
    PANIER_LIVRE,
    PANIERS,
    PANIERS_SANS_COMPTAGE_ETABLI,
    PANIERS_TRIBUTAIRES_D_UNE_DECLARATION,
    SENSIBILITE_ACTUALISATION,
    SourceDesavouee,
    qualifier_prime_illiquidite,
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

    def test_le_552_porte_desormais_la_reserve_d_actualisation(self):
        """⚠️ ET ELLE PENCHE DANS L'AUTRE SENS QUE LES DEUX PRÉCÉDENTES."""
        r = reserve_du_panier(PANIER_AVEC_FRAIS_GESTION)
        self.assertIn("N'EST PAS ACTUALISÉ", r)
        self.assertIn('SURESTIME', r)
        self.assertIn('§32 a) ii)', r)

    def test_la_reserve_du_552_dit_que_les_omissions_ne_se_compensent_pas(self):
        r = reserve_du_panier(PANIER_AVEC_FRAIS_GESTION)
        self.assertIn('NE SE COMPENSENT PAS', r)
        self.assertIn('11 %', r)

    def test_la_reserve_du_552_dit_pourquoi_il_reste_employe(self):
        """Le refuser supprimerait une date que la norme exige."""
        self.assertIn('meilleur disponible',
                      reserve_du_panier(PANIER_AVEC_FRAIS_GESTION))

    def test_le_panier_livre_ne_porte_aucune_reserve_car_il_est_refuse(self):
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

    def test_les_deux_paniers_complets_sont_tributaires(self):
        self.assertEqual(
            PANIERS_TRIBUTAIRES_D_UNE_DECLARATION,
            frozenset({PANIER_COMPLET_47, PANIER_COMPLET_47_ACTUALISE}))


class T5_LeQuatriemePanierNAPasDeComptage(unittest.TestCase):
    """⚠️ « CONNU SANS COMPTAGE » N'EST PAS « INCONNU »."""

    def test_il_est_connu_mais_absent_du_comptage(self):
        self.assertIn(PANIER_COMPLET_47_ACTUALISE, PANIERS)
        self.assertNotIn(PANIER_COMPLET_47_ACTUALISE, COMPTAGE_DEFICITAIRES)
        self.assertIn(PANIER_COMPLET_47_ACTUALISE,
                      PANIERS_SANS_COMPTAGE_ETABLI)

    def test_sa_reserve_exige_DEUX_declarations(self):
        """⚠️ La courbe ET la convention — pas seulement la courbe."""
        r = reserve_du_panier(PANIER_COMPLET_47_ACTUALISE)
        self.assertIn('COURBE déclarée', r)
        self.assertIn('CONVENTION déclarée', r)
        self.assertIn('§36 b', r)

    def test_sa_reserve_chiffre_le_poids_de_la_convention(self):
        """⚠️ 47 contrats sur 208 : la convention pèse 23 % de l'effet."""
        r = reserve_du_panier(PANIER_COMPLET_47_ACTUALISE)
        self.assertIn(str(ECART_ENTRE_CONVENTIONS_A_4PCT), r)
        self.assertIn(str(EFFET_ACTUALISATION_A_4PCT), r)
        self.assertIn('23%', r.replace(' %', '%'))

    def test_la_sensibilite_est_mesuree_et_decroissante(self):
        """⚠️ L'actualisation RÉDUIT — sens inverse des deux omissions."""
        taux = sorted(SENSIBILITE_ACTUALISATION)
        comptes = [SENSIBILITE_ACTUALISATION[t] for t in taux]
        self.assertEqual(comptes[0], 747)
        self.assertEqual(comptes, sorted(comptes, reverse=True))

    def test_la_sensibilite_nomme_sa_convention(self):
        self.assertIn('durée moyenne', CONVENTION_DES_SENSIBILITES)
        self.assertIn('nominal', CONVENTION_DES_SENSIBILITES)


class T6_LaPrimeDIlliquiditeATroisFormes(unittest.TestCase):
    """⚠️ TECHNIQUE, NÉANT MOTIVÉ, OU REFUS — JAMAIS UN NÉANT NU."""

    #: ⚠️ LE CALIBRAGE VIT DANS LA GATE, comme celui de `PLACEHOLDERS`. Un
    #: contrôle sur de la prose qui n'exhibe pas ses deux taux d'erreur se
    #: fait croire sur parole.
    NEANTS_MOTIVES = (
        'ecart de liquidite tenu a des maturites de 0,81 a 4,76 ans',
        'aucune prime retenue, les passifs sont adosses a du monetaire',
        'nulle par decision du comite ALM du 12/06/2026',
        'sans objet : portefeuille integralement en run-off',
        'zero, faute de portefeuille de reference representatif',
        'rien de significatif au regard du seuil de materialite',
        'neant, spread du portefeuille de reference non significatif',
        'non applicable aux traites detenus, note du 30/06',
    )
    NEANTS_NUS = (
        'neant', 'Neant', 'NEANT', 'néant', 'nul', 'nulle', 'zero', 'aucune',
        'aucun', 'rien', 'sans objet', 'non applicable', 'SANS OBJET', 'N/A',
        'na', '-', '', 'A_REMPLACER', 'pas applicable', 'inapplicable',
        'non', 'no', '  neant  ',
    )

    def test_le_controle_verifie_la_PRESENCE_du_motif_pas_sa_QUALITE(self):
        """⚠️ CE QU'IL N'ÉTABLIT PAS, ET IL FAUT LE LIRE AVANT DE S'Y FIER.

        « Hors plage CEIOPS » porte un motif, donc passe — alors que ce
        motif n'est PAS opposable : il invoque une source sans portée
        normative ici. Le mécanisme constate qu'une raison est donnée ; il
        ne juge pas si elle vaut. Les deux contrôles sont distincts, et le
        second n'existe pas.
        """
        qualifier_prime_illiquidite(
            forme=FORME_NEANT_MOTIVE,
            contenu='hors plage CEIOPS 24-48 ans')
        self.assertIn("N'EST PAS UN MOTIF OPPOSABLE",
                      MOTIF_NON_OPPOSABLE_CEIOPS)

    def test_zero_faux_rejet_sur_les_neants_motives(self):
        for v in self.NEANTS_MOTIVES:
            qualifier_prime_illiquidite(forme=FORME_NEANT_MOTIVE, contenu=v)

    def test_zero_faux_accepte_sur_les_neants_nus(self):
        for v in self.NEANTS_NUS:
            with self.assertRaises(SourceDesavouee, msg=v):
                qualifier_prime_illiquidite(forme=FORME_NEANT_MOTIVE,
                                            contenu=v)

    def test_une_technique_est_acceptee_et_engage_l_entite(self):
        m = qualifier_prime_illiquidite(
            forme=FORME_TECHNIQUE,
            contenu='approche ascendante B80, granularite par portefeuille')
        self.assertIn('engage', m)
        self.assertIn('ne sont pas des règles', m)

    def test_un_neant_motive_est_une_DECLARATION_pas_une_absence(self):
        m = qualifier_prime_illiquidite(
            forme=FORME_NEANT_MOTIVE,
            contenu='hors plage CEIOPS, duree maximale 4,76 ans')
        self.assertIn('pas une absence de déclaration', m)
        self.assertIn(MOTIF_NON_OPPOSABLE_CEIOPS, m)
        self.assertIn(MOTIF_OPPOSABLE_ECART_DE_LIQUIDITE, m)

    def test_un_refus_est_une_position_et_il_se_porte(self):
        m = qualifier_prime_illiquidite(
            forme=FORME_REFUS, contenu='faute de portefeuille de reference')
        self.assertIn('REFUSE', m)
        self.assertIn(ECUEIL_TAUX_INCOMPLET, m)

    def test_une_quatrieme_forme_est_refusee(self):
        with self.assertRaises(SourceDesavouee):
            qualifier_prime_illiquidite(forme='PEUT_ETRE', contenu='x')

    def test_les_trois_formes_exigent_un_contenu(self):
        for f in FORMES_PRIME_ILLIQUIDITE:
            with self.assertRaises(SourceDesavouee, msg=f):
                qualifier_prime_illiquidite(forme=f, contenu='')


class T7_LaPlageCEIOPSNEstPasOpposable(unittest.TestCase):
    """⚠️ CETTE CONSTANTE DISAIT « À INSTRUIRE » — c'était lui prêter une
    autorité qu'elle n'a pas."""

    def test_aucune_borne_numerique_n_est_posee(self):
        """24 et 48 sont CITÉS, jamais comparés à une durée."""
        self.assertIn('24 à 48 ans', MOTIF_NON_OPPOSABLE_CEIOPS)

    def test_le_motif_dit_que_la_source_n_est_pas_opposable(self):
        self.assertIn("N'EST PAS UN MOTIF OPPOSABLE",
                      MOTIF_NON_OPPOSABLE_CEIOPS)
        self.assertIn('trois degrés de distance',
                      MOTIF_NON_OPPOSABLE_CEIOPS.lower()
                      .replace('degres', 'degrés'))

    def test_le_motif_rappelle_que_la_norme_ne_pose_aucun_seuil(self):
        """⚠️ Vérifié au texte : ni §36 a) ni B80 n'en portent."""
        self.assertIn('NI §36 a) NI B80', MOTIF_NON_OPPOSABLE_CEIOPS)
        self.assertIn('sans borne', MOTIF_NON_OPPOSABLE_CEIOPS)

    def test_l_argument_d_auto_annulation_a_DISPARU(self):
        """⚠️ RETIRÉ, PAS NUANCÉ : il importait un paramètre postérieur de
        cinq ans à la phrase qu'il commentait."""
        for mort in ('se contredit', 'Last Liquid Point', 'nulle part',
                     'SUR QUELLE LECTURE'):
            self.assertNotIn(mort, MOTIF_NON_OPPOSABLE_CEIOPS)

    def test_le_motif_opposable_est_MESURABLE_et_le_dit(self):
        self.assertIn('MESURABLE', MOTIF_OPPOSABLE_ECART_DE_LIQUIDITE)
        self.assertIn('0,81 à 4,76 ans', MOTIF_OPPOSABLE_ECART_DE_LIQUIDITE)
        self.assertIn('se conteste', MOTIF_OPPOSABLE_ECART_DE_LIQUIDITE)


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
