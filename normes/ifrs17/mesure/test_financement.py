# -*- coding: utf-8 -*-
"""Tests N1 — le §56 confronté au roll-forward ICA 5.6.1, sur 3 arrêtés.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ C'EST LE PREMIER TEST DE MESURE ULTÉRIEURE DU DÉPÔT. L'oracle 5.2 ne
portait qu'un arrêté : un calcul faux qui n'aurait perdu son terme qu'à
partir du second serait passé. Ici il y en a trois.
"""
import unittest

from normes.ifrs17.mesure.financement import (
    MOTIF_TAUX_ABERRANT,
    MOTIF_TAUX_SANS_ARRETE,
    MOTIF_TAUX_SANS_SIGNATURE,
    MOTIF_TAUX_SANS_SOURCE,
    roll_forward,
    verrouiller,
)
from normes.ifrs17.mesure.lrc_paa import (
    MOTIF_FINANCEMENT_NON_CONSTRUIT,
    RefusMesure,
    lrc_suivant,
)
from normes.ifrs17.oracles.ica_222092 import (
    CHAINE_EXACTE_5_6_1,
    ENTREE_5_6_1,
    ROLL_FORWARD_5_6_1,
    TOLERANCE,
)


def _taux():
    return verrouiller(
        ENTREE_5_6_1['taux_verrouille'],
        arrete_verrouillage='2026-01-01',
        source="oracle ICA/CIA doc 222092 section 5.6.1 — taux de l'exemple",
        actuaire_resp='Selasse Sekle')


def _mesure():
    return roll_forward(prime=ENTREE_5_6_1['prime'],
                        duree_ans=ENTREE_5_6_1['duree_couverture_ans'],
                        taux=_taux(), eligibilite_declaree=True)


class T1_LOracle5_6_1(unittest.TestCase):
    """T1 — trois arrêtés, face aux valeurs publiées."""

    def test_les_trois_LRC_de_cloture_tombent_sur_l_oracle(self):
        """⚠️ LA TOLERANCE EST 0,5, ET ELLE EST MESUREE. La source conseille
        1 unite ; sur un solde de 1 040 cela vaut 0,1 %, assez lache pour
        laisser passer un defaut."""
        mesure = _mesure()
        publie = ROLL_FORWARD_5_6_1[1:]
        self.assertEqual(len(mesure), len(publie))
        for m, p in zip(mesure, publie):
            self.assertLessEqual(
                abs(m.lrc_cloture - p['lrc_cloture']), TOLERANCE,
                f"{p['arrete']} : mesure {m.lrc_cloture}, "
                f"oracle {p['lrc_cloture']}")
        obtenus = [round(m.lrc_cloture, 2) for m in mesure]
        print(f"    OK N1 : LRC de cloture {obtenus} vs oracle "
              f"{[p['lrc_cloture'] for p in publie]}")

    def test_la_convention_de_signe_est_RETOURNEE_EXPLICITEMENT(self):
        """⚠️⚠️ LE PIEGE QUE L'ORACLE PORTE DANS SON PROPRE DOCUMENT.

        La section 5.2 publie le revenu POSITIF, la 5.6.1 le publie NEGATIF.
        Ce module rend le revenu positif, comme `lrc_paa`. Le retournement se
        fait ICI, et il est ECRIT : le laisser implicite ferait passer un
        signe inverse pour une egalite.
        """
        for m, p in zip(_mesure(), ROLL_FORWARD_5_6_1[1:]):
            attendu_positif = -p['revenu_total']       # <-- LE RETOURNEMENT
            self.assertLess(p['revenu_total'], 0)      # la source est negative
            self.assertGreater(m.revenu_total, 0)      # ce module est positif
            self.assertLessEqual(abs(m.revenu_total - attendu_positif), 1.0,
                                 p['arrete'])
        print("    OK N1b : revenu retourne explicitement — source negative, "
              "mesure positive, ecart borne")

    def test_la_composante_de_financement_du_revenu_tombe_aussi(self):
        """⚠️ LA COLONNE QUE J'ALLAIS OUBLIER DE CONFRONTER.

        L'oracle publie le revenu de financement separement du revenu de
        prime (-20, -40, -61). Ne verifier que le LRC de cloture laisserait
        passer une VENTILATION fausse dont les totaux tombent juste : deux
        erreurs qui se compensent entre les deux composantes donneraient le
        bon solde. C'est vulture qui a signale le champ non lu.
        """
        for m, p in zip(_mesure(), ROLL_FORWARD_5_6_1[1:]):
            attendu = -p['revenu_financement']         # retournement declare
            self.assertLessEqual(
                abs(m.revenu_financement - attendu), TOLERANCE,
                f"{p['arrete']} : mesure {m.revenu_financement}, "
                f"oracle {attendu}")
            self.assertAlmostEqual(
                m.revenu_prime,
                ENTREE_5_6_1['prime'] / ENTREE_5_6_1['duree_couverture_ans'],
                6)
        obtenus = [round(m.revenu_financement, 2) for m in _mesure()]
        print(f"    OK N1e : revenu de financement {obtenus} vs oracle "
              f"[20, 40, 61] — la VENTILATION, pas seulement le solde")

    def test_la_charge_financiere_suit_la_chaine_non_arrondie(self):
        """⚠️ ON SE COMPARE ICI A LA CHAINE NON ARRONDIE, PAS AUX VALEURS
        PUBLIEES, et c'est dit : la source publie 41 pour 40,80. Ce test
        verifie que la mesure ne reproduit pas l'ARRONDI de presentation
        mais la valeur reelle -- sinon on ajusterait le modele sur
        l'affichage du guide."""
        for m, exact in zip(_mesure(), CHAINE_EXACTE_5_6_1):
            self.assertAlmostEqual(m.charge_financiere,
                                   exact['charge_financiere'], 2)
            self.assertAlmostEqual(m.lrc_cloture, exact['lrc_cloture'], 2)
        print("    OK N1c : charges financieres 60,00 / 40,80 / 20,81 — la "
              "valeur reelle, pas l'arrondi publie 60 / 41 / 21")

    def test_le_LRC_s_eteint_au_dernier_arrete(self):
        """⚠️ CE ZERO NE PROUVE PRESQUE RIEN, ET L'ORACLE LE DIT. Le LRC DOIT
        s'eteindre en fin de couverture : c'est structurel. Le test existe
        pour attraper un terme PERDU, pas pour valider la mesure."""
        self.assertAlmostEqual(_mesure()[-1].lrc_cloture, 0.0, 6)
        print("    OK N1d : LRC eteint au dernier arrete — controle de "
              "terme perdu, pas preuve d'exactitude")


class T2_LeTauxEstSigne(unittest.TestCase):
    """T2 — un taux qui entre au résultat engage quelqu'un."""

    def test_sans_signataire_le_taux_est_refuse(self):
        for vide in ('', '   '):
            with self.assertRaises(RefusMesure) as ctx:
                verrouiller(0.02, '2026-01-01', 'courbe EIOPA', vide)
            self.assertEqual(ctx.exception.motif, MOTIF_TAUX_SANS_SIGNATURE)
        print("    OK N2 : pas de taux verrouille sans actuaire nomme")

    def test_sans_source_le_taux_est_refuse(self):
        """« D'ou vient ce taux » est la premiere question d'un CAC."""
        with self.assertRaises(RefusMesure) as ctx:
            verrouiller(0.02, '2026-01-01', '', 'Selasse Sekle')
        self.assertEqual(ctx.exception.motif, MOTIF_TAUX_SANS_SOURCE)
        print("    OK N2b : pas de taux sans sa source")

    def test_sans_date_de_verrouillage_le_taux_est_refuse(self):
        """§B72 a) fige le taux a la comptabilisation initiale ; sans cette
        date, il ne se rattache a aucun groupe."""
        with self.assertRaises(RefusMesure) as ctx:
            verrouiller(0.02, '', 'courbe EIOPA', 'Selasse Sekle')
        self.assertEqual(ctx.exception.motif, MOTIF_TAUX_SANS_ARRETE)
        print("    OK N2c : pas de taux sans sa date de verrouillage")

    def test_une_erreur_d_unite_est_attrapee(self):
        """⚠️ 2 SAISI POUR 2 % MULTIPLIERAIT LE LRC PAR TROIS EN UN ARRETE.
        Les bornes ne viennent d'AUCUN paragraphe -- elles n'existent que
        pour ce cas-la, et le motif le dit."""
        for aberrant in (2.0, -0.5, 100.0):
            with self.assertRaises(RefusMesure) as ctx:
                verrouiller(aberrant, '2026-01-01', 'courbe', 'Actuaire')
            self.assertEqual(ctx.exception.motif, MOTIF_TAUX_ABERRANT)
            self.assertIn("d'unité", str(ctx.exception))
        print("    OK N2d : erreur d'unite attrapee, bornes declarees comme "
              "vraisemblance et non comme norme")

    def test_le_taux_verrouille_porte_ses_quatre_champs(self):
        t = _taux()
        self.assertEqual(t.taux, 0.02)
        self.assertEqual(t.actuaire_resp, 'Selasse Sekle')
        self.assertTrue(t.source)
        self.assertTrue(t.arrete_verrouillage)
        print(f"    OK N2e : taux {t.taux}, verrouille au "
              f"{t.arrete_verrouillage}, atteste par {t.actuaire_resp}")


class T3_LeRefusDu55TombeQuandLaChargeArrive(unittest.TestCase):
    """T3 — le refus du lot précédent existait pour une raison précise."""

    def test_financement_declare_sans_charge_reste_refuse(self):
        """⚠️ LE REFUS N'A PAS ETE LEVE EN BLOC. Il visait le LRC
        silencieusement NON actualise ; il tient donc tant qu'aucune charge
        n'est fournie."""
        with self.assertRaises(RefusMesure) as ctx:
            lrc_suivant(3000.0, revenue_periode=1000.0,
                        eligibilite_declaree=True,
                        financement_significatif=True)
        self.assertEqual(ctx.exception.motif,
                         MOTIF_FINANCEMENT_NON_CONSTRUIT)
        print("    OK N3 : financement declare sans charge -> refus maintenu")

    def test_avec_la_charge_la_mesure_passe(self):
        obtenu = lrc_suivant(3000.0, revenue_periode=1020.0,
                             charge_financiere=60.0,
                             eligibilite_declaree=True,
                             financement_significatif=True)
        self.assertAlmostEqual(obtenu, 2040.0, 6)
        print(f"    OK N3b : 3000 + 60 - 1020 = {obtenu:.0f}, le refus tombe "
              "quand la charge arrive")


if __name__ == '__main__':
    unittest.main()
