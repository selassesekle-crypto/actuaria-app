# -*- coding: utf-8 -*-
"""Tests — §61, §62 et §62A : grouper et dater la réassurance détenue.

⚠️ FIXTURES SYNTHÉTIQUES. Seule la FORME est empruntée au banc local.
"""

import datetime
import unittest

from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.reassurance_61_62 import (
    CLASSE_AUTRES,
    CLASSE_NON_ETABLIE,
    CLASSE_PROFIT_NET,
    CLASSE_SANS_POSSIBILITE,
    CLASSES_61,
    MOTIF_ACTUALISATION_NON_DECLAREE,
    MOTIF_PANIER_REFUSE,
    MOTIF_POSITION_NON_QUALIFIEE,
    ORIGINE_62A_DEBUT_COUVERTURE,
    ORIGINE_62A_REPORT,
    ORIGINE_62B_DEFICIT_SOUS_JACENT,
    PANIER_ADMIS_FAUTE_DE_MIEUX_62B,
    PANIER_PREFERE_62B,
    RESERVE_18_PAA,
    classe_61,
    date_comptabilisation_62,
)
from normes.ifrs17.socle.errata_donnees import (
    DECLARATION_PRIME_ILLIQUIDITE,
    DECLARATIONS_DU_TAUX_36,
    ECUEIL_TAUX_INCOMPLET,
    FORME_NEANT_MOTIVE,
    FORME_TECHNIQUE,
    PANIER_COMPLET_47,
    PANIER_LIVRE,
    SourceDesavouee,
)

J = datetime.date
DEBUT = J(2026, 1, 1)
PANIER = PANIER_ADMIS_FAUTE_DE_MIEUX_62B
COURBE = ('EIOPA 31/07/2026, source swaps EURIBOR 6 mois, sans VA, '
          'CRA publie de 10 bps deja retranche - note du 12/08/2026')
CONV = 'duree moyenne sur sinistres + frais de gestion + ajustement risque'
ILLIQ = ('approche ascendante B80, spread du portefeuille de reference, '
         'granularite par portefeuille - note ALM du 30/06/2026')
FORME = FORME_TECHNIQUE


class T1_Le61InverseLeCritereDu16(unittest.TestCase):

    def test_une_position_en_faveur_de_l_entite_se_separe(self):
        c = classe_61(position_nette=1500.0, panier_de_la_position=PANIER)
        self.assertEqual(c.classe, CLASSE_PROFIT_NET)
        self.assertIn('PROFIT NET', c.motif)

    def test_le_motif_rappelle_le_groupe_d_un_seul_contrat(self):
        """§61 l'admet explicitement, et c'est contre-intuitif."""
        c = classe_61(position_nette=1500.0, panier_de_la_position=PANIER)
        self.assertIn('un seul contrat', c.motif)

    def test_sans_profit_net_et_sans_declaration_la_classe_n_est_pas_etablie(self):
        """⚠️ Tomber dans AUTRES par défaut affirmerait un examen absent."""
        c = classe_61(position_nette=-1500.0, panier_de_la_position=PANIER)
        self.assertEqual(c.classe, CLASSE_NON_ETABLIE)
        self.assertNotEqual(c.classe, CLASSE_AUTRES)

    def test_une_declaration_signee_ouvre_la_classe_b(self):
        c = classe_61(position_nette=-1500.0, panier_de_la_position=PANIER,
                      possibilite_importante_declaree=
                      'note du 12/06/2026, comite de souscription')
        self.assertEqual(c.classe, CLASSE_SANS_POSSIBILITE)
        self.assertIn('engage', c.motif)

    def test_une_declaration_en_placeholder_ne_l_ouvre_pas(self):
        c = classe_61(position_nette=-1500.0, panier_de_la_position=PANIER,
                      possibilite_importante_declaree='A_RENSEIGNER')
        self.assertEqual(c.classe, CLASSE_NON_ETABLIE)

    def test_aucune_classe_ne_dit_deficitaire(self):
        """Le vocabulaire du §61 est inversé — les noms le suivent."""
        for c in CLASSES_61:
            self.assertNotIn('DEFICIT', c)


class T2_LaPositionDoitDireCeQuElleContient(unittest.TestCase):
    """⚠️ LA LEÇON DU PANIER À 249, APPLIQUÉE AU §61."""

    def test_une_position_sans_panier_qualifie_est_refusee(self):
        with self.assertRaises(RefusMesure) as e:
            classe_61(position_nette=1500.0, panier_de_la_position='')
        self.assertEqual(e.exception.motif, MOTIF_POSITION_NON_QUALIFIEE)

    def test_le_refus_rappelle_que_le_critere_porte_sur_les_flux(self):
        with self.assertRaises(RefusMesure) as e:
            classe_61(position_nette=1500.0, panier_de_la_position='A_DEFINIR')
        self.assertIn('FLUX D', str(e.exception))
        self.assertIn('249', str(e.exception))


class T3_Le62ARefuseUnPanierNonSigne(unittest.TestCase):
    """⚠️ SANS CE REFUS, LA DATE HÉRITERAIT D'UN A_REMPLACER."""

    def test_le_panier_complet_47_est_refuse_pour_dater(self):
        with self.assertRaises(RefusMesure) as e:
            date_comptabilisation_62(
                debut_couverture_cedee=DEBUT, couverture_proportionnelle=False,
                date_deficit_sous_jacent=J(2025, 11, 1),
                traite_conclu_au_plus_tard=True,
                panier_du_deficit=PANIER_COMPLET_47)
        self.assertEqual(e.exception.motif, MOTIF_PANIER_REFUSE)
        self.assertIn('A_REMPLACER', str(e.exception))
        self.assertIn('porte dérobée', str(e.exception))

    def test_le_panier_livre_est_refuse_aussi(self):
        with self.assertRaises(RefusMesure) as e:
            date_comptabilisation_62(
                debut_couverture_cedee=DEBUT, couverture_proportionnelle=False,
                date_deficit_sous_jacent=J(2025, 11, 1),
                traite_conclu_au_plus_tard=True,
                panier_du_deficit=PANIER_LIVRE)
        self.assertEqual(e.exception.motif, MOTIF_PANIER_REFUSE)

    def test_le_panier_552_reste_admis_MAIS_avec_sa_reserve(self):
        """⚠️ Le refuser supprimerait une date que la norme exige."""
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=False,
            date_deficit_sous_jacent=J(2025, 11, 1),
            traite_conclu_au_plus_tard=True, panier_du_deficit=PANIER)
        self.assertEqual(r.origine, ORIGINE_62B_DEFICIT_SOUS_JACENT)
        self.assertIn("N'EST PAS ACTUALISÉ", r.motif)
        self.assertIn('SURESTIME', r.motif)

    def test_le_panier_complet_actualise_est_admis_si_tout_est_declare(self):
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=False,
            date_deficit_sous_jacent=J(2025, 11, 1),
            traite_conclu_au_plus_tard=True,
            panier_du_deficit=PANIER_PREFERE_62B,
            courbe_declaree=COURBE, forme_prime_illiquidite=FORME,
            prime_illiquidite_declaree=ILLIQ,
            convention_actualisation_declaree=CONV)
        self.assertEqual(r.date, J(2025, 11, 1))
        self.assertNotIn("N'EST PAS ACTUALISÉ", r.motif)

    def test_le_panier_actualise_sans_COURBE_est_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            date_comptabilisation_62(
                debut_couverture_cedee=DEBUT,
                couverture_proportionnelle=False,
                date_deficit_sous_jacent=J(2025, 11, 1),
                traite_conclu_au_plus_tard=True,
                panier_du_deficit=PANIER_PREFERE_62B,
                forme_prime_illiquidite=FORME,
            prime_illiquidite_declaree=ILLIQ,
                convention_actualisation_declaree=CONV)
        self.assertEqual(e.exception.motif, MOTIF_ACTUALISATION_NON_DECLAREE)

    def test_le_panier_actualise_sans_CONVENTION_est_refuse(self):
        """⚠️ Ce n'est pas seulement la courbe qui se déclare."""
        with self.assertRaises(RefusMesure) as e:
            date_comptabilisation_62(
                debut_couverture_cedee=DEBUT,
                couverture_proportionnelle=False,
                date_deficit_sous_jacent=J(2025, 11, 1),
                traite_conclu_au_plus_tard=True,
                panier_du_deficit=PANIER_PREFERE_62B, courbe_declaree=COURBE,
                forme_prime_illiquidite=FORME,
            prime_illiquidite_declaree=ILLIQ)
        self.assertEqual(e.exception.motif, MOTIF_ACTUALISATION_NON_DECLAREE)
        self.assertIn('23 %', str(e.exception))
        self.assertIn('521, 539, 541 et 568', str(e.exception))

    def test_un_NEANT_MOTIVE_ne_bloque_PAS_la_datation(self):
        """⚠️ UN NÉANT MOTIVÉ EST UNE DÉCLARATION, PAS UNE ABSENCE.

        Les confondre bloquerait un cas légitime : si la prime d'illiquidité
        est nulle pour une raison établie, le groupe doit pouvoir être daté.
        """
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=False,
            date_deficit_sous_jacent=J(2025, 11, 1),
            traite_conclu_au_plus_tard=True,
            panier_du_deficit=PANIER_PREFERE_62B, courbe_declaree=COURBE,
            forme_prime_illiquidite=FORME_NEANT_MOTIVE,
            prime_illiquidite_declaree=(
                'hors plage CEIOPS, duree de reglement maximale 4,76 ans'),
            convention_actualisation_declaree=CONV)
        self.assertEqual(r.date, J(2025, 11, 1))
        self.assertIn('déclarée NULLE, et motivée', r.motif)

    def test_un_neant_NU_bloque_bien_la_datation(self):
        """⚠️ Le verrou dans l'autre sens : « néant » seul n'établit rien."""
        with self.assertRaises(SourceDesavouee) as e:
            date_comptabilisation_62(
                debut_couverture_cedee=DEBUT,
                couverture_proportionnelle=False,
                date_deficit_sous_jacent=J(2025, 11, 1),
                traite_conclu_au_plus_tard=True,
                panier_du_deficit=PANIER_PREFERE_62B, courbe_declaree=COURBE,
                forme_prime_illiquidite=FORME_NEANT_MOTIVE,
                prime_illiquidite_declaree='neant',
                convention_actualisation_declaree=CONV)
        self.assertIn('REDIT LE NÉANT', str(e.exception))

    def _refus_actualisation(self):
        with self.assertRaises(RefusMesure) as e:
            date_comptabilisation_62(
                debut_couverture_cedee=DEBUT,
                couverture_proportionnelle=False,
                date_deficit_sous_jacent=J(2025, 11, 1),
                traite_conclu_au_plus_tard=True,
                panier_du_deficit=PANIER_PREFERE_62B)
        return str(e.exception)

    def test_le_refus_nomme_la_PRIME_D_ILLIQUIDITE_comme_manquante(self):
        """⚠️ CE TEST A AFFIRMÉ L'INVERSE, ET C'ÉTAIT FAUX.

        Il exigeait que le refus réclame « le retraitement du CRA ». Or le
        CRA retire de la courbe swap le risque de crédit bancaire : §36 c)
        impose justement d'exclure les facteurs qui influent sur les prix de
        marché mais pas sur les flux d'assurance. Ce qui manque est la prime
        d'illiquidité du §36 a) et de B80.
        """
        msg = self._refus_actualisation()
        self.assertIn(DECLARATION_PRIME_ILLIQUIDITE, msg)
        self.assertIn("prime d'illiquidité", msg)
        self.assertIn('B80', msg)
        self.assertIn('§36 a)', msg)

    def test_la_PRIME_D_ILLIQUIDITE_est_une_declaration_A_PART(self):
        """⚠️ SÉPARÉE DE LA COURBE, ET C'EST LA LEÇON DU CRA.

        Courbe et convention déclarées, illiquidité manquante : le module
        doit refuser. La fondre dans « la courbe » la rendrait invisible, et
        un terme absorbé dans un mot global ne se rouvre pas.
        """
        with self.assertRaises(RefusMesure) as e:
            date_comptabilisation_62(
                debut_couverture_cedee=DEBUT,
                couverture_proportionnelle=False,
                date_deficit_sous_jacent=J(2025, 11, 1),
                traite_conclu_au_plus_tard=True,
                panier_du_deficit=PANIER_PREFERE_62B, courbe_declaree=COURBE,
                convention_actualisation_declaree=CONV)
        self.assertEqual(e.exception.motif, MOTIF_ACTUALISATION_NON_DECLAREE)
        self.assertIn(DECLARATION_PRIME_ILLIQUIDITE, str(e.exception))
        self.assertIn('1 des 3', str(e.exception))

    def test_le_refus_porte_l_ecueil_documente(self):
        """⚠️ « À LA FOIS le sans-risque ET la prime d'illiquidité »."""
        self.assertIn(ECUEIL_TAUX_INCOMPLET, self._refus_actualisation())

    def test_les_trois_declarations_sont_nommees_dans_le_refus(self):
        msg = self._refus_actualisation()
        for d in DECLARATIONS_DU_TAUX_36:
            self.assertIn(d, msg)
        self.assertIn('3 des 3', msg)

    def test_le_refus_dit_que_le_CRA_est_DEJA_conforme(self):
        """⚠️ Le verrou dans l'autre sens : ne pas redemander de le défaire."""
        msg = self._refus_actualisation()
        self.assertIn('DÉJÀ', msg)
        self.assertIn('§36 c)', msg)
        self.assertNotIn('doit être retraité', msg)

    def test_la_reserve_ne_descend_PAS_sur_une_date_du_62a(self):
        """⚠️ Une réserve hors sujet finit par ne plus être lue."""
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=False)
        self.assertNotIn("N'EST PAS ACTUALISÉ", r.motif)

    def test_le_panier_552_donne_toujours_la_meme_date(self):
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=False,
            date_deficit_sous_jacent=J(2025, 11, 1),
            traite_conclu_au_plus_tard=True, panier_du_deficit=PANIER)
        self.assertEqual(r.date, J(2025, 11, 1))
        self.assertEqual(r.origine, ORIGINE_62B_DEFICIT_SOUS_JACENT)

    def test_sans_date_de_deficit_aucun_panier_n_est_exige(self):
        r = date_comptabilisation_62(debut_couverture_cedee=DEBUT,
                                     couverture_proportionnelle=False)
        self.assertEqual(r.date, DEBUT)


class T4_Le62AEcarteLe62a(unittest.TestCase):
    """⚠️ « NONOBSTANT » — §62A n'entre pas en concours, il écarte."""

    def test_la_couverture_proportionnelle_est_reportee(self):
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=True,
            premiere_compta_sous_jacent=J(2026, 3, 15))
        self.assertEqual(r.date, J(2026, 3, 15))
        self.assertEqual(r.origine, ORIGINE_62A_REPORT)
        self.assertIn('NONOBSTANT', r.motif)

    def test_une_couverture_non_proportionnelle_n_est_pas_reportee(self):
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=False,
            premiere_compta_sous_jacent=J(2026, 3, 15))
        self.assertEqual(r.date, DEBUT)
        self.assertEqual(r.origine, ORIGINE_62A_DEBUT_COUVERTURE)

    def test_un_sous_jacent_anterieur_ne_reporte_rien(self):
        """§62A ne joue QUE si la date est POSTÉRIEURE."""
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=True,
            premiere_compta_sous_jacent=J(2025, 12, 1))
        self.assertEqual(r.date, DEBUT)

    def test_le_62b_peut_devancer_le_report_du_62A(self):
        """§62 retient la PREMIÈRE des dates applicables."""
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=True,
            premiere_compta_sous_jacent=J(2026, 3, 15),
            date_deficit_sous_jacent=J(2026, 2, 1),
            traite_conclu_au_plus_tard=True, panier_du_deficit=PANIER)
        self.assertEqual(r.date, J(2026, 2, 1))

    def test_un_traite_non_conclu_a_la_date_n_ouvre_pas_le_62b(self):
        """§62 b) porte une CONDITION, et elle n'est pas décorative."""
        r = date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=False,
            date_deficit_sous_jacent=J(2025, 11, 1),
            traite_conclu_au_plus_tard=False, panier_du_deficit=PANIER)
        self.assertEqual(r.date, DEBUT)


class T5_LeStatutDu18DescendAvecLaDate(unittest.TestCase):
    """⚠️ SOUS PAA, LE PANIER RENVERSE UNE PRÉSOMPTION — pas un verdict."""

    def _dater(self, en_paa):
        return date_comptabilisation_62(
            debut_couverture_cedee=DEBUT, couverture_proportionnelle=False,
            date_deficit_sous_jacent=J(2025, 11, 1),
            traite_conclu_au_plus_tard=True, panier_du_deficit=PANIER,
            sous_jacent_en_paa=en_paa)

    def test_en_paa_la_reserve_du_18_est_portee(self):
        self.assertIn(RESERVE_18_PAA, self._dater(True).motif)
        self.assertIn('RENVERSE UNE PRÉSOMPTION', self._dater(True).motif)

    def test_hors_paa_elle_ne_l_est_pas(self):
        """Le statut diffère : en modèle général, c'est un verdict."""
        self.assertNotIn(RESERVE_18_PAA, self._dater(False).motif)

    def test_la_date_est_la_meme_dans_les_deux_cas(self):
        """⚠️ §18 change le STATUT, pas la date — et c'est le point."""
        self.assertEqual(self._dater(True).date, self._dater(False).date)


if __name__ == '__main__':
    unittest.main()
