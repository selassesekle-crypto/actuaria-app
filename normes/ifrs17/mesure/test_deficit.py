# -*- coding: utf-8 -*-
"""Tests U1 — le test de déficit : déclenché, mené, ou non déclenché.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ AUCUN ORACLE. Le classeur de la section 7 de la note ICA, qui chiffre
l'élément de perte, est annoncé « under separate cover » et n'est pas en
notre possession. Ces tests établissent des invariants et des refus, pas une
concordance avec une source publiée.
"""
import unittest

from normes.ifrs17.mesure.deficit import (
    MOTIF_INCOHERENCE_59B,
    MOTIF_LRC_NEGATIF,
    MOTIF_NON_DECLENCHE,
    MOTIF_SANS_FAITS,
    MOTIF_SANS_SIGNATURE,
    declarer_declenchement,
    eprouver,
)
from normes.ifrs17.mesure.flux_execution import (
    Scenario,
    assembler,
    declarer_ajustement,
    declarer_courbe,
    esperance,
    montant_declare,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

PLATE = {1: 0.02, 2: 0.02}


def _flux(montants=(1000.0, 800.0), ajust=100.0, dispense=False,
          probabilise=False):
    if probabilise:
        lot = [esperance(a, [Scenario(m, 1.0)])
               for a, m in enumerate(montants, start=1)]
    else:
        lot = [montant_declare(a, m) for a, m in enumerate(montants, start=1)]
    courbe = None if dispense else declarer_courbe(
        PLATE, 'courbe interne', '2026-12-31', 'Selasse Sekle')
    aj = declarer_ajustement(ajust, 'quantile 75 %', 'cout du capital 6 %',
                             '2026-12-31', 'Selasse Sekle')
    return assembler(lot, courbe, aj, dispense_59b=dispense)


def _decl(declenche=True, faits='sinistralite 2026 superieure de 40 % a '
                                'la sinistralite attendue sur ce portefeuille'):
    return declarer_declenchement(declenche=declenche,
                                  faits_et_circonstances=faits,
                                  arrete='2026-12-31',
                                  actuaire_resp='Selasse Sekle')


class T1_NonDeclencheNEstPasSain(unittest.TestCase):
    """T1 — « non testé » ne doit pas ressembler à « testé et sain »."""

    def test_sans_declenchement_rien_n_est_conclu(self):
        """⚠️ LA MEME LECON QUE `PAA_NON_ETABLI`. En l'absence de faits et
        circonstances declares, la presomption de non-deficit de la PAA est
        MAINTENUE -- ce n'est pas un constat que le groupe est sain, c'est
        l'absence d'examen."""
        r = eprouver(_decl(declenche=False, faits=''))
        self.assertFalse(r.declenche)
        self.assertIsNone(r.element_de_perte)
        self.assertIsNone(r.ecart)
        self.assertIsNone(r.lrc)
        self.assertEqual(r.motif, MOTIF_NON_DECLENCHE)
        self.assertIn("PAS un constat", r.motif)
        print("    OK U1 : non declenche -> aucun chiffre, presomption "
              "maintenue, et le motif dit que ce n'est PAS un examen")

    def test_un_test_mene_sans_perte_dit_qu_il_a_ete_MENE(self):
        """⚠️ ET C'EST LA DIFFERENCE QUI COMPTE. Un test declenche qui ne
        trouve pas de perte EST un examen concluant ; un test non declenche
        ne l'est pas. Les deux rendent zero perte, et ils ne valent pas la
        meme chose."""
        r = eprouver(_decl(), lrc=5000.0, flux=_flux(probabilise=True))
        self.assertTrue(r.declenche)
        self.assertEqual(r.element_de_perte, 0.0)
        self.assertIn('MENÉ', r.motif)
        self.assertIn('examen concluant', r.motif)
        print(f"    OK U1b : test mene, ecart {r.ecart:+.1f}, aucune perte "
              "-- et le motif le distingue d'un test non declenche")


class T2_LEcartEtLElementDePerte(unittest.TestCase):
    """T2 — §57 puis §58."""

    def test_les_flux_qui_excedent_le_LRC_font_une_perte(self):
        f = _flux(probabilise=True)
        r = eprouver(_decl(), lrc=1000.0, flux=f)
        self.assertAlmostEqual(r.ecart, f.total - 1000.0, 9)
        self.assertAlmostEqual(r.element_de_perte, f.total - 1000.0, 9)
        self.assertGreater(r.element_de_perte, 0)
        print(f"    OK U2 : flux {f.total:.1f} contre LRC 1000 -> element "
              f"de perte {r.element_de_perte:.1f}")

    def test_l_element_de_perte_n_est_jamais_negatif(self):
        """⚠️ §58 : « DANS LA MESURE OU les flux EXCEDENT ». Un LRC
        superieur aux flux ne cree pas un profit -- il ne cree rien."""
        f = _flux(probabilise=True)
        r = eprouver(_decl(), lrc=99999.0, flux=f)
        self.assertEqual(r.element_de_perte, 0.0)
        self.assertLess(r.ecart, 0)
        print(f"    OK U2b : ecart {r.ecart:+.1f} negatif -> perte 0, "
              "jamais un profit fabrique")

    def test_la_reserve_du_33a_DESCEND_sur_l_element_de_perte(self):
        """⚠️ UN CHIFFRE CALCULE SUR UNE BASE NON ETABLIE NE DEVIENT PAS
        ETABLI EN CHANGEANT DE LIGNE. Si les flux portent la reserve du
        §33 a), l'element de perte la porte aussi."""
        r = eprouver(_decl(), lrc=1000.0, flux=_flux(probabilise=False))
        self.assertGreater(r.element_de_perte, 0)
        self.assertIn('BASE NON ÉTABLIE', r.motif)
        self.assertIn('§33 a)', r.motif)
        print("    OK U2c : la reserve du §33 a) descend sur l'element de "
              "perte, elle ne se perd pas en chemin")


class T3_LaRegleDeCoherenceDu57(unittest.TestCase):
    """T3 — la phrase du §57 la plus facile à manquer."""

    def test_dispense_59b_et_flux_actualises_sont_incoherents(self):
        """⚠️ §57 : « l'entite qui applique le paragraphe 59 b) SANS ajuster
        le passif au titre des sinistres survenus [...] NE DOIT PAS inclure
        de tels ajustements dans les flux de tresorerie d'execution ».

        Deux conventions dans le meme test fausseraient l'ecart dans un sens
        SYSTEMATIQUE : des flux actualises sont plus petits, donc l'element
        de perte serait sous-estime -- en faveur de l'entite.
        """
        with self.assertRaises(RefusMesure) as ctx:
            eprouver(_decl(), lrc=1000.0, flux=_flux(probabilise=True),
                     dispense_59b_sur_le_lic=True)
        self.assertEqual(ctx.exception.motif, MOTIF_INCOHERENCE_59B)
        self.assertIn('en faveur de l', str(ctx.exception))
        print("    OK U3 : dispense §59 b) + flux actualises -> REFUS, "
              "l'ecart aurait ete fausse en faveur de l'entite")

    def test_dispense_des_deux_cotes_est_coherente(self):
        f = _flux(dispense=True, probabilise=True)
        self.assertFalse(f.actualisation_appliquee)
        r = eprouver(_decl(), lrc=1000.0, flux=f,
                     dispense_59b_sur_le_lic=True)
        self.assertGreater(r.element_de_perte, 0)
        print("    OK U3b : dispense des deux cotes -> coherent, le test "
              "se mene")


class T4_LesRefus(unittest.TestCase):
    """T4 — ce que le module refuse plutôt que de le fausser."""

    def test_declencher_sans_dire_pourquoi_est_refuse(self):
        """⚠️ §57 SUBORDONNE LE TEST A CE QUE « LES FAITS ET CIRCONSTANCES
        INDIQUENT ». Un declenchement sans eux n'est verifiable par
        personne, et un element de perte non justifiable n'est pas
        presentable."""
        with self.assertRaises(RefusMesure) as ctx:
            declarer_declenchement(declenche=True, faits_et_circonstances='',
                                   arrete='2026-12-31',
                                   actuaire_resp='Selasse Sekle')
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_FAITS)
        print("    OK U4 : declenchement sans faits nommes -> refus")

    def test_sans_signataire_ou_sans_arrete_c_est_refuse(self):
        for kw in ({'actuaire_resp': '  '}, {'arrete': ''}):
            base = {'declenche': False, 'faits_et_circonstances': '',
                    'arrete': '2026-12-31', 'actuaire_resp': 'Selasse'}
            base.update(kw)
            with self.assertRaises(RefusMesure) as ctx:
                declarer_declenchement(**base)
            self.assertEqual(ctx.exception.motif, MOTIF_SANS_SIGNATURE)
        print("    OK U4b : sans signataire ou sans arrete -> refus")

    def test_un_terme_manquant_du_57_est_refuse(self):
        """Un ecart calcule sur un seul terme n'a aucun sens."""
        for kw in ({'lrc': 1000.0}, {'flux': _flux()}):
            with self.assertRaises(RefusMesure) as ctx:
                eprouver(_decl(), **kw)
            self.assertEqual(ctx.exception.motif, 'termes_du_57_incomplets')
        print("    OK U4c : un seul terme du §57 -> refus, jamais un ecart "
              "calcule sur la moitie")

    def test_un_LRC_negatif_est_refuse(self):
        with self.assertRaises(RefusMesure) as ctx:
            eprouver(_decl(), lrc=-500.0, flux=_flux())
        self.assertEqual(ctx.exception.motif, MOTIF_LRC_NEGATIF)
        print("    OK U4d : LRC negatif -> refus, creance de prime signalee")


if __name__ == '__main__':
    unittest.main()
