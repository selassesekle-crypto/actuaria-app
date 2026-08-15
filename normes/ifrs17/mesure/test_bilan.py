# -*- coding: utf-8 -*-
"""Tests W1 — le bilan du §78 : séparément, jamais compensé.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ AUCUN ORACLE. Aucune source publiée disponible ne chiffre un bilan IFRS 17
par portefeuille. Ces tests établissent des invariants et des refus.
"""
import unittest

from normes.ifrs17.mesure.bilan import (
    MOTIF_AUCUN_SOLDE,
    MOTIF_PORTEFEUILLE_ETRANGER,
    MOTIF_PORTEFEUILLE_MANQUANT,
    MOTIF_PORTEFEUILLE_VIDE,
    MOTIF_REASSURANCE_ABSENTE,
    SoldeGroupe,
    etat_situation_financiere,
    valeur_comptable_avec_frais_acquisition,
)
from normes.ifrs17.mesure.declaration import ContexteEvaluation
from normes.ifrs17.mesure.lrc_paa import RefusMesure

CONTEXTE = ContexteEvaluation(arrete='2026-12-31',
                              portefeuilles=('rc_auto', 'mrh', 'flotte'))
CONTEXTE_MRH = ContexteEvaluation(arrete='2026-12-31',
                                  portefeuilles=('mrh',))

#: Trois portefeuilles : deux passifs, un actif (creance de prime nette).
SOLDES = (
    SoldeGroupe('rc_auto', 'rc_auto|AUTRES|2026', 12_000.0),
    SoldeGroupe('rc_auto', 'rc_auto|AUTRES|2025', 3_000.0),
    SoldeGroupe('mrh', 'mrh|AUTRES|2026', 8_000.0),
    SoldeGroupe('flotte', 'flotte|AUTRES|2026', -5_000.0),
)


class W1_LaSeparationDuCoteActifEtDuCotePassif(unittest.TestCase):
    """W1 — le mot « séparément » du §78, et ce qu'il coûte de l'ignorer."""

    def test_un_portefeuille_net_negatif_est_un_ACTIF(self):
        """⚠️ UN LRC NEGATIF EST UN CAS REEL -- une creance de prime non
        encaissee. Le portefeuille bascule alors du cote ACTIF."""
        b = etat_situation_financiere(SOLDES, CONTEXTE)
        self.assertEqual([p.portefeuille for p in b.actifs], ['flotte'])
        self.assertEqual(b.total_actifs, 5_000.0)
        self.assertTrue(b.actifs[0].est_actif)
        print(f"    OK W1 : portefeuille 'flotte' a -5 000 -> ACTIF de "
              f"{b.total_actifs:,.0f}")

    def test_les_deux_cotes_ne_se_compensent_JAMAIS(self):
        """⚠️⚠️ LE PIEGE QUE CE MODULE EXISTE POUR EMPECHER.

        Compenser donnerait un bilan dont le TOTAL est juste et dont les
        DEUX LIGNES sont fausses -- une erreur qu'aucun controle d'equilibre
        ne verrait, puisque l'equilibre tient. Ici : 23 000 de passifs et
        5 000 d'actifs, jamais 18 000 nets.
        """
        b = etat_situation_financiere(SOLDES, CONTEXTE)
        self.assertEqual(b.total_passifs, 23_000.0)
        self.assertEqual(b.total_actifs, 5_000.0)
        compense = b.total_passifs - b.total_actifs
        self.assertEqual(compense, 18_000.0)
        self.assertNotEqual(b.total_passifs, compense)
        print(f"    OK W1b : {b.total_passifs:,.0f} de passifs ET "
              f"{b.total_actifs:,.0f} d'actifs -- jamais "
              f"{compense:,.0f} nets")

    def test_la_compensation_A_L_INTERIEUR_d_un_portefeuille_est_voulue(self):
        """⚠️ §78 NOMME LE PORTEFEUILLE QUATRE FOIS : c'est l'unite de
        presentation. Additionner les groupes d'un meme portefeuille est donc
        juste ; ce qui est interdit, c'est de franchir le portefeuille."""
        b = etat_situation_financiere(SOLDES, CONTEXTE)
        auto = next(p for p in b.passifs if p.portefeuille == 'rc_auto')
        self.assertEqual(auto.valeur, 15_000.0)
        self.assertEqual(auto.nb_groupes, 2)
        self.assertEqual(b.nb_portefeuilles, 3)
        print(f"    OK W1c : 'rc_auto' agrege ses {auto.nb_groupes} groupes "
              f"a {auto.valeur:,.0f} -- compensation INTERNE, voulue")

    def test_un_portefeuille_qui_bascule_change_de_cote_en_entier(self):
        """Un portefeuille dont un groupe suffit a inverser le net bascule
        TOUT ENTIER, il ne se coupe pas en deux."""
        soldes = (SoldeGroupe('mrh', 'mrh|A|2026', 8_000.0),
                  SoldeGroupe('mrh', 'mrh|B|2026', -9_500.0))
        b = etat_situation_financiere(soldes, CONTEXTE_MRH)
        self.assertEqual(len(b.actifs), 1)
        self.assertEqual(len(b.passifs), 0)
        self.assertEqual(b.total_actifs, 1_500.0)
        print(f"    OK W1d : 8 000 et -9 500 dans le meme portefeuille -> un "
              f"seul ACTIF de {b.total_actifs:,.0f}, jamais deux lignes")


class W2_CeQueLEtatNeCouvrePas(unittest.TestCase):
    """W2 — deux lignes présentées comme quatre tromperaient."""

    def test_l_absence_de_reassurance_est_DITE(self):
        """⚠️ §78 c) ET d) EXIGENT LA REASSURANCE DETENUE, SEPAREMENT. Elle
        n'est pas construite. Un etat a deux lignes lu comme complet ferait
        conclure qu'il n'y a PAS de reassurance -- ce qui n'est pas la meme
        chose que ne pas la mesurer."""
        b = etat_situation_financiere(SOLDES, CONTEXTE)
        self.assertEqual(b.motif, MOTIF_REASSURANCE_ABSENTE)
        self.assertIn('§78 c) et d)', b.motif)
        self.assertIn('ABSENTES, elles', b.motif)
        self.assertIn('ne valent pas zéro', b.motif)
        print("    OK W2 : l'etat dit qu'il est PARTIEL et pourquoi")


class W3_LArticle79(unittest.TestCase):
    """W3 — l'actif de frais d'acquisition s'incorpore."""

    def test_il_diminue_la_valeur_comptable_du_portefeuille(self):
        """⚠️ MEME REGLE QU'AU §55 a), et c'est le piege que l'oracle ICA
        5.2 attrape : un traitement separe donnerait 500 la ou la norme veut
        400."""
        self.assertEqual(
            valeur_comptable_avec_frais_acquisition(12_000.0, 2_000.0),
            10_000.0)
        print("    OK W3 : 12 000 de passif - 2 000 d'actif de frais "
              "d'acquisition = 10 000, sur UNE ligne")

    def test_un_actif_negatif_est_refuse(self):
        with self.assertRaises(RefusMesure) as ctx:
            valeur_comptable_avec_frais_acquisition(12_000.0, -500.0)
        self.assertEqual(ctx.exception.motif,
                         'actif_frais_acquisition_negatif')
        print("    OK W3b : actif de frais d'acquisition negatif -> refus")


class W4_LesRefus(unittest.TestCase):
    """W4 — ce que le module refuse plutôt que de le fausser."""

    def test_aucun_solde_n_est_pas_un_bilan_a_zero(self):
        """⚠️ LE MOTIF DE TOUTE CETTE SESSION."""
        with self.assertRaises(RefusMesure) as ctx:
            etat_situation_financiere([], CONTEXTE)
        self.assertEqual(ctx.exception.motif, MOTIF_AUCUN_SOLDE)
        self.assertIn('Ran 0 tests', str(ctx.exception))
        print("    OK W4 : aucun solde -> refus, jamais deux lignes nulles")

    def test_un_groupe_sans_portefeuille_est_refuse(self):
        """§78 presente PAR PORTEFEUILLE : sans lui, la ligne du bilan ou ce
        groupe atterrit n'est pas determinee."""
        with self.assertRaises(RefusMesure) as ctx:
            etat_situation_financiere(
                [SoldeGroupe('  ', 'g|A|2026', 100.0)], CONTEXTE)
        self.assertEqual(ctx.exception.motif, MOTIF_PORTEFEUILLE_VIDE)
        self.assertIn('g|A|2026', str(ctx.exception))
        print("    OK W4b : groupe sans portefeuille -> refus, et le groupe "
              "fautif est nomme")


class W5_LesDeuxEcartsDePerimetreNeSeValentPas(unittest.TestCase):
    """⚠️⚠️ L'ÉTRANGER EST VISIBLE, LE MANQUANT EST SILENCIEUX."""

    def test_un_portefeuille_ETRANGER_est_refuse(self):
        with self.assertRaises(RefusMesure) as e:
            etat_situation_financiere(
                SOLDES, ContexteEvaluation(arrete='2026-12-31',
                                           portefeuilles=('rc_auto', 'mrh')))
        self.assertEqual(e.exception.motif, MOTIF_PORTEFEUILLE_ETRANGER)
        self.assertIn("'flotte'", str(e.exception))
        self.assertIn('hors mandat', str(e.exception))

    def test_un_portefeuille_MANQUANT_est_refuse_ET_dit_pourquoi_c_est_pire(self):
        """⚠️ LE BILAN ÉQUILIBRE QUAND MÊME — aucun contrôle d'équilibre ne
        le verrait. C'est la forme que ce module combat déjà pour la
        compensation entre côtés."""
        large = ContexteEvaluation(
            arrete='2026-12-31',
            portefeuilles=('rc_auto', 'mrh', 'flotte', 'dommages_ouvrage'))
        with self.assertRaises(RefusMesure) as e:
            etat_situation_financiere(SOLDES, large)
        self.assertEqual(e.exception.motif, MOTIF_PORTEFEUILLE_MANQUANT)
        self.assertIn("'dommages_ouvrage'", str(e.exception))
        self.assertIn('ÉQUILIBRE QUAND MÊME', str(e.exception))
        self.assertIn('SILENCIEUX', str(e.exception))

    def test_le_bilan_EQUILIBRE_malgre_le_portefeuille_manquant(self):
        """⚠️ LA DÉMONSTRATION, ET C'EST ELLE QUI JUSTIFIE LE REFUS.

        Sans ce contrôle, le bilan amputé se présente exactement comme un
        bilan complet : mêmes totaux, mêmes lignes, rien qui cloche.
        """
        b = etat_situation_financiere(SOLDES, CONTEXTE)
        self.assertEqual(b.nb_portefeuilles, 3)
        self.assertGreater(b.total_passifs, 0.0)
        self.assertGreater(b.total_actifs, 0.0)

    def test_une_absence_DECLAREE_vide_est_acceptee(self):
        """⚠️ Un portefeuille sans aucun groupe à l'arrêté n'a rien à
        présenter — un refus aveugle bloquerait un cas légitime."""
        large = ContexteEvaluation(
            arrete='2026-12-31',
            portefeuilles=('rc_auto', 'mrh', 'flotte', 'dommages_ouvrage'))
        b = etat_situation_financiere(
            SOLDES, large,
            portefeuilles_vides_declares={
                'dommages_ouvrage': 'aucun groupe a cet arrete, note du 30/06'})
        self.assertEqual(b.nb_portefeuilles, 3)

    def test_une_absence_declaree_SANS_MOTIF_est_refusee(self):
        """« non vide » n'est pas « renseigne », ici comme ailleurs."""
        large = ContexteEvaluation(
            arrete='2026-12-31',
            portefeuilles=('rc_auto', 'mrh', 'flotte', 'dommages_ouvrage'))
        for motif in ('', 'A_RENSEIGNER'):
            with self.assertRaises(RefusMesure, msg=motif) as e:
                etat_situation_financiere(
                    SOLDES, large,
                    portefeuilles_vides_declares={'dommages_ouvrage': motif})
            self.assertEqual(e.exception.motif, MOTIF_PORTEFEUILLE_MANQUANT)

    def test_declarer_vide_un_portefeuille_PRESENT_se_contredit(self):
        with self.assertRaises(RefusMesure) as e:
            etat_situation_financiere(
                SOLDES, CONTEXTE,
                portefeuilles_vides_declares={'mrh': 'pretendu vide'})
        self.assertEqual(e.exception.motif, MOTIF_PORTEFEUILLE_MANQUANT)
        self.assertIn('se contredisent', str(e.exception))


if __name__ == '__main__':
    unittest.main()
